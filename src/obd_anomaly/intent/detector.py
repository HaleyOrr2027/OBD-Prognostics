"""Causal accelerator-request estimation (not full driver intent).

Pedal sensors D/E are direct indications of accelerator demand, but their
absolute scales can differ. Their *changes* are compared for agreement.
Commanded throttle and measured throttle are lower-confidence proxies.
No speed or RPM is used: a failed engine must not redefine the driver's request.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DIRECT = ("ACCELERATOR_PEDAL_POSITION_D", "ACCELERATOR_PEDAL_POSITION_E")
PROXIES = ("COMMANDED_THROTTLE_ACTUATOR", "THROTTLE_POSITION")
OUTPUTS = ("DRIVER_REQUEST", "DRIVER_REQUEST_SOURCE", "DRIVER_REQUEST_CONFIDENCE",
           "DRIVER_REQUEST_REASON", "PEDAL_DELTA_PERCENT")

def _read(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(values.between(0, 100))

def detect_driver_request(frame: pd.DataFrame, *, threshold: float = 2.0,
                          released_max: float = 4.0, max_gap_sec: float = 3.0) -> pd.DataFrame:
    """Append estimate columns; unknown is a valid result.

    Threshold is a change in percentage points between distinct timestamps.
    No future samples used. A large time gap resets the reference.
    This v1 estimates pedal action, not braking or requested acceleration rate.
    """
    out = frame.copy()
    for col in OUTPUTS:
        out[col] = np.nan if col in ("DRIVER_REQUEST_CONFIDENCE", "PEDAL_DELTA_PERCENT") else ""
    out["DRIVER_REQUEST"] = "UNKNOWN_REQUEST"
    out["DRIVER_REQUEST_SOURCE"] = "NONE"
    out["DRIVER_REQUEST_CONFIDENCE"] = 0.0
    out["DRIVER_REQUEST_REASON"] = "NO_RELIABLE_INPUT"
    if "ELAPSED_SEC" not in out:
        return out
    times = pd.to_numeric(out["ELAPSED_SEC"], errors="coerce")
    blocks = out["TIME_BLOCK"] if "TIME_BLOCK" in out else pd.Series(0, index=out.index)
    signals = {name: _read(out, name) for name in DIRECT + PROXIES}
    # Per-block last distinct timestamp, shared by all rows with the same time.
    for _, indexes in blocks.groupby(blocks, sort=False).groups.items():
        prev_t = None
        prev = {}
        for t, group in out.loc[indexes].groupby(times.loc[indexes], sort=False):
            if not np.isfinite(t):
                continue
            current = {name: float(signals[name].loc[group].median())
                       if signals[name].loc[group].notna().any() else np.nan
                       for name in DIRECT + PROXIES}
            gap_ok = prev_t is not None and 0 < t-prev_t <= max_gap_sec
            direct = [n for n in DIRECT if np.isfinite(current[n])]
            selected = direct if direct else [n for n in PROXIES if np.isfinite(current[n])][:1]
            source = "PEDAL" if direct else ("THROTTLE_PROXY" if selected else "NONE")
            status, reason, conf, change = "UNKNOWN_REQUEST", "NO_RELIABLE_INPUT", 0.0, np.nan
            if selected:
                if not gap_ok or any(not np.isfinite(prev.get(n, np.nan)) for n in selected):
                    reason = "NO_PREVIOUS_SAMPLE"
                else:
                    deltas = [current[n] - prev[n] for n in selected]
                    change = float(np.median(deltas))
                    directions = [1 if d >= threshold else (-1 if d <= -threshold else 0) for d in deltas]
                    if len(directions) > 1 and max(directions)-min(directions) == 2:
                        reason = "PEDAL_CHANNEL_CONFLICT"
                    else:
                        # If one channel changes and the other stays flat, abstain.
                        if len(directions) > 1 and len(set(directions)) > 1:
                            reason = "PEDAL_CHANNEL_DISAGREEMENT"
                        elif directions[0] == 1:
                            status, reason = "ACCELERATE_REQUEST", "INCREASING_INPUT"
                        elif directions[0] == -1:
                            status, reason = "RELEASE_ACCELERATOR", "DECREASING_INPUT"
                        elif source == "PEDAL" and all(current[n] <= released_max for n in selected):
                            status, reason = "NO_ACCELERATOR_REQUEST", "LOW_PEDAL"
                        else:
                            status, reason = "MAINTAIN_REQUEST", "STEADY_INPUT"
                    if status != "UNKNOWN_REQUEST":
                        conf = 0.9 if source == "PEDAL" and len(selected) == 2 else (0.75 if source == "PEDAL" else 0.4)
                if status == "UNKNOWN_REQUEST":
                    source = source if reason != "NO_RELIABLE_INPUT" else "NONE"
            out.loc[group.index, "DRIVER_REQUEST"] = status
            out.loc[group.index, "DRIVER_REQUEST_SOURCE"] = source
            out.loc[group.index, "DRIVER_REQUEST_CONFIDENCE"] = conf
            out.loc[group.index, "DRIVER_REQUEST_REASON"] = reason
            out.loc[group.index, "PEDAL_DELTA_PERCENT"] = change if source == "PEDAL" else np.nan
            prev, prev_t = current, t
    return out
