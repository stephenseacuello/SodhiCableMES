"""ISA-95 Level 3, MESA F10: Product tracking & genealogy (spans L2-L4).

SodhiCable MES — Traceability Blueprint
Lot genealogy and reel inventory.
"""
from flask import Blueprint, render_template, jsonify, request

bp = Blueprint("traceability", __name__)


@bp.route("/traceability")
def traceability_page():
    return render_template("traceability.html")


@bp.route("/api/traceability/lots")
def lot_list():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT DISTINCT output_lot FROM lot_tracking
        UNION
        SELECT DISTINCT input_lot FROM lot_tracking WHERE input_lot IS NOT NULL
        ORDER BY 1
    """).fetchall()
    return jsonify({"lots": [r[0] for r in rows]})


@bp.route("/api/traceability/trace")
def trace_lot():
    from db import get_db
    db = get_db()
    lot = request.args.get("lot", "")
    direction = request.args.get("direction", "forward")

    if not lot:
        return jsonify({"error": "lot parameter required"}), 400

    if direction == "forward":
        # Forward trace: find all children from this lot
        rows = db.execute("""
            WITH RECURSIVE trace AS (
                SELECT lot_id, output_lot, input_lot, wo_id, operation_id, transaction_time, 0 AS depth
                FROM lot_tracking
                WHERE input_lot = ?
                UNION ALL
                SELECT lt.lot_id, lt.output_lot, lt.input_lot, lt.wo_id, lt.operation_id, lt.transaction_time, t.depth + 1
                FROM lot_tracking lt
                JOIN trace t ON lt.input_lot = t.output_lot
                WHERE t.depth < 10
            )
            SELECT * FROM trace ORDER BY depth, transaction_time
        """, (lot,)).fetchall()
    else:
        # Backward trace: find all parents of this lot
        rows = db.execute("""
            WITH RECURSIVE trace AS (
                SELECT lot_id, output_lot, input_lot, wo_id, operation_id, transaction_time, 0 AS depth
                FROM lot_tracking
                WHERE output_lot = ?
                UNION ALL
                SELECT lt.lot_id, lt.output_lot, lt.input_lot, lt.wo_id, lt.operation_id, lt.transaction_time, t.depth + 1
                FROM lot_tracking lt
                JOIN trace t ON lt.output_lot = t.input_lot
                WHERE t.depth < 10
            )
            SELECT * FROM trace ORDER BY depth, transaction_time
        """, (lot,)).fetchall()

    return jsonify({"lot": lot, "direction": direction, "trace": [dict(r) for r in rows]})


@bp.route("/api/traceability/risk_scored_trace")
def risk_scored_trace():
    """Forward trace with risk scoring — enables smart quarantine release.

    Each traced lot gets a risk score based on process quality indicators:
    - All spark tests passed? (low risk)
    - SPC readings within 2σ? (low risk)
    - Any process deviations during production? (high risk)
    Lots scoring below threshold can be released immediately; marginal lots need re-inspection.
    """
    from db import get_db
    db = get_db()
    lot = request.args.get("lot", "")
    if not lot:
        return jsonify({"error": "lot parameter required"}), 400

    # Forward trace
    rows = db.execute("""
        WITH RECURSIVE trace AS (
            SELECT lot_id, output_lot, input_lot, wo_id, 0 AS depth
            FROM lot_tracking WHERE input_lot = ?
            UNION ALL
            SELECT lt.lot_id, lt.output_lot, lt.input_lot, lt.wo_id, t.depth + 1
            FROM lot_tracking lt JOIN trace t ON lt.input_lot = t.output_lot
            WHERE t.depth < 10
        ) SELECT DISTINCT output_lot, wo_id, depth FROM trace ORDER BY depth
    """, (lot,)).fetchall()

    scored = []
    for r in rows:
        out_lot = r["output_lot"]
        wo = r["wo_id"]
        risk = 0.0
        factors = []

        # Check spark tests for this WO
        sparks = db.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN result='FAIL' THEN 1 ELSE 0 END) AS fails FROM spark_test_log WHERE wo_id = ?",
            (wo,)).fetchone() if wo else None
        if sparks and sparks["total"] and sparks["total"] > 0:
            fail_rate = (sparks["fails"] or 0) / sparks["total"]
            if fail_rate > 0:
                risk += 40
                factors.append(f"Spark fail rate: {fail_rate*100:.0f}%")
            else:
                factors.append("All spark tests PASS")

        # Check for process deviations during this WO
        devs = db.execute(
            "SELECT COUNT(*) AS c FROM process_deviations WHERE wo_id = ? AND severity IN ('Major','Critical')",
            (wo,)).fetchone() if wo else None
        if devs and devs["c"] > 0:
            risk += 30
            factors.append(f"{devs['c']} Major/Critical deviations")

        # Check SPC readings quality
        ooc = db.execute(
            "SELECT COUNT(*) AS c FROM spc_readings WHERE wo_id = ? AND status = 'OOC'",
            (wo,)).fetchone() if wo else None
        if ooc and ooc["c"] > 0:
            risk += 20
            factors.append(f"{ooc['c']} SPC out-of-control readings")

        # Check if any holds existed
        holds = db.execute(
            "SELECT COUNT(*) AS c FROM hold_release WHERE wo_id = ?",
            (wo,)).fetchone() if wo else None
        if holds and holds["c"] > 0:
            risk += 10
            factors.append(f"{holds['c']} hold events")

        risk_level = "HIGH" if risk >= 40 else "MEDIUM" if risk >= 20 else "LOW"
        action = "Re-inspect" if risk >= 40 else "Review" if risk >= 20 else "Release"

        scored.append({
            "lot": out_lot, "wo_id": wo, "depth": r["depth"],
            "risk_score": risk, "risk_level": risk_level,
            "recommended_action": action, "factors": factors,
        })

    # Summary
    high = sum(1 for s in scored if s["risk_level"] == "HIGH")
    med = sum(1 for s in scored if s["risk_level"] == "MEDIUM")
    low = sum(1 for s in scored if s["risk_level"] == "LOW")

    return jsonify({
        "source_lot": lot, "total_lots": len(scored),
        "high_risk": high, "medium_risk": med, "low_risk": low,
        "release_immediately": low, "needs_review": med, "needs_reinspection": high,
        "lots": scored,
    })


@bp.route("/api/traceability/reels")
def reels():
    from db import get_db
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    total = db.execute("SELECT COUNT(*) FROM reel_inventory").fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        "SELECT * FROM reel_inventory ORDER BY reel_id LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@bp.route("/api/traceability/graph")
def trace_graph():
    """Return node/edge structure for visual genealogy rendering."""
    from db import get_db
    db = get_db()
    lot = request.args.get("lot", "")
    direction = request.args.get("direction", "forward")
    if not lot:
        return jsonify({"error": "lot parameter required"}), 400

    if direction == "forward":
        rows = db.execute("""
            WITH RECURSIVE trace AS (
                SELECT lot_id, output_lot, input_lot, wo_id, tier_level, qty_consumed, 0 AS depth
                FROM lot_tracking WHERE input_lot = ?
                UNION ALL
                SELECT lt.lot_id, lt.output_lot, lt.input_lot, lt.wo_id, lt.tier_level, lt.qty_consumed, t.depth+1
                FROM lot_tracking lt JOIN trace t ON lt.input_lot = t.output_lot WHERE t.depth < 10
            ) SELECT * FROM trace ORDER BY depth""", (lot,)).fetchall()
    else:
        rows = db.execute("""
            WITH RECURSIVE trace AS (
                SELECT lot_id, output_lot, input_lot, wo_id, tier_level, qty_consumed, 0 AS depth
                FROM lot_tracking WHERE output_lot = ?
                UNION ALL
                SELECT lt.lot_id, lt.output_lot, lt.input_lot, lt.wo_id, lt.tier_level, lt.qty_consumed, t.depth+1
                FROM lot_tracking lt JOIN trace t ON lt.output_lot = t.input_lot WHERE t.depth < 10
            ) SELECT * FROM trace ORDER BY depth""", (lot,)).fetchall()

    nodes = {}
    edges = []
    # Add root node
    nodes[lot] = {"id": lot, "label": lot, "depth": -1, "tier": "Root", "wo_id": None}
    for r in rows:
        out = r["output_lot"]
        inp = r["input_lot"]
        if out and out not in nodes:
            nodes[out] = {"id": out, "label": out, "depth": r["depth"], "tier": r["tier_level"] or "Unknown", "wo_id": r["wo_id"]}
        if inp and inp not in nodes:
            nodes[inp] = {"id": inp, "label": inp, "depth": max(0, r["depth"]-1), "tier": "Input", "wo_id": r["wo_id"]}
        if inp and out:
            edges.append({"from": inp, "to": out})

    return jsonify({"lot": lot, "direction": direction,
                    "nodes": list(nodes.values()), "edges": edges})


@bp.route("/api/traceability/print_verify", methods=["POST"])
def print_verify():
    """Record and verify print marking on a reel against its specification."""
    from db import get_db
    from utils.audit import log_audit
    db = get_db()
    data = request.get_json(force=True)
    reel_id = data.get("reel_id")
    if not reel_id:
        return jsonify({"error": "reel_id required"}), 400

    pm = db.execute("SELECT * FROM print_marking WHERE reel_id = ? ORDER BY timestamp DESC LIMIT 1", (reel_id,)).fetchone()
    reel = db.execute("""
        SELECT ri.*, p.name AS product_name, p.family
        FROM reel_inventory ri LEFT JOIN products p ON ri.product_id = p.product_id
        WHERE ri.reel_id = ?
    """, (reel_id,)).fetchone()
    if not reel:
        return jsonify({"error": "Reel not found"}), 404

    legend = data.get("observed_legend", "")
    checks = []
    expected_product = reel["product_name"] or reel["product_id"] or ""
    checks.append({"field": "product_name", "expected": expected_product,
                    "found": expected_product.lower() in legend.lower() if legend else False})
    if pm:
        for field in ["print_legend", "ul_listing"]:
            val = pm[field] if pm[field] else ""
            checks.append({"field": field, "expected": val,
                           "found": val.lower() in legend.lower() if val and legend else False})

    all_passed = all(c["found"] for c in checks) if checks else False
    if pm:
        db.execute("UPDATE print_marking SET verification_status = ? WHERE reel_id = ?",
                   ("Verified" if all_passed else "Failed", reel_id))
        log_audit(db, "print_marking", reel_id, "verification_status", None,
                  "Verified" if all_passed else "Failed")
        db.commit()

    return jsonify({
        "reel_id": reel_id, "all_passed": all_passed, "checks": checks,
        "verification_status": "Verified" if all_passed else "Failed",
    })


@bp.route("/reel-label/<reel_id>")
def reel_label_page(reel_id):
    """Render print-ready reel label page."""
    return render_template("reel_label.html", reel_id=reel_id)


@bp.route("/api/traceability/reel_label/<reel_id>")
def reel_label_data(reel_id):
    """Get all data needed for a reel label."""
    from db import get_db
    db = get_db()
    reel = db.execute(
        """SELECT ri.*, p.name AS product_name, p.family, p.awg,
                  rt.name AS reel_type_name
           FROM reel_inventory ri
           LEFT JOIN products p ON ri.product_id = p.product_id
           LEFT JOIN reel_types rt ON ri.reel_type_id = rt.reel_type_id
           WHERE ri.reel_id = ?""",
        (reel_id,),
    ).fetchone()
    if not reel:
        return jsonify({"error": "Reel not found"}), 404

    pm = db.execute(
        "SELECT * FROM print_marking WHERE reel_id = ? ORDER BY timestamp DESC LIMIT 1",
        (reel_id,),
    ).fetchone()

    tests = db.execute(
        "SELECT test_type, pass_fail, test_date FROM test_results WHERE lot_number = ? ORDER BY test_date DESC",
        (reel["lot_id"] or "",),
    ).fetchall()

    return jsonify({
        "reel": dict(reel),
        "marking": dict(pm) if pm else None,
        "tests": [dict(t) for t in tests],
    })


# ---------------------------------------------------------------------------
# Certificate of Compliance Generation
# ---------------------------------------------------------------------------
@bp.route("/api/traceability/certificate/<wo_id>")
def certificate_of_compliance(wo_id):
    """Aggregate WO details, test results, lot genealogy, and applicable spec
    into a structured JSON certificate of compliance."""
    from db import get_db
    from datetime import datetime
    db = get_db()

    # Work order + product details
    wo = db.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft, wo.status,
               p.name AS product_name, p.family, p.awg, p.description,
               c.customer_name
        FROM work_orders wo
        JOIN products p ON wo.product_id = p.product_id
        LEFT JOIN sales_orders so ON wo.sales_order_id = so.sales_order_id
        LEFT JOIN customers c ON so.customer_id = c.customer_id
        WHERE wo.wo_id = ?
    """, (wo_id,)).fetchone()
    if not wo:
        return jsonify({"error": "Work order not found"}), 404

    # Determine the lot(s) produced by this WO
    lots = db.execute(
        "SELECT DISTINCT output_lot FROM lot_tracking WHERE wo_id = ?",
        (wo_id,),
    ).fetchall()
    lot_ids = [r["output_lot"] for r in lots]

    # All test results for those lots
    tests = []
    all_passed = True
    for lot_id in lot_ids:
        rows = db.execute("""
            SELECT test_type, test_spec, test_value, test_uom,
                   lower_limit, upper_limit, pass_fail, test_date
            FROM test_results WHERE lot_number = ?
            ORDER BY test_date
        """, (lot_id,)).fetchall()
        for r in rows:
            rec = dict(r)
            rec["lot_number"] = lot_id
            tests.append(rec)
            if rec["pass_fail"] and rec["pass_fail"].upper() != "PASS":
                all_passed = False

    # Lot genealogy (backward trace of input materials)
    material_trace = []
    for lot_id in lot_ids:
        rows = db.execute("""
            WITH RECURSIVE trace AS (
                SELECT lot_id, output_lot, input_lot, input_material_id,
                       tier_level, qty_consumed, uom, 0 AS depth
                FROM lot_tracking WHERE output_lot = ?
                UNION ALL
                SELECT lt.lot_id, lt.output_lot, lt.input_lot,
                       lt.input_material_id, lt.tier_level,
                       lt.qty_consumed, lt.uom, t.depth + 1
                FROM lot_tracking lt
                JOIN trace t ON lt.output_lot = t.input_lot
                WHERE t.depth < 10
            )
            SELECT * FROM trace ORDER BY depth
        """, (lot_id,)).fetchall()
        for r in rows:
            material_trace.append(dict(r))

    # Applicable compliance spec based on product family
    family = wo["family"] or ""
    family_prefix = family[0].upper() if family else ""
    spec_map = {
        "A": "MIL-DTL-24643",
        "B": "MIL-DTL-24643",
        "S": "IEEE 1580 / UL 1309",
        "U": "UL 2196",
        "D": "MIL-DTL-24643 (DHT)",
    }
    compliance_spec = spec_map.get(family_prefix, "Customer Specification")

    return jsonify({
        "wo_id": wo_id,
        "product": {
            "product_id": wo["product_id"],
            "name": wo["product_name"],
            "family": wo["family"],
            "awg": wo["awg"],
            "description": wo["description"],
        },
        "customer": wo["customer_name"],
        "order_qty_kft": wo["order_qty_kft"],
        "test_summary": tests,
        "material_traceability": material_trace,
        "compliance_spec": compliance_spec,
        "issue_date": datetime.utcnow().isoformat(),
        "all_tests_passed": all_passed,
    })


# ---------------------------------------------------------------------------
# Splice Zone Detection
# ---------------------------------------------------------------------------
@bp.route("/api/traceability/splice_zones")
def splice_zones():
    """Find output lots that have multiple distinct input lots, indicating a
    splice (two conductor payoffs merged into one reel)."""
    from db import get_db
    db = get_db()

    rows = db.execute("""
        SELECT output_lot,
               COUNT(DISTINCT input_lot) AS input_count,
               GROUP_CONCAT(DISTINCT input_lot) AS input_lots
        FROM lot_tracking
        WHERE input_lot IS NOT NULL
        GROUP BY output_lot
        HAVING input_count > 1
        ORDER BY input_count DESC
    """).fetchall()

    zones = []
    for r in rows:
        zones.append({
            "output_lot": r["output_lot"],
            "input_count": r["input_count"],
            "input_lots": r["input_lots"].split(",") if r["input_lots"] else [],
            "quarantine_scope_expanded": True,
        })

    return jsonify({"splice_zones": zones, "total": len(zones)})


# ---------------------------------------------------------------------------
# Cycle Detection in Genealogy
# ---------------------------------------------------------------------------
@bp.route("/api/traceability/cycle_check")
def cycle_check():
    """Detect regrind/reclaim cycles where scrap material feeds back into
    production.  Uses a recursive CTE with a visited path; if any output_lot
    appears as its own ancestor within 10 levels, it is flagged."""
    from db import get_db
    db = get_db()

    # Build the full lot graph in Python for cycle detection because SQLite
    # recursive CTEs do not natively support visited-set tracking.
    edges = db.execute("""
        SELECT DISTINCT output_lot, input_lot
        FROM lot_tracking
        WHERE input_lot IS NOT NULL AND output_lot IS NOT NULL
    """).fetchall()

    # Adjacency list: child -> [parents]  (backward edges: output depends on input)
    # For cycle detection we want forward edges: input -> [outputs]
    graph = {}
    for e in edges:
        inp = e["input_lot"]
        out = e["output_lot"]
        graph.setdefault(inp, []).append(out)

    cycles_found = []
    visited_global = set()

    def dfs(node, path, path_set):
        if len(path) > 10:
            return
        for neighbor in graph.get(node, []):
            if neighbor in path_set:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles_found.append(cycle)
            elif neighbor not in visited_global:
                path.append(neighbor)
                path_set.add(neighbor)
                dfs(neighbor, path, path_set)
                path.pop()
                path_set.discard(neighbor)
        visited_global.add(node)

    for start in graph:
        if start not in visited_global:
            dfs(start, [start], {start})

    return jsonify({
        "cycles": cycles_found,
        "cycle_count": len(cycles_found),
        "has_cycles": len(cycles_found) > 0,
    })


# ---------------------------------------------------------------------------
# Multi-Site Trace
# ---------------------------------------------------------------------------
@bp.route("/api/traceability/multi_site_trace")
def multi_site_trace():
    """Enhanced trace that flags when material crosses plant boundaries
    (specifically the NJ-EXT external facility).  Each hop is annotated with
    the work center and whether it is at the external site."""
    from db import get_db
    db = get_db()
    lot = request.args.get("lot", "")
    if not lot:
        return jsonify({"error": "lot parameter required"}), 400

    rows = db.execute("""
        WITH RECURSIVE trace AS (
            SELECT lt.lot_id, lt.output_lot, lt.input_lot, lt.wo_id,
                   lt.operation_id, lt.tier_level, lt.qty_consumed,
                   lt.transaction_time, 0 AS depth
            FROM lot_tracking lt
            WHERE lt.output_lot = ?
            UNION ALL
            SELECT lt.lot_id, lt.output_lot, lt.input_lot, lt.wo_id,
                   lt.operation_id, lt.tier_level, lt.qty_consumed,
                   lt.transaction_time, t.depth + 1
            FROM lot_tracking lt
            JOIN trace t ON lt.output_lot = t.input_lot
            WHERE t.depth < 10
        )
        SELECT trace.*,
               op.wc_id,
               CASE WHEN op.wc_id = 'NJ-EXT' THEN 1 ELSE 0 END AS is_external
        FROM trace
        LEFT JOIN operations op ON trace.operation_id = op.operation_id
        ORDER BY depth, transaction_time
    """, (lot,)).fetchall()

    trace_list = []
    any_external = False
    for r in rows:
        hop = dict(r)
        hop["site_boundary"] = bool(r["is_external"])
        if r["is_external"]:
            any_external = True
        trace_list.append(hop)

    return jsonify({
        "lot": lot,
        "trace": trace_list,
        "incoming_inspection_required": any_external,
        "total_hops": len(trace_list),
    })
