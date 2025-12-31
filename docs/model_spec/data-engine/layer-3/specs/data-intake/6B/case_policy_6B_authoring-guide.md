# Authoring Guide — `case_policy_6B` (S4 case grouping, escalation, closure, v1)

## 0) Purpose

`case_policy_6B` is the **required** S4 policy pack that defines how 6B.S4 turns **flow-level truth + bank-view lifecycle** into a **case-level timeline** (`s4_case_timeline_6B`) by:

* deciding **which flows are “case-involved”** (based on `s4_flow_bank_view_6B`),
* defining deterministic **case keys** and grouping strategy,
* defining deterministic **case_id** construction (stable within `(seed, manifest_fingerprint)`),
* defining the **case event vocabulary** and the **state machine** (allowed transitions),
* defining how to emit **case events** (timestamps, linking to flows/events),
* defining any (optional) stochastic “split into multiple cases” behaviour (must go via `rng_event_case_timeline`).

S4 explicitly treats this as a required config pack and uses it to build case timelines.

---

## 1) Contract identity (MUST)

From your 6B registry/dictionary:

* **manifest_key:** `mlr.6B.policy.case_policy`
* **dataset_id:** `case_policy_6B`
* **path:** `config/layer3/6B/case_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/case_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S4`

Token-less posture:

* no timestamps/UUIDs/digests in-file; S0 sealing records `sha256_hex` in `sealed_inputs_6B`.

---

## 2) Inputs and authority boundaries (MUST)

### Required inputs (sealed by S0; row-level)

S4 constructs cases using:

* `s4_flow_bank_view_6B` (bank lifecycle timestamps & outcomes),
* `s4_flow_truth_labels_6B` (truth label/subtype),
* and S3 overlay metadata on flows when needed (campaign/pattern provenance),
  then emits `s4_case_timeline_6B@{seed,fingerprint}`.

### Prohibitions

* S4 MUST NOT create/drop flows/events; cases are derived only.
* Any case event sequence MUST follow the state machine defined here; violations fail the case scope.

---

## 3) What this policy MUST define (S4 Step 4 requirements)

S4 Step 4 explicitly requires case_policy to define:

* case keys & grouping strategy,
* deterministic `case_id` assignment,
* case event sequence generation consistent with bank-view + delay models + RNG policy,
* and the state machine constraints.

---

## 4) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `case_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `vocabulary` (object)
5. `case_involvement` (object)
6. `case_key_model` (object)
7. `case_grouping_model` (object)
8. `case_id_model` (object)
9. `case_event_model` (object)
10. `state_machine` (object)
11. `stochastic_splitting` (object)
12. `guardrails` (object)
13. `realism_targets` (object)
14. `notes` (optional)

Unknown keys ⇒ **INVALID** (fail closed at S0/S4).
No YAML anchors/aliases. Token-less file.

---

## 5) Vocabulary (MUST)

`vocabulary` MUST include:

* `case_event_type_vocab` — at minimum include the S4-indicated case events:
  `CASE_OPENED`, `DETECTION_EVENT_ATTACHED`, `CUSTOMER_DISPUTE_FILED`, `CHARGEBACK_INITIATED`, `CHARGEBACK_DECISION`, `CASE_CLOSED`.
* `case_type_vocab` (recommended): coarse case categories, e.g. `DETECTION_CASE`, `DISPUTE_CASE`, `CHARGEBACK_CASE`, `REVIEW_CASE`.
* `case_outcome_vocab` (recommended): e.g. `CONFIRMED_FRAUD`, `CONFIRMED_LEGIT`, `BANK_LOSS`, `BANK_WIN`, `UNKNOWN`.
* `case_key_type_vocab` (recommended): e.g. `INSTRUMENT`, `ACCOUNT`, `PARTY`, `MERCHANT`.

---

## 6) Case involvement predicate (MUST)

`case_involvement` MUST pin which flows “require case handling”.

v1 recommended (deterministic, fail-closed if fields missing):

* `case_involved = (case_opened_ts_utc != null) OR (bank_view_label in case_trigger_labels)`.

This aligns with S4’s requirement: any flow the bank-view indicates is in a case must appear in the case timeline.

---

## 7) Case key model (MUST)

S4 requires a deterministic case_key definition.

### 7.1 Key selection precedence (recommended v1)

Define a priority order for picking a stable key from the flow context:

1. If `instrument_id` is present → `case_key_type=INSTRUMENT`, `case_key_value=instrument_id`
2. Else if `account_id` present → `ACCOUNT`
3. Else if `party_id` present → `PARTY`
4. Else if `merchant_id` present → `MERCHANT`
   Else: FAIL (case-involved flow without any key material is invalid).

### 7.2 Key encoding (MUST)

Define a canonical `case_key_string`:

`case_key_string = "{case_key_type}|{case_key_value}"`

and include `(seed, manifest_fingerprint)` implicitly (not inside the string; those are already partition axes).

### 7.3 Optional enrichments (allowed)

You MAY include a time-bucket discriminator in the key **only if** you want cases never to span long windows, but the policy must then define the bucket law exactly (e.g., ISO-week of `case_anchor_ts_utc`).

---

## 8) Case grouping model (MUST)

Grouping occurs at the **(seed, fingerprint)** scope (case timeline partitions don’t include scenario_id).

`case_grouping_model` MUST define:

* `case_anchor_ts_source` (deterministic):

  * `MIN_NON_NULL(case_opened_ts_utc, detection_ts_utc, dispute_ts_utc, chargeback_ts_utc, flow_first_ts_utc)`
* `group_window_seconds` (flows within this window from the anchor can be in the same case)
* `reopen_gap_seconds` (if a new case-involved flow occurs after this gap, open a new case even with same case_key)
* deterministic flow ordering for grouping (e.g., sort by `case_anchor_ts_utc`, tie-break `flow_id` asc).

---

## 9) Case ID model (MUST be deterministic)

S4 requires deterministic `case_id` generation, and gives a canonical shape: hash over `(mf, seed, case_key, case_index_within_key)`.

`case_id_model` MUST define:

* `mode: hash64_v1`
* `domain_tag: "mlr:6B.case_id.v1"`
* `inputs: [manifest_fingerprint, seed, case_key_string, case_index_within_key]`
* output format (e.g., `id64_hex_le`)

Rule:

* `case_index_within_key` is 0-based within each `case_key_string`, after applying grouping windows.

---

## 10) Case event model (MUST)

S4’s case timeline rows encode “case events” like CASE_OPENED, DISPUTE, CHARGEBACK, CLOSED.

`case_event_model` MUST define:

### 10.1 Which events exist and when they are emitted

At minimum, for each case:

* `CASE_OPENED` (MUST be first event)
* optional: `DETECTION_EVENT_ATTACHED` if any flow in the case has detection
* optional: `CUSTOMER_DISPUTE_FILED` if any flow in the case has dispute
* optional: `CHARGEBACK_INITIATED` if any flow has chargeback
* optional: `CHARGEBACK_DECISION` if any flow has a chargeback outcome
* `CASE_CLOSED` (MUST be last event unless `allow_open_cases=true`)

### 10.2 Timestamp source per event type (MUST)

Pinned default (safe, consistent with S4 acceptance constraints):

* `CASE_OPENED.ts = min(case_opened_ts_utc across member flows)`
* `DETECTION_EVENT_ATTACHED.ts = min(detection_ts_utc across member flows)`
* `CUSTOMER_DISPUTE_FILED.ts = min(dispute_ts_utc across member flows)`
* `CHARGEBACK_INITIATED.ts = min(chargeback_ts_utc across member flows)`
* `CHARGEBACK_DECISION.ts = CASE_CLOSED.ts` (v1 simple)
* `CASE_CLOSED.ts`:

  * if any member flow has `case_closed_ts_utc`, use `max(case_closed_ts_utc)`
  * else sample close delay using `delay_models_6B` + S4 RNG (`rng_event_case_timeline`) (see §11)

All case event timestamps MUST be non-decreasing and consistent with flow-level timestamps, otherwise S4 must FAIL.

### 10.3 Linkage fields

Policy must specify which fields are populated per case event row (schema will later enforce):

* always: `case_id`, `case_event_seq`, `case_event_type`, `case_event_ts_utc`
* optional linkage: `flow_id` and/or `scenario_id` for the “triggering” flow (tie-break by earliest event time, then flow_id asc).

---

## 11) State machine (MUST)

S4 requires that case events follow a state machine defined here, and treats violations as FAIL.

v1 recommended state machine:

* `START -> CASE_OPENED`
* `CASE_OPENED -> (DETECTION_EVENT_ATTACHED | CUSTOMER_DISPUTE_FILED | CHARGEBACK_INITIATED | CASE_CLOSED)`
* `DETECTION_EVENT_ATTACHED -> (CUSTOMER_DISPUTE_FILED | CHARGEBACK_INITIATED | CASE_CLOSED)`
* `CUSTOMER_DISPUTE_FILED -> (CHARGEBACK_INITIATED | CASE_CLOSED)`
* `CHARGEBACK_INITIATED -> (CHARGEBACK_DECISION | CASE_CLOSED)`
* `CHARGEBACK_DECISION -> CASE_CLOSED`
* `CASE_CLOSED -> END` (no further events)

And multiplicity rules (must be explicit):

* `CASE_OPENED`: exactly once
* `CASE_CLOSED`: exactly once (unless `allow_open_cases=true`)
* other events: at most once each in v1 (keeps it clean)

---

## 12) Stochastic splitting (optional; MUST be pinned if enabled)

S4 allows stochastic assignment of flows to multiple cases within a key group, but requires use of `rng_event_case_timeline` with key `(mf, ph, seed, case_key, flow_id)` and fixed budgets.

`stochastic_splitting` MUST define:

* `enabled` (bool; v1 default false)
* if enabled:

  * `rng_family: rng_event_case_timeline`
  * `decision_id: case_split`
  * `max_cases_per_case_key` (int)
  * deterministic base split (e.g., “split by time window first”), then RNG only for ambiguous assignments.

---

## 13) Guardrails (MUST)

Hard caps to prevent runaway:

* `max_cases_per_seed_fingerprint`
* `max_flows_per_case`
* `max_case_duration_seconds`
* `max_case_events_per_case` (must be consistent with state machine)

On violation: v1 should FAIL the case scope (avoid silent clamp unless behaviour_config explicitly allows clamp-and-warn).

---

## 14) Realism targets (MUST)

Non-toy corridors checked in S5:

* `case_involvement_fraction_range` (fraction of flows that end up in any case)
* `mean_flows_per_case_range`
* `mean_case_duration_range_seconds`
* `chargeback_case_fraction_range`
* `multi_flow_case_fraction_range` (ensures not all cases are singletons)
* `max_case_cluster_size_cap` (prevents absurd mega-cases)

These must be compatible with bank_view + delay models.

---

## 15) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: case_policy_6B
policy_version: v1

vocabulary:
  case_event_type_vocab:
    - CASE_OPENED
    - DETECTION_EVENT_ATTACHED
    - CUSTOMER_DISPUTE_FILED
    - CHARGEBACK_INITIATED
    - CHARGEBACK_DECISION
    - CASE_CLOSED
  case_key_type_vocab: [INSTRUMENT, ACCOUNT, PARTY, MERCHANT]
  case_type_vocab: [DETECTION_CASE, DISPUTE_CASE, CHARGEBACK_CASE, REVIEW_CASE]
  case_outcome_vocab: [CONFIRMED_FRAUD, CONFIRMED_LEGIT, BANK_LOSS, BANK_WIN, UNKNOWN]

case_involvement:
  mode: bank_view_driven_v1
  predicate:
    any_of:
      - { field: case_opened_ts_utc, op: NOT_NULL }
      - { field: bank_view_label, op: IN, values: [BANK_CONFIRMED_FRAUD, CUSTOMER_DISPUTE_REJECTED, CHARGEBACK_WRITTEN_OFF] }

case_key_model:
  mode: precedence_v1
  precedence: [INSTRUMENT, ACCOUNT, PARTY, MERCHANT]
  fields:
    INSTRUMENT: instrument_id
    ACCOUNT: account_id
    PARTY: party_id
    MERCHANT: merchant_id
  encode:
    mode: concat_v1
    format: "{case_key_type}|{case_key_value}"

case_grouping_model:
  case_anchor_ts_source: MIN_NON_NULL
  group_window_seconds: 604800        # 7 days
  reopen_gap_seconds: 1209600         # 14 days
  sort_member_flows_by: [case_anchor_ts_utc, flow_id]

case_id_model:
  mode: hash64_v1
  domain_tag: "mlr:6B.case_id.v1"
  inputs: [manifest_fingerprint, seed, case_key_string, case_index_within_key]
  output_format: id64_hex_le

case_event_model:
  allow_open_cases: false
  event_ts_sources:
    CASE_OPENED: { mode: MIN_CASE_OPENED_TS }
    DETECTION_EVENT_ATTACHED: { mode: MIN_DETECTION_TS }
    CUSTOMER_DISPUTE_FILED: { mode: MIN_DISPUTE_TS }
    CHARGEBACK_INITIATED: { mode: MIN_CHARGEBACK_TS }
    CHARGEBACK_DECISION: { mode: CASE_CLOSED_TS }
    CASE_CLOSED:
      mode: FROM_BANK_VIEW_IF_PRESENT_ELSE_DELAY_MODEL
      delay_model_id: CASE_CLOSE_DELAY_V1
      rng_family: rng_event_case_timeline
      decision_id: case_close_delay
  linkage:
    trigger_flow_tie_break: [min_event_ts, flow_id_asc]
    include_flow_id_on_events: true

state_machine:
  mode: v1_table
  require_first_event: CASE_OPENED
  require_last_event: CASE_CLOSED
  max_once_events: [CASE_OPENED, CASE_CLOSED, DETECTION_EVENT_ATTACHED, CUSTOMER_DISPUTE_FILED, CHARGEBACK_INITIATED, CHARGEBACK_DECISION]
  allowed_transitions:
    START: [CASE_OPENED]
    CASE_OPENED: [DETECTION_EVENT_ATTACHED, CUSTOMER_DISPUTE_FILED, CHARGEBACK_INITIATED, CASE_CLOSED]
    DETECTION_EVENT_ATTACHED: [CUSTOMER_DISPUTE_FILED, CHARGEBACK_INITIATED, CASE_CLOSED]
    CUSTOMER_DISPUTE_FILED: [CHARGEBACK_INITIATED, CASE_CLOSED]
    CHARGEBACK_INITIATED: [CHARGEBACK_DECISION, CASE_CLOSED]
    CHARGEBACK_DECISION: [CASE_CLOSED]
    CASE_CLOSED: []

stochastic_splitting:
  enabled: false
  rng_family: rng_event_case_timeline
  decision_id: case_split
  max_cases_per_case_key: 3

guardrails:
  max_cases_per_seed_fingerprint: 200000
  max_flows_per_case: 200
  max_case_duration_seconds: 7776000       # 90 days
  max_case_events_per_case: 12

realism_targets:
  case_involvement_fraction_range: { min: 0.0005, max: 0.20 }
  mean_flows_per_case_range: { min: 1.1, max: 25.0 }
  mean_case_duration_range_seconds: { min: 3600.0, max: 2592000.0 }
  chargeback_case_fraction_range: { min: 0.0001, max: 0.05 }
  multi_flow_case_fraction_range: { min: 0.02, max: 0.50 }
```

---

## 16) Acceptance checklist (MUST)

1. Case policy exists, is schema-valid, and is sealed before S4 reads data rows; otherwise S4 fails preconditions.
2. Case key + case_id are deterministic and yield unique `case_id` within `(seed, fingerprint)`.
3. Case timeline PK invariants hold: `(seed, fingerprint, case_id, case_event_seq)` unique; `case_event_seq` contiguous & monotone.
4. Any flow marked “in a case” in bank view appears in ≥1 case timeline row linking it to a case.
5. Case events follow the state machine (no close-before-open, no duplicate opens unless policy allows it).
6. Case timeline timestamps are non-decreasing and consistent with flow-level timestamps/delay models; violations FAIL case scope.

---
