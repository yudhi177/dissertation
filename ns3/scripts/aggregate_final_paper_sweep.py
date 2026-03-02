import os, re, glob
import pandas as pd

RUNS_DIR = os.path.expanduser("~/dissertation/ns3/results/final_paper_sweep/runs")
OUT_DIR  = os.path.expanduser("~/dissertation/ns3/results/final_paper_sweep/summary")
os.makedirs(OUT_DIR, exist_ok=True)

pat = re.compile(r"veh_(\d+)_spd_([0-9.]+)_seed_(\d+)_mal_([0-9.]+)_tf_([0-9.]+)_tm_([0-9.]+)\.csv$")

rows=[]
for f in glob.glob(os.path.join(RUNS_DIR, "*.csv")):
    m = pat.search(os.path.basename(f))
    if not m: 
        continue
    nveh, spd, seed, mal, tf, tm = m.groups()
    df = pd.read_csv(f)
    if df.empty: 
        continue
    r = df.iloc[0].to_dict()
    r.update({
        "nVehicles": int(nveh),
        "speedTag": float(spd),
        "seed": int(seed),
        "maliciousRate_cfg": float(mal),
        "trustFastThresh_cfg": float(tf),
        "trustMinThresh_cfg": float(tm),
        "runFile": os.path.basename(f),
    })
    rows.append(r)

if not rows:
    print("No sweep CSVs found.")
    raise SystemExit(0)

raw = pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT_DIR, "final_sweep_raw.csv"), index=False)

group_cols = ["nVehicles","speedTag","maliciousRate_cfg","trustFastThresh_cfg","trustMinThresh_cfg"]
metrics = [c for c in raw.columns if c not in group_cols + ["seed","runFile"]]

agg = raw.groupby(group_cols)[metrics].agg(["mean","std"]).reset_index()
agg.columns = ["_".join([c for c in col if c]) for col in agg.columns.to_flat_index()]
agg = agg.rename(columns={
    "nVehicles_":"nVehicles",
    "speedTag_":"speedTag",
    "maliciousRate_cfg_":"maliciousRate",
    "trustFastThresh_cfg_":"trustFastThresh",
    "trustMinThresh_cfg_":"trustMinThresh",
})
agg.to_csv(os.path.join(OUT_DIR, "final_sweep_mean_std.csv"), index=False)

print("[OK] Wrote:")
print(" -", os.path.join(OUT_DIR, "final_sweep_raw.csv"))
print(" -", os.path.join(OUT_DIR, "final_sweep_mean_std.csv"))
