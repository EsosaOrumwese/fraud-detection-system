# Phase 6 - Working network + Learning coupled readiness

The goal of `Phase 6` is to prove that the enlarged `dev_full` working network remains production-credible once the managed learning corridor is attached as active runtime truth rather than as a separate plane-ready island.

This phase does not close because a candidate bundle exists in registry storage or because a static registry file can be edited locally. It closes only when the live runtime can:

- adopt the promoted learning bundle on the real RTDL path,
- preserve already-proven runtime and case/label behaviour under bounded production-shaped load,
- attribute runtime decisions back to the admitted learning basis and governed bundle truth,
- roll back to the prior active bundle without ambiguity,
- and restore the promoted bundle again as the final active truth.

## Why this phase exists in the full plan

`Phase 5` proved the learning corridor on its own criteria:

- semantic admission,
- bounded dataset basis,
- managed train/eval,
- lineage,
- governed publication,
- bounded rollback drill.

That still leaves the main platform question unanswered:

- once the promoted bundle is attached to the actual runtime network, does the platform still behave as one semantically coherent production system?

`Phase 6` exists to answer that question on the live AWS/EKS boundary.

## What must be true for the phase goal to be genuinely accomplished

`Phase 6` is only genuinely accomplished when all of the following are true:

1. the live runtime can be rematerialized with the promoted bundle-resolution surfaces, not just a local receipt,
2. the runtime warm gate proves that both registry snapshot and registry policy are the promoted ones,
3. the bounded coupled runtime slice remains green on ingress, RTDL, Case + Label, and timing,
4. live decision evidence on the active run carries the promoted bundle truth,
5. rollback to the prior active bundle is bounded and attributable on the same runtime path,
6. restore to the promoted bundle is bounded and attributable on the same runtime path,
7. the final active runtime truth at phase closure is the promoted bundle, not the rollback bundle,
8. the evidence chain remains explainable from:
   - admitted source world
   - bounded learning basis
   - managed train/eval result
   - governed publication
   - active runtime decision attribution

If any one of those is false, `Phase 6` is not closed.

## Components, paths, and cross-plane relationships that contribute to that goal

### Upstream authorities already accepted
- working-platform source authority:
  - `execution_id = phase4_case_label_coupled_20260312T003302Z`
  - `platform_run_id = platform_20260312T003302Z`
- learning-plane authority:
  - `execution_id = phase5_learning_managed_20260312T071600Z`
  - `verdict = PHASE5_READY`

### Active coupled paths in scope
- runtime decision truth -> case/label truth -> learning basis -> governed bundle publication
- governed bundle publication -> RTDL registry resolution surfaces
- RTDL active bundle resolution -> decision evidence -> DLA governance stamps
- prior active bundle -> rollback restore path
- rollback restore path -> promoted bundle re-restore path

### Live runtime surfaces in scope
- EKS RTDL namespace
- EKS Case + Label namespace
- API Gateway + Lambda ingress edge
- MSK topics used by the working platform
- Aurora-backed RTDL / Case + Label / DLA stores
- DLA governance stamps and recent attempts

## Real subphases derived from the actual work

## Phase 6.A - Runtime bundle-resolution repin
Purpose:
- prove that the runtime can actually load the promoted learning bundle-resolution truth.

This subphase is green only when:
1. run-scoped promoted registry snapshot and registry policy are both materialized,
2. the rematerialized runtime mounts both files, not just the snapshot,
3. the DF warm gate reports the promoted bundle and promoted policy revision on the live pod.

## Phase 6.B - Coupled runtime bounded proof
Purpose:
- prove that the promoted runtime still preserves the already-hardened working network under bounded production-shaped pressure.

This subphase is green only when:
1. ingress envelope is green,
2. RTDL / Case + Label component health remains green or advisory-only within the known bounded posture,
3. coupled timing remains green,
4. no new integrity breach appears in DF / AL / DLA / Case + Label.

## Phase 6.C - Runtime decision attribution proof
Purpose:
- prove that the active runtime decisions for the bounded Phase 6 run carry the promoted bundle truth in the actual DLA governance stamps.

This subphase is green only when:
1. one bounded bundle identity is present for the main scenario,
2. that bundle identity matches the promoted Phase 5 bundle,
3. one bounded policy identity is present for the main scenario,
4. no DLA quarantine or attribution ambiguity appears.

## Phase 6.D - Rollback and restore proof
Purpose:
- prove that the active runtime truth can be switched back to the prior active bundle and then restored to the promoted bundle without ambiguity.

This subphase is green only when:
1. rollback rematerialization is healthy,
2. rollback activation traffic yields runtime decisions attributed to the prior active bundle,
3. restore rematerialization is healthy,
4. restore activation traffic yields runtime decisions attributed again to the promoted bundle,
5. final active runtime truth at phase closure is the promoted bundle.

## Phase 6.E - Coupled-network judgment
Purpose:
- decide whether `Learning + Evolution / MLOps` can be promoted into the working platform.

This subphase is green only when:
- the earlier subphases are green,
- the evidence chain remains explainable and auditable,
- no major semantic ambiguity remains around active bundle adoption or rollback,
- the enlarged network is still production-credible as one coupled platform.

## Telemetry burden for this phase

- live logs:
  - RTDL workers
  - Case + Label workers
  - DLA worker
  - WSP bounded runner
- live counters:
  - ingress admitted / latency / recovery
  - DF / AL / DLA / Case + Label deltas
  - DLA governance bundle refs
  - rollback and restore drill timings
- live boundary health:
  - mounted promoted policy + snapshot on the runtime
  - active bundle visible in DLA decision stamps
  - no mixed bundle truth on the bounded scenario
- fail-fast triggers:
  - runtime materialization red
  - warm gate red
  - candidate bundle drift in DLA
  - rollback bundle drift in DLA
  - restore bundle drift in DLA
  - ingress / RTDL / Case + Label regression on the main bounded slice

## Current starting facts entering the rebuilt phase

- the runtime is intentionally in standby from the cost-hygiene pass:
  - nodegroup `fraud-platform-dev-full-m6f-workers` at `desired=0`, `min=0`
  - RTDL and Case + Label deployments scaled to `0`
  - `coredns` scaled to `0`
- the base registry snapshot / policy still point at the prior active bundle:
  - `bundle_version = m11g_candidate_bundle_20260227T081200Z`
- the promoted learning bundle from `Phase 5` is:
  - `bundle_id = da1b8f7690cf6cfec4f3f9e7c69df2479d2953fbd00102ad2f7e3ed9c66b943e`
  - `bundle_version = v0-29d2b27919a7`
- the first truthful blocker entering `Phase 6` was not runtime performance:
  - it was that runtime rematerialization carried only the registry snapshot while the DF policy still came from the image
- that repin defect must be fixed before any coupled verdict is accepted.

## Rebuilt execution and accepted closure authority

The rebuilt `Phase 6` did not close on the first apparently promising run. It stayed open until the active blocker class was identified truthfully and removed without weakening the target.

The meaningful rebuilt sequence was:

- `phase6_learning_coupled_20260312T140338Z`
  - fixed false rollback / restore darkness by introducing fresh rollback and restore run scopes
  - left real envelope red plus rollup-authority drift
- `phase6_learning_coupled_20260312T154940Z`
  - failed fast on real `case_mgmt` `OOMKilled`
- `phase6_learning_coupled_20260312T155754Z`
  - confirmed `case_mgmt` repin worked
  - exposed real `label_store` `OOMKilled`
- `phase6_learning_coupled_20260312T163721Z`
  - candidate / rollback / restore probes green
  - runtime budgets now stable
  - narrowed remaining blocker to burst only
- `phase6_learning_coupled_20260312T173845Z`
  - burst recovered
  - exposed steady-window dip as the only blocker
- `phase6_learning_coupled_20260312T184417Z`
  - longer presteady did not remove the dip
  - proved the active defect was still in the harness boundary, not the runtime
- `phase6_learning_coupled_20260312T194748Z`
  - accepted closure run after the shared envelope builder stopped emitting a no-op same-rate transition at the scored steady boundary

The accepted closure authority is therefore:

- execution:
  - `phase6_learning_coupled_20260312T194748Z`
- platform run:
  - `platform_20260312T194748Z`
- verdict:
  - `PHASE6_READY`
- next phase:
  - `PHASE7`

## Accepted closure metrics

### Phase 6.B - Coupled runtime bounded proof
- steady:
  - `3047.367 eps`
  - `4xx = 0`
  - `5xx = 0`
  - `p95 = 54.982 ms`
  - `p99 = 85.951 ms`
- burst:
  - `6099.000 eps`
  - `4xx = 0`
  - `5xx = 0`
  - `p95 = 47.000 ms`
  - `p99 = 54.000 ms`
- recovery:
  - `3019.894 eps`
  - `4xx = 0`
  - `5xx = 0`
  - sustained green from the first `30`-second recovery bin

### Phase 6.B - Coupled integrity and timing
- integrity deltas:
  - `df_hard_fail_closed_delta = 0`
  - `df_publish_quarantine_delta = 0`
  - `al_publish_quarantine_delta = 0`
  - `dla_append_failure_delta = 0`
  - `case_trigger_quarantine_delta = 0`
  - `case_mgmt_anomalies_total_delta = 0`
  - `label_store_pending_delta = 0`
  - `label_store_rejected_delta = 0`
- timing:
  - `decision_to_case p95 = 0.0 s`
  - `case_to_label p95 = 0.196 s`

### Phase 6.C / 6.D - Runtime attribution and rollback / restore
- candidate bundle attribution:
  - green
  - active runtime bundle matched the promoted Phase 5 bundle
- rollback attribution:
  - green
  - bounded rollback resolved to the prior active bundle without ambiguity
- restore attribution:
  - green
  - final active runtime truth returned to the promoted bundle

### Closure judgment

`Phase 6` is now closed green.

Why this closure is trustworthy:

- the managed learning corridor remained anchored to the accepted `Phase 5` evidence chain
- the enlarged runtime remained green on ingress, RTDL, Case + Label, timing, integrity, attribution, rollback, and restore
- the final blocker was removed by correcting a shared proving-harness defect rather than by weakening the target
- the final accepted run proved the same coupled question on the same declared envelope:
  - `3000 steady eps`
  - `6000 burst eps`

That means `Learning + Evolution / MLOps` is no longer just plane-ready. It is now promoted into the working platform as a coupled production-credible member.

## Phase closure rule

`Phase 6` closes only when:

1. promoted runtime adoption is green,
2. bounded coupled runtime proof is green,
3. runtime decision attribution is green,
4. rollback and restore proof are green,
5. the final active runtime truth is the promoted bundle,
6. notes, logbook, plan state, and readiness graphs all tell the same truthful story.

If any one of those is false, `Phase 6` remains open.
