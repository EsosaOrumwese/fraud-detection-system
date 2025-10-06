# AGENT BRIEF - S0 FOUNDATIONS L3

Purpose: Validate S0 outputs by recomputing deterministic quantities and asserting lineage before later states consume them.

Guidance for future agents:
- Treat all inputs as read-only; this layer should never mutate artefacts.
- Encode assertions with clear failure messages tied to spec sections.
- Keep checks deterministic so the validation bundle can be replayed byte for byte.

