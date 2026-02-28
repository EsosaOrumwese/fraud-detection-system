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
1. Verify upstream `M13.B` pass posture (`ADVANCE_TO_M13_C`, `M13.C_READY`).
2. Build lane matrix for required lanes (`spine`, `ofs`, `mf`, `mpr`, `teardown`) and required proof categories:
   - `deploy`, `monitor`, `failure_drill`, `recovery`, `rollback`, `cost_control`.
3. For every lane/proof cell, assert:
   - proof ref is explicitly pinned (no empty cells),
   - proof ref is readability-verified from durable evidence surface.
4. Emit and publish:
   - `m13c_six_proof_matrix_snapshot.json`,
   - `m13c_blocker_register.json`,
   - `m13c_execution_summary.json`.

Blockers:
1. `M13-B3` on incomplete six-proof matrix.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [x] six-proof matrix has no missing proof cell for required lanes.
- [x] proof refs are readability-verified.
- [x] `m13c_six_proof_matrix_snapshot.json` committed locally and durably.
- [x] `m13c_execution_summary.json` shows `overall_pass=true`, `verdict=ADVANCE_TO_M13_D`, `next_gate=M13.D_READY`.

### M13.D - Final Verdict Publication
Goal:
1. Publish deterministic full-platform final verdict.

Entry conditions:
1. `M13.C` pass.
2. upstream `M13.C` summary is readable and gate-consistent (`ADVANCE_TO_M13_D`, `M13.D_READY`).

Execution checks:
1. resolve source-matrix closure surface (`M1..M12`) from `M13.B` snapshot and re-validate row readability/pass posture.
2. append `M13.A`, `M13.B`, `M13.C` summary closure checks into final-verdict scope.
3. construct deterministic verdict bundle (`m13d_final_verdict_bundle.json`) with explicit phase coverage map.
4. publish full verdict object to `FULL_VERDICT_PATH_PATTERN` (run-scoped) and read back for parity.
5. enforce fail-closed `M13-B4` on any missing/unreadable/inconsistent scope row or publish/readback mismatch.

Blockers:
1. `M13-B4` on verdict inconsistency or publication failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [x] upstream `M13.C` gate checks pass (`ADVANCE_TO_M13_D`, `M13.D_READY`).
- [x] scope rows (`M1..M12`, `M13.A`, `M13.B`, `M13.C`) are readability-verified and pass.
- [x] run-scoped final verdict exists and is readable.
- [x] `m13d_final_verdict_bundle.json` committed locally and durably.
- [x] `m13d_execution_summary.json` shows `overall_pass=true`, `verdict=ADVANCE_TO_M13_E`, `next_gate=M13.E_READY`.

### M13.E - Teardown Plan Closure
Goal:
1. Produce deterministic teardown plan for non-essential resources.

Entry conditions:
1. `M13.D` pass.
2. upstream `M13.D` summary is readable and gate-consistent (`ADVANCE_TO_M13_E`, `M13.E_READY`).

Execution checks:
1. teardown handles are present and non-placeholder:
   - `TEARDOWN_NON_ESSENTIAL_DEFAULT`,
   - `TEARDOWN_BLOCK_ON_RESIDUAL_RISK`,
   - `TEARDOWN_RESIDUAL_SCAN_PATH_PATTERN`,
   - `TEARDOWN_COST_SNAPSHOT_PATH_PATTERN`,
   - `FULL_VERDICT_PATH_PATTERN`.
2. run-scoped full verdict is readable and provides `platform_run_id` + `scenario_run_id`.
3. non-essential teardown target matrix is complete and deterministic.
4. protected/retained surfaces are explicit (evidence/object-store truth surfaces).
5. residual/cost snapshot outputs for next lanes are rendered from handle patterns.

Blockers:
1. `M13-B5` on teardown plan ambiguity/incompleteness.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [x] upstream `M13.D` gate checks pass (`ADVANCE_TO_M13_E`, `M13.E_READY`).
- [x] teardown target matrix complete.
- [x] retained/protected surface matrix complete.
- [x] residual/cost planned output refs are rendered and non-empty.
- [x] `m13e_teardown_plan_snapshot.json` committed locally and durably.
- [x] `m13e_execution_summary.json` shows `overall_pass=true`, `verdict=ADVANCE_TO_M13_F`, `next_gate=M13.F_READY`.

### M13.F - Teardown Execution Closure
Goal:
1. Execute teardown/idle-safe posture.

Entry conditions:
1. `M13.E` pass.
2. upstream `M13.E` summary is readable and gate-consistent (`ADVANCE_TO_M13_F`, `M13.F_READY`).

Execution checks:
1. execute teardown actions from `M13.E` plan on non-essential runtime surfaces.
2. EKS runtime nodegroups are scaled to `min=0`, `desired=0`.
3. ECS runtime services are scaled to desired `0`.
4. active EMR-on-EKS jobs are cancelled (if present).
5. active SageMaker endpoints are deleted or moved out of active status.
6. required retained surfaces remain intact/readable after teardown actions.
7. run-scoped full verdict object remains readable.

Blockers:
1. `M13-B6` on teardown execution failure.

Runtime budget:
1. Target <= 12 minutes.

DoD:
- [x] upstream `M13.E` gate checks pass (`ADVANCE_TO_M13_F`, `M13.F_READY`).
- [x] teardown execution action receipts are complete.
- [x] non-essential runtime post-state is zero/idle-safe.
- [x] retained/protected surfaces are readability-verified post-teardown.
- [x] `m13f_teardown_execution_snapshot.json` committed locally and durably.
- [x] `m13f_execution_summary.json` shows `overall_pass=true`, `verdict=ADVANCE_TO_M13_G`, `next_gate=M13.G_READY`.

### M13.G - Residual Risk + Readability Closure
Goal:
1. Prove no forbidden residuals and preserve evidence readability post-teardown.

Entry conditions:
1. `M13.F` pass.
2. upstream `M13.F` summary is readable and gate-consistent (`ADVANCE_TO_M13_G`, `M13.G_READY`).

Execution checks:
1. load upstream `M13.F` execution summary and enforce pass posture.
2. load upstream `M13.F` teardown execution snapshot and extract post-state surfaces:
   - EKS nodegroups,
   - ECS services,
   - EMR on EKS active runs,
   - SageMaker endpoints.
3. derive residual-risk matrix from post-state:
   - any non-zero EKS nodegroup min/desired is residual,
   - any ECS desired count > 0 is residual,
   - any EMR active run is residual,
   - any active SageMaker endpoint state is residual.
4. load upstream `M13.E` teardown plan snapshot (via `M13.F` linkage) and resolve:
   - `platform_run_id`,
   - `teardown_block_on_residual_risk`,
   - run-scoped residual scan destination.
5. publish deterministic run-scoped residual scan object and verify readback.
6. verify post-teardown evidence readability:
   - retained surfaces from `M13.E` remain readable,
   - run-scoped full verdict remains readable,
   - upstream `M13.E/F` required artifacts remain readable.
7. fail-closed posture:
   - `M13-B7` if residual risk exists while `teardown_block_on_residual_risk=true`,
   - `M13-B8` for unreadable required evidence surfaces.

Blockers:
1. `M13-B7` on residual risk.
2. `M13-B8` on unreadable post-teardown evidence.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [x] upstream `M13.F` gate checks pass (`ADVANCE_TO_M13_G`, `M13.G_READY`).
- [x] deterministic residual scan object is published and readable at run-scoped path.
- [x] residual-risk matrix is explicit and blocker-free (or accepted waiver explicitly recorded).
- [x] post-teardown readability matrix is explicit and blocker-free.
- [x] `m13g_post_teardown_readability_snapshot.json` committed locally and durably.
- [x] `m13g_execution_summary.json` shows `overall_pass=true`, `verdict=ADVANCE_TO_M13_H`, `next_gate=M13.H_READY`.

### M13.H - Post-Teardown Cost Guardrail Closure
Goal:
1. Publish post-teardown cost guardrail snapshot.

Entry conditions:
1. `M13.G` pass.
2. upstream `M13.G` summary is readable and gate-consistent (`ADVANCE_TO_M13_H`, `M13.H_READY`).

Execution checks:
1. load upstream `M13.G` summary and enforce pass posture.
2. load upstream `M13.G` residual/readability snapshot and linked `M13.E` teardown plan.
3. enforce residual closure continuity:
   - `residual_item_count=0`,
   - `residual_scan_published=true`.
4. verify idle-safe runtime posture at closure point:
   - no non-zero EKS nodegroup desired/min targets,
   - no ECS desired counts > 0 for dev-full runtime clusters,
   - no active EMR-on-EKS runs on pinned virtual cluster,
   - no active SageMaker endpoint states.
5. construct deterministic cost-guardrail snapshot containing:
   - runtime idle posture summary,
   - guardrail result,
   - run-scoped teardown cost snapshot reference.
6. publish run-scoped teardown cost snapshot object and verify readback.
7. emit run-control snapshot + blocker register + execution summary.

Blockers:
1. `M13-B9` on cost guardrail closure failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [x] upstream `M13.G` gate checks pass (`ADVANCE_TO_M13_H`, `M13.H_READY`).
- [x] residual closure continuity checks pass (`residual_item_count=0`, `residual_scan_published=true`).
- [x] idle runtime posture checks pass at closure point.
- [x] run-scoped teardown cost snapshot is published and readability-verified.
- [x] `m13h_cost_guardrail_snapshot.json` committed locally and durably.
- [x] `m13h_execution_summary.json` shows `overall_pass=true`, `verdict=ADVANCE_TO_M13_I`, `next_gate=M13.I_READY`.

### M13.I - M13 Phase Budget + Cost-Outcome Closure
Goal:
1. Publish M13 budget envelope and cost-outcome receipt.

Entry conditions:
1. `M13.H` pass.
2. upstream `M13.H` summary is readable and gate-consistent (`ADVANCE_TO_M13_I`, `M13.I_READY`).

Execution checks:
1. load upstream `M13.H` summary and enforce pass posture.
2. load upstream `M13.H` cost-guardrail snapshot and verify:
   - `idle_safe=true`,
   - `residual_item_count=0`,
   - run-scoped teardown cost snapshot was published.
3. resolve/pin M13 phase-cost handles from registry:
   - `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`,
   - `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`,
   - `PHASE_COST_OUTCOME_REQUIRED`,
   - `PHASE_ENVELOPE_REQUIRED`,
   - `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD`,
   - `DEV_FULL_BUDGET_ALERT_1_USD`,
   - `DEV_FULL_BUDGET_ALERT_2_USD`,
   - `DEV_FULL_BUDGET_ALERT_3_USD`,
   - `BUDGET_CURRENCY`.
4. emit deterministic phase envelope:
   - `m13_phase_budget_envelope.json` with configured monthly/threshold contract for M13 closure scope.
5. emit deterministic phase cost-outcome receipt:
   - `m13_phase_cost_outcome_receipt.json` with upstream closure linkage and guardrail outcome.
6. publish envelope + receipt to rendered phase-pattern refs and verify readback.
7. emit run-control `M13.I` snapshot + blocker register + execution summary.

Blockers:
1. `M13-B10` on cost-outcome closure failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [x] upstream `M13.H` gate checks pass (`ADVANCE_TO_M13_I`, `M13.I_READY`).
- [x] `m13_phase_budget_envelope.json` committed locally and durably.
- [x] `m13_phase_cost_outcome_receipt.json` committed locally and durably.
- [x] rendered phase-pattern refs for envelope/receipt are published and readability-verified.
- [x] receipt field contract closure pass (guardrail linkage + idle-safe continuity).
- [x] `m13i_execution_summary.json` shows `overall_pass=true`, `verdict=ADVANCE_TO_M13_J`, `next_gate=M13.J_READY`.

### M13.J - M13 Closure Sync
Goal:
1. Close M13 and publish authoritative final summary.

Entry conditions:
1. `M13.I` pass.
2. upstream `M13.I` summary is readable and gate-consistent (`ADVANCE_TO_M13_J`, `M13.J_READY`).

Execution checks:
1. load and validate upstream execution summaries for `M13.A..M13.I`:
   - each `overall_pass=true`,
   - each `blocker_count=0`,
   - each `next_gate` matches expected phase transition.
2. enforce M13 transition chain parity:
   - `A -> B_READY`,
   - `B -> C_READY`,
   - `C -> D_READY`,
   - `D -> E_READY`,
   - `E -> F_READY`,
   - `F -> G_READY`,
   - `G -> H_READY`,
   - `H -> I_READY`,
   - `I -> J_READY`.
3. validate non-gate acceptance closure surfaces:
   - final verdict reference from `M13.D` is present and readable,
   - post-teardown guardrail continuity from `M13.H` is pass posture (`idle_safe=true`, `residual_item_count=0`, run-scoped snapshot published),
   - phase cost-outcome continuity from `M13.I` is pass posture (`phase_outcome_pass=true`, `cost_within_envelope=true`).
4. verify run-scope continuity (`platform_run_id`, `scenario_run_id`) across `M13.D`, `M13.H`, `M13.I`.
5. emit authoritative closure artifacts:
   - `m13_execution_summary.json`,
   - `m13_blocker_register.json`,
   - `m13_closure_sync_snapshot.json` (source matrix + non-gate acceptance evidence index).
6. publish closure artifacts to run-control path and verify readback.
7. terminal verdict on pass:
   - `verdict=M13_COMPLETE_GREEN`,
   - `next_gate=DEV_FULL_TRACK_COMPLETE`.

Blockers:
1. `M13-B11` on summary/evidence parity failure.
2. `M13-B12` on non-gate acceptance failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [x] upstream `M13.I` gate check passes (`ADVANCE_TO_M13_J`, `M13.J_READY`).
- [x] `M13.A..M13.I` transition/source-matrix parity is pass posture.
- [x] non-gate acceptance closure checks are pass posture.
- [x] `m13_execution_summary.json` committed locally and durably.
- [x] `m13_blocker_register.json` committed locally and durably.
- [x] `m13_closure_sync_snapshot.json` committed locally and durably.
- [x] `m13_execution_summary.json` shows `overall_pass=true`, `verdict=M13_COMPLETE_GREEN`, `next_gate=DEV_FULL_TRACK_COMPLETE`.

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
- [x] `M13.C` complete
- [x] `M13.D` complete
- [x] `M13.E` complete
- [x] `M13.F` complete
- [x] `M13.G` complete
- [x] `M13.H` complete
- [x] `M13.I` complete
- [x] `M13.J` complete
- [x] all active `M13-B*` blockers resolved
- [x] final verdict + teardown + cost closure artifacts are pass posture

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
9. `M13.C` first attempt failed (`run_id=22507540671`, execution `m13c_six_proof_matrix_20260227T231600Z`) with `M13-B3` on teardown proof readability (legacy `m2i` KMS/read access surface).
10. `M13.C` blocker remediation cycle:
   - teardown proof artifacts rematerialized to readable durable prefix:
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13c_teardown_backfill_20260227/m2i_rehearsal_scope_snapshot.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13c_teardown_backfill_20260227/m2i_residual_scan_snapshot.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13c_teardown_backfill_20260227/m2i_destroy_apply_receipts.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13c_teardown_backfill_20260227/m2i_recover_apply_receipts.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13c_teardown_backfill_20260227/m2i_post_recovery_integrity_snapshot.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13c_teardown_backfill_20260227/m2i_cost_posture_snapshot.json`
   - second run (`22507614201`, execution `m13c_six_proof_matrix_20260227T231902Z`) reduced blockers to 3; parser updated to accept valid JSON arrays for proof readability checks.
11. `M13.C` is now closed green from run `22507681052` (`dev-full-m13-managed`, `m13_subphase=C`, `execution_mode=six_proof_closure`):
   - execution id: `m13c_six_proof_matrix_20260227T232146Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M13_D`,
   - `next_gate=M13.D_READY`,
   - evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13c_six_proof_matrix_20260227T232146Z/`.
12. `M13.C` re-validation rerun is green from run `22507835286` (`dev-full-m13-managed`, `m13_subphase=C`, `execution_mode=six_proof_closure`):
   - execution id: `m13c_six_proof_matrix_20260227T232813Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M13_D`,
   - `next_gate=M13.D_READY`,
   - evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13c_six_proof_matrix_20260227T232813Z/`.
13. `M13.D` first attempt failed (`run_id=22508061627`, execution `m13d_final_verdict_20260227T233738Z`) with `M13-B4` on strict overall-pass enforcement against legacy pre-run row (`M1`) already accepted in `M13.B`.
14. `M13.D` blocker remediation applied:
   - propagated `legacy_scope_reason` + `upstream_row_pass` from `M13.B` source matrix rows,
   - enforced readability + upstream row pass for legacy rows,
   - retained strict `overall_pass/blocker_count` checks for non-legacy rows.
15. `M13.D` is now closed green from run `22508123412` (`dev-full-m13-managed`, `m13_subphase=D`, `execution_mode=final_verdict_closure`):
   - execution id: `m13d_final_verdict_20260227T234010Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M13_E`,
   - `next_gate=M13.E_READY`,
   - run-control evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13d_final_verdict_20260227T234010Z/`,
   - full verdict path: `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/full_platform/final_verdict.json`.
16. `M13.E` is closed green from run `22508292412` (`dev-full-m13-managed`, `m13_subphase=E`, `execution_mode=teardown_plan_closure`):
   - execution id: `m13e_teardown_plan_20260227T234734Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M13_F`,
   - `next_gate=M13.F_READY`,
   - run-control evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13e_teardown_plan_20260227T234734Z/`.
17. `M13.F` first execution failed closed:
   - run: `22508463812`, execution `m13f_teardown_execution_20260227T235508Z`,
   - result: `overall_pass=false`, `blocker_count=3`, `verdict=HOLD_REMEDIATE`,
   - blocker surfaces: `eks:list_nodegroups`, `sagemaker:list_endpoints_before`, `sagemaker:list_endpoints_after` (`AccessDenied` posture under current OIDC role policy).
18. `M13.F` blocker remediation applied on IAM lane:
   - Terraform stack: `infra/terraform/dev_full/ops`,
   - policy updated (`GitHubActionsM6FRemoteDevFull`) to include:
     - `eks:ListNodegroups`, `eks:UpdateNodegroupConfig`, `eks:DescribeUpdate`,
     - `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`, `sagemaker:DeleteEndpoint`,
   - preserved prior `M12d` IAM statements (`M12dEKSDescribeCluster`, `M12dKafkaDataPlaneProof`) in Terraform source before targeted apply.
19. `M13.F` is now closed green from run `22508650494` (`dev-full-m13-managed`, `m13_subphase=F`, `execution_mode=teardown_execution_closure`):
   - execution id: `m13f_teardown_execution_20260228T000326Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M13_G`,
   - `next_gate=M13.G_READY`,
   - run-control evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13f_teardown_execution_20260228T000326Z/`.
20. `M13.G` mode gap closed in managed workflow:
   - added `execution_mode=residual_readability_closure` bound to `m13_subphase=G`,
   - added `upstream_m13f_execution` input + fail-closed `M13-B7/M13-B8` checks.
21. `M13.G` is now closed green from run `22508840465` (`dev-full-m13-managed`, `m13_subphase=G`, `execution_mode=residual_readability_closure`):
   - execution id: `m13g_residual_readability_20260228T001208Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M13_H`,
   - `next_gate=M13.H_READY`,
   - `residual_item_count=0`,
   - `residual_scan_published=true`,
   - run-control evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13g_residual_readability_20260228T001208Z/`.
22. `M13.H` mode gap closed in managed workflow:
   - added `execution_mode=post_teardown_cost_guardrail_closure` bound to `m13_subphase=H`,
   - added `upstream_m13g_execution` input + fail-closed `M13-B9` idle/cost guardrail checks.
23. `M13.H` is now closed green from run `22508967026` (`dev-full-m13-managed`, `m13_subphase=H`, `execution_mode=post_teardown_cost_guardrail_closure`):
   - execution id: `m13h_cost_guardrail_20260228T001807Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M13_I`,
   - `next_gate=M13.I_READY`,
   - guardrail posture: `idle_safe=true`, `residual_item_count=0`, `run_scoped_snapshot_published=true`,
   - run-control evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13h_cost_guardrail_20260228T001807Z/`.
24. `M13.I` first managed execution failed closed (`run_id=22509104250`, execution `m13i_phase_cost_outcome_20260228T002428Z`) with blocker `M13-B10`:
   - failure cause: numeric budget pins were parsed through a string-only helper in workflow logic, resolving threshold values to null (`monthly_limit/alert_1/alert_2/alert_3`).
25. `M13.I` blocker remediation:
   - updated `.github/workflows/dev_full_m13_managed.yml` `get_handle_float()` to parse raw numeric handle values directly (while still rejecting boolean values),
   - workflow-only release commit: `8c8757068` (`ci: fix M13.I budget handle parsing for numeric pins`).
26. `M13.I` is now closed green from run `22509198947` (`dev-full-m13-managed`, `m13_subphase=I`, `execution_mode=phase_cost_outcome_closure`):
   - execution id: `m13i_phase_cost_outcome_20260228T002906Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M13_J`,
   - `next_gate=M13.J_READY`,
   - budget pins resolved and validated in snapshot:
     - `monthly_limit=300.0`,
     - `alert_1=120.0`,
     - `alert_2=210.0`,
     - `alert_3=270.0`,
   - run-control evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13i_phase_cost_outcome_20260228T002906Z/`.
27. `M13.J` mode gap closed in managed workflow:
   - added `execution_mode=final_closure_sync` bound to `m13_subphase=J`,
   - added `upstream_m13i_execution` input + fail-closed `M13-B11/M13-B12` checks.
28. `M13.J` is closed green from run `22509404836` (`dev-full-m13-managed`, `m13_subphase=J`, `execution_mode=final_closure_sync`):
   - execution id: `m13j_closure_sync_20260228T003853Z`,
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=M13_COMPLETE_GREEN`,
   - `next_gate=DEV_FULL_TRACK_COMPLETE`,
   - source matrix parity: pass for `M13.A..M13.I`,
   - non-gate acceptance closure: pass (`final verdict readability`, `guardrail continuity`, `phase cost-outcome continuity`),
   - run-control evidence prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m13j_closure_sync_20260228T003853Z/`.
29. M13 is now fully closed green on managed lane.
