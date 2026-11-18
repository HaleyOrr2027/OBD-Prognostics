"""Create a poster-ready request-vs-mode enrichment heatmap.

Instead of plotting raw percentages only, this shows how much more or less
likely each vehicle mode is after a given driver request compared with that
mode's overall frequency across all request events.

Example interpretation:
    2.0x = twice as likely as baseline
    1.0x = no change from baseline
    0.5x = half as likely as baseline

Usage:
    python scripts/plot_poster_request_mode_lift.py drive3 drive12

Output:
    outputs/evaluation/poster_request_mode_lift_4s.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABELED = ROOT / "data" / "labeled"
OUT = ROOT / "outputs" / "evaluation"
DELAY_SEC = 4.0

REQUEST_ORDER = [
    "ACCELERATE_REQUEST",
    "MAINTAIN_REQUEST",
    "RELEASE_ACCELERATOR",
    "NO_ACCELERATOR_REQUEST",
]
REQUEST_LABELS = {
    "ACCELERATE_REQUEST": "Accelerate",
    "MAINTAIN_REQUEST": "Maintain",
    "RELEASE_ACCELERATOR": "Release",
    "NO_ACCELERATOR_REQUEST": "No accel.",
}
MODE_ORDER = [
    "ACCELERATING",
    "CRUISING",
    "COASTING_DECEL",
    "IDLE",
    "STRONG_DECEL",
    "STARTUP_WARMUP",
]
MODE_LABELS = {
    "ACCELERATING": "Accelerating",
    "CRUISING": "Cruising",
    "COASTING_DECEL": "Coasting",
    "IDLE": "Idle",
    "STRONG_DECEL": "Strong decel.",
    "STARTUP_WARMUP": "Startup",
}


def load_session(session: str) -> pd.DataFrame:
    path = LABELED / f"{session}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run training/02_label_modes.py first.")
    frame = pd.read_csv(path)
    frame = frame.drop_duplicates(subset=["ELAPSED_SEC"]).sort_values("ELAPSED_SEC").copy()
    frame["SESSION_ID"] = session
    return frame[["SESSION_ID", "ELAPSED_SEC", "DRIVER_REQUEST", "MOTION_STATE"]]


def request_events(full: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for session, sf in full.groupby("SESSION_ID", sort=False):
        sf = sf.sort_values("ELAPSED_SEC").copy()
        changed = sf["DRIVER_REQUEST"].ne(sf["DRIVER_REQUEST"].shift())
        parts.append(sf.loc[changed])
    return pd.concat(parts, ignore_index=True)


def pair_events(events: pd.DataFrame, full: pd.DataFrame) -> pd.DataFrame:
    chunks = []
    for session, ef in events.groupby("SESSION_ID", sort=False):
        ef = ef[ef["DRIVER_REQUEST"].isin(REQUEST_ORDER)].copy()
        ef["TARGET_SEC"] = ef["ELAPSED_SEC"] + DELAY_SEC

        mf = full[full["SESSION_ID"] == session][["ELAPSED_SEC", "MOTION_STATE"]].copy()
        mf = mf.rename(columns={"ELAPSED_SEC": "MODE_SEC", "MOTION_STATE": "FUTURE_MODE"})
        matched = pd.merge_asof(
            ef.sort_values("TARGET_SEC"),
            mf.sort_values("MODE_SEC"),
            left_on="TARGET_SEC",
            right_on="MODE_SEC",
            direction="forward",
        )
        chunks.append(matched)
    return pd.concat(chunks, ignore_index=True).dropna(subset=["FUTURE_MODE"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions", nargs="+")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    full = pd.concat([load_session(s) for s in args.sessions], ignore_index=True)
    pairs = pair_events(request_events(full), full)

    counts = pd.crosstab(pairs["DRIVER_REQUEST"], pairs["FUTURE_MODE"])
    counts = counts.reindex(index=REQUEST_ORDER, columns=MODE_ORDER, fill_value=0).astype(float)

    row_total = counts.sum(axis=1).replace(0.0, float("nan"))
    cond = counts.div(row_total, axis=0).fillna(0.0)

    baseline = counts.sum(axis=0)
    baseline = baseline / baseline.sum()

    lift = cond.div(baseline.replace(0.0, float("nan")), axis=1).fillna(0.0)

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    image = ax.imshow(lift.to_numpy(dtype=float), aspect="auto", vmin=0.0, vmax=2.5)
    ax.set_xticks(range(len(MODE_ORDER)), [MODE_LABELS[m] for m in MODE_ORDER], rotation=25, ha="right")
    ax.set_yticks(range(len(REQUEST_ORDER)), [REQUEST_LABELS[r] for r in REQUEST_ORDER])
    ax.set_xlabel("Vehicle mode ~4 s later")
    ax.set_ylabel("Driver request")
    ax.set_title("Driver Request Changes Future Mode Likelihood")

    for r in range(lift.shape[0]):
        for c in range(lift.shape[1]):
            value = lift.iloc[r, c]
            if counts.iloc[r, c] > 0:
                ax.text(c, r, f"{value:.1f}×", ha="center", va="center", fontsize=9)

    cbar = fig.colorbar(image, ax=ax, pad=0.02)
    cbar.set_label("Likelihood vs. baseline")
    fig.tight_layout()
    out = OUT / "poster_request_mode_lift_4s.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)

    print("\nOverall mode baseline:")
    print((baseline * 100).round(1).to_string())
    print("\nRequest -> mode lift (~4 s later):")
    print(lift.round(2).to_string())
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
