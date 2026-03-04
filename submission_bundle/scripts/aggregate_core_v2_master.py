import os, re
import pandas as pd

BASE = os.path.expanduser("~/dissertation/ns3/results/core_v2_master")
RUNS = os.path.join(BASE, "runs")
SUM  = os.path.join(BASE, "summary")
os.makedirs(SUM, exist_ok=True)

files = [f for f in os.listdir(RUNS) if f.endswith(".csv") and not f.endswith("_events.csv")]
if not files:
    print("No CSV files found.")
    raise SystemExit(0)

rows=[]
for fn in files:
    path = os.path.join(RUNS, fn)
    df = pd.read_csv(path)
    if df.empty:
        continue
    row = df.iloc[0].to_dict()
    row["runTag"] = fn.replace(".csv","")
    rows.append(row)

D = pd.DataFrame(rows)

# ---------- Parse runTag into META, but prefix with tag_ to avoid duplicates ----------
def parse(tag):
    out={}
    if tag.startswith("attackmode_"):
        m=re.search(r"attackmode_n(\d+)_s([0-9.]+)_seed(\d+)_m(\d+)", tag)
        out["tag_exp"]="attackmode"
        out["tag_nVehicles"]=int(m.group(1))
        out["tag_speedTag"]=float(m.group(2))
        out["tag_seed"]=int(m.group(3))
        out["tag_attackMode"]=int(m.group(4))
    elif tag.startswith("malsweep_"):
        m=re.search(r"malsweep_n(\d+)_s([0-9.]+)_seed(\d+)_mal([0-9.]+)", tag)
        out["tag_exp"]="malsweep"
        out["tag_nVehicles"]=int(m.group(1))
        out["tag_speedTag"]=float(m.group(2))
        out["tag_seed"]=int(m.group(3))
        out["tag_maliciousRate"]=float(m.group(4))
    elif tag.startswith("thresh_"):
        m=re.search(r"thresh_n(\d+)_s([0-9.]+)_seed(\d+)_tf([0-9.]+)_tm([0-9.]+)", tag)
        out["tag_exp"]="thresh"
        out["tag_nVehicles"]=int(m.group(1))
        out["tag_speedTag"]=float(m.group(2))
        out["tag_seed"]=int(m.group(3))
        out["tag_trustFastThresh"]=float(m.group(4))
        out["tag_trustMinThresh"]=float(m.group(5))
    return out

meta = D["runTag"].apply(parse).apply(pd.Series)

# Ensure no duplicate column names after concat
D = pd.concat([meta, D], axis=1)
D = D.loc[:, ~D.columns.duplicated()]

# experiment grouping keys
exp_groups = {
    "attackmode": ["tag_exp","tag_nVehicles","tag_speedTag","tag_attackMode"],
    "malsweep":   ["tag_exp","tag_nVehicles","tag_speedTag","tag_maliciousRate"],
    "thresh":     ["tag_exp","tag_nVehicles","tag_speedTag","tag_trustFastThresh","tag_trustMinThresh"]
}

# metric columns = numeric columns excluding meta
drop_cols = set(["runTag"]) | set(sum(exp_groups.values(), [])) | set(["tag_seed"])
metric_cols = [c for c in D.columns if c not in drop_cols and D[c].dtype != object]

# Write per-experiment outputs
for exp, keys in exp_groups.items():
    sub = D[D["tag_exp"]==exp].copy()
    if sub.empty:
        continue

    g = sub.groupby(keys, dropna=False)

    mean = g[metric_cols].mean().add_suffix("_mean")
    std  = g[metric_cols].std(ddof=0).add_suffix("_std")
    out  = pd.concat([mean, std], axis=1).reset_index()
    out["nRuns"] = g.size().values

    out_path = os.path.join(SUM, f"{exp}_mean_std.csv")
    out.to_csv(out_path, index=False)
    print("[OK] wrote", out_path)

print("[OK] done. summaries in:", SUM)
