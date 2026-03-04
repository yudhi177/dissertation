#!/usr/bin/env python3
import re, glob
import pandas as pd
from pathlib import Path

IN_DIR = Path.home() / "dissertation/ns3/results/sumo_pipeline/runs"
OUT = Path.home() / "dissertation/ns3/results/sumo_pipeline/summary/sumo_pipeline_mean_std.csv"

pat = re.compile(r"veh_(\d+)_spd_([0-9.]+)_seed_(\d+)\.csv$")

rows = []
for f in glob.glob(str(IN_DIR / "*.csv")):
    m = pat.search(f)
    if not m:
        continue
    nveh = int(m.group(1))
    spd = float(m.group(2))
    seed = int(m.group(3))

    df = pd.read_csv(f)
    d = df.iloc[0].to_dict()
    d["nVehicles"] = nveh
    d["speedTag"] = spd
    d["seed"] = seed
    rows.append(d)

if not rows:
    raise SystemExit("No CSV files found to aggregate.")

all_df = pd.DataFrame(rows)

group_cols = ["nVehicles", "speedTag"]
metric_cols = [c for c in all_df.columns if c not in group_cols + ["seed"]]

g = all_df.groupby(group_cols)
mean_df = g[metric_cols].mean(numeric_only=True).add_suffix("_mean")
std_df  = g[metric_cols].std(numeric_only=True).add_suffix("_std")
n_runs  = g.size().rename("nRuns")

out = pd.concat([n_runs, mean_df, std_df], axis=1).reset_index()
out.to_csv(OUT, index=False)

print("[OK] Wrote:", OUT)
print(out[["nVehicles","speedTag","nRuns","pdr_norm_mean","handoverCount_mean","avgHandoverDelay_s_mean","avgLedgerTrust_mean"]])
