"""Persistence operations for fresh, private workspace chat/project tables."""
from contextlib import contextmanager
import time
import uuid

import workspace_store as WS


@contextmanager
def authorized_connection(db_path, user_id, workspace_id, *, write=False):
    """Hold one SQLite snapshot/lock while checking membership and using resources."""
    conn = WS.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        if not WS.active_workspace_in_connection(conn, user_id, workspace_id):
            conn.rollback()
            yield None
            return
        yield conn
        if conn.in_transaction:
            conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def _project(conn, user_id, workspace_id, project_id):
    return conn.execute(
        """SELECT workspace_id, id, name, instructions, created_at, updated_at
           FROM workspace_projects
           WHERE workspace_id = ? AND id = ? AND owner_user_id = ?""",
        (str(workspace_id), str(project_id), str(user_id)),
    ).fetchone()


def list_projects(db_path, user_id, workspace_id, limit=50):
    with authorized_connection(db_path, user_id, workspace_id) as conn:
        if conn is None:
            return None
        rows = conn.execute(
            """SELECT workspace_id, id, name, instructions, created_at, updated_at
               FROM workspace_projects
               WHERE workspace_id = ? AND owner_user_id = ?
               ORDER BY updated_at DESC, id LIMIT ?""",
            (str(workspace_id), str(user_id), int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]


def create_project(db_path, user_id, workspace_id, name, instructions):
    project_id = uuid.uuid4().hex
    now = time.time()
    with authorized_connection(db_path, user_id, workspace_id, write=True) as conn:
        if conn is None:
            return None
        conn.execute(
            """INSERT INTO workspace_projects
               (workspace_id, id, owner_user_id, name, instructions, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(workspace_id), project_id, str(user_id), name, instructions, now, now),
        )
        return _project(conn, user_id, workspace_id, project_id)


def get_project(db_path, user_id, workspace_id, project_id):
    with authorized_connection(db_path, user_id, workspace_id) as conn:
        if conn is None:
            return None
        row = _project(conn, user_id, workspace_id, project_id)
        return dict(row) if row else None


def update_project(db_path, user_id, workspace_id, project_id, fields):
    with authorized_connection(db_path, user_id, workspace_id, write=True) as conn:
        if conn is None or not _project(conn, user_id, workspace_id, project_id):
            return None
        assignments = [f"{key} = ?" for key in fields]
        values = list(fields.values())
        assignments.append("updated_at = ?")
        values.extend((time.time(), str(workspace_id), str(project_id), str(user_id)))
        conn.execute(
            f"UPDATE workspace_projects SET {', '.join(assignments)} "
            "WHERE workspace_id = ? AND id = ? AND owner_user_id = ?",
            values,
        )
        return dict(_project(conn, user_id, workspace_id, project_id))


def delete_project(db_path, user_id, workspace_id, project_id):
    with authorized_connection(db_path, user_id, workspace_id, write=True) as conn:
        if conn is None or not _project(conn, user_id, workspace_id, project_id):
            return False
        # Only the same owner's chats can reference this project (also enforced by a composite FK).
        conn.execute(
            """UPDATE workspace_chats SET project_id = NULL, updated_at = ?
               WHERE workspace_id = ? AND owner_user_id = ? AND project_id = ?""",
            (time.time(), str(workspace_id), str(user_id), str(project_id)),
        )
        conn.execute(
            """DELETE FROM workspace_projects
               WHERE workspace_id = ? AND id = ? AND owner_user_id = ?""",
            (str(workspace_id), str(project_id), str(user_id)),
        )
        return True


def _chat(conn, user_id, workspace_id, chat_id):
    return conn.execute(
        """SELECT workspace_id, id, title, pinned, project_id, created_at, updated_at
           FROM workspace_chats
           WHERE workspace_id = ? AND id = ? AND owner_user_id = ?""",
        (str(workspace_id), str(chat_id), str(user_id)),
    ).fetchone()


def list_chats(db_path, user_id, workspace_id, limit=50):
    with authorized_connection(db_path, user_id, workspace_id) as conn:
        if conn is None:
            return None
        rows = conn.execute(
            """SELECT workspace_id, id, title, pinned, project_id, created_at, updated_at
               FROM workspace_chats
               WHERE workspace_id = ? AND owner_user_id = ?
               ORDER BY pinned DESC, updated_at DESC, id LIMIT ?""",
            (str(workspace_id), str(user_id), int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]


def create_chat(db_path, user_id, workspace_id, title, project_id=None):
    chat_id = uuid.uuid4().hex
    now = time.time()
    with authorized_connection(db_path, user_id, workspace_id, write=True) as conn:
        if conn is None:
            return None
        if project_id is not None and not _project(conn, user_id, workspace_id, project_id):
            return None
        conn.execute(
            """INSERT INTO workspace_chats
               (workspace_id, id, owner_user_id, project_id, title, pinned, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
            (str(workspace_id), chat_id, str(user_id), project_id, title, now, now),
        )
        return dict(_chat(conn, user_id, workspace_id, chat_id))


def get_chat(db_path, user_id, workspace_id, chat_id):
    with authorized_connection(db_path, user_id, workspace_id) as conn:
        if conn is None:
            return None
        row = _chat(conn, user_id, workspace_id, chat_id)
        if row is None:
            return None
        messages = conn.execute(
            """SELECT id, role, content, model, created_at
               FROM workspace_messages
               WHERE workspace_id = ? AND chat_id = ? AND owner_user_id = ?
               ORDER BY id""",
            (str(workspace_id), str(chat_id), str(user_id)),
        ).fetchall()
        return {**dict(row), "messages": [dict(message) for message in messages]}


def update_chat(db_path, user_id, workspace_id, chat_id, fields):
    with authorized_connection(db_path, user_id, workspace_id, write=True) as conn:
        if conn is None or not _chat(conn, user_id, workspace_id, chat_id):
            return None
        if fields.get("project_id") is not None and not _project(
            conn, user_id, workspace_id, fields["project_id"]
        ):
            return None
        assignments = [f"{key} = ?" for key in fields]
        values = list(fields.values())
        assignments.append("updated_at = ?")
        values.extend((time.time(), str(workspace_id), str(chat_id), str(user_id)))
        conn.execute(
            f"UPDATE workspace_chats SET {', '.join(assignments)} "
            "WHERE workspace_id = ? AND id = ? AND owner_user_id = ?",
            values,
        )
        return dict(_chat(conn, user_id, workspace_id, chat_id))


def delete_chat(db_path, user_id, workspace_id, chat_id):
    with authorized_connection(db_path, user_id, workspace_id, write=True) as conn:
        if conn is None or not _chat(conn, user_id, workspace_id, chat_id):
            return False
        conn.execute(
            """DELETE FROM workspace_chats
               WHERE workspace_id = ? AND id = ? AND owner_user_id = ?""",
            (str(workspace_id), str(chat_id), str(user_id)),
        )
        return True


def append_user_message(db_path, user_id, workspace_id, chat_id, content):
    now = time.time()
    with authorized_connection(db_path, user_id, workspace_id, write=True) as conn:
        if conn is None or not _chat(conn, user_id, workspace_id, chat_id):
            return None
        cursor = conn.execute(
            """INSERT INTO workspace_messages
               (workspace_id, chat_id, owner_user_id, author_user_id, role, content, created_at)
               VALUES (?, ?, ?, ?, 'user', ?, ?)""",
            (str(workspace_id), str(chat_id), str(user_id), str(user_id), content, now),
        )
        conn.execute(
            """UPDATE workspace_chats SET updated_at = ?
               WHERE workspace_id = ? AND id = ? AND owner_user_id = ?""",
            (now, str(workspace_id), str(chat_id), str(user_id)),
        )
        return {"id": cursor.lastrowid, "role": "user", "content": content, "created_at": now}
