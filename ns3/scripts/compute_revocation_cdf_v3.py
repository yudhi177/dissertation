import sys, re
import pandas as pd

if len(sys.argv) != 3:
    print("Usage: compute_revocation_cdf_v3.py <events.csv> <out.csv>")
    sys.exit(2)

path_in, path_out = sys.argv[1], sys.argv[2]

# Read with header auto-detect: if first token is non-numeric ("time"), treat first row as header
with open(path_in, "r", errors="ignore") as f:
    first = f.readline().strip().split(",")[0]

has_header = False
try:
    float(first)
except:
    has_header = True

if has_header:
    df = pd.read_csv(path_in)  # expects columns like time,event
    # normalize names
    cols = [c.strip().lower() for c in df.columns]
    df.columns = cols
    tcol = "time" if "time" in cols else cols[0]
    ecol = "event" if "event" in cols else cols[1]
    df = df[[tcol, ecol]].rename(columns={tcol:"t", ecol:"event"})
else:
    df = pd.read_csv(path_in, header=None, names=["t","event"])

# coerce numeric time
df["t"] = pd.to_numeric(df["t"], errors="coerce")
df = df.dropna(subset=["t"])

issue_t = None
delays = []

delay_pat = re.compile(r"delay=([0-9\.]+)")

for _, r in df.iterrows():
    ev = str(r["event"])
    t = float(r["t"])

    if "REVOKE_ISSUE" in ev and issue_t is None:
        issue_t = t

    if "REVOKE_APPLY" in ev and issue_t is not None:
        # prefer delay= field if present and >0, else compute from timestamps
        m = delay_pat.search(ev)
        if m:
            d = float(m.group(1))
            if d > 0:
                delays.append(d)
                continue
        delays.append(t - issue_t)

delays = sorted([d for d in delays if d >= 0])

out = pd.DataFrame({"delay_s": delays})
if len(out) > 0:
    out["cdf"] = (out.index + 1) / len(out)
else:
    out["cdf"] = []

out.to_csv(path_out, index=False)
print("[OK] wrote", path_out, "n=", len(out))
