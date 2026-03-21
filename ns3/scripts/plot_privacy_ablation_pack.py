import os
import pandas as pd
import matplotlib.pyplot as plt

INP = os.path.expanduser("~/dissertation/ns3/results/privacy_ablation_pack/summary/summary_ci95.csv")
OUT = os.path.expanduser("~/dissertation/ns3/results/privacy_ablation_pack/plots")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(INP)

order = ["FULL_NO_PRIVACY","FULL_PRIVACY"]
df["baseline"] = pd.Categorical(df["baseline"], categories=order, ordered=True)
df = df.sort_values("baseline")

mean_cols = [c for c in df.columns if c.endswith("_mean")]

def pick(preds):
    for c in mean_cols:
        name = c.lower()
        if any(p in name for p in preds):
            return c
    return None

pdr_col   = pick(["pdr"])
delay_col = pick(["avgdelay","delay"])
thr_col   = pick(["throughput"])

# privacy-related if present (best effort)
link_col  = pick(["link", "linksuccessrate", "linkability"])
rot_col   = pick(["rotation", "rotations"])

def plot_point(mean_col, title, fname):
    base = mean_col[:-5]  # strip _mean
    ci_col = base + "_ci95"
    y = df[mean_col]
    e = df[ci_col] if ci_col in df.columns else 0
    x = list(range(len(df)))
    plt.figure()
    plt.errorbar(x, y, yerr=e, fmt="o", capsize=4)
    plt.xticks(x, df["baseline"])
    plt.ylabel(base)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, fname))
    plt.close()

if pdr_col:   plot_point(pdr_col,   "PDR (mean ± CI95): FULL privacy ablation",        "pdr_privacy_ablation.png")
if delay_col: plot_point(delay_col, "Delay (mean ± CI95): FULL privacy ablation",      "delay_privacy_ablation.png")
if thr_col:   plot_point(thr_col,   "Throughput (mean ± CI95): FULL privacy ablation", "throughput_privacy_ablation.png")
if link_col:  plot_point(link_col,  "Linkability metric (mean ± CI95)",                "linkability_privacy_ablation.png")
if rot_col:   plot_point(rot_col,   "Pseudonym rotations (mean ± CI95)",               "rotations_privacy_ablation.png")

print("[OK] plots in", OUT)
print("[INFO] detected mean columns:", mean_cols[:25])
