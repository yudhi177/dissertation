import os, re
import pandas as pd

BASE = os.path.expanduser("~/dissertation/ns3/results/privacy_linkability_sweep")
RUNS = os.path.join(BASE, "runs")
OUT  = os.path.join(BASE, "summary")
os.makedirs(OUT, exist_ok=True)

files = [f for f in os.listdir(RUNS) if f.endswith(".csv") and not f.endswith("_events.csv")]
if not files:
    print("No CSV files found:", RUNS)
    raise SystemExit(0)

rows=[]
tag_pat = re.compile(r"priv_n(\d+)_s([0-9.]+)_seed(\d+)_rot(\d+)_rsu(\d+)_pool(\d+)")

def parse_events(evt_path):
    out = {"linkAttempts":0, "linkSuccess":0, "pseudoRotations":0, "pseudoRegistrations":0}
    if not os.path.exists(evt_path):
        return out
    with open(evt_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "PSEUDO_ROT" in line: out["pseudoRotations"] += 1
            if "PSEUDO_REG" in line: out["pseudoRegistrations"] += 1
            if "LINK_ATTEMPT" in line: out["linkAttempts"] += 1
            if "LINK_SUCCESS" in line: out["linkSuccess"] += 1
    return out

for fn in files:
    path = os.path.join(RUNS, fn)
    df = pd.read_csv(path)
    if df.empty:
        continue

    runTag = fn.replace(".csv","")
    m = tag_pat.search(runTag)
    if not m:
        continue

    row = df.iloc[0].to_dict()
    row["runTag"] = runTag
    row["nVehicles"] = int(m.group(1))
    row["speedTag"] = float(m.group(2))
    row["seed"] = int(m.group(3))
    row["pseudoRotateSec"] = int(m.group(4))
    row["rotateOnRsuChange"] = int(m.group(5))
    row["pseudoPoolSize"] = int(m.group(6))

    evt = os.path.join(RUNS, runTag + "_events.csv")
    evm = parse_events(evt)
    row.update(evm)

    la = float(row["linkAttempts"])
    ls = float(row["linkSuccess"])
    row["linkabilityRate"] = (ls/la) if la > 0 else 0.0

    rows.append(row)

D = pd.DataFrame(rows)

# force numeric
D["linkabilityRate"] = pd.to_numeric(D["linkabilityRate"], errors="coerce").fillna(0.0)

keys = ["nVehicles","speedTag","pseudoRotateSec","rotateOnRsuChange","pseudoPoolSize"]
num_cols = [c for c in D.columns if c not in keys + ["runTag","seed"] and str(D[c].dtype) != "object"]

g = D.groupby(keys)
mean = g[num_cols].mean().add_suffix("_mean")
std  = g[num_cols].std(ddof=0).add_suffix("_std")
out = pd.concat([mean,std], axis=1).reset_index()

out_path = os.path.join(OUT, "privacy_linkability_mean_std.csv")
out.to_csv(out_path, index=False)
print("[OK] Wrote:", out_path)

raw_path = os.path.join(OUT, "privacy_linkability_all_runs.csv")
D.to_csv(raw_path, index=False)
print("[OK] Wrote:", raw_path)
