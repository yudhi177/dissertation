#!/usr/bin/env bash
set -euo pipefail

NS3_DIR="$HOME/ns-3"
OUT_BASE="$HOME/dissertation/ns3/results/final_comparison/runs"
SEEDS=(1 2 3 4 5)

# Standard experiment params
NVEH=30
SIMTIME=20

# Crypto params (only for scenarios that support them)
CRYPTO_TX=200
CRYPTO_RX=200

# Full integrated params
MAL=0.2
BLOCK=1000
MINE=50
FAST=0.7
MIN=0.3
REPLAY=1
REPLAY_EVERY=300

cd "$NS3_DIR"

run_scenario () {
  local key="$1"
  local scen="$2"
  local args_builder="$3"

  echo "=== Scenario: ${key} (${scen}) ==="
  ln -sf "$HOME/dissertation/ns3/scenarios/${scen}.cc" "scratch/${scen}.cc"
  ./ns3 build

  for seed in "${SEEDS[@]}"; do
    local csv_out="${OUT_BASE}/${key}_seed_${seed}.csv"
    echo "Running ${key}, seed=${seed}"

    # build args per scenario
    local args
    args=$(eval "${args_builder}")

    ./ns3 run "scratch/${scen} --RngRun=${seed} ${args} --csvOut=${csv_out}" >/dev/null
  done
}

# 1) Baseline (urban_v2x): ONLY nVehicles + simTime + csvOut
run_scenario "baseline" "urban_v2x" 'echo "--nVehicles='"${NVEH}"' --simTime='"${SIMTIME}"'"'

# 2) Secure (secure_v2x): usually supports cryptoDelayUsTx/Rx + replay args
# If secure_v2x rejects replay args, we will remove them after seeing its help output.
run_scenario "secure" "secure_v2x" 'echo "--nVehicles='"${NVEH}"' --simTime='"${SIMTIME}"' --cryptoDelayUsTx='"${CRYPTO_TX}"' --cryptoDelayUsRx='"${CRYPTO_RX}"'"'

# 3) Blockchain-only (blockchain_trust_v2x): supports cryptoDelayUsTx/Rx (per your earlier help output)
run_scenario "blockchain" "blockchain_trust_v2x" 'echo "--nVehicles='"${NVEH}"' --simTime='"${SIMTIME}"' --cryptoDelayUsTx='"${CRYPTO_TX}"' --cryptoDelayUsRx='"${CRYPTO_RX}"'"'

# 4) Full integrated (bc_rsu_handover_trust_v2x): supports everything
run_scenario "full" "bc_rsu_handover_trust_v2x" 'echo "--nVehicles='"${NVEH}"' --simTime='"${SIMTIME}"' --cryptoDelayUsTx='"${CRYPTO_TX}"' --cryptoDelayUsRx='"${CRYPTO_RX}"' --maliciousRate='"${MAL}"' --enableReplayAttack='"${REPLAY}"' --replayEveryMs='"${REPLAY_EVERY}"' --blockIntervalMs='"${BLOCK}"' --mineDelayMs='"${MINE}"' --trustFastThresh='"${FAST}"' --trustMinThresh='"${MIN}"'"'

echo "DONE. Outputs in ${OUT_BASE}"
