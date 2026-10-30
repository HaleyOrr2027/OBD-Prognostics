# OBD Prognostics Starter Repository

This branch intentionally contains **structure and placeholders, not a completed project**.

Start with `plan.md` and implement the numbered steps in order.

## Goal

Build a Raspberry Pi + Bluetooth OBD-II system that:
1. collects vehicle PID data,
2. identifies the current operating mode/context,
3. scores behavior against a model trained for that context,
4. abstains when context/data quality is uncertain.

## Setup

```bash
git clone -b starter-repo https://github.com/HaleyOrr2027/OBD-Prognostics.git
cd OBD-Prognostics
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On the Raspberry Pi, use `requirements-pi.txt` in addition to the normal requirements.

## First task

Do **not** start by training an autoencoder. Begin at Step 00 in `plan.md`.

## Mode detector v1 (Steps 12–25 in progress)

The operating-mode detector is implemented. It labels every sample of a drive with what the car was doing: idle, accelerating, cruising, coasting deceleration, strong deceleration, startup, or engine off.

```bash
python scripts/fetch_carobd.py                  # download the public carOBD drives into data/raw/carOBD/
python training/02_label_modes.py               # writes data/labeled/<session>.csv, one row per sample
python training/03_build_mode_inventory.py      # how much data exists per mode
python scripts/score_modes.py drive3 data/reference_labels/drive3_600-900.csv   # accuracy vs hand labels
python scripts/plot_mode_review.py drive3 --start 600 --end 900 --reference data/reference_labels/drive3_600-900.csv
python training/04_build_windows.py      # Steps 33-35: the training file, one row per window with summary features
python scripts/window_policy_report.py     # Step 30: windows per mode and accuracy, per hold time
python -m pytest tests/unit
```

See `docs/mode_taxonomy.md` for state definitions and threshold choices, and `docs/validation_protocol.md` for how accuracy is measured and the current results.

Steps 01, 02, 03, 06, 07, 09 and 10 are implemented only as far as the mode detector needs them. Step 08 (unit conversion) is a pass-through because carOBD already uses the canonical units.
