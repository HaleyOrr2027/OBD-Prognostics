"""Step 15: engine state. A lost connection is UNKNOWN, never OFF."""

from __future__ import annotations

import pandas as pd

from ..config import Config
from ..schemas import EngineState


def detect_engine_state(frame: pd.DataFrame, config: Config) -> pd.Series:
    running_min = float(config.get("modes", "engine_state", "running_rpm_min"))
    rpm = frame["ENGINE_RPM"]

    state = pd.Series(EngineState.UNKNOWN.value, index=frame.index, dtype=object)
    state[rpm >= running_min] = EngineState.RUNNING.value
    state[rpm < running_min] = EngineState.OFF.value

    if "CONNECTION_OK" in frame.columns:
        state[~frame["CONNECTION_OK"].astype(bool)] = EngineState.UNKNOWN.value
    return state
