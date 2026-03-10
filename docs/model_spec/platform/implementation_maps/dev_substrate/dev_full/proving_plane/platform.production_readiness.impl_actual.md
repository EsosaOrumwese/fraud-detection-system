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
6. The front-door health surface is live and self-identifying.
   - `GET /ops/health` returns `200`
   - service: `ig-edge`
   - mode: `apigw_lambda_ddb_kafka`
   - profile: `dev_full`
   - envelope:
     - `rate_limit_rps=3000`
     - `rate_limit_burst=6000`

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

## 2026-03-10 11:52 +00:00 - Phase 0.B run-surface decision

Problem
- `Phase 0.B` now needs a bounded AWS-first correctness run surface, but the existing reusable execution logic still lives in `scripts/dev_substrate/pr3_wsp_replay_dispatch.py` and carries old `PR3` naming and artifact conventions.
- The question is whether to build a brand-new control/ingress runner immediately or to wrap the existing remote dispatcher in a proving-plane-specific CLI entrypoint.

Why this matters in production
- The wrong choice here either drags stale `PR3` semantics back into the proving loop or creates unnecessary duplicate execution logic that we would then have to maintain and revalidate separately.
- The execution core should stay shared where possible, but the operator surface for hardening must speak the current proving-plane language and write to the current proving-plane run roots.

Options considered
1. Call `pr3_wsp_replay_dispatch.py` directly and accept the old argument names.
   - Rejected for operator clarity.
   - It would work technically, but it would keep the proving loop conceptually tied to old `PR3` naming and make logs and notes harder to reason about.
2. Rewrite a full new remote dispatcher just for `Phase 0`.
   - Rejected as wasteful right now.
   - The existing dispatcher already contains the hard part: canonical remote WSP replay against the live ingress edge with bounded thresholds.
3. Create a thin proving-plane wrapper for `Phase 0.B`.
   - Chosen.
   - The wrapper can generate the fresh run ids, redirect outputs into the proving-plane run root, pin the `Phase 0` naming, and preserve the shared remote execution core.

Decision
- Build a thin `Phase 0` CLI wrapper around the existing remote WSP dispatcher.
- Keep the execution core shared.
- Make the operator-facing interface and artifact location proving-plane-native.

Expected result
- `Phase 0.B` gets a clean CLI entrypoint for bounded Control + Ingress correctness revalidation.
- We avoid duplicating the remote replay logic.
- We avoid letting the old `PR3` naming leak back into the active proving method.

Implementation result
- Added `scripts/dev_substrate/phase0_control_ingress_revalidate.py`.
- The wrapper:
  - generates fresh run ids,
  - writes under `runs/dev_substrate/dev_full/proving_plane/run_control`,
  - pins `Phase 0` naming on execution and blocker prefixes,
  - reuses the existing remote WSP replay core rather than cloning it.

## 2026-03-10 11:55 +00:00 - First Phase 0.B launch blocker

Problem
- The first bounded `Phase 0.B` launch failed before any AWS traffic was generated because the shared remote dispatcher expects the execution root directory to exist already.
- The new Phase 0 wrapper passed a new execution id but did not pre-create `runs/dev_substrate/dev_full/proving_plane/run_control/<execution_id>/`.

Why this matters in production
- This is not a platform-runtime defect. It is a hardening-loop defect.
- If we do not fix it immediately, the proving path remains more fragile than it should be and later phases will pay for the same trivial launch problem again.

Observed failure
- `RuntimeError: PR3 execution root missing: runs\\dev_substrate\\dev_full\\proving_plane\\run_control\\phase0_<timestamp>`

Decision
- Fix the wrapper, not the shared dispatcher, because the proving-plane wrapper is the layer that owns the proving-plane run root and naming.
- The wrapper must pre-create the execution directory before invoking the shared remote replay core.

Next work
1. patch the wrapper to create the execution root,
2. rerun the same bounded `Phase 0.B` launch,
3. continue only after the launch passes this local boundary.

## 2026-03-10 11:59 +00:00 - Second Phase 0.B launch blocker

Problem
- The second bounded `Phase 0.B` launch passed the missing-directory defect but failed on the next legacy assumption inside `pr3_wsp_replay_dispatch.py`.
- The shared dispatcher hard-requires `pr3_s0_execution_receipt.json` in the execution root and refuses to start unless that receipt says `PR3_S0_READY`.

Why this matters in production
- This is still a proving-loop defect, not a Control + Ingress runtime defect.
- The dispatcher is carrying an old upstream-lock convention from the `PR3` path. If the wrapper does not absorb that legacy assumption, the proving-plane CLI remains unable to launch bounded ingress runs cleanly.

Options considered
1. Rewrite the shared dispatcher immediately to remove the legacy upstream lock.
   - Rejected for this phase.
   - It is broader than the current proving question and would widen the work mid-boundary.
2. Seed a minimal compatibility receipt in the proving-plane wrapper.
   - Chosen.
   - The wrapper owns the translation layer between proving-plane naming and the legacy shared dispatcher, so this is the narrowest correct fix.

Decision
- The wrapper will create a tiny compatibility `pr3_s0_execution_receipt.json` in the execution root before invoking the shared dispatcher.
- This is a compatibility shim only. It is not being treated as authority for proving-plane status; it only satisfies the shared dispatcher's historical guard.
