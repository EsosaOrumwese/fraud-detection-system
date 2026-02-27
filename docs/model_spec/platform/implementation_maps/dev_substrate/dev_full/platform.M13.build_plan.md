# Dev Substrate Deep Plan - M13 (P16-P17 FINAL_VERDICT_AND_IDLE_SAFE_CLOSE)
_Status source of truth: `platform.build_plan.md`_
_Track: `dev_full`_
_Last updated: 2026-02-27_

## 0) Purpose
M13 closes `P16 FULL_PLATFORM_CLOSED` and `P17 TEARDOWN_IDLE_SAFE`.

M13 is green only when all of the following are true:
1. Full source matrix over prior phases is complete and blocker-free.
2. Six-proof matrix is complete for each required lane (`spine`, `ofs`, `mf`, `mpr`, `teardown`).
3. Final verdict bundle is deterministic and published to run-scoped truth surface.
4. Non-essential runtime is scaled to zero or destroyed with residual-risk enforcement.
5. Post-teardown evidence remains readable.
6. M13 cost-outcome closure is committed and coherent.
7. Final phase closure artifacts (`m13_execution_summary.json`, `m13_blocker_register.json`) are parity-verified.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M12.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Entry Contract (Fail-Closed)
M13 cannot execute unless all are true:
1. `M12` is `DONE` in `platform.build_plan.md`.
2. `M12.J` summary is pass:
   - `overall_pass=true`
   - `blocker_count=0`
   - `verdict=ADVANCE_TO_M13`
   - `next_gate=M13_READY`
3. M12 closure artifacts are readable from durable run-control:
   - `m12_execution_summary.json`
   - `m12_blocker_register.json`
4. P15 handoff continuity from M12.H remains readable:
   - `m13_handoff_pack.json`
   - `m12h_p15_gate_verdict.json`

Entry evidence anchors:
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12j_closure_sync_20260227T184452Z/m12_execution_summary.json`
2. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12j_closure_sync_20260227T184452Z/m12_blocker_register.json`
3. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12h_p15_gate_rollup_20260227T181932Z/m13_handoff_pack.json`
4. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12h_p15_gate_rollup_20260227T181932Z/m12h_p15_gate_verdict.json`

## 3) Scope Boundary for M13
In scope:
1. P16 full-platform source-matrix and six-proof closure.
2. Final verdict publication.
3. P17 teardown/idle-safe closure with residual-risk enforcement.
4. Post-teardown evidence readability closure.
5. M13 phase budget + cost-outcome closure.
6. Final M13 summary/blocker-register parity closure.

Out of scope:
1. New functional capabilities beyond P17 closure.
2. Any reopening of closed M1..M12 lanes unless M13 fail-closed blocker requires remediation.

## 4) Global M13 Guardrails
1. No local authoritative compute or ad-hoc local teardown as truth source.
2. Managed-first execution path only.
3. Fail-closed on unresolved required handles.
4. Fail-closed on any unreadable required upstream artifact.
5. Teardown cannot pass while forbidden residual resources remain.
6. Cost closure is mandatory before M13 closeout.

## 4.1) Managed Execution Prerequisite
M13 execution requires an authoritative managed lane.

Prerequisite blocker:
1. `M13-B0` if managed M13 workflow lane is not materialized and dispatchable.

Closure expectation for this prerequisite:
1. single managed workflow lane supports `M13.A..M13.J`,
2. deterministic execution-id routing per subphase,
3. no local fallback marked authoritative.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary subphase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M13.A | no unresolved required P16/P17 handles |
| Full source matrix closure | M13.B | matrix snapshot pass over M1..M12 |
| Six-proof matrix closure | M13.C | six-proof matrix pass for required lanes |
| Final verdict publication | M13.D | run-scoped final verdict bundle readable |
| Teardown plan closure | M13.E | deterministic teardown plan snapshot pass |
| Teardown execution closure | M13.F | non-essential lanes scaled down/destroyed |
| Residual + readability closure | M13.G | residual scan + evidence readability pass |
| Cost guardrail post-teardown | M13.H | cost guardrail snapshot pass |
| M13 cost-outcome closure | M13.I | phase budget envelope + cost-outcome receipt pass |
| Final closure sync | M13.J | `m13_execution_summary.json` + `m13_blocker_register.json` parity pass |

## 5) Artifact Contract and Path Conventions
M13 artifacts must be emitted locally and durably.

Local run folder:
1. `runs/dev_substrate/dev_full/m13/<execution_id>/...`

Durable run-control mirror:
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/<execution_id>/...`

Run-scoped final verdict + teardown evidence:
1. `FULL_VERDICT_PATH_PATTERN = evidence/runs/{platform_run_id}/full_platform/final_verdict.json`
2. `TEARDOWN_COST_SNAPSHOT_PATH_PATTERN = evidence/runs/{platform_run_id}/teardown/cost_guardrail_snapshot.json`
3. `TEARDOWN_RESIDUAL_SCAN_PATH_PATTERN = evidence/runs/{platform_run_id}/teardown/residual_scan.json`

Expected M13 artifacts:
1. `m13a_handle_closure_snapshot.json`
2. `m13b_source_matrix_snapshot.json`
3. `m13c_six_proof_matrix_snapshot.json`
4. `m13d_final_verdict_bundle.json`
5. `m13e_teardown_plan_snapshot.json`
6. `m13f_teardown_execution_snapshot.json`
7. `m13g_post_teardown_readability_snapshot.json`
8. `m13h_cost_guardrail_snapshot.json`
9. `m13_phase_budget_envelope.json`
10. `m13_phase_cost_outcome_receipt.json`
11. `m13_execution_summary.json`
12. `m13_blocker_register.json`

## 6) Subphase Execution Contracts

### M13.A - Authority + Handle Closure
Goal:
1. Close required P16/P17 handles before final closure execution.

Entry conditions:
1. M13 entry contract (Section 2) is satisfied.
2. `M13-B0` closure summary is readable and pass posture:
   - `overall_pass=true`
   - `verdict=ADVANCE_TO_M13_A`
   - `next_gate=M13.A_READY`

Required handles:
1. `FULL_VERDICT_PATH_PATTERN`
2. `TEARDOWN_COST_SNAPSHOT_PATH_PATTERN`
3. `TEARDOWN_RESIDUAL_SCAN_PATH_PATTERN`
4. `TEARDOWN_NON_ESSENTIAL_DEFAULT`
5. `TEARDOWN_BLOCK_ON_RESIDUAL_RISK`
6. `COST_GUARDRAIL_SNAPSHOT_PATH_PATTERN`
7. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
8. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`
9. `PHASE_COST_OUTCOME_REQUIRED`
10. `PHASE_ENVELOPE_REQUIRED`

Execution checks:
1. Read upstream `M12.J` summary and fail closed on non-pass posture.
2. Read upstream `M13-B0` summary and fail closed on non-pass posture.
3. Parse `dev_full_handles.registry.v0.md` and build explicit required-handle matrix.
4. Validate each required handle is present and non-placeholder.
5. Validate path-pattern handles contain required run placeholders:
   - `FULL_VERDICT_PATH_PATTERN`, `TEARDOWN_COST_SNAPSHOT_PATH_PATTERN`, `TEARDOWN_RESIDUAL_SCAN_PATH_PATTERN` include `{platform_run_id}`.
   - `COST_GUARDRAIL_SNAPSHOT_PATH_PATTERN`, `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`, `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN` include `{phase_execution_id}`.
6. Validate teardown and phase-closure flags are typed/coherent:
   - `TEARDOWN_BLOCK_ON_RESIDUAL_RISK` is boolean.
   - `PHASE_COST_OUTCOME_REQUIRED` and `PHASE_ENVELOPE_REQUIRED` are boolean and `true`.
7. Emit and publish:
   - `m13a_handle_closure_snapshot.json`
   - `m13a_blocker_register.json`
   - `m13a_execution_summary.json`

Blockers:
1. `M13-B1` on unresolved/malformed required handles.

Runtime budget:
1. Target <= 5 minutes.

DoD:
- [x] required handle matrix explicit and complete.
- [x] unresolved handles blocker-marked.
- [x] `m13a_handle_closure_snapshot.json` committed locally and durably.
- [x] `m13a_execution_summary.json` shows `overall_pass=true`, `verdict=ADVANCE_TO_M13_B`, `next_gate=M13.B_READY`.

### M13.B - Full Source Matrix Closure
Goal:
1. Prove full source matrix (`M1..M12`) is complete and blocker-free.

Entry conditions:
1. `M13.A` pass.

Execution checks:
1. Verify upstream `M13.A` pass posture (`ADVANCE_TO_M13_B`, `M13.B_READY`).
2. Build required source row set for `M1..M12` with explicit source contract:
   - primary source: durable S3 summary keys,
   - allowed fallback source (legacy-only rows): durable legacy backfill summaries under run-control.
3. For each row, assert:
   - summary is readable from at least one allowed source,
   - pass posture fields meet per-row criteria (`overall_pass`, verdict/next-gate where applicable),
   - row includes explicit `source_mode` (`s3_primary` or `repo_fallback`).
4. Continuity checks:
   - strict run-scope continuity on `M5..M12` (`platform_run_id` and `scenario_run_id` aligned),
   - `M1..M3` may be marked `legacy_pre_run_scope` only with explicit reason marker and pass posture evidence.
5. Emit and publish:
   - `m13b_source_matrix_snapshot.json`,
   - `m13b_blocker_register.json`,
   - `m13b_execution_summary.json`.

Blockers:
1. `M13-B2` on missing/unreadable/inconsistent matrix row.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [x] matrix rows are complete for required sources.
- [x] pass posture is explicit for each source row.
- [x] `m13b_source_matrix_snapshot.json` committed locally and durably.
- [x] `m13b_execution_summary.json` shows `overall_pass=true`, `verdict=ADVANCE_TO_M13_C`, `next_gate=M13.C_READY`.

### M13.C - Six-Proof Matrix Closure
Goal:
1. Close six-proof matrix for required lanes (`spine`, `ofs`, `mf`, `mpr`, `teardown`).

Entry conditions:
1. `M13.B` pass.

Execution checks:
1. each lane has six proofs (deploy, monitor, failure drill, recovery, rollback, cost-control).
2. proof refs are readable.

Blockers:
1. `M13-B3` on incomplete six-proof matrix.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [ ] six-proof matrix has no missing proof cell for required lanes.
- [ ] proof refs are readability-verified.
- [ ] `m13c_six_proof_matrix_snapshot.json` committed locally and durably.

### M13.D - Final Verdict Publication
Goal:
1. Publish deterministic full-platform final verdict.

Entry conditions:
1. `M13.C` pass.

Execution checks:
1. verdict is deterministic and scope-complete.
2. run-scoped final verdict path resolves and is readable after write.

Blockers:
1. `M13-B4` on verdict inconsistency or publication failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [ ] run-scoped final verdict exists and is readable.
- [ ] `m13d_final_verdict_bundle.json` committed locally and durably.

### M13.E - Teardown Plan Closure
Goal:
1. Produce deterministic teardown plan for non-essential resources.

Entry conditions:
1. `M13.D` pass.

Execution checks:
1. non-essential teardown targets enumerated.
2. protected/retained surfaces explicit (evidence/object stores).

Blockers:
1. `M13-B5` on teardown plan ambiguity/incompleteness.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [ ] teardown target matrix complete.
- [ ] `m13e_teardown_plan_snapshot.json` committed locally and durably.

### M13.F - Teardown Execution Closure
Goal:
1. Execute teardown/idle-safe posture.

Entry conditions:
1. `M13.E` pass.

Execution checks:
1. non-essential runtime scaled to zero or destroyed.
2. required retained surfaces remain intact.

Blockers:
1. `M13-B6` on teardown execution failure.

Runtime budget:
1. Target <= 12 minutes.

DoD:
- [ ] teardown execution snapshot pass.
- [ ] `m13f_teardown_execution_snapshot.json` committed locally and durably.

### M13.G - Residual Risk + Readability Closure
Goal:
1. Prove no forbidden residuals and preserve evidence readability post-teardown.

Entry conditions:
1. `M13.F` pass.

Execution checks:
1. residual scan pass (or explicit accepted waiver).
2. post-teardown evidence readability pass.

Blockers:
1. `M13-B7` on residual risk.
2. `M13-B8` on unreadable post-teardown evidence.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [ ] residual scan report pass or accepted waiver recorded.
- [ ] readability snapshot pass.
- [ ] `m13g_post_teardown_readability_snapshot.json` committed locally and durably.

### M13.H - Post-Teardown Cost Guardrail Closure
Goal:
1. Publish post-teardown cost guardrail snapshot.

Entry conditions:
1. `M13.G` pass.

Execution checks:
1. cost guardrail snapshot emitted.
2. snapshot reflects idle-safe posture.

Blockers:
1. `M13-B9` on cost guardrail closure failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [ ] cost guardrail snapshot committed.
- [ ] `m13h_cost_guardrail_snapshot.json` committed locally and durably.

### M13.I - M13 Phase Budget + Cost-Outcome Closure
Goal:
1. Publish M13 budget envelope and cost-outcome receipt.

Entry conditions:
1. `M13.H` pass.

Execution checks:
1. `m13_phase_budget_envelope.json` emitted.
2. `m13_phase_cost_outcome_receipt.json` emitted.
3. receipt field contract is satisfied.

Blockers:
1. `M13-B10` on cost-outcome closure failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [ ] budget envelope and cost-outcome receipt committed locally and durably.
- [ ] receipt field contract closure pass.

### M13.J - M13 Closure Sync
Goal:
1. Close M13 and publish authoritative final summary.

Entry conditions:
1. `M13.I` pass.

Execution checks:
1. emit `m13_execution_summary.json`.
2. emit `m13_blocker_register.json`.
3. parity/readability check for required M13 outputs.

Blockers:
1. `M13-B11` on summary/evidence parity failure.
2. `M13-B12` on non-gate acceptance failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [ ] `m13_execution_summary.json` committed locally and durably.
- [ ] `m13_blocker_register.json` committed locally and durably.
- [ ] M13 closure sync passes with no unresolved blocker.

## 7) Blocker Taxonomy (Fail-Closed)
1. `M13-B0`: managed M13 execution lane not materialized.
2. `M13-B1`: authority/handle closure failure.
3. `M13-B2`: full source matrix closure failure.
4. `M13-B3`: six-proof matrix incompleteness.
5. `M13-B4`: final verdict inconsistency/publication failure.
6. `M13-B5`: teardown plan closure failure.
7. `M13-B6`: teardown execution failure.
8. `M13-B7`: residual cost/resource risk.
9. `M13-B8`: post-teardown evidence unreadable.
10. `M13-B9`: post-teardown cost guardrail closure failure.
11. `M13-B10`: phase cost-outcome closure failure.
12. `M13-B11`: summary/evidence publication parity failure.
13. `M13-B12`: non-gate acceptance failure.

## 8) Completion Checklist
- [x] `M13.A` complete
- [x] `M13.B` complete
- [ ] `M13.C` complete
- [ ] `M13.D` complete
- [ ] `M13.E` complete
- [ ] `M13.F` complete
- [ ] `M13.G` complete
- [ ] `M13.H` complete
- [ ] `M13.I` complete
- [ ] `M13.J` complete
- [ ] all active `M13-B*` blockers resolved
- [ ] final verdict + teardown + cost closure artifacts are pass posture

## 9) Planning Status
1. M13 deep plan is now execution-grade and aligned to P16/P17 authority.
2. M12 closure entry requirements are satisfied.
3. Managed workflow file `.github/workflows/dev_full_m13_managed.yml` is materialized and merged to default branch `main` via workflow-only PR `#70`.
4. `M13-B0` is closed green from run `22500308645` (`dev-full-m13-managed`, `m13_subphase=A`):
   - `overall_pass=true`
   - `verdict=ADVANCE_TO_M13_A`
   - `next_gate=M13.A_READY`
   - evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13a_handle_closure_20260227T191722Z/`
5. `M13.A` is closed green from run `22506814523` (`dev-full-m13-managed`, `m13_subphase=A`, `execution_mode=handle_closure`):
   - `overall_pass=true`
   - `verdict=ADVANCE_TO_M13_B`
   - `next_gate=M13.B_READY`
   - evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13a_handle_closure_20260227T224800Z/`
6. `M13.B` first attempt failed (`run_id=22507181947`, execution `m13b_source_matrix_20260227T230154Z`) with `M13-B2` on legacy source readability (`M1..M4`) and strict continuity extraction for `M11`.
7. `M13.B` blocker remediation applied:
   - durable legacy fallback summaries written to:
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13b_legacy_matrix_backfill_20260227/m1e_execution_summary.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13b_legacy_matrix_backfill_20260227/m2j_execution_summary.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13b_legacy_matrix_backfill_20260227/m3_execution_summary.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13b_legacy_matrix_backfill_20260227/m4_execution_summary.json`
   - M11 matrix row source switched to `m11j_execution_summary.json` for run-scope fields.
8. `M13.B` is now closed green from run `22507270736` (`dev-full-m13-managed`, `m13_subphase=B`, `execution_mode=source_matrix_closure`):
   - execution id: `m13b_source_matrix_20260227T230519Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M13_C`,
   - `next_gate=M13.C_READY`,
   - evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13b_source_matrix_20260227T230519Z/`.
9. Next action: expand and execute `M13.C` (six-proof matrix closure) on managed lane.
