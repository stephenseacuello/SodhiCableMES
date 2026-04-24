"""ISA-95 Level 3, MESA F6: Labor management.

SodhiCable MES — Labor Blueprint
Personnel, certification tracking, shift scheduling, labor hours, and handoffs.
"""
from flask import Blueprint, render_template, jsonify, request

bp = Blueprint("labor", __name__)


@bp.route("/labor")
def labor_page():
    return render_template("labor.html")


@bp.route("/api/labor/personnel")
def personnel_list():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT p.*, GROUP_CONCAT(pc.certification_type, ', ') AS certifications
        FROM personnel p
        LEFT JOIN personnel_certs pc ON p.person_id = pc.person_id
        GROUP BY p.person_id
        ORDER BY p.person_id
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/labor/certs_expiring")
def certs_expiring():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT pc.*, p.employee_name
        FROM personnel_certs pc
        JOIN personnel p ON pc.person_id = p.person_id
        WHERE pc.expiry_date <= DATE('now', '+30 days')
        ORDER BY pc.expiry_date ASC
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/labor/cert_matrix")
def cert_matrix():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT pc.cert_id, pc.person_id, p.employee_name, p.role, p.shift,
               pc.wc_id, pc.certification_type, pc.cert_level,
               pc.issued_date, pc.expiry_date, pc.status,
               CAST(julianday(pc.expiry_date) - julianday('now') AS INTEGER) AS days_until_expiry
        FROM personnel_certs pc
        JOIN personnel p ON pc.person_id = p.person_id
        WHERE p.active = 1
        ORDER BY p.employee_name, pc.wc_id
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/labor/schedule")
def labor_schedule():
    from db import get_db
    db = get_db()
    date_param = request.args.get("date")
    if date_param:
        rows = db.execute("""
            SELECT ss.*, p.employee_name, p.role
            FROM shift_schedule ss
            JOIN personnel p ON ss.person_id = p.person_id
            WHERE ss.shift_date = ?
            ORDER BY ss.wc_id, p.employee_name
        """, (date_param,)).fetchall()
    else:
        # Return all schedule entries (or today if available)
        rows = db.execute("""
            SELECT ss.*, p.employee_name, p.role
            FROM shift_schedule ss
            JOIN personnel p ON ss.person_id = p.person_id
            ORDER BY ss.shift_date DESC, ss.wc_id, p.employee_name
        """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/labor/hours")
def labor_hours():
    from db import get_db
    db = get_db()
    # Aggregate labor_time by labor_type
    summary_rows = db.execute("""
        SELECT labor_type,
               ROUND(SUM(hours), 1) AS total_hours,
               COUNT(*) AS entry_count
        FROM labor_time
        GROUP BY labor_type
        ORDER BY total_hours DESC
    """).fetchall()
    summary = [dict(r) for r in summary_rows]

    # Compute efficiency = earned_hrs / actual_hrs
    eff_row = db.execute("""
        SELECT ROUND(SUM(CASE WHEN labor_type IN ('Run','Setup') THEN hours ELSE 0 END), 1) AS total_earned,
               ROUND(SUM(hours), 1) AS total_actual
        FROM labor_time
    """).fetchone()
    efficiency = None
    if eff_row:
        earned = eff_row["total_earned"] or 0
        actual = eff_row["total_actual"] or 0
        if actual > 0:
            efficiency = round(earned / actual, 4)

    return jsonify({"summary": summary, "efficiency": efficiency})


@bp.route("/api/labor/handoffs")
def labor_handoffs():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM shift_handoff
        ORDER BY handoff_date DESC, from_shift
        LIMIT 20
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/labor/handoff/create", methods=["POST"])
def handoff_create():
    """Create a new shift handoff record."""
    from db import get_db
    from utils.audit import log_audit
    db = get_db()
    data = request.get_json(force=True)
    db.execute(
        """INSERT INTO shift_handoff
           (from_shift, to_shift, handoff_date, from_operator, to_operator,
            machines_running, wos_in_progress, quality_issues, safety_alerts, notes, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')""",
        (data.get("from_shift"), data.get("to_shift"), data.get("handoff_date"),
         data.get("from_operator"), data.get("to_operator"), data.get("machines_running"),
         data.get("wos_in_progress"), data.get("quality_issues"), data.get("safety_alerts"),
         data.get("notes")),
    )
    db.commit()
    handoff_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_audit(db, "shift_handoff", handoff_id, "status", None, "Pending")
    db.commit()
    return jsonify({"ok": True, "handoff_id": handoff_id})


@bp.route("/api/labor/handoff/acknowledge", methods=["POST"])
def handoff_acknowledge():
    """Acknowledge receipt of a shift handoff."""
    from db import get_db
    from utils.audit import log_audit
    db = get_db()
    data = request.get_json(force=True)
    handoff_id = data["handoff_id"]
    db.execute("UPDATE shift_handoff SET status = 'Acknowledged' WHERE handoff_id = ?", (handoff_id,))
    log_audit(db, "shift_handoff", handoff_id, "status", "Pending", "Acknowledged")
    db.commit()
    return jsonify({"ok": True})


@bp.route("/api/labor/roster/what_if", methods=["POST"])
def roster_what_if():
    """Labor rostering what-if analysis.

    Scenarios:
    - callout: N operators unavailable → show coverage gaps
    - cross_train: Add certs to N operators → show capacity gained
    - overtime: Calculate overtime cost for coverage
    """
    from db import get_db
    db = get_db()
    data = request.get_json(force=True)
    scenario = data.get("scenario", "callout")
    shift = data.get("shift", "Day")

    # Current state
    total = db.execute(
        "SELECT COUNT(*) AS c FROM personnel WHERE active=1 AND shift=?", (shift,)
    ).fetchone()["c"]
    wc_coverage = db.execute("""
        SELECT pc.wc_id, COUNT(DISTINCT pc.person_id) AS certified_count
        FROM personnel_certs pc
        JOIN personnel p ON p.person_id = pc.person_id
        WHERE p.active = 1 AND p.shift = ? AND pc.status = 'Active'
        GROUP BY pc.wc_id ORDER BY certified_count ASC
    """, (shift,)).fetchall()
    coverage = [dict(r) for r in wc_coverage]

    if scenario == "callout":
        n_callouts = int(data.get("count", 3))
        # Identify the most impactful callouts (WCs with fewest certified operators)
        gaps = []
        for wc in coverage:
            remaining = max(0, wc["certified_count"] - n_callouts)
            gap = "CRITICAL" if remaining == 0 else "AT RISK" if remaining == 1 else "OK"
            gaps.append({
                "wc_id": wc["wc_id"],
                "current_certified": wc["certified_count"],
                "after_callout": remaining,
                "status": gap,
            })
        critical = sum(1 for g in gaps if g["status"] == "CRITICAL")
        at_risk = sum(1 for g in gaps if g["status"] == "AT RISK")
        return jsonify({
            "scenario": "callout",
            "shift": shift,
            "total_operators": total,
            "callouts": n_callouts,
            "remaining": total - n_callouts,
            "wc_impact": gaps,
            "critical_wcs": critical,
            "at_risk_wcs": at_risk,
            "recommendation": f"Cross-train {critical + at_risk} operators on single-certified WCs to build resilience"
                              if critical > 0 else "Coverage adequate for this scenario",
        })

    elif scenario == "cross_train":
        target_wc = data.get("wc_id", "DRAW-1")
        n_trainees = int(data.get("count", 5))
        current = next((w for w in coverage if w["wc_id"] == target_wc), None)
        current_count = current["certified_count"] if current else 0
        return jsonify({
            "scenario": "cross_train",
            "target_wc": target_wc,
            "current_certified": current_count,
            "after_training": current_count + n_trainees,
            "shifts_covered": min(3, (current_count + n_trainees) // 2),
            "training_hours_est": n_trainees * 40,
            "training_cost_est": n_trainees * 40 * 35,
            "recommendation": f"Training {n_trainees} on {target_wc} increases coverage from {current_count} to {current_count + n_trainees} operators",
        })

    elif scenario == "overtime":
        # Calculate overtime needed to cover gaps
        base_rate = 35.0  # $/hr
        ot_rate = base_rate * 1.5
        gaps_needing_ot = [w for w in coverage if w["certified_count"] <= 2]
        ot_hours = len(gaps_needing_ot) * 8  # 8 hrs per uncovered WC per day
        return jsonify({
            "scenario": "overtime",
            "shift": shift,
            "wcs_needing_coverage": len(gaps_needing_ot),
            "overtime_hours_per_day": ot_hours,
            "daily_ot_cost": round(ot_hours * ot_rate, 2),
            "weekly_ot_cost": round(ot_hours * ot_rate * 5, 2),
            "vs_hiring_annual": round(base_rate * 2080 * len(gaps_needing_ot), 2),
            "recommendation": f"${round(ot_hours * ot_rate * 260, 0):,.0f}/yr overtime vs ${round(base_rate * 2080 * len(gaps_needing_ot), 0):,.0f}/yr for {len(gaps_needing_ot)} new hires",
        })

    elif scenario == "fatigue":
        # Night shift fatigue analysis
        # Operators on Night shift for consecutive days have degraded performance
        night_ops = db.execute("""
            SELECT ss.person_id, p.employee_name, COUNT(*) AS consecutive_nights
            FROM shift_schedule ss
            JOIN personnel p ON p.person_id = ss.person_id
            WHERE ss.shift = 'Night'
              AND ss.shift_date >= DATE('now', '-7 days')
            GROUP BY ss.person_id
            ORDER BY consecutive_nights DESC
        """).fetchall()

        fatigued = []
        for op in night_ops:
            nights = op["consecutive_nights"]
            # 5% performance degradation per consecutive night (research-backed)
            degradation_pct = min(25, nights * 5)
            effective_quality = round(100 - degradation_pct, 1)
            risk = "HIGH" if effective_quality < 80 else "MODERATE" if effective_quality < 90 else "LOW"
            fatigued.append({
                "person_id": op["person_id"],
                "employee_name": op["employee_name"],
                "consecutive_nights": nights,
                "degradation_pct": degradation_pct,
                "effective_quality_pct": effective_quality,
                "risk_level": risk,
            })

        high_risk = sum(1 for f in fatigued if f["risk_level"] == "HIGH")
        return jsonify({
            "scenario": "fatigue",
            "shift": "Night",
            "total_night_operators": len(fatigued),
            "high_risk_count": high_risk,
            "moderate_risk_count": sum(1 for f in fatigued if f["risk_level"] == "MODERATE"),
            "operators": fatigued,
            "recommendation": f"Rotate {high_risk} high-fatigue operators to Day/Swing shift. "
                             f"Night shift quality typically degrades 5% per consecutive night (Folkard & Tucker, 2003)."
                             if high_risk > 0 else "Fatigue levels acceptable for current rotation.",
        })

    elif scenario == "training_pipeline":
        # Identify WCs with insufficient certified operators and plan training
        training_hours = {
            'Extrusion': 120, 'Drawing': 80, 'Braiding': 60, 'Cabling': 80,
            'Testing': 40, 'Cutting': 30, 'Compounding': 100, 'Armoring': 70,
            'Jacketing': 100, 'Default': 60,
        }
        stages = ['Trainee (0-40hrs)', 'Provisional (40-80hrs)', 'Qualified (80+hrs)', 'Trainer (160+hrs)']

        # Find WCs with < 3 certified operators
        gap_wcs = db.execute("""
            SELECT pc.wc_id, wc.name AS wc_name, wc.wc_type,
                   COUNT(DISTINCT pc.person_id) AS certified_count
            FROM personnel_certs pc
            JOIN work_centers wc ON wc.wc_id = pc.wc_id
            WHERE pc.status = 'Active'
            GROUP BY pc.wc_id
            HAVING certified_count < 3
            ORDER BY certified_count ASC
        """).fetchall()

        pipeline = []
        total_hours = 0
        total_cost = 0
        for wc in gap_wcs:
            trainees_needed = 3 - wc["certified_count"]
            wc_type = wc["wc_type"] or "Default"
            hrs = training_hours.get(wc_type, training_hours["Default"])
            cost = trainees_needed * hrs * 35  # $35/hr loaded cost
            total_hours += trainees_needed * hrs
            total_cost += cost
            pipeline.append({
                "wc_id": wc["wc_id"],
                "wc_name": wc["wc_name"],
                "current_certified": wc["certified_count"],
                "trainees_needed": trainees_needed,
                "hours_per_trainee": hrs,
                "total_training_hours": trainees_needed * hrs,
                "cost_estimate": cost,
                "stages": stages,
                "weeks_to_qualified": round(hrs / 40, 1),
            })

        return jsonify({
            "scenario": "training_pipeline",
            "gap_wcs": len(pipeline),
            "total_trainees_needed": sum(p["trainees_needed"] for p in pipeline),
            "total_training_hours": total_hours,
            "total_cost_estimate": total_cost,
            "time_to_full_coverage_weeks": round(max((p["weeks_to_qualified"] for p in pipeline), default=0), 1),
            "pipeline": pipeline,
            "stages": stages,
            "recommendation": f"Train {sum(p['trainees_needed'] for p in pipeline)} operators across {len(pipeline)} work centers. "
                             f"Estimated {total_hours} hours, ${total_cost:,.0f}. "
                             f"Staged progression: Trainee → Provisional → Qualified → Trainer.",
        })

    return jsonify({"error": f"Unknown scenario: {scenario}"}), 400


@bp.route("/api/labor/handoff/auto_populate", methods=["POST"])
def handoff_auto_populate():
    """Auto-populate shift handoff with current WO/equipment/quality state."""
    from db import get_db
    import json
    db = get_db()
    data = request.get_json(force=True)
    from_shift = data.get("from_shift", "Day")

    # Machines currently running (equipment with status = Active that has recent downtime_log)
    machines = db.execute("""
        SELECT e.equipment_code, e.work_center_id, e.status
        FROM equipment e
        WHERE e.status = 'Active'
        ORDER BY e.work_center_id
    """).fetchall()
    machines_running = [{"code": m["equipment_code"], "wc": m["work_center_id"]} for m in machines[:20]]

    # WOs currently in progress
    wos = db.execute("""
        SELECT wo.wo_id, wo.product_id, wo.status, wo.order_qty_kft
        FROM work_orders wo
        WHERE wo.status = 'InProcess'
        ORDER BY wo.wo_id
    """).fetchall()
    wos_in_progress = [{"wo_id": w["wo_id"], "product": w["product_id"], "qty_kft": w["order_qty_kft"]} for w in wos]

    # Open quality issues
    quality_issues = []
    ncrs = db.execute("SELECT ncr_id, severity, description FROM ncr WHERE status != 'Closed' ORDER BY reported_date DESC LIMIT 5").fetchall()
    for n in ncrs:
        quality_issues.append(f"NCR-{n['ncr_id']} ({n['severity']}): {n['description'][:80]}")

    holds = db.execute("SELECT wo_id, hold_reason FROM hold_release WHERE hold_status = 'Active' LIMIT 5").fetchall()
    for h in holds:
        quality_issues.append(f"HOLD on {h['wo_id']}: {h['hold_reason']}")

    # Safety alerts
    safety_alerts = []
    deviations = db.execute(
        "SELECT wc_id, parameter_name, severity FROM process_deviations WHERE resolved = 0 AND severity IN ('Critical','Major') LIMIT 5"
    ).fetchall()
    for d in deviations:
        safety_alerts.append(f"{d['severity']} deviation at {d['wc_id']}/{d['parameter_name']}")

    return jsonify({
        "from_shift": from_shift,
        "machines_running": json.dumps(machines_running),
        "wos_in_progress": json.dumps(wos_in_progress),
        "quality_issues": "\n".join(quality_issues) if quality_issues else "No open quality issues",
        "safety_alerts": "\n".join(safety_alerts) if safety_alerts else "No active safety alerts",
    })
