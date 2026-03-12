# Phase 4 - Working Network + Case + Label Coupled Readiness

## Goal
The goal of `Phase 4` is to prove that the enlarged working network holds once `Case + Label` is attached to the already-promoted `Control + Ingress + RTDL` base.

This phase does not close because `Case + Label` is plane-ready on its own. It closes only when the full operational path from ingress through RTDL into case and label truth remains timely, attributable, duplicate-safe, and production-worthy under the retained ingress envelope.

## What must be true for Phase 4 to close
`Phase 4` closes only when all of the following are true:

1. the live coupled runtime boundary is explicitly pinned and current-run-correct,
2. the enlarged network sustains the retained ingress envelope while keeping RTDL and Case + Label materially participating,
3. decision-to-case and case-to-label timing remain within the bounded production target for the active slice,
4. no silent starvation or hidden dark downstream state exists across `RTDL -> CaseTrigger -> Case Management -> Label Store`,
5. `Case + Label` does not regress the already-promoted `Control + Ingress + RTDL` base,
6. the evidence is explainable, attributable, and auditable enough to promote the enlarged network as the new working platform.

## Active runtime boundary pinned
The currently accepted live coupled boundary is:

- API Gateway `fraud-platform-dev-full-ig-edge`, stage `v1`
- Lambda `fraud-platform-dev-full-ig-handler`
- ECS cluster `fraud-platform-dev-full-wsp-ephemeral`
- EKS cluster `fraud-platform-dev-full`
- namespace `fraud-platform-rtdl`
- namespace `fraud-platform-case-labels`
- active promoted deployments:
  - `fp-pr3-csfb`
  - `fp-pr3-ieg`
  - `fp-pr3-ofp`
  - `fp-pr3-df`
  - `fp-pr3-dl`
  - `fp-pr3-al`
  - `fp-pr3-dla`
  - `fp-pr3-archive-writer`
  - `fp-pr3-case-trigger`
  - `fp-pr3-case-mgmt`
  - `fp-pr3-label-store`
- current shared platform image family accepted for proof:
  - `fraud-platform-dev-full@sha256:c9846969465366dd1b97cad43b675e72db98ea4b7e46b7a7790c56f9860d320a`

## Derived subphases

### Phase 4.A - Coupled runtime truth and telemetry gate
Goal:
- ensure the enlarged network is observable enough that the coupled run is not blind or falsely green because downstream participation disappeared.

This subphase requires:

1. run-scope continuity from control into ingress, RTDL, and Case + Label,
2. live downstream participation visibility across RTDL and Case + Label,
3. timing visibility for `decision -> case` and `case -> label`,
4. fail-fast visibility on starvation, duplicate corruption, or RTDL regression.

Status:
- in progress

### Phase 4.B - Coupled-network validation slice
Goal:
- prove the enlarged network stays production-worthy on the retained ingress envelope once the full operational review path is attached.

This subphase requires:

1. steady, burst, and recovery segments at the retained envelope,
2. positive RTDL and Case + Label participation on the same active run scope,
3. no semantic regressions in RTDL, CaseTrigger, Case Management, or Label Store,
4. attributable timing and continuity across the coupled path.

Status:
- in progress

### Phase 4.C - Promotion judgment
Goal:
- decide whether the enlarged `Control + Ingress + RTDL + Case + Label` network is ready to be treated as the new promoted working platform.

This subphase requires:

1. bounded coupled-network validation green,
2. no regression of the already-promoted planes,
3. no hidden starvation or dark downstream state,
4. truthful notes, plan state, and readiness graphs.

Status:
- not started

## Current telemetry set for active Phase 4.A work

### Live logs
- WSP bounded replay producer
- ingress Lambda
- RTDL publishers and immediate decision path
- `fp-pr3-case-trigger`
- `fp-pr3-case-mgmt`
- `fp-pr3-label-store`

### Live counters and health checks
- ingress:
  - admitted eps
  - `4xx`
  - `5xx`
  - latency p95 / p99
- RTDL:
  - decision publication
  - fail-closed / quarantine deltas
  - append continuity
  - checkpoint and lag freshness for `csfb`, `ieg`, `ofp`
- CaseTrigger:
  - `triggers_seen`
  - `published`
  - `duplicates`
  - `quarantine`
  - `publish_ambiguous`
- Case Management:
  - `case_triggers`
  - `cases_created`
  - `timeline_events`
  - `timeline_events_appended`
  - `labels_accepted`
  - `labels_rejected`
  - `evidence_pending`
  - `evidence_unavailable`
- Label Store:
  - `accepted`
  - `pending`
  - `rejected`
  - `duplicate`
  - `dedupe_tuple_collision`
  - `payload_hash_mismatch`
  - `missing_evidence_refs`
  - `timeline_rows`
- coupled-path timing:
  - decision-to-case latency
  - case-to-label latency
  - starvation counters across RTDL -> Case + Label

### Fail-fast signals
- ingress healthy but RTDL or Case + Label dark on the active run
- RTDL healthy but CaseTrigger participation absent
- case activity present without label-store truth
- any duplicate corruption or payload mismatch delta above `0`
- RTDL latency / fail-closed posture regresses under the new coupling

## Current execution posture
`Phase 4` is now materially narrowed. The enlarged network is no longer being treated as broadly red.

Accepted execution path:

- keep the promoted runtime/image family pinned
- derive the coupled validation slice from the Phase 3 bounded runner rather than replaying the older broad `PR3-S4` bundle
- preserve the retained upstream envelope
- add coupled timing and starvation evidence rather than collapsing back to plane-only metrics
- keep remediation narrow to the currently evidenced blocker family

## Final impact metrics and closure judgment

### Accepted closure scope
- `execution_id = phase4_case_label_coupled_20260312T003302Z`
- `platform_run_id = platform_20260312T003302Z`
- `scenario_run_id = 9491946f6c82eed929797d2128ec38e8`

### Final envelope truth on the enlarged network
- steady:
  - `observed_admitted_eps = 3060.177777777778`
  - `4xx = 0`
  - `5xx = 0`
  - `latency_p95_ms = 52.8965`
  - `latency_p99_ms = 77.4241`
- burst:
  - `observed_admitted_eps = 7118.0`
  - `4xx = 0`
  - `5xx = 0`
- recovery:
  - `observed_admitted_eps = 3018.4333333333334`
  - `4xx = 0`
  - `5xx = 0`
  - `recovery_seconds_to_sustained_green = 0.0`

### Final coupled participation and timing truth
- RTDL participation: green
- CaseTrigger participation: green
- Case Management participation: green
- Label Store participation: green
- decision-to-case timing: green
  - `p95 = 0.0 s`
- case-to-label timing: green
  - `p95 = 0.17482505 s`
- Lambda errors: `0`
- Lambda throttles: `0`
- DLQ delta: `0`

### Final downstream commit posture
- refreshed post snapshot on the same run shows:
  - `case_mgmt labels_accepted = 2931`
  - `label_store accepted = 3080`
- final rerolled scorecard shows:
  - `case_mgmt_labels_accepted_delta = 2747`
  - `label_store_accepted_delta = 2782`
- integrity deltas remain `0`

### Closure judgment
- `Phase 4` is green and closed.
- The decisive ingress-edge correction was:
  - `burst_step_initial_tokens = 0.0`
- The remaining old rollup red was not accepted as a real platform defect.
  - It was a stale scoring surface that disappeared once the matured post snapshot was rerolled on the same run scope.
- The working platform is therefore now truthfully promoted as:
  - `Control + Ingress + RTDL + Case + Label`

## Handoff to Phase 5
The next unmet goal is `Phase 5 - Learning + Evolution / MLOps plane readiness`.

The accepted handoff inputs are:
- promoted working platform:
  - `Control + Ingress + RTDL + Case + Label`
- authoritative source scope for the newest coupled closure:
  - `phase4_case_label_coupled_20260312T003302Z`
- retained proving method:
  - telemetry first
  - AWS-real / managed-surface-real execution
  - bounded proof before stress
  - fix narrow and rerun narrow
