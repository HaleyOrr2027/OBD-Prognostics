# Description: Tests for the OBD data classes

from datetime import datetime, timezone

from obd_anomaly.schemas import (
    OBDSample,
    NormalizedSample,
    ModeState,
    FeatureWindow,
    AnomalyResult
)


def make_sample():
    return OBDSample(
        SESSION_ID="drive_001",
        TIMESTAMP_UTC=datetime.now(timezone.utc),
        MONOTONIC_SEC=10.0,
        VEHICLE_ID="car_001",
        SOURCE="csv",
        CONNECTION_OK=True,
        ENGINE_RPM=850.0,
        VEHICLE_SPEED=0.0
    )


def test_obd_sample():
    sample = make_sample()

    assert sample.ENGINE_RPM == 850.0
    assert sample.VEHICLE_SPEED == 0.0
    assert sample.ENGINE_LOAD is None


def test_normalized_sample():
    sample = make_sample()
    normalized = NormalizedSample(RAW_SAMPLE=sample)

    normalized.PID_VALIDITY["ENGINE_RPM"] = True
    normalized.PID_VALIDITY["VEHICLE_SPEED"] = True
    normalized.SAMPLE_DT_SEC = 0.5

    assert normalized.RAW_SAMPLE == sample
    assert normalized.PID_VALIDITY["ENGINE_RPM"] == True
    assert normalized.SAMPLE_DT_SEC == 0.5

    another = NormalizedSample(RAW_SAMPLE=sample)
    assert another.PID_VALIDITY == {}


def test_mode_state():
    mode = ModeState(
        ENGINE_STATE="RUNNING",
        THERMAL_STATE="WARM_OR_UNKNOWN",
        MOTION_STATE_RAW="IDLE",
        MOTION_STATE="IDLE",
        LOAD_STATE="LOW",
        MODE_CONFIDENCE=0.95
    )

    assert mode.ENGINE_STATE == "RUNNING"
    assert mode.MOTION_STATE == "IDLE"
    assert mode.MODE_CONFIDENCE == 0.95


def test_feature_window():
    window = FeatureWindow(
        WINDOW_ID="window_001",
        SESSION_ID="drive_001",
        MODE_SEGMENT_ID="segment_001",
        MOTION_STATE="IDLE",
        WINDOW_START_SEC=10.0,
        WINDOW_END_SEC=20.0,
        DURATION_SEC=10.0,
        SAMPLE_COUNT=20,
        MIN_MODE_CONFIDENCE=0.9
    )

    window.FEATURES["RPM_MEAN"] = 850.0

    assert window.SAMPLE_COUNT == 20
    assert window.FEATURES["RPM_MEAN"] == 850.0


def test_anomaly_result():
    result = AnomalyResult(
        RESULT_TIME_UTC=datetime.now(timezone.utc),
        WINDOW_ID="window_001",
        MOTION_STATE="IDLE",
        MODE_CONFIDENCE=0.95,
        STATUS="NORMAL"
    )

    assert result.STATUS == "NORMAL"
    assert result.ANOMALY_SCORE is None
    assert result.TOP_CONTRIBUTORS == []
