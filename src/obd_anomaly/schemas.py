"""Step 02: data contracts.

Partial: defines the column vocabulary and mode-state values from plan.md
Sections 2.1-2.4, which the mode detector produces. Feature-window and
anomaly-result contracts (2.5, 2.6) are left for Steps 33+.

Batch processing uses pandas DataFrames whose columns follow these names.
"""

from __future__ import annotations

from enum import Enum


class EngineState(str, Enum):
    OFF = "OFF"
    RUNNING = "RUNNING"
    UNKNOWN = "UNKNOWN"


class ThermalState(str, Enum):
    STARTUP_WARMUP = "STARTUP_WARMUP"
    WARM_OR_UNKNOWN = "WARM_OR_UNKNOWN"


class MotionState(str, Enum):
    ENGINE_OFF = "ENGINE_OFF"
    STARTUP_WARMUP = "STARTUP_WARMUP"
    IDLE = "IDLE"
    ACCELERATING = "ACCELERATING"
    CRUISING = "CRUISING"
    COASTING_DECEL = "COASTING_DECEL"
    STRONG_DECEL = "STRONG_DECEL"
    UNKNOWN_TRANSITION = "UNKNOWN_TRANSITION"


class LoadState(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


# Motion states a per-mode anomaly model may score. Everything else abstains.
ROUTABLE_STATES = (
    MotionState.IDLE,
    MotionState.ACCELERATING,
    MotionState.CRUISING,
    MotionState.COASTING_DECEL,
    MotionState.STRONG_DECEL,
)

# Section 2.1 metadata.
RAW_METADATA = ("SESSION_ID", "TIMESTAMP_UTC", "MONOTONIC_SEC", "VEHICLE_ID", "SOURCE", "CONNECTION_OK")

# Section 2.2 additions.
NORMALIZED_COLUMNS = ("ELAPSED_SEC", "SAMPLE_DT_SEC", "DATA_QUALITY_OK", "QUALITY_FLAGS")

# Section 2.3 additions.
DERIVED_COLUMNS = (
    "SPEED_SMOOTH_KMH",
    "ACCELERATION_MPS2",
    "RPM_DELTA_PER_SEC",
    "LOAD_DELTA_PER_SEC",
    "THROTTLE_DELTA_PER_SEC",
    "SECONDS_SINCE_ENGINE_START",
)

# Section 2.4 mode-state contract.
MODE_COLUMNS = (
    "ENGINE_STATE",
    "THERMAL_STATE",
    "MOTION_STATE_RAW",
    "MOTION_STATE",
    "LOAD_STATE",
    "MODE_CONFIDENCE",
    "MODE_REASON",
    "MODE_SEGMENT_ID",
)
