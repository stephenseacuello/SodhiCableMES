"""
SodhiCable MES — Auto Lot Number Generator
Generates intelligent lot numbers: YYMMDD-WCCODE-SEQ
"""
from __future__ import annotations

import sqlite3
from datetime import datetime


def generate_lot_number(db: sqlite3.Connection, wc_id: str = "GEN") -> str:
    """Generate a unique lot number encoding date, work center, and sequence.

    Format: YYMMDD-XXXX-NNN  (e.g. 260418-EXT1-003)
    """
    date_prefix = datetime.now().strftime("%y%m%d")
    wc_code = wc_id.replace("WC-", "").replace("-", "")[:4].upper()
    row = db.execute(
        "SELECT COUNT(*) AS cnt FROM lot_tracking WHERE output_lot LIKE ?",
        (f"{date_prefix}-{wc_code}-%",),
    ).fetchone()
    seq = (row["cnt"] or 0) + 1
    return f"{date_prefix}-{wc_code}-{seq:03d}"
