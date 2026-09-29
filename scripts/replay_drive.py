from pathlib import Path
import argparse,sys,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from obd_anomaly.core import load_config,preprocess,label_modes,windows,Registry
def main():
    p=argparse.ArgumentParser(); p.add_argument("csv"); a=p.parse_args(); cfg=load_config()
    df=preprocess(pd.read_csv(a.csv),cfg); df["SESSION"]=Path(a.csv).stem; df=label_modes(df,cfg); feats=windows(df,cfg); reg=Registry().load()
    results=[reg.score(str(r["MODE"]),r) | {"window_start":r["WINDOW_START"],"window_end":r["WINDOW_END"]} for r in feats.to_dict("records")]
    out=Path("outputs/replay"); out.mkdir(parents=True,exist_ok=True); pd.DataFrame(results).to_csv(out/(Path(a.csv).stem+"_results.csv"),index=False)
    print(pd.DataFrame(results).to_string(index=False) if results else "No scorable windows.")
if __name__=="__main__":main()
