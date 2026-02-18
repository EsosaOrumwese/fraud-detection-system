# Dev Substrate Deep Plan - M7 (P8-P10 RTDL + Case/Labels)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M7._
_Last updated: 2026-02-18_

## 0) Purpose
M7 closes `P8..P10` on managed substrate by proving:
1. `P8 RTDL_CAUGHT_UP`: RTDL core consumption reaches caught-up posture with durable offsets/archive evidence.
2. `P9 DECISION_CHAIN_COMMITTED`: decision lane commits decisions/actions/audit under append-only/idempotent posture.
3. `P10 CASE_LABELS_COMMITTED`: case/label append-only commits succeed on managed DB with durable case/label evidence.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P8..P10` sections)
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M6.build_plan.md`
2. `runs/dev_substrate/m6/20260216T214025Z/m7_handoff_pack.json`
3. `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260216T214025Z/m7_handoff_pack.json`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 1.1) Branch Deep Plans (Authoritative by Plane)
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P8.build_plan.md`
   - deep execution plan for `P8 RTDL_CAUGHT_UP`.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P9.build_plan.md`
   - deep execution plan for `P9 DECISION_CHAIN_COMMITTED`.
3. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P10.build_plan.md`
   - deep execution plan for `P10 CASE_LABELS_COMMITTED`.

Control rule:
1. This file (`platform.M7.build_plan.md`) is the M7 orchestrator authority:
   - cross-plane sequencing,
   - integrated blocker rollup,
   - final M7 verdict/handoff.
2. Branch files carry detailed lane execution/DoD per plane and must remain aligned to this orchestrator.

## 2) Scope Boundary for M7
In scope:
1. `P8` RTDL core daemon closure:
   - consumer posture, lag/caught-up closure, origin-offset evidence, archive durability proof.
2. `P9` decision-lane closure:
   - DL/DF/AL/DLA health, idempotency posture, decision/action/audit evidence closure.
3. `P10` case/labels closure:
   - managed DB readiness, subject-key pinning, append-only case/label commit evidence.
4. M7 verdict and M8 handoff publication.

Out of scope:
1. `P11` Obs/Gov closure (`M8`).
2. `P12` teardown (`M9`).
3. certification runs (`M10`).

## 3) M7 Deliverables
1. `M7.A` handle/authority closure snapshot.
2. `M7.B` RTDL readiness snapshot.
3. `M7.C` RTDL caught-up snapshot.
4. `M7.D` archive durability snapshot.
5. `M7.E` decision-lane readiness snapshot.
6. `M7.F` decision-chain commit snapshot.
7. `M7.G` P10 identity/DB readiness snapshot.
8. `M7.H` case-label commit snapshot.
9. `M7.I` deterministic verdict snapshot (`ADVANCE_TO_M8` or `HOLD_M7`).
10. `M7.J` `m8_handoff_pack.json`.

## 4) Execution Gate for This Phase
Current posture:
1. M7 is active and execution has started (`M7.A`, `M7.B`, and `M7.C` are closed; `M7.D` is next).

Execution block:
1. No M8 execution is allowed before M7 verdict is `ADVANCE_TO_M8`.
2. No M7 runtime execution is allowed until demo/confluent stacks are rematerialized and in-scope services are healthy.
3. No P10 execution is allowed with placeholder subject-key handles.

## 4.1) Anti-Cram Law (Binding for M7)
1. M7 is not execution-ready unless these lanes are explicit:
   - authority/handles
   - identity/IAM + secrets
   - network + consumer posture
   - managed DB state/migrations
   - evidence publication contracts
   - rerun/rollback posture
2. Sub-phase count is not fixed; this file expands until closure-grade coverage is achieved.
3. Any newly discovered lane/hole blocks progression and must be added before execution continues.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting sub-phases | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + handles closure | M7.A | M7.I | zero unresolved required `P8..P10` handles |
| RTDL readiness + consumer posture | M7.B | M7.C | healthy RTDL daemons + consumer policy proof |
| RTDL caught-up + offsets | M7.C | M7.I | durable offsets/caught-up artifacts |
| Archive durability proof | M7.D | M7.I | archive object + progress evidence |
| Decision-lane readiness | M7.E | M7.F | healthy DL/DF/AL/DLA services |
| Decision-chain commit closure | M7.F | M7.I | decision/action/audit summaries durable |
| P10 identity + DB readiness | M7.G | M7.H | subject-key fields pinned + DB readiness proof |
| Case/label commit closure | M7.H | M7.I | case/label summaries durable |
| Verdict + M8 handoff | M7.I / M7.J | - | `ADVANCE_TO_M8` + durable `m8_handoff_pack.json` |

## 5) Work Breakdown (Deep)
Execution detail split:
1. `M7.B`/`M7.C`/`M7.D` procedural depth is anchored to `platform.M7.P8.build_plan.md`.
2. `M7.E`/`M7.F` procedural depth is anchored to `platform.M7.P9.build_plan.md`.
3. `M7.G`/`M7.H` procedural depth is anchored to `platform.M7.P10.build_plan.md`.
4. `M7.A`, `M7.I`, and `M7.J` remain orchestrator-owned in this file.

## M7 Decision Pins (Closed Before Execution)
1. Managed-runtime law:
   - RTDL/decision/case-label components run on ECS-managed compute only.
2. `P7` dependency law:
   - official RTDL consumption starts only after M6/P7 pass.
3. Commit-after-write law:
   - offsets are not advanced ahead of durable writes.
4. Append-only truth law:
   - DLA audit, case timelines, and label assertions remain append-only.
5. Idempotency law:
   - AL side effects and case/label appends must be idempotent under pinned key fields.
6. No-local-state law:
   - runtime state/checkpoints live in managed DB/storage only.
7. Evidence-first law:
   - M7 pass requires durable run-scoped evidence for P8/P9/P10.
8. Subject-key law:
   - `CASE_SUBJECT_KEY_FIELDS` and `LABEL_SUBJECT_KEY_FIELDS` must be concretely pinned before P10 commit execution.
9. Fail-closed progression law:
   - any blocker in `M7.A..M7.H` yields `HOLD_M7`.

### M7.A Authority + Handle Closure (`P8..P10`)
Goal:
1. Close required M7 handles before runtime actions.

Entry conditions:
1. `M6.I` handoff exists and indicates `m6_verdict=ADVANCE_TO_M7`.
2. M6 terminal artifacts are readable.

Required inputs:
1. Authority:
   - `platform.build_plan.md`
   - `dev_min_spine_green_v0_run_process_flow.md` (`P8..P10`)
   - `dev_min_handles.registry.v0.md`.
2. Source artifacts:
   - local: `runs/dev_substrate/m6/20260216T214025Z/m7_handoff_pack.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260216T214025Z/m7_handoff_pack.json`.
3. Required handle groups:
   - RTDL services/roles:
     - `SVC_RTDL_CORE_ARCHIVE_WRITER`
     - `SVC_RTDL_CORE_IEG`
     - `SVC_RTDL_CORE_OFP`
     - `SVC_RTDL_CORE_CSFB`
     - `ROLE_RTDL_CORE`
   - Decision lane services/roles:
     - `SVC_DECISION_LANE_DL`
     - `SVC_DECISION_LANE_DF`
     - `SVC_DECISION_LANE_AL`
     - `SVC_DECISION_LANE_DLA`
     - `ROLE_DECISION_LANE`
   - Case/labels services/roles:
     - `SVC_CASE_TRIGGER`
     - `SVC_CM`
     - `SVC_LS`
     - `ROLE_CASE_LABELS`
   - Kafka/topics/consumer posture:
     - `FP_BUS_TRAFFIC_FRAUD_V1`
     - `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1`
     - `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1`
     - `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1`
     - `FP_BUS_RTDL_V1`
     - `FP_BUS_AUDIT_V1`
     - `FP_BUS_CASE_TRIGGERS_V1`
     - `RTDL_CORE_CONSUMER_GROUP_ID`
     - `RTDL_CORE_OFFSET_COMMIT_POLICY`
     - `RTDL_CAUGHT_UP_LAG_MAX`
   - DB/state:
     - `RDS_INSTANCE_ID`
     - `RDS_ENDPOINT`
     - `DB_NAME`
     - `DB_SCHEMA_RTDL`
     - `DB_SCHEMA_CASES`
     - `DB_SCHEMA_LABELS`
     - `SSM_DB_USER_PATH`
     - `SSM_DB_PASSWORD_PATH`
   - Evidence paths:
     - `S3_EVIDENCE_BUCKET`
     - `S3_EVIDENCE_RUN_ROOT_PATTERN`
     - `OFFSETS_SNAPSHOT_PATH_PATTERN`
     - `RTDL_CORE_EVIDENCE_PATH_PATTERN`
     - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
     - `DLA_EVIDENCE_PATH_PATTERN`
     - `CASE_EVIDENCE_PATH_PATTERN`
     - `LABEL_EVIDENCE_PATH_PATTERN`.

Tasks:
1. Validate M6->M7 carry-forward invariants (`platform_run_id`, verdict, blocker-free handoff).
2. Build deterministic handle-closure matrix with source/probe results.
3. Enforce fail-closed:
   - no unresolved required P8/P9 handles,
   - no wildcard aliases in required set.
4. Track `CASE_SUBJECT_KEY_FIELDS` and `LABEL_SUBJECT_KEY_FIELDS` explicitly:
   - if placeholder, open `M7G-B1` debt and block P10 execution until closed.
5. Emit `m7_a_handle_closure_snapshot.json`.
6. Publish local + durable snapshot.

DoD:
- [x] M6->M7 carry-forward invariants verified.
- [x] Required P8/P9/P10 handles are explicit and probed.
- [x] Placeholder/wildcard required handles are absent (except tracked P10 subject-key debt).
- [x] `m7_a_handle_closure_snapshot.json` exists locally and durably.

Execution notes:
1. `M7.A` execution id:
   - `m7_20260218T141420Z`
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m7/20260218T141420Z/m7_a_handle_closure_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_a_handle_closure_snapshot.json`
3. Closure result:
   - `overall_pass=true`,
   - `resolved_handle_count=40`,
   - `unresolved_handle_count=0`,
   - probe failures: none.
4. Topic/materialization probe basis:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260218T133848Z/topic_readiness_snapshot.json` (`overall_pass=true`).
5. Forward debt (not an M7.A blocker, but blocks P10 execution entry):
   - `M7G-B1` remains open because:
     - `CASE_SUBJECT_KEY_FIELDS = <PIN_AT_P10_PHASE_ENTRY>`
     - `LABEL_SUBJECT_KEY_FIELDS = <PIN_AT_P10_PHASE_ENTRY>`.

Blockers:
1. `M7A-B1`: M6 handoff invalid/unreadable or run-id mismatch.
2. `M7A-B2`: required handles unresolved.
3. `M7A-B3`: placeholder/wildcard detected in required closure set.
4. `M7A-B4`: handle materialization probe failure.
5. `M7A-B5`: snapshot write/upload failure.

### M7.B P8 RTDL Readiness + Consumer Posture
Detailed lane authority: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P8.build_plan.md` (`P8.A`).

Goal:
1. Prove RTDL core services are healthy and configured for commit-after-write consumption.

Entry conditions:
1. `M7.A` PASS.
2. Demo/confluent stacks rematerialized and service surfaces reachable.

Required inputs:
1. Latest `M7.A` snapshot.
2. ECS service handles `SVC_RTDL_CORE_*` and role handle `ROLE_RTDL_CORE`.
3. `RTDL_CORE_CONSUMER_GROUP_ID`, `RTDL_CORE_OFFSET_COMMIT_POLICY`.

Tasks:
1. Confirm RTDL services are active (`desired=1`, `running=1`, no crashloop).
2. Confirm task env and runtime posture include required consumer group and commit policy.
3. Confirm Kafka and evidence/DB dependencies are reachable from RTDL tasks.
4. Emit `m7_b_rtdl_readiness_snapshot.json`.
5. Publish local + durable snapshot.

DoD:
- [x] RTDL core services healthy and stable.
- [x] Consumer group + commit policy posture verified.
- [x] Dependency reachability checks pass.
- [x] Snapshot published locally and durably.

Execution notes:
1. `M7.B` execution context:
   - `m7_execution_id = m7_20260218T141420Z`
   - `platform_run_id = platform_20260213T214223Z`
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m7/20260218T141420Z/m7_b_rtdl_readiness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_b_rtdl_readiness_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blocker rollup empty.
4. Closure remediation before final rerun:
   - RTDL task definitions rematerialized with pinned consumer-posture env vars:
     - `RTDL_CORE_CONSUMER_GROUP_ID=fraud-platform-dev-min-rtdl-core-v0`
     - `RTDL_CORE_OFFSET_COMMIT_POLICY=commit_after_durable_write`.

Blockers:
1. `M7B-B1`: RTDL service unhealthy/crashlooping.
2. `M7B-B2`: consumer posture mismatch (group/policy not pinned).
3. `M7B-B3`: dependency reachability failure (Kafka/DB/S3).
4. `M7B-B4`: snapshot write/upload failure.

### M7.C P8 Offsets + Caught-Up Evidence Closure
Detailed lane authority: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P8.build_plan.md` (`P8.B`).

Goal:
1. Produce durable RTDL offsets/caught-up evidence and close the lag gate.

Entry conditions:
1. `M7.B` PASS.

Required inputs:
1. Required topic set from handles.
2. `RTDL_CAUGHT_UP_LAG_MAX`.
3. Evidence path handles:
   - `OFFSETS_SNAPSHOT_PATH_PATTERN`
   - `RTDL_CORE_EVIDENCE_PATH_PATTERN`.

Tasks:
1. Collect run-window offset progression across required RTDL inputs.
2. Verify lag is <= `RTDL_CAUGHT_UP_LAG_MAX` (or end-offset reached for demo window).
3. Emit run-scoped artifacts:
   - `rtdl_core/offsets_snapshot.json`
   - `rtdl_core/caught_up.json`.
4. Emit control-plane `m7_c_rtdl_caught_up_snapshot.json`.
5. Publish local + durable snapshot.

DoD:
- [x] Offsets snapshot exists and is complete for required topics/partitions.
- [x] Caught-up gate closes with lag threshold.
- [x] Control snapshot is published locally and durably.

Execution notes:
1. Initial `M7.C` execution published artifacts but failed closure:
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/rtdl_core/offsets_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/rtdl_core/caught_up.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_c_rtdl_caught_up_snapshot.json`
2. Result:
   - `overall_pass=false`
   - fail-closed stale-basis blocker opened during first attempt.
3. Rerun after P7 basis refresh closed PASS:
   - refreshed ingest basis:
     - local: `runs/dev_substrate/m6/20260218T154307Z/kafka_offsets_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/ingest/kafka_offsets_snapshot.json`
   - rerun snapshot:
     - local: `runs/dev_substrate/m7/20260218T141420Z/m7_c_rtdl_caught_up_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_c_rtdl_caught_up_snapshot.json`
   - closure result:
     - `overall_pass=true`
     - blocker rollup empty.
4. The refreshed basis now explicitly captures the active Kafka epoch for required topics as empty (`run_end_offset=-1` on all partitions), removing stale-basis drift for this lane.

Blockers:
1. `M7C-B1`: offsets evidence missing/incomplete.
2. `M7C-B2`: lag threshold not met.
3. `M7C-B3`: run-scope mismatch in evidence.
4. `M7C-B4`: snapshot write/upload failure.
5. `M7C-B5`: run-window ingest basis is stale versus active Kafka topic state.

### M7.D P8 Archive Durability Proof
Detailed lane authority: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P8.build_plan.md` (`P8.C`).

Goal:
1. Prove archive durability surface is working for M7 run scope.

Entry conditions:
1. `M7.C` PASS.

Required inputs:
1. `S3_ARCHIVE_BUCKET`
2. `S3_ARCHIVE_RUN_PREFIX_PATTERN`
3. `S3_ARCHIVE_EVENTS_PREFIX_PATTERN`.

Tasks:
1. Verify archive prefix is run-scoped and non-empty for this run where archive writer is active.
2. Verify archive progression is consistent with RTDL offsets progression.
3. Emit run-scoped `rtdl_core/archive_write_summary.json` (if writer active).
4. Emit control-plane `m7_d_archive_durability_snapshot.json`.
5. Publish local + durable snapshot.

DoD:
- [ ] Archive durability proof exists for active writer lane.
- [ ] Archive progression is coherent with RTDL progression.
- [ ] Snapshot published locally and durably.

Execution notes:
1. Executed `M7.D` and published:
   - local: `runs/dev_substrate/m7/20260218T141420Z/rtdl_core/archive_write_summary.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/rtdl_core/archive_write_summary.json`
   - local: `runs/dev_substrate/m7/20260218T141420Z/m7_d_archive_durability_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_d_archive_durability_snapshot.json`
2. Result:
   - `overall_pass=false`
   - open blocker `M7D-B4`.
3. Runtime finding behind blocker:
   - archive-writer service is on real worker runtime command (task definition `:15`),
   - service is crash-looping (`desired=1`, `running=0`, repeated non-zero exits),
   - CloudWatch logs show `AssertionError` in `archive_writer.worker` (`_file_reader is None`).
4. Current epoch offset basis is empty (`run_end=-1` on required partitions), so archive count coherence is neutral (`expected_archive_events_from_offsets=0`, `archive_object_count=0`); closure is still blocked by runtime stability failure.

Blockers:
1. `M7D-B1`: archive prefix missing/empty when writer lane is expected active.
2. `M7D-B2`: archive progression mismatch vs offsets evidence.
3. `M7D-B3`: snapshot write/upload failure.
4. `M7D-B4`: archive writer runtime command is materialized but worker crashes under active service posture.

### M7.E P9 Decision-Lane Readiness + Idempotency Posture
Detailed lane authority: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P9.build_plan.md` (`P9.A`).

Goal:
1. Prove decision-lane services are healthy with pinned idempotency posture.

Entry conditions:
1. `M7.D` PASS.

Required inputs:
1. Service handles `SVC_DECISION_LANE_*`.
2. Role handle `ROLE_DECISION_LANE`.
3. Idempotency handles:
   - `ACTION_IDEMPOTENCY_KEY_FIELDS`
   - `ACTION_OUTCOME_WRITE_POLICY`.

Tasks:
1. Confirm decision-lane services healthy/stable.
2. Verify runtime posture includes idempotency and append-only write policy.
3. Confirm required inputs from RTDL lane are flowing.
4. Emit `m7_e_decision_lane_readiness_snapshot.json`.
5. Publish local + durable snapshot.

DoD:
- [ ] DL/DF/AL/DLA services healthy and stable.
- [ ] Idempotency + append-only posture validated.
- [ ] Snapshot published locally and durably.

Blockers:
1. `M7E-B1`: decision-lane service unhealthy/crashlooping.
2. `M7E-B2`: idempotency/write-policy posture mismatch.
3. `M7E-B3`: no valid RTDL input flow.
4. `M7E-B4`: snapshot write/upload failure.

### M7.F P9 Decision-Chain Commit Evidence Closure
Detailed lane authority: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P9.build_plan.md` (`P9.B`).

Goal:
1. Produce durable decision/action/audit evidence for P9.

Entry conditions:
1. `M7.E` PASS.

Required inputs:
1. `DECISION_LANE_EVIDENCE_PATH_PATTERN`
2. `DLA_EVIDENCE_PATH_PATTERN`
3. Required run-scope and lane service handles.

Tasks:
1. Build run-scoped:
   - `decision_lane/decision_summary.json`
   - `decision_lane/action_summary.json`
   - `decision_lane/audit_summary.json`.
2. Verify append-only audit posture and idempotent outcomes (no double-action effect).
3. Emit control-plane `m7_f_decision_chain_snapshot.json`.
4. Publish local + durable snapshot.

DoD:
- [ ] Decision/action/audit summaries exist and are run-scoped.
- [ ] Append-only + idempotency checks pass.
- [ ] Snapshot published locally and durably.

Blockers:
1. `M7F-B1`: required P9 evidence missing/incomplete.
2. `M7F-B2`: append-only/idempotency violation detected.
3. `M7F-B3`: snapshot write/upload failure.

### M7.G P10 Identity-Key Pin + Managed DB Readiness
Detailed lane authority: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P10.build_plan.md` (`P10.A`).

Goal:
1. Close P10 decision debt by pinning subject-key handles and proving DB readiness.

Entry conditions:
1. `M7.F` PASS.

Required inputs:
1. Handle registry identity keys:
   - `CASE_SUBJECT_KEY_FIELDS`
   - `LABEL_SUBJECT_KEY_FIELDS`.
2. DB handles:
   - `RDS_ENDPOINT`
   - `DB_NAME`
   - `SSM_DB_USER_PATH`
   - `SSM_DB_PASSWORD_PATH`
   - `DB_SECURITY_GROUP_ID`
   - `TD_DB_MIGRATIONS` (if required).

Tasks:
1. Confirm subject-key fields are concretely pinned (no `<PIN_AT_P10_PHASE_ENTRY>` placeholders).
2. Verify DB readiness (connectivity, schema present, migrations complete as required).
3. Emit `m7_g_case_label_db_readiness_snapshot.json`.
4. Publish local + durable snapshot.

DoD:
- [ ] `CASE_SUBJECT_KEY_FIELDS` and `LABEL_SUBJECT_KEY_FIELDS` are pinned, concrete, and non-placeholder.
- [ ] Managed DB readiness is proven for CM/LS runtime.
- [ ] Snapshot published locally and durably.

Blockers:
1. `M7G-B1`: subject-key handle placeholders unresolved.
2. `M7G-B2`: DB readiness/migration failure.
3. `M7G-B3`: snapshot write/upload failure.

### M7.H P10 Case/Label Commit Evidence Closure
Detailed lane authority: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P10.build_plan.md` (`P10.B`).

Goal:
1. Produce durable case/label evidence proving append-only/idempotent commits.

Entry conditions:
1. `M7.G` PASS.

Required inputs:
1. Service handles `SVC_CASE_TRIGGER`, `SVC_CM`, `SVC_LS`.
2. Evidence path handles:
   - `CASE_EVIDENCE_PATH_PATTERN`
   - `LABEL_EVIDENCE_PATH_PATTERN`.

Tasks:
1. Verify case-trigger processing and CM timeline appends for run scope.
2. Verify LS label assertion appends for run scope.
3. Build run-scoped:
   - `case_labels/case_summary.json`
   - `case_labels/label_summary.json`.
4. Emit control-plane `m7_h_case_label_commit_snapshot.json`.
5. Publish local + durable snapshot.

DoD:
- [ ] Case summary and label summary are present and run-scoped.
- [ ] Append-only + idempotency posture is validated for case/label writes.
- [ ] Snapshot published locally and durably.

Blockers:
1. `M7H-B1`: case/label evidence missing or incomplete.
2. `M7H-B2`: append-only/idempotency posture violation.
3. `M7H-B3`: snapshot write/upload failure.

### M7.I P8..P10 Gate Rollup + Verdict
Goal:
1. Compute deterministic M7 verdict.

Entry conditions:
1. `M7.A..M7.H` snapshots are readable.

Tasks:
1. Evaluate predicates:
   - `p8_rtdl_caught_up`
   - `p9_decision_chain_committed`
   - `p10_case_labels_committed`.
2. Roll up blockers from `M7.A..M7.H`.
3. Verdict:
   - all predicates true + blockers empty => `ADVANCE_TO_M8`
   - else => `HOLD_M7`.
4. Publish `m7_i_verdict_snapshot.json`.

DoD:
- [ ] Predicate set explicit and reproducible.
- [ ] Blocker rollup complete and fail-closed.
- [ ] Verdict snapshot published locally and durably.

Blockers:
1. `M7I-B1`: prerequisite snapshot missing/unreadable.
2. `M7I-B2`: predicate evaluation incomplete/invalid.
3. `M7I-B3`: blocker rollup non-empty.
4. `M7I-B4`: verdict snapshot write/upload failure.

### M7.J M8 Handoff Artifact Publication
Goal:
1. Publish canonical handoff package for M8 entry.

Entry conditions:
1. `M7.I` verdict is `ADVANCE_TO_M8`.

Tasks:
1. Build `m8_handoff_pack.json` with:
   - `platform_run_id`
   - `m7_verdict`
   - `p8`/`p9`/`p10` evidence URIs
   - source execution IDs (`m7_a..m7_i`).
2. Enforce non-secret payload.
3. Publish local + durable handoff artifact.

DoD:
- [ ] `m8_handoff_pack.json` complete and non-secret.
- [ ] Durable handoff publication passes.
- [ ] URI references are valid for M8 entry.

Blockers:
1. `M7J-B1`: M7 verdict is not `ADVANCE_TO_M8`.
2. `M7J-B2`: handoff payload missing required fields/URIs.
3. `M7J-B3`: non-secret policy violation.
4. `M7J-B4`: handoff artifact write/upload failure.

## 6) M7 Evidence Contract (Pinned for Execution)
Evidence roots:
1. Run-scoped evidence root:
   - `evidence/runs/<platform_run_id>/`
2. M7 control-plane evidence root:
   - `evidence/dev_min/run_control/<m7_execution_id>/`
3. `<m7_execution_id>` format:
   - `m7_<YYYYMMDDTHHmmssZ>`.

Minimum M7 evidence payloads:
1. `evidence/runs/<platform_run_id>/rtdl_core/offsets_snapshot.json`
2. `evidence/runs/<platform_run_id>/rtdl_core/caught_up.json`
3. `evidence/runs/<platform_run_id>/rtdl_core/archive_write_summary.json` (if archive writer active)
4. `evidence/runs/<platform_run_id>/decision_lane/decision_summary.json`
5. `evidence/runs/<platform_run_id>/decision_lane/action_summary.json`
6. `evidence/runs/<platform_run_id>/decision_lane/audit_summary.json`
7. `evidence/runs/<platform_run_id>/case_labels/case_summary.json`
8. `evidence/runs/<platform_run_id>/case_labels/label_summary.json`
9. `evidence/dev_min/run_control/<m7_execution_id>/m7_a_handle_closure_snapshot.json`
10. `evidence/dev_min/run_control/<m7_execution_id>/m7_i_verdict_snapshot.json`
11. `evidence/dev_min/run_control/<m7_execution_id>/m8_handoff_pack.json`.

Notes:
1. M7 artifacts must be non-secret.
2. Any secret-bearing payload in M7 artifacts is a hard blocker.
3. If any required evidence object is missing, M7 verdict must remain `HOLD_M7`.

## 7) M7 Completion Checklist
- [x] M7.A complete
- [x] M7.B complete
- [x] M7.C complete
- [ ] M7.D complete
- [ ] M7.E complete
- [ ] M7.F complete
- [ ] M7.G complete
- [ ] M7.H complete
- [ ] M7.I complete
- [ ] M7.J complete

## 8) Risks and Controls
R1: RTDL declared caught-up without durable offset evidence.  
Control: mandatory offsets/caught-up artifacts and lag threshold gate.

R2: Decision chain passes while audit truth is mutable.  
Control: append-only checks in P9 evidence closure.

R3: P10 proceeds with unresolved subject identity keys.  
Control: hard blocker `M7G-B1` on placeholder subject-key fields.

R4: Hidden substrate downtime after teardown/rematerialization cycles.  
Control: M7.B/E/G readiness gates before commit lanes.

## 8.1) Unresolved Blocker Register (Must Be Empty Before M7 Closure)
Current blockers:
1. `M7G-B1` (open, forward blocker for `M7.G`/`P10` entry)
   - subject-key handle placeholders unresolved in registry:
     - `CASE_SUBJECT_KEY_FIELDS = <PIN_AT_P10_PHASE_ENTRY>`
     - `LABEL_SUBJECT_KEY_FIELDS = <PIN_AT_P10_PHASE_ENTRY>`
   - closure rule:
     - pin concrete non-placeholder subject-key fields before `M7.G` execution.
2. `M7D-B4` (open, execution blocker for `M7.D`/`P8.C`)
   - observed posture:
     - archive-writer ECS service is on real worker runtime command (task definition `:15`),
     - service is crash-looping (`desired=1`, `running=0`, repeated non-zero exits),
     - CloudWatch logs show runtime `AssertionError` in `archive_writer.worker` (`_file_reader is None`).
     - implementation fix is landed in-repo (Kafka reader + explicit dispatch), pending runtime image rollout.
   - closure rule:
     - keep real worker runtime command materialized,
     - fix archive-writer runtime crash under managed Kafka posture,
     - rerun `M7.D` and require `overall_pass=true` with empty blockers.
Rule:
1. Any newly discovered blocker is appended here with closure criteria.
2. If this register is non-empty, M7 execution remains blocked.

## 9) Exit Criteria
M7 can be marked `DONE` only when:
1. Section 7 checklist is fully complete.
2. M7 evidence contract artifacts are produced and verified.
3. Main plan M7 DoD checklist is complete.
4. M7 verdict is `ADVANCE_TO_M8`.
5. USER confirms progression to M8 activation.

Note:
1. This file does not change phase status.
2. Status transition is made only in `platform.build_plan.md`.
