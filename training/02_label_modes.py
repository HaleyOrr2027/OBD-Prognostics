"""Step 25: label every raw session with operating modes.

Input:  data/raw/**/*.csv
Output: data/labeled/<session>.csv           one row per raw sample, with mode columns
        data/labeled/<session>_segments.csv  one row per stable mode segment
        data/labeled/_label_run.json         config version and per-session row counts

Usage:
    python training/02_label_modes.py                 # every session
    python training/02_label_modes.py drive3 drive12  # selected sessions
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import _paths  # noqa: F401  (adds src/ to sys.path)
from obd_anomaly.config import load_config
from obd_anomaly.modes.segments import segment_table
from obd_anomaly.pipeline import label_session

OUTPUT_COLUMNS = [
    "SESSION_ID", "VEHICLE_ID", "ELAPSED_SEC", "SAMPLE_DT_SEC", "VEHICLE_SPEED", "SPEED_SMOOTH_KMH",
    "ACCELERATION_MPS2", "ENGINE_RPM", "THROTTLE_POSITION", "ENGINE_LOAD", "COOLANT_TEMPERATURE",
    "SECONDS_SINCE_ENGINE_START", "ENGINE_STATE", "THERMAL_STATE", "MOTION_STATE_RAW",
    "MOTION_STATE", "LOAD_STATE", "MODE_CONFIDENCE", "MODE_REASON", "MODE_SEGMENT_ID",
    "DATA_QUALITY_OK", "QUALITY_FLAGS",
]


def main(selected: list[str]) -> int:
    config = load_config()
    sessions = _paths.raw_sessions(config.path("data", "raw"))
    if selected:
        missing = [s for s in selected if s not in sessions]
        if missing:
            print(f"Unknown session(s): {missing}")
            return 1
        sessions = {s: sessions[s] for s in selected}

    out_dir = config.path("data", "labeled")
    out_dir.mkdir(parents=True, exist_ok=True)
    run = {"config_version": config.version_tag(), "created_utc": datetime.now(timezone.utc).isoformat(), "sessions": {}}

    for session, path in sessions.items():
        labeled = label_session(path, config, vehicle_id=path.parent.name)
        labeled[OUTPUT_COLUMNS].to_csv(out_dir / f"{session}.csv", index=False)
        segment_table(labeled).to_csv(out_dir / f"{session}_segments.csv", index=False)
        run["sessions"][session] = {"source": str(path.relative_to(config.root)), "rows": len(labeled)}
        print(f"{session:10s} {len(labeled):6d} rows  {labeled['MODE_SEGMENT_ID'].nunique():4d} segments")

    (out_dir / "_label_run.json").write_text(json.dumps(run, indent=2))
    print(f"\nWrote {len(sessions)} labeled sessions to {out_dir.relative_to(config.root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
