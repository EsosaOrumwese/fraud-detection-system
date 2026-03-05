# Dev Substrate Stress Plan - M13 (P16-P17 FINAL_VERDICT_AND_IDLE_SAFE_CLOSE)
_Parent authority: `platform.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-05_
_Current posture: `S4_GREEN` (strict `M13-ST-S4` passed from `m13_stress_s3_20260305T104425Z`; `S5` pending execution)._

## 0) Purpose
M13 stress validates full-platform closure and deterministic teardown/idle-safe posture under strict production-realism and fail-closed gates.

M13 stress must prove:
1. P16 entry binds only to immutable, current M12 closure authority.
2. full source matrix closure (`M1..M12`) is deterministic and blocker-free.
3. six-proof matrix closure is complete for required lanes (`spine`, `ofs`, `mf`, `mpr`, `teardown`).
4. final verdict publication is deterministic, run-scoped, and readback-verified.
5. teardown plan + teardown execution are deterministic and safe.
6. residual-risk and post-teardown evidence readability close fail-closed.
7. post-teardown cost guardrail and M13 phase cost-outcome closure are attributable and blocker-free.
8. final closure sync emits deterministic `ADVANCE_TO_M14` + `M14_READY` with zero unresolved blockers.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M13.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M12.stress_test.md`
2. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
3. `.github/workflows/dev_full_m13_managed.yml` (materialization required; fail-closed if absent/non-dispatchable)
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.impl_actual.md`

Strict entry authority (current):
1. Parent `M12-ST-S5`: `m12_stress_s5_20260305T091936Z` (`overall_pass=true`, `verdict=ADVANCE_TO_M13`, `next_gate=M13_READY`, `open_blocker_count=0`).
2. Parent lane `M12.J`: `m12j_stress_s5_20260305T091936Z` (`overall_pass=true`, `verdict=ADVANCE_TO_M13`, `next_gate=M13_READY`).
3. M12 handoff lane `M12.H`: `m12h_stress_s4_20260305T090625Z` (`m13_handoff_pack.json` readable, `p15_verdict=ADVANCE_TO_P16`, `next_gate=M13_READY`, `m13_entry_ready=true`).

Legacy receipts (history only, not closure authority):
1. historical M13 managed receipts in `platform.M13.build_plan.md` (2026-02-27).

## 2) Stage-A Findings (M13)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M13-ST-F1` | `ACCEPT` | strict M12 closure authority is green and deterministic for M13 entry. | use `m12_stress_s5_20260305T091936Z` as sole entry authority. |
| `M13-ST-F2` | `PREVENT` | dedicated M13 stress parent runner/wrappers are not materialized on this branch. | implement `m13_stress_runner.py` and `m13{a..j}_*.py` wrappers before execution. |
| `M13-ST-F3` | `PREVENT` | managed M13 workflow dispatchability is not yet validated in current strict chain. | execute `S0` managed-lane materialization checks fail-closed. |
| `M13-ST-F4` | `PREVENT` | workflow defaults can point to stale historical upstream execution ids. | enforce explicit upstream overrides from current strict chain. |
| `M13-ST-F5` | `PREVENT` | historical M13 receipts can be mistaken as current closure authority. | enforce stale-evidence rejection and run-scope continuity checks at every stage. |
| `M13-ST-F6` | `OBSERVE` | final verdict publication can pass functionally yet drift in scope rows. | enforce deterministic source-matrix row coverage and readback parity in `S2/S5`. |
| `M13-ST-F7` | `OBSERVE` | teardown can appear successful while leaving forbidden residual resources. | enforce residual-risk fail-closed checks in `S3`. |
| `M13-ST-F8` | `OBSERVE` | post-teardown readability may degrade despite pass status fields. | require explicit readability matrix with durable refs in `S3/S5`. |
| `M13-ST-F9` | `OBSERVE` | cost posture can drift if post-teardown attribution is partial. | fail-closed on missing cost envelope/receipt fields in `S4/S5`. |
| `M13-ST-F10` | `ACCEPT` | Data Engine remains black-box for platform closure proofs. | prohibit implementation-introspection dependencies in M13 closure proofs. |
| `M13-ST-F11` | `PREVENT` | non-gate acceptance can be skipped if only stage gates are checked. | enforce non-gate acceptance closure in `S5`. |
| `M13-ST-F12` | `PREVENT` | unresolved teardown handles silently degrade closure confidence. | enforce unresolved-handle rejection in `S0` and carry forward as hard gate. |

## 3) Scope Boundary for M13 Stress
In scope:
1. P16 authority/handle closure and final verdict closure chain.
2. full source matrix and six-proof matrix closure.
3. teardown plan, teardown execution, residual/readability closure.
4. post-teardown cost guardrail and M13 phase cost-outcome closure.
5. final M13 closure sync and deterministic `M14_READY` recommendation.

Out of scope:
1. M14 runtime-placement repin execution itself.
2. reopening M1..M12 unless M13 fail-closed blockers require direct remediation.
3. Data Engine internal implementation details (black-box boundary remains).
4. local-only artifacts as closure authority.

## 4) M13 Stress Handle Packet (Pinned)
1. `M13_STRESS_PROFILE_ID = "final_closure_idle_safe_strict_stress_v0"`.
2. `M13_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m13_blocker_register.json"`.
3. `M13_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m13_execution_summary.json"`.
4. `M13_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m13_decision_log.json"`.
5. `M13_STRESS_GATE_VERDICT_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m13_gate_verdict.json"`.
6. `M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY = true`.
7. `M13_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX = true`.
8. `M13_STRESS_DISALLOW_WAIVED_REALISM = true`.
9. `M13_STRESS_FAIL_ON_STALE_UPSTREAM = true`.
10. `M13_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS = true`.
11. `M13_STRESS_REQUIRE_MANAGED_LANE_MATERIALIZATION = true`.
12. `M13_STRESS_EXPECTED_ENTRY_EXECUTION = "m12_stress_s5_20260305T091936Z"`.
13. `M13_STRESS_EXPECTED_ENTRY_GATE = "M13_READY"`.
14. `M13_STRESS_EXPECTED_NEXT_GATE_ON_PASS = "M14_READY"`.
15. `M13_STRESS_MAX_RUNTIME_MINUTES = 260`.
16. `M13_STRESS_MAX_SPEND_USD = 90`.
17. `M13_STRESS_REQUIRE_NON_GATE_ACCEPTANCE = true`.
18. `M13_STRESS_REQUIRE_COST_OUTCOME_CLOSURE = true`.
19. `M13_STRESS_REQUIRE_TEARDOWN_IDLE_SAFE = true`.

## 5) Fail-Closed Preflight Gates
`M13-ST-G0` decision completeness:
1. all required handles/inputs for active stage are resolved (no `TO_PIN`/placeholder/wildcard for required keys).

`M13-ST-G1` phase coverage:
1. active stage explicitly covers authority, identity, transport, evidence parity, teardown safety, budget/cost, and rerun posture.

`M13-ST-G2` stale-evidence guard:
1. only current strict chain receipts are accepted for closure (`M12 -> M13` current run scope).

`M13-ST-G3` locality/source-authority guard:
1. closure uses durable managed evidence refs only; no local-only authority.

`M13-ST-G4` Data Engine black-box guard:
1. no implementation-introspection dependency for closure proof.

`M13-ST-G5` realism guard:
1. no toy/advisory-only teardown or verdict posture for closure lanes.

`M13-ST-G6` implementation-readiness guard:
1. active stage cannot execute unless required parent runner/wrappers and managed lane paths exist.

`M13-ST-G7` non-gate acceptance guard:
1. residual-risk/readability/cost evidence is mandatory before M13 closure.

`M13-ST-G8` upstream-override guard:
1. workflow dispatch must use explicit current upstream execution ids; historical defaults are rejected.

`M13-ST-G9` teardown safety guard:
1. teardown cannot pass while forbidden residual resources remain or required retained surfaces lose readability.

## 6) Capability-Lane Coverage Matrix (M13)
| Capability lane | Stress stage owner | Minimum pass evidence |
| --- | --- | --- |
| managed lane materialization | `S0` | `m13_managed_lane_materialization_snapshot.json` + `m13b0_execution_summary.json` pass posture |
| authority/handle closure | `S0` | `m13a_handle_closure_snapshot.json` pass posture |
| full source matrix closure | `S1` | `m13b_source_matrix_snapshot.json` pass posture |
| six-proof matrix closure | `S1` | `m13c_six_proof_matrix_snapshot.json` pass posture |
| final verdict publication | `S2` | `m13d_final_verdict_bundle.json` + run-scoped full verdict readback pass |
| teardown plan closure | `S2` | `m13e_teardown_plan_snapshot.json` pass posture |
| teardown execution closure | `S3` | `m13f_teardown_execution_snapshot.json` pass posture |
| residual/readability closure | `S3` | `m13g_post_teardown_readability_snapshot.json` + residual scan pass posture |
| post-teardown cost guardrail | `S4` | `m13h_cost_guardrail_snapshot.json` pass posture |
| phase budget + cost-outcome closure | `S4` | `m13_phase_budget_envelope.json` + `m13_phase_cost_outcome_receipt.json` pass posture |
| final closure sync | `S5` | `m13_execution_summary.json` (`ADVANCE_TO_M14`, `M14_READY`) + `m13_blocker_register.json` |

## 7) Execution Topology (Parent `S0..S5`)
1. `S0`: managed lane materialization + authority/handle closure (`B0`,`A`).
2. `S1`: source matrix + six-proof matrix closure (`B`,`C`).
3. `S2`: final verdict publication + teardown plan (`D`,`E`).
4. `S3`: teardown execution + residual/readability closure (`F`,`G`).
5. `S4`: cost guardrail + phase cost-outcome closure (`H`,`I`).
6. `S5`: final M13 closure sync (`J`).

## 8) Stage Plans
### 8.1 `M13-ST-S0` - Materialization + authority/handle closure (`B0`,`A`)
Objective:
1. validate managed lane dispatchability and close required P16/P17 handles from strict M12 entry.

Entry criteria:
1. strict M12 entry receipt `m12_stress_s5_20260305T091936Z` is readable and pass.
2. parent runner and wrappers for `B0/A` exist and are executable.

Fail-closed blockers:
1. `M13-ST-B0`: managed-lane materialization failure.
2. `M13-ST-B1`: authority/handle closure failure.
3. `M13-ST-B11`: summary/evidence parity failure.
4. `M13-ST-B16`: locality/source-authority/Data-Engine-boundary violation.
5. `M13-ST-B18`: execution-lane implementation hole.
6. `M13-ST-B20`: default-upstream override violation.

Pass gate:
1. `next_gate=M13_ST_S1_READY`.

### 8.2 `M13-ST-S1` - Source matrix + six-proof closure (`B`,`C`)
Objective:
1. prove closure completeness across source matrix and six-proof matrix under strict readability and run-scope continuity.

Entry criteria:
1. successful `S0` with `next_gate=M13_ST_S1_READY`.
2. wrappers for `B/C` exist and are executable.

Fail-closed blockers:
1. `M13-ST-B2`: source matrix closure failure.
2. `M13-ST-B3`: six-proof matrix closure failure.
3. `M13-ST-B11`: summary/evidence parity failure.
4. `M13-ST-B15`: stale evidence or run-scope drift.
5. `M13-ST-B18`: execution-lane implementation hole.

Pass gate:
1. `next_gate=M13_ST_S2_READY`.

### 8.3 `M13-ST-S2` - Final verdict + teardown plan (`D`,`E`)
Objective:
1. publish deterministic full-platform verdict and close deterministic teardown plan posture.

Entry criteria:
1. successful `S1` with `next_gate=M13_ST_S2_READY`.
2. wrappers for `D/E` exist and are executable.

Fail-closed blockers:
1. `M13-ST-B4`: final verdict inconsistency/publication failure.
2. `M13-ST-B5`: teardown plan closure failure.
3. `M13-ST-B11`: summary/evidence parity failure.
4. `M13-ST-B12`: non-gate acceptance precondition failure.
5. `M13-ST-B18`: execution-lane implementation hole.

Pass gate:
1. `next_gate=M13_ST_S3_READY`.

### 8.4 `M13-ST-S3` - Teardown execution + residual/readability (`F`,`G`)
Objective:
1. prove teardown executes to idle-safe posture while retained surfaces remain readable and residual policy is enforced.

Entry criteria:
1. successful `S2` with `next_gate=M13_ST_S3_READY`.
2. wrappers for `F/G` exist and are executable.

Fail-closed blockers:
1. `M13-ST-B6`: teardown execution failure.
2. `M13-ST-B7`: residual risk or forbidden post-state.
3. `M13-ST-B8`: post-teardown readability failure.
4. `M13-ST-B11`: summary/evidence parity failure.
5. `M13-ST-B18`: execution-lane implementation hole.

Pass gate:
1. `next_gate=M13_ST_S4_READY`.

### 8.5 `M13-ST-S4` - Cost guardrail + phase cost-outcome (`H`,`I`)
Objective:
1. prove post-teardown cost posture and close M13 phase budget/cost-outcome contract deterministically.

Entry criteria:
1. successful `S3` with `next_gate=M13_ST_S4_READY`.
2. wrappers for `H/I` exist and are executable.

Fail-closed blockers:
1. `M13-ST-B9`: post-teardown cost guardrail failure.
2. `M13-ST-B10`: phase cost-outcome closure failure.
3. `M13-ST-B11`: summary/evidence parity failure.
4. `M13-ST-B18`: execution-lane implementation hole.
5. `M13-ST-B19`: managed-service quota/capacity/access boundary unresolved.

Pass gate:
1. `next_gate=M13_ST_S5_READY`.

### 8.6 `M13-ST-S5` - Final closure sync (`J`)
Objective:
1. finalize M13 with deterministic summary, parity closure, non-gate acceptance closure, and progression to M14.

Entry criteria:
1. successful `S4` with `next_gate=M13_ST_S5_READY`.
2. wrapper for `J` exists and is executable.

Fail-closed blockers:
1. `M13-ST-B11`: summary/evidence publication parity failure.
2. `M13-ST-B12`: non-gate acceptance failure.
3. `M13-ST-B16`: locality/source-authority/Data-Engine-boundary violation.
4. `M13-ST-B17`: non-realistic closure posture.
5. `M13-ST-B18`: execution-lane implementation hole.

Pass gate:
1. `overall_pass=true`.
2. `verdict=ADVANCE_TO_M14`.
3. `next_gate=M14_READY`.
4. `open_blocker_count=0`.

## 9) Blocker Taxonomy (M13 Parent)
1. `M13-ST-B0`: managed M13 execution lane not materialized.
2. `M13-ST-B1`: authority/handle closure failure.
3. `M13-ST-B2`: full source matrix failure.
4. `M13-ST-B3`: six-proof matrix incompleteness.
5. `M13-ST-B4`: final verdict inconsistency/publication failure.
6. `M13-ST-B5`: teardown plan failure.
7. `M13-ST-B6`: teardown execution failure.
8. `M13-ST-B7`: residual-risk policy violation.
9. `M13-ST-B8`: post-teardown readability failure.
10. `M13-ST-B9`: post-teardown cost guardrail failure.
11. `M13-ST-B10`: phase cost-outcome closure failure.
12. `M13-ST-B11`: summary/evidence publication parity failure.
13. `M13-ST-B12`: non-gate acceptance failure.
14. `M13-ST-B13`: unresolved decision/input hole.
15. `M13-ST-B14`: phase-coverage lane hole.
16. `M13-ST-B15`: stale-evidence or run-scope continuity failure.
17. `M13-ST-B16`: runtime locality/source-authority/Data-Engine-boundary violation.
18. `M13-ST-B17`: non-realistic closure posture used for phase closure.
19. `M13-ST-B18`: execution-lane implementation hole.
20. `M13-ST-B19`: managed-service quota/capacity/access boundary unresolved.
21. `M13-ST-B20`: workflow-default upstream override violation.

## 10) Artifact Contract (Parent Stage Outputs)
Required stage outputs (phase-level):
1. `m13_stagea_findings.json`
2. `m13_lane_matrix.json`
3. `m13_runtime_locality_guard_snapshot.json`
4. `m13_source_authority_guard_snapshot.json`
5. `m13_realism_guard_snapshot.json`
6. `m13_non_gate_acceptance_snapshot.json`
7. `m13_managed_lane_materialization_snapshot.json`
8. `m13_subphase_dispatchability_snapshot.json`
9. `m13a_handle_closure_snapshot.json`
10. `m13b_source_matrix_snapshot.json`
11. `m13c_six_proof_matrix_snapshot.json`
12. `m13d_final_verdict_bundle.json`
13. `m13e_teardown_plan_snapshot.json`
14. `m13f_teardown_execution_snapshot.json`
15. `m13g_post_teardown_readability_snapshot.json`
16. `m13h_cost_guardrail_snapshot.json`
17. `m13_phase_budget_envelope.json`
18. `m13_phase_cost_outcome_receipt.json`
19. `m13_blocker_register.json`
20. `m13_execution_summary.json`
21. `m13_decision_log.json`
22. `m13_gate_verdict.json`

## 11) DoD (Planning to Execution-Ready)
- [x] dedicated M13 stress authority created.
- [x] capability-lane coverage explicit (`B0`,`A..J` + infra lanes).
- [x] anti-hole preflight gates pinned.
- [x] M12 carry-forward guards pinned (locality/source authority/realism/black-box).
- [x] non-gate acceptance contract pinned as mandatory closure input.
- [x] stale-default upstream override guard pinned.
- [x] missing execution-lane implementations and parent runner pinned as explicit `PREVENT` findings.
- [x] `M13-ST-S0` executed and closed green.
- [x] `M13-ST-S1` executed and closed green.
- [x] `M13-ST-S2` executed and closed green.
- [x] `M13-ST-S3` executed and closed green.
- [x] `M13-ST-S4` executed and closed green.
- [ ] `M13-ST-S5` executed and closed green with deterministic `M14_READY`.

## 12) Immediate Next Actions
1. proceed to `M13-ST-S5` from strict upstream `m13_stress_s4_20260305T110049Z`.
2. materialize parent `M13.J` wrapper and extend `m13_stress_runner.py` for `S5`.
3. execute strict `S5` fail-closed and stop on first blocker.
4. close M13 only if `S5` emits deterministic `ADVANCE_TO_M14` + `M14_READY` with zero unresolved blockers.
5. keep parent `platform.stress_test.md` synchronized after each run with latest execution id and gate.

## 13) Execution Progress
1. M13 detailed stress authority is pinned and active.
2. Strict M12 closure authority for M13 entry remains pinned to `m12_stress_s5_20260305T091936Z`.
3. `M13-ST-S0` passed in strict chain:
   - parent `phase_execution_id=m13_stress_s0_20260305T094531Z`,
   - `overall_pass=true`, `open_blocker_count=0`, `next_gate=M13_ST_S1_READY`, `verdict=GO`.
4. S0 lane receipts:
   - `M13.B0`: `execution_id=m13b0_stress_s0_20260305T094531Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_A`, `next_gate=M13.A_READY`,
   - `M13.A`: `execution_id=m13a_stress_s0_20260305T094836Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_B`, `next_gate=M13.B_READY`.
5. `M13-ST-S1` passed in strict chain:
   - parent `phase_execution_id=m13_stress_s1_20260305T095859Z`,
   - `overall_pass=true`, `open_blocker_count=0`, `next_gate=M13_ST_S2_READY`, `verdict=GO`.
6. S1 lane receipts:
   - `M13.B`: `execution_id=m13b_stress_s1_20260305T095859Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_C`, `next_gate=M13.C_READY`,
   - `M13.C`: `execution_id=m13c_stress_s1_20260305T100204Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_D`, `next_gate=M13.D_READY`.
7. Initial S2 attempt failed fail-closed:
   - parent `phase_execution_id=m13_stress_s2_20260305T102042Z`,
   - blockers: `M13-ST-B4` (`m13d_not_ready`), `M13-ST-B5` (`m13e_skipped_due_to_prior_blocker`), `M13-ST-B11` (S2 artifact incompleteness),
   - root cause: `M13.D` wrapper received placeholder upstream lineage (`M13_S2_NOT_APPLICABLE`) for dependencies requiring strict S1 lineage refs.
8. S2 remediation applied:
   - wired strict upstream lineage into `M13.D` dispatch (`m13a_execution_id`, `m13b_execution_id`) via `m13_stress_runner.py` `run_s2(...)`.
9. `M13-ST-S2` passed in strict chain after remediation:
   - parent `phase_execution_id=m13_stress_s2_20260305T102426Z`,
   - `overall_pass=true`, `open_blocker_count=0`, `next_gate=M13_ST_S3_READY`, `verdict=GO`.
10. S2 lane receipts:
   - `M13.D`: `execution_id=m13d_stress_s2_20260305T102426Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_E`, `next_gate=M13.E_READY`,
   - `M13.E`: `execution_id=m13e_stress_s2_20260305T102730Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_F`, `next_gate=M13.F_READY`.
11. `M13-ST-S3` passed in strict chain:
   - parent `phase_execution_id=m13_stress_s3_20260305T104425Z`,
   - `overall_pass=true`, `open_blocker_count=0`, `next_gate=M13_ST_S4_READY`, `verdict=GO`.
12. S3 lane receipts:
   - `M13.F`: `execution_id=m13f_stress_s3_20260305T104425Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_G`, `next_gate=M13.G_READY`,
   - `M13.G`: `execution_id=m13g_stress_s3_20260305T104729Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_H`, `next_gate=M13.H_READY`.
13. `M13-ST-S4` passed in strict chain:
   - parent `phase_execution_id=m13_stress_s4_20260305T110049Z`,
   - `overall_pass=true`, `open_blocker_count=0`, `next_gate=M13_ST_S5_READY`, `verdict=GO`.
14. S4 lane receipts:
   - `M13.H`: `execution_id=m13h_stress_s4_20260305T110049Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_I`, `next_gate=M13.I_READY`,
   - `M13.I`: `execution_id=m13i_stress_s4_20260305T110355Z`, `overall_pass=true`, `verdict=ADVANCE_TO_M13_J`, `next_gate=M13.J_READY`.
15. Next strict executable stage is `M13-ST-S5`.

## 14) Reopen Notice (Strict Authority)
1. M13 cannot be closed using historical 2026-02 receipts alone.
2. only receipts generated from this M13 stress authority and current strict M12 handoff chain can close M13.
