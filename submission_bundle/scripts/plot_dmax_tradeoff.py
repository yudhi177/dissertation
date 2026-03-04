import os
import pandas as pd
import matplotlib.pyplot as plt

INP=os.path.expanduser("~/dissertation/ns3/results/dmax_tradeoff/summary/summary_ci95.csv")
OUT=os.path.expanduser("~/dissertation/ns3/results/dmax_tradeoff/plots")
os.makedirs(OUT,exist_ok=True)

df=pd.read_csv(INP).sort_values("trustMaxAgeMs")

# pick best available delay metric
delay_candidates=["handoverDelayMs_mean","avgHandoverDelay_mean","avgDelay_mean","delay_mean"]
delay=None
for c in delay_candidates:
    if c in df.columns:
        delay=c; break

# Plot mismatch rate
if "staleMismatchRate_mean" in df.columns:
    plt.figure()
    plt.errorbar(df["trustMaxAgeMs"], df["staleMismatchRate_mean"],
                 yerr=df.get("staleMismatchRate_ci95",0), marker="o", capsize=3)
    plt.xlabel("Δmax (ms)")
    plt.ylabel("staleMismatchRate")
    plt.title("Stale mismatch rate vs Δmax")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT,"mismatchRate_vs_dmax.png"))
    plt.close()

# Plot delay
if delay:
    base=delay.replace("_mean","")
    plt.figure()
    plt.errorbar(df["trustMaxAgeMs"], df[delay],
                 yerr=df.get(base+"_ci95",0), marker="o", capsize=3)
    plt.xlabel("Δmax (ms)")
    plt.ylabel(base)
    plt.title(f"{base} vs Δmax")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT,"delay_vs_dmax.png"))
    plt.close()

print("[OK] plots in",OUT)
