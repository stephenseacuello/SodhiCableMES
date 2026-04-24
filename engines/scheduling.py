"""
Scheduling & Optimization Solvers for SodhiCable MES
=====================================================
12 optimization solvers covering product-mix LP, work-order acceptance IP,
single/parallel/flow-shop scheduling, supply chain planning, metaheuristics,
resource allocation, transportation, campaign batching, and reel cutting.

Imports LpProblem, LpVariable, etc. from engines.solver.
Also uses sqlite3 for database access.
"""

import sqlite3
import math
import random
import copy
from collections import defaultdict
from itertools import permutations

from engines.solver import (
    LpProblem, LpVariable, LpMaximize, LpMinimize,
    LpBinary, LpContinuous, value, lpSum,
)


# ===================================================================
# Helper utilities
# ===================================================================

def _fetch_all_dicts(cur):
    """Fetch all rows from cursor as list of dicts."""
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _safe_value(var):
    """Extract numeric value from LP variable, defaulting to 0."""
    v = value(var)
    return v if v is not None else 0.0


# ===================================================================
# P1 - Product Mix LP
# ===================================================================

def solve_p1_product_mix(conn, overrides=None):
    """
    Linear program to maximize profit from product mix.

    max  sum( (revenue_per_kft - cost_per_kft) * x_i )
    s.t. sum( time_ij * x_i ) <= capacity_j   for each work center j
         0 <= x_i <= max_order_qty_kft

    Parameters
    ----------
    conn : sqlite3.Connection
    overrides : dict or None
        Optional overrides for capacity or bounds.
        Keys: 'capacities' -> {wc_id: new_cap}, 'bounds' -> {product_id: (lo,hi)}

    Returns
    -------
    (status, profit, quantities_dict, shadow_prices_dict)
    """
    cur = conn.cursor()
    overrides = overrides or {}

    # Fetch products
    cur.execute("SELECT product_id, revenue_per_kft, cost_per_kft, max_order_qty_kft "
                "FROM products ORDER BY product_id")
    products = _fetch_all_dicts(cur)

    # Fetch work centers
    cur.execute("SELECT wc_id, capacity_hrs_per_week, num_parallel FROM work_centers")
    wcs = _fetch_all_dicts(cur)

    # Fetch routings
    cur.execute("SELECT product_id, wc_id, process_time_min_per_100ft FROM routings")
    routings = _fetch_all_dicts(cur)

    # Build routing lookup: (product_id, wc_id) -> time per kft in hours
    routing_map = {}
    for r in routings:
        # process_time_min_per_100ft -> hours per kft = time * 10 / 60
        hrs_per_kft = r["process_time_min_per_100ft"] * 10.0 / 60.0
        routing_map[(r["product_id"], r["wc_id"])] = hrs_per_kft

    # Build LP
    prob = LpProblem("ProductMix", LpMaximize)

    # Decision variables
    x = {}
    for p in products:
        pid = p["product_id"]
        lo, hi = 0, p["max_order_qty_kft"]
        if "bounds" in overrides and pid in overrides["bounds"]:
            lo, hi = overrides["bounds"][pid]
        x[pid] = LpVariable(f"x_{pid}", lowBound=lo, upBound=hi,
                             cat=LpContinuous)

    # Objective: maximize profit
    profit_coeffs = []
    for p in products:
        pid = p["product_id"]
        margin = p["revenue_per_kft"] - p["cost_per_kft"]
        profit_coeffs.append(margin * x[pid])
    prob += lpSum(profit_coeffs)

    # Constraints: work center capacity
    cap_overrides = overrides.get("capacities", {})
    constraint_names = {}
    for wc in wcs:
        wc_id = wc["wc_id"]
        cap = cap_overrides.get(wc_id, wc["capacity_hrs_per_week"] * wc["num_parallel"])

        usage = []
        for p in products:
            pid = p["product_id"]
            key = (pid, wc_id)
            if key in routing_map:
                usage.append(routing_map[key] * x[pid])
        if usage:
            cname = f"Cap_{wc_id}"
            prob += lpSum(usage) <= cap, cname
            constraint_names[wc_id] = cname

    # Solve
    prob.solve()
    status = prob.status

    # Extract results
    total_profit = value(prob.objective) if prob.objective else 0.0
    quantities = {pid: _safe_value(x[pid]) for pid in x}

    # Shadow prices — compute from capacity utilization
    # If a WC is at 100% capacity, its shadow price = marginal profit of relaxing that constraint
    shadow_prices = {}
    for wc in wcs:
        wc_id = wc["wc_id"]
        cap = wc["capacity_hrs_per_week"] * wc["num_parallel"]
        # Calculate actual usage
        usage_hrs = 0
        for pid in quantities:
            qty = quantities[pid]
            if qty <= 0:
                continue
            key = (pid, wc_id)
            if key in routing_map:
                usage_hrs += routing_map[key] * qty

        slack = cap - usage_hrs
        utilization = usage_hrs / cap if cap > 0 else 0

        if slack < 0.01 and usage_hrs > 0:
            # Binding constraint — estimate shadow price as avg margin of products using this WC
            margins = []
            for pid in quantities:
                if quantities[pid] > 0:
                    key = (pid, wc_id)
                    if key in routing_map and routing_map[key] > 0:
                        p = next((pr for pr in products if pr["product_id"] == pid), None)
                        if p:
                            margin_per_hr = (p["revenue_per_kft"] - p["cost_per_kft"]) / routing_map[key]
                            margins.append(margin_per_hr)
            shadow_prices[wc_id] = round(min(margins) if margins else 0, 2)
        else:
            shadow_prices[wc_id] = 0.0

    status_str = {1: "Optimal", 0: "Not Solved", -1: "Infeasible",
                  -2: "Unbounded", -3: "Undefined"}.get(status, str(status))

    return status_str, total_profit, quantities, shadow_prices


# ===================================================================
# P2 - Work Order Acceptance (Binary IP)
# ===================================================================

def solve_p2_wo_acceptance(conn, overrides=None):
    """
    Binary IP to select which work orders to accept.

    max  sum( value_i * x_i )
    s.t. sum( time_ij * qty_i * x_i ) <= capacity_j
         x_i in {0, 1}

    Returns (status, total_value, accepted_dict, slack_info)
    """
    cur = conn.cursor()
    overrides = overrides or {}

    # Fetch work orders
    cur.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft, wo.priority,
               p.revenue_per_kft, p.cost_per_kft
        FROM work_orders wo
        JOIN products p ON wo.product_id = p.product_id
        WHERE wo.status != 'cancelled'
        ORDER BY wo.wo_id
    """)
    work_orders = _fetch_all_dicts(cur)

    # Fetch work centers
    cur.execute("SELECT wc_id, capacity_hrs_per_week, num_parallel FROM work_centers")
    wcs = _fetch_all_dicts(cur)

    # Fetch routings
    cur.execute("SELECT product_id, wc_id, process_time_min_per_100ft FROM routings")
    routings = _fetch_all_dicts(cur)
    routing_map = {}
    for r in routings:
        hrs_per_kft = r["process_time_min_per_100ft"] * 10.0 / 60.0
        routing_map[(r["product_id"], r["wc_id"])] = hrs_per_kft

    # Build IP
    prob = LpProblem("WO_Acceptance", LpMaximize)

    x = {}
    for wo in work_orders:
        woid = wo["wo_id"]
        x[woid] = LpVariable(f"accept_{woid}", cat=LpBinary)

    # Objective: maximize revenue (weighted by priority)
    obj = []
    for wo in work_orders:
        woid = wo["wo_id"]
        wo_value = (wo["revenue_per_kft"] - wo["cost_per_kft"]) * wo["order_qty_kft"]
        # Weight by priority (higher priority = more value)
        wo_value *= (1.0 + wo["priority"] * 0.1)
        obj.append(wo_value * x[woid])
    prob += lpSum(obj)

    # Constraints: capacity
    cap_overrides = overrides.get("capacities", {})
    constraint_refs = {}
    for wc in wcs:
        wc_id = wc["wc_id"]
        cap = cap_overrides.get(wc_id, wc["capacity_hrs_per_week"] * wc["num_parallel"])

        usage = []
        for wo in work_orders:
            woid = wo["wo_id"]
            pid = wo["product_id"]
            key = (pid, wc_id)
            if key in routing_map:
                hrs = routing_map[key] * wo["order_qty_kft"]
                usage.append(hrs * x[woid])
        if usage:
            cname = f"Cap_{wc_id}"
            prob += lpSum(usage) <= cap, cname
            constraint_refs[wc_id] = cname

    prob.solve()
    status = prob.status
    status_str = {1: "Optimal", 0: "Not Solved", -1: "Infeasible",
                  -2: "Unbounded", -3: "Undefined"}.get(status, str(status))

    total_value = value(prob.objective) if prob.objective else 0.0
    accepted = {wo["wo_id"]: int(_safe_value(x[wo["wo_id"]])) for wo in work_orders}

    # Slack info
    slack_info = {}
    for wc_id, cname in constraint_refs.items():
        c = prob.constraints.get(cname)
        if c is not None:
            try:
                slack_info[wc_id] = c.slack if hasattr(c, "slack") and c.slack is not None else 0.0
            except Exception:
                slack_info[wc_id] = 0.0
        else:
            slack_info[wc_id] = 0.0

    return status_str, total_value, accepted, slack_info


# ===================================================================
# P3 - Single Machine Scheduling
# ===================================================================

def solve_p3_single_machine(conn, method="wspt"):
    """
    Single-machine scheduling for CABLE-1 work center.

    Methods: wspt, edd, moore

    Returns (method, metrics_dict, schedule_list)
    where metrics_dict has: makespan, tardy_jobs, total_tardiness, avg_flow_time
    """
    cur = conn.cursor()

    # Fetch jobs assigned to CABLE-1 (or first available WC)
    cur.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft, wo.priority,
               wo.due_date, wo.business_unit,
               r.process_time_min_per_100ft
        FROM work_orders wo
        JOIN routings r ON wo.product_id = r.product_id
        WHERE r.wc_id = 'CABLE-1' AND wo.status != 'cancelled'
        ORDER BY wo.wo_id
    """)
    rows = _fetch_all_dicts(cur)

    if not rows:
        # Try any work center
        cur.execute("""
            SELECT wo.wo_id, wo.product_id, wo.order_qty_kft, wo.priority,
                   wo.due_date, wo.business_unit,
                   r.process_time_min_per_100ft, r.wc_id
            FROM work_orders wo
            JOIN routings r ON wo.product_id = r.product_id
            WHERE wo.status != 'cancelled'
            ORDER BY wo.wo_id
        """)
        rows = _fetch_all_dicts(cur)

    # Build job list
    jobs = []
    for r in rows:
        # Processing time in hours
        proc_hrs = r["process_time_min_per_100ft"] * r["order_qty_kft"] * 10.0 / 60.0
        # Due date as numeric (hours from start)
        due = 0
        if r["due_date"]:
            try:
                due = float(r["due_date"])
            except (ValueError, TypeError):
                # Parse date string to week number * 40 hours
                due = 200.0  # default
        weight = r.get("priority", 1) or 1

        jobs.append({
            "wo_id": r["wo_id"],
            "product_id": r["product_id"],
            "qty_kft": r["order_qty_kft"],
            "proc_time": proc_hrs,
            "due": due,
            "weight": weight,
            "business_unit": r.get("business_unit", ""),
        })

    method = method.lower().strip()

    if method == "wspt":
        # Weighted Shortest Processing Time: sort by weight/proc_time descending
        jobs.sort(key=lambda j: j["weight"] / max(j["proc_time"], 0.001), reverse=True)

    elif method == "edd":
        # Earliest Due Date: sort by due date ascending
        jobs.sort(key=lambda j: j["due"])

    elif method == "moore":
        # Moore's algorithm: minimize number of tardy jobs
        # Sort by due date first
        jobs.sort(key=lambda j: j["due"])
        on_time = []
        tardy_set = []
        current_time = 0.0

        for job in jobs:
            on_time.append(job)
            current_time += job["proc_time"]
            if current_time > job["due"] and job["due"] > 0:
                # Remove the job with the longest processing time
                longest = max(on_time, key=lambda j: j["proc_time"])
                on_time.remove(longest)
                tardy_set.append(longest)
                current_time -= longest["proc_time"]

        jobs = on_time + tardy_set
    else:
        # Default to WSPT
        jobs.sort(key=lambda j: j["weight"] / max(j["proc_time"], 0.001), reverse=True)

    # Build schedule and compute metrics
    schedule = []
    current_time = 0.0
    total_tardiness = 0.0
    tardy_count = 0
    total_flow = 0.0

    for job in jobs:
        start = current_time
        end = start + job["proc_time"]
        flow_time = end
        tardiness = max(0, end - job["due"]) if job["due"] > 0 else 0.0
        is_tardy = tardiness > 0

        if is_tardy:
            tardy_count += 1
            total_tardiness += tardiness

        total_flow += flow_time

        schedule.append({
            "wo_id": job["wo_id"],
            "product_id": job["product_id"],
            "qty_kft": job["qty_kft"],
            "start": round(start, 2),
            "end": round(end, 2),
            "proc_time": round(job["proc_time"], 2),
            "due": job["due"],
            "tardiness": round(tardiness, 2),
            "tardy": is_tardy,
        })

        current_time = end

    makespan = current_time
    avg_flow = total_flow / len(jobs) if jobs else 0.0

    metrics = {
        "makespan": round(makespan, 2),
        "tardy_jobs": tardy_count,
        "total_tardiness": round(total_tardiness, 2),
        "avg_flow_time": round(avg_flow, 2),
    }

    return method.upper(), metrics, schedule


# ===================================================================
# P4 - Parallel Machine Scheduling (LPT)
# ===================================================================

def solve_p4_parallel_machines(conn):
    """
    Longest Processing Time (LPT) heuristic for parallel machines
    (CV-1 and CV-2 or first two work centers).

    Returns (makespan, schedule_list, assignment_dict)
    """
    cur = conn.cursor()

    # Get parallel machines
    cur.execute("SELECT wc_id FROM work_centers WHERE wc_id IN ('CV-1','CV-2') ORDER BY wc_id")
    machines = [r[0] for r in cur.fetchall()]
    if len(machines) < 2:
        cur.execute("SELECT wc_id FROM work_centers ORDER BY wc_id LIMIT 2")
        machines = [r[0] for r in cur.fetchall()]
    if not machines:
        machines = ["M1", "M2"]

    # Get jobs
    cur.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft, wo.priority,
               r.process_time_min_per_100ft
        FROM work_orders wo
        JOIN routings r ON wo.product_id = r.product_id
        WHERE r.wc_id = ? AND wo.status != 'cancelled'
        ORDER BY wo.wo_id
    """, (machines[0],))
    rows = _fetch_all_dicts(cur)

    if not rows:
        cur.execute("""
            SELECT DISTINCT wo.wo_id, wo.product_id, wo.order_qty_kft, wo.priority,
                   MIN(r.process_time_min_per_100ft) as process_time_min_per_100ft
            FROM work_orders wo
            JOIN routings r ON wo.product_id = r.product_id
            WHERE wo.status != 'cancelled'
            GROUP BY wo.wo_id
            ORDER BY wo.wo_id
        """)
        rows = _fetch_all_dicts(cur)

    jobs = []
    for r in rows:
        proc = r["process_time_min_per_100ft"] * r["order_qty_kft"] * 10.0 / 60.0
        jobs.append({
            "wo_id": r["wo_id"],
            "product_id": r["product_id"],
            "qty_kft": r["order_qty_kft"],
            "proc_time": proc,
        })

    # LPT: sort jobs by processing time descending
    jobs.sort(key=lambda j: j["proc_time"], reverse=True)

    # Assign to least-loaded machine
    machine_load = {m: 0.0 for m in machines}
    machine_schedule = {m: [] for m in machines}
    assignment = {}

    for job in jobs:
        # Pick machine with minimum current load
        best_m = min(machine_load, key=machine_load.get)
        start = machine_load[best_m]
        end = start + job["proc_time"]

        machine_schedule[best_m].append({
            "wo_id": job["wo_id"],
            "product_id": job["product_id"],
            "qty_kft": job["qty_kft"],
            "machine": best_m,
            "start": round(start, 2),
            "end": round(end, 2),
            "proc_time": round(job["proc_time"], 2),
        })

        machine_load[best_m] = end
        assignment[job["wo_id"]] = best_m

    makespan = max(machine_load.values()) if machine_load else 0.0

    # Flatten schedule
    schedule = []
    for m in machines:
        schedule.extend(machine_schedule[m])
    schedule.sort(key=lambda s: (s["machine"], s["start"]))

    return round(makespan, 2), schedule, assignment


# ===================================================================
# P5a - Flow Shop (Johnson's Rule, 2 machines)
# ===================================================================

def solve_p5_flow_shop(conn):
    """
    Johnson's Rule for 2-machine flow shop on B-family products.

    Returns (makespan, schedule_list)
    """
    cur = conn.cursor()

    # Get B-family work orders with routings on two machines
    cur.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft,
               r.wc_id, r.process_time_min_per_100ft
        FROM work_orders wo
        JOIN routings r ON wo.product_id = r.product_id
        JOIN products p ON wo.product_id = p.product_id
        WHERE (p.family = 'B' OR p.family LIKE 'B%') AND wo.status != 'cancelled'
        ORDER BY wo.wo_id, r.wc_id
    """)
    rows = _fetch_all_dicts(cur)

    if not rows:
        # Fallback: use all work orders
        cur.execute("""
            SELECT wo.wo_id, wo.product_id, wo.order_qty_kft,
                   r.wc_id, r.process_time_min_per_100ft
            FROM work_orders wo
            JOIN routings r ON wo.product_id = r.product_id
            WHERE wo.status != 'cancelled'
            ORDER BY wo.wo_id, r.wc_id
        """)
        rows = _fetch_all_dicts(cur)

    # Build job times per machine
    job_times = defaultdict(dict)  # {wo_id: {wc_id: time_hrs}}
    job_info = {}
    wc_set = set()

    for r in rows:
        proc = r["process_time_min_per_100ft"] * r["order_qty_kft"] * 10.0 / 60.0
        job_times[r["wo_id"]][r["wc_id"]] = proc
        job_info[r["wo_id"]] = {"product_id": r["product_id"],
                                 "qty_kft": r["order_qty_kft"]}
        wc_set.add(r["wc_id"])

    machines = sorted(wc_set)[:2]
    if len(machines) < 2:
        machines = machines + ["M2"]

    m1, m2 = machines[0], machines[1]

    # Johnson's Rule
    front = []
    back = []
    job_ids = list(job_times.keys())

    for jid in job_ids:
        t1 = job_times[jid].get(m1, 0)
        t2 = job_times[jid].get(m2, 0)
        if t1 <= t2:
            front.append((jid, t1, t2))
        else:
            back.append((jid, t1, t2))

    front.sort(key=lambda x: x[1])   # ascending by machine 1 time
    back.sort(key=lambda x: x[2], reverse=True)  # descending by machine 2 time

    sequence = front + back

    # Compute schedule
    schedule = []
    m1_end = 0.0
    m2_end = 0.0

    for jid, t1, t2 in sequence:
        s1 = m1_end
        e1 = s1 + t1
        s2 = max(e1, m2_end)
        e2 = s2 + t2

        info = job_info.get(jid, {})
        schedule.append({
            "wo_id": jid,
            "product_id": info.get("product_id", ""),
            "qty_kft": info.get("qty_kft", 0),
            "m1_start": round(s1, 2),
            "m1_end": round(e1, 2),
            "m2_start": round(s2, 2),
            "m2_end": round(e2, 2),
        })

        m1_end = e1
        m2_end = e2

    makespan = m2_end

    return round(makespan, 2), schedule


# ===================================================================
# P5b - Flow Shop NEH Heuristic (m machines)
# ===================================================================

def solve_p5_flow_shop_neh(conn):
    """
    NEH heuristic for m-machine flow shop.

    Returns (makespan, schedule_list)
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft,
               r.wc_id, r.process_time_min_per_100ft
        FROM work_orders wo
        JOIN routings r ON wo.product_id = r.product_id
        WHERE wo.status != 'cancelled'
        ORDER BY wo.wo_id, r.wc_id
    """)
    rows = _fetch_all_dicts(cur)

    # Build job times
    job_times = defaultdict(dict)
    job_info = {}
    wc_order = []
    wc_seen = set()

    for r in rows:
        proc = r["process_time_min_per_100ft"] * r["order_qty_kft"] * 10.0 / 60.0
        job_times[r["wo_id"]][r["wc_id"]] = proc
        job_info[r["wo_id"]] = {"product_id": r["product_id"],
                                 "qty_kft": r["order_qty_kft"]}
        if r["wc_id"] not in wc_seen:
            wc_order.append(r["wc_id"])
            wc_seen.add(r["wc_id"])

    machines = wc_order if wc_order else ["M1"]
    job_ids = list(job_times.keys())

    def _compute_makespan(seq):
        """Compute makespan for a given sequence on m machines."""
        n = len(seq)
        m = len(machines)
        if n == 0 or m == 0:
            return 0.0
        # C[i][j] = completion time of job i on machine j
        C = [[0.0] * m for _ in range(n)]
        for i, jid in enumerate(seq):
            for j, mc in enumerate(machines):
                proc = job_times[jid].get(mc, 0.0)
                if i == 0 and j == 0:
                    C[i][j] = proc
                elif i == 0:
                    C[i][j] = C[i][j - 1] + proc
                elif j == 0:
                    C[i][j] = C[i - 1][j] + proc
                else:
                    C[i][j] = max(C[i - 1][j], C[i][j - 1]) + proc
        return C[n - 1][m - 1]

    # NEH: sort by total processing time descending
    total_times = {jid: sum(job_times[jid].values()) for jid in job_ids}
    sorted_jobs = sorted(job_ids, key=lambda j: total_times[j], reverse=True)

    # Build sequence incrementally
    best_seq = []
    for job in sorted_jobs:
        best_ms = float("inf")
        best_pos = 0
        for pos in range(len(best_seq) + 1):
            trial = best_seq[:pos] + [job] + best_seq[pos:]
            ms = _compute_makespan(trial)
            if ms < best_ms:
                best_ms = ms
                best_pos = pos
        best_seq = best_seq[:best_pos] + [job] + best_seq[best_pos:]

    # Build schedule details
    n = len(best_seq)
    m = len(machines)
    schedule = []

    if n > 0 and m > 0:
        C = [[0.0] * m for _ in range(n)]
        S = [[0.0] * m for _ in range(n)]
        for i, jid in enumerate(best_seq):
            for j, mc in enumerate(machines):
                proc = job_times[jid].get(mc, 0.0)
                if i == 0 and j == 0:
                    S[i][j] = 0.0
                elif i == 0:
                    S[i][j] = C[i][j - 1]
                elif j == 0:
                    S[i][j] = C[i - 1][j]
                else:
                    S[i][j] = max(C[i - 1][j], C[i][j - 1])
                C[i][j] = S[i][j] + proc

        for i, jid in enumerate(best_seq):
            info = job_info.get(jid, {})
            entry = {
                "wo_id": jid,
                "product_id": info.get("product_id", ""),
                "qty_kft": info.get("qty_kft", 0),
                "position": i + 1,
            }
            for j, mc in enumerate(machines):
                entry[f"{mc}_start"] = round(S[i][j], 2)
                entry[f"{mc}_end"] = round(C[i][j], 2)
            schedule.append(entry)

        makespan = C[n - 1][m - 1]
    else:
        makespan = 0.0

    return round(makespan, 2), schedule


# ===================================================================
# P6 - Supply Chain Multi-Period LP
# ===================================================================

def solve_p6_supply_chain(conn):
    """
    Multi-period (4 weeks) supply chain planning LP.

    min  sum( production_cost * x_it + holding_cost * inv_it )
    s.t. inv_i,t = inv_i,t-1 + x_i,t - demand_i,t
         x_it <= capacity
         inv_it >= 0

    Returns (status, total_cost, production_plan, inventory_plan)
    """
    cur = conn.cursor()

    # Products
    cur.execute("SELECT product_id, cost_per_kft FROM products ORDER BY product_id")
    products = _fetch_all_dicts(cur)

    weeks = [1, 2, 3, 4]

    # Generate demand per product per week from work orders
    demand = defaultdict(lambda: defaultdict(float))
    cur.execute("""
        SELECT product_id, order_qty_kft, due_date FROM work_orders
        WHERE status != 'cancelled'
    """)
    for row in cur.fetchall():
        pid, qty, due = row
        try:
            wk = int(due) if due else 1
        except (ValueError, TypeError):
            wk = 1
        wk = max(1, min(wk, 4))
        demand[pid][wk] += qty

    # Capacity per week (sum of all work centers)
    cur.execute("SELECT SUM(capacity_hrs_per_week * num_parallel) FROM work_centers")
    total_cap_hrs = cur.fetchone()[0] or 200.0

    prob = LpProblem("SupplyChain", LpMinimize)

    # Variables
    x = {}  # production
    inv = {}  # inventory
    holding_rate = 0.5  # per kft per week

    for p in products:
        pid = p["product_id"]
        for w in weeks:
            x[(pid, w)] = LpVariable(f"prod_{pid}_{w}", lowBound=0, cat=LpContinuous)
            inv[(pid, w)] = LpVariable(f"inv_{pid}_{w}", lowBound=0, cat=LpContinuous)

    # Objective
    cost_terms = []
    for p in products:
        pid = p["product_id"]
        for w in weeks:
            cost_terms.append(p["cost_per_kft"] * x[(pid, w)])
            cost_terms.append(holding_rate * inv[(pid, w)])
    prob += lpSum(cost_terms)

    # Inventory balance
    initial_inv = 5.0  # initial inventory per product
    for p in products:
        pid = p["product_id"]
        for w in weeks:
            d = demand[pid].get(w, 0)
            if w == 1:
                prob += inv[(pid, w)] == initial_inv + x[(pid, w)] - d, \
                    f"InvBal_{pid}_{w}"
            else:
                prob += inv[(pid, w)] == inv[(pid, w - 1)] + x[(pid, w)] - d, \
                    f"InvBal_{pid}_{w}"

    # Capacity constraints (simplified: total production hours per week)
    cur.execute("SELECT product_id, process_time_min_per_100ft FROM routings")
    avg_time = {}
    counts = defaultdict(int)
    time_sums = defaultdict(float)
    for row in cur.fetchall():
        pid, pt = row
        time_sums[pid] += pt
        counts[pid] += 1
    for pid in time_sums:
        avg_time[pid] = time_sums[pid] / counts[pid]

    for w in weeks:
        cap_terms = []
        for p in products:
            pid = p["product_id"]
            hrs_per_kft = avg_time.get(pid, 5.0) * 10.0 / 60.0
            cap_terms.append(hrs_per_kft * x[(pid, w)])
        prob += lpSum(cap_terms) <= total_cap_hrs, f"Cap_wk{w}"

    prob.solve()
    status = prob.status
    status_str = {1: "Optimal", 0: "Not Solved", -1: "Infeasible",
                  -2: "Unbounded", -3: "Undefined"}.get(status, str(status))

    total_cost = value(prob.objective) if prob.objective else 0.0

    production_plan = {}
    inventory_plan = {}
    for p in products:
        pid = p["product_id"]
        production_plan[pid] = {w: round(_safe_value(x[(pid, w)]), 2) for w in weeks}
        inventory_plan[pid] = {w: round(_safe_value(inv[(pid, w)]), 2) for w in weeks}

    return status_str, round(total_cost, 2), production_plan, inventory_plan


# ===================================================================
# P7 - Metaheuristics (SA and GA)
# ===================================================================

def solve_p7_metaheuristics(conn, method="sa"):
    """
    Metaheuristic solvers for job sequencing.

    SA: T0=1000, alpha=0.95, 500 iterations, swap/insert neighbors.
    GA: pop=30, 50 generations, OX crossover, tournament selection.

    Returns (best_obj, best_sequence, convergence)
    """
    cur = conn.cursor()

    # Build jobs with changeover data
    cur.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft,
               r.process_time_min_per_100ft
        FROM work_orders wo
        JOIN routings r ON wo.product_id = r.product_id
        WHERE wo.status != 'cancelled'
        ORDER BY wo.wo_id
    """)
    rows = _fetch_all_dicts(cur)

    # Deduplicate by wo_id (take first routing)
    seen = set()
    jobs = []
    for r in rows:
        if r["wo_id"] not in seen:
            seen.add(r["wo_id"])
            proc = r["process_time_min_per_100ft"] * r["order_qty_kft"] * 10.0 / 60.0
            jobs.append({
                "wo_id": r["wo_id"],
                "product_id": r["product_id"],
                "proc_time": proc,
            })

    n = len(jobs)
    if n == 0:
        return 0.0, [], []

    # Changeover matrix
    cur.execute("SELECT from_product, to_product, setup_minutes FROM changeover_matrix")
    changeover = {}
    for row in cur.fetchall():
        changeover[(row[0], row[1])] = row[2] / 60.0  # convert to hours

    def get_changeover(i, j):
        """Get changeover time between job i and job j (by index)."""
        p1 = jobs[i]["product_id"]
        p2 = jobs[j]["product_id"]
        return changeover.get((p1, p2), 0.5)  # default 30 min

    def objective(seq):
        """Total makespan = sum of processing times + changeover times."""
        total = 0.0
        for k, idx in enumerate(seq):
            total += jobs[idx]["proc_time"]
            if k > 0:
                total += get_changeover(seq[k - 1], idx)
        return total

    method = method.lower().strip()

    if method == "sa":
        # --- Simulated Annealing ---
        T0 = 1000.0
        alpha = 0.95
        max_iter = 500

        rng = random.Random(42)
        current = list(range(n))
        rng.shuffle(current)
        current_obj = objective(current)
        best = current[:]
        best_obj = current_obj
        T = T0
        convergence = []

        for it in range(max_iter):
            # Generate neighbor: swap two random positions
            neighbor = current[:]
            i, j = rng.sample(range(n), 2)
            if rng.random() < 0.5:
                # Swap
                neighbor[i], neighbor[j] = neighbor[j], neighbor[i]
            else:
                # Insert: remove i and insert at j
                elem = neighbor.pop(i)
                neighbor.insert(j, elem)

            neighbor_obj = objective(neighbor)
            delta = neighbor_obj - current_obj

            if delta < 0 or rng.random() < math.exp(-delta / max(T, 1e-10)):
                current = neighbor
                current_obj = neighbor_obj

                if current_obj < best_obj:
                    best = current[:]
                    best_obj = current_obj

            T *= alpha
            convergence.append({
                "iteration": it,
                "temperature": round(T, 4),
                "current_obj": round(current_obj, 4),
                "best_obj": round(best_obj, 4),
            })

        best_sequence = [jobs[i]["wo_id"] for i in best]
        return round(best_obj, 2), best_sequence, convergence

    elif method == "ga":
        # --- Genetic Algorithm ---
        pop_size = 30
        generations = 50
        rng = random.Random(42)

        # Initialize population
        population = []
        for _ in range(pop_size):
            ind = list(range(n))
            rng.shuffle(ind)
            population.append(ind)

        def fitness(ind):
            return objective(ind)

        def tournament_select(pop, fitnesses, k=3):
            """Tournament selection with tournament size k."""
            candidates = rng.sample(range(len(pop)), min(k, len(pop)))
            best_c = min(candidates, key=lambda c: fitnesses[c])
            return pop[best_c][:]

        def ox_crossover(p1, p2):
            """Order crossover (OX)."""
            size = len(p1)
            if size < 3:
                return p1[:], p2[:]
            a, b = sorted(rng.sample(range(size), 2))
            child1 = [None] * size
            child2 = [None] * size

            child1[a:b + 1] = p1[a:b + 1]
            child2[a:b + 1] = p2[a:b + 1]

            def fill_child(child, donor):
                pos = (b + 1) % size
                donor_pos = (b + 1) % size
                while None in child:
                    gene = donor[donor_pos]
                    if gene not in child:
                        child[pos] = gene
                        pos = (pos + 1) % size
                    donor_pos = (donor_pos + 1) % size
                return child

            child1 = fill_child(child1, p2)
            child2 = fill_child(child2, p1)
            return child1, child2

        def mutate(ind, rate=0.1):
            """Swap mutation."""
            if rng.random() < rate and len(ind) >= 2:
                i, j = rng.sample(range(len(ind)), 2)
                ind[i], ind[j] = ind[j], ind[i]
            return ind

        convergence = []
        best_ever = None
        best_ever_obj = float("inf")

        for gen in range(generations):
            fitnesses = [fitness(ind) for ind in population]

            # Track best
            gen_best_idx = min(range(len(population)), key=lambda i: fitnesses[i])
            gen_best_obj = fitnesses[gen_best_idx]

            if gen_best_obj < best_ever_obj:
                best_ever_obj = gen_best_obj
                best_ever = population[gen_best_idx][:]

            convergence.append({
                "generation": gen,
                "best_fitness": round(gen_best_obj, 4),
                "avg_fitness": round(sum(fitnesses) / len(fitnesses), 4),
                "best_ever": round(best_ever_obj, 4),
            })

            # Create next generation
            new_pop = [best_ever[:]]  # elitism

            while len(new_pop) < pop_size:
                p1 = tournament_select(population, fitnesses)
                p2 = tournament_select(population, fitnesses)
                c1, c2 = ox_crossover(p1, p2)
                c1 = mutate(c1)
                c2 = mutate(c2)
                new_pop.append(c1)
                if len(new_pop) < pop_size:
                    new_pop.append(c2)

            population = new_pop

        best_sequence = [jobs[i]["wo_id"] for i in best_ever] if best_ever else []
        return round(best_ever_obj, 2), best_sequence, convergence

    else:
        # Default to SA
        return solve_p7_metaheuristics(conn, method="sa")


# ===================================================================
# P8 - Resource Allocation (Assignment LP)
# ===================================================================

def solve_p8_resource_allocation(conn):
    """
    Binary assignment LP: assign work orders to work centers to minimize cost.

    min sum( cost_ij * x_ij )
    s.t. sum_j(x_ij) = 1 for each WO i  (each WO assigned exactly once)
         sum_i(time_ij * x_ij) <= capacity_j for each WC j
         x_ij in {0,1}

    Returns (status, total_cost, assignments_dict)
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft
        FROM work_orders wo WHERE wo.status != 'cancelled'
        ORDER BY wo.wo_id
    """)
    work_orders = _fetch_all_dicts(cur)

    cur.execute("SELECT wc_id, capacity_hrs_per_week, num_parallel FROM work_centers")
    wcs = _fetch_all_dicts(cur)

    cur.execute("SELECT product_id, wc_id, process_time_min_per_100ft FROM routings")
    routings_raw = _fetch_all_dicts(cur)
    routing_map = {}
    for r in routings_raw:
        routing_map[(r["product_id"], r["wc_id"])] = r["process_time_min_per_100ft"]

    prob = LpProblem("ResourceAllocation", LpMinimize)

    x = {}
    for wo in work_orders:
        for wc in wcs:
            key = (wo["wo_id"], wc["wc_id"])
            x[key] = LpVariable(f"assign_{wo['wo_id']}_{wc['wc_id']}", cat=LpBinary)

    # Objective: minimize total processing cost
    cost_terms = []
    for wo in work_orders:
        for wc in wcs:
            key = (wo["wo_id"], wc["wc_id"])
            rt = routing_map.get((wo["product_id"], wc["wc_id"]), None)
            if rt is not None:
                hrs = rt * wo["order_qty_kft"] * 10.0 / 60.0
                cost = hrs * 50.0  # $50/hr operating cost
            else:
                cost = 99999.0  # Big-M penalty for infeasible assignment
            cost_terms.append(cost * x[key])
    prob += lpSum(cost_terms)

    # Each WO assigned exactly once
    for wo in work_orders:
        terms = [x[(wo["wo_id"], wc["wc_id"])] for wc in wcs]
        prob += lpSum(terms) == 1, f"Assign_{wo['wo_id']}"

    # Capacity constraints
    for wc in wcs:
        cap = wc["capacity_hrs_per_week"] * wc["num_parallel"]
        terms = []
        for wo in work_orders:
            key = (wo["wo_id"], wc["wc_id"])
            rt = routing_map.get((wo["product_id"], wc["wc_id"]), 0)
            hrs = rt * wo["order_qty_kft"] * 10.0 / 60.0
            terms.append(hrs * x[key])
        prob += lpSum(terms) <= cap, f"Cap_{wc['wc_id']}"

    prob.solve()
    status = prob.status
    status_str = {1: "Optimal", 0: "Not Solved", -1: "Infeasible",
                  -2: "Unbounded", -3: "Undefined"}.get(status, str(status))

    total_cost = value(prob.objective) if prob.objective else 0.0

    assignments = {}
    for wo in work_orders:
        for wc in wcs:
            key = (wo["wo_id"], wc["wc_id"])
            if _safe_value(x[key]) > 0.5:
                assignments[wo["wo_id"]] = wc["wc_id"]

    return status_str, round(total_cost, 2), assignments


# ===================================================================
# P9 - Transportation Problem
# ===================================================================

def solve_p9_transportation(conn):
    """
    Transportation LP using plants and shipping_costs tables.

    min sum( cost_ij * x_ij )
    s.t. sum_j(x_ij) <= supply_i      (plant capacity)
         sum_i(x_ij) >= demand_j       (customer demand)
         x_ij >= 0

    Returns (status, total_cost, shipments_dict, plant_usage, customer_demand)
    """
    cur = conn.cursor()

    # Try to read plants table
    try:
        cur.execute("SELECT plant_id, capacity_kft FROM plants ORDER BY plant_id")
        plants = _fetch_all_dicts(cur)
    except sqlite3.OperationalError:
        # Create synthetic data if table doesn't exist
        plants = [
            {"plant_id": "PLANT-1", "capacity_kft": 500},
            {"plant_id": "PLANT-2", "capacity_kft": 400},
            {"plant_id": "PLANT-3", "capacity_kft": 350},
        ]

    # Try to read customers/demand
    try:
        cur.execute("SELECT customer_id, demand_kft FROM customers ORDER BY customer_id")
        customers = _fetch_all_dicts(cur)
    except sqlite3.OperationalError:
        customers = [
            {"customer_id": "CUST-A", "demand_kft": 200},
            {"customer_id": "CUST-B", "demand_kft": 300},
            {"customer_id": "CUST-C", "demand_kft": 250},
            {"customer_id": "CUST-D", "demand_kft": 150},
        ]

    # Try to read shipping costs
    try:
        cur.execute("SELECT plant_id, customer_id, cost_per_kft FROM shipping_costs")
        cost_rows = _fetch_all_dicts(cur)
        cost_map = {(r["plant_id"], r["customer_id"]): r["cost_per_kft"]
                    for r in cost_rows}
    except sqlite3.OperationalError:
        # Generate synthetic costs
        rng = random.Random(42)
        cost_map = {}
        for p in plants:
            for c in customers:
                cost_map[(p["plant_id"], c["customer_id"])] = round(rng.uniform(2, 10), 2)

    prob = LpProblem("Transportation", LpMinimize)

    x = {}
    for p in plants:
        for c in customers:
            key = (p["plant_id"], c["customer_id"])
            x[key] = LpVariable(f"ship_{p['plant_id']}_{c['customer_id']}",
                                lowBound=0, cat=LpContinuous)

    # Objective
    obj_terms = []
    for p in plants:
        for c in customers:
            key = (p["plant_id"], c["customer_id"])
            unit_cost = cost_map.get(key, 5.0)
            obj_terms.append(unit_cost * x[key])
    prob += lpSum(obj_terms)

    # Supply constraints
    for p in plants:
        terms = [x[(p["plant_id"], c["customer_id"])] for c in customers]
        prob += lpSum(terms) <= p["capacity_kft"], f"Supply_{p['plant_id']}"

    # Demand constraints
    for c in customers:
        terms = [x[(p["plant_id"], c["customer_id"])] for p in plants]
        prob += lpSum(terms) >= c["demand_kft"], f"Demand_{c['customer_id']}"

    prob.solve()
    status = prob.status
    status_str = {1: "Optimal", 0: "Not Solved", -1: "Infeasible",
                  -2: "Unbounded", -3: "Undefined"}.get(status, str(status))

    total_cost = value(prob.objective) if prob.objective else 0.0

    shipments = {}
    for p in plants:
        for c in customers:
            key = (p["plant_id"], c["customer_id"])
            val = _safe_value(x[key])
            if val > 0.01:
                shipments[f"{p['plant_id']}->{c['customer_id']}"] = round(val, 2)

    plant_usage = {}
    for p in plants:
        used = sum(_safe_value(x[(p["plant_id"], c["customer_id"])]) for c in customers)
        plant_usage[p["plant_id"]] = {
            "used": round(used, 2),
            "capacity": p["capacity_kft"],
            "utilization_pct": round(used / p["capacity_kft"] * 100, 1) if p["capacity_kft"] > 0 else 0,
        }

    cust_demand = {}
    for c in customers:
        received = sum(_safe_value(x[(p["plant_id"], c["customer_id"])]) for p in plants)
        cust_demand[c["customer_id"]] = {
            "received": round(received, 2),
            "demand": c["demand_kft"],
            "satisfied": received >= c["demand_kft"] - 0.01,
        }

    return status_str, round(total_cost, 2), shipments, plant_usage, cust_demand


# ===================================================================
# P10 - Campaign / Batch Scheduling
# ===================================================================

def solve_p10_campaign_batch(conn):
    """
    Campaign scheduling: group WOs by product family, minimize changeover.

    Uses 2-opt local search on family sequence to minimize total changeover.

    Returns (best_sequence, best_changeover, random_changeover,
             campaign_schedule, family_groups)
    """
    cur = conn.cursor()

    # Get WOs with family info
    cur.execute("""
        SELECT wo.wo_id, wo.product_id, wo.order_qty_kft,
               p.family
        FROM work_orders wo
        JOIN products p ON wo.product_id = p.product_id
        WHERE wo.status != 'cancelled'
        ORDER BY wo.wo_id
    """)
    rows = _fetch_all_dicts(cur)

    # Group by family
    family_groups = defaultdict(list)
    for r in rows:
        family = r.get("family", "X") or "X"
        family_groups[family].append(r)
    family_groups = dict(family_groups)

    # Get changeover matrix
    cur.execute("SELECT from_product, to_product, setup_minutes FROM changeover_matrix")
    changeover = {}
    for row in cur.fetchall():
        changeover[(row[0], row[1])] = row[2]

    def inter_family_changeover(fam_a, fam_b):
        """Estimate changeover between two families."""
        if fam_a == fam_b:
            return 0.0
        wos_a = family_groups.get(fam_a, [])
        wos_b = family_groups.get(fam_b, [])
        if not wos_a or not wos_b:
            return 30.0  # default 30 min
        # Use last product of A, first product of B
        last_a = wos_a[-1]["product_id"]
        first_b = wos_b[0]["product_id"]
        return changeover.get((last_a, first_b), 30.0)

    def intra_family_changeover(family):
        """Total changeover within a family campaign."""
        wos = family_groups.get(family, [])
        total = 0.0
        for i in range(1, len(wos)):
            p1 = wos[i - 1]["product_id"]
            p2 = wos[i]["product_id"]
            total += changeover.get((p1, p2), 5.0)  # small intra-family
        return total

    families = list(family_groups.keys())
    n_fam = len(families)

    def total_changeover(seq):
        """Total changeover for a family sequence."""
        total = 0.0
        for fam in seq:
            total += intra_family_changeover(fam)
        for i in range(1, len(seq)):
            total += inter_family_changeover(seq[i - 1], seq[i])
        return total

    # Random baseline
    rng = random.Random(42)
    random_seq = families[:]
    rng.shuffle(random_seq)
    random_changeover = total_changeover(random_seq)

    # 2-opt improvement
    best_seq = families[:]
    best_co = total_changeover(best_seq)

    # Try all permutations if small, else 2-opt
    if n_fam <= 8:
        for perm in permutations(families):
            co = total_changeover(list(perm))
            if co < best_co:
                best_co = co
                best_seq = list(perm)
    else:
        # 2-opt
        improved = True
        while improved:
            improved = False
            for i in range(n_fam - 1):
                for j in range(i + 1, n_fam):
                    new_seq = best_seq[:]
                    new_seq[i], new_seq[j] = new_seq[j], new_seq[i]
                    new_co = total_changeover(new_seq)
                    if new_co < best_co:
                        best_co = new_co
                        best_seq = new_seq
                        improved = True

    # Build campaign schedule
    campaign_schedule = []
    current_time = 0.0
    for idx, fam in enumerate(best_seq):
        wos = family_groups.get(fam, [])
        if idx > 0:
            co_time = inter_family_changeover(best_seq[idx - 1], fam)
            current_time += co_time

        campaign_start = current_time
        for wo in wos:
            campaign_schedule.append({
                "family": fam,
                "wo_id": wo["wo_id"],
                "product_id": wo["product_id"],
                "qty_kft": wo["order_qty_kft"],
                "start_min": round(current_time, 2),
            })
            # Estimate processing time (rough: 10 min per kft)
            current_time += wo["order_qty_kft"] * 10.0

    # Convert family_groups values to serializable format
    fg_summary = {}
    for fam, wos in family_groups.items():
        fg_summary[fam] = {
            "count": len(wos),
            "total_qty_kft": sum(w["order_qty_kft"] for w in wos),
            "products": list(set(w["product_id"] for w in wos)),
        }

    return (best_seq, round(best_co, 2), round(random_changeover, 2),
            campaign_schedule, fg_summary)


# ===================================================================
# P11 - Cut / Reel Optimization (FFD Bin Packing)
# ===================================================================

def solve_p11_cut_reel(conn):
    """
    First Fit Decreasing (FFD) bin-packing to assign WO footage to reels,
    minimizing trim waste.

    Returns (waste_pct, reels, stats_dict)
    """
    cur = conn.cursor()

    # Get reel capacity
    try:
        cur.execute("SELECT reel_type_id, max_footage_ft FROM reel_types ORDER BY max_footage_ft DESC")
        reel_types = _fetch_all_dicts(cur)
    except sqlite3.OperationalError:
        reel_types = [{"reel_type_id": "REEL-STD", "max_footage_ft": 5000}]

    reel_cap = reel_types[0]["max_footage_ft"] if reel_types else 5000
    reel_type = reel_types[0]["reel_type_id"] if reel_types else "REEL-STD"

    # Get work order footage
    cur.execute("""
        SELECT wo_id, product_id, order_qty_kft
        FROM work_orders WHERE status != 'cancelled'
        ORDER BY wo_id
    """)
    rows = _fetch_all_dicts(cur)

    # Convert kft to ft and create cut items
    items = []
    for r in rows:
        footage = r["order_qty_kft"] * 1000.0  # kft -> ft
        # If footage > reel capacity, split into multiple items
        while footage > reel_cap:
            items.append({
                "wo_id": r["wo_id"],
                "product_id": r["product_id"],
                "footage_ft": reel_cap,
            })
            footage -= reel_cap
        if footage > 0:
            items.append({
                "wo_id": r["wo_id"],
                "product_id": r["product_id"],
                "footage_ft": footage,
            })

    # Sort descending by footage (FFD)
    items.sort(key=lambda x: x["footage_ft"], reverse=True)

    # Bin packing
    reels = []  # each reel: {"reel_id": str, "items": [...], "used_ft": float, "remaining_ft": float}

    for item in items:
        placed = False
        for reel in reels:
            if reel["remaining_ft"] >= item["footage_ft"]:
                reel["items"].append(item)
                reel["used_ft"] += item["footage_ft"]
                reel["remaining_ft"] -= item["footage_ft"]
                placed = True
                break

        if not placed:
            reel_id = f"{reel_type}-{len(reels) + 1:03d}"
            reels.append({
                "reel_id": reel_id,
                "reel_type": reel_type,
                "capacity_ft": reel_cap,
                "items": [item],
                "used_ft": item["footage_ft"],
                "remaining_ft": reel_cap - item["footage_ft"],
            })

    # Stats
    total_capacity = len(reels) * reel_cap
    total_used = sum(r["used_ft"] for r in reels)
    total_waste = total_capacity - total_used
    waste_pct = (total_waste / total_capacity * 100.0) if total_capacity > 0 else 0.0

    # Utilization per reel
    utilizations = [r["used_ft"] / r["capacity_ft"] * 100 for r in reels] if reels else [0]

    stats = {
        "num_reels": len(reels),
        "total_capacity_ft": total_capacity,
        "total_used_ft": total_used,
        "total_waste_ft": total_waste,
        "waste_pct": round(waste_pct, 2),
        "avg_utilization_pct": round(sum(utilizations) / len(utilizations), 2) if utilizations else 0,
        "min_utilization_pct": round(min(utilizations), 2) if utilizations else 0,
        "max_utilization_pct": round(max(utilizations), 2) if utilizations else 0,
        "num_items_packed": len(items),
        "reel_type": reel_type,
        "reel_capacity_ft": reel_cap,
    }

    # Simplify reel output for serialization
    reel_output = []
    for r in reels:
        reel_output.append({
            "reel_id": r["reel_id"],
            "reel_type": r["reel_type"],
            "capacity_ft": r["capacity_ft"],
            "used_ft": round(r["used_ft"], 2),
            "remaining_ft": round(r["remaining_ft"], 2),
            "utilization_pct": round(r["used_ft"] / r["capacity_ft"] * 100, 2) if r["capacity_ft"] > 0 else 0,
            "num_items": len(r["items"]),
            "items": [{
                "wo_id": it["wo_id"],
                "product_id": it["product_id"],
                "footage_ft": round(it["footage_ft"], 2),
            } for it in r["items"]],
        })

    return round(waste_pct, 2), reel_output, stats


# ===================================================================
# Main (smoke test)
# ===================================================================

if __name__ == "__main__":
    print("scheduling.py loaded successfully.")
    print("Available solvers:")
    solvers = [
        "P1  solve_p1_product_mix        - Product mix LP",
        "P2  solve_p2_wo_acceptance      - WO acceptance binary IP",
        "P3  solve_p3_single_machine     - Single machine (WSPT/EDD/Moore)",
        "P4  solve_p4_parallel_machines  - Parallel machines (LPT)",
        "P5a solve_p5_flow_shop          - Flow shop (Johnson's Rule)",
        "P5b solve_p5_flow_shop_neh      - Flow shop (NEH heuristic)",
        "P6  solve_p6_supply_chain       - Supply chain multi-period LP",
        "P7  solve_p7_metaheuristics     - SA / GA metaheuristics",
        "P8  solve_p8_resource_allocation- Resource allocation assignment LP",
        "P9  solve_p9_transportation     - Transportation LP",
        "P10 solve_p10_campaign_batch    - Campaign batch scheduling",
        "P11 solve_p11_cut_reel          - Cut/reel FFD bin packing",
    ]
    for s in solvers:
        print(f"  {s}")
