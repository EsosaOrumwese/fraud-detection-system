# Dev Substrate Deep Plan - M7.P8 (P8 RTDL_CAUGHT_UP)
_Status source of truth: `platform.build_plan.md` and `platform.M7.build_plan.md`_
_This document provides plane-deep planning detail for M7 P8._
_Last updated: 2026-02-18_

## 0) Purpose
Close `P8 RTDL_CAUGHT_UP` with explicit, durable proof that RTDL core:
1. consumes run-scoped admitted Kafka inputs,
2. advances offsets only after durable writes,
3. reaches caught-up threshold,
4. persists replay-grade offset/archive evidence.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (M7 section)
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P8`)
4. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`

Supporting:
1. `runs/dev_substrate/m6/20260216T214025Z/m7_handoff_pack.json`
2. `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260216T214025Z/m7_handoff_pack.json`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M7.P8
In scope:
1. RTDL core readiness + dependency checks (`M7.B` lane depth).
2. Offsets/caught-up gate closure (`M7.C` lane depth).
3. Archive durability closure (`M7.D` lane depth).
4. P8 plane-level closure snapshot for M7 orchestrator consumption.

Out of scope:
1. Decision-lane commits (`P9`).
2. Case/labels commits (`P10`).
3. Final M7 verdict/handoff (`M7.I`/`M7.J`).

## 3) P8 Deliverables
1. `m7_b_rtdl_readiness_snapshot.json` (control-plane).
2. `m7_c_rtdl_caught_up_snapshot.json` (control-plane).
3. `m7_d_archive_durability_snapshot.json` (control-plane).
4. Run-scoped `rtdl_core/offsets_snapshot.json`.
5. Run-scoped `rtdl_core/caught_up.json`.
6. Run-scoped `rtdl_core/archive_write_summary.json` (if archive writer is active).
7. `m7_p8_plane_snapshot.json` (plane closure summary for orchestrator).

## 4) Execution Gate for This Plane
Current posture:
1. `P8.A` is execution-closed with PASS evidence; `P8.B` is next.

Execution block:
1. No P8 runtime execution before `M7.A` handle closure pass.
2. No P8 runtime execution while substrate is torn down/unhealthy.
3. No P8 pass with missing offsets/caught-up artifacts.

## 4.1) Capability-Lane Matrix (P8)
| Capability lane | Primary step | Minimum PASS evidence |
| --- | --- | --- |
| RTDL service readiness | P8.A | RTDL services healthy with stable desired/running posture |
| Consumer posture | P8.A | `RTDL_CORE_CONSUMER_GROUP_ID` + commit policy confirmed |
| Offset progression | P8.B | durable `offsets_snapshot.json` with required topic/partition coverage |
| Caught-up gate | P8.B | durable `caught_up.json` with lag <= threshold |
| Archive durability | P8.C | archive summary or explicit inactive-writer proof |
| Plane closure | P8.D | `m7_p8_plane_snapshot.json` overall pass true |

## 4.2) Pre-Execution Readiness Matrix (Must Pass Before P8.A Starts)
1. `M7.A` carry-forward invariants:
   - `m7_a_handle_closure_snapshot.json` exists and `overall_pass=true`.
   - `platform_run_id` is present and non-empty.
2. Substrate health/stability:
   - ECS cluster `ACTIVE`.
   - `SVC_RTDL_CORE_ARCHIVE_WRITER`, `SVC_RTDL_CORE_IEG`, `SVC_RTDL_CORE_OFP`, `SVC_RTDL_CORE_CSFB` each at `desired=running=1`.
   - no active crashloop/restart storm in the latest service events.
3. Kafka materialization posture:
   - latest M2.F topic readiness snapshot is present and `overall_pass=true`.
   - required P8 topics are present in that snapshot.
4. Run-scope continuity:
   - RTDL lane tasks expose `REQUIRED_PLATFORM_RUN_ID` equal to `platform_run_id`.
   - no conflicting run-scope value observed across RTDL services.
5. Access and write posture:
   - RTDL role can read required SSM paths.
   - RTDL role can write run-scoped evidence objects.
   - archive bucket/prefix is writable if archive writer is active.
6. DB dependency posture:
   - runtime DB is reachable/available and endpoint matches active demo outputs.

Fail-closed rule:
1. Any unmet row above blocks P8 execution and must be logged as `M7B-B*` before continuing.

## 4.3) Runtime Budget Gates (Performance Law, P8-Specific)
1. `P8.A` budget: 10 minutes max wall clock.
2. `P8.B` budget: 20 minutes max wall clock.
3. `P8.C` budget: 10 minutes max wall clock.
4. `P8.D` budget: 5 minutes max wall clock.
5. Plane budget (`P8.A..P8.D`): 40 minutes max wall clock.

Budget control:
1. Each sub-phase snapshot must include `started_at_utc`, `completed_at_utc`, and `elapsed_seconds`.
2. Any overrun requires explicit blocker + root-cause note; otherwise sub-phase is fail-closed.

## 4.4) Rerun and Rollback Prep (Must Be Planned Before P8.A)
1. Rerun trigger conditions:
   - missing/invalid offsets evidence,
   - lag threshold not met,
   - archive coherence failure.
2. Safe rollback boundaries:
   - do not delete Kafka topics or committed evidence from prior phases,
   - only clear rebuildable RTDL intermediate state if closure rules permit.
3. Rerun contract:
   - rerun must preserve `platform_run_id`,
   - rerun writes a new control-plane snapshot id while keeping run-scoped evidence path stable.

## 5) Decision Pins (P8)
1. RTDL runs on ECS-managed runtime only.
2. Official P8 consumption begins only after M6/P7 pass.
3. Offset commit posture is `commit_after_durable_write`.
4. Caught-up threshold is governed by `RTDL_CAUGHT_UP_LAG_MAX`.
5. Archive proof must be explicit: active writer summary or explicit inactive-writer declaration.
6. Any missing required evidence is fail-closed.
7. Consumer identity is stable:
   - `RTDL_CORE_CONSUMER_GROUP_ID` must not change inside one M7 execution.
8. Run-scope law:
   - all P8 evidence must resolve under `platform_run_id` from M7 handoff.
9. Topic ownership law:
   - P8 consumes traffic/context and feeds downstream evidence; no ownership drift to other lanes.
10. Performance law:
   - P8 sub-phases must meet runtime budgets or produce explicit blocker-approved overrun rationale.

## 6) Plane Work Breakdown

### P8.A Readiness + Consumer Posture (`M7.B` depth)
Goal:
1. Prove RTDL services and dependencies are execution-ready.

Entry conditions:
1. Section 4.2 readiness matrix is fully satisfied.
2. `M7.A` snapshot is readable locally and durably.

Required inputs:
1. `M7.A` pass snapshot.
2. RTDL service handles:
   - `SVC_RTDL_CORE_ARCHIVE_WRITER`
   - `SVC_RTDL_CORE_IEG`
   - `SVC_RTDL_CORE_OFP`
   - `SVC_RTDL_CORE_CSFB`
3. Kafka/consumer handles:
   - `RTDL_CORE_CONSUMER_GROUP_ID`
   - `RTDL_CORE_OFFSET_COMMIT_POLICY`.

Preparation checks:
1. Confirm ECS service stability window with two consecutive checks (no restart churn).
2. Confirm run-scope env consistency (`REQUIRED_PLATFORM_RUN_ID`).
3. Confirm latest topic-readiness evidence exists and is `overall_pass=true`.

Execution sequence:
1. Verify services healthy (`desired=1`, `running=1`, no crashloop).
2. Verify consumer-group identity and commit policy posture.
3. Verify dependency reachability (Kafka/S3/DB/logging).
4. Verify RTDL evidence-root write posture.
5. Publish `m7_b_rtdl_readiness_snapshot.json` with:
   - service health table,
   - consumer posture values,
   - run-scope checks,
   - dependency probe results,
   - elapsed timing.

DoD:
- [x] RTDL readiness checks pass.
- [x] Consumer posture checks pass.
- [x] Run-scope and dependency checks pass.
- [x] Snapshot exists locally + durably.

Execution notes:
1. `P8.A` execution context:
   - `m7_execution_id = m7_20260218T141420Z`
   - `platform_run_id = platform_20260213T214223Z`
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m7/20260218T141420Z/m7_b_rtdl_readiness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_b_rtdl_readiness_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blocker rollup empty.
4. Runtime alignment remediation applied before closure:
   - RTDL daemon task definitions now carry pinned consumer posture env vars:
     - `RTDL_CORE_CONSUMER_GROUP_ID=fraud-platform-dev-min-rtdl-core-v0`
     - `RTDL_CORE_OFFSET_COMMIT_POLICY=commit_after_durable_write`
   - topic-readiness probe aligns to `M2.F` evidence schema (`topics_present`).

Blockers:
1. `M7B-B1`: RTDL service unhealthy.
2. `M7B-B2`: consumer posture mismatch.
3. `M7B-B3`: dependency reachability failure.
4. `M7B-B4`: snapshot publish failure.
5. `M7B-B5`: run-scope mismatch across RTDL services.
6. `M7B-B6`: evidence write-path access probe failure.
7. `M7B-B7`: required topic-readiness evidence missing/stale.

### P8.B Offsets + Caught-Up Closure (`M7.C` depth)
Goal:
1. Close lag/offset gate with replay-grade evidence.

Entry conditions:
1. `M7.B` pass snapshot exists and is durable.
2. Required topic set is confirmed materialized for the active run window.

Required inputs:
1. `M7.B` pass snapshot.
2. Required topic set:
   - `FP_BUS_TRAFFIC_FRAUD_V1`
   - `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1`
   - `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1`
   - `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1`.
3. Evidence handles:
   - `OFFSETS_SNAPSHOT_PATH_PATTERN`
   - `RTDL_CORE_EVIDENCE_PATH_PATTERN`.

Preparation checks:
1. Load run-start context from P7 ingest evidence (`ingest/kafka_offsets_snapshot.json`) where available.
2. Confirm partition coverage strategy for each required topic.
3. Confirm caught-up threshold value is explicit (`RTDL_CAUGHT_UP_LAG_MAX`).

Execution sequence:
1. Build run-window offsets for required topics/partitions (start/end/current/lag).
2. Validate offset progression (no backwards/invalid progression).
3. Evaluate caught-up gate:
   - lag <= `RTDL_CAUGHT_UP_LAG_MAX`,
   - or end-offset reached for demo-bound window.
4. Publish run-scoped:
   - `rtdl_core/offsets_snapshot.json`
   - `rtdl_core/caught_up.json`.
5. Publish `m7_c_rtdl_caught_up_snapshot.json` with:
   - per-topic/partition lag table,
   - threshold used,
   - gate decision,
   - elapsed timing.

DoD:
- [x] Offsets snapshot complete.
- [x] Caught-up threshold satisfied.
- [x] Partition coverage is complete across required topics.
- [x] Snapshot exists locally + durably.

Execution notes:
1. First `P8.B` execution artifacts are published but not closure-valid:
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/rtdl_core/offsets_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/rtdl_core/caught_up.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_c_rtdl_caught_up_snapshot.json`
2. Result was fail-closed (`overall_pass=false`) due stale run-window basis versus active Kafka topic state (`M7C-B7`).
3. Rerun after active-epoch P7 basis refresh closed PASS:
   - refreshed basis:
     - local: `runs/dev_substrate/m6/20260218T154307Z/kafka_offsets_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/ingest/kafka_offsets_snapshot.json`
   - rerun outputs:
     - local: `runs/dev_substrate/m7/20260218T141420Z/rtdl_core/offsets_snapshot.json`
     - local: `runs/dev_substrate/m7/20260218T141420Z/rtdl_core/caught_up.json`
     - local: `runs/dev_substrate/m7/20260218T141420Z/m7_c_rtdl_caught_up_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/rtdl_core/offsets_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/rtdl_core/caught_up.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_c_rtdl_caught_up_snapshot.json`
   - closure result:
     - `overall_pass=true`
     - blockers empty.
4. Current active Kafka epoch for required topics is empty (`run_start_offset=run_end_offset=-1` on all required partitions) and is now explicitly represented in the refreshed P7 basis.

Blockers:
1. `M7C-B1`: offsets evidence missing/incomplete.
2. `M7C-B2`: lag threshold unmet.
3. `M7C-B3`: run-scope mismatch.
4. `M7C-B4`: snapshot publish failure.
5. `M7C-B5`: partition coverage gap in required topics.
6. `M7C-B6`: offset regression/inconsistent progression detected.
7. `M7C-B7`: run-window offset basis is stale versus active Kafka substrate (for example, live end offsets reset while run-end basis remains non-zero).

### P8.C Archive Durability Closure (`M7.D` depth)
Goal:
1. Prove archive durability surface for active writer posture.

Entry conditions:
1. `M7.C` pass snapshot exists and is durable.

Required inputs:
1. `M7.C` pass snapshot.
2. Archive handles:
   - `S3_ARCHIVE_BUCKET`
   - `S3_ARCHIVE_RUN_PREFIX_PATTERN`
   - `S3_ARCHIVE_EVENTS_PREFIX_PATTERN`.

Preparation checks:
1. Determine archive writer posture from service desired/running state.
2. Resolve concrete archive run prefix for `platform_run_id`.

Execution sequence:
1. If archive writer is active:
   - verify archive prefix has run-scoped objects,
   - verify object timestamps/count progression coherence with offsets evidence.
2. If archive writer is inactive by design:
   - emit explicit inactive-writer rationale and evidence pointer.
3. Publish run-scoped `rtdl_core/archive_write_summary.json` when active.
4. Publish `m7_d_archive_durability_snapshot.json` with:
   - active/inactive posture,
   - archive prefix/object counters,
   - coherence check result,
   - elapsed timing.

DoD:
- [ ] Archive durability posture is explicit and evidenced.
- [ ] Active-writer case includes archive summary.
- [ ] Archive coherence against offsets evidence is verified.
- [ ] Snapshot exists locally + durably.

Execution notes:
1. Executed `M7.D` on active M7 context (`m7_execution_id=m7_20260218T141420Z`, `platform_run_id=platform_20260213T214223Z`) and published:
   - run-scoped summary:
     - local: `runs/dev_substrate/m7/20260218T141420Z/rtdl_core/archive_write_summary.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/rtdl_core/archive_write_summary.json`
   - control snapshot:
     - local: `runs/dev_substrate/m7/20260218T141420Z/m7_d_archive_durability_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_d_archive_durability_snapshot.json`
2. Closure result: fail-closed (`overall_pass=false`), blocker set non-empty.
3. Runtime posture observed:
   - archive writer ECS service is configured on real worker runtime command (`task definition :15`),
   - service is currently crash-looping (`desired=1`, `running=0`, repeated non-zero stops),
   - CloudWatch logs show `AssertionError` in `archive_writer.worker` (`_file_reader is None`),
   - archive bucket run prefix is empty for this run (`archive_object_count=0`),
   - offsets coherence count is neutral for this epoch (`expected_archive_events_from_offsets=0` from refreshed P7 basis).
4. Open blocker is runtime stability failure (`M7D-B4`) under managed Kafka posture, not archive count incoherence.

Blockers:
1. `M7D-B1`: expected archive proof missing.
2. `M7D-B2`: archive/offset coherence failure.
3. `M7D-B3`: snapshot publish failure.
4. `M7D-B4`: archive writer runtime command is materialized but worker crashes under active service posture.

### P8.D Plane Closure Summary
Goal:
1. Emit deterministic P8 closure artifact for M7 orchestrator.

Entry conditions:
1. `P8.A`, `P8.B`, and `P8.C` completed.

Tasks:
1. Roll up blockers from `M7.B..M7.D`.
2. Compute `p8_overall_pass`.
3. Publish `m7_p8_plane_snapshot.json` with:
   - source snapshot refs,
   - lag summary,
   - archive posture,
   - runtime budget summary (`P8.A..P8.C`),
   - blocker rollup,
   - `overall_pass`.

DoD:
- [ ] Plane snapshot exists locally + durably.
- [ ] Blocker rollup is explicit.
- [ ] Runtime budget results are explicit for each sub-phase.
- [ ] `overall_pass` is deterministic.

Blockers:
1. `M7P8-B1`: source snapshot missing/unreadable.
2. `M7P8-B2`: blocker rollup non-empty.
3. `M7P8-B3`: plane snapshot publish failure.
4. `M7P8-B4`: unexplained runtime budget breach.

## 7) Evidence Contract (P8)
Run-scoped:
1. `evidence/runs/<platform_run_id>/rtdl_core/offsets_snapshot.json`
2. `evidence/runs/<platform_run_id>/rtdl_core/caught_up.json`
3. `evidence/runs/<platform_run_id>/rtdl_core/archive_write_summary.json` (when active)

Control-plane:
1. `evidence/dev_min/run_control/<m7_execution_id>/m7_b_rtdl_readiness_snapshot.json`
2. `evidence/dev_min/run_control/<m7_execution_id>/m7_c_rtdl_caught_up_snapshot.json`
3. `evidence/dev_min/run_control/<m7_execution_id>/m7_d_archive_durability_snapshot.json`
4. `evidence/dev_min/run_control/<m7_execution_id>/m7_p8_plane_snapshot.json`

Required metadata fields in each control-plane snapshot:
1. `phase_id`
2. `platform_run_id`
3. `m7_execution_id`
4. `started_at_utc`
5. `completed_at_utc`
6. `elapsed_seconds`
7. `overall_pass`
8. `blockers`

## 8) Completion Checklist (P8)
- [x] P8.A complete
- [x] P8.B complete
- [ ] P8.C complete
- [ ] P8.D complete
- [ ] Runtime budget gates satisfied (or explicitly fail-closed with accepted blockers).
- [ ] Rerun/rollback posture documented for any non-pass lane.

## 9) Exit Criteria (P8)
P8 branch is closure-ready only when:
1. Section 8 checklist is fully complete.
2. Required evidence artifacts exist and are durable.
3. `m7_p8_plane_snapshot.json` has `overall_pass=true`.
4. P8 closure is consumed by `platform.M7.build_plan.md` for M7 rollup.

## 10) Unresolved Blocker Register (P8 Branch)
Current blockers:
1. `M7D-B4` (open, blocks `P8.C` closure)
   - observed posture:
     - `fraud-platform-dev-min-rtdl-core-archive-writer` service is active (`desired=1`) on task definition `:15`,
     - task definition command is now real worker runtime (`python -m fraud_detection.archive_writer.worker --profile config/platform/profiles/dev_min.yaml`),
     - writer is crash-looping (`running=0`, repeated stopped tasks with `exitCode=1`),
     - CloudWatch logs show runtime `AssertionError` in `archive_writer.worker` (`_file_reader is None`).
   - impact:
     - archive durability closure cannot claim active-writer proof because worker runtime is not stable.
   - closure criteria:
     - keep archive-writer service on real worker runtime command (already rematerialized),
     - fix archive-writer runtime crash under Kafka posture (implementation patch is now in repo; requires image rollout),
     - rerun `M7.D` and require `overall_pass=true` with empty blocker rollup.

Rule:
1. Any blocker discovered in `P8.A..P8.D` is appended here with:
   - blocker id,
   - impacted sub-phase,
   - closure criteria.
2. If this register is non-empty, P8 branch cannot be marked closure-ready.
