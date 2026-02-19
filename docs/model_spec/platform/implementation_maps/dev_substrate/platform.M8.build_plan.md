# Dev Substrate Deep Plan - M8 (P11 Obs/Gov Closure)
_Status source of truth: `platform.build_plan.md`_  
_This document provides deep planning detail for M8._  
_Last updated: 2026-02-19_

## 0) Purpose
M8 closes `P11 OBS_GOV_CLOSED` on managed substrate by proving:
1. Reporter closeout runs as a one-shot managed task under strict single-writer posture.
2. Run closure evidence bundle is complete, durable, and run-scoped.
3. Replay anchors and reconciliation are coherent against prior phase evidence.
4. Closure marker is written and M9 handoff is published.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P11` section)
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.build_plan.md`
2. Local M7 handoff:
   - `runs/dev_substrate/m7/20260218T141420Z/m8_handoff_pack.json`
3. Durable M7 handoff:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m8_handoff_pack.json`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M8
In scope:
1. P11 authority/handle closure for reporter and Obs/Gov paths.
2. Reporter runtime readiness and lock posture validation.
3. Closure-input evidence readiness checks (from M6/M7 outputs).
4. Reporter one-shot execution and lock contention fail-closed proof.
5. Closure artifact completeness, replay-anchor/reconciliation coherence, and closure marker verification.
6. M8 verdict publication and M9 handoff artifact publication.

Out of scope:
1. P12 teardown operations (M9).
2. M10 semantic/scale certification runs.
3. Any mutation of base truth stores (receipts/audit/timelines).

## 3) M8 Deliverables
1. `M8.A` handle/authority closure snapshot.
2. `M8.B` reporter runtime + lock readiness snapshot.
3. `M8.C` closure input readiness snapshot.
4. `M8.D` single-writer contention probe snapshot.
5. `M8.E` reporter execution snapshot.
6. `M8.F` closure bundle completeness snapshot.
7. `M8.G` replay/reconciliation coherence snapshot.
8. `M8.H` Obs/Gov closure marker snapshot.
9. `M8.I` M8 verdict snapshot (`ADVANCE_TO_M9` or `HOLD_M8`) + `m9_handoff_pack.json`.

## 4) Execution Gate for This Phase
Current posture:
1. M7 is closed through `M7.J` and published `m8_handoff_pack.json`.
2. M8 is active for planning/execution.

Execution block:
1. No M9 execution is allowed before M8 verdict is `ADVANCE_TO_M9`.
2. No M8 closure is allowed if reporter lock discipline is not provable.
3. No manual reporter run is allowed concurrently with any reporter daemon/one-shot for the same run scope.

## 4.1) Anti-Cram Law (Binding for M8)
1. M8 is not execution-ready unless these lanes are explicit:
   - authority/handles
   - identity/IAM + secrets
   - reporter lock backend + contention behavior
   - closure input evidence readiness
   - closure artifact publication + non-secret checks
   - replay/reconciliation coherence
   - rerun/rollback posture
   - runtime budget + cost posture
2. If a missing lane is discovered, execution pauses and plan expansion is mandatory before continuing.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting sub-phases | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + handles closure | M8.A | M8.I | zero unresolved required P11 handles |
| Reporter runtime + IAM readiness | M8.B | M8.E | reporter task runtime/role lock-ready |
| Closure-input evidence readiness | M8.C | M8.F/M8.G | required upstream evidence URIs readable |
| Single-writer lock discipline | M8.D | M8.E | contention probe fails closed for second writer |
| Reporter execution | M8.E | M8.F | one-shot reporter completes with lock lifecycle proof |
| Closure bundle completeness | M8.F | M8.H | required closure artifacts exist with run scope |
| Replay/reconciliation coherence | M8.G | M8.I | replay anchors + reconciliation are internally coherent |
| Closure marker + governance outputs | M8.H | M8.I | `run_completed.json` + obs artifacts verified |
| Verdict + M9 handoff | M8.I | - | `ADVANCE_TO_M9` + durable `m9_handoff_pack.json` |

## 5) Work Breakdown (Deep)

### M8.A P11 Authority + Handle Closure
Goal:
1. Close all required P11 handles before any reporter execution.
2. Freeze a deterministic P11 handle matrix for downstream M8 lanes.

Entry conditions:
1. `M7` is `DONE` and `M7.J` handoff artifact is readable.
2. Handoff contract passes:
   - `m8_entry_gate=READY`
   - `overall_pass=true`
   - blockers empty.
3. Active run scope is fixed:
   - `platform_run_id=platform_20260213T214223Z`.

Required inputs:
1. M7 handoff artifacts:
   - local: `runs/dev_substrate/m7/20260218T141420Z/m8_handoff_pack.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m8_handoff_pack.json`.
2. Required P11 handles (registry closure set):
   - reporter runtime:
     - `TD_REPORTER`
     - `ROLE_REPORTER_SINGLE_WRITER`
   - evidence roots and closure outputs:
     - `S3_EVIDENCE_BUCKET`
     - `S3_EVIDENCE_RUN_ROOT_PATTERN`
     - `RUN_CLOSURE_MARKER_PATH_PATTERN`
     - `RUN_REPORT_PATH_PATTERN`
     - `REPLAY_ANCHORS_PATH_PATTERN`
     - `RECONCILIATION_PATH_PATTERN`
     - `ENV_CONFORMANCE_PATH_PATTERN`
   - lock contract:
     - `REPORTER_LOCK_BACKEND`
     - `REPORTER_LOCK_KEY_PATTERN`
   - closeout input evidence patterns:
     - `RECEIPT_SUMMARY_PATH_PATTERN`
     - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
     - `RTDL_CORE_EVIDENCE_PATH_PATTERN`
     - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
     - `CASE_EVIDENCE_PATH_PATTERN`
     - `LABEL_EVIDENCE_PATH_PATTERN`.
3. Authority sources:
   - `platform.build_plan.md`
   - `dev_min_spine_green_v0_run_process_flow.md` (`P11`)
   - `dev_min_handles.registry.v0.md`.

Preparation checks:
1. Validate M7 handoff run-scope conformance (`platform_run_id`, `m7_execution_id` present and non-placeholder).
2. Validate each required handle key exists in registry and resolves to non-empty concrete value.
3. Validate no wildcard/placeholder posture in required closure set.
4. Validate path-pattern handles preserve run-scope placeholder contract (`{platform_run_id}` where required).

Deterministic verification algorithm (M8.A):
1. Load M7 handoff (local preferred, durable fallback); unreadable/invalid -> `M8A-B1`.
2. Verify handoff gate (`READY`, `overall_pass=true`, blockers empty); mismatch -> `M8A-B1`.
3. Resolve required handle keys from registry into closure matrix:
   - record `value`, `source`, `resolved=true/false`.
4. Fail closed on unresolved required handle -> `M8A-B2`.
5. Detect wildcard/placeholder posture in required set -> `M8A-B3`.
6. Execute lightweight materialization probes:
   - reporter task/role handles present and parseable,
   - evidence bucket/root handles parseable for run-scope rendering.
   Probe failure -> `M8A-B4`.
7. Emit `m8_a_handle_closure_snapshot.json` locally with:
   - run scope and handoff refs,
   - required handle matrix (resolved/unresolved),
   - wildcard/placeholder findings,
   - probe results,
   - blocker list + `overall_pass`.
8. Publish snapshot durably.

Tasks:
1. Validate M7->M8 handoff invariants (`platform_run_id`, verdict, blocker-free posture).
2. Probe required P11 handles from registry and build deterministic closure matrix.
3. Emit and publish `m8_a_handle_closure_snapshot.json` (local + durable).

Required snapshot fields (`m8_a_handle_closure_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_m7_handoff_local`, `source_m7_handoff_uri`.
3. `required_handle_keys`, `resolved_handle_count`, `unresolved_handle_count`.
4. `unresolved_handle_keys`, `wildcard_handle_keys`, `placeholder_handle_keys`.
5. `probe_results`, `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M8.A` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

DoD:
- [x] Required handles are explicit and probe-pass.
- [x] Placeholder/wildcard required handles are absent.
- [x] Snapshot exists locally and durably.

Planning status:
1. `M8.A` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. Execution attempted on `2026-02-19` under `m8_execution_id=m8_20260219T073801Z`.
3. Initial attempt failed closed on `M8A-B2` (`TD_REPORTER`, `ROLE_REPORTER_SINGLE_WRITER` unresolved).
4. Reporter surfaces were materialized via Terraform demo lane:
   - role: `fraud-platform-dev-min-reporter-single-writer`,
   - task definition family: `fraud-platform-dev-min-reporter`.
5. Rerun passed on `m8_execution_id=m8_20260219T075228Z` (`overall_pass=true`, blockers empty).

Execution closure (2026-02-19):
1. Snapshot emitted locally:
   - `runs/dev_substrate/m8/20260219T073801Z/m8_a_handle_closure_snapshot.json`.
2. Snapshot published durably:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T073801Z/m8_a_handle_closure_snapshot.json`.
3. Result:
   - `overall_pass=false`,
   - `resolved_handle_count=15`,
   - `unresolved_handle_count=2`.
4. Blocking unresolved required handles:
   - `ROLE_REPORTER_SINGLE_WRITER`,
   - `TD_REPORTER`.
5. M8.A remains open until required reporter handles are bound to concrete values and rerun passes.

Execution closure rerun (2026-02-19):
1. Snapshot emitted locally:
   - `runs/dev_substrate/m8/m8_20260219T075228Z/m8_a_handle_closure_snapshot.json`.
2. Snapshot published durably:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T075228Z/m8_a_handle_closure_snapshot.json`.
3. Result:
   - `overall_pass=true`,
   - `resolved_handle_count=17`,
   - `unresolved_handle_count=0`,
   - blockers empty.
4. Reporter runtime hardening applied post-materialization:
   - active reporter task definition now `fraud-platform-dev-min-reporter:2` on managed platform image digest (not busybox default).
5. `M8.A` is now closed and `M8.B` is unblocked.

Blocker Codes (Taxonomy):
1. `M8A-B1`: M7 handoff invalid or unreadable.
2. `M8A-B2`: required handle unresolved.
3. `M8A-B3`: placeholder/wildcard required handle detected.
4. `M8A-B4`: snapshot write/upload failure.
5. `M8A-B5`: run-scope mismatch between M7 handoff and active execution scope.

### M8.B Reporter Runtime + Lock Readiness
Goal:
1. Prove reporter task runtime posture and lock backend readiness.

Entry conditions:
1. `M8.A` rerun is pass with blockers empty:
   - local: `runs/dev_substrate/m8/m8_20260219T075228Z/m8_a_handle_closure_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T075228Z/m8_a_handle_closure_snapshot.json`.
2. Active run scope is fixed:
   - `platform_run_id=platform_20260213T214223Z`.
3. Reporter handles are concretely pinned:
   - `TD_REPORTER=fraud-platform-dev-min-reporter`
   - `ROLE_REPORTER_SINGLE_WRITER=fraud-platform-dev-min-reporter-single-writer`.

Required inputs:
1. `M8.A` pass snapshot (local preferred, durable fallback).
2. Reporter readiness handles:
   - `TD_REPORTER`
   - `ROLE_REPORTER_SINGLE_WRITER`
   - `REPORTER_LOCK_BACKEND`
   - `REPORTER_LOCK_KEY_PATTERN`
   - `S3_EVIDENCE_BUCKET`
   - `S3_EVIDENCE_RUN_ROOT_PATTERN`
   - `RUN_REPORT_PATH_PATTERN`
   - `REPLAY_ANCHORS_PATH_PATTERN`
   - `RECONCILIATION_PATH_PATTERN`
   - `ENV_CONFORMANCE_PATH_PATTERN`
   - `RUN_CLOSURE_MARKER_PATH_PATTERN`.
3. Runtime probe surfaces:
   - `aws ecs describe-task-definition` for `TD_REPORTER`,
   - `aws iam get-role` for `ROLE_REPORTER_SINGLE_WRITER`,
   - inline role-policy retrieval for required action families.

Preparation checks:
1. Validate `M8.A` pass posture and run-scope match.
2. Validate reporter handle values are non-empty and non-placeholder.
3. Validate lock contract values:
   - backend equals `db_advisory_lock`,
   - key pattern includes `{platform_run_id}` and renders cleanly for active run.

Deterministic verification algorithm (M8.B):
1. Load `M8.A` snapshot; fail on missing/invalid/pass-mismatch -> `M8B-B5`.
2. Resolve required handles; unresolved/placeholder/wildcard -> `M8B-B5`.
3. Describe `TD_REPORTER`; fail on missing task definition -> `M8B-B1`.
4. Validate reporter runtime command posture:
   - contains `python -m fraud_detection.platform_reporter.worker`,
   - includes `--once`,
   - includes run-scope enforcement (`--required-platform-run-id` or equivalent env lock),
   - no no-op/stub echo loop command.
   Failure -> `M8B-B1`.
5. Validate reporter image posture:
   - managed platform image (ECR platform digest),
   - explicitly reject `public.ecr.aws/docker/library/busybox*`.
   Failure -> `M8B-B1`.
6. Validate reporter role binding:
   - task role ARN resolves to `ROLE_REPORTER_SINGLE_WRITER`,
   - IAM role exists and is assumable by ECS tasks.
   Failure -> `M8B-B2`.
7. Validate minimal role capability families via inline policies:
   - SSM parameter read for runtime secret surfaces,
   - S3 read/write on evidence run roots,
   - S3 read/write on run-control evidence roots.
   Failure -> `M8B-B2`.
8. Validate lock contract rendering:
   - `REPORTER_LOCK_BACKEND` in allowlist (`db_advisory_lock` for v0),
   - rendered lock key has no unresolved template token.
   Failure -> `M8B-B3`.
9. Emit `m8_b_reporter_readiness_snapshot.json` locally and publish durably.
10. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Validate task definition runtime posture (image + command + run-scope enforcement).
2. Validate reporter role existence, binding, and minimal policy capability families.
3. Validate lock backend/key contract.
4. Emit and publish `m8_b_reporter_readiness_snapshot.json` (local + durable).

Required snapshot fields (`m8_b_reporter_readiness_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_m8a_snapshot_local`, `source_m8a_snapshot_uri`.
3. `td_reporter`, `td_reporter_arn`, `td_reporter_revision`, `reporter_image`.
4. `reporter_command_checks`, `reporter_role_binding_checks`, `reporter_role_policy_checks`.
5. `lock_contract`, `lock_contract_checks`.
6. `blockers`, `overall_pass`, `elapsed_seconds`.

DoD:
- [x] Reporter task runtime posture is valid and managed.
- [x] Role and lock backend posture checks pass.
- [x] Snapshot exists locally and durably.

Runtime budget:
1. `M8.B` target budget: <= 12 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Planning status:
1. `M8.B` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. Execution completed on `m8_execution_id=m8_20260219T080757Z` with pass verdict.

Execution closure (2026-02-19):
1. Snapshot emitted locally:
   - `runs/dev_substrate/m8/m8_20260219T080757Z/m8_b_reporter_readiness_snapshot.json`.
2. Snapshot published durably:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T080757Z/m8_b_reporter_readiness_snapshot.json`.
3. Result:
   - `overall_pass=true`,
   - blockers empty.
4. Runtime posture confirmed:
   - reporter task definition `fraud-platform-dev-min-reporter:2`,
   - managed platform image digest (no busybox),
   - role binding `fraud-platform-dev-min-reporter-single-writer`,
   - lock contract valid (`db_advisory_lock`, `reporter:{platform_run_id}` renderable).
5. `M8.B` is closed and `M8.C` is unblocked.

Blocker Codes (Taxonomy):
1. `M8B-B1`: reporter task/runtime command invalid.
2. `M8B-B2`: reporter role capability mismatch.
3. `M8B-B3`: lock backend/key configuration invalid.
4. `M8B-B4`: snapshot write/upload failure.
5. `M8B-B5`: `M8.A` prerequisite or run-scope gate failed.

### M8.C Closure Input Evidence Readiness
Goal:
1. Verify all required upstream evidence artifacts are readable, run-scoped, and semantically sufficient before reporter closeout.

Entry conditions:
1. `M8.B` is pass with blockers empty:
   - local: `runs/dev_substrate/m8/m8_20260219T080757Z/m8_b_reporter_readiness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T080757Z/m8_b_reporter_readiness_snapshot.json`.
2. Active run scope is fixed:
   - `platform_run_id=platform_20260213T214223Z`.
3. No concurrent reporter closeout execution for the same run scope.

Required inputs:
1. `M8.B` pass snapshot (local preferred, durable fallback).
2. Required handles (renderable and non-placeholder):
   - `S3_EVIDENCE_BUCKET`
   - `S3_EVIDENCE_RUN_ROOT_PATTERN`
   - `RECEIPT_SUMMARY_PATH_PATTERN`
   - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
   - `RTDL_CORE_EVIDENCE_PATH_PATTERN`
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
   - `CASE_EVIDENCE_PATH_PATTERN`
   - `LABEL_EVIDENCE_PATH_PATTERN`.
3. Required evidence objects after handle rendering:
   - `ingest/receipt_summary.json`
   - `ingest/kafka_offsets_snapshot.json`
   - `rtdl_core/caught_up.json`
   - `rtdl_core/offsets_snapshot.json`
   - `decision_lane/decision_summary.json`
   - `decision_lane/action_summary.json`
   - `decision_lane/audit_summary.json`
   - `case_labels/case_summary.json`
   - `case_labels/label_summary.json`.

Preparation checks:
1. Validate `M8.B` pass posture and run-scope match.
2. Validate all required handle values resolve concretely (no wildcard/placeholder posture).
3. Render required evidence URIs and verify every URI sits under rendered run root:
   - `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/...`.

Deterministic verification algorithm (M8.C):
1. Load `M8.B` snapshot; fail on missing/invalid/pass-mismatch -> `M8C-B5`.
2. Resolve required handles; unresolved/placeholder/wildcard -> `M8C-B5`.
3. Render required evidence object URIs from handle patterns + run scope.
4. For each required URI, assert `HEAD`/read success and non-zero payload; failure -> `M8C-B1`.
5. Parse each artifact and assert run-scope conformance (`platform_run_id` in payload or pinned run metadata); mismatch -> `M8C-B2`.
6. Validate ingest ambiguity posture from receipt summary:
   - `publish_unknown_count` (or equivalent ambiguity indicator) must be zero.
   - ambiguity present -> `M8C-B2`.
7. Validate offsets semantics minimums:
   - ingest and rtdl offsets snapshots contain at least one topic/partition range.
   - empty/invalid ranges -> `M8C-B3`.
8. Emit `m8_c_input_readiness_snapshot.json` locally and publish durably.
9. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Validate required upstream evidence object readability for P7/P8/P9/P10 surfaces.
2. Validate run-scope and ambiguity posture from evidence payloads.
3. Validate offsets snapshot semantic minimums (non-empty topic/partition ranges).
4. Emit and publish `m8_c_input_readiness_snapshot.json` (local + durable).

Required snapshot fields (`m8_c_input_readiness_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_m8b_snapshot_local`, `source_m8b_snapshot_uri`.
3. `rendered_evidence_root`, `required_evidence_uris`.
4. `readability_checks`, `run_scope_checks`, `ambiguity_checks`, `offset_semantics_checks`.
5. `blockers`, `overall_pass`, `elapsed_seconds`.

DoD:
- [x] Required input evidence URIs are readable.
- [x] Run-scope and ingest ambiguity posture checks pass.
- [x] Offsets semantic checks pass for ingest and RTDL snapshots.
- [x] Snapshot exists locally and durably.

Runtime budget:
1. `M8.C` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Planning status:
1. `M8.C` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. Runtime execution completed on `m8_execution_id=m8_20260219T082913Z` with pass verdict.

Execution closure (2026-02-19):
1. Fail-first attempt (trace retained):
   - execution id: `m8_20260219T082518Z`
   - local snapshot: `runs/dev_substrate/m8/m8_20260219T082518Z/m8_c_input_readiness_snapshot.json`
   - result: `overall_pass=false`, blockers `M8C-B5`, `M8C-B3`
   - cause: prerequisite local snapshot BOM decode + narrow offset-shape probe.
2. Intermediate attempt (trace retained):
   - execution id: `m8_20260219T082755Z`
   - local snapshot: `runs/dev_substrate/m8/m8_20260219T082755Z/m8_c_input_readiness_snapshot.json`
   - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T082755Z/m8_c_input_readiness_snapshot.json`
   - result: `overall_pass=false`, blocker `M8C-B3`
   - cause: offset semantic probe accepted only `start_offset/end_offset`; runtime artifacts use `run_start_offset/run_end_offset`.
3. Closure pass run:
   - execution id: `m8_20260219T082913Z`
   - local snapshot: `runs/dev_substrate/m8/m8_20260219T082913Z/m8_c_input_readiness_snapshot.json`
   - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T082913Z/m8_c_input_readiness_snapshot.json`
   - result: `overall_pass=true`, blockers empty
   - runtime: `elapsed_seconds=1.673` (within `M8.C` budget).
4. Verified posture in pass run:
   - required P7/P8/P9/P10 evidence objects are readable and non-empty,
   - run-scope conformance holds across all required input surfaces,
   - ingest ambiguity indicators resolved at zero,
   - ingest + RTDL offset snapshots provide partition-range coverage.
5. `M8.C` is closed; `M8.D` is unblocked.

Blocker Codes (Taxonomy):
1. `M8C-B1`: required evidence URI missing/unreadable.
2. `M8C-B2`: run-scope mismatch or unresolved ingest publish ambiguity in required evidence.
3. `M8C-B3`: required offsets semantic checks failed.
4. `M8C-B4`: snapshot write/upload failure.
5. `M8C-B5`: `M8.B` prerequisite or run-scope gate failed.

### M8.D Single-Writer Contention Probe
Goal:
1. Prove fail-closed behavior under same-run reporter contention.

Entry conditions:
1. `M8.C` is pass with blockers empty:
   - local: `runs/dev_substrate/m8/m8_20260219T082913Z/m8_c_input_readiness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T082913Z/m8_c_input_readiness_snapshot.json`.
2. Active run scope is fixed:
   - `platform_run_id=platform_20260213T214223Z`.
3. Reporter runtime and lock-contract handles remain concrete and non-placeholder:
   - `TD_REPORTER`
   - `ROLE_REPORTER_SINGLE_WRITER`
   - `REPORTER_LOCK_BACKEND`
   - `REPORTER_LOCK_KEY_PATTERN`.

Required inputs:
1. `M8.C` pass snapshot (local preferred, durable fallback).
2. Reporter runtime surfaces:
   - ECS cluster/service/task-definition handles for one-shot reporter invocation,
   - CloudWatch log group/prefix for reporter task logs.
3. Lock proof surfaces:
   - runtime signal proving lock acquisition/denial semantics,
   - run-scoped closure output surfaces (`run_report` path + governance/event stream if available).

Preparation checks:
1. Validate `M8.C` pass posture and run-scope match.
2. Validate reporter task-definition revision matches M8.B-ready runtime posture.
3. Validate contention-probe executability:
   - lock semantics are actually wired in runtime path (not just contract config),
   - probe can produce deterministic overlap window for two same-run invocations.
   Failure of this preparation check is fail-closed (`M8D-B4`).

Deterministic verification algorithm (M8.D):
1. Load `M8.C` snapshot; fail on missing/invalid/pass-mismatch -> `M8D-B5`.
2. Resolve reporter + lock handles; unresolved/placeholder/wildcard -> `M8D-B5`.
3. Assert lock wiring is executable in runtime lane (code-path/log signal), not only declarative contract:
   - missing executable lock behavior -> `M8D-B4`.
4. Launch two reporter one-shot tasks with same `platform_run_id` in controlled overlap window.
5. Wait for both tasks to terminal state and capture:
   - task ARNs, exit codes, stop reasons, log stream refs, start/stop timestamps.
6. Evaluate contention outcome:
   - exactly one writer succeeds in lock-protected section,
   - second writer is denied/fails closed with lock-conflict signal.
   Any other outcome -> `M8D-B1` or `M8D-B2` per failure class.
7. Verify no conflicting closure writes:
   - no dual-success conflicting write pattern for run closure artifacts,
   - governance/report outputs remain single-writer coherent for the probe window.
   Conflict -> `M8D-B2`.
8. Emit `m8_d_single_writer_probe_snapshot.json` locally and publish durably.
9. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Execute controlled two-writer contention probe for same run scope.
2. Verify second writer fail-closed behavior with explicit runtime evidence.
3. Verify closure outputs remain single-writer coherent during probe window.
4. Emit and publish `m8_d_single_writer_probe_snapshot.json` (local + durable).

Required snapshot fields (`m8_d_single_writer_probe_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_m8c_snapshot_local`, `source_m8c_snapshot_uri`.
3. `probe_inputs` (task definition, lock contract, overlap window settings).
4. `task_invocations` (task ids, state transitions, exits, stop reasons, log refs).
5. `contention_outcome_checks`, `single_writer_output_checks`.
6. `blockers`, `overall_pass`, `elapsed_seconds`.

DoD:
- [x] Contention probe demonstrates single-writer lock correctness.
- [x] Second writer is denied/fails closed with explicit runtime evidence.
- [x] No conflicting closure writes occur under probe.
- [x] Snapshot exists locally and durably.

Runtime budget:
1. `M8.D` target budget: <= 15 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Planning status:
1. `M8.D` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. Runtime execution completed on `m8_execution_id=m8_20260219T091250Z` with fail-closed verdict.
3. Runtime remediation rerun completed on `m8_execution_id=m8_20260219T093130Z` with pass verdict.

Execution closure (2026-02-19):
1. Probe execution:
   - execution id: `m8_20260219T091250Z`
   - local snapshot: `runs/dev_substrate/m8/m8_20260219T091250Z/m8_d_single_writer_probe_snapshot.json`
   - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T091250Z/m8_d_single_writer_probe_snapshot.json`.
2. Contention outcomes observed:
   - two reporter one-shot tasks launched for same run scope with overlap `32.435s`,
   - one task exited `0`,
   - one task exited `1` with runtime trace including `RuntimeError: S3_APPEND_CONFLICT`.
3. Probe classification:
   - `M8D-B1` cleared after corrected log retrieval confirmed explicit conflict signal on losing writer,
   - unresolved `M8D-B4` remains because pinned lock contract (`REPORTER_LOCK_BACKEND`/`REPORTER_LOCK_KEY_PATTERN`, `db_advisory_lock`) is not executable/provable in reporter runtime path.
4. Verdict:
   - `overall_pass=false`,
   - blockers: `M8D-B4`.
5. Phase posture:
   - `M8.D` remains open (fail-closed),
   - `M8.E` stays blocked until `M8D-B4` is remediated and `M8.D` rerun passes.

Execution remediation rerun closure (2026-02-19):
1. Remediation posture:
   - reporter worker now executes explicit advisory-lock path (`db_advisory_lock`),
   - reporter runtime env includes:
     - `REPORTER_LOCK_BACKEND=db_advisory_lock`,
     - `REPORTER_LOCK_KEY_PATTERN=reporter:{platform_run_id}`,
   - reporter task definition rematerialized to `fraud-platform-dev-min-reporter:3`.
2. Rerun execution:
   - execution id: `m8_20260219T093130Z`
   - local snapshot: `runs/dev_substrate/m8/m8_20260219T093130Z/m8_d_single_writer_probe_snapshot.json`
   - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T093130Z/m8_d_single_writer_probe_snapshot.json`.
3. Rerun outcomes:
   - two same-run reporter tasks overlapped (`30.782s`),
   - one task succeeded, one task failed closed under contention,
   - conflict/lock signal evidence present (`lock_conflict_signal_count=9`),
   - no conflicting closure writes observed.
4. Verdict:
   - `overall_pass=true`,
   - blockers empty.
5. Phase posture:
   - `M8.D` is closed,
   - `M8.E` is unblocked for execution.

Blocker Codes (Taxonomy):
1. `M8D-B1`: lock does not enforce single-writer under contention probe.
2. `M8D-B2`: concurrent writer succeeds unexpectedly or conflicting closure writes observed.
3. `M8D-B3`: snapshot write/upload failure.
4. `M8D-B4`: lock semantics not executable/provable in reporter runtime path.
5. `M8D-B5`: `M8.C` prerequisite or run-scope gate failed.

### M8.E Reporter One-Shot Execution
Goal:
1. Execute reporter closeout for active run scope on managed compute.

Entry conditions:
1. `M8.D` is pass with blockers empty:
   - local: `runs/dev_substrate/m8/m8_20260219T093130Z/m8_d_single_writer_probe_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T093130Z/m8_d_single_writer_probe_snapshot.json`.
2. Active run scope is fixed:
   - `platform_run_id=platform_20260213T214223Z`.
3. Reporter runtime contract remains concrete on live task definition:
   - `TD_REPORTER`,
   - `ROLE_REPORTER_SINGLE_WRITER`,
   - `REPORTER_LOCK_BACKEND=db_advisory_lock`,
   - `REPORTER_LOCK_KEY_PATTERN=reporter:{platform_run_id}`.

Required inputs:
1. `M8.D` pass snapshot (local preferred, durable fallback).
2. Reporter runtime surfaces:
   - ECS cluster + task-definition handles for one-shot invocation,
   - CloudWatch log group/prefix for reporter logs.
3. Closure output surfaces:
   - run-scoped evidence root for Obs/Gov outputs,
   - M8 control-plane evidence root for `m8_e_reporter_execution_snapshot.json`.

Preparation checks:
1. Validate `M8.D` pass posture and run-scope match.
2. Validate reporter task-definition revision and image digest align with post-remediation runtime lane.
3. Validate lock contract env remains concrete (no placeholder/wildcard/unset values).
4. Validate evidence bucket/path permissions for local->durable snapshot publication.
   Failure of any preparation check is fail-closed (`M8E-B4`/`M8E-B5`).

Deterministic verification algorithm (M8.E):
1. Load `M8.D` pass snapshot; fail on missing/invalid/pass-mismatch -> `M8E-B4`.
2. Resolve reporter runtime handles and run scope; unresolved/placeholder/wildcard -> `M8E-B5`.
3. Launch one reporter task for fixed `platform_run_id` with deterministic `startedBy` marker.
4. Wait for terminal outcome within M8.E budget window.
   - timeout/non-terminal -> `M8E-B1`.
5. Verify terminal status:
   - task exit must be `0`,
   - no fatal runtime exception patterns in task logs.
   Failure -> `M8E-B1`.
6. Verify lock lifecycle evidence from runtime logs/surfaces:
   - lock attempt/acquire/release present,
   - no lock-denied conflict pattern in this one-shot lane.
   Failure -> `M8E-B2`.
7. Emit `m8_e_reporter_execution_snapshot.json` locally and publish durably.
8. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Invoke one-shot reporter task with run-scope inputs.
2. Verify task completion (`exit=0`) and lock lifecycle in logs (attempt/acquire/release).
3. Emit `m8_e_reporter_execution_snapshot.json` (local + durable).

Required snapshot fields (`m8_e_reporter_execution_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_m8d_snapshot_local`, `source_m8d_snapshot_uri`.
3. `reporter_invocation` (task arn/id, startedBy, cluster, task definition revision, image digest).
4. `terminal_outcome_checks` (exit code, stop reason, runtime timing).
5. `lock_lifecycle_checks` (attempt/acquire/release signal checks).
6. `blockers`, `overall_pass`, `elapsed_seconds`.

DoD:
- [x] Reporter task exits successfully.
- [x] Lock lifecycle is evidenced in runtime logs/snapshot.
- [x] Snapshot exists locally and durably.

Blocker Codes (Taxonomy):
1. `M8E-B1`: reporter task failed or timed out.
2. `M8E-B2`: lock lifecycle evidence incomplete.
3. `M8E-B3`: snapshot write/upload failure.
4. `M8E-B4`: `M8.D` prerequisite or run-scope gate failed.
5. `M8E-B5`: reporter runtime contract/handle resolution failed.

Runtime budget:
1. `M8.E` target budget: <= 15 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Planning status:
1. `M8.E` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. Runtime execution completed on `m8_execution_id=m8_20260219T095720Z` with pass verdict.

Execution closure (2026-02-19):
1. One-shot execution:
   - execution id: `m8_20260219T095720Z`
   - local snapshot: `runs/dev_substrate/m8/m8_20260219T095720Z/m8_e_reporter_execution_snapshot.json`
   - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T095720Z/m8_e_reporter_execution_snapshot.json`.
2. Runtime posture validated before launch:
   - source gate `M8.D` pass artifact readable,
   - reporter task definition `fraud-platform-dev-min-reporter:3`,
   - lock contract env concrete (`db_advisory_lock`, `reporter:{platform_run_id}`).
3. One-shot outcomes:
   - reporter task exit `0` (`task_id=89ce923388114e13932d3b793d790b47`),
   - no timeout/fatal runtime pattern,
   - lock lifecycle evidenced (`attempt`, `acquired`, `released`) with no deny signal.
4. Verdict:
   - `overall_pass=true`,
   - blockers empty,
   - elapsed `77.158s`.
5. Phase posture:
   - `M8.E` is closed,
   - `M8.F` is unblocked for execution.

### M8.F Closure Bundle Completeness
Goal:
1. Verify required closure artifacts exist and are run-scoped.

Entry conditions:
1. `M8.E` is pass with blockers empty:
   - local: `runs/dev_substrate/m8/m8_20260219T095720Z/m8_e_reporter_execution_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T095720Z/m8_e_reporter_execution_snapshot.json`.
2. Active run scope is fixed:
   - `platform_run_id=platform_20260213T214223Z`.
3. Run-scoped evidence root is resolvable and readable:
   - `evidence/runs/<platform_run_id>/`.

Required inputs:
1. `M8.E` pass snapshot (local preferred, durable fallback).
2. Required run-scoped closure bundle targets:
   - `evidence/runs/<platform_run_id>/run_completed.json`
   - `evidence/runs/<platform_run_id>/obs/run_report.json`
   - `evidence/runs/<platform_run_id>/obs/reconciliation.json`
   - `evidence/runs/<platform_run_id>/obs/replay_anchors.json`
   - `evidence/runs/<platform_run_id>/obs/environment_conformance.json`
   - `evidence/runs/<platform_run_id>/obs/anomaly_summary.json`.
3. M8 control-plane evidence root for `m8_f_bundle_completeness_snapshot.json`.

Preparation checks:
1. Validate `M8.E` pass posture and run-scope match.
2. Validate evidence bucket/root handles are concrete and non-placeholder.
3. Validate local->durable snapshot publication path is writable.
   Failure of any preparation check is fail-closed (`M8F-B4`/`M8F-B5`).

Deterministic verification algorithm (M8.F):
1. Load `M8.E` pass snapshot; fail on missing/invalid/pass-mismatch -> `M8F-B4`.
2. Resolve required closure artifact paths from fixed run scope.
3. For each required object:
   - validate object existence/readability,
   - fetch payload and validate parseability (JSON),
   - evaluate run-scope conformance (`platform_run_id`/equivalent field alignment).
4. Record per-artifact verdict rows:
   - `exists`, `readable`, `json_parse_ok`, `run_scope_ok`, `failure_reason`.
5. Classify blockers:
   - missing/unreadable object -> `M8F-B1`,
   - parse/scope/content conformance failure -> `M8F-B2`.
6. Emit `m8_f_bundle_completeness_snapshot.json` locally and publish durably.
7. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Validate artifact existence:
   - `evidence/runs/<platform_run_id>/run_completed.json`
   - `evidence/runs/<platform_run_id>/obs/run_report.json`
   - `evidence/runs/<platform_run_id>/obs/reconciliation.json`
   - `evidence/runs/<platform_run_id>/obs/replay_anchors.json`
   - `evidence/runs/<platform_run_id>/obs/environment_conformance.json`
   - `evidence/runs/<platform_run_id>/obs/anomaly_summary.json`.
2. Validate each artifact references active run scope.
3. Emit `m8_f_bundle_completeness_snapshot.json`.

Required snapshot fields (`m8_f_bundle_completeness_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_m8e_snapshot_local`, `source_m8e_snapshot_uri`.
3. `bundle_targets` (required object paths under run-scoped root).
4. `artifact_checks` (per-object existence/readability/parse/scope results).
5. `blockers`, `overall_pass`, `elapsed_seconds`.

DoD:
- [x] Required closure artifacts exist at pinned paths.
- [x] Artifact run-scope conformance checks pass.
- [x] Snapshot exists locally and durably.

Blocker Codes (Taxonomy):
1. `M8F-B1`: required closure artifact missing.
2. `M8F-B2`: closure artifact run-scope mismatch.
3. `M8F-B3`: snapshot write/upload failure.
4. `M8F-B4`: `M8.E` prerequisite or run-scope gate failed.
5. `M8F-B5`: evidence-handle resolution/preparation check failed.

Runtime budget:
1. `M8.F` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Planning status:
1. `M8.F` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. Runtime execution completed with fail-first evidence plus remediation rerun pass closure.

Execution closure (2026-02-19):
1. Fail-first witness run:
   - execution id: `m8_20260219T104212Z`
   - local snapshot: `runs/dev_substrate/m8/m8_20260219T104212Z/m8_f_bundle_completeness_snapshot.json`
   - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T104212Z/m8_f_bundle_completeness_snapshot.json`
   - posture: fail-closed witness only; blocker typing corrected in rerun.
2. Authoritative rerun:
   - execution id: `m8_20260219T104508Z`
   - local snapshot: `runs/dev_substrate/m8/m8_20260219T104508Z/m8_f_bundle_completeness_snapshot.json`
   - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T104508Z/m8_f_bundle_completeness_snapshot.json`.
3. Canonical rerun outcomes:
   - `overall_pass=false`,
   - blockers: `M8F-B1`,
   - all six required bundle targets are missing at pinned contract paths.
4. Verified available non-substitute Obs files during closure:
   - `obs/platform_run_report.json`,
   - `obs/governance/events.jsonl`.
5. Phase posture:
   - `M8.F` remains open fail-closed,
   - `M8.G..M8.I` remain blocked pending `M8F-B1` remediation + rerun pass.
6. Remediation closure reruns:
   - reporter task definition rematerialized to `fraud-platform-dev-min-reporter:4` using image digest `sha256:2072e48137013851c349e9de2e5e0b4a8a2ff522d0a0db1ef609970d9c080c54`.
   - `M8.E` rerun:
     - execution id: `m8_20260219T111715Z`
     - local snapshot: `runs/dev_substrate/m8/m8_20260219T111715Z/m8_e_reporter_execution_snapshot.json`
     - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T111715Z/m8_e_reporter_execution_snapshot.json`
     - result: `overall_pass=true`, blockers empty.
   - `M8.F` rerun:
     - execution id: `m8_20260219T111902Z`
     - local snapshot: `runs/dev_substrate/m8/m8_20260219T111902Z/m8_f_bundle_completeness_snapshot.json`
     - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T111902Z/m8_f_bundle_completeness_snapshot.json`
     - result: `overall_pass=true`, blockers empty.
   - verified bundle targets now present and run-scoped:
     - `run_completed.json`
     - `obs/run_report.json`
     - `obs/reconciliation.json`
     - `obs/replay_anchors.json`
     - `obs/environment_conformance.json`
     - `obs/anomaly_summary.json`.
7. Current phase posture:
   - `M8.F` is closed,
   - `M8.G..M8.I` are unblocked for sequential execution.

### M8.G Replay Anchors + Reconciliation Coherence
Goal:
1. Verify replay anchors and reconciliation summaries are coherent.

Entry conditions:
1. `M8.F` is pass with blockers empty:
   - local: `runs/dev_substrate/m8/m8_20260219T111902Z/m8_f_bundle_completeness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T111902Z/m8_f_bundle_completeness_snapshot.json`.
2. Active run scope is pinned to:
   - `platform_run_id=platform_20260213T214223Z`.
3. No unresolved blockers remain from `M8.F`.

Required inputs:
1. `M8.F` pass snapshot (local preferred, durable fallback).
2. Run-scoped P11 closure artifacts:
   - `evidence/runs/<platform_run_id>/obs/run_report.json`
   - `evidence/runs/<platform_run_id>/obs/reconciliation.json`
   - `evidence/runs/<platform_run_id>/obs/replay_anchors.json`.
3. Referenced upstream offset snapshots from replay-anchors source refs:
   - `evidence/runs/<platform_run_id>/ingest/kafka_offsets_snapshot.json`
   - `evidence/runs/<platform_run_id>/rtdl_core/offsets_snapshot.json`.
4. M8 control-plane evidence root for `m8_g_replay_reconciliation_snapshot.json`.

Preparation checks (fail-closed):
1. Validate `M8.F` pass posture and run-scope match.
2. Validate all required JSON objects above are readable and parseable.
3. Validate replay-anchors source refs resolve to readable objects under the same run scope.
4. Validate required handle values are concrete (no placeholder/wildcard) before evaluation.

Deterministic verification algorithm (M8.G):
1. Load `M8.F` pass snapshot; fail on missing/invalid/pass-mismatch -> `M8G-B4`.
2. Load and parse:
   - `run_report.json`,
   - `reconciliation.json`,
   - `replay_anchors.json`,
   - offset snapshots referenced by replay-anchors source refs.
3. Enforce run-scope conformance across all loaded payloads (`platform_run_id` equals active run scope).
4. Replay-anchor structure checks:
   - required keys exist: `anchors.ingest`, `anchors.rtdl_core`, `counts.ingest_anchors`, `counts.rtdl_anchors`, `source_refs.ingest_offsets_ref`, `source_refs.rtdl_offsets_ref`,
   - counts match array lengths:
     - `counts.ingest_anchors == len(anchors.ingest)`
     - `counts.rtdl_anchors == len(anchors.rtdl_core)`,
   - each anchor row (if present) includes topic/partition/offset fields with non-negative offsets.
5. Expected-anchor lower-bound checks derived from upstream offsets:
   - ingest expected lower-bound = count of ingest topic-partitions where `run_end_offset >= 0` or `watermark_high > 0`,
   - rtdl expected lower-bound = count of rtdl rows where `run_end_offset >= 0` or `watermark_high > 0`,
   - fail if actual anchor counts are below derived lower-bounds.
6. Reconciliation coherence checks:
   - `status == PASS`,
   - all boolean checks in `checks` map are true,
   - deltas are non-negative for:
     - `sent_minus_received`,
     - `received_minus_admit`,
     - `decision_minus_outcome`,
   - arithmetic identity checks from `run_report`:
     - `run_report.ingress.sent - run_report.ingress.received == reconciliation.deltas.sent_minus_received`,
     - `run_report.ingress.received - run_report.ingress.admit == reconciliation.deltas.received_minus_admit`,
     - `run_report.rtdl.decision - run_report.rtdl.outcome == reconciliation.deltas.decision_minus_outcome`.
7. Emit `m8_g_replay_reconciliation_snapshot.json` locally and publish durably.
8. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Validate replay anchor structure and derived lower-bound coherence against upstream offsets.
2. Validate reconciliation arithmetic + check-map posture against `run_report`.
3. Validate no impossible negative deltas or cross-artifact run-scope drift.
4. Emit `m8_g_replay_reconciliation_snapshot.json`.

DoD:
- [x] Replay anchors are structurally complete and coherent.
- [x] Reconciliation results are coherent with upstream evidence.
- [x] Snapshot exists locally and durably.

Blocker Codes (Taxonomy):
1. `M8G-B1`: replay anchor fields missing/incoherent.
2. `M8G-B2`: reconciliation mismatch beyond allowed rules.
3. `M8G-B3`: snapshot write/upload failure.
4. `M8G-B4`: `M8.F` prerequisite or run-scope gate failed.
5. `M8G-B5`: evidence-handle resolution/preparation check failed.

Required snapshot fields (`m8_g_replay_reconciliation_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_m8f_snapshot_local`, `source_m8f_snapshot_uri`.
3. `artifact_refs` (`run_report`, `reconciliation`, `replay_anchors`, `ingest_offsets`, `rtdl_offsets`).
4. `anchor_structure_checks`, `anchor_expected_lower_bounds`, `anchor_count_checks`.
5. `reconciliation_checks`, `delta_checks`, `cross_artifact_identity_checks`.
6. `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M8.G` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Planning status:
1. `M8.G` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. Runtime execution is complete with pass closure.

Execution closure (2026-02-19):
1. Execution id: `m8_20260219T114220Z`.
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m8/m8_20260219T114220Z/m8_g_replay_reconciliation_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T114220Z/m8_g_replay_reconciliation_snapshot.json`.
3. Outcomes:
   - `overall_pass=true`,
   - blockers empty,
   - run-scope checks passed across all source artifacts.
4. Replay-anchor coherence outcomes:
   - required keys present,
   - count parity passed (`counts` match anchor arrays),
   - derived lower-bounds from offsets:
     - ingest expected min `0`, actual `0`,
     - rtdl expected min `0`, actual `0`,
     - both lower-bound checks passed.
5. Reconciliation coherence outcomes:
   - `status=PASS`,
   - all boolean checks true,
   - non-negative deltas passed,
   - cross-artifact arithmetic identity checks passed.
6. Phase posture:
   - `M8.G` is closed,
   - `M8.H` is unblocked.

### M8.H Closure Marker + Obs/Gov Surface Verification
Goal:
1. Confirm closure marker and governance outputs satisfy P11 close condition.

Entry conditions:
1. `M8.G` is pass with blockers empty.
2. Active run scope is pinned to:
   - `platform_run_id=platform_20260213T214223Z`.
3. No unresolved blockers remain from `M8.G`.

Required inputs:
1. `M8.G` pass snapshot (local preferred, durable fallback).
2. Run-scoped closure artifacts:
   - `evidence/runs/<platform_run_id>/run_completed.json`
   - `evidence/runs/<platform_run_id>/obs/environment_conformance.json`
   - `evidence/runs/<platform_run_id>/obs/anomaly_summary.json`
   - `evidence/runs/<platform_run_id>/obs/governance/events.jsonl`.
3. Referenced closure-ref artifacts from `run_completed.json`:
   - `obs/run_report.json`
   - `obs/reconciliation.json`
   - `obs/replay_anchors.json`.
4. M8 control-plane evidence root for `m8_h_obs_gov_closure_snapshot.json`.

Preparation checks (fail-closed):
1. Validate `M8.G` pass posture and run-scope match.
2. Validate all required objects are readable.
3. Validate closure refs in `run_completed.json` are non-empty and run-scoped.
4. Validate required handle values are concrete (no placeholder/wildcard) before evaluation.

Deterministic verification algorithm (M8.H):
1. Load `M8.G` pass snapshot; fail on missing/invalid/pass-mismatch -> `M8H-B4`.
2. Load and parse:
   - `run_completed.json`
   - `environment_conformance.json`
   - `anomaly_summary.json`
   - referenced closure-ref JSON objects (`run_report`, `reconciliation`, `replay_anchors`).
3. Enforce closure-marker checks:
   - `status == COMPLETED`,
   - `platform_run_id` equals active run scope,
   - `closure_refs` includes required refs:
     - `run_report_ref`,
     - `reconciliation_ref`,
     - `replay_anchors_ref`,
     - `environment_conformance_ref`,
     - `anomaly_summary_ref`,
     - `governance_events_ref`,
   - each closure ref resolves to readable object under the same run scope.
4. Enforce Obs output checks:
   - `environment_conformance.status == PASS`,
   - every check row in `environment_conformance.checks` has `status == PASS`,
   - `anomaly_summary.status == PASS`,
   - `anomaly_summary.anomaly_total >= 0`,
   - `anomaly_summary.anomaly_total == sum(anomaly_summary.anomaly_counts[*])`.
5. Enforce derived-summary boundary checks (no base-truth mutation signal):
   - `run_completed`, `environment_conformance`, and `anomaly_summary` top-level keys remain contract-bounded summary keys (no raw event payload arrays/maps),
   - closure refs resolve to Obs/Gov summary surfaces only (`obs/*` and `run_completed.json`), not mutable base-truth stores.
6. Governance surface checks:
   - `obs/governance/events.jsonl` exists and is readable,
   - sample parse check passes for first N lines (N>=50) with required event fields:
     - `event_id`,
     - `event_family`,
     - `ts_utc`,
     - `pins.platform_run_id`,
   - sampled governance rows are run-scoped (`pins.platform_run_id == active run scope`),
   - at least one `RUN_REPORT_GENERATED` event exists in sampled or full scan result.
7. Emit `m8_h_obs_gov_closure_snapshot.json` locally and publish durably.
8. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Validate closure marker shape, status, run scope, and closure-ref resolvability.
2. Validate environment-conformance and anomaly-summary PASS posture and numeric coherence.
3. Validate governance surface readability + schema/run-scope sample checks.
4. Validate derived-summary boundary posture (no base-truth mutation signal).
5. Emit `m8_h_obs_gov_closure_snapshot.json`.

DoD:
- [x] Closure marker exists with correct run scope.
- [x] Environment-conformance and anomaly-summary outputs are present and valid.
- [x] Derived-summary boundary checks pass (no base-truth mutation signal).
- [x] Snapshot exists locally and durably.

Blocker Codes (Taxonomy):
1. `M8H-B1`: closure marker missing/invalid.
2. `M8H-B2`: required Obs/Gov output missing/invalid.
3. `M8H-B3`: snapshot write/upload failure.
4. `M8H-B4`: `M8.G` prerequisite or run-scope gate failed.
5. `M8H-B5`: evidence-handle resolution/preparation check failed.
6. `M8H-B6`: derived-summary boundary violation.

Required snapshot fields (`m8_h_obs_gov_closure_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_m8g_snapshot_local`, `source_m8g_snapshot_uri`.
3. `artifact_refs` (`run_completed`, `environment_conformance`, `anomaly_summary`, `governance_events`, `run_report`, `reconciliation`, `replay_anchors`).
4. `closure_marker_checks`, `closure_ref_checks`.
5. `env_conformance_checks`, `anomaly_summary_checks`.
6. `governance_surface_checks`, `derived_summary_boundary_checks`.
7. `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M8.H` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Planning status:
1. `M8.H` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. Runtime execution is complete with pass closure.

Execution closure (2026-02-19):
1. Execution id: `m8_20260219T120213Z`.
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m8/m8_20260219T120213Z/m8_h_obs_gov_closure_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T120213Z/m8_h_obs_gov_closure_snapshot.json`.
3. Outcomes:
   - `overall_pass=true`,
   - blockers empty,
   - closure-marker, Obs outputs, governance surface, and derived-summary checks all passed.
4. Key verification outcomes:
   - closure marker (`run_completed.json`) exists, parseable, `status=COMPLETED`, run-scoped, and includes all required closure refs,
   - environment conformance is `PASS` with all check rows `PASS`,
   - anomaly summary is `PASS` with coherent numeric totals,
   - governance surface parse checks passed for first `50` sampled rows with required fields and run scope,
   - governance surface includes `RUN_REPORT_GENERATED`,
   - derived-summary boundary checks passed (contract-bounded keys, allowed closure-ref surfaces only, no raw payload fields).
5. Phase posture:
   - `M8.H` is closed,
   - `M8.I` is unblocked.

### M8.I P11 Verdict + M9 Handoff
Goal:
1. Compute deterministic M8 verdict and publish M9 handoff artifact.

Entry conditions:
1. `M8.H` is pass with blockers empty:
   - local: `runs/dev_substrate/m8/m8_20260219T120213Z/m8_h_obs_gov_closure_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T120213Z/m8_h_obs_gov_closure_snapshot.json`.
2. Active run scope is pinned to:
   - `platform_run_id=platform_20260213T214223Z`.
3. No unresolved blockers remain from `M8.H`.

Required inputs:
1. Pass snapshots for `M8.A..M8.H` (local preferred, durable fallback):
   - `M8.A`: `runs/dev_substrate/m8/m8_20260219T075228Z/m8_a_handle_closure_snapshot.json`
   - `M8.B`: `runs/dev_substrate/m8/m8_20260219T080757Z/m8_b_reporter_readiness_snapshot.json`
   - `M8.C`: `runs/dev_substrate/m8/m8_20260219T082913Z/m8_c_input_readiness_snapshot.json`
   - `M8.D`: `runs/dev_substrate/m8/m8_20260219T093130Z/m8_d_single_writer_probe_snapshot.json`
   - `M8.E`: `runs/dev_substrate/m8/m8_20260219T111715Z/m8_e_reporter_execution_snapshot.json`
   - `M8.F`: `runs/dev_substrate/m8/m8_20260219T111902Z/m8_f_bundle_completeness_snapshot.json`
   - `M8.G`: `runs/dev_substrate/m8/m8_20260219T114220Z/m8_g_replay_reconciliation_snapshot.json`
   - `M8.H`: `runs/dev_substrate/m8/m8_20260219T120213Z/m8_h_obs_gov_closure_snapshot.json`.
2. Durable run-control evidence root for `m8_i_verdict_snapshot.json` and `m9_handoff_pack.json`.
3. M8 run-scoped closure root:
   - `evidence/runs/<platform_run_id>/`.

Preparation checks (fail-closed):
1. Validate all source snapshots above are readable and parseable.
2. Validate all source snapshots are run-scoped to active `platform_run_id`.
3. Validate source snapshots include required fields:
   - `phase`, `phase_id`, `platform_run_id`, `overall_pass`, `blockers`.
4. Validate required durable evidence root values are concrete (no placeholder/wildcard).

Deterministic verification algorithm (M8.I):
1. Load `M8.A..M8.H` source snapshots; any missing/unreadable/parse failure -> `M8I-B1`.
2. Enforce run-scope conformance across all source snapshots (`platform_run_id` equals active run scope); mismatch -> `M8I-B2`.
3. Build deterministic source matrix in fixed phase order:
   - `M8.A`, `M8.B`, `M8.C`, `M8.D`, `M8.E`, `M8.F`, `M8.G`, `M8.H`.
4. Roll up blockers from all source snapshots:
   - `source_blocker_rollup = union(source.blockers for all phases)`.
5. Compute P11 predicate map from source pass posture:
   - `p11_handles_closed = M8.A.overall_pass`,
   - `single_writer_verified = M8.D.overall_pass AND M8.E.overall_pass`,
   - `closure_bundle_complete = M8.F.overall_pass`,
   - `replay_reconciliation_coherent = M8.G.overall_pass`,
   - `closure_marker_valid = M8.H.overall_pass`,
   - `obs_outputs_valid = M8.H.overall_pass`.
6. Evaluate verdict:
   - if every predicate above is true and `source_blocker_rollup` is empty -> `ADVANCE_TO_M9`,
   - else -> `HOLD_M8`.
7. Non-secret policy checks for handoff payload:
   - payload contains refs/ids/verdict only (no secrets/tokens/credentials),
   - fail on any key/value matching secret-bearing patterns (`secret`, `password`, `token`, `AKIA`, private key markers) -> `M8I-B5`.
8. Emit `m8_i_verdict_snapshot.json` locally and publish durably.
9. Emit `m9_handoff_pack.json` locally and publish durably.
10. Return `overall_pass=true` only when:
   - verdict is `ADVANCE_TO_M9`,
   - blockers list is empty,
   - both artifacts are written and durably published.

Tasks:
1. Build source snapshot matrix from `M8.A..M8.H`.
2. Compute deterministic predicate map + blocker rollup.
3. Compute verdict and emit `m8_i_verdict_snapshot.json`.
4. Build non-secret handoff payload and emit `m9_handoff_pack.json`.
5. Publish both artifacts locally and durably.

DoD:
- [ ] M8 verdict snapshot is deterministic and reproducible.
- [ ] M9 handoff artifact is complete and non-secret.
- [ ] Both artifacts exist locally and durably.

Blocker Codes (Taxonomy):
1. `M8I-B1`: source snapshot missing/unreadable.
2. `M8I-B2`: predicate evaluation incomplete/invalid.
3. `M8I-B3`: blocker rollup non-empty.
4. `M8I-B4`: verdict/handoff write or upload failure.
5. `M8I-B5`: handoff payload non-secret policy violation.

Required snapshot fields (`m8_i_verdict_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_snapshot_refs` (map for `M8.A..M8.H` local + durable refs).
3. `source_phase_matrix` (phase -> `overall_pass`, `blockers`, `phase_id`).
4. `source_blocker_rollup`.
5. `p11_predicates`.
6. `verdict`.
7. `blockers`, `overall_pass`, `elapsed_seconds`.

Required handoff fields (`m9_handoff_pack.json`):
1. `handoff_id`, `generated_at_utc`, `platform_run_id`.
2. `m8_verdict`, `m8_overall_pass`, `m8_execution_id`.
3. `source_verdict_snapshot_uri`.
4. `phase_pass_matrix` (`M8.A..M8.H`).
5. `required_evidence_refs`:
   - run-scoped closure root,
   - `run_completed`,
   - `obs/run_report`,
   - `obs/reconciliation`,
   - `obs/replay_anchors`,
   - `obs/environment_conformance`,
   - `obs/anomaly_summary`.
6. `m9_entry_gate`:
   - `required_verdict=ADVANCE_TO_M9`,
   - `required_overall_pass=true`.
7. `non_secret_policy`:
   - `pass=true|false`,
   - `violations`.

Runtime budget:
1. `M8.I` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Planning status:
1. `M8.I` is now execution-grade (entry/precheck/algorithm/snapshot + handoff contract pinned).
2. Runtime execution is pending.

## 6) Runtime Budget Gates
1. `M8.A`: <= 10 minutes
2. `M8.B`: <= 10 minutes
3. `M8.C`: <= 10 minutes
4. `M8.D`: <= 15 minutes
5. `M8.E`: <= 15 minutes
6. `M8.F`: <= 10 minutes
7. `M8.G`: <= 10 minutes
8. `M8.H`: <= 10 minutes
9. `M8.I`: <= 10 minutes
10. M8 total target: <= 100 minutes wall clock

Rule:
1. Any over-budget lane remains fail-closed unless USER waiver is explicitly recorded.

## 7) M8 Evidence Contract (Pinned for Execution)
Evidence roots:
1. Run-scoped evidence root:
   - `evidence/runs/<platform_run_id>/`
2. M8 control-plane evidence root:
   - `evidence/dev_min/run_control/<m8_execution_id>/`
3. `<m8_execution_id>` format:
   - `m8_<YYYYMMDDTHHmmssZ>`.

Minimum run-scoped closure artifacts:
1. `evidence/runs/<platform_run_id>/run_completed.json`
2. `evidence/runs/<platform_run_id>/obs/run_report.json`
3. `evidence/runs/<platform_run_id>/obs/reconciliation.json`
4. `evidence/runs/<platform_run_id>/obs/replay_anchors.json`
5. `evidence/runs/<platform_run_id>/obs/environment_conformance.json`
6. `evidence/runs/<platform_run_id>/obs/anomaly_summary.json`

Minimum M8 control-plane artifacts:
1. `evidence/dev_min/run_control/<m8_execution_id>/m8_a_handle_closure_snapshot.json`
2. `evidence/dev_min/run_control/<m8_execution_id>/m8_b_reporter_readiness_snapshot.json`
3. `evidence/dev_min/run_control/<m8_execution_id>/m8_c_input_readiness_snapshot.json`
4. `evidence/dev_min/run_control/<m8_execution_id>/m8_d_single_writer_probe_snapshot.json`
5. `evidence/dev_min/run_control/<m8_execution_id>/m8_e_reporter_execution_snapshot.json`
6. `evidence/dev_min/run_control/<m8_execution_id>/m8_f_bundle_completeness_snapshot.json`
7. `evidence/dev_min/run_control/<m8_execution_id>/m8_g_replay_reconciliation_snapshot.json`
8. `evidence/dev_min/run_control/<m8_execution_id>/m8_h_obs_gov_closure_snapshot.json`
9. `evidence/dev_min/run_control/<m8_execution_id>/m8_i_verdict_snapshot.json`
10. `evidence/dev_min/run_control/<m8_execution_id>/m9_handoff_pack.json`

Notes:
1. M8 artifacts must be non-secret.
2. Any secret-bearing payload in M8 artifacts is a hard blocker.
3. Missing required evidence object keeps M8 in `HOLD_M8`.

## 8) M8 Completion Checklist
- [x] M8.A complete
- [x] M8.B complete
- [x] M8.C complete
- [x] M8.D complete
- [x] M8.E complete
- [x] M8.F complete
- [x] M8.G complete
- [x] M8.H complete
- [ ] M8.I complete

## 9) Exit Criteria
M8 can be marked `DONE` only when:
1. Section 8 checklist is fully complete.
2. Required run-scoped and control-plane artifacts are durable and readable.
3. `m8_i_verdict_snapshot.json` has `verdict=ADVANCE_TO_M9` and `overall_pass=true`.
4. `m9_handoff_pack.json` is published and non-secret.
5. USER confirms progression to M9 activation.

Note:
1. This file does not change phase status.
2. Status transition is made only in `platform.build_plan.md`.

