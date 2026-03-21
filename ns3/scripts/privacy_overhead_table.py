import os
import pandas as pd

INP = os.path.expanduser("~/dissertation/ns3/results/privacy_ablation_pack/summary/summary_ci95.csv")
OUT = os.path.expanduser("~/dissertation/ns3/results/privacy_ablation_pack/summary/privacy_overhead.csv")

df = pd.read_csv(INP).set_index("baseline")

def pick_mean(cands):
    for c in cands:
        if c in df.columns:
            return c
    return None

pdr  = pick_mean(["PDR_mean","pdr_mean"])
delay= pick_mean(["avgDelay_mean","delay_mean"])
thr  = pick_mean(["throughput_mean","Throughput_mean"])

rows=[]
A="FULL_NO_PRIVACY"
B="FULL_PRIVACY"

for name, col, direction in [
    ("PDR", pdr, "higher"),
    ("Delay", delay, "lower"),
    ("Throughput", thr, "higher"),
]:
    if col is None:
        continue

    a = df.loc[A, col]
    b = df.loc[B, col]

    # overhead: for delay higher is worse; for PDR/THR lower is worse
    if direction == "lower":
        overhead = ((b - a) / a * 100.0) if a != 0 else float("nan")
    else:
        overhead = ((a - b) / a * 100.0) if a != 0 else float("nan")

    rows.append({
        "metric": name,
        "FULL_NO_PRIVACY_mean": a,
        "FULL_PRIVACY_mean": b,
        "privacy_overhead_%": overhead,
        "note": ("positive = worse (more delay)" if direction=="lower" else "positive = worse (drop from no-privacy)")
    })

out = pd.DataFrame(rows)
out.to_csv(OUT, index=False)
print("[OK] wrote", OUT)
