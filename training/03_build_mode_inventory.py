"""Step 26: how much data exists per mode.

Input:  data/labeled/*.csv (from 02_label_modes.py)
Output: data/inventory/mode_inventory.csv          per session and mode
        data/inventory/mode_inventory_summary.csv  per mode, all sessions
"""

from __future__ import annotations

import sys

import pandas as pd

import _paths  # noqa: F401
from obd_anomaly.config import load_config


def main() -> int:
    config = load_config()
    labeled_dir = config.path("data", "labeled")
    files = sorted(p for p in labeled_dir.glob("*.csv") if not p.stem.endswith("_segments"))
    if not files:
        print("No labeled sessions. Run training/02_label_modes.py first.")
        return 1

    rows = []
    for path in files:
        frame = pd.read_csv(path)
        segments = pd.read_csv(labeled_dir / f"{path.stem}_segments.csv")
        dt = frame["ELAPSED_SEC"].diff().clip(lower=0).fillna(0)
        for mode, part in frame.groupby("MOTION_STATE"):
            seg = segments[segments["MOTION_STATE"] == mode]
            rows.append({
                "VEHICLE_ID": frame["VEHICLE_ID"].iloc[0],
                "SESSION_ID": path.stem,
                "MOTION_STATE": mode,
                "TOTAL_SECONDS": round(float(dt.loc[part.index].sum()), 1),
                "SAMPLE_COUNT": len(part),
                "SEGMENT_COUNT": len(seg),
                "MEDIAN_SEGMENT_SEC": round(float(seg["DURATION_SEC"].median()), 1) if len(seg) else 0.0,
            })

    inventory = pd.DataFrame(rows)
    summary = inventory.groupby("MOTION_STATE").agg(
        SESSIONS=("SESSION_ID", "nunique"),
        TOTAL_SECONDS=("TOTAL_SECONDS", "sum"),
        SEGMENTS=("SEGMENT_COUNT", "sum"),
        MEDIAN_SEGMENT_SEC=("MEDIAN_SEGMENT_SEC", "median"),
    ).sort_values("TOTAL_SECONDS", ascending=False)

    out_dir = config.path("data", "inventory")
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(out_dir / "mode_inventory.csv", index=False)
    summary.to_csv(out_dir / "mode_inventory_summary.csv")
    print(summary.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
