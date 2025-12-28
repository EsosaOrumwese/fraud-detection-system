# Layer-3 - Segment 6B - State Overview (S0-S5)

Segment 6B builds behaviour and labels. It gates upstream worlds, attaches arrivals to entities and sessions, synthesises baseline flows, overlays fraud/abuse campaigns, derives truth/bank-view labels plus case timelines, and seals the segment with a PASS bundle. These surfaces are the sole authority for behaviour and labels for a given world.

## Segment role at a glance
- Enforce HashGates for 1A-3B, 5A/5B, and 6A; seal what 6B may read.
- Attach arrival events to entities and group them into sessions.
- Generate baseline (all-legit) flows and events.
- Overlay fraud/abuse campaigns to produce post-overlay flows/events.
- Label flows/events (truth and bank-view) and publish case timelines; seal with `validation_bundle_6B` + `_passed.flag`.

---

## S0 - Gate & sealed inputs (RNG-free)
**Purpose & scope**  
Verify upstream `_passed.flag_*` (1A-3B, 5A, 5B, 6A) for the target `manifest_fingerprint`; seal the artefacts 6B may read.

**Preconditions & gates**  
Upstream bundles/flags must match; Layer-3 schemas/dictionary/registry present; identities `{seed, parameter_hash, manifest_fingerprint}` fixed.

**Inputs**  
Upstream gated surfaces (listed in sealed manifest): 5B `arrival_events_5B`; 6A entities/posture (`s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`, `s4_device_base_6A`, `s4_ip_base_6A`, links, fraud-role surfaces); context from Layer-1/2 as needed; 6B priors/policies (behaviour, campaigns, labelling, RNG).

**Outputs & identity**  
`s0_gate_receipt_6B` at `data/layer3/6B/s0_gate_receipt_6B/fingerprint={manifest_fingerprint}/`; `sealed_inputs_6B` at `data/layer3/6B/sealed_inputs_6B/fingerprint={manifest_fingerprint}/`.

**RNG**  
None.

**Key invariants**  
Only artefacts in `sealed_inputs_6B` may be read; sealed digest verified by S1-S5; "no PASS -> no read" enforced for all upstream gates.

**Downstream consumers**  
S1-S5 verify receipt/digest; 6B surfaces remain unreadable by downstream until `_passed.flag`.

---

## S1 - Arrival-to-entity attachment & sessionisation
**Purpose & scope**  
Attach each arrival to entities and group arrivals into sessions.

**Preconditions & gates**  
S0 PASS; `arrival_events_5B` and required 6A bases/links/fraud roles listed in sealed inputs with appropriate scopes.

**Inputs**  
`arrival_events_5B` `[seed, fingerprint, scenario_id]`; 6A bases (`party/account/instrument/device/ip`); 6A links and fraud roles; attachment/session policies.

**Outputs & identity**  
`s1_arrival_entities_6B` at `data/layer3/6B/s1_arrival_entities_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/`, one row per arrival with entity ids, `session_id`, provenance.  
`s1_session_index_6B` at `.../s1_session_index_6B/.../` with session windows and aggregates.

**RNG posture**  
Philox streams for ambiguous attachments and session boundary choices; event families such as `rng_event_entity_attach`, `rng_event_session_boundary`; budgets logged and reconciled in trace.

**Key invariants**  
Every arrival appears exactly once in `s1_arrival_entities_6B`; every `session_id` appears in `s1_session_index_6B`; no new entities created; FKs to 6A hold.

**Downstream consumers**  
S2-S4 consume attachments/sessions; S5 validates coverage and RNG.

---

## S2 - Baseline transactional flows (RNG)
**Purpose & scope**  
Generate baseline (all-legit) flows and events from attached arrivals/sessions.

**Preconditions & gates**  
S0, S1 PASS; flow/amount/timing policies sealed.

**Inputs**  
`s1_arrival_entities_6B`, `s1_session_index_6B`; behaviour policies (`flow_shape_policy_6B`, `amount_model_6B`, `timing_policy_6B`, `flow_rng_policy_6B`); context from 6A posture/features as permitted.

**Outputs & identity**  
`s2_flow_anchor_baseline_6B` at `data/layer3/6B/s2_flow_anchor_baseline_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/`, PK `(seed, fingerprint, scenario_id, flow_id)`, with flow metadata/timestamps/amounts.  
`s2_event_stream_baseline_6B` at `.../s2_event_stream_baseline_6B/.../`, PK `(seed, fingerprint, scenario_id, flow_id, event_seq)`, ordered baseline events.

**RNG posture**  
Philox streams for flow counts/types, event timing, amounts (`rng_event_flow_shape`, `rng_event_event_timing`, `rng_event_amount_draw`); budgets logged and reconciled.

**Key invariants**  
Every baseline flow has >=1 baseline event; flow_ids unique per `(seed, fingerprint, scenario_id)`; flows injectively derived from sessions/arrivals per policy; S3/S4 cannot mutate S2 outputs.

**Downstream consumers**  
S3 overlays campaigns; S4 labels; S5 audits parity and RNG accounting.

---

## S3 - Fraud & abuse campaign overlay (RNG)
**Purpose & scope**  
Overlay structured fraud/abuse campaigns onto baseline flows/events; produce post-overlay flows/events and campaign catalogue.

**Preconditions & gates**  
S0-S2 PASS; fraud/abuse campaign configs and RNG policy sealed; 6A posture available.

**Inputs**  
`s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`; `s1_arrival_entities_6B`, `s1_session_index_6B`; 6A fraud roles; campaign configs (`fraud_campaign_catalogue_config_6B`, `fraud_overlay_policy_6B`, `fraud_rng_policy_6B`).

**Outputs & identity**  
`s3_campaign_catalogue_6B` at `data/layer3/6B/s3_campaign_catalogue_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/`.  
`s3_flow_anchor_with_fraud_6B` at `.../s3_flow_anchor_with_fraud_6B/.../` (same PK as baseline, adds origin/campaign/fraud flags).  
`s3_event_stream_with_fraud_6B` at `.../s3_event_stream_with_fraud_6B/.../` with post-overlay events and provenance.

**RNG posture**  
Philox streams for campaign activation/targeting/mutation (`rng_event_campaign_activation`, `rng_event_campaign_targeting`, `rng_event_overlay_mutation`); budgets logged and reconciled.

**Key invariants**  
Every baseline flow appears in post-overlay anchors (possibly unchanged); pure-fraud flows are marked; overlays respect 6A posture and campaign config; S4 treats S3 as behavioural authority.

**Downstream consumers**  
S4 labels/cases; S5 validates overlays and RNG usage.

---

## S4 - Labels, bank view, and case timelines (RNG)
**Purpose & scope**  
Derive truth labels, bank-view labels, and case timelines from S3 behaviour.

**Preconditions & gates**  
S0-S3 PASS; labelling/bank-view/case policies and RNG sealed.

**Inputs**  
`s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`, `s3_campaign_catalogue_6B`; optional context from S1/S2/6A; labelling and delay policies (`truth_labelling_policy_6B`, `bank_view_policy_6B`, `delay_models_6B`, `case_policy_6B`, `label_rng_policy_6B`).

**Outputs & identity**  
`s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B` at `.../seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/`, one row per flow with truth/bank labels and provenance.  
`s4_event_labels_6B` at `.../s4_event_labels_6B/.../`, one row per event with truth/bank flags.  
`s4_case_timeline_6B` at `.../s4_case_timeline_6B/seed={seed}/fingerprint={manifest_fingerprint}/` with case events per `case_id`.

**RNG posture**  
Philox streams for ambiguous labels and delays (`rng_event_truth_label_ambiguity`, `rng_event_detection_delay`, `rng_event_dispute_delay`, `rng_event_chargeback_delay`, `rng_event_case_timeline`); budgets logged and reconciled.

**Key invariants**  
Exactly one truth row and one bank-view row per flow; exactly one event-label row per S3 event; case timeline events reference valid flows and align with bank-view/delay models.

**Downstream consumers**  
S5 validation; downstream/enterprise consumers read only after `_passed.flag`.

---

## S5 - Validation bundle & `_passed.flag`
**Purpose & scope**  
Validate S0-S4 outputs and publish the 6B HashGate.

**Preconditions & gates**  
S0-S4 PASS; all seeds/scenarios present; upstream gates still verify.

**Inputs**  
`s0_gate_receipt_6B`, `sealed_inputs_6B`; S1-S4 datasets (attachments/sessions, baseline/post-overlay flows/events, labels, case timelines); RNG logs/events/trace; validation policies/tolerances.

**Outputs & identity**  
`s5_validation_report_6B` and optional `s5_issue_table_6B` at `fingerprint={manifest_fingerprint}`; `validation_bundle_6B` at `data/layer3/6B/validation/fingerprint={manifest_fingerprint}/` with `validation_bundle_index_6B`; `_passed.flag` alongside containing `sha256_hex = <bundle_digest>` over indexed files in ASCII-lex order (flag excluded).

**RNG**  
None (validator).

**Key invariants**  
Schema/partition conformance; coverage and FK integrity across arrivals->entities->flows->events->labels/cases; overlays and labels consistent with policies; RNG accounting across S1-S4 closes; bundle digest matches `_passed.flag`; enforces "no PASS -> no read" for all 6B artefacts.

**Downstream consumers**  
Any consumer must verify `_passed.flag` (and upstream gates) before using 6B surfaces.
