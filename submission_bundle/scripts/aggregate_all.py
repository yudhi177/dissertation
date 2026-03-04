#!/usr/bin/env python3
import os
import glob
import pandas as pd

OUT_DIR = "final_results"
OUT_CSV = os.path.join(OUT_DIR, "final_master_summary.csv")

def safe_read_csv(path: str) -> pd.DataFrame:
    # robust reading for small single-row CSVs
    return pd.read_csv(path)

def add_unified_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Create unified columns across scenarios (if present)
    # tx/rx
    if "txCount" in df.columns and "tx" not in df.columns:
        df["tx"] = df["txCount"]
    if "rxCount" in df.columns and "rx" not in df.columns:
        df["rx"] = df["rxCount"]
    if "txData" in df.columns and "tx" not in df.columns:
        df["tx"] = df["txData"]
    if "rxData" in df.columns and "rx" not in df.columns:
        df["rx"] = df["rxData"]

    # common metrics
    if "pdr" not in df.columns and "PDR" in df.columns:
        df["pdr"] = df["PDR"]
    if "avgDelay_s" not in df.columns and "avgDelay" in df.columns:
        df["avgDelay_s"] = df["avgDelay"]
    if "throughput_bps" not in df.columns and "throughput" in df.columns:
        df["throughput_bps"] = df["throughput"]

    return df

def collect(pattern: str, scenario: str):
    rows = []
    for f in sorted(glob.glob(pattern)):
        try:
            df = safe_read_csv(f)
            if df.empty:
                continue
            df = add_unified_columns(df)
            df["scenario"] = scenario
            df["source_file"] = os.path.basename(f)
            df["source_path"] = f
            rows.append(df)
        except Exception as e:
            print(f"[WARN] Skipping {f}: {e}")
    if not rows:
        return None
    return pd.concat(rows, ignore_index=True)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Add here all important outputs you want in final comparison:
    sources = [
        ("results/metrics_*.csv", "baseline_urban_v2x"),
        ("results/handover_runs/master_summary.csv", "rsu_handover_trust"),
        ("results/secure_*.csv", "secure_v2x"),
        ("results/t.csv", "secure_v2x_tmp"),
        ("blockchain_runs/bc_metrics_*.csv", "blockchain_trust_v2x"),
        ("bc_ho_runs/bc_ho_m*.csv", "bc_rsu_handover_trust"),
        ("bc_ho_sweep/*.csv", "bc_ho_sweep"),           # only metric CSVs (events may exist, they will be skipped if parse fails)
        ("bc_ho_crypto/*.csv", "bc_ho_crypto"),         # metric CSVs + events (events will be skipped if parse fails)
    ]

    all_dfs = []
    for pattern, scenario in sources:
        got = collect(pattern, scenario)
        if got is not None:
            all_dfs.append(got)

    if not all_dfs:
        raise SystemExit("No input CSVs found. Check your folders/paths.")

    out = pd.concat(all_dfs, ignore_index=True)

    # Remove obvious event CSVs if they slipped in (they don't have expected columns)
    # Keep only rows that have at least one core metric column
    core_cols = {"pdr", "avgDelay_s", "throughput_bps", "tx", "rx"}
    keep_mask = out.columns.isin(core_cols).any()
    # If dataframe doesn't have those columns for some scenario, keep anyway, but better filter by column existence:
    # We'll do row-wise fallback: keep everything; plots will skip missing columns.
    # (So no hard filtering here.)

    out.to_csv(OUT_CSV, index=False)
    print(f"Wrote: {OUT_CSV} rows= {len(out)}")
    print("Columns:", len(out.columns))
    if "scenario" not in out.columns:
        print("ERROR: scenario missing (should not happen).")
    else:
        print("Scenarios:", sorted(out["scenario"].dropna().unique().tolist()))

if __name__ == "__main__":
    main()
