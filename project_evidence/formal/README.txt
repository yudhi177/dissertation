Scyther Formal Verification Evidence

Files:
1. v2x_handover_auth.spdl
   - Initial insecure protocol model
   - Multiple secrecy/authentication claims fail

2. v2x_handover_auth_result.txt
   - Result of insecure baseline verification

3. v2x_handover_auth_secure.spdl
   - Hardened protocol with identity binding and signed encrypted payloads
   - Most claims pass, but initiator-side synchronization/agreement still incomplete

4. v2x_handover_auth_secure_result.txt
   - Result of intermediate secure model verification

5. v2x_handover_auth_final.spdl
   - Final protocol with responder freshness nonce and explicit final ACK
   - All key authentication and synchronization claims pass

6. v2x_handover_auth_final_result.txt
   - Final successful verification result

Conclusion:
The final V2X handover authentication protocol resists the attacks found in the baseline model and satisfies secrecy, aliveness, weak agreement, non-injective agreement, and synchronization claims under Scyther analysis bounds.
