import os, re
import pandas as pd

BASE = os.path.expanduser("~/dissertation/ns3/results/baseline_ablation")
RUNS = os.path.join(BASE, "runs")
OUT  = os.path.join(BASE, "summary")
os.makedirs(OUT, exist_ok=True)

files = [f for f in os.listdir(RUNS) if f.endswith(".csv") and not f.endswith("_events.csv")]
if not files:
    print("No CSV files found:", RUNS)
    raise SystemExit(0)

pat = re.compile(r"base_(pki|bc|full)_n(\d+)_s([0-9.]+)_seed(\d+)")

def parse_revocation(evt_path):
    issue_t = None
    apply_delays = []
    revoke_drops = 0
    if not os.path.exists(evt_path): 
        return {"revIssue":0, "revApply":0, "revPropMax":0.0, "revPropAvg":0.0, "revokeDropsEvt":0}
    with open(evt_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "REVOKE_ISSUE" in line:
                # time is first CSV field
                try:
                    issue_t = float(line.split(",",1)[0])
                except:
                    pass
            if "REVOKE_APPLY" in line and "delay=" in line:
                try:
                    d = float(line.split("delay=",1)[1].strip())
                    apply_delays.append(d)
                except:
                    pass
            if "DATA_DROP_REVOKED" in line:
                revoke_drops += 1
    if not apply_delays:
        return {"revIssue":1 if issue_t is not None else 0, "revApply":0, "revPropMax":0.0, "revPropAvg":0.0, "revokeDropsEvt":revoke_drops}
    return {
        "revIssue":1 if issue_t is not None else 0,
        "revApply":len(apply_delays),
        "revPropMax":max(apply_delays),
        "revPropAvg":sum(apply_delays)/len(apply_delays),
        "revokeDropsEvt":revoke_drops
    }

rows=[]
for fn in files:
    tag = fn.replace(".csv","")
    m = pat.search(tag)
    if not m: 
        continue
    baseline, nveh, spd, seed = m.group(1), int(m.group(2)), float(m.group(3)), int(m.group(4))
    df = pd.read_csv(os.path.join(RUNS, fn))
    if df.empty: 
        continue
    row = df.iloc[0].to_dict()
    row.update({"baseline":baseline, "nVehicles":nveh, "speedTag":spd, "seed":seed, "runTag":tag})
    evt = os.path.join(RUNS, tag + "_events.csv")
    row.update(parse_revocation(evt))
    rows.append(row)

D = pd.DataFrame(rows)
raw_path = os.path.join(OUT, "baseline_ablation_all_runs.csv")
D.to_csv(raw_path, index=False)
print("[OK] Wrote:", raw_path)

keys = ["baseline","nVehicles","speedTag"]
num_cols = [c for c in D.columns if c not in keys + ["runTag","seed"] and str(D[c].dtype) != "object"]
g = D.groupby(keys)
mean = g[num_cols].mean().add_suffix("_mean")
std  = g[num_cols].std(ddof=0).add_suffix("_std")
S = pd.concat([mean,std], axis=1).reset_index()

out_path = os.path.join(OUT, "baseline_ablation_mean_std.csv")
S.to_csv(out_path, index=False)
print("[OK] Wrote:", out_path)
