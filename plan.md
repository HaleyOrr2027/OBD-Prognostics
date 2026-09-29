# Build Plan

The repository is intentionally built as small, testable stages.

## 01 Normalize input
Goal: one schema for CSV and live OBD.
Input: raw CSV or python-OBD samples.
Code: src/obd_anomaly/core.py normalize().
Output: canonical ENGINE_RPM, VEHICLE_SPEED, COOLANT_TEMPERATURE, THROTTLE_POSITION, etc.
Done: aliases test passes.

## 02 Construct time
Goal: elapsed seconds for derivatives and persistence.
Input priority: TIME_SEC, ENGINE_RUN_TIME, TIMESTAMP, otherwise row order.
Output: TIME_SEC.
Done: usable monotonic time exists.

## 03 Smooth speed
Goal: avoid differentiating raw speed jitter.
Input: VEHICLE_SPEED.
Config: speed_median_samples.
Output: SPEED_SMOOTH.
Done: downstream acceleration uses smoothed speed.

## 04 Derive acceleration
Input: SPEED_SMOOTH and TIME_SEC.
Output: ACCELERATION_MPS2.
Done: increasing speed is positive and decreasing speed negative.

## 05 Detect engine-off
Input: ENGINE_RPM.
Config: engine_on_rpm.
Output: ENGINE_OFF.
Done: engine-off data is never anomaly-scored.

## 06 Isolate startup
Input: detected engine start and elapsed time.
Config: startup_seconds.
Output: STARTUP_WARMUP.
Done: startup samples cannot contaminate steady-state models.

## 07 Classify raw motion
Input: speed and acceleration.
Outputs: IDLE, ACCELERATING, CRUISING, COASTING_DECEL, STRONG_DECEL.
Caveat: strong deceleration is not proof of braking.
Done: synthetic examples map correctly.

## 08 Add persistence
Goal: stop rapid mode flapping.
Input: raw mode stream.
Config: persistence_seconds.
Output: stable MODE.
Done: candidate mode must persist before switch.

## 09 Add confidence
Goal: abstain when context is uncertain.
Output: MODE_CONFIDENCE.
Done: low-confidence windows are rejected.

## 10 Segment modes
Goal: define contiguous mode events.
Output: MODE_SEGMENT.
Done: windows cannot cross a segment boundary.

## 11 Collect healthy sessions
Input: Raspberry Pi Bluetooth OBD.
Command: scripts/record_drive.py.
Output: data/raw/drive_TIMESTAMP.csv.
Record metadata separately: vehicle, cold/warm start, route, weather, DTCs, maintenance condition, unusual events.
Done: several independent sessions cover each intended mode.

## 12 Build pure-mode windows
Input: labeled session.
Code: windows().
Initial configurable lengths: idle 20 s, cruise 12 s, accel 5 s, coasting 5 s, strong decel 4 s.
Output: one row per stable single-mode window.
Done: no window contains two modes.

## 13 Build features
Input: each pure window.
Features: mean/std/min/max for available configured sensors.
Output: data/features/windows.csv.
Done: training and inference use the same summarize() function.

## 14 Split by whole session
Goal: prevent leakage.
Input: feature rows.
Output: disjoint train/calibration/test session IDs.
Done: one drive appears in exactly one split.

## 15 Fit per-mode scaler
Input: training rows for one mode only.
Output: models/MODE/scaler.joblib.
Done: calibration/test data never fit the scaler.

## 16 Fit per-mode baseline
Model: Isolation Forest.
Input: scaled healthy training windows.
Output: models/MODE/model.joblib.
Done: each adequately represented mode has its own model.

## 17 Calibrate threshold
Input: held-out healthy calibration sessions.
Method: configured anomaly-score quantile.
Output: threshold in models/MODE/metadata.json.
Done: thresholds are mode-specific.

## 18 Evaluate false positives
Input: untouched healthy test sessions.
Output: healthy_test_fpr in metadata.
Important: healthy-only testing does not measure fault recall.
Done: nuisance alert rate is known per mode.

## 19 Export registry
Output: models/registry.json.
Purpose: runtime selects model solely from detected mode.
Done: Pi never retrains during driving.

## 20 Offline replay
Command: scripts/replay_drive.py DRIVE.csv.
Input: raw recorded drive + frozen registry.
Output: outputs/replay/DRIVE_results.csv.
Done: exact inference path runs without the car.

## 21 Discover target-car PID support
Command: scripts/discover_obd.py.
Input: paired Bluetooth OBD adapter.
Output: supported configured PIDs.
Done: know which optional sensors the target vehicle exposes.

## 22 Validate modes in the real car
Goal: run collection/replay and compare mode labels with observed driving.
Done: idle/accel/cruise/decel transitions are plausible and stable before trusting anomaly scores.

## 23 Live inference
Command: scripts/run_pi.py (next deployment integration step).
Input: streaming OBD samples and frozen models.
Output: NORMAL / ANOMALOUS / UNSCORED events.
Done: only complete, confident, supported-mode windows are scored.

## 24 Real fault validation
Input: known-fault drives, DTCs, repair outcomes.
Metrics: event-level recall, precision, false positives, detection delay.
Done: claims about fault detection are supported by real labeled evidence.
Synthetic sensor changes are only sanity checks.

## Design rules
- Mode detection happens before anomaly detection.
- Rule/state-machine mode detection comes first because it is inspectable and needs no labeled mode dataset.
- Separate per-mode anomaly models come before a conditional neural model.
- Training is offline; Pi inference is frozen.
- Uncertain context is UNSCORED instead of guessed.
- Dataset splits are by drive/session.
- A future autoencoder should be compared against the baseline rather than assumed superior.
- Component diagnosis requires labeled fault evidence.
