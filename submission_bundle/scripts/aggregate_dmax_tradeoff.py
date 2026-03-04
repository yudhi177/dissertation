import os, re, glob
import pandas as pd
import numpy as np

RUNS = os.path.expanduser("~/dissertation/ns3/results/dmax_tradeoff/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/dmax_tradeoff/summary")
os.makedirs(OUT, exist_ok=True)

pat = re.compile(r"DMAX_(\d+)_seed(\d+)")
stale_pat = re.compile(r"\[STALE\].*maxAgeMs=(\d+).*staleChecks=(\d+).*staleMismatch=(\d+).*mismatchRate=([0-9.]+)")

rows=[]
for f in glob.glob(os.path.join(RUNS,"DMAX_*_seed*.csv")):
    base=os.path.basename(f)
    m=pat.search(base)
    if not m: 
        continue
    dmax=int(m.group(1)); seed=int(m.group(2))
    df=pd.read_csv(f)
    num=df.select_dtypes(include=[np.number]).mean(numeric_only=True).to_dict()

    # log parse for mismatchRate
    log=os.path.join(RUNS,f"DMAX_{dmax}_seed{seed}.log")
    mismatchRate=None; staleChecks=None
    if os.path.exists(log):
        txt=open(log,"r",errors="ignore").read()
        mm=stale_pat.search(txt)
        if mm:
            mismatchRate=float(mm.group(4))
            staleChecks=int(mm.group(2))

    row={"trustMaxAgeMs":dmax,"seed":seed,"staleMismatchRate":mismatchRate,"staleChecks":staleChecks}
    row.update(num)
    rows.append(row)

raw=pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT,"raw.csv"),index=False)

def ci95(x):
    x=pd.to_numeric(x,errors="coerce").dropna()
    if len(x)<=1: return 0.0
    return 1.96*x.std(ddof=1)/np.sqrt(len(x))

metrics=[c for c in raw.columns if c not in ("trustMaxAgeMs","seed")]
agg=raw.groupby("trustMaxAgeMs")[metrics].agg(["mean","std","count"])
agg.columns=["_".join(c) for c in agg.columns]
agg=agg.reset_index()
for m in metrics:
    agg[f"{m}_ci95"]=raw.groupby("trustMaxAgeMs")[m].apply(ci95).values

agg.to_csv(os.path.join(OUT,"summary_ci95.csv"),index=False)
print("[OK] wrote",os.path.join(OUT,"summary_ci95.csv"))
