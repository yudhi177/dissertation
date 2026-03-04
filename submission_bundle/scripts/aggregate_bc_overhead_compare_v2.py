import os, re, glob
import pandas as pd
import numpy as np

RUNS = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare_v2/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare_v2/summary")
os.makedirs(OUT, exist_ok=True)

pat = re.compile(r"^(BC_TRUST|BC_ALWAYS_QUERY|FULL)_probe(\d+)_seed(\d+)\.log$")
bc_pat = re.compile(
    r"\[BC\]\s+queries=(\d+)\s+updates=(\d+)\s+cacheHits=(\d+)\s+cacheMisses=(\d+)\s+hitRate=([0-9.]+)\s+avgQms=([0-9.]+)\s+avgUms=([0-9.]+)"
)

rows = []
for logf in glob.glob(os.path.join(RUNS, "*.log")):
    base = os.path.basename(logf)
    m = pat.match(base)
    if not m:
        continue
    baseline = m.group(1)
    probeMs = int(m.group(2))
    seed = int(m.group(3))

    txt = open(logf, "r", errors="ignore").read()
    mm = bc_pat.search(txt)
    if not mm:
        continue

    queries = int(mm.group(1))
    updates = int(mm.group(2))
    cacheHits = int(mm.group(3))
    cacheMisses = int(mm.group(4))
    hitRate = float(mm.group(5))
    avgQms = float(mm.group(6))
    avgUms = float(mm.group(7))

    totalOverheadMs = queries * avgQms + updates * avgUms

    rows.append({
        "baseline": baseline,
        "probeIntervalMs": probeMs,
        "seed": seed,
        "queries": queries,
        "updates": updates,
        "cacheHits": cacheHits,
        "cacheMisses": cacheMisses,
        "hitRate": hitRate,
        "avgQms": avgQms,
        "avgUms": avgUms,
        "totalOverheadMs": totalOverheadMs,
    })

raw = pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT, "raw.csv"), index=False)

if raw.empty:
    raise SystemExit(f"[ERR] No parsed logs found in {RUNS}")

def ci95(x):
    x = pd.to_numeric(x, errors="coerce").dropna()
    if len(x) <= 1:
        return 0.0
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x))

metrics = ["totalOverheadMs","hitRate","queries","updates","avgQms","avgUms"]

grp = raw.groupby(["baseline","probeIntervalMs"])
summary = grp[metrics].agg(["mean","std","count"])
summary.columns = [f"{a}_{b}" for (a,b) in summary.columns]
summary = summary.reset_index()

# add ci95 columns robustly via merge
for m in metrics:
    ci = grp[m].apply(ci95).reset_index().rename(columns={m: f"{m}_ci95"})
    summary = summary.merge(ci, on=["baseline","probeIntervalMs"], how="left")

summary.to_csv(os.path.join(OUT, "summary_ci95.csv"), index=False)
print("[OK] wrote", os.path.join(OUT, "summary_ci95.csv"))
