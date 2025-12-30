# Authoring Guide — `fraud_overlay_policy_6B` (S3 permitted tactics & mutation constraints, v1)

## 0) Purpose

`fraud_overlay_policy_6B` is the **sealed authority** that defines **how S3 mutates baseline flows/events** (from S2) into “with-fraud” flows/events.

It defines:

* the closed **tactic vocabulary** (what kinds of mutations exist),
* which tactics are allowed for which **campaign types**,
* how a tactic mutates flows/events (amount shifts, routing anomalies, device/IP swaps, inserts/suppressions),
* constraints and guardrails (fail-closed posture), and
* provenance fields so S4 can later label truth and S5 can validate correctness.

S3 must never mutate baseline outputs in place: it must emit separate “with fraud” surfaces.

---

## 1) Contract identity (MUST)

Your 6B contracts require this as a sealed policy consumed by S0 and S3.

* **dataset_id:** `fraud_overlay_policy_6B`
* **manifest_key:** `mlr.6B.policy.fraud_overlay_policy`
* **path:** `config/layer3/6B/fraud_overlay_policy_6B.yaml` 
* **schema_ref:** `schemas.6B.yaml#/policy/fraud_overlay_policy_6B` 
* **consumed_by:** `6B.S0`, `6B.S3` 

Token-less posture:

* no timestamps, UUIDs, or in-file digests; S0 sealing records `sha256_hex` in `sealed_inputs_6B`.

---

## 2) Dependencies (MUST)

This policy is evaluated in S3 and must align with:

* `fraud_campaign_catalogue_config_6B` (campaign types and target domains)
* `flow_shape_policy_6B` (baseline flow types + event templates)
* `amount_model_6B` and `timing_policy_6B` (mutation constraints cannot violate basic amount/time invariants; if tactics change those, they must specify how)
* `fraud_rng_policy_6B` (RNG families/budgets for mutation decisions; referenced here but defined there)

Hard rule:

* Overlay tactics must be **deterministic in semantics**: all stochasticity is via `fraud_rng_policy_6B` families. 

---

## 3) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be 1)
2. `policy_id` (string; MUST be `fraud_overlay_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `vocabulary` (object)
5. `tactics` (list of objects)
6. `campaign_to_tactics` (list of objects)
7. `mutation_rules` (object)
8. `constraints` (object)
9. `provenance` (object)
10. `guardrails` (object)
11. `realism_targets` (object)
12. `notes` (optional)

Unknown keys ⇒ INVALID (fail-closed).

Token-less:

* no timestamps/digests/UUIDs
* no YAML anchors/aliases

---

## 4) Vocabulary (MUST)

`vocabulary` MUST define closed enums used throughout:

* `tactic_vocab` (list[str])
* `mutation_axis_vocab` (list[str]): recommended axes:

  * `AMOUNT`, `ROUTING`, `IDENTITY`, `TIMING`, `STRUCTURE`
* `event_type_vocab` (must match S2 event types)
* `flow_type_vocab` (must match S2 flow types)
* `channel_group_vocab` (must match S1/S2)

Optional but recommended:

* `routing_anomaly_vocab` (e.g., `CROSS_BORDER_MISMATCH`, `UNUSUAL_SITE`, `VIRTUAL_EDGE_SHIFT`)
* `identity_swap_vocab` (e.g., `DEVICE_SWAP`, `IP_SWAP`, `INSTRUMENT_SWAP`, `ACCOUNT_SWAP`)

---

## 5) Tactics catalogue (MUST)

Each `tactics[]` entry MUST include:

### Identity

* `tactic_id` (stable token, uppercase snake)
* `axis` (one of mutation_axis_vocab)
* `description` (1–3 sentences)

### Applicability

* `allowed_target_kind` (ENTITY/FLOW/EVENT)
* `allowed_channel_groups` (subset)
* `allowed_flow_types` (subset; empty means “any”)
* `requires` (object of booleans):

  * `instrument_present`, `device_present`, `ip_present`, `merchant_present`
* `forbids` (object) (optional)

### RNG hooks (referential only)

* `rng_decision_points` (list of decision ids) that must be budgeted in `fraud_rng_policy_6B`:

  * e.g., `MUTATION_CHOICE`, `AMOUNT_SHIFT`, `DEVICE_SWAP`, `IP_SWAP`, `STRUCTURE_INSERT`, etc.

### Mutation spec

* `mutation_spec` (object) which is **axis-specific**, see §6.

---

## 6) Mutation specs (axis-specific, v1)

### 6.1 AMOUNT tactics

Allowed operations:

* `MULTIPLY_AMOUNT` with factor distribution (bounded)
* `ADD_FEE` with fee distribution (bounded)
* `SPLIT_AMOUNT` (one flow becomes two flows with partitioned amounts; requires STRUCTURE axis, see below)

Must specify:

* which event_type(s) are mutated (auth/clearing/refund)
* whether sign constraints are preserved
* how to keep cross-event constraints coherent (e.g., if auth changes, clearing changes too unless explicitly decoupled)
* hard caps (max factor, max additive fee)

### 6.2 ROUTING tactics

Allowed operations:

* `SITE_SHIFT` (physical site anomaly)
* `EDGE_SHIFT` (virtual edge anomaly)
* `COUNTRY_SHIFT` (cross-border routing anomaly)
* `CHANNEL_SHIFT` (optional, but can have broad impacts)

Must specify:

* candidate generation rule (deterministic) and how the final choice is made (RNG decision point)
* constraints: cannot route to a non-existent site/edge; must respect 2B/3B routing universe
* whether it changes only “observed location” fields or also “settlement” fields (virtual merchants distinction)

### 6.3 IDENTITY tactics (entity swapping)

Allowed operations:

* `DEVICE_SWAP`
* `IP_SWAP`
* `INSTRUMENT_SWAP`
* `ACCOUNT_SWAP`
* `PARTY_SWAP` (rare; high-impact)

Must specify:

* which fields are swapped
* constraints:

  * swapped entities must be compatible with the flow (e.g., instrument belongs to account unless you intentionally create inconsistency)
  * if creating inconsistency is the point (e.g., stolen card), specify the exact inconsistency allowed and how it is represented
* candidate pools (deterministic) + RNG selection

### 6.4 TIMING tactics

Allowed operations:

* `BURST` (compress inter-event gaps)
* `DELAY` (push event(s) later)
* `SESSION_SPAN` (spread events across longer window)
* `RETRY_ACCELERATION` (reduce retry gap)

Must specify:

* which transitions are mutated
* bounded multipliers/additive offsets
* must preserve monotonicity and remain within scenario horizon unless explicitly allowed.

### 6.5 STRUCTURE tactics

Allowed operations:

* `INSERT_EVENT` (e.g., additional auth attempt)
* `SUPPRESS_EVENT` (e.g., suppress clearing)
* `DUPLICATE_FLOW` (clone with modifications)
* `SPLIT_FLOW` (one flow becomes two related flows)

Must specify:

* which templates can be modified
* insertion positions (by event_type anchor)
* limits (max inserts, max suppressions)
* must preserve schema invariants (event_seq contiguous per flow; no orphan events).

---

## 7) Campaign→tactics mapping (MUST)

`campaign_to_tactics[]` maps `campaign_type` (from campaign catalogue) to allowed tactics and their mixture weights.

Each entry MUST include:

* `campaign_type`
* `allowed_tactics` list of `{tactic_id, weight}`
* `selection_mode`:

  * `NONE` (no tactics; campaign only does targeting)
  * `MIXTURE_V1` (choose one tactic per target)
  * `STACK_V1` (apply multiple tactics in sequence; must specify order and caps)

If `MIXTURE_V1`:

* S3 chooses one tactic per targeted item with one RNG decision (`rng_event_overlay_mutation`), using weights. Budget must be 1 draw.

If `STACK_V1`:

* Must specify:

  * `max_tactics_per_target`
  * deterministic tactic order or another RNG step (but then budgets must be pinned in `fraud_rng_policy_6B`).

---

## 8) Constraints (hard fails)

`constraints` MUST include:

* `fail_on_missing_tactic: true`
* `fail_on_incompatible_target: true`
* `forbid_out_of_universe_routing: true`
* `forbid_schema_invariant_breaks: true`
* `forbid_time_travel: true` (monotone per flow)
* `forbid_amount_sign_violations: true`
* `forbid_unbounded_loops: true` (no iterative mutation loops)

---

## 9) Provenance (MUST)

Overlay must be auditable.

`provenance` MUST define:

* required fields added to with-fraud flows/events, e.g.:

  * `campaign_id`, `template_id`, `campaign_type`
  * `tactic_id`, `mutation_axis`
  * `mutation_rule_id`
  * `mutation_rng_family` and `mutation_decision_id`
* whether baseline ids are preserved (recommended) or a new “overlay id namespace” is used
* whether S3 emits a per-mutation log (optional; contract-dependent)

---

## 10) Guardrails (MUST)

Hard caps:

* `max_targets_total_per_seed_scenario`
* `max_mutations_per_flow`
* `max_new_flows_created_per_seed_scenario` (for structure tactics)
* `max_event_inserts_per_flow`
* `max_event_suppressions_per_flow`
* `max_amount_multiplier`
* `max_time_multiplier`

If a guardrail is exceeded: v1 should FAIL (unless behaviour_config chooses clamp-and-warn explicitly).

---

## 11) Realism targets (MUST)

Corridors that prevent toy overlays and absurd overlays:

* `min_fraction_of_campaigns_with_any_mutation` (if campaigns are enabled)
* `mutation_axis_coverage_min` (at least N axes appear across templates)
* `amount_shift_factor_range` ({min,max}) for amount tactics
* `routing_anomaly_fraction_range` ({min,max})
* `identity_swap_fraction_range` ({min,max})
* `time_anomaly_fraction_range` ({min,max})
* `structure_anomaly_fraction_range` ({min,max})

These are used by S5 validation policy to decide PASS/WARN/FAIL.

---

## 12) Minimal v1 skeleton

```yaml
schema_version: 1
policy_id: fraud_overlay_policy_6B
policy_version: v1

vocabulary:
  tactic_vocab: [AMOUNT_UPSHIFT, DEVICE_SWAP, IP_SWAP, SITE_SHIFT, BURST_TIMING, SUPPRESS_CLEARING]
  mutation_axis_vocab: [AMOUNT, IDENTITY, ROUTING, TIMING, STRUCTURE]
  event_type_vocab: [AUTH_REQUEST, AUTH_RESPONSE, CLEARING, REFUND, REVERSAL]
  flow_type_vocab: [CARD_AUTH_CLEAR, CARD_AUTH_DECLINE, BANK_TRANSFER]
  channel_group_vocab: [ECOM, POS, ATM, BANK_RAIL, HYBRID]
  routing_anomaly_vocab: [UNUSUAL_SITE, CROSS_BORDER_MISMATCH, VIRTUAL_EDGE_SHIFT]
  identity_swap_vocab: [DEVICE_SWAP, IP_SWAP, INSTRUMENT_SWAP, ACCOUNT_SWAP]

tactics:
  - tactic_id: AMOUNT_UPSHIFT
    axis: AMOUNT
    description: "Increase attempted and settled amounts by a bounded factor."
    allowed_target_kind: FLOW
    allowed_channel_groups: [ECOM, POS, HYBRID]
    allowed_flow_types: [CARD_AUTH_CLEAR]
    requires: { instrument_present: true, device_present: true, ip_present: true, merchant_present: true }
    rng_decision_points: [MUTATION_CHOICE, AMOUNT_SHIFT]
    mutation_spec:
      op: MULTIPLY_AMOUNT
      apply_to_event_types: [AUTH_REQUEST, CLEARING]
      factor:
        dist_id: LOGNORMAL_V1
        mu_log: 0.10
        sigma_log: 0.25
        clip: { min: 1.05, max: 3.00 }

  - tactic_id: IP_SWAP
    axis: IDENTITY
    description: "Swap the observed IP to an anonymizer-like IP for targeted flows."
    allowed_target_kind: FLOW
    allowed_channel_groups: [ECOM, POS, HYBRID]
    allowed_flow_types: []
    requires: { instrument_present: true, device_present: true, ip_present: true, merchant_present: true }
    rng_decision_points: [MUTATION_CHOICE, IP_SWAP]
    mutation_spec:
      op: IP_SWAP
      candidate_pool: ANONYMIZER_PROXY
      preserve_device: true

campaign_to_tactics:
  - campaign_type: CARD_TESTING
    selection_mode: MIXTURE_V1
    allowed_tactics:
      - { tactic_id: IP_SWAP, weight: 0.60 }
      - { tactic_id: AMOUNT_UPSHIFT, weight: 0.40 }

mutation_rules:
  axis_defaults:
    AMOUNT:
      rng_family: rng_event_overlay_mutation
    IDENTITY:
      rng_family: rng_event_overlay_mutation
    ROUTING:
      rng_family: rng_event_overlay_mutation
    TIMING:
      rng_family: rng_event_overlay_mutation
    STRUCTURE:
      rng_family: rng_event_overlay_mutation

constraints:
  fail_on_missing_tactic: true
  fail_on_incompatible_target: true
  forbid_out_of_universe_routing: true
  forbid_schema_invariant_breaks: true
  forbid_time_travel: true
  forbid_amount_sign_violations: true
  forbid_unbounded_loops: true

provenance:
  require_campaign_id: true
  require_tactic_id: true
  require_mutation_rule_id: true
  require_rng_family_and_decision_id: true

guardrails:
  max_targets_total_per_seed_scenario: 200000
  max_mutations_per_flow: 2
  max_new_flows_created_per_seed_scenario: 20000
  max_event_inserts_per_flow: 2
  max_event_suppressions_per_flow: 1
  max_amount_multiplier: 5.0
  max_time_multiplier: 10.0

realism_targets:
  mutation_axis_coverage_min: 3
  amount_shift_factor_range: { min: 1.05, max: 4.0 }
  routing_anomaly_fraction_range: { min: 0.0005, max: 0.05 }
  identity_swap_fraction_range: { min: 0.0005, max: 0.05 }
  time_anomaly_fraction_range: { min: 0.0005, max: 0.05 }
  structure_anomaly_fraction_range: { min: 0.0001, max: 0.02 }
```

---

## 13) Acceptance checklist (MUST)

1. Contract pins match (path + schema_ref + manifest_key).
2. Every campaign_type referenced exists in the campaign catalogue config.
3. Every tactic_id referenced exists in `tactics[]`.
4. All RNG decision points are budgeted in `fraud_rng_policy_6B` families; this policy must not invent new families.
5. Constraints/guardrails prevent out-of-universe routing, schema breaks, negative-time, unbounded loops.
6. Realism corridors are non-degenerate and satisfiable.

---
