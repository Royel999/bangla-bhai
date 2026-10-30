import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

import workspace_api
import workspace_store as store


def create_legacy_database(path):
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """CREATE TABLE users(id TEXT PRIMARY KEY, email TEXT);
               CREATE TABLE chats(id TEXT PRIMARY KEY, user TEXT, title TEXT);
               CREATE TABLE messages(id INTEGER PRIMARY KEY, chat_id TEXT, content TEXT);
               CREATE TABLE projects(id TEXT PRIMARY KEY, user TEXT, name TEXT);
               CREATE TABLE settings(user TEXT PRIMARY KEY, data TEXT);
               INSERT INTO users(id, email) VALUES ('u1', 'u1@example.test');
               INSERT INTO users(id, email) VALUES ('u2', 'u2@example.test');
               INSERT INTO chats VALUES ('legacy-c1', 'u1', 'Existing private chat');
               INSERT INTO messages VALUES (1, 'legacy-c1', 'legacy message');
               INSERT INTO projects VALUES ('legacy-p1', 'u1', 'Existing project');
               INSERT INTO settings VALUES ('u1', '{"theme":"dark"}');"""
        )
        conn.commit()
    finally:
        conn.close()


def insert_workspace(conn, workspace_id, workspace_type, name, created_by, status="active"):
    conn.execute(
        """INSERT INTO workspaces
           (id, type, name, status, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (workspace_id, workspace_type, name, status, created_by, 1.0, 1.0),
    )


def insert_membership(conn, workspace_id, user_id, role="member", status="active"):
    conn.execute(
        """INSERT INTO workspace_memberships
           (workspace_id, user_id, role, status, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (workspace_id, user_id, role, status, 1.0),
    )


class WorkspaceDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "data.db"
        create_legacy_database(self.db_path)
        self.assertTrue(store.upgrade(self.db_path))

    def tearDown(self):
        self.temp.cleanup()

    def test_upgrade_is_idempotent_empty_and_preserves_legacy_rows(self):
        self.assertFalse(store.upgrade(self.db_path))
        with store.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_memberships").fetchone()[0], 0)
            self.assertEqual(
                tuple(conn.execute("SELECT id, user, title FROM chats").fetchone()),
                ("legacy-c1", "u1", "Existing private chat"),
            )
            self.assertEqual(conn.execute("SELECT content FROM messages WHERE id=1").fetchone()[0], "legacy message")
            self.assertEqual(conn.execute("SELECT name FROM projects WHERE id='legacy-p1'").fetchone()[0], "Existing project")
            self.assertEqual(conn.execute("SELECT data FROM settings WHERE user='u1'").fetchone()[0], '{"theme":"dark"}')

    def test_foreign_keys_are_enabled_for_each_workspace_connection(self):
        with store.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            insert_workspace(conn, "p1", "PERSONAL", "Personal", "u1")
        with store.connect(self.db_path) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                insert_membership(conn, "p1", "missing-user")

    def test_workspace_type_role_and_user_foreign_key_constraints(self):
        with store.connect(self.db_path) as conn:
            insert_workspace(conn, "p1", "PERSONAL", "Personal", "u1")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE workspaces SET type='OFFICIAL' WHERE id='p1'")
            with self.assertRaises(sqlite3.IntegrityError):
                insert_membership(conn, "p1", "u1", role="superuser")
            with self.assertRaises(sqlite3.IntegrityError):
                insert_workspace(conn, "bad", "PERSONAL", "Bad", "missing-user")

    def test_empty_downgrade_drops_only_new_schema_and_keeps_legacy_rows(self):
        self.assertTrue(store.downgrade(self.db_path))
        self.assertFalse(store.downgrade(self.db_path))
        with sqlite3.connect(self.db_path) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn("workspaces", tables)
            self.assertNotIn("workspace_memberships", tables)
            self.assertNotIn(store.MIGRATION_TABLE, tables)
            self.assertEqual(conn.execute("SELECT title FROM chats WHERE id='legacy-c1'").fetchone()[0], "Existing private chat")
            self.assertEqual(conn.execute("SELECT content FROM messages WHERE id=1").fetchone()[0], "legacy message")
            self.assertEqual(conn.execute("SELECT name FROM projects WHERE id='legacy-p1'").fetchone()[0], "Existing project")
            self.assertEqual(conn.execute("SELECT data FROM settings WHERE user='u1'").fetchone()[0], '{"theme":"dark"}')

    def test_downgrade_refuses_to_drop_populated_registry(self):
        with store.connect(self.db_path) as conn:
            insert_workspace(conn, "p1", "PERSONAL", "Personal", "u1")
        with self.assertRaises(store.UnsafeWorkspaceDowngrade):
            store.downgrade(self.db_path)
        with store.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspaces WHERE id='p1'").fetchone()[0], 1)
            self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {store.MIGRATION_TABLE}").fetchone()[0], 1)

    def test_migration_requires_identity_table_and_rolls_back_cleanly(self):
        other = Path(self.temp.name) / "without-users.db"
        sqlite3.connect(other).close()
        with self.assertRaises(store.WorkspaceMigrationError):
            store.upgrade(other)
        with sqlite3.connect(other) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertEqual(tables, set())


class WorkspaceApiIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "data.db"
        create_legacy_database(self.db_path)
        store.upgrade(self.db_path)
        with store.connect(self.db_path) as conn:
            insert_workspace(conn, "p1", "PERSONAL", "Personal", "u1")
            insert_workspace(conn, "o1", "OFFICIAL", "Official", "u2")
            insert_membership(conn, "p1", "u1", "owner", "active")
            insert_membership(conn, "o1", "u2", "admin", "active")
            insert_membership(conn, "o1", "u1", "member", "suspended")

        def test_session_actor(request: Request):
            actor = request.headers.get("x-test-user")
            if not actor:
                raise HTTPException(status_code=401, detail="login required")
            return actor

        app = FastAPI()
        app.include_router(workspace_api.create_workspace_router(self.db_path, test_session_actor))
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_list_only_includes_the_authenticated_users_active_memberships(self):
        response = self.client.get("/api/v1/workspaces", headers={"x-test-user": "u1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()], ["p1"])
        self.assertEqual(response.headers["cache-control"], "private, no-store")

    def test_cross_workspace_and_unknown_id_return_the_same_404(self):
        denied = self.client.get("/api/v1/workspaces/o1", headers={"x-test-user": "u1"})
        missing = self.client.get("/api/v1/workspaces/not-a-real-id", headers={"x-test-user": "u1"})
        self.assertEqual(denied.status_code, 404)
        self.assertEqual(denied.json(), {"error": "not found"})
        self.assertEqual((denied.status_code, denied.json()), (missing.status_code, missing.json()))
        self.assertEqual(denied.headers["cache-control"], "private, no-store")

    def test_active_official_member_can_read_the_explicitly_joined_workspace(self):
        response = self.client.get("/api/v1/workspaces/o1", headers={"x-test-user": "u2"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": "o1", "type": "OFFICIAL", "name": "Official", "role": "admin"})

    def test_suspended_membership_is_not_authorized(self):
        response = self.client.get("/api/v1/workspaces/o1", headers={"x-test-user": "u1"})
        self.assertEqual(response.status_code, 404)

    def test_client_cannot_choose_another_actor_by_query_parameter(self):
        response = self.client.get("/api/v1/workspaces?user_id=u2", headers={"x-test-user": "u1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()], ["p1"])

    def test_unauthenticated_and_self_service_membership_mutations_are_denied(self):
        self.assertEqual(self.client.get("/api/v1/workspaces").status_code, 401)
        response = self.client.post("/api/v1/workspaces", headers={"x-test-user": "u1"})
        self.assertEqual(response.status_code, 405)


if __name__ == "__main__":
    unittest.main(verbosity=2)
