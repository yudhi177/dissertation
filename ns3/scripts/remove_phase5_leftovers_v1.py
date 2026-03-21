from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 1) Remove TrustConfidence() usage blocks that were injected
txt = re.sub(r'\n\s*//\s*PHASE5_CONF_GATE_V1.*?\n\s*\}\s*\n', '\n', txt, flags=re.S)
txt = re.sub(r'\n\s*//\s*PHASE5_FAST_DENY_COUNTER_V2.*?\n\s*\}\s*\n', '\n', txt, flags=re.S)
txt = re.sub(r'^\s*const\s+double\s+conf\s*=\s*TrustConfidence\(id\);\s*\n', '', txt, flags=re.M)
txt = re.sub(r'^\s*const\s+bool\s+confOk\s*=\s*\(\!g_enableTrustConfidence\).*?\n', '', txt, flags=re.M)

# 2) Remove any direct TrustConfidence(...) line remnants
txt = re.sub(r'^\s*.*TrustConfidence\s*\(.*\)\s*;.*\n', '', txt, flags=re.M)

# 3) Remove cmd.AddValue(...) for Phase5 flags
txt = re.sub(r'^\s*cmd\.AddValue\(\s*"enableTrustConfidence".*?\);\s*\n', '', txt, flags=re.M)
txt = re.sub(r'^\s*cmd\.AddValue\(\s*"enableChannelFairness".*?\);\s*\n', '', txt, flags=re.M)
txt = re.sub(r'^\s*cmd\.AddValue\(\s*"badChannelLossThresh".*?\);\s*\n', '', txt, flags=re.M)
txt = re.sub(r'^\s*cmd\.AddValue\(\s*"fairnessPenaltyScaleBad".*?\);\s*\n', '', txt, flags=re.M)

# 4) Remove obsCount init
txt = re.sub(r'^\s*g_obsCount\.assign\(g_nVehicles,\s*0\);\s*\n', '', txt, flags=re.M)

# 5) Remove PrintPhase5Stats call
txt = re.sub(r'^\s*PrintPhase5Stats\(\);\s*\n', '', txt, flags=re.M)

p.write_text(txt)
print("[OK] removed Phase5 leftovers from scratch:", p)
