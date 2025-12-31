# Authoring Guide — `device_role_priors_6A` (`mlr.6A.s5.prior.device_roles`, v1)

## 0) Purpose

`device_role_priors_6A` is the **sealed, token-less, deterministic (RNG-free) policy** used by **6A.S5** to assign **static fraud posture** to devices (one row per `device_id` in `s4_device_base_6A`). The output field is `fraud_role_device` (and optionally `static_risk_tier_device`). 

Device posture is **static** and must be derived only from **sealed 6A world structure** (S4 device/IP graph + taxonomies + other S5 priors). S5 may use degree/sharing patterns and attachment to risky entities as conditioning signals. 

---

## 1) Contract identity (MUST)

* **manifest_key:** `mlr.6A.s5.prior.device_roles` 
* **dataset_id:** `prior_device_roles_6A` 
* **path:** `config/layer3/6A/priors/device_role_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/device_role_priors_6A`
* **status:** `required` (consumed by `6A.S0`, `6A.S5`) 

**Token-less posture:** do **not** embed timestamps, UUIDs, digests, or “generated_at” in-file. S0 seals by exact bytes and records the digest in `sealed_inputs_6A`. 

---

## 2) Inputs S5 is allowed to condition on (MUST be sealed)

S5 treats S1–S4 datasets as **sealed ground truth**; for devices specifically it may read:
` s4_device_base_6A`, `s4_ip_base_6A`, `s4_device_links_6A`, `s4_ip_links_6A` and derived aggregations. 

This policy must declare (and only allow) a fixed feature whitelist, using only:

### 2.1 From S4 device/IP datasets (ROW_LEVEL)

* device attributes: `device_type`, `os_family`, (optional) `ua_family`, (optional) device static risk codes 
* graph edges: device↔party/account/instrument/merchant links; device↔IP links; IP↔party/merchant links 

### 2.2 Optional cross-entity posture (recommended for coherence)

* owner party posture (from S5 party roles) and/or merchant posture (from S5 merchant roles), **only as coarse flags** (e.g., `owner_party_is_mule`). 

If the policy marks any signal as `required` but S5 cannot compute it from sealed inputs, S5 MUST FAIL CLOSED. 

---

## 3) Role vocabulary (MUST be non-toy)

The S5 spec explicitly expects device roles such as:
`NORMAL_DEVICE`, `RISKY_DEVICE`, `BOT_LIKE_DEVICE`, `SHARED_SUSPICIOUS_DEVICE` (examples). 

### 3.1 Required roles (MUST include in v1)

* `NORMAL_DEVICE`
* `RISKY_DEVICE`
* `BOT_LIKE_DEVICE`
* `SHARED_SUSPICIOUS_DEVICE`

Keep v1 tight: add more roles only if 6B campaigns will explicitly use them.

### 3.2 Optional risk tier (recommended)

If emitted, use the consistent tier vocabulary: `LOW`, `STANDARD`, `ELEVATED`, `HIGH`. 

---

## 4) Policy shape (guided + deterministic)

### 4.1 Device grouping (MUST)

To avoid an unthinkably large `(device_type × os × ua × …)` table, v1 must introduce `device_group_id`:

* `CONSUMER_PERSONAL` (phones, wearables)
* `CONSUMER_SHARED` (household desktops/tablets)
* `COMPUTER_PORTABLE` (laptops)
* `MERCHANT_TERMINAL` (POS/ATM/kiosk)
* `BACKEND_SERVER` (server/API clients)
* `IOT_OTHER` (optional)

The mapping **device_type → group_id** is part of this file.

### 4.2 Derived features (MUST be explicitly specified)

All derived features must be deterministic aggregations from sealed graphs. Recommended minimal set:

* `deg_party` = distinct party_ids linked to device (bucketed)
* `deg_account` = distinct account_ids linked to device (bucketed)
* `deg_ip` = distinct ip_ids linked to device (bucketed)
* `has_anonymizer_ip` = any linked ip where `ip_type ∈ {VPN_PROXY, DATACENTRE}` (or equivalent) 
* `has_high_risk_ip_flag` (if IP risk flags exist in S4)
* `has_high_risk_device_flag` (if device risk flags exist in S4)
* optional: `owner_party_is_mule` (if you enable posture cross-dependency)

Bucket rules must be declared in-file (edges + bucket values).

### 4.3 Risk score → risk tier → role

To keep Codex autonomous and stop “hand-wavy heuristics”, v1 should be a 2-step model:

1. Deterministic **risk_score_device ∈ [0,1]**
2. Deterministic tier thresholds → `static_risk_tier_device`
3. Role distribution by `(device_group_id, risk_tier)` plus bounded nudges for key flags.

---

## 5) Strict YAML structure (MUST)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `device_role_priors_6A`)
3. `policy_version` (string; MUST be `v1`)
4. `role_vocabulary` (list of objects)
5. `risk_tier_vocabulary` (list of objects)
6. `device_groups` (object)
7. `feature_whitelist` (object)
8. `derived_feature_buckets` (object)
9. `risk_score_model` (object)
10. `risk_tier_thresholds` (object)
11. `role_probability_model` (object)
12. `optional_cluster_model` (object)
13. `constraints` (object)
14. `realism_targets` (object)
15. `notes` (optional string)

Unknown keys: **INVALID**. No YAML anchors/aliases. Token-less only.

---

## 6) Required sections

### 6.1 `role_vocabulary[]`

Each role entry MUST include:

* `role_id`
* `label`
* `description`
* `severity_rank` (int; increasing)

### 6.2 `risk_tier_vocabulary[]`

Each tier entry MUST include:

* `tier_id` (`LOW|STANDARD|ELEVATED|HIGH`)
* `label`, `description`, `severity_rank`

### 6.3 `device_groups`

* `groups`: list of `{group_id, device_types:[...], semantics}`
* `device_type_to_group` (explicit map OR implied by membership; v1 SHOULD make it explicit)

### 6.4 `feature_whitelist`

* `required_sources`: list of dataset manifest keys (e.g., S4 device base + links) 
* `allowed_features`: list of **exact** feature names S5 may compute/use
* `required_features`: subset that MUST be computable or FAIL CLOSED

### 6.5 `derived_feature_buckets`

Provide pinned bucket edges and bucket→[0,1] score mapping, e.g.:

* `deg_party_bucket`:

  * edges: `[0,1,2,4,8,16]`
  * values: `[0.00,0.10,0.18,0.35,0.55,0.75,0.90]`

Same for `deg_ip`, `deg_account`.

### 6.6 `risk_score_model`

Pinned deterministic law:

`risk_score = clamp( base_by_group[group] + Σ weight_i * (x_i - ref_i), 0, 1 )`

Where `x_i` are:

* bucket scores (0..1),
* boolean flags (0/1),
* optional device static risk tier mapped to numeric.

### 6.7 `risk_tier_thresholds`

* `tiers_in_order: [LOW, STANDARD, ELEVATED, HIGH]`
* `thresholds: { LOW_max, STANDARD_max, ELEVATED_max, HIGH_max: 1.0 }`

### 6.8 `role_probability_model`

* `mode: by_group_and_risk_tier_v1`
* `pi_role_by_group_and_tier` table: `(group_id, tier) → [{role_id, prob}]` sums to 1.
* optional bounded `nudges`:

  * e.g., if `has_anonymizer_ip==true`: increase `BOT_LIKE_DEVICE`
  * if `deg_party_bucket` high: increase `SHARED_SUSPICIOUS_DEVICE`

### 6.9 `optional_cluster_model` (recommended, but switchable)

To avoid toy “independent bot devices”, v1 MAY include a correlation layer:

* `enabled` bool
* `cluster_key` (e.g., `ip_type`, or `(ip_type, asn_class)` derived from linked IPs)
* `cluster_role` (e.g., `BOT_LIKE_DEVICE`)
* `cluster_size_distribution` (zipf/geometric capK)
* selection rule: clusters are seeded from “anonymizer” IP contexts, then devices behind those IPs are upgraded to the cluster role until targets reached.

If disabled, roles are assigned iid from `pi_role_by_group_and_tier`.

---

## 7) Realism targets (non-toy corridors)

Your corridors should make it impossible for Codex to output toy policies.

Minimum required corridors:

* `bot_like_fraction_world_range` (e.g., `{min: 0.0005, max: 0.02}`)
* `shared_suspicious_fraction_world_range` (e.g., `{min: 0.002, max: 0.08}`)
* `risky_fraction_world_range` (e.g., `{min: 0.01, max: 0.20}`)
* `bot_enrichment_in_anonymizer_context_min_ratio`

  * e.g., `P(bot_like | has_anonymizer_ip) / P(bot_like | not)` ≥ 3.0
* `shared_enrichment_in_high_deg_party_min_ratio`

  * e.g., devices with `deg_party ≥ 4` must be ≥ 5× more likely to be `SHARED_SUSPICIOUS_DEVICE`
* tier distribution sanity:

  * `high_tier_fraction_range`_toggle if you emit tiers
* `region_variation` (if multiple regions exist):

  * require some non-trivial variation in bot-like or risky fraction.

---

## 8) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: device_role_priors_6A
policy_version: v1

role_vocabulary:
  - { role_id: BOT_LIKE_DEVICE, label: Bot-like, description: "Automation / scripted / farm-like posture.", severity_rank: 3 }
  - { role_id: NORMAL_DEVICE, label: Normal, description: "Baseline device posture.", severity_rank: 0 }
  - { role_id: RISKY_DEVICE, label: Risky, description: "Elevated posture without strong bot signals.", severity_rank: 2 }
  - { role_id: SHARED_SUSPICIOUS_DEVICE, label: Shared suspicious, description: "High-sharing device posture consistent with abuse risk.", severity_rank: 2 }

risk_tier_vocabulary:
  - { tier_id: LOW, label: Low, description: "Low static posture.", severity_rank: 0 }
  - { tier_id: STANDARD, label: Standard, description: "Typical posture.", severity_rank: 1 }
  - { tier_id: ELEVATED, label: Elevated, description: "Elevated posture.", severity_rank: 2 }
  - { tier_id: HIGH, label: High, description: "High posture.", severity_rank: 3 }

device_groups:
  groups:
    - { group_id: BACKEND_SERVER, device_types: [SERVER], semantics: "Backend / automated clients." }
    - { group_id: CONSUMER_PERSONAL, device_types: [MOBILE_PHONE, WEARABLE], semantics: "Mostly personal consumer devices." }
    - { group_id: CONSUMER_SHARED, device_types: [DESKTOP, TABLET], semantics: "Shared household devices." }
    - { group_id: COMPUTER_PORTABLE, device_types: [LAPTOP], semantics: "Portable computers." }
    - { group_id: MERCHANT_TERMINAL, device_types: [POS_TERMINAL, ATM, KIOSK], semantics: "Merchant terminals." }

feature_whitelist:
  required_sources: [s4_device_base_6A, s4_device_links_6A, s4_ip_links_6A]
  allowed_features:
    - device_group_id
    - deg_party_bucket
    - deg_ip_bucket
    - has_anonymizer_ip
    - has_high_risk_device_flag
  required_features: [device_group_id, deg_party_bucket, deg_ip_bucket, has_anonymizer_ip]

derived_feature_buckets:
  deg_party_bucket:
    edges: [0, 1, 2, 4, 8, 16]
    values: [0.00, 0.10, 0.18, 0.35, 0.55, 0.75, 0.90]
  deg_ip_bucket:
    edges: [0, 1, 2, 4, 8, 16]
    values: [0.00, 0.08, 0.15, 0.30, 0.50, 0.70, 0.85]

risk_score_model:
  base_by_group:
    CONSUMER_PERSONAL: 0.45
    COMPUTER_PORTABLE: 0.46
    CONSUMER_SHARED: 0.48
    MERCHANT_TERMINAL: 0.50
    BACKEND_SERVER: 0.58
  features:
    - { name: has_anonymizer_ip, source: GRAPH_DERIVED, ref: 0.00, weight: 0.22 }
    - { name: deg_party_bucket,  source: GRAPH_DERIVED, ref: 0.10, weight: 0.18 }
    - { name: deg_ip_bucket,     source: GRAPH_DERIVED, ref: 0.08, weight: 0.12 }
    - { name: has_high_risk_device_flag, source: DEVICE_ATTR, ref: 0.00, weight: 0.10 }

risk_tier_thresholds:
  tiers_in_order: [LOW, STANDARD, ELEVATED, HIGH]
  thresholds: { LOW_max: 0.25, STANDARD_max: 0.65, ELEVATED_max: 0.85, HIGH_max: 1.00 }

role_probability_model:
  mode: by_group_and_risk_tier_v1
  pi_role_by_group_and_tier:
    CONSUMER_PERSONAL:
      LOW:      [{role_id: NORMAL_DEVICE, prob: 0.9980}, {role_id: RISKY_DEVICE, prob: 0.0017}, {role_id: BOT_LIKE_DEVICE, prob: 0.0002}, {role_id: SHARED_SUSPICIOUS_DEVICE, prob: 0.0001}]
      STANDARD: [{role_id: NORMAL_DEVICE, prob: 0.9920}, {role_id: RISKY_DEVICE, prob: 0.0070}, {role_id: BOT_LIKE_DEVICE, prob: 0.0007}, {role_id: SHARED_SUSPICIOUS_DEVICE, prob: 0.0003}]
      ELEVATED: [{role_id: NORMAL_DEVICE, prob: 0.9650}, {role_id: RISKY_DEVICE, prob: 0.0300}, {role_id: BOT_LIKE_DEVICE, prob: 0.0040}, {role_id: SHARED_SUSPICIOUS_DEVICE, prob: 0.0010}]
      HIGH:     [{role_id: NORMAL_DEVICE, prob: 0.9000}, {role_id: RISKY_DEVICE, prob: 0.0700}, {role_id: BOT_LIKE_DEVICE, prob: 0.0250}, {role_id: SHARED_SUSPICIOUS_DEVICE, prob: 0.0050}]
    CONSUMER_SHARED:
      LOW:      [{role_id: NORMAL_DEVICE, prob: 0.9950}, {role_id: RISKY_DEVICE, prob: 0.0040}, {role_id: SHARED_SUSPICIOUS_DEVICE, prob: 0.0010}]
      STANDARD: [{role_id: NORMAL_DEVICE, prob: 0.9850}, {role_id: RISKY_DEVICE, prob: 0.0100}, {role_id: SHARED_SUSPICIOUS_DEVICE, prob: 0.0050}]
      ELEVATED: [{role_id: NORMAL_DEVICE, prob: 0.9500}, {role_id: RISKY_DEVICE, prob: 0.0300}, {role_id: SHARED_SUSPICIOUS_DEVICE, prob: 0.0200}]
      HIGH:     [{role_id: NORMAL_DEVICE, prob: 0.8800}, {role_id: RISKY_DEVICE, prob: 0.0600}, {role_id: SHARED_SUSPICIOUS_DEVICE, prob: 0.0600}]
  nudges:
    - if_feature: "has_anonymizer_ip == true"
      multiply_roles: { BOT_LIKE_DEVICE: 1.60, NORMAL_DEVICE: 0.90 }
      clip_multiplier: { min: 0.70, max: 2.00 }
    - if_feature: "deg_party_bucket >= 0.35"
      multiply_roles: { SHARED_SUSPICIOUS_DEVICE: 1.80, NORMAL_DEVICE: 0.88 }
      clip_multiplier: { min: 0.70, max: 2.50 }

optional_cluster_model:
  enabled: true
  cluster_key: [has_anonymizer_ip]
  cluster_role: BOT_LIKE_DEVICE
  cluster_size_distribution: { model_id: zipf_capK_v1, min_k: 2, max_k: 200, alpha: 1.25 }

constraints:
  fail_on_missing_rule: true
  prob_dp: 12
  max_role_share_caps_world:
    BOT_LIKE_DEVICE: 0.02
    SHARED_SUSPICIOUS_DEVICE: 0.10
  min_non_normal_presence:
    RISKY_DEVICE: 0.005

realism_targets:
  bot_like_fraction_world_range: { min: 0.0005, max: 0.02 }
  shared_suspicious_fraction_world_range: { min: 0.002, max: 0.08 }
  risky_fraction_world_range: { min: 0.01, max: 0.20 }
  bot_enrichment_in_anonymizer_context_min_ratio: 3.0
  shared_enrichment_in_high_deg_party_min_ratio: 5.0
  region_variation:
    required_if_n_regions_ge: 3
    min_delta_in_bot_like_fraction: 0.001
```

---

## 9) Acceptance checklist (MUST)

1. **Contract pins match** (`mlr.6A.s5.prior.device_roles`, correct path/schema_ref).
2. **Token-less**: no timestamps/UUIDs/digests; no YAML anchors/aliases.
3. **Role vocab contains required roles** (at least the S5 examples). 
4. **All probability tables** sum to 1 within tolerance; probs in [0,1].
5. **Feature whitelist** uses only S4-derived and taxonomy-derived signals; no arrivals dependency. 
6. **Realism corridors pass** (world-level fractions + enrichment ratios + region variation if multi-region).
7. **Feasibility guard**: for any device population that exists, policy must not force an impossible all-zero outcome (S5 must be able to assign exactly one role per device). 

---

## 10) Change control (MUST)

* Adding/removing/changing meaning of any `role_id`, changing thresholds, or changing feature definitions is **behaviour-breaking** → bump the file version (e.g., `…v2.yaml`) and update S5 validation corridors accordingly. 
