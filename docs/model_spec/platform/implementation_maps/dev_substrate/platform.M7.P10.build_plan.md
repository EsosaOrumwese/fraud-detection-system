# Dev Substrate Deep Plan - M7.P10 (P10 CASE_LABELS_COMMITTED)
_Status source of truth: `platform.build_plan.md` and `platform.M7.build_plan.md`_
_This document provides plane-deep planning detail for M7 P10._
_Last updated: 2026-02-18_

## 0) Purpose
Close `P10 CASE_LABELS_COMMITTED` with explicit durable proof that case/label lane:
1. runs healthy on managed runtime and managed DB,
2. uses concretely pinned subject-key identity fields,
3. commits append-only + idempotent case/label truth,
4. publishes run-scoped case/label evidence.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (M7 section)
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P10`)
4. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P9.build_plan.md`
2. `runs/dev_substrate/m6/20260216T214025Z/m7_handoff_pack.json`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M7.P10
In scope:
1. Subject-key pin and managed DB readiness closure (`M7.G` lane depth).
2. Case/label commit evidence closure (`M7.H` lane depth).
3. P10 plane-level closure snapshot for M7 orchestrator consumption.

Out of scope:
1. RTDL closure (`P8`).
2. Decision-lane closure (`P9`).
3. Final M7 verdict/handoff (`M7.I`/`M7.J`).

## 3) P10 Deliverables
1. `m7_g_case_label_db_readiness_snapshot.json`.
2. `m7_h_case_label_commit_snapshot.json`.
3. Run-scoped `case_labels/case_summary.json`.
4. Run-scoped `case_labels/label_summary.json`.
5. `m7_p10_plane_snapshot.json` (plane closure summary for orchestrator).

## 4) Execution Gate for This Plane
Current posture:
1. Planning active only.

Execution block:
1. No P10 runtime execution before P9 closure is pass-consumed by M7 orchestrator.
2. No P10 runtime execution with placeholder identity keys.
3. No P10 pass without managed DB readiness proof.

## 4.1) Capability-Lane Matrix (P10)
| Capability lane | Primary step | Minimum PASS evidence |
| --- | --- | --- |
| Identity-key closure | P10.A | subject-key handles pinned and non-placeholder |
| Managed DB readiness | P10.A | DB connectivity/schema/migration posture pass |
| Case/label commit evidence | P10.B | case/label summaries durable |
| Append-only/idempotent writes | P10.B | no duplicate append inflation and no in-place mutation |
| Plane closure | P10.C | `m7_p10_plane_snapshot.json` overall pass true |

## 5) Decision Pins (P10)
1. CM/LS run on ECS-managed runtime only.
2. Operational state is managed DB-backed (no laptop DB/files).
3. Case timelines and label assertions are append-only.
4. Case/label writes are idempotent by stable key composition.
5. Subject-key identity handles must be pinned before commit execution.

## 6) Plane Work Breakdown

### P10.A Subject-Key Pin + Managed DB Readiness (`M7.G` depth)
Goal:
1. Close identity-key and DB readiness prerequisites for P10 commit.

Entry conditions:
1. `P9.C` closure snapshot exists and reports `overall_pass=true`.
2. Active run scope (`platform_run_id`, `m7_execution_id`) is fixed for this lane.

Required inputs:
1. P9 closure pass (via orchestrator gating).
2. Identity handles:
   - `CASE_SUBJECT_KEY_FIELDS`
   - `LABEL_SUBJECT_KEY_FIELDS`.
3. DB handles:
   - `RDS_ENDPOINT`
   - `DB_NAME`
   - `SSM_DB_USER_PATH`
   - `SSM_DB_PASSWORD_PATH`
   - `DB_SECURITY_GROUP_ID`
   - `TD_DB_MIGRATIONS` (if required).
4. Service/runtime handles:
   - `SVC_CASE_TRIGGER`
   - `SVC_CM`
   - `SVC_LS`
   - `ROLE_CASE_LABELS`.
5. Runtime truth anchors for identity composition:
   - `src/fraud_detection/case_mgmt/ids.py` + `config/platform/case_mgmt/taxonomy_v0.yaml`
   - `src/fraud_detection/label_store/ids.py` + `config/platform/label_store/taxonomy_v0.yaml`.

Preparation checks:
1. Confirm `P9.C` source snapshot:
   - `runs/dev_substrate/m7/<m7_execution_id>/m7_p9_plane_snapshot.json`
   - `overall_pass=true`.
2. Confirm identity handles resolve to concrete values (not `<PIN_AT_P10_PHASE_ENTRY>`).
3. Confirm DB secret paths resolve and can be fetched by lane role at runtime.
4. Confirm `CM`/`LS` service handles exist and task definitions resolve.
5. Confirm DB migration lane readiness:
   - if migrations required, `TD_DB_MIGRATIONS` is materialized and executable.

Recommended subject-key pin values (runtime-aligned):
1. `CASE_SUBJECT_KEY_FIELDS = "platform_run_id,event_class,event_id"`
2. `LABEL_SUBJECT_KEY_FIELDS = "platform_run_id,event_id"`
3. These values are recommendations for `M7G-B1` closure and must be explicitly pinned in the handle registry before execution.

Deterministic verification algorithm (P10.A):
1. Resolve `CASE_SUBJECT_KEY_FIELDS` and `LABEL_SUBJECT_KEY_FIELDS`.
2. Fail closed with `M7G-B1` if either value is placeholder or blank.
3. Validate identity composition against runtime truth anchors:
   - case fields exactly match CM deterministic identity constant/taxonomy,
   - label fields exactly match LS deterministic identity constant/taxonomy.
   - any mismatch -> `M7G-B4`.
4. Validate managed DB readiness from managed runtime network (ECS one-shot probe):
   - DB connect success,
   - required schema/table surfaces are present for CM/LS append lanes,
   - migration posture confirmed (`applied` or `not required`).
   - failure -> `M7G-B2`.
5. Validate CM/LS service readiness for P10 entry (two probes):
   - `desired=1`, `running=1`, `pending=0`,
   - no startup crashloop signal in recent events.
   - failure -> `M7G-B5`.
6. Publish `m7_g_case_label_db_readiness_snapshot.json` locally + durably.
7. Compute `overall_pass=true` only when all checks pass and blocker list is empty.

Tasks:
1. Verify subject-key fields are concrete and non-placeholder.
2. Verify DB connectivity and schema readiness.
3. If migrations required, verify migration completion.
4. Publish `m7_g_case_label_db_readiness_snapshot.json`.

Required snapshot fields:
1. `phase`, `phase_id`, `platform_run_id`, `m7_execution_id`.
2. `subject_key_resolution`:
   - resolved handle values,
   - runtime-truth comparison result.
3. `db_readiness`:
   - connectivity result,
   - table/surface checks,
   - migration status.
4. `service_readiness`:
   - CM/LS two-probe posture.
5. `overall_pass`, `blockers`, `elapsed_seconds`.

Runtime budget:
1. `P10.A` target budget: <= 15 minutes wall clock.
2. If exceeded, lane remains fail-closed until explicit USER waiver.

DoD:
- [ ] Subject-key identity handles are pinned and non-placeholder.
- [ ] Managed DB readiness checks pass.
- [ ] Snapshot exists locally + durably.
- [ ] Runtime budget target is met (or explicitly waived).

Blockers:
1. `M7G-B1`: subject-key placeholder unresolved.
2. `M7G-B2`: DB readiness/migration failure.
3. `M7G-B3`: snapshot publish failure.
4. `M7G-B4`: subject-key drift vs runtime truth anchors.
5. `M7G-B5`: CM/LS service readiness failure for P10 entry.

### P10.B Case/Label Commit Closure (`M7.H` depth)
Goal:
1. Publish closure-grade case/label evidence with append-only/idempotent posture checks.

Required inputs:
1. `M7.G` pass snapshot.
2. Service handles:
   - `SVC_CASE_TRIGGER`
   - `SVC_CM`
   - `SVC_LS`.
3. Evidence handles:
   - `CASE_EVIDENCE_PATH_PATTERN`
   - `LABEL_EVIDENCE_PATH_PATTERN`.

Tasks:
1. Verify case-trigger consumption and CM append-only timeline writes.
2. Verify LS append-only label assertion writes.
3. Validate duplicate handling is idempotent (no double-append on replay/duplicates).
4. Publish run-scoped:
   - `case_labels/case_summary.json`
   - `case_labels/label_summary.json`.
5. Publish `m7_h_case_label_commit_snapshot.json`.

DoD:
- [ ] Case summary and label summary exist and are run-scoped.
- [ ] Append-only and idempotency checks pass.
- [ ] Snapshot exists locally + durably.

Blockers:
1. `M7H-B1`: case/label evidence missing or incomplete.
2. `M7H-B2`: append-only/idempotency violation.
3. `M7H-B3`: snapshot publish failure.

### P10.C Plane Closure Summary
Goal:
1. Emit deterministic P10 closure artifact for M7 orchestrator.

Entry conditions:
1. `P10.A` and `P10.B` completed.

Tasks:
1. Roll up blockers from `M7.G..M7.H`.
2. Compute `p10_overall_pass`.
3. Publish `m7_p10_plane_snapshot.json` with:
   - source snapshot refs,
   - subject-key pin evidence,
   - case/label commit counts,
   - blocker rollup,
   - `overall_pass`.

DoD:
- [ ] Plane snapshot exists locally + durably.
- [ ] Blocker rollup is explicit.
- [ ] `overall_pass` is deterministic.

Blockers:
1. `M7P10-B1`: source snapshot missing/unreadable.
2. `M7P10-B2`: blocker rollup non-empty.
3. `M7P10-B3`: plane snapshot publish failure.

## 7) Evidence Contract (P10)
Run-scoped:
1. `evidence/runs/<platform_run_id>/case_labels/case_summary.json`
2. `evidence/runs/<platform_run_id>/case_labels/label_summary.json`

Control-plane:
1. `evidence/dev_min/run_control/<m7_execution_id>/m7_g_case_label_db_readiness_snapshot.json`
2. `evidence/dev_min/run_control/<m7_execution_id>/m7_h_case_label_commit_snapshot.json`
3. `evidence/dev_min/run_control/<m7_execution_id>/m7_p10_plane_snapshot.json`

## 8) Completion Checklist (P10)
- [ ] P10.A complete
- [ ] P10.B complete
- [ ] P10.C complete

## 9) Exit Criteria (P10)
P10 branch is closure-ready only when:
1. Section 8 checklist is fully complete.
2. Required evidence artifacts exist and are durable.
3. `m7_p10_plane_snapshot.json` has `overall_pass=true`.
4. P10 closure is consumed by `platform.M7.build_plan.md` for M7 rollup.
