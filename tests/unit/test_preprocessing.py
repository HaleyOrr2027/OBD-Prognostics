import numpy as np
import pandas as pd
import pytest

from obd_anomaly.adapters.csv_source import read_raw_csv
from obd_anomaly.config import ConfigError, load_config
from obd_anomaly.preprocessing.derived_signals import add_derived_signals
from obd_anomaly.preprocessing.normalize import ColumnCollisionError, normalize_columns
from obd_anomaly.preprocessing.quality import add_quality_flags
from obd_anomaly.preprocessing.timebase import build_timebase


def prepared(raw, config):
    frame = normalize_columns(raw, config)
    frame = build_timebase(frame, config)
    frame = add_quality_flags(frame, config)
    return add_derived_signals(frame, config)


# Step 01
def test_missing_config_dir_fails_clearly(tmp_path):
    with pytest.raises(ConfigError, match="Missing config file"):
        load_config(tmp_path)


def test_missing_key_names_the_key(config):
    with pytest.raises(ConfigError, match="modes.motion_state.not_a_key"):
        config.get("modes", "motion_state", "not_a_key")


# Step 06
def test_trailing_comma_does_not_shift_columns(tmp_path):
    path = tmp_path / "trailing.csv"
    path.write_text("ENGINE_RUN_TINE (),ENGINE_RPM (),VEHICLE_SPEED ()\n0.0, 800.0, 0.0,\n1.0, 900.0, 5.0,\n")
    frame = read_raw_csv(path)
    assert list(frame.columns) == ["ENGINE_RUN_TINE ()", "ENGINE_RPM ()", "VEHICLE_SPEED ()"]
    assert frame["ENGINE_RPM ()"].tolist() == [800.0, 900.0]


# Step 07
@pytest.mark.parametrize("header", ["ENGINE_RPM ()", "engine rpm", "RPM", "Engine-RPM"])
def test_rpm_aliases(config, header):
    out = normalize_columns(pd.DataFrame({header: [800]}), config)
    assert out["ENGINE_RPM"].tolist() == [800]


def test_carobd_run_time_typo_is_recognized(config):
    out = normalize_columns(pd.DataFrame({"ENGINE_RUN_TINE ()": [3.0]}), config)
    assert out["ENGINE_RUN_TIME"].tolist() == [3.0]


def test_two_columns_for_one_pid_raise(config):
    with pytest.raises(ColumnCollisionError):
        normalize_columns(pd.DataFrame({"RPM": [1], "ENGINE_RPM": [2]}), config)


def test_unknown_columns_are_prefixed_not_dropped(config):
    out = normalize_columns(pd.DataFrame({"FUEL_TANK ()": [50.0]}), config)
    assert "RAW_FUEL_TANK" in out.columns


# Step 09
def test_timebase_flags(config, drive):
    raw = drive([10, 10, 10, 10, 10])
    raw["ENGINE_RUN_TIME"] = [0.0, 1.0, 1.0, 20.0, 19.0]
    frame = build_timebase(normalize_columns(raw, config), config)
    flags = frame["TIME_FLAGS"].tolist()
    assert "DUPLICATE_TIME" in flags[2]
    assert "TIME_GAP" in flags[3]
    assert "CLOCK_REVERSAL" in flags[4]
    assert frame["TIME_BLOCK"].tolist() == [0, 0, 0, 1, 2]


# Step 10
def test_missing_required_pid_marks_bad_quality(config, drive):
    raw = drive([10, 10, 10])
    raw.loc[1, "VEHICLE_SPEED"] = np.nan
    frame = add_quality_flags(build_timebase(normalize_columns(raw, config), config), config)
    assert frame["DATA_QUALITY_OK"].tolist() == [True, False, True]


# Steps 12-13
def test_constant_speed_has_zero_acceleration(config, drive):
    out = prepared(drive([50.0] * 20), config)
    assert np.allclose(out["ACCELERATION_MPS2"].dropna(), 0.0)


def test_acceleration_sign(config, drive):
    up = prepared(drive(np.linspace(0, 36, 20)), config)
    down = prepared(drive(np.linspace(36, 0, 20)), config)
    assert (up["ACCELERATION_MPS2"].dropna().iloc[3:] > 0).all()
    assert (down["ACCELERATION_MPS2"].dropna().iloc[3:] < 0).all()


def test_ramp_acceleration_in_mps2(config, drive):
    out = prepared(drive(np.arange(0, 40, 3.6)), config)  # +3.6 km/h per second = 1 m/s^2
    assert np.isclose(out["ACCELERATION_MPS2"].iloc[-1], 1.0, atol=0.05)


def test_duplicate_timestamps_never_produce_infinity(config, drive):
    raw = drive([10, 11, 12, 13, 14, 15])
    raw["ENGINE_RUN_TIME"] = [0, 0, 1, 1, 2, 2]
    out = prepared(raw, config)
    assert np.isfinite(out["ACCELERATION_MPS2"].dropna()).all()


def test_smoothing_is_causal(config, drive):
    """Changing a future sample must not change any earlier smoothed value."""
    base = prepared(drive([30.0] * 10), config)
    changed = drive([30.0] * 10)
    changed.loc[9, "VEHICLE_SPEED"] = 90.0
    after = prepared(changed, config)
    pd.testing.assert_series_equal(base["SPEED_SMOOTH_KMH"].iloc[:9], after["SPEED_SMOOTH_KMH"].iloc[:9])
