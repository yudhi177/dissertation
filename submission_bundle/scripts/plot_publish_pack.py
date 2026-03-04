import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

if len(sys.argv) != 3:
    print("Usage: plot_publish_pack.py summary.csv out_plots_dir")
    raise SystemExit(2)

summ = Path(sys.argv[1])
outd = Path(sys.argv[2])
outd.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(summ)

def pick_col(cands):
    for c in cands:
        if c in df.columns:
            return c
    return None

col_pdr = pick_col(["PDR","pdr","pdrMean"])
col_delay = pick_col(["avgDelay","avgDelayMs","delay","meanDelay"])
col_thr = pick_col(["throughput","throughputKbps","avgThroughput","tput"])
col_priv = pick_col(["priv_linkSuccessRate"])
col_bcu = pick_col(["bc_updates","bc_updates_mean"])

def plot_metric(ycol, title, fname):
    if not ycol: return
    plt.figure()
    for b, sub in df.groupby("baseline"):
        sub = sub.sort_values("speed")
        plt.plot(sub["speed"], sub[ycol], marker="o", label=b)
    plt.xlabel("speed")
    plt.ylabel(ycol)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outd / fname)
    plt.close()

plot_metric(col_pdr, "PDR vs Speed (Baselines)", "pdr_vs_speed.png")
plot_metric(col_delay, "Delay vs Speed (Baselines)", "delay_vs_speed.png")
plot_metric(col_thr, "Throughput vs Speed (Baselines)", "throughput_vs_speed.png")
plot_metric(col_priv, "Linkability Success Rate vs Speed (FULL baseline)", "linkability_vs_speed.png")

# BC updates vs speed (if available)
if col_bcu:
    plt.figure()
    for b, sub in df.groupby("baseline"):
        sub = sub.sort_values("speed")
        plt.plot(sub["speed"], sub[col_bcu], marker="o", label=b)
    plt.xlabel("speed")
    plt.ylabel(col_bcu)
    plt.title("Blockchain Updates vs Speed")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outd / "bc_updates_vs_speed.png")
    plt.close()

print("[OK] plots in", outd)
