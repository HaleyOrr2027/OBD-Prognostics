"""Offline pipeline: raw session -> labeled samples (plan.md Step 25 chain)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .adapters.csv_source import CSVSource
from .config import Config, load_config
from .modes.detector import detect_modes
from .preprocessing.derived_signals import add_derived_signals
from .preprocessing.normalize import normalize_columns
from .preprocessing.quality import add_quality_flags
from .preprocessing.timebase import build_timebase


def label_frame(raw: pd.DataFrame, config: Config) -> pd.DataFrame:
    frame = normalize_columns(raw, config)
    frame = build_timebase(frame, config)
    frame = add_quality_flags(frame, config)
    frame = add_derived_signals(frame, config)
    return detect_modes(frame, config)


def label_session(path: str | Path, config: Config | None = None, vehicle_id: str = "unknown") -> pd.DataFrame:
    """Label one raw CSV. vehicle_id defaults to unknown; the label script uses the raw subfolder name."""
    config = config or load_config()
    return label_frame(CSVSource(path, vehicle_id=vehicle_id).to_frame(), config)
