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

## Open decision: persistence vs. accuracy

carOBD reports speed in whole km/h, roughly once per second, and real speed-ups and slow-downs in these drives last only 3–5 s. A dwell time suppresses flicker, but it also swallows short real events. Results across all 13 `drive*` sessions:

| `dwell_sec` | Median moving-segment length | Moving segments ≥ 5 s | drive12 exact / ±2 s | drive3 exact / ±2 s |
|---|---|---|---|---|
| 0.0 (current) | 0.0 s | 14% | 79.7% / 98.0% | 68.8% / 95.0% |
| 1.0 | 5.0 s | 53% | 66.0% / 83.3% | 64.1% / 79.4% |
| 2.0 | 5.0 s | 59% | 65.0% / 81.0% | 62.8% / 77.1% |
| 3.0 | 9.0 s | 74% | 56.0% / 67.0% | 61.5% / 69.4% |

The dwell value was chosen on drive12 before these drive3 numbers were computed. The drive3 column is here for the team decision only.

The Step 30 window policy needs to settle this. Pure-mode windows need segments long enough to fill a window. Options:

1. Raise `dwell_sec` and accept the lower accuracy.
2. Keep accurate per-sample labels and let windows take the majority mode.
3. Re-check once Step 11 measures the real Pi sampling rate, which may differ from carOBD.

Threshold hysteresis (a lower exit threshold than entry) was also tried. It cut flicker from 12 to 10 changes per minute at a 1-point accuracy cost, so it was not adopted.

## Known weakness

On long steady stretches, each 1 km/h step in the reported speed shows up as a brief ±0.14 m/s² acceleration. That chops CRUISING into short ACCELERATING or COASTING_DECEL pieces. In the drive3 confusion matrix, this accounts for most of the steady-labeled seconds that were missed.
