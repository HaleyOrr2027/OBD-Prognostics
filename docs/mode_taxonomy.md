# Mode Taxonomy

Mode detector v1, covering plan.md Steps 12–25. Thresholds live in `config/modes.yaml`; this page records what each state means and why each value was chosen.

## Axes

The detector keeps each axis as its own column, so they are never collapsed into one label.

| Column | Values | Source |
|---|---|---|
| `ENGINE_STATE` | OFF, RUNNING, UNKNOWN | RPM ≥ `running_rpm_min` → RUNNING. A lost connection is UNKNOWN, never OFF. |
| `THERMAL_STATE` | STARTUP_WARMUP, WARM_OR_UNKNOWN | First `startup_guard_sec` after an OFF→RUNNING transition. Coolant temperature is recorded but not used as a threshold. |
| `MOTION_STATE_RAW` | see routing states below | Rule result for each sample before persistence |
| `MOTION_STATE` | see routing states below | Stable state after persistence; this is what selects a model |
| `LOAD_STATE` | LOW, MEDIUM, HIGH, UNKNOWN | ENGINE_LOAD bins; context only in v1 |
| `MODE_CONFIDENCE` | 0–1 | 0 for unroutable states; reduced near a threshold or while a transition is pending |
| `MODE_REASON` | `;`-separated flags | STARTUP_GUARD, ENGINE_OFF, BAD_QUALITY, ENGINE_UNKNOWN, NO_ACCELERATION_YET, NEAR_THRESHOLD, PENDING_TRANSITION |
| `MODE_SEGMENT_ID` | `<session>-NNNN` | Increments on every stable-state change, time gap, or session boundary |

## Routing states (`MOTION_STATE`)

Rules are applied in priority order:

| State | Rule | Scored by a model? |
|---|---|---|
| UNKNOWN_TRANSITION | bad data quality, unknown engine state, or no acceleration value yet | no |
| ENGINE_OFF | engine OFF | no |
| STARTUP_WARMUP | inside the startup guard | no (v1 abstains) |
| IDLE | engine running, smoothed speed ≤ `stopped_speed_kmh`, RPM ≤ `idle_rpm_max` | yes |
| ACCELERATING | moving, acceleration ≥ `accel_mps2` | yes |
| CRUISING | moving, abs(acceleration) < `accel_mps2` | yes |
| COASTING_DECEL | moving, acceleration ≤ `decel_mps2` | yes |
| STRONG_DECEL | moving, acceleration ≤ `strong_decel_mps2` | yes |

STRONG_DECEL is deliberately not called braking: there is no brake-pedal signal.

## Signals

- **Speed smoothing:** trailing rolling median over `speed_smooth_sec`.
- **Acceleration:** smoothed speed change over the trailing `accel_span_sec`, divided by actual elapsed time, in m/s².

Both use only current and past samples, so the live Pi and offline replay give identical labels. Neither crosses a time gap longer than `max_gap_sec`.

## Threshold choices (v1)

| Setting | Value | Why |
|---|---|---|
| `speed_smooth_sec` | 1.0 | Best on the drive12 review window; longer windows added lag |
| `accel_span_sec` | 2.0 | Best on drive12; 3.0 s missed short bursts |
| `accel_mps2` / `decel_mps2` | ±0.15 | Matches the earlier notebook threshold of 0.6 km/h/s; 0.15 and 0.20 scored identically |
| `strong_decel_mps2` | −1.2 | **Untuned.** The scoring vocabulary does not separate coasting from strong deceleration. The drive3 hard stop at 747–750 s (42 → 4 km/h in about 3 s) is caught correctly. |
| `dwell_sec` | 0.0 | See the open decision below |
| `startup_guard_sec` | 30 | Conservative default from plan.md Step 17. Not yet checked against warm-up data. |

Tuning used **drive12 seconds 1480–1780 only**. drive3 seconds 600–900 is the held-out check (see `docs/validation_protocol.md`).

## Window policy (Step 30)

Policy: `config/windows.yaml`. Evidence: `python scripts/window_policy_report.py` (about 1 minute), which labels all 129 carOBD sessions, cuts windows, and writes `outputs/evaluation/window_policy_report.csv` and `window_policy_decision.csv`.

### Sampling rate sets the floor

carOBD logs about 2 rows per second, but its clock (`ENGINE_RUN_TIME`) only advances about every 2 s. The median gap between distinct timestamps is 2.0 s in every dataset group (drive, idle, live, long, ufpe). A window therefore needs about 6 s to contain 3 distinct readings, the minimum for mean, standard deviation, and slope features. This is a partial Step 11 measurement, and the Pi's real rate may be different.

### Rules for every mode

| Setting | Value | Why |
|---|---|---|
| `min_distinct_times` | 3 | Fewest readings that support mean, standard deviation, and slope |
| `max_internal_gap_sec` | 3.0 | 1.5x the normal 2 s spacing; also checked at the window edges, so a window with data missing at its start or end is rejected |
| `discard_partial_final` | true | A window that would run past the end of its segment is dropped, never padded |
| `min_mode_confidence` | 0.5 | Matches `confidence.min_for_scoring` in modes.yaml |
| Stride | Fixed grid from each segment's start | Makes WINDOW_IDs deterministic |

### Per-mode lengths

Segment durations are measured across all 129 sessions. They are shown at `dwell_sec` 0 (current) and 1.

| Mode | Segment median / p75 / p90 (dwell 0) | Same at dwell 1 | Window / stride | Why |
|---|---|---|---|---|
| IDLE | 11 / 29 / 69 s | 16 / 34 / 76 s | 20 / 10 s | Idle is stable, so a longer window gives about 10 readings. It sits between the median and p75. |
| CRUISING | 0 / 2 / 6 s | 6 / 13 / 22 s | 8 / 4 s | 4 readings; between the median and p75 at dwell 1 |
| ACCELERATING | 0 / 3 / 7 s | 6 / 11 / 15 s | 6 / 2 s | Event-sized; the shortest length that holds 3 readings |
| COASTING_DECEL | 0 / 2 / 6 s | 4 / 8 / 12 s | 6 / 2 s | Same reasoning as ACCELERATING |
| STRONG_DECEL | 0 / 0 / 2 s | 0 / 2 / 4 s | 4 / 2 s | **Unsupported in v1.** Hard stops last only a few seconds, giving 0 windows at dwell 0 and 20 windows from 16 sessions at dwell 1. That fails the plan.md Section 6 data gates. |

## Decision for Haley and Rijul: hold time (`dwell_sec`)

A hold time stops modes from flickering, but it also swallows the short, real speed-ups and slow-downs these drives are full of. The report puts both sides in one table:

| `dwell_sec` | IDLE | CRUISING | ACCELERATING | COASTING_DECEL | STRONG_DECEL | drive12 exact / ±2 s | drive3 exact / ±2 s |
|---|---|---|---|---|---|---|---|
| 0 (current) | 3891 (107) | 619 (78) | 1948 (82) | 1511 (81) | 0 (0) | 79.7% / 98.0% | 68.8% / 95.0% |
| 1 | 3915 (109) | 4414 (82) | 3743 (82) | 2774 (82) | 20 (16) | 66.0% / 83.3% | 64.1% / 79.4% |
| 2 | 3915 (109) | 5163 (82) | 3680 (82) | 2772 (82) | 20 (16) | 65.0% / 81.0% | 62.8% / 77.1% |
| 3 | 4016 (110) | 6013 (82) | 4945 (82) | 3705 (82) | 34 (25) | 56.0% / 67.0% | 61.5% / 69.4% |

Cells are accepted windows, with the number of independent sessions in brackets. Windows overlap, so the session count is the better measure of how much independent data there is. The dwell value was chosen on drive12 before any drive3 numbers existed; the drive3 column is shown for this decision only.

What the table shows:

- **Every supported mode has data from 78–82 sessions at any hold time.** With event-sized windows, Step 30 does not force a hold time.
- **A 1 s hold mainly helps CRUISING:** 619 → 4414 windows, while ACCELERATING and COASTING_DECEL roughly double. It costs 4.7 points of exact accuracy on drive3 and 15.6 points within ±2 s.
- **Holds longer than 1 s add little data** and keep lowering accuracy.

**Proposed:** keep `dwell_sec: 0` for v1. Revisit if the Step 36 session split leaves CRUISING calibration or test sets too thin (about 619 windows across 78 sessions), or once the Pi's own sampling rate is measured.

Threshold hysteresis (a lower exit threshold than entry) was also tried. It cut flicker from 12 to 10 changes per minute at a 1-point accuracy cost, so it was not adopted.

## Known weakness

On long steady stretches, each 1 km/h step in the reported speed shows up as a brief ±0.14 m/s² acceleration. That chops CRUISING into short ACCELERATING or COASTING_DECEL pieces. In the drive3 confusion matrix, this accounts for most of the steady-labeled seconds that were missed.
