import os
import pandas as pd
import matplotlib.pyplot as plt

inp = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare/summary_ci95.csv")
out = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare/plots")
os.makedirs(out, exist_ok=True)

df = pd.read_csv(inp)

# --- detect grouping column names ---
def pick_col(cands):
    for c in cands:
        if c in df.columns:
            return c
    return None

col_baseline = pick_col(["baseline", "baseline_", "baseline__"])
col_speed    = pick_col(["speed", "speed_", "speed__"])
col_nveh     = pick_col(["nveh", "nveh_", "nveh__"])

if not col_baseline or not col_speed:
    raise SystemExit(f"[ERR] Could not find baseline/speed columns. Columns={list(df.columns)[:30]}")

# choose one nveh level if present (prefer max)
if col_nveh:
    nveh_vals = sorted(df[col_nveh].dropna().unique())
    chosen_nveh = nveh_vals[-1]
    df = df[df[col_nveh] == chosen_nveh].copy()

def plot_metric(metric_base, title, fname):
    ycol = pick_col([f"{metric_base}_mean", metric_base])
    if not ycol:
        print("[SKIP] missing metric:", metric_base)
        return
    ecol = pick_col([f"{metric_base}_ci95", f"{metric_base}_ci95_mean"])  # just in case

    plt.figure()
    for b in ["BC_TRUST", "BC_ALWAYS_QUERY", "FULL"]:
        g = df[df[col_baseline] == b].sort_values(col_speed)
        if len(g) == 0:
            continue
        x = g[col_speed].astype(float).values
        y = g[ycol].astype(float).values
        e = g[ecol].astype(float).values if (ecol and ecol in g.columns) else None
        plt.errorbar(x, y, yerr=e, marker="o", capsize=3, label=b)
    plt.xlabel("Speed")
    plt.ylabel(metric_base)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out, fname))
    plt.close()
    print("[OK] saved", fname)

plot_metric("totalOverheadMs", "Total BC overhead vs speed", "total_bc_overhead_vs_speed.png")
plot_metric("hitRate", "BC cache hitRate vs speed", "bc_cache_hitrate_vs_speed.png")
plot_metric("queries", "BC queries vs speed", "bc_queries_vs_speed.png")
plot_metric("updates", "BC updates vs speed", "bc_updates_vs_speed.png")

print("[DONE] plots in", out)
