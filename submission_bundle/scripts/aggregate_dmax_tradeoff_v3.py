import os, re, glob
import pandas as pd
import numpy as np

RUNS = os.path.expanduser("~/dissertation/ns3/results/dmax_tradeoff/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/dmax_tradeoff/summary")
os.makedirs(OUT, exist_ok=True)

pat = re.compile(r"DMAX_(\d+)_seed(\d+)")
stale_pat = re.compile(r"\[STALE\].*maxAgeMs=(\d+).*staleChecks=(\d+).*staleMismatch=(\d+).*mismatchRate=([0-9.]+)")

rows=[]
for f in glob.glob(os.path.join(RUNS, "DMAX_*_seed*.csv")):
    base=os.path.basename(f)
    m=pat.search(base)
    if not m:
        continue
    dmax=int(m.group(1)); seed=int(m.group(2))

    df=pd.read_csv(f)
    num=df.select_dtypes(include=[np.number]).mean(numeric_only=True).to_dict()

    log=os.path.join(RUNS, f"DMAX_{dmax}_seed{seed}.log")
    mismatchRate=np.nan; staleChecks=np.nan; staleMismatch=np.nan
    if os.path.exists(log):
        t=open(log,"r",errors="ignore").read()
        mm=stale_pat.search(t)
        if mm:
            mismatchRate=float(mm.group(4))
            staleChecks=float(mm.group(2))
            staleMismatch=float(mm.group(3))

    row={"trustMaxAgeMs":dmax,"seed":seed,
         "staleMismatchRate":mismatchRate,
         "staleChecks":staleChecks,
         "staleMismatch":staleMismatch}
    row.update(num)
    rows.append(row)

raw=pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT,"raw.csv"),index=False)

if raw.empty:
    print("[ERR] No runs found in", RUNS)
    raise SystemExit(1)

def ci95(series):
    s=pd.to_numeric(series,errors="coerce").dropna()
    if len(s)<=1: return 0.0
    return 1.96*s.std(ddof=1)/np.sqrt(len(s))

grp = raw.groupby("trustMaxAgeMs")

mean = grp.mean(numeric_only=True)
std  = grp.std(numeric_only=True, ddof=1)
cnt  = grp.count()

out = mean.add_suffix("_mean")
out = out.join(std.add_suffix("_std"))
out = out.join(cnt.add_suffix("_count"))

# ci95 for each numeric metric
for col in mean.columns:
    out[col + "_ci95"] = grp[col].apply(ci95)

out = out.reset_index()
out.to_csv(os.path.join(OUT,"summary_ci95.csv"),index=False)
print("[OK] wrote", os.path.join(OUT,"summary_ci95.csv"))
