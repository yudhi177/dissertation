#!/usr/bin/env python3
import os
import glob
import pandas as pd

IN_DIR = "bc_ho_crypto"
OUT = os.path.join(IN_DIR, "master_summary.csv")

def main():
    os.makedirs(IN_DIR, exist_ok=True)

    # Only metrics CSVs (ignore *_events.csv)
    files = sorted([
        f for f in glob.glob(os.path.join(IN_DIR, "*.csv"))
        if not f.endswith("_events.csv") and "events" not in os.path.basename(f).lower()
    ])

    if not files:
        raise SystemExit(f"No metrics CSVs found in {IN_DIR}/ (expected *.csv, excluding *_events.csv)")

    dfs = []
    for f in files:
        # Metrics CSV should be 2 lines (header + 1 row), but use safe read anyway
        df = pd.read_csv(f, on_bad_lines="skip")
        if df.empty:
            print("WARN: empty/invalid file skipped:", f)
            continue

        # If multiple rows accidentally, keep first
        df = df.head(1).copy()
        df["file"] = os.path.basename(f)

        # Add a combined cryptoDelayUs column for plotting convenience
        if "cryptoDelayUsTx" in df.columns and "cryptoDelayUsRx" in df.columns:
            df["cryptoDelayUs"] = (df["cryptoDelayUsTx"].astype(float) + df["cryptoDelayUsRx"].astype(float)) / 2.0
        elif "cryptoDelayUs" not in df.columns:
            # fallback: try parse from filename like c200 or crypto200
            base = os.path.basename(f)
            num = "".join([ch for ch in base if ch.isdigit()])
            df["cryptoDelayUs"] = float(num) if num else 0.0

        dfs.append(df)

    out = pd.concat(dfs, ignore_index=True)
    out = out.sort_values(["cryptoDelayUs", "maliciousRate"], kind="mergesort")

    out.to_csv(OUT, index=False)
    print(f"Wrote {OUT} rows={len(out)}")
    print("Input files:", len(files))

if __name__ == "__main__":
    main()
