import os, glob
import pandas as pd
import numpy as np

RUNS = os.path.expanduser("~/dissertation/ns3/results/revocation_pack/runs")
OUTD = os.path.expanduser("~/dissertation/ns3/results/revocation_pack/summary")
os.makedirs(OUTD, exist_ok=True)

fps = sorted(glob.glob(os.path.join(RUNS, "*_detect_fp.csv")))
if not fps:
    raise SystemExit(f"[ERR] No *_detect_fp.csv found in {RUNS}")

rows=[]
for f in fps:
    df = pd.read_csv(f)
    # expected columns: accused,reports,first_report_s,detect_time_s,detected,is_malicious_assumed,false_positive
    if df.empty:
        continue
    df["source"] = os.path.basename(f)
    rows.append(df)

all_df = pd.concat(rows, ignore_index=True)
all_df.to_csv(os.path.join(OUTD, "detect_fp_all.csv"), index=False)

# Focus on malicious detection times (vehicle0 is forced malicious in your setup)
mal = all_df[(all_df["is_malicious_assumed"]==1) & (all_df["detected"]==1)]
det_times = pd.to_numeric(mal["detect_time_s"], errors="coerce").dropna().values

# false positives
fp_df = all_df[all_df["false_positive"]==1]

# Build empirical CDF for detection time
det_times_sorted = np.sort(det_times)
cdf = pd.DataFrame({
    "detect_time_s": det_times_sorted,
    "cdf": np.arange(1, len(det_times_sorted)+1)/max(1,len(det_times_sorted))
})
cdf.to_csv(os.path.join(OUTD, "detect_time_cdf.csv"), index=False)

# Summary stats
summary = {
    "n_runs_detect_fp_files": len(fps),
    "n_detected_malicious": int(len(det_times_sorted)),
    "detect_time_mean_s": float(np.mean(det_times_sorted)) if len(det_times_sorted) else np.nan,
    "detect_time_median_s": float(np.median(det_times_sorted)) if len(det_times_sorted) else np.nan,
    "false_positive_count": int(len(fp_df)),
}
pd.DataFrame([summary]).to_csv(os.path.join(OUTD, "summary.csv"), index=False)
print("[OK] wrote summary + CDF in", OUTD)
