# Proving-Plane Implementation Notes

## 2026-03-10 12:31:00 +00:00
Restarting `Phase 0` fresh means treating the prior implementation-note trail as non-authoritative and rebuilding this notebook from the current proving authority only:

- `AGENTS.md`
- `platform.production_readiness.md`
- `platform.production_readiness.plan.md`
- `platform.production_readiness.phase0.md`

The immediate task is not to rediscover ingress broadly. It is to remove blind spots around the live `Control + Ingress` boundary so the first bounded revalidation run can be interpreted honestly.

Fresh AWS preflight confirmed the active external front door is still:

- API `fraud-platform-dev-full-ig-edge` (`pd7rtjze95`)
- stage `v1`
- route `POST /ingest/push`
- integration `sm9ahw3`
- Lambda `fraud-platform-dev-full-ig-handler`

The active ingress runtime still self-reports the expected mode and envelope once the platform API key is supplied to the health endpoint:

- mode `apigw_lambda_ddb_kafka`
- `rate_limit_rps = 3000`
- `rate_limit_burst = 6000`

Two pieces of live truth matter because they would otherwise create avoidable blindness during the run:

1. `GET /ops/health` is not anonymously readable in practice. Even though API Gateway route auth is `NONE`, the application itself returns `{"error":"unauthorized","reason":"missing_api_key"}` unless `X-IG-Api-Key` is supplied. The health probe is therefore valid, but only when exercised with the same key material the ingress runtime expects.
2. `/fraud-platform/dev_full/ig/service_url` in SSM still points to the retained internal ALB ingress surface. That path is not the active external front door for `Phase 0`, but it remains a drift hazard because older proving helpers can still resolve it if the execute-api target is not passed explicitly.

The current telemetry posture is usable but still intentionally narrow:

- API Gateway stage `v1` keeps the declared `3000 / 6000` throttle posture.
- API Gateway `DetailedMetricsEnabled` remains `false`.
- Lambda logs and metrics are present.
- WSP logs are present.
- DDB idempotency and SQS DLQ surfaces are present.

Current baseline conditions that affect interpretation of the run:

- the DDB idempotency table is large (`15,646,769` items, `PAY_PER_REQUEST`), so active-run correctness must be judged by run-scoped deltas and attributable evidence rather than absolute table size.
- the DLQ is not empty before the run (`ApproximateNumberOfMessagesVisible = 92`) and has been flat over the recent window, so `Phase 0` must treat queue growth delta, not raw queue depth, as the meaningful fail-fast signal.

Before spending another AWS run, a proving-loop defect was found in the fresh `Phase 0` wrapper: the dry-run command was still not explicitly passing `--ig-ingest-url`, which meant the shared dispatcher could fall back to the stale SSM ALB service URL. That would have violated the `Phase 0.A` pinned boundary truth and made the next run ambiguous. The wrapper was patched in place so the dry-run command now forces:

- `https://pd7rtjze95.execute-api.eu-west-2.amazonaws.com/v1/ingest/push`

Judgment at this point:

- `Phase 0.A` preflight truth is materially re-established.
- the main remaining blind spot from the launcher path has been removed.
- `Phase 0.B` is now authorized to run against the correct execute-api boundary.

## 2026-03-10 12:39:59 +00:00
Ran the first fresh bounded `Phase 0.B` correctness window against the corrected execute-api target:

- execution `phase0_20260310T123239Z`
- platform run `platform_20260310T123239Z`
- surface `API Gateway -> Lambda`
- metric surface mode `APIGW`

The result is red, but importantly it is not red in the way the earlier ambiguous attempts were red.

What remained healthy:

- ingress path was the intended one
- valid-traffic `4xx = 0`
- valid-traffic `5xx = 0`
- DLQ depth stayed flat at the pre-run baseline (`92`)
- Lambda errors and throttles stayed at `0`
- final summary latency stayed inside the `Phase 0.B` correctness posture (`p95 212.66 ms`, `p99 294.39 ms`)

What failed:

- admitted throughput only reached `1734.125 eps` against the declared `3000 eps` target

The live telemetry and the lane logs narrow this sharply away from “ingress is broken” and toward “the current proving shape is under-driving ingress”:

- API Gateway request counts moved continuously throughout the bounded window.
- Lambda invocations moved continuously on the same window.
- There was no sign of early error leakage, throttling, or DLQ growth.
- WSP lane logs showed each lane materially under its own target while still reporting:
  - `WSP rate limiter active ... target_eps=125`
  - `WSP pack manifest missing`
  - `WSP pack not sealed`

Two sampled lanes told the same story:

- lane `0/24` reached only about `11.7k` total emitted records across the four configured outputs by around `12:36:18`
- lane `23/24` reached only about `11.1k` total emitted records across the same outputs by around `12:36:38`

That is roughly `60-65 eps` per lane in practice, far below the configured `125 eps` per lane target. Multiplied across `24` lanes, that observed source pace lands in the same neighborhood as the measured ingress throughput shortfall. In other words, the run shape itself is presently failing to generate production-shaped pressure even though the ingress path is admitting what it receives cleanly.

The runner code explains why this is a plausible harness/source ceiling rather than an ingress-runtime ceiling. In `src/fraud_detection/world_streamer_producer/runner.py`, the WSP replay path does not only respect the token-bucket rate limiter; it also sleeps on source timestamp gaps after applying `stream_speedup`. With the current `Phase 0` defaults:

- `stream_speedup = 19.7`
- `lane_count = 24`

the source replay pace is too weak to satisfy the declared `3000 eps` envelope on this substrate.

This is not just a theory from one failed run. Existing run evidence in `runs/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/` shows the same substrate previously reaching `3025.36 eps` with a materially stronger WSP launch posture:

- `stream_speedup = 51.2`
- `lane_count = 40`
- `duration_seconds = 180`

There is no repo evidence of a `24`-lane `Phase 0`-style shape reaching the declared `3000 eps` envelope. That means the current default `Phase 0.B` launch parameters are themselves a production-readiness blocker because they can produce a false red against ingress by under-driving the boundary.

Judgment now:

- the fresh `Phase 0.B` run is trustworthy enough to clear the old path-drift ambiguity
- the current red is narrowed to a proving-shape calibration defect, not yet an ingress-runtime defect
- the next action should be a narrow rerun of `Phase 0.B` only, using a stronger WSP shape based on prior proven repo evidence rather than broad ingress remediation

## 2026-03-10 13:10:58 +00:00
The stronger WSP reruns answered the next methodological question cleanly: after correcting the under-driving harness shape, `Phase 0.B` is no longer red because of the proof harness. It is now red because of the ingress runtime itself.

Three fresh bounded runs matter:

1. `phase0_20260310T124200Z` used the evidence-backed WSP posture (`40` lanes, `stream_speedup 51.2`) but still produced intermittent `5xx` and non-zero lane exits.
2. Lambda logs for that run showed the real cause was not API Gateway instability or generic Lambda crash. The ingress runtime was returning `IG_UNHEALTHY:BUS_UNHEALTHY` because the request path was still using `IG_HEALTH_BUS_PROBE_MODE=describe`.
3. After repinning the live Lambda to `IG_HEALTH_BUS_PROBE_MODE=none`, `phase0_20260310T130200Z` became the first clean truthful runtime red:
   - `4xx = 0`
   - `5xx = 0`
   - admitted throughput `1584.525 eps`
   - API Gateway latency `p95 1479.95 ms`
   - API Gateway latency `p99 1990.17 ms`
   - Lambda `Errors = 0`
   - Lambda `Throttles = 0`
   - Lambda concurrency peaked at `599` against the then-live reserved `600`

That `13:02` run is the current best baseline for judgment because it preserves the intended external boundary, keeps the valid-traffic error families at zero, and still fails the declared envelope. In other words, the ingress edge is materially functioning but is not yet production-ready at the required steady `3000 eps` posture.

I then tested whether this was only a concurrency ceiling by increasing live reserved concurrency from `600` to `900` and rerunning `Phase 0.B` immediately as `phase0_20260310T130900Z`. That did not produce a green or even a cleaner red. It exposed a second, more dangerous failure family:

- all `40` WSP lanes exited non-zero before the measurement window stabilized,
- lane logs showed `IG_PUSH_REJECTED`,
- Lambda logs showed repeated `PUBLISH_AMBIGUOUS`,
- the concrete exception path was `RuntimeError: KAFKA_PUBLISH_TIMEOUT`,
- quarantine artifacts for the active run carried `reason_codes=["PUBLISH_AMBIGUOUS"]`.

That means the `900`-concurrency change was not a valid promotion candidate. It was a narrow remediation probe and it failed: pushing more concurrent Lambda workers into the same synchronous publish path created fail-closed publish ambiguity on valid traffic. Because that is a materially worse live posture than the truthful `600`-concurrency red, I reverted reserved concurrency back to `600` and also reverted the Terraform default to `600`.

Two current judgments follow from this:

- `Phase 0.B` does not need a structural replan yet. After the WSP calibration correction, the subphase is exposing real runtime truths rather than confusing harness truths.
- the active production-readiness blocker is now the ingress hot path itself:
  - at `600` reserved concurrency, it stays semantically clean but misses throughput and latency targets;
  - at `900`, it tips into `KAFKA_PUBLISH_TIMEOUT -> PUBLISH_AMBIGUOUS`, which is a hard fail-closed blocker by design.

One more blind spot was also removed before any further AWS rerun: the shared remote WSP dispatcher used metadata-only lane capture when lane count exceeded `32`, which meant the durable run summary lost the actual per-lane failure reason. I patched it so metadata mode now still captures short abnormal-lane log tails and extracted failure markers for non-zero-exit lanes. That keeps hardening artifacts small while preserving the diagnostic truth needed for fail-fast decisions.

Current next-step posture:

- keep `Phase 0` anchored on the truthful `600`-concurrency baseline rather than the failed `900` probe,
- retain `IG_HEALTH_BUS_PROBE_MODE=none`,
- use the improved lane-tail telemetry on the next bounded rerun or targeted remediation probe,
- investigate the synchronous Kafka publish path as the active throughput / ambiguity boundary rather than reopening WSP or front-door path selection.

One additional telemetry defect surfaced while trying to pull phase-level hot-path timing from Lambda logs. The ingress code already records and periodically flushes:

- `phase.publish_seconds`
- `phase.receipt_seconds`
- `phase.dedupe_*`
- `admission_seconds`

through `MetricsRecorder`, but those `logger.info(...)` flushes were not materially visible in CloudWatch for the fresh `Phase 0` windows. Reading the Lambda entrypoint explains why: `aws_lambda_handler.py` only set its own module logger to `INFO`, not the root logger or the `fraud_detection` logger hierarchy. That leaves `fraud_detection.ingestion_gate.metrics` and `fraud_detection.platform_narrative` vulnerable to staying effectively above the emitted level under Lambda defaults.

I patched the Lambda entrypoint locally so it now configures:

- root logger level from `IG_LOG_LEVEL` (default `INFO`)
- `fraud_detection` logger level
- `fraud_detection.platform_narrative` logger level
- the handler module logger level

This is not live yet, so it does not change the current production judgment. It does matter for the next bounded rerun because once deployed it should finally expose the per-phase timing story that is already being recorded in-process, especially whether the truthful `600`-concurrency red is dominated by `phase.publish_seconds`, receipt work, or a different part of the hot path.
