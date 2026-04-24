"""ISA-95 Level 4: Sales order management.

SodhiCable MES -- Sales Orders & ATP Blueprint (Item #13)
Sales order tracking, line-item detail, and Available-To-Promise checking.
"""
from flask import Blueprint, render_template, jsonify, request, redirect

bp = Blueprint("sales", __name__)


@bp.route("/sales")
def sales_page():
    return redirect("/erp?tab=orders")


@bp.route("/api/sales/orders")
def sales_orders():
    """List all sales orders with customer name and line-item summary."""
    from db import get_db
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    total = db.execute("SELECT COUNT(*) FROM sales_orders").fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute("""
        SELECT so.*, c.customer_name,
               GROUP_CONCAT(sol.product_id || ' x ' || sol.quantity, '; ') AS line_items,
               COUNT(sol.line_id) AS line_count,
               SUM(sol.quantity * COALESCE(sol.unit_price, 0)) AS total_value
        FROM sales_orders so
        JOIN customers c ON so.customer_id = c.customer_id
        LEFT JOIN sales_order_lines sol ON so.sales_order_id = sol.sales_order_id
        GROUP BY so.sales_order_id
        ORDER BY so.required_date ASC
        LIMIT ? OFFSET ?
    """, (per_page, offset)).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@bp.route("/api/sales/order/<order_id>")
def sales_order_detail(order_id):
    """Get a specific order with all its line items."""
    from db import get_db
    db = get_db()
    order = db.execute("""
        SELECT so.*, c.customer_name
        FROM sales_orders so
        JOIN customers c ON so.customer_id = c.customer_id
        WHERE so.sales_order_id = ?
    """, (order_id,)).fetchone()
    if not order:
        return jsonify({"error": "Order not found"}), 404

    lines = db.execute("""
        SELECT sol.*, p.name AS product_name
        FROM sales_order_lines sol
        LEFT JOIN products p ON sol.product_id = p.product_id
        WHERE sol.sales_order_id = ?
        ORDER BY sol.line_id
    """, (order_id,)).fetchall()

    result = dict(order)
    result["lines"] = [dict(l) for l in lines]
    return jsonify(result)


@bp.route("/api/sales/atp", methods=["POST"])
def atp_check():
    """Check Available-To-Promise for a product and quantity."""
    from db import get_db
    db = get_db()
    data = request.get_json(force=True)
    product_id = data.get("product_id", "")
    qty_requested = float(data.get("qty_kft", 0))

    row = db.execute("""
        SELECT SUM(qty_on_hand - qty_allocated) AS qty_available
        FROM inventory
        WHERE product_id = ?
    """, (product_id,)).fetchone()

    qty_available = (row["qty_available"] or 0) if row else 0

    return jsonify({
        "product_id": product_id,
        "qty_requested": qty_requested,
        "qty_available": round(qty_available, 2),
        "can_promise": qty_available >= qty_requested,
    })


@bp.route("/api/sales/products")
def sales_products():
    """List products for the ATP dropdown."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT product_id, name, family
        FROM products
        ORDER BY family, name
    """).fetchall()
    return jsonify([dict(r) for r in rows])
