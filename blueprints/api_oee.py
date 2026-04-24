"""ISA-95 Level 3: OEE calculations.

SodhiCable MES — OEE Drill-Down Blueprint with full filtering.
"""
import csv
import io

from flask import Blueprint, render_template, jsonify, request, Response, redirect

bp = Blueprint("oee", __name__)


@bp.route("/oee")
def oee_page():
    """Redirect to F11 Performance page (OEE drill-down merged into F11)."""
    return redirect("/performance", code=302)


def _build_filters():
    """Parse common query params: wc_id, shift, date_from, date_to, family."""
    wc = request.args.get("wc_id", "")
    shift = request.args.get("shift", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    family = request.args.get("family", "")
    return wc, shift, date_from, date_to, family


def _apply_sr_filters(base_query, wc, shift, date_from, date_to, family):
    """Apply filters to a shift_reports query. Returns (query, params)."""
    clauses = []
    params = []
    if wc:
        clauses.append("sr.wc_id = ?")
        params.append(wc)
    if shift:
        clauses.append("sr.shift_code = ?")
        params.append(shift)
    if date_from:
        clauses.append("sr.shift_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("sr.shift_date <= ?")
        params.append(date_to)
    if family:
        # Filter by product family through work orders on that WC
        clauses.append("""sr.wc_id IN (
            SELECT DISTINCT r.wc_id FROM routings r
            JOIN products p ON p.product_id = r.product_id
            WHERE p.family = ?)""")
        params.append(family)

    where = " AND ".join(clauses)
    if where:
        base_query += " AND " + where if "WHERE" in base_query else " WHERE " + where
    return base_query, params


@bp.route("/api/oee/summary")
def oee_summary():
    from db import get_db
    db = get_db()
    wc, shift, date_from, date_to, family = _build_filters()

    query = """SELECT sr.wc_id, sr.shift_code, sr.shift_date,
               sr.oee_availability, sr.oee_performance, sr.oee_quality, sr.oee_overall,
               sr.total_output_ft, sr.total_scrap_ft, sr.total_downtime_min
               FROM shift_reports sr WHERE 1=1"""
    query, params = _apply_sr_filters(query, wc, shift, date_from, date_to, family)
    query += " ORDER BY sr.shift_date DESC, sr.wc_id"

    rows = db.execute(query, params).fetchall()
    reports = [dict(r) for r in rows]

    if reports:
        avg_a = sum(r["oee_availability"] for r in reports) / len(reports)
        avg_p = sum(r["oee_performance"] for r in reports) / len(reports)
        avg_q = sum(r["oee_quality"] for r in reports) / len(reports)
        avg_oee = sum(r["oee_overall"] for r in reports) / len(reports)
        total_output = sum(r["total_output_ft"] or 0 for r in reports)
        total_scrap = sum(r["total_scrap_ft"] or 0 for r in reports)
        total_downtime = sum(r["total_downtime_min"] or 0 for r in reports)
    else:
        avg_a = avg_p = avg_q = avg_oee = 0
        total_output = total_scrap = total_downtime = 0

    return jsonify({
        "availability": round(avg_a * 100, 1),
        "performance": round(avg_p * 100, 1),
        "quality": round(avg_q * 100, 1),
        "oee": round(avg_oee * 100, 1),
        "total_output_ft": total_output,
        "total_scrap_ft": total_scrap,
        "total_downtime_min": total_downtime,
        "reports": reports[:100],  # Limit to 100 for UI performance
        "count": len(reports),
    })


@bp.route("/api/oee/trend")
def oee_trend():
    from db import get_db
    db = get_db()
    wc, shift, date_from, date_to, family = _build_filters()

    # Aggregate by date (average across shifts and WCs for the filtered set)
    query = """SELECT sr.shift_date,
               AVG(sr.oee_overall) AS avg_oee,
               AVG(sr.oee_availability) AS avg_a,
               AVG(sr.oee_performance) AS avg_p,
               AVG(sr.oee_quality) AS avg_q
               FROM shift_reports sr WHERE 1=1"""
    query, params = _apply_sr_filters(query, wc, shift, date_from, date_to, family)
    query += " GROUP BY sr.shift_date ORDER BY sr.shift_date ASC"

    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/oee/by_wc")
def oee_by_wc():
    """OEE summary per work center (for comparison view)."""
    from db import get_db
    db = get_db()
    _, shift, date_from, date_to, family = _build_filters()

    query = """SELECT sr.wc_id, wc.name AS wc_name,
               AVG(sr.oee_availability) AS avg_a,
               AVG(sr.oee_performance) AS avg_p,
               AVG(sr.oee_quality) AS avg_q,
               AVG(sr.oee_overall) AS avg_oee,
               SUM(sr.total_output_ft) AS total_output,
               SUM(sr.total_scrap_ft) AS total_scrap,
               COUNT(*) AS shift_count
               FROM shift_reports sr
               JOIN work_centers wc ON wc.wc_id = sr.wc_id
               WHERE 1=1"""
    query, params = _apply_sr_filters(query, "", shift, date_from, date_to, family)
    query += " GROUP BY sr.wc_id ORDER BY avg_oee DESC"

    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/oee/losses")
def oee_losses():
    from db import get_db
    db = get_db()
    wc = request.args.get("wc_id", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    query = "SELECT category, SUM(duration_min) AS total_min, COUNT(*) AS events FROM downtime_log WHERE 1=1"
    params = []
    if wc:
        query += " AND wc_id = ?"
        params.append(wc)
    if date_from:
        query += " AND start_time >= ?"
        params.append(date_from)
    if date_to:
        query += " AND start_time <= ?"
        params.append(date_to + " 23:59:59")
    query += " GROUP BY category ORDER BY total_min DESC"

    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/oee/work_centers")
def oee_wcs():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT DISTINCT sr.wc_id, wc.name
        FROM shift_reports sr
        JOIN work_centers wc ON wc.wc_id = sr.wc_id
        ORDER BY sr.wc_id
    """).fetchall()
    return jsonify([{"wc_id": r["wc_id"], "name": r["name"]} for r in rows])


@bp.route("/api/oee/families")
def oee_families():
    from db import get_db
    db = get_db()
    rows = db.execute("SELECT DISTINCT family FROM products ORDER BY family").fetchall()
    return jsonify([r["family"] for r in rows])


@bp.route("/api/oee/export")
def oee_export():
    """Export OEE data as CSV with current filters applied."""
    from db import get_db
    db = get_db()
    wc, shift, date_from, date_to, family = _build_filters()
    query = """SELECT sr.wc_id, sr.shift_date, sr.shift_code,
               sr.oee_availability, sr.oee_performance, sr.oee_quality, sr.oee_overall,
               sr.total_output_ft, sr.total_scrap_ft, sr.total_downtime_min
               FROM shift_reports sr WHERE 1=1"""
    query, params = _apply_sr_filters(query, wc, shift, date_from, date_to, family)
    query += " ORDER BY sr.shift_date DESC, sr.wc_id"
    rows = db.execute(query, params).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['WC', 'Date', 'Shift', 'Availability', 'Performance', 'Quality', 'OEE',
                     'Output (ft)', 'Scrap (ft)', 'Downtime (min)'])
    for r in rows:
        writer.writerow([r['wc_id'], r['shift_date'], r['shift_code'],
                        r['oee_availability'], r['oee_performance'], r['oee_quality'], r['oee_overall'],
                        r['total_output_ft'], r['total_scrap_ft'], r['total_downtime_min']])
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=oee_export.csv'})


@bp.route("/api/oee/date_range")
def oee_date_range():
    from db import get_db
    db = get_db()
    row = db.execute("SELECT MIN(shift_date) AS min_date, MAX(shift_date) AS max_date FROM shift_reports").fetchone()
    return jsonify({"min_date": row["min_date"], "max_date": row["max_date"]})
