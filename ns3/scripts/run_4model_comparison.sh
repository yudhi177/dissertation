#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"
PROGRAM="scratch/secure_trust_blockchain_v2x"

SIM_TIME="${SIM_TIME:-20}"
SUMO_STEP="${SUMO_STEP:-0.1}"

NET_XML="$REPO/sumo/maps/grid/grid.net.xml"

OUT="$REPO/ns3/results/model4_comparison"
RUNS="$OUT/runs"
SUM="$OUT/summary"
PLOTS="$OUT/plots"
mkdir -p "$RUNS" "$SUM" "$PLOTS"

VEH_LIST=(10 30 50 80)
SPD_LIST=(8.3 13.9 22.2)
SEED_LIST=(1 2 3 4 5)

RSU_RADIUS="${RSU_RADIUS:-300}"
TX_ALL="${TX_ALL:-0}"

ATTACK_MODE="${ATTACK_MODE:-2}"   # 2 = sig corrupt
MAL_RATE="${MAL_RATE:-0.2}"

echo "[OK] Building ns-3..." >&2
cd "$NS3DIR"
./ns3 build >/dev/null

make_trace () {
  local nveh="$1"
  local spd="$2"
  local seed="$3"

  local TAG="veh_${nveh}_spd_${spd}_seed_${seed}"
  local RUN_DIR="$REPO/sumo/output/model4/${TAG}"
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
  local out_csv="$3"
  local out_evt="$4"
  local extra="$5"

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
    --csvOut=$out_csv \
    --eventsOut=$out_evt \
    $extra" >/dev/null
}

# model configs
# baseline: all OFF
MODEL_baseline="--enableReplayCheck=0 --enableSigCheck=0 --enableReports=0 --enableBlockchain=0 --enableTrustGate=0 --enableReplayAttack=0"
# secure: replay+sig ON, others OFF
MODEL_secure="--enableReplayCheck=1 --enableSigCheck=1 --enableReports=0 --enableBlockchain=0 --enableTrustGate=0 --enableReplayAttack=1"
# trust_bc: trust pipeline ON, crypto checks OFF
MODEL_trustbc="--enableReplayCheck=0 --enableSigCheck=0 --enableReports=1 --enableBlockchain=1 --enableTrustGate=1 --enableReplayAttack=0"
# full: everything ON
MODEL_full="--enableReplayCheck=1 --enableSigCheck=1 --enableReports=1 --enableBlockchain=1 --enableTrustGate=1 --enableReplayAttack=1"

echo "[STEP] 4-model comparison runs..." >&2
for nveh in "${VEH_LIST[@]}"; do
  for spd in "${SPD_LIST[@]}"; do
    for seed in "${SEED_LIST[@]}"; do
      NS2="$(make_trace "$nveh" "$spd" "$seed")" || continue

      for model in baseline secure trustbc full; do
        TAG="model4_${model}_n${nveh}_s${spd}_seed${seed}"
        OUTCSV="$RUNS/${TAG}.csv"
        OUTEVT="$RUNS/${TAG}_events.csv"
        EXTRA_VAR="MODEL_${model}"
        EXTRA="${!EXTRA_VAR}"
        run_ns3 "$NS2" "$nveh" "$OUTCSV" "$OUTEVT" "$EXTRA"
        echo "[OK] $TAG" >&2
      done
    done
  done
done

echo "[DONE] CSVs in: $RUNS" >&2
