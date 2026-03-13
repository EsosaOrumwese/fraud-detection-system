# Phase 9 - Full-Platform Bounded Stress Authorization

The goal of `Phase 9` is to decide whether the now-working `dev_full` platform deserves a later longer stress or soak run by widening pressure on the full integrated platform without changing the declared production shape.

This phase does not exist to rediscover correctness. `Phase 8` already answered that at bounded integrated scale. `Phase 9` exists to answer the next harder question:

- when the same full platform is held at production envelope for a materially longer bounded window, do latency tails, integrity, participation, learning continuity, and operator surfaces still stay inside production-credible bounds?

This phase is green only if the widened slice remains semantically trustworthy. A fast-looking run where a critical plane silently goes dark, or where decisions and labels continue to flow but lose meaning, is not acceptable.

## Why this phase exists in the full plan

After `Phase 8`, the whole platform is bounded-correct as one integrated production system. That is necessary, but it is still not long-window stress authority.

`Phase 9` exists to authorize the next costlier class of testing only if the platform proves that the full integrated system still holds under a wider bounded pressure window:

- same declared ingress envelope
- same critical paths
- same explainability and auditability standard
- more admitted volume
- longer sustained pressure

So the question here is not "does the system work?" It is:

- does it still work with its meaning intact when the pressure window is widened enough to deserve the phrase stress authorization?

## What must be true for the phase goal to be genuinely accomplished

`Phase 9` is only genuinely accomplished when all of the following are true:

1. a fresh full-platform runtime backbone remains green at the unchanged declared envelope,
2. the widened bounded slice admits `2M to 5M` events without hidden participation loss,
3. latency tails remain production-credible under the wider window,
4. fail-closed, quarantine, lineage, case, label, learning, and governance counters remain within bounded expectations,
5. operator surfaces remain live and attributable during the widened slice,
6. active runtime bundle truth remains continuous through the widened slice,
7. RTDL continues to emit explainable decision / action truth rather than mere traffic,
8. Case + Label outputs remain authoritative and anomaly-safe under widened load,
9. learning truth remains meaningful and runtime bundle continuity stays coupled to that governed basis,
10. no plane appears healthy because another plane silently stopped doing real work,
11. the resulting verdict is strong enough to authorize later longer stress or soak rather than merely repeat bounded correctness.

If any one of those is false, `Phase 9` is not closed.

## Components, paths, and cross-plane relationships that contribute to that goal

### Full-platform authority entering this phase
- accepted integrated closure authority:
  - `phase8_full_platform_integrated_20260313T010847Z`
- accepted fresh runtime backbone behind that closure:
  - `phase6_learning_coupled_20260313T010847Z`

### Critical full-platform stress paths in scope
- ingress -> RTDL -> audit / lineage
- RTDL -> case trigger -> case management -> label store
- runtime bundle truth -> decision attribution -> governance evidence
- promoted learning bundle -> active runtime resolution under widened load
- operator dashboards / alarms / readback surfaces under the widened window

### Live surfaces in scope
- API Gateway + Lambda ingress edge
- EKS RTDL namespace
- EKS Case + Label namespace
- Aurora-backed RTDL / Case + Label / DLA stores
- MSK topics used by the active runtime
- Databricks / MLflow / SageMaker readback surfaces needed to challenge active bundle truth
- CloudWatch dashboards / alarms / billing guardrails / evidence surfaces

## Real subphases derived from the actual work

## Phase 9.A - Stress telemetry and shape repin
Purpose:
- pin the widened bounded stress slice before spending on it.

This subphase is green only when:
1. the widened run shape stays inside the declared production envelope,
2. the active logs, counters, and fail-fast triggers are pinned for the widened window,
3. the operator surfaces needed to challenge the widened result are materially readable,
4. the stress question is clear enough that the cost is justified.

## Phase 9.B - Widened full-platform stress slice
Purpose:
- prove the full working platform still holds when the bounded pressure window is widened and the data still means what the platform says it means.

This subphase is green only when:
1. a fresh runtime-learning backbone is green,
2. admitted volume is between `2M` and `5M`,
3. steady / burst / recovery remain green at the unchanged declared envelope,
4. latency tails remain within the bounded stress posture,
5. no critical plane goes dark under widened pressure,
6. integrity and timing continuity remain green,
7. RTDL still shows accepted `decision_response` and `action_intent` truth on the governed active bundle,
8. Case + Label still turns stressed runtime truth into cases and authoritative labels without anomalies, pending buildup, or rejection drift,
9. learning-bundle continuity remains tied to a meaningful bounded evaluation basis rather than an unreadable or degenerate training story.

## Phase 9.C - Stress-time operator and governance challenge
Purpose:
- prove that the widened stress result remains challengeable and attributable from the live operator surface.

This subphase is green only when:
1. alert / dashboard / runbook chain is still materially present,
2. active bundle truth still matches governed learning truth after the widened slice,
3. evidence readback and run reconstruction remain complete,
4. critical metrics remain fresh on the live operator surface,
5. no control-surface handle drift or placeholder regression appears,
6. the operator can still challenge semantic questions, not just infrastructure ones:
   - which bundle was active?
   - what decision / action truth was emitted?
   - were cases and labels still being authored cleanly?
   - does the active bundle still trace back to a meaningful bounded evaluation basis?

## Phase 9.D - Stress authorization judgment
Purpose:
- decide whether later longer stress or soak is honestly authorized.

This subphase is green only when:
- the widened runtime slice is green,
- the stress-time operator challenge is green,
- the platform remains semantically trustworthy under the wider window,
- no invalidating telemetry blindspot remains.

## Telemetry burden for this phase

- live logs:
  - ingress edge and Lambda logs
  - RTDL workers
  - Case + Label workers
  - operator dashboards / alarm history / evidence readback failures
- live counters:
  - full-platform latency tails
  - fail-closed / quarantine / lineage / case / label / learning / governance counters
  - admitted volume and recovery continuity
  - active bundle / policy continuity
  - RTDL recent decision / action truth
  - case-to-label continuity
  - carried learning-quality and cohort visibility readbacks
- live boundary health:
  - full-platform participation remains real under widened pressure
  - active runtime bundle still matches governed promoted truth
  - operator surfaces stay live and attributable
- fail-fast triggers:
  - early clear miss of target envelope
  - latency tails beyond recoverable bound
  - critical plane dark while upstream remains hot
  - bundle truth drift between learning, runtime, and governance surfaces
  - evidence defect large enough to invalidate the widened verdict

## Current starting facts entering this phase

- the whole platform is now promoted into the working platform after `Phase 8`
- the next honest question is no longer integrated correctness
- it is whether the same full platform deserves later longer stress or soak

The immediate posture is:

1. keep the accepted `Phase 8` evidence chain fixed,
2. widen only the pressure window,
3. do not widen scope in ways unrelated to the stress question,
4. stop early if the widened slice clearly goes red.

## Phase closure rule

`Phase 9` closes only when:

1. the widened full-platform slice is green,
2. the stress-time operator challenge is green,
3. the final stress rollup is green,
4. implementation notes, logbook, plan state, and readiness graphs all tell the same truthful story.

If any one of those is false, `Phase 9` remains open.

## Current live status

`Phase 9` is open and currently red.

What the widened runs have already shown truthfully:

- semantic handling stayed clean across the active full-platform story:
  - RTDL continued to emit governed decision / action truth
  - Case + Label continued to create cases and authoritative labels without anomaly, pending, or rejection growth
  - active runtime bundle truth stayed attributable to the governed learning basis
- the blocker is not presently “the platform makes meaningless outputs under pressure”

What is still red:

- the widened WSP-driven stress source has not yet proved the declared envelope truthfully and repeatably
- the strongest remaining miss is now the front edge of the scored steady window, not the widened burst itself

Current widened source evidence:

- `phase6_learning_coupled_20260313T061950Z`
  - steady `3006.173 eps`
  - burst `5882.000 eps`
  - recovery `3015.711 eps`
- `phase6_learning_coupled_20260313T072902Z`
  - steady `3003.818 eps`
  - burst `5473.000 eps`
  - recovery `3018.772 eps`
- rejected token-top-up attempt `phase6_learning_coupled_20260313T083846Z`
  - steady `2942.727 eps`
  - burst `5519.500 eps`
  - recovery stayed green
- explicit hot-lane burst-seed rerun `phase6_learning_coupled_20260313T095425Z`
  - steady `2995.770 eps`
  - burst `6152.000 eps`
  - recovery `3020.106 eps`
  - per-second APIGW readback showed the first ~`15s` of the scored steady boundary still ramping before stabilizing near `3000/s`
- widened presteady repin on the same `54`-lane source `phase6_learning_coupled_20260313T110346Z`
  - steady `3005.513 eps`
  - burst `5176.500 eps`
  - recovery `3017.289 eps`
  - this removed the front-edge steady miss but reintroduced burst under-drive

Current judgment:

- `Phase 9` remains open because long-window stress authorization is still blocked by widened-source envelope truth, not by proven semantic corruption inside the platform.
- the `54`-lane widened source is now shown to be insufficiently repeatable under narrow timing repins
- the next narrow correction is source topology itself:
  - higher lane count at the same total envelope
  - lower per-lane burden
  - no relaxation of the platform target

Additional current truth after the first topology repin attempt:

- attempted higher-lane rerun `phase6_learning_coupled_20260313T121323Z`
  - intended posture:
    - `lane_count = 60`
    - `presteady_seconds = 150`
    - `burst_step_initial_tokens = 25.0`
  - actual applied posture:
    - receipt still shows `lane_count = 54`
    - so the topology repin did not apply
  - observed metrics on that still-`54`-lane run:
    - steady `3005.373 eps`
    - burst `5884.500 eps`
    - recovery `3019.339 eps`
  - companion `ofp:RED` on that run is not currently treated as a new runtime blocker:
    - `lag_seconds = 0.018824`
    - `checkpoint_age_seconds = 0.018824`
    - `snapshot_failures = 0`
    - reasons stayed `WATERMARK_TOO_OLD` + `STALE_GRAPH_VERSION_RED`
    - runtime participation and semantic continuity remained materially present

So the immediate next correction is not "more retries". It is:

- fix the widened source runner so explicit lane-count repins are not silently re-inherited away
- then rerun the widened source at a real higher-lane topology before spending on another full `Phase 9` attempt

The next widened source rerun has now answered that question:

- truthful higher-lane rerun `phase6_learning_coupled_20260313T132900Z`
  - applied posture:
    - `lane_count = 60`
    - `presteady_seconds = 150`
    - `steady_seconds = 600`
    - `burst_step_initial_tokens = 25.0`
  - observed metrics:
    - steady `3006.672 eps`
    - burst `6538.000 eps`
    - recovery `3019.306 eps`
    - `4xx = 0`
    - `5xx = 0`
  - semantic participation stayed material:
    - `df_decisions_total_delta = 9000`
    - `case_mgmt_cases_created_delta = 2000`
    - `label_store_accepted_delta = 3199`
    - integrity counters remained `0`
    - `decision_to_case p95 = 0.0 s`
    - `case_to_label p95 = 0.21583285 s`
  - OFP remained advisory-only:
    - same `WATERMARK_TOO_OLD + STALE_GRAPH_VERSION_RED`
    - `lag_seconds <= 0.076574`
    - `snapshot_failures = 0`
    - `events_applied` increased materially

So the widened source blocker is now removed. The active `Phase 9` question is no longer "can the source truthfully hold the widened envelope?" It is now the actual phase question:

- does the full stress authorization chain remain green on that widened truthful source when operator challenge and final stress judgment are executed together?

The first full `Phase 9` attempt on that rebuilt wrapper changed that judgment again:

- full authorization attempt `phase9_full_platform_stress_20260313T143700Z`
  - source backbone `phase6_learning_coupled_20260313T143700Z`
  - same widened source posture:
    - `lane_count = 60`
    - `presteady_seconds = 150`
    - `burst_step_initial_tokens = 25.0`
  - fresh backbone result:
    - steady `3006.123 eps`
    - burst `5132.500 eps`
    - recovery `3017.400 eps`
    - `4xx = 0`
    - `5xx = 0`
  - operator-side follow-on result:
    - alert drill green
    - ML day-2 operator surface green
    - `Phase 9` operator surface held only because the source backbone was red:
      - `PHASE9_C_SOURCE_PHASE6_NOT_GREEN`

So the truthful current judgment is:

- semantic handling remains clean
- the operator / governance side did not introduce a new blocker
- the widened source is better but still not repeatable enough at the current `60`-lane posture to anchor final stress authorization

That means `Phase 9` remains open red on **source repeatability**, not on semantic corruption and not on operator-surface failure.
