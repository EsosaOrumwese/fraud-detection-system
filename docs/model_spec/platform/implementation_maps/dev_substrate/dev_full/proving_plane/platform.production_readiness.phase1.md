# Phase 1 - RTDL Plane Readiness

## Goal
The goal of `Phase 1` is to prove that the RTDL plane can turn admitted traffic from the now-confirmed `Control + Ingress` base into correct, timely, explainable, auditable runtime decision truth on the live AWS runtime path.

This phase is not asking whether the RTDL pods exist. It is asking whether the live RTDL plane is actually execution-ready, run-scope-correct, observable enough to debug honestly, and semantically trustworthy under a bounded production-shaped run.

## What must be true for Phase 1 to close
`Phase 1` only closes when all of the following are true:

1. the live RTDL runtime boundary is the intended one and is explicitly pinned,
2. every RTDL worker materially adopts the current run scope rather than an old one,
3. the plane has a telemetry set rich enough to distinguish inactivity, lag, stale scope, dependency failure, semantic failure, and append/audit failure,
4. bounded RTDL proof shows correct context, feature, decision, action, audit, and archive participation for the active run,
5. replay / duplicate / restart posture remains explainable rather than silently corrupting RTDL truth.

## Active runtime boundary pinned on 2026-03-10
The live RTDL runtime path currently observed is:

- EKS cluster `fraud-platform-dev-full`
- namespace `fraud-platform-rtdl`
- service accounts:
  - `rtdl`
  - `decision-lane`
- active deployments:
  - `fp-pr3-csfb`
  - `fp-pr3-ieg`
  - `fp-pr3-ofp`
  - `fp-pr3-dl`
  - `fp-pr3-df`
  - `fp-pr3-al`
  - `fp-pr3-dla`
  - `fp-pr3-archive-writer`
- all eight deployments currently at `1/1` available
- all eight deployments currently pinned to image digest `sha256:687fd3033f9c54df6e9289cff8145f6638206c64c387937dcb8b2da5326f9feb`

The retained Managed Flink RTDL surface remains out of the active proof path for this phase unless the runtime is explicitly repinned.

## First hard blocker discovered before any bounded Phase 1 run
`Phase 1` is not execution-ready yet because the entire RTDL lane is still pinned to the prior runtime scope:

- Kubernetes secret `fp-pr3-runtime-secrets` creation time: `2026-03-09T01:46:02Z`
- `PLATFORM_RUN_ID = platform_20260309T164209Z`
- `ACTIVE_PLATFORM_RUN_ID = platform_20260309T164209Z`
- `CSFB_REQUIRED_PLATFORM_RUN_ID = platform_20260309T164209Z`
- `IEG_REQUIRED_PLATFORM_RUN_ID = platform_20260309T164209Z`
- `OFP_REQUIRED_PLATFORM_RUN_ID = platform_20260309T164209Z`
- `DF_REQUIRED_PLATFORM_RUN_ID = platform_20260309T164209Z`

The deployment labels confirm the same stale posture, for example `fp-pr3-df` still carries:

- `fp.platform_run_id = platform_20260309T164209Z`

This is a real blocker, not a cosmetic mismatch. Under the proving method now in force, a bounded RTDL run cannot be trusted while the active plane is still scoped to an old run id.

## Telemetry needed before the first bounded RTDL proof
The starting telemetry set for `Phase 1` must answer four questions live:

1. are the RTDL workers participating for the current run?
2. are the right topics moving?
3. are the right stores being written?
4. are they doing so semantically or merely staying process-alive?

Initial live surfaces to pin:

- logs:
  - `fp-pr3-csfb`
  - `fp-pr3-ieg`
  - `fp-pr3-ofp`
  - `fp-pr3-dl`
  - `fp-pr3-df`
  - `fp-pr3-al`
  - `fp-pr3-dla`
  - `fp-pr3-archive-writer`
- control-plane posture:
  - deployment rollout status
  - pod restart counts
  - pod image digests
  - deployment labels and secret-backed run pins
- bus / storage boundary checks:
  - active run id in secret and deployment labels
  - MSK broker reachability from workers
  - Aurora DSNs for CSFB / IEG / OFP / DF / DLA / archive
  - DLA and archive evidence writes for the active run

## First live runtime findings
The first log samples already show that "pods are running" is not an acceptable health proxy:

- `fp-pr3-csfb` is showing repeated Kafka consumer socket disconnects and reconnects
- `fp-pr3-df` is showing the same consumer disconnect pattern
- `fp-pr3-df` also emitted a Kafka producer SASL re-authentication principal-change failure on the internal publisher path

These do not yet prove the RTDL plane is broken for `Phase 1`, but they do prove the plane needs richer live counters and fail-fast checks before any bounded semantic proof.

## Immediate Phase 1 posture
The first work inside `Phase 1` is therefore not a proof run. It is execution-readiness hardening:

1. repin RTDL to a fresh current run scope through the intended materialization path,
2. verify rollout and label/secret adoption on every RTDL workload,
3. define the minimal live telemetry pack for run participation, lag/checkpoint health, and decision/audit/archive outputs,
4. only then run the first bounded RTDL plane-readiness proof.

## Current-run repin completed on 2026-03-10
The first blocker is now closed through the intended runtime materialization path rather than ad hoc cluster edits.

Materialization command used:

- `scripts/dev_substrate/pr3_rtdl_materialize.py`
- `pr3_execution_id = phase1_rtdl_materialize_20260310T225349Z`
- `platform_run_id = platform_20260310T225349Z`
- `scenario_run_id = 80173048a5f341a0a5893aa11b23aaca`

Materialization result:

- `overall_pass = true`
- no blockers
- RTDL deployments rolled out successfully
- case/label deployments were also refreshed because the materializer writes both namespaces
- the stale registry MSK bootstrap was overridden with the restored live broker published through the runtime materialization path

Verification after rollout:

- `PLATFORM_RUN_ID = platform_20260310T225349Z`
- `ACTIVE_PLATFORM_RUN_ID = platform_20260310T225349Z`
- `ACTIVE_SCENARIO_RUN_ID = 80173048a5f341a0a5893aa11b23aaca`
- `CSFB_REQUIRED_PLATFORM_RUN_ID = platform_20260310T225349Z`
- `IEG_REQUIRED_PLATFORM_RUN_ID = platform_20260310T225349Z`
- `OFP_REQUIRED_PLATFORM_RUN_ID = platform_20260310T225349Z`
- `DF_REQUIRED_PLATFORM_RUN_ID = platform_20260310T225349Z`
- deployment labels now also carry `fp.platform_run_id=platform_20260310T225349Z`

So the stale-scope blocker that initially made `Phase 1` non-executable is now closed.

## First bounded RTDL participation probe
After the repin, I did not jump straight into an expensive semantic proof. I first ran the cheapest bounded probe that could answer the question "is the live RTDL lane materially participating for the current run?"

Probe shape:

- execution id `phase1_rtdl_probe_20260310T230000Z`
- `duration_seconds = 120`
- `lane_count = 4`
- `target_request_rate_eps = 100`
- `stream_speedup = 51.2`
- truthful current ingress boundary pinned to the live execute-api endpoint
- final threshold check intentionally skipped because this probe was for RTDL participation, not ingress certification

Probe result:

- dispatcher verdict `= REMOTE_WSP_WINDOW_READY`
- no blockers
- exact APIGW access-log window admitted `11334` requests over `120 s` = `94.45 eps`
- aligned APIGW bins hit `100 eps`
- `4xx = 0`
- `5xx = 0`

The important RTDL finding is not the ingress count. It is that the current-run plane actually participated:

- `fp-pr3-csfb` and `fp-pr3-df` log identities now include `platform_20260310T225349Z`
- `fp-pr3-df` exported current-run decision metrics:
  - `decisions_total = 702`
  - `publish_admit_total = 702`
  - `degrade_total = 557`
  - `fail_closed_total = 0`
- current-run RTDL artifacts exist in pod-local `runs/fraud-platform/platform_20260310T225349Z/...` trees for:
  - `identity_entity_graph`
  - `online_feature_plane`
  - `decision_fabric`
  - `degrade_ladder`

This means the repin is not merely cosmetic. The active RTDL workers are now processing and writing evidence for the fresh run.

## What the first telemetry pass actually exposed
The first bounded probe did not reveal a dead RTDL plane. It revealed that the remaining blocker has changed shape.

`IEG` live shared status:

- `mutating_applied = 6922`
- `events_seen = 6922`
- `checkpoint_age_seconds = 0.080539`
- `apply_failure_count = 0`
- but pod health artifact still reports:
  - `health_state = RED`
  - `health_reasons = ["WATERMARK_TOO_OLD"]`

`OFP` live shared status later in the same run:

- `events_applied = 5369`
- `events_seen = 5369`
- `missing_features = 0`
- `snapshot_failures = 0`
- `checkpoint_age_seconds = 291.313837`
- pod health artifact reports:
  - `health_state = RED`
  - `health_reasons = ["WATERMARK_TOO_OLD"]`

`DL` posture evolution explains the real sequence:

- remained `NORMAL` with all required signals `OK` through the active participation window
- first fail-closed transition did not happen until `2026-03-10T23:05:27.668100+00:00`
- that first transition was caused by `eb_consumer_lag = ERROR`
- `ofp_health` only turned `ERROR` later once the OFP shared checkpoint aged out as well

That matters because it narrows the current blocker materially:

1. the active run scope is correct,
2. the RTDL workers did participate,
3. the first fail-closed transition happened after the short bounded pulse went idle and shared checkpoint freshness exceeded the DL required max age,
4. the projector pod health artifacts are still untruthful for historical replay traffic because they treat old event-time watermark as hard red even while the run is actively processing and checkpoint freshness is good.

So the current `Phase 1` blocker is no longer "RTDL may still be pinned wrong" and not yet "RTDL cannot make decisions." The blocker is:

- active-window proof and post-window idle are being conflated inside the current health story,
- and at least the projector health artifacts are not yet truthful enough for bounded historical replay proof.

## Immediate next posture
The next `Phase 1` work should therefore stay narrow:

1. harden RTDL operator truth so `IEG` / `OFP` health surfaces do not report false red during active bounded replay,
2. keep the bounded proof window focused on active participation rather than treating post-pulse idle lag as if it were an active-run semantic failure,
3. only after that run the next bounded RTDL plane proof for context -> feature -> decision -> audit / archive continuity.

## First accepted Phase 1 telemetry correction
The first accepted code correction inside `Phase 1` is now local and validated:

- `src/fraud_detection/identity_entity_graph/query.py`
- `tests/services/identity_entity_graph/test_query_surface.py`

Correction made:

- `IEG` health now emits `WATERMARK_REPLAY_ADVISORY` and stays `AMBER` rather than falsely going `RED` when:
  - the watermark is historically old,
  - the checkpoint is still fresh,
  - apply failures are zero,
  - and current-run mutation / event processing is active

Targeted local validation:

- `python -m py_compile src/fraud_detection/identity_entity_graph/query.py`
- `.venv\Scripts\python.exe -m pytest tests/services/identity_entity_graph/test_query_surface.py -q`
- result: `5 passed`

This is intentionally narrow. It does not settle the later `DL` idle-lag transition after the short probe. It only removes one misleading health surface so the next AWS-bound RTDL proof can be read more truthfully.

## Live validation after the health correction rollout
I did not leave the `IEG` correction local-only. I built and pushed a fresh shared platform image and rolled the two RTDL workloads that materially needed it:

- image tag `phase1-rtdl-health-20260310T231501Z`
- image digest `sha256:7ccddd2ab23361de6490d38ca821b52026cd87de7ea08137c42979454cf3c97a`
- rolled deployments:
  - `fp-pr3-ieg`
  - `fp-pr3-dl`

Then I reran the same cheap bounded RTDL participation probe:

- execution id `phase1_rtdl_probe_20260310T231740Z`
- `120 s`
- `100 eps`
- `4` lanes
- dispatcher verdict `= REMOTE_WSP_WINDOW_READY`
- `4xx = 0`
- `5xx = 0`

The ingress exact-window count came back lower than the aligned APIGW bins on this run (`88.825 eps` exact vs `100 eps` aligned), but this probe was not used as an ingress gate and the RTDL-side evidence was the more important truth surface.

What changed materially on the RTDL side:

`IEG` now reports truthful replay advisory rather than false red during active processing:

- `mutating_applied = 18253`
- `events_seen = 18253`
- `checkpoint_age_seconds = 0.091156`
- `apply_failure_count = 0`
- `health_state = AMBER`
- `health_reasons = ["WATERMARK_REPLAY_ADVISORY"]`

`OFP` also shows truthful active-window posture:

- `events_applied = 5422`
- `events_seen = 5422`
- `missing_features = 0`
- `snapshot_failures = 0`
- `checkpoint_age_seconds = 76.50025`
- `health_state = AMBER`
- `health_reasons = ["WATERMARK_REPLAY_ADVISORY"]`

`DL` recovered to a truthful green active-window decision posture:

- `decision_mode = NORMAL`
- `health_state = GREEN`
- all required signals `OK`
- mode-change event at `2026-03-10T23:21:51.556161+00:00`

`DF`, `DLA`, and archive continuity are now all visible on the same run:

- `DF` metrics:
  - `decisions_total = 5422`
  - `publish_admit_total = 5422`
  - `fail_closed_total = 0`
- `DLA` metrics:
  - `accepted_total = 8182`
  - `append_success_total = 8182`
  - `append_failure_total = 0`
  - `replay_divergence_total = 0`
- archive writer metrics:
  - `archived_total = 17417`
  - `duplicate_total = 0`
  - `payload_mismatch_total = 0`
  - `write_error_total = 0`
- archive reconciliation now contains concrete S3 archive refs under:
  - `s3://fraud-platform-dev-full-object-store/platform_20260310T225349Z/archive/events/...`

This materially changes the open Phase 1 question.

The remaining blocker is no longer:

- stale run scope,
- basic RTDL participation ambiguity,
- or false-red projector health during bounded replay.

The remaining blocker is:

- a richer bounded production-shaped RTDL proof is still needed before the plane can be called ready under the full standard.

That next proof should focus on the now-trustworthy chain:

- context participation,
- feature participation,
- decision production,
- audit append continuity,
- archive continuity,
- and whether those remain explainable at production-shaped ingress pressure rather than only on the cheap `100 eps` participation probe.

## First fresh richer bounded proof and the blocker it actually revealed
I did the first richer bounded RTDL proof on a fresh run scope once the cheap probe had already shown that current-run participation and continuity were real.

Fresh materialization:

- execution `phase1_rtdl_materialize_20260310T232635Z`
- `platform_run_id = platform_20260310T232635Z`
- `scenario_run_id = 71a81c0235674d51847b0fa1ee4f262c`

Fresh richer bounded proof:

- execution `phase1_rtdl_bounded_20260310T233050Z`
- `120 s`
- `50` lanes
- target `3000 eps`
- exact APIGW access-log window admitted `293479` requests over `120 s` = `2445.658 eps`
- `4xx = 0`
- `5xx = 0`

That run did materially drive RTDL. Pulling the live pod-local artifacts directly from the namespace showed:

- `IEG` current-run artifacts and reconciliation present
- `OFP` current-run artifacts present with `events_applied = 38311`
- `DF` metrics present with `decisions_total = 3106`, `publish_admit_total = 3106`, `fail_closed_total = 0`
- `DLA` metrics present with `append_success_total = 10543`, `append_failure_total = 0`, `replay_divergence_total = 0`
- archive writer `GREEN` with concrete archive refs under `platform_20260310T232635Z/archive/events/...`

So the richer run did not show RTDL non-participation.

The blocker it actually revealed was that the plane had been silently redeployed on an older shared image during fresh materialization:

- live RTDL deployments were running `fraud-platform-dev-full@sha256:cde0404e6042...`
- that older digest replaced the earlier truthful health-fix digest `sha256:7ccddd2ab233...`
- as a result, projector pod-local health regressed to false hard-red `WATERMARK_TOO_OLD` again even while the run was actively being processed

That narrowed the real blocker from "run the richer proof" to "stop the materializer from silently undoing live RTDL hardening between runs".

Accepted remediation:

- patch `pr3_rtdl_materialize.py` so it prefers:
  1. explicit `--image-uri`
  2. currently deployed RTDL image
  3. ECS WSP task image only as fallback

I will not treat the first richer bounded proof as a closure candidate because the plane-under-test changed under the run setup itself. The richer RTDL proof must be rerun on a fresh scope after that repin defect is removed.

## Repinned rerun and the new actual blocker
I removed the materializer image-regression defect from the next richer run by rematerializing RTDL on a fresh scope with the fixed digest passed explicitly:

- materialization execution `phase1_rtdl_materialize_20260311T000005Z`
- `platform_run_id = platform_20260311T000006Z`
- `scenario_run_id = e72b368ddba3b04545b30417e65fcffd`
- explicit image `fraud-platform-dev-full@sha256:7ccddd2ab23361de6490d38ca821b52026cd87de7ea08137c42979454cf3c97a`

The live deployment templates then confirmed the active RTDL workloads were actually pinned to that digest, not the old `phase0c` image.

With that fixed, I reran the same richer bounded proof shape:

- execution `phase1_rtdl_bounded_20260311T000430Z`
- exact APIGW access-log window admitted `292831` requests over `120 s` = `2440.258 eps`
- `4xx = 0`
- `5xx = 0`

That rerun is important because it closed one blocker and surfaced the next one more honestly.

What is now closed:

- `IEG` stayed on truthful replay advisory under the repinned run:
  - `health_state = AMBER`
  - `health_reasons = ["WATERMARK_REPLAY_ADVISORY"]`
  - `checkpoint_age_seconds = 0.077472`
  - `mutating_applied = 3781`
  - `apply_failure_count = 0`

So the materializer rollback defect is no longer the active blocker.

What is now open:

- `OFP` remained `RED` on the same repinned richer run:
  - `health_reasons = ["WATERMARK_TOO_OLD", "MISSING_FEATURES_RED"]`
  - `events_applied = 5208`
  - `missing_features = 152`
  - `missing_feature_rate = 0.029185867895545316`
  - `snapshot_failures = 0`
  - `stale_graph_version = 0`

That makes this a different class of blocker from the earlier repin defect. This time the richer run is revealing a real feature-plane problem under load:

- RTDL remained materially alive,
- `DL` stayed `NORMAL`,
- `DLA` and archive continuity remained visible,
- but `OFP` is serving enough missing features to trip a real red posture.

Before rerunning again, I accepted one more telemetry correction because the remaining blindspot is now specific:

- the current OFP health surface tells me the count,
- but not which feature keys or groups are missing.

So I patched `src/fraud_detection/online_feature_plane/serve.py` to log sampled missing feature keys and groups whenever the service returns missing-feature posture, and I added targeted coverage in `tests/services/online_feature_plane/test_phase5_serve.py`.

That telemetry patch should be deployed before the next richer rerun so the next `Phase 1` investigation answers the real question:

- which exact OFP keys/groups are going missing under the bounded production-shaped RTDL proof,
- and whether the fix belongs in OFP snapshot materialization, DF request shape, or feature-definition compatibility.

## OFP telemetry deployment posture before the next rerun
I do not want the next richer bounded run to answer two questions at once. The open semantic blocker is already narrow:

- `OFP` goes `RED`
- `missing_feature_rate` is materially non-zero
- the rest of RTDL is alive enough that the plane is telling me something real

So the next step is not another broad experiment. It is to put the already-built OFP telemetry patch onto the live `fp-pr3-ofp` deployment and keep the rest of the richer proof shape unchanged.

The reason for rolling only `fp-pr3-ofp` is attribution:

- if I change the whole RTDL lane again, I reopen image-drift and coupled-change ambiguity
- if I change only OFP logging and keep the same richer bounded proof shape, then any new evidence about missing features is directly attributable to the OFP telemetry patch rather than a broader runtime repin

The new image that contains the OFP missing-feature logging patch is:

- `fraud-platform-dev-full@sha256:ea644d7726158c7a13d87a387731daca706029f35011ce943c8196f41ab2aebe`

The next live sequence is therefore:

1. roll `fp-pr3-ofp` only to `sha256:ea644d772615...`
2. verify rollout completion and live image truth in the namespace
3. generate a fresh `platform_run_id` / `scenario_run_id`
4. rerun the richer bounded RTDL proof on the same production-shaped control
5. read the new OFP warning logs and current-run health artifacts for exact missing feature keys/groups

That is the current dynamic posture:

- do not rerun blind,
- do not widen the change surface,
- improve visibility exactly where the red posture still lacks attribution,
- then fix the actual semantic defect rather than the generic symptom.

The OFP rollout itself is now complete:

- deployment revision `22`
- `fp-pr3-ofp` template image = `fraud-platform-dev-full@sha256:ea644d7726158c7a13d87a387731daca706029f35011ce943c8196f41ab2aebe`

That closes the cluster-side telemetry deployment step, but it does not by itself create a valid next proof window. The active RTDL runtime identity is still pinned to the older fresh scope:

- `platform_run_id = platform_20260311T000006Z`
- `scenario_run_id = e72b368ddba3b04545b30417e65fcffd`

So the next step has to be a fresh materialization again, otherwise the next WSP replay would be mixing a new diagnostic question into an old RTDL scope. I am accepting that rematerialization because fresh scope truth matters more than keeping the deployment history cosmetically narrow.

The constraint I am preserving is different:

- the proof shape stays the same
- the only code delta carried into the fresh scope is the OFP missing-feature telemetry patch
- the next run still exists to explain the same `OFP` red posture, not to explore a new traffic shape

That fresh rerun on `platform_20260311T001956Z` removed the blindspot completely and changed the diagnosis again.

The missing-feature logs did what they were supposed to do. The repeated shape is now clear:

- OFP serves repeated missing-feature posture on concrete `event_id:*` and `flow_id:*` keys
- the posture flags are consistently `["GRAPH_VERSION_UNAVAILABLE", "MISSING_FEATURE_STATE"]`
- `missing_groups` is empty
- OFP run-scoped health still goes `RED` because `missing_feature_rate = 0.010208087946603848`

That matters because it means the red posture is not a generic feature-group-definition mismatch. `core_features` is configured on both sides. The stronger clue is the graph-version flag.

I then checked the live IEG run-scoped health on the same fresh scope and found that the graph version does exist:

- `graph_version = 43ead213380ff0053dcf8b943fab6b5bfe070a19030cc53894d55476c7cf3630`
- `health_state = AMBER`
- `health_reasons = ["WATERMARK_REPLAY_ADVISORY"]`
- `checkpoint_age_seconds = 0.195907`

So the actual defect is not "IEG has no graph version". The actual defect is an interface-shape mismatch:

- `IdentityGraphQuery.status()` was returning `graph_version` as a bare string
- DF's graph resolver only accepted a mapping
- the resolver therefore discarded the real graph version and OFP saw `GRAPH_VERSION_UNAVAILABLE`

That is a much better blocker than the earlier generic missing-feature red. It is attributable and narrow.

Accepted fix:

- patch `src/fraud_detection/identity_entity_graph/query.py` so `status()` returns structured graph-version payload for DF/OFP consumption:
  - `version_id`
  - `watermark_ts_utc`
  - `stream`
  - `computed_at_utc`
  - `basis_digest` when available
- keep the raw token as `graph_version_token` for compatibility
- add targeted coverage in `tests/services/identity_entity_graph/test_query_surface.py`

Local validation passed:

- `python -m py_compile src/fraud_detection/identity_entity_graph/query.py`
- `.venv\Scripts\python.exe -m pytest tests/services/identity_entity_graph/test_query_surface.py -q`
- `6 passed`

The next live step is to build/push this graph-version contract fix, rematerialize RTDL on a fresh scope again, and rerun the same richer bounded proof. If the `GRAPH_VERSION_UNAVAILABLE` flag disappears and OFP missing-feature red collapses with it, then this fix closes the real blocker. If not, the remaining issue will be true feature-state absence rather than graph-resolution blindness.

That build/push step is now done:

- image tag `phase1-ieg-graph-contract-20260311T003455Z`
- pushed digest `fraud-platform-dev-full@sha256:759d9ad2302b08b946f29efccd1297f60e5a1ce210c85b0631359f54c6db37eb`

So the next proof window can carry the contract fix onto a fresh scope without further local work in between.

At `2026-03-11 01:27 +00:00` I rechecked the repo/runtime boundary before spending more AWS time. The fresh RTDL scope is already materialized on the graph-contract image:

- `platform_run_id = platform_20260311T003731Z`
- `scenario_run_id = 9b54e816226249b3ac1066d57bbeda4a`
- materialization execution `phase1_rtdl_materialize_20260311T003731Z`

So the next narrow step is not another rollout or another code edit. It is the same richer bounded proof shape on this fresh scope, followed immediately by run-scoped inspection of:

- DF warning logs for `OFP missing feature state`
- OFP health and metrics for the active run id
- IEG health for the same run id
- DF reconciliation counts to see whether `GRAPH_VERSION_UNAVAILABLE` disappears or just reveals the next semantic blocker underneath

That preserves the dynamic posture correctly:

- keep the proof shape fixed
- spend on one decisive run
- use the new contract fix to answer one question cleanly before considering any further RTDL changes

The rerun on `platform_20260311T003731Z` answered that question clearly.

Fresh richer bounded proof:

- execution `phase1_rtdl_bounded_20260311T012845Z`
- exact APIGW access-log window admitted `290053` requests over `120 s` = `2417.108 eps`
- `4xx = 0`
- `5xx = 0`
- latency remained inside the ingress budget

The important part is not the admission number by itself. It is what changed underneath it.

What is now closed:

- `IEG` run-scoped health now exports structured `graph_version` payload rather than a bare token
- `GRAPH_VERSION_UNAVAILABLE` no longer appears in current DF logs
- `OFP` run-scoped health is no longer red:
  - `health_state = AMBER`
  - `health_reasons = ["WATERMARK_REPLAY_ADVISORY"]`
  - `missing_features = 0`
  - `snapshot_failures = 0`
- `DL` is green with all required signals `OK`
- `DF` is green with no fail-closed or resolver failures

So the graph-version contract defect was real, and it is now materially closed.

The next mismatch is narrower and more subtle. DF warning logs on the same run still show repeated OFP missing-feature warnings, but they are now only:

- `missing_feature_keys = ['event_id:*']`
- `missing_groups = []`
- `posture_flags = ['MISSING_FEATURE_STATE']`

Accepted interpretation for this boundary:

- OFP projector key precedence is `flow_id`, then `event_id`
- DF had been requesting both keys when `flow_id` already existed
- the remaining OFP warning noise was therefore a request-shape mismatch, not a missing graph-version or missing-feature-group defect

Ingress timing on the same run stayed healthy:

- `phase.publish_seconds p95 ~= 0.009 - 0.010 s`
- `admission_seconds p95 ~= 0.032 - 0.035 s`

So the coupled-window shortfall at that point was not attributable to slow ingress publish behavior.

Accepted remediation for that seam:

- `src/fraud_detection/decision_fabric/worker.py`
- request OFP features on `flow_id` when present
- keep `event_id` only as the fallback when `flow_id` is absent

Targeted validation for that remediation:

- `python -m py_compile src/fraud_detection/decision_fabric/worker.py`
- `.venv\Scripts\python.exe -m pytest tests/services/decision_fabric/test_worker_helpers.py -q`
- `7 passed`

Materialized deployment reference for the accepted seam fix:

- image tag `phase1-df-feature-keys-20260311T015210Z`
- pushed digest `fraud-platform-dev-full@sha256:c9846969465366dd1b97cad43b675e72db98ea4b7e46b7a7790c56f9860d320a`

## Current Phase 1 planning posture
The live notebook trail for active diagnosis and remediation is kept in `platform.production_readiness.impl_actual.md`. This phase plan holds only the current planning state, active proof boundary, and the impact metrics that decide closure.

### Closed blockers now accepted
- stale RTDL run-scope repin defect
- false `IEG` hard-red graph-version contract defect
- DF/OFP redundant feature-key mismatch
- coupled-proof control-shape drift caused by using a non-Phase-0 rate plan
- coupled-proof under-drive caused by `ig_push_concurrency = 1`
- fresh-scope ingress producer cold-path collapse caused by run-scoped Kafka publisher rebuild

### Current Phase 1.B status
`Phase 1.B` remains open.

The current closure candidate after the ingress producer patch is:

- materialization execution `phase1_rtdl_materialize_20260311T044725Z`
- closure execution `phase1_rtdl_coupled_envelope_fresh_igpush2_postfix_20260311T044725Z`
- `platform_run_id = platform_20260311T044725Z`
- `scenario_run_id = 358a836a65d7491d8cadc55a3cc7abf7`
- image `fraud-platform-dev-full@sha256:c9846969465366dd1b97cad43b675e72db98ea4b7e46b7a7790c56f9860d320a`
- calibrated `Phase 0` common rate plan retained
- `ig_push_concurrency = 2`

### Current impact metrics
- steady admitted `= 2272.589 eps`
- burst admitted `= 4886.000 eps`
- recovery admitted `= 2558.617 eps`
- steady `4xx = 129`
- `5xx = 0`
- steady `p95 = 45.85 ms`
- steady `p99 = 82.50 ms`
- dispatch blockers `= 2`
- sustained recovery green within the scored `180 s` window: `not achieved`

### Current blocker shape
The catastrophic fresh-scope ingress ambiguity is no longer the active blocker. After the shared Kafka publisher patch:

- the earlier `503` wave disappeared
- all-lane collapse disappeared
- only `2` WSP lanes still fail

The active blocker is now a narrower fresh-scope residual rejection / under-drive posture:

- `wsp_lane_00` failed on `IG_PUSH_REJECTED`
- `wsp_lane_01` failed on `IG_PUSH_REJECTED`
- both failures occur materially inside the campaign rather than at lane start
- APIGW remains semantically clean on `5xx`
- the remaining question is whether those two lane losses account for most of the throughput deficit, or whether a broader surviving-lane under-drive still exists

### Immediate next proof question
Before another closure rerun, `Phase 1.B` must answer one narrow attribution question:

- are the two residual `IG_PUSH_REJECTED` lanes the primary cause of the remaining steady / burst / recovery shortfall?

That means the next work stays bounded to:

- lane-level rejection attribution on Lambda / APIGW telemetry
- lane-progress comparison against the exact-window throughput deficit
- one narrow fix on the surface that explains the residual fresh-scope rejection

`Phase 1.B` does not close until the fresh-scope coupled envelope is repeatably green on the calibrated `Phase 0` control with RTDL materially participating and without residual ambiguous lane rejection.
