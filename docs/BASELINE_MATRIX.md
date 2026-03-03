# Baseline Matrix (Ablation ON/OFF)

| Baseline | TrustEngine | enableBlockchain | BC Cache | BC Probe | Privacy | Revocation | Δmax Gate |
|---|---:|---:|---:|---:|---:|---:|---:|
| PKI_ONLY | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| TRUST_ONLY | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| BC_TRUST | 1 | 1 | 1 | 1 | 0 | 0 | 1 |
| BC_ALWAYS_QUERY | 1 | 1 | 0 | 1 | 0 | 0 | 1 |
| FULL | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## Notes
- TRUST_ONLY must never print BC updates/queries (hard assert).
- BC_ALWAYS_QUERY is worst-case overhead (cache OFF, probe ON).
- FULL enables privacy + revocation on top of BC_TRUST.
