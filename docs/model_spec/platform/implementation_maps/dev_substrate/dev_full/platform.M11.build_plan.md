# Dev Substrate Deep Plan - M11 (P14 MF_EVAL_COMMITTED)
_Status source of truth: `platform.build_plan.md`_
_This document provides orchestration-level deep planning detail for M11._
_Last updated: 2026-02-26_

## 0) Purpose
M11 closes:
1. `P14 MF_EVAL_COMMITTED`.

M11 must prove:
1. training/evaluation consume immutable M10 dataset inputs.
2. MF eval passes compatibility, performance, and leakage gates.
3. MLflow lineage and provenance are complete and auditable.
4. candidate bundle is published with safe-disable/rollback posture.
5. deterministic `P14` verdict and M12 handoff are committed.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P14`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M10.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary for M11
In scope:
1. MF authority/handle closure.
2. SageMaker runtime readiness for train/eval.
3. immutable input binding to M10 output set.
4. train/eval execution and metric/leakage gates.
5. MLflow lineage and provenance closure.
6. candidate bundle publication.
7. safe-disable/rollback path publication.
8. deterministic P14 verdict + M12 handoff + cost-outcome closure.

Out of scope:
1. promotion and rollback corridor operations (`M12`).
2. final full-platform verdict and teardown (`M13`).

## 3) Deliverables
1. `m11a_handle_closure_snapshot.json`
2. `m11b_sagemaker_readiness_snapshot.json`
3. `m11c_input_immutability_snapshot.json`
4. `m11d_train_eval_execution_snapshot.json`
5. `m11e_eval_gate_snapshot.json`
6. `m11f_mlflow_lineage_snapshot.json`
7. `m11g_candidate_bundle_snapshot.json`
8. `m11h_safe_disable_rollback_snapshot.json`
9. `m11i_p14_gate_verdict.json`
10. `m12_handoff_pack.json`
11. `m11_phase_budget_envelope.json`
12. `m11_phase_cost_outcome_receipt.json`
13. `m11_execution_summary.json`

## 4) Entry Gate and Current Posture
Entry gate for M11:
1. `M10` is `DONE`.
2. `P13` verdict is `ADVANCE_TO_P14`.
3. M10 blockers are resolved.

Current posture:
1. M11 planning is expanded and execution-grade.
2. Execution has not started.

## 4.1) Anti-Cram Law (Binding for M11)
M11 is not execution-ready unless these capability lanes are explicit:
1. authority + handles.
2. SageMaker runtime readiness.
3. input immutability.
4. train/eval execution.
5. eval/leakage/stability gates.
6. MLflow lineage + provenance.
7. candidate bundle publication.
8. safe-disable/rollback closure.
9. deterministic verdict + handoff.
10. cost-outcome closure.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M11.A | no unresolved required P14 handles |
| SageMaker readiness | M11.B | runtime role and endpoint/training surfaces pass |
| Input immutability | M11.C | M10 dataset binding checks pass |
| Train/eval execution | M11.D | execution snapshot pass |
| Eval gate closure | M11.E | metrics/leakage/stability checks pass |
| MLflow lineage closure | M11.F | lineage/provenance snapshot pass |
| Candidate bundle publication | M11.G | candidate bundle snapshot pass |
| Safe-disable/rollback closure | M11.H | rollback/safe-disable checks pass |
| P14 verdict + handoff | M11.I | `ADVANCE_TO_P15` + `m12_handoff_pack.json` |
| Cost-outcome + closure sync | M11.J | summary + budget + cost receipt pass |

## 5) Work Breakdown (Orchestration)

### M11.A P14 Authority + Handle Closure
Goal:
1. close required P14 handles before train/eval execution.

Required handle set:
1. `SM_TRAINING_JOB_NAME_PREFIX`
2. `SM_BATCH_TRANSFORM_JOB_NAME_PREFIX`
3. `SM_MODEL_PACKAGE_GROUP_NAME`
4. `SM_ENDPOINT_NAME`
5. `MF_EVAL_REPORT_PATH_PATTERN`
6. `MF_CANDIDATE_BUNDLE_PATH_PATTERN`
7. `MF_LEAKAGE_PROVENANCE_CHECK_PATH_PATTERN`
8. `MLFLOW_HOSTING_MODE`
9. `MLFLOW_EXPERIMENT_PATH`
10. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
11. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`

DoD:
- [ ] required handle matrix explicit and complete.
- [ ] unresolved handles are blocker-marked.
- [ ] `m11a_handle_closure_snapshot.json` committed locally and durably.

### M11.B SageMaker Runtime Readiness
Goal:
1. prove SageMaker runtime and identity surfaces are executable.

Tasks:
1. validate role/endpoint/training job surfaces.
2. validate required secret/path dependencies.
3. emit `m11b_sagemaker_readiness_snapshot.json`.

DoD:
- [ ] SageMaker readiness checks pass.
- [ ] readiness snapshot committed locally and durably.

### M11.C Input Immutability Binding
Goal:
1. prove training inputs are immutable and bound to M10 outputs.

Tasks:
1. validate M10 manifest/fingerprint references.
2. validate as-of/replay/provenance closure references.
3. emit `m11c_input_immutability_snapshot.json`.

DoD:
- [ ] immutable input checks pass.
- [ ] snapshot committed locally and durably.

### M11.D Train/Eval Execution
Goal:
1. execute training/evaluation runs with deterministic inputs.

Tasks:
1. run training and evaluation jobs.
2. capture job refs and completion states.
3. emit `m11d_train_eval_execution_snapshot.json`.

DoD:
- [ ] train/eval execution completes.
- [ ] execution snapshot committed locally and durably.

### M11.E Eval Gate Closure
Goal:
1. adjudicate metric, leakage, and stability gates.

Tasks:
1. validate thresholds and gate outcomes.
2. fail-closed on gate failures.
3. emit `m11e_eval_gate_snapshot.json`.

DoD:
- [ ] evaluation gates pass.
- [ ] snapshot committed locally and durably.

### M11.F MLflow Lineage + Provenance Closure
Goal:
1. prove full lineage and provenance references.

Tasks:
1. verify MLflow experiment/run/model refs.
2. verify provenance fields include dataset fingerprint and replay/as-of controls.
3. emit `m11f_mlflow_lineage_snapshot.json`.

DoD:
- [ ] lineage/provenance checks pass.
- [ ] snapshot committed locally and durably.

### M11.G Candidate Bundle Publication
Goal:
1. publish candidate bundle with compatibility metadata.

Tasks:
1. emit candidate bundle artifact and metadata.
2. validate required compatibility fields.
3. emit `m11g_candidate_bundle_snapshot.json`.

DoD:
- [ ] candidate bundle publication checks pass.
- [ ] snapshot committed locally and durably.

### M11.H Safe-Disable/Rollback Closure
Goal:
1. close safe-disable and rollback evidence for MF.

Tasks:
1. publish safe-disable posture for candidate.
2. validate rollback strategy and evidence refs.
3. emit `m11h_safe_disable_rollback_snapshot.json`.

DoD:
- [ ] safe-disable/rollback checks pass.
- [ ] snapshot committed locally and durably.

### M11.I P14 Gate Rollup + M12 Handoff
Goal:
1. produce deterministic `P14` verdict and handoff.

Tasks:
1. roll up M11A-H outcomes in fixed order.
2. emit `m11i_p14_gate_verdict.json`.
3. emit `m12_handoff_pack.json`.

DoD:
- [ ] deterministic verdict is emitted.
- [ ] pass posture requires `ADVANCE_TO_P15` + `next_gate=M12_READY`.
- [ ] handoff pack committed locally and durably.

### M11.J M11 Cost-Outcome + Closure Sync
Goal:
1. close M11 with cost-outcome and summary parity.

Tasks:
1. emit `m11_phase_budget_envelope.json`.
2. emit `m11_phase_cost_outcome_receipt.json`.
3. emit `m11_execution_summary.json`.

DoD:
- [ ] budget + receipt artifacts committed locally and durably.
- [ ] summary parity checks pass.
- [ ] M11 closure sync passes with no unresolved blocker.

## 6) Blocker Taxonomy (Fail-Closed)
1. `M11-B1`: authority/handle closure failure.
2. `M11-B2`: SageMaker readiness failure.
3. `M11-B3`: input immutability failure.
4. `M11-B4`: train/eval execution failure.
5. `M11-B5`: eval gate failure.
6. `M11-B6`: MLflow lineage/provenance failure.
7. `M11-B7`: candidate bundle publication failure.
8. `M11-B8`: safe-disable/rollback closure failure.
9. `M11-B9`: P14 rollup/verdict inconsistency.
10. `M11-B10`: handoff publication failure.
11. `M11-B11`: phase cost-outcome closure failure.
12. `M11-B12`: summary/evidence publication parity failure.

## 7) Artifact Contract (M11)
1. `m11a_handle_closure_snapshot.json`
2. `m11b_sagemaker_readiness_snapshot.json`
3. `m11c_input_immutability_snapshot.json`
4. `m11d_train_eval_execution_snapshot.json`
5. `m11e_eval_gate_snapshot.json`
6. `m11f_mlflow_lineage_snapshot.json`
7. `m11g_candidate_bundle_snapshot.json`
8. `m11h_safe_disable_rollback_snapshot.json`
9. `m11i_p14_gate_verdict.json`
10. `m12_handoff_pack.json`
11. `m11_phase_budget_envelope.json`
12. `m11_phase_cost_outcome_receipt.json`
13. `m11_execution_summary.json`

## 8) Completion Checklist
- [ ] `M11.A` complete
- [ ] `M11.B` complete
- [ ] `M11.C` complete
- [ ] `M11.D` complete
- [ ] `M11.E` complete
- [ ] `M11.F` complete
- [ ] `M11.G` complete
- [ ] `M11.H` complete
- [ ] `M11.I` complete
- [ ] `M11.J` complete
- [ ] all active `M11-B*` blockers resolved

## 9) Planning Status
1. M11 planning is expanded and execution-grade.
2. Execution is blocked until M10 closure is green and handoff is committed.
