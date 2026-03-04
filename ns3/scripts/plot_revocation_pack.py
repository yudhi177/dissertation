import os
import pandas as pd
import matplotlib.pyplot as plt

INP = os.path.expanduser("~/dissertation/ns3/results/revocation_pack/summary/detect_time_cdf.csv")
OUT = os.path.expanduser("~/dissertation/ns3/results/revocation_pack/plots")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(INP)
plt.figure()
plt.plot(df["detect_time_s"], df["cdf"], marker="o")
plt.xlabel("Detection time (s)")
plt.ylabel("CDF")
plt.title("Revocation detection time CDF (FULL baseline)")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "detect_time_cdf.png"))
plt.close()

print("[OK] plots in", OUT)
