import os, re, glob
import pandas as pd
import numpy as np

RUNS = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare/summary")
os.makedirs(OUT, exist_ok=True)

pat = re.compile(r"^(BC_TRUST|BC_ALWAYS_QUERY|FULL)_spd(\d+)_seed(\d+)\.csv$")

rows=[]
for f in glob.glob(os.path.join(RUNS,"*.csv")):
    base=os.path.basename(f)
    m=pat.match(base)
    if not m: 
        continue
    baseline=m.group(1)
    speed=int(m.group(2))
    seed=int(m.group(3))
    df=pd.read_csv(f)
    num=df.select_dtypes(include=[np.number]).mean(numeric_only=True).to_dict()
    row={"baseline":baseline,"speed":speed,"seed":seed}
    row.update(num)
    rows.append(row)

raw=pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT,"raw.csv"),index=False)

def ci95(x):
    x=pd.to_numeric(x,errors="coerce").dropna()
    if len(x)<=1: return 0.0
    return 1.96*x.std(ddof=1)/np.sqrt(len(x))

if raw.empty:
    print("[ERR] No runs found in", RUNS)
    raise SystemExit(1)

metrics=[c for c in raw.columns if c not in ("baseline","speed","seed")]
grp=raw.groupby(["baseline","speed"],as_index=False)

agg = grp[metrics].agg(["mean","std","count"])
agg.columns=["_".join(c).strip("_") for c in agg.columns]
agg=agg.reset_index().rename(columns={"index":"row"})

# add ci95
for m in metrics:
    agg[m+"_ci95"]=grp[m].apply(ci95).values

agg.to_csv(os.path.join(OUT,"summary_ci95.csv"),index=False)
print("[OK] wrote", os.path.join(OUT,"summary_ci95.csv"))
