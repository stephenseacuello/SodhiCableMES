"""
engines/spc.py - Statistical Process Control Engine

Provides X-bar/R charting, capability indices (Cp/Cpk),
CUSUM, EWMA, and Western Electric rule detection for
SodhiCable MES quality monitoring.
"""

import math
import statistics

# ---------------------------------------------------------------------------
# Control-chart constants for subgroup size n = 5
# ---------------------------------------------------------------------------
_A2 = 0.577
_D3 = 0.0
_D4 = 2.114
_d2 = 2.326


# ---------------------------------------------------------------------------
# X-bar / R chart
# ---------------------------------------------------------------------------
def xbar_r_chart(values, subgroup_size=5):
    """Build X-bar and R control-chart statistics.

    Parameters
    ----------
    values : list[float]
        Individual measurements in time order. Length must be a multiple
        of *subgroup_size*.
    subgroup_size : int
        Number of observations per rational subgroup (default 5).

    Returns
    -------
    dict
        x_bar_values  - list of subgroup means
        r_values      - list of subgroup ranges
        ucl_xbar      - upper control limit for X-bar
        cl_xbar       - center line for X-bar (grand mean)
        lcl_xbar      - lower control limit for X-bar
        ucl_r         - upper control limit for R
        cl_r          - center line for R (R-bar)
        lcl_r         - lower control limit for R
    """
    n = subgroup_size
    if len(values) < n:
        raise ValueError("Need at least one full subgroup of measurements.")

    # Trim to a whole number of subgroups
    num_subgroups = len(values) // n
    trimmed = values[: num_subgroups * n]

    subgroups = [trimmed[i * n : (i + 1) * n] for i in range(num_subgroups)]

    x_bar_values = [statistics.mean(sg) for sg in subgroups]
    r_values = [max(sg) - min(sg) for sg in subgroups]

    x_double_bar = statistics.mean(x_bar_values)
    r_bar = statistics.mean(r_values)

    ucl_xbar = x_double_bar + _A2 * r_bar
    lcl_xbar = x_double_bar - _A2 * r_bar

    ucl_r = _D4 * r_bar
    lcl_r = _D3 * r_bar  # 0 for n = 5

    return {
        "x_bar_values": x_bar_values,
        "r_values": r_values,
        "ucl_xbar": ucl_xbar,
        "cl_xbar": x_double_bar,
        "lcl_xbar": lcl_xbar,
        "ucl_r": ucl_r,
        "cl_r": r_bar,
        "lcl_r": lcl_r,
    }


# ---------------------------------------------------------------------------
# Process capability Cp / Cpk
# ---------------------------------------------------------------------------
def compute_cpk(values, usl, lsl, subgroup_size=5):
    """Compute Cp and Cpk using the R-bar/d2 estimator for sigma.

    Parameters
    ----------
    values : list[float]
        Individual measurements (length must be >= subgroup_size).
    usl : float
        Upper specification limit.
    lsl : float
        Lower specification limit.
    subgroup_size : int
        Subgroup size used for sigma estimation (default 5).

    Returns
    -------
    dict
        cp        - process capability ratio
        cpk       - adjusted capability index
        sigma_hat - estimated process standard deviation (R-bar / d2)
    """
    chart = xbar_r_chart(values, subgroup_size)
    r_bar = chart["cl_r"]
    sigma_hat = r_bar / _d2

    if sigma_hat == 0:
        return {"cp": float("inf"), "cpk": float("inf"), "sigma_hat": 0.0}

    x_double_bar = chart["cl_xbar"]
    cp = (usl - lsl) / (6 * sigma_hat)
    cpu = (usl - x_double_bar) / (3 * sigma_hat)
    cpl = (x_double_bar - lsl) / (3 * sigma_hat)
    cpk = min(cpu, cpl)

    return {"cp": cp, "cpk": cpk, "sigma_hat": sigma_hat}


# ---------------------------------------------------------------------------
# CUSUM chart
# ---------------------------------------------------------------------------
def cusum(values, target, k=0.5, h=5):
    """Tabular CUSUM for detecting mean shifts.

    Parameters
    ----------
    values : list[float]
        Observations in time order.
    target : float
        In-control process mean.
    k : float
        Allowance (slack) value in sigma units (default 0.5).
    h : float
        Decision interval in sigma units (default 5).

    Returns
    -------
    dict
        c_plus         - upper CUSUM accumulator list
        c_minus        - lower CUSUM accumulator list
        signal_indices - indices where |C| exceeded h * sigma
    """
    if len(values) < 2:
        raise ValueError("Need at least 2 observations for CUSUM.")

    sigma = statistics.stdev(values)
    if sigma == 0:
        sigma = 1.0  # degenerate case

    c_plus = []
    c_minus = []
    signal_indices = []

    cp_prev = 0.0
    cm_prev = 0.0

    for i, x in enumerate(values):
        z = (x - target) / sigma
        cp_i = max(0.0, z - k + cp_prev)
        cm_i = max(0.0, -z - k + cm_prev)
        c_plus.append(cp_i)
        c_minus.append(cm_i)

        if cp_i > h or cm_i > h:
            signal_indices.append(i)

        cp_prev = cp_i
        cm_prev = cm_i

    return {
        "c_plus": c_plus,
        "c_minus": c_minus,
        "signal_indices": signal_indices,
    }


# ---------------------------------------------------------------------------
# EWMA chart
# ---------------------------------------------------------------------------
def ewma(values, lambda_=0.2, L=3, target=None):
    """Exponentially Weighted Moving Average control chart.

    Parameters
    ----------
    values : list[float]
        Observations in time order.
    lambda_ : float
        Smoothing constant, 0 < lambda_ <= 1 (default 0.2).
    L : float
        Width of control limits in sigma units (default 3).
    target : float or None
        In-control mean. Defaults to the sample mean.

    Returns
    -------
    dict
        ewma_values    - EWMA statistic at each point
        ucl            - upper control limit at each point
        lcl            - lower control limit at each point
        signal_indices - indices where EWMA exceeded limits
    """
    if target is None:
        target = statistics.mean(values)

    sigma = statistics.stdev(values) if len(values) > 1 else 1.0
    if sigma == 0:
        sigma = 1.0

    ewma_values = []
    ucl_list = []
    lcl_list = []
    signal_indices = []

    z = target  # initial EWMA value

    for i, x in enumerate(values):
        z = lambda_ * x + (1 - lambda_) * z
        ewma_values.append(z)

        # Time-varying limits
        factor = (lambda_ / (2 - lambda_)) * (1 - (1 - lambda_) ** (2 * (i + 1)))
        limit_width = L * sigma * math.sqrt(factor)
        ucl_list.append(target + limit_width)
        lcl_list.append(target - limit_width)

        if z > ucl_list[-1] or z < lcl_list[-1]:
            signal_indices.append(i)

    return {
        "ewma_values": ewma_values,
        "ucl": ucl_list,
        "lcl": lcl_list,
        "signal_indices": signal_indices,
    }


# ---------------------------------------------------------------------------
# Western Electric rules
# ---------------------------------------------------------------------------
def western_electric_rules(values, ucl, cl, lcl):
    """Check observations against all eight Western Electric rules.

    Rules
    -----
    Rule 1 - Any single point beyond 3-sigma (UCL / LCL).
    Rule 2 - 2 out of 3 consecutive points beyond 2-sigma (same side).
    Rule 3 - 4 out of 5 consecutive points beyond 1-sigma (same side).
    Rule 4 - 8 consecutive points on the same side of the center line.
    Rule 5 - 6 consecutive points increasing or decreasing (trend).
    Rule 6 - 15 consecutive points within 1-sigma of center (stratification).
    Rule 7 - 14 consecutive points alternating up and down.
    Rule 8 - 8 consecutive points beyond 1-sigma on either side (mixture).

    Parameters
    ----------
    values : list[float]
        Control-chart statistics (e.g. x-bar values).
    ucl : float
        Upper control limit (3-sigma).
    cl : float
        Center line.
    lcl : float
        Lower control limit (3-sigma).

    Returns
    -------
    list[tuple[int, str]]
        (index, rule_name) for each violation detected.
    """
    violations = []
    one_sigma = (ucl - cl) / 3.0
    two_sigma = 2 * one_sigma

    upper_2s = cl + two_sigma
    lower_2s = cl - two_sigma
    upper_1s = cl + one_sigma
    lower_1s = cl - one_sigma

    for i, v in enumerate(values):
        # Rule 1: beyond 3 sigma
        if v > ucl or v < lcl:
            violations.append((i, "Rule1"))

        # Rule 2: 2 of 3 beyond 2 sigma same side
        if i >= 2:
            window = values[i - 2 : i + 1]
            above = sum(1 for w in window if w > upper_2s)
            below = sum(1 for w in window if w < lower_2s)
            if above >= 2:
                violations.append((i, "Rule2"))
            if below >= 2:
                violations.append((i, "Rule2"))

        # Rule 3: 4 of 5 beyond 1 sigma same side
        if i >= 4:
            window = values[i - 4 : i + 1]
            above = sum(1 for w in window if w > upper_1s)
            below = sum(1 for w in window if w < lower_1s)
            if above >= 4:
                violations.append((i, "Rule3"))
            if below >= 4:
                violations.append((i, "Rule3"))

        # Rule 4: 8 consecutive same side
        if i >= 7:
            window = values[i - 7 : i + 1]
            all_above = all(w > cl for w in window)
            all_below = all(w < cl for w in window)
            if all_above or all_below:
                violations.append((i, "Rule4"))

        # Rule 5: 6 consecutive points increasing or decreasing (trend)
        if i >= 5:
            window = values[i - 5 : i + 1]
            increasing = all(window[j] < window[j + 1] for j in range(5))
            decreasing = all(window[j] > window[j + 1] for j in range(5))
            if increasing or decreasing:
                violations.append((i, "Rule5"))

        # Rule 6: 15 consecutive points within 1-sigma (stratification)
        if i >= 14:
            window = values[i - 14 : i + 1]
            all_within = all(lower_1s <= w <= upper_1s for w in window)
            if all_within:
                violations.append((i, "Rule6"))

        # Rule 7: 14 consecutive points alternating up and down
        if i >= 13:
            window = values[i - 13 : i + 1]
            alternating = True
            for j in range(len(window) - 2):
                rising = window[j + 1] > window[j]
                next_rising = window[j + 2] > window[j + 1]
                if rising == next_rising:
                    alternating = False
                    break
            if alternating:
                violations.append((i, "Rule7"))

        # Rule 8: 8 consecutive points beyond 1-sigma on either side (mixture)
        if i >= 7:
            window = values[i - 7 : i + 1]
            all_outside = all(w > upper_1s or w < lower_1s for w in window)
            if all_outside:
                violations.append((i, "Rule8"))

    return violations


# ---------------------------------------------------------------------------
# ASTM B193 Temperature Correction for Resistance
# ---------------------------------------------------------------------------
def temperature_correct_resistance(measured_resistance, measured_temp_c, target_temp_c=20.0, alpha=0.00393):
    """Correct resistance to target temperature per ASTM B193.

    R_target = R_measured * [1 + alpha * (T_target - T_measured)]

    Parameters
    ----------
    measured_resistance : float
        Measured resistance value (ohms or ohms/kft).
    measured_temp_c : float
        Temperature at which measurement was taken (degrees C).
    target_temp_c : float
        Target reference temperature (default 20.0 C per ASTM B193).
    alpha : float
        Temperature coefficient of resistance (/degrees C).
        Default 0.00393 for annealed copper.

    Returns
    -------
    float
        Resistance corrected to target temperature.
    """
    return measured_resistance * (1.0 + alpha * (target_temp_c - measured_temp_c))
