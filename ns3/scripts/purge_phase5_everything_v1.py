from pathlib import Path
import re

targets = [
  Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
  Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

patterns = [
  # remove marked Phase5 blocks
  r"// PHASE5_CONF_FAIR_V1_BEGIN.*?// PHASE5_CONF_FAIR_V1_END\s*",
  r"// PHASE5_CONF_FAIR_V2_BEGIN.*?// PHASE5_CONF_FAIR_V2_END\s*",

  # remove any duplicated Phase5 globals/helpers that may remain outside markers
  r"\n\s*static\s+bool\s+g_enableTrustConfidence\s*=\s*(true|false)\s*;\s*",
  r"\n\s*static\s+uint64_t\s+g_fastDeniedLowConf\s*=\s*\d+\s*;\s*",
  r"\n\s*static\s+bool\s+g_enableChannelFairness\s*=\s*(true|false)\s*;\s*",
  r"\n\s*static\s+double\s+g_badChannelLossThresh\s*=\s*[-0-9.]+\s*;\s*",
  r"\n\s*static\s+double\s+g_fairnessPenaltyScaleBad\s*=\s*[-0-9.]+\s*;\s*",
  r"\n\s*static\s+uint64_t\s+g_fairnessBadChannelHits\s*=\s*\d+\s*;\s*",
  r"\n\s*static\s+double\s+g_lossProxy\s*=\s*[-0-9.]+\s*;\s*",
  r"\n\s*static\s+std::vector<\s*uint32_t\s*>\s+g_obsCount\s*;\s*",

  # remove helper functions if duplicated
  r"\n\s*static\s+inline\s+double\s+TrustConfidence\s*\(uint32_t\s+id\)\s*\{.*?\n\s*\}\s*",
  r"\n\s*static\s+inline\s+void\s+RecordObservation\s*\(uint32_t\s+id\)\s*\{.*?\n\s*\}\s*",
  r"\n\s*static\s+inline\s+double\s+ApplyFairnessPenaltyScale\s*\(double\s+.*?\)\s*\{.*?\n\s*\}\s*",

  # remove CheckHandover injection marker (if present)
  r"^\s*//\s*PHASE5_CONF_GATE_V1.*?\n",
  r"^\s*//\s*PHASE5_CONF_GATE_V2.*?\n",
]

for p in targets:
  if not p.exists():
    continue
  txt = p.read_text()
  removed_total = 0
  for pat in patterns:
    txt, n = re.subn(pat, "", txt, flags=re.S | re.M)
    removed_total += n
  p.write_text(txt)
  print(f"[OK] purged Phase5 content in {p} (patterns_removed={removed_total})")
