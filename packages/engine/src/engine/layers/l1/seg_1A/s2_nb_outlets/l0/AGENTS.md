# AGENT BRIEF - S2 NB OUTLETS L0

Purpose: Manage IO for the negative binomial outlet count stage. Load dispersion and mean parameters, receive hurdle survivors, and persist sampled domestic counts.

Guidance for future agents:
- Keep logic to schema interactions; delegate math to L1.
- Track rejection counts and metadata for the validation layer.
- Preserve deterministic ordering of merchants when writing results.

