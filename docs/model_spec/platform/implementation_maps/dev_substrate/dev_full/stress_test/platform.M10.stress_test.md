# Dev Substrate Stress Plan - M10 (P13 OFS_DATASET_COMMITTED)
_Parent authority: `platform.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-05_
_Current posture: `S1_GREEN` (strict S0/S1 chain is green; M10 routed to `S2`)._

## 0) Purpose
M10 stress validates OFS dataset closure under realistic production pressure with strict replay/as-of provenance continuity and deterministic handoff posture.

M10 stress must prove:
1. OFS build binds only to M9-validated replay/as-of inputs.
2. dataset manifest/fingerprint publication is immutable and provenance-complete.
3. Iceberg + Glue commit state is coherent and replay-safe.
4. rollback recipe evidence is executable and deterministic.
5. P13 rollup verdict and M11 handoff are deterministic and reproducible.
6. M10 closure publishes attributable cost-to-outcome evidence with no unexplained spend.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M10.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M9.stress_test.md`
2. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.impl_actual.md`

Strict entry authority (current):
1. Parent `M9-ST-S5`: `m9_stress_s5_20260305T003614Z` (`overall_pass=true`, `verdict=ADVANCE_TO_M10`, `next_gate=M10_READY`, `open_blocker_count=0`).
2. Parent lane `M9.J`: `m9j_stress_s5_20260305T003614Z` (`overall_pass=true`, `verdict=ADVANCE_TO_M10`, `next_gate=M10_READY`).

Legacy receipts (history only, not closure authority):
1. historical M10 managed closure receipts embedded in `platform.M10.build_plan.md` (2026-02-26).

## 2) Stage-A Findings (M10)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M10-ST-F1` | `ACCEPT` | strict M9 closure authority is green and deterministic for M10 entry. | use `m9_stress_s5_20260305T003614Z` as sole entry authority. |
| `M10-ST-F2` | `ACCEPT` | dedicated M10 stress authority is now pinned in `stress_test/`. | maintain this file as sole M10 stress authority. |
| `M10-ST-F3` | `ACCEPT` | parent M10 stress orchestrator now exists (`m10_stress_runner.py`) with strict `S0/S1` fail-closed flow. | extend runner stage-by-stage (`S2..S5`) using the same fail-closed contract. |
| `M10-ST-F4` | `PREVENT` | execution-lane implementation remains partial (`m10a/m10b/m10c/m10d` present; `m10e..m10j` missing). | pin execution-lane implementation blockers and fail closed until lanes are implemented. |
| `M10-ST-F5` | `PREVENT` | without explicit anti-hole gates, M10 may close using stale/historical receipts. | enforce run-scope freshness and stale-evidence rejection at every stage. |
| `M10-ST-F6` | `PREVENT` | M10 can silently drift into local/runtime shortcuts for Databricks/OFS checks. | enforce remote-only runtime + source-authority guard snapshots on each stage. |
| `M10-ST-F7` | `OBSERVE` | Databricks readiness can bottleneck on job/policy drift under repeated runs. | include explicit Databricks contract checks in S0 and continuity checks in later stages. |
| `M10-ST-F8` | `OBSERVE` | Iceberg/Glue commit checks can pass while manifest parity drifts if contracts are weak. | require parity matrix + deterministic artifact contract on S2/S3/S5. |
| `M10-ST-F9` | `OBSERVE` | rollback recipe posture can appear green without drill semantics under closure pressure. | enforce explicit rollback drill verdict checks in S3. |
| `M10-ST-F10` | `ACCEPT` | M10 build authority already contains lane-level contracts and budgets. | reuse as stress target with explicit fail-closed mapping. |

## 3) Scope Boundary for M10 Stress
In scope:
1. P13 authority and handle closure with strict M9 continuity.
2. Databricks runtime/job readiness under managed posture.
3. M9 input binding and immutability proofs for OFS build.
4. OFS dataset build + quality gate stress.
5. Iceberg/Glue commit stress and parity validation.
6. manifest/fingerprint/time-bound audit publication stress.
7. rollback recipe closure with deterministic drill posture.
8. deterministic P13 rollup + M11 handoff.
9. M10 phase budget envelope + cost-outcome closure.

Out of scope:
1. M11 model train/eval execution itself.
2. M12 promotion/rollback corridor execution itself.
3. Data Engine internal implementation details (black-box boundary remains).
4. local filesystem-only evidence as closure authority.

## 4) M10 Stress Handle Packet (Pinned)
1. `M10_STRESS_PROFILE_ID = "ofs_dataset_strict_stress_v0"`.
2. `M10_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m10_blocker_register.json"`.
3. `M10_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m10_execution_summary.json"`.
4. `M10_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m10_decision_log.json"`.
5. `M10_STRESS_GATE_VERDICT_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m10_gate_verdict.json"`.
6. `M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY = true`.
7. `M10_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX = true`.
8. `M10_STRESS_DISALLOW_WAIVED_REALISM = true`.
9. `M10_STRESS_FAIL_ON_STALE_UPSTREAM = true`.
10. `M10_STRESS_EXPECTED_ENTRY_EXECUTION = "m9_stress_s5_20260305T003614Z"`.
11. `M10_STRESS_EXPECTED_ENTRY_GATE = "M10_READY"`.
12. `M10_STRESS_EXPECTED_NEXT_GATE_ON_PASS = "M11_READY"`.
13. `M10_STRESS_MAX_RUNTIME_MINUTES = 260`.
14. `M10_STRESS_MAX_SPEND_USD = 130`.

## 5) Fail-Closed Preflight Gates
`M10-ST-G0` decision completeness:
1. all required handles for active stage are resolved (no `TO_PIN`/placeholder/wildcard for required keys).

`M10-ST-G1` phase coverage:
1. active stage explicitly covers authority, runtime identity, storage/catalog, evidence parity, rollback/rerun, budget/cost, and teardown posture.

`M10-ST-G2` stale-evidence guard:
1. only current strict chain receipts are accepted for closure (`M9 -> M10` current run scope).

`M10-ST-G3` locality/source-authority guard:
1. closure uses durable managed evidence refs only; no local-only authority.

`M10-ST-G4` Data Engine black-box guard:
1. no implementation-introspection dependency for closure proof.

`M10-ST-G5` realism guard:
1. no toy/waived realism posture for closure lanes.

`M10-ST-G6` implementation-readiness guard:
1. active stage cannot execute unless all required lane scripts and parent runner paths exist.

## 6) Capability-Lane Coverage Matrix (M10)
| Capability lane | Stress stage owner | Minimum pass evidence |
| --- | --- | --- |
| authority/handles | `S0` | `m10a_handle_closure_snapshot.json` pass posture |
| Databricks readiness | `S0` | `m10b_databricks_readiness_snapshot.json` pass posture |
| input binding/immutability | `S1` | `m10c_input_binding_snapshot.json` pass posture |
| OFS build execution | `S1` | `m10d_ofs_build_execution_snapshot.json` pass posture |
| quality gate adjudication | `S2` | `m10e_quality_gate_snapshot.json` pass posture |
| Iceberg/Glue commit closure | `S2` | `m10f_iceberg_commit_snapshot.json` pass posture |
| manifest/fingerprint/time-bound audit | `S3` | `m10g_manifest_fingerprint_snapshot.json` pass posture |
| rollback recipe closure | `S3` | `m10h_rollback_recipe_snapshot.json` pass posture |
| P13 rollup + M11 handoff | `S4` | `m10i_p13_gate_verdict.json` (`ADVANCE_TO_P14`, `M11_READY`) + `m11_handoff_pack.json` |
| cost-outcome + closure sync | `S5` | `m10_phase_budget_envelope.json`, `m10_phase_cost_outcome_receipt.json`, final `m10_execution_summary.json` (`ADVANCE_TO_M11`, `M11_READY`) |

## 7) Execution Topology (Parent `S0..S5`)
1. `S0`: authority + Databricks readiness (`A`,`B`).
2. `S1`: input binding + OFS build execution (`C`,`D`).
3. `S2`: quality + Iceberg/Glue commit (`E`,`F`).
4. `S3`: manifest/fingerprint/audit + rollback (`G`,`H`).
5. `S4`: P13 rollup + M11 handoff (`I`).
6. `S5`: cost-outcome + final closure sync (`J`).

## 8) Stage Plans
### 8.1 `M10-ST-S0` - Authority + Databricks readiness (`A`,`B`)
Objective:
1. validate M10 authority/handle closure and Databricks runtime readiness from strict M9 entry.

Entry criteria:
1. strict M9 entry receipt `m9_stress_s5_20260305T003614Z` is readable and pass.
2. lane scripts for `A,B` exist and are executable.

Execution steps:
1. run lane `A` handle-closure checks.
2. run lane `B` Databricks readiness checks.
3. emit parent guard snapshots and stage receipts.

Fail-closed blockers:
1. `M10-ST-B1`: authority/handle closure failure.
2. `M10-ST-B2`: Databricks readiness failure.
3. `M10-ST-B12`: artifact parity failure.
4. `M10-ST-B16`: locality/source-authority/Data-Engine-boundary failure.
5. `M10-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `35` minutes.
2. max spend: `$12`.

Pass gate:
1. `next_gate=M10_ST_S1_READY`.

### 8.2 `M10-ST-S1` - Input binding + OFS build execution (`C`,`D`)
Objective:
1. prove M9-bound input immutability and execute OFS build with deterministic run scope.

Entry criteria:
1. successful `S0` with `next_gate=M10_ST_S1_READY`.
2. lane scripts for `C,D` exist and are executable.

Execution steps:
1. run lane `C` input-binding immutability checks.
2. run lane `D` OFS build execution checks.
3. emit parent stage receipts and guards.

Fail-closed blockers:
1. `M10-ST-B3`: input binding/immutability failure.
2. `M10-ST-B4`: OFS build execution failure.
3. `M10-ST-B12`: artifact parity failure.
4. `M10-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `55` minutes.
2. max spend: `$20`.

Pass gate:
1. `next_gate=M10_ST_S2_READY`.

### 8.3 `M10-ST-S2` - Quality + Iceberg/Glue commit (`E`,`F`)
Objective:
1. adjudicate quality gates and verify Iceberg/Glue commit coherence under stress.

Entry criteria:
1. successful `S1` with `next_gate=M10_ST_S2_READY`.
2. lane scripts for `E,F` exist and are executable.

Execution steps:
1. run lane `E` quality-gate checks.
2. run lane `F` Iceberg/Glue commit verification.
3. emit parent stage receipts and guards.

Fail-closed blockers:
1. `M10-ST-B5`: quality gate failure.
2. `M10-ST-B6`: Iceberg/Glue commit failure.
3. `M10-ST-B12`: artifact parity failure.
4. `M10-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `60` minutes.
2. max spend: `$24`.

Pass gate:
1. `next_gate=M10_ST_S3_READY`.

### 8.4 `M10-ST-S3` - Manifest/audit + rollback (`G`,`H`)
Objective:
1. verify manifest/fingerprint/audit evidence and rollback recipe deterministic drill posture.

Entry criteria:
1. successful `S2` with `next_gate=M10_ST_S3_READY`.
2. lane scripts for `G,H` exist and are executable.

Execution steps:
1. run lane `G` manifest/fingerprint/time-bound audit checks.
2. run lane `H` rollback recipe/drill checks.
3. emit parent stage receipts and guards.

Fail-closed blockers:
1. `M10-ST-B7`: manifest/fingerprint/audit failure.
2. `M10-ST-B8`: rollback recipe failure.
3. `M10-ST-B12`: artifact parity failure.
4. `M10-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `45` minutes.
2. max spend: `$18`.

Pass gate:
1. `next_gate=M10_ST_S4_READY`.

### 8.5 `M10-ST-S4` - P13 rollup + M11 handoff (`I`)
Objective:
1. compute deterministic P13 verdict and publish M11 handoff pack.

Entry criteria:
1. successful `S3` with `next_gate=M10_ST_S4_READY`.
2. lane script for `I` exists and is executable.

Execution steps:
1. aggregate lane readiness in fixed order.
2. emit deterministic rollup/verdict (`ADVANCE_TO_P14`, `M11_READY`).
3. emit `m11_handoff_pack.json`.

Fail-closed blockers:
1. `M10-ST-B9`: P13 rollup/verdict inconsistency.
2. `M10-ST-B10`: M11 handoff publication/contract failure.
3. `M10-ST-B12`: artifact parity failure.
4. `M10-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$10`.

Pass gate:
1. `next_gate=M10_ST_S5_READY`.

### 8.6 `M10-ST-S5` - Cost-outcome + final closure (`J`)
Objective:
1. finalize M10 with deterministic summary and closure recommendation.

Entry criteria:
1. successful `S4` with `next_gate=M10_ST_S5_READY`.
2. lane script for `J` exists and is executable.

Execution steps:
1. validate parity/readability across `A..I` artifacts.
2. compute phase budget envelope and cost-outcome receipt.
3. emit final parent receipts and gate verdict.

Fail-closed blockers:
1. `M10-ST-B11`: cost-outcome closure failure.
2. `M10-ST-B12`: summary/evidence publication parity failure.
3. `M10-ST-B16`: locality/source-authority/Data-Engine-boundary violation.
4. `M10-ST-B17`: non-realistic closure posture.
5. `M10-ST-B18`: execution-lane implementation hole.

Runtime/cost budget:
1. max runtime: `35` minutes.
2. max spend: `$16`.

Pass gate:
1. `overall_pass=true`.
2. `verdict=ADVANCE_TO_M11`.
3. `next_gate=M11_READY`.
4. `open_blocker_count=0`.

## 9) Blocker Taxonomy (M10 Parent)
1. `M10-ST-B1`: authority/handle closure failure.
2. `M10-ST-B2`: Databricks readiness failure.
3. `M10-ST-B3`: input binding/immutability failure.
4. `M10-ST-B4`: OFS build execution failure.
5. `M10-ST-B5`: quality gate failure.
6. `M10-ST-B6`: Iceberg/Glue commit failure.
7. `M10-ST-B7`: manifest/fingerprint/time-bound audit failure.
8. `M10-ST-B8`: rollback recipe failure.
9. `M10-ST-B9`: P13 rollup/verdict inconsistency.
10. `M10-ST-B10`: M11 handoff publication failure.
11. `M10-ST-B11`: phase cost-outcome closure failure.
12. `M10-ST-B12`: summary/evidence publication parity failure.
13. `M10-ST-B13`: unresolved decision/input hole.
14. `M10-ST-B14`: phase-coverage lane hole.
15. `M10-ST-B15`: stale-evidence authority selection.
16. `M10-ST-B16`: runtime locality/source-authority/Data-Engine-boundary violation.
17. `M10-ST-B17`: non-realistic data posture used for closure.
18. `M10-ST-B18`: execution-lane implementation hole.

## 10) Artifact Contract
Required stage outputs (phase-level):
1. `m10a_handle_closure_snapshot.json`
2. `m10b_databricks_readiness_snapshot.json`
3. `m10c_input_binding_snapshot.json`
4. `m10d_ofs_build_execution_snapshot.json`
5. `m10e_quality_gate_snapshot.json`
6. `m10f_iceberg_commit_snapshot.json`
7. `m10g_manifest_fingerprint_snapshot.json`
8. `m10h_rollback_recipe_snapshot.json`
9. `m10i_p13_rollup_matrix.json`
10. `m10i_p13_gate_verdict.json`
11. `m11_handoff_pack.json`
12. `m10_phase_budget_envelope.json`
13. `m10_phase_cost_outcome_receipt.json`
14. `m10j_blocker_register.json`
15. `m10j_execution_summary.json`
16. `m10_runtime_locality_guard_snapshot.json`
17. `m10_source_authority_guard_snapshot.json`
18. `m10_realism_guard_snapshot.json`
19. `m10_blocker_register.json`
20. `m10_execution_summary.json`
21. `m10_decision_log.json`
22. `m10_gate_verdict.json`

## 11) DoD (Planning to Execution-Ready)
- [x] dedicated M10 stress authority created.
- [x] capability-lane coverage explicit (`A..J` + infra lanes).
- [x] anti-hole preflight gates pinned.
- [x] M9 carry-forward guards pinned (locality/source authority/realism/black-box).
- [x] missing execution-lane implementations and parent runner pinned as explicit `PREVENT` findings.
- [x] `M10-ST-S0` executed and closed green.
- [x] `M10-ST-S1` executed and closed green.
- [ ] `M10-ST-S2` executed and closed green.
- [ ] `M10-ST-S3` executed and closed green.
- [ ] `M10-ST-S4` executed and closed green.
- [ ] `M10-ST-S5` executed and closed green with deterministic `M11_READY`.

## 12) Immediate Next Actions
1. plan and execute `M10-ST-S2` (`E+F`) with fail-closed mapping (`M10-ST-B5/B6/B12/B18`) and strict `S1` continuity.
2. implement/validate missing lane executors `M10.E` and `M10.F` before `S2` run.
3. maintain fail-closed posture with targeted remediation only.

## 13) Execution Progress
1. M10 detailed stress authority is pinned and active.
2. Strict M9 closure authority for M10 entry is pinned to `m9_stress_s5_20260305T003614Z`.
3. Stage-A implementation-readiness finding remains explicit:
   - lane scripts present: `m10a`, `m10b`, `m10c`, `m10d`,
   - lane scripts missing: `m10e..m10j`,
   - parent runner present: `m10_stress_runner.py` (`S0` + `S1` implemented).
4. First `M10-ST-S0` attempt failed closed (`m10_stress_s0_20260305T005201Z`):
   - `open_blocker_count=2`, `next_gate=HOLD_REMEDIATE`,
   - blocker root cause: `M10.A` could not read `M9` closure summary at the expected S3 authority key (`NoSuchKey`), cascading into `M10.B` non-pass posture.
5. Remediation applied:
   - updated parent runner to publish a strict bridge copy of upstream `m9_execution_summary.json` to:
     - `evidence/dev_full/run_control/m9_stress_s5_20260305T003614Z/m9_execution_summary.json`
     before executing `M10.A`.
6. `M10-ST-S0` rerun passed (`m10_stress_s0_20260305T005311Z`):
   - `overall_pass=true`, `open_blocker_count=0`, `verdict=GO`, `next_gate=M10_ST_S1_READY`.
7. Lane execution IDs in green S0:
   - `m10a_execution_id=m10a_stress_s0_20260305T005312Z` (`overall_pass=true`, `next_gate=M10.B_READY`),
   - `m10b_execution_id=m10b_stress_s0_20260305T005322Z` (`overall_pass=true`, `next_gate=M10.C_READY`).
8. `M10-ST-S1` first execution failed closed (`m10_stress_s1_20260305T010157Z`):
   - `open_blocker_count=1`, `next_gate=HOLD_REMEDIATE`,
   - `M10.C` passed; `M10.D` failed with Databricks terminal error:
     - `INVALID_PARAMETER_VALUE: Workspace doesn't support Client-1 channel for REPL`.
9. Remediation applied:
   - implemented `scripts/dev_substrate/m10d_ofs_build_execution.py` (lane `M10.D`),
   - repinned serverless upsert contract in `m10b_upsert_databricks_jobs.py` from `client=1` to `client=2`,
   - re-upserted jobs via fresh S0 run `m10_stress_s0_20260305T010426Z` (green).
10. `M10-ST-S1` rerun passed (`m10_stress_s1_20260305T010445Z`):
    - `overall_pass=true`, `open_blocker_count=0`, `verdict=GO`, `next_gate=M10_ST_S2_READY`.
11. Lane execution IDs in green S1:
    - `m10c_execution_id=m10c_stress_s1_20260305T010445Z` (`overall_pass=true`, `next_gate=M10.D_READY`),
    - `m10d_execution_id=m10d_stress_s1_20260305T010447Z` (`overall_pass=true`, `next_gate=M10.E_READY`).
12. Databricks OFS build closure proof in green S1:
    - run id `14362870372775`, terminal `TERMINATED/SUCCESS`,
    - repo source provenance pinned (`platform/databricks/dev_full/ofs_build_v0.py`, `sha256=71edd09a78f973800f3c290a02b93232c14efafe0de93041255693939ee432ca`).
13. Current evidence roots:
    - S0 refresh: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m10_stress_s0_20260305T010426Z/stress/`,
    - S1 green: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m10_stress_s1_20260305T010445Z/stress/`.

## 14) Reopen Notice (Strict Authority)
1. M10 cannot be closed using historical 2026-02-26 receipts alone.
2. only receipts generated from this M10 stress authority and current strict M9 handoff chain can close M10.
