# Migration To Dev - Scaffold

This folder contains dev-migration scaffolds for Spine Green v0.

## Files
- `dev_min_spine_green_v0_run_process_flow.md`
  - Dev-min run-process twin (phase-keyed) to be authored.
- `dev_min_handles.registry.v0.md`
  - Dev-min handles registry (single source of wiring identifiers) to be authored.

## Mapping Source
These migration docs are intended to map and translate the canonical local flow expressed in:
- `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
- `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
- `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
- `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`

Use canonical `phase_id=P#` references (`P0..P11`, with `P12` teardown-only) while authoring.
