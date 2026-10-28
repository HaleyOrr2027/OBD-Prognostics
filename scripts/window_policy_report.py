"""Step 30 evidence: segment durations and window yield per mode, for each hold time.

For every hold time (persistence dwell_sec) it labels all raw sessions, cuts
windows with config/windows.yaml, and reports per mode:
  - segment duration percentiles (what the window lengths are based on)
  - accepted windows and how many independent sessions they come from
  - mode-detection accuracy on the two reference-label files

This is the table for choosing dwell_sec together with the window policy.

Usage:
    python scripts/window_policy_report.py                 # dwell 0, 1, 2, 3 s
    python scripts/window_policy_report.py --dwell 0 1     # chosen values only

Writes outputs/evaluation/window_policy_report.csv and window_policy_decision.csv
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402
import score_modes  # noqa: E402
from obd_anomaly.config import load_config  # noqa: E402
from obd_anomaly.features.windows import extract_windows  # noqa: E402
from obd_anomaly.modes.segments import segment_table  # noqa: E402
from obd_anomaly.pipeline import label_session  # noqa: E402

REFERENCE = [
    ("drive12", "data/reference_labels/drive12_1480-1780.csv", "tuning"),
    ("drive3", "data/reference_labels/drive3_600-900.csv", "held out"),
]


def evaluate(dwell: float, base) -> tuple[pd.DataFrame, dict]:
    config = copy.deepcopy(base)
    config.modes["persistence"]["dwell_sec"] = dwell
    modes = list(config.get("windows", "modes"))

    segments, windows = [], []
    for path in _paths.raw_sessions(config.path("data", "raw")).values():
        labeled = label_session(path, config)
        segments.append(segment_table(labeled))
        windows.append(extract_windows(labeled, config)[0])
    seg = pd.concat(segments)
    win = pd.concat(windows)

    rows = []
    for mode in modes:
        s = seg[seg["MOTION_STATE"] == mode]
        w = win[win["MOTION_STATE"] == mode]
        q = s["DURATION_SEC"].quantile([0.25, 0.5, 0.75, 0.9]) if len(s) else pd.Series([np.nan] * 4)
        rows.append({
            "dwell_sec": dwell,
            "mode": mode,
            "segments": len(s),
            "segment_p25_sec": q.iloc[0],
            "segment_median_sec": q.iloc[1],
            "segment_p75_sec": q.iloc[2],
            "segment_p90_sec": q.iloc[3],
            "window_sec": config.windows["modes"][mode]["window_sec"],
            "windows": len(w),
            "window_sessions": w["SESSION_ID"].nunique(),
            "window_segments": w["MODE_SEGMENT_ID"].nunique(),
        })

    accuracy = {}
    for session, labels, role in REFERENCE:
        r = score_modes.score(session, labels, config)
        accuracy[f"{session}_{role}_exact"] = r["exact_agreement"]
        accuracy[f"{session}_{role}_within_2s"] = r["agreement_within_2s"]
    return pd.DataFrame(rows), accuracy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dwell", type=float, nargs="+", default=[0.0, 1.0, 2.0, 3.0])
    args = parser.parse_args()

    base = load_config()
    detail, decision = [], []
    for dwell in args.dwell:
        rows, accuracy = evaluate(dwell, base)
        detail.append(rows)
        summary = {"dwell_sec": dwell, **accuracy}
        for r in rows.itertuples():
            summary[f"{r.mode}_windows"] = r.windows
            summary[f"{r.mode}_sessions"] = r.window_sessions
        decision.append(summary)
        print(f"dwell {dwell:.1f} s done")

    detail = pd.concat(detail, ignore_index=True)
    decision = pd.DataFrame(decision)
    out_dir = base.path("outputs", "evaluation")
    out_dir.mkdir(parents=True, exist_ok=True)
    detail.round(2).to_csv(out_dir / "window_policy_report.csv", index=False)
    decision.round(3).to_csv(out_dir / "window_policy_decision.csv", index=False)

    pd.set_option("display.width", 200)
    print("\nWindows per mode (independent sessions in brackets) and detection accuracy:\n")
    view = pd.DataFrame({"dwell_sec": decision["dwell_sec"]})
    for mode in base.windows["modes"]:
        view[mode] = decision[f"{mode}_windows"].astype(str) + " (" + decision[f"{mode}_sessions"].astype(str) + ")"
    for session, _, role in REFERENCE:
        view[f"{session} exact / ±2s"] = (
            (decision[f"{session}_{role}_exact"] * 100).round(1).astype(str) + "% / "
            + (decision[f"{session}_{role}_within_2s"] * 100).round(1).astype(str) + "%"
        )
    print(view.to_string(index=False))
    print(f"\nSaved {(out_dir / 'window_policy_report.csv').relative_to(base.root)} and window_policy_decision.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
