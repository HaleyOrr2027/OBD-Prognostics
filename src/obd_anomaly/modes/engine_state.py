"""Step 15: engine state. A lost connection is UNKNOWN, never OFF.

RPM/speed cross-check (proposed by Haley, Oct 21): if RPM says the engine is
off but speed says the vehicle is clearly moving, neither signal is trusted and
the engine state is UNKNOWN. The detector tags those samples with the reason
RPM_SPEED_CONFLICT. This is not treated as a sensor fault: it is also what a
stall while rolling looks like.
"""

from __future__ import annotations

import pandas as pd

from ..config import Config
from ..schemas import EngineState


def rpm_speed_conflict(frame: pd.DataFrame, config: Config) -> pd.Series:
    """True where RPM reads engine-off while speed shows the vehicle moving."""
    p = config.get("modes", "engine_state")
    if not p.get("rpm_speed_conflict_check", False):
        return pd.Series(False, index=frame.index)
    rpm_says_off = frame["ENGINE_RPM"] < float(p["running_rpm_min"])
    moving = frame["VEHICLE_SPEED"] > float(p["conflict_speed_kmh"])
    return (rpm_says_off & moving).fillna(False)


def detect_engine_state(frame: pd.DataFrame, config: Config) -> pd.Series:
    running_min = float(config.get("modes", "engine_state", "running_rpm_min"))
    rpm = frame["ENGINE_RPM"]

    state = pd.Series(EngineState.UNKNOWN.value, index=frame.index, dtype=object)
    state[rpm >= running_min] = EngineState.RUNNING.value
    state[rpm < running_min] = EngineState.OFF.value
    state[rpm_speed_conflict(frame, config)] = EngineState.UNKNOWN.value

    if "CONNECTION_OK" in frame.columns:
        state[~frame["CONNECTION_OK"].astype(bool)] = EngineState.UNKNOWN.value
    return state
