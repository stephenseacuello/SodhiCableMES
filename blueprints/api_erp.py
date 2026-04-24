"""ISA-95 Level 4: Enterprise resource planning, S&OP, order-to-cash.

SodhiCable MES — Level 4 ERP Blueprint

Unified ERP module: S&OP, Purchase Orders, Order-to-Cash, ISA-95 Interface,
Financials, Demand Forecasting, and ERP Simulator control.

Existing endpoints in api_sales, api_mrp, api_inventory, api_suppliers, api_extras
are reused by the ERP dashboard -- this blueprint adds new ERP-specific endpoints only.
"""
from flask import Blueprint, render_template, jsonify, request, redirect
import json

bp = Blueprint("erp", __name__)


# ── Page Route ────────────────────────────────────────────────────
@bp.route("/erp")
def erp_page():
    return render_template("erp.html")


@bp.route("/api/erp/materials")
def erp_materials():
    """List materials for PO creation dropdown."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT m.material_id, m.name, m.unit_cost, m.supplier, m.uom
        FROM materials m ORDER BY m.name
    """).fetchall()
    return jsonify([dict(r) for r in rows])


# ══════════════════════════════════════════════════════════════════
# SIMULATOR CONTROL
# ══════════════════════════════════════════════════════════════════

@bp.route("/api/erp/sim/start", methods=["POST"])
def sim_start():
    from engines.erp_sim import start as erp_start, is_running
    if is_running():
        return jsonify({"ok": False, "message": "Already running"})
    from config import DATABASE
    data = request.get_json(force=True) if request.is_json else {}
    interval = int(data.get("interval", 10))
    interval = max(3, min(interval, 30))  # clamp 3-30s
    erp_start(DATABASE, interval=interval)
    return jsonify({"ok": True, "message": f"ERP simulator started ({interval}s interval)"})


@bp.route("/api/erp/sim/stop", methods=["POST"])
def sim_stop():
    from engines.erp_sim import stop as erp_stop
    erp_stop()
    return jsonify({"ok": True, "message": "ERP simulator stopped"})


@bp.route("/api/erp/sim/status")
def sim_status():
    from engines.erp_sim import is_running, get_tick
    from db import get_db
    db = get_db()
    state = {}
    for r in db.execute("SELECT key, value FROM erp_sim_state").fetchall():
        state[r[0]] = r[1]
    return jsonify({
        "running": is_running(),
        "tick": get_tick(),
        "sim_week": state.get("sim_week", "0"),
        "sim_date": state.get("sim_date", ""),
        "total_orders_generated": state.get("total_orders_generated", "0"),
        "total_pos_created": state.get("total_pos_created", "0"),
    })


# ══════════════════════════════════════════════════════════════════
# DASHBOARD SUMMARY
# ══════════════════════════════════════════════════════════════════

@bp.route("/api/erp/summary")
def erp_summary():
    """Single-call endpoint for ERP dashboard KPIs."""
    from db import get_db
    db = get_db()

    open_sos = db.execute("SELECT COUNT(*) FROM sales_orders WHERE status IN ('Open','InProgress')").fetchone()[0]
    open_pos = db.execute("SELECT COUNT(*) FROM purchase_orders WHERE status IN ('Draft','Approved','Sent')").fetchone()[0]

    ar_row = db.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE status IN ('Sent','Overdue')").fetchone()
    ar_balance = ar_row[0] if ar_row else 0

    # Forecast accuracy (from seed data with actuals)
    fc_rows = db.execute("""
        SELECT forecast_qty, actual_qty FROM demand_forecast
        WHERE actual_qty IS NOT NULL AND actual_qty > 0 ORDER BY created_date DESC LIMIT 50
    """).fetchall()
    if len(fc_rows) >= 3:
        pct_errors = [abs(r[0] - r[1]) / r[1] * 100 for r in fc_rows if r[1] > 0]
        forecast_accuracy = round(100 - (sum(pct_errors) / max(len(pct_errors), 1)), 1) if pct_errors else 89.0
    else:
        forecast_accuracy = 89.0  # fallback for fresh DB

    # ISA-95 messages today
    msg_today = db.execute("SELECT COUNT(*) FROM isa95_messages WHERE timestamp >= date('now')").fetchone()[0]

    # Revenue & COGS
    rev_row = db.execute("SELECT COALESCE(SUM(amount),0) FROM financial_ledger WHERE account_type='Revenue'").fetchone()
    cogs_row = db.execute("SELECT COALESCE(SUM(amount),0) FROM financial_ledger WHERE account_type='COGS'").fetchone()
    total_revenue = rev_row[0]
    total_cogs = cogs_row[0]
    gross_margin = round(total_revenue - total_cogs, 2)

    return jsonify({
        "open_sos": open_sos,
        "open_pos": open_pos,
        "ar_balance": round(ar_balance, 2),
        "forecast_accuracy": forecast_accuracy,
        "isa95_messages_today": msg_today,
        "total_revenue": round(total_revenue, 2),
        "total_cogs": round(total_cogs, 2),
        "gross_margin": gross_margin,
    })


# ══════════════════════════════════════════════════════════════════
# S&OP PLANNING
# ══════════════════════════════════════════════════════════════════

@bp.route("/api/erp/sop/plan")
def sop_plan():
    """Return S&OP plan grid by family."""
    from db import get_db
    db = get_db()
    family = request.args.get("family", "")
    horizon = int(request.args.get("horizon", 12))

    query = "SELECT * FROM sop_plan WHERE plan_version = (SELECT MAX(plan_version) FROM sop_plan)"
    params = []
    if family:
        query += " AND product_family = ?"
        params.append(family)
    query += " ORDER BY product_family, period_start LIMIT ?"
    params.append(horizon * 9)  # 9 families max

    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/erp/sop/adjust", methods=["POST"])
def sop_adjust():
    """User adjusts production_plan for a family+period."""
    from db import get_db
    db = get_db()
    data = request.get_json(force=True)
    family = data.get("family")
    period = data.get("period_start")
    new_plan = float(data.get("production_plan", 0))

    if not family or not period:
        return jsonify({"error": "family and period_start required"}), 400

    row = db.execute(
        "SELECT plan_id, demand_forecast, beginning_inventory FROM sop_plan WHERE product_family=? AND period_start=?",
        (family, period)).fetchone()
    if not row:
        return jsonify({"error": "Plan row not found"}), 404

    ending = round(row[2] + new_plan - row[1], 1)
    cap_req = round(new_plan * 2.5, 1)
    db.execute("""UPDATE sop_plan SET production_plan=?, ending_inventory=?,
                  capacity_required_hrs=?, capacity_gap=capacity_available_hrs-?
                  WHERE plan_id=?""",
               (new_plan, ending, cap_req, cap_req, row[0]))
    db.commit()
    return jsonify({"ok": True})


@bp.route("/api/erp/sop/capacity")
def sop_capacity():
    """Rough-cut capacity check by product family."""
    from db import get_db
    from engines.forecast import family_bottleneck_map
    db = get_db()

    bottlenecks = family_bottleneck_map()
    result = []
    for fam, wcs in bottlenecks.items():
        plan_row = db.execute(
            "SELECT SUM(production_plan) AS total_plan FROM sop_plan WHERE product_family=? AND status='Draft'",
            (fam,)).fetchone()
        total_plan = plan_row[0] if plan_row and plan_row[0] else 0
        cap_required = round(total_plan * 2.5, 1)

        # Available capacity: 3 shifts x 8 hrs x 5 days x 12 weeks = 1440 hrs per WC
        cap_available = len(wcs) * 1440
        result.append({
            "family": fam,
            "bottleneck_wcs": wcs,
            "planned_kft": round(total_plan, 1),
            "capacity_required_hrs": cap_required,
            "capacity_available_hrs": cap_available,
            "utilization_pct": round(cap_required / max(cap_available, 1) * 100, 1),
            "status": "Overloaded" if cap_required > cap_available else "OK",
        })
    return jsonify(result)


@bp.route("/api/erp/sop/approve", methods=["POST"])
def sop_approve():
    """Approve and lock current S&OP plan."""
    from db import get_db
    db = get_db()
    db.execute("UPDATE sop_plan SET status='Approved', approved_by='User', approved_date=datetime('now') WHERE status='Draft'")
    db.commit()

    # Log ISA-95 message
    db.execute("""INSERT INTO isa95_messages (direction,message_type,source_system,target_system,payload_summary,reference_id,status)
                  VALUES ('L4_to_L3','ProductionSchedule','ERP','MES','S&OP plan approved and released to MES','SOP-PLAN','Processed')""")
    db.commit()
    return jsonify({"ok": True, "message": "S&OP plan approved"})


@bp.route("/api/erp/forecast")
def forecast_data():
    """Return demand forecast data."""
    from db import get_db
    db = get_db()
    family = request.args.get("family", "")

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    count_query = "SELECT COUNT(*) FROM demand_forecast"
    data_query = "SELECT * FROM demand_forecast"
    params = []
    if family:
        count_query += " WHERE product_family = ?"
        data_query += " WHERE product_family = ?"
        params.append(family)

    total = db.execute(count_query, params).fetchone()[0]

    data_query += " ORDER BY product_family, period_start LIMIT ? OFFSET ?"
    offset = (page - 1) * per_page
    rows = db.execute(data_query, (*params, per_page, offset)).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@bp.route("/api/erp/forecast/generate", methods=["POST"])
def forecast_generate():
    """Regenerate forecasts for all families."""
    from db import get_db
    from engines.forecast import ses_forecast, des_forecast, forecast_accuracy
    db = get_db()
    data = request.get_json(force=True) if request.is_json else {}
    method = data.get("method", "SES")
    alpha = float(data.get("alpha", 0.3))
    beta = float(data.get("beta", 0.1))

    families = [r[0] for r in db.execute("SELECT DISTINCT family FROM products").fetchall()]
    results = []
    for fam in families:
        actuals_rows = db.execute("""
            SELECT actual_qty FROM demand_forecast
            WHERE product_family=? AND actual_qty IS NOT NULL
            ORDER BY period_start
        """, (fam,)).fetchall()
        actuals = [r[0] for r in actuals_rows]
        if not actuals:
            actuals = [10]

        if method == "DES":
            forecasts = des_forecast(actuals, alpha, beta, periods_ahead=4)
        else:
            forecasts = ses_forecast(actuals, alpha, periods_ahead=4)

        acc = forecast_accuracy(forecasts[:len(actuals)], actuals)

        # Insert new forecast periods
        from datetime import datetime, timedelta
        now = datetime.now()
        for i in range(4):
            period = (now + timedelta(weeks=i)).strftime("%Y-%m-%d")
            fc_val = forecasts[len(actuals) + i] if len(actuals) + i < len(forecasts) else forecasts[-1]
            db.execute(
                "INSERT INTO demand_forecast (product_family,period_start,period_type,forecast_qty,forecast_method,alpha) VALUES (?,?,?,?,?,?)",
                (fam, period, "week", fc_val, method, alpha))

        results.append({"family": fam, "method": method, "alpha": alpha, "accuracy": acc,
                        "forecast_periods": 4})

    db.commit()
    return jsonify({"ok": True, "results": results})


# ══════════════════════════════════════════════════════════════════
# PURCHASE ORDERS
# ══════════════════════════════════════════════════════════════════

@bp.route("/api/erp/po/list")
def po_list():
    from db import get_db
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    total = db.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute("""
        SELECT po.*, m.name AS material_name
        FROM purchase_orders po
        LEFT JOIN materials m ON po.material_id = m.material_id
        ORDER BY po.order_date DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset)).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@bp.route("/api/erp/po/<po_id>")
def po_detail(po_id):
    from db import get_db
    db = get_db()
    po = db.execute("""
        SELECT po.*, m.name AS material_name
        FROM purchase_orders po
        LEFT JOIN materials m ON po.material_id = m.material_id
        WHERE po.po_id = ?
    """, (po_id,)).fetchone()
    if not po:
        return jsonify({"error": "PO not found"}), 404

    grs = db.execute("SELECT * FROM goods_receipts WHERE po_id=? ORDER BY receipt_date DESC", (po_id,)).fetchall()
    result = dict(po)
    result["goods_receipts"] = [dict(r) for r in grs]
    return jsonify(result)


@bp.route("/api/erp/po/create", methods=["POST"])
def po_create():
    from db import get_db
    db = get_db()
    data = request.get_json(force=True)
    material_id = data.get("material_id")
    quantity = float(data.get("quantity", 0))

    if not material_id or quantity <= 0:
        return jsonify({"error": "material_id and positive quantity required"}), 400

    mat = db.execute("SELECT unit_cost, supplier, name FROM materials WHERE material_id=?", (material_id,)).fetchone()
    if not mat:
        return jsonify({"error": "Material not found"}), 404

    count = db.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    po_id = f"PO-USR-{count + 1:04d}"

    db.execute(
        """INSERT INTO purchase_orders (po_id,supplier,material_id,quantity,unit_cost,total_cost,
           expected_delivery,status,created_by) VALUES (?,?,?,?,?,?,date('now','+14 days'),?,?)""",
        (po_id, mat[1] or "Unknown", material_id, quantity, mat[0],
         round(quantity * mat[0], 2), "Draft", "User"))
    db.commit()

    db.execute("""INSERT INTO isa95_messages (direction,message_type,source_system,target_system,payload_summary,reference_id,status)
                  VALUES ('L4_to_L3','MaterialRequirement','ERP','MES',?,?,'Processed')""",
               (f"Manual PO {po_id}: {mat[2]} x {quantity}", po_id))
    db.commit()
    return jsonify({"ok": True, "po_id": po_id})


@bp.route("/api/erp/po/approve", methods=["POST"])
def po_approve():
    from db import get_db
    db = get_db()
    data = request.get_json(force=True)
    po_id = data.get("po_id")
    db.execute("UPDATE purchase_orders SET status='Approved', approved_by='User', approved_date=datetime('now') WHERE po_id=? AND status='Draft'",
               (po_id,))
    db.commit()
    return jsonify({"ok": True})


@bp.route("/api/erp/po/receive", methods=["POST"])
def po_receive():
    """Process goods receipt for a PO."""
    from db import get_db
    db = get_db()
    data = request.get_json(force=True)
    po_id = data.get("po_id")

    po = db.execute("SELECT material_id, quantity FROM purchase_orders WHERE po_id=?", (po_id,)).fetchone()
    if not po:
        return jsonify({"error": "PO not found"}), 404

    qty = po[1]
    accepted = int(qty * 0.98)
    rejected = int(qty) - accepted
    lot = f"GR-USR-{__import__('random').randint(10000,99999)}"

    db.execute(
        """INSERT INTO goods_receipts (po_id,material_id,qty_received,qty_accepted,qty_rejected,
           inspector,inspection_result,lot_number) VALUES (?,?,?,?,?,?,?,?)""",
        (po_id, po[0], int(qty), accepted, rejected, "User", "Pass", lot))
    db.execute("UPDATE purchase_orders SET status='Received', actual_delivery=datetime('now') WHERE po_id=?", (po_id,))

    # Update inventory
    existing = db.execute("SELECT inv_id FROM inventory WHERE material_id=? LIMIT 1", (po[0],)).fetchone()
    if existing:
        db.execute("UPDATE inventory SET qty_on_hand = qty_on_hand + ? WHERE inv_id=?", (accepted, existing[0]))

    db.execute("""INSERT INTO isa95_messages (direction,message_type,source_system,target_system,payload_summary,reference_id,status)
                  VALUES ('L3_to_L4','MaterialReceipt','MES','ERP',?,?,'Processed')""",
               (f"GR for {po_id}: {accepted} accepted", po_id))
    db.commit()
    return jsonify({"ok": True, "accepted": accepted, "rejected": rejected, "lot": lot})


# ══════════════════════════════════════════════════════════════════
# ORDER-TO-CASH
# ══════════════════════════════════════════════════════════════════

@bp.route("/api/erp/otc/pipeline")
def otc_pipeline():
    """Return order-to-cash pipeline for all SOs."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT so.sales_order_id, so.customer_id, c.customer_name, so.order_date,
               so.required_date, so.status AS so_status, so.priority,
               wo.wo_id, wo.status AS wo_status, wo.order_qty_kft,
               sh.shipment_id, sh.status AS ship_status, sh.ship_date,
               inv.invoice_id, inv.status AS inv_status, inv.total AS inv_total,
               sol.product_id, sol.quantity, sol.unit_price
        FROM sales_orders so
        LEFT JOIN customers c ON so.customer_id = c.customer_id
        LEFT JOIN sales_order_lines sol ON so.sales_order_id = sol.sales_order_id
        LEFT JOIN (SELECT sales_order_id, wo_id, status, order_qty_kft
                   FROM work_orders GROUP BY sales_order_id) wo ON wo.sales_order_id = so.sales_order_id
        LEFT JOIN shipments sh ON sh.sales_order_id = so.sales_order_id
        LEFT JOIN invoices inv ON inv.sales_order_id = so.sales_order_id
        GROUP BY so.sales_order_id
        ORDER BY so.order_date DESC
        LIMIT 100
    """).fetchall()

    pipeline = []
    seen = set()
    for r in rows:
        so_id = r[0]
        if so_id in seen:
            continue
        seen.add(so_id)

        # Determine pipeline stage
        if r["inv_status"] == "Paid":
            stage = "Paid"
            stage_num = 6
        elif r["inv_status"] in ("Sent", "Overdue"):
            stage = "Invoiced"
            stage_num = 5
        elif r["ship_status"] in ("Shipped", "Delivered"):
            stage = "Shipped"
            stage_num = 4
        elif r["wo_status"] == "Complete":
            stage = "Produced"
            stage_num = 3
        elif r["wo_status"] in ("Released", "InProcess"):
            stage = "In Production"
            stage_num = 2
        elif r["wo_id"]:
            stage = "WO Created"
            stage_num = 1
        else:
            stage = "Order Received"
            stage_num = 0

        pipeline.append({
            "sales_order_id": so_id,
            "customer_name": r["customer_name"] or r["customer_id"],
            "product_id": r["product_id"],
            "quantity": r["quantity"],
            "order_date": r["order_date"],
            "required_date": r["required_date"],
            "priority": r["priority"],
            "stage": stage,
            "stage_num": stage_num,
            "wo_id": r["wo_id"],
            "wo_status": r["wo_status"],
            "shipment_id": r["shipment_id"],
            "invoice_id": r["invoice_id"],
            "inv_total": r["inv_total"],
            "inv_status": r["inv_status"],
        })
    return jsonify(pipeline)


@bp.route("/api/erp/otc/create_wo", methods=["POST"])
def otc_create_wo():
    """Create a work order from a sales order."""
    from db import get_db
    db = get_db()
    data = request.get_json(force=True)
    so_id = data.get("sales_order_id")

    so = db.execute("""
        SELECT so.sales_order_id, sol.product_id, sol.quantity, so.required_date
        FROM sales_orders so
        JOIN sales_order_lines sol ON so.sales_order_id = sol.sales_order_id
        WHERE so.sales_order_id = ?
    """, (so_id,)).fetchone()
    if not so:
        return jsonify({"error": "Sales order not found"}), 404

    # Check if WO already exists
    existing = db.execute("SELECT wo_id FROM work_orders WHERE sales_order_id=?", (so_id,)).fetchone()
    if existing:
        return jsonify({"error": f"WO {existing[0]} already exists for this SO"}), 400

    count = db.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    wo_id = f"WO-ERP-{count + 1:04d}"

    db.execute(
        """INSERT INTO work_orders (wo_id, product_id, order_qty_kft, priority, due_date, status, created_date, sales_order_id)
           VALUES (?,?,?,3,?,?,datetime('now'),?)""",
        (wo_id, so[1], so[2], so[3], "Released", so_id))
    db.execute("UPDATE sales_orders SET status='InProgress' WHERE sales_order_id=?", (so_id,))

    db.execute("""INSERT INTO isa95_messages (direction,message_type,source_system,target_system,payload_summary,reference_id,status)
                  VALUES ('L4_to_L3','ProductionSchedule','ERP','MES',?,?,'Processed')""",
               (f"WO {wo_id} released from SO {so_id}", wo_id))
    db.commit()
    return jsonify({"ok": True, "wo_id": wo_id})


@bp.route("/api/erp/otc/ship", methods=["POST"])
def otc_ship():
    """Record shipment for a completed WO."""
    from db import get_db
    import random
    db = get_db()
    data = request.get_json(force=True)
    so_id = data.get("sales_order_id")

    wo = db.execute("""
        SELECT wo.wo_id, wo.order_qty_kft, so.customer_id
        FROM work_orders wo
        JOIN sales_orders so ON wo.sales_order_id = so.sales_order_id
        WHERE wo.sales_order_id = ? AND wo.status = 'Complete'
    """, (so_id,)).fetchone()
    if not wo:
        return jsonify({"error": "No completed WO found for this SO"}), 400

    count = db.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
    ship_id = f"SHIP-USR-{count + 1:04d}"
    carriers = ["FedEx Freight", "UPS Freight", "YRC", "Old Dominion"]

    db.execute(
        "INSERT INTO shipments (shipment_id,sales_order_id,wo_id,customer_id,carrier,qty_shipped,status) VALUES (?,?,?,?,?,?,?)",
        (ship_id, so_id, wo[0], wo[2], random.choice(carriers), wo[1], "Shipped"))
    db.execute("UPDATE sales_orders SET status='Shipped' WHERE sales_order_id=?", (so_id,))
    db.commit()
    return jsonify({"ok": True, "shipment_id": ship_id})


@bp.route("/api/erp/otc/invoice", methods=["POST"])
def otc_invoice():
    """Generate invoice from a shipped order."""
    from db import get_db
    db = get_db()
    data = request.get_json(force=True)
    so_id = data.get("sales_order_id")

    ship = db.execute("""
        SELECT s.shipment_id, s.customer_id, s.qty_shipped, sol.unit_price
        FROM shipments s
        JOIN sales_order_lines sol ON s.sales_order_id = sol.sales_order_id
        WHERE s.sales_order_id = ? AND s.status IN ('Shipped','Delivered')
    """, (so_id,)).fetchone()
    if not ship:
        return jsonify({"error": "No shipped order found"}), 400

    count = db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    inv_id = f"INV-USR-{count + 1:04d}"
    subtotal = round((ship[2] or 1) * (ship[3] or 50), 2)
    tax = round(subtotal * 0.07, 2)

    db.execute(
        "INSERT INTO invoices (invoice_id,sales_order_id,customer_id,subtotal,tax,total,due_date,status) VALUES (?,?,?,?,?,?,date('now','+30 days'),?)",
        (inv_id, so_id, ship[1], subtotal, tax, round(subtotal + tax, 2), "Sent"))
    db.commit()
    return jsonify({"ok": True, "invoice_id": inv_id, "total": round(subtotal + tax, 2)})


# ══════════════════════════════════════════════════════════════════
# ISA-95 INTERFACE
# ══════════════════════════════════════════════════════════════════

@bp.route("/api/erp/isa95/messages")
def isa95_messages():
    """Paginated ISA-95 message log."""
    from db import get_db
    db = get_db()
    direction = request.args.get("direction", "")
    msg_type = request.args.get("type", "")
    limit = int(request.args.get("limit", 50))

    query = "SELECT * FROM isa95_messages WHERE 1=1"
    params = []
    if direction:
        query += " AND direction = ?"
        params.append(direction)
    if msg_type:
        query += " AND message_type = ?"
        params.append(msg_type)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/erp/isa95/stats")
def isa95_stats():
    """Aggregate ISA-95 message counts."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT direction, message_type, COUNT(*) AS count
        FROM isa95_messages GROUP BY direction, message_type
        ORDER BY direction, count DESC
    """).fetchall()

    total_l4_l3 = db.execute("SELECT COUNT(*) FROM isa95_messages WHERE direction='L4_to_L3'").fetchone()[0]
    total_l3_l4 = db.execute("SELECT COUNT(*) FROM isa95_messages WHERE direction='L3_to_L4'").fetchone()[0]

    return jsonify({
        "total_l4_to_l3": total_l4_l3,
        "total_l3_to_l4": total_l3_l4,
        "total": total_l4_l3 + total_l3_l4,
        "by_type": [dict(r) for r in rows],
    })


@bp.route("/api/erp/isa95/flow")
def isa95_flow():
    """Data for ISA-95 flow/Sankey visualization."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT source_system, target_system, message_type, COUNT(*) AS count
        FROM isa95_messages
        GROUP BY source_system, target_system, message_type
        ORDER BY count DESC
    """).fetchall()
    return jsonify([dict(r) for r in rows])


# ══════════════════════════════════════════════════════════════════
# FINANCIALS
# ══════════════════════════════════════════════════════════════════

@bp.route("/api/erp/finance/pnl")
def finance_pnl():
    """P&L statement by period."""
    from db import get_db
    db = get_db()
    period = request.args.get("period", "")

    query = """
        SELECT period, account_type, ROUND(SUM(amount), 2) AS total
        FROM financial_ledger
    """
    params = []
    if period:
        query += " WHERE period = ?"
        params.append(period)
    query += " GROUP BY period, account_type ORDER BY period, account_type"

    rows = db.execute(query, params).fetchall()

    # Pivot into P&L structure
    periods = {}
    for r in rows:
        p = r[0] or "Unknown"
        if p not in periods:
            periods[p] = {"period": p, "Revenue": 0, "COGS": 0, "MaterialCost": 0,
                          "LaborCost": 0, "ScrapCost": 0, "OverheadCost": 0}
        periods[p][r[1]] = r[2]

    # Calculate margins
    result = []
    for p, data in sorted(periods.items()):
        data["GrossMargin"] = round(data["Revenue"] - data["COGS"], 2)
        data["OperatingCosts"] = round(data["MaterialCost"] + data["LaborCost"] + data["ScrapCost"] + data["OverheadCost"], 2)
        data["NetMargin"] = round(data["GrossMargin"] - data["OperatingCosts"], 2)
        data["MarginPct"] = round(data["GrossMargin"] / max(data["Revenue"], 1) * 100, 1)
        result.append(data)

    return jsonify(result)


@bp.route("/api/erp/finance/cost_breakdown")
def finance_cost_breakdown():
    """Cost breakdown by product family."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT p.family,
               ROUND(AVG(p.revenue_per_kft), 2) AS avg_revenue,
               ROUND(AVG(p.cost_per_kft), 2) AS avg_cost,
               ROUND(AVG(p.revenue_per_kft - p.cost_per_kft), 2) AS avg_margin,
               COUNT(DISTINCT p.product_id) AS product_count
        FROM products p
        GROUP BY p.family
        ORDER BY p.family
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/erp/finance/ar_aging")
def finance_ar_aging():
    """Accounts receivable aging buckets."""
    from db import get_db
    db = get_db()

    buckets = {
        "current": db.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status='Sent' AND due_date >= date('now')").fetchone()[0],
        "days_30": db.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status IN ('Sent','Overdue') AND due_date < date('now') AND due_date >= date('now','-30 days')").fetchone()[0],
        "days_60": db.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status IN ('Sent','Overdue') AND due_date < date('now','-30 days') AND due_date >= date('now','-60 days')").fetchone()[0],
        "days_90_plus": db.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status IN ('Sent','Overdue') AND due_date < date('now','-60 days')").fetchone()[0],
    }
    buckets["total"] = round(sum(buckets.values()), 2)
    return jsonify(buckets)
