import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from obd_anomaly.config import load_config  # noqa: E402


@pytest.fixture
def config():
    return load_config()


def make_drive(speeds, step=1.0, rpm=None, session="synthetic"):
    """Raw frame shaped like CSVSource.to_frame() output, one sample per step seconds."""
    n = len(speeds)
    return pd.DataFrame({
        "SESSION_ID": session,
        "VEHICLE_ID": "test",
        "SOURCE": "csv",
        "CONNECTION_OK": True,
        "ENGINE_RUN_TIME": 100.0 + np.arange(n) * step,
        "ENGINE_RPM": rpm if rpm is not None else np.full(n, 1500.0),
        "VEHICLE_SPEED": np.asarray(speeds, dtype=float),
        "RELATIVE_THROTTLE_POSITION": np.full(n, 5.0),
        "ENGINE_LOAD": np.full(n, 40.0),
        "COOLANT_TEMPERATURE": np.full(n, 88.0),
    })


@pytest.fixture
def drive():
    return make_drive
