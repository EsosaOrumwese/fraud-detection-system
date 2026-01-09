# Authoring Guide — `rng_policy_6B` (6B.S1 RNG families & budgets, v1)

## 0) Purpose

`rng_policy_6B` is the **S1 RNG contract**: it defines the **only** RNG event families S1 may use (and their **fixed per-event budgets**) for:

* sampling **entity attachments** for arrivals
* optional **stochastic session boundary** decisions

S1 is required to restrict itself to a small, fixed set of families (explicitly named in the S1 expanded spec), and S5 later validates actual RNG logs against the expectations implied by this policy.

---

## 1) File identity (MUST)

Mirror the conventions used by your other authoring guides (token-less YAML in `config/...`):

* **Path:** `config/layer3/6B/rng_policy_6B.yaml`
* **Schema anchor:** `schemas.6B.yaml#/policy/rng_policy_6B`
* **Sealing:** 6B.S0 MUST list this file in `sealed_inputs_6B` with an appropriate role and `sha256_hex` (token-less file; digest comes from sealing, not in-file).

Recommended `sealed_inputs_6B` role metadata:

* `role: RNG_POLICY_6B_S1`
* `status: REQUIRED`
* `read_scope: ROW_LEVEL`

---

## 2) Dependency (MUST)

This policy MUST reference the layer-wide RNG law:

* `rng_profile_layer3` is the authority for:

  * Philox engine token
  * open-interval `u∈(0,1)` mapping
  * “draws/blocks” accounting law
  * substream key derivation (order-invariant)

S1 MUST fail closed if `rng_profile_layer3` is missing or digest-mismatched.

---

## 3) RNG families reserved for S1 (MUST)

The S1 spec explicitly reserves (at least) these families for S1: 

* `rng_event_entity_attach`
* `rng_event_session_boundary`

**Rule:** S1 MUST NOT use any RNG family not listed in this policy.

---

## 4) Budgets (MUST be fixed per event)

To keep auditing and S5 validation deterministic, budgets are pinned **per emitted RNG event**, not “per run”.

### 4.1 `rng_event_entity_attach` (single-uniform)

* **draws:** `"1"`
* **blocks:** `1`

Meaning: one `U(0,1)` open-interval uniform (lane x0) used to make exactly **one** stochastic attachment choice.

### 4.2 `rng_event_session_boundary` (single-uniform)

* **draws:** `"1"`
* **blocks:** `1`

Meaning: one `U(0,1)` used for session-boundary stochasticity (only if enabled).

### 4.3 Deterministic decisions (non-consuming envelopes allowed)

When the decision is deterministic (e.g., candidate set size is 0/1, or policy disables the stochastic branch), S1 MUST NOT advance the counter. The policy MUST allow emitting a **non-consuming event envelope** with:

* `draws: "0"`
* `blocks: 0`
* `before_counter == after_counter`

S1 spec allows deterministic (non-consuming) envelopes for auditability. 

---

## 5) When events are emitted (binding emission rules)

This is what makes S5 able to compute expected event/draw counts from domain sizes + policy. 

### 5.1 Attachment steps (fixed order)

For each arrival row, S1 MUST process attachment steps in **this exact order**:

1. `ATTACH_PARTY`
2. `ATTACH_ACCOUNT`
3. `ATTACH_INSTRUMENT`
4. `ATTACH_DEVICE`
5. `ATTACH_IP`

For each step:

* If the candidate set size ≤ 1, emit `rng_event_entity_attach` as **non-consuming** (`draws="0"`).
* Else, emit `rng_event_entity_attach` as **consuming** (`draws="1"`), and use the resulting `u` to choose exactly one candidate.

### 5.2 Session boundary (optional)

If `sessionisation_policy_6B` enables stochastic boundary posture:

* Evaluate the deterministic boundary predicate first (gap threshold, etc.).
* Only when the predicate leaves ambiguity (as defined by `sessionisation_policy_6B`) emit `rng_event_session_boundary` (consuming `"1"`), else emit non-consuming `"0"`.

---

## 6) Substream keying (MUST)

S1 is allowed to parameterise substream keys by stable identifiers (seed/fingerprint/scenario/arrival keys) but MUST NOT use **data-dependent family selection** or **data-dependent budgets**. 

### 6.1 Hard rule

* **`run_id` MUST NOT participate in substream keying.**
  (`run_id` may appear in logs for traceability only.)

### 6.2 Required substream id tuple

Each RNG event MUST define its substream ids as:

Common prefix:

* `manifest_fingerprint`
* `seed`
* `scenario_id`

Arrival identity (from `arrival_events_5B`):

* `merchant_id`
* `zone_representation`
* `bucket_index`
* `arrival_seq`

Step discriminator:

* `attachment_step` (enum string for entity_attach)
* `boundary_step` (enum string for session_boundary, if you have more than one kind)

This ensures:

* per-arrival determinism
* no collisions across attachment steps
* stable expected counts

---

## 7) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `policy_id` (MUST be `rng_policy_6B`)
2. `version` (e.g., `v1.0.0`)
3. `scope` (object)
4. `rng_profile_ref` (object)
5. `families` (list)
6. `emission_rules` (object)
7. `keying` (object)
8. `guardrails` (object)
9. `notes` *(optional)*

Unknown keys: **INVALID**.

---

## 8) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
policy_id: rng_policy_6B
version: v1.0.0

scope:
  segment: 6B
  state: S1
  description: "S1 RNG families & budgets (entity attachment + optional stochastic session boundaries)."

rng_profile_ref:
  policy_id: rng_profile_layer3
  required: true

families:
  - family_id: rng_event_entity_attach
    purpose: "One stochastic attachment choice for a single arrival attachment step."
    budgets:
      consuming: { draws: "1", blocks: 1 }
      non_consuming: { draws: "0", blocks: 0 }
    step_enum:
      - ATTACH_PARTY
      - ATTACH_ACCOUNT
      - ATTACH_INSTRUMENT
      - ATTACH_DEVICE
      - ATTACH_IP

  - family_id: rng_event_session_boundary
    purpose: "Optional stochastic boundary decision during sessionisation."
    budgets:
      consuming: { draws: "1", blocks: 1 }
      non_consuming: { draws: "0", blocks: 0 }
    step_enum:
      - BOUNDARY_AMBIGUITY

emission_rules:
  attachment_steps_order:
    - ATTACH_PARTY
    - ATTACH_ACCOUNT
    - ATTACH_INSTRUMENT
    - ATTACH_DEVICE
    - ATTACH_IP

  entity_attach:
    emit_event_every_step: true
    consume_if_candidate_count_gt: 1
    deterministic_if_candidate_count_le: 1

  session_boundary:
    enabled_by_sessionisation_policy: true
    emit_event_on_ambiguity_only: true
    consume_if_ambiguity: true

keying:
  forbid_run_id_in_key: true

  common_ids:
    - manifest_fingerprint
    - seed
    - scenario_id

  arrival_ids:
    - merchant_id
    - zone_representation
    - bucket_index
    - arrival_seq

  step_id_field:
    rng_event_entity_attach: attachment_step
    rng_event_session_boundary: boundary_step

guardrails:
  forbid_unknown_families: true
  forbid_variable_budgets: true
  forbid_lane_reuse_across_events: true
  require_open_interval_u01: true
```

---

## 9) Acceptance checklist (MUST)

1. YAML parses; keys exactly as §7; token-less; no YAML anchors/aliases.
2. `families` contains **only** the S1-reserved families (at least the two named in the S1 spec). 
3. Budgets are fixed per event: consuming is `"1"/1`, non-consuming is `"0"/0.
4. `emission_rules.attachment_steps_order` is fixed and complete (5 steps).
5. Keying excludes `run_id`.
6. S5 can compute expected counts from this policy + domain sizes, and compare against RNG logs as described in S5. 

---

## Non-toy/realism guardrails (MUST)

- Only the two S1 families are allowed; any extra family is invalid.
- Budgets are fixed (`draws` 0/1); no variable-draw algorithms.
- Non-consuming envelopes are required when candidate sets are size 0/1.
- Keying must exclude `run_id` and follow the policy basis.

