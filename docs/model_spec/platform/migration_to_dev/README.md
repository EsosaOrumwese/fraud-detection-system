# Migration To Dev - Authority Index

This folder contains the authoritative migration documents for lifting platform runtime
from local parity semantics into managed substrate environments.

## Active authority sets

### Dev-min (certified spine baseline)
- `dev_min_spine_green_v0_run_process_flow.md`
  - Canonical dev_min run-process twin keyed by `phase_id=P#` (`P0..P11`, `P12` teardown).
- `dev_min_handles.registry.v0.md`
  - Single source of truth for dev_min wiring handles (S3, Kafka, ECS, DB, IAM, evidence paths).

### Dev-full (full-platform extension authority)
- `dev_full_platform_green_v0_run_process_flow.md`
  - Canonical dev_full run-process authority keyed by `phase_id=P#` (`P(-1)`, `P0..P17`) for Spine + Learning/Evolution closure.
- `dev_full_handles.registry.v0.md`
  - Single source of truth for dev_full concrete handles (EKS/MSK/S3/Aurora/Redis/Databricks/SageMaker/MWAA/Step Functions/IAM/evidence).
  - Note: `TO_PIN` materialization handles in Section 14 are explicit fail-closed prerequisites before first `dev-full-up`.

## Mapping source (semantic authority)
These docs translate and preserve the canonical local-parity flow in:
- `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
- `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
- `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
- `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
- `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
- `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`
- `docs/design/platform/local-parity/addendum_5_concurrency_backpressure_knobs.txt`

## Working rule
Treat process-flow + handles registry as a pair for each environment:
- process-flow defines phase semantics, gates, and proof obligations;
- handles registry defines concrete names/paths/IDs used by implementation.
