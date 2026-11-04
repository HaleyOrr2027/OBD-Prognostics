"""Run the old and new RPM rules side by side on every raw session.

Old rules (before Oct 21): IDLE capped at idle_rpm_max = 1300 RPM and judged
from smoothed speed only, and RPM below running_rpm_min always means ENGINE_OFF.
New rules (config/modes.yaml): no RPM cap on IDLE, IDLE also needs the raw
speed reading stopped, and RPM that says "off" while speed says "moving" makes
the engine state UNKNOWN (RPM_SPEED_CONFLICT).

Reports what Haley asked to see before replacing the rules:
  - how often each version produces UNKNOWN_TRANSITION / ENGINE_OFF / IDLE
  - accuracy on the reference-label files
  - usable windows gained or lost per mode
  - every sample whose label changed, as an old -> new table

Usage:
    python scripts/compare_mode_rules.py

Writes outputs/evaluation/mode_rules_comparison.csv and mode_rules_label_changes.csv
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402
import score_modes  # noqa: E402
from obd_anomaly.config import load_config  # noqa: E402
from obd_anomaly.features.windows import extract_windows  # noqa: E402
from obd_anomaly.pipeline import label_session  # noqa: E402

REFERENCE = [
    ("drive12", "data/reference_labels/drive12_1480-1780.csv"),
    ("drive3", "data/reference_labels/drive3_600-900.csv"),
]
STATES = ["IDLE", "ACCELERATING", "CRUISING", "COASTING_DECEL", "STRONG_DECEL",
          "STARTUP_WARMUP", "ENGINE_OFF", "UNKNOWN_TRANSITION"]


def old_rules(config):
    old = copy.deepcopy(config)
    old.modes["motion_state"]["idle_rpm_max"] = 1300.0
    old.modes["engine_state"]["rpm_speed_conflict_check"] = False
    old.modes["motion_state"]["idle_requires_raw_stop"] = False
    return old


def run(config):
    labels, windows = [], []
    for session, path in _paths.raw_sessions(config.path("data", "raw")).items():
        d = label_session(path, config)
        labels.append(d[["SESSION_ID", "ELAPSED_SEC", "MOTION_STATE", "MODE_REASON", "ENGINE_RPM", "VEHICLE_SPEED"]])
        windows.append(extract_windows(d, config)[0])
    return pd.concat(labels, ignore_index=True), pd.concat(windows, ignore_index=True)


def main() -> int:
    new_cfg = load_config()
    versions = {"old": old_rules(new_cfg), "new": new_cfg}
    results, label_sets = [], {}

    for name, cfg in versions.items():
        labels, windows = run(cfg)
        label_sets[name] = labels
        row = {"rules": name, "samples": len(labels)}
        share = labels["MOTION_STATE"].value_counts(normalize=True)
        for state in ("UNKNOWN_TRANSITION", "ENGINE_OFF", "IDLE"):
            row[f"{state}_pct"] = round(100 * share.get(state, 0.0), 3)
        row["conflict_samples"] = int(labels["MODE_REASON"].fillna("").str.contains("RPM_SPEED_CONFLICT").sum())
        row["idle_rpm_high_samples"] = int(labels["MODE_REASON"].fillna("").str.contains("IDLE_RPM_HIGH").sum())
        for mode in cfg.windows["modes"]:
            w = windows[windows["MOTION_STATE"] == mode]
            row[f"{mode}_windows"] = len(w)
            row[f"{mode}_sessions"] = w["SESSION_ID"].nunique()
        for session, ref in REFERENCE:
            r = score_modes.score(session, ref, cfg)
            row[f"{session}_exact"] = r["exact_agreement"]
            row[f"{session}_within_2s"] = r["agreement_within_2s"]
        results.append(row)
        print(f"{name} rules done")

    comparison = pd.DataFrame(results).set_index("rules").T
    comparison["change"] = comparison["new"] - comparison["old"]

    old, new = label_sets["old"], label_sets["new"]
    changed = old["MOTION_STATE"] != new["MOTION_STATE"]
    changes = (
        pd.DataFrame({"old": old.loc[changed, "MOTION_STATE"], "new": new.loc[changed, "MOTION_STATE"],
                      "session": old.loc[changed, "SESSION_ID"]})
        .groupby(["old", "new"])
        .agg(samples=("session", "size"), sessions=("session", "nunique"))
        .reset_index()
        .sort_values("samples", ascending=False)
    )

    out_dir = new_cfg.path("outputs", "evaluation")
    out_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(out_dir / "mode_rules_comparison.csv")
    changes.to_csv(out_dir / "mode_rules_label_changes.csv", index=False)

    pd.set_option("display.width", 200)
    print("\nOld vs new rules, all sessions:\n")
    print(comparison.to_string())
    print(f"\nLabels that changed ({int(changed.sum())} of {len(old)} samples, {100 * changed.mean():.2f}%):\n")
    print(changes.to_string(index=False))
    print(f"\nSaved {(out_dir / 'mode_rules_comparison.csv').relative_to(new_cfg.root)} and mode_rules_label_changes.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
