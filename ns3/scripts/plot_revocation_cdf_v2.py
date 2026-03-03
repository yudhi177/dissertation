import sys
import pandas as pd
import matplotlib.pyplot as plt

if len(sys.argv) != 3:
    print("Usage: plot_revocation_cdf_v2.py <cdf.csv> <out.png>")
    raise SystemExit(2)

df = pd.read_csv(sys.argv[1])

xcol = "delay_s" if "delay_s" in df.columns else df.columns[0]
ycol = "cdf" if "cdf" in df.columns else df.columns[-1]

plt.figure()
plt.plot(df[xcol], df[ycol], marker="o")
plt.xlabel("Revocation propagation delay (s)")
plt.ylabel("CDF")
plt.title("Revocation Propagation Delay CDF")
plt.tight_layout()
plt.savefig(sys.argv[2])
print("[OK] saved", sys.argv[2])
