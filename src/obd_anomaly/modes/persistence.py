"""Step 22: persistence / hysteresis.

The stable state only switches after a candidate state has held for dwell_sec of
elapsed time (not rows). Hard states switch immediately in either direction,
because scoring must stop at once when the engine turns off, the engine has just
started, or the data cannot be trusted.

COASTING_DECEL and STRONG_DECEL share one dwell timer. A deceleration whose
rate wobbles around the strong threshold is still one deceleration; timing the
two separately would keep resetting the timer so the switch never happens.
Within an already-stable deceleration the sub-state follows the raw state.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config
from ..schemas import MotionState

HARD_STATES = {
    MotionState.ENGINE_OFF.value,
    MotionState.STARTUP_WARMUP.value,
    MotionState.UNKNOWN_TRANSITION.value,
}
FAMILY = {
    MotionState.COASTING_DECEL.value: "DECEL",
    MotionState.STRONG_DECEL.value: "DECEL",
}


def _family(state: str) -> str:
    return FAMILY.get(state, state)


def apply_persistence(raw: pd.Series, elapsed: pd.Series, time_block: pd.Series, config: Config) -> pd.Series:
    dwell = float(config.get("modes", "persistence", "dwell_sec"))
    raw_values = raw.to_numpy(dtype=object)
    t = elapsed.to_numpy(dtype=float)
    blocks = time_block.to_numpy()

    stable = np.empty(len(raw), dtype=object)
    current = candidate = None
    candidate_since = 0.0

    for i, state in enumerate(raw_values):
        new_block = i == 0 or blocks[i] != blocks[i - 1]
        if new_block or current is None or state in HARD_STATES or current in HARD_STATES:
            current, candidate = state, None
        elif _family(state) == _family(current):
            current, candidate = state, None
        elif candidate is None or _family(state) != _family(candidate):
            candidate, candidate_since = state, t[i]
        else:
            candidate = state  # same family, keep the timer running
        if candidate is not None and t[i] - candidate_since >= dwell:
            current, candidate = candidate, None
        stable[i] = current

    return pd.Series(stable, index=raw.index)
