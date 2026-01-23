# Authoring Guide — `product_mix_priors_6A` (`mlr.6A.prior.product_mix`, v1)

## 0) Purpose

`product_mix_priors_6A` is the **sealed PRODUCT_PRIOR** that 6A.S2 uses to:

1. define the allowed **account-type domain** per population cell
   [
   A(b) = {\text{account_type} \mid \text{priors say allowed for } b}
   ]
2. provide expected **accounts-per-party** for each account cell
   [
   \lambda_{\text{acc_per_party}}(c) \ge 0
   ]
   so S2 can compute continuous targets
   [
   N_{\text{acc_target}}(c) = N_{\text{party}}(b)\times \lambda_{\text{acc_per_party}}(c)\times s_{\text{context}}(c)
   ]
   with (s_{\text{context}}(c)=1) unless optional context scaling is used.

This prior is **RNG-free**, **token-less**, and **non-toy**: it must support realistic heterogeneity across `region_id × party_type × segment_id` without hand-wavy defaults.

---

## 1) File identity (binding)

* **manifest_key:** `mlr.6A.prior.product_mix` 
* **dataset_id:** `prior_product_mix_6A`
* **path:** `config/layer3/6A/priors/product_mix_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/product_mix_priors_6A`
* **status:** `required` (S0 + S2) 

**Token-less posture:** no timestamps, no embedded digests/UUIDs; S0 seals by file bytes + sha256.

---

## 2) Dependencies (MUST exist & be compatible)

This prior MUST be authored against these sealed inputs:

* **party taxonomy:** `taxonomy_party_6A` (`party_taxonomy_6A.v1.yaml`) for `region_id`, `party_type`, `segment_id` vocab.
* **account taxonomy:** `taxonomy_account_types_6A` (`account_taxonomy_6A.v1.yaml`) for valid `account_type` codes and owner/eligibility constraints.
* **segmentation priors:** produced `segment_id` is what S2 sees in `b=(region_id,party_type,segment_id)`; product mix must be defined over that same cell axis.

---

## 3) Pinned semantics (what S2 will do with it)

### 3.1 Cell definition (v1)

S2’s core planning cells are:

* **base cell:** `b = (region_id, party_type, segment_id)`
* **account cell:** `c = (region_id, party_type, segment_id, account_type)`

### 3.2 What the prior must provide

For every base cell (b) that exists in S1 output:

* a deterministic domain (A(b)) (allowed account types), and
* (\lambda_{\text{acc_per_party}}(c)) for each (c=(b,account_type)) where `account_type ∈ A(b)`.

S2 is allowed to apply deterministic **context scaling** (s_{\text{context}}(c)) from optional context surfaces, but those must not redefine taxonomies/identity.

### 3.3 Merchant accounts (optional branch)

S2 may additionally allocate **merchant-owned accounts** if your model enables it; S2 then defines a merchant cell domain (example: `(merchant_region, merchant_risk_class, merchant_size_band, account_type)`). If your priors do not enable merchant mode, S2 must not create merchant accounts. 

---

## 4) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `prior_id` (string; MUST be `product_mix_priors_6A`)
3. `prior_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `party_account_domain` (object)
6. `party_lambda_model` (object)
7. `constraints` (object)
8. `realism_targets` (object)
9. `merchant_mode` (object)
10. `notes` (optional string)

Unknown keys: **INVALID**.

Formatting MUST:

* no YAML anchors/aliases
* stable ordering (see §8.3)
* token-less.

---

## 5) Section contracts

### 5.1 `bindings` (MUST)

Required:

* `party_taxonomy_ref` = `taxonomy_party_6A`
* `account_taxonomy_ref` = `taxonomy_account_types_6A`
* `cell_definition`:

  * `base_cell`: `[region_id, party_type, segment_id]`
  * `account_cell`: `[region_id, party_type, segment_id, account_type]`

### 5.2 `party_account_domain` (MUST)

Defines how `A(b)` is derived.

Required fields:

* `mode` ∈ `{ explicit_by_party_type, explicit_by_party_type_and_segment }`
* `required_account_types_by_party_type` (map: `RETAIL|BUSINESS|OTHER → list[account_type]`)
* `allowed_account_types_by_party_type` (map: `RETAIL|BUSINESS|OTHER → list[account_type]`)

If `mode=explicit_by_party_type_and_segment`, also require:

* `allowed_account_types_by_segment` (list of `{party_type, segment_id, allowed_account_types}`)

Hard rules:

* Any `account_type` named here MUST exist in `taxonomy_account_types_6A`.
* Any `account_type` used for PARTY owners MUST be eligible for that `party_type` per account taxonomy; otherwise S2 should fail as “taxonomy/eligibility violation”.

### 5.3 `party_lambda_model` (MUST)

Defines (\lambda_{\text{acc_per_party}}(c)).

Required fields:

* `lambda_units`: MUST be `accounts_per_party`
* `mode` ∈ `{ base_plus_segment_tilt_v1 }`
* `base_lambda_by_party_type`:

  * map party_type → map account_type → float λ (≥ 0)

Segment tilt (required in v1 mode):

* `segment_tilt`:

  * `feature_center` (float; default `0.5`)
  * `features` (list of allowed feature names, e.g. `digital_affinity`, `credit_appetite`, `stability_score`, `cash_affinity`, `cross_border_propensity`)
  * `weights_by_feature`:

    * map feature_name → map account_type → weight (float; can be negative)
  * `clip_log_multiplier` (float > 0)
  * `segment_profile_source` = `prior_segmentation_6A` *(meaning: S2 expects the segmentation prior pack to expose per-segment feature scores, or you must set all weights to 0)*

Pinned law (deterministic):

For base cell `b=(region_id, party_type, segment_id)` and account_type `a`:

* `λ_base = base_lambda_by_party_type[party_type][a]`
* `x = Σ_f w[f][a] * (score_f(segment_id) - feature_center)`
* `x = clamp(x, -clip_log_multiplier, +clip_log_multiplier)`
* `λ(c) = max(0, λ_base * exp(x))`

Optional context scaling:

* `context_scaling` object (optional; if absent S2 uses `s_context(c)=1`):

  * `enabled` (bool)
  * `context_feature` (enum string; e.g. `CARD_HEAVY_SCORE`, `CASH_HEAVY_SCORE`)
  * `weights_by_account_group` (map group → weight)
  * `clip_log_multiplier`

*(This aligns with S2’s allowance to tilt priors using deterministic context surfaces.)*

### 5.4 `constraints` (MUST)

Required:

* `max_total_lambda_per_party_by_party_type` (map party_type → float > 0)
  *(S2 sanity checks expect “max accounts per party × N_party(b)” style bounds.)*
* `min_nonzero_account_types_in_domain` (map party_type → int ≥ 1)
* `disallow_zero_domain_cells` (bool; if true and `N_party(b)>0`, `A(b)` must be non-empty)
* `enforce_required_types` (bool; if true, required types must be in A(b) and have λ>0)

### 5.5 `realism_targets` (MUST)

These are corridor checks that MUST be satisfied by the authored priors.

Required:

* `lambda_total_range_by_party_type` (map party_type → `{min,max}`)
  *(range for Σ_a λ(c) across allowed a in a typical cell)*
* `deposit_penetration_proxy_range` (map party_type → `{min,max}`)
  *(proxy using `1-exp(-λ_deposit_total)`; use DEPOSIT-like account types)*
* `credit_card_penetration_proxy_range` (map party_type → `{min,max}`)
* `max_single_account_type_share_proxy` (map party_type → float in (0,1))
  *(proxy: λ_a / Σ λ )*
* `region_variation_required_if_n_regions_ge` (int ≥ 2)
* `region_variation_min_delta_lambda` (float ≥ 0)
  *(ensure not every region identical if there are many regions)*

### 5.6 `merchant_mode` (MUST)

Required:

* `enabled` (bool)
* if `enabled: false`:

  * `reason` (string; e.g. “merchant accounts not modelled in v1”)
* if `enabled: true`:

  * `merchant_account_types` (list[account_type] where taxonomy owner_kind is MERCHANT)
  * `lambda_per_merchant` (map account_type → float ≥ 0)
  * `merchant_cell_definition` (list of dimension names; MUST match what S2 actually has available)

---

## 6) Non-toy realism (minimum requirements)

MUST satisfy:

* For each party_type, `allowed_account_types_by_party_type[party_type]` has at least:

  * RETAIL: ≥ 5 types
  * BUSINESS: ≥ 4 types
  * OTHER: ≥ 2 types
* `required_account_types_by_party_type` is non-empty for RETAIL and BUSINESS (to avoid “unbanked” toy worlds).
* In at least one party_type, at least one non-deposit product has λ > 0.05 (avoid “everyone has only current account”).

---

## 7) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
prior_id: product_mix_priors_6A
prior_version: v1

bindings:
  party_taxonomy_ref: taxonomy_party_6A
  account_taxonomy_ref: taxonomy_account_types_6A
  cell_definition:
    base_cell: [region_id, party_type, segment_id]
    account_cell: [region_id, party_type, segment_id, account_type]

party_account_domain:
  mode: explicit_by_party_type
  required_account_types_by_party_type:
    RETAIL: [RETAIL_CURRENT_BASIC]
    BUSINESS: [BUSINESS_CURRENT]
    OTHER: [OTHER_CURRENT]
  allowed_account_types_by_party_type:
    RETAIL:
      - RETAIL_CURRENT_BASIC
      - RETAIL_SAVINGS_INSTANT
      - RETAIL_CREDIT_CARD_STANDARD
      - RETAIL_PERSONAL_LOAN_UNSECURED
      - WALLET_DEVICE_TOKEN
    BUSINESS:
      - BUSINESS_CURRENT
      - BUSINESS_SAVINGS
      - BUSINESS_CREDIT_CARD
      - BUSINESS_TERM_LOAN
    OTHER:
      - OTHER_CURRENT
      - OTHER_SAVINGS

party_lambda_model:
  lambda_units: accounts_per_party
  mode: base_plus_segment_tilt_v1

  base_lambda_by_party_type:
    RETAIL:
      RETAIL_CURRENT_BASIC: 1.00
      RETAIL_SAVINGS_INSTANT: 0.35
      RETAIL_CREDIT_CARD_STANDARD: 0.45
      RETAIL_PERSONAL_LOAN_UNSECURED: 0.10
      WALLET_DEVICE_TOKEN: 0.20
    BUSINESS:
      BUSINESS_CURRENT: 1.00
      BUSINESS_SAVINGS: 0.40
      BUSINESS_CREDIT_CARD: 0.35
      BUSINESS_TERM_LOAN: 0.18
    OTHER:
      OTHER_CURRENT: 1.00
      OTHER_SAVINGS: 0.30

  segment_tilt:
    segment_profile_source: prior_segmentation_6A
    feature_center: 0.5
    features: [digital_affinity, credit_appetite, stability_score, cash_affinity]
    clip_log_multiplier: 0.9
    weights_by_feature:
      digital_affinity:
        WALLET_DEVICE_TOKEN: 0.9
        RETAIL_CREDIT_CARD_STANDARD: 0.2
      credit_appetite:
        RETAIL_CREDIT_CARD_STANDARD: 0.8
        RETAIL_PERSONAL_LOAN_UNSECURED: 0.7
        BUSINESS_CREDIT_CARD: 0.6
        BUSINESS_TERM_LOAN: 0.6
      stability_score:
        RETAIL_SAVINGS_INSTANT: 0.5
        BUSINESS_SAVINGS: 0.5
      cash_affinity:
        WALLET_DEVICE_TOKEN: -0.6
        RETAIL_CREDIT_CARD_STANDARD: -0.3

constraints:
  max_total_lambda_per_party_by_party_type: { RETAIL: 6.0, BUSINESS: 8.0, OTHER: 4.0 }
  min_nonzero_account_types_in_domain: { RETAIL: 3, BUSINESS: 3, OTHER: 2 }
  disallow_zero_domain_cells: true
  enforce_required_types: true

realism_targets:
  lambda_total_range_by_party_type:
    RETAIL: { min: 1.3, max: 4.5 }
    BUSINESS: { min: 1.5, max: 5.5 }
    OTHER: { min: 1.1, max: 3.0 }
  deposit_penetration_proxy_range:
    RETAIL: { min: 0.92, max: 0.999 }
    BUSINESS: { min: 0.97, max: 0.999 }
    OTHER: { min: 0.90, max: 0.999 }
  credit_card_penetration_proxy_range:
    RETAIL: { min: 0.25, max: 0.85 }
    BUSINESS: { min: 0.10, max: 0.70 }
    OTHER: { min: 0.00, max: 0.20 }
  max_single_account_type_share_proxy:
    RETAIL: 0.80
    BUSINESS: 0.85
    OTHER: 0.95
  region_variation_required_if_n_regions_ge: 3
  region_variation_min_delta_lambda: 0.05

merchant_mode:
  enabled: false
  reason: "Merchant-owned accounts not modelled in v1 (party accounts only)."
```

*(All account_type ids in this example must exist in `taxonomy_account_types_6A`; the actual ids are defined by your account taxonomy.)*

---

## 8) Acceptance checklist (MUST)

### 8.1 Structural & token-less

* YAML parses cleanly.
* Unknown keys absent at every level.
* No timestamps/UUIDs/digests in-file; no YAML anchors/aliases.

### 8.2 Taxonomy compatibility

* Every referenced `account_type` exists in `taxonomy_account_types_6A`.
* No PARTY cell allows account types that the account taxonomy forbids for that party_type (S2 must fail if present).

### 8.3 Numeric sanity (RNG-free)

* For all implied cells, λ is finite and ≥ 0.
* In each party_type: at least `min_nonzero_account_types_in_domain` account types have λ>0 after tilt.
* For typical cells, Σ λ ≤ `max_total_lambda_per_party_by_party_type[party_type]` (or S2 will fail target sanity).

### 8.4 Non-toy corridors

* `realism_targets` all satisfied (proxy penetrations, max-share proxy, region-variation rule when enough regions).

---

## 9) Change control (MUST)

* Any change that:

  * adds/removes account types in domain,
  * changes tilt law semantics,
  * changes corridor thresholds,
    is a **breaking change** → bump the file version (e.g., `.v2.yaml`) and update `schemas.6A.yaml` anchor definitions accordingly. 

---
