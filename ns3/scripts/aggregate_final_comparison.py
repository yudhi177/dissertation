#!/usr/bin/env python3
import glob
import os
import re
import pandas as pd

RUNS_DIR = os.path.expanduser("~/dissertation/ns3/results/final_comparison/runs")
OUT_CSV  = os.path.expanduser("~/dissertation/ns3/results/final_comparison/summary/final_master_comparison_mean_std.csv")

METRICS = [
    "pdr_norm",
    "avgDelay_s",
    "throughput_bps",
    "avgLedgerTrust",
    "avgHandoverDelay_s",
    "avgBlockLatency_s",
]

pattern = re.compile(r"(?P<scen>baseline|secure|blockchain|full)_seed_(?P<seed>[0-9]+)\.csv$")

rows = []
for path in sorted(glob.glob(os.path.join(RUNS_DIR, "*_seed_*.csv"))):
    m = pattern.search(os.path.basename(path))
    if not m:
        continue
    scen = m.group("scen")
    seed = int(m.group("seed"))

    df = pd.read_csv(path)
    if df.empty:
        continue

    r = {"Scenario": scen, "seed": seed}
    for col in METRICS:
        if col in df.columns:
            r[col] = float(df.loc[0, col])
        else:
            r[col] = None  # baseline may not have blockchain metrics
    rows.append(r)

all_df = pd.DataFrame(rows)

keys = ["Scenario"]

nRuns = all_df.groupby(keys).size().reset_index(name="nRuns")
mean_df = all_df.groupby(keys)[METRICS].mean().reset_index()
std_df  = all_df.groupby(keys)[METRICS].std(ddof=1).fillna(0.0).reset_index()

mean_df = mean_df.rename(columns={c: f"{c}_mean" for c in METRICS})
std_df  = std_df.rename(columns={c: f"{c}_std" for c in METRICS})

out = nRuns.merge(mean_df, on=keys).merge(std_df, on=keys)

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
out.to_csv(OUT_CSV, index=False)

print(f"[OK] Wrote: {OUT_CSV}")
print(out.to_string(index=False))
