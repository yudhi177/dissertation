from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/aggregate_publish_pack.py"
txt = p.read_text()

# Add exp key to parser list
txt2 = txt.replace(
    'for key in ["rotations","linkAttempts","linkSuccess","linkSuccessRate"]:',
    'for key in ["rotations","linkAttempts","linkSuccess","linkSuccessRate","linkSuccessRateExp"]:'
)

p.write_text(txt2)
print("[OK] aggregate_publish_pack.py patched to parse linkSuccessRateExp")
