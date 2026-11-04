import numpy as np
import pandas as pd

from obd_anomaly.config import load_config
from obd_anomaly.intent.detector import detect_driver_request
from obd_anomaly.preprocessing.normalize import normalize_columns


def frame(d, e=None, throttle=None, times=None):
    n = len(d)
    result = pd.DataFrame({
        "ELAPSED_SEC": list(range(n)) if times is None else times,
        "TIME_BLOCK": [0] * n,
        "ACCELERATOR_PEDAL_POSITION_D": d,
    })
    if e is not None:
        result["ACCELERATOR_PEDAL_POSITION_E"] = e
    if throttle is not None:
        result["COMMANDED_THROTTLE_ACTUATOR"] = throttle
    return result


def test_real_carobd_column_aliases():
    raw = pd.DataFrame({"PEDAL_D ()": [30.], "PEDAL_E ()": [20.],
                        "COMMANDED_THROTTLE_ACTUATOR ()": [18.]})
    out = normalize_columns(raw, load_config())
    assert out["ACCELERATOR_PEDAL_POSITION_D"].iloc[0] == 30
    assert out["ACCELERATOR_PEDAL_POSITION_E"].iloc[0] == 20
    assert out["COMMANDED_THROTTLE_ACTUATOR"].iloc[0] == 18


def test_increase_hold_release():
    out = detect_driver_request(frame([10, 15, 15, 4, 4], [20, 25, 25, 14, 3]))
    assert out["DRIVER_REQUEST"].tolist() == [
        "UNKNOWN_REQUEST", "ACCELERATE_REQUEST", "MAINTAIN_REQUEST",
        "RELEASE_ACCELERATOR", "RELEASE_ACCELERATOR"
    ]
    assert out["DRIVER_REQUEST_SOURCE"].iloc[1] == "PEDAL"


def test_no_accelerator_request_when_both_low():
    out = detect_driver_request(frame([0, 0, 0], [0, 0, 0]))
    assert out["DRIVER_REQUEST"].iloc[1] == "NO_ACCELERATOR_REQUEST"


def test_conflicting_sensors_abstain():
    out = detect_driver_request(frame([15, 25], [25, 15]))
    assert out["DRIVER_REQUEST"].iloc[-1] == "UNKNOWN_REQUEST"
    assert out["DRIVER_REQUEST_REASON"].iloc[-1] == "PEDAL_CHANNEL_CONFLICT"


def test_commanded_throttle_is_only_a_proxy():
    out = detect_driver_request(frame([np.nan, np.nan], throttle=[10, 20]))
    assert out["DRIVER_REQUEST"].iloc[-1] == "ACCELERATE_REQUEST"
    assert out["DRIVER_REQUEST_SOURCE"].iloc[-1] == "THROTTLE_PROXY"
    assert out["DRIVER_REQUEST_CONFIDENCE"].iloc[-1] <= 0.4


def test_missing_inputs_do_not_guess():
    out = detect_driver_request(frame([np.nan, np.nan]))
    assert (out["DRIVER_REQUEST"] == "UNKNOWN_REQUEST").all()


def test_large_gap_does_not_infer_change():
    out = detect_driver_request(frame([10, 50], times=[0, 20]))
    assert out["DRIVER_REQUEST"].iloc[-1] == "UNKNOWN_REQUEST"


def test_duplicate_timestamps_share_result():
    out = detect_driver_request(frame([10, 10, 20, 20], times=[0, 0, 1, 1]))
    assert out["DRIVER_REQUEST"].tolist() == [
        "UNKNOWN_REQUEST", "UNKNOWN_REQUEST",
        "ACCELERATE_REQUEST", "ACCELERATE_REQUEST"
    ]


def test_future_input_does_not_change_past_results():
    before = detect_driver_request(frame([10, 12, 14, 16]))
    after = detect_driver_request(frame([10, 12, 14, 50]))
    assert before["DRIVER_REQUEST"].iloc[:3].tolist() == after["DRIVER_REQUEST"].iloc[:3].tolist()
