# Dev Substrate Deep Plan - M6 (P4-P7 Control + Ingress)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M6._
_Last updated: 2026-02-15_

## 0) Purpose
M6 closes the control+ingress chain on managed substrate by proving `P4..P7` in order: IG readiness and auth boundary, SR READY publication, WSP streaming activation, and IG ingest commit evidence with fail-closed ambiguity handling.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P4..P7` sections)
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M5.build_plan.md`
2. `runs/dev_substrate/m5/20260215T002310Z/m6_handoff_pack.json`
3. `runs/dev_substrate/m5/20260214T235117Z/stream_sort_summary.json`
4. `runs/dev_substrate/m5/20260215T002040Z/checker_pass.json`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M6
In scope:
1. `P4 INGEST_READY`:
   - IG ECS service readiness, health, auth boundary enforcement.
   - Kafka publish smoke + S3 receipts/quarantine write smoke.
2. `P5 READY_PUBLISHED`:
   - one-shot SR execution and READY control-message publication.
3. `P6 STREAMING_ACTIVE`:
   - one-shot WSP execution gated by READY and stream-view-first input posture.
4. `P7 INGEST_COMMITTED`:
   - IG ingest outcome evidence closure (receipts/quarantine/offset snapshots),
   - unresolved `PUBLISH_AMBIGUOUS` fail-closed gate.
5. M6 verdict and M7 handoff artifact publication.

Out of scope:
1. RTDL core/case-label closeout (`M7` / `P8..P10`).
2. Obs/Gov closeout (`M8` / `P11`).
3. Teardown (`M9`) and certification (`M10`).

## 3) M6 Deliverables
1. `M6.A` handle/authority closure snapshot.
2. `M6.B` IG readiness snapshot (health/auth checks).
3. `M6.C` `ingest/ig_ready.json` commit evidence (+ smoke snapshot).
4. `M6.D` SR READY publication snapshot.
5. `M6.E` WSP launch/READY-consumption snapshot.
6. `M6.F` WSP execution summary snapshot.
7. `M6.G` ingest commit verification snapshot (`P7`).
8. `M6.H` deterministic verdict snapshot (`ADVANCE_TO_M7` or `HOLD_M6`).
9. `M6.I` `m7_handoff_pack.json`.

## 4) Execution Gate for This Phase
Current posture:
1. M6 is active for deep planning and sequential execution preparation.

Execution block:
1. No M7 execution is allowed before M6 verdict is `ADVANCE_TO_M7`.
2. No WSP execution is allowed before SR READY publication is proven.
3. No progression is allowed with unresolved `PUBLISH_AMBIGUOUS` outcomes.

## 4.1) Anti-Cram Law (Binding for M6)
1. M6 is not execution-ready unless these lanes are explicit:
   - authority/handles
   - identity/IAM + secrets
   - network + runtime reachability
   - control-bus/READY semantics
   - ingress boundary/auth semantics
   - evidence publication and rollback/rerun posture
2. Sub-phase count is not fixed; this file expands until closure-grade coverage is achieved.
3. Any newly discovered lane/hole blocks progression and must be added before execution continues.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting sub-phases | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + handles closure | M6.A | M6.H | zero unresolved required `P4..P7` handles |
| IG readiness/auth boundary | M6.B | M6.C | health+auth pass snapshot |
| IG publish/storage smoke | M6.C | M6.G | `ingest/ig_ready.json` with Kafka+S3 smoke pass |
| SR READY gate | M6.D | M6.E | READY publication receipt for active run |
| WSP launch + streaming evidence | M6.E / M6.F | M6.G | WSP summary with READY-consumption proof |
| Ingest commit closure | M6.G | M6.H | receipt/offset/quarantine summaries coherent |
| Ambiguity fail-closed gate | M6.G | M6.H | unresolved `PUBLISH_AMBIGUOUS == 0` |
| Verdict + M7 handoff | M6.H / M6.I | - | `ADVANCE_TO_M7` and durable `m7_handoff_pack.json` |

## 5) Work Breakdown (Deep)

## M6 Decision Pins (Closed Before Execution)
1. Managed-runtime law:
   - IG/SR/WSP execute on ECS only; no laptop runtime compute.
2. Writer-boundary law:
   - IG ingest requires auth and fails closed when missing/invalid.
3. READY law:
   - WSP must not stream without SR READY for the active `platform_run_id`.
4. Stream-view-first law:
   - WSP reads only M5 stream_view outputs (no raw oracle input lane).
5. Deterministic-idempotent law:
   - WSP retries retain deterministic `event_id`; IG dedupe semantics remain canonical.
6. Publisher ownership law:
   - WSP sends to IG; IG alone publishes admitted events to Kafka topics.
7. Append-only evidence law:
   - ingest receipts/quarantine evidence remain append-only and durable.
8. Ambiguity gate law:
   - unresolved `PUBLISH_AMBIGUOUS` is a hard blocker for M6 closure.
9. Fail-closed progression law:
   - any blocker in `M6.A..M6.G` yields `HOLD_M6`.

### M6.A Authority + Handle Closure (`P4..P7`)
Goal:
1. Close all required M6 handles before runtime actions.

Entry conditions:
1. M5 handoff artifact exists and indicates `m5_verdict=ADVANCE_TO_M6`.
2. M5 terminal closure artifacts are readable:
   - `stream_sort_summary.json`
   - `checker_pass.json`
   - `m5_h_verdict_snapshot.json`
   - `m6_handoff_pack.json`.

Required inputs:
1. Authority:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P4..P7`)
   - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`.
2. Source artifacts:
   - local: `runs/dev_substrate/m5/20260215T002310Z/m6_handoff_pack.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T235117Z/m6_handoff_pack.json`
   - local: `runs/dev_substrate/m5/20260214T235117Z/stream_sort_summary.json`
   - local: `runs/dev_substrate/m5/20260215T002040Z/checker_pass.json`.
3. Handle groups to close:
   - IG service/auth/endpoint:
     - `SVC_IG`
     - `IG_BASE_URL`
     - `IG_LISTEN_ADDR`
     - `IG_PORT`
     - `IG_INGEST_PATH`
     - `IG_HEALTHCHECK_PATH`
     - `IG_AUTH_MODE`
     - `IG_AUTH_HEADER_NAME`
     - `SSM_IG_API_KEY_PATH`.
   - SR/WSP execution and network:
     - `TD_SR`
     - `TD_WSP`
     - `ROLE_SR_TASK`
     - `ROLE_WSP_TASK`
     - `ECS_CLUSTER_NAME`
     - `SUBNET_IDS_PUBLIC`
     - `SECURITY_GROUP_ID_APP`.
   - Kafka/control/topic surface:
     - `FP_BUS_CONTROL_V1`
     - `FP_BUS_TRAFFIC_FRAUD_V1`
     - `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1`
     - `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1`
     - `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1`
     - `SSM_CONFLUENT_BOOTSTRAP_PATH`
     - `SSM_CONFLUENT_API_KEY_PATH`
     - `SSM_CONFLUENT_API_SECRET_PATH`.
   - WSP runtime knob surface:
     - `READY_MESSAGE_FILTER`
     - `WSP_MAX_INFLIGHT`
     - `WSP_RETRY_MAX_ATTEMPTS`
     - `WSP_RETRY_BACKOFF_MS`
     - `WSP_STOP_ON_NONRETRYABLE`.
   - Evidence + ingest output paths:
     - `S3_EVIDENCE_BUCKET`
     - `S3_EVIDENCE_RUN_ROOT_PATTERN`
     - `S3_QUARANTINE_BUCKET`
     - `S3_QUARANTINE_RUN_PREFIX_PATTERN`
     - `RECEIPT_SUMMARY_PATH_PATTERN`
     - `QUARANTINE_INDEX_PATH_PATTERN`.

Tasks:
1. Validate M5->M6 carry-forward invariants:
   - `platform_run_id` is consistent across M5 artifacts and handoff.
   - `m5_verdict=ADVANCE_TO_M6`.
   - no unresolved M5 blockers remain.
2. Build a deterministic handle-closure matrix with one row per required handle:
   - fields:
     - `handle_key`
     - `lane` (`P4|P5|P6|P7`)
     - `value_present`
     - `source_kind` (`registry_literal|terraform_output|ssm_path|derived_pattern`)
     - `secret_class` (`secret|non_secret`)
     - `placeholder_detected`
     - `wildcard_detected`
     - `materialization_probe_pass`.
3. Execute materialization probes (without exposing secret values):
   - ECS service/task-definition/cluster handles:
     - resolve by describe/list API checks.
   - SSM path handles:
     - resolve by parameter metadata existence checks.
   - Kafka topic handles:
     - resolve by topic catalog/managed substrate evidence checks.
   - pattern/path handles:
     - verify tokenized forms are run-scoped and non-ambiguous.
4. Enforce fail-closed closure rules:
   - no unresolved required handles,
   - no placeholders (`<PIN_...>`) or wildcard aliases,
   - critical policy pins must match expected posture:
     - `IG_AUTH_MODE=api_key`
     - `WSP_STOP_ON_NONRETRYABLE=true`.
5. Emit `m6_a_handle_closure_snapshot.json` with minimum fields:
   - `m6_execution_id`
   - `platform_run_id`
   - `source_m5_handoff_local`
   - `source_m5_handoff_uri`
   - `required_handle_keys`
   - `resolved_handle_count`
   - `unresolved_handle_count`
   - `unresolved_handle_keys`
   - `policy_pin_mismatches`
   - `placeholder_handle_keys`
   - `wildcard_handle_keys`
   - `probe_failures`
   - `blockers`
   - `overall_pass`.
6. Publish artifacts:
   - local: `runs/dev_substrate/m6/<timestamp>/m6_a_handle_closure_snapshot.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/run_control/<m6_execution_id>/m6_a_handle_closure_snapshot.json`.
7. Stop progression if `overall_pass=false`.

DoD:
- [ ] M5->M6 carry-forward invariants are verified and recorded.
- [ ] Full required-handle closure matrix is complete for `P4..P7`.
- [ ] Placeholder/wildcard handle usage is absent in closure result.
- [ ] Critical policy pins (`IG_AUTH_MODE`, `WSP_STOP_ON_NONRETRYABLE`) are validated.
- [ ] `m6_a_handle_closure_snapshot.json` exists locally and durably.

Blockers:
1. `M6A-B1`: M5 handoff invalid/unreadable or run-id mismatch.
2. `M6A-B2`: required `P4..P7` handles unresolved.
3. `M6A-B3`: placeholder/wildcard handle detected in required closure set.
4. `M6A-B4`: materialization probe failure for required handle(s).
5. `M6A-B5`: critical policy pin mismatch (`IG_AUTH_MODE` / `WSP_STOP_ON_NONRETRYABLE`).
6. `M6A-B6`: M6.A snapshot write/upload failure.

Execution status (2026-02-15):
1. Executed fail-closed using M5 handoff anchor and published durable evidence:
   - local: `runs/dev_substrate/m6/20260215T032545Z/m6_a_handle_closure_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T032545Z/m6_a_handle_closure_snapshot.json`
2. Result:
   - `overall_pass=true`
   - blocker set: empty
   - `resolved_handle_count=35/35`
3. Materialization outcome:
   - `TD_SR` and `TD_WSP` task definitions now materialized and probe PASS.
4. Policy pins validated in this execution:
   - `IG_AUTH_MODE=api_key`
   - `WSP_STOP_ON_NONRETRYABLE=true`
5. Historical note:
   - initial run `m6_20260215T022734Z` was superseded by corrected parsing in `m6_20260215T022859Z`,
   - then superseded by handle-pin rerun `m6_20260215T031058Z`,
   - final authoritative PASS snapshot is `m6_20260215T032545Z`.

### M6.B P4 IG Readiness + Auth Boundary
Goal:
1. Prove IG service is healthy and writer boundary auth is enforced.

Entry conditions:
1. `M6.A` PASS.

Tasks:
1. Confirm IG service task is stable/running.
2. Execute IG health probe on `IG_HEALTHCHECK_PATH`.
3. Execute auth probes on `IG_INGEST_PATH`:
   - unauthenticated request fails closed,
   - authenticated minimal request is accepted.
4. Emit `m6_b_ig_readiness_snapshot.json`.

DoD:
- [x] IG service healthy and stable.
- [x] Auth boundary fail/pass probes meet expected outcomes.
- [x] M6.B snapshot published locally and durably.

Blockers:
1. `M6B-B1`: IG service unhealthy or crashlooping.
2. `M6B-B2`: auth boundary behavior invalid.
3. `M6B-B3`: M6.B snapshot write/upload failure.

Execution status (2026-02-15):
1. Initial run failed closed:
   - local: `runs/dev_substrate/m6/20260215T033201Z/m6_b_ig_readiness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T033201Z/m6_b_ig_readiness_snapshot.json`
   - result: `overall_pass=false` (`M6B-B2`).
2. Closure rerun passed:
   - local: `runs/dev_substrate/m6/20260215T040527Z/m6_b_ig_readiness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T040527Z/m6_b_ig_readiness_snapshot.json`
   - result: `overall_pass=true`, blocker set empty.
3. Proven closure facts:
   - IG service stable on ECS (`desired=1`, `running=1`, `pending=0`).
   - task definition is non-placeholder and exposes port mapping on `8080`.
   - app SG ingress exists for probe path execution.
   - IG API key in SSM is non-placeholder.
   - probe outcomes:
     - `/v1/ops/health` authenticated: `200`,
     - `/v1/ingest/push` unauthenticated: `401`,
     - `/v1/ingest/push` authenticated: `200`.

### M6.C P4 Kafka/S3 Smoke + `ig_ready.json`
Goal:
1. Prove IG can publish to Kafka and write durable ingest evidence.

Entry conditions:
1. `M6.B` PASS.
2. Decision-completeness gate is closed:
   - IG runtime is configured for managed bus + durable object-store posture for dev substrate.
   - no `file` bus / local `runs` storage shim remains in the active IG runtime command/profile.

Tasks:
1. M6.C.1 runtime posture preflight:
   - snapshot active IG task definition command/env and confirm no local shim mode (`event_bus_kind=file`, local `runs` object-store root).
   - confirm required handles for this lane are resolved.
2. M6.C.2 smoke envelope contract:
   - pin one minimal authenticated ingest payload based on existing contract event type.
   - pin one deterministic expected publish target topic for offset verification.
3. M6.C.3 ingestion smoke execution:
   - send authenticated smoke payload through IG writer boundary.
   - capture response status/body + receipt reference.
4. M6.C.4 Kafka publish verification:
   - record topic/partition/offset before and after smoke event.
   - assert offset advancement in run scope.
5. M6.C.5 durable evidence verification:
   - verify receipt/quarantine object write under run-scoped durable prefix.
   - publish `evidence/runs/<platform_run_id>/ingest/ig_ready.json`.
6. M6.C.6 snapshot publication:
   - emit `m6_c_ingest_ready_snapshot.json` local + durable under run-control prefix.

DoD:
- [x] Runtime posture preflight confirms managed bus + durable object-store mode (no local shim).
- [x] Kafka publish smoke evidence captured for IG path with offset advancement.
- [x] Durable receipt/quarantine write smoke evidence captured.
- [x] `ingest/ig_ready.json` exists locally and durably.
- [x] `m6_c_ingest_ready_snapshot.json` exists locally and durably with `overall_pass=true`.

Blockers:
1. `M6C-B1`: Kafka smoke publish/read verification failed.
2. `M6C-B2`: S3 write smoke failed.
3. `M6C-B3`: `ig_ready.json` write/upload failure.
4. `M6C-B4`: runtime posture drift (`file` bus and/or local storage shim) blocks managed Kafka/S3 proof.
5. `M6C-B5`: topic-offset verification surface unavailable or non-deterministic for selected smoke topic.

Initial execution hold (historical, now closed):
1. `M6C-B4` was opened based on latest M6.B PASS snapshot (`m6_20260215T040527Z`):
   - active IG command still uses planning shim that mutates runtime profile to `event_bus_kind=file` and local `runs` object-store root.
2. Closure requirement before M6.C execution:
   - rematerialize IG runtime command/profile to managed bus + durable object-store posture for dev substrate,
   - rerun M6.B-style runtime-surface confirmation,
   - then execute M6.C smoke/commit lane.

Execution status (2026-02-15):
1. Executed fail-closed M6.C preflight snapshot (no false smoke claim while `M6C-B4` is open):
   - local: `runs/dev_substrate/m6/20260215T071807Z/m6_c_ingest_ready_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T071807Z/m6_c_ingest_ready_snapshot.json`
2. Result:
   - `overall_pass=false`
   - blocker set: `M6C-B4`
3. Runtime preflight findings in authoritative snapshot:
   - `uses_local_parity_profile=true`
   - `forces_file_bus=true`
   - `forces_local_runs_store=true`
4. Because runtime posture is not yet managed-bus/durable-store conformant, M6.C smoke steps were intentionally not executed:
   - no Kafka publish smoke,
   - no topic offset verification,
   - no `ingest/ig_ready.json` publication claim.
5. Rematerialization and closure reruns:
   - IG runtime rematerialized from temporary local file-bus shim to managed-bus + durable-store posture.
   - Intermediate fail-closed retries (kept as history):
     - `runs/dev_substrate/m6/20260215T082355Z/m6_c_ingest_ready_snapshot.json` (`M6C-B1`, service transition window)
     - `runs/dev_substrate/m6/20260215T082520Z/m6_c_ingest_ready_snapshot.json` (`M6C-B1`, envelope invalid)
     - `runs/dev_substrate/m6/20260215T083016Z/m6_c_ingest_ready_snapshot.json` (`M6C-B5`, readback method)
6. Authoritative closure snapshot:
   - local: `runs/dev_substrate/m6/20260215T083126Z/m6_c_ingest_ready_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T083126Z/m6_c_ingest_ready_snapshot.json`
   - run-scoped readiness artifact:
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/ingest/ig_ready.json`
   - result: `overall_pass=true`, blocker set empty.
7. Implementation note for this closure run:
   - publish/read smoke is proven on the active managed stream adapter (`kinesis_sequence` evidence in `eb_ref`),
   - no local file-bus or local-runs object-store shim remains in active IG runtime command.

### M6.D P5 SR Task + READY Publication
Goal:
1. Execute SR gate task and publish READY evidence.

Entry conditions:
1. `M6.C` PASS.
2. Latest authoritative M6.C snapshot is readable:
   - local: `runs/dev_substrate/m6/20260215T124328Z/m6_c_ingest_ready_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T124328Z/m6_c_ingest_ready_snapshot.json`
3. Pinned handles from `M6.A` remain resolvable:
   - `ECS_CLUSTER_NAME`,
   - `TD_SR`,
   - `ROLE_SR_TASK`,
   - `PLATFORM_RUN_ID`,
   - control-bus bootstrap/topic handles.
4. Active IG readiness artifact is present:
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/ingest/ig_ready.json`.

Tasks:
1. M6.D.1 preflight snapshot:
   - resolve all required handles,
   - assert run scope identity (`platform_run_id`),
   - assert `M6.C` source snapshot `overall_pass=true`.
2. M6.D.2 SR launch:
   - run one-shot `TD_SR` in `ECS_CLUSTER_NAME` with active run scope,
   - capture task ARN, launch timestamp, and task-definition revision.
3. M6.D.3 SR completion gate:
   - wait for terminal task state,
   - assert container exit code `0`,
   - capture stop reason and completion timestamp.
4. M6.D.4 SR PASS evidence gate:
   - verify run-scoped SR pass artifact exists under `evidence/runs/<platform_run_id>/sr/`,
   - verify payload indicates PASS semantics (not merely file presence).
5. M6.D.5 READY publication gate:
   - verify READY publication receipt exists and references active `platform_run_id`,
   - verify control-bus topic/offset metadata exists and is non-empty.
6. M6.D.6 snapshot publication:
   - emit local snapshot `m6_d_sr_ready_snapshot.json`,
   - upload durable snapshot under:
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m6_execution_id>/m6_d_sr_ready_snapshot.json`.
7. M6.D.7 fail-closed verdict:
   - set `overall_pass=true` only when all gates above pass,
   - otherwise publish blocker set and keep `overall_pass=false`.

DoD:
- [x] Required handles are resolvable and run-scoped preflight passes.
- [x] SR task exits success with captured run-scoped task evidence.
- [x] SR PASS artifact exists and validates pass semantics.
- [x] READY publication receipt exists and references active run.
- [x] M6.D snapshot is published locally and durably with `overall_pass=true` for closure.

Blockers:
1. `M6D-B1`: preflight/handle closure failure.
2. `M6D-B2`: SR launch or terminal completion failure.
3. `M6D-B3`: SR PASS artifact missing/invalid.
4. `M6D-B4`: READY publication missing or run-scope mismatch.
5. `M6D-B5`: M6.D snapshot write/upload failure.

Snapshot contract (`m6_d_sr_ready_snapshot.json`):
1. `phase`, `captured_at_utc`, `m6_execution_id`, `platform_run_id`.
2. `input_m6c_snapshot` with source path/URI and source `overall_pass`.
3. `sr_task` block:
   - `cluster`, `task_definition`, `task_arn`, `started_at_utc`, `stopped_at_utc`,
   - `last_status`, `exit_code`, `stop_reason`.
4. `sr_pass_evidence` block:
   - `artifact_uri`,
   - `exists`,
   - `pass_semantics_valid`.
5. `ready_publication` block:
   - `receipt_uri`,
   - `exists`,
   - `platform_run_id_match`,
   - `topic`,
   - `offset`.
6. `blockers` and `overall_pass`.

Execution status (2026-02-15):
1. Initial execution attempts failed closed and were retained as evidence:
   - `runs/dev_substrate/m6/20260215T134714Z/m6_d_sr_ready_snapshot.json` (`M6D-B2`)
   - `runs/dev_substrate/m6/20260215T134946Z/m6_d_sr_ready_snapshot.json` (`M6D-B2`)
   - `runs/dev_substrate/m6/20260215T135205Z/m6_d_sr_ready_snapshot.json` (`M6D-B2`)
   - `runs/dev_substrate/m6/20260215T135601Z/m6_d_sr_ready_snapshot.json` (`M6D-B2`)
   - `runs/dev_substrate/m6/20260215T140337Z/m6_d_sr_ready_snapshot.json` (`M6D-B3`)
   - `runs/dev_substrate/m6/20260215T140741Z/m6_d_sr_ready_snapshot.json` (`M6D-B3`, `M6D-B4`)
2. Closure run (authoritative):
   - local: `runs/dev_substrate/m6/20260215T144233Z/m6_d_sr_ready_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T144233Z/m6_d_sr_ready_snapshot.json`
   - result: `overall_pass=true`, blocker set empty.
3. Proven closure facts:
   - SR run status is `READY` for run `78d859d39f4232fc510463fb868bc6e1`,
   - READY receipt exists at `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/ready_signal/78d859d39f4232fc510463fb868bc6e1.json`,
   - control-bus READY publication is verified on stream `fraud-platform-dev-min-ig-bus-v0` with sequence `49671822697342044645261017794300307957859908788827455490`.
4. Execution note (explicit, non-hidden):
    - This closure run is historically valid, but its output-set narrowness is now **superseded** (see follow-up closure below).
    - This closure run used temporary task-scoped execution shims:
      - interface-pack layer-1 schema reference stub materialization,
      - lease keepalive loop for long evidence-reuse windows.

Follow-up closure (authoritative for 4-output Oracle Store posture; 2026-02-15):
1. Purpose: confirm SR (M6.D) is not implicitly narrowed to `s3_event_stream_with_fraud_6B`, and prove READY can be published
   with the full 4-output Oracle `stream_view` surface now present under canonical Oracle Store root.
2. Canonical Oracle Store root (engine-run-scoped; no coupling to platform_run_id):
   - `s3://fraud-platform-dev-min-object-store/oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/`
   - `stream_view_root`: `.../stream_view/ts_utc/`
3. Remediation required for deterministic re-run (fail-closed):
   - purged stale SR instance receipts that pinned legacy `oracle/platform_...` locator paths:
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/instance_receipts/`
   - kept SR lease alive during long S3 scans (task-scoped keepalive shim) to avoid `LEASE_LOST`.
   - materialized minimal missing interface-pack schema ref (`layer-1` `schemas.layer1.yaml`) as task-scoped shim.
  4. Result (PASS):
    - SR run `READY`: `run_id=17dacbdc997e6765bcd242f7cb3b6c37`
   - READY signal (durable):
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/ready_signal/17dacbdc997e6765bcd242f7cb3b6c37.json`
   - `oracle_pack_ref.stream_view_output_refs` includes all 4:
     - `arrival_events_5B`
     - `s1_arrival_entities_6B`
     - `s3_event_stream_with_fraud_6B`
     - `s3_flow_anchor_with_fraud_6B`
   - SR facts view (durable):
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/run_facts_view/17dacbdc997e6765bcd242f7cb3b6c37.json`
    - SR instance receipts re-materialized under canonical locator paths (durable):
      - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/instance_receipts/`

Proper closure (published image; no task-scoped shims; 2026-02-15):
1. Purpose: close M6.D under the same posture we will use going forward in dev_min:
   - immutable image published via authoritative CI lane,
   - ECS task definitions updated to reference immutable digest,
   - SR rerun proves READY with the full 4-output Oracle Store posture without any task-scoped shims.
2. Authoritative packaging proof:
   - workflow: `dev-min-m1-packaging` (`.github/workflows/dev_min_m1_packaging.yml`)
   - ref: `migrate-dev`
   - git sha: `0f75e2f28913eb26db2d0079f9a692c127f9d5e8`
   - published digest: `sha256:5550d39731e762bd4211fcae0d55edb72059bef5d3a1c7a3bdbab599064b89c3`
3. Task-definition roll-forward proof (Terraform apply; targeted to SR/WSP only):
   - `TD_SR` revision advanced to `fraud-platform-dev-min-sr:2` using the published digest above.
   - `TD_WSP` revision advanced to `fraud-platform-dev-min-wsp:2` using the published digest above.
4. SR rerun proof (ECS one-shot task):
   - task arn: `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/bbda2a70bab94568ba8338f607c18f3a`
   - task definition: `arn:aws:ecs:eu-west-2:230372904534:task-definition/fraud-platform-dev-min-sr:2`
   - exit code: `0`
   - runtime (observed): ~23 seconds (fast digest path avoids hashing every parquet object over S3)
5. READY truth (unchanged and still authoritative):
   - READY signal:
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/ready_signal/17dacbdc997e6765bcd242f7cb3b6c37.json`
   - `oracle_pack_ref.stream_view_output_refs` contains the full 4-output surface under canonical Oracle Store root:
     - `arrival_events_5B`
     - `s1_arrival_entities_6B`
     - `s3_event_stream_with_fraud_6B`
     - `s3_flow_anchor_with_fraud_6B`
6. Operator re-run command surface (deterministic):
   - run SR task: `aws ecs run-task ... --task-definition fraud-platform-dev-min-sr:2 ...`
   - wait: `aws ecs wait tasks-stopped ...`
   - verify READY: list latest under `evidence/runs/<platform_run_id>/sr/ready_signal/` and assert the 4 output refs map is complete.

### M6.E P6 WSP Launch Contract + READY Consumption
Goal:
1. Validate WSP launch inputs and prove READY is consumed for the active run scope.
2. Ensure WSP cannot accidentally stream an out-of-scope/stale READY message (control-bus replay hazard).

Entry conditions:
1. `M6.D` PASS.
2. Authoritative READY signal exists (run-scoped durable):
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/ready_signal/17dacbdc997e6765bcd242f7cb3b6c37.json`
3. `TD_WSP` is not a placeholder task definition.
   - Fail-closed if `aws ecs describe-task-definition ...` shows command `echo wsp_task_definition_materialized && exit 0`.
4. WSP can reach IG ingress from inside the ECS network:
    - `IG_INGEST_URL` MUST be resolvable/reachable from the WSP task.
    - `IG_INGEST_URL` MUST be the base URL (`http(s)://<host>:<port>`). WSP appends `/v1/ingest/push` internally.
    - Note: `IG_BASE_URL = "http://fraud-platform-dev-min-ig:8080"` is only valid if a concrete service discovery lane exists (ECS Service Connect, Cloud Map, or LB DNS).
5. WSP run scope is pinned (deterministic READY selection):
   - `PLATFORM_RUN_ID` MUST be set to `platform_20260213T214223Z` for the task.
   - Rationale: the Kinesis control-bus reader starts from `TRIM_HORIZON`; without run scope pinning, stale READY messages can be consumed first.

Tasks:
1. M6.E.1 Preflight (fail-closed):
   - assert the authoritative READY signal exists and is readable,
   - assert the READY payload references the canonical Oracle Store stream_view roots (4-output surface),
   - assert IG is reachable from the VPC lane selected for `IG_INGEST_URL` (service discovery/LB decision must be implemented before execution).
2. M6.E.2 WSP launch contract closure (fail-closed):
    - `TD_WSP` must run the WSP READY consumer (not a placeholder):
      - required command shape (canonical):
        - `python -m fraud_detection.world_streamer_producer.ready_consumer --profile <WSP_PROFILE> --once --max-messages 200`
    - required env for deterministic behavior (minimum):
      - `PLATFORM_RUN_ID=platform_20260213T214223Z` (deterministic READY scope filter),
      - `IG_INGEST_URL=<reachable base URL (scheme://host:port)>` (WSP → IG boundary; WSP appends `/v1/ingest/push`),
      - `IG_SERVICE_TOKEN` or equivalent secret env referenced by the chosen profile (MUST be injected from SSM; never hardcoded),
      - `CONTROL_BUS_STREAM=<control bus stream name>` and `CONTROL_BUS_REGION=eu-west-2`,
      - `ORACLE_ROOT`, `ORACLE_ENGINE_RUN_ROOT`, `ORACLE_SCENARIO_ID`, `ORACLE_STREAM_VIEW_ROOT`,
      - `OBJECT_STORE_REGION=eu-west-2`,
      - `WSP_CHECKPOINT_DSN` (recommended: Postgres; file backend is acceptable only for smoke, not for deterministic dev_min reruns).
   - required WSP knobs pinned for v0 validation:
     - `WSP_MAX_EVENTS_PER_OUTPUT=200` (bounded validation; note this is per-output and yields up to 800 total across 4 outputs),
     - `WSP_READY_REQUIRED_PACKS=""` (must be empty in ECS; avoids Run/Operate local FS dependency),
     - `WSP_STOP_ON_NONRETRYABLE=true` (already pinned as a critical policy pin in M6.A).
3. M6.E.3 Execute WSP one-shot task:
   - run one-shot `TD_WSP` in `ECS_CLUSTER_NAME` with the pinned env/secret posture above,
   - capture task ARN, launch timestamp, and task-definition revision.
4. M6.E.4 Terminal gate:
   - wait for terminal task state,
   - assert container exit code `0`,
   - capture stop reason and completion timestamp.
5. M6.E.5 READY-consumption proof gate (run-scoped, durable):
   - verify at least one WSP ready-record exists under:
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/wsp/ready_runs/*.jsonl`
   - verify the record contains a terminal status for the active run:
     - `status in {"STREAMED", "SKIPPED_DUPLICATE"}` and `run_id == "17dacbdc997e6765bcd242f7cb3b6c37"`
   - (optional, but recommended): CloudWatch log snippet contains:
     - `WSP READY poll processed=...` and `WSP stream start run_id=17dac...`
6. M6.E.6 Emit snapshot:
   - emit local snapshot `m6_e_wsp_launch_snapshot.json`,
   - upload durable snapshot under:
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m6_execution_id>/m6_e_wsp_launch_snapshot.json`.

DoD:
- [ ] WSP launch contract is complete, deterministic, and run-scoped (`PLATFORM_RUN_ID` pinned).
- [ ] WSP READY-consumption proof exists durably for the authoritative READY (`run_id=17dac...`).
- [ ] M6.E snapshot published locally and durably with `overall_pass=true`.

Execution status (2026-02-15):
1. Corrected WSP → IG base URL contract and executed one-shot WSP successfully.
2. WSP task:
   - `TD_WSP=fraud-platform-dev-min-wsp:6`
   - task ARN: `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/76b6851b47694328a5c6f69c64783820`
   - exit code: `0`
   - `IG_INGEST_URL=http://10.42.0.159:8080` (private IP base URL; WSP appends `/v1/ingest/push`)
3. READY-consumption proof (run-scoped, durable):
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/wsp/ready_runs/5273f3c8bcbbcea65875d31ccfe726759456ec45b87e484576a489fbf2fa83ee.jsonl`
   - terminal record: `status=STREAMED`, `emitted=800`, `run_id=17dacbdc997e6765bcd242f7cb3b6c37`
4. Snapshot published:
   - local: `runs/dev_substrate/m6/20260215T230419Z/m6_e_wsp_launch_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T230419Z/m6_e_wsp_launch_snapshot.json`
5. Historical note:
   - earlier attempt used `IG_INGEST_URL` including `/v1/ingest/push`, causing `POST /v1/ingest/push/v1/ingest/push` and `404` (captured in IG logs as `IG_PUSH_REJECTED`); corrected by using base URL only.

Blockers:
1. `M6E-B1`: WSP launch contract unresolved (task definition still placeholder, missing env/secret pins, or IG endpoint unreachable).
2. `M6E-B2`: WSP did not consume READY for the active run scope (no `wsp/ready_runs/*.jsonl` record for `run_id=17dac...`).
3. `M6E-B3`: M6.E snapshot write/upload failure.

Snapshot contract (`m6_e_wsp_launch_snapshot.json`):
1. `phase`, `captured_at_utc`, `m6_execution_id`, `platform_run_id`.
2. `inputs`:
   - `sr_ready_signal_uri` (must be the authoritative `17dac...` READY),
   - `expected_sr_run_id` (must equal `17dacbdc997e6765bcd242f7cb3b6c37` for this closure set),
   - `ig_ingest_url` (non-secret),
   - `control_bus_stream`, `control_bus_topic`.
3. `wsp_task`:
   - `cluster`, `task_definition`, `task_arn`, `started_at_utc`, `stopped_at_utc`,
   - `last_status`, `exit_code`, `stop_reason`.
4. `ready_consumption_evidence`:
   - `ready_runs_prefix_uri` (run-scoped S3 prefix),
   - `matched_ready_record_uri` (the `.jsonl` path that contains `run_id=17dac...`),
   - `matched_ready_record_status`,
   - `cloudwatch_log_stream` (optional) and `log_snippet_anchor` (optional).
5. `blockers` and `overall_pass` (fail-closed).

### M6.F P6 WSP Execution Summary
Goal:
1. Verify WSP completed streaming and wrote summary evidence.

Entry conditions:
1. `M6.E` PASS.

Tasks:
1. Validate WSP execution completion:
   - task exit code,
   - send/retry counters,
   - non-retryable count.
2. Verify run-scoped WSP summary artifact(s) exist.
3. Emit `m6_f_wsp_summary_snapshot.json`.

DoD:
- [ ] WSP task completed successfully.
- [ ] WSP summary evidence exists locally and durably.
- [ ] Non-retryable errors are zero for pass closure set.

Blockers:
1. `M6F-B1`: WSP task terminal failure.
2. `M6F-B2`: missing/invalid WSP summary evidence.
3. `M6F-B3`: non-retryable failure occurred.
4. `M6F-B4`: M6.F snapshot write/upload failure.

### M6.G P7 Ingest Commit Verification
Goal:
1. Verify IG committed ingest outcomes with coherent evidence.

Entry conditions:
1. `M6.F` PASS.

Tasks:
1. Verify run-scoped ingest evidence:
   - `ingest/receipt_summary.json`,
   - `ingest/kafka_offsets_snapshot.json`,
   - `ingest/quarantine_summary.json` (if applicable).
2. Validate outcome coherence:
   - outcome totals reconcile with attempted sends,
   - topic offsets advanced for run window.
3. Enforce ambiguity gate:
   - unresolved `PUBLISH_AMBIGUOUS == 0`.
4. Emit `m6_g_ingest_commit_snapshot.json`.

DoD:
- [ ] Receipt/offset/quarantine evidence exists and is coherent.
- [ ] Offset advancement for required topics is proven.
- [ ] Unresolved `PUBLISH_AMBIGUOUS` count is zero.
- [ ] M6.G snapshot published locally and durably.

Blockers:
1. `M6G-B1`: missing/invalid ingest commit evidence.
2. `M6G-B2`: offsets did not advance as required.
3. `M6G-B3`: unresolved `PUBLISH_AMBIGUOUS` exists.
4. `M6G-B4`: M6.G snapshot write/upload failure.

### M6.H P4..P7 Gate Rollup + Verdict
Goal:
1. Compute deterministic M6 verdict.

Entry conditions:
1. `M6.A..M6.G` snapshots are readable.

Tasks:
1. Evaluate predicates:
   - `p4_ingest_ready`,
   - `p5_ready_published`,
   - `p6_streaming_active`,
   - `p7_ingest_committed`.
2. Roll up blockers from `M6.A..M6.G`.
3. Verdict:
   - all predicates true + blockers empty => `ADVANCE_TO_M7`,
   - else => `HOLD_M6`.
4. Publish `m6_h_verdict_snapshot.json`.

DoD:
- [ ] Predicate set explicit and reproducible.
- [ ] Blocker rollup complete and fail-closed.
- [ ] Verdict snapshot published locally and durably.

Blockers:
1. `M6H-B1`: prerequisite snapshot missing/unreadable.
2. `M6H-B2`: predicate evaluation incomplete/invalid.
3. `M6H-B3`: blocker rollup non-empty.
4. `M6H-B4`: verdict snapshot write/upload failure.

### M6.I M7 Handoff Artifact Publication
Goal:
1. Publish canonical handoff package for M7 entry.

Entry conditions:
1. `M6.H` verdict is `ADVANCE_TO_M7`.

Tasks:
1. Build `m7_handoff_pack.json` with:
   - `platform_run_id`,
   - `m6_verdict`,
   - `ig_ready_uri`,
   - `sr_ready_uri`,
   - `wsp_summary_uri`,
   - ingest commit evidence URIs,
   - source execution IDs (`m6_a..m6_h`).
2. Enforce non-secret payload.
3. Publish local + durable handoff artifact.

DoD:
- [ ] `m7_handoff_pack.json` complete and non-secret.
- [ ] Durable handoff publication passes.
- [ ] URI references are valid for M7 entry.

Blockers:
1. `M6I-B1`: M6 verdict is not `ADVANCE_TO_M7`.
2. `M6I-B2`: handoff payload missing required fields/URIs.
3. `M6I-B3`: non-secret policy violation.
4. `M6I-B4`: handoff artifact write/upload failure.

## 6) M6 Evidence Contract (Pinned for Execution)
Evidence roots:
1. Run-scoped evidence root:
   - `evidence/runs/<platform_run_id>/`
2. M6 control-plane evidence root:
   - `evidence/dev_min/run_control/<m6_execution_id>/`
3. `<m6_execution_id>` format:
   - `m6_<YYYYMMDDTHHmmssZ>`

Minimum M6 evidence payloads:
1. `evidence/runs/<platform_run_id>/ingest/ig_ready.json`
2. `evidence/runs/<platform_run_id>/sr/sr_pass.json` (or equivalent)
3. `evidence/runs/<platform_run_id>/sr/ready_publish_receipt.json`
4. `evidence/runs/<platform_run_id>/wsp/wsp_summary.json`
5. `evidence/runs/<platform_run_id>/ingest/receipt_summary.json`
6. `evidence/runs/<platform_run_id>/ingest/kafka_offsets_snapshot.json`
7. `evidence/runs/<platform_run_id>/ingest/quarantine_summary.json` (if applicable)
8. `evidence/dev_min/run_control/<m6_execution_id>/m6_a_handle_closure_snapshot.json`
9. `evidence/dev_min/run_control/<m6_execution_id>/m6_h_verdict_snapshot.json`
10. `evidence/dev_min/run_control/<m6_execution_id>/m7_handoff_pack.json`

Notes:
1. M6 artifacts must be non-secret.
2. Any secret-bearing payload in M6 artifacts is a hard blocker.
3. If any required evidence object is missing, M6 verdict must remain `HOLD_M6`.

## 7) M6 Completion Checklist
- [x] M6.A complete
- [x] M6.B complete
- [x] M6.C complete
- [x] M6.D complete
- [ ] M6.E complete
- [ ] M6.F complete
- [ ] M6.G complete
- [ ] M6.H complete
- [ ] M6.I complete

## 8) Risks and Controls
R1: IG auth bypass or degraded boundary behavior.  
Control: mandatory fail/pass auth probes and `ig_ready.json` gate artifact.

R2: READY semantics drift (`P5` bypass).  
Control: READY publication receipt + WSP READY-consumption proof.

R3: WSP streams wrong source surface.  
Control: stream-view-first launch contract validation in `M6.E`.

R4: Ingest closure claimed while ambiguity unresolved.  
Control: hard fail on unresolved `PUBLISH_AMBIGUOUS` in `M6.G`.

## 8.1) Unresolved Blocker Register (Must Be Empty Before M6 Closure)
Current blockers:
1. none.
2. M6.C blocker chain (`M6C-B4` -> `M6C-B1` -> `M6C-B5`) is closed by snapshot:
   - `runs/dev_substrate/m6/20260215T083126Z/m6_c_ingest_ready_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T083126Z/m6_c_ingest_ready_snapshot.json`
   - post-convergence rerun:
     - `runs/dev_substrate/m6/20260215T124328Z/m6_c_ingest_ready_snapshot.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T124328Z/m6_c_ingest_ready_snapshot.json`
3. Control note:
   - runtime rematerialization used an immediate live hotfix path and was then converged into Terraform state:
     - imported `module.demo.aws_kinesis_stream.ig_event_bus`,
     - applied `infra/terraform/dev_min/demo` with pinned vars (`required_platform_run_id`, `ecs_daemon_container_image`, `ig_api_key`),
     - final `terraform plan -detailed-exitcode` returned `0` (no drift).
   - authoritative IG runtime now serves from task definition `arn:aws:ecs:eu-west-2:230372904534:task-definition/fraud-platform-dev-min-ig:8`.
4. M6.D blocker chain (`M6D-B2` -> `M6D-B3/B4`) is closed by snapshot:
   - `runs/dev_substrate/m6/20260215T144233Z/m6_d_sr_ready_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T144233Z/m6_d_sr_ready_snapshot.json`
   - READY receipt:
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/ready_signal/78d859d39f4232fc510463fb868bc6e1.json`
   - control-bus sequence proof:
     - `49671822697342044645261017794300307957859908788827455490` on stream `fraud-platform-dev-min-ig-bus-v0`.
   - closure run caveat:
     - requested output set was narrowed to `s3_event_stream_with_fraud_6B` and used task-scoped execution shims (schema-ref stub + lease keepalive).
     - follow-up closure confirms full 4-output Oracle Store posture:
       - READY receipt: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/ready_signal/17dacbdc997e6765bcd242f7cb3b6c37.json`

Rule:
1. Any newly discovered blocker is appended here with closure criteria.
2. If this register is non-empty, M6 execution remains blocked.

## 9) Exit Criteria
M6 can be marked `DONE` only when:
1. Section 7 checklist is fully complete.
2. M6 evidence contract artifacts are produced and verified.
3. Main plan M6 DoD checklist is complete.
4. M6 verdict is `ADVANCE_TO_M7`.
5. USER confirms progression to M7 activation.

Note:
1. This file does not change phase status.
2. Status transition is made only in `platform.build_plan.md`.
