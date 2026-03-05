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

Entry conditions:
1. `M9.C` summary is green (`overall_pass=true`, `next_gate=M9.D_READY`).
2. replay-basis receipt from `M9.C` is readable and immutable.

Required upstream surfaces:
1. `evidence/dev_full/run_control/{m9c_execution_id}/m9c_execution_summary.json`
2. `evidence/dev_full/run_control/{m9c_execution_id}/m9c_replay_basis_receipt.json`
3. run-scoped replay-basis receipt key from `M9.C` summary.

Required handle set:
1. `LEARNING_FEATURE_ASOF_REQUIRED`
2. `LEARNING_LABEL_ASOF_REQUIRED`
3. `LEARNING_LABEL_MATURITY_DAYS_DEFAULT`
4. `LEARNING_FUTURE_TIMESTAMP_POLICY`

Tasks:
1. validate `feature_asof_utc`, `label_asof_utc`, and maturity policy input.
2. fail-closed if as-of or maturity controls are missing/invalid.
3. emit:
   - `m9d_asof_maturity_policy_snapshot.json`
   - `m9d_blocker_register.json`
   - `m9d_execution_summary.json`.

Deterministic verification algorithm:
1. read `M9.C` summary and enforce pass posture.
2. read replay-basis receipt from run-control and run-scoped receipt key and enforce fingerprint parity.
3. validate required handles are concrete and non-placeholder.
4. derive temporal anchors:
   - compute `feature_asof_utc` from max replay offset epoch,
   - set `label_asof_utc` at strict parity with `feature_asof_utc`,
   - derive `label_maturity_cutoff_utc = label_asof_utc - label_maturity_days`.
5. enforce temporal invariants:
   - as-of values are parseable UTC timestamps,
   - as-of values are not in the future relative to capture time,
   - maturity days is positive.
6. classify blockers:
   - `M9-B4` for as-of/maturity policy failures,
   - `M9-B11` for artifact publication/readback parity failures.
7. emit deterministic next gate:
   - `M9.E_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [x] as-of and maturity controls are explicit.
- [x] boundary values are coherent and auditable.
- [x] `m9d_asof_maturity_policy_snapshot.json` committed locally and durably.
- [x] `m9d_blocker_register.json` and `m9d_execution_summary.json` committed locally and durably.
- [x] `M9.E_READY` emitted with blocker count `0`.

Execution status:
1. Closure execution:
   - execution id: `m9d_p12_asof_maturity_20260226T080452Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M9.E_READY`.
2. Temporal policy closure:
   - `feature_asof_utc=2026-02-25T17:57:26Z`,
   - `label_asof_utc=2026-02-25T17:57:26Z`,
   - `label_maturity_days=30`,
   - `label_maturity_cutoff_utc=2026-01-26T17:57:26Z`.
3. Policy checks:
   - `LEARNING_FEATURE_ASOF_REQUIRED=true`,
   - `LEARNING_LABEL_ASOF_REQUIRED=true`,
   - `LEARNING_FUTURE_TIMESTAMP_POLICY=fail_closed`.
4. Invariant checks:
   - as-of timestamps are not future-valued,
   - maturity cutoff is not after label as-of,
   - replay receipt fingerprint parity (run-control vs run-scoped) passes.
5. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9d_p12_asof_maturity_20260226T080452Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9d_p12_asof_maturity_20260226T080452Z/`.

### M9.E Leakage Guardrail Evaluation
Goal:
1. detect and block any future timestamp leakage.

Entry conditions:
1. `M9.D` summary is green (`overall_pass=true`, `next_gate=M9.E_READY`).
2. as-of + maturity snapshot is readable and policy-complete.

Required upstream surfaces:
1. `evidence/dev_full/run_control/{m9d_execution_id}/m9d_execution_summary.json`
2. `evidence/dev_full/run_control/{m9d_execution_id}/m9d_asof_maturity_policy_snapshot.json`
3. `evidence/dev_full/run_control/{m9c_execution_id}/m9c_replay_basis_receipt.json`

Required handle set:
1. `LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN`
2. `LEARNING_FUTURE_TIMESTAMP_POLICY`
3. `LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS`
4. `LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS`
5. oracle stream-view location handles (`ORACLE_STORE_BUCKET`, `ORACLE_SOURCE_NAMESPACE`, `ORACLE_ENGINE_RUN_ID`, `S3_STREAM_VIEW_PREFIX_PATTERN`)

Tasks:
1. run timestamp boundary checks against configured fields.
2. record violations with row/sample references.
3. emit:
   - `m9e_leakage_guardrail_report.json`
   - `m9e_blocker_register.json`
   - `m9e_execution_summary.json`.

Deterministic verification algorithm:
1. read M9.D summary/snapshot and enforce pass posture and fail-closed future policy.
2. read M9.C replay-basis receipt and evaluate each origin-offset row against:
   - `last_offset_epoch <= feature_asof_utc_epoch`
   - `last_offset_epoch <= label_asof_utc_epoch`.
3. materialize row-level check samples (topic/partition/offset/as-of bounds).
4. evaluate truth-surface leakage guardrail:
   - list active stream-view `output_id=*` prefixes under oracle stream-view root,
   - fail-closed if any active output intersects `LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS`.
5. evaluate guardrail config completeness:
   - forbidden future-field list must be concrete and non-empty.
6. classify blockers:
   - `M9-B5` for leakage/future-boundary violations (including `DFULL-RUN-B12.2` posture),
   - `M9-B11` for artifact publication/readback parity failures.
7. publish leakage report to:
   - run-scope evidence path (`LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN`),
   - run-control execution path (`m9e_leakage_guardrail_report.json`).
8. emit deterministic next gate:
   - `M9.F_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 12 minutes wall clock.

DoD:
- [x] no unresolved leakage violation remains.
- [x] boundary breach emits blocker `DFULL-RUN-B12.2` fail-closed.
- [x] `m9e_leakage_guardrail_report.json` committed locally and durably.
- [x] `m9e_blocker_register.json` and `m9e_execution_summary.json` committed locally and durably.
- [x] `M9.F_READY` emitted with blocker count `0`.

Execution status:
1. Closure execution:
   - execution id: `m9e_p12_leakage_guardrail_20260226T080940Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M9.F_READY`.
2. Temporal leakage checks:
   - rows checked: `1`,
   - violation count: `0`,
   - boundary sample confirms `last_offset_epoch <= feature/label as-of epochs`.
3. Truth-surface leakage checks:
   - active stream-view outputs:
     - `arrival_events_5B`,
     - `s1_arrival_entities_6B`,
     - `s3_event_stream_with_fraud_6B`,
     - `s3_flow_anchor_with_fraud_6B`,
   - forbidden truth-output intersection: none.
4. Policy checks:
   - future policy enforced: `fail_closed`,
   - forbidden future-field and truth-output lists are concrete/non-empty.
5. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9e_p12_leakage_guardrail_20260226T080940Z/`,
   - durable run-control: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9e_p12_leakage_guardrail_20260226T080940Z/`,
   - durable run-scoped report:
     - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/input/leakage_guardrail_report.json`.

### M9.F Runtime-vs-Learning Surface Separation
Goal:
1. prove runtime lanes are isolated from offline truth surfaces.

Entry conditions:
1. `M9.E` summary is green (`overall_pass=true`, `next_gate=M9.F_READY`).
2. leakage guardrail report is readable and blocker-free.

Required upstream surfaces:
1. `evidence/dev_full/run_control/{m9e_execution_id}/m9e_execution_summary.json`
2. `evidence/dev_full/run_control/{m9e_execution_id}/m9e_leakage_guardrail_report.json`
3. `evidence/dev_full/run_control/{m9b_execution_id}/m9b_handoff_scope_snapshot.json` (for runtime evidence refs scope check)
4. interface boundary contract:
   - `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`

Required handle set:
1. `LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS`
2. `LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS`
3. `ORACLE_STORE_BUCKET`
4. `ORACLE_SOURCE_NAMESPACE`
5. `ORACLE_ENGINE_RUN_ID`
6. `S3_STREAM_VIEW_PREFIX_PATTERN`

Tasks:
1. validate live-runtime forbid set (`s4_*` + future-derived fields).
2. verify learning-only access boundaries for truth products.
3. emit:
   - `m9f_surface_separation_snapshot.json`
   - `m9f_blocker_register.json`
   - `m9f_execution_summary.json`.

Deterministic verification algorithm:
1. read M9.E summary/report and enforce pass posture.
2. resolve required handles and forbidden sets.
3. enumerate active runtime stream-view `output_id=*` prefixes from oracle stream-view root.
4. evaluate truth-surface separation:
   - fail if active outputs intersect `LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS`,
   - fail if active outputs intersect interface-declared `truth_products`.
5. evaluate future-derived surface separation:
   - derive output ids associated with forbidden future fields from interface contract notes,
   - fail if any derived output id appears in active runtime outputs.
6. evaluate runtime-vs-learning boundary refs:
   - runtime evidence refs from M9.B must not point to learning/truth-product surfaces.
7. classify blockers:
   - `M9-B6` for separation failures,
   - `M9-B11` for artifact publication/readback parity failures.
8. emit deterministic next gate:
   - `M9.G_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 12 minutes wall clock.

DoD:
- [x] runtime truth-surface violations are absent.
- [x] separation checks are explicit and evidence-backed.
- [x] `m9f_surface_separation_snapshot.json` committed locally and durably.
- [x] `m9f_blocker_register.json` and `m9f_execution_summary.json` committed locally and durably.
- [x] `M9.G_READY` emitted with blocker count `0`.

Execution status:
1. Closure execution:
   - execution id: `m9f_p12_surface_sep_20260226T081356Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M9.G_READY`.
2. Runtime output surface:
   - active outputs:
     - `arrival_events_5B`,
     - `s1_arrival_entities_6B`,
     - `s3_event_stream_with_fraud_6B`,
     - `s3_flow_anchor_with_fraud_6B`.
3. Separation results:
   - forbidden truth-output intersection: none,
   - interface truth-product intersection: none,
   - future-derived output intersection: none,
   - runtime evidence-ref leakage: none.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9f_p12_surface_sep_20260226T081356Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9f_p12_surface_sep_20260226T081356Z/`.

### M9.G Learning Input Readiness Snapshot
Goal:
1. publish consolidated readiness evidence for P12 closure.

Entry conditions:
1. `M9.C`, `M9.D`, `M9.E`, and `M9.F` summaries are all green at pinned execution ids.
2. run-control artifacts for each upstream lane are readable from `S3_EVIDENCE_BUCKET`.
3. run-scoped learning artifacts from prior lanes are readable:
   - replay basis receipt (`M9.C`),
   - leakage guardrail report (`M9.E`).
4. required handles are pinned and non-placeholder:
   - `S3_EVIDENCE_BUCKET`,
   - `LEARNING_INPUT_READINESS_PATH_PATTERN`,
   - `S3_RUN_CONTROL_ROOT_PATTERN`.

Tasks:
1. aggregate outputs from `M9.C..M9.F` in fixed order.
2. validate deterministic gate chain:
   - `M9.C -> M9.D_READY`,
   - `M9.D -> M9.E_READY`,
   - `M9.E -> M9.F_READY`,
   - `M9.F -> M9.G_READY`.
3. validate run-scope coherence across upstream summaries:
   - single `platform_run_id`,
   - single `scenario_run_id`.
4. validate run-scoped learning evidence reachability:
   - `m9c_replay_basis_receipt` key exists,
   - `m9e_leakage_guardrail_report` key exists.
5. emit deterministic artifacts:
   - `m9g_learning_input_readiness_snapshot.json`,
   - `m9g_blocker_register.json`,
   - `m9g_execution_summary.json`.
6. publish snapshot to run-control and run-scoped learning path via `LEARNING_INPUT_READINESS_PATH_PATTERN`.
7. classify blockers:
   - `M9-B7` for readiness incompleteness/inconsistency,
   - `M9-B11` for artifact publication/readback parity failures.
8. emit deterministic next gate:
   - `M9.H_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [x] readiness snapshot is complete and parseable.
- [x] blocker register is coherent with prior checks.
- [x] run-scope continuity across `M9.C..M9.F` is explicitly proven.
- [x] `m9g_learning_input_readiness_snapshot.json` committed locally and durably.
- [x] `m9g_blocker_register.json` and `m9g_execution_summary.json` committed locally and durably.
- [x] `M9.H_READY` emitted with blocker count `0`.

Execution status:
1. Closure execution:
   - execution id: `m9g_p12_learning_input_readiness_20260226T081947Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M9.H_READY`.
2. Upstream gate-chain rollup:
   - `M9.C`: pass + `M9.D_READY`,
   - `M9.D`: pass + `M9.E_READY`,
   - `M9.E`: pass + `M9.F_READY`,
   - `M9.F`: pass + `M9.G_READY`.
3. Run-scope continuity:
   - `platform_run_id`: `platform_20260223T184232Z` (single value),
   - `scenario_run_id`: `scenario_38753050f3b70c666e16f7552016b330` (single value).
4. Run-scoped learning artifacts:
   - replay-basis receipt exists:
     - `evidence/runs/platform_20260223T184232Z/learning/input/replay_basis_receipt.json`,
   - leakage-guardrail report exists:
     - `evidence/runs/platform_20260223T184232Z/learning/input/leakage_guardrail_report.json`.
5. Readiness snapshot publish targets:
   - run-control: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9g_p12_learning_input_readiness_20260226T081947Z/`,
   - run-scoped: `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/input/readiness_snapshot.json`.
6. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9g_p12_learning_input_readiness_20260226T081947Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9g_p12_learning_input_readiness_20260226T081947Z/`.

### M9.H P12 Gate Rollup + M10 Handoff
Goal:
1. produce deterministic P12 verdict and handoff.

Entry conditions:
1. `M9.A..M9.G` summaries are all green and readable from run-control surfaces.
2. `M9.G` closure posture is pass with `next_gate=M9.H_READY`.
3. active run scope is single-valued across all M9 source summaries.
4. required handles for durable publication are pinned and non-placeholder:
   - `S3_EVIDENCE_BUCKET`,
   - `S3_RUN_CONTROL_ROOT_PATTERN`.

Tasks:
1. roll up M9A-G outcomes in fixed order.
2. validate gate-chain continuity:
   - `M9.A -> M9.B_READY`,
   - `M9.B -> M9.C_READY`,
   - `M9.C -> M9.D_READY`,
   - `M9.D -> M9.E_READY`,
   - `M9.E -> M9.F_READY`,
   - `M9.F -> M9.G_READY`,
   - `M9.G -> M9.H_READY`.
3. compute deterministic pass-matrix for P12 source phases and run-scope continuity assertions.
4. emit deterministic artifacts:
   - `m9h_p12_rollup_matrix.json`,
   - `m9h_p12_gate_verdict.json`,
   - `m10_handoff_pack.json`,
   - `m9h_execution_summary.json`.
5. classify blockers:
   - `M9-B8` for rollup/verdict inconsistency,
   - `M9-B9` for handoff publication/contract failure,
   - `M9-B11` for artifact publication/readback parity failures.
6. emit deterministic pass posture:
   - `verdict=ADVANCE_TO_P13`,
   - `next_gate=M10_READY`,
   - otherwise fail closed to `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [x] deterministic verdict is emitted.
- [x] pass posture requires `ADVANCE_TO_P13` and `next_gate=M10_READY`.
- [x] handoff pack committed locally and durably.
- [x] rollup matrix + execution summary committed locally and durably.

Execution status:
1. Closure execution:
   - execution id: `m9h_p12_gate_rollup_20260226T082548Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_P13`, `next_gate=M10_READY`.
2. Source gate-chain rollup:
   - `M9.A`: pass + `M9.B_READY`,
   - `M9.B`: pass + `M9.C_READY`,
   - `M9.C`: pass + `M9.D_READY`,
   - `M9.D`: pass + `M9.E_READY`,
   - `M9.E`: pass + `M9.F_READY`,
   - `M9.F`: pass + `M9.G_READY`,
   - `M9.G`: pass + `M9.H_READY`.
3. Run scope continuity:
   - `platform_run_id`: `platform_20260223T184232Z` (single value),
   - `scenario_run_id`: `scenario_38753050f3b70c666e16f7552016b330` (single value).
4. Handoff pack:
   - `m10_handoff_pack.json` emitted with required refs for M10 entry,
   - `m10_entry_gate.required_verdict=ADVANCE_TO_P13`,
   - `m10_entry_gate.next_gate=M10_READY`.
5. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9h_p12_gate_rollup_20260226T082548Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9h_p12_gate_rollup_20260226T082548Z/`.

### M9.I M9 Phase Budget + Cost-Outcome Closure
Goal:
1. publish cost-to-outcome artifacts for M9.

Entry conditions:
1. `M9.H` is green with:
   - `verdict=ADVANCE_TO_P13`,
   - `next_gate=M10_READY`,
   - blocker count `0`.
2. `M9.A..M9.H` summaries and contract artifacts are readable from run-control surfaces.
3. active run scope remains single-valued across `M9.A..M9.H`.
4. cost handles are pinned and parseable:
   - `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD`,
   - `DEV_FULL_BUDGET_ALERT_1_USD`,
   - `DEV_FULL_BUDGET_ALERT_2_USD`,
   - `DEV_FULL_BUDGET_ALERT_3_USD`,
   - `BUDGET_CURRENCY`,
   - `COST_CAPTURE_SCOPE`,
   - `AWS_COST_CAPTURE_ENABLED`.

Tasks:
1. validate M9 upstream closure matrix (`M9.A..M9.H`) and run-scope continuity.
2. capture AWS MTD cost (`month_start..tomorrow`) from billing region.
3. validate budget threshold ordering:
   - `alert_1 < alert_2 < alert_3 <= monthly_limit`.
4. emit deterministic artifacts:
   - `m9_phase_budget_envelope.json`,
   - `m9_phase_cost_outcome_receipt.json`,
   - `m9i_blocker_register.json`,
   - `m9i_execution_summary.json`.
5. classify blockers:
   - `M9-B10` for cost-outcome closure failures,
   - `M9-B11` for artifact publication/readback parity failures.
6. emit deterministic next gate:
   - `M9.J_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [x] budget envelope is valid and parseable.
- [x] cost-outcome receipt is coherent with emitted artifacts.
- [x] `m9_phase_budget_envelope.json` and `m9_phase_cost_outcome_receipt.json` committed locally and durably.
- [x] `m9i_execution_summary.json` committed locally and durably with `next_gate=M9.J_READY` when blocker-free.

Execution status:
1. Closure execution:
   - execution id: `m9i_phase_cost_closure_20260226T083151Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M9J`, `next_gate=M9.J_READY`.
2. Cost posture:
   - `budget_currency=USD`,
   - threshold envelope: `120/210/270` over `monthly_limit=300`,
   - captured AWS MTD spend: `89.2979244404 USD`,
   - capture scope: `aws_only_pre_m11_databricks_cost_deferred`,
   - Databricks capture mode: `DEFERRED` (disabled in this lane).
3. Contract parity:
   - required upstream artifacts: `18`,
   - readable upstream artifacts: `18`,
   - required M9.I outputs: `2`,
   - published M9.I outputs: `2`,
   - `all_required_available=true`.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9i_phase_cost_closure_20260226T083151Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9i_phase_cost_closure_20260226T083151Z/`.

### M9.J M9 Closure Sync
Goal:
1. close M9 and publish authoritative summary.

Entry conditions:
1. `M9.I` is green with:
   - `verdict=ADVANCE_TO_M9J`,
   - `next_gate=M9.J_READY`,
   - blocker count `0`.
2. all M9 lane summaries (`M9.A..M9.I`) are readable from run-control surfaces.
3. active run scope remains single-valued across `M9.A..M9.I`.
4. M9 contract artifacts are readable and parity-checkable:
   - `m9a..m9h` lane artifacts,
   - `m10_handoff_pack.json`,
   - `m9_phase_budget_envelope.json`,
   - `m9_phase_cost_outcome_receipt.json`.

Tasks:
1. emit `m9_execution_summary.json`.
2. verify local+durable parity of M9 outputs.
3. update M9 closure status and next gate readiness.
4. emit deterministic closure posture:
   - `verdict=ADVANCE_TO_M10`,
   - `next_gate=M10_READY`,
   - otherwise fail closed to `HOLD_REMEDIATE`.
5. classify blockers:
   - `M9-B10` for closure-sync completeness failure,
   - `M9-B11` for summary/evidence publication parity failure.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [x] `m9_execution_summary.json` committed locally and durably.
- [x] M9 closure sync passes with no unresolved blocker.

Execution status:
1. Closure execution:
   - execution id: `m9j_closure_sync_20260226T083701Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M10`, `next_gate=M10_READY`.
2. Summary-chain closure:
   - `M9.A..M9.I` all readable and green with expected next-gate continuity.
3. Contract parity:
   - required upstream artifacts: `20`,
   - readable upstream artifacts: `20`,
   - required M9.J outputs: `1`,
   - published M9.J outputs: `1`,
   - `all_required_available=true`.
4. Entry posture for M10:
   - `p12_verdict=ADVANCE_TO_P13` retained from M9.H,
   - `m10_handoff_pack.json` reference preserved in `m9_execution_summary.json`,
   - phase closure verdict now `ADVANCE_TO_M10`.
5. Evidence:
   - local: `runs/dev_substrate/dev_full/m9/m9j_closure_sync_20260226T083701Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m9j_closure_sync_20260226T083701Z/`.

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
- [x] `M9.D` complete
- [x] `M9.E` complete
- [x] `M9.F` complete
- [x] `M9.G` complete
- [x] `M9.H` complete
- [x] `M9.I` complete
- [x] `M9.J` complete
- [x] all active `M9-B*` blockers resolved

## 9) Planning Status
1. M9 planning is expanded and execution-grade.
2. `M9.A` is closed green with `next_gate=M9.B_READY`.
3. `M9.B` is closed green with `next_gate=M9.C_READY`.
4. `M9.C` is closed green with `next_gate=M9.D_READY`.
5. `M9.D` is closed green with `next_gate=M9.E_READY`.
6. `M9.E` is closed green with `next_gate=M9.F_READY`.
7. `M9.F` is closed green with `next_gate=M9.G_READY`.
8. `M9.G` is closed green with `next_gate=M9.H_READY`.
9. `M9.H` is closed green with `verdict=ADVANCE_TO_P13` and `next_gate=M10_READY`.
10. `M9.I` is closed green with `next_gate=M9.J_READY`.
11. `M9.J` is closed green with `verdict=ADVANCE_TO_M10` and `next_gate=M10_READY`.
12. M9 is `DONE`.
13. Next action is `M10.A` authority + handle closure.

## 10) DD-4 Closure Contract (Replay-Offset Semantics)
Debt item:
1. `DD-4` replay-offset semantics pin.

Closure decision:
1. `origin_offset_ranges` semantics are mode-aware and now pinned explicitly:
   - when `IG_EDGE_MODE=apigw_lambda_ddb`, origin offsets are event-time epoch-second boundaries from `IG_ADMISSION_INDEX_PROXY`,
   - when `IG_EDGE_MODE=kafka_direct`, origin offsets are broker topic/partition offsets from `KAFKA_TOPIC_PARTITION_OFFSETS`.

Owner:
1. Learning-input owner (`M9` lane owner).

Source-of-truth paths:
1. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` (`LEARNING_REPLAY_BASIS_MODE`, `LEARNING_ORIGIN_OFFSET_SEMANTICS`).
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P12` pass-gate semantics).
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M9.build_plan.md` (this section).

Closure condition (met):
1. no ambiguity remains on whether replay basis references epoch-seconds or broker offsets.
2. P12 evidence contract now has deterministic interpretation for both edge modes.
