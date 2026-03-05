import glob, os
import pandas as pd

out = os.path.expanduser("~/dissertation/ns3/results/final_table.csv")
files = sorted(glob.glob(os.path.expanduser("~/dissertation/ns3/results/*_pack/master_summary.csv")))

rows = []
for f in files:
    pack = os.path.basename(os.path.dirname(f))
    df = pd.read_csv(f)
    if df.empty:
        continue

    # try pick best columns
    def pick(cols, cands):
        for c in cands:
            if c in cols: return c
        return None

    cols = df.columns
    pcol = pick(cols, ["pdr_norm_mean","pdr_norm","pdr"])
    dcol = pick(cols, ["avgDelayMs","avgDelay_s_mean","avgDelay_s"])
    tcol = pick(cols, ["throughputKbps","throughput_bps_mean","throughput_bps"])

    # numeric
    if pcol:
        df[pcol] = pd.to_numeric(df[pcol], errors="coerce")
        mx = df[pcol].max()
        if mx is not None and mx > 1 and mx <= 100:
            df[pcol] = df[pcol]/100.0

    if dcol: df[dcol] = pd.to_numeric(df[dcol], errors="coerce")
    if tcol: df[tcol] = pd.to_numeric(df[tcol], errors="coerce")

    # summary row
    row = {
        "pack": pack,
        "rows": len(df),
        "pdr_mean": float(df[pcol].mean()) if pcol else None,
        "delay_mean": float(df[dcol].mean()) if dcol else None,
        "throughput_mean": float(df[tcol].mean()) if tcol else None,
        "source_file": f
    }
    rows.append(row)

pd.DataFrame(rows).to_csv(out, index=False)
print("[OK] wrote:", out)
