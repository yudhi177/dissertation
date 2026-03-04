import os, re, glob
import pandas as pd
import numpy as np

RUNS = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_density_pack/runs")
OUTD = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_density_pack/summary")
os.makedirs(OUTD, exist_ok=True)

pat = re.compile(r"^(BC_TRUST|BC_ALWAYS_QUERY|FULL)_n(\d+)_seed(\d+)\.log$")
bc_pat = re.compile(r"\[BC\]\s+queries=(\d+)\s+updates=(\d+)\s+cacheHits=(\d+)\s+cacheMisses=(\d+)\s+hitRate=([0-9.]+)\s+avgQms=([0-9.]+)\s+avgUms=([0-9.]+)")

rows=[]
for logf in glob.glob(os.path.join(RUNS, "*.log")):
    base=os.path.basename(logf)
    m=pat.match(base)
    if not m:
        continue
    baseline=m.group(1)
    nveh=int(m.group(2))
    seed=int(m.group(3))

    txt=open(logf,"r",errors="ignore").read()
    mm=bc_pat.search(txt)
    if not mm:
        continue

    queries=int(mm.group(1))
    updates=int(mm.group(2))
    hits=int(mm.group(3))
    misses=int(mm.group(4))
    hitRate=float(mm.group(5))
    avgQ=float(mm.group(6))
    avgU=float(mm.group(7))
    totalOverheadMs = queries*avgQ + updates*avgU

    rows.append({
        "baseline": baseline, "nVehicles": nveh, "seed": seed,
        "queries": queries, "updates": updates,
        "cacheHits": hits, "cacheMisses": misses,
        "hitRate": hitRate,
        "avgQms": avgQ, "avgUms": avgU,
        "totalOverheadMs": totalOverheadMs
    })

raw=pd.DataFrame(rows)
raw.to_csv(os.path.join(OUTD,"raw.csv"), index=False)

if raw.empty:
    raise SystemExit(f"[ERR] No parsed logs found in {RUNS}")

def ci95(x):
    x=pd.to_numeric(x, errors="coerce").dropna()
    if len(x)<=1: return 0.0
    return 1.96*x.std(ddof=1)/np.sqrt(len(x))

metrics=[c for c in raw.columns if c not in ("baseline","nVehicles","seed")]
grp = raw.groupby(["baseline","nVehicles"])

mean = grp[metrics].mean().add_suffix("_mean")
std  = grp[metrics].std(ddof=1).add_suffix("_std")
cnt  = grp[metrics].count().add_suffix("_count")
ci   = grp[metrics].apply(lambda df: df.apply(ci95)).add_suffix("_ci95")

out = pd.concat([mean,std,cnt,ci], axis=1).reset_index()
out.to_csv(os.path.join(OUTD,"summary_ci95.csv"), index=False)
print("[OK] wrote", os.path.join(OUTD,"summary_ci95.csv"))
