# Dev Substrate Deep Plan - M14 (POST-P17 REPIN MATERIALIZATION_AND_RECERT)
_Status source of truth: `platform.build_plan.md`_
_Track: `dev_full`_
_Last updated: 2026-03-01_

## 0) Purpose
M14 is the single alignment phase for the approved dev_full v0.2 runtime-placement repin.

M14 is green only when all are true:
1. Repinned runtime lanes are materialized on approved managed targets.
2. Contract parity remains intact for admission, projection, decision, audit, case, label, and learning interfaces.
3. Non-regression pack passes on repinned runtime surfaces.
4. Cost and performance posture are within pinned envelopes.
5. Rollback posture is executable for every repinned lane.
6. Final M14 closure artifacts are published and parity-verified.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
4. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.build_plan.md`

## 2) Entry Contract (Fail-Closed)
M14 cannot execute unless all are true:
1. `M13` is `DONE` in `platform.build_plan.md`.
2. v0.2 repin overlay is present and consistent across authority, run-process, handles, and plan docs.
3. Required handle set for repinned lanes is materialized (no unresolved `TO_PIN` for active M14 lane).
4. Managed workflow lane for M14 exists and is dispatchable.

## 3) Scope Boundary
In scope:
1. Runtime-placement repin materialization and verification.
2. Re-certification of non-regression claims on repinned lanes.
3. Cost/performance closure and rollback-contract closure.

Out of scope:
1. New product capability not required for runtime repin.
2. Rewriting baseline semantics for already certified contracts.

## 4) Capability-Lane Coverage Matrix
| Capability lane | Primary subphase | Minimum PASS evidence |
| --- | --- | --- |
| Repin handle freeze | M14.A | explicit handle matrix, unresolved count = 0 |
| M5 stream-sort move | M14.B | managed sort receipt + parity report |
| SR move (SFN+Lambda/job) | M14.C | READY parity bundle + idempotency continuity |
| WSP move (Fargate task) | M14.D | envelope/retry/dedupe parity snapshot |
| IEG/OFP move (Managed Flink) | M14.E | branch-separated metrics + lag/offset continuity |
| Archive connector cutover | M14.F | offset continuity + S3 sink parity proof |
| AL/Case/Label move | M14.G | contract parity receipts for AL/CaseTrigger/CM/LS |
| Non-regression pack | M14.H | P5/P8/P9/P10/P11/P12 regression matrix pass |
| Cost/perf recert | M14.I | phase budget receipt + perf scorecard pass |
| Final closure sync | M14.J | m14 summary + blocker register parity pass |

## 5) Subphase Execution Contracts

### M14.A - Repin Handle Freeze
Goal:
1. Freeze and validate complete handle contract for all repinned lanes.

Entry conditions:
1. `M13` is `DONE` in `platform.build_plan.md`.
2. Repin authority trio is readable:
   - `dev-full_managed-substrate_migration.design-authority.v0.md`,
   - `dev_full_platform_green_v0_run_process_flow.md`,
   - `dev_full_handles.registry.v0.md`.
3. Required freeze-set handles are discoverable in registry.

Required freeze-set handles and pinned values:
1. `ORACLE_STREAM_SORT_ENGINE = "EMR_SERVERLESS_SPARK"`
2. `ORACLE_STREAM_SORT_RUNTIME_PATH = "EMR_SERVERLESS_SPARK"`
3. `ORACLE_STREAM_SORT_EMR_SERVERLESS_APP` (non-placeholder)
4. `SR_RUNTIME = "STEP_FUNCTIONS_PLUS_LAMBDA_JOB"`
5. `SR_READY_COMPUTE_MODE = "control_plane_orchestration_not_flink"`
6. `WSP_RUNTIME = "ECS_FARGATE_RUNTASK_EPHEMERAL"`
7. `WSP_TRIGGER_MODE = "READY_EVENT_TRIGGERED"`
8. `FLINK_RUNTIME_PATH_ACTIVE = "MSF_MANAGED"`
9. `FLINK_APP_RTDL_IEG_OFP_V0` (non-placeholder)
10. `FLINK_APP_RTDL_IEG_OFP_SPLIT_POLICY` (non-placeholder)
11. `FLINK_APP_RTDL_IEG_OFP_METRIC_NAMESPACES` (non-placeholder)
12. `RUNTIME_WORKLOAD_ARCHIVE = "MANAGED_CONNECTOR_TO_S3"`
13. `RUNTIME_WORKLOAD_AL = "ECS_FARGATE_SERVICE"`
14. `RUNTIME_WORKLOAD_CASE_TRIGGER = "ECS_FARGATE_SERVICE"`
15. `RUNTIME_WORKLOAD_CM = "ECS_FARGATE_SERVICE_PLUS_AURORA"`
16. `RUNTIME_WORKLOAD_LS = "ECS_FARGATE_SERVICE_PLUS_AURORA"`

Execution steps:
1. Parse handle registry and build explicit freeze-set matrix (`key`, `expected`, `actual`, `status`).
2. Fail-closed if required handle is missing, placeholder (`TO_PIN`), malformed, or value-drifted.
3. Run authority cross-check assertions for repin posture consistency across:
   - design authority,
   - run-process flow,
   - handle registry.
4. Emit local artifacts under:
   - `runs/dev_substrate/dev_full/m14/<execution_id>/`.
5. Publish durable artifacts under:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/<execution_id>/`.
6. Emit deterministic execution summary (`overall_pass`, `blocker_count`, `verdict`, `next_gate`).

Blockers:
1. `M14-B1` unresolved handle or malformed type.
2. `M14-B6` artifact publication/readback failure.

DoD:
- [x] handle matrix complete and published.
- [x] no unresolved required handle.
- [x] authority cross-check posture is consistent for repin targets.
- [x] local + durable artifacts are readable.
- [x] execution summary is pass and advances gate to `M14.B_READY`.

Runtime budget:
1. Target <= 10 minutes.

### M14.B - M5 Stream-Sort Materialization
Goal:
1. Materialize `EMR_SERVERLESS_SPARK` path for M5 and prove output parity.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B3` output parity mismatch.

DoD:
- [ ] managed sort executes successfully.
- [ ] required outputs + manifests + receipts parity-verified.

### M14.C - SR Runtime Materialization
Goal:
1. Materialize SR on `Step Functions + Lambda/job` with READY semantic parity.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B3` READY semantic drift.

DoD:
- [ ] READY commit evidence unchanged.
- [ ] idempotency and gate semantics preserved.

### M14.D - WSP Runtime Materialization
Goal:
1. Materialize WSP on `ECS/Fargate` ephemeral task with contract parity.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B3` envelope/retry/dedupe drift.

DoD:
- [ ] envelope schema parity pass.
- [ ] retry and dedupe behavior parity pass.

### M14.E - RTDL Projection Materialization
Goal:
1. Materialize IEG/OFP on `AWS Managed Service for Apache Flink` canonical runtime.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B4` lag/offset/throughput regression.

DoD:
- [ ] single-app branch-separated evidence for `ieg_*` and `ofp_*`.
- [ ] lag, offset continuity, and replay integrity pass.

### M14.F - Archive Connector Cutover
Goal:
1. Replace archive writer runtime path with managed connector-to-S3 and prove continuity.

Blockers:
1. `M14-B2` connector materialization failure.
2. `M14-B3` continuity drift.

DoD:
- [ ] offset continuity proven across cutover boundary.
- [ ] archive object and sink parity proofs pass.

### M14.G - AL/Case/Label Placement Materialization
Goal:
1. Materialize AL, CaseTrigger, CM, LS on ECS/Fargate and preserve semantics.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B3` contract drift.

DoD:
- [ ] side-effect/idempotency semantics remain stable.
- [ ] case/label timelines and append semantics remain stable.

### M14.H - Non-Regression Pack on Repinned Runtime
Goal:
1. Re-run targeted non-regression closures on repinned lanes.

Blockers:
1. `M14-B3` semantic non-regression failure.

DoD:
- [ ] regression matrix pass for `P5/P8/P9/P10/P11/P12`.
- [ ] no unresolved regression blocker.

### M14.I - Cost and Performance Re-Certification
Goal:
1. Close repin-window cost/performance posture with explicit receipt.

Blockers:
1. `M14-B4` performance regression.
2. `M14-B5` cost envelope breach.

DoD:
- [ ] performance scorecard pass against pinned envelopes.
- [ ] cost-to-outcome receipt committed and within envelope.

### M14.J - Final Repin Closure Sync
Goal:
1. Publish deterministic M14 verdict and rollback posture closure.

Blockers:
1. `M14-B6` evidence parity/readability failure.
2. `M14-B7` rollback path not executable.

DoD:
- [ ] `m14_execution_summary.json` + `m14_blocker_register.json` parity pass.
- [ ] rollback contract for each repinned lane is readable and executable.
- [ ] verdict published: `M14_COMPLETE_GREEN`.

## 6) Artifact Contract
Local run folder:
1. `runs/dev_substrate/dev_full/m14/<execution_id>/...`

Durable run-control mirror:
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/<execution_id>/...`

Required artifacts:
1. `m14a_handle_closure_snapshot.json`
2. `m14b_streamsort_materialization_snapshot.json`
3. `m14c_sr_materialization_snapshot.json`
4. `m14d_wsp_materialization_snapshot.json`
5. `m14e_flink_projection_snapshot.json`
6. `m14f_archive_connector_snapshot.json`
7. `m14g_case_label_materialization_snapshot.json`
8. `m14h_non_regression_snapshot.json`
9. `m14i_phase_cost_performance_receipt.json`
10. `m14_execution_summary.json`
11. `m14_blocker_register.json`

## 7) Runtime Budgets and Cost Envelope
1. Every subphase must publish planned envelope before execution.
2. Non-active lanes must stay idle-safe.
3. Any unattributed spend blocks advancement.
4. Any runtime budget breach without approved waiver blocks advancement.

## 8) Closure Contract
M14 closes only when:
1. All subphases `M14.A..M14.J` pass with blocker count `0`.
2. Repinned runtime lanes have no unresolved semantic drift.
3. Cost/performance receipts are committed and reviewed.
4. Final verdict is `M14_COMPLETE_GREEN`.

## 9) Progress Tracker
- [x] M14.A
- [ ] M14.B
- [ ] M14.C
- [ ] M14.D
- [ ] M14.E
- [ ] M14.F
- [ ] M14.G
- [ ] M14.H
- [ ] M14.I
- [ ] M14.J

## 10) Notes
1. This deep plan is execution detail only.
2. Phase status changes are controlled exclusively in `platform.build_plan.md`.

## 11) M14.A Closure Snapshot
1. First run failed closed due parser false-negative on valid handle lines with trailing inline notes:
   - execution id: `m14a_handle_freeze_20260302T000035Z`,
   - blockers: `M14-B1` on `FLINK_RUNTIME_PATH_ACTIVE`, `FLINK_APP_RTDL_IEG_OFP_V0`.
2. Remediation applied:
   - parser updated to accept trailing inline text after backtick assignment/bare-handle lines.
3. Green rerun:
   - execution id: `m14a_handle_freeze_20260302T000213Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M14_B`, `next_gate=M14.B_READY`,
   - required freeze-set: `16/16` pass, unresolved required handles: `0`.
4. Local evidence:
   - `runs/dev_substrate/dev_full/m14/m14a_handle_freeze_20260302T000213Z/m14a_handle_closure_snapshot.json`,
   - `runs/dev_substrate/dev_full/m14/m14a_handle_freeze_20260302T000213Z/m14a_handle_matrix.json`,
   - `runs/dev_substrate/dev_full/m14/m14a_handle_freeze_20260302T000213Z/m14a_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14a_handle_freeze_20260302T000213Z/m14a_execution_summary.json`.
5. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14a_handle_freeze_20260302T000213Z/m14a_handle_closure_snapshot.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14a_handle_freeze_20260302T000213Z/m14a_handle_matrix.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14a_handle_freeze_20260302T000213Z/m14a_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14a_handle_freeze_20260302T000213Z/m14a_execution_summary.json`.
