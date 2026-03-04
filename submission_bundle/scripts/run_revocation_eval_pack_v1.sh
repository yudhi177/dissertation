#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/revocation_eval"
mkdir -p "$OUTD"

CSV="$OUTD/revoke.csv"
EVT="$OUTD/revoke_events.csv"
LOG="$OUTD/revoke.log"

# FULL baseline must include privacy=1 (baseline asserts)
./ns3 run "scratch/secure_trust_blockchain_v2x \
  --simTime=25 \
  --csvOut=${CSV} \
  --eventsOut=${EVT} \
  --baselineName=FULL \
  --seed=5 \
  --enableTrustEngineFinal=1 \
  --enableBlockchain=1 --enableBCLocalCache=1 \
  --enablePrivacy=1 \
  --enableRevocation=1 \
  --forceRevokeVehicle0=1 --forceRevokeTime=2.0 \
  --revokeSyncIntervalMs=500 \
  --enableBcProbe=1 --bcProbeIntervalMs=200" | tee "$LOG"

echo "[OK] wrote:"
echo " - $CSV"
echo " - $EVT"
echo " - $LOG"
