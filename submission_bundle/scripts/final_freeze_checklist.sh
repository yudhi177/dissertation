#!/usr/bin/env bash
set -euo pipefail

echo "=== FINAL FREEZE CHECKLIST ==="
echo "[1] Build ns-3"
cd ~/ns-3
./ns3 build

echo "[2] PrintHelp sanity (key flags present)"
./ns3 run "scratch/secure_trust_blockchain_v2x --PrintHelp" | egrep -n "baselineName|seed|trustMaxAgeMs|confWindow|confMinForFast|enableAuthBind|enableMitmAttack|enableRevocation|enablePrivacy|enableBcProbe|enableBCLocalCache" | head -n 60 || true

echo "[3] Run quick publish pack"
~/dissertation/ns3/scripts/make_publishable_results.sh quick

echo "[4] Check publishable outputs exist"
P=~/dissertation/results_publishable/baselines_pack
test -f "$P/summary.csv" && echo "OK summary.csv"
test -f "$P/runs_index.csv" && echo "OK runs_index.csv"
ls -1 "$P"/*.png 2>/dev/null | head -n 20 || echo "WARN: no pngs found"
test -f "$P/revocation_cdf.png" && echo "OK revocation_cdf.png" || echo "WARN revocation_cdf.png missing"
test -f "$P/detect_fp.csv" && echo "OK detect_fp.csv" || echo "WARN detect_fp.csv missing"

echo "[5] Ensure big folders NOT tracked"
cd ~/dissertation
git status --porcelain | head -n 200

echo "=== DONE ==="
