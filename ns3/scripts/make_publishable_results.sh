#!/usr/bin/env bash
set -euo pipefail

cd "$HOME/ns-3"

MODE="${1:-quick}"   # quick | full

OUTROOT="$HOME/dissertation/ns3/results/publish_pack_baselines"
RUNSD="$OUTROOT/runs"
PLOTSD="$OUTROOT/plots"
mkdir -p "$RUNSD" "$PLOTSD"

HELP=$(/home/$USER/ns-3/./ns3 run "scratch/secure_trust_blockchain_v2x --PrintHelp" 2>/dev/null || true)

has_flag() { echo "$HELP" | grep -qE -- "$1"; }

pick_flag() {
  # prints first matching flag (without leading --), or empty
  for f in "$@"; do
    if echo "$HELP" | grep -qE -- "--${f}:"; then
      echo "$f"
      return 0
    fi
  done
  echo ""
}

# Detect common flags
F_SIMTIME=$(pick_flag simTime)
F_CSV=$(pick_flag csvOut)
F_EVT=$(pick_flag eventsOut)
F_TRUST=$(pick_flag enableTrustEngineFinal enableTrust)
F_REV=$(pick_flag enableRevocation)
F_PRIV=$(pick_flag enablePrivacy)
F_ROT_HO=$(pick_flag rotateOnHandover)
F_PSEUDO_INT=$(pick_flag pseudoRotateIntervalS pseudoRotateSec)
F_LINKWIN=$(pick_flag linkWindowS linkTimeWindowSec)
F_MIXR=$(pick_flag mixRadiusM)
F_BC_CACHE=$(pick_flag enableBCLocalCache)
F_BC_SYNC=$(pick_flag bcSyncIntervalMs)
F_BC_QD=$(pick_flag bcQueryDelayMs)
F_BC_UD=$(pick_flag bcUpdateDelayMs)
F_ENABLE_BC=$(pick_flag enableBlockchain)
F_BC_PROBE=$(pick_flag enableBcProbe)
F_BC_PROBE_INT=$(pick_flag bcProbeIntervalMs)
F_BC_PROBE_PSEU=$(pick_flag bcProbeUsePseudonym)

F_NVEH=$(pick_flag nVehicles nVeh numVehicles vehicles)
F_SPEED=$(pick_flag vehSpeed speed speedMs meanSpeed)

echo "[INFO] Detected flags:"
echo " simTime=$F_SIMTIME csvOut=$F_CSV eventsOut=$F_EVT nVeh=$F_NVEH speed=$F_SPEED"
echo " trust=$F_TRUST revocation=$F_REV privacy=$F_PRIV rotateHO=$F_ROT_HO pseudoInt=$F_PSEUDO_INT linkWin=$F_LINKWIN mixR=$F_MIXR"
echo " bcCache=$F_BC_CACHE bcSync=$F_BC_SYNC bcQDelay=$F_BC_QD bcUDelay=$F_BC_UD"
echo

if [[ -z "$F_SIMTIME" || -z "$F_CSV" || -z "$F_EVT" ]]; then
  echo "[ERR] Missing required flags (simTime/csvOut/eventsOut). Check your program supports these."
  exit 1
fi

# Experiment grid
if [[ "$MODE" == "quick" ]]; then
  NVEHS=(30 60)
  SPEEDS=(10 20)       # only used if your code exposes a speed flag
  SEEDS=(1 2 3)
  SIM=40
else
  NVEHS=(30 60 90)
  SPEEDS=(5 10 15 20 25)

# If program has no speed flag, collapse speed dimension
if [[ -z "$F_SPEED" ]]; then SPEEDS=(0); fi
  SEEDS=(1 2 3 4 5)
  SIM=60
fi

INDEX="$OUTROOT/runs_index.csv"
echo "baseline,nveh,speed,seed,csv,events,bc_line,priv_line" > "$INDEX"

run_one () {
  local baseline="$1"
  local nveh="$2"
  local spd="$3"
  local seed="$4"

  local tag="${baseline}_veh${nveh}_spd${spd}_seed${seed}"
  local csv="$RUNSD/${tag}.csv"
  local evt="$RUNSD/${tag}_events.csv"
  local log="$RUNSD/${tag}.log"
  local manifest="$RUNSD/${tag}_manifest.json"

  # base args
  local args="--${F_SIMTIME}=${SIM} --${F_CSV}=${csv} --${F_EVT}=${evt}"

  # optional: nVehicles + speed + seed
  if [[ -n "$F_NVEH" ]]; then args="$args --${F_NVEH}=${nveh}"; fi
  if [[ -n "$F_SPEED" ]]; then args="$args --${F_SPEED}=${spd}"; fi
  if echo "$HELP" | grep -qE -- "--seed:"; then args="$args --seed=${seed}"; fi

  # baseline configs
  case "$baseline" in
    PKI_ONLY)
      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=0"; fi
      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi
      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi
      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=0"; fi
      if [[ -n "$F_BC_QD" ]]; then args="$args --${F_BC_QD}=0"; fi
      if [[ -n "$F_BC_UD" ]]; then args="$args --${F_BC_UD}=0"; fi
            if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=0"; fi
;;
    TRUST_ONLY)
      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi
      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi
      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi
      # blockchain OFF
      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=0"; fi
      if [[ -n "$F_BC_QD" ]]; then args="$args --${F_BC_QD}=0"; fi
      if [[ -n "$F_BC_UD" ]]; then args="$args --${F_BC_UD}=0"; fi
      # probes OFF
      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=0"; fi
      if [[ -n "$F_BC_PROBE_INT" ]]; then args="$args --${F_BC_PROBE_INT}=200"; fi
      if [[ -n "$F_BC_PROBE_PSEU" ]]; then args="$args --${F_BC_PROBE_PSEU}=0"; fi
            if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=0"; fi
;;

    BC_TRUST)
      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi
      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi
      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi
      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=1"; fi
      if [[ -n "$F_BC_SYNC" ]]; then args="$args --${F_BC_SYNC}=500"; fi
      if [[ -n "$F_BC_QD" ]]; then args="$args --${F_BC_QD}=12"; fi
      if [[ -n "$F_BC_UD" ]]; then args="$args --${F_BC_UD}=18"; fi
      
      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=1"; fi
      if [[ -n "$F_BC_PROBE_INT" ]]; then args="$args --${F_BC_PROBE_INT}=200"; fi
      if [[ -n "$F_BC_PROBE_PSEU" ]]; then args="$args --${F_BC_PROBE_PSEU}=1"; fi
      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi
;;
    FULL)
      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi
      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=1"; fi
      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=1"; fi
      if [[ -n "$F_ROT_HO" ]]; then args="$args --${F_ROT_HO}=1"; fi
      if [[ -n "$F_PSEUDO_INT" ]]; then args="$args --${F_PSEUDO_INT}=5"; fi
      if [[ -n "$F_LINKWIN" ]]; then args="$args --${F_LINKWIN}=2"; fi
      if [[ -n "$F_MIXR" ]]; then args="$args --${F_MIXR}=50"; fi
      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=1"; fi
      if [[ -n "$F_BC_SYNC" ]]; then args="$args --${F_BC_SYNC}=500"; fi
      if [[ -n "$F_BC_QD" ]]; then args="$args --${F_BC_QD}=12"; fi
      if [[ -n "$F_BC_UD" ]]; then args="$args --${F_BC_UD}=18"; fi
      
      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=1"; fi
      if [[ -n "$F_BC_PROBE_INT" ]]; then args="$args --${F_BC_PROBE_INT}=200"; fi
      if [[ -n "$F_BC_PROBE_PSEU" ]]; then args="$args --${F_BC_PROBE_PSEU}=1"; fi
      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi
;;
    *)
      echo "[ERR] Unknown baseline $baseline"; exit 1;;
  esac

  echo "[RUN] $tag"
  # write per-run manifest (reproducibility)
  python3 - "$tag" "$baseline" "$nveh" "$spd" "$seed" "$SIM" "$args" "$manifest" <<'PYEOF'
import json, sys, os, subprocess
tag, baseline, nveh, spd, seed, sim, args, manifest = sys.argv[1:]

def to_int(x):
    try: return int(float(x))
    except: return 0

data = {
  "tag": tag,
  "baseline": baseline,
  "nveh": to_int(nveh),
  "speed": to_int(spd),
  "seed": to_int(seed),
  "sim": to_int(sim),
  "args": args,
  "git_commit": subprocess.getoutput(f"git -C {os.path.expanduser('~')}/dissertation rev-parse --short HEAD 2>/dev/null").strip()
}
with open(manifest, "w") as f:
    f.write(json.dumps(data, indent=2))
PYEOF

  ./ns3 run "scratch/secure_trust_blockchain_v2x ${args}" 2>&1 | tee "$log" >/dev/null

  local bc_line priv_line
  bc_line=$(grep -m1 '^\[BC\]' "$log" || true)
  priv_line=$(grep -m1 '^\[PRIV\]' "$log" || true)

  # escape commas for CSV
  bc_line=${bc_line//,/;}
  priv_line=${priv_line//,/;}

  echo "${baseline},${nveh},${spd},${seed},${csv},${evt},\"${bc_line}\",\"${priv_line}\"" >> "$INDEX"
}

BASELINES=(PKI_ONLY TRUST_ONLY BC_TRUST FULL)

for b in "${BASELINES[@]}"; do
  for n in "${NVEHS[@]}"; do
    for s in "${SPEEDS[@]}"; do
      for k in "${SEEDS[@]}"; do
        run_one "$b" "$n" "$s" "$k"
      done
    done
  done
done

echo
echo "[DONE] Runs complete. Index: $INDEX"

python3 "$HOME/dissertation/ns3/scripts/aggregate_publish_pack.py" "$INDEX" "$OUTROOT/summary.csv"
python3 "$HOME/dissertation/ns3/scripts/plot_publish_pack.py" "$OUTROOT/summary.csv" "$PLOTSD"

# Copy final pack
PUB="$HOME/dissertation/results_publishable/baselines_pack"
mkdir -p "$PUB"
cp -f "$OUTROOT/summary.csv" "$PUB/"
cp -f "$PLOTSD"/*.png "$PUB/" 2>/dev/null || true
cp -f "$INDEX" "$PUB/"


# --- Security postprocess (revocation CDF + detection/FP) ---
"$HOME/dissertation/ns3/scripts/postprocess_security_pack.sh" "$OUTROOT/runs" "$PUB"

echo "[PUBLISH] $PUB"
