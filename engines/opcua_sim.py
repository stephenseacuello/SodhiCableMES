"""
SodhiCable MES — OPC-UA Tag Simulator + Live Event Generator

Generates continuous sensor readings AND periodic operational events:
- Sensor readings every 5 seconds (process_data_live)
- Shift reports every 60 seconds (shift_reports → OEE changes on dashboard)
- Random alarms/deviations every ~30 seconds (process_deviations, NCR)
- Occasional downtime events (downtime_log)
- Occasional scrap events (scrap_log)

This makes the entire MES feel alive — dashboards, SCADA, notifications all update.
"""
import threading
import time
import random
import sqlite3
from datetime import datetime

_running = False
_thread = None
_tick = 0  # counter for periodic events

# Sensor profiles: (parameter, mean, sigma)
PROFILES = {
    # Compounding — Banbury mixer (batch process: temperature, rotor speed, ram pressure, power draw)
    'COMPOUND-1': [('BatchTemp_F', 280, 8), ('RotorSpeed_rpm', 40, 2), ('RamPressure_psi', 85, 5), ('PowerDraw_kW', 75, 4)],
    'COMPOUND-2': [('BatchTemp_F', 275, 6), ('RotorSpeed_rpm', 38, 1.5), ('RamPressure_psi', 80, 4), ('PowerDraw_kW', 70, 3)],
    # Drawing
    'DRAW-1': [('Tension_lbf', 45, 3), ('LineSpeed_fpm', 800, 25), ('WireDiameter_in', 0.0253, 0.0003)],
    'STRAND-1': [('Tension_lbf', 35, 3), ('LineSpeed_fpm', 600, 20), ('LayLength_in', 4.5, 0.2)],
    # Extrusion / CV lines
    'CV-1': [('Temperature_F', 365, 3), ('LineSpeed_fpm', 400, 15), ('InsulationOD_in', 0.065, 0.001), ('Tension_lbf', 25, 2)],
    'CV-2': [('Temperature_F', 355, 3.5), ('LineSpeed_fpm', 3000, 50), ('Tension_lbf', 18, 1.5)],
    'CV-3': [('Temperature_F', 370, 4), ('LineSpeed_fpm', 300, 12), ('Tension_lbf', 30, 2.5)],
    # Jacketing
    'PLCV-1': [('Temperature_F', 370, 3.5), ('Tension_lbf', 35, 3), ('JacketOD_in', 0.310, 0.004)],
    'LPML-1': [('Temperature_F', 340, 3), ('Tension_lbf', 40, 3.5)],
    'PX-1': [('Temperature_F', 590, 4), ('Tension_lbf', 12, 1)],
    # Assembly
    'BRAID-1': [('LineSpeed_fpm', 200, 8)],
    'CABLE-1': [('LineSpeed_fpm', 350, 12)],
    # Testing / Finishing
    'TEST-1': [('LineSpeed_fpm', 500, 20)],
}

# Work centers for shift report generation
SHIFT_REPORT_WCS = ['COMPOUND-1', 'COMPOUND-2', 'CV-1', 'CV-2', 'CV-3', 'DRAW-1', 'STRAND-1',
                    'PLCV-1', 'LPML-1', 'PX-1', 'CABLE-1', 'CABLE-2', 'BRAID-1', 'TEST-1', 'CUT-1']

SCRAP_CAUSES = ['STARTUP', 'CHANGEOVER', 'SPARK_FAULT', 'OD_EXCURSION', 'MATERIAL_DEFECT', 'COMPOUND_BLEED']
DOWNTIME_CATS = ['Breakdown', 'Setup', 'MaterialWait', 'QualityHold', 'PM']


def _run(db_path, interval):
    global _running, _tick
    _tick = 0
    while _running:
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys = ON")

            # ── 1. Correlated sensor readings (every tick) ──────────────
            # Parameters are cross-correlated: a shared "process state" drives
            # all sensors on a WC together (speed up → temp rises, tension drops)
            for wc_id, params in PROFILES.items():
                # Shared process noise — drives correlations
                process_noise = random.gauss(0, 1)
                # Occasional sustained drift (die wear, compound viscosity)
                sustained_drift = 0.3 * (_tick % 50 - 25) / 25 if _tick % 200 < 50 and wc_id in ('DRAW-1', 'CV-1') else 0

                for i, (param, mu, sigma) in enumerate(params):
                    # Correlate: first param gets positive noise, tension gets negative
                    if 'Tension' in param:
                        corr_factor = -0.3 * process_noise  # tension inversely correlated with speed
                    elif 'Speed' in param or 'LineSpeed' in param:
                        corr_factor = 0.5 * process_noise
                    elif 'Temp' in param:
                        corr_factor = 0.4 * process_noise  # temp positively correlated with speed
                    elif 'OD' in param or 'Diameter' in param:
                        corr_factor = -0.2 * process_noise + sustained_drift  # OD drift from die wear
                    else:
                        corr_factor = 0.1 * process_noise

                    val = round(mu + corr_factor * sigma + random.gauss(0, sigma * 0.7), 4)
                    # Lowered thresholds: ~15% Suspect, ~3% Bad (realistic for a running plant)
                    flag = 'Bad' if abs(val - mu) > 2.5 * sigma else 'Suspect' if abs(val - mu) > 1.5 * sigma else 'Good'
                    # Stagger timestamps so readings don't all share the same second
                    ts_offset = i * 0.3  # 300ms between parameters on same WC
                    ts = datetime.now() + __import__('datetime').timedelta(seconds=ts_offset)
                    conn.execute(
                        "INSERT INTO process_data_live (wc_id, parameter, value, timestamp, quality_flag) VALUES (?,?,?,?,?)",
                        (wc_id, param, val, ts.strftime("%Y-%m-%d %H:%M:%S"), flag))

            # ── 2. Shift reports (every 6 ticks = ~30s) ───────────────
            if _tick > 0 and _tick % 6 == 0:
                wc = random.choice(SHIFT_REPORT_WCS)
                a = round(random.uniform(0.78, 0.96), 3)
                p = round(random.uniform(0.80, 0.95), 3)
                q = round(random.uniform(0.94, 0.99), 3)
                oee = round(a * p * q, 3)
                output = random.randint(400, 3500)
                scrap = int(output * (1 - q))
                dt_min = int((1 - a) * 480)
                shift = random.choice(['Day', 'Swing', 'Night'])
                conn.execute(
                    """INSERT INTO shift_reports (shift_date, shift_code, wc_id,
                       oee_availability, oee_performance, oee_quality, oee_overall,
                       total_output_ft, total_scrap_ft, total_downtime_min)
                       VALUES (DATE('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (shift, wc, a, p, q, oee, output, scrap, dt_min))

            # ── 3. Random alarm/deviation (every 4 ticks = ~20s) ──────
            if _tick > 0 and _tick % 4 == 0 and random.random() < 0.6:
                wc = random.choice(list(PROFILES.keys()))
                param = random.choice(PROFILES[wc])[0]
                severity = random.choice(['Warning', 'Warning', 'Minor', 'Minor', 'Major', 'Critical'])
                val = round(random.gauss(100, 15), 2)
                sp = 100
                method = random.choice(['Threshold', 'CUSUM', 'EWMA'])
                conn.execute(
                    """INSERT INTO process_deviations
                       (wc_id, parameter_name, detection_method, deviation_value,
                        setpoint_value, severity, corrective_action)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (wc, param, method, val, sp, severity,
                     'PID auto-corrected' if severity == 'Warning' else 'Operator notified'))

                # Major/Critical → auto-create NCR
                if severity in ('Major', 'Critical'):
                    conn.execute(
                        "INSERT INTO ncr (description, severity, detected_at, status) VALUES (?,?,?,'Open')",
                        (f"Auto-NCR: {param} {severity} on {wc}", severity, wc))

                # Critical → auto-hold
                if severity == 'Critical':
                    wo = conn.execute("SELECT wo_id FROM work_orders WHERE status='InProcess' LIMIT 1").fetchone()
                    if wo:
                        conn.execute(
                            "INSERT INTO hold_release (wo_id, hold_reason, hold_status) VALUES (?,?,'Active')",
                            (wo[0], f"Critical: {param} on {wc}"))

            # ── 4. Random downtime (every 10 ticks = ~50s) ──────────
            if _tick > 0 and _tick % 10 == 0 and random.random() < 0.5:
                wc = random.choice(SHIFT_REPORT_WCS)
                cat = random.choice(DOWNTIME_CATS)
                dur = random.randint(5, 45)
                conn.execute(
                    "INSERT INTO downtime_log (wc_id, start_time, duration_min, category, cause) VALUES (?, datetime('now'), ?, ?, ?)",
                    (wc, dur, cat, f"Sim: {cat} event on {wc}"))

            # ── 5. Random scrap (every 8 ticks = ~40s) ────────────────
            if _tick > 0 and _tick % 8 == 0 and random.random() < 0.5:
                wc = random.choice(['CV-1', 'CV-2', 'CV-3', 'PLCV-1', 'DRAW-1'])
                cause = random.choice(SCRAP_CAUSES)
                qty = random.randint(50, 500)
                conn.execute(
                    "INSERT INTO scrap_log (wc_id, cause_code, quantity_ft, disposition) VALUES (?, ?, ?, 'Scrap')",
                    (wc, cause, qty))

            # ── 6. WO progression (every 12 ticks = ~60s) ──────────────
            # Slowly move work orders through their routing
            if _tick > 0 and _tick % 12 == 0:
                # Complete next pending operation on a random InProcess WO
                next_op = conn.execute("""
                    SELECT o.operation_id, o.wo_id, o.wc_id, o.step_sequence,
                           wo.order_qty_kft
                    FROM operations o
                    JOIN work_orders wo ON wo.wo_id = o.wo_id
                    WHERE o.status = 'Pending' AND wo.status = 'InProcess'
                    ORDER BY RANDOM() LIMIT 1
                """).fetchone()
                if next_op:
                    qty = (next_op["order_qty_kft"] or 1) * 1000
                    good = int(qty * random.uniform(0.95, 0.99))
                    scrap = int(qty - good)
                    conn.execute(
                        "UPDATE operations SET status='Complete', qty_good=?, qty_scrap=?, actual_end=datetime('now') WHERE operation_id=?",
                        (good, scrap, next_op["operation_id"]))

                    # Update SCADA simulation_state so the WC shows as running this job
                    conn.execute(
                        "INSERT OR REPLACE INTO simulation_state (wc_id, status, current_job, queue_length, last_updated) VALUES (?, 'running', ?, 1, datetime('now'))",
                        (next_op["wc_id"], next_op["wo_id"]))

                    # Check if all operations for this WO are complete
                    remaining = conn.execute(
                        "SELECT COUNT(*) AS c FROM operations WHERE wo_id=? AND status != 'Complete'",
                        (next_op["wo_id"],)).fetchone()["c"]
                    if remaining == 0:
                        conn.execute(
                            "UPDATE work_orders SET status='Complete', actual_end=datetime('now') WHERE wo_id=?",
                            (next_op["wo_id"],))
                        # Set WC to idle when job finishes
                        conn.execute(
                            "INSERT OR REPLACE INTO simulation_state (wc_id, status, current_job, queue_length, last_updated) VALUES (?, 'idle', NULL, 0, datetime('now'))",
                            (next_op["wc_id"],))

            # ── 7. Start new WO (every 24 ticks = ~120s) ─────────────
            if _tick > 0 and _tick % 24 == 0:
                pending = conn.execute(
                    "SELECT wo_id FROM work_orders WHERE status='Pending' ORDER BY priority ASC, due_date ASC LIMIT 1"
                ).fetchone()
                if pending:
                    conn.execute(
                        "UPDATE work_orders SET status='InProcess', actual_start=datetime('now') WHERE wo_id=?",
                        (pending["wo_id"],))
                    # Start first operation
                    first_op = conn.execute(
                        "SELECT operation_id FROM operations WHERE wo_id=? ORDER BY step_sequence ASC LIMIT 1",
                        (pending["wo_id"],)).fetchone()
                    if first_op:
                        conn.execute(
                            "UPDATE operations SET status='InProcess', actual_start=datetime('now') WHERE operation_id=?",
                            (first_op["operation_id"],))

            conn.commit()
            conn.close()
            _tick += 1
        except Exception:
            pass
        time.sleep(interval)


def start(db_path, interval=5):
    global _running, _thread, _tick
    if _running:
        return False
    _running = True
    _tick = 0
    _thread = threading.Thread(target=_run, args=(db_path, interval), daemon=True)
    _thread.start()
    return True


def stop():
    global _running
    _running = False
    return True


def is_running():
    return _running
