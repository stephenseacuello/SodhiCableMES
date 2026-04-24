"""
engines/dispatch.py - F3 Weighted Priority Dispatch Engine

Scores and ranks work orders in the dispatch queue using a weighted
composite of urgency, priority class, and changeover penalty.

    S_i = w1 * (1 / (d_i - t)) + w2 * P_i + w3 * (1 / (s_ij + 1))

where
    d_i = due date (epoch seconds), t = current time,
    P_i = numeric priority, s_ij = changeover time (minutes).
"""

from datetime import datetime

# Business Unit → Priority Weight (from design doc)
# Defense (MIL-DTL, shipboard, UL-2196): w=3
# Control/Power (B, M families): w=2
# Industrial/Building Wire (R, A, I): w=1
BU_WEIGHTS = {
    "Defense": 3,
    "Infrastructure": 2,
    "Industrial": 1,
    "Oil & Gas": 2,
}

FAMILY_WEIGHTS = {
    "S": 3, "U": 3,  # Shipboard/UL-2196 = Defense priority
    "B": 2, "M": 2,  # Control/Power/MV
    "A": 1, "R": 1, "I": 1,  # Industrial/Building
    "C": 2, "D": 2,  # DHT = Oil&Gas priority
}


# ---------------------------------------------------------------------------
# Core scoring function
# ---------------------------------------------------------------------------
def score_dispatch(
    due_date,
    current_time,
    priority,
    changeover_time,
    w_urgency=0.4,
    w_priority=0.4,
    w_changeover=0.2,
):
    """Compute the composite dispatch score for a single job.

    Parameters
    ----------
    due_date : float
        Due-date as a Unix timestamp (seconds).
    current_time : float
        Current time as a Unix timestamp (seconds).
    priority : float
        Numeric priority value (higher = more important).
    changeover_time : float
        Estimated changeover / setup time in minutes.
    w_urgency : float
        Weight for the urgency term (default 0.4).
    w_priority : float
        Weight for the priority term (default 0.4).
    w_changeover : float
        Weight for the changeover term (default 0.2).

    Returns
    -------
    float
        Composite score. Higher is better.
    """
    time_remaining = due_date - current_time
    if time_remaining <= 0:
        # Already overdue - assign very high urgency
        urgency = 1e6
    else:
        urgency = 1.0 / time_remaining

    changeover_factor = 1.0 / (changeover_time + 1.0)

    return w_urgency * urgency + w_priority * priority + w_changeover * changeover_factor


# ---------------------------------------------------------------------------
# Select the next job to dispatch
# ---------------------------------------------------------------------------
def dispatch_next(conn, wc_id):
    """Pick the highest-priority job from the dispatch queue.

    Reads from: dispatch_queue (columns: wo_id, wc_id, due_date,
    priority, changeover_time).

    Parameters
    ----------
    conn : sqlite3.Connection
    wc_id : str
        Target work center.

    Returns
    -------
    dict or None
        {wo_id, score} of the selected work order, or None if empty.
    """
    ranked = rank_queue(conn, wc_id)
    if not ranked:
        return None
    return {"wo_id": ranked[0]["wo_id"], "score": ranked[0]["score"]}


# ---------------------------------------------------------------------------
# Rank the entire queue
# ---------------------------------------------------------------------------
def rank_queue(conn, wc_id):
    """Return all queued jobs ranked by composite dispatch score.

    Parameters
    ----------
    conn : sqlite3.Connection
    wc_id : str

    Returns
    -------
    list[dict]
        Each dict has wo_id, due_date, priority, changeover_time, score.
        Sorted descending by score.
    """
    cur = conn.cursor()
    cur.execute(
        """SELECT wo_id, due_date, priority, changeover_time
           FROM dispatch_queue
           WHERE wc_id = ?""",
        (wc_id,),
    )
    rows = cur.fetchall()

    now = datetime.utcnow().timestamp()

    scored = []
    for wo_id, due_date_str, priority, changeover_time in rows:
        # Accept epoch float or ISO string
        if isinstance(due_date_str, str):
            due_ts = datetime.fromisoformat(due_date_str).timestamp()
        else:
            due_ts = float(due_date_str)

        s = score_dispatch(due_ts, now, priority, changeover_time)
        scored.append(
            {
                "wo_id": wo_id,
                "due_date": due_date_str,
                "priority": priority,
                "changeover_time": changeover_time,
                "score": round(s, 6),
            }
        )

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored
