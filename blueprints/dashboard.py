"""ISA-95 Level 3: Production supervision dashboard.

SodhiCable MES v4.0 — Dashboard Blueprint

Supervisor-level dashboard (Week 11 hierarchy):
- 6 KPI cards (OEE, throughput, WIP, on-time, FPY, utilization)
- OEE waterfall (A*P*Q breakdown -- TPM 6 Big Losses)
- Loss Pareto (top 5 stop reasons)
- Capacity utilization bars
Follows 5-Second Rule: biggest KPI top-left, 5-9 metrics max.
"""
from flask import Blueprint, render_template, jsonify, request
from utils.cache import cached

bp = Blueprint("dashboard", __name__)


def _date_wc_filter(table_alias="", date_col="shift_date", wc_col="wc_id", family_col="", shift_col=""):
    """Build WHERE clauses from ?date_from=&date_to=&wc_id=&family=&shift= query params."""
    clauses, params = [], []
    prefix = f"{table_alias}." if table_alias else ""
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    wc_id = request.args.get("wc_id", "")
    family = request.args.get("family", "")
    shift = request.args.get("shift", "")
    # Strip time from datetime-local inputs (T14:30) so DATE comparisons work correctly
    if date_from and "T" in date_from:
        date_from = date_from.split("T")[0]
    if date_to and "T" in date_to:
        date_to = date_to.split("T")[0]
    if date_from:
        clauses.append(f"{prefix}{date_col} >= ?"); params.append(date_from)
    if date_to:
        clauses.append(f"{prefix}{date_col} <= ?"); params.append(date_to)
    if wc_id:
        clauses.append(f"{prefix}{wc_col} = ?"); params.append(wc_id)
    if family and family_col:
        clauses.append(f"{family_col} = ?"); params.append(family)
    if shift and shift_col:
        clauses.append(f"{shift_col} = ?"); params.append(shift)
    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    return where, params


@bp.route("/")
def index():
    """Render main dashboard page."""
    return render_template("dashboard.html")


@bp.route("/api/dashboard/kpis")
@cached(ttl=15)
def dashboard_kpis():
    """Return 6 KPI card values. Supports ?date_from=&date_to=&wc_id=&family= filters."""
    from db import get_db
    db = get_db()
    family = request.args.get("family", "")
    product_id = request.args.get("product_id", "")
    filt, params = _date_wc_filter(shift_col="shift_code")

    # OEE — if family/product filter, join through WCs that processed those WOs
    if family or product_id:
        prod_clauses, prod_params = [], []
        if family: prod_clauses.append("p.family=?"); prod_params.append(family)
        if product_id: prod_clauses.append("p.product_id=?"); prod_params.append(product_id)
        prod_where = " AND ".join(prod_clauses)
        fam_wcs = db.execute(
            f"SELECT DISTINCT o.wc_id FROM operations o JOIN work_orders wo ON o.wo_id=wo.wo_id JOIN products p ON wo.product_id=p.product_id WHERE {prod_where}",
            prod_params).fetchall()
        fam_wc_ids = [r["wc_id"] for r in fam_wcs]
        if fam_wc_ids:
            ph = ",".join("?" for _ in fam_wc_ids)
            row = db.execute(
                f"SELECT ROUND(AVG(oee_overall)*100,1) AS oee FROM shift_reports WHERE wc_id IN ({ph}){filt}",
                fam_wc_ids + params).fetchone()
        else:
            row = {"oee": 0}
    else:
        row = db.execute(
            f"SELECT ROUND(AVG(oee_overall)*100,1) AS oee FROM shift_reports WHERE 1=1{filt}", params
        ).fetchone()
    oee = row["oee"] if row and row["oee"] else 0

    # Throughput + On-Time (work_orders joined to products for family/product)
    wo_clauses, wo_params = [], []
    df = request.args.get("date_from", "")
    dt = request.args.get("date_to", "")
    if df: wo_clauses.append("wo.actual_end >= ?"); wo_params.append(df)
    if dt: wo_clauses.append("wo.actual_end <= ?"); wo_params.append(dt)
    if family: wo_clauses.append("p.family = ?"); wo_params.append(family)
    if product_id: wo_clauses.append("p.product_id = ?"); wo_params.append(product_id)
    wo_where = (" AND " + " AND ".join(wo_clauses)) if wo_clauses else ""
    row = db.execute(f"""
        SELECT COUNT(*) AS completed
        FROM work_orders wo JOIN products p ON wo.product_id=p.product_id
        WHERE wo.status='Complete'{wo_where}
    """, wo_params).fetchone()
    completed = row["completed"]

    # WIP
    wip_clauses, wip_params = [], []
    if family: wip_clauses.append("p.family = ?"); wip_params.append(family)
    if product_id: wip_clauses.append("p.product_id = ?"); wip_params.append(product_id)
    wip_where = (" AND " + " AND ".join(wip_clauses)) if wip_clauses else ""
    row = db.execute(f"""
        SELECT COUNT(*) AS wip FROM work_orders wo JOIN products p ON wo.product_id=p.product_id
        WHERE wo.status='InProcess'{wip_where}
    """, wip_params).fetchone()
    wip = row["wip"]

    # On-Time
    row = db.execute(f"""
        SELECT COUNT(CASE WHEN wo.actual_end <= wo.due_date THEN 1 END) * 100.0 / MAX(COUNT(*), 1) AS on_time_pct
        FROM work_orders wo JOIN products p ON wo.product_id=p.product_id
        WHERE wo.status='Complete' AND wo.due_date IS NOT NULL{wo_where}
    """, wo_params).fetchone()
    on_time = round(row["on_time_pct"], 1) if row["on_time_pct"] else 0

    # FPY (scrap joined to work_orders→products for family)
    scrap_clauses, scrap_params = list(wo_clauses), list(wo_params)  # reuse date+family
    sf = (" AND " + " AND ".join(scrap_clauses)) if scrap_clauses else ""
    # Replace wo.actual_end with sl.timestamp for scrap
    sf = sf.replace("wo.actual_end", "sl.timestamp")
    if family or product_id:
        scrap_ft = db.execute(f"""
            SELECT COALESCE(SUM(sl.quantity_ft),0) AS s FROM scrap_log sl
            LEFT JOIN work_orders wo ON sl.wo_id=wo.wo_id
            LEFT JOIN products p ON wo.product_id=p.product_id
            WHERE 1=1{sf}
        """, scrap_params).fetchone()["s"]
    else:
        sf2, sp2 = _date_wc_filter(date_col="timestamp")
        scrap_ft = db.execute(f"SELECT COALESCE(SUM(quantity_ft),0) AS s FROM scrap_log WHERE 1=1{sf2}", sp2).fetchone()["s"]
    output_ft = db.execute(f"SELECT COALESCE(SUM(total_output_ft),1) AS o FROM shift_reports WHERE 1=1{filt}", params).fetchone()["o"]
    fpy = round((1 - scrap_ft / max(output_ft, 1)) * 100, 1)

    # Utilization
    wcf = request.args.get("wc_id", "")
    if wcf:
        row = db.execute("SELECT ROUND(utilization_target*100,1) AS avg_util FROM work_centers WHERE wc_id=?", (wcf,)).fetchone()
    else:
        row = db.execute("SELECT ROUND(AVG(utilization_target)*100,1) AS avg_util FROM work_centers").fetchone()
    util = row["avg_util"] if row["avg_util"] else 0

    return jsonify({"oee": oee, "throughput": completed, "wip": wip, "on_time": on_time, "fpy": fpy, "utilization": util})


@bp.route("/api/dashboard/oee_by_wc")
def oee_by_wc():
    """Return OEE breakdown per work center. Supports ?date_from=&date_to=&wc_id=&shift= filters."""
    from db import get_db
    db = get_db()
    filt, params = _date_wc_filter(shift_col="shift_code")
    rows = db.execute(f"""
        SELECT wc_id,
            ROUND(AVG(oee_availability) * 100, 1) AS availability,
            ROUND(AVG(oee_performance) * 100, 1) AS performance,
            ROUND(AVG(oee_quality) * 100, 1) AS quality,
            ROUND(AVG(oee_overall) * 100, 1) AS oee
        FROM shift_reports WHERE 1=1{filt}
        GROUP BY wc_id ORDER BY oee DESC
    """, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/dashboard/scrap_pareto")
def scrap_pareto():
    """Return top 5 scrap causes. Supports all filters including family/product."""
    from db import get_db
    db = get_db()
    family = request.args.get("family", "")
    product_id = request.args.get("product_id", "")
    filt, params = _date_wc_filter(date_col="timestamp")
    if family or product_id:
        join = " LEFT JOIN work_orders wo ON sl.wo_id=wo.wo_id LEFT JOIN products p ON wo.product_id=p.product_id"
        extra_clauses = []
        if family: extra_clauses.append("p.family = ?"); params.append(family)
        if product_id: extra_clauses.append("p.product_id = ?"); params.append(product_id)
        filt += " AND " + " AND ".join(extra_clauses)
    else:
        join = ""
    rows = db.execute(f"""
        SELECT sl.cause_code, SUM(sl.quantity_ft) AS total_ft, COUNT(*) AS event_count
        FROM scrap_log sl{join} WHERE 1=1{filt}
        GROUP BY sl.cause_code ORDER BY total_ft DESC LIMIT 5
    """, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/dashboard/wo_status")
def wo_status():
    """Return work order counts by status. Supports ?date_from=&date_to=&family=&product_id= filters."""
    from db import get_db
    db = get_db()
    clauses, params = [], []
    df = request.args.get("date_from", "")
    dt = request.args.get("date_to", "")
    family = request.args.get("family", "")
    product_id = request.args.get("product_id", "")
    if df: clauses.append("wo.created_date >= ?"); params.append(df)
    if dt: clauses.append("wo.created_date <= ?"); params.append(dt)
    if family: clauses.append("p.family = ?"); params.append(family)
    if product_id: clauses.append("p.product_id = ?"); params.append(product_id)
    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(f"""
        SELECT wo.status, COUNT(*) AS count
        FROM work_orders wo JOIN products p ON wo.product_id = p.product_id
        WHERE 1=1{where}
        GROUP BY wo.status ORDER BY count DESC
    """, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/dashboard/capacity")
def capacity_utilization():
    """Return capacity utilization per work center."""
    from db import get_db
    db = get_db()
    wcf = request.args.get("wc_id", "")
    wc_clause = " AND wc.wc_id = ?" if wcf else ""
    wc_params = [wcf] if wcf else []
    rows = db.execute(f"""
        SELECT wc.wc_id, wc.name, wc.utilization_target,
               COALESCE(load.total_hours, 0) AS current_load_hrs, wc.capacity_hrs_per_week
        FROM work_centers wc
        LEFT JOIN (
            SELECT wc_id, SUM(run_time_min + setup_time_min) / 60.0 AS total_hours
            FROM operations WHERE status IN ('InProcess', 'Pending') GROUP BY wc_id
        ) load ON load.wc_id = wc.wc_id
        WHERE 1=1{wc_clause} ORDER BY wc.wc_id
    """, wc_params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/dashboard/downtime_by_category")
def downtime_by_category():
    """Return downtime totals by category. Supports all filters."""
    from db import get_db
    db = get_db()
    filt, params = _date_wc_filter(date_col="start_time")
    family = request.args.get("family", "")
    product_id = request.args.get("product_id", "")
    if family or product_id:
        # downtime_log doesn't have wo_id directly, but has wc_id
        # Filter by WCs that process this family/product
        prod_clauses, prod_params = [], []
        if family: prod_clauses.append("p.family = ?"); prod_params.append(family)
        if product_id: prod_clauses.append("p.product_id = ?"); prod_params.append(product_id)
        prod_where = " AND ".join(prod_clauses)
        fam_wcs = db.execute(
            f"SELECT DISTINCT o.wc_id FROM operations o JOIN work_orders wo ON o.wo_id=wo.wo_id JOIN products p ON wo.product_id=p.product_id WHERE {prod_where}",
            prod_params).fetchall()
        wc_ids = [r["wc_id"] for r in fam_wcs]
        if wc_ids:
            ph = ",".join("?" for _ in wc_ids)
            filt += f" AND wc_id IN ({ph})"
            params.extend(wc_ids)
        else:
            return jsonify([])
    rows = db.execute(f"""
        SELECT category, SUM(duration_min) AS total_min, COUNT(*) AS events
        FROM downtime_log WHERE 1=1{filt} GROUP BY category ORDER BY total_min DESC
    """, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/dashboard/downtime_by_wc")
def downtime_by_wc():
    """Return downtime by WC, stacked by reason category. Supports all filters."""
    from db import get_db
    db = get_db()
    filt, params = _date_wc_filter(date_col="start_time")
    family = request.args.get("family", "")
    product_id = request.args.get("product_id", "")
    if family or product_id:
        prod_clauses, prod_params = [], []
        if family: prod_clauses.append("p.family = ?"); prod_params.append(family)
        if product_id: prod_clauses.append("p.product_id = ?"); prod_params.append(product_id)
        fam_wcs = db.execute(
            f"SELECT DISTINCT o.wc_id FROM operations o JOIN work_orders wo ON o.wo_id=wo.wo_id JOIN products p ON wo.product_id=p.product_id WHERE {' AND '.join(prod_clauses)}",
            prod_params).fetchall()
        wc_ids = [r["wc_id"] for r in fam_wcs]
        if wc_ids:
            ph = ",".join("?" for _ in wc_ids)
            filt += f" AND wc_id IN ({ph})"
            params.extend(wc_ids)
        else:
            return jsonify({"totals": [], "stacked": {"work_centers": [], "categories": [], "data": {}}})
    rows = db.execute(f"""
        SELECT wc_id, category, SUM(duration_min) AS total_min, COUNT(*) AS events
        FROM downtime_log WHERE 1=1{filt} GROUP BY wc_id, category ORDER BY wc_id, total_min DESC
    """, params).fetchall()
    totals = db.execute(f"""
        SELECT wc_id, SUM(duration_min) AS total_min, COUNT(*) AS events
        FROM downtime_log WHERE 1=1{filt} GROUP BY wc_id ORDER BY total_min DESC LIMIT 15
    """, params).fetchall()
    # Build stacked data structure
    wcs = list(dict.fromkeys(r["wc_id"] for r in rows))  # unique, ordered
    categories = list(dict.fromkeys(r["category"] for r in rows))
    stacked = {}
    for r in rows:
        key = (r["wc_id"], r["category"])
        stacked[key] = r["total_min"]
    return jsonify({
        "totals": [dict(r) for r in totals],
        "stacked": {"work_centers": wcs, "categories": categories,
                     "data": {cat: [stacked.get((wc, cat), 0) for wc in wcs] for cat in categories}},
    })


@bp.route("/api/dashboard/scrap_by_wc")
def scrap_by_wc():
    """Return scrap by WC, stacked by cause code. Supports all filters."""
    from db import get_db
    db = get_db()
    family = request.args.get("family", "")
    product_id = request.args.get("product_id", "")
    filt, params = _date_wc_filter(date_col="sl.timestamp", wc_col="sl.wc_id")
    if family or product_id:
        join = " LEFT JOIN work_orders wo ON sl.wo_id=wo.wo_id LEFT JOIN products p ON wo.product_id=p.product_id"
        if family: filt += " AND p.family = ?"; params.append(family)
        if product_id: filt += " AND p.product_id = ?"; params.append(product_id)
    else:
        join = ""
    rows = db.execute(f"""
        SELECT sl.wc_id, sl.cause_code, SUM(sl.quantity_ft) AS total_ft, COUNT(*) AS events
        FROM scrap_log sl{join} WHERE 1=1{filt} GROUP BY sl.wc_id, sl.cause_code ORDER BY sl.wc_id, total_ft DESC
    """, params).fetchall()
    totals = db.execute(f"""
        SELECT sl.wc_id, SUM(sl.quantity_ft) AS total_ft, COUNT(*) AS events
        FROM scrap_log sl{join} WHERE 1=1{filt} GROUP BY sl.wc_id ORDER BY total_ft DESC
    """, params).fetchall()
    wcs = list(dict.fromkeys(r["wc_id"] for r in rows))
    causes = list(dict.fromkeys(r["cause_code"] for r in rows))
    stacked = {}
    for r in rows:
        stacked[(r["wc_id"], r["cause_code"])] = r["total_ft"]
    return jsonify({
        "totals": [dict(r) for r in totals],
        "stacked": {"work_centers": wcs, "causes": causes,
                     "data": {cause: [stacked.get((wc, cause), 0) for wc in wcs] for cause in causes}},
    })


@bp.route("/api/dashboard/maintenance_upcoming")
def maintenance_upcoming():
    """Return PM status for all equipment. Supports ?wc_id= filter."""
    from db import get_db
    db = get_db()
    wc_id = request.args.get("wc_id", "")
    wc_clause = " AND e.work_center_id = ?" if wc_id else ""
    wc_params = [wc_id] if wc_id else []
    # Return ALL PMs (not just top 30 overdue) so charts show the full mix
    rows = db.execute(f"""
        SELECT e.equipment_code, e.description, e.work_center_id AS wc_id,
               ms.pm_type, ms.next_due,
               CAST(julianday(ms.next_due) - julianday('now') AS INTEGER) AS days_until_due,
               CASE WHEN julianday(ms.next_due) < julianday('now') THEN 'OVERDUE'
                    WHEN julianday(ms.next_due) - julianday('now') < 7 THEN 'DUE SOON'
                    ELSE 'OK' END AS pm_status
        FROM equipment e
        JOIN maintenance_schedule ms ON ms.equipment_id = e.equipment_id
        WHERE 1=1{wc_clause}
        ORDER BY ms.next_due ASC
    """, wc_params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/dashboard/throughput_trend")
def throughput_trend():
    """Daily throughput trend (output footage per day). Supports filters."""
    from db import get_db
    db = get_db()
    filt, params = _date_wc_filter(shift_col="shift_code")
    rows = db.execute(f"""
        SELECT shift_date AS day,
               SUM(total_output_ft) AS output_ft,
               COUNT(*) AS shift_count,
               ROUND(AVG(oee_overall) * 100, 1) AS avg_oee
        FROM shift_reports WHERE 1=1{filt}
        GROUP BY shift_date ORDER BY shift_date ASC
    """, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/dashboard/schedule_adherence")
def schedule_adherence():
    """Today's WO schedule adherence — planned vs actual."""
    from db import get_db
    db = get_db()
    family = request.args.get("family", "")
    product_id = request.args.get("product_id", "")
    clauses, qparams = [], []
    if family: clauses.append("p.family = ?"); qparams.append(family)
    if product_id: clauses.append("p.product_id = ?"); qparams.append(product_id)
    extra = (" AND " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(f"""
        SELECT wo.wo_id, wo.product_id, p.name AS product_name,
               wo.status, wo.order_qty_kft, wo.due_date, wo.actual_start, wo.actual_end,
               s.planned_start, s.planned_end,
               CASE
                 WHEN wo.status = 'Complete' AND wo.actual_end <= wo.due_date THEN 'On Time'
                 WHEN wo.status = 'Complete' AND wo.actual_end > wo.due_date THEN 'Late'
                 WHEN wo.status IN ('InProcess','Released') AND wo.due_date < DATE('now') THEN 'Overdue'
                 WHEN wo.status IN ('InProcess','Released') THEN 'In Progress'
                 ELSE wo.status
               END AS adherence_status
        FROM work_orders wo
        JOIN products p ON wo.product_id = p.product_id
        LEFT JOIN schedule s ON s.wo_id = wo.wo_id
        WHERE wo.status NOT IN ('Cancelled')
          AND wo.due_date IS NOT NULL{extra}
        ORDER BY wo.due_date ASC
        LIMIT 25
    """, qparams).fetchall()
    # Summary counts
    summary = {"on_time": 0, "late": 0, "overdue": 0, "in_progress": 0}
    for r in rows:
        key = r["adherence_status"].lower().replace(" ", "_")
        if key in summary:
            summary[key] += 1
    return jsonify({"orders": [dict(r) for r in rows], "summary": summary})
