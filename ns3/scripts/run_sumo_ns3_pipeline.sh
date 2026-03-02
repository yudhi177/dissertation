#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"

VEH_LIST=(10 30 50 80)
SPEED_LIST=(8.3 13.9 22.2)
SEED_LIST=(1 2 3 4 5)

SIM_TIME=20
SUMO_STEP=0.1

NET_XML="$REPO/sumo/maps/grid/grid.net.xml"
OUT_BASE="$REPO/ns3/results/sumo_pipeline"
RUNS_DIR="$OUT_BASE/runs"
mkdir -p "$RUNS_DIR"

PROGRAM="scratch/secure_trust_blockchain_v2x"

echo "Building ns-3..."
cd "$NS3DIR"
./ns3 build

run_one () {
  local nveh="$1"
  local spd="$2"
  local seed="$3"

  local TAG="veh_${nveh}_spd_${spd}_seed_${seed}"
  local RUN_DIR="$REPO/sumo/output/grid/${TAG}"
  local TRIPS="$RUN_DIR/trips.xml"
  local ROU="$RUN_DIR/routes.rou.xml"
  local FCD="$RUN_DIR/fcd.xml"
  local NS2="$RUN_DIR/ns2mobility.tcl"
  local LOCAL_CFG="$RUN_DIR/run.sumocfg"
  local VTYPE_ADD="$RUN_DIR/vtypes.add.xml"

  local OUT_RUN_CSV="$RUNS_DIR/${TAG}.csv"
  local OUT_RUN_EVT="$RUNS_DIR/${TAG}_events.csv"

  mkdir -p "$RUN_DIR"
  echo "=== RUN: $TAG ==="

  # period so we generate about nveh vehicles within SIM_TIME
  local PERIOD
  PERIOD="$(python3 - <<PY
sim=${SIM_TIME}
n=${nveh}
print(max(0.1, sim/float(n)))
PY
)"

  # vType definition (fixes: "vehicle type 'car' not known")
  cat > "$VTYPE_ADD" <<EOF
<additional>
  <vType id="car" accel="2.6" decel="4.5" sigma="0.5" length="5" maxSpeed="${spd}"/>
</additional>
EOF

  # Generate trips+routes WITHOUT trimming
  python3 /usr/share/sumo/tools/randomTrips.py \
    -n "$NET_XML" \
    -b 0 -e "$SIM_TIME" -p "$PERIOD" \
    --seed "$seed" \
    --prefix veh \
    --min-distance 50 \
    --random \
    --vehicle-class passenger \
    --vtype car \
    -o "$TRIPS" \
    -r "$ROU" >/dev/null

  # Local sumocfg (route + additional vtypes)
  cat > "$LOCAL_CFG" <<EOF
<configuration>
  <input>
    <net-file value="$NET_XML"/>
    <route-files value="$ROU"/>
    <additional-files value="$VTYPE_ADD"/>
  </input>
  <time>
    <begin value="0"/>
    <end value="$SIM_TIME"/>
    <step-length value="$SUMO_STEP"/>
  </time>
  <output>
    <fcd-output value="$FCD"/>
  </output>
</configuration>
EOF

  # Run SUMO
  sumo -c "$LOCAL_CFG" --seed "$seed" --quit-on-end --no-step-log true >/dev/null

  grep -q "<vehicle" "$FCD" || { echo "[WARN] No vehicles in FCD, skip"; return 0; }

  # Convert to ns2 mobility (limit MUST match nveh)
  python3 "$REPO/sumo/traci_controller.py" \
    --fcd "$FCD" \
    --out "$NS2" \
    --limit "$nveh"

  test -s "$NS2" || { echo "[WARN] Empty NS2 trace, skip"; return 0; }

  # Run ns-3 (nVehicles MUST match nveh)
  cd "$NS3DIR"
  ./ns3 run "$PROGRAM -- \
    --useNs2Mobility=1 \
    --ns2Mobility=$NS2 \
    --simTime=$SIM_TIME \
    --nVehicles=$nveh \
    --csvOut=$OUT_RUN_CSV \
    --eventsOut=$OUT_RUN_EVT" >/dev/null

  if [ -s "$OUT_RUN_CSV" ]; then
    echo "[OK] CSV: $OUT_RUN_CSV"
  else
    echo "[WARN] No CSV produced: $OUT_RUN_CSV"
  fi
}

for nveh in "${VEH_LIST[@]}"; do
  for spd in "${SPEED_LIST[@]}"; do
    for seed in "${SEED_LIST[@]}"; do
      run_one "$nveh" "$spd" "$seed"
    done
  done
done

echo "DONE. CSVs in: $RUNS_DIR"
