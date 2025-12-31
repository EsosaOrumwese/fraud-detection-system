# Authoring Guide — `merchant_role_priors_6A` (`mlr.6A.s5.prior.merchant_roles`, v1)

## 0) Purpose

`merchant_role_priors_6A` is the **sealed, token-less, RNG-free** control-plane artefact that tells **6A.S5** how to assign **static fraud posture** to **Layer-1 merchants** (one row per `merchant_id`) in `s5_merchant_fraud_roles_6A`.

S5’s merchant posture is **static** (no per-arrival behaviour), and must be derived only from **sealed inputs**. S5 may use *coarse aggregates* as context (e.g., “high-volume MCCs”), but must not depend on the arrival stream itself.

---

## 1) Contract identity (binding pins)

From the 6A v1 contract surface:

* **manifest_key:** `mlr.6A.s5.prior.merchant_roles` 
* **dataset_id:** `prior_merchant_roles_6A`
* **path:** `config/layer3/6A/priors/merchant_role_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/merchant_role_priors_6A`
* **consumed_by:** `6A.S0`, `6A.S5`

Token-less posture: **no timestamps, UUIDs, or digests in-file**; S0 seals by exact bytes.

---

## 2) What S5 must produce (merchant posture output)

S5’s merchant posture surface (`s5_merchant_fraud_roles_6A`) is produced by `6A.S5` and depends (minimally) on upstream `outlet_catalogue` and this prior.

The S5 spec’s role examples for merchants include:
`NORMAL`, `COLLUSIVE`, `HIGH_RISK_MCC`, `MSB`, etc., conditioned on MCC, region, and volume/graph features.

---

## 3) Allowed conditioning signals (what this prior is allowed to reference)

This policy MUST be written so Codex can implement it **without hidden data dependencies**. It must declare an explicit whitelist of features S5 is allowed to compute from sealed inputs.

### 3.1 Required feature sources (v1)

S5 may derive the following per-merchant aggregates deterministically (examples):

* **From `mlr.1A.output.outlet_catalogue`** (row-level aggregate):

  * `n_sites_total(m)`
  * `n_countries(m)` (distinct `legal_country_iso`)
  * `cross_border_share(m) = 1 - (n_sites_home / n_sites_total)` (home inferred or provided; see §3.3)
  * `top_country_iso(m)` by site mass (tie-break `country_iso` asc)

* **Required (v1; must be sealed row-level input):**

  * `mcc(m)`, `channel(m)`, `home_country_iso(m)` from the sealed merchant universe (ingress).
    *(If these are absent, S5 MUST FAIL CLOSED; v1 does not support MCC-free merchant posture.)*

### 3.2 Forbidden (must not be used)

* Individual arrivals from `arrival_events_5B` (no per-event logic). 
* Any 6B outputs (flows/labels).

### 3.3 Home-country resolution (MUST be pinned)

If `home_country_iso` is not directly available for a merchant, define:

* `home_country_iso = top_country_iso` (by outlet mass), tie-break by `country_iso` lexicographic ascending.

This makes `cross_border_share` well-defined without extra inputs.

---

## 4) Non-toy modelling goals (what “realism” means here)

This prior must yield a merchant world where:

* Most merchants are `NORMAL`.
* A **small fraction** are `HIGH_RISK_MCC` / `MSB` and concentrated in plausible MCC classes.
* A **very small fraction** are `COLLUSIVE`, and *optionally* appear in **clusters** (not isolated singletons).
* Merchant posture is **not uniform across regions/countries**, but also not absurdly concentrated in one place.

---

## 5) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `merchant_role_priors_6A`)
3. `policy_version` (string; MUST be `v1`)
4. `role_vocabulary` (list of objects)
5. `risk_tier_vocabulary` (list of objects)
6. `feature_whitelist` (object)
7. `mcc_classification` (object)
8. `risk_score_model` (object)
9. `risk_tier_thresholds` (object)
10. `role_probability_model` (object)
11. `collusion_cluster_model` (object)
12. `constraints` (object)
13. `realism_targets` (object)
14. `notes` (optional string)

Unknown keys: **INVALID**.

Formatting MUST:

* token-less (no timestamps/digests)
* no YAML anchors/aliases
* deterministic ordering (see §11).

---

## 6) Role vocabulary (MUST)

### 6.1 Minimum v1 roles (MUST include)

* `NORMAL`
* `HIGH_RISK_MCC`
* `MSB`
* `COLLUSIVE`

(These mirror the S5 spec’s merchant examples.)

Each role entry MUST include:

* `role_id`
* `label`
* `description`
* `severity_rank` (int; increasing)

### 6.2 Optional v1 roles (ONLY if you need them)

* `RISKY_CROSS_BORDER` (driven by `cross_border_share` / `n_countries`)
* `VERY_HIGH_VOLUME` (driven by `n_sites_total` band)
* `VIRTUAL_EDGE_OPERATOR` (only if you seal and use virtual merchant metadata)

---

## 7) Feature whitelist (must make Codex autonomous)

`feature_whitelist` MUST declare:

* `required_sources`: list of dataset manifest keys (min: `mlr.1A.output.outlet_catalogue`)
* `allowed_features`: explicit list of feature names S5 may compute, e.g.
  `n_sites_total`, `n_countries`, `cross_border_share`, `mcc`, `channel`, `home_country_iso`
* `fallbacks`: pinned rules for missing optional features (e.g., `home_country_iso` fallback in §3.3)

If any feature is declared “required” but cannot be computed from sealed inputs, S5 must **FAIL CLOSED**.

---

## 8) MCC classification (guided, not hand-wavy)

Because S5’s merchant roles are explicitly conditioned on MCC-like semantics in the spec, v1 MUST include a deterministic MCC→class mapping that does not require external internet lookups.

`mcc_classification` MUST include:

* `mcc_class_vocab`: list of class ids (e.g., `GENERAL_RETAIL`, `TRAVEL`, `DIGITAL_GOODS`, `MONEY_SERVICES`, `HOSPITALITY`, `FOOD_BEV`, `HIGH_CHARGEBACK_RISK`)
* `mcc_to_class_rules`: ordered rules (first match wins), each with:

  * `rule_id`
  * `match`: either `{mcc_values:[...]}` or `{mcc_ranges:[{min,max},...]}`
  * `mcc_class`
* `unknown_mcc_policy`: MUST be `FAIL` in v1 (no silent “OTHER” class)

This is what prevents toy “random MCC risk” and keeps it reproducible.

---

## 9) Risk score + tier (deterministic)

### 9.1 `risk_score_model` (MUST)

v1 pins a bounded deterministic score:

* `risk_score = clamp( base + Σ_i weight_i * (x_i - ref_i), 0, 1 )`

Required features (recommended minimal set):

* `mcc_risk_weight(mcc_class)` (from `mcc_classification`)
* `cross_border_share` (from outlet catalogue)
* `log_size_score = log1p(n_sites_total) / log1p(size_ref)` (bounded)
* optional `n_countries_score` (bounded)

### 9.2 `risk_tier_thresholds` (MUST)

Define tiers (recommended consistent with other entity tiers):
`LOW`, `STANDARD`, `ELEVATED`, `HIGH`, with deterministic thresholds.

---

## 10) Role probability model (how roles are drawn)

S5 assigns roles stochastically using its RNG families; this prior supplies the target distributions.

### 10.1 Mode (v1 pinned)

`mode: by_mcc_class_and_risk_tier_v1`

Provide `pi_role_by_class_and_tier`:

* key: `(mcc_class, risk_tier)`
* value: list of `{role_id, prob}` summing to 1

Rules:

* every `role_id` must exist in vocabulary
* probabilities in [0,1], sum to 1 (tolerance 1e-12)

### 10.2 Context nudges (optional, bounded)

Allow bounded multiplicative nudges such as:

* if `cross_border_share >= 0.6` → increase `COLLUSIVE` and/or `RISKY_CROSS_BORDER`
* if `n_sites_total` in top band → increase `COLLUSIVE` slightly (only if you want that)

Pinned semantics:

* multiply unnormalised probabilities
* clip multipliers to `[min,max]`
* renormalise

---

## 11) Collusion cluster model (recommended for realism)

To avoid toy “independent Bernoulli collusive merchants”, v1 SHOULD allow cluster-correlated collusion.

`collusion_cluster_model` MUST include:

* `enabled` (bool)
* if enabled:

  * `cluster_key`: e.g. `[home_country_iso, mcc_class]`
  * `target_collusive_fraction_by_tier` (risk_tier → fraction)
  * `cluster_size_distribution`:

    * `model_id ∈ {geometric_capK_v1, zipf_capK_v1}`
    * parameters + caps (`min_k`, `max_k`)
  * `min_clusters_per_large_country` (int; applied if country has ≥ N merchants)

Operationally:

* S5 selects collusive merchants by first selecting clusters (using RNG), then filling cluster members from eligible merchants in the same cluster_key, ensuring at least some multi-merchant clusters.

If `enabled: false`, S5 assigns `COLLUSIVE` independently using the probability model.

---

## 12) Constraints (hard fails)

`constraints` MUST include:

* `fail_on_missing_rule: true`
* `prob_dp` (recommended 12)
* `unknown_mcc_policy: FAIL`
* `max_role_share_caps_world` (role_id → max fraction)
* `min_non_normal_presence` (role_id → min fraction, at least for one non-NORMAL role so world isn’t “all normal”)
* `require_mcc_coverage: true` (every merchant must map to an mcc_class)

---

## 13) Realism targets (corridors; fail closed)

At minimum:

* `normal_fraction_range_world` ({min,max})
* `high_risk_mcc_fraction_range_world` ({min,max})
* `msb_fraction_range_world` ({min,max})
* `collusive_fraction_range_world` ({min,max})
* `msb_share_within_money_services_class_range` ({min,max})
* `region_variation`:

  * `required_if_n_countries_ge`
  * `min_delta_high_risk_fraction_between_countries`
* `collusion_cluster_realism` (if cluster model enabled):

  * `min_fraction_collusive_in_clusters_size_ge_2`

These are what enforce “not toy”.

---

## 14) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: merchant_role_priors_6A
policy_version: v1

role_vocabulary:
  - { role_id: COLLUSIVE,    label: Collusive,    description: "Merchant plausibly engaged in collusion.", severity_rank: 3 }
  - { role_id: HIGH_RISK_MCC,label: High-risk MCC,description: "Merchant in a higher-risk MCC class.",      severity_rank: 2 }
  - { role_id: MSB,          label: MSB,          description: "Money-services posture.",                   severity_rank: 2 }
  - { role_id: NORMAL,       label: Normal,       description: "Baseline merchant posture.",               severity_rank: 0 }

risk_tier_vocabulary:
  - { tier_id: LOW,      label: Low,      description: "Low static posture.",      severity_rank: 0 }
  - { tier_id: STANDARD, label: Standard, description: "Typical posture.",         severity_rank: 1 }
  - { tier_id: ELEVATED, label: Elevated, description: "Elevated posture.",        severity_rank: 2 }
  - { tier_id: HIGH,     label: High,     description: "High static posture.",     severity_rank: 3 }

feature_whitelist:
  required_sources: [mlr.1A.output.outlet_catalogue, mlr.input.transaction_schema.merchant_ids]
  allowed_features: [n_sites_total, n_countries, cross_border_share, home_country_iso, mcc, channel]
  fallbacks:
    home_country_iso: "top_country_iso_by_outlet_mass (tie-break country_iso asc)"

mcc_classification:
  mcc_class_vocab: [GENERAL_RETAIL, TRAVEL, HOSPITALITY, DIGITAL_GOODS, MONEY_SERVICES, HIGH_CHARGEBACK_RISK]
  mcc_to_class_rules:
    - rule_id: MSB_SET
      match: { mcc_values: [4829, 6012, 6051] }
      mcc_class: MONEY_SERVICES
    - rule_id: DIGITAL_SET
      match: { mcc_values: [5734, 5817] }
      mcc_class: DIGITAL_GOODS
    - rule_id: DEFAULT
      match: { mcc_ranges: [{min: 0, max: 9999}] }
      mcc_class: GENERAL_RETAIL
  unknown_mcc_policy: FAIL

risk_score_model:
  base: 0.35
  features:
    - { name: mcc_class_risk,     ref: 0.0, weight: 0.35 }
    - { name: cross_border_share, ref: 0.1, weight: 0.25 }
    - { name: log_size_score,     ref: 0.2, weight: 0.20 }
    - { name: n_countries_score,  ref: 0.1, weight: 0.20 }
  mcc_class_risk_weights:
    GENERAL_RETAIL: 0.05
    TRAVEL: 0.10
    HOSPITALITY: 0.10
    DIGITAL_GOODS: 0.18
    HIGH_CHARGEBACK_RISK: 0.25
    MONEY_SERVICES: 0.30
  size_ref_sites: 50

risk_tier_thresholds:
  tiers_in_order: [LOW, STANDARD, ELEVATED, HIGH]
  thresholds: { LOW_max: 0.25, STANDARD_max: 0.65, ELEVATED_max: 0.85, HIGH_max: 1.00 }

role_probability_model:
  mode: by_mcc_class_and_risk_tier_v1
  pi_role_by_class_and_tier:
    MONEY_SERVICES:
      LOW:      [{role_id: NORMAL, prob: 0.92}, {role_id: MSB, prob: 0.07}, {role_id: HIGH_RISK_MCC, prob: 0.009}, {role_id: COLLUSIVE, prob: 0.001}]
      STANDARD: [{role_id: NORMAL, prob: 0.85}, {role_id: MSB, prob: 0.12}, {role_id: HIGH_RISK_MCC, prob: 0.025}, {role_id: COLLUSIVE, prob: 0.005}]
      ELEVATED: [{role_id: NORMAL, prob: 0.70}, {role_id: MSB, prob: 0.20}, {role_id: HIGH_RISK_MCC, prob: 0.070}, {role_id: COLLUSIVE, prob: 0.030}]
      HIGH:     [{role_id: NORMAL, prob: 0.55}, {role_id: MSB, prob: 0.25}, {role_id: HIGH_RISK_MCC, prob: 0.120}, {role_id: COLLUSIVE, prob: 0.080}]
    GENERAL_RETAIL:
      LOW:      [{role_id: NORMAL, prob: 0.9990}, {role_id: HIGH_RISK_MCC, prob: 0.0008}, {role_id: COLLUSIVE, prob: 0.0002}]
      STANDARD: [{role_id: NORMAL, prob: 0.9960}, {role_id: HIGH_RISK_MCC, prob: 0.0030}, {role_id: COLLUSIVE, prob: 0.0010}]
      ELEVATED: [{role_id: NORMAL, prob: 0.985 }, {role_id: HIGH_RISK_MCC, prob: 0.010 }, {role_id: COLLUSIVE, prob: 0.005 }]
      HIGH:     [{role_id: NORMAL, prob: 0.960 }, {role_id: HIGH_RISK_MCC, prob: 0.025 }, {role_id: COLLUSIVE, prob: 0.015 }]
  nudges:
    - if_feature: "cross_border_share >= 0.60"
      multiply_roles: { COLLUSIVE: 1.30, NORMAL: 0.92 }
      clip_multiplier: { min: 0.70, max: 1.80 }

collusion_cluster_model:
  enabled: true
  cluster_key: [home_country_iso, mcc_class]
  target_collusive_fraction_by_tier: { LOW: 0.0002, STANDARD: 0.0010, ELEVATED: 0.0040, HIGH: 0.0100 }
  cluster_size_distribution:
    model_id: zipf_capK_v1
    min_k: 2
    max_k: 50
    alpha: 1.25
  min_clusters_per_large_country: 3
  large_country_threshold_merchants: 5000

constraints:
  fail_on_missing_rule: true
  prob_dp: 12
  unknown_mcc_policy: FAIL
  require_mcc_coverage: true
  max_role_share_caps_world: { COLLUSIVE: 0.01, MSB: 0.02, HIGH_RISK_MCC: 0.15 }
  min_non_normal_presence: { HIGH_RISK_MCC: 0.01 }

realism_targets:
  normal_fraction_range_world:        { min: 0.85,   max: 0.995 }
  high_risk_mcc_fraction_range_world: { min: 0.01,   max: 0.15 }
  msb_fraction_range_world:           { min: 0.001,  max: 0.02 }
  collusive_fraction_range_world:     { min: 0.0002, max: 0.01 }
  msb_share_within_money_services_class_range: { min: 0.10, max: 0.80 }
  region_variation:
    required_if_n_countries_ge: 5
    min_delta_high_risk_fraction_between_countries: 0.01
  collusion_cluster_realism:
    min_fraction_collusive_in_clusters_size_ge_2: 0.70
```

---

## 15) Acceptance checklist (MUST)

* **Contract pins match** v1 (manifest_key/path/schema_ref).
* Token-less (no timestamps/UUIDs/digests); no YAML anchors/aliases. 
* `mcc_to_class_rules` covers all MCCs present in sealed merchant universe; unknown MCC ⇒ FAIL.
* For every `(mcc_class, risk_tier)` you can encounter, probabilities sum to 1.
* Realism corridors pass (world-level ranges, MSB concentrated in MONEY_SERVICES, collusive not absurdly common, non-trivial country variation when multi-country).
* If `collusion_cluster_model.enabled`, cluster realism rule passes (most collusive merchants appear in clusters, not isolated singletons).

---
