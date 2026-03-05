import os, glob
import pandas as pd
import matplotlib.pyplot as plt

outdir = os.path.expanduser("~/dissertation/ns3/results/plots_all")
os.makedirs(outdir, exist_ok=True)

files = sorted(glob.glob(os.path.expanduser("~/dissertation/ns3/results/*/master_summary.csv")))
files += sorted(glob.glob(os.path.expanduser("~/dissertation/ns3/results/*/*summary*.csv")))
files = sorted(set(files))

def pick_col(cols, candidates):
    for c in candidates:
        if c in cols: return c
    return None

for f in files:
    try:
        df = pd.read_csv(f)
    except Exception:
        continue
    if df.empty: 
        continue

    cols = list(df.columns)

    # choose x
    xcol = pick_col(cols, ["speed", "Speed", "nVehicles", "nVehicles_mean", "simTime", "run", "Run"])
    if xcol is None:
        df["idx"] = range(len(df))
        xcol = "idx"

    # choose metrics
    pcol = pick_col(cols, ["pdr_norm", "pdr_norm_mean", "pdr"])
    dcol = pick_col(cols, ["avgDelayMs", "avgDelay_s", "avgDelay_s_mean"])
    tcol = pick_col(cols, ["throughputKbps", "throughput_bps", "throughput_bps_mean"])

    # normalize pdr if percent
    if pcol and df[pcol].dropna().astype(float).max() > 1.0 and df[pcol].dropna().astype(float).max() <= 100.0:
        df[pcol] = df[pcol].astype(float) / 100.0

    base = os.path.basename(os.path.dirname(f)) + "__" + os.path.basename(f).replace(".csv","")

    def plot_one(ycol, title, ylabel):
        if ycol is None or ycol not in df.columns: 
            return
        y = pd.to_numeric(df[ycol], errors="coerce")
        x = pd.to_numeric(df[xcol], errors="coerce")
        m = x.notna() & y.notna()
        if m.sum() < 2:
            return
        plt.figure()
        plt.plot(x[m], y[m], marker="o")
        plt.title(f"{title} ({os.path.basename(os.path.dirname(f))})")
        plt.xlabel(xcol)
        plt.ylabel(ylabel)
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, f"{base}__{ycol}.png"))
        plt.close()

    plot_one(pcol, "PDR", "PDR (0-1)")
    plot_one(dcol, "Avg Delay", dcol)
    plot_one(tcol, "Throughput", tcol)

print("[OK] plots saved to:", outdir)
