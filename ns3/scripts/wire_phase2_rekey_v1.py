from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Add a periodic timer function if not exists
if "static void RekeyTick()" not in txt:
    anchor = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not anchor:
        raise SystemExit("[ERR] using namespace ns3 not found")
    ins = anchor.end()
    helper = r'''
static void RekeyTick()
{
  if (!g_enableRekey) return;

  // lightweight: count rekeys between a few pairs (sender 0 -> receiver 1 like auth probes)
  // In real FS, you already generate new ECDH each handshake; this models policy + overhead.
  RekeyEvent(0, 1);

  Simulator::Schedule(MilliSeconds(g_rekeyIntervalMs), &RekeyTick);
}
'''
    txt = txt[:ins] + helper + txt[ins:]

# Schedule RekeyTick() after cmd.Parse if not scheduled
if "Simulator::Schedule(MilliSeconds(g_rekeyIntervalMs), &RekeyTick);" not in txt:
    m = re.search(r"cmd\.Parse\(argc,\s*argv\);\s*\n", txt)
    if not m:
        raise SystemExit("[ERR] cmd.Parse(argc, argv) not found")
    pos = m.end()
    hook = (
        "  // PHASE2: start rekey policy timer\n"
        "  if (g_enableRekey)\n"
        "  {\n"
        "    Simulator::Schedule(MilliSeconds(g_rekeyIntervalMs), &RekeyTick);\n"
        "  }\n"
    )
    txt = txt[:pos] + hook + txt[pos:]

p.write_text(txt)
print("[OK] added RekeyTick() + schedule")
