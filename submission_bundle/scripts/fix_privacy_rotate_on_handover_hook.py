from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 1) Remove the broken hook
txt = re.sub(r"// PRIVACY_HO_ROTATE_HOOK_BEGIN.*?// PRIVACY_HO_ROTATE_HOOK_END\s*", "", txt, flags=re.S)

# 2) Locate FinishHandover signature and grab first param name
sig = re.search(r'\bvoid\s+FinishHandover\s*\(\s*uint32_t\s+(\w+)\s*,', txt)
if not sig:
    raise SystemExit("[ERR] Could not find FinishHandover(uint32_t <name>, ...) signature.")

veh_var = sig.group(1)

# 3) Extract FinishHandover function block (best-effort with braces)
start = sig.start()
brace_open = txt.find('{', sig.end())
if brace_open < 0:
    raise SystemExit("[ERR] Could not find '{' after FinishHandover signature.")

# Find matching closing brace for the function
depth = 0
end = None
for i in range(brace_open, len(txt)):
    c = txt[i]
    if c == '{':
        depth += 1
    elif c == '}':
        depth -= 1
        if depth == 0:
            end = i + 1
            break
if end is None:
    raise SystemExit("[ERR] Could not find end of FinishHandover() block.")

func = txt[brace_open:end]

# 4) Find HO_DONE inside this function block
ho = func.find("HO_DONE")
if ho < 0:
    raise SystemExit("[ERR] HO_DONE not found inside FinishHandover() block.")

# 5) Insert hook AFTER the statement containing HO_DONE finishes (after next semicolon)
semi = func.find(";\n", ho)
if semi < 0:
    semi = func.find(";\r\n", ho)
if semi < 0:
    # fallback: after ');'
    semi = func.find(");\n", ho)
    if semi >= 0:
        semi += 1
if semi < 0:
    raise SystemExit("[ERR] Could not locate statement end ';' after HO_DONE.")

insert_at = semi + 2  # after ";\n" (or close enough)

hook = f'''
// PRIVACY_HO_ROTATE_HOOK_BEGIN
  // Rotate pseudonym on handover completion (privacy boost at RSU boundary)
  if (g_enablePrivacy && g_rotateOnHandover)
  {{
    PrivacyRotate({veh_var}, "HO_DONE");
  }}
// PRIVACY_HO_ROTATE_HOOK_END
'''

func2 = func[:insert_at] + hook + func[insert_at:]
txt2 = txt[:brace_open] + func2 + txt[end:]

p.write_text(txt2)
print(f"[OK] Reinserted HO_DONE pseudonym rotation hook after statement end. Using veh var: {veh_var}")
