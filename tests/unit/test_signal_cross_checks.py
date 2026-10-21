"""Tests for the RPM cross-checks Haley proposed on Oct 21.

1. IDLE should mean "stationary with the engine running", not "stationary with
   RPM in the expected idle range", so the IDLE model sees high-RPM stops.
2. RPM saying the engine is off while speed says the car is moving is a
   conflict: engine UNKNOWN with reason RPM_SPEED_CONFLICT, not ENGINE_OFF.

Each test holds speed fixed and changes only RPM, or the reverse.
"""

import copy

import numpy as np
import pytest

from obd_anomaly.pipeline import label_frame


def old_rules(config):
    """The rules before Oct 21: IDLE capped at 1300 RPM, no RPM/speed cross-check."""
    old = copy.deepcopy(config)
    old.modes["motion_state"]["idle_rpm_max"] = 1300.0
    old.modes["engine_state"]["rpm_speed_conflict_check"] = False
    old.modes["motion_state"]["idle_requires_raw_stop"] = False
    return old


def stationary(drive, rpm, seconds=60):
    # Run time well past the 30 s startup guard so only the RPM rule is tested.
    raw = drive([0.0] * seconds, rpm=np.full(seconds, float(rpm)))
    raw["ENGINE_RUN_TIME"] = 300.0 + np.arange(seconds, dtype=float)
    return raw


@pytest.mark.parametrize("rpm", [750, 1300, 1500, 3000])
def test_stationary_running_engine_is_idle_at_any_rpm(config, drive, rpm):
    out = label_frame(stationary(drive, rpm), config)
    assert out["MOTION_STATE"].iloc[-1] == "IDLE"


@pytest.mark.parametrize("rpm, expected", [(750, "IDLE"), (1300, "IDLE"), (1500, "UNKNOWN_TRANSITION"), (3000, "UNKNOWN_TRANSITION")])
def test_old_rule_dropped_high_rpm_stops(config, drive, rpm, expected):
    out = label_frame(stationary(drive, rpm), old_rules(config))
    assert out["MOTION_STATE"].iloc[-1] == expected


def test_high_rpm_idle_is_flagged_not_hidden(config, drive):
    out = label_frame(stationary(drive, 3000), config)
    assert "IDLE_RPM_HIGH" in out["MODE_REASON"].iloc[-1]
    assert "IDLE_RPM_HIGH" not in label_frame(stationary(drive, 750), config)["MODE_REASON"].iloc[-1]


def test_moving_with_engine_off_rpm_is_a_conflict(config, drive):
    raw = drive([50.0] * 20, rpm=np.full(20, 100.0))
    out = label_frame(raw, config)
    assert (out["ENGINE_STATE"] == "UNKNOWN").all()
    assert (out["MOTION_STATE"] == "UNKNOWN_TRANSITION").all()
    assert out["MODE_REASON"].str.contains("RPM_SPEED_CONFLICT").all()


def test_old_rule_called_moving_low_rpm_engine_off(config, drive):
    raw = drive([50.0] * 20, rpm=np.full(20, 100.0))
    out = label_frame(raw, old_rules(config))
    assert (out["MOTION_STATE"] == "ENGINE_OFF").all()


def test_stall_while_rolling_then_stopped(config, drive):
    """RPM drops to 0 while still rolling: conflict until stopped, then ENGINE_OFF."""
    speeds = np.r_[np.full(10, 40.0), np.linspace(40, 0, 10), np.zeros(5)]
    rpm = np.r_[np.full(10, 1500.0), np.zeros(15)]
    out = label_frame(drive(speeds, rpm=rpm), config)
    rolling_after_stall = out.iloc[10:15]
    assert (rolling_after_stall["ENGINE_STATE"] == "UNKNOWN").all()
    assert out["MOTION_STATE"].iloc[-1] == "ENGINE_OFF"


def test_rpm_glitch_does_not_restart_startup_guard(config, drive):
    """A brief RPM dropout mid-drive (a conflict) must not trigger 30 s of STARTUP_WARMUP."""
    n = 60
    rpm = np.full(n, 1500.0)
    rpm[30:32] = 0.0
    raw = drive([50.0] * n, rpm=rpm)
    raw["ENGINE_RUN_TIME"] = 300.0 + np.arange(n, dtype=float)
    out = label_frame(raw, config)
    assert "STARTUP_WARMUP" not in set(out["MOTION_STATE"].iloc[32:])


def test_normal_engine_off_still_engine_off(config, drive):
    out = label_frame(drive([0.0] * 10, rpm=np.zeros(10)), config)
    assert (out["MOTION_STATE"] == "ENGINE_OFF").all()
    assert not out["MODE_REASON"].str.contains("RPM_SPEED_CONFLICT").any()


def test_pull_away_is_not_high_rpm_idle(config, drive):
    """RPM rises as the car starts to roll; smoothed speed still reads ~0 for a moment."""
    speeds = np.r_[np.zeros(40), [3.0, 6.0, 9.0, 12.0, 15.0]]
    rpm = np.r_[np.full(40, 750.0), [1800.0, 2000.0, 2100.0, 2200.0, 2300.0]]
    raw = drive(speeds, rpm=rpm)
    raw["ENGINE_RUN_TIME"] = 300.0 + np.arange(len(speeds), dtype=float)
    out = label_frame(raw, config)
    assert not out["MODE_REASON"].iloc[40:].str.contains("IDLE_RPM_HIGH").any()
    assert (out["MOTION_STATE"].iloc[40:] != "IDLE").all()
