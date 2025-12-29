# Authoring Guide — `device_count_priors_6A` (`mlr.6A.prior.device_counts`, v1)

## 0) Purpose

`device_count_priors_6A` is the **sealed, token-less, RNG-free** prior pack that **6A.S4** uses to plan and realise the **device universe** and its ownership/sharing structure.

S4 uses these priors to compute continuous targets per device planning cell:

* `λ_devices_per_party(c_dev)`, optionally `λ_devices_per_account(c_dev)`, `λ_devices_per_merchant(c_dev)`
* `N_device_target(c_dev)` and a device-type mix `π_device_type|c_dev(device_type)`
* then S4 integerises and allocates devices to entities, failing if weights/caps make the plan infeasible.

This file must be **non-toy**: it needs to produce realistic device densities, mixes (mobile vs desktop vs terminal), sharing (personal vs household/shared), and attribute distributions (OS/UA/risk tiers) aligned to your taxonomies.

---

## 1) Contract identity (binding)

These pins are non-negotiable:

* **manifest_key:** `mlr.6A.prior.device_counts` 
* **dataset_id:** `prior_device_counts_6A` 
* **path:** `config/layer3/6A/priors/device_count_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/device_count_priors_6A`
* **status:** `required` and consumed by `6A.S0` + `6A.S4` 

**Token-less posture:** no timestamps, UUIDs, in-file digests. S0 seals exact bytes (`sha256_hex`) in `sealed_inputs_6A`.

---

## 2) Dependencies (MUST exist & be compatible)

This prior must be authored against:

* `taxonomy_party_6A` (regions + party_type + segment_id universe) 
* `taxonomy_devices_6A` (device_type, os_family, ua_family if present, risk codes) 
* `prior_segmentation_6A` **or equivalent** segment profiles (so S4 can tilt devices by segment features deterministically)

Optional (only if you enable “product-biased devices”):

* `taxonomy_account_types_6A` and coarse `account_type_class` mapping for device planning cells. 

---

## 3) How S4 uses this prior (pinned semantics)

### 3.1 Planning cells (v1 must declare what you choose)

S4’s generic device planning cell notation is:

`c_dev = (region_id, party_type, segment_id[, account_type_class])`

Your v1 prior MUST declare whether `account_type_class` is used (and if so, how account types map to classes).

### 3.2 Continuous targets (must be supported by the prior)

S4 computes:

```
N_device_target(c_dev) =
    N_parties(c_dev)   × λ_devices_per_party(c_dev)
  + N_accounts(c_dev)  × λ_devices_per_account(c_dev)
  + N_merchants(c_dev) × λ_devices_per_merchant(c_dev)
```

and then:

`N_device_target(c_dev, device_type) = N_device_target(c_dev) × π_device_type|c_dev(device_type)`

### 3.3 Allocation feasibility (your priors must avoid impossible plans)

S4 normalises entity weights `w_e` and fails if `W_total==0` while `N_device(c_dev,type)>0`. 
So your priors must ensure: **where targets are positive, there exist eligible entities with positive weight under the constraints**.

---

## 4) What this prior MUST provide (v1)

At minimum:

1. **Device density model**

* `λ_devices_per_party(c_dev)` always required
* `λ_devices_per_account(c_dev)` optional (default 0 if not used)
* `λ_devices_per_merchant(c_dev)` optional (default 0 if merchant devices disabled)

2. **Device-type mix**

* `π_device_type|c_dev(device_type)` for all device types you intend to realise in each cell

3. **Ownership & sharing rules**

* whether devices are personal vs shared
* max/min parties per device (by device_type group)
* how “household devices” vs “personal devices” are represented 

4. **Allocation weight recipe**

* a deterministic way to compute `w_party` (and/or `w_account`, `w_merchant`) per `(c_dev, device_type)`
* includes zero-inflation + heavy-tail (so a few parties can have many devices, but not everyone)

5. **Device attribute distributions**

* `os_family` distribution by device_type (and optionally by party_type / region)
* `ua_family` distribution if modelled
* static risk tiers/flags distributions if used by your device taxonomy

6. **Hard caps & safety caps**

* max devices per party/account/merchant
* global safety caps (max total devices / edges) so S4 can fail cleanly rather than produce an absurdly dense graph

---

## 5) Strict YAML structure (MUST)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `prior_id` (string; MUST be `device_count_priors_6A`)
3. `prior_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `cell_model` (object)
6. `density_model` (object)
7. `type_mix_model` (object)
8. `sharing_model` (object)
9. `allocation_weight_model` (object)
10. `attribute_models` (object)
11. `constraints` (object)
12. `realism_targets` (object)
13. `notes` (optional string)

Unknown keys: **INVALID**.

Formatting MUST:

* no YAML anchors/aliases
* stable ordering (lists sorted by id/key)
* token-less (no timestamps/digests)

---

## 6) Section contracts (v1 recommended)

### 6.1 `bindings` (MUST)

* `party_taxonomy_ref: taxonomy_party_6A`
* `device_taxonomy_ref: taxonomy_devices_6A`
* `segmentation_prior_ref: prior_segmentation_6A` *(or your chosen name)*
* optional `account_taxonomy_ref: taxonomy_account_types_6A` *(only if account_type_class enabled)*

### 6.2 `cell_model` (MUST)

* `mode` ∈ `{ party_cell_v1, party_cell_with_account_class_v1 }`
* `cell_definition`:

  * if `party_cell_v1`: `[region_id, party_type, segment_id]`
  * if `party_cell_with_account_class_v1`: add `account_type_class`
* if account_class mode:

  * `account_type_class_map`: list of `{account_type, account_type_class}`

### 6.3 `density_model` (MUST)

Defines λ values.

Required:

* `party_lambda`:

  * `mode: base_plus_segment_tilt_v1`
  * `base_lambda_by_party_type` (map RETAIL/BUSINESS/OTHER → float)
  * `segment_feature_tilt` (object):

    * `features` (e.g. `digital_affinity`, `stability_score`)
    * `weights_by_feature` (feature → scalar weight applied to log-multiplier)
    * `clip_log_multiplier` (float > 0)

Optional:

* `account_lambda` (enabled bool; default false → λ_devices_per_account=0)
* `merchant_lambda` (enabled bool; default false → λ_devices_per_merchant=0)
* `global_density_multiplier` (float > 0; allows CI scaling without changing structure)

Pinned tilt law (deterministic):

* `λ = base × exp( clamp( Σ w_f × (score_f(segment)-0.5), ±clip ) )`

### 6.4 `type_mix_model` (MUST)

Defines `π_device_type|c_dev`.

Required:

* `mode: by_party_type_with_segment_tilt_v1`
* `base_pi_by_party_type`:

  * party_type → list of `{device_type, share}` summing to 1
* optional `segment_tilts`:

  * list of `{feature, device_type, weight, clip}`

### 6.5 `sharing_model` (MUST)

Defines personal vs shared devices and degree bounds.

Required:

* `mode: by_device_type_group_v1`
* `device_type_groups` list:

  * `{group_id, device_types:[...], semantics}`
* for each group:

  * `p_shared` (float in [0,1])
  * `parties_per_shared_device` distribution:

    * `min_k`, `max_k`, and either `pmf` or `{model: geometric_capK, p}`
  * `max_parties_per_device` hard cap (int ≥ 1)

Recommended:

* mobile phones mostly personal (`p_shared` low)
* desktops/tablets higher household sharing
* merchant terminals shared across many customers but *owned by merchant* (if merchant devices enabled)

### 6.6 `allocation_weight_model` (MUST)

Defines how S4 computes per-entity weights `w_e` for allocating devices, with zero-inflation + heavy-tail.

Required:

* `mode: hash_lognormal_with_zero_gate_v1`
* `p_zero_weight_by_group` (group_id → float in [0,1))
* `sigma_by_group` (group_id → float ≥ 0)
* `weight_floor_eps` (float > 0)
* optional feature tilts:

  * `p_zero_weight_multipliers_by_feature`
  * `sigma_multipliers_by_feature`
  * with bounded clips

This is what prevents `W_total==0` failures when targets are positive. 

### 6.7 `attribute_models` (MUST)

Required sub-objects (even if some are disabled):

* `os_family_model`
* `ua_family_model`
* `risk_tier_model`
* `risk_flags_model` *(if you model flags)*

Each MUST include:

* `enabled` (bool)
* `mode`
* `defaults`
* `overrides` (optional list)

Recommended v1 modes:

* `os_family_model.mode = by_device_type_v1`
* `ua_family_model.mode = by_device_type_v1` (enabled only if taxonomy includes ua_family)
* `risk_tier_model.mode = by_device_type_with_stability_tilt_v1`

### 6.8 `constraints` (MUST)

Required:

* `max_devices_per_party` (int)
* `max_devices_per_account` (int)
* `max_devices_per_merchant` (int)
* `max_total_devices_world` (int)
* `max_total_device_edges_world` (int)
* `fail_on_missing_rule: true`

### 6.9 `realism_targets` (MUST)

Corridors to enforce non-toy realism:

Required:

* `lambda_devices_per_party_range_by_party_type` (party_type → {min,max})
* `mobile_share_range_retail` ({min,max})
* `desktop_share_range_business` ({min,max})
* `shared_fraction_range_by_group` (group_id → {min,max})
* `os_diversity_floor` (device_type → min distinct OS families with share ≥ threshold)
* `high_risk_fraction_cap` (float) *(if risk tiers used)*
* `segment_variation_required_if_n_segments_ge` (int)
* `segment_variation_min_delta` (float)

---

## 7) Authoring procedure (Codex-ready)

1. Load `taxonomy_party_6A` (region_id, party_type, segment_id) and `taxonomy_devices_6A` (device_type, os_family, ua_family/risk vocab).
2. Choose `cell_model` (v1 recommended: `party_cell_v1` unless you truly need product bias). 
3. Set `party_lambda` baselines:

   * RETAIL typically ~1.2–3.2 devices/party (active + inactive devices)
   * BUSINESS typically ~1.5–4.5 devices/party (more desktops + terminals if modelled)
4. Define `type_mix_model`:

   * RETAIL skew mobile-heavy
   * BUSINESS more desktop/laptop share
5. Define `sharing_model` by device group:

   * mobile mostly personal
   * desktops/tablets more shared
6. Define `allocation_weight_model`:

   * ensure `p_zero_weight < 1` for groups that exist in cells with positive targets
7. Define `attribute_models`:

   * OS mix by device_type (mobile: Android/iOS split; desktop: Windows/Mac/Linux; terminals: Embedded)
8. Set caps + realism corridors; fail closed if violated.
9. Freeze formatting (sorted lists; no anchors; token-less).

---

## 8) Minimal v1 example (illustrative shape)

```yaml
schema_version: 1
prior_id: device_count_priors_6A
prior_version: v1

bindings:
  party_taxonomy_ref: taxonomy_party_6A
  device_taxonomy_ref: taxonomy_devices_6A
  segmentation_prior_ref: prior_segmentation_6A

cell_model:
  mode: party_cell_v1
  cell_definition: [region_id, party_type, segment_id]

density_model:
  global_density_multiplier: 1.0
  party_lambda:
    mode: base_plus_segment_tilt_v1
    base_lambda_by_party_type: { RETAIL: 2.1, BUSINESS: 2.6, OTHER: 1.6 }
    segment_feature_tilt:
      features: [digital_affinity, stability_score]
      weights_by_feature: { digital_affinity: 0.35, stability_score: 0.10 }
      clip_log_multiplier: 0.60

type_mix_model:
  mode: by_party_type_with_segment_tilt_v1
  base_pi_by_party_type:
    RETAIL:
      - { device_type: MOBILE_PHONE, share: 0.62 }
      - { device_type: TABLET,      share: 0.10 }
      - { device_type: LAPTOP,      share: 0.12 }
      - { device_type: DESKTOP,     share: 0.10 }
      - { device_type: WEARABLE,    share: 0.06 }
    BUSINESS:
      - { device_type: LAPTOP,      share: 0.32 }
      - { device_type: DESKTOP,     share: 0.28 }
      - { device_type: MOBILE_PHONE,share: 0.26 }
      - { device_type: TABLET,      share: 0.10 }
      - { device_type: SERVER,      share: 0.04 }
    OTHER:
      - { device_type: DESKTOP,     share: 0.35 }
      - { device_type: LAPTOP,      share: 0.25 }
      - { device_type: MOBILE_PHONE,share: 0.25 }
      - { device_type: TABLET,      share: 0.15 }
  segment_tilts:
    - { feature: digital_affinity, device_type: MOBILE_PHONE, weight: 0.45, clip: 0.60 }
    - { feature: digital_affinity, device_type: DESKTOP,      weight: -0.25, clip: 0.60 }

sharing_model:
  mode: by_device_type_group_v1
  device_type_groups:
    - group_id: CONSUMER_PERSONAL
      device_types: [MOBILE_PHONE, WEARABLE]
      semantics: "Mostly personal devices."
    - group_id: CONSUMER_SHARED
      device_types: [DESKTOP, TABLET]
      semantics: "Household/shared devices."
    - group_id: COMPUTER_PORTABLE
      device_types: [LAPTOP]
      semantics: "Usually personal, sometimes shared."
  group_params:
    CONSUMER_PERSONAL:
      p_shared: 0.03
      parties_per_shared_device: { model: geometric_capK, p: 0.65, min_k: 2, max_k: 4 }
      max_parties_per_device: 4
    CONSUMER_SHARED:
      p_shared: 0.22
      parties_per_shared_device: { model: geometric_capK, p: 0.55, min_k: 2, max_k: 6 }
      max_parties_per_device: 6
    COMPUTER_PORTABLE:
      p_shared: 0.08
      parties_per_shared_device: { model: geometric_capK, p: 0.60, min_k: 2, max_k: 4 }
      max_parties_per_device: 4

allocation_weight_model:
  mode: hash_lognormal_with_zero_gate_v1
  p_zero_weight_by_group:
    CONSUMER_PERSONAL: 0.02
    CONSUMER_SHARED:  0.35
    COMPUTER_PORTABLE: 0.15
  sigma_by_group:
    CONSUMER_PERSONAL: 0.55
    CONSUMER_SHARED:  0.95
    COMPUTER_PORTABLE: 0.80
  weight_floor_eps: 1.0e-6

attribute_models:
  os_family_model:
    enabled: true
    mode: by_device_type_v1
    defaults:
      MOBILE_PHONE:
        - { os_family: ANDROID, share: 0.72 }
        - { os_family: IOS,     share: 0.28 }
      DESKTOP:
        - { os_family: WINDOWS, share: 0.68 }
        - { os_family: MACOS,   share: 0.22 }
        - { os_family: LINUX,   share: 0.10 }
      LAPTOP:
        - { os_family: WINDOWS, share: 0.62 }
        - { os_family: MACOS,   share: 0.28 }
        - { os_family: LINUX,   share: 0.10 }
      TABLET:
        - { os_family: ANDROID, share: 0.55 }
        - { os_family: IOS,     share: 0.45 }
    overrides: []

  ua_family_model:
    enabled: true
    mode: by_device_type_v1
    defaults:
      MOBILE_PHONE:
        - { ua_family: WEBVIEW, share: 0.45 }
        - { ua_family: CHROME,  share: 0.35 }
        - { ua_family: SAFARI,  share: 0.20 }
      DESKTOP:
        - { ua_family: CHROME,  share: 0.55 }
        - { ua_family: EDGE,    share: 0.20 }
        - { ua_family: SAFARI,  share: 0.10 }
        - { ua_family: FIREFOX, share: 0.15 }
    overrides: []

  risk_tier_model:
    enabled: true
    mode: by_device_type_with_stability_tilt_v1
    defaults:
      MOBILE_PHONE:
        - { device_risk_tier: LOW,      share: 0.18 }
        - { device_risk_tier: STANDARD, share: 0.78 }
        - { device_risk_tier: HIGH,     share: 0.04 }
      DESKTOP:
        - { device_risk_tier: LOW,      share: 0.12 }
        - { device_risk_tier: STANDARD, share: 0.80 }
        - { device_risk_tier: HIGH,     share: 0.08 }
    overrides: []

  risk_flags_model:
    enabled: false
    mode: none
    defaults: {}
    overrides: []

constraints:
  fail_on_missing_rule: true
  max_devices_per_party: 12
  max_devices_per_account: 6
  max_devices_per_merchant: 25
  max_total_devices_world: 200000000
  max_total_device_edges_world: 400000000

realism_targets:
  lambda_devices_per_party_range_by_party_type:
    RETAIL:  { min: 1.2, max: 3.8 }
    BUSINESS:{ min: 1.4, max: 5.0 }
    OTHER:   { min: 0.8, max: 3.0 }
  mobile_share_range_retail: { min: 0.45, max: 0.78 }
  desktop_share_range_business: { min: 0.18, max: 0.40 }
  shared_fraction_range_by_group:
    CONSUMER_PERSONAL: { min: 0.00, max: 0.08 }
    CONSUMER_SHARED:  { min: 0.08, max: 0.35 }
    COMPUTER_PORTABLE:{ min: 0.02, max: 0.18 }
  os_diversity_floor:
    MOBILE_PHONE: { min_distinct: 2, min_share: 0.05 }
    DESKTOP:      { min_distinct: 2, min_share: 0.05 }
  high_risk_fraction_cap: 0.12
  segment_variation_required_if_n_segments_ge: 6
  segment_variation_min_delta: 0.05
```

---

## 9) Acceptance checklist (MUST)

### Contract pins

* Uses the exact path/schema_ref for `prior_device_counts_6A`.

### Structural strictness

* YAML parses; unknown keys absent.
* Token-less (no timestamps/UUIDs/digests).
* No YAML anchors/aliases.
* All per-list items sorted deterministically (e.g., device_types sorted by id).

### Taxonomy compatibility

* Every `device_type/os_family/ua_family/device_risk_tier` referenced exists in `taxonomy_devices_6A`.
* Every `party_type/segment_id/region_id` referenced exists in `taxonomy_party_6A`.

### Feasibility (prevents S4 hard fails)

* For any cell where priors imply positive targets, allocation weights must permit `W_total>0` (i.e., `p_zero_weight < 1` for at least one eligible group) or S4 will fail by design. 
* Caps do not make the plan infeasible (e.g., don’t demand more devices than `max_devices_per_party × N_parties`).

### Non-toy realism corridors

* All `realism_targets` corridors pass (mobile share, shared fraction, OS diversity, high-risk cap).
* If enough segments exist, at least one segment materially differs (variation rule).

---
