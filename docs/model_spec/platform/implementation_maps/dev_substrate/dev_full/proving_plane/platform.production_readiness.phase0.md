# Phase 0 - Control + Ingress Revalidation

## Why this document exists
This document expands `Phase 0` from:

- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.plan.md`

It does not create subphases because a fixed number looks tidy. It derives the subphases from the actual goal of `Phase 0`.

## Authority used for this phase expansion
Primary authority for this document:

1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.plan.md`

Supporting reflections only:

1. `docs/design/platform/dev_full/graph/readiness/dev_full_platform_network_production_ready_current_v0.mermaid.mmd`
2. `docs/design/platform/dev_full/graph/readiness/dev_full_platform_resources_production_ready_current_v0.mermaid.mmd`
3. `docs/design/platform/dev_full/graph/readiness/dev_full_control_ingress_readiness_delta_current_v0.mermaid.mmd`

Not used as authority for this phase expansion:

- historical `M*` build-phase decomposition
- `road_to_prod` phase mechanics
- older workflow-driven state sequences

## Parent phase goal
The goal of `Phase 0` is to reconfirm that `Control + Ingress` is a genuinely production-ready working-platform base under the proving method now in force.

That means:

1. it must be proven on AWS, not assumed from old evidence,
2. it must be observable live while it is being tested,
3. it must still meet the currently declared envelope:
   - `3000 steady eps`
   - `6000 burst eps`
4. it must still satisfy the qualitative production-readiness meaning already discussed in `platform.production_readiness.md`,
5. it must be trustworthy enough to serve as the base network to which `RTDL` will later be coupled.

## What must be true for the phase goal to be genuinely accomplished
`Phase 0` is only genuinely complete if all of the following are true:

1. the live `Control + Ingress` path being exercised is the intended one,
2. control truth and ingress truth remain continuous under a fresh bounded run,
3. valid traffic is admitted, deduplicated, published, and receipted deterministically,
4. the declared throughput, latency, and recovery posture still hold,
5. the plane is explainable enough that later problems in `RTDL` can be attributed to `RTDL` and not to unresolved ingress defects,
6. the confirmed production-ready network and resource graphs remain truthful after revalidation.

## Contributors to the phase goal
The phase goal depends on distinct contributors:

1. control authority and run identity continuity,
2. World Streamer Producer (WSP) replay discipline,
3. ingress front-door and admission behavior,
4. dedupe and publish continuity,
5. receipts, quarantine, and evidence continuity,
6. bounded recovery behavior,
7. live operator visibility during the run.

These contributors do not all require the same work. That is why the subphases are derived from them instead of from a fixed template.

## Derived subphases

### Phase 0.A - Telemetry and preflight truth
Goal:
- make the active `Control + Ingress` boundary visible enough that later bounded runs are not blind.

This subphase must accomplish:

1. identify the exact live boundary that will be exercised,
2. pin the live telemetry needed for the phase,
3. pin the fail-fast conditions that should stop a bad run early,
4. confirm the minimum preflight truth needed before any run starts.

### Telemetry sub-ledger for Phase 0.A

#### Live logs
- `World Streamer Producer (WSP)` live log tail
- ingress runtime live log tail
- front-door health / target health events

#### Live counters
- admitted rate
- duplicate rate
- valid-traffic `4xx`
- valid-traffic `5xx`
- publish success / retry / unresolved ambiguity counts
- receipt count
- quarantine count
- `p95` / `p99` latency

#### Boundary-health checks
- fresh run identity visible through control and ingress
- dedupe ledger writing for the active run
- publish continuity visible at the transport boundary
- run-scoped receipts and quarantine outputs visible

#### Fail-fast conditions
- no fresh run identity continuity
- admitted traffic with no dedupe or publish continuity
- early valid-traffic `5xx` growth
- early latency-tail blowout
- receipt/quarantine surfaces not producing attributable run-scoped outputs

Definition of done:
- the plane can now be observed honestly in real time,
- later bounded runs will not be blind.

### Phase 0.B - Fresh-run correctness proof
Goal:
- prove that a fresh bounded run still shows correct control-to-ingress behavior.

This subphase must accomplish:

1. use a fresh run identity,
2. prove control -> ingress run-scope continuity,
3. prove valid traffic is admitted, deduplicated, published, and receipted correctly,
4. prove duplicates do not falsify the verdict,
5. prove the current live path is behaving like the intended path.

Run shape:
- plane correctness slice
- `100k to 300k` events
- `2 to 5` minutes
- same declared envelope where applicable

### Telemetry sub-ledger for Phase 0.B

#### Metrics / signals to watch
- fresh run identity continuity
- admitted vs duplicate ratio
- admitted-with-publish continuity
- receipt / quarantine coherence
- valid-traffic error rate

#### Success posture
- fresh run ids remain consistent through the active boundary
- duplicate posture is bounded and explainable
- every admitted first-seen event reaches publish continuity
- receipts remain coherent and attributable
- valid traffic has `4xx = 0` and `5xx = 0`

#### Red posture
- stale or reused run identity
- duplicate flood caused by stale scope or bad keying
- admitted-without-publish evidence
- contradictory or missing receipt story
- any unexpected valid-traffic error leakage

Definition of done:
- fresh bounded correctness is green,
- there is no stale-scope contamination,
- the plane is still semantically and operationally coherent before stress.

### Phase 0.C - Envelope and recovery proof
Goal:
- prove that the plane still holds the declared envelope and bounded recovery posture.

This subphase must accomplish:

1. prove `3000 steady / 6000 burst`,
2. prove `p95 <= 350 ms` and `p99 <= 700 ms`,
3. prove bounded disturbance and recovery within `180 s`,
4. prove surge pressure does not silently break publish continuity or receipt truth.

Run shape:
- coupled-network validation slice
- `500k to 1M` events
- `5 to 8` minutes
- `3000 steady / 6000 burst`
- steady segment + bounded burst segment + bounded recovery segment

### Telemetry sub-ledger for Phase 0.C

#### Metrics / signals to watch
- steady admitted throughput
- burst admitted throughput
- latency `p95`
- latency `p99`
- recovery timer
- publish continuity during burst
- receipt coherence during burst and recovery

#### Success posture
- `steady >= 3000 eps`
- `burst >= 6000 eps`
- `p95 <= 350 ms`
- `p99 <= 700 ms`
- `recovery <= 180 s`
- no silent publish break under pressure
- no receipt breakdown under pressure

#### Red posture
- steady shortfall
- burst shortfall
- tail-latency blowout
- ambiguous or slow recovery
- edge alive while publish continuity is dark
- receipt or quarantine truth breaking under load

Definition of done:
- the declared envelope remains real,
- the recovery bound remains real,
- pressure does not silently destroy explainability.

### Phase 0.D - Working-platform base reaffirmation
Goal:
- decide whether `Control + Ingress` remains the confirmed working-platform base and update the current proving artifacts truthfully.

This subphase must accomplish:

1. assess whether the parent phase goal was actually achieved,
2. capture any newly discovered production-readiness-defining metrics in the ledger,
3. keep the readiness graphs truthful,
4. record the reasoning and verdict in notes and logbook,
5. either:
   - reaffirm `Control + Ingress` as the working-platform base, or
   - reopen ingress remediation before `Phase 1`.

### Telemetry / evidence sub-ledger for Phase 0.D

#### Items to assess
- verdict traceability
- ledger completeness
- readiness graph truthfulness

#### Success posture
- the verdict is explained by the metrics, logs, and summary together
- any new material metric family is added to the ledger
- the readiness graphs still reflect only what is proven

#### Red posture
- evidence conflicts with the verdict
- important new metric family discovered but not captured
- graph overclaims what is production-ready

Definition of done:
- the working-platform base is either reaffirmed honestly or reopened honestly,
- the parent plan remains truthful.

## Phase 0 closure rule
`Phase 0` closes only when:

1. `Phase 0.A` has removed blindness,
2. `Phase 0.B` has proved fresh-run correctness,
3. `Phase 0.C` has proved envelope and recovery,
4. `Phase 0.D` has reaffirmed the working-platform base truthfully.

If any one of those is false, `Phase 0` remains open.

## What Phase 0 hands to Phase 1
If `Phase 0` closes green, it hands this to `Phase 1`:

1. a trusted `Control + Ingress` working-platform base,
2. a usable telemetry-first proving pattern,
3. an updated readiness ledger,
4. truthful readiness graphs,
5. confidence that later red posture can be attributed to `RTDL` and its new coupled paths rather than to unresolved ingress defects.
