# Accelerator request estimation (v1)

This is an estimate of **accelerator pedal action**, not a complete statement of the
driver's intentions. Do not infer brake use, requested speed, or a mechanical fault.

## Inputs
- Direct: carOBD `PEDAL_D ()` and `PEDAL_E ()`, normalized to
  `ACCELERATOR_PEDAL_POSITION_D/E`.
- Fallback: `COMMANDED_THROTTLE_ACTUATOR`, then `THROTTLE_POSITION`.
  These are proxies for ECU/engine behavior, **not direct pedal intent**.
- The detector does **not** read RPM or acceleration when estimating a request:
  those measure the response, which could be abnormal.

## Output columns
- `DRIVER_REQUEST`: ACCELERATE_REQUEST, MAINTAIN_REQUEST,
  RELEASE_ACCELERATOR, NO_ACCELERATOR_REQUEST, UNKNOWN_REQUEST.
- `DRIVER_REQUEST_SOURCE`: PEDAL, THROTTLE_PROXY, NONE.
- `DRIVER_REQUEST_CONFIDENCE`: heuristic evidence grade, not calibrated probability.
- `DRIVER_REQUEST_REASON`: reason for label or abstention.
- `PEDAL_DELTA_PERCENT`: median signed pedal-channel change (percentage points)
  between the current and previous distinct timestamps, or missing if unavailable.

## Rules
A >2 percentage-point increase -> ACCELERATE_REQUEST; a >2 point reduction ->
RELEASE_ACCELERATOR. Stable low direct pedal (<=4% without a known baseline; or within configured source-specific baseline tolerance) -> NO_ACCELERATOR_REQUEST;
other stable input -> MAINTAIN_REQUEST. Two pedal channels need consistent
movement direction (their raw values need not match). Contradiction -> UNKNOWN.
The first sample, samples following >3 s gaps, and missing inputs abstain.
When direct pedal is absent, a throttle-based proxy is lower-confidence and
cannot safely establish brake or full driver intent.

## Run
```bash
python -m pytest tests/unit/test_driver_intent.py -v
python scripts/fetch_carobd.py
python training/02_label_modes.py drive3
```
Inspect `data/labeled/drive3.csv` for the five columns.
Raw drive data is not committed.

## Limitations / validation still required
- Thresholds are preliminary and must be calibrated on actual carOBD sessions.
- Different pedal channels may have distinct scaling, update rates and offset.
- Throttle may be ECU-controlled and cannot stand in for pedal action reliably.
- carOBD has pedal columns, but other vehicles may not expose these PIDs.
- No ground-truth driver-request labels or measured test accuracy yet.
- No request/response fault classification in this PR.

## First carOBD calibration review (drive3)
The upstream `drive3.csv` was inspected, including raw sensor headers and all 2,926 rows (793 distinct engine-time readings). Sensor D repeatedly bottoms out at **16.078432%**, and E at **31.764706%**. Among stationary running samples, both medians equal those values. These are candidate resting offsets, NOT independently verified foot-off-pedal truth.

To avoid making these offsets universal, `config/runtime.yaml` records the carOBD-specific baseline and a provisional **0.8 percentage-point** resting tolerance. `pipeline.py` applies it only when `VEHICLE_ID == 'carOBD'`. Other data sources keep the uncalibrated rules. This affects stable low-input classification only; increase and decrease thresholds remain 2 percentage points pending labeled validation.

Reproduce the raw-data summary locally with:
```bash
python scripts/pedal_calibration_report.py drive3
python training/02_label_modes.py drive3
python -m pytest tests/unit -v
```
Check the change in `NO_ACCELERATOR_REQUEST` labels after regenerating `data/labeled/drive3.csv`.

**Still needed:** ground-truth pedal-release observations and multi-session stability checks. Zero vehicle speed alone cannot prove that the driver wasn't pressing the accelerator.
