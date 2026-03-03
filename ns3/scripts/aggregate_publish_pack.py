import sys, csv
from pathlib import Path
import pandas as pd

if len(sys.argv) != 3:
    print("Usage: aggregate_publish_pack.py runs_index.csv summary.csv")
    raise SystemExit(2)

idx_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])

idx = pd.read_csv(idx_path)

rows = []
for _, r in idx.iterrows():
    csvf = Path(str(r["csv"]))
    if not csvf.exists():
        continue
    # ns-3 per-run metrics: assume header + single row
    with csvf.open() as f:
        reader = csv.reader(f)
        header = next(reader, None)
        vals = next(reader, None)
    if not header or not vals:
        continue
    d = dict(zip(header, vals))

    # add metadata
    d["baseline"] = r["baseline"]
    d["nveh"] = r["nveh"]
    d["speed"] = r["speed"]
    d["seed"] = r["seed"]

    # parse [BC] and [PRIV] lines if present
    bc = str(r.get("bc_line",""))
    priv = str(r.get("priv_line",""))
    for key in ["queries","updates","cacheHits","cacheMisses","hitRate","avgQms","avgUms"]:
        if f"{key}=" in bc:
            try: d[f"bc_{key}"] = float(bc.split(f"{key}=")[1].split()[0])
            except: pass
    for key in ["rotations","linkAttempts","linkSuccess","linkSuccessRate","linkSuccessRateExp"]:
        if f"{key}=" in priv:
            try: d[f"priv_{key}"] = float(priv.split(f"{key}=")[1].split()[0])
            except: pass

    rows.append(d)

df = pd.DataFrame(rows)

# convert numeric where possible
for c in df.columns:
    if c in ["baseline"]:
        continue
    df[c] = pd.to_numeric(df[c], errors="ignore")

# group mean/std
group_cols = ["baseline","nveh","speed"]
num_cols = [c for c in df.columns if c not in group_cols and c != "seed"]

g = df.groupby(group_cols)
mean = g[num_cols].mean().reset_index()
std = g[num_cols].std(ddof=1).reset_index()

# CI95 = 1.96 * std/sqrt(n)
counts = g.size().reset_index(name="n")
out = mean.merge(std, on=group_cols, suffixes=("", "_std")).merge(counts, on=group_cols)

import numpy as np
for c in num_cols:
    if c + "_std" in out.columns:
        out[c + "_ci95"] = 1.96 * out[c + "_std"] / np.sqrt(out["n"].clip(lower=1))

out.to_csv(out_path, index=False)
print("[OK] wrote", out_path)
