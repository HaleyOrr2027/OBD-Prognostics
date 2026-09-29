from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from obd_anomaly.core import load_config
def val(r):
    if r is None or r.is_null():return None
    try:return float(r.value.magnitude)
    except:return None
def main():
    import obd
    p=argparse.ArgumentParser();p.add_argument("--seconds",type=float,default=600);a=p.parse_args();c=load_config()["obd"]
    conn=obd.OBD(c.get("port"),baudrate=c.get("baudrate"),timeout=float(c["timeout_seconds"]),fast=True)
    names=["RPM","SPEED","ENGINE_LOAD","COOLANT_TEMP","THROTTLE_POS","MAF","INTAKE_PRESSURE"]; names=[n for n in names if conn.supports(obd.commands[n])]
    rows=[];start=time.monotonic()
    while time.monotonic()-start<a.seconds:
        row={"TIMESTAMP":datetime.now(timezone.utc).isoformat(),"TIME_SEC":time.monotonic()-start}
        for n in names:row[n]=val(conn.query(obd.commands[n]))
        rows.append(row)
    conn.close(); path=Path("data/raw")/("drive_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".csv");path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
    print(path)
if __name__=="__main__":main()
