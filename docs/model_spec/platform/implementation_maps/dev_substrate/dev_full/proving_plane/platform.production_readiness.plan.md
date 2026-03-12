# dev_full Platform Production Readiness Plan

## Purpose
This plan defines how `dev_full` will be taken from a correctly wired platform to a production-ready platform.

The method is not to run the whole system for long durations and hope defects reveal themselves. The method is to build a **confirmed working production network** incrementally:

1. prove one plane on its own production criteria,
2. couple that plane to the already-working network,
3. prove the enlarged network and the new paths it introduces,
4. only then promote that plane into the working platform.

At the start of this plan, the only plane treated as materially working is:
- `Control + Ingress`

The target end state is:
- `Control + Ingress`
- `Real-Time Decision Loop (RTDL)`
- `Case + Label Management`
- `Learning + Evolution / MLOps`
- `Operations / Governance / Meta`

all proven individually, all proven in coupling, and all proven as one platform under bounded production-shaped load.

---

## Planning assumptions
- Obey the `AGENTS.md`
- `dev_full` is already built and wired. This plan hardens and proves it; it does not redesign it from scratch unless a production-blocking flaw forces a repin.
- The Data Engine remains a black box. The platform works with the data available in the oracle store and through the data-engine interface pack.
- When a plane depends on understanding the semantics of the incoming data, the agent may inspect only the allowed Data Engine references for understanding:
  - primary contract: `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
  - output inventory and gates: `docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`, `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`
  - allowed build/state context:
    - `docs/model_spec/data-engine/implementation_maps/segment_5B.build_plan.md`
    - `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
    - `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s5.expanded.md`
    - `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
- Those Data Engine docs are for semantic understanding only. They do not change the black-box rule: the platform still consumes the engine through the interface pack and oracle-store outputs, not by editing or re-running engine internals.
- The graphs in `docs/design/platform/dev_full/graph/` are reflections of implemented truth and readiness progress. They are not substitutes for proof.
- All runtime validation is AWS-first or managed-surface-first. Local work is limited to code changes, static analysis, artifact preparation, and documentation.
- No plane is promoted into the working platform unless both the plane and its newly introduced cross-plane paths are production-worthy.

---

## Execution doctrine

### 1. Plane-first, then network-coupled
For each plane, execution has two proof steps:
1. `plane readiness`
2. `coupled-network readiness`

A plane is not added to the working platform after the first step. It is added only after both steps are green.

### 2. Production shape is preserved
Reducing cost must not reduce the production shape.

We will reduce:
- total event count,
- run duration,
- unnecessary always-on compute,
- repeated long reruns.

We will not reduce:
- target steady throughput,
- target burst throughput,
- latency expectations,
- recovery expectations,
- semantic correctness expectations,
- auditability expectations.

### 3. Bounded proof before long stress
No soak or long-duration stress run is allowed until:
- bounded correctness is green,
- bounded stress is green,
- the newly coupled network has no unresolved semantic or operational defects.

### 4. Graphs reflect reality after proof
We do not mark a plane or path as working because it exists on a graph.
We update the graphs only after the proof for that plane or path is complete enough to support the claim.

### 5. Telemetry-first hardening
No phase may begin execution without an explicit telemetry plan for that phase.

Every phase expansion must define, before the first AWS run:
- live logs for the active plane and its immediate dependencies,
- live progress counters for the active plane,
- live boundary-health checks,
- fail-fast stop conditions,
- the minimal hardening artifact set to keep under `runs/`.

The point is to eliminate blind runs and reduce guesswork. If the phase cannot be observed live, the phase is not yet execution-ready.

### 6. Truthful steady-state measurement
When a phase is proving a steady-state envelope, the measurement window must reflect the real steady-state boundary rather than a launcher artifact.

This means:
- the target itself does not move,
- the run shape must remain production-legitimate,
- the measurement start must be attributable to confirmed plane participation rather than raw submission time when those differ materially,
- a measurement correction is valid only if it is explicit, explainable, and repeatable on the same run shape,
- traffic-shape changes that create synchronized-arrival artifacts or otherwise change the boundary are diagnostic tools only, not valid promotion evidence.

### 7. Narrow rerun discipline
Once a phase has one semantically trustworthy baseline, that baseline should be frozen while the remaining ambiguity is removed.

This means:
- do not keep inventing new run shapes to chase a green receipt,
- prefer fixing telemetry, attribution, or a narrow runtime defect first,
- repeat the same truthful baseline to prove repeatability,
- only widen or reshape the run if the current baseline is itself shown to be invalid.

---

## Working platform promotion rule
A plane is added to the working platform only when all of the following are true:
- its component-level production criteria are met,
- its immediate cross-plane paths are met,
- it does not regress already-working planes,
- its bounded correctness run is green,
- its bounded stress run is green,
- the coupled-network validation is green,
- its evidence is explainable, attributable, and auditable.

If any one of those is false, the plane is not part of the working platform yet.

---

## Road map for phase expansion
We do not move through this plan by shamelessly and foolishly creating states within a phase that do not really lead toward the goal of that phase and as a whole this plan.

Instead, the road map is:

1. start at the parent phase in this plan,
2. ask what the goal of that phase is in relation to the goal of this entire plan,
3. ask how that phase goal can actually be accomplished,
4. ask what steps are necessary to accomplish that goal,
5. let those real required steps define the subphases for that phase.

_(Once again, this is not a template but a mindset)_

This means:
- subphases are not forced into a fixed number,
- subphases are not created because a runner or workflow suggests another state,
- subphases are created only because they are necessary to accomplish the goal of the parent phase.

### How each phase is to be expanded
For every phase, the expansion method is:

1. restate the goal of the phase,
2. ask what must be true for that phase goal to be genuinely accomplished,
3. identify the components, paths, and cross-plane relationships that contribute to that goal,
4. identify which of those contributors need their own focused attention,
5. derive the subphases from that real work.

This is important because some phases will contain many components and each component may contribute a unique part to the goal of the phase. They should not be lumped together without consideration just because they live in the same plane.

### Telemetry and metric derivation for subphases
Once the subphases are defined from the real goal of the phase, we then ask:
- what live telemetry is needed to monitor each subphase honestly?
- what metrics are we looking for that actually match the goal of that subphase?
- what progress or red posture would those metrics show?

That telemetry and those metrics should then be added as the subphase ledger for that phase.

### Phase closure rule
Once the goal of the phase is actually accomplished:
- close the phase,
- update the ledger in this plan with what has now been proven,
- then move to the next phase.

The phase is not complete because its subphases were run. The phase is complete only when its goal, in relation to the entire production-readiness plan, has actually been achieved.

---

## Standard run shapes

### Common proof slices
These are the default low-cost but production-legitimate run shapes.

#### Plane correctness slice
Purpose:
- prove the plane works correctly on real runtime surfaces.

Shape:
- `100k to 300k` admitted events
- `2 to 5` minutes wall-clock
- production target throughput retained
- include:
  - common traffic
  - rare-path traffic
  - duplicates
  - late / out-of-order traffic
  - skew / hot-key traffic
  - plane-relevant decision-bearing traffic

#### Coupled-network validation slice
Purpose:
- prove the new plane works when attached to the already-working network.

Shape:
- `500k to 1.5M` admitted events
- `5 to 10` minutes wall-clock
- production target throughput retained
- include:
  - steady segment
  - bounded burst segment
  - bounded recovery segment

#### Stress authorization slice
Purpose:
- prove the enlarged working network deserves longer stress or soak.

Shape:
- `2M to 5M` admitted events
- `10 to 15` minutes wall-clock
- production target throughput retained
- only run after the first two slices are clean.

### Current declared ingress envelope
Unless explicitly repinned, the declared current Control + Ingress production envelope is:
- `3000 steady eps`
- `6000 burst eps`

All bounded readiness runs for the planes that depend on ingress should preserve that envelope.

---

## Common acceptance language
This plan uses these terms consistently.

### Green
The scope being tested met its production criteria at the declared envelope and within the declared run shape.

### Red
The scope being tested failed a production criterion, showed unresolved ambiguity, or produced insufficient evidence to trust the verdict.

### Plane-ready
The plane is green when judged primarily on its own component and intra-plane criteria, using the minimum real upstream dependencies it needs.

### Network-ready
The enlarged working network is green when the newly introduced plane and the already-working planes operate correctly together, including the new cross-plane paths.

### Working platform
The set of planes that have passed both plane-ready and network-ready proof and can therefore be treated as production-credible members of the platform.

---

## Readiness metric ledger
This ledger pins the metric families and target posture the platform is working toward.

It exists to remove “looks good” or “seems fine” reasoning from production-readiness claims. Each metric family here must later be tied to live telemetry and phase evidence.

Rules:
- these targets are the current production-readiness working targets, not permanent universal ceilings,
- they may be tightened by evidence,
- they must not be loosened casually just to get a green verdict,
- where a metric is intentionally fault-injection-dependent, the target applies to healthy bounded runs unless the phase explicitly says otherwise.
- this ledger is intentionally living: as phases progress and new production-readiness-defining metrics are discovered, the ledger must be expanded in place rather than left implicit in notes or run summaries.
- phase expansion work must check whether the current ledger is missing any metric family that became materially necessary to judge the plane or cross-plane path honestly; if yes, that metric must be added before the phase can be considered closed.

### Control + Ingress

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| steady admitted throughput | `>= 3000 eps` | ingress live telemetry + bounded run summary | Phase 0 |
| burst admitted throughput | `>= 6000 eps` | ingress live telemetry + bounded run summary | Phase 0 |
| latency p95 | `<= 350 ms` | ingress live telemetry | Phase 0 |
| latency p99 | `<= 700 ms` | ingress live telemetry | Phase 0 |
| valid-traffic `4xx` | `0` | ingress live telemetry | Phase 0 |
| valid-traffic `5xx` | `0` | ingress live telemetry | Phase 0 |
| duplicate correctness error rate | `0` | dedupe ledger + bounded run summary | Phase 0 |
| admitted-without-publish count | `0` | ingress + Kafka boundary telemetry | Phase 0 |
| publish ambiguity unresolved count | `0` | ingress receipts + Kafka boundary telemetry | Phase 0 |
| bounded recovery time | `<= 180 s` | run summary + live recovery counters | Phase 0 |

### Real-Time Decision Loop (RTDL)

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| CSFB false-ready rate | `0` | RTDL live telemetry + correctness summary | Phase 1 |
| IEG checkpoint age p99 | `<= 2 s` | IEG live telemetry | Phase 1 |
| IEG lag p99 | `<= 2 s` | IEG live telemetry | Phase 1 |
| IEG backpressure incidents | `0` in healthy bounded runs | IEG live telemetry | Phase 1 |
| OFP freshness lag p99 | `<= 2 s` | OFP live telemetry | Phase 1 |
| OFP restart-to-green | `<= 180 s` | OFP recovery telemetry | Phase 1 |
| false missing-feature rate | `0` | OFP + DF boundary telemetry | Phase 1 |
| DL false fail-closed rate | `0` | DL reason breakdown | Phase 1 |
| DF hard fail-closed count | `0` in healthy bounded runs | DF live telemetry | Phase 1 |
| DF quarantine count | `0` in healthy bounded runs unless ambiguity is intentionally injected | DF live telemetry | Phase 1 |
| decision latency p95 | `<= 300 ms` | DF / RTDL live telemetry | Phase 1 |
| decision latency p99 | `<= 600 ms` | DF / RTDL live telemetry | Phase 1 |
| AL duplicate side-effect error rate | `0` | AL live telemetry | Phase 1 |
| DLA append failure count | `0` | DLA live telemetry | Phase 1 |
| DLA replay divergence count | `0` | DLA live telemetry | Phase 1 |
| Archive Writer write error count | `0` | Archive Writer live telemetry | Phase 1 |
| Archive Writer payload mismatch count | `0` | Archive validation telemetry | Phase 1 |

### Case + Label Management

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| CaseTrigger duplicate suppression correctness | `100%` | case/label telemetry + correctness summary | Phase 3 |
| missed trigger rate | `0` for in-scope case-worthy events in bounded runs | CaseTrigger telemetry | Phase 3 |
| case-open success rate | `100%` for valid case-worthy events | Case Management telemetry | Phase 3 |
| duplicate case creation count | `0` | Case Management telemetry | Phase 3 |
| case-open latency p95 | `<= 5 s` | case/label live telemetry | Phase 3 |
| invalid case-state transition count | `0` | Case Management telemetry | Phase 3 |
| append-only timeline violations | `0` | case timeline validation telemetry | Phase 3 |
| label commit success rate | `100%` for valid bounded inputs | Label Store telemetry | Phase 3 |
| label commit latency p95 | `<= 10 s` | Label Store telemetry | Phase 3 |
| duplicate label corruption count | `0` | Label Store telemetry | Phase 3 |
| conflicting-label visibility | `100%` surfaced, `0` silent overwrite | Label Store telemetry | Phase 3 |
| future-label leakage count | `0` | label maturity / readback telemetry | Phase 3 |

### Learning + Evolution / MLOps

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| point-in-time correctness violations | `0` | Databricks dataset validation | Phase 5 |
| future leakage violations | `0` | Databricks dataset validation | Phase 5 |
| dataset manifest completeness | `100%` | OFS / Databricks outputs | Phase 5 |
| dataset build success rate | `100%` for bounded proof windows | Databricks job telemetry | Phase 5 |
| dataset build duration p95 | `<= 30 min` bounded build window | Databricks job telemetry | Phase 5 |
| training success rate | `100%` for bounded proof windows | SageMaker job telemetry | Phase 5 |
| evaluation success rate | `100%` for bounded proof windows | SageMaker job telemetry | Phase 5 |
| training / evaluation reproducibility | within pinned tolerance for repeated bounded basis | SageMaker + MLflow lineage evidence | Phase 5 |
| candidate bundle completeness | `100%` | SageMaker / artifact validation | Phase 5 |
| lineage completeness | `100%` from dataset -> train/eval -> candidate bundle -> active bundle | MLflow / MPR telemetry | Phase 5 |
| promotion evidence completeness | `100%` | MLflow / MPR telemetry | Phase 5 |
| rollback success rate | `100%` in bounded drills | MLflow / MPR telemetry | Phase 5 |
| rollback RTO | `<= 15 min` | rollback drill summary | Phase 5 |
| rollback RPO | `0` model-version ambiguity | rollback drill summary | Phase 5 |
| active-bundle resolution correctness | `100%` | runtime + MLflow / MPR cross-check | Phase 6 |

### Operations / Governance / Meta

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| run identity uniqueness | `100%` | run control telemetry | Phase 7 |
| receipt completeness | `100%` for required receipts | run control / reporter telemetry | Phase 7 |
| evidence readback success | `100%` | evidence readback checks | Phase 7 |
| verdict traceability | `100%` from verdict -> evidence -> run scope | reporter / governance telemetry | Phase 7 |
| mutation violations on governance facts | `0` | governance append telemetry | Phase 7 |
| metric freshness | within declared plane budget, no stale critical dashboards | observability telemetry | Phase 7 |
| critical alert coverage | `100%` for declared failure families | dashboard / alarm validation | Phase 7 |
| unattributed spend | `0` | cost guardrail telemetry | Phase 7 |
| residual non-essential compute after idle | `0` | teardown / residual scan | Phase 7 |
| placeholder handle count | `0` in active runtime path | handle-resolution telemetry | Phase 7 |
| required secret/handle resolution success | `100%` | control/runtime preflight telemetry | Phase 7 |

### Full-platform cross-plane

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| run identity continuity across active planes | `100%` | integrated live telemetry | Phase 8 |
| truth continuity across critical paths | `100%`, no silent handoff break | integrated live telemetry + summaries | Phase 8 |
| timing continuity across critical paths | all active paths within their declared budgets | integrated live telemetry | Phase 8 |
| silent starvation count | `0` | integrated live telemetry | Phase 8 |
| full-platform bounded recovery | `<= 180 s` unless a path declares a tighter budget | integrated recovery telemetry | Phase 8 |
| explainability / audit completeness | `100%` for accepted decisions and promoted bundles in bounded runs | integrated evidence readback | Phase 8 |
| stress authorization posture | no red plane, no red critical path, no invalidating telemetry blind spot | integrated stress summary | Phase 9 |

---

## Current baseline
The baseline now established under this plan is:
- `Control + Ingress`: promoted working-platform member
- `RTDL`: promoted working-platform member after fresh-scope Phase 1 closure on `2026-03-11`
- `Case + Label`: promoted working-platform member after bounded Phase 3 plane closure on `2026-03-11` and coupled Phase 4 closure on `2026-03-12`
- `Learning + Evolution / MLOps`: wired on managed surfaces, not yet accepted as a production-ready plane
- `Ops / Gov / Meta`: present, not yet accepted as a production-ready plane

That means the current working platform is:
- `Control + Ingress + RTDL + Case + Label`

Everything else remains to be proven under this plan.

---

## Phase sequence overview

## Phase 0 - Control + Ingress revalidation
Purpose:
- reconfirm the current working-platform member under the bounded-production method before coupling anything else to it.

Phase expansion document:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.phase0.md`

Why this phase exists:
- earlier evidence is strong, but the working platform must be established under the exact method this plan will use for every other plane.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Control & Ingress Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- steady and burst throughput at the current declared envelope
- p95 and p99 ingress latency
- `4xx` and `5xx` leakage for valid traffic
- duplicate correctness and publish continuity
- recovery time after bounded disturbance

Qualitative proof focus:
- run identity continuity from control into ingress
- deterministic admission, dedupe, and publish behavior
- receipt and quarantine truth that remains reconstructable
- no deployment-drift mismatch between the intended ingress path and the live ingress path

Scope:
- run control / orchestration
- run identity propagation
- World Streamer Producer (WSP)
- API Gateway / ALB edge
- Ingress Lambda / ECS admission shell
- DynamoDB idempotency ledger
- Kafka publish boundary
- receipts / quarantine surfaces

Run shape:
- coupled-network validation slice
- `500k to 1M` events
- `5 to 8` minutes
- `3000 steady / 6000 burst`

Success criteria:
- throughput and latency still satisfy the current declared envelope
- valid traffic does not leak `4xx` or `5xx`
- duplicate handling remains correct
- publish continuity into the event transport boundary is intact
- receipts remain coherent and attributable
- recovery remains within the existing bound
- the steady-state verdict is repeatable on the same truthful run shape rather than dependent on ad hoc reshaping

Telemetry plan:
- live logs:
  - World Streamer Producer (WSP)
  - Ingress Lambda / ECS admission shell
  - API edge and target health events
- live progress counters:
  - admitted rate
  - duplicate rate
  - publish success / retry / ambiguity counts
  - `4xx` / `5xx`
  - p95 / p99 latency
- live boundary health:
  - run-scope continuity from control into ingress
  - ingress dedupe ledger writes
  - Kafka publish continuity and topic movement
- fail-fast triggers:
  - early `5xx` or timeout growth above bounded red threshold
  - duplicate-heavy windows caused by stale run identity
  - admitted-without-publish evidence
  - healthy edge requests with no downstream bus movement
- hardening artifacts:
  - one run manifest
  - one live summary
  - one optional metric snapshot
  - one implementation-note entry

Current closeout posture:
- the semantically trustworthy unsynchronized bounded run shape is the current `Phase 0.B` baseline
- the remaining blocker is proof-boundary stability at the steady admitted-throughput gate, not a currently active ingress semantic defect
- synchronized-start and unstable warmed single-bin probes are diagnostic evidence only and must not become the promotion baseline
- `Phase 0` should close through:
  - telemetry lock on the active ingress path,
  - one frozen truthful steady-state baseline,
  - repeatable green bounded correctness on that same baseline,
  - only then bounded burst / recovery proof
- if the frozen truthful baseline stays red after the measurement boundary is made explicit, the red must be treated as a real capacity or hot-path defect and remediated narrowly before promotion

Definition of done:
- Control + Ingress is reconfirmed as the working-platform base
- any regressions are fixed before Phase 1 starts

---

## Phase 1 - RTDL plane readiness
Purpose:
- prove RTDL on its own production criteria using the minimum real upstream dependencies it requires.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Real-Time Decision Loop (RTDL) plane production-ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- consumer lag and checkpoint age
- feature freshness and restart-to-green time
- decision latency
- fail-closed, quarantine, append failure, replay divergence, and archive write-error rates

Qualitative proof focus:
- context correctness
- feature correctness
- fail-closed only for real insufficiency
- append-only audit and archive truth
- replay, duplicate, and restart safety for RTDL truth surfaces

Scope:
- Context Store Flow Binding (CSFB)
- Identity Entity Graph (IEG)
- Online Feature Plane (OFP)
- Degrade Ladder (DL)
- Decision Fabric (DF)
- Action Layer (AL)
- Decision Log Audit (DLA)
- Archive Writer

Upstream dependencies allowed:
- Control + Ingress
- event transport
- required state stores and evidence surfaces

Run shape:
- plane correctness slice
- `150k to 300k` events
- `3 to 5` minutes
- production ingress envelope retained where applicable

Primary questions:
- does RTDL form correct context and feature truth?
- does it decide correctly and fail closed only for real insufficiency?
- does it append action, audit, and archive truth correctly?
- does restart/replay/duplicate pressure corrupt any RTDL truth surface?

Focus metrics:
- CSFB false-ready rate
- IEG lag / checkpoint age / backpressure
- OFP freshness / feature availability / restart-to-green
- DL false fail-closed rate
- DF fail-closed and quarantine correctness
- AL duplicate-safe outcome commits
- DLA append failure and replay divergence
- Archive Writer payload mismatch and write failures

Semantic references for this phase:
- `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
  - behavioural stream roles
  - join map for behavioural streams
  - time-safe guidance
  - truth-product boundaries
- `docs/model_spec/data-engine/implementation_maps/segment_5B.build_plan.md`
  - upstream arrival realism and civil-time quality expectations for `arrival_events_5B`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s5.expanded.md`
  - arrival-layer validation and gate posture
- `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
  - behavioural stream, overlay, and truth-product realism expectations
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
  - authoritative 6B outputs, coverage, and validation bundle posture

Telemetry plan:
- live logs:
  - Context Store Flow Binding (CSFB)
  - Identity Entity Graph (IEG)
  - Online Feature Plane (OFP)
  - Degrade Ladder (DL)
  - Decision Fabric (DF)
  - Action Layer (AL)
  - Decision Log Audit (DLA)
  - Archive Writer
- live progress counters:
  - current-run participation by component
  - consumer lag and checkpoint age by component
  - OFP freshness / feature-ready counters
  - DL degrade-reason breakdown
  - DF decision / fail-closed / quarantine breakdown
  - AL outcome counts
  - DLA append / unresolved-age posture
  - Archive Writer write counts and error counts
- live boundary health:
  - run-scope adoption in every RTDL worker
  - behavioural-stream topics moving
  - OFP materializing run-scoped features
  - DLA and archive stores receiving current-run writes
- fail-fast triggers:
  - no current-run RTDL participation after bounded warm window
  - lag/checkpoint age crossing early red bounds
  - OFP freshness or feature readiness staying dark
  - DF fail-closed or quarantine spiking from a healthy upstream window
  - DLA append failures or replay divergence appearing early
- hardening artifacts:
  - one run manifest
  - one live summary
  - one optional RTDL metric snapshot
  - one implementation-note entry

Definition of done:
- RTDL is plane-ready
- all known RTDL semantic, replay, freshness, and lineage defects for the bounded run shape are resolved

---

## Phase 2 - Control + Ingress + RTDL coupled-network readiness
Status:
- closed green by completion inside `Phase 1.B` and `Phase 1.C`

Planning note:
- this phase's goal was satisfied by the fresh-scope RTDL promotion proof that closed on `2026-03-11`
- no separate standalone rerun is required here, because the coupled-network validation already became the evidence used to promote `Control + Ingress + RTDL` into the working platform

Purpose:
- prove the first real working network beyond Control + Ingress.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> The critical cross-plane paths`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- ingress throughput and latency under live RTDL consumption
- RTDL lag, decision latency, and append/archive integrity under real admitted pressure
- bounded recovery time for the combined network

Qualitative proof focus:
- Control -> Ingress identity continuity
- Ingress -> Event Bus publication continuity
- Event Bus -> RTDL truth continuity
- no false-green caused by downstream starvation or stale run scope

Scope:
- existing Control + Ingress working platform
- full RTDL plane
- cross-plane paths:
  - Control -> Ingress
  - Ingress -> Event Bus
  - Event Bus -> RTDL
  - RTDL internal hot path
  - RTDL audit / archive path
  - RTDL degrade / recovery path

Run shape:
- coupled-network validation slice
- `750k to 1.5M` events
- `6 to 10` minutes
- `3000 steady / 6000 burst`

Primary questions:
- does the combined network remain stable at the current envelope?
- does ingress remain green when RTDL is actually consuming and deciding?
- does RTDL remain semantically correct under real admission pressure?
- do the new paths preserve run identity, truth continuity, and timing continuity?

Telemetry plan:
- live logs:
  - ingress edge and admission shell
  - RTDL workers with emphasis on DF, OFP, DLA
- live progress counters:
  - admitted rate vs RTDL current-run participation
  - ingress latency/error posture
  - RTDL lag / checkpoint / decision counters
  - DLA append and archive rates
- live boundary health:
  - Control -> Ingress run identity continuity
  - Ingress -> Event Bus publication continuity
  - Event Bus -> RTDL consumption continuity
- fail-fast triggers:
  - healthy ingress with dark RTDL participation
  - RTDL red despite healthy bus movement and healthy ingress
  - evidence of stale run scope on either side of the boundary
- hardening artifacts:
  - one run manifest
  - one coupled-network summary
  - one optional cross-plane metric snapshot
  - one implementation-note entry

Definition of done:
- `Control + Ingress + RTDL` becomes the working platform
- the production paths introduced by RTDL are marked as working in reflected artifacts

---

## Phase 3 - Case + Label plane readiness
Purpose:
- prove Case + Label on its own production criteria using the already-working upstream decision surfaces.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Case & Label Management Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- trigger precision and recall
- case-open and case-transition latency
- duplicate case-creation rate
- label commit latency
- label idempotency and conflicting-label visibility

Qualitative proof focus:
- correct escalation from decision truth to case intent
- append-only case timeline truth
- append-only label truth
- strict truth ownership between CaseTrigger, Case Management, and Label Store
- no future-label leakage

Scope:
- CaseTrigger
- Case Management (CM)
- Label Store (LS)

Upstream dependencies allowed:
- the working platform from Phase 2
- required truth stores and evidence surfaces

Run shape:
- plane correctness slice
- `100k to 250k` relevant decision-bearing events
- duration driven by sufficient case-worthy volume rather than raw ingress alone
- production envelope retained for upstream ingress and RTDL

Primary questions:
- do the right decisions create the right case intents?
- are duplicate case creations prevented?
- is case timeline truth append-only and reconstructable?
- are labels committed as authoritative truth with proper maturity and provenance?

Focus metrics:
- CaseTrigger precision / recall / duplicate suppression
- case-open latency and case creation idempotency
- append-only timeline integrity
- label commit latency and label idempotency
- conflicting label visibility
- future-label leakage

Semantic references for this phase:
- `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
  - truth products
  - `s4_event_labels_6B`
  - `s4_flow_truth_labels_6B`
  - `s4_flow_bank_view_6B`
  - `s4_case_timeline_6B`
  - join map from RTDL outputs toward truth products
- `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
  - truth-label and case-timeline realism expectations
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
  - authoritative case and label output surfaces and validation posture

Telemetry plan:
- live logs:
  - CaseTrigger
  - Case Management (CM)
  - Label Store (LS)
  - immediate RTDL publishers feeding them
- live progress counters:
  - trigger intake counts
  - case-open counts
  - case-transition counts
  - label pending / accepted / rejected counts
  - duplicate suppression and conflict counters
- live boundary health:
  - RTDL -> CaseTrigger event movement
  - case timeline writes
  - label-store commits and readback
  - run-scope continuity into case/label outputs
- fail-fast triggers:
  - case/label workers healthy but zero current-run participation
  - duplicate case creation or duplicate label corruption
  - missing case timeline writes for valid case-worthy traffic
  - conflicting labels being silently overwritten
- hardening artifacts:
  - one run manifest
  - one case/label live summary
  - one optional case/label metric snapshot
  - one implementation-note entry

Definition of done:
- Case + Label is plane-ready
- no shadow truth ownership exists between Case Management and Label Store

Status:
- closed green on `2026-03-11`

Closure metrics:
- closure scope `phase3_case_label_20260311T142813Z`
- `observed_admitted_eps = 3046.783`
- `admitted_request_count = 182807`
- `4xx = 0`
- `5xx = 0`
- `latency_p95_ms = 48`
- `latency_p99_ms = 55`
- CaseTrigger / Case Management / Label Store integrity deltas all clean on the bounded slice
- promoted upstream base scored `PASS`

---

## Phase 4 - Working network + Case + Label coupled readiness
Purpose:
- prove the enlarged network once Case + Label is attached.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Case & Label Management Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> The critical cross-plane paths`

Quantitative proof focus:
- decision-to-case latency
- case-to-label latency
- case and label throughput under real upstream pressure
- starvation count across RTDL -> Case/Label boundaries

Qualitative proof focus:
- RTDL outputs remain usable as operational truth
- duplicate-safe case and label formation under load
- case and label lineage remain linked to upstream RTDL truth
- no regression of the already-working `Control + Ingress + RTDL` network

Scope:
- working platform from Phase 2
- Case + Label plane
- cross-plane paths:
  - RTDL -> CaseTrigger
  - CaseTrigger -> Case Management
  - Case Management -> Label Store
  - RTDL / Case / Label auditability path
  - label truth path into future learning use

Run shape:
- coupled-network validation slice
- `500k to 1M` admitted events
- enough case-worthy traffic to generate meaningful case and label volumes
- production envelope retained for upstream ingress and RTDL

Primary questions:
- does the network still hold when operational review truth is introduced?
- do cases and labels remain timely, duplicate-safe, and auditable under load?
- does RTDL output remain usable downstream rather than merely technically present?

Telemetry plan:
- live logs:
  - RTDL publishers into CaseTrigger
  - CaseTrigger
  - Case Management
  - Label Store
- live progress counters:
  - decision-to-case counts and latency
  - case-to-label counts and latency
  - starvation counters across RTDL -> case/label boundaries
- live boundary health:
  - RTDL outputs producing case-worthy traffic
  - case truth and label truth remaining linked to upstream decision truth
- fail-fast triggers:
  - RTDL healthy but case/label dark
  - case activity without label-store truth
  - regressions in RTDL latency or fail-closed posture caused by the new coupling
- hardening artifacts:
  - one run manifest
  - one coupled-network summary
  - one optional cross-plane snapshot
  - one implementation-note entry

Definition of done:
- `Control + Ingress + RTDL + Case + Label` becomes the working platform
- case and label paths are promoted into the working network

---

## Phase 5 - Learning + Evolution / MLOps plane readiness
Purpose:
- prove the managed learning corridor on its own production criteria.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes Learning & Evolution Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- dataset build duration and success
- leakage violations
- train/eval duration and success
- candidate bundle completeness
- promotion evidence completeness
- rollback success and rollback RTO/RPO

Qualitative proof focus:
- authoritative runtime and label truth as the only learning basis
- point-in-time correctness
- lineage completeness from dataset to candidate bundle
- deterministic active-bundle resolution through the managed corridor
- no hidden local or script-only path making learning appear healthy

Scope:
- `Databricks (Offline Feature Plane / OFS)`
- `SageMaker (Model Factory / MF)`
- `MLflow (Model Promotion and Registry / MPR)`

Dependencies allowed:
- working platform from Phase 4 as source of runtime and label truth
- managed learning surfaces
- required evidence and registry surfaces

Run shape:
- bounded learning slice, not a giant corpus replay
- enough authoritative runtime truth and label truth to exercise:
  - dataset build semantics
  - train/eval lineage
  - candidate bundle production
  - promotion / rollback / active-bundle resolution
- typical starting scale:
  - `100k to 500k` labeled rows
  - bounded build and train/eval windows

Primary questions:
- are datasets built from authoritative runtime and label truth only?
- is point-in-time correctness preserved?
- does SageMaker train/eval from the right basis?
- does MLflow provide deterministic active-bundle resolution, promotion evidence, and rollback discipline?

Focus metrics:
- dataset build success / duration / leakage violations
- manifest completeness and fingerprint stability
- training / evaluation success and bounded duration
- bundle completeness and provenance completeness
- promotion evidence completeness
- rollback success and rollback RTO / RPO

Semantic references for this phase:
- `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
  - truth-product boundaries
  - time-safe guidance
  - no-PASS-no-read gate posture
- `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`
  - gate verification and instance-proof posture for authoritative engine outputs
- `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
  - labelled runtime truth expectations and downstream training/evaluation suitability
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
  - 6B validation bundle and `_passed.flag` as world-level learning-read gates

Telemetry plan:
- live logs:
  - Databricks job output for the Offline Feature Plane (OFS)
  - SageMaker training / evaluation job logs for the Model Factory (MF)
  - MLflow / Model Promotion and Registry (MPR) promotion and rollback events
- live progress counters:
  - dataset row counts and build stage progress
  - train/eval job state and durations
  - candidate bundle creation progress
  - promotion / rollback counts and state
- live boundary health:
  - authoritative dataset basis present and gated
  - label truth available with maturity semantics
  - active-bundle resolution present and readable
- fail-fast triggers:
  - point-in-time or leakage violation detected
  - train/eval running on non-authoritative dataset basis
  - promotion attempt without complete lineage
  - rollback path unavailable or unresolved
- hardening artifacts:
  - one run manifest
  - one learning/MLOps live summary
  - one optional lineage snapshot
  - one implementation-note entry

Definition of done:
- Learning + Evolution / MLOps is plane-ready
- no hidden local or script-only learning path is required for the managed corridor to function

---

## Phase 6 - Working network + Learning coupled readiness
Purpose:
- prove the platform feedback loop once learning is attached to the working network.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes Learning & Evolution Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> The critical cross-plane paths`

Quantitative proof focus:
- bounded dataset-build, train/eval, and promotion timings within the same proof window
- active-bundle resolution correctness at runtime
- rollback execution within declared bounds

Qualitative proof focus:
- runtime-to-label-to-learning truth continuity
- learning-to-runtime feedback continuity
- replay-to-dataset correctness
- no drift between promoted bundle truth and runtime decision authority

Scope:
- working platform from Phase 4
- managed learning corridor from Phase 5
- cross-plane paths:
  - RTDL + Label truth -> Learning
  - Learning -> Registry / Promotion
  - Registry -> RTDL feedback
  - rollback path
  - replay-to-dataset path

Run shape:
- coupled-network validation slice for runtime
- bounded learning execution windows for dataset build, train/eval, and promotion mechanics
- no soak yet

Primary questions:
- does the enlarged network preserve truth continuity from runtime to label to dataset to bundle to active runtime?
- can the platform explain which dataset and bundle influenced a runtime decision?
- can it roll back without ambiguity?

Telemetry plan:
- live logs:
  - Databricks / SageMaker / MLflow plus the runtime consumer of active bundle truth
- live progress counters:
  - dataset-build / train-eval / promotion timing
  - active-bundle resolution status
  - rollback timing and success
- live boundary health:
  - runtime-to-label-to-dataset continuity
  - promoted bundle visible to runtime
  - rollback path restoring prior active truth
- fail-fast triggers:
  - active bundle not matching promoted truth
  - runtime cannot resolve the managed bundle
  - learning lineage complete on paper but unreadable in runtime
- hardening artifacts:
  - one run manifest
  - one coupled-network summary
  - one optional runtime/learning lineage snapshot
  - one implementation-note entry

Definition of done:
- `Control + Ingress + RTDL + Case + Label + Learning + Evolution / MLOps` becomes the working platform
- the runtime-to-learning feedback loop is production-credible

---

## Phase 7 - Operations / Governance / Meta readiness
Purpose:
- prove the platform can be operated, audited, governed, and cost-controlled with the same rigor that it is executed.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Operations / Governance / Meta layer production-ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- receipt completeness
- evidence readback success
- alert coverage and metric freshness
- cost attribution completeness
- residual non-essential compute after idle/teardown

Qualitative proof focus:
- exact run reconstruction
- verdict traceability back to evidence
- drift detection before false certification
- safe idle and restart posture
- governed, attributable, and bounded operational behavior

Scope:
- run control and receipts
- reporter / scorecard / rollup
- governance append surfaces
- evidence bucket and path discipline
- dashboards / metrics / alarms
- budget and cost guardrails
- idle / teardown / residual scan
- identity / handles / secrets / SSM posture
- drift detection

Run shape:
- bounded operational proof on top of the working platform from Phase 6
- no need for giant data volume; focus is correctness, coverage, and operational usefulness

Primary questions:
- can runs be reconstructed exactly?
- can verdicts be justified from evidence?
- can drift be detected before false certification happens?
- is spend attributable and controllable?
- can the platform safely idle and restart?

Telemetry plan:
- live logs:
  - run-control and reporter surfaces
  - governance append / evidence write surfaces
  - teardown / residual scan outputs
- live progress counters:
  - receipt and evidence emission counts
  - dashboard freshness
  - alert fire / clear counts
  - attributable spend views
  - residual compute counts
- live boundary health:
  - exact run reconstruction possible from current-run evidence
  - active drift checks reading the same runtime surfaces the platform actually uses
  - idle/teardown actions visible and reversible
- fail-fast triggers:
  - missing run receipts
  - evidence holes on active run
  - unattributed spend during active proof
  - drift detected between live runtime and declared active path
- hardening artifacts:
  - one run manifest
  - one ops/gov live summary
  - one optional evidence/compliance snapshot
  - one implementation-note entry

Definition of done:
- Operations / Governance / Meta is plane-ready
- all working-platform planes are now governable and operable as one system

---

## Phase 8 - Full-platform bounded integrated validation
Purpose:
- validate the entire working platform as one network before authorizing heavier stress.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> The critical cross-plane paths`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- bounded integrated throughput, latency, lag, recovery, and error posture across the full network
- bounded integrated case, label, learning, and governance timings where relevant

Qualitative proof focus:
- full-platform truth continuity
- full-platform timing continuity
- full-platform explainability and auditability
- no hidden handoff defect across any active plane boundary

Scope:
- all planes
- all critical cross-plane paths
- full-platform run identity, truth continuity, timing continuity, and recovery continuity

Run shape:
- coupled-network validation slice at full working-platform scope
- `500k to 1.5M` admitted events where runtime-serving paths apply, plus bounded learning and governance activity in the same proof window
- bounded burst and recovery segments
- learning and ops/governance actions executed within the same bounded proof story where relevant

Primary questions:
- does the full platform behave as one coherent production system?
- are there any hidden handoff defects that only appear once all planes are active?
- is the platform explainable and auditable across the full run story?

Telemetry plan:
- live logs:
  - active-plane logs across all working-platform planes
  - operator-facing governance and evidence surfaces
- live progress counters:
  - ingress, RTDL, case/label, learning, and ops/gov summaries in one watch surface
  - cross-plane path health and timing continuity
- live boundary health:
  - all critical cross-plane paths materially participating on the same run
  - no plane appears green because another plane stopped doing real work
- fail-fast triggers:
  - any active plane dark while upstream is hot
  - any critical cross-plane path loses run identity or truth continuity
  - observability/evidence defects large enough to invalidate the integrated verdict
- hardening artifacts:
  - one run manifest
  - one integrated live summary
  - one optional whole-platform metric snapshot
  - one implementation-note entry

Definition of done:
- the whole platform is bounded-correct
- no unresolved red remains that would invalidate later stress authorization

---

## Phase 9 - Full-platform bounded stress authorization
Purpose:
- determine whether the now-working platform deserves a longer stress or soak run.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- latency tails under widened pressure
- fail-closed, quarantine, lineage, case, label, learning, and ops metrics under bounded full-platform stress
- recovery behavior under widened stress

Qualitative proof focus:
- the full platform remains semantically trustworthy under the widened pressure window
- outputs remain meaningful, explainable, and auditable
- no plane only appears green because another plane silently stopped doing real work

Scope:
- full platform under the stress authorization slice

Run shape:
- `2M to 5M` admitted events
- `10 to 15` minutes
- production ingress envelope retained
- bounded burst and recovery segments preserved

Primary questions:
- does the full platform hold at production shape when the pressure window is widened?
- do latency tails, fail-closed rates, lineage completeness, case/label throughput, learning lineage, and ops surfaces remain within bounds?

Telemetry plan:
- live logs:
  - all active planes with emphasis on the currently tightest bottlenecks
- live progress counters:
  - full-platform latency tails
  - fail-closed / quarantine / lineage / case / label / learning / governance counters
  - recovery counters during widened pressure
- live boundary health:
  - full-platform participation remains real under widened stress
  - no critical path is silently bypassed or starved
- fail-fast triggers:
  - clear early miss of target envelope
  - tail latency or error posture already beyond recoverable bound
  - a critical plane stops materially participating
- hardening artifacts:
  - one run manifest
  - one stress live summary
  - one optional stress metric snapshot
  - one implementation-note entry

Definition of done:
- long stress or soak is authorized only if this phase is green
- if not green, the platform is still not production-ready regardless of how clean the wiring looks

---

## Per-phase operating rules
These rules apply to every phase above.

### 1. Telemetry before execution
No phase or phase subsection may execute until its telemetry plan is pinned and materially available:
- log tail,
- live counters,
- boundary-health checks,
- fail-fast conditions.

### 2. Fail fast
The run stops as soon as the active boundary has enough evidence to show:
- a correctness defect,
- a semantic defect,
- a path defect,
- a deployment drift issue,
- or an observability defect large enough to invalidate the verdict.

### 3. Fix narrow, rerun narrow
When a phase fails:
- fix the specific defect,
- rerun the smallest legitimate boundary,
- do not rerun the whole platform unless the defect actually spans it.

### 4. Keep the platform AWS-real
The runtime proof must happen on the actual platform surfaces:
- ingress on ingress surfaces,
- RTDL on RTDL runtime,
- learning on managed learning surfaces,
- ops/governance on the real evidence and control surfaces.

### 5. Keep the workspace clean
- durable evidence goes to `runs/`
- temporary diagnosis artifacts do not accumulate in repo root
- notes go to implementation maps and logbook, not ad hoc scratch dumps unless explicitly temporary

### 6. Update reflected artifacts only after proof
After a phase is complete, update as needed:
- network graph reflections,
- readiness reflections,
- implementation notes,
- logbook.

---

## What this plan deliberately avoids
- treating wiring as evidence of readiness
- using giant expensive runs to discover basic correctness defects
- lowering throughput to make a verdict easier to achieve
- promoting a plane because it exists rather than because it is proven
- treating the graph as the platform
- treating helper scripts as the real managed runtime
- running soak before bounded correctness and bounded stress are clean

---

## Immediate next action
Proceed with `Phase 5 - Learning + Evolution / MLOps plane readiness`.

`Phase 4` closed the enlarged `Control + Ingress + RTDL + Case + Label` working network on `2026-03-12`, so the immediate purpose now shifts to proving the managed learning corridor on its own production criteria using authoritative Phase 4 runtime and label truth only.

Execution order now is:
1. pin the live Phase 5 telemetry set and fail-fast conditions across Databricks / OFS, SageMaker / MF, and MLflow / MPR,
2. verify that the managed learning corridor is reading only authoritative runtime and label truth from the promoted working platform,
3. run the smallest bounded learning slice that proves dataset build, train/eval, bundle lineage, and promotion / rollback discipline on the real managed surfaces,
4. only then decide whether the learning plane is green or remediation must remain open.
