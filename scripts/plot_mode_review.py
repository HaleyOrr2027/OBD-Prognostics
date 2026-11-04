"""Step 27: manual mode-review plots.

Draws speed, acceleration, RPM, throttle and coolant with the detected mode as a
colored strip above them, plus mode confidence. If a reference label file is
given, a second strip shows the hand labels so disagreements are visible.

Usage:
    python scripts/plot_mode_review.py drive3
    python scripts/plot_mode_review.py drive3 --start 600 --end 900 --reference data/reference_labels/drive3_600-900.csv

Writes outputs/plots/mode_review_<session>[_<start>-<end>].png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
import _paths  # noqa: E402
from obd_anomaly.config import load_config  # noqa: E402
from obd_anomaly.pipeline import label_session  # noqa: E402

MODE_COLORS = {
    "STARTUP_WARMUP": "#2a78d6",
    "IDLE": "#1baf7a",
    "ACCELERATING": "#eda100",
    "CRUISING": "#008300",
    "COASTING_DECEL": "#e87ba4",
    "STRONG_DECEL": "#4a3aa7",
    "ENGINE_OFF": "#8a8983",
    "UNKNOWN_TRANSITION": "#c9c8c1",
}
REFERENCE_COLORS = {"idle": "#1baf7a", "accel": "#eda100", "steady": "#008300", "decel": "#e87ba4"}
SHORT = {
    "STARTUP_WARMUP": "startup", "IDLE": "idle", "ACCELERATING": "accel", "CRUISING": "cruise",
    "COASTING_DECEL": "decel", "STRONG_DECEL": "strong", "ENGINE_OFF": "off", "UNKNOWN_TRANSITION": "?",
    "idle": "idle", "accel": "accel", "steady": "steady", "decel": "decel",
}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e3e2dd", "#fcfcfb"


def strip(ax, starts, ends, states, colors, label, min_label_sec):
    for x0, x1, state in zip(starts, ends, states):
        ax.axvspan(x0, x1, color=colors.get(state, "#c9c8c1"), linewidth=0)
        if x1 - x0 >= min_label_sec:
            ax.text((x0 + x1) / 2, 0.5, SHORT.get(state, state), ha="center", va="center",
                    fontsize=7, color="#ffffff", weight="bold")
    ax.set_yticks([])
    ax.set_ylabel(label, fontsize=8, color=MUTED, rotation=0, ha="right", va="center")
    for side in ax.spines.values():
        side.set_visible(False)


def runs(times: pd.Series, states: pd.Series):
    change = (states != states.shift()).cumsum()
    grouped = pd.DataFrame({"t": times, "s": states, "g": change}).groupby("g", sort=False)
    starts = grouped["t"].min().to_numpy()
    ends = list(starts[1:]) + [times.iloc[-1]]
    return starts, ends, grouped["s"].first().to_numpy()


def trace(ax, t, y, label):
    ax.plot(t, y, linewidth=1.4, color=INK)
    ax.set_ylabel(label, fontsize=8, color=MUTED)
    ax.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=7)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session")
    parser.add_argument("--start", type=float)
    parser.add_argument("--end", type=float)
    parser.add_argument("--reference", help="reference label CSV to draw under the detector strip")
    args = parser.parse_args()

    config = load_config()
    sessions = _paths.raw_sessions(config.path("data", "raw"))
    if args.session not in sessions:
        print(f"Session '{args.session}' not found under data/raw/")
        return 1

    df = label_session(sessions[args.session], config)
    lo = args.start if args.start is not None else df["ELAPSED_SEC"].min()
    hi = args.end if args.end is not None else df["ELAPSED_SEC"].max()
    d = df[(df["ELAPSED_SEC"] >= lo) & (df["ELAPSED_SEC"] <= hi)].reset_index(drop=True)
    t = d["ELAPSED_SEC"]
    min_label = (hi - lo) / 25

    panels = [("ACCELERATION_MPS2", "accel\nm/s²"), ("ENGINE_RPM", "RPM"),
              ("THROTTLE_POSITION", "throttle\n%"), ("COOLANT_TEMPERATURE", "coolant\n°C"),
              ("MODE_CONFIDENCE", "mode\nconfidence")]
    strips = 2 if args.reference else 1
    heights = [0.45] * strips + [1.3] + [1.0] * len(panels)
    fig, axes = plt.subplots(len(heights), 1, figsize=(13, 1.2 * sum(heights) + 1.2), sharex=True,
                             gridspec_kw={"height_ratios": heights, "hspace": 0.15})
    fig.patch.set_facecolor(SURFACE)
    for ax in axes:
        ax.set_facecolor(SURFACE)

    strip(axes[0], *runs(t, d["MOTION_STATE"]), MODE_COLORS, "detected", min_label)
    if args.reference:
        ref = pd.read_csv(args.reference)
        strip(axes[1], ref["start_s"], ref["end_s"] + 1, ref["label"], REFERENCE_COLORS, "reference", min_label)

    speed_ax = axes[strips]
    trace(speed_ax, t, d["VEHICLE_SPEED"], "speed\nkm/h")
    speed_ax.plot(t, d["SPEED_SMOOTH_KMH"], linewidth=1.0, color=MODE_COLORS["STARTUP_WARMUP"], label="smoothed")
    speed_ax.legend(loc="upper right", fontsize=7, frameon=False, labelcolor=MUTED)

    p = config.get("modes", "motion_state")
    for ax, (column, label) in zip(axes[strips + 1:], panels):
        trace(ax, t, d[column], label)
        if column == "ACCELERATION_MPS2":
            for thr, name in ((p["accel_mps2"], "ACCELERATING"), (p["decel_mps2"], "COASTING_DECEL"),
                              (p["strong_decel_mps2"], "STRONG_DECEL")):
                ax.axhline(thr, color=MODE_COLORS[name], linewidth=1, linestyle="--")
    axes[-1].set_xlabel("session time (s)", fontsize=8, color=MUTED)

    present = [m for m in MODE_COLORS if m in set(d["MOTION_STATE"])]
    fig.legend(handles=[Patch(facecolor=MODE_COLORS[m], label=m) for m in present], loc="lower center",
               ncol=min(len(present), 4), frameon=False, fontsize=8, labelcolor=MUTED)
    title = f"{args.session} — detected operating modes" + (" vs hand labels" if args.reference else "")
    fig.suptitle(title, fontsize=12, color=INK, weight="bold", x=0.09, ha="left", y=0.995)
    fig.subplots_adjust(top=0.96, bottom=0.08, left=0.09, right=0.98)

    out_dir = config.path("outputs", "plots")
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{int(lo)}-{int(hi)}" if args.start is not None or args.end is not None else ""
    out = out_dir / f"mode_review_{args.session}{suffix}.png"
    fig.savefig(out, dpi=140, facecolor=SURFACE)
    print(f"Saved {out.relative_to(config.root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
