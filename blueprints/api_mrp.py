"""ISA-95 Level 3: Material requirements planning.

SodhiCable MES — MRP Blueprint
Bill of materials and MRP explosion.
"""
from flask import Blueprint, render_template, jsonify, request, redirect

bp = Blueprint("mrp", __name__)


@bp.route("/mrp")
def mrp_page():
    return redirect("/erp?tab=mrp")


@bp.route("/api/mrp/products")
def mrp_products():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT product_id, name, family FROM products ORDER BY family, product_id
    """).fetchall()
    return jsonify({"products": [{"id": r["product_id"], "name": r["name"], "family": r["family"]} for r in rows]})


@bp.route("/api/mrp/explode")
def mrp_explode():
    from db import get_db
    db = get_db()
    product_id = request.args.get("product", "")
    lot_method = request.args.get("lot_method", "LFL")

    if not product_id:
        return jsonify({"error": "product parameter required"}), 400

    # Get product info
    prod = db.execute("SELECT product_id, name FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if not prod:
        return jsonify({"error": f"Product {product_id} not found"}), 404

    # Get BOM materials
    bom_rows = db.execute("""
        SELECT bm.material_id, m.name AS material_name, bm.qty_per_kft, bm.bom_level,
               m.lead_time_days, m.uom
        FROM bom_materials bm
        LEFT JOIN materials m ON bm.material_id = m.material_id
        WHERE bm.product_id = ?
        ORDER BY bm.bom_level, bm.material_id
    """, (product_id,)).fetchall()

    # Build BOM tree
    bom_tree = {"name": prod["name"], "qty": 1, "lead_time": 0, "children": []}
    for r in bom_rows:
        bom_tree["children"].append({
            "name": f"{r['material_name'] or r['material_id']} ({r['uom'] or ''})",
            "qty": r["qty_per_kft"],
            "lead_time": r["lead_time_days"] or 0,
            "children": [],
        })

    # Build MRP grid (simplified)
    weeks = 8
    grid = []
    for r in bom_rows:
        gross_req = r["qty_per_kft"] or 0
        # Get on-hand inventory
        inv_row = db.execute("SELECT qty_on_hand FROM inventory WHERE material_id = ?", (r["material_id"],)).fetchone()
        on_hand = inv_row["qty_on_hand"] if inv_row else 0
        lt = r["lead_time_days"] or 1
        lt_weeks = max(1, (lt + 6) // 7)

        gross_vals = [0] * weeks
        gross_vals[0] = gross_req
        sched_vals = [0] * weeks
        proj_oh = [on_hand] * weeks
        net_vals = [0] * weeks
        planned_vals = [0] * weeks

        for w in range(weeks):
            avail = proj_oh[w - 1] if w > 0 else on_hand
            net = gross_vals[w] - avail - sched_vals[w]
            net_vals[w] = max(0, net)
            if lot_method == "LFL":
                planned_vals[w] = net_vals[w]
            elif lot_method == "EOQ":
                planned_vals[w] = max(net_vals[w], 50) if net_vals[w] > 0 else 0
            elif lot_method == "FOQ":
                planned_vals[w] = 100 if net_vals[w] > 0 else 0
            else:
                planned_vals[w] = net_vals[w]
            proj_oh[w] = avail + sched_vals[w] + planned_vals[w] - gross_vals[w]

        planned_release = [0] * weeks
        for w in range(weeks):
            release_week = w - lt_weeks
            if release_week >= 0 and planned_vals[w] > 0:
                planned_release[release_week] = planned_vals[w]

        grid.append({
            "name": r["material_name"] or r["material_id"],
            "rows": [
                {"label": "Gross Req", "values": gross_vals},
                {"label": "Sched Receipts", "values": sched_vals},
                {"label": "Proj On-Hand", "values": [round(v, 1) for v in proj_oh]},
                {"label": "Net Req", "values": [round(v, 1) for v in net_vals]},
                {"label": "Planned Order", "values": [round(v, 1) for v in planned_vals]},
                {"label": "Planned Release", "values": [round(v, 1) for v in planned_release]},
            ],
        })

    return jsonify({"bom": bom_tree, "grid": grid, "weeks": weeks})


@bp.route("/api/mrp/bom/<product_id>")
def bom(product_id):
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT bm.*, m.name AS material_name, m.uom, m.unit_cost
        FROM bom_materials bm
        LEFT JOIN materials m ON bm.material_id = m.material_id
        WHERE bm.product_id = ?
        ORDER BY bm.bom_level, bm.material_id
    """, (product_id,)).fetchall()
    return jsonify({"product_id": product_id, "bom": [dict(r) for r in rows]})


@bp.route("/api/mrp/run", methods=["POST"])
def mrp_run():
    data = request.get_json(force=True)

    try:
        from engines.mrp_engine import create_mrp_tables, populate_sodhicable_bom, run_mrp
        from db import get_db
        db = get_db()
        create_mrp_tables(db)
        populate_sodhicable_bom(db)
        total, past_due = run_mrp(db)
        return jsonify({"total_orders": total, "past_due": past_due})
    except Exception:
        product_id = data.get("product_id", "PROD-001")
        qty = data.get("order_qty_kft", 10)
        return jsonify({
            "note": "Engine not loaded – mock MRP result",
            "product_id": product_id,
            "order_qty_kft": qty,
            "planned_orders": [
                {"material_id": "MAT-CU-01", "qty_needed": qty * 5.2,
                 "on_hand": 100, "net_req": max(0, qty * 5.2 - 100),
                 "planned_release": "2026-04-20"},
                {"material_id": "MAT-PVC-01", "qty_needed": qty * 2.1,
                 "on_hand": 50, "net_req": max(0, qty * 2.1 - 50),
                 "planned_release": "2026-04-18"},
            ],
        })


@bp.route("/api/mrp/save_run", methods=["POST"])
def mrp_save_run():
    """Persist an MRP run result for historical comparison."""
    from db import get_db
    import json
    db = get_db()
    data = request.get_json(force=True)

    db.execute("""CREATE TABLE IF NOT EXISTS mrp_run_history (
        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_datetime TEXT DEFAULT (datetime('now')),
        product_id TEXT, lot_method TEXT,
        result_json TEXT, notes TEXT)""")

    db.execute(
        "INSERT INTO mrp_run_history (product_id, lot_method, result_json, notes) VALUES (?,?,?,?)",
        (data.get("product_id"), data.get("lot_method"),
         json.dumps(data.get("result")), data.get("notes")),
    )
    db.commit()
    run_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify({"ok": True, "run_id": run_id})


@bp.route("/api/mrp/history")
def mrp_history():
    """Return past MRP runs for comparison."""
    from db import get_db
    db = get_db()
    try:
        rows = db.execute(
            "SELECT run_id, run_datetime, product_id, lot_method, notes FROM mrp_run_history ORDER BY run_datetime DESC LIMIT 50"
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception:
        return jsonify([])


@bp.route("/api/mrp/pegging")
def mrp_pegging():
    """Return demand pegging report for a given item_id."""
    from db import get_db
    from engines.mrp_engine import (create_mrp_tables, get_pegging_report)

    item_id = request.args.get("item_id", "")
    if not item_id:
        return jsonify({"error": "item_id parameter required"}), 400

    db = get_db()
    create_mrp_tables(db)

    report = get_pegging_report(db, item_id)
    return jsonify({"item_id": item_id, "pegging": report})


@bp.route("/api/mrp/kanban")
def mrp_kanban():
    """
    Compute kanban size from query params and return suggested kanban
    sizes for all MRP items based on their demand patterns.
    """
    from db import get_db
    from engines.mrp_engine import (create_mrp_tables, compute_kanban_size)

    db = get_db()
    create_mrp_tables(db)

    # --- Per-request kanban calculation from query parameters ---
    demand_rate = request.args.get("demand_rate", type=float)
    lead_time = request.args.get("lead_time", type=float)
    safety_factor = request.args.get("safety_factor", 0.2, type=float)

    custom_result = None
    if demand_rate is not None and lead_time is not None:
        custom_result = compute_kanban_size(demand_rate, lead_time,
                                            safety_factor)

    # --- Suggested kanban sizes for all MRP items ---
    cur = db.cursor()
    cur.execute("SELECT item_id, name, lead_time FROM mrp_items ORDER BY item_id")
    items = cur.fetchall()

    suggestions = []
    for item_id, name, lt in items:
        # Average weekly demand from mrp_demand
        cur.execute(
            "SELECT AVG(quantity) FROM mrp_demand WHERE item_id = ?",
            (item_id,),
        )
        row = cur.fetchone()
        avg_demand = row[0] if row and row[0] else 0.0

        if avg_demand > 0:
            kb = compute_kanban_size(avg_demand, lt, safety_factor)
            suggestions.append({
                "item_id": item_id,
                "name": name,
                "avg_demand_per_week": round(avg_demand, 2),
                "lead_time_weeks": lt,
                "safety_factor": safety_factor,
                "kanban_size": kb["kanban_size"],
            })

    result = {"safety_factor": safety_factor, "items": suggestions}
    if custom_result is not None:
        result["custom"] = custom_result

    return jsonify(result)
