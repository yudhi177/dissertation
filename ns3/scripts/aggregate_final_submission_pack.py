import os, re, glob
import numpy as np
import pandas as pd

RUNS = os.path.expanduser("~/dissertation/ns3/results/final_submission_pack/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/final_submission_pack/summary")
os.makedirs(OUT, exist_ok=True)

def ci95(s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) <= 1:
        return 0.0
    return 1.96 * s.std(ddof=1) / np.sqrt(len(s))

# ------------------
# A) Baselines
# ------------------
pat_base = re.compile(r"^BASE_(PKI_ONLY|TRUST_ONLY|BC_TRUST|BC_ALWAYS_QUERY|FULL)_seed(\d+)\.csv$")
rows=[]
for f in glob.glob(os.path.join(RUNS,"BASE_*_seed*.csv")):
    m=pat_base.match(os.path.basename(f))
    if not m: 
        continue
    baseline=m.group(1); seed=int(m.group(2))
    df=pd.read_csv(f)
    num=df.select_dtypes(include=[np.number]).mean(numeric_only=True).to_dict()
    row={"baseline":baseline,"seed":seed}
    row.update(num)
    rows.append(row)

raw=pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT,"baseline_raw.csv"),index=False)

if not raw.empty:
    metrics=[c for c in raw.columns if c not in ("baseline","seed")]
    grp=raw.groupby("baseline")
    mean=grp[metrics].mean(numeric_only=True).add_suffix("_mean")
    std =grp[metrics].std(numeric_only=True, ddof=1).add_suffix("_std")
    cnt =grp[metrics].count().add_suffix("_count")
    ci  =grp[metrics].agg(ci95).add_suffix("_ci95")
    out=pd.concat([mean,std,cnt,ci],axis=1).reset_index()
    out.to_csv(os.path.join(OUT,"baseline_summary_ci95.csv"),index=False)
    print("[OK] baseline_summary_ci95.csv")
else:
    print("[WARN] No baseline raw rows found")

# ------------------
# B) DMAX
# ------------------
pat_dmax = re.compile(r"^DMAX_(\d+)_seed(\d+)\.csv$")
stale_pat = re.compile(r"\[STALE\].*maxAgeMs=(\d+).*staleChecks=(\d+).*staleMismatch=(\d+).*mismatchRate=([0-9.]+)")

rows=[]
for f in glob.glob(os.path.join(RUNS,"DMAX_*_seed*.csv")):
    m=pat_dmax.match(os.path.basename(f))
    if not m:
        continue
    dmax=int(m.group(1)); seed=int(m.group(2))
    df=pd.read_csv(f)
    num=df.select_dtypes(include=[np.number]).mean(numeric_only=True).to_dict()

    log=os.path.join(RUNS,f"DMAX_{dmax}_seed{seed}.log")
    mismatch=np.nan; checks=np.nan
    if os.path.exists(log):
        t=open(log,"r",errors="ignore").read()
        mm=stale_pat.search(t)
        if mm:
            mismatch=float(mm.group(4))
            checks=float(mm.group(2))

    row={"trustMaxAgeMs":dmax,"seed":seed,"staleMismatchRate":mismatch,"staleChecks":checks}
    row.update(num)
    rows.append(row)

raw=pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT,"dmax_raw.csv"),index=False)

if not raw.empty:
    metrics=[c for c in raw.columns if c not in ("trustMaxAgeMs","seed")]
    grp=raw.groupby("trustMaxAgeMs")
    mean=grp[metrics].mean(numeric_only=True).add_suffix("_mean")
    std =grp[metrics].std(numeric_only=True, ddof=1).add_suffix("_std")
    cnt =grp[metrics].count().add_suffix("_count")
    ci  =grp[metrics].agg(ci95).add_suffix("_ci95")
    out=pd.concat([mean,std,cnt,ci],axis=1).reset_index()
    out.to_csv(os.path.join(OUT,"dmax_summary_ci95.csv"),index=False)
    print("[OK] dmax_summary_ci95.csv")
else:
    print("[WARN] No dmax rows found")

# ------------------
# C) Auth Security Pack (parse logs)
# ------------------
pat_auth = re.compile(r"^(AUTH_OK|AUTH_MITM|AUTH_REPLAY)_seed(\d+)\.log$")
auth_pat = re.compile(r"\[AUTH\]\s+ok=(\d+)\s+fail=(\d+)\s+mitmFail=(\d+)\s+replayFail=(\d+)")

rows=[]
for logf in glob.glob(os.path.join(RUNS,"AUTH_*_seed*.log")):
    m=pat_auth.match(os.path.basename(logf))
    if not m:
        continue
    scen=m.group(1); seed=int(m.group(2))
    t=open(logf,"r",errors="ignore").read()
    mm=auth_pat.search(t)
    if not mm:
        continue
    ok=int(mm.group(1)); fail=int(mm.group(2))
    mitmFail=int(mm.group(3)); replayFail=int(mm.group(4))
    total=ok+fail
    rows.append({
        "scenario":scen,"seed":seed,
        "authOk":ok,"authFail":fail,
        "mitmFail":mitmFail,"replayFail":replayFail,
        "totalHandshakes":total,
        "successRate": (ok/total) if total>0 else np.nan,
        "failRate": (fail/total) if total>0 else np.nan,
    })

raw=pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT,"auth_raw.csv"),index=False)

if not raw.empty:
    metrics=[c for c in raw.columns if c not in ("scenario","seed")]
    grp=raw.groupby("scenario")
    mean=grp[metrics].mean(numeric_only=True).add_suffix("_mean")
    std =grp[metrics].std(numeric_only=True, ddof=1).add_suffix("_std")
    cnt =grp[metrics].count().add_suffix("_count")
    ci  =grp[metrics].agg(ci95).add_suffix("_ci95")
    out=pd.concat([mean,std,cnt,ci],axis=1).reset_index()
    out.to_csv(os.path.join(OUT,"auth_summary_ci95.csv"),index=False)
    print("[OK] auth_summary_ci95.csv")
else:
    print("[WARN] No auth parsed rows found")
