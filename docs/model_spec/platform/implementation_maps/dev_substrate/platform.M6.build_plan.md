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
- [ ] IG service healthy and stable.
- [ ] Auth boundary fail/pass probes meet expected outcomes.
- [ ] M6.B snapshot published locally and durably.

Blockers:
1. `M6B-B1`: IG service unhealthy or crashlooping.
2. `M6B-B2`: auth boundary behavior invalid.
3. `M6B-B3`: M6.B snapshot write/upload failure.

### M6.C P4 Kafka/S3 Smoke + `ig_ready.json`
Goal:
1. Prove IG can publish to Kafka and write durable ingest evidence.

Entry conditions:
1. `M6.B` PASS.

Tasks:
1. Trigger minimal admission smoke through IG.
2. Verify Kafka publish smoke:
   - topic/partition/offset evidence captured.
3. Verify S3 receipt/quarantine smoke write.
4. Publish run-scoped `ingest/ig_ready.json`.
5. Emit `m6_c_ingest_ready_snapshot.json`.

DoD:
- [ ] Kafka publish smoke evidence captured for IG path.
- [ ] S3 write smoke evidence captured.
- [ ] `ingest/ig_ready.json` exists locally and durably.

Blockers:
1. `M6C-B1`: Kafka smoke publish/read verification failed.
2. `M6C-B2`: S3 write smoke failed.
3. `M6C-B3`: `ig_ready.json` write/upload failure.

### M6.D P5 SR Task + READY Publication
Goal:
1. Execute SR gate task and publish READY evidence.

Entry conditions:
1. `M6.C` PASS.

Tasks:
1. Run one-shot `TD_SR` for active run scope.
2. Verify SR pass artifact and READY publication receipt:
   - SR PASS evidence under `sr/`,
   - READY topic offset receipt under run evidence.
3. Emit `m6_d_sr_ready_snapshot.json`.

DoD:
- [ ] SR task exits success.
- [ ] READY publication receipt exists and references active run.
- [ ] M6.D snapshot published locally and durably.

Blockers:
1. `M6D-B1`: SR task failed.
2. `M6D-B2`: READY missing or mismatched run scope.
3. `M6D-B3`: M6.D snapshot write/upload failure.

### M6.E P6 WSP Launch Contract + READY Consumption
Goal:
1. Validate WSP launch inputs and prove READY is consumed before streaming.

Entry conditions:
1. `M6.D` PASS.

Tasks:
1. Validate WSP launch contract:
   - stream-view root from M5 handoff,
   - IG endpoint/auth handles,
   - WSP knob closure.
2. Run one-shot `TD_WSP`.
3. Capture READY-consumption proof from logs/receipts.
4. Emit `m6_e_wsp_launch_snapshot.json`.

DoD:
- [ ] WSP launch contract is complete and run-scoped.
- [ ] READY-consumption proof exists for active run.
- [ ] M6.E snapshot published locally and durably.

Blockers:
1. `M6E-B1`: WSP launch contract unresolved.
2. `M6E-B2`: WSP did not consume READY for run scope.
3. `M6E-B3`: M6.E snapshot write/upload failure.

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
- [ ] M6.A complete
- [ ] M6.B complete
- [ ] M6.C complete
- [ ] M6.D complete
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
1. None.

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
