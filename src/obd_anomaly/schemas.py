#
# Filename: schemas.py
# Description: Defines the data structures used in the OBD project
#

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


 
# Driving and engine states
 

# Possible driving modes
class MotionState(Enum):
    ENGINE_OFF = "ENGINE_OFF"
    STARTUP_WARMUP = "STARTUP_WARMUP"
    IDLE = "IDLE"
    ACCELERATING = "ACCELERATING"
    CRUISING = "CRUISING"
    COASTING_DECEL = "COASTING_DECEL"
    STRONG_DECEL = "STRONG_DECEL"
    UNKNOWN_TRANSITION = "UNKNOWN_TRANSITION"


# Possible engine states
class EngineState(Enum):
    OFF = "OFF"
    RUNNING = "RUNNING"
    UNKNOWN = "UNKNOWN"


# Possible engine warm-up states
class ThermalState(Enum):
    STARTUP_WARMUP = "STARTUP_WARMUP"
    WARM_OR_UNKNOWN = "WARM_OR_UNKNOWN"

# Possible engine load states
class LoadState(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


# Modes that can be sent to an anomaly model
ROUTABLE_STATES = {
    MotionState.IDLE,
    MotionState.ACCELERATING,
    MotionState.CRUISING,
    MotionState.COASTING_DECEL,
    MotionState.STRONG_DECEL
}


# Collection information, not vehicle sensor readings
RAW_METADATA = {
    "SESSION_ID",
    "VEHICLE_ID",
    "SOURCE",
    "CONNECTION_OK",
    "TIMESTAMP_UTC",
    "MONOTONIC_SEC",
    "ELAPSED_SEC",
    "TIME_BLOCK",
    "TIME_FLAGS"
}


 
# Raw OBD data
 

@dataclass
class OBDSample:
    SESSION_ID: str
    TIMESTAMP_UTC: datetime
    MONOTONIC_SEC: float
    VEHICLE_ID: str
    SOURCE: str
    CONNECTION_OK: bool

    ENGINE_RPM: float | None = None
    VEHICLE_SPEED: float | None = None
    ENGINE_LOAD: float | None = None
    THROTTLE_POSITION: float | None = None
    COOLANT_TEMPERATURE: float | None = None
    MAF: float | None = None
    INTAKE_PRESSURE: float | None = None
    INTAKE_TEMPERATURE: float | None = None
    SHORT_FUEL_TRIM_1: float | None = None
    LONG_FUEL_TRIM_1: float | None = None
    ENGINE_RUN_TIME: float | None = None


 
# Cleaned OBD data
 

@dataclass
class NormalizedSample:
    RAW_SAMPLE: OBDSample

    SAMPLE_DT_SEC: float | None = None
    PID_VALIDITY: dict = field(default_factory=dict)
    PID_AGE_SEC: dict = field(default_factory=dict)
    DATA_QUALITY_OK: bool = False
    QUALITY_FLAGS: list = field(default_factory=list)

    SPEED_SMOOTH_KMH: float | None = None
    ACCELERATION_MPS2: float | None = None
    RPM_DELTA_PER_SEC: float | None = None
    LOAD_DELTA_PER_SEC: float | None = None
    THROTTLE_DELTA_PER_SEC: float | None = None
    SECONDS_SINCE_ENGINE_START: float | None = None


 
# Current driving mode
 

@dataclass
class ModeState:
    ENGINE_STATE: str
    THERMAL_STATE: str
    MOTION_STATE_RAW: str
    MOTION_STATE: str
    LOAD_STATE: str
    MODE_CONFIDENCE: float

    MODE_REASON: list = field(default_factory=list)
    MODE_SEGMENT_ID: str | None = None


 
# Features from a window of data
 

@dataclass
class FeatureWindow:
    WINDOW_ID: str
    SESSION_ID: str
    MODE_SEGMENT_ID: str
    MOTION_STATE: str
    WINDOW_START_SEC: float
    WINDOW_END_SEC: float
    DURATION_SEC: float
    SAMPLE_COUNT: int
    MIN_MODE_CONFIDENCE: float

    QUALITY_FLAGS: list = field(default_factory=list)
    FEATURES: dict = field(default_factory=dict)


 
# Anomaly detection result
 

@dataclass
class AnomalyResult:
    RESULT_TIME_UTC: datetime
    WINDOW_ID: str
    MOTION_STATE: str
    MODE_CONFIDENCE: float
    STATUS: str

    ANOMALY_SCORE: float | None = None
    THRESHOLD: float | None = None
    MODEL_VERSION: str | None = None
    TOP_CONTRIBUTORS: list = field(default_factory=list)
    REASON: str | None = None
