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

### Current preflight truth for Phase 0.A

The currently pinned live external admission path is:

1. `World Streamer Producer (WSP)` ECS/Fargate ephemeral task family:
   - `fraud-platform-dev-full-wsp-ephemeral`
2. `HTTP API Gateway v2`:
   - API `fraud-platform-dev-full-ig-edge`
   - API ID `pd7rtjze95`
   - stage `v1`
   - route `POST /ingest/push`
3. `Ingress Lambda`:
   - `fraud-platform-dev-full-ig-handler`
4. `DynamoDB` idempotency ledger:
   - `fraud-platform-dev-full-ig-idempotency`
5. Kafka publish boundary:
   - bootstrap brokers from `/fraud-platform/dev_full/msk/bootstrap_brokers`
   - cluster `fraud-platform-dev-full-msk`
6. `SQS` dead-letter queue:
   - `fraud-platform-dev-full-ig-dlq`
7. front-door health endpoint:
   - `GET /ops/health`
   - current response `200` when `X-IG-Api-Key` is supplied
   - current mode `apigw_lambda_ddb_kafka`
   - current declared envelope `3000 / 6000`

Important boundary decision:
- the internal `Ingress ECS service` is **not** the current external front door for `Phase 0`.
- `API Gateway -> Lambda` is the live external admission path.
- the internal ECS ingress surface exists, but it must not be treated as the active external boundary for this phase unless explicitly reactivated and repinned into the run method.

Current live operator-visible surfaces:
- WSP logs:
  - `/ecs/fraud-platform-dev-full-wsp-ephemeral`
- Lambda logs:
  - `/aws/lambda/fraud-platform-dev-full-ig-handler`
- internal ECS ingress logs:
  - `/ecs/fraud-platform-dev-full-ig-service`
- ECS container insights:
  - `/aws/ecs/containerinsights/fraud-platform-dev-full-ingress/performance`
- API Gateway stage throttling:
  - `3000 rate / 6000 burst`
- Lambda envelope:
  - `2048 MB`
  - timeout `30 s`
  - reserved concurrency `600`
- DynamoDB table status:
  - `ACTIVE`
  - `PAY_PER_REQUEST`

Current telemetry gap discovered in preflight:
- API Gateway stage `v1` has `DetailedMetricsEnabled = false`
- no API Gateway access-log group is currently visible
- because of that, the primary live telemetry for the external ingress path must initially come from:
  - Lambda logs and Lambda metrics,
  - DynamoDB idempotency writes,
  - Kafka publish continuity,
  - WSP logs,
  - receipt/quarantine outputs
- not from rich API Gateway stage-level metrics alone

Current telemetry posture:
- API Gateway and Lambda metric namespaces are present and queryable in CloudWatch,
- the queue depth metric for `fraud-platform-dev-full-ig-dlq` is active and currently readable,
- Lambda and WSP log groups are present,
- the front-door health endpoint is live and self-reports the expected ingress mode and envelope,
- recent datapoints are sparse right now because the plane is not actively running,
- `Phase 0.B` therefore needs an intentional fresh bounded run to warm the metric and log surfaces before verdicting them.

Current drift hazard discovered in preflight:
- `/fraud-platform/dev_full/ig/service_url` in SSM still points at the retained internal ALB ingress surface.
- that path must not be allowed to decide the target for `Phase 0.B`.
- the proving wrapper therefore has to pass the execute-api ingress URL explicitly so the active run cannot silently fall back to the retained ALB path.

### Telemetry sub-ledger for Phase 0.A

#### Live logs
- `World Streamer Producer (WSP)`:
  - `/ecs/fraud-platform-dev-full-wsp-ephemeral`
- active ingress runtime:
  - `/aws/lambda/fraud-platform-dev-full-ig-handler`
- secondary retained ingress runtime, for divergence checks only:
  - `/ecs/fraud-platform-dev-full-ig-service`
- front-door and target health events where applicable:
  - API Gateway stage `v1`
  - internal ALB `fp-dev-full-ig-svc`
  - target group `fp-dev-full-ig-svc`

#### Live counters
- admitted rate
- duplicate rate
- valid-traffic `4xx`
- valid-traffic `5xx`
- publish success / retry / unresolved ambiguity counts
- receipt count
- quarantine count
- `p95` / `p99` latency
- Lambda cold-start share
- gate initialization count / `init_seconds`
- request timing split:
  - `auth`
  - `gate`
  - `admit`
  - `response`
  - total request time

Current concrete surfaces:
- API Gateway stage throttling posture
- Lambda `Invocations`, `Errors`, `Throttles`, `Duration`, `ConcurrentExecutions`
- DynamoDB idempotency write growth on the active run window
- SQS DLQ depth on `fraud-platform-dev-full-ig-dlq`
- WSP sent / success / retry posture from task logs
- Kafka publish continuity from ingress logs and receipts

#### Boundary-health checks
- fresh run identity visible through control and ingress
- dedupe ledger writing for the active run
- publish continuity visible at the transport boundary
- run-scoped receipts and quarantine outputs visible

Current concrete checks:
- API Gateway route `POST /ingest/push` resolves to Lambda integration `sm9ahw3`
- Lambda environment is pinned to:
  - `IG_RATE_LIMIT_RPS=3000`
  - `IG_RATE_LIMIT_BURST=6000`
  - `IG_IDEMPOTENCY_TABLE=fraud-platform-dev-full-ig-idempotency`
  - `IG_DLQ_URL=https://sqs.eu-west-2.amazonaws.com/230372904534/fraud-platform-dev-full-ig-dlq`
  - `KAFKA_BOOTSTRAP_BROKERS_PARAM_PATH=/fraud-platform/dev_full/msk/bootstrap_brokers`
  - `KAFKA_REQUEST_TIMEOUT_MS=5000`
  - `IG_HEALTH_BUS_PROBE_MODE=none`
- operator can resolve:
  - `/fraud-platform/dev_full/ig/api_key`
  - `/fraud-platform/dev_full/msk/bootstrap_brokers`
- `GET /ops/health` currently returns:
  - status `ok`
  - service `ig-edge`
  - mode `apigw_lambda_ddb_kafka`
  - profile `dev_full`
  - `rate_limit_rps=3000`
  - `rate_limit_burst=6000`

#### Fail-fast conditions
- no fresh run identity continuity
- admitted traffic with no dedupe or publish continuity
- early valid-traffic `5xx` growth
- early latency-tail blowout
- receipt/quarantine surfaces not producing attributable run-scoped outputs

Concrete early-stop conditions for Phase 0:
- the active run is hitting the internal ECS ingress surface instead of `API Gateway -> Lambda`
- Lambda invocations rise but active-run DynamoDB dedupe writes do not
- Lambda admits traffic but no active-run publish continuity appears in logs/receipts
- valid-traffic `5xx` appears early in the bounded window
- DLQ depth rises for current-run valid traffic
- WSP is sending but the Lambda log stream remains dark for the active run
- abnormal WSP lane tails show `IG_PUSH_REJECTED`, `PUBLISH_AMBIGUOUS`, `IG_UNHEALTHY`, or `KAFKA_PUBLISH_TIMEOUT`
- run-scoped quarantine outputs start growing for valid traffic before the bounded window reaches a stable measurement minute

### Phase 0.A operator loop

The default operator loop for `Phase 0.B` and `Phase 0.C` is:

1. tail the active ingress Lambda:
   - `aws logs tail /aws/lambda/fraud-platform-dev-full-ig-handler --follow --region eu-west-2`
2. tail the active WSP task logs:
   - `aws logs tail /ecs/fraud-platform-dev-full-wsp-ephemeral --follow --region eu-west-2`
3. watch API Gateway stage metrics:
   - `AWS/ApiGateway` for `ApiId=pd7rtjze95`, `Stage=v1`
4. watch Lambda metrics:
   - `Invocations`
   - `Errors`
   - `Throttles`
   - `Duration`
   - `ConcurrentExecutions`
5. watch SQS DLQ depth:
   - `ApproximateNumberOfMessagesVisible`
   - `ApproximateAgeOfOldestMessage`
6. confirm active-run DDB writes on:
   - `fraud-platform-dev-full-ig-idempotency`
7. confirm active-run publish continuity through Lambda log output and receipts
8. probe `GET /ops/health` with `X-IG-Api-Key` before launch so the operator verifies the live mode and envelope on the same authenticated surface the ingress runtime expects

If these surfaces cannot be watched live during the run, the run is not Phase-0-authorized.

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

Default CLI entrypoint for this subphase:
- `python scripts/dev_substrate/phase0_control_ingress_revalidate.py`
- this is a thin proving-plane wrapper over the shared remote WSP replay core
- it writes to:
  - `runs/dev_substrate/dev_full/proving_plane/run_control/`
- default bounded correctness posture:
  - fresh `platform_run_id`
  - fresh `scenario_run_id`
  - duration `90 s`
  - expected admitted throughput `3000 eps`
  - early cutoff `45 s`
- the wrapper must explicitly target the live execute-api ingress URL:
  - `https://pd7rtjze95.execute-api.eu-west-2.amazonaws.com/v1/ingest/push`
  - not the retained internal ALB `service_url` parameter still present in SSM
- when `lane_count` is high enough that the shared dispatcher uses metadata-only lane capture, the bounded-run summary must still retain short abnormal-lane log tails and extracted failure markers so early lane collapse remains attributable from the durable artifact set

### Telemetry sub-ledger for Phase 0.B

#### Metrics / signals to watch
- fresh run identity continuity
- admitted vs duplicate ratio
- admitted-with-publish continuity
- receipt / quarantine coherence
- valid-traffic error rate
- publish ambiguity / quarantine spike rate
- abnormal WSP lane tail markers when metadata-only lane capture is used
- Lambda cold-start rate during the bounded window
- gate initialization frequency / `init_seconds`
- request timing split for successful and abnormal requests
- quarantine reason family for any non-`5xx` abnormal lanes
- fleet confirmation mode and `measurement_start_utc` attribution for the active baseline

#### Success posture
- fresh run ids remain consistent through the active boundary
- duplicate posture is bounded and explainable
- every admitted first-seen event reaches publish continuity
- receipts remain coherent and attributable
- valid traffic has `4xx = 0` and `5xx = 0`
- the steady-state measurement window is explicitly derived from confirmed fleet participation on the same run shape that will be repeated for verdicting
- the same truthful bounded baseline can be repeated without introducing new traffic-shape artifacts

#### Red posture
- stale or reused run identity
- duplicate flood caused by stale scope or bad keying
- admitted-without-publish evidence
- contradictory or missing receipt story
- any unexpected valid-traffic error leakage
- cold-fleet churn large enough to dominate the latency budget
- slow admit-path work even when valid traffic is being admitted successfully
- duplicate/in-flight resolution waiting long enough to turn valid traffic into `QUARANTINE`

Definition of done:
- fresh bounded correctness is green,
- there is no stale-scope contamination,
- the plane is still semantically and operationally coherent before stress.

### Current live `Phase 0.B` status

Fresh execution evidence on `2026-03-10` now separates the runtime truth from the remaining proof-gate truth.

Latest semantically trustworthy bounded reruns:

- execution `phase0_20260310T143110Z`
- admitted throughput `2999.925 eps`
- valid-traffic `4xx = 0`
- valid-traffic `5xx = 0`
- `p95 = 49.576 ms`
- `p99 = 57.463 ms`

- execution `phase0_20260310T143801Z`
- admitted throughput `2999.650 eps`
- valid-traffic `4xx = 0`
- valid-traffic `5xx = 0`
- `p95 = 49.315 ms`
- `p99 = 56.726 ms`

Current judgment:

- `Phase 0.B` is still red
- the active red is no longer explained by ingress semantic failure
- after widening the benign object-store append-conflict handling and redeploying the Lambda, the bounded correctness runs became:
  - semantically clean
  - latency-clean
  - free of valid-traffic `4xx` / `5xx`
- the remaining blocker is now a tiny repeatable throughput shortfall on the proof surface only

One additional note matters for interpretation:

- later diagnostic probes were run specifically to understand that proof-boundary shortfall and should not be mistaken for new baselines:
  - `phase0_20260310T144447Z` (`target_request_rate_eps = 3000.5`) only shifted the miss across metric minutes; it did not prove a runtime defect or a valid correction
  - `phase0_20260310T145355Z` (`lane_log_mode = full`) proved CloudWatch was not lagging and showed the miss was on the order of `1-2` requests per lane across the measured `120 s` window
  - `phase0_20260310T150019Z` (forced synchronized `campaign_start_utc`) caused widespread `503` / quarantine behavior and is not an acceptable proving posture
  - `phase0_20260310T150824Z` (warmup-shaped one-minute probe) also failed and is not an acceptable proving posture

Current engineering interpretation:

- the unsynchronized bounded run shape is still the only semantically trustworthy `Phase 0.B` baseline
- the runtime now looks healthy enough that the active work should move from ingress remediation back to proof-gate remediation
- `Phase 0.B` remains open because the current bounded correctness window is still not measuring a fully stable steady-state minute cleanly enough to support a final green verdict

One additional proving-loop nuance now matters:

- the shared dispatcher had a real fleet-start timing defect when used on large `40`-lane warmup probes
- that defect is now patched so the run summary records how the fleet was confirmed:
  - `all_running`
  - `all_started`
  - or fallback to submission time
- after that fix, a warmed one-bin probe (`phase0_20260310T153432Z`) became semantically clean and nearly on target (`2999.617 eps`)
- but the very next warmed one-bin repeat (`phase0_20260310T154004Z`) reintroduced widespread `IG_PUSH_REJECTED` lane exits and throughput collapse

So the current truthful posture is:

- the dispatcher timing fix should stay
- the warmed single-bin proof shape is not yet repeatable enough to become the new `Phase 0.B` baseline
- `Phase 0.B` is still open on proof-shape instability

### Phase 0.B closeout posture as of 2026-03-10

`Phase 0.B` should now be closed using a narrow proof-boundary method rather than further broad run-shape experimentation.

That means:

1. keep the semantically trustworthy unsynchronized bounded run shape as the active baseline,
2. tighten the live telemetry on that same baseline, including:
   - API Gateway detailed metrics / access visibility during the active hardening window where practical,
   - Lambda phase and request timing visibility,
   - WSP lane confirmation and abnormal-tail evidence,
   - run-scoped publish, receipt, quarantine, and DLQ continuity,
3. make the steady-state measurement boundary explicit from confirmed fleet participation rather than raw submission time if those differ materially,
4. rerun that same truthful baseline for repeatable bounded correctness proof,
5. if the same truthful baseline remains below `3000 eps` after the measurement boundary is explicit and attributable, treat that as a real ingress capacity or hot-path defect and remediate narrowly instead of reshaping the traffic again.

The following probes are therefore diagnostic-only and must not be used as promotion baselines:

- synchronized `campaign_start_utc` runs,
- warmed single-bin runs that are not yet repeatable,
- target-rate nudges that only move underfill between metric minutes.

### Phase 0.B exact-window proof update as of 2026-03-10

The latest bounded reruns after the APIGW telemetry lock changed the proof judgment again.

What changed first:

- API Gateway stage `v1` was updated live so:
  - `DetailedMetricsEnabled = true`
  - access logs now emit to `/aws/apigateway/fraud-platform-dev-full-ig-edge-v1-access`
- the proving dispatcher now records:
  - fleet-confirmation mode,
  - exact measurement-start attribution,
  - minute-bin shortfall distribution

What the latest frozen-baseline reruns then showed:

- `phase0_20260310T161236Z`
  - minute-bin APIGW gate still red at `2999.100 eps`
  - `4xx = 0`
  - `5xx = 0`
  - `p95 = 51.747 ms`
  - `p99 = 59.505 ms`
- `phase0_20260310T161814Z`
  - minute-bin APIGW gate still red at `2999.700 eps`
  - `4xx = 0`
  - `5xx = 0`
  - `p95 = 51.203 ms`
  - `p99 = 59.445 ms`
- `phase0_20260310T162638Z`
  - minute-bin APIGW gate still red at `2999.600 eps`
  - `4xx = 0`
  - `5xx = 0`
  - `p95 = 50.296 ms`
  - `p99 = 58.310 ms`

Those reruns would have left `Phase 0.B` apparently red if the minute-aligned APIGW metric bins were still treated as the only admitted-throughput truth surface.

The new APIGW access-log evidence shows that is not the truthful steady-state gate for this frozen proof shape.

Exact APIGW access-log windows anchored on confirmed fleet participation showed:

- for `phase0_20260310T161814Z`
  - `active_confirmed_utc = 2026-03-10T16:19:27.919635Z`
  - exact `120 s` window count `= 362874` successful `202` requests
  - exact admitted throughput `= 3023.950 eps`
  - exact `p95 ≈ 49.951 ms`
  - exact `p99 ≈ 58.966 ms`
- for `phase0_20260310T162638Z`
  - `active_confirmed_utc = 2026-03-10T16:27:55.637278Z`
  - exact `120 s` window count `= 362957` successful `202` requests
  - exact admitted throughput `= 3024.642 eps`
  - exact `p95 ≈ 49.951 ms`
  - exact `p99 ≈ 56.996 ms`

One additional attribution check matters:

- WSP progress logs on `phase0_20260310T161814Z`, measured between `16:20:45` and `16:21:45`, showed aggregate source pacing of about `3003.85 eps`
- that means the source was not materially under-driving the boundary during the measured steady minute

Current engineering judgment is therefore:

- the frozen unsynchronized bounded baseline is now repeatably semantically clean
- the exact APIGW access-log window from confirmed fleet participation is repeatably above the declared `3000 eps` steady target
- the remaining red belongs to the older minute-aligned APIGW metric-bin gate, not to the ingress runtime
- `Phase 0.B` is now effectively blocked by proof-harness codification, not by an unresolved ingress production defect

That means the next narrow action is:

- codify the exact APIGW access-log steady-state window into the proving harness so the durable run verdict matches the truthful proof boundary already observed live
- then rerun the same frozen baseline under that codified gate and close `Phase 0.B` if the result stays consistent

### Additional Phase 0.B hardening: DynamoDB hot-path cost correction
The bounded ingress reruns exposed a second production defect in the same `Phase 0` surface: the idempotency table had become an unnecessarily expensive write sink.

Live posture:

- table `fraud-platform-dev-full-ig-idempotency`
- `PAY_PER_REQUEST`
- cost dominated by `WriteRequestUnits`, not storage
- live Lambda still running `IG_RECEIPT_STORAGE_MODE = ddb_hot`
- inline `receipt_payload_json` on old rows was roughly `2 KB`

That mattered because the table is not supposed to be a large receipt archive. It is supposed to be the hot admission / dedupe ledger. We were paying production-write cost for receipt detail that was not needed in the hot row.

I tested the obvious alternative first: switch Lambda receipt persistence to `object_store` mode and keep DynamoDB small. That diagnostic was run as `phase0_20260310T164435Z`.

Verdict on that posture:

- rejected for `Phase 0`
- ingress collapsed to about `65.6 eps`
- valid traffic began receiving `IG_PUSH_REJECTED`
- Lambda logs showed `KAFKA_PUBLISH_TIMEOUT`
- quarantine receipts showed `PUBLISH_AMBIGUOUS`

So object-store receipts are not yet acceptable on the Lambda hot path at the declared steady envelope. That is a cost-saving idea that fails the production-shape rule.

The accepted remediation was narrower:

- restore `ddb_hot`
- keep the proven fast hot-path write shape
- replace the inline full receipt body with a compact receipt summary

The compact serializer now keeps only run-attribution and lookup-critical fields. A fresh live admitted row from `platform_20260310T165309Z` shows `receipt_payload_json` reduced to `392` bytes.

Measured impact on the successful rerun `phase0_20260310T165309Z`:

- semantics remained clean: `4xx = 0`, `5xx = 0`
- latency remained clean: `p95 ≈ 52.0 ms`, `p99 ≈ 60.4 ms`
- no lane collapse and no publish ambiguity
- DynamoDB write pressure dropped materially to about `488k` to `540k WRU/min`, versus the earlier successful baseline around `~720k WRU/min`

Judgment:

- this fixes a real production cost defect inside the active `Phase 0` boundary
- it does not close `Phase 0.B` by itself
- it is still the right change because it reduces waste without weakening the runtime shape we are trying to prove

### Further Phase 0.B replanning: exact route truth, then source-side instability
The next set of runs showed that the proof problem had shifted again.

First, API Gateway detailed metrics exposed route-level `Count` for `POST /ingest/push`, while APIGW access logs gave the only truthful per-request route surface. That let the dispatcher move away from the stale stage-wide minute-bin story, but it also exposed another hardening detail: exact APIGW access logs arrive with variable lag. They are truthful, but not instantly complete.

That forced one more `Phase 0.B` posture correction:

- keep the aligned steady-state window as the parent proof window
- use exact APIGW route logs as the truthful request-count verifier
- guard against APIGW log-delivery lag before finalizing
- stop treating `active_confirmed_utc` itself as the exact count window for steady-state proof

I then tested a cleaner steady-state baseline with:

- `warmup_seconds = 60`
- the same bounded `120 s` correctness window

That was an improvement because it removed the accidental dependence on where fleet confirmation landed inside the minute. But by itself it still only produced a near-threshold result (`phase0_20260310T171930Z` at `2999.55 eps`).

The next narrow correction was to bias the WSP source target slightly above the gate so the proof would not fail on tiny source pacing loss while the ingress gate stayed fixed at `3000 eps`:

- `target_request_rate_eps = 3010`
- `expected_window_eps = 3000`

One run on that candidate shape did go green:

- `phase0_20260310T173526Z`
- exact aligned APIGW route count `= 361433`
- admitted throughput `= 3011.94 eps`
- `4xx = 0`
- `5xx = 0`

But the repeatability test reopened the phase. The repeat `phase0_20260310T174232Z` went materially red, and the full-log diagnostic rerun `phase0_20260310T175034Z` finally showed why:

- `wsp_lane_06` exited early
- lane result reason `= IG_PUSH_REJECTED`
- ECS stop posture `= EssentialContainerExited`
- lane emitted `0`
- run admitted throughput collapsed to about `2401.22 eps`
- APIGW still showed `4xx = 0` and `5xx = 0`

Current `Phase 0.B` judgment is therefore:

- the proof gate itself is no longer the main blocker
- the DDB cost defect is no longer the main blocker
- the active blocker is unstable WSP-side lane behavior under the candidate steady-state proof shape
- `Phase 0.B` remains open until that lane-level `IG_PUSH_REJECTED` posture is understood, fixed narrowly, and revalidated repeatably

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

Entry rule:
- `Phase 0.C` does not begin until `Phase 0.B` is green on a repeatable truthful baseline rather than on a one-off or reshaped proof.

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
