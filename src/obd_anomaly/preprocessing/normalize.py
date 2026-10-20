"""Steps 07-08: canonical column names and units.

Step 08 (unit conversion) is a pass-through for now: carOBD already reports
km/h, degrees C and kPa, which are the canonical units in config/pids.yaml.
"""

from __future__ import annotations

import re

import pandas as pd

from ..config import Config
from ..schemas import RAW_METADATA


class ColumnCollisionError(ValueError):
    pass


def clean_header(name: str) -> str:
    """Lowercase, drop empty unit brackets, and collapse punctuation to underscores."""
    text = str(name).replace("()", "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def alias_map(config: Config) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical, spec in config.pids["pids"].items():
        for alias in [canonical.lower(), *spec.get("aliases", [])]:
            key = clean_header(alias)
            if key in mapping and mapping[key] != canonical:
                raise ColumnCollisionError(
                    f"Alias '{alias}' maps to both {mapping[key]} and {canonical} in pids.yaml"
                )
            mapping[key] = canonical
    return mapping


def normalize_columns(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Rename known PIDs to canonical names; keep unknown columns under RAW_*.

    Unknown columns pass through with a RAW_ prefix so they are visible but can
    never be picked up as model features by accident.
    """
    mapping = alias_map(config)
    renamed: dict[str, str] = {}
    claimed: dict[str, str] = {}

    for column in frame.columns:
        if column in RAW_METADATA:
            continue
        canonical = mapping.get(clean_header(column))
        if canonical is None:
            renamed[column] = f"RAW_{clean_header(column).upper()}"
            continue
        if canonical in claimed:
            raise ColumnCollisionError(
                f"Columns '{claimed[canonical]}' and '{column}' both map to {canonical}"
            )
        claimed[canonical] = column
        renamed[column] = canonical

    out = frame.rename(columns=renamed)
    for canonical in config.pids["pids"]:
        if canonical in out.columns:
            out[canonical] = pd.to_numeric(out[canonical], errors="coerce")
        else:
            out[canonical] = float("nan")
    return out
