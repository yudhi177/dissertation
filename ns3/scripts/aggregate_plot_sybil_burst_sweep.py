import os, re
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.expanduser("~/dissertation/ns3/results/sybil_burst_sweep")
RUNS = os.path.join(BASE, "runs")
SUM  = os.path.join(BASE, "summary")
PLOTS= os.path.join(BASE, "plots")
os.makedirs(SUM, exist_ok=True)
os.makedirs(PLOTS, exist_ok=True)

files = [f for f in os.listdir(RUNS) if f.endswith(".csv") and not f.endswith("_events.csv")]
if not files:
    print("No CSVs found in runs/.")
    raise SystemExit(0)

rows=[]
for fn in files:
    tag = fn.replace(".csv","")
    m = re.search(r"sybil_n(\d+)_s([0-9.]+)_seed(\d+)_b(\d+)", tag)
    if not m:
        continue
    nveh=int(m.group(1)); spd=float(m.group(2)); seed=int(m.group(3)); burst=int(m.group(4))
    df = pd.read_csv(os.path.join(RUNS, fn))
    if df.empty: 
        continue
    row = df.iloc[0].to_dict()
    row.update({"nVehicles":nveh,"speedTag":spd,"seed":seed,"sybilBurst":burst})
    rows.append(row)

D = pd.DataFrame(rows)
if D.empty:
    print("No parsable rows.")
    raise SystemExit(0)

metrics = [
    "pdr_norm","avgDelay_s","throughput_bps",
    "avgLedgerTrust","reportsCommitted","avgBlockLatency_s",
    "malReject","honReject","handoverCount"
]
have = [m for m in metrics if m in D.columns]
print("[OK] metrics found:", have)

g = D.groupby(["nVehicles","sybilBurst"])
mean = g[have].mean().add_suffix("_mean")
std  = g[have].std(ddof=0).add_suffix("_std")
out = pd.concat([mean,std], axis=1).reset_index()
out["nRuns"] = g.size().values

out_csv = os.path.join(SUM, "sybil_burst_mean_std.csv")
out.to_csv(out_csv, index=False)
print("[OK] wrote", out_csv)

def plot(metric, ylabel, fname):
    if f"{metric}_mean" not in out.columns:
        return
    plt.figure()
    for nveh in sorted(out["nVehicles"].unique()):
        sub = out[out["nVehicles"]==nveh].sort_values("sybilBurst")
        yerr = sub.get(f"{metric}_std", None)
        plt.errorbar(sub["sybilBurst"], sub[f"{metric}_mean"], yerr=yerr, marker="o", label=f"n={nveh}")
    plt.title(f"Sybil Burst Sweep: {metric}")
    plt.xlabel("sybilBurst")
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    path=os.path.join(PLOTS,fname)
    plt.savefig(path, dpi=200)
    plt.close()
    print("[OK]", path)

plot("pdr_norm","pdr_norm","sybil_pdr_norm.png")
plot("avgDelay_s","avgDelay_s","sybil_delay.png")
plot("throughput_bps","throughput_bps","sybil_throughput.png")
plot("avgLedgerTrust","avgLedgerTrust","sybil_ledgerTrust.png")
plot("reportsCommitted","reportsCommitted","sybil_reportsCommitted.png")
plot("avgBlockLatency_s","avgBlockLatency_s","sybil_blockLatency.png")
plot("malReject","malReject","sybil_malReject.png")
plot("honReject","honReject","sybil_honReject.png")
plot("handoverCount","handoverCount","sybil_handoverCount.png")

print("[DONE] plots in", PLOTS)
