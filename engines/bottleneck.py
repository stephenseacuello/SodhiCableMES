"""
engines/bottleneck.py - Bottleneck Analysis Engine

Uses the Kingman (VUT) approximation for G/G/1 queues to estimate
waiting times, identifies the plant bottleneck by utilisation, and
provides a what-if analysis for adding parallel capacity.
"""

import math


# ---------------------------------------------------------------------------
# Kingman (VUT) approximation
# ---------------------------------------------------------------------------
def kingman_approximation(lam, mu, ca_sq=1.0, cs_sq=0.5):
    """Estimate expected waiting time using the Kingman formula.

    E[Wq] = ((Ca^2 + Cs^2) / 2) * (rho / (1 - rho)) * (1 / mu)

    Parameters
    ----------
    lam : float
        Arrival rate (jobs per time unit).
    mu : float
        Service rate (jobs per time unit).
    ca_sq : float
        Squared coefficient of variation of inter-arrival times
        (default 1.0, i.e. Poisson arrivals).
    cs_sq : float
        Squared coefficient of variation of service times
        (default 0.5).

    Returns
    -------
    dict
        rho         - server utilisation (lambda / mu)
        expected_wq - expected waiting time in queue
        expected_w  - expected time in system (wait + service)
    """
    if mu <= 0:
        raise ValueError("Service rate mu must be positive.")
    if lam < 0:
        raise ValueError("Arrival rate must be non-negative.")

    rho = lam / mu

    if rho >= 1.0:
        return {
            "rho": rho,
            "expected_wq": float("inf"),
            "expected_w": float("inf"),
        }

    variability = (ca_sq + cs_sq) / 2.0
    utilisation_factor = rho / (1.0 - rho)
    service_time = 1.0 / mu

    expected_wq = variability * utilisation_factor * service_time
    expected_w = expected_wq + service_time

    return {
        "rho": round(rho, 4),
        "expected_wq": round(expected_wq, 4),
        "expected_w": round(expected_w, 4),
    }


# ---------------------------------------------------------------------------
# Identify bottleneck across work centers
# ---------------------------------------------------------------------------
def identify_bottleneck(conn):
    """Rank all work centers by utilisation (descending).

    Reads from: work_centers (columns: wc_id, name, arrival_rate,
    service_rate).

    Parameters
    ----------
    conn : sqlite3.Connection

    Returns
    -------
    list[dict]
        Each entry: wc_id, name, utilization, queue_estimate.
        Sorted by utilization descending (bottleneck first).
    """
    cur = conn.cursor()
    cur.execute("SELECT wc_id, name, capacity_ft_per_hr, utilization_target, capacity_hrs_per_week FROM work_centers")
    rows = cur.fetchall()

    results = []
    for row in rows:
        wc_id = row[0]
        name = row[1]
        capacity = row[2] or 0
        util_target = row[3] or 0.8
        # Estimate arrival/service from utilization target
        mu = max(capacity / 100.0, 0.1)  # service rate
        lam = mu * util_target  # arrival rate from target utilization

        if mu <= 0:
            results.append({
                "wc_id": wc_id,
                "name": name,
                "utilization": 0,
                "queue_estimate": 0,
            })
            continue

        kg = kingman_approximation(lam, mu)
        results.append({
            "wc_id": wc_id,
            "name": name,
            "utilization": kg["rho"],
            "queue_estimate": kg["expected_wq"],
        })

    results.sort(key=lambda r: r["utilization"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# What-if: add a parallel server
# ---------------------------------------------------------------------------
def what_if_add_server(conn, wc_id):
    """Estimate queue-time reduction from doubling capacity at a work center.

    Doubling capacity is modeled as doubling the service rate (mu).

    Parameters
    ----------
    conn : sqlite3.Connection
    wc_id : str
        Work center to evaluate.

    Returns
    -------
    dict
        current_wq    - current expected wait in queue
        new_wq        - estimated wait after adding a server
        reduction_pct - percentage reduction in waiting time
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT arrival_rate, service_rate FROM work_centers WHERE wc_id = ?",
        (wc_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"Work center '{wc_id}' not found.")

    lam, mu = row

    current = kingman_approximation(lam, mu)
    new = kingman_approximation(lam, mu * 2)  # double capacity

    current_wq = current["expected_wq"]
    new_wq = new["expected_wq"]

    if current_wq == float("inf") or current_wq == 0:
        reduction_pct = 0.0
    else:
        reduction_pct = ((current_wq - new_wq) / current_wq) * 100.0

    return {
        "current_wq": current_wq,
        "new_wq": new_wq,
        "reduction_pct": round(reduction_pct, 2),
    }
