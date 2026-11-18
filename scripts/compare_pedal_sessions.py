"""Compare carOBD accelerator sensor behavior across recordings.

This is a *sanity check*, not accuracy measurement: carOBD has no independently
observed foot-on/off event labels. A stopped vehicle is not proof of pedal release.

Run after:
    python scripts/fetch_carobd.py
    python training/02_label_modes.py drive3 drive12
    python scripts/compare_pedal_sessions.py drive3 drive12
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "carOBD"
LABELED = ROOT / "data" / "labeled"
REPORT = ROOT / "outputs" / "evaluation" / "pedal_session_comparison.md"
CHANNELS = {"D": "PEDAL_D ()", "E": "PEDAL_E ()"}
TIME = "ENGINE_RUN_TINE ()"  # Actual carOBD header (including upstream typo).
STATES = (
    "ACCELERATE_REQUEST", "MAINTAIN_REQUEST", "RELEASE_ACCELERATOR",
    "NO_ACCELERATOR_REQUEST", "UNKNOWN_REQUEST",
)


def summarize(session: str, baselines: dict[str, float], tolerance: float) -> list[str]:
    raw_path = RAW / f"{session}.csv"
    labeled_path = LABELED / f"{session}.csv"
    for path in (raw_path, labeled_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}. Fetch data and label sessions first.")

    raw = pd.read_csv(raw_path, index_col=False, skipinitialspace=True)
    required = [TIME, "VEHICLE_SPEED ()", "ENGINE_RPM ()", *CHANNELS.values()]
    missing = [column for column in required if column not in raw]
    if missing:
        raise ValueError(f"{session}: missing raw columns {missing}")
    numeric = raw[required].apply(pd.to_numeric, errors="coerce")
    # Multiple rows from the same engine timestamp are not independent samples.
    distinct = numeric.groupby(TIME, sort=True).median(numeric_only=True)
    stopped = distinct.loc[
        (distinct["VEHICLE_SPEED ()"] <= 0.01)
        & (distinct["ENGINE_RPM ()"] > 600)
    ]

    labeled = pd.read_csv(labeled_path)
    required_labels = [
        "ELAPSED_SEC", "DRIVER_REQUEST", "DRIVER_REQUEST_SOURCE",
        "DRIVER_REQUEST_REASON", "PEDAL_DELTA_PERCENT",
    ]
    missing_labels = [column for column in required_labels if column not in labeled]
    if missing_labels:
        raise ValueError(f"{session}: missing labeled columns {missing_labels}")
    # Count distinct output timestamps, not duplicated raw PID rows.
    events = labeled.drop_duplicates(subset=["ELAPSED_SEC"]).copy()
    lines = [
        f"## {session}",
        "",
        f"- Raw rows: **{len(raw)}**; distinct engine timestamps: **{len(distinct)}**.",
        f"- Stationary, engine-running timestamps: **{len(stopped)}** "
        "(not verified pedal-release events).",
        "",
        "| Pedal channel | Configured candidate baseline | Minimum observed | "
        "5th percentile | Stationary median | Difference from baseline |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for channel, raw_name in CHANNELS.items():
        key = f"ACCELERATOR_PEDAL_POSITION_{channel}"
        series = distinct[raw_name].dropna()
        rest = stopped[raw_name].dropna()
        baseline = float(baselines[key])
        minimum = float(series.min()) if len(series) else None
        fifth = float(series.quantile(.05)) if len(series) else None
        median = float(rest.median()) if len(rest) else None
        difference = (median - baseline) if median is not None else None

        def fmt(value: float | None) -> str:
            return "N/A" if value is None else f"{value:.3f}%"

        lines.append(
            f"| {channel} | {fmt(baseline)} | {fmt(minimum)} | {fmt(fifth)} | "
            f"{fmt(median)} | {fmt(difference)} |"
        )
        if difference is None:
            lines.append(f"\nChannel {channel}: cannot compare stationary readings (none available).")
        elif abs(difference) > tolerance:
            lines.append(
                f"\nChannel {channel}: stationary median differs from the drive3 "
                f"candidate by more than {tolerance:.2f} percentage points. "
                "**Investigate; this alone does not prove the calibration is wrong.**"
            )
        else:
            lines.append(
                f"\nChannel {channel}: stationary median is within "
                f"{tolerance:.2f} points of the drive3 candidate. "
                "**This does not prove the driver's foot was off the pedal.**"
            )

    counts = events["DRIVER_REQUEST"].value_counts()
    lines += [
        "",
        "### Detector outputs (distinct elapsed timestamps)",
        "",
        "| Detector output | Count |",
        "|---|---:|",
    ]
    for state in STATES:
        lines.append(f"| {state} | {int(counts.get(state, 0))} |")
    lines += ["", "### Input source", "", "| Source | Count |", "|---|---:|"]
    for source, count in events["DRIVER_REQUEST_SOURCE"].value_counts().items():
        lines.append(f"| {source} | {int(count)} |")

    lines += [
        "", "### Examples to review manually", "",
        "These are examples of what the **code reported**, not proof of actual pedal motion.",
        "", "| Elapsed second | Label | Pedal change | Reason |",
        "|---:|---|---:|---|",
    ]
    for state in ("ACCELERATE_REQUEST", "RELEASE_ACCELERATOR",
                  "MAINTAIN_REQUEST", "NO_ACCELERATOR_REQUEST", "UNKNOWN_REQUEST"):
        matching = events.loc[events["DRIVER_REQUEST"] == state].head(3)
        for _, row in matching.iterrows():
            change = pd.to_numeric(row["PEDAL_DELTA_PERCENT"], errors="coerce")
            change_text = "N/A" if pd.isna(change) else f"{float(change):+.3f}"
            lines.append(
                f"| {float(row['ELAPSED_SEC']):.1f} | {state} | "
                f"{change_text} | {row['DRIVER_REQUEST_REASON']} |"
            )
    lines.append("")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessions", nargs="+", help="e.g. drive3 drive12")
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    runtime = yaml.safe_load((ROOT / "config" / "runtime.yaml").read_text())
    settings = runtime["driver_request"]
    baselines = settings["carobd_pedal_baselines"]
    tolerance = float(settings["carobd_rest_tolerance_percent"])
    lines = [
        "# Cross-drive accelerator-request sanity check", "",
        "**Not a measured accuracy result.** These recordings have no independent "
        "observations of actual pedal presses/releases. Stationary readings are "
        "only candidate resting values. Counts and examples describe detector "
        "behavior; human-observed pedal events are still needed.", "",
        "Configured candidate baselines were originally measured on drive3; "
        "drive12 is an out-of-session comparison.", "",
    ]
    for session in args.sessions:
        lines.extend(summarize(session, baselines, tolerance))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: {args.output}")
    print("IMPORTANT: No independent pedal ground truth; accuracy cannot be claimed.")


if __name__ == "__main__":
    main()
