#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/phase2_security"
RUNS="$OUTD/runs"
mkdir -p "$RUNS"

SIM=20

echo "[1] Rate-limit DoS test (tight rate)"
./ns3 run "scratch/secure_trust_blockchain_v2x \
  --simTime=${SIM} \
  --csvOut=/tmp/p2_rl.csv --eventsOut=/tmp/p2_rl_events.csv \
  --seed=1 \
  --enableAuthProbe=1 --authProbeIntervalMs=50 \
  --enableAuthRateLimit=1 --rlRatePerSec=2.0 --rlBurst=3.0" | tee "$RUNS/p2_rl.log"
cp -f /tmp/p2_rl.csv "$RUNS/"
cp -f /tmp/p2_rl_events.csv "$RUNS/"

echo "[2] Rekey test"
./ns3 run "scratch/secure_trust_blockchain_v2x \
  --simTime=${SIM} \
  --csvOut=/tmp/p2_rekey.csv --eventsOut=/tmp/p2_rekey_events.csv \
  --seed=2 \
  --enableAuthProbe=1 --authProbeIntervalMs=200 \
  --enableRekey=1 --rekeyIntervalMs=1000 --rekeyOnHandover=1" | tee "$RUNS/p2_rekey.log"
cp -f /tmp/p2_rekey.csv "$RUNS/"
cp -f /tmp/p2_rekey_events.csv "$RUNS/"

echo "[3] Anti-downgrade test (FULL-like + trust gate)"
./ns3 run "scratch/secure_trust_blockchain_v2x \
  --simTime=${SIM} \
  --csvOut=/tmp/p2_dg.csv --eventsOut=/tmp/p2_dg_events.csv \
  --baselineName=TRUST_ONLY --seed=3 \
  --enableTrustEngineFinal=1 --enableTrustGate=1 \
  --enableAntiDowngrade=1 \
  --attackMode=2 --maliciousRate=0.2" | tee "$RUNS/p2_dg.log"
cp -f /tmp/p2_dg.csv "$RUNS/"
cp -f /tmp/p2_dg_events.csv "$RUNS/"

echo "[DONE] $RUNS"
