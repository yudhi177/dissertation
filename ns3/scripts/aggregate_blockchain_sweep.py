#!/usr/bin/env python3
import glob
import os
import re
import pandas as pd

RUNS_DIR = os.path.expanduser("~/dissertation/ns3/results/sensitivity/blockchain/runs")
OUT_CSV  = os.path.expanduser("~/dissertation/ns3/results/sensitivity/blockchain/summary/blockchain_sweep_mean_std.csv")

METRICS = [
    "avgBlockLatency_s",
    "avgLedgerTrust",
    "reportsCommitted",
    "pdr_norm",
    "throughput_bps",
]

pattern = re.compile(r"block_(?P<block>[0-9]+)_mine_(?P<mine>[0-9]+)_seed_(?P<seed>[0-9]+)\.csv$")

rows = []
for path in sorted(glob.glob(os.path.join(RUNS_DIR, "block_*_mine_*_seed_*.csv"))):
    m = pattern.search(os.path.basename(path))
    if not m:
        continue
    block = int(m.group("block"))
    mine  = int(m.group("mine"))
    seed  = int(m.group("seed"))

    df = pd.read_csv(path)
    if df.empty:
        continue

    r = {"blockIntervalMs": block, "mineDelayMs": mine, "seed": seed}
    for col in METRICS:
        if col not in df.columns:
            raise SystemExit(f"Missing column '{col}' in {path}")
        r[col] = float(df.loc[0, col])
    rows.append(r)

all_df = pd.DataFrame(rows)

keys = ["blockIntervalMs", "mineDelayMs"]

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
