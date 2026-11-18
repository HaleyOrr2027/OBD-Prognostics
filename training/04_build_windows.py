"""Step 35: build the training file for the fault detector.

From the raw drives: label every sample with its operating mode, cut
pure-mode windows (config/windows.yaml), and compute each window's summary
features (config/models.yaml). One row per window.

Input:  data/raw/**/*.csv   (python scripts/fetch_carobd.py downloads carOBD)
Output: data/windows/windows.parquet               the training file (not committed)
        data/windows/feature_schema.json           feature names, order, schema version
        outputs/evaluation/window_dataset_summary.csv  windows per mode (committed)

Usage:
    python training/04_build_windows.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd

import _paths  # noqa: F401  (adds src/ to sys.path)
from obd_anomaly.config import load_config
from obd_anomaly.features.extract import MissingRequiredSignal, extract_features, feature_names, schema
from obd_anomaly.features.windows import extract_windows
from obd_anomaly.pipeline import label_session

META = ["WINDOW_ID", "SESSION_ID", "VEHICLE_ID", "MODE_SEGMENT_ID", "MOTION_STATE", "WINDOW_START_SEC",
        "WINDOW_END_SEC", "DURATION_SEC", "SAMPLE_COUNT", "DISTINCT_TIMES", "MIN_MODE_CONFIDENCE",
        "QUALITY_FLAGS", "FEATURE_SCHEMA_VERSION", "CONFIG_VERSION"]


def build_session(path, config, vehicle_id: str) -> tuple[list[dict], int]:
    labeled = label_session(path, config, vehicle_id=vehicle_id)
    windows, _ = extract_windows(labeled, config)
    version = schema(config)["version"]
    rows, dropped = [], 0
    for w in windows.itertuples(index=False):
        in_window = labeled[
            (labeled["MODE_SEGMENT_ID"] == w.MODE_SEGMENT_ID)
            & (labeled["ELAPSED_SEC"] >= w.WINDOW_START_SEC)
            & (labeled["ELAPSED_SEC"] < w.WINDOW_END_SEC)
        ]
        try:
            features, flags = extract_features(in_window, config)
        except MissingRequiredSignal:
            dropped += 1
            continue
        row = w._asdict()
        row["VEHICLE_ID"] = vehicle_id
        existing = [f for f in str(row["QUALITY_FLAGS"]).split(";") if f]
        row["QUALITY_FLAGS"] = ";".join(sorted(set(existing + flags)))
        row["FEATURE_SCHEMA_VERSION"] = version
        row["CONFIG_VERSION"] = config.version_tag()
        row.update(features)
        rows.append(row)
    return rows, dropped


def summarize(data: pd.DataFrame, config) -> pd.DataFrame:
    modes = config.get("windows", "modes")
    rows = []
    for mode, policy in modes.items():
        part = data[data["MOTION_STATE"] == mode]
        rows.append({
            "MOTION_STATE": mode,
            "WINDOWS": len(part),
            "SESSIONS": part["SESSION_ID"].nunique(),
            "WINDOW_SEC": policy["window_sec"],
            "SUPPORTED_V1": policy.get("supported_v1", True),
        })
    return pd.DataFrame(rows)


def main() -> int:
    config = load_config()
    sessions = _paths.raw_sessions(config.path("data", "raw"))
    if not sessions:
        print("No raw sessions under data/raw/. Run: python scripts/fetch_carobd.py")
        return 1

    rows, dropped = [], 0
    for session, path in sessions.items():
        session_rows, session_dropped = build_session(path, config, vehicle_id=path.parent.name)
        rows += session_rows
        dropped += session_dropped

    names = feature_names(config)
    data = pd.DataFrame(rows, columns=META + names)

    out_dir = config.path("data", "windows")
    out_dir.mkdir(parents=True, exist_ok=True)
    data.to_parquet(out_dir / "windows.parquet", index=False)
    (out_dir / "feature_schema.json").write_text(json.dumps({
        "feature_schema_version": schema(config)["version"],
        "config_version": config.version_tag(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sessions": len(sessions),
        "features": names,
    }, indent=2))

    summary = summarize(data, config)
    eval_dir = config.path("outputs", "evaluation")
    eval_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(eval_dir / "window_dataset_summary.csv", index=False)

    print(f"{len(data)} windows from {len(sessions)} sessions, {len(names)} features each "
          f"({dropped} windows dropped for a missing required signal)\n")
    print(summary.to_string(index=False))
    print("\nSaved data/windows/windows.parquet, data/windows/feature_schema.json, "
          "outputs/evaluation/window_dataset_summary.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
