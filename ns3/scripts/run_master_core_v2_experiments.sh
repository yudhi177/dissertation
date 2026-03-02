#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"
PROGRAM="scratch/secure_trust_blockchain_v2x"

SIM_TIME="${SIM_TIME:-20}"
SUMO_STEP="${SUMO_STEP:-0.1}"

NET_XML="$REPO/sumo/maps/grid/grid.net.xml"

OUT="$REPO/ns3/results/core_v2_master"
RUNS="$OUT/runs"
mkdir -p "$RUNS"

# Defaults
VEH_LIST=(10 30 50 80)
SPD_LIST=(8.3 13.9 22.2)
SEED_LIST=(1 2 3 4 5)

# Sweeps
ATTACK_MODES=(0 1 2 3)
MAL_SWEEP=(0.0 0.1 0.2 0.4 0.6)
FAST_SWEEP=(0.6 0.7 0.8)
MIN_SWEEP=(0.2 0.3 0.4)

# Fixed params
RSU_RADIUS="${RSU_RADIUS:-300}"
TX_ALL="${TX_ALL:-0}"
ENABLE_REPORTS="${ENABLE_REPORTS:-1}"
ENABLE_BLOCKCHAIN="${ENABLE_BLOCKCHAIN:-1}"
ENABLE_TRUSTGATE="${ENABLE_TRUSTGATE:-1}"

# which sweeps to run
RUN_ATTACKMODE="${RUN_ATTACKMODE:-1}"
RUN_MALSWEEP="${RUN_MALSWEEP:-1}"
RUN_THRESH="${RUN_THRESH:-1}"

# ONLY_ONE mode
if [[ "${ONLY_ONE:-0}" == "1" ]]; then
  VEH_LIST=("${NVEH:-10}")
  SPD_LIST=("${SPD:-8.3}")
  SEED_LIST=("${SEED:-1}")

  # default only attackmode in ONLY_ONE
  RUN_ATTACKMODE="${RUN_ATTACKMODE:-1}"
  RUN_MALSWEEP="${RUN_MALSWEEP:-0}"
  RUN_THRESH="${RUN_THRESH:-0}"
fi

echo "[OK] Building ns-3..." >&2
cd "$NS3DIR"
./ns3 build >/dev/null

make_trace () {
  local nveh="$1"
  local spd="$2"
  local seed="$3"

  local TAG="veh_${nveh}_spd_${spd}_seed_${seed}"
  local RUN_DIR="$REPO/sumo/output/grid_master/${TAG}"
  local TRIPS="$RUN_DIR/trips.xml"
  local ROU="$RUN_DIR/routes.rou.xml"
  local FCD="$RUN_DIR/fcd.xml"
  local NS2="$RUN_DIR/ns2mobility.tcl"
  local LOCAL_CFG="$RUN_DIR/run.sumocfg"

  mkdir -p "$RUN_DIR"

  # routes
  python3 /usr/share/sumo/tools/randomTrips.py \
    -n "$NET_XML" \
    -o "$TRIPS" \
    -r "$ROU" \
    --seed "$seed" \
    --prefix veh \
    --min-distance 50 \
    --random >/dev/null

  # Clean XML (NO stdout from python!)
  python3 - <<PY >/dev/null
import xml.etree.ElementTree as ET
p="${ROU}"
tree=ET.parse(p)
root=tree.getroot()

# remove duplicate vTypes
for vt in list(root.findall("vType")):
    if vt.get("id","") in ("veh_passenger","car"):
        root.remove(vt)

# insert single vType with speed
vtype = ET.Element("vType", {
    "id":"veh_passenger",
    "accel":"2.6","decel":"4.5","sigma":"0.5","length":"5",
    "maxSpeed":"${spd}"
})
root.insert(0, vtype)

# force type on all vehicles
for v in root.findall("vehicle"):
    v.set("type","veh_passenger")

# trim to nveh
vehicles = root.findall("vehicle")
for v in vehicles[int(${nveh}):]:
    root.remove(v)

tree.write(p)
PY
  echo "[OK] routes cleaned: $TAG (kept $nveh, maxSpeed=$spd)" >&2

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

  # IMPORTANT: limit exactly nveh (so nVehicles matches mobility)
  python3 "$REPO/sumo/traci_controller.py" --fcd "$FCD" --out "$NS2" --limit "$nveh" >/dev/null
  test -s "$NS2" || { echo "[WARN] empty ns2 for $TAG" >&2; return 1; }

  # stdout ONLY the ns2 path
  echo "$NS2"
}

run_ns3 () {
  local ns2="$1"
  local nveh="$2"
  local out_csv="$3"
  local out_evt="$4"
  local extra_args="$5"

  cd "$NS3DIR"
  ./ns3 run "$PROGRAM \
    --useNs2Mobility=1 \
    --ns2Mobility=$ns2 \
    --simTime=$SIM_TIME \
    --nVehicles=$nveh \
    --rsuCoverageRadius=$RSU_RADIUS \
    --txAllVehicles=$TX_ALL \
    --enableReports=$ENABLE_REPORTS \
    --enableBlockchain=$ENABLE_BLOCKCHAIN \
    --enableTrustGate=$ENABLE_TRUSTGATE \
    --csvOut=$out_csv \
    --eventsOut=$out_evt \
    $extra_args" >/dev/null
}

# 1) Attack-mode comparison
if [[ "$RUN_ATTACKMODE" == "1" ]]; then
  echo "[STEP] Attack-mode comparison..." >&2
  for nveh in "${VEH_LIST[@]}"; do
    for spd in "${SPD_LIST[@]}"; do
      for seed in "${SEED_LIST[@]}"; do
        NS2="$(make_trace "$nveh" "$spd" "$seed")" || continue
        for mode in "${ATTACK_MODES[@]}"; do
          TAG="attackmode_n${nveh}_s${spd}_seed${seed}_m${mode}"
          OUTCSV="$RUNS/${TAG}.csv"
          OUTEVT="$RUNS/${TAG}_events.csv"
          run_ns3 "$NS2" "$nveh" "$OUTCSV" "$OUTEVT" "--attackMode=$mode --maliciousRate=0.2"
          echo "[OK] $TAG" >&2
        done
      done
    done
  done
fi

# 2) Malicious rate sweep
if [[ "$RUN_MALSWEEP" == "1" ]]; then
  echo "[STEP] MaliciousRate sweep..." >&2
  for nveh in "${VEH_LIST[@]}"; do
    for spd in "${SPD_LIST[@]}"; do
      for seed in "${SEED_LIST[@]}"; do
        NS2="$(make_trace "$nveh" "$spd" "$seed")" || continue
        for mal in "${MAL_SWEEP[@]}"; do
          TAG="malsweep_n${nveh}_s${spd}_seed${seed}_mal${mal}"
          OUTCSV="$RUNS/${TAG}.csv"
          OUTEVT="$RUNS/${TAG}_events.csv"
          run_ns3 "$NS2" "$nveh" "$OUTCSV" "$OUTEVT" "--attackMode=2 --maliciousRate=$mal"
          echo "[OK] $TAG" >&2
        done
      done
    done
  done
fi

# 3) Threshold heatmap
if [[ "$RUN_THRESH" == "1" ]]; then
  echo "[STEP] Threshold heatmap..." >&2
  for nveh in "${VEH_LIST[@]}"; do
    for spd in "${SPD_LIST[@]}"; do
      for seed in "${SEED_LIST[@]}"; do
        NS2="$(make_trace "$nveh" "$spd" "$seed")" || continue
        for tf in "${FAST_SWEEP[@]}"; do
          for tm in "${MIN_SWEEP[@]}"; do
            TAG="thresh_n${nveh}_s${spd}_seed${seed}_tf${tf}_tm${tm}"
            OUTCSV="$RUNS/${TAG}.csv"
            OUTEVT="$RUNS/${TAG}_events.csv"
            run_ns3 "$NS2" "$nveh" "$OUTCSV" "$OUTEVT" "--attackMode=2 --maliciousRate=0.2 --trustFastThresh=$tf --trustMinThresh=$tm"
            echo "[OK] $TAG" >&2
          done
        done
      done
    done
  done
fi

echo "[DONE] CSVs in: $RUNS" >&2
