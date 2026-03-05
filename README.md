# Secure Trust-Based V2X Communication with Blockchain Support (ns-3)

4th Year Dissertation Project (V2X / VANET simulation in ns-3)

**Core idea:** Trust-based RSU handover + security attacks + blockchain-backed trust + privacy controls.

---

## Project Highlights
- **Trust-based RSU handover** (FAST vs FULL authentication behavior)
- **Security evaluation**: simulated crypto delay + replay / sybil / signature-corruption style attacks
- **Blockchain-backed trust (simulated)**: trust commits + optional trust cache
- **Privacy controls**: pseudonym rotation + linkability / mix-zone style evaluation
- **Automation**: experiment scripts + CSV aggregation + plots for results

---

## Repository Structure
- `ns3/`
  - `scenarios/` → ns-3 C++ scenario(s), especially `secure_trust_blockchain_v2x.cc`
  - `scripts/` → run/aggregate/plot scripts
  - `results/` → experiment outputs (CSV summaries + plots)
- `docs/` → reproducibility notes + explanation of results
- `submission_bundle/` → final “submission-ready” copy (scenario + scripts + selected outputs)
- `blockchain/` → optional prototype utilities (only if used)
- `sumo/` → optional SUMO artifacts (only if used)

---

## Prerequisites
- ns-3 (CMake/Ninja based)
- C++ compiler (g++)
- Python 3 (for scripts + plotting)

---

## Build ns-3 (recommended workflow)
Run these inside your **ns-3 workspace** (not inside this repo):
```bash
cd ~/ns-3
./ns3 clean
./ns3 configure
./ns3 build
