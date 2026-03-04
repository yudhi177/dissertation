import os, re
import pandas as pd
import numpy as np

idx_path = os.path.expanduser("~/dissertation/results_publishable/baselines_pack/runs_index.csv")
outdir   = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare")
os.makedirs(outdir, exist_ok=True)

df = pd.read_csv(idx_path, header=None)
# columns (based on your runs_index format):
# baseline,nveh,speed,seed,csv,events,bc_line,priv_line
df.columns = ["baseline","nveh","speed","seed","csv","events","bc_line","priv_line"]

bc_re = re.compile(r"queries=(\d+).*updates=(\d+).*cacheHits=(\d+).*cacheMisses=(\d+).*hitRate=([0-9.]+).*avgQms=([0-9.]+).*avgUms=([0-9.]+)")
rows=[]
for _,r in df.iterrows():
    m = bc_re.search(str(r["bc_line"]))
    if not m:
        continue
    q,u,h,miss,hit,avgQ,avgU = map(float, m.groups())
    total = q*avgQ + u*avgU
    rows.append({
        "baseline": r["baseline"],
        "nveh": int(r["nveh"]),
        "speed": int(r["speed"]),
        "seed": int(r["seed"]),
        "queries": q,
        "updates": u,
        "cacheHits": h,
        "cacheMisses": miss,
        "hitRate": hit,
        "avgQms": avgQ,
        "avgUms": avgU,
        "totalOverheadMs": total
    })

raw = pd.DataFrame(rows)
raw.to_csv(os.path.join(outdir,"raw_bc_overhead.csv"), index=False)

def ci95(x):
    x = pd.to_numeric(x, errors="coerce").dropna()
    if len(x) <= 1: return 0.0
    return 1.96*x.std(ddof=1)/np.sqrt(len(x))

metrics = ["queries","updates","hitRate","avgQms","avgUms","totalOverheadMs"]
agg = raw.groupby(["baseline","nveh","speed"])[metrics].agg(["mean","std","count"]).reset_index()
agg.columns = ["_".join(c).strip("_") for c in agg.columns]

for m in metrics:
    agg[f"{m}_ci95"] = raw.groupby(["baseline","nveh","speed"])[m].apply(ci95).values

agg.to_csv(os.path.join(outdir,"summary_ci95.csv"), index=False)
print("[OK] wrote", os.path.join(outdir,"summary_ci95.csv"))
