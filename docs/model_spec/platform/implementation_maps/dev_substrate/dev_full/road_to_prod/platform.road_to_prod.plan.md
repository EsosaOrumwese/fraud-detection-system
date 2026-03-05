# Dev Full Road To Production-Ready Plan (Main)
_As of 2026-03-05_

## 0) Purpose
This is the main execution authority to move `dev_full` from stress-tested wiring to production-ready status under the binding authority:
- `docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md`

This document is not a progress checklist. It is a fail-closed gate program:
1. A phase cannot close because tasks were completed.
2. A phase closes only when gate intent is proven on realistic behavior/load with claimable evidence.
3. Any unresolved mismatch between gate intent and evidence blocks advancement.

## 1) Program Goal
Complete the production-grade mission objective (not toy validation) and declare `dev_full` production-ready within `RC2-S` only when:
1. `G1`, `G2`, `G3A`, `G3B`, and `G4` are all `PASS`.
2. Required evidence packs exist with deterministic paths and readable indexes.
3. Final verdict has `open_blockers=0`.

Mission-level intent that must be true at closure:
1. Platform sustains meaningful load (`steady -> burst -> recovery -> soak`) with SLO posture on correct measurement surfaces.
2. Platform preserves correctness under realistic data messiness (duplicates, replay, out-of-order, skew/hotkeys, join sparsity).
3. Platform is operationally governable (promotion proof, rollback proof, audit answerability, runbook/alert ownership).
4. Platform demonstrates bounded spend and clean idle-safe closure.

## 2) Phase And Gate Closure Sufficiency Standard (Binding)
Every phase and subphase must satisfy all closure tests below before it can be marked complete:
1. **Intent fidelity test**:
   The produced evidence proves the purpose of the gate/phase, not just execution of steps.
2. **Realism test**:
   Evidence is from declared realistic window/cohorts/load profile, using declared measurement surfaces.
3. **Claimability test**:
   Required artifacts, indexes, and verdict files are present/readable and deterministic.
4. **Blocker test**:
   `open_blockers=0` for the closing boundary, or status is explicitly `HOLD_REMEDIATE`.
5. **Anti-toy test**:
   No short-window/proxy-only/waived-low-sample closure is accepted for required claims.

## 3) Current Posture
1. Foundation wiring and control-plane hardening work is already present from prior stress program.
2. Production-ready declaration is not yet closed.
3. Remaining closure focus is data realism, operational certification packs, and go-live rehearsal.

## 4) Phase Ladder (PR0-PR5)

### PR0 - Program Lock And Status Owner Sync
Intent:
1. Establish one authoritative status surface for this road.
2. Pin mission charter identity and active gate map.
3. Materialize initial blocker register for unresolved required `TBD` fields in active scope.
4. Execute detailed state plan in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR0.road_to_prod.md`.

Exit / DoD:
1. Status owner file is pinned and current.
2. Mission charter is present and scoped (`injection_path`, envelope, budgets, windows).
3. Initial blocker register exists with rerun boundaries.
4. No gate progression ambiguity exists between status owner and evidence pack posture.
5. Execution status: `COMPLETE` (`pr0_20260305T1725Z`, verdict `PR1_READY`).

### PR1 - G2 Data Realism Pack Closure
Intent:
1. Close 7-day realism and semantic readiness from actual platform-fed data.
2. Pin decisions for joins, allowlists, IEG minimal graph, and label maturity.
3. Execute detailed state plan in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR1.road_to_prod.md`.

Subphase template:
1. `S0` entry and window pinning.
2. `S1` realism profile measurements.
3. `S2` join coverage and fanout closure.
4. `S3` RTDL allowlist and IEG decisions.
5. `S4` learning maturity and time-causality closure.
6. `S5` deterministic pack rollup and verdict.

Exit / DoD:
1. `G2` data realism pack complete and readable.
2. Required realism decisions pinned.
3. `open_blockers=0` for `G2`.
4. Unknowns are converted to pinned decisions or explicit blockers with rerun boundaries (no silent unknowns).
5. Execution status: `COMPLETE` (`pr1_20260305T174744Z`, verdict `PR2_READY`, `next_gate=PR2_READY`).

### PR2 - Numeric Contract Activation
Intent:
1. Activate required runtime and ops/gov numeric contract sections with no required `TBD`.
2. Ensure every threshold has declared measurement surface, sample minima, and failure path.

Subphase template:
1. `S0` required row inventory and gap map.
2. `S1` threshold population from measured evidence plus policy guardbands.
3. `S2` activation validation and anti-gaming checks.
4. `S3` activation verdict and blocker rollup.

Exit / DoD:
1. Active contract scope has no required `TBD`.
2. Activation verifier passes.
3. Contract activation blockers are zero.
4. Threshold rows are measurement-surface valid and anti-gaming checks pass.

### PR3 - G3A Runtime Operational Certification Pack
Intent:
1. Certify runtime hot-path behavior under `steady -> burst -> recovery -> soak`.
2. Prove runtime drills with claimable artifacts.

Subphase template:
1. `S0` preflight and run binding.
2. `S1` steady profile.
3. `S2` burst profile.
4. `S3` recovery profile.
5. `S4` soak profile plus runtime drills.
6. `S5` pack rollup and verdict.

Exit / DoD:
1. Required runtime metrics present on correct surfaces and pass thresholds.
2. Required runtime drill artifacts complete.
3. `G3A` pack has `open_blockers=0`.
4. Closure demonstrates runtime gate intent (not probe-only or checklist-only pass).

### PR4 - G3B Ops/Gov Operational Certification Pack
Intent:
1. Certify governed promotion corridor, rollback, audit answerability, and governance posture.
2. Close ops/gov cost enforcement slice.

Subphase template:
1. `S0` entry and authority binding.
2. `S1` promotion corridor proof.
3. `S2` rollback drill proof.
4. `S3` audit drill proof.
5. `S4` runbook and alert governance proof.
6. `S5` cost governance closure and pack verdict.

Exit / DoD:
1. Promotion, rollback, audit, and governance artifacts are complete.
2. Ops/gov thresholds pass.
3. `G3B` pack has `open_blockers=0`.
4. Closure demonstrates operational governability under change, not static-document compliance.

### PR5 - G4 Go-Live Rehearsal Mission Pack
Intent:
1. Run full rehearsal mission with controlled incident and controlled change.
2. Close with bounded cost and idle-safe teardown.

Subphase template:
1. `S0` rehearsal entry lock.
2. `S1` sustained operation segment.
3. `S2` burst and recovery segment.
4. `S3` controlled incident drill and recovery.
5. `S4` controlled change and rollback readiness plus audit drill.
6. `S5` cost closure, teardown residual scan, final verdict.

Exit / DoD:
1. Rehearsal events and required drill artifacts complete.
2. Cost-to-outcome and idle-safe closure complete.
3. Final verdict `PASS` with `open_blockers=0`.
4. Final pack proves mission intent end-to-end and is claimable as production-ready within `RC2-S`.

## 5) Fail-Closed Operating Rules
1. No phase advances with unresolved blockers.
2. No certification claim from missing metrics or missing artifacts.
3. No metric claims from wrong measurement surfaces.
4. No run under non-activatable contract rows.
5. No rerun-the-world posture; rerun only declared blocker boundary.
6. No closure from checklist completion alone without gate-intent proof.
7. No state can be marked complete if its human-readable analytical metric digest is missing.

## 6) Rerun Discipline
1. Each blocker record must carry exact rerun boundary.
2. Remediation is accepted only when rerun evidence removes blocker.
3. Historical failed packs remain retained as remediation evidence.

## 7) Forbidden Closure Patterns (Anti-Circle)
1. Marking a phase complete because all substeps ran, while gate-intent evidence remains weak/incomplete.
2. Passing throughput/latency using proxy counters that do not match declared injection path scope.
3. Accepting waived-low-sample posture for required claim boundaries.
4. Declaring readiness with missing mandatory drill bundles.
5. Declaring readiness with unattributed spend or non-clean teardown residuals.

## 8) Execution Rhythm
1. Expand detail only for the active phase/subphase before execution.
2. Keep one status owner updated after every attempt.
3. Append implementation-map and logbook entries at pre-edit and post-edit points.

### 8.1 Human-Readable Metrics Digest Standard (Binding)
For every state attempt (`PASS`, `HOLD_REMEDIATE`, or `FAIL`), publish an analytical digest that a human reviewer can interpret without opening JSON artifacts.

Required digest columns:
1. `Signal`
2. `Observed Value`
3. `Threshold/Expectation`
4. `Status` (`PASS`/`WARN`/`FAIL`)
5. `Interpretation` (why it matters)
6. `Decision/Next Action`

Required digest rows:
1. Gate verdict and blocker count.
2. Core performance/correctness metrics for that state.
3. Runtime budget posture (`elapsed` vs state budget).
4. Cost posture (`attributable_spend_usd` vs envelope; explain near-zero when evidence-first reuse applies).
5. Data/provenance scope (window, injection path, source refs).
6. Caveats/advisories with explicit severity and follow-up boundary.

Mandatory publication surfaces:
1. Phase authority doc (state findings section).
2. Main plan snapshot section for current state.
3. Daily logbook summary entry.

Completion law:
1. If a state digest is missing any required column/row above, the state remains `HOLD_REMEDIATE` for reporting incompleteness.

## 9) Document Completion Rule
This plan's intent is satisfied only when:
1. The mission objective in Section 1 is fully proven by gate outputs.
2. Each phase closure satisfies the sufficiency standard in Section 2.
3. The final production-ready verdict is claimable, auditable, and has `open_blockers=0`.

## 10) Immediate Next Step
1. Start `PR2-S0`: execute numeric contract activation entry lock from completed `PR1` gate outputs.
2. Use `PR1-S5` receipt as immediate upstream authority:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_s5_execution_receipt.json`.
3. Keep Section 11 target status table as the active blocker-routing surface during `PR2` execution.
4. Use the dedicated PR1 authority doc as closed historical source and PR2 authority doc as active execution source:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR1.road_to_prod.md`.

### 10.1 PR1-S1 Findings Snapshot (Readable)
| Signal | Value | Why it matters for PR1 |
| --- | --- | --- |
| S1 verdict | `PR1_S1_READY` | Confirms S1 closure and legal handoff to S2. |
| Open blockers | `0` | No fail-closed blocker carried from S1 into S2. |
| Natural charter-window profile | `rows=37,113,583`, `steady=61.365 eps`, `event_type_count=2` | Baseline behavior is now strictly charter-window measured (no cross-window carry-forward). |
| Pressure cohort contract | duplicate `0.75%`, out-of-order `0.3%`, hotkey top1 `35.0%`, mixed-event types `8` | Required pressure lanes are explicitly derived from injected realism contract evidence, preventing toy-clean closure. |
| Parse errors | `0` | No profile-quality parsing defect carried forward. |
| Envelope candidate (S1) | steady `61.365 eps`, burst `73 eps`, durations `30/5/5/30 min` | S1 candidate is bounded; final numeric pin remains S5 responsibility. |
| Runtime posture (`S1`) | `elapsed_minutes=0.645` vs budget `20` | S1 recompute remained minute-scale under strict charter extraction. |
| Cost posture (`S1`) | `attributable_spend_usd=0.102349` vs envelope `25.0` | S1 spend is explicitly attributable and bounded. |
| Gate checks | `B04=true`, `B05=true`, `B06=true` | Required S1 acceptance checks all passed. |

### 10.2 PR1-S2 Findings Snapshot (Readable)
| Signal | Value | Why it matters for PR1 |
| --- | --- | --- |
| S2 verdict | `PR1_S2_READY` | Confirms legal handoff to S3. |
| Open blockers | `0` | No S2 fail-closed blocker remains. |
| Mandatory joins covered | `4/4` | Required join graph is fully represented in S2 matrix. |
| Highest unmatched rate | `0.00000407` (`J1`) | Well below pinned unmatched cap (`0.001`). |
| Fanout posture | `J1 p95/p99=1.0`, others `1.0` | Within pinned fanout cap (`2.0`). |
| Duplicate-key rates | `0.0` on mandatory joins (canonical identity keys) | No duplicate-key pressure seen in mandatory S2 paths after cardinality-safe keying. |
| `TGT-06` thresholds pinned | `max_unmatched_join_rate=0.001`, `max_fanout_p99=2.0`, `max_duplicate_key_rate_each_side=0.001` | Join/fanout/unmatched contract moved from TBD to pinned values. |
| Runtime posture (`S2`) | `elapsed_minutes=3.185` vs budget `15` | S2 remained inside runtime budget with explicit receipt evidence. |
| Cost posture (`S2`) | `attributable_spend_usd=0.369668` vs envelope `35.0` | S2 spend is explicitly attributable and bounded. |
| Gate checks | `B07=true`, `B08=true`, `B09=true` | S2 acceptance checks all passed. |
| Scope caveat | `none` | S2 evidence is now charter-window aligned; prior cross-window caveat is cleared. |

### 10.3 PR1 Analytical Ledger Snapshot (Standardized)
| Signal | Observed Value | Threshold/Expectation | Status | Interpretation | Decision/Next Action |
| --- | --- | --- | --- | --- | --- |
| `PR1-S2` gate verdict | `PR1_S2_READY`, `open_blockers=0` | `open_blockers=0` | `PASS` | S2 closure is fail-closed clean. | Proceed to `PR1-S3`. |
| Highest unmatched join rate | `0.00000407` (`J1`) | `<= 0.001` | `PASS` | Join loss is materially below cap. | Keep current unmatched cap; monitor in S3/S5 rollup. |
| Max fanout estimate | `1.0` (`J1 p95/p99_est`) | `<= 2.0` | `PASS` | Fanout pressure is comfortably below cap. | Maintain current fanout cap and monitor downstream. |
| Duplicate-key rate (mandatory joins) | `0.0` | `<= 0.001` | `PASS` | No duplicate-key pressure observed on mandatory join paths. | Keep current duplicate-key cap; no remediation now. |
| Runtime budget posture (`S2`) | `elapsed_minutes=3.185` | `<= 15 min` | `PASS` | Runtime evidence is now explicitly claimable. | Keep runtime receipt fields mandatory for all future states. |
| Cost posture (`S2`) | `attributable_spend_usd=0.369668` | `<= 35.0` | `PASS` | Spend evidence is now explicitly attributable. | Keep per-state spend receipts mandatory. |
| Scope/provenance caveat | `none` | Charter-window alignment required | `PASS` | S2 extraction is fully charter-window aligned. | Maintain this strict scope posture for S4/S5. |

### 10.4 PR1-S3 Findings Snapshot (Readable)
| Signal | Observed Value | Threshold/Expectation | Status | Why it matters for PR1 | Decision/Next Action |
| --- | --- | --- | --- | --- | --- |
| S3 verdict | `PR1_S3_READY`, `open_blockers=0` | `open_blockers=0` | `PASS` | Confirms legal handoff to S4. | Proceed to `PR1-S4`. |
| `B10` RTDL scope check | allowlist/denylist emitted and readable | required | `PASS` | Runtime-safe data boundary is explicit, not implied. | Keep as active runtime boundary contract. |
| `B11` IEG scope check | minimal graph pinned (`edge_count=6`) + TTL/state bounds | required | `PASS` | Graph scope is bounded and auditable for G2. | Use this as S4/S5 graph-scope baseline. |
| `B12` lateness-policy check | fail-closed as-of policy pinned; enforceability checks all `true` | required | `PASS` | Time-causality/lateness posture is enforceable, not narrative only. | Carry policy to S4 learning closure and S5 rollup. |
| Runtime posture (`S3`) | `elapsed_minutes=0.656` vs budget `15` | `<= 15` | `PASS` | S3 recompute stayed minute-scale with explicit runtime evidence. | Preserve this execution posture for remaining PR1 states. |
| Cost posture (`S3`) | `attributable_spend_usd=0.046417` vs envelope `10.0` | `<= 10.0` | `PASS` | S3 spend is attributable and bounded even with fresh boundary checks. | Continue spend receipts even on low-spend states. |
| Target closure impact | `TGT-03=PINNED`, `TGT-04=PINNED` | both pinned by PR1-S5 latest | `PASS` | Two mandatory G2 targets are now closed earlier at S3. | Focus S4/S5 on `TGT-05`, `TGT-07`, and final `TGT-02`. |
| Scope caveat | `none` | charter-window alignment required | `PASS` | S3 policy and boundary checks are now charter-window aligned. | Keep charter-as-of binding in downstream states. |

### 10.5 PR1-S4 Findings Snapshot (Readable)
| Signal | Observed Value | Threshold/Expectation | Status | Why it matters for PR1 | Decision/Next Action |
| --- | --- | --- | --- | --- | --- |
| S4 verdict | `PR1_S4_READY`, `open_blockers=0` | `open_blockers=0` | `PASS` | Confirms legal handoff to S5. | Proceed to `PR1-S5` rollup closure. |
| `B13` label maturity check | candidate coverage `1d=0.857648`, `3d=0.57411`, `7d=0.0`; selected lag `3d` | selected lag required with fail-closed coverage policy | `PASS` | `TGT-05` moves from candidate to pinned with measurable maturity semantics. | Keep `3d` lag and carry to S5 pack index. |
| `B14` leakage guardrail check | `m9d=true`, `m9e=true`, `m11e=true`, hard-fail enabled | all true | `PASS` | Learning-time causality is enforceable, not stated-only. | Keep fail-closed guardrail posture unchanged. |
| `B15` monitoring baseline check | baseline status `ACTIVE`; refs `G2/G3A/G3B` non-empty; required metric families present | all true | `PASS` | `TGT-07` is pinned and downstream gates can consume baseline contract. | Carry baseline contract into S5 verdict and PR3/PR4 refs. |
| Runtime posture (`S4`) | `elapsed_minutes=0.015` vs budget `15` | `<= 15` | `PASS` | S4 closure stayed minute-scale. | Preserve this posture for S5. |
| Cost posture (`S4`) | `attributable_spend_usd=0.018179` vs envelope `10.0` | `<= 10.0` | `PASS` | S4 spend is attributable and bounded. | Keep attributable receipts mandatory in S5. |
| Advisory posture | `PR1.S4.AD01_LABEL_TS_PROXY_SEMANTICS` | explicit advisory allowed when documented | `PASS` | Proxy semantics are transparent and auditable (no hidden field assumptions). | Keep migration note active until true `label_available_ts` is available. |

### 10.6 PR1-S5 Findings Snapshot (Readable)
| Signal | Observed Value | Threshold/Expectation | Status | Why it matters for PR1 | Decision/Next Action |
| --- | --- | --- | --- | --- | --- |
| S5 verdict | `PR1_S5_READY`, `open_blockers=0`, `next_state=PR2-S0` | `open_blockers=0` | `PASS` | Confirms legal closure of PR1 phase. | Move to `PR2-S0`. |
| G2 gate verdict | `PASS`, `next_gate=PR2_READY`, `open_blockers=0` | `PASS` + zero blockers | `PASS` | `G2` gate closure is now claimable and auditable. | Treat PR1 as complete. |
| `B16` target set check | `TGT-02..TGT-07` all `PINNED` | all required targets pinned | `PASS` | Removes remaining target incompleteness risk from G2. | Carry this set as immutable baseline for PR2+. |
| `B17` pack/index check | all required S5 rollup artifacts readable | required artifacts present | `PASS` | Deterministic pack/index contract is complete. | Preserve artifact paths for downstream references. |
| `TGT-02` RC2-S activation | steady `61.365 eps`, burst `73 eps`, durations `30/5/5/30`, min processed `37,113,583` | numeric set required at S5 | `PASS` | Converts envelope from candidate into activated numeric contract for PR1 scope. | Carry activated envelope to PR2 contract activation. |
| Runtime posture (`S5`) | `elapsed_minutes=0.001` vs budget `10` | `<= 10` | `PASS` | Rollup closure stayed minute-scale. | Keep this posture for future rollup states. |
| Cost posture (`S5`) | `attributable_spend_usd=0.0` vs envelope `5.0` | `<= 5.0` | `PASS` | Evidence-first rollup remained spend-neutral. | Preserve by-reference rollup policy where applicable. |
| Advisory posture | `PR1.S4.AD01_LABEL_TS_PROXY_SEMANTICS` retained | explicit advisory allowed when documented | `PASS` | Maintains semantic transparency for label maturity pinning basis. | Keep migration note active until schema exposes true availability timestamp. |

## 11) Required TBD Closure Sheet (Binding)
This section defines the mandatory closure routing for unresolved targets in:
1. `docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md` Section 15.1 (open decisions `OD-01..OD-09`).
2. Appendix A.1 workload envelope template required fields.
3. Appendix C.1 monitoring baseline template required fields.

Fail-closed rules for this sheet:
1. Any row marked `Pin Now` must be closed before advancing beyond `PR0`.
2. Any row marked `Pin By G2` must be closed before `PR1-S5` can PASS.
3. Any row marked `Pin By G3A` must be closed before `PR3-S5` can PASS.
4. Any row marked `Pin By G3B` must be closed before `PR4-S5` can PASS.
5. Any row marked `Pin By G4` must be closed before final `PR5-S5` PASS.
6. `Deferred/Out-Of-Scope` is allowed only where explicitly non-required for `dev_full` production-ready claim; otherwise it is a blocker.

As-of snapshot (2026-03-05) from authority scan:
1. Open decisions: `OD-01..OD-09` (9 total).
2. Appendix A.1 template `TBD` fields: 68.
3. Appendix C.1 template `TBD` fields: 129.

### 11.1 Closure Routing Table
| Target ID | Decision/TBD class | Source locus | Close-by target | Owner lane | Closure artifact |
| --- | --- | --- | --- | --- | --- |
| TGT-01 | Injection-path certification policy (`via_IG` vs `via_MSK`) | OD-01 | Pin Now (PR0) | Program owner + run-control | Mission charter + status owner entry |
| TGT-02 | RC2-S envelope numeric set (steady/burst/recovery/soak/replay) | OD-02 + Appendix A.1 envelope rows | Pin By G2 (PR1) | Runtime/perf | Activated workload envelope section |
| TGT-03 | Watermark/allowed-lateness posture | OD-03 + Appendix A.1 late-event rows | Pin By G2 (PR1) | RTDL/data semantics | Late-event policy receipt + threshold row activation |
| TGT-04 | IEG minimal graph scope + TTL/state bounds | OD-04 | Pin By G2 (PR1) | IEG/data semantics | IEG scope decision record + realism pack reference |
| TGT-05 | Label maturity lag definition and enforcement bound | OD-07 + Appendix A.1/C.1 maturity fields | Pin By G2 (PR1) | Learning/truth | Maturity lag decision + causality evidence link |
| TGT-06 | Join/fanout/unmatched-rate required bounds | Appendix A.1 join rows | Pin By G2 (PR1) | Data realism | Join matrix decision output + activated thresholds |
| TGT-07 | Monitoring baseline reference binding (`G2/G3A/G3B refs`) | Appendix C.1 `pack_ref` rows | Pin By G2 (PR1) | Observability | Monitoring baseline ACTIVE/FROZEN header |
| TGT-08 | Runtime threshold families (lag/latency/error/timeout/checkpoint) | Appendix A.1 + Appendix C.1 runtime metric families | Pin By G3A (PR3) | Runtime/perf | G3A scorecard + runtime pack index |
| TGT-09 | Archive sink design and backpressure posture | OD-05 | Pin By G3A (PR3) | Archive/egress | Sink design decision + burst/soak evidence link |
| TGT-10 | Decision explainability minimal schema | OD-06 | Pin By G3B (PR4) | Decision/audit | Explainability contract + audit drill evidence |
| TGT-11 | Promotion observation window and stable-signal set | OD-08 | Pin By G3B (PR4) | Ops/gov | Promotion corridor policy + observation receipt |
| TGT-12 | Cost budgets by gate and mission, with enforcement posture | OD-09 + Appendix A.1/C.1 cost rows | Pin By G3B (PR4) | Cost governance | Gate budget table + enforcement receipt |
| TGT-13 | Ops/gov monitor families owner assignment and numeric thresholds | Appendix C.1 owner/threshold rows | Pin By G3B (PR4) | Ops/gov/observability | Monitoring baseline activated owner table |
| TGT-14 | Final rehearsal-only required rows (if any still pending) | Remaining required TBD in ACTIVE scope | Pin By G4 (PR5) | Program owner | Final ACTIVE/FROZEN validator output |
| TGT-15 | RC2-L stretch rows | Appendix A.1/C.1 RC2-L | Deferred/Out-Of-Scope for dev_full claim | Program owner | Deferred register entry with rationale |

### 11.2 Status Discipline
Allowed status values for each target:
1. `OPEN`
2. `IN_PROGRESS`
3. `PINNED`
4. `WAIVED_TIMEBOXED` (explicit USER approval required)
5. `DEFERRED_OUT_OF_SCOPE` (only for non-required stretch scope)

Closure rule:
1. Required targets cannot remain `OPEN`/`IN_PROGRESS`/`WAIVED_TIMEBOXED` at their close-by gate.
2. Any miss becomes `HOLD_REMEDIATE` with explicit rerun boundary before phase continuation.

### 11.3 Current Target Status Snapshot (PR1-S5)
As-of execution: `pr1_20260305T174744Z`

| Target ID | Current status | Blocking gate | Notes |
| --- | --- | --- | --- |
| TGT-01 | PINNED | PR0 | Injection-path policy pinned: `via_IG` is production claim path; `via_MSK` is hot-path-only scoped claim path. |
| TGT-02 | PINNED | PR1-S5 | S5 finalized and activated RC2-S numeric envelope from measured PR1 profile + cohort contract evidence (`steady=61.365 eps`, `burst=73 eps`, `30/5/5/30 min`). |
| TGT-03 | PINNED | PR1-S5 | S3 pinned lateness policy with fail-closed as-of semantics and enforceability receipt. |
| TGT-04 | PINNED | PR1-S5 | S3 pinned IEG minimal graph scope with explicit TTL/state bounds. |
| TGT-05 | PINNED | PR1-S5 | S4 pinned `label_maturity_lag=3d` from charter-window maturity distribution using explicit `ts_utc` availability proxy semantics and fail-closed selection policy. |
| TGT-06 | PINNED | PR1-S5 | S2 pinned join/fanout/unmatched bounds with explicit thresholds and decision register. |
| TGT-07 | PINNED | PR1-S5 | S4 activated monitoring baseline contract (`status=ACTIVE`) with bound `G2/G3A/G3B` refs and required metric families. |
| TGT-08 | OPEN | PR3-S5 | Runtime threshold families pending G3A runtime cert. |
| TGT-09 | OPEN | PR3-S5 | Archive sink design and backpressure posture pending G3A. |
| TGT-10 | OPEN | PR4-S5 | Decision explainability schema pending G3B audit closure. |
| TGT-11 | OPEN | PR4-S5 | Promotion observation window pending G3B corridor closure. |
| TGT-12 | OPEN | PR4-S5 | Gate and mission cost budgets pending G3B cost governance closure. |
| TGT-13 | OPEN | PR4-S5 | Ops/gov monitor owner+threshold rows pending G3B closure. |
| TGT-14 | OPEN | PR5-S5 | Final rehearsal-only required rows pending G4 rehearsal closure. |
| TGT-15 | DEFERRED_OUT_OF_SCOPE | N/A | RC2-L stretch rows deferred for dev_full production-ready claim. |
