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
