"""ISA-95 Cross-Level (L2-L4): AI/ML intelligence layer, proposed MESA F12.

SodhiCable MES — AI / ML Insights Blueprint
Demonstrates AI as a potential 12th MESA function layer using pure Python
statistics (z-score anomaly detection, exponential failure model, correlation-
based quality risk, and a rules-based recommendation engine).

No external AI/ML libraries -- only stdlib: statistics, math, collections, datetime.
"""
import math
import statistics
from collections import defaultdict
from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, jsonify, request
from utils.cache import cached

bp = Blueprint("ai", __name__)


# ---------------------------------------------------------------------------
# Page route
# ---------------------------------------------------------------------------

@bp.route("/ai")
def ai_page():
    return render_template("ai.html")


# ---------------------------------------------------------------------------
# Helper: safe float parsing
# ---------------------------------------------------------------------------

def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# GET /api/ai/anomalies
# Z-score anomaly detection on process_data_live
# ---------------------------------------------------------------------------

@bp.route("/api/ai/anomalies")
@cached(ttl=60)
def anomalies():
    from db import get_db
    db = get_db()

    rows = db.execute("""
        SELECT wc_id, parameter, value, timestamp, quality_flag
        FROM process_data_live
        ORDER BY wc_id, parameter, timestamp
    """).fetchall()

    # Group values by (wc_id, parameter)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["wc_id"], r["parameter"])].append(dict(r))

    anomalies_list = []

    for (wc_id, param), readings in groups.items():
        values = [_safe_float(r["value"]) for r in readings]
        if len(values) < 5:
            continue  # need enough data for meaningful stats

        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        if stdev == 0:
            continue  # no variation — nothing anomalous

        for r in readings:
            v = _safe_float(r["value"])
            z = (v - mean) / stdev
            abs_z = abs(z)
            if abs_z > 2.5:
                severity = "Critical" if abs_z > 3.0 else "Warning"
                anomalies_list.append({
                    "wc_id": wc_id,
                    "parameter": param,
                    "value": round(v, 4),
                    "timestamp": r["timestamp"],
                    "z_score": round(z, 3),
                    "abs_z": round(abs_z, 3),
                    "mean": round(mean, 4),
                    "stdev": round(stdev, 4),
                    "severity": severity,
                })

    # Sort by |z_score| descending and limit to 50
    anomalies_list.sort(key=lambda a: a["abs_z"], reverse=True)
    return jsonify(anomalies_list[:50])


# ---------------------------------------------------------------------------
# GET /api/ai/quality_predictions
# Correlate process deviations to scrap outcomes per work center
# ---------------------------------------------------------------------------

@bp.route("/api/ai/quality_predictions")
def quality_predictions():
    from db import get_db
    db = get_db()

    # Scrap totals per WC
    scrap_rows = db.execute("""
        SELECT wc_id, SUM(quantity_ft) AS total_scrap, COUNT(*) AS scrap_events
        FROM scrap_log
        WHERE wc_id IS NOT NULL
        GROUP BY wc_id
    """).fetchall()
    scrap_by_wc = {r["wc_id"]: dict(r) for r in scrap_rows}

    # Total output per WC from shift_reports (denominator for scrap rate)
    output_rows = db.execute("""
        SELECT wc_id, SUM(total_output_ft) AS total_output
        FROM shift_reports
        WHERE wc_id IS NOT NULL
        GROUP BY wc_id
    """).fetchall()
    output_by_wc = {r["wc_id"]: _safe_float(r["total_output"], 1) for r in output_rows}

    # Process deviations with setpoints
    dev_rows = db.execute("""
        SELECT wc_id, parameter_name, deviation_value, setpoint_value
        FROM process_deviations
        WHERE setpoint_value IS NOT NULL AND setpoint_value != 0
    """).fetchall()

    # Group deviations by WC
    dev_by_wc = defaultdict(list)
    for r in dev_rows:
        dev_by_wc[r["wc_id"]].append(dict(r))

    # Also pull average parameter values from process_data_live
    param_rows = db.execute("""
        SELECT wc_id, parameter, AVG(value) AS avg_value
        FROM process_data_live
        GROUP BY wc_id, parameter
    """).fetchall()
    params_by_wc = defaultdict(list)
    for r in param_rows:
        params_by_wc[r["wc_id"]].append({
            "param": r["parameter"],
            "avg_value": round(_safe_float(r["avg_value"]), 4),
        })

    # Build quality predictions for WCs that have both process data and scrap
    results = []
    all_wcs = set(list(scrap_by_wc.keys()) + list(dev_by_wc.keys()))

    for wc_id in all_wcs:
        scrap_info = scrap_by_wc.get(wc_id, {})
        total_scrap = _safe_float(scrap_info.get("total_scrap", 0))
        total_output = output_by_wc.get(wc_id, 0)
        scrap_rate = (total_scrap / total_output * 100) if total_output > 0 else 0

        # Compute average deviation percentage from setpoints
        devs = dev_by_wc.get(wc_id, [])
        param_details = []
        total_dev_pct = 0
        for d in devs:
            sp = _safe_float(d.get("setpoint_value", 0))
            dv = _safe_float(d.get("deviation_value", 0))
            if sp != 0:
                dev_pct = abs(dv - sp) / abs(sp) * 100
                total_dev_pct += dev_pct
                param_details.append({
                    "param": d.get("parameter_name", ""),
                    "deviation_value": round(dv, 4),
                    "setpoint": round(sp, 4),
                    "deviation_pct": round(dev_pct, 2),
                })

        avg_dev_pct = total_dev_pct / len(devs) if devs else 0

        # Risk score: combines deviation magnitude with scrap rate
        risk_score = (avg_dev_pct / 100) * (scrap_rate / 100) * 100
        if risk_score == 0 and scrap_rate > 0:
            risk_score = scrap_rate * 0.1  # baseline risk from scrap alone

        results.append({
            "wc_id": wc_id,
            "parameters": sorted(param_details, key=lambda p: p["deviation_pct"], reverse=True)[:5],
            "process_params": params_by_wc.get(wc_id, []),
            "scrap_qty": round(total_scrap, 1),
            "scrap_events": scrap_info.get("scrap_events", 0),
            "total_output": round(total_output, 1),
            "scrap_rate": round(scrap_rate, 2),
            "avg_deviation_pct": round(avg_dev_pct, 2),
            "risk_score": round(risk_score, 4),
        })

    results.sort(key=lambda r: r["risk_score"], reverse=True)
    return jsonify(results)


# ---------------------------------------------------------------------------
# GET /api/ai/maintenance_predictions
# Exponential failure model: P(fail) = 1 - exp(-t / MTBF)
# ---------------------------------------------------------------------------

@bp.route("/api/ai/maintenance_predictions")
def maintenance_predictions():
    from db import get_db
    db = get_db()

    equipment_rows = db.execute("""
        SELECT e.equipment_id, e.equipment_code, e.description,
               e.work_center_id, e.last_pm_date, e.next_pm_date, e.status
        FROM equipment e
        ORDER BY e.equipment_id
    """).fetchall()

    # Maintenance history per equipment
    maint_rows = db.execute("""
        SELECT equipment_id, completed_date
        FROM maintenance
        WHERE completed_date IS NOT NULL
        ORDER BY equipment_id, completed_date
    """).fetchall()

    maint_by_equip = defaultdict(list)
    for r in maint_rows:
        maint_by_equip[r["equipment_id"]].append(r["completed_date"])

    today = date.today()
    results = []

    for eq in equipment_rows:
        eq_id = eq["equipment_id"]
        last_pm_str = eq["last_pm_date"]
        next_pm_str = eq["next_pm_date"]

        # Days since last PM
        days_since_pm = 30  # default fallback
        if last_pm_str:
            try:
                last_pm = datetime.strptime(last_pm_str[:10], "%Y-%m-%d").date()
                days_since_pm = max((today - last_pm).days, 0)
            except (ValueError, TypeError):
                pass

        # PM overdue?
        pm_overdue = False
        if next_pm_str:
            try:
                next_pm = datetime.strptime(next_pm_str[:10], "%Y-%m-%d").date()
                pm_overdue = next_pm < today
            except (ValueError, TypeError):
                pass

        # Estimate MTBF from maintenance history
        dates = maint_by_equip.get(eq_id, [])
        mtbf_days = 45  # default if insufficient data
        if len(dates) >= 2:
            parsed = []
            for d in dates:
                try:
                    parsed.append(datetime.strptime(d[:10], "%Y-%m-%d").date())
                except (ValueError, TypeError):
                    continue
            parsed.sort()
            if len(parsed) >= 2:
                intervals = [(parsed[i + 1] - parsed[i]).days
                             for i in range(len(parsed) - 1)
                             if (parsed[i + 1] - parsed[i]).days > 0]
                if intervals:
                    mtbf_days = statistics.mean(intervals)

        # Exponential failure probability
        if mtbf_days > 0:
            failure_prob = 1.0 - math.exp(-days_since_pm / mtbf_days)
        else:
            failure_prob = 0.0

        # Risk level
        if failure_prob > 0.7:
            risk_level = "Critical"
        elif failure_prob > 0.4:
            risk_level = "Warning"
        else:
            risk_level = "OK"

        # Cost-of-delay estimate (qualitative based on risk)
        if failure_prob > 0.7:
            cost_of_delay = "High — unplanned downtime likely"
        elif failure_prob > 0.4:
            cost_of_delay = "Medium — schedule PM soon"
        else:
            cost_of_delay = "Low — within PM window"

        results.append({
            "equipment_id": eq_id,
            "equipment_code": eq["equipment_code"],
            "description": eq["description"],
            "work_center_id": eq["work_center_id"],
            "status": eq["status"],
            "last_pm_date": last_pm_str,
            "next_pm_date": next_pm_str,
            "pm_overdue": pm_overdue,
            "days_since_pm": days_since_pm,
            "mtbf_days": round(mtbf_days, 1),
            "failure_probability": round(failure_prob, 4),
            "failure_pct": round(failure_prob * 100, 1),
            "risk_level": risk_level,
            "cost_of_delay": cost_of_delay,
            "maint_records": len(dates),
        })

    results.sort(key=lambda r: r["failure_probability"], reverse=True)
    return jsonify(results)


# ---------------------------------------------------------------------------
# GET /api/ai/recommendations
# Rules-based recommendation engine synthesizing all data sources
# ---------------------------------------------------------------------------

@bp.route("/api/ai/recommendations")
@cached(ttl=60)
def recommendations():
    from db import get_db
    db = get_db()

    recs = []
    today = date.today()

    # -----------------------------------------------------------------------
    # Rule 1: High scrap work centers (scrap rate > 5%)
    # -----------------------------------------------------------------------
    scrap_rows = db.execute("""
        SELECT sl.wc_id,
               SUM(sl.quantity_ft) AS total_scrap,
               sr.total_output
        FROM scrap_log sl
        LEFT JOIN (
            SELECT wc_id, SUM(total_output_ft) AS total_output
            FROM shift_reports GROUP BY wc_id
        ) sr ON sl.wc_id = sr.wc_id
        WHERE sl.wc_id IS NOT NULL
        GROUP BY sl.wc_id
    """).fetchall()

    for r in scrap_rows:
        total_output = _safe_float(r["total_output"], 1)
        total_scrap = _safe_float(r["total_scrap"], 0)
        rate = (total_scrap / total_output * 100) if total_output > 0 else 0
        if rate > 5:
            recs.append({
                "type": "quality",
                "priority": 1,
                "title": f"High scrap rate at {r['wc_id']}",
                "detail": (f"Scrap rate {rate:.1f}% exceeds 5% threshold "
                           f"({total_scrap:.0f} ft scrap / {total_output:.0f} ft output). "
                           f"Investigate root cause — review SPC, material lots, and operator logs."),
                "mesa_functions": ["F5", "F7", "F8", "F10"],
                "affected_wc": r["wc_id"],
            })

    # -----------------------------------------------------------------------
    # Rule 2: CUSUM drift — unresolved deviations
    # -----------------------------------------------------------------------
    cusum_rows = db.execute("""
        SELECT wc_id, parameter_name, deviation_value, setpoint_value, severity
        FROM process_deviations
        WHERE detection_method = 'CUSUM' AND resolved = 0
    """).fetchall()

    for r in cusum_rows:
        recs.append({
            "type": "process",
            "priority": 2,
            "title": f"CUSUM drift on {r['wc_id']} / {r['parameter_name']}",
            "detail": (f"CUSUM drift detected — current value {r['deviation_value']} vs "
                       f"setpoint {r['setpoint_value']} ({r['severity']} severity). "
                       f"Likely cause: die wear, material variation, or calibration drift."),
            "mesa_functions": ["F5", "F7", "F8"],
            "affected_wc": r["wc_id"],
        })

    # -----------------------------------------------------------------------
    # Rule 3: Overdue PM
    # -----------------------------------------------------------------------
    overdue_rows = db.execute("""
        SELECT equipment_code, work_center_id, next_pm_date, last_pm_date
        FROM equipment
        WHERE next_pm_date IS NOT NULL AND next_pm_date < ?
    """, (today.isoformat(),)).fetchall()

    for r in overdue_rows:
        last_pm = r["last_pm_date"] or "unknown"
        days_overdue = 0
        try:
            next_pm = datetime.strptime(r["next_pm_date"][:10], "%Y-%m-%d").date()
            days_overdue = (today - next_pm).days
        except (ValueError, TypeError):
            pass
        recs.append({
            "type": "maintenance",
            "priority": 2,
            "title": f"PM overdue on {r['equipment_code']}",
            "detail": (f"Preventive maintenance overdue by {days_overdue} day(s) "
                       f"(due {r['next_pm_date']}, last PM {last_pm}). "
                       f"Schedule immediately to avoid unplanned downtime."),
            "mesa_functions": ["F1", "F9"],
            "affected_wc": r["work_center_id"],
        })

    # -----------------------------------------------------------------------
    # Rule 4: Low Cpk (< 1.33)
    # -----------------------------------------------------------------------
    spc_rows = db.execute("""
        SELECT wc_id, parameter_name, measured_value, usl, lsl
        FROM spc_readings
        WHERE measured_value IS NOT NULL AND usl IS NOT NULL AND lsl IS NOT NULL
    """).fetchall()

    cpk_groups = defaultdict(list)
    cpk_limits = {}
    for r in spc_rows:
        key = (r["wc_id"], r["parameter_name"])
        cpk_groups[key].append(_safe_float(r["measured_value"]))
        if key not in cpk_limits:
            cpk_limits[key] = (r["usl"], r["lsl"])

    for (wc_id, param), values in cpk_groups.items():
        if len(values) < 10:
            continue
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        if stdev == 0:
            continue
        usl, lsl = cpk_limits[(wc_id, param)]
        usl_f = _safe_float(usl)
        lsl_f = _safe_float(lsl)
        if usl_f == 0 and lsl_f == 0:
            continue
        cpu = (usl_f - mean) / (3 * stdev) if usl_f else 999
        cpl = (mean - lsl_f) / (3 * stdev) if lsl_f else 999
        cpk = min(cpu, cpl)
        if cpk < 1.33:
            recs.append({
                "type": "quality",
                "priority": 3 if cpk >= 1.0 else 2,
                "title": f"Low Cpk at {wc_id} / {param}",
                "detail": (f"Process capability Cpk = {cpk:.2f} is below 1.33 target "
                           f"(mean={mean:.4f}, sigma={stdev:.4f}, USL={usl_f}, LSL={lsl_f}). "
                           f"Tighten process controls or widen specifications."),
                "mesa_functions": ["F7", "F8", "F11"],
                "affected_wc": wc_id,
            })

    # -----------------------------------------------------------------------
    # Rule 5: Cert expiring within 30 days
    # -----------------------------------------------------------------------
    cutoff = (today + timedelta(days=30)).isoformat()
    cert_rows = db.execute("""
        SELECT COUNT(*) AS cnt
        FROM personnel_certs
        WHERE expiry_date IS NOT NULL
          AND expiry_date <= ?
          AND status = 'Active'
    """, (cutoff,)).fetchone()
    cert_count = cert_rows["cnt"] if cert_rows else 0
    if cert_count > 0:
        recs.append({
            "type": "labor",
            "priority": 3,
            "title": f"Operator certifications expiring ({cert_count})",
            "detail": (f"{cert_count} personnel certification(s) expiring within 30 days. "
                       f"Schedule re-certification to maintain compliance and avoid "
                       f"production disruptions."),
            "mesa_functions": ["F1", "F6"],
            "affected_wc": "All",
        })

    # -----------------------------------------------------------------------
    # Rule 6: OEE declining (last 7 days avg < previous 7 days)
    # -----------------------------------------------------------------------
    oee_rows = db.execute("""
        SELECT shift_date, AVG(oee_overall) AS avg_oee
        FROM shift_reports
        WHERE oee_overall IS NOT NULL
        GROUP BY shift_date
        ORDER BY shift_date DESC
        LIMIT 14
    """).fetchall()

    if len(oee_rows) >= 10:
        recent_7 = [_safe_float(r["avg_oee"]) for r in oee_rows[:7]]
        prev_7 = [_safe_float(r["avg_oee"]) for r in oee_rows[7:14]]
        if recent_7 and prev_7:
            recent_avg = statistics.mean(recent_7)
            prev_avg = statistics.mean(prev_7)
            if recent_avg < prev_avg:
                drop = prev_avg - recent_avg
                recs.append({
                    "type": "performance",
                    "priority": 3,
                    "title": "OEE trend declining",
                    "detail": (f"Average OEE dropped from {prev_avg:.1f}% to {recent_avg:.1f}% "
                               f"(7-day rolling average, -{drop:.1f} pp). "
                               f"Investigate availability losses, speed losses, and quality rejects."),
                    "mesa_functions": ["F8", "F9", "F11"],
                    "affected_wc": "All",
                })

    # -----------------------------------------------------------------------
    # Rule 7: Unresolved process deviations (any method) — bonus rule
    # -----------------------------------------------------------------------
    unresolved = db.execute("""
        SELECT COUNT(*) AS cnt FROM process_deviations WHERE resolved = 0
    """).fetchone()
    unresolved_cnt = unresolved["cnt"] if unresolved else 0
    if unresolved_cnt > 3:
        recs.append({
            "type": "process",
            "priority": 4,
            "title": f"{unresolved_cnt} unresolved process deviations",
            "detail": (f"There are {unresolved_cnt} open process deviations across the plant. "
                       f"Prioritize investigation and corrective actions to prevent "
                       f"quality escapes."),
            "mesa_functions": ["F7", "F8"],
            "affected_wc": "Multiple",
        })

    # Sort by priority (1 = highest)
    recs.sort(key=lambda r: r["priority"])
    return jsonify(recs)


# ---------------------------------------------------------------------------
# GET /api/ai/summary
# Aggregate dashboard KPIs for the AI page header cards
# ---------------------------------------------------------------------------

@bp.route("/api/ai/summary")
def summary():
    from db import get_db
    db = get_db()

    today = date.today()

    # Anomalies count (z-score > 2.5 logic inline for speed)
    rows = db.execute("""
        SELECT wc_id, parameter, value
        FROM process_data_live
    """).fetchall()

    groups = defaultdict(list)
    for r in rows:
        groups[(r["wc_id"], r["parameter"])].append(_safe_float(r["value"]))

    anomaly_count = 0
    for key, values in groups.items():
        if len(values) < 5:
            continue
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        if stdev == 0:
            continue
        for v in values:
            if abs(v - mean) > 2.5 * stdev:
                anomaly_count += 1

    # Predicted failures (P(fail) > 0.5)
    equipment_rows = db.execute("""
        SELECT equipment_id, last_pm_date FROM equipment
    """).fetchall()

    maint_rows = db.execute("""
        SELECT equipment_id, completed_date
        FROM maintenance WHERE completed_date IS NOT NULL
        ORDER BY equipment_id, completed_date
    """).fetchall()
    maint_by_equip = defaultdict(list)
    for r in maint_rows:
        maint_by_equip[r["equipment_id"]].append(r["completed_date"])

    failure_count = 0
    total_failure_prob = 0
    equip_count = 0

    for eq in equipment_rows:
        eq_id = eq["equipment_id"]
        days_since_pm = 30
        if eq["last_pm_date"]:
            try:
                last_pm = datetime.strptime(eq["last_pm_date"][:10], "%Y-%m-%d").date()
                days_since_pm = max((today - last_pm).days, 0)
            except (ValueError, TypeError):
                pass

        dates = maint_by_equip.get(eq_id, [])
        mtbf_days = 45
        if len(dates) >= 2:
            parsed = []
            for d in dates:
                try:
                    parsed.append(datetime.strptime(d[:10], "%Y-%m-%d").date())
                except (ValueError, TypeError):
                    continue
            parsed.sort()
            if len(parsed) >= 2:
                intervals = [(parsed[i + 1] - parsed[i]).days
                             for i in range(len(parsed) - 1)
                             if (parsed[i + 1] - parsed[i]).days > 0]
                if intervals:
                    mtbf_days = statistics.mean(intervals)

        fp = 1.0 - math.exp(-days_since_pm / mtbf_days) if mtbf_days > 0 else 0
        if fp > 0.5:
            failure_count += 1
        total_failure_prob += fp
        equip_count += 1

    # Recommendations count (use rules inline — lightweight version)
    rec_count = 0

    # High scrap WCs
    scrap_check = db.execute("""
        SELECT sl.wc_id,
               SUM(sl.quantity_ft) AS total_scrap,
               sr.total_output
        FROM scrap_log sl
        LEFT JOIN (
            SELECT wc_id, SUM(total_output_ft) AS total_output
            FROM shift_reports GROUP BY wc_id
        ) sr ON sl.wc_id = sr.wc_id
        WHERE sl.wc_id IS NOT NULL
        GROUP BY sl.wc_id
    """).fetchall()
    for r in scrap_check:
        total_output = _safe_float(r["total_output"], 1)
        rate = (_safe_float(r["total_scrap"]) / total_output * 100) if total_output > 0 else 0
        if rate > 5:
            rec_count += 1

    # Unresolved CUSUM
    cusum_cnt = db.execute(
        "SELECT COUNT(*) AS c FROM process_deviations WHERE detection_method='CUSUM' AND resolved=0"
    ).fetchone()["c"]
    rec_count += cusum_cnt

    # Overdue PM
    overdue_cnt = db.execute(
        "SELECT COUNT(*) AS c FROM equipment WHERE next_pm_date IS NOT NULL AND next_pm_date < ?",
        (today.isoformat(),)
    ).fetchone()["c"]
    rec_count += overdue_cnt

    # Expiring certs
    cutoff = (today + timedelta(days=30)).isoformat()
    cert_cnt = db.execute(
        "SELECT COUNT(*) AS c FROM personnel_certs WHERE expiry_date <= ? AND status='Active'",
        (cutoff,)
    ).fetchone()["c"]
    if cert_cnt > 0:
        rec_count += 1

    # Average quality risk score
    qp_rows = db.execute("""
        SELECT sl.wc_id,
               SUM(sl.quantity_ft) AS total_scrap,
               sr.total_output
        FROM scrap_log sl
        LEFT JOIN (
            SELECT wc_id, SUM(total_output_ft) AS total_output
            FROM shift_reports GROUP BY wc_id
        ) sr ON sl.wc_id = sr.wc_id
        WHERE sl.wc_id IS NOT NULL
        GROUP BY sl.wc_id
    """).fetchall()

    risk_scores = []
    for r in qp_rows:
        total_output = _safe_float(r["total_output"], 1)
        scrap_rate = (_safe_float(r["total_scrap"]) / total_output * 100) if total_output > 0 else 0
        risk_scores.append(scrap_rate * 0.1)  # simplified risk proxy

    avg_risk = statistics.mean(risk_scores) if risk_scores else 0

    return jsonify({
        "anomalies_detected": anomaly_count,
        "predicted_failures": failure_count,
        "recommendations_count": rec_count,
        "avg_risk_score": round(avg_risk, 2),
        "equipment_count": equip_count,
    })


# ---------------------------------------------------------------------------
# GET /api/ai/isolation_forest
# Isolation Forest anomaly detection (pure Python implementation)
# ---------------------------------------------------------------------------

import random as _random

def _isolation_tree(data, max_depth, rng):
    """Build a single isolation tree recursively."""
    if len(data) <= 1 or max_depth <= 0:
        return {"type": "leaf", "size": len(data)}
    n_features = len(data[0])
    feat = rng.randint(0, n_features - 1)
    col = [row[feat] for row in data]
    lo, hi = min(col), max(col)
    if lo == hi:
        return {"type": "leaf", "size": len(data)}
    split = rng.uniform(lo, hi)
    left = [row for row in data if row[feat] < split]
    right = [row for row in data if row[feat] >= split]
    return {
        "type": "split", "feat": feat, "split": split,
        "left": _isolation_tree(left, max_depth - 1, rng),
        "right": _isolation_tree(right, max_depth - 1, rng),
    }


def _path_length(point, tree, depth=0):
    """Compute path length for a point through an isolation tree."""
    if tree["type"] == "leaf":
        n = tree["size"]
        if n <= 1:
            return depth
        # Average path length for BST of n items
        return depth + 2.0 * (math.log(n - 1) + 0.5772) - 2.0 * (n - 1) / n
    if point[tree["feat"]] < tree["split"]:
        return _path_length(point, tree["left"], depth + 1)
    return _path_length(point, tree["right"], depth + 1)


def _anomaly_score(path_length, n_samples):
    """Convert average path length to anomaly score (0-1)."""
    if n_samples <= 1:
        return 0.0
    c_n = 2.0 * (math.log(n_samples - 1) + 0.5772) - 2.0 * (n_samples - 1) / n_samples
    return 2.0 ** (-path_length / c_n)


@bp.route("/api/ai/isolation_forest")
@cached(ttl=60)
def isolation_forest():
    """Isolation Forest anomaly detection on process data.

    Pure Python implementation — no sklearn needed. Builds an ensemble of
    100 isolation trees on (value, delta, rate_of_change) features per
    work center, then scores each reading.
    """
    from db import get_db
    db = get_db()

    rows = db.execute("""
        SELECT wc_id, parameter, value, timestamp
        FROM process_data_live
        ORDER BY wc_id, parameter, timestamp
    """).fetchall()

    groups = defaultdict(list)
    for r in rows:
        groups[(r["wc_id"], r["parameter"])].append(dict(r))

    n_trees = 100
    max_depth = 8
    anomalies_list = []

    for (wc_id, param), readings in groups.items():
        values = [_safe_float(r["value"]) for r in readings]
        if len(values) < 10:
            continue

        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        if stdev == 0:
            continue

        # Build feature matrix: [z_score, delta, lag_delta]
        features = []
        for i, v in enumerate(values):
            z = (v - mean) / stdev
            delta = v - values[i - 1] if i > 0 else 0
            lag_delta = v - values[i - 2] if i > 1 else 0
            features.append([z, delta / stdev, lag_delta / stdev])

        # Build isolation forest
        rng = _random.Random(42)
        n_samples = len(features)
        sample_size = min(256, n_samples)
        trees = []
        for _ in range(n_trees):
            sample = rng.sample(features, sample_size)
            tree = _isolation_tree(sample, max_depth, rng)
            trees.append(tree)

        # Score each point
        for i, feat in enumerate(features):
            avg_path = statistics.mean(_path_length(feat, t) for t in trees)
            score = _anomaly_score(avg_path, sample_size)
            if score > 0.65:
                severity = "Critical" if score > 0.75 else "Warning"
                anomalies_list.append({
                    "wc_id": wc_id,
                    "parameter": param,
                    "value": round(values[i], 4),
                    "timestamp": readings[i]["timestamp"],
                    "anomaly_score": round(score, 4),
                    "avg_path_length": round(avg_path, 2),
                    "severity": severity,
                    "method": "IsolationForest",
                })

    anomalies_list.sort(key=lambda a: a["anomaly_score"], reverse=True)
    return jsonify(anomalies_list[:50])


# ---------------------------------------------------------------------------
# GET /api/ai/gradient_boost_quality
# Gradient-Boosted Decision Stump quality prediction (pure Python)
# ---------------------------------------------------------------------------

def _decision_stump(X, residuals, features_subset):
    """Find best single-feature split to minimize MSE of residuals."""
    best_feat, best_split, best_mse = 0, 0, float("inf")
    best_left_val, best_right_val = 0, 0
    n = len(X)
    for feat in features_subset:
        col = [(X[i][feat], residuals[i]) for i in range(n)]
        col.sort(key=lambda x: x[0])
        for j in range(1, n):
            if col[j][0] == col[j - 1][0]:
                continue
            left = [c[1] for c in col[:j]]
            right = [c[1] for c in col[j:]]
            left_mean = sum(left) / len(left)
            right_mean = sum(right) / len(right)
            mse = sum((r - left_mean) ** 2 for r in left) + sum((r - right_mean) ** 2 for r in right)
            if mse < best_mse:
                best_mse = mse
                best_feat = feat
                best_split = (col[j][0] + col[j - 1][0]) / 2
                best_left_val = left_mean
                best_right_val = right_mean
    return best_feat, best_split, best_left_val, best_right_val


@bp.route("/api/ai/gradient_boost_quality")
def gradient_boost_quality():
    """Gradient-boosted decision stumps for scrap prediction per WC.

    Features: avg deviation %, unresolved deviations, OEE, downtime minutes.
    Target: scrap rate.
    Pure Python — no sklearn, xgboost, etc.
    """
    from db import get_db
    db = get_db()

    # Build feature matrix per WC
    wc_rows = db.execute("SELECT DISTINCT wc_id FROM work_centers ORDER BY wc_id").fetchall()
    wc_ids = [r["wc_id"] for r in wc_rows]

    features_data = []  # (wc_id, [features], target)
    for wc_id in wc_ids:
        # Feature 1: avg deviation %
        dev = db.execute(
            "SELECT AVG(ABS(deviation_value - setpoint_value) / MAX(ABS(setpoint_value), 1) * 100) "
            "FROM process_deviations WHERE wc_id = ? AND setpoint_value IS NOT NULL AND setpoint_value != 0",
            (wc_id,)
        ).fetchone()[0] or 0

        # Feature 2: unresolved deviation count
        unresolved = db.execute(
            "SELECT COUNT(*) FROM process_deviations WHERE wc_id = ? AND resolved = 0", (wc_id,)
        ).fetchone()[0]

        # Feature 3: OEE
        oee = db.execute(
            "SELECT AVG(oee_overall) FROM shift_reports WHERE wc_id = ?", (wc_id,)
        ).fetchone()[0] or 0.85

        # Feature 4: downtime minutes
        dt = db.execute(
            "SELECT COALESCE(SUM(duration_min), 0) FROM downtime_log WHERE wc_id = ?", (wc_id,)
        ).fetchone()[0]

        # Target: scrap rate
        scrap = db.execute("SELECT COALESCE(SUM(quantity_ft), 0) FROM scrap_log WHERE wc_id = ?", (wc_id,)).fetchone()[0]
        output = db.execute("SELECT COALESCE(SUM(total_output_ft), 1) FROM shift_reports WHERE wc_id = ?", (wc_id,)).fetchone()[0]
        scrap_rate = scrap / max(output, 1) * 100

        features_data.append((wc_id, [dev, unresolved, oee * 100, dt], scrap_rate))

    if len(features_data) < 5:
        return jsonify({"error": "Insufficient data for gradient boosting", "predictions": []})

    # Train gradient-boosted stumps
    X = [f[1] for f in features_data]
    y = [f[2] for f in features_data]
    n = len(X)
    n_features = len(X[0])
    learning_rate = 0.3
    n_rounds = 50

    # Initialize predictions to mean
    y_mean = sum(y) / n
    predictions = [y_mean] * n
    stumps = []

    rng = _random.Random(42)
    for _ in range(n_rounds):
        residuals = [y[i] - predictions[i] for i in range(n)]
        feat_subset = list(range(n_features))
        feat, split, left_val, right_val = _decision_stump(X, residuals, feat_subset)
        stumps.append((feat, split, left_val, right_val))
        for i in range(n):
            pred = left_val if X[i][feat] < split else right_val
            predictions[i] += learning_rate * pred

    # Output predictions with feature importance
    feature_names = ["avg_deviation_pct", "unresolved_deviations", "oee_pct", "downtime_min"]
    feat_importance = [0.0] * n_features
    for feat, split, lv, rv in stumps:
        feat_importance[feat] += abs(lv - rv)
    total_imp = sum(feat_importance) or 1
    feat_importance = [round(fi / total_imp * 100, 1) for fi in feat_importance]

    results = []
    for i, (wc_id, feats, actual) in enumerate(features_data):
        results.append({
            "wc_id": wc_id,
            "predicted_scrap_rate": round(predictions[i], 3),
            "actual_scrap_rate": round(actual, 3),
            "residual": round(actual - predictions[i], 3),
            "risk_level": "Critical" if predictions[i] > 5 else "Warning" if predictions[i] > 3 else "OK",
            "features": dict(zip(feature_names, [round(f, 2) for f in feats])),
        })

    results.sort(key=lambda r: r["predicted_scrap_rate"], reverse=True)
    return jsonify({
        "model": "GradientBoostedStumps",
        "n_rounds": n_rounds, "learning_rate": learning_rate,
        "feature_importance": dict(zip(feature_names, feat_importance)),
        "predictions": results,
        "rmse": round(math.sqrt(sum((y[i] - predictions[i]) ** 2 for i in range(n)) / n), 4),
    })


# ---------------------------------------------------------------------------
# GET /api/ai/rul_maintenance
# Remaining Useful Life (RUL) predictive maintenance using Weibull model
# ---------------------------------------------------------------------------

@bp.route("/api/ai/rul_maintenance")
def rul_maintenance():
    """Weibull-based Remaining Useful Life estimation for equipment.

    Fits a Weibull distribution to time-between-failure data per equipment,
    then estimates RUL = E[T | T > t_elapsed].
    """
    from db import get_db
    db = get_db()

    equipment_rows = db.execute("""
        SELECT e.equipment_id, e.equipment_code, e.description,
               e.work_center_id, e.last_pm_date, e.status
        FROM equipment e ORDER BY e.equipment_id
    """).fetchall()

    # Failure durations from downtime_log (Breakdown category)
    failure_rows = db.execute("""
        SELECT equipment_id, start_time, duration_min
        FROM downtime_log
        WHERE category IN ('Breakdown', 'Equipment', 'Equipment Failure')
          AND equipment_id IS NOT NULL
        ORDER BY equipment_id, start_time
    """).fetchall()

    failures_by_equip = defaultdict(list)
    for r in failure_rows:
        failures_by_equip[r["equipment_id"]].append({
            "start": r["start_time"], "duration": r["duration_min"]
        })

    today = date.today()
    results = []

    for eq in equipment_rows:
        eq_id = eq["equipment_id"]
        failures = failures_by_equip.get(eq_id, [])

        # Time since last PM
        days_since_pm = 30
        if eq["last_pm_date"]:
            try:
                last_pm = datetime.strptime(eq["last_pm_date"][:10], "%Y-%m-%d").date()
                days_since_pm = max((today - last_pm).days, 1)
            except (ValueError, TypeError):
                pass

        # Compute time-between-failures (TBF) from failure timestamps
        tbf_list = []
        if len(failures) >= 2:
            parsed_times = []
            for f in failures:
                try:
                    parsed_times.append(datetime.strptime(f["start"][:19], "%Y-%m-%d %H:%M:%S"))
                except (ValueError, TypeError):
                    try:
                        parsed_times.append(datetime.strptime(f["start"][:10], "%Y-%m-%d"))
                    except (ValueError, TypeError):
                        continue
            parsed_times.sort()
            for j in range(1, len(parsed_times)):
                gap_hours = (parsed_times[j] - parsed_times[j - 1]).total_seconds() / 3600
                if gap_hours > 0:
                    tbf_list.append(gap_hours)

        # Weibull parameter estimation (method of moments)
        if len(tbf_list) >= 3:
            mean_tbf = statistics.mean(tbf_list)
            std_tbf = statistics.stdev(tbf_list)
            cv = std_tbf / mean_tbf if mean_tbf > 0 else 1
            # Approximate shape parameter (beta) from CV
            # CV ≈ 1/beta for Weibull (rough approximation)
            beta = max(1.0 / max(cv, 0.1), 0.5)
            # Scale parameter (eta) from mean
            # mean = eta * Gamma(1 + 1/beta) ≈ eta for beta near 1-3
            gamma_approx = math.exp(-0.5772 / beta) if beta > 0 else 1
            eta = mean_tbf / gamma_approx if gamma_approx > 0 else mean_tbf

            # Current age in hours
            t_elapsed = days_since_pm * 24

            # Reliability at current age: R(t) = exp(-(t/eta)^beta)
            reliability = math.exp(-((t_elapsed / eta) ** beta)) if eta > 0 else 0

            # Hazard rate: h(t) = (beta/eta) * (t/eta)^(beta-1)
            hazard = (beta / eta) * ((t_elapsed / eta) ** (beta - 1)) if eta > 0 else 0

            # RUL estimate (conditional mean): approximate
            # E[T-t | T>t] ≈ eta * Gamma(1 + 1/beta) - t for exponential-like
            rul_hours = max(mean_tbf - t_elapsed, 0)
            rul_days = round(rul_hours / 24, 1)

            # Failure probability in next 7 days
            t_future = t_elapsed + 168  # +7 days in hours
            r_future = math.exp(-((t_future / eta) ** beta)) if eta > 0 else 0
            prob_7day = max(0, min(1, reliability - r_future)) / max(reliability, 0.001)
        else:
            # Fallback: exponential model
            mtbf_hours = 45 * 24  # default 45 days
            t_elapsed = days_since_pm * 24
            beta = 1.0
            eta = mtbf_hours
            reliability = math.exp(-t_elapsed / mtbf_hours)
            hazard = 1.0 / mtbf_hours
            rul_hours = max(mtbf_hours - t_elapsed, 0)
            rul_days = round(rul_hours / 24, 1)
            prob_7day = 1.0 - math.exp(-168 / mtbf_hours)

        risk_level = "Critical" if rul_days < 7 else "Warning" if rul_days < 21 else "OK"

        results.append({
            "equipment_id": eq_id,
            "equipment_code": eq["equipment_code"],
            "description": eq["description"],
            "work_center_id": eq["work_center_id"],
            "status": eq["status"],
            "days_since_pm": days_since_pm,
            "weibull_beta": round(beta, 3),
            "weibull_eta_hours": round(eta, 1),
            "reliability": round(reliability, 4),
            "hazard_rate": round(hazard, 6),
            "rul_hours": round(rul_hours, 1),
            "rul_days": rul_days,
            "prob_fail_7day": round(prob_7day, 4),
            "risk_level": risk_level,
            "failure_count": len(failures),
            "tbf_count": len(tbf_list),
            "model": "Weibull" if len(tbf_list) >= 3 else "Exponential",
        })

    results.sort(key=lambda r: r["rul_days"])
    return jsonify(results)


# ---------------------------------------------------------------------------
# GET /api/ai/mahalanobis
# Multivariate anomaly detection using Mahalanobis distance (pure Python)
# ---------------------------------------------------------------------------

@bp.route("/api/ai/mahalanobis")
def mahalanobis():
    """Mahalanobis distance anomaly detection on process data.

    Groups process_data_live by wc_id, builds a feature vector of parameter
    values at each timestamp, computes the mean vector and covariance matrix,
    then flags observations where D² exceeds a chi-squared critical threshold.
    Pure Python — no numpy needed.
    """
    from db import get_db
    db = get_db()

    rows = db.execute("""
        SELECT wc_id, parameter, value, timestamp
        FROM process_data_live
        ORDER BY wc_id, timestamp, parameter
    """).fetchall()

    # Group readings by (wc_id, timestamp) to build feature vectors
    wc_ts_data = defaultdict(lambda: defaultdict(dict))
    wc_params = defaultdict(set)
    for r in rows:
        wc_id = r["wc_id"]
        ts = r["timestamp"]
        param = r["parameter"]
        wc_ts_data[wc_id][ts][param] = _safe_float(r["value"])
        wc_params[wc_id].add(param)

    anomalies_list = []

    for wc_id, ts_dict in wc_ts_data.items():
        params = sorted(wc_params[wc_id])
        p = len(params)
        if p < 2:
            continue  # need at least 2 features for multivariate analysis

        # Build observation matrix: each row is a feature vector
        observations = []
        timestamps = []
        for ts in sorted(ts_dict.keys()):
            reading = ts_dict[ts]
            if all(param in reading for param in params):
                vec = [reading[param] for param in params]
                observations.append(vec)
                timestamps.append(ts)

        n = len(observations)
        if n < p + 2:
            continue  # need enough observations

        # Compute mean vector
        mean_vec = [sum(obs[j] for obs in observations) / n for j in range(p)]

        # Compute covariance matrix
        cov = [[0.0] * p for _ in range(p)]
        for i_row in range(p):
            for j_col in range(i_row, p):
                s = sum(
                    (observations[k][i_row] - mean_vec[i_row]) *
                    (observations[k][j_col] - mean_vec[j_col])
                    for k in range(n)
                ) / max(n - 1, 1)
                cov[i_row][j_col] = s
                cov[j_col][i_row] = s

        # Invert covariance matrix (explicit formula for 2x2 or 3x3)
        inv_cov = None
        if p == 2:
            a, b = cov[0][0], cov[0][1]
            c, d = cov[1][0], cov[1][1]
            det = a * d - b * c
            if abs(det) < 1e-12:
                continue  # singular
            inv_cov = [
                [ d / det, -b / det],
                [-c / det,  a / det],
            ]
        elif p == 3:
            # 3x3 matrix inverse using cofactors
            m = cov
            det = (m[0][0] * (m[1][1]*m[2][2] - m[1][2]*m[2][1])
                 - m[0][1] * (m[1][0]*m[2][2] - m[1][2]*m[2][0])
                 + m[0][2] * (m[1][0]*m[2][1] - m[1][1]*m[2][0]))
            if abs(det) < 1e-12:
                continue  # singular
            inv_cov = [
                [
                    (m[1][1]*m[2][2] - m[1][2]*m[2][1]) / det,
                    (m[0][2]*m[2][1] - m[0][1]*m[2][2]) / det,
                    (m[0][1]*m[1][2] - m[0][2]*m[1][1]) / det,
                ],
                [
                    (m[1][2]*m[2][0] - m[1][0]*m[2][2]) / det,
                    (m[0][0]*m[2][2] - m[0][2]*m[2][0]) / det,
                    (m[0][2]*m[1][0] - m[0][0]*m[1][2]) / det,
                ],
                [
                    (m[1][0]*m[2][1] - m[1][1]*m[2][0]) / det,
                    (m[0][1]*m[2][0] - m[0][0]*m[2][1]) / det,
                    (m[0][0]*m[1][1] - m[0][1]*m[1][0]) / det,
                ],
            ]
        else:
            # For p > 3 use only the first 2 features (keep it pure Python)
            params = params[:2]
            p = 2
            observations = [[obs[0], obs[1]] for obs in observations]
            mean_vec = mean_vec[:2]
            a = cov[0][0]
            b = cov[0][1]
            c = cov[1][0]
            d = cov[1][1]
            det = a * d - b * c
            if abs(det) < 1e-12:
                continue
            inv_cov = [
                [ d / det, -b / det],
                [-c / det,  a / det],
            ]

        # Chi-squared critical value thresholds (99% confidence)
        # p=2 → 9.21, p=3 → 11.34
        chi2_crit = {2: 9.21, 3: 11.34}.get(p, 9.21)

        # Compute Mahalanobis D² for each observation
        for idx in range(n):
            diff = [observations[idx][j] - mean_vec[j] for j in range(p)]
            # D² = diffᵀ × Σ⁻¹ × diff
            temp = [sum(inv_cov[i][j] * diff[j] for j in range(p)) for i in range(p)]
            d_sq = sum(diff[i] * temp[i] for i in range(p))

            if d_sq > chi2_crit:
                severity = "Critical" if d_sq > chi2_crit * 1.5 else "Warning"
                anomalies_list.append({
                    "wc_id": wc_id,
                    "timestamp": timestamps[idx],
                    "d_squared": round(d_sq, 4),
                    "chi2_threshold": chi2_crit,
                    "n_features": p,
                    "features": params,
                    "values": {params[j]: round(observations[idx][j], 4) for j in range(p)},
                    "mean_values": {params[j]: round(mean_vec[j], 4) for j in range(p)},
                    "severity": severity,
                    "method": "Mahalanobis",
                })

    # Sort by D² descending and return top 50
    anomalies_list.sort(key=lambda a: a["d_squared"], reverse=True)
    return jsonify(anomalies_list[:50])


@bp.route("/api/ai/changeover_analysis")
def changeover_analysis():
    """Analyze changeover matrix vs actual schedule sequences to identify learning opportunities."""
    from db import get_db
    db = get_db()

    # Get static changeover matrix
    matrix = db.execute("SELECT from_product, to_product, setup_minutes, scrap_ft FROM changeover_matrix ORDER BY setup_minutes DESC").fetchall()

    # Get actual schedule sequences (consecutive jobs on same WC)
    actual = db.execute("""
        SELECT s1.wc_id, s1.wo_id AS from_wo, s2.wo_id AS to_wo,
               wo1.product_id AS from_product, wo2.product_id AS to_product,
               s1.sequence_pos AS from_seq, s2.sequence_pos AS to_seq
        FROM schedule s1
        JOIN schedule s2 ON s1.wc_id = s2.wc_id AND s2.sequence_pos = s1.sequence_pos + 1
        JOIN work_orders wo1 ON wo1.wo_id = s1.wo_id
        JOIN work_orders wo2 ON wo2.wo_id = s2.wo_id
        ORDER BY s1.wc_id, s1.sequence_pos
    """).fetchall()

    # Compare: find transitions in actual schedule that exist in changeover matrix
    matrix_dict = {(r["from_product"], r["to_product"]): dict(r) for r in matrix}
    insights = []
    for a in actual:
        key = (a["from_product"], a["to_product"])
        if key in matrix_dict:
            m = matrix_dict[key]
            insights.append({
                "wc_id": a["wc_id"],
                "from_product": a["from_product"],
                "to_product": a["to_product"],
                "planned_setup_min": m["setup_minutes"],
                "planned_scrap_ft": m["scrap_ft"],
                "learning_note": "ML could learn actual setup times from historical timestamps to improve planning accuracy",
            })

    # Identify top changeover-heavy transitions
    top_changevers = [dict(r) for r in matrix[:10]]

    return jsonify({
        "total_matrix_entries": len(matrix),
        "actual_transitions_found": len(insights),
        "top_changeovers": top_changevers,
        "schedule_insights": insights[:20],
        "recommendation": "A learning algorithm would track actual setup durations and update the changeover matrix automatically, "
                         "reducing scheduling estimation error by an estimated 15-25%.",
    })


@bp.route("/api/ai/adaptive_changeover", methods=["POST"])
def adaptive_changeover():
    """Update changeover matrix from historical downtime data (closed-loop optimization).

    Queries actual setup durations from downtime_log WHERE category='Setup',
    computes average per product-family transition, and updates changeover_matrix.
    """
    from db import get_db
    from utils.audit import log_audit
    db = get_db()

    # Get actual setup times from downtime log grouped by preceding/following product families
    # Use schedule sequence to infer which product transitions correspond to which setup events
    actuals = db.execute("""
        SELECT cm.from_product, cm.to_product, cm.setup_minutes AS static_minutes,
               COALESCE(AVG(dl.duration_min), cm.setup_minutes) AS actual_avg_minutes,
               COUNT(dl.log_id) AS sample_count
        FROM changeover_matrix cm
        LEFT JOIN downtime_log dl ON dl.category = 'Setup'
            AND dl.wc_id IN (SELECT DISTINCT wc_id FROM schedule)
        GROUP BY cm.from_product, cm.to_product
    """).fetchall()

    updates = []
    for r in actuals:
        static = r["static_minutes"]
        actual = round(r["actual_avg_minutes"], 1)
        diff = round(actual - static, 1)
        if abs(diff) > 2 and r["sample_count"] > 0:  # Only update if meaningful difference
            db.execute(
                "UPDATE changeover_matrix SET setup_minutes = ? WHERE from_product = ? AND to_product = ?",
                (actual, r["from_product"], r["to_product"]))
            updates.append({
                "from": r["from_product"], "to": r["to_product"],
                "old_minutes": static, "new_minutes": actual, "diff": diff,
                "samples": r["sample_count"],
            })

    if updates:
        log_audit(db, "changeover_matrix", "adaptive", "setup_minutes", "static", f"Updated {len(updates)} entries from actuals")
        db.commit()

    return jsonify({
        "ok": True,
        "entries_analyzed": len(actuals),
        "entries_updated": len(updates),
        "updates": updates,
        "note": "Changeover matrix updated from historical setup duration data. "
                "Re-run scheduling solvers to use updated values.",
    })


@bp.route("/api/ai/nlp_queries")
def nlp_queries():
    """Return pre-built example queries (fallback when no API key)."""
    from db import get_db
    db = get_db()

    queries = [
        {"question": "Which lot should I prioritize?",
         "sql": "SELECT wo_id, wc_id, priority_score FROM dispatch_queue WHERE status='Waiting' ORDER BY priority_score DESC LIMIT 5",
         "mesa": ["F3"]},
        {"question": "What caused the CV-2 failure?",
         "sql": "SELECT ncr_id, defect_type, description, severity FROM ncr WHERE detected_at='CV-2' OR wo_id IN (SELECT wo_id FROM ncr WHERE detected_at='CV-2') ORDER BY reported_date DESC LIMIT 5",
         "mesa": ["F7", "F8"]},
        {"question": "Is DRAW-1 die wearing out?",
         "sql": "SELECT parameter_name, deviation_value, setpoint_value, severity, timestamp FROM process_deviations WHERE wc_id='DRAW-1' AND detection_method='CUSUM' ORDER BY timestamp DESC LIMIT 5",
         "mesa": ["F5", "F8"]},
        {"question": "How much scrap this week?",
         "sql": "SELECT cause_code, SUM(quantity_ft) AS total_ft, COUNT(*) AS events FROM scrap_log WHERE timestamp >= DATE('now','-7 days') GROUP BY cause_code ORDER BY total_ft DESC",
         "mesa": ["F11"]},
        {"question": "Who can run CV-1 tonight?",
         "sql": "SELECT p.employee_name, pc.cert_level, pc.expiry_date FROM personnel_certs pc JOIN personnel p ON p.person_id=pc.person_id WHERE pc.wc_id='CV-1' AND p.shift='Night' AND pc.status='Active' AND p.active=1",
         "mesa": ["F6", "F3"]},
    ]

    results = []
    for q in queries:
        try:
            rows = db.execute(q["sql"]).fetchall()
            results.append({"question": q["question"], "sql": q["sql"],
                           "mesa_functions": q["mesa"], "result_count": len(rows),
                           "results": [dict(r) for r in rows[:5]]})
        except Exception as e:
            results.append({"question": q["question"], "sql": q["sql"],
                           "mesa_functions": q["mesa"], "result_count": 0,
                           "results": [], "error": str(e)})

    return jsonify({"concept": "Pre-built example queries. Set ANTHROPIC_API_KEY to enable live AI queries.",
                    "queries": results})


# ---------------------------------------------------------------------------
# Claude API — Natural Language to SQL (MESA Function 12: Intelligence Layer)
# ---------------------------------------------------------------------------

def _get_schema_summary(db):
    """Build a concise schema summary for the Claude system prompt."""
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    lines = ["SodhiCable MES Database Schema (SQLite, 65 tables):\n"]
    for t in tables:
        tname = t["name"]
        cols = db.execute(f"PRAGMA table_info([{tname}])").fetchall()
        col_str = ", ".join(f"{c['name']} {c['type']}" for c in cols)
        lines.append(f"  {tname}: {col_str}")
    return "\n".join(lines)


_SYSTEM_PROMPT = """You are the SodhiCable MES AI Assistant — an intelligent query layer for a wire & cable Manufacturing Execution System.

You answer manufacturing questions by querying the SQLite database using the execute_sql tool.

Rules:
1. ONLY generate SELECT queries. Never INSERT, UPDATE, DELETE, DROP, or ALTER.
2. Limit results to 50 rows maximum (use LIMIT 50).
3. Use the schema provided below to write correct queries.
4. After receiving results, provide a clear, concise natural language answer.
5. Include the SQL you ran so the user can learn from it.
6. If the question is ambiguous, make reasonable assumptions and state them.
7. Reference MESA functions (F1-F11) when relevant.

{schema}

Key domain knowledge:
- OEE = Availability x Performance x Quality (target 85%)
- Cpk target >= 1.33 (world class process capability)
- Work centers: COMPOUND, DRAW, CV (extrusion), BRAID, CABLE, PLCV/PX (jacket), TEST, CUT, PACK
- Products have families: A=Instrumentation, B=Armored, C=DHT, I=Insulated, M=MV, R=Utility, S=Shipboard, U=Fire-Rated
- Scrap tracked in feet, costs in dollars, OEE as decimal (0.85 = 85%)
"""

_TOOL_DEF = {
    "name": "execute_sql",
    "description": "Execute a read-only SQL SELECT query against the SodhiCable MES database and return results as JSON rows.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A SQL SELECT query. Must start with SELECT. Use LIMIT 50."
            }
        },
        "required": ["query"]
    }
}


@bp.route("/api/ai/ask", methods=["POST"])
def ai_ask():
    """Process a natural language manufacturing question using Claude API.

    Requires ANTHROPIC_API_KEY environment variable.
    Falls back to an error message if not configured.
    """
    import os
    import json as _json

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({
            "error": "ANTHROPIC_API_KEY not set. Set it as an environment variable to enable AI queries.",
            "fallback": True,
        }), 503

    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Please provide a question."}), 400

    try:
        import anthropic
    except ImportError:
        return jsonify({"error": "anthropic package not installed. Run: pip install anthropic"}), 503

    from db import get_db
    db = get_db()

    # Build schema-aware system prompt
    schema_text = _get_schema_summary(db)
    system = _SYSTEM_PROMPT.format(schema=schema_text)

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": question}]
    sql_queries = []  # track queries executed

    # Try models in order of preference — fall back if one fails
    models = ["claude-sonnet-4-6", "claude-sonnet-4-5-20241022", "claude-3-5-sonnet-20241022"]
    used_model = None

    try:
        response = None
        last_error = None
        for model in models:
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system,
                    tools=[_TOOL_DEF],
                    messages=messages,
                )
                used_model = model
                break
            except anthropic.APIError as model_err:
                last_error = model_err
                continue

        if response is None:
            return jsonify({"error": f"All models failed. Last error: {str(last_error)}"}), 502

        # Agentic loop — handle tool calls (supports parallel tool use)
        iterations = 0
        while response.stop_reason == "tool_use" and iterations < 8:
            iterations += 1

            # Find ALL tool_use blocks (Claude may request multiple in parallel)
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            if not tool_blocks:
                break

            # Execute all requested queries
            tool_results = []
            for tool_block in tool_blocks:
                query_text = tool_block.input.get("query", "")

                if not query_text.strip().upper().startswith("SELECT"):
                    tool_result = _json.dumps({"error": "Only SELECT queries allowed."})
                else:
                    try:
                        rows = db.execute(query_text).fetchall()
                        result_data = [dict(r) for r in rows[:50]]
                        sql_queries.append(query_text)
                        tool_result = _json.dumps({"row_count": len(result_data), "results": result_data})
                    except Exception as e:
                        tool_result = _json.dumps({"error": str(e)})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": tool_result,
                })

            # Continue conversation with all tool results
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            try:
                response = client.messages.create(
                    model=used_model,
                    max_tokens=4096,
                    system=system,
                    tools=[_TOOL_DEF],
                    messages=messages,
                )
            except anthropic.APIError:
                break  # stop the loop on error, use what we have

        # Extract final text answer
        answer = ""
        for block in response.content:
            if hasattr(block, "text"):
                answer += block.text

        return jsonify({
            "question": question,
            "answer": answer,
            "sql_queries": sql_queries,
            "model": used_model,
        })

    except anthropic.APIError as e:
        return jsonify({"error": f"Claude API error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@bp.route("/api/ai/nlp_status")
def nlp_status():
    """Check if Claude API is configured."""
    import os
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    try:
        import anthropic
        has_sdk = True
    except ImportError:
        has_sdk = False
    return jsonify({"api_key_set": has_key, "sdk_installed": has_sdk, "ready": has_key and has_sdk})
