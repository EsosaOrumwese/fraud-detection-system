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
6. `WSP_RUNTIME = "MSF_MANAGED_PRIMARY"`
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
2. Materialize/verify managed WSP stream-lane primitives:
   - managed Flink application or explicit `EKS_FLINK_OPERATOR` fallback ref,
   - execution role,
   - runtime spec / job ref for WSP lane entrypoint.
3. Start one run-scoped managed WSP stream lane using bounded event cap.
4. Wait terminal job/application status and capture runtime reference + log evidence.
5. Validate contract parity and lane outcomes:
   - WSP runtime pins equal expected (`MSF_MANAGED_PRIMARY`, `READY_EVENT_TRIGGERED`),
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
- [x] WSP lane executes on ECS/Fargate runtask and task exits successfully.
- [x] envelope/retry contract parity checks pass against pinned handles.
- [x] run-scoped IG admission evidence is present and non-zero for the lane run id.
- [x] local + durable `m14d_*` artifacts are readable.
- [x] execution summary is pass and advances gate to `M14.E_READY`.

Runtime budget:
1. Target <= 45 minutes.

### M14.E - RTDL Projection Materialization
Goal:
1. Materialize IEG/OFP on `AWS Managed Service for Apache Flink` canonical runtime.

Entry conditions:
1. `M14.D` is pass (`ADVANCE_TO_M14_E`, `M14.E_READY`).
2. Required handles are resolved and non-placeholder:
   - `FLINK_RUNTIME_PATH_ACTIVE`,
   - `FLINK_RUNTIME_PATH_ALLOWED`,
   - `FLINK_APP_RTDL_IEG_OFP_V0`,
   - `FLINK_APP_RTDL_IEG_OFP_SPLIT_POLICY`,
   - `FLINK_APP_RTDL_IEG_OFP_METRIC_NAMESPACES`,
   - `RTDL_CAUGHT_UP_LAG_MAX`,
   - `RTDL_CORE_CONSUMER_GROUP_ID`,
   - `S3_EVIDENCE_BUCKET`.
3. Prior RTDL closure evidence references are readable:
   - `P8.E` rollup matrix + verdict (`ieg`/`ofp` branch proofs),
   - `P6.B` lag posture snapshot,
   - `P12` replay-basis receipt.

Execution steps:
1. Build deterministic `m14e_execution_id` and local run root under `runs/dev_substrate/dev_full/m14/<execution_id>/`.
2. Run canonical MSF materialization probe:
   - attempt `kinesisanalyticsv2 create-application` with pinned Flink app handle and execution role posture,
   - capture exact command, API result, and error class/message into `m14e_msf_probe_receipt.json`.
3. Adjudicate runtime path:
   - if MSF probe succeeds, require app exists and is readable under `list/describe` and continue on canonical path,
   - if MSF probe is externally blocked (`UnsupportedOperationException` / account-gated), apply bounded fallback adjudication per policy and continue only when `FLINK_RUNTIME_PATH_ALLOWED` includes `EKS_FLINK_OPERATOR`.
4. Build branch-separated projection evidence:
   - verify `P8.E` rollup includes separate upstream rows/proofs for `IEG` and `OFP`,
   - require proof refs are readable in durable evidence.
5. Build continuity evidence:
   - lag posture pass from `P6.B` (`measured_lag <= RTDL_CAUGHT_UP_LAG_MAX`),
   - replay/offset integrity pass from `P12` replay-basis receipt (non-empty origin offset ranges + no validation errors).
6. Emit local + durable artifacts:
   - `m14e_rtdl_projection_snapshot.json`,
   - `m14e_msf_probe_receipt.json`,
   - `m14e_blocker_register.json`,
   - `m14e_execution_summary.json`.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B4` lag/offset/throughput regression.
3. `M14-B6` artifact publication/readback failure.

DoD:
- [x] single-app branch-separated evidence for `ieg_*` and `ofp_*`.
- [x] lag, offset continuity, and replay integrity pass.
- [x] runtime-path adjudication is explicit (canonical success or policy-allowed bounded fallback with reason).
- [x] local + durable `m14e_*` artifacts are readable.
- [x] execution summary is pass and advances gate to `M14.F_READY`.

### M14.F - Archive Connector Cutover
Goal:
1. Replace archive writer runtime path with managed connector-to-S3 and prove continuity.

Entry conditions:
1. `M14.E` is pass (`ADVANCE_TO_M14_F`, `M14.F_READY`).
2. Prior-lane blocker register is zero in local and durable run-control mirrors.
3. Archive connector handle set is pinned and non-`TO_PIN`:
   - `RUNTIME_WORKLOAD_ARCHIVE`
   - `ARCHIVE_CONNECTOR_MODE`
   - `ARCHIVE_CONNECTOR_FUNCTION_NAME`
   - `ARCHIVE_CONNECTOR_IAM_ROLE_NAME`
   - `ARCHIVE_CONNECTOR_SOURCE_CLUSTER_ARN`
   - `ARCHIVE_CONNECTOR_SOURCE_TOPIC`
   - `ARCHIVE_CONNECTOR_STARTING_POSITION`
   - `ARCHIVE_CONNECTOR_BATCH_SIZE`
   - `ARCHIVE_CONNECTOR_S3_PREFIX_PATTERN`
   - `ARCHIVE_CONNECTOR_RUN_SCOPE_PROOF_MODE`
   - `ARCHIVE_CONNECTOR_PROBE_EMIT_MODE`
   - `ARCHIVE_CONNECTOR_PROBE_ECS_CLUSTER`
   - `ARCHIVE_CONNECTOR_PROBE_TASK_DEFINITION`
4. IG edge contract remains pinned and readable for probe admission:
   - `IG_BASE_URL`, `IG_INGEST_PATH`, `IG_AUTH_HEADER_NAME`, `SSM_IG_API_KEY_PATH`.
5. Runtime/cost envelope for this lane is pinned before execution:
   - runtime target `<= 35 minutes`,
   - one delivery stream only (no fanout),
   - no long-lived non-active lanes started.

Execution:
1. Resolve handles and fail closed on any unresolved pin or runtime drift (`M14-B1`).
2. Materialize archive connector IAM role (Firehose assume role + bounded MSK/S3/log permissions).
3. Materialize or update managed delivery stream:
   - source: MSK topic `ARCHIVE_CONNECTOR_SOURCE_TOPIC`,
   - runtime: connector mode pinned by `ARCHIVE_CONNECTOR_MODE` (Lambda MSK trigger or ECS batch consumer),
   - sink: S3 prefix from `ARCHIVE_CONNECTOR_S3_PREFIX_PATTERN`,
   - run-scope continuity proven by object path + payload readback (`platform_run_id`, `event_id`) using `ARCHIVE_CONNECTOR_RUN_SCOPE_PROOF_MODE`,
   - connector runtime receipt is explicit and readable.
4. Emit bounded run-scoped IG probe events and capture admission results (attempted/admitted/failed).
   - for control-lane topic source, emit bounded probes via pinned ECS producer task mode.
5. Verify sink parity:
   - new archive objects appear under run-scoped prefix,
   - probe event ids are readable in newly delivered objects.
6. Verify continuity posture:
   - prior archive component proof exists (legacy baseline),
   - connector lane links admissions -> sink objects for same probe ids.
7. Write local artifacts and durable mirrors under `evidence/dev_full/run_control/<execution_id>/`.

Blockers:
1. `M14-B1` unresolved or drifted connector/stream handles.
2. `M14-B2` connector materialization failure.
3. `M14-B3` continuity drift.
4. `M14-B6` artifact publication/readback failure.

DoD:
- [x] offset continuity proven across cutover boundary.
- [x] archive object and sink parity proofs pass.
- [x] local + durable `m14f_*` artifacts are readable.
- [x] execution summary is pass and advances gate to `M14.G_READY`.

### M14.G - AL/Case/Label Placement Materialization
Goal:
1. Materialize AL, CaseTrigger, CM, LS on ECS/Fargate and preserve semantics.

Entry conditions:
1. `M14.F` is pass (`ADVANCE_TO_M14_G`, `M14.G_READY`) with blocker-free local and durable registers.
2. Placement handles are pinned and non-`TO_PIN`:
   - `RUNTIME_WORKLOAD_AL`
   - `RUNTIME_WORKLOAD_CASE_TRIGGER`
   - `RUNTIME_WORKLOAD_CM`
   - `RUNTIME_WORKLOAD_LS`
3. ECS probe substrate handles remain readable:
   - `ARCHIVE_CONNECTOR_PROBE_ECS_CLUSTER`
   - `ARCHIVE_CONNECTOR_PROBE_TASK_DEFINITION`
   - `ARCHIVE_CONNECTOR_PROBE_SUBNET_IDS`
   - `ARCHIVE_CONNECTOR_PROBE_SECURITY_GROUP_ID`.

Execution:
1. Resolve placement handles and fail closed on any drift from canonical placement targets.
2. Materialize ECS/Fargate task definitions for AL/CaseTrigger/CM/LS if absent.
3. Ensure per-lane CloudWatch log groups exist with bounded retention.
4. Run managed lane health tasks (`python -m ... --help`) for AL/CaseTrigger/CM/LS and require clean exits.
5. Verify semantic continuity by detecting common run-id intersections across component-proof artifacts:
   - `decision_lane/al_component_proof.json`
   - `case_labels/case_trigger_component_proof.json`
   - `case_labels/cm_component_proof.json`
   - `case_labels/ls_component_proof.json`.
6. Write local artifacts and durable mirrors under `evidence/dev_full/run_control/<execution_id>/`.

Blockers:
1. `M14-B2` runtime materialization failure.
2. `M14-B3` contract drift.

DoD:
- [x] side-effect/idempotency semantics remain stable.
- [x] case/label timelines and append semantics remain stable.

### M14.H - Non-Regression Pack on Repinned Runtime
Goal:
1. Re-run targeted non-regression closures on repinned lanes.

Entry conditions:
1. `M14.G` is pass (`ADVANCE_TO_M14_H`, `M14.H_READY`) with blocker-free local and durable registers.
2. Canonical regression anchors are readable from durable run-control:
   - `P5` rollup summary (`m6d_p5c_gate_rollup_*`),
   - `P8` rollup summary (`m7f_p8e_rollup_*`),
   - `P9` rollup summary (`m7k_p9e_rollup_*`),
   - `P10` rollup summary (`m7p_p10e_rollup_*`),
   - `P11` closure summary (`m8j_p11_closure_sync_*`),
   - `P12` closure summary (`m12j_closure_sync_*`).
3. Repin-lane closures are pass and readable:
   - `M14.C`, `M14.D`, `M14.E`, `M14.F`, `M14.G` execution summaries.

Execution:
1. Resolve and read latest durable anchor summaries for `P5/P8/P9/P10/P11/P12`.
2. Fail closed on any anchor with non-pass `overall_pass` or non-zero blocker count.
3. Validate continuity posture:
   - `P8/P9/P10/P12` platform run id continuity is unchanged across anchors.
4. Read repin-lane summaries (`M14.C..M14.G`) and require pass + blocker-free status.
5. Validate baseline non-regression artifact readability:
   - latest `m8g_p11_non_regression_*/non_regression_pack.json`,
   - canonical run non-regression surface under `evidence/runs/<platform_run_id>/obs/non_regression_pack.json`.
6. Emit deterministic matrix + verdict artifacts to local + durable run-control.

Blockers:
1. `M14-B3` semantic non-regression failure.
2. `M14-B6` artifact publication/readback failure.

DoD:
- [x] regression matrix pass for `P5/P8/P9/P10/P11/P12`.
- [x] no unresolved regression blocker.

### M14.I - Cost and Performance Re-Certification
Goal:
1. Close repin-window cost/performance posture with explicit receipt.

Entry conditions:
1. `M14.H` is pass (`ADVANCE_TO_M14_I`, `M14.I_READY`) with local + durable blocker count `0`.
2. Upstream repin lane summaries are readable and pass:
   - `M14.A` .. `M14.H`.
3. Cost/performance handles are pinned and non-placeholder:
   - `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD`
   - `DEV_FULL_BUDGET_ALERT_1_USD`
   - `DEV_FULL_BUDGET_ALERT_2_USD`
   - `DEV_FULL_BUDGET_ALERT_3_USD`
   - `BUDGET_CURRENCY`
   - `THROUGHPUT_CERT_MIN_SAMPLE_EVENTS`
   - `THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND`
   - `THROUGHPUT_CERT_MAX_ERROR_RATE_PCT`
   - `THROUGHPUT_CERT_MAX_RETRY_RATIO_PCT`
   - `RTDL_CAUGHT_UP_LAG_MAX`.

Execution:
1. Resolve and validate pinned cost/performance handles fail-closed.
2. Verify previous-lane closure:
   - local latest `m14h_blocker_register.json` has `blocker_count=0`,
   - durable latest `m14h_blocker_register.json` has `blocker_count=0`.
3. Validate upstream repin summary matrix (`M14.A..M14.H`) from durable run-control:
   - each summary is readable,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - expected gate progression is preserved.
4. Build performance scorecard from authoritative evidence:
   - EMR Serverless stream-sort runtime/usage from `M14.B` job run API readback,
   - throughput certification posture from `M7.K` cert snapshot,
   - RTDL lag posture from `M6.F` lag snapshot.
5. Build phase budget posture:
   - pull AWS MTD spend (`month_start..tomorrow`) from billing region,
   - compute utilization against monthly and alert thresholds,
   - fail closed when critical envelope is breached.
6. Publish artifacts locally + durably:
   - `m14i_performance_scorecard.json`
   - `m14i_phase_budget_envelope.json`
   - `m14i_phase_cost_performance_receipt.json`
   - `m14i_blocker_register.json`
   - `m14i_execution_summary.json`.

Blockers:
1. `M14-B4` performance regression.
2. `M14-B5` cost envelope breach.
3. `M14-B6` evidence publication/readback failure.

DoD:
- [x] performance scorecard pass against pinned envelopes (`M14.B` runtime + `M7.K` throughput + `M6.F` lag).
- [x] cost-to-outcome receipt committed and within envelope.
- [x] local + durable `m14i_*` artifacts are readable and blocker-free.

Runtime budget:
1. Target <= 15 minutes.

### M14.J - Final Repin Closure Sync
Goal:
1. Publish deterministic M14 verdict and rollback posture closure.

Entry conditions:
1. `M14.I` is pass (`ADVANCE_TO_M14_J`, `M14.J_READY`) with local + durable blocker count `0`.
2. Upstream repin summaries (`M14.A..M14.I`) are readable and pass (`overall_pass=true`, `blocker_count=0`).
3. Rollback-capability handles are pinned and non-placeholder:
   - `FLINK_RUNTIME_PATH_ALLOWED`
   - `FLINK_EKS_WSP_STREAM_REF`
   - `FLINK_EKS_SR_READY_REF`
   - `FLINK_EKS_RTDL_IEG_REF`
   - `FLINK_EKS_RTDL_OFP_REF`
   - `IG_BASE_URL_EKS_FALLBACK`
   - `ARCHIVE_CONNECTOR_FUNCTION_NAME`
   - `ARCHIVE_CONNECTOR_MODE`
   - `K8S_DEPLOY_AL`
   - `K8S_DEPLOY_CASE_TRIGGER`
   - `K8S_DEPLOY_CM`
   - `K8S_DEPLOY_LS`.

Execution:
1. Validate previous-lane continuity (`M14.I` blocker count local + durable == 0).
2. Validate full M14 upstream matrix (`M14.A..M14.I`) from durable run-control:
   - each summary readable, pass, and blocker-free.
3. Build rollback contract matrix for repinned lanes (`M14.B..M14.G`):
   - lane closure summary ref (current canonical run),
   - primary runtime posture handle,
   - fallback handle set,
   - rollback evidence refs (where applicable),
   - executable surface check:
     - script surfaces compile (`python -m py_compile`) where present,
     - managed workflow surfaces are present and dispatch-capable by contract (`workflow_dispatch`).
4. Fail closed on any missing/unreadable rollback contract or non-executable rollback surface (`M14-B7`).
5. Emit closure artifacts locally + durably:
   - `m14j_closure_sync_snapshot.json`,
   - `m14j_execution_summary.json`,
   - `m14_blocker_register.json`,
   - `m14_execution_summary.json`.
6. Final verdict:
   - `M14_COMPLETE_GREEN` only when blocker count is zero and rollback contract matrix is fully pass.

Blockers:
1. `M14-B6` evidence parity/readability failure.
2. `M14-B7` rollback path not executable.

DoD:
- [x] `m14_execution_summary.json` + `m14_blocker_register.json` parity pass.
- [x] rollback contract for each repinned lane is readable and executable.
- [x] verdict published: `M14_COMPLETE_GREEN`.

Runtime budget:
1. Target <= 15 minutes.

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
10. `m14j_closure_sync_snapshot.json`
11. `m14j_execution_summary.json`
12. `m14_execution_summary.json`
13. `m14_blocker_register.json`

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
- [x] M14.D
- [x] M14.E
- [x] M14.F
- [x] M14.G
- [x] M14.H
- [x] M14.I
- [x] M14.J

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

## 14) M14.D Closure Snapshot
1. Executed WSP runtime materialization on ECS/Fargate with fail-closed remediation to clear network/IAM/runtime bootstrap drift:
   - execution: `m14d_wsp_materialization_20260302T032223Z`,
   - verdict: `ADVANCE_TO_M14_E`, next gate: `M14.E_READY`,
   - blocker count: `0`.
2. Runtime parity and contract checks passed:
   - `WSP_RUNTIME = ECS_FARGATE_RUNTASK_EPHEMERAL` (pinned),
   - `WSP_TRIGGER_MODE = READY_EVENT_TRIGGERED` (pinned),
   - retry posture pinned and honored (`max_attempts=5`, `backoff_ms=500`, `stop_on_nonretryable=true`).
3. Historical note:
   - this closure snapshot reflects the pre-2026-03-06 WSP ECS materialization posture and is no longer the active authority after managed-WSP repin.
4. Run-scoped admission proof is non-zero and tied to lane run id:
   - run id: `platform_20260302T032223Z`,
   - table: `fraud-platform-dev-full-ig-idempotency`,
   - admissions: `admitted_count > 0` (summary shows `blocker_count=0`).
5. WSP task result proof:
   - `s3://fraud-platform-dev-full-object-store/oracle-store/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/m14d_runtime/m14d_wsp_materialization_20260302T032223Z/wsp_task_result.json`,
   - task returned `status=STREAMED`, `returncode=0`.
6. Local artifacts:
   - `runs/dev_substrate/dev_full/m14/m14d_wsp_materialization_20260302T032223Z/m14d_wsp_materialization_snapshot.json`,
   - `runs/dev_substrate/dev_full/m14/m14d_wsp_materialization_20260302T032223Z/m14d_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14d_wsp_materialization_20260302T032223Z/m14d_execution_summary.json`.
7. Durable run-control artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14d_wsp_materialization_20260302T032223Z/m14d_wsp_materialization_snapshot.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14d_wsp_materialization_20260302T032223Z/m14d_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14d_wsp_materialization_20260302T032223Z/m14d_execution_summary.json`.

## 15) M14.E Closure Snapshot
1. Executed RTDL projection materialization lane:
   - execution: `m14e_rtdl_projection_20260302T033143Z`,
   - verdict: `ADVANCE_TO_M14_F`, next gate: `M14.F_READY`,
   - blocker count: `0`.
2. Canonical probe outcome:
   - `kinesisanalyticsv2 create-application` for `fraud-platform-dev-full-rtdl-ieg-ofp-v0` remains externally blocked (`UnsupportedOperationException` account verification gate),
   - advisory recorded: `M14E-AD1`,
   - runtime adjudication explicitly applied under pinned policy: effective path `EKS_FLINK_OPERATOR` with canonical intent unchanged.
3. Branch-separated evidence pass:
   - metric namespace pin retained: `ieg_*,ofp_*`,
   - `P8.E` rollup ref confirms separate `IEG` and `OFP` proof surfaces:
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7f_p8e_rollup_20260225T214307Z/p8e_rtdl_gate_rollup_matrix.json`.
4. Continuity pass:
   - lag posture pass (`measured_lag=2`, threshold `10`) from:
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6f_p6b_streaming_active_20260225T175655Z/m6f_streaming_lag_posture.json`,
   - replay/offset integrity pass from:
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9c_p12_replay_basis_20260226T075941Z/m9c_replay_basis_receipt.json`.
5. Local artifacts:
   - `runs/dev_substrate/dev_full/m14/m14e_rtdl_projection_20260302T033143Z/m14e_rtdl_projection_snapshot.json`,
   - `runs/dev_substrate/dev_full/m14/m14e_rtdl_projection_20260302T033143Z/m14e_msf_probe_receipt.json`,
   - `runs/dev_substrate/dev_full/m14/m14e_rtdl_projection_20260302T033143Z/m14e_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14e_rtdl_projection_20260302T033143Z/m14e_execution_summary.json`.
6. Durable run-control artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14e_rtdl_projection_20260302T033143Z/m14e_rtdl_projection_snapshot.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14e_rtdl_projection_20260302T033143Z/m14e_msf_probe_receipt.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14e_rtdl_projection_20260302T033143Z/m14e_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14e_rtdl_projection_20260302T033143Z/m14e_execution_summary.json`.

## 16) M14.F Closure Snapshot
1. Final closure execution:
   - execution: `m14f_archive_connector_20260302T051741Z`,
   - summary: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M14_G`, `next_gate=M14.G_READY`.
2. Runtime connector posture:
   - canonical mode repinned to `ARCHIVE_CONNECTOR_MODE=ECS_MSK_BATCH_CONSUMER_TO_S3`,
   - probe emission remained managed ECS producer (`attempted=6`, `admitted=6`, exit `0`),
   - archive consumer ECS materialization exit `0`.
3. Sink parity closure:
   - new run-scoped archive objects written under `archive/{platform_run_id}/events/...`,
   - admitted probe ids fully present in object readback,
   - run-scope proof mode remained `object_path_plus_payload_readback`.
4. Local artifacts:
   - `runs/dev_substrate/dev_full/m14/m14f_archive_connector_20260302T051741Z/m14f_archive_connector_snapshot.json`,
   - `runs/dev_substrate/dev_full/m14/m14f_archive_connector_20260302T051741Z/m14f_connector_runtime_receipt.json`,
   - `runs/dev_substrate/dev_full/m14/m14f_archive_connector_20260302T051741Z/m14f_probe_admission_receipt.json`,
   - `runs/dev_substrate/dev_full/m14/m14f_archive_connector_20260302T051741Z/m14f_sink_parity_receipt.json`,
   - `runs/dev_substrate/dev_full/m14/m14f_archive_connector_20260302T051741Z/m14f_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14f_archive_connector_20260302T051741Z/m14f_execution_summary.json`.
5. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14f_archive_connector_20260302T051741Z/m14f_archive_connector_snapshot.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14f_archive_connector_20260302T051741Z/m14f_connector_runtime_receipt.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14f_archive_connector_20260302T051741Z/m14f_probe_admission_receipt.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14f_archive_connector_20260302T051741Z/m14f_sink_parity_receipt.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14f_archive_connector_20260302T051741Z/m14f_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14f_archive_connector_20260302T051741Z/m14f_execution_summary.json`.

## 17) M14.G Closure Snapshot
1. Final closure execution:
   - execution: `m14g_case_label_materialization_20260302T052538Z`,
   - summary: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M14_H`, `next_gate=M14.H_READY`.
2. Placement materialization:
   - registered ECS/Fargate task definitions:
     - `fraud-platform-dev-full-al:1`,
     - `fraud-platform-dev-full-case-trigger:1`,
     - `fraud-platform-dev-full-cm:1`,
     - `fraud-platform-dev-full-ls:1`.
   - managed help-run health checks passed for all four lanes.
3. Contract parity and semantic continuity:
   - runtime placement handles match canonical targets for AL/CaseTrigger/CM/LS,
   - historical semantic proofs detected with common run-id intersection across:
     - `decision_lane/al_component_proof.json`,
     - `case_labels/case_trigger_component_proof.json`,
     - `case_labels/cm_component_proof.json`,
     - `case_labels/ls_component_proof.json`.
4. Local artifacts:
   - `runs/dev_substrate/dev_full/m14/m14g_case_label_materialization_20260302T052538Z/m14g_case_label_materialization_snapshot.json`,
   - `runs/dev_substrate/dev_full/m14/m14g_case_label_materialization_20260302T052538Z/m14g_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14g_case_label_materialization_20260302T052538Z/m14g_execution_summary.json`.
5. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14g_case_label_materialization_20260302T052538Z/m14g_case_label_materialization_snapshot.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14g_case_label_materialization_20260302T052538Z/m14g_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14g_case_label_materialization_20260302T052538Z/m14g_execution_summary.json`.

## 18) M14.H Closure Snapshot
1. Final closure execution:
   - execution: `m14h_non_regression_20260302T053452Z`,
   - summary: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M14_I`, `next_gate=M14.I_READY`.
2. Regression anchor matrix pass (all green, blocker-free):
   - `P5`: `m6d_p5c_gate_rollup_20260225T041801Z/m6d_execution_summary.json`,
   - `P8`: `m7f_p8e_rollup_20260225T214307Z/p8e_execution_summary.json`,
   - `P9`: `m7k_p9e_rollup_20260226T023154Z/p9e_execution_summary.json`,
   - `P10`: `m7p_p10e_rollup_20260226T030607Z/p10e_execution_summary.json`,
   - `P11`: `m8j_p11_closure_sync_20260226T065141Z/m8j_execution_summary.json`,
   - `P12`: `m12j_closure_sync_20260227T184452Z/m12_execution_summary.json`.
3. Repin-lane continuity pass:
   - `M14.C`, `M14.D`, `M14.E`, `M14.F`, `M14.G` latest execution summaries all pass with `blocker_count=0`.
4. Baseline non-regression artifact readback pass:
   - latest `m8g` non-regression pack readable,
   - canonical `evidence/runs/platform_20260223T184232Z/obs/non_regression_pack.json` readable.
5. Local artifacts:
   - `runs/dev_substrate/dev_full/m14/m14h_non_regression_20260302T053452Z/m14h_non_regression_snapshot.json`,
   - `runs/dev_substrate/dev_full/m14/m14h_non_regression_20260302T053452Z/m14h_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14h_non_regression_20260302T053452Z/m14h_execution_summary.json`.
6. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14h_non_regression_20260302T053452Z/m14h_non_regression_snapshot.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14h_non_regression_20260302T053452Z/m14h_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14h_non_regression_20260302T053452Z/m14h_execution_summary.json`.
7. Revalidation rerun (operator verification pass):
   - execution: `m14h_non_regression_20260302T053657Z`,
   - summary: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M14_I`, `next_gate=M14.I_READY`,
   - local summary: `runs/dev_substrate/dev_full/m14/m14h_non_regression_20260302T053657Z/m14h_execution_summary.json`,
   - durable summary: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14h_non_regression_20260302T053657Z/m14h_execution_summary.json`.

## 19) M14.I Closure Snapshot
1. Final closure execution:
   - execution: `m14i_phase_cost_performance_20260302T054521Z`,
   - summary: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M14_J`, `next_gate=M14.J_READY`.
2. Previous-lane continuity pass:
   - local latest `m14h_blocker_register.json` blocker count `0`,
   - durable latest `m14h_blocker_register.json` blocker count `0`.
3. Upstream repin summary matrix (`M14.A..M14.H`) pass:
   - each summary readable,
   - each `overall_pass=true`,
   - each `blocker_count=0`,
   - expected gate progression preserved.
4. Performance scorecard pass:
   - `M14.B` EMR stream-sort: duration `345s` (budget `<= 7200s`), rows `1,183,458,470`, effective `3,430,314.405797 rows/s`, job state `SUCCESS`,
   - `M7.K` throughput cert: sample `11,878 >= 5,000`, observed `49.491666... eps >= 20`, error `0 <= 1.0`, retry `0 <= 5.0`,
   - `M6.F` lag posture: measured lag `2 <= 10`.
5. Cost posture pass:
   - AWS MTD `14.2552236516 USD`,
   - envelope `120/210/270` over monthly `300`,
   - utilization `4.7517%`,
   - status `GREEN`,
   - capture scope `aws_only_pre_m11_databricks_cost_deferred`.
6. Local artifacts:
   - `runs/dev_substrate/dev_full/m14/m14i_phase_cost_performance_20260302T054521Z/m14i_performance_scorecard.json`,
   - `runs/dev_substrate/dev_full/m14/m14i_phase_cost_performance_20260302T054521Z/m14i_phase_budget_envelope.json`,
   - `runs/dev_substrate/dev_full/m14/m14i_phase_cost_performance_20260302T054521Z/m14i_phase_cost_performance_receipt.json`,
   - `runs/dev_substrate/dev_full/m14/m14i_phase_cost_performance_20260302T054521Z/m14i_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14i_phase_cost_performance_20260302T054521Z/m14i_execution_summary.json`.
7. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14i_phase_cost_performance_20260302T054521Z/m14i_performance_scorecard.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14i_phase_cost_performance_20260302T054521Z/m14i_phase_budget_envelope.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14i_phase_cost_performance_20260302T054521Z/m14i_phase_cost_performance_receipt.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14i_phase_cost_performance_20260302T054521Z/m14i_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14i_phase_cost_performance_20260302T054521Z/m14i_execution_summary.json`.

## 20) M14.J Closure Snapshot
1. First execution failed closed:
   - execution: `m14j_closure_sync_20260302T055131Z`,
   - blocker: `M14-B6 rollback_evidence_unreadable:M14.D:ClientError`,
   - root cause: rollback evidence check targeted run-scoped `receipt_summary.json` for `platform_20260302T032223Z`, but M14.D rollback evidence is captured in run-control snapshot surface for that execution.
2. Remediation applied:
   - retargeted `M14.D` rollback evidence check to durable run-control artifact:
     - `evidence/dev_full/run_control/<m14d_execution_id>/m14d_wsp_materialization_snapshot.json`.
3. Final closure execution:
   - execution: `m14j_closure_sync_20260302T055205Z`,
   - `m14j` summary: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M14_COMPLETE`, `next_gate=M14_COMPLETE_READY`.
4. Final M14 verdict:
   - `m14_execution_summary.json` => `overall_pass=true`, `blocker_count=0`, `verdict=M14_COMPLETE_GREEN`, `next_gate=M15_READY`.
5. Rollback contract matrix:
   - repinned lanes `M14.B..M14.G` are all readable and executable (scripts compile and/or managed workflow rollback surfaces are dispatch-capable).
6. Local artifacts:
   - `runs/dev_substrate/dev_full/m14/m14j_closure_sync_20260302T055205Z/m14j_closure_sync_snapshot.json`,
   - `runs/dev_substrate/dev_full/m14/m14j_closure_sync_20260302T055205Z/m14j_execution_summary.json`,
   - `runs/dev_substrate/dev_full/m14/m14j_closure_sync_20260302T055205Z/m14_blocker_register.json`,
   - `runs/dev_substrate/dev_full/m14/m14j_closure_sync_20260302T055205Z/m14_execution_summary.json`.
7. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14j_closure_sync_20260302T055205Z/m14j_closure_sync_snapshot.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14j_closure_sync_20260302T055205Z/m14j_execution_summary.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14j_closure_sync_20260302T055205Z/m14_blocker_register.json`,
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m14j_closure_sync_20260302T055205Z/m14_execution_summary.json`.
