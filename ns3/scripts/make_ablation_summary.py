import os
import re
import glob
import pandas as pd
import matplotlib.pyplot as plt

OUT_DIR = os.path.expanduser("~/dissertation/ns3/results/ablation_summary")
os.makedirs(OUT_DIR, exist_ok=True)

# ---- Where your final comparison CSV likely lives (search) ----
search_roots = [
    os.path.expanduser("~/dissertation/ns3/results"),
]

candidates = []
for root in search_roots:
    candidates += glob.glob(os.path.join(root, "**", "*final*summary*.csv"), recursive=True)
    candidates += glob.glob(os.path.join(root, "**", "*comparison*.csv"), recursive=True)
    candidates += glob.glob(os.path.join(root, "**", "*master_summary*.csv"), recursive=True)

# also include the known sumo_pipeline mean/std for baseline in case needed
candidates += [os.path.expanduser("~/dissertation/ns3/results/sumo_pipeline/summary/sumo_pipeline_mean_std.csv")]

# keep only existing
candidates = [c for c in candidates if os.path.isfile(c)]
candidates = list(dict.fromkeys(candidates))  # unique

if not candidates:
    raise SystemExit("[ERR] No candidate summary CSVs found under ns3/results.")

print("[OK] Found candidates:")
for c in candidates[:12]:
    print(" -", c)

# ---- Heuristic: pick the file that contains model labels (baseline/secure/blockchain/full) ----
best = None
best_score = -1

keywords = ["baseline", "secure", "blockchain", "integrated", "full"]
for c in candidates:
    try:
        df = pd.read_csv(c)
    except Exception:
        continue
    cols = [x.lower() for x in df.columns.astype(str)]
    score = 0
    # score by presence of typical columns
    for k in ["pdr_norm", "avgdelay", "throughput", "avgledgertrust", "handovercount"]:
        score += sum(k in col for col in cols)
    # score if any row contains model names
    txt = " ".join(df.astype(str).head(30).values.flatten()).lower()
    score += sum(k in txt for k in keywords) * 2
    if score > best_score:
        best_score = score
        best = c

if best is None:
    raise SystemExit("[ERR] Could not read any candidate CSVs.")

print("[OK] Using:", best)
df = pd.read_csv(best)

# ---- Normalize schema: try to find a model column ----
model_col = None
for c in df.columns:
    cl = str(c).lower()
    if cl in ["model", "scenario", "scheme", "variant", "name"]:
        model_col = c
        break

# If no model col, assume this file is NOT a multi-model summary; we will still produce something minimal.
if model_col is None:
    # create a pseudo model label
    df["Model"] = "SUMO_PIPELINE"
    model_col = "Model"

# ---- Pick representative rows (mean rows)
# If mean/std table: choose one density+speed (e.g., nVehicles=50, speedTag=13.9) if available, else first row.
pick = df.copy()
if "nVehicles" in pick.columns and "speedTag" in pick.columns:
    # try standard paper condition
    target = pick[(pick["nVehicles"]==50) & (pick["speedTag"]==13.9)]
    if target.empty:
        target = pick.head(1)
    pick = target

# ---- Map columns (robust to naming)
def find_col(cands):
    for c in cands:
        if c in pick.columns: return c
    # fuzzy
    low = {x.lower(): x for x in pick.columns}
    for c in cands:
        for k,v in low.items():
            if c.lower() == k: return v
    for c in cands:
        for k,v in low.items():
            if c.lower() in k: return v
    return None

col_pdr  = find_col(["pdr_norm_mean","pdr_norm"])
col_del  = find_col(["avgDelay_s_mean","avgDelay_s","delay_mean","avgDelay"])
col_thr  = find_col(["throughput_bps_mean","throughput_bps","throughput_mean"])
col_tru  = find_col(["avgLedgerTrust_mean","avgLedgerTrust"])
col_ho   = find_col(["handoverCount_mean","handoverCount"])
col_blk  = find_col(["avgBlockLatency_s_mean","avgBlockLatency_s"])

metrics = {
    "PDR_norm": col_pdr,
    "Delay_s": col_del,
    "Throughput_bps": col_thr,
    "LedgerTrust": col_tru,
    "HandoverCount": col_ho,
    "BlockLatency_s": col_blk
}
metrics = {k:v for k,v in metrics.items() if v is not None}

# Build ablation table
ab = pick[[model_col] + list(metrics.values())].copy()
ab.rename(columns={model_col:"Model", **{v:k for k,v in metrics.items()}}, inplace=True)

# Clean model names a bit
ab["Model"] = ab["Model"].astype(str).str.replace("_", " ").str.title()

out_csv = os.path.join(OUT_DIR, "ablation_table.csv")
ab.to_csv(out_csv, index=False)
print("[OK] wrote:", out_csv)

# ---- Plot: simple grouped bar for 4 key metrics if present
plot_metrics = [m for m in ["PDR_norm","Delay_s","Throughput_bps","LedgerTrust","HandoverCount"] if m in ab.columns]

if plot_metrics:
    # normalize each metric for plotting (so different scales fit)
    norm = ab.copy()
    for m in plot_metrics:
        x = pd.to_numeric(norm[m], errors="coerce")
        mn, mx = x.min(), x.max()
        if mx - mn < 1e-12:
            norm[m] = 0.0
        else:
            norm[m] = (x - mn) / (mx - mn)

    plt.figure(figsize=(10,4))
    width = 0.15
    xs = range(len(norm["Model"]))
    for i,m in enumerate(plot_metrics):
        plt.bar([x + i*width for x in xs], norm[m], width=width, label=m)

    plt.xticks([x + width*(len(plot_metrics)-1)/2 for x in xs], norm["Model"], rotation=20, ha="right")
    plt.ylabel("Normalized (0–1)")
    plt.title("Ablation Summary (normalized metrics)")
    plt.legend()
    plt.tight_layout()

    out_png = os.path.join(OUT_DIR, "ablation_bar.png")
    plt.savefig(out_png, dpi=200)
    plt.close()
    print("[OK] wrote:", out_png)
else:
    print("[WARN] No plottable metrics found in selected row.")
