# OBD Prognostics — Implementation Plan

> **Purpose of this branch:** this is a starter repository, not a finished project. The files are intentionally empty or skeletal. Implement the project in the order below. Do not skip artifact/validation steps just because a later model can technically be trained.

---

# 0. Project Goal

Build a Raspberry Pi system that connects to a vehicle through a Bluetooth OBD-II adapter, continuously collects supported OBD-II PIDs, determines the vehicle's current operating context, and reports whether the observed behavior is anomalous **relative to that context**.

The core problem is conditional normality:

- 800 RPM may be normal at warm idle.
- 3,000 RPM may be normal during acceleration.
- falling manifold pressure may be normal during deceleration.
- high load may be normal on a hill.
- unstable RPM may be normal immediately after startup but suspicious after warm-up.

Therefore the final system must **not** train one undifferentiated "normal driving" detector and apply it everywhere.

The first production-worthy architecture should be:

```text
Bluetooth OBD-II adapter
        |
        v
raw PID acquisition + timestamps
        |
        v
canonical schema + quality flags
        |
        v
derived signals
(speed smoothing, acceleration, deltas, age/staleness)
        |
        v
context / mode detector
        |
        +--> ENGINE_OFF / STARTUP_WARMUP / UNKNOWN => abstain
        |
        v
stable motion mode
(IDLE / ACCELERATING / CRUISING / COASTING_DECEL / STRONG_DECEL)
        |
        v
mode-specific window policy
        |
        v
feature extraction
        |
        v
model registry selects model for current mode
        |
        v
anomaly score + mode-specific threshold
        |
        v
NORMAL / ANOMALOUS / UNSCORED
        |
        v
event merging + logs + explanation fields
```

## 0.1 What this project is not

This project is not a replacement for dashboard warning lamps, DTCs, manufacturer diagnostics, professional inspection, or any safety-critical control system. An anomaly means "unusual relative to the healthy data/model for this context," not automatically "this component is broken."

## 0.2 Architecture decision for version 1

Use a **hierarchical context model** rather than exploding every combination into a separate flat class.

Track these axes:

| Axis | Initial values | Used for |
|---|---|---|
| Engine state | OFF, RUNNING | hard scoring gate |
| Thermal/start state | STARTUP_WARMUP, WARM_OR_UNKNOWN | scoring gate/context |
| Motion state | IDLE, ACCELERATING, CRUISING, COASTING_DECEL, STRONG_DECEL, UNKNOWN_TRANSITION | primary model routing |
| Load context | LOW, MEDIUM, HIGH, UNKNOWN | feature/context first; split models later only if data proves useful |

The v1 anomaly registry should primarily route by **motion state**. Startup/warm-up should initially abstain unless enough healthy startup data is collected to justify a dedicated model. Load and thermal values should first be included as features/context rather than multiplying the number of models.

This is a project engineering choice to validate against real drives, not a universal OBD rule.

---

# 1. Starter Repository Target Structure

```text
OBD-Prognostics/
├── README.md
├── plan.md
├── requirements.txt
├── requirements-pi.txt
├── .gitignore
│
├── config/
│   ├── pids.yaml
│   ├── modes.yaml
│   ├── windows.yaml
│   ├── models.yaml
│   └── runtime.yaml
│
├── docs/
│   ├── data_dictionary.md
│   ├── mode_taxonomy.md
│   ├── data_collection_protocol.md
│   └── validation_protocol.md
│
├── data/
│   ├── raw/
│   ├── inventory/
│   ├── normalized/
│   ├── labeled/
│   ├── windows/
│   └── manifests/
│
├── src/
│   └── obd_anomaly/
│       ├── __init__.py
│       ├── schemas.py
│       ├── config.py
│       ├── pipeline.py
│       ├── results.py
│       │
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── csv_source.py
│       │   └── bluetooth_obd_source.py
│       │
│       ├── preprocessing/
│       │   ├── __init__.py
│       │   ├── normalize.py
│       │   ├── timebase.py
│       │   ├── quality.py
│       │   └── derived_signals.py
│       │
│       ├── modes/
│       │   ├── __init__.py
│       │   ├── engine_state.py
│       │   ├── thermal_state.py
│       │   ├── motion_state.py
│       │   ├── load_state.py
│       │   ├── persistence.py
│       │   ├── detector.py
│       │   └── segments.py
│       │
│       ├── features/
│       │   ├── __init__.py
│       │   ├── buffer.py
│       │   ├── windows.py
│       │   └── extract.py
│       │
│       └── anomaly/
│           ├── __init__.py
│           ├── registry.py
│           ├── scorer.py
│           ├── explain.py
│           └── events.py
│
├── training/
│   ├── 00_inventory_raw_data.py
│   ├── 01_normalize_sessions.py
│   ├── 02_label_modes.py
│   ├── 03_build_mode_inventory.py
│   ├── 04_build_windows.py
│   ├── 05_make_splits.py
│   ├── 06_fit_scalers.py
│   ├── 07_train_baselines.py
│   ├── 08_calibrate_thresholds.py
│   ├── 09_evaluate_healthy.py
│   └── 10_export_registry.py
│
├── scripts/
│   ├── inspect_adapter.py
│   ├── collect_drive.py
│   ├── replay_drive.py
│   ├── run_pi.py
│   └── benchmark_pi.py
│
├── models/
│   └── .gitkeep
│
├── tests/
│   ├── fixtures/
│   ├── unit/
│   └── integration/
│
├── deployment/
│   ├── obd-anomaly.service
│   └── install_pi.sh
│
└── outputs/
    ├── plots/
    ├── evaluation/
    ├── benchmarks/
    └── logs/
```

---

# 2. Artifact Contracts

Do not let scripts invent their own schemas. Define these contracts first in `src/obd_anomaly/schemas.py` and document them in `docs/data_dictionary.md`.

## 2.1 Raw sample contract

One row represents one acquisition cycle, not necessarily one simultaneous ECU snapshot.

Required metadata:

| Field | Meaning |
|---|---|
| SESSION_ID | unique drive/collection session |
| TIMESTAMP_UTC | wall-clock timestamp |
| MONOTONIC_SEC | monotonic elapsed time used for intervals |
| VEHICLE_ID | pseudonymous vehicle identifier |
| SOURCE | csv or bluetooth_obd |
| CONNECTION_OK | adapter connection health |

PID columns are nullable because support differs by vehicle.

Recommended initial PID vocabulary:

| Canonical field | Purpose | Initial importance |
|---|---|---|
| ENGINE_RPM | engine state + behavior | required for v1 |
| VEHICLE_SPEED | motion state | required for v1 |
| ENGINE_LOAD | power/load context | recommended |
| THROTTLE_POSITION | driver/engine demand proxy | recommended |
| COOLANT_TEMPERATURE | warm-up context | recommended |
| MAF | airflow/load behavior | optional |
| INTAKE_PRESSURE | load behavior | optional |
| INTAKE_TEMPERATURE | environmental/context | optional |
| SHORT_FUEL_TRIM_1 | fuel-control behavior | optional |
| LONG_FUEL_TRIM_1 | fuel-control baseline | optional |
| ENGINE_RUN_TIME | startup timing fallback | optional |

Never assume every car supports every PID.

## 2.2 Normalized sample contract

Raw contract plus:

- canonical numeric units
- `SAMPLE_DT_SEC`
- per-PID validity flags
- per-PID age/staleness if polling asynchronously
- `DATA_QUALITY_OK`
- `QUALITY_FLAGS`

## 2.3 Derived-signal contract

Normalized sample plus:

- `SPEED_SMOOTH_KMH`
- `ACCELERATION_MPS2`
- `RPM_DELTA_PER_SEC`
- `LOAD_DELTA_PER_SEC` when load exists
- `THROTTLE_DELTA_PER_SEC` when throttle exists
- `SECONDS_SINCE_ENGINE_START`

## 2.4 Mode-state contract

| Field | Meaning |
|---|---|
| ENGINE_STATE | OFF/RUNNING/UNKNOWN |
| THERMAL_STATE | STARTUP_WARMUP/WARM_OR_UNKNOWN |
| MOTION_STATE_RAW | rule result before persistence |
| MOTION_STATE | persisted stable state |
| LOAD_STATE | LOW/MEDIUM/HIGH/UNKNOWN |
| MODE_CONFIDENCE | 0-1 confidence/quality score |
| MODE_REASON | machine-readable reason flags |
| MODE_SEGMENT_ID | contiguous stable-mode segment |

## 2.5 Feature-window contract

| Field | Meaning |
|---|---|
| WINDOW_ID | unique identifier |
| SESSION_ID | source session |
| MODE_SEGMENT_ID | source stable segment |
| MOTION_STATE | model-routing mode |
| WINDOW_START_SEC | elapsed start |
| WINDOW_END_SEC | elapsed end |
| DURATION_SEC | actual duration |
| SAMPLE_COUNT | rows used |
| MIN_MODE_CONFIDENCE | weakest confidence in window |
| QUALITY_FLAGS | window-level quality |
| FEATURE_* | extracted numeric features |

## 2.6 Anomaly-result contract

| Field | Meaning |
|---|---|
| RESULT_TIME_UTC | decision time |
| WINDOW_ID | scored window |
| MOTION_STATE | routing mode |
| MODE_CONFIDENCE | routing confidence |
| STATUS | NORMAL / ANOMALOUS / UNSCORED |
| ANOMALY_SCORE | model score |
| THRESHOLD | threshold for this mode/model |
| MODEL_VERSION | exact artifact version |
| TOP_CONTRIBUTORS | explanation data if supported |
| REASON | especially for UNSCORED |

---

# 3. Execution Rules

1. Raw data is immutable. Never overwrite `data/raw/`.
2. Generated datasets are reproducible from raw data + committed config.
3. Train/calibration/test splits happen by **session**, not random rows.
4. A mode is not considered supported until enough independent healthy sessions exist.
5. A model never scores a window whose mode is uncertain or unsupported.
6. Threshold calibration data is separate from model-fitting data.
7. Test data remains untouched until model + threshold are frozen.
8. Synthetic anomalies are only pipeline sanity tests; they are not evidence of real fault recall.
9. Every training artifact stores the exact feature list, config hash/version, sessions used, threshold, and library versions.
10. The Raspberry Pi performs inference only. Training stays on a development computer unless benchmarking later proves otherwise.

---

# 4. Detailed Implementation Sequence

## Step 00 — Create and verify the development environment

**Goal:** make the empty starter repo reproducibly installable.

**Why:** every later result is suspect if developers use different Python/dependency environments.

**Inputs:** `requirements.txt`, `requirements-pi.txt`.

**Files to modify:** `README.md`, optionally add `pyproject.toml` after deciding packaging style.

**Implementation actions:**
- Select one supported Python version for development and Pi.
- Create `.venv`.
- Install development dependencies.
- Verify imports for numpy, pandas, yaml, sklearn, joblib, pytest.
- On Pi only, verify `obd`/serial dependencies separately.

**Outputs:** working local virtual environment; documented install commands.

**Validation:** run a one-line import check and `pytest` even though the initial suite is empty.

**Definition of done:** a second machine can clone the branch and reproduce the environment using only README instructions.

**Next step consumes:** stable dependency environment.

---

## Step 01 — Define canonical configuration loading

**Goal:** all thresholds and paths come from config files rather than scattered constants.

**Inputs:** files under `config/`.

**Files to implement:** `src/obd_anomaly/config.py`.

**Implementation actions:**
- Create a typed configuration loader.
- Resolve paths relative to repo root.
- Validate required keys.
- Fail with actionable messages for missing/invalid keys.
- Add a config-version field.
- Keep vehicle-specific overrides possible without changing source.

**Outputs:** one configuration object used by training and runtime.

**Tests:** `tests/unit/test_config.py` for missing file, malformed YAML, missing key, valid config.

**Done:** no later module reads YAML directly.

**Next:** schemas and PID definitions use the same config object.

---

## Step 02 — Define data classes / schemas before writing processing code

**Goal:** freeze interfaces between acquisition, preprocessing, mode detection, features, and scoring.

**Inputs:** artifact contracts in Section 2.

**Files to implement:** `src/obd_anomaly/schemas.py`, `docs/data_dictionary.md`.

**Implementation actions:**
- Define `OBDSample`.
- Define `NormalizedSample`.
- Define `ModeState`.
- Define `FeatureWindow`.
- Define `AnomalyResult`.
- Decide whether internal batch processing uses dataclasses, DataFrames, or both.
- Document nullable vs required fields and units.

**Outputs:** importable schema definitions and human-readable data dictionary.

**Tests:** construct valid/invalid examples.

**Done:** every module in the plan can name its input/output type.

---

## Step 03 — Define the PID registry

**Goal:** separate "what we would like to read" from "what this vehicle actually supports."

**Inputs:** generic OBD-II PID candidates.

**Files to fill:** `config/pids.yaml`, `docs/data_dictionary.md`.

**Implementation actions:**
- List required, recommended, and optional PIDs.
- For each PID store canonical name, python-OBD command name, target unit, expected type, polling priority.
- Do not encode plausible-value anomaly limits yet; keep acquisition validation separate from anomaly learning.
- Add aliases for historical CSV column names if existing datasets use different labels.

**Output:** versioned PID registry.

**Validation:** config loader can parse every entry and canonical names are unique.

**Done:** live and CSV adapters can target the same canonical vocabulary.

---

## Step 04 — Define raw drive metadata

**Goal:** make every collection session traceable.

**Inputs:** planned road tests.

**Files to fill:** `docs/data_collection_protocol.md`.

**Implementation actions:**
- Define `SESSION_ID`, pseudonymous `VEHICLE_ID`, date/time, route label, cold/warm start, known DTCs, recent maintenance, weather notes, driver notes, adapter model.
- Decide whether metadata lives in a sidecar JSON file or repeated CSV columns.
- Never store unnecessary personal/location information.

**Output:** documented session metadata schema.

**Validation:** create one hand-written example metadata record.

**Done:** every future raw file can be tied to a collection context.

---

## Step 05 — Implement raw dataset inventory

**Goal:** know what data exists before preprocessing or modeling.

**Inputs:** `data/raw/**/*`.

**File to implement:** `training/00_inventory_raw_data.py`.

**Implementation actions:**
- Recursively discover supported raw files.
- Record file path, session ID, rows, columns, parse status, timestamp availability, duration estimate, missingness, min/max RPM, min/max speed.
- Never silently skip a failed file.
- Record parse errors in the inventory.

**Output:** `data/inventory/dataset_inventory.csv`.

**Validation:** number of inventory rows equals number of discovered raw sessions.

**Done:** one table answers which sessions and PIDs are available.

---

## Step 06 — Implement the CSV replay source adapter

**Goal:** make offline files look like the future live source.

**Inputs:** one raw CSV.

**Files to implement:** `src/obd_anomaly/adapters/base.py`, `csv_source.py`.

**Implementation actions:**
- Define a source interface: open/start, read/iterate sample, close.
- CSV source yields samples in timestamp order.
- Preserve original raw values until normalization.
- Support fast replay and optionally real-time replay later.

**Output:** stream/iterator of `OBDSample`-compatible records.

**Tests:** tiny fixture CSV with known order and nulls.

**Done:** downstream pipeline code does not care whether input came from CSV or Bluetooth.

---

## Step 07 — Normalize column names

**Goal:** eliminate dataset-specific naming differences.

**Inputs:** raw CSV samples and PID registry aliases.

**File to implement:** `preprocessing/normalize.py`.

**Implementation actions:**
- Normalize case and punctuation.
- Apply explicit alias map.
- Detect collisions: two raw columns mapping to one canonical name must raise or be resolved explicitly.
- Preserve unknown columns separately or pass them through without letting them become model features automatically.

**Output:** canonical column names.

**Tests:** RPM, rpm, ENGINE RPM, historical typo aliases.

**Done:** downstream code only references canonical names.

---

## Step 08 — Normalize units

**Goal:** make values comparable across files and live acquisition.

**Inputs:** canonical PID values + registry target units.

**File:** `preprocessing/normalize.py`.

**Implementation actions:**
- Convert speed to km/h or chosen canonical unit.
- Convert temperatures to Celsius.
- Convert pressure/MAF consistently.
- Store unit conventions in data dictionary.
- Reject ambiguous unitless historical columns unless the source convention is known.

**Output:** numeric canonical-unit columns.

**Validation:** known conversion fixtures.

**Done:** one canonical unit exists per sensor.

---

## Step 09 — Build a trustworthy time base

**Goal:** derive intervals from monotonic time rather than assuming one row equals one second.

**Inputs:** MONOTONIC_SEC if collected live; otherwise TIMESTAMP or ENGINE_RUN_TIME fallback.

**File:** `preprocessing/timebase.py`.

**Implementation actions:**
- Select source priority.
- Compute elapsed session time.
- Compute `SAMPLE_DT_SEC`.
- Flag zero, negative, or very large gaps.
- Never silently repair clock reversals without a quality flag.

**Outputs:** elapsed time + interval + time quality flags.

**Tests:** irregular sampling, duplicate timestamps, gap, clock reversal.

**Done:** derivatives never use implicit row spacing.

---

## Step 10 — Add sample-level data quality flags

**Goal:** distinguish "weird vehicle behavior" from "bad/missing acquisition."

**Inputs:** normalized sample.

**File:** `preprocessing/quality.py`.

**Implementation actions:**
- Flag missing required PIDs.
- Flag stale values.
- Flag nonnumeric parse failures.
- Flag connection interruptions.
- Flag impossible acquisition metadata such as negative dt.
- Keep quality checks conservative; do not turn learned anomaly rules into hard-coded plausibility rules.

**Outputs:** `DATA_QUALITY_OK`, `QUALITY_FLAGS`.

**Tests:** one fixture per flag.

**Done:** anomaly model can abstain because data quality is bad.

---

## Step 11 — Measure real sampling behavior

**Goal:** stop assuming an OBD sampling rate.

**Inputs:** several raw/live sessions.

**Files:** add analysis to `training/00_inventory_raw_data.py`; document in `outputs/evaluation/sampling_report.csv`.

**Implementation actions:**
- Measure median/p5/p95 dt.
- Measure effective update rate per PID.
- Measure missing/stale fraction.
- Compare rates when polling different PID counts.
- Record adapter/car combination.

**Output:** sampling report.

**Done:** later smoothing/window policies are based on measured timing.

---

## Step 12 — Implement speed smoothing

**Goal:** reduce quantization/jitter before differentiation.

**Inputs:** VEHICLE_SPEED + timestamps.

**File:** `preprocessing/derived_signals.py`.

**Implementation actions:**
- Start with a short rolling median or another causal filter suitable for online use.
- Keep raw speed.
- Configure filter length in time/samples.
- Do not use a centered future-looking filter in the live path.

**Output:** `SPEED_SMOOTH_KMH`.

**Tests:** constant speed with spikes; acceleration ramp.

**Done:** smoothing suppresses isolated noise without erasing real transitions.

---

## Step 13 — Derive acceleration robustly

**Goal:** obtain the main signal for motion-state changes.

**Inputs:** smoothed speed + actual dt.

**File:** `derived_signals.py`.

**Implementation actions:**
- Convert speed to m/s.
- Differentiate using actual elapsed time.
- Guard tiny/invalid dt.
- Optionally smooth the derivative separately.
- Flag acceleration as invalid across large acquisition gaps.

**Output:** `ACCELERATION_MPS2`.

**Tests:** constant speed ≈ 0; increasing speed > 0; decreasing speed < 0.

**Done:** no infinities and sign is correct.

---

## Step 14 — Derive engine/load transient signals

**Goal:** expose short-term changes without requiring a sequence model initially.

**Inputs:** RPM, load, throttle when available.

**File:** `derived_signals.py`.

**Implementation actions:**
- Compute per-second RPM delta.
- Compute load/throttle deltas.
- Respect actual dt.
- Leave unavailable optional features null.

**Outputs:** derivative columns.

**Done:** derived features are deterministic offline and online.

---

## Step 15 — Detect engine state

**Goal:** establish the first hard routing gate.

**Inputs:** RPM plus connection/quality state.

**File:** `modes/engine_state.py`.

**Implementation actions:**
- Define OFF, RUNNING, UNKNOWN.
- Configure an RPM threshold but test it against real vehicle data.
- Do not treat adapter disconnect as engine off.
- Add hysteresis if near-threshold noise exists.

**Output:** ENGINE_STATE.

**Tests:** off, cranking/ambiguous, running, disconnected.

**Done:** scoring cannot occur while engine state is OFF/UNKNOWN.

---

## Step 16 — Track seconds since engine start

**Goal:** identify startup context.

**Inputs:** engine-state transitions + monotonic time; optionally ENGINE_RUN_TIME.

**File:** `modes/thermal_state.py`.

**Implementation actions:**
- Detect OFF/UNKNOWN -> RUNNING transition.
- Start/reset timer.
- Reconcile with ENGINE_RUN_TIME when available.
- Define behavior when collection begins after engine is already running.

**Output:** `SECONDS_SINCE_ENGINE_START`.

**Done:** startup timer is reproducible in replay and live modes.

---

## Step 17 — Implement startup/warm-up context v1

**Goal:** prevent cold/start transient behavior from contaminating warm models.

**Inputs:** seconds since start; coolant temperature if available.

**File:** `modes/thermal_state.py`; config in `modes.yaml`.

**Implementation actions:**
- Start with a conservative time-based startup guard.
- If coolant exists, record it as context but do not hard-code a universal warm threshold without vehicle data.
- Define WARM_OR_UNKNOWN after startup guard.
- Later evaluate whether coolant-based submodels improve results.

**Output:** THERMAL_STATE.

**Done:** startup samples are separable from steady operation.

---

## Step 18 — Detect stopped vs moving

**Goal:** establish robust idle eligibility.

**Inputs:** speed, RPM, quality.

**File:** `modes/motion_state.py`.

**Implementation actions:**
- Configure a small stopped-speed tolerance.
- Require engine running for IDLE.
- Decide how to treat creeping/stop-and-go traffic.
- Keep UNKNOWN_TRANSITION for ambiguous cases.

**Output:** raw IDLE/MOVING classification.

**Tests:** engine off at 0 speed is not idle; running at 0 is idle candidate.

**Done:** idle is not inferred from speed alone.

---

## Step 19 — Detect acceleration, steady motion, and deceleration

**Goal:** create the primary model-routing states.

**Inputs:** moving state + acceleration.

**File:** `motion_state.py`.

**Implementation actions:**
- Configure positive acceleration threshold.
- Configure negative deceleration threshold.
- Define steady band around zero.
- Define stronger negative threshold for STRONG_DECEL.
- Call it STRONG_DECEL, not BRAKING, unless a real brake signal exists.

**Output:** MOTION_STATE_RAW.

**Tests:** synthetic trajectories and real reviewed snippets.

**Done:** each valid moving sample gets a preliminary state or UNKNOWN_TRANSITION.

---

## Step 20 — Add load context

**Goal:** distinguish low/medium/high engine demand without multiplying models yet.

**Inputs:** ENGINE_LOAD, throttle, MAP/MAF if available.

**File:** `modes/load_state.py`.

**Implementation actions:**
- Begin with ENGINE_LOAD-based bins only if that PID is reliable on the target car.
- Otherwise emit UNKNOWN.
- Treat thresholds as vehicle/config-specific.
- Preserve continuous load as a model feature.

**Output:** LOAD_STATE.

**Done:** load context exists but does not force a separate model in v1.

---

## Step 21 — Compose the context detector

**Goal:** produce one coherent ModeState object.

**Inputs:** engine, thermal, raw motion, load states.

**File:** `modes/detector.py`.

**Implementation actions:**
- Define priority: bad quality/unknown engine -> abstain; engine off -> off; startup -> startup; otherwise motion state.
- Produce reason codes.
- Keep axes separately in output rather than collapsing all information into one string.

**Output:** ModeState before persistence.

**Done:** one function/class produces the full context record for every sample.

---

## Step 22 — Add persistence/hysteresis

**Goal:** prevent mode flapping near thresholds.

**Inputs:** raw context stream.

**File:** `modes/persistence.py`.

**Implementation actions:**
- Track current stable state, candidate state, candidate start time.
- Require configurable dwell time before switching.
- Allow immediate transitions for hard states such as engine off if appropriate.
- Use time, not row count.

**Output:** stable MOTION_STATE.

**Tests:** noisy threshold crossings and genuine sustained transitions.

**Done:** short noise spikes do not create new mode segments.

---

## Step 23 — Compute mode confidence

**Goal:** explicitly represent uncertainty.

**Inputs:** data quality, distance from thresholds, optional PID availability, transition state.

**File:** `modes/detector.py`.

**Implementation actions:**
- Define interpretable confidence components.
- Lower confidence near decision boundaries.
- Lower confidence when required derived signals are stale.
- Configure minimum confidence for model scoring.

**Output:** MODE_CONFIDENCE + MODE_REASON.

**Done:** uncertain samples can be UNSCORED rather than misrouted.

---

## Step 24 — Build stable mode segments

**Goal:** create contiguous events from the persisted state stream.

**Inputs:** stable ModeState sequence.

**File:** `modes/segments.py`.

**Implementation actions:**
- Increment segment ID when routing mode changes.
- Store start/end/duration/sample count.
- Preserve session boundaries.
- Never join segments across missing-data gaps automatically.

**Outputs:** MODE_SEGMENT_ID in labeled samples; optional segment table.

**Done:** every future window belongs to exactly one stable segment.

---

## Step 25 — Label all raw sessions

**Goal:** produce an inspectable dataset before training any anomaly model.

**Inputs:** raw sessions + config.

**File:** `training/02_label_modes.py`.

**Outputs:** `data/labeled/<session>.parquet` or CSV, depending chosen format.

**Implementation actions:**
- Run normalization, timebase, quality, derived signals, mode detector, persistence, segmentation.
- Preserve source session ID.
- Save config/version metadata.

**Validation:** labeled row count equals normalized row count.

**Done:** every healthy drive can be inspected with mode labels.

---

## Step 26 — Build mode coverage inventory

**Goal:** know whether there is enough data per mode.

**Inputs:** labeled sessions.

**Files:** `training/03_build_mode_inventory.py`.

**Output:** `data/inventory/mode_inventory.csv`.

**Columns:** vehicle, session, mode, total seconds, sample count, segment count, median segment duration, optional PID coverage.

**Done:** unsupported modes are identified before model training.

---

## Step 27 — Create manual mode-review plots

**Goal:** validate the rule detector visually against real driving.

**Inputs:** labeled sessions.

**Files:** add a plotting utility under training or scripts; output only under `outputs/plots/`.

**Plots:** speed, acceleration, RPM, load/throttle, coolant, colored mode background, confidence.

**Validation:** manually review representative idle, acceleration, cruise, decel, startup, stop-and-go.

**Done:** obvious systematic mislabels are fixed before freezing v1 mode rules.

---

## Step 28 — Tune mode thresholds from reviewed drives

**Goal:** replace guessed thresholds with target-vehicle evidence.

**Inputs:** review plots + labeled drives.

**Files:** `config/modes.yaml`.

**Implementation actions:**
- Adjust acceleration/deceleration bands.
- Adjust stopped tolerance.
- Adjust persistence duration.
- Document why each threshold changed.
- Re-run Steps 25-27 after every change.

**Output:** mode-detector config v1.

**Done:** representative drives are acceptably segmented.

---

## Step 29 — Freeze mode-detector v1 and write tests from real snippets

**Goal:** stop moving the routing target while anomaly models are built.

**Inputs:** reviewed labeled data.

**Files:** `tests/fixtures/mode_snippets/`, unit/integration mode tests.

**Implementation actions:**
- Extract small de-identified snippets for each state.
- Store expected mode intervals.
- Add regression tests.

**Done:** later refactors cannot silently change mode labels.

---

## Step 30 — Define per-mode window policy

**Goal:** choose windows that match mode duration.

**Inputs:** segment-duration statistics.

**Files:** `config/windows.yaml`, `docs/mode_taxonomy.md`.

**Implementation actions:**
- Do not default every mode to 30 seconds.
- Idle/cruise may use longer windows.
- Accel/decel need shorter/event-sized windows.
- Define stride/overlap policy.
- Define minimum samples and max gap.
- Define whether partial final windows are discarded.

**Output:** explicit window policy per mode.

**Done:** each policy is justified by observed segment durations.

---

## Step 31 — Implement the online ring buffer

**Goal:** support the same window construction on Pi.

**Inputs:** normalized labeled samples.

**File:** `features/buffer.py`.

**Implementation actions:**
- Keep bounded history by time.
- Reset/partition on session or hard connection gap.
- Expose samples for current stable segment.
- Avoid unbounded memory growth.

**Output:** reusable buffer object.

**Tests:** append, trim, reset, gap handling.

**Done:** longest configured window fits while memory stays bounded.

---

## Step 32 — Implement pure-mode window extraction

**Goal:** ensure a training/scoring window never mixes incompatible modes.

**Inputs:** one stable segment + window policy.

**File:** `features/windows.py`.

**Implementation actions:**
- Require one MODE_SEGMENT_ID.
- Require minimum mode confidence.
- Require data quality.
- Enforce duration/sample count.
- Reject windows crossing gaps.
- Assign WINDOW_ID deterministically.

**Output:** raw FeatureWindow candidates.

**Tests:** boundary-crossing window rejected.

**Done:** every accepted window is mode-pure.

---

## Step 33 — Define the feature schema

**Goal:** explicitly choose features before fitting models.

**Inputs:** available PIDs and derived signals.

**Files:** `config/models.yaml`, `docs/data_dictionary.md`.

**Initial candidate statistics:** mean, standard deviation, min, max, range, first-last delta, slope where meaningful.

**Implementation actions:**
- Start small.
- Avoid redundant features automatically added without review.
- Decide mode-specific sensor lists.
- Record required vs optional model features.

**Output:** versioned feature schema.

**Done:** exact feature names can be generated before any model is trained.

---

## Step 34 — Implement feature extraction

**Goal:** make training and runtime use identical feature code.

**Inputs:** accepted raw window.

**File:** `features/extract.py`.

**Implementation actions:**
- Compute configured statistics.
- Use stable feature naming.
- Handle nulls according to an explicit policy.
- Do not silently impute with global means unless that policy is validated.
- Return quality metadata with feature vector.

**Output:** feature row.

**Tests:** hand-calculated fixture.

**Done:** same input window produces byte-for-byte equivalent feature names/order offline and online.

---

## Step 35 — Build the full window dataset

**Goal:** create the modeling table.

**Inputs:** `data/labeled/*`.

**File:** `training/04_build_windows.py`.

**Outputs:** `data/windows/windows.parquet` plus summary CSV.

**Required metadata:** session, vehicle, mode, segment, times, sample count, confidence, feature-schema version.

**Done:** dataset can be regenerated from raw files.

---

## Step 36 — Create session-level train/calibration/test manifests

**Goal:** prevent leakage.

**Inputs:** window dataset and session metadata.

**File:** `training/05_make_splits.py`.

**Outputs:** `data/manifests/train.csv`, `calibration.csv`, `test.csv`.

**Implementation actions:**
- Split whole sessions.
- If multiple vehicles exist, decide whether evaluation is within-vehicle or cross-vehicle and document it.
- Keep test sessions untouched.
- Store random seed if randomized.

**Validation:** set intersections are empty.

**Done:** every window maps to exactly one split.

---

## Step 37 — Fit per-mode preprocessing/scalers

**Goal:** prevent one mode's scale from defining another mode's normality.

**Inputs:** training manifest + training windows.

**File:** `training/06_fit_scalers.py`.

**Outputs:** `models/<mode>/<version>/scaler.joblib`, feature list metadata.

**Implementation actions:**
- Fit only on training sessions.
- Remove/flag constant features using training data only.
- Persist exact ordered feature list.

**Done:** calibration/test data never influence scaler parameters.

---

## Step 38 — Train a simple baseline before an autoencoder

**Goal:** establish a lightweight reference model.

**Inputs:** scaled healthy training windows per mode.

**File:** `training/07_train_baselines.py`.

**Initial candidate:** Isolation Forest. Optionally compare robust covariance/one-class methods where sample size permits.

**Outputs:** model artifact + training metadata per mode.

**Why:** if a simple detector performs adequately, it is easier to debug and cheaper on Pi; a neural model should earn its complexity.

**Done:** every supported mode has at least one baseline model.

---

## Step 39 — Add an autoencoder only as a comparison candidate

**Goal:** test whether reconstruction modeling improves results.

**Inputs:** same split and feature schema as baseline.

**Files:** add a separate training module only when baseline pipeline is stable.

**Implementation actions:**
- Never change test set to favor the AE.
- Use a separate validation subset for training/early stopping; do not reuse threshold-calibration data for early stopping.
- Compare latency/memory and false-positive behavior.

**Output:** optional candidate artifact.

**Done:** AE is retained only if evaluation justifies it.

---

## Step 40 — Calibrate thresholds separately per mode

**Goal:** convert continuous scores into decisions.

**Inputs:** frozen model + held-out healthy calibration sessions for that mode.

**File:** `training/08_calibrate_thresholds.py`.

**Implementation actions:**
- Compute anomaly scores.
- Choose target healthy false-positive policy.
- Estimate threshold from calibration data only.
- Report confidence/uncertainty when calibration sample size is small.
- Never use one global threshold across modes unless evidence supports it.

**Output:** threshold + calibration summary in model metadata.

**Done:** each model bundle contains its own decision threshold.

---

## Step 41 — Evaluate untouched healthy test sessions

**Goal:** quantify nuisance-alert behavior.

**Inputs:** frozen model/scaler/threshold + test manifest.

**File:** `training/09_evaluate_healthy.py`.

**Metrics:** window-level FPR, anomalies/hour, anomalies/drive, score distribution by mode, unscored fraction.

**Output:** `outputs/evaluation/healthy_test_summary.csv`.

**Done:** test results are generated without fitting/tuning.

---

## Step 42 — Evaluate mode detector separately from anomaly detector

**Goal:** avoid blaming anomaly models for routing errors.

**Inputs:** manually reviewed mode intervals.

**Outputs:** mode confusion table, transition timing error, unknown/unscored rate.

**Files:** `docs/validation_protocol.md` and evaluation script.

**Done:** mode quality has its own acceptance criteria.

---

## Step 43 — Add synthetic anomaly sanity tests

**Goal:** verify the pipeline reacts to obvious perturbations.

**Inputs:** copies of healthy windows.

**Perturbations:** unrealistic sensor offsets, frozen sensor, abrupt drift, isolated spikes, cross-sensor inconsistency.

**Important:** do not report this as real fault-detection accuracy.

**Output:** sanity-test report.

**Done:** severe injected abnormalities move scores in the expected direction.

---

## Step 44 — Define model-bundle metadata and registry

**Goal:** make deployment deterministic.

**Inputs:** scaler, model, threshold, feature schema.

**Files:** `anomaly/registry.py`, `training/10_export_registry.py`.

**Per-mode metadata must include:** mode, version, training date, feature order, window policy version, scaler file, model file, threshold, score direction, train/cal/test session IDs or manifest hash, library versions.

**Output:** `models/registry.json`.

**Done:** runtime can load a model using only the detected mode and registry.

---

## Step 45 — Implement anomaly scorer

**Goal:** return one consistent result contract.

**Inputs:** FeatureWindow + ModelRegistry.

**File:** `anomaly/scorer.py`.

**Implementation actions:**
- Verify supported mode.
- Verify feature schema/version.
- Verify required features.
- Apply correct scaler/model.
- Compare score to correct threshold.
- Return UNSCORED with reason instead of throwing for expected unsupported conditions.

**Output:** AnomalyResult.

**Tests:** normal score, anomalous score, missing model, missing feature, low confidence.

**Done:** scorer never silently routes to a different mode's model.

---

## Step 46 — Add explanation/contributor output

**Goal:** make alerts debuggable without pretending to diagnose a component.

**Inputs:** scored feature vector.

**File:** `anomaly/explain.py`.

**Implementation actions:**
- For models that support interpretable feature contributions, report them.
- Otherwise report standardized feature deviations or reconstruction errors as diagnostic context.
- Label these as contributors, not root causes.

**Output:** TOP_CONTRIBUTORS.

**Done:** an alert can say which measurements/features were unusual.

---

## Step 47 — Merge adjacent anomalous windows into events

**Goal:** avoid flooding logs with one alert per overlapping window.

**Inputs:** AnomalyResult stream.

**File:** `anomaly/events.py`.

**Implementation actions:**
- Define event start/end.
- Merge nearby anomalous windows in same mode.
- Track peak score and contributing features.
- Close event after configurable normal gap or mode change.

**Output:** anomaly-event records.

**Done:** evaluation can report events/drive, not only windows.

---

## Step 48 — Implement offline full-drive replay

**Goal:** run the exact intended pipeline without a car.

**Inputs:** raw drive + frozen registry.

**File:** `scripts/replay_drive.py`, orchestrator in `pipeline.py`.

**Outputs:** labeled sample file, window/result file, event file.

**Validation:** no training code is imported by replay runtime.

**Done:** one command reproduces an end-to-end drive analysis.

---

## Step 49 — Implement Bluetooth OBD adapter inspection

**Goal:** verify hardware before live collection.

**Inputs:** paired adapter and running vehicle/ignition state.

**File:** `scripts/inspect_adapter.py`, `adapters/bluetooth_obd_source.py`.

**Implementation actions:**
- Connect through configured serial/RFCOMM device.
- Report adapter/connection status.
- Enumerate supported configured PIDs.
- Measure query latency.
- Do not assume all configured PIDs are supported.

**Output:** console/report of capability and timing.

**Done:** target vehicle's usable PID set is known.

---

## Step 50 — Implement live Bluetooth sample source

**Goal:** produce the same OBDSample contract as CSV replay.

**Input:** python-OBD/serial connection.

**File:** `bluetooth_obd_source.py`.

**Implementation actions:**
- Query only supported PIDs.
- Attach monotonic and wall timestamps.
- Track per-PID age.
- Handle null OBD responses.
- Keep acquisition logic separate from preprocessing.

**Output:** live OBDSample stream.

**Done:** CSV and Bluetooth sources can feed the same pipeline.

---

## Step 51 — Implement drive collection command

**Goal:** build the project's own healthy dataset.

**Input:** live source.

**File:** `scripts/collect_drive.py`.

**Outputs:** immutable raw session + metadata sidecar.

**Implementation actions:**
- Write incrementally so power loss does not erase the whole drive.
- Flush periodically.
- Record connection errors.
- Never run anomaly training inside collection.

**Done:** repeated road tests produce consistent raw artifacts.

---

## Step 52 — Implement reconnect/backoff behavior

**Goal:** survive temporary Bluetooth/adapter failures.

**Inputs:** live source errors.

**Files:** `bluetooth_obd_source.py`, `pipeline.py`.

**Implementation actions:**
- Close broken connection.
- Mark gap/quality state.
- Retry with bounded backoff.
- Reset buffers if gap invalidates windows.
- Never interpret disconnect as a vehicle anomaly.

**Done:** unplug/replug or temporary loss does not corrupt mode/anomaly state.

---

## Step 53 — Implement live Pi pipeline

**Goal:** run collection -> preprocessing -> mode -> window -> scoring continuously.

**File:** `scripts/run_pi.py`.

**Inputs:** runtime config + model registry + live source.

**Outputs:** JSONL/CSV structured results and events under `outputs/logs/` or configured persistent path.

**Implementation actions:**
- Keep memory bounded.
- Score only completed eligible windows.
- Log UNSCORED reasons.
- Never block acquisition on expensive reporting.

**Done:** road test produces timestamped mode and anomaly results.

---

## Step 54 — Benchmark on the actual Raspberry Pi

**Goal:** prove the runtime fits device limits.

**File:** `scripts/benchmark_pi.py`.

**Metrics:** CPU %, RSS memory, acquisition latency, preprocessing latency, scoring latency, log growth, missed query rate.

**Output:** `outputs/benchmarks/pi_benchmark.json`.

**Done:** runtime keeps up with measured acquisition rate with comfortable headroom.

---

## Step 55 — Add log rotation and storage limits

**Goal:** prevent filling the Pi filesystem.

**Inputs:** expected daily log volume.

**Files:** runtime config + deployment/logging setup.

**Implementation actions:**
- Define max file size/age/count.
- Separate raw collection from compact anomaly event logs.
- Document retention.

**Done:** unattended operation has bounded storage use.

---

## Step 56 — Install as a systemd service

**Goal:** start automatically after boot and recover from process failure.

**Files:** `deployment/obd-anomaly.service`, `deployment/install_pi.sh`.

**Implementation actions:**
- Run as non-root user where possible.
- Depend on Bluetooth/network only as actually required.
- Configure working directory and environment.
- Restart on failure with delay.
- Send logs to chosen destination.

**Done:** reboot -> service starts -> adapter reconnects -> pipeline resumes.

---

## Step 57 — Run boot/recovery tests

**Goal:** test failure modes before normal road use.

**Scenarios:** Pi reboot, adapter absent at boot, adapter appears later, ignition off/on, temporary Bluetooth loss, corrupted model registry, missing optional PID, low disk space.

**Output:** `docs/validation_protocol.md` checklist/results.

**Done:** expected failures become UNSCORED/retry states rather than crashes or false alerts.

---

## Step 58 — Define the real-fault data protocol

**Goal:** create evidence for actual fault detection.

**Files:** `docs/data_collection_protocol.md`, `docs/validation_protocol.md`.

**Record when available:** DTCs, technician diagnosis, repair performed, pre/post-repair drives, symptom timing, vehicle condition.

**Important:** do not intentionally create unsafe mechanical faults.

**Done:** real fault sessions can be labeled at event/session level.

---

## Step 59 — Evaluate real fault data

**Goal:** measure whether the system detects meaningful abnormalities.

**Inputs:** frozen model version + labeled fault sessions.

**Metrics:** event recall, precision, false alerts/hour, detection delay, mode at detection, pre/post-repair score shift.

**Output:** versioned fault evaluation report.

**Done:** project claims are limited to what this evidence supports.

---

## Step 60 — Decide whether the architecture needs a learned mode classifier

**Goal:** only add ML routing if deterministic routing is a demonstrated bottleneck.

**Inputs:** mode confusion/errors from Step 42.

**Candidate:** supervised classifier using speed, acceleration, RPM, load, throttle and short history.

**Acceptance rule:** learned router must improve reviewed mode accuracy without unacceptable Pi cost or loss of debuggability.

**Done:** either retain deterministic v1 or document evidence for classifier v2.

---

## Step 61 — Decide whether load/thermal submodels are justified

**Goal:** address hills/high load/cold operation without unnecessary model explosion.

**Inputs:** healthy false positives grouped by load and coolant/start context.

**Implementation decision:**
- If errors cluster strongly by context and enough data exists, split a mode into submodels.
- Otherwise keep context as features.

**Done:** submodels are data-driven, not speculative.

---

## Step 62 — Compare advanced anomaly models

**Goal:** improve detection only after the baseline is measurable.

**Candidates:** one-class methods, autoencoder, temporal autoencoder, lightweight sequence model, conditional model/mixture of experts.

**Inputs:** same immutable split manifests.

**Compare:** healthy FPR, real-fault recall when available, latency, memory, calibration stability, explanation quality.

**Done:** replacement model must beat baseline on agreed metrics, not merely training loss.

---

# 5. Mode Detector v1 Acceptance Matrix

Before anomaly training starts, the following must be manually reviewed:

| Scenario | Expected routing behavior |
|---|---|
| engine off, speed 0 | ENGINE_OFF, UNSCORED |
| engine just started | STARTUP_WARMUP, initially UNSCORED |
| warm engine, stopped | IDLE |
| speed increasing clearly | ACCELERATING |
| steady speed within tolerance | CRUISING |
| moderate negative acceleration | COASTING_DECEL |
| strong negative acceleration | STRONG_DECEL |
| noisy boundary crossing | stable prior mode until persistence requirement met |
| missing speed | UNKNOWN_TRANSITION / UNSCORED |
| Bluetooth gap | bad quality / UNSCORED, not anomaly |
| unsupported model mode | UNSCORED |
| low mode confidence | UNSCORED |

---

# 6. Minimum Dataset Before Trusting a Mode Model

Do not define a universal number here without inspecting actual window diversity. Instead enforce these gates:

1. multiple independent sessions, not one long drive;
2. multiple distinct segments for the mode;
3. enough duration to produce a meaningful calibration set and untouched test set;
4. representative operating conditions for the target use;
5. no known unresolved mechanical fault in "healthy" training sessions;
6. sufficient PID completeness for the chosen feature schema.

If a mode fails these gates, the registry must mark it unsupported.

---

# 7. Evaluation Rules

## 7.1 Mode detection metrics

- manually reviewed interval accuracy
- confusion matrix
- transition delay
- fraction UNKNOWN/UNSCORED
- mode-segment fragmentation

## 7.2 Healthy anomaly metrics

- false-positive windows / total windows
- anomaly events per hour
- anomaly events per drive
- false positives by mode
- false positives by load/thermal context
- unscored fraction

## 7.3 Fault metrics when real labels exist

- event recall
- precision
- detection delay
- pre/post-repair score comparison
- mode-specific detection behavior

## 7.4 Pi runtime metrics

- acquisition update rate
- PID staleness
- CPU
- memory
- score latency
- dropped/failed queries
- log growth

---

# 8. Research / Design Notes to Preserve

- Generic OBD PID support varies by vehicle; runtime must discover support instead of assuming all configured sensors exist.
- Bluetooth OBD adapters on Linux commonly appear through a serial/RFCOMM path; the exact connection procedure and channel can vary by adapter.
- Actual polling throughput depends on adapter, vehicle protocol, number of PIDs, ECU response time, and software; measure it on the target car rather than assuming a fixed sample rate.
- EPA MOVES uses operating-mode concepts based on vehicle speed and power-demand-related quantities. That is useful inspiration for context-aware behavior, but MOVES emissions bins should not be copied directly as anomaly classes.
- Generic speed deceleration alone does not establish that the driver pressed the brake pedal. Use STRONG_DECEL unless an actual brake signal is available.
- Isolation Forest is a sensible baseline because it provides an unsupervised anomaly score and is lightweight, but it is a baseline to evaluate, not a predetermined final answer.

Reference reading:
- python-OBD project/docs: https://github.com/brendan-w/python-OBD
- BlueZ RFCOMM documentation: https://github.com/bluez/bluez/wiki/rfcomm
- scikit-learn outlier detection / Isolation Forest: https://scikit-learn.org/stable/modules/outlier_detection.html
- EPA MOVES / Vehicle Specific Power: https://www.epa.gov/moves/what-vehicle-specific-power-vsp

---

# 9. Definition of Project Completion

The project is not "done" because a model trains.

Version 1 is complete when all of the following are true:

- a fresh Pi can be installed from documentation;
- the Pi connects to the target Bluetooth OBD adapter;
- supported PIDs are discovered and logged;
- raw sessions are timestamped and reproducible;
- mode labels are manually validated;
- windows never cross incompatible mode segments;
- train/calibration/test sessions are disjoint;
- every supported mode has a versioned model bundle and threshold;
- unsupported/uncertain states abstain;
- offline replay and live inference use the same preprocessing/feature/scoring code;
- healthy false-positive behavior is measured on untouched drives;
- Pi CPU/memory/latency are measured;
- reconnect/reboot/missing-PID behavior is tested;
- real-fault performance claims are made only when real labeled fault evidence exists;
- README and docs allow another developer to reproduce the system without the original author.
