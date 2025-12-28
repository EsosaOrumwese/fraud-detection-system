# Authoring Guide — `taxonomy.party` (6A.S1 party types + segment taxonomy, v1)

## 0) Purpose

`taxonomy.party` is the **sealed authority** for the **closed vocabulary** that 6A uses to describe customer-side parties (retail + business + “other institutions”) and their **segment codes**.

It defines:

* **`party_type`**: coarse type (e.g., `RETAIL`, `BUSINESS`, `OTHER`)
* **`segment_id`**: stable leaf segment identifiers used as conditioning keys by 6A priors
* optional hierarchy (`segment_families`, `segment_groups`) and behavioural **tags** to support realistic heterogeneity

This artefact MUST be:

* **token-less** (no timestamps, no in-file digests)
* **deterministic / RNG-free**
* **fields-strict** (unknown keys invalid)
* **non-toy** (enough segmentation for realistic downstream priors)

---

## 1) File identity (binding)

* **Artefact / dictionary id:** `taxonomy.party`
* **Manifest key (used in 6A contracts):** `mlr.6A.taxonomy.party`
* **Role in `sealed_inputs_6A`:** `TAXONOMY`
* **Path:** `config/layer3/6A/taxonomy/taxonomy.party.v1.yaml`
* **Format:** YAML (UTF-8, LF)
* **Schema anchor:** `schemas.6A.yaml#/taxonomy/party_taxonomy_6A` *(may be permissive or stub; this guide pins the real contract)*
* **Digest posture:** token-less; **do not embed digest fields**. 6A.S0 seals by exact bytes (`sha256_hex`) and all consumers select by **S0-sealed `path + sha256`**, never “latest”.

---

## 2) Scope and non-goals

### In scope

* Defining **party types** and **segment ids** as a stable “API”.
* Providing optional hierarchy + tags to make downstream priors realistic without inventing new data sources.

### Out of scope (MUST NOT appear here)

* Population counts or segment shares (those are `prior.population` / `prior.segmentation`)
* Product mixes, instrument mixes, device/IP priors (separate prior packs)
* Fraud labels/roles (S5 priors; do not embed “FRAUDSTER” semantics here)

---

## 3) Consumers and authority boundaries

### Consumers

* **Direct:** `6A.S1` (party universe) uses `party_type`/`segment_id` vocab.
* **Indirect:** all later 6A priors that condition on `segment_id` (accounts, instruments, devices/IPs, and S5 fraud posture).

### Authority boundaries (MUST)

* `segment_id` meanings are **owned** here. Priors may reference segment ids but MUST NOT redefine them.
* Segment ids MUST be stable across versions; deprecation is allowed but **repurposing is forbidden**.

---

## 4) Strict YAML structure (MUST)

### 4.1 Top-level keys (exactly)

Required:

* `schema_version` *(int; MUST be `1`)*
* `taxonomy_id` *(string; MUST be `taxonomy.party.v1`)*
* `party_types` *(list of objects)*
* `segments` *(list of objects)*

Optional:

* `segment_families` *(list of objects)*
* `segment_groups` *(list of objects)*
* `tag_vocabulary` *(list of strings)*
* `notes` *(string)*

Unknown top-level keys: **INVALID**.

### 4.2 ID naming rules (MUST)

All ids (`party_type.id`, `segment.id`, family/group ids, tags) MUST:

* be ASCII
* match: `^[A-Z][A-Z0-9_]{1,63}$`

### 4.3 Ordering and formatting (MUST)

* Lists MUST be sorted by `id` ascending:

  * `party_types`, `segment_families`, `segment_groups`, `segments`, `tag_vocabulary`
* **No YAML anchors/aliases** (they can hide duplicate keys and break digest stability)
* 2-space indentation

---

## 5) Object schemas (fields-strict)

### 5.1 `party_types[]` (required)

Each object MUST contain:

* `id`
* `label`
* `description`

Optional:

* `is_business` *(bool)*
* `notes` *(string)*

### 5.2 `segment_families[]` (optional)

Each object MUST contain:

* `id`
* `party_type` *(must match a `party_types[].id`)*
* `label`
* `description`

### 5.3 `segment_groups[]` (optional)

Each object MUST contain:

* `id`
* `family_id` *(must match a `segment_families[].id`)*
* `label`
* `description`

Optional (recommended for realism/clarity):

* `dimension` *(enum; e.g., `LIFESTAGE`, `AFFLUENCE`, `BUSINESS_SIZE`, `INSTITUTION_TYPE`)*

### 5.4 `segments[]` (required)

Each object MUST contain:

* `id`
* `party_type` *(must match `party_types[].id`)*
* `label`
* `description`

Optional:

* `family_id` *(if `segment_families` present)*
* `group_id` *(if `segment_groups` present)*
* `tags` *(list; each tag must be in `tag_vocabulary`)*
* `deprecated` *(bool; default false)*
* `replacement_id` *(required if `deprecated:true`; must reference an existing non-deprecated segment)*

Rules:

* A `segment_id` MUST belong to **exactly one** `party_type`.
* If `family_id` is present, it MUST belong to the same `party_type`.
* If `group_id` is present, its `family_id` MUST equal the segment’s `family_id`.

---

## 6) Realism requirements (NON-TOY)

Minimum realism floors (MUST):

* Total segments `len(segments)` **≥ 16**
* `RETAIL` segments **≥ 8**
* `BUSINESS` segments **≥ 6**
* `OTHER` segments **≥ 2**

Recommended realism (SHOULD):

* Retail segments cover both:

  * **lifecycle** (e.g., student, early-career, family, mature, retired)
  * **affluence / constraint** (value, mass-market, affluent)
* Business segments cover:

  * **size/complexity** (sole trader, micro, SME, mid-market, corporate)
  * at least one segment reflecting **digital/online intensity** (e.g., e-commerce–heavy)
* “Other” covers at least:

  * **nonprofit**
  * **public sector**

Tag realism (if tags used):

* `tag_vocabulary` SHOULD have **≥ 12** tags
* tags SHOULD describe tendencies, not outcomes (e.g., `DIGITAL_HEAVY`, not `FRAUDSTER`)

---

## 7) Authoring procedure (Codex-ready)

1. **Define party types**

   * Use `BUSINESS`, `OTHER`, `RETAIL` (v1 minimum).

2. **Define hierarchy (recommended)**

   * `segment_families`: typically 1:1 with party types in v1.
   * `segment_groups`: define groups with a clear `dimension`:

     * `RETAIL_LIFESTAGE`, `RETAIL_AFFLUENCE`
     * `BUSINESS_SIZE`, `BUSINESS_OPERATING_MODE`
     * `OTHER_INSTITUTION`

3. **Define tag vocabulary (optional but recommended)**

   * Create ~12–20 tags that priors can use as hints.

4. **Draft segments**

   * Create segment ids as stable API tokens.
   * Keep descriptions short, specific, and non-overlapping.
   * Ensure floors in Section 6.

5. **Run acceptance checks (Section 9)**

   * Fail closed if any rule is violated.

6. **Freeze formatting**

   * Sort lists by id, remove anchors/aliases, ensure token-less posture.

---

## 8) Minimal v1 example (realistic)

```yaml
schema_version: 1
taxonomy_id: taxonomy.party.v1
notes: >
  Party type + segment catalog for 6A. Segment ids are stable API tokens.

party_types:
  - id: BUSINESS
    is_business: true
    label: Business customer
    description: Registered businesses and sole traders acting primarily for commercial use.
  - id: OTHER
    is_business: false
    label: Other institution
    description: Public bodies, charities, and other non-standard institutional customers.
  - id: RETAIL
    is_business: false
    label: Retail consumer
    description: Individuals acting primarily for personal use.

segment_families:
  - id: BUSINESS
    party_type: BUSINESS
    label: Business segmentation
    description: Business segments by size/complexity and operating mode.
  - id: OTHER
    party_type: OTHER
    label: Institutional segmentation
    description: Non-consumer institutions.
  - id: RETAIL
    party_type: RETAIL
    label: Retail segmentation
    description: Retail segments by lifecycle and affluence/constraint.

segment_groups:
  - id: BUSINESS_OPERATING_MODE
    family_id: BUSINESS
    dimension: BUSINESS_OPERATING_MODE
    label: Operating mode
    description: Online/omnichannel vs in-person intensity.
  - id: BUSINESS_SIZE
    family_id: BUSINESS
    dimension: BUSINESS_SIZE
    label: Business size
    description: Segments primarily defined by size and complexity.
  - id: OTHER_INSTITUTION
    family_id: OTHER
    dimension: INSTITUTION_TYPE
    label: Institution type
    description: Institutional segments.
  - id: RETAIL_AFFLUENCE
    family_id: RETAIL
    dimension: AFFLUENCE
    label: Retail affluence / constraint
    description: Segments defined by affluence and financial constraint.
  - id: RETAIL_LIFESTAGE
    family_id: RETAIL
    dimension: LIFESTAGE
    label: Retail lifecycle stage
    description: Segments defined by lifecycle stage.

tag_vocabulary:
  - CASH_HEAVY
  - CREDIT_AVOIDER
  - CREDIT_SEEKER
  - CROSS_BORDER_HEAVY
  - DIGITAL_HEAVY
  - ECOM_FOCUSED
  - INCOME_VOLATILE
  - INTERNATIONAL_CLIENTS
  - LONG_TENURE
  - NEW_TO_BANK
  - POS_FOCUSED
  - SAVINGS_ORIENTED
  - SEASONAL
  - TRAVEL_HEAVY

segments:
  # BUSINESS (>= 6)
  - id: BUSINESS_CORPORATE
    party_type: BUSINESS
    family_id: BUSINESS
    group_id: BUSINESS_SIZE
    label: Corporate
    description: Large enterprises with multiple products, higher volumes, and complex operations.
    tags: [INTERNATIONAL_CLIENTS, CROSS_BORDER_HEAVY]
  - id: BUSINESS_ECOM_NATIVE
    party_type: BUSINESS
    family_id: BUSINESS
    group_id: BUSINESS_OPERATING_MODE
    label: E-commerce native
    description: Businesses with predominantly online sales and higher digital channel intensity.
    tags: [ECOM_FOCUSED, DIGITAL_HEAVY, INTERNATIONAL_CLIENTS]
  - id: BUSINESS_MID_MARKET
    party_type: BUSINESS
    family_id: BUSINESS
    group_id: BUSINESS_SIZE
    label: Mid-market
    description: Established businesses with moderate complexity and multi-product usage.
    tags: [POS_FOCUSED]
  - id: BUSINESS_MICRO
    party_type: BUSINESS
    family_id: BUSINESS
    group_id: BUSINESS_SIZE
    label: Micro business
    description: Very small businesses with limited product usage and variable cashflow.
    tags: [INCOME_VOLATILE]
  - id: BUSINESS_SME
    party_type: BUSINESS
    family_id: BUSINESS
    group_id: BUSINESS_SIZE
    label: SME
    description: Small/medium businesses with standard banking needs and moderate volumes.
    tags: [POS_FOCUSED]
  - id: BUSINESS_SOLE_TRADER
    party_type: BUSINESS
    family_id: BUSINESS
    group_id: BUSINESS_SIZE
    label: Sole trader
    description: Self-employed individuals operating a small business, often with simple product use.
    tags: [DIGITAL_HEAVY]

  # OTHER (>= 2)
  - id: OTHER_NONPROFIT
    party_type: OTHER
    family_id: OTHER
    group_id: OTHER_INSTITUTION
    label: Non-profit
    description: Charities and non-profits with donation/expense patterns and governance constraints.
    tags: [SEASONAL]
  - id: OTHER_PUBLIC_SECTOR
    party_type: OTHER
    family_id: OTHER
    group_id: OTHER_INSTITUTION
    label: Public sector
    description: Public bodies and agencies with stable funding and administrative payment flows.
    tags: [LONG_TENURE]

  # RETAIL (>= 8)
  - id: RETAIL_AFFLUENT
    party_type: RETAIL
    family_id: RETAIL
    group_id: RETAIL_AFFLUENCE
    label: Affluent
    description: Higher disposable income customers with travel and cross-border propensity.
    tags: [TRAVEL_HEAVY, CROSS_BORDER_HEAVY]
  - id: RETAIL_EARLY_CAREER
    party_type: RETAIL
    family_id: RETAIL
    group_id: RETAIL_LIFESTAGE
    label: Early career
    description: Recently employed customers with growing income and increasing product eligibility.
    tags: [DIGITAL_HEAVY, CREDIT_SEEKER]
  - id: RETAIL_FAMILY
    party_type: RETAIL
    family_id: RETAIL
    group_id: RETAIL_LIFESTAGE
    label: Family household
    description: Customers with dependants and recurring expenses; stability varies by income.
    tags: [POS_FOCUSED]
  - id: RETAIL_MASS_MARKET
    party_type: RETAIL
    family_id: RETAIL
    group_id: RETAIL_AFFLUENCE
    label: Mass market
    description: Broad mainstream retail customers with typical product use and balanced channels.
    tags: [POS_FOCUSED]
  - id: RETAIL_MATURE
    party_type: RETAIL
    family_id: RETAIL
    group_id: RETAIL_LIFESTAGE
    label: Mature working
    description: Established customers with stable income and longer tenure; broader product usage.
    tags: [LONG_TENURE, SAVINGS_ORIENTED]
  - id: RETAIL_RETIRED
    party_type: RETAIL
    family_id: RETAIL
    group_id: RETAIL_LIFESTAGE
    label: Retired
    description: Post-employment customers with stable income sources and different spend cadence.
    tags: [CREDIT_AVOIDER, LONG_TENURE]
  - id: RETAIL_STUDENT
    party_type: RETAIL
    family_id: RETAIL
    group_id: RETAIL_LIFESTAGE
    label: Student
    description: Education-linked customers with lower income and high digital channel usage.
    tags: [DIGITAL_HEAVY, NEW_TO_BANK]
  - id: RETAIL_VALUE
    party_type: RETAIL
    family_id: RETAIL
    group_id: RETAIL_AFFLUENCE
    label: Value / budget
    description: Lower disposable income customers with stronger budget constraints and higher cash usage.
    tags: [CASH_HEAVY, CREDIT_AVOIDER]
```

---

## 9) Acceptance checklist (MUST)

### 9.1 Structural checks

* YAML parses cleanly.
* `schema_version == 1`
* `taxonomy_id == taxonomy.party.v1`
* Unknown keys absent (top-level and nested objects).
* All ids match `^[A-Z][A-Z0-9_]{1,63}$`.
* Uniqueness:

  * `party_types[].id` unique
  * `segments[].id` unique
  * family/group ids unique (if present)
* Referential integrity:

  * every `segments[].party_type` exists
  * if `family_id` present: family exists and matches party_type
  * if `group_id` present: group exists and matches family
  * if tags present: tags ⊆ `tag_vocabulary`

### 9.2 Realism floors

* `len(segments) >= 16`
* retail segments >= 8
* business segments >= 6
* other segments >= 2

### 9.3 Stability / digest posture

* No timestamps (`generated_at`, `created_at`), UUIDs, or embedded digests.
* Lists sorted by id ascending.
* No YAML anchors/aliases.

---

## 10) Change control (MUST)

* Segment ids are **API tokens**:

  * Never repurpose an existing `segment_id`.
  * Use `deprecated:true` + `replacement_id` for migrations.
* Any change that removes or renames a `segment_id` is **breaking** and MUST:

  * update all 6A prior packs that reference segments,
  * update `SEGMENT_CHECKLIST_6A` if it names segments,
  * bump filename version (`taxonomy.party.v2.yaml`).
