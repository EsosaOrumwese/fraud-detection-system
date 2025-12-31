# Authoring Guide — `flow_shape_policy_6B` (S2 baseline flow structure, v1)

## 0) Purpose

`flow_shape_policy_6B` is the **single authority** for how **6B.S2** turns S1 sessions/arrivals into **baseline, all-legit flows** and **baseline event templates**.

S2 uses this policy to:

* decide **how many flows** exist per session (`N_flows(s)`), deterministically or via RNG,
* decide **how arrivals map to flows** (one-flow, arrival-per-flow, or multi-flow),
* choose a **flow type** (auth→clear, decline, refund patterns, step-up patterns, etc.) and the corresponding **event sequence template**,
* ensure the baseline constraints hold: **no orphan flows/events**, and event ordering is unambiguous.

This policy does **not** set amounts or timestamps; those are controlled by `amount_model_6B` and `timing_policy_6B`.

---

## 1) Contract identity (MUST)

From your 6B contracts:

* **dataset_id:** `flow_shape_policy_6B` (status: required)
* **manifest_key:** `mlr.6B.policy.flow_shape_policy`
* **path:** `config/layer3/6B/flow_shape_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/flow_shape_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S2`

Token-less posture:

* no timestamps, UUIDs, or digests in-file (digest is recorded by S0 sealing).

---

## 2) Dependencies (MUST)

S2 evaluates this policy per `(seed, manifest_fingerprint, scenario_id)` and must only read inputs sealed in `sealed_inputs_6B`.

This policy is authored assuming the existence of:

* `sessionisation_policy_6B` + `attachment_policy_6B` outputs (`s1_session_index_6B`, `s1_arrival_entities_6B`)
* `flow_rng_policy_6B` (budgets + family contracts for S2 RNG; referenced but not defined here)

Hard rule:

* This policy may **name** RNG decision points and required family IDs, but **budget semantics live in `flow_rng_policy_6B`**.

---

## 3) Authority boundaries (MUST)

S2 MUST:

* not change S1 attachments or session membership; S1 remains the authority for `*_id` and `session_id`.
* not create/delete arrivals; 5B remains the authority for arrivals/timestamps/routing keys.
* produce only the two S2 datasets (flow anchor + event stream).

---

## 4) What this policy must fully specify

### 4.1 Session → flow planning

* the rule for **`N_flows(s)`** (deterministic or stochastic)
* the rule for mapping arrivals in session `s` into those flows (including multi-flow logic)
* whether **empty sessions** are allowed (default: not allowed; `N_flows(s) ≥ 1` unless explicitly permitted)

### 4.2 Flow type selection

* the **catalog** of flow archetypes (flow types)
* conditional availability by context (channel_group, merchant, etc.)
* deterministic vs stochastic selection (stochastic uses `rng_event_flow_shape`)

### 4.3 Event sequence templates

* for each flow type: a base event template (e.g. `[AUTH_REQUEST, AUTH_RESPONSE, CLEARING]`)
* any conditional branches (step-up, retries, refunds, reversals) and the decision point name(s) that control them (RNG family is referenced, budget elsewhere)

### 4.4 Invariants enforced by S2 and later by S5

* Every flow has ≥1 event; every event references exactly one flow; no orphans.
* `event_seq` is strictly ordered and contiguous per `(flow_id)` as the schema specifies.

---

## 5) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `flow_shape_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `flow_count_model` (object)
6. `arrival_to_flow_model` (object)
7. `flow_type_catalog` (object)
8. `flow_type_selection` (object)
9. `event_templates` (object)
10. `branching` (object)
11. `provenance_fields` (object)
12. `guardrails` (object)
13. `realism_targets` (object)
14. `notes` (optional string)

Unknown keys ⇒ **INVALID**.

Token-less:

* no timestamps/digests/UUIDs in-file
* no YAML anchors/aliases

---

## 6) Section semantics (v1 pinned)

### 6.1 `bindings`

MUST include:

* `rng_family_ids_used` (list of family ids that S2 will call when stochastic; budget in flow_rng_policy_6B)

  * v1 minimum: `rng_event_flow_shape`
* `channel_groups` (allowed set; must match what S1 carries forward)
* `event_type_vocab` (closed set of event_type strings used in templates)

### 6.2 `flow_count_model`

Defines `N_flows(s)`.

Required fields:

* `mode` ∈ `{ one_flow_per_session, one_flow_per_arrival, stochastic_discrete_v1 }`
* if `stochastic_discrete_v1`:

  * `support` (list of ints ≥0; e.g. `[1,2,3,4]`)
  * `prob` (same length; sums to 1)
  * `rng_family: rng_event_flow_shape`
  * `keying_ids: [seed, manifest_fingerprint, scenario_id, session_id]` (no run_id)
* `allow_empty_sessions` (bool; default false)
* `empty_session_predicate` (required if allow_empty_sessions=true; deterministic predicate on session features)

S2 must treat “singleton support” as deterministic (no RNG consumed).

### 6.3 `arrival_to_flow_model`

Defines how arrivals map into flows given `N_flows(s)`.

Required:

* `mode` ∈ `{ all_arrivals_one_flow, arrival_per_flow, multi_flow_orders_v1 }`

If `multi_flow_orders_v1`, required:

* `max_flows_per_session` (int ≥ 1)
* `order_key_fields` (list of arrival/session fields used deterministically to cluster)
* `tie_break_order` (explicit stable ordering for arrivals and flows)
* optional `stochastic_assignment`:

  * `enabled` (bool)
  * if enabled: `rng_family: rng_event_flow_shape` and keying ids pinned

Assignment must be deterministic given inputs + RNG draws, and recorded in the flow anchor (via provenance fields).

### 6.4 `flow_type_catalog`

Defines a closed list of flow types and their high-level meaning.

Required fields:

* `flow_types`: list of objects, each with:

  * `flow_type_id` (stable token)
  * `description`
  * `channel_groups_allowed` (subset)
  * `baseline_outcome_class` (e.g., `AUTH_SETTLED`, `AUTH_DECLINED`, `AUTH_SETTLED_REFUNDED`)
  * `requires_instrument` (bool)
  * `allows_refund` (bool)
  * `allows_step_up` (bool)
  * `max_retry_count` (int ≥ 0)

### 6.5 `flow_type_selection`

Defines how S2 chooses a flow type for each flow.

Required:

* `mode` ∈ `{ by_channel_group_v1 }`
* `pi_flow_type_by_channel_group`: mapping channel_group → list of `{flow_type_id, prob}` summing to 1
* `deterministic_if_singleton: true`
* `rng_family: rng_event_flow_shape`
* `keying_ids: [seed, manifest_fingerprint, scenario_id, flow_id]` (no run_id)

### 6.6 `event_templates`

Defines per-flow-type base templates.

Required:

* `template_base_index` (enum: `0_based` or `1_based`; must match schema convention)
* `templates_by_flow_type`: mapping flow_type_id → list of event_type tokens (in order)
* rule: each template must be non-empty (≥1 event).

### 6.7 `branching`

Defines optional branches that can extend templates (step-up, retries, refunds).

Required:

* `retry_branch` (object)
* `step_up_branch` (object)
* `refund_branch` (object)
* `reversal_branch` (object)

Each branch object MUST include:

* `enabled` (bool)
* `applicable_flow_types` (list of flow_type_id)
* `insertion_rule` (where to insert event(s) in base template)
* `decision`:

  * `mode` ∈ `{ deterministic, bernoulli_v1 }`
  * if bernoulli: `p` in [0,1], `rng_family: rng_event_flow_shape` or another family listed in bindings
* `max_insertions` (int ≥ 0)

Branch decisions must be deterministic if `p ∈ {0,1}` (no RNG).

### 6.8 `provenance_fields`

Defines what S2 records in anchors/events to make auditing possible.

Required:

* `flow_plan_rule_id_enabled` (bool)
* `flow_type_id_enabled` (bool)
* `arrival_assignment_rule_id_enabled` (bool)
* `branch_trace_enabled` (bool) (records which branches fired)

S2 spec requires that mapping/choices are recordable in the flow anchor fields.

### 6.9 `guardrails`

Hard caps to prevent runaway structure (fail closed if violated):

* `max_flows_per_session` (int)
* `max_events_per_flow` (int)
* `max_retry_count_global` (int)

### 6.10 `realism_targets`

Corridors that reject toy policies:

* `min_fraction_declines` ({min,max}) by channel_group
* `min_fraction_refunds` ({min,max}) where refunds enabled
* `min_fraction_multi_flow_sessions` ({min,max}) if multi-flow enabled
* `max_single_flow_type_share_cap` (float)
* `event_template_diversity_min` (int; number of distinct templates that must appear in non-zero probability mass)

---

## 7) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: flow_shape_policy_6B
policy_version: v1

bindings:
  rng_family_ids_used: [rng_event_flow_shape]
  channel_groups: [ECOM, POS, ATM, BANK_RAIL, HYBRID]
  event_type_vocab:
    - AUTH_REQUEST
    - AUTH_RESPONSE
    - STEP_UP_CHALLENGE
    - STEP_UP_COMPLETE
    - CLEARING
    - REFUND
    - REVERSAL

flow_count_model:
  mode: stochastic_discrete_v1
  support: [1, 2, 3, 4]
  prob:    [0.78, 0.16, 0.05, 0.01]
  rng_family: rng_event_flow_shape
  keying_ids: [seed, manifest_fingerprint, scenario_id, session_id]
  allow_empty_sessions: false

arrival_to_flow_model:
  mode: multi_flow_orders_v1
  max_flows_per_session: 6
  order_key_fields: [merchant_id]      # simple v1: split by merchant within session
  tie_break_order:
    arrivals: [ts_utc, merchant_id, arrival_seq]
    flows: [flow_index_within_session]
  stochastic_assignment:
    enabled: false

flow_type_catalog:
  flow_types:
    - flow_type_id: CARD_AUTH_CLEAR
      description: "Auth approved then cleared."
      channel_groups_allowed: [ECOM, POS, ATM, HYBRID]
      baseline_outcome_class: AUTH_SETTLED
      requires_instrument: true
      allows_refund: true
      allows_step_up: true
      max_retry_count: 1

    - flow_type_id: CARD_AUTH_DECLINE
      description: "Auth declined, no clearing."
      channel_groups_allowed: [ECOM, POS, ATM, HYBRID]
      baseline_outcome_class: AUTH_DECLINED
      requires_instrument: true
      allows_refund: false
      allows_step_up: false
      max_retry_count: 1

    - flow_type_id: CARD_AUTH_RETRY_SUCCESS_CLEAR
      description: "Auth retry then approved then cleared."
      channel_groups_allowed: [ECOM, POS, HYBRID]
      baseline_outcome_class: AUTH_SETTLED
      requires_instrument: true
      allows_refund: true
      allows_step_up: true
      max_retry_count: 2

    - flow_type_id: BANK_TRANSFER
      description: "Bank-rail transfer flow (no card instrument required)."
      channel_groups_allowed: [BANK_RAIL]
      baseline_outcome_class: TRANSFER_COMPLETED
      requires_instrument: false
      allows_refund: false
      allows_step_up: false
      max_retry_count: 0

flow_type_selection:
  mode: by_channel_group_v1
  deterministic_if_singleton: true
  rng_family: rng_event_flow_shape
  keying_ids: [seed, manifest_fingerprint, scenario_id, flow_id]
  pi_flow_type_by_channel_group:
    ECOM:
      - { flow_type_id: CARD_AUTH_CLEAR, prob: 0.86 }
      - { flow_type_id: CARD_AUTH_DECLINE, prob: 0.10 }
      - { flow_type_id: CARD_AUTH_RETRY_SUCCESS_CLEAR, prob: 0.04 }
    POS:
      - { flow_type_id: CARD_AUTH_CLEAR, prob: 0.90 }
      - { flow_type_id: CARD_AUTH_DECLINE, prob: 0.08 }
      - { flow_type_id: CARD_AUTH_RETRY_SUCCESS_CLEAR, prob: 0.02 }
    ATM:
      - { flow_type_id: CARD_AUTH_CLEAR, prob: 0.93 }
      - { flow_type_id: CARD_AUTH_DECLINE, prob: 0.07 }
    BANK_RAIL:
      - { flow_type_id: BANK_TRANSFER, prob: 1.0 }
    HYBRID:
      - { flow_type_id: CARD_AUTH_CLEAR, prob: 0.88 }
      - { flow_type_id: CARD_AUTH_DECLINE, prob: 0.09 }
      - { flow_type_id: CARD_AUTH_RETRY_SUCCESS_CLEAR, prob: 0.03 }

event_templates:
  template_base_index: 0_based
  templates_by_flow_type:
    CARD_AUTH_CLEAR: [AUTH_REQUEST, AUTH_RESPONSE, CLEARING]
    CARD_AUTH_DECLINE: [AUTH_REQUEST, AUTH_RESPONSE]
    CARD_AUTH_RETRY_SUCCESS_CLEAR: [AUTH_REQUEST, AUTH_RESPONSE, AUTH_REQUEST, AUTH_RESPONSE, CLEARING]
    BANK_TRANSFER: [AUTH_REQUEST, AUTH_RESPONSE]   # placeholder “transfer init/complete”; refine if you add transfer event types

branching:
  retry_branch:
    enabled: true
    applicable_flow_types: [CARD_AUTH_RETRY_SUCCESS_CLEAR]
    insertion_rule: "template already includes retry events"
    decision: { mode: deterministic }
    max_insertions: 0

  step_up_branch:
    enabled: true
    applicable_flow_types: [CARD_AUTH_CLEAR, CARD_AUTH_RETRY_SUCCESS_CLEAR]
    insertion_rule: "insert [STEP_UP_CHALLENGE, STEP_UP_COMPLETE] after first AUTH_REQUEST"
    decision: { mode: bernoulli_v1, p: 0.08, rng_family: rng_event_flow_shape }
    max_insertions: 1

  refund_branch:
    enabled: true
    applicable_flow_types: [CARD_AUTH_CLEAR]
    insertion_rule: "append [REFUND]"
    decision: { mode: bernoulli_v1, p: 0.03, rng_family: rng_event_flow_shape }
    max_insertions: 1

  reversal_branch:
    enabled: true
    applicable_flow_types: [CARD_AUTH_CLEAR]
    insertion_rule: "append [REVERSAL]"
    decision: { mode: bernoulli_v1, p: 0.005, rng_family: rng_event_flow_shape }
    max_insertions: 1

provenance_fields:
  flow_plan_rule_id_enabled: true
  flow_type_id_enabled: true
  arrival_assignment_rule_id_enabled: true
  branch_trace_enabled: true

guardrails:
  max_flows_per_session: 20
  max_events_per_flow: 40
  max_retry_count_global: 3

realism_targets:
  max_single_flow_type_share_cap: 0.98
  event_template_diversity_min: 3
  min_fraction_declines:
    ECOM: { min: 0.02, max: 0.25 }
    POS:  { min: 0.01, max: 0.20 }
    ATM:  { min: 0.01, max: 0.25 }
  min_fraction_refunds:
    ECOM: { min: 0.001, max: 0.10 }
    POS:  { min: 0.001, max: 0.10 }
  min_fraction_multi_flow_sessions: { min: 0.02, max: 0.30 }
```

---

## 8) Acceptance checklist (MUST)

1. **Contract pins** match: `mlr.6B.policy.flow_shape_policy`, correct path + schema_ref.
2. **S2 semantics alignment**:

   * policy supports deterministic or stochastic `N_flows(s)` using `flow_shape_policy_6B` as described in S2.
   * policy supports selecting flow type + event template as described.
3. **No toy outcomes**: corridors in `realism_targets` are satisfiable and non-degenerate.
4. **No orphan flows/events** is achievable: every defined flow type has ≥1 event; policies don’t allow generating flows with zero events.
5. **Deterministic if singleton**: if a distribution reduces to a single outcome, S2 must not consume RNG.
6. Token-less, fields-strict, no YAML anchors/aliases.

---

## Placeholder resolution (MUST)

- Replace placeholder flow templates and probabilities with the final v1 templates.
- Replace any example flow types with the actual allowed flow types.

