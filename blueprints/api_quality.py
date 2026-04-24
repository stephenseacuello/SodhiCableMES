"""ISA-95 Level 3, MESA F7: Quality management & SPC.

SodhiCable MES — Quality Blueprint (F7)
SPC control charts, NCR, Cpk -- filterable by WC and parameter.
CSV export, audit trail, scrap-to-parameter correlation, rework tracking.
"""
import csv
import io

from flask import Blueprint, render_template, jsonify, request, Response

bp = Blueprint("quality", __name__)


@bp.route("/quality")
def quality_page():
    return render_template("quality.html")


@bp.route("/api/quality/spc")
def spc_data():
    """Return SPC readings with optional WC and parameter filters."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    param = request.args.get("parameter", "")

    query = "SELECT * FROM spc_readings WHERE 1=1"
    params = []
    if wc:
        query += " AND wc_id = ?"
        params.append(wc)
    if param:
        query += " AND parameter_name = ?"
        params.append(param)
    query += " ORDER BY measurement_date ASC LIMIT 500"

    rows = db.execute(query, params).fetchall()
    readings = [dict(r) for r in rows]

    # Compute control limits from data
    ucl = cl = lcl = 0
    if readings:
        values = [r["measured_value"] for r in readings if r.get("measured_value") is not None]
        if len(values) > 1:
            import statistics
            cl = statistics.mean(values)
            sigma = statistics.stdev(values)
            ucl = cl + 3 * sigma
            lcl = cl - 3 * sigma

    return jsonify({"readings": readings, "ucl": ucl, "cl": cl, "lcl": lcl, "count": len(readings)})


@bp.route("/api/quality/spc_filters")
def spc_filters():
    """Return available WCs and parameters for SPC filtering."""
    from db import get_db
    db = get_db()
    wcs = db.execute("SELECT DISTINCT wc_id FROM spc_readings ORDER BY wc_id").fetchall()
    params = db.execute("SELECT DISTINCT parameter_name FROM spc_readings ORDER BY parameter_name").fetchall()
    return jsonify({
        "work_centers": [r["wc_id"] for r in wcs],
        "parameters": [r["parameter_name"] for r in params],
    })


@bp.route("/api/quality/cpk")
def cpk():
    """Compute Cpk per WC/parameter combination."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    param = request.args.get("parameter", "")

    query = """SELECT wc_id, parameter_name, measured_value, usl, lsl
               FROM spc_readings WHERE measured_value IS NOT NULL AND usl IS NOT NULL"""
    params = []
    if wc:
        query += " AND wc_id = ?"
        params.append(wc)
    if param:
        query += " AND parameter_name = ?"
        params.append(param)

    rows = db.execute(query, params).fetchall()

    if not rows:
        return jsonify({"cpk_results": [], "note": "No SPC data for selected filters"})

    # Group by WC + parameter
    from collections import defaultdict
    import statistics

    groups = defaultdict(list)
    specs = {}
    for r in rows:
        key = (r["wc_id"], r["parameter_name"])
        groups[key].append(r["measured_value"])
        if key not in specs:
            specs[key] = (r["usl"], r["lsl"])

    results = []
    for (wc_id, param_name), values in sorted(groups.items()):
        if len(values) < 2:
            continue
        mean = statistics.mean(values)
        sigma = statistics.stdev(values)
        usl, lsl = specs[(wc_id, param_name)]
        if sigma > 0 and usl and lsl:
            cp = (usl - lsl) / (6 * sigma)
            cpk = min((usl - mean) / (3 * sigma), (mean - lsl) / (3 * sigma))
        else:
            cp = cpk = 0

        status = "CAPABLE" if cpk >= 1.33 else "MARGINAL" if cpk >= 1.0 else "NEEDS IMPROVEMENT"
        results.append({
            "wc_id": wc_id,
            "parameter": param_name,
            "n_samples": len(values),
            "mean": round(mean, 6),
            "sigma": round(sigma, 6),
            "usl": usl,
            "lsl": lsl,
            "cp": round(cp, 3),
            "cpk": round(cpk, 3),
            "status": status,
        })

    return jsonify({"cpk_results": results})


@bp.route("/api/quality/ncr")
def ncr_list():
    from db import get_db
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    total = db.execute("SELECT COUNT(*) FROM ncr").fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        "SELECT * FROM ncr ORDER BY reported_date DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@bp.route("/api/quality/spark_summary")
def spark_summary():
    """Spark test pass/fail summary."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT result, COUNT(*) AS cnt
        FROM spark_test_log GROUP BY result
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/quality/spc/export")
def spc_export():
    """Export SPC readings as CSV."""
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    param = request.args.get("parameter", "")
    query = "SELECT spc_id, wc_id, parameter_name, measured_value, measurement_date, ucl, cl, lcl, rule_violation, status FROM spc_readings WHERE 1=1"
    params = []
    if wc:
        query += " AND wc_id = ?"
        params.append(wc)
    if param:
        query += " AND parameter_name = ?"
        params.append(param)
    query += " ORDER BY measurement_date ASC"
    rows = db.execute(query, params).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'WC', 'Parameter', 'Value', 'Date', 'UCL', 'CL', 'LCL', 'Violation', 'Status'])
    for r in rows:
        writer.writerow([r['spc_id'], r['wc_id'], r['parameter_name'], r['measured_value'],
                        r['measurement_date'], r['ucl'], r['cl'], r['lcl'], r['rule_violation'], r['status']])
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=spc_export.csv'})


@bp.route("/api/quality/scrap_context/<int:scrap_id>")
def scrap_context(scrap_id):
    """Get process readings around the time of a scrap event for root cause analysis."""
    from db import get_db
    db = get_db()
    scrap = db.execute("SELECT * FROM scrap_log WHERE scrap_id = ?", (scrap_id,)).fetchone()
    if not scrap:
        return jsonify({"error": "Scrap record not found"}), 404

    readings = db.execute(
        """SELECT parameter, value, timestamp, quality_flag
           FROM process_data_live
           WHERE wc_id = ? AND timestamp BETWEEN datetime(?, '-30 minutes') AND datetime(?, '+5 minutes')
           ORDER BY timestamp""",
        (scrap["wc_id"], scrap["timestamp"], scrap["timestamp"]),
    ).fetchall()

    return jsonify({"scrap": dict(scrap), "process_readings": [dict(r) for r in readings]})


@bp.route("/api/quality/scrap/create", methods=["POST"])
def scrap_create():
    """Create a scrap/rework record with disposition tracking."""
    from db import get_db
    from utils.audit import log_audit
    db = get_db()
    data = request.get_json(force=True)

    from utils.validation import validate_required
    missing = validate_required(data, ["cause_code", "quantity_ft"])
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    db.execute(
        """INSERT INTO scrap_log (wo_id, operation_id, wc_id, cause_code, quantity_ft, cost, disposition, notes)
           VALUES (?,?,?,?,?,?,?,?)""",
        (data.get("wo_id"), data.get("operation_id"), data.get("wc_id"),
         data["cause_code"], data["quantity_ft"], data.get("cost"),
         data.get("disposition", "Scrap"), data.get("notes")),
    )
    db.commit()
    scrap_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_audit(db, "scrap_log", scrap_id, "created", None, data.get("disposition", "Scrap"))
    db.commit()
    return jsonify({"ok": True, "scrap_id": scrap_id})


@bp.route("/api/quality/scrap_list")
def scrap_list():
    """List all scrap/rework records."""
    from db import get_db
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    total = db.execute("SELECT COUNT(*) FROM scrap_log").fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        "SELECT * FROM scrap_log ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@bp.route("/api/quality/ncr/create", methods=["POST"])
def ncr_create():
    from db import get_db
    from utils.audit import log_audit
    from utils.validation import validate_required
    db = get_db()
    data = request.get_json(force=True)

    missing = validate_required(data, ["defect_type"])
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    db.execute("""INSERT INTO ncr (product_id, wo_id, lot_number, defect_type, description, severity, detected_at, status)
                  VALUES (?,?,?,?,?,?,?,'Open')""",
               (data.get("product_id"), data.get("wo_id"), data.get("lot_number"),
                data.get("defect_type",""), data.get("description",""), data.get("severity","Minor"),
                data.get("detected_at","")))
    db.commit()
    ncr_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_audit(db, "ncr", ncr_id, "status", None, "Open")
    db.commit()
    return jsonify({"ok": True, "ncr_id": ncr_id})

@bp.route("/api/quality/ncr/update", methods=["POST"])
def ncr_update():
    from db import get_db
    from utils.audit import log_audit
    db = get_db()
    data = request.get_json(force=True)
    ncr_id = data.get("ncr_id")

    # Fetch old values for audit trail
    old_row = db.execute("SELECT * FROM ncr WHERE ncr_id = ?", (ncr_id,)).fetchone()

    updates = []
    params = []
    for field in ["status", "root_cause", "corrective_action", "preventive_action", "resolution", "severity"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
            if old_row:
                log_audit(db, "ncr", ncr_id, field, old_row[field], data[field])
    if data.get("status") == "Closed":
        updates.append("resolved_date = datetime('now')")
    if updates:
        params.append(ncr_id)
        db.execute(f"UPDATE ncr SET {', '.join(updates)} WHERE ncr_id = ?", params)
        db.commit()
    return jsonify({"ok": True, "ncr_id": ncr_id})
