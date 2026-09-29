"""Validate mode detection against a real drive by plotting modes over the signals."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
from pathlib import Path

import mode_segmentation as ms

MODE_COLORS = {
    "startup": "#2a78d6",
    "cold_idle": "#eb6834",
    "hot_idle": "#1baf7a",
    "acceleration": "#eda100",
    "deceleration": "#e87ba4",
    "cruise": "#008300",
    "other": "#b8b7b0",
}
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e3e2dd"
SURFACE = "#fcfcfb"


def ribbon(ax, t, mode, label_min_span=45):
    """Draw modes as a solid categorical strip, with labels on wide segments."""
    runs = (mode != mode.shift()).cumsum()
    for _, idx in mode.groupby(runs, sort=False).groups.items():
        idx = list(idx)
        x0, x1 = t.loc[idx[0]], t.loc[idx[-1]]
        name = mode.loc[idx[0]]
        ax.axvspan(x0, x1, color=MODE_COLORS[name], linewidth=0)
        if x1 - x0 >= label_min_span:
            ax.text(
                (x0 + x1) / 2, 0.5, name.replace("_", " "),
                ha="center", va="center", fontsize=7, color="#ffffff", weight="bold",
            )
    ax.set_yticks([])
    ax.set_ylabel("mode", fontsize=9, color=MUTED, rotation=0, ha="right", va="center")


def trace(ax, t, y, label, color=INK):
    ax.plot(t, y, linewidth=1.6, color=color, solid_capstyle="round")
    ax.set_ylabel(label, fontsize=9, color=MUTED)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)


def figure(df, window=None, title=""):
    t_col = ms.resolve_column(df, "run_time")
    sp = ms.resolve_column(df, "speed")
    rpm = ms.resolve_column(df, "rpm")
    th = ms.resolve_column(df, "throttle")
    co = ms.resolve_column(df, "coolant")

    d = df if window is None else df[(df[t_col] >= window[0]) & (df[t_col] <= window[1])]
    t = d[t_col]

    fig, axes = plt.subplots(
        6, 1, figsize=(13, 9), sharex=True,
        gridspec_kw={"height_ratios": [0.5, 1, 1, 1, 1, 1], "hspace": 0.18},
    )
    fig.patch.set_facecolor(SURFACE)
    for ax in axes:
        ax.set_facecolor(SURFACE)

    ribbon(axes[0], t, d["mode"], label_min_span=(t.max() - t.min()) / 22)
    for side in ("top", "right", "left", "bottom"):
        axes[0].spines[side].set_visible(False)

    trace(axes[1], t, d[sp], "speed\nkph")
    trace(axes[2], t, d["speed_rate"], "speed rate\nkph/s")
    axes[2].axhline(ms.PARAMS["accel_kph_per_s"], color="#eda100", linewidth=1, linestyle="--")
    axes[2].axhline(ms.PARAMS["decel_kph_per_s"], color="#e87ba4", linewidth=1, linestyle="--")
    trace(axes[3], t, d[rpm], "RPM")
    trace(axes[4], t, d[th], "rel throttle\n%")
    axes[4].axhline(ms.PARAMS["closed_throttle_pct"], color=MUTED, linewidth=1, linestyle="--")
    trace(axes[5], t, d[co], "coolant\n°C")
    axes[5].axhline(ms.PARAMS["cold_coolant_c"], color=MUTED, linewidth=1, linestyle="--")
    axes[5].set_xlabel("engine run time (s)", fontsize=9, color=MUTED)

    present = [m for m in ms.MODES if m in set(d["mode"])]
    fig.legend(
        handles=[Patch(facecolor=MODE_COLORS[m], label=m.replace("_", " ")) for m in present],
        loc="upper center", bbox_to_anchor=(0.5, 0.045), ncol=len(present),
        frameon=False, fontsize=9, labelcolor=MUTED,
    )
    fig.suptitle(title, fontsize=13, color=INK, weight="bold", x=0.125, ha="left", y=0.96)
    fig.subplots_adjust(top=0.92, bottom=0.10, left=0.09, right=0.98)
    return fig


DATA = Path(__file__).resolve().parents[1] / "data" / "carOBD" / "obdiidata"


if __name__ == "__main__":
    import sys

    recording = sys.argv[1] if len(sys.argv) > 1 else DATA / "drive12.csv"
    df = ms.segment(recording)
    t_col = ms.resolve_column(df, "run_time")
    OUT = Path(__file__).resolve().parent / "figures"
    OUT.mkdir(exist_ok=True)

    figure(df, title="drive12 — detected operating modes over the full recording").savefig(
        OUT / "mode_validation_full.png", dpi=150, facecolor=SURFACE
    )

    # A window in the middle, where stop-and-go makes the transitions legible.
    mid = df[t_col].max() * 0.45
    figure(df, window=(mid, mid + 300),
           title="drive12 — 5-minute detail, mode transitions").savefig(
        OUT / "mode_validation_detail.png", dpi=150, facecolor=SURFACE
    )
    print("wrote mode_validation_full.png, mode_validation_detail.png")
