"""Step 06: CSV replay source.

Raw values are preserved; renaming and units happen in preprocessing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from .base import SampleSource


def read_raw_csv(path: str | Path) -> pd.DataFrame:
    """Read a raw OBD CSV without silently shifting its columns.

    carOBD rows end with a trailing comma, so each row carries one more field
    than the header. By default pandas then promotes the first column to the
    index and shifts every header one place left, which puts fuel-trim values
    under COOLANT_TEMPERATURE without any error. index_col=False prevents that.
    """
    frame = pd.read_csv(path, index_col=False, skipinitialspace=True)
    return frame.loc[:, ~frame.columns.astype(str).str.match(r"^Unnamed")]


class CSVSource(SampleSource):
    def __init__(self, path: str | Path, session_id: str | None = None, vehicle_id: str = "unknown"):
        self.path = Path(path)
        self.session_id = session_id or self.path.stem
        self.vehicle_id = vehicle_id
        self._frame: pd.DataFrame | None = None

    def open(self) -> None:
        self._frame = read_raw_csv(self.path)

    def close(self) -> None:
        self._frame = None

    def __iter__(self) -> Iterator[dict[str, Any]]:
        if self._frame is None:
            raise RuntimeError("CSVSource.open() must be called before iterating")
        for record in self._frame.to_dict("records"):
            yield {
                "SESSION_ID": self.session_id,
                "VEHICLE_ID": self.vehicle_id,
                "SOURCE": "csv",
                "CONNECTION_OK": True,
                **record,
            }

    def to_frame(self) -> pd.DataFrame:
        frame = read_raw_csv(self.path)
        frame.insert(0, "CONNECTION_OK", True)
        frame.insert(0, "SOURCE", "csv")
        frame.insert(0, "VEHICLE_ID", self.vehicle_id)
        frame.insert(0, "SESSION_ID", self.session_id)
        return frame
