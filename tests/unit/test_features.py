"""Tests for feature extraction (Step 34) and the training-file builder (Step 35)."""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from obd_anomaly.features.extract import MissingRequiredSignal, extract_features, feature_names
from obd_anomaly.pipeline import label_frame

ROOT = Path(__file__).resolve().parents[2]


def window(times, **signals):
    frame = pd.DataFrame({"ELAPSED_SEC": times})
    for name, values in signals.items():
        frame[name] = values
    return frame


def hand_window():
    # Four readings, one timestamp duplicated (as carOBD logs it):
    #   t=0 rpm 1000, t=2 rpm 1200 and 1400 (averages to 1300), t=4 rpm 1600
    return window(
        [0.0, 2.0, 2.0, 4.0],
        ENGINE_RPM=[1000.0, 1200.0, 1400.0, 1600.0],
        VEHICLE_SPEED=[10.0, 20.0, 20.0, 30.0],
        THROTTLE_POSITION=[2.0, 4.0, 4.0, 6.0],
        ENGINE_LOAD=[30.0, 30.0, 30.0, 30.0],
        INTAKE_PRESSURE=[50.0, 50.0, 50.0, 50.0],
        SHORT_FUEL_TRIM_1=[0.0, 0.0, 0.0, 0.0],
        LONG_FUEL_TRIM_1=[1.0, 1.0, 1.0, 1.0],
        COOLANT_TEMPERATURE=[85.0, 86.0, 86.0, 87.0],
    )


def test_hand_calculated_window(config):
    f, flags = extract_features(hand_window(), config)
    # Per-timestamp RPM: 1000, 1300, 1600 at t = 0, 2, 4
    assert f["ENGINE_RPM__mean"] == pytest.approx(1300.0)
    assert f["ENGINE_RPM__min"] == 1000.0
    assert f["ENGINE_RPM__max"] == 1600.0
    assert f["ENGINE_RPM__delta"] == 600.0
    assert f["ENGINE_RPM__std"] == pytest.approx(math.sqrt((300**2 + 0 + 300**2) / 3))  # 244.95
    assert f["ENGINE_RPM__slope"] == pytest.approx(150.0)   # 600 RPM over 4 s
    assert f["VEHICLE_SPEED__slope"] == pytest.approx(5.0)  # 20 km/h over 4 s
    assert f["ENGINE_LOAD__std"] == 0.0
    assert f["COOLANT_TEMPERATURE__mean"] == pytest.approx(86.0)
    assert flags == []


def test_duplicate_timestamps_are_averaged_not_double_counted(config):
    # Without averaging, the duplicated t=2 rows would pull the mean to 1300 anyway,
    # so use an asymmetric duplicate to tell the two apart.
    w = hand_window()
    w.loc[2, "ENGINE_RPM"] = 2000.0  # t=2 rows: 1200 and 2000 -> 1600
    f, _ = extract_features(w, config)
    assert f["ENGINE_RPM__mean"] == pytest.approx((1000 + 1600 + 1600) / 3)


def test_feature_names_are_fixed_and_ordered(config):
    names = feature_names(config)
    assert names[:6] == [f"VEHICLE_SPEED__{s}" for s in ["mean", "std", "min", "max", "delta", "slope"]]
    assert names[-1] == "COOLANT_TEMPERATURE__mean"
    assert len(names) == len(set(names)) == 7 * 6 + 1
    f, _ = extract_features(hand_window(), config)
    assert list(f) == names


def test_missing_required_signal_rejects_window(config):
    w = hand_window()
    w["ENGINE_LOAD"] = np.nan
    with pytest.raises(MissingRequiredSignal, match="ENGINE_LOAD"):
        extract_features(w, config)


def test_missing_optional_signal_is_nan_and_flagged_not_filled(config):
    w = hand_window().drop(columns=["SHORT_FUEL_TRIM_1"])
    f, flags = extract_features(w, config)
    assert math.isnan(f["SHORT_FUEL_TRIM_1__mean"])
    assert "MISSING_SHORT_FUEL_TRIM_1" in flags


def _builder():
    spec = importlib.util.spec_from_file_location("build_windows", ROOT / "training" / "04_build_windows.py")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(ROOT / "training"))
    spec.loader.exec_module(module)
    return module


def test_no_training_row_mixes_two_kinds_of_driving(config, drive, tmp_path):
    """Build rows from a drive that idles, accelerates, cruises and slows down,
    then check every row's samples share one mode and one segment."""
    speeds = np.r_[np.zeros(60), np.linspace(0, 50, 15), np.full(30, 50.0), np.linspace(50, 0, 15), np.zeros(30)]
    rpm = np.where(speeds > 0, 1800.0, 750.0)
    raw = drive(speeds, rpm=rpm)
    raw["ENGINE_RUN_TIME"] = 300.0 + np.arange(len(speeds), dtype=float)
    raw = raw.rename(columns={"RELATIVE_THROTTLE_POSITION": "THROTTLE_POSITION"})
    path = tmp_path / "synthetic.csv"
    raw.drop(columns=["SESSION_ID", "VEHICLE_ID", "SOURCE", "CONNECTION_OK"]).to_csv(path, index=False)

    rows, _ = _builder().build_session(path, config, vehicle_id="test")
    assert rows, "expected at least one window"
    labeled = label_frame(raw.assign(SESSION_ID="synthetic"), config)
    for row in rows:
        inside = labeled[(labeled["ELAPSED_SEC"] >= row["WINDOW_START_SEC"]) & (labeled["ELAPSED_SEC"] < row["WINDOW_END_SEC"])]
        assert inside["MOTION_STATE"].nunique() == 1
        assert (inside["MOTION_STATE"] == row["MOTION_STATE"]).all()
    assert {r["MOTION_STATE"] for r in rows} >= {"IDLE", "CRUISING"}
