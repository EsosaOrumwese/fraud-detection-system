# AGENT BRIEF - S0 FOUNDATIONS L0

Purpose: Manage the schema-bound IO for S0. Load the merchant snapshot, GDP buckets, and governed artefacts, and prepare write envelopes for downstream stages.

Guidance for future agents:
- Keep functions limited to validated reads and structured writes; route business rules to L1 kernels.
- Honour contract paths from docs/model_spec when adding new inputs.
- Surface deterministic metadata and hashes exactly as specified in the state docs.

