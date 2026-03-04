#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"
PROGRAM="scratch/secure_trust_blockchain_v2x"

SIM_TIME="${SIM_TIME:-20}"
SUMO_STEP="${SUMO_STEP:-0.1}"

NET_XML="$REPO/sumo/maps/grid/grid.net.xml"

OUT="$REPO/ns3/results/bc_params_heatmap"
RUNS="$OUT/runs"
mkdir -p "$RUNS"

# Defaults
VEH_LIST=(10 30 50 80)
SPD_LIST=(8.3 13.9 22.2)
SEED_LIST=(1 2 3 4 5)

# Heatmap grid (edit freely)
BLOCK_INTERVALS_MS=(500 1000 2000)
MINE_DELAYS_MS=(10 50 100)

# Fixed scenario knobs
RSU_RADIUS="${RSU_RADIUS:-300}"
TX_ALL="${TX_ALL:-0}"
ATTACK_MODE="${ATTACK_MODE:-2}"
MAL_RATE="${MAL_RATE:-0.2}"

# We want FULL model with blockchain enabled (ablation already done earlier)
ENABLE_REPLAY_CHECK=1
ENABLE_SIG_CHECK=1
ENABLE_REPORTS=1
ENABLE_BLOCKCHAIN=1
ENABLE_TRUSTGATE=1
ENABLE_REPLAY_ATTACK=1

# ONLY_ONE quick mode
if [[ "${ONLY_ONE:-0}" == "1" ]]; then
  VEH_LIST=("${NVEH:-10}")
  SPD_LIST=("${SPD:-8.3}")
  SEED_LIST=("${SEED:-1}")
fi

echo "[OK] Building ns-3..." >&2
cd "$NS3DIR"
./ns3 build >/dev/null

make_trace () {
  local nveh="$1"
  local spd="$2"
  local seed="$3"

  local TAG="veh_${nveh}_spd_${spd}_seed_${seed}"
  local RUN_DIR="$REPO/sumo/output/bc_params/${TAG}"
  local TRIPS="$RUN_DIR/trips.xml"
  local ROU="$RUN_DIR/routes.rou.xml"
  local FCD="$RUN_DIR/fcd.xml"
  local NS2="$RUN_DIR/ns2mobility.tcl"
  local LOCAL_CFG="$RUN_DIR/run.sumocfg"
  mkdir -p "$RUN_DIR"

  python3 /usr/share/sumo/tools/randomTrips.py \
    -n "$NET_XML" -o "$TRIPS" -r "$ROU" \
    --seed "$seed" --prefix veh --min-distance 50 --random >/dev/null

  python3 - <<PY >/dev/null
import xml.etree.ElementTree as ET
p="${ROU}"
tree=ET.parse(p); root=tree.getroot()
for vt in list(root.findall("vType")):
    if vt.get("id","") in ("veh_passenger","car"):
        root.remove(vt)
root.insert(0, ET.Element("vType", {
    "id":"veh_passenger","accel":"2.6","decel":"4.5","sigma":"0.5","length":"5","maxSpeed":"${spd}"
}))
for v in root.findall("vehicle"):
    v.set("type","veh_passenger")
vehicles = root.findall("vehicle")
for v in vehicles[int(${nveh}):]:
    root.remove(v)
tree.write(p)
PY

  cat > "$LOCAL_CFG" <<CFG
<configuration>
  <input>
    <net-file value="$NET_XML"/>
    <route-files value="$ROU"/>
  </input>
  <time>
    <step-length value="$SUMO_STEP"/>
  </time>
  <output>
    <fcd-output value="$FCD"/>
  </output>
</configuration>
CFG

  sumo -c "$LOCAL_CFG" --seed "$seed" >/dev/null
  grep -q "<vehicle" "$FCD" || { echo "[WARN] no vehicles in FCD for $TAG" >&2; return 1; }

  python3 "$REPO/sumo/traci_controller.py" --fcd "$FCD" --out "$NS2" --limit "$nveh" >/dev/null
  test -s "$NS2" || { echo "[WARN] empty ns2 for $TAG" >&2; return 1; }

  echo "$NS2"
}

run_ns3 () {
  local ns2="$1"
  local nveh="$2"
  local bi="$3"
  local md="$4"
  local out_csv="$5"
  local out_evt="$6"

  cd "$NS3DIR"
  ./ns3 run "$PROGRAM \
    --useNs2Mobility=1 \
    --ns2Mobility=$ns2 \
    --simTime=$SIM_TIME \
    --nVehicles=$nveh \
    --rsuCoverageRadius=$RSU_RADIUS \
    --txAllVehicles=$TX_ALL \
    --attackMode=$ATTACK_MODE \
    --maliciousRate=$MAL_RATE \
    --enableReplayCheck=$ENABLE_REPLAY_CHECK \
    --enableSigCheck=$ENABLE_SIG_CHECK \
    --enableReports=$ENABLE_REPORTS \
    --enableBlockchain=$ENABLE_BLOCKCHAIN \
    --enableTrustGate=$ENABLE_TRUSTGATE \
    --enableReplayAttack=$ENABLE_REPLAY_ATTACK \
    --blockIntervalMs=$bi \
    --mineDelayMs=$md \
    --csvOut=$out_csv \
    --eventsOut=$out_evt" >/dev/null
}

echo "[STEP] Blockchain params heatmap runs..." >&2
for nveh in "${VEH_LIST[@]}"; do
  for spd in "${SPD_LIST[@]}"; do
    for seed in "${SEED_LIST[@]}"; do
      NS2="$(make_trace "$nveh" "$spd" "$seed")" || continue
      for bi in "${BLOCK_INTERVALS_MS[@]}"; do
        for md in "${MINE_DELAYS_MS[@]}"; do
          TAG="bcparam_n${nveh}_s${spd}_seed${seed}_bi${bi}_md${md}"
          OUTCSV="$RUNS/${TAG}.csv"
          OUTEVT="$RUNS/${TAG}_events.csv"
          run_ns3 "$NS2" "$nveh" "$bi" "$md" "$OUTCSV" "$OUTEVT"
          echo "[OK] $TAG" >&2
        done
      done
    done
  done
done

echo "[DONE] CSVs in: $RUNS" >&2
