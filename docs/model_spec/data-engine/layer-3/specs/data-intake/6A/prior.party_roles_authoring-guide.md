# Authoring Guide — `party_role_priors_6A` (`mlr.6A.s5.prior.party_roles`, v1)

## 0) Purpose

`party_role_priors_6A` is the **sealed, token-less, RNG-free** policy that 6A.S5 uses to assign **static fraud posture** to parties, producing **one row per party** in `s5_party_fraud_roles_6A` with:

* `fraud_role_party` (enum; e.g. `CLEAN`, `MULE`, `SYNTHETIC_ID`, `ORGANISER`, `ASSOCIATE`, …)
* optional `static_risk_tier_party` (e.g. `LOW`, `STANDARD`, `ELEVATED`, `HIGH`)
* optional QA diagnostics (e.g. `cell_id`, `risk_score_bucket`) that are **not identity**. 

This prior MUST be realistic (non-toy): it should yield a world where most parties are clean, but a **small, structured** fraction are higher risk and/or involved in organised fraud ecosystems, in a way that correlates with **sealed context** (segment, product mix, simple device/IP graph features). 

---

## 1) Contract identity (binding)

From the 6A artefact registry + dataset dictionary:

* **manifest_key:** `mlr.6A.s5.prior.party_roles` 
* **dataset_id:** `prior_party_roles_6A`
* **path:** `config/layer3/6A/priors/party_role_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/party_role_priors_6A` *(schema may be permissive; this guide is the binding spec for semantics)*
* **status:** `required` (consumed by **6A.S0** and **6A.S5**)
* **license:** `Proprietary-Internal` (authored, not acquired) 

Token-less posture: **do not embed digests/timestamps** inside the file; 6A.S0 seals the exact file bytes and records the digest in `sealed_inputs_6A`.

---

## 2) Scope and authority boundaries

### In scope (this file owns)

* The **role vocabulary** that S5 is allowed to emit for parties.
* The **risk tier vocabulary** (if you emit tiers).
* The **deterministic mapping** from sealed context → `(risk_score, risk_tier)` and from `(risk_tier, context)` → `π(fraud_role_party)`.

### Out of scope (must not live here)

* Fraud behaviour campaigns, event sequences, and labels (those belong to 6B).
* Any “learning/trained” artefacts (this must be authored/deterministic).
* Changes to upstream world structure (S5 must treat S1–S4 as sealed truth). 

---

## 3) Inputs S5 may condition on (must be sealed)

S5 is allowed to condition party roles on **coarse, sealed aggregates** from 6A.S1–S4 and on sealed priors/taxonomies. 

This guide pins the allowed feature sources to keep Codex autonomous and prevent “hidden data dependencies”:

### 3.1 From S1 (`s1_party_base_6A`)

* `region_id`, `party_type`, `segment_id`

### 3.2 From segmentation priors (already sealed for S1)

* per-segment profile scores (e.g. `digital_affinity`, `cross_border_propensity`, `credit_appetite`, `stability_score`) **if** your `prior_segmentation_6A` provides them.

### 3.3 From S2/S3 holdings (aggregated per party)

Allowed derived indicators (computed deterministically by S5):

* `has_credit_product` (any CREDIT account)
* `has_credit_instrument` (any credit-card instrument type)
* `n_accounts_bucket` (bucketed from account count)
* `n_instruments_bucket`

### 3.4 From S4 graph (aggregated per party)

Allowed derived indicators:

* `n_devices_bucket`
* `has_any_high_risk_device` (device risk tier == HIGH)
* `has_any_anonymizer_ip` (ip_type in {VPN_PROXY, DATACENTRE} or risk flag if modelled)
* `ip_exposure_bucket` (bucketed count of distinct IPs linked to party, directly or via device)

If any required upstream fields needed to compute these are missing, S5 must **FAIL CLOSED** (do not “guess defaults”).

---

## 4) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `party_role_priors_6A`)
3. `policy_version` (string; MUST be `v1`)
4. `role_vocabulary` (list of objects)
5. `risk_tier_vocabulary` (list of objects)
6. `cell_definition` (object)
7. `risk_score_model` (object)
8. `risk_tier_thresholds` (object)
9. `role_probability_model` (object)
10. `constraints` (object)
11. `realism_targets` (object)
12. `notes` (optional string)

Unknown keys: **INVALID**.

Formatting MUST:

* be token-less (no `generated_at`, no digests)
* use 2-space indentation
* contain **no YAML anchors/aliases**
* keep lists sorted deterministically (see Acceptance checklist).

---

## 5) Role vocabulary (MUST)

### 5.1 `role_vocabulary[]`

Each role object MUST include:

* `role_id` (e.g. `CLEAN`)
* `label`
* `description`
* `applicable_party_types` (subset of `{RETAIL,BUSINESS,OTHER}`; non-empty)
* `severity_rank` (int; 0=benign … higher=more concerning)

Minimum required v1 roles (MUST include at least):

* `CLEAN`
* `SYNTHETIC_ID`
* `MULE`
* `ASSOCIATE`
* `ORGANISER`

Guidance (non-binding): keep the set small and interpretable in v1; add more roles only when 6B campaigns explicitly need them.

---

## 6) Risk tier vocabulary (MUST)

### 6.1 `risk_tier_vocabulary[]`

Each tier object MUST include:

* `tier_id` (e.g. `STANDARD`)
* `label`
* `description`
* `severity_rank` (int; increasing)

Minimum required v1 tiers (MUST include):

* `LOW`
* `STANDARD`
* `ELEVATED`
* `HIGH`

---

## 7) Cell definition (what “π_party_role | cell” means)

`cell_definition` MUST specify:

* `base_cell`: `[region_id, party_type, segment_id]`
* `context_features`: ordered list of permitted derived features from §3 (e.g. `has_credit_instrument`, `has_any_anonymizer_ip`, `n_devices_bucket`, …)
* `cell_id_format`: deterministic string format, e.g.
  `"{region_id}|{party_type}|{segment_id}|{flagpack}"`

Rules:

* S5 may emit `cell_id` only as diagnostics; it MUST NOT be part of PK. 

---

## 8) Risk score model (deterministic, RNG-free)

### 8.1 `risk_score_model`

v1 pins a **bounded linear score** in [0,1]:

* Compute a feature vector `x` consisting of:

  * segment profile scores (0..1) if present
  * derived flags/buckets from holdings and graph (0/1 or bucket indices mapped to 0..1)

* Compute:

  * `score_raw = base + Σ_i weight_i * (x_i - ref_i)`
  * `risk_score = clamp(score_raw, 0.0, 1.0)`

Required fields:

* `base` (float in [0,1])
* `features` (list of `{name, source, ref, weight}`)

Allowed `source` values (strict):

* `SEGMENT_PROFILE`
* `HOLDINGS_DERIVED`
* `GRAPH_DERIVED`

If a feature is declared but cannot be computed from sealed inputs, S5 must **FAIL**.

### 8.2 Bucketing derived counts

Any bucketed feature MUST define:

* `bucket_edges` (ascending ints)
* `bucket_values` (same length+1 floats in [0,1])

Example: `n_devices_bucket` maps `{0,1,2,3–4,5–7,8+}` to values `{0.0,0.1,0.2,0.35,0.55,0.75}`.

---

## 9) Risk tier thresholds (deterministic)

`risk_tier_thresholds` MUST define:

* `tiers_in_order`: `[LOW, STANDARD, ELEVATED, HIGH]`
* `thresholds`:

  * `LOW_max` (float)
  * `STANDARD_max` (float)
  * `ELEVATED_max` (float)
  * `HIGH_max` MUST equal `1.0`

Interpretation:

* `risk_score ≤ LOW_max` ⇒ `LOW`
* `LOW_max < risk_score ≤ STANDARD_max` ⇒ `STANDARD`
* `STANDARD_max < risk_score ≤ ELEVATED_max` ⇒ `ELEVATED`
* else ⇒ `HIGH`

---

## 10) Role probability model (how roles are drawn)

`role_probability_model` MUST specify:

### 10.1 `mode`

v1 pins: `by_party_type_and_risk_tier_v1`

### 10.2 `pi_role_by_party_type_and_tier`

A table of distributions:

* key: `(party_type, risk_tier)`
* value: list of `{role_id, prob}` summing to 1

Rules:

* Every `role_id` must exist in `role_vocabulary`.
* Roles not applicable to that party_type MUST have prob=0 and SHOULD be omitted.
* For each `(party_type,tier)` distribution: sum to 1 within tolerance `1e-12`.

### 10.3 Optional “context nudges”

To keep it non-toy without exploding table size, v1 allows **bounded multiplicative nudges**:

* `nudges`: list of rules:

  * `if_feature` (e.g. `has_any_anonymizer_ip == true`)
  * `multiply_roles` (map role_id → multiplier)
  * `clip_multiplier` `{min,max}`

Pinned semantics:

* Start from base `π`.
* Apply multipliers to unnormalised probs.
* Renormalise.

No nudges may introduce a role that is not in vocabulary.

---

## 11) Constraints (hard fails)

`constraints` MUST include:

* `fail_on_missing_rule: true`
* `prob_dp` (int; recommended 12) for normalised output precision (internal; file still stores decimal)
* `max_role_share_caps` (map role_id → max fraction) evaluated at world aggregate:

  * e.g. `ORGANISER ≤ 0.001`, `MULE ≤ 0.03`, `SYNTHETIC_ID ≤ 0.02` (tunable)
* `min_nonclean_presence` (map party_type → min fraction of non-CLEAN) to avoid toy “all clean” worlds
* `require_role_vocab_minimum: true` (enforce minimum role set)

---

## 12) Realism targets (corridor checks; fail closed)

`realism_targets` MUST include corridors evaluated on expected rates implied by the priors (and optionally on realised outcomes during S5 validation):

* `clean_fraction_range_by_party_type` (party_type → {min,max})
* `high_risk_tier_fraction_range_by_party_type` (party_type → {min,max})
* `organiser_fraction_range_world` ({min,max})
* `mule_fraction_range_world` ({min,max})
* `synthetic_id_fraction_range_world` ({min,max})
* `risk_tier_entropy_min_by_party_type` (party_type → float ≥ 0)
* `nontrivial_region_variation`:

  * `required_if_n_regions_ge` (int)
  * `min_delta_in_high_risk_fraction` (float)

These corridors are where you enforce “not toy, not absurd”.

---

## 13) Minimal v1 example (realistic shape)

```yaml
schema_version: 1
policy_id: party_role_priors_6A
policy_version: v1

role_vocabulary:
  - role_id: ASSOCIATE
    label: Associate
    description: Party plausibly connected to organised fraud actors; elevated posture.
    applicable_party_types: [RETAIL, BUSINESS]
    severity_rank: 3
  - role_id: CLEAN
    label: Clean
    description: No static fraud posture indicators beyond baseline risk.
    applicable_party_types: [RETAIL, BUSINESS, OTHER]
    severity_rank: 0
  - role_id: MULE
    label: Mule
    description: Party plausibly used as an intermediary for fraud/money movement.
    applicable_party_types: [RETAIL, BUSINESS]
    severity_rank: 4
  - role_id: ORGANISER
    label: Organiser
    description: Rare party plausibly coordinating fraud activity and recruiting others.
    applicable_party_types: [RETAIL, BUSINESS]
    severity_rank: 5
  - role_id: SYNTHETIC_ID
    label: Synthetic identity
    description: Party plausibly constructed/fragmented identity; elevated baseline risk.
    applicable_party_types: [RETAIL, BUSINESS]
    severity_rank: 2

risk_tier_vocabulary:
  - tier_id: ELEVATED
    label: Elevated
    description: Elevated static posture.
    severity_rank: 2
  - tier_id: HIGH
    label: High
    description: High static posture.
    severity_rank: 3
  - tier_id: LOW
    label: Low
    description: Low static posture.
    severity_rank: 0
  - tier_id: STANDARD
    label: Standard
    description: Typical baseline posture.
    severity_rank: 1

cell_definition:
  base_cell: [region_id, party_type, segment_id]
  context_features:
    - has_credit_instrument
    - has_any_anonymizer_ip
    - has_any_high_risk_device
    - n_devices_bucket
  cell_id_format: "{region_id}|{party_type}|{segment_id}|{flags}"

risk_score_model:
  base: 0.48
  features:
    - { name: digital_affinity,        source: SEGMENT_PROFILE,  ref: 0.50, weight:  0.18 }
    - { name: cross_border_propensity, source: SEGMENT_PROFILE,  ref: 0.50, weight:  0.16 }
    - { name: credit_appetite,         source: SEGMENT_PROFILE,  ref: 0.50, weight:  0.10 }
    - { name: has_credit_instrument,   source: HOLDINGS_DERIVED, ref: 0.00, weight:  0.10 }
    - { name: has_any_anonymizer_ip,   source: GRAPH_DERIVED,    ref: 0.00, weight:  0.18 }
    - { name: has_any_high_risk_device,source: GRAPH_DERIVED,    ref: 0.00, weight:  0.10 }
    - { name: n_devices_bucket,        source: GRAPH_DERIVED,    ref: 0.25, weight:  0.08 }

risk_tier_thresholds:
  tiers_in_order: [LOW, STANDARD, ELEVATED, HIGH]
  thresholds:
    LOW_max: 0.25
    STANDARD_max: 0.65
    ELEVATED_max: 0.85
    HIGH_max: 1.00

role_probability_model:
  mode: by_party_type_and_risk_tier_v1
  pi_role_by_party_type_and_tier:
    RETAIL:
      LOW:
        - { role_id: CLEAN,        prob: 0.9975 }
        - { role_id: SYNTHETIC_ID, prob: 0.0010 }
        - { role_id: MULE,         prob: 0.0012 }
        - { role_id: ASSOCIATE,    prob: 0.00025 }
        - { role_id: ORGANISER,    prob: 0.00005 }
      STANDARD:
        - { role_id: CLEAN,        prob: 0.9880 }
        - { role_id: SYNTHETIC_ID, prob: 0.0050 }
        - { role_id: MULE,         prob: 0.0050 }
        - { role_id: ASSOCIATE,    prob: 0.0016 }
        - { role_id: ORGANISER,    prob: 0.0004 }
      ELEVATED:
        - { role_id: CLEAN,        prob: 0.940 }
        - { role_id: SYNTHETIC_ID, prob: 0.020 }
        - { role_id: MULE,         prob: 0.030 }
        - { role_id: ASSOCIATE,    prob: 0.008 }
        - { role_id: ORGANISER,    prob: 0.002 }
      HIGH:
        - { role_id: CLEAN,        prob: 0.800 }
        - { role_id: SYNTHETIC_ID, prob: 0.070 }
        - { role_id: MULE,         prob: 0.100 }
        - { role_id: ASSOCIATE,    prob: 0.020 }
        - { role_id: ORGANISER,    prob: 0.010 }

    BUSINESS:
      LOW:
        - { role_id: CLEAN,        prob: 0.9980 }
        - { role_id: SYNTHETIC_ID, prob: 0.0010 }
        - { role_id: MULE,         prob: 0.0008 }
        - { role_id: ASSOCIATE,    prob: 0.00018 }
        - { role_id: ORGANISER,    prob: 0.00002 }
      STANDARD:
        - { role_id: CLEAN,        prob: 0.9920 }
        - { role_id: SYNTHETIC_ID, prob: 0.0040 }
        - { role_id: MULE,         prob: 0.0020 }
        - { role_id: ASSOCIATE,    prob: 0.0017 }
        - { role_id: ORGANISER,    prob: 0.0003 }
      ELEVATED:
        - { role_id: CLEAN,        prob: 0.955 }
        - { role_id: SYNTHETIC_ID, prob: 0.015 }
        - { role_id: MULE,         prob: 0.020 }
        - { role_id: ASSOCIATE,    prob: 0.008 }
        - { role_id: ORGANISER,    prob: 0.002 }
      HIGH:
        - { role_id: CLEAN,        prob: 0.860 }
        - { role_id: SYNTHETIC_ID, prob: 0.050 }
        - { role_id: MULE,         prob: 0.060 }
        - { role_id: ASSOCIATE,    prob: 0.020 }
        - { role_id: ORGANISER,    prob: 0.010 }

    OTHER:
      LOW:
        - { role_id: CLEAN, prob: 1.0 }
      STANDARD:
        - { role_id: CLEAN, prob: 1.0 }
      ELEVATED:
        - { role_id: CLEAN, prob: 1.0 }
      HIGH:
        - { role_id: CLEAN, prob: 1.0 }

  nudges:
    - if_feature: "has_any_anonymizer_ip == true"
      multiply_roles: { MULE: 1.35, ORGANISER: 1.20, CLEAN: 0.90 }
      clip_multiplier: { min: 0.70, max: 1.60 }

constraints:
  fail_on_missing_rule: true
  prob_dp: 12
  max_role_share_caps:
    ORGANISER: 0.0010
    ASSOCIATE: 0.0100
    MULE: 0.0300
    SYNTHETIC_ID: 0.0200
  min_nonclean_presence:
    RETAIL: 0.003
    BUSINESS: 0.002
    OTHER: 0.000
  require_role_vocab_minimum: true

realism_targets:
  clean_fraction_range_by_party_type:
    RETAIL:  { min: 0.93,  max: 0.995 }
    BUSINESS:{ min: 0.95,  max: 0.997 }
    OTHER:   { min: 0.995, max: 1.0 }
  high_risk_tier_fraction_range_by_party_type:
    RETAIL:  { min: 0.002, max: 0.030 }
    BUSINESS:{ min: 0.001, max: 0.025 }
    OTHER:   { min: 0.000, max: 0.010 }
  organiser_fraction_range_world:    { min: 0.00002, max: 0.00080 }
  mule_fraction_range_world:         { min: 0.00100, max: 0.02500 }
  synthetic_id_fraction_range_world: { min: 0.00050, max: 0.01500 }
  risk_tier_entropy_min_by_party_type:
    RETAIL: 1.0
    BUSINESS: 0.8
    OTHER: 0.0
  nontrivial_region_variation:
    required_if_n_regions_ge: 3
    min_delta_in_high_risk_fraction: 0.003
```

---

## 14) Acceptance checklist (MUST)

### 14.1 Contract pins

* File is written to the contract path and uses the correct manifest key / schema_ref.

### 14.2 Structural strictness

* YAML parses cleanly.
* Unknown keys absent everywhere.
* Token-less (no timestamps/UUIDs/digests).
* No YAML anchors/aliases.
* Deterministic ordering:

  * vocab lists sorted by `role_id` / `tier_id`
  * `features` sorted by `name`
  * probability tables sorted by `(party_type, tier, role_id)`.

### 14.3 Vocabulary validity

* Required roles present (`CLEAN`, `SYNTHETIC_ID`, `MULE`, `ASSOCIATE`, `ORGANISER`).
* Required tiers present (`LOW`, `STANDARD`, `ELEVATED`, `HIGH`).

### 14.4 Probability validity

* For each `(party_type, tier)` row: probs in [0,1] and sum to 1 within tolerance.
* Roles not applicable to a party_type must not appear (or must have prob 0).

### 14.5 Realism corridors

* Global and per-party_type corridors pass (clean fraction, high risk fraction, mule/organiser prevalence, entropy, region variation).

### 14.6 Feasibility alignment with S5 outputs

* Role vocabulary must support emitting `fraud_role_party` exactly as S5 outputs require. 
* Prior must be present and sealed as a REQUIRED row-level input for S5.

---

## 15) Change control (MUST)

* Any change to:

  * role ids or meanings,
  * risk tier thresholds,
  * probability tables / nudges,
  * feature definitions,
    is a **behaviour-breaking** change → bump filename/version (`…v2.yaml`) and update S5 validation corridors accordingly.

---
