from pathlib import Path
import re

targets = [
  Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
  Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

patterns = [
  r"// PHASE5_CONF_FAIR_V1_BEGIN.*?// PHASE5_CONF_FAIR_V1_END\s*",
  r"// PHASE5_CONF_FAIR_V2_BEGIN.*?// PHASE5_CONF_FAIR_V2_END\s*",
  r"// PHASE5_CONF_FAIR_V3_BEGIN.*?// PHASE5_CONF_FAIR_V3_END\s*",
  r"// PHASE5_CONF_FAIR_V4_BEGIN.*?// PHASE5_CONF_FAIR_V4_END\s*",

  r"^\s*cmd\.AddValue\(\"enableTrustConfidence\".*\)\s*;\s*\n",
  r"^\s*cmd\.AddValue\(\"enableChannelFairness\".*\)\s*;\s*\n",
  r"^\s*cmd\.AddValue\(\"badChannelLossThresh\".*\)\s*;\s*\n",
  r"^\s*cmd\.AddValue\(\"fairnessPenaltyScaleBad\".*\)\s*;\s*\n",
  r"^\s*cmd\.AddValue\(\"lossProxy\".*\)\s*;\s*\n",

  r"^\s*g_obsCount\.assign\(g_nVehicles,\s*0\);\s*\n",
  r"^\s*PrintPhase5Stats\(\);\s*\n",

  r"^\s*//\s*PHASE5_CONF_GATE_.*\n",
  r"^.*FAST_DENY_LOW_CONF.*\n",
  r"^\s*g_fastDeniedLowConf\+\+;\s*\n",
]

for p in targets:
  if not p.exists():
    continue

  txt = p.read_text()
  removed = 0

  for pat in patterns:
    txt, n = re.subn(pat, "", txt, flags=re.S | re.M)
    removed += n

  # revert FAST logic if it still contains TrustConfidence()
  txt = re.sub(
    r'^\s*bool\s+fast\s*=.*TrustConfidence.*;\s*$',
    '  bool fast = (trust >= g_trustFastThresh);',
    txt,
    flags=re.M
  )

  p.write_text(txt)
  print(f"[OK] Phase5 purge: {p} removed_hits={removed}")
