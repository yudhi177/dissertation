from pathlib import Path
import re

targets = [
  Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
  Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

regex_patterns = [
  r"// PHASE5_CONF_FAIR_V1_BEGIN.*?// PHASE5_CONF_FAIR_V1_END\s*",
  r"// PHASE5_CONF_FAIR_V2_BEGIN.*?// PHASE5_CONF_FAIR_V2_END\s*",
  r"// PHASE5_CONF_FAIR_V3_BEGIN.*?// PHASE5_CONF_FAIR_V3_END\s*",

  r'^\s*cmd\.AddValue\("enableTrustConfidence".*?\);\s*$\n?',
  r'^\s*cmd\.AddValue\("enableChannelFairness".*?\);\s*$\n?',
  r'^\s*cmd\.AddValue\("badChannelLossThresh".*?\);\s*$\n?',
  r'^\s*cmd\.AddValue\("fairnessPenaltyScaleBad".*?\);\s*$\n?',
  r'^\s*cmd\.AddValue\("lossProxy".*?\);\s*$\n?',

  r'^\s*g_obsCount\.assign\(g_nVehicles,\s*0\);\s*$\n?',
  r'^\s*PrintPhase5Stats\(\);\s*$\n?',

  r'\n\s*static\s+void\s+PrintPhase5Stats\s*\(\s*\)\s*\{.*?\n\s*\}\s*\n',
  r'\n\s*static\s+inline\s+double\s+TrustConfidence\s*\(.*?\)\s*\{.*?\n\s*\}\s*\n',
  r'\n\s*static\s+inline\s+void\s+RecordObservation\s*\(.*?\)\s*\{.*?\n\s*\}\s*\n',
  r'\n\s*static\s+inline\s+double\s+ApplyFairnessPenaltyScale\s*\(.*?\)\s*\{.*?\n\s*\}\s*\n',

  r'^.*FAST_DENY_LOW_CONF.*\n?',
  r'^\s*g_fastDeniedLowConf\+\+;\s*\n?',
]

def remove_orphan_blocks(lines):
  i = 0
  out = []
  removed = 0
  while i < len(lines):
    line = lines[i]
    if line.strip() == "{":
      j = i - 1
      while j >= 0 and lines[j].strip() == "":
        j -= 1
      prev = lines[j].strip() if j >= 0 else ""
      looks_like_opener = (
        prev.endswith(")") or
        prev.startswith("struct") or
        prev.startswith("class") or
        prev.startswith("namespace") or
        prev.endswith(":")
      )
      if not looks_like_opener:
        depth = 0
        k = i
        while k < len(lines):
          depth += lines[k].count("{")
          depth -= lines[k].count("}")
          k += 1
          if depth <= 0:
            break
        removed += 1
        i = k
        continue
    out.append(line)
    i += 1
  return out, removed

for p in targets:
  if not p.exists():
    continue
  txt = p.read_text()

  removed_regex = 0
  for pat in regex_patterns:
    txt, n = re.subn(pat, "", txt, flags=re.S | re.M)
    removed_regex += n

  # revert FAST selection to simple default (removes TrustConfidence deps)
  txt = re.sub(
    r'^\s*bool\s+fast\s*=.*g_trustFastThresh.*;\s*$',
    '  bool fast = (trust >= g_trustFastThresh);',
    txt,
    flags=re.M
  )
  txt = re.sub(r'^.*TrustConfidence\s*\(.*\).*\n?', '', txt, flags=re.M)

  lines = txt.splitlines(True)
  lines, removed_orphans = remove_orphan_blocks(lines)
  txt = "".join(lines)

  p.write_text(txt)
  print(f"[OK] Phase5 purge v2: {p}  regex_removed={removed_regex}  orphan_blocks_removed={removed_orphans}")
