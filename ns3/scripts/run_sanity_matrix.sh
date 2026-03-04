#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/sanity_matrix"
mkdir -p "$OUTD"

SIM=8
SEED=1

run_one () {
  local name="$1"; shift
  echo "[RUN] $name"
  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --simTime=${SIM} \
    --csvOut=${OUTD}/${name}.csv \
    --eventsOut=${OUTD}/${name}_events.csv \
    --seed=${SEED} \
    --baselineName=${name} \
    $*"
  echo "[OK] $name"
}

run_one PKI_ONLY \
  --enableTrustEngineFinal=0 --enableTrustGate=0 \
  --enableBlockchain=0 --enableBCLocalCache=0 --enableBcProbe=0 \
  --enablePrivacy=0 --enableRevocation=0

run_one TRUST_ONLY \
  --enableTrustEngineFinal=1 --enableTrustGate=1 \
  --enableBlockchain=0 --enableBCLocalCache=0 --enableBcProbe=0 \
  --enablePrivacy=0 --enableRevocation=0

run_one BC_TRUST \
  --enableTrustEngineFinal=1 --enableTrustGate=1 \
  --enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=1 \
  --enablePrivacy=0 --enableRevocation=0 \
  --bcProbeIntervalMs=200

run_one BC_ALWAYS_QUERY \
  --enableTrustEngineFinal=1 --enableTrustGate=1 \
  --enableBlockchain=1 --enableBCLocalCache=0 --enableBcProbe=1 \
  --enablePrivacy=0 --enableRevocation=0 \
  --bcProbeIntervalMs=200

run_one FULL \
  --enableTrustEngineFinal=1 --enableTrustGate=1 \
  --enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=1 \
  --enablePrivacy=1 --enableRevocation=1 \
  --bcProbeIntervalMs=200

echo "[DONE] $OUTD"
