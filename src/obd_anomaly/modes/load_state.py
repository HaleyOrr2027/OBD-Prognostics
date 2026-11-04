"""Step 20: load context. Recorded as context; it does not route models in v1."""

from __future__ import annotations

import pandas as pd

from ..config import Config
from ..schemas import LoadState


def detect_load_state(frame: pd.DataFrame, config: Config) -> pd.Series:
    p = config.get("modes", "load_state")
    load = frame["ENGINE_LOAD"]
    state = pd.Series(LoadState.UNKNOWN.value, index=frame.index, dtype=object)
    state[load < p["low_max_pct"]] = LoadState.LOW.value
    state[(load >= p["low_max_pct"]) & (load < p["high_min_pct"])] = LoadState.MEDIUM.value
    state[load >= p["high_min_pct"]] = LoadState.HIGH.value
    return state
