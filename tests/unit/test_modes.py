import numpy as np
import pandas as pd

from obd_anomaly.modes.persistence import apply_persistence
from obd_anomaly.pipeline import label_frame


def states(frame):
    return frame["MOTION_STATE"].tolist()


# Step 15
def test_disconnect_is_unknown_not_off(config, drive):
    raw = drive([0.0] * 5, rpm=np.zeros(5))
    raw.loc[2, "CONNECTION_OK"] = False
    out = label_frame(raw, config)
    assert out["ENGINE_STATE"].tolist()[2] == "UNKNOWN"
    assert out["ENGINE_STATE"].tolist()[0] == "OFF"


# Step 18
def test_engine_off_at_zero_speed_is_not_idle(config, drive):
    out = label_frame(drive([0.0] * 5, rpm=np.zeros(5)), config)
    assert set(states(out)) == {"ENGINE_OFF"}


def test_running_at_zero_speed_is_idle(config, drive):
    out = label_frame(drive([0.0] * 10, rpm=np.full(10, 750.0)), config)
    assert states(out)[-1] == "IDLE"


# Steps 16-17
def test_startup_guard_after_engine_start(config, drive):
    rpm = np.r_[np.zeros(5), np.full(60, 800.0)]
    raw = drive([0.0] * 65, rpm=rpm)
    raw["ENGINE_RUN_TIME"] = np.arange(65, dtype=float)
    out = label_frame(raw, config)
    assert states(out)[6] == "STARTUP_WARMUP"
    assert states(out)[-1] == "IDLE"


# Step 19
def test_motion_states_on_synthetic_trajectory(config, drive):
    speeds = np.r_[np.full(10, 40.0), np.linspace(40, 76, 10), np.full(10, 76.0), np.linspace(76, 40, 10), np.full(5, 40.0)]
    out = label_frame(drive(speeds), config)
    s = states(out)
    assert s[8] == "CRUISING"
    assert s[16] == "ACCELERATING"
    assert s[28] == "CRUISING"
    assert s[36] in ("COASTING_DECEL", "STRONG_DECEL")


def test_hard_stop_is_strong_decel(config, drive):
    speeds = np.r_[np.full(10, 50.0), np.linspace(50, 0, 6), np.zeros(5)]
    out = label_frame(drive(speeds), config)
    assert "STRONG_DECEL" in states(out)[10:16]


# Step 22
def _persist(raw_states, dwell, config):
    config.modes["persistence"]["dwell_sec"] = dwell
    raw = pd.Series(raw_states)
    t = pd.Series(np.arange(len(raw_states), dtype=float))
    return apply_persistence(raw, t, pd.Series(0, index=raw.index), config).tolist()


def test_short_spike_does_not_switch_with_dwell(config):
    out = _persist(["CRUISING"] * 5 + ["ACCELERATING"] + ["CRUISING"] * 5, dwell=2.0, config=config)
    assert set(out) == {"CRUISING"}


def test_sustained_change_switches_after_dwell(config):
    out = _persist(["CRUISING"] * 3 + ["ACCELERATING"] * 5, dwell=2.0, config=config)
    assert out[4] == "CRUISING" and out[5] == "ACCELERATING"


def test_decel_wobble_shares_one_timer(config):
    wobble = ["COASTING_DECEL", "STRONG_DECEL"] * 3
    out = _persist(["CRUISING"] * 3 + wobble, dwell=2.0, config=config)
    assert out[-1] in ("COASTING_DECEL", "STRONG_DECEL")


def test_engine_off_switches_immediately(config):
    out = _persist(["CRUISING"] * 3 + ["ENGINE_OFF"], dwell=5.0, config=config)
    assert out[-1] == "ENGINE_OFF"


# Steps 23-24
def test_unroutable_states_have_zero_confidence(config, drive):
    out = label_frame(drive([0.0] * 5, rpm=np.zeros(5)), config)
    assert (out["MODE_CONFIDENCE"] == 0).all()


def test_segments_break_on_time_gap(config, drive):
    raw = drive([50.0] * 10)
    raw["ENGINE_RUN_TIME"] = np.r_[np.arange(5.0), np.arange(5.0) + 100]
    out = label_frame(raw, config)
    assert out["MODE_SEGMENT_ID"].iloc[4] != out["MODE_SEGMENT_ID"].iloc[5]


# Step 25 contract
def test_label_frame_keeps_every_row(config, drive):
    raw = drive(np.linspace(0, 60, 40))
    assert len(label_frame(raw, config)) == len(raw)
