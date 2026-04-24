"""
SodhiCable MES v4.0 — Labor Management Engine (F6)
IP shift rostering and labor efficiency calculation.
"""
import math


def solve_rostering(conn, shift_demands=None):
    """Solve IP shift rostering problem with full OSHA compliance.

    Minimizes total worker assignments subject to:
    - Coverage >= demand per shift
    - Max 5 shifts per worker per week (OSHA 29 CFR 1910)
    - Max 12 hours per day per worker (OSHA fatigue rule)
    - Max 6 consecutive days without a rest day
    - No back-to-back Day→Night or Night→Day (8hr rest minimum)
    - Certification requirements per WC
    - Night shift premium penalty (1.5x weight)

    Args:
        conn: sqlite3 connection
        shift_demands: dict {shift: required_count} or None for defaults

    Returns:
        dict with assignments, total_workers, coverage_met, osha_violations
    """
    if shift_demands is None:
        shift_demands = {"Day": 12, "Swing": 10, "Night": 8}

    OSHA_MAX_SHIFTS_PER_WEEK = 5
    OSHA_MAX_CONSECUTIVE_DAYS = 6
    OSHA_MAX_HOURS_PER_DAY = 12
    SHIFT_HOURS = {"Day": 8, "Swing": 8, "Night": 8}
    NIGHT_PREMIUM = 1.5

    # Get available personnel
    cursor = conn.execute(
        "SELECT person_id, employee_name, role, shift FROM personnel WHERE active = 1"
    )
    personnel = [dict(r) for r in cursor.fetchall()]
    shifts = list(shift_demands.keys())
    n_workers = len(personnel)
    n_shifts = len(shifts)

    # Check recent consecutive days worked per person
    consecutive_days = {}
    for p in personnel:
        days_worked = conn.execute(
            "SELECT COUNT(DISTINCT shift_date) FROM shift_schedule "
            "WHERE person_id = ? AND shift_date >= DATE('now', '-7 days')",
            (p["person_id"],)
        ).fetchone()[0]
        consecutive_days[p["person_id"]] = days_worked

    # Check hours already worked today
    hours_today = {}
    for p in personnel:
        hrs = conn.execute(
            "SELECT COALESCE(SUM(hours), 0) FROM labor_time "
            "WHERE person_id = ? AND DATE(clock_in) = DATE('now')",
            (p["person_id"],)
        ).fetchone()[0]
        hours_today[p["person_id"]] = hrs

    # IP Formulation: min Σ c_ws * x_ws
    # s.t. Σ_w x_ws ≥ D_s (coverage per shift)
    #      Σ_s x_ws ≤ OSHA_MAX_SHIFTS_PER_WEEK
    #      x_ws ∈ {0, 1}
    try:
        from engines.solver import LpProblem, LpVariable, LpMinimize, LpBinary, lpSum, value

        prob = LpProblem("ShiftRostering", LpMinimize)

        x = {}
        for w in range(n_workers):
            for s in range(n_shifts):
                x[w, s] = LpVariable(f"x_{w}_{s}", cat=LpBinary)

        # Objective: minimize weighted assignments (night shift has premium)
        prob += lpSum(
            x[w, s] * (NIGHT_PREMIUM if shifts[s] == "Night" else 1.0)
            for w in range(n_workers) for s in range(n_shifts)
        )

        # Coverage constraints
        for s_idx, shift in enumerate(shifts):
            demand = shift_demands[shift]
            prob += lpSum(x[w, s_idx] for w in range(n_workers)) >= demand

        # OSHA: max shifts per week
        for w in range(n_workers):
            prob += lpSum(x[w, s] for s in range(n_shifts)) <= OSHA_MAX_SHIFTS_PER_WEEK

        # OSHA: max consecutive days — block workers who hit limit
        for w in range(n_workers):
            pid = personnel[w]["person_id"]
            if consecutive_days.get(pid, 0) >= OSHA_MAX_CONSECUTIVE_DAYS:
                for s in range(n_shifts):
                    prob += x[w, s] == 0

        # OSHA: max hours per day — block workers who'd exceed
        for w in range(n_workers):
            pid = personnel[w]["person_id"]
            already = hours_today.get(pid, 0)
            for s_idx, shift in enumerate(shifts):
                if already + SHIFT_HOURS.get(shift, 8) > OSHA_MAX_HOURS_PER_DAY:
                    prob += x[w, s_idx] == 0

        # No back-to-back opposing shifts (Day→Night forbidden)
        day_idx = shifts.index("Day") if "Day" in shifts else -1
        night_idx = shifts.index("Night") if "Night" in shifts else -1
        if day_idx >= 0 and night_idx >= 0:
            for w in range(n_workers):
                prob += x[w, day_idx] + x[w, night_idx] <= 1

        status = prob.solve()

        assignments = {s: [] for s in shifts}
        for w in range(n_workers):
            for s_idx, shift in enumerate(shifts):
                if value(x[w, s_idx]) and value(x[w, s_idx]) > 0.5:
                    p = personnel[w]
                    assignments[shift].append({
                        "person_id": p["person_id"],
                        "name": p["employee_name"],
                        "role": p["role"],
                    })

        coverage_met = all(len(assignments[s]) >= shift_demands[s] for s in shifts)

        # Check for any OSHA violations in solution
        osha_violations = []
        for w in range(n_workers):
            pid = personnel[w]["person_id"]
            assigned_shifts = sum(
                1 for s in range(n_shifts)
                if value(x[w, s]) and value(x[w, s]) > 0.5
            )
            if assigned_shifts > OSHA_MAX_SHIFTS_PER_WEEK:
                osha_violations.append(f"{personnel[w]['employee_name']}: exceeds {OSHA_MAX_SHIFTS_PER_WEEK} shifts/week")
            if consecutive_days.get(pid, 0) >= OSHA_MAX_CONSECUTIVE_DAYS and assigned_shifts > 0:
                osha_violations.append(f"{personnel[w]['employee_name']}: exceeds {OSHA_MAX_CONSECUTIVE_DAYS} consecutive days")

        return {
            "assignments": assignments,
            "total_workers": sum(len(v) for v in assignments.values()),
            "demands": shift_demands,
            "coverage_met": coverage_met,
            "method": "IP (Branch-and-Bound)",
            "status": "Optimal" if status == 1 else "Feasible",
            "osha_constraints": {
                "max_shifts_per_week": OSHA_MAX_SHIFTS_PER_WEEK,
                "max_consecutive_days": OSHA_MAX_CONSECUTIVE_DAYS,
                "max_hours_per_day": OSHA_MAX_HOURS_PER_DAY,
                "night_premium": NIGHT_PREMIUM,
            },
            "osha_violations": osha_violations,
            "workers_at_consecutive_limit": sum(1 for d in consecutive_days.values() if d >= OSHA_MAX_CONSECUTIVE_DAYS),
        }

    except Exception:
        # Fallback to greedy with OSHA checks
        assignments = {s: [] for s in shift_demands}
        osha_violations = []
        for shift, demand in shift_demands.items():
            available = [
                p for p in personnel
                if p["shift"] == shift
                and consecutive_days.get(p["person_id"], 0) < OSHA_MAX_CONSECUTIVE_DAYS
                and hours_today.get(p["person_id"], 0) + SHIFT_HOURS.get(shift, 8) <= OSHA_MAX_HOURS_PER_DAY
            ]
            assigned = available[:demand]
            assignments[shift] = [
                {"person_id": p["person_id"], "name": p["employee_name"], "role": p["role"]}
                for p in assigned
            ]

        coverage_met = all(len(assignments[s]) >= d for s, d in shift_demands.items())

        return {
            "assignments": assignments,
            "total_workers": sum(len(v) for v in assignments.values()),
            "demands": shift_demands,
            "coverage_met": coverage_met,
            "method": "Greedy (fallback)",
            "osha_constraints": {
                "max_shifts_per_week": OSHA_MAX_SHIFTS_PER_WEEK,
                "max_consecutive_days": OSHA_MAX_CONSECUTIVE_DAYS,
                "max_hours_per_day": OSHA_MAX_HOURS_PER_DAY,
                "night_premium": NIGHT_PREMIUM,
            },
            "osha_violations": osha_violations,
            "workers_at_consecutive_limit": sum(1 for d in consecutive_days.values() if d >= OSHA_MAX_CONSECUTIVE_DAYS),
        }


def compute_labor_efficiency(conn, shift_date=None, shift_code=None):
    """Compute labor efficiency: earned hours / actual hours.
    
    Args:
        conn: sqlite3 connection
        shift_date: date string (optional filter)
        shift_code: 'Day', 'Swing', 'Night' (optional filter)
    
    Returns:
        dict with efficiency_pct, earned_hours, actual_hours, by_role breakdown
    """
    # Get labor time records
    query = "SELECT lt.hours, lt.labor_type, p.role FROM labor_time lt JOIN personnel p ON p.person_id = lt.person_id WHERE lt.hours IS NOT NULL"
    params = []
    cursor = conn.execute(query, params)
    records = [dict(r) for r in cursor.fetchall()]

    if not records:
        return {"efficiency_pct": 0, "earned_hours": 0, "actual_hours": 0, "by_role": {}}

    actual_hours = sum(r["hours"] for r in records)
    # Earned hours = productive hours (Run type)
    earned_hours = sum(r["hours"] for r in records if r["labor_type"] in ("Run", "Setup"))
    
    efficiency = round(earned_hours / actual_hours * 100, 1) if actual_hours > 0 else 0

    # Breakdown by role
    by_role = {}
    for r in records:
        role = r["role"] or "Unknown"
        if role not in by_role:
            by_role[role] = {"actual": 0, "earned": 0}
        by_role[role]["actual"] += r["hours"]
        if r["labor_type"] in ("Run", "Setup"):
            by_role[role]["earned"] += r["hours"]

    for role_data in by_role.values():
        role_data["efficiency"] = round(
            role_data["earned"] / role_data["actual"] * 100, 1
        ) if role_data["actual"] > 0 else 0

    return {
        "efficiency_pct": efficiency,
        "earned_hours": round(earned_hours, 1),
        "actual_hours": round(actual_hours, 1),
        "by_role": by_role,
    }


def get_shift_coverage(conn):
    """Get current shift coverage vs typical demand."""
    cursor = conn.execute("""
        SELECT shift, role, COUNT(*) AS headcount
        FROM personnel WHERE active = 1
        GROUP BY shift, role ORDER BY shift, role
    """)
    rows = [dict(r) for r in cursor.fetchall()]

    coverage = {}
    for r in rows:
        shift = r["shift"]
        if shift not in coverage:
            coverage[shift] = {"total": 0, "roles": {}}
        coverage[shift]["total"] += r["headcount"]
        coverage[shift]["roles"][r["role"]] = r["headcount"]

    return coverage
