# Dev Full Road To Production-Ready - PR2 Numeric Contract Activation
_As of 2026-03-05_

## 0) Purpose
`PR2` activates numeric contracts required for downstream runtime and ops/governance certification.

`PR2` is fail-closed. It cannot pass unless:
1. required active-scope numeric contract rows are populated (no required `TBD`),
2. measurement surfaces and sample minima are explicitly bound,
3. contract activation validators pass with zero unresolved blockers.

## 1) Binding Authorities
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`
2. `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_s5_execution_receipt.json`
3. `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_execution_summary.json`
4. `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/g2_data_realism_pack_index.json`
5. `docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md` (Section 12 + Appendix A.1 + Appendix C.1)
6. `docs/model_spec/data-engine/interface_pack/` (boundary contract; engine internals out-of-scope)

## 2) Scope Boundary
In scope:
1. required row inventory/gap map for active RC2-S numeric contract scope,
2. threshold and measurement-surface population from measured evidence plus policy guardbands,
3. contract activation validation and anti-gaming checks,
4. deterministic activation index and phase verdict emission.

Out of scope:
1. runtime pressure certification windows (`PR3/G3A`),
2. ops/governance drill execution (`PR4/G3B`),
3. go-live rehearsal mission (`PR5/G4`).

## 3) PR2 Exit Standard (Hard)
`PR2` can close only if all conditions are true:
1. runtime and ops/governance contract artifacts are present and `ACTIVE`,
2. active required scope has no unresolved `TBD`,
3. activation validators pass (`ENV_NOT_ACTIVATABLE`/`BASELINES_NOT_ACTIVATABLE` absent),
4. threshold sanity and anti-gaming checks pass,
5. rollup verdict is `PR3_READY` with `open_blockers=0` and deterministic evidence index.

## 4) Capability Lanes (Mandatory PR2 Coverage)
`PR2` must explicitly cover all lanes below:
1. Authority/handles lane:
   - bind PR1 closure artifacts and numeric contract authority sections.
2. Identity/IAM lane:
   - declare readers/writers for contract artifacts and validator outputs.
3. Network/runtime lane:
   - preserve injection-path claim scope (`via_IG`) inherited from PR1 pack.
4. Data store lane:
   - define deterministic PR2 run root and contract artifact paths.
5. Messaging lane:
   - bind measurement surfaces and event-flow boundaries to active thresholds.
6. Secrets lane:
   - no secrets or decrypted values in PR2 docs/artifacts.
7. Observability/evidence lane:
   - emit validator outputs, activation index, blocker register, and summary.
8. Rollback/rerun lane:
   - every blocker maps to one exact state rerun boundary.
9. Teardown/idle lane:
   - no always-on runtime introduced by PR2 planning.
10. Budget lane:
    - enforce runtime/cost budgets and fail on unexplained spend.

## 5) Execution Posture (Performance + Cost Discipline)
1. Evidence-first posture:
   - reuse PR1 measured artifacts and existing authority templates before any fresh extraction.
2. No rerun-the-world:
   - remediate and rerun only failed PR2 boundary state.
3. No local orchestration:
   - local machine is only for planning/validation artifact generation.
4. Fail-closed activatability:
   - `ACTIVE` contracts cannot retain required `TBD`.

## 6) PR2 State Plan (`S0..S3`)

### S0 - Entry Lock, Required-Row Inventory, And Gap Map
Objective:
1. pin strict upstream continuity from PR1 and enumerate required active-scope contract rows.

Required actions:
1. validate upstream PR1 receipt (`PR1_S5_READY`, `open_blockers=0`),
2. derive required row inventory for active RC2-S scope from A.1/C.1 validator laws,
3. classify each row as `prefilled`, `pending_fill`, `deferred_out_of_scope` (with explicit reason),
4. assign owner lane and due state for each pending row.

Outputs:
1. `pr2_entry_lock.json`
2. `pr2_required_row_inventory.json`
3. `pr2_gap_map.json`
4. `pr2_s0_execution_receipt.json`

Pass condition:
1. required row inventory is complete and no required row is orphaned without owner/state.

Fail-closed blockers:
1. `PR2.B01_ENTRY_LOCK_MISSING`
2. `PR2.B02_UPSTREAM_PR1_NOT_READY`
3. `PR2.B03_REQUIRED_ROW_INVENTORY_MISSING`
4. `PR2.B04_REQUIRED_ROW_OWNER_GAP`

S0 planning expansion (execution checklist):
1. upstream lock:
   - require `pr1_s5_execution_receipt.json` with `PR1_S5_READY`.
2. scope lock:
   - active scope = RC2-S required rows only; RC2-L rows remain explicitly deferred.
3. inventory lock:
   - include row id, source template path, required/optional flag, current status, owner lane.
4. gap lock:
   - map each pending required row to S1/S2 fill or validation boundary.
5. publication lock:
   - emit readable S0 digest in PR2 doc + main plan + logbook.

### S1 - Threshold Population And Contract Materialization
Objective:
1. materialize runtime and ops/governance RC2-S contract artifacts with populated required fields.

Required actions:
1. populate runtime contract fields (campaign/cohorts/sample minima/thresholds/surfaces/evidence contract),
2. populate ops/governance baseline fields (metric families/alerts/runbooks/window binding),
3. attach calibration traceability (`baseline -> target -> guardband -> source_ref`),
4. mark artifacts `ACTIVE` only if required fields are fully populated.

Outputs:
1. `pr2_runtime_numeric_contract.rc2s.active.yaml`
2. `pr2_opsgov_numeric_contract.rc2s.active.yaml`
3. `pr2_threshold_population_ledger.json`
4. `pr2_calibration_traceability.json`
5. `pr2_deferred_scope_register.json`
6. `pr2_s1_execution_receipt.json`

Pass condition:
1. required active-scope rows are populated with no required `TBD`.

Fail-closed blockers:
1. `PR2.B05_RUNTIME_CONTRACT_MISSING`
2. `PR2.B06_OPSGOV_CONTRACT_MISSING`
3. `PR2.B07_REQUIRED_TBD_REMAIN`
4. `PR2.B08_MEASUREMENT_SURFACE_UNBOUND`
5. `PR2.B09_CALIBRATION_TRACE_MISSING`

S1 planning expansion (execution checklist):
1. evidence lock:
   - use PR1 pack outputs as first-class baseline sources.
2. threshold lock:
   - every required threshold has explicit value, unit, and failure behavior.
3. surface lock:
   - every required metric maps to declared measurement surface(s).
4. calibration lock:
   - each policy target has baseline + guardband + source reference.
5. status lock:
   - `ACTIVE` state allowed only when required rows are non-`TBD`.

### S2 - Activation Validation And Anti-Gaming Checks
Objective:
1. prove populated contracts are activatable and logically sane before PR3 execution.

Required actions:
1. validate runtime contract against A.1 activation laws,
2. validate ops/governance baseline contract against C.1 activation laws,
3. run threshold sanity checks (`p95<=p99`, bounded rates, residual max=0, etc.),
4. verify anti-gaming posture (distribution requirements, sample minima, injection-path scope notes).

Outputs:
1. `pr2_runtime_contract_validator.json`
2. `pr2_opsgov_contract_validator.json`
3. `pr2_threshold_sanity_report.json`
4. `pr2_activation_validation_matrix.json`
5. `pr2_s2_execution_receipt.json`

Pass condition:
1. validators pass and no critical activation/sanity failure remains.

Fail-closed blockers:
1. `PR2.B10_ENV_NOT_ACTIVATABLE`
2. `PR2.B11_BASELINES_NOT_ACTIVATABLE`
3. `PR2.B12_THRESHOLD_SANITY_FAIL`
4. `PR2.B13_ALERT_RUNBOOK_BINDING_MISSING`
5. `PR2.B14_ANTI_GAMING_GUARD_FAIL`

S2 planning expansion (execution checklist):
1. validator lock:
   - emit explicit `overall_valid` with structured failure codes and paths.
2. sanity lock:
   - enforce required mathematical and range checks for active fields.
3. anti-gaming lock:
   - enforce distribution/sample minima and non-proxy measurement surface rules.
4. rerun lock:
   - each failed check maps to exact remediation owner and rerun boundary.

### S3 - Activation Verdict And Blocker Rollup
Objective:
1. emit deterministic PR2 activation verdict and handoff posture to PR3.

Required actions:
1. compile activation index with contract refs + statuses + validator summaries,
2. compute blocker register from S0..S2 outcomes,
3. emit phase summary and evidence index,
4. set `next_gate=PR3_READY` only when blockers are zero.

Outputs:
1. `pr2_numeric_contract_activation_index.json`
2. `pr2_blocker_register.json`
3. `pr2_execution_summary.json`
4. `pr2_evidence_index.json`
5. `pr2_s3_execution_receipt.json`

Pass condition:
1. verdict `PR3_READY`, `open_blockers=0`, and activation index complete.

Fail-closed blockers:
1. `PR2.B15_ACTIVATION_INDEX_MISSING`
2. `PR2.B16_SUMMARY_MISSING`
3. `PR2.B17_OPEN_BLOCKERS_NONZERO`
4. `PR2.B18_VERDICT_NOT_PR3_READY`
5. `PR2.B19_UNATTRIBUTED_SPEND`

S3 planning expansion (execution checklist):
1. rollup lock:
   - include all required contract refs, validator refs, and target-state posture.
2. blocker lock:
   - include blocker id, severity, reason, owner, rerun boundary.
3. handoff lock:
   - `PR3_READY` only when `open_blockers=0`.

## 7) PR2 Artifact Contract
Deterministic control root:
1. `runs/dev_substrate/dev_full/road_to_prod/run_control/<pr2_execution_id>/`

Required artifacts:
1. `pr2_entry_lock.json`
2. `pr2_required_row_inventory.json`
3. `pr2_gap_map.json`
4. `pr2_runtime_numeric_contract.rc2s.active.yaml`
5. `pr2_opsgov_numeric_contract.rc2s.active.yaml`
6. `pr2_threshold_population_ledger.json`
7. `pr2_calibration_traceability.json`
8. `pr2_deferred_scope_register.json`
9. `pr2_runtime_contract_validator.json`
10. `pr2_opsgov_contract_validator.json`
11. `pr2_threshold_sanity_report.json`
12. `pr2_activation_validation_matrix.json`
13. `pr2_numeric_contract_activation_index.json`
14. `pr2_blocker_register.json`
15. `pr2_execution_summary.json`
16. `pr2_evidence_index.json`
17. `pr2_s0_execution_receipt.json`
18. `pr2_s1_execution_receipt.json`
19. `pr2_s2_execution_receipt.json`
20. `pr2_s3_execution_receipt.json`

Schema minimums:
1. every JSON artifact includes: `phase`, `state`, `generated_at_utc`, `generated_by`, `version`,
2. `pr2_execution_summary.json` includes: `verdict`, `next_gate`, `open_blockers`, `blocker_ids`, `contract_refs`,
3. every state receipt includes:
   - `elapsed_minutes`,
   - `runtime_budget_minutes`,
   - `attributable_spend_usd`,
   - `cost_envelope_usd`,
   - `advisory_ids`.

## 8) Runtime And Cost Budgets (PR2)
Runtime budget:
1. `S0 <= 10 min`
2. `S1 <= 25 min`
3. `S2 <= 20 min`
4. `S3 <= 10 min`
5. Total `<= 65 min`

Cost budget:
1. Expected mode is evidence-first and low incremental spend.
2. If fresh extraction is required, attributable spend must be emitted with explicit envelope and rationale.
3. Unattributed spend is fail-closed (`PR2.B19_UNATTRIBUTED_SPEND`).

## 9) Rerun Discipline
1. Rerun only failed boundary state:
   - inventory/ownership blockers -> `S0`,
   - threshold population blockers -> `S1`,
   - activation/sanity blockers -> `S2`,
   - rollup/verdict blockers -> `S3`.
2. Preserve failed artifacts; do not overwrite without rerun attempt markers when needed.
3. No threshold drift-to-pass without explicit rationale in implementation map and logbook.

## 10) PR2 Definition Of Done Checklist
1. `S0..S3` executed with deterministic artifacts under `runs/`.
2. Runtime and ops/governance active-scope contracts are activatable (`ACTIVE`, no required `TBD`).
3. Activation validators and anti-gaming checks pass.
4. `pr2_execution_summary.json` has `open_blockers=0`.
5. Verdict is `PR3_READY` and `next_gate=PR3_READY`.

## 11) Execution Record
Status:
1. `COMPLETE` (`S0..S3` complete; `PR3_READY` emitted).

Active control root:
1. `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/`
2. Latest pointer:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_latest.json` (`latest_state=S3`).

State closure:
1. `S0` executed from strict upstream:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_s5_execution_receipt.json`.
2. `S0` receipt:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_s0_execution_receipt.json`.
3. `S0` verdict:
   - `PR2_S0_READY`, `open_blockers=0`, `next_state=PR2-S1`.
4. `S1` receipt:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_s1_execution_receipt.json`.
5. `S1` verdict:
   - `PR2_S1_READY`, `open_blockers=0`, `next_state=PR2-S2`.
6. `S2` receipt:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_s2_execution_receipt.json`.
7. `S2` verdict:
   - `PR2_S2_READY`, `open_blockers=0`, `next_state=PR2-S3`.
8. `S3` receipt:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_s3_execution_receipt.json`.
9. `S3` verdict:
   - `PR2_S3_READY`, `open_blockers=0`, `next_state=PR3-S0`, `next_gate=PR3_READY`.
10. PR2 summary:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_execution_summary.json` (`verdict=PR3_READY`, `next_gate=PR3_READY`).

### 11.1 PR2-S0 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR2_S0_READY`, `open_blockers=0` | Entry gate closed cleanly; PR2 can proceed to S1. |
| Upstream continuity | PR1 closure lock was valid and strict | PR2 started from a legal upstream boundary, not a partial state. |
| Inventory scope | `total=36`, `required=34`, `pending_required=9` | Required activation scope is fully enumerated and auditable. |
| Ownership completeness | no orphan pending required rows (`owner_gap=0`) | S1 remediation/closure lanes are deterministic by owner. |
| Deferred optional scope | optional rows routed to later phases (`PR3`/`PR4`) | Deferred scope is explicit and does not dilute PR2 required gates. |
| Runtime and cost posture | `elapsed=0.0 min` (budget `10`), `attributable_spend_usd=0.0` (envelope `2.0`) | S0 remained minute-scale and spend-neutral under evidence-first execution. |
| Advisory continuity | maturity proxy advisory remains explicit | Known semantic caveat is transparent and tracked, not hidden. |

### 11.2 PR2-S1 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR2_S1_READY`, `open_blockers=0` | Contract materialization gate closed cleanly; handoff to S2 is legal. |
| Required contract closure | required `TBD` count reduced to `0` | Active scope is fully populated for activation validation. |
| Measurement binding | throughput and latency surfaces explicitly bound on hot path | S2 can validate real claim surfaces instead of inferred proxies. |
| Calibration readiness | required calibration rows covered (`R006/R007/R010/R022/R023/R024/R025`) | Threshold decisions remain auditable and reproducible. |
| Runtime envelope pin | steady `3000 eps`, burst `6000 eps` pinned | PR2 moved from baseline envelope to production-target envelope. |
| Burst constraint | projected burst under uniform speedup `3568.809582 eps` (gap `2431.190418 eps`) | Burst-shaper proof is required in PR3; no premature burst claim in PR2. |
| Runtime and cost posture | `elapsed=0.0 min` (budget `25`), `attributable_spend_usd=0.0` (envelope `5.0`) | S1 stayed minute-scale and spend-neutral. |

### 11.3 PR2-S2 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR2_S2_READY`, `open_blockers=0` | Activation validation gate closed cleanly; S3 rollup is unblocked. |
| Runtime activatability | all runtime activatability checks passed | Runtime contract is claimable for downstream execution gates. |
| Ops/gov activatability | all ops/gov activatability checks passed | Ops/governance contract is enforceable and complete in active scope. |
| Threshold sanity | all threshold sanity checks passed | Numeric thresholds are logically consistent and bounded. |
| Alert/runbook actionability | no missing owners and no unresolved runbook bindings | Critical alert posture is actionable, not dashboard-only. |
| Anti-gaming posture | non-proxy surfaces + sample-minima consistency + burst-gap routing all passed | PR2 claims remain realistic and non-gamed. |
| Runtime and cost posture | `elapsed=0.0 min` (budget `20`), `attributable_spend_usd=0.0` (envelope `5.0`) | S2 remained minute-scale and spend-neutral. |

### 11.4 PR2-S3 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR2_S3_READY`, `open_blockers=0`, `next_state=PR3-S0` | PR2 closure is complete and handoff boundary is legal. |
| Phase verdict | `PR3_READY`, `next_gate=PR3_READY` | PR2 exits with a deterministic green verdict and no unresolved blockers. |
| Closure checks | `B15..B19` all passed | Activation index, summary, blocker posture, verdict coherence, and spend attribution all closed fail-closed. |
| Evidence completeness | required artifacts are present and readable (`missing=0`, `unreadable=0`) | PR2 closure remains fully auditable without evidence holes. |
| Runtime and cost posture | `elapsed=0.0 min` (budget `10`), `attributable_spend_usd=0.0` (envelope `5.0`) | Final rollup stayed minute-scale and spend-neutral. |
