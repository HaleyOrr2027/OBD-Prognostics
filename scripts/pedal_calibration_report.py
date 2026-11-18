"""Review carOBD pedal ranges without treating zero speed as proof of pedal release.

Usage: python scripts/pedal_calibration_report.py drive3
Works on locally downloaded data/raw/carOBD/<session>.csv.
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
def main():
    session = sys.argv[1] if len(sys.argv) > 1 else "drive3"
    path = ROOT / "data" / "raw" / "carOBD" / f"{session}.csv"
    if not path.is_file():
        raise SystemExit(f"Missing {path}. Run python scripts/fetch_carobd.py first.")
    data = pd.read_csv(path, index_col=False, skipinitialspace=True)
    cols = {"D": "PEDAL_D ()", "E": "PEDAL_E ()"}
    required = [*cols.values(), "VEHICLE_SPEED ()", "ENGINE_RPM ()", "ENGINE_RUN_TINE ()"]
    missing = [c for c in required if c not in data]
    if missing:
        raise SystemExit(f"Missing columns: {missing}")
    frame = data[required].apply(pd.to_numeric, errors="coerce")
    # Avoid counting duplicate timestamps as independent observations.
    unique = frame.groupby("ENGINE_RUN_TINE ()", sort=True).median(numeric_only=True)
    stationary = unique[(unique["VEHICLE_SPEED ()"] <= 0.01) &
                        (unique["ENGINE_RPM ()"] > 600)]
    print(f"Session: {session}")
    print(f"Raw rows: {len(frame)}; distinct timestamps: {len(unique)}")
    print(f"Stationary, engine-running timestamps: {len(stationary)}")
    for name, column in cols.items():
        print(f"\nPedal channel {name}")
        print("All timestamps:")
        print(unique[column].describe(percentiles=[.05, .25, .5, .75, .95]).to_string())
        print("Stationary / engine running (not proof that pedal is released):")
        print(stationary[column].describe(percentiles=[.05, .25, .5, .75, .95]).to_string())
    print("\nNOTE: Minimum repeated readings are resting-offset candidates,")
    print("not independently verified foot-off-pedal ground truth.")
if __name__ == "__main__":
    main()
