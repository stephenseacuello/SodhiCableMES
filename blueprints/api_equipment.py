"""ISA-95 Level 2: Equipment monitoring, predictive maintenance.

SodhiCable MES — Equipment Blueprint
Equipment status, maintenance history, and MTBF calculations.
Filterable by work center and date range.
"""
from flask import Blueprint, render_template, jsonify, request

bp = Blueprint("equipment", __name__)


@bp.route("/equipment")
def equipment_page():
    return render_template("equipment.html")


@bp.route("/api/equipment/status")
def equipment_status():
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    query = """
        SELECT e.*, ms.next_due, ms.frequency_days, ms.last_performed, ms.pm_type
        FROM equipment e
        LEFT JOIN maintenance_schedule ms ON e.equipment_id = ms.equipment_id
        WHERE 1=1
    """
    params = []
    if wc:
        query += " AND e.work_center_id = ?"
        params.append(wc)
    query += " ORDER BY e.work_center_id, e.equipment_code"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/equipment/maintenance_history")
def maintenance_history():
    """Return maintenance records filterable by WC and date range."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    query = """
        SELECT m.maint_id, m.equipment_id, e.equipment_code, e.description,
               e.work_center_id, m.maint_type, m.scheduled_date, m.completed_date,
               m.duration_hours, m.technician, m.result, m.status
        FROM maintenance m
        JOIN equipment e ON e.equipment_id = m.equipment_id
        WHERE 1=1
    """
    params = []
    if wc:
        query += " AND e.work_center_id = ?"
        params.append(wc)
    if date_from:
        query += " AND m.completed_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND m.completed_date <= ?"
        params.append(date_to + " 23:59:59")
    query += " ORDER BY m.completed_date DESC LIMIT 200"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/equipment/downtime")
def equipment_downtime():
    """Return downtime records filterable by WC and date range."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    query = """
        SELECT dl.log_id, dl.wc_id, dl.equipment_id, dl.start_time, dl.end_time,
               dl.duration_min, dl.category, dl.cause, dl.notes
        FROM downtime_log dl
        WHERE 1=1
    """
    params = []
    if wc:
        query += " AND dl.wc_id = ?"
        params.append(wc)
    if date_from:
        query += " AND dl.start_time >= ?"
        params.append(date_from)
    if date_to:
        query += " AND dl.start_time <= ?"
        params.append(date_to + " 23:59:59")
    query += " ORDER BY dl.start_time DESC LIMIT 200"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/equipment/work_centers")
def equipment_work_centers():
    """Return work centers that have equipment."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT DISTINCT e.work_center_id, wc.name
        FROM equipment e
        JOIN work_centers wc ON wc.wc_id = e.work_center_id
        ORDER BY e.work_center_id
    """).fetchall()
    return jsonify([{"wc_id": r["work_center_id"], "name": r["name"]} for r in rows])


@bp.route("/api/equipment/complete_pm", methods=["POST"])
def complete_pm():
    """Complete a preventive maintenance action on equipment.

    Updates: equipment.last_pm_date, equipment.next_pm_date,
    maintenance_schedule.last_performed, maintenance_schedule.next_due,
    inserts maintenance record, logs downtime as PM category, audit trail.
    This resets the CDF failure clock for the equipment.
    """
    from db import get_db
    from utils.audit import log_audit
    from datetime import datetime, timedelta
    db = get_db()
    data = request.get_json(force=True)

    equipment_id = data.get("equipment_id")
    if not equipment_id:
        return jsonify({"error": "equipment_id required"}), 400

    duration_min = data.get("duration_min", 60)
    technician = data.get("technician", "Maintenance Tech")
    notes = data.get("notes", "")
    pm_type = data.get("pm_type", "Preventive")

    # Get equipment info
    eq = db.execute("SELECT * FROM equipment WHERE equipment_id = ?", (equipment_id,)).fetchone()
    if not eq:
        return jsonify({"error": f"Equipment {equipment_id} not found"}), 404

    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    today_str = now.strftime("%Y-%m-%d")

    # Get PM frequency from maintenance_schedule
    sched = db.execute(
        "SELECT schedule_id, frequency_days FROM maintenance_schedule WHERE equipment_id = ? ORDER BY frequency_days ASC LIMIT 1",
        (equipment_id,)
    ).fetchone()
    freq_days = sched["frequency_days"] if sched else 30
    next_pm = (now + timedelta(days=freq_days)).strftime("%Y-%m-%d")

    # 1. Update equipment dates
    db.execute(
        "UPDATE equipment SET last_pm_date = ?, next_pm_date = ? WHERE equipment_id = ?",
        (today_str, next_pm, equipment_id))

    # 2. Update maintenance_schedule
    if sched:
        db.execute(
            "UPDATE maintenance_schedule SET last_performed = ?, next_due = ? WHERE schedule_id = ?",
            (today_str, next_pm, sched["schedule_id"]))

    # 3. Insert maintenance record
    db.execute(
        """INSERT INTO maintenance (equipment_id, wc_id, maint_type, scheduled_date, completed_date,
           duration_hours, technician, result, status, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'Pass', 'Complete', ?)""",
        (equipment_id, eq["work_center_id"], pm_type, today_str, now_str,
         round(duration_min / 60, 2), technician, notes))

    # 4. Log downtime as PM category
    end_time = (now + timedelta(minutes=duration_min)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """INSERT INTO downtime_log (wc_id, equipment_id, start_time, end_time, duration_min, category, cause, notes)
           VALUES (?, ?, ?, ?, ?, 'PM', 'Scheduled preventive maintenance', ?)""",
        (eq["work_center_id"], equipment_id, now_str, end_time, duration_min, notes))

    # 5. Audit trail
    log_audit(db, "equipment", equipment_id, "last_pm_date", eq["last_pm_date"], today_str, technician)
    db.commit()

    return jsonify({
        "ok": True,
        "equipment_id": equipment_id,
        "equipment_code": eq["equipment_code"],
        "work_center_id": eq["work_center_id"],
        "previous_pm": eq["last_pm_date"],
        "new_pm_date": today_str,
        "next_pm_due": next_pm,
        "frequency_days": freq_days,
        "duration_min": duration_min,
        "message": f"PM completed on {eq['equipment_code']}. CDF clock reset. Next PM due {next_pm}.",
    })


@bp.route("/api/equipment/mtbf/<equipment_id>")
def equipment_mtbf(equipment_id):
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT start_time, end_time, duration_min
        FROM downtime_log
        WHERE equipment_id = ?
        ORDER BY start_time
    """, (equipment_id,)).fetchall()

    events = [dict(r) for r in rows]
    if len(events) < 2:
        return jsonify({"equipment_id": equipment_id, "mtbf_hours": None,
                         "note": "Insufficient downtime events"})

    total_downtime_min = sum(e.get("duration_min", 0) or 0 for e in events)
    # Estimate operating time between first and last event
    first = events[0].get("start_time", "")
    last = events[-1].get("start_time", "")

    mtbf_hours = None
    if total_downtime_min and len(events) > 1:
        # Simple MTBF = total operating hours / number of failures
        # Approximate: assume 24/7 operation between first and last event
        try:
            from datetime import datetime
            t0 = datetime.fromisoformat(first)
            t1 = datetime.fromisoformat(last)
            span_hours = (t1 - t0).total_seconds() / 3600
            operating_hours = span_hours - total_downtime_min / 60
            mtbf_hours = round(operating_hours / len(events), 2)
        except Exception:
            mtbf_hours = None

    return jsonify({
        "equipment_id": equipment_id,
        "failure_count": len(events),
        "total_downtime_min": total_downtime_min,
        "mtbf_hours": mtbf_hours,
    })
