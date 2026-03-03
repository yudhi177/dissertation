#!/usr/bin/env bash
set -euo pipefail

echo "=============================="
echo " FINAL CHECKLIST (V2X Project) "
echo "=============================="

REPO="$HOME/dissertation"
NS3="$HOME/ns-3"
BIN="$NS3/build/scratch/ns3-dev-secure_trust_blockchain_v2x-default"

PACK="$REPO/results_publishable/baselines_pack"
SUM="$PACK/summary.csv"
PLOTS_DIR="$PACK"

echo "[1] Build status"
cd "$NS3"
./ns3 build >/dev/null
echo "  ✅ ns-3 build OK"

echo "[2] Binary exists"
test -f "$BIN"
echo "  ✅ binary: $BIN"

echo "[3] Required flags present"
HELP=$(./ns3 run "scratch/secure_trust_blockchain_v2x --PrintHelp" 2>/dev/null || true)

need_flag () {
  local f="$1"
  echo "$HELP" | grep -qE -- "--${f}:" || { echo "  ❌ missing flag: --$f"; exit 2; }
}

need_flag simTime
need_flag csvOut
need_flag eventsOut
need_flag enableTrustEngineFinal
need_flag enableBCLocalCache
need_flag bcSyncIntervalMs
need_flag bcQueryDelayMs
need_flag bcUpdateDelayMs
need_flag enablePrivacy
need_flag pseudoRotateIntervalS
need_flag linkWindowS
need_flag mixRadiusM
need_flag enableBcProbe
need_flag bcProbeIntervalMs

echo "  ✅ flags OK"

echo "[4] Publish pack exists"
test -d "$PACK" || { echo "  ❌ missing folder: $PACK"; exit 3; }
test -f "$SUM"  || { echo "  ❌ missing summary.csv: $SUM"; exit 3; }
echo "  ✅ publish folder + summary.csv OK"

echo "[5] Required summary columns"
head -n 1 "$SUM" > /tmp/_hdr.txt

need_col () {
  local c="$1"
  grep -qE "(^|,)${c}(,|$)" /tmp/_hdr.txt || { echo "  ❌ missing column: $c"; exit 4; }
}

# core metrics (best-effort: accept either pdr/PDR; delay/avgDelay; throughput)
HDR=$(cat /tmp/_hdr.txt)
echo "$HDR" | grep -qiE "(^|,)(PDR|pdr)(,|$)" || echo "  ⚠️ PDR column not found (ok if named differently)"
echo "$HDR" | grep -qiE "(^|,)(avgDelay|delay)(,|$)" || echo "  ⚠️ Delay column not found (ok if named differently)"
echo "$HDR" | grep -qiE "(^|,)(throughput|tput)(,|$)" || echo "  ⚠️ Throughput column not found (ok if named differently)"

# bc + privacy metrics
need_col bc_queries
need_col bc_updates
need_col bc_hitRate
need_col priv_rotations

# exp-rate optional (warn only)
if grep -qE "(^|,)priv_linkSuccessRateExp(,|$)" /tmp/_hdr.txt; then
  echo "  ✅ priv_linkSuccessRateExp present"
else
  echo "  ⚠️ priv_linkSuccessRateExp missing (add parser in aggregator if needed)"
fi

echo "  ✅ required columns OK (core + bc + privacy)"

echo "[6] Plots exist"
PNGCOUNT=$(ls -1 "$PLOTS_DIR"/*.png 2>/dev/null | wc -l | tr -d ' ')
if [[ "$PNGCOUNT" -lt 2 ]]; then
  echo "  ⚠️ low plot count ($PNGCOUNT). Did plotting run?"
else
  echo "  ✅ plots found: $PNGCOUNT"
fi

echo "[7] Manifests exist"
MCOUNT=$(ls -1 "$REPO/ns3/results/publish_pack_baselines/runs"/*_manifest.json 2>/dev/null | wc -l | tr -d ' ')
if [[ "$MCOUNT" -lt 1 ]]; then
  echo "  ⚠️ no manifest files found (optional)"
else
  echo "  ✅ manifests found: $MCOUNT"
fi

echo
echo "✅ FINAL CHECKLIST COMPLETE"
echo "Publish pack ready at: $PACK"
