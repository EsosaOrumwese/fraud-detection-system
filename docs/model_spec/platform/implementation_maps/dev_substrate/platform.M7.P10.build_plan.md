# Dev Substrate Deep Plan - M7.P10 (P10 CASE_LABELS_COMMITTED)
_Status source of truth: `platform.build_plan.md` and `platform.M7.build_plan.md`_
_This document provides plane-deep planning detail for M7 P10._
_Last updated: 2026-02-19_

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
1. `P10.A` rerun is pass-closed (`overall_pass=true`); `P10.B`/`P10.C` not started.

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
- [x] Subject-key identity handles are pinned and non-placeholder.
- [x] Managed DB readiness checks pass.
- [x] Snapshot exists locally + durably.
- [x] Runtime budget target is met (or explicitly waived).

Blocker Codes (Taxonomy):
1. `M7G-B1`: subject-key placeholder unresolved.
2. `M7G-B2`: DB readiness/migration failure.
3. `M7G-B3`: snapshot publish failure.
4. `M7G-B4`: subject-key drift vs runtime truth anchors.
5. `M7G-B5`: CM/LS service readiness failure for P10 entry.

Execution notes (`2026-02-19`):
1. `P10.A` snapshot published:
   - local: `runs/dev_substrate/m7/20260218T141420Z/m7_g_case_label_db_readiness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_g_case_label_db_readiness_snapshot.json`
2. Subject-key closure is now green:
   - `CASE_SUBJECT_KEY_FIELDS=platform_run_id,event_class,event_id`
   - `LABEL_SUBJECT_KEY_FIELDS=platform_run_id,event_id`
3. Initial fail-closed blockers from live runtime truth:
   - `M7G-B2`: DB readiness/migration proof not materialized (CM/LS + DB migrations task definitions still stub commands).
   - `M7G-B5`: CM/LS service runtime command conformance failed (scheduler healthy but sleep-loop stubs).
4. Remediation rerun closure:
   - CM/LS rematerialized to real worker runtime (`fraud-platform-dev-min-case-mgmt:14`, `fraud-platform-dev-min-label-store:14`).
   - DB migrations rematerialized to one-shot managed runtime proof (`fraud-platform-dev-min-db-migrations:13`).
   - one-shot task `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/d51d7efc8c274152920aad1ceb029b44` exited `0` with log evidence `db_migrations_ok tables=5`.
   - rerun snapshot verdict is now `overall_pass=true` with blocker list empty.

#### M7.G Remediation Plan (`M7G-B2` + `M7G-B5`) Before Rerun
Goal:
1. Rematerialize CM/LS + DB-migrations to real worker/runtime DB posture and rerun `P10.A` to PASS.

Pinned execution posture:
1. No local-compute substitute for managed DB proof.
2. No planner drift: execute this subsection sequentially and fail-closed at each gate.
3. Keep run scope fixed:
   - `platform_run_id=platform_20260213T214223Z`
   - `m7_execution_id=m7_20260218T141420Z`.

Required handles (must resolve before apply):
1. `SVC_CM`, `SVC_LS`, `SVC_CASE_TRIGGER`, `TD_DB_MIGRATIONS`.
2. `RDS_ENDPOINT`, `DB_NAME`, `DB_SECURITY_GROUP_ID`.
3. `SSM_DB_USER_PATH`, `SSM_DB_PASSWORD_PATH` (and `SSM_DB_DSN_PATH` if used by runtime).
4. `ROLE_CASE_LABELS`, `ROLE_DB_MIGRATIONS` (or equivalent task role binding for migration task).

Execution steps:
1. Runtime command conformance pin:
   - replace CM/LS task-definition stub commands with real worker commands for `case_mgmt` and `label_store`.
   - require DB config/env/secrets to be present on CM/LS task definitions.
2. Migration lane conformance pin:
   - replace `TD_DB_MIGRATIONS` stub command with real migrations entrypoint/command.
   - require migration task role has DB + secret read permissions required for execution.
3. Rematerialization rollout:
   - apply targeted infra changes for:
     - `fraud-platform-dev-min-case-mgmt`,
     - `fraud-platform-dev-min-label-store`,
     - `fraud-platform-dev-min-db-migrations`.
   - wait for CM/LS steady-state on new task-definition revisions.
4. Managed DB proof (required before rerun):
   - run DB migrations one-shot task and require successful exit.
   - verify migration/schema readiness from managed runtime lane (not laptop substitute).
5. Service readiness proof:
   - run two-probe CM/LS checks (`desired=1`, `running=1`, `pending=0`) on rematerialized task definitions.
   - verify no startup crashloop signal in recent ECS events.
6. `P10.A` rerun:
   - republish `m7_g_case_label_db_readiness_snapshot.json` local + durable.
   - require `overall_pass=true` with blocker list empty.

Remediation DoD:
- [x] CM/LS task definitions run real worker commands (no sleep-loop stubs).
- [x] CM/LS task definitions include DB-ready env/secrets posture.
- [x] `TD_DB_MIGRATIONS` runs real migration command and completes successfully.
- [x] Managed DB connect + schema readiness are proven from managed runtime lane.
- [x] `P10.A` rerun snapshot is green (`overall_pass=true`).

Remediation blockers:
1. `M7G-R1`: CM/LS command/env conformance patch not materialized.
2. `M7G-R2`: DB migration task command/role/secret posture invalid.
3. `M7G-R3`: targeted rematerialization apply failed.
4. `M7G-R4`: migration run failed or schema proof missing.
5. `M7G-R5`: CM/LS two-probe readiness failed after rematerialization.
6. `M7G-R6`: `P10.A` rerun snapshot publish failed.

### P10.B Case/Label Commit Closure (`M7.H` depth)
Goal:
1. Publish closure-grade case/label evidence with append-only/idempotent posture checks.

Entry conditions:
1. `P10.A` snapshot exists and reports `overall_pass=true`.
2. Active run scope is fixed:
   - `platform_run_id=platform_20260213T214223Z`
   - `m7_execution_id=m7_20260218T141420Z`.
3. `CM`/`LS` services are on non-stub runtime task definitions and scheduler-healthy.

Required inputs:
1. `M7.G` pass snapshot.
2. Service handles:
   - `SVC_CASE_TRIGGER`
   - `SVC_CM`
   - `SVC_LS`.
3. Evidence handles:
   - `CASE_EVIDENCE_PATH_PATTERN`
   - `LABEL_EVIDENCE_PATH_PATTERN`.
4. Identity/policy anchors:
   - `CASE_SUBJECT_KEY_FIELDS`
   - `LABEL_SUBJECT_KEY_FIELDS`
   - `ACTION_IDEMPOTENCY_KEY_FIELDS` (from P9 lane)
   - `config/platform/case_mgmt/taxonomy_v0.yaml`
   - `config/platform/label_store/taxonomy_v0.yaml`
   - `config/platform/case_mgmt/label_emission_policy_v0.yaml`.
5. Runtime truth anchors:
   - `src/fraud_detection/case_mgmt/ids.py`
   - `src/fraud_detection/label_store/ids.py`.

Preparation checks:
1. Confirm `M7.G` pass source snapshot:
   - `runs/dev_substrate/m7/<m7_execution_id>/m7_g_case_label_db_readiness_snapshot.json`
   - `overall_pass=true`.
2. Confirm case/label service handles resolve to concrete ECS services.
3. Confirm evidence handles resolve to concrete run-scoped durable paths.
4. Confirm no unresolved blockers are carried from `M7.G`.

Deterministic verification algorithm (P10.B):
1. Read `M7.G` pass snapshot and fail closed if not pass (`M7H-B4`).
2. Perform two-probe service checks for `case-trigger`, `case-mgmt`, and `label-store`:
   - each probe requires `desired=1`, `running=1`, `pending=0`,
   - task definitions must be non-stub worker commands.
   - failures -> `M7H-B5`.
3. Build run-scoped evidence summaries:
   - `case_labels/case_summary.json`
   - `case_labels/label_summary.json`.
4. Validate summary completeness:
   - required fields present, non-null, and scoped to active `platform_run_id`,
   - durable object existence confirmed at run-scoped evidence paths.
   - failures -> `M7H-B1`.
5. Validate append-only posture:
   - no in-place mutation indicators in summary proofs,
   - append counters/history markers are monotonic for this run.
   - failures -> `M7H-B2`.
6. Validate idempotency posture:
   - duplicate/replay suppression counters are present,
   - no duplicate inflation in deterministic identity counts (`case_timeline_event_id`, `label_assertion_id`) for run scope.
   - failures -> `M7H-B2`.
7. Validate case-to-label coherence:
   - if run-scoped case commits are non-zero, label summary must be coherent with label-emission policy posture (no orphan label assertions).
   - failures -> `M7H-B6`.
8. Emit `m7_h_case_label_commit_snapshot.json` and publish local + durable.
9. Compute `overall_pass=true` only when blocker list is empty.

Tasks:
1. Verify case-trigger consumption and CM append-only timeline writes.
2. Verify LS append-only label assertion writes.
3. Validate duplicate handling is idempotent (no double-append on replay/duplicates).
4. Publish run-scoped:
   - `case_labels/case_summary.json`
   - `case_labels/label_summary.json`.
5. Publish `m7_h_case_label_commit_snapshot.json`.

Required snapshot fields:
1. `phase`, `phase_id`, `platform_run_id`, `m7_execution_id`.
2. `m7g_dependency`:
   - source snapshot path,
   - `overall_pass` carry-forward flag.
3. `service_readiness`:
   - two-probe ECS posture for `case-trigger`, `case-mgmt`, `label-store`,
   - runtime command conformance summary.
4. `case_summary` and `label_summary`:
   - durable URIs,
   - key counts,
   - run-scope conformance flags.
5. `append_only_checks`:
   - mutation/drift indicators,
   - monotonicity check outputs.
6. `idempotency_checks`:
   - duplicate suppression counters,
   - deterministic identity inflation checks.
7. `overall_pass`, `blockers`, `elapsed_seconds`.

Runtime budget:
1. `P10.B` target budget: <= 20 minutes wall clock.
2. If exceeded, lane remains fail-closed until explicit USER waiver.

DoD:
- [x] Case summary and label summary exist and are run-scoped.
- [x] Append-only and idempotency checks pass.
- [x] Snapshot exists locally + durably.
- [x] Runtime budget target is met (or explicitly waived).

Blocker Codes (Taxonomy):
1. `M7H-B1`: case/label evidence missing or incomplete.
2. `M7H-B2`: append-only/idempotency violation.
3. `M7H-B3`: snapshot publish failure.
4. `M7H-B4`: missing/non-pass `M7.G` dependency.
5. `M7H-B5`: case-label lane service readiness/runtime conformance failure.
6. `M7H-B6`: case-to-label coherence failure for run scope.

Execution closure (`2026-02-19`):
1. Runtime blocker root cause was pinned and corrected:
   - `case-mgmt` Kafka intake was stripping envelope fields in `_read_kafka`, preventing `event_type=case_trigger` recognition.
   - fixed in `src/fraud_detection/case_mgmt/worker.py` and rematerialized to managed image digest `sha256:126d604ebc6a3e1ffe7bed9754a6c0ef718132559c3c277bce96c23685af3165`.
2. Managed catch-up executed (no local compute):
   - case lane one-shot processed `593` records to close durable commit surfaces.
3. Closure evidence:
   - local:
     - `runs/dev_substrate/m7/20260218T141420Z/case_labels/case_summary.json`
     - `runs/dev_substrate/m7/20260218T141420Z/case_labels/label_summary.json`
     - `runs/dev_substrate/m7/20260218T141420Z/m7_h_case_label_commit_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/case_labels/case_summary.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/case_labels/label_summary.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_h_case_label_commit_snapshot.json`
4. Snapshot verdict:
   - `overall_pass=true`
   - blockers empty
   - run-scoped counts:
     - `cm_cases=200`, `cm_case_trigger_intake=200`, `cm_case_timeline=600`
     - `ls_label_assertions=200`, `ls_label_timeline=200`
     - `ct_publish_admit_total=200`, `ct_publish_ambiguous_total=0`

### P10.C Plane Closure Summary (`M7.I` depth)
Goal:
1. Emit deterministic P10 closure artifact for M7 orchestrator.
2. Provide machine-checkable P10 predicate posture for M7 verdict rollup.

Entry conditions:
1. `P10.A` snapshot exists and reports `overall_pass=true`.
2. `P10.B` snapshot exists and reports `overall_pass=true`.
3. Active run scope is fixed:
   - `platform_run_id=platform_20260213T214223Z`
   - `m7_execution_id=m7_20260218T141420Z`.

Required inputs:
1. `runs/dev_substrate/m7/<m7_execution_id>/m7_g_case_label_db_readiness_snapshot.json`
2. `runs/dev_substrate/m7/<m7_execution_id>/m7_h_case_label_commit_snapshot.json`
3. `runs/dev_substrate/m7/<m7_execution_id>/m7_p8_plane_snapshot.json`
4. `runs/dev_substrate/m7/<m7_execution_id>/m7_p9_plane_snapshot.json`
5. Durable roots:
   - `evidence/dev_min/run_control/<m7_execution_id>/...`
   - `evidence/runs/<platform_run_id>/...`

Preparation checks:
1. Ensure all source snapshots are readable (local preferred, durable fallback if needed).
2. Verify each source snapshot carries the active `platform_run_id` and `m7_execution_id`.
3. Verify each source snapshot has `overall_pass` field and blocker list contract.

Deterministic verification algorithm (P10.C):
1. Load source snapshots (`P8`, `P9`, `P10.A`, `P10.B`); missing/unreadable -> `M7P10-B1`.
2. Verify run-scope conformance across all snapshots (`platform_run_id`, `m7_execution_id`); mismatch -> `M7P10-B4`.
3. Evaluate required predicate booleans:
   - `p8_rtdl_caught_up = m7_p8_plane_snapshot.overall_pass`
   - `p9_decision_chain_committed = m7_p9_plane_snapshot.overall_pass`
   - `p10_case_labels_committed = m7_h_case_label_commit_snapshot.overall_pass`.
4. If any required predicate is false -> `M7P10-B2`.
5. Roll up blockers from source snapshots into a deterministic ordered set.
6. If rolled blockers non-empty -> `M7P10-B3`.
7. Emit `m7_p10_plane_snapshot.json` locally with:
   - source snapshot refs,
   - predicate map,
   - blocker rollup,
   - `overall_pass`.
8. Publish the snapshot durably.
9. Compute `overall_pass=true` only when predicates are all true, blocker rollup is empty, and durable publish succeeds.

Tasks:
1. Roll up blockers from `M7.G..M7.H` plus `P8/P9` closure snapshots.
2. Compute deterministic predicate map (`p8`, `p9`, `p10`).
3. Publish `m7_p10_plane_snapshot.json` locally + durably.

Required snapshot fields:
1. `phase`, `phase_id`, `platform_run_id`, `m7_execution_id`.
2. `source_snapshots` map:
   - path + `overall_pass` for `m7_p8_plane_snapshot`, `m7_p9_plane_snapshot`, `m7_g_case_label_db_readiness_snapshot`, `m7_h_case_label_commit_snapshot`.
3. `predicate_map`:
   - `p8_rtdl_caught_up`
   - `p9_decision_chain_committed`
   - `p10_case_labels_committed`.
4. `blocker_rollup`:
   - ordered list + source provenance.
5. `overall_pass`, `blockers`, `elapsed_seconds`.

Runtime budget:
1. `P10.C` target budget: <= 10 minutes wall clock.
2. If exceeded, lane remains fail-closed until explicit USER waiver.

DoD:
- [x] Plane snapshot exists locally + durably.
- [x] Blocker rollup is explicit and reproducible.
- [x] `overall_pass` is deterministic and predicate-driven.
- [x] Runtime budget target is met (or explicitly waived).

Blocker Codes (Taxonomy):
1. `M7P10-B1`: source snapshot missing/unreadable.
2. `M7P10-B2`: required predicate false or invalid.
3. `M7P10-B3`: blocker rollup non-empty.
4. `M7P10-B4`: run-scope mismatch across source snapshots.
5. `M7P10-B5`: plane snapshot write/upload failure.

Execution closure (`2026-02-19`):
1. Source snapshots consumed:
   - `runs/dev_substrate/m7/20260218T141420Z/m7_p8_plane_snapshot.json`
   - `runs/dev_substrate/m7/20260218T141420Z/m7_p9_plane_snapshot.json`
   - `runs/dev_substrate/m7/20260218T141420Z/m7_g_case_label_db_readiness_snapshot.json`
   - `runs/dev_substrate/m7/20260218T141420Z/m7_h_case_label_commit_snapshot.json`
2. Run-scope conformance checks:
   - `platform_run_id=platform_20260213T214223Z` matched across all sources.
   - `m7_execution_id=m7_20260218T141420Z` matched across all sources.
3. Predicate map result:
   - `p8_rtdl_caught_up=true`
   - `p9_decision_chain_committed=true`
   - `p10_case_labels_committed=true`
4. Blocker rollup:
   - empty (`[]`).
5. Published snapshot:
   - local:
     - `runs/dev_substrate/m7/20260218T141420Z/m7_p10_plane_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_p10_plane_snapshot.json`
6. Verdict:
   - `overall_pass=true`
   - blockers empty
   - runtime budget within target.

## 7) Evidence Contract (P10)
Run-scoped:
1. `evidence/runs/<platform_run_id>/case_labels/case_summary.json`
2. `evidence/runs/<platform_run_id>/case_labels/label_summary.json`

Control-plane:
1. `evidence/dev_min/run_control/<m7_execution_id>/m7_g_case_label_db_readiness_snapshot.json`
2. `evidence/dev_min/run_control/<m7_execution_id>/m7_h_case_label_commit_snapshot.json`
3. `evidence/dev_min/run_control/<m7_execution_id>/m7_p10_plane_snapshot.json`

## 8) Completion Checklist (P10)
- [x] P10.A complete
- [x] P10.B complete
- [x] P10.C complete

## 9) Exit Criteria (P10)
P10 branch is closure-ready only when:
1. Section 8 checklist is fully complete.
2. Required evidence artifacts exist and are durable.
3. `m7_p10_plane_snapshot.json` has `overall_pass=true`.
4. P10 closure is consumed by `platform.M7.build_plan.md` for M7 rollup.

