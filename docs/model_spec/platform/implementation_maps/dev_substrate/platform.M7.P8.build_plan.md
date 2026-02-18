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
1. Planning active only.

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

## 5) Decision Pins (P8)
1. RTDL runs on ECS-managed runtime only.
2. Official P8 consumption begins only after M6/P7 pass.
3. Offset commit posture is `commit_after_durable_write`.
4. Caught-up threshold is governed by `RTDL_CAUGHT_UP_LAG_MAX`.
5. Archive proof must be explicit: active writer summary or explicit inactive-writer declaration.
6. Any missing required evidence is fail-closed.

## 6) Plane Work Breakdown

### P8.A Readiness + Consumer Posture (`M7.B` depth)
Goal:
1. Prove RTDL services and dependencies are execution-ready.

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

Tasks:
1. Verify services healthy (`desired=1`, `running=1`, no crashloop).
2. Verify consumer-group identity and commit policy posture.
3. Verify dependency reachability (Kafka/S3/DB/logging).
4. Publish `m7_b_rtdl_readiness_snapshot.json`.

DoD:
- [ ] RTDL readiness checks pass.
- [ ] Consumer posture checks pass.
- [ ] Snapshot exists locally + durably.

Blockers:
1. `M7B-B1`: RTDL service unhealthy.
2. `M7B-B2`: consumer posture mismatch.
3. `M7B-B3`: dependency reachability failure.
4. `M7B-B4`: snapshot publish failure.

### P8.B Offsets + Caught-Up Closure (`M7.C` depth)
Goal:
1. Close lag/offset gate with replay-grade evidence.

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

Tasks:
1. Build run-window offsets for required topics/partitions.
2. Verify lag <= `RTDL_CAUGHT_UP_LAG_MAX` (or end-offset reached where applicable).
3. Publish run-scoped:
   - `rtdl_core/offsets_snapshot.json`
   - `rtdl_core/caught_up.json`.
4. Publish `m7_c_rtdl_caught_up_snapshot.json`.

DoD:
- [ ] Offsets snapshot complete.
- [ ] Caught-up threshold satisfied.
- [ ] Snapshot exists locally + durably.

Blockers:
1. `M7C-B1`: offsets evidence missing/incomplete.
2. `M7C-B2`: lag threshold unmet.
3. `M7C-B3`: run-scope mismatch.
4. `M7C-B4`: snapshot publish failure.

### P8.C Archive Durability Closure (`M7.D` depth)
Goal:
1. Prove archive durability surface for active writer posture.

Required inputs:
1. `M7.C` pass snapshot.
2. Archive handles:
   - `S3_ARCHIVE_BUCKET`
   - `S3_ARCHIVE_RUN_PREFIX_PATTERN`
   - `S3_ARCHIVE_EVENTS_PREFIX_PATTERN`.

Tasks:
1. If archive writer is active:
   - verify archive prefix has run-scoped objects,
   - verify archive progression coherence with offsets.
2. If archive writer is inactive by design:
   - emit explicit inactive-writer rationale in snapshot.
3. Publish run-scoped `rtdl_core/archive_write_summary.json` when active.
4. Publish `m7_d_archive_durability_snapshot.json`.

DoD:
- [ ] Archive durability posture is explicit and evidenced.
- [ ] Active-writer case includes archive summary.
- [ ] Snapshot exists locally + durably.

Blockers:
1. `M7D-B1`: expected archive proof missing.
2. `M7D-B2`: archive/offset coherence failure.
3. `M7D-B3`: snapshot publish failure.

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
   - blocker rollup,
   - `overall_pass`.

DoD:
- [ ] Plane snapshot exists locally + durably.
- [ ] Blocker rollup is explicit.
- [ ] `overall_pass` is deterministic.

Blockers:
1. `M7P8-B1`: source snapshot missing/unreadable.
2. `M7P8-B2`: blocker rollup non-empty.
3. `M7P8-B3`: plane snapshot publish failure.

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

## 8) Completion Checklist (P8)
- [ ] P8.A complete
- [ ] P8.B complete
- [ ] P8.C complete
- [ ] P8.D complete

## 9) Exit Criteria (P8)
P8 branch is closure-ready only when:
1. Section 8 checklist is fully complete.
2. Required evidence artifacts exist and are durable.
3. `m7_p8_plane_snapshot.json` has `overall_pass=true`.
4. P8 closure is consumed by `platform.M7.build_plan.md` for M7 rollup.
