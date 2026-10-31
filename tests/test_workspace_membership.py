import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

import workspace_api
import workspace_membership_api
import workspace_membership_store as membership_store
import workspace_resources_api
import workspace_store as store


OWNER = "configured-owner"


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


class WorkspaceMembershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "data.db"
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """CREATE TABLE users(id TEXT PRIMARY KEY, email TEXT, name TEXT, role TEXT);
                   INSERT INTO users VALUES ('configured-owner', 'owner@example.test', 'Owner', 'owner');
                   INSERT INTO users VALUES ('u1', 'u1@example.test', 'User One', 'user');
                   INSERT INTO users VALUES ('u2', 'u2@example.test', 'User Two', 'user');
                   INSERT INTO users VALUES ('u3', 'u3@example.test', 'User Three', 'owner');"""
            )
        self.assertTrue(store.upgrade(self.db_path))
        with store.connect(self.db_path) as conn:
            insert_workspace(conn, "official-1", "OFFICIAL", "Official One", OWNER)
            insert_workspace(conn, "official-2", "OFFICIAL", "Official Two", OWNER)
            insert_workspace(conn, "official-paused", "OFFICIAL", "Paused", OWNER, "suspended")
            insert_workspace(conn, "personal-u2", "PERSONAL", "U2 Personal", "u2")
            insert_membership(conn, "official-1", OWNER, "owner", "active")
            insert_membership(conn, "official-1", "u2", "admin", "active")
            insert_membership(conn, "official-1", "u3", "owner", "active")
            insert_membership(conn, "personal-u2", "u2", "owner", "active")

        def test_session_actor(request: Request):
            actor = request.headers.get("x-test-user")
            if not actor:
                raise HTTPException(status_code=401, detail="login required")
            return actor

        app = FastAPI()
        app.include_router(workspace_api.create_workspace_router(self.db_path, test_session_actor, OWNER))
        app.include_router(
            workspace_resources_api.create_workspace_resources_router(
                self.db_path, test_session_actor
            )
        )
        app.include_router(
            workspace_membership_api.create_workspace_membership_router(
                self.db_path, test_session_actor, OWNER
            )
        )
        self.client = TestClient(app, headers={"Origin": "http://testserver"})

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def headers(self, user_id):
        return {"x-test-user": user_id}

    def rows(self, sql, params=()):
        with store.connect(self.db_path) as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def test_migration_never_auto_provisions_and_all_mutations_require_auth(self):
        with store.connect(self.db_path) as conn:
            before = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_membership_requests").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_membership_events").fetchone()[0], 0)
        self.assertEqual(self.client.get("/api/v1/workspaces").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/workspaces", json={}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/workspaces/official", json={}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/workspace-memberships/requests/official-1", json={}).status_code, 401)
        self.assertEqual(
            self.client.post("/api/v1/workspace-memberships/requests/fake/approve", json={}).status_code,
            401,
        )
        with store.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0], before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_membership_requests").fetchone()[0], 0)

    def test_official_creation_is_configured_owner_only_and_audited(self):
        before = self.rows("SELECT id FROM workspaces WHERE name='New Official'")
        for headers in ({}, self.headers("u1"), self.headers("u3")):
            response = self.client.post(
                "/api/v1/workspaces/official", headers=headers, json={"name": "New Official"}
            )
            self.assertIn(response.status_code, (401, 404))
        self.assertEqual(self.rows("SELECT id FROM workspaces WHERE name='New Official'"), before)
        self.assertEqual(self.rows("SELECT id FROM workspace_membership_events WHERE action='official_created'"), [])

        created = self.client.post(
            "/api/v1/workspaces/official", headers=self.headers(OWNER), json={"name": "New Official"}
        )
        self.assertEqual(created.status_code, 201, created.text)
        workspace = created.json()
        self.assertEqual((workspace["type"], workspace["name"], workspace["role"]), ("OFFICIAL", "New Official", "owner"))
        self.assertEqual(created.headers["cache-control"], "private, no-store")
        membership = self.rows(
            "SELECT role, status FROM workspace_memberships WHERE workspace_id=? AND user_id=?",
            (workspace["id"], OWNER),
        )[0]
        self.assertEqual((membership["role"], membership["status"]), ("owner", "active"))
        event = self.rows(
            "SELECT workspace_id, subject_user_id, actor_user_id, action, request_id "
            "FROM workspace_membership_events WHERE action='official_created'"
        )[0]
        self.assertEqual(
            (event["workspace_id"], event["subject_user_id"], event["actor_user_id"], event["request_id"]),
            (workspace["id"], OWNER, OWNER, None),
        )
        self.assertIn(workspace["id"], [w["id"] for w in self.client.get(
            "/api/v1/workspace-memberships/management", headers=self.headers(OWNER)
        ).json()["workspaces"]])

    def test_official_creation_rejects_duplicate_and_invalid_inputs(self):
        invalid_payloads = (
            {},
            {"name": ""},
            {"name": "   "},
            {"name": "x" * 121},
            {"name": 42},
            {"name": "Invalid", "type": "PERSONAL"},
            {"name": "Invalid", "role": "owner"},
        )
        for payload in invalid_payloads:
            response = self.client.post(
                "/api/v1/workspaces/official", headers=self.headers(OWNER), json=payload
            )
            self.assertEqual(response.status_code, 422, (payload, response.text))
        cross_site = self.client.post(
            "/api/v1/workspaces/official",
            headers={"x-test-user": OWNER, "Origin": "https://attacker.example"},
            json={"name": "Cross Site"},
        )
        self.assertEqual(cross_site.status_code, 403)
        self.assertEqual(self.rows("SELECT id FROM workspace_membership_events WHERE action='official_created'"), [])

        first = self.client.post(
            "/api/v1/workspaces/official", headers=self.headers(OWNER), json={"name": "Operations"}
        )
        duplicate = self.client.post(
            "/api/v1/workspaces/official", headers=self.headers(OWNER), json={"name": "  operations  "}
        )
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.assertEqual(
            len(self.rows("SELECT id FROM workspaces WHERE type='OFFICIAL' AND lower(name)=lower('Operations')")),
            1,
        )
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_events WHERE action='official_created'")), 1)

    def test_official_creation_rolls_back_if_audit_insert_fails(self):
        with store.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TRIGGER fail_official_created_audit
                   BEFORE INSERT ON workspace_membership_events
                   WHEN NEW.action='official_created'
                   BEGIN SELECT RAISE(ABORT, 'forced audit failure'); END"""
            )
        with self.assertRaises(sqlite3.IntegrityError):
            membership_store.create_official_workspace(self.db_path, OWNER, OWNER, "Atomic Official")
        self.assertEqual(self.rows("SELECT id FROM workspaces WHERE name='Atomic Official'"), [])
        self.assertEqual(self.rows("SELECT workspace_id FROM workspace_memberships WHERE workspace_id IN (SELECT id FROM workspaces WHERE name='Atomic Official')"), [])

    def test_personal_workspace_requires_explicit_action_and_is_created_atomically(self):
        created = self.client.post(
            "/api/v1/workspaces", headers=self.headers("u1"), json={"name": "U1 Personal"}
        )
        self.assertEqual(created.status_code, 201)
        workspace = created.json()
        self.assertEqual(workspace["type"], "PERSONAL")
        self.assertEqual(workspace["role"], "owner")
        self.assertEqual(self.client.get("/api/v1/workspaces/" + workspace["id"], headers=self.headers("u1")).status_code, 200)
        with store.connect(self.db_path) as conn:
            membership = conn.execute(
                "SELECT role, status FROM workspace_memberships WHERE workspace_id=? AND user_id='u1'",
                (workspace["id"],),
            ).fetchone()
            event = conn.execute(
                """SELECT workspace_id, subject_user_id, actor_user_id, action
                   FROM workspace_membership_events WHERE workspace_id=?""",
                (workspace["id"],),
            ).fetchone()
        self.assertEqual(tuple(membership), ("owner", "active"))
        self.assertEqual(tuple(event), (workspace["id"], "u1", "u1", "personal_created"))
        self.assertEqual(
            self.client.post("/api/v1/workspaces", headers=self.headers("u1"), json={}).status_code,
            409,
        )
        self.assertEqual(len(self.rows("SELECT id FROM workspaces WHERE created_by='u1' AND type='PERSONAL'")), 1)

    def test_personal_create_rejects_overposting_and_cross_site_origin(self):
        forged = self.client.post(
            "/api/v1/workspaces",
            headers=self.headers("u1"),
            json={"type": "OFFICIAL", "role": "owner", "name": "Forged"},
        )
        self.assertEqual(forged.status_code, 422)
        cross_site = self.client.post(
            "/api/v1/workspaces",
            headers={"x-test-user": "u1", "Origin": "https://attacker.example"},
            json={},
        )
        self.assertEqual(cross_site.status_code, 403)
        self.assertEqual(len(self.rows("SELECT id FROM workspaces WHERE created_by='u1'")), 0)

    def test_request_is_pending_only_duplicate_safe_and_not_auto_join(self):
        first = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["id"], first.json()["id"])
        self.assertEqual(self.client.get("/api/v1/workspaces", headers=self.headers("u1")).json(), [])
        self.assertEqual(self.client.get("/api/v1/workspaces/official-1", headers=self.headers("u1")).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/workspaces/official-1/projects", headers=self.headers("u1")).status_code, 404)
        request = self.rows("SELECT * FROM workspace_membership_requests WHERE id=?", (first.json()["id"],))[0]
        event_rows = self.rows("SELECT * FROM workspace_membership_events WHERE request_id=?", (first.json()["id"],))
        self.assertEqual(request["status"], "pending")
        self.assertIsNone(request["decided_by"])
        self.assertIsNotNone(request["requested_at"])
        self.assertEqual(len(event_rows), 1)
        self.assertEqual((event_rows[0]["subject_user_id"], event_rows[0]["actor_user_id"], event_rows[0]["action"]), ("u1", "u1", "requested"))

    def test_requester_can_read_only_own_request_status(self):
        request = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        ).json()
        own = self.client.get(
            "/api/v1/workspace-memberships/requests/mine", headers=self.headers("u1")
        )
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.headers["cache-control"], "private, no-store")
        self.assertEqual([(row["id"], row["status"]) for row in own.json()], [(request["id"], "pending")])
        self.assertEqual(
            self.client.get("/api/v1/workspace-memberships/requests/mine", headers=self.headers("u2")).json(),
            [],
        )
        self.client.post(
            f"/api/v1/workspace-memberships/requests/{request['id']}/approve",
            headers=self.headers(OWNER), json={},
        )
        updated = self.client.get(
            "/api/v1/workspace-memberships/requests/mine", headers=self.headers("u1")
        )
        self.assertEqual(updated.json()[0]["status"], "approved")
        self.assertEqual(updated.json()[0]["workspace_name"], "Official One")

    def test_only_active_official_workspaces_accept_requests(self):
        for workspace_id in ("missing", "personal-u2", "official-paused"):
            response = self.client.post(
                f"/api/v1/workspace-memberships/requests/{workspace_id}",
                headers=self.headers("u1"), json={},
            )
            self.assertEqual(response.status_code, 404)
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_requests")), 0)
        self.assertEqual(
            self.client.post(
                "/api/v1/workspace-memberships/requests/official-1",
                headers=self.headers("u2"), json={},
            ).status_code,
            409,
        )

    def test_invited_legacy_row_requires_request_and_owner_approval_suspended_row_stays_blocked(self):
        with store.connect(self.db_path) as conn:
            insert_membership(conn, "official-2", "u1", role="admin", status="invited")
        self.assertEqual(
            self.client.get("/api/v1/workspaces/official-2", headers=self.headers("u1")).status_code,
            404,
        )
        request = self.client.post(
            "/api/v1/workspace-memberships/requests/official-2",
            headers=self.headers("u1"), json={},
        )
        self.assertEqual(request.status_code, 201)
        self.assertEqual(
            self.client.get("/api/v1/workspaces/official-2", headers=self.headers("u1")).status_code,
            404,
        )
        self.client.post(
            f"/api/v1/workspace-memberships/requests/{request.json()['id']}/approve",
            headers=self.headers(OWNER), json={},
        )
        row = self.rows(
            "SELECT role, status FROM workspace_memberships WHERE workspace_id='official-2' AND user_id='u1'"
        )[0]
        self.assertEqual((row["role"], row["status"]), ("member", "active"))
        self.assertEqual(
            self.client.get("/api/v1/workspaces/official-2", headers=self.headers("u1")).status_code,
            200,
        )
        with store.connect(self.db_path) as conn:
            insert_membership(conn, "official-2", "u2", role="member", status="suspended")
        self.assertEqual(
            self.client.post(
                "/api/v1/workspace-memberships/requests/official-2",
                headers=self.headers("u2"), json={},
            ).status_code,
            409,
        )

    def test_exact_configured_owner_alone_can_view_requests_and_decide(self):
        request = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        ).json()
        management = self.client.get("/api/v1/workspace-memberships/management", headers=self.headers(OWNER))
        self.assertEqual(management.status_code, 200)
        official = next(row for row in management.json()["workspaces"] if row["id"] == "official-1")
        self.assertEqual(official["requests"][0]["id"], request["id"])
        self.assertEqual(official["requests"][0]["email"], "u1@example.test")
        # A database role or workspace membership role cannot substitute for the configured identity.
        for user_id in ("u2", "u3"):
            self.assertEqual(
                self.client.get("/api/v1/workspace-memberships/management", headers=self.headers(user_id)).status_code,
                404,
            )
            self.assertEqual(
                self.client.post(
                    f"/api/v1/workspace-memberships/requests/{request['id']}/approve",
                    headers=self.headers(user_id), json={},
                ).status_code,
                404,
            )
        self.assertEqual(
            self.client.post(
                f"/api/v1/workspace-memberships/requests/{request['id']}/approve",
                headers=self.headers(OWNER), json={"role": "admin"},
            ).status_code,
            422,
        )
        self.assertEqual(self.rows("SELECT status FROM workspace_membership_requests WHERE id=?", (request["id"],))[0]["status"], "pending")

    def test_approval_grants_member_only_and_creator_only_resource_access_remains(self):
        request = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        ).json()
        approved = self.client.post(
            f"/api/v1/workspace-memberships/requests/{request['id']}/approve",
            headers=self.headers(OWNER), json={},
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "approved")
        membership = self.rows(
            "SELECT role, status FROM workspace_memberships WHERE workspace_id='official-1' AND user_id='u1'"
        )[0]
        self.assertEqual((membership["role"], membership["status"]), ("member", "active"))
        request_row = self.rows("SELECT status, decided_by, decided_at FROM workspace_membership_requests WHERE id=?", (request["id"],))[0]
        self.assertEqual((request_row["status"], request_row["decided_by"]), ("approved", OWNER))
        self.assertIsNotNone(request_row["decided_at"])
        self.assertEqual(
            self.client.get("/api/v1/workspaces/official-1", headers=self.headers("u1")).status_code,
            200,
        )
        created = self.client.post(
            "/api/v1/workspaces/official-1/projects",
            headers=self.headers("u1"), json={"name": "U1 private"},
        )
        self.assertEqual(created.status_code, 201)
        project_id = created.json()["id"]
        self.assertEqual(
            self.client.get(f"/api/v1/workspaces/official-1/projects/{project_id}", headers=self.headers("u2")).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/workspaces/official-2/projects/{project_id}", headers=self.headers("u1")).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/workspace-memberships/requests/{request['id']}/approve",
                headers=self.headers(OWNER), json={},
            ).status_code,
            409,
        )
        event = self.rows(
            "SELECT actor_user_id, subject_user_id, action, request_id FROM workspace_membership_events WHERE action='approved'"
        )[0]
        self.assertEqual((event["actor_user_id"], event["subject_user_id"], event["request_id"]), (OWNER, "u1", request["id"]))

    def test_rejection_does_not_join_and_a_new_explicit_request_is_allowed(self):
        first = self.client.post(
            "/api/v1/workspace-memberships/requests/official-2",
            headers=self.headers("u1"), json={},
        ).json()
        rejected = self.client.post(
            f"/api/v1/workspace-memberships/requests/{first['id']}/reject",
            headers=self.headers(OWNER), json={},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/workspaces/official-2", headers=self.headers("u1")).status_code, 404)
        row = self.rows("SELECT status, decided_by, decided_at FROM workspace_membership_requests WHERE id=?", (first["id"],))[0]
        self.assertEqual((row["status"], row["decided_by"]), ("rejected", OWNER))
        self.assertIsNotNone(row["decided_at"])
        second = self.client.post(
            "/api/v1/workspace-memberships/requests/official-2",
            headers=self.headers("u1"), json={},
        )
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(second.json()["id"], first["id"])
        self.assertEqual(
            self.client.post(
                f"/api/v1/workspace-memberships/requests/{first['id']}/approve",
                headers=self.headers(OWNER), json={},
            ).status_code,
            409,
        )

    def test_owner_revocation_is_audited_and_immediately_removes_access_without_deleting_data(self):
        request = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        ).json()
        self.client.post(
            f"/api/v1/workspace-memberships/requests/{request['id']}/approve",
            headers=self.headers(OWNER), json={},
        )
        project = self.client.post(
            "/api/v1/workspaces/official-1/projects",
            headers=self.headers("u1"), json={"name": "Retained"},
        ).json()
        self.assertEqual(
            self.client.post(
                "/api/v1/workspace-memberships/workspaces/official-1/members/u1/revoke",
                headers=self.headers("u2"), json={},
            ).status_code,
            404,
        )
        revoked = self.client.post(
            "/api/v1/workspace-memberships/workspaces/official-1/members/u1/revoke",
            headers=self.headers(OWNER), json={},
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/workspaces/official-1", headers=self.headers("u1")).status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/workspaces/official-1/projects/{project['id']}", headers=self.headers("u1")).status_code, 404)
        with store.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT status FROM workspace_memberships WHERE workspace_id='official-1' AND user_id='u1'").fetchone()[0], "revoked")
            self.assertEqual(conn.execute("SELECT name FROM workspace_projects WHERE id=?", (project["id"],)).fetchone()[0], "Retained")
        event = self.rows("SELECT actor_user_id, subject_user_id, action, request_id FROM workspace_membership_events WHERE action='revoked'")[0]
        self.assertEqual((event["actor_user_id"], event["subject_user_id"], event["request_id"]), (OWNER, "u1", request["id"]))
        retry = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        )
        self.assertEqual(retry.status_code, 201)

    def test_owner_and_workspace_owner_memberships_cannot_be_revoked_by_this_flow(self):
        for user_id in (OWNER, "u3"):
            response = self.client.post(
                f"/api/v1/workspace-memberships/workspaces/official-1/members/{user_id}/revoke",
                headers=self.headers(OWNER), json={},
            )
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.rows("SELECT status FROM workspace_memberships WHERE workspace_id='official-1' AND user_id='u3'")[0]["status"], "active")
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_events WHERE action='revoked'")), 0)

    def test_owner_management_list_has_no_cache_and_unknown_or_cross_workspace_requests_are_hidden(self):
        self.assertEqual(
            self.client.get("/api/v1/workspace-memberships/management").status_code,
            401,
        )
        response = self.client.get("/api/v1/workspace-memberships/management", headers=self.headers("u1"))
        self.assertEqual(response.status_code, 404)
        owner = self.client.get("/api/v1/workspace-memberships/management", headers=self.headers(OWNER))
        self.assertEqual(owner.headers["cache-control"], "private, no-store")
        request = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        ).json()
        self.assertEqual(
            self.client.get(f"/api/v1/workspaces/official-2/chats/{request['id']}", headers=self.headers("u1")).status_code,
            404,
        )

    def test_mutations_require_same_origin_and_empty_body_for_membership_actions(self):
        cross_site = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers={"x-test-user": "u1", "Origin": "https://attacker.example"}, json={},
        )
        self.assertEqual(cross_site.status_code, 403)
        forged = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={"user_id": "u2", "role": "admin"},
        )
        self.assertEqual(forged.status_code, 422)
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_requests")), 0)

    def test_request_and_decision_audit_and_membership_state_roll_back_together(self):
        request = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        ).json()
        with store.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TRIGGER fail_approve_audit BEFORE INSERT ON workspace_membership_events
                   WHEN NEW.action = 'approved' BEGIN SELECT RAISE(ABORT, 'audit failure'); END"""
            )
        with self.assertRaises(sqlite3.IntegrityError):
            membership_store.decide_membership_request(
                self.db_path, OWNER, OWNER, request["id"], "approved"
            )
        with store.connect(self.db_path) as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM workspace_memberships WHERE workspace_id='official-1' AND user_id='u1'").fetchone())
            self.assertEqual(conn.execute("SELECT status FROM workspace_membership_requests WHERE id=?", (request["id"],)).fetchone()[0], "pending")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM workspace_membership_events WHERE action='approved'").fetchone()[0], 0)

    def test_personal_and_request_audit_failures_roll_back_all_state(self):
        with store.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TRIGGER fail_create_audit BEFORE INSERT ON workspace_membership_events
                   WHEN NEW.action IN ('personal_created', 'requested')
                   BEGIN SELECT RAISE(ABORT, 'audit failure'); END"""
            )
        with self.assertRaises(sqlite3.IntegrityError):
            membership_store.create_personal_workspace(self.db_path, "u1", "No partial workspace")
        with self.assertRaises(sqlite3.IntegrityError):
            membership_store.request_official_membership(self.db_path, "u1", "official-1")
        self.assertEqual(len(self.rows("SELECT id FROM workspaces WHERE type='PERSONAL' AND created_by='u1'")), 0)
        self.assertEqual(len(self.rows("SELECT workspace_id FROM workspace_memberships WHERE user_id='u1'")), 0)
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_requests")), 0)
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_events")), 0)

    def test_concurrent_personal_creation_has_one_atomic_winner(self):
        barrier = Barrier(3)

        def create():
            barrier.wait()
            try:
                return ("created", membership_store.create_personal_workspace(self.db_path, "u1"))
            except membership_store.MembershipConflict:
                return ("conflict", None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(create) for _ in range(2)]
            barrier.wait()
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(sorted(result[0] for result in results), ["conflict", "created"])
        self.assertEqual(len(self.rows("SELECT id FROM workspaces WHERE type='PERSONAL' AND created_by='u1'")), 1)
        self.assertEqual(len(self.rows("SELECT workspace_id FROM workspace_memberships WHERE user_id='u1' AND status='active'")), 1)
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_events WHERE action='personal_created'")), 1)

    def test_concurrent_membership_requests_are_serialized_and_idempotent(self):
        barrier = Barrier(3)

        def request():
            barrier.wait()
            return membership_store.request_official_membership(self.db_path, "u1", "official-1")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(request) for _ in range(2)]
            barrier.wait()
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(sorted(result["created"] for result in results), [False, True])
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_requests WHERE status='pending'")), 1)
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_events WHERE action='requested'")), 1)

    def test_concurrent_approval_has_one_winner_and_one_active_member(self):
        request = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        ).json()
        barrier = Barrier(3)

        def approve():
            barrier.wait()
            try:
                return membership_store.decide_membership_request(
                    self.db_path, OWNER, OWNER, request["id"], "approved"
                )["status"]
            except membership_store.MembershipConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(approve) for _ in range(2)]
            barrier.wait()
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(sorted(results), ["approved", "conflict"])
        self.assertEqual(len(self.rows("SELECT user_id FROM workspace_memberships WHERE workspace_id='official-1' AND user_id='u1' AND status='active'")), 1)
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_events WHERE action='approved'")), 1)

    def test_revocation_audit_failure_leaves_membership_active(self):
        request = self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        ).json()
        self.client.post(
            f"/api/v1/workspace-memberships/requests/{request['id']}/approve",
            headers=self.headers(OWNER), json={},
        )
        with store.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TRIGGER fail_revoke_audit BEFORE INSERT ON workspace_membership_events
                   WHEN NEW.action = 'revoked' BEGIN SELECT RAISE(ABORT, 'audit failure'); END"""
            )
        with self.assertRaises(sqlite3.IntegrityError):
            membership_store.revoke_official_membership(
                self.db_path, OWNER, OWNER, "official-1", "u1"
            )
        self.assertEqual(
            self.rows("SELECT status FROM workspace_memberships WHERE workspace_id='official-1' AND user_id='u1'")[0]["status"],
            "active",
        )
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_events WHERE action='revoked'")), 0)

    def test_populated_membership_history_blocks_migration_downgrade(self):
        self.client.post(
            "/api/v1/workspace-memberships/requests/official-1",
            headers=self.headers("u1"), json={},
        )
        with self.assertRaises(store.UnsafeWorkspaceDowngrade):
            store.downgrade(self.db_path)
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_requests WHERE status='pending'")), 1)
        self.assertEqual(len(self.rows("SELECT id FROM workspace_membership_events WHERE action='requested'")), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
