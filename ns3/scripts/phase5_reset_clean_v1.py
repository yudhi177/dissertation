from pathlib import Path
import re

targets = [
  Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
  Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

RM_BLOCKS = [
  r"//\s*PHASE5_CONF_FAIR_V1_BEGIN.*?//\s*PHASE5_CONF_FAIR_V1_END\s*",
  r"//\s*PHASE5_CONF_FAIR_V2_BEGIN.*?//\s*PHASE5_CONF_FAIR_V2_END\s*",
  r"//\s*PHASE5_CONF_FAIR_V3_BEGIN.*?//\s*PHASE5_CONF_FAIR_V3_END\s*",
  r"//\s*PHASE5_CONF_FAIR_V4_BEGIN.*?//\s*PHASE5_CONF_FAIR_V4_END\s*",
]

RM_LEFT = [
  r"\n\s*//\s*PHASE5_CONF_GATE_V1.*?\n\s*\}\s*\n",
  r"\n\s*//\s*PHASE5_FAST_DENY_COUNTER_V2.*?\n\s*\}\s*\n",
  r"\n\s*//\s*PHASE5_FAST_DENY_COUNTER_V3.*?\n\s*\}\s*\n",
  r"\n\s*//\s*PHASE5_FAST_DENY_COUNTER_V4.*?\n\s*\}\s*\n",

  r"^\s*cmd\.AddValue\(\s*\"enableTrustConfidence\".*?\);\s*\n",
  r"^\s*cmd\.AddValue\(\s*\"enableChannelFairness\".*?\);\s*\n",
  r"^\s*cmd\.AddValue\(\s*\"badChannelLossThresh\".*?\);\s*\n",
  r"^\s*cmd\.AddValue\(\s*\"fairnessPenaltyScaleBad\".*?\);\s*\n",

  r"^\s*g_obsCount\.assign\(g_nVehicles,\s*0\);\s*\n",
  r"^\s*PrintPhase5Stats\(\);\s*\n",
]

for p in targets:
  if not p.exists():
    continue
  txt = p.read_text()

  for pat in RM_BLOCKS:
    txt = re.sub(pat, "", txt, flags=re.S)
  for pat in RM_LEFT:
    txt = re.sub(pat, "", txt, flags=re.M|re.S)

  # fix misleading indentation if exists
  txt = re.sub(r"^\s*if\s*\(g_evt\.is_open\(\)\)\s*g_evt\.close\(\)\s*;\s*$",
               "  if (g_evt.is_open()) { g_evt.close(); }",
               txt, flags=re.M)

  p.write_text(txt)
  print("[OK] Phase5 cleaned:", p)
