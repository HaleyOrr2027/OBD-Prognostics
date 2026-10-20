"""Step 06: common sample-source interface.

Downstream code depends on this interface, not on whether samples came from a
CSV replay or a live Bluetooth adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator

import pandas as pd


class SampleSource(ABC):
    session_id: str

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def __iter__(self) -> Iterator[dict[str, Any]]:
        """Yield one raw sample per acquisition cycle, in time order."""

    @abstractmethod
    def close(self) -> None: ...

    def to_frame(self) -> pd.DataFrame:
        """Batch helper for offline processing."""
        self.open()
        try:
            return pd.DataFrame(list(iter(self)))
        finally:
            self.close()

    def __enter__(self) -> "SampleSource":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
