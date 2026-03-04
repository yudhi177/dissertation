from pathlib import Path
import re

# Your real source file
p = Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 1) Mark legacy counters as unused (if present)
txt = re.sub(r'\bstatic\s+uint64_t\s+g_trustCacheHits\s*=\s*0\s*;',
             'static uint64_t g_trustCacheHits __attribute__((unused)) = 0;', txt)

txt = re.sub(r'\bstatic\s+uint64_t\s+g_trustCacheMiss\s*=\s*0\s*;',
             'static uint64_t g_trustCacheMiss __attribute__((unused)) = 0;', txt)

# 2) Mark TrustEvidenceGood as unused (if present)
# Handles: static void TrustEvidenceGood(uint32_t sender)
txt = re.sub(r'\bstatic\s+void\s+TrustEvidenceGood\s*\(',
             'static void TrustEvidenceGood __attribute__((unused)) (', txt)

p.write_text(txt)
print("[OK] Marked unused vars/functions to silence warnings in:", p)
