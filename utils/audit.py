"""
SodhiCable MES — Audit Trail Utility
Shared function for logging changes to the audit_trail table.
"""
from __future__ import annotations

import sqlite3


def log_audit(db: sqlite3.Connection, table_name: str, record_id: int | str, field_changed: str, old_value: str | None, new_value: str | None, changed_by: str | None = None, reason: str | None = None) -> None:
    """Insert a row into audit_trail for compliance tracking."""
    db.execute(
        """INSERT INTO audit_trail
           (table_name, record_id, field_changed, old_value, new_value, changed_by, changed_datetime, change_reason)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
        (table_name, str(record_id), field_changed,
         str(old_value) if old_value is not None else None,
         str(new_value) if new_value is not None else None,
         changed_by, reason),
    )
