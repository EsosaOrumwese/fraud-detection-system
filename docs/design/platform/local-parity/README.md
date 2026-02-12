# Local Parity - Spine Green v0 Docs Index

This folder captures the local parity run design and migration prep for **Spine Green v0**.

Scope in this baseline:
- Control and Ingress
- RTDL
- Case and Labels
- Run/Operate and Observability/Governance

Out of scope for this baseline:
- Learning and Registry (OFS/MF/MPR)

## Reading Order

1. `spine_green_v0_run_process_flow.md`
2. `addendum_1_phase_state_machine_and_gates.md`
3. `addendum_1_operator_gate_checklist.md`
4. `addendum_1_phase_to_packaging_map.md`
5. `addendum_2_process_job_cards.md`
6. `addendum_3_rerun_cleanup_matrix.md`
7. `addendum_4_io_ownership_matrix.md`
8. `addendum_5_concurrency_backpressure_knobs.md`

## Document Roles

- `spine_green_v0_run_process_flow.md`
  - Main file. End-to-end local run process flow for Spine Green v0.

- `addendum_1_phase_state_machine_and_gates.md`
  - Addendum 1A. Phase state machine with entry/exit gates and retry posture.

- `addendum_1_operator_gate_checklist.md`
  - Addendum 1B. Minimum operator checklist for declaring run PASS.

- `addendum_1_phase_to_packaging_map.md`
  - Addendum 1C. One-page mapping from phase to packaging/deployment target.

- `addendum_2_process_job_cards.md`
  - Addendum 2. Per-process job cards for migration packaging and execution.

- `addendum_3_rerun_cleanup_matrix.md`
  - Addendum 3. Rerun/cleanup levels and safe retry guidance.

- `addendum_4_io_ownership_matrix.md`
  - Addendum 4. IO ownership matrix for reads/writes/calls and permission planning.

- `addendum_5_concurrency_backpressure_knobs.md`
  - Addendum 5. Behavior/safety/perf knobs for concurrency and backpressure.
