"""SQLite workspace registry v1.

The migration adds only registry tables. It never creates workspace/member rows
or assigns existing user-owned data to a workspace.
"""
import argparse
import os
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = os.path.expanduser("~/bangla_bhai/data.db")
MIGRATION_TABLE = "workspace_schema_migrations"
MIGRATION_VERSION = 1
WORKSPACE_TABLES = {"workspaces", "workspace_memberships"}


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


def _schema_statements():
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


def upgrade(db_path=DEFAULT_DB):
    """Apply v1 atomically; repeat calls are safe after the auth schema exists."""
    conn = connect(db_path)
    try:
        if "users" not in _tables(conn):
            raise WorkspaceMigrationError("existing users table is required")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
                version INTEGER PRIMARY KEY CHECK(version > 0),
                name TEXT NOT NULL,
                applied_at REAL NOT NULL
            )"""
        )
        applied = conn.execute(
            f"SELECT version FROM {MIGRATION_TABLE} ORDER BY version"
        ).fetchall()
        versions = [row["version"] for row in applied]
        if MIGRATION_VERSION in versions:
            if not (WORKSPACE_TABLES | {MIGRATION_TABLE}).issubset(_tables(conn)):
                raise WorkspaceMigrationError("v1 is recorded but its schema is incomplete")
            conn.commit()
            return False
        if versions:
            raise WorkspaceMigrationError("unsupported workspace migration version")
        collisions = WORKSPACE_TABLES.intersection(_tables(conn))
        if collisions:
            raise WorkspaceMigrationError(
                "untracked workspace table(s) already exist: " + ", ".join(sorted(collisions))
            )
        for statement in _schema_statements():
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


def downgrade(db_path=DEFAULT_DB):
    """Remove v1 only while empty; never silently delete registry data."""
    conn = connect(db_path)
    try:
        if MIGRATION_TABLE not in _tables(conn):
            return False
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            f"SELECT version FROM {MIGRATION_TABLE} ORDER BY version"
        ).fetchall()
        versions = [row["version"] for row in rows]
        if MIGRATION_VERSION not in versions:
            conn.commit()
            return False
        if versions != [MIGRATION_VERSION]:
            raise WorkspaceMigrationError("downgrade newer workspace migrations first")
        if not WORKSPACE_TABLES.issubset(_tables(conn)):
            raise WorkspaceMigrationError("v1 migration record exists but workspace tables are missing")
        has_rows = any(
            conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
            for table in ("workspace_memberships", "workspaces")
        )
        if has_rows:
            raise UnsafeWorkspaceDowngrade(
                "workspace data exists; export and approve a data-retention plan before downgrade"
            )
        conn.execute("DROP TRIGGER IF EXISTS workspace_type_immutable")
        conn.execute("DROP INDEX IF EXISTS workspace_memberships_user_status_idx")
        conn.execute("DROP TABLE workspace_memberships")
        conn.execute("DROP TABLE workspaces")
        conn.execute(f"DELETE FROM {MIGRATION_TABLE} WHERE version = ?", (MIGRATION_VERSION,))
        conn.execute(f"DROP TABLE {MIGRATION_TABLE}")
        conn.commit()
        return True
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def list_active_workspaces(db_path, user_id):
    """Return only active workspaces with an active membership for this user."""
    if not user_id:
        return []
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """SELECT w.id, w.type, w.name, m.role
               FROM workspaces AS w
               JOIN workspace_memberships AS m ON m.workspace_id = w.id
               WHERE m.user_id = ? AND m.status = 'active' AND w.status = 'active'
               ORDER BY w.type, w.id""",
            (str(user_id),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_active_workspace(db_path, user_id, workspace_id):
    """Resolve the requested workspace only through the actor's active membership."""
    if not user_id or not workspace_id:
        return None
    conn = connect(db_path)
    try:
        row = conn.execute(
            """SELECT w.id, w.type, w.name, m.role
               FROM workspaces AS w
               JOIN workspace_memberships AS m ON m.workspace_id = w.id
               WHERE w.id = ? AND m.user_id = ?
                 AND m.status = 'active' AND w.status = 'active'""",
            (str(workspace_id), str(user_id)),
        ).fetchone()
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
