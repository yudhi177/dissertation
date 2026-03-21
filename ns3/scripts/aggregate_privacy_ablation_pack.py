import os, re, glob
import numpy as np
import pandas as pd

RUNS = os.path.expanduser("~/dissertation/ns3/results/privacy_ablation_pack/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/privacy_ablation_pack/summary")
os.makedirs(OUT, exist_ok=True)

pat = re.compile(r"^(FULL_NO_PRIVACY|FULL_PRIVACY)_seed(\d+)\.csv$")

rows=[]
for f in glob.glob(os.path.join(RUNS, "*.csv")):
    base = os.path.basename(f)
    m = pat.match(base)
    if not m:
        continue
    tag = m.group(1)
    seed = int(m.group(2))

    df = pd.read_csv(f)
    num = df.select_dtypes(include=[np.number]).mean(numeric_only=True).to_dict()
    row = {"baseline": tag, "seed": seed}
    row.update(num)
    rows.append(row)

raw = pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT, "raw.csv"), index=False)

if raw.empty:
    raise SystemExit(f"[ERR] No runs found in {RUNS}")

def ci95(x):
    x = pd.to_numeric(x, errors="coerce").dropna()
    if len(x) <= 1:
        return 0.0
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x))

metrics = [c for c in raw.columns if c not in ("baseline","seed")]
grp = raw.groupby("baseline", as_index=False)

agg = grp[metrics].agg(["mean","std","count"])
agg.columns = ["%s_%s" % (m, s) for (m, s) in agg.columns]
agg = agg.reset_index().rename(columns={"index":"baseline"})  # safety

# add ci95 per metric
grp2 = raw.groupby("baseline")
for m in metrics:
    agg[f"{m}_ci95"] = grp2[m].apply(ci95).values

agg.to_csv(os.path.join(OUT, "summary_ci95.csv"), index=False)
print("[OK] wrote", os.path.join(OUT, "summary_ci95.csv"))
