from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # (A) freshOk unused warning: keep logic but silence with (void)freshOk;
    # Match common pattern: const bool freshOk = (ageMs <= g_trustMaxAgeMs);
    txt = re.sub(
        r'(^\s*const\s+bool\s+freshOk\s*=\s*\(.*?g_trustMaxAgeMs.*?\)\s*;\s*$)',
        r'\1\n  (void)freshOk;',
        txt,
        flags=re.M
    )

    # (B) AuthInitKeys defined-but-not-used: mark function unused safely
    # Convert: static void AuthInitKeys(...)  -> static void __attribute__((unused)) AuthInitKeys(...)
    txt = re.sub(
        r'^\s*static\s+void\s+AuthInitKeys\s*\(',
        'static void __attribute__((unused)) AuthInitKeys(',
        txt,
        flags=re.M
    )

    p.write_text(txt)
    print("[OK] cleaned warnings in:", p)
