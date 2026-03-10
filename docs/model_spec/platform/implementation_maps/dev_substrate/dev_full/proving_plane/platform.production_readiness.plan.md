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
- `dev_full` is already built and wired. This plan hardens and proves it; it does not redesign it from scratch unless a production-blocking flaw forces a repin.
- The Data Engine remains a black box. The platform works with the data available in the oracle store and through the data-engine interface pack.
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

## Current baseline
The baseline at the start of this plan is:
- `Control + Ingress`: strongest existing plane and current working-platform member
- `RTDL`: wired, partly proven, not yet accepted as a production-ready plane under this method
- `Case + Label`: wired, not yet accepted as a production-ready plane
- `Learning + Evolution / MLOps`: wired on managed surfaces, not yet accepted as a production-ready plane
- `Ops / Gov / Meta`: present, not yet accepted as a production-ready plane

That means the current working platform is:
- `Control + Ingress`

Everything else remains to be proven under this plan.

---

## Phase sequence overview

## Phase 0 - Control + Ingress revalidation
Purpose:
- reconfirm the current working-platform member under the bounded-production method before coupling anything else to it.

Why this phase exists:
- earlier evidence is strong, but the working platform must be established under the exact method this plan will use for every other plane.

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

Definition of done:
- Control + Ingress is reconfirmed as the working-platform base
- any regressions are fixed before Phase 1 starts

---

## Phase 1 - RTDL plane readiness
Purpose:
- prove RTDL on its own production criteria using the minimum real upstream dependencies it requires.

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

Definition of done:
- RTDL is plane-ready
- all known RTDL semantic, replay, freshness, and lineage defects for the bounded run shape are resolved

---

## Phase 2 - Control + Ingress + RTDL coupled-network readiness
Purpose:
- prove the first real working network beyond Control + Ingress.

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

Definition of done:
- `Control + Ingress + RTDL` becomes the working platform
- the production paths introduced by RTDL are marked as working in reflected artifacts

---

## Phase 3 - Case + Label plane readiness
Purpose:
- prove Case + Label on its own production criteria using the already-working upstream decision surfaces.

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

Definition of done:
- Case + Label is plane-ready
- no shadow truth ownership exists between Case Management and Label Store

---

## Phase 4 - Working network + Case + Label coupled readiness
Purpose:
- prove the enlarged network once Case + Label is attached.

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

Definition of done:
- `Control + Ingress + RTDL + Case + Label` becomes the working platform
- case and label paths are promoted into the working network

---

## Phase 5 - Learning + Evolution / MLOps plane readiness
Purpose:
- prove the managed learning corridor on its own production criteria.

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

Definition of done:
- Learning + Evolution / MLOps is plane-ready
- no hidden local or script-only learning path is required for the managed corridor to function

---

## Phase 6 - Working network + Learning coupled readiness
Purpose:
- prove the platform feedback loop once learning is attached to the working network.

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

Definition of done:
- `Control + Ingress + RTDL + Case + Label + Learning + Evolution / MLOps` becomes the working platform
- the runtime-to-learning feedback loop is production-credible

---

## Phase 7 - Operations / Governance / Meta readiness
Purpose:
- prove the platform can be operated, audited, governed, and cost-controlled with the same rigor that it is executed.

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

Definition of done:
- Operations / Governance / Meta is plane-ready
- all working-platform planes are now governable and operable as one system

---

## Phase 8 - Full-platform bounded integrated validation
Purpose:
- validate the entire working platform as one network before authorizing heavier stress.

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

Definition of done:
- the whole platform is bounded-correct
- no unresolved red remains that would invalidate later stress authorization

---

## Phase 9 - Full-platform bounded stress authorization
Purpose:
- determine whether the now-working platform deserves a longer stress or soak run.

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

Definition of done:
- long stress or soak is authorized only if this phase is green
- if not green, the platform is still not production-ready regardless of how clean the wiring looks

---

## Per-phase operating rules
These rules apply to every phase above.

### 1. Fail fast
The run stops as soon as the active boundary has enough evidence to show:
- a correctness defect,
- a semantic defect,
- a path defect,
- a deployment drift issue,
- or an observability defect large enough to invalidate the verdict.

### 2. Fix narrow, rerun narrow
When a phase fails:
- fix the specific defect,
- rerun the smallest legitimate boundary,
- do not rerun the whole platform unless the defect actually spans it.

### 3. Keep the platform AWS-real
The runtime proof must happen on the actual platform surfaces:
- ingress on ingress surfaces,
- RTDL on RTDL runtime,
- learning on managed learning surfaces,
- ops/governance on the real evidence and control surfaces.

### 4. Keep the workspace clean
- durable evidence goes to `runs/`
- temporary diagnosis artifacts do not accumulate in repo root
- notes go to implementation maps and logbook, not ad hoc scratch dumps unless explicitly temporary

### 5. Update reflected artifacts only after proof
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
Proceed with `Phase 0 - Control + Ingress revalidation`.

The purpose of the immediate next action is not to rediscover ingress from scratch. It is to establish the first confirmed member of the working platform under this exact plan so the rest of the platform can be added to a trustworthy base.
