# Data Collection Protocol

Fill this during Steps 04, 11, 51 and 58 in plan.md.

Define session metadata, healthy-drive collection procedure, vehicle/adapter metadata, annotation rules, and real-fault evidence rules.

## Ground-truth test drive (mode detector validation)

The existing reference labels were read off the speed trace, so they test the detector against the same signal it uses. This drive gives independent ground truth: a passenger writes down what the car is doing while the Pi logs, and the detector is scored against those notes.

It is also one run toward the connection test plan. A drive that logs end to end without a gap counts as one successful session.

### People

| Role | Job |
|---|---|
| Driver | Drives the route and says out loud what they are about to do ("pulling away", "slowing for the light") |
| Passenger | Runs a phone stopwatch and writes one line per change in what the car is doing |
| Pi operator | Can be the passenger. Starts and stops logging, then checks the file afterward. |

### Before the drive

1. Start Pi logging with the engine **off**.
2. Start the engine. If possible, start cold (parked for 3+ hours) so the startup guard is also exercised.
3. Wait until RPM is steady at idle, at least 20 s.
4. **Sync rev:** the passenger starts the stopwatch and says "sync". The driver gives one quick rev to about 2,000 RPM in Park or Neutral. The script finds this rev in the RPM log and lines up the two clocks.
5. Idle at least 60 s more before moving. This gives a full IDLE window.

### Route (about 10–15 minutes)

Cover each mode several times. These are the minimums:

| What to do | How many | Why |
|---|---|---|
| Pull away from a stop | 5+ | ACCELERATING |
| Hold a steady speed for 20+ s, at two different speeds | 3+ each | CRUISING |
| Gentle slow-down, coasting off the gas | 4+ | COASTING_DECEL |
| Firmer stop (safely) | 2+ | STRONG_DECEL, which has almost no data so far |
| Stopped 30+ s with the engine running | 3+ | IDLE |

Drive normally and safely. Don't stage anything unsafe to hit a count.

### Passenger's event log

Write one line each time the car changes what it's doing, using stopwatch time:

```
time,event,note
0:00,sync,rev in Park
0:45,pull away,
0:56,steady,about 40 km/h
1:30,slowing,light ahead
1:38,stopped,
2:15,pull away,
...
12:40,end,parked
```

Allowed events: `sync`, `pull away`, `steady`, `slowing`, `braking`, `stopped`, `end`. Start with `sync` and finish with `end`. Writing a second or two late is fine, because scoring reports agreement within ±2 s alongside exact agreement. A blank template is at `data/reference_labels/event_log_template.csv`.

### After the drive

1. Stop logging after the engine is off.
2. Copy the Pi log to `data/raw/<vehicle_id>/<session_id>.csv`. Copy the event log to `data/reference_labels/<session_id>_event_log.csv`.
3. Fill in the session metadata (next section) as `data/raw/<vehicle_id>/<session_id>.json`.
4. Convert and score:

```
python scripts/event_log_to_labels.py <session_id> data/reference_labels/<session_id>_event_log.csv
python scripts/score_modes.py <session_id> data/reference_labels/<session_id>_events.csv
python scripts/plot_mode_review.py <session_id> --reference data/reference_labels/<session_id>_events.csv
```

### Logging check (counts toward the connection test plan)

The session passes if all of these hold:
- logging ran from engine-off before the start to engine-off at the end;
- no gap between samples is longer than `max_gap_sec` (5 s);
- `DATA_QUALITY_OK` is true for at least 99% of samples;
- ENGINE_RPM, VEHICLE_SPEED and COOLANT_TEMPERATURE are present for the whole drive.

Record the result in the session metadata.

## Session metadata (Step 04)

One JSON sidecar per raw session, next to the log file:

```json
{
  "session_id": "veh01_20261030_a",
  "vehicle_id": "veh01",
  "date": "2026-10-30",
  "route_label": "town loop",
  "start": "cold",
  "known_dtcs": [],
  "recent_maintenance": "",
  "weather": "dry, 12 C",
  "adapter": "ELM327 Bluetooth",
  "logger_commit": "<git commit of the Pi code>",
  "ground_truth": "passenger event log",
  "logging_check": {"passed": true, "max_gap_sec": 1.1, "quality_ok_pct": 99.8},
  "notes": ""
}
```

Privacy rules:
- `vehicle_id` is a code, not a plate number or VIN.
- No names, no addresses, and no GPS.
- `route_label` stays generic ("town loop", "highway"), never a street address.
