#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

SIM=6
SEED=1

run_one () {
  local name="$1"; shift
  local csv="/tmp/${name}.csv"
  local evt="/tmp/${name}_events.csv"
  echo
  echo "===== RUN $name ====="
  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --simTime=${SIM} \
    --csvOut=${csv} --eventsOut=${evt} \
    --baselineName=${name} \
    --seed=${SEED} \
    $*"

  ls -lh "${csv}" "${evt}"
  echo "----- SUMMARY LINES -----"
  grep -E "^\[BC\]|\[PRIV\]|\[AUTH\]|\[STALE\]" "${evt}" 2>/dev/null || true
  echo "----- LAST CONSOLE SUMMARY (if present) -----"
}

# 1) PKI ONLY (everything OFF)
run_one "PKI_ONLY" \
  --enableTrustEngineFinal=0 --enableTrustGate=0 \
  --enableBlockchain=0 --enableBCLocalCache=0 --enableBcProbe=0 \
  --enablePrivacy=0 --enableRevocation=0 \
  --attackMode=0 --maliciousRate=0.0

# 2) TRUST ONLY (trust ON, rest OFF)
run_one "TRUST_ONLY" \
  --enableTrustEngineFinal=1 --enableTrustGate=1 \
  --enableBlockchain=0 --enableBCLocalCache=0 --enableBcProbe=0 \
  --enablePrivacy=0 --enableRevocation=0 \
  --attackMode=2 --maliciousRate=0.2

# 3) BC_TRUST (trust ON + blockchain ON + local cache ON, probe OFF)
run_one "BC_TRUST" \
  --enableTrustEngineFinal=1 --enableTrustGate=1 \
  --enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=0 \
  --enablePrivacy=0 --enableRevocation=0 \
  --trustSyncIntervalMs=5000 \
  --attackMode=2 --maliciousRate=0.2

# 4) BC_ALWAYS_QUERY (trust ON + blockchain ON + cache OFF + probe ON)
run_one "BC_ALWAYS_QUERY" \
  --enableTrustEngineFinal=1 --enableTrustGate=1 \
  --enableBlockchain=1 --enableBCLocalCache=0 \
  --enableBcProbe=1 --bcProbeIntervalMs=200 \
  --enablePrivacy=0 --enableRevocation=0 \
  --trustSyncIntervalMs=5000 \
  --attackMode=2 --maliciousRate=0.2

# 5) FULL (trust + blockchain + privacy + revocation + probe ON)
run_one "FULL" \
  --enableTrustEngineFinal=1 --enableTrustGate=1 \
  --enableBlockchain=1 --enableBCLocalCache=1 \
  --enableBcProbe=1 --bcProbeIntervalMs=200 \
  --enablePrivacy=1 --enableRevocation=1 \
  --trustSyncIntervalMs=5000 \
  --attackMode=2 --maliciousRate=0.2

echo
echo "[DONE] Smoke pack complete. Files in /tmp:"
ls -lh /tmp/PKI_ONLY.csv /tmp/TRUST_ONLY.csv /tmp/BC_TRUST.csv /tmp/BC_ALWAYS_QUERY.csv /tmp/FULL.csv 2>/dev/null || true
