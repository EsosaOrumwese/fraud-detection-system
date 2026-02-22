# Migration To Dev - Authority Index

This folder contains the authoritative migration documents for lifting:
1. Spine Green v0 from local parity to dev_min managed substrate.
2. Learning/Registry + full-platform closure from dev_min baseline to dev_full.

## Files
- `dev_min_spine_green_v0_run_process_flow.md`
  - Canonical dev_min run-process twin keyed by `phase_id=P#` (`P0..P11`, `P12` teardown).
- `dev_min_handles.registry.v0.md`
  - Single source of truth for dev_min wiring handles (S3, Kafka, ECS, DB, IAM, evidence paths).
- `dev_full_handles.registry.v0.md`
  - Single source of truth for dev_full Learning/Registry + full-platform handle surfaces (`M11+`).

## Dev-Full Authority Pair
- `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
  - Pins dev_full migration posture for Learning/Evolution and full-platform closure.
- `dev_full_handles.registry.v0.md`
  - Carries concrete handle registry for all dev_full runtime, identity, data, and evidence surfaces.

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

For `M11+` (Learning/Registry + full-platform closure), `dev_full` authority docs are mandatory.
