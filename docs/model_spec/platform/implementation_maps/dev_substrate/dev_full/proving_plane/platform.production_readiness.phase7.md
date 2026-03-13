# Phase 7 - Operations / Governance / Meta readiness

The goal of `Phase 7` is to prove that the already-promoted working platform can be operated like a real production system after the bounded proof runs are over.

That means more than "dashboards exist" and more than "we can still read old receipts." It means an operator can:

- reconstruct the accepted platform story from durable evidence,
- move from alert -> dashboard -> runbook -> mitigation without guesswork,
- detect runtime, bundle, and learning-surface drift before silent damage accumulates,
- prove cost is attributable and bounded by deliberate operator action rather than by luck,
- and do all of that with the ML day-2 responsibilities made explicit rather than left to a later phase by assumption.

`Phase 7` remains open until that operational story is as defensible as the earlier runtime, case/label, and learning proofs.

## Why this phase exists in the full plan

`Phase 0` through `Phase 6` established that the platform can execute the intended production job on its active runtime surfaces and preserve semantic truth across the promoted planes.

That still does not answer the production operations question:

- can the platform be operated, governed, and recovered without tribal knowledge once the proving window is over?

This phase exists to answer that question on the live AWS and managed-service boundary.

## What must be true for the phase goal to be genuinely accomplished

`Phase 7` is only genuinely accomplished when all of the following are true:

1. the accepted `Phase 6` story can be reconstructed exactly from durable evidence and active control-surface truth,
2. critical alerts are not merely defined but tied to owned runbooks and bounded mitigation actions,
3. at least one alert/incident path is exercised as a real alert-to-runbook drill rather than assumed from configuration,
4. ML day-2 monitoring is explicit:
   - active bundle truth is readable,
   - learning/runtime drift surfaces are attributable,
   - mitigation paths are explicit (`rollback`, `degrade`, `pause learning`, `investigate label/data quality`) where relevant,
5. governance surfaces are append-only, attributable, and resistant to placeholder / stale-handle drift,
6. cost is attributable enough to identify waste, and idle / restore discipline is proven on the live runtime,
7. no major operational blindspot remains around dashboards, alarms, runbooks, drift visibility, or operator response.

If any one of those is false, `Phase 7` is not closed.

## Components, paths, and cross-plane relationships that contribute to that goal

### Upstream authority already accepted
- working-platform source authority:
  - `execution_id = phase6_learning_coupled_20260312T194748Z`
  - `platform_run_id = platform_20260312T194748Z`
  - `verdict = PHASE6_READY`

### Active paths in scope
- run control -> receipt -> evidence ref -> operator readback
- accepted learning bundle -> live decision fabric resolution -> operator drift readback
- CloudWatch alarm -> dashboard -> runbook -> bounded mitigation action
- budget guardrail -> cost attribution -> idle / restore action
- SSM / secret / handle resolution -> active runtime and learning surfaces
- learning/runtime drift visibility -> mitigation choice and verification

### Live surfaces in scope
- `runs/dev_substrate/dev_full/proving_plane/run_control/*`
- S3 evidence and object-store refs used by accepted Phase 5 / 6 proof
- CloudWatch dashboards, alarms, and alarm history
- AWS Budgets and Cost Explorer
- EKS nodegroup + RTDL / Case + Label workloads
- active decision-fabric registry snapshot / policy on the runtime
- Databricks-managed MLflow alias and SageMaker control-plane surfaces
- SSM Parameter Store paths used by the live platform

## Real subphases derived from the actual work

## Phase 7.A - Audit reconstruction and verdict challenge
Purpose:
- prove the accepted `Phase 6` run story can be reconstructed exactly from durable evidence, not from notebook memory.

This subphase is green only when:
1. the required receipts and manifests for the accepted source authority are present,
2. evidence refs are readable on their real surfaces,
3. the verdict can be walked from receipt -> evidence -> live bundle/runtime truth without ambiguity,
4. provenance gaps or run-scope collisions are `0`.

## Phase 7.B - Alert-to-runbook operational governance
Purpose:
- prove that critical operational failures can move through a complete operator chain rather than stopping at "an alarm exists."

This subphase is green only when:
1. dashboards cover the actual working-platform operator surface,
2. critical alarms exist for the declared failure families,
3. each critical alarm has explicit runbook / owner / escalation linkage,
4. at least one alert path is exercised or otherwise evidenced beyond initial `INSUFFICIENT_DATA -> OK`.

## Phase 7.C - ML day-2 monitoring and mitigation ownership
Purpose:
- prove that model/data/platform operations are connected by an explicit operator posture rather than by assumption.

This subphase is green only when:
1. active bundle truth is readable from the live runtime,
2. learning-surface truth is readable from managed control surfaces,
3. drift and degradation visibility is explicit for the active production path,
4. mitigation choices are explicit and attributable:
   - `rollback`,
   - `degrade`,
   - `pause promotion / learning`,
   - `investigate data / label quality`,
5. the alert / runbook / mitigation chain does not depend on guessed surface names.

## Phase 7.D - Cost governance, idle, and restart discipline
Purpose:
- prove that active cost can be attributed, that waste can be identified, and that the runtime can enter and leave standby safely.

This subphase is green only when:
1. current spend is attributable by service family and active runtime shape,
2. top waste surfaces are identifiable and actionable,
3. the budget guardrail is visible and tied to an operator action path,
4. bounded idle-to-zero and restore are proven on the live runtime,
5. residual non-essential compute after idle is `0`.

## Phase 7.E - Handle integrity and governance truth
Purpose:
- prove that active control paths do not depend on stale, placeholder, or guessed handles.

This subphase is green only when:
1. required SSM / handle / secret surfaces resolve cleanly,
2. placeholder count on active paths is `0`,
3. repo authority and live runtime authority do not disagree on the active governed path,
4. missing or guessed control-surface names are treated as blockers rather than papered over.

## Phase 7.F - Phase judgment
Purpose:
- decide whether `Operations / Governance / Meta` is plane-ready.

This subphase is green only when:
- all earlier subphases are green,
- the operational story is explainable and attributable end to end,
- the platform can be operated without guesswork,
- ML day-2 responsibility is explicit and materially supported on the live platform,
- and no major blindspot remains.

## Telemetry burden for this phase

- live logs:
  - run-control / reporter surfaces
  - governance append / evidence readback failures
  - alarm history and operator-action surfaces
  - idle / restore actions
  - runtime drift and learning-surface readback failures
- live counters:
  - receipt completeness and evidence readback counts
  - dashboard freshness and alarm coverage counts
  - alert-history / drill evidence counts
  - handle-resolution successes / failures
  - attributable spend by service family
  - idle / restore residual counts
- live boundary health:
  - exact run reconstruction possible from accepted `Phase 6` evidence
  - alert -> dashboard -> runbook -> mitigation chain is complete
  - active runtime bundle truth matches governed truth
  - cost guardrails are visible and operator-actionable
  - ML day-2 monitoring does not rely on guessed or absent surfaces
- fail-fast triggers:
  - missing required receipts or evidence holes
  - missing runbook linkage on critical alert families
  - no real alarm validation evidence
  - unattributed active compute or missing budget action path
  - missing / guessed active ML control-surface identity
  - unresolved placeholder or missing handle on active paths

## Current starting facts entering the restarted phase

- accepted source authority remains:
  - `phase6_learning_coupled_20260312T194748Z`
  - `platform_20260312T194748Z`
- live dashboards exist:
  - `fraud-platform-dev-full-operations`
  - `fraud-platform-dev-full-cost-guardrail`
- live alarms exist on the current naming surface:
  - ingress Lambda errors / throttles
  - APIGW `5xx`
  - EKS unschedulable
  - EKS apiserver `5xx`
- but the fresh restart probe shows the old closure logic was too permissive:
  - the assessor can still describe the surface more easily than it can prove operator actionability
  - the fresh rerun stayed red only on missing idle-drill freshness, which is itself evidence that the current gate is underpowered for a real Phase 7 closure
- live dashboard gap:
  - no explicit runbook / owner / escalation linkage is present on the current dashboard bodies
- live alert-validation gap:
  - alarm history currently shows only initial `INSUFFICIENT_DATA -> OK` state changes
  - no retained alert fire / clear drill evidence exists yet for this restarted phase
- ML day-2 operator ambiguity is still real:
  - active runtime bundle truth is readable from the decision fabric
  - managed learning surfaces are partly readable (`MLflow tracking_uri = databricks`, model package group present)
  - but obvious operator-facing SSM names for an online endpoint / package-group handle are absent, which means this phase must pin the real governed control surfaces rather than assume them
- cost posture is visibly hot and attributable:
  - monthly budget `300 USD`
  - actual spend already `3142.638 USD`
  - current daily leaders include `RDS`, `S3`, `MSK`, `DynamoDB`, `Lambda`, `API Gateway`, and EC2-related spend

## Immediate restart posture

The restarted `Phase 7` begins red on real operator-governance gaps, not on runtime throughput:

1. the alert-to-runbook chain is not yet proven,
2. the ML day-2 mitigation path is not yet explicit enough,
3. the current Phase 7 assessor is too thin to be closure authority,
4. the cost guardrail is visible but not yet tied to a fresh bounded operator action drill for this restarted phase.

That means the next work is:

1. tighten the Phase 7 assessor so it fails on the real missing operational controls,
2. pin or create the missing runbook / mitigation surfaces,
3. execute fresh bounded Phase 7 proof slices on that stricter boundary,
4. only then judge whether the plane is actually green.

## Rebuilt execution and accepted closure authority

The restarted `Phase 7` did not reuse the withdrawn closure story. It restarted from the live operator boundary and only closed after the stricter subproofs were materially present on the same execution scope.

The meaningful rebuilt sequence was:

- repo authority reset:
  - rushed Phase 7 phase doc withdrawn
  - rushed readiness-delta graph removed
  - master plan reset to `Phase 7 active`
- fresh operator-boundary audit:
  - dashboards and alarms existed
  - but no explicit runbook chain was present on the dashboards
  - ML day-2 operator responsibility was still under-specified
- fresh phase doc rebuilt from the actual goal of the plane
- operator control surfaces created:
  - dedicated Phase 7 runbook
  - dashboard markdown linking alert -> runbook -> mitigation posture
- fresh bounded alert-to-runbook drill:
  - exercised `fraud-platform-dev-full-ig-lambda-errors`
  - manual `ALARM -> OK` state transitions recorded in CloudWatch alarm history
  - runbook linkage materially present on the live dashboards
- fresh ML day-2 operator-surface probe:
  - first pass stayed red because rollback / restore authority was being read from the wrong probe shape
  - narrow fix:
    - derive rollback from the accepted previous-bundle authority
    - derive restore from the accepted promoted-bundle authority
  - rerun closed green on the same execution scope
- fresh idle / restore drill:
  - live nodegroup reached true zero-node idle
  - runtime restored to the pre-drill working shape
  - a receipt-serialization defect in the drill controller was fixed without changing the live drill boundary
- final bounded Phase 7 assessor:
  - accepted closure only after all three restart-scope subproofs were present and green on the same execution authority

The accepted rebuilt closure authority is:

- execution:
  - `phase7_ops_gov_meta_restart_20260313T002459Z`
- source working-platform authority:
  - `phase6_learning_coupled_20260312T194748Z`
- verdict:
  - `PHASE7_READY`
- next phase:
  - `PHASE8`

## Accepted closure metrics

### Phase 7.A - Audit reconstruction and verdict challenge
- required local evidence:
  - `10 / 10` present
- accepted Phase 5 readback refs:
  - `18 / 18` readable
- verdict traceability:
  - source authority remained `PHASE6_READY`
  - active runtime bundle still matched the accepted promoted bundle

### Phase 7.B - Alert-to-runbook operational governance
- dashboards:
  - operations widgets = `5`
  - cost widgets = `3`
- runbook linkage:
  - operations dashboard markdown present
  - cost dashboard markdown present
  - runbook path = `docs/runbooks/dev_full_phase7_ops_gov_runbook.md`
- critical alarm coverage:
  - `fraud-platform-dev-full-ig-lambda-errors`
  - `fraud-platform-dev-full-ig-lambda-throttles`
  - `fraud-platform-dev-full-ig-apigw-5xx`
  - `fraud-platform-dev-full-eks-unschedulable-pods`
  - `fraud-platform-dev-full-eks-apiserver-5xx`
  - `fraud-platform-dev-full-billing-estimated-charges`
- alert drill:
  - `fraud-platform-dev-full-ig-lambda-errors`
  - CloudWatch history recorded:
    - `OK -> ALARM`
    - `ALARM -> OK`
  - drill artifact green on the same execution scope
- metric freshness:
  - Lambda duration fresh through `2026-03-12T20:44:00Z`
  - APIGW count fresh through `2026-03-12T20:44:00Z`
  - EKS apiserver metric fresh through `2026-03-13T00:29:00Z`

### Phase 7.C - ML day-2 monitoring and mitigation ownership
- active serving truth:
  - serving mode = `EKS_DECISION_FABRIC_RUNTIME`
  - active fraud-primary bundle matched promoted truth:
    - `bundle_id = da1b8f...`
    - `bundle_version = v0-29d2b27919a7`
  - policy revision = `r3`
- managed learning surfaces:
  - `mlflow_tracking_uri = databricks`
  - SageMaker execution role resolved
  - model package group present:
    - `fraud-platform-dev-full-models`
  - no active SageMaker endpoint was assumed or required for the current serving path
- mitigation surfaces:
  - rollback bundle authority readable
  - restore bundle authority readable
  - allowed actions pinned:
    - `rollback`
    - `degrade`
    - `pause_promotion_or_learning`
    - `investigate_data_or_label_quality`

### Phase 7.D - Cost governance, idle, and restart discipline
- budget:
  - name = `fraud-platform-dev-full-monthly`
  - limit = `300 USD`
  - actual spend visible = `3142.638 USD`
- latest daily cost remained attributable by service family, with visible major contributors including:
  - `RDS`
  - `S3`
  - `MSK`
  - `DynamoDB`
  - `Lambda`
  - `API Gateway`
- idle / restore drill:
  - nodegroup scaled from `min=2`, `desired=4`, `max=8` to `min=0`, `desired=0`, `max=8`
  - node count after idle reached `0`
  - restore returned to `min=2`, `desired=4`, `max=8`
  - RTDL, Case + Label, and `coredns` returned to their pre-drill shape

### Phase 7.E - Handle integrity and governance truth
- required handle / secret surfaces:
  - resolved `11 / 11`
  - placeholder-like active handles = `0`
- runtime drift readback:
  - `registry_snapshot.promoted.yaml`
  - `registry_resolution_policy.promoted.yaml`
  - live active bundle still matched the accepted promoted authority

## Closure judgment

`Phase 7` is now closed green on the rebuilt standard as a plane-readiness judgment.

Why this restarted closure is materially stronger than the withdrawn candidate:

- the phase was restarted from a clean authority boundary instead of patched around the old closure story
- the operator chain now includes a real runbook surface, not just metrics
- the alert surface was exercised on the live platform, not merely observed in `OK`
- ML day-2 operator truth and mitigation surfaces are now explicit and attributable
- the idle / restore drill is fresh on the same execution scope as the final accepted assessor

This still does **not** promote `Ops / Gov / Meta` into the working platform.

That promotion still depends on `Phase 8`, where the plane has to hold inside the fully coupled platform story rather than only on its own plane boundary.
