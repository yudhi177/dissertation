# Implementation Roadmap (Execution Plan)

## P0 — Security-correct session establishment
- Authenticated ECDH: bind ephemeral public key to pseudonym cert signature (or SimpleSig binding in sim).
- Replay protection: nonce/timestamp verification + replay cache.
- MITM test mode: pubkey swap must fail.
- Events: AUTH_START/AUTH_OK/AUTH_FAIL (+ reason).

Ship gate:
- MITM enabled → handshake fails
- Replay resend → dropped

## P1 — Trust model defensibility
- Explicit trust equation + decay + recovery
- TRUST_ONLY baseline (trust on, blockchain off)

## P2 — Mobility-aware trust continuity
- Bounded staleness policy Dmax
- staleMismatch metric
- FAST allowed only if trust fresh

## P3 — Blockchain realism
- Calibrate query/update delays or justify
- Latency decomposition

## P4 — Privacy evaluation upgrade
- Pseudonym rotation policies compare
- Linkability attacker model + event logs

## P5 — Attack + revocation evaluation
- Detection time / FP rate
- Revocation delay CDF

## P6 — Final pack freeze
- Multi-seed + CI95 + baselines
- Publish pack + manifests + checklist
