"""Explicit personal workspace creation and owner-controlled OFFICIAL membership."""
import sqlite3
import time
import uuid

import workspace_store as ws


class MembershipNotFound(RuntimeError):
    """The workspace, request, or membership is not available to this actor."""


class MembershipConflict(RuntimeError):
    """A membership state transition is not valid in the current state."""


def _event(conn, workspace_id, subject_user_id, actor_user_id, action, occurred_at, request_id=None):
    conn.execute(
        """INSERT INTO workspace_membership_events
           (workspace_id, subject_user_id, actor_user_id, action, occurred_at, request_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (workspace_id, subject_user_id, actor_user_id, action, occurred_at, request_id),
    )


def create_personal_workspace(db_path, user_id, name="ব্যক্তিগত"):
    """Create one PERSONAL workspace only when the authenticated user explicitly asks."""
    name = str(name or "").strip()
    if not 1 <= len(name) <= 120:
        raise ValueError("workspace name must contain 1-120 characters")
    workspace_id = uuid.uuid4().hex
    now = time.time()
    conn = ws.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        exists = conn.execute(
            "SELECT 1 FROM workspaces WHERE created_by = ? AND type = 'PERSONAL'",
            (str(user_id),),
        ).fetchone()
        if exists:
            raise MembershipConflict("PERSONAL workspace already exists")
        conn.execute(
            """INSERT INTO workspaces
               (id, type, name, status, created_by, created_at, updated_at)
               VALUES (?, 'PERSONAL', ?, 'active', ?, ?, ?)""",
            (workspace_id, name, str(user_id), now, now),
        )
        conn.execute(
            """INSERT INTO workspace_memberships
               (workspace_id, user_id, role, status, created_at)
               VALUES (?, ?, 'owner', 'active', ?)""",
            (workspace_id, str(user_id), now),
        )
        _event(conn, workspace_id, str(user_id), str(user_id), "personal_created", now)
        conn.commit()
        return {"id": workspace_id, "type": "PERSONAL", "name": name, "role": "owner"}
    except sqlite3.IntegrityError as exc:
        if conn.in_transaction:
            conn.rollback()
        if "unique" in str(exc).casefold():
            raise MembershipConflict("PERSONAL workspace already exists") from exc
        raise
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def create_official_workspace(db_path, actor_user_id, configured_owner_id, name):
    """Create an OFFICIAL workspace only by an explicit action from the configured owner."""
    if not configured_owner_id or str(actor_user_id) != str(configured_owner_id):
        raise MembershipNotFound("not found")
    if not isinstance(name, str):
        raise ValueError("workspace name must be text")
    name = name.strip()
    if not 1 <= len(name) <= 120:
        raise ValueError("workspace name must contain 1-120 characters")
    now = time.time()
    workspace_id = uuid.uuid4().hex
    conn = ws.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        owner = conn.execute("SELECT 1 FROM users WHERE id = ?", (str(configured_owner_id),)).fetchone()
        if not owner:
            raise MembershipNotFound("not found")
        existing_names = conn.execute(
            "SELECT name FROM workspaces WHERE type='OFFICIAL' AND status='active'"
        ).fetchall()
        if any(row["name"].strip().casefold() == name.casefold() for row in existing_names):
            raise MembershipConflict("an active OFFICIAL workspace with this name already exists")
        conn.execute(
            """INSERT INTO workspaces
               (id, type, name, status, created_by, created_at, updated_at)
               VALUES (?, 'OFFICIAL', ?, 'active', ?, ?, ?)""",
            (workspace_id, name, str(configured_owner_id), now, now),
        )
        conn.execute(
            """INSERT INTO workspace_memberships
               (workspace_id, user_id, role, status, created_at)
               VALUES (?, ?, 'owner', 'active', ?)""",
            (workspace_id, str(configured_owner_id), now),
        )
        _event(
            conn, workspace_id, str(configured_owner_id), str(configured_owner_id),
            "official_created", now,
        )
        conn.commit()
        return {
            "id": workspace_id,
            "type": "OFFICIAL",
            "name": name,
            "status": "active",
            "role": "owner",
        }
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def request_official_membership(db_path, user_id, workspace_id):
    """Create one pending request for an active OFFICIAL workspace; never grants access."""
    now = time.time()
    conn = ws.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        workspace = conn.execute(
            """SELECT id FROM workspaces
               WHERE id = ? AND type = 'OFFICIAL' AND status = 'active'""",
            (str(workspace_id),),
        ).fetchone()
        if not workspace:
            raise MembershipNotFound("not found")
        member = conn.execute(
            "SELECT status FROM workspace_memberships WHERE workspace_id = ? AND user_id = ?",
            (str(workspace_id), str(user_id)),
        ).fetchone()
        if member and member["status"] not in ("revoked", "invited"):
            raise MembershipConflict("membership cannot be requested in its current state")
        pending = conn.execute(
            """SELECT id FROM workspace_membership_requests
               WHERE workspace_id = ? AND user_id = ? AND status = 'pending'""",
            (str(workspace_id), str(user_id)),
        ).fetchone()
        if pending:
            conn.commit()
            return {"id": pending["id"], "status": "pending", "created": False}
        request_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO workspace_membership_requests
               (id, workspace_id, user_id, status, requested_at)
               VALUES (?, ?, ?, 'pending', ?)""",
            (request_id, str(workspace_id), str(user_id), now),
        )
        _event(
            conn, str(workspace_id), str(user_id), str(user_id), "requested", now, request_id
        )
        conn.commit()
        return {"id": request_id, "status": "pending", "created": True}
    except sqlite3.IntegrityError as exc:
        if conn.in_transaction:
            conn.rollback()
        # A concurrent request is serialized by BEGIN IMMEDIATE and protected by a partial index.
        if "unique" in str(exc).casefold():
            raise MembershipConflict("a pending request already exists") from exc
        raise
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def list_my_membership_requests(db_path, user_id, limit=50):
    """List only the caller's own recent request status; never expose other requesters."""
    conn = ws.connect(db_path)
    try:
        rows = conn.execute(
            """SELECT r.id, r.workspace_id, w.name AS workspace_name, r.status,
                      r.requested_at, r.decided_at
               FROM workspace_membership_requests AS r
               JOIN workspaces AS w ON w.id = r.workspace_id
               WHERE r.user_id = ?
               ORDER BY r.requested_at DESC, r.id DESC LIMIT ?""",
            (str(user_id), max(1, min(int(limit), 50))),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def owner_membership_management(db_path, actor_user_id, configured_owner_id):
    """Return pending requests and active members only to the configured owner."""
    if not configured_owner_id or str(actor_user_id) != str(configured_owner_id):
        return None
    conn = ws.connect(db_path)
    try:
        workspaces = conn.execute(
            """SELECT id, name, created_by FROM workspaces
               WHERE type = 'OFFICIAL' AND status = 'active' ORDER BY name, id"""
        ).fetchall()
        output = []
        for workspace in workspaces:
            requests = conn.execute(
                """SELECT r.id, r.user_id, COALESCE(NULLIF(trim(u.name), ''), u.email, u.id) AS display_name,
                          u.email, r.requested_at
                   FROM workspace_membership_requests AS r
                   JOIN users AS u ON u.id = r.user_id
                   WHERE r.workspace_id = ? AND r.status = 'pending'
                   ORDER BY r.requested_at, r.id""",
                (workspace["id"],),
            ).fetchall()
            members = conn.execute(
                """SELECT m.user_id, m.role, COALESCE(NULLIF(trim(u.name), ''), u.email, u.id) AS display_name,
                          u.email, m.created_at
                   FROM workspace_memberships AS m
                   JOIN users AS u ON u.id = m.user_id
                   WHERE m.workspace_id = ? AND m.status = 'active'
                   ORDER BY m.role, display_name, m.user_id""",
                (workspace["id"],),
            ).fetchall()
            output.append(
                {
                    "id": workspace["id"],
                    "name": workspace["name"],
                    "created_by": workspace["created_by"],
                    "requests": [dict(row) for row in requests],
                    "members": [dict(row) for row in members],
                }
            )
        return {"workspaces": output}
    finally:
        conn.close()


def decide_membership_request(db_path, actor_user_id, configured_owner_id, request_id, decision):
    """Atomically approve as member or reject; only the exact configured owner may decide."""
    if not configured_owner_id or str(actor_user_id) != str(configured_owner_id):
        raise MembershipNotFound("not found")
    if decision not in ("approved", "rejected"):
        raise ValueError("unsupported decision")
    now = time.time()
    conn = ws.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        request = conn.execute(
            """SELECT r.id, r.workspace_id, r.user_id, r.status, w.type, w.status AS workspace_status
               FROM workspace_membership_requests AS r
               JOIN workspaces AS w ON w.id = r.workspace_id
               WHERE r.id = ?""",
            (str(request_id),),
        ).fetchone()
        if not request or request["type"] != "OFFICIAL" or request["workspace_status"] != "active":
            raise MembershipNotFound("not found")
        if request["status"] != "pending":
            raise MembershipConflict("request has already been decided")
        if decision == "approved":
            membership = conn.execute(
                """SELECT role, status FROM workspace_memberships
                   WHERE workspace_id = ? AND user_id = ?""",
                (request["workspace_id"], request["user_id"]),
            ).fetchone()
            if membership and membership["status"] not in ("revoked", "invited"):
                raise MembershipConflict("membership must be reviewed before approval")
            if membership:
                conn.execute(
                    """UPDATE workspace_memberships
                       SET role = 'member', status = 'active', created_at = ?
                       WHERE workspace_id = ? AND user_id = ? AND status IN ('revoked', 'invited')""",
                    (now, request["workspace_id"], request["user_id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO workspace_memberships
                       (workspace_id, user_id, role, status, created_at)
                       VALUES (?, ?, 'member', 'active', ?)""",
                    (request["workspace_id"], request["user_id"], now),
                )
        updated = conn.execute(
            """UPDATE workspace_membership_requests
               SET status = ?, decided_by = ?, decided_at = ?
               WHERE id = ? AND status = 'pending'""",
            (decision, str(configured_owner_id), now, str(request_id)),
        )
        if updated.rowcount != 1:
            raise MembershipConflict("request has already been decided")
        _event(
            conn,
            request["workspace_id"],
            request["user_id"],
            str(configured_owner_id),
            decision,
            now,
            request["id"],
        )
        conn.commit()
        return {"id": request["id"], "status": decision}
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def revoke_official_membership(db_path, actor_user_id, configured_owner_id, workspace_id, member_user_id):
    """Revoke an active non-owner membership without deleting its row or owned resources."""
    if not configured_owner_id or str(actor_user_id) != str(configured_owner_id):
        raise MembershipNotFound("not found")
    if str(member_user_id) == str(configured_owner_id):
        raise MembershipConflict("configured owner membership cannot be revoked here")
    now = time.time()
    conn = ws.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        workspace = conn.execute(
            """SELECT id, created_by FROM workspaces
               WHERE id = ? AND type = 'OFFICIAL' AND status = 'active'""",
            (str(workspace_id),),
        ).fetchone()
        if not workspace:
            raise MembershipNotFound("not found")
        member = conn.execute(
            """SELECT role, status FROM workspace_memberships
               WHERE workspace_id = ? AND user_id = ?""",
            (str(workspace_id), str(member_user_id)),
        ).fetchone()
        if not member or member["status"] != "active":
            raise MembershipNotFound("not found")
        if member["role"] == "owner" or str(member_user_id) == str(workspace["created_by"]):
            raise MembershipConflict("workspace owner membership cannot be revoked here")
        result = conn.execute(
            """UPDATE workspace_memberships SET status = 'revoked'
               WHERE workspace_id = ? AND user_id = ? AND status = 'active'""",
            (str(workspace_id), str(member_user_id)),
        )
        if result.rowcount != 1:
            raise MembershipConflict("membership state changed")
        prior_request = conn.execute(
            """SELECT id FROM workspace_membership_requests
               WHERE workspace_id = ? AND user_id = ? AND status = 'approved'
               ORDER BY decided_at DESC LIMIT 1""",
            (str(workspace_id), str(member_user_id)),
        ).fetchone()
        _event(
            conn,
            str(workspace_id),
            str(member_user_id),
            str(configured_owner_id),
            "revoked",
            now,
            prior_request["id"] if prior_request else None,
        )
        conn.commit()
        return {"workspace_id": str(workspace_id), "user_id": str(member_user_id), "status": "revoked"}
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()
