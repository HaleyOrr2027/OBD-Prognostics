"""Score detected operating modes against reference labels for a recording.

Reference labels are a CSV of segments: start_s, end_s, label, note
using the driver-level vocabulary idle / accel / decel / steady.

The detector's modes are collapsed onto that vocabulary before comparison:
    startup, cold_idle, hot_idle -> idle
    acceleration                 -> accel
    deceleration                 -> decel
    cruise, other                -> steady
("other" is moving at a steady speed below the cruise speed floor.)

Usage:
    python notebooks/score_modes.py data/carOBD/obdiidata/drive12.csv notebooks/labels/drive12_1480-1780_reference.csv
"""

import sys

import numpy as np
import pandas as pd

import mode_segmentation as ms

COLLAPSE = {
    "startup": "idle",
    "cold_idle": "idle",
    "hot_idle": "idle",
    "acceleration": "accel",
    "deceleration": "decel",
    "cruise": "steady",
    "other": "steady",
}
CLASSES = ["idle", "accel", "decel", "steady"]


def expand(labels: pd.DataFrame) -> pd.Series:
    """Turn labelled segments into one label per whole second."""
    rows = {}
    for _, seg in labels.iterrows():
        for s in range(int(seg.start_s), int(seg.end_s) + 1):
            rows[s] = seg.label
    return pd.Series(rows).sort_index()


def score(recording: str, label_file: str, tolerance_s: int = 2):
    df = ms.segment(recording)
    t_col = ms.resolve_column(df, "run_time")
    detected = df.set_index(df[t_col].round().astype(int))["mode"].map(COLLAPSE)
    detected = detected[~detected.index.duplicated()]

    truth = expand(pd.read_csv(label_file))
    pred = detected.reindex(truth.index)

    exact = (pred == truth).mean()

    # A sample also counts as correct if the detector's label matches the reference
    # within +/- tolerance seconds; this forgives transitions shifted by smoothing.
    near = []
    for s, lab in truth.items():
        window = detected.reindex(range(s - tolerance_s, s + tolerance_s + 1))
        near.append(lab in set(window.dropna()))
    tolerant = float(np.mean(near))

    confusion = pd.crosstab(
        truth.rename("reference"), pred.rename("detected")
    ).reindex(index=CLASSES, columns=CLASSES, fill_value=0)

    per_class = pd.DataFrame(
        {
            "seconds": confusion.sum(axis=1),
            "recall": np.diag(confusion) / confusion.sum(axis=1).replace(0, np.nan),
            "precision": np.diag(confusion) / confusion.sum(axis=0).replace(0, np.nan),
        }
    ).round(2)

    return exact, tolerant, confusion, per_class, truth, pred


if __name__ == "__main__":
    rec, lab = sys.argv[1], sys.argv[2]
    exact, tolerant, confusion, per_class, truth, pred = score(rec, lab)
    print(f"Seconds scored:          {len(truth)}")
    print(f"Exact agreement:         {exact:.1%}")
    print(f"Agreement within +/-2 s: {tolerant:.1%}")
    print("\nConfusion matrix (rows = reference, columns = detector), seconds:")
    print(confusion.to_string())
    print("\nPer class:")
    print(per_class.to_string())
