"""
engines/oee.py - Overall Equipment Effectiveness Engine

Computes OEE (Availability x Performance x Quality), First-Pass Yield,
the Six Big Losses breakdown, and per-shift KPI reports for SodhiCable
work centers.
"""

from datetime import date, datetime


# ---------------------------------------------------------------------------
# OEE
# ---------------------------------------------------------------------------
def compute_oee(conn, wc_id, shift_date=None):
    """Calculate OEE for a work center on a given date.

    OEE = Availability x Performance x Quality

    Reads from: shift_reports, downtime_log, scrap_log.

    Parameters
    ----------
    conn : sqlite3.Connection
    wc_id : str
        Work-center identifier.
    shift_date : str or None
        ISO date string (YYYY-MM-DD). Defaults to today.

    Returns
    -------
    dict
        availability, performance, quality, oee (all 0-1 floats),
        plus a *details* sub-dict with raw values.
    """
    if shift_date is None:
        shift_date = date.today().isoformat()

    cur = conn.cursor()

    # Get shift report data (uses actual schema columns)
    date_filter = shift_date or "%"
    cur.execute(
        """SELECT COALESCE(AVG(oee_availability), 0),
                  COALESCE(AVG(oee_performance), 0),
                  COALESCE(AVG(oee_quality), 0),
                  COALESCE(AVG(oee_overall), 0),
                  COALESCE(SUM(total_output_ft), 0),
                  COALESCE(SUM(total_scrap_ft), 0),
                  COALESCE(SUM(total_downtime_min), 0)
           FROM shift_reports
           WHERE wc_id = ? AND shift_date LIKE ?""",
        (wc_id, date_filter),
    )
    row = cur.fetchone()
    if row and row[0]:
        return {
            "wc_id": wc_id,
            "availability": round(row[0] * 100, 1),
            "performance": round(row[1] * 100, 1),
            "quality": round(row[2] * 100, 1),
            "oee": round(row[3] * 100, 1),
            "total_output_ft": row[4],
            "total_scrap_ft": row[5],
            "total_downtime_min": row[6],
        }

    # Fallback: compute from raw data
    planned_min = 480  # 8-hour shift default
    actual_output = 0
    rated_output = 0

    # Downtime from downtime_log
    cur.execute(
        "SELECT COALESCE(SUM(duration_min), 0) FROM downtime_log WHERE wc_id = ?",
        (wc_id,),
    )
    (downtime_min,) = cur.fetchone()

    # Scrap
    cur.execute(
        "SELECT COALESCE(SUM(quantity_ft), 0) FROM scrap_log WHERE wc_id = ?",
        (wc_id,),
    )
    (scrap_qty,) = cur.fetchone()

    # Guard against division by zero
    if planned_min == 0:
        return {
            "availability": 0.0,
            "performance": 0.0,
            "quality": 0.0,
            "oee": 0.0,
            "details": {
                "planned_minutes": 0,
                "downtime_minutes": downtime_min,
                "actual_output": actual_output,
                "rated_output": rated_output,
                "scrap_qty": scrap_qty,
            },
        }

    availability = (planned_min - downtime_min) / planned_min
    performance = actual_output / rated_output if rated_output else 0.0
    total_produced = actual_output  # includes scrap
    quality = (total_produced - scrap_qty) / total_produced if total_produced else 0.0
    oee = availability * performance * quality

    return {
        "availability": round(availability, 4),
        "performance": round(performance, 4),
        "quality": round(quality, 4),
        "oee": round(oee, 4),
        "details": {
            "planned_minutes": planned_min,
            "downtime_minutes": downtime_min,
            "actual_output": actual_output,
            "rated_output": rated_output,
            "scrap_qty": scrap_qty,
        },
    }


# ---------------------------------------------------------------------------
# First-Pass Yield
# ---------------------------------------------------------------------------
def compute_fpy(conn, wc_id=None):
    """Compute First-Pass Yield across process steps.

    FPY = product of (1 - defect_rate) for each step.

    Reads from: quality_steps (columns: step_id, wc_id, defect_rate).

    Parameters
    ----------
    conn : sqlite3.Connection
    wc_id : str or None
        Filter to a single work center. None = plant-wide.

    Returns
    -------
    float
        First-pass yield as a decimal (0-1).
    """
    cur = conn.cursor()
    if wc_id:
        cur.execute(
            "SELECT defect_rate FROM quality_steps WHERE wc_id = ?", (wc_id,)
        )
    else:
        cur.execute("SELECT defect_rate FROM quality_steps")

    rows = cur.fetchall()
    if not rows:
        return 1.0

    fpy = 1.0
    for (dr,) in rows:
        fpy *= 1.0 - dr
    return round(fpy, 6)


# ---------------------------------------------------------------------------
# Six Big Losses
# ---------------------------------------------------------------------------
def compute_six_big_losses(conn, wc_id):
    """Categorise downtime and waste into the Six Big Losses.

    Categories (TPM standard)
    -------------------------
    1. Equipment Failure — unplanned breakdown stops
    2. Setup & Adjustment — changeover, calibration
    3. Idling & Minor Stops — jams, sensor trips, short stoppages
    4. Reduced Speed — running below rated capacity
    5. Process Defects — scrap/rework during steady-state production
    6. Startup Losses — scrap/yield loss during startup & warmup

    Maps from downtime_log.category (Breakdown, Setup, MinorStop,
    ReducedSpeed, PM, MaterialWait, QualityHold, NoOrders) and
    scrap_log.cause_code to the six standard losses.

    Returns
    -------
    dict
        Keys are the six loss category names; values are total minutes.
    """
    # Mapping from downtime_log.category → 6 Big Losses
    _DOWNTIME_MAP = {
        "Breakdown": "equipment_failure",
        "Equipment": "equipment_failure",
        "Equipment Failure": "equipment_failure",
        "Setup": "setup_adjustment",
        "Changeover": "setup_adjustment",
        "Setup/Changeover": "setup_adjustment",
        "MinorStop": "idling_minor_stops",
        "Minor Stop": "idling_minor_stops",
        "Idle": "idling_minor_stops",
        "MaterialWait": "idling_minor_stops",
        "Material Wait": "idling_minor_stops",
        "NoOrders": "idling_minor_stops",
        "ReducedSpeed": "reduced_speed",
        "Reduced Speed": "reduced_speed",
        "Speed Loss": "reduced_speed",
        "PM": "setup_adjustment",
        "QualityHold": "process_defects",
        "Quality Hold": "process_defects",
    }

    categories = {
        "equipment_failure": 0.0,
        "setup_adjustment": 0.0,
        "idling_minor_stops": 0.0,
        "reduced_speed": 0.0,
        "process_defects": 0.0,
        "startup_losses": 0.0,
    }

    cur = conn.cursor()

    # 1-4: Availability & Performance losses from downtime_log
    cur.execute(
        """SELECT category, COALESCE(SUM(duration_min), 0) AS total_min
           FROM downtime_log
           WHERE wc_id = ?
           GROUP BY category""",
        (wc_id,),
    )

    for row in cur.fetchall():
        cat = row[0] or ""
        total = row[1]
        key = _DOWNTIME_MAP.get(cat)
        if key is None:
            # Fuzzy match
            key = cat.lower().replace(" ", "_").replace("&", "").replace("__", "_")
        if key in categories:
            categories[key] += total

    # 5-6: Quality losses from scrap_log
    _SCRAP_MAP = {
        "Startup": "startup_losses",
        "Startup_Scrap": "startup_losses",
        "Warmup": "startup_losses",
        "Changeover": "startup_losses",
    }

    scrap_rows = cur.execute(
        """SELECT cause_code, COALESCE(SUM(quantity_ft), 0) AS total_ft
           FROM scrap_log
           WHERE wc_id = ?
           GROUP BY cause_code""",
        (wc_id,),
    ).fetchall()

    for row in scrap_rows:
        cause = row[0] or ""
        ft = row[1]
        loss_key = _SCRAP_MAP.get(cause, "process_defects")
        # Convert feet to equivalent minutes using rough rate (500 ft/hr)
        equiv_min = ft / (500 / 60) if ft > 0 else 0
        categories[loss_key] += round(equiv_min, 1)

    return categories


# ---------------------------------------------------------------------------
# Shift report
# ---------------------------------------------------------------------------
def compute_shift_report(conn, wc_id, shift_code, shift_date):
    """Generate a full KPI report for one shift.

    Parameters
    ----------
    conn : sqlite3.Connection
    wc_id : str
    shift_code : str
        E.g. 'A', 'B', 'C'.
    shift_date : str
        ISO date (YYYY-MM-DD).

    Returns
    -------
    dict
        oee (dict), fpy (float), six_big_losses (dict),
        shift_code, shift_date, wc_id.
    """
    oee = compute_oee(conn, wc_id, shift_date)
    fpy = compute_fpy(conn, wc_id)
    losses = compute_six_big_losses(conn, wc_id)

    return {
        "wc_id": wc_id,
        "shift_code": shift_code,
        "shift_date": shift_date,
        "oee": oee,
        "fpy": fpy,
        "six_big_losses": losses,
    }
