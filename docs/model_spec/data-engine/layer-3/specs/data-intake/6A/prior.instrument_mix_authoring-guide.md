# Authoring Guide — `instrument_mix_priors_6A` (`mlr.6A.prior.instrument_mix`, v1)

## 0) Purpose

`instrument_mix_priors_6A` is the **sealed INSTRUMENT_PRIOR / PRODUCT_PRIOR** that 6A.S3 uses to define:

* which **instrument types** exist for each **account cell**
* expected **instruments-per-account** targets by instrument type (and optionally by scheme)
* deterministic **attribute mixes** used when S3 samples instrument attributes (scheme/network, brand_tier, token_type, expiry/flags)

S3 plans over instrument cells:

* account cell: `b_acc = (region_id, party_type, segment_id, account_type)`
* instrument planning cell: `c_instr = (region_id, party_type, segment_id, account_type, instrument_type[, scheme])`

and derives targets like:

`N_instr_target(c_instr) = N_accounts(b_acc) × λ_instr_per_account(c_instr) × scale_context(c_instr)`

This prior MUST be **token-less**, **RNG-free**, **fields-strict**, and **non-toy**.

---

## 1) File identity (binding)

From the 6A contracts:

* **manifest_key:** `mlr.6A.prior.instrument_mix`
* **dataset_id:** `prior_instrument_mix_6A`
* **path:** `config/layer3/6A/priors/instrument_mix_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/instrument_mix_priors_6A`
* **status:** required (consumed by `6A.S0` and `6A.S3`)

**Token-less posture:** do **not** embed timestamps/UUIDs/digests; S0 seals this file by exact bytes and records `sha256_hex`.

---

## 2) Dependencies (MUST exist & be compatible)

This prior must be authored against these sealed artefacts:

* `taxonomy_instrument_types_6A` (instrument types, schemes/networks, brand tiers, token types)
* `taxonomy_account_types_6A` (account_type universe / eligibility)
* `taxonomy_party_6A` (region_id, party_type, segment_id universe)
* `prior_segmentation_6A` (segment profiles if you use feature-based tilts)

S3 will **fail closed** if required priors/taxonomies are missing/invalid/digest-mismatched.

---

## 3) What this prior must determine (S3-faithful)

For every account cell `b_acc` that has `N_accounts(b_acc) > 0`, this prior must define:

### 3.1 Instrument domain

A non-empty allowed set:

`I(b_acc) ⊆ {instrument_type}`

and optionally whether scheme is part of planning:

* `scheme_mode = IN_CELL` → `scheme` is part of `c_instr`
* `scheme_mode = ATTRIBUTE_ONLY` → scheme is sampled later as an attribute, using π_scheme|c

### 3.2 Expected instruments per account

Either directly as per-type rates:

* `λ_instr_per_account(b_acc, instrument_type[, scheme])`

or as:

* a total `λ_total(b_acc)` and a mix `π_instr_type|b_acc`, where
  `λ_instr = λ_total × π_instr_type`.

### 3.3 Attribute distributions (used by S3 attribute sampling)

Deterministic conditional distributions for:

* `π_scheme | c` (if scheme not in cell)
* `π_brand_tier | c` (premium vs basic vs business tiers, etc.)
* `π_token_type | c` (e.g., network token vs none)
* `π_expiry_offset | c` and `π_flags | c` (contactless_enabled, virtual_only, etc.)

---

## 4) Modelling principles (NON-TOY realism)

### 4.1 Coverage

* Any account_type that is **instrument-bearing** in your world must have ≥1 instrument_type in its domain.
* Deposit/current accounts should have at least one access credential path (e.g., debit card and/or bank-account handle) unless you explicitly model “un-instrumented” accounts (rare).
* Credit card accounts must map to credit-card instrument types (and later linkage rules / per-account priors enforce min≥1 where required).

### 4.2 Density sanity

Per account_type, your λ ranges must avoid toy or absurd worlds:

* “primary” deposit/current: typically λ_total in `[1.0, 2.5]`
* savings: often `[0.0, 0.5]`
* revolving credit cards: often `[1.0, 2.5]` (one physical + optional virtual/token)
* loans: often `[0.0, 0.3]` (many loans have no dedicated instrument)

S3 will fail if targets are grossly inconsistent (or yield impossible allocations) and surfaces that as `INSTRUMENT_TARGETS_INCONSISTENT` / `LINKAGE_RULE_VIOLATION` style errors.

### 4.3 Variation

If there are multiple regions, your mix should not be identical everywhere:

* at least one region should be meaningfully more card-heavy / more digital-token heavy than another (deterministic).

---

## 5) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `prior_id` (string; MUST be `instrument_mix_priors_6A`)
3. `prior_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `cell_definition` (object)
6. `scheme_mode` (enum)
7. `instrument_domain_model` (object)
8. `lambda_model` (object)
9. `attribute_models` (object)
10. `constraints` (object)
11. `realism_targets` (object)
12. `notes` (optional string)

Unknown keys: **INVALID**.

Formatting MUST:

* be token-less
* contain no YAML anchors/aliases
* sort lists by stable keys (see Acceptance checklist).

---

## 6) Section contracts

### 6.1 `bindings` (MUST)

* `party_taxonomy_ref: taxonomy_party_6A`
* `account_taxonomy_ref: taxonomy_account_types_6A`
* `instrument_taxonomy_ref: taxonomy_instrument_types_6A`

### 6.2 `cell_definition` (MUST)

* `account_cell: [region_id, party_type, segment_id, account_type]`
* `instrument_cell_base: [region_id, party_type, segment_id, account_type, instrument_type]`
* if `scheme_mode=IN_CELL`: `instrument_cell: [..., scheme]` else same as base.

### 6.3 `scheme_mode` (MUST)

* `IN_CELL` or `ATTRIBUTE_ONLY` (exact).

### 6.4 `instrument_domain_model` (MUST)

Defines `I(b_acc)`.

Required fields:

* `mode` ∈ `{ by_party_type_account_type, by_party_type_segment_account_type }`
* `allowed_instrument_types`:

  * list of rows `{party_type, account_type, instrument_types:[...]}`
* optional `segment_overrides`:

  * list of rows `{party_type, segment_id, account_type, instrument_types:[...]}`

Rules:

* Every `instrument_type` must exist in `taxonomy_instrument_types_6A`.
* Missing domain for any planned `(party_type, account_type)` cell is **FAIL CLOSED**.

### 6.5 `lambda_model` (MUST)

Defines λ targets by cell.

Required fields:

* `mode` ∈ `{ lambda_total_times_mix_v1 }`
* `lambda_total_by_party_type_account_type`:

  * rows `{party_type, account_type, lambda_total}`
* `mix_by_party_type_account_type`:

  * rows `{party_type, account_type, pi_instr:[{instrument_type, share}]}`

Optional deterministic tilts:

* `segment_tilt` (object; if present)

  * `segment_profile_source: prior_segmentation_6A`
  * `features` list (e.g., `digital_affinity`, `credit_appetite`, `cash_affinity`, `cross_border_propensity`)
  * `weights_by_feature` mapping `feature -> instrument_type -> weight`
  * `clip_log_multiplier` (float > 0)
  * pinned law: multiply unnormalised mix weights by `exp(Σ weight×(score-0.5))` then renormalise.

* `region_tilt` (object; optional)

  * `region_profiles` list `{region_id, card_penetration_score, digital_score, cross_border_score}` in [0,1]
  * used to scale `lambda_total` and/or adjust mix weights deterministically (no RNG).

If `scheme_mode=IN_CELL`, you may additionally provide:

* `scheme_split` mapping `{instrument_type -> pi_scheme_kind -> pi_scheme}` to expand `(instrument_type)` into `(instrument_type, scheme)` cells.

### 6.6 `attribute_models` (MUST)

Defines distributions used in S3 attribute sampling.

Required sub-objects (even if disabled):

* `scheme_model`
* `brand_tier_model`
* `token_type_model`
* `expiry_model`
* `flags_model`

Each sub-object MUST have:

* `enabled` (bool)
* `mode` (enum; v1 pinned below)
* `defaults` (object)
* `overrides` (optional list)

Pinned v1 modes (recommended, deterministic):

* `scheme_model.mode = by_region_and_scheme_kind_v1`
* `brand_tier_model.mode = by_party_type_with_segment_tilt_v1`
* `token_type_model.mode = by_party_type_with_digital_tilt_v1`
* `expiry_model.mode = fixed_horizon_offsets_v1`
* `flags_model.mode = by_instrument_type_v1`

Rules:

* Every referenced `scheme`, `brand_tier`, `token_type` MUST exist in `taxonomy_instrument_types_6A`.

### 6.7 `constraints` (MUST)

Required:

* `fail_on_missing_rule: true`
* `max_lambda_total_per_account_type` rows `{party_type, account_type, max_lambda_total}`
* `min_nonzero_instrument_types_per_domain` rows `{party_type, account_type, min_k}`
* `max_single_instrument_type_share_cap` rows `{party_type, account_type, cap}`

If `scheme_mode=IN_CELL`:

* `min_nonzero_schemes_per_card_cell` (int ≥ 1)

### 6.8 `realism_targets` (MUST)

Corridors S3 (or CI) can validate before/after planning:

Required:

* `lambda_total_range_by_account_group` (group → {min,max})
* `card_penetration_proxy_range_by_party_type` (party_type → {min,max})
* `virtual_share_range_for_card_like` ({min,max})
* `tokenization_share_range_for_card_like` ({min,max})
* `region_variation_required_if_n_regions_ge` (int ≥ 2)
* `region_variation_min_delta` (float ≥ 0)

---

## 7) Authoring procedure (Codex-ready)

1. **Read taxonomies**

   * account types and which ones are instrument-bearing
   * instrument types + which ones are card-like / bank-rail / wallet-like

2. **Define instrument domain**

   * for each `(party_type, account_type)`, list allowed instrument_types
   * keep domain non-empty for all planned cells

3. **Set base λ_total**

   * per `(party_type, account_type)` choose realistic densities

4. **Set base type mix**

   * per `(party_type, account_type)` choose shares across instrument types
   * enforce caps so one type doesn’t dominate everywhere

5. **Add deterministic tilts**

   * use segment profiles (digital_affinity, credit_appetite…) to shift virtual/token shares
   * use region profiles to drive regional scheme/card penetration differences

6. **Define attribute models**

   * card networks by region
   * brand_tier skew by segment income
   * tokenization skew by digital affinity/region digital score
   * expiry offsets and static flags by instrument_type

7. **Run acceptance checks** (next section) and FAIL CLOSED on violations.

---

## 8) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
prior_id: instrument_mix_priors_6A
prior_version: v1

bindings:
  party_taxonomy_ref: taxonomy_party_6A
  account_taxonomy_ref: taxonomy_account_types_6A
  instrument_taxonomy_ref: taxonomy_instrument_types_6A

cell_definition:
  account_cell: [region_id, party_type, segment_id, account_type]
  instrument_cell_base: [region_id, party_type, segment_id, account_type, instrument_type]

scheme_mode: ATTRIBUTE_ONLY

instrument_domain_model:
  mode: by_party_type_account_type
  allowed_instrument_types:
    - party_type: RETAIL
      account_type: RETAIL_CURRENT_BASIC
      instrument_types: [RETAIL_DEBIT_CARD_PHYSICAL, PARTY_BANK_ACCOUNT_DOMESTIC]
    - party_type: RETAIL
      account_type: RETAIL_CREDIT_CARD_STANDARD
      instrument_types: [RETAIL_CREDIT_CARD_PHYSICAL, RETAIL_CREDIT_CARD_VIRTUAL]
    - party_type: BUSINESS
      account_type: BUSINESS_CURRENT
      instrument_types: [BUSINESS_DEBIT_CARD_PHYSICAL, PARTY_BANK_ACCOUNT_DOMESTIC]

lambda_model:
  mode: lambda_total_times_mix_v1
  lambda_total_by_party_type_account_type:
    - { party_type: RETAIL, account_type: RETAIL_CURRENT_BASIC,       lambda_total: 1.60 }
    - { party_type: RETAIL, account_type: RETAIL_CREDIT_CARD_STANDARD, lambda_total: 1.40 }
    - { party_type: BUSINESS, account_type: BUSINESS_CURRENT,          lambda_total: 1.80 }

  mix_by_party_type_account_type:
    - party_type: RETAIL
      account_type: RETAIL_CURRENT_BASIC
      pi_instr:
        - { instrument_type: RETAIL_DEBIT_CARD_PHYSICAL, share: 0.75 }
        - { instrument_type: PARTY_BANK_ACCOUNT_DOMESTIC, share: 0.25 }
    - party_type: RETAIL
      account_type: RETAIL_CREDIT_CARD_STANDARD
      pi_instr:
        - { instrument_type: RETAIL_CREDIT_CARD_PHYSICAL, share: 0.75 }
        - { instrument_type: RETAIL_CREDIT_CARD_VIRTUAL,  share: 0.25 }
    - party_type: BUSINESS
      account_type: BUSINESS_CURRENT
      pi_instr:
        - { instrument_type: BUSINESS_DEBIT_CARD_PHYSICAL, share: 0.70 }
        - { instrument_type: PARTY_BANK_ACCOUNT_DOMESTIC,  share: 0.30 }

  segment_tilt:
    segment_profile_source: prior_segmentation_6A
    features: [digital_affinity, credit_appetite]
    clip_log_multiplier: 0.9
    weights_by_feature:
      digital_affinity:
        RETAIL_CREDIT_CARD_VIRTUAL: 0.8
      credit_appetite:
        RETAIL_CREDIT_CARD_PHYSICAL: 0.4
        RETAIL_CREDIT_CARD_VIRTUAL: 0.4

attribute_models:
  scheme_model:
    enabled: true
    mode: by_region_and_scheme_kind_v1
    defaults:
      CARD_NETWORK:
        - { scheme: VISA, share: 0.55 }
        - { scheme: MASTERCARD, share: 0.40 }
        - { scheme: AMEX, share: 0.05 }
      BANK_RAIL:
        - { scheme: FPS, share: 0.55 }
        - { scheme: SEPA_CREDIT, share: 0.35 }
        - { scheme: SWIFT, share: 0.10 }
    overrides: []

  brand_tier_model:
    enabled: true
    mode: by_party_type_with_segment_tilt_v1
    defaults:
      RETAIL:
        - { brand_tier: BASIC, share: 0.85 }
        - { brand_tier: PREMIUM, share: 0.15 }
      BUSINESS:
        - { brand_tier: BUSINESS, share: 0.90 }
        - { brand_tier: CORPORATE, share: 0.10 }
    overrides: []

  token_type_model:
    enabled: true
    mode: by_party_type_with_digital_tilt_v1
    defaults:
      RETAIL:
        - { token_type: NONE, share: 0.70 }
        - { token_type: NETWORK_TOKEN, share: 0.25 }
        - { token_type: DEVICE_TOKEN, share: 0.05 }
      BUSINESS:
        - { token_type: NONE, share: 0.80 }
        - { token_type: NETWORK_TOKEN, share: 0.18 }
        - { token_type: DEVICE_TOKEN, share: 0.02 }
    overrides: []

  expiry_model:
    enabled: true
    mode: fixed_horizon_offsets_v1
    defaults:
      card_expiry_years: [2, 3, 4, 5]
      month_uniform: true
    overrides: []

  flags_model:
    enabled: true
    mode: by_instrument_type_v1
    defaults:
      contactless_enabled_prob: 0.92
      card_present_capable_prob: 0.80
      card_not_present_capable_prob: 0.98
    overrides: []

constraints:
  fail_on_missing_rule: true
  min_nonzero_instrument_types_per_domain:
    - { party_type: RETAIL, account_type: RETAIL_CURRENT_BASIC,       min_k: 1 }
    - { party_type: RETAIL, account_type: RETAIL_CREDIT_CARD_STANDARD, min_k: 1 }
    - { party_type: BUSINESS, account_type: BUSINESS_CURRENT,          min_k: 1 }
  max_lambda_total_per_account_type:
    - { party_type: RETAIL, account_type: RETAIL_CURRENT_BASIC,       max_lambda_total: 3.0 }
    - { party_type: RETAIL, account_type: RETAIL_CREDIT_CARD_STANDARD, max_lambda_total: 3.0 }
    - { party_type: BUSINESS, account_type: BUSINESS_CURRENT,          max_lambda_total: 4.0 }
  max_single_instrument_type_share_cap:
    - { party_type: RETAIL, account_type: RETAIL_CURRENT_BASIC,       cap: 0.90 }
    - { party_type: RETAIL, account_type: RETAIL_CREDIT_CARD_STANDARD, cap: 0.95 }
    - { party_type: BUSINESS, account_type: BUSINESS_CURRENT,          cap: 0.95 }

realism_targets:
  lambda_total_range_by_account_group:
    DEPOSIT_PRIMARY: { min: 1.0, max: 2.5 }
    CREDIT_CARD:     { min: 1.0, max: 2.5 }
  card_penetration_proxy_range_by_party_type:
    RETAIL:  { min: 0.75, max: 0.98 }
    BUSINESS:{ min: 0.65, max: 0.98 }
    OTHER:   { min: 0.10, max: 0.90 }
  virtual_share_range_for_card_like: { min: 0.05, max: 0.45 }
  tokenization_share_range_for_card_like: { min: 0.05, max: 0.55 }
  region_variation_required_if_n_regions_ge: 3
  region_variation_min_delta: 0.03
```

*(IDs here must match the instrument/account taxonomies you authored; this is a shape example.)*

---

## 9) Acceptance checklist (MUST)

### 9.1 Contract pins

* manifest_key/dataset_id/path/schema_ref match the 6A dictionary/registry.

### 9.2 Structural strictness

* YAML parses; unknown keys absent everywhere.
* Token-less; no timestamps/UUIDs/digests.
* No YAML anchors/aliases.
* Deterministic ordering:

  * domain/lambda rows sorted by `(party_type, account_type)` then id
  * mixes sorted by `(party_type, account_type, instrument_type)`.

### 9.3 Taxonomy compatibility

* Every referenced `instrument_type/scheme/brand_tier/token_type` exists in `taxonomy_instrument_types_6A`.
* Every referenced `account_type` exists in `taxonomy_account_types_6A`.

### 9.4 Non-toy corridors

* Domain non-empty where accounts exist.
* λ totals within configured ranges.
* No single instrument_type dominates beyond cap for all cells.
* If regions ≥ threshold: at least one meaningful regional difference in a monitored statistic (e.g., virtual share or scheme mix).

### 9.5 S3 feasibility alignment

* Parameters must not imply impossible allocations (e.g., λ_total huge with tight caps in linkage rules), otherwise S3 will fail with `INSTRUMENT_TARGETS_INCONSISTENT` / `LINKAGE_RULE_VIOLATION`.

---
