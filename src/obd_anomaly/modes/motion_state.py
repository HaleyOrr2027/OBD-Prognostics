"""Steps 18-19: stopped vs moving, then acceleration / steady / deceleration.

Deceleration is split into COASTING_DECEL and STRONG_DECEL. It is not called
braking because there is no brake-pedal signal (plan.md Section 8).
"""

from __future__ import annotations

import pandas as pd

from ..config import Config
from ..schemas import EngineState, MotionState


def detect_motion_state_raw(frame: pd.DataFrame, engine_state: pd.Series, config: Config) -> pd.Series:
    p = config.get("modes", "motion_state")
    speed = frame["SPEED_SMOOTH_KMH"]
    accel = frame["ACCELERATION_MPS2"]
    rpm = frame["ENGINE_RPM"]
    running = engine_state == EngineState.RUNNING.value

    stopped = speed <= p["stopped_speed_kmh"]
    moving = speed > p["stopped_speed_kmh"]

    # IDLE also requires the latest raw speed reading to be stopped. Smoothed
    # speed lags about a second, so without this the RPM rise at a pull-away
    # briefly looks like a stationary high-RPM idle.
    if p.get("idle_requires_raw_stop", False):
        raw_stopped = frame["VEHICLE_SPEED"] <= p["stopped_speed_kmh"]
    else:
        raw_stopped = pd.Series(True, index=frame.index)

    state = pd.Series(MotionState.UNKNOWN_TRANSITION.value, index=frame.index, dtype=object)

    # Idle needs the engine running: engine off at 0 km/h is not idle.
    # idle_rpm_max: null (Haley, Oct 21) means IDLE is any stationary running
    # engine, so a high-RPM stop still reaches the IDLE model instead of being
    # dropped as UNKNOWN_TRANSITION. A number restores the old upper limit.
    idle = running & stopped & raw_stopped
    if p.get("idle_rpm_max") is not None:
        idle &= rpm <= float(p["idle_rpm_max"])
    state[idle] = MotionState.IDLE.value

    known = running & moving & accel.notna()
    state[known & (accel.abs() < p["accel_mps2"])] = MotionState.CRUISING.value
    state[known & (accel >= p["accel_mps2"])] = MotionState.ACCELERATING.value
    state[known & (accel <= p["decel_mps2"])] = MotionState.COASTING_DECEL.value
    state[known & (accel <= p["strong_decel_mps2"])] = MotionState.STRONG_DECEL.value
    return state
