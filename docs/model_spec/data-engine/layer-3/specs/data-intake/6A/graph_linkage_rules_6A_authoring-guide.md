# Authoring Guide — `graph_linkage_rules_6A` (`GRAPH_LINKAGE_RULES`, v1)

## 0) Purpose

`graph_linkage_rules_6A` is the **sealed ruleset** that 6A.S4 uses to realise a **static device/IP graph** while enforcing:

* **device sharing patterns** (single-party vs shared; parties per shared device),
* **IP sharing patterns** (devices per IP, parties per IP, special handling for datacentre/VPN),
* **attachment constraints** (max degrees, forbidden combos),
* and a **link_role vocabulary** for:

  * `s4_device_links_6A` (`PRIMARY_OWNER`, `SECONDARY_USER`, `MERCHANT_TERMINAL`, `ASSOCIATED_ACCOUNT_ACCESS`, …)
  * `s4_ip_links_6A` (`TYPICAL_DEVICE_IP`, `RECENT_LOGIN_IP`, `MERCHANT_ENDPOINT`, `SHARED_PUBLIC_WIFI`, …).

S4 explicitly calls out that “graph/linkage rules” MUST exist as sealed inputs when treated as required, with roles like `"GRAPH_LINKAGE_RULES"` / `"DEVICE_LINKAGE_RULES"`.

This artefact MUST be:

* **token-less** (no timestamps, no in-file digests),
* **RNG-free** (pure rules; RNG happens in S4 sampling),
* **fields-strict** (unknown keys invalid),
* **non-toy** (enforced by corridors + caps + required patterns).

---

## 1) Contract wiring note

This artefact is registered in the 6A v2 contract surface and MUST be sealed by S0 as a row-level policy input.

**Recommended v1 registration (add to artefact_registry + dataset_dictionary later):**

* `manifest_key: mlr.6A.policy.graph_linkage_rules`
* `dataset_id: graph_linkage_rules_6A`
* `path_template: config/layer3/6A/policy/graph_linkage_rules_6A.v1.yaml`
* `schema_ref: schemas.6A.yaml#/policy/graph_linkage_rules_6A`
* `sealed_inputs role: GRAPH_LINKAGE_RULES`
* `sealed_inputs status: REQUIRED`
* `sealed_inputs read_scope: ROW_LEVEL`

---

## 2) What this ruleset controls (and what it does NOT)

### In scope (this file owns)

* **Which edges exist** in `s4_device_links_6A` and `s4_ip_links_6A`, and what **link_role** means.
* Degree caps + forbidden combos (fail-closed).
* How to map “counts from priors” → “typed edges” (e.g., IPs per device become `TYPICAL_DEVICE_IP` vs `RECENT_LOGIN_IP`).

### Out of scope (must be elsewhere)

* **How many devices exist** → `prior_device_counts_6A`.
* **How many IPs exist** and the **ip_type/asn_class mix** → `prior_ip_counts_6A`.
* Fraud roles → S5 priors.
* Any per-arrival behaviour → 6B.

---

## 3) Required datasets this must align with

This config must align with:

* `s4_device_links_6A` schema + ordering + “wide optional columns” design.
* `s4_ip_links_6A` schema + ordering.
* S4 invariants: link tables must reference existing IDs only, and sharing patterns implied by links must respect priors/config constraints.

---

## 4) File identity (recommended v1)

* **Path:** `config/layer3/6A/policy/graph_linkage_rules_6A.v1.yaml`
* **Format:** YAML (UTF-8, LF)
* **Token-less:** no `generated_at`, no digests, no UUIDs.
* **Sealing:** 6A.S0 records `sha256_hex` in `sealed_inputs_6A`.

---

## 5) Strict YAML structure (MUST)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `config_id` (string; MUST be `graph_linkage_rules_6A`)
3. `config_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `device_groups` (object)
6. `ip_groups` (object)
7. `device_link_roles` (list of objects)
8. `ip_link_roles` (list of objects)
9. `device_owner_and_sharing` (object)
10. `device_access_edges` (object)
11. `device_ip_edges` (object)
12. `direct_entity_ip_edges` (object)
13. `degree_caps` (object)
14. `forbidden_combinations` (list of objects)
15. `realism_targets` (object)
16. `acceptance_checks` (object)
17. `notes` (optional string)

Unknown keys: **INVALID**.
No YAML anchors/aliases.

---

## 6) `bindings` (MUST)

Declare which sealed artefacts this ruleset expects to exist (so Codex can fail fast):

* `device_taxonomy_ref: taxonomy_devices_6A`
* `ip_taxonomy_ref: taxonomy_ips_6A`
* `account_taxonomy_ref: taxonomy_account_types_6A`
* `instrument_taxonomy_ref: taxonomy_instrument_types_6A`
* `device_counts_ref: prior_device_counts_6A`
* `ip_counts_ref: prior_ip_counts_6A`

Purpose: link roles and constraints must only reference IDs/types that exist in the sealed taxonomies/priors.

---

## 7) Grouping (MUST)

### 7.1 `device_groups`

Define a small set of device groups + a mapping from `device_type` → `device_group_id`.

Minimum recommended groups:

* `CONSUMER_PERSONAL` (phones/wearables)
* `CONSUMER_SHARED` (shared desktops/tablets)
* `COMPUTER_PORTABLE` (laptops)
* `MERCHANT_TERMINAL` (POS/ATM/kiosk)
* `BACKEND_SERVER` (servers/API clients) *(optional)*

### 7.2 `ip_groups`

Define IP groups based on `(ip_type, asn_class)` so constraints can be expressed cleanly.

Minimum recommended groups:

* `RESIDENTIAL`
* `MOBILE_CARRIER`
* `CORPORATE_NAT`
* `PUBLIC_SHARED`
* `HOSTING_DATACENTRE`
* `ANONYMIZER_PROXY`

---

## 8) Link-role vocabularies (MUST)

S4 requires `link_role` fields to exist and carry fixed semantics.

### 8.1 `device_link_roles[]`

Each role entry MUST include:

* `role_id`
* `description`
* `required_nonnull_fields` (subset of `{party_id, account_id, instrument_id, merchant_id}`)
* `forbidden_nonnull_fields` (subset)
* `semantic_class` (enum: `OWNERSHIP`, `SHARING`, `ACCESS`)

Minimum v1 set (recommended, matches S4 examples):

* `PRIMARY_OWNER` (party_id required)
* `SECONDARY_USER` (party_id required)
* `MERCHANT_TERMINAL` (merchant_id required)
* `ASSOCIATED_ACCOUNT_ACCESS` (account_id required; party_id optional)
* `ASSOCIATED_INSTRUMENT_ACCESS` (instrument_id required; party_id optional) *(recommended)*

### 8.2 `ip_link_roles[]`

Each role entry MUST include:

* `role_id`
* `description`
* `required_nonnull_fields` (subset of `{device_id, party_id, merchant_id}`)
* `forbidden_nonnull_fields` (subset)
* `semantic_class` (enum: `DEVICE_ENDPOINT`, `DIRECT_ENDPOINT`, `MERCHANT_ENDPOINT`, `SHARED_CONTEXT`)

Minimum v1 set (recommended, matches S4 examples):

* `TYPICAL_DEVICE_IP` (device_id required)
* `RECENT_LOGIN_IP` (device_id required)
* `MERCHANT_ENDPOINT` (merchant_id required)
* `SHARED_PUBLIC_WIFI` (device_id required; indicates “shared public context”)

---

## 9) Core rule blocks

### 9.1 `device_owner_and_sharing`

Defines:

* owner_kind per device_group (`PARTY` vs `MERCHANT`)
* `p_shared` per device_group (probability shared)
* `parties_per_shared_device` distribution per group (`geometric_capK_v1` or `zipf_capK_v1`)
* which roles to emit:

  * always 1 `PRIMARY_OWNER` for PARTY-owned devices
  * emit `(k-1)` `SECONDARY_USER` edges when shared
  * always 1 `MERCHANT_TERMINAL` edge for MERCHANT-owned terminal devices

### 9.2 `device_access_edges`

Defines how to emit `ASSOCIATED_ACCOUNT_ACCESS` and `ASSOCIATED_INSTRUMENT_ACCESS` edges.

Required fields:

* `account_edges_per_device_by_group` distribution (ZI-Poisson capK recommended)
* `instrument_edges_per_device_by_group` distribution
* selection scope:

  * `OWNERS_ONLY` or `OWNERS_AND_SHARED_USERS`
* hard fail/degrade rules:

  * if `min_k > 0` and eligible set empty ⇒ FAIL
  * else emit 0 edges

### 9.3 `device_ip_edges`

Defines how the IP-per-device result (from `prior_ip_counts_6A`) becomes **typed** device↔IP edges.

Required fields:

* `edge_roles_by_group`:

  * per device_group: `{role_id -> share}` summing to 1 over the device-edge roles you use
* `role_to_allowed_ip_groups`:

  * e.g., `TYPICAL_DEVICE_IP` allows `{RESIDENTIAL, MOBILE_CARRIER, CORPORATE_NAT}`
  * `RECENT_LOGIN_IP` allows `{PUBLIC_SHARED, ANONYMIZER_PROXY, HOSTING_DATACENTRE}` (small)
  * `SHARED_PUBLIC_WIFI` allows `{PUBLIC_SHARED}` only
* `role_allocation_rule` (v1 pinned):

  * if a device has K IP edges:

    * allocate at least 1 to `TYPICAL_DEVICE_IP` (if K≥1),
    * allocate 0–1 to `SHARED_PUBLIC_WIFI` (if eligible by device_group and K≥2),
    * remaining to `RECENT_LOGIN_IP`
  * if any role cannot be satisfied due to `allowed_ip_groups` constraints, degrade by reassigning to the next permissible role; if none possible ⇒ FAIL.

### 9.4 `direct_entity_ip_edges`

Defines whether to emit direct `party_id`→`ip_id` and `merchant_id`→`ip_id` edges (in `s4_ip_links_6A`).

Required:

* `direct_party_ip_edges.enabled` (bool)
* `direct_merchant_ip_edges.enabled` (bool)

If enabled, define:

* distribution of direct IPs per entity (capK)
* allowed ip_groups
* roles to use (e.g., `MERCHANT_ENDPOINT` for merchants)

If disabled:

* S4 must still produce a consistent graph by routing party↔IP exposure via device↔IP edges only.

---

## 10) Constraints & forbidden combinations

### 10.1 `degree_caps`

Must include (at minimum):

* per-device caps by device_group:

  * `max_parties_per_device`
  * `max_accounts_per_device`
  * `max_instruments_per_device`
  * `max_ips_per_device`
* per-ip caps by ip_group:

  * `max_devices_per_ip`
  * `max_parties_per_ip` *(if direct edges enabled)*
* per-entity global caps:

  * `max_devices_per_party`
  * `max_ips_per_party` *(direct or via devices)*
  * `max_devices_per_merchant`
  * `max_ips_per_merchant`

These are hard constraints; violation ⇒ S4 fail (`LINKAGE_RULE_VIOLATION`).

### 10.2 `forbidden_combinations[]`

Explicit prohibitions, each:

* `rule_id`
* `when` predicate (role_id / device_group / ip_group)
* `forbid` predicate (nonnull fields / disallowed group pairings)

Examples (typical v1):

* MERCHANT_TERMINAL devices MUST NOT have `party_id` in device-link roles.
* `SHARED_PUBLIC_WIFI` edges MUST NOT attach to non-`PUBLIC_SHARED` ip_groups.
* `TYPICAL_DEVICE_IP` MUST NOT be `ANONYMIZER_PROXY` (unless you explicitly allow it).

---

## 11) Realism targets (NON-TOY corridors)

Must include corridors such as:

* shared-device fractions by device_group (shared groups > personal groups)
* mean accounts-per-device by group
* mean IPs-per-device by group (aligned with `prior_ip_counts_6A`)
* fraction of devices with at least one `TYPICAL_DEVICE_IP` ≥ 0.99
* fraction of consumer devices with any `RECENT_LOGIN_IP` in `[min,max]` (ensures travel/public/VPN exposure exists)
* enrichment rules:

  * devices with `SHARED_PUBLIC_WIFI` should have higher `deg_party` on average
  * `ANONYMIZER_PROXY` IPs should have much higher `deg_device` than `RESIDENTIAL` (qualitative guardrail; quantitative caps set elsewhere)

---

## 12) Acceptance checklist (MUST)

* **Schema & identity alignment:** generated edge rows must be valid for:

  * `schemas.6A.yaml#/s4/device_links` and `schemas.6A.yaml#/s4/ip_links`.
* **Writer ordering is respected** (deterministic output):

  * device links ordered by `[device_id, party_id, account_id, instrument_id, merchant_id, link_role]`.
  * IP links ordered by `[ip_id, device_id, party_id, merchant_id, link_role]`.
* **FK integrity:** all IDs in link tables resolve to bases; no new IDs introduced.
* **Role correctness:** each `link_role` obeys required/forbidden non-null field rules.
* **Degree caps + forbidden combos enforced**; any violation ⇒ FAIL CLOSED.
* **Non-toy corridors** pass.

---

## 13) Minimal v1 example (shape only)

```yaml
schema_version: 1
config_id: graph_linkage_rules_6A
config_version: v1

bindings:
  device_taxonomy_ref: taxonomy_devices_6A
  ip_taxonomy_ref: taxonomy_ips_6A
  account_taxonomy_ref: taxonomy_account_types_6A
  instrument_taxonomy_ref: taxonomy_instrument_types_6A
  device_counts_ref: prior_device_counts_6A
  ip_counts_ref: prior_ip_counts_6A

device_groups:
  groups:
    - { group_id: CONSUMER_PERSONAL, device_types: [MOBILE_PHONE, WEARABLE], semantics: "Personal devices." }
    - { group_id: CONSUMER_SHARED,  device_types: [DESKTOP, TABLET],        semantics: "Shared household devices." }
    - { group_id: COMPUTER_PORTABLE,device_types: [LAPTOP],                 semantics: "Portable computers." }
    - { group_id: MERCHANT_TERMINAL,device_types: [POS_TERMINAL, ATM, KIOSK],semantics: "Merchant terminals." }

ip_groups:
  groups:
    - { group_id: RESIDENTIAL,       ip_types: [RESIDENTIAL], asn_classes: [CONSUMER_ISP] }
    - { group_id: MOBILE_CARRIER,    ip_types: [MOBILE],      asn_classes: [MNO] }
    - { group_id: PUBLIC_SHARED,     ip_types: [PUBLIC_WIFI, HOTEL_TRAVEL, EDUCATION], asn_classes: [CONSUMER_ISP, ENTERPRISE, PUBLIC_SECTOR] }
    - { group_id: HOSTING_DATACENTRE,ip_types: [DATACENTRE],  asn_classes: [HOSTING_PROVIDER, CDN_EDGE] }
    - { group_id: ANONYMIZER_PROXY,  ip_types: [VPN_PROXY],   asn_classes: [HOSTING_PROVIDER] }

device_link_roles:
  - role_id: PRIMARY_OWNER
    semantic_class: OWNERSHIP
    required_nonnull_fields: [party_id]
    forbidden_nonnull_fields: [account_id, instrument_id, merchant_id]
    description: "Primary owner party."

  - role_id: SECONDARY_USER
    semantic_class: SHARING
    required_nonnull_fields: [party_id]
    forbidden_nonnull_fields: [account_id, instrument_id, merchant_id]
    description: "Secondary user party for shared devices."

  - role_id: MERCHANT_TERMINAL
    semantic_class: OWNERSHIP
    required_nonnull_fields: [merchant_id]
    forbidden_nonnull_fields: [party_id, account_id, instrument_id]
    description: "Merchant-owned terminal device."

  - role_id: ASSOCIATED_ACCOUNT_ACCESS
    semantic_class: ACCESS
    required_nonnull_fields: [account_id]
    forbidden_nonnull_fields: [merchant_id, instrument_id]
    description: "Device can access account."

ip_link_roles:
  - role_id: TYPICAL_DEVICE_IP
    semantic_class: DEVICE_ENDPOINT
    required_nonnull_fields: [device_id]
    forbidden_nonnull_fields: [party_id, merchant_id]
    description: "Typical/default IP for device."

  - role_id: RECENT_LOGIN_IP
    semantic_class: DEVICE_ENDPOINT
    required_nonnull_fields: [device_id]
    forbidden_nonnull_fields: [party_id, merchant_id]
    description: "Recent/secondary IP exposure for device."

  - role_id: SHARED_PUBLIC_WIFI
    semantic_class: SHARED_CONTEXT
    required_nonnull_fields: [device_id]
    forbidden_nonnull_fields: [party_id, merchant_id]
    description: "Device exposure via shared public WiFi/travel/campus."

  - role_id: MERCHANT_ENDPOINT
    semantic_class: MERCHANT_ENDPOINT
    required_nonnull_fields: [merchant_id]
    forbidden_nonnull_fields: [device_id, party_id]
    description: "Merchant endpoint IP(s)."

device_owner_and_sharing:
  owner_kind_by_group:
    CONSUMER_PERSONAL: PARTY
    CONSUMER_SHARED: PARTY
    COMPUTER_PORTABLE: PARTY
    MERCHANT_TERMINAL: MERCHANT
  p_shared_by_group:
    CONSUMER_PERSONAL: 0.03
    COMPUTER_PORTABLE: 0.08
    CONSUMER_SHARED: 0.25
    MERCHANT_TERMINAL: 0.00
  parties_per_shared_device:
    CONSUMER_PERSONAL: { model_id: geometric_capK_v1, min_k: 2, max_k: 4, p: 0.70 }
    COMPUTER_PORTABLE: { model_id: geometric_capK_v1, min_k: 2, max_k: 4, p: 0.65 }
    CONSUMER_SHARED:   { model_id: geometric_capK_v1, min_k: 2, max_k: 6, p: 0.55 }

device_access_edges:
  account_edges_per_device_by_group:
    CONSUMER_PERSONAL: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 5, p_zero: 0.05, mu: 1.6 }
    CONSUMER_SHARED:   { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 8, p_zero: 0.15, mu: 2.2 }
    MERCHANT_TERMINAL: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 2, p_zero: 0.60, mu: 0.6 }
  selection_scope: OWNERS_AND_SHARED_USERS

device_ip_edges:
  edge_roles_by_group:
    CONSUMER_PERSONAL: { TYPICAL_DEVICE_IP: 0.70, RECENT_LOGIN_IP: 0.25, SHARED_PUBLIC_WIFI: 0.05 }
    CONSUMER_SHARED:   { TYPICAL_DEVICE_IP: 0.60, RECENT_LOGIN_IP: 0.30, SHARED_PUBLIC_WIFI: 0.10 }
    MERCHANT_TERMINAL: { TYPICAL_DEVICE_IP: 0.95, RECENT_LOGIN_IP: 0.05 }
  role_to_allowed_ip_groups:
    TYPICAL_DEVICE_IP: [RESIDENTIAL, MOBILE_CARRIER, CORPORATE_NAT]
    RECENT_LOGIN_IP:   [RESIDENTIAL, MOBILE_CARRIER, PUBLIC_SHARED, ANONYMIZER_PROXY]
    SHARED_PUBLIC_WIFI:[PUBLIC_SHARED]

direct_entity_ip_edges:
  direct_party_ip_edges: { enabled: false }
  direct_merchant_ip_edges:
    enabled: true
    ips_per_merchant: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 6, p_zero: 0.30, mu: 1.4 }
    allowed_ip_groups: [CORPORATE_NAT, HOSTING_DATACENTRE]
    role_id: MERCHANT_ENDPOINT

degree_caps:
  per_device_by_group:
    CONSUMER_PERSONAL: { max_parties: 4, max_accounts: 6, max_ips: 30 }
    CONSUMER_SHARED:   { max_parties: 6, max_accounts: 10, max_ips: 40 }
    MERCHANT_TERMINAL: { max_parties: 0, max_accounts: 2, max_ips: 15 }
  per_ip_by_group:
    RESIDENTIAL:       { max_devices: 20 }
    MOBILE_CARRIER:    { max_devices: 20000 }
    PUBLIC_SHARED:     { max_devices: 2000 }
    HOSTING_DATACENTRE:{ max_devices: 100000 }
    ANONYMIZER_PROXY:  { max_devices: 50000 }
  per_entity_global:
    max_devices_per_party: 20
    max_ips_per_party: 80
    max_devices_per_merchant: 40
    max_ips_per_merchant: 200

forbidden_combinations:
  - rule_id: TERM_NO_PARTY_LINKS
    when: { device_group_id: MERCHANT_TERMINAL }
    forbid: { device_link_role: [PRIMARY_OWNER, SECONDARY_USER] }

  - rule_id: PUBLIC_WIFI_ROLE_RESTRICT
    when: { ip_link_role: SHARED_PUBLIC_WIFI }
    forbid: { ip_group_id: [RESIDENTIAL, MOBILE_CARRIER, HOSTING_DATACENTRE, ANONYMIZER_PROXY] }

realism_targets:
  shared_fraction_range_by_group:
    CONSUMER_PERSONAL: { min: 0.00, max: 0.08 }
    CONSUMER_SHARED:   { min: 0.10, max: 0.40 }
  fraction_devices_with_typical_ip_min: 0.99
  fraction_devices_with_any_recent_ip_range: { min: 0.15, max: 0.85 }
  fraction_devices_with_public_wifi_range: { min: 0.03, max: 0.35 }

acceptance_checks:
  enforce_degree_caps: true
  enforce_forbidden_combinations: true
  require_one_primary_owner_for_party_devices: true
  require_one_merchant_terminal_edge_for_terminal_devices: true
```

---
