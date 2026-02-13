# Local Parity - Spine Green v0 Docs Index

This folder captures the local parity run design and migration prep for **Spine Green v0**.

Scope in this baseline:
- Control and Ingress
- RTDL
- Case and Labels
- Run/Operate and Observability/Governance

Out of scope for this baseline:
- Learning and Registry (OFS/MF/MPR)

## Conventions

- `platform_run_id` is the platform-run identity for run-scoped artifacts.
- `scenario_run_id` is SR scenario identity; do not substitute it for platform artifact paths.
- Canonical phase reference key is `phase_id=P#` from `P0` to `P11`.
- `P12` is optional teardown and is outside Spine Green v0 closure acceptance.
- Run-operate uses hybrid artifacts:
  - pack-scoped control/state/status under `runs/fraud-platform/operate/<pack_id>/...`
  - run-scoped logs/events under `runs/fraud-platform/<platform_run_id>/operate/<pack_id>/...`

## Canonical Phase IDs

- `P0` substrate ready
- `P1` run pinned
- `P2` daemons ready
- `P3` oracle ready
- `P4` ingest ready
- `P5` ready published
- `P6` streaming active
- `P7` ingest committed
- `P8` RTDL caught up
- `P9` decision chain committed
- `P10` case + labels committed
- `P11` obs/gov closed
- `P12` optional teardown (non-closure phase)

## Reading Order

1. `spine_green_v0_run_process_flow.txt`
2. `addendum_1_phase_state_machine_and_gates.txt`
3. `addendum_1_operator_gate_checklist.txt`
4. `addendum_1_phase_to_packaging_map.txt`
5. `addendum_2_process_job_cards.txt`
6. `addendum_3_rerun_cleanup_matrix.txt`
7. `addendum_4_io_ownership_matrix.txt`
8. `addendum_5_concurrency_backpressure_knobs.txt`

## Document Roles

- `spine_green_v0_run_process_flow.txt`
  - Main file. End-to-end local run process flow for Spine Green v0.

- `addendum_1_phase_state_machine_and_gates.txt`
  - Addendum 1A. Phase state machine with entry/exit gates and retry posture.

- `addendum_1_operator_gate_checklist.txt`
  - Addendum 1B. Minimum operator checklist for declaring run PASS.

- `addendum_1_phase_to_packaging_map.txt`
  - Addendum 1C. One-page mapping from phase to packaging/deployment target.

- `addendum_2_process_job_cards.txt`
  - Addendum 2. Per-process job cards for migration packaging and execution.

- `addendum_3_rerun_cleanup_matrix.txt`
  - Addendum 3. Rerun/cleanup levels and safe retry guidance.

- `addendum_4_io_ownership_matrix.txt`
  - Addendum 4. IO ownership matrix for reads/writes/calls and permission planning.

- `addendum_5_concurrency_backpressure_knobs.txt`
  - Addendum 5. Behavior/safety/perf knobs for concurrency and backpressure.
