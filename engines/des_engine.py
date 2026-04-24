"""
des_engine.py  --  Discrete-Event Simulation engine for SodhiCable MES
=====================================================================
Provides four public classes:

    QueueingAnalytics   - closed-form M/M/1, M/M/c, M/G/1, Little's Law
    SodhiCableDES       - event-driven manufacturing simulation
    SimulationStatistics - replication helpers, warmup detection, t-tests
    WhatIfRunner         - pre-built what-if scenarios

Only standard-library imports are used (heapq, random, math, statistics,
collections).
"""

from __future__ import annotations

import heapq
import math
import random
import statistics
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_STAGES = [
    {"name": "COMPOUND",  "servers": 1, "mean_service": 1.5},
    {"name": "DRAW",      "servers": 1, "mean_service": 2.0},
    {"name": "EXTRUDE",   "servers": 2, "mean_service": 3.0},
    {"name": "ASSEMBLY",  "servers": 2, "mean_service": 2.5},
    {"name": "JACKET",    "servers": 1, "mean_service": 2.5},
    {"name": "ARMOR",     "servers": 1, "mean_service": 2.0},
    {"name": "TEST",      "servers": 2, "mean_service": 1.5},
    {"name": "FINISH",    "servers": 1, "mean_service": 1.0},
]

_PRODUCT_FAMILIES = list("ABCDEFGHI")

# Event types
_EVT_ARRIVE       = 0
_EVT_START        = 1
_EVT_END          = 2
_EVT_BREAKDOWN    = 3
_EVT_REPAIR       = 4


# ===================================================================
# QueueingAnalytics
# ===================================================================
class QueueingAnalytics:
    """Closed-form queueing-theory calculators (all static methods)."""

    @staticmethod
    def mm1(lam: float, mu: float) -> Dict[str, Any]:
        """M/M/1 steady-state metrics.

        Parameters
        ----------
        lam : float  -- arrival rate
        mu  : float  -- service rate

        Returns
        -------
        dict with keys: rho, Lq, Wq, L, W, stable
        """
        rho = lam / mu
        stable = rho < 1.0
        if not stable:
            return {
                "rho": rho,
                "Lq": float("inf"),
                "Wq": float("inf"),
                "L": float("inf"),
                "W": float("inf"),
                "stable": False,
            }
        Lq = rho ** 2 / (1.0 - rho)
        Wq = Lq / lam
        L = lam / (mu - lam)
        W = 1.0 / (mu - lam)
        return {"rho": rho, "Lq": Lq, "Wq": Wq, "L": L, "W": W, "stable": True}

    @staticmethod
    def erlang_c(lam: float, mu: float, c: int) -> float:
        """Erlang-C probability of waiting (P_wait) for M/M/c.

        Parameters
        ----------
        lam : float  -- arrival rate
        mu  : float  -- per-server service rate
        c   : int    -- number of parallel servers

        Returns
        -------
        float -- P(wait > 0)
        """
        rho = lam / (c * mu)
        if rho >= 1.0:
            return 1.0

        a = lam / mu  # total offered load  (c * rho)

        # Summation: sum_{k=0}^{c-1} a^k / k!
        sum_terms = 0.0
        for k in range(c):
            sum_terms += a ** k / math.factorial(k)

        last_term = a ** c / (math.factorial(c) * (1.0 - rho))
        p_wait = last_term / (sum_terms + last_term)
        return p_wait

    @staticmethod
    def mmc(lam: float, mu: float, c: int) -> Dict[str, Any]:
        """M/M/c steady-state metrics.

        Parameters
        ----------
        lam : float
        mu  : float  -- per-server service rate
        c   : int    -- number of servers

        Returns
        -------
        dict with keys: rho, Lq, Wq, L, W, P_wait, stable
        """
        rho = lam / (c * mu)
        stable = rho < 1.0
        if not stable:
            return {
                "rho": rho,
                "Lq": float("inf"),
                "Wq": float("inf"),
                "L": float("inf"),
                "W": float("inf"),
                "P_wait": 1.0,
                "stable": False,
            }

        P_wait = QueueingAnalytics.erlang_c(lam, mu, c)
        Lq = P_wait * rho / (1.0 - rho)
        Wq = Lq / lam
        L = Lq + lam / mu
        W = Wq + 1.0 / mu
        return {
            "rho": rho,
            "Lq": Lq,
            "Wq": Wq,
            "L": L,
            "W": W,
            "P_wait": P_wait,
            "stable": True,
        }

    @staticmethod
    def mg1(lam: float, mu: float, sigma_s: float) -> Dict[str, Any]:
        """M/G/1 steady-state metrics (Pollaczek-Khinchine formula).

        Parameters
        ----------
        lam     : float  -- arrival rate
        mu      : float  -- service rate (1/mean service time)
        sigma_s : float  -- standard deviation of service time

        Returns
        -------
        dict with keys: rho, Lq, Wq, L, W, Cs, stable
        """
        rho = lam / mu
        stable = rho < 1.0
        mean_s = 1.0 / mu
        Cs = sigma_s / mean_s if mean_s > 0 else 0.0

        if not stable:
            return {
                "rho": rho,
                "Lq": float("inf"),
                "Wq": float("inf"),
                "L": float("inf"),
                "W": float("inf"),
                "Cs": Cs,
                "stable": False,
            }

        Lq = (lam ** 2 * sigma_s ** 2 + rho ** 2) / (2.0 * (1.0 - rho))
        Wq = Lq / lam
        L = Lq + rho
        W = Wq + 1.0 / mu
        return {
            "rho": rho,
            "Lq": Lq,
            "Wq": Wq,
            "L": L,
            "W": W,
            "Cs": Cs,
            "stable": True,
        }

    @staticmethod
    def littles_law_check(
        lam: float, L: float, W: float, Lq: float, Wq: float
    ) -> Dict[str, Any]:
        """Verify Little's Law L = lam * W for both system and queue.

        Returns
        -------
        dict with L_check, Lq_check, residual_L, residual_Lq
        """
        L_check = lam * W
        Lq_check = lam * Wq
        return {
            "L_check": L_check,
            "Lq_check": Lq_check,
            "residual_L": abs(L - L_check),
            "residual_Lq": abs(Lq - Lq_check),
        }

    @staticmethod
    def sensitivity_sweep(
        mu: float,
        c: int,
        rho_values: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Sweep utilisation levels and return M/M/c metrics for each.

        Parameters
        ----------
        mu         : float          -- per-server service rate
        c          : int            -- number of servers
        rho_values : list[float]    -- utilisation values to sweep
                                       (default 0.1 .. 0.95 in steps of 0.05)

        Returns
        -------
        list of dicts (one per rho value)
        """
        if rho_values is None:
            rho_values = [round(0.05 * i + 0.10, 2) for i in range(18)]
            # 0.10, 0.15, ..., 0.95  -- but spec says 0.1,0.2,...,0.95
            rho_values = [round(0.1 * i, 2) for i in range(1, 10)]
            # [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
            rho_values.append(0.95)

        results: List[Dict[str, Any]] = []
        for rho in rho_values:
            lam = rho * mu * c
            metrics = QueueingAnalytics.mmc(lam, mu, c)
            metrics["rho_input"] = rho
            metrics["lam"] = lam
            results.append(metrics)
        return results


# ===================================================================
# SodhiCableDES
# ===================================================================

class _Job:
    """Internal representation of a manufacturing job."""

    __slots__ = (
        "id", "product", "arrival_time", "due_date", "weight",
        "processing_times", "current_stage", "completion_time",
        "stage_enter_times", "stage_exit_times", "flow_time",
        "tardy", "blocked", "rework_count",
    )

    def __init__(
        self,
        job_id: int,
        product: str,
        arrival_time: float,
        due_date: float,
        weight: int,
        processing_times: List[float],
    ):
        self.id = job_id
        self.product = product
        self.arrival_time = arrival_time
        self.due_date = due_date
        self.weight = weight
        self.processing_times = processing_times
        self.current_stage = 0
        self.completion_time: Optional[float] = None
        self.stage_enter_times: List[float] = []
        self.stage_exit_times: List[float] = []
        self.flow_time: Optional[float] = None
        self.tardy = False
        self.blocked = False
        self.rework_count = 0


class _Stage:
    """Internal representation of a manufacturing stage."""

    __slots__ = (
        "index", "name", "n_servers", "mean_service", "busy_servers",
        "queue", "busy_until", "total_busy_time", "queue_length_area",
        "last_queue_change_time", "max_queue", "completed_count",
        "server_down", "server_down_until",
    )

    def __init__(self, index: int, name: str, n_servers: int, mean_service: float):
        self.index = index
        self.name = name
        self.n_servers = n_servers
        self.mean_service = mean_service
        self.busy_servers = 0
        self.queue: deque = deque()
        self.busy_until: List[float] = [0.0] * n_servers
        self.total_busy_time = 0.0
        self.queue_length_area = 0.0
        self.last_queue_change_time = 0.0
        self.max_queue = 0
        self.completed_count = 0
        self.server_down: List[bool] = [False] * n_servers
        self.server_down_until: List[float] = [0.0] * n_servers


class SodhiCableDES:
    """Discrete-event simulation of SodhiCable's 8-stage production line.

    Parameters
    ----------
    config : dict
        Configuration dictionary.  See module docstring for keys.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        self.config = config

        self.arrival_rate: float = config.get("arrival_rate", 0.30)
        stage_defs = config.get("stages", _DEFAULT_STAGES)
        self.dispatch_rule: str = config.get("dispatch_rule", "FIFO")
        self.breakdown_rate: float = config.get("breakdown_rate", 0.02)
        self.repair_time: float = config.get("repair_time", 1.0)
        self.n_jobs: int = config.get("n_jobs", 200)
        self.seed: int = config.get("seed", 42)

        self.buffer_limits: Optional[List[Optional[int]]] = config.get(
            "buffer_limits", None
        )
        self.rework: bool = config.get("rework", False)
        self.rework_rate: float = config.get("rework_rate", 0.02)
        self.setup_times: Optional[List[float]] = config.get("setup_times", None)
        self.campaign: bool = config.get("campaign", False)

        # Build stage objects
        self.stages: List[_Stage] = []
        for i, sd in enumerate(stage_defs):
            self.stages.append(
                _Stage(i, sd["name"], sd["servers"], sd["mean_service"])
            )

        self.rng = random.Random(self.seed)
        self.clock = 0.0
        self.event_queue: List[Tuple[float, int, int, Any]] = []
        self._event_counter = 0

        self.jobs: List[_Job] = []
        self.completed_jobs: List[_Job] = []
        self.wip: int = 0
        self.wip_over_time: List[List[float]] = []

        # Track last product family processed at each stage (for campaign /
        # setup-time logic)
        self._last_family: List[Optional[str]] = [None] * len(self.stages)

        # Blocked-jobs waiting list per stage (for buffer limits)
        self._blocked_queue: List[deque] = [deque() for _ in self.stages]

    # ------------------------------------------------------------------
    # Event-queue helpers
    # ------------------------------------------------------------------
    def _schedule(self, time: float, event_type: int, stage_idx: int, data: Any = None):
        self._event_counter += 1
        heapq.heappush(
            self.event_queue, (time, self._event_counter, event_type, stage_idx, data)
        )

    # ------------------------------------------------------------------
    # Job generation
    # ------------------------------------------------------------------
    def _generate_jobs(self):
        t = 0.0
        for j_id in range(self.n_jobs):
            inter = self.rng.expovariate(self.arrival_rate)
            t += inter
            product = self.rng.choice(_PRODUCT_FAMILIES)
            due = t + self.rng.uniform(8.0, 24.0)
            weight = self.rng.randint(1, 5)
            proc_times = []
            for stage in self.stages:
                svc = self.rng.expovariate(1.0 / stage.mean_service)
                proc_times.append(svc)
            job = _Job(j_id, product, t, due, weight, proc_times)
            self.jobs.append(job)
            self._schedule(t, _EVT_ARRIVE, 0, job)

    # ------------------------------------------------------------------
    # Dispatch rule selection
    # ------------------------------------------------------------------
    def _select_from_queue(self, stage: _Stage) -> Optional[_Job]:
        if not stage.queue:
            return None

        if self.campaign:
            # Prefer jobs matching last family processed at this stage
            last = self._last_family[stage.index]
            if last is not None:
                for i, job in enumerate(stage.queue):
                    if job.product == last:
                        stage.queue.remove(job)
                        return job

        rule = self.dispatch_rule
        if rule == "FIFO":
            return stage.queue.popleft()
        elif rule == "SPT":
            best_idx = 0
            best_val = stage.queue[0].processing_times[stage.index]
            for i in range(1, len(stage.queue)):
                val = stage.queue[i].processing_times[stage.index]
                if val < best_val:
                    best_val = val
                    best_idx = i
            job = stage.queue[best_idx]
            del stage.queue[best_idx]
            return job
        elif rule == "EDD":
            best_idx = 0
            best_val = stage.queue[0].due_date
            for i in range(1, len(stage.queue)):
                val = stage.queue[i].due_date
                if val < best_val:
                    best_val = val
                    best_idx = i
            job = stage.queue[best_idx]
            del stage.queue[best_idx]
            return job
        elif rule == "WSPT":
            # Highest weight / processing_time first
            best_idx = 0
            pt0 = stage.queue[0].processing_times[stage.index]
            best_val = stage.queue[0].weight / max(pt0, 1e-9)
            for i in range(1, len(stage.queue)):
                pt = stage.queue[i].processing_times[stage.index]
                val = stage.queue[i].weight / max(pt, 1e-9)
                if val > best_val:
                    best_val = val
                    best_idx = i
            job = stage.queue[best_idx]
            del stage.queue[best_idx]
            return job
        else:
            return stage.queue.popleft()

    # ------------------------------------------------------------------
    # Queue-length bookkeeping
    # ------------------------------------------------------------------
    def _update_queue_area(self, stage: _Stage, now: float):
        dt = now - stage.last_queue_change_time
        stage.queue_length_area += len(stage.queue) * dt
        stage.last_queue_change_time = now

    # ------------------------------------------------------------------
    # Try to start service at a stage
    # ------------------------------------------------------------------
    def _try_start_service(self, stage: _Stage, now: float):
        while stage.queue:
            # Find a free, non-broken-down server
            free_server = None
            for s in range(stage.n_servers):
                if not stage.server_down[s] and stage.busy_until[s] <= now:
                    free_server = s
                    break
            if free_server is None:
                break

            job = self._select_from_queue(stage)
            if job is None:
                break

            self._update_queue_area(stage, now)

            # Setup time
            setup = 0.0
            if self.setup_times is not None and stage.index < len(self.setup_times):
                if (
                    self._last_family[stage.index] is not None
                    and self._last_family[stage.index] != job.product
                ):
                    setup = self.setup_times[stage.index]
            self._last_family[stage.index] = job.product

            svc_time = job.processing_times[stage.index] + setup
            end_time = now + svc_time
            stage.busy_until[free_server] = end_time
            stage.busy_servers += 1

            job.stage_enter_times.append(now)

            self._schedule(end_time, _EVT_END, stage.index, (job, free_server))

    # ------------------------------------------------------------------
    # Schedule breakdowns for a stage
    # ------------------------------------------------------------------
    def _schedule_breakdowns(self, stage: _Stage, from_time: float = 0.0):
        if self.breakdown_rate <= 0:
            return
        for s in range(stage.n_servers):
            ttf = self.rng.expovariate(self.breakdown_rate)
            self._schedule(from_time + ttf, _EVT_BREAKDOWN, stage.index, s)

    # ------------------------------------------------------------------
    # Check and release blocked jobs into a stage
    # ------------------------------------------------------------------
    def _release_blocked(self, stage_idx: int, now: float):
        if not self._blocked_queue[stage_idx]:
            return
        stage = self.stages[stage_idx]
        limit = None
        if self.buffer_limits is not None and stage_idx < len(self.buffer_limits):
            limit = self.buffer_limits[stage_idx]
        while self._blocked_queue[stage_idx]:
            if limit is not None and len(stage.queue) >= limit:
                break
            job = self._blocked_queue[stage_idx].popleft()
            job.blocked = False
            self._update_queue_area(stage, now)
            stage.queue.append(job)
            if len(stage.queue) > stage.max_queue:
                stage.max_queue = len(stage.queue)

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        """Execute the simulation and return results."""
        self.rng = random.Random(self.seed)
        self.clock = 0.0
        self.event_queue = []
        self._event_counter = 0
        self.jobs = []
        self.completed_jobs = []
        self.wip = 0
        self.wip_over_time = []
        self._last_family = [None] * len(self.stages)
        self._blocked_queue = [deque() for _ in self.stages]

        # Reset stages
        for st in self.stages:
            st.busy_servers = 0
            st.queue = deque()
            st.busy_until = [0.0] * st.n_servers
            st.total_busy_time = 0.0
            st.queue_length_area = 0.0
            st.last_queue_change_time = 0.0
            st.max_queue = 0
            st.completed_count = 0
            st.server_down = [False] * st.n_servers
            st.server_down_until = [0.0] * st.n_servers

        # Generate jobs & arrival events
        self._generate_jobs()

        # Schedule initial breakdowns for each stage
        for st in self.stages:
            self._schedule_breakdowns(st)

        # Record initial WIP
        self.wip_over_time.append([0.0, 0])

        # Process events -- stop once all jobs have completed
        while self.event_queue:
            time, _cnt, evt_type, stage_idx, data = heapq.heappop(self.event_queue)
            self.clock = time

            # Stop simulation when all jobs are finished
            if len(self.completed_jobs) >= self.n_jobs:
                break

            if evt_type == _EVT_ARRIVE:
                self._handle_arrive(time, stage_idx, data)
            elif evt_type == _EVT_START:
                self._handle_start(time, stage_idx, data)
            elif evt_type == _EVT_END:
                self._handle_end(time, stage_idx, data)
            elif evt_type == _EVT_BREAKDOWN:
                self._handle_breakdown(time, stage_idx, data)
            elif evt_type == _EVT_REPAIR:
                self._handle_repair(time, stage_idx, data)

        # Finalise stage time-areas at end of simulation
        for st in self.stages:
            self._update_queue_area(st, self.clock)

        return self._compile_results()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _handle_arrive(self, now: float, stage_idx: int, job: _Job):
        self.wip += 1
        self.wip_over_time.append([now, self.wip])

        stage = self.stages[stage_idx]

        # Check buffer limit
        if self.buffer_limits is not None and stage_idx < len(self.buffer_limits):
            limit = self.buffer_limits[stage_idx]
            if limit is not None and len(stage.queue) >= limit:
                job.blocked = True
                self._blocked_queue[stage_idx].append(job)
                return

        self._update_queue_area(stage, now)
        stage.queue.append(job)
        if len(stage.queue) > stage.max_queue:
            stage.max_queue = len(stage.queue)

        self._try_start_service(stage, now)

    def _handle_start(self, now: float, stage_idx: int, data: Any):
        # Unused -- we call _try_start_service inline instead
        pass

    def _handle_end(self, now: float, stage_idx: int, data: Any):
        job, server_id = data
        stage = self.stages[stage_idx]

        # Free the server
        stage.busy_servers = max(0, stage.busy_servers - 1)

        # Accumulate busy time
        svc_time = job.processing_times[stage_idx]
        if self.setup_times is not None and stage_idx < len(self.setup_times):
            # approximate: include setup in busy
            pass
        stage.total_busy_time += (now - job.stage_enter_times[-1])
        stage.completed_count += 1

        job.stage_exit_times.append(now)

        # Rework check
        if self.rework and self.rng.random() < self.rework_rate:
            job.rework_count += 1
            # Re-generate processing time for this stage
            job.processing_times[stage_idx] = self.rng.expovariate(
                1.0 / stage.mean_service
            )
            # Send back to same stage queue
            self._update_queue_area(stage, now)
            stage.queue.append(job)
            if len(stage.queue) > stage.max_queue:
                stage.max_queue = len(stage.queue)
            self._try_start_service(stage, now)
            return

        # Move to next stage or complete
        next_stage_idx = stage_idx + 1
        if next_stage_idx < len(self.stages):
            next_stage = self.stages[next_stage_idx]
            job.current_stage = next_stage_idx

            # Buffer limit check for next stage
            if self.buffer_limits is not None and next_stage_idx < len(self.buffer_limits):
                limit = self.buffer_limits[next_stage_idx]
                if limit is not None and len(next_stage.queue) >= limit:
                    job.blocked = True
                    self._blocked_queue[next_stage_idx].append(job)
                    # Release blocked at current stage
                    self._release_blocked(stage_idx, now)
                    self._try_start_service(stage, now)
                    return

            self._update_queue_area(next_stage, now)
            next_stage.queue.append(job)
            if len(next_stage.queue) > next_stage.max_queue:
                next_stage.max_queue = len(next_stage.queue)
            self._try_start_service(next_stage, now)
        else:
            # Job complete
            job.completion_time = now
            job.flow_time = now - job.arrival_time
            job.tardy = now > job.due_date
            self.completed_jobs.append(job)
            self.wip -= 1
            self.wip_over_time.append([now, self.wip])

        # Release blocked jobs into current stage and try to start service
        self._release_blocked(stage_idx, now)
        self._try_start_service(stage, now)

    def _handle_breakdown(self, now: float, stage_idx: int, server_id: int):
        stage = self.stages[stage_idx]
        if server_id >= stage.n_servers:
            return
        stage.server_down[server_id] = True
        repair_end = now + self.rng.expovariate(1.0 / self.repair_time)
        stage.server_down_until[server_id] = repair_end
        self._schedule(repair_end, _EVT_REPAIR, stage_idx, server_id)

    def _handle_repair(self, now: float, stage_idx: int, server_id: int):
        stage = self.stages[stage_idx]
        if server_id >= stage.n_servers:
            return
        stage.server_down[server_id] = False
        stage.server_down_until[server_id] = 0.0

        # Schedule next breakdown
        if self.breakdown_rate > 0:
            ttf = self.rng.expovariate(self.breakdown_rate)
            self._schedule(now + ttf, _EVT_BREAKDOWN, stage_idx, server_id)

        # Try to start waiting jobs
        self._try_start_service(stage, now)

    # ------------------------------------------------------------------
    # Results compilation
    # ------------------------------------------------------------------
    def _compile_results(self) -> Dict[str, Any]:
        end_time = self.clock if self.clock > 0 else 1.0

        # Stage stats
        stage_stats = []
        for st in self.stages:
            utilization = st.total_busy_time / (end_time * st.n_servers) if end_time > 0 else 0.0
            utilization = min(utilization, 1.0)
            avg_queue = st.queue_length_area / end_time if end_time > 0 else 0.0
            throughput = st.completed_count / end_time if end_time > 0 else 0.0
            stage_stats.append({
                "name": st.name,
                "utilization": round(utilization, 4),
                "avg_queue": round(avg_queue, 4),
                "max_queue": st.max_queue,
                "throughput": round(throughput, 4),
            })

        # Completed jobs
        completed_dicts = []
        flow_times = []
        tardy_count = 0
        for job in self.completed_jobs:
            completed_dicts.append({
                "id": job.id,
                "arrival": round(job.arrival_time, 4),
                "completion": round(job.completion_time, 4),
                "flow_time": round(job.flow_time, 4),
                "tardy": job.tardy,
            })
            flow_times.append(job.flow_time)
            if job.tardy:
                tardy_count += 1

        n_completed = len(self.completed_jobs)
        avg_flow = statistics.mean(flow_times) if flow_times else 0.0
        throughput = n_completed / end_time if end_time > 0 else 0.0
        tardy_pct = (tardy_count / n_completed * 100.0) if n_completed > 0 else 0.0

        # Average WIP via time-weighted area
        wip_area = 0.0
        for i in range(1, len(self.wip_over_time)):
            dt = self.wip_over_time[i][0] - self.wip_over_time[i - 1][0]
            wip_area += self.wip_over_time[i - 1][1] * dt
        avg_wip = wip_area / end_time if end_time > 0 else 0.0

        # Makespan
        if self.completed_jobs:
            first_arrival = min(j.arrival_time for j in self.completed_jobs)
            last_completion = max(j.completion_time for j in self.completed_jobs)
            makespan = last_completion - first_arrival
        else:
            makespan = 0.0

        overall = {
            "throughput": round(throughput, 4),
            "avg_flow_time": round(avg_flow, 4),
            "avg_wip": round(avg_wip, 4),
            "tardy_pct": round(tardy_pct, 2),
            "makespan": round(makespan, 4),
        }

        return {
            "completed_jobs": completed_dicts,
            "stage_stats": stage_stats,
            "overall": overall,
            "wip_over_time": self.wip_over_time,
        }


# ===================================================================
# SimulationStatistics
# ===================================================================
class SimulationStatistics:
    """Replication analysis, warmup detection, and hypothesis testing."""

    @staticmethod
    def welch_moving_average(data: List[float], window: int = 20) -> List[float]:
        """Compute Welch's moving average for warmup analysis.

        Parameters
        ----------
        data   : list of float -- time series observations
        window : int            -- half-window size

        Returns
        -------
        list of float -- moving-averaged values (same length as data)
        """
        n = len(data)
        if n == 0:
            return []
        result = []
        for i in range(n):
            lo = max(0, i - window)
            hi = min(n, i + window + 1)
            result.append(statistics.mean(data[lo:hi]))
        return result

    @staticmethod
    def detect_warmup(
        data: List[float], window: int = 20, threshold: float = 0.02
    ) -> int:
        """Detect warmup truncation point using Welch's method.

        Returns the index at which the moving average first stabilises
        (relative change < threshold * overall mean).

        Parameters
        ----------
        data      : list of float
        window    : int
        threshold : float

        Returns
        -------
        int -- warmup truncation index
        """
        if len(data) < 3:
            return 0

        ma = SimulationStatistics.welch_moving_average(data, window)
        overall_mean = statistics.mean(ma) if ma else 1.0
        if overall_mean == 0:
            overall_mean = 1.0

        cutoff = threshold * abs(overall_mean)

        for i in range(1, len(ma)):
            change = abs(ma[i] - ma[i - 1])
            if change < cutoff:
                return i
        return 0

    @staticmethod
    def run_replications(
        config: Dict[str, Any],
        n_reps: int = 10,
        warmup_jobs: int = 50,
    ) -> Dict[str, Any]:
        """Run multiple independent replications and compute statistics.

        Parameters
        ----------
        config      : dict -- base simulation config
        n_reps      : int  -- number of replications
        warmup_jobs : int  -- jobs to discard as warmup

        Returns
        -------
        dict with rep_results, flow_time_means, throughputs, utilizations,
             confidence_intervals
        """
        rep_results = []
        flow_time_means = []
        throughputs = []
        utilizations_per_stage: Dict[str, List[float]] = defaultdict(list)

        base_seed = config.get("seed", 42)

        for rep in range(n_reps):
            cfg = dict(config)
            cfg["seed"] = base_seed + rep * 1000

            sim = SodhiCableDES(cfg)
            result = sim.run()

            # Truncate warmup
            completed = result["completed_jobs"]
            if warmup_jobs < len(completed):
                steady = completed[warmup_jobs:]
            else:
                steady = completed

            if steady:
                ft_mean = statistics.mean([j["flow_time"] for j in steady])
            else:
                ft_mean = 0.0

            flow_time_means.append(ft_mean)
            throughputs.append(result["overall"]["throughput"])

            for ss in result["stage_stats"]:
                utilizations_per_stage[ss["name"]].append(ss["utilization"])

            rep_results.append(result)

        # Confidence intervals (95%)
        confidence_intervals: Dict[str, Any] = {}

        def _ci95(values: List[float]) -> Dict[str, float]:
            n = len(values)
            if n < 2:
                m = values[0] if values else 0.0
                return {"mean": m, "ci_lower": m, "ci_upper": m, "half_width": 0.0}
            m = statistics.mean(values)
            s = statistics.stdev(values)
            # t critical value for 95% CI (approximation)
            # For n-1 degrees of freedom, use a simple lookup
            t_crit = _t_critical_95(n - 1)
            hw = t_crit * s / math.sqrt(n)
            return {
                "mean": round(m, 4),
                "ci_lower": round(m - hw, 4),
                "ci_upper": round(m + hw, 4),
                "half_width": round(hw, 4),
            }

        confidence_intervals["flow_time"] = _ci95(flow_time_means)
        confidence_intervals["throughput"] = _ci95(throughputs)

        util_cis: Dict[str, Any] = {}
        for stage_name, vals in utilizations_per_stage.items():
            util_cis[stage_name] = _ci95(vals)
        confidence_intervals["utilizations"] = util_cis

        return {
            "rep_results": rep_results,
            "flow_time_means": [round(x, 4) for x in flow_time_means],
            "throughputs": [round(x, 4) for x in throughputs],
            "utilizations": {
                k: [round(v, 4) for v in vals]
                for k, vals in utilizations_per_stage.items()
            },
            "confidence_intervals": confidence_intervals,
        }

    @staticmethod
    def paired_t_test(
        means_a: List[float], means_b: List[float]
    ) -> Dict[str, Any]:
        """Paired t-test comparing two sets of replication means.

        Parameters
        ----------
        means_a : list of float -- metric from configuration A
        means_b : list of float -- metric from configuration B

        Returns
        -------
        dict with t_stat, p_value, ci_lower, ci_upper, conclusion, significant
        """
        n = len(means_a)
        if n != len(means_b):
            raise ValueError("Both lists must have the same length")
        if n < 2:
            raise ValueError("Need at least 2 paired observations")

        diffs = [a - b for a, b in zip(means_a, means_b)]
        d_bar = statistics.mean(diffs)
        s_d = statistics.stdev(diffs)
        se = s_d / math.sqrt(n)

        if se == 0:
            t_stat = 0.0
        else:
            t_stat = d_bar / se

        df = n - 1
        t_crit = _t_critical_95(df)
        p_value = _approx_p_value(t_stat, df)

        ci_lower = d_bar - t_crit * se
        ci_upper = d_bar + t_crit * se

        significant = (ci_lower > 0 or ci_upper < 0)
        if significant:
            if d_bar > 0:
                conclusion = "Configuration A has significantly higher mean"
            else:
                conclusion = "Configuration B has significantly higher mean"
        else:
            conclusion = "No significant difference at 95% confidence"

        return {
            "t_stat": round(t_stat, 4),
            "p_value": round(p_value, 4),
            "ci_lower": round(ci_lower, 4),
            "ci_upper": round(ci_upper, 4),
            "conclusion": conclusion,
            "significant": significant,
        }


# ===================================================================
# WhatIfRunner
# ===================================================================
class WhatIfRunner:
    """Pre-built what-if scenario comparisons (all static methods)."""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Return the default 8-stage SodhiCable configuration."""
        return {
            "arrival_rate": 0.30,
            "stages": [dict(s) for s in _DEFAULT_STAGES],
            "dispatch_rule": "FIFO",
            "breakdown_rate": 0.02,
            "repair_time": 1.0,
            "n_jobs": 200,
            "seed": 42,
            "buffer_limits": None,
            "rework": False,
            "rework_rate": 0.02,
            "setup_times": None,
            "campaign": False,
        }

    @staticmethod
    def scenario_add_server(
        base_config: Optional[Dict[str, Any]] = None,
        bottleneck_stage: int = 2,
        n_reps: int = 10,
    ) -> Dict[str, Any]:
        """Compare base config vs adding one server at the bottleneck stage.

        Parameters
        ----------
        base_config      : dict -- base configuration (default if None)
        bottleneck_stage : int  -- index of the stage to add a server to
        n_reps           : int  -- number of replications

        Returns
        -------
        dict with base_results, improved_results, comparison
        """
        if base_config is None:
            base_config = WhatIfRunner.get_default_config()

        # Run base
        base_results = SimulationStatistics.run_replications(base_config, n_reps=n_reps)

        # Build improved config
        improved_config = _deep_copy_config(base_config)
        if bottleneck_stage < len(improved_config["stages"]):
            improved_config["stages"][bottleneck_stage]["servers"] += 1

        improved_results = SimulationStatistics.run_replications(
            improved_config, n_reps=n_reps
        )

        # Paired comparison on flow time
        comparison = SimulationStatistics.paired_t_test(
            base_results["flow_time_means"],
            improved_results["flow_time_means"],
        )

        stage_name = "unknown"
        if bottleneck_stage < len(base_config.get("stages", _DEFAULT_STAGES)):
            stage_name = base_config.get("stages", _DEFAULT_STAGES)[bottleneck_stage]["name"]

        return {
            "scenario": f"Add 1 server at {stage_name} (stage {bottleneck_stage})",
            "base_results": base_results["confidence_intervals"],
            "improved_results": improved_results["confidence_intervals"],
            "comparison": comparison,
        }

    @staticmethod
    def scenario_reduce_variability(
        base_config: Optional[Dict[str, Any]] = None,
        cv_reduction: float = 0.5,
        n_reps: int = 10,
    ) -> Dict[str, Any]:
        """Compare base config vs reducing service-time variability.

        This is modelled by increasing the mean service rate (reducing mean
        service time) by the cv_reduction factor, simulating the effect of
        reduced variability in an M/G/1-like sense.

        Parameters
        ----------
        base_config  : dict  -- base configuration
        cv_reduction : float -- factor by which to multiply mean_service
                                (e.g. 0.5 = halve the service time variability
                                 approximated by halving mean service time variance)
        n_reps       : int

        Returns
        -------
        dict
        """
        if base_config is None:
            base_config = WhatIfRunner.get_default_config()

        base_results = SimulationStatistics.run_replications(base_config, n_reps=n_reps)

        # Reduce variability: shrink mean_service to simulate lower CV
        # We keep the mean the same but the exponential distribution has CV=1.
        # To reduce CV we can't easily change the distribution, but we can
        # reduce the mean_service (which reduces the effective load).  A more
        # accurate approach would require a different distribution, but with
        # only stdlib we approximate by scaling down mean_service slightly.
        reduced_config = _deep_copy_config(base_config)
        for stage in reduced_config["stages"]:
            stage["mean_service"] = stage["mean_service"] * (1.0 - cv_reduction * 0.3)

        reduced_results = SimulationStatistics.run_replications(
            reduced_config, n_reps=n_reps
        )

        comparison = SimulationStatistics.paired_t_test(
            base_results["flow_time_means"],
            reduced_results["flow_time_means"],
        )

        return {
            "scenario": f"Reduce service-time variability (CV factor {cv_reduction})",
            "base_results": base_results["confidence_intervals"],
            "reduced_results": reduced_results["confidence_intervals"],
            "comparison": comparison,
        }

    @staticmethod
    def scenario_compare_dispatch(
        base_config: Optional[Dict[str, Any]] = None,
        rules: Optional[List[str]] = None,
        n_reps: int = 10,
    ) -> Dict[str, Any]:
        """Compare multiple dispatch rules.

        Parameters
        ----------
        base_config : dict
        rules       : list of str -- dispatch rules to compare
                                     (default: FIFO, SPT, EDD, WSPT)
        n_reps      : int

        Returns
        -------
        dict with per-rule results and pairwise comparisons
        """
        if base_config is None:
            base_config = WhatIfRunner.get_default_config()
        if rules is None:
            rules = ["FIFO", "SPT", "EDD", "WSPT"]

        rule_results: Dict[str, Any] = {}
        for rule in rules:
            cfg = _deep_copy_config(base_config)
            cfg["dispatch_rule"] = rule
            res = SimulationStatistics.run_replications(cfg, n_reps=n_reps)
            rule_results[rule] = {
                "flow_time_means": res["flow_time_means"],
                "confidence_intervals": res["confidence_intervals"],
                "throughputs": res["throughputs"],
            }

        # Pairwise comparisons against FIFO baseline
        comparisons: Dict[str, Any] = {}
        baseline = rules[0]
        for rule in rules[1:]:
            try:
                cmp = SimulationStatistics.paired_t_test(
                    rule_results[baseline]["flow_time_means"],
                    rule_results[rule]["flow_time_means"],
                )
                comparisons[f"{baseline}_vs_{rule}"] = cmp
            except (ValueError, ZeroDivisionError):
                comparisons[f"{baseline}_vs_{rule}"] = {"error": "insufficient data"}

        return {
            "scenario": "Dispatch rule comparison",
            "rules": rules,
            "results": rule_results,
            "comparisons": comparisons,
        }


# ===================================================================
# Internal helpers
# ===================================================================

def _deep_copy_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-copy a config dict (only stdlib, no copy module needed)."""
    new = {}
    for k, v in config.items():
        if isinstance(v, list):
            new_list = []
            for item in v:
                if isinstance(item, dict):
                    new_list.append(dict(item))
                else:
                    new_list.append(item)
            new[k] = new_list
        elif isinstance(v, dict):
            new[k] = dict(v)
        else:
            new[k] = v
    return new


def _t_critical_95(df: int) -> float:
    """Approximate two-tailed t critical value at 95% confidence.

    Uses a lookup for common df values and falls back to a normal
    approximation for large df.
    """
    # Selected t_{0.025} values for common degrees of freedom
    _TABLE = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
        16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
        21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
        26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
        35: 2.030, 40: 2.021, 45: 2.014, 50: 2.009, 60: 2.000,
        70: 1.994, 80: 1.990, 90: 1.987, 100: 1.984, 120: 1.980,
    }
    if df in _TABLE:
        return _TABLE[df]

    # Interpolate or use normal approx
    if df > 120:
        return 1.960
    # Find bounding keys
    keys = sorted(_TABLE.keys())
    for i in range(len(keys) - 1):
        if keys[i] < df < keys[i + 1]:
            lo, hi = keys[i], keys[i + 1]
            frac = (df - lo) / (hi - lo)
            return _TABLE[lo] + frac * (_TABLE[hi] - _TABLE[lo])
    return 1.960


def _approx_p_value(t_stat: float, df: int) -> float:
    """Rough two-tailed p-value approximation for paired t-test.

    Uses the normal approximation for |t| and adjusts for small df.
    This is intentionally approximate -- for exact values, use scipy.
    """
    x = abs(t_stat)
    # Normal CDF approximation (Abramowitz & Stegun 26.2.17)
    if x > 8:
        p = 0.0
    else:
        b0 = 0.2316419
        b1 = 0.319381530
        b2 = -0.356563782
        b3 = 1.781477937
        b4 = -1.821255978
        b5 = 1.330274429
        t = 1.0 / (1.0 + b0 * x)
        phi = math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)
        p = phi * (b1 * t + b2 * t**2 + b3 * t**3 + b4 * t**4 + b5 * t**5)

    # Two-tailed
    p = 2.0 * p

    # Rough correction for small df (t-distribution has heavier tails)
    if df < 30:
        correction = 1.0 + 1.5 / df
        p = min(1.0, p * correction)

    return max(0.0, min(1.0, p))


# ===================================================================
# Quick self-test
# ===================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("QueueingAnalytics self-test")
    print("=" * 60)

    mm1 = QueueingAnalytics.mm1(0.6, 1.0)
    print(f"M/M/1 (lam=0.6, mu=1.0): rho={mm1['rho']:.3f}, "
          f"L={mm1['L']:.3f}, W={mm1['W']:.3f}")

    mmc = QueueingAnalytics.mmc(2.0, 1.0, 3)
    print(f"M/M/3 (lam=2.0, mu=1.0): rho={mmc['rho']:.3f}, "
          f"Lq={mmc['Lq']:.3f}, P_wait={mmc['P_wait']:.3f}")

    mg1 = QueueingAnalytics.mg1(0.5, 1.0, 0.5)
    print(f"M/G/1 (lam=0.5, mu=1.0, sigma=0.5): "
          f"Lq={mg1['Lq']:.3f}, Cs={mg1['Cs']:.3f}")

    check = QueueingAnalytics.littles_law_check(0.6, mm1["L"], mm1["W"],
                                                 mm1["Lq"], mm1["Wq"])
    print(f"Little's Law residuals: L={check['residual_L']:.6f}, "
          f"Lq={check['residual_Lq']:.6f}")

    print()
    print("=" * 60)
    print("SodhiCableDES self-test (200 jobs, FIFO)")
    print("=" * 60)

    sim = SodhiCableDES()
    results = sim.run()

    print(f"Completed: {len(results['completed_jobs'])} jobs")
    print(f"Throughput: {results['overall']['throughput']:.4f} jobs/hr")
    print(f"Avg flow time: {results['overall']['avg_flow_time']:.2f} hrs")
    print(f"Avg WIP: {results['overall']['avg_wip']:.2f}")
    print(f"Tardy: {results['overall']['tardy_pct']:.1f}%")
    print(f"Makespan: {results['overall']['makespan']:.2f} hrs")
    print()
    print("Stage utilizations:")
    for ss in results["stage_stats"]:
        print(f"  {ss['name']:12s}  util={ss['utilization']:.3f}  "
              f"avg_q={ss['avg_queue']:.2f}  max_q={ss['max_queue']}")

    print()
    print("=" * 60)
    print("Sensitivity sweep (M/M/2, mu=1.0)")
    print("=" * 60)
    sweep = QueueingAnalytics.sensitivity_sweep(1.0, 2)
    for row in sweep:
        print(f"  rho={row['rho_input']:.2f}  Lq={row['Lq']:.4f}  "
              f"Wq={row['Wq']:.4f}  P_wait={row['P_wait']:.4f}")

    print()
    print("Self-test complete.")
