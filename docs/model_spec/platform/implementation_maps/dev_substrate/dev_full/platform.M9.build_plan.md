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

Entry conditions:
1. `M8` closure is green with `ADVANCE_TO_M9` and `next_gate=M9_READY`.
2. canonical source handoff is readable by resolving:
   - `evidence/dev_full/run_control/{m8_execution_id}/m8_execution_summary.json` -> `upstream_refs.m8i_execution_id`,
   - then `evidence/dev_full/run_control/{m8i_execution_id}/m9_handoff_pack.json`.
3. active run scope (`platform_run_id`, `scenario_run_id`) is inherited from handoff evidence; no manual run-scope override.

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
1. validate M8->M9 handoff posture and run-scope continuity.
2. resolve and validate required P12 handles from registry.
3. fail-closed on unresolved/wildcard/placeholder handle values.
4. emit:
   - `m9a_handle_closure_snapshot.json`
   - `m9a_blocker_register.json`
   - `m9a_execution_summary.json`.

Deterministic verification algorithm:
1. read upstream `m8_execution_summary.json` from M8 closure run-control evidence, derive `m8i_execution_id`, then read `m9_handoff_pack.json` from M8.I run-control evidence.
2. enforce handoff posture:
   - `m8_verdict=ADVANCE_TO_M9`
   - `m8_overall_pass=true`
   - `m9_entry_gate.next_gate=M9_READY`.
3. resolve `required_handle_set` and classify:
   - missing handles,
   - placeholder/wildcard handles.
4. fail-closed classification:
   - `M9-B1` for handoff/readability/handle-closure failure.
5. publish local artifacts, then durable artifacts with put+head parity checks.
6. fail-closed on publication/readback failure:
   - `M9-B11`.
7. emit deterministic next gate:
   - `M9.B_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [x] required handle matrix explicit and complete.
- [x] unresolved required handles are blocker-marked.
- [x] `m9a_handle_closure_snapshot.json` committed locally and durably.
- [x] `m9a_blocker_register.json` and `m9a_execution_summary.json` committed locally and durably.
- [x] `M9.B_READY` emitted with blocker count `0`.

Execution status:
1. First execution failed closed:
   - execution id: `m9a_p12_handle_closure_20260226T074802Z`,
   - result: `overall_pass=false`, `blocker_count=2`, `next_gate=HOLD_REMEDIATE`,
   - blockers:
     - `M9-B1` handoff key mismatch (`m9_handoff_pack` was resolved at M8.J root instead of M8.I root),
     - `M9-B1` unresolved run scope due to unreadable handoff payload.
2. Remediation applied:
   - patched `scripts/dev_substrate/m9a_handle_closure.py` to:
     - read upstream `m8_execution_summary.json`,
     - derive `m8i_execution_id` from `upstream_refs`,
     - resolve `m9_handoff_pack.json` from derived M8.I run-control prefix,
     - remove stale env run-scope pre-seeding to prevent contamination.
3. Closure execution:
   - execution id: `m9a_p12_handle_closure_20260226T074906Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M9.B_READY`,
   - required handles resolved: `12/12`,
   - missing/placeholder/wildcard handles: `0/0/0`.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9a_p12_handle_closure_20260226T074906Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9a_p12_handle_closure_20260226T074906Z/`.

### M9.B M8 Handoff + Run-Scope Lock
Goal:
1. lock M8->M9 run-scope continuity and handoff contract.

Entry conditions:
1. `M9.A` summary is green (`overall_pass=true`, `next_gate=M9.B_READY`).
2. upstream M8 closure summary is green (`overall_pass=true`, `verdict=ADVANCE_TO_M9`, `next_gate=M9_READY`).

Required upstream surfaces:
1. `evidence/dev_full/run_control/{m8_execution_id}/m8_execution_summary.json`
2. `evidence/dev_full/run_control/{m8i_execution_id}/m9_handoff_pack.json` (derived from M8 summary `upstream_refs`)
3. `evidence/dev_full/run_control/{m9a_execution_id}/m9a_execution_summary.json`
4. `evidence/dev_full/run_control/{m9a_execution_id}/m9a_handle_closure_snapshot.json`

Tasks:
1. validate M8 verdict/handoff references (`m8i`, `m8j`).
2. pin `platform_run_id` + `scenario_run_id` for all M9 sub-phases.
3. emit:
   - `m9b_handoff_scope_snapshot.json`
   - `m9b_blocker_register.json`
   - `m9b_execution_summary.json`.

Deterministic verification algorithm:
1. read upstream M8 summary and enforce `ADVANCE_TO_M9` + `M9_READY` posture.
2. derive `m8i_execution_id` from M8 summary `upstream_refs`.
3. read M8 handoff pack (`m9_handoff_pack.json`) and M9.A artifacts.
4. enforce continuity invariants:
   - M8 handoff run scope equals M9.A run scope,
   - M8 handoff `required_evidence_refs` is non-empty and parseable,
   - M8 handoff entry gate declaration remains `M9_READY`.
5. build deterministic scope-lock matrix for `M9.B..M9.J` with one canonical run scope.
6. classify blockers:
   - `M9-B2` for continuity/scope-lock failures,
   - `M9-B11` for artifact publish/readback parity failures.
7. emit deterministic next gate:
   - `M9.C_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [x] M8 continuity checks pass with blocker-free posture.
- [x] run-scope lock is explicit.
- [x] `m9b_handoff_scope_snapshot.json` committed locally and durably.
- [x] `m9b_blocker_register.json` and `m9b_execution_summary.json` committed locally and durably.
- [x] `M9.C_READY` emitted with blocker count `0`.

Execution status:
1. Closure execution:
   - execution id: `m9b_p12_scope_lock_20260226T075421Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M9.C_READY`.
2. Continuity checks:
   - upstream M8 closure posture validated (`ADVANCE_TO_M9`, `M9_READY`),
   - upstream M9.A posture validated (`overall_pass=true`, `M9.B_READY`).
3. Run-scope lock output:
   - canonical run scope:
     - `platform_run_id=platform_20260223T184232Z`,
     - `scenario_run_id=scenario_38753050f3b70c666e16f7552016b330`,
   - locked sub-phases: `M9.B..M9.J` (`9` lanes),
   - scope lock hash:
     - `92dff0c910630d96a7dd80fcf79c6de37d52370d841979f6f055dc254b63cd70`.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9b_p12_scope_lock_20260226T075421Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9b_p12_scope_lock_20260226T075421Z/`.

### M9.C Replay-Basis Receipt Closure
Goal:
1. commit learning replay basis receipt with deterministic offsets.

Entry conditions:
1. `M9.B` summary is green (`overall_pass=true`, `next_gate=M9.C_READY`).
2. replay-basis mode handle is pinned to `origin_offset_ranges`.

Required upstream surfaces:
1. `evidence/dev_full/run_control/{m9b_execution_id}/m9b_execution_summary.json`
2. `evidence/dev_full/run_control/{m9b_execution_id}/m9b_handoff_scope_snapshot.json`
3. run-scoped ingest evidence:
   - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
   - `RECEIPT_SUMMARY_PATH_PATTERN` (cross-check surface)
4. run-scoped closure references from M8 handoff (run-report/reconciliation/governance refs).

Tasks:
1. gather and validate `origin_offset` range references for learning input scope.
2. enforce `LEARNING_REPLAY_BASIS_MODE=origin_offset_ranges`.
3. emit:
   - `m9c_replay_basis_receipt.json`
   - `m9c_blocker_register.json`
   - `m9c_execution_summary.json`.

Deterministic verification algorithm:
1. read `M9.B` artifacts and enforce pass posture.
2. resolve canonical run scope and render ingest evidence keys from handles.
3. read `kafka_offsets_snapshot.json` and validate:
   - `offset_mode` is present,
   - each topic row has `topic`, `partition`, `first_offset`, `last_offset`,
   - `first_offset <= last_offset`,
   - `observed_count > 0` for each replay basis row.
4. enforce replay mode handle:
   - `LEARNING_REPLAY_BASIS_MODE=origin_offset_ranges`.
5. build receipt payload with immutable replay basis rows and source refs.
6. publish replay-basis receipt to:
   - run-scope evidence path (`LEARNING_REPLAY_BASIS_RECEIPT_PATH_PATTERN`),
   - run-control execution path (`m9c_replay_basis_receipt.json`).
7. classify blockers:
   - `M9-B3` for replay-basis/readability/validation failures,
   - `M9-B11` for publish/readback parity failures.
8. emit deterministic next gate:
   - `M9.D_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [x] replay basis is explicit, immutable, and parseable.
- [x] replay basis references are run-scoped.
- [x] `m9c_replay_basis_receipt.json` committed locally and durably.
- [x] `m9c_blocker_register.json` and `m9c_execution_summary.json` committed locally and durably.
- [x] `M9.D_READY` emitted with blocker count `0`.

Execution status:
1. Closure execution:
   - execution id: `m9c_p12_replay_basis_20260226T075941Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M9.D_READY`.
2. Replay basis output:
   - mode: `origin_offset_ranges`,
   - range rows: `1`,
   - canonical row:
     - topic: `ig.edge.admission.proxy.v1`,
     - partition: `0`,
     - first_offset: `1772022980`,
     - last_offset: `1772042246`,
     - observed_count: `18`.
3. Determinism:
   - replay basis fingerprint:
     - `2bb3d8acc862cf7ea5e67ff78be849e9717111d617d5159a5aafb83a0ad384c3`.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9c_p12_replay_basis_20260226T075941Z/`,
   - durable run-control: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9c_p12_replay_basis_20260226T075941Z/`,
   - durable run-scoped receipt:
     - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/input/replay_basis_receipt.json`.

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
- [x] `M9.A` complete
- [x] `M9.B` complete
- [x] `M9.C` complete
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
2. `M9.A` is closed green with `next_gate=M9.B_READY`.
3. `M9.B` is closed green with `next_gate=M9.C_READY`.
4. `M9.C` is closed green with `next_gate=M9.D_READY`.
5. Next action is `M9.D` as-of + maturity policy closure.
