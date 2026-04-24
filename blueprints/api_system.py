"""ISA-95 Level 2: System metrics, OPC-UA control, health, audit, notifications.

SodhiCable MES — System Metrics Blueprint
"""
import os
from flask import Blueprint, render_template, jsonify, request, current_app

bp = Blueprint("system", __name__)

@bp.route("/system")
def system_page():
    return render_template("system.html")

@bp.route("/api/system/metrics")
def system_metrics():
    from db import get_db
    db = get_db()
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    table_stats = []
    total_rows = 0
    for t in tables:
        try:
            cnt = db.execute(f"SELECT COUNT(*) FROM [{t['name']}]").fetchone()[0]
            total_rows += cnt
            table_stats.append({"table": t["name"], "rows": cnt})
        except: pass
    table_stats.sort(key=lambda x: x["rows"], reverse=True)
    views = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view'").fetchone()[0]
    db_list = db.execute("PRAGMA database_list").fetchone()
    db_path = db_list[2] if db_list else ""
    db_size = os.path.getsize(db_path) if db_path and os.path.exists(db_path) else 0
    freshness = {}
    for tbl, col in [("process_data_live","timestamp"),("shift_reports","shift_date"),("audit_trail","changed_datetime"),("energy_readings","timestamp")]:
        try: freshness[tbl] = db.execute(f"SELECT MAX({col}) FROM {tbl}").fetchone()[0]
        except: freshness[tbl] = None
    endpoints = len(list(current_app.url_map.iter_rules()))
    return jsonify({"endpoints": endpoints, "tables": len(tables), "views": views, "total_rows": total_rows,
                    "db_size_mb": round(db_size/1048576, 2), "table_stats": table_stats[:25],
                    "freshness": freshness, "version": "4.0"})


# ── Health Check ──────────────────────────────────────────────────

@bp.route("/api/health")
def health_check():
    import time as _time
    from db import get_db
    start = _time.time()
    try:
        db = get_db()
        row = db.execute("SELECT COUNT(*) AS c FROM work_orders").fetchone()
        db_ok = True
        wo_count = row["c"]
    except Exception:
        db_ok = False
        wo_count = 0
    return jsonify({
        "status": "healthy" if db_ok else "degraded",
        "db_connected": db_ok,
        "work_order_count": wo_count,
        "response_time_ms": round((_time.time() - start) * 1000, 1),
        "version": "4.0",
    })


# ── Audit Trail ──────────────────────────────────────────────────

@bp.route("/api/audit/log")
def audit_log():
    from db import get_db
    db = get_db()
    table = request.args.get("table", "")
    limit_val = request.args.get("limit", "100")
    query = "SELECT * FROM audit_trail WHERE 1=1"
    params = []
    if table:
        query += " AND table_name = ?"
        params.append(table)
    query += " ORDER BY changed_datetime DESC LIMIT ?"
    params.append(int(limit_val))
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Notification Center ──────────────────────────────────────────

@bp.route("/api/notifications")
def notifications():
    from db import get_db
    db = get_db()
    items = []
    for r in db.execute("SELECT deviation_id, wc_id, parameter_name, severity, timestamp FROM process_deviations WHERE resolved = 0 AND severity IN ('Critical','Major') ORDER BY timestamp DESC LIMIT 5").fetchall():
        items.append({"type": "alarm", "severity": "critical" if r["severity"] == "Critical" else "warning",
                      "title": f"{r['severity']}: {r['wc_id']}/{r['parameter_name']}", "link": "/process", "ts": r["timestamp"]})
    for r in db.execute("SELECT e.equipment_code, ms.next_due FROM maintenance_schedule ms JOIN equipment e ON e.equipment_id=ms.equipment_id WHERE ms.next_due < DATE('now') LIMIT 5").fetchall():
        items.append({"type": "pm", "severity": "warning", "title": f"PM overdue: {r['equipment_code']}", "link": "/equipment", "ts": r["next_due"]})
    for r in db.execute("SELECT wo_id, due_date FROM work_orders WHERE status NOT IN ('Complete','Cancelled') AND due_date < DATE('now') LIMIT 5").fetchall():
        items.append({"type": "late", "severity": "warning", "title": f"WO {r['wo_id']} overdue", "link": f"/workorder/{r['wo_id']}", "ts": r["due_date"]})
    for r in db.execute("SELECT p.employee_name, pc.expiry_date FROM personnel_certs pc JOIN personnel p ON p.person_id=pc.person_id WHERE pc.expiry_date BETWEEN DATE('now') AND DATE('now','+30 days') LIMIT 5").fetchall():
        items.append({"type": "cert", "severity": "info", "title": f"Cert expiring: {r['employee_name']}", "link": "/labor", "ts": r["expiry_date"]})
    for r in db.execute("SELECT wo_id, hold_reason FROM hold_release WHERE hold_status = 'Active' LIMIT 3").fetchall():
        items.append({"type": "hold", "severity": "critical", "title": f"Hold: {r['wo_id']}", "link": "/process", "ts": None})
    items.sort(key=lambda x: (0 if x["severity"] == "critical" else 1 if x["severity"] == "warning" else 2))
    return jsonify({"count": len(items), "items": items})
