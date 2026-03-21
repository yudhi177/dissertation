from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# remove any combined one-liner: close + PrintPhase5Stats
txt = re.sub(r'^\s*if\s*\(g_evt\.is_open\(\)\)\s*g_evt\.close\(\)\s*;\s*PrintPhase5Stats\(\)\s*;\s*$\n',
             '', txt, flags=re.M)

# remove any standalone PrintPhase5Stats call
txt = re.sub(r'^\s*PrintPhase5Stats\(\)\s*;\s*$\n', '', txt, flags=re.M)

# normalize event close (avoid misleading indentation)
txt = re.sub(r'^\s*if\s*\(g_evt\.is_open\(\)\)\s*g_evt\.close\(\)\s*;\s*$',
             '  if (g_evt.is_open()) { g_evt.close(); }', txt, flags=re.M)

p.write_text(txt)
print("[OK] removed broken PrintPhase5Stats calls + fixed close():", p)
