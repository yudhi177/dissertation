import os, re
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.expanduser("~/dissertation/ns3/results/blockchain_ablation")
RUNS = os.path.join(BASE, "runs")
SUM  = os.path.join(BASE, "summary")
PLOTS= os.path.join(BASE, "plots")
os.makedirs(SUM, exist_ok=True)
os.makedirs(PLOTS, exist_ok=True)

files = [f for f in os.listdir(RUNS) if f.endswith(".csv") and not f.endswith("_events.csv")]
rows=[]
for fn in files:
    tag = fn.replace(".csv","")
    m = re.search(r"bcabl_(trust_reports|trust_bc|full_no_bc|full_bc)_n(\d+)_s([0-9.]+)_seed(\d+)", tag)
    if not m:
        continue
    model = m.group(1)
    nveh = int(m.group(2))
    spd  = float(m.group(3))
    seed = int(m.group(4))
    df = pd.read_csv(os.path.join(RUNS, fn))
    if df.empty:
        continue
    row = df.iloc[0].to_dict()
    row["model"]=model
    row["nVehicles"]=nveh
    row["speedTag"]=spd
    row["seed"]=seed
    rows.append(row)

D = pd.DataFrame(rows)
if D.empty:
    print("No data found.")
    raise SystemExit(0)

metrics = ["pdr_norm","avgDelay_s","throughput_bps","reportsCommitted","avgLedgerTrust",
           "avgBlockLatency_s","blocks","malReject","honReject","handoverCount","avgHandoverDelay_s"]
have = [m for m in metrics if m in D.columns]

g = D.groupby(["model","nVehicles","speedTag"])
mean = g[have].mean().add_suffix("_mean")
std  = g[have].std(ddof=0).add_suffix("_std")
out = pd.concat([mean,std], axis=1).reset_index()
out["nRuns"] = g.size().values

out_csv = os.path.join(SUM, "bc_ablation_mean_std.csv")
out.to_csv(out_csv, index=False)
print("[OK] wrote", out_csv)

def plot_metric(metric, ylabel, fname):
    plt.figure()
    order = ["trust_reports","trust_bc","full_no_bc","full_bc"]
    for model in order:
        sub = out[out["model"]==model].sort_values("nVehicles")
        if sub.empty: 
            continue
        plt.errorbar(sub["nVehicles"], sub[f"{metric}_mean"], yerr=sub.get(f"{metric}_std", None),
                     marker="o", label=model)
    plt.title(f"Blockchain Ablation: {metric} vs density")
    plt.xlabel("nVehicles")
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    path=os.path.join(PLOTS,fname)
    plt.savefig(path, dpi=200)
    plt.close()
    print("[OK]", path)

if "pdr_norm" in have: plot_metric("pdr_norm","pdr_norm","bcabl_pdr_norm.png")
if "avgLedgerTrust" in have: plot_metric("avgLedgerTrust","avgLedgerTrust","bcabl_ledgerTrust.png")
if "reportsCommitted" in have: plot_metric("reportsCommitted","reportsCommitted","bcabl_reportsCommitted.png")
if "avgBlockLatency_s" in have: plot_metric("avgBlockLatency_s","avgBlockLatency_s","bcabl_blockLatency.png")
if "malReject" in have: plot_metric("malReject","malReject","bcabl_malReject.png")
if "honReject" in have: plot_metric("honReject","honReject","bcabl_honReject.png")

print("[DONE] plots in", PLOTS)
