"""ISA-95 Level 3, MESA F1: Resource allocation & work orders.

SodhiCable MES — Work Orders Blueprint
CRUD for work orders with audit trail, validation, CSV export, and auto lot numbering.
"""
import csv
import io

from flask import Blueprint, render_template, jsonify, request, Response

bp = Blueprint("workorders", __name__)


@bp.route("/workorders")
def workorders_page():
    return render_template("workorders.html")


@bp.route("/api/workorders/list")
def wo_list():
    from db import get_db
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    total = db.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute("""
        SELECT wo.*, p.description AS product_desc, p.awg, p.jacket_type
        FROM work_orders wo
        LEFT JOIN products p ON wo.product_id = p.product_id
        ORDER BY wo.due_date ASC
        LIMIT ? OFFSET ?
    """, (per_page, offset)).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@bp.route("/api/workorders/export")
def wo_export():
    """Export work orders as CSV."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft, wo.priority, wo.due_date,
               wo.planned_start, wo.planned_end, wo.actual_start, wo.actual_end,
               wo.status, wo.business_unit, wo.created_date
        FROM work_orders wo ORDER BY wo.due_date ASC
    """).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['WO ID', 'Product', 'Qty (KFT)', 'Priority', 'Due Date',
                     'Planned Start', 'Planned End', 'Actual Start', 'Actual End',
                     'Status', 'Business Unit', 'Created'])
    for r in rows:
        writer.writerow([r['wo_id'], r['product_id'], r['order_qty_kft'], r['priority'],
                        r['due_date'], r['planned_start'], r['planned_end'],
                        r['actual_start'], r['actual_end'], r['status'],
                        r['business_unit'], r['created_date']])
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=workorders_export.csv'})


@bp.route("/api/workorders/create", methods=["POST"])
def wo_create():
    from db import get_db
    from utils.validation import validate_required, validate_exists, validate_positive_number
    from utils.audit import log_audit
    db = get_db()
    data = request.get_json(force=True)

    # Input validation
    missing = validate_required(data, ["product_id"])
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    if not validate_exists(db, "products", "product_id", data["product_id"]):
        return jsonify({"error": f"Product {data['product_id']} not found"}), 400
    qty = data.get("order_qty_kft", 0)
    qty_err = validate_positive_number(qty, "order_qty_kft")
    if qty_err:
        return jsonify({"error": qty_err}), 400

    # Auto-generate WO ID if not provided
    wo_id = data.get("wo_id")
    if not wo_id:
        row = db.execute("SELECT COUNT(*) AS cnt FROM work_orders").fetchone()
        wo_id = f"WO-2026-{row['cnt']+1:03d}"

    # Auto-generate lot number
    from utils.lot_number import generate_lot_number
    lot_number = generate_lot_number(db)

    db.execute("""
        INSERT INTO work_orders (wo_id, product_id, order_qty_kft, due_date, priority, business_unit, status, created_date)
        VALUES (?, ?, ?, ?, ?, ?, 'Pending', datetime('now'))
    """, (
        wo_id,
        data["product_id"],
        qty,
        data.get("due_date"),
        data.get("priority", 3),
        data.get("business_unit", "Industrial"),
    ))

    # Seed lot tracking with the auto-generated lot number
    db.execute(
        "INSERT INTO lot_tracking (output_lot, wo_id, tier_level, notes) VALUES (?, ?, 'Finished', 'Auto-generated')",
        (lot_number, wo_id),
    )

    log_audit(db, "work_orders", wo_id, "status", None, "Pending")
    db.commit()
    return jsonify({"ok": True, "wo_id": wo_id, "lot_number": lot_number})


@bp.route("/api/workorders/update_status", methods=["POST"])
def wo_update_status():
    from db import get_db
    from utils.audit import log_audit
    db = get_db()
    data = request.get_json(force=True)

    new_status = data["status"]
    wo_id_val = data["wo_id"]

    valid_statuses = ["Pending", "InProcess", "Complete", "On Hold", "Cancelled"]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400

    # Get old status for audit trail
    old_row = db.execute("SELECT status FROM work_orders WHERE wo_id = ?", (wo_id_val,)).fetchone()
    if not old_row:
        return jsonify({"error": f"Work order {wo_id_val} not found"}), 404

    if new_status == "InProcess":
        db.execute("UPDATE work_orders SET status = ?, actual_start = datetime('now') WHERE wo_id = ?", (new_status, wo_id_val))
    elif new_status == "Complete":
        db.execute("UPDATE work_orders SET status = ?, actual_end = datetime('now') WHERE wo_id = ?", (new_status, wo_id_val))
    else:
        db.execute("UPDATE work_orders SET status = ? WHERE wo_id = ?", (new_status, wo_id_val))

    log_audit(db, "work_orders", wo_id_val, "status", old_row["status"], new_status)
    db.commit()
    return jsonify({"ok": True, "wo_id": data["wo_id"], "status": data["status"]})


@bp.route("/workorder/<wo_id>")
def wo_detail_page(wo_id):
    return render_template("workorder_detail.html", wo_id=wo_id)


@bp.route("/api/workorders/<wo_id>")
def wo_detail(wo_id):
    from db import get_db
    db = get_db()
    wo = db.execute("SELECT wo.*, p.name AS product_name, p.family, p.awg FROM work_orders wo LEFT JOIN products p ON p.product_id = wo.product_id WHERE wo.wo_id = ?", (wo_id,)).fetchone()
    if not wo: return jsonify({"error": "Not found"}), 404
    operations = [dict(r) for r in db.execute("SELECT o.*, wc.name AS wc_name FROM operations o LEFT JOIN work_centers wc ON wc.wc_id = o.wc_id WHERE o.wo_id = ? ORDER BY o.step_sequence", (wo_id,)).fetchall()]
    quality = [dict(r) for r in db.execute("SELECT ncr_id, defect_type, severity, status, reported_date FROM ncr WHERE wo_id = ? ORDER BY reported_date DESC", (wo_id,)).fetchall()]
    tests = [dict(r) for r in db.execute("SELECT test_type, pass_fail, test_value, test_date FROM test_results WHERE wo_id = ? ORDER BY test_date DESC", (wo_id,)).fetchall()]
    lots = [dict(r) for r in db.execute("SELECT output_lot, input_lot, qty_consumed, tier_level, transaction_time FROM lot_tracking WHERE wo_id = ? ORDER BY transaction_time", (wo_id,)).fetchall()]
    scrap = [dict(r) for r in db.execute("SELECT cause_code, quantity_ft, cost, disposition, timestamp FROM scrap_log WHERE wo_id = ? ORDER BY timestamp DESC", (wo_id,)).fetchall()]
    holds = [dict(r) for r in db.execute("SELECT hold_reason, held_date, hold_status, disposition, released_date FROM hold_release WHERE wo_id = ?", (wo_id,)).fetchall()]
    audit = [dict(r) for r in db.execute("SELECT field_changed, old_value, new_value, changed_datetime, change_reason FROM audit_trail WHERE table_name = 'work_orders' AND record_id = ? ORDER BY changed_datetime DESC", (wo_id,)).fetchall()]
    return jsonify({"work_order": dict(wo), "operations": operations, "quality": quality, "tests": tests, "lots": lots, "scrap": scrap, "holds": holds, "audit": audit})
