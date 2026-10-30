"""Steps 21 and 23: compose the context detector and compute confidence.

Priority: bad data or unknown engine -> UNKNOWN_TRANSITION; engine off ->
ENGINE_OFF; startup guard -> STARTUP_WARMUP; otherwise the motion state. Every
axis is kept as its own column rather than collapsed into one string.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config
from ..schemas import ROUTABLE_STATES, EngineState, MotionState, ThermalState
from .engine_state import detect_engine_state, rpm_speed_conflict
from .load_state import detect_load_state
from .motion_state import detect_motion_state_raw
from .persistence import apply_persistence
from .segments import assign_segments
from .thermal_state import detect_thermal_state, seconds_since_engine_start

ROUTABLE = {s.value for s in ROUTABLE_STATES}


def _compose(frame: pd.DataFrame, engine: pd.Series, thermal: pd.Series, motion: pd.Series, config: Config):
    state = motion.copy()
    reason = pd.Series("", index=frame.index, dtype=object)

    bad = ~frame["DATA_QUALITY_OK"].astype(bool)
    unknown_engine = engine == EngineState.UNKNOWN.value
    off = engine == EngineState.OFF.value
    startup = (thermal == ThermalState.STARTUP_WARMUP.value) & ~off

    state[startup] = MotionState.STARTUP_WARMUP.value
    reason[startup] += "STARTUP_GUARD;"
    state[off] = MotionState.ENGINE_OFF.value
    reason[off] += "ENGINE_OFF;"
    state[bad | unknown_engine] = MotionState.UNKNOWN_TRANSITION.value
    reason[bad] += "BAD_QUALITY;"
    conflict = rpm_speed_conflict(frame, config)
    reason[conflict] += "RPM_SPEED_CONFLICT;"
    reason[unknown_engine & ~conflict] += "ENGINE_UNKNOWN;"

    # Context only: a stationary running engine above the usual idle range is
    # still IDLE (when idle_rpm_max is null) but is marked so it can be reviewed.
    flag_above = config.get("modes", "motion_state").get("idle_rpm_flag_above")
    if flag_above is not None:
        high_idle = (state == MotionState.IDLE.value) & (frame["ENGINE_RPM"] > float(flag_above))
        reason[high_idle] += "IDLE_RPM_HIGH;"

    no_accel = frame["ACCELERATION_MPS2"].isna() & (state == MotionState.UNKNOWN_TRANSITION.value) & ~bad
    reason[no_accel] += "NO_ACCELERATION_YET;"
    return state, reason


def _confidence(frame: pd.DataFrame, raw: pd.Series, stable: pd.Series, reason: pd.Series, config: Config):
    p = config.get("modes", "motion_state")
    margin = float(config.get("modes", "confidence", "boundary_margin_mps2"))
    accel = frame["ACCELERATION_MPS2"].to_numpy(dtype=float)

    thresholds = np.array([p["accel_mps2"], p["decel_mps2"], p["strong_decel_mps2"]], dtype=float)
    distance = np.abs(accel[:, None] - thresholds[None, :]).min(axis=1)  # NaN where accel is NaN
    boundary = np.clip(0.5 + 0.5 * distance / margin, 0.5, 1.0)

    stopped = stable.to_numpy() == MotionState.IDLE.value
    boundary = np.where(stopped | ~np.isfinite(boundary), 1.0, boundary)

    in_transition = (raw != stable).to_numpy()
    conf = boundary * np.where(in_transition, 0.6, 1.0)
    conf = np.where(stable.isin(ROUTABLE).to_numpy(), conf, 0.0)

    reason = reason.copy()
    reason[(boundary < 1.0) & stable.isin(ROUTABLE).to_numpy()] += "NEAR_THRESHOLD;"
    reason[in_transition] += "PENDING_TRANSITION;"
    return pd.Series(np.round(conf, 3), index=frame.index), reason


def detect_modes(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Add the Section 2.4 mode-state columns to a derived-signal frame."""
    out = frame.copy()
    engine = detect_engine_state(out, config)
    out["SECONDS_SINCE_ENGINE_START"] = seconds_since_engine_start(out, engine)
    thermal = detect_thermal_state(out["SECONDS_SINCE_ENGINE_START"], config)
    motion = detect_motion_state_raw(out, engine, config)

    raw, reason = _compose(out, engine, thermal, motion, config)
    stable = apply_persistence(raw, out["ELAPSED_SEC"], out["TIME_BLOCK"], config)
    confidence, reason = _confidence(out, raw, stable, reason, config)

    out["ENGINE_STATE"] = engine
    out["THERMAL_STATE"] = thermal
    out["MOTION_STATE_RAW"] = raw
    out["MOTION_STATE"] = stable
    out["LOAD_STATE"] = detect_load_state(out, config)
    out["MODE_CONFIDENCE"] = confidence
    out["MODE_REASON"] = reason.str.rstrip(";")
    out["MODE_SEGMENT_ID"] = assign_segments(out)
    return out
