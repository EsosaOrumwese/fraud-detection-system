# Authoring Guide — `ip_role_priors_6A` (`mlr.6A.s5.prior.ip_roles`, v1)

## 0) Purpose

`ip_role_priors_6A` is the **sealed, token-less, deterministic (RNG-free)** policy used by **6A.S5** to assign **static fraud posture** to IPs/endpoints (one row per `ip_id` in `s4_ip_base_6A`), producing `fraud_role_ip` (and optionally `static_risk_tier_ip`).

The S5 expanded spec explicitly expects IP-role priors such as:

* `NORMAL_IP`, `PROXY_IP`, `DATACENTRE_IP`, `HIGH_RISK_IP`, … 

This policy MUST be **non-toy**:

* most IPs are normal, but a meaningful minority represent shared networks (mobile/public Wi-Fi/corporate NAT), and a small fraction represent anonymizers / hosting / proxy-like contexts;
* risky roles correlate plausibly with **sealed** IP attributes and graph structure (degree/sharing), not with arrivals. 

---

## 1) Contract identity (binding pins)

From the 6A v1 contract surface:

* **manifest_key:** `mlr.6A.s5.prior.ip_roles` 
* **dataset_id:** `prior_ip_roles_6A`
* **path:** `config/layer3/6A/priors/ip_role_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/ip_role_priors_6A`
* **status:** `required` (consumed by `6A.S0` and `6A.S5`)
* **PII:** none; **retention_class:** engine_control_plane

Token-less posture:

* **No** timestamps, UUIDs, or digests in-file.
* 6A.S0 seals by exact bytes and records `sha256_hex` in `sealed_inputs_6A`. 

---

## 2) Allowed conditioning signals (must be sealed, no arrivals)

This file MUST declare a strict whitelist of signals that S5 may use. In v1, the allowed sources are:

### 2.1 From 6A.S4 IP artefacts (row-level)

* IP attributes: `ip_type`, `asn_class`, optional `risk_tier` / `risk_flags`, optional `churn_class`, optional `ip_version` (v4/v6 or `ipv6_share_bucket`).
* Graph edges: device↔IP links (and any optional party↔IP / merchant↔IP links your S4 emits). 

### 2.2 From taxonomies (row-level or metadata-only)

* `taxonomy_ips_6A` (valid `ip_type` and `asn_class` vocabulary).
* Optionally `taxonomy_devices_6A` if you bucket linked device types.

### 2.3 Optional cross-entity posture (recommended but must avoid cycles)

If you include it, restrict it to *coarse booleans* derived from already-computed posture summaries, and make it **optional**:

* e.g., `has_any_bot_like_device_linked` (computed after device role assignment)
* e.g., `has_any_mule_party_linked` (computed after party roles)

If you don’t want to pin an evaluation order, omit cross-posture dependence in v1.

**Forbidden (must not be used):**

* Arrival events (`arrival_events_5B`) or any 6B outputs (flows/labels). 

Fail-closed rule:

* if a feature is declared **required** but cannot be computed from sealed inputs, S5 MUST FAIL.

---

## 3) Role vocabulary (v1 MUST be non-toy)

### 3.1 Required roles (MUST include in v1)

Minimum role set (aligned to S5 spec examples): 

* `NORMAL_IP`
* `PROXY_IP`
* `DATACENTRE_IP`
* `HIGH_RISK_IP`

### 3.2 Recommended additional roles (helps realism without exploding complexity)

* `MOBILE_CARRIER_IP` (shared mobile NAT context)
* `PUBLIC_SHARED_IP` (public Wi-Fi / hospitality / campus)
* `CORPORATE_NAT_IP` (enterprise NAT / office)

If you include these, keep S5’s assignment guided via the taxonomy (`ip_type`, `asn_class`) so they don’t become arbitrary.

### 3.3 Optional risk tiers (recommended, consistent across entities)

* `LOW`, `STANDARD`, `ELEVATED`, `HIGH`

---

## 4) Policy shape (guided + deterministic)

To keep Codex autonomous and prevent “hand-wavy” rules, v1 SHOULD be a 3-stage deterministic + stochastic assignment:

1. **Deterministic IP grouping:** map `ip_type`/`asn_class` into `ip_group_id` (e.g., `RESIDENTIAL`, `MOBILE`, `PUBLIC_SHARED`, `CORPORATE`, `HOSTING`, `ANONYMIZER`).
2. **Deterministic risk score:** compute `risk_score_ip ∈ [0,1]` from:

   * taxonomy-derived base risk (ip_group)
   * degree/sharing indicators (how many devices/parties appear behind the IP)
   * churn/risk flags if present
3. **Tier + role draw:** map score→tier, then draw `fraud_role_ip` from `π(role | ip_group, tier)` plus bounded nudges for strong signals.

This keeps the policy expressive but still small and auditable.

---

## 5) Strict YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `ip_role_priors_6A`)
3. `policy_version` (string; MUST be `v1`)
4. `role_vocabulary` (list of objects)
5. `risk_tier_vocabulary` (list of objects)
6. `ip_groups` (object)
7. `feature_whitelist` (object)
8. `derived_feature_buckets` (object)
9. `risk_score_model` (object)
10. `risk_tier_thresholds` (object)
11. `role_probability_model` (object)
12. `optional_cluster_model` (object)
13. `constraints` (object)
14. `realism_targets` (object)
15. `notes` (optional string)

Unknown keys: **INVALID**.
Formatting MUST be token-less; no YAML anchors/aliases; deterministic ordering.

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

### 6.3 `ip_groups`

To keep tables small, define:

* `groups`: list of `{group_id, ip_types:[...], asn_classes:[...], semantics}`
* and a pinned evaluation rule:

  * first match wins by `group_priority` (explicit integer), or
  * deterministic fallback group `OTHER_IP` (only if your taxonomy includes such a type; otherwise FAIL)

### 6.4 `feature_whitelist`

* `required_sources`: e.g. `[s4_ip_base_6A, s4_ip_links_6A]`
* `allowed_features`: explicit list, e.g.:

  * `ip_group_id`, `ip_type`, `asn_class`
  * `deg_device_bucket`, `deg_party_bucket`
  * `has_anonymizer_type` (ip_type == VPN_PROXY or equivalent)
  * `has_hosting_asn` (asn_class == HOSTING_PROVIDER or equivalent)
  * optional `churn_bucket`, `ipv6_flag`, `risk_flag_any`
* `required_features`: subset that MUST be computable or FAIL

### 6.5 `derived_feature_buckets`

Provide pinned bucket edges + mapped values in [0,1], e.g.:

* `deg_device_bucket` (distinct devices behind IP)
* `deg_party_bucket` (distinct parties behind IP, if party links exist)
* `deg_account_bucket` (optional)

### 6.6 `risk_score_model`

Pinned deterministic law:

`risk_score = clamp( base_by_group[group] + Σ weight_i * (x_i - ref_i), 0, 1 )`

Where:

* `x_i` are bucket scores (0..1) and/or booleans (0/1) and/or churn/risk flags.
* `base_by_group` gives an interpretable baseline: hosting/anonymizer groups start higher than residential.

### 6.7 `risk_tier_thresholds`

* `tiers_in_order: [LOW, STANDARD, ELEVATED, HIGH]`
* thresholds partitioning [0,1] with `HIGH_max: 1.0`

### 6.8 `role_probability_model`

* `mode: by_group_and_risk_tier_v1`
* `pi_role_by_group_and_tier`: `(ip_group_id, tier) → [{role_id, prob}]` sums to 1.
* optional bounded `nudges` for strong signals:

  * if `deg_device_bucket` high → increase `HIGH_RISK_IP`
  * if `ip_group_id == ANONYMIZER` → increase `PROXY_IP`
  * if `ip_group_id == HOSTING` → increase `DATACENTRE_IP`

### 6.9 `optional_cluster_model` (recommended)

To avoid toy “independent proxy IPs”, allow correlated clusters:

* `enabled` bool
* `cluster_key` (e.g., `[asn_class]` or `[ip_group_id]`)
* `cluster_role` (e.g., `PROXY_IP`)
* `cluster_size_distribution` (zipf/geometric capK)
* deterministic rule for selecting cluster members from eligible IPs, then upgrading their roles until target fractions reached.

If disabled: roles are iid from `pi_role_by_group_and_tier`.

---

## 7) Non-toy realism corridors (MUST)

Your corridors should make toy outputs impossible.

Minimum required corridors:

* `proxy_fraction_world_range` (e.g., `{min: 0.002, max: 0.08}`)
* `datacentre_fraction_world_range` (e.g., `{min: 0.002, max: 0.10}`)
* `high_risk_fraction_world_range` (e.g., `{min: 0.01, max: 0.25}`)
* enrichment constraints:

  * `P(PROXY_IP | ip_group=ANONYMIZER) / P(PROXY_IP | ip_group!=ANONYMIZER) >= X`
  * `P(DATACENTRE_IP | ip_group=HOSTING) / P(DATACENTRE_IP | else) >= Y`
  * `P(HIGH_RISK_IP | deg_device high) / P(HIGH_RISK_IP | deg_device low) >= Z`
* `region_variation` (if multiple regions exist): require non-trivial variation in proxy/high-risk fraction.

---

## 8) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: ip_role_priors_6A
policy_version: v1

role_vocabulary:
  - { role_id: DATACENTRE_IP, label: Datacentre, description: "Hosting/datacentre-like endpoint posture.", severity_rank: 2 }
  - { role_id: HIGH_RISK_IP,  label: High risk,  description: "Elevated endpoint posture based on sharing/flags.", severity_rank: 3 }
  - { role_id: NORMAL_IP,     label: Normal,     description: "Baseline endpoint posture.", severity_rank: 0 }
  - { role_id: PROXY_IP,      label: Proxy,      description: "Proxy/VPN/anonymizer-like endpoint posture.", severity_rank: 2 }

risk_tier_vocabulary:
  - { tier_id: LOW,      label: Low,      description: "Low static posture.", severity_rank: 0 }
  - { tier_id: STANDARD, label: Standard, description: "Typical posture.",    severity_rank: 1 }
  - { tier_id: ELEVATED, label: Elevated, description: "Elevated posture.",   severity_rank: 2 }
  - { tier_id: HIGH,     label: High,     description: "High posture.",       severity_rank: 3 }

ip_groups:
  groups:
    - group_id: ANONYMIZER
      group_priority: 10
      ip_types: [VPN_PROXY]
      asn_classes: [HOSTING_PROVIDER]
      semantics: "VPN/proxy endpoints (anonymizing)."
    - group_id: HOSTING
      group_priority: 20
      ip_types: [DATACENTRE]
      asn_classes: [HOSTING_PROVIDER, CDN_EDGE]
      semantics: "Hosting/datacentre infrastructure."
    - group_id: MOBILE
      group_priority: 30
      ip_types: [MOBILE]
      asn_classes: [MNO]
      semantics: "Mobile carrier NAT/shared."
    - group_id: RESIDENTIAL
      group_priority: 40
      ip_types: [RESIDENTIAL]
      asn_classes: [CONSUMER_ISP]
      semantics: "Home broadband context."
    - group_id: PUBLIC_SHARED
      group_priority: 50
      ip_types: [PUBLIC_WIFI, HOTEL_TRAVEL, EDUCATION]
      asn_classes: [CONSUMER_ISP, ENTERPRISE, PUBLIC_SECTOR]
      semantics: "Shared public/campus/travel access."
    - group_id: CORPORATE
      group_priority: 60
      ip_types: [CORPORATE]
      asn_classes: [ENTERPRISE]
      semantics: "Corporate/office NAT."

feature_whitelist:
  required_sources: [s4_ip_base_6A, s4_ip_links_6A]
  allowed_features: [ip_group_id, deg_device_bucket, has_risk_flag_any, churn_bucket]
  required_features: [ip_group_id, deg_device_bucket]

derived_feature_buckets:
  deg_device_bucket:
    edges: [0, 1, 2, 5, 10, 50, 200, 1000]
    values: [0.00, 0.08, 0.15, 0.25, 0.38, 0.55, 0.75, 0.90, 0.98]
  churn_bucket:
    edges: [0, 1, 2]
    values: [0.10, 0.50, 0.85, 0.95]  # STABLE / DYNAMIC / HIGH_CHURN mapped upstream

risk_score_model:
  base_by_group:
    RESIDENTIAL: 0.35
    CORPORATE: 0.45
    PUBLIC_SHARED: 0.55
    MOBILE: 0.60
    HOSTING: 0.70
    ANONYMIZER: 0.78
  features:
    - { name: deg_device_bucket, source: GRAPH_DERIVED, ref: 0.15, weight: 0.22 }
    - { name: churn_bucket,      source: IP_ATTR,      ref: 0.50, weight: 0.10 }
    - { name: has_risk_flag_any, source: IP_ATTR,      ref: 0.00, weight: 0.15 }

risk_tier_thresholds:
  tiers_in_order: [LOW, STANDARD, ELEVATED, HIGH]
  thresholds: { LOW_max: 0.25, STANDARD_max: 0.65, ELEVATED_max: 0.85, HIGH_max: 1.00 }

role_probability_model:
  mode: by_group_and_risk_tier_v1
  pi_role_by_group_and_tier:
    RESIDENTIAL:
      LOW:      [{role_id: NORMAL_IP, prob: 0.9990}, {role_id: HIGH_RISK_IP, prob: 0.0010}]
      STANDARD: [{role_id: NORMAL_IP, prob: 0.9950}, {role_id: HIGH_RISK_IP, prob: 0.0050}]
      ELEVATED: [{role_id: NORMAL_IP, prob: 0.9700}, {role_id: HIGH_RISK_IP, prob: 0.0300}]
      HIGH:     [{role_id: NORMAL_IP, prob: 0.9200}, {role_id: HIGH_RISK_IP, prob: 0.0800}]

    HOSTING:
      LOW:      [{role_id: DATACENTRE_IP, prob: 0.9800}, {role_id: HIGH_RISK_IP, prob: 0.0200}]
      STANDARD: [{role_id: DATACENTRE_IP, prob: 0.9300}, {role_id: HIGH_RISK_IP, prob: 0.0700}]
      ELEVATED: [{role_id: DATACENTRE_IP, prob: 0.8500}, {role_id: HIGH_RISK_IP, prob: 0.1500}]
      HIGH:     [{role_id: DATACENTRE_IP, prob: 0.7000}, {role_id: HIGH_RISK_IP, prob: 0.3000}]

    ANONYMIZER:
      LOW:      [{role_id: PROXY_IP, prob: 0.9500}, {role_id: HIGH_RISK_IP, prob: 0.0500}]
      STANDARD: [{role_id: PROXY_IP, prob: 0.9000}, {role_id: HIGH_RISK_IP, prob: 0.1000}]
      ELEVATED: [{role_id: PROXY_IP, prob: 0.8200}, {role_id: HIGH_RISK_IP, prob: 0.1800}]
      HIGH:     [{role_id: PROXY_IP, prob: 0.7000}, {role_id: HIGH_RISK_IP, prob: 0.3000}]

  nudges:
    - if_feature: "deg_device_bucket >= 0.75"
      multiply_roles: { HIGH_RISK_IP: 1.50, NORMAL_IP: 0.90 }
      clip_multiplier: { min: 0.70, max: 2.00 }

optional_cluster_model:
  enabled: true
  cluster_key: [ip_group_id]
  cluster_role: PROXY_IP
  cluster_size_distribution: { model_id: zipf_capK_v1, min_k: 2, max_k: 500, alpha: 1.20 }

constraints:
  fail_on_missing_rule: true
  prob_dp: 12
  max_role_share_caps_world:
    PROXY_IP: 0.10
    DATACENTRE_IP: 0.12
    HIGH_RISK_IP: 0.30
  min_non_normal_presence:
    HIGH_RISK_IP: 0.01

realism_targets:
  proxy_fraction_world_range: { min: 0.002, max: 0.08 }
  datacentre_fraction_world_range: { min: 0.002, max: 0.10 }
  high_risk_fraction_world_range: { min: 0.01, max: 0.25 }
  proxy_enrichment_in_anonymizer_min_ratio: 5.0
  datacentre_enrichment_in_hosting_min_ratio: 4.0
  high_risk_enrichment_in_high_degree_min_ratio: 3.0
  region_variation:
    required_if_n_regions_ge: 3
    min_delta_in_proxy_fraction: 0.002
```

---

## 9) Acceptance checklist (MUST)

1. **Contract pins match** (`mlr.6A.s5.prior.ip_roles`, correct path/schema_ref).
2. **Token-less + strict**: no timestamps/UUIDs/digests; no YAML anchors/aliases; unknown keys absent.
3. **Role vocab includes required roles** (at least `NORMAL_IP`, `PROXY_IP`, `DATACENTRE_IP`, `HIGH_RISK_IP`). 
4. **Taxonomy compatibility**: every `ip_type` / `asn_class` referenced exists in `taxonomy_ips_6A`.
5. **Probabilities valid**: every `(group_id, tier)` distribution sums to 1 within tolerance; probs ∈ [0,1].
6. **Non-toy corridors pass**: world-level fractions + enrichment ratios + region variation (if applicable).
7. **Feasibility**: policy always assigns exactly one role per IP (no “unhandled” groups; missing group ⇒ FAIL CLOSED).

---

## 10) Change control (MUST)

* Changing role ids, thresholds, group definitions, or feature semantics is **behaviour-breaking** → bump the file version (`…v2.yaml`) and update S5 validation corridors accordingly.
