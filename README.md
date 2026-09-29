# OBD Prognostics — Mode-Aware Rebuild

Raspberry Pi + Bluetooth OBD-II anomaly detection where normal behavior is conditioned on the current vehicle operating mode.

Pipeline:
OBD-II -> preprocessing -> mode detection -> mode-specific window -> mode-specific anomaly model -> NORMAL / ANOMALOUS / UNSCORED

Modes:
ENGINE_OFF, STARTUP_WARMUP, IDLE, ACCELERATING, CRUISING, COASTING_DECEL, STRONG_DECEL, UNKNOWN_TRANSITION.

STRONG_DECEL is not called braking because generic OBD-II speed data does not prove brake-pedal application.

## Setup

git clone -b mode-aware-rebuild https://github.com/HaleyOrr2027/OBD-Prognostics.git
cd OBD-Prognostics
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
pytest

## Offline training

Put healthy CSV drives in data/raw, then:

python training/train.py
python scripts/replay_drive.py data/raw/YOUR_DRIVE.csv

The training command normalizes each session, labels modes, extracts pure-mode windows, splits by whole session, fits a scaler and Isolation Forest for each mode, calibrates a separate threshold, and writes models/registry.json plus per-mode bundles.

## Raspberry Pi

Install Pi dependencies:

pip install -e ".[pi]"

Pair the Bluetooth ELM327-compatible adapter in Linux and expose a serial device such as /dev/rfcomm0. Set the device in config/default.yaml.

Discover supported PIDs:
python scripts/discover_obd.py

Record healthy data:
python scripts/record_drive.py --seconds 600

Run live inference after models have been trained:
python scripts/run_pi.py

This is an anomaly detector, not a safety-critical diagnostic or replacement for manufacturer warnings/professional inspection.
