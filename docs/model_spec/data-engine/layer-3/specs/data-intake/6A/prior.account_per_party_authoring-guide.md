# Authoring Guide — `account_per_party_priors_6A` (`mlr.6A.prior.account_per_party`, v1)

## 0) Purpose

`account_per_party_priors_6A` is the **sealed account-per-party prior pack** that 6A.S2 uses to describe:

* the **discrete distribution** of how many accounts of a given `account_type` a party tends to have in a population cell, i.e.
  **P(k accounts of type t | cell b)** 
* how to derive **party-level allocation propensities** `w_p(b, account_type)` used to allocate realised account counts to individual parties. 

This pack does **not** decide total account counts. Totals come from the product-mix plan (`N_acc(c)` per cell) and the S2 integerisation step. This pack shapes **who within the cell gets the accounts** and how concentrated that ownership is.

Non-toy requirement: this pack MUST yield realistic heterogeneity (some parties hold multiple products, many hold none of a specific product) without hand-wavy defaults.

---

## 1) Contract identity (binding)

From the 6A contracts:

* **manifest_key:** `mlr.6A.prior.account_per_party` 
* **dataset_id:** `prior_account_per_party_6A` 
* **path:** `config/layer3/6A/priors/account_per_party_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/account_per_party_priors_6A`
* **status:** `required` (consumed by `6A.S0` and `6A.S2`)

**Token-less posture:** no timestamps, no embedded digests/UUIDs. Sealing happens in S0 via `sealed_inputs_6A` (`sha256_hex` recorded there). 

---

## 2) How 6A.S2 uses it (pinned semantics)

### 2.1 Cell axes

S2 operates over:

* **base cell:** `b = (region_id, party_type, segment_id)`
* **account cell:** `c = (b, account_type)`

### 2.2 What this prior must enable

For each `(b, account_type)` that S2 plans to allocate:

1. a distribution **P(k | b, account_type)** over integer `k ≥ 0` (often zero-inflated and capped),
2. a deterministic way to compute non-negative **party propensities** `w_p(b, account_type)` used to form:

   * `W_total = Σ_p w_p`
   * `π_p = w_p / W_total` 

Hard fail condition (must be prevented by authoring):

* If `W_total = 0` while `N_party(b) > 0` and `N_acc(c) > 0`, S2 must fail. 

---

## 3) Scope and non-goals

### In scope

* Propensity / concentration / caps for allocating accounts among parties.
* Structural zero-inflation (“most people do not have product X”).
* “Some people hold multiple of product X” (e.g., multiple savings, multiple cards) within bounded caps.

### Out of scope

* Total account planning `N_acc(c)` (owned by S2 planning + product-mix priors).
* Eligibility rules (owned by linkage/eligibility configs, not this prior).
* Account attributes (currency, risk tier, channel profile) — those are in S2 attribute priors, not here.

---

## 4) Dependencies (must be compatible)

This prior MUST be authored to align with:

* `taxonomy_party_6A` (party_type / segment_id / region_id universe) 
* `taxonomy_account_types_6A` (valid `account_type` codes and owner/party_type constraints) 
* `product_mix_priors_6A` (defines which account_types may appear in each base cell and the target mix)

**Fail-closed coverage rule (v1):**
If an `account_type` can appear in S2 planning for PARTY owners (because it is allowed by account taxonomy and present in product-mix domain), it MUST have a rule in this file; missing rules are invalid.

---

## 5) Pinned v1 modelling approach

### 5.1 Two outputs from one rule

Each rule produces:

1. **A count distribution** `P(k)` (for reasoning and optional “precompute desired counts” schemes).
2. **A propensity weight generator** for `w_p`, used by the baseline allocation scheme:

   * S2 samples `N_acc(c)` owner parties from `π_p` using `account_allocation_sampling` RNG.

### 5.2 Supported `count_model_id` values (v1 pinned)

v1 supports exactly these `count_model_id` values:

* `bernoulli_cap1_v1`
  k ∈ {0,1} with P(k=1)=q.

* `zi_poisson_capK_v1`
  Structural zero with probability `p_zero`, else Poisson with mean μ, with hard cap `K_max`.

* `zi_nb2_capK_v1`
  Structural zero with probability `p_zero`, else NB2(mean μ, dispersion κ), with hard cap `K_max`.

Any other value ⇒ **FAIL CLOSED** (S2 must treat priors invalid).

### 5.3 Pinned mapping from mean targets to distribution (v1)

This prior is allowed to depend on the **cell mean** λ (expected accounts-per-party) computed by product-mix planning.

Given a desired mean `λ ≥ 0` for a specific `(b, account_type)`:

* If `count_model_id == bernoulli_cap1_v1`:

  * `q = clamp(λ, 0, 1)`

* If `count_model_id ∈ {zi_poisson_capK_v1, zi_nb2_capK_v1}`:

  * μ is set to keep the **unconditional mean** aligned:

    * `μ = λ / max(1e-12, (1 - p_zero))`
  * If `μ` implies an expected value that is unrealistically above `K_max`, S2 must treat this as a configuration error (cap infeasible) and FAIL (do not silently clamp).

This keeps product-mix means and “accounts-per-party” distributions consistent, instead of two priors fighting each other.

---

## 6) Weight construction (v1 pinned, deterministic)

S2 needs `w_p(b, account_type)` for each party `p` in cell `b`. 

v1 pins a deterministic, RNG-free weight construction so we don’t explode RNG event volumes:

1. Compute deterministic uniforms from a hash:

   * `u0 = u_det(mf, parameter_hash, party_id, account_type, "zero_gate") ∈ (0,1)`
   * `u1 = u_det(mf, parameter_hash, party_id, account_type, "weight") ∈ (0,1)`
     *(use the same “hash-to-(0,1)” law you already use elsewhere; no RNG draws)*

2. Structural zero gate:

   * if `u0 < p_zero_weight` ⇒ `w_p = 0`

3. Positive weight:

   * let `z = normal_icdf(u1)` using a deterministic libm profile
   * `normal_icdf` MUST use the engine's pinned normal primitive under numeric policy (open-interval U(0,1) + deterministic libm; see S0.3.4-S0.3.5)
   * `g = exp(sigma * z - 0.5 * sigma^2)`  (mean 1 lognormal)
   * `w_p = max(weight_floor_eps, g)`

4. Optional tag adjustments:

   * if party segment carries tags (from `taxonomy_party_6A`), apply multiplicative adjustments to `p_zero_weight` and/or `sigma` (bounded) before steps 2–3.

This yields:

* zero-inflation (many parties have `w_p=0`)
* heavy-tail propensity among eligible parties
* stable results given `(mf, parameter_hash)` (and party_id)

S2 then normalises and samples owners. If `W_total=0` but `N_acc>0`, S2 fails (by spec). 

---

## 7) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `prior_id` (string; MUST be `account_per_party_priors_6A`)
3. `prior_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `supported_count_models` (list of objects)
6. `rules` (list of objects)
7. `tag_adjustments` (optional list of objects)
8. `constraints` (object)
9. `realism_targets` (object)
10. `notes` (optional string)

Unknown keys ⇒ INVALID.

Formatting MUST:

* token-less (no timestamps/digests)
* no YAML anchors/aliases
* lists sorted by stable keys (see acceptance checks)

### 7.1 `bindings` (MUST)

Required:

* `party_taxonomy_ref: taxonomy_party_6A`
* `account_taxonomy_ref: taxonomy_account_types_6A`
* `base_cell: [region_id, party_type, segment_id]`
* `account_cell: [region_id, party_type, segment_id, account_type]`

### 7.2 `supported_count_models[]` (MUST)

Each entry:

* `count_model_id` (one of the pinned set)
* `required_params` (list of param keys expected under rules)
* `description`

### 7.3 `rules[]` (MUST)

Each rule object MUST contain:

* `party_type` (RETAIL|BUSINESS|OTHER)
* `account_type` (must exist in account taxonomy)
* `count_model_id` (pinned set)
* `params` (object; keys depend on model)

Common required params (all models):

* `K_max` (int ≥ 1)
* `p_zero_weight` (float in [0,1])  *(weight-side structural zero)*
* `sigma` (float ≥ 0) *(lognormal dispersion for positive weights)*
* `weight_floor_eps` (float > 0)

Model-specific required params:

* for `bernoulli_cap1_v1`: *(no extra)*
* for `zi_poisson_capK_v1`: `p_zero` (float in [0,1))
* for `zi_nb2_capK_v1`: `p_zero` (float in [0,1)), `kappa` (float > 0)

### 7.4 `tag_adjustments[]` (optional)

Each adjustment object:

* `tag` (string; must exist in party taxonomy tag vocab if used)
* `account_type`
* `p_zero_weight_multiplier` (float > 0)
* `sigma_multiplier` (float > 0)
* `multipliers_clip` (object `{min,max}`)

Purpose: let “DIGITAL_HEAVY” decrease `p_zero_weight` for wallets, etc., without per-segment hand-tables.

### 7.5 `constraints` (MUST)

Required:

* `coverage_mode` ∈ `{ fail_on_missing_rule }` (v1 pinned)
* `required_types_min_weighted_coverage` (object: party_type → float in (0,1])
  *(e.g., for current accounts, ensure `p_zero_weight` isn’t near 1 everywhere)*
* `K_max_global_upper_bound` (int; hard fail if any rule exceeds)
* `sigma_global_upper_bound` (float; hard fail if any rule exceeds)

### 7.6 `realism_targets` (MUST)

Corridor checks (fail closed if violated):

Required:

* `p_zero_weight_ranges_by_account_group` (map group → `{min,max}`)
* `sigma_ranges_by_account_group` (map group → `{min,max}`)
* `K_max_ranges_by_account_group` (map group → `{min,max}`)
* `min_fraction_of_rules_with_sigma_ge` (object `{sigma: float, frac: float}`)

Account groups are derived from account taxonomy (e.g., deposit vs credit vs loan vs wallet) or explicitly declared in this file as a mapping.

---

## 8) Non-toy realism defaults (recommended ranges)

These aren’t “truth”; they’re guardrails to prevent toy configs.

Typical ranges:

* **Primary deposit/current accounts:**
  `p_zero_weight ∈ [0.00, 0.05]`, `sigma ∈ [0.10, 0.60]`, `K_max ∈ [1,3]`
* **Savings / secondary deposits:**
  `p_zero_weight ∈ [0.40, 0.85]`, `sigma ∈ [0.50, 1.20]`, `K_max ∈ [2,5]`
* **Credit cards:**
  `p_zero_weight ∈ [0.25, 0.75]`, `sigma ∈ [0.60, 1.40]`, `K_max ∈ [2,5]`
* **Loans:**
  `p_zero_weight ∈ [0.70, 0.98]`, `sigma ∈ [0.40, 1.00]`, `K_max ∈ [1,3]`
* **Wallet / token accounts (if modelled as accounts):**
  `p_zero_weight ∈ [0.20, 0.80]`, `sigma ∈ [0.60, 1.60]`, `K_max ∈ [1,3]`

Minimum heterogeneity floor:

* At least **30%** of (party_type, account_type) rules must have `sigma ≥ 0.6` (otherwise allocations become uniform-toy).

---

## 9) Authoring procedure (Codex-ready)

1. Load taxonomies:

   * party taxonomy (party_types, segment tags if present)
   * account taxonomy (valid `account_type` universe and groupings)

2. Read product-mix domain:

   * list the account_types that can appear for each party_type (and segment tags, if you used them)

3. Create `rules`:

   * one rule per `(party_type, account_type)` you might allocate
   * choose `count_model_id` based on product nature (deposit vs credit vs loan)
   * choose `K_max`, `p_zero_weight`, `sigma` using the non-toy guardrails

4. Add tag adjustments (optional):

   * e.g. `DIGITAL_HEAVY` lowers wallet `p_zero_weight`
   * `CREDIT_AVOIDER` raises credit-card `p_zero_weight`

5. Run acceptance checks (next section) and FAIL CLOSED if any violate.

---

## 10) Minimal v1 example (illustrative)

```yaml
schema_version: 1
prior_id: account_per_party_priors_6A
prior_version: v1

bindings:
  party_taxonomy_ref: taxonomy_party_6A
  account_taxonomy_ref: taxonomy_account_types_6A
  base_cell: [region_id, party_type, segment_id]
  account_cell: [region_id, party_type, segment_id, account_type]

supported_count_models:
  - count_model_id: bernoulli_cap1_v1
    required_params: [K_max, p_zero_weight, sigma, weight_floor_eps]
    description: "k in {0,1}; mean matched via q=clamp(lambda,0,1)"
  - count_model_id: zi_poisson_capK_v1
    required_params: [K_max, p_zero, p_zero_weight, sigma, weight_floor_eps]
    description: "structural zero + Poisson(mean=mu), hard cap K_max; mu set from lambda/(1-p_zero)"
  - count_model_id: zi_nb2_capK_v1
    required_params: [K_max, p_zero, kappa, p_zero_weight, sigma, weight_floor_eps]
    description: "structural zero + NB2(mean=mu,disp=kappa), hard cap K_max; mu set from lambda/(1-p_zero)"

rules:
  # RETAIL examples (ids must match taxonomy_account_types_6A)
  - party_type: RETAIL
    account_type: RETAIL_CURRENT_BASIC
    count_model_id: zi_poisson_capK_v1
    params: { K_max: 2, p_zero: 0.02, p_zero_weight: 0.01, sigma: 0.25, weight_floor_eps: 1.0e-6 }

  - party_type: RETAIL
    account_type: RETAIL_SAVINGS_INSTANT
    count_model_id: zi_nb2_capK_v1
    params: { K_max: 4, p_zero: 0.65, kappa: 2.5, p_zero_weight: 0.60, sigma: 0.95, weight_floor_eps: 1.0e-6 }

  - party_type: RETAIL
    account_type: RETAIL_CREDIT_CARD_STANDARD
    count_model_id: zi_nb2_capK_v1
    params: { K_max: 4, p_zero: 0.45, kappa: 1.8, p_zero_weight: 0.40, sigma: 1.10, weight_floor_eps: 1.0e-6 }

  - party_type: RETAIL
    account_type: RETAIL_PERSONAL_LOAN_UNSECURED
    count_model_id: zi_poisson_capK_v1
    params: { K_max: 2, p_zero: 0.88, p_zero_weight: 0.85, sigma: 0.70, weight_floor_eps: 1.0e-6 }

  # BUSINESS examples
  - party_type: BUSINESS
    account_type: BUSINESS_CURRENT
    count_model_id: zi_poisson_capK_v1
    params: { K_max: 3, p_zero: 0.01, p_zero_weight: 0.01, sigma: 0.35, weight_floor_eps: 1.0e-6 }

  - party_type: BUSINESS
    account_type: BUSINESS_CREDIT_CARD
    count_model_id: zi_nb2_capK_v1
    params: { K_max: 6, p_zero: 0.35, kappa: 1.5, p_zero_weight: 0.30, sigma: 1.20, weight_floor_eps: 1.0e-6 }

tag_adjustments:
  - tag: DIGITAL_HEAVY
    account_type: RETAIL_CREDIT_CARD_STANDARD
    p_zero_weight_multiplier: 0.85
    sigma_multiplier: 1.05
    multipliers_clip: { min: 0.50, max: 1.50 }

constraints:
  coverage_mode: fail_on_missing_rule
  required_types_min_weighted_coverage:
    RETAIL: 0.95
    BUSINESS: 0.98
    OTHER: 0.80
  K_max_global_upper_bound: 10
  sigma_global_upper_bound: 2.0

realism_targets:
  p_zero_weight_ranges_by_account_group:
    DEPOSIT_PRIMARY: { min: 0.00, max: 0.08 }
    SAVINGS: { min: 0.30, max: 0.95 }
    CREDIT: { min: 0.15, max: 0.90 }
    LOAN: { min: 0.60, max: 0.99 }
  sigma_ranges_by_account_group:
    DEPOSIT_PRIMARY: { min: 0.05, max: 0.80 }
    SAVINGS: { min: 0.30, max: 1.60 }
    CREDIT: { min: 0.40, max: 1.80 }
    LOAN: { min: 0.20, max: 1.20 }
  K_max_ranges_by_account_group:
    DEPOSIT_PRIMARY: { min: 1, max: 3 }
    SAVINGS: { min: 2, max: 6 }
    CREDIT: { min: 1, max: 6 }
    LOAN: { min: 1, max: 3 }
  min_fraction_of_rules_with_sigma_ge: { sigma: 0.6, frac: 0.30 }
```

---

## 11) Acceptance checklist (MUST)

### 11.1 Contract pins

* manifest_key / path / schema_ref match the 6A contracts.

### 11.2 Structural strictness

* YAML parses.
* Unknown keys absent at every level.
* Token-less (no timestamps/UUIDs/digests).
* No YAML anchors/aliases.
* Lists sorted deterministically:

  * `rules` sorted by `(party_type, account_type)` ascending
  * `supported_count_models` sorted by `count_model_id`

### 11.3 Taxonomy compatibility

* Every `account_type` referenced exists in `taxonomy_account_types_6A`. 
* Every `party_type` referenced is in party taxonomy. 

### 11.4 Feasibility guards (prevents S2 hard fails)

* For any account_type that product-mix can allocate with positive targets:

  * `p_zero_weight < 1`
  * `K_max >= 1`
  * `weight_floor_eps > 0`
* No rule violates global bounds (`K_max_global_upper_bound`, `sigma_global_upper_bound`).

### 11.5 Alignment with S2 allocation invariants

* Parameters must allow non-zero `W_total` wherever `N_acc(c)>0`, otherwise S2 will fail by design. 

---

