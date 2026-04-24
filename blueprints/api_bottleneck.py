"""ISA-95 Level 3: Bottleneck & queueing analysis.

SodhiCable MES — Bottleneck Blueprint
Bottleneck identification and Kingman approximation.
"""
from flask import Blueprint, render_template, jsonify, request
from utils.cache import cached
import math

bp = Blueprint("bottleneck", __name__)


@bp.route("/bottleneck")
def bottleneck_page():
    return render_template("bottleneck.html")


@bp.route("/api/bottleneck/analysis")
@cached(ttl=60)
def bottleneck_analysis():
    try:
        from engines.bottleneck import identify_bottleneck
        from db import get_db
        db = get_db()
        raw = identify_bottleneck(db)
        # Engine returns list — convert to structured format for template
        if isinstance(raw, list) and raw:
            raw.sort(key=lambda x: x.get("utilization", 0), reverse=True)
            utilizations = [{"name": w.get("name", w.get("wc_id", "?")), "value": w.get("utilization", 0), "wc_id": w.get("wc_id", ""), "is_bottleneck": i == 0} for i, w in enumerate(raw)]
            bn = raw[0]
            bn_util = bn.get("utilization", 0)
            import math
            kingman_rho = [round(r * 0.01, 2) for r in range(5, 100, 5)]
            kingman_wq = [round((rho / (1 - rho)) * 1.5, 2) if rho < 1 else 999 for rho in kingman_rho]
            return jsonify({
                "bottleneck_wc": bn.get("name", bn.get("wc_id")),
                "bottleneck_util": bn_util,
                "bottleneck_wq": round(bn.get("queue_estimate", 0), 2),
                "utilizations": utilizations,
                "work_centers": [w.get("wc_id", w.get("name", "")) for w in raw],
                "kingman": {"rho": kingman_rho, "wq": kingman_wq},
            })
        return jsonify(raw)
    except Exception:
        # Fall back to DB query
        try:
            from db import get_db
            db = get_db()
            rows = db.execute("""
                SELECT wc_id, name, utilization_target, capacity_hrs_per_week
                FROM work_centers
                ORDER BY utilization_target DESC
            """).fetchall()
            wcs = [dict(r) for r in rows]
            bottleneck = wcs[0] if wcs else None
            # Build response matching template expectations
            utilizations = []
            for i, w in enumerate(wcs):
                utilizations.append({
                    "name": w.get("name") or w.get("wc_id"),
                    "value": w.get("utilization_target", 0),
                    "is_bottleneck": i == 0,
                })
            bn_name = (wcs[0].get("name") or wcs[0].get("wc_id")) if wcs else None
            bn_util = wcs[0].get("utilization_target", 0) if wcs else None

            # Generate Kingman curve data
            import math
            kingman_rho = [round(r * 0.01, 2) for r in range(5, 100, 5)]
            kingman_wq = [round((rho / (1 - rho)) * 1.0 * (1 / 0.5), 2) if rho < 1 else 999 for rho in kingman_rho]

            return jsonify({
                "note": "Engine not loaded – ranked by utilization_target",
                "bottleneck_wc": bn_name,
                "bottleneck_util": bn_util,
                "bottleneck_wq": round((bn_util / (1 - bn_util)) * (1 / 0.5), 2) if bn_util and bn_util < 1 else None,
                "utilizations": utilizations,
                "work_centers": [w.get("name") or w.get("wc_id") for w in wcs],
                "kingman": {"rho": kingman_rho, "wq": kingman_wq},
            })
        except Exception:
            return jsonify({"note": "Engine not loaded", "bottleneck": None})


@bp.route("/api/bottleneck/whatif")
def bottleneck_whatif():
    wc_filter = request.args.get("wc", "")
    delta = float(request.args.get("delta", 0))
    try:
        from db import get_db
        db = get_db()
        rows = db.execute("""
            SELECT wc_id, name, utilization_target, capacity_hrs_per_week
            FROM work_centers
            ORDER BY utilization_target DESC
        """).fetchall()
        wcs = [dict(r) for r in rows]

        utilizations = []
        for i, w in enumerate(wcs):
            name = w.get("name") or w.get("wc_id")
            wc_id = w.get("wc_id", "")
            util = w.get("utilization_target", 0)
            if wc_id == wc_filter or name == wc_filter:
                # Apply capacity change: increasing capacity reduces utilization
                factor = 1 + delta / 100
                util = util / factor if factor > 0 else util
            utilizations.append({
                "name": name,
                "wc_id": wc_id,
                "value": min(util, 0.99),
                "is_bottleneck": False,
            })

        utilizations.sort(key=lambda x: x["value"], reverse=True)
        if utilizations:
            utilizations[0]["is_bottleneck"] = True

        bn = utilizations[0] if utilizations else {}
        kingman_rho = [round(r * 0.01, 2) for r in range(5, 100, 5)]
        kingman_wq = [round((rho / (1 - rho)) * 1.0 * (1 / 0.5), 2) if rho < 1 else 999 for rho in kingman_rho]

        return jsonify({
            "bottleneck_wc": bn.get("name"),
            "bottleneck_util": bn.get("value"),
            "bottleneck_wq": round((bn["value"] / (1 - bn["value"])) * (1 / 0.5), 2) if bn.get("value") and bn["value"] < 1 else None,
            "utilizations": utilizations,
            "kingman": {"rho": kingman_rho, "wq": kingman_wq},
        })
    except Exception:
        return jsonify({"error": "Could not compute what-if"}), 500


@bp.route("/api/bottleneck/kingman")
def kingman():
    lam = float(request.args.get("lam", 0.3))
    mu = float(request.args.get("mu", 0.5))
    ca = float(request.args.get("ca", 1.0))  # arrival CV
    cs = float(request.args.get("cs", 1.0))  # service CV

    try:
        from engines.bottleneck import kingman_approximation
        result = kingman_approximation(lam=lam, mu=mu, ca_sq=ca**2, cs_sq=cs**2)
        return jsonify(result)
    except Exception:
        if mu <= lam:
            return jsonify({"error": "System unstable: lambda >= mu"}), 400

        rho = lam / mu
        # Kingman (VUT) formula: Wq ≈ (rho/(1-rho)) * ((ca^2+cs^2)/2) * (1/mu)
        wq = (rho / (1 - rho)) * ((ca ** 2 + cs ** 2) / 2) * (1 / mu)
        ws = wq + 1 / mu
        lq = lam * wq

        return jsonify({
            "note": "Engine not loaded – analytical Kingman (VUT)",
            "lambda": lam,
            "mu": mu,
            "ca": ca,
            "cs": cs,
            "rho": round(rho, 4),
            "Wq": round(wq, 4),
            "Ws": round(ws, 4),
            "Lq": round(lq, 4),
        })
