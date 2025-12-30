# Authoring Guide — `amount_model_6B` (S2 amount + currency model, v1)

## 0) Purpose

`amount_model_6B` is the **required** policy that defines how **6B.S2** assigns:

* **currency** (when a flow permits cross-currency),
* **amounts** for each event in a flow (auth/clearing/refund/reversal/etc.),
* **cross-event relationships** (e.g., clearing equals auth ± small deltas; refunds are negative; partial clearing; chargeback-like amounts are not produced in baseline S2),

in a way that is:

* realistic (heavy-tailed, not uniform),
* deterministic in semantics (all randomness is via `flow_rng_policy_6B`),
* consistent with upstream **merchant currency** reality and 1A/1B/3B merchant virtuality,
* consistent with S2 templates from `flow_shape_policy_6B`.

S2 writes baseline flows/events; fraud overlays (S3) may mutate amounts later, but the baseline must stand on its own.

---

## 1) Contract identity (MUST)

From the 6B contracts:

* **dataset_id:** `amount_model_6B`
* **manifest_key:** `mlr.6B.policy.amount_model`
* **path:** `config/layer3/6B/amount_model_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/amount_model_6B`
* **consumed_by:** `6B.S0`, `6B.S2`

Token-less posture:

* no timestamps/UUIDs/digests in-file; S0 sealing records `sha256_hex`.

---

## 2) Dependencies (MUST)

This policy is applied in S2 and depends on sealed inputs:

* `flow_shape_policy_6B` (event templates and flow_type meaning)
* `flow_rng_policy_6B` (RNG families/budgets for amount sampling)
* merchant currency context from Layer-1 (e.g., `merchant_currency` or equivalent) and 5B arrivals for merchant+site context
* `numeric_policy` (rounding dp, IEEE-754 posture; assumed global)

Hard rules:

* No direct FX rate calls. Cross-currency amounts use deterministic, sealed FX surfaces if enabled (see §6), otherwise are disabled.

---

## 3) Amount model surfaces (what this policy must fully specify)

For each **event_type** that can appear in S2 templates, define:

* a **sign convention** (`+` for charges, `-` for refunds/reversals)
* an **amount family** (`PURCHASE`, `CASH_WITHDRAWAL`, `TRANSFER`, `FEE`, etc.)
* a base distribution for the **primary event amount** (typically auth request amount)
* deterministic relationships for derived event amounts (clearing amount, refund amount, reversal amount)

This policy must define the authoritative mapping:

`(channel_group, flow_type_id, event_type) → amount_rule_id`

so S2 can record provenance and S5 can audit consistency.

---

## 4) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be 1)
2. `policy_id` (string; MUST be `amount_model_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `currency_policy` (object)
6. `amount_families` (object)
7. `event_amount_rules` (object)
8. `cross_event_constraints` (object)
9. `rounding` (object)
10. `guardrails` (object)
11. `realism_targets` (object)
12. `notes` *(optional)*

Unknown keys ⇒ INVALID.

Token-less:

* no timestamps/digests/UUIDs
* no YAML anchors/aliases

---

## 5) Currency policy (MUST)

### 5.1 `currency_policy.mode`

* `MERCHANT_PRIMARY_ONLY` (default v1)
* `MERCHANT_PRIMARY_PLUS_CROSS_CURRENCY` (optional; requires sealed FX surface)

### 5.2 Currency selection (MERCHANT_PRIMARY_ONLY)

* Set `ccy = merchant_primary_ccy` (deterministic)
* If merchant has no primary currency in sealed inputs, fail (`MISSING_MERCHANT_CCY`).

### 5.3 Cross-currency support (optional)

If enabled, policy must define:

* which channel_groups allow cross-currency
* the probability of cross-currency by context
* required FX surface manifest_key/dataset_id
* rounding/fee rules

If FX surface is missing, S2 must fail unless behaviour_config explicitly disables cross-currency.

---

## 6) Amount distributions (MUST be realistic and auditable)

### 6.1 Supported base distributions (v1 pinned set)

Choose from a small, auditable set:

* `LOGNORMAL_V1` (heavy tail; parameters are `mu_log`, `sigma_log`)
* `LOGNORMAL_MIX_V1` (mixture of 2–3 lognormals with fixed weights)
* `GAMMA_V1` (shape/scale)
* `DISCRETE_PRICE_POINTS_V1` (explicit mass at common price points + continuous tail)

Any other distribution id ⇒ invalid.

All sampling uses `flow_rng_policy_6B` families (see §9).

### 6.2 Event family amount rules

Define “primary amount” rules by amount family, then map event types to those rules:

Examples (non-binding names):

* `PURCHASE_AUTH_AMOUNT`
* `ATM_WITHDRAWAL_AMOUNT`
* `BANK_TRANSFER_AMOUNT`
* `FEE_AMOUNT`

---

## 7) Cross-event constraints (MUST)

These define deterministic relationships between event amounts in the same flow:

Required constraints:

* **Clearing vs auth**:

  * baseline: `amt_clearing = amt_auth × (1 + delta)` where `delta` is either 0 (deterministic) or a small stochastic jitter drawn via `flow_rng_policy_6B` (bounded).
* **Refund**:

  * `amt_refund = -refund_fraction × amt_clearing` (fraction in (0,1]) with optional partial refunds.
* **Reversal**:

  * `amt_reversal = -amt_auth` (or `-amt_clearing` depending on event semantics; must be pinned by flow_type/event_type).
* **Sign rules**:

  * Refund/Reversal amounts must be negative (or have `direction` field), but v1 should use signed numeric for simplicity.

All relationships must be pinned by `cross_event_constraints` and must reference event_type tokens from `flow_shape_policy_6B`.

---

## 8) Rounding rules (MUST)

Amounts must obey a deterministic rounding policy:

* `amount_dp_by_currency` (map `ccy → dp`) or a single `default_dp`
* rounding mode: `round_half_even` (recommended, consistent with numeric policy)
* clamp to min/max per currency (optional)

S2 should store:

* `amount_minor` (int) and optionally `amount` float for convenience; if both are stored, minor must be authoritative.

---

## 9) RNG integration (how this policy consumes RNG)

This policy must not define budgets; it must define which **decision points** exist so `flow_rng_policy_6B` can budget them.

Required fields in `bindings`:

* `rng_family_for_amount_base_draw` (e.g., `rng_event_amount_base`)
* `rng_family_for_amount_jitter_draw` (e.g., `rng_event_amount_jitter`)
* `rng_family_for_currency_cross_draw` (if cross-currency enabled)

Rule:

* All sampling uses open-interval u01 mapping from `rng_profile_layer3`.
* No extra RNG families beyond those budgeted by `flow_rng_policy_6B`.

---

## 10) Guardrails (MUST)

Hard caps preventing absurd outputs:

* `max_amount_minor_by_currency` (map)
* `min_amount_minor_by_currency` (map; usually 1 minor unit for positive events)
* `max_refund_fraction` (≤1)
* `max_clearing_delta_abs` (e.g., 0.02)
* `max_fee_fraction` (if fees used)

If violated: FAIL (baseline should not silently clamp unless behaviour_config says clamp-and-warn for dev).

---

## 11) Realism targets (MUST)

Non-toy corridors per amount family and channel_group:

* `median_minor_range_by_family` (family → {min,max})
* `p95_minor_range_by_family` (family → {min,max})
* `heavy_tail_ratio_range_by_family` (family → ratio bounds, e.g. p99/p50)
* `fraction_round_price_points_min` (for DISCRETE_PRICE_POINTS_V1)
* `decline_amount_distribution_same_as_approved` (bool; typically true—declines still have attempted amounts)

These corridors force realistic, heavy-tailed money.

---

## 12) Minimal v1 example (starter skeleton)

```yaml
schema_version: 1
policy_id: amount_model_6B
policy_version: v1

bindings:
  channel_groups: [ECOM, POS, ATM, BANK_RAIL, HYBRID]
  event_type_vocab: [AUTH_REQUEST, AUTH_RESPONSE, CLEARING, REFUND, REVERSAL]
  rng_family_for_amount_base_draw: rng_event_amount_base
  rng_family_for_amount_jitter_draw: rng_event_amount_jitter
  rng_family_for_currency_cross_draw: rng_event_currency_cross

currency_policy:
  mode: MERCHANT_PRIMARY_ONLY
  require_merchant_primary_ccy: true

amount_families:
  PURCHASE:
    base_distribution:
      dist_id: DISCRETE_PRICE_POINTS_V1
      price_points_minor: [199, 499, 999, 1499, 1999, 2999, 4999]
      point_mass_total: 0.35
      tail:
        dist_id: LOGNORMAL_V1
        mu_log: 7.2
        sigma_log: 0.9
  CASH_WITHDRAWAL:
    base_distribution:
      dist_id: DISCRETE_PRICE_POINTS_V1
      price_points_minor: [2000, 5000, 10000, 20000, 50000]
      point_mass_total: 0.70
      tail:
        dist_id: LOGNORMAL_V1
        mu_log: 8.4
        sigma_log: 0.6

event_amount_rules:
  rules:
    - rule_id: RULE_PURCHASE_AUTH
      amount_family: PURCHASE
      applies_to:
        channel_groups: [ECOM, POS, HYBRID]
        event_types: [AUTH_REQUEST]
      sign: POSITIVE
      base_draw: { enabled: true, family: rng_event_amount_base }

    - rule_id: RULE_ATM_AUTH
      amount_family: CASH_WITHDRAWAL
      applies_to:
        channel_groups: [ATM]
        event_types: [AUTH_REQUEST]
      sign: POSITIVE
      base_draw: { enabled: true, family: rng_event_amount_base }

cross_event_constraints:
  clearing_amount:
    mode: auth_times_one_plus_delta_v1
    delta:
      enabled: true
      family: rng_event_amount_jitter
      delta_abs_max: 0.01
      dist_id: UNIFORM_SYMMETRIC_V1
    apply_when_event_types_present: [AUTH_REQUEST, CLEARING]

  refund_amount:
    mode: negative_fraction_of_clearing_v1
    refund_fraction:
      allow_partial: true
      partial_prob: 0.35
      partial_fraction_range: { min: 0.10, max: 0.90 }
      full_prob: 0.65
    sign: NEGATIVE
    apply_when_event_types_present: [CLEARING, REFUND]

  reversal_amount:
    mode: negative_of_auth_v1
    sign: NEGATIVE
    apply_when_event_types_present: [AUTH_REQUEST, REVERSAL]

rounding:
  mode: minor_units
  default_dp: 2
  rounding_mode: round_half_even

guardrails:
  max_amount_minor_by_currency: { DEFAULT: 500000000 }  # 5,000,000.00
  min_amount_minor_by_currency: { DEFAULT: 1 }
  max_refund_fraction: 1.0
  max_clearing_delta_abs: 0.02

realism_targets:
  median_minor_range_by_family:
    PURCHASE: { min: 300, max: 6000 }
    CASH_WITHDRAWAL: { min: 2000, max: 30000 }
  p95_minor_range_by_family:
    PURCHASE: { min: 5000, max: 200000 }
    CASH_WITHDRAWAL: { min: 20000, max: 200000 }
  heavy_tail_ratio_range_by_family:
    PURCHASE: { min: 10.0, max: 300.0 }
    CASH_WITHDRAWAL: { min: 2.0, max: 50.0 }
  fraction_round_price_points_min:
    PURCHASE: 0.20
    CASH_WITHDRAWAL: 0.60
```

---

## 13) Acceptance checklist (MUST)

1. Contract pins match (path + schema_ref + manifest_key).
2. Token-less, no YAML anchors/aliases, unknown keys invalid.
3. Currency mode is coherent with sealed merchant currency inputs (fail if missing).
4. All event_type tokens referenced exist in `flow_shape_policy_6B` vocab.
5. All stochastic draws reference RNG families budgeted by `flow_rng_policy_6B`.
6. Cross-event constraints enforce sign rules and bounded deltas.
7. Realism corridors are non-degenerate (heavy-tailed) and satisfiable.

---
