# Authoring Guide — `bank_view_policy_6B` (S4 bank decisions, detection, disputes/chargebacks, v1)

## 0) Purpose

`bank_view_policy_6B` is the **sealed authority** for **how the bank perceives and reacts** to each post-overlay flow over time in **6B.S4 Step 2**:

* auth-time decision: `APPROVE | DECLINE | REVIEW | CHALLENGE`
* detection outcome + timestamps: `DETECTED_AT_AUTH | DETECTED_POST_AUTH | NOT_DETECTED` and `detection_ts_utc`
* customer dispute / chargeback outcomes + timestamps: `dispute_ts_utc`, `chargeback_ts_utc`, chargeback type/outcome
* final bank classification: `bank_view_label` (e.g., `BANK_CONFIRMED_FRAUD`, `NO_CASE_OPENED`, …)
* preliminary case lifecycle timestamps: `case_opened_ts_utc`, `case_closed_ts_utc` (case_policy may refine timeline later)

This policy MUST be **deterministic in semantics**: any stochastic decisions must go only through S4 RNG families defined in `label_rng_policy_6B`.

---

## 1) Contract identity (MUST)

* **manifest_key:** `mlr.6B.policy.bank_view_policy` 
* **dataset_id:** `bank_view_policy_6B` 
* **path:** `config/layer3/6B/bank_view_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/bank_view_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S4`

Token-less posture:

* no timestamps/UUIDs/digests in-file; S0 sealing records `sha256_hex` in `sealed_inputs_6B`.

---

## 2) Dependencies (MUST)

S4 Step 2 uses this policy together with:

* `truth_labelling_policy_6B` + `s4_flow_truth_labels_6B` (truth input; bank view must be compatible with truth but not identical)
* `delay_models_6B` (all delay distributions; this policy references delay model IDs, but does not define distributions)
* `case_policy_6B` (case opening rules; this policy can set preliminary `case_opened_ts_utc`, but case timeline is governed by case policy)
* `label_rng_policy_6B` (S4 RNG families/budgets: truth ambiguity, detection delay, dispute delay, chargeback delay, case timeline RNG)

And S4 may join sealed context from S1–S3 + 6A posture surfaces when permitted.

---

## 3) Required S4 algorithm surface this policy must support

For each flow `f` in `s3_flow_anchor_with_fraud_6B`, S4 Step 2 performs:

1. Auth decision (deterministic or probabilistic)
2. Detection outcome + detection delay (via `delay_models_6B` + `rng_event_detection_delay`)
3. Dispute outcome + dispute delay (via `delay_models_6B` + `rng_event_dispute_delay`)
4. Chargeback outcome + chargeback delay/type (via `delay_models_6B` + `rng_event_chargeback_delay`)
5. Final `bank_view_label` and lifecycle timestamps (`case_opened_ts_utc`, `case_closed_ts_utc`)

Your policy must define each step’s eligibility, rules, and mapping to outputs.

---

## 4) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `bank_view_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `vocabulary` (object)
5. `inputs_allowed` (object)
6. `auth_decision_model` (object)
7. `detection_model` (object)
8. `dispute_model` (object)
9. `chargeback_model` (object)
10. `case_lifecycle_model` (object)
11. `final_label_map` (object)
12. `event_label_hints` (object)
13. `constraints` (object)
14. `realism_targets` (object)
15. `notes` (optional)

Unknown keys ⇒ **INVALID** (fail closed at S0).

Token-less:

* no timestamps/digests/UUIDs
* no YAML anchors/aliases

---

## 5) Vocabulary (MUST)

`vocabulary` MUST define closed enums used in `s4_flow_bank_view_6B`:

* `auth_decision_vocab`: `[APPROVE, DECLINE, REVIEW, CHALLENGE]`
* `detection_outcome_vocab`: `[DETECTED_AT_AUTH, DETECTED_POST_AUTH, NOT_DETECTED]`
* `bank_view_label_vocab`: include at least the spec-indicative set you plan to emit, e.g.
  `BANK_CONFIRMED_FRAUD`, `BANK_CONFIRMED_LEGIT`, `NO_CASE_OPENED`, `CUSTOMER_DISPUTE_REJECTED`, `CHARGEBACK_WRITTEN_OFF`
* `chargeback_type_vocab` (if modelling types; e.g. `UNAUTHORISED`, `SERVICE_DISPUTE`, `FRAUD_CARD_NOT_PRESENT`, …)
* `chargeback_outcome_vocab` (e.g. `BANK_WIN`, `BANK_LOSS`, `PARTIAL`, `NONE`)
* `dispute_outcome_vocab` (e.g. `FILED`, `NOT_FILED`)

---

## 6) Allowed inputs (MUST be explicit)

`inputs_allowed` prevents hidden dependencies. It MUST list:

### Required sources (minimum)

* flow truth label + subtype (`s4_flow_truth_labels_6B`)
* S3 overlay metadata on the flow/event canvas (campaign/pattern fields)
* S2/S3 amounts + times (used for “amount anomaly” / timing context)

### Optional sources (must be declared if used)

* 6A static posture surfaces (party/account/merchant/device/ip roles)
* derived “risk score” inputs (bucketed, deterministic; must be computable without arrivals beyond the flow itself)

Hard rule:

* If a feature is declared required but cannot be computed from sealed inputs, S4 must FAIL (`S4_PRECONDITION_INPUT_MISSING`).

---

## 7) RNG integration (policy references families; budgets live in `label_rng_policy_6B`)

The S4 spec enumerates the RNG families used in S4:

* `rng_event_detection_delay` (detection vs non-detection + detection delay sampling)
* `rng_event_dispute_delay` (whether dispute occurs + dispute delay)
* `rng_event_chargeback_delay` (chargeback initiation + chargeback delay/outcome)
* `rng_event_case_timeline` (any remaining case stochasticity, if used)

Auth decision randomness can either:

* be deterministic, OR
* reuse `rng_event_detection_delay` with `decision_id="auth_decision"` (as the S4 spec suggests is acceptable).

Keying MUST be pinned (no run_id), and must include at least:
`(manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id)` for per-flow decisions.

---

## 8) Step models (what the policy must define)

### 8.1 `auth_decision_model`

Must define:

* deterministic rules (e.g., always decline for some patterns)
* probabilistic rules (e.g., review vs approve vs challenge) by context:

  * channel_group
  * truth_subtype (latent for simulation realism)
  * optional “bank_risk_score” buckets

Required fields:

* `mode`: `DETERMINISTIC_PLUS_MIXTURE_V1`
* `rules[]`: ordered (first match wins), each with:

  * `rule_id`
  * `when` predicate (flow context)
  * either:

    * `deterministic_decision` (one of vocab), or
    * `pi_decision` list `{auth_decision, prob}` summing to 1
  * `rng_family` + `decision_id` (only if probabilistic)

### 8.2 `detection_model`

Must define:

* eligibility: which flows are even “detectable”
* probability of detection, and whether detection is at-auth or post-auth
* mapping from detection to `detection_ts_utc`:

  * at-auth uses an auth-time timestamp from the flow events
  * post-auth uses `delay_models_6B` + `rng_event_detection_delay`

Required fields:

* `eligibility_rules[]` (deterministic)
* `p_detect_by_truth_subtype` (table, optionally conditioned on auth_decision)
* `p_detect_at_auth_given_detect` (table)
* `delay_model_id_for_post_auth_detection` (string; must exist in delay_models_6B)
* RNG hooks:

  * `rng_family: rng_event_detection_delay`
  * `decision_ids`: `detect_flag`, `detect_at_auth_flag`, `detect_delay`

### 8.3 `dispute_model`

Must define:

* dispute eligibility and probability by truth label/subtype and bank actions
* delay model to sample `dispute_ts_utc` if dispute occurs

Required:

* `eligibility_rules[]`
* `p_dispute_by_truth_subtype` (table)
* `delay_model_id_for_dispute` (id into delay_models_6B)
* RNG hooks:

  * `rng_family: rng_event_dispute_delay`
  * `decision_ids`: `dispute_flag`, `dispute_delay`

### 8.4 `chargeback_model`

Must define:

* eligibility (typically only for card-like flows and disputes)
* probability of chargeback initiation
* chargeback type distribution
* chargeback outcome distribution conditioned on truth label/subtype (bank win/loss)
* delay model(s) for `chargeback_ts_utc`

Required:

* `eligibility_rules[]`
* `p_chargeback_given_dispute` (table)
* `pi_chargeback_type` (table)
* `pi_chargeback_outcome` (table)
* `delay_model_id_for_chargeback` (id into delay_models_6B)
* RNG hooks:

  * `rng_family: rng_event_chargeback_delay`
  * `decision_ids`: `chargeback_flag`, `chargeback_type`, `chargeback_outcome`, `chargeback_delay`

### 8.5 `case_lifecycle_model`

Must define when a “case is opened” from bank view, and how preliminary open/close timestamps are set (case_policy may later author the detailed timeline).

Required:

* `open_case_when` predicates (e.g., detection true OR dispute filed OR manual review)
* `case_open_ts_rule` (e.g., min(detection_ts, dispute_ts, auth_ts when review/challenge))
* `case_close_delay_model_id` (id into delay_models_6B) + RNG hook (optional)
* `no_case_label` token (e.g., `NO_CASE_OPENED`)

### 8.6 `final_label_map`

A deterministic mapping from:
`(truth_label, auth_decision, detection_outcome, dispute_flag, chargeback_flag/outcome, case_opened_flag)`
to `bank_view_label`.

Must be:

* total (covers all combinations the policy can produce)
* non-ambiguous (no “else” without explicit rule_id)

### 8.7 `event_label_hints`

S4 Step 3 sets `is_detection_action` and `is_case_event` flags on `s4_event_labels_6B` using bank-view context.

This policy should provide **hints**, not full event generation:

* which event types are considered “auth-time decision events” (e.g., AUTH_RESPONSE)
* when to mark an event as detection action (relative to `detection_ts_utc`)
* when to mark an event as case event (relative to case open/close)

---

## 9) Constraints (hard fails)

`constraints` MUST include:

* `fail_on_unknown_enum: true` (unknown auth_decision/detection outcome/etc.)
* `require_one_row_per_flow: true` (S4 must emit exactly one bank-view row for every S3 flow)
* `require_timestamps_consistent_with_events: true` (e.g., detection_ts must be within scenario and not before flow start)
* `forbid_time_travel: true` (case/dispute/chargeback timestamps must be monotone with respect to flow time)
* `forbid_bank_confirmed_fraud_when_truth_legit_without_dispute`: **policy choice** (if you want false positives, encode them explicitly with probabilities + constraints)

---

## 10) Realism targets (corridor checks)

To enforce “no toy stuff”, include corridors such as:

* `false_positive_rate_range` (LEGIT flows labelled as suspicious/fraud by bank)
* `false_negative_rate_range_by_truth_subtype` (FRAUD/ABUSE flows not detected/no dispute)
* `detection_rate_range_by_truth_subtype` (detected at any time)
* `detection_at_auth_fraction_range` (given detected)
* `dispute_rate_range_by_truth_subtype`
* `chargeback_rate_range_given_dispute`
* `bank_win_rate_range_on_chargeback_by_truth_subtype`
* `mean_detection_delay_range_seconds` (post-auth)
* `mean_dispute_delay_range_seconds`
* `mean_chargeback_delay_range_seconds`

These should be checked in S5 validation against realised outputs.

---

## 11) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: bank_view_policy_6B
policy_version: v1

vocabulary:
  auth_decision_vocab: [APPROVE, DECLINE, REVIEW, CHALLENGE]
  detection_outcome_vocab: [DETECTED_AT_AUTH, DETECTED_POST_AUTH, NOT_DETECTED]
  bank_view_label_vocab:
    - BANK_CONFIRMED_FRAUD
    - BANK_CONFIRMED_LEGIT
    - NO_CASE_OPENED
    - CUSTOMER_DISPUTE_REJECTED
    - CHARGEBACK_WRITTEN_OFF
  dispute_outcome_vocab: [FILED, NOT_FILED]
  chargeback_type_vocab: [UNAUTHORISED, SERVICE_DISPUTE, OTHER]
  chargeback_outcome_vocab: [BANK_WIN, BANK_LOSS, PARTIAL, NONE]

inputs_allowed:
  required_sources: [s4_flow_truth_labels_6B, s3_flow_anchor_with_fraud_6B]
  optional_sources: [s1_arrival_entities_6B, s5_party_fraud_roles_6A, s5_account_fraud_roles_6A]
  forbid_arrival_row_level_use: true

auth_decision_model:
  mode: DETERMINISTIC_PLUS_MIXTURE_V1
  rules:
    - rule_id: AUTH_ALWAYS_DECLINE_CARD_TESTING
      when: { truth_subtype_in: [CARD_TESTING], channel_group_in: [ECOM, POS] }
      deterministic_decision: DECLINE

    - rule_id: AUTH_MIX_DEFAULT
      when: { any: true }
      pi_decision:
        - { auth_decision: APPROVE,  prob: 0.965 }
        - { auth_decision: REVIEW,   prob: 0.020 }
        - { auth_decision: CHALLENGE,prob: 0.010 }
        - { auth_decision: DECLINE,  prob: 0.005 }
      rng_family: rng_event_detection_delay
      decision_id: auth_decision

detection_model:
  eligibility_rules:
    - { rule_id: DETECT_ONLY_NONLEGIT_OR_FLAGGED, when: { truth_label_in: [FRAUD, ABUSE] }, eligible: true }
    - { rule_id: DETECT_LEGIT_RARE_FP, when: { truth_label_in: [LEGIT] }, eligible: true }

  p_detect_by_truth_subtype:
    NONE: 0.002
    CARD_TESTING: 0.55
    ATO: 0.35
    REFUND_ABUSE: 0.15
    FRIENDLY_FRAUD: 0.08

  p_detect_at_auth_given_detect:
    CARD_TESTING: 0.55
    ATO: 0.20
    REFUND_ABUSE: 0.05
    FRIENDLY_FRAUD: 0.02
    NONE: 0.40

  delay_model_id_for_post_auth_detection: DETECTION_DELAY_V1
  rng_family: rng_event_detection_delay
  decision_ids: [detect_flag, detect_at_auth_flag, detect_delay]

dispute_model:
  p_dispute_by_truth_subtype:
    NONE: 0.002
    CARD_TESTING: 0.10
    ATO: 0.45
    REFUND_ABUSE: 0.30
    FRIENDLY_FRAUD: 0.55
  delay_model_id_for_dispute: DISPUTE_DELAY_V1
  rng_family: rng_event_dispute_delay
  decision_ids: [dispute_flag, dispute_delay]

chargeback_model:
  eligibility_rules:
    - { rule_id: CB_ONLY_IF_DISPUTE, when: { dispute_filed: true }, eligible: true }
    - { rule_id: CB_ELSE_NOT, when: { dispute_filed: false }, eligible: false }

  p_chargeback_given_dispute:
    CARD_TESTING: 0.25
    ATO: 0.45
    REFUND_ABUSE: 0.20
    FRIENDLY_FRAUD: 0.35
    NONE: 0.05

  pi_chargeback_type:
    default:
      - { chargeback_type: UNAUTHORISED, prob: 0.70 }
      - { chargeback_type: SERVICE_DISPUTE, prob: 0.20 }
      - { chargeback_type: OTHER, prob: 0.10 }

  pi_chargeback_outcome:
    FRAUD:
      - { chargeback_outcome: BANK_LOSS, prob: 0.75 }
      - { chargeback_outcome: BANK_WIN,  prob: 0.15 }
      - { chargeback_outcome: PARTIAL,   prob: 0.10 }
    ABUSE:
      - { chargeback_outcome: BANK_LOSS, prob: 0.35 }
      - { chargeback_outcome: BANK_WIN,  prob: 0.55 }
      - { chargeback_outcome: PARTIAL,   prob: 0.10 }
    LEGIT:
      - { chargeback_outcome: BANK_LOSS, prob: 0.05 }
      - { chargeback_outcome: BANK_WIN,  prob: 0.90 }
      - { chargeback_outcome: PARTIAL,   prob: 0.05 }

  delay_model_id_for_chargeback: CHARGEBACK_DELAY_V1
  rng_family: rng_event_chargeback_delay
  decision_ids: [chargeback_flag, chargeback_type, chargeback_outcome, chargeback_delay]

case_lifecycle_model:
  open_case_when:
    - { rule_id: OPEN_ON_DETECTION, when: { detection_outcome_in: [DETECTED_AT_AUTH, DETECTED_POST_AUTH] }, open: true }
    - { rule_id: OPEN_ON_REVIEW, when: { auth_decision_in: [REVIEW, CHALLENGE] }, open: true }
    - { rule_id: OPEN_ON_DISPUTE, when: { dispute_filed: true }, open: true }

  case_open_ts_rule: MIN_OF_AVAILABLE
  case_close_delay_model_id: CASE_CLOSE_DELAY_V1
  rng_family: rng_event_case_timeline
  decision_ids: [case_close_delay]

final_label_map:
  mode: rule_table_v1
  rules:
    - rule_id: LABEL_CONFIRMED_FRAUD
      when: { truth_label: FRAUD, detection_outcome_in: [DETECTED_AT_AUTH, DETECTED_POST_AUTH] }
      bank_view_label: BANK_CONFIRMED_FRAUD

    - rule_id: LABEL_CHARGEBACK_WRITTEN_OFF
      when: { chargeback_outcome: BANK_LOSS }
      bank_view_label: CHARGEBACK_WRITTEN_OFF

    - rule_id: LABEL_DISPUTE_REJECTED
      when: { dispute_filed: true, chargeback_outcome_in: [BANK_WIN, PARTIAL] }
      bank_view_label: CUSTOMER_DISPUTE_REJECTED

    - rule_id: LABEL_NO_CASE
      when: { case_opened: false }
      bank_view_label: NO_CASE_OPENED

    - rule_id: LABEL_CONFIRMED_LEGIT
      when: { truth_label: LEGIT }
      bank_view_label: BANK_CONFIRMED_LEGIT

event_label_hints:
  detection_action_window:
    mark_is_detection_action_if_event_ts_between: [detection_ts_utc_minus, detection_ts_utc_plus]
    window_seconds: 60
  case_event_window:
    mark_is_case_event_if_event_ts_between: [case_opened_ts_utc_minus, case_closed_ts_utc_plus]
    window_seconds: 300

constraints:
  fail_on_unknown_enum: true
  require_one_row_per_flow: true
  require_timestamps_consistent_with_events: true
  forbid_time_travel: true

realism_targets:
  false_positive_rate_range: { min: 0.0005, max: 0.02 }
  detection_rate_range_by_truth_label:
    FRAUD: { min: 0.05, max: 0.95 }
    ABUSE: { min: 0.01, max: 0.60 }
    LEGIT: { min: 0.0001, max: 0.05 }
```

---

## 12) Acceptance checklist (MUST)

* Identity matches registry/dictionary: manifest_key/path/schema_ref.
* Produces bank-view outcomes described in S4: auth decision, detection outcome + timestamps, dispute/chargeback + timestamps, final label.
* Uses S4 RNG families exactly as the S4 spec expects (detection/dispute/chargeback/case), and keying includes `(mf, ph, seed, scenario_id, flow_id, decision_id)`; no run_id.
* Every S3 flow gets exactly one `s4_flow_bank_view_6B` row (PK parity with truth labels).
* Token-less, fields-strict, no YAML anchors/aliases.

---
