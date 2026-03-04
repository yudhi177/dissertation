import os, re, glob
import pandas as pd
import numpy as np

RUNS = os.path.expanduser("~/dissertation/ns3/results/auth_security_pack/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/auth_security_pack/summary")
os.makedirs(OUT, exist_ok=True)

pat = re.compile(r"^(AUTH_OK|AUTH_MITM|AUTH_REPLAY)_seed(\d+)\.log$")
auth_pat = re.compile(r"\[AUTH\]\s+ok=(\d+)\s+fail=(\d+)\s+mitmFail=(\d+)\s+replayFail=(\d+)")

rows=[]
for logf in glob.glob(os.path.join(RUNS, "*.log")):
    base=os.path.basename(logf)
    m=pat.match(base)
    if not m:
        continue
    scen=m.group(1)
    seed=int(m.group(2))
    txt=open(logf,"r",errors="ignore").read()
    mm=auth_pat.search(txt)
    if not mm:
        continue

    ok=int(mm.group(1)); fail=int(mm.group(2))
    mitmFail=int(mm.group(3)); replayFail=int(mm.group(4))
    total = ok + fail

    rows.append({
        "scenario": scen, "seed": seed,
        "authOk": ok, "authFail": fail,
        "mitmFail": mitmFail, "replayFail": replayFail,
        "totalHandshakes": total,
        "successRate": (ok/total) if total>0 else np.nan,
        "failRate": (fail/total) if total>0 else np.nan,
    })

raw=pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT,"raw.csv"),index=False)

if raw.empty:
    raise SystemExit(f"[ERR] No parsed logs found in {RUNS}")

def ci95(x):
    x=pd.to_numeric(x,errors="coerce").dropna()
    if len(x)<=1: return 0.0
    return 1.96*x.std(ddof=1)/np.sqrt(len(x))

metrics=[c for c in raw.columns if c not in ("scenario","seed")]

mean_df = raw.groupby("scenario")[metrics].mean().add_suffix("_mean")
std_df  = raw.groupby("scenario")[metrics].std(ddof=1).add_suffix("_std")
cnt_df  = raw.groupby("scenario")[metrics].count().add_suffix("_count")
ci_df   = raw.groupby("scenario")[metrics].apply(lambda g: g.apply(ci95)).add_suffix("_ci95")

out = pd.concat([mean_df, std_df, cnt_df, ci_df], axis=1).reset_index()
out.to_csv(os.path.join(OUT,"summary_ci95.csv"),index=False)
print("[OK] wrote", os.path.join(OUT,"summary_ci95.csv"))
