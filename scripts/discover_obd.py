from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from obd_anomaly.core import load_config
def main():
    import obd
    c=load_config()["obd"]; conn=obd.OBD(c.get("port"),baudrate=c.get("baudrate"),timeout=float(c["timeout_seconds"]),fast=True)
    print("connected:",conn.is_connected())
    for name in ["RPM","SPEED","ENGINE_LOAD","COOLANT_TEMP","THROTTLE_POS","MAF","INTAKE_PRESSURE"]:
        if conn.supports(obd.commands[name]): print(name)
    conn.close()
if __name__=="__main__":main()
