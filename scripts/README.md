# Developer scripts
Status: LOCKED (conceptual).
Purpose: Local helpers only.
Owns: bootstrap/hash/package helpers
Boundaries: no business logic
When we unlock this: keep tiny, documented

- `run_segment1b.py`: Execute Segment 1B (S0–S2) runs from a YAML config, feeding `python -m engine.cli.segment1b` for nightly drivers.