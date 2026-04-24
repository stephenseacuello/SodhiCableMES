"""SodhiCable MES — Simple database migration runner.

Usage:
    python migrate.py              # Apply pending migrations
    python migrate.py --status     # Show migration status
    python migrate.py --create NAME # Create a new empty migration file
"""
from __future__ import annotations

import os
import sys
import sqlite3
import glob
from datetime import datetime

from config import DATABASE

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "database", "migrations")


def ensure_migrations_table(db: sqlite3.Connection) -> None:
    """Create the _migrations tracking table if it doesn't exist."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            migration_id TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.commit()


def get_applied(db: sqlite3.Connection) -> set[str]:
    """Return set of already-applied migration IDs."""
    rows = db.execute("SELECT migration_id FROM _migrations ORDER BY migration_id").fetchall()
    return {r[0] for r in rows}


def get_pending(db: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return list of (filename, path) for pending migrations, sorted."""
    applied = get_applied(db)
    migrations = []
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        name = os.path.basename(path)
        if name not in applied:
            migrations.append((name, path))
    return migrations


def apply_migrations(db: sqlite3.Connection) -> None:
    """Apply all pending migrations."""
    pending = get_pending(db)
    if not pending:
        print("No pending migrations.")
        return

    for name, path in pending:
        print(f"  Applying {name} ... ", end="")
        with open(path) as f:
            sql = f.read()
        try:
            db.executescript(sql)
            db.execute("INSERT INTO _migrations (migration_id) VALUES (?)", (name,))
            db.commit()
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")
            sys.exit(1)

    print(f"\n{len(pending)} migration(s) applied.")


def show_status(db: sqlite3.Connection) -> None:
    """Show which migrations are applied and which are pending."""
    applied = get_applied(db)
    all_files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))

    print(f"Database: {DATABASE}")
    print(f"Migrations directory: {MIGRATIONS_DIR}\n")

    if not all_files:
        print("No migration files found.")
        return

    for name in all_files:
        status = "applied" if name in applied else "PENDING"
        print(f"  [{status:>7}] {name}")


def create_migration(name: str) -> None:
    """Create a new empty migration file with the next sequence number."""
    os.makedirs(MIGRATIONS_DIR, exist_ok=True)
    existing = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    if existing:
        last_num = int(os.path.basename(existing[-1]).split("_")[0])
    else:
        last_num = 0

    seq = f"{last_num + 1:03d}"
    slug = name.lower().replace(" ", "_").replace("-", "_")
    filename = f"{seq}_{slug}.sql"
    path = os.path.join(MIGRATIONS_DIR, filename)

    with open(path, "w") as f:
        f.write(f"-- Migration {seq}: {name}\n\n")

    print(f"Created: {path}")


if __name__ == "__main__":
    if "--create" in sys.argv:
        idx = sys.argv.index("--create")
        if idx + 1 >= len(sys.argv):
            print("Usage: python migrate.py --create <migration_name>")
            sys.exit(1)
        create_migration(sys.argv[idx + 1])
    else:
        db = sqlite3.connect(DATABASE)
        ensure_migrations_table(db)
        if "--status" in sys.argv:
            show_status(db)
        else:
            apply_migrations(db)
        db.close()
