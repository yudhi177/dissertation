import os, re
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.expanduser("~/dissertation/ns3/results/txall_realism")
RUNS = os.path.join(BASE, "runs")
SUM  = os.path.join(BASE, "summary")
PLOTS= os.path.join(BASE, "plots")
os.makedirs(SUM, exist_ok=True)
os.makedirs(PLOTS, exist_ok=True)

files = [f for f in os.listdir(RUNS) if f.endswith(".csv") and not f.endswith("_events.csv")]
rows=[]
for fn in files:
    df = pd.read_csv(os.path.join(RUNS, fn))
    if df.empty: 
        continue
    row = df.iloc[0].to_dict()
    tag = fn.replace(".csv","")
    m = re.search(r"txall_n(\d+)_s([0-9.]+)_seed(\d+)_tx(\d+)", tag)
    if not m: 
        continue
    row["nVehicles"]=int(m.group(1))
    row["speedTag"]=float(m.group(2))
    row["seed"]=int(m.group(3))
    row["txAll"]=int(m.group(4))
    rows.append(row)

D = pd.DataFrame(rows)
if D.empty:
    print("No data to aggregate.")
    raise SystemExit(0)

metrics = ["pdr_norm","avgDelay_s","throughput_bps","sigDrops","replayDrops","reportsCommitted","avgLedgerTrust","malReject","honReject","handoverCount","avgHandoverDelay_s"]
have = [m for m in metrics if (m in D.columns)]

g = D.groupby(["nVehicles","speedTag","txAll"])
mean = g[have].mean().add_suffix("_mean")
std  = g[have].std(ddof=0).add_suffix("_std")
out = pd.concat([mean,std], axis=1).reset_index()
out["nRuns"] = g.size().values

out_csv = os.path.join(SUM, "txall_mean_std.csv")
out.to_csv(out_csv, index=False)
print("[OK] wrote", out_csv)

# Plots: for each metric, compare txAll=0 vs 1 across nVehicles
def plot_metric(metric, ylabel, fname):
    plt.figure()
    for tx in [0,1]:
        sub = out[out["txAll"]==tx].sort_values("nVehicles")
        plt.errorbar(sub["nVehicles"], sub[f"{metric}_mean"], yerr=sub.get(f"{metric}_std", None),
                     marker="o", label=f"txAll={tx}")
    plt.title(f"TX_ALL realism: {metric}")
    plt.xlabel("nVehicles")
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    path = os.path.join(PLOTS, fname)
    plt.savefig(path, dpi=200)
    plt.close()
    print("[OK]", path)

if "pdr_norm" in have: plot_metric("pdr_norm","pdr_norm","txall_pdr_norm.png")
if "avgDelay_s" in have: plot_metric("avgDelay_s","avgDelay_s","txall_delay.png")
if "throughput_bps" in have: plot_metric("throughput_bps","throughput_bps","txall_throughput.png")
if "sigDrops" in have: plot_metric("sigDrops","sigDrops","txall_sigDrops.png")
if "reportsCommitted" in have: plot_metric("reportsCommitted","reportsCommitted","txall_reportsCommitted.png")
if "malReject" in have: plot_metric("malReject","malReject","txall_malReject.png")
if "honReject" in have: plot_metric("honReject","honReject","txall_honReject.png")

print("[DONE] plots in", PLOTS)
