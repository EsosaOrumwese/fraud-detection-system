# Dev Substrate Stress Plan - M11 (P14 MF_EVAL_COMMITTED)
_Parent authority: `platform.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-05_
_Current posture: `S1_GREEN` (strict `M11-ST-S1` executed green; next gate `M11_ST_S2_READY`)._

## 0) Purpose
M11 stress validates managed model-factory train/eval closure under realistic production pressure with deterministic provenance and fail-closed gate semantics.

M11 stress must prove:
1. P14 execution binds only to immutable M10 closure artifacts.
2. SageMaker train/eval runtime is reachable, policy-correct, and budget-safe.
3. evaluation gates (compatibility, leakage, performance, stability) are explicit and deterministic.
4. MLflow lineage/provenance is complete enough for deterministic replay.
5. candidate bundle publication and safe-disable/rollback artifacts are operationally usable.
6. P14 rollup verdict and M12 handoff are deterministic and reproducible.
7. closure cost-to-outcome evidence is attributable with no unexplained spend.
8. non-gate acceptance (utility, reproducibility, operability, auditability, decision quality) is explicitly satisfied.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M11.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M10.stress_test.md`
2. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.impl_actual.md`

Strict entry authority (current):
1. Parent `M10-ST-S5`: `m10_stress_s5_20260305T014017Z` (`overall_pass=true`, `verdict=ADVANCE_TO_M11`, `next_gate=M11_READY`, `open_blocker_count=0`).
2. Parent lane `M10.J`: `m10j_stress_s5_20260305T014017Z` (`overall_pass=true`, `verdict=ADVANCE_TO_M11`, `next_gate=M11_READY`).
3. M10 handoff lane `M10.I`: `m10i_stress_s4_20260305T013131Z` (`m11_handoff_pack.json` readable, deterministic pass chain `A..H`).

Legacy receipts (history only, not closure authority):
1. historical M11 managed closure receipts embedded in `platform.M11.build_plan.md` (2026-02-26/27).

## 2) Stage-A Findings (M11)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M11-ST-F1` | `ACCEPT` | strict M10 closure authority is green and deterministic for M11 entry. | use `m10_stress_s5_20260305T014017Z` as sole entry authority. |
| `M11-ST-F2` | `ACCEPT` | dedicated M11 stress authority is now pinned in `stress_test/`. | maintain this file as sole M11 stress authority. |
| `M11-ST-F3` | `ACCEPT` | parent M11 stress orchestrator now exists for `S0` and enforces fail-closed gates. | extend stage-by-stage (`S1..S5`) under the same fail-closed contract. |
| `M11-ST-F4` | `PREVENT` | execution-lane implementation remains partial (`m11a,m11b` present; `m11c..m11j` missing). | fail closed for any stage requiring missing lanes until implementation is complete. |
| `M11-ST-F5` | `PREVENT` | historical M11 receipts can be mistaken for current closure authority. | enforce stale-evidence rejection and run-scope continuity checks at every stage. |
| `M11-ST-F6` | `PREVENT` | without explicit non-gate acceptance checks, chain pass can mask weak production readiness. | require utility/reproducibility/operability/auditability/decision-quality artifacts before closure. |
| `M11-ST-F7` | `OBSERVE` | SageMaker managed quotas and regional capacity can bottleneck `M11.D`. | include explicit quota/capacity diagnostics and targeted remediation lane in S1. |
| `M11-ST-F8` | `OBSERVE` | package-group and IAM/SSM boundary drift can present as intermittent readiness failures. | enforce deterministic readiness checks in S0 and continuity checks downstream. |
| `M11-ST-F9` | `OBSERVE` | MLflow tracking URI/secret drift can break lineage closure after successful eval. | fail-closed lineage checks in S2 with source-authority guard snapshots. |
| `M11-ST-F10` | `PREVENT` | cost-attribution closure can be skipped if not pinned in parent stage design. | enforce `m11_phase_budget_envelope.json` + `m11_phase_cost_outcome_receipt.json` in S5. |
| `M11-ST-F11` | `ACCEPT` | M11 build authority already defines lane contracts and gate chain at high fidelity. | reuse as stress target with explicit fail-closed mapping and budget gates. |
| `M11-ST-F12` | `ACCEPT` | Data Engine remains black-box for platform stress closure. | prohibit implementation introspection dependencies in M11 closure proofs. |

## 3) Scope Boundary for M11 Stress
In scope:
1. P14 authority and handle closure with strict M10 continuity.
2. SageMaker runtime readiness and managed train/eval execution.
3. immutable M10 input-binding and run-scope parity checks.
4. deterministic evaluation gate adjudication with explicit metric and leakage evidence.
5. MLflow lineage/provenance commit and closure.
6. candidate bundle publication and model operability evidence.
7. safe-disable/rollback closure plus bounded reproducibility proof.
8. deterministic P14 rollup + M12 handoff publication.
9. phase budget envelope and attributable cost-outcome closure.

Out of scope:
1. M12 promotion/rollback execution itself.
2. M13 full-platform verdict/teardown execution.
3. Data Engine internal implementation details (black-box boundary remains).
4. local-only artifacts as closure authority.

## 4) M11 Stress Handle Packet (Pinned)
1. `M11_STRESS_PROFILE_ID = "mf_eval_strict_stress_v0"`.
2. `M11_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m11_blocker_register.json"`.
3. `M11_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m11_execution_summary.json"`.
4. `M11_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m11_decision_log.json"`.
5. `M11_STRESS_GATE_VERDICT_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m11_gate_verdict.json"`.
6. `M11_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY = true`.
7. `M11_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX = true`.
8. `M11_STRESS_DISALLOW_WAIVED_REALISM = true`.
9. `M11_STRESS_FAIL_ON_STALE_UPSTREAM = true`.
10. `M11_STRESS_EXPECTED_ENTRY_EXECUTION = "m10_stress_s5_20260305T014017Z"`.
11. `M11_STRESS_EXPECTED_ENTRY_GATE = "M11_READY"`.
12. `M11_STRESS_EXPECTED_NEXT_GATE_ON_PASS = "M12_READY"`.
13. `M11_STRESS_MAX_RUNTIME_MINUTES = 320`.
14. `M11_STRESS_MAX_SPEND_USD = 185`.
15. `M11_STRESS_REQUIRE_NON_GATE_ACCEPTANCE = true`.

## 5) Fail-Closed Preflight Gates
`M11-ST-G0` decision completeness:
1. all required handles for active stage are resolved (no `TO_PIN`/placeholder/wildcard for required keys).

`M11-ST-G1` phase coverage:
1. active stage explicitly covers authority, runtime identity, data/feature binding, evidence parity, rollback/rerun, budget/cost, and teardown posture.

`M11-ST-G2` stale-evidence guard:
1. only current strict chain receipts are accepted for closure (`M10 -> M11` current run scope).

`M11-ST-G3` locality/source-authority guard:
1. closure uses durable managed evidence refs only; no local-only authority.

`M11-ST-G4` Data Engine black-box guard:
1. no implementation-introspection dependency for closure proof.

`M11-ST-G5` realism guard:
1. no toy/waived realism posture for closure lanes.

`M11-ST-G6` implementation-readiness guard:
1. active stage cannot execute unless all required lane scripts and parent runner paths exist.

`M11-ST-G7` non-gate acceptance guard:
1. utility/reproducibility/operability/auditability/decision-quality evidence is required before M11 closure.

## 6) Capability-Lane Coverage Matrix (M11)
| Capability lane | Stress stage owner | Minimum pass evidence |
| --- | --- | --- |
| authority/handles | `S0` | `m11a_handle_closure_snapshot.json` pass posture |
| SageMaker runtime readiness | `S0` | `m11b_sagemaker_readiness_snapshot.json` pass posture |
| immutable input binding | `S1` | `m11c_input_immutability_snapshot.json` pass posture |
| managed train/eval execution | `S1` | `m11d_train_eval_execution_snapshot.json` pass posture |
| eval gate adjudication | `S2` | `m11e_eval_gate_snapshot.json` + `m11_eval_vs_baseline_report.json` pass posture |
| MLflow lineage/provenance | `S2` | `m11f_mlflow_lineage_snapshot.json` pass posture |
| candidate bundle publication + operability | `S3` | `m11g_candidate_bundle_snapshot.json` + `m11_model_operability_report.json` pass posture |
| safe-disable/rollback + reproducibility | `S3` | `m11h_safe_disable_rollback_snapshot.json` + `m11_reproducibility_check.json` pass posture |
| P14 rollup + M12 handoff | `S4` | `m11i_p14_gate_verdict.json` (`ADVANCE_TO_P15`, `M12_READY`) + `m12_handoff_pack.json` |
| cost-outcome + closure sync | `S5` | `m11_phase_budget_envelope.json`, `m11_phase_cost_outcome_receipt.json`, final `m11_execution_summary.json` (`ADVANCE_TO_M12`, `M12_READY`) |

## 7) Execution Topology (Parent `S0..S5`)
1. `S0`: authority + SageMaker readiness (`A`,`B`).
2. `S1`: input binding + train/eval execution (`C`,`D`).
3. `S2`: eval adjudication + MLflow lineage (`E`,`F`).
4. `S3`: candidate bundle + safe-disable/rollback (`G`,`H`).
5. `S4`: P14 rollup + M12 handoff (`I`).
6. `S5`: cost-outcome + final closure sync (`J`).

## 8) Stage Plans
### 8.1 `M11-ST-S0` - Authority + SageMaker readiness (`A`,`B`)
Objective:
1. validate M11 authority/handle closure and SageMaker runtime readiness from strict M10 entry.

Entry criteria:
1. strict M10 entry receipt `m10_stress_s5_20260305T014017Z` is readable and pass.
2. lane scripts for `A,B` exist and are executable.

Execution steps:
1. run lane `A` handle-closure checks.
2. run lane `B` SageMaker readiness checks.
3. emit parent guard snapshots and stage receipts.

Fail-closed blockers:
1. `M11-ST-B1`: authority/handle closure failure.
2. `M11-ST-B2`: SageMaker readiness failure.
3. `M11-ST-B12`: artifact parity failure.
4. `M11-ST-B16`: locality/source-authority/Data-Engine-boundary failure.
5. `M11-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `35` minutes.
2. max spend: `$14`.

Pass gate:
1. `next_gate=M11_ST_S1_READY`.

### 8.2 `M11-ST-S1` - Input binding + train/eval execution (`C`,`D`)
Objective:
1. prove immutable M10 binding and execute deterministic managed train/eval within budget.

Entry criteria:
1. successful `S0` with `next_gate=M11_ST_S1_READY`.
2. lane scripts for `C,D` exist and are executable.

Execution steps:
1. run lane `C` immutable input-binding checks.
2. run lane `D` managed training + evaluation execution checks.
3. emit parent stage receipts and guard snapshots.

Fail-closed blockers:
1. `M11-ST-B3`: input binding/immutability failure.
2. `M11-ST-B4`: train/eval execution failure.
3. `M11-ST-B12`: artifact parity failure.
4. `M11-ST-B18`: execution-lane implementation hole.
5. `M11-ST-B19`: managed-service quota/capacity/access boundary unresolved.

Runtime/cost budget:
1. max runtime: `130` minutes.
2. max spend: `$78`.

Pass gate:
1. `next_gate=M11_ST_S2_READY`.

### 8.3 `M11-ST-S2` - Eval adjudication + MLflow lineage (`E`,`F`)
Objective:
1. adjudicate deterministic eval gates and close lineage/provenance with replay-grade completeness.

Entry criteria:
1. successful `S1` with `next_gate=M11_ST_S2_READY`.
2. lane scripts for `E,F` exist and are executable.

Execution steps:
1. run lane `E` compatibility/leakage/performance/stability gate checks.
2. run lane `F` MLflow lineage/provenance closure checks.
3. emit stage receipts, eval-vs-baseline report, and lineage proof artifacts.

Fail-closed blockers:
1. `M11-ST-B5`: eval gate failure.
2. `M11-ST-B6`: MLflow lineage/provenance failure.
3. `M11-ST-B12`: artifact parity failure.
4. `M11-ST-B13`: non-gate acceptance evidence failure.
5. `M11-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `45` minutes.
2. max spend: `$24`.

Pass gate:
1. `next_gate=M11_ST_S3_READY`.

### 8.4 `M11-ST-S3` - Candidate bundle + safe-disable/rollback (`G`,`H`)
Objective:
1. verify candidate publication operability and deterministic safe-disable/rollback with bounded reproducibility.

Entry criteria:
1. successful `S2` with `next_gate=M11_ST_S3_READY`.
2. lane scripts for `G,H` exist and are executable.

Execution steps:
1. run lane `G` candidate bundle publication + operability checks.
2. run lane `H` safe-disable/rollback + reproducibility checks.
3. emit stage receipts and non-gate acceptance artifacts.

Fail-closed blockers:
1. `M11-ST-B7`: candidate bundle publication failure.
2. `M11-ST-B8`: safe-disable/rollback failure.
3. `M11-ST-B12`: artifact parity failure.
4. `M11-ST-B13`: non-gate acceptance evidence failure.
5. `M11-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `40` minutes.
2. max spend: `$21`.

Pass gate:
1. `next_gate=M11_ST_S4_READY`.

### 8.5 `M11-ST-S4` - P14 rollup + M12 handoff (`I`)
Objective:
1. compute deterministic P14 verdict and publish M12 handoff pack.

Entry criteria:
1. successful `S3` with `next_gate=M11_ST_S4_READY`.
2. lane script for `I` exists and is executable.

Execution steps:
1. aggregate lane readiness in fixed order (`A..H`).
2. emit deterministic rollup/verdict (`ADVANCE_TO_P15`, `M12_READY`).
3. emit `m12_handoff_pack.json`.

Fail-closed blockers:
1. `M11-ST-B9`: P14 rollup/verdict inconsistency.
2. `M11-ST-B10`: M12 handoff publication/contract failure.
3. `M11-ST-B12`: artifact parity failure.
4. `M11-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `25` minutes.
2. max spend: `$10`.

Pass gate:
1. `next_gate=M11_ST_S5_READY`.

### 8.6 `M11-ST-S5` - Cost-outcome + final closure (`J`)
Objective:
1. finalize M11 with deterministic summary, closure recommendation, and non-gate acceptance proof.

Entry criteria:
1. successful `S4` with `next_gate=M11_ST_S5_READY`.
2. lane script for `J` exists and is executable.

Execution steps:
1. validate parity/readability across `A..I` artifacts.
2. compute phase budget envelope and cost-outcome receipt.
3. enforce non-gate acceptance closure checks.
4. emit final parent receipts and gate verdict.

Fail-closed blockers:
1. `M11-ST-B11`: cost-outcome closure failure.
2. `M11-ST-B12`: summary/evidence publication parity failure.
3. `M11-ST-B16`: locality/source-authority/Data-Engine-boundary violation.
4. `M11-ST-B17`: non-realistic closure posture.
5. `M11-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$18`.

Pass gate:
1. `overall_pass=true`.
2. `verdict=ADVANCE_TO_M12`.
3. `next_gate=M12_READY`.
4. `open_blocker_count=0`.

## 9) Blocker Taxonomy (M11 Parent)
1. `M11-ST-B1`: authority/handle closure failure.
2. `M11-ST-B2`: SageMaker readiness failure.
3. `M11-ST-B3`: input binding/immutability failure.
4. `M11-ST-B4`: train/eval execution failure.
5. `M11-ST-B5`: eval gate failure.
6. `M11-ST-B6`: MLflow lineage/provenance failure.
7. `M11-ST-B7`: candidate bundle publication failure.
8. `M11-ST-B8`: safe-disable/rollback failure.
9. `M11-ST-B9`: P14 rollup/verdict inconsistency.
10. `M11-ST-B10`: M12 handoff publication failure.
11. `M11-ST-B11`: phase cost-outcome closure failure.
12. `M11-ST-B12`: summary/evidence publication parity failure.
13. `M11-ST-B13`: non-gate acceptance failure (utility/reproducibility/operability/auditability/decision quality).
14. `M11-ST-B14`: unresolved decision/input hole.
15. `M11-ST-B15`: phase-coverage lane hole.
16. `M11-ST-B16`: runtime locality/source-authority/Data-Engine-boundary violation.
17. `M11-ST-B17`: non-realistic data posture used for closure.
18. `M11-ST-B18`: execution-lane implementation hole.
19. `M11-ST-B19`: managed-service quota/capacity/access boundary unresolved.

## 10) Artifact Contract
Required stage outputs (phase-level):
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
11. `m11_eval_vs_baseline_report.json`
12. `m11_reproducibility_check.json`
13. `m11_model_operability_report.json`
14. `m11_non_gate_acceptance_snapshot.json`
15. `m11_phase_budget_envelope.json`
16. `m11_phase_cost_outcome_receipt.json`
17. `m11j_blocker_register.json`
18. `m11j_execution_summary.json`
19. `m11_runtime_locality_guard_snapshot.json`
20. `m11_source_authority_guard_snapshot.json`
21. `m11_realism_guard_snapshot.json`
22. `m11_blocker_register.json`
23. `m11_execution_summary.json`
24. `m11_decision_log.json`
25. `m11_gate_verdict.json`

## 11) DoD (Planning to Execution-Ready)
- [x] dedicated M11 stress authority created.
- [x] capability-lane coverage explicit (`A..J` + infra lanes).
- [x] anti-hole preflight gates pinned.
- [x] M10 carry-forward guards pinned (locality/source authority/realism/black-box).
- [x] non-gate acceptance contract pinned as mandatory closure input.
- [x] missing execution-lane implementations and parent runner pinned as explicit `PREVENT` findings.
- [x] `M11-ST-S0` executed and closed green.
- [x] `M11-ST-S1` executed and closed green.
- [ ] `M11-ST-S2` executed and closed green.
- [ ] `M11-ST-S3` executed and closed green.
- [ ] `M11-ST-S4` executed and closed green.
- [ ] `M11-ST-S5` executed and closed green with deterministic `M12_READY` and non-gate acceptance pass.

## 12) Immediate Next Actions
1. implement `M11-ST-S2` lanes and parent dispatch:
   - `scripts/dev_substrate/m11e_eval_gate.py`,
   - `scripts/dev_substrate/m11f_mlflow_lineage.py`,
   - extend `scripts/dev_substrate/m11_stress_runner.py` for `S2`.
2. execute `M11-ST-S2` from strict upstream `m11_stress_s1_20260305T023231Z`.
3. fail closed on first blocker and remediate in-lane until `next_gate=M11_ST_S3_READY` with `open_blocker_count=0`.

## 13) Execution Progress
1. M11 detailed stress authority is pinned and active.
2. Strict M10 closure authority for M11 entry is pinned to `m10_stress_s5_20260305T014017Z`.
3. `M11-ST-S0` implementation closure:
   - added `scripts/dev_substrate/m11a_handle_closure.py`,
   - added `scripts/dev_substrate/m11b_sagemaker_readiness.py`,
   - added `scripts/dev_substrate/m11_stress_runner.py` (`S0` fail-closed orchestration).
4. `M11-ST-S1` implementation closure:
   - added `scripts/dev_substrate/m11c_input_immutability.py`,
   - added `scripts/dev_substrate/m11d_train_eval_execution.py`,
   - extended `scripts/dev_substrate/m11_stress_runner.py` for `S1`.
5. S0 readiness closure proof:
   - IAM role check pass (`fraud-platform-dev-full-sagemaker-execution`, trust includes `sagemaker.amazonaws.com`),
   - SSM parity pass for role ARN and MLflow tracking URI handles,
   - SageMaker control-plane probes pass (`list_training_jobs`, `list_model_package_groups`),
   - package group `fraud-platform-dev-full-models` readiness pass (`describe_ok`), no advisories.
6. `M11-ST-S1` fail-closed remediation chronology:
   - blocked run: `m11_stress_s1_20260305T022412Z` (`M11.C` immutable-input schema mismatch),
   - blocked run: `m11_stress_s1_20260305T022940Z` (single residual fingerprint canonicalization mismatch),
   - remediated green run: `m11_stress_s1_20260305T023231Z` (`overall_pass=true`, `open_blocker_count=0`, `next_gate=M11_ST_S2_READY`).
7. Final strict-chain upstream for next stage:
   - `M11-ST-S0`: `m11_stress_s0_20260305T023211Z` (`overall_pass=true`, `next_gate=M11_ST_S1_READY`),
   - `M11-ST-S1`: `m11_stress_s1_20260305T023231Z` (`overall_pass=true`, `next_gate=M11_ST_S2_READY`).
8. Current evidence root:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m11_stress_s1_20260305T023231Z/stress/`.

## 14) Reopen Notice (Strict Authority)
1. M11 cannot be closed using historical 2026-02-26/27 receipts alone.
2. only receipts generated from this M11 stress authority and current strict M10 handoff chain can close M11.
