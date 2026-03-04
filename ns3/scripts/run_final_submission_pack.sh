#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/final_submission_pack"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

SEEDS=(1 2 3 4 5)

# ---------
# 1) Baselines (short sanity)
# ---------
SIM_BASE=10
for seed in "${SEEDS[@]}"; do
  for b in PKI_ONLY TRUST_ONLY BC_TRUST BC_ALWAYS_QUERY FULL; do
    tag="BASE_${b}_seed${seed}"
    csv="$RUNS/${tag}.csv"
    evt="$RUNS/${tag}_events.csv"
    log="$RUNS/${tag}.log"

    # baseline-specific switches
    case "$b" in
      PKI_ONLY)
        extra=(--enableTrustEngineFinal=0 --enableTrustGate=0 --enableBlockchain=0 --enableBCLocalCache=0 --enableBcProbe=0 --enablePrivacy=0 --enableRevocation=0 --attackMode=0 --maliciousRate=0.0)
        ;;
      TRUST_ONLY)
        extra=(--enableTrustEngineFinal=1 --enableTrustGate=1 --enableBlockchain=0 --enableBCLocalCache=0 --enableBcProbe=0 --enablePrivacy=0 --enableRevocation=0 --attackMode=2 --maliciousRate=0.2)
        ;;
      BC_TRUST)
        extra=(--enableTrustEngineFinal=1 --enableTrustGate=1 --enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=0 --enablePrivacy=0 --enableRevocation=0 --attackMode=2 --maliciousRate=0.2)
        ;;
      BC_ALWAYS_QUERY)
        extra=(--enableTrustEngineFinal=1 --enableTrustGate=1 --enableBlockchain=1 --enableBCLocalCache=0 --enableBcProbe=1 --bcProbeIntervalMs=200 --enablePrivacy=0 --enableRevocation=0 --attackMode=2 --maliciousRate=0.2)
        ;;
      FULL)
        extra=(--enableTrustEngineFinal=1 --enableTrustGate=1 --enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=1 --bcProbeIntervalMs=200 --enablePrivacy=1 --enableRevocation=1 --attackMode=2 --maliciousRate=0.2)
        ;;
    esac

    ./ns3 run "scratch/secure_trust_blockchain_v2x \
      --simTime=${SIM_BASE} \
      --csvOut=${csv} --eventsOut=${evt} \
      --baselineName=${b} --seed=${seed} \
      ${extra[*]}" | tee "$log"

    echo "[OK] $tag"
  done
done

# ---------
# 2) Δmax stale tradeoff (BC_TRUST)
# ---------
SIM_DMAX=20
DMAX=(0 200 500 1000 2000 5000)

for seed in "${SEEDS[@]}"; do
  for d in "${DMAX[@]}"; do
    tag="DMAX_${d}_seed${seed}"
    csv="$RUNS/${tag}.csv"
    evt="$RUNS/${tag}_events.csv"
    log="$RUNS/${tag}.log"

    ./ns3 run "scratch/secure_trust_blockchain_v2x \
      --simTime=${SIM_DMAX} \
      --csvOut=${csv} --eventsOut=${evt} \
      --baselineName=BC_TRUST --seed=${seed} \
      --enableTrustEngineFinal=1 --enableTrustGate=1 \
      --enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=0 \
      --enablePrivacy=0 --enableRevocation=0 \
      --trustSyncIntervalMs=60000 \
      --trustMaxAgeMs=${d} \
      --attackMode=2 --maliciousRate=0.2" | tee "$log"

    echo "[OK] $tag"
  done
done

# ---------
# 3) Auth security pack (OK / MITM / REPLAY)
# ---------
SIM_AUTH=20
SCEN=(AUTH_OK AUTH_MITM AUTH_REPLAY)
MITM=(0 1 0)
REPLAY=(0 0 1)

for i in "${!SCEN[@]}"; do
  scen="${SCEN[$i]}"
  mitm="${MITM[$i]}"
  replay="${REPLAY[$i]}"
  for seed in "${SEEDS[@]}"; do
    tag="${scen}_seed${seed}"
    csv="$RUNS/${tag}.csv"
    evt="$RUNS/${tag}_events.csv"
    log="$RUNS/${tag}.log"

    ./ns3 run "scratch/secure_trust_blockchain_v2x \
      --simTime=${SIM_AUTH} \
      --csvOut=${csv} --eventsOut=${evt} \
      --seed=${seed} \
      --enableAuthBind=1 \
      --enableAuthProbe=1 --authProbeIntervalMs=200 \
      --enableMitmAttack=${mitm} \
      --enableAuthReplayAttack=${replay} --authReplayEveryN=3" | tee "$log"

    echo "[OK] $tag"
  done
done

echo "[DONE] Final submission pack in: $RUNS"
