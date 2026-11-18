"""Evaluate whether an expected vehicle response appears after a request event.

This avoids pretending the carOBD historical clock can resolve sub-second
response timing. Instead, each request-change event is evaluated over a future
response window.

Usage:
    python scripts/plot_request_response_windows.py drive3 drive12
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABELED = ROOT / "data" / "labeled"
OUT = ROOT / "outputs" / "evaluation"

WINDOWS = [2.0, 4.0, 6.0]

# These are intentionally broad response families, not "fault" rules.
EXPECTED = {
    "ACCELERATE_REQUEST": {"ACCELERATING"},
    "RELEASE_ACCELERATOR": {"COASTING_DECEL", "STRONG_DECEL", "CRUISING"},
    "MAINTAIN_REQUEST": {"CRUISING", "ACCELERATING"},
    "NO_ACCELERATOR_REQUEST": {"IDLE", "COASTING_DECEL", "CRUISING"},
}


def load_session(session: str) -> pd.DataFrame:
    path = LABELED / f"{session}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run training/02_label_modes.py first.")
    frame = pd.read_csv(path)
    required = ["ELAPSED_SEC", "DRIVER_REQUEST", "MOTION_STATE"]
    missing = [c for c in required if c not in frame]
    if missing:
        raise ValueError(f"{session}: missing columns {missing}")
    frame = frame.drop_duplicates(subset=["ELAPSED_SEC"]).copy()
    frame = frame.sort_values("ELAPSED_SEC").reset_index(drop=True)
    frame["SESSION_ID"] = session
    return frame[["SESSION_ID", "ELAPSED_SEC", "DRIVER_REQUEST", "MOTION_STATE"]]


def request_events(frame: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for session, sf in frame.groupby("SESSION_ID", sort=False):
        sf = sf.sort_values("ELAPSED_SEC").copy()
        changed = sf["DRIVER_REQUEST"].ne(sf["DRIVER_REQUEST"].shift())
        parts.append(sf.loc[changed])
    return pd.concat(parts, ignore_index=True)


def time_resolution(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for session, sf in frame.groupby("SESSION_ID", sort=False):
        t = sf["ELAPSED_SEC"].drop_duplicates().sort_values()
        dt = t.diff().dropna()
        dt = dt[dt > 0]
        rows.append({
            "session": session,
            "distinct_timestamps": len(t),
            "median_positive_step_sec": float(dt.median()) if len(dt) else float("nan"),
            "min_positive_step_sec": float(dt.min()) if len(dt) else float("nan"),
            "p90_positive_step_sec": float(dt.quantile(.90)) if len(dt) else float("nan"),
        })
    return pd.DataFrame(rows)


def evaluate_window(events: pd.DataFrame, full: pd.DataFrame, window: float) -> pd.DataFrame:
    rows = []
    for _, event in events.iterrows():
        request = event["DRIVER_REQUEST"]
        if request not in EXPECTED:
            continue
        sf = full[full["SESSION_ID"] == event["SESSION_ID"]]
        start = float(event["ELAPSED_SEC"])
        future = sf[(sf["ELAPSED_SEC"] > start) & (sf["ELAPSED_SEC"] <= start + window)]
        observed = set(future["MOTION_STATE"].dropna())
        expected = EXPECTED[request]
        matched = bool(observed & expected)
        rows.append({
            "SESSION_ID": event["SESSION_ID"],
            "EVENT_SEC": start,
            "DRIVER_REQUEST": request,
            "WINDOW_SEC": window,
            "EXPECTED_MODES": "|".join(sorted(expected)),
            "OBSERVED_MODES": "|".join(sorted(observed)),
            "EXPECTED_RESPONSE_SEEN": matched,
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions", nargs="+")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    full = pd.concat([load_session(s) for s in args.sessions], ignore_index=True)
    events = request_events(full)

    timing = time_resolution(full)
    timing.to_csv(OUT / "request_response_time_resolution.csv", index=False)

    all_results = []
    for window in WINDOWS:
        result = evaluate_window(events, full, window)
        all_results.append(result)
    results = pd.concat(all_results, ignore_index=True)
    results.to_csv(OUT / "request_response_window_events.csv", index=False)

    summary = (
        results.groupby(["WINDOW_SEC", "DRIVER_REQUEST"])["EXPECTED_RESPONSE_SEEN"]
        .agg(["count", "mean"])
        .reset_index()
    )
    summary["match_pct"] = summary["mean"] * 100.0
    summary = summary.drop(columns=["mean"])
    summary.to_csv(OUT / "request_response_window_summary.csv", index=False, float_format="%.2f")

    pivot = summary.pivot(index="DRIVER_REQUEST", columns="WINDOW_SEC", values="match_pct").fillna(0.0)
    ax = pivot.plot(kind="bar", figsize=(11, 6))
    ax.set_ylabel("Events with an expected response seen (%)")
    ax.set_xlabel("Driver request event")
    ax.set_ylim(0, 100)
    ax.set_title("Expected vehicle response within a future window (drive3 + drive12)")
    ax.legend(title="Response window (s)")
    ax.figure.tight_layout()
    ax.figure.savefig(OUT / "request_response_window_summary.png", dpi=180)
    plt.close(ax.figure)

    print("\nObserved timestamp resolution:")
    print(timing.round(2).to_string(index=False))
    print("\nExpected-response match rate by future window (not accuracy):")
    print(summary.round(1).to_string(index=False))
    print(f"\nWrote response-window outputs to {OUT}")


if __name__ == "__main__":
    main()
