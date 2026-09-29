"""Operating-mode segmentation for OBD-II time series (carOBD format).

Replaces the idle-only filter in stable_idle_anomaly_detector.py. Instead of
discarding startup windows, every sample is labelled with one of six operating
modes, and windows are cut so each lies entirely inside a single mode.

Usage:
    df = load_recording("data/carOBD/obdiidata/drive1.csv")
    df = add_derivatives(df)
    df["mode"] = label_modes(df)
    windows = make_windows(df, source="drive1.csv")
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MODES = (
    "startup",
    "cold_idle",
    "hot_idle",
    "acceleration",
    "deceleration",
    "cruise",
    "other",
)

# Thresholds. Tune against labelled runs rather than trusting the defaults.
PARAMS = {
    "startup_seconds": 30.0,
    "cold_coolant_c": 70.0,
    "idle_speed_kph": 2.0,
    "idle_rpm_max": 1200.0,
    "accel_kph_per_s": 0.6,
    "decel_kph_per_s": -0.6,
    "closed_throttle_pct": 3.0,
    "cruise_speed_min_kph": 25.0,
    "resample_seconds": 1.0,
    "smooth_seconds": 4.0,
    "window_seconds": 5.0,
    "window_stride_seconds": 2.5,
    "min_samples_per_window": 4,
    "min_run_seconds": 3.0,
}

# Fuzzy lookup, most specific candidate first. Note two dataset quirks:
#   - ENGINE_RUN_TINE is misspelled in the source headers.
#   - Absolute THROTTLE never reaches 0 (floor around 15%), so relative
#     throttle position is the signal that actually indicates a closed pedal.
SIGNALS = {
    "run_time": ["engine_run_tin", "engine_run_tim", "run_tin", "run_tim"],
    "speed": ["vehicle_speed", "speed"],
    "rpm": ["engine_rpm", "rpm"],
    "coolant": ["coolant_temperature", "coolant_temp", "coolant"],
    "throttle": ["relative_throttle_position", "throttle_pos", "throttle"],
    "load": ["engine_load", "calculated_load", "load"],
}


def _normalise(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in str(name).strip().lower())


def resolve_column(df: pd.DataFrame, signal: str, required: bool = True):
    """Find the column holding a signal, tolerating header variation."""
    lookup = [(_normalise(c), c) for c in df.columns]
    for candidate in SIGNALS[signal]:
        for norm, original in lookup:
            if candidate in norm:
                return original
    if required:
        raise KeyError(
            f"Could not find a column for '{signal}'. Tried {SIGNALS[signal]}. "
            f"Available: {sorted(df.columns)}"
        )
    return None


def load_recording(path: str | Path) -> pd.DataFrame:
    """Read a carOBD CSV without the column shift the trailing comma causes.

    Every data row ends in a comma, so rows carry one more field than the
    header. Left to itself pandas promotes the first data column to the index
    and shifts every remaining name one position left, which silently puts fuel
    trim values under COOLANT_TEMPERATURE. index_col=False prevents that.
    """
    df = pd.read_csv(path, index_col=False)
    df.columns = [str(c).replace("()", "").strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    df = df.apply(pd.to_numeric, errors="coerce")
    return df.dropna(axis=1, how="all")


def resample_uniform(df: pd.DataFrame, period: float | None = None) -> pd.DataFrame:
    """Put the recording on a uniform time grid.

    Logging is roughly 2 Hz but timestamps repeat, so consecutive samples often
    share a time and a plain diff divides by zero. Duplicate timestamps are
    averaged and the result is reindexed onto an evenly spaced grid, which is
    what makes rate-of-change well defined.
    """
    period = period or PARAMS["resample_seconds"]
    time_col = resolve_column(df, "run_time")
    t = pd.to_numeric(df[time_col], errors="coerce")

    collapsed = df.drop(columns=[time_col]).groupby(t.values).mean(numeric_only=True)
    grid = np.arange(collapsed.index.min(), collapsed.index.max() + period, period)
    out = collapsed.reindex(collapsed.index.union(grid)).interpolate(
        method="index", limit_direction="both"
    ).reindex(grid)

    out.index.name = time_col
    return out.reset_index()


def add_derivatives(df: pd.DataFrame) -> pd.DataFrame:
    """Add smoothed rate-of-change columns for speed and RPM.

    Speed is reported in whole kph, so differentiating it raw produces a square
    wave that flickers between zero and several kph/s. A centred rolling mean
    over smooth_seconds turns that into a usable slope.
    """
    df = df.copy()
    t = pd.to_numeric(df[resolve_column(df, "run_time")], errors="coerce")
    period = float(np.median(np.diff(t.to_numpy(dtype=float))))
    span = max(int(round(PARAMS["smooth_seconds"] / period)), 3)

    for signal, out in (("speed", "speed_rate"), ("rpm", "rpm_rate")):
        col = resolve_column(df, signal, required=(signal == "speed"))
        if col is None:
            df[out] = np.nan
            continue
        smoothed = (
            pd.to_numeric(df[col], errors="coerce")
            .rolling(span, center=True, min_periods=1)
            .mean()
        )
        df[f"{signal}_smooth"] = smoothed
        df[out] = np.gradient(smoothed.to_numpy(dtype=float), period)

    return df


def label_modes(df: pd.DataFrame) -> pd.Series:
    """Assign an operating mode to every sample, in priority order."""
    run_time = pd.to_numeric(df[resolve_column(df, "run_time")], errors="coerce")
    speed = pd.to_numeric(df[resolve_column(df, "speed")], errors="coerce")
    rpm = pd.to_numeric(df[resolve_column(df, "rpm")], errors="coerce")
    coolant = pd.to_numeric(df[resolve_column(df, "coolant")], errors="coerce")

    throttle_col = resolve_column(df, "throttle", required=False)
    throttle = (
        pd.to_numeric(df[throttle_col], errors="coerce")
        if throttle_col is not None
        else pd.Series(np.nan, index=df.index)
    )

    speed_rate = df.get("speed_rate", pd.Series(0.0, index=df.index))

    running = rpm > 0  # engine-off samples are not an operating mode
    stopped = (speed <= PARAMS["idle_speed_kph"]) & (rpm <= PARAMS["idle_rpm_max"])
    cold = coolant < PARAMS["cold_coolant_c"]
    closed_throttle = throttle.isna() | (throttle <= PARAMS["closed_throttle_pct"])
    moving = speed > PARAMS["idle_speed_kph"]

    rules = [
        ("startup", (run_time < PARAMS["startup_seconds"]) & (rpm > 0)),
        ("cold_idle", stopped & cold),
        ("hot_idle", stopped & ~cold),
        (
            "deceleration",
            moving & (speed_rate <= PARAMS["decel_kph_per_s"]) & closed_throttle,
        ),
        ("acceleration", moving & (speed_rate >= PARAMS["accel_kph_per_s"])),
        (
            "cruise",
            (speed >= PARAMS["cruise_speed_min_kph"])
            & (speed_rate.abs() < PARAMS["accel_kph_per_s"]),
        ),
    ]

    mode = pd.Series("other", index=df.index, dtype=object)
    unassigned = running.fillna(False).copy()
    for name, condition in rules:
        hit = unassigned & condition.fillna(False)
        mode[hit] = name
        unassigned &= ~hit

    return mode


def _mode_runs(mode: pd.Series) -> pd.Series:
    return (mode != mode.shift()).cumsum()


def despeckle(df: pd.DataFrame, mode_col: str = "mode") -> pd.Series:
    """Absorb mode runs shorter than min_run_seconds into the previous mode.

    Without this, a single noisy sample splits a long cruise stretch into three
    runs and both fragments get dropped for being under one window long.
    """
    mode = df[mode_col].copy()
    t = pd.to_numeric(df[resolve_column(df, "run_time")], errors="coerce")
    limit = PARAMS["min_run_seconds"]

    for _ in range(3):  # repeat so neighbouring specks merge rather than ping-pong
        runs = _mode_runs(mode)
        changed = False
        for _, idx in mode.groupby(runs, sort=False).groups.items():
            idx = pd.Index(idx)
            span = t.loc[idx].max() - t.loc[idx].min()
            position = df.index.get_loc(idx[0])
            if span < limit and position > 0:
                mode.loc[idx] = mode.iloc[position - 1]
                changed = True
        if not changed:
            break

    return mode


def make_windows(df: pd.DataFrame, source: str = "") -> pd.DataFrame:
    """Cut the recording into overlapping windows that never cross a mode change."""
    if "mode" not in df.columns:
        raise KeyError("Call label_modes() and assign df['mode'] first.")

    time_col = resolve_column(df, "run_time")
    coolant_col = resolve_column(df, "coolant", required=False)
    t = pd.to_numeric(df[time_col], errors="coerce")
    feature_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns if c != time_col
    ]

    width = PARAMS["window_seconds"]
    stride = PARAMS["window_stride_seconds"]
    rows = []

    for _, run in df.groupby(_mode_runs(df["mode"]), sort=False):
        run_mode = run["mode"].iloc[0]
        if run_mode == "other":
            continue

        run_t = t.loc[run.index]
        start, stop = run_t.min(), run_t.max()
        if not np.isfinite(start) or stop - start < width:
            continue

        edge = start
        while edge + width <= stop:
            chunk = run[(run_t >= edge) & (run_t < edge + width)]
            edge += stride
            if len(chunk) < PARAMS["min_samples_per_window"]:
                continue

            row = {
                "source": source,
                "mode": run_mode,
                "t_start": float(chunk[time_col].iloc[0]),
                "n_samples": len(chunk),
                # Closed-loop fuelling only engages once warm, so O2 and fuel-trim
                # features mean different things either side of this flag.
                "warm": bool(
                    pd.to_numeric(chunk[coolant_col], errors="coerce").mean()
                    >= PARAMS["cold_coolant_c"]
                )
                if coolant_col is not None
                else True,
            }
            for col in feature_cols:
                values = pd.to_numeric(chunk[col], errors="coerce")
                row[f"{col}_mean"] = values.mean()
                row[f"{col}_std"] = values.std(ddof=0)
            rows.append(row)

    return pd.DataFrame(rows)


def mode_report(windows: pd.DataFrame) -> pd.DataFrame:
    """Window counts per mode, for checking whether a mode has enough data."""
    counts = (
        windows.groupby("mode")
        .agg(windows=("mode", "size"), recordings=("source", "nunique"))
        .reindex(list(MODES))
        .fillna(0)
        .astype(int)
    )
    counts["share"] = (counts["windows"] / max(counts["windows"].sum(), 1)).round(3)
    return counts


def segment(path: str | Path) -> pd.DataFrame:
    """Load, resample, differentiate, label and despeckle one recording."""
    df = load_recording(path)
    df = resample_uniform(df)
    df = add_derivatives(df)
    df["mode"] = label_modes(df)
    df["mode"] = despeckle(df)
    return df
