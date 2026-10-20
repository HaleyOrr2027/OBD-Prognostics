
# OBD Data Dictionary

This file explains the variables used in 'schemas.py'.

---

## 1. OBDSample
**Raw data collected from the OBD reader or CSV files.**

### Collection Info
- 'SESSION_ID' (str) - ID for the driving session
- 'TIMESTAMP_UTC' (datetime) - Date and time of the reading
- 'MONOTONIC_SEC' (float) - Clock time used to measure intervals, in seconds
- 'VEHICLE_ID' (str) - Vehicle ID
- 'SOURCE' (str) - CSV or Bluetooth
- 'CONNECTION_OK' (bool) - Whether the connection is working

### Engine Readings
- 'ENGINE_RPM' - Engine speed (RPM)
- 'ENGINE_LOAD' - Engine load (%)
- 'THROTTLE_POSITION' - Throttle position (%)
- 'ENGINE_RUN_TIME' - Time since startup (source units)

### Vehicle and Air Readings
- 'VEHICLE_SPEED' - Vehicle speed (source units)
- 'COOLANT_TEMPERATURE' - Coolant temperature (source units)
- 'MAF' - Mass airflow (source units)
- 'INTAKE_PRESSURE' - Intake pressure (source units)
- 'INTAKE_TEMPERATURE' - Intake air temperature (source units)

### Fuel Readings
- 'SHORT_FUEL_TRIM_1' - Short-term fuel correction (%)
- 'LONG_FUEL_TRIM_1' - Long-term fuel correction (%)

All sensor readings are 'float | None'. They default to 'None' when a reading is unavailable.

Raw sensor units depend on the data source and need to be identified before conversion.

---

## 2. NormalizedSample
**Stores the raw sample, data quality information, and calculated values.**

### Original Data
- 'RAW_SAMPLE' (OBDSample) - Original OBD reading

### Timing
- 'SAMPLE_DT_SEC' - Time between samples (seconds)
- 'PID_AGE_SEC' - Dictionary of how old each sensor reading is (seconds)
- 'SECONDS_SINCE_ENGINE_START' - Seconds since startup

### Data Quality
- 'PID_VALIDITY' - Dictionary of valid/invalid sensor readings
- 'DATA_QUALITY_OK' - True if the sample passes quality checks
- 'QUALITY_FLAGS' - List of problems with the data

### Calculated Values
- 'SPEED_SMOOTH_KMH' - Smoothed speed (km/h)
- 'ACCELERATION_MPS2' - Acceleration (m/s²)
- 'RPM_DELTA_PER_SEC' - RPM change per second
- 'LOAD_DELTA_PER_SEC' - Engine load change (% points/s)
- 'THROTTLE_DELTA_PER_SEC' - Throttle change (% points/s)

Calculated numeric values can be 'None' when unavailable.

The preprocessing code calculates these values later. The storage of converted sensor readings still needs to be finalized.

---

## 3. ModeState
**Stores what the vehicle is currently doing.**

### Engine Conditions
- 'ENGINE_STATE' - OFF / RUNNING / UNKNOWN
- 'THERMAL_STATE' - STARTUP_WARMUP / WARM_OR_UNKNOWN
- 'LOAD_STATE' - LOW / MEDIUM / HIGH / UNKNOWN

### Driving Mode
- 'MOTION_STATE_RAW' - Initial driving mode
- 'MOTION_STATE' - Stable driving mode

Possible modes:
- IDLE
- ACCELERATING
- CRUISING
- COASTING_DECEL
- STRONG_DECEL
- UNKNOWN_TRANSITION

### Other Information
- 'MODE_CONFIDENCE' - Confidence score from 0 to 1
- 'MODE_REASON' - List of reasons for the classification
- 'MODE_SEGMENT_ID' - ID for the continuous driving mode segment, or None

---

## 4. FeatureWindow
**Stores information collected over a period of time.**

### Identification
- 'WINDOW_ID' - Window ID
- 'SESSION_ID' - Driving session ID
- 'MODE_SEGMENT_ID' - Driving mode segment ID
- 'MOTION_STATE' - Mode being analyzed

### Time and Samples
- 'WINDOW_START_SEC' - Start time (seconds)
- 'WINDOW_END_SEC' - End time (seconds)
- 'DURATION_SEC' - Window length (seconds)
- 'SAMPLE_COUNT' - Number of samples

### Analysis
- 'MIN_MODE_CONFIDENCE' - Lowest mode confidence in the window
- 'QUALITY_FLAGS' - List of data quality problems
- 'FEATURES' - Dictionary of calculated statistics

Examples of features:
- Average RPM
- RPM standard deviation
- Average engine load

---

## 5. AnomalyResult
**Stores the result from the anomaly detection model.**

### Result Information
- 'RESULT_TIME_UTC' - Time of the result
- 'WINDOW_ID' - Window being analyzed
- 'MOTION_STATE' - Driving mode used
- 'MODE_CONFIDENCE' - Confidence in that mode

### Model Output
- 'STATUS' - NORMAL / ANOMALOUS / UNSCORED
- 'ANOMALY_SCORE' - Score from the model
- 'THRESHOLD' - Threshold used for the decision
- 'MODEL_VERSION' - Model version

### Explanation
- 'TOP_CONTRIBUTORS' - List of features contributing to the result
- 'REASON' - Explanation, especially for UNSCORED results

### Status Meanings
- **NORMAL:** Behavior matches what the model considers normal.
- **ANOMALOUS:** Behavior is unusual compared to the model's normal data.
- **UNSCORED:** The program could not make a decision.

An anomaly does not necessarily mean something is broken.

---

## Notes

- 'str' = text
- 'float' = number that can have decimals
- 'int' = whole number
- 'bool' = True or False
- 'datetime' = date and time
- 'list' = collection of items
- 'dict' = collection of key-value pairs
- 'None' = no value available

The classes store information. Other Python files will perform the actual calculations and processing.
