# AGENT BRIEF - S0 FOUNDATIONS L2

Purpose: Orchestrate S0 by sequencing IO from L0 with the kernels in L1, producing seeded state records and manifest fingerprints.

Guidance for future agents:
- Maintain idempotent execution; reruns must not duplicate outputs.
- Centralise error handling here and fail closed on any contract violation.
- Emit structured logs for RNG seed derivations to support validation in L3.
