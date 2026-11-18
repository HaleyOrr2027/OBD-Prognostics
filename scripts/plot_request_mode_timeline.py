"""Plot driver request and detected vehicle mode on the same time axis.

Example:
    python scripts/plot_request_mode_timeline.py drive3 --start 600 --end 900
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABELED = ROOT / "data" / "labeled"
OUT = ROOT / "outputs" / "evaluation"

REQUEST_LEVELS = [
    "UNKNOWN_REQUEST",
    "NO_ACCELERATOR_REQUEST",
    "RELEASE_ACCELERATOR",
    "MAINTAIN_REQUEST",
    "ACCELERATE_REQUEST",
]
MODE_LEVELS = [
    "UNKNOWN_TRANSITION",
    "ENGINE_OFF",
    "STARTUP_WARMUP",
    "IDLE",
    "STRONG_DECEL",
    "COASTING_DECEL",
    "CRUISING",
    "ACCELERATING",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("session")
    parser.add_argument("--start", type=float, default=None)
    parser.add_argument("--end", type=float, default=None)
    args = parser.parse_args()

    path = LABELED / f"{args.session}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run training/02_label_modes.py first.")

    frame = pd.read_csv(path)
    frame = frame.drop_duplicates(subset=["ELAPSED_SEC"]).sort_values("ELAPSED_SEC")
    if args.start is not None:
        frame = frame[frame["ELAPSED_SEC"] >= args.start]
    if args.end is not None:
        frame = frame[frame["ELAPSED_SEC"] <= args.end]
    if frame.empty:
        raise ValueError("No samples in the requested time range.")

    request_map = {name: i for i, name in enumerate(REQUEST_LEVELS)}
    mode_map = {name: i for i, name in enumerate(MODE_LEVELS)}

    request_y = frame["DRIVER_REQUEST"].map(request_map)
    mode_y = frame["MOTION_STATE"].map(mode_map)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.step(frame["ELAPSED_SEC"], request_y, where="post", label="Driver request")
    mode_offset = len(REQUEST_LEVELS) + 1
    ax.step(frame["ELAPSED_SEC"], mode_y + mode_offset, where="post", label="Vehicle mode")

    request_ticks = list(range(len(REQUEST_LEVELS)))
    mode_ticks = [mode_offset + i for i in range(len(MODE_LEVELS))]
    ax.set_yticks(request_ticks + mode_ticks, REQUEST_LEVELS + MODE_LEVELS)
    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Detected state")
    title = f"{args.session}: driver request and vehicle mode"
    if args.start is not None or args.end is not None:
        title += f" ({args.start if args.start is not None else 'start'}–{args.end if args.end is not None else 'end'} s)"
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    ax.legend()
    fig.tight_layout()

    start_tag = "start" if args.start is None else str(args.start).replace(".", "p")
    end_tag = "end" if args.end is None else str(args.end).replace(".", "p")
    out = OUT / f"request_mode_timeline_{args.session}_{start_tag}_{end_tag}.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
