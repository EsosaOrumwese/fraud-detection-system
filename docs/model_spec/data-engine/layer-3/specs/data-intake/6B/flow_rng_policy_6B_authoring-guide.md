# Authoring Guide — `flow_rng_policy_6B` (S2 RNG families, budgets & keying, v1)

## 0) Purpose

`flow_rng_policy_6B` is the **required RNG contract** for **6B.S2**. It defines:

* the **only RNG families** S2 is allowed to consume,
* the **fixed `draws` / `blocks` budgets** per decision type (deterministic by domain size, never by outcomes),
* the **keying scheme** (substream ids) so S2 is reproducible and auditable,
* the **event-emission obligations** that let S5 reconcile actual RNG logs against expected counts.

S2 explicitly names these S2 families as the “friendly names” used for:

* flow shape (`rng_event_flow_shape`)
* event timing (`rng_event_event_timing`)
* amount/currency (`rng_event_amount_draw`)

If this policy is missing/invalid, S2 must fail with `S2_PRECONDITION_RNG_POLICY_INVALID` and must not run.

---

## 1) Contract identity (MUST)

From your 6B contracts:

* **dataset_id:** `flow_rng_policy_6B`
* **manifest_key:** `mlr.6B.policy.flow_rng_policy`
* **path:** `config/layer3/6B/flow_rng_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/flow_rng_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S2`

Token-less posture:

* No timestamps, UUIDs, or in-file digests.
* S0 sealing records `sha256_hex` in `sealed_inputs_6B`.

---

## 2) Dependencies (MUST)

This policy is evaluated under S0 sealing and used by S2.

Required dependencies:

* `rng_profile_layer3` (engine token, open-interval law, `blocks = ceil(draws/2)` law, key derivation)
* `flow_shape_policy_6B`, `amount_model_6B`, `timing_policy_6B` (they may reference families by name; they must not introduce new families)

Hard rule:

* `run_id` is **log-only** and MUST NOT participate in substream keying.

---

## 3) Family inventory (MUST match S2)

v1 defines **exactly these three S2 families**:

1. `rng_event_flow_shape`
2. `rng_event_event_timing`
3. `rng_event_amount_draw`

S2 MUST NOT consume RNG from any family not listed here.

---

## 4) Deterministic budget law (MUST)

S2 requires “deterministic budgets per decision” and forbids outcome-dependent draw counts.

### 4.1 General rule

* A **decision locus** is a single semantic “coin flip / draw” that can be inferred from domain size:

  * e.g., one “flows-per-session draw” per session when the policy is stochastic,
  * one “flow-type draw” per flow when the type distribution is non-degenerate,
  * one “timing draw” per event slot,
  * one “amount draw” per event slot.

* Each locus emits an RNG event:

  * **consuming** when randomness is needed, or
  * **non-consuming** (`draws="0", blocks=0`) when deterministic.

### 4.2 `blocks` vs `draws`

* `draws` is a decimal u128 string.
* `blocks` must be consistent with `rng_profile_layer3`’s `ceil(draws/2)` law.

---

## 5) Budgets per family (v1)

### 5.1 `rng_event_flow_shape`

Used for:

* `N_flows(session)` when stochastic (1 draw per session)
* flow type selection (1 draw per flow)
* optional stochastic branches (refund/step-up/etc.) (1 draw per branch locus)
* optional stochastic arrival→flow assignment (1 draw per arrival needing stochastic assignment)

Budgets:

* consuming: `draws="1"`, `blocks=1`
* non-consuming: `draws="0"`, `blocks=0`

### 5.2 `rng_event_event_timing`

S2 uses this to sample **event time offsets** with key `(seed, fingerprint, scenario_id, flow_id, event_index)`.

**v1 emission rule:** emit exactly one timing RNG event **per event slot** in the final event template:

* consuming if the timing policy requires a draw for that slot
* non-consuming otherwise

Budgets:

* consuming: `draws="1"`, `blocks=1`
* non-consuming: `draws="0"`, `blocks=0`

### 5.3 `rng_event_amount_draw`

S2 uses this for **amounts and currencies**, keyed by `(seed, fingerprint, scenario_id, flow_id)` and **event index where relevant**.

**v1 emission rule:** emit exactly one amount RNG event **per event slot** in the final event template:

* consuming if the event slot is amount-bearing under `amount_model_6B`
* non-consuming otherwise

**v1 fixed sample budget for consuming amount slots:**

* consuming: `draws="2"`, `blocks=1`
* non-consuming: `draws="0"`, `blocks=0`

Why `2` draws:

* amount_model can use `(u0,u1)` to cover:

  * currency selection (or “cross-currency off” case),
  * mixture branch / point-mass selection,
  * continuous tail sampling,
    by deterministic splitting/remapping (no extra draws), keeping S2 budgets audit-friendly.

---

## 6) Keying scheme (MUST; no run_id)

S2 must key RNG substreams deterministically by stable ids, and the S2 spec gives canonical key shapes.

### 6.1 Common identity axes (MUST include)

All families MUST key by:

* `seed`
* `manifest_fingerprint`
* `scenario_id`

Recommended additional axis (allowed):

* `parameter_hash` (to avoid collisions across parameter bundles)

### 6.2 Decision-specific ids (MUST)

**`rng_event_flow_shape`**

* `FLOWS_PER_SESSION`: add `session_id`
* `FLOW_TYPE`: add `flow_id`
* `BRANCH_DECISION`: add `flow_id`, `branch_id`, and (if multiple branch slots) `branch_slot_index`
* `ARRIVAL_FLOW_ASSIGNMENT`: add `session_id`, `arrival_seq` (and optionally `arrival_index_in_session`)

**`rng_event_event_timing`**

* add `flow_id`, `event_index`

**`rng_event_amount_draw`**

* add `flow_id`, `event_index` (event index “where relevant”)

### 6.3 Event index convention (MUST)

* `event_index` MUST be **0-based within the flow template**, even if the stored `event_seq` is 1-based.

  * If schema uses 1-based `event_seq`, then `event_index = event_seq - 1`.

This pins stable keying independent of schema indexing.

---

## 7) Sampling primitives contract (MUST; fixed-draw, no rejection loops)

To enforce deterministic budgets, v1 pins these constraints:

### 7.1 Discrete selection (flow counts, flow types, branches)

* Exactly **1** uniform per discrete choice (CDF selection).
* If distribution is a singleton (prob=1), emit non-consuming envelope.

### 7.2 Timing offsets

* Exactly **1** uniform per event slot when timing draw is enabled.
* Must use an **inverse-CDF / direct map** sampler (no rejection sampling loops).

### 7.3 Amounts/currency

* Exactly **2** uniforms per amount-bearing event slot.
* All amount/currency decisions for that event must be implementable from those two uniforms via deterministic splitting/remapping.
* No extra per-event “helper draws” are allowed.

This is exactly what S2 means by “draw counts implied by domain size, not outcomes.”

---

## 8) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be 1)
2. `policy_id` (string; MUST be `flow_rng_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `rng_profile_ref` (object)
5. `families` (list)
6. `keying` (object)
7. `sampling_primitives` (object)
8. `emission_rules` (object)
9. `guardrails` (object)
10. `notes` *(optional)*

Unknown keys ⇒ INVALID.

---

## 9) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: flow_rng_policy_6B
policy_version: v1

rng_profile_ref:
  policy_id: rng_profile_layer3
  required: true

families:
  - family_id: rng_event_flow_shape
    decisions:
      - decision_id: FLOWS_PER_SESSION
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, session_id]
      - decision_id: FLOW_TYPE
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id]
      - decision_id: BRANCH_DECISION
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, branch_id, branch_slot_index]
      - decision_id: ARRIVAL_FLOW_ASSIGNMENT
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, session_id, arrival_seq]

  - family_id: rng_event_event_timing
    per_event_slot:
      budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
      key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, event_index]
      event_index_base: 0
      emit_event_every_event_slot: true

  - family_id: rng_event_amount_draw
    per_event_slot:
      budgets: { consuming: { draws: "2", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
      key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, event_index]
      event_index_base: 0
      emit_event_every_event_slot: true
      max_consuming_events_per_flow_event_slot: 1

keying:
  forbid_run_id_in_key: true
  decision_id_field: decision_id
  event_index_field: event_index

sampling_primitives:
  discrete_choice_draws: "1"
  timing_offset_draws_per_event_slot: "1"
  amount_draws_per_amount_bearing_event_slot: "2"
  forbid_rejection_sampling: true

emission_rules:
  require_non_consuming_envelopes_when_deterministic: true
  forbid_data_dependent_family_selection: true
  forbid_data_dependent_budget_variation: true

guardrails:
  forbid_unknown_families: true
  forbid_variable_budgets: true
```

---

## 10) Acceptance checklist (MUST)

1. **Contract pins** match dictionary/registry (`mlr.6B.policy.flow_rng_policy`, correct path/schema_ref).
2. Families include at least the S2 families named in the S2 spec (`rng_event_flow_shape`, `rng_event_event_timing`, `rng_event_amount_draw`).
3. Budgets are fixed per decision type and consistent with `rng_profile_layer3` budget law.
4. Keying matches S2 required shapes (session_id for flow-count; flow_id for flow-type; flow_id+event_index for timing and amount).
5. `run_id` not in keying; outcome-dependent budgets forbidden.
6. If this policy is missing/invalid, S2 must fail preconditions (`S2_PRECONDITION_RNG_POLICY_INVALID`).

---

## Non-toy/realism guardrails (MUST)

- Only the three S2 families are allowed; any extra family is invalid.
- Budgets must be fixed (`draws` 0 or 1); no variable-draw algorithms or rejection loops.
- `blocks` must follow `ceil(draws/2)` and keying must exclude `run_id`.
- Every stochastic locus must emit exactly one event (consuming) or a non-consuming envelope.

