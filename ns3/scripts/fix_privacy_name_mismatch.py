from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 1) Replace names inside the injected privacy block + elsewhere where our CLI lines are
if "g_pseudoRotateSec" in txt:
    txt = txt.replace("g_pseudoRotateIntervalS", "g_pseudoRotateSec")

if "g_linkTimeWindowSec" in txt:
    txt = txt.replace("g_linkWindowS", "g_linkTimeWindowSec")

# 2) Fix CLI flag variable bindings (keep flag names, bind to existing vars)
# (If you prefer, we can also rename flag strings later. For now, just compile.)
txt = re.sub(r'cmd\.AddValue\("pseudoRotateIntervalS"([^;]*),\s*g_pseudoRotateSec\);',
             r'cmd.AddValue("pseudoRotateIntervalS"\1, g_pseudoRotateSec);', txt)

txt = re.sub(r'cmd\.AddValue\("linkWindowS"([^;]*),\s*g_linkTimeWindowSec\);',
             r'cmd.AddValue("linkWindowS"\1, g_linkTimeWindowSec);', txt)

# 3) Ensure g_rotateOnHandover exists (not present in your file currently)
if not re.search(r'\bstatic\s+bool\s+g_rotateOnHandover\b', txt):
    # Insert it near existing privacy globals (after g_enablePrivacy definition if found)
    m = re.search(r'^\s*static\s+bool\s+g_enablePrivacy[^\n]*\n', txt, flags=re.M)
    insert = '\nstatic bool g_rotateOnHandover = true; // added by fix_privacy_name_mismatch\n'
    if m:
        pos = m.end()
        txt = txt[:pos] + insert + txt[pos:]
    else:
        # fallback: insert near top after includes
        m2 = re.search(r'using\s+namespace\s+ns3;\s*\n', txt)
        if m2:
            pos = m2.end()
            txt = txt[:pos] + insert + txt[pos:]
        else:
            txt = insert + txt

p.write_text(txt)
print("[OK] Fixed privacy name mismatches + added g_rotateOnHandover in:", p)
