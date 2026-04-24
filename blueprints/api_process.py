"""ISA-95 Level 1-2: Process control, alarms, PID feedback.

SodhiCable MES — Process Control Blueprint (F8)
Process deviations, alarm management, PID simulation, hold/release, live process data.
Filterable by work center and date range.
"""
from flask import Blueprint, render_template, jsonify, request

bp = Blueprint("process", __name__)


@bp.route("/process")
def process_page():
    return render_template("process.html")


@bp.route("/api/process/deviations")
def deviations():
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    severity = request.args.get("severity", "")
    resolved = request.args.get("resolved", "")
    query = "SELECT * FROM process_deviations WHERE 1=1"
    params = []
    if wc:
        query += " AND wc_id = ?"
        params.append(wc)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if resolved in ("0", "1"):
        query += " AND resolved = ?"
        params.append(int(resolved))
    query += " ORDER BY timestamp DESC LIMIT 200"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/process/holds")
def holds():
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    query = """SELECT hr.*, wo.product_id FROM hold_release hr
               LEFT JOIN work_orders wo ON wo.wo_id = hr.wo_id
               WHERE 1=1"""
    params = []
    if wc:
        query += " AND hr.hold_reason LIKE ?"
        params.append(f"%{wc}%")
    query += " ORDER BY hr.held_date DESC LIMIT 100"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/process/live_readings")
def live_readings():
    """Return latest process readings per parameter for a work center."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    if not wc:
        return jsonify({"error": "wc_id required"}), 400
    rows = db.execute("""
        SELECT pdl.parameter,
               pdl.value, pdl.timestamp, pdl.quality_flag,
               (SELECT rp.parameter_value FROM recipe_parameters rp
                JOIN recipes r ON r.recipe_id = rp.recipe_id
                WHERE r.work_center_id = pdl.wc_id AND rp.parameter_name = pdl.parameter
                  AND r.status = 'Approved' LIMIT 1) AS setpoint,
               (SELECT rp.lower_limit FROM recipe_parameters rp
                JOIN recipes r ON r.recipe_id = rp.recipe_id
                WHERE r.work_center_id = pdl.wc_id AND rp.parameter_name = pdl.parameter
                  AND r.status = 'Approved' LIMIT 1) AS lower_limit,
               (SELECT rp.upper_limit FROM recipe_parameters rp
                JOIN recipes r ON r.recipe_id = rp.recipe_id
                WHERE r.work_center_id = pdl.wc_id AND rp.parameter_name = pdl.parameter
                  AND r.status = 'Approved' LIMIT 1) AS upper_limit
        FROM process_data_live pdl
        WHERE pdl.wc_id = ? AND pdl.reading_id IN (
            SELECT MAX(reading_id) FROM process_data_live WHERE wc_id = ? GROUP BY parameter
        )
        ORDER BY pdl.parameter
    """, (wc, wc)).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/process/trend")
def process_trend():
    """Return time-series for a specific parameter at a work center."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    param = request.args.get("parameter", "")
    if not wc or not param:
        return jsonify({"error": "wc_id and parameter required"}), 400
    rows = db.execute("""
        SELECT value, timestamp, quality_flag FROM process_data_live
        WHERE wc_id = ? AND parameter = ?
        ORDER BY timestamp DESC LIMIT 200
    """, (wc, param)).fetchall()
    return jsonify({"readings": [dict(r) for r in reversed(rows)]})


@bp.route("/api/process/summary")
def process_summary():
    """Return summary KPIs for process control."""
    from db import get_db
    db = get_db()
    unresolved = db.execute("SELECT COUNT(*) AS c FROM process_deviations WHERE resolved = 0").fetchone()["c"]
    critical = db.execute("SELECT COUNT(*) AS c FROM process_deviations WHERE resolved = 0 AND severity = 'Critical'").fetchone()["c"]
    active_holds = db.execute("SELECT COUNT(*) AS c FROM hold_release WHERE hold_status = 'Active'").fetchone()["c"]
    total_readings = db.execute("SELECT COUNT(*) AS c FROM process_data_live").fetchone()["c"]
    wcs_monitored = db.execute("SELECT COUNT(DISTINCT wc_id) AS c FROM process_data_live").fetchone()["c"]
    return jsonify({
        "unresolved_deviations": unresolved,
        "critical_alarms": critical,
        "active_holds": active_holds,
        "total_readings": total_readings,
        "wcs_monitored": wcs_monitored,
    })


@bp.route("/api/process/work_centers")
def process_work_centers():
    """Return work centers that have process data."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT DISTINCT pdl.wc_id, wc.name
        FROM process_data_live pdl
        JOIN work_centers wc ON wc.wc_id = pdl.wc_id
        ORDER BY pdl.wc_id
    """).fetchall()
    return jsonify([{"wc_id": r["wc_id"], "name": r["name"]} for r in rows])


@bp.route("/api/process/pid_simulate", methods=["POST"])
def pid_simulate():
    data = request.get_json(force=True)
    kp = data.get("kp", 1.0)
    ki = data.get("ki", 0.1)
    kd = data.get("kd", 0.05)
    setpoint = data.get("setpoint", 100)
    duration = data.get("duration", 60)

    try:
        from engines.pid_control import simulate_pid
        import random as _rng
        # Build disturbance sequence from request or generate random ones
        disturbances = data.get("disturbances", None)
        if disturbances is None:
            rng = _rng.Random(42)
            steps = min(int(duration), 200)
            disturbances = [rng.gauss(0, 0.5) for _ in range(steps)]
        result = simulate_pid(setpoint, disturbances, Kp=kp, Ki=ki, Kd=kd)
        return jsonify(result)
    except Exception:
        # Mock PID response
        import math
        steps = min(int(duration), 200)
        time_series = []
        pv = 0
        for t in range(steps):
            # Simple first-order approximation
            error = setpoint - pv
            pv += error * 0.1
            time_series.append({"t": t, "pv": round(pv, 2), "sp": setpoint})

        return jsonify({
            "note": "Engine not loaded – mock PID simulation",
            "kp": kp, "ki": ki, "kd": kd,
            "setpoint": setpoint,
            "time_series": time_series,
        })


@bp.route("/api/process/trigger_alarm", methods=["POST"])
def trigger_alarm():
    """Alarm rationalization chain: detect -> deviation -> optionally NCR -> hold -> quarantine"""
    from db import get_db
    db = get_db()
    data = request.get_json(force=True)
    severity = data.get("severity", "Warning")
    wc_id = data.get("wc_id", "")
    wo_id = data.get("wo_id", "")
    param = data.get("parameter", "")
    value = data.get("value", 0)
    setpoint = data.get("setpoint", 0)

    # Always create process deviation
    db.execute("INSERT INTO process_deviations (wo_id, wc_id, parameter_name, detection_method, deviation_value, setpoint_value, severity) VALUES (?,?,?,?,?,?,?)",
               (wo_id, wc_id, param, data.get("method", "Threshold"), value, setpoint, severity))

    actions = ["deviation_logged"]

    # Major/Critical -> auto-create NCR
    if severity in ("Major", "Critical"):
        db.execute("INSERT INTO ncr (wo_id, description, severity, detected_at, status) VALUES (?,?,?,?,'Open')",
                   (wo_id, f"Auto-NCR: {param} deviation ({value} vs {setpoint}) on {wc_id}", severity, wc_id))
        actions.append("ncr_created")

    # Critical -> auto-hold + lot quarantine
    if severity == "Critical":
        db.execute("INSERT INTO hold_release (wo_id, hold_reason, hold_status) VALUES (?,?,'Active')",
                   (wo_id, f"Critical alarm: {param} on {wc_id}"))
        actions.append("hold_placed")
        actions.append("lot_quarantined")

    db.commit()
    return jsonify({"ok": True, "severity": severity, "actions": actions})


@bp.route("/api/process/resolve_deviation", methods=["POST"])
def resolve_deviation():
    """Acknowledge or resolve a process deviation."""
    from db import get_db
    from utils.audit import log_audit
    db = get_db()
    data = request.get_json(force=True)
    dev_id = data["deviation_id"]
    action = data.get("action", "resolve")  # "acknowledge" or "resolve"
    corrective = data.get("corrective_action", "")

    if action == "resolve":
        db.execute("UPDATE process_deviations SET resolved = 1, corrective_action = ? WHERE deviation_id = ?",
                   (corrective, dev_id))
        log_audit(db, "process_deviations", dev_id, "resolved", "0", "1")
    else:
        db.execute("UPDATE process_deviations SET corrective_action = ? WHERE deviation_id = ?",
                   (corrective, dev_id))
        log_audit(db, "process_deviations", dev_id, "corrective_action", None, corrective)
    db.commit()
    return jsonify({"ok": True})


@bp.route("/api/process/alarm_cascade/<int:deviation_id>")
def alarm_cascade(deviation_id):
    """Show the alarm rationalization chain for a deviation."""
    from db import get_db
    db = get_db()
    dev = db.execute("SELECT * FROM process_deviations WHERE deviation_id = ?", (deviation_id,)).fetchone()
    if not dev:
        return jsonify({"error": "Deviation not found"}), 404
    d = dict(dev)

    chain = [{"step": "Deviation Detected", "detail": f"{d['parameter_name']} = {d['deviation_value']} (SP: {d['setpoint_value']})",
              "severity": d["severity"], "method": d["detection_method"]}]

    # Check if NCR was auto-created for this WO around the same time
    if d["severity"] in ("Major", "Critical") and d.get("wo_id"):
        ncr = db.execute("SELECT ncr_id, severity, status FROM ncr WHERE wo_id = ? AND detected_at = ? LIMIT 1",
                         (d["wo_id"], d["wc_id"])).fetchone()
        if ncr:
            chain.append({"step": "NCR Auto-Created", "detail": f"NCR-{ncr['ncr_id']} ({ncr['severity']})", "status": ncr["status"]})

    if d["severity"] == "Critical" and d.get("wo_id"):
        hold = db.execute("SELECT hold_id, hold_status, disposition FROM hold_release WHERE wo_id = ? LIMIT 1",
                          (d["wo_id"],)).fetchone()
        if hold:
            chain.append({"step": "Hold Placed", "detail": f"Hold #{hold['hold_id']}", "status": hold["hold_status"]})
            chain.append({"step": "Lot Quarantined", "detail": f"Disposition: {hold['disposition'] or 'Pending'}", "status": hold["hold_status"]})

    return jsonify({"deviation": d, "chain": chain})


@bp.route("/api/process/cusum_ewma")
def cusum_ewma():
    """Compute CUSUM and EWMA for a parameter at a work center."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    param = request.args.get("parameter", "")
    if not wc or not param:
        return jsonify({"error": "wc_id and parameter required"}), 400

    rows = db.execute("""
        SELECT value, timestamp FROM process_data_live
        WHERE wc_id = ? AND parameter = ?
        ORDER BY timestamp ASC LIMIT 200
    """, (wc, param)).fetchall()

    if len(rows) < 5:
        return jsonify({"cusum_plus": [], "cusum_minus": [], "ewma": [], "timestamps": []})

    values = [r["value"] for r in rows]
    timestamps = [r["timestamp"] for r in rows]

    import statistics
    mean = statistics.mean(values)
    sigma = statistics.stdev(values) if len(values) > 1 else 1

    # CUSUM (two-sided)
    k = 0.5 * sigma  # slack
    h = 5 * sigma     # threshold
    cp, cm = [0], [0]
    for v in values[1:]:
        cp.append(max(0, cp[-1] + (v - mean) - k))
        cm.append(max(0, cm[-1] - (v - mean) - k))

    # EWMA
    lam = 0.2
    ewma = [values[0]]
    for v in values[1:]:
        ewma.append(lam * v + (1 - lam) * ewma[-1])

    return jsonify({
        "timestamps": timestamps,
        "values": values,
        "cusum_plus": [round(v, 4) for v in cp],
        "cusum_minus": [round(v, 4) for v in cm],
        "cusum_h": round(h, 4),
        "ewma": [round(v, 4) for v in ewma],
        "mean": round(mean, 4),
        "sigma": round(sigma, 4),
    })


@bp.route("/api/process/alarm_timeline")
def alarm_timeline():
    """Return alarm events over the past 14 days for timeline visualization."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    query = """SELECT deviation_id, wc_id, parameter_name, severity, timestamp, resolved,
                      detection_method, deviation_value, setpoint_value
               FROM process_deviations
               WHERE timestamp >= DATE('now', '-14 days')"""
    params = []
    if wc:
        query += " AND wc_id = ?"
        params.append(wc)
    query += " ORDER BY timestamp ASC"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/process/rationalization_summary")
def rationalization_summary():
    """Alarm rationalization chain summary: deviations → NCRs → holds → quarantines."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    period = " AND timestamp >= DATE('now', '-7 days')" if not wc else ""

    base_filter = ""
    if wc:
        base_filter = f" AND wc_id = '{wc}'"

    devs = db.execute(f"SELECT COUNT(*) AS c FROM process_deviations WHERE 1=1{base_filter}{period}").fetchone()["c"]
    ncrs = db.execute(f"SELECT COUNT(*) AS c FROM ncr WHERE status != 'Cancelled'{' AND detected_at = ?' if wc else ''}{period.replace('timestamp','reported_date')}",
                      ([wc] if wc else [])).fetchone()["c"]
    holds = db.execute("SELECT COUNT(*) AS c FROM hold_release WHERE hold_status = 'Active'").fetchone()["c"]
    quarantined = holds  # in our model, hold = quarantine

    return jsonify({
        "period": "last 7 days" if not wc else f"{wc}",
        "deviations": devs,
        "auto_ncrs": ncrs,
        "holds_placed": holds,
        "lots_quarantined": quarantined,
        "chain": f"{devs} deviations → {ncrs} NCRs → {holds} holds → {quarantined} lots quarantined",
    })


@bp.route("/api/process/deviation_scrap/<int:deviation_id>")
def deviation_scrap(deviation_id):
    """Find scrap events near a deviation (within 30 minutes)."""
    from db import get_db
    db = get_db()
    dev = db.execute("SELECT wc_id, timestamp FROM process_deviations WHERE deviation_id = ?", (deviation_id,)).fetchone()
    if not dev:
        return jsonify({"error": "Deviation not found"}), 404

    scraps = db.execute("""
        SELECT scrap_id, wo_id, cause_code, quantity_ft, cost, disposition, timestamp
        FROM scrap_log
        WHERE wc_id = ? AND timestamp BETWEEN datetime(?, '-30 minutes') AND datetime(?, '+30 minutes')
        ORDER BY timestamp
    """, (dev["wc_id"], dev["timestamp"], dev["timestamp"])).fetchall()
    return jsonify({"deviation_id": deviation_id, "nearby_scrap": [dict(r) for r in scraps]})


@bp.route("/api/process/environmental")
def environmental():
    """Return environmental readings for a work center."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    if not wc:
        return jsonify([])
    rows = db.execute("""
        SELECT temperature_f, humidity_pct, timestamp, status
        FROM environmental_readings
        WHERE wc_id = ? ORDER BY timestamp DESC LIMIT 50
    """, (wc,)).fetchall()
    return jsonify([dict(r) for r in reversed(rows)])


# ── SSE Streaming: Live Process Data ─────────────────────────────

@bp.route("/api/stream/process_data")
def stream_process_data():
    """Server-Sent Events stream of live process data.

    Pushes latest sensor readings every 5 seconds. Clients connect via
    EventSource('/api/stream/process_data') and receive JSON events.
    """
    import time as _time
    import json as _json
    import sqlite3
    from flask import Response, stream_with_context
    from config import DATABASE

    wc_filter = request.args.get("wc_id", "")

    def generate():
        while True:
            try:
                db = sqlite3.connect(DATABASE)
                db.row_factory = sqlite3.Row
                try:
                    query = """
                        SELECT wc_id, parameter, value, timestamp, quality_flag
                        FROM process_data_live
                        WHERE timestamp >= DATETIME('now', '-30 seconds')
                    """
                    params = []
                    if wc_filter:
                        query += " AND wc_id = ?"
                        params.append(wc_filter)
                    query += " ORDER BY timestamp DESC LIMIT 50"
                    rows = db.execute(query, params).fetchall()
                    data = [dict(r) for r in rows]
                finally:
                    db.close()

                event_data = _json.dumps({
                    "type": "process_data",
                    "count": len(data),
                    "readings": data,
                    "server_time": _time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                yield f"data: {event_data}\n\n"
            except Exception as e:
                yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            _time.sleep(5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── SSE Streaming: Alarms ────────────────────────────────────────

@bp.route("/api/stream/alarms")
def stream_alarms():
    """SSE stream for real-time alarm notifications."""
    import time as _time
    import json as _json
    import sqlite3
    from flask import Response, stream_with_context
    from config import DATABASE

    def generate():
        while True:
            try:
                db = sqlite3.connect(DATABASE)
                db.row_factory = sqlite3.Row
                try:
                    alarms = db.execute("""
                        SELECT deviation_id, wc_id, parameter_name, severity,
                               deviation_value, setpoint_value, timestamp
                        FROM process_deviations
                        WHERE resolved = 0 AND severity IN ('Critical', 'Major')
                        ORDER BY timestamp DESC LIMIT 10
                    """).fetchall()
                finally:
                    db.close()

                event_data = _json.dumps({
                    "type": "alarms",
                    "count": len(alarms),
                    "alarms": [dict(r) for r in alarms],
                    "server_time": _time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                yield f"data: {event_data}\n\n"
            except Exception as e:
                yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            _time.sleep(10)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
