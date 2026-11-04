"""Tests for turning a passenger's event log into reference labels."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import event_log_to_labels as ev  # noqa: E402

from obd_anomaly.pipeline import label_frame  # noqa: E402


def write_log(tmp_path, lines):
    path = tmp_path / "events.csv"
    path.write_text("time,event,note\n" + "\n".join(lines) + "\n")
    return path


@pytest.mark.parametrize("text, seconds", [("0:00", 0), ("1:06", 66), ("45", 45), ("1:02:03", 3723)])
def test_parse_clock(text, seconds):
    assert ev.parse_clock(text) == seconds


def test_events_become_intervals_with_offset(tmp_path):
    log = ev.read_event_log(write_log(tmp_path, [
        "0:00,sync,rev", "0:20,pull away,", "0:31,steady,about 40", "0:58,slowing,light", "1:06,stopped,", "1:30,end,",
    ]))
    labels = ev.to_reference_labels(log, offset=100)
    assert labels[["start_s", "end_s", "label"]].values.tolist() == [
        [120, 130, "accel"], [131, 157, "steady"], [158, 165, "decel"], [166, 189, "idle"],
    ]


def test_unknown_event_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="Unknown event"):
        ev.read_event_log(write_log(tmp_path, ["0:00,sync,", "0:10,drifting,", "0:20,end,"]))


def test_missing_end_is_rejected(tmp_path):
    log = ev.read_event_log(write_log(tmp_path, ["0:00,sync,", "0:10,steady,"]))
    with pytest.raises(SystemExit, match="'end' event"):
        ev.to_reference_labels(log, offset=0)


def test_sync_rev_found_in_rpm(config, drive):
    # Parked at 750 RPM, a rev to 2200 at t=40 s, then back to idle.
    rpm = np.full(90, 750.0)
    rpm[40:43] = 2200.0
    raw = drive([0.0] * 90, rpm=rpm)
    raw["ENGINE_RUN_TIME"] = np.arange(90, dtype=float)
    labeled = label_frame(raw, config)
    assert ev.find_sync_rev(labeled) == pytest.approx(40.0)
