# Authoring Guide — `instrument_per_account_priors_6A` (`mlr.6A.prior.instrument_per_account`, v1)

## 0) Purpose

`instrument_per_account_priors_6A` is the **sealed, deterministic prior pack** that 6A.S3 uses to model the **discrete per-account distribution**:

> **P(k instruments of type X | account_cell)**

including **zero-inflation** and **hard caps/minimums**, and to derive **non-negative per-account weights** `w_a(c)` used when allocating `N_instr(c)` instruments across the concrete accounts in a cell.

This is **not** the same as the *instrument mix* priors:

* `instrument_mix_priors_6A` decides **how many instruments exist per account cell** and how that total splits across instrument types/schemes.
* `instrument_per_account_priors_6A` decides **how concentrated that allocation is across accounts** and enforces per-account min/max constraints (e.g., “no more than K cards per account”).

Non-toy requirement: this pack must create realistic heterogeneity (some accounts get multiple credentials; many get none of a given type) without “everyone gets exactly one of everything”.

---

## 1) File identity (binding)

From the 6A contract surface:

* **manifest_key:** `mlr.6A.prior.instrument_per_account` 
* **dataset_id:** `prior_instrument_per_account_6A` 
* **path:** `config/layer3/6A/priors/instrument_per_account_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/instrument_per_account_priors_6A`
* **status:** `required` and consumed by **`6A.S0`** and **`6A.S3`**

**Token-less posture:** no timestamps, UUIDs, or embedded digests; 6A.S0 seals by exact bytes and records `sha256_hex` in `sealed_inputs_6A`.

---

## 2) Dependencies (MUST exist & be compatible)

This prior must be authored against the sealed vocab + mix priors S3 uses:

* `taxonomy_instrument_types_6A` (instrument_type / scheme / brand_tier / token_type vocab)
* `taxonomy_account_types_6A` (account_type vocab; eligibility constraints by owner kind/party type)
* `taxonomy_party_6A` (region_id / party_type / segment_id universe)
* `instrument_mix_priors_6A` (the domain of instrument cells and the continuous targets `N_instr_target`)

S3 treats “instrument-per-account distributions” as **REQUIRED row-level priors**; if missing/invalid, S3 must fail.

---

## 3) How 6A.S3 uses this prior (pinned semantics)

### 3.1 Cell axes

S3 plans over:

* **account cell**
  `b_acc = (region_id, party_type, segment_id, account_type)`

* **instrument cell**
  `c_instr = (region_id, party_type, segment_id, account_type, instrument_type[, scheme])` (scheme is included only if the design chooses it)

### 3.2 Where this prior enters

In Phase 4 (“Allocate instruments to specific accounts”), S3 must:

1. collect the concrete accounts belonging to the relevant account cell;
2. compute non-negative weights `w_a(c_instr)` per account using this prior (+ linkage rules);
3. normalise to probabilities `π_a(c_instr) = w_a / Σ w_a`;
4. sample account assignments for each instrument instance using `instrument_allocation_sampling`;
5. enforce hard per-account constraints (min/max instruments per account), failing if infeasible.

Hard fail rule:

* If `Σ w_a == 0` while `N_instr(c_instr) > 0`, S3 must fail (prior/linkage inconsistency).

---

## 4) What this prior MUST provide (v1)

For every instrument cell that can be produced by `instrument_mix_priors_6A`, this file must define:

1. **A per-account count model** for that `(party_type, account_type, instrument_type[,scheme_scope])`, describing:

   * structural zero probability (many accounts have none of that instrument),
   * how multi-instrument accounts occur (e.g., multiple virtual cards),
   * a hard cap `K_max`,
   * optional hard minimum `K_min` (for mandatory instruments).

2. **A deterministic weight recipe** that maps an account to a non-negative weight:

   * `w_a = 0` for ineligible/structural zero accounts,
   * otherwise `w_a` is heavy-tailed (lognormal-like) to create realistic concentration.

This is RNG-free and token-less; RNG happens only when S3 samples from `π_a`.

---

## 5) Supported count models (MUST be fixed set in v1)

`count_model_id` is an enum. v1 supports exactly:

* `bernoulli_cap1_v1`
  k ∈ {0,1}

* `zi_poisson_capK_v1`
  structural zero with probability `p_zero`, else Poisson(mean=μ), hard-cap to `K_max`

* `zi_nb2_capK_v1`
  structural zero with probability `p_zero`, else NB2(mean=μ, dispersion κ), hard-cap to `K_max`

Any other model id ⇒ **FAIL CLOSED** (invalid priors).

**Mean-consistency law (MUST):** This prior must be mean-compatible with `λ_instr_per_account` coming from instrument mix priors. S3 may set μ via:

`μ = λ / max(1e-12, (1 - p_zero))`

and then enforce feasibility vs `K_max` (fail if impossible rather than silently clamping).

---

## 6) Deterministic weight construction (v1 pinned)

S3 needs per-account weights `w_a(c_instr)`; v1 pins a deterministic, RNG-free recipe so we don’t explode RNG event volume.

For a given `(manifest_fingerprint, parameter_hash, account_id, instrument_type, scheme_scope)`:

1. Derive two deterministic uniforms `u0,u1 ∈ (0,1)` using your standard **hash→open-interval** mapping (same posture as other priors).
2. Structural zero gate:

   * if `u0 < p_zero_weight` then `w_a = 0`
3. Positive weight:

   * `z = normal_icdf(u1)` (deterministic libm profile)
   * `normal_icdf` MUST use the engine's pinned normal primitive under numeric policy (open-interval U(0,1) + deterministic libm; see S0.3.4-S0.3.5)
   * `g = exp(sigma * z - 0.5*sigma^2)` (mean 1)
   * `w_a = max(weight_floor_eps, g)`

Optional deterministic tilts (recommended):

* multiply `p_zero_weight` and/or `sigma` by bounded multipliers based on **segment profiles** (digital_affinity → more virtual/token; cash_affinity → fewer wallets) and/or static account attributes (`product_family`). S3 explicitly allows weights to depend on segment, account_type, region, product_family, and holdings context.

---

## 7) YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be 1)
2. `prior_id` (string; MUST be `instrument_per_account_priors_6A`)
3. `prior_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `scheme_scope_mode` (enum)
6. `supported_count_models` (list)
7. `rules` (list)
8. `segment_feature_tilts` (optional list)
9. `constraints` (object)
10. `realism_targets` (object)
11. `notes` (optional string)

Unknown keys: **INVALID**.

### 7.1 `bindings` (MUST)

* `party_taxonomy_ref: taxonomy_party_6A`
* `account_taxonomy_ref: taxonomy_account_types_6A`
* `instrument_taxonomy_ref: taxonomy_instrument_types_6A`
* `instrument_mix_ref: prior_instrument_mix_6A`

### 7.2 `scheme_scope_mode` (MUST)

Defines whether rules are keyed by scheme:

* `NONE` — rules keyed by `(party_type, account_type, instrument_type)` only
* `SCHEME_KIND` — rules keyed by `(…, instrument_type, scheme_kind)` where scheme_kind ∈ {CARD_NETWORK, BANK_RAIL, WALLET_NETWORK}
* `SCHEME_ID` — rules keyed by `(…, instrument_type, scheme)` (most granular; usually not needed)

This must align with how `instrument_mix_priors_6A` treats scheme (in-cell vs attribute-only).

### 7.3 `rules[]` (MUST)

Each rule object MUST contain:

* `party_type` (RETAIL|BUSINESS|OTHER)
* `account_type` (valid account taxonomy id)
* `instrument_type` (valid instrument taxonomy id)
* optional `scheme_key` (only if scheme_scope_mode != NONE)
* `count_model_id` (pinned enum)
* `hard_min_per_account` (int ≥ 0)
* `hard_max_per_account` (int ≥ 1)
* `params` (object)

`params` required keys (all models):

* `p_zero` (float in [0,1)) *(distribution structural zero)*
* `p_zero_weight` (float in [0,1]) *(weight gate structural zero)*
* `sigma` (float ≥ 0)
* `weight_floor_eps` (float > 0)

Model-specific:

* if `zi_nb2_capK_v1`: `kappa` (float > 0)

Hard rules:

* `hard_max_per_account` MUST be ≥ `hard_min_per_account`
* if `hard_min_per_account > 0` then `p_zero` MUST be 0 (mandatory presence cannot be structurally zero)
* `hard_max_per_account` SHOULD be small for “physical” instruments (e.g. 1–3), larger only for virtual credentials if you want that behaviour.

### 7.4 `segment_feature_tilts[]` (optional, recommended)

Each tilt applies bounded multipliers based on segment scores from `prior_segmentation_6A`:

* `feature` (e.g. `digital_affinity`, `cross_border_propensity`, `stability_score`)
* `instrument_type`
* `p_zero_weight_multiplier_by_feature` (float, bounded by clip)
* `sigma_multiplier_by_feature` (float, bounded by clip)
* `clip` `{min,max}`

This is how Codex can build realistic variation without hand-authoring per-segment tables.

### 7.5 `constraints` (MUST)

Required:

* `coverage_mode: fail_on_missing_rule`
* `max_sigma_global` (float; hard fail if exceeded)
* `max_hard_max_global` (int; hard fail if exceeded)
* `require_nonzero_weight_when_mandatory: true`
* `forbid_rules_for_ineligible_pairs: true`
  *(if an account_type cannot own an instrument_type by taxonomy/linkage, S3 must treat it as invalid config to even specify a rule)*

### 7.6 `realism_targets` (MUST)

Corridors to avoid toy behaviour:

* `p_zero_weight_ranges_by_instrument_group` (group → {min,max})
* `sigma_ranges_by_instrument_group` (group → {min,max})
* `hard_max_ranges_by_instrument_group` (group → {min,max})
* `min_fraction_rules_with_sigma_ge` `{sigma, frac}`
* `mandatory_coverage_rules` (list of requirements like `{account_type, instrument_type, hard_min_per_account}`)

Instrument groups are either:

* derived from instrument taxonomy class (CARD/BANK_ACCOUNT/WALLET/TOKEN), or
* explicitly defined in this file (recommended if you want tighter corridors).

---

## 8) Authoring procedure (Codex-ready)

1. **Load taxonomies + instrument mix priors**
   Enumerate every `(party_type, account_type, instrument_type[,scheme_scope])` that can appear.

2. **Partition into instrument groups** (example)

* `CARD_PHYSICAL`, `CARD_VIRTUAL`, `BANK_HANDLE`, `WALLET_TOKEN`, `MANDATE/OTHER`

3. **Choose mandatory rules**

* If your design expects “every current account must have ≥1 debit instrument/handle”, encode it here as `hard_min_per_account=1` (and `p_zero=0`) OR ensure the separate linkage rules enforce it. S3 explicitly treats such constraints as hard requirements and must fail if infeasible.

4. **Pick distribution parameters by group** (non-toy defaults)

* Physical debit card: low `p_zero` (0–0.05), `hard_max` 2–3, moderate sigma (0.4–0.9)
* Virtual card: higher `p_zero` (0.2–0.8), `hard_max` 3–8, higher sigma (0.7–1.6)
* Bank handle: low `p_zero` (0–0.2), `hard_max` 1–2
* Wallet token: medium/high `p_zero`, moderate/high sigma

5. **Add feature tilts** (recommended)

* Higher `digital_affinity` → lower `p_zero_weight` and higher `sigma` for virtual/token instruments.
* Higher `stability_score` → slightly higher weights for long-lived instruments (bank handles, physical cards).

6. **Run acceptance checks** (below) and fail closed on any violation.

---

## 9) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
prior_id: instrument_per_account_priors_6A
prior_version: v1

bindings:
  party_taxonomy_ref: taxonomy_party_6A
  account_taxonomy_ref: taxonomy_account_types_6A
  instrument_taxonomy_ref: taxonomy_instrument_types_6A
  instrument_mix_ref: prior_instrument_mix_6A

scheme_scope_mode: NONE

supported_count_models:
  - count_model_id: bernoulli_cap1_v1
    required_params: [p_zero, p_zero_weight, sigma, weight_floor_eps]
    description: "k in {0,1}; mandatory via hard_min=1."
  - count_model_id: zi_poisson_capK_v1
    required_params: [p_zero, p_zero_weight, sigma, weight_floor_eps]
    description: "ZI Poisson with hard cap."
  - count_model_id: zi_nb2_capK_v1
    required_params: [p_zero, kappa, p_zero_weight, sigma, weight_floor_eps]
    description: "ZI NB2 with hard cap."

rules:
  - party_type: RETAIL
    account_type: RETAIL_CURRENT_BASIC
    instrument_type: RETAIL_DEBIT_CARD_PHYSICAL
    count_model_id: zi_poisson_capK_v1
    hard_min_per_account: 1
    hard_max_per_account: 2
    params: { p_zero: 0.0, p_zero_weight: 0.0, sigma: 0.55, weight_floor_eps: 1.0e-6 }

  - party_type: RETAIL
    account_type: RETAIL_CREDIT_CARD_STANDARD
    instrument_type: RETAIL_CREDIT_CARD_VIRTUAL
    count_model_id: zi_nb2_capK_v1
    hard_min_per_account: 0
    hard_max_per_account: 6
    params: { p_zero: 0.55, kappa: 1.8, p_zero_weight: 0.50, sigma: 1.10, weight_floor_eps: 1.0e-6 }

segment_feature_tilts:
  - feature: digital_affinity
    instrument_type: RETAIL_CREDIT_CARD_VIRTUAL
    p_zero_weight_multiplier_by_feature: 0.85
    sigma_multiplier_by_feature: 1.10
    clip: { min: 0.60, max: 1.60 }

constraints:
  coverage_mode: fail_on_missing_rule
  max_sigma_global: 2.2
  max_hard_max_global: 12
  require_nonzero_weight_when_mandatory: true
  forbid_rules_for_ineligible_pairs: true

realism_targets:
  p_zero_weight_ranges_by_instrument_group:
    CARD_PHYSICAL: { min: 0.00, max: 0.10 }
    CARD_VIRTUAL:  { min: 0.15, max: 0.90 }
  sigma_ranges_by_instrument_group:
    CARD_PHYSICAL: { min: 0.20, max: 1.10 }
    CARD_VIRTUAL:  { min: 0.50, max: 1.90 }
  hard_max_ranges_by_instrument_group:
    CARD_PHYSICAL: { min: 1, max: 3 }
    CARD_VIRTUAL:  { min: 2, max: 10 }
  min_fraction_rules_with_sigma_ge: { sigma: 0.7, frac: 0.30 }
  mandatory_coverage_rules:
    - { account_type: RETAIL_CURRENT_BASIC, instrument_type: RETAIL_DEBIT_CARD_PHYSICAL, hard_min_per_account: 1 }
```

*(IDs must match your taxonomies; this is a shape example.)*

---

## 10) Acceptance checklist (MUST)

### 10.1 Contract pins

* manifest_key / dataset_id / path / schema_ref match the 6A contracts.

### 10.2 Structural strictness

* YAML parses cleanly.
* Unknown keys absent everywhere.
* Token-less: no timestamps/UUIDs/digests.
* No YAML anchors/aliases.
* Deterministic ordering:

  * `rules` sorted by `(party_type, account_type, instrument_type, scheme_key?)`.

### 10.3 Coverage & taxonomy compatibility

* Every referenced `account_type` exists in `taxonomy_account_types_6A`. 
* Every referenced `instrument_type` exists in `taxonomy_instrument_types_6A`. 
* For every instrument cell that instrument-mix can produce, a corresponding rule exists (fail on missing).

### 10.4 Feasibility (prevents S3 hard fails)

* If `hard_min_per_account > 0` then `p_zero == 0` and `p_zero_weight == 0`.
* If `N_instr(c) > 0` for any cell, weights cannot be identically zero (`Σ w_a > 0`) unless S3 is supposed to fail (it is). 

### 10.5 Non-toy corridors

* Corridors in `realism_targets` are satisfied (σ diversity, reasonable zero rates, caps).
* At least `min_fraction_rules_with_sigma_ge.frac` of rules have σ ≥ threshold.

---

## 11) Change control (MUST)

Any change that affects:

* which pairs are mandatory (`hard_min_per_account`),
* caps (`hard_max_per_account`),
* supported count models or parameter meanings,

is a **breaking behavioural change** for S3 and must be versioned (new file name / v2) and reflected in validation expectations.
