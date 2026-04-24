"""ISA-95 Level 3, MESA F4: Document & recipe control.

SodhiCable MES — F4 Document Control Blueprint
Technical manuals, SOPs, recipes, specifications -- with linkage to products and work centers.
"""
from flask import Blueprint, render_template, jsonify, request

bp = Blueprint("documents", __name__)


@bp.route("/documents")
def documents_page():
    return render_template("documents.html")


@bp.route("/api/documents/recipes")
def recipes():
    """Return recipes grouped with their parameters and ingredients."""
    from db import get_db
    db = get_db()

    # Get recipes
    recipe_rows = db.execute("""
        SELECT r.recipe_id, r.recipe_code, r.description, r.product_id, r.work_center_id,
               r.version, r.status, r.effective_date,
               p.name AS product_name, p.family,
               wc.name AS wc_name
        FROM recipes r
        LEFT JOIN products p ON p.product_id = r.product_id
        LEFT JOIN work_centers wc ON wc.wc_id = r.work_center_id
        ORDER BY r.work_center_id, r.product_id
    """).fetchall()

    recipes = []
    for r in recipe_rows:
        rd = dict(r)
        rid = rd["recipe_id"]

        # Get parameters for this recipe
        params = db.execute(
            "SELECT parameter_name, parameter_value, uom, lower_limit, upper_limit, control_type FROM recipe_parameters WHERE recipe_id = ? ORDER BY parameter_name",
            (rid,)
        ).fetchall()
        rd["parameters"] = [dict(p) for p in params]

        # Get ingredients for this recipe
        ingr = db.execute("""
            SELECT ri.material_id, m.name AS material_name, ri.qty_per_kft, ri.uom, ri.scrap_allowance
            FROM recipe_ingredients ri
            JOIN materials m ON m.material_id = ri.material_id
            WHERE ri.recipe_id = ?
            ORDER BY m.name
        """, (rid,)).fetchall()
        rd["ingredients"] = [dict(i) for i in ingr]

        recipes.append(rd)

    return jsonify(recipes)


@bp.route("/api/documents/list")
def doc_list():
    """Return documents with their linked products/WCs."""
    from db import get_db
    db = get_db()
    rows = db.execute("SELECT * FROM documents ORDER BY doc_type, doc_name").fetchall()

    docs = []
    for r in rows:
        d = dict(r)
        # Get linked entities
        links = db.execute("""
            SELECT linked_entity_type, linked_entity_id, link_type
            FROM document_links WHERE doc_id = ?
        """, (d["doc_id"],)).fetchall()
        d["links"] = [dict(l) for l in links]
        d["linked_products"] = [l["linked_entity_id"] for l in links if l["linked_entity_type"] == "Product"]
        d["linked_wcs"] = [l["linked_entity_id"] for l in links if l["linked_entity_type"] == "WorkCenter"]
        docs.append(d)

    return jsonify(docs)


@bp.route("/api/documents/currency")
def doc_currency():
    from db import get_db
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM documents WHERE status != 'Obsolete'").fetchone()[0]
    current = db.execute("SELECT COUNT(*) FROM documents WHERE status = 'Active'").fetchone()[0]
    currency = round(current / max(total, 1) * 100, 1)
    return jsonify({"total_docs": total, "active_docs": current, "currency_pct": currency, "target": 95.0, "status": "PASS" if currency >= 95 else "FAIL"})


@bp.route("/api/documents/recipe_compare")
def recipe_compare():
    """Compare versions of a recipe side by side."""
    from db import get_db
    db = get_db()
    recipe_code = request.args.get("recipe_code", "")
    if not recipe_code:
        # Return all recipe codes that have multiple versions
        codes = db.execute("SELECT recipe_code, COUNT(*) AS versions FROM recipes GROUP BY recipe_code HAVING versions > 1 ORDER BY recipe_code").fetchall()
        return jsonify({"recipe_codes": [dict(r) for r in codes]})

    versions = db.execute("SELECT * FROM recipes WHERE recipe_code = ? ORDER BY version ASC", (recipe_code,)).fetchall()
    result = []
    for v in versions:
        vd = dict(v)
        params = db.execute("SELECT parameter_name, parameter_value, uom, lower_limit, upper_limit FROM recipe_parameters WHERE recipe_id = ?", (v["recipe_id"],)).fetchall()
        ingredients = db.execute("SELECT ri.material_id, m.name AS material_name, ri.qty_per_kft, ri.uom FROM recipe_ingredients ri LEFT JOIN materials m ON m.material_id = ri.material_id WHERE ri.recipe_id = ?", (v["recipe_id"],)).fetchall()
        vd["parameters"] = [dict(p) for p in params]
        vd["ingredients"] = [dict(i) for i in ingredients]
        result.append(vd)

    # Compute diff between latest two versions
    changes = []
    if len(result) >= 2:
        old_params = {p["parameter_name"]: p for p in result[-2].get("parameters", [])}
        new_params = {p["parameter_name"]: p for p in result[-1].get("parameters", [])}
        for name in set(list(old_params.keys()) + list(new_params.keys())):
            old = old_params.get(name)
            new = new_params.get(name)
            if not old: changes.append({"parameter": name, "change": "added", "new_value": new["parameter_value"] if new else None})
            elif not new: changes.append({"parameter": name, "change": "removed", "old_value": old["parameter_value"]})
            elif old["parameter_value"] != new["parameter_value"]:
                changes.append({"parameter": name, "change": "modified", "old_value": old["parameter_value"], "new_value": new["parameter_value"]})

    return jsonify({"recipe_code": recipe_code, "versions": result, "changes": changes})


@bp.route("/api/documents/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    """Full detail for a single recipe."""
    from db import get_db
    db = get_db()
    r = db.execute("SELECT * FROM recipes WHERE recipe_id = ?", (recipe_id,)).fetchone()
    if not r:
        return jsonify({"error": "Recipe not found"}), 404
    rd = dict(r)
    rd["parameters"] = [dict(p) for p in db.execute("SELECT * FROM recipe_parameters WHERE recipe_id = ?", (recipe_id,)).fetchall()]
    rd["ingredients"] = [dict(i) for i in db.execute("SELECT ri.*, m.name AS material_name FROM recipe_ingredients ri JOIN materials m ON m.material_id = ri.material_id WHERE ri.recipe_id = ?", (recipe_id,)).fetchall()]
    rd["download_log"] = [dict(l) for l in db.execute("SELECT * FROM recipe_download_log WHERE recipe_id = ? ORDER BY download_datetime DESC LIMIT 10", (recipe_id,)).fetchall()]
    return jsonify(rd)
