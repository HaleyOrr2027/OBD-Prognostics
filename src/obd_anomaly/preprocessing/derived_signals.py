"""Steps 12-14: derived signals.

All filters are trailing (causal): each value uses only the current and past
samples, so the live Pi and offline replay produce identical results. Rates are
computed against elapsed time, never row spacing, and never across a time gap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config

KMH_TO_MPS = 1000.0 / 3600.0


def _trailing_median(values: pd.Series, elapsed: pd.Series, span_sec: float) -> pd.Series:
    """Median of the samples in (t - span, t]."""
    indexed = pd.Series(values.to_numpy(dtype=float), index=pd.to_timedelta(elapsed.to_numpy(), unit="s"))
    smoothed = indexed.rolling(f"{span_sec}s", min_periods=1).median()
    return pd.Series(smoothed.to_numpy(), index=values.index)


def _trailing_rate(values: pd.Series, elapsed: pd.Series, span_sec: float) -> pd.Series:
    """(v(t) - v(t - span)) / actual elapsed time, using the oldest sample inside the span.

    Rows sharing a timestamp get the same reference point, so duplicate
    timestamps never cause a division by zero.
    """
    t = elapsed.to_numpy(dtype=float)
    v = values.to_numpy(dtype=float)
    start = np.searchsorted(t, t - span_sec, side="left")
    dt = t - t[start]
    dv = v - v[start]
    rate = np.full_like(v, np.nan)
    valid = dt >= 0.5 * span_sec
    rate[valid] = dv[valid] / dt[valid]
    return pd.Series(rate, index=values.index)


def add_derived_signals(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    out = frame.copy()
    smooth_sec = float(config.get("modes", "derived", "speed_smooth_sec"))
    span_sec = float(config.get("modes", "derived", "accel_span_sec"))

    columns = {
        "SPEED_SMOOTH_KMH": [],
        "ACCELERATION_MPS2": [],
        "RPM_DELTA_PER_SEC": [],
        "LOAD_DELTA_PER_SEC": [],
        "THROTTLE_DELTA_PER_SEC": [],
    }

    for _, block in out.groupby("TIME_BLOCK", sort=False):
        elapsed = block["ELAPSED_SEC"]
        speed = _trailing_median(block["VEHICLE_SPEED"], elapsed, smooth_sec)
        columns["SPEED_SMOOTH_KMH"].append(speed)
        columns["ACCELERATION_MPS2"].append(_trailing_rate(speed * KMH_TO_MPS, elapsed, span_sec))
        columns["RPM_DELTA_PER_SEC"].append(_trailing_rate(block["ENGINE_RPM"], elapsed, span_sec))
        for source, name in (("ENGINE_LOAD", "LOAD_DELTA_PER_SEC"), ("THROTTLE_POSITION", "THROTTLE_DELTA_PER_SEC")):
            if block[source].notna().any():
                columns[name].append(_trailing_rate(block[source], elapsed, span_sec))
            else:
                columns[name].append(pd.Series(np.nan, index=block.index))

    for name, parts in columns.items():
        out[name] = pd.concat(parts).reindex(out.index)
    return out
