from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 1) Add g_linkSuccessExp if missing near g_linkSuccess
if "g_linkSuccessExp" not in txt:
    txt = re.sub(
        r"(static\s+uint64_t\s+g_linkSuccess\s*=\s*0;\s*\n)",
        r"\1static double   g_linkSuccessExp = 0.0; // expected-success accumulator\n",
        txt,
        count=1
    )

# 2) Replace k==0 rule with expected probability update (inside PrivacyRotate)
txt2 = txt
txt2 = re.sub(
    r'if\s*\(\s*k\s*==\s*0\s*\)\s*g_linkSuccess\+\+\s*;',
    r'''{
      // Expected success probability = 1/(k+1)
      const double p = 1.0 / double(k + 1);
      g_linkSuccessExp += p;
      // also keep hard-success count for reference
      if (k == 0) g_linkSuccess++;
    }''',
    txt2,
    count=1
)

if txt2 == txt:
    print("[WARN] Could not find the exact 'if (k == 0) g_linkSuccess++;' line. No change made there.")
txt = txt2

# 3) Improve PrintPrivacyStats to print exp-rate too
if "linkSuccessRateExp" not in txt:
    txt = re.sub(
        r'(const double rate = g_linkAttempts \? \(double\)g_linkSuccess / \(double\)g_linkAttempts : 0\.0;\s*\n)',
        r'\1  const double expRate = g_linkAttempts ? (g_linkSuccessExp / (double)g_linkAttempts) : 0.0;\n',
        txt,
        count=1
    )
    txt = txt.replace(
        '<< " linkSuccessRate=" << rate',
        '<< " linkSuccessRate=" << rate << " linkSuccessRateExp=" << expRate'
    )

p.write_text(txt)
print("[OK] Patched privacy linkability V3 expected-success into:", p)
