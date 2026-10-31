import base64
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PROBE = r'''
import json
import os
from fastapi.testclient import TestClient
import app
import workspace_store as ws

owner = app.CFG["BB_USER"]
with ws.connect(app.DB) as conn:
    assert conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM workspace_memberships").fetchone()[0] == 0
assert app.AU.owner_user() == owner
assert os.path.realpath(app.AU.DB) == os.path.realpath(app.DB)
assert app._workspace_owner_id == owner

with app.db() as conn:
    conn.execute(
        "INSERT INTO projects VALUES(?,?,?,?,?)",
        ("legacy-project", owner, "Legacy project", "legacy instructions", 1.0),
    )
    conn.execute(
        "INSERT INTO chats VALUES(?,?,?,?,?,?,?)",
        ("legacy-chat", owner, "Legacy chat", 0, "legacy-project", 1.0, 1.0),
    )
    conn.execute(
        "INSERT INTO messages(chat_id,role,content,created) VALUES(?,?,?,?)",
        ("legacy-chat", "user", "LEGACY_ONLY_SENTINEL", 1.0),
    )

with TestClient(app.app, headers={"Origin": "http://testserver"}) as client:
    assert client.get("/bb/health").status_code == 200
    assert client.get("/api/v1/workspaces/not-created/chats").status_code == 401
    assert client.get("/api/v1/workspaces").status_code == 401
    assert client.post("/api/v1/workspaces/official", json={"name": "Anonymous Official"}).status_code == 401
    assert client.get("/api/v1/workspace-memberships/management").status_code == 401
    assert client.get("/api/v1/workspace-memberships/requests/mine").status_code == 401
    login = client.post(
        "/login", data={"username": owner, "password": app.CFG["BB_PASSWORD"]},
        follow_redirects=False,
    )
    assert login.status_code == 303, (login.status_code, login.text)

    assert client.get("/api/v1/workspace-memberships/management").json() == {"workspaces": []}
    assert client.get("/api/v1/workspace-memberships/requests/mine").json() == []
    assert client.get("/api/v1/workspaces").json() == []
    official_response = client.post("/api/v1/workspaces/official", json={"name": "CI Official"})
    assert official_response.status_code == 201, (official_response.status_code, official_response.text)
    official_id = official_response.json()["id"]
    assert official_response.json()["type"] == "OFFICIAL"
    assert client.get(f"/api/v1/workspaces/{official_id}").status_code == 200
    personal_response = client.post("/api/v1/workspaces", json={"name": "CI Personal"})
    assert personal_response.status_code == 201, (personal_response.status_code, personal_response.text)
    personal_id = personal_response.json()["id"]
    assert personal_response.json()["type"] == "PERSONAL"

    new_project_response = client.post(
        f"/api/v1/workspaces/{personal_id}/projects",
        json={"name": "Workspace-only project", "instructions": "WS_PROJECT_SENTINEL"},
    )
    assert new_project_response.status_code == 201, (new_project_response.status_code, new_project_response.text)
    new_project = new_project_response.json()
    new_chat_response = client.post(
        f"/api/v1/workspaces/{personal_id}/chats",
        json={"title": "Workspace-only chat", "project_id": new_project["id"]},
    )
    assert new_chat_response.status_code == 201, (new_chat_response.status_code, new_chat_response.text)
    new_chat = new_chat_response.json()
    new_message_response = client.post(
        f"/api/v1/workspaces/{personal_id}/chats/{new_chat['id']}/messages",
        json={"content": "WORKSPACE_ONLY_SENTINEL"},
    )
    assert new_message_response.status_code == 201, (new_message_response.status_code, new_message_response.text)
    assert [row["id"] for row in client.get(f"/api/v1/workspaces/{personal_id}/chats").json()] == [new_chat["id"]]
    assert [row["id"] for row in client.get(f"/api/v1/workspaces/{personal_id}/projects").json()] == [new_project["id"]]

    legacy_chats = client.get("/bb/api/chats").json()
    legacy_projects = client.get("/bb/api/projects").json()
    assert [row["id"] for row in legacy_chats] == ["legacy-chat"], legacy_chats
    assert [row["id"] for row in legacy_projects] == ["legacy-project"], legacy_projects
    assert client.get(f"/bb/api/chats/{new_chat['id']}").status_code == 404
    assert client.get(f"/bb/api/chats/{new_chat['id']}/export.md").status_code == 404
    assert client.patch(f"/bb/api/chats/{new_chat['id']}", json={"title": "hijack"}).status_code == 404
    assert client.delete(f"/bb/api/chats/{new_chat['id']}").status_code == 404
    assert client.post(f"/bb/api/chats/{new_chat['id']}/stream", json={"content": "do not run"}).status_code == 404
    assert client.post(f"/bb/api/chats/{new_chat['id']}/note", json={"user": "do not write"}).status_code == 404
    assert client.post(
        "/bb/api/skills/propose", json={"chat_id": new_chat["id"], "goal": "do not read"}
    ).status_code == 404

    # A legacy chat can reference only a legacy project; the workspace project stays private.
    old_chat = client.post(
        "/bb/api/chats", json={"title": "Legacy chat", "project": new_project["id"]}
    ).json()
    old_chat_record = client.get(f"/bb/api/chats/{old_chat['id']}").json()
    assert old_chat_record["project"] is None
    assert client.delete(f"/bb/api/chats/{old_chat['id']}").status_code == 200

    export = client.get("/bb/api/export")
    assert export.status_code == 200
    exported = export.text
    assert "LEGACY_ONLY_SENTINEL" in exported
    assert "WORKSPACE_ONLY_SENTINEL" not in exported
    assert "WS_PROJECT_SENTINEL" not in exported

    # Legacy project mutations target only the legacy table; they must leave the new row intact.
    assert client.patch(
        f"/bb/api/projects/{new_project['id']}", json={"name": "hijack"}
    ).status_code == 200
    assert client.delete(f"/bb/api/projects/{new_project['id']}").status_code == 200
    still_there = client.get(
        f"/api/v1/workspaces/{personal_id}/projects/{new_project['id']}"
    )
    assert still_there.status_code == 200, still_there.text
    assert still_there.json()["name"] == "Workspace-only project"

    # The legacy clear endpoint may delete legacy data, but must never touch fresh workspace tables.
    assert client.delete("/bb/api/data").status_code == 200
    assert client.get("/bb/api/chats").json() == []
    assert client.get("/bb/api/projects").json() == []
    assert client.get(f"/api/v1/workspaces/{personal_id}/chats/{new_chat['id']}").status_code == 200
    assert client.get(f"/api/v1/workspaces/{personal_id}/projects/{new_project['id']}").status_code == 200

    # New v1 routes are equally unable to resolve legacy IDs.
    assert client.get(f"/api/v1/workspaces/{personal_id}/chats/legacy-chat").status_code == 404
    assert client.get(f"/api/v1/workspaces/{personal_id}/projects/legacy-project").status_code == 404

with ws.connect(app.DB) as conn:
    assert conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM workspace_chats").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM workspace_projects").fetchone()[0] == 1
    assert conn.execute("SELECT content FROM workspace_messages").fetchone()[0] == "WORKSPACE_ONLY_SENTINEL"
    assert conn.execute("SELECT COUNT(*) FROM workspaces WHERE type='OFFICIAL' AND name='CI Official'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM workspace_membership_events WHERE action='official_created'").fetchone()[0] == 1
'''


class LegacyWorkspaceBoundaryTests(unittest.TestCase):
    def test_real_legacy_and_workspace_routes_are_data_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            base = home / "bangla_bhai"
            secrets = home / ".secrets"
            base.mkdir(parents=True)
            secrets.mkdir(parents=True)
            (base / "static").symlink_to(PROJECT_ROOT / "static", target_is_directory=True)
            (secrets / "bangla_bhai.env").write_text(
                "BB_USER=ci-owner\nBB_PASSWORD=ci-test-password\n"
                "BB_SESSION_SECRET=workspace-isolation-ci-secret\nBB_EDGE_SECRET=\n",
                encoding="utf-8",
            )
            for name in ("groq", "gemini", "openrouter", "bbai", "vapid", "telegram"):
                (secrets / f"{name}.env").write_text("", encoding="utf-8")
            (secrets / "bb_byok.key").write_bytes(base64.urlsafe_b64encode(b"\0" * 32))
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "PYTHONPATH": str(PROJECT_ROOT),
                    "BB_INSECURE_COOKIE": "1",
                    "BB_ROLE": "standby",
                }
            )
            completed = subprocess.run(
                [sys.executable, "-c", APP_PROBE],
                cwd=PROJECT_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + "\n" + completed.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
