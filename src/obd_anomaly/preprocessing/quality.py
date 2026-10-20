"""Step 10: sample-level data quality flags.

Conservative acquisition checks only. Duplicate timestamps are informational
for carOBD-style logs and do not by themselves mark a sample as bad.
"""

from __future__ import annotations

import pandas as pd

from ..config import Config

BLOCKING_TIME_FLAGS = ("CLOCK_REVERSAL", "TIME_GAP", "MISSING_TIME")


def add_quality_flags(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    out = frame.copy()
    flags = out.get("TIME_FLAGS", pd.Series("", index=out.index)).astype(str).copy()

    for pid in config.pids["required"]:
        missing = out[pid].isna()
        flags[missing] += f"MISSING_{pid};"

    if "CONNECTION_OK" in out.columns:
        flags[~out["CONNECTION_OK"].astype(bool)] += "CONNECTION_LOST;"

    blocking = [f"MISSING_{pid}" for pid in config.pids["required"]]
    blocking += list(BLOCKING_TIME_FLAGS) + ["CONNECTION_LOST"]
    out["QUALITY_FLAGS"] = flags
    out["DATA_QUALITY_OK"] = ~flags.apply(lambda f: any(b in f for b in blocking))
    return out
