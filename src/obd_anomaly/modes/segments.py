"""Step 24: stable mode segments.

A new segment starts whenever the stable motion state changes or a time gap
opens. Segments never join across gaps or across sessions.
"""

from __future__ import annotations

import pandas as pd


def assign_segments(frame: pd.DataFrame) -> pd.Series:
    session = frame["SESSION_ID"].astype(str)
    change = (
        (frame["MOTION_STATE"] != frame["MOTION_STATE"].shift())
        | (frame["TIME_BLOCK"] != frame["TIME_BLOCK"].shift())
        | (session != session.shift())
    )
    number = change.cumsum()
    return session + "-" + number.map("{:04d}".format)


def segment_table(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby("MODE_SEGMENT_ID", sort=False)
    table = grouped.agg(
        SESSION_ID=("SESSION_ID", "first"),
        MOTION_STATE=("MOTION_STATE", "first"),
        START_SEC=("ELAPSED_SEC", "min"),
        END_SEC=("ELAPSED_SEC", "max"),
        SAMPLE_COUNT=("ELAPSED_SEC", "size"),
        MEAN_CONFIDENCE=("MODE_CONFIDENCE", "mean"),
    ).reset_index()
    table["DURATION_SEC"] = table["END_SEC"] - table["START_SEC"]
    return table
