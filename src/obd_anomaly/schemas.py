
#
# Filename: schemas.py
# Description: Defines the data structures used in the OBD project
#

from dataclasses import dataclass, field
from datetime import datetime


# Raw OBD data
@dataclass
class OBDSample:
    SESSION_ID: str          # Identifies which driving/collection session the reading came from
    TIMESTAMP_UTC: datetime  # Actual date and time the reading was collected
    MONOTONIC_SEC: float     # Time measured using a steadily increasing clock
    VEHICLE_ID: str          # Identifies the vehicle without needing personal information
    SOURCE: str              # Whether the reading came from a CSV or Bluetooth adapter
    CONNECTION_OK: bool      # Whether the adapter connection is working
    ENGINE_RPM: float | None = None            # How fast the engine is rotating
    VEHICLE_SPEED: float | None = None         # How fast the car is moving
    ENGINE_LOAD: float | None = None           # Relative engine demand
    THROTTLE_POSITION: float | None = None     #Throttle opening
    COOLANT_TEMPERATURE: float | None = None    # Engine coolant temperature
    MAF: float | None = None                    # Mass airflow entering the engine
    INTAKE_PRESSURE: float | None = None        # Intake manifold pressure
    INTAKE_TEMPERATURE: float | None = None     # Air temperature entering the engine
    SHORT_FUEL_TRIM_1: float | None = None      # Short-term fuel mixture correction
    LONG_FUEL_TRIM_1: float | None = None       # Long-term fuel mixture correction
    ENGINE_RUN_TIME: float | None = None        # Time since the engine started


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
