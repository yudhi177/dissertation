import os, re, glob
import numpy as np
import pandas as pd

RUNS = os.path.expanduser("~/dissertation/ns3/results/baseline_pack/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/baseline_pack/summary")
os.makedirs(OUT, exist_ok=True)

pat = re.compile(r"^(PKI_ONLY|TRUST_ONLY|BC_TRUST|BC_ALWAYS_QUERY|FULL)_seed(\d+)\.csv$")

rows = []
for f in glob.glob(os.path.join(RUNS, "*.csv")):
    base = os.path.basename(f)
    m = pat.match(base)
    if not m:
        continue
    baseline = m.group(1)
    seed = int(m.group(2))

    df = pd.read_csv(f)
    num = df.select_dtypes(include=[np.number]).mean(numeric_only=True).to_dict()
    row = {"baseline": baseline, "seed": seed}
    row.update(num)
    rows.append(row)

raw = pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT, "raw.csv"), index=False)

if raw.empty:
    raise SystemExit(f"[ERR] No run CSVs found in {RUNS}")

def ci95(s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) <= 1:
        return 0.0
    return 1.96 * s.std(ddof=1) / np.sqrt(len(s))

metrics = [c for c in raw.columns if c not in ("baseline", "seed")]
grp = raw.groupby("baseline")

mean = grp[metrics].mean(numeric_only=True).add_suffix("_mean")
std  = grp[metrics].std(numeric_only=True, ddof=1).add_suffix("_std")
cnt  = grp[metrics].count().add_suffix("_count")
ci   = grp[metrics].agg(ci95).add_suffix("_ci95")

out = pd.concat([mean, std, cnt, ci], axis=1).reset_index()
out.to_csv(os.path.join(OUT, "summary_ci95.csv"), index=False)

print("[OK] wrote", os.path.join(OUT, "summary_ci95.csv"))
