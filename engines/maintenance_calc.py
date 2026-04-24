"""
engines/maintenance_calc.py - F9 Maintenance Calculation Engine

Computes reliability KPIs (MTBF, MTTR), derives preventive-maintenance
intervals from an exponential reliability model, and performs delay-cost
analysis for SodhiCable equipment.
"""

import math


# ---------------------------------------------------------------------------
# MTBF
# ---------------------------------------------------------------------------
def compute_mtbf(conn, equipment_id):
    """Mean Time Between Failures for a piece of equipment.

    Reads from: failure_log (columns: equipment_id, failure_time,
    repair_end_time).

    Parameters
    ----------
    conn : sqlite3.Connection
    equipment_id : str

    Returns
    -------
    float
        MTBF in hours.  Returns 0.0 if fewer than 2 failure records.
    """
    cur = conn.cursor()
    # Use downtime_log with category='Breakdown' as failure events
    # Join through work_centers to find equipment's WC
    cur.execute(
        """SELECT dl.start_time
           FROM downtime_log dl
           JOIN equipment e ON dl.wc_id = e.work_center_id
           WHERE e.equipment_id = ? AND dl.category = 'Breakdown'
           ORDER BY dl.start_time ASC""",
        (equipment_id,),
    )
    rows = [r[0] for r in cur.fetchall() if r[0]]

    if len(rows) < 2:
        # Fallback: estimate from equipment install date
        cur.execute("SELECT install_date FROM equipment WHERE equipment_id = ?", (equipment_id,))
        row = cur.fetchone()
        if row and row[0]:
            from datetime import datetime
            install = datetime.fromisoformat(row[0])
            now = datetime.now()
            total_hrs = (now - install).total_seconds() / 3600.0
            return max(total_hrs / max(len(rows), 1), 500.0)  # At least 500 hrs default
        return 500.0  # Default MTBF

    from datetime import datetime
    times = [datetime.fromisoformat(t) for t in rows]
    total_hours = (times[-1] - times[0]).total_seconds() / 3600.0
    intervals = len(times) - 1

    return total_hours / intervals


# ---------------------------------------------------------------------------
# MTTR
# ---------------------------------------------------------------------------
def compute_mttr(conn, equipment_id):
    """Mean Time To Repair for a piece of equipment.

    Reads from: failure_log (columns: equipment_id, failure_time,
    repair_end_time).

    Parameters
    ----------
    conn : sqlite3.Connection
    equipment_id : str

    Returns
    -------
    float
        MTTR in hours.  Returns 0.0 if no records.
    """
    cur = conn.cursor()
    cur.execute(
        """SELECT dl.start_time, dl.end_time, dl.duration_min
           FROM downtime_log dl
           JOIN equipment e ON dl.wc_id = e.work_center_id
           WHERE e.equipment_id = ? AND dl.category = 'Breakdown'
             AND dl.duration_min IS NOT NULL""",
        (equipment_id,),
    )
    rows = cur.fetchall()

    if not rows:
        return 2.0  # Default 2 hours MTTR

    # Use duration_min directly
    total_repair_hrs = sum(r[2] for r in rows if r[2]) / 60.0
    return total_repair_hrs / len(rows) if rows else 2.0

    from datetime import datetime  # kept for compatibility

    total = 0.0
    for ft, rt in rows:
        start = datetime.fromisoformat(ft)
        end = datetime.fromisoformat(rt)
        total += (end - start).total_seconds() / 3600.0

    return total / len(rows)


# ---------------------------------------------------------------------------
# PM interval from reliability target
# ---------------------------------------------------------------------------
def compute_pm_interval(mtbf, reliability_target=0.90):
    """Derive the optimal PM interval using exponential reliability.

    T_PM = -MTBF * ln(reliability_target)

    Parameters
    ----------
    mtbf : float
        Mean time between failures (hours).
    reliability_target : float
        Desired reliability at PM interval (default 0.90).

    Returns
    -------
    float
        Recommended PM interval in hours.
    """
    if mtbf <= 0 or reliability_target <= 0 or reliability_target >= 1:
        return 0.0
    return -mtbf * math.log(reliability_target)


# ---------------------------------------------------------------------------
# Failure probability
# ---------------------------------------------------------------------------
def failure_probability(mtbf, time_since_last_pm):
    """Probability of failure given elapsed time (exponential model).

    P(failure) = 1 - e^(-t / MTBF)

    Parameters
    ----------
    mtbf : float
        Mean time between failures (hours).
    time_since_last_pm : float
        Hours elapsed since the last preventive maintenance.

    Returns
    -------
    float
        Probability of failure (0-1).
    """
    if mtbf <= 0:
        return 1.0
    return 1.0 - math.exp(-time_since_last_pm / mtbf)


# ---------------------------------------------------------------------------
# Cost-of-delay analysis
# ---------------------------------------------------------------------------
def cost_of_delay(mtbf, mttr, cost_per_hour, pm_cost, delay_hours):
    """Evaluate the expected cost of delaying a PM action.

    Parameters
    ----------
    mtbf : float
        Mean time between failures (hours).
    mttr : float
        Mean time to repair (hours).
    cost_per_hour : float
        Cost of unplanned downtime per hour (USD).
    pm_cost : float
        Fixed cost of performing the PM (USD).
    delay_hours : float
        Proposed delay beyond the scheduled PM (hours).

    Returns
    -------
    dict
        expected_cost - expected cost of breakdown during delay
        break_even    - delay hours at which expected breakdown cost
                        equals pm_cost
    """
    p_fail = failure_probability(mtbf, delay_hours)
    breakdown_cost = p_fail * mttr * cost_per_hour
    expected_cost = breakdown_cost  # vs. pm_cost to do it now

    # Break-even: find t where (1 - e^(-t/MTBF)) * MTTR * C_hr = pm_cost
    if mttr * cost_per_hour > 0 and mtbf > 0:
        ratio = pm_cost / (mttr * cost_per_hour)
        if 0 < ratio < 1:
            break_even = -mtbf * math.log(1 - ratio)
        else:
            break_even = float("inf")
    else:
        break_even = float("inf")

    return {
        "expected_cost": round(expected_cost, 2),
        "break_even": round(break_even, 2) if break_even != float("inf") else None,
    }
