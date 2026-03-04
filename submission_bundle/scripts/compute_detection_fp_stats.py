import sys, re
import pandas as pd

if len(sys.argv) != 3:
    print("Usage: compute_detection_fp_stats.py <events.csv> <out.csv>")
    sys.exit(2)

events = pd.read_csv(sys.argv[1], header=None, names=["t","event"])
pat = re.compile(r"REPORT_RX_RSU.*about=(\d+)")
counts = {}
first_time = {}
detect_time = {}

K = 3  # must match reportTriggerK default unless you override in run

for _, r in events.iterrows():
    ev = str(r["event"])
    m = pat.search(ev)
    if not m:
        continue
    t = float(r["t"])
    accused = int(m.group(1))
    counts[accused] = counts.get(accused, 0) + 1
    first_time.setdefault(accused, t)
    if counts[accused] == K:
        detect_time[accused] = t

rows = []
for accused, c in sorted(counts.items()):
    rows.append({
        "accused": accused,
        "reports": c,
        "first_report_s": first_time.get(accused, None),
        "detect_time_s": detect_time.get(accused, None),
        "detected": int(accused in detect_time),
        "is_malicious_assumed": int(accused == 0),
        "false_positive": int((accused != 0) and (accused in detect_time)),
    })

df = pd.DataFrame(rows)
df.to_csv(sys.argv[2], index=False)
print("[OK] wrote", sys.argv[2])
print(df.head(10).to_string(index=False))
