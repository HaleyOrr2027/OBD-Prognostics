from pathlib import Path
import sys, json
import joblib, numpy as np, pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from obd_anomaly.core import load_config, preprocess, label_modes, windows

def split_sessions(names,seed):
    a=np.array(sorted(set(names))); np.random.default_rng(seed).shuffle(a)
    if len(a)<3: raise ValueError("Need at least 3 independent healthy sessions")
    n=max(1,int(len(a)*0.6)); m=max(1,int(len(a)*0.2))
    if n+m>=len(a): n=len(a)-2; m=1
    return set(a[:n]),set(a[n:n+m]),set(a[n+m:])

def main():
    cfg=load_config(); labeled=Path("data/labeled"); features_dir=Path("data/features")
    labeled.mkdir(parents=True,exist_ok=True); features_dir.mkdir(parents=True,exist_ok=True)
    all_features=[]
    for path in sorted(Path("data/raw").glob("*.csv")):
        df=preprocess(pd.read_csv(path),cfg); df["SESSION"]=path.stem
        df=label_modes(df,cfg); df.to_csv(labeled/path.name,index=False)
        f=windows(df,cfg)
        if not f.empty: all_features.append(f)
    if not all_features: raise SystemExit("No complete stable-mode windows were produced.")
    data=pd.concat(all_features,ignore_index=True); data.to_csv(features_dir/"windows.csv",index=False)
    root=Path("models"); root.mkdir(exist_ok=True); registry={"version":1,"modes":{}}
    meta_cols={"SESSION","MODE","MODE_SEGMENT","WINDOW_START","WINDOW_END","MODE_CONFIDENCE"}
    for mode,g in data.groupby("MODE"):
        if len(g)<int(cfg["model"]["minimum_windows"]): print("Skipping",mode,"insufficient windows"); continue
        tr,ca,te=split_sessions(g["SESSION"].astype(str),int(cfg["model"]["random_state"]))
        train=g[g.SESSION.astype(str).isin(tr)]; cal=g[g.SESSION.astype(str).isin(ca)]; test=g[g.SESSION.astype(str).isin(te)]
        feats=[c for c in g.columns if c not in meta_cols and pd.api.types.is_numeric_dtype(g[c]) and train[c].notna().all() and train[c].std(ddof=0)>0]
        if not feats: continue
        scaler=StandardScaler().fit(train[feats]); model=IsolationForest(n_estimators=int(cfg["model"]["n_estimators"]),random_state=int(cfg["model"]["random_state"]),n_jobs=-1).fit(scaler.transform(train[feats]))
        cal_scores=-model.decision_function(scaler.transform(cal[feats])); threshold=float(np.quantile(cal_scores,float(cfg["model"]["calibration_quantile"])))
        test_scores=-model.decision_function(scaler.transform(test[feats])); fpr=float(np.mean(test_scores>threshold))
        d=root/mode.lower(); d.mkdir(parents=True,exist_ok=True); joblib.dump(model,d/"model.joblib"); joblib.dump(scaler,d/"scaler.joblib")
        (d/"metadata.json").write_text(json.dumps({"mode":mode,"features":feats,"threshold":threshold,"train_sessions":sorted(tr),"calibration_sessions":sorted(ca),"test_sessions":sorted(te),"healthy_test_fpr":fpr},indent=2))
        registry["modes"][mode]=mode.lower()
    (root/"registry.json").write_text(json.dumps(registry,indent=2))
    print("Trained modes:",", ".join(registry["modes"]) or "none")

if __name__=="__main__": main()
