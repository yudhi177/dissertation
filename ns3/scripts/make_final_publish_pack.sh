#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dissertation"
NS3="$HOME/ns-3"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/results_publishable/final_pack_$STAMP"

mkdir -p "$OUT"/{baselines,dmax,privacy,auth,revocation,plots,summary,logs}
echo "[INFO] OUT=$OUT"

need () { command -v "$1" >/dev/null 2>&1 || { echo "[ERR] missing command: $1"; exit 1; }; }
need python3

echo "[1/7] Build ns-3"
cd "$NS3"
./ns3 build | tee "$OUT/logs/build.log"

echo "[2/7] Baselines pack (quick)"
if [[ -x "$ROOT/ns3/scripts/make_publishable_results.sh" ]]; then
  "$ROOT/ns3/scripts/make_publishable_results.sh" quick | tee "$OUT/logs/baselines_pack.log" || true
fi

# Copy latest baselines_pack if exists
if [[ -d "$ROOT/results_publishable/baselines_pack" ]]; then
  cp -a "$ROOT/results_publishable/baselines_pack/." "$OUT/baselines/" || true
fi
if [[ -d "$ROOT/ns3/results/publish_pack_baselines" ]]; then
  cp -a "$ROOT/ns3/results/publish_pack_baselines/." "$OUT/baselines/" || true
fi

echo "[3/7] Δmax tradeoff pack"
if [[ -x "$ROOT/ns3/scripts/run_dmax_tradeoff_sweep.sh" ]]; then
  "$ROOT/ns3/scripts/run_dmax_tradeoff_sweep.sh" | tee "$OUT/logs/dmax_sweep.log"
fi
if [[ -f "$ROOT/ns3/scripts/aggregate_dmax_tradeoff_v2.py" ]]; then
  python3 "$ROOT/ns3/scripts/aggregate_dmax_tradeoff_v2.py" | tee "$OUT/logs/dmax_agg.log" || true
fi
if [[ -f "$ROOT/ns3/scripts/plot_dmax_tradeoff.py" ]]; then
  python3 "$ROOT/ns3/scripts/plot_dmax_tradeoff.py" | tee "$OUT/logs/dmax_plot.log" || true
fi
if [[ -d "$ROOT/ns3/results/dmax_tradeoff" ]]; then
  cp -a "$ROOT/ns3/results/dmax_tradeoff/." "$OUT/dmax/" || true
fi

echo "[4/7] Privacy pack"
if [[ -x "$ROOT/ns3/scripts/run_privacy_linkability_sweep.sh" ]]; then
  "$ROOT/ns3/scripts/run_privacy_linkability_sweep.sh" | tee "$OUT/logs/privacy_sweep.log"
fi
if [[ -x "$ROOT/ns3/scripts/sweep_privacy_mixzone_quick.sh" ]]; then
  "$ROOT/ns3/scripts/sweep_privacy_mixzone_quick.sh" | tee "$OUT/logs/privacy_mixzone.log" || true
fi
if [[ -f "$ROOT/ns3/scripts/aggregate_privacy_linkability.py" ]]; then
  python3 "$ROOT/ns3/scripts/aggregate_privacy_linkability.py" | tee "$OUT/logs/privacy_agg.log" || true
fi
if [[ -f "$ROOT/ns3/scripts/plot_privacy_linkability.py" ]]; then
  python3 "$ROOT/ns3/scripts/plot_privacy_linkability.py" | tee "$OUT/logs/privacy_plot.log" || true
fi
if [[ -d "$ROOT/ns3/results/privacy_linkability_sweep" ]]; then
  cp -a "$ROOT/ns3/results/privacy_linkability_sweep/." "$OUT/privacy/" || true
fi
if [[ -f "$ROOT/ns3/results/privacy_mixzone_sweep.csv" ]]; then
  cp -f "$ROOT/ns3/results/privacy_mixzone_sweep.csv" "$OUT/privacy/" || true
fi

echo "[5/7] Auth security pack"
if [[ -x "$ROOT/ns3/scripts/run_auth_security_pack.sh" ]]; then
  "$ROOT/ns3/scripts/run_auth_security_pack.sh" | tee "$OUT/logs/auth_pack.log"
fi
if [[ -f "$ROOT/ns3/scripts/aggregate_auth_security_pack_v3.py" ]]; then
  python3 "$ROOT/ns3/scripts/aggregate_auth_security_pack_v3.py" | tee "$OUT/logs/auth_agg.log" || true
fi
if [[ -f "$ROOT/ns3/scripts/plot_auth_security_pack_v2.py" ]]; then
  python3 "$ROOT/ns3/scripts/plot_auth_security_pack_v2.py" | tee "$OUT/logs/auth_plot.log" || true
fi
if [[ -d "$ROOT/ns3/results/auth_security_pack" ]]; then
  cp -a "$ROOT/ns3/results/auth_security_pack/." "$OUT/auth/" || true
fi

echo "[6/7] Revocation final pack (if exists)"
if [[ -d "$ROOT/ns3/results/revocation_final_pack" ]]; then
  cp -a "$ROOT/ns3/results/revocation_final_pack/." "$OUT/revocation/" || true
fi

echo "[7/7] Collect key plots + summaries"
# grab plots from known places
find "$ROOT" -type f \( -name "*.png" -o -name "*.csv" \) 2>/dev/null | \
  grep -E "results_publishable|ns3/results/(dmax_tradeoff|privacy_linkability_sweep|auth_security_pack|publish_pack_baselines|revocation_final_pack)" \
  | head -n 2000 > "$OUT/summary/files_index.txt" || true

# copy only png plots into OUT/plots
while IFS= read -r f; do
  [[ -f "$f" ]] || continue
  if [[ "$f" == *.png ]]; then
    base="$(basename "$f")"
    cp -f "$f" "$OUT/plots/$base" 2>/dev/null || true
  fi
done < "$OUT/summary/files_index.txt"

echo "[OK] Final publish pack ready:"
echo "  $OUT"
ls -lah "$OUT" | head
