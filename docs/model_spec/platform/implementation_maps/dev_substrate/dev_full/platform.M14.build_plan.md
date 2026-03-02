# Dev Substrate Deep Plan - M14 (POST-P17 REPIN MATERIALIZATION_AND_RECERT)
_Status source of truth: `platform.build_plan.md`_
_Track: `dev_full`_
_Last updated: 2026-03-02_

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

Entry conditions:
1. `M14.A` is pass (`ADVANCE_TO_M14_B`, `M14.B_READY`).
2. Required handles for managed sort are resolved:
   - `ORACLE_STREAM_SORT_ENGINE`,
   - `ORACLE_STREAM_SORT_RUNTIME_PATH`,
   - `ORACLE_STREAM_SORT_EMR_SERVERLESS_APP`,
   - `ORACLE_STREAM_SORT_EXECUTION_ROLE_ARN`,
   - `ORACLE_STREAM_SORT_EMR_RELEASE_LABEL`,
   - `ORACLE_REQUIRED_OUTPUT_IDS`,
   - `ORACLE_SORT_KEY_BY_OUTPUT_ID`,
   - `ORACLE_SOURCE_NAMESPACE`,
   - `ORACLE_ENGINE_RUN_ID`,
   - `S3_OBJECT_STORE_BUCKET`,
   - `S3_EVIDENCE_BUCKET`.
3. Oracle raw source paths for required output IDs are readable.

Execution steps:
1. Build deterministic `m14b_execution_id` and run root under `runs/dev_substrate/dev_full/m14/<execution_id>/`.
2. Resolve source mapping for required outputs under oracle run root:
   - `arrival_events_5B -> data/layer2/5B/arrival_events/`
   - `s1_arrival_entities_6B -> data/layer3/6B/s1_arrival_entities_6B/`
   - `s3_event_stream_with_fraud_6B -> data/layer3/6B/s3_event_stream_with_fraud_6B/`
   - `s3_flow_anchor_with_fraud_6B -> data/layer3/6B/s3_flow_anchor_with_fraud_6B/`
3. Ensure EMR Serverless app exists and is started for configured app handle.
4. Submit managed stream-sort Spark job and wait for terminal state.
5. Validate per-output materialization under:
   - `oracle-store/{oracle_source_namespace}/{oracle_engine_run_id}/stream_view/ts_utc/output_id=<output_id>/`
6. Require per-output `_stream_sort_receipt.json`, `_stream_view_manifest.json`, and parquet presence.
7. Publish local and durable artifacts:
   - `m14b_streamsort_materialization_snapshot.json`,
   - `m14b_streamsort_parity_report.json`,
   - `m14b_blocker_register.json`,
   - `m14b_execution_summary.json`.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B3` output parity mismatch.
3. `M14-B6` artifact publication/readback failure.

DoD:
- [x] managed sort executes successfully.
- [x] required outputs + manifests + receipts parity-verified.
- [x] local + durable `m14b_*` artifacts are readable.
- [x] execution summary is pass and advances gate to `M14.C_READY`.

Runtime budget:
1. Target <= 120 minutes.

### M14.C - SR Runtime Materialization
Goal:
1. Materialize SR on `Step Functions + Lambda/job` with READY semantic parity.

Entry conditions:
1. `M14.B` is pass (`ADVANCE_TO_M14_C`, `M14.C_READY`).
2. Required SR runtime handles are resolved and non-placeholder:
   - `SR_RUNTIME`,
   - `SR_READY_COMPUTE_MODE`,
   - `SR_READY_COMMIT_AUTHORITY`,
   - `SR_READY_COMMIT_STATE_MACHINE`,
   - `SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF`,
   - `SR_READY_COMMIT_RECEIPT_PATH_PATTERN`,
   - `SFN_PLATFORM_RUN_ORCHESTRATOR_V0`,
   - `S3_EVIDENCE_BUCKET`.
3. Step Functions state machine referenced by SR commit authority exists and is invokable.

Execution steps:
1. Build deterministic `m14c_execution_id` and local run root under `runs/dev_substrate/dev_full/m14/<execution_id>/`.
2. Resolve SR commit state-machine indirection:
   - `SR_READY_COMMIT_STATE_MACHINE` -> concrete handle key -> concrete state-machine name.
3. Run commit-authority probe:
   - start Step Functions execution with deterministic name + run-scoped input payload,
   - wait for terminal status and require `SUCCEEDED`.
4. Run idempotency probe:
   - attempt duplicate start with same execution name,
   - require `ExecutionAlreadyExists` (or equivalent duplicate guard) as pass condition.
5. Emit run-scoped READY commit receipt to:
   - `evidence/runs/{platform_run_id}/sr/ready_commit_receipt.json`,
   - requiring populated `step_functions_execution_arn`.
6. Emit local + durable control artifacts:
   - `m14c_sr_materialization_snapshot.json`,
   - `m14c_blocker_register.json`,
   - `m14c_execution_summary.json`.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B3` READY semantic drift.
3. `M14-B6` artifact publication/readback failure.

DoD:
- [x] READY commit evidence unchanged (`commit_authority=step_functions_only`, receipt path pattern unchanged, receipt includes SFN execution ARN).
- [x] idempotency semantics preserved (duplicate execution-name rejected deterministically).
- [x] local + durable `m14c_*` artifacts are readable.
- [x] execution summary is pass and advances gate to `M14.D_READY`.

Runtime budget:
1. Target <= 20 minutes.

### M14.D - WSP Runtime Materialization
Goal:
1. Materialize WSP on `ECS/Fargate` ephemeral task with contract parity.

Entry conditions:
1. `M14.C` is pass (`ADVANCE_TO_M14_D`, `M14.D_READY`).
2. Required handles are resolved and non-placeholder:
   - `WSP_RUNTIME`,
   - `WSP_TRIGGER_MODE`,
   - `WSP_MAX_INFLIGHT`,
   - `WSP_RETRY_MAX_ATTEMPTS`,
   - `WSP_RETRY_BACKOFF_MS`,
   - `WSP_STOP_ON_NONRETRYABLE`,
   - `IG_BASE_URL`,
   - `IG_AUTH_MODE`,
   - `IG_AUTH_HEADER_NAME`,
   - `SSM_IG_API_KEY_PATH`,
   - `ORACLE_SOURCE_NAMESPACE`,
   - `ORACLE_ENGINE_RUN_ID`,
   - `ORACLE_REQUIRED_OUTPUT_IDS`,
   - `S3_OBJECT_STORE_BUCKET`,
   - `DDB_IG_IDEMPOTENCY_TABLE`.
3. Runtime substrate for lane execution is available:
   - VPC + public subnets discoverable,
   - ECS/Fargate cluster/task definition can be materialized,
   - image in ECR is pullable by task execution role.

Execution steps:
1. Build deterministic `m14d_execution_id` and local run root under `runs/dev_substrate/dev_full/m14/<execution_id>/`.
2. Materialize/verify ECS ephemeral lane primitives:
   - ECS cluster,
   - task-execution role,
   - task-runtime role,
   - task definition (WSP entrypoint command override).
3. Start one Fargate runtask using run-scoped `platform_run_id` and bounded event cap.
4. Wait terminal task status and capture container exit code + log stream reference.
5. Validate contract parity and lane outcomes:
   - WSP runtime pins equal expected (`ECS_FARGATE_RUNTASK_EPHEMERAL`, `READY_EVENT_TRIGGERED`),
   - retry knobs in launch profile match pinned values,
   - IG admission evidence exists for run-scoped `platform_run_id` in idempotency table.
6. Publish local + durable artifacts:
   - `m14d_wsp_materialization_snapshot.json`,
   - `m14d_blocker_register.json`,
   - `m14d_execution_summary.json`.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B3` envelope/retry/dedupe drift.
3. `M14-B6` artifact publication/readback failure.

DoD:
- [ ] WSP lane executes on ECS/Fargate runtask and task exits successfully.
- [ ] envelope/retry contract parity checks pass against pinned handles.
- [ ] run-scoped IG admission evidence is present and non-zero for the lane run id.
- [ ] local + durable `m14d_*` artifacts are readable.
- [ ] execution summary is pass and advances gate to `M14.E_READY`.

Runtime budget:
1. Target <= 45 minutes.

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
- [x] M14.B
- [x] M14.C
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

## 12) M14.B Closure Snapshot
1. First run failed closed:
   - execution id: `m14b_streamsort_materialization_20260302T002019Z`,
   - blocker `M14-B2`: invalid pinned release label (`emr-6.15.0-latest`) for EMR Serverless app create,
   - additional downstream `M14-B3` artifacts absent because job failed before materialization.
2. Remediation set applied:
   - repinned handles in registry:
     - `ORACLE_STREAM_SORT_EMR_RELEASE_LABEL = emr-6.15.0`,
     - `EMR_EKS_RELEASE_LABEL = emr-6.15.0`,
   - patched IaC role trust in `infra/terraform/dev_full/runtime/main.tf`:
     - added `Service: emr-serverless.amazonaws.com` to `assume_role_flink`,
   - applied runtime Terraform target for `aws_iam_role.flink_execution`.
3. Green rerun:
   - execution id: `m14b_streamsort_materialization_20260302T002345Z`,
   - EMR application: `fraud-platform-dev-full-oracle-stream-sort-v0` (`application_id=00g3qriott52200t`),
   - job run: `00g3qrko3qpk9g0v` (`state=SUCCESS`),
   - result: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M14_C`, `next_gate=M14.C_READY`.
4. Required output closure (all pass):
   - `arrival_events_5B`: receipt+manifest present, parquet count `400`, row parity `236,691,694 == 236,691,694`,
   - `s1_arrival_entities_6B`: receipt+manifest present, parquet count `400`, row parity `236,691,694 == 236,691,694`,
   - `s3_event_stream_with_fraud_6B`: receipt+manifest present, parquet count `400`, row parity `473,383,388 == 473,383,388`,
   - `s3_flow_anchor_with_fraud_6B`: receipt+manifest present, parquet count `400`, row parity `236,691,694 == 236,691,694`.
5. Local evidence:
   - `runs/dev_substrate/dev_full/m14/m14b_streamsort_materialization_20260302T002345Z/m14b_streamsort_materialization_snapshot.json`,
   - `runs/dev_substrate/dev_full/m14/m14b_streamsort_materialization_20260302T002345Z/m14b_streamsort_parity_report.json`,
   - `runs/dev_substrate/dev_full/m14/m14b_streamsort_materialization_20260302T002345Z/m14b_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14b_streamsort_materialization_20260302T002345Z/m14b_execution_summary.json`.
6. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14b_streamsort_materialization_20260302T002345Z/m14b_streamsort_materialization_snapshot.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14b_streamsort_materialization_20260302T002345Z/m14b_streamsort_parity_report.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14b_streamsort_materialization_20260302T002345Z/m14b_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14b_streamsort_materialization_20260302T002345Z/m14b_execution_summary.json`.

### M14.B Performance Receipt (short)
1. Managed job runtime:
   - start: `2026-03-02T00:24:38Z`,
   - end: `2026-03-02T00:30:23Z`,
   - `totalExecutionDurationSeconds=345` (EMR Serverless authoritative metric).
2. Workload size (aggregate across required outputs):
   - `total_raw_rows=1,183,458,470`,
   - `total_sorted_rows=1,183,458,470`,
   - row parity: `PASS` for all required outputs.
3. Effective processing rate (aggregate rows / execution seconds):
   - `~3,430,314 rows/second`.
4. Billed compute utilization:
   - `vCPUHour=12.226`,
   - `memoryGBHour=54.054`,
   - `storageGBHour=0.0` (billed),
   - `storageGBHour=120.333` (total utilization).
5. Source of truth for this receipt:
   - EMR job metadata: `application_id=00g3qriott52200t`, `job_run_id=00g3qrko3qpk9g0v`,
   - parity artifact: `m14b_streamsort_parity_report.json`.

### M14.B Extension - Offline Truth Sort (no-native-ts tables)
1. Objective:
   - extend managed sorting to offline truth outputs that do not carry native `ts_utc` so downstream learning lanes can consume ordered truth views without local compute.
2. Managed execution:
   - execution id: `m14c_truth_sort_20260302T012806Z`,
   - EMR application/job: `00g3qriott52200t` / `00g3qsplb0rfi00v`,
   - terminal state: `SUCCESS`.
3. Derived timestamp policy applied (fail-closed):
   - `s4_event_labels_6B`: derive `ts_utc` from `s3_event_stream_with_fraud_6B` via join keys `(seed, manifest_fingerprint, scenario_id, flow_id, event_seq)`,
   - `s4_flow_truth_labels_6B` and `s4_flow_bank_view_6B`: derive `ts_utc` from `s3_flow_anchor_with_fraud_6B` via join keys `(seed, manifest_fingerprint, scenario_id, flow_id)`,
   - `s4_case_timeline_6B`: use native `ts_utc`,
   - unmatched derived timestamp rows are hard-fail; observed unmatched count: `0`.
4. Published target surface:
   - `oracle-store/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/truth_view/ts_utc/output_id=<output_id>/`.
5. Closure verification:
   - `s4_event_labels_6B`: parquet `600`, manifest+receipt present,
   - `s4_flow_truth_labels_6B`: parquet `600`, manifest+receipt present,
   - `s4_flow_bank_view_6B`: parquet `600`, manifest+receipt present,
   - `s4_case_timeline_6B`: parquet `300`, manifest+receipt present.
6. Evidence:
   - local: `runs/dev_substrate/dev_full/m14/m14c_truth_sort_20260302T012806Z/m14c_truth_sort_summary.json`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14c_truth_sort_20260302T012806Z/oracle/offline_truth_sort_receipt.json`.

## 13) M14.C Closure Snapshot
1. Executed SR runtime materialization with Step Functions commit authority:
   - execution id: `m14c_sr_materialization_20260302T015340Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `m14c_verdict=ADVANCE_TO_M14_D`, `next_gate=M14.D_READY`.
2. Commit-authority parity checks passed against baseline M6.C evidence:
   - `commit_authority`: unchanged (`step_functions_only`),
   - state-machine name: unchanged (`fraud-platform-dev-full-platform-run-v0`),
   - receipt path pattern: unchanged (`evidence/runs/{platform_run_id}/sr/ready_commit_receipt.json`).
3. Idempotency semantics probe passed:
   - first start-execution succeeded,
   - duplicate start with same execution name was rejected (`ExecutionAlreadyExists`).
4. Run-scoped READY receipt written with required SFN execution reference:
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260302T015340Z/sr/ready_commit_receipt.json`.
5. Local artifacts:
   - `runs/dev_substrate/dev_full/m14/m14c_sr_materialization_20260302T015340Z/m14c_sr_materialization_snapshot.json`,
   - `runs/dev_substrate/dev_full/m14/m14c_sr_materialization_20260302T015340Z/m14c_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14c_sr_materialization_20260302T015340Z/m14c_execution_summary.json`.
6. Durable run-control artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14c_sr_materialization_20260302T015340Z/m14c_sr_materialization_snapshot.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14c_sr_materialization_20260302T015340Z/m14c_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14c_sr_materialization_20260302T015340Z/m14c_execution_summary.json`.
