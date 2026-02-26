# Dev Substrate Deep Plan - M10 (P13 OFS_DATASET_COMMITTED)
_Status source of truth: `platform.build_plan.md`_
_This document provides orchestration-level deep planning detail for M10._
_Last updated: 2026-02-26_

## 0) Purpose
M10 closes:
1. `P13 OFS_DATASET_COMMITTED`.

M10 must prove:
1. OFS builds from M9-validated replay/as-of basis only.
2. dataset manifest and fingerprint are immutable and provenance-complete.
3. Iceberg table commit and Glue catalog state are coherent.
4. rollback recipe is executable and evidence-backed.
5. deterministic `P13` verdict and M11 handoff are committed.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P13`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M9.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary for M10
In scope:
1. OFS authority/handle closure.
2. Databricks readiness for OFS build jobs.
3. M9 input immutability and contract binding.
4. dataset build + quality gate execution.
5. Iceberg/Glue commit verification.
6. manifest/fingerprint/time-bound audit publication.
7. rollback recipe closure.
8. deterministic P13 verdict, M11 handoff, and cost-outcome closure.

Out of scope:
1. SageMaker training/evaluation execution (`M11`).
2. Promotion/rollback corridor operations (`M12`).

## 3) Deliverables
1. `m10a_handle_closure_snapshot.json`
2. `m10b_databricks_readiness_snapshot.json`
3. `m10c_input_binding_snapshot.json`
4. `m10d_ofs_build_execution_snapshot.json`
5. `m10e_quality_gate_snapshot.json`
6. `m10f_iceberg_commit_snapshot.json`
7. `m10g_manifest_fingerprint_snapshot.json`
8. `m10h_rollback_recipe_snapshot.json`
9. `m10i_p13_gate_verdict.json`
10. `m11_handoff_pack.json`
11. `m10_phase_budget_envelope.json`
12. `m10_phase_cost_outcome_receipt.json`
13. `m10_execution_summary.json`

## 4) Entry Gate and Current Posture
Entry gate for M10:
1. `M9` is `DONE`.
2. `P12` verdict is `ADVANCE_TO_P13`.
3. M9 blockers are resolved.

Current posture:
1. M10 planning is expanded to execution-grade.
2. Execution has not started.

## 4.1) Anti-Cram Law (Binding for M10)
M10 is not execution-ready unless these capability lanes are explicit:
1. authority + handles.
2. Databricks runtime identity/readiness.
3. input immutability and replay/as-of binding.
4. dataset build and quality gates.
5. Iceberg/Glue commit verification.
6. manifest/fingerprint and time-bound leakage audit.
7. rollback recipe evidence.
8. deterministic verdict/handoff.
9. cost-outcome closure.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M10.A | no unresolved required P13 handles |
| Databricks readiness | M10.B | workspace/job identity checks pass |
| Input binding | M10.C | M9 input contract and immutability pass |
| OFS build execution | M10.D | dataset build snapshot pass |
| Quality gates | M10.E | quality gate snapshot pass |
| Iceberg commit closure | M10.F | Iceberg + Glue commit checks pass |
| Manifest/fingerprint closure | M10.G | manifest + fingerprint + time-bound audit pass |
| Rollback recipe | M10.H | rollback recipe checks pass |
| P13 verdict + handoff | M10.I | `ADVANCE_TO_P14` + `m11_handoff_pack.json` |
| Cost-outcome + closure sync | M10.J | summary + budget + cost receipt pass |

## 5) Work Breakdown (Orchestration)

### M10.A P13 Authority + Handle Closure
Goal:
1. close required P13 handles before OFS execution.

Required handle set:
1. `DBX_WORKSPACE_URL`
2. `DBX_JOB_OFS_BUILD_V0`
3. `DBX_JOB_OFS_QUALITY_GATES_V0`
4. `OFS_MANIFEST_PATH_PATTERN`
5. `OFS_FINGERPRINT_PATH_PATTERN`
6. `OFS_TIME_BOUND_AUDIT_PATH_PATTERN`
7. `DATA_TABLE_FORMAT_PRIMARY`
8. `DATA_TABLE_CATALOG`
9. `OFS_ICEBERG_DATABASE`
10. `OFS_ICEBERG_WAREHOUSE_PREFIX_PATTERN`
11. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
12. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`

DoD:
- [ ] required handle matrix explicit and complete.
- [ ] unresolved handles are blocker-marked.
- [ ] `m10a_handle_closure_snapshot.json` committed locally and durably.

### M10.B Databricks Runtime Readiness
Goal:
1. prove workspace/job/identity surfaces are executable.

Tasks:
1. validate workspace URL/token access surfaces.
2. validate job definitions and expected compute policy.
3. emit `m10b_databricks_readiness_snapshot.json`.

DoD:
- [ ] Databricks readiness checks pass.
- [ ] readiness snapshot committed locally and durably.

### M10.C M9 Input Binding + Immutability
Goal:
1. bind OFS build inputs to M9 replay/as-of closure.

Tasks:
1. verify replay-basis and leakage reports from M9.
2. verify input references are immutable and run-scoped.
3. emit `m10c_input_binding_snapshot.json`.

DoD:
- [ ] input binding and immutability checks pass.
- [ ] snapshot committed locally and durably.

### M10.D OFS Dataset Build Execution
Goal:
1. execute OFS dataset build on Databricks.

Tasks:
1. run OFS build job with pinned parameters.
2. capture run refs and completion status.
3. emit `m10d_ofs_build_execution_snapshot.json`.

DoD:
- [ ] OFS build completes with pass posture.
- [ ] execution snapshot committed locally and durably.

### M10.E Quality-Gate Adjudication
Goal:
1. verify dataset quality gates and leakage/time-bound posture.

Tasks:
1. run/collect quality gate outcomes.
2. fail-closed on threshold or leakage/time-bound violations.
3. emit `m10e_quality_gate_snapshot.json`.

DoD:
- [ ] quality gates pass.
- [ ] blocker-free snapshot committed locally and durably.

### M10.F Iceberg + Glue Commit Verification
Goal:
1. prove table commit and catalog state are coherent.

Tasks:
1. verify Iceberg metadata and table state.
2. verify Glue catalog registration and refs.
3. emit `m10f_iceberg_commit_snapshot.json`.

DoD:
- [ ] Iceberg/Glue commit checks pass.
- [ ] commit snapshot committed locally and durably.

### M10.G Manifest + Fingerprint + Time-Bound Audit
Goal:
1. publish immutable OFS manifest/fingerprint and time-bound audit.

Tasks:
1. emit manifest and fingerprint artifacts.
2. emit time-bound/leakage audit artifact.
3. emit `m10g_manifest_fingerprint_snapshot.json`.

DoD:
- [ ] manifest + fingerprint committed.
- [ ] time-bound audit committed and green.
- [ ] snapshot committed locally and durably.

### M10.H Rollback Recipe Closure
Goal:
1. prove rollback recipe exists and is executable.

Tasks:
1. publish rollback recipe contract.
2. validate rollback preconditions and references.
3. emit `m10h_rollback_recipe_snapshot.json`.

DoD:
- [ ] rollback recipe checks pass.
- [ ] snapshot committed locally and durably.

### M10.I P13 Gate Rollup + M11 Handoff
Goal:
1. produce deterministic `P13` verdict and handoff.

Tasks:
1. roll up M10A-H outcomes in fixed order.
2. emit `m10i_p13_gate_verdict.json`.
3. emit `m11_handoff_pack.json`.

DoD:
- [ ] deterministic verdict is emitted.
- [ ] pass posture requires `ADVANCE_TO_P14` + `next_gate=M11_READY`.
- [ ] handoff pack committed locally and durably.

### M10.J M10 Cost-Outcome + Closure Sync
Goal:
1. close M10 with cost-outcome and summary parity.

Tasks:
1. emit `m10_phase_budget_envelope.json`.
2. emit `m10_phase_cost_outcome_receipt.json`.
3. emit `m10_execution_summary.json`.

DoD:
- [ ] budget + receipt artifacts committed locally and durably.
- [ ] summary parity checks pass.
- [ ] M10 closure sync passes with no unresolved blocker.

## 6) Blocker Taxonomy (Fail-Closed)
1. `M10-B1`: authority/handle closure failure.
2. `M10-B2`: Databricks readiness failure.
3. `M10-B3`: input binding/immutability failure.
4. `M10-B4`: OFS build execution failure.
5. `M10-B5`: quality gate failure.
6. `M10-B6`: Iceberg/Glue commit failure.
7. `M10-B7`: manifest/fingerprint/time-bound audit failure.
8. `M10-B8`: rollback recipe failure.
9. `M10-B9`: P13 rollup/verdict inconsistency.
10. `M10-B10`: handoff publication failure.
11. `M10-B11`: phase cost-outcome closure failure.
12. `M10-B12`: summary/evidence publication parity failure.

## 7) Artifact Contract (M10)
1. `m10a_handle_closure_snapshot.json`
2. `m10b_databricks_readiness_snapshot.json`
3. `m10c_input_binding_snapshot.json`
4. `m10d_ofs_build_execution_snapshot.json`
5. `m10e_quality_gate_snapshot.json`
6. `m10f_iceberg_commit_snapshot.json`
7. `m10g_manifest_fingerprint_snapshot.json`
8. `m10h_rollback_recipe_snapshot.json`
9. `m10i_p13_gate_verdict.json`
10. `m11_handoff_pack.json`
11. `m10_phase_budget_envelope.json`
12. `m10_phase_cost_outcome_receipt.json`
13. `m10_execution_summary.json`

## 8) Completion Checklist
- [ ] `M10.A` complete
- [ ] `M10.B` complete
- [ ] `M10.C` complete
- [ ] `M10.D` complete
- [ ] `M10.E` complete
- [ ] `M10.F` complete
- [ ] `M10.G` complete
- [ ] `M10.H` complete
- [ ] `M10.I` complete
- [ ] `M10.J` complete
- [ ] all active `M10-B*` blockers resolved

## 9) Planning Status
1. M10 planning is expanded and execution-grade.
2. Execution is blocked until M9 closure is green and `M11` handoff contract is defined from M10 verdict path.
