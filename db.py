"""Database connection helper for SodhiCable MES."""
from __future__ import annotations

import sqlite3
from flask import g
from config import DATABASE


def get_db() -> sqlite3.Connection:
    """Get database connection for current request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception: BaseException | None = None) -> None:
    """Close database connection at end of request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()
