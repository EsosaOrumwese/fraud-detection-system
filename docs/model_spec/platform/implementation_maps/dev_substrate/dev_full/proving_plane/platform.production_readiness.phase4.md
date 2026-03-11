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
`Phase 4` is entering on a materially better boundary than the earlier `PR3-S4` bundle:

- `Control + Ingress + RTDL + Case + Label` is now a promoted working-platform base
- the narrow Phase 3 executor already proved the downstream seam and current image family
- the next question is no longer whether the Case + Label plane works at all
- the next question is whether the enlarged network holds under the retained ingress envelope with the downstream operational-review truth path attached

Accepted execution path:

- keep the promoted runtime/image family pinned
- derive the coupled validation slice from the Phase 3 bounded runner rather than replaying the older broad `PR3-S4` bundle
- preserve the retained upstream envelope
- add coupled timing and starvation evidence rather than collapsing back to plane-only metrics
- keep the bounded burst shape aligned with the last accepted coupled-network proof unless evidence shows that shape itself is invalid

Current coupled-envelope repin:

- the first fresh full Phase 4 rerun proved that the inherited `30 s` burst and higher inline push fanout are the wrong proving shape for this coupled boundary
- that shape produced API-edge `429` during burst and early recovery while steady, downstream participation, and coupled timing all stayed green
- the accepted repin is to reuse the already-proven coupled burst posture from the promoted RTDL closure:
  - short bounded burst segment (`2 s`)
  - retained `6000 burst eps` target
  - initial narrow fanout correction tested with `ig_push_concurrency = 1`
- the short-burst rerun removed the `429` burst defect completely, but that fanout reduction overcorrected the first steady window while later steady/recovery minutes returned to the retained envelope
- the current narrow follow-up is:
  - keep `burst_seconds = 2`
  - keep `ig_push_concurrency = 2` for the scored window
  - treat the remaining red as a transition-shaping defect rather than a broad coupled-network regression
  - expose and tune the burst-token seeding controls on the same Phase 4 runner
  - extend the scored-activation settle slightly so the scored steady slice is not polluted by activation residue
- the latest rerun proved that simply restoring `ig_push_concurrency = 2` is not enough:
  - steady came back only slightly red at `2979.367 eps`
  - steady `p99` rose to `722.864 ms`
  - burst/recovery carried API-edge `429` again (`872` burst, `982` early recovery)
  - downstream Case + Label participation and coupled timing still stayed green
- this still does not lower the target; it is a narrow driver correction so the enlarged network is judged on a truthful coupled burst boundary without artificially starving the steady slice or overdriving the edge transition

Candidate proving path now pinned:

- existing bounded runner base: `scripts/dev_substrate/phase3_case_label_readiness.py`
- existing runtime snapshot primitive: `scripts/dev_substrate/pr3_runtime_surface_snapshot.py`
- existing WSP replay dispatcher: `scripts/dev_substrate/pr3_wsp_replay_dispatch.py`
- next narrow implementation task:
  - introduce a dedicated `Phase 4` coupled runner and rollup so steady / burst / recovery plus coupled timing can be scored directly without mixing in later learning or ops/governance surfaces

## Current impact metrics entering Phase 4

### Promoted network baseline
- current working platform:
  - `Control + Ingress + RTDL + Case + Label`
- retained envelope:
  - `3000 steady eps`
  - `6000 burst eps`

### Most recent accepted closure scope feeding this phase
- source scope:
  - `execution_id = phase3_case_label_20260311T142813Z`
  - `platform_run_id = platform_20260311T142813Z`
  - `scenario_run_id = 4156588de0c1c3555bd56e0e273176ce`
- scored ingress slice:
  - `observed_admitted_eps = 3046.783`
  - `admitted_request_count = 182807`
  - `4xx = 0`
  - `5xx = 0`
  - `latency_p95_ms = 48`
  - `latency_p99_ms = 55`
- coupled downstream participation from the same accepted scope:
  - `case_trigger_triggers_seen_delta = 2276`
  - `case_trigger_published_delta = 2276`
  - `case_mgmt_cases_created_delta = 335`
  - `case_mgmt_timeline_events_appended_delta = 1005`
  - `label_store_accepted_delta = 933`
  - `label_store_timeline_rows_delta = 933`
- integrity posture from that source scope:
  - all tracked quarantine / ambiguity / duplicate / mismatch / pending deltas stayed `0`

## Phase 4 closure rule
`Phase 4` closes only when:

1. the enlarged runtime boundary is current-run-correct and observably healthy enough for truthful coupled proof,
2. the retained ingress envelope holds through steady, burst, and recovery on the enlarged network,
3. RTDL and Case + Label remain materially participating on the same active run scope,
4. decision-to-case and case-to-label timing remain attributable and acceptable,
5. the enlarged network does not regress already-promoted behavior,
6. notes, logbook, plan state, and readiness graphs all tell the same truthful story.

If any one of those is false, `Phase 4` remains open.
