#!/usr/bin/env bash
set -euo pipefail

cd ~/dissertation
OUT="results_publishable/final_release_$(date +%Y%m%d_%H%M).zip"

# include: publishable plots + summaries + key scripts + scenario code + docs
zip -r "$OUT" \
  results_publishable/baselines_pack \
  ns3/scripts \
  ns3/scenarios/secure_trust_blockchain_v2x.cc \
  docs \
  README.md \
  -x "ns3/results/**" "sumo/output/**" ".git/**"

echo "[OK] created $OUT"
ls -lh "$OUT"
