"""SQLite workspace registry and isolated resource migrations.

Legacy chats/projects/messages remain in their existing tables. V2 creates
separate workspace-owned tables and never backfills or rewrites legacy rows.
"""
import argparse
import os
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = os.path.expanduser("~/bangla_bhai/data.db")
MIGRATION_TABLE = "workspace_schema_migrations"
MIGRATION_VERSION = 1
RESOURCE_MIGRATION_VERSION = 2
WORKSPACE_TABLES = {"workspaces", "workspace_memberships"}
RESOURCE_TABLES = {"workspace_projects", "workspace_chats", "workspace_messages"}
RESOURCE_INDEXES = {
    "personal_workspace_per_creator_idx",
    "workspace_projects_owner_updated_idx",
    "workspace_chats_owner_updated_idx",
    "workspace_messages_chat_idx",
}


class WorkspaceMigrationError(RuntimeError):
    """Workspace schema is inconsistent or cannot be changed safely."""


class UnsafeWorkspaceDowngrade(WorkspaceMigrationError):
    """Refuse to remove the registry when it contains workspace data."""


def connect(db_path):
    """Open an existing app database with FK enforcement on this connection."""
    path = os.fspath(db_path)
    if path != ":memory:" and not Path(path).is_file():
        raise WorkspaceMigrationError("database file does not exist; refusing to create it")
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    enabled = conn.execute("PRAGMA foreign_keys").fetchone()
    if enabled is None or enabled[0] != 1:
        conn.close()
        raise WorkspaceMigrationError("SQLite foreign-key enforcement is unavailable")
    return conn


def _tables(conn):
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _indexes(conn):
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }


def _versions(conn):
    if MIGRATION_TABLE not in _tables(conn):
        return []
    return [
        row["version"]
        for row in conn.execute(
            f"SELECT version FROM {MIGRATION_TABLE} ORDER BY version"
        )
    ]


def _registry_schema_statements():
    return (
        """CREATE TABLE workspaces (
            id TEXT PRIMARY KEY CHECK(length(id) BETWEEN 1 AND 128),
            type TEXT NOT NULL CHECK(type IN ('PERSONAL', 'OFFICIAL')),
            name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 120),
            status TEXT NOT NULL CHECK(status IN ('active', 'suspended', 'archived')),
            created_by TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE RESTRICT
        )""",
        """CREATE TABLE workspace_memberships (
            workspace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner', 'admin', 'member')),
            status TEXT NOT NULL CHECK(status IN ('invited', 'active', 'suspended', 'revoked')),
            created_at REAL NOT NULL,
            PRIMARY KEY(workspace_id, user_id),
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE RESTRICT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE RESTRICT
        )""",
        "CREATE INDEX workspace_memberships_user_status_idx "
        "ON workspace_memberships(user_id, status, workspace_id)",
        """CREATE TRIGGER workspace_type_immutable
            BEFORE UPDATE OF type ON workspaces
            FOR EACH ROW WHEN NEW.type <> OLD.type
            BEGIN
                SELECT RAISE(ABORT, 'workspace_type_immutable');
            END""",
    )


def _resource_schema_statements():
    return (
        """CREATE UNIQUE INDEX personal_workspace_per_creator_idx
            ON workspaces(created_by) WHERE type = 'PERSONAL'""",
        """CREATE TABLE workspace_projects (
            workspace_id TEXT NOT NULL,
            id TEXT NOT NULL CHECK(length(id) BETWEEN 1 AND 128),
            owner_user_id TEXT NOT NULL,
            name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 120),
            instructions TEXT NOT NULL DEFAULT '' CHECK(length(instructions) <= 8000),
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY(workspace_id, id),
            UNIQUE(workspace_id, owner_user_id, id),
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE RESTRICT,
            FOREIGN KEY(workspace_id, owner_user_id)
                REFERENCES workspace_memberships(workspace_id, user_id) ON DELETE RESTRICT
        )""",
        "CREATE INDEX workspace_projects_owner_updated_idx "
        "ON workspace_projects(workspace_id, owner_user_id, updated_at DESC)",
        """CREATE TABLE workspace_chats (
            workspace_id TEXT NOT NULL,
            id TEXT NOT NULL CHECK(length(id) BETWEEN 1 AND 128),
            owner_user_id TEXT NOT NULL,
            project_id TEXT,
            title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 200),
            pinned INTEGER NOT NULL DEFAULT 0 CHECK(pinned IN (0, 1)),
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY(workspace_id, id),
            UNIQUE(workspace_id, id, owner_user_id),
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE RESTRICT,
            FOREIGN KEY(workspace_id, owner_user_id)
                REFERENCES workspace_memberships(workspace_id, user_id) ON DELETE RESTRICT,
            FOREIGN KEY(workspace_id, owner_user_id, project_id)
                REFERENCES workspace_projects(workspace_id, owner_user_id, id) ON DELETE RESTRICT
        )""",
        "CREATE INDEX workspace_chats_owner_updated_idx "
        "ON workspace_chats(workspace_id, owner_user_id, updated_at DESC)",
        """CREATE TABLE workspace_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            author_user_id TEXT,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL CHECK(length(content) BETWEEN 1 AND 60000),
            model TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY(workspace_id, chat_id, owner_user_id)
                REFERENCES workspace_chats(workspace_id, id, owner_user_id) ON DELETE CASCADE,
            FOREIGN KEY(workspace_id, author_user_id)
                REFERENCES workspace_memberships(workspace_id, user_id) ON DELETE RESTRICT
        )""",
        "CREATE INDEX workspace_messages_chat_idx "
        "ON workspace_messages(workspace_id, chat_id, owner_user_id, id)",
    )


def _upgrade_registry(db_path):
    conn = connect(db_path)
    try:
        if "users" not in _tables(conn):
            raise WorkspaceMigrationError("existing users table is required")
        conn.execute("BEGIN IMMEDIATE")
        tables = _tables(conn)
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
                version INTEGER PRIMARY KEY CHECK(version > 0),
                name TEXT NOT NULL,
                applied_at REAL NOT NULL
            )"""
        )
        versions = _versions(conn)
        if MIGRATION_VERSION in versions:
            if not (WORKSPACE_TABLES | {MIGRATION_TABLE}).issubset(_tables(conn)):
                raise WorkspaceMigrationError("v1 is recorded but its schema is incomplete")
            if versions[0] != MIGRATION_VERSION or versions != sorted(set(versions)):
                raise WorkspaceMigrationError("unsupported workspace migration history")
            conn.commit()
            return False
        if versions:
            raise WorkspaceMigrationError("unsupported workspace migration version")
        collisions = WORKSPACE_TABLES.intersection(tables)
        if collisions:
            raise WorkspaceMigrationError(
                "untracked workspace table(s) already exist: " + ", ".join(sorted(collisions))
            )
        for statement in _registry_schema_statements():
            conn.execute(statement)
        conn.execute(
            f"INSERT INTO {MIGRATION_TABLE}(version, name, applied_at) VALUES (?, ?, ?)",
            (MIGRATION_VERSION, "workspace_registry_v1", time.time()),
        )
        conn.commit()
        return True
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def _upgrade_resources(db_path):
    conn = connect(db_path)
    try:
        if MIGRATION_TABLE not in _tables(conn):
            raise WorkspaceMigrationError("workspace registry v1 must be applied first")
        conn.execute("BEGIN IMMEDIATE")
        versions = _versions(conn)
        if MIGRATION_VERSION not in versions:
            raise WorkspaceMigrationError("workspace registry v1 must be applied first")
        tables = _tables(conn)
        indexes = _indexes(conn)
        if RESOURCE_MIGRATION_VERSION in versions:
            if versions != [MIGRATION_VERSION, RESOURCE_MIGRATION_VERSION]:
                raise WorkspaceMigrationError("unsupported workspace migration history")
            if not RESOURCE_TABLES.issubset(tables) or not RESOURCE_INDEXES.issubset(indexes):
                raise WorkspaceMigrationError("v2 is recorded but its schema is incomplete")
            conn.commit()
            return False
        if versions != [MIGRATION_VERSION]:
            raise WorkspaceMigrationError("unsupported workspace migration version")
        collisions = RESOURCE_TABLES.intersection(tables)
        if collisions:
            raise WorkspaceMigrationError(
                "untracked resource table(s) already exist: " + ", ".join(sorted(collisions))
            )
        index_collisions = RESOURCE_INDEXES.intersection(indexes)
        if index_collisions:
            raise WorkspaceMigrationError(
                "untracked resource index(es) already exist: " + ", ".join(sorted(index_collisions))
            )
        # Fail closed if pre-existing workspace rows contradict the approved one-PERSONAL rule.
        duplicate_personals = conn.execute(
            """SELECT created_by FROM workspaces WHERE type='PERSONAL'
               GROUP BY created_by HAVING COUNT(*) > 1 LIMIT 1"""
        ).fetchone()
        if duplicate_personals:
            raise WorkspaceMigrationError(
                "duplicate PERSONAL workspaces exist; resolve them before applying v2"
            )
        for statement in _resource_schema_statements():
            conn.execute(statement)
        conn.execute(
            f"INSERT INTO {MIGRATION_TABLE}(version, name, applied_at) VALUES (?, ?, ?)",
            (RESOURCE_MIGRATION_VERSION, "workspace_private_resources_v2", time.time()),
        )
        conn.commit()
        return True
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def upgrade(db_path=DEFAULT_DB):
    """Apply registry v1 and fresh workspace-resource v2 atomically per version."""
    changed_registry = _upgrade_registry(db_path)
    changed_resources = _upgrade_resources(db_path)
    return changed_registry or changed_resources


def downgrade(db_path=DEFAULT_DB):
    """Remove v2 then v1 only when all workspace-owned data is empty."""
    conn = connect(db_path)
    try:
        if MIGRATION_TABLE not in _tables(conn):
            return False
        conn.execute("BEGIN IMMEDIATE")
        versions = _versions(conn)
        changed = False
        tables = _tables(conn)
        if RESOURCE_MIGRATION_VERSION in versions:
            if versions != [MIGRATION_VERSION, RESOURCE_MIGRATION_VERSION]:
                raise WorkspaceMigrationError("downgrade newer workspace migrations first")
            if not RESOURCE_TABLES.issubset(tables):
                raise WorkspaceMigrationError("v2 migration record exists but resource tables are missing")
            has_resource_rows = any(
                conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
                for table in ("workspace_messages", "workspace_chats", "workspace_projects")
            )
            if has_resource_rows:
                raise UnsafeWorkspaceDowngrade(
                    "workspace resource data exists; export and approve a data-retention plan before downgrade"
                )
            conn.execute("DROP INDEX IF EXISTS workspace_messages_chat_idx")
            conn.execute("DROP INDEX IF EXISTS workspace_chats_owner_updated_idx")
            conn.execute("DROP INDEX IF EXISTS workspace_projects_owner_updated_idx")
            conn.execute("DROP TABLE workspace_messages")
            conn.execute("DROP TABLE workspace_chats")
            conn.execute("DROP TABLE workspace_projects")
            conn.execute("DROP INDEX IF EXISTS personal_workspace_per_creator_idx")
            conn.execute(
                f"DELETE FROM {MIGRATION_TABLE} WHERE version = ?",
                (RESOURCE_MIGRATION_VERSION,),
            )
            changed = True
            versions = _versions(conn)
            tables = _tables(conn)
        if MIGRATION_VERSION in versions:
            if versions != [MIGRATION_VERSION]:
                raise WorkspaceMigrationError("unsupported workspace migration history")
            if not WORKSPACE_TABLES.issubset(tables):
                raise WorkspaceMigrationError("v1 migration record exists but workspace tables are missing")
            has_registry_rows = any(
                conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
                for table in ("workspace_memberships", "workspaces")
            )
            if has_registry_rows:
                raise UnsafeWorkspaceDowngrade(
                    "workspace data exists; export and approve a data-retention plan before downgrade"
                )
            conn.execute("DROP TRIGGER IF EXISTS workspace_type_immutable")
            conn.execute("DROP INDEX IF EXISTS workspace_memberships_user_status_idx")
            conn.execute("DROP TABLE workspace_memberships")
            conn.execute("DROP TABLE workspaces")
            conn.execute(
                f"DELETE FROM {MIGRATION_TABLE} WHERE version = ?", (MIGRATION_VERSION,)
            )
            conn.execute(f"DROP TABLE {MIGRATION_TABLE}")
            changed = True
        elif versions:
            raise WorkspaceMigrationError("unsupported workspace migration version")
        conn.commit()
        return changed
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def _active_workspace_query():
    return """SELECT w.id, w.type, w.name, m.role
              FROM workspaces AS w
              JOIN workspace_memberships AS m ON m.workspace_id = w.id
              WHERE m.user_id = ? AND m.status = 'active' AND w.status = 'active'
                AND (w.type <> 'PERSONAL' OR (w.created_by = m.user_id AND m.role = 'owner'))"""


def active_workspace_in_connection(conn, user_id, workspace_id):
    """Resolve active membership within the caller's existing SQLite transaction."""
    if not user_id or not workspace_id:
        return None
    return conn.execute(
        _active_workspace_query() + " AND w.id = ?",
        (str(user_id), str(workspace_id)),
    ).fetchone()


def list_active_workspaces(db_path, user_id):
    """Return only active workspaces where the actor has approved membership."""
    if not user_id:
        return []
    conn = connect(db_path)
    try:
        rows = conn.execute(
            _active_workspace_query() + " ORDER BY w.type, w.id", (str(user_id),)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_active_workspace(db_path, user_id, workspace_id):
    """Resolve a workspace only through active membership; PERSONAL is creator-only."""
    if not user_id or not workspace_id:
        return None
    conn = connect(db_path)
    try:
        row = active_workspace_in_connection(conn, user_id, workspace_id)
        return dict(row) if row else None
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage the additive SQLite workspace schema")
    parser.add_argument("action", choices=("upgrade", "downgrade"))
    parser.add_argument("--db", default=DEFAULT_DB, help="Existing Bangla Bhai SQLite database")
    args = parser.parse_args(argv)
    changed = upgrade(args.db) if args.action == "upgrade" else downgrade(args.db)
    print("applied" if changed and args.action == "upgrade" else "reverted" if changed else "no change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
