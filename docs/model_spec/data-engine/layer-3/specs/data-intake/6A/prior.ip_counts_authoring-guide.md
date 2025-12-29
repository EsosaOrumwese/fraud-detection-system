# Authoring Guide — `ip_count_priors_6A` (`mlr.6A.prior.ip_counts`, v1)

## 0) Purpose

`ip_count_priors_6A` is the **sealed, token-less, RNG-free** prior pack that **6A.S4** uses to plan and realise the **IP / endpoint universe** and its **sharing structure**:

* how many distinct IPs exist per `(region_id, ip_type, asn_class)` planning cell
* how many IPs a device/party tends to “use” (static distinct IP set over the world horizon)
* how many devices/parties share the same IP (NAT/public Wi-Fi/datacentre fan-out)
* deterministic attribute mixes for IP nodes (IPv4/IPv6, churn class, static risk tier/flags) consistent with `taxonomy.ips`

This file MUST prevent “toy worlds” (e.g., everyone uses 1 residential IP, no shared networks, no datacentre/VPN exposure), while staying **fully guided** so Codex can author it without judgment calls.

---

## 1) Contract identity (binding)

* **manifest_key:** `mlr.6A.prior.ip_counts`
* **dataset_id:** `prior_ip_counts_6A`
* **path:** `config/layer3/6A/priors/ip_count_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/ip_count_priors_6A`
* **status:** `required` (consumed by `6A.S0` and `6A.S4`)

**Token-less posture:** no timestamps, UUIDs, or embedded digests. 6A.S0 seals exact bytes and records `sha256_hex` in `sealed_inputs_6A`.

---

## 2) Dependencies (MUST exist & be compatible)

This prior MUST be authored against:

* `taxonomy_ips_6A` (`mlr.6A.taxonomy.ips`) — provides `ip_type`, `asn_class`, and optional risk vocab.
* `taxonomy_devices_6A` — for device grouping when modelling “IPs per device by device_type group”.
* `taxonomy_party_6A` — for `region_id` universe.
* `prior_device_counts_6A` — because S4 derives `N_devices_ref` per region from device planning.

Optional (only if you enable direct party/merchant IP links):

* `prior_segmentation_6A` (segment feature tilts) 

Fail-closed rule:

* Any `ip_type/asn_class` referenced here MUST exist in `taxonomy_ips_6A`, else S4 fails.

---

## 3) Pinned S4 semantics this prior must support

### 3.1 IP planning cell (v1)

S4 defines an IP planning cell typically as:

```text
c_ip = (region_id, ip_type, asn_class)
```

and computes continuous targets `N_ip_target(c_ip)` then integerises to `N_ip(c_ip)` with RNG (`ip_count_realisation`). (This prior is RNG-free; it supplies the parameters.)

### 3.2 How `N_ip_target(c_ip)` is computed (binding, v1)

To make the plan deterministic and feasible, v1 MUST use the identity:

1. **Edge demand (device→IP edges)**
   For each region `r`, define expected device→IP edges:

```text
E_dev_ip_target(r) = Σ_{device_group g} N_devices_ref(r,g) * λ_ip_per_device(r,g)
```

2. **Split edges across ip_type/asn_class**
   Using `π_ip_cell(r, ip_type, asn_class)`:

```text
E_target(c_ip) = E_dev_ip_target(region_id=r) * π_ip_cell(c_ip)
```

3. **Convert edges into IP node demand using sharing mean**
   If the mean devices per IP for this cell is `μ_dev_per_ip(c_ip)`:

```text
N_ip_target(c_ip) = E_target(c_ip) / max(μ_dev_per_ip(c_ip), eps)
```

This is the core “shared IP” logic:

* higher sharing → larger `μ_dev_per_ip` → fewer IP nodes
* lower sharing → smaller `μ_dev_per_ip` → more IP nodes

S4 then integerises `N_ip_target(c_ip)` into `N_ip(c_ip)`.

---

## 4) What this prior MUST provide (v1)

### 4.1 Device groups (for IP behaviour)

A deterministic mapping from `taxonomy.devices.device_type` → `device_group_id`, e.g.:

* `CONSUMER_MOBILE`
* `CONSUMER_COMPUTER`
* `MERCHANT_TERMINAL`
* `SERVER_BACKEND`
* `IOT_OTHER`

### 4.2 IP edge demand: `λ_ip_per_device(r,g)`

* base `λ_ip_per_device_by_group[g]`
* optional region tilt (deterministic) via a bounded multiplier

Interpretation: number of distinct IPs a device is associated with (static set over the world horizon), not time-series churn.

### 4.3 IP cell mix: `π_ip_cell(c_ip)`

A probability mass function over `(ip_type, asn_class)` per region, summing to 1 for each region.

This is built in two deterministic stages:

* `π_ip_type|region(r, ip_type)`
* `π_asn_class|ip_type(ip_type, asn_class)`
  then:

```text
π_ip_cell(r, ip_type, asn_class) = π_ip_type|region(r, ip_type) * π_asn_class|ip_type(ip_type, asn_class)
```

and renormalise over valid pairs.

### 4.4 Sharing model per IP cell

For each `c_ip`, provide:

* `μ_dev_per_ip(c_ip)` (mean devices per IP)
* `deg_model_dev_per_ip` distribution parameters (to sample `k_D` per IP instance in S4’s `ip_allocation_sampling`)
* optionally `μ_party_per_ip(c_ip)` and parameters for direct party fan-out (if you model direct party→IP links)

### 4.5 Attribute distributions for IP nodes

Deterministic distributions conditional on `(ip_type, asn_class)` for:

* `ipv6_share` (or `ip_version_mix`)
* `churn_class` (e.g., `STABLE`, `DYNAMIC`, `HIGH_CHURN`)
* risk tiers/flags if `taxonomy.ips` provides vocab

### 4.6 Address generation policy (non-toy, safe)

A deterministic rule for `ip_address_masked` that:

* guarantees uniqueness per `ip_id`
* uses **documentation / non-routable** ranges only (safe synthetic)
* supports both IPv4 and IPv6 generation according to `ip_version_mix`

---

## 5) Strict YAML structure (MUST)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `prior_id` (string; MUST be `ip_count_priors_6A`)
3. `prior_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `cell_definition` (object)
6. `device_groups` (object)
7. `ip_edge_demand_model` (object)
8. `ip_type_mix_model` (object)
9. `asn_mix_model` (object)
10. `sharing_model` (object)
11. `attribute_models` (object)
12. `address_policy` (object)
13. `constraints` (object)
14. `realism_targets` (object)
15. `notes` (optional string)

Unknown keys: **INVALID**.

Formatting MUST:

* token-less (no timestamps/digests)
* no YAML anchors/aliases
* deterministic ordering (sorted lists by id)

---

## 6) Section contracts (v1)

### 6.1 `bindings` (MUST)

* `party_taxonomy_ref: taxonomy_party_6A`
* `device_taxonomy_ref: taxonomy_devices_6A`
* `ip_taxonomy_ref: taxonomy_ips_6A`
* `device_counts_ref: prior_device_counts_6A`

### 6.2 `cell_definition` (MUST)

* `ip_cell: [region_id, ip_type, asn_class]`

### 6.3 `device_groups` (MUST)

* `groups`: list of `{group_id, device_types:[...], semantics}`
* `device_type_to_group` MUST be derivable (either explicit map or implied by groups)

### 6.4 `ip_edge_demand_model` (MUST)

Required:

* `mode: lambda_ip_per_device_v1`
* `lambda_ip_per_device_by_group` (map group_id → float ≥ 0)
* optional `region_multiplier`:

  * `enabled` (bool)
  * `mode: by_region_score_v1`
  * `region_scores`: list `{region_id, score}` in [0,1]
  * `clip_multiplier` `{min,max}`

### 6.5 `ip_type_mix_model` (MUST)

Required:

* `mode: by_region_v1`
* `pi_ip_type_by_region`: list of:

  * `{region_id, pi_ip_type: [{ip_type, share}]}`

Rules:

* for each region: shares sum to 1 (tolerance 1e-12)
* every ip_type must exist in `taxonomy_ips_6A`

### 6.6 `asn_mix_model` (MUST)

Required:

* `mode: by_ip_type_v1`
* `pi_asn_class_by_ip_type`: list of:

  * `{ip_type, pi_asn: [{asn_class, share}]}`

Rules:

* for each ip_type: shares sum to 1
* every asn_class must exist in taxonomy

### 6.7 `sharing_model` (MUST)

Required:

* `mode: dev_per_ip_and_party_per_ip_v1`
* `mu_dev_per_ip`: list `{ip_type, asn_class, mean}` with mean > 0
* `deg_dev_per_ip_distribution`:

  * per `(ip_type, asn_class)` provide a model:

    * `model_id ∈ { geometric_capK_v1, zipf_capK_v1 }`
    * params + caps (`min_k`, `max_k`)
* `direct_party_links`:

  * `enabled` (bool)
  * if enabled:

    * `mu_party_per_ip` + distribution model by `(ip_type, asn_class)`
    * `lambda_ip_per_party_by_party_type` (map party_type → float ≥ 0)
  * if disabled:

    * S4 MUST attach parties to IPs only via device links (party_id nullable in `s4_ip_links_6A` rows)

### 6.8 `attribute_models` (MUST)

Required sub-objects (even if disabled):

* `ip_version_model`
* `churn_model`
* `risk_tier_model`
* `risk_flags_model`

Each MUST contain:

* `enabled` (bool)
* `mode`
* `defaults`
* `overrides` (optional)

Recommended v1 modes:

* `ip_version_model.mode = by_ip_type_v1` (ipv6_share by ip_type)
* `churn_model.mode = by_ip_type_asn_class_v1`
* `risk_tier_model.mode = deterministic_by_ip_type_v1` (datacentre/vpn higher)
* `risk_flags_model.mode = by_ip_type_asn_class_v1` (optional)

### 6.9 `address_policy` (MUST)

Required:

* `mode: documentation_ranges_v1`
* `ipv4_pools` list of CIDRs (MUST be documentation ranges only)
* `ipv6_pool` CIDR (MUST be documentation range only)
* `assignment`:

  * `mode: hash_from_ip_id_v1`
  * `salt_label` (string constant, e.g. `"ip_address_masked"`)
  * `open_interval_mapping` (string, must match your numeric policy’s mapping law)
* `formatting`:

  * `ipv4_style: dotted_decimal`
  * `ipv6_style: compressed_lower`

### 6.10 `constraints` (MUST)

Required:

* `fail_on_missing_rule: true`
* `max_total_ips_world` (int)
* `max_total_ip_edges_world` (int)
* `max_ips_per_device` (int)
* `max_devices_per_ip` (int)
* `max_parties_per_ip` (int)
* `eps_min_mu_dev_per_ip` (float > 0)

### 6.11 `realism_targets` (MUST)

Corridors (fail closed if violated):

Required:

* `lambda_ip_per_device_range_by_group` (group_id → {min,max})
* `mu_dev_per_ip_range_by_ip_type` (ip_type → {min,max})
* `datacentre_fraction_range` ({min,max})  *(share of edges or nodes; define explicitly)*
* `vpn_proxy_fraction_range` ({min,max})
* `ipv6_share_range_by_ip_type` (ip_type → {min,max})
* `shared_network_presence_min` (float in (0,1))  *(fraction of devices that see any shared IP type such as PUBLIC_WIFI/MOBILE)*
* `region_variation_required_if_n_regions_ge` (int ≥ 2)
* `region_variation_min_delta` (float ≥ 0)

---

## 7) Non-toy defaults (recommended anchors)

These are realistic guardrails (not “truth”), to keep Codex from producing flat toy worlds.

### 7.1 Mean IPs per device (`λ_ip_per_device`)

Typical:

* `CONSUMER_MOBILE`: 2.0–8.0 (mobile network + Wi-Fi + travel)
* `CONSUMER_COMPUTER`: 1.2–5.0
* `MERCHANT_TERMINAL`: 0.8–3.0 (more stable)
* `SERVER_BACKEND`: 1.0–4.0
* `IOT_OTHER`: 0.8–3.0

### 7.2 Mean devices per IP (`μ_dev_per_ip`)

By `ip_type` (ballpark):

* `RESIDENTIAL`: 1–6
* `CORPORATE`: 5–200
* `PUBLIC_WIFI`: 10–500
* `MOBILE`: 20–1500
* `DATACENTRE`: 50–50_000
* `VPN_PROXY`: 50–20_000

These means drive node counts via `N_ip_target = E / μ`.

---

## 8) Authoring procedure (Codex-ready)

1. Load `taxonomy_ips_6A` and list all `ip_type` and `asn_class`.
2. Load `taxonomy_devices_6A` and define `device_groups` that are stable (do not depend on shares).
3. Set `λ_ip_per_device_by_group` using §7.1 anchors.
4. Define `π_ip_type_by_region` (not uniform-toy). Ensure regions differ mildly if multiple regions exist.
5. Define `π_asn_class_by_ip_type` using plausible constraints:

   * MOBILE → mostly `MNO`
   * RESIDENTIAL → mostly `CONSUMER_ISP`
   * DATACENTRE/VPN → mostly `HOSTING_PROVIDER` (+ `CDN_EDGE` for DATACENTRE if present)
6. Define `μ_dev_per_ip` and degree distributions per cell (shared networks heavy-tailed).
7. Define IP attributes:

   * ipv6 share higher for mobile/datacentre than residential (plausible)
   * churn higher for MOBILE/PUBLIC_WIFI than CORPORATE
   * risk tiers/flags aligned to ip_type
8. Define address policy using documentation ranges only.
9. Run acceptance checks; fail closed on any corridor violation.
10. Freeze formatting (sorted lists; token-less; no anchors/aliases).

---

## 9) Minimal v1 example (shape only)

```yaml
schema_version: 1
prior_id: ip_count_priors_6A
prior_version: v1

bindings:
  party_taxonomy_ref: taxonomy_party_6A
  device_taxonomy_ref: taxonomy_devices_6A
  ip_taxonomy_ref: taxonomy_ips_6A
  device_counts_ref: prior_device_counts_6A

cell_definition:
  ip_cell: [region_id, ip_type, asn_class]

device_groups:
  groups:
    - group_id: CONSUMER_MOBILE
      device_types: [MOBILE_PHONE, WEARABLE]
      semantics: "Consumer mobile devices."
    - group_id: CONSUMER_COMPUTER
      device_types: [LAPTOP, DESKTOP, TABLET]
      semantics: "Consumer computers/tablets."
    - group_id: MERCHANT_TERMINAL
      device_types: [POS_TERMINAL, ATM, KIOSK]
      semantics: "Merchant terminals."
    - group_id: SERVER_BACKEND
      device_types: [SERVER]
      semantics: "Backend/server devices."

ip_edge_demand_model:
  mode: lambda_ip_per_device_v1
  lambda_ip_per_device_by_group:
    CONSUMER_MOBILE: 4.5
    CONSUMER_COMPUTER: 2.2
    MERCHANT_TERMINAL: 1.4
    SERVER_BACKEND: 1.8

ip_type_mix_model:
  mode: by_region_v1
  pi_ip_type_by_region:
    - region_id: REGION_A
      pi_ip_type:
        - { ip_type: RESIDENTIAL, share: 0.42 }
        - { ip_type: MOBILE,      share: 0.33 }
        - { ip_type: CORPORATE,   share: 0.10 }
        - { ip_type: PUBLIC_WIFI, share: 0.08 }
        - { ip_type: DATACENTRE,  share: 0.05 }
        - { ip_type: VPN_PROXY,   share: 0.02 }

asn_mix_model:
  mode: by_ip_type_v1
  pi_asn_class_by_ip_type:
    - ip_type: RESIDENTIAL
      pi_asn: [{ asn_class: CONSUMER_ISP, share: 1.0 }]
    - ip_type: MOBILE
      pi_asn: [{ asn_class: MNO, share: 1.0 }]
    - ip_type: DATACENTRE
      pi_asn:
        - { asn_class: HOSTING_PROVIDER, share: 0.85 }
        - { asn_class: CDN_EDGE,         share: 0.15 }
    - ip_type: VPN_PROXY
      pi_asn: [{ asn_class: HOSTING_PROVIDER, share: 1.0 }]

sharing_model:
  mode: dev_per_ip_and_party_per_ip_v1
  mu_dev_per_ip:
    - { ip_type: RESIDENTIAL, asn_class: CONSUMER_ISP, mean: 2.2 }
    - { ip_type: MOBILE,      asn_class: MNO,          mean: 140.0 }
    - { ip_type: DATACENTRE,  asn_class: HOSTING_PROVIDER, mean: 6000.0 }
    - { ip_type: VPN_PROXY,   asn_class: HOSTING_PROVIDER, mean: 2500.0 }
  deg_dev_per_ip_distribution:
    - ip_type: RESIDENTIAL
      asn_class: CONSUMER_ISP
      model_id: geometric_capK_v1
      min_k: 1
      max_k: 10
      p: 0.55
    - ip_type: MOBILE
      asn_class: MNO
      model_id: zipf_capK_v1
      min_k: 5
      max_k: 5000
      alpha: 1.20
    - ip_type: DATACENTRE
      asn_class: HOSTING_PROVIDER
      model_id: zipf_capK_v1
      min_k: 10
      max_k: 80000
      alpha: 1.10
  direct_party_links:
    enabled: false

attribute_models:
  ip_version_model:
    enabled: true
    mode: by_ip_type_v1
    defaults:
      RESIDENTIAL: { ipv6_share: 0.25 }
      MOBILE:      { ipv6_share: 0.55 }
      DATACENTRE:  { ipv6_share: 0.40 }
      VPN_PROXY:   { ipv6_share: 0.35 }
    overrides: []
  churn_model:
    enabled: true
    mode: by_ip_type_asn_class_v1
    defaults:
      RESIDENTIAL: { churn_class: STABLE }
      MOBILE:      { churn_class: HIGH_CHURN }
      DATACENTRE:  { churn_class: STABLE }
      VPN_PROXY:   { churn_class: HIGH_CHURN }
    overrides: []
  risk_tier_model:
    enabled: true
    mode: deterministic_by_ip_type_v1
    defaults:
      RESIDENTIAL: { risk_tier: LOW }
      MOBILE:      { risk_tier: STANDARD }
      DATACENTRE:  { risk_tier: HIGH }
      VPN_PROXY:   { risk_tier: HIGH }
    overrides: []
  risk_flags_model:
    enabled: false
    mode: none
    defaults: {}
    overrides: []

address_policy:
  mode: documentation_ranges_v1
  ipv4_pools: ["192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"]
  ipv6_pool: "2001:db8::/32"
  assignment:
    mode: hash_from_ip_id_v1
    salt_label: "ip_address_masked"
    open_interval_mapping: "numeric_policy.open_interval_u64"
  formatting:
    ipv4_style: dotted_decimal
    ipv6_style: compressed_lower

constraints:
  fail_on_missing_rule: true
  max_total_ips_world: 300000000
  max_total_ip_edges_world: 900000000
  max_ips_per_device: 40
  max_devices_per_ip: 100000
  max_parties_per_ip: 100000
  eps_min_mu_dev_per_ip: 1.0e-9

realism_targets:
  lambda_ip_per_device_range_by_group:
    CONSUMER_MOBILE: { min: 2.0, max: 10.0 }
    CONSUMER_COMPUTER: { min: 1.0, max: 7.0 }
    MERCHANT_TERMINAL: { min: 0.5, max: 4.0 }
  mu_dev_per_ip_range_by_ip_type:
    RESIDENTIAL: { min: 1.0, max: 8.0 }
    MOBILE:      { min: 10.0, max: 3000.0 }
    DATACENTRE:  { min: 50.0, max: 100000.0 }
    VPN_PROXY:   { min: 50.0, max: 50000.0 }
  datacentre_fraction_range: { min: 0.01, max: 0.20 }
  vpn_proxy_fraction_range: { min: 0.005, max: 0.10 }
  ipv6_share_range_by_ip_type:
    RESIDENTIAL: { min: 0.05, max: 0.60 }
    MOBILE:      { min: 0.20, max: 0.85 }
    DATACENTRE:  { min: 0.10, max: 0.75 }
  shared_network_presence_min: 0.15
  region_variation_required_if_n_regions_ge: 2
  region_variation_min_delta: 0.03
```

---

## 10) Acceptance checklist (MUST)

### 10.1 Contract pins

* manifest_key/dataset_id/path/schema_ref match v1 contracts.

### 10.2 Structural strictness

* YAML parses cleanly.
* Unknown keys absent everywhere.
* Token-less: no timestamps/UUIDs/digests.
* No YAML anchors/aliases.
* Deterministic ordering:

  * region rows sorted by `region_id`
  * mixes sorted by `(ip_type, asn_class)`.

### 10.3 Taxonomy compatibility

* Every referenced `ip_type/asn_class` exists in `taxonomy_ips_6A`.
* Every referenced `device_type` exists in `taxonomy_devices_6A`.

### 10.4 Feasibility guards (prevents S4 hard fails)

* `μ_dev_per_ip(c_ip) > 0` for all defined cells.
* `λ_ip_per_device_by_group[g]` finite and not so large that it violates `max_ips_per_device`.
* Safety caps not violated by implied totals:

  * total IP nodes ≤ `max_total_ips_world`
  * total edges ≤ `max_total_ip_edges_world`

### 10.5 Non-toy corridors

* `realism_targets` all satisfied (datacentre/VPN presence, shared network presence, ipv6 share plausibility, regional variation if multiple regions).

---

## 11) Change control (MUST)

* Changing `c_ip` definition, the edge→node conversion law, or the address policy is **breaking** → bump file version (`...v2.yaml`) and update dependent validation expectations in `6A.S4` / `6A.S5`.

---
