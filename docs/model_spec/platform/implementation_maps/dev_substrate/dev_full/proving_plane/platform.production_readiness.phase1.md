# Phase 1 - RTDL Plane Readiness

## Goal
The goal of `Phase 1` is to prove that the RTDL plane can turn admitted traffic from the confirmed `Control + Ingress` base into correct, timely, explainable, auditable runtime decision truth on the live AWS runtime path.

This phase does not close because RTDL pods exist. It closes only when the RTDL plane and the newly introduced coupled paths are observable, semantically trustworthy, and production-worthy under bounded production-shaped proof.

## What must be true for Phase 1 to close
`Phase 1` closes only when all of the following are true:

1. the live RTDL runtime boundary is explicitly pinned and current-run-correct,
2. the semantic seam across `IEG`, `OFP`, `DF`, decision lane, archive, and case/label participation is materially healthy for the active run,
3. the telemetry set can distinguish inactivity, stale scope, lag, semantic failure, append/audit failure, and coupled ingress-path defects,
4. bounded RTDL proof shows correct context, feature, decision, audit, and archive continuity for the active run,
5. bounded coupled proof shows the RTDL-attached network does not regress the already-green `Control + Ingress` base,
6. the evidence is explainable, attributable, and auditable enough to promote the RTDL plane into the working platform.

## Active runtime boundary pinned
The currently accepted live RTDL boundary is:

- EKS cluster `fraud-platform-dev-full`
- namespace `fraud-platform-rtdl`
- active deployments:
  - `fp-pr3-csfb`
  - `fp-pr3-ieg`
  - `fp-pr3-ofp`
  - `fp-pr3-dl`
  - `fp-pr3-df`
  - `fp-pr3-al`
  - `fp-pr3-dla`
  - `fp-pr3-archive-writer`
- active ingress front door for coupled proof:
  - `API Gateway -> Lambda -> Kafka publish`
- current shared platform image family accepted for RTDL proof:
  - `fraud-platform-dev-full@sha256:c9846969465366dd1b97cad43b675e72db98ea4b7e46b7a7790c56f9860d320a`

The retained Managed Flink RTDL path is out of the active proof boundary unless explicitly repinned.

## Derived subphases

### Phase 1.A - Runtime boundary, repin, and telemetry truth
Goal:
- ensure the active RTDL lane is current-run-correct and observable enough that later bounded proof is not blind.

This subphase requires:

1. fresh run-scope adoption across secret-backed pins and deployment labels,
2. rollout verification across all RTDL workloads,
3. live telemetry for run participation, lag/checkpoint health, and output continuity,
4. fail-fast visibility on semantic seam defects.

Status:
- green

Accepted closures:
- stale run-scope repin defect removed through the intended materialization path
- live telemetry surfaces pinned well enough to distinguish run-scope drift from real RTDL inactivity

### Phase 1.B - Coupled RTDL envelope and semantic continuity
Goal:
- prove that the RTDL-attached network stays semantically trustworthy and production-worthy under the bounded coupled envelope.

This subphase requires:

1. semantic seam continuity across `IEG -> OFP -> DF -> DL -> archive / case / label`,
2. truthful coupled ingress control that does not inject synthetic demand,
3. fresh-scope coupled proof on the calibrated `Phase 0` base,
4. no regression of ingress correctness while RTDL materially participates.

Status:
- open

### Phase 1.C - Promotion judgment
Goal:
- decide whether RTDL and its newly introduced coupled paths can be added to the working platform.

This subphase requires:

1. fresh-scope bounded correctness green,
2. fresh-scope bounded stress green,
3. coupled-path evidence that remains attributable under inspection,
4. truthful readiness graphs and implementation trail.

Status:
- not started because `Phase 1.B` is still open.

## Current telemetry set for active Phase 1.B work

### Live logs
- `fp-pr3-csfb`
- `fp-pr3-ieg`
- `fp-pr3-ofp`
- `fp-pr3-dl`
- `fp-pr3-df`
- `fp-pr3-al`
- `fp-pr3-dla`
- `fp-pr3-archive-writer`
- ingress Lambda `fraud-platform-dev-full-ig-handler`
- APIGW access logs for `POST /ingest/push`

### Live counters and health checks
- exact APIGW route request count and `4xx` / `5xx`
- Lambda admission and publish timing
- WSP lane participation and reject posture
- run-id continuity across ingress, Kafka, RTDL, archive, case, and label surfaces
- `CSFB` checkpoint age / lag
- `OFP` missing-feature and snapshot posture
- `DF` decision and degrade posture
- archive / case / label write deltas

### Fail-fast signals
- APIGW `429` at the burst transition
- ingress `503` or `PUBLISH_AMBIGUOUS`
- WSP lane-wide `IG_PUSH_REJECTED`
- stale `CSFB` / `OFP` checkpoint posture on a fresh-scope run
- no material RTDL participation for the active run id

## Closed blockers now accepted
- stale RTDL run-scope / materializer drift
- false `IEG` graph-version contract defect
- DF/OFP redundant feature-key mismatch
- coupled-proof under-drive caused by `ig_push_concurrency = 1`
- fresh-scope ingress producer cold-path collapse caused by run-scoped Kafka publisher rebuild
- cold-start producer warm-up landing on first live requests
- burst-edge APIGW `429` caused by full-bucket transition reseeding

## Current planning posture for Phase 1.B
The active closure candidate is not the reused-scope rerun on `platform_20260311T052700Z`. That run remains diagnostic-only because ingress idempotency includes `platform_run_id`, so repeated scope reuse is not a trustworthy coupled verdict.

The next honest closure candidate must therefore use:

- a fresh RTDL materialization,
- the same accepted RTDL image family,
- the same calibrated `Phase 0` common rate plan family,
- `ig_push_concurrency = 2`,
- a front-door burst-transition seed that is truthful enough not to contaminate the coupled verdict with APIGW `429`.

## Current impact metrics

### Fresh-scope post-cold-start-fix coupled run
- execution family:
  - `phase1_rtdl_coupled_envelope_fresh_igpush2_coldwarm_20260311T052700Z`
- result:
  - steady admitted `= 2952.833 eps`
  - burst `4xx = 800`
  - recovery `4xx = 930`
  - `5xx = 0`
- accepted interpretation:
  - ingress cold-path regression is closed
  - the remaining red at that point was front-door control overshoot, not RTDL semantics

### Reused-scope reseeded diagnostic
- execution family:
  - `phase1_rtdl_coupled_envelope_fresh_igpush2_reseed_20260311T052700Z`
- result:
  - steady admitted `= 2931.722 eps`
  - burst admitted `= 3625.000 eps`
  - recovery admitted `= 2886.433 eps`
  - `4xx = 0`
  - `5xx = 0`
  - burst `p95 = 429.929 ms`
  - burst `p99 = 1413.919 ms`
- accepted interpretation:
  - synthetic-token APIGW `429` blocker is closed
  - this run is diagnostic-only and not eligible for coupled promotion judgment because it reused the same `platform_run_id`

### Latest ingress-only burst-transition calibration
- execution:
  - `phase1_control_calibration_burstmid_20260311T061700Z`
- control under test:
  - steady seed `= 15.0`
  - burst seed `= 22.5`
  - recovery seed `= 15.0`
- result:
  - steady admitted `= 2986.044 eps`
  - burst admitted `= 6784.000 eps`
  - recovery admitted `= 3005.672 eps`
  - burst `4xx = 800`
  - recovery `4xx = 808`
  - `5xx = 0`
- accepted interpretation:
  - midpoint burst seeding is still too aggressive for the front door
  - another narrow burst-transition correction is cheaper and more truthful than spending on a fresh RTDL scope immediately

### Latest ingress-only carry-forward comparison
- execution family:
  - `phase1_control_calibration_burstcarry_20260311T070500Z`
  - `phase1_control_calibration_burstcarry_igpush1_20260311T071900Z`
- same carry-forward burst seed:
  - `15.0`
- split result:
  - `ig_push_concurrency = 2`
    - steady admitted `= 3001.200 eps`
    - burst admitted `= 7074.500 eps`
    - recovery admitted `= 3016.067 eps`
    - burst `4xx = 408`
    - recovery `4xx = 488`
  - `ig_push_concurrency = 1`
    - steady admitted `= 2936.856 eps`
    - burst admitted `= 5593.000 eps`
    - recovery admitted `= 3018.461 eps`
    - `4xx = 0`
    - `5xx = 0`
- accepted interpretation:
  - the active blocker is no longer "find the next burst seed"
  - the active blocker is now the control distribution tradeoff between push concurrency and semantic cleanliness

### Latest ingress-only calibrated closure candidate
- execution:
  - `phase1_control_calibration_burstcarry_igpush1_l54_su522_20260311T080200Z`
- control posture:
  - `lane_count = 54`
  - `ig_push_concurrency = 1`
  - `stream_speedup = 52.2`
  - carry-forward burst seed
- result:
  - steady admitted `= 3031.889 eps`
  - burst admitted `= 6104.500 eps`
  - recovery admitted `= 3018.861 eps`
  - `4xx = 0`
  - `5xx = 0`
  - recovery to sustained green `= 0 s`
- accepted interpretation:
  - ingress-side coupled control is now calibrated cleanly enough for the next fresh RTDL spend
  - the next honest red, if any, should now belong to fresh RTDL coupling rather than ingress-shape ambiguity

## Current blocker family
The active blocker is no longer ingress-side control calibration.

The current hold is now methodological and RTDL-scoped:

- a fresh-scope coupled verdict is still required
- the earlier reused-scope `CSFB` / `OFP` red posture remains the first RTDL blocker family to test again
- because the control surface is now calibrated, the next fresh-scope red can be attributed back to RTDL with much higher confidence

That means the next honest question has shifted back to the coupled RTDL boundary:

- on a fresh materialized scope, does the RTDL-attached network hold the now-calibrated ingress control cleanly, or do `CSFB` / `OFP` / context-path defects reappear under load?

## Immediate next proof question
Before the next fresh RTDL materialization, `Phase 1.B` must answer one bounded question:

- on a fresh RTDL scope, is the remaining red now genuinely RTDL-semantic rather than ingress-control-induced?

Only after that question is answered cleanly should the phase spend on:

1. fresh RTDL materialization,
2. fresh coupled closure candidate on the calibrated control,
3. fresh-scope attribution of any remaining `CSFB` / `OFP` pressure under load.

## Phase 1 closure rule
`Phase 1` closes only when:

1. the RTDL boundary is current-run-correct and observably healthy enough for truthful proof,
2. the semantic seam is green on the accepted image family,
3. the coupled ingress control is truthful and no longer the primary source of red posture,
4. a fresh-scope coupled envelope run is green with RTDL materially participating,
5. the newly introduced RTDL paths do not regress the already-green `Control + Ingress` base,
6. notes, logbook, and readiness graphs all tell the same truthful story.

If any one of those is false, `Phase 1` remains open.
