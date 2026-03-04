#!/usr/bin/env python3
import glob
import os
import re
import pandas as pd

RUNS_DIR = os.path.expanduser("~/dissertation/ns3/results/sensitivity/trust_threshold/runs")
OUT_CSV  = os.path.expanduser("~/dissertation/ns3/results/sensitivity/trust_threshold/summary/trust_threshold_mean_std.csv")

METRICS = [
    "pdr_norm",
    "avgDelay_s",
    "throughput_bps",
    "avgLedgerTrust",
    "handoverCount",
    "avgHandoverDelay_s",
    "fastAuthCount",
    "fullAuthCount",
    "rejectCount",
]

pattern = re.compile(r"fast_(?P<fast>[0-9.]+)_min_(?P<mn>[0-9.]+)_seed_(?P<seed>[0-9]+)\.csv$")

rows = []
for path in sorted(glob.glob(os.path.join(RUNS_DIR, "fast_*_min_*_seed_*.csv"))):
    m = pattern.search(os.path.basename(path))
    if not m:
        continue
    fast = float(m.group("fast"))
    mn = float(m.group("mn"))
    seed = int(m.group("seed"))

    df = pd.read_csv(path)
    if df.empty:
        continue

    r = {"trustFastThresh": fast, "trustMinThresh": mn, "seed": seed}
    for col in METRICS:
        if col not in df.columns:
            raise SystemExit(f"Missing column '{col}' in {path}")
        r[col] = float(df.loc[0, col])
    rows.append(r)

if not rows:
    raise SystemExit(f"No run CSV files found in {RUNS_DIR}")

all_df = pd.DataFrame(rows)

# group by (fast,min)
keys = ["trustFastThresh", "trustMinThresh"]

nRuns = all_df.groupby(keys).size().reset_index(name="nRuns")

mean_df = all_df.groupby(keys)[METRICS].mean().reset_index()
std_df  = all_df.groupby(keys)[METRICS].std(ddof=1).fillna(0.0).reset_index()

mean_df = mean_df.rename(columns={c: f"{c}_mean" for c in METRICS})
std_df  = std_df.rename(columns={c: f"{c}_std" for c in METRICS})

out = nRuns.merge(mean_df, on=keys).merge(std_df, on=keys)
out = out.sort_values(keys).reset_index(drop=True)

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
out.to_csv(OUT_CSV, index=False)

print(f"[OK] Wrote: {OUT_CSV}")
print(out.to_string(index=False))
