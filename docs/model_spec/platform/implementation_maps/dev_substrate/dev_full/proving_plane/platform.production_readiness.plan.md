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
- Obey the `AGENTS.md`
- `dev_full` is already built and wired. This plan hardens and proves it; it does not redesign it from scratch unless a production-blocking flaw forces a repin.
- The Data Engine remains a black box. The platform works with the data available in the oracle store and through the data-engine interface pack.
- When a plane depends on understanding the semantics of the incoming data, the agent may inspect only the allowed Data Engine references for understanding:
  - primary contract: `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
  - output inventory and gates: `docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`, `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`
  - allowed build/state context:
    - `docs/model_spec/data-engine/implementation_maps/segment_5B.build_plan.md`
    - `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
    - `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s5.expanded.md`
    - `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
- Those Data Engine docs are for semantic understanding only. They do not change the black-box rule: the platform still consumes the engine through the interface pack and oracle-store outputs, not by editing or re-running engine internals.
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

### 5. Telemetry-first hardening
No phase may begin execution without an explicit telemetry plan for that phase.

Every phase expansion must define, before the first AWS run:
- live logs for the active plane and its immediate dependencies,
- live progress counters for the active plane,
- live boundary-health checks,
- fail-fast stop conditions,
- the minimal hardening artifact set to keep under `runs/`.

The point is to eliminate blind runs and reduce guesswork. If the phase cannot be observed live, the phase is not yet execution-ready.

### 6. Truthful steady-state measurement
When a phase is proving a steady-state envelope, the measurement window must reflect the real steady-state boundary rather than a launcher artifact.

This means:
- the target itself does not move,
- the run shape must remain production-legitimate,
- the measurement start must be attributable to confirmed plane participation rather than raw submission time when those differ materially,
- a measurement correction is valid only if it is explicit, explainable, and repeatable on the same run shape,
- traffic-shape changes that create synchronized-arrival artifacts or otherwise change the boundary are diagnostic tools only, not valid promotion evidence.

### 7. Narrow rerun discipline
Once a phase has one semantically trustworthy baseline, that baseline should be frozen while the remaining ambiguity is removed.

This means:
- do not keep inventing new run shapes to chase a green receipt,
- prefer fixing telemetry, attribution, or a narrow runtime defect first,
- repeat the same truthful baseline to prove repeatability,
- only widen or reshape the run if the current baseline is itself shown to be invalid.

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

## Road map for phase expansion
We do not move through this plan by shamelessly and foolishly creating states within a phase that do not really lead toward the goal of that phase and as a whole this plan.

Instead, the road map is:

1. start at the parent phase in this plan,
2. ask what the goal of that phase is in relation to the goal of this entire plan,
3. ask how that phase goal can actually be accomplished,
4. ask what steps are necessary to accomplish that goal,
5. let those real required steps define the subphases for that phase.

_(Once again, this is not a template but a mindset)_

This means:
- subphases are not forced into a fixed number,
- subphases are not created because a runner or workflow suggests another state,
- subphases are created only because they are necessary to accomplish the goal of the parent phase.

### How each phase is to be expanded
For every phase, the expansion method is:

1. restate the goal of the phase,
2. ask what must be true for that phase goal to be genuinely accomplished,
3. identify the components, paths, and cross-plane relationships that contribute to that goal,
4. identify which of those contributors need their own focused attention,
5. derive the subphases from that real work.

This is important because some phases will contain many components and each component may contribute a unique part to the goal of the phase. They should not be lumped together without consideration just because they live in the same plane.

### Telemetry and metric derivation for subphases
Once the subphases are defined from the real goal of the phase, we then ask:
- what live telemetry is needed to monitor each subphase honestly?
- what metrics are we looking for that actually match the goal of that subphase?
- what progress or red posture would those metrics show?

That telemetry and those metrics should then be added as the subphase ledger for that phase.

### Phase closure rule
Once the goal of the phase is actually accomplished:
- close the phase,
- update the ledger in this plan with what has now been proven,
- then move to the next phase.

The phase is not complete because its subphases were run. The phase is complete only when its goal, in relation to the entire production-readiness plan, has actually been achieved.

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

## Readiness metric ledger
This ledger pins the metric families and target posture the platform is working toward.

It exists to remove “looks good” or “seems fine” reasoning from production-readiness claims. Each metric family here must later be tied to live telemetry and phase evidence.

Rules:
- these targets are the current production-readiness working targets, not permanent universal ceilings,
- they may be tightened by evidence,
- they must not be loosened casually just to get a green verdict,
- where a metric is intentionally fault-injection-dependent, the target applies to healthy bounded runs unless the phase explicitly says otherwise.
- this ledger is intentionally living: as phases progress and new production-readiness-defining metrics are discovered, the ledger must be expanded in place rather than left implicit in notes or run summaries.
- phase expansion work must check whether the current ledger is missing any metric family that became materially necessary to judge the plane or cross-plane path honestly; if yes, that metric must be added before the phase can be considered closed.
- closure updates in this ledger must remain truthful:
  - do not pretend every row has a fresh standalone scalar if the accepted authority proved that row as part of a bounded family,
  - tie each ledger family to the accepted closure run(s) and the key impact metrics that actually justified the verdict,
  - keep row-level targets as targets unless the accepted phase authority really established a tighter permanent number.

### Control + Ingress

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| steady admitted throughput | `>= 3000 eps` | ingress live telemetry + bounded run summary | Phase 0 |
| burst admitted throughput | `>= 6000 eps` | ingress live telemetry + bounded run summary | Phase 0 |
| latency p95 | `<= 350 ms` | ingress live telemetry | Phase 0 |
| latency p99 | `<= 700 ms` | ingress live telemetry | Phase 0 |
| valid-traffic `4xx` | `0` | ingress live telemetry | Phase 0 |
| valid-traffic `5xx` | `0` | ingress live telemetry | Phase 0 |
| duplicate correctness error rate | `0` | dedupe ledger + bounded run summary | Phase 0 |
| admitted-without-publish count | `0` | ingress + Kafka boundary telemetry | Phase 0 |
| publish ambiguity unresolved count | `0` | ingress receipts + Kafka boundary telemetry | Phase 0 |
| bounded recovery time | `<= 180 s` | run summary + live recovery counters | Phase 0 |

Current proven ledger status:
- accepted closure authority:
  - `phase0_20260310T223332Z`
- key observed closure metrics:
  - steady admitted `= 3025.30 eps`
  - burst admitted `= 6019.50 eps`
  - recovery admitted `= 3019.21 eps`
  - `4xx = 0`
  - `5xx = 0`
  - Lambda `Errors = 0`
  - Lambda `Throttles = 0`
  - DLQ delta `= 0`
  - recovery to sustained green `= 0 s`
- ledger judgment:
  - the Phase 0 control + ingress metric family is proven on the exact APIGW-scored closure authority and remains the working-platform base.

### Real-Time Decision Loop (RTDL)

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| CSFB false-ready rate | `0` | RTDL live telemetry + correctness summary | Phase 1 |
| IEG checkpoint age p99 | `<= 2 s` | IEG live telemetry | Phase 1 |
| IEG lag p99 | `<= 2 s` | IEG live telemetry | Phase 1 |
| IEG backpressure incidents | `0` in healthy bounded runs | IEG live telemetry | Phase 1 |
| OFP freshness lag p99 | `<= 2 s` | OFP live telemetry | Phase 1 |
| OFP restart-to-green | `<= 180 s` | OFP recovery telemetry | Phase 1 |
| false missing-feature rate | `0` | OFP + DF boundary telemetry | Phase 1 |
| DL false fail-closed rate | `0` | DL reason breakdown | Phase 1 |
| DF hard fail-closed count | `0` in healthy bounded runs | DF live telemetry | Phase 1 |
| DF quarantine count | `0` in healthy bounded runs unless ambiguity is intentionally injected | DF live telemetry | Phase 1 |
| decision latency p95 | `<= 300 ms` | DF / RTDL live telemetry | Phase 1 |
| decision latency p99 | `<= 600 ms` | DF / RTDL live telemetry | Phase 1 |
| AL duplicate side-effect error rate | `0` | AL live telemetry | Phase 1 |
| DLA append failure count | `0` | DLA live telemetry | Phase 1 |
| DLA replay divergence count | `0` | DLA live telemetry | Phase 1 |
| Archive Writer write error count | `0` | Archive Writer live telemetry | Phase 1 |
| Archive Writer payload mismatch count | `0` | Archive validation telemetry | Phase 1 |

Current proven ledger status:
- accepted closure authority:
  - `phase1_rtdl_coupled_envelope_fresh_closure_su529_20260311T092709Z`
  - fresh scope `platform_20260311T092709Z`
- key observed closure metrics:
  - steady admitted `= 3035.833 eps`
  - burst admitted `= 6227.000 eps`
  - recovery admitted `= 3020.050 eps`
  - `4xx = 0`
  - `5xx = 0`
  - ingress `p95 = 49.951 ms`
  - ingress `p99 = 58.966 ms`
  - `IEG apply_failure_count = 0`
  - snapshot blocker ids `= []`
- ledger judgment:
  - the RTDL metric family is proven on a fresh coupled scope with material RTDL participation and no accepted fail-closed / quarantine / archive integrity regression.

### Case + Label Management

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| CaseTrigger duplicate suppression correctness | `100%` | case/label telemetry + correctness summary | Phase 3 |
| missed trigger rate | `0` for in-scope case-worthy events in bounded runs | CaseTrigger telemetry | Phase 3 |
| case-open success rate | `100%` for valid case-worthy events | Case Management telemetry | Phase 3 |
| duplicate case creation count | `0` | Case Management telemetry | Phase 3 |
| case-open latency p95 | `<= 5 s` | case/label live telemetry | Phase 3 |
| invalid case-state transition count | `0` | Case Management telemetry | Phase 3 |
| append-only timeline violations | `0` | case timeline validation telemetry | Phase 3 |
| label commit success rate | `100%` for valid bounded inputs | Label Store telemetry | Phase 3 |
| label commit latency p95 | `<= 10 s` | Label Store telemetry | Phase 3 |
| duplicate label corruption count | `0` | Label Store telemetry | Phase 3 |
| conflicting-label visibility | `100%` surfaced, `0` silent overwrite | Label Store telemetry | Phase 3 |
| future-label leakage count | `0` | label maturity / readback telemetry | Phase 3 |

Current proven ledger status:
- accepted plane closure authority:
  - `phase3_case_label_20260311T142813Z`
  - fresh scope `platform_20260311T142813Z`
- key observed closure metrics:
  - admitted `= 3046.783 eps`
  - `4xx = 0`
  - `5xx = 0`
  - `latency_p95_ms = 48`
  - `latency_p99_ms = 55`
  - `case_trigger_triggers_seen_delta = 2276`
  - `case_trigger_published_delta = 2276`
  - `case_mgmt_cases_created_delta = 335`
  - `case_mgmt_timeline_events_appended_delta = 1005`
  - `label_store_accepted_delta = 933`
  - all tracked quarantine / ambiguity / duplicate / mismatch / pending deltas stayed `0`
- ledger judgment:
  - the Case + Label metric family is proven on the bounded plane-ready slice with append-only case truth and authoritative label truth remaining clean.

### Learning + Evolution / MLOps

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| authoritative-world gate compliance | `100%` of bounded proofs use interface-pack-authorized, `6B.S5`-passed worlds only | OFS dataset-basis validation + engine gate evidence | Phase 5 |
| unauthorized dataset basis count | `0` | OFS dataset manifest validation | Phase 5 |
| point-in-time correctness violations | `0` | Databricks dataset validation | Phase 5 |
| future leakage violations | `0` | Databricks dataset validation | Phase 5 |
| label maturity / as-of policy violations | `0` | OFS label-resolution receipts + dataset validation | Phase 5 |
| required supervision coverage policy satisfaction | `100%` for declared label families in bounded proof windows | OFS coverage gate + label-resolution diagnostics | Phase 5 |
| dataset manifest completeness | `100%` | OFS / Databricks outputs | Phase 5 |
| dataset build success rate | `100%` for bounded proof windows | Databricks job telemetry | Phase 5 |
| dataset build duration p95 | `<= 30 min` bounded build window | Databricks job telemetry | Phase 5 |
| offline-learning feature contract violations | `0` | OFS dataset validation + feature contract checks | Phase 5 |
| training success rate | `100%` for bounded proof windows | SageMaker job telemetry | Phase 5 |
| evaluation success rate | `100%` for bounded proof windows | SageMaker job telemetry | Phase 5 |
| training / evaluation reproducibility | within pinned tolerance for repeated bounded basis | SageMaker + MLflow lineage evidence | Phase 5 |
| bounded subgroup/regime evaluation visibility | `100%` for declared critical cohorts | SageMaker eval outputs + MLflow lineage evidence | Phase 6 |
| candidate bundle completeness | `100%` | SageMaker / artifact validation | Phase 5 |
| lineage completeness | `100%` from dataset -> train/eval -> candidate bundle -> active bundle | MLflow / MPR telemetry | Phase 5 |
| promotion evidence completeness | `100%` | MLflow / MPR telemetry | Phase 5 |
| rollback success rate | `100%` in bounded drills | MLflow / MPR telemetry | Phase 5 |
| rollback RTO | `<= 15 min` | rollback drill summary | Phase 5 |
| rollback RPO | `0` model-version ambiguity | rollback drill summary | Phase 5 |
| active-bundle resolution correctness | `100%` | runtime + MLflow / MPR cross-check | Phase 6 |

Current proven ledger status:
- accepted plane-ready authority:
  - semantic admission `phase5_learning_mlops_20260312T054200Z`
  - dataset basis `phase5_ofs_dataset_basis_20260312T054900Z`
  - managed train/eval + governance `phase5_learning_managed_20260312T071600Z`
- accepted coupled authority:
  - `phase6_learning_coupled_20260312T194748Z`
- key observed closure metrics:
  - bounded sample:
    - `selected_rows = 3000`
    - `train_rows = 1800`
    - `validation_rows = 600`
    - `test_rows = 600`
    - `fraud_rows = 1000`
    - `campaign_present_rows = 2`
  - temporal proof:
    - `feature_asof_utc = 2026-03-05T00:00:00Z`
    - `event_scan.ts_max_utc = 2026-03-04T22:25:01.492086Z`
  - managed execution:
    - SageMaker training `Completed`
    - SageMaker transform `Completed`
    - MLflow run `FINISHED`
    - `gate_decision = PASS`
    - `publish_decision = ELIGIBLE`
    - `publication_status = PUBLISHED`
    - `rollback_validation_status = VALIDATED`
  - bounded evaluation:
    - `auc_roc = 0.9104674176699058`
    - `precision_at_50 = 1.0`
    - `log_loss = 0.21071451840777855`
  - coupled runtime resolution:
    - steady `3047.367 eps`
    - burst `6099.000 eps`
    - recovery `3019.894 eps`
    - `4xx = 0`
    - `5xx = 0`
    - `decision_to_case p95 = 0.0 s`
    - `case_to_label p95 = 0.196 s`
- ledger judgment:
  - the learning / evolution metric family is proven both as a managed corridor and as an active runtime bundle-resolution path coupled back into the working network.

### Operations / Governance / Meta

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| run identity uniqueness | `100%` | run control telemetry | Phase 7 |
| receipt completeness | `100%` for required receipts | run control / reporter telemetry | Phase 7 |
| evidence readback success | `100%` | evidence readback checks | Phase 7 |
| verdict traceability | `100%` from verdict -> evidence -> run scope | reporter / governance telemetry | Phase 7 |
| mutation violations on governance facts | `0` | governance append telemetry | Phase 7 |
| metric freshness | within declared plane budget, no stale critical dashboards | observability telemetry | Phase 7 |
| critical alert coverage | `100%` for declared failure families | dashboard / alarm validation | Phase 7 |
| unattributed spend | `0` | cost guardrail telemetry | Phase 7 |
| residual non-essential compute after idle | `0` | teardown / residual scan | Phase 7 |
| placeholder handle count | `0` in active runtime path | handle-resolution telemetry | Phase 7 |
| required secret/handle resolution success | `100%` | control/runtime preflight telemetry | Phase 7 |

Current proven ledger status:
- accepted closure authority:
  - `phase7_ops_gov_meta_restart_20260313T002459Z`
- key observed closure metrics:
  - required local evidence `= 10 / 10`
  - accepted Phase 5 refs readable `= 18 / 18`
  - critical alarms present `= 6`
  - alert drill recorded `OK -> ALARM -> OK` on `fraud-platform-dev-full-ig-lambda-errors`
  - required handle / secret surfaces resolved `= 11 / 11`
  - placeholder-like active handles `= 0`
  - node count after idle `= 0`
  - nodegroup restored to pre-drill shape
  - visible major spend families remained attributable:
    - `RDS`
    - `S3`
    - `MSK`
    - `DynamoDB`
    - `Lambda`
    - `API Gateway`
- ledger judgment:
  - the operations / governance / meta metric family is proven on a rebuilt plane-ready scope with real alert drill evidence, exact run reconstruction, ML day-2 readback, and idle / restore discipline.

### Full-platform cross-plane

| Metric | Current target | Evidence surface | Owning phase |
|---|---|---|---|
| run identity continuity across active planes | `100%` | integrated live telemetry | Phase 8 |
| truth continuity across critical paths | `100%`, no silent handoff break | integrated live telemetry + summaries | Phase 8 |
| timing continuity across critical paths | all active paths within their declared budgets | integrated live telemetry | Phase 8 |
| silent starvation count | `0` | integrated live telemetry | Phase 8 |
| full-platform bounded recovery | `<= 180 s` unless a path declares a tighter budget | integrated recovery telemetry | Phase 8 |
| explainability / audit completeness | `100%` for accepted decisions and promoted bundles in bounded runs | integrated evidence readback | Phase 8 |
| stress authorization posture | no red plane, no red critical path, no invalidating telemetry blind spot | integrated stress summary | Phase 9 |

Current proven ledger status:
- accepted bounded integrated authority:
  - `phase8_full_platform_integrated_20260313T010847Z`
- accepted bounded stress authority:
  - `phase9_full_platform_stress_20260313T203100Z`
  - widened backbone `phase6_learning_coupled_20260313T203100Z`
- key integrated metrics:
  - Phase 8 steady `= 3049.811 eps`
  - Phase 8 burst `= 6188.000 eps`
  - Phase 8 recovery `= 3019.217 eps`
  - Phase 8 integrity deltas all `0`
  - Phase 8 `decision_to_case p95 = 0.0 s`
  - Phase 8 `case_to_label p95 = 0.1982594 s`
- key stress-authorization metrics:
  - admitted `= 2,360,103`
  - steady `= 3007.053 eps`
  - burst `= 6359.000 eps`
  - recovery `= 3017.517 eps`
  - steady `p95 = 47.9935 ms`
  - steady `p99 = 59.9765 ms`
  - runtime participation remained material:
    - `df_decisions_total_delta = 9095`
    - `al_intake_total_delta = 6061`
    - `dla_append_success_total_delta = 11066`
    - `case_trigger_triggers_seen_delta = 8505`
    - `case_mgmt_cases_created_delta = 2079`
    - `label_store_accepted_delta = 2693`
  - critical integrity deltas stayed `0`
  - active bundle remained attributable to governed learning truth:
    - `bundle_version = v0-29d2b27919a7`
    - `policy_revision = r3`
- ledger judgment:
  - the full-platform cross-plane metric family is proven both on bounded integrated correctness and on widened bounded stress authorization, including semantic continuity under pressure.

---

## Current baseline
The baseline now established under this plan is:
- `Control + Ingress`: promoted working-platform member
- `RTDL`: promoted working-platform member after fresh-scope Phase 1 closure on `2026-03-11`
- `Case + Label`: promoted working-platform member after bounded Phase 3 plane closure on `2026-03-11` and coupled Phase 4 closure on `2026-03-12`
- `Learning + Evolution / MLOps`: promoted working-platform member after rebuilt Phase 5 closure on `2026-03-12` and coupled Phase 6 closure on `2026-03-12`
- `Ops / Gov / Meta`: promoted working-platform member after rebuilt Phase 7 plane closure on `2026-03-13` and integrated Phase 8 closure on `2026-03-13`

That means the current working platform is:
- `Control + Ingress + RTDL + Case + Label + Learning + Evolution / MLOps + Ops / Gov / Meta`

Everything else remains to be proven under this plan.

---

## Phase sequence overview

## Phase 0 - Control + Ingress revalidation
Purpose:
- reconfirm the current working-platform member under the bounded-production method before coupling anything else to it.

Phase expansion document:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.phase0.md`

Why this phase exists:
- earlier evidence is strong, but the working platform must be established under the exact method this plan will use for every other plane.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Control & Ingress Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- steady and burst throughput at the current declared envelope
- p95 and p99 ingress latency
- `4xx` and `5xx` leakage for valid traffic
- duplicate correctness and publish continuity
- recovery time after bounded disturbance

Qualitative proof focus:
- run identity continuity from control into ingress
- deterministic admission, dedupe, and publish behavior
- receipt and quarantine truth that remains reconstructable
- no deployment-drift mismatch between the intended ingress path and the live ingress path

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
- the steady-state verdict is repeatable on the same truthful run shape rather than dependent on ad hoc reshaping

Telemetry plan:
- live logs:
  - World Streamer Producer (WSP)
  - Ingress Lambda / ECS admission shell
  - API edge and target health events
- live progress counters:
  - admitted rate
  - duplicate rate
  - publish success / retry / ambiguity counts
  - `4xx` / `5xx`
  - p95 / p99 latency
- live boundary health:
  - run-scope continuity from control into ingress
  - ingress dedupe ledger writes
  - Kafka publish continuity and topic movement
- fail-fast triggers:
  - early `5xx` or timeout growth above bounded red threshold
  - duplicate-heavy windows caused by stale run identity
  - admitted-without-publish evidence
  - healthy edge requests with no downstream bus movement
- hardening artifacts:
  - one run manifest
  - one live summary
  - one optional metric snapshot
  - one implementation-note entry

Current closeout posture:
- the semantically trustworthy unsynchronized bounded run shape is the current `Phase 0.B` baseline
- the remaining blocker is proof-boundary stability at the steady admitted-throughput gate, not a currently active ingress semantic defect
- synchronized-start and unstable warmed single-bin probes are diagnostic evidence only and must not become the promotion baseline
- `Phase 0` should close through:
  - telemetry lock on the active ingress path,
  - one frozen truthful steady-state baseline,
  - repeatable green bounded correctness on that same baseline,
  - only then bounded burst / recovery proof
- if the frozen truthful baseline stays red after the measurement boundary is made explicit, the red must be treated as a real capacity or hot-path defect and remediated narrowly before promotion

Definition of done:
- Control + Ingress is reconfirmed as the working-platform base
- any regressions are fixed before Phase 1 starts

---

## Phase 1 - RTDL plane readiness
Purpose:
- prove RTDL on its own production criteria using the minimum real upstream dependencies it requires.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Real-Time Decision Loop (RTDL) plane production-ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- consumer lag and checkpoint age
- feature freshness and restart-to-green time
- decision latency
- fail-closed, quarantine, append failure, replay divergence, and archive write-error rates

Qualitative proof focus:
- context correctness
- feature correctness
- fail-closed only for real insufficiency
- append-only audit and archive truth
- replay, duplicate, and restart safety for RTDL truth surfaces

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

Semantic references for this phase:
- `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
  - behavioural stream roles
  - join map for behavioural streams
  - time-safe guidance
  - truth-product boundaries
- `docs/model_spec/data-engine/implementation_maps/segment_5B.build_plan.md`
  - upstream arrival realism and civil-time quality expectations for `arrival_events_5B`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s5.expanded.md`
  - arrival-layer validation and gate posture
- `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
  - behavioural stream, overlay, and truth-product realism expectations
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
  - authoritative 6B outputs, coverage, and validation bundle posture

Telemetry plan:
- live logs:
  - Context Store Flow Binding (CSFB)
  - Identity Entity Graph (IEG)
  - Online Feature Plane (OFP)
  - Degrade Ladder (DL)
  - Decision Fabric (DF)
  - Action Layer (AL)
  - Decision Log Audit (DLA)
  - Archive Writer
- live progress counters:
  - current-run participation by component
  - consumer lag and checkpoint age by component
  - OFP freshness / feature-ready counters
  - DL degrade-reason breakdown
  - DF decision / fail-closed / quarantine breakdown
  - AL outcome counts
  - DLA append / unresolved-age posture
  - Archive Writer write counts and error counts
- live boundary health:
  - run-scope adoption in every RTDL worker
  - behavioural-stream topics moving
  - OFP materializing run-scoped features
  - DLA and archive stores receiving current-run writes
- fail-fast triggers:
  - no current-run RTDL participation after bounded warm window
  - lag/checkpoint age crossing early red bounds
  - OFP freshness or feature readiness staying dark
  - DF fail-closed or quarantine spiking from a healthy upstream window
  - DLA append failures or replay divergence appearing early
- hardening artifacts:
  - one run manifest
  - one live summary
  - one optional RTDL metric snapshot
  - one implementation-note entry

Definition of done:
- RTDL is plane-ready
- all known RTDL semantic, replay, freshness, and lineage defects for the bounded run shape are resolved

---

## Phase 2 - Control + Ingress + RTDL coupled-network readiness
Status:
- closed green by completion inside `Phase 1.B` and `Phase 1.C`

Planning note:
- this phase's goal was satisfied by the fresh-scope RTDL promotion proof that closed on `2026-03-11`
- no separate standalone rerun is required here, because the coupled-network validation already became the evidence used to promote `Control + Ingress + RTDL` into the working platform

Purpose:
- prove the first real working network beyond Control + Ingress.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> The critical cross-plane paths`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- ingress throughput and latency under live RTDL consumption
- RTDL lag, decision latency, and append/archive integrity under real admitted pressure
- bounded recovery time for the combined network

Qualitative proof focus:
- Control -> Ingress identity continuity
- Ingress -> Event Bus publication continuity
- Event Bus -> RTDL truth continuity
- no false-green caused by downstream starvation or stale run scope

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

Telemetry plan:
- live logs:
  - ingress edge and admission shell
  - RTDL workers with emphasis on DF, OFP, DLA
- live progress counters:
  - admitted rate vs RTDL current-run participation
  - ingress latency/error posture
  - RTDL lag / checkpoint / decision counters
  - DLA append and archive rates
- live boundary health:
  - Control -> Ingress run identity continuity
  - Ingress -> Event Bus publication continuity
  - Event Bus -> RTDL consumption continuity
- fail-fast triggers:
  - healthy ingress with dark RTDL participation
  - RTDL red despite healthy bus movement and healthy ingress
  - evidence of stale run scope on either side of the boundary
- hardening artifacts:
  - one run manifest
  - one coupled-network summary
  - one optional cross-plane metric snapshot
  - one implementation-note entry

Definition of done:
- `Control + Ingress + RTDL` becomes the working platform
- the production paths introduced by RTDL are marked as working in reflected artifacts

---

## Phase 3 - Case + Label plane readiness
Purpose:
- prove Case + Label on its own production criteria using the already-working upstream decision surfaces.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Case & Label Management Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- trigger precision and recall
- case-open and case-transition latency
- duplicate case-creation rate
- label commit latency
- label idempotency and conflicting-label visibility

Qualitative proof focus:
- correct escalation from decision truth to case intent
- append-only case timeline truth
- append-only label truth
- strict truth ownership between CaseTrigger, Case Management, and Label Store
- no future-label leakage

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

Semantic references for this phase:
- `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
  - truth products
  - `s4_event_labels_6B`
  - `s4_flow_truth_labels_6B`
  - `s4_flow_bank_view_6B`
  - `s4_case_timeline_6B`
  - join map from RTDL outputs toward truth products
- `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
  - truth-label and case-timeline realism expectations
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
  - authoritative case and label output surfaces and validation posture

Telemetry plan:
- live logs:
  - CaseTrigger
  - Case Management (CM)
  - Label Store (LS)
  - immediate RTDL publishers feeding them
- live progress counters:
  - trigger intake counts
  - case-open counts
  - case-transition counts
  - label pending / accepted / rejected counts
  - duplicate suppression and conflict counters
- live boundary health:
  - RTDL -> CaseTrigger event movement
  - case timeline writes
  - label-store commits and readback
  - run-scope continuity into case/label outputs
- fail-fast triggers:
  - case/label workers healthy but zero current-run participation
  - duplicate case creation or duplicate label corruption
  - missing case timeline writes for valid case-worthy traffic
  - conflicting labels being silently overwritten
- hardening artifacts:
  - one run manifest
  - one case/label live summary
  - one optional case/label metric snapshot
  - one implementation-note entry

Definition of done:
- Case + Label is plane-ready
- no shadow truth ownership exists between Case Management and Label Store

Status:
- closed green on `2026-03-11`

Closure metrics:
- closure scope `phase3_case_label_20260311T142813Z`
- `observed_admitted_eps = 3046.783`
- `admitted_request_count = 182807`
- `4xx = 0`
- `5xx = 0`
- `latency_p95_ms = 48`
- `latency_p99_ms = 55`
- CaseTrigger / Case Management / Label Store integrity deltas all clean on the bounded slice
- promoted upstream base scored `PASS`

---

## Phase 4 - Working network + Case + Label coupled readiness
Purpose:
- prove the enlarged network once Case + Label is attached.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Case & Label Management Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> The critical cross-plane paths`

Quantitative proof focus:
- decision-to-case latency
- case-to-label latency
- case and label throughput under real upstream pressure
- starvation count across RTDL -> Case/Label boundaries

Qualitative proof focus:
- RTDL outputs remain usable as operational truth
- duplicate-safe case and label formation under load
- case and label lineage remain linked to upstream RTDL truth
- no regression of the already-working `Control + Ingress + RTDL` network

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

Telemetry plan:
- live logs:
  - RTDL publishers into CaseTrigger
  - CaseTrigger
  - Case Management
  - Label Store
- live progress counters:
  - decision-to-case counts and latency
  - case-to-label counts and latency
  - starvation counters across RTDL -> case/label boundaries
- live boundary health:
  - RTDL outputs producing case-worthy traffic
  - case truth and label truth remaining linked to upstream decision truth
- fail-fast triggers:
  - RTDL healthy but case/label dark
  - case activity without label-store truth
  - regressions in RTDL latency or fail-closed posture caused by the new coupling
- hardening artifacts:
  - one run manifest
  - one coupled-network summary
  - one optional cross-plane snapshot
  - one implementation-note entry

Definition of done:
- `Control + Ingress + RTDL + Case + Label` becomes the working platform
- case and label paths are promoted into the working network

---

## Phase 5 - Learning + Evolution / MLOps plane readiness
Purpose:
- prove the managed learning corridor on its own production criteria.
- prove that the managed learning corridor is learning from semantically valid, sealed, point-in-time-correct truth rather than merely producing artifacts on healthy infrastructure.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes Learning & Evolution Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- dataset build duration and success
- authoritative-world admission and dataset-basis compliance
- leakage violations
- label coverage and maturity-policy satisfaction
- train/eval duration and success
- bounded cohort and regime evaluation visibility
- candidate bundle completeness
- promotion evidence completeness
- rollback success and rollback RTO/RPO

Qualitative proof focus:
- authoritative runtime and label truth as the only learning basis
- interface-pack discipline: behavioural streams, behavioural context, and truth products must not be mixed casually
- `6B.S5` green world admission as a hard gate for any training/eval basis that depends on 6B behaviour/labels/cases
- point-in-time correctness
- label as-of and maturity correctness
- supervision fitness: labels, case-linked truth, and regime coverage are materially usable for learning, not merely present
- feature admissibility: offline features are built from allowed offline surfaces and do not smuggle future-derived or RTDL-unsafe fields into training
- model-fit discipline: bounded training/evaluation must be interpretable against the actual fraud/legit structure, label families, and cohort behaviour in the admitted data
- lineage completeness from dataset to candidate bundle
- deterministic active-bundle resolution through the managed corridor
- no hidden local or script-only path making learning appear healthy

Scope:
- `Databricks (Offline Feature Plane / OFS)`
- `SageMaker (Model Factory / MF)`
- `MLflow (Model Promotion and Registry / MPR)`

Dependencies allowed:
- working platform from Phase 4 as source of runtime and label truth
- Data Engine interface pack as the only allowed semantic authority for downstream engine consumption
- `6B` sealed truth products and `6B.S5` validation artefacts for learning/evaluation admission decisions
- `5B` sealed-input / catalogue posture as the model for evidence discovery and non-ad-hoc dataset resolution
- managed learning surfaces
- required evidence and registry surfaces

Run shape:
- bounded learning slice, not a giant corpus replay
- enough authoritative runtime truth and label truth to exercise:
  - world admission and basis gating
  - dataset build semantics
  - feature and label admissibility
  - supervision coverage and maturity checks
  - train/eval lineage
  - cohort-aware evaluation and model-fit reasoning
  - candidate bundle production
  - promotion / rollback / active-bundle resolution
- typical starting scale:
  - `100k to 500k` labeled rows
  - bounded build and train/eval windows

Primary questions:
- are admitted worlds and datasets authorized by the interface pack and sealed `6B.S5` gates, or are we learning from ungoverned surfaces?
- are datasets built from authoritative runtime and label truth only?
- is point-in-time correctness preserved?
- are label as-of and maturity rules enforced strongly enough that the supervision basis is trustworthy?
- do the resulting datasets retain materially useful class, subtype, campaign, and case-linked coverage for bounded learning?
- are the selected model families and evaluation criteria justified by the actual admitted data rather than by tooling convenience?
- does SageMaker train/eval from the right basis?
- does MLflow provide deterministic active-bundle resolution, promotion evidence, and rollback discipline?

Focus metrics:
- dataset build success / duration / leakage violations
- authoritative-world admission and dataset-basis compliance
- label as-of / maturity policy compliance
- supervision coverage by required label family / cohort
- offline feature admissibility and contract violations
- manifest completeness and fingerprint stability
- training / evaluation success and bounded duration
- bounded evaluation visibility across critical fraud / legit regimes and cohorts
- bundle completeness and provenance completeness
- promotion evidence completeness
- rollback success and rollback RTO / RPO

Semantic references for this phase:
- `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
  - truth-product boundaries
  - time-safe guidance
  - no-PASS-no-read gate posture
- `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`
  - gate verification and instance-proof posture for authoritative engine outputs
- `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
  - labelled runtime truth expectations and downstream training/evaluation suitability
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
  - 6B validation bundle and `_passed.flag` as world-level learning-read gates
- `docs/model_spec/data-engine/implementation_maps/segment_5B.build_plan.md`
  - sealed-input, catalogue, and non-ad-hoc evidence-discovery discipline
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s5.expanded.md`
  - bundle / flag / catalogue posture for trustworthy dataset discovery and evidence pinning

Telemetry plan:
- live logs:
  - Databricks job output for the Offline Feature Plane (OFS)
  - SageMaker training / evaluation job logs for the Model Factory (MF)
  - MLflow / Model Promotion and Registry (MPR) promotion and rollback events
- live progress counters:
  - admitted world count vs rejected world count by gate reason
  - dataset row counts and build stage progress
  - label-family coverage and maturity counters
  - feature admissibility and leakage-check counters
  - train/eval job state and durations
  - critical cohort / regime evaluation completion counters
  - candidate bundle creation progress
  - promotion / rollback counts and state
- live boundary health:
  - every admitted learning basis resolves through declared dictionary / registry / gate surfaces
  - authoritative dataset basis present and gated
  - label truth available with maturity semantics
  - offline feature basis remains leakage-safe and contract-valid
  - active-bundle resolution present and readable
- fail-fast triggers:
  - any admitted world lacks the required `6B.S5` green gate
  - point-in-time or leakage violation detected
  - supervision basis falls below declared coverage or maturity policy
  - train/eval running on non-authoritative dataset basis
  - critical cohort / regime evaluation missing or unreadable
  - promotion attempt without complete lineage
  - rollback path unavailable or unresolved
- hardening artifacts:
  - one run manifest
  - one learning/MLOps live summary
  - one optional lineage snapshot
  - one implementation-note entry

Definition of done:
- Learning + Evolution / MLOps is plane-ready
- no hidden local or script-only learning path is required for the managed corridor to function

---

## Phase 6 - Working network + Learning coupled readiness
Purpose:
- prove the platform feedback loop once learning is attached to the working network.
- prove that the runtime -> case/label -> learning -> promoted bundle -> runtime loop remains semantically stable, leakage-safe, explainable, and operationally useful once it becomes one coupled network.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes Learning & Evolution Plane Production Ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> The critical cross-plane paths`

Quantitative proof focus:
- bounded dataset-build, train/eval, and promotion timings within the same proof window
- active-bundle resolution correctness at runtime
- rollback execution within declared bounds
- bounded cohort/regime evaluation visibility on the same admitted truth basis

Qualitative proof focus:
- runtime-to-label-to-learning truth continuity
- learning-to-runtime feedback continuity
- replay-to-dataset correctness
- no semantic drift between authoritative label truth, learning basis, promoted bundle behaviour, and runtime interpretation
- bounded evidence that model evolution changes something meaningful on valid supervision rather than merely changing versions
- explainable bundle adoption: the platform can name the admitted world, label basis, feature basis, eval result, and promotion reason behind the active bundle
- no drift between promoted bundle truth and runtime decision authority

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
- does the enlarged network preserve semantic meaning across that loop, or does the learning corridor reinterpret/flatten the truth in ways the runtime cannot justify?
- can the platform explain which dataset and bundle influenced a runtime decision?
- can the platform show that the promoted bundle was trained and evaluated on admissible, mature, coverage-sufficient truth?
- can the platform surface bounded cohort / regime behaviour so model evolution is not accepted on aggregate-only optics?
- can it roll back without ambiguity?

Telemetry plan:
- live logs:
  - Databricks / SageMaker / MLflow plus the runtime consumer of active bundle truth
- live progress counters:
  - admitted world / dataset / bundle lineage checkpoints
  - dataset-build / train-eval / promotion timing
  - cohort/regime evaluation completion and summary counters
  - active-bundle resolution status
  - rollback timing and success
- live boundary health:
  - runtime-to-label-to-dataset continuity
  - learning basis remains interface-pack-authorized and `6B.S5`-gated through promotion
  - promoted bundle visible to runtime
  - runtime decision evidence can be traced back to dataset / label / bundle basis
  - rollback path restoring prior active truth
- fail-fast triggers:
  - active bundle not matching promoted truth
  - runtime cannot resolve the managed bundle
  - promoted bundle lacks readable cohort / regime evaluation or admissible basis evidence
  - learning lineage complete on paper but unreadable in runtime
  - runtime feedback loop is operationally green but semantically unattributable
- hardening artifacts:
  - one run manifest
  - one coupled-network summary
  - one optional runtime/learning lineage snapshot
  - one implementation-note entry

Definition of done:
- `Control + Ingress + RTDL + Case + Label + Learning + Evolution / MLOps` becomes the working platform
- the runtime-to-learning feedback loop is production-credible

---

## Phase 7 - Operations / Governance / Meta readiness
Purpose:
- prove the platform can be operated, audited, governed, and cost-controlled with the same rigor that it is executed.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the Operations / Governance / Meta layer production-ready?`
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- receipt completeness
- evidence readback success
- alert coverage and metric freshness
- cost attribution completeness
- residual non-essential compute after idle/teardown

Qualitative proof focus:
- exact run reconstruction
- verdict traceability back to evidence
- drift detection before false certification
- safe idle and restart posture
- governed, attributable, and bounded operational behavior
- ML day-2 monitoring ownership:
  - data-quality drift visibility on admitted runtime and learning surfaces
  - active-bundle / model-behaviour monitoring visibility
  - bounded drift-to-mitigation operator actions and runbooks
  - audit response continuity from runtime decision -> active bundle -> admitted dataset basis

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
- active learning/runtime operator surfaces:
  - promoted bundle observability
  - data-quality / model-behaviour drift readbacks
  - drift-mitigation control path

Run shape:
- bounded operational proof on top of the working platform from Phase 6
- no need for giant data volume; focus is correctness, coverage, and operational usefulness

Primary questions:
- can runs be reconstructed exactly?
- can verdicts be justified from evidence?
- can drift be detected before false certification happens?
- is spend attributable and controllable?
- can the platform safely idle and restart?
- can operators see and react to learning/runtime drift before it becomes silent model damage?

Telemetry plan:
- live logs:
  - run-control and reporter surfaces
  - governance append / evidence write surfaces
  - teardown / residual scan outputs
- live progress counters:
  - receipt and evidence emission counts
  - dashboard freshness
  - alert fire / clear counts
  - attributable spend views
  - residual compute counts
  - data-quality / model-behaviour drift counters where the live platform exposes them
- live boundary health:
  - exact run reconstruction possible from current-run evidence
  - active drift checks reading the same runtime surfaces the platform actually uses
  - idle/teardown actions visible and reversible
- fail-fast triggers:
  - missing run receipts
  - evidence holes on active run
  - unattributed spend during active proof
  - drift detected between live runtime and declared active path
  - missing critical alert coverage for declared failure families
- hardening artifacts:
  - one run manifest
  - one ops/gov live summary
  - one optional evidence/compliance snapshot
  - one implementation-note entry

Definition of done:
- Operations / Governance / Meta is plane-ready
- all working-platform planes are now governable and operable as one system

---

## Phase 8 - Full-platform bounded integrated validation
Purpose:
- validate the entire working platform as one network before authorizing heavier stress.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> The critical cross-plane paths`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- bounded integrated throughput, latency, lag, recovery, and error posture across the full network
- bounded integrated case, label, learning, and governance timings where relevant

Qualitative proof focus:
- full-platform truth continuity
- full-platform timing continuity
- full-platform explainability and auditability
- no hidden handoff defect across any active plane boundary

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

Telemetry plan:
- live logs:
  - active-plane logs across all working-platform planes
  - operator-facing governance and evidence surfaces
- live progress counters:
  - ingress, RTDL, case/label, learning, and ops/gov summaries in one watch surface
  - cross-plane path health and timing continuity
- live boundary health:
  - all critical cross-plane paths materially participating on the same run
  - no plane appears green because another plane stopped doing real work
- fail-fast triggers:
  - any active plane dark while upstream is hot
  - any critical cross-plane path loses run identity or truth continuity
  - observability/evidence defects large enough to invalidate the integrated verdict
- hardening artifacts:
  - one run manifest
  - one integrated live summary
  - one optional whole-platform metric snapshot
  - one implementation-note entry

Definition of done:
- the whole platform is bounded-correct
- no unresolved red remains that would invalidate later stress authorization

---

## Phase 9 - Full-platform bounded stress authorization
Purpose:
- determine whether the now-working platform deserves a longer stress or soak run.

Production-readiness anchor:
- `platform.production_readiness.md -> What makes the platform as a whole production-ready?`
- `platform.production_readiness.md -> Production paths that exist in the platform`

Quantitative proof focus:
- latency tails under widened pressure
- fail-closed, quarantine, lineage, case, label, learning, and ops metrics under bounded full-platform stress
- recovery behavior under widened stress

Qualitative proof focus:
- the full platform remains semantically trustworthy under the widened pressure window
- outputs remain meaningful, explainable, and auditable
- RTDL decision and action outputs remain explainable under widened pressure
- Case + Label truth remains authoritative under widened pressure
- the active runtime bundle remains tied to a meaningful governed learning basis rather than a hollow green train/eval story
- no plane only appears green because another plane silently stopped doing real work

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
- do RTDL, Case + Label, and learning/runtime bundle truth still handle the information within the data meaningfully rather than merely continue to emit traffic?

Telemetry plan:
- live logs:
  - all active planes with emphasis on the currently tightest bottlenecks
- live progress counters:
  - full-platform latency tails
  - fail-closed / quarantine / lineage / case / label / learning / governance counters
  - recovery counters during widened pressure
  - RTDL decision / action participation
  - case / label semantic continuity counters
  - learning-basis / active-bundle continuity readbacks
- live boundary health:
  - full-platform participation remains real under widened stress
  - no critical path is silently bypassed or starved
  - RTDL decision truth, case truth, label truth, and active-bundle truth remain attributable on the same widened run story
- fail-fast triggers:
  - clear early miss of target envelope
  - tail latency or error posture already beyond recoverable bound
  - a critical plane stops materially participating
  - decision / case / label / bundle meaning becomes unreadable or internally contradictory
- hardening artifacts:
  - one run manifest
  - one stress live summary
  - one optional stress metric snapshot
  - one implementation-note entry

Definition of done:
- long stress or soak is authorized only if this phase is green
- if not green, the platform is still not production-ready regardless of how clean the wiring looks

---

## Per-phase operating rules
These rules apply to every phase above.

### 1. Telemetry before execution
No phase or phase subsection may execute until its telemetry plan is pinned and materially available:
- log tail,
- live counters,
- boundary-health checks,
- fail-fast conditions.

### 2. Fail fast
The run stops as soon as the active boundary has enough evidence to show:
- a correctness defect,
- a semantic defect,
- a path defect,
- a deployment drift issue,
- or an observability defect large enough to invalidate the verdict.

### 3. Fix narrow, rerun narrow
When a phase fails:
- fix the specific defect,
- rerun the smallest legitimate boundary,
- do not rerun the whole platform unless the defect actually spans it.

### 4. Keep the platform AWS-real
The runtime proof must happen on the actual platform surfaces:
- ingress on ingress surfaces,
- RTDL on RTDL runtime,
- learning on managed learning surfaces,
- ops/governance on the real evidence and control surfaces.

### 5. Keep the workspace clean
- durable evidence goes to `runs/`
- temporary diagnosis artifacts do not accumulate in repo root
- notes go to implementation maps and logbook, not ad hoc scratch dumps unless explicitly temporary

### 6. Update reflected artifacts only after proof
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
The plan is now closed on the bounded production-readiness standard.

Accepted final authority:

- full-platform bounded integrated validation:
  - `phase8_full_platform_integrated_20260313T010847Z`
- full-platform bounded stress authorization:
  - `phase9_full_platform_stress_20260313T203100Z`
- fresh widened runtime-learning backbone behind the accepted stress closure:
  - `phase6_learning_coupled_20260313T203100Z`

The current promoted working platform is:

- `Control + Ingress + RTDL + Case + Label + Learning + Evolution / MLOps + Ops / Gov / Meta`

Current judgment:

- `dev_full` is production-ready on the bounded authorization standard defined by this plan
- later longer stress / soak is now authorized because the full platform remained production-credible under widened bounded pressure
- that authorization is not based on wiring alone; it is based on one continuous stress story where:
  - throughput, latency, integrity, and recovery stayed green
  - RTDL decision / action truth remained explainable
  - Case + Label truth remained authoritative
  - active runtime bundle truth stayed tied to the governed learning basis
  - operator and governance challenge stayed live and attributable

Any later longer stress / soak work should therefore begin from the accepted `Phase 9` authority rather than reopening earlier bounded phase questions unless a new defect appears.

---

## AWS cost snapshot (`2026-03-01` to `2026-03-13`)

This snapshot is included because production readiness in this repo explicitly includes cost discipline, and the phase work materially changed the cost profile over time.

Source:
- AWS Cost Explorer
- metric: `UnblendedCost`
- granularity: `DAILY`
- group-by: `SERVICE`
- query window: `2026-03-01` through `2026-03-13`

Caveat:
- all returned days were still marked `Estimated=true` at query time
- this is AWS-only and does not pretend to cover non-AWS control planes unless separately captured

### Daily totals

| Date | Total USD | Estimated |
|---|---:|---|
| 2026-03-01 | `668.81` | `true` |
| 2026-03-02 | `38.18` | `true` |
| 2026-03-03 | `33.43` | `true` |
| 2026-03-04 | `34.82` | `true` |
| 2026-03-05 | `33.34` | `true` |
| 2026-03-06 | `196.21` | `true` |
| 2026-03-07 | `619.83` | `true` |
| 2026-03-08 | `564.86` | `true` |
| 2026-03-09 | `190.50` | `true` |
| 2026-03-10 | `275.10` | `true` |
| 2026-03-11 | `533.49` | `true` |
| 2026-03-12 | `317.49` | `true` |
| 2026-03-13 | `302.72` | `true` |

### Service totals so far

| Service | Total USD |
|---|---:|
| Amazon DynamoDB | `858.61` |
| Tax | `634.80` |
| Amazon Elastic Container Service | `434.71` |
| Amazon Managed Streaming for Apache Kafka | `358.42` |
| AWS Lambda | `275.76` |
| Amazon Relational Database Service | `261.95` |
| Amazon API Gateway | `243.99` |
| Amazon Simple Storage Service | `234.68` |
| AmazonCloudWatch | `186.67` |
| Amazon Elastic Compute Cloud - Compute | `143.59` |
| EC2 - Other | `71.57` |
| Amazon Virtual Private Cloud | `46.93` |
| Amazon Elastic Container Service for Kubernetes | `29.82` |
| Amazon Kinesis | `11.77` |
| Amazon Elastic Load Balancing | `6.29` |
| Amazon Elastic MapReduce | `3.74` |
| Amazon Athena | `1.74` |
| Amazon Kinesis Analytics | `1.74` |
| AWS Key Management Service | `0.93` |
| AWS Cost Explorer | `0.56` |
| Amazon EC2 Container Registry (ECR) | `0.46` |
| Amazon SageMaker | `0.05` |

### Daily breakdown by major service

| Date | DynamoDB | ECS | MSK | Lambda | RDS | API GW | S3 | CloudWatch | EC2 Compute | EC2 Other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-03-01 | `0.00` | `0.00` | `21.00` | `0.00` | `1.76` | `0.00` | `0.25` | `0.00` | `4.02` | `0.00` |
| 2026-03-02 | `0.28` | `0.07` | `21.21` | `0.00` | `1.75` | `0.00` | `0.49` | `0.00` | `4.53` | `0.00` |
| 2026-03-03 | `0.10` | `0.00` | `21.25` | `0.00` | `1.76` | `0.00` | `0.28` | `0.00` | `4.54` | `0.00` |
| 2026-03-04 | `0.01` | `0.00` | `22.57` | `0.00` | `1.75` | `0.00` | `0.28` | `0.00` | `4.53` | `0.00` |
| 2026-03-05 | `0.00` | `0.00` | `22.59` | `0.00` | `1.75` | `0.00` | `0.31` | `0.00` | `2.06` | `0.00` |
| 2026-03-06 | `29.71` | `23.90` | `24.48` | `12.67` | `9.63` | `36.81` | `20.02` | `17.49` | `14.81` | `0.01` |
| 2026-03-07 | `213.30` | `175.22` | `42.13` | `0.00` | `52.86` | `0.00` | `34.31` | `71.55` | `18.36` | `0.36` |
| 2026-03-08 | `261.69` | `155.69` | `42.00` | `0.00` | `52.87` | `0.00` | `6.60` | `13.18` | `18.95` | `3.57` |
| 2026-03-09 | `47.84` | `22.07` | `25.75` | `9.19` | `16.53` | `2.00` | `18.92` | `16.03` | `14.14` | `9.89` |
| 2026-03-10 | `77.04` | `9.42` | `30.23` | `59.86` | `8.81` | `42.20` | `15.37` | `13.40` | `5.10` | `5.71` |
| 2026-03-11 | `119.42` | `23.71` | `35.48` | `100.14` | `32.58` | `82.79` | `56.88` | `28.09` | `21.31` | `23.59` |
| 2026-03-12 | `42.73` | `11.69` | `29.07` | `44.54` | `46.90` | `34.87` | `51.60` | `11.53` | `20.48` | `15.00` |
| 2026-03-13 | `66.49` | `12.94` | `20.66` | `49.35` | `32.99` | `45.32` | `29.38` | `15.40` | `10.75` | `13.44` |

### Other services by day

| Date | VPC | EKS | Kinesis | ELB | KMS | Cost Explorer | ECR | SageMaker | Tax |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-03-01 | `2.11` | `2.40` | `0.65` | `0.00` | `0.03` | `0.00` | `0.00` | `0.00` | `634.80` |
| 2026-03-02 | `2.11` | `2.40` | `0.96` | `0.00` | `0.03` | `0.01` | `0.00` | `0.00` | `0.00` |
| 2026-03-03 | `2.11` | `2.40` | `0.96` | `0.00` | `0.03` | `0.00` | `0.00` | `0.00` | `0.00` |
| 2026-03-04 | `2.11` | `2.40` | `0.96` | `0.00` | `0.03` | `0.18` | `0.00` | `0.00` | `0.00` |
| 2026-03-05 | `2.11` | `2.40` | `0.96` | `1.04` | `0.03` | `0.05` | `0.01` | `0.01` | `0.00` |
| 2026-03-06 | `3.20` | `2.40` | `0.96` | `0.00` | `0.05` | `0.00` | `0.02` | `0.00` | `0.00` |
| 2026-03-07 | `5.57` | `2.40` | `0.96` | `2.61` | `0.14` | `0.00` | `0.04` | `0.00` | `0.00` |
| 2026-03-08 | `4.02` | `2.14` | `0.96` | `3.09` | `0.04` | `0.00` | `0.06` | `0.00` | `0.00` |
| 2026-03-09 | `4.17` | `2.28` | `0.96` | `0.59` | `0.07` | `0.00` | `0.07` | `0.00` | `0.00` |
| 2026-03-10 | `4.24` | `2.40` | `0.96` | `0.00` | `0.14` | `0.16` | `0.07` | `0.00` | `0.00` |
| 2026-03-11 | `5.89` | `2.40` | `0.96` | `0.00` | `0.16` | `0.00` | `0.07` | `0.00` | `0.00` |
| 2026-03-12 | `5.42` | `2.40` | `0.96` | `0.00` | `0.10` | `0.09` | `0.07` | `0.03` | `0.00` |
| 2026-03-13 | `3.87` | `1.40` | `0.56` | `0.00` | `0.07` | `0.07` | `0.04` | `0.00` | `0.00` |

### Cost judgment from this snapshot

- the biggest month-to-date AWS accumulator is `Amazon DynamoDB`
- the next material cost families are:
  - `Amazon Elastic Container Service`
  - `Amazon Managed Streaming for Apache Kafka`
  - `AWS Lambda`
  - `Amazon Relational Database Service`
  - `Amazon API Gateway`
  - `Amazon Simple Storage Service`
- `2026-03-09` reflects the materially lower post-teardown / rebuild day compared with the heavier `2026-03-07`, `2026-03-08`, `2026-03-11`, `2026-03-12`, and `2026-03-13` hardening windows
- the `Tax` line on `2026-03-01` is a billing artifact, not a runtime service family
