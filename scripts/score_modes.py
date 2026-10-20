"""Step 27/42: score the mode detector against hand-labeled reference intervals.

Reference labels use plain driving vocabulary (idle / accel / decel / steady),
one row per interval, in session seconds (ELAPSED_SEC; for carOBD this equals
ENGINE_RUN_TIME). Detector states are collapsed onto that vocabulary:

    IDLE                          -> idle
    ACCELERATING                  -> accel
    CRUISING                      -> steady
    COASTING_DECEL, STRONG_DECEL  -> decel
    ENGINE_OFF, STARTUP_WARMUP,
    UNKNOWN_TRANSITION            -> unscored  (always counted as a miss)

At each whole second the detector's answer is the state of the latest sample at
or before that second, which is what the live system would report.

Usage:
    python scripts/score_modes.py drive3 data/reference_labels/drive3_600-900.csv

Writes outputs/evaluation/mode_score_<label file stem>.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
import _paths  # noqa: E402
from obd_anomaly.config import Config, load_config  # noqa: E402
from obd_anomaly.pipeline import label_session  # noqa: E402

COLLAPSE = {
    "IDLE": "idle",
    "ACCELERATING": "accel",
    "CRUISING": "steady",
    "COASTING_DECEL": "decel",
    "STRONG_DECEL": "decel",
}
CLASSES = ["idle", "accel", "decel", "steady"]
TOLERANCE_SEC = 2


def reference_per_second(label_file: Path) -> pd.Series:
    labels = pd.read_csv(label_file)
    bad = set(labels["label"]) - set(CLASSES)
    if bad:
        raise ValueError(f"Unknown reference label(s) {bad}; use {CLASSES}")
    seconds = {}
    for row in labels.itertuples():
        for s in range(int(row.start_s), int(row.end_s) + 1):
            seconds[s] = row.label
    return pd.Series(seconds, name="reference").sort_index()


def detector_per_second(labeled: pd.DataFrame, seconds: pd.Index) -> pd.Series:
    states = labeled[["ELAPSED_SEC", "MOTION_STATE"]].sort_values("ELAPSED_SEC")
    query = pd.DataFrame({"ELAPSED_SEC": seconds.astype(float)})
    merged = pd.merge_asof(query, states, on="ELAPSED_SEC", direction="backward")
    collapsed = merged["MOTION_STATE"].map(COLLAPSE).fillna("unscored")
    return pd.Series(collapsed.to_numpy(), index=seconds, name="detected")


def transition_delays(reference: pd.Series, detected: pd.Series, horizon: int = 10) -> list[int]:
    """Seconds from each reference label change until the detector agrees."""
    delays = []
    changes = reference.index[1:][reference.to_numpy()[1:] != reference.to_numpy()[:-1]]
    for start in changes:
        target = reference[start]
        for lag in range(horizon + 1):
            s = start + lag
            if s in detected.index and detected[s] == target:
                delays.append(lag)
                break
    return delays


def score(session: str, label_file: str | Path, config: Config | None = None) -> dict:
    config = config or load_config()
    sessions = _paths.raw_sessions(config.path("data", "raw"))
    if session not in sessions:
        raise SystemExit(f"Session '{session}' not found under data/raw/")

    labeled = label_session(sessions[session], config)
    reference = reference_per_second(Path(label_file))
    detected = detector_per_second(labeled, reference.index)

    exact = float((detected == reference).mean())
    near = []
    for s, target in reference.items():
        window = detected.reindex(range(s - TOLERANCE_SEC, s + TOLERANCE_SEC + 1)).dropna()
        near.append(target in set(window))

    confusion = pd.crosstab(reference, detected).reindex(index=CLASSES, columns=CLASSES + ["unscored"], fill_value=0)
    recall = {c: round(float(confusion.loc[c, c] / max(confusion.loc[c].sum(), 1)), 3) for c in CLASSES}
    delays = transition_delays(reference, detected)

    window = labeled[(labeled["ELAPSED_SEC"] >= reference.index.min()) & (labeled["ELAPSED_SEC"] <= reference.index.max())]
    minutes = (reference.index.max() - reference.index.min() + 1) / 60

    return {
        "session": session,
        "label_file": str(label_file),
        "config_version": config.version_tag(),
        "seconds_scored": int(len(reference)),
        "exact_agreement": round(exact, 3),
        f"agreement_within_{TOLERANCE_SEC}s": round(float(np.mean(near)), 3),
        "recall": recall,
        "unscored_fraction": round(float((detected == "unscored").mean()), 3),
        "median_transition_delay_sec": float(np.median(delays)) if delays else None,
        "segments_per_minute": round(window["MODE_SEGMENT_ID"].nunique() / minutes, 2),
        "confusion_matrix": confusion.to_dict(orient="index"),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1
    result = score(argv[0], argv[1])
    config = load_config()
    out_dir = config.path("outputs", "evaluation")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"mode_score_{Path(argv[1]).stem}.json"
    out_path.write_text(json.dumps(result, indent=2))

    print(f"Session:                  {result['session']}  ({result['seconds_scored']} seconds)")
    print(f"Exact agreement:          {result['exact_agreement']:.1%}")
    print(f"Agreement within +/-{TOLERANCE_SEC} s:  {result[f'agreement_within_{TOLERANCE_SEC}s']:.1%}")
    print(f"Unscored:                 {result['unscored_fraction']:.1%}")
    print(f"Median transition delay:  {result['median_transition_delay_sec']} s")
    print("Recall:                   " + ", ".join(f"{k} {v:.0%}" for k, v in result["recall"].items()))
    print("\nConfusion (rows = reference, columns = detector), seconds:")
    print(pd.DataFrame(result["confusion_matrix"]).T.to_string())
    print(f"\nSaved {out_path.relative_to(config.root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
