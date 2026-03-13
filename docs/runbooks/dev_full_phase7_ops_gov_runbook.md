# dev_full Phase 7 Ops / Gov Runbook

## Purpose

This runbook is the operator action surface for `Phase 7 - Operations / Governance / Meta readiness` on `dev_full`.

It exists to make the alert path explicit:

- alert -> dashboard -> runbook -> mitigation -> verification

This runbook is intentionally bounded to the active `dev_full` production-readiness proof scope. It is not a generic AWS operations manual.

## Scope

The runbook covers:

- ingress and runtime critical alarm families,
- live bundle / policy drift readback on the active decision-fabric runtime,
- managed learning-surface readback relevant to the active promoted bundle,
- cost guardrail review and bounded idle / restore action,
- escalation posture for Phase 7 drills and live operator incidents.

## Source Authority

- accepted coupled source:
  - `phase6_learning_coupled_20260312T194748Z`
  - `platform_20260312T194748Z`
- active dashboards:
  - `fraud-platform-dev-full-operations`
  - `fraud-platform-dev-full-cost-guardrail`

## Critical Alert Families

### 1. `fraud-platform-dev-full-ig-lambda-errors`
Meaning:
- ingress Lambda is surfacing unhandled or fail-closed execution errors.

Immediate checks:
1. open `fraud-platform-dev-full-operations`
2. inspect `Ingress Lambda Errors / Throttles / Duration`
3. inspect CloudWatch log group for `fraud-platform-dev-full-ig-handler`
4. confirm whether the active issue is:
   - package drift,
   - downstream publish ambiguity,
   - timeout / throttling,
   - malformed traffic outside the accepted run

Bounded mitigation:
- if tied to an active proof run, stop the run early when error posture is already red
- if tied to runtime drift, repin the Lambda package / configuration on the narrow boundary only
- if tied to downstream publish ambiguity, inspect Kafka / DLQ / receipt continuity before rerunning

Verification:
- alarm returns to `OK`
- `4xx` / `5xx` posture and Lambda errors return to clean bounded levels
- no receipt ambiguity remains

### 2. `fraud-platform-dev-full-ig-lambda-throttles`
Meaning:
- ingress Lambda concurrency or burst posture is constraining the certified envelope.

Immediate checks:
1. inspect the Lambda errors / throttles / duration widget
2. confirm reserved concurrency and recent runtime scaling posture
3. verify whether the throttle is:
   - expected during a drill,
   - a regression from deployment/config drift,
   - or an indication that the proving boundary is no longer truthful

Bounded mitigation:
- do not widen traffic shape blindly
- verify reserved concurrency and active deploy truth
- rerun only the narrow ingress boundary after the real cause is pinned

Verification:
- throttles return to `0` in the bounded proof window
- steady / burst posture remains attributable

### 3. `fraud-platform-dev-full-ig-apigw-5xx`
Meaning:
- the certified ingress edge is failing requests at the active APIGW boundary.

Immediate checks:
1. inspect the APIGW `Count / 4xx / 5xx` widget
2. query APIGW access logs for the active run window
3. correlate with Lambda errors and downstream publish path

Bounded mitigation:
- fail the active proof early if `5xx` is non-zero on valid traffic
- inspect whether this is edge failure, Lambda failure, or timing-window distortion

Verification:
- APIGW `5xx` returns to `0` on the rerun window
- access-log readback matches the repaired path

### 4. `fraud-platform-dev-full-eks-unschedulable-pods`
Meaning:
- the active runtime no longer has the scheduling headroom implied by the certified working shape.

Immediate checks:
1. inspect `EKS Unschedulable / Scheduler Errors`
2. `kubectl get pods -A`
3. `kubectl describe node` on the active cluster if scheduling pressure is non-zero

Bounded mitigation:
- identify whether this is a real residual-cost / idle-restore defect, nodegroup drift, or a new workload escaping the accepted runtime shape
- scale or restore only the narrow runtime boundary needed to return to the declared shape

Verification:
- unschedulable count returns to `0`
- active deployments match the accepted working shape

### 5. `fraud-platform-dev-full-eks-apiserver-5xx`
Meaning:
- the cluster control plane is degrading enough to threaten bounded operator control and runtime diagnosis.

Immediate checks:
1. inspect `EKS API Server 5xx / 429`
2. retry bounded `kubectl get` readbacks
3. determine whether this is transient control-plane saturation or a broader cluster issue

Bounded mitigation:
- pause active proof progression
- avoid layering new mutations onto a control plane that is already unstable
- recover the cluster control surface before resuming runtime proof

Verification:
- apiserver error metrics return to `OK`
- bounded cluster control commands succeed deterministically

### 6. `fraud-platform-dev-full-billing-estimated-charges`
Meaning:
- the monthly budget guardrail is breached and the platform must switch from "observe spend" to "take action on spend."

Immediate checks:
1. open `fraud-platform-dev-full-cost-guardrail`
2. query Cost Explorer by service family for the current daily window
3. compare against the active runtime shape:
   - EKS nodegroup desired count
   - RTDL / Case + Label deployment replicas
   - obvious storage-growth surfaces

Bounded mitigation:
- stop non-essential proof reruns
- scale the runtime to standby when not actively proving a phase
- prune rejected or dead-end storage artifacts where safe
- identify whether the major spend is:
   - durable storage growth,
   - live compute left hot,
   - managed service floor cost,
   - or repeated blind runs

Verification:
- spend remains attributable
- idle / restore posture is preserved
- no essential production surface is destroyed

## ML Day-2 Operator Posture

### Active serving truth

For the current promoted platform, active serving truth is the decision-fabric runtime on EKS, not a SageMaker endpoint.

The operator questions are:
1. which bundle is active right now?
2. which policy revision is resolving that bundle?
3. which accepted learning proof produced it?
4. what is the last-known-good rollback target?

Primary readback surface:
- decision-fabric runtime:
  - `registry_snapshot.promoted.yaml`
  - `registry_resolution_policy.promoted.yaml`

Expected active bundle source:
- accepted `Phase 5` / `Phase 6` promoted bundle truth

### Managed learning truth

Managed learning surfaces still matter for operator diagnosis even though active serving is EKS-resolved:

- `MLflow tracking_uri = databricks`
- SageMaker model package group:
  - `fraud-platform-dev-full-models`

Operator meaning:
- if runtime and managed learning disagree about the promoted truth, treat that as a Phase 7 drift issue
- do not guess a SageMaker online endpoint if the active production path is not endpoint-served

### Allowed bounded mitigations

If the active model or its surrounding learning surface is suspected of being unsafe:

1. `rollback`
   - use the accepted rollback bundle authority from the coupled learning proof
2. `degrade`
   - hold or reduce capability according to the runtime policy / accepted safety posture
3. `pause promotion / learning progression`
   - if the issue is governance, lineage, or dataset-basis ambiguity
4. `investigate data / label quality`
   - if the issue looks like semantic drift rather than infrastructure drift

### Post-mitigation verification

After any mitigation:
1. verify active bundle truth again from the live decision fabric
2. verify policy revision and fallback posture
3. verify the platform remains within the accepted bounded runtime envelope for the active phase

## Escalation Posture

Severity guidance:

- `SEV-1`
  - active runtime correctness or auditability is at risk
  - stop the active proof immediately
- `SEV-2`
  - alert surface, bundle truth, or cost control is degraded but the platform is not yet silently corrupting truth
  - hold further proving until the bounded control is restored
- `SEV-3`
  - operator-surface incompleteness or documentation/runbook gap without current runtime corruption
  - remediate before claiming phase closure

## Verification Checklist

Before calling a bounded Phase 7 slice green:

1. receipt -> evidence -> runtime truth chain is reconstructable
2. critical alarm family is linked here and reflected on the dashboard
3. at least one alert/incident path has fresh evidence beyond mere alarm existence
4. active bundle truth is readable from the runtime
5. learning-surface truth is readable from the real managed surfaces
6. cost posture is attributable
7. standby / restore actions remain bounded and reversible
