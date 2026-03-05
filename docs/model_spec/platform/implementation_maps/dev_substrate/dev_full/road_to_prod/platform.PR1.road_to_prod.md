# Dev Full Road To Production-Ready - PR1 G2 Data Realism Pack Closure
_As of 2026-03-05_

## 0) Purpose
`PR1` closes `G2` data realism and semantic readiness so runtime certification (`PR3/G3A`) is grounded in observed reality, not guessed assumptions.

`PR1` is fail-closed. It cannot pass unless required `Pin By G2` targets are pinned with claimable evidence:
1. `TGT-02` RC2-S envelope numeric set.
2. `TGT-03` watermark/allowed-lateness posture.
3. `TGT-04` IEG minimal graph scope + TTL/state bounds.
4. `TGT-05` label maturity lag and time-causal learning bounds.
5. `TGT-06` join/fanout/unmatched bounds.
6. `TGT-07` monitoring baseline references and activation posture.

## 1) Binding Authorities
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`
2. `runs/dev_substrate/dev_full/road_to_prod/run_control/pr0_20260305T1725Z/pr0_execution_summary.json`
3. `docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md` (`G2` sections)
4. `docs/model_spec/data-engine/interface_pack/` (data-engine boundary contract)

## 2) Scope Boundary
In scope:
1. 7-day realism profile and cohort mix pinning.
2. Joinability/fanout/missingness decisions with explicit bounds.
3. RTDL time-safe allowlist/denylist and late-event policy.
4. IEG minimal graph decision closure for runtime scope.
5. Label maturity and time-causal learning feasibility closure.
6. Monitoring baseline activation refs for downstream gates.
7. Data Realism Pack rollup and `G2` verdict emission.

Out of scope:
1. runtime pressure certification (`steady/burst/recovery/soak`) under `G3A`,
2. ops/governance certification under `G3B`,
3. rehearsal mission under `G4`.

Black-box boundary rule:
1. Treat data engine internals as out-of-scope.
2. Use platform-fed surfaces and contract-exposed artifacts only.

## 3) PR1 Exit Standard (Hard)
`PR1` can close only if all conditions are true:
1. Data Realism Pack is complete and readable.
2. `TGT-02..TGT-07` are all `PINNED`.
3. `G2` verdict is `PASS` with `open_blockers=0`.
4. Downstream references for `PR2`/`PR3` are deterministic and readable.
5. Unknowns are either pinned or converted to explicit blockers with rerun boundaries.

## 4) Capability Lanes (Mandatory PR1 Coverage)
`PR1` execution must explicitly cover all lanes below:
1. Authority/handles lane:
   - bind PR0 summary, G2 authority sections, and boundary contracts.
2. Identity/IAM lane:
   - confirm source artifact access assumptions and reader identity context.
3. Network/runtime lane:
   - preserve `via_IG` claim boundary from PR0 mission charter.
4. Data store lane:
   - define deterministic pack root and durable refs.
5. Messaging lane:
   - map cohort/ingestion surfaces used for realism and joins.
6. Secrets lane:
   - no secret-bearing content in pack docs/artifacts.
7. Observability/evidence lane:
   - emit pack index + verdict + blocker register with deterministic paths.
8. Rollback/rerun lane:
   - every blocker includes exact rerun boundary.
9. Teardown/idle lane:
   - no always-on runtime introduced by PR1 planning/closure.
10. Budget lane:
    - enforce runtime/cost budgets and fail on unexplained overrun.

## 5) Execution Posture (Performance + Cost Discipline)
1. Evidence-first posture:
   - reuse existing valid evidence before scheduling fresh extraction.
2. No rerun-the-world:
   - execute only missing or stale boundary states.
3. Local machine posture:
   - no local orchestration of platform services; only lightweight planning/summarization work.
4. Fail-closed on stale/non-claimable evidence:
   - if source evidence cannot support gate claims, record blocker and rerun boundary.

## 6) PR1 State Plan (`S0..S5`)

### S0 - Entry Lock, 7-Day Charter, Evidence Inventory
Objective:
1. pin one 7-day realism charter and inventory available evidence against it.

Required actions:
1. bind upstream PR0 summary + mission charter.
2. pin `window_start_ts_utc`, `window_end_ts_utc`, `as_of_time_utc`, `label_maturity_lag` candidate set.
3. build evidence inventory matrix (reusable vs stale vs missing).

Outputs:
1. `pr1_entry_lock.json`
2. `pr1_window_charter.json`
3. `pr1_evidence_inventory.json`

Pass condition:
1. charter pinned, inventory complete, and missing sets explicitly declared.

Fail-closed blockers:
1. `PR1.B01_ENTRY_LOCK_MISSING`
2. `PR1.B02_WINDOW_CHARTER_INVALID`
3. `PR1.B03_EVIDENCE_INVENTORY_MISSING`

S0 planning expansion (execution checklist):
1. Authority lock:
   - confirm readability of PR0 summary, PR0 mission charter, G2 authority doc, and interface pack.
2. Charter lock:
   - pin one 7-day window with absolute UTC bounds (`window_start_ts_utc`, `window_end_ts_utc`, `as_of_time_utc`),
   - preserve PR0 injection path scope (`via_IG`) and claim boundaries,
   - declare label maturity lag as candidate set at S0 (final pin at S4).
3. Evidence inventory lock:
   - classify candidate references into `reusable_claimable`, `reusable_context_only`, `stale_or_missing`,
   - require deterministic path + readability + phase relevance for claimable class,
   - map each missing/weak class to planned boundary state (`S1`, `S2`, `S3`, `S4`, or `S5`).
4. Budget/discipline lock:
   - assert evidence-first posture and no rerun-the-world,
   - pin S0 runtime budget conformance.
5. S0 handoff:
   - emit `PR1_S0_READY` receipt only if blockers `B01..B03` are zero.

### S1 - 7-Day Reality Profile And Cohort Derivation
Objective:
1. measure realistic distribution and derive cohort mix from observed platform-fed data.

Required actions:
1. produce 7-day profile for volume/rate/skew/dupes/out-of-order/payload/event-type mix.
2. derive cohort minima for duplicates/out-of-order/hot-key/payload-extremes/mixed event types.
3. generate initial RC2-S envelope candidate from observed profile.

Outputs:
1. `pr1_g2_profile_summary.json`
2. `pr1_g2_cohort_profile.json`
3. `g2_load_campaign_seed.json`

Pass condition:
1. profile is complete, cohort mix is derived from reality, and envelope candidate is claimable.

Fail-closed blockers:
1. `PR1.B04_PROFILE_COVERAGE_INSUFFICIENT`
2. `PR1.B05_COHORT_DERIVATION_MISSING`
3. `PR1.B06_ENVELOPE_CANDIDATE_UNBOUND`

S1 planning expansion (execution checklist):
1. Source lock:
   - use oracle-store/by-ref platform evidence only (no local dataset processing lane),
   - no data-engine run for S1; treat engine as black-box through interface pack boundaries.
2. Charter conformity checks:
   - enforce S0 window bounds exactly (`2026-02-26T00:00:00Z` to `2026-03-05T00:00:00Z`, as-of `2026-03-05T00:00:00Z`),
   - enforce injection-path scope from PR0 (`via_IG` claim boundary),
   - reject artifacts outside charter or outside claim scope.
3. Evidence ingestion plan:
   - ingest by-reference realism/profile artifacts first (`m7_data_profile_summary`, subset manifest, realism window summary),
   - classify each metric as `claimable_now` or `requires_refresh` with reason and blocker code.
4. Cohort derivation plan:
   - derive duplicates/out-of-order/hot-key/payload-extremes/mixed-event-type minima from observed profile,
   - produce cohort composition and expected impact posture for downstream stress lanes.
5. Envelope candidate plan:
   - derive RC2-S candidate rates/durations/sample minima from observed 7-day profile and guardbands,
   - keep candidate numeric set explicitly marked as S1-derived candidate until S5 finalization (`TGT-02` pin).
6. Claimability gates:
   - required metrics must have deterministic refs, readable artifacts, and sufficient sample basis,
   - low-sample/proxy-only rows are advisory unless supported by explicit injected-pressure evidence.
7. S1 outputs quality gates:
   - `pr1_g2_profile_summary.json` must include coverage, skew, duplicate/out-of-order posture, and parse/error posture,
   - `pr1_g2_cohort_profile.json` must include cohort minima + rationale + confidence notes,
   - `g2_load_campaign_seed.json` must include steady/burst/soak candidate + cohort mix linkage.
8. S1 handoff rule:
   - emit `PR1_S1_READY` only when blockers `B04..B06` are zero,
   - otherwise emit fail-closed blocker register with rerun boundary `S1`.

### S2 - Joinability Closure And Bound Pinning
Objective:
1. validate intended join graph behavior and pin bounded decisions.

Required actions:
1. produce join matrix (coverage, unmatched rate, fanout distributions).
2. pin decisions for high-unmatched/high-fanout paths (cap, re-key, defer, or route adjustments).
3. pin required join thresholds for `TGT-06`.

Outputs:
1. `pr1_join_matrix.json`
2. `pr1_join_decision_register.json`

Pass condition:
1. every mandatory join has verdict + decision and required thresholds are pinned.

Fail-closed blockers:
1. `PR1.B07_JOIN_MATRIX_MISSING`
2. `PR1.B08_JOIN_DECISION_GAPS`
3. `PR1.B09_JOIN_THRESHOLDS_UNPINNED`

### S3 - RTDL Allowlist, IEG Scope, And Lateness Policy
Objective:
1. close runtime-safe data surfaces and semantic handling policy.

Required actions:
1. pin `g2_rtdl_allowlist.yaml` and `g2_rtdl_denylist.yaml`.
2. pin IEG minimal graph scope and TTL/state bounds.
3. pin watermark/allowed-lateness handling policy and evidence of enforceability.

Outputs:
1. `g2_rtdl_allowlist.yaml`
2. `g2_rtdl_denylist.yaml`
3. `pr1_ieg_scope_decisions.json`
4. `pr1_late_event_policy_receipt.json`

Pass condition:
1. `TGT-03` and `TGT-04` are pinned and runtime-safe scope is explicit.

Fail-closed blockers:
1. `PR1.B10_RTDL_ALLOWLIST_MISSING`
2. `PR1.B11_IEG_SCOPE_UNPINNED`
3. `PR1.B12_LATENESS_POLICY_UNPINNED`

### S4 - Learning Maturity And Monitoring Baselines
Objective:
1. close time-causal learning boundaries and baseline references for downstream runtime certification.

Required actions:
1. pin label maturity distribution and selected maturity lag.
2. pin learning window specification and leakage guardrail posture.
3. produce monitoring baselines derived from G2 profile.
4. bind baseline refs for downstream `G3A/G3B` chartering.

Outputs:
1. `pr1_label_maturity_report.json`
2. `pr1_learning_window_spec.json`
3. `pr1_leakage_guardrail_report.json`
4. `g2_monitoring_baselines.json`

Pass condition:
1. `TGT-05` and `TGT-07` are pinned with enforceable references.

Fail-closed blockers:
1. `PR1.B13_LABEL_MATURITY_UNPINNED`
2. `PR1.B14_LEAKAGE_GUARDRAIL_FAIL`
3. `PR1.B15_MONITORING_BASELINE_MISSING`

### S5 - Data Realism Pack Rollup And Verdict
Objective:
1. emit deterministic `G2` pack and gate verdict.

Required actions:
1. finalize RC2-S envelope numeric set from PR1 outputs (`TGT-02`).
2. compile Data Realism Pack index and blocker register.
3. emit gate verdict and phase execution summary.

Outputs:
1. `g2_data_realism_pack_index.json`
2. `g2_data_realism_verdict.json`
3. `pr1_blocker_register.json`
4. `pr1_execution_summary.json`
5. `pr1_evidence_index.json`

Pass condition:
1. `TGT-02..TGT-07` all `PINNED`, `G2 PASS`, `open_blockers=0`, `next_gate=PR2_READY`.

Fail-closed blockers:
1. `PR1.B16_TGT_G2_SET_INCOMPLETE`
2. `PR1.B17_PACK_INDEX_MISSING`
3. `PR1.B18_G2_VERDICT_NOT_PASS`
4. `PR1.B19_OPEN_BLOCKERS_NONZERO`

## 7) PR1 Artifact Contract
Deterministic control root:
1. `runs/dev_substrate/dev_full/road_to_prod/run_control/<pr1_execution_id>/`

Required artifacts:
1. `pr1_entry_lock.json`
2. `pr1_window_charter.json`
3. `pr1_evidence_inventory.json`
4. `pr1_g2_profile_summary.json`
5. `pr1_g2_cohort_profile.json`
6. `g2_load_campaign_seed.json`
7. `pr1_join_matrix.json`
8. `pr1_join_decision_register.json`
9. `g2_rtdl_allowlist.yaml`
10. `g2_rtdl_denylist.yaml`
11. `pr1_ieg_scope_decisions.json`
12. `pr1_late_event_policy_receipt.json`
13. `pr1_label_maturity_report.json`
14. `pr1_learning_window_spec.json`
15. `pr1_leakage_guardrail_report.json`
16. `g2_monitoring_baselines.json`
17. `g2_data_realism_pack_index.json`
18. `g2_data_realism_verdict.json`
19. `pr1_blocker_register.json`
20. `pr1_execution_summary.json`
21. `pr1_evidence_index.json`

Schema minimums:
1. every JSON artifact includes: `phase`, `state`, `generated_at_utc`, `generated_by`, `version`,
2. `g2_data_realism_verdict.json` includes: `overall_pass`, `verdict`, `open_blockers`, `blocker_ids`, `next_gate`,
3. `pr1_execution_summary.json` includes: `verdict`, `next_gate`, `open_blockers`, `tgt_status_map`, `evidence_refs`.

## 8) Runtime And Cost Budgets (PR1)
Runtime budget:
1. `S0 <= 10 min`
2. `S1 <= 20 min`
3. `S2 <= 15 min`
4. `S3 <= 15 min`
5. `S4 <= 15 min`
6. `S5 <= 10 min`
7. Total `<= 85 min`

Cost budget:
1. Evidence-first expected incremental spend: minimal/near-zero.
2. If fresh extraction is required, pin spend envelope before run and emit attributable receipt.
3. Unattributed spend is fail-closed (`PR1.B20_UNATTRIBUTED_SPEND`).

## 9) Rerun Discipline
1. Rerun only failed boundary state by blocker id:
   - profile blockers -> `S1`,
   - join blockers -> `S2`,
   - RTDL/IEG/lateness blockers -> `S3`,
   - maturity/baseline blockers -> `S4`,
   - rollup blockers -> `S5`.
2. Preserve failed artifacts and append rerun attempt suffix.
3. No threshold drift-to-pass. Policy changes require explicit rationale in implementation note.

## 10) PR1 Definition Of Done Checklist
1. `S0..S5` executed with deterministic artifacts under `runs/`.
2. Data Realism Pack is complete and readable.
3. `TGT-02..TGT-07` are all `PINNED`.
4. `g2_data_realism_verdict.json` is `PASS`.
5. `pr1_execution_summary.json` has `open_blockers=0`.
6. `next_gate=PR2_READY`.

## 11) Execution Record - `pr1_20260305T174744Z` (`S0-S1`)
State outcomes:
1. `S0 PASS`:
   - upstream lock validated from PR0 (`PR1_READY`),
   - 7-day charter pinned (`2026-02-26T00:00:00Z` to `2026-03-05T00:00:00Z`, as-of `2026-03-05T00:00:00Z`),
   - evidence inventory emitted with future-gap mapping (`S1/S2/S3/S4/S5`),
   - verdict `PR1_S0_READY`, `next_state=PR1-S1`, `open_blockers=0`.
2. `S1 PASS`:
   - source posture remained oracle-store/by-ref only (no data-engine run),
   - profile coverage passed (`B04=true`),
   - cohort derivation passed after alias normalization (`late_out_of_order` -> out-of-order lane, `rare_edge_case` -> payload-extremes lane),
   - envelope candidate remained bounded (`B06=true`),
   - verdict `PR1_S1_READY`, `next_state=PR1-S2`, `open_blockers=0`.

Run-control root:
1. `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/`

Artifacts emitted in this state:
1. `pr1_entry_lock.json`
2. `pr1_window_charter.json`
3. `pr1_evidence_inventory.json`
4. `pr1_s0_execution_receipt.json`
5. `pr1_g2_profile_summary.json`
6. `pr1_g2_cohort_profile.json`
7. `g2_load_campaign_seed.json`
8. `pr1_s1_execution_receipt.json`
