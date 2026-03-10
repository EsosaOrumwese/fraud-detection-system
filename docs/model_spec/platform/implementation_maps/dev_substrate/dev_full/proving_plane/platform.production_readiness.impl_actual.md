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
