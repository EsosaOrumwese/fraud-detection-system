# Phase 8 - Full-Platform Bounded Integrated Validation

The goal of `Phase 8` is to prove that the whole `dev_full` platform now behaves as one coherent bounded production system when the already-promoted working platform is coupled with the now-plane-ready `Ops / Gov / Meta` control surface.

This phase is not a larger replay of earlier greens. It exists to answer the question that the earlier plane proofs cannot answer on their own:

- when all active planes are treated as one bounded production story, does anything silently break at the handoffs?
- can the platform still be explained, reconstructed, governed, and safely operated without one plane appearing green because another plane stopped doing real work?

`Phase 8` closes only when the integrated proof story is:

- bounded-correct,
- truth-continuous,
- timing-continuous,
- explainable,
- auditable,
- and free of hidden handoff defects across the full platform.

## Why this phase exists in the full plan

Earlier phases proved, in order:

- `Control + Ingress`
- `RTDL`
- `Case + Label`
- `Learning + Evolution / MLOps`
- `Ops / Gov / Meta` as a plane-readiness judgment

That is still not enough to authorize wider full-platform stress.

`Phase 8` exists because the real production question is no longer "does each plane work?" It is:

- does the whole platform still behave coherently once the ops/governance plane is attached to the live production story?

The full-platform truth we need here is:

- ingress admitted traffic is still real,
- runtime decisions still carry active bundle truth,
- case and label paths still materially participate,
- learning truth remains attributable,
- governance surfaces can still reconstruct and challenge the same run story,
- idle / alert / operator actions do not hide a coupled defect.

## What must be true for the phase goal to be genuinely accomplished

`Phase 8` is only genuinely accomplished when all of the following are true:

1. one fresh bounded runtime-serving proof is green on the already-accepted production envelope,
2. the learning authority behind the active bundle remains the accepted governed basis rather than a stale or guessed source,
3. the active runtime bundle and policy truth remain continuous through the integrated proof story,
4. `Case + Label` still materially participates under the same bounded run,
5. operator surfaces can reconstruct, challenge, and mitigate the same integrated run story,
6. alert, dashboard, runbook, and mitigation surfaces remain coupled to the real active platform,
7. bounded idle / restore leaves the platform in a known-good post-restore state with the same governed runtime truth,
8. no hidden handoff defect appears once the full platform is scored as one network.

If any one of those is false, `Phase 8` is not closed.

## Components, paths, and cross-plane relationships that contribute to that goal

### Full working-platform basis entering this phase
- accepted runtime-serving authority:
  - `phase6_learning_coupled_20260312T194748Z`
- accepted ops/gov plane-readiness authority:
  - `phase7_ops_gov_meta_restart_20260313T002459Z`

### Critical full-platform paths in scope
- ingress -> RTDL -> audit / lineage
- RTDL -> case trigger -> case management -> label store
- runtime / label truth -> learning basis -> governed bundle publication
- governed bundle publication -> runtime resolution
- runtime resolution -> decision evidence -> operator reconstruction
- alert -> dashboard -> runbook -> bounded mitigation
- idle / restore -> post-restore governed runtime truth

### Live surfaces in scope
- API Gateway + Lambda ingress edge
- EKS RTDL namespace
- EKS Case + Label namespace
- Aurora-backed RTDL / Case + Label / DLA stores
- MSK topics used by the active runtime
- Databricks / MLflow / SageMaker managed learning surfaces already proven in `Phase 5`
- CloudWatch dashboards / alarms / billing guardrails / evidence readback surfaces already proven in `Phase 7`

## Real subphases derived from the actual work

## Phase 8.A - Fresh integrated runtime backbone
Purpose:
- prove the full-platform integrated story starts from a fresh bounded runtime-serving authority rather than from reused earlier receipts.

This subphase is green only when:
1. a fresh `Phase 6`-shaped bounded runtime-learning execution is green,
2. the fresh run preserves the declared envelope:
   - `3000 steady eps`
   - `6000 burst eps`
3. runtime bundle adoption, rollback, and restore remain green,
4. `Case + Label` participation and timing remain materially green on the same fresh run,
5. the learning authority remains the accepted governed bundle basis.

## Phase 8.B - Integrated operator coupling
Purpose:
- prove that ops / gov acts on the same fresh integrated run story rather than on a detached prior run.

This subphase is green only when:
1. alert drill evidence exists on the same integrated execution scope,
2. ML day-2 operator truth reads the same promoted runtime bundle as the fresh integrated runtime,
3. run reconstruction and evidence readback remain complete,
4. bounded idle / restore returns the runtime to the governed active bundle without drift,
5. the final post-restore bounded assessor remains green.

## Phase 8.C - Integrated full-platform judgment
Purpose:
- decide whether the whole platform is bounded-correct as one coupled production system.

This subphase is green only when:
- `Phase 8.A` is green,
- `Phase 8.B` is green,
- full-platform truth continuity is explainable,
- full-platform timing continuity is explainable,
- no active plane is dark while upstream remains hot,
- the integrated verdict is reconstructable and auditable from one bounded run story.

## Telemetry burden for this phase

- live logs:
  - ingress edge and Lambda logs
  - RTDL workers
  - Case + Label workers
  - governance / evidence / alarm-history surfaces
  - managed learning readback surfaces where the active bundle authority depends on them
- live counters:
  - ingress steady / burst / recovery counters
  - RTDL / DLA / Case + Label participation deltas
  - active bundle / policy continuity
  - alert fire / clear counts
  - evidence readback and reconstruction counts
  - idle / restore residual counts
- live boundary health:
  - all critical paths participating on the same integrated execution
  - active runtime bundle matches governed learning truth
  - operator surfaces act on real active resources rather than guessed handles
  - post-restore runtime still matches governed truth
- fail-fast triggers:
  - any envelope window red
  - any active plane dark while upstream remains hot
  - any active bundle drift between learning, runtime, and ops/gov surfaces
  - any evidence hole large enough to invalidate the integrated verdict
  - post-restore runtime not converging back to governed truth

## Current starting facts entering this phase

- `Learning + Evolution / MLOps` is promoted into the working platform after accepted `Phase 6`
- `Ops / Gov / Meta` is only plane-ready after the rebuilt `Phase 7`
- the next truthful question is therefore not another isolated plane proof
- it is whether the whole platform can now hold as one integrated production system

The immediate posture is:

1. do not reuse the accepted `Phase 6` and rebuilt `Phase 7` receipts as closure authority for `Phase 8`,
2. generate one fresh runtime-learning backbone,
3. attach fresh ops/gov subproofs to that same integrated execution scope,
4. only then score the whole platform as one bounded network.

## Phase closure rule

`Phase 8` closes only when:

1. a fresh integrated runtime backbone is green,
2. fresh integrated operator coupling is green on the same proof story,
3. the full-platform integrated rollup is green,
4. implementation notes, logbook, plan state, and readiness graphs all tell the same truthful story.

If any one of those is false, `Phase 8` remains open.
