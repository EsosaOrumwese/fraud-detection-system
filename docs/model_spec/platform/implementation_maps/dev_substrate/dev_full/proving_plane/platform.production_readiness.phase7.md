# Phase 7 - Operations / Governance / Meta readiness

The goal of `Phase 7` is to prove that the enlarged `dev_full` working platform can be operated, reconstructed, audited, governed, and cost-controlled with the same rigor that it was executed in `Phase 0` through `Phase 6`.

This phase does not close because dashboards exist or because receipts were emitted in earlier phases. It closes only when the live platform can:

- reconstruct the accepted working-platform run story exactly from durable evidence,
- justify the accepted verdicts from authoritative readbacks rather than notebook memory,
- detect drift between declared active truth and live runtime surfaces before false certification,
- surface critical failure families through usable dashboards and alarms,
- prove spend is attributable and that the runtime can be idled and restarted safely,
- and do all of that without leaving ML day-2 monitoring as an ambiguous responsibility.

## Why this phase exists in the full plan

`Phase 0` through `Phase 6` proved that the working platform can execute and evolve correctly.

That still leaves the production operations question unanswered:

- can the platform be operated like a real production system after the proving run is over?

`Phase 7` exists to answer that question on the live AWS boundary.

## What must be true for the phase goal to be genuinely accomplished

`Phase 7` is only genuinely accomplished when all of the following are true:

1. the accepted `Phase 6` run story can be reconstructed exactly from run control, receipts, and evidence refs,
2. readback from verdict -> receipt -> evidence -> active runtime surface is deterministic and complete,
3. governance facts used by the platform remain append-only and attributable,
4. dashboards show the real working-platform operator posture rather than a partial ingress-only slice,
5. alarms cover the declared critical failure families and can be validated live,
6. cost posture is attributable enough to identify active waste and residual non-essential compute,
7. safe idle and restart posture is demonstrable on the live runtime,
8. active handle / secret / SSM resolution succeeds without placeholder drift,
9. ML day-2 monitoring ownership is explicit on the same platform:
   - active bundle truth is readable,
   - learning/runtime drift signals are visible where they exist,
   - operator mitigation surfaces are attributable.

If any one of those is false, `Phase 7` is not closed.

## Components, paths, and cross-plane relationships that contribute to that goal

### Upstream authorities already accepted
- working-platform source authority:
  - `execution_id = phase6_learning_coupled_20260312T194748Z`
  - `platform_run_id = platform_20260312T194748Z`
  - `verdict = PHASE6_READY`

### Active paths in scope
- run control -> receipt -> scorecard / rollup -> evidence readback
- accepted verdict -> active runtime path -> declared bundle truth
- evidence bucket -> dashboards / alarms / operator readback
- cost guardrail -> idle / teardown -> restart posture
- SSM / handles / secrets -> live runtime resolution
- drift readback -> operator diagnosis / mitigation

### Live surfaces in scope
- S3 evidence bucket
- object store refs used by accepted learning and runtime proof
- CloudWatch dashboards and alarms
- EKS nodegroup + RTDL / Case + Label deployments
- SSM Parameter Store paths used by the live platform
- run-control artifacts under `runs/dev_substrate/dev_full/proving_plane/run_control`

## Real subphases derived from the actual work

## Phase 7.A - Run reconstruction and verdict readback
Purpose:
- prove the accepted `Phase 6` run can be reconstructed exactly from durable evidence.

This subphase is green only when:
1. required receipts for the accepted run are present,
2. evidence refs in the accepted receipts are readable,
3. the verdict can be traced back to measured evidence without gaps,
4. no run-scope collision or receipt ambiguity appears.

## Phase 7.B - Observability and alert coverage
Purpose:
- prove the live operator surfaces show the real working-platform posture and cover critical failure families.

This subphase is green only when:
1. operations and cost dashboards are present and materially complete,
2. metrics are fresh enough to be useful,
3. alarms exist for the declared critical failure families,
4. the alert surface is attributable to the same live runtime and ingress path being certified.

## Phase 7.C - Cost, idle, and restart discipline
Purpose:
- prove the platform can be put into an economical standby posture and restored without hidden leftovers.

This subphase is green only when:
1. active cost surfaces are attributable,
2. residual non-essential compute can be identified,
3. bounded idle actions are visible and reversible,
4. restart from idle preserves the declared runtime shape.

## Phase 7.D - Identity, handles, and drift integrity
Purpose:
- prove the active operational trust model is real and that drift can be detected before false certification.

This subphase is green only when:
1. required SSM / handle / secret surfaces resolve cleanly,
2. placeholder handle count on active paths is `0`,
3. declared active bundle/runtime truth matches live surfaces,
4. drift readback catches real mismatch classes rather than static file parity only.

## Phase 7.E - Phase judgment
Purpose:
- decide whether `Operations / Governance / Meta` is plane-ready.

This subphase is green only when:
- the earlier subphases are green,
- ML day-2 monitoring responsibility is explicit rather than deferred,
- the platform can be operated, audited, governed, and cost-controlled without guesswork,
- no major blindspot remains around evidence, alarms, drift, or idle posture.

## Telemetry burden for this phase

- live logs:
  - run-control / reporter surfaces
  - governance append / evidence readback failures
  - cost / residual-scan actions
  - drift / resolution checks
- live counters:
  - receipt counts and evidence readback counts
  - dashboard freshness
  - alarm count by failure family
  - attributable active runtime count and residual idle count
  - handle resolution successes / failures
- live boundary health:
  - exact run reconstruction possible from accepted `Phase 6` evidence
  - live runtime path matches declared active bundle truth
  - dashboards and alarms point at the active runtime surfaces
  - idle / restart actions are visible and reversible
- fail-fast triggers:
  - missing required receipts or evidence holes
  - missing critical alarm coverage
  - unattributed active compute
  - active-runtime-path drift
  - placeholder or unresolved required handle on active paths

## Current starting facts entering the phase

- accepted source authority is:
  - `phase6_learning_coupled_20260312T194748Z`
  - `platform_20260312T194748Z`
- live dashboards are present:
  - `fraud-platform-dev-full-operations`
  - `fraud-platform-dev-full-cost-guardrail`
- live dashboards are still too thin for full `Phase 7` closure:
  - current operations dashboard is ingress-centric only
  - current cost dashboard shows budget shape but not runtime residual posture
- live alarm coverage is currently missing on the declared `fraud-platform-dev-full` naming surface
- the working runtime is currently active:
  - EKS nodegroup `fraud-platform-dev-full-m6f-workers` at `desired=4`
  - RTDL and Case + Label deployments running
- that means the first active blocker is operational-surface incompleteness, not a platform execution defect.

## Rebuilt execution and accepted closure authority

The rebuilt `Phase 7` did not close on the first apparently green assessment. It stayed open until the operator-surface proof and the live idle/restart drill were both present and attributable.

The meaningful rebuilt sequence was:

- live boundary audit before execution:
  - dashboards existed
  - alarm coverage was effectively absent
  - runtime was active at `desired=4`
- first bounded `Phase 7` assessor pass:
  - closed the old dashboard/alarm blind spot after live CloudWatch sync
  - exposed two proof-harness defects:
    - CSV evidence refs were being treated as JSON-only readbacks
    - the runtime drift probe assumed the wrong DF registry object shape
- second bounded assessor pass:
  - reconstruction / evidence / observability / drift surfaces all went green
  - but that revealed a method defect:
    - the assessor could still go green without the required live idle/restart drill
- tightened assessor:
  - `Phase 7` now fails closed unless `phase7_idle_restart_drill.json` exists and is green
- first idle drill execution:
  - control script failed on the wrong `eks.describe_update` parameter name
  - the live runtime still reached the intended idle boundary:
    - deployments `0`
    - nodegroup `desired=0`
    - nodes draining to zero
- corrected idle drill path:
  - waited for true zero-node idle
  - restored nodegroup to `min=2`, `desired=4`
  - restored RTDL / Case + Label / `coredns`
  - rewrote the drill receipt with the actual successful idle and restore updates
- final bounded assessor pass:
  - accepted closure on the same source authority after the idle/restart proof was present

The accepted closure authority is therefore:

- execution:
  - `phase7_ops_gov_meta_20260312T235900Z`
- source working-platform authority:
  - `phase6_learning_coupled_20260312T194748Z`
- verdict:
  - `PHASE7_READY`
- next phase:
  - `PHASE8`

## Accepted closure metrics

### Phase 7.A - Run reconstruction and verdict readback
- required local evidence:
  - `10 / 10` present
- Phase 5 readback refs:
  - `18 / 18` readable
- source authority:
  - `Phase 6` receipt remained `PHASE6_READY`

### Phase 7.B - Observability and alert coverage
- dashboards:
  - operations widgets = `4`
  - cost widgets = `3`
- alarm coverage:
  - `fraud-platform-dev-full-ig-lambda-errors`
  - `fraud-platform-dev-full-ig-lambda-throttles`
  - `fraud-platform-dev-full-ig-apigw-5xx`
  - `fraud-platform-dev-full-eks-unschedulable-pods`
  - `fraud-platform-dev-full-eks-apiserver-5xx`
- metric freshness:
  - Lambda duration fresh through `2026-03-12T20:41:00Z`
  - APIGW count fresh through `2026-03-12T20:41:00Z`
  - EKS apiserver metric fresh through `2026-03-12T23:56:00Z`
- budget surface:
  - readable and fresh
  - last updated `2026-03-12 19:13:49.687000+00:00`

### Phase 7.C - Cost, idle, and restart discipline
- idle drill:
  - nodegroup scaled from `min=2`, `desired=4`, `max=8` to `min=0`, `desired=0`, `max=8`
  - node count after idle reached `0`
  - restore returned to `min=2`, `desired=4`, `max=8`
  - RTDL, Case + Label, and `coredns` restored to their pre-drill replica counts
- cost visibility:
  - latest daily cost window remained attributable by service family
  - active spend remained visible even though the monthly budget was already exceeded
  - billing guardrail alarm present on the live `AWS/Billing` surface:
    - `fraud-platform-dev-full-billing-estimated-charges`

### Phase 7.D - Identity, handles, and drift integrity
- required handle / secret surfaces:
  - resolved `11 / 11`
  - placeholder-like active handles = `0`
- runtime drift probe:
  - live DF runtime still mounted:
    - `registry_snapshot.promoted.yaml`
    - `registry_resolution_policy.promoted.yaml`
  - active fraud-primary bundle still matched promoted Phase 5 bundle:
    - `bundle_id = da1b8f...`
    - `bundle_version = v0-29d2b27919a7`
  - policy revision remained `r3`

## Closure judgment

`Phase 7` is now closed green as a plane-readiness judgment.

Why this closure is trustworthy:

- the accepted `Phase 6` run story can now be reconstructed deterministically from receipts and evidence
- dashboards and alarms now cover the declared bounded failure families on the live platform
- the assessor itself was tightened so it could not go green without the required idle/restart proof
- the live idle/restart drill reached true zero-node idle and restored the runtime back to the accepted working shape
- active runtime drift readback still matched the promoted learning bundle and policy truth

This does **not** promote `Ops / Gov / Meta` into the working platform yet.

That still depends on `Phase 8`, where the plane has to hold as part of the full coupled platform story rather than only on its own plane boundary.
