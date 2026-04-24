"""
SodhiCable MES v4.0 — Real-Time Factory Simulation Engine

Wraps DES engine for step-by-step SSE streaming with scripted failure injection.
Runs in a background thread, pushes events to a thread-safe queue.
"""
import threading
import queue
import json
import time
import random
import sqlite3
from datetime import datetime

# Thread-safe event queue for SSE streaming
simulation_queue = queue.Queue(maxsize=1000)
simulation_running = False
simulation_thread = None
simulation_config = {
    "speed_ms": 500,
    "dispatch_rule": "FIFO",
    "n_jobs": 50,
    "arrival_rate": 0.30,
    "breakdown_rate": 0.02,
    "inject_failures": True,
}

# Default 8-stage factory
STAGES = [
    # Actual SodhiCable WCs with realistic service times (hrs per 1 KFT job)
    {"name": "COMPOUND-1", "servers": 1, "mean_service": 2.0},    # 500 ft/hr → 2.0 hrs/KFT
    {"name": "DRAW-1", "servers": 1, "mean_service": 0.2},        # 5000 ft/hr → 0.2 hrs/KFT
    {"name": "CV-1", "servers": 2, "mean_service": 2.5},          # CV-1(400)+CV-2(3000) → ~2.5 avg
    {"name": "BRAID-1", "servers": 2, "mean_service": 4.0},       # 200-300 ft/hr → 4.0 hrs/KFT
    {"name": "CABLE-1", "servers": 2, "mean_service": 2.9},       # 350 ft/hr → 2.9 hrs/KFT
    {"name": "PLCV-1", "servers": 1, "mean_service": 2.0},        # 500 ft/hr → 2.0 hrs/KFT
    {"name": "TEST-1", "servers": 2, "mean_service": 2.0},        # 500 ft/hr → 2.0 hrs/KFT
    {"name": "CUT-1", "servers": 1, "mean_service": 0.67},        # 1500 ft/hr → 0.67 hrs/KFT
]

# Scripted failure scenarios
SCRIPTED_FAILURES = [
    {"time": 15.0, "type": "spark_fail", "wc": "TEST-1",
     "description": "Spark test FAIL on CV-2, Reel R-4521 at 1,247 ft",
     "mesa_chain": ["F5", "F7", "F8", "F10"]},
    {"time": 25.0, "type": "cusum_drift", "wc": "DRAW-1",
     "description": "CUSUM detects sustained wire diameter drift on DRAW-1",
     "mesa_chain": ["F5", "F8", "F9"]},
    {"time": 35.0, "type": "spc_ooc", "wc": "CV-1",
     "description": "SPC out-of-control: insulation thickness beyond UCL",
     "mesa_chain": ["F7", "F8"]},
]


def _push_event(event_type, wc_id, job_id, sim_time, details, db_path=None):
    """Push event to SSE queue and optionally to database."""
    event = {
        "event_type": event_type,
        "wc_id": wc_id,
        "job_id": job_id,
        "sim_time": round(sim_time, 2),
        "wall_time": datetime.now().isoformat(),
        "details": details,
    }
    try:
        simulation_queue.put_nowait(event)
    except queue.Full:
        pass  # Drop oldest events if queue full

    if db_path:
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO simulation_events (simulation_run_id, event_type, wc_id, job_id, event_time, details) VALUES (?, ?, ?, ?, ?, ?)",
                ("run-" + datetime.now().strftime("%H%M%S"), event_type, wc_id, job_id, sim_time, json.dumps(details))
            )
            conn.execute(
                "INSERT OR REPLACE INTO simulation_state (wc_id, status, current_job, queue_length, last_updated) VALUES (?, ?, ?, ?, datetime('now'))",
                (wc_id, details.get("status", "running"), job_id, details.get("queue_length", 0))
            )
            # Write to operational tables so dashboards update in real-time
            _write_operational(conn, event_type, wc_id, job_id, details)
            conn.commit()
            conn.close()
        except Exception:
            pass


def _write_operational(conn, event_type, wc_id, job_id, details):
    """Mirror simulation events to operational tables for live dashboard integration."""
    try:
        if event_type == "job_complete":
            a = round(random.uniform(0.80, 0.96), 3)
            p = round(random.uniform(0.82, 0.95), 3)
            q = round(random.uniform(0.95, 0.99), 3)
            oee = round(a * p * q, 3)
            output = random.randint(500, 3000)
            scrap = int(output * (1 - q))
            conn.execute(
                """INSERT INTO shift_reports (shift_date, shift_code, wc_id,
                   oee_availability, oee_performance, oee_quality, oee_overall,
                   total_output_ft, total_scrap_ft, total_downtime_min)
                   VALUES (DATE('now'), 'Day', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (wc_id, a, p, q, oee, output, scrap, random.randint(5, 30)))

        elif event_type == "breakdown":
            conn.execute(
                "INSERT INTO downtime_log (wc_id, start_time, duration_min, category, cause) VALUES (?, datetime('now'), ?, 'Breakdown', ?)",
                (wc_id, random.randint(15, 120), details.get("reason", "Sim breakdown")))

        elif event_type in ("spark_fail", "scripted_failure"):
            conn.execute(
                "INSERT INTO spark_test_log (wc_id, wo_id, voltage_kv, result, footage_at_fault_ft, timestamp) VALUES (?, ?, ?, 'FAIL', ?, datetime('now'))",
                (wc_id, job_id, round(random.uniform(2.0, 4.0), 1), random.randint(100, 2000)))
            conn.execute(
                "INSERT INTO process_deviations (wc_id, wo_id, parameter_name, detection_method, deviation_value, setpoint_value, severity) VALUES (?, ?, 'SparkTest', 'Threshold', 0, 1, 'Critical')",
                (wc_id, job_id))

        elif event_type in ("job_start", "processing"):
            # Generate sensor readings for this WC
            profiles = {
                'CV-1': [('Temperature_F', 365, 3), ('Tension_lbf', 25, 2)],
                'CV-2': [('Temperature_F', 355, 3.5)],
                'DRAW-1': [('Tension_lbf', 45, 3), ('LineSpeed_fpm', 800, 25)],
                'PLCV-1': [('Temperature_F', 370, 3.5)],
                'STRAND-1': [('Tension_lbf', 35, 3)],
                'TEST-1': [('LineSpeed_fpm', 500, 20)],
            }
            for param, mu, sigma in profiles.get(wc_id, []):
                val = round(random.gauss(mu, sigma), 2)
                flag = 'Bad' if abs(val - mu) > 3 * sigma else 'Suspect' if abs(val - mu) > 2 * sigma else 'Good'
                conn.execute(
                    "INSERT INTO process_data_live (wc_id, parameter, value, quality_flag) VALUES (?, ?, ?, ?)",
                    (wc_id, param, val, flag))
    except Exception:
        pass  # Don't let operational writes crash the simulation


def _run_simulation(db_path):
    """Main simulation loop — runs in background thread."""
    global simulation_running
    random.seed(42)

    config = simulation_config.copy()
    speed_ms = config.get("speed_ms", 500)
    n_jobs = config.get("n_jobs", 50)
    inject = config.get("inject_failures", True)

    # Initialize stage state
    stage_state = {}
    for s in STAGES:
        stage_state[s["name"]] = {
            "status": "idle", "busy_until": 0, "queue": [],
            "completed": 0, "total_busy": 0, "servers": s["servers"],
            "mean_service": s["mean_service"],
        }

    # Generate job arrivals
    sim_time = 0.0
    jobs_completed = []
    failure_idx = 0

    _push_event("sim_start", "SYSTEM", None, 0, {"message": "Simulation started", "n_jobs": n_jobs}, db_path)

    for job_num in range(n_jobs):
        if not simulation_running:
            break

        job_id = f"JOB-{job_num+1:03d}"
        interarrival = random.expovariate(config.get("arrival_rate", 0.30))
        sim_time += interarrival

        # Check for scripted failures
        if inject:
            while failure_idx < len(SCRIPTED_FAILURES) and sim_time >= SCRIPTED_FAILURES[failure_idx]["time"]:
                fail = SCRIPTED_FAILURES[failure_idx]
                _push_event("failure", fail["wc"], None, sim_time, {
                    "status": "breakdown",
                    "failure_type": fail["type"],
                    "description": fail["description"],
                    "mesa_chain": fail["mesa_chain"],
                    "queue_length": len(stage_state.get(fail["wc"], {}).get("queue", [])),
                }, db_path)
                # Update stage state
                if fail["wc"] in stage_state:
                    stage_state[fail["wc"]]["status"] = "breakdown"
                time.sleep(speed_ms / 1000.0)
                # Repair after brief delay
                _push_event("repair", fail["wc"], None, sim_time + 0.5, {
                    "status": "running",
                    "description": f"{fail['wc']} repaired and back online",
                    "queue_length": len(stage_state.get(fail["wc"], {}).get("queue", [])),
                }, db_path)
                if fail["wc"] in stage_state:
                    stage_state[fail["wc"]]["status"] = "idle"
                failure_idx += 1

        # Process job through stages
        job_start = sim_time
        for stage in STAGES:
            if not simulation_running:
                break
            wc = stage["name"]
            st = stage_state[wc]

            # Service time
            service = max(0.1, random.expovariate(1.0 / st["mean_service"]))

            # Arrival at stage
            _push_event("arrival", wc, job_id, sim_time, {
                "status": "running",
                "queue_length": len(st["queue"]) + 1,
            }, db_path)

            # Wait in queue if busy
            if st["busy_until"] > sim_time:
                wait = st["busy_until"] - sim_time
                sim_time = st["busy_until"]
            else:
                wait = 0

            # Start service
            st["busy_until"] = sim_time + service
            st["status"] = "running"
            sim_time += service
            st["completed"] += 1
            st["total_busy"] += service

            _push_event("completion", wc, job_id, sim_time, {
                "status": "idle" if len(st["queue"]) == 0 else "running",
                "queue_length": max(0, len(st["queue"]) - 1),
                "service_time": round(service, 2),
                "wait_time": round(wait, 2),
            }, db_path)

            time.sleep(speed_ms / 1000.0)

        flow_time = sim_time - job_start
        jobs_completed.append({"job_id": job_id, "flow_time": round(flow_time, 2)})

    # End of simulation
    stage_stats = []
    total_time = sim_time if sim_time > 0 else 1
    for s in STAGES:
        st = stage_state[s["name"]]
        util = round(st["total_busy"] / total_time * 100, 1) if total_time > 0 else 0
        stage_stats.append({"wc": s["name"], "completed": st["completed"], "utilization": util})
        _push_event("stage_summary", s["name"], None, sim_time, {
            "status": "idle", "completed": st["completed"], "utilization": util, "queue_length": 0,
        }, db_path)

    avg_flow = sum(j["flow_time"] for j in jobs_completed) / len(jobs_completed) if jobs_completed else 0
    _push_event("sim_end", "SYSTEM", None, sim_time, {
        "message": "Simulation complete",
        "jobs_completed": len(jobs_completed),
        "avg_flow_time": round(avg_flow, 2),
        "stage_stats": stage_stats,
    }, db_path)

    simulation_running = False


def start_simulation(db_path=None):
    """Start simulation in background thread."""
    global simulation_running, simulation_thread
    if simulation_running:
        return {"status": "already_running"}
    simulation_running = True
    # Clear queue
    while not simulation_queue.empty():
        try:
            simulation_queue.get_nowait()
        except queue.Empty:
            break
    simulation_thread = threading.Thread(target=_run_simulation, args=(db_path,), daemon=True)
    simulation_thread.start()
    return {"status": "started"}


def stop_simulation():
    """Stop running simulation."""
    global simulation_running
    simulation_running = False
    return {"status": "stopped"}


def update_config(new_config):
    """Update simulation parameters."""
    simulation_config.update(new_config)
    return {"status": "updated", "config": simulation_config}


def get_event_stream():
    """Generator for SSE event stream."""
    while True:
        try:
            event = simulation_queue.get(timeout=30)
            yield f"data: {json.dumps(event)}\n\n"
        except queue.Empty:
            yield f"data: {json.dumps({'event_type': 'heartbeat', 'sim_time': 0})}\n\n"
