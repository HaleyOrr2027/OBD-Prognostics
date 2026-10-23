"""Turn a passenger's timestamped event log into reference labels for scoring.

The passenger runs a stopwatch during a logged drive and writes one line per
change in what the car is doing (docs/data_collection_protocol.md):

    time,event,note
    0:00,sync,engine rev while parked
    0:20,pull away,
    0:31,steady,about 40 on Main St
    0:58,slowing,light ahead
    1:06,stopped,

Each event starts a new interval that lasts until the next event. Events map to
the scoring vocabulary: pull away / speeding up -> accel, steady -> steady,
slowing / braking -> decel, stopped -> idle. "sync" and "end" mark time only.

The stopwatch and the logger clock start at different moments. The protocol
asks for a short rev while parked as the first event ("sync"), and this script
finds that rev in the logged RPM to line the two clocks up. --offset overrides
it with a known number of seconds instead.

Usage:
    python scripts/event_log_to_labels.py <session> <event_log.csv> [--offset SEC]

Writes data/reference_labels/<session>_events.csv, which score_modes.py reads:
    python scripts/score_modes.py <session> data/reference_labels/<session>_events.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
import _paths  # noqa: E402
from obd_anomaly.config import load_config  # noqa: E402
from obd_anomaly.pipeline import label_session  # noqa: E402

EVENT_LABELS = {
    "pull away": "accel", "pulling away": "accel", "speeding up": "accel", "accelerating": "accel",
    "steady": "steady", "cruising": "steady", "holding speed": "steady",
    "slowing": "decel", "slowing down": "decel", "braking": "decel", "coasting": "decel",
    "stopped": "idle", "stop": "idle", "idle": "idle",
}
MARKERS = {"sync", "end"}
SYNC_RPM_RISE = 600.0     # rev must rise at least this far above the parked RPM
SYNC_SEARCH_SEC = 600.0   # look for the rev in the first 10 minutes of the log


def parse_clock(text: str) -> float:
    """'1:06' -> 66.0, '1:02:03' -> 3723.0, '45' -> 45.0."""
    seconds = 0.0
    for part in str(text).strip().split(":"):
        seconds = seconds * 60 + float(part)
    return seconds


def read_event_log(path: str | Path) -> pd.DataFrame:
    log = pd.read_csv(path, dtype=str).fillna("")
    log["t"] = log["time"].map(parse_clock)
    log["event"] = log["event"].str.strip().str.lower()
    unknown = sorted(set(log["event"]) - set(EVENT_LABELS) - MARKERS)
    if unknown:
        raise SystemExit(f"Unknown event(s) {unknown}. Use one of: {sorted(set(EVENT_LABELS) | MARKERS)}")
    if not log["t"].is_monotonic_increasing:
        raise SystemExit("Event times must be in order.")
    return log


def find_sync_rev(labeled: pd.DataFrame) -> float:
    """Session time of the first parked rev: RPM jumps well above its parked level at 0 km/h."""
    early = labeled[(labeled["ELAPSED_SEC"] <= SYNC_SEARCH_SEC) & (labeled["VEHICLE_SPEED"] <= 1)]
    running = early[early["ENGINE_RPM"] > 300]
    if running.empty:
        raise SystemExit("No parked, running period found to search for the sync rev; pass --offset instead.")
    baseline = running["ENGINE_RPM"].median()
    revs = running[running["ENGINE_RPM"] >= baseline + SYNC_RPM_RISE]
    if revs.empty:
        raise SystemExit("No sync rev found in the RPM data; pass --offset instead.")
    return float(revs["ELAPSED_SEC"].iloc[0])


def to_reference_labels(log: pd.DataFrame, offset: float) -> pd.DataFrame:
    """Convert events to start_s,end_s,label,note intervals in session seconds."""
    rows = []
    for i, event in log.reset_index(drop=True).iterrows():
        if event["event"] in MARKERS:
            continue
        if i + 1 >= len(log):
            raise SystemExit("The last line must be an 'end' event so the final interval has an end time.")
        start = round(event["t"] + offset)
        end = round(log.iloc[i + 1]["t"] + offset) - 1
        if end >= start:
            rows.append({"start_s": start, "end_s": end, "label": EVENT_LABELS[event["event"]],
                         "note": f"{event['event']}: {event.get('note', '')}".strip(": ")})
    return pd.DataFrame(rows, columns=["start_s", "end_s", "label", "note"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session")
    parser.add_argument("event_log")
    parser.add_argument("--offset", type=float, help="seconds to add to stopwatch times (skips the sync search)")
    args = parser.parse_args()

    config = load_config()
    log = read_event_log(args.event_log)

    if args.offset is not None:
        offset = args.offset
        how = "given"
    else:
        sync = log[log["event"] == "sync"]
        if sync.empty:
            raise SystemExit("The event log has no 'sync' line; add one or pass --offset.")
        sessions = _paths.raw_sessions(config.path("data", "raw"))
        if args.session not in sessions:
            raise SystemExit(f"Session '{args.session}' not found under data/raw/")
        rev_at = find_sync_rev(label_session(sessions[args.session], config))
        offset = rev_at - float(sync["t"].iloc[0])
        how = f"sync rev found at {rev_at:.1f} s in the log"

    labels = to_reference_labels(log, offset)
    out = config.path("data", "reference_labels", f"{args.session}_events.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    labels.to_csv(out, index=False)
    print(f"Offset {offset:+.1f} s ({how}); {len(labels)} intervals -> {out.relative_to(config.root)}")
    print(f"Score it with: python scripts/score_modes.py {args.session} {out.relative_to(config.root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
