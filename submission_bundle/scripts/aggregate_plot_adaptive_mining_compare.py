import os, re
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.expanduser("~/dissertation/ns3/results/adaptive_mining_compare")
RUNS = os.path.join(BASE, "runs")
SUM  = os.path.join(BASE, "summary")
PLOTS= os.path.join(BASE, "plots")
os.makedirs(RUNS, exist_ok=True)
os.makedirs(SUM, exist_ok=True)
os.makedirs(PLOTS, exist_ok=True)

files = [f for f in os.listdir(RUNS) if f.endswith(".csv") and not f.endswith("_events.csv")]
if not files:
    print("No CSVs found in runs/. Run the experiment script first.")
    raise SystemExit(0)

rows=[]
for fn in files:
    tag = fn.replace(".csv","")
    m = re.search(r"adapt_n(\d+)_s([0-9.]+)_seed(\d+)_a(\d+)", tag)
    if not m:
        continue
    nveh=int(m.group(1)); spd=float(m.group(2)); seed=int(m.group(3)); a=int(m.group(4))
    df = pd.read_csv(os.path.join(RUNS, fn))
    if df.empty:
        continue
    row = df.iloc[0].to_dict()
    row.update({"nVehicles":nveh,"speedTag":spd,"seed":seed,"adaptive":a})
    rows.append(row)

D = pd.DataFrame(rows)
if D.empty:
    print("No parsable rows.")
    raise SystemExit(0)

metrics = ["avgBlockLatency_s","reportsCommitted","blocks","avgLedgerTrust","pdr_norm","malReject","honReject","throughput_bps","avgDelay_s"]
have = [m for m in metrics if m in D.columns]
print("[OK] metrics found:", have)

g = D.groupby(["nVehicles","adaptive"])
mean = g[have].mean().add_suffix("_mean")
std  = g[have].std(ddof=0).add_suffix("_std")
out = pd.concat([mean,std], axis=1).reset_index()
out["nRuns"] = g.size().values

out_csv = os.path.join(SUM, "adaptive_mean_std.csv")
out.to_csv(out_csv, index=False)
print("[OK] wrote", out_csv)

def plot(metric, ylabel, fname):
    if f"{metric}_mean" not in out.columns:
        return
    plt.figure()
    for a in [0,1]:
        sub = out[out["adaptive"]==a].sort_values("nVehicles")
        yerr = sub.get(f"{metric}_std", None)
        plt.errorbar(sub["nVehicles"], sub[f"{metric}_mean"], yerr=yerr, marker="o", label=f"adaptive={a}")
    plt.title(f"Adaptive Mining Compare: {metric}")
    plt.xlabel("nVehicles")
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    path=os.path.join(PLOTS,fname)
    plt.savefig(path, dpi=200)
    plt.close()
    print("[OK]", path)

plot("avgBlockLatency_s","avgBlockLatency_s","adapt_blockLatency.png")
plot("reportsCommitted","reportsCommitted","adapt_reportsCommitted.png")
plot("blocks","blocks","adapt_blocks.png")
plot("avgLedgerTrust","avgLedgerTrust","adapt_ledgerTrust.png")
plot("pdr_norm","pdr_norm","adapt_pdr_norm.png")
plot("avgDelay_s","avgDelay_s","adapt_delay.png")
plot("throughput_bps","throughput_bps","adapt_throughput.png")
plot("malReject","malReject","adapt_malReject.png")
plot("honReject","honReject","adapt_honReject.png")

print("[DONE] plots in", PLOTS)
