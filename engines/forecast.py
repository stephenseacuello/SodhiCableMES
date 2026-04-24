"""
SodhiCable MES — Demand Forecasting Engine

Simple Exponential Smoothing (SES) and Double Exponential Smoothing (DES/Holt)
for product-family demand forecasting at the S&OP planning level.
"""
import math


def ses_forecast(actuals, alpha=0.3, periods_ahead=4):
    """Simple Exponential Smoothing.
    F(t+1) = alpha * A(t) + (1 - alpha) * F(t)

    Returns list of forecasts (same length as actuals + periods_ahead).
    """
    if not actuals:
        return []
    forecasts = [actuals[0]]
    for t in range(1, len(actuals)):
        f = alpha * actuals[t - 1] + (1 - alpha) * forecasts[t - 1]
        forecasts.append(round(f, 2))
    # Project forward
    last = alpha * actuals[-1] + (1 - alpha) * forecasts[-1]
    for _ in range(periods_ahead):
        forecasts.append(round(last, 2))
        last = round(last, 2)  # flat projection for SES
    return forecasts


def des_forecast(actuals, alpha=0.3, beta=0.1, periods_ahead=4):
    """Double Exponential Smoothing (Holt's method) with trend.
    Level:  L(t) = alpha * A(t) + (1-alpha) * (L(t-1) + T(t-1))
    Trend:  T(t) = beta * (L(t) - L(t-1)) + (1-beta) * T(t-1)
    Forecast: F(t+k) = L(t) + k * T(t)
    """
    if len(actuals) < 2:
        return ses_forecast(actuals, alpha, periods_ahead)

    level = actuals[0]
    trend = actuals[1] - actuals[0]
    forecasts = [round(level, 2)]

    for t in range(1, len(actuals)):
        new_level = alpha * actuals[t] + (1 - alpha) * (level + trend)
        new_trend = beta * (new_level - level) + (1 - beta) * trend
        level, trend = new_level, new_trend
        forecasts.append(round(level + trend, 2))

    # Project forward with trend
    for k in range(1, periods_ahead + 1):
        forecasts.append(round(level + k * trend, 2))
    return forecasts


def forecast_accuracy(forecasts, actuals):
    """Calculate forecast accuracy metrics.
    Returns dict with MAPE, bias, and tracking signal.
    """
    if not forecasts or not actuals:
        return {"mape": 0, "bias": 0, "tracking_signal": 0, "n": 0}

    n = min(len(forecasts), len(actuals))
    errors = []
    abs_errors = []
    pct_errors = []

    for i in range(n):
        if actuals[i] and actuals[i] != 0:
            e = actuals[i] - forecasts[i]
            errors.append(e)
            abs_errors.append(abs(e))
            pct_errors.append(abs(e) / abs(actuals[i]) * 100)

    if not errors:
        return {"mape": 0, "bias": 0, "tracking_signal": 0, "n": 0}

    mape = round(sum(pct_errors) / len(pct_errors), 1)
    bias = round(sum(errors) / len(errors), 2)
    mad = sum(abs_errors) / len(abs_errors)
    tracking_signal = round(sum(errors) / max(mad, 0.01), 2)

    return {"mape": mape, "bias": bias, "tracking_signal": tracking_signal, "n": len(errors)}


# Family -> primary bottleneck work centers (derived from routings)
FAMILY_BOTTLENECK_MAP = {
    "A": ["CV-1", "BRAID-1"],
    "B": ["CV-1", "ARMOR-1"],
    "C": ["PX-1"],
    "D": ["PX-1"],
    "I": ["DRAW-1", "CV-2"],
    "M": ["CV-1", "CV-3"],
    "R": ["CV-2", "CUT-1"],
    "S": ["PLCV-1"],
    "U": ["CV-2", "PLCV-1"],
}


def family_bottleneck_map():
    """Return mapping of product family to primary bottleneck work centers."""
    return dict(FAMILY_BOTTLENECK_MAP)
