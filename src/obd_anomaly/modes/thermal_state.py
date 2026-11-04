"""Steps 16-17: seconds since engine start and the startup/warm-up guard.

If a session begins with the engine already running and no start transition is
seen, ENGINE_RUN_TIME is used as the engine age when available; otherwise the
age is unknown and the sample counts as WARM_OR_UNKNOWN. Coolant temperature is
kept as context only (no universal warm threshold, per plan.md Step 17).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config
from ..schemas import EngineState, ThermalState


def seconds_since_engine_start(frame: pd.DataFrame, engine_state: pd.Series) -> pd.Series:
    elapsed = frame["ELAPSED_SEC"].to_numpy(dtype=float)
    running = (engine_state == EngineState.RUNNING.value).to_numpy()
    run_time = frame["ENGINE_RUN_TIME"].to_numpy(dtype=float) if "ENGINE_RUN_TIME" in frame else None

    out = np.full(len(frame), np.nan)
    start_time = None
    for i in range(len(frame)):
        if not running[i]:
            start_time = None
            continue
        if start_time is None:
            just_started = i > 0 and not running[i - 1]
            if just_started:
                start_time = elapsed[i]
            elif run_time is not None and np.isfinite(run_time[i]):
                start_time = elapsed[i] - run_time[i]
            else:
                continue  # engine age unknown
        out[i] = elapsed[i] - start_time
    return pd.Series(out, index=frame.index)


def detect_thermal_state(seconds_since_start: pd.Series, config: Config) -> pd.Series:
    guard = float(config.get("modes", "thermal_state", "startup_guard_sec"))
    state = pd.Series(ThermalState.WARM_OR_UNKNOWN.value, index=seconds_since_start.index, dtype=object)
    state[seconds_since_start < guard] = ThermalState.STARTUP_WARMUP.value
    return state
