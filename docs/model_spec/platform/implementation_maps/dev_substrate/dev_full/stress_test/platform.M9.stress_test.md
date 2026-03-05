# Dev Substrate Stress Plan - M9 (P12 LEARNING_INPUT_READY)
_Parent authority: `platform.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-05_
_Current posture: `S0_GREEN` (`M9-ST-S0` executed pass; next gate `M9_ST_S1_READY`)._

## 0) Purpose
M9 stress validates learning-input readiness under realistic production data behavior, deterministic run scope, and cost discipline.

M9 stress must prove:
1. replay basis is explicit and immutable (`origin_offset` ranges and provenance).
2. as-of and label-maturity controls enforce temporal causality.
3. no-future-leakage checks fail closed with evidence-backed reasons.
4. runtime and learning data-surface boundaries are enforced without drift.
5. P12 verdict and M10 handoff are deterministic and reproducible.
6. M9 closure publishes attributable cost-to-outcome evidence with no unexplained spend.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M9.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M8.stress_test.md`
2. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
3. `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.impl_actual.md`

Strict entry authority (current):
1. Parent `M8-ST-S5`: `m8_stress_s5_20260304T234918Z` (`overall_pass=true`, `verdict=ADVANCE_TO_M9`, `next_gate=M9_READY`, `open_blocker_count=0`).
2. Parent `M8-ST-S4`: `m8_stress_s4_20260304T234834Z` (`overall_pass=true`, native `m8a/m8b/m8c` chain green).

Legacy receipts (history only, not closure authority):
1. Historical M9 planning/execution notes in `platform.M9.build_plan.md` dated 2026-02-26.

## 2) Stage-A Findings (M9)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M9-ST-F1` | `PREVENT` | No dedicated M9 stress authority exists in `stress_test/`. | Create and pin `platform.M9.stress_test.md` before any M9 execution. |
| `M9-ST-F2` | `PREVENT` | M9 has ten lanes (`A..J`); missing-lane risk is high if runbook is shallow. | Pin lane ownership and fail-closed coverage checks before S0. |
| `M9-ST-F3` | `PREVENT` | Learning-input checks can silently drift into Data Engine internals. | Enforce Data Engine black-box guard and use platform-facing truth surfaces only. |
| `M9-ST-F4` | `PREVENT` | Replay/as-of/leakage checks are vulnerable to stale or mixed run scopes. | Require strict M8 handoff continuity and deterministic run-scope lock. |
| `M9-ST-F5` | `PREVENT` | Leakage claims can pass with proxy-only data or synthetic-only slices. | Enforce actual platform data cohorts from stream/truth surfaces and fail on waiver posture. |
| `M9-ST-F6` | `PREVENT` | Surface-separation checks can be bypassed by local files or ad-hoc joins. | Enforce source-authority guard (durable/oracle refs only) and locality guard. |
| `M9-ST-F7` | `PREVENT` | Cost closure can look green with unattributed account-level spend only. | Require phase-window attributable spend and explicit attribution method. |
| `M9-ST-F8` | `ACCEPT` | M8 closure is currently strict and green with `M9_READY`. | Use M8 strict closure as sole entry authority for M9. |

## 3) Scope Boundary for M9 Stress
In scope:
1. P12 authority and handle closure with strict M8 continuity.
2. replay-basis receipt generation and validation.
3. as-of and maturity policy verification.
4. leakage guardrail validation with explicit breach semantics.
5. runtime-vs-learning surface separation checks.
6. deterministic P12 rollup verdict and M10 handoff publication.
7. M9 phase budget envelope and cost-outcome closure.

Out of scope:
1. M10 dataset materialization and Iceberg write stress.
2. M11 training/evaluation execution.
3. Data Engine internal implementation details (treated as black box).
4. local filesystem-only evidence as closure authority.

## 4) M9 Stress Handle Packet (Pinned)
1. `M9_STRESS_PROFILE_ID = "learning_input_strict_stress_v0"`.
2. `M9_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m9_blocker_register.json"`.
3. `M9_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m9_execution_summary.json"`.
4. `M9_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m9_decision_log.json"`.
5. `M9_STRESS_MAX_RUNTIME_MINUTES = 210`.
6. `M9_STRESS_MAX_SPEND_USD = 80`.
7. `M9_STRESS_EXPECTED_VERDICT_ON_PASS = "ADVANCE_TO_M10"`.
8. `M9_STRESS_EXPECTED_NEXT_GATE_ON_PASS = "M10_READY"`.
9. `M9_STRESS_TARGETED_RERUN_ONLY = true`.
10. `M9_STRESS_STALE_EVIDENCE_CUTOFF_UTC = "2026-03-04T00:00:00Z"`.
11. `M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY = true`.
12. `M9_STRESS_REQUIRE_ORACLE_EVIDENCE_ONLY = true`.
13. `M9_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX = true`.
14. `M9_STRESS_DISALLOW_WAIVED_REALISM = true`.

Required registry handles (fail closed if missing/placeholder):
1. `S3_EVIDENCE_BUCKET`
2. `S3_RUN_CONTROL_ROOT_PATTERN`
3. `RECEIPT_SUMMARY_PATH_PATTERN`
4. `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
5. `LEARNING_INPUT_READINESS_PATH_PATTERN`
6. `LEARNING_REPLAY_BASIS_RECEIPT_PATH_PATTERN`
7. `LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN`
8. `LEARNING_REPLAY_BASIS_MODE`
9. `LEARNING_ORIGIN_OFFSET_SEMANTICS`
10. `LEARNING_FEATURE_ASOF_REQUIRED`
11. `LEARNING_LABEL_ASOF_REQUIRED`
12. `LEARNING_LABEL_MATURITY_DAYS_DEFAULT`
13. `LEARNING_FUTURE_TIMESTAMP_POLICY`
14. `LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS`
15. `LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS`
16. `ORACLE_STORE_BUCKET`
17. `ORACLE_SOURCE_NAMESPACE`
18. `ORACLE_ENGINE_RUN_ID`
19. `S3_STREAM_VIEW_PREFIX_PATTERN`
20. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
21. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`
22. `AWS_COST_CAPTURE_ENABLED`
23. `COST_CAPTURE_SCOPE`
24. `BUDGET_CURRENCY`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
### 5.1 M9 lane ownership
| Capability lane | M9 lane ID | Parent stage owner | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + handle closure | `A` | `S0` | no unresolved P12 required handles |
| Handoff + run-scope lock | `B` | `S0` | M8 to M9 continuity snapshot is green |
| Replay basis closure | `C` | `S1` | replay-basis receipt committed and immutable |
| As-of + maturity policy | `D` | `S1` | policy snapshot passes with deterministic checks |
| Leakage guardrail | `E` | `S2` | no future-leakage breach; fail-closed breach path proven |
| Runtime-learning surface separation | `F` | `S2` | forbidden runtime outputs and future fields blocked |
| Learning-input readiness snapshot | `G` | `S3` | consolidated readiness snapshot committed |
| P12 rollup + M10 handoff | `H` | `S3` | deterministic verdict + `m10_handoff_pack.json` |
| Phase budget + cost-outcome | `I` | `S4` | budget envelope + attributable receipt are coherent |
| M9 closure sync | `J` | `S5` | final summary committed with zero blockers |

### 5.2 Infrastructure/system lanes (mandatory)
| Platform lane | Owner stage(s) | Minimum PASS evidence |
| --- | --- | --- |
| Identity/IAM | `S0..S5` | role/capability checks pass for all read/write surfaces |
| Network reachability | `S0..S5` | durable surfaces reachable without local fallback |
| Data stores | `S1..S3` | stream/truth/run-control refs readable and scoped |
| Messaging lineage | `S1..S2` | replay basis and offset lineage are parseable and deterministic |
| Secrets posture | `S0..S5` | no secret material in emitted evidence artifacts |
| Observability/evidence | `S0..S5` | every stage emits required receipts with local+durable parity |
| Rollback/rerun control | `S0..S5` | targeted rerun policy enforced fail closed |
| Teardown/idle safety | `S4..S5` | no non-active lane left running after stage completion |
| Budget/cost control | `S4..S5` | phase-window attributable spend with threshold checks |

Execution is blocked if any capability lane above is not explicitly owned.

## 6) Anti-Hole Gates (Binding Before Execution)
### 6.1 Decision-completeness gate
1. all required stage inputs must be pinned before execution.
2. unresolved decision/input opens `M9-ST-B12` and blocks progression.

### 6.2 Phase-coverage gate
1. all M9 lanes (`A..J`) and platform lanes in section `5.2` must be represented.
2. missing lane ownership opens `M9-ST-B13`.

### 6.3 Stale-evidence quarantine gate
1. stale receipts older than `M9_STRESS_STALE_EVIDENCE_CUTOFF_UTC` are history only.
2. stale authority usage opens `M9-ST-B14`.

### 6.4 Deterministic selector rule
1. candidate selection must use deterministic timestamp + id tie-break rules.
2. filesystem traversal order cannot determine closure authority.

### 6.5 Runtime locality and source authority guard
1. closure claims must use durable/oracle evidence only; local files are non-authoritative.
2. locality/source violations open `M9-ST-B15`.

### 6.6 Data Engine black-box guard
1. M9 checks must validate platform-facing outputs and contracts only.
2. introspecting Data Engine internals opens `M9-ST-B15`.

### 6.7 Realism guard
1. synthetic-only/proxy-only pass posture is not accepted for M9 closure.
2. waiver posture opens `M9-ST-B16`.

## 7) Execution Topology (Parent `S0..S5`)
1. `S0`: authority + handoff scope lock (`A`,`B`).
2. `S1`: replay basis + as-of/maturity policy (`C`,`D`).
3. `S2`: leakage guardrail + surface separation (`E`,`F`).
4. `S3`: readiness snapshot + deterministic P12 verdict/handoff (`G`,`H`).
5. `S4`: phase budget + cost-outcome closure (`I`).
6. `S5`: final closure sync (`J`).

## 8) Execution Plan (Fail-Closed Runbook)
### 8.1 `M9-ST-S0` - Authority and handoff scope lock (`A`,`B`)
Objective:
1. close M9 entry authority and lock a single run scope from M8 handoff.

Entry criteria:
1. M8 closure authority is green (`m8_stress_s5_20260304T234918Z`, `M9_READY`).
2. required M9 authority docs and handles are readable.

Execution steps:
1. validate M8 summary and handoff contract continuity.
2. resolve required handle set and fail on missing/placeholder values.
3. emit `m9a_*` and `m9b_*` evidence with parity checks.
4. emit parent stage guard snapshots.

Fail-closed blockers:
1. `M9-ST-B1`: authority/handle closure failure.
2. `M9-ST-B2`: handoff/run-scope continuity failure.
3. `M9-ST-B11`: artifact parity failure.
4. `M9-ST-B12`: unresolved decision/input hole.
5. `M9-ST-B13`: phase coverage hole.
6. `M9-ST-B14`: stale authority usage.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$5`.

Pass gate:
1. `next_gate=M9_ST_S1_READY`.

### 8.2 `M9-ST-S1` - Replay basis + as-of/maturity controls (`C`,`D`)
Objective:
1. prove replay-basis provenance and temporal policy correctness before leakage checks.

Entry criteria:
1. successful `S0` with `next_gate=M9_ST_S1_READY`.

Execution steps:
1. produce and validate replay-basis receipt with deterministic offset lineage.
2. validate as-of/maturity policy against pinned handle semantics.
3. emit `m9c_*` and `m9d_*` artifacts and parent snapshots.

Fail-closed blockers:
1. `M9-ST-B3`: replay-basis closure failure.
2. `M9-ST-B4`: as-of/maturity policy failure.
3. `M9-ST-B11`: artifact parity failure.
4. `M9-ST-B15`: source-authority/locality violation.

Runtime/cost budget:
1. max runtime: `40` minutes.
2. max spend: `$12`.

Pass gate:
1. `next_gate=M9_ST_S2_READY`.

### 8.3 `M9-ST-S2` - Leakage guardrail + surface separation (`E`,`F`)
Objective:
1. fail closed on future leakage and runtime-truth boundary violations under realistic data.

Entry criteria:
1. successful `S1` with `next_gate=M9_ST_S2_READY`.

Execution steps:
1. evaluate replay offsets and timestamps for future-leakage violations.
2. enforce runtime forbidden output and future-field policies.
3. validate runtime-vs-learning evidence surface separation.
4. emit `m9e_*`, `m9f_*`, and parent stage receipts.

Fail-closed blockers:
1. `M9-ST-B5`: leakage guardrail failure (`DFULL-RUN-B12.2` posture included).
2. `M9-ST-B6`: runtime-learning surface separation failure.
3. `M9-ST-B11`: artifact parity failure.
4. `M9-ST-B16`: non-realistic data posture.

Runtime/cost budget:
1. max runtime: `50` minutes.
2. max spend: `$16`.

Pass gate:
1. `next_gate=M9_ST_S3_READY`.

### 8.4 `M9-ST-S3` - Learning readiness + P12 verdict/handoff (`G`,`H`)
Objective:
1. aggregate lane readiness and publish deterministic P12 verdict with M10 handoff.

Entry criteria:
1. successful `S2` with `next_gate=M9_ST_S3_READY`.

Execution steps:
1. roll up `C..F` readiness in fixed order.
2. emit `m9g_learning_input_readiness_snapshot.json`.
3. compute deterministic P12 matrix and emit:
   - `m9h_p12_gate_rollup_matrix.json`,
   - `m9h_p12_gate_verdict.json`,
   - `m10_handoff_pack.json`.

Fail-closed blockers:
1. `M9-ST-B7`: readiness snapshot incompleteness/inconsistency.
2. `M9-ST-B8`: P12 rollup/verdict inconsistency.
3. `M9-ST-B9`: M10 handoff publication/contract failure.
4. `M9-ST-B11`: artifact parity failure.

Runtime/cost budget:
1. max runtime: `35` minutes.
2. max spend: `$11`.

Pass gate:
1. `next_gate=M9_ST_S4_READY`.
2. lane `H` verdict on pass: `ADVANCE_TO_P13`.

### 8.5 `M9-ST-S4` - Phase budget + cost-outcome closure (`I`)
Objective:
1. produce phase budget envelope and attributable spend receipt for M9 outcomes.

Entry criteria:
1. successful `S3` with `next_gate=M9_ST_S4_READY`.

Execution steps:
1. validate `A..H` closure continuity and run-scope single-valued posture.
2. compute attributable phase-window spend and enforce thresholds.
3. emit:
   - `m9_phase_budget_envelope.json`,
   - `m9_phase_cost_outcome_receipt.json`,
   - `m9i_execution_summary.json`.

Fail-closed blockers:
1. `M9-ST-B10`: cost-outcome closure failure.
2. `M9-ST-B11`: artifact parity failure.
3. `M9-ST-B15`: source-authority/locality violation.

Runtime/cost budget:
1. max runtime: `25` minutes.
2. max spend: `$18`.

Pass gate:
1. `next_gate=M9_ST_S5_READY`.

### 8.6 `M9-ST-S5` - M9 closure sync (`J`)
Objective:
1. finalize M9 closure with deterministic summary and next-gate readiness.

Entry criteria:
1. successful `S4` with `next_gate=M9_ST_S5_READY`.

Execution steps:
1. verify parity/readability across all M9 lane artifacts (`A..I`).
2. emit final:
   - `m9_blocker_register.json`,
   - `m9_execution_summary.json`,
   - `m9_decision_log.json`,
   - `m9_gate_verdict.json`.
3. enforce guard snapshots (locality, source authority, realism) at closure.

Fail-closed blockers:
1. `M9-ST-B10`: closure-sync completeness failure.
2. `M9-ST-B11`: final summary/evidence parity failure.
3. `M9-ST-B15`: source-authority/locality violation.
4. `M9-ST-B16`: non-realistic closure posture.

Runtime/cost budget:
1. max runtime: `20` minutes.
2. max spend: `$8`.

Pass gate:
1. `overall_pass=true`.
2. `verdict=ADVANCE_TO_M10`.
3. `next_gate=M10_READY`.
4. `open_blocker_count=0`.

## 9) Blocker Taxonomy (M9 Parent)
1. `M9-ST-B1`: authority/handle closure failure.
2. `M9-ST-B2`: handoff/run-scope continuity failure.
3. `M9-ST-B3`: replay-basis closure failure.
4. `M9-ST-B4`: as-of/maturity policy failure.
5. `M9-ST-B5`: leakage guardrail failure.
6. `M9-ST-B6`: runtime-learning surface separation failure.
7. `M9-ST-B7`: readiness snapshot incompleteness.
8. `M9-ST-B8`: P12 rollup/verdict inconsistency.
9. `M9-ST-B9`: M10 handoff publication failure.
10. `M9-ST-B10`: phase cost-outcome or closure-sync failure.
11. `M9-ST-B11`: summary/evidence publication parity failure.
12. `M9-ST-B12`: unresolved decision/input hole.
13. `M9-ST-B13`: phase-coverage lane hole.
14. `M9-ST-B14`: stale-evidence authority selection.
15. `M9-ST-B15`: runtime locality/source-authority/Data-Engine-boundary violation.
16. `M9-ST-B16`: non-realistic data posture used for closure.

## 10) Artifact Contract
Required stage outputs (phase-level):
1. `m9_stagea_findings.json`
2. `m9_lane_matrix.json`
3. `m9a_handle_closure_snapshot.json`
4. `m9b_handoff_scope_snapshot.json`
5. `m9c_replay_basis_receipt.json`
6. `m9d_asof_maturity_policy_snapshot.json`
7. `m9e_leakage_guardrail_report.json`
8. `m9f_surface_separation_snapshot.json`
9. `m9g_learning_input_readiness_snapshot.json`
10. `m9h_p12_gate_rollup_matrix.json`
11. `m9h_p12_gate_verdict.json`
12. `m10_handoff_pack.json`
13. `m9_phase_budget_envelope.json`
14. `m9_phase_cost_outcome_receipt.json`
15. `m9_blocker_register.json`
16. `m9_execution_summary.json`
17. `m9_decision_log.json`
18. `m9_gate_verdict.json`
19. `m9_runtime_locality_guard_snapshot.json`
20. `m9_source_authority_guard_snapshot.json`
21. `m9_realism_guard_snapshot.json`

## 11) DoD (Planning to Execution-Ready)
- [x] dedicated M9 stress authority created.
- [x] capability-lane coverage explicit (`A..J` + infrastructure lanes).
- [x] anti-hole preflight gates pinned.
- [x] M8 carry-forward guards pinned (locality/source authority/realism/black-box).
- [x] fail-closed blocker taxonomy and artifact contract pinned.
- [x] `M9-ST-S0` executed and closed green.
- [ ] `M9-ST-S1` executed and closed green.
- [ ] `M9-ST-S2` executed and closed green.
- [ ] `M9-ST-S3` executed and closed green.
- [ ] `M9-ST-S4` executed and closed green.
- [ ] `M9-ST-S5` executed and closed green with deterministic `M10_READY`.

## 12) Immediate Next Actions
1. expand `scripts/dev_substrate/m9_stress_runner.py` from `S0` to `S1` (`C+D`) with deterministic blocker mapping.
2. execute `M9-ST-S1` using upstream `m9_stress_s0_20260305T000519Z`.
3. maintain fail-closed posture with targeted remediation only.

## 13) Execution Progress
1. M9 stress authority is pinned and active.
2. M8 strict closure authority for M9 entry is pinned to `m8_stress_s5_20260304T234918Z`.
3. `M9-ST-S0` first execution failed closed (runner contract bug):
   - `phase_execution_id=m9_stress_s0_20260305T000457Z`,
   - blocker: `M9-ST-B11` (`artifact_contract_incomplete` from prewrite self-check of stage receipts).
4. Remediation applied:
   - patched `scripts/dev_substrate/m9_stress_runner.py` `finish()` to validate only pre-existing stage artifacts before writing stage receipts.
5. `M9-ST-S0` closure execution passed:
   - `phase_execution_id=m9_stress_s0_20260305T000519Z`,
   - `overall_pass=true`, `open_blocker_count=0`,
   - `verdict=GO`, `next_gate=M9_ST_S1_READY`.
6. Native lane execution IDs in S0:
   - `m9a_execution_id=m9a_stress_s0_20260305T000520Z` (`overall_pass=true`, `next_gate=M9.B_READY`),
   - `m9b_execution_id=m9b_stress_s0_20260305T000522Z` (`overall_pass=true`, `next_gate=M9.C_READY`).
7. S0 evidence root:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m9_stress_s0_20260305T000519Z/stress/`.

## 14) Reopen Notice (Strict Authority)
1. M9 cannot be closed using historical 2026-02-26 receipts alone.
2. Only receipts generated from this M9 stress authority and current strict M8 handoff chain can close M9.
