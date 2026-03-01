#!/usr/bin/env python3
import glob
import os
import re
import pandas as pd

RUNS_DIR = os.path.expanduser("~/dissertation/ns3/results/sensitivity/malicious_rate/runs")
OUT_CSV  = os.path.expanduser("~/dissertation/ns3/results/sensitivity/malicious_rate/summary/malicious_sweep_mean_std.csv")

METRICS = [
    "pdr_norm",
    "avgDelay_s",
    "throughput_bps",
    "replayDrops",
    "sigDrops",
    "avgLedgerTrust",
    "avgHandoverDelay_s",
    "rejectCount",
    "blocks",
    "avgBlockLatency_s",
    "reportsCommitted",
]

pattern = re.compile(r"mal_(?P<mal>[0-9.]+)_seed_(?P<seed>[0-9]+)\.csv$")

rows = []
for path in sorted(glob.glob(os.path.join(RUNS_DIR, "mal_*_seed_*.csv"))):
    m = pattern.search(os.path.basename(path))
    if not m:
        continue
    mal = float(m.group("mal"))
    seed = int(m.group("seed"))

    df = pd.read_csv(path)
    if df.empty:
        continue

    r = {"maliciousRate": mal, "seed": seed}
    for col in METRICS:
        if col not in df.columns:
            raise SystemExit(f"Missing column '{col}' in {path}")
        r[col] = float(df.loc[0, col])
    rows.append(r)

if not rows:
    raise SystemExit(f"No run CSV files found in {RUNS_DIR}")

all_df = pd.DataFrame(rows)

# nRuns per maliciousRate
nRuns = all_df.groupby("maliciousRate").size().reset_index(name="nRuns")

# mean/std per maliciousRate
mean_df = all_df.groupby("maliciousRate")[METRICS].mean().reset_index()
std_df  = all_df.groupby("maliciousRate")[METRICS].std(ddof=1).fillna(0.0).reset_index()

# Rename columns
mean_df = mean_df.rename(columns={c: f"{c}_mean" for c in METRICS})
std_df  = std_df.rename(columns={c: f"{c}_std" for c in METRICS})

# Merge into one output
out = nRuns.merge(mean_df, on="maliciousRate").merge(std_df, on="maliciousRate")
out = out.sort_values("maliciousRate").reset_index(drop=True)

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
out.to_csv(OUT_CSV, index=False)

print(f"[OK] Wrote: {OUT_CSV}")
print(out.to_string(index=False))
