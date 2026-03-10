# Proving-Plane Implementation Notes

## 2026-03-10 11:08 +00:00 - Phase 0 authority reset and planning basis

Problem
- The previous `Phase 0` expansion leaked old build-track thinking into the proving-plane method by pulling historical `M*` decomposition into a planning surface that should have been derived only from the current proving docs.

Why this matters in production
- If the proving plan is expanded using stale structure, the execution path can drift away from the actual production-readiness question and optimize for inherited state mechanics instead of the current goal.
- That would make later hardening less trustworthy and would reintroduce the same phase-chasing behavior that wasted time and cost in the old `road_to_prod` loop.

Authority used for the corrected Phase 0 expansion
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.plan.md`

Explicitly not used as planning authority for this step
- historical `M*` build-phase mappings
- `road_to_prod` phase mechanics
- workflow-defined state decomposition

Decision
- Expand `Phase 0` only from the current proving-plane goal and its contributors.
- Treat supporting readiness graphs as reflections only, not authority.
- Start execution with `Phase 0.A`: telemetry and preflight truth.

Planned next work
1. inventory the current live Control + Ingress resources and operator-visible surfaces,
2. determine which logs, metrics, counters, and boundary checks are actually available now,
3. pin the usable telemetry set and fail-fast conditions,
4. only then authorize a bounded correctness run.

## 2026-03-10 11:27 +00:00 - Phase 0.A preflight truth for the active ingress boundary

Problem
- `Phase 0.A` originally described telemetry in generic terms, but the proving method now requires the active boundary to be pinned to real AWS surfaces before any bounded run is authorized.
- Without that pinning, a later Control + Ingress run could easily be observed through the wrong surfaces and we would be blind again.

Why this matters in production
- The plane cannot be reaffirmed as the working-platform base unless we know which admission surface is actually live, which logs and counters can be trusted during the run, and which telemetry gaps still exist.
- A platform can look wired while the operator is watching the wrong path. That is exactly how guesswork and cost waste re-enter the process.

Live preflight findings
1. The active external admission path is `API Gateway v2 -> Lambda`, not the internal ECS ingress service.
   - API: `fraud-platform-dev-full-ig-edge`
   - API ID: `pd7rtjze95`
   - stage: `v1`
   - route: `POST /ingest/push`
   - integration: `sm9ahw3`
   - integration type: `AWS_PROXY`
   - integration URI resolves to Lambda `fraud-platform-dev-full-ig-handler`
2. The internal ECS ingress service is present but is not the active external front door for this phase.
   - cluster: `fraud-platform-dev-full-ingress`
   - service: `fraud-platform-dev-full-ig-service`
   - desired count: `0`
   - running count: `0`
   - internal ALB: `fp-dev-full-ig-svc`
3. The active ingress Lambda is materially pinned to the declared ingress envelope.
   - memory: `2048 MB`
   - timeout: `30 s`
   - reserved concurrency: `600`
   - env pins include:
     - `IG_RATE_LIMIT_RPS=3000`
     - `IG_RATE_LIMIT_BURST=6000`
     - `IG_IDEMPOTENCY_TABLE=fraud-platform-dev-full-ig-idempotency`
     - `IG_DLQ_URL=https://sqs.eu-west-2.amazonaws.com/230372904534/fraud-platform-dev-full-ig-dlq`
     - `KAFKA_BOOTSTRAP_BROKERS_PARAM_PATH=/fraud-platform/dev_full/msk/bootstrap_brokers`
4. The WSP operator surface is available through ECS/Fargate.
   - task family: `fraud-platform-dev-full-wsp-ephemeral`
   - task definition revision inspected: `:60`
   - log group: `/ecs/fraud-platform-dev-full-wsp-ephemeral`
5. The primary current ingress telemetry surfaces are:
   - Lambda logs: `/aws/lambda/fraud-platform-dev-full-ig-handler`
   - Lambda metrics: invocations, errors, throttles, duration, concurrency
   - DynamoDB active-run writes on `fraud-platform-dev-full-ig-idempotency`
   - SQS depth on `fraud-platform-dev-full-ig-dlq`
   - WSP logs
   - Kafka continuity inferred from ingress logs/receipts

Telemetry gap discovered
- API Gateway stage `v1` currently has `DetailedMetricsEnabled=false`
- no API Gateway access-log group is currently visible
- this means stage-level API telemetry is weaker than desired for active hardening
- for `Phase 0.B`, the live truth surface must therefore be Lambda + DDB + SQS + WSP + publish continuity, not API Gateway access logging

Telemetry observations
- CloudWatch metric namespaces for both API Gateway and Lambda are present and queryable for the active ingress path.
- Recent datapoints for API Gateway request count and Lambda invocations are currently sparse because the plane is not actively running.
- SQS DLQ depth is live and readable right now and therefore can serve as an always-on fail-fast signal even before the next run starts.
- The practical effect is that `Phase 0.B` needs a fresh bounded run not only to prove ingress, but also to warm the primary operator telemetry surfaces.

Decision
- Treat `API Gateway -> Lambda` as the only active external ingress path for `Phase 0`.
- Treat the internal ECS ingress service as a retained comparison surface only, not the primary proof boundary.
- Update the Phase 0 doc so the telemetry sub-ledger and fail-fast rules reflect the actual live surfaces.
- Record the default operator loop in the Phase 0 doc so the next run is launched with live log tails and live counters already attached.

Next work
1. finish the `Phase 0.A` telemetry pinning in the phase doc,
2. add any remaining preflight checks needed for bounded correctness authorization,
3. prepare the exact CLI/operator loop for `Phase 0.B`.
