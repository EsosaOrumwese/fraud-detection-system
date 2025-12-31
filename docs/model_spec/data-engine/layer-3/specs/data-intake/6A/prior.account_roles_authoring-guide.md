# Authoring Guide — `account_role_priors_6A` (`mlr.6A.s5.prior.account_roles`, v1)

## 0) Purpose

`account_role_priors_6A` is the **sealed, token-less, RNG-free** control-plane artefact that tells **6A.S5** how to assign **static fraud posture** to **accounts** (one row per `account_id`) in `s5_account_fraud_roles_6A`.

This prior must be **non-toy**:

* Most accounts are clean, but a small, structured fraction are high-risk or mule-like.
* Risk correlates plausibly with **account type** and **sealed context** (segment traits, holdings, device/IP exposure).
* The policy is **fully guided** so Codex can author it without “making up realism” ad hoc.

---

## 1) Contract identity (binding pins)

From the 6A v1 contract surface:

* **manifest_key:** `mlr.6A.s5.prior.account_roles`
* **dataset_id:** `prior_account_roles_6A`
* **path:** `config/layer3/6A/priors/account_role_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/account_role_priors_6A`
* **partitioning:** `[]` (single file, no partitions)
* **consumed_by:** `6A.S0`, `6A.S5`

Token-less posture:

* No timestamps, UUIDs, or digests inside the file.
* S0 seals it by exact bytes (`sha256_hex`) in `sealed_inputs_6A`.

---

## 2) What S5 must produce (for context)

S5 writes `s5_account_fraud_roles_6A` with at least:

* `manifest_fingerprint`, `parameter_hash`, `seed`
* `account_id` (FK to `s2_account_base_6A`)
* optional `owner_party_id` (convenience FK)
* `fraud_role_account` (enum; examples include `CLEAN_ACCOUNT`, `MULE_ACCOUNT`, `HIGH_RISK_ACCOUNT`, `DORMANT_RISKY`)
* optional `static_risk_tier_account`

This guide defines the **policy inputs** that make that output realistic and auditable.

---

## 3) Scope and authority boundaries

### In scope (this file owns)

* **The role vocabulary** S5 is allowed to emit for accounts.
* **The deterministic mapping** from sealed context → `risk_score_account` → `static_risk_tier_account`.
* **The probability model** `π(fraud_role_account | cell, tier, context)`.

### Out of scope (must not be here)

* Dynamic fraud events, campaigns, labels (6B owns behaviour).
* Any trained/learned models (this is authored, deterministic).
* Any attempt to alter upstream “truth” (S1–S4 are sealed inputs). 

---

## 4) Allowed conditioning signals (must be sealed / derivable)

S5 may condition account roles on **coarse, deterministic features** derivable from sealed 6A outputs plus taxonomies/priors.

### 4.1 From `s2_account_base_6A` (account identity + product facts)

* `account_type`, `product_family`, `ledger_class` (or equivalents)
* `currency_policy` / `is_multi_currency` if present
* `owner_party_id` (and/or `owner_merchant_id` if your model allows it) 

### 4.2 From `s3_instrument_base_6A` + link tables (holdings indicators)

Derived booleans/buckets per account:

* `has_card_instrument`
* `has_virtual_instrument`
* `n_instruments_bucket`

### 4.3 From `s4_device_links_6A` / `s4_ip_links_6A` (via owner party)

Derived booleans/buckets per owner party (then inherited by account for scoring):

* `has_any_anonymizer_ip` (e.g., ip_type `VPN_PROXY` / `DATACENTRE` or a risk flag)
* `has_any_high_risk_device`
* `ip_exposure_bucket`, `n_devices_bucket`

### 4.4 From S5 party posture (optional but recommended for coherence)

* `owner_party_fraud_role` and/or `owner_party_risk_tier` (already being assigned in S5)
  This supports “mule parties tend to have mule accounts” without hard-coding identities.

Fail-closed rule:

* If the policy declares a feature as **required** and S5 cannot compute it from sealed inputs, S5 must FAIL (no silent defaults).

---

## 5) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `account_role_priors_6A`)
3. `policy_version` (string; MUST be `v1`)
4. `role_vocabulary` (list)
5. `risk_tier_vocabulary` (list)
6. `cell_definition` (object)
7. `risk_score_model` (object)
8. `risk_tier_thresholds` (object)
9. `role_probability_model` (object)
10. `constraints` (object)
11. `realism_targets` (object)
12. `notes` (optional string)

Unknown keys: **INVALID**.

Formatting MUST:

* token-less (no timestamps/digests)
* no YAML anchors/aliases
* deterministic ordering (vocab + tables sorted by key)

---

## 6) Role vocabulary (MUST)

### 6.1 Minimum required roles (v1 MUST include)

These align with S5’s expected enum examples: 

* `CLEAN_ACCOUNT`
* `MULE_ACCOUNT`
* `HIGH_RISK_ACCOUNT`
* `DORMANT_RISKY`

### 6.2 Optional roles (v1 MAY include)

Only add if you intend S5/6B to use them:

* `COMPROMISED_ACCOUNT` (account-takeover prone posture)
* `BUST_OUT_CREDIT` (credit-focused posture)
* `SYNTHETIC_ACCOUNT` (if you want account-level synthetic posture distinct from party)

Each role entry MUST contain:

* `role_id`, `label`, `description`
* `applicable_ledger_classes` (subset; non-empty)
* `severity_rank` (int; increasing)

---

## 7) Risk tiers (MUST)

Provide a tier set (recommend keeping consistent across entity types):

* `LOW`, `STANDARD`, `ELEVATED`, `HIGH`

Each tier entry MUST contain:

* `tier_id`, `label`, `description`, `severity_rank`

---

## 8) Cell definition (what the policy conditions on)

`cell_definition` MUST include:

* `base_cell`: `[region_id, party_type, segment_id, account_type]`
* `account_groups`: mapping `account_type → account_group_id` (e.g., `DEPOSIT_PRIMARY`, `SAVINGS`, `CREDIT_CARD`, `LOAN`, `BUSINESS_DEPOSIT`)
* `context_features_allowed`: explicit whitelist of derived features (names only; S5 defines how to compute them)

This keeps the policy “guided” and prevents sneaky hidden dependencies.

---

## 9) Risk score model (deterministic, RNG-free)

### 9.1 Pinned v1 law

Compute `risk_score_account ∈ [0,1]` as:

* `score_raw = base_by_group[account_group] + Σ_i weight_i * (x_i - ref_i)`
* `risk_score = clamp(score_raw, 0.0, 1.0)`

Where `x_i` are:

* segment profile scores (if enabled), and/or
* derived holdings/graph flags/buckets, and/or
* owner party tier score (if enabled)

`risk_score_model` MUST declare each feature with:

* `name`
* `source` ∈ `{SEGMENT_PROFILE, HOLDINGS_DERIVED, GRAPH_DERIVED, PARTY_POSTURE}`
* `ref` (float in [0,1])
* `weight` (float)

If a declared feature cannot be computed, FAIL CLOSED.

---

## 10) Risk tier thresholds (deterministic)

Threshold mapping MUST define:

* `tiers_in_order: [LOW, STANDARD, ELEVATED, HIGH]`
* numeric thresholds that partition `[0,1]` (HIGH_max must be 1.0)

---

## 11) Role probability model (how account roles are drawn)

### 11.1 Base mode (v1 pinned)

`mode: by_account_group_and_risk_tier_v1`

Provide `pi_role_by_group_and_tier`:

* key: `(account_group, risk_tier)`
* value: list of `{role_id, prob}` summing to 1

### 11.2 Context nudges (optional, bounded)

Allow small, bounded multiplicative nudges such as:

* if `owner_party_role == MULE` → increase `MULE_ACCOUNT`
* if `has_any_anonymizer_ip == true` → increase `HIGH_RISK_ACCOUNT`
* if `n_instruments_bucket` high and `account_group == CREDIT_CARD` → slightly increase `HIGH_RISK_ACCOUNT`

Pinned semantics:

* multiply unnormalised probs, clip multipliers to `[min,max]`, renormalise.

---

## 12) Constraints (hard fails)

`constraints` MUST include:

* `fail_on_missing_rule: true`
* `prob_dp` (recommended 12) used for normalised probability comparisons in validation
* `max_role_share_caps_world` (role_id → max fraction)
* `min_nonclean_presence_by_group` (account_group → min fraction of non-clean)
* `require_minimum_vocab: true` (enforce required roles exist)

---

## 13) Realism targets (corridors; fail closed)

At minimum include corridors:

* `clean_fraction_range_world` ({min,max})
* `high_risk_fraction_range_world` ({min,max})
* `mule_account_fraction_range_world` ({min,max})
* `dormant_risky_fraction_range_world` ({min,max})
* `by_group_caps`:

  * e.g., credit-card groups may have higher `HIGH_RISK_ACCOUNT` than primary deposits
* `region_variation`:

  * require non-trivial differences if multiple regions exist (prevents “copy-paste world”)

---

## 14) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: account_role_priors_6A
policy_version: v1

role_vocabulary:
  - role_id: CLEAN_ACCOUNT
    label: Clean account
    description: No static fraud posture beyond baseline risk.
    applicable_ledger_classes: [DEPOSIT, CREDIT_REVOLVING, CREDIT_INSTALLMENT, SETTLEMENT]
    severity_rank: 0
  - role_id: DORMANT_RISKY
    label: Dormant but risky
    description: Low activity/low footprint account with elevated static risk indicators.
    applicable_ledger_classes: [DEPOSIT]
    severity_rank: 2
  - role_id: HIGH_RISK_ACCOUNT
    label: High risk account
    description: Elevated static posture (exposure, product context, or linkage risk).
    applicable_ledger_classes: [DEPOSIT, CREDIT_REVOLVING, CREDIT_INSTALLMENT]
    severity_rank: 3
  - role_id: MULE_ACCOUNT
    label: Mule account
    description: Static posture consistent with use as an intermediary for illicit movement.
    applicable_ledger_classes: [DEPOSIT]
    severity_rank: 4

risk_tier_vocabulary:
  - { tier_id: LOW,      label: Low,      description: Low static posture,      severity_rank: 0 }
  - { tier_id: STANDARD, label: Standard, description: Typical baseline posture, severity_rank: 1 }
  - { tier_id: ELEVATED, label: Elevated, description: Elevated static posture, severity_rank: 2 }
  - { tier_id: HIGH,     label: High,     description: High static posture,     severity_rank: 3 }

cell_definition:
  base_cell: [region_id, party_type, segment_id, account_type]
  account_groups:
    RETAIL_CURRENT_BASIC: DEPOSIT_PRIMARY
    RETAIL_SAVINGS_INSTANT: SAVINGS
    RETAIL_CREDIT_CARD_STANDARD: CREDIT_CARD
    RETAIL_PERSONAL_LOAN_UNSECURED: LOAN
    BUSINESS_CURRENT: BUSINESS_DEPOSIT
  context_features_allowed:
    - has_card_instrument
    - has_virtual_instrument
    - has_any_anonymizer_ip
    - has_any_high_risk_device
    - n_instruments_bucket
    - owner_party_risk_tier_score

risk_score_model:
  base_by_group:
    DEPOSIT_PRIMARY: 0.45
    SAVINGS: 0.40
    CREDIT_CARD: 0.52
    LOAN: 0.50
    BUSINESS_DEPOSIT: 0.47
  features:
    - { name: owner_party_risk_tier_score, source: PARTY_POSTURE,  ref: 0.25, weight: 0.22 }
    - { name: has_any_anonymizer_ip,       source: GRAPH_DERIVED,  ref: 0.00, weight: 0.18 }
    - { name: has_any_high_risk_device,    source: GRAPH_DERIVED,  ref: 0.00, weight: 0.10 }
    - { name: has_virtual_instrument,      source: HOLDINGS_DERIVED, ref: 0.00, weight: 0.08 }
    - { name: n_instruments_bucket,        source: HOLDINGS_DERIVED, ref: 0.25, weight: 0.06 }

risk_tier_thresholds:
  tiers_in_order: [LOW, STANDARD, ELEVATED, HIGH]
  thresholds:
    LOW_max: 0.25
    STANDARD_max: 0.65
    ELEVATED_max: 0.85
    HIGH_max: 1.00

role_probability_model:
  mode: by_account_group_and_risk_tier_v1
  pi_role_by_group_and_tier:
    DEPOSIT_PRIMARY:
      LOW:
        - { role_id: CLEAN_ACCOUNT,     prob: 0.9985 }
        - { role_id: HIGH_RISK_ACCOUNT, prob: 0.0010 }
        - { role_id: MULE_ACCOUNT,      prob: 0.0004 }
        - { role_id: DORMANT_RISKY,     prob: 0.0001 }
      STANDARD:
        - { role_id: CLEAN_ACCOUNT,     prob: 0.9930 }
        - { role_id: HIGH_RISK_ACCOUNT, prob: 0.0040 }
        - { role_id: MULE_ACCOUNT,      prob: 0.0020 }
        - { role_id: DORMANT_RISKY,     prob: 0.0010 }
      ELEVATED:
        - { role_id: CLEAN_ACCOUNT,     prob: 0.965 }
        - { role_id: HIGH_RISK_ACCOUNT, prob: 0.020 }
        - { role_id: MULE_ACCOUNT,      prob: 0.010 }
        - { role_id: DORMANT_RISKY,     prob: 0.005 }
      HIGH:
        - { role_id: CLEAN_ACCOUNT,     prob: 0.860 }
        - { role_id: HIGH_RISK_ACCOUNT, prob: 0.080 }
        - { role_id: MULE_ACCOUNT,      prob: 0.040 }
        - { role_id: DORMANT_RISKY,     prob: 0.020 }

    CREDIT_CARD:
      LOW:
        - { role_id: CLEAN_ACCOUNT,     prob: 0.9990 }
        - { role_id: HIGH_RISK_ACCOUNT, prob: 0.0010 }
      STANDARD:
        - { role_id: CLEAN_ACCOUNT,     prob: 0.9960 }
        - { role_id: HIGH_RISK_ACCOUNT, prob: 0.0040 }
      ELEVATED:
        - { role_id: CLEAN_ACCOUNT,     prob: 0.980 }
        - { role_id: HIGH_RISK_ACCOUNT, prob: 0.020 }
      HIGH:
        - { role_id: CLEAN_ACCOUNT,     prob: 0.930 }
        - { role_id: HIGH_RISK_ACCOUNT, prob: 0.070 }

  nudges:
    - if_feature: "owner_party_role == MULE"
      multiply_roles: { MULE_ACCOUNT: 1.60, CLEAN_ACCOUNT: 0.85 }
      clip_multiplier: { min: 0.70, max: 2.00 }
    - if_feature: "has_any_anonymizer_ip == true"
      multiply_roles: { HIGH_RISK_ACCOUNT: 1.25, CLEAN_ACCOUNT: 0.92 }
      clip_multiplier: { min: 0.70, max: 1.60 }

constraints:
  fail_on_missing_rule: true
  prob_dp: 12
  max_role_share_caps_world:
    MULE_ACCOUNT: 0.020
    HIGH_RISK_ACCOUNT: 0.080
    DORMANT_RISKY: 0.030
  min_nonclean_presence_by_group:
    DEPOSIT_PRIMARY: 0.002
    CREDIT_CARD: 0.001
  require_minimum_vocab: true

realism_targets:
  clean_fraction_range_world: { min: 0.92, max: 0.995 }
  high_risk_fraction_range_world: { min: 0.003, max: 0.080 }
  mule_account_fraction_range_world: { min: 0.0005, max: 0.020 }
  dormant_risky_fraction_range_world: { min: 0.0005, max: 0.030 }
  region_variation:
    required_if_n_regions_ge: 3
    min_delta_in_high_risk_fraction: 0.002
```

---

## 15) Acceptance checklist (MUST)

* **Contract pins match:** manifest_key/path/schema_ref align to v1 contracts.
* **Token-less:** no timestamps/UUIDs/digests; no YAML anchors/aliases.
* **Required roles present:** at least `CLEAN_ACCOUNT`, `MULE_ACCOUNT`, `HIGH_RISK_ACCOUNT`, `DORMANT_RISKY`. 
* **Probabilities valid:** for every `(account_group, tier)` distribution, probs ∈ [0,1] and sum to 1.
* **Coverage:** every account_group you plan to emit must have rules for all tiers.
* **Corridors pass:** world + group-level realism targets satisfied; non-trivial variation if multi-region.

---
