# Dev Substrate Deep Plan - M9 (P12 LEARNING_INPUT_READY)
_Status source of truth: `platform.build_plan.md`_
_This document provides orchestration-level deep planning detail for M9._
_Last updated: 2026-02-26_

## 0) Purpose
M9 closes:
1. `P12 LEARNING_INPUT_READY`.

M9 must prove:
1. learning input replay basis is explicit and immutable (`origin_offset` ranges).
2. as-of and maturity controls enforce temporal causality.
3. no-future-leakage checks are fail-closed and evidence-backed.
4. runtime and learning data-surface boundaries are enforced.
5. deterministic `P12` verdict and M10 handoff are committed.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P12`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
2. `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
4. M8 closure evidence prefix:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8j_p11_closure_sync_20260226T065141Z/`

## 2) Scope Boundary for M9
In scope:
1. `P12` authority/handle closure and run-scope continuity from M8.
2. learning replay-basis receipt generation and validation.
3. as-of, label maturity, and temporal boundary checks.
4. no-future-leakage guardrail execution.
5. runtime-vs-learning surface separation validation.
6. deterministic gate rollup/verdict and M10 handoff publication.
7. phase budget envelope and cost-outcome closure for M9.

Out of scope:
1. Databricks dataset build and Iceberg writes (`M10`).
2. SageMaker training/evaluation (`M11`).
3. promotion/rollback corridor execution (`M12`).

## 3) Deliverables
1. `m9a_handle_closure_snapshot.json`
2. `m9b_handoff_scope_snapshot.json`
3. `m9c_replay_basis_receipt.json`
4. `m9d_asof_maturity_policy_snapshot.json`
5. `m9e_leakage_guardrail_report.json`
6. `m9f_surface_separation_snapshot.json`
7. `m9g_learning_input_readiness_snapshot.json`
8. `m9h_p12_gate_verdict.json`
9. `m10_handoff_pack.json`
10. `m9_phase_budget_envelope.json`
11. `m9_phase_cost_outcome_receipt.json`
12. `m9_execution_summary.json`

## 4) Entry Gate and Current Posture
Entry gate for M9:
1. `M8` is `DONE`.
2. M8 verdict is `ADVANCE_TO_M9` with `next_gate=M9_READY`.
3. M8 blockers are resolved (`blocker_count=0`).
4. run scope remains unchanged from M8 closure.

Current posture:
1. Entry conditions are met from existing M8 closure evidence.
2. M9 planning is expanded to execution-grade; execution has not started.

## 4.1) Anti-Cram Law (Binding for M9)
M9 is not execution-ready unless these capability lanes are explicit:
1. authority + handles.
2. run identity continuity.
3. replay basis closure.
4. as-of/maturity policy closure.
5. leakage guardrail checks.
6. runtime vs learning surface separation checks.
7. deterministic rollup/verdict + handoff.
8. phase budget + cost-outcome closure.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M9.A | no unresolved required `P12` handles |
| Handoff and run-scope lock | M9.B | M8->M9 continuity snapshot passes |
| Replay basis closure | M9.C | replay-basis receipt committed |
| As-of and maturity policy | M9.D | as-of/maturity snapshot passes |
| Leakage guardrail | M9.E | guardrail report pass with no future breach |
| Surface separation | M9.F | runtime/learning boundary checks pass |
| Learning-input readiness | M9.G | readiness snapshot committed |
| P12 verdict + handoff | M9.H | `ADVANCE_TO_P13` + `m10_handoff_pack.json` |
| Cost-outcome closure | M9.I | budget + receipt pass |
| Closure sync | M9.J | `m9_execution_summary.json` committed |

## 5) Work Breakdown (Orchestration)

### M9.A P12 Authority + Handle Closure
Goal:
1. close required P12 handles before learning-input execution.

Required handle set:
1. `LEARNING_INPUT_READINESS_PATH_PATTERN`
2. `LEARNING_REPLAY_BASIS_RECEIPT_PATH_PATTERN`
3. `LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN`
4. `LEARNING_REPLAY_BASIS_MODE`
5. `LEARNING_FEATURE_ASOF_REQUIRED`
6. `LEARNING_LABEL_ASOF_REQUIRED`
7. `LEARNING_LABEL_MATURITY_DAYS_DEFAULT`
8. `LEARNING_FUTURE_TIMESTAMP_POLICY`
9. `LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS`
10. `LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS`
11. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
12. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`

Tasks:
1. resolve and validate required P12 handles.
2. fail-closed on unresolved/wildcard/placeholder handle values.
3. emit `m9a_handle_closure_snapshot.json`.

DoD:
- [ ] required handle matrix explicit and complete.
- [ ] unresolved required handles are blocker-marked.
- [ ] `m9a_handle_closure_snapshot.json` committed locally and durably.

### M9.B M8 Handoff + Run-Scope Lock
Goal:
1. lock M8->M9 run-scope continuity and handoff contract.

Tasks:
1. validate M8 verdict/handoff references (`m8i`, `m8j`).
2. pin `platform_run_id` + `scenario_run_id` for all M9 sub-phases.
3. emit `m9b_handoff_scope_snapshot.json`.

DoD:
- [ ] M8 continuity checks pass with blocker-free posture.
- [ ] run-scope lock is explicit.
- [ ] `m9b_handoff_scope_snapshot.json` committed locally and durably.

### M9.C Replay-Basis Receipt Closure
Goal:
1. commit learning replay basis receipt with deterministic offsets.

Tasks:
1. gather and validate `origin_offset` range references for learning input scope.
2. enforce `LEARNING_REPLAY_BASIS_MODE=origin_offset_ranges`.
3. emit `m9c_replay_basis_receipt.json`.

DoD:
- [ ] replay basis is explicit, immutable, and parseable.
- [ ] replay basis references are run-scoped.
- [ ] `m9c_replay_basis_receipt.json` committed locally and durably.

### M9.D As-Of + Maturity Policy Closure
Goal:
1. prove temporal boundaries are pinned before dataset build.

Tasks:
1. validate `feature_asof_utc`, `label_asof_utc`, and maturity policy input.
2. fail-closed if as-of or maturity controls are missing/invalid.
3. emit `m9d_asof_maturity_policy_snapshot.json`.

DoD:
- [ ] as-of and maturity controls are explicit.
- [ ] boundary values are coherent and auditable.
- [ ] `m9d_asof_maturity_policy_snapshot.json` committed locally and durably.

### M9.E Leakage Guardrail Evaluation
Goal:
1. detect and block any future timestamp leakage.

Tasks:
1. run timestamp boundary checks against configured fields.
2. record violations with row/sample references.
3. emit `m9e_leakage_guardrail_report.json`.

DoD:
- [ ] no unresolved leakage violation remains.
- [ ] boundary breach emits blocker `DFULL-RUN-B12.2` fail-closed.
- [ ] `m9e_leakage_guardrail_report.json` committed locally and durably.

### M9.F Runtime-vs-Learning Surface Separation
Goal:
1. prove runtime lanes are isolated from offline truth surfaces.

Tasks:
1. validate live-runtime forbid set (`s4_*` + future-derived fields).
2. verify learning-only access boundaries for truth products.
3. emit `m9f_surface_separation_snapshot.json`.

DoD:
- [ ] runtime truth-surface violations are absent.
- [ ] separation checks are explicit and evidence-backed.
- [ ] `m9f_surface_separation_snapshot.json` committed locally and durably.

### M9.G Learning Input Readiness Snapshot
Goal:
1. publish consolidated readiness evidence for P12 closure.

Tasks:
1. aggregate outputs from `M9.C..M9.F`.
2. emit `m9g_learning_input_readiness_snapshot.json` + blocker register.

DoD:
- [ ] readiness snapshot is complete and parseable.
- [ ] blocker register is coherent with prior checks.
- [ ] snapshot artifacts committed locally and durably.

### M9.H P12 Gate Rollup + M10 Handoff
Goal:
1. produce deterministic P12 verdict and handoff.

Tasks:
1. roll up M9A-G outcomes in fixed order.
2. emit `m9h_p12_gate_verdict.json`.
3. emit `m10_handoff_pack.json`.

DoD:
- [ ] deterministic verdict is emitted.
- [ ] pass posture requires `ADVANCE_TO_P13` and `next_gate=M10_READY`.
- [ ] handoff pack committed locally and durably.

### M9.I M9 Phase Budget + Cost-Outcome Closure
Goal:
1. publish cost-to-outcome artifacts for M9.

Tasks:
1. emit `m9_phase_budget_envelope.json`.
2. emit `m9_phase_cost_outcome_receipt.json`.

DoD:
- [ ] budget envelope is valid and parseable.
- [ ] cost-outcome receipt is coherent with emitted artifacts.
- [ ] both artifacts committed locally and durably.

### M9.J M9 Closure Sync
Goal:
1. close M9 and publish authoritative summary.

Tasks:
1. emit `m9_execution_summary.json`.
2. verify local+durable parity of M9 outputs.
3. update M9 closure status and next gate readiness.

DoD:
- [ ] `m9_execution_summary.json` committed locally and durably.
- [ ] M9 closure sync passes with no unresolved blocker.

## 6) Blocker Taxonomy (Fail-Closed)
1. `M9-B1`: authority/handle closure failure.
2. `M9-B2`: handoff/run-scope continuity failure.
3. `M9-B3`: replay-basis closure failure.
4. `M9-B4`: as-of/maturity policy failure.
5. `M9-B5`: leakage guardrail failure.
6. `M9-B6`: surface-separation failure.
7. `M9-B7`: readiness snapshot incompleteness.
8. `M9-B8`: P12 rollup/verdict inconsistency.
9. `M9-B9`: handoff publication failure.
10. `M9-B10`: phase cost-outcome closure failure.
11. `M9-B11`: summary/evidence publication parity failure.

## 7) Artifact Contract (M9)
1. `m9a_handle_closure_snapshot.json`
2. `m9b_handoff_scope_snapshot.json`
3. `m9c_replay_basis_receipt.json`
4. `m9d_asof_maturity_policy_snapshot.json`
5. `m9e_leakage_guardrail_report.json`
6. `m9f_surface_separation_snapshot.json`
7. `m9g_learning_input_readiness_snapshot.json`
8. `m9h_p12_gate_verdict.json`
9. `m10_handoff_pack.json`
10. `m9_phase_budget_envelope.json`
11. `m9_phase_cost_outcome_receipt.json`
12. `m9_execution_summary.json`

## 8) Completion Checklist
- [ ] `M9.A` complete
- [ ] `M9.B` complete
- [ ] `M9.C` complete
- [ ] `M9.D` complete
- [ ] `M9.E` complete
- [ ] `M9.F` complete
- [ ] `M9.G` complete
- [ ] `M9.H` complete
- [ ] `M9.I` complete
- [ ] `M9.J` complete
- [ ] all active `M9-B*` blockers resolved

## 9) Planning Status
1. M9 planning is expanded and execution-grade.
2. Next action is `M9.A` authority + handle closure for `P12`.
