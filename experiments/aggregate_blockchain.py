#!/usr/bin/env python3
import glob
import os
import re
import pandas as pd

def parse_malicious_rate(fname: str):
    # bc_metrics_m0.2.csv -> 0.2
    m = re.search(r"_m([0-9]+(?:\.[0-9]+)?)", fname)
    return float(m.group(1)) if m else None

def main():
    base = os.path.join("ns3", "results", "blockchain_runs")
    files = sorted(glob.glob(os.path.join(base, "bc_metrics_*.csv")))
    if not files:
        raise SystemExit(f"No files found: {base}/bc_metrics_*.csv")

    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df["file"] = os.path.basename(f)
        mr = parse_malicious_rate(df["file"].iloc[0])
        if "maliciousRate" not in df.columns and mr is not None:
            df["maliciousRate"] = mr
        dfs.append(df)

    out = pd.concat(dfs, ignore_index=True)

    out_path = os.path.join(base, "master_summary.csv")
    out.to_csv(out_path, index=False)
    print("Wrote", out_path, "rows=", len(out))
    print("Input files:", len(files))

if __name__ == "__main__":
    main()
