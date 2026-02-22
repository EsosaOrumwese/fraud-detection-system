# Migration To Dev - Authority Index

This folder contains the authoritative migration documents for lifting
Spine Green v0 from local parity to dev_min managed substrate.

## Files
- `dev_min_spine_green_v0_run_process_flow.md`
  - Canonical dev_min run-process twin keyed by `phase_id=P#` (`P0..P11`, `P12` teardown).
- `dev_min_handles.registry.v0.md`
  - Single source of truth for dev_min wiring handles (S3, Kafka, ECS, DB, IAM, evidence paths).

## Mapping Source (Semantic Authority)
These docs translate and preserve the canonical local-parity flow in:
- `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
- `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
- `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
- `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
- `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
- `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`
- `docs/design/platform/local-parity/addendum_5_concurrency_backpressure_knobs.txt`

## Working Rule
Treat the run-process document + handles registry as a pair:
- process-flow defines phase semantics, gates, and proof obligations;
- handles registry defines the concrete names/paths/IDs used by implementation.
