"""Compare driver request at time t with vehicle mode after a response delay.

Usage:
    python scripts/plot_request_vs_mode_delay.py drive3 drive12

Outputs:
    outputs/evaluation/request_vs_mode_delay_summary.csv
    outputs/evaluation/request_vs_mode_delay_0p5s.png
    outputs/evaluation/request_vs_mode_delay_1p0s.png
    outputs/evaluation/request_vs_mode_delay_2p0s.png
    outputs/evaluation/request_vs_mode_delay_3p0s.png

Important:
- This does NOT measure ground-truth driver intent.
- It asks whether the detected vehicle mode changes in a more intuitive way
  shortly AFTER a driver-request label.
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
DELAYS = [0.5, 1.0, 2.0, 3.0]


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


def delayed_pairs(frame: pd.DataFrame, delay: float) -> pd.DataFrame:
    left = frame[["SESSION_ID", "ELAPSED_SEC", "DRIVER_REQUEST"]].copy()
    left["TARGET_SEC"] = left["ELAPSED_SEC"] + delay

    right = frame[["SESSION_ID", "ELAPSED_SEC", "MOTION_STATE"]].copy()
    right = right.rename(columns={"ELAPSED_SEC": "MODE_SEC", "MOTION_STATE": "FUTURE_MODE"})

    chunks = []
    for session, left_s in left.groupby("SESSION_ID", sort=False):
        right_s = right[right["SESSION_ID"] == session].sort_values("MODE_SEC")
        matched = pd.merge_asof(
            left_s.sort_values("TARGET_SEC"),
            right_s,
            left_on="TARGET_SEC",
            right_on="MODE_SEC",
            direction="nearest",
            tolerance=max(0.35, delay * 0.35),
        )
        chunks.append(matched)

    out = pd.concat(chunks, ignore_index=True)
    return out.dropna(subset=["FUTURE_MODE"])


def save_heatmap(data: pd.DataFrame, delay: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    counts = pd.crosstab(data["DRIVER_REQUEST"], data["FUTURE_MODE"])
    counts = counts.reindex(index=REQUEST_ORDER, columns=MODE_ORDER, fill_value=0)
    # Keep this numeric. Using pd.NA here can promote the DataFrame to object
    # dtype, which matplotlib cannot render with imshow.
    counts = counts.astype(float)
    row_totals = counts.sum(axis=1).replace(0.0, float("nan"))
    percent = (counts.div(row_totals, axis=0).fillna(0.0) * 100.0).astype(float)

    fig, ax = plt.subplots(figsize=(12, 6))
    image = ax.imshow(percent.to_numpy(dtype=float), aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(MODE_ORDER)), MODE_ORDER, rotation=35, ha="right")
    ax.set_yticks(range(len(REQUEST_ORDER)), REQUEST_ORDER)
    ax.set_xlabel(f"Detected vehicle mode about {delay:g} s later")
    ax.set_ylabel("Driver request at time t")
    ax.set_title(f"Driver request vs. vehicle mode after {delay:g} s (drive3 + drive12)")

    for r in range(percent.shape[0]):
        for c in range(percent.shape[1]):
            value = percent.iloc[r, c]
            count = counts.iloc[r, c]
            if count:
                ax.text(c, r, f"{value:.1f}%\n(n={count})", ha="center", va="center", fontsize=8)

    fig.colorbar(image, ax=ax, label="% within each driver-request row")
    fig.tight_layout()
    suffix = str(delay).replace(".", "p")
    fig.savefig(OUT / f"request_vs_mode_delay_{suffix}s.png", dpi=180)
    plt.close(fig)
    return counts, percent


def metric(percent: pd.DataFrame) -> dict[str, float]:
    # These are not accuracy scores. They are simple intuitive-alignment
    # indicators used only to compare response delays.
    return {
        "accelerate_to_accelerating_pct": float(percent.loc["ACCELERATE_REQUEST", "ACCELERATING"]),
        "release_to_coasting_pct": float(percent.loc["RELEASE_ACCELERATOR", "COASTING_DECEL"]),
        "release_to_strong_decel_pct": float(percent.loc["RELEASE_ACCELERATOR", "STRONG_DECEL"]),
        "maintain_to_cruising_pct": float(percent.loc["MAINTAIN_REQUEST", "CRUISING"]),
        "no_accel_to_idle_pct": float(percent.loc["NO_ACCELERATOR_REQUEST", "IDLE"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions", nargs="+")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    frames = [load_session(s) for s in args.sessions]
    data = pd.concat(frames, ignore_index=True)

    rows = []
    for delay in DELAYS:
        pairs = delayed_pairs(data, delay)
        _, percent = save_heatmap(pairs, delay)
        row = {"delay_sec": delay, "matched_timestamps": len(pairs), **metric(percent)}
        rows.append(row)

    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "request_vs_mode_delay_summary.csv", index=False, float_format="%.2f")

    print("\nDelay comparison (not accuracy):")
    print(summary.round(1).to_string(index=False))
    print(f"\nWrote delayed heatmaps and summary to {OUT}")


if __name__ == "__main__":
    main()
