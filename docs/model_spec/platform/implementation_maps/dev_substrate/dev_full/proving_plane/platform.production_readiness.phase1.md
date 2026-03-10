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
