import glob, os, re
import pandas as pd
import numpy as np

RUNS = os.path.expanduser("~/dissertation/ns3/results/trust_sensitivity_sweep/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/trust_sensitivity_sweep/summary")
os.makedirs(OUT, exist_ok=True)

rows = []
pat = re.compile(r"^(S\d+_[A-Z]+)_(.+)_(.+)_seed(\d+)\.csv$")

for f in glob.glob(os.path.join(RUNS, "*.csv")):
    base = os.path.basename(f)
    m = pat.match(base)
    if not m:
        continue
    sweep, key, val, seed = m.group(1), m.group(2), m.group(3), int(m.group(4))

    df = pd.read_csv(f)
    # If multi-row, average numeric columns; if single-row, same effect.
    num = df.select_dtypes(include=[np.number])
    if num.shape[0] == 0 or num.shape[1] == 0:
        continue
    means = num.mean(axis=0, numeric_only=True).to_dict()

    row = {"sweep": sweep, "param": key, "value": float(val), "seed": seed}
    row.update(means)
    rows.append(row)

raw = pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT, "raw_long.csv"), index=False)

def ci95(x: pd.Series):
    x = x.dropna().astype(float)
    n = len(x)
    if n <= 1:
        return 0.0
    return 1.96 * x.std(ddof=1) / np.sqrt(n)

group_cols = ["sweep", "param", "value"]
metrics = [c for c in raw.columns if c not in group_cols + ["seed"]]

agg = raw.groupby(group_cols)[metrics].agg(["mean", "std", "count"])
# flatten
agg.columns = ["_".join(c) for c in agg.columns]
agg = agg.reset_index()

# add ci95 per metric
for m in metrics:
    agg[f"{m}_ci95"] = raw.groupby(group_cols)[m].apply(ci95).values

agg.to_csv(os.path.join(OUT, "summary_ci95.csv"), index=False)
print("[OK] wrote", os.path.join(OUT, "raw_long.csv"))
print("[OK] wrote", os.path.join(OUT, "summary_ci95.csv"))
print("metrics:", metrics[:12], "...")
