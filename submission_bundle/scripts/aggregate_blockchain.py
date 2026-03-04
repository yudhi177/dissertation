#!/usr/bin/env python3
import glob
import os
import pandas as pd

def main():
    in_files = sorted(glob.glob("blockchain_runs/bc_metrics_*.csv"))
    if not in_files:
        raise SystemExit("No files found: blockchain_runs/bc_metrics_*.csv")

    dfs = []
    for f in in_files:
        df = pd.read_csv(f)
        df["file"] = os.path.basename(f)

        # Try to parse maliciousRate from filename: bc_metrics_m0.2.csv
        mr = None
        name = os.path.basename(f)
        if "_m" in name:
            try:
                mr = float(name.split("_m")[-1].replace(".csv", ""))
            except Exception:
                mr = None
        df["maliciousRate_from_file"] = mr

        dfs.append(df)

    out = pd.concat(dfs, ignore_index=True)
    out.to_csv("blockchain_runs/master_summary.csv", index=False)

    print("Wrote blockchain_runs/master_summary.csv rows =", len(out))
    print("Inputs:", len(in_files))

if __name__ == "__main__":
    main()
