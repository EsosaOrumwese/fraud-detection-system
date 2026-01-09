# 6A.S2 — Accounts & product holdings (Layer-3 / Segment 6A)

## 1. Purpose & scope *(Binding)*

6A.S2 is the **account and product realisation state** for Layer-3 / Segment 6A. Its job is to take the **party universe** produced by S1 and turn it into a **closed-world account universe** for each `(manifest_fingerprint, seed)`. That means S2 decides:

* **Which accounts/products exist** (current accounts, savings, cards, loans, merchant settlement accounts, wallets, etc.).
* **Who owns them** (which parties and, where applicable, which merchants).
* **What static attributes** each account has at initialisation (type, currency, product family, simple flags).

Concretely, S2 must:

* Construct `s2_account_base_6A`: the authoritative list of accounts in the world for 6A/6B, including:

  * a stable `account_id` unique within `(manifest_fingerprint, seed)`,
  * owner references (usually `party_id`, optionally `merchant_id` for merchant accounts),
  * account/product type (e.g. current, savings, credit card, loan, merchant settlement),
  * static attributes such as currency, region, risk tier and basic eligibility flags.
* Construct a **product-holdings view** per party (and optionally per merchant), e.g. `s2_party_product_holdings_6A`, that summarises “this party holds X current accounts, Y cards, Z loans…”, strictly derived from the account base and the S1 party base.

Within Layer-3, S2 is the **sole authority** on:

* **Account existence**: how many accounts/products exist per world+seed, per region/segment/type.
* **Ownership topology**: which party (and merchant, if applicable) owns which account at initialisation.
* **Static account-level attributes**: the attributes that characterise an account before any transactional behaviour or balances are simulated.

The scope of S2 is deliberately constrained:

* S2 **does not**:

  * create or modify parties (that is 6A.S1’s responsibility),
  * create instruments (card PANs, tokens), devices, IPs, or graph edges (those belong to later 6A states),
  * define balances, transaction histories, flows, campaigns, or fraud behaviour (all of that is owned by 6B and downstream states),
  * interact with individual arrivals from 5B (it may only use coarse context, if configured, via sealed priors).

* S2 **must not** alter or reinterpret upstream Layer-1 / Layer-2 artefacts:

  * merchants, sites, zones, virtual edges, routing, time, intensities, and arrivals remain under 1A–3B and 5A–5B.

Within 6A, S2 sits **downstream of S0 and S1**:

* It runs only when S0 has sealed the input universe and S1 has successfully created the party base for the same `(manifest_fingerprint, seed)`.
* It uses 6A **product-mix priors**, **account taxonomies**, and any configured linkage rules to realise per-cell account counts and then allocate those accounts to parties/merchants in a way that is consistent with S1’s segmentation and the upstream world.

All later 6A states (instruments, devices/IPs, fraud posture) and 6B’s flow/fraud logic must treat S2’s account base as **read-only ground truth** for “what accounts/products exist and who owns them” in the synthetic bank.

---

## 2. Preconditions, upstream gates & sealed inputs *(Binding)*

6A.S2 only runs where **Layer-1, Layer-2, 6A.S0 and 6A.S1 are already sealed** for the relevant world and seed. This section fixes those preconditions and the **minimum sealed inputs** S2 expects to see.

---

### 2.1 World-level preconditions (Layer-1 & Layer-2)

For a given `manifest_fingerprint` that S2 will serve, the engine MUST already have:

* Successfully run all required upstream segments:

  * Layer-1: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.
  * Layer-2: `5A`, `5B`.

* Successfully verified their HashGates (validation bundles + PASS flags), as recorded by 6A.S0.

S2 **does not** re-implement upstream HashGate logic. It **trusts S0’s view** via `s0_gate_receipt_6A`:

* For this `manifest_fingerprint`, every required segment in `upstream_gates` MUST have:

  ```text
  gate_status == "PASS"
  ```

If any required segment has `gate_status ∈ {"FAIL","MISSING"}`, S2 MUST treat the world as **not eligible** and fail fast with a gate error (e.g. `6A.S2.S0_OR_S1_GATE_FAILED`).

---

### 2.2 6A.S0 preconditions (gate & sealed inputs)

S2 is not allowed to run unless the **6A.S0 gate is fully satisfied**.

For the target `manifest_fingerprint`, S2 MUST:

1. **Validate S0 artefacts**

   * Confirm `s0_gate_receipt_6A` and `sealed_inputs_6A` exist under the correct `fingerprint={manifest_fingerprint}` partitions.
   * Validate both against their schema anchors in `schemas.layer3.yaml`:

     * `#/gate/6A/s0_gate_receipt_6A`,
     * `#/gate/6A/sealed_inputs_6A`.

2. **Verify sealed-inputs digest**

   * Recompute `sealed_inputs_digest_6A` from `sealed_inputs_6A` using the canonical row encoding and sort order defined in S0.
   * Require:

     ```text
     recomputed_digest == s0_gate_receipt_6A.sealed_inputs_digest_6A
     ```

3. **Check S0 run-report status**

   * The latest 6A.S0 run-report for this `manifest_fingerprint` MUST have:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

If any of these checks fails, S2 MUST NOT attempt to read priors or generate any accounts for that world+seed, and MUST fail with a gate/inputs error.

---

### 2.3 6A.S1 preconditions (party base gate)

S2 sits directly downstream of S1 in 6A. For each `(manifest_fingerprint, seed)` S2 will process, it MUST ensure that 6A.S1 is PASS and that the party base is available and valid.

For the target `(mf, seed)`:

1. **S1 run-report**

   * Locate the latest 6A.S1 run-report entry for that `(mf, seed)`.
   * Require:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

2. **Party base dataset**

   * Locate `s1_party_base_6A` via `dataset_dictionary.layer3.6A.yaml` and `artefact_registry_6A.yaml`.
   * Ensure the partition for `(seed={seed}, fingerprint={mf})`:

     * exists,
     * validates against `schemas.6A.yaml#/s1/party_base`,
     * has `COUNT(*) == total_parties` reported in the S1 run-report.

If S1 is missing or not PASS for the `(mf, seed)` S2 intends to process, S2 MUST fail with `6A.S2.S0_OR_S1_GATE_FAILED` and MUST NOT produce any accounts for that world+seed.

---

### 2.4 Required sealed inputs for S2

S2 may only read artefacts that appear in `sealed_inputs_6A` (for its `manifest_fingerprint`) and have:

* `status ∈ {"REQUIRED","OPTIONAL"}`, and
* `read_scope = "ROW_LEVEL"` for data-level logic, or
* `read_scope = "METADATA_ONLY"` where only presence/shape is consulted.

Among those, S2 requires at minimum:

#### 2.4.1 Product mix priors & account-allocation priors

Artefacts with `role = "PRODUCT_PRIOR"` or similar, e.g.:

* **Product mix priors**:

  * expected number of accounts/products per cell, where a cell might be `(region, party_type, segment)` or a richer combination,
  * expected composition across account types per cell (e.g. share of current vs savings vs credit card vs loan).

* **Account-per-party distributions**:

  * distributions for how many accounts of each type a party in a given cell is likely to hold (e.g. 0–2 current accounts, 0–3 cards, etc.),
  * any zero-inflation or bounds (min/max accounts per party).

These priors must be present as rows in one or more prior tables, and must be marked as `status="REQUIRED"` and `read_scope="ROW_LEVEL"` in `sealed_inputs_6A`.

#### 2.4.2 Account & product taxonomies

Artefacts with `role = "TAXONOMY"` that define the allowed account/product codes, including:

* account types (e.g. `CURRENT_ACCOUNT`, `SAVINGS_ACCOUNT`, `CREDIT_CARD`, `LOAN`, `MERCHANT_SETTLEMENT`),
* product families (e.g. basic vs premium, secured vs unsecured),
* any enumeration tables that S2 needs to populate `account_type`, `product_family`, `currency_policy`, etc.

These taxonomies may be `REQUIRED` or `OPTIONAL`, but:

* any taxonomy that is referenced by schema enums for S2 outputs MUST be present and valid, otherwise S2 MUST fail.

#### 2.4.3 Linkage rules & constraints

Artefacts (often priors or config packs) describing **which parties are allowed to own which products**, with `role` values like:

* `PRODUCT_LINKAGE_RULES` (contract id: `product_linkage_rules_6A`),
* `PRODUCT_ELIGIBILITY_CONFIG` (contract id: `product_eligibility_config_6A`),
* or a specific `PRODUCT_PRIOR` with a subtype.

Examples:

* rules that say:

  * retail parties cannot own merchant settlement accounts,
  * SME segments may own both personal and business accounts,
  * certain products are only available in certain regions.

These artefacts MUST be present (or explicitly marked `OPTIONAL` with clear semantics) if S2 is expected to enforce such rules.

#### 2.4.4 6A contracts (metadata-only)

Entries in `sealed_inputs_6A` with `role="CONTRACT"` and `read_scope="METADATA_ONLY"` for:

* `schemas.layer3.yaml`,
* `schemas.6A.yaml`,
* `dataset_dictionary.layer3.6A.yaml`,
* `artefact_registry_6A.yaml`.

S2 uses these to:

* validate that its outputs are declared correctly, and
* resolve dataset IDs, paths, and schema refs.

S2 MUST NOT attempt to modify these contracts.

#### 2.4.5 Optional upstream context (if used)

Depending on design, S2 MAY also consume contextual upstream artefacts, for example:

* **Region/world surfaces** (`role="UPSTREAM_EGRESS"` or `POPULATION_PRIOR`):

  * country/region tables,
  * card penetration or banking penetration indicators,
  * GDP or income surfaces.

* **Scenario/volume hints** (`role="SCENARIO_CONFIG"` or `UPSTREAM_EGRESS`):

  * coarse per-region or per-segment traffic/spend expectations from 5A/5B, used to adjust account densities.

If S2 uses such context:

* it must be listed in `sealed_inputs_6A` with appropriate `role` and `read_scope`,
* and its absence must have a well-defined meaning (e.g. “use default, volume-agnostic product mix”).

---

### 2.5 Axes of operation: world & seed

S2’s natural domain is the pair `(manifest_fingerprint, seed)`:

* `manifest_fingerprint` identifies the upstream world and sealed input universe (as in S0/S1).
* `seed` identifies a specific population realisation within that world.

Preconditions per axis:

* For each world `mf`:

  * S0 must be PASS,
  * all upstream HashGates must be PASS (via S0),
  * S2 must only consider sealed inputs and priors for that `mf`.

* For each seed within `mf`:

  * S1 must be PASS for `(mf, seed)` and `s1_party_base_6A` must exist and be valid,
  * S2 may then generate accounts for exactly that party base and seed.

Scenario identity (`scenario_id`) is not a direct axis for S2:

* S2 creates a single account universe per `(mf, seed)`, shared across scenarios;
* if scenario-dependent accounts are ever introduced, that will be a breaking change and must be versioned under change control.

---

### 2.6 Out-of-scope inputs

S2 explicitly **must not depend on**:

* individual arrivals from `arrival_events_5B` (no per-arrival logic here),
* balances, flows, labels, or any 6B outputs,
* non-catalogued data sources (no ad-hoc files, network calls, or environment variables for semantics),
* artefacts not present in `sealed_inputs_6A` for this `manifest_fingerprint`,
* artefacts present but marked with `read_scope="METADATA_ONLY"` for row-level logic.

Any implementation that uses such inputs is out of spec, even if it appears to work operationally.

---

## 3. Inputs & authority boundaries *(Binding)*

This section pins down, for **6A.S2**, exactly:

* **what it is allowed to read**, and
* **who is allowed to define what** (L1, L2, S0, S1, S2),

so that downstream states (S3–S5, 6B) can trust that S2 never redefines upstream responsibilities or introduces “mystery” inputs.

S2 **may only** consume artefacts listed in `sealed_inputs_6A` for its `manifest_fingerprint`, plus `s1_party_base_6A`, and must respect each artefact’s `role` and `read_scope`.

---

### 3.1 Logical inputs S2 is allowed to use

Subject to the preconditions in §2 and `sealed_inputs_6A`, S2’s inputs fall into four groups:

#### 3.1.1 S0 / S1 control-plane inputs

These are *mandatory* control-plane inputs and must be treated as read-only:

* **From 6A.S0:**

  * `s0_gate_receipt_6A`

    * world & parameter identity (`manifest_fingerprint`, `parameter_hash`),
    * upstream gate statuses (`upstream_gates`),
    * 6A contract/priors summary,
    * `sealed_inputs_digest_6A`.

  * `sealed_inputs_6A`

    * enumerates all artefacts 6A may depend on, with `role`, `status`, `read_scope`, `schema_ref`, `path_template`, `partition_keys`, `sha256_hex`.

* **From 6A.S1:**

  * `s1_party_base_6A`

    * the authoritative party universe for `(manifest_fingerprint, seed)`:
      `party_id`, party type, segment, home geo, static attributes.

S2 MUST:

* trust S0’s view of upstream segments and the 6A input universe,
* treat `s1_party_base_6A` as read-only ground truth for **who exists** and how they are segmented.

#### 3.1.2 6A priors & product/account taxonomies (ROW_LEVEL)

From `sealed_inputs_6A` with `status ∈ {REQUIRED, OPTIONAL}` and `read_scope = "ROW_LEVEL"`:

* **Product mix priors** (`role="PRODUCT_PRIOR"` or equivalent):

  * expected numbers of accounts/products per *population cell* (e.g. `(region, party_type, segment)` or `(region, segment, party_risk_tier)`),
  * expected mix of account types within each cell (e.g. currents vs savings vs cards vs loans).

* **Account-per-party priors**:

  * discrete distributions for “how many accounts of type X does a party in cell c tend to have”
    (zero-inflated, bounded, or otherwise, per design).

* **Account & product taxonomies** (`role="TAXONOMY"`):

  * account types (`account_type`),
  * product families / brands (`product_family`),
  * any enums used in S2 outputs (e.g. `account_risk_tier`, `account_channel_profile`).

* **Linkage / eligibility rules** (`role` e.g. `"PRODUCT_LINKAGE_RULES"` / `"PRODUCT_ELIGIBILITY_CONFIG"`; contract ids: `product_linkage_rules_6A`, `product_eligibility_config_6A`):

  * constraints such as:

    * retail parties cannot own merchant settlement accounts,
    * some products only available in certain regions,
    * SME / corporate-only products,
    * optional caps (e.g. max cards per party in some segments).

S2 uses this group to compute:

* target account counts per cell & type, and
* how those accounts can legally be attached to parties and merchants.

#### 3.1.3 Optional upstream context (ROW_LEVEL or METADATA_ONLY)

Depending on your final design, S2 MAY also draw on contextual surfaces, **if and only if** they are present in `sealed_inputs_6A`:

* **World/geo context** (`role="UPSTREAM_EGRESS"` or `POPULATION_PRIOR`):

  * country/region master tables (ISO codes, region groupings),
  * socio-economic surfaces (e.g. income buckets, card penetration indicators by country).

* **Scenario / volume hints** (`role="SCENARIO_CONFIG"` or `UPSTREAM_EGRESS`):

  * coarse per-region / per-segment / per-merchant expected activity from 5A/5B, used to bias product mix (e.g. more credit cards where spend is card-heavy).

Usage rules:

* If `read_scope="ROW_LEVEL"`, S2 may read rows as inputs to its **account planning** (e.g. to scale account counts).
* If `read_scope="METADATA_ONLY"`, S2 may *only* test presence/version/digest (e.g. “volume-aware mode is enabled”) and must not read rows.

These inputs are **context**, not primary authority: they may influence scale but do not override priors or define account identity.

#### 3.1.4 6A contracts (METADATA_ONLY)

From `sealed_inputs_6A` with `role="CONTRACT"` and `read_scope="METADATA_ONLY"`:

* `schemas.layer3.yaml`
* `schemas.6A.yaml`
* `dataset_dictionary.layer3.6A.yaml`
* `artefact_registry_6A.yaml`

S2 must use these to:

* resolve dataset IDs, schema refs, and paths for S2 outputs,
* confirm that its outputs are declared and shaped correctly.

S2 MUST NOT attempt to change these contracts.

---

### 3.2 Upstream authority boundaries (L1 & L2)

S2 is layered on top of a sealed world from Layer-1 and Layer-2. The boundaries below are **binding**.

#### 3.2.1 Merchant, site, geo & time (1A–2A)

* **Authority:** 1A/1B/2A

  * 1A owns merchants and outlet catalogue.
  * 1B owns site locations.
  * 2A owns civil time (`site_timezones`, `tz_timetable_cache`).

S2 **must not**:

* create or delete merchants,
* modify merchant attributes (MCC, channel, home country, etc.),
* change site geometry or site counts,
* assign or override time zones.

If S2 needs merchant-level views (e.g. coarse “merchant category” to guide merchant account creation), those views come from upstream egress and are read via `sealed_inputs_6A` with `role="UPSTREAM_EGRESS"`.

#### 3.2.2 Zones, routing & virtual overlay (2B, 3A, 3B)

* **Authority:** 2B (routing), 3A (zone_alloc), 3B (virtual overlay)

S2 **must not**:

* reinterpret routing weights or alias laws,
* change zone allocations or virtual merchant classification,
* assign accounts in a way that assumes new routing behaviours (e.g. “this account must always transact at zone Z”).

S2 may *annotate* accounts with high-level attributes that are consistent with upstream zones (e.g. “home_region” or a “likely routing region”), but it does not own those upstream constructs.

#### 3.2.3 Intensities & arrivals (5A, 5B)

* **Authority:** 5A (intensity surfaces) and 5B (arrival skeleton).

S2 **must not**:

* read or modify individual arrivals (`arrival_events_5B`),
* change λ surfaces or bucket counts,
* embed assumptions about future transactional volume that contradict 5A/5B.

If S2 uses volume hints, it must use **explicitly sealed aggregates** (if present) and treat them as hints, not strict laws.

---

### 3.3 6A authority boundaries: S1 vs S2 vs later states

Within Layer-3 / 6A:

#### 3.3.1 What S1 owns (for S2)

S1 is the single authority on:

* which `party_id`s exist for a given `(mf, seed)`,
* their party types, segments, home geography, and any S1-owned static attributes.

S2 **must not**:

* invent new `party_id`s or duplicate existing ones,
* change party attributes produced by S1.

S2 may only **reference** `s1_party_base_6A` to attach accounts to parties.

#### 3.3.2 What S2 exclusively owns

S2 is the sole authority on:

* **Account existence & identity**

  * number and type of accounts in the world per `(mf, seed)`,
  * assignment of `account_id` and any `product_id` if modeled,
  * mapping from `account_id` to owner `party_id` and/or `merchant_id`.

* **Static account attributes**

  * product type/family,
  * configured currency,
  * static risk flags or eligibility flags at account level,
  * any other account-level attributes that are fixed at initialisation.

No other state may create or delete accounts or modify these static attributes after S2 has run. Later states may annotate accounts (e.g. dynamic limits or flags) but not change their core identity.

#### 3.3.3 What S2 must not do (later-state & external boundaries)

S2 **must not**:

* Create instruments (card PANs, payment tokens) — those belong to the **instrument state** (likely S3).
* Create devices/IPs or graph edges — those belong to later states (S4, etc.).
* Assign fraud roles — static fraud posture is the responsibility of an explicit fraud-role state (S5).
* Attach accounts to **arrivals** or build **flows** — that is Layer-3 / 6B’s responsibility.

If an implementation tries to “sneak in” an early flow or fraud concept into S2, it is out-of-spec.

---

### 3.4 Forbidden dependencies & non-inputs

S2 **must not** depend on:

* Any dataset or config **not present** in `sealed_inputs_6A` for its `manifest_fingerprint`.

* Any artefact with `read_scope="METADATA_ONLY"` for row-level logic.

* Any external source of configuration or data, including but not limited to:

  * environment variables (beyond non-semantic toggles and logging),
  * wall-clock time (other than audit timestamps),
  * network calls, external databases, or non-catalogued files.

* Raw upstream validation bundles beyond:

  * what S0 has already validated and recorded,
  * any specific contract artefacts S2 is explicitly allowed to see as `role="CONTRACT"` (`METADATA_ONLY`).

Any behaviour that reads extra, off-catalogue files or encodes dependencies on environment-specific features **breaks** the S2 spec, even if it appears operationally convenient.

---

### 3.5 How S0’s sealed-input manifest constrains S2

The effective input universe for S2 is:

> all rows in `sealed_inputs_6A` for its `manifest_fingerprint` with `status ∈ {"REQUIRED","OPTIONAL"}`, plus `s1_party_base_6A`.

S2 MUST:

1. Load `s0_gate_receipt_6A` and `sealed_inputs_6A`.
2. Verify the sealed-inputs digest (as described in S0 & §2).
3. Filter `sealed_inputs_6A` to the subset relevant for S2 (product priors, link rules, taxonomies, optional context, contracts).
4. Refuse to read or rely on any artefact that:

   * is absent from `sealed_inputs_6A`, or
   * has `read_scope="METADATA_ONLY"` for data-level logic.

Downstream states can therefore assume:

* S2’s account base is constructed **only** from the sealed, catalogued inputs for that world,
* there are no hidden side channels, and
* any change to inputs will yield a new `sealed_inputs_digest_6A` and hence a semantically different 6A world.

---

## 4. Outputs (datasets) & identity *(Binding)*

6A.S2 produces the **account & product universe** for 6A. This section defines *what* those datasets are, *what they mean*, and *how they are identified* in the world.

S2 has:

* **one required base dataset** — the account universe,
* **one required derived dataset** — party-level holdings,
* optional diagnostic / convenience views.

Everything else in S2 is either RNG logs or internal planning surfaces, not part of the public contract.

---

### 4.1 Required dataset — account base

**Logical name:** `s2_account_base_6A`
**Role:** the *only* authoritative list of accounts/products that exist in the world for 6A/6B.

#### 4.1.1 Domain & scope

For each `(manifest_fingerprint, seed)`, `s2_account_base_6A` contains **one row per account** in that world+seed.

* Domain axes:

  * `manifest_fingerprint` — world identity (same as S0/S1 and upstream segments).
  * `parameter_hash` — parameter/prior pack identity (embedded as a column).
  * `seed` — RNG identity for this population realisation.

* S2 is **scenario-independent**:

  * there is a single account universe per `(mf, seed)`, shared across all scenarios;
  * if scenario-specific accounts are ever introduced, that is a breaking change.

#### 4.1.2 Required content (logical fields)

The base table MUST include, at minimum, the following logical fields (names can vary in the schema, semantics cannot):

* **Identity & linkage**

  * `account_id`

    * stable identifier for the account within `(manifest_fingerprint, seed)`,
    * globally unique for that world+seed.
  * `manifest_fingerprint`
  * `parameter_hash`
  * `seed`

* **Owners**

  * `owner_party_id` (or `party_id`):

    * reference to the owning party in `s1_party_base_6A`,
    * MUST match an existing `party_id` for the same `(mf, seed)`.
  * optional `owner_merchant_id` (for merchant settlement/acquiring accounts):

    * reference to a merchant in the Layer-1 merchant universe,
    * MUST match a valid `merchant_id` in upstream egress if present.
  * optional `ownership_role` / `account_role` (e.g. `PRIMARY_HOLDER`, `JOINT_HOLDER`, `MERCHANT_SETTLEMENT`), if you support multiple owners per account — the semantics must be pinned in the schema.

* **Account & product classification**

  * `account_type` — enum keyed off the account taxonomy (e.g. `CURRENT_ACCOUNT`, `SAVINGS_ACCOUNT`, `CREDIT_CARD`, `LOAN`, `MERCHANT_SETTLEMENT`, `WALLET`).
  * optional `product_family` — higher-level grouping (e.g. `RETAIL_CURRENT`, `BUSINESS_LOAN`, `PREMIUM_CARD`).
  * optional `product_tier` / `brand` — further classification if the taxonomy supports it.

* **Currency & geography**

  * `currency_iso` — ISO currency code for the account (if the product is currency-denominated).
  * optional `country_iso` / `region_id` — account’s home country/region (often inherited from owner or product definition).

* **Static account attributes**

  Only attributes that S2 owns; anything dynamic (balances, limits that evolve, flags set by behaviour) belongs later.

  Examples:

  * `overdraft_enabled` (bool)
  * `credit_limit_band` (banded, not raw numeric limit)
  * `account_risk_tier` (e.g. `STANDARD`, `HIGH_RISK`, `PREMIUM`)
  * `channel_profile` (e.g. `BRANCH_HEAVY`, `MOBILE_FIRST`)
  * eligibility flags such as `eligible_for_overdraft`, `eligible_for_loans`, if those are static.

All of these are:

* derived from 6A’s product-mix and account-level priors,
* immutable within S2; later states may only *read* them.

#### 4.1.3 Identity & invariants

For `s2_account_base_6A`:

* **Logical primary key:**

  ```text
  (manifest_fingerprint, seed, account_id)
  ```

* **Uniqueness invariants:**

  * `account_id` MUST be unique within `(manifest_fingerprint, seed)`.
  * There MUST be no two rows with the same `(mf, seed, account_id)`.

* **Ownership invariants:**

  * Every `owner_party_id` MUST appear in `s1_party_base_6A` for the same `(mf, seed)`.
  * If `owner_merchant_id` is present:

    * it MUST reference a valid upstream merchant,
    * it MUST respect any linkage rules (e.g. no retail customer as owner of a merchant-settlement-only account).

* **World consistency:**

  * All rows in the `(seed={seed}, fingerprint={mf})` partition MUST share those values in their columns.
  * All rows for `(mf, seed)` MUST share the same `parameter_hash` value; if multiple parameter packs show up, that world+seed is invalid from S2’s perspective.

* **Closed-world semantics for accounts:**

  For a given `(manifest_fingerprint, seed)`, the set of `account_id` values in `s2_account_base_6A` is the **full account universe** for that world+seed. No other dataset is allowed to introduce additional accounts; later states must treat this as read-only ground truth.

---

### 4.2 Required dataset — party product holdings

**Logical name:** `s2_party_product_holdings_6A`
**Role:** per-party aggregate view of “what this party holds”, strictly derived from the base table and S1’s party base.

#### 4.2.1 Domain & scope

For each `(manifest_fingerprint, seed)`, `s2_party_product_holdings_6A` contains at most one row per party per product grouping.

A typical grouping is:

```text
g = (party_id, account_type)  or  (party_id, product_family)
```

The grouping scheme itself becomes part of the binding spec once chosen.

#### 4.2.2 Required content (logical fields)

At minimum:

* Identity:

  * `manifest_fingerprint`
  * `parameter_hash`
  * `seed`
  * `party_id` (must exist in `s1_party_base_6A`)

* Grouping keys:

  * either `account_type` or `product_family` (or both), depending on design.

* Holdings metrics:

  * `account_count` — number of accounts matching the group for this party.
  * optional metrics:

    * `primary_account_count` vs `secondary_account_count`,
    * simple risk indicators (e.g. count of high-risk-tier accounts).

This table is **derived**: every row must correspond to a set of rows in `s2_account_base_6A` joined to S1; it must not introduce any new `party_id` or account semantics.

#### 4.2.3 Identity & invariants

* **Logical key:**

  * `(manifest_fingerprint, seed, party_id, [grouping_keys…])`

* **Derivation invariant:**

  * For each row, `account_count` must equal the count of base-table rows where:

    * `owner_party_id == party_id`, and
    * other grouping columns match.

* **Coverage invariant:**

  * Summing `account_count` across holdings for a party must equal that party’s total accounts in `s2_account_base_6A`.

If this table is ever out of sync with the base, the base wins and S2 is considered invalid.

---

### 4.3 Optional datasets — merchant accounts & summaries

Depending on how you choose to present merchant accounts and diagnostics, S2 may expose additional views. These are **optional** and strictly derived from the base.

#### 4.3.1 Optional merchant account base

**Logical name:** `s2_merchant_account_base_6A`
**Role:** convenience view for accounts where a merchant is a primary owner (if you don’t want to force all consumers to filter the main base).

* Domain: subset of `s2_account_base_6A` where `owner_merchant_id` is non-null, possibly with merchant-oriented attributes (e.g. acquiring region, MCC).

* Invariants:

  * Must be a pure subset of the base table.
  * No row may exist here without a matching row in `s2_account_base_6A`.

Whether you implement this as a separate table or just a documented filter on the base is a design choice; either way, it must not introduce new accounts.

#### 4.3.2 Optional account summary

**Logical name:** `s2_account_summary_6A`
**Role:** aggregate counts across world/segment/product dimensions for diagnostics and sizing, e.g.:

* group keys: `(region_id, account_type, party_segment)`
* metrics: `account_count`, optional `party_count_with_account`, etc.

Invariants:

* For any grouping, `account_count` must equal the number of base-table rows that match that group.
* Summing `account_count` over all groups must equal `COUNT(*)` of `s2_account_base_6A` for the `(mf, seed)`.

Again, the summary is informative only; the base remains the source of truth.

---

### 4.4 Relationship to upstream and downstream identity

S2 outputs are carefully aligned with identity axes upstream and in later states:

* **Upstream alignment:**

  * `manifest_fingerprint` and `parameter_hash` match S0/S1 and the upstream world; S2 does not introduce new “world IDs”.
  * `owner_party_id` references S1’s `s1_party_base_6A`.
  * `owner_merchant_id` (if used) references the merchant universe defined in Layer-1.

* **Downstream alignment:**

  * Later 6A states (e.g. instruments, devices/IP, fraud posture) and 6B will attach further structure and behaviour to accounts using:

    * `(manifest_fingerprint, seed, account_id)` as the primary key,
    * `party_id` and `merchant_id` as foreign keys.

  * No downstream state is permitted to create accounts outside `s2_account_base_6A` or to change the static attributes S2 defines.

* **Closed-world semantics for the financial universe:**

  * `s1_party_base_6A` answers **“who exists?”**,
  * `s2_account_base_6A` answers **“what accounts/products exist and who owns them?”**,
  * 6B (and beyond) then answer **“what happens over time?”** — but always within those closed sets.

All identity and dataset semantics described here are **binding**. The exact schema text and dictionary/registry wiring live in §5 and the JSON-Schema files; implementations must adhere to this meaning when generating S2 outputs.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

All binding schema anchors, dataset IDs, partitioning rules, and manifest keys for this state's egress live in the Layer-3 / Segment 6A contracts:
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/dataset_dictionary.layer3.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/artefact_registry_6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/schemas.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/schemas.layer3.yaml`

This specification only summarises semantics so there is a single source of truth for catalogue details. Always consult the files above for precise schema refs, physical paths, partition keys, writer ordering, lifecycle flags, and dependency metadata.

### 5.1 Outputs owned by this state
- `s2_account_base_6A` — Account and product universe derived from sealed holdings plus S1 context, keyed by account_id.
- `s2_party_product_holdings_6A` — Per-party holdings describing which products/accounts each party controls after S2 filtering.
- `s2_merchant_account_base_6A` — Subset of the account base covering merchant/acquirer specific accounts used downstream.
- `s2_account_summary_6A` — Aggregate counts and QA metrics for account coverage, grouped by product and geography.

### 5.2 Catalogue & downstream obligations
Implementations and downstream consumers MUST resolve datasets via the dictionary/registry, honour the declared schema anchors, and treat any artefact not listed there as out of scope for this state.

## 6. Deterministic algorithm (with RNG — account counts & allocation) *(Binding)*

6A.S2 is **deterministic given**:

* the sealed 6A input universe (`s0_gate_receipt_6A`, `sealed_inputs_6A`),
* the party base from S1 (`s1_party_base_6A`),
* the relevant S2 priors/taxonomies,
* `manifest_fingerprint`, `parameter_hash`, and `seed`.

This section fixes **what S2 does, in which order, and which parts are RNG-bearing vs RNG-free**.
Implementers are free to choose data structures and optimisations, but **not** free to change the observable behaviour described here.

---

### 6.0 Overview & RNG discipline

For each `(manifest_fingerprint, seed)`:

1. Load gate, priors & taxonomies (RNG-free).
2. Define population cells & derive **continuous account targets** per cell/product type (RNG-free).
3. Realise **integer account counts** per cell/product type (RNG-bearing).
4. Allocate accounts to individual parties (and merchants, if applicable) (RNG-bearing).
5. Assign static account attributes (RNG-bearing).
6. Materialise S2 datasets & run internal checks (RNG-free).

RNG discipline:

* S2 uses the **Layer-3 Philox envelope**, with substreams keyed on `(manifest_fingerprint, seed, "6A.S2", substream_label, context…)`.

* S2 defines at least these RNG families (names indicative, but semantics binding):

  * `account_count_realisation` (contract id: `rng_event_account_count_realisation`; substream_label: `account_count_realisation`) - realising integer account counts per cell/product.
  * `account_allocation_sampling` (contract id: `rng_event_account_allocation_sampling`; substream_label: `account_allocation_sampling`) - allocating realised counts to parties/merchants.
  * `account_attribute_sampling` (contract id: `rng_event_account_attribute_sampling`; substream_label: `account_attribute_sampling`) - sampling account-level attributes (currency, tier, flags).

* Each RNG event is logged under an `rng_event_*` schema with:

  * `counter_before`, `counter_after`,
  * `blocks`, `draws` (per event),
  * contextual identifiers (world, seed, cell, product, attribute family).

RNG **never** influences identity axes (`manifest_fingerprint`, `parameter_hash`, `seed`) or the shape of the output schema; it only affects realised counts and assignments.

---

### 6.1 Phase 1 — Load gate, priors & taxonomies (RNG-free)

**Goal:** Ensure S2 is operating under a sealed world, and load the S2-specific priors/taxonomies it needs.

1. **Verify S0 gate & sealed inputs**

   * Read `s0_gate_receipt_6A` and `sealed_inputs_6A` for the target `manifest_fingerprint`.
   * Recompute `sealed_inputs_digest_6A` and check equality with the receipt.
   * Ensure all required upstream segments `{1A,1B,2A,2B,3A,3B,5A,5B}` are `gate_status="PASS"`.

2. **Verify S1 gate**

   * Read the latest 6A.S1 run-report for `(mf, seed)` and require `status="PASS"` and empty `error_code`.
   * Resolve and validate `s1_party_base_6A` for `(seed={seed}, fingerprint={mf})` against its schema.

3. **Identify S2-relevant sealed inputs**

   From `sealed_inputs_6A`, select entries with:

   * `role ∈ { "PRODUCT_PRIOR", "PRODUCT_LINKAGE_RULES", "TAXONOMY", "UPSTREAM_EGRESS", "SCENARIO_CONFIG" }`,
   * `status ∈ { "REQUIRED", "OPTIONAL" }`.

   Partition these into:

   * **Product mix priors & account-per-party priors** (PRODUCT_PRIOR).
   * **Linkage/eligibility rules** (contract ids: `product_linkage_rules_6A`, `product_eligibility_config_6A`).
   * **Account/product taxonomies** (TAXONOMY).
   * **Optional context surfaces** (UPSTREAM_EGRESS / SCENARIO_CONFIG).

4. **Load & validate priors/taxonomies**

   * For each required prior/taxonomy:

     * resolve via `path_template` + `partition_keys`,
     * read rows and validate against `schema_ref`,
     * confirm digest matches `sha256_hex` (and any registry digest).

   * Build in-memory structures such as:

     * taxonomy maps for `account_type`, `product_family`, `currency_iso`, etc.,
     * per-“population cell” product mix priors (see 6.2),
     * per-cell or per-attribute linkage rules (party_type/segment/region ↔ allowed account types),
     * any per-account attribute priors (e.g. currency distribution per region & product).

5. **Load optional context**

   * If configured and present:

     * load upstream geo/socio-economic surfaces (e.g. banking penetration by country),
     * load aggregate volume hints from 5A/5B (e.g. “card-heavy” vs “cash-heavy” regions).

   * These may scale or tilt product-mix priors but must not redefine taxonomies or identity.

This phase is strictly **RNG-free** and must be deterministic given the sealed inputs.

---

### 6.2 Phase 2 — Define domain & derive continuous account targets (RNG-free)

**Goal:** Define the domain over which S2 plans accounts, and compute **continuous target counts** per cell/product type.

#### 6.2.1 Define population cells for accounts

Choose a “population cell” granularity for account planning, consistent with priors. For example:

```text
base cell b = (region_id, party_type, segment_id)
acc cell c  = (region_id, party_type, segment_id, account_type)
```

Steps:

1. **Compute party cell counts**

   * From `s1_party_base_6A`, group parties by base cell `b` and compute:

     ```text
     N_party(b) = number of parties in cell b
     ```

   * Cells with `N_party(b) = 0` may be dropped unless priors explicitly require accounts in empty cells (in which case that is a modelling error).

2. **Define account-type domain per cell**

   * For each base cell `b`, use product mix priors to determine the set of allowed `account_type`s:

     ```text
     A(b) = {account_type | priors say type is allowed for b}
     ```

   * The account-cell domain is:

     ```text
     C_acc = { c = (b, account_type) | account_type ∈ A(b) }
     ```

#### 6.2.2 Derive continuous account targets

For each account cell `c = (b, account_type)`:

1. From priors, obtain:

   * expected **accounts per party** of this type in this cell:

     ```text
     λ_acc_per_party(c) ≥ 0
     ```

   * optionally, global/product-level constraints (e.g. world-level card penetration, max/min accounts per party).

2. Compute **continuous target accounts per cell**:

   ```text
   N_acc_target(c) = N_party(b) * λ_acc_per_party(c) * s_context(c)
   ```

   where:

   * `s_context(c)` is a deterministic scaling factor derived from context surfaces (e.g. volume hints, socio-economic data) if used; otherwise `s_context(c)=1`.

3. Sanity checks (RNG-free):

   * For all `c`, `N_acc_target(c)` must be finite and ≥ 0.

   * For each base cell `b`, the implied total expected accounts:

     ```text
     N_acc_target_total(b) = Σ_{account_type∈A(b)} N_acc_target(b, account_type)
     ```

     must be finite and within any configured bounds (e.g. max accounts per party × `N_party(b)`).

   * Summed over all `c`, a global `N_acc_target_world` is defined and finite.

If any of these conditions fail, S2 must fail with an appropriate target-derivation error (e.g. `6A.S2.ACCOUNT_TARGETS_INCONSISTENT`).

This phase is purely arithmetic and RNG-free.

---

### 6.3 Phase 3 — Realise integer account counts per cell (RNG-bearing)

**Goal:** Convert continuous targets `N_acc_target(c)` into **integer counts** `N_acc(c)` per account cell, respecting constraints as far as possible.

This is the first RNG-bearing phase and uses the `account_count_realisation` family.

#### 6.3.1 Global / regional totals (optional two-step)

A typical, conservation-friendly approach:

1. **Region/product-type totals (RNG-free)**

   If desired, you can first aggregate targets by `(region_id, account_type)`:

   ```text
   N_acc_target_region(r, t) = Σ_{b with region_id=r; account_type=t} N_acc_target(b, t)
   ```

   Then integerise these higher-level targets by deterministic rounding and largest-remainder allocation (no RNG):

   * `N_acc_floor_region(r, t) = floor(N_acc_target_region(r, t))`,
   * assign remaining units per `(r, t)` deterministically to regions using residual fractions.

2. **Per-cell splitting (RNG-bearing)**

   For each `(r, t)`, you have:

   * integer `N_acc_region(r, t)`,
   * per-cell shares `π_c|r,t` derived from `N_acc_target(c)`.

   Use `account_count_realisation` to sample integer `N_acc(c)` for all cells `c` under `(r, t)` such that:

   * `Σ_{c under (r,t)} N_acc(c) = N_acc_region(r, t)`,
   * the realised split approximates `π_c|r,t`,
   * counts are non-negative integers.

This may be implemented via multinomial draws or by a stochastic variant of largest-remainder rounding; the spec cares only about the invariants.

#### 6.3.2 Direct per-cell integerisation (allowed alternative)

If you don’t do a regional step, you may integerise directly per cell with global constraints, e.g.:

* `N_acc_floor(c) = floor(N_acc_target(c))`,
* residuals `r_c = N_acc_target(c) - N_acc_floor(c)`,
* sum of floors `N_floor_world = Σ_c N_acc_floor(c)`,
* desired integer total `N_acc_world_int` (rounded global target).

Use `account_count_realisation` RNG to allocate the remaining `N_acc_world_int - N_floor_world` units across cells proportionally to `r_c`.

Again, invariants:

* `N_acc(c) ≥ 0`, integer,
* `Σ_c N_acc(c) = N_acc_world_int`.

#### 6.3.3 RNG events & invariants

For each RNG batch (e.g. per `(r, t)` or per world):

* Emit `rng_event_account_count` with:

  * context: `(manifest_fingerprint, parameter_hash, seed, region_id, account_type, …)`,
  * RNG envelope: before/after counters, `blocks`, `draws`,
  * optional summary stats (e.g. `N_acc_target_region`, `N_acc_region`, number of cells).

After Phase 3:

* All `N_acc(c)` are non-negative integers.
* Conservation constraints chosen in your design (per region/product or world) hold exactly.
* Any configured min/max constraints (e.g. max accounts per party × `N_party(b)`) are not violated; if they are, S2 must FAIL with an integerisation error.

---

### 6.4 Phase 4 — Allocate realised accounts to parties/merchants (RNG-bearing)

**Goal:** Given integer `N_acc(c)` per account cell, create `N_acc(c)` account instances and assign each to a **party** (and optionally a **merchant**) in that cell, respecting linkage rules.

This phase uses the `account_allocation_sampling` RNG family.

#### 6.4.1 Construct party-level allocation weights

For each base cell `b = (region_id, party_type, segment_id)` and each account type in `A(b)`:

1. **Collect parties in cell**

   * From `s1_party_base_6A`, collect all parties with attributes matching `b`.

2. **Compute allocation weight per party**

   * Using account-per-party priors, derive a non-negative weight `w_p(b, account_type)` for each party `p` in cell `b`.
   * These weights represent relative propensity to hold that account type (e.g. some segments in `b` may have higher/lower propensity).

3. **Normalise weights**

   * For each `(b, account_type)` with at least one party:

     ```text
     W_total = Σ_p w_p
     π_p = w_p / W_total   (if W_total > 0)
     ```

   * If `W_total = 0` for a cell with `N_party(b) > 0` but `N_acc(b, account_type) > 0`, that is a configuration error: S2 must fail (`6A.S2.ACCOUNT_TARGETS_INCONSISTENT` or `LINKAGE_RULE_VIOLATION`).

#### 6.4.2 Allocate accounts to parties (party-owner accounts)

For each account cell `c = (b, account_type)` with `N_acc(c) > 0` and a non-empty party set:

1. **Draw `N_acc(c)` owner parties**

   * Use `account_allocation_sampling` RNG to perform `N_acc(c)` draws from the categorical distribution `π_p` over parties in cell `b`:

     * Each draw selects a party `p` as the primary owner of one account of `account_type`.
     * Sampling may be:

       * **with replacement**, resulting in a multi-set of parties, OR
       * via a more complex scheme if you want per-party caps (using priors and linkage rules).

2. **Apply hard constraints**

   * Enforce any hard constraints from linkage rules, for example:

     * per-party maximum number of accounts of a given type,
     * disallowed combinations (e.g. some segments cannot have certain account types).

   * Strategies include:

     * reject-and-redraw within a bounded retry budget, or
     * precompute a feasible “desired accounts per party” distribution and ensure sampling respects it.

   * If a feasible allocation cannot be found without breaking constraints, S2 must FAIL with `6A.S2.LINKAGE_RULE_VIOLATION` (or a more specific code) rather than silently ignoring constraints.

3. **Produce per-party allocations**

   * The output of this step is a mapping:

     ```text
     for each party p and account_type a:
        n_accounts(p, a) ∈ ℕ
     ```

   * Satisfying:

     ```text
     Σ_p n_accounts(p, a) == N_acc(c)  for each cell c = (b, a)
     ```

Each group of draws for `(b, account_type)` must be covered by one or more `rng_event_account_allocation` events with proper RNG accounting.

#### 6.4.3 Allocate merchant accounts (if applicable)

If merchant accounts (e.g. settlement or acquiring accounts) are part of the model:

1. Define a **merchant cell** domain:

   * e.g. `(merchant_region, merchant_risk_class, merchant_size_band, account_type)`.

2. Use merchant-level priors to compute continuous targets and integer counts `N_acc_merchant(c)` in Phase 2–3 (similar to parties but over the merchant universe).

3. Allocate merchant accounts over merchants using the same pattern:

   * merchant weights from priors (e.g. `w_m` based on size, risk class),
   * RNG draws from a categorical distribution,
   * enforcement of merchant-level linkage constraints (e.g. some products only for certain MCCs).

The result is `n_accounts_for_merchant(m, account_type)` per merchant, analogous to per-party counts.

---

### 6.5 Phase 5 — Assign account attributes (RNG-bearing)

**Goal:** For each account instance, assign static attributes (currency, product tier, risk tier, etc.) consistent with priors and taxonomies.

This phase uses the `account_attribute_sampling` RNG family.

#### 6.5.1 Construct account-level attribute priors

From S2 priors/config:

* For each account cell (party-based or merchant-based) and account type, construct conditional distributions for attributes such as:

  * `π_currency | region, account_type`
  * `π_risk_tier | segment, account_type`
  * `π_channel_profile | segment, account_type`
  * etc.

These may depend on:

* region / country,
* party segment,
* account_type / product_family,
* optional context.

Attribute priors are deterministic functions of priors, taxonomies, and cell/party/merchant attributes.

#### 6.5.2 Sample attributes per account

For each realised account instance:

1. **Identify context**

   * Determine the cell context (region, party_type, segment, account_type) and any party/merchant-level attributes that condition priors.

2. **Sample attribute values**

   * For each attribute S2 owns:

     * sample a value from its conditional prior using `account_attribute_sampling` RNG,
     * possibly vectorising per batch (e.g. per cell) while maintaining the RNG envelope.

3. **Emit RNG events**

   * For each batch of attribute draws (per cell and attribute family), emit `rng_event_account_attribute` with:

     * context (mf, seed, cell, attribute family),
     * counters before/after, `blocks`, `draws`,
     * optional summary stats (e.g. histograms of assigned values).

This step fully determines the static account attributes that appear in `s2_account_base_6A`.

---

### 6.6 Phase 6 — Materialise S2 datasets & internal validation (RNG-free)

**Goal:** Write S2 outputs with correct identity and check that they are consistent with the realised plan and invariant constraints.

#### 6.6.1 Materialise `s2_account_base_6A`

Using the allocations and attributes from Phases 4–5:

* Construct rows for `s2_account_base_6A` with:

  * `manifest_fingerprint`, `parameter_hash`, `seed`,
  * `account_id` (deterministic function of `(mf, seed, cell, local_account_index)`),
  * `owner_party_id` and optional `owner_merchant_id`,
  * account classification fields (account_type, product_family, …),
  * static attributes (currency, risk tier, flags, etc.).

* Ensure `account_id` is generated by a deterministic, injective function within `(mf, seed)`, e.g.:

  ```text
  account_id = LOW64( SHA256( mf || seed || "account" || cell_key(c) || uint64(i) ) )
  ```

  where `i` is the per-cell local index.

* Write to:

  ```text
  data/layer3/6A/s2_account_base_6A/seed={seed}/manifest_fingerprint={mf}/...
  ```

  using the partitioning and ordering specified in the dictionary.

* Validate:

  * Schema conformance against `schemas.6A.yaml#/s2/account_base`.
  * Uniqueness of `(mf, seed, account_id)`.
  * FK to `s1_party_base_6A` (owner_party_id) and to merchants (owner_merchant_id, if present).

#### 6.6.2 Materialise derived datasets

1. **`s2_party_product_holdings_6A`**

   * Aggregate `s2_account_base_6A` joined to `s1_party_base_6A` by the chosen grouping (e.g. `(party_id, account_type)`):

     ```text
     account_count(p, type) = count of base rows where owner_party_id = p and account_type = type
     ```

   * Write to the configured path/partition, validate against schema.

   * Check per-party consistency:

     * sum of `account_count(p, *)` over all groups for party `p` equals total accounts in base for `p`.

2. **Optional `s2_merchant_account_base_6A`**

   * If implemented, filter `s2_account_base_6A` to rows with `owner_merchant_id` non-null and write the subset to its own dataset.

3. **Optional `s2_account_summary_6A`**

   * Aggregate `s2_account_base_6A` by the configured grouping keys (e.g. region × segment × account_type) and write the result.

#### 6.6.3 Internal validation

Before marking S2 as PASS for `(mf, seed)`, S2 must perform internal checks, including:

* **Plan vs base consistency:**

  * For each account cell `c`, the count of base-table rows in that cell must equal `N_acc(c)` realised in Phase 3.
  * Summing over all cells yields the global `N_acc_world_int`.

* **Holdings & summary consistency:**

  * For every holdings row, `account_count` matches the base-table count.
  * For every summary row, `account_count` matches the base-table count for that group.

* **Linkage invariants:**

  * All base-table rows obey eligibility rules (no forbidden owner/product combinations).
  * No party or merchant exceeds configured min/max per product type, where such constraints are configured.

Any violation must result in a **FAIL** for S2 with an appropriate error code (`ACCOUNT_BASE_SCHEMA_OR_KEY_INVALID`, `ACCOUNT_COUNTS_MISMATCH`, `LINKAGE_RULE_VIOLATION`, etc.) and a non-PASS run-report.

---

### 6.7 Determinism guarantees

Given:

* `manifest_fingerprint`,
* `parameter_hash`,
* `seed`,
* sealed `s0_gate_receipt_6A`, `sealed_inputs_6A`,
* sealed S1 outputs (`s1_party_base_6A`),
* S2 priors/taxonomies/configs included in `sealed_inputs_6A`,

S2’s business outputs (`s2_account_base_6A`, `s2_party_product_holdings_6A`, and any optional derived views) must be:

* **bit-stable and idempotent** — re-running S2 in the same catalogue state and with the same seed must produce byte-identical outputs;
* independent of:

  * execution scheduling and parallelism strategy,
  * physical file layout beyond the canonical ordering,
  * environment-specific details (hostnames, wall-clock, etc.).

All uses of randomness must go through the declared S2 RNG families under the Layer-3 envelope and must be fully accounted in RNG events and trace logs.

Any change to:

* S2 priors,
* taxonomies,
* mapping from priors to counts/allocations, or
* RNG family semantics

is a behavioural change and must be controlled under §12 (change control & compatibility), not silently introduced as an implementation tweak.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S2’s outputs are identified, partitioned, ordered and merged**.
All downstream 6A states (S3–S5) and 6B must treat these rules as **binding**, not implementation hints.

S2’s business outputs are:

* **Required:**

  * `s2_account_base_6A`
  * `s2_party_product_holdings_6A`
* **Optional, strictly derived from the base:**

  * `s2_merchant_account_base_6A`
  * `s2_account_summary_6A`

RNG logs follow the Layer-3 RNG envelope and are covered by layer-wide RNG contracts, not here.

---

### 7.1 Identity axes

S2 is defined over the same three primary axes as S1:

* **World identity**

  * `manifest_fingerprint`
  * Identifies the sealed upstream world and 6A input universe.
  * S2 must never change or reinterpret this value.

* **Parameter identity**

  * `parameter_hash`
  * Identifies the parameter/prior pack set governing product mix, linkage rules, and account attributes.
  * Stored as a column in S2 outputs, **not** as a partition key.
  * For a given `(manifest_fingerprint, seed)`, there MUST be exactly one `parameter_hash` in S2 outputs.

* **RNG identity**

  * `seed`
  * Identifies the specific population / account realisation within a world.
  * Different seeds with the same `(mf, ph)` represent different account universes (even though they share priors and world structure).

`run_id` is logging-only and MUST NOT affect business outputs.

---

### 7.2 Partitioning & path tokens

All S2 datasets are **world+seed scoped** and partitioned identically.

#### 7.2.1 `s2_account_base_6A`

* Partition keys:

  ```text
  [seed, fingerprint]
  ```

* Path template (schematic):

  ```text
  data/layer3/6A/s2_account_base_6A/
    seed={seed}/
    fingerprint={manifest_fingerprint}/
    s2_account_base_6A.parquet
  ```

#### 7.2.2 `s2_party_product_holdings_6A`

* Partition keys:

  ```text
  [seed, fingerprint]
  ```

* Path template (schematic):

  ```text
  data/layer3/6A/s2_party_product_holdings_6A/
    seed={seed}/
    fingerprint={manifest_fingerprint}/
    s2_party_product_holdings_6A.parquet
  ```

#### 7.2.3 Optional `s2_merchant_account_base_6A` / `s2_account_summary_6A`

If implemented, both follow the same partition scheme:

* Partition keys:

  ```text
  [seed, fingerprint]
  ```

* Path templates:

  ```text
  data/layer3/6A/s2_merchant_account_base_6A/seed={seed}/manifest_fingerprint={mf}/...
  data/layer3/6A/s2_account_summary_6A/seed={seed}/manifest_fingerprint={mf}/...
  ```

**Binding rules:**

* The `seed={seed}` and `fingerprint={manifest_fingerprint}` path tokens MUST match the `seed` and `manifest_fingerprint` columns inside the data.
* No additional partition keys shall be introduced for S2 business datasets (no `parameter_hash`, no `scenario_id`).
* Any consumer that wants S2 data for `(mf, seed)` MUST resolve the dataset via the catalogue and then substitute these tokens; hard-coded path logic is out-of-spec.

---

### 7.3 Primary keys, foreign keys & uniqueness

#### 7.3.1 `s2_account_base_6A`

* **Logical primary key:**

  ```text
  (manifest_fingerprint, seed, account_id)
  ```

* **Uniqueness:**

  * `account_id` MUST be unique within each `(manifest_fingerprint, seed)`.
  * No duplicate `(mf, seed, account_id)` rows are permitted.

* **Foreign keys:**

  * `owner_party_id` MUST reference an existing `party_id` in `s1_party_base_6A` for the same `(mf, seed)`.
  * If present, `owner_merchant_id` MUST reference a valid upstream merchant (as defined by L1 dictionaries/registries).
  * Any account that cannot satisfy these FKs MUST be treated as an S2 failure (not silently dropped).

* **Parameter consistency:**

  * All rows for a given `(mf, seed)` MUST share the same `parameter_hash`.
  * If multiple `parameter_hash` values appear for the same `(mf, seed)`, that is an identity/config error.

#### 7.3.2 `s2_party_product_holdings_6A`

* **Logical key** (assuming grouping by `(party_id, account_type)`; adapt if you choose a different grouping):

  ```text
  (manifest_fingerprint, seed, party_id, account_type)
  ```

* **Derivation invariant:**

  * For each row, `account_count` MUST equal the number of rows in `s2_account_base_6A` where:

    * `owner_party_id == party_id`,
    * `account_type` matches (and any other grouping keys match).

* **Coverage invariant:**

  * Summing `account_count` over all holdings rows for a given `party_id` MUST equal that party’s total accounts in `s2_account_base_6A`.

No new `party_id` may appear here; every `party_id` MUST exist in `s1_party_base_6A`.

#### 7.3.3 Optional views

If implemented:

* **`s2_merchant_account_base_6A`**

  * Logical key: `(manifest_fingerprint, seed, account_id)` (same as base).
  * MUST be a strict subset of `s2_account_base_6A` (typically accounts with `owner_merchant_id` non-null).
  * No rows may appear that are not also in the base table.

* **`s2_account_summary_6A`**

  * Key depends on grouping (e.g. `(mf, seed, country_iso, segment_id, account_type)`).
  * For each grouping key `g`, `account_count(g)` MUST equal the number of base rows matching `g`.
  * Summing `account_count` over all groups MUST equal `COUNT(*)` of `s2_account_base_6A` for `(mf, seed)`.

---

### 7.4 Ordering: canonical vs semantic

We distinguish:

* **Canonical ordering** — required of writers to ensure idempotence and stable digests.
* **Semantic ordering** — ordering that consumers are allowed to rely on.

#### 7.4.1 Canonical writer ordering

The dataset dictionary defines a canonical `ordering` for each S2 dataset, e.g.:

* `s2_account_base_6A`:

  ```text
  ORDER BY country_iso, account_type, owner_party_id, account_id
  ```

* `s2_party_product_holdings_6A`:

  ```text
  ORDER BY party_id, account_type
  ```

* Optional datasets: analogous groupings.

Writers MUST respect these canonical sort orders when materialising partitions. This ensures:

* stable write-outs across re-runs,
* predictable digests if any higher-level hashing incorporates S2 datasets.

#### 7.4.2 Semantic ordering

Consumers **must not** derive business meaning from physical row order:

* They must use **keys and filters** (party_id, account_type, region, etc.) to interpret the data.
* Assuming, for example, “first N rows are one region” is out-of-spec.

Canonical ordering is a writer responsibility and may be used in internal audits; it is not a semantic guarantee for downstream business logic.

---

### 7.5 Merge discipline & lifecycle

S2 behaves as **replace-not-append** at the granularity of `(manifest_fingerprint, seed)`.

#### 7.5.1 Replace-not-append per world+seed

For each `(mf, seed)`:

* There is **one logical account universe snapshot** in `s2_account_base_6A`.
* Likewise, one derived holdings view and any optional derived views.

Behavioural rules:

* Re-running S2 with the same inputs (`mf`, `ph`, `seed`, sealed inputs, S1 base) MUST either:

  * produce **byte-identical** outputs for all S2 datasets, or
  * fail with an `OUTPUT_CONFLICT` (or equivalent) error and leave existing outputs unchanged.

* There is no notion of appending or merging multiple S2 runs for the same `(mf, seed)`; any such attempt is a spec violation.

#### 7.5.2 No cross-world / cross-seed merges

* **No cross-world merges:**

  * Accounts from different `manifest_fingerprint`s MUST NEVER be mixed.
  * Any consumer aggregating across worlds must do so explicitly and treat each world as hermetic.

* **No cross-seed population merges:**

  * `seed` is a first-class identity axis.
  * For business semantics (e.g. accounts → flows → fraud), each `(mf, seed)` defines a self-contained universe.
  * Cross-seed aggregations can exist for analysis, but no state may treat two seeds as “one big world”.

If an implementation silently merges data from multiple seeds into a single S2 view, it is out-of-spec.

---

### 7.6 Consumption discipline for S3–S5 and 6B

Downstream states MUST respect S2’s identity and merge discipline.

#### 7.6.1 6A.S3–S5 (later 6A states)

For each `(mf, seed)` they operate on, S3–S5 MUST:

* Verify S2 PASS for that `(mf, seed)` using S2’s run-report (status + error_code).
* Confirm that `s2_account_base_6A` exists and is schema-valid.
* Treat:

  * `s2_account_base_6A` as the **only** source of accounts/products,
  * `s2_party_product_holdings_6A` (and optional views) as **derived** convenience layers.

They MUST NOT:

* create additional accounts (no new `account_id`s),
* modify static account attributes set by S2,
* attach instruments/devices/fraud roles to non-existent `account_id`s.

#### 7.6.2 6B (flows & fraud)

6B MUST:

* join flows and transactional entities to S2 via `(mf, seed, account_id)` (and via `party_id` / `merchant_id` as appropriate).
* treat any reference to an `account_id` not found in `s2_account_base_6A` for the same `(mf, seed)` as an error, not “an unknown account”.

6B is free to generate dynamic attributes (balances, limits, flags, flow-level risk signals), but these MUST NOT alter the identity, ownership or static classification that S2 has defined.

---

These identity, partitioning, ordering, and merge rules are **binding**. Storage format, engine, and parallelism are implementation details; any implementation that changes these semantics is not a correct implementation of 6A.S2.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines exactly **when 6A.S2 is considered PASS** for a given `(manifest_fingerprint, seed)`, and how **downstream states must gate** on S2 before using any account/product data.

If any condition here fails, S2 is **FAIL for that `(mf, seed)`**, and **no later 6A state (S3–S5) nor 6B may treat S2 outputs as valid**.

---

### 8.1 Segment-local PASS / FAIL definition

For a given `(manifest_fingerprint, seed)`, 6A.S2 is **PASS** *iff* all of the following hold.

#### 8.1.1 S0 / S1 / upstream worlds are sealed

1. **S0 gate & sealed-inputs are valid for this world:**

   * `s0_gate_receipt_6A` and `sealed_inputs_6A` exist for `manifest_fingerprint` and validate against their schemas.
   * Recomputing `sealed_inputs_digest_6A` from `sealed_inputs_6A` yields exactly the value recorded in `s0_gate_receipt_6A.sealed_inputs_digest_6A`.
   * Latest 6A.S0 run-report for this `mf` has:

     * `status == "PASS"`
     * `error_code` empty / null.

2. **Upstream segments are sealed:**

   * In `s0_gate_receipt_6A.upstream_gates`, each required segment in `{1A,1B,2A,2B,3A,3B,5A,5B}` has:

     ```text
     gate_status == "PASS"
     ```

3. **S1 is sealed for this `(mf, seed)`:**

   * Latest 6A.S1 run-report for `(mf, seed)` has:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```
   * `s1_party_base_6A` exists for `(seed={seed}, fingerprint={mf})`, validates against its schema, and `COUNT(*)` equals `total_parties` reported by S1.

If any of these fail, S2 MUST NOT produce accounts for that `(mf, seed)` and MUST fail with an appropriate gate error (e.g. `6A.S2.S0_OR_S1_GATE_FAILED`).

---

#### 8.1.2 Priors, taxonomies & linkage rules

4. **Required S2 priors and taxonomies are present and usable:**

   * Every prior/config artefact that S2’s design classifies as **required** (e.g. product mix priors, account-per-party priors, linkage rules, account taxonomies) has a row in `sealed_inputs_6A` with:

     * `status == "REQUIRED"`
     * `read_scope == "ROW_LEVEL"` (for data priors) or `METADATA_ONLY` (for pure contracts)
   * Each such artefact:

     * can be resolved from `path_template` / `partition_keys`,
     * validates against its `schema_ref`,
     * has a `sha256_hex` digest matching its contents.

5. **Taxonomy consistency:**

   * All account/product taxonomy tables required by S2 exist and are valid.
   * Every `account_type`, `product_family`, `account_risk_tier`, etc. that S2 intends to emit appears in the corresponding taxonomy with compatible semantics.

If any required prior/taxonomy is missing or invalid, S2 MUST fail with `6A.S2.PRIOR_PACK_MISSING`, `6A.S2.PRIOR_PACK_INVALID`, `6A.S2.PRIOR_PACK_DIGEST_MISMATCH`, or `6A.S2.TAXONOMY_MISSING_OR_INVALID` (or equivalent).

---

#### 8.1.3 Target derivation & integer account counts

6. **Continuous targets are sane:**

   * All continuous targets `N_acc_target(c)` (per account cell) are finite and ≥ 0.
   * Summaries such as:

     * per-cell totals to region or world,
     * per-region per-product totals,
       are within configured tolerances relative to priors (e.g. no absurd blowup due to mis-scaling).

7. **Integer counts are consistent and conservative:**

   After integerisation:

   * For each grouping where conservation is required (e.g. per region+account_type, or globally):

     ```text
     Σ_c N_acc(c) == target_integer_total_for_that_group
     ```
   * Every `N_acc(c)` is a non-negative integer.
   * Any configured min/max constraints are honoured, for example:

     * max accounts per party-type/segment/region,
     * min required accounts per cell, if specified.

If targets or integerisation fail these invariants, S2 MUST fail with `6A.S2.ACCOUNT_TARGETS_INCONSISTENT`, `6A.S2.ACCOUNT_INTEGERISATION_FAILED`, or `6A.S2.POPULATION_ZERO_WHEN_DISALLOWED` (if you define that variant).

---

#### 8.1.4 Base-table correctness & linkage

8. **`s2_account_base_6A` exists and is schema-valid:**

   * The partition for `(seed={seed}, fingerprint={mf})` exists.
   * It validates against `schemas.6A.yaml#/s2/account_base`.
   * The logical PK `(manifest_fingerprint, seed, account_id)` is unique:

     * no duplicate `account_id` within the same `(mf, seed)`,
     * all rows in the partition carry the correct `manifest_fingerprint` and `seed`.

9. **Foreign key & linkage invariants:**

   * For every row:

     * `owner_party_id` exists in `s1_party_base_6A` for the same `(mf, seed)`.
     * if `owner_merchant_id` is present, it references a valid upstream merchant.
   * All account-owner relationships respect linkage rules:

     * no disallowed combinations (e.g. retail-only products attached to business-only segments),
     * no party or merchant exceeds configured min/max accounts per product type, where such constraints are hard requirements.

   Violations surface as `6A.S2.ORPHAN_ACCOUNT_OWNER` or `6A.S2.LINKAGE_RULE_VIOLATION`.

10. **Counts match the integerisation plan:**

    * For each account cell `c` in the integer plan, the number of base-table rows in that cell equals `N_acc(c)`.
    * Summing across all cells per `(mf, seed)` yields the global `N_accounts_world_int` computed in Phase 3.

    Any mismatch is `6A.S2.ACCOUNT_COUNTS_MISMATCH`.

11. **Taxonomy compatibility in base:**

    * Every `account_type`, `product_family`, `currency_iso`, `country_iso`/`region_id`, and any enum-coded field in the base table:

      * appears in the corresponding taxonomy,
      * obeys compatibility rules (e.g. currency vs region, account_type vs party_type).

    Violations are treated as `6A.S2.TAXONOMY_COMPATIBILITY_FAILED` or a more specific code.

---

#### 8.1.5 Derived datasets (holdings & optional summaries)

12. **Party holdings are consistent with base:**

    * `s2_party_product_holdings_6A` exists and validates against `schemas.6A.yaml#/s2/party_product_holdings`.
    * For each row `(party_id, [grouping_keys…])`:

      ```text
      account_count == number of base rows matching that party & grouping
      ```
    * For each `party_id`, summing `account_count` over all its holdings rows equals the number of base-table rows with `owner_party_id = party_id`.

    Any mismatch is a `6A.S2.ACCOUNT_COUNTS_MISMATCH` or a specific holdings inconsistency code.

13. **Optional views (if implemented) are consistent:**

    * `s2_merchant_account_base_6A` is a strict subset of the base (no extra or altered accounts).
    * `s2_account_summary_6A` aggregates base-table rows exactly according to its grouping, and `Σ account_count` equals total base rows for `(mf, seed)`.

---

#### 8.1.6 RNG accounting

14. **RNG usage is fully accounted and within budget:**

    * All uses of randomness in S2 are confined to the declared RNG families:

      * `account_count_realisation`,
      * `account_allocation_sampling`,
      * `account_attribute_sampling`.

    * For each family, aggregate metrics from S2’s RNG event datasets and the Layer-3 RNG logs must reconcile:

      * number of events,
      * total draws and blocks,
      * no overlapping or out-of-order Philox counter ranges.

    * Any configured RNG budgets (e.g. max draws per family per world+seed) are respected.

If RNG accounting fails, S2 must fail with `6A.S2.RNG_ACCOUNTING_MISMATCH` or `6A.S2.RNG_STREAM_CONFIG_INVALID`.

---

### 8.2 Gating obligations for downstream 6A states (S3–S5)

For each `(manifest_fingerprint, seed)`, **6A.S3–S5 MUST treat S2 as a hard precondition**.

Before reading or using any account/product data, a downstream 6A state MUST:

1. Verify S0 and S1 gates as per their own specs, **and**

2. Verify S2 PASS for `(mf, seed)` by:

   * reading the latest 6A.S2 run-report for `(mf, seed)`,
   * requiring:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```
   * confirming that `s2_account_base_6A` and `s2_party_product_holdings_6A` exist and validate against their schemas.

3. Treat the absence of a PASS S2 run (or missing/invalid S2 datasets) as a **blocking gate failure** (e.g. `6A.S3.S2_GATE_FAILED`).

Additionally, S3–S5 MUST:

* NEVER create new accounts (`account_id`s) outside `s2_account_base_6A`.
* NEVER modify static account fields that S2 owns.
* ALWAYS join on `(manifest_fingerprint, seed, account_id)` (and through `party_id` / `owner_merchant_id` as needed) to attach their own structures.

---

### 8.3 Gating obligations for 6B and external consumers

6B and any external consumer that uses accounts/products for flows or decisioning must:

1. Require S2 PASS for the target `(mf, seed)`:

   * consult S2’s run-report,
   * confirm `status="PASS"` and empty `error_code`.

2. Treat `s2_account_base_6A` as the **only source of truth** for which accounts exist and who owns them.

3. Treat `s2_party_product_holdings_6A` and any optional views as **derived**, not as independent definitions of ownership.

4. Treat any reference to an `account_id` not present in `s2_account_base_6A` for the same `(mf, seed)` as an error, not as “an external/unknown account”.

6B may build balances, transactional histories and labels on top of `s2_account_base_6A`, but it MUST NOT change S2’s identity, ownership, or static classification.

---

### 8.4 Behaviour on failure & partial outputs

If S2 fails for a given `(manifest_fingerprint, seed)`:

* Any partially written S2 datasets (`s2_account_base_6A`, holdings, merchant views, summaries) **must not** be treated as valid.
* Downstream states must treat that world+seed as **having no valid S2 account universe**, regardless of whether files exist.

The 6A.S2 run-report MUST be updated with:

* `status = "FAIL"`,
* the relevant `error_code` from the `6A.S2.*` namespace,
* a short `error_message`.

The only valid states are:

* **S2 PASS →** S3–S5 and 6B may operate on accounts/products for that `(mf, seed)`.
* **S2 FAIL →** S3–S5 and 6B must NOT operate on accounts/products for that `(mf, seed)` until S2 is re-run and PASS.

These acceptance criteria and gating obligations are **binding** and fully define what “S2 is done and safe to build on” means for the rest of Layer-3 and the enterprise shell.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error surface** for 6A.S2.

Every failure for a given `(manifest_fingerprint, seed)` **must** be mapped to exactly one of these codes.
All are:

* **Fatal** for S2 for that `(manifest_fingerprint, seed)`.
* **Blocking** for S3–S5 and 6B for that `(manifest_fingerprint, seed)`.

No “best-effort” downgrade is allowed.

---

### 9.1 Error class overview

We group S2 failures into six classes:

1. **Gate / sealed-input / S1 errors** — S0/S1 not sealed, or inputs inconsistent.
2. **Priors, taxonomies & linkage rules errors** — missing/invalid product mix, account priors, taxonomies or linkage configs.
3. **Target derivation & integerisation errors** — impossible or inconsistent account counts.
4. **Base-table & linkage errors** — invalid `s2_account_base_6A` or holdings.
5. **RNG & accounting errors** — misuse or mis-accounting of randomness.
6. **IO / identity / internal errors** — storage conflicts or unexpected failures.

Each has a small, closed set of codes under the `6A.S2.*` namespace.

---

### 9.2 Canonical error codes

#### 9.2.1 Gate / sealed-input / S1 errors

These mean S2 cannot trust the world-level gate or party base.

* `6A.S2.S0_OR_S1_GATE_FAILED`
  *Meaning:* One of:

  * S0 is missing or not PASS for this `manifest_fingerprint`,
  * `sealed_inputs_digest_6A` recomputed from `sealed_inputs_6A` does not match `s0_gate_receipt_6A`,
  * one or more required upstream segments `{1A,1B,2A,2B,3A,3B,5A,5B}` have `gate_status != "PASS"`, or
  * S1 is missing or not PASS for this `(manifest_fingerprint, seed)`.

* `6A.S2.SEALED_INPUTS_MISSING_REQUIRED`
  *Meaning:* One or more artefacts that S2 considers **required** (e.g. product-mix priors, account taxonomy, linkage rules) do not appear in `sealed_inputs_6A` for this world.

* `6A.S2.SEALED_INPUTS_SCOPE_INVALID`
  *Meaning:* A required artefact appears in `sealed_inputs_6A` but with incompatible `status` or `read_scope` (e.g. `status="IGNORED"` or `read_scope="METADATA_ONLY"` where S2 needs `ROW_LEVEL`).

All imply: **“S2 cannot even start; the input universe or upstream gate is not valid.”**

---

#### 9.2.2 Priors, taxonomies & linkage rules errors

These indicate S2’s own priors and taxonomies are not usable.

* `6A.S2.PRIOR_PACK_MISSING`
  *Meaning:* A required S2 prior/config artefact (product mix, account-per-party priors, or linkage rule pack) referenced in `sealed_inputs_6A` cannot be resolved for this `mf` / `ph`.

* `6A.S2.PRIOR_PACK_INVALID`
  *Meaning:* A required prior/config artefact exists but fails validation against its `schema_ref` (bad structure, missing required fields, type errors).

* `6A.S2.PRIOR_PACK_DIGEST_MISMATCH`
  *Meaning:* The SHA-256 digest computed from a prior/config artefact does not match `sha256_hex` in `sealed_inputs_6A` (and/or the registry).

* `6A.S2.TAXONOMY_MISSING_OR_INVALID`
  *Meaning:* A required taxonomy (e.g. account types, product families, risk tiers, account-level enums) is missing or invalid (schema error or missing required values).

* `6A.S2.LINKAGE_RULES_MISSING_OR_INVALID`
  *Meaning:* Product linkage / eligibility rules required by S2 are missing, invalid, or self-contradictory (e.g. no allowed products for a cell with non-zero party count).

These all mean: **“S2 doesn’t know what products can exist or who may own them.”**

---

#### 9.2.3 Target derivation & integerisation errors

These indicate S2 cannot derive a consistent account plan from priors.

* `6A.S2.ACCOUNT_TARGETS_INCONSISTENT`
  *Meaning:* Continuous target counts `N_acc_target(c)` per cell are inconsistent or ill-formed, e.g.:

  * negative or NaN/Inf values,
  * sums across cells wildly out of sync with priors or configured global constraints,
  * cells required by priors are missing from the domain.

* `6A.S2.ACCOUNT_INTEGERISATION_FAILED`
  *Meaning:* Integerisation of targets to `N_acc(c)` fails to satisfy constraints, e.g.:

  * some `N_acc(c) < 0`,
  * conservation broken at required group levels (e.g. per region+account_type),
  * global integer total does not match target within allowed bounds.

* `6A.S2.ACCOUNT_POPULATION_ZERO_WHEN_DISALLOWED`
  *(Optional but recommended)*
  *Meaning:* Priors/configs indicate that certain cells or regions **must not** have zero accounts (e.g. `min_accounts_per_cell > 0`), but integerisation yields `N_acc(c) = 0` for such cells.

These codes mean: **“We can’t produce a sane account count plan from the inputs; any base table built on top would be invalid.”**

---

#### 9.2.4 Base-table & linkage errors

These indicate the materialised S2 datasets are inconsistent with the plan, with upstream entities, or with taxonomies.

* `6A.S2.ACCOUNT_BASE_SCHEMA_OR_KEY_INVALID`
  *Meaning:* `s2_account_base_6A` exists but:

  * fails validation against `schemas.6A.yaml#/s2/account_base`, or
  * violates the PK/uniqueness constraint `(manifest_fingerprint, seed, account_id)`.

* `6A.S2.ACCOUNT_COUNTS_MISMATCH`
  *Meaning:* When aggregating `s2_account_base_6A`:

  * counts per account cell do not match the realised integer plan `N_acc(c)`, and/or
  * the total number of base rows does not equal the summed integer counts.

* `6A.S2.ORPHAN_ACCOUNT_OWNER`
  *Meaning:* One or more accounts reference owners that don’t exist:

  * `owner_party_id` not found in `s1_party_base_6A` for `(mf, seed)`, or
  * `owner_merchant_id` not found in the upstream merchant universe.

* `6A.S2.LINKAGE_RULE_VIOLATION`
  *Meaning:* Account-owner relationships in the base table violate eligibility/linkage rules, e.g.:

  * retail-only products assigned to business-only segments (or vice versa),
  * accounts allocated to disallowed regions,
  * per-party/per-merchant account caps violated where they were specified as hard constraints.

* `6A.S2.TAXONOMY_COMPATIBILITY_FAILED`
  *Meaning:* Account base emits codes that are inconsistent with taxonomies, e.g.:

  * `account_type`, `product_family`, `currency_iso`, `region_id` or similar fields contain unknown values,
  * combinations that violate compatibility rules (e.g. a currency not allowed in a region, or an account_type not allowed for a party_type).

* `6A.S2.HOLDINGS_INCONSISTENT_WITH_BASE`
  *Meaning:* `s2_party_product_holdings_6A` does not match `s2_account_base_6A`, e.g.:

  * `account_count` per party/group doesn’t equal the number of base-table accounts in that group,
  * total holdings counts don’t sum to total base accounts.

* `6A.S2.SUMMARY_INCONSISTENT_WITH_BASE`
  *Meaning:* If `s2_account_summary_6A` is implemented, its `account_count` fields do not match aggregated counts from the base table.

All of these mean: **“The concrete account datasets are internally faulty; S2 is not a valid account universe.”**

---

#### 9.2.5 RNG & accounting errors

These indicate the randomness in S2 **cannot be trusted or audited**.

* `6A.S2.RNG_ACCOUNTING_MISMATCH`
  *Meaning:* Aggregate RNG metrics for S2 families (`account_count_realisation`, `account_allocation_sampling`, `account_attribute_sampling`) do not reconcile with expectations, e.g.:

  * missing or extra RNG events,
  * overlapping or out-of-order Philox counters,
  * total draws/blocks outside configured budgets.

* `6A.S2.RNG_STREAM_CONFIG_INVALID`
  *Meaning:* S2’s RNG configuration is inconsistent with the Layer-3 envelope, e.g.:

  * unregistered substream labels,
  * conflicting or reused substream keys,
  * misalignment between RNG event schemas and the envelope.

These errors mean: **“We cannot reliably reproduce or audit S2’s random choices; the run is not trustworthy.”**

---

#### 9.2.6 IO / identity / internal errors

These indicate storage or generic runtime failures.

* `6A.S2.IO_READ_FAILED`
  *Meaning:* S2 could not read a required artefact (priors, taxonomies, S0/S1 outputs, catalogue files) because of IO issues (permissions, network, corruption), despite the catalogue claiming it exists.

* `6A.S2.IO_WRITE_FAILED`
  *Meaning:* S2 attempted to write `s2_account_base_6A`, holdings, or optional views, and the write failed to complete atomically/durably.

* `6A.S2.OUTPUT_CONFLICT`
  *Meaning:* For a given `(mf, seed)`, outputs for S2 already exist and are **not** byte-identical to what S2 would produce from the current inputs (violating replace-not-append / idempotency). S2 must not silently overwrite.

* `6A.S2.INTERNAL_ERROR`
  *Meaning:* A non-classified, unexpected internal error occurred (e.g. assertion failure, unhandled exception) that doesn’t map cleanly to any code above. This should be treated as an implementation bug.

These errors mean: **“This S2 run failed structurally; treat its outputs as unusable for this `(mf, seed)`.”**

---

### 9.3 Mapping detection → error code

Implementations **must** map detected conditions to these codes deterministically. Examples:

* S0 or S1 gate fails → `6A.S2.S0_OR_S1_GATE_FAILED`.
* A required product-mix prior missing from `sealed_inputs_6A` → `6A.S2.SEALED_INPUTS_MISSING_REQUIRED`.
* Required prior present but schema-invalid → `6A.S2.PRIOR_PACK_INVALID`.
* Account type taxonomy missing → `6A.S2.TAXONOMY_MISSING_OR_INVALID`.
* Continuous targets contain NaNs or negative values → `6A.S2.ACCOUNT_TARGETS_INCONSISTENT`.
* Integerisation gives negative or non-conserving counts → `6A.S2.ACCOUNT_INTEGERISATION_FAILED`.
* An account points to a non-existent `party_id` → `6A.S2.ORPHAN_ACCOUNT_OWNER`.
* Retail-only account type allocated to a business-only segment where linkage rules forbid it → `6A.S2.LINKAGE_RULE_VIOLATION`.
* Base table fails schema or PK check → `6A.S2.ACCOUNT_BASE_SCHEMA_OR_KEY_INVALID`.
* Holdings counts don’t match the base → `6A.S2.HOLDINGS_INCONSISTENT_WITH_BASE`.
* RNG trace doesn’t match expected event/draw counts → `6A.S2.RNG_ACCOUNTING_MISMATCH`.
* Attempt to overwrite an existing different S2 output → `6A.S2.OUTPUT_CONFLICT`.

If no specific code fits, implementations must use `6A.S2.INTERNAL_ERROR` and the spec should be updated later, rather than inventing ad-hoc codes.

---

### 9.4 Run-report integration & propagation

On every S2 run for `(manifest_fingerprint, seed)`, the run-report record **must** include:

* `state_id = "6A.S2"`
* `manifest_fingerprint`, `parameter_hash`, `seed`
* `status ∈ {"PASS","FAIL"}`
* `error_code` (empty/null if PASS; one of the `6A.S2.*` codes if FAIL)
* `error_message` (short human-readable description; non-normative)

On **FAIL**, S2:

* MUST NOT mark the account universe as usable,
* MUST NOT be treated as gating-success by S3–S5 or 6B, even if partial datasets exist.

Downstream S3–S5 and 6B **must**:

* check S2’s run-report for `(mf, seed)` before consuming S2 outputs,
* refuse to proceed if `status != "PASS"` or `error_code` is non-empty.

The error codes in this section are the **primary machine-readable signal** of S2’s failure reasons.
Logs and stack traces are for debugging only and are not part of the contract.

---

## 10. Observability & run-report integration *(Binding)*

6A.S2 is a **core modelling state**: it defines the entire account/product universe for each `(manifest_fingerprint, seed)`. Its health and outputs must be **explicitly visible** via a run-report record, and downstream states must gate on that record rather than guessing from file presence.

This section fixes **what S2 must report**, how it is **keyed**, and how **downstream components must use it**.

---

### 10.1 Run-report record for 6A.S2

For every attempted S2 run on a `(manifest_fingerprint, seed)`, the engine **MUST** emit exactly one run-report record with at least:

#### Identity

* `state_id = "6A.S2"`
* `manifest_fingerprint`
* `parameter_hash`
* `seed`
* `engine_version`
* `spec_version_6A` (including S2’s effective spec version)

#### Execution envelope

* `run_id` (execution identifier; non-semantic)
* `started_utc` (RFC 3339, micros)
* `completed_utc` (RFC 3339, micros)
* `duration_ms` (derived)

#### Status & error

* `status ∈ { "PASS", "FAIL" }`
* `error_code` (empty/null for PASS; one of the `6A.S2.*` codes for FAIL)
* `error_message` (short human-readable description; non-normative)

#### Core account metrics

For a PASS run these fields are **binding** (must be consistent with the datasets):

* `total_accounts` — total number of rows in `s2_account_base_6A` for `(mf, seed)`.
* `accounts_by_type` — map/array summarising counts per `account_type`.
* `accounts_by_product_family` — optional; counts per `product_family`.
* `accounts_by_region` — counts per region/country (using whatever geography grain S2 uses).
* `accounts_by_segment` — counts by party segment (derived by joining to `s1_party_base_6A`).

#### Distribution metrics

To give a quick view of how concentrated holdings are:

* `accounts_per_party_min` / `accounts_per_party_max`
* `accounts_per_party_mean`
* `accounts_per_party_pXX` — selected percentiles (e.g. p50, p90, p99).
* Optional: analogous metrics for accounts per merchant (if merchant accounts exist).

#### RNG metrics

Per RNG family S2 uses:

* `rng_account_count_events`, `rng_account_count_draws`
* `rng_account_allocation_events`, `rng_account_allocation_draws`
* `rng_account_attribute_events`, `rng_account_attribute_draws`

These must reconcile with the RNG envelope/trace logs (see §8.1.6).

---

### 10.2 PASS vs FAIL semantics in the run-report

For a **PASS** S2 run on `(manifest_fingerprint, seed)`:

* `status == "PASS"`
* `error_code` is empty or null.
* `total_accounts`, `accounts_by_*` and distribution metrics **MUST** agree with what you would compute directly from `s2_account_base_6A` (and `s1_party_base_6A` where applicable).

For a **FAIL** run:

* `status == "FAIL"`
* `error_code` is one of the `6A.S2.*` codes (see §9).
* `total_accounts` and other metrics may be omitted or set to sentinel values; they are *not* authoritative.
* Downstream states MUST NOT treat a FAIL record as “good enough” to proceed.

Implementations must not emit `status="PASS"` unless:

* the datasets described in §4 are present and valid, and
* all acceptance criteria in §8 are satisfied.

---

### 10.3 Relationship between run-report and S2 datasets

For a **PASS** S2 run on `(mf, seed)`:

* There **must exist** corresponding partitions of:

  * `s2_account_base_6A`,
  * `s2_party_product_holdings_6A`,
  * and optional S2 derived views (merchant base, summary if implemented),

  that:

  * validate against their schema anchors in `schemas.6A.yaml`, and
  * are consistent with the metrics in the run-report.

Concretely:

* `total_accounts == COUNT(*)` over `s2_account_base_6A` for `(mf, seed)`.
* `accounts_by_type` matches `GROUP BY account_type` counts on the base table.
* `accounts_by_region`, `accounts_by_segment` match the appropriate groupings (joining S1 where needed).
* `accounts_per_party_*` metrics correspond to aggregations of base accounts by `owner_party_id`.

For a **FAIL** run:

* S2 datasets **must not** be treated as valid, even if files exist.
* Orchestration may choose to delete/quarantine partial outputs, but downstream components must rely on the run-report `status` and `error_code`, not file presence, to decide.

---

### 10.4 Gating behaviour in downstream states

All downstream states that depend on S2 — i.e.:

* later 6A states (S3–S5),
* 6B (flows/fraud),
* and any external consumers of account/product data —

**MUST** incorporate S2’s run-report into their gating logic.

Before using S2 outputs for `(mf, seed)`, a downstream state MUST:

1. Locate the **latest** 6A.S2 run-report record for `(mf, seed)`.

2. Require:

   ```text
   status     == "PASS"
   error_code == "" or null
   ```

3. Confirm that:

   * `s2_account_base_6A` exists for `(mf, seed)` and validates against its schema,
   * `s2_party_product_holdings_6A` exists and validates,
   * `total_accounts` from the run-report matches `COUNT(*)` over `s2_account_base_6A`.

If any of these checks fails, the downstream state **must not**:

* read or rely on S2 account datasets for that `(mf, seed)`,
* proceed to attach instruments/devices/fraud roles or flows to accounts for that world+seed.

Instead, it must fail with a state-local gate error (e.g. `6A.S3.S2_GATE_FAILED`, `6B.S0.S2_GATE_FAILED`).

---

### 10.5 Additional observability (recommended, non-semantic)

While not binding for correctness, implementations **should** also:

* Record simple **distribution snapshots** per run (in logs or extended run-report fields), for example:

  * top N account types by count,
  * top N segments by average accounts per party,
  * histograms of accounts per party and accounts per merchant.

* At INFO level, log per-run:

  * `(manifest_fingerprint, seed, parameter_hash)`,
  * `status`, `error_code`,
  * `total_accounts`,
  * basic splits by type/segment/region.

* At DEBUG level, log:

  * regions or segments where realised concentrations deviate strongly from priors (useful for QA),
  * detailed RNG accounting diagnostics when investigating `RNG_ACCOUNTING_MISMATCH`.

These logs are for operations/debugging and **not part of the formal contract**; their format may evolve as long as the binding run-report fields remain consistent.

---

### 10.6 Integration with higher-level monitoring

Engine-level monitoring and dashboards **MUST** be able to summarise S2’s health across worlds and seeds. At minimum, they should expose:

* For each `manifest_fingerprint`:

  * S2 status per seed (PASS / FAIL / MISSING),
  * `total_accounts` per seed,
  * coarse breakdowns (accounts_by_type, accounts_by_segment, accounts_by_region).

* Cross-world views:

  * distribution of `total_accounts` across worlds/seeds,
  * counts of S2 failures by `error_code`,
  * correlation with upstream failures (e.g. clusters of S2 failures due to missing priors).

The aim is that, using only the observability surface, an operator can quickly answer:

> “For this world and seed, did we generate a valid account universe? How big is it, and how is it distributed?”

without manually querying the underlying S2 datasets.

These observability and run-report requirements are **binding** for S2’s contract with the rest of the engine.

---

## 11. Performance & scalability *(Informative)*

6A.S2 is the second big “data-plane” step in Layer-3: it can easily create **as many or more rows as S1**, depending on product density. This section is non-binding, but it describes how S2 is expected to scale and which levers you have to keep it practical.

---

### 11.1 Complexity profile

For a given `(manifest_fingerprint, seed)`:

Let:

* `P` = number of parties in `s1_party_base_6A`.
* `R` = number of regions/countries used in S2’s planning.
* `S` = number of segments.
* `T` = number of account types.
* `C_pop` = number of “population cells” used for accounts (e.g. `(region, party_type, segment)`).
* `C_acc` = number of **account cells** `(population cell, account_type)`.
* `A` = total number of accounts realised by S2 (`N_accounts_world_int`).

Then:

* **Phase 1 – load priors/taxonomies:**

  * O(C_pop + C_acc + size(prior tables)) — usually tiny compared to `P` and `A`.

* **Phase 2 – continuous targets:**

  * O(C_acc) — per-cell arithmetic.

* **Phase 3 – integerisation:**

  * O(C_acc) — plus RNG calls per region/world; still small compared to per-account work.

* **Phase 4 – allocation to parties/merchants:**

  * O(A) — account-level RNG + assignment logic.
  * You may also touch O(P) to build weight vectors per cell.

* **Phase 5 – account attributes:**

  * O(A × k) where `k` is number of attributes per account (constant).

* **Phase 6 – writing outputs & internal checks:**

  * O(A) to write the base table,
  * O(P × T’) to compute party holdings, where `T’` is number of account types or product families.

So, **S2 is essentially O(A + P)** in time; as with S1, the per-entity work dominates.

---

### 11.2 Expected sizes & regimes

You can think of S2 scale as “S1 scale × product density”:

* If S1 has:

  * `P ≈ 10⁶–10⁷` parties per `(mf, seed)`, and
  * average accounts per party ≈ 1–5,

* Then S2 will usually produce:

  * `A ≈ 10⁶–5×10⁷` accounts,
  * `|s2_party_product_holdings_6A| ≈ P × T_h`, where `T_h` is number of account types/families with non-zero holdings per party (typically small).

Optional views:

* `s2_merchant_account_base_6A` — subset of the base, often much smaller unless you have a merchant-heavy world.
* `s2_account_summary_6A` — on the order of `C_acc` (usually low hundreds or low thousands).

Compared to Layer-2:

* S2’s `A` will often be **smaller** than total arrivals in 5B but similar to or larger than `P`.
* S2 must therefore be engineered with similar care as S1/5B, but still remains small compared to “all events over a long horizon”.

---

### 11.3 Parallelism & sharding

S2 is highly parallelisable. Natural axes:

1. **Across seeds**

   * Each `(manifest_fingerprint, seed)` is hermetic — different account universes.
   * Safest primary sharding axis for horizontal scale.

2. **Across cells within a seed**

   * Integerisation and allocation phases can be parallelised by region or by account cell (`(region, party_type, segment, account_type)`):

     * Phase 2–3: plan integer counts per cell;
     * Phase 4–5: per-cell account generation and attribute sampling.

   * To preserve determinism, you typically:

     * fix a global ordering over cells,
     * derive RNG substream keys from that ordering,
     * ensure any parallel execution still respects the same substream allocation.

3. **Streaming/batched writes**

   * You don’t need all `A` rows in memory at once:

     * generate accounts per cell or per region in batches,
     * stream to columnar files in canonical order,
     * keep only a bounded batch in memory at any time.

As long as you maintain:

* canonical writer ordering, and
* deterministic mapping of RNG substreams to cells and attributes,

parallelisation doesn’t change semantics.

---

### 11.4 Memory & IO considerations

**Memory**

* Priors/taxonomies: small; keep fully in memory.
* Population/account plans (arrays of `N_acc_target(c)` and `N_acc(c)` over `C_acc`): also small.
* The heavy part (A accounts) should be **streamed**, not fully buffered.

Reasonable pattern:

* Build per-cell or per-region allocations, then:

  * generate accounts for one cell / batch at a time,
  * immediately write them out,
  * keep only a small window in memory.

This keeps memory ~O(size(priors) + size(plan) + batch_size), not O(A).

**IO**

* Reads:

  * S1 base (`s1_party_base_6A`) — accessed for owner weights; you can stream or chunk by region.
  * Priors/taxonomies — small; loaded once.
  * Optional context surfaces — moderate, but far smaller than data-plane flows.

* Writes:

  * dominated by `s2_account_base_6A`, which is O(A) rows,
  * plus smaller holdings/summary tables.

For large N, IO bandwidth is often more important than CPU; using compressed, columnar storage and decent batch sizes per row-group will help.

---

### 11.5 RNG cost & accounting

RNG cost is small compared to IO, but not negligible for huge A:

* Count realisation (`account_count_realisation`):

  * scales with `C_acc` (cells); typically tiny.

* Allocation & attributes:

  * scale with A and the number of attributes per account.
  * If you have M attributes, roughly O(A × M) uniform draws.

Design guidance:

* Use **vectorised** Philox generation where possible (e.g. per cell, per batch) while still:

  * obeying the envelope (correct `blocks`, `draws`),
  * maintaining deterministic counter/stream assignment per event.

* Use sparse RNG logs: one event per logically meaningful batch (e.g. per cell), not per account, as long as you can still reconcile totals.

Accounting is mostly about **auditability**:

* you want clean evidence that every RNG family stayed within budget and that there are no gaps/overlaps in counters.

---

### 11.6 Operational tuning knobs

To make S2 manageable across environments (dev, CI, staging, prod), you can expose **non-semantic** tuning knobs via priors/config (therefore reflected in `parameter_hash`):

* **Account density factor**

  * A scalar that scales expected accounts per party before integerisation (e.g. 0.1× for CI, 1× for production).
  * Since this changes behaviour, it must be encoded as part of the S2 priors and thus in `parameter_hash`; S2 itself remains deterministic for a given pack.

* **Maximum accounts per party / merchant**

  * Hard caps to avoid extreme outliers from tails of priors;
  * If caps are exceeded and no feasible allocation exists, S2 fails cleanly rather than generating absurdly dense holders.

* **Maximum accounts per `(mf, seed)`**

  * A global safety cap: if computed `N_acc_world_int` exceeds a configured threshold, S2 fails rather than overwhelming downstream resources.

* **Sharding configuration**

  * Optionally, a config that indicates preferred shard keys for parallel execution (e.g. region shards, or number of worker shards), used by the orchestrator.

All such knobs should live in the **sealed prior/config packs**, not as ad-hoc flags, so they’re properly captured in the S0 sealed input universe and S2’s `parameter_hash`.

---

### 11.7 Behaviour at scale & failure modes

Under high-volume settings (large `P` and `A`), you should expect:

* **Longer runtimes** roughly linear in A,
* Increased **pressure on IO** (account base writes) and metadata stores,
* More significant RNG traffic (especially if many attributes per account).

To keep S2 operable:

* Monitor S2’s run-report metrics (e.g. `total_accounts`, `accounts_by_type`, `accounts_per_party_*`) and set alert thresholds for suspiciously large or skewed populations.
* Use smaller `parameter_hash` variants (fewer parties or lower account density) in development/CI while keeping structure consistent.

In failure scenarios (e.g. misconfigured priors causing huge `N_acc_target(c)`):

* S2 should fail with a concise error (e.g. `ACCOUNT_TARGETS_INCONSISTENT`, `ACCOUNT_INTEGERISATION_FAILED`) rather than emit partial or absurd outputs.
* The run-report plus logs should make it obvious if the issue was:

  * unexpected scale,
  * mis-specified priors,
  * IO limits,
  * or RNG/accounting problems.

None of these performance notes change S2’s binding semantics. They’re here to help ensure that an implementation can handle realistic “bank-sized” worlds without turning S2 into the slowest or most fragile part of the engine.

---

## 12. Change control & compatibility *(Binding)*

This section fixes **how 6A.S2 is allowed to evolve** and what “compatible” means for:

* upstream segments (1A–3B, 5A–5B),
* upstream 6A states (S0, S1),
* downstream 6A states (S3–S5),
* 6B and any external consumers that rely on the **account universe**.

Any change that violates these rules is a **spec violation**, even if an implementation appears to “work” in a particular deployment.

---

### 12.1 Versioning model for S2

S2 participates in the 6A versioning stack:

* `spec_version_6A` — overall 6A spec version (S0–S5).

* `spec_version_6A_S2` — effective version identifier for the S2 portion of the spec.

* Schema versions:

  * `schemas.6A.yaml#/s2/account_base`,
  * `schemas.6A.yaml#/s2/party_product_holdings`,
  * `schemas.6A.yaml#/s2/merchant_account_base` *(if present)*,
  * `schemas.6A.yaml#/s2/account_summary` *(if present)*.

* Catalogue versions:

  * `dataset_dictionary.layer3.6A.yaml` entries for S2 datasets,
  * `artefact_registry_6A.yaml` entries with `produced_by: 6A.S2` and S2 priors/configs.

S2’s run-report MUST carry enough information (e.g. `spec_version_6A`, optional `spec_version_6A_S2`) so consumers can know which version of the S2 spec produced a given account universe.

---

### 12.2 Backwards-compatible changes (allowed within a major version)

The following changes are **backwards compatible**, provided all constraints in §§1–11 remain satisfied:

1. **Add optional fields to S2 outputs**

   * Adding new, *optional* columns to:

     * `s2_account_base_6A`,
     * `s2_party_product_holdings_6A`,
     * optional S2 views,

     without changing the meaning of existing fields.

   * Examples: new static flags (`eligible_for_new_feature`), additional diagnostic tags, additional banded attributes.

   * Existing consumers can safely ignore unknown columns.

2. **Extend taxonomies**

   * Adding new values to account/product taxonomies (new `account_type`, `product_family`, `account_risk_tier`, etc.) that:

     * obey the existing type system,
     * do not repurpose existing values.

   * Consumers should be robust to unknown enum values (e.g. treat them as generic types until upgraded).

3. **Refine priors numerically (same semantics)**

   * Changing numeric values in priors (e.g. `λ_acc_per_party`, cell weights) while **keeping the same structure and interpretation** is allowed:

     * this changes realised distributions (how many accounts per party, etc.),
     * but not the meaning of fields or S2’s identity rules.

4. **Add new S2 diagnostics or optional views**

   * Adding new **optional** datasets (diagnostics, QA reports) that are clearly marked `status: optional` in the dictionary and registry and do not affect S2’s acceptance criteria.

5. **Performance/implementation optimisations**

   * Any change that alters how S2 is implemented (caching, parallelism, streaming) but not:

     * the contents of S2 outputs,
     * the RNG family semantics, or
     * run-report semantics,

   is backwards compatible.

Within a given **major** `spec_version_6A`, consumers must assume such changes may occur and must tolerate unknown columns and taxonomies.

---

### 12.3 Soft-breaking changes (require coordination, but can be staged)

These changes can be kept compatible with care, but require **coordination** between producers and consumers and should be accompanied by a **spec/minor version bump** and explicit migration notes.

1. **New required account attributes**

   * Making a new field in `s2_account_base_6A` **required** (e.g. introducing `account_risk_tier` as mandatory) is only safe if:

     * consumers are updated to understand it, or
     * the field is introduced in two stages:

       1. Added as optional,
       2. After all consumers have been updated, promoted to required.

2. **New hard constraints in priors/linkage rules**

   * Introducing new **hard** constraints (e.g. new max/min accounts per party, new disallowed combinations) that S2 must enforce:

     * S2 should update its error codes and run-report to highlight such failures,
     * downstream may need to adapt to more “strict” populations (e.g. fewer high-risk accounts than before).

3. **New priors that change account density dramatically**

   * Introducing priors that change the *scale* (e.g. more products per party) can be soft-breaking for resource usage, even if the schema remains valid.
   * Should be accompanied by guidance for downstream components, and may require capacity updates.

4. **New S2 base datasets for specific account subtypes**

   * If you split the account base into multiple base tables (e.g. strongly separated “consumer” and “business” account bases), you must:

     * declare them as additional required datasets,
     * ensure consumers understand how to join across them,
     * and plan for a staged introduction.

Soft-breaking changes should bump **minor** `spec_version_6A` / `spec_version_6A_S2` and require downstream code to check versions explicitly where necessary.

---

### 12.4 Breaking changes (require major version bump)

The following are **breaking changes** and must not be introduced without:

* a major bump to `spec_version_6A` / `spec_version_6A_S2`,
* updated schemas/dictionaries/registries, and
* explicit migration guidance for all S2 consumers.

1. **Changing identity or partitioning**

   * Modifying the S2 primary key semantics (e.g. dropping `seed` or `manifest_fingerprint` from the PK, or changing `account_id` uniqueness rules).
   * Changing S2 partitioning (e.g. removing `seed` or adding `scenario_id` as a partition key).
   * Renaming `account_id` or reusing that field for something else.

2. **Changing semantics of core fields**

   * Reinterpreting:

     * `account_type`,
     * `product_family`,
     * `owner_party_id`, `owner_merchant_id`,
     * `currency_iso`, `country_iso` / `region_id`,

     in ways that change business meaning.

   * Reusing existing enum values for completely different products or account roles.

3. **Changing the account generation law**

   * Changing the *class* of law that maps priors → integer counts → allocation to parties in ways that violate downstream assumptions:

     * e.g. previously scenario-independent account universe becoming scenario-dependent,
     * previously one account base per `(mf, seed)` becoming multiple overlapping bases.

   * Changing the **RNG family mapping** (e.g. turning `account_count_realisation` into a different random operation with different distributional behaviour) is also behavioural and must be treated as breaking.

4. **Changing how S2 relates to S1/S0**

   * Weakening the dependence on S1 (e.g. allowing accounts with no parties),
   * Changing gating from S0/S1 such that S2 can run in partially sealed worlds.

5. **Removing required datasets**

   * Downgrading `s2_account_base_6A` or `s2_party_product_holdings_6A` from `status: required` to `status: optional`
   * Or removing them outright in favour of different datasets.

6. **Changing acceptance/gating semantics**

   * Changing PASS conditions in §8 in a way that:

     * makes previously failing worlds count as PASS (without tightening tests elsewhere), or
     * makes previously PASS worlds systematically FAIL due solely to a spec change (not a bug fix).

Any of these changes must be treated as a **major version** change, and downstream (S3–S5, 6B) must explicitly support the new version before consuming those worlds.

---

### 12.5 Compatibility obligations for downstream states

Downstream 6A states and 6B have responsibilities under this spec:

1. **Version pinning**

   * Each downstream state (S3, S4, S5, 6B) MUST declare a **minimum supported S2 spec version** / `spec_version_6A_S2`, and:

     * read S2’s run-report,
     * fail fast if the S2 spec version for a given `(mf, seed)` is outside the supported range.

2. **Ignore unknown fields gracefully**

   * Within a supported major version, downstream code MUST:

     * ignore additional fields in S2 outputs that it doesn’t understand,
     * avoid strict “column equality” checks that break when optional fields are added.

3. **Do not hard-wire layout**

   * Downstream logic MUST:

     * resolve S2 datasets through the dictionary/registry and `schema_ref`,
     * not assume specific path strings beyond the tokenised templates,
     * not assume a particular file layout within partitions.

4. **Do not re-encode or override S2 semantics**

   * Downstream specs or code MUST NOT redefine:

     * what `account_type`, `product_family`, `owner_party_id`, `owner_merchant_id` mean,
     * how accounts are associated with parties/merchants.

   * They must treat S2 outputs as **authoritative** on account identity and ownership.

---

### 12.6 Migration & co-existence strategy

When a **breaking S2 change** is introduced:

* It MUST be released as a new **major** `spec_version_6A` / `spec_version_6A_S2`.
* Worlds may be tagged in the catalogue or run-report with the S2 spec version used to generate them.

In environments that need to support **multiple S2 versions concurrently**:

* Orchestration may:

  * route different worlds to different pipelines based on spec version,
  * allow some downstream states to support multiple S2 versions in “dual-mode”, or
  * restrict certain downstream features to worlds with a minimum S2 version.

S2 itself MUST remain internally consistent per world:

* A single `(manifest_fingerprint, seed)` MUST NOT be populated by two different S2 spec versions.

---

### 12.7 Non-goals

This section does **not**:

* version or constrain upstream segments (1A–3B, 5A–5B) — they have their own specs,
* define how often priors are updated (that’s a modelling choice),
* dictate CI/CD or branching strategies.

It **does** require that:

* any change to S2 that affects observable behaviour is explicitly versioned,
* downstream components **never** assume compatibility without checking versions,
* and any change that touches identity, schema, account-generation law, or gating semantics is treated as a deliberate, coordinated spec evolution — **not** as an implementation detail.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the short-hands and symbols used in **6A.S2**.
If anything here seems to contradict the binding sections (§1–§12), the binding sections (and the JSON-Schemas) win.

---

### 13.1 Identity axes

* **`mf`**
  Shorthand for **`manifest_fingerprint`**.
  Identifies the sealed upstream world (L1+L2) and the 6A input universe for S0/S1/S2.

* **`ph`**
  Shorthand for **`parameter_hash`**.
  Identifies the parameter / prior pack set (S2 priors: product mix, linkage rules, account attributes, etc.).

* **`seed`**
  RNG identity for S2 (and Layer-3 more broadly).
  Different seeds under the same `(mf, ph)` correspond to different population + account universes.

* **`party_id`**
  Stable identifier for a party/customer within `(mf, seed)`, created by S1.
  S2 must treat `(mf, seed, party_id)` as **foreign key** into `s1_party_base_6A`.

* **`account_id`**
  Stable identifier for an account within `(mf, seed)`, created by S2.
  S2 guarantees uniqueness of `(mf, seed, account_id)`.

* **`owner_party_id`**, **`owner_merchant_id`**
  References linking accounts to parties (S1) and merchants (L1).
  Together define the ownership topology S2 is responsible for.

---

### 13.2 Population / cell notation for S2

Let:

* **`R`** — set of regions or countries used by S2 (e.g. `country_iso` or `region_id`).
* **`T_party`** — set of party types (e.g. `RETAIL`, `BUSINESS`, `OTHER`).
* **`S_seg`** — set of segments (e.g. `STUDENT`, `SALARIED`, `SME`, `CORPORATE`, …).
* **`T_acc`** — set of account types (e.g. `CURRENT_ACCOUNT`, `SAVINGS_ACCOUNT`, `CREDIT_CARD`, `LOAN`, `MERCHANT_SETTLEMENT`, etc.).

We use:

* **Base “population cell”** (from S1):

  ```text
  b ∈ B ≔ (region_id, party_type, segment_id)
  ```

* **Account planning cell**:

  ```text
  c ∈ C_acc ≔ (region_id, party_type, segment_id, account_type)
  ```

Core quantities:

* **`N_party(b)`**
  Number of parties in base cell `b` (derived from `s1_party_base_6A`).

* **`λ_acc_per_party(c)`**
  Expected number of accounts of type `account_type` (the last component of `c`) per party in cell `b`.

* **`N_acc_target(c)`**
  Continuous (real-valued) target number of accounts in cell `c`:

  ```text
  N_acc_target(c) = N_party(b) × λ_acc_per_party(c) × s_context(c)
  ```

  where `s_context(c)` is an optional deterministic scaling factor from context surfaces.

* **`N_acc(c)`**
  Realised integer number of accounts in cell `c` after integerisation.

* **`N_acc_world_int`**
  Total realised accounts in the world:

  ```text
  N_acc_world_int = Σ_c N_acc(c)
  ```

---

### 13.3 Taxonomy & attribute symbols

Symbols for classification and attributes (names indicative):

* **`account_type`**
  Enum code describing the **type of account**, from the S2 account taxonomy.

* **`product_family`**
  Coarser grouping of products/accounts (e.g. consumer vs business, premium vs standard).

* **`account_risk_tier`**
  Enum capturing static account-level risk classification (e.g. `STANDARD`, `HIGH_RISK`, `PREMIUM`), if modelled at S2.

* **`currency_iso`**
  ISO 4217 currency code assigned to an account.

* **`country_iso` / `region_id`**
  Geographic classification for the account (home country/region), often derived from party or merchant location or product definition.

* **Static account attributes** (examples):

  * `overdraft_enabled` — boolean flag indicating overdraft facility.
  * `credit_limit_band` — banded representation of credit limit (not raw numeric).
  * `channel_profile` — enum describing “intended” high-level usage (e.g. `BRANCH_HEAVY`, `MOBILE_FIRST`).
  * eligibility flags (e.g. `eligible_for_overdraft`, `eligible_for_loans`).

All of these are **static** from S2’s perspective: later states read them as context and must not change them.

---

### 13.4 Priors, linkage & holdings notation

* **`π_account_type|cell(c, t)`**
  Fractional share (prior) for account type `t` within a population cell (sometimes folded into `λ_acc_per_party(c)`).

* **Account-per-party distribution**
  Distribution (per prior packs) describing `P(k accounts of type t | cell b)` for each party.
  Used to create party-level weights for allocation.

* **`n_accounts(p, t)`**
  Realised number of accounts of type `t` assigned to party `p` in a given cell.
  Satisfies:

  ```text
  Σ_p n_accounts(p, t) == N_acc(c)   for the corresponding cell c
  ```

* **`account_count(p, group)`**
  Count of accounts for a party `p` in `s2_party_product_holdings_6A` for a given grouping key (e.g. per `account_type`).

* **Linkage rules**
  Configs that constrain which (party_type, segment, region) can own which `account_type` or `product_family`, and any min/max per party or merchant.

---

### 13.5 Roles, statuses & scopes in `sealed_inputs_6A` (S2-relevant)

From `sealed_inputs_6A`:

* **`role`** (S2 cares about):

  * `PRODUCT_PRIOR` - product-mix and account-per-party priors.
  * `PRODUCT_LINKAGE_RULES` - eligibility/linkage configuration (contract id: `product_linkage_rules_6A`).
  * `PRODUCT_ELIGIBILITY_CONFIG` - eligibility config (contract id: `product_eligibility_config_6A`).
  * `TAXONOMY` — account/product taxonomies, risk tiers, etc.
  * `UPSTREAM_EGRESS` — upstream context surfaces (geo, economic indicators) used as hints.
  * `SCENARIO_CONFIG` — optional scenario/volume context from 5A/5B.
  * `CONTRACT` — schema/dictionary/registry artefacts (metadata only).

* **`status`**:

  * `REQUIRED` — S2 cannot run without this artefact.
  * `OPTIONAL` — S2 can branch behaviour based on presence/absence.
  * `IGNORED` — S2 must not use this artefact.

* **`read_scope`**:

  * `ROW_LEVEL` — S2 may read rows for data logic.
  * `METADATA_ONLY` — S2 may only use existence, schema, and digest.

S2’s effective input universe is the intersection of `{REQUIRED, OPTIONAL}` and `ROW_LEVEL` (for data); `METADATA_ONLY` inputs are for contracts/catalogue checks only.

---

### 13.6 RNG symbols for S2

S2 uses the Layer-3 Philox envelope; these names refer to logical RNG families:

* **`account_count_realisation`** (contract id: `rng_event_account_count_realisation`; substream_label: `account_count_realisation`)
  RNG family used when turning continuous targets `N_acc_target(c)` into integer counts `N_acc(c)` per cell.

* **`account_allocation_sampling`** (contract id: `rng_event_account_allocation_sampling`; substream_label: `account_allocation_sampling`)
  RNG family used to allocate accounts to parties (and merchants), given the integer plan.

* **`account_attribute_sampling`** (contract id: `rng_event_account_attribute_sampling`; substream_label: `account_attribute_sampling`)
  RNG family used to sample account-level attributes (currency, risk tier, channel profile, flags) from conditional priors.

* **`rng_event_account_count_realisation`**, **`rng_event_account_allocation_sampling`**, **`rng_event_account_attribute_sampling`**
  Logical event types in RNG logs that record:

  * context (mf, seed, cell, attribute family),
  * `counter_before` / `counter_after`,
  * `blocks`, `draws`,
  * optional summary stats.

All RNG is counter-based (Philox-2x64-10), and per-event counter evolution is determined by the substream derivation from `(mf, seed, "6A.S2", substream_label, context)`.

---

### 13.7 Miscellaneous shorthand & conventions

* **“World”**
  As in S0/S1: shorthand for “everything tied to one `manifest_fingerprint`”.

* **“Account universe”**
  The set of all rows in `s2_account_base_6A` for a given `(mf, seed)` — the complete set of accounts/products that exist in that world+seed.

* **“Holdings”**
  Shorthand for `s2_party_product_holdings_6A` (and any equivalent merchant holdings views): per-entity, per-product-type aggregates of account ownership.

* **“Cell”**
  When used without qualification in S2, typically refers to an account planning cell `c = (region, party_type, segment, account_type)`.

* **Conservation**
  Used informally for “integer counts match targets and aggregations”: e.g. sum of `N_acc(c)` equals `N_acc_world_int`, and `s2_account_base_6A` plus holdings/summary all reflect the same counts.

This appendix is **informative** only; it exists to make the S2 spec easier to read and to keep notation consistent across 6A.

---
