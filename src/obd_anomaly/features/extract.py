"""Step 34: feature extraction for one window.

The same function serves training (training/04_build_windows.py) and, later,
the live Pi, so both produce identical feature names in identical order.

Rows that share a timestamp are averaged first. carOBD logs about two rows per
timestamp, and without this a duplicated reading would count twice in the
mean, the spread and the slope.

Null policy:
  - required signal with no reading in the window -> window rejected
    (MISSING_REQUIRED), because a model cannot score it
  - optional signal with no reading -> its features are NaN and the window is
    flagged MISSING_<SIGNAL>; nothing is imputed
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..config import Config


class MissingRequiredSignal(ValueError):
    pass


def schema(config: Config) -> dict:
    return config.get("models", "feature_schema")


def feature_names(config: Config) -> list[str]:
    """Exact feature column names, in order, before any data is seen."""
    s = schema(config)
    names = []
    for signal in s["signals"]["required"] + s["signals"].get("optional", []):
        names += [f"{signal}__{stat}" for stat in s["stats"]]
    for signal, stats in s.get("context", {}).items():
        names += [f"{signal}__{stat}" for stat in stats]
    return names


def _stats(t: np.ndarray, v: np.ndarray, wanted: list[str]) -> dict[str, float]:
    ok = np.isfinite(v)
    t, v = t[ok], v[ok]
    out = {}
    for stat in wanted:
        if len(v) == 0:
            out[stat] = math.nan
        elif stat == "mean":
            out[stat] = float(v.mean())
        elif stat == "std":
            out[stat] = float(v.std(ddof=0))
        elif stat == "min":
            out[stat] = float(v.min())
        elif stat == "max":
            out[stat] = float(v.max())
        elif stat == "delta":
            out[stat] = float(v[-1] - v[0])
        elif stat == "slope":
            if len(v) < 2 or np.ptp(t) == 0:
                out[stat] = math.nan
            else:
                tc = t - t.mean()
                out[stat] = float((tc * (v - v.mean())).sum() / (tc * tc).sum())
        else:
            raise ValueError(f"Unknown statistic '{stat}' in config/models.yaml")
    return out


def extract_features(samples: pd.DataFrame, config: Config) -> tuple[dict[str, float], list[str]]:
    """Feature values for one window, plus quality flags.

    `samples` is the window's rows from a labeled session (needs ELAPSED_SEC
    and the configured signal columns). Raises MissingRequiredSignal if a
    required signal has no reading.
    """
    s = schema(config)
    required = s["signals"]["required"]
    optional = s["signals"].get("optional", [])
    context = s.get("context", {})
    columns = required + optional + list(context)

    present = [c for c in columns if c in samples.columns]
    per_time = (
        samples[["ELAPSED_SEC"] + present]
        .apply(pd.to_numeric, errors="coerce")
        .groupby("ELAPSED_SEC", sort=True)
        .mean()
    )
    t = per_time.index.to_numpy(dtype=float)

    def values(signal):
        if signal not in per_time:
            return np.full(len(t), np.nan)
        return per_time[signal].to_numpy(dtype=float)

    missing_required = [sig for sig in required if not np.isfinite(values(sig)).any()]
    if missing_required:
        raise MissingRequiredSignal(", ".join(missing_required))

    features: dict[str, float] = {}
    flags: list[str] = []
    for signal in required + optional:
        v = values(signal)
        if not np.isfinite(v).any():
            flags.append(f"MISSING_{signal}")
        for stat, value in _stats(t, v, s["stats"]).items():
            features[f"{signal}__{stat}"] = value
    for signal, stats in context.items():
        for stat, value in _stats(t, values(signal), stats).items():
            features[f"{signal}__{stat}"] = value

    ordered = {name: features[name] for name in feature_names(config)}
    return ordered, flags
