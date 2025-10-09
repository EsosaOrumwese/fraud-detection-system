# AGENT BRIEF - S1 HURDLE L0

Purpose: Handle schema-bound IO for the hurdle decision. Fetch coefficients, prepare RNG streams, and persist Bernoulli outcomes for each merchant.

Guidance for future agents:
- Keep files limited to loading and writing; mathematical transforms belong in L1.
- Verify all artefact hashes against the registry before proceeding.
- Record RNG counters with enough detail for L3 replay.

