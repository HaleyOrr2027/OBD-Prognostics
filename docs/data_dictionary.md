# Data Dictionary

Fill this document while completing Steps 02-09 in plan.md.

Document every canonical field, type, unit, nullable status, source, and meaning.

## Canonical PIDs (config/pids.yaml)

| Field | Unit | Required | Notes |
|---|---|---|---|
| ENGINE_RPM | rpm | yes | |
| VEHICLE_SPEED | km/h | yes | carOBD reports whole km/h |
| ENGINE_LOAD | % | recommended | |
| THROTTLE_POSITION | % | recommended | Relative throttle; reads 0 on a closed pedal. carOBD's absolute `THROTTLE` never drops below ~15.7% and is passed through as `RAW_THROTTLE`. |
| COOLANT_TEMPERATURE | °C | recommended | |
| INTAKE_PRESSURE | kPa | optional | |
| INTAKE_TEMPERATURE | °C | optional | |
| SHORT_FUEL_TRIM_1, LONG_FUEL_TRIM_1 | % | optional | |
| ENGINE_RUN_TIME | s | optional | carOBD header is misspelled `ENGINE_RUN_TINE`; used as the clock when `MONOTONIC_SEC` is absent |

Unrecognized raw columns are kept with a `RAW_` prefix so they are never used as model features by accident.

## Columns added by preprocessing

| Field | Type | Meaning |
|---|---|---|
| ELAPSED_SEC | float | Seconds since the first sample of the session |
| SAMPLE_DT_SEC | float | Interval to the previous row. carOBD logs several rows per timestamp, so 0 is common. |
| TIME_SOURCE | str | MONOTONIC_SEC or ENGINE_RUN_TIME |
| TIME_FLAGS | str | DUPLICATE_TIME, CLOCK_REVERSAL, TIME_GAP, MISSING_TIME |
| TIME_BLOCK | int | Contiguous block; increments after any gap or reversal |
| QUALITY_FLAGS | str | TIME_FLAGS plus MISSING_<PID> and CONNECTION_LOST |
| DATA_QUALITY_OK | bool | False if a required PID is missing, a time gap or reversal occurred, or the connection was lost |
| SPEED_SMOOTH_KMH | float, km/h | Trailing rolling median of speed |
| ACCELERATION_MPS2 | float, m/s² | Trailing rate of smoothed speed; null at the start of a time block |
| RPM_DELTA_PER_SEC, LOAD_DELTA_PER_SEC, THROTTLE_DELTA_PER_SEC | float | Trailing rates; null if the source PID is unavailable |
| SECONDS_SINCE_ENGINE_START | float, s | Null while the engine is off or its age is unknown |

Mode-state columns are documented in `docs/mode_taxonomy.md`.

## carOBD reading note

carOBD data rows end with a trailing comma, so each row has one more field than the header. Reading with plain `pd.read_csv` shifts every column name one place left without raising an error. `adapters/csv_source.read_raw_csv` uses `index_col=False` to prevent this.
