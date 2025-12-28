# Authoring Guide — `taxonomy.ips` (6A.S4 IP / endpoint classification vocab, v1)

## 0) Purpose

`taxonomy.ips` is the **sealed authority** for the **closed vocabulary** used by **6A.S4** when emitting the IP / endpoint universe (`s4_ip_base_6A`) and IP link tables.

At minimum, 6A.S4 expects the IP taxonomy pack to provide:

* `ip_type` enum (e.g., `RESIDENTIAL`, `MOBILE`, `CORPORATE`, `DATACENTRE`, `VPN_PROXY`, `PUBLIC_WIFI`) 
* `asn_class` / ISP class enum (e.g., `CONSUMER_ISP`, `MNO`, `HOSTING_PROVIDER`, `ENTERPRISE`) 
* optional static risk classes / flags (if modelled) 

This taxonomy is **vocabulary + compatibility**, not a distribution. **Counts/shares** belong in IP priors (e.g., “IPs per party/device”, “degree per IP by (region, ip_type, asn_class)”). 

---

## 1) File identity (binding)

* **Manifest key:** `mlr.6A.taxonomy.ips` 
* **Role in `sealed_inputs_6A`:** `TAXONOMY` (ROW_LEVEL)
* **Path:** `config/layer3/6A/taxonomy/taxonomy.ips.v1.yaml`
* **Format:** YAML (UTF-8, LF)
* **Digest posture:** **token-less**; do **not** embed digests or timestamps in-file. 6A.S0 sealing records exact-bytes `sha256_hex`.

---

## 2) Scope and non-goals

### In scope

* Enumerating `ip_type`, `asn_class`, and optional risk categories used in S4 outputs.
* Declaring **stable semantics** for each class (what it means, what it represents).
* Optional compatibility hints (e.g., which `ip_type` can plausibly co-occur with which `asn_class`) as *constraints*, not probabilities.

### Out of scope (MUST NOT appear here)

* Any probability, share, rate, or mean count (belongs to priors). 
* Any “fraud label” semantics (belongs to 6A.S5 priors).
* Any run-time evidence / RNG logic.

---

## 3) Strict YAML structure (MUST)

### 3.1 Top-level keys (exactly)

Required:

* `schema_version` *(int; MUST be `1`)*
* `taxonomy_id` *(string; MUST be `taxonomy.ips.v1`)*
* `ip_types` *(list of objects)*
* `asn_classes` *(list of objects)*

Optional:

* `risk_tiers` *(list of objects)*
* `risk_flags` *(list of objects)*
* `compatibility_rules` *(list of objects)*
* `notes` *(string)*

Unknown top-level keys: **INVALID**.

### 3.2 ID naming rules (MUST)

All ids (`ip_types[].id`, `asn_classes[].id`, `risk_tiers[].id`, `risk_flags[].id`) MUST:

* be ASCII
* match: `^[A-Z][A-Z0-9_]{1,63}$`

### 3.3 Ordering & formatting (MUST)

* Lists MUST be sorted by `id` ascending:

  * `ip_types`, `asn_classes`, `risk_tiers`, `risk_flags`
* **No YAML anchors/aliases**
* 2-space indentation
* token-less posture (no timestamps, UUIDs, digests)

---

## 4) Object schemas (fields-strict)

### 4.1 `ip_types[]` (required)

Each object MUST contain:

* `id`
* `label`
* `description`

Optional (recommended):

* `is_anonymizing` *(bool; default false)*
* `is_shared_infrastructure` *(bool; default false)*
* `notes` *(string)*

Semantics guidance:

* `ip_type` represents the **usage/infrastructure context** (home broadband vs mobile carrier vs corporate NAT vs datacentre vs anonymizer).

### 4.2 `asn_classes[]` (required)

Each object MUST contain:

* `id`
* `label`
* `description`

Optional:

* `kind` *(enum string; e.g., `CONSUMER_ACCESS`, `MOBILE_ACCESS`, `HOSTING`, `ENTERPRISE`, `PUBLIC_SECTOR`, `CDN_EDGE`)*
* `notes`

Semantics guidance:

* `asn_class` represents **provider category**, not a specific ASN number. The actual ASN identifier (if modelled) is an attribute sampled by priors, not part of the taxonomy. 

### 4.3 `risk_tiers[]` (optional but recommended)

Each object MUST contain:

* `id` *(minimum set recommended: `LOW`, `STANDARD`, `HIGH`)*
* `label`
* `description`

Rule:

* Tiers are **static posture descriptors**, not “fraud labels”.

### 4.4 `risk_flags[]` (optional)

Each object MUST contain:

* `id`
* `label`
* `description`

Rules:

* Flags are **orthogonal annotations** (multiple flags may apply to an IP).
* Flags MUST be interpretable without implying ground-truth wrongdoing (e.g., “known proxy range” is a property, not a verdict). 

### 4.5 `compatibility_rules[]` (optional; constraint-only)

Each rule object MUST contain:

* `id`
* `ip_type` *(one of `ip_types[].id`)*
* `allowed_asn_classes` *(list of `asn_classes[].id`; non-empty)*

Purpose:

* Lets S4 validation fail closed if priors attempt impossible combinations (e.g., `DATACENTRE` with `MNO` if you don’t want that).

---

## 5) Realism requirements (NON-TOY)

Minimum floors (MUST):

* `len(ip_types) >= 8`
* `len(asn_classes) >= 6`

`ip_types` MUST include at least:

* `RESIDENTIAL`
* `MOBILE`
* `CORPORATE`
* `DATACENTRE`
* `PUBLIC_WIFI`
* `VPN_PROXY` *(or separate `VPN` and `PROXY` if you prefer)*
* `EDUCATION` *(campus networks)*
* `HOTEL_TRAVEL` *(travel/hospitality access networks)*

`asn_classes` MUST include at least:

* `CONSUMER_ISP`
* `MNO` *(mobile network operator)*
* `HOSTING_PROVIDER`
* `ENTERPRISE`
* `PUBLIC_SECTOR`
* `CDN_EDGE`

If `risk_tiers` present (recommended):

* MUST include `LOW`, `STANDARD`, `HIGH`

If `risk_flags` present (recommended):

* SHOULD include at least 6, with coverage such as:

  * `KNOWN_PROXY_PROVIDER`
  * `TOR_EXIT_RANGE`
  * `VPN_ENDPOINT_RANGE`
  * `NEWLY_SEEN_RANGE`
  * `HIGH_CHURN_RANGE`
  * `PUBLIC_SHARED_ACCESS`

---

## 6) Authoring procedure (Codex-ready)

1. **Define `ip_types`** with crisp, non-overlapping definitions.
2. **Define `asn_classes`** as provider categories (not specific ASNs).
3. **(Recommended) Define `risk_tiers`** as LOW/STANDARD/HIGH.
4. **(Recommended) Define `risk_flags`** as orthogonal annotations.
5. **(Optional) Add `compatibility_rules`** to fail closed on impossible pairings.
6. **Run acceptance checks** (§8).
7. **Freeze formatting**: sort by id, remove anchors/aliases, ensure token-less posture.

---

## 7) Minimal v1 example (realistic)

```yaml
schema_version: 1
taxonomy_id: taxonomy.ips.v1
notes: >
  IP / endpoint classification taxonomy for 6A.S4. Ids are stable API tokens.

ip_types:
  - id: CORPORATE
    label: Corporate / office
    description: Enterprise networks (office NATs, corporate gateways, managed networks).
  - id: DATACENTRE
    label: Datacentre
    description: Hosting and datacentre infrastructure (VMs, servers, cloud networks).
    is_shared_infrastructure: true
  - id: EDUCATION
    label: Education / campus
    description: University/campus networks with shared access patterns.
    is_shared_infrastructure: true
  - id: HOTEL_TRAVEL
    label: Hotel / travel Wi-Fi
    description: Hospitality/travel access networks with shared churn-heavy usage.
    is_shared_infrastructure: true
  - id: MOBILE
    label: Mobile carrier
    description: Mobile network access (cellular NATs, carrier gateways).
    is_shared_infrastructure: true
  - id: PUBLIC_WIFI
    label: Public Wi-Fi
    description: Public/shared Wi-Fi access points (cafes, transport hubs).
    is_shared_infrastructure: true
  - id: RESIDENTIAL
    label: Residential broadband
    description: Home broadband access networks (consumer ISP).
  - id: VPN_PROXY
    label: VPN / proxy
    description: VPN endpoints and proxy infrastructure used to mask origin.
    is_anonymizing: true
    is_shared_infrastructure: true

asn_classes:
  - id: CDN_EDGE
    kind: CDN_EDGE
    label: CDN edge
    description: Content delivery edge providers / distributed edge infrastructure.
  - id: CONSUMER_ISP
    kind: CONSUMER_ACCESS
    label: Consumer ISP
    description: Consumer broadband and access ISPs.
  - id: ENTERPRISE
    kind: ENTERPRISE
    label: Enterprise
    description: Enterprise or corporate ASN owners/providers.
  - id: HOSTING_PROVIDER
    kind: HOSTING
    label: Hosting provider
    description: Datacentres and hosting/cloud providers.
  - id: MNO
    kind: MOBILE_ACCESS
    label: Mobile network operator
    description: Mobile carrier network providers.
  - id: PUBLIC_SECTOR
    kind: PUBLIC_SECTOR
    label: Public sector
    description: Government/public-sector networks and providers.

risk_tiers:
  - id: HIGH
    label: High risk
    description: Higher static risk posture (shared/anonymizing/churn-heavy plausible).
  - id: LOW
    label: Low risk
    description: Lower static risk posture (stable, managed, low churn plausible).
  - id: STANDARD
    label: Standard risk
    description: Typical baseline posture.

risk_flags:
  - id: HIGH_CHURN_RANGE
    label: High churn range
    description: Ranges with high observed turnover / dynamic allocation patterns.
  - id: KNOWN_PROXY_PROVIDER
    label: Known proxy provider
    description: IP range known to be operated by a proxy/anonymizer provider.
  - id: NEWLY_SEEN_RANGE
    label: Newly seen
    description: Range is newly introduced in the world’s observed IP universe.
  - id: PUBLIC_SHARED_ACCESS
    label: Public shared access
    description: Shared-access network context (public Wi-Fi, hotel, campus).
  - id: TOR_EXIT_RANGE
    label: Tor exit range
    description: Range associated with Tor exit nodes.
  - id: VPN_ENDPOINT_RANGE
    label: VPN endpoint range
    description: Range associated with VPN endpoints.

compatibility_rules:
  - id: RULE_RESIDENTIAL
    ip_type: RESIDENTIAL
    allowed_asn_classes: [CONSUMER_ISP]
  - id: RULE_MOBILE
    ip_type: MOBILE
    allowed_asn_classes: [MNO]
  - id: RULE_DATACENTRE
    ip_type: DATACENTRE
    allowed_asn_classes: [HOSTING_PROVIDER, CDN_EDGE]
  - id: RULE_CORPORATE
    ip_type: CORPORATE
    allowed_asn_classes: [ENTERPRISE]
  - id: RULE_PUBLIC_SHARED
    ip_type: PUBLIC_WIFI
    allowed_asn_classes: [CONSUMER_ISP, PUBLIC_SECTOR, ENTERPRISE]
  - id: RULE_ANONYMIZER
    ip_type: VPN_PROXY
    allowed_asn_classes: [HOSTING_PROVIDER]
```

---

## 8) Acceptance checklist (MUST)

### 8.1 Structural checks

* YAML parses cleanly.
* `schema_version == 1`
* `taxonomy_id == taxonomy.ips.v1`
* Unknown keys absent (top-level and nested objects).
* All ids match `^[A-Z][A-Z0-9_]{1,63}$`.
* Lists sorted by `id` ascending.
* No YAML anchors/aliases.
* No timestamps / UUIDs / in-file digests.

### 8.2 Referential integrity

* `compatibility_rules[].ip_type` exists in `ip_types`.
* `compatibility_rules[].allowed_asn_classes` ⊆ `asn_classes[].id` and non-empty.

### 8.3 Realism floors

* `ip_types >= 8` and required types present.
* `asn_classes >= 6` and required classes present.
* If `risk_tiers` present: includes LOW/STANDARD/HIGH.

---

## 9) Change control (MUST)

* All ids are **stable API tokens**:

  * never repurpose an existing `ip_type` / `asn_class` / `risk_tier` / `risk_flag`
  * prefer additive changes
* Breaking changes require bumping the filename version (`taxonomy.ips.v2.yaml`) and updating:

  * IP priors and any validation checks that reference ids
  * 6A.S4 validation expectations (missing-code is a hard fail) 
