"""
engines/pid_control.py - F8 Process Control Engine

Provides a discrete PID controller, alarm classification, and a
closed-loop simulation for SodhiCable extrusion / insulation
process parameters (temperature, line speed, tension, etc.).
"""

import math


# ---------------------------------------------------------------------------
# Single PID step
# ---------------------------------------------------------------------------
def pid_step(setpoint, actual, Kp=2.0, Ki=0.1, Kd=0.5,
             prev_error=0.0, integral=0.0, dt=1.0):
    """Execute one discrete PID control iteration.

    Parameters
    ----------
    setpoint : float
        Desired process value.
    actual : float
        Current measured process value.
    Kp : float
        Proportional gain (default 2.0).
    Ki : float
        Integral gain (default 0.1).
    Kd : float
        Derivative gain (default 0.5).
    prev_error : float
        Error from the previous time step.
    integral : float
        Accumulated integral term from prior steps.
    dt : float
        Time step duration (default 1.0).

    Returns
    -------
    dict
        output     - control signal
        error      - current error (setpoint - actual)
        integral   - updated integral accumulator
        derivative - current derivative term
    """
    error = setpoint - actual
    integral = integral + error * dt
    derivative = (error - prev_error) / dt if dt != 0 else 0.0

    output = Kp * error + Ki * integral + Kd * derivative

    return {
        "output": output,
        "error": error,
        "integral": integral,
        "derivative": derivative,
    }


# ---------------------------------------------------------------------------
# Alarm classification
# ---------------------------------------------------------------------------
def classify_alarm(value, setpoint, sigma, spec_limit):
    """Classify a process reading into an alarm severity level.

    Levels
    ------
    OK       - within 2 sigma of setpoint
    Warning  - between 2 sigma and spec limit, no CUSUM signal
    Minor    - CUSUM-style drift detected but still within spec
    Major    - deviation exceeds 80 % of the tolerance band
    Critical - exceeds the specification limit

    Parameters
    ----------
    value : float
        Current process measurement.
    setpoint : float
        Target value.
    sigma : float
        Estimated process standard deviation.
    spec_limit : float
        Absolute specification limit (distance from setpoint).

    Returns
    -------
    str
        One of 'OK', 'Warning', 'Minor', 'Major', 'Critical'.
    """
    deviation = abs(value - setpoint)

    if deviation > spec_limit:
        return "Critical"

    tolerance_pct = deviation / spec_limit if spec_limit != 0 else 0.0

    if tolerance_pct > 0.80:
        return "Major"

    # Minor: drift beyond 2-sigma but below 80% tolerance
    if deviation > 2 * sigma and tolerance_pct <= 0.80:
        return "Minor"

    # Warning: between 1-sigma and 2-sigma
    if deviation > sigma:
        return "Warning"

    return "OK"


# ---------------------------------------------------------------------------
# Closed-loop PID simulation
# ---------------------------------------------------------------------------
def simulate_pid(setpoint, disturbances, Kp=2.0, Ki=0.1, Kd=0.5):
    """Simulate a PID controller responding to a disturbance sequence.

    The plant model is a simple integrator:
        actual(t+1) = actual(t) + control_output(t) + disturbance(t)

    Parameters
    ----------
    setpoint : float
        Desired process value.
    disturbances : list[float]
        External disturbance at each time step.
    Kp, Ki, Kd : float
        PID gains.

    Returns
    -------
    dict
        actual_values    - process value at each step
        control_outputs  - PID output at each step
        errors           - error at each step
    """
    actual_values = []
    control_outputs = []
    errors = []

    actual = setpoint  # start at setpoint
    prev_error = 0.0
    integral = 0.0

    for d in disturbances:
        result = pid_step(
            setpoint, actual,
            Kp=Kp, Ki=Ki, Kd=Kd,
            prev_error=prev_error,
            integral=integral,
            dt=1.0,
        )

        control = result["output"]
        prev_error = result["error"]
        integral = result["integral"]

        # Simple integrator plant model
        actual = actual + control + d

        actual_values.append(actual)
        control_outputs.append(control)
        errors.append(result["error"])

    return {
        "actual_values": actual_values,
        "control_outputs": control_outputs,
        "errors": errors,
    }
