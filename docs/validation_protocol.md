# Validation Protocol

Fill this during Steps 27-29 and 41-59 in plan.md.

Separate validation of mode detection, healthy anomaly false positives, Pi runtime behavior, and real-fault detection.

## Mode detection (Steps 27-28, 42)

### Reference labels

Hand labels live in `data/reference_labels/<session>_<start>-<end>.csv` with columns `start_s,end_s,label,note`. Times are session seconds (`ELAPSED_SEC`; for carOBD this equals `ENGINE_RUN_TIME`). Labels use plain driving vocabulary:

| Label | Meaning when read off the speed trace |
|---|---|
| idle | stopped, engine running |
| accel | speed clearly rising |
| decel | speed clearly falling |
| steady | speed roughly holding |

Rules:

- Label from the raw speed trace **before** looking at detector output for that window.
- Tune thresholds on one window. Score every other window once, after tuning is frozen.
- Record in the file's notes who labeled it and how it was reviewed.

### Scoring

```
python scripts/score_modes.py <session> data/reference_labels/<file>.csv
```

At each whole second, the detector's answer is the state of the latest sample at or before that second, which is what the live system would report. COASTING_DECEL and STRONG_DECEL both count as decel. ENGINE_OFF, STARTUP_WARMUP, and UNKNOWN_TRANSITION count as unscored and always as misses.

Reported metrics (plan.md 7.1): exact agreement, agreement within ±2 s, per-label recall, confusion matrix, unscored fraction, median transition delay, and segments per minute (fragmentation). Results are saved to `outputs/evaluation/mode_score_<file>.json`.

### Visual review

```
python scripts/plot_mode_review.py <session> --start <s> --end <s> --reference <labels.csv>
```

This draws the detected and reference strips above speed, acceleration (with thresholds), RPM, throttle, coolant, and confidence.

### Results, mode detector v1 (`pids-v1_modes-v1`)

| Window | Role | Exact | Within ±2 s | idle / accel / decel / steady recall | Median delay |
|---|---|---|---|---|---|
| drive12 1480–1780 s | tuning | 79.7% | 98.0% | 100 / 80 / 73 / 61% | 1.0 s |
| drive3 600–900 s | held out | 68.8% | 95.0% | 100 / 74 / 60 / 65% | 1.5 s |

**Label provenance:** both files were drafted with Claude from the raw traces. Human review status is tracked in `data/reference_labels/README.md`.

- **drive12:** labeled from the speed trace, September 29.
- **drive3:** drafted from the speed and throttle trace without running the detector, then machine-checked: every interval's speed change matches its label, with no contradictions. Three intervals are gentle changes near the threshold (742–747 decel at −0.7 km/h/s, 807–813 and 855–863 accel at +0.7–0.9 km/h/s). The 748–756 interval is a real hard stop (42 → 4 km/h over about 3 s in the raw rows), not a logging glitch.

**Comparison with the earlier notebook detector:** it scored 89.3% on drive12 and 83.1% on drive3. That version used centered smoothing, which looks a few seconds into the future. The live Pi cannot do that, so v1 uses trailing filters only, and the gap between the two sets of numbers is the cost of running in real time.

**Not yet validated:**

- A drive with independent ground truth: a passenger writing down timestamped events while the Pi logs.
- The STRONG_DECEL threshold.
- The startup guard length.
- Any vehicle other than the carOBD car.
