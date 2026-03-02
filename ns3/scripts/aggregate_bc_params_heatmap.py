import os, re
import pandas as pd

BASE = os.path.expanduser("~/dissertation/ns3/results/bc_params_heatmap")
RUNS = os.path.join(BASE, "runs")
SUM  = os.path.join(BASE, "summary")
os.makedirs(SUM, exist_ok=True)

files = [f for f in os.listdir(RUNS) if f.endswith(".csv") and not f.endswith("_events.csv")]
if not files:
    print("No CSV files found.")
    raise SystemExit(0)

rows=[]
for fn in files:
    tag = fn.replace(".csv","")
    m = re.search(r"bcparam_n(\d+)_s([0-9.]+)_seed(\d+)_bi(\d+)_md(\d+)", tag)
    if not m:
        continue
    nveh=int(m.group(1)); spd=float(m.group(2)); seed=int(m.group(3))
    bi=int(m.group(4)); md=int(m.group(5))

    df = pd.read_csv(os.path.join(RUNS, fn))
    if df.empty: 
        continue
    row = df.iloc[0].to_dict()
    row.update({
        "nVehicles": nveh, "speedTag": spd, "seed": seed,
        "blockIntervalMs": bi, "mineDelayMs": md
    })
    rows.append(row)

D = pd.DataFrame(rows)
if D.empty:
    print("No rows parsed.")
    raise SystemExit(0)

# pick metrics you care about (only keep ones present)
metrics = [
    "pdr_norm","avgDelay_s","throughput_bps",
    "reportsCommitted","avgLedgerTrust",
    "avgBlockLatency_s","blocks",
    "malReject","honReject",
    "sigDrops","replayDrops"
]
have = [m for m in metrics if m in D.columns]

g = D.groupby(["nVehicles","speedTag","blockIntervalMs","mineDelayMs"])
mean = g[have].mean().add_suffix("_mean")
std  = g[have].std(ddof=0).add_suffix("_std")
out  = pd.concat([mean,std], axis=1).reset_index()
out["nRuns"] = g.size().values

out_csv = os.path.join(SUM, "bc_params_mean_std.csv")
out.to_csv(out_csv, index=False)
print("[OK] wrote", out_csv)
