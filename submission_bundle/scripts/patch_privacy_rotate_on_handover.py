from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# remove old hook if exists
txt = re.sub(r"// PRIVACY_HO_ROTATE_HOOK_BEGIN.*?// PRIVACY_HO_ROTATE_HOOK_END\s*", "", txt, flags=re.S)

# strategy: after the first occurrence of writing/logging HO_DONE, insert hook
# We match a line that contains "HO_DONE" inside an event log call or string.
pat = re.compile(r'^(.*HO_DONE.*\n)', re.M)

m = pat.search(txt)
if not m:
    raise SystemExit("[ERR] Could not find a line containing HO_DONE to hook into.")

insert_pos = m.end()

hook = r'''
// PRIVACY_HO_ROTATE_HOOK_BEGIN
  // Rotate pseudonym on handover completion (privacy boost at RSU boundary)
  if (g_enablePrivacy && g_rotateOnHandover)
  {
    // veh id expected to be in-scope as 'id' or 'v' or 'vehId'
    // We'll try the common variable 'id' first; if compile fails, we adjust.
    PrivacyRotate(id, "HO_DONE");
  }
// PRIVACY_HO_ROTATE_HOOK_END
'''

txt = txt[:insert_pos] + hook + txt[insert_pos:]
p.write_text(txt)
print("[OK] Inserted HO_DONE pseudonym rotation hook into:", p)
