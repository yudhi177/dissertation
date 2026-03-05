import glob, os
import pandas as pd

files = glob.glob(os.path.expanduser("~/dissertation/ns3/results/*/master_summary.csv"))
for f in files:
    df = pd.read_csv(f)
    if df.empty: 
        continue
    pcol = None
    for c in ["pdr_norm","pdr_norm_mean","pdr"]:
        if c in df.columns:
            pcol = c
            break
    if not pcol:
        continue
    mx = pd.to_numeric(df[pcol], errors="coerce").max()
    if mx is not None and mx > 1.0 and mx <= 100.0:
        df[pcol] = pd.to_numeric(df[pcol], errors="coerce") / 100.0
        df.to_csv(f, index=False)
        print("[OK] normalized percent->fraction:", f, "col=", pcol)
