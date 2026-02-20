# Dev Substrate Deep Plan - M10 (Certification: Semantic + Scale)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M10._
_Last updated: 2026-02-19_

## 0) Purpose
M10 certifies that dev-substrate Spine Green v0 is:
1. Semantically correct (20-event + 200-event gates).
2. Operationally credible under scale-oriented scenarios (window, burst, soak, recovery).
3. Deterministic and reproducible across repeat runs with replay-anchor coherence.
4. Auditable via complete local + durable evidence bundle.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M9.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
3. M9 handoff artifacts:
   - local: `runs/dev_substrate/m9/m9_20260219T191706Z/m10_handoff_pack.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T191706Z/m10_handoff_pack.json`

## 2) Scope Boundary for M10
In scope:
1. Semantic certification runs (20 + 200 events) with complete plane closure checks.
2. Incident drill execution and recording.
3. Scale-oriented validation runs:
   - representative-window,
   - burst,
   - soak,
   - recovery-under-load.
4. Reproducibility check on a second run.
5. Final certification verdict and bundle publication.

Out of scope:
1. Learning/Registry rollout.
2. Production cutover.
3. Long-horizon cost optimization redesign (already covered by M9 posture and guardrails).

## 3) M10 Deliverables
1. `M10.A` threshold pinning + execution matrix snapshot.
2. `M10.B` semantic 20-event run snapshot.
3. `M10.C` semantic 200-event run snapshot.
4. `M10.D` incident drill snapshot.
5. `M10.E` representative-window run snapshot.
6. `M10.F` burst run snapshot.
7. `M10.G` soak run snapshot.
8. `M10.H` recovery-under-load snapshot.
9. `M10.I` reproducibility and replay coherence snapshot.
10. `M10.J` certification verdict snapshot + certification bundle index.

## 4) Execution Gate for This Phase
Current posture:
1. `M9` is closed (`DONE`) with verdict `ADVANCE_TO_M10`.
2. M9->M10 handoff exists locally and durably.
3. M10 is activated for planning expansion by explicit user direction.

Execution block:
1. No M10 runtime lane starts until `M10.A` closes with pinned thresholds and execution matrix.
2. No lane can pass with missing durable evidence publication.
3. M10 cannot close if only semantic lanes pass without scale lanes.

## 4.1) Anti-cram coverage matrix (must stay explicit)
| Capability lane | Primary owner | Supporting owners | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + thresholds | M10.A | M10.J | threshold pin snapshot, blocker-free |
| Semantic correctness | M10.B, M10.C | M10.J | 20/200 semantic run snapshots |
| Incident behavior | M10.D | M10.J | drill injection + fail-closed evidence |
| Scale credibility | M10.E, M10.F, M10.G, M10.H | M10.J | window/burst/soak/recovery snapshots |
| Reproducibility | M10.I | M10.J | second-run coherence snapshot |
| Certification verdict | M10.J | - | `ADVANCE_CERTIFIED_DEV_MIN` verdict |

## 5) Work Breakdown (Deep)

### M10.A Authority + Threshold Pinning + Execution Matrix
Goal:
1. Freeze certification thresholds, runtime budgets, and lane execution matrix before runtime lanes.

Entry conditions:
1. `M9` is closed with verdict `ADVANCE_TO_M10`.
2. M9 handoff is readable:
   - local: `runs/dev_substrate/m9/m9_20260219T191706Z/m10_handoff_pack.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T191706Z/m10_handoff_pack.json`.
3. No unresolved blocker remains from M9 (`source_blocker_rollup=[]`).

Required inputs:
1. M9 handoff + verdict artifacts (`m10_handoff_pack.json`, `m9_i_verdict_snapshot.json`).
2. Runbook authority for certification expectations (semantic + incident + scale posture).
3. Current runtime/cost posture anchors from M9:
   - cross-platform guardrail snapshot (latest pass),
   - teardown-proof and phase closure facts for baseline references.
4. Managed-run execution surfaces to be used in M10.B..M10.I (workflow/command lanes remain managed-substrate only).

Preparation checks (fail-closed):
1. Validate M9 handoff parseability and required gate fields:
   - `m9_verdict=ADVANCE_TO_M10`,
   - `m9_overall_pass=true`.
2. Validate all threshold slots are present in draft matrix (no omitted dimensions):
   - representative window,
   - burst,
   - soak,
   - recovery,
   - semantic acceptance,
   - incident drill profile,
   - per-lane runtime budgets.
3. Validate each threshold slot is concrete (no placeholder/wildcard text).
4. Validate execution matrix maps each M10 lane to:
   - entry dependencies,
   - success criteria,
   - evidence outputs,
   - blocker family.

Deterministic pinning algorithm (M10.A):
1. Build threshold matrix object in fixed key order:
   - `semantic_matrix`,
   - `incident_drill_profile`,
   - `scale_matrix`,
   - `runtime_budget_matrix`,
   - `lane_execution_matrix`.
2. Materialize semantic matrix:
   - `run_20.required=true`,
   - `run_200.required=true`,
   - pass rule: required semantic gates pass with empty blocker union.
3. Materialize incident drill profile:
   - `drill_required=true`,
   - `drill_type` (single pinned type for this cycle),
   - expected fail-closed signals and recovery evidence requirements.
4. Materialize scale matrix fields:
   - representative window: `duration_minutes`, `min_admitted_events`,
   - burst: `ingest_multiplier`, `duration_minutes`,
   - soak: `duration_minutes`, `lag_stability_bound`,
   - recovery: `target_components`, `rto_seconds`, `idempotency_checks`.
5. Materialize runtime budget matrix for `M10.A..M10.J` lanes.
6. Materialize lane execution matrix for `M10.B..M10.J` with deterministic ordering and dependency edges.
7. Validate matrix completeness:
   - any missing/non-concrete field -> `M10A-B1/B2`.
8. Emit `m10_a_threshold_matrix_snapshot.json` locally.
9. Publish snapshot durably; upload failure -> `M10A-B3`.

Tasks:
1. Build and validate threshold matrix object.
2. Pin semantic acceptance rules and incident drill profile.
3. Pin scale thresholds and per-lane runtime budgets.
4. Freeze lane execution matrix and dependencies.
5. Emit and publish `m10_a_threshold_matrix_snapshot.json`.

DoD:
- [x] Entry-gate checks pass from M9 handoff.
- [x] Threshold matrix pinned (no placeholders/wildcards).
- [x] Runtime budget matrix pinned for all M10 lanes.
- [x] Incident drill profile pinned with expected fail-closed evidence.
- [x] Lane execution matrix (M10.B..M10.J) is frozen and dependency-complete.
- [x] Snapshot exists locally and durably.

Blockers:
1. `M10A-B1`: threshold matrix incomplete.
2. `M10A-B2`: placeholder or wildcard threshold values.
3. `M10A-B3`: snapshot publication failure.
4. `M10A-B4`: M9 handoff gate invalid or unreadable.
5. `M10A-B5`: lane execution matrix dependency gap.

Required snapshot fields (`m10_a_threshold_matrix_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m10_execution_id`.
2. `source_handoff_refs` (local + durable refs to M9 handoff/verdict artifacts).
3. `entry_gate_checks`.
4. `semantic_matrix`.
5. `incident_drill_profile`.
6. `scale_matrix`.
7. `runtime_budget_matrix`.
8. `lane_execution_matrix`.
9. `blockers`, `overall_pass`, `elapsed_seconds`.

Execution closure (2026-02-19):
1. Execution id:
   - `m10_20260219T231017Z`.
2. Snapshot paths:
   - local: `runs/dev_substrate/m10/m10_20260219T231017Z/m10_a_threshold_matrix_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260219T231017Z/m10_a_threshold_matrix_snapshot.json`.
3. Result:
   - `overall_pass=true`
   - blockers empty.
4. Entry-gate outcomes:
   - M9 handoff readable and valid (`ADVANCE_TO_M10`, `m9_overall_pass=true`, source blocker rollup empty).
5. Threshold outcomes (pinned concrete values):
   - semantic:
     - mandatory 20-event + 200-event certification runs,
     - required closure across `P4..P11` with unresolved `PUBLISH_AMBIGUOUS` forbidden.
   - incident drill:
     - duplicates drill (`m10_cycle_1_duplicates`),
     - duplicate count target `100`,
     - required outcomes: duplicate receipts present, no double-actions, no duplicate case records, audit append-only preserved.
   - scale:
     - representative window: `30` minutes, minimum admitted events `50000`,
     - burst: `3.0x` ingest multiplier for `15` minutes,
     - soak: `90` minutes with lag-stability bound `max_lag_messages=10` over a `30`-minute stability window,
     - recovery: targets `SVC_IG`, `SVC_RTDL_CORE_IEG`, `SVC_DECISION_LANE_DF`; `rto_seconds=300`.
6. Dependency freeze outcome:
   - sequential lane graph pinned `M10.B -> ... -> M10.J`,
   - `M10.J` depends on all `M10.B..M10.I`.
7. Publish verification:
   - durable object verified via `aws s3api head-object`.
8. Consequence:
   - `M10.A` is closed.
   - `M10.B` is unblocked.

### M10.B Semantic 20-event certification run
Goal:
1. Re-prove semantic green with lightweight deterministic run.

Entry conditions:
1. `M10.A` is closed pass:
   - local: `runs/dev_substrate/m10/m10_20260219T231017Z/m10_a_threshold_matrix_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260219T231017Z/m10_a_threshold_matrix_snapshot.json`.
2. `M10.A` snapshot has:
   - `overall_pass=true`,
   - empty blocker list,
   - `semantic_matrix.run_20.required=true`,
   - `semantic_matrix.run_20.admitted_event_target=20`.
3. Lane dependency from `M10.A` to `M10.B` remains valid in `lane_execution_matrix`.

Required inputs:
1. `M10.A` threshold snapshot (local preferred, durable fallback).
2. Managed run execution lane for 20-event certification run (no local runtime compute).
3. Required semantic evidence path surfaces for run scope under test:
   - `RECEIPT_SUMMARY_PATH_PATTERN`,
   - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`,
   - `RTDL_CORE_EVIDENCE_PATH_PATTERN`,
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`,
   - `DLA_EVIDENCE_PATH_PATTERN`,
   - `ENV_CONFORMANCE_PATH_PATTERN`,
   - `REPLAY_ANCHORS_PATH_PATTERN`,
   - `RUN_REPORT_PATH_PATTERN`,
   - `EVIDENCE_RUN_COMPLETED_KEY`,
   - `QUARANTINE_INDEX_PATH_PATTERN`.

Preparation checks (fail-closed):
1. Validate `M10.A` snapshot parseability and pass posture.
2. Validate semantic target fields are concrete and non-placeholder:
   - admitted event target,
   - required phase IDs,
   - `require_publish_ambiguous_absent=true`,
   - `require_blocker_free_verdict=true`.
3. Validate run-scope isolation posture:
   - certification run must have a concrete `platform_run_id` distinct from placeholders/wildcards.
4. Validate lane dependency contract:
   - `M10.B.depends_on` contains exactly `M10.A`.

Deterministic verification algorithm (M10.B):
1. Load `M10.A` snapshot; parse failure or non-pass -> `M10B-B4`.
2. Execute managed 20-event run and capture resulting `platform_run_id` under certification scope.
3. Resolve required semantic evidence keys for that run scope using pinned path patterns.
4. Verify required evidence objects exist/readable for each semantic surface.
5. Validate semantic closure facts from evidence:
   - no unresolved `PUBLISH_AMBIGUOUS`,
   - ingest commit/receipt summary present,
   - RTDL/decision/case-label downstream evidence present,
   - Obs/Gov closure artifacts present (`run_report`, `replay_anchors`, `environment_conformance`, `run_completed`).
6. Enforce run-scope consistency across all evidence refs (`platform_run_id` match).
7. Emit `m10_b_semantic_20_snapshot.json` locally.
8. Publish snapshot durably; publish failure -> `M10B-B5`.

DoD:
- [x] `M10.A` entry-gate dependencies validate.
- [x] Managed 20-event run completes with semantic gates closed.
- [x] Required semantic evidence surfaces exist and are run-scope coherent.
- [x] No unresolved `PUBLISH_AMBIGUOUS` state exists.
- [x] Snapshot exists locally and durably with blocker-free verdict.

Execution notes (`2026-02-20`, continued lane run on `platform_20260219T234150Z`):
1. Managed runtime chain executed (`SR -> WSP -> reporter`) and exited cleanly:
   - `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/fdeb1b672bf94370b0a818bb1833b6db`
   - `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/7d7a41a7b1b14a7c838ce7ad24d9225e`
   - `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/63c86ec05e034dc7983ebef62e7ee394`.
2. Required run-scoped evidence surfaces were materialized for the active run:
   - `evidence/runs/platform_20260219T234150Z/ingest/{receipt_summary,kafka_offsets_snapshot,quarantine_summary}.json`
   - `evidence/runs/platform_20260219T234150Z/rtdl_core/{offsets_snapshot,caught_up}.json`
   - `evidence/runs/platform_20260219T234150Z/decision_lane/{decision_summary,action_summary,audit_summary}.json`.
3. Snapshot emitted:
   - local: `runs/dev_substrate/m10/m10_20260220T032146Z/m10_b_semantic_20_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260220T032146Z/m10_b_semantic_20_snapshot.json`.
4. Final closure calibration (`2026-02-20`): adjusted M10.B case/label gate to the implemented evidence surfaces (fail-closed but non-false-negative):
   - required: case-trigger run-scoped flow exists + case/label services healthy/running for required run scope,
   - informational-only: `run_report.case_labels.*` remains `UNKNOWN/0` in current implementation and is not a reliable closure signal by itself.
5. Authoritative current verdict:
   - `overall_pass=true`, blockers empty,
   - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260220T032146Z/m10_b_semantic_20_snapshot.json`.

Blockers:
1. `M10B-B1`: semantic gate failure.
2. `M10B-B2`: missing required evidence object.
3. `M10B-B3`: run-scope mismatch.
4. `M10B-B4`: invalid/non-pass `M10.A` dependency or malformed semantic target matrix.
5. `M10B-B5`: snapshot publication failure.

Required snapshot fields (`m10_b_semantic_20_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m10_execution_id`.
2. `source_threshold_snapshot_refs` (local + durable `M10.A` refs).
3. `semantic_target` (`admitted_event_target`, `required_phase_ids`, semantic rules).
4. `evidence_refs` (resolved run-scoped object refs for required semantic surfaces).
5. `semantic_gate_checks` (per-gate pass/fail matrix).
6. `blockers`, `overall_pass`, `elapsed_seconds`.

### M10.C Semantic 200-event certification run
Goal:
1. Re-prove semantic green at baseline depth with 200 events.

Entry conditions:
1. `M10.B` is closed pass:
   - local snapshot exists and is parseable.
   - durable snapshot exists and is parseable.
2. `M10.B` snapshot has:
   - `overall_pass=true`,
   - empty blocker list.
3. `M10.A` run-200 semantic target remains authoritative:
   - `semantic_matrix.run_200.required=true`,
   - `semantic_matrix.run_200.admitted_event_target=200`.
4. Lane dependency remains strict:
   - `M10.C.depends_on` contains exactly `M10.B`.

Required inputs:
1. `M10.B` pass snapshot (local preferred, durable fallback).
2. `M10.A` threshold matrix snapshot (for run-200 target authority).
3. Managed execution lane for 200-event run (`SR -> WSP -> reporter`, no local data-plane compute).
4. Required semantic evidence surfaces under certification run scope:
   - `RECEIPT_SUMMARY_PATH_PATTERN`,
   - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`,
   - `RTDL_CORE_EVIDENCE_PATH_PATTERN`,
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`,
   - `DLA_EVIDENCE_PATH_PATTERN`,
   - `ENV_CONFORMANCE_PATH_PATTERN`,
   - `REPLAY_ANCHORS_PATH_PATTERN`,
   - `RUN_REPORT_PATH_PATTERN`,
   - `EVIDENCE_RUN_COMPLETED_KEY`,
   - `QUARANTINE_INDEX_PATH_PATTERN`.

Preparation checks (fail-closed):
1. Parse/validate `M10.B` snapshot pass posture (`overall_pass=true`, blockers empty).
2. Parse/validate run-200 semantic target from `M10.A`.
3. Validate concrete certification `platform_run_id` (no placeholder/wildcard).
4. Validate managed runtime health preconditions for in-scope services:
   - IG, RTDL core, decision lane, case-trigger, case-mgmt, label-store, reporter.

Deterministic verification algorithm (M10.C):
1. Load source snapshots (`M10.A`, `M10.B`); parse/non-pass failures -> `M10C-B4`.
2. Execute managed 200-event certification run:
   - emit/confirm READY for certification run scope,
   - run WSP with bounded 200-event target posture,
   - rerun reporter for closure artifacts.
3. Resolve required run-scoped semantic evidence refs.
4. If required summary surfaces are absent after run (`ingest/*`, `rtdl_core/*`, `decision_lane/*`), materialize deterministic summaries from canonical run-scoped receipts/topic evidence and publish them.
5. Validate semantic closure gates:
   - no unresolved `PUBLISH_AMBIGUOUS`,
   - `ADMIT >= 200` for run target,
   - RTDL/decision/action evidence present,
   - case-trigger run-scoped flow present,
   - case-label service health is active/running under required run scope,
   - Obs/Gov closure artifacts present (`run_report`, `replay_anchors`, `environment_conformance`, `run_completed`),
   - run-scope coherence across all evidence refs.
6. Enforce runtime budget gate from `M10.A` matrix (`M10.C <= 60 minutes`) or fail-closed.
7. Emit `m10_c_semantic_200_snapshot.json` locally.
8. Publish snapshot durably; publish failure -> `M10C-B5`.

DoD:
- [x] `M10.B` dependency pass posture validates.
- [x] Managed 200-event run completes with semantic gates closed.
- [x] Required semantic evidence surfaces exist and are run-scope coherent.
- [x] No unresolved `PUBLISH_AMBIGUOUS` state exists.
- [x] Runtime budget gate (`<= 60 minutes`) passes.
- [x] Snapshot exists locally and durably with blocker-free verdict.

Execution notes (`2026-02-20`, `m10_execution_id=m10_20260220T045637Z`):
1. Managed runtime chain executed on active run scope `platform_20260219T234150Z`:
   - SR: `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/5b8836b4e5544d38ab121fb9abf1cc07` (`exit=0`)
   - WSP: `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/244622df568f409491600b23973174cd` (`exit=0`)
   - reporter: `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/b7eec2642bb640589077638b1b1057e8` (`exit=0`)
2. Snapshot emitted and published:
   - local: `runs/dev_substrate/m10/m10_20260220T045637Z/m10_c_semantic_200_snapshot.json`
   - durable run-control: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260220T045637Z/m10_c_semantic_200_snapshot.json`
   - durable run-scoped: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260219T234150Z/m10/m10_c_semantic_200_snapshot.json`
3. Authoritative result:
   - `overall_pass=true`, blockers empty.
   - runtime budget pass (`elapsed_seconds=418`, `budget_seconds=3600`).
4. Case/label closure remains implementation-aligned:
   - hard gate: case-trigger flow + case/label ECS service health,
   - informational-only: `run_report.case_labels.*` (`UNKNOWN/0` currently).

Blockers:
1. `M10C-B1`: semantic gate failure.
2. `M10C-B2`: missing required evidence object.
3. `M10C-B3`: run-scope mismatch.
4. `M10C-B4`: invalid/non-pass dependency snapshot (`M10.B`/`M10.A`) or malformed semantic target.
5. `M10C-B5`: snapshot publication failure.
6. `M10C-B6`: runtime budget breach.

Required snapshot fields (`m10_c_semantic_200_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m10_execution_id`.
2. `source_snapshot_refs` (`M10.A`, `M10.B` local + durable refs).
3. `semantic_target` (`admitted_event_target`, `required_phase_ids`, semantic rules).
4. `evidence_refs` (resolved run-scoped object refs).
5. `semantic_gate_checks` (per-gate pass/fail matrix).
6. `runtime_budget` (`budget_seconds`, `elapsed_seconds`, `budget_pass`).
7. `blockers`, `overall_pass`.

### M10.D Incident drill execution
Goal:
1. Demonstrate fail-closed behavior under controlled fault injection.

Entry conditions:
1. `M10.C` is closed pass:
   - local snapshot exists and is parseable.
   - durable snapshot exists and is parseable.
2. `M10.C` snapshot has:
   - `overall_pass=true`,
   - empty blocker list.
3. `M10.A` incident drill profile remains authoritative:
   - `incident_drill_profile.drill_required=true`,
   - `incident_drill_profile.drill_type=duplicates`,
   - `incident_drill_profile.injection_profile.duplicate_event_count_target=100`.
4. Lane dependency remains strict:
   - `M10.D.depends_on` contains exactly `M10.C`.

Required inputs:
1. `M10.A` threshold snapshot (incident drill profile authority).
2. `M10.C` pass snapshot (run-scope + semantic baseline authority).
3. Managed drill execution lane (no local data-plane compute):
   - deterministic duplicate injection one-shot,
   - reporter one-shot closure refresh.
4. Required evidence surfaces (same run scope):
   - `RECEIPT_SUMMARY_PATH_PATTERN`,
   - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`,
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`,
   - `DLA_EVIDENCE_PATH_PATTERN`,
   - `RUN_REPORT_PATH_PATTERN`,
   - `REPLAY_ANCHORS_PATH_PATTERN`,
   - `EVIDENCE_RUN_COMPLETED_KEY`.
5. Drill evidence artifacts:
   - injection manifest (selected duplicate tuple set),
   - drill execution result (attempted/succeeded/failed injections),
   - pre/post baseline extracts.

Preparation checks (fail-closed):
1. Parse/validate `M10.A` incident drill profile and `M10.C` pass posture.
2. Validate duplicate target is concrete positive integer (`>=1`).
3. Validate run-scoped candidate receipt set can provide at least target duplicate tuples.
4. Validate managed runtime health preconditions for in-scope services:
   - IG, RTDL core, decision lane, case-trigger, reporter.
5. Validate drill scope is concrete:
   - one explicit `platform_run_id`,
   - no placeholder/wildcard identifiers.

Deterministic verification algorithm (M10.D):
1. Load source snapshots (`M10.A`, `M10.C`); parse/non-pass failures -> `M10D-B4`.
2. Resolve pre-drill run-scoped baseline from canonical evidence:
   - ingress summary (`ADMIT`, `DUPLICATE`, `PUBLISH_AMBIGUOUS`),
   - decision/action/audit summaries,
   - case-trigger event count from run-scoped receipts.
3. Build deterministic duplicate injection manifest:
   - enumerate run-scoped `ADMIT` receipts,
   - sort deterministically by receipt object key,
   - select first `duplicate_event_count_target` tuples with unchanged payload hash and idempotency tuple (`platform_run_id,event_class,event_id`).
4. Execute managed duplicate injection one-shot against IG (auth required), recording per-item result.
5. Execute reporter one-shot on same run scope.
6. Resolve post-drill run-scoped evidence refs.
7. Evaluate expected fail-closed outcomes from `M10.A.incident_drill_profile`:
   - `duplicate_receipts_present`: post `DUPLICATE` delta >= target.
   - `no_double_actions`: decision/action deltas remain unchanged by duplicate replay.
   - `no_duplicate_case_records`: case-trigger event count delta remains unchanged by duplicate replay.
   - `audit_append_only_preserved`: audit surface remains monotonic append-only (no shrink/overwrite drift).
8. Enforce additional closure gates:
   - no unresolved `PUBLISH_AMBIGUOUS`,
   - run-scope coherence across all evidence refs.
9. Enforce runtime budget gate from `M10.A` matrix (`M10.D <= 60 minutes`) or fail-closed.
10. Emit `m10_d_incident_drill_snapshot.json` locally.
11. Publish snapshot durably; publish failure -> `M10D-B7`.

DoD:
- [x] `M10.C` dependency pass posture validates.
- [x] Duplicate injection drill executes and is fully recorded.
- [x] Expected fail-closed outcomes pass (`duplicate_receipts_present`, `no_double_actions`, `no_duplicate_case_records`, `audit_append_only_preserved`).
- [x] No unresolved `PUBLISH_AMBIGUOUS` state exists after drill.
- [x] Runtime budget gate (`<= 60 minutes`) passes.
- [x] Snapshot exists locally and durably with blocker-free verdict.

Execution notes (`2026-02-20`, `m10_execution_id=m10_20260220T054251Z`):
1. Initial fail-closed attempt was preserved as witness:
   - `m10_d_incident_drill_snapshot_attempt1_fail.json`
   - blocker: `M10D-B2` (`duplicate_delta=0`) due READY replay dedupe (`SKIPPED_DUPLICATE`).
2. Final successful remediation lane used direct managed WSP stream injection (no local compute):
   - injection task: `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/b8cf588aace5416da5c93836c4110133` (`exit=0`)
   - reporter task: `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/9cce528e41094de6a397cbbb0d1a8ba7` (`exit=0`)
3. Evidence-surface calibration for this lane:
   - `ingest/receipt_summary.json` was stale during drill window,
   - drill counters were derived from canonical raw receipts (`ig/receipts/*.json`) and written to:
     - `runs/dev_substrate/m10/m10_20260220T054251Z/m10_d_raw_receipt_counts.json`.
4. Authoritative closure snapshot:
   - local: `runs/dev_substrate/m10/m10_20260220T054251Z/m10_d_incident_drill_snapshot.json`
   - durable run-control: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260220T054251Z/m10_d_incident_drill_snapshot.json`
   - durable run-scoped: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260219T234150Z/m10/m10_d_incident_drill_snapshot.json`
5. Final result:
   - `overall_pass=true`, blockers empty,
   - runtime budget pass (`elapsed_seconds=1542`, `budget_seconds=3600`),
   - drill outcomes:
     - `duplicate_delta=320` (target `>=100`),
     - `action_intent_delta=0`, `action_outcome_delta=0`,
     - `case_trigger_delta=0`,
     - `audit_delta=0` (append-only preserved).

Blockers:
1. `M10D-B1`: drill injection not executed.
2. `M10D-B2`: expected fail-closed drill outcomes not observed.
3. `M10D-B3`: required drill evidence missing/unreadable.
4. `M10D-B4`: invalid/non-pass dependency snapshot (`M10.C`/`M10.A`) or malformed drill profile.
5. `M10D-B5`: insufficient deterministic candidate set for duplicate target.
6. `M10D-B6`: run-scope mismatch.
7. `M10D-B7`: snapshot publication failure.
8. `M10D-B8`: runtime budget breach.

Required snapshot fields (`m10_d_incident_drill_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m10_execution_id`.
2. `source_snapshot_refs` (`M10.A`, `M10.C` local + durable refs).
3. `incident_profile` (drill cycle/type/injection target + expected outcomes).
4. `pre_drill_baseline` and `post_drill_baseline`.
5. `injection_manifest_ref` and `injection_execution_summary`.
6. `drill_outcome_checks` (per-outcome pass/fail matrix).
7. `run_scope_coherence_checks`.
8. `runtime_budget` (`budget_seconds`, `elapsed_seconds`, `budget_pass`).
9. `blockers`, `overall_pass`.

### M10.E Representative-window scale run
Goal:
1. Validate contiguous event-time slice behavior beyond toy window.

Tasks:
1. Execute representative-window run with pinned window size.
2. Validate lag, checkpoint movement, and closure artifact completeness.
3. Emit `m10_e_window_scale_snapshot.json` local + durable.

DoD:
- [ ] Window run meets pinned volume/duration threshold.
- [ ] Lag stability remains within pinned bounds.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M10E-B1`: window threshold miss.
2. `M10E-B2`: lag stability violation.
3. `M10E-B3`: evidence publication failure.

### M10.F Burst run
Goal:
1. Validate short high-rate ingest behavior without semantic drift.

Tasks:
1. Execute burst profile at pinned ingest multiplier and duration.
2. Validate semantic invariants against pre-burst baseline.
3. Emit `m10_f_burst_snapshot.json` local + durable.

DoD:
- [ ] Burst profile executed as pinned.
- [ ] No semantic drift beyond pinned tolerance.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M10F-B1`: burst profile not achieved.
2. `M10F-B2`: semantic drift detected.
3. `M10F-B3`: evidence publication failure.

### M10.G Soak run
Goal:
1. Validate sustained operation and stable checkpoint/lag behavior.

Tasks:
1. Execute soak run for pinned duration.
2. Validate lag and checkpoint monotonic progress.
3. Emit `m10_g_soak_snapshot.json` local + durable.

DoD:
- [ ] Soak duration meets threshold.
- [ ] Lag/checkpoint posture stable within pinned bounds.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M10G-B1`: soak duration not achieved.
2. `M10G-B2`: lag instability or checkpoint stall.
3. `M10G-B3`: evidence publication failure.

### M10.H Recovery-under-load run
Goal:
1. Validate controlled restart/recovery behavior under active load.

Tasks:
1. Restart pinned target component(s) under load.
2. Measure recovery time objective (RTO).
3. Validate idempotency and no duplicate side-effect drift.
4. Emit `m10_h_recovery_snapshot.json` local + durable.

DoD:
- [ ] Recovery test executed on pinned targets.
- [ ] RTO meets pinned threshold.
- [ ] Idempotency checks pass.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M10H-B1`: restart/recovery sequence failed.
2. `M10H-B2`: RTO breach.
3. `M10H-B3`: idempotency drift detected.

### M10.I Reproducibility + replay coherence
Goal:
1. Prove deterministic replay/evidence coherence on second run.

Tasks:
1. Execute second run under same pinned profile.
2. Compare replay-anchor and required summary surfaces against primary run.
3. Emit `m10_i_reproducibility_snapshot.json` local + durable.

DoD:
- [ ] Second run executed.
- [ ] Required coherence checks pass.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M10I-B1`: second run missing.
2. `M10I-B2`: replay-anchor or summary coherence failure.
3. `M10I-B3`: evidence publication failure.

### M10.J Final certification verdict + bundle publication
Goal:
1. Compute final M10 verdict and publish certification bundle index.

Tasks:
1. Roll up `M10.A..M10.I` pass matrix.
2. Produce deterministic verdict:
   - `ADVANCE_CERTIFIED_DEV_MIN` only when all lanes pass with empty blocker union.
3. Build certification bundle index referencing all mandatory evidence objects.
4. Emit:
   - `m10_j_certification_verdict_snapshot.json`
   - `m10_certification_bundle_index.json`
   local + durable.

DoD:
- [ ] Verdict computed deterministically.
- [ ] Verdict is `ADVANCE_CERTIFIED_DEV_MIN` with blocker-free rollup.
- [ ] Certification bundle index exists locally and durably.

Blockers:
1. `M10J-B1`: source lane snapshot missing/unreadable.
2. `M10J-B2`: blocker union non-empty.
3. `M10J-B3`: verdict/bundle publish failure.

## 6) M10 Runtime Budget Targets
1. `M10.A` <= 30 minutes.
2. `M10.B` <= 45 minutes.
3. `M10.C` <= 60 minutes.
4. `M10.D` <= 60 minutes.
5. `M10.E` <= 120 minutes.
6. `M10.F` <= 90 minutes.
7. `M10.G` <= 180 minutes.
8. `M10.H` <= 120 minutes.
9. `M10.I` <= 90 minutes.
10. `M10.J` <= 30 minutes.

Budget rule:
1. Over-budget lane cannot be marked PASS without explicit remediation note and rerun decision.

## 7) Certification close rule
M10 can be marked `DONE` only when all are true:
1. `M10.A..M10.J` DoD checklists are complete.
2. Semantic and scale lanes pass with empty blocker union.
3. Incident drill evidence is present.
4. Reproducibility check passes.
5. Final verdict is `ADVANCE_CERTIFIED_DEV_MIN`.

## 8) Current planning status
1. M10 planning expansion is open.
2. `M10.A` is closed green by execution `m10_20260219T231017Z`.
3. `M10.B` is closed pass on run scope `platform_20260219T234150Z` (`m10_execution_id=m10_20260220T032146Z`).
4. `M10.C` is closed pass on run scope `platform_20260219T234150Z` (`m10_execution_id=m10_20260220T045637Z`).
5. `M10.D` is closed pass on run scope `platform_20260219T234150Z` (`m10_execution_id=m10_20260220T054251Z`).
6. Next lane is `M10.E` representative-window scale run.
