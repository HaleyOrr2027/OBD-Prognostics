import numpy as np
import pandas as pd

from obd_anomaly.features.windows import extract_windows


def labeled(states, times=None, confidence=1.0, session="s1"):
    """Minimal labeled frame: one sample per second unless times are given."""
    n = len(states)
    t = np.arange(n, dtype=float) if times is None else np.asarray(times, dtype=float)
    frame = pd.DataFrame({
        "SESSION_ID": session,
        "ELAPSED_SEC": t,
        "MOTION_STATE": states,
        "MODE_CONFIDENCE": confidence,
        "DATA_QUALITY_OK": True,
        "QUALITY_FLAGS": "",
    })
    change = frame["MOTION_STATE"] != frame["MOTION_STATE"].shift()
    frame["MODE_SEGMENT_ID"] = session + "-" + change.cumsum().map("{:04d}".format)
    return frame


def test_windows_never_cross_a_segment_boundary(config):
    frame = labeled(["ACCELERATING"] * 8 + ["CRUISING"] * 20)
    windows, _ = extract_windows(frame, config)
    for w in windows.itertuples():
        inside = frame[(frame.ELAPSED_SEC >= w.WINDOW_START_SEC) & (frame.ELAPSED_SEC < w.WINDOW_END_SEC)]
        assert inside["MODE_SEGMENT_ID"].nunique() == 1
        assert (inside["MOTION_STATE"] == w.MOTION_STATE).all()


def test_segment_shorter_than_window_gives_nothing(config):
    windows, _ = extract_windows(labeled(["ACCELERATING"] * 5), config)  # 4 s long, window is 6 s
    assert windows.empty


def test_partial_final_window_is_discarded(config):
    # ACCELERATING: 6 s window, 2 s stride. A segment spanning 0..10 s fits starts 0, 2, 4.
    windows, _ = extract_windows(labeled(["ACCELERATING"] * 11), config)
    assert windows["WINDOW_START_SEC"].tolist() == [0.0, 2.0, 4.0]
    assert (windows["WINDOW_END_SEC"] <= 10.0).all()


def test_window_ids_are_deterministic(config):
    frame = labeled(["CRUISING"] * 30)
    first, _ = extract_windows(frame, config)
    second, _ = extract_windows(frame, config)
    assert first["WINDOW_ID"].tolist() == second["WINDOW_ID"].tolist()
    assert first["WINDOW_ID"].is_unique


def test_low_confidence_window_is_rejected(config):
    windows, rejected = extract_windows(labeled(["CRUISING"] * 30, confidence=0.3), config)
    assert windows.empty and rejected["LOW_CONFIDENCE"] > 0


def test_internal_gap_is_rejected(config):
    times = [0, 1, 2, 7, 8, 9, 10, 11, 12]  # 5 s jump inside the first windows
    windows, rejected = extract_windows(labeled(["ACCELERATING"] * 9, times=times), config)
    assert rejected["INTERNAL_GAP"] > 0
    assert all(w.WINDOW_START_SEC >= 2 for w in windows.itertuples())


def test_too_few_distinct_timestamps_is_rejected(config):
    times = np.repeat([0.0, 4.0, 8.0], 4)  # only two distinct times fit in any 6 s window
    windows, rejected = extract_windows(labeled(["ACCELERATING"] * 12, times=times), config)
    assert windows.empty and rejected["TOO_FEW_TIMES"] > 0


def test_unscorable_modes_get_no_windows(config):
    frame = labeled(["STARTUP_WARMUP"] * 40 + ["ENGINE_OFF"] * 40)
    windows, _ = extract_windows(frame, config)
    assert windows.empty
