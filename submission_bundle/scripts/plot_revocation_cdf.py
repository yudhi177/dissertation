import sys
import pandas as pd
import matplotlib.pyplot as plt

if len(sys.argv) != 3:
    print("Usage: plot_revocation_cdf.py <cdf.csv> <out.png>")
    raise SystemExit(2)

df = pd.read_csv(sys.argv[1])
plt.figure()
plt.plot(df["delay_s"], df["cdf"], marker="o")
plt.xlabel("Revocation propagation delay (s)")
plt.ylabel("CDF")
plt.title("Revocation Propagation Delay CDF")
plt.tight_layout()
plt.savefig(sys.argv[2])
print("[OK] saved", sys.argv[2])
