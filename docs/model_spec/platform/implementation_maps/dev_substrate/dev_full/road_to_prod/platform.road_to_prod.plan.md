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
3. Execute detailed state plan in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR2.road_to_prod.md`.

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
5. Execution status: `COMPLETE` (`pr2_20260305T200521Z`, verdict `PR3_READY`, `next_gate=PR3_READY`).

### PR3 - G3A Runtime Operational Certification Pack
Intent:
1. Certify runtime hot-path behavior under `steady -> burst -> recovery -> soak`.
2. Prove runtime drills with claimable artifacts.
3. Execute detailed state plan in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR3.road_to_prod.md`.

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
5. Execution status: `IN_PROGRESS` (`S0` complete; `S1` rerun with fresh evidence and currently `HOLD_REMEDIATE` on threshold breach).

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

Binding rehearsal profile:
PR5 SHALL execute G4 as a single continuous 24-hour wall-clock mission under `RC2-S` using a declared `injection_path` (`via_IG` preferred for end-to-end claimability). The 24-hour duration is mandatory for PR5 claimability: it is not advisory, may not be replaced by a shorter “meaningful window,” and may not be split across multiple runs. `S1` SHALL be interpreted as the entry into this 24-hour continuous mission, with `S2`–`S5` executed as required mission events/artifact closures within the same run. Any underrun, segmentation, or substitute shorter duration SHALL be treated as an explicit blocker and PR5 MUST exit non-PASS / `HOLD_REMEDIATE`.

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
1. `Area`
2. `What was found`
3. `Interpretation`

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
1. Keep the corrected canonical remote `WSP` runtime path for `PR3-S1`; do not revert to synthetic or non-`WSP` pressure.
2. Active `PR3-S1` work is now treated as a **fresh-runtime-identity correction**:
   - keep the oracle-store world fixed,
   - preserve stable event identities,
   - issue fresh runtime `platform_run_id` and `scenario_run_id` per certification attempt,
   - then rerun `PR3-S1` from the same strict upstream boundary.
3. Active S1 blocker to clear remains:
   - `PR3.B10_STEADY_THRESHOLD_BREACH`,
   - but the immediate correction is no longer ingress topology; it is restoring a truthful first-seen-admission steady window.
4. Use strict upstream authority:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/pr3_s0_execution_receipt.json`.
5. Keep Section 11 target status table as the active blocker-routing surface during `PR3` execution.
6. Use this main plan + PR3 authority as active execution sources:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR3.road_to_prod.md`.
7. Keep `platform.PR2.road_to_prod.md` as upstream closure reference only (not active PR3 execution authority).

### 10.1 PR1-S1 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR1_S1_READY`, `open_blockers=0` | S1 closed fail-closed and can legally hand off to S2. |
| Charter scope and baseline | charter window held; baseline `rows=37,113,583`, natural `steady=61.365 eps` | Baseline evidence is representative and claimable for envelope seeding. |
| Stress-lane realism | duplicate/out-of-order/hotkey minima were explicitly bound | S1 avoided toy-clean profiling by preserving pressure cohorts. |
| Runtime and cost posture | `elapsed=0.645 min` (budget `20`), `spend=0.102349 USD` (envelope `25.0`) | State stayed minute-scale with attributable spend. |
| Closure checks | `B04/B05/B06` all `true` | Required S1 controls are complete with no blocker carry-forward. |

### 10.2 PR1-S2 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR1_S2_READY`, `open_blockers=0` | S2 closed cleanly and can hand off to S3. |
| Join realism coverage | mandatory joins covered `4/4`; unmatched `0.00000407`; fanout `1.0`; duplicate-key `0.0` | Join quality is materially better than pinned bounds and free of integrity pressure. |
| Threshold closure | `TGT-06` bounds pinned (`unmatched=0.001`, `fanout=2.0`, `dup-key=0.001`) | Join/fanout policy moved from TBD to explicit standards. |
| Runtime and cost posture | `elapsed=3.185 min` (budget `15`), `spend=0.369668 USD` (envelope `35.0`) | S2 stayed within budget and cost controls. |
| Closure checks | `B07/B08/B09` all `true`; no scope caveat | S2 evidence is charter-aligned and fail-closed complete. |

### 10.3 PR1 Cross-State Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| State continuity | `S1` and `S2` both closed with `open_blockers=0` | PR1 early-state chain is deterministic and legally sequenced. |
| Join-risk posture | unmatched/fanout/duplicate-key metrics all below caps | No immediate remediation pressure on join integrity. |
| Runtime evidence | `S1=0.645 min`, `S2=3.185 min` | Runtime claimability is explicit, not inferred. |
| Cost evidence | `S1=0.102349 USD`, `S2=0.369668 USD` | Cost claimability is explicit and attributable. |
| Scope integrity | no remaining charter-window caveat | Upstream PR1 lanes remain aligned to declared scope. |

### 10.4 PR1-S3 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR1_S3_READY`, `open_blockers=0` | S3 can legally hand off to S4. |
| Boundary governance | RTDL allow/deny controls and IEG bounded scope passed | Runtime/graph scope is explicit and enforceable for G2. |
| Time-causality posture | strict lateness + quarantine route + enforceability checks all passed | Causality policy is enforceable, not narrative-only. |
| Runtime and cost posture | `elapsed=0.656 min` (budget `15`), `spend=0.046417 USD` (envelope `10.0`) | S3 stayed minute-scale and low-cost. |
| Closure impact | `TGT-03` and `TGT-04` pinned | Two required G2 targets closed at S3 boundary. |

### 10.5 PR1-S4 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR1_S4_READY`, `open_blockers=0` | S4 can legally hand off to S5. |
| Label maturity decision | candidate rates `1d/3d/7d = 0.857648/0.57411/0.0`; selected lag `3d` | `TGT-05` is pinned with measurable non-toy maturity semantics. |
| Leakage and monitoring posture | leakage guard checks all true; monitoring baseline active with required families | `TGT-07` is operationally usable for downstream gates. |
| Runtime and cost posture | `elapsed=0.015 min` (budget `15`), `spend=0.018179 USD` (envelope `10.0`) | S4 remained minute-scale and cost-bounded. |
| Advisory | maturity proxy advisory retained explicitly | Semantic caveat remains transparent and tracked. |

### 10.6 PR1-S5 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR1_S5_READY`, `open_blockers=0`, `next_state=PR2-S0` | PR1 closure is legal and deterministic. |
| G2 closure | `PASS`, `next_gate=PR2_READY`; `TGT-02..TGT-07` pinned | Required PR1/G2 targets are complete and claimable. |
| RC2-S activation | steady `61.365 eps`, burst `73 eps`, durations `30/5/5/30`, min processed `37,113,583` | Candidate envelope became active numeric baseline for PR2 handoff. |
| Runtime and cost posture | `elapsed=0.001 min` (budget `10`), `spend=0.0 USD` (envelope `5.0`) | Rollup stayed minute-scale and spend-neutral. |
| Closure checks | `B16/B17/B18/B19` all `true` | No PR1 closure blocker remains. |

### 10.7 PR2-S0 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR2_S0_READY`, `open_blockers=0` | PR2 entry stage closed and can proceed to S1. |
| Scope inventory | required rows `34` with pending `9`; ownership gaps `0` | Required activation scope is explicit and lane-routable. |
| Deferred optional scope | optional rows explicitly routed to later phases | Deferred scope does not contaminate PR2 required closure. |
| Runtime and cost posture | `elapsed=0.0 min` (budget `10`), `spend=0.0 USD` (envelope `2.0`) | S0 remained minute-scale and spend-neutral. |
| Advisory continuity | maturity proxy advisory retained explicitly | Known semantic caveat remained transparent. |

### 10.8 PR2-S1 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR2_S1_READY`, `open_blockers=0` | S1 contract materialization closed cleanly for S2 handoff. |
| Required closure | required `TBD` count is `0`; required contract checks passed | Active contract scope is fully populated and activatable. |
| Envelope pin | steady `3000 eps`, burst `6000 eps` | PR2 target posture moved to production envelope. |
| Burst realism caveat | projected burst `3568.809582 eps` under uniform speedup (gap `2431.190418 eps`) | Burst-shaper proof is explicitly deferred to PR3, avoiding over-claim. |
| Runtime and cost posture | `elapsed=0.0 min` (budget `25`), `spend=0.0 USD` (envelope `5.0`) | S1 remained minute-scale and spend-neutral. |

### 10.9 PR2-S2 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR2_S2_READY`, `open_blockers=0` | S2 activation validation closed and can proceed to S3. |
| Activatability posture | runtime and ops/gov activatability checks passed | Contract activation is enforceable in active scope. |
| Sanity and anti-gaming posture | threshold sanity and anti-gaming checks passed | PR2 claims are bounded to realistic, non-proxy surfaces. |
| Alert/runbook actionability | no missing critical owners or runbook bindings | Ops posture remains actionable, not dashboard-only. |
| Runtime and cost posture | `elapsed=0.0 min` (budget `20`), `spend=0.0 USD` (envelope `5.0`) | S2 remained minute-scale and spend-neutral. |

### 10.10 PR2-S3 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR2_S3_READY`, `open_blockers=0`, `next_state=PR3-S0` | PR2 closure state is legal and complete. |
| Phase verdict | `PR3_READY`, `next_gate=PR3_READY` | PR2 exits with deterministic handoff gate. |
| Closure checks | `B15..B19` all passed | Activation index, summary coherence, blocker posture, and spend attribution all closed fail-closed. |
| Evidence completeness | required artifact set is complete and readable | PR2 closure remains fully auditable with no evidence holes. |
| Runtime and cost posture | `elapsed=0.0 min` (budget `10`), `spend=0.0 USD` (envelope `5.0`) | Final rollup stayed minute-scale and spend-neutral. |

### 10.11 PR3-S0 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR3_S0_READY`, `open_blockers=0`, `next_state=PR3-S1` | PR3 entry/preflight closed cleanly and unblocks steady-window execution. |
| Strict upstream continuity | `PR2_S3_READY` + `PR3_READY` checks all passed from `pr2_20260305T200521Z` | PR3 started from the required upstream boundary without ambiguity. |
| Charter and scope freeze | `via_IG`, `RC2-S`, budget `250.0`, profile minima derived and emitted | Runtime certification scope is explicit and fail-closed before load execution. |
| Measurement surface governance | required runtime metric-surface map emitted (`throughput`, `latency`, `lag`, `checkpoint`, `cost`) | PR3 measurement posture is explicit and non-proxy by construction. |
| Dependency preflight | `8/8` evidence checks passed (`M13`, `M14E`, `M14F`, runbook/owner/policy checks) | Runtime readiness is evidenced with no local orchestration side effects. |
| Target routing posture | `TGT-08` and `TGT-09` set to `IN_PROGRESS` in S0 receipt | G3A critical targets are actively routed with deterministic evidence refs. |
| Runtime and cost posture | `elapsed=0.0 min` (budget `20`), `spend=0.0 USD` (envelope `250.0`) | S0 remained minute-scale and spend-neutral. |

### 10.12 PR3-S1 Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | `PR3_S1_READY`, `open_blockers=0`, `next_state=PR3-S2` | S1 steady certification is now closed on the canonical remote-WSP path. |
| Steady goal vs observed throughput | acceptance target `3000.0 eps`; observed admitted throughput `3003.4222 eps` | The platform now clears the RC2-S steady-rate goal on the authoritative ingress measurement surface. |
| Source-setpoint calibration | generator setpoint `3005.0 eps`; observed admitted `3003.4222 eps` | The load generator needed a small calibrated overdrive to overcome sub-1% open-loop underdelivery while keeping the acceptance contract fixed at `3000 eps`. |
| Measurement surface validity | `IG_ADMITTED_EVENTS_PER_SEC`; covered metric window `180s`; `metric_bin_count=3` | S1 is now judged on settled CloudWatch minute bins rather than partial-bin wall-clock math. |
| Sample minima | bounded steady minimum `540,000` events; observed admitted `540,616` | The bounded-window sample floor is satisfied for this certification state. |
| Latency posture | API Gateway latency `p95/p99` for the same window remained within charter maxima (`<=350 ms`, `<=700 ms`) | Throughput closure did not degrade hot-path latency posture. |
| Error posture | `4xx_total=0`, `5xx_total=0`, `error_rate_ratio=0.0` | S1 closed with a clean transport/admission error surface. |
| Runtime and cost posture | active closure path `221.411s`; no cost-waiver logic used | The state stayed within a minute-scale operational posture and remains compatible with later PR3 cost rollups. |
| Goal-level verdict | S1 is production-credible and closed; PR3 can advance to burst/backpressure proof in `S2` | Further PR3 work now belongs to the next state, not more steady remediation. |

### 10.13 PR3-S1 Runtime-Correction Snapshot (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Problem actual | current `PR3-S1` proof path is not the real `WSP` path | A green rerun on the current path would not be a valid production-readiness claim. |
| WSP runtime reality | actual `WSP` is Python HTTP replay with `stream_speedup`, not Flink transform code | `WSP` must be treated as a replay producer runtime, not a managed Flink lane by assumption. |
| Authority drift | design/runbook surfaces disagree on `WSP` placement (`ECS/Fargate` vs `MSF_MANAGED_PRIMARY`) | Runtime authority must be corrected before S1 can be considered canonical again. |
| Production-grade decision | use the real remote `WSP` path; keep Managed Flink for `IEG/OFP/RTDL` only | This aligns the certification lane with the actual platform hot path. |
| Execution split | `READY` remains required for control compatibility, but steady certification uses window-bounded remote WSP replay | Throughput proof should depend on the emitter hot path, not on synthetic or control-only launch behavior. |
| Real calibration | realistic four-output oracle pace is about `152 eps`, so first-pass `stream_speedup` to target `3000 eps` is about `19.7` | The next run can be calibrated from measured oracle density instead of guesses. |
| Smoke progression | bounded canonical smokes successively exposed wrong subnet posture, missing private `logs` endpoint, and then stale runtime-image behavior | The runtime-correction work is now evidence-led and stripping blockers in the right order. |
| Active boundary | the live ECS task definition still runs the pre-fix image digest, so the latest WSP loader correction is not yet in service | More reruns of the same image would be wasteful and misleading. |
| Immediate consequence | S1 rerun is deferred until the WSP runtime image is refreshed and the bounded smoke is re-cleared | The next correct action is image refresh first, bounded smoke second, rerun third. |

### 10.14 PR3-S1 Fresh-Identity Findings Summary (Readable)
| Area | What was found | Interpretation |
| --- | --- | --- |
| Gate outcome | latest strict rerun `22790499579` returned `HOLD_REMEDIATE`, `open_blockers=4` | S1 remains open after ingress rollout completion. |
| Impact metrics | throughput `2242.2 eps`; `5xx_total=43`; ALB latency `p95=803 ms`, `p99=1113 ms` | The raw numbers are red, but they are not yet the right first-admission truth to certify against. |
| Fleet posture | ingress stayed `32/32` healthy with CPU mostly `14%..26%` and memory `7%..8%` | The front-door fleet is not presenting as saturated. |
| Duplicate dominance | live worker summaries show `admit=12 duplicate=898 quarantine=0` during the window | The lane has drifted into a duplicate-heavy benchmark rather than a fresh-ingest benchmark. |
| Root cause | reruns reused `platform_run_id=platform_20260223T184232Z`; IG dedupe key includes `platform_run_id` and stable `event_id` | IG is correctly honoring idempotency across reruns, which invalidates this window as fresh steady-admission proof. |
| Required correction | keep the same oracle world but issue a fresh runtime `platform_run_id`/`scenario_run_id` per PR3 certification attempt | This restores production-realistic first-seen mission semantics without wiping dedupe state. |
| Next rerun boundary | `PR3-S1` only | The next valid action is tooling correction plus a fresh-identity S1 rerun, not a broader PR3 restart. |

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
| TGT-08 | IN_PROGRESS | PR3-S5 | PR3-S0 bound runtime metric surfaces; PR3-S1 cleared minima/surface/completeness but exposed canonical `WSP` runtime-path drift. Runtime correction has now progressed through subnet/bootstrap fixes and isolated stale-image drift; image refresh plus post-refresh steady proof remain required before TGT-08 can close. |
| TGT-09 | IN_PROGRESS | PR3-S5 | PR3-S0 pinned archive sink/backpressure posture; downstream validation remains scheduled for `S2/S4` after S1 clearance. |
| TGT-10 | OPEN | PR4-S5 | Decision explainability schema pending G3B audit closure. |
| TGT-11 | OPEN | PR4-S5 | Promotion observation window pending G3B corridor closure. |
| TGT-12 | OPEN | PR4-S5 | Gate and mission cost budgets pending G3B cost governance closure. |
| TGT-13 | OPEN | PR4-S5 | Ops/gov monitor owner+threshold rows pending G3B closure. |
| TGT-14 | OPEN | PR5-S5 | Final rehearsal-only required rows pending G4 rehearsal closure. |
| TGT-15 | DEFERRED_OUT_OF_SCOPE | N/A | RC2-L stretch rows deferred for dev_full production-ready claim. |
