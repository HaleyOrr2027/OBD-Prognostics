"""Poster figure: what the driver did vs what the detector saw, on a held-out drive.

Two strips (hand labels on top, real-time detector below) over the speed trace
for drive3 seconds 600-900, with the headline agreement numbers. Built for
print: large type, four plain-language categories, vector PDF plus 300 dpi PNG.

Usage:
    python scripts/poster_mode_figure.py

Writes outputs/plots/poster_mode_detection.pdf and .png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402
import score_modes  # noqa: E402
from obd_anomaly.config import load_config  # noqa: E402
from obd_anomaly.pipeline import label_session  # noqa: E402

SESSION = "drive3"
LABELS = "data/reference_labels/drive3_600-900.csv"
START, END = 600, 900

# Plain-language categories, in the validated categorical order.
CATEGORIES = {
    "idle": ("Stopped", "#1baf7a"),
    "accel": ("Speeding up", "#eda100"),
    "steady": ("Steady", "#008300"),
    "decel": ("Slowing down", "#e87ba4"),
    "unscored": ("Not classified", "#c9c8c1"),
}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e3e2dd", "#fcfcfb"


def segments(times: pd.Series, labels: pd.Series):
    """Contiguous runs of one label as (start, end, label)."""
    change = (labels != labels.shift()).cumsum()
    runs = pd.DataFrame({"t": times.to_numpy(), "l": labels.to_numpy(), "g": change.to_numpy()})
    first = runs.groupby("g", sort=False).first()
    starts = first["t"].to_numpy()
    ends = list(starts[1:]) + [times.iloc[-1] + 1]
    return list(zip(starts, ends, first["l"]))


def draw_strip(ax, runs, title):
    for x0, x1, label in runs:
        ax.axvspan(x0, x1, ymin=0.0, ymax=1.0, color=CATEGORIES[label][1], linewidth=0)
        ax.axvline(x0, color=SURFACE, linewidth=1.5)  # surface gap between segments
    ax.set_yticks([])
    for side in ax.spines.values():
        side.set_visible(False)
    ax.text(-0.005, 0.5, title, transform=ax.transAxes, ha="right", va="center", fontsize=17, color=INK)


def main() -> int:
    config = load_config()
    session_path = _paths.raw_sessions(config.path("data", "raw"))[SESSION]
    labeled = label_session(session_path, config)
    result = score_modes.score(SESSION, LABELS, config)

    reference = score_modes.reference_per_second(Path(LABELS))
    detected = score_modes.detector_per_second(labeled, reference.index)
    seconds = pd.Series(reference.index, index=reference.index)

    window = labeled[(labeled["ELAPSED_SEC"] >= START) & (labeled["ELAPSED_SEC"] <= END)]

    fig = plt.figure(figsize=(16, 7.2))
    fig.patch.set_facecolor(SURFACE)
    grid = fig.add_gridspec(3, 1, height_ratios=[0.5, 0.5, 2.4], hspace=0.12, left=0.2, right=0.985, top=0.80, bottom=0.17)
    ax_ref = fig.add_subplot(grid[0])
    ax_det = fig.add_subplot(grid[1], sharex=ax_ref)
    ax_speed = fig.add_subplot(grid[2], sharex=ax_ref)
    for ax in (ax_ref, ax_det, ax_speed):
        ax.set_facecolor(SURFACE)

    draw_strip(ax_ref, segments(seconds, reference), "What the car did\n(hand-labeled)")
    draw_strip(ax_det, segments(seconds, detected), "What the detector saw\n(real time)")
    plt.setp(ax_ref.get_xticklabels(), visible=False)
    plt.setp(ax_det.get_xticklabels(), visible=False)

    ax_speed.plot(window["ELAPSED_SEC"], window["VEHICLE_SPEED"], color=INK, linewidth=2.2, solid_capstyle="round")
    ax_speed.set_ylabel("Speed (km/h)", fontsize=16, color=MUTED)
    ax_speed.set_xlabel("Time into the drive (seconds)", fontsize=16, color=MUTED)
    ax_speed.set_xlim(START, END + 1)
    ax_speed.set_ylim(bottom=0)
    ax_speed.grid(True, axis="y", color=GRID, linewidth=1)
    ax_speed.set_axisbelow(True)
    ax_speed.tick_params(colors=MUTED, labelsize=14)
    for side in ("top", "right"):
        ax_speed.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax_speed.spines[side].set_color(GRID)

    exact = result["exact_agreement"] * 100
    near = result["agreement_within_2s"] * 100
    fig.text(0.2, 0.94, "Detecting what the car is doing, in real time", fontsize=26, weight="bold", color=INK)
    fig.text(0.2, 0.875,
             f"On a drive the detector never saw: matches the hand labels {exact:.0f}% of the time, "
             f"and {near:.0f}% within 2 seconds",
             fontsize=17, color=MUTED)

    shown = [k for k in ("idle", "accel", "steady", "decel", "unscored") if k in set(reference) | set(detected)]
    fig.legend(handles=[Patch(facecolor=CATEGORIES[k][1], label=CATEGORIES[k][0]) for k in shown],
               loc="lower center", ncol=len(shown), frameon=False, fontsize=15, labelcolor=INK,
               bbox_to_anchor=(0.59, 0.0), handlelength=1.6, handleheight=1.1, columnspacing=2.2)

    out_dir = config.path("outputs", "plots")
    out_dir.mkdir(parents=True, exist_ok=True)
    for ext, dpi in (("pdf", None), ("png", 300)):
        fig.savefig(out_dir / f"poster_mode_detection.{ext}", dpi=dpi, facecolor=SURFACE)
    print(f"Saved outputs/plots/poster_mode_detection.pdf and .png ({exact:.1f}% exact, {near:.1f}% within 2 s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
