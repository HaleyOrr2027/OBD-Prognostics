"""Create request-vs-mode comparison tables and charts from labeled sessions.

Usage:
    python scripts/plot_request_vs_mode.py drive3 drive12

Outputs:
    outputs/evaluation/request_vs_mode_counts.csv
    outputs/evaluation/request_vs_mode_percent.csv
    outputs/evaluation/request_vs_mode_heatmap.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABELED = ROOT / "data" / "labeled"
OUT = ROOT / "outputs" / "evaluation"

REQUEST_ORDER = [
    "NO_ACCELERATOR_REQUEST",
    "MAINTAIN_REQUEST",
    "ACCELERATE_REQUEST",
    "RELEASE_ACCELERATOR",
    "UNKNOWN_REQUEST",
]
MODE_ORDER = [
    "ENGINE_OFF",
    "STARTUP_WARMUP",
    "IDLE",
    "ACCELERATING",
    "CRUISING",
    "COASTING_DECEL",
    "STRONG_DECEL",
    "UNKNOWN_TRANSITION",
]


def load_session(session: str) -> pd.DataFrame:
    path = LABELED / f"{session}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run training/02_label_modes.py first.")
    frame = pd.read_csv(path)
    required = ["ELAPSED_SEC", "DRIVER_REQUEST", "MOTION_STATE"]
    missing = [c for c in required if c not in frame]
    if missing:
        raise ValueError(f"{session}: missing columns {missing}")
    # carOBD has duplicate PID rows at the same elapsed time. Compare one
    # detector result per distinct time point, not duplicated raw rows.
    frame = frame.drop_duplicates(subset=["ELAPSED_SEC"]).copy()
    frame["SESSION_ID"] = session
    return frame[["SESSION_ID", "ELAPSED_SEC", "DRIVER_REQUEST", "MOTION_STATE"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions", nargs="+")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    data = pd.concat([load_session(s) for s in args.sessions], ignore_index=True)

    counts = pd.crosstab(data["DRIVER_REQUEST"], data["MOTION_STATE"])
    counts = counts.reindex(index=REQUEST_ORDER, columns=MODE_ORDER, fill_value=0)
    counts.to_csv(OUT / "request_vs_mode_counts.csv")

    row_totals = counts.sum(axis=1).replace(0, pd.NA)
    percent = counts.div(row_totals, axis=0).fillna(0) * 100.0
    percent.to_csv(OUT / "request_vs_mode_percent.csv", float_format="%.2f")

    fig, ax = plt.subplots(figsize=(12, 6))
    image = ax.imshow(percent.to_numpy(), aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(MODE_ORDER)), MODE_ORDER, rotation=35, ha="right")
    ax.set_yticks(range(len(REQUEST_ORDER)), REQUEST_ORDER)
    ax.set_xlabel("Detected vehicle mode")
    ax.set_ylabel("Driver request")
    ax.set_title("Driver request vs. detected vehicle mode (drive3 + drive12)")

    for r in range(percent.shape[0]):
        for c in range(percent.shape[1]):
            value = percent.iloc[r, c]
            count = counts.iloc[r, c]
            if count:
                ax.text(c, r, f"{value:.1f}%\n(n={count})", ha="center", va="center", fontsize=8)

    fig.colorbar(image, ax=ax, label="% of timestamps within each driver-request row")
    fig.tight_layout()
    fig.savefig(OUT / "request_vs_mode_heatmap.png", dpi=180)
    plt.close(fig)

    print("\nCounts:")
    print(counts.to_string())
    print("\nRow percentages:")
    print(percent.round(1).to_string())
    print(f"\nWrote chart and CSVs to {OUT}")


if __name__ == "__main__":
    main()
