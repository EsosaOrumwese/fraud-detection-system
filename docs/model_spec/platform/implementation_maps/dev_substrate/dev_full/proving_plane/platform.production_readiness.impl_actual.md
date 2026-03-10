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

## 2026-03-10 14:07:26 +00:00
I continued from that telemetry gap instead of treating the `13:38` truthful red as the end of the story. The next bounded run needed better observability first, so I pushed request-level timing telemetry into the live Lambda and then used the resulting runs to separate proving-agent defects from real ingress defects.

First deployment: `phase0_ig_lambda_20260310T135006Z`

- purpose: make the Lambda emit request timing splits (`auth`, `gate`, `admit`, `response`, `total`) so the next bounded `Phase 0.B` run would not stay blind inside the hot path
- outcome: the code deployed, but the first live rerun immediately exposed a proving-agent defect in the new telemetry helper

Bad bounded rerun: `phase0_20260310T135126Z`

- bounded window result:
  - admitted throughput collapsed to `30.183 eps`
  - valid-traffic `5xx = 2206`
  - all `40` WSP lanes eventually failed with `IG_PUSH_RETRY_EXHAUSTED`
- this is **not** a platform-runtime verdict
- CloudWatch and Lambda evidence pinned the cause to the proving change itself:
  - `NameError: name '_prune_none' is not defined`
  - the exception was thrown inside the request-timing emitter after successful admission work
  - API Gateway `5xx` matched Lambda `Errors`
  - Lambda `Throttles = 0`

That matters methodologically because the run went red for a reason introduced by the hardening agent, not by the ingress platform. I therefore treated `phase0_20260310T135126Z` as invalid proof, fixed the telemetry helper, and redeployed before spending another bounded window.

Second deployment: `phase0_ig_lambda_20260310T135741Z`

- repaired the helper by replacing the bad `_prune_none` reference with a local compacting helper
- wrapped timing emission so telemetry failure cannot break admission again
- kept slow-path logging sampled by default so hardening gains visibility without turning the Lambda into a log storm
- current live Lambda code hash after the repaired deployment:
  - `oXhYuOAnn1QR3kFu8hoEuGdWPBwCic52eGscCDDQ47g=`

Truthful rerun after repair: `phase0_20260310T135855Z`

- bounded window result:
  - valid-traffic `4xx = 0`
  - valid-traffic `5xx = 0`
  - admitted throughput `1324.508 eps`
  - API Gateway latency `p95 = 553.894 ms`
  - API Gateway latency `p99 = 1472.352 ms`
  - Lambda `Throttles = 0`
  - Lambda `ConcurrentExecutions` peaked at `581`, then sat well below the reserved `600`
- production judgment:
  - the active red is no longer throttling-driven
  - it is also not the earlier `KAFKA_PUBLISH_TIMEOUT` family from the failed `900`-concurrency probe
  - the ingress boundary is still materially under-performing, but the failure family is now different and more precise

The new timing telemetry removed the largest remaining blind spot and exposed three concrete latency contributors.

1. Cold-fleet / gate-initialization churn is materially real

- sampled `IG gate initialized` logs for the active run: `525`
- `init_seconds p50 ≈ 1.38`
- `init_seconds p95 ≈ 1.414`
- `init_seconds max ≈ 1.469`

That is a production-readiness-defining signal. It means the current `API Gateway -> Lambda` posture is creating a broad cold execution fleet during the bounded window, and each fresh environment pays roughly `1.4 s` to build the gate. The run is therefore losing latency budget before actual admission work has even started.

2. Successful admits are still slow even after gate construction is separated

- sampled `IG request timing` logs for successful `202 ADMIT` requests showed roughly:
  - `auth_ms ≈ 45-60`
  - `gate_ms ≈ 1365-1415`
  - `admit_ms ≈ 800-900`
  - `response_ms ≈ negligible`
  - `total_ms ≈ 2200-2350`

So the remaining ingress red is not only a cold-start problem. Even where the request reaches the admit path successfully, the hot path still spends close to another second inside admission itself.

3. The abnormal WSP lanes in the truthful run are not `5xx`; they are long-running quarantines

- `wsp_lane_01`, `wsp_lane_10`, and `wsp_lane_11` exited because Lambda returned `400` with `decision = QUARANTINE`
- sampled timing logs for those `400` requests showed:
  - `gate_ms ≈ 1.36-1.45 s`
  - `admit_ms ≈ 11-15 s`
  - total request time `≈ 12.5-16 s`

That points away from front-door instability and toward duplicate/in-flight resolution waiting too long inside the admission path, after which the request fails closed into `QUARANTINE`.

Current engineering judgment from the truthful `13:58` rerun:

- `Phase 0.B` remains red
- the decisive blockers are now:
  - cold-start amplification and gate-construction cost on the Lambda fleet
  - slow admit-path work even on successful first-seen traffic
  - a smaller but still real duplicate/in-flight resolution path that can wait `11-15 s` and then quarantine valid traffic
- the next remediation should stay narrow and production-shaped:
  - reduce or absorb the cold-start / gate-init penalty,
  - isolate the dominant cost inside `admit_ms`,
  - pin the exact quarantine reason family for the long duplicate-resolution cases

## 2026-03-10 14:30:49 +00:00
That `13:58` judgment did not survive the next telemetry pass unchanged. Once the repaired Lambda timing build was live and the object-store health path was read against the new logs, I found that another failure family was still being misclassified as ingress-runtime sickness.

The concrete clue was in the fresh bounded red `phase0_20260310T142125Z`:

- Lambda logs still showed benign governance append contention:
  - `Governance projection append deferred ... reason=S3_APPEND_CONFLICT`
- but the health observer was also marking the same append path unhealthy through the live S3 exception shape:
  - `ClientError ... ConditionalRequestConflict`
- once that happened, valid traffic started failing closed through `IG_UNHEALTHY:OBJECT_STORE_UNHEALTHY`.

So the earlier store-health hardening had been too narrow. It treated the in-process `RuntimeError("S3_APPEND_CONFLICT")` family as benign, but not the equivalent live `botocore ClientError` surface. I patched `src/fraud_detection/ingestion_gate/store.py` so append contention is now treated as benign for both shapes:

- `S3_APPEND_CONFLICT`
- `ConditionalRequestConflict`
- `PreconditionFailed` / `412`

I then rebuilt and redeployed the Lambda (`phase0_ig_lambda_20260310T143049Z`, live code hash `Nnc6Es87IZewxrfoAoDMks1vlO+h+c6mNsmul8RgRSA=`) and reran bounded `Phase 0.B`.

Those reruns changed the production judgment materially.

`phase0_20260310T143110Z`

- admitted throughput `2999.925 eps`
- `4xx = 0`
- `5xx = 0`
- `p95 = 49.576 ms`
- `p99 = 57.463 ms`

`phase0_20260310T143801Z`

- admitted throughput `2999.650 eps`
- `4xx = 0`
- `5xx = 0`
- `p95 = 49.315 ms`
- `p99 = 56.726 ms`

That is a very different picture from the earlier hot-path diagnosis. The ingress runtime is now semantically clean under the bounded correctness shape. The old runtime blockers that were dominating the story at `13:58` are no longer the right explanation for the active red posture.

What remains red after the store-health fix is much narrower:

- a tiny repeatable throughput shortfall on the metric surface only
- no valid-traffic `4xx`
- no valid-traffic `5xx`
- no Lambda errors
- no Lambda throttles

I also tried the obvious but methodologically weak probe of nudging the requested rate upward (`phase0_20260310T144447Z`, `target_request_rate_eps = 3000.5`). That did not solve the problem. It only shifted which measured minute underfilled. So the issue is not “the platform needs a higher target”; it is a proof-boundary calibration issue.

Current judgment at this point:

- the ingress runtime is no longer the active `Phase 0.B` blocker
- the active blocker has moved back to the proving surface
- the next work should stay on the proof boundary, not reopen ingress-runtime remediation blindly

## 2026-03-10 15:25:52 +00:00
I then spent the next bounded runs trying to attribute that last proof-boundary miss cleanly rather than patching by instinct.

First diagnostic run: `phase0_20260310T145355Z` with `lane_log_mode=full`

This was the right telemetry move even though it still returned red:

- admitted throughput `2999.375 eps`
- `4xx = 0`
- `5xx = 0`
- `p95 = 49.363 ms`
- `p99 = 56.808 ms`

The important thing was what the full lane logs proved:

- CloudWatch was not lagging; later metric re-queries matched the original counts exactly
- the WSP lanes were materially participating and landing close to their intended rate
- the bounded miss was on the order of `75` requests total across the entire `120 s` window, which is only about `1-2` requests per lane
- the second measured minute was effectively on target while the first measured minute carried almost all of the deficit

That sharply narrows the defect to the proving window itself: the current `Phase 0.B` gate is still mixing a little bit of driver fleet stabilization into what it is judging as steady-state throughput.

I tested two candidate corrections to see whether they were honest fixes or bad proof shapes.

1. Forced synchronized campaign start: `phase0_20260310T150019Z`

- explicit `campaign_start_utc = 2026-03-10T15:04:00Z`
- result was materially worse and clearly invalid as a new baseline:
  - widespread `http_503`
  - `IG_PUSH_RETRY_EXHAUSTED`
  - `IG_PUSH_REJECTED`
  - quarantines on valid traffic
  - `p95 ≈ 28.1 s`
  - `p99 ≈ 29.9 s`

This matters because it proves that perfect fleet phase alignment changes the arrival shape enough to create a new overload/fail-closed regime. So that is not an acceptable proof correction.

2. Warmup-shaped one-minute probe: `phase0_20260310T150824Z`

- `warmup_seconds = 60`
- `duration_seconds = 60`
- this also did not produce an honest green
- it stopped early with widespread lane exits and `IG_PUSH_REJECTED`

So the two obvious corrections both failed for good reasons:

- forced alignment creates an artificial synchronized arrival pattern and breaks the boundary
- the quick warmup probe is not yet a stable replacement for the current bounded correctness gate

Current judgment now is tighter than before:

- the semantically trustworthy `Phase 0.B` baseline is still the unsynchronized bounded run shape that gives:
  - `4xx = 0`
  - `5xx = 0`
  - clean latency
  - admitted throughput within a few dozen requests of the target
- the remaining blocker is specifically the proof-window definition for steady-state correctness
- the next correct move is to rework the bounded correctness measurement posture itself so it measures a truly stable steady minute without introducing synchronized-arrival artifacts

That is different from “the platform is green” and different from “ingress is broken.” It means `Phase 0.B` is open because the current proof gate is not yet shaped tightly enough to render a truthful final verdict on a runtime that now looks semantically healthy.

## 2026-03-10 15:45:36 +00:00
I pushed one more level down into the proof harness because the first warmup-shaped probe had been invalid for a harness reason, not a platform reason.

The concrete defect was in `scripts/dev_substrate/pr3_wsp_replay_dispatch.py`: the dispatcher only moved `active_confirmed_at` forward when every lane was `RUNNING` at the same instant. On a large `40`-lane fleet, that is too strict. If some lanes have already started but the fleet never reaches a perfect simultaneous `RUNNING` moment, the proof clock falls back to `submitted_at`, which contaminates `measurement_start_utc`.

I patched that boundary so the dispatcher now records the fleet as confirmed once all lanes have at least started, even if the fleet never hits a perfect simultaneous `RUNNING` state. The run summary now also records `fleet_confirmation_mode` so later interpretation can distinguish:

- `all_running`
- `all_started`
- `submitted_at_fallback`

That patch immediately paid off on the next warmup-shaped steady-state probe:

`phase0_20260310T153432Z`

- `warmup_seconds = 60`
- `duration_seconds = 60`
- `fleet_confirmation_mode = all_running`
- admitted throughput `2999.617 eps`
- `4xx = 0`
- `5xx = 0`
- `p95 = 49.743 ms`
- `p99 = 57.593 ms`

This is important because it proved the earlier catastrophic warmup run was not a trustworthy argument against warmup-shaped measurement. After the dispatcher fix, that same basic posture became semantically clean and landed only `23` requests short on a single `60 s` APIGW bin.

I then immediately repeated the same warmup one-bin posture to test whether it was stable enough to adopt as the new bounded correctness gate.

That repeat failed badly:

`phase0_20260310T154004Z`

- widespread non-zero WSP lane exits
- repeated `IG_PUSH_REJECTED`
- admitted throughput collapsed to `630.433 eps`
- latency stayed low only because most traffic never made it through normal admission

So the current state is more complicated than “warmup fixed it”:

- the dispatcher timing bug was real and is now fixed
- a warmed single-bin proof can be truthful
- but that warmed posture is not yet repeatable enough to adopt as the new `Phase 0.B` baseline

That repeatability failure matters methodologically. It suggests the warmed posture is changing the semantic slice of source traffic enough that later duplicate/quarantine behavior can re-enter the proof in a way the original bounded shape did not. In other words, I do not yet have a replan I trust.

Current judgment right now:

- keep the dispatcher timing fix; it is a real harness hardening improvement
- do **not** promote the warmed single-bin posture into the plan yet
- `Phase 0.B` is still open on proof-shape instability, not on a newly rediscovered ingress-runtime fault

## 2026-03-10 15:58:47 +00:00
At this point the work needed a posture correction in the authoritative plan itself, not just another rerun.

The main thing I have learned from the `14:31`, `14:55`, `15:08`, `15:34`, and `15:40` bounded probes is that `Phase 0` is no longer blocked by a broad ingress mystery. The active issue is narrower:

- the unsynchronized bounded run shape is semantically trustworthy,
- the remaining miss is at the proof boundary for steady-state admitted throughput,
- the synchronized-start correction is invalid because it creates a new overload regime,
- the warmed single-bin correction is not yet repeatable enough to adopt as a new baseline.

That combination changes how `Phase 0` should be closed. The right move now is not “keep trying more shapes until one goes green.” The right move is:

1. freeze the semantically trustworthy unsynchronized bounded run as the active baseline,
2. tighten telemetry on that exact baseline so the steady-state boundary is attributable rather than inferred,
3. make the measurement start explicit from confirmed fleet participation where that differs from raw submission time,
4. repeat the same truthful baseline until the verdict is either:
   - repeatably green, or
   - repeatably red for a real capacity / hot-path reason.

This is a meaningful methodological shift even though it does not lower a single target. The throughput target remains `3000 eps`. The point is to stop spending money on proof-shape churn and instead force `Phase 0` into a small decisive closure matrix:

- truthful baseline
- repeatability check
- only then narrow runtime remediation if the truthful baseline still stays red

I have therefore updated the parent production-readiness plan and the `Phase 0` expansion so this posture is no longer implicit in notebook text alone.

## 2026-03-10 16:06:49 +00:00
The readiness graphs also needed the same correction. They had fallen behind the current `Phase 0` truth in two important ways.

First, the two "production-ready current" graphs were still visually carrying the retained internal ALB / ECS ingress path as though it were part of the currently accepted external admission boundary. That no longer matches the pinned `Phase 0.A` preflight truth. The active external front door for this revalidation is:

- `HTTP API Gateway v2`
- `POST /ingest/push`
- `fraud-platform-dev-full-ig-handler`

So I rewrote the network and resource graphs to show the currently promoted Control + Ingress core through `API Gateway -> Lambda`, and to make the retained internal ingress service absent on purpose rather than silently overclaimed.

Second, the readiness-delta graph was still telling an older green closure story. That was materially false against the current work. The live story now is:

- active boundary drift hazard was removed,
- ingress semantics on the truthful unsynchronized baseline are now clean,
- the remaining blocker is the repeatable steady-state proof boundary,
- synchronized and unstable warmup reshapes are diagnostic only,
- `Phase 0.B` is still open and `Phase 0.C` is blocked.

I regenerated the PNGs immediately after updating the Mermaid sources so the visual artifacts now match the text artifacts. This matters because the graphs are for operator understanding; if they lag behind the notes, they create the same blindness in a different form.

## 2026-03-10 16:34:55 +00:00
The latest `Phase 0` work changed the problem shape again, but this time in the direction we want.

I first closed the APIGW-side telemetry gap materially, not just on paper:

- updated the live `v1` stage so `DetailedMetricsEnabled = true`
- created `/aws/apigateway/fraud-platform-dev-full-ig-edge-v1-access`
- added the missing CloudWatch Logs resource policy so APIGW could actually write there
- verified delivery with a real `GET /ops/health` call and a live access-log event from `pd7rtjze95_v1-*`

That matters because it gave me the first truthful APIGW-side per-request evidence surface on the exact external boundary I am trying to prove.

I then reran the frozen unsynchronized `40`-lane / `51.2x` baseline three times:

- `phase0_20260310T161236Z`
- `phase0_20260310T161814Z`
- `phase0_20260310T162638Z`

All three stayed semantically clean:

- valid-traffic `4xx = 0`
- valid-traffic `5xx = 0`
- p95/p99 stayed comfortably inside the Phase 0 budget

But the old minute-aligned APIGW metric gate still rendered them red at:

- `2999.100 eps`
- `2999.700 eps`
- `2999.600 eps`

The decisive new result came from comparing that old gate to the exact APIGW access-log window anchored on `active_confirmed_utc`.

For `phase0_20260310T161814Z`:

- `active_confirmed_utc = 2026-03-10T16:19:27.919635Z`
- exact `120 s` access-log count `= 362874`
- exact admitted throughput `= 3023.950 eps`
- exact `p95 ≈ 49.951 ms`
- exact `p99 ≈ 58.966 ms`

For `phase0_20260310T162638Z`:

- `active_confirmed_utc = 2026-03-10T16:27:55.637278Z`
- exact `120 s` access-log count `= 362957`
- exact admitted throughput `= 3024.642 eps`
- exact `p95 ≈ 49.951 ms`
- exact `p99 ≈ 56.996 ms`

Those two repeat checks matter more than another minute-bin near miss because they line up with the proving doctrine we already wrote into the plan: steady-state measurement should be anchored to confirmed plane participation, not to a more convenient but slightly distorted launcher artifact.

I also used the full-log `phase0_20260310T161814Z` rerun to get one more attribution layer. The WSP progress logs over the steady minute (`16:20:45` to `16:21:45`) imply about `3003.85 eps` at the source side. That means the current red is not a clean case of the source under-driving ingress either.

So the current truthful judgment is tighter than before:

- the ingress runtime is not the blocker
- the frozen unsynchronized proof shape is not the blocker
- the remaining blocker is that the proving harness still verdicts on the older minute-aligned APIGW metric-bin view, even though the now-live exact APIGW access-log surface shows the same run shape clearing the target repeatably

That is a good kind of blocker. It means the next narrow action is no longer another exploratory rerun. It is to codify this exact APIGW access-log steady-state window into the proving harness so the durable run verdict matches the truthful boundary we are now able to observe.

## 2026-03-10 16:59:41 +00:00
The next `Phase 0` problem was not semantic red on ingress. It was production waste on the same hot path.

The user's cost concern was correct. Live DynamoDB posture showed the idempotency table had become the dominant ingress cost surface:

- table `fraud-platform-dev-full-ig-idempotency`
- `PAY_PER_REQUEST`
- about `41.3 GB`
- about `17.1 M` items
- cost explorer dominated by `EUW2-WriteRequestUnits`, not by storage

That distinction mattered. If storage had been the cost driver, the remedy would have been retention or table-shape work. It was not. The cost driver was write amplification on the live Lambda hot path.

I confirmed that the live Lambda was still running `IG_RECEIPT_STORAGE_MODE = ddb_hot` and that the idempotency row was carrying the entire receipt body inline in `receipt_payload_json`. The sampled old rows were roughly `2 KB` each, which explains why a supposedly lightweight dedupe table was consuming such a large write surface during bounded `Phase 0` runs.

I first tested the obvious alternative: move the Lambda to `object_store` receipt mode and keep DynamoDB only as the small dedupe ledger. That was a valid production question, so I tried it live rather than speculating.

The result was decisively bad on the current envelope. `phase0_20260310T164435Z` collapsed almost immediately:

- admitted throughput fell to about `65.6 eps`
- valid traffic began receiving `IG_PUSH_REJECTED`
- Lambda logs showed `KAFKA_PUBLISH_TIMEOUT`
- quarantine receipts recorded `PUBLISH_AMBIGUOUS`

That failure was useful because it narrowed the real boundary. The platform is not ready for object-store receipt persistence on the Lambda hot path at the declared `Phase 0` steady envelope. Keeping that change would have reduced DynamoDB cost by breaking the production shape, which is explicitly disallowed by the plan.

So I changed posture rather than forcing the cheaper path. The right remediation is:

- keep the proven fast `ddb_hot` mode,
- remove the wasteful part of it,
- preserve the same semantic and latency posture.

I patched `DdbAdmissionIndex` so `receipt_payload_json` now stores only a compact receipt summary instead of the whole payload. The compact live row keeps only the fields needed for run attribution and fast lookup:

- `receipt_id`
- `decision`
- `event_id`
- `event_type`
- `platform_run_id`
- `scenario_run_id`
- `ts_utc`
- `admitted_at_utc`
- `schema_version`
- `reason_codes` only when present

I added a targeted unit test for that serializer, rebuilt the Lambda bundle, redeployed the live function, and reran the frozen `Phase 0.B` baseline as `phase0_20260310T165309Z`.

That rerun behaved the right way:

- `4xx = 0`
- `5xx = 0`
- `p95 ≈ 52.0 ms`
- `p99 ≈ 60.4 ms`
- no lane collapse
- no publish ambiguity
- the only red remained the already-known stale minute-bin throughput gate at `2999.575 eps`

The live DynamoDB evidence also confirmed the cost improvement without changing the proof shape. A fresh admitted row from `platform_20260310T165309Z` now stores a `392`-byte compact receipt body rather than the earlier roughly `2 KB` inline payload. Minute-level `ConsumedWriteCapacityUnits` on the successful rerun sat around `488k` to `540k WRU/min`, versus the earlier successful baseline around `~720k WRU/min`.

So the current judgment is:

- the DynamoDB cost complaint was real
- the bad part was write amplification, not storage posture
- `object_store` receipts on Lambda are not yet viable at the declared envelope
- compact `ddb_hot` receipts materially reduce write cost while preserving the truthful `Phase 0.B` runtime behavior
- the active blocker for `Phase 0.B` is still the proof-gate codification, not a newly reopened ingress or cost-induced runtime defect

## 2026-03-10 17:58:54 +00:00
The next round of `Phase 0.B` work changed the blocker again, and this time the change is valuable because it isolates what is left.

I first codified the truthful APIGW-side proof boundary into the dispatcher rather than keeping it as manual analysis:

- APIGW access-log group is now resolved from the live stage
- the summary records exact APIGW access-log window evidence alongside the older metric-bin view
- the final gate can now distinguish between the aligned metric view and the exact APIGW log window

That work exposed another methodological defect immediately. The first exact-window implementation anchored the final count on `active_confirmed_utc`, which made the proof depend too heavily on where fleet confirmation happened to land inside the minute. That was not a good steady-state boundary. I repinned the exact-log count to the same aligned steady window as the parent proof and added a lag guard so the dispatcher does not finalize while APIGW access logs are still obviously behind the already-settled metric window.

While doing that I learned something important about the managed telemetry surfaces themselves:

- API Gateway detailed metrics now expose route-level `Count` for `POST /ingest/push`
- stage-wide `Count` is not clean enough for this phase because it can include other routes
- exact APIGW access logs are the more truthful per-request surface, but their delivery lag is variable enough that they cannot be snapshotted too early

I then tested several narrow proof shapes against that corrected understanding.

The `warmup_seconds = 60` change was a real improvement. It removed the accidental dependence on minute alignment that had been giving some runs almost no pre-window settle time and other runs nearly a full minute. But it did not close the phase by itself. The warmup-only run `phase0_20260310T171930Z` still came in essentially on the line at `2999.55 eps`, which is too close to treat as a stable proof.

I then tested the next narrow idea: keep the gate at `3000 eps` but bias the WSP source target slightly above it to stop the proof from being source-limited by tiny pacing granularity loss. That candidate shape was:

- `warmup_seconds = 60`
- `target_request_rate_eps = 3010`
- exact aligned APIGW log gate

One run on that shape did go green:

- `phase0_20260310T173526Z`
- `3011.94 eps`
- `4xx = 0`
- `5xx = 0`
- `p95 ≈ 48.0 ms`
- `p99 ≈ 55.0 ms`

But the repeatability test is what mattered, and that is where the real blocker surfaced.

The repeat `phase0_20260310T174232Z` went materially red again. To stop guessing, I reran the same candidate shape once more with full lane logs as `phase0_20260310T175034Z`. That full-log run gave the missing attribution:

- one lane (`wsp_lane_06`) exited early with `IG_PUSH_REJECTED`
- ECS marked it `EssentialContainerExited`
- that lane emitted `0`
- aggregate WSP progress-derived emitted count still showed the fleet trying to work (`612877`), but the admitted ingress rate collapsed to `2401.22 eps`
- APIGW still showed `4xx = 0` and `5xx = 0`, so this is not the same as the earlier public-edge overload posture

That changes the truthful engineering judgment again:

- `Phase 0.B` is no longer blocked by the stale minute-bin proof gate
- it is no longer blocked by the DynamoDB cost posture
- it is not presently blocked by a generic APIGW semantic defect either
- it is now blocked by unstable WSP-side lane behavior under the candidate steady-state proof shape, with at least one concrete failing lane showing `IG_PUSH_REJECTED`

So the next narrow action is not another blind throughput rerun. It is to inspect and harden the WSP push/retry path around that lane-level rejection so the bounded `Phase 0.B` proof can become repeatable on the same declared boundary.

## 2026-03-10 18:07:03 +00:00
I am changing my documentation posture here because the user is right about the failure mode.

The implementation notes should not trail the work as a retrospective summary after several material changes have already happened. They need to move with the work so the current problem shape, the current hypothesis, and the current branch in the road are visible while the phase is still open.

So before I continue `Phase 0.B` remediation I am pinning the next active branch explicitly:

- the unresolved runtime blocker remains the WSP-side lane instability observed as `IG_PUSH_REJECTED`
- before resuming that remediation, I am inspecting the next major cost surfaces the user called out: `ECS`, `MSK`, and the relational database
- the purpose is not to weaken the platform or remove needed evidence, but to find spend that is not serving the production-ready goal of the current proving method

I also need to restore branch hygiene while this is in flight. The repo now has enough material change that it should be committed and pushed on the active working branch rather than left only in the local workspace.

## 2026-03-10 18:12:41 +00:00
The cost pass is now specific enough to act on.

The first useful narrowing was ECS. Cost Explorer had already shown the large ECS spikes were Fargate task-hours, not transfer. The live AWS inspection now tells me something narrower and more operationally useful:

- the active external `Phase 0` boundary is still `API Gateway -> Lambda`
- the retained internal ingress ECS service is still provisioned live
- but it is not serving the current boundary and is already scaled to `desiredCount = 0`
- Terraform's current desired posture already says `ig_service_enabled = false`

That means the remaining ECS ingress cost problem is not "we need to tune the service." It is "we are carrying live drift that no longer serves the current proving boundary." The internal ALB, ECS cluster/service shell, task definition lineage, security groups, ECS log group, and stale SSM service URL are all still materially present even though the current proving method explicitly excludes that path from the active Control + Ingress boundary.

The Terraform plan made that explicit. Once I supplied the current code changes locally and ran the runtime plan, the desired diff was:

- create the codified APIGW access-log resources that now support the truthful Phase 0 proof boundary
- destroy the retained internal ingress ECS / ALB / SSM stack because `ig_service_enabled = false`

That is the right cost posture for the current phase: remove the live ingress stack that is no longer part of the accepted production-ready network instead of leaving it around simply because it was useful earlier.

The only thing that stopped immediate apply was not uncertainty about the destroy. It was deployment hygiene around the Lambda package. The runtime workspace now enforces the remote-bundle triplet for `aws_lambda_function.ig_handler`, and the live Lambda has drifted ahead of Terraform state because recent bounded Phase 0 deploys updated the function directly. So I need to repin the current ingress Lambda into a fresh remote artifact first, then apply the runtime reconciliation safely.

Aurora and MSK do not currently justify the same kind of blunt live removal.

For Aurora:

- the cluster is serverless-v2 with `MinCapacity = 0.5`, `MaxCapacity = 4.0`
- quiet periods do settle back near the floor
- the expensive periods are tied to heavy write I/O and connection churn during active platform work

So Aurora is not the same as the retained internal ingress stack. It is not obviously "wired but unused." It is being driven by runtime write patterns. The right next move there is attribution of which platform writers are causing unnecessary churn, not just lowering capacity and risking a false green or a later latent bottleneck.

For MSK:

- the fixed serverless cluster-hour cost is real and always on
- the variable spike is bytes in/out during hardening windows
- that again points more toward traffic and duplication discipline than toward an immediate safe topology cut

So the current engineering judgment is:

- the next accepted cost remediation is to reconcile away the retained internal ingress ECS / ALB / SSM drift
- Aurora and MSK remain in the cost-investigation set, but their spend is currently tied to active runtime behavior rather than to an obviously obsolete retained surface
- I should not weaken those two yet just to make the bill look cleaner

The next action from here is therefore:

- build a fresh authoritative ingress Lambda artifact from the current repo state
- upload it to the runtime artifacts bucket
- apply the runtime stack so the APIGW telemetry resources are codified and the unused internal ingress stack is removed without rolling the live Lambda backward

## 2026-03-10 18:17:03 +00:00
The cost reconciliation is now materially complete for the obsolete ingress surface.

I built a fresh authoritative Lambda artifact from the current repo state using the existing deterministic bundle path, uploaded it as:

- `s3://fraud-platform-dev-full-artifacts/artifacts/lambda/ig_handler/manual-20260310T181500Z.zip`
- `sha256_base64 = 3DxIaUwPXkI7syppAvP03Ut+c9gOOsNw+bFA4PHmqn8=`

That step mattered because the runtime workspace would not safely plan or apply otherwise. The earlier apply had already shown the right destroy set, but the live Lambda had moved ahead of Terraform state through bounded `Phase 0` deploys, so a careless reconcile would have risked rolling ingress code backward while trying to save cost. Re-pinning the live bundle first removed that risk.

While verifying the workspace before apply I also found a local proving-harness defect that would have become another blindspot later: `scripts/dev_substrate/pr3_wsp_replay_dispatch.py` contained an invalid f-string expression in the APIGW access-log query builder. That is now fixed by precomputing the escaped route key before formatting the query. The harness compiles again.

The runtime reconcile then proceeded in two passes:

1. first apply:
   - refreshed the live Lambda to the fresh remote artifact
   - destroyed the retained internal ingress surface
   - failed only because the APIGW access-log group already existed live from the earlier manual telemetry bootstrap
2. state recovery + second apply:
   - imported `/aws/apigateway/fraud-platform-dev-full-ig-edge-v1-access` into Terraform state
   - reran the plan
   - applied the final stage/log-group reconciliation cleanly

The important production outcome is that the obsolete internal ingress surface is now gone:

- ALB `fp-dev-full-ig-svc` is removed
- stale SSM parameter `/fraud-platform/dev_full/ig/service_url` is removed
- the ingress ECS cluster is now `INACTIVE`
- `runtime_handle_materialization` now truthfully shows:
  - `IG_SERVICE_ENABLED = false`
  - `IG_SERVICE_NAME = null`
  - `IG_SERVICE_CLUSTER_NAME = null`
  - `SSM_IG_SERVICE_URL_PATH = null`

The APIGW telemetry surface is also now properly codified rather than being partly manual:

- stage `v1` now shows `DetailedMetricsEnabled = true`
- access logs are attached to `/aws/apigateway/fraud-platform-dev-full-ig-edge-v1-access`
- the managed CloudWatch Logs resource policy is `fraud-platform-dev-full-ig-api-access`
- the earlier manual duplicate policy has been removed, so this surface is back to single ownership

The live Lambda is now pinned to the fresh bundle and remains on the intended `Phase 0` posture:

- `LastModified = 2026-03-10T18:14:47.000+0000`
- `CodeSha256 = 3DxIaUwPXkI7syppAvP03Ut+c9gOOsNw+bFA4PHmqn8=`
- `IG_HEALTH_BUS_PROBE_MODE = none`
- `IG_RECEIPT_STORAGE_MODE = ddb_hot`
- reserved concurrency remains `600`

So the current truthful judgment after this cost pass is:

- the obsolete retained ingress ECS / ALB / SSM path was a real cost-and-drift defect
- it has now been reconciled away without weakening the active Control + Ingress proving boundary
- APIGW telemetry is now codified in Terraform rather than partly manual
- Aurora and MSK are still open cost questions, but of a different class:
  - they are being actively driven by runtime behavior rather than by an obviously obsolete retained surface
  - so they require narrow write-path and traffic attribution, not topology removal by instinct

That means the next active technical blocker returns cleanly to `Phase 0.B` itself:

- WSP-side instability under the candidate steady-state shape
- specifically the lane-level `IG_PUSH_REJECTED` failure family that made repeatability collapse

## 2026-03-10 18:24:00 +00:00
Before returning to the remaining `Phase 0.B` repeatability blocker, I started the next explicit cost-discipline pass the user called out: `ECS | MSK | relational database`.

The posture for this pass is narrow and production-honest. I am not looking for cosmetic bill reduction or topology cuts that weaken the active proving boundary. I am looking for spend caused by retained drift, overprovisioned proving defaults, duplicated evidence paths, or hardening-side runtime behavior that does not materially help the platform reach production readiness.

The first live split already changed the question materially:

- `ECS` is no longer an idle-service problem after removing the retained internal ingress stack
- `MSK` is not mainly a topic-storage problem
- `Aurora` is not mainly a database-size problem

So the useful work here is to identify the proving-side behaviors that are inflating those bills before I spend more money on another `Phase 0.B` iteration.

## 2026-03-10 18:33:00 +00:00
The live cost surfaces are now clear enough to stop guessing.

For `ECS`, the only remaining live cluster is `fraud-platform-dev-full-wsp-ephemeral`. It is idle right now (`runningTasksCount = 0`, `activeServicesCount = 0`), so the bill is not coming from a retained always-on ECS surface anymore. Cost Explorer shows the spend on March 7-9 was almost entirely:

- `EUW2-Fargate-vCPU-Hours:perCPU`
- `EUW2-Fargate-GB-Hours`

That immediately points to the proving harness itself: remote WSP replay tasks. The live task definition confirms those tasks are being launched at `cpu = 1024` and `memory = 2048`. For bounded `Phase 0` proof this is expensive enough that I should not keep treating it as free just because it is “only the load generator”.

For `MSK`, the dominant daily line items are:

- `KafkaServerless-ClusterHours`
- then `KafkaServerless-In-Bytes`
- then `KafkaServerless-Out-Bytes`

`PartitionHours` and storage are small by comparison. That means the main MSK bill is a combination of the unavoidable serverless floor plus run traffic, not runaway topic retention. This is important because it means a blind topic-partition cleanup would not materially solve the current bill and could still create churn. There is no truthful MSK cut to make yet without changing runtime shape or deleting substrate, which I do not want to do during active hardening.

For `Aurora`, the bill shape is even clearer:

- `Aurora:StorageIOUsage` dominates
- `Aurora:ServerlessV2Usage` is second
- storage footprint itself is tiny

CloudWatch supports that reading. `VolumeWriteIOPs` spikes into the millions during active hardening windows, `ACUUtilization` sits near saturation in those same windows, and `DatabaseConnections` spikes above `200`. So the relational-database spend is being driven by high write churn and connection churn during proving, not by a simple baseline floor.

That changes the next accepted remediation. The strongest proving-side suspects are now:

- WSP Fargate task sizing for bounded replay
- WSP checkpoint pressure on Aurora
- WSP ECS logs retaining forever

Those three are all worth fixing before spending on another full `Phase 0.B` repetition because they are hardening-side costs, not platform truths that must be preserved as-is.

## 2026-03-10 18:39:00 +00:00
I have now pushed this cost pass far enough to separate the accepted fixes from the still-ambiguous ones.

The accepted fixes are:

1. WSP log retention is no longer unbounded.
   The log group `/ecs/fraud-platform-dev-full-wsp-ephemeral` was live with `retentionInDays = null`. I set it to `7` days. That is a direct cost/housekeeping correction with no impact on runtime truth.

2. `Phase 0` WSP checkpoints no longer need to default to Aurora durability.
   I patched WSP config loading so checkpoint backend, root, DSN, and flush frequency can be overridden by environment. Then I patched the `Phase 0` wrapper / dispatcher path so the bounded `Phase 0` run can default to:
   - `WSP_CHECKPOINT_BACKEND=file`
   - `WSP_CHECKPOINT_ROOT=/tmp/wsp-checkpoints`
   - `WSP_CHECKPOINT_FLUSH_EVERY=50000`

   That is the right proving posture. WSP checkpoint durability is a harness concern, not part of the active `Control + Ingress` production boundary, so there is no reason to keep paying Aurora write I/O for it by default during short bounded proof windows.

3. The wrapper defaults are repinned to the truthful frozen `Phase 0` shape.
   The local CLI wrapper was still carrying old default values (`24` lanes / `19.7x`) even though the current accepted baseline is `40` lanes / `51.2x`. I corrected that so future local invocations are less likely to rerun the wrong shape by accident.

I also tested WSP task right-sizing, because that is where most of the remaining ECS cost lives. The result is not clean enough yet to promote:

- first calibration at the stale `24`-lane shape proved only that the cheap posture can run syntactically; it was not the truthful `Phase 0` baseline and therefore not decision-worthy
- second calibration at the truthful `40`-lane / `51.2x` shape, with `512 CPU / 1024 MiB` overrides and file checkpoints, stayed semantically clean but produced an ambiguous measurement split:
  - aligned APIGW bins were essentially at target (`2999.908 eps`)
  - exact access-log window came back materially lower (`2903.800 eps`)

That discrepancy is too large to treat as noise. Under the telemetry-first posture, I cannot call that task right-sizing safe yet. So I am not keeping reduced WSP task size as the default. I am keeping the override capability in place for future narrow calibration, but the accepted default remains the task-definition size until the exact-window evidence is trustworthy.

So the current truthful cost judgment is:

- accepted now:
  - WSP log retention `7d`
  - file-backed WSP checkpoints for bounded `Phase 0`
  - drastically reduced checkpoint flush pressure
  - wrapper repinned to the real frozen baseline
- not yet accepted:
  - reduced WSP task CPU / memory as the default `Phase 0` posture

That means I have removed the clear proving-side waste without weakening the active proof boundary, and I have deliberately left the ambiguous ECS right-sizing change out of the default path.

## 2026-03-10 18:24:00 +00:00
Before returning to the remaining `Phase 0.B` repeatability blocker, I am doing the next cost-discipline pass the user explicitly called out: `ECS | MSK | relational database`.

The posture for this pass is intentionally narrow. I am not looking for a cosmetic bill reduction or for topology cuts that would weaken the active proving boundary. I am looking for spend that is being created by retained drift, overprovisioned defaults, duplicated evidence paths, or runtime behaviors that do not materially help the platform reach production readiness.

The immediate questions are:

- which ECS surfaces are still live and whether any of them are retained but not serving the active Control + Ingress proving boundary
- whether MSK cost is dominated by unavoidable serverless baseline versus avoidable traffic duplication or retention posture
- whether Aurora cost is baseline floor, connection churn, or write amplification driven by current proving / telemetry behavior

I am treating this as another engineering problem to be understood before changing anything. Any accepted change from here has to preserve the production shape and keep `Phase 0` attribution truthful.

## 2026-03-10 18:46:00 +00:00
I am back on the direct `Phase 0.B` execution loop now.

The remaining question after the cost pass is narrow: whether the accepted cheaper proving posture (`file` checkpoints, high checkpoint flush interval, WSP log retention guardrail) still closes the truthful frozen baseline when the APIGW exact-window verifier is allowed its normal settle window.

The `30 s` settle calibration was useful for cost attribution, but not decision-grade for closure. It reintroduced a large split between aligned APIGW route metrics and exact access-log counts under the reduced-cost experiment. That is not enough to repin the proof boundary or to close the phase. It is only enough to say the aggressive cost posture is not yet promotion-safe.

So the next move is back to the accepted baseline:

- frozen unsynchronized `40`-lane / `51.2x` shape
- default WSP task size from the task definition
- file-backed WSP checkpoints
- normal measurement / metric-settle posture

If that run comes back green on the exact-window gate with the accepted cost fixes still in place, then the cost pass can be treated as production-safe and I can continue closing `Phase 0.B` instead of debating the cost posture further.

## 2026-03-10 19:03:00 +00:00
The accepted cost posture held on the real frozen `Phase 0.B` baseline.

Run:
- `phase0_20260310T185503Z`
- generated by `phase0-baseline-after-cost-pass`

Result:
- verdict `REMOTE_WSP_WINDOW_READY`
- `open_blockers = 0`
- exact APIGW access-log window `= 362215` successful `202` requests over `120 s`
- exact admitted throughput `= 3018.458 eps`
- `4xx = 0`
- `5xx = 0`
- `p95 = 46.997 ms`
- `p99 = 53.947 ms`

Most importantly, this rerun used the accepted cheaper proving posture that should stay:

- WSP checkpoints on `file`
- `WSP_CHECKPOINT_FLUSH_EVERY = 50000`
- WSP log retention bounded at `7d`
- default WSP task-definition size retained

That matters because it means the accepted cost cleanup did not reopen `Phase 0.B`. The earlier `30 s` calibration discrepancy belongs to the aggressive task right-sizing experiment, not to the accepted cost posture.

So the current truthful state is:

- `Phase 0.B` is now green on the codified exact-window APIGW access-log gate
- the accepted cost posture is production-safe for bounded `Phase 0`
- the next active boundary is `Phase 0.C`: bounded envelope and recovery proof

I am therefore stopping steady-state reruns here and moving to the burst/recovery boundary instead of spending more money re-proving an already-closed subphase.

## 2026-03-10 19:07:00 +00:00
I have paused long enough to repin the actual `Phase 0.C` execution problem before touching code or spending on another run.

`Phase 0.B` is green. The open boundary is not steady-state ingress anymore; it is truthful burst and recovery proof on the same live `API Gateway -> Lambda` surface.

The existing generic recovery tooling is close, but not truthful enough for this phase as-is:

- the dispatcher can already drive a continuous scheduled `WSP` campaign against the real APIGW edge
- the current `pr3_s3_rollup.py` continuous path still hard-blocks on `ALB`
- it also assumes the recovery proof should be interpreted through later-stage component snapshots that are not necessary to decide `Control + Ingress`

If I force that tool unchanged, I will be proving the wrong ingress surface and importing proof requirements from outside the active plane. That would be a methodology defect, not just a tooling inconvenience.

So the `Phase 0.C` posture is now explicitly:

- keep the proving surface as `API Gateway -> Lambda`
- run one continuous bounded campaign with explicit scheduled rate segments
- evaluate exact sub-windows directly from APIGW access logs rather than from coarse minute alignment alone
- keep the evidence set narrow:
  - steady window truth
  - burst window truth
  - recovery window truth
  - zero meaningful `4xx/5xx`
  - no publish-failure or DLQ growth signals during the run

This is the same dynamic-posture rule the user has been emphasizing: the phase goal stays fixed, but the proving method changes once it becomes clear that the current tooling would create a blindspot or the wrong attribution boundary.

The next concrete work is therefore:

1. add a narrow `Phase 0.C` execution/evaluation path that reuses the accepted dispatcher and APIGW exact-window telemetry
2. keep the accepted cheaper proving posture from `Phase 0.B`
3. run the bounded envelope campaign once the evaluation path is truthful
4. only then decide whether `Phase 0.C` is green or whether the burst/recovery boundary itself needs narrow remediation

## 2026-03-10 19:20:00 +00:00
The first truthful `Phase 0.C` run is now complete, and it materially changed the diagnosis.

Run:

- `phase0_20260310T191050Z`
- generated by `phase0-envelope-after-phase0b-green`
- continuous APIGW campaign
- `48` lanes
- `600.0x` stream speedup
- scheduled windows:
  - `90 s` steady at `3000 eps`
  - `30 s` burst at `6000 eps`
  - `180 s` recovery target at `3000 eps`
- accepted cheaper proving posture retained:
  - file checkpoints
  - high checkpoint flush interval
  - bounded log retention

What actually happened is important:

- the run did **not** fail first in the burst window
- it collapsed during the opening steady segment
- APIGW exact steady-window throughput was only about `622.44 eps`
- APIGW steady window carried `404` `4xx` and `2672` `5xx`
- steady latency blew out (`p95 ~ 416.49 ms`, `p99 ~ 11675.83 ms`)
- Lambda metrics for the run window showed `Errors = 182`, `Throttles = 1634`
- WSP lane tails showed repeated `http_503` retries followed by:
  - `IG_PUSH_REJECTED`
  - `IG_PUSH_RETRY_EXHAUSTED`

This matters because it narrows the real problem sharply.

The platform has not yet told me that `6000` burst is impossible. What it has told me is that the current `Phase 0.C` proof shape is wrong for a fresh run identity:

- all lanes are released against the exact same campaign start
- the ingress gate for a fresh `platform_run_id` has to initialize under that shock
- Lambda concurrency then falls into throttling before the proof ever reaches a stable steady segment

So the current red is not yet a truthful envelope verdict. It is a synchronized cold-start / fresh-gate shock verdict.

That means the next adaptation should be narrow and methodological:

- keep the same production target
- keep the same APIGW proof surface
- keep the steady / burst / recovery proof requirement
- add a non-scored presteady warmup segment so the measured steady window begins only after gate and Lambda cold posture have settled

This is exactly the dynamic-posture rule the user has been emphasizing: do not stay rigid once the run has shown that the current shape is answering the wrong question. The goal is still `Phase 0.C`. The change is only in how the proof is staged so it measures real envelope behavior rather than synchronized startup shock.

## 2026-03-10 19:31:00 +00:00
The warmup-adjusted rerun also came back red, but it changed the diagnosis again in a useful way.

Run:

- `phase0_20260310T192032Z`
- generated by `phase0-envelope-presteady-warmup`
- same `48` lanes / `600.0x` source posture
- added non-scored presteady warmup:
  - `60 s` at `1500 eps`

The important part is what *did not* happen:

- Lambda `Errors = 0`
- Lambda `Throttles = 0`

So the red is no longer an infra-throttle story.

CloudWatch Lambda logs for this run show the real failure class:

- `IG transient retry required ... reason=PUBLISH_IN_FLIGHT_RETRY`
- `IG transient retry required ... reason=PUBLISH_AMBIGUOUS_RETRY`

The request-timing and metrics logs explain why those retries are surfacing:

- `phase.publish_seconds` repeatedly stretches into multi-second territory
- some publish calls run around `4 s` to `10 s`
- those long publish attempts then drive `PUBLISH_AMBIGUOUS` and leave later attempts seeing in-flight / ambiguous dedupe state

That means the active blocker is now narrower and clearer:

- the current continuous `WSP` source posture (`48` lanes, `600.0x`, scheduled campaign) is overdriving the ingress publish path before the scored windows even settle
- this is not yet a truthful statement that the platform cannot hold `6000` burst
- it *is* a truthful statement that the current `Phase 0.C` source posture is not promotion-safe

So the next adaptation is not another doc-only change and not another repeat of the same 48-lane posture.

The next narrow action should be:

1. recalibrate `Phase 0.C` from the already-proven steady-state source posture (`40` lanes, `51.2x`) instead of the borrowed `PR3.S5` stress defaults
2. keep the APIGW exact-window evaluator
3. increase pressure only as far as needed to answer the burst question, instead of starting from the larger stress-oriented source posture

This is cheaper and methodologically cleaner because it isolates whether the blocker is the burst target itself or merely the aggressive continuous-source shape I chose for the first `Phase 0.C` attempts.

## 2026-03-10 19:41:00 +00:00
The `40`-lane / `51.2x` recalibration did not rescue the current `Phase 0.C` shape.

Run:

- `phase0_20260310T193106Z`
- generated by `phase0-envelope-baseline-lanes40-speed51p2`
- `40` lanes
- `51.2x` stream speedup
- same presteady warmup:
  - `60 s` at `1500 eps`

This matters because it rules out the earlier hypothesis that the main defect was just the borrowed `48`-lane / `600.0x` stress posture.

The run still failed in the presteady portion, before the scored steady window began:

- APIGW exact window from `19:33:30Z` to `19:34:51Z` only admitted about `352.99 eps`
- `4xx = 411`
- `5xx = 1367`
- abnormal WSP lanes again ended on `IG_PUSH_REJECTED`

Combined with the earlier `PUBLISH_IN_FLIGHT_RETRY` / `PUBLISH_AMBIGUOUS_RETRY` logs, the remaining common factor is now clearer:

- the fleet is still entering each scheduled segment at the same instant
- the resulting segment-edge shock is enough to destabilize the publish path even when I fall back to the previously proven `40`-lane source posture

So the next methodological correction is not another rate or lane-count experiment by itself.

The next correction is:

- keep one continuous run identity
- keep one continuous APIGW proof
- stagger lane campaign starts across the fleet
- start scoring each segment only after the last lane has entered that segment

That should preserve the real `Phase 0.C` goal while removing the artificial step-function fleet transition that is still contaminating the result.

## 2026-03-10 19:42:34 +00:00
Before touching the `Phase 0.C` runner again, I stopped to name the active error properly because the last two reruns were no longer teaching anything new at the original posture.

The important distinction is:

- this is not a generic "burst is too hard" result
- this is not a reopening of `Phase 0.B`
- this is not a reason to lower the `6000 eps` burst target

It is a proving-shape defect inside the current `Phase 0.C` method.

The shared symptom across the two failed reruns is that the fleet is still making a hard synchronized transition into each scheduled segment. Once that happens, the publish path starts seeing ambiguous / in-flight retry pressure, `WSP` lanes begin to reject pushes, and the scored windows never become trustworthy.

So the next move is a method correction, not another traffic experiment:

1. add per-lane campaign-start staggering to the dispatcher
2. propagate that same staggering into the `Phase 0.C` envelope wrapper
3. extend total campaign duration by the fleet-spread amount
4. move the scored APIGW windows so they start only after the last lane has entered the segment

That preserves the real production question:

- can the live external ingress boundary hold steady, burst, then recover on one continuous proof campaign?

while removing the artificial fleet step-function that is currently polluting the answer.

## 2026-03-10 19:43:08 +00:00
The stagger correction is now executable.

I finished the code path so the dispatcher can offset `WSP_CAMPAIGN_START_UTC` per lane, and the `Phase 0.C` wrapper now accounts for the resulting fleet-spread in three places:

- dispatch duration is extended by the campaign-start spread
- the scored APIGW windows are delayed until the full fleet has entered the segment
- the summary artifacts now carry both `campaign_start_stagger_seconds` and `campaign_start_spread_seconds`

Local validation passed:

- `py_compile` clean on `pr3_wsp_replay_dispatch.py` and `phase0_control_ingress_envelope.py`
- `--dry-run` shows:
  - `48` lanes
  - `0.5 s` campaign-start stagger
  - `23.5 s` total fleet spread
  - scored steady window no longer starts at raw campaign start plus presteady only

This is the right next bounded posture because it keeps the same `Phase 0.C` goal while removing the synchronized segment-edge artifact that was dominating the last two reruns.

## 2026-03-10 19:57:54 +00:00
The staggered `Phase 0.C` rerun was the right correction because it finally separated the proof-shape defect from the actual ingress verdict.

Run:

- `phase0_20260310T194344Z`
- generated by `phase0-envelope-staggered-lanes40-speed51p2`
- `40` lanes
- `51.2x` stream speedup
- presteady `60 s @ 1500 eps`
- campaign-start stagger `0.5 s` per lane
- full fleet spread `19.5 s`

What changed materially:

- the run no longer collapsed at segment entry
- dispatcher stayed green (`REMOTE_WSP_WINDOW_READY`)
- Lambda `Errors = 0`
- Lambda `Throttles = 0`
- DLQ delta `= 0`
- recovery is now clean and immediate:
  - recovery admitted `3029.55 eps`
  - `4xx = 0`
  - `5xx = 0`
  - sustained green from the first `30 s` recovery bin

So the synchronized fleet-entry problem was real, and the stagger correction removed it.

The remaining blockers are now much narrower:

- steady window still carries `4874` `4xx`
- burst window carries `10478` `4xx`
- burst admitted throughput reaches only `3201.13 eps` against `6000 eps`

That means the active `Phase 0.C` problem has changed shape again:

- not fleet-start collapse
- not Lambda infra saturation
- not DLQ growth
- now either a request-class rejection problem, a burst-realization problem in the source path, or both

The next narrow step is to classify the `4xx` precisely from APIGW access logs / Lambda logs and determine whether burst is being limited by ingress rejection or by the current `WSP` source realization.

## 2026-03-10 20:00:10 +00:00
The `4xx` class is now pinned, and it materially changes what `Phase 0.C` means.

They are not Lambda semantic rejections. They are API Gateway throttles:

- steady-window `4xx` were all `429`
- burst-window `4xx` were all `429`
- `integration_status = "-"`, so those requests never reached Lambda
- stage `v1` is configured live at:
  - `ThrottlingRateLimit = 3000`
  - `ThrottlingBurstLimit = 6000`

That explains the earlier burst result almost exactly. A `30 s` segment measured at `6000 eps` on a `3000 rate / 6000 burst` token bucket is not a truthful zero-throttle gate. If the bucket starts full, the maximum admitted average over `30 s` is:

- `6000 + (3000 * 30) = 96000` requests
- `96000 / 30 = 3200 eps`

The observed burst result was `3201.13 eps` with `429`s, which is effectively the live token-bucket math announcing itself.

There is also a second, purely harness-side defect in the new staggered scorer:

- I delayed segment scoring until the last lane entered the segment
- but I still ended each scored window when the last lane left it
- that means the scored steady window accidentally included early burst participation
- and the scored burst window accidentally included early recovery participation

The per-second APIGW counts make that obvious:

- the "steady" window is perfectly clean near `3000 eps` for most of the interval, then begins showing `429`s only in the tail where early lanes have already entered burst
- the "burst" window is a mixed overlap window, not a pure all-lanes-burst window

So the next correction is now unambiguous:

1. score only the **full-overlap** window for each staggered segment:
   - segment start = last lane enters
   - segment end = first lane leaves
2. reject stagger settings that leave no full-overlap window
3. replan the burst segment itself around the live `3000 / 6000` token-bucket semantics instead of the arbitrary earlier `30 s @ 6000 eps` average

That is not a relaxation of the production target. It is finally making the proof match the live boundary we are actually hardening.

## 2026-03-10 20:01:51 +00:00
I have now applied the scorer correction, not just described it.

The `Phase 0.C` envelope runner now scores only the full-overlap window for each staggered segment:

- steady overlap = `steady_seconds - campaign_start_spread_seconds`
- burst overlap = `burst_seconds - campaign_start_spread_seconds`
- recovery overlap = `recovery_seconds - campaign_start_spread_seconds`

It also now hard-fails if a chosen segment duration is shorter than the fleet spread, because that would leave no truthful scored window at all.

The dry-run for the current `40`-lane / `0.5 s` stagger posture now makes the overlap truth explicit:

- steady overlap `= 70.5 s`
- burst overlap `= 10.5 s`
- recovery overlap `= 160.5 s`

I also updated the active `Phase 0` map so the burst proof is explicitly tied to the live APIGW token-bucket semantics and the full-overlap rule. That keeps the phase authority aligned with the now-proven runtime reality instead of with the earlier arbitrary `30 s` burst assumption.

Next move:

- checkpoint these corrections in git
- rerun `Phase 0.C` with a burst window derived from the live edge semantics, not from the earlier arbitrary duration

## 2026-03-10 20:03:05 +00:00
I now have a concrete next run shape that is derived from the live edge instead of from hand-wavy "bounded burst" wording.

Given the current APIGW stage:

- rate limit `= 3000`
- burst bucket `= 6000`

the clean no-throttle burst proof needs a short full-overlap window around `2 s`, not a long multi-second average.

To make that burst window both truthful and measurable:

- use a total fleet spread of `1.0 s`
- with `40` lanes, that means `campaign_start_stagger_seconds = 1 / 39 ≈ 0.025641`
- set `burst_seconds = 3`
- score only the full-overlap burst window, which then becomes exactly `2.0 s`

That gives three useful properties at once:

1. the burst proof now matches the live token-bucket semantics
2. the scored burst window lands on exact-second boundaries, which keeps the APIGW access-log query honest
3. the fleet is still slightly spread instead of perfectly synchronized

The next run will therefore keep the already-proven steady source posture (`40` lanes / `51.2x`) and change only the burst proof shape to this token-bucket-derived form.

## 2026-03-10 20:13:45 +00:00
The short-spread rerun (`phase0_20260310T200312Z`) failed usefully because it exposed a design error in my own timing model.

Shrinking total fleet spread back to `1 s` reintroduced the original startup-collapse pattern:

- all `40` lanes went red
- WSP logs showed repeated `http_503`
- every lane ended `IG_PUSH_REJECTED`
- APIGW exact window only admitted about `260.93 eps`
- `5xx = 1126`
- `p95 ≈ 2004.87 ms`
- `p99 ≈ 26653.88 ms`

That means the small-spread run shape is not promotion-safe, even though its burst window was mathematically closer to the live token bucket.

The real issue is that I was still using one knob for two different jobs:

1. startup staggering, which needs to be large enough to avoid the fresh-run collapse
2. rate-plan segment timing, which needs to stay common so steady / burst / recovery can be scored truthfully

I have now split those responsibilities:

- `WSP_CAMPAIGN_START_UTC` remains per-lane and can stay safely staggered
- new `WSP_RATE_PLAN_START_UTC` is shared across lanes, so the scheduled limiter changes segments on one common clock

This is the missing methodological correction. It lets me keep the safe `19.5 s` startup spread while still scoring a common short burst segment without shrinking the burst window itself.

So the next truthful run shape is now:

- keep `40` lanes / `51.2x`
- keep safe startup spread `= 19.5 s` (`0.5 s` per lane)
- keep common rate-plan origin
- set burst segment duration to `2 s` on the shared schedule

If that run stays semantically clean, it becomes the first real answer to the `6000 burst` question on the live edge.

## 2026-03-10 20:27:50 +00:00
The common-rate-plan rerun (`phase0_20260310T201418Z`) is the cleanest `Phase 0.C` result so far.

What is now green:

- dispatcher green
- `4xx = 0`
- `5xx = 0`
- Lambda `Errors = 0`
- Lambda `Throttles = 0`
- DLQ delta `= 0`
- recovery is green immediately and stays green

So the front door is no longer the active problem.

The remaining red is now purely source realization:

- steady admitted `= 2875.89 eps`
- burst admitted `= 4672.00 eps`

The per-second APIGW counts show exactly why.

Steady window:

- starts around `1578 eps`
- ramps upward for about `20 s`
- then settles right around `3000 eps`

Burst window:

- `3089` requests in the first second
- `3086` requests in the second second

That is not an ingress throttle story and not a semantic rejection story. It is the `WSP` scheduled limiter changing segments with almost-empty buckets.

The cause is in the current per-segment limiter construction:

- each segment re-instantiates a token bucket
- bucket capacity is `target_eps * burst_seconds`
- but `initial_tokens` is still being seeded at the old fixed tiny value (`0.25`)

So every segment begins by starving its own bucket and ramping up slowly. That is why:

- steady takes about `20 s` to reach the declared rate
- the short burst segment never actually realizes the declared `6000 eps` before it ends

This is now the next narrow fix:

- keep the same clean common-rate-plan proof shape
- seed each segment with at least its own bucket capacity (`target_eps * target_burst_seconds`)
- rerun the same bounded `Phase 0.C` shape

If that works, the remaining red should disappear without changing the ingress boundary at all.

## 2026-03-10 20:28:52 +00:00
The limiter-seeding correction is now in place.

`Phase 0.C` no longer seeds each new scheduled segment with the old fixed tiny token value. It now seeds each segment with at least its own bucket capacity:

- `initial_tokens >= target_eps * target_burst_seconds`

For the current `40`-lane proof shape, the dry-run rate plan is now:

- presteady `37.5 eps` lane target -> `9.375` initial tokens
- steady `75.0 eps` lane target -> `18.75` initial tokens
- burst `150.0 eps` lane target -> `37.5` initial tokens
- recovery `75.0 eps` lane target -> `18.75` initial tokens

That is exactly the narrow fix I wanted: same ingress boundary, same timing model, same proof windows, but segment transitions are no longer self-starved by the limiter itself.

Next step is simply to rerun the same clean common-rate-plan `Phase 0.C` shape and see whether the remaining steady / burst shortfalls disappear.

## 2026-03-10 20:43:30 +00:00
The seeded-bucket rerun (`phase0_20260310T202917Z`) clarified the final active limiter for `Phase 0.C`.

It did **not** materially change the burst result:

- steady admitted `= 2881.91 eps`
- burst admitted `= 4718.50 eps`
- still `4xx = 0`, `5xx = 0`

The APIGW per-second counts, together with the WSP code path and live ECS logs, show why:

- WSP still applies oracle-timestamp replay delay (`_delay_seconds(..., speedup)`) before each push
- the ingress limiter sits later, inside `_push_to_ig`
- with `stream_speedup = 51.2`, the replay clock itself is still capping how fast events even arrive at the ingress limiter

This matches the live evidence:

- steady ramps for roughly `20 s`, then stabilizes right around `3000 eps`
- burst never gets near `6000 eps`; it stays around low-`3000` per-second counts in the scored window
- the segment-transition logs prove the limiter is entering segment `2`, but the source still is not feeding it fast enough for the burst target to matter

So the next correction is not an ingress change and not another limiter change.

It is a source-posture correction:

- keep the same clean common-rate-plan proof
- keep the same safe startup spread
- keep the same burst/recovery timing
- raise `stream_speedup` so oracle replay delay no longer dominates the proof

At that point the limiter, not the replay clock, should become the true driver of the ingress envelope.

## 2026-03-10 20:59:49 +00:00
I have paused before another rerun because the error class is now specific enough that another unmodified run would just spend money on the same ambiguity.

The active defect is not in the ingress edge:

- APIGW remains semantically clean on the common-rate-plan shape
- Lambda stays clean
- DLQ stays flat
- recovery is materially strong once the immediate post-burst disturbance passes

The active defect is also no longer in the scheduled limiter itself:

- the common rate-plan clock is correct
- segment bucket seeding is correct
- increasing `stream_speedup` to `100` improved burst realization only partially and introduced first-bin recovery `4xx`, which means raw replay acceleration alone is the wrong lever

The remaining structural problem is that `WSP` is still double-pacing `Phase 0.C`:

1. oracle timestamp replay delay runs first
2. the scheduled ingress limiter runs second

For a proof whose explicit purpose is to verify the ingress envelope under a scheduled rate plan, that is the wrong source posture. It means the proof is still being materially shaped by the oracle replay clock rather than by the declared envelope driver. That is why:

- steady takes too long to reach the target window
- the `2 s` burst segment never fully realizes the declared `6000 eps`
- higher replay speed helps somewhat but does not remove the structural cap cleanly

So the next narrow correction is to let scheduled-rate mode own pacing for `Phase 0.C`.

I do **not** want to remove replay pacing globally. The right change is:

- introduce an explicit runtime switch for scheduled-rate proof mode
- when that switch is enabled and a scheduled rate plan is active, bypass the oracle replay delay
- keep the scheduled limiter in place
- keep the existing lane staggering and common rate-plan clock

That keeps the correction narrow and honest:

- normal replay behavior remains unchanged elsewhere
- only the envelope proof stops double-pacing itself
- the ingress edge is still being tested against the declared schedule rather than against an arbitrary synthetic flood

If the rerun goes green after that change, the conclusion will be that `Phase 0.C` was blocked by source-path proof posture, not by ingress capacity.

## 2026-03-10 21:02:16 +00:00
The narrow source-path correction is now implemented and locally validated.

What changed:

- `WSP` now has an explicit scheduled-rate proof switch:
  - `WSP_DISABLE_REPLAY_DELAY_WHEN_RATE_PLAN=true`
- the bypass only activates when that switch is on **and** a scheduled rate plan is present
- when active, oracle replay delay is skipped and the scheduled ingress limiter becomes the sole pacing surface for the proof
- `Phase 0.C` now passes that switch through the replay dispatcher automatically

I intentionally kept the correction scoped:

- normal replay behavior is unchanged for non-rate-plan runs
- no ingress-edge thresholds were changed
- no APIGW or Lambda sizing was changed

Local validation:

- touched Python files compile cleanly
- `tests/services/world_streamer_producer/test_runner.py` passes
- `tests/services/world_streamer_producer/test_push_retry.py` passes

Those test runs also flushed out a small amount of local test drift:

- one stray assertion fragment in `test_runner.py`
- `test_push_retry.py` was still patching `requests.post` while the runner now uses a session object

I corrected both before proceeding. So the repo is back to a truthful local baseline for the next AWS proof.

## 2026-03-10 21:18:40 +00:00
The bounded rerun (`phase0_20260310T210242Z`) changed the problem again.

What the run itself proved:

- semantics stayed clean
- recovery became fully green:
  - no `4xx`
  - no `5xx`
  - Lambda clean
  - DLQ flat
- but steady and burst remained red:
  - steady `= 2882.96 eps`
  - burst `= 4732.00 eps`

That alone would still suggest a deeper source-path cap. But the live ECS logs showed something more important:

- the running WSP tasks were still logging the **old** scheduled-limiter message shape
- the new `replay delay bypass active ...` log line never appeared

So the actual AWS runtime for `fraud-platform-dev-full-wsp-ephemeral` is still on the old image/task revision (`:60`) and does not contain the local code change I just made.

That means the last rerun is **not** evidence against the correction itself. It is evidence that I was still exercising stale runtime code.

This is now the correct blocker statement for `Phase 0.C`:

- live WSP runtime image drift is preventing truthful revalidation of the latest source-path correction

The next move is therefore not another proof-shape change. It is:

- build and push a fresh runtime image from the current repo state
- register a fresh `fraud-platform-dev-full-wsp-ephemeral` task definition revision
- rerun the same bounded `Phase 0.C` proof against the updated live runtime

That is the only honest way to decide whether the remaining red is real runtime capacity or just stale image drift.

## 2026-03-10 21:35:10 +00:00
The fresh runtime rerun (`phase0_20260310T212058Z`) finally exercised the new source-path code, and the failure mode changed exactly as the logs suggested it would.

What changed materially:

- the new log lines appeared on ECS:
  - `rate_plan_start_utc=...`
  - `WSP replay delay bypass active ...`
- so the live task family drift is resolved
- the source correction is now truly on the AWS surface

What the run then showed:

- the old under-realization problem is gone as the dominant story
- burst admitted jumped to `7271 eps`
- but that came with real red posture:
  - burst `4xx`
  - steady `5xx`
  - Lambda `Errors`
  - Lambda `Throttles`
  - one lane (`wsp_lane_34`) failed with repeated `http_503 -> IG_PUSH_REJECTED`

That means the current posture is now **too aggressive**, not too weak.

The important engineering point is that this is still progress. The stale-image ambiguity is gone, and I now have a truthful live failure mode:

- the scheduled-rate proof can drive the edge hard enough
- but the current per-lane push shape is too bursty for a semantically clean `Phase 0.C` proof

The lane logs make that concrete:

- `http_503` retries begin during steady, not only at the burst segment
- that points to intra-lane emission burstiness rather than just the `2 s` burst segment
- with `4` outputs processed concurrently and `4` push workers per output, each lane can express too much local parallelism once replay delay is removed

So the next narrow correction is not to back out the replay-bypass work. It is to smooth the source posture:

- keep the fresh runtime image
- keep replay bypass
- keep the common rate-plan clock
- reduce intra-output push concurrency first
- rerun the exact same bounded `Phase 0.C` shape

That is the cheapest truthful next move because it preserves the successful parts of the correction while targeting the now-observed overload mechanism directly.

## 2026-03-10 21:49:50 +00:00
The smoothed rerun (`phase0_20260310T213535Z`) is the first near-complete `Phase 0.C` answer on the fresh runtime.

What went green:

- dispatcher green
- steady green:
  - `3005.09 eps`
  - `4xx = 0`
  - `5xx = 0`
- recovery green:
  - `3016.65 eps`
  - immediate sustained green
  - Lambda clean
  - DLQ flat
- no lane failures

What remains red:

- burst admitted `= 5044.50 eps`
- still semantically clean, but below the declared `6000 eps` target

This is a much better posture than the previous rerun because it removes the overload ambiguity without falling back to the old weak source shape. The current picture is now:

- replay bypass is correct
- fresh runtime image is correct
- lane-level push smoothing fixed the overload defect
- only the burst realization is still under target

So the next narrow correction is to increase the source bucket burst window while keeping the now-correct smoothing posture:

- keep `ig_push_concurrency = 1`
- keep the fresh task revision
- keep replay bypass
- keep the common `2 s` scored burst segment
- raise the source token-bucket `burst_seconds` only

That change should let the source express more of the declared burst without reintroducing the earlier steady-state overload.

## 2026-03-10 22:03:15 +00:00
The widened source bucket rerun (`phase0_20260310T215010Z`) ruled out the next obvious hypothesis cleanly.

What stayed good:

- steady remained green
- recovery remained green
- semantics remained clean
- Lambda remained clean

What changed badly:

- burst fell further to `4847.50 eps`

So the burst shortfall is **not** because the source bucket window was too small. Widening it made the source smoother still, which is the opposite of what the remaining burst gate needs.

That narrows the remaining problem again:

- the live runtime now needs a slightly more aggressive concurrency envelope than `ig_push_concurrency = 1`
- but it cannot jump back to the old `ig_push_concurrency = 4` posture, because that reintroduced real overload

So the next truthful move is the obvious midpoint:

- restore the original source bucket window (`0.25 s`)
- keep replay bypass
- keep the fresh runtime image
- raise `ig_push_concurrency` from `1` to `2`
- rerun the same bounded `Phase 0.C` shape

If that lands green, `Phase 0.C` closes. If it still misses burst, then the remaining question becomes whether the declared `6000` burst needs to be proven through a different yet still truthful source-lane geometry rather than through more per-lane parallelism.

## 2026-03-10 22:17:25 +00:00
The midpoint concurrency rerun (`phase0_20260310T220334Z`) settled the last open tuning fork for the current `40`-lane geometry.

What happened:

- raising `ig_push_concurrency` from `1` to `2` reintroduced burst `4xx`
- steady fell back under target
- recovery picked up `4xx` again in the first recovery bin

So the `40`-lane geometry now has a clear shape:

- `ig_push_concurrency = 1` is the only semantically clean posture so far
- any higher per-lane push concurrency pushes the source back into overload behavior

That means more per-lane parallelism is no longer the right tuning direction.

The remaining truthful option inside `Phase 0.C` is to change source-lane geometry, not source-lane aggression:

- keep the clean `ig_push_concurrency = 1` posture
- keep replay bypass
- keep the fresh runtime image
- raise lane count so each lane carries less per-lane target load while the aggregate burst target is still `6000`

This is still a truthful proving move because it does not lower the production target; it changes only how the bounded source fleet expresses that target.

## 2026-03-10 22:32:27 +00:00
The first higher-lane geometry rerun (`phase0_20260310T221746Z`) is the best `Phase 0.C` posture so far and, importantly, it stayed clean while moving the burst proof almost all the way to closure.

What changed:

- raised lane count from `40` to `48`
- kept the fresh WSP runtime revision
- kept replay-delay bypass
- kept `ig_push_concurrency = 1`
- kept the original `0.25 s` source bucket window

What stayed green:

- steady admitted `= 3038.51 eps`
- recovery admitted `= 3019.37 eps`
- `4xx = 0`
- `5xx = 0`
- Lambda stayed clean
- no lane collapse reopened

What remains red:

- burst admitted `= 5965.50 eps`
- only blocker emitted was `BURST_THROUGHPUT_SHORTFALL:observed=5965.500:target=6000.000`

This matters because it changes the posture again. The remaining gap is now only `34.5 eps`, and it is being missed from an otherwise semantically green and operationally explainable run shape. That is close enough that the next move should stay narrow and geometric:

- do not raise per-lane push concurrency again
- do not widen the bucket window again
- keep the clean `48`-lane / `ig_push_concurrency = 1` posture as the baseline
- test the next small lane-count increment only, so the platform sees slightly less per-lane pressure while the aggregate target remains unchanged

If that closes burst without reopening `4xx` or `5xx`, `Phase 0.C` closes. If it misses again, then the burst gate itself is still cleanly attributable and the remaining question becomes whether another equally narrow geometry increment is needed.

## 2026-03-10 22:47:37 +00:00
The next narrow geometry step (`phase0_20260310T223332Z`) closed the open `Phase 0.C` burst defect without reopening any of the earlier overload or semantic failures.

What changed:

- raised lane count from `48` to `50`
- kept the fresh WSP runtime revision (`fraud-platform-dev-full-wsp-ephemeral:61`)
- kept replay-delay bypass
- kept `ig_push_concurrency = 1`
- kept the original `0.25 s` source bucket window

What the run proved:

- steady admitted `= 3025.30 eps`
- burst admitted `= 6019.50 eps`
- recovery admitted `= 3019.21 eps`
- `4xx = 0`
- `5xx = 0`
- Lambda `Errors = 0`
- Lambda `Throttles = 0`
- DLQ delta `= 0`
- recovery returned to sustained green immediately (`0 s`)
- dispatcher stayed green with no lane-level blockers

This is the first bounded `Phase 0.C` run that is fully green on the truthful APIGW access-log gate while still preserving the production target and the semantically clean source posture.

That means the `Phase 0` picture has now changed materially:

- `Phase 0.B` is green on the truthful steady-state proof boundary
- `Phase 0.C` is green on steady, burst, and recovery
- the cost-corrected hot path remains intact
- the active external ingress boundary is explainable, attributable, and auditable on AWS-real telemetry

The only remaining work inside `Phase 0` is documentary rather than diagnostic:

- record the reaffirmation decision in the phase doc
- refresh the readiness graphs so they stop showing an open `Phase 0.C` blocker
- commit and push the current state so the working-platform base is visible remotely

Judgment:

- `Control + Ingress` is now truthfully reaffirmed as the working-platform base under the proving method in force on `2026-03-10`
- `Phase 0` can be closed once the authority docs and graphs reflect that green verdict explicitly

## 2026-03-10 22:49:51 +00:00
The follow-through work is now done as well, so `Phase 0` is not only green in the run folder but green in the repo authority and reflection surfaces.

Completed after the decisive `phase0_20260310T223332Z` run:

- updated the `Phase 0` authority doc to mark `Phase 0.D` green and `Phase 0` closed
- moved the plan's immediate next action from `Phase 0` to `Phase 1 - RTDL plane readiness`
- refreshed the production-ready network graph, production-ready resource graph, and Control + Ingress readiness-delta graph so they no longer show an open burst blocker
- re-rendered all three readiness PNGs from the updated Mermaid sources

That closes the last stale state mismatch between:

- the live bounded evidence under `runs/`
- the implementation reasoning trail
- the phase authority doc
- the reflected readiness graphs

`Phase 0` is now closed green in a way that is inspectable remotely, not only recoverable from a local run folder.

## 2026-03-10 22:49:51 +00:00 - Phase 1 opened
With `Phase 0` closed and pushed, the next move was to open `Phase 1` properly instead of drifting straight into ad hoc RTDL checks.

The first thing I needed from the live platform was not a bounded proof run. It was runtime boundary truth:

- what the active RTDL runtime actually is,
- whether it is pinned to the current run scope,
- and whether it is observable enough to support a truthful bounded proof.

Live runtime truth on AWS:

- EKS cluster `fraud-platform-dev-full`
- namespace `fraud-platform-rtdl`
- active deployments:
  - `fp-pr3-csfb`
  - `fp-pr3-ieg`
  - `fp-pr3-ofp`
  - `fp-pr3-dl`
  - `fp-pr3-df`
  - `fp-pr3-al`
  - `fp-pr3-dla`
  - `fp-pr3-archive-writer`
- all eight are `1/1` available with no recent restarts
- all eight are pinned to the same runtime image digest `sha256:687fd3033f9c54df6e9289cff8145f6638206c64c387937dcb8b2da5326f9feb`

The first hard blocker appeared immediately:

- secret `fp-pr3-runtime-secrets` is still pinned to `platform_20260309T164209Z`
- `ACTIVE_PLATFORM_RUN_ID`, `CSFB_REQUIRED_PLATFORM_RUN_ID`, `IEG_REQUIRED_PLATFORM_RUN_ID`, `OFP_REQUIRED_PLATFORM_RUN_ID`, and `DF_REQUIRED_PLATFORM_RUN_ID` are all still that same old run id
- deployment labels such as `fp-pr3-df` still carry `fp.platform_run_id=platform_20260309T164209Z`

This means `Phase 1` is not execution-ready yet. Any bounded RTDL run started before repinning would be partly blind because the plane would still be scoped to yesterday's run.

The second finding is that process health also cannot be trusted at face value:

- `fp-pr3-csfb` logs show repeated Kafka consumer socket disconnect / reconnect churn
- `fp-pr3-df` shows the same consumer churn plus an internal publisher SASL re-authentication principal-change failure

So the RTDL opening posture is now explicit:

- first repin the plane through the intended materialization path
- then verify rollout and secret adoption
- then pin the richer `Phase 1` telemetry set
- only after that run the first bounded RTDL proof

I created `platform.production_readiness.phase1.md` to keep that reasoning from collapsing back into the generic implementation note.
