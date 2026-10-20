"""Step 32: pure-mode window extraction.

A window is accepted only if it lies inside one stable mode segment, every
sample in it has good data quality and enough mode confidence, it has enough
distinct timestamps, and no internal time gap is too long. Windows are cut on a
fixed grid from each segment's start, so WINDOW_IDs are deterministic.

Features are not computed here (Steps 33-34); this returns window boundaries
and metadata only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config

WINDOW_COLUMNS = [
    "WINDOW_ID", "SESSION_ID", "MODE_SEGMENT_ID", "MOTION_STATE", "WINDOW_START_SEC",
    "WINDOW_END_SEC", "DURATION_SEC", "SAMPLE_COUNT", "DISTINCT_TIMES", "MIN_MODE_CONFIDENCE",
    "QUALITY_FLAGS",
]

REJECT_REASONS = ("LOW_CONFIDENCE", "BAD_QUALITY", "TOO_FEW_TIMES", "INTERNAL_GAP")


def window_policy(config: Config) -> tuple[dict, dict]:
    defaults = config.get("windows", "defaults")
    modes = config.get("windows", "modes")
    return defaults, modes


def _check(window: pd.DataFrame, start: float, end: float, defaults: dict) -> str | None:
    """Return a rejection reason, or None if the window is acceptable.

    Gaps are measured including the window edges, so a window whose data stops
    early (or starts late) is rejected rather than silently covering less time.
    The end edge is exclusive, so the last sample can be up to one sampling
    interval before it without counting as a gap.
    """
    if (window["MODE_CONFIDENCE"] < defaults["min_mode_confidence"]).any():
        return "LOW_CONFIDENCE"
    if not window["DATA_QUALITY_OK"].astype(bool).all():
        return "BAD_QUALITY"
    times = np.unique(window["ELAPSED_SEC"].to_numpy(dtype=float))
    if len(times) < defaults["min_distinct_times"]:
        return "TOO_FEW_TIMES"
    edges = np.concatenate(([start], times, [end]))
    if np.diff(edges).max() > defaults["max_internal_gap_sec"]:
        return "INTERNAL_GAP"
    return None


def extract_windows(labeled: pd.DataFrame, config: Config) -> tuple[pd.DataFrame, pd.Series]:
    """Cut accepted windows from one labeled session.

    Returns (windows, rejections) where rejections counts candidate windows
    turned down, by reason.
    """
    defaults, modes = window_policy(config)
    rows = []
    rejected = {reason: 0 for reason in REJECT_REASONS}

    for segment_id, segment in labeled.groupby("MODE_SEGMENT_ID", sort=False):
        mode = segment["MOTION_STATE"].iloc[0]
        if mode not in modes:
            continue
        width = float(modes[mode]["window_sec"])
        stride = float(modes[mode]["stride_sec"])
        t = segment["ELAPSED_SEC"].to_numpy(dtype=float)
        seg_start, seg_end = t.min(), t.max()

        k = 0
        start = seg_start
        while True:
            end = start + width
            if end > seg_end and defaults["discard_partial_final"]:
                break
            window = segment[(t >= start) & (t < end)]
            reason = _check(window, start, end, defaults) if len(window) else "TOO_FEW_TIMES"
            if reason:
                rejected[reason] += 1
            else:
                rows.append({
                    "WINDOW_ID": f"{segment_id}-W{k:03d}",
                    "SESSION_ID": segment["SESSION_ID"].iloc[0],
                    "MODE_SEGMENT_ID": segment_id,
                    "MOTION_STATE": mode,
                    "WINDOW_START_SEC": start,
                    "WINDOW_END_SEC": end,
                    "DURATION_SEC": width,
                    "SAMPLE_COUNT": len(window),
                    "DISTINCT_TIMES": int(window["ELAPSED_SEC"].nunique()),
                    "MIN_MODE_CONFIDENCE": float(window["MODE_CONFIDENCE"].min()),
                    "QUALITY_FLAGS": ";".join(sorted({f for f in window["QUALITY_FLAGS"].astype(str) if f})),
                })
            k += 1
            start += stride
            if end > seg_end:
                break

    return pd.DataFrame(rows, columns=WINDOW_COLUMNS), pd.Series(rejected, name="rejected")
