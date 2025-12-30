# Authoring Guide — `truth_labelling_policy_6B` (S4 truth mapping rules, v1)

## 0) Purpose

`truth_labelling_policy_6B` defines **how 6B.S4 assigns ground-truth labels** to every flow (and truth roles to events) on the S3 “with-fraud canvas”:

* **Flow truth:** `truth_label ∈ {LEGIT, FRAUD, ABUSE}` + `truth_subtype` + provenance.
* **Event truth roles:** `is_fraud_event_truth` + `truth_event_role` consistent with the flow’s truth label and S3 overlay metadata.

S4 is the **only** state allowed to produce these truth labels, and S4 must fail if labels contradict S3 overlays or this policy.

---

## 1) Contract identity (MUST)

* **manifest_key:** `mlr.6B.policy.truth_labelling_policy`
* **dataset_id:** `truth_labelling_policy_6B`
* **path_template:** `config/layer3/6B/truth_labelling_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/truth_labelling_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S4`

Token-less:

* No timestamps/UUIDs/digests in-file. S0 seals bytes and records `sha256_hex` in `sealed_inputs_6B`.

---

## 2) Dependencies & authority boundary (MUST)

S4 Step 0 explicitly loads this policy alongside `bank_view_policy_6B`, `delay_models_6B`, `case_policy_6B`, and `label_rng_policy_6B` before doing any labelling.

Truth labelling must be driven primarily by:

* S3 flow/event overlays: `fraud_pattern_type`, `campaign_id`, overlay flags, and campaign catalogue,
* and secondarily by deterministic collateral heuristics and sealed posture (6A).

Hard rule: `truth_labelling_policy_6B` may **not** depend on bank-view outcomes (that comes later).

---

## 3) Outputs it must support (what S4 writes)

S4 writes (per `(seed, manifest_fingerprint, parameter_hash, scenario_id)`):

* `s4_flow_truth_labels_6B` (one row per flow)
* `s4_event_labels_6B` (one row per event, keyed to S3 event stream)

Your policy must align to the fields/enums described in the S4 spec:

* `truth_label`, `truth_subtype`, `label_policy_id`, `pattern_source`
* `is_fraud_event_truth`, `truth_event_role`

Coverage is strict: every S3 flow/event must have exactly one corresponding truth row; mismatch is an S4 FAIL.

---

## 4) Deterministic precedence (MUST)

S4 requires deterministic rules to be applied in a documented precedence order; deterministic rules MUST NOT consume RNG.

Recommended v1 precedence (authoritative list in policy):

1. **Direct campaign mapping** (S3 `fraud_pattern_type` / campaign metadata)
2. **Overlay-flag mapping** when campaign metadata exists but subtype needs refinement
3. **Collateral rules** (flows pulled into a fraud “story” by deterministic window/entity rules)
4. **Posture overrides** (e.g., mule/account posture forcing subtype choice, if explicitly allowed)
5. **Residual heuristics** (only if allowed; must be explicit and bounded)
6. **Default**: `LEGIT` when no campaign and no anomaly flags are present (unless policy explicitly overrides)

Violations of “truth ↔ S3 consistency” must fail the partition (`S4_TRUTH_CONSISTENCY_FAILED`).

---

## 5) Ambiguity resolution (MUST; RNG only when needed)

S4 Step 1 requires that ambiguous/collateral cases be resolved by:

* generating a candidate label set + probabilities from this policy, then
* sampling with `rng_event_truth_label_ambiguity` using the pinned key:
  `(manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, "truth")`.

This policy must:

* define **when** a flow is “ambiguous,”
* define how to compute candidate labels + probabilities,
* define the **decision_id** string (v1: `"truth"`) and require that `label_rng_policy_6B` budget the draw count accordingly.

---

## 6) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `truth_labelling_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `vocabulary` (object)
5. `precedence` (list[str])
6. `direct_pattern_map` (list of objects)
7. `collateral_rules` (list of objects)
8. `posture_overrides` (list of objects)
9. `ambiguity_models` (list of objects)
10. `event_truth_roles` (object)
11. `provenance` (object)
12. `constraints` (object)
13. `realism_targets` (object)
14. `notes` *(optional)*

Unknown keys ⇒ INVALID (fail closed).

Token-less:

* no timestamps/digests/UUIDs
* no YAML anchors/aliases

---

## 7) Vocabulary (MUST)

`vocabulary` must pin closed enums used by S4:

* `truth_label_vocab`: `[LEGIT, FRAUD, ABUSE]`
* `truth_subtype_vocab`: include at least the S4-indicative set you intend to use (examples in spec: `CARD_TESTING`, `ATO`, `REFUND_ABUSE`, `MULE_ACTIVITY`, `FRIENDLY_FRAUD`, `NONE`).
* `pattern_source_vocab`: `[CAMPAIGN, COLLATERAL, HEURISTIC_ONLY]`
* `truth_event_role_vocab`: recommended set from S4 spec (e.g., `PRIMARY_FRAUD_ACTION`, `SUPPORTING_EVENT`, `LEGIT_CONTEXT`, `DETECTION_ACTION`, `CASE_EVENT`, `NONE`).

**Pinned sentinel (MUST):**
* The no-fraud/no-overlay sentinel value for `fraud_pattern_type` MUST be the literal string `NONE`.
* If S3 uses any other sentinel in its outputs, the run is invalid (S4 must fail `S4_TRUTH_CONSISTENCY_FAILED`).

---

## 8) Direct campaign/pattern mapping (MUST)

`direct_pattern_map[]` defines deterministic mappings from S3 signals to truth:

Each row MUST include:

* `rule_id`
* `match` (predicate over `fraud_pattern_type`, `campaign_type`, overlay flags)
* `truth_label` (LEGIT/FRAUD/ABUSE)
* `truth_subtype` (from vocab)
* `pattern_source = CAMPAIGN`
* `requires_campaign_id` (bool)

v1 must include the “obvious” base rules described in the S4 spec:

* known fraud patterns → `FRAUD_*` or `ABUSE_*` consistent with the pattern,
* `fraud_pattern_type = NONE` + no overlay anomalies → `LEGIT` (sentinel pinned above).

---

## 9) Collateral rules (MUST be explainable)

Collateral rules pull additional flows into a story deterministically (no RNG).

Each `collateral_rules[]` entry MUST include:

* `rule_id`
* `anchor_condition` (which flows are “primary” fraud anchors)
* `scope_entity` (e.g., `same_account`, `same_instrument`, `same_party`)
* `time_window_seconds` (non-negative)
* `action` (set `truth_label/subtype` OR mark as “ambiguous candidate set”)
* `pattern_source = COLLATERAL`

These are explicitly required to be explainable and consistent with policy; otherwise S4 fails `S4_TRUTH_CONSISTENCY_FAILED`.

---

## 10) Ambiguity models (MUST; RNG-controlled)

`ambiguity_models[]` define candidate label sets and probabilities for ambiguous flows.

Each entry MUST include:

* `model_id`
* `when` predicate (e.g., collateral flow near fraud anchor but uncertain)
* `candidates`: list of `{truth_label, truth_subtype, prob}`
* `rng_family: rng_event_truth_label_ambiguity`
* `decision_id: "truth"`
* `draws_required` (v1 recommended: `"1"`; must match `label_rng_policy_6B`)
* `pattern_source = COLLATERAL` or `HEURISTIC_ONLY`

S4 uses the configured RNG keying for ambiguity (see §5).

---

## 11) Event-level truth roles (MUST)

`event_truth_roles` must define how S4 sets:

* `is_fraud_event_truth`
* `truth_event_role`

Minimal v1 rule set:

* For `truth_label=LEGIT`: all events → `is_fraud_event_truth=false`, `truth_event_role=LEGIT_CONTEXT`.
* For `truth_label in {FRAUD, ABUSE}`:

  * events flagged by S3 overlay as primary mutation/action → `PRIMARY_FRAUD_ACTION`
  * supporting events in the same flow → `SUPPORTING_EVENT`
  * everything else in flow → `LEGIT_CONTEXT`
* `DETECTION_ACTION` and `CASE_EVENT` are reserved for bank-view/case encoding; if your S4 encodes them in the event stream, then the truth policy must specify exactly when they are allowed.

Event label consistency is strict; inconsistencies must fail S4.

---

## 12) Constraints & fail-closed posture (MUST)

`constraints` must include:

* `fail_on_unknown_fraud_pattern_type: true`
* `fail_on_unknown_truth_subtype: true`
* `require_campaign_consistency: true` (cannot label LEGIT if a rule says campaign implies fraud/abuse)
* `require_full_flow_coverage: true` (no unlabeled flows)
* `require_full_event_coverage: true` (event label table matches S3 events exactly)

---

## 13) Minimal v1 example skeleton

```yaml
schema_version: 1
policy_id: truth_labelling_policy_6B
policy_version: v1

vocabulary:
  truth_label_vocab: [LEGIT, FRAUD, ABUSE]
  truth_subtype_vocab: [NONE, CARD_TESTING, ATO, REFUND_ABUSE, MULE_ACTIVITY, FRIENDLY_FRAUD]
  pattern_source_vocab: [CAMPAIGN, COLLATERAL, HEURISTIC_ONLY]
  truth_event_role_vocab: [PRIMARY_FRAUD_ACTION, SUPPORTING_EVENT, LEGIT_CONTEXT, NONE]

precedence:
  - DIRECT_CAMPAIGN
  - OVERLAY_FLAGS
  - COLLATERAL_RULES
  - POSTURE_OVERRIDES
  - AMBIGUITY_MODELS
  - DEFAULT_LEGIT

direct_pattern_map:
  - rule_id: RULE_NONE_NO_OVERLAY
    match: { fraud_pattern_type: NONE, overlay_anomaly_any: false }
    truth_label: LEGIT
    truth_subtype: NONE
    pattern_source: HEURISTIC_ONLY
    requires_campaign_id: false

  - rule_id: RULE_CARD_TESTING
    match: { fraud_pattern_type: CARD_TESTING }
    truth_label: FRAUD
    truth_subtype: CARD_TESTING
    pattern_source: CAMPAIGN
    requires_campaign_id: true

  - rule_id: RULE_ATO
    match: { fraud_pattern_type: ATO }
    truth_label: FRAUD
    truth_subtype: ATO
    pattern_source: CAMPAIGN
    requires_campaign_id: true

  - rule_id: RULE_REFUND_ABUSE
    match: { fraud_pattern_type: REFUND_ABUSE }
    truth_label: ABUSE
    truth_subtype: REFUND_ABUSE
    pattern_source: CAMPAIGN
    requires_campaign_id: true

collateral_rules:
  - rule_id: COLLATERAL_SAME_ACCOUNT_WINDOW
    anchor_condition: { truth_subtype_in: [CARD_TESTING, ATO], pattern_source: CAMPAIGN }
    scope_entity: same_account
    time_window_seconds: 14400   # 4 hours
    action:
      mode: AMBIGUOUS
      candidates_model_id: AMBIG_COLLATERAL_ACCOUNT
    pattern_source: COLLATERAL

posture_overrides: []

ambiguity_models:
  - model_id: AMBIG_COLLATERAL_ACCOUNT
    when: { collateral_from_rule: COLLATERAL_SAME_ACCOUNT_WINDOW }
    candidates:
      - { truth_label: FRAUD, truth_subtype: ATO, prob: 0.20 }
      - { truth_label: LEGIT, truth_subtype: NONE, prob: 0.80 }
    rng_family: rng_event_truth_label_ambiguity
    decision_id: "truth"
    draws_required: "1"
    pattern_source: COLLATERAL

event_truth_roles:
  mode: overlay_flags_then_flow_truth_v1
  rules:
    - when_flow_truth_label: LEGIT
      default: { is_fraud_event_truth: false, truth_event_role: LEGIT_CONTEXT }
    - when_flow_truth_label_in: [FRAUD, ABUSE]
      primary_event_when: { s3_overlay_primary_flag: true }
      primary: { is_fraud_event_truth: true, truth_event_role: PRIMARY_FRAUD_ACTION }
      supporting: { is_fraud_event_truth: true, truth_event_role: SUPPORTING_EVENT }
      default: { is_fraud_event_truth: false, truth_event_role: LEGIT_CONTEXT }

provenance:
  label_policy_id_field: label_policy_id
  include_campaign_id: true
  include_pattern_source: true

constraints:
  fail_on_unknown_fraud_pattern_type: true
  fail_on_unknown_truth_subtype: true
  require_campaign_consistency: true
  require_full_flow_coverage: true
  require_full_event_coverage: true

realism_targets:
  fraud_fraction_range: { min: 0.0005, max: 0.10 }
  abuse_fraction_range: { min: 0.0002, max: 0.08 }
```

---

## 14) Acceptance checklist (MUST)

* Identity matches registry/dictionary (manifest_key/path/schema_ref).
* Deterministic precedence applied; deterministic rules consume **no RNG**.
* Ambiguity uses `rng_event_truth_label_ambiguity` with the pinned key shape and draw count matching `label_rng_policy_6B`.
* Every S3 flow gets exactly one truth row; every S3 event gets exactly one event-label row; otherwise S4 FAIL.
* Truth labels are consistent with S3 overlays and campaign metadata; otherwise `S4_TRUTH_CONSISTENCY_FAILED`.

---
