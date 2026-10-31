import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

import workspace_api
import workspace_resources_api
import workspace_store as store


def create_legacy_database(path):
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """CREATE TABLE users(id TEXT PRIMARY KEY, email TEXT);
               CREATE TABLE chats(id TEXT PRIMARY KEY, user TEXT, title TEXT);
               CREATE TABLE messages(id INTEGER PRIMARY KEY, chat_id TEXT, content TEXT);
               CREATE TABLE projects(id TEXT PRIMARY KEY, user TEXT, name TEXT);
               INSERT INTO users(id, email) VALUES ('u1', 'u1@example.test');
               INSERT INTO users(id, email) VALUES ('u2', 'u2@example.test');"""
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


class WorkspaceResourceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "data.db"
        create_legacy_database(self.db_path)
        self.assertTrue(store.upgrade(self.db_path))
        with store.connect(self.db_path) as conn:
            insert_workspace(conn, "p1", "PERSONAL", "U1 Personal", "u1")
            insert_workspace(conn, "o1", "OFFICIAL", "Official", "u2")
            insert_workspace(conn, "o2", "OFFICIAL", "Other Official", "u2")
            insert_membership(conn, "p1", "u1", "owner", "active")
            # A non-creator's PERSONAL membership must not grant access.
            insert_membership(conn, "p1", "u2", "member", "active")
            # Admin/owner roles deliberately do not grant access to another creator's rows.
            insert_membership(conn, "o1", "u1", "admin", "active")
            insert_membership(conn, "o1", "u2", "owner", "active")
            insert_membership(conn, "o2", "u2", "admin", "active")
            insert_membership(conn, "o2", "u1", "member", "suspended")

        def test_session_actor(request: Request):
            actor = request.headers.get("x-test-user")
            if not actor:
                raise HTTPException(status_code=401, detail="login required")
            return actor

        app = FastAPI()
        app.include_router(workspace_api.create_workspace_router(self.db_path, test_session_actor))
        app.include_router(
            workspace_resources_api.create_workspace_resources_router(
                self.db_path, test_session_actor
            )
        )
        self.client = TestClient(app, headers={"Origin": "http://testserver"})

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def headers(self, user_id):
        return {"x-test-user": user_id}

    def test_no_auto_provision_and_unauthenticated_resource_access_is_denied(self):
        with store.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_chats").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_projects").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_memberships").fetchone()[0], 6)
        self.assertEqual(self.client.get("/api/v1/workspaces/p1/chats").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/workspaces").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/workspaces/o1/members").status_code, 404)

    def test_mutation_rejects_cross_site_origin_before_writing(self):
        response = self.client.post(
            "/api/v1/workspaces/p1/projects",
            headers={"x-test-user": "u1", "Origin": "https://attacker.example"},
            json={"name": "must not be created"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(
            self.client.get("/api/v1/workspaces/p1/projects", headers=self.headers("u1")).json(),
            [],
        )

    def test_personal_workspace_is_creator_only_even_if_another_account_has_a_row(self):
        u1_list = self.client.get("/api/v1/workspaces", headers=self.headers("u1"))
        u2_list = self.client.get("/api/v1/workspaces", headers=self.headers("u2"))
        self.assertEqual([row["id"] for row in u1_list.json()], ["o1", "p1"])
        self.assertNotIn("p1", [row["id"] for row in u2_list.json()])
        self.assertEqual(self.client.get("/api/v1/workspaces/p1", headers=self.headers("u2")).status_code, 404)

    def test_new_projects_are_workspace_and_creator_scoped(self):
        created = self.client.post(
            "/api/v1/workspaces/o1/projects",
            headers=self.headers("u2"),
            json={"name": "U2 private project", "instructions": "private", "user_id": "u1"},
        )
        self.assertEqual(created.status_code, 422)  # identity overposting is rejected
        created = self.client.post(
            "/api/v1/workspaces/o1/projects",
            headers=self.headers("u2"),
            json={"name": "U2 private project", "instructions": "private"},
        )
        self.assertEqual(created.status_code, 201)
        project = created.json()
        self.assertEqual(project["workspace_id"], "o1")
        self.assertEqual(project["name"], "U2 private project")
        self.assertEqual(
            self.client.get("/api/v1/workspaces/o1/projects", headers=self.headers("u1")).json(),
            [],
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/workspaces/o1/projects/{project['id']}", headers=self.headers("u1")
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/workspaces/o1/projects/{project['id']}",
                headers=self.headers("u1"),
                json={"name": "hijacked"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/v1/workspaces/o1/projects/{project['id']}", headers=self.headers("u1")
            ).status_code,
            404,
        )
        after = self.client.get(
            f"/api/v1/workspaces/o1/projects/{project['id']}", headers=self.headers("u2")
        )
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.json()["name"], "U2 private project")

    def test_cross_workspace_and_same_workspace_other_creator_have_same_404(self):
        project = self.client.post(
            "/api/v1/workspaces/o1/projects", headers=self.headers("u2"), json={"name": "Private"}
        ).json()
        chat = self.client.post(
            "/api/v1/workspaces/o1/chats",
            headers=self.headers("u2"),
            json={"title": "U2 chat", "project_id": project["id"]},
        ).json()
        same_workspace = self.client.get(
            f"/api/v1/workspaces/o1/chats/{chat['id']}", headers=self.headers("u1")
        )
        cross_workspace = self.client.get(
            f"/api/v1/workspaces/o2/chats/{chat['id']}", headers=self.headers("u2")
        )
        no_membership = self.client.get(
            f"/api/v1/workspaces/o2/chats/{chat['id']}", headers=self.headers("u1")
        )
        missing = self.client.get(
            "/api/v1/workspaces/o1/chats/not-a-real-id", headers=self.headers("u1")
        )
        for response in (same_workspace, cross_workspace, no_membership, missing):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"error": "not found"})
            self.assertEqual(response.headers["cache-control"], "private, no-store")

    def test_other_member_cannot_update_delete_or_append_to_a_chat(self):
        chat = self.client.post(
            "/api/v1/workspaces/o1/chats", headers=self.headers("u2"), json={"title": "U2 chat"}
        ).json()
        path = f"/api/v1/workspaces/o1/chats/{chat['id']}"
        self.assertEqual(
            self.client.patch(path, headers=self.headers("u1"), json={"title": "changed"}).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                path + "/messages", headers=self.headers("u1"), json={"content": "unauthorized"}
            ).status_code,
            404,
        )
        self.assertEqual(self.client.delete(path, headers=self.headers("u1")).status_code, 404)
        self.assertEqual(self.client.get(path, headers=self.headers("u2")).json()["title"], "U2 chat")

    def test_creator_can_manage_only_own_project_chat_and_messages(self):
        project = self.client.post(
            "/api/v1/workspaces/o1/projects", headers=self.headers("u1"), json={"name": "Original"}
        ).json()
        chat = self.client.post(
            "/api/v1/workspaces/o1/chats",
            headers=self.headers("u1"),
            json={"title": "Original chat", "project_id": project["id"]},
        ).json()
        project_update = self.client.patch(
            f"/api/v1/workspaces/o1/projects/{project['id']}",
            headers=self.headers("u1"),
            json={"name": "Updated"},
        )
        self.assertEqual(project_update.status_code, 200)
        self.assertEqual(project_update.json()["name"], "Updated")
        chat_update = self.client.patch(
            f"/api/v1/workspaces/o1/chats/{chat['id']}",
            headers=self.headers("u1"),
            json={"title": "Updated chat", "pinned": True},
        )
        self.assertEqual(chat_update.status_code, 200)
        self.assertEqual(chat_update.json()["pinned"], 1)
        message = self.client.post(
            f"/api/v1/workspaces/o1/chats/{chat['id']}/messages",
            headers=self.headers("u1"),
            json={"content": "owned message"},
        )
        self.assertEqual(message.status_code, 201)
        self.assertEqual(
            self.client.delete(
                f"/api/v1/workspaces/o1/projects/{project['id']}", headers=self.headers("u1")
            ).status_code,
            200,
        )
        self.assertIsNone(
            self.client.get(
                f"/api/v1/workspaces/o1/chats/{chat['id']}", headers=self.headers("u1")
            ).json()["project_id"]
        )
        self.assertEqual(
            self.client.delete(
                f"/api/v1/workspaces/o1/chats/{chat['id']}", headers=self.headers("u1")
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/workspaces/o1/chats/{chat['id']}", headers=self.headers("u1")
            ).status_code,
            404,
        )
        with store.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_messages").fetchone()[0], 0)

    def test_message_role_is_server_owned_and_chat_project_link_is_same_creator(self):
        u2_project = self.client.post(
            "/api/v1/workspaces/o1/projects", headers=self.headers("u2"), json={"name": "U2 project"}
        ).json()
        forged = self.client.post(
            "/api/v1/workspaces/o1/chats",
            headers=self.headers("u1"),
            json={"title": "forged", "project_id": u2_project["id"]},
        )
        self.assertEqual(forged.status_code, 404)
        other_workspace_project = self.client.post(
            "/api/v1/workspaces/o2/projects", headers=self.headers("u2"), json={"name": "Other workspace"}
        ).json()
        cross_workspace_link = self.client.post(
            "/api/v1/workspaces/o1/chats",
            headers=self.headers("u2"),
            json={"title": "cross-link", "project_id": other_workspace_project["id"]},
        )
        self.assertEqual(cross_workspace_link.status_code, 404)
        own_project = self.client.post(
            "/api/v1/workspaces/o1/projects", headers=self.headers("u1"), json={"name": "U1 project"}
        ).json()
        chat = self.client.post(
            "/api/v1/workspaces/o1/chats",
            headers=self.headers("u1"),
            json={"title": "U1 chat", "project_id": own_project["id"]},
        ).json()
        message = self.client.post(
            f"/api/v1/workspaces/o1/chats/{chat['id']}/messages",
            headers=self.headers("u1"),
            json={"content": "hello", "role": "assistant"},
        )
        self.assertEqual(message.status_code, 422)
        message = self.client.post(
            f"/api/v1/workspaces/o1/chats/{chat['id']}/messages",
            headers=self.headers("u1"),
            json={"content": "hello"},
        )
        self.assertEqual(message.status_code, 201)
        self.assertEqual(message.json()["role"], "user")
        stored = self.client.get(
            f"/api/v1/workspaces/o1/chats/{chat['id']}", headers=self.headers("u1")
        ).json()
        self.assertEqual(stored["messages"][0]["content"], "hello")
        self.assertEqual(stored["messages"][0]["role"], "user")

    def test_fresh_resource_tables_require_workspace_and_creator_relationships(self):
        project = self.client.post(
            "/api/v1/workspaces/o1/projects", headers=self.headers("u2"), json={"name": "P"}
        ).json()
        chat = self.client.post(
            "/api/v1/workspaces/o1/chats", headers=self.headers("u2"), json={"title": "C"}
        ).json()
        with store.connect(self.db_path) as conn:
            for table in ("workspace_projects", "workspace_chats", "workspace_messages"):
                info = {row[1]: row for row in conn.execute(f"PRAGMA table_info({table})")}
                self.assertIn("workspace_id", info)
                self.assertEqual(info["workspace_id"][3], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """INSERT INTO workspace_chats
                       (workspace_id,id,owner_user_id,project_id,title,pinned,created_at,updated_at)
                       VALUES ('o1','bad-link','u1',?,'Bad',0,1,1)""",
                    (project["id"],),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """INSERT INTO workspace_messages
                       (workspace_id,chat_id,owner_user_id,author_user_id,role,content,created_at)
                       VALUES ('o1',?,'u1','u1','user','Bad owner link',1)""",
                    (chat["id"],),
                )

    def test_populated_resource_downgrade_is_refused_and_preserves_rows(self):
        project = self.client.post(
            "/api/v1/workspaces/o1/projects", headers=self.headers("u2"), json={"name": "Keep"}
        ).json()
        with self.assertRaises(store.UnsafeWorkspaceDowngrade):
            store.downgrade(self.db_path)
        self.assertEqual(
            self.client.get(
                f"/api/v1/workspaces/o1/projects/{project['id']}", headers=self.headers("u2")
            ).status_code,
            200,
        )
        with store.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_projects").fetchone()[0], 1)
            self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {store.MIGRATION_TABLE}").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
