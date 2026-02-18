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
1. Planning active only.

Execution block:
1. No P9 runtime execution before P8 closure is pass-consumed by M7 orchestrator.
2. No P9 pass without append-only and idempotency proof.
3. No P9 runtime execution while decision lane services are unhealthy.

## 4.1) Capability-Lane Matrix (P9)
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

Tasks:
1. Verify decision-lane services healthy (`desired=1`, `running=1`, no crashloop).
2. Verify idempotency key and append-only outcome policy posture.
3. Verify required input flow from RTDL lane exists.
4. Publish `m7_e_decision_lane_readiness_snapshot.json`.

DoD:
- [ ] Decision-lane readiness checks pass.
- [ ] Idempotency/append-only posture checks pass.
- [ ] Snapshot exists locally + durably.

Blockers:
1. `M7E-B1`: decision-lane service unhealthy.
2. `M7E-B2`: idempotency/write-policy mismatch.
3. `M7E-B3`: no valid upstream input flow.
4. `M7E-B4`: snapshot publish failure.

### P9.B Decision/Action/Audit Commit Closure (`M7.F` depth)
Goal:
1. Publish closure-grade P9 evidence under run scope.

Required inputs:
1. `M7.E` pass snapshot.
2. Evidence handles:
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
   - `DLA_EVIDENCE_PATH_PATTERN`.

Tasks:
1. Build run-scoped:
   - `decision_lane/decision_summary.json`
   - `decision_lane/action_summary.json`
   - `decision_lane/audit_summary.json`.
2. Validate append-only audit posture.
3. Validate idempotent action-outcome posture (duplicate-safe).
4. Publish `m7_f_decision_chain_snapshot.json`.

DoD:
- [ ] Required P9 evidence artifacts exist and are run-scoped.
- [ ] Append-only and idempotency checks pass.
- [ ] Snapshot exists locally + durably.

Blockers:
1. `M7F-B1`: required evidence missing/incomplete.
2. `M7F-B2`: append-only/idempotency violation detected.
3. `M7F-B3`: snapshot publish failure.

### P9.C Plane Closure Summary
Goal:
1. Emit deterministic P9 closure artifact for M7 orchestrator.

Entry conditions:
1. `P9.A` and `P9.B` completed.

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
- [ ] Plane snapshot exists locally + durably.
- [ ] Blocker rollup is explicit.
- [ ] `overall_pass` is deterministic.

Blockers:
1. `M7P9-B1`: source snapshot missing/unreadable.
2. `M7P9-B2`: blocker rollup non-empty.
3. `M7P9-B3`: plane snapshot publish failure.

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
- [ ] P9.A complete
- [ ] P9.B complete
- [ ] P9.C complete

## 9) Exit Criteria (P9)
P9 branch is closure-ready only when:
1. Section 8 checklist is fully complete.
2. Required evidence artifacts exist and are durable.
3. `m7_p9_plane_snapshot.json` has `overall_pass=true`.
4. P9 closure is consumed by `platform.M7.build_plan.md` for M7 rollup.
