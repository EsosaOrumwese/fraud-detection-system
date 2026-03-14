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

`Phase 9` is closed green.

Accepted stress-authorization authority:

- full Phase 9 closure run:
  - `phase9_full_platform_stress_20260313T203100Z`
- fresh widened runtime-learning backbone behind that closure:
  - `phase6_learning_coupled_20260313T203100Z`
- final receipt:
  - `PHASE9_READY`
- next authorized state:
  - `LONG_STRESS_AUTHORIZED`

## What actually closed the phase

The final accepted posture did not lower the platform target. It removed the source-repeatability defect by changing source fan-out, not by weakening the platform standard:

- `lane_count = 84`
- `ig_push_concurrency = 1`
- `presteady_seconds = 150`
- `steady_seconds = 600`
- `burst_step_initial_tokens = 17.8571428571`

That posture matters because earlier attempts showed the real blocker clearly:

- `60` lanes was not repeatable enough to anchor full authorization
- `72` lanes improved the widened source, but still failed on full-repeat burst behavior
- `ig_push_concurrency = 2` was rejected because it created real `4xx` / `5xx` and recovery damage

So the accepted `84`-lane posture is not a lucky pass. It is the final narrow remediation after the actual error class was understood as source repeatability under the widened burst boundary.

## Final Phase 9 stress story

From `phase9_full_platform_stress_20260313T203100Z`:

- admitted total:
  - `2,360,103` requests
- widened envelope:
  - steady `3007.053 eps`
  - burst `6359.000 eps`
  - recovery `3017.517 eps`
- latency:
  - steady `p95 = 47.9935 ms`
  - steady `p99 = 59.9765 ms`

From the accepted widened backbone `phase6_learning_coupled_20260313T203100Z`:

- steady `3008.575 eps`
- burst `6681.000 eps`
- recovery `3017.589 eps`
- `4xx = 0`
- `5xx = 0`
- burst `p99 = 151.9405 ms`

So the widened stress slice held the declared production shape without relaxing throughput or latency expectations.

## Semantic handling under widened pressure

This phase only closes if the platform keeps its meaning under widened pressure. The final accepted run did that.

### RTDL stayed meaningful

- recent RTDL event types remained:
  - `action_intent`
  - `decision_response`
- recent RTDL reason codes remained:
  - `ACCEPT`
- governed active-bundle continuity stayed present while widened traffic was running

This matters because it shows the platform was still making attributable runtime decisions, not merely moving opaque traffic through the path.

### Case + Label remained authoritative

Runtime-to-case-to-label participation stayed materially present:

- `case_trigger_triggers_seen_delta = 8505`
- `case_mgmt_cases_created_delta = 2079`
- `label_store_accepted_delta = 2693`

Timing continuity stayed credible:

- `decision_to_case_p95_seconds = 0.0`
- `case_to_label_p95_seconds = 0.1976141`

Integrity remained clean:

- `case_mgmt_anomalies_total_delta = 0`
- `label_store_pending_delta = 0`
- `label_store_rejected_delta = 0`
- `case_trigger_quarantine_delta = 0`

So the stressed platform was still turning runtime truth into cases and authoritative labels, not silently stalling or degrading into backlog / anomaly growth.

### Learning and bundle continuity remained meaningful

The active runtime bundle still traced back to the governed learning basis:

- active bundle id:
  - `da1b8f7690cf6cfec4f3f9e7c69df2479d2953fbd00102ad2f7e3ed9c66b943e`
- active bundle version:
  - `v0-29d2b27919a7`
- policy revision:
  - `r3`
- readable Phase 5 references:
  - `18`

The carried learning-quality basis remained explicit in the same stress story:

- `phase5_auc_roc = 0.9104674176699058`
- `phase5_precision_at_50 = 1.0`
- `feature_asof_utc = 2026-03-05T00:00:00Z`
- `campaign_present_rows = 2`

That means widened runtime pressure did not sever the bundle from the meaningful bounded learning basis already accepted in `Phase 5` and coupled in `Phase 6`.

## Cross-plane participation and integrity

Full-platform participation remained real:

- `df_decisions_total_delta = 9095`
- `al_intake_total_delta = 6061`
- `dla_append_success_total_delta = 11066`
- `case_trigger_triggers_seen_delta = 8505`
- `case_mgmt_cases_created_delta = 2079`
- `label_store_accepted_delta = 2693`

Critical integrity deltas stayed at `0`:

- `df_hard_fail_closed_delta`
- `df_publish_quarantine_delta`
- `al_publish_quarantine_delta`
- `dla_append_failure_delta`
- `dla_replay_divergence_delta`
- `case_trigger_quarantine_delta`
- `case_mgmt_anomalies_total_delta`
- `label_store_pending_delta`
- `label_store_rejected_delta`

So no plane only appeared green because another plane silently stopped doing real work.

## Operator and governance challenge under stress

The full Phase 9 authorization chain completed, not just the widened backbone:

- `phase7_alert_runbook_drill_receipt.json`
  - `PHASE7_ALERT_DRILL_READY`
- `phase7_ml_day2_operator_surface_receipt.json`
  - `PHASE7_ML_DAY2_READY`
- `phase9_stress_operator_surface_receipt.json`
  - `PHASE9_OPERATOR_READY`
- final stress receipt:
  - `PHASE9_READY`

The manifest confirms the full chain completed:

1. `phase6_stress_backbone`
2. `phase7_alert_runbook_drill`
3. `phase7_ml_day2_operator_surface`
4. `phase9_stress_operator_surface`
5. `phase9_stress_rollup`

So the widened stress result stayed challengeable and attributable from the live operator surface rather than depending on a hidden post hoc reconstruction.

## Final judgment

`Phase 9` is green because the full `dev_full` platform proved two things at the same time on one widened bounded stress story:

1. it still holds the declared production shape under materially wider pressure, and
2. it still handles the information within the data meaningfully across RTDL, Case + Label, and learning/runtime bundle continuity.

That is the required authorization boundary for this plan.

The platform is therefore not just "green on stress." It is authorized for later longer stress / soak because the widened proof showed:

- production-credible throughput and latency,
- clean integrity and recovery,
- real cross-plane participation,
- explainable RTDL decision truth,
- authoritative case / label truth,
- continuous governed learning / active-bundle truth,
- live operator challenge and governance readback.
