"""Step 09: time base.

Source priority: MONOTONIC_SEC (live collection) -> ENGINE_RUN_TIME (historical
CSVs). Row order is never treated as time.

carOBD logs several rows per second that share one ENGINE_RUN_TIME value, so
zero intervals are common there. They are flagged, not repaired, and the
derivative code works on elapsed time rather than per-row differences.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config


def build_timebase(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    out = frame.copy()
    max_gap = float(config.get("modes", "timebase", "max_gap_sec"))

    if "MONOTONIC_SEC" in out.columns and out["MONOTONIC_SEC"].notna().any():
        clock = pd.to_numeric(out["MONOTONIC_SEC"], errors="coerce")
        source = "MONOTONIC_SEC"
    elif out.get("ENGINE_RUN_TIME") is not None and out["ENGINE_RUN_TIME"].notna().any():
        clock = pd.to_numeric(out["ENGINE_RUN_TIME"], errors="coerce")
        source = "ENGINE_RUN_TIME"
    else:
        raise ValueError("No usable time column: need MONOTONIC_SEC or ENGINE_RUN_TIME")

    first = clock.dropna().iloc[0]
    out["ELAPSED_SEC"] = clock - first
    dt = out["ELAPSED_SEC"].diff()
    out["SAMPLE_DT_SEC"] = dt
    out["TIME_SOURCE"] = source

    flags = pd.Series("", index=out.index, dtype=object)
    flags[dt == 0] += "DUPLICATE_TIME;"
    flags[dt < 0] += "CLOCK_REVERSAL;"
    flags[dt > max_gap] += "TIME_GAP;"
    flags[clock.isna()] += "MISSING_TIME;"
    out["TIME_FLAGS"] = flags

    # A new contiguous block starts after any gap or reversal. Derivatives and
    # mode segments never reach across a block boundary.
    breaks = (dt > max_gap) | (dt < 0) | clock.isna()
    out["TIME_BLOCK"] = np.cumsum(breaks.fillna(False).to_numpy())
    return out
