# Dev Substrate Deep Plan - M7.P9 (P9 DECISION_CHAIN_COMMITTED)
_Status source of truth: `platform.build_plan.md` and `platform.M7.build_plan.md`_
_This document provides plane-deep planning detail for M7 P9._
_Last updated: 2026-02-18_

## 0) Purpose
Close `P9 DECISION_CHAIN_COMMITTED` with explicit durable proof that decision lane:
1. runs healthy on managed runtime,
2. commits decision/action/audit outcomes under idempotency + append-only posture,
3. publishes run-scoped decision-lane evidence suitable for M7 rollup.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (M7 section)
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P9`)
4. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P8.build_plan.md`
2. `runs/dev_substrate/m6/20260216T214025Z/m7_handoff_pack.json`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M7.P9
In scope:
1. Decision-lane readiness and idempotency posture checks (`M7.E` lane depth).
2. Decision/action/audit commit evidence closure (`M7.F` lane depth).
3. P9 plane-level closure snapshot for M7 orchestrator consumption.

Out of scope:
1. RTDL caught-up and archive closure (`P8`).
2. Case/label commit closure (`P10`).
3. Final M7 verdict/handoff (`M7.I`/`M7.J`).

## 3) P9 Deliverables
1. `m7_e_decision_lane_readiness_snapshot.json`.
2. `m7_f_decision_chain_snapshot.json`.
3. Run-scoped `decision_lane/decision_summary.json`.
4. Run-scoped `decision_lane/action_summary.json`.
5. Run-scoped `decision_lane/audit_summary.json`.
6. `m7_p9_plane_snapshot.json` (plane closure summary for orchestrator).

## 4) Execution Gate for This Plane
Current posture:
1. `P9.A` executed and closed PASS under active run scope:
   - local snapshot: `runs/dev_substrate/m7/20260218T141420Z/m7_e_decision_lane_readiness_snapshot.json`
   - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_e_decision_lane_readiness_snapshot.json`
   - `overall_pass=true`, blockers empty.
2. Next lane is `P9.B` (`M7.F`).

Execution block:
1. No P9 runtime execution before P8 closure is pass-consumed by M7 orchestrator.
2. No P9 pass without append-only and idempotency proof.
3. No P9 runtime execution while decision lane services are unhealthy.

## 4.2) Pre-Execution Readiness Matrix (Must Pass Before P9.A Starts)
1. `P8` closure posture:
   - `m7_p8_plane_snapshot.json` exists and `overall_pass=true`.
2. Substrate health/stability:
   - ECS cluster `ACTIVE`.
   - decision-lane services (`DL/DF/AL/DLA`) each at `desired=running=1`.
   - no active crashloop/restart storm in latest service events.
3. Handle and policy closure:
   - `ACTION_IDEMPOTENCY_KEY_FIELDS` is pinned and non-placeholder.
   - `ACTION_OUTCOME_WRITE_POLICY` is pinned to append-only posture.
4. Run-scope continuity:
   - decision-lane tasks expose `REQUIRED_PLATFORM_RUN_ID == platform_run_id`.
   - no run-id mismatch across decision-lane services.
5. Dependency reachability:
   - runtime can read required SSM secrets.
   - managed DB is reachable from decision-lane tasks.
   - Kafka connectivity posture is healthy for required topics.

Fail-closed rule:
1. Any unmet row above blocks `P9.A` execution and must be logged as `M7E-B*`.

## 4.3) Runtime Budget Gates (Performance Law, P9-Specific)
1. `P9.A` budget: 15 minutes max wall clock.
2. `P9.B` budget: 20 minutes max wall clock.
3. `P9.C` budget: 5 minutes max wall clock.
4. Plane budget (`P9.A..P9.C`): 40 minutes max wall clock.

Budget control:
1. Each sub-phase snapshot must include `started_at_utc`, `completed_at_utc`, and `elapsed_seconds`.
2. Any unexplained overrun is fail-closed (`M7P9-B4` at plane layer).

## 4.4) Rerun and Rollback Prep (Must Be Planned Before P9.A)
1. Rerun trigger conditions:
   - decision-lane service instability,
   - idempotency policy mismatch,
   - missing/invalid decision/action/audit summaries.
2. Safe rollback boundaries:
   - do not mutate append-only audit artifacts,
   - only rebuild control snapshots and recomputable summaries.
3. Rerun contract:
   - preserve `platform_run_id`,
   - preserve idempotency keys and write-policy posture,
   - publish fresh control-plane snapshots under the same `m7_execution_id`.

## 4.6) P9.B Pre-Execution Readiness Matrix (Must Pass Before P9.B Starts)
1. `P9.A` closure posture:
   - `m7_e_decision_lane_readiness_snapshot.json` exists and `overall_pass=true`.
2. Decision-lane runtime stability:
   - `DL/DF/AL/DLA` remain `desired=1`, `running=1`, no active restart storm.
3. Evidence handle closure:
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN` resolves non-placeholder.
   - `DLA_EVIDENCE_PATH_PATTERN` resolves non-placeholder.
   - `S3_EVIDENCE_BUCKET` and `S3_EVIDENCE_RUN_ROOT_PATTERN` resolve non-placeholder.
4. Policy/invariant closure:
   - `ACTION_IDEMPOTENCY_KEY_FIELDS` and `ACTION_OUTCOME_WRITE_POLICY` remain pinned and unchanged from `P9.A`.
5. Input lane continuity:
   - required decision-lane source topics (`FP_BUS_RTDL_V1`, `FP_BUS_AUDIT_V1`) remain reachable.
6. Evidence write posture:
   - run-scoped evidence prefix for `platform_run_id` is writable by decision-lane role.

Fail-closed rule:
1. Any unmet row above blocks `P9.B` execution and must be logged as `M7F-B*`.

## 4.7) P9.B Deterministic Verification Algorithm (Pinned)
1. Source checks:
   - load `M7.E` pass snapshot.
   - assert all required handles resolve to concrete values.
2. Evidence presence checks:
   - verify run-scoped objects exist:
     - `decision_lane/decision_summary.json`
     - `decision_lane/action_summary.json`
     - `decision_lane/audit_summary.json`.
3. Run-scope checks:
   - each summary must declare `platform_run_id` matching active run.
4. Append-only checks:
   - audit summary indicates append-only posture (no overwrite/mutation signal).
5. Idempotency checks:
   - action summary indicates idempotent outcome posture and duplicate-safe behavior.
6. Snapshot assembly:
   - compute blocker rollup and publish `m7_f_decision_chain_snapshot.json` locally and durably.

## 4.5) Capability-Lane Matrix (P9)
| Capability lane | Primary step | Minimum PASS evidence |
| --- | --- | --- |
| Decision-lane readiness | P9.A | DL/DF/AL/DLA healthy with stable desired/running posture |
| Idempotency posture | P9.A | key/write-policy checks pass |
| Commit evidence | P9.B | decision/action/audit summaries durable |
| Append-only audit truth | P9.B | no overwrite/mutation posture verified |
| Plane closure | P9.C | `m7_p9_plane_snapshot.json` overall pass true |

## 5) Decision Pins (P9)
1. Decision lane runs on ECS-managed runtime only.
2. Audit truth is append-only.
3. Action outcomes are idempotent using pinned key fields.
4. Missing decision/audit evidence is fail-closed.
5. Degrade posture must be explicit in evidence where applied.

## 6) Plane Work Breakdown

### P9.A Readiness + Idempotency Posture (`M7.E` depth)
Goal:
1. Prove decision-lane services are healthy and idempotency posture is pinned at runtime.

Entry conditions:
1. `P8` plane snapshot exists and `overall_pass=true`.
2. Section 4.2 readiness matrix is fully satisfied.

Required inputs:
1. P8 closure pass (via orchestrator gating).
2. Service handles:
   - `SVC_DECISION_LANE_DL`
   - `SVC_DECISION_LANE_DF`
   - `SVC_DECISION_LANE_AL`
   - `SVC_DECISION_LANE_DLA`.
3. Idempotency handles:
   - `ACTION_IDEMPOTENCY_KEY_FIELDS`
   - `ACTION_OUTCOME_WRITE_POLICY`.
4. Role/IAM handle:
   - `ROLE_DECISION_LANE`.

Preparation checks:
1. Confirm two consecutive ECS probes for each decision-lane service with no churn.
2. Confirm runtime env includes run-scope guard (`REQUIRED_PLATFORM_RUN_ID`) on all four services.
3. Confirm idempotency and append-only policy values resolve from handles registry without placeholder/default drift.
4. Confirm upstream RTDL evidence exists and is pass-consumed (`rtdl_core/caught_up.json`, `m7_p8_plane_snapshot.json`).

Tasks:
1. Verify decision-lane services healthy (`desired=1`, `running=1`, no crashloop).
2. Verify idempotency key and append-only outcome policy posture.
3. Verify required input flow from RTDL lane exists.
4. Publish `m7_e_decision_lane_readiness_snapshot.json`.
5. Publish local + durable snapshot.

Required snapshot fields:
1. `phase_id`, `platform_run_id`, `m7_execution_id`.
2. `started_at_utc`, `completed_at_utc`, `elapsed_seconds`.
3. service posture table (`DL/DF/AL/DLA`) with desired/running/pending and task definition refs.
4. resolved `ACTION_IDEMPOTENCY_KEY_FIELDS` and `ACTION_OUTCOME_WRITE_POLICY`.
5. run-scope consistency summary and upstream-flow assertion.
6. `overall_pass` and `blockers`.

DoD:
- [x] Decision-lane readiness checks pass.
- [x] Idempotency/append-only posture checks pass.
- [x] Snapshot exists locally + durably.

Blocker Codes (Taxonomy):
1. `M7E-B1`: decision-lane service unhealthy.
2. `M7E-B2`: idempotency/write-policy mismatch.
3. `M7E-B3`: no valid upstream input flow.
4. `M7E-B4`: snapshot publish failure.
5. `M7E-B5`: run-scope mismatch across decision-lane services.
6. `M7E-B6`: dependency reachability failure (DB/SSM/Kafka).

Execution notes:
1. `P9.A` first probe window failed fail-closed during rollout churn (`M7E-B1` on all four services).
2. Services stabilized on task definition `:14` with pinned digest `sha256:956fbd1ca609fb6b996cb05f60078b1fb88e93520f73e69a5eb51241654a80ff`.
3. Re-execution closed PASS:
   - `DL/DF/AL/DLA` all `desired=1`, `running=1`, `pending=0` on two consecutive probes.
   - `REQUIRED_PLATFORM_RUN_ID` matched `platform_20260213T214223Z` for all services.
   - idempotency/write-policy handles resolved and matched pinned values:
     - `ACTION_IDEMPOTENCY_KEY_FIELDS=platform_run_id,event_id,action_type`
     - `ACTION_OUTCOME_WRITE_POLICY=append_only`.
   - dependency reachability (`ECS/RDS/SSM/Kafka`) and upstream `P8` consumption checks all passed.

### P9.B Decision/Action/Audit Commit Closure (`M7.F` depth)
Goal:
1. Publish closure-grade P9 evidence under run scope.

Entry conditions:
1. `M7.E` pass snapshot exists and `overall_pass=true`.
2. Section 4.6 readiness matrix is fully satisfied.

Required inputs:
1. `M7.E` pass snapshot.
2. Evidence handles:
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
   - `DLA_EVIDENCE_PATH_PATTERN`.
3. Evidence root handles:
   - `S3_EVIDENCE_BUCKET`
   - `S3_EVIDENCE_RUN_ROOT_PATTERN`.
4. Topic handles:
   - `FP_BUS_RTDL_V1`
   - `FP_BUS_AUDIT_V1`.
5. Invariant handles:
   - `ACTION_IDEMPOTENCY_KEY_FIELDS`
   - `ACTION_OUTCOME_WRITE_POLICY`.

Preparation checks:
1. Confirm `DL/DF/AL/DLA` remain healthy/stable at execution start.
2. Confirm `M7.E` snapshot run-scope matches active run.
3. Confirm required decision/audit evidence path handles resolve non-placeholder.
4. Confirm evidence bucket run prefix is writable.

Tasks:
1. Materialize and verify run-scoped:
   - `decision_lane/decision_summary.json`
   - `decision_lane/action_summary.json`
   - `decision_lane/audit_summary.json`.
2. Validate run-scope coherence (`platform_run_id` consistency across all three summaries).
3. Validate append-only audit posture.
4. Validate idempotent action-outcome posture (duplicate-safe).
5. Publish `m7_f_decision_chain_snapshot.json` with deterministic blocker rollup.
6. Publish local + durable snapshot.

Required snapshot fields:
1. `phase_id`, `platform_run_id`, `m7_execution_id`.
2. `started_at_utc`, `completed_at_utc`, `elapsed_seconds`.
3. required evidence URIs and existence flags.
4. run-scope coherence summary.
5. append-only/idempotency validation summary.
6. `overall_pass` and `blockers`.

DoD:
- [x] Required P9 evidence artifacts exist and are run-scoped.
- [x] Append-only and idempotency checks pass.
- [x] Snapshot exists locally + durably.
- [x] Runtime budget gate (`P9.B <= 20 min`) is met or explicitly fail-closed.

Blocker Codes (Taxonomy):
1. `M7F-B1`: required evidence missing/incomplete.
2. `M7F-B2`: append-only/idempotency violation detected.
3. `M7F-B3`: snapshot publish failure.
4. `M7F-B4`: decision-lane service unstable during P9.B execution window.
5. `M7F-B5`: run-scope mismatch across decision/action/audit artifacts.
6. `M7F-B6`: dependency reachability failure (Kafka/DB/SSM/S3 evidence write).

Execution result (`2026-02-18`, fail-closed baseline):
1. Artifacts were materialized locally + durably:
   - `runs/dev_substrate/m7/20260218T141420Z/decision_lane/decision_summary.json`
   - `runs/dev_substrate/m7/20260218T141420Z/decision_lane/action_summary.json`
   - `runs/dev_substrate/m7/20260218T141420Z/decision_lane/audit_summary.json`
   - `runs/dev_substrate/m7/20260218T141420Z/m7_f_decision_chain_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/decision_lane/decision_summary.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/decision_lane/action_summary.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/decision_lane/audit_summary.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_f_decision_chain_snapshot.json`
2. `overall_pass=false` with explicit blockers:
   - `M7F-B1`: non-zero admitted traffic basis (`traffic_fraud=400`) but zero run-scoped records on `FP_BUS_RTDL_V1`.
   - `M7F-B1`: non-zero admitted traffic basis (`traffic_fraud=400`) but zero run-scoped records on `FP_BUS_AUDIT_V1`.
   - `M7F-B2`: idempotent action-outcome posture not provable (`action outcomes = 0`).
3. Decision-lane service stability was re-probed during execution; services held `desired=1,running=1,pending=0`, but data-plane production remained empty for run scope.

Execution rerun (`2026-02-18`, closure PASS):
1. Root-cause closure applied before rerun:
   - `decision-lane-dla` task definition drifted to probe image (`busybox`) and could not execute Python worker/runtime intake.
   - DLA was rematerialized to platform image (`fraud-platform-dev-min@sha256:37fb5180c93f1079b0ea56ba4310d07e04a9acca8bc4f1c499dc27d931e7a16e`) and service stabilized on `:24`.
2. Run-scoped non-zero decision/audit/action evidence restored and republished:
   - `decision_summary`: `decisions=200`
   - `action_summary`: `intents=200`, `outcomes=200`
   - `audit_summary`: `audit_records=600`, `quarantine_records=0`
3. Rerun control snapshot:
   - local: `runs/dev_substrate/m7/20260218T141420Z/m7_f_decision_chain_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_f_decision_chain_snapshot.json`
   - result: `overall_pass=true`, blockers empty.

### P9.C Plane Closure Summary
Goal:
1. Emit deterministic P9 closure artifact for M7 orchestrator.

Entry conditions:
1. `P9.A` and `P9.B` completed.

Required inputs:
1. `m7_e_decision_lane_readiness_snapshot.json` (`overall_pass` + blocker list).
2. `m7_f_decision_chain_snapshot.json` (`overall_pass` + blocker list + counts).
3. Active control artifact destination:
   - `evidence/dev_min/run_control/<m7_execution_id>/m7_p9_plane_snapshot.json`.

Preparation checks:
1. Source snapshots are readable locally and durably.
2. Source `platform_run_id` and `m7_execution_id` match.
3. Source snapshots are from the same execution epoch (`m7_20260218T141420Z`).

Deterministic rollup algorithm:
1. Roll up blockers = concatenation of source blockers from `M7.E` and `M7.F`.
2. Set `p9_overall_pass=true` only when:
   - both source snapshots have `overall_pass=true`, and
   - rolled-up blocker list is empty.
3. Budget summary:
   - carry forward elapsed seconds from sources,
   - compute `p9_elapsed_total_seconds = m7e_elapsed_seconds + m7f_elapsed_seconds`.
4. Any source read failure or mismatch materializes blocker `M7P9-B1`.

Tasks:
1. Roll up blockers from `M7.E..M7.F`.
2. Compute `p9_overall_pass`.
3. Publish `m7_p9_plane_snapshot.json` with:
   - source snapshot refs,
   - decision/action/audit counts,
   - idempotency posture summary,
   - blocker rollup,
   - `overall_pass`.

DoD:
- [x] Plane snapshot exists locally + durably.
- [x] Blocker rollup is explicit.
- [x] `overall_pass` is deterministic.

Blocker Codes (Taxonomy):
1. `M7P9-B1`: source snapshot missing/unreadable.
2. `M7P9-B2`: blocker rollup non-empty.
3. `M7P9-B3`: plane snapshot publish failure.

Execution result (`2026-02-19`):
1. Plane snapshot published:
   - local: `runs/dev_substrate/m7/20260218T141420Z/m7_p9_plane_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_p9_plane_snapshot.json`
2. Rollup outcome:
   - source snapshots: `M7.E=PASS`, `M7.F=PASS`
   - blocker rollup: empty
   - `p9_overall_pass=true`
3. Count rollup (from `P9.B` snapshot):
   - decisions `200`
   - action intents `200`
   - action outcomes `200`
   - audit records `600`
4. Plane closure snapshot:
   - local: `runs/dev_substrate/m7/20260218T141420Z/m7_p9_plane_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_p9_plane_snapshot.json`
   - `overall_pass=true`, blockers empty.

## 7) Evidence Contract (P9)
Run-scoped:
1. `evidence/runs/<platform_run_id>/decision_lane/decision_summary.json`
2. `evidence/runs/<platform_run_id>/decision_lane/action_summary.json`
3. `evidence/runs/<platform_run_id>/decision_lane/audit_summary.json`

Control-plane:
1. `evidence/dev_min/run_control/<m7_execution_id>/m7_e_decision_lane_readiness_snapshot.json`
2. `evidence/dev_min/run_control/<m7_execution_id>/m7_f_decision_chain_snapshot.json`
3. `evidence/dev_min/run_control/<m7_execution_id>/m7_p9_plane_snapshot.json`

## 8) Completion Checklist (P9)
- [x] P9.A complete
- [x] P9.B complete
- [x] P9.C complete
- [x] Runtime budget gates satisfied (or explicitly fail-closed with accepted blockers).
- [x] Rerun/rollback posture documented for any non-pass lane.

## 9) Exit Criteria (P9)
P9 branch is closure-ready only when:
1. Section 8 checklist is fully complete.
2. Required evidence artifacts exist and are durable.
3. `m7_p9_plane_snapshot.json` has `overall_pass=true`.
4. P9 closure is consumed by `platform.M7.build_plan.md` for M7 rollup.

## 10) Unresolved Blocker Register (P9 Branch)
Current blockers:
1. none (`M7F-B1` and `M7F-B2` were closed by rerun with `overall_pass=true`).

Rule:
1. Any blocker discovered in `P9.A..P9.C` is appended here with:
   - blocker id,
   - impacted sub-phase,
   - closure criteria.
2. If this register is non-empty, P9 branch cannot be marked closure-ready.

