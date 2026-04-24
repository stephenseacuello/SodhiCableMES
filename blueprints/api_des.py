"""ISA-95 Level 3: Discrete-event simulation.

SodhiCable MES — DES Blueprint
Discrete-event simulation using actual SodhiCable factory configuration.
"""
from flask import Blueprint, render_template, jsonify, request
import math

bp = Blueprint("des", __name__)


@bp.route("/des")
def des_page():
    return render_template("des.html")


def _build_sodhicable_config(user_config, db):
    """Build DES config from actual SodhiCable factory data.

    Maps our 24 WCs into the DES 8-stage pipeline by grouping:
      Stage 0: COMPOUND (COMPOUND-1, COMPOUND-2)
      Stage 1: DRAW (DRAW-1)
      Stage 2: EXTRUDE (CV-1, CV-2, CV-3, PX-1, PT-1)
      Stage 3: ASSEMBLY (FOIL-1, TAPE-1, BRAID-1/2/3, CABLE-1/2, COMB-1)
      Stage 4: JACKET (PLCV-1, LPML-1, CCCW-1)
      Stage 5: ARMOR (ARMOR-1)
      Stage 6: TEST (TEST-1, TEST-2)
      Stage 7: FINISH (CUT-1, PACK-1)
    """
    # Get actual WC data
    wcs = {}
    for r in db.execute("SELECT wc_id, name, wc_type, num_parallel, capacity_ft_per_hr FROM work_centers WHERE wc_id != 'NJ-EXT'").fetchall():
        wcs[r[0]] = {"name": r[1], "type": r[2], "parallel": r[3], "cap_ft_hr": r[4] or 500}

    # Map WC types to stages with actual service rates
    # Mean service time in hours per job (1 KFT = 1000 ft)
    # service_time = 1000 ft / capacity_ft_per_hr
    stage_groups = [
        ("COMPOUND", ["COMPOUND-1", "COMPOUND-2"], "Compounding"),
        ("DRAW", ["DRAW-1"], "Wire Drawing"),
        ("EXTRUDE", ["CV-1", "CV-2", "CV-3", "PX-1", "PT-1"], "Insulation Extrusion"),
        ("ASSEMBLY", ["FOIL-1", "TAPE-1", "BRAID-1", "BRAID-2", "BRAID-3", "CABLE-1", "CABLE-2", "COMB-1"], "Shielding & Cabling"),
        ("JACKET", ["PLCV-1", "LPML-1", "CCCW-1"], "Jacketing"),
        ("ARMOR", ["ARMOR-1"], "Armoring"),
        ("TEST", ["TEST-1", "TEST-2"], "Testing & QC"),
        ("FINISH", ["CUT-1", "PACK-1"], "Cut & Package"),
    ]

    stages = []
    for stage_name, wc_ids, desc in stage_groups:
        # Aggregate: total parallel servers = sum of parallels for this stage's WCs
        total_servers = 0
        total_rate = 0
        active_wcs = []
        for wc_id in wc_ids:
            if wc_id in wcs:
                w = wcs[wc_id]
                total_servers += w["parallel"]
                total_rate += w["cap_ft_hr"]
                active_wcs.append(wc_id)

        if total_servers == 0:
            total_servers = 1
        if total_rate == 0:
            total_rate = 500

        # Mean service time per job (in hours)
        # Average job size from user config or default 3 KFT
        avg_job_kft = user_config.get("avg_job_kft", 3)
        mean_service = round((avg_job_kft * 1000) / total_rate, 2)

        stages.append({
            "name": f"{stage_name} ({', '.join(active_wcs[:3])}{'...' if len(active_wcs) > 3 else ''})",
            "servers": total_servers,
            "mean_service": max(0.1, mean_service),
            "description": desc,
            "work_centers": active_wcs,
        })

    config = {
        "stages": stages,
        "arrival_rate": user_config.get("arrival_rate", 0.30),
        "dispatch_rule": user_config.get("dispatch_rule", "FIFO"),
        "n_jobs": user_config.get("n_jobs", 20),
        "seed": user_config.get("seed", 42),
        "breakdown_rate": user_config.get("breakdown_rate", 0.02),
        "repair_time": user_config.get("repair_time", 1.0),
    }

    # Optional advanced features
    if user_config.get("rework"):
        config["rework"] = True
        config["rework_rate"] = user_config.get("rework_rate", 0.02)
    if user_config.get("buffer_limits"):
        config["buffer_limits"] = True
        config["max_queue"] = user_config.get("max_queue", 10)

    return config


@bp.route("/api/des/run", methods=["POST"])
def des_run():
    user_config = request.get_json(force=True)

    try:
        from engines.des_engine import SodhiCableDES
        from db import get_db
        db = get_db()

        # Build config from actual factory data
        config = _build_sodhicable_config(user_config, db)

        sim = SodhiCableDES(config)
        results = sim.run()

        # Enrich results with SodhiCable context
        results["factory"] = "SodhiCable LLC — Wire & Cable Manufacturing"
        results["config_source"] = "Database (25 work centers, actual capacities)"
        results["stage_mapping"] = [
            {"stage": s["name"], "work_centers": s["work_centers"], "servers": s["servers"],
             "mean_service_hrs": s["mean_service"]}
            for s in config["stages"]
        ]

        return jsonify(results)
    except Exception as e:
        # Fallback with error info
        return jsonify({
            "error": str(e),
            "note": "DES engine error — check config",
        }), 500


@bp.route("/api/des/config")
def des_config():
    """Return the actual SodhiCable factory configuration for DES."""
    from db import get_db
    db = get_db()
    config = _build_sodhicable_config({}, db)
    return jsonify({
        "stages": config["stages"],
        "total_servers": sum(s["servers"] for s in config["stages"]),
        "factory": "SodhiCable LLC",
    })


@bp.route("/api/des/queueing")
def queueing():
    model = request.args.get("model", "mm1")
    lam = float(request.args.get("lam", 0.3))
    mu = float(request.args.get("mu", 0.5))

    try:
        from engines.des_engine import QueueingAnalytics
        qa = QueueingAnalytics()
        if model == "mm1":
            result = qa.mm1(lam, mu)
        elif model == "mmc":
            c = int(request.args.get("c", 2))
            result = qa.mmc(lam, mu, c)
        elif model == "mg1":
            sigma = float(request.args.get("sigma", 0.5))
            result = qa.mg1(lam, mu, sigma)
        else:
            return jsonify({"error": f"Unknown model: {model}"}), 400
        result["model"] = model
        return jsonify(result)
    except Exception:
        if mu <= lam:
            return jsonify({"error": "System unstable: lambda >= mu"}), 400
        rho = lam / mu
        lq = rho ** 2 / (1 - rho)
        wq = lq / lam
        return jsonify({
            "note": "Engine not loaded – analytical M/M/1",
            "model": model, "rho": round(rho, 4),
            "Lq": round(lq, 4), "Wq": round(wq, 4),
            "L": round(lq + rho, 4), "W": round(wq + 1/mu, 4),
        })


# ---------------------------------------------------------------------------
# GET /api/des/stream
# SSE endpoint — streams DES events in real-time
# ---------------------------------------------------------------------------

@bp.route("/api/des/stream")
def des_stream():
    """Server-Sent Events endpoint that runs a short DES simulation and
    streams ARRIVE / START / END events in real-time.

    Connect from the browser with:
        const src = new EventSource("/api/des/stream");
        src.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    import json
    import time
    import random
    from flask import Response, stream_with_context

    n_jobs = int(request.args.get("n_jobs", 8))
    arrival_rate = float(request.args.get("arrival_rate", 0.3))
    seed = int(request.args.get("seed", 42))

    stages = ["COMPOUND", "DRAW", "EXTRUDE", "ASSEMBLY", "JACKET", "TEST", "CUT-PACK"]

    def generate():
        rng = random.Random(seed)
        clock = 0.0

        for job_id in range(1, n_jobs + 1):
            # Inter-arrival time (exponential)
            inter_arrival = rng.expovariate(arrival_rate)
            clock += inter_arrival

            # ARRIVE event
            event = {
                "event_type": "ARRIVE",
                "job_id": f"JOB-{job_id:03d}",
                "stage": stages[0],
                "timestamp": round(clock, 3),
            }
            yield f"data: {json.dumps(event)}\n\n"
            time.sleep(0.15)

            # Process through each stage
            for stage in stages:
                # Service time (exponential, mean ~1.5 hrs)
                service_time = rng.expovariate(1.0 / 1.5)

                # START event
                start_event = {
                    "event_type": "START",
                    "job_id": f"JOB-{job_id:03d}",
                    "stage": stage,
                    "timestamp": round(clock, 3),
                }
                yield f"data: {json.dumps(start_event)}\n\n"
                time.sleep(0.10)

                clock += service_time

                # END event
                end_event = {
                    "event_type": "END",
                    "job_id": f"JOB-{job_id:03d}",
                    "stage": stage,
                    "timestamp": round(clock, 3),
                }
                yield f"data: {json.dumps(end_event)}\n\n"
                time.sleep(0.10)

        # Final done marker
        yield f"data: {json.dumps({'event_type': 'DONE', 'total_jobs': n_jobs, 'final_clock': round(clock, 3)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
