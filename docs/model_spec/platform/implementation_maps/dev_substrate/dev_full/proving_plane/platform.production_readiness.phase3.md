# Phase 3 - Case + Label Plane Readiness

## Goal
The goal of `Phase 3` is to prove that the Case + Label plane can turn correct RTDL decision truth into authoritative, append-only, reconstructable case and label truth on the live AWS runtime path.

This phase does not close because the workers exist. It closes only when case intent, case timeline truth, and label truth are observable, semantically trustworthy, and production-worthy on top of the promoted `Control + Ingress + RTDL` base.

## What must be true for Phase 3 to close
`Phase 3` closes only when all of the following are true:

1. the live Case + Label runtime boundary is explicitly pinned and current-run-correct,
2. the semantic seam from RTDL decision truth into CaseTrigger, Case Management, and Label Store is materially healthy for the active run,
3. the telemetry set can distinguish inactivity, stale scope, duplicate creation, append corruption, silent overwrite, and future-label leakage,
4. bounded Case + Label proof shows correct trigger, case-open, timeline, label-commit, and readback continuity for the active run,
5. bounded plane proof does not regress the already-green `Control + Ingress + RTDL` base,
6. the evidence is explainable, attributable, and auditable enough to promote the plane into the working platform.

## Active runtime boundary pinned
The currently accepted live Case + Label boundary is:

- EKS cluster `fraud-platform-dev-full`
- namespace `fraud-platform-case-labels`
- active deployments:
  - `fp-pr3-case-trigger`
  - `fp-pr3-case-mgmt`
  - `fp-pr3-label-store`
- promoted upstream dependency boundary:
  - `Control + Ingress + RTDL`
- current shared platform image family accepted for proof:
  - `fraud-platform-dev-full@sha256:c9846969465366dd1b97cad43b675e72db98ea4b7e46b7a7790c56f9860d320a`

## Semantic references pinned for this phase
These references are for semantic understanding only and do not change the Data Engine black-box rule:

- `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
  - authoritative truth products:
    - `s4_event_labels_6B`
    - `s4_flow_truth_labels_6B`
    - `s4_flow_bank_view_6B`
    - `s4_case_timeline_6B`
  - binding constraints:
    - truth products are offline truth and not live RTDL features
    - `s4_case_timeline_6B` is case-centric and authoritative for case-truth expectations
- `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
  - preserve event-label parity with `s3_event_stream_with_fraud_6B`
  - preserve deterministic `s4_case_timeline_6B` cardinality and schema
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
  - labels and case timelines remain authoritative S4 outputs
  - S5 validates coverage and consistency but does not rewrite business truth

## Derived subphases

### Phase 3.A - Runtime boundary and telemetry truth
Goal:
- ensure the active Case + Label lane is current-run-correct and observable enough that later bounded proof is not blind.

This subphase requires:

1. rollout verification across all Case + Label workloads,
2. run-scope continuity from RTDL decision truth into case/label workers,
3. live telemetry for trigger intake, case-open, timeline, and label-commit continuity,
4. fail-fast visibility on duplicate or overwrite defects.

Status:
- in progress

### Phase 3.B - Case + Label correctness slice
Goal:
- prove the plane itself stays semantically trustworthy on the promoted upstream network.

This subphase requires:

1. correct escalation from decision truth to case intent,
2. duplicate case creation suppressed,
3. append-only case timeline continuity,
4. label commit latency, idempotency, and conflict visibility,
5. no future-label leakage or silent overwrite.

Status:
- not started

### Phase 3.C - Promotion judgment
Goal:
- decide whether Case + Label and its immediate introduced paths can be added to the working platform.

This subphase requires:

1. bounded Case + Label correctness green,
2. truthful attribution of upstream and plane-local effects,
3. no regression of the promoted `Control + Ingress + RTDL` base,
4. truthful readiness graphs and implementation trail.

Status:
- not started

## Current telemetry set for active Phase 3.A work

### Live logs
- `fp-pr3-case-trigger`
- `fp-pr3-case-mgmt`
- `fp-pr3-label-store`
- immediate RTDL publishers feeding case-worthy decisions

### Live counters and health checks
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
  - `label_status_accepted`
  - `label_status_rejected`
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
- RTDL -> CaseTrigger event movement
- case timeline writes and readback
- label-store commits and readback
- run-scope continuity into case and label outputs

### Fail-fast signals
- workers healthy but zero current-run participation
- duplicate case creation for current-run case-worthy traffic
- missing case timeline writes for valid case-worthy decisions
- conflicting labels being silently overwritten
- current-run labels or cases written under stale scope

## Current planning posture
`Phase 3` is entering at the correct boundary:

- upstream `Control + Ingress + RTDL` is now promoted and trustworthy enough to serve as the decision source
- the Case + Label workers are materially live on the accepted image family
- the next honest spend is not a broad platform run; it is a bounded Case + Label correctness slice with rich live telemetry

## Current impact metrics

### Phase-entry runtime truth
- namespace `fraud-platform-case-labels` deployments:
  - `fp-pr3-case-trigger`
  - `fp-pr3-case-mgmt`
  - `fp-pr3-label-store`
- rollout posture at phase entry:
  - all `1/1` available
  - all pods `Running`
  - all on the promoted image family

### Phase-entry semantic truth
- authoritative truth products remain:
  - `s4_event_labels_6B`
  - `s4_flow_truth_labels_6B`
  - `s4_flow_bank_view_6B`
  - `s4_case_timeline_6B`
- accepted semantic expectations at phase entry:
  - event-label parity with the fraud event stream must hold
  - case timeline truth must remain append-only and reconstructable
  - labels must be authoritative, idempotent, and conflict-visible
  - no future-label leakage is acceptable

### Phase-entry live telemetry truth from the promoted RTDL closure scope
- source scope:
  - `platform_run_id = platform_20260311T092709Z`
  - `scenario_run_id = 61947dc98a734b8093fe938cc562b683`
- CaseTrigger:
  - `triggers_seen = 1661`
  - `duplicates = 0`
  - `quarantine = 0`
  - `publish_ambiguous = 0`
- Case Management:
  - `case_triggers = 1292`
  - `cases_created = 1292`
  - `timeline_events = 3876`
  - `timeline_events_appended = 3876`
  - `labels_accepted = 1292`
  - `labels_rejected = 0`
- Label Store:
  - `accepted = 1440`
  - `pending = 0`
  - `rejected = 0`
  - `duplicate = 0`
  - `dedupe_tuple_collision = 0`
  - `payload_hash_mismatch = 0`

## Phase 3 closure rule
`Phase 3` closes only when:

1. the Case + Label boundary is current-run-correct and observably healthy enough for truthful proof,
2. the RTDL -> CaseTrigger -> Case Management -> Label Store seam is green on the accepted image family,
3. the bounded Case + Label correctness slice is green,
4. append-only case and label truth is reconstructable and auditable,
5. the plane does not regress the already-green `Control + Ingress + RTDL` base,
6. notes, logbook, and readiness graphs all tell the same truthful story.

If any one of those is false, `Phase 3` remains open.
