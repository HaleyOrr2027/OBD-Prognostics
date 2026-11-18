"""Make clearer driver-request vs vehicle-response visualizations.

Run after:
    python training/02_label_modes.py drive3 drive12
    python scripts/plot_request_response_windows.py drive3 drive12
    python scripts/plot_request_response_visuals.py drive3 drive12

Outputs:
    outputs/evaluation/request_response_window_heatmap.png
    outputs/evaluation/request_response_4s_by_session.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "evaluation"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions", nargs="+")
    args = parser.parse_args()

    events_path = OUT / "request_response_window_events.csv"
    summary_path = OUT / "request_response_window_summary.csv"
    if not events_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError(
            "Missing response-window CSVs. Run "
            "'python scripts/plot_request_response_windows.py drive3 drive12' first."
        )

    events = pd.read_csv(events_path)
    summary = pd.read_csv(summary_path)

    heat = summary.pivot(
        index="DRIVER_REQUEST", columns="WINDOW_SEC", values="match_pct"
    ).fillna(0.0)
    fig, ax = plt.subplots(figsize=(8, 5))
    image = ax.imshow(heat.to_numpy(dtype=float), aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(heat.columns)), [f"{c:g} s" for c in heat.columns])
    ax.set_yticks(range(len(heat.index)), heat.index)
    ax.set_xlabel("Future response window")
    ax.set_ylabel("Driver request event")
    ax.set_title("Expected vehicle response found within future window")
    for r in range(heat.shape[0]):
        for c in range(heat.shape[1]):
            ax.text(c, r, f"{heat.iloc[r, c]:.1f}%", ha="center", va="center")
    fig.colorbar(image, ax=ax, label="Events with expected response (%)")
    fig.tight_layout()
    fig.savefig(OUT / "request_response_window_heatmap.png", dpi=180)
    plt.close(fig)

    four = events[events["WINDOW_SEC"] == 4.0].copy()
    four = four[four["SESSION_ID"].isin(args.sessions)]
    per_session = (
        four.groupby(["SESSION_ID", "DRIVER_REQUEST"])["EXPECTED_RESPONSE_SEEN"]
        .mean()
        .mul(100.0)
        .reset_index(name="match_pct")
    )
    pivot = per_session.pivot(
        index="DRIVER_REQUEST", columns="SESSION_ID", values="match_pct"
    ).fillna(0.0)
    ax = pivot.plot(kind="bar", figsize=(11, 6))
    ax.set_ylim(0, 100)
    ax.set_ylabel("Events with expected response (%)")
    ax.set_xlabel("Driver request event")
    ax.set_title("4-second response-window match rate by drive")
    ax.legend(title="Session")
    ax.figure.tight_layout()
    ax.figure.savefig(OUT / "request_response_4s_by_session.png", dpi=180)
    plt.close(ax.figure)

    print("\n4-second response-window match rate by session:")
    print(per_session.round(1).to_string(index=False))
    print(f"\nWrote visualizations to {OUT}")


if __name__ == "__main__":
    main()
