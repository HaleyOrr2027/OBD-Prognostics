import pandas as pd
from obd_anomaly.core import normalize,ModeDetector
def test_aliases():
    d=normalize(pd.DataFrame({"RPM":[800],"SPEED":[0]}));assert "ENGINE_RPM" in d and "VEHICLE_SPEED" in d
def test_idle():
    cfg={"mode":{"engine_on_rpm":100,"stopped_speed_kmh":0.5,"accel_threshold_mps2":0.15,"decel_threshold_mps2":-0.15,"strong_decel_threshold_mps2":-1,"startup_seconds":0,"persistence_seconds":0}}
    d=ModeDetector(cfg); mode,_,_=d.update({"TIME_SEC":0,"ENGINE_RPM":800,"SPEED_SMOOTH":0,"ACCELERATION_MPS2":0}); assert mode=="IDLE"
