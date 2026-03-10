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
