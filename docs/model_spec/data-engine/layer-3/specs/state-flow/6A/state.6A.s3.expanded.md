# 6A.S3 — Instruments & payment credentials (Layer-3 / Segment 6A)

## 1. Purpose & scope *(Binding)*

6A.S3 is the **instrument & payment-credential realisation state** for Layer-3 / Segment 6A.
Its job is to take the **account universe** from S2 (and the party universe from S1) and turn it into a **closed-world instrument universe** for each `(manifest_fingerprint, seed)`.

Concretely, S3 must:

* Create the set of **instruments/credentials** that exist in the synthetic bank, such as:

  * card-like instruments (debit/credit cards, virtual cards, stored-card tokens),
  * bank-transfer handles (IBAN-like identifiers, sort-code/account-number pairs, routing numbers),
  * wallet IDs / payment handles,
  * any other static payment credentials the bank would hold.
* Attach each instrument to:

  * a **primary account** (`account_id` from S2), and
  * by extension, a **party** (`party_id` from S1), and optionally a **merchant** (for merchant-centric instruments, if modelled).
* Assign **static instrument metadata**, for example:

  * instrument type (`CARD`, `BANK_TRANSFER_HANDLE`, `WALLET_ID`, …),
  * scheme/network (`VISA`, `MASTERCARD`, local schemes, bank transfer networks),
  * brand/tier (e.g. `PLATINUM`, `BUSINESS`),
  * masked identifier fields (PAN-like masks, IBAN-like masks, token IDs),
  * expiry profiles (e.g. month/year) and simple static flags (e.g. `contactless_enabled`, `virtual_only`).

Within 6A, S3 is the **sole authority** on:

* **Instrument existence** — which instruments/credentials exist for a given `(manifest_fingerprint, seed)`, and in what quantity per segment/region/product.
* **Instrument ownership topology** — which accounts and parties each instrument belongs to at initialisation (and, where relevant, which merchants).
* **Static instrument attributes** — type, scheme, brand, masked identifiers, expiry, and any other static properties that do not change over time.

S3’s scope is intentionally **narrow and upstream-respecting**:

* S3 **does not**:

  * create or modify parties (that is 6A.S1’s responsibility),
  * create or modify accounts/products (that is 6A.S2’s responsibility),
  * create devices, IPs, or network graph edges (those belong to a later 6A state, e.g. S4),
  * attach instruments to individual arrivals or flows, decide which instrument is used for a particular authorisation, or simulate transaction patterns (all of that belongs to 6B),
  * assign fraud roles or dynamic risk signals (that is reserved for the fraud posture / flows states).

* S3 **must not** change or reinterpret upstream constructs:

  * merchants, sites, geo, time zones, routing, and virtual overlay remain under 1A–3B,
  * intensities and arrivals remain under 5A–5B,
  * party and account identities/attributes remain under S1 and S2.

Within Layer-3, S3 sits **downstream of S0, S1 and S2**:

* It only runs for worlds where:

  * S0 has sealed the input universe (`sealed_inputs_6A` + `s0_gate_receipt_6A` PASS), and
  * S1 and S2 are PASS for the same `(manifest_fingerprint, seed)` and have produced a consistent party and account universe.
* It uses the **instrument mix priors**, **instrument taxonomies**, and **linkage rules** sealed by S0 to:

  * decide how many instruments should exist per account cell (e.g. per `(region, party_type, segment, account_type)`), and
  * allocate those instruments to specific accounts and parties in a way that respects eligibility and max/min constraints.

All later 6A states (e.g. device/IP graph, fraud posture) and 6B’s flow/fraud logic must treat S3’s instrument base as **read-only ground truth** for:

> “which instruments/credentials exist, and which accounts/parties they belong to”

within the synthetic bank for that `(manifest_fingerprint, seed)`.

---

## 2. Preconditions, upstream gates & sealed inputs *(Binding)*

6A.S3 only runs where **Layer-1, Layer-2, 6A.S0, 6A.S1 and 6A.S2 are already sealed** for the relevant world and seed. This section fixes those preconditions and the **minimum sealed inputs** S3 expects to see.

---

### 2.1 World-level preconditions (Layer-1 & Layer-2)

For a given `manifest_fingerprint` that S3 will serve, the engine MUST already have:

* Successfully run all required upstream segments:

  * Layer-1: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.
  * Layer-2: `5A`, `5B`.

* Successfully verified their HashGates (validation bundles + PASS flags), as recorded by 6A.S0.

S3 **does not** re-implement upstream HashGate logic. It **trusts S0’s view** via `s0_gate_receipt_6A`:

* For this `manifest_fingerprint`, every required segment in `upstream_gates` MUST have:

  ```text
  gate_status == "PASS"
  ```

If any required segment has `gate_status ∈ {"FAIL","MISSING"}`, S3 MUST treat the world as **not eligible** and fail fast with a gate error (e.g. `6A.S3.S0_S1_S2_GATE_FAILED`).

---

### 2.2 6A.S0 preconditions (gate & sealed inputs)

S3 is not allowed to run unless the **6A.S0 gate is fully satisfied**.

For the target `manifest_fingerprint`, S3 MUST:

1. **Validate S0 artefacts**

   * Confirm `s0_gate_receipt_6A` and `sealed_inputs_6A` exist under the correct `fingerprint={manifest_fingerprint}` partitions.
   * Validate both against their schema anchors in `schemas.layer3.yaml`:

     * `#/gate/6A/s0_gate_receipt_6A`
     * `#/gate/6A/sealed_inputs_6A`.

2. **Verify sealed-inputs digest**

   * Recompute `sealed_inputs_digest_6A` from `sealed_inputs_6A` using the canonical row encoding + ordering defined in S0.
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

If any of these checks fails, S3 MUST NOT attempt to read priors or generate any instruments for that world and MUST fail with a S0/inputs gate error.

---

### 2.3 6A.S1 and 6A.S2 preconditions (party & account gates)

S3 sits directly downstream of S1 and S2. For each `(manifest_fingerprint, seed)` S3 will process, it MUST ensure that:

1. **S1 is PASS for this `(mf, seed)`**

   * Locate the latest 6A.S1 run-report for `(mf, seed)` and require:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

   * Resolve `s1_party_base_6A` for `(seed={seed}, fingerprint={mf})` via the catalogue and:

     * validate it against `schemas.6A.yaml#/s1/party_base`,
     * verify that `COUNT(*)` equals `total_parties` in the S1 run-report.

2. **S2 is PASS for this `(mf, seed)`**

   * Locate the latest 6A.S2 run-report for `(mf, seed)` and require:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

   * Resolve `s2_account_base_6A` and `s2_party_product_holdings_6A` for `(seed={seed}, fingerprint={mf})` and:

     * validate them against their schemas (`#/s2/account_base`, `#/s2/party_product_holdings`),
     * verify that `COUNT(*)` for the account base equals `total_accounts` in the S2 run-report.

If S1 or S2 is missing or not PASS for `(mf, seed)`, S3 MUST fail with `6A.S3.S0_S1_S2_GATE_FAILED` and MUST NOT create any instruments for that world+seed.

---

### 2.4 Required sealed inputs for S3

S3 may only read artefacts that appear in `sealed_inputs_6A` (for its `manifest_fingerprint`) and have:

* `status ∈ {"REQUIRED","OPTIONAL"}`, and
* `read_scope = "ROW_LEVEL"` for data-level logic, or
* `read_scope = "METADATA_ONLY"` where only presence/shape is consulted.

Among those, S3 requires at minimum:

#### 2.4.1 Instrument mix priors & per-account priors

Artefacts with `role = "PRODUCT_PRIOR"` (or an S3-specific role such as `"INSTRUMENT_PRIOR"`) that provide:

* **Instrument mix priors**:

  * expected number of instruments per account cell, where a cell might be `(region, party_type, segment, account_type)` or similar,
  * splits across instrument types for each cell (e.g. debit vs credit vs virtual card).

* **Instruments-per-account distributions**:

  * discrete distributions for “how many instruments of type X does an account in cell c tend to have”
    (including zero-inflated and bounded distributions, where configured).

These priors MUST be present as row-level tables and MUST be marked:

```text
status     == "REQUIRED"
read_scope == "ROW_LEVEL"
```

for S3 to run in its intended mode.

#### 2.4.2 Instrument taxonomies

Artefacts with `role = "TAXONOMY"` that define:

* **Instrument types** (e.g. `CARD_PHYSICAL`, `CARD_VIRTUAL`, `BANK_ACCOUNT_HANDLE`, `WALLET_ID`, `DIRECT_DEBIT_MANDATE`).
* **Schemes/networks & brands** (e.g. `VISA`, `MASTERCARD`, domestic schemes, “brand tiers”).
* Optional taxonomies for:

  * `token_type` (e.g. PAN vs network token vs bank ID),
  * `card_feature` flags (`CONTACTLESS`, `VIRTUAL_ONLY`, etc.).

Taxonomies referenced by S3 schemas (e.g. enums in `s3_instrument_base_6A`) MUST be present and valid; otherwise S3 MUST fail.

#### 2.4.3 Linkage & eligibility rules

Artefacts (often priors or config packs) with roles such as:

* `"PRODUCT_LINKAGE_RULES"` (contract id: `product_linkage_rules_6A`), `"INSTRUMENT_LINKAGE_RULES"` (contract id: `instrument_linkage_rules_6A`) or similar, specifying:

  * which `account_type`s are eligible for which instrument types and schemes,
  * which party segments or regions may hold which instrument types,
  * per-party and per-account hard caps (max instruments of each type),
  * any mandatory instruments (e.g. “every current account must have at least one debit card” if that’s a requirement).

These artefacts MUST be present (or the design must explicitly treat their absence as “no additional linkage constraints”). If S3 treats them as required, they MUST appear in `sealed_inputs_6A` with `status="REQUIRED"` and `read_scope="ROW_LEVEL"`.

#### 2.4.4 6A contracts (metadata-only)

From `sealed_inputs_6A` with `role="CONTRACT"` and `read_scope="METADATA_ONLY"`:

* `schemas.layer3.yaml`
* `schemas.6A.yaml`
* `dataset_dictionary.layer3.6A.yaml`
* `artefact_registry_6A.yaml`

S3 uses these to:

* resolve dataset IDs, schema refs, and paths for S3 outputs,
* check that its own outputs are declared correctly.

S3 MUST NOT mutate these contracts.

#### 2.4.5 Optional upstream context (if used)

Depending on final design, S3 MAY also consume contextual artefacts, for example:

* card/network penetration indicators per region,
* per-region scheme mix priors (e.g. share of domestic vs international schemes),
* coarse usage hints from L2 (e.g. card-heavy vs non-card-heavy regions).

If used, these artefacts MUST:

* appear in `sealed_inputs_6A` with suitable `role` (e.g. `UPSTREAM_EGRESS`, `SCENARIO_CONFIG`),
* have `read_scope` consistent with intended use (`ROW_LEVEL` vs `METADATA_ONLY`),
* be treated as **hints**, not authorities, for instrument planning.

---

### 2.5 Axes of operation: world & seed

S3’s natural domain is the pair `(manifest_fingerprint, seed)`:

* `manifest_fingerprint` identifies the sealed upstream world and 6A input universe.
* `seed` identifies a specific party+account+instrument realisation within that world.

Preconditions per axis:

* For each `manifest_fingerprint`:

  * S0 MUST be PASS,
  * all upstream HashGates MUST be PASS via S0,
  * S3 MUST only consider sealed inputs and priors for that `mf`.

* For each `(mf, seed)`:

  * S1 and S2 MUST be PASS and have produced `s1_party_base_6A` and `s2_account_base_6A` for that pair,
  * S3 then constructs an instrument universe attached to exactly that party+account universe.

Scenario identity (`scenario_id`) is NOT an axis for S3:

* S3 builds a **scenario-independent instrument universe** per `(mf, seed)`;
* all scenarios in 6B draw instruments from this same universe.

If a future version introduces scenario-dependent instruments, that will be a breaking change and MUST be versioned accordingly.

---

### 2.6 Out-of-scope inputs

S3 explicitly **must not depend on**:

* individual arrivals from `arrival_events_5B`,
* any transaction/flow/label-level datasets from 6B or downstream,
* environment or wall-clock time (beyond non-semantic audit timestamps),
* any artefact not present in `sealed_inputs_6A` for this `manifest_fingerprint`,
* any artefact present but marked with `read_scope="METADATA_ONLY"` for row-level logic.

Any implementation that reads such inputs is **out of spec**, even if it “works” operationally.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes, for **6A.S3**, exactly:

* **what it is allowed to read**, and
* **who is allowed to define what** (L1, L2, S0, S1, S2, S3),

so that downstream states (S4/S5, 6B) can trust that S3 never redefines upstream responsibilities or pulls in “mystery” inputs.

S3 **must only** consume artefacts that:

* are listed in `sealed_inputs_6A` for its `manifest_fingerprint`, with `status ∈ {REQUIRED, OPTIONAL}`, and
* have `read_scope = "ROW_LEVEL"` for row-level logic,

plus the party and account bases from S1 and S2.

---

### 3.1 Logical inputs S3 is allowed to use

Subject to §2 and `sealed_inputs_6A`, S3’s inputs fall into four groups.

#### 3.1.1 S0 / S1 / S2 control-plane & base inputs

These are mandatory and read-only:

* **From 6A.S0:**

  * `s0_gate_receipt_6A`

    * binds `manifest_fingerprint`, `parameter_hash`,
    * records upstream gate statuses,
    * carries `sealed_inputs_digest_6A` and 6A contract/priors summary.

  * `sealed_inputs_6A`

    * enumerates all artefacts 6A may use, with `role`, `status`, `read_scope`, `schema_ref`, `path_template`, `partition_keys`, `sha256_hex`.

* **From 6A.S1:**

  * `s1_party_base_6A`

    * authoritative party universe for `(mf, seed)`: `party_id`, party type, segment, home geo, static attributes.

* **From 6A.S2:**

  * `s2_account_base_6A`

    * authoritative account universe for `(mf, seed)`: `account_id`, `owner_party_id`, optional `owner_merchant_id`, `account_type`, `product_family`, `currency_iso`, and static account attributes.

  * `s2_party_product_holdings_6A`

    * derived per-party holdings; useful for QA or as a convenience surface but not a new source of truth.

S3 **must** treat:

* S0 as the single source of truth for which inputs are sealed,
* S1 as the sole authority on parties,
* S2 as the sole authority on accounts.

#### 3.1.2 6A priors & taxonomies for instruments (ROW_LEVEL)

From `sealed_inputs_6A` with `status ∈ {REQUIRED, OPTIONAL}` and `read_scope = "ROW_LEVEL"`:

* **Instrument mix priors** (`role` e.g. `"PRODUCT_PRIOR"` / `"INSTRUMENT_PRIOR"`):

  * expected number of instruments per account “cell” (e.g. `(region, party_type, segment, account_type)`),
  * expected composition across instrument types (e.g. number of physical cards vs virtual cards vs bank-transfer handles per cell).

* **Instrument-per-account distributions**:

  * discrete distributions describing, for each cell, how many instruments of each type an account tends to have (including zero-inflation, min/max caps, etc.).

* **Instrument taxonomies** (`role="TAXONOMY"`):

  * instrument types (`instrument_type`),
  * schemes/networks (`scheme` / `network`),
  * brands/tiers,
  * token types or instrument sub-types if modelled (e.g. PAN vs network token vs bank handle).

* **Instrument-level attribute priors**:

  * e.g. expiry distributions (`expiry_month`, `expiry_year`),
  * scheme/brand mix per region/segment/account_type,
  * optional priors for static flags (contactless enabled, virtual-only).

* **Linkage / eligibility rules** (`role` e.g. `"INSTRUMENT_LINKAGE_RULES"` / `"PRODUCT_LINKAGE_RULES"`; contract ids: `instrument_linkage_rules_6A`, `product_linkage_rules_6A`):

  * which account types can have which instrument types and schemes,
  * which party segments/regions are eligible for given instruments,
  * per-account and per-party hard caps (e.g. max cards per account or per party),
  * any mandatory instrument rules (e.g. “every current account must have at least one debit instrument” if that’s in scope).

S3 uses this group to:

* derive continuous and integer instrument counts per cell and type, and
* enforce which accounts/parties are eligible to receive which instruments.

#### 3.1.3 Optional upstream context (ROW_LEVEL or METADATA_ONLY)

If present in `sealed_inputs_6A` and used by the design, S3 MAY also read:

* **Geo / socio-economic context** (`role="UPSTREAM_EGRESS"` or `POPULATION_PRIOR`):

  * region/country tables,
  * card/network penetration indicators per country/region,
  * data on prevalence of schemes (e.g. domestic vs international scheme mix).

* **Scenario / volume hints from L2** (`role="SCENARIO_CONFIG"` or `UPSTREAM_EGRESS`):

  * e.g. aggregated card vs non-card usage hints per region/segment from 5A/5B.

Usage rules:

* If `read_scope="ROW_LEVEL"`, S3 may use rows to **shape targets** (e.g. more cards per account in card-heavy regions).
* If `read_scope="METADATA_ONLY"`, S3 may only check presence/version/digests and must not read rows.

These are **hints** only; they do not override priors or define any new identity.

#### 3.1.4 6A contracts & schemas (METADATA_ONLY)

From `sealed_inputs_6A` with `role="CONTRACT"` and `read_scope="METADATA_ONLY"`:

* `schemas.layer3.yaml`
* `schemas.6A.yaml`
* `dataset_dictionary.layer3.6A.yaml`
* `artefact_registry_6A.yaml`

S3 uses these to:

* discover shapes, IDs and paths for its outputs,
* ensure its outputs line up with the declared schemas and catalogue.

S3 MUST NOT write to or mutate these artefacts.

---

### 3.2 Upstream authority boundaries (Layer-1 & Layer-2)

S3 sits on top of a fully sealed world from Layers 1 and 2. The following boundaries are **binding**.

#### 3.2.1 Merchants, sites, geo & time (1A–2A)

**Authority:**

* 1A — merchants & outlets,
* 1B — site locations,
* 2A — civil time (`site_timezones`, `tz_timetable_cache`).

S3 **must not**:

* create/delete merchants or sites,
* change merchant attributes (MCC, channels, countries, zones),
* alter site coordinates or time zones.

If S3 wants to understand regional or channel context (e.g. to bias schemes), it must do so via upstream egress (present in `sealed_inputs_6A`), not by redefining geometry/time.

#### 3.2.2 Zone allocation, routing & virtual overlay (2B, 3A, 3B)

**Authority:**

* 2B — routing & site selection,
* 3A — `zone_alloc` and routing universe hashes,
* 3B — virtual classification and virtual edge universe.

S3 **must not**:

* reinterpret routing behaviour,
* change how physical vs virtual merchants are defined,
* modify or depend on per-arrival routing decisions.

Instruments may carry hints that relate to upstream routing (e.g. “this card is likely to be used cross-border”), but those hints must be derived consistently from upstream surfaces and priors, not by changing upstream routing logic.

#### 3.2.3 Intensities & arrivals (5A, 5B)

**Authority:**

* 5A — deterministic intensity surfaces,
* 5B — arrival skeleton (`arrival_events_5B`).

S3 **must not**:

* read or re-sample individual arrivals,
* adjust counts or timings of arrivals,
* decide which instrument is used for any specific arrival — that’s 6B’s job.

If S3 uses any volume hints, they must come from aggregated, sealed context surfaces present in `sealed_inputs_6A` and are only used to shape priors, not to touch actual events.

---

### 3.3 6A authority boundaries: S1 vs S2 vs S3 vs later states

Within 6A, each state owns a distinct slice of the world.

#### 3.3.1 S1 ownership (parties)

S1 is the sole authority on:

* which `party_id`s exist for `(mf, seed)`,
* party types, segments, home geography, and S1-owned static attributes.

S3 **must not**:

* create or delete parties,
* change any S1 attributes.

It may only **reference** `party_id` and S1 attributes to condition instrument priors, not to mutate them.

#### 3.3.2 S2 ownership (accounts/products)

S2 is the sole authority on:

* which `account_id`s exist for `(mf, seed)`,
* mapping from `account_id` to `owner_party_id` / `owner_merchant_id`,
* static account attributes (account_type, product_family, currency, account-level flags).

S3 **must not**:

* create or delete accounts,
* change any S2 fields,
* violate S2’s account-level constraints (e.g. no instrument on an account that isn’t allowed by its type).

It may only attach instruments to existing accounts.

#### 3.3.3 S3 ownership (instruments & credentials)

S3 exclusively owns:

* **Instrument universe**:

  * how many instruments exist per `(mf, seed)`,
  * their `instrument_id`s,
  * which accounts/parties (and optionally merchants) they belong to.

* **Static instrument attributes**:

  * instrument_type, scheme/network, brand/tier, token_type,
  * masked identifier fields, expiry, and static flags.

Later states (e.g. S4+ for devices/IP, S5 for fraud posture) may build structures that reference `instrument_id`, but they **must not** create instruments or change these static attributes.

#### 3.3.4 Later-state boundaries (S4/S5 & 6B)

S3 **must not**:

* Create devices, IPs, or network graph edges — those are S4’s responsibility.
* Label parties/accounts/instruments as mules, synthetic, high-risk, etc. — that belongs to the fraud posture state (e.g. S5).
* Attach instruments to arrivals or build flows — that is 6B’s responsibility.

S3’s only job is to establish “which instruments exist and who they belong to”, not how they are used over time.

---

### 3.4 Forbidden dependencies & non-inputs

S3 explicitly **must not depend on**:

* Any artefact **not present** in `sealed_inputs_6A` for its `manifest_fingerprint`.

* Any artefact with `read_scope="METADATA_ONLY"` for row-level logic.

* Off-catalogue inputs — including:

  * arbitrary files not described in the dictionary/registry,
  * environment variables for anything beyond non-semantic toggles/log levels,
  * wall-clock time or host details for business semantics,
  * network calls to external services or databases.

* Raw upstream validation bundles beyond:

  * S0’s digest verification, and
  * any specific contract artefacts that S0 exposes as `role="CONTRACT"`.

Any implementation behaviour that pulls in unsealed or un-catalogued inputs is out-of-spec, even if it “works” locally.

---

### 3.5 How S0’s sealed-input manifest constrains S3

The **effective input universe** for S3 is:

> all rows in `sealed_inputs_6A` for its `manifest_fingerprint` with `status ∈ {"REQUIRED","OPTIONAL"}`, plus `s1_party_base_6A` and `s2_account_base_6A`.

S3 MUST:

1. Load `s0_gate_receipt_6A` and `sealed_inputs_6A`.

2. Verify `sealed_inputs_digest_6A` matches the recomputed digest.

3. Filter `sealed_inputs_6A` down to just the rows relevant for S3:

   * instrument priors,
   * instrument taxonomies,
   * linkage/eligibility rules,
   * optional context,
   * contracts.

4. Treat any artefact:

   * **absent** from `sealed_inputs_6A`, or
   * present with `status="IGNORED"`, or
   * present with `read_scope="METADATA_ONLY"` (for non-contracts),

   as **out of bounds** for S3’s business logic.

Downstream S4/S5 and 6B can then safely assume:

* S3’s instrument universe is derived entirely from sealed, catalogued inputs for that world,
* there are no hidden side channels, and
* any change to priors or contracts would change `sealed_inputs_digest_6A` and, hence, correspond to a different world from S3’s perspective.

---

## 4. Outputs (datasets) & identity *(Binding)*

6A.S3 produces the **instrument / credential universe** and a small set of derived linkage/holding views. This section fixes *what* those datasets are, *what they mean*, and *how they are identified*.

S3 has:

* **Required base dataset**

  * `s3_instrument_base_6A` — the instrument universe.
* **Required derived dataset**

  * `s3_account_instrument_links_6A` — per-account linkage surface (strictly derived).
* **Optional derived datasets**

  * `s3_party_instrument_holdings_6A` — per-party aggregates.
  * `s3_instrument_summary_6A` — aggregate diagnostics by region/segment/type.

Everything else in S3 (RNG logs, planning matrices) is internal and not part of the public contract.

---

### 4.1 Required dataset — instrument base

**Logical name:** `s3_instrument_base_6A`
**Role:** the *only* authoritative list of instruments / payment credentials that exist in the world for S3/6B.

#### 4.1.1 Domain & scope

For each `(manifest_fingerprint, seed)`, `s3_instrument_base_6A` contains **one row per instrument** in that world+seed.

* Domain axes:

  * `manifest_fingerprint` — world identity, as fixed by S0 and upstream.
  * `parameter_hash` — parameter/prior-pack identity (embedded as a column).
  * `seed` — RNG identity for this party+account+instrument realisation.

* S3 is **scenario-independent**:

  * there is a single instrument universe per `(mf, seed)`;
  * all scenarios in 6B draw from this same universe.

#### 4.1.2 Required content (logical fields)

The base table MUST include, at minimum, the following logical fields (names can vary in schema; semantics cannot):

* **Identity & axes**

  * `instrument_id`

    * stable identifier for the instrument within `(manifest_fingerprint, seed)`,
    * globally unique per world+seed.
  * `manifest_fingerprint`
  * `parameter_hash`
  * `seed`

* **Owner references**

  * `account_id` — FK into `s2_account_base_6A` for the same `(mf, seed)`; every instrument attaches to a single primary account.
  * optional `owner_party_id` — FK into `s1_party_base_6A`; usually redundant (derivable via account→party) but may be carried for convenience.
  * optional `owner_merchant_id` — if you model merchant-owned instruments (e.g. merchant credentials, tokens tied to a merchant), this field must be FK into the upstream merchant universe.

* **Instrument classification**

  * `instrument_type` — enum from S3 instrument taxonomy, e.g.:

    * `CARD_PHYSICAL`, `CARD_VIRTUAL`,
    * `BANK_ACCOUNT_HANDLE`,
    * `WALLET_ID`, `DIRECT_DEBIT_MANDATE`, etc.
  * optional `token_type` — e.g. `PAN`, `NETWORK_TOKEN`, `IBAN`, `ALIAS_ID`.
  * `scheme` / `network` — e.g. `VISA`, `MASTERCARD`, domestic scheme codes, ACH vs SEPA, etc.
  * optional `brand_tier` — card/product tier (`STANDARD`, `GOLD`, `PREMIUM`, etc.).

* **Identifier & display fields**

  These are *static* descriptors, not live secrets:

  * `masked_identifier` — e.g. `**** **** **** 1234` or masked IBAN;
  * optional structured pieces used for routing / branding:

    * `bin_prefix` / `iin`: synthetic issuer identification number,
    * `last4` / `last_n_digits`,
    * `issuer_country_iso` (if separate from account country), etc.

  The spec does **not** define how you generate these, only that they are static and consistent with taxonomies and priors.

* **Expiry & static flags**

  * `expiry_month`, `expiry_year` — if the instrument has an expiry concept.
  * static flags such as:

    * `contactless_enabled`,
    * `virtual_only`,
    * `card_present_capable`,
    * `card_not_present_capable`.

All of these values are:

* determined by S3’s priors/configs,
* immutable for the lifetime of the world; later states may read them but must not change them.

#### 4.1.3 Identity & invariants

For `s3_instrument_base_6A`:

* **Logical primary key:**

  ```text
  (manifest_fingerprint, seed, instrument_id)
  ```

* **Uniqueness:**

  * `instrument_id` MUST be unique within each `(manifest_fingerprint, seed)`.
  * No duplicate `(mf, seed, instrument_id)` rows may exist.

* **Foreign key invariants:**

  * Every `account_id` MUST exist in `s2_account_base_6A` for the same `(mf, seed)`.
  * If `owner_party_id` is populated, it MUST exist in `s1_party_base_6A` and MUST be consistent with the party owning the referenced account (if you choose to enforce that redundancy).
  * If `owner_merchant_id` is populated, it MUST exist in the upstream merchant universe.

* **Taxonomy invariants:**

  * Every `instrument_type`, `scheme`, `brand_tier`, `token_type`, etc. MUST appear in the corresponding taxonomy artefact(s).
  * Combinations must obey compatibility rules (e.g. scheme vs region, instrument_type vs account_type).

* **World consistency:**

  * All rows in the `(seed={seed}, fingerprint={mf})` partition MUST have those values in their columns.
  * All rows for `(mf, seed)` MUST share the same `parameter_hash`.

* **Closed-world semantics for instruments:**

  For a given `(manifest_fingerprint, seed)`, the set of `instrument_id`s in `s3_instrument_base_6A` is the **complete instrument universe** for that world+seed. No other dataset is allowed to introduce additional instruments; later states must treat this as read-only ground truth.

---

### 4.2 Required dataset — account–instrument links

**Logical name:** `s3_account_instrument_links_6A`
**Role:** canonical linkage surface from accounts to instruments; convenient for downstream states and QA. It is **purely derived** from `s3_instrument_base_6A` and `s2_account_base_6A`, but is treated as a required contract.

#### 4.2.1 Domain & scope

For each `(manifest_fingerprint, seed)`, `s3_account_instrument_links_6A` contains one or more rows per account, depending on your chosen shape:

* Either **one row per instrument** with a slim view of linkage (very close to projecting the base table).
* Or **one row per account+instrument_type** (or per account+instrument_type+scheme) with counts and optional ID arrays.

The specific grouping scheme becomes part of the binding spec once chosen. The key idea is:

> For any account, this dataset must summarise exactly which instruments it owns, in a way that is trivial to reconcile with the instrument base.

#### 4.2.2 Required content (logical fields)

Minimum logical fields:

* Identity & axes:

  * `manifest_fingerprint`, `parameter_hash`, `seed`.

* Account-level keys:

  * `account_id` (FK into `s2_account_base_6A`),
  * optional `party_id` via join or carried through.

* Instrument-level keys (depending on shape):

  * EITHER `instrument_id` (link table with one row per instrument, redundant with base),
  * OR grouping fields such as `instrument_type` / `scheme`.

* Holdings metrics:

  * if per-instrument rows: may just be one row per `(account_id, instrument_id)`.
  * if grouped: at least:

    * `instrument_count` — number of instruments in that group for this account.

In both cases, the table must be reproducible from joins between `s3_instrument_base_6A` and `s2_account_base_6A`.

#### 4.2.3 Identity & invariants

* **Logical key** (example if grouping by `account_id, instrument_type`):

  ```text
  (manifest_fingerprint, seed, account_id, instrument_type)
  ```

* **Derivation invariant:**

  * For each row, `instrument_count` MUST equal the number of base-table instruments where:

    * `account_id` matches,
    * grouping keys (e.g. `instrument_type`, `scheme`) match.

* **Coverage invariant:**

  * Summing `instrument_count` over all groups for a given `account_id` must equal the total number of instruments in the base with that `account_id`.

No new `account_id` or `instrument_id` may be introduced here; everything must be traceable back to `s2_account_base_6A` and `s3_instrument_base_6A`.

---

### 4.3 Optional datasets — party holdings & instrument summary

These are **optional** but, if implemented, must be strictly derived from the base and links.

#### 4.3.1 `s3_party_instrument_holdings_6A` (optional)

**Role:** per-party instrument holdings; convenience for downstream sizing/QA and some fraud features.

* Domain: one or more rows per `(manifest_fingerprint, seed, party_id)` plus grouping keys.
* Grouping keys: e.g. `(instrument_type)` or `(instrument_type, scheme)`.

**Required content:**

* Identity: `manifest_fingerprint`, `parameter_hash`, `seed`.
* Keys: `party_id` (FK to `s1_party_base_6A`), grouping fields.
* Metrics:

  * `instrument_count` — number of instruments held by that party in that group (via account ownership).

**Invariants:**

* Must be computable as an aggregation over `s3_instrument_base_6A` joined to `s2_account_base_6A` (and S1 for party mapping).
* Summing `instrument_count` over groups for a given party must equal the total instruments attached to that party (via accounts) in the base.

#### 4.3.2 `s3_instrument_summary_6A` (optional)

**Role:** aggregate counts across region/segment/account_type/instrument_type for diagnostics and model QA.

* Domain: one row per group, where group keys might be:

  ```text
  (region_id, party_type, segment_id, account_type, instrument_type)
  ```

  or a subset thereof.

**Required content:**

* Identity: `manifest_fingerprint`, `parameter_hash`, `seed`.
* Grouping keys: chosen combination of geo/segment/account/instrument dimensions.
* Metrics:

  * `instrument_count` — number of base instruments in the group.

**Invariants:**

* For each grouping key `g`, `instrument_count(g)` MUST equal the count of base-table rows matching `g`.
* Summing `instrument_count` over all groups MUST equal `COUNT(*)` of `s3_instrument_base_6A` for that `(mf, seed)`.

---

### 4.4 Relationship to upstream and downstream identity

S3 outputs are aligned with upstream identity and downstream expectations:

* **Upstream alignment:**

  * `manifest_fingerprint` and `parameter_hash` match S0/S1/S2 and upstream segments.
  * `account_id` is a FK into S2’s account universe; S3 never introduces accounts.
  * `owner_party_id`/`owner_merchant_id` remain consistent with S1 and L1.

* **Downstream alignment:**

  * Later 6A states (e.g. device/IP graph, fraud posture) and 6B will attach additional structure and behaviour to `instrument_id` and `account_id`, always using:

    * `(manifest_fingerprint, seed, instrument_id)` as the instrument key,
    * `(manifest_fingerprint, seed, account_id)` as the account key,
    * and `party_id`/`merchant_id` as owner context.

  * No downstream state is permitted to:

    * create new instruments outside `s3_instrument_base_6A`, or
    * change static instrument attributes defined in S3.

* **Closed-world semantics for credentials:**

  * S1: **who exists** (party universe).
  * S2: **what accounts/products exist and who owns them**.
  * **S3:** **what instruments/credentials exist and which accounts/parties they belong to**.
  * 6B: **what happens over time** (flows/transactions) using those instruments, without changing the underlying universe.

These identity and dataset semantics are **binding**. The exact column names and JSON-Schema appear in `schemas.6A.yaml`; any implementation must faithfully implement these meanings when generating S3 outputs.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

All binding schema anchors, dataset IDs, partitioning rules, and manifest keys for this state's egress live in the Layer-3 / Segment 6A contracts:
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/dataset_dictionary.layer3.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/artefact_registry_6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/schemas.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/schemas.layer3.yaml`

This specification only summarises semantics so there is a single source of truth for catalogue details. Always consult the files above for precise schema refs, physical paths, partition keys, writer ordering, lifecycle flags, and dependency metadata.

### 5.1 Outputs owned by this state
- `s3_instrument_base_6A` — Instrument / credential universe (cards, tokens, wallets) derived from S2 accounts and priors.
- `s3_account_instrument_links_6A` — Mapping between accounts and instruments so later states can traverse exposure.
- `s3_party_instrument_holdings_6A` — Per-party instrument holdings referencing the party universe.
- `s3_instrument_summary_6A` — Aggregate QA metrics for instrument coverage and dedupe health.

### 5.2 Catalogue & downstream obligations
Implementations and downstream consumers MUST resolve datasets via the dictionary/registry, honour the declared schema anchors, and treat any artefact not listed there as out of scope for this state.

## 6. Deterministic algorithm (with RNG — instrument counts & assignment) *(Binding)*

6A.S3 is **deterministic given**:

* the sealed 6A input universe (`s0_gate_receipt_6A`, `sealed_inputs_6A`),
* the party base from S1 (`s1_party_base_6A`),
* the account base from S2 (`s2_account_base_6A`),
* the S3-specific priors/taxonomies/linkage rules,
* `manifest_fingerprint`, `parameter_hash`, and `seed`.

This section fixes **what S3 does, in which order, and which parts are RNG-bearing vs RNG-free**.
Implementation details (data structures, batching, parallelism) are free; **observable behaviour is not**.

---

### 6.0 Overview & RNG discipline

For each `(manifest_fingerprint, seed)`:

1. Load gates, priors & taxonomies (RNG-free).
2. Define instrument-planning domain & derive **continuous instrument targets** per account cell (RNG-free).
3. Realise **integer instrument counts** per cell/type/scheme (RNG-bearing).
4. Allocate instruments to individual accounts (and by extension parties/merchants) (RNG-bearing).
5. Assign static instrument metadata (IDs, schemes, expiry, flags) (RNG-bearing).
6. Materialise S3 datasets & run internal checks (RNG-free).

RNG discipline:

* S3 uses the Layer-3 Philox envelope, with substreams keyed on:

  ```text
  (manifest_fingerprint, seed, "6A.S3", substream_label, context...)
  ```

* S3 defines (at least) these RNG families:

  * `instrument_count_realisation` (contract id: `rng_event_instrument_count_realisation`; substream_label: `instrument_count_realisation`) - for turning continuous instrument targets into integer counts per cell/type/scheme.
  * `instrument_allocation_sampling` (contract id: `rng_event_instrument_allocation_sampling`; substream_label: `instrument_allocation_sampling`) - for distributing instrument counts across accounts.
  * `instrument_attribute_sampling` (contract id: `rng_event_instrument_attribute_sampling`; substream_label: `instrument_attribute_sampling`) - for sampling instrument attributes (scheme/brand selection where not fixed by priors, expiries, flags, masked ID patterns, etc.).

* Each RNG event is logged using S3-specific event schemas, with:

  * `counter_before`, `counter_after`,
  * `blocks`, `draws`,
  * contextual identifiers (world, seed, cell keys, attribute family).

No RNG is used for schema, identity axes, path construction, or partitioning.

---

### 6.1 Phase 1 — Load gates, priors & taxonomies (RNG-free)

**Goal:** ensure S3 operates in a sealed world, with known S1/S2 bases and S3 priors/taxonomies.

1. **Verify S0 gate & sealed inputs**

   * Read `s0_gate_receipt_6A` and `sealed_inputs_6A` for `manifest_fingerprint`.
   * Recompute `sealed_inputs_digest_6A` and check against the value in the gate receipt.
   * Confirm all required upstream segments `{1A,1B,2A,2B,3A,3B,5A,5B}` have `gate_status="PASS"`.

2. **Verify S1 & S2 gates**

   * For the given `(mf, seed)`:

     * read latest S1 run-report, require `status="PASS"` and empty `error_code`,
     * read latest S2 run-report, require `status="PASS"` and empty `error_code`.

   * Locate `s1_party_base_6A`, `s2_account_base_6A` and `s2_party_product_holdings_6A` partitions for `(seed={seed}, fingerprint={mf})` via the catalogue and:

     * validate them against their schema anchors,
     * verify `COUNT(*)` for S1 and S2 match their run-report metrics.

3. **Identify S3-relevant sealed inputs**

   From `sealed_inputs_6A`, select rows with:

   * `role ∈ {"PRODUCT_PRIOR","INSTRUMENT_PRIOR","INSTRUMENT_LINKAGE_RULES","TAXONOMY","UPSTREAM_EGRESS","SCENARIO_CONFIG"}`,
   * `status ∈ {"REQUIRED","OPTIONAL"}`.

   Contract ids for linkage rules: `product_linkage_rules_6A`, `instrument_linkage_rules_6A`.

   Partition them into:

   * instrument mix / per-account priors,
   * linkage / eligibility rules,
   * instrument taxonomies,
   * optional context surfaces (geo, penetration, volume hints),
   * contracts (schemas/dictionaries/registry; `read_scope="METADATA_ONLY"`).

4. **Load & validate priors / taxonomies**

   * For each **required** prior/taxonomy:

     * resolve path via `path_template` + `partition_keys`,
     * read rows; validate shape against `schema_ref`,
     * recompute SHA-256 and compare to `sha256_hex`.

   * Build in-memory views for:

     * instrument mix per **instrument cell** (see 6.2),
     * distributions for instruments per account,
     * taxonomy maps for `instrument_type`, `scheme`, `brand_tier`, `token_type`, etc.,
     * per-cell attribute priors (expiry, flags, etc.), if configured.

5. **Load optional context**

   * If configured and present:

     * load region/card penetration surfaces, scheme mix hints, etc.,
     * load aggregate usage/volume hints from L2 if used to tilt priors.

   * These context surfaces must not contradict or overwrite taxonomies; they only modify target intensities.

This phase is **RNG-free** and fully deterministic given the sealed inputs.

---

### 6.2 Phase 2 — Define instrument-planning domain & continuous targets (RNG-free)

**Goal:** define the domain of instrument planning and compute **continuous expected instrument counts** per planning cell.

#### 6.2.1 Define account-level planning cells

A natural cell is:

```text
b_acc = (region_id, party_type, segment_id, account_type)
```

Where:

* `region_id` / `country_iso` are derived from `s1_party_base_6A` / `s2_account_base_6A`,
* `party_type` and `segment_id` from S1,
* `account_type` from S2.

Steps:

1. **Compute account cell counts**

   * Join `s2_account_base_6A` to `s1_party_base_6A` (via `owner_party_id`) to obtain, for each account:

     * `(region_id, party_type, segment_id, account_type)`.

   * Group by `b_acc` to compute:

     ```text
     N_accounts(b_acc) = count of accounts in that cell
     ```

   * Cells with `N_accounts(b_acc) = 0` may be dropped unless priors explicitly require instruments there (in which case, inconsistent priors should cause failure).

2. **Define instrument cell domain**

   * For each `b_acc` and each allowed `instrument_type` (from linkage rules for that cell) define an instrument cell:

     ```text
     c_instr = (region_id, party_type, segment_id, account_type, instrument_type)
     ```

   * Optionally refine with scheme dimension:

     ```text
     c_instr_scheme = (region_id, party_type, segment_id, account_type, instrument_type, scheme)
     ```

   * The domain `C_instr` is the set of all such `c_instr` or `c_instr_scheme` that are allowed by S3 priors and linkage rules.

#### 6.2.2 Derive continuous instrument targets

For each instrument cell `c`:

1. From priors, obtain:

   * `λ_instr_per_account(c)` — expected number of instruments of this type (or type+scheme) per account in that cell,
   * optional context adjustments: e.g. `scale_context(c)` scaling factor from region card penetration or scenario hints.

2. Compute continuous target:

   ```text
   N_instr_target(c) = N_accounts(b_acc(c)) * λ_instr_per_account(c) * scale_context(c)
   ```

3. Sanity checks (RNG-free):

   * `N_instr_target(c)` is finite and ≥ 0.

   * For each `b_acc`, implied expected instruments per account type:

     ```text
     N_instr_target_total(b_acc) = Σ_c over same b_acc N_instr_target(c)
     ```

     must be within configured bounds (e.g. min/max instruments per account).

   * Global continuous total:

     ```text
     N_instr_target_world = Σ_c N_instr_target(c)
     ```

     must be finite and within practical limits (subject to any configured caps).

Failures here yield errors like `6A.S3.INSTRUMENT_TARGETS_INCONSISTENT`.

This phase remains **RNG-free** and purely arithmetic.

---

### 6.3 Phase 3 — Realise integer instrument counts per cell (RNG-bearing)

**Goal:** convert `N_instr_target(c)` into **integer counts** `N_instr(c)` per cell, respecting conservation and any configured min/max constraints.

This is the first RNG-bearing phase and uses the `instrument_count_realisation` family.

#### 6.3.1 Option A — per-account-type/region aggregate then split

You may structure integerisation in two stages:

1. **Aggregate by region/account_type/instrument_type** (RNG-free)

   * For each aggregate group, e.g. `(region_id, account_type, instrument_type)` or including `scheme`:

     ```text
     N_target_group(g) = Σ_{c in group g} N_instr_target(c)
     ```

   * Compute initial integer totals:

     ```text
     N_floor_group(g)  = floor(N_target_group(g))
     r_group(g)        = N_target_group(g) - N_floor_group(g)
     ```

   * Apply deterministic largest-remainder to allocate the remaining rounds, obtaining integer `N_group(g)`.

2. **Within-group split across cells** (RNG-bearing)

   * Within each group `g`, we have:

     * integer total `N_group(g)`,
     * per-cell weights `w_c ∝ N_instr_target(c)`.

   * Use `instrument_count_realisation` RNG to sample `N_instr(c)` for cells `c` in group `g` such that:

     ```text
     Σ_{c in g} N_instr(c) == N_group(g),    N_instr(c) ∈ ℕ, N_instr(c) ≥ 0
     ```

   * This can be implemented as a multinomial draw or a RNG-driven largest-remainder scheme.

#### 6.3.2 Option B — global residual allocation

Alternatively, operate directly at cell level:

* `N_floor(c) = floor(N_instr_target(c))`,
* residuals `r_c = N_instr_target(c) - N_floor(c)`,
* base integer sum `N_floor_world = Σ_c N_floor(c)`,
* choose a global integer `N_instr_world_int` close to `N_instr_target_world` using deterministic rounding rules,
* use `instrument_count_realisation` to allocate `N_instr_world_int - N_floor_world` extra units across cells according to `r_c`.

Invariants must hold as per your selected grouping, but the spec doesn’t mandate which of A/B you use.

#### 6.3.3 RNG events & invariants

For each group of integerisation draws (e.g. per region/account_type/instrument_type or globally):

* Emit `rng_event_instrument_count` with:

  * context: `(manifest_fingerprint, parameter_hash, seed, region_id?, account_type?, instrument_type?, scheme?)`,
  * RNG envelope: `counter_before`, `counter_after`, `blocks`, `draws`,
  * optional summary: target totals vs realised totals.

Post-Phase 3 invariants:

* All `N_instr(c)` are integers ≥ 0.

* For each conservation group:

  ```text
  Σ_{c in group} N_instr(c) == N_group(group)
  ```

* Global integer total `N_instr_world_int = Σ_c N_instr(c)` is finite and within configured bounds (i.e. not absurdly large given priors and safety caps).

* Any hard min/max constraints from priors (e.g. “at least 1 instrument of type X per account_type Y” or “no more than K per account”) are not obviously violated at the plan level; if they are, S3 must fail with `6A.S3.INSTRUMENT_INTEGERISATION_FAILED` (or a more specific code).

---

### 6.4 Phase 4 — Allocate instruments to specific accounts (RNG-bearing)

**Goal:** Given `N_instr(c)` per instrument cell, instantiate `N_instr(c)` instruments and attach each to a concrete **account** (and by implication, to a party/merchant), respecting linkage and per-account constraints.

This phase uses the `instrument_allocation_sampling` family.

#### 6.4.1 Build per-cell account sets & weights

For each account cell `b_acc` and instrument type (or instrument cell `c`):

1. **Collect accounts for the cell**

   * From `s2_account_base_6A` joined to `s1_party_base_6A`, gather the set of accounts that belong to cell `(region_id, party_type, segment_id, account_type)`.

2. **Compute allocation weights per account**

   * Using instrument-per-account priors and linkage rules, derive a non-negative weight `w_a(c)` for each account `a` in cell `c`:

     * may depend on party segment, account_type, region, product_family, existing holdings from S2, etc.

3. **Normalise to probabilities per cell**

   * For each cell `c` with `N_accounts(b_acc) > 0` and `N_instr(c) > 0`:

     * compute `W_total(c) = Σ_a w_a(c)`,
     * if `W_total(c) == 0` and `N_instr(c) > 0`, that is a linkage/prior inconsistency → fail with `LINKAGE_RULES_MISSING_OR_INVALID` or `INSTRUMENT_TARGETS_INCONSISTENT`,
     * otherwise define `π_a(c) = w_a(c) / W_total(c)`.

#### 6.4.2 Sample account owners per instrument

For each instrument cell `c` with positive `N_instr(c)`:

1. **Sample account assignments**

   * Using `instrument_allocation_sampling` RNG, perform `N_instr(c)` draws from the distribution `π_a(c)` to assign instruments to accounts:

     * one draw per instrument instance, OR
     * a multinomial draw that yields counts per account `n_instr(a, c)`.

   * The result is a mapping:

     ```text
     n_instr(a, c) ∈ ℕ, Σ_a n_instr(a, c) == N_instr(c)
     ```

2. **Enforce per-account constraints**

   * Apply linkage rules that set minimum/maximum instruments per account for each instrument_type (and scheme), e.g.:

     * max cards per account,
     * some accounts not eligible for certain schemes.

   * Strategies:

     * generate a **desired per-account count** from priors and enforce consistency when sampling, or
     * use a bounded reject/repair scheme to adjust draws that violate constraints, failing if no feasible allocation is possible within a configured number of attempts.

   * If constraints cannot be satisfied without violating priors beyond configured tolerance, S3 must fail with `6A.S3.LINKAGE_RULE_VIOLATION` or `6A.S3.INSTRUMENT_INTEGERISATION_FAILED`.

3. **Emit RNG events**

   * For each cell/group, emit `rng_event_instrument_allocation` with:

     * context `(mf, ph, seed, cell identifiers)`,
     * RNG envelope,
     * optional summary: distribution of instruments per account in that cell.

---

### 6.5 Phase 5 — Assign instrument attributes (RNG-bearing)

**Goal:** For each instrument instance, assign static attributes consistent with priors/taxonomies (scheme, brand, token_type, masked representation, expiry, flags).

This phase uses `instrument_attribute_sampling`.

#### 6.5.1 Construct attribute priors

From S3 priors/config:

* For each instrument cell `c` (and possibly conditioning on account-level and party-level attributes), define conditional distributions such as:

  * `π_scheme | c` — scheme/network mix (if not fixed by `c`).
  * `π_brand_tier | c` — brand/tier distribution (e.g. share of premium cards).
  * `π_expiry_offset | c` — distribution of expiry relative to world start date.
  * `π_flag | c` — probability of flags like `contactless_enabled`, `virtual_only`.

These priors are **deterministic** functions of sealed priors and account/party context.

#### 6.5.2 Sample attributes per instrument

For each instrument instance (i.e. a unit in `n_instr(a, c)`):

1. **Identify context**

   * Determine the context for the instrument:

     * `c` (cell identifiers: region, party_type, segment, account_type, instrument_type, optional scheme),
     * attributes of its owner account & party (e.g. risk tier, income band, segment).

2. **Attribute draws**

   * For each attribute S3 owns:

     * if determined directly by taxonomies/prior config (e.g. instrument_type or scheme fixed for this cell), simply copy the value,
     * otherwise, sample from the corresponding conditional prior using `instrument_attribute_sampling`:

       * e.g. sample `brand_tier` from `π_brand_tier|c`,
       * sample expiry (month/year) from `π_expiry_offset|c`,
       * sample flags from Bernoulli/Beta-Binomial priors.

   * For identifier-like attributes:

     * the **masked identifier** and its components (e.g. `bin_prefix`, `last4`) are derived by a deterministic (or RNG-backed) function:

       * you may use RNG to sample synthetic BIN ranges or final digits,
       * but the algorithm for constructing the masked string must be deterministic given those draws.

3. **Emit RNG events**

   * Group attribute draws at appropriate batches (e.g. per cell / per attribute family) and emit `rng_event_instrument_attribute` entries with:

     * context (cell, attribute family),
     * `counter_before` / `counter_after`, `blocks`, `draws`,
     * optional summary statistics (e.g. scheme distribution per region).

---

### 6.6 Phase 6 — Materialise S3 datasets & internal validation (RNG-free)

**Goal:** write S3 outputs (`s3_instrument_base_6A`, links, holdings, summary) and ensure they are internally consistent and consistent with the RNG plan and upstream bases.

#### 6.6.1 Materialise `s3_instrument_base_6A`

Using allocations and attributes from Phases 4–5:

* Build rows with:

  * `manifest_fingerprint`, `parameter_hash`, `seed`,
  * `instrument_id` (deterministic function of `(mf, seed, cell, local_index)`),
  * `account_id`, optional `owner_party_id`, `owner_merchant_id`,
  * `instrument_type`, `scheme`, `brand_tier`, `token_type`,
  * `masked_identifier` and any structured fields,
  * expiry and static flags.

* Generate `instrument_id` via an injective, deterministic mapping, e.g.:

  ```text
  instrument_id = LOW64( SHA256( mf || seed || "instrument" || cell_key(c) || uint64(i) ) )
  ```

  where `i` is the per-cell index.

* Write to:

  ```text
  data/layer3/6A/s3_instrument_base_6A/seed={seed}/manifest_fingerprint={mf}/...
  ```

  using the canonical ordering defined in the dictionary (e.g. `account_id, instrument_type, scheme, instrument_id`).

* Validate:

  * conformance to `schemas.6A.yaml#/s3/instrument_base`,
  * uniqueness of `(mf, seed, instrument_id)`,
  * FKs:

    * `account_id` in S2 base,
    * `owner_party_id` in S1 base (if populated),
    * `owner_merchant_id` in the merchant universe (if populated).

#### 6.6.2 Materialise derived datasets

1. **`s3_account_instrument_links_6A` (required)**

   * Either:

     * project `s3_instrument_base_6A` to `(account_id, instrument_id, …)`, OR
     * aggregate into `(account_id, instrument_type, scheme)` → `instrument_count`, depending on chosen shape.

   * Write to the configured path/partition; validate against the schema anchor.

2. **`s3_party_instrument_holdings_6A` (optional)**

   * Join `s3_instrument_base_6A` → `s2_account_base_6A` → `s1_party_base_6A` to derive per-party holdings.
   * Group by the chosen dimensions (e.g. `party_id, instrument_type[, scheme]`) and compute `instrument_count`.
   * Write and validate.

3. **`s3_instrument_summary_6A` (optional)**

   * Aggregate `s3_instrument_base_6A` over the chosen grouping (e.g. `region_id, account_type, instrument_type, scheme`) and compute `instrument_count`.
   * Write and validate.

#### 6.6.3 Internal validation checks

Before marking S3 as PASS for `(mf, seed)`, S3 must perform internal checks (RNG-free):

* **Plan vs base consistency:**

  * For each instrument cell `c`, count instruments in the base belonging to `c` and verify:

    ```text
    count_in_base(c) == N_instr(c)
    ```

  * Summed across all cells, total base instruments must equal `N_instr_world_int`.

* **Links & holdings consistency:**

  * For each `account_id`, the count of instruments in `s3_account_instrument_links_6A` must match the count in the base.
  * For each `party_id` (if holdings table exists), the sum over holdings `instrument_count` must equal the number of base instruments reachable via that party’s accounts.

* **Linkage & taxonomy checks:**

  * Validate no `instrument_type`, `scheme`, `brand_tier`, etc. is outside taxonomies.
  * Confirm no account or party violates configured min/max instruments or eligibility rules.

* **RNG accounting reconciliation:**

  * Aggregate RNG event metrics per family (counts, draws, blocks).
  * Confirm they match the expected totals derived from S3’s planning logic and configured budgets.
  * Confirm no overlapping/out-of-order Philox counters.

Any failure yields a non-PASS S3 run with an appropriate `6A.S3.*` error code.

---

### 6.7 Determinism guarantees

Given:

* `manifest_fingerprint`,
* `parameter_hash`,
* `seed`,
* sealed S0 inputs (`sealed_inputs_6A`),
* sealed S1/S2 bases,
* S3 priors/taxonomies/config packs,

S3’s business outputs:

* `s3_instrument_base_6A`,
* `s3_account_instrument_links_6A`,
* `s3_party_instrument_holdings_6A` (if present),
* `s3_instrument_summary_6A` (if present),

MUST be:

* **Bit-stable & idempotent** — re-running S3 in the same catalogue state with the same seed produces byte-identical outputs.
* Independent of:

  * internal parallelism/scheduling,
  * physical layout beyond canonical ordering,
  * environment-specific details (hostnames, wall-clock times, process IDs, etc.).

All randomness must flow exclusively through the declared RNG families, under the Layer-3 RNG envelope, with fully accounted events/logs. Any change to the mapping from priors to counts and assignments—or to RNG family semantics—is a behavioural change and must be handled via spec versioning and change control, not as a silent implementation tweak.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S3’s outputs are identified, partitioned, ordered and merged**.
All downstream 6A states (S4–S5) and 6B must treat these rules as **binding**, not implementation hints.

S3’s business outputs are:

* **Required**

  * `s3_instrument_base_6A`
  * `s3_account_instrument_links_6A`
* **Optional (strictly derived from base)**

  * `s3_party_instrument_holdings_6A`
  * `s3_instrument_summary_6A`

RNG logs follow the Layer-3 RNG envelope and are covered elsewhere.

---

### 7.1 Identity axes

S3 uses the same three primary identity axes as S1/S2:

* **World identity**

  * `manifest_fingerprint`
  * Identifies the sealed upstream world and 6A input universe.
  * S3 must not change or reinterpret this.

* **Parameter identity**

  * `parameter_hash`
  * Identifies the priors/config pack used for instrument mix, linkage rules, and instrument attributes.
  * Stored as a **column** in S3 outputs, **not** as a partition key.
  * For a given `(manifest_fingerprint, seed)`, all S3 rows must share a single `parameter_hash`.

* **RNG identity**

  * `seed`
  * Identifies the specific party+account+instrument realisation within a world.
  * Different seeds with the same `(mf, ph)` define different instrument universes.

`run_id` is for logging/observability only; it must not affect business outputs.

---

### 7.2 Partitioning & path tokens

All S3 datasets are **world+seed scoped** with identical partitioning.

#### 7.2.1 `s3_instrument_base_6A`

* Partition keys:

  ```text
  [seed, fingerprint]
  ```

* Path template (schematic):

  ```text
  data/layer3/6A/s3_instrument_base_6A/
    seed={seed}/
    fingerprint={manifest_fingerprint}/
    s3_instrument_base_6A.parquet
  ```

#### 7.2.2 `s3_account_instrument_links_6A`

* Partition keys:

  ```text
  [seed, fingerprint]
  ```

* Path template (schematic):

  ```text
  data/layer3/6A/s3_account_instrument_links_6A/
    seed={seed}/
    fingerprint={manifest_fingerprint}/
    s3_account_instrument_links_6A.parquet
  ```

#### 7.2.3 Optional `s3_party_instrument_holdings_6A`, `s3_instrument_summary_6A`

If implemented:

* Partition keys:

  ```text
  [seed, fingerprint]
  ```

* Path templates:

  ```text
  data/layer3/6A/s3_party_instrument_holdings_6A/seed={seed}/manifest_fingerprint={mf}/...
  data/layer3/6A/s3_instrument_summary_6A/seed={seed}/manifest_fingerprint={mf}/...
  ```

**Binding rules:**

* `seed={seed}` and `fingerprint={manifest_fingerprint}` path tokens MUST match the `seed` and `manifest_fingerprint` columns in the data.
* No additional partition keys (e.g. `parameter_hash`, `scenario_id`) may be introduced for S3 business datasets.
* Consumers MUST resolve locations via the dictionary/registry and then substitute these tokens; hard-coded paths are out of spec.

---

### 7.3 Primary keys, foreign keys & uniqueness

#### 7.3.1 `s3_instrument_base_6A`

* **Logical primary key:**

  ```text
  (manifest_fingerprint, seed, instrument_id)
  ```

* **Uniqueness:**

  * `instrument_id` MUST be unique within each `(manifest_fingerprint, seed)`.
  * No duplicate `(mf, seed, instrument_id)` rows are permitted.

* **Foreign keys:**

  * `account_id` MUST reference an existing row in `s2_account_base_6A` for the same `(mf, seed)`.

  * If `owner_party_id` is present:

    * it MUST reference an existing `party_id` in `s1_party_base_6A` for `(mf, seed)`, and
    * if you choose to enforce the redundancy, it MUST be consistent with the party owning the referenced account.

  * If `owner_merchant_id` is present, it MUST reference a valid merchant in the Layer-1 merchant universe.

* **Parameter consistency:**

  * All rows for a given `(mf, seed)` MUST share the same `parameter_hash`.
  * Multiple `parameter_hash` values within the same `(mf, seed)` partition are a config/identity error.

#### 7.3.2 `s3_account_instrument_links_6A`

The exact PK depends on whether you store per-instrument rows or grouped holdings; both are allowed, but one scheme MUST be chosen and encoded in the schema/dictionary.

* **Variant A (per-instrument rows):**

  * Logical key:

    ```text
    (manifest_fingerprint, seed, account_id, instrument_id)
    ```

  * This is effectively a projected, slim view of the base table.

* **Variant B (grouped rows, e.g. by account_type/instrument_type/scheme):**

  * Logical key (example):

    ```text
    (manifest_fingerprint, seed, account_id, instrument_type, scheme?)
    ```

  * `instrument_count` MUST equal the number of base instruments matching that grouping for that account.

In both variants:

* Every `account_id` MUST exist in `s2_account_base_6A` for the same `(mf, seed)`.
* No new `instrument_id` may appear here that is not in `s3_instrument_base_6A`.

#### 7.3.3 Optional views

If implemented:

* **`s3_party_instrument_holdings_6A`**

  * Logical key (example):

    ```text
    (manifest_fingerprint, seed, party_id, instrument_type, scheme?)
    ```

  * `instrument_count` per row MUST equal the number of base instruments reachable via that party’s accounts that match the grouping.

* **`s3_instrument_summary_6A`**

  * Key depends on grouping (e.g. `(mf, seed, region_id, segment_id, account_type, instrument_type, scheme)`).

  * For each grouping key `g`, `instrument_count(g)` MUST equal the number of base-table instruments matching `g`.

In all cases, summary/holdings tables **must not** introduce new `party_id`/`account_id`/`instrument_id`s; they are purely derived.

---

### 7.4 Ordering: canonical vs semantic

We distinguish:

* **Canonical ordering** — required writer ordering to ensure deterministic, idempotent outputs and stable digests.
* **Semantic ordering** — ordering guarantees that consumers may rely on.

#### 7.4.1 Canonical writer ordering

The dataset dictionary MUST define canonical `ordering` for S3 datasets. For example:

* `s3_instrument_base_6A`:

  ```text
  ORDER BY account_id, instrument_type, scheme, instrument_id
  ```

* `s3_account_instrument_links_6A` (grouped variant):

  ```text
  ORDER BY account_id, instrument_type, scheme
  ```

* `s3_party_instrument_holdings_6A`:

  ```text
  ORDER BY party_id, instrument_type, scheme
  ```

* `s3_instrument_summary_6A`:

  ```text
  ORDER BY region_id, segment_id, account_type, instrument_type, scheme
  ```

Writer implementations MUST honour these orderings when materialising partitions. This ensures:

* byte-stable outputs across re-runs,
* predictable digests if S3 or later layers hash S3 datasets.

#### 7.4.2 Semantic ordering

Consumers **must not** infer business meaning from physical row order in S3 datasets:

* They must filter and group by keys (account_id, party_id, instrument_type, scheme, region_id, etc.), not rely on ordering.
* “First N rows” semantics are out-of-spec.

Canonical ordering is for idempotence/auditability; it is not a semantic contract for business logic.

---

### 7.5 Merge discipline & lifecycle

S3 behaves as **replace-not-append** at the granularity of `(manifest_fingerprint, seed)`.

#### 7.5.1 Replace-not-append per world+seed

For each `(mf, seed)`:

* `s3_instrument_base_6A` is **one complete instrument universe snapshot**.
* `s3_account_instrument_links_6A` and any optional holdings/summary views are **complete derived views** for the same universe.

Behavioural rules:

* Re-running S3 for the same `(mf, seed)` under the same `parameter_hash`, priors, and bases MUST either:

  * produce **byte-identical** outputs for all S3 datasets, or
  * fail with `6A.S3.OUTPUT_CONFLICT` (or equivalent) and leave existing outputs unchanged.

* S3 MUST NOT:

  * append instruments to an existing `(mf, seed)` universe,
  * merge two independently computed instrument universes for the same `(mf, seed)`.

Any attempt to “top up” instruments across runs is out-of-spec.

#### 7.5.2 No cross-world / cross-seed merges

* **No cross-world merges:**

  * Instruments for different `manifest_fingerprint`s must never be mixed; each world is hermetic.

* **No cross-seed merges within a world:**

  * Different `seed`s under the same `mf` correspond to different universes;
  * you may aggregate across seeds for analysis, but no state may treat them as a single logical universe for flows/fraud.

If an implementation merges data from multiple seeds into one S3 view without explicit analysis semantics, it violates the spec.

---

### 7.6 Consumption discipline for S4–S5 and 6B

Downstream states **must** respect S3’s identity and merge discipline.

#### 7.6.1 6A.S4–S5 (later 6A states)

For each `(mf, seed)` they operate on, S4–S5 MUST:

* Check S0/S1/S2 gates as per their own specs, **and**

* Check S3 PASS for `(mf, seed)` via S3’s run-report:

  * latest S3 run-report has `status="PASS"` and empty `error_code`.

* Confirm that:

  * `s3_instrument_base_6A` exists and is schema-valid,
  * `s3_account_instrument_links_6A` exists and is schema-valid.

They MUST NOT:

* create new instruments (`instrument_id`) not present in `s3_instrument_base_6A`,
* change static instrument attributes defined by S3.

Any graph edges, device/IP associations or fraud labels they define must reference existing `(mf, seed, instrument_id)` / `account_id` / `party_id` values.

#### 7.6.2 6B (flows & fraud)

6B MUST:

* treat `s3_instrument_base_6A` as the **only** source of instruments/credentials for `(mf, seed)`,
* only attach flows/transactions to `instrument_id` / `account_id` pairs that exist in S3/S2 for the same `(mf, seed)`,
* treat any reference to a non-existent `instrument_id`/`account_id` as an error (not as an “external” or “unknown” instrument).

6B may introduce dynamic state (balances, authorisation history, labels) keyed off S3/S2 identifiers, but it MUST NOT alter S3’s identity or static attributes.

---

These identity, partition, ordering, and merge rules are **binding**. Storage format, execution strategy, and internal data structures are implementation concerns; any implementation that changes these semantics is not a correct implementation of 6A.S3.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 6A.S3 is considered PASS** for a given `(manifest_fingerprint, seed)` and how **downstream states must gate on S3** before using any instrument/credential data.

If any condition here fails, S3 is **FAIL for that `(mf, seed)`**, and **no later 6A state (S4–S5) nor 6B may treat S3 outputs as valid**.

---

### 8.1 Segment-local PASS / FAIL definition

For a given `(manifest_fingerprint, seed)`, 6A.S3 is **PASS** *iff* all of the following hold.

#### 8.1.1 S0 / S1 / S2 / upstream worlds are sealed

1. **S0 gate & sealed-inputs valid for this world:**

   * `s0_gate_receipt_6A` and `sealed_inputs_6A` exist for `manifest_fingerprint` and validate against their schemas.
   * Recomputing `sealed_inputs_digest_6A` from `sealed_inputs_6A` yields exactly the value in `s0_gate_receipt_6A.sealed_inputs_digest_6A`.
   * Latest 6A.S0 run-report for this `mf` has:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

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
   * `s1_party_base_6A` exists for `(seed={seed}, fingerprint={mf})`, validates against its schema, and `COUNT(*)` equals `total_parties` in the S1 run-report.

4. **S2 is sealed for this `(mf, seed)`:**

   * Latest 6A.S2 run-report for `(mf, seed)` has:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```
   * `s2_account_base_6A` and `s2_party_product_holdings_6A` exist for `(seed={seed}, fingerprint={mf})`, validate against their schemas, and `COUNT(*)` of the account base equals `total_accounts` in the S2 run-report.

If any of 1–4 fail, S3 MUST NOT construct an instrument universe for that `(mf, seed)` and MUST fail with a gate error (e.g. `6A.S3.S0_S1_S2_GATE_FAILED`).

---

#### 8.1.2 Priors, taxonomies & linkage rules

5. **Required S3 priors & taxonomies are present and usable:**

   * Every artefact S3 classifies as **required** (instrument mix priors, instruments-per-account priors, instrument taxonomies, linkage/eligibility configs) has a row in `sealed_inputs_6A` with:

     ```text
     status     == "REQUIRED"
     read_scope == "ROW_LEVEL"   # except pure contracts, which may be METADATA_ONLY
     ```
   * Each such artefact:

     * resolves via `path_template` / `partition_keys`,
     * validates against its `schema_ref`,
     * has `sha256_hex` matching its contents (and any registry digest).

6. **Taxonomy consistency:**

   * All taxonomies referenced by S3 schemas (instrument_type, scheme/network, brand_tier, token_type, etc.) exist and are schema-valid.
   * All codes they define are internally consistent (no duplicates, no obviously conflicting rules).

If any required prior/taxonomy/linkage pack is missing or invalid, S3 MUST fail with one of:

* `6A.S3.PRIOR_PACK_MISSING`,
* `6A.S3.PRIOR_PACK_INVALID`,
* `6A.S3.PRIOR_PACK_DIGEST_MISMATCH`,
* `6A.S3.TAXONOMY_MISSING_OR_INVALID`,
* `6A.S3.LINKAGE_RULES_MISSING_OR_INVALID`.

---

#### 8.1.3 Target derivation & integer instrument counts

7. **Continuous instrument targets are sane:**

   * All continuous targets `N_instr_target(c)` (per instrument planning cell) are finite and ≥ 0.
   * For each base account cell (e.g. `(region, party_type, segment, account_type)`), the implied expected instruments per account is within configured bounds (e.g. not negative, not “thousands per account” unless explicitly allowed).
   * The global continuous total:

     ```text
     N_instr_target_world = Σ_c N_instr_target(c)
     ```

     is finite and within any configured safety caps.

8. **Integer instrument counts are consistent and conservative:**

   After integerisation:

   * For each conservation group (e.g. per `(region, account_type, instrument_type[, scheme])` or per world, depending on design):

     ```text
     Σ_{c in group} N_instr(c) == N_group_integer_total
     ```
   * Every `N_instr(c)` is a non-negative integer.
   * Any configured **min/max** constraints in priors/linkage rules are honoured, for example:

     * max instruments per account or per party/segment/type,
     * mandatory instruments per account_type where specified.

If targets or integerisation violate these invariants, S3 MUST fail with `6A.S3.INSTRUMENT_TARGETS_INCONSISTENT` or `6A.S3.INSTRUMENT_INTEGERISATION_FAILED`.

---

#### 8.1.4 Base-table correctness & linkage

9. **`s3_instrument_base_6A` exists and is schema-valid:**

   * The partition for `(seed={seed}, fingerprint={mf})` exists.
   * It validates against `schemas.6A.yaml#/s3/instrument_base`.
   * The logical PK `(manifest_fingerprint, seed, instrument_id)` is unique:

     * no duplicate `instrument_id` within `(mf, seed)`,
     * all rows have the correct `(mf, seed)` columns.

10. **Foreign key & linkage invariants:**

    * For each row in the base:

      * `account_id` exists in `s2_account_base_6A` for the same `(mf, seed)`.
      * If `owner_party_id` is populated, it exists in `s1_party_base_6A` and, if you enforce redundancy, is consistent with the party owning the account.
      * If `owner_merchant_id` is populated, it exists in the upstream merchant universe.

    * All instrument-owner relationships obey linkage rules:

      * account_type/segment/region combinations are eligible for that `instrument_type` and `scheme`,
      * per-account / per-party caps (max instruments of type X) are not violated where configured as hard constraints.

    Violations MUST surface as:

    * `6A.S3.ORPHAN_INSTRUMENT_OWNER`, and/or
    * `6A.S3.LINKAGE_RULE_VIOLATION`.

11. **Counts match the integerisation plan:**

    * For each planning cell `c`, the number of base-table instruments belonging to `c` equals `N_instr(c)` realised in Phase 3.
    * Summed over all cells:

      ```text
      COUNT(*) over s3_instrument_base_6A for (mf, seed) == N_instr_world_int
      ```

    Any mismatch MUST be reported as `6A.S3.INSTRUMENT_COUNTS_MISMATCH`.

12. **Taxonomy compatibility in base:**

    * Every `instrument_type`, `scheme`, `brand_tier`, `token_type`, and any other enum-coded field:

      * appears in the corresponding taxonomy, and
      * respects compatibility rules (e.g. scheme allowed in region, instrument_type allowed for account_type, etc.).

    Violations MUST be treated as `6A.S3.TAXONOMY_COMPATIBILITY_FAILED`.

---

#### 8.1.5 Derived datasets: links, holdings & summaries

13. **`s3_account_instrument_links_6A` is consistent with base:**

    * Exists and validates against `schemas.6A.yaml#/s3/account_instrument_links`.
    * For each account/group row, `instrument_count` (if using grouped variant) equals the number of instruments in the base that match that account/group.
    * For each `account_id`, summing `instrument_count` over all groups equals the total base instruments for that account.

14. **Optional `s3_party_instrument_holdings_6A` is consistent (if present):**

    * Exists and validates against its schema anchor.
    * For each `(party_id, [grouping])` row, `instrument_count` equals the number of base instruments reachable via that party’s accounts that match the grouping.
    * For each `party_id`, summing `instrument_count` over holdings rows equals the total number of base instruments for that party.

15. **Optional `s3_instrument_summary_6A` is consistent (if present):**

    * Exists and validates against its schema anchor.
    * For each grouping key `g`, `instrument_count(g)` equals the number of base-table instruments matching `g`.
    * Summing `instrument_count` over all rows equals `COUNT(*)` of `s3_instrument_base_6A` for `(mf, seed)`.

Any inconsistency between links/holdings/summaries and the base MUST result in a non-PASS S3 run (e.g. `6A.S3.INSTRUMENT_COUNTS_MISMATCH` or a more specific holdings/summary error).

---

#### 8.1.6 RNG accounting

16. **RNG usage is fully accounted and within budget:**

    * All uses of randomness in S3 are confined to the declared RNG families:

      * `instrument_count_realisation`,
      * `instrument_allocation_sampling`,
      * `instrument_attribute_sampling`.

    * Aggregate RNG metrics from S3’s event tables and layer-wide RNG logs reconcile:

      * expected number of RNG events per family,
      * total draws and blocks per family,
      * no overlapping/out-of-order Philox counter ranges.

    * Any configured RNG budgets (e.g. max draws per family per `(mf, seed)`) are respected.

If RNG accounting fails, S3 MUST fail with `6A.S3.RNG_ACCOUNTING_MISMATCH` or `6A.S3.RNG_STREAM_CONFIG_INVALID`.

---

### 8.2 Gating obligations for downstream 6A states (S4–S5)

For each `(manifest_fingerprint, seed)`, **6A.S4–S5 MUST treat S3 as a hard precondition**.

Before reading or using any instrument/credential data, a downstream 6A state MUST:

1. Verify S0, S1, S2 gates as per its own spec, **and**
2. Verify S3 PASS for `(mf, seed)` by:

   * reading the latest 6A.S3 run-report for `(mf, seed)`,
   * requiring:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```
   * confirming that `s3_instrument_base_6A` and `s3_account_instrument_links_6A` exist and validate against their schemas.

If any of these checks fails, the downstream state MUST:

* NOT read or rely on S3 instrument datasets for that `(mf, seed)`,
* fail its own gate with a state-local error such as `6A.S4.S3_GATE_FAILED`.

Downstream 6A states MUST also:

* NEVER create new `instrument_id`s; S3 is the sole authority on instrument existence.
* NEVER change static instrument attributes; they may only read them as context.
* ALWAYS reference instruments via `(manifest_fingerprint, seed, instrument_id)` and accounts / parties via S2/S1 PKs.

---

### 8.3 Gating obligations for 6B and external consumers

6B and any other consumer that uses instruments/credentials for flows or decisions MUST:

1. Require S3 PASS for the target `(mf, seed)`:

   * consult S3’s run-report entry for `(mf, seed)`,
   * ensure `status="PASS"` and `error_code` empty/null.

2. Treat `s3_instrument_base_6A` as the **only source of truth** for:

   * which instruments/credentials exist,
   * how they are statically classified (type, scheme, brand, flags),
   * which account and party each instrument belongs to.

3. Treat `s3_account_instrument_links_6A` and optional holdings/summaries as **derived** convenience surfaces, not as independent definitions of reality.

4. Treat any references to `instrument_id` or `account_id` not found in S3/S2 for the same `(mf, seed)` as errors, not as “external instruments”.

6B may attach dynamic behaviour to `instrument_id`/`account_id` (flows, balances, authorisation events), but MUST NOT alter the underlying static instrument universe.

---

### 8.4 Behaviour on failure & partial outputs

If S3 fails for a given `(manifest_fingerprint, seed)`:

* Any partially written S3 datasets (`s3_instrument_base_6A`, links, holdings, summaries) MUST NOT be treated as valid.
* Downstream states MUST consider that world+seed as having **no valid S3 instrument universe**, regardless of file presence.

S3’s run-report record MUST be updated with:

* `status = "FAIL"`,
* a non-empty `error_code` from the `6A.S3.*` namespace,
* a short `error_message`.

No state is allowed to “limp on” using partially generated instruments. The only valid states are:

* **S3 PASS →** S4–S5 and 6B may operate on instruments for that `(mf, seed)`.
* **S3 FAIL →** S4–S5 and 6B MUST NOT operate on instruments for that `(mf, seed)` until S3 is re-run and PASS.

These acceptance criteria and gating obligations are **binding** and define exactly what “S3 is done and safe to build on” means for the rest of Layer-3 and the enterprise shell.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error surface** for 6A.S3.

Every failure for a given `(manifest_fingerprint, seed)` **must** be mapped to exactly one of these codes.

All codes here are:

* **Fatal** for S3 for that `(manifest_fingerprint, seed)`.
* **Blocking** for all later 6A states (S4–S5) and 6B for that `(manifest_fingerprint, seed)`.

There is no “best effort” downgrade. If S3 fails, the instrument universe for that world+seed is **not usable**.

---

### 9.1 Error class overview

We group S3 failures into six classes:

1. **Gate / sealed-input / S1/S2 errors**
2. **Priors, taxonomies & linkage-rule errors**
3. **Target derivation & integerisation errors**
4. **Base-table & linkage errors**
5. **RNG & accounting errors**
6. **IO / identity / internal errors**

Each class has a small, closed set of codes under the `6A.S3.*` namespace.

---

### 9.2 Canonical error codes

#### 9.2.1 Gate / sealed-input / S1/S2 errors

These mean S3 cannot trust the world-level gate, the sealed input universe, or the party/account bases.

* `6A.S3.S0_S1_S2_GATE_FAILED`
  *Meaning:* One of:

  * S0 is missing or not PASS for this `manifest_fingerprint`, or
  * `sealed_inputs_digest_6A` recomputed from `sealed_inputs_6A` does not match `s0_gate_receipt_6A`, or
  * one or more required upstream segments `{1A,1B,2A,2B,3A,3B,5A,5B}` have `gate_status != "PASS"` in `upstream_gates`, or
  * S1 is missing or not PASS for this `(manifest_fingerprint, seed)`, or
  * S2 is missing or not PASS for this `(manifest_fingerprint, seed)`.

* `6A.S3.SEALED_INPUTS_MISSING_REQUIRED`
  *Meaning:* One or more artefacts S3 considers **required** (e.g. instrument-mix priors, instrument taxonomies, linkage rules) are not present as rows in `sealed_inputs_6A` for this `manifest_fingerprint`.

* `6A.S3.SEALED_INPUTS_SCOPE_INVALID`
  *Meaning:* A required artefact appears in `sealed_inputs_6A`, but:

  * `status="IGNORED"`, or
  * `read_scope="METADATA_ONLY"` where S3 requires `ROW_LEVEL`.

These codes all mean: **“S3 cannot even start; the gate / input universe is not valid for this world.”**

---

#### 9.2.2 Priors, taxonomies & linkage-rule errors

These indicate that S3’s own priors/configs and taxonomies are not usable.

* `6A.S3.PRIOR_PACK_MISSING`
  *Meaning:* A required S3 prior/config artefact (instrument mix priors, instruments-per-account distributions, or linkage config) referenced in `sealed_inputs_6A` cannot be resolved via the catalogue for this `(mf, ph)`.

* `6A.S3.PRIOR_PACK_INVALID`
  *Meaning:* A required prior/config artefact is present but fails validation against its `schema_ref` (wrong structure, missing required fields, type mismatches, etc.).

* `6A.S3.PRIOR_PACK_DIGEST_MISMATCH`
  *Meaning:* The SHA-256 digest computed from a prior/config artefact does not match `sha256_hex` recorded in `sealed_inputs_6A` (and/or the registry).

* `6A.S3.TAXONOMY_MISSING_OR_INVALID`
  *Meaning:* A required taxonomy (for instrument types, schemes/networks, brand tiers, token types, etc.) is missing, malformed, or lacks required values used by S3.

* `6A.S3.LINKAGE_RULES_MISSING_OR_INVALID`
  *Meaning:* Required linkage / eligibility rules:

  * are missing from `sealed_inputs_6A`,
  * fail schema validation, or
  * are internally inconsistent (e.g. no allowed instrument types for a cell with non-zero account count).

These errors all mean: **“S3 does not have a coherent set of priors/taxonomies/linkage rules to define instruments.”**

---

#### 9.2.3 Target derivation & integerisation errors

These indicate that S3 cannot derive or realise a consistent plan for instrument counts.

* `6A.S3.INSTRUMENT_TARGETS_INCONSISTENT`
  *Meaning:* Continuous target counts `N_instr_target(c)` per planning cell are inconsistent or ill-formed; examples:

  * some `N_instr_target(c)` are negative or NaN/Inf,
  * implied instruments-per-account in a cell wildly exceed configured min/max bounds,
  * required cells (by priors/linkage rules) are missing from the planning domain.

* `6A.S3.INSTRUMENT_INTEGERISATION_FAILED`
  *Meaning:* Integerisation of targets to `N_instr(c)` fails to satisfy constraints; examples:

  * some `N_instr(c) < 0`,
  * conservation fails at required aggregation levels (e.g. per region/account_type/instrument_type),
  * global integer total diverges from continuous target beyond allowed tolerance,
  * min/max constraints (e.g. mandatory instruments per account type) cannot be satisfied simultaneously at the plan level.

These mean: **“We cannot produce a sane, integer instrument-count plan from the priors; don’t trust any base-table built on top of it.”**

---

#### 9.2.4 Base-table & linkage errors

These indicate that the materialised S3 datasets are internally inconsistent, violate linkage rules, or disagree with the plan.

* `6A.S3.INSTRUMENT_BASE_SCHEMA_OR_KEY_INVALID`
  *Meaning:* `s3_instrument_base_6A` exists but:

  * fails validation against `schemas.6A.yaml#/s3/instrument_base`, or
  * violates the PK/uniqueness constraint `(manifest_fingerprint, seed, instrument_id)`.

* `6A.S3.INSTRUMENT_COUNTS_MISMATCH`
  *Meaning:* When comparing the base table to the integer plan:

  * counts per instrument cell `c` (based on region/segment/account_type/instrument_type[/scheme]) do not match `N_instr(c)`, and/or
  * `COUNT(*)` over the base table does not equal `N_instr_world_int`.

* `6A.S3.ORPHAN_INSTRUMENT_OWNER`
  *Meaning:* One or more instruments:

  * refer to an `account_id` that does not exist in `s2_account_base_6A` for `(mf, seed)`, and/or
  * refer to an `owner_party_id` that does not exist in `s1_party_base_6A` (where that field is populated), and/or
  * refer to an `owner_merchant_id` that is not present in the upstream merchant universe.

* `6A.S3.LINKAGE_RULE_VIOLATION`
  *Meaning:* Instrument-owner relationships in the base table violate linkage/eligibility rules; for example:

  * instruments of type X attached to accounts or parties that are not eligible for type X,
  * per-account or per-party caps on instruments of type X are exceeded where they are configured as hard constraints.

* `6A.S3.TAXONOMY_COMPATIBILITY_FAILED`
  *Meaning:* Base-table codes are inconsistent with taxonomies; for example:

  * `instrument_type`, `scheme`, `brand_tier`, `token_type` contain unknown values,
  * combinations violate compatibility rules (e.g. scheme not allowed in region, instrument_type not allowed for a given account_type/segment).

* `6A.S3.LINKS_INCONSISTENT_WITH_BASE`
  *Meaning:* `s3_account_instrument_links_6A` does not match `s3_instrument_base_6A`, e.g.:

  * `instrument_count` per (account, group) does not equal the number of base-table instruments for that account/group,
  * some accounts with instruments in the base are missing from the links dataset, or vice versa.

* `6A.S3.HOLDINGS_INCONSISTENT_WITH_BASE`
  *(if `s3_party_instrument_holdings_6A` is present)*
  *Meaning:* Per-party holdings do not match the base table; for example:

  * `instrument_count` for `(party, group)` does not equal the number of base instruments reachable via that party’s accounts,
  * aggregate holdings per party do not match the total base instruments attached to that party.

* `6A.S3.SUMMARY_INCONSISTENT_WITH_BASE`
  *(if `s3_instrument_summary_6A` is present)*
  *Meaning:* Summary counts do not match the base table:

  * `instrument_count` for a group key `g` does not equal the number of base-table rows matching `g`, or
  * sum over all summary rows does not equal `COUNT(*)` over `s3_instrument_base_6A` for `(mf, seed)`.

All of these mean: **“The materialised instrument universe is not a valid reflection of S3’s plan, upstream entities, or taxonomies.”**

---

#### 9.2.5 RNG & accounting errors

These indicate that S3’s randomness **cannot be trusted or audited**.

* `6A.S3.RNG_ACCOUNTING_MISMATCH`
  *Meaning:* Aggregate RNG metrics for S3 families (`instrument_count_realisation`, `instrument_allocation_sampling`, `instrument_attribute_sampling`) do not reconcile with expectations; e.g.:

  * missing or extra RNG events,
  * overlapping or out-of-order Philox counter ranges,
  * total draws/blocks significantly outside configured budgets.

* `6A.S3.RNG_STREAM_CONFIG_INVALID`
  *Meaning:* S3’s RNG configuration is inconsistent with the Layer-3 RNG envelope; e.g.:

  * substream labels not registered or mis-specified,
  * conflicting key derivations (two different contexts mapping to the same substream),
  * mismatch between RNG event schema and the envelope contract.

These errors mean: **“We can’t reliably reproduce or audit S3’s random choices; this run is not trustworthy.”**

---

#### 9.2.6 IO / identity / internal errors

These indicate storage problems, identity conflicts, or unexpected internal failures.

* `6A.S3.IO_READ_FAILED`
  *Meaning:* S3 failed to read a required artefact (priors, taxonomies, S0/S1/S2 outputs, catalogue files) because of IO issues (permissions, network, corruption), even though the catalogue claims it exists.

* `6A.S3.IO_WRITE_FAILED`
  *Meaning:* S3 attempted to write `s3_instrument_base_6A`, links, or holdings/summary datasets and the write failed to complete atomically/durably.

* `6A.S3.OUTPUT_CONFLICT`
  *Meaning:* For a given `(mf, seed)`, S3 outputs already exist and are **not** byte-identical to what S3 would produce given the current inputs (priors, taxonomies, bases). S3 is not allowed to silently overwrite; this is a replace-not-append violation.

* `6A.S3.INTERNAL_ERROR`
  *Meaning:* A non-classified, unexpected internal error occurred (e.g. assertion failure, unhandled exception) that doesn’t map cleanly onto any of the more specific codes above. This should be treated as an implementation bug, not a normal operational state.

These all mean: **“This S3 run is structurally broken; its outputs must not be used.”**

---

### 9.3 Mapping detection → error code

Implementations **must** map detected failures to these codes deterministically. Some examples:

* S0/S1/S2 gate checks fail → `6A.S3.S0_S1_S2_GATE_FAILED`.
* A required instrument prior is missing from `sealed_inputs_6A` → `6A.S3.SEALED_INPUTS_MISSING_REQUIRED`.
* An instrument prior is present but schema-invalid → `6A.S3.PRIOR_PACK_INVALID`.
* Instrument taxonomy missing or doesn’t contain a required code → `6A.S3.TAXONOMY_MISSING_OR_INVALID`.
* Continuous targets contain NaNs or negative values → `6A.S3.INSTRUMENT_TARGETS_INCONSISTENT`.
* Integerisation produces negative counts or breaks conservation → `6A.S3.INSTRUMENT_INTEGERISATION_FAILED`.
* An instrument’s `account_id` doesn’t exist in S2 base → `6A.S3.ORPHAN_INSTRUMENT_OWNER`.
* Instrument attached to an account/party in violation of linkage rules → `6A.S3.LINKAGE_RULE_VIOLATION`.
* Base-table counts don’t match the integer plan → `6A.S3.INSTRUMENT_COUNTS_MISMATCH`.
* Links/holdings/summary disagree with base → `6A.S3.LINKS_INCONSISTENT_WITH_BASE`, `6A.S3.HOLDINGS_INCONSISTENT_WITH_BASE`, or `6A.S3.SUMMARY_INCONSISTENT_WITH_BASE`.
* RNG counters/draws don’t reconcile → `6A.S3.RNG_ACCOUNTING_MISMATCH`.
* Attempt to overwrite non-identical existing S3 outputs → `6A.S3.OUTPUT_CONFLICT`.

If no specific code fits, implementations must use `6A.S3.INTERNAL_ERROR` and the spec should be extended later, rather than inventing ad-hoc codes.

---

### 9.4 Run-report integration & propagation

On each S3 run for `(manifest_fingerprint, seed)`, the S3 run-report record MUST include:

* `state_id = "6A.S3"`
* `manifest_fingerprint`, `parameter_hash`, `seed`
* `status ∈ {"PASS","FAIL"}`
* `error_code` (empty/null on PASS; one of the `6A.S3.*` codes on FAIL)
* `error_message` (short, human-readable, non-normative)

For **FAIL**:

* S3 MUST NOT mark the instrument universe as usable,
* S3 MUST NOT be treated as “gate PASS” by any downstream state, regardless of dataset presence.

Downstream S4–S5 and 6B MUST:

* check S3’s run-report for `(mf, seed)` before consuming S3 outputs,
* refuse to proceed if `status != "PASS"` or `error_code` is non-empty.

The `6A.S3.*` error codes are the **primary machine-readable signal** of S3’s failure mode. Logs and stack traces are diagnostic only and do not form part of the contract.

---

## 10. Observability & run-report integration *(Binding)*

6A.S3 defines the **instrument universe**, so its status and high-level shape must be **explicitly observable** and **machine-checkable**.
Downstream states (S4–S5, 6B) must gate on S3’s **run-report**, not on “files exist”.

This section fixes:

* what S3 must emit in its run-report,
* how that report relates to S3 datasets, and
* how downstream must use it.

---

### 10.1 Run-report record for 6A.S3

For every attempted S3 run on a `(manifest_fingerprint, seed)`, the engine **MUST** emit exactly one run-report record with at least:

#### Identity

* `state_id = "6A.S3"`
* `manifest_fingerprint`
* `parameter_hash`
* `seed`
* `engine_version`
* `spec_version_6A` (including S3’s effective spec version, e.g. `spec_version_6A_S3` if you split it)

#### Execution envelope

* `run_id` (execution identifier; non-semantic)
* `started_utc` (RFC 3339 with micros)
* `completed_utc` (RFC 3339 with micros)
* `duration_ms` (derived)

#### Status & error

* `status ∈ { "PASS", "FAIL" }`
* `error_code`

  * empty / null for PASS,
  * one of the `6A.S3.*` codes from §9 for FAIL.
* `error_message`

  * short, human-oriented description (non-normative; not parsed by machines).

#### Core instrument metrics (binding for PASS)

For a PASS run, at minimum:

* `total_instruments`

  * total number of rows in `s3_instrument_base_6A` for `(mf, seed)`.

* `instruments_by_type`

  * map/array: `instrument_type → count`.

* `instruments_by_scheme`

  * map/array: `scheme → count` (where scheme is meaningful).

* `instruments_by_account_type`

  * counts per `account_type` of the owning account (via join to `s2_account_base_6A`).

* `instruments_by_party_segment`

  * counts per party `segment_id` (via join through S2→S1).

* `instruments_by_region`

  * counts per region/country axis used in S3 planning (e.g. `region_id` or `country_iso` for the owner).

#### Distribution metrics (binding for PASS)

To capture concentration:

* `instruments_per_account_min` / `instruments_per_account_max`
* `instruments_per_account_mean`
* `instruments_per_account_pXX`

  * selected percentiles (e.g. p50, p90, p99).

Optionally:

* `instruments_per_party_min` / `max` / `mean` / `pXX`, derived via party-level aggregation.

#### RNG metrics

Per RNG family used by S3:

* `rng_instrument_count_events`, `rng_instrument_count_draws`
* `rng_instrument_allocation_events`, `rng_instrument_allocation_draws`
* `rng_instrument_attribute_events`, `rng_instrument_attribute_draws`

These MUST reconcile with the RNG envelope and trace logs (see §8.1.6).

---

### 10.2 PASS vs FAIL semantics

**PASS run**:

* `status == "PASS"`
* `error_code` is empty / null.
* All reported metrics **MUST** be consistent with S3 datasets:

  * `total_instruments == COUNT(*)` over `s3_instrument_base_6A` for `(mf, seed)`.
  * `instruments_by_type` matches `GROUP BY instrument_type` on the base.
  * `instruments_by_scheme`, `instruments_by_account_type`, `instruments_by_party_segment`, `instruments_by_region` match appropriate groupings via joins to S2/S1.
  * `instruments_per_account_*` metrics match the distribution of per-account instrument counts computed from `s3_account_instrument_links_6A` (or from the base if you don’t store counts there).

**FAIL run**:

* `status == "FAIL"`
* `error_code` is a non-empty `6A.S3.*` code.
* `total_instruments` and other metrics may be omitted or set to sentinel values; they are **not authoritative**.
* Downstream states MUST NOT treat a FAIL record as “good enough to continue”.

S3 MUST NOT emit `status="PASS"` unless all acceptance criteria in §8 are satisfied and S3 datasets have been successfully written and validated.

---

### 10.3 Relationship between run-report and S3 datasets

For a **PASS** S3 run on `(mf, seed)`:

* The following partitions MUST exist and be schema-valid:

  * `s3_instrument_base_6A` for `(seed={seed}, fingerprint={mf})`,
  * `s3_account_instrument_links_6A` for `(seed={seed}, fingerprint={mf})`,
  * and any implemented optional S3 views (`s3_party_instrument_holdings_6A`, `s3_instrument_summary_6A`).

* The run-report metrics MUST agree with dataset contents, in particular:

  * `total_instruments == COUNT(*)` over `s3_instrument_base_6A` for `(mf, seed)`.
  * `instruments_by_type`/`scheme` match group-by queries on the base.
  * `instruments_by_account_type`, `instruments_by_party_segment`, `instruments_by_region` match group-by queries via joins to S2/S1.
  * `instruments_per_account_*` metrics match the distribution obtained from counting instruments per `account_id` in base/links.
  * If holdings and summary datasets exist, their aggregates MUST align with the base counts as per §8.

For a **FAIL** run:

* S3 datasets (if any exist) MUST NOT be treated as valid for that `(mf, seed)`.
* Orchestration may choose to delete or quarantine partial data, but downstream states MUST base their gating on the run-report `status` and `error_code`, not on file existence.

---

### 10.4 Gating behaviour in downstream states

All downstream states that depend on instruments — i.e.:

* later 6A states (S4–S5), and
* 6B (flows / fraud) and any external consumers —

**MUST** incorporate S3’s run-report in their gates.

Before consuming S3 outputs for `(mf, seed)`, a downstream state MUST:

1. Locate the **latest** 6A.S3 run-report record for that `(mf, seed)`.

2. Require:

   ```text
   status     == "PASS"
   error_code == "" or null
   ```

3. Confirm that:

   * `s3_instrument_base_6A` exists, is schema-valid, and `COUNT(*)` matches `total_instruments`.
   * `s3_account_instrument_links_6A` exists, is schema-valid, and is consistent with the base (either by direct PK join or by verifying counts against the run-report and §8 invariants).

If any of these checks fail, the downstream state MUST:

* treat S3 as **not available** for that `(mf, seed)`, and
* fail its own gate with a state-local error (e.g. `6A.S4.S3_GATE_FAILED`, `6B.S0.S3_GATE_FAILED`).

No downstream state may proceed on “partial” or unverified S3 outputs.

---

### 10.5 Additional observability (recommended, non-semantic)

The following are recommended (but **non-binding**) to aid operators and model QA:

* Extended metrics (in run-report or separate QA logs), e.g.:

  * top N instrument_types and schemes by count,
  * distribution of instrument density across segments/regions,
  * counts of instruments per merchant (if merchant instruments are modelled).

* INFO-level logs per S3 run summarising:

  * `(manifest_fingerprint, seed, parameter_hash)`,
  * `status`, `error_code`,
  * `total_instruments`,
  * key splits (type, scheme, region, segment).

* DEBUG-level logs for:

  * cells where realised instrument densities deviate significantly from priors (beyond configured tolerances),
  * detailed RNG accounting when diagnosing `RNG_ACCOUNTING_MISMATCH`.

These logging conventions are not part of the strict contract; formats may change as long as the run-report semantics above are honoured.

---

### 10.6 Integration with higher-level monitoring

Higher-level monitoring / dashboards **MUST** be able to summarise S3’s health across worlds and seeds. At minimum:

* Per `manifest_fingerprint`:

  * S3 status per seed (PASS / FAIL / MISSING),
  * `total_instruments` per seed,
  * simple breakdowns (by instrument_type, scheme, region, segment).

* Cross-world views:

  * distribution of `total_instruments` across `(mf, seed)`,
  * counts of S3 FAILs by `error_code`,
  * correlations between S3 failures and upstream (S1/S2) failures.

Operators should be able to answer, from observability alone:

> “For this world and seed, did we generate a valid instrument universe? How big is it, and how is it distributed by type/segment/region?”

without directly querying raw S3 datasets.

These observability and run-report integration rules are **binding** for S3’s contract with the rest of the engine.

---

## 11. Performance & scalability *(Informative)*

6A.S3 is the **third big data-plane step** in Layer-3. In many designs it will produce **as many or more rows as S2** (accounts), depending on instrument density (cards per account, tokens per card, handles per account, etc.).

This section is **non-binding**. It describes how S3 is expected to scale and which levers you have to keep it sane. The binding behaviour remains in §§1–10 & 12.

---

### 11.1 Complexity profile

For a given `(manifest_fingerprint, seed)`, define:

* `P`  — number of parties in `s1_party_base_6A`.
* `A`  — number of accounts in `s2_account_base_6A`.
* `R`  — number of regions/countries S3 uses.
* `S`  — number of segments.
* `T_acc` — number of account types.
* `T_instr` — number of instrument types.
* `C_acc` — number of **account cells** used in S2/S3 (e.g. combinations of `(region, party_type, segment, account_type)`).
* `C_instr` — number of **instrument cells** S3 uses (e.g. `(region, party_type, segment, account_type, instrument_type[, scheme])`).
* `I`  — total number of instruments realised by S3.

High-level complexity:

* **Phase 1 – load gates & priors/taxonomies:**

  * O(C_acc + C_instr + size(prior/taxonomy tables)) — small compared with A and I.
* **Phase 2 – continuous instrument targets:**

  * O(C_instr) — per-cell arithmetic.
* **Phase 3 – integerisation:**

  * O(C_instr) — plus a few RNG calls per group; negligible relative to I.
* **Phase 4 – allocation to accounts:**

  * O(A + I) — build per-cell account weights, then sample allocations; this is one of the dominant costs.
* **Phase 5 – instrument attributes:**

  * O(I × k) where `k` is number of attributes per instrument (constant).
* **Phase 6 – writing outputs & internal checks:**

  * O(I) for writing base table,
  * O(A × T_instr_eff)` for per-account links/holdings (effective number of types actually in use).

So overall, S3 is ~**O(I + A)** in time. As with S2, per-entity work dominates; priors/plans are cheap.

---

### 11.2 Expected sizes & regimes

Instrument density is typically modest but can explode if priors are mis-specified.

Rough expectations (you’ll pin actual numbers via priors):

* `P` ~ 10⁶–10⁷ parties.
* `A` ~ 1–5×P accounts depending on product mix.
* `I` (instruments):

  * low-density scenario: ~1–3 instruments per qualifying account → `I` ≈ few × A,
  * high-density (lots of tokens, multiple cards per account) can push `I` towards 5–10×A.

Optional views:

* account-instrument links: same order as I (per instrument) or `O(A × T_instr_eff)` (grouped).
* party holdings: `O(P × T_instr_eff)`; usually much smaller than I.
* instrument summary: `O(C_instr)` (hundreds–low thousands of rows).

Compared to L2:

* S3 will typically produce fewer rows than the full arrival stream (5B) but may be comparable to or larger than S2, depending on how aggressive your priors are.

---

### 11.3 Parallelism & sharding

S3 is highly parallelisable; you should expect to exploit this for larger worlds.

**Natural parallel axes:**

1. **Across seeds**

   * Each `(mf, seed)` is hermetic — independent universe.
   * This is the primary axis for horizontal sharding across workers.

2. **Across instrument cells within a seed**

   * Integerisation (Phase 3) and allocation/attribute sampling (Phases 4–5) can be done per instrument cell `c` or per group `(region, account_type, instrument_type[, scheme])`.

   To stay deterministic:

   * Define a fixed global ordering over cells/groups.
   * Derive RNG substreams from `(mf, seed, "6A.S3", substream_label, cell_id)` independent of scheduling.
   * Ensure canonical writer ordering is respected when writing outputs.

3. **Streaming / batched generation**

   * You don’t need all `I` instruments in memory:

     * For each cell or batch of cells:

       * compute `N_instr(c)`,
       * allocate to accounts,
       * generate instrument attributes,
       * stream rows to `s3_instrument_base_6A` in canonical order.

   * Maintain small, bounded per-cell / per-batch buffers rather than an `I`-sized in-memory table.

As long as:

* substreams are deterministically assigned,
* you respect canonical ordering at write time,

parallelism won’t change observable outputs.

---

### 11.4 Memory & IO characteristics

**Memory**

* Priors & taxonomies: small; cache fully.
* Instrument cell plan (`N_instr_target(c)`, `N_instr(c)`) across `C_instr`: small.
* Heavy parts: per-account weights + instrument instances. Those should be **streamed**.

Practical pattern:

* For each cell/group:

  * compute account weights,
  * sample allocations,
  * generate attributes,
  * write out instrument rows immediately.

* Keep only:

  * priors, taxonomies, and cell metadata in memory,
  * a working buffer per cell or small cell-batch.

**IO**

* Reads:

  * S1 base (`s1_party_base_6A`) — typically via grouped or indexed access by region/segment;
  * S2 base (`s2_account_base_6A`) — for owner accounts and their attributes;
  * priors/taxonomies/context surfaces — small relative to S1/S2.

* Writes:

  * dominated by `s3_instrument_base_6A` (I rows),
  * plus one smaller dataset for links and, optionally, holdings + summary.

Columnar formats with compression and sensible row-group sizes will help keep IO manageable.

---

### 11.5 RNG cost & accounting

RNG costs in S3 are moderate but not negligible for large I:

* **Count realisation** (`instrument_count_realisation`):

  * scales with `C_instr` (cells); usually trivial.

* **Account allocation** (`instrument_allocation_sampling`):

  * scales with I (for per-instrument draws) or with `(number of accounts per cell)` (for multinomial style allocation).

* **Attribute sampling** (`instrument_attribute_sampling`):

  * scales with `I × k`, where `k` is number of RNG-driven attributes (scheme, tier, expiry, flags, id components).

Guidance:

* Use vectorised Philox draws (per cell/batch) while still respecting:

  * the envelope (`blocks`, `draws` per event),
  * the deterministic mapping from context → substream.

* Use **coarse RNG events**:

  * one event per cell or cell×attribute-family, not per instrument,
  * but track totals carefully so that RNG accounting checks remain cheap and robust.

RNG accounting is about **auditability** and reproducibility, not throughput; but careless event granularity (one event per instrument) can create unnecessary overhead.

---

### 11.6 Operational tuning knobs

To keep S3 manageable across environments and worlds, you can expose **non-semantic** tuning knobs through priors/config (and therefore `parameter_hash`):

* **Instrument density factor**

  * Global or per-cell multiplier applied to `λ_instr_per_account(c)` before integerisation, e.g.:

    * 0.1× instruments per account in CI/dev,
    * 1× in production-scale runs.

  * Since it changes counts, it must be encoded in S3 priors and thus `parameter_hash`.

* **Per-account caps**

  * Hard caps such as:

    * max cards per consumer account,
    * max instruments per merchant account.

  * Used to prevent extreme outliers from tail behaviour; if caps cannot be satisfied, S3 fails cleanly rather than emitting skewed universes.

* **Global safety cap on `I`**

  * A ceiling on `N_instr_world_int` per `(mf, seed)`;
  * if exceeded due to misconfigured priors, S3 fails fast with a clear “too many instruments” error rather than overwhelming downstream stages.

* **Sharding configuration**

  * Optional configuration describing preferred per-cell or per-region sharding, which orchestration can use to balance work across workers.

All such knobs should live in the same sealed prior/config packs that S0 records; ad-hoc environment flags must not drive semantics.

---

### 11.7 Behaviour in stress & failure scenarios

Under misconfiguration or extreme worlds, you might see:

* `N_instr_world_int` exploding (e.g. overly aggressive instrument density).
* Very skewed distributions (e.g. some party or segment with huge instrument counts).

The intended behaviour:

* S3 detects gross inconsistencies and:

  * fails during target derivation (`INSTRUMENT_TARGETS_INCONSISTENT`), or
  * fails during integerisation (`INSTRUMENT_INTEGERISATION_FAILED`), or
  * fails during linkage enforcement (`LINKAGE_RULE_VIOLATION`).

* S3’s run-report and metrics should make the failure obvious:

  * unexpectedly high `total_instruments`,
  * extreme `instruments_per_account_*` metrics,
  * specific error codes pointing to priors or linkage rules.

For CI / development:

* Use smaller worlds (lower P, A) and/or lower instrument density factors, while keeping structure identical (same priors, same cell definitions).
* This lets you validate the logic at small scale and trust that it scales predictably when you crank priors up.

None of these performance notes change S3’s **binding** semantics; they’re here to guide an implementation that remains efficient, debuggable, and predictable as you scale to realistic “bank-sized” workloads.

---

## 12. Change control & compatibility *(Binding)*

This section fixes **how 6A.S3 is allowed to evolve** and what “compatible” means for:

* Upstream segments (1A–3B, 5A–5B).
* Upstream 6A states (S0, S1, S2).
* Downstream 6A states (S4–S5).
* 6B and any external consumers that rely on S3’s **instrument universe**.

Any change that violates these rules is a **spec violation**, even if an implementation appears to “work” in a specific deployment.

---

### 12.1 Versioning model for S3

S3 participates in the 6A versioning stack:

* `spec_version_6A` — overall 6A spec version (S0–S5).

* `spec_version_6A_S3` — effective version identifier for the S3 portion of the spec.

* Schema versions:

  * `schemas.6A.yaml#/s3/instrument_base`
  * `schemas.6A.yaml#/s3/account_instrument_links`
  * `schemas.6A.yaml#/s3/party_instrument_holdings` *(if present)*
  * `schemas.6A.yaml#/s3/instrument_summary` *(if present)*

* Catalogue versions:

  * `dataset_dictionary.layer3.6A.yaml` entries for S3 datasets.
  * `artefact_registry_6A.yaml` entries with `produced_by: 6A.S3` and S3 priors/taxonomies.

S3’s run-report MUST carry enough information (e.g. `spec_version_6A` and/or `spec_version_6A_S3`) that consumers can tell **which spec version** produced the instrument universe for a given `(manifest_fingerprint, seed)`.

---

### 12.2 Backwards-compatible changes (allowed within a major version)

The following changes are **backwards compatible**, provided all binding constraints in §§1–11 still hold:

1. **Adding optional fields to S3 outputs**

   * New, *optional* columns in:

     * `s3_instrument_base_6A`,
     * `s3_account_instrument_links_6A`,
     * optional holdings/summary datasets,

     that do not change the meaning of any existing fields.

   * Examples: additional static flags (`is_virtual_card`, `is_tokenised`), extra diagnostic tags, new banded attributes.

   * Existing consumers must be able to safely ignore unknown columns.

2. **Extending taxonomies**

   * Introducing new enum values for:

     * `instrument_type`, `scheme`, `brand_tier`, `token_type`, etc.,

     while preserving the semantics of existing values.

   * Consumers should be written to tolerate unknown enum values (e.g. treat them as generic until upgraded).

3. **Refining priors numerically under the same semantic model**

   * Adjusting numerical priors (e.g. `λ_instr_per_account(c)`, scheme mix per cell) while keeping:

     * the same structure (same conditioning variables, same cell definitions), and
     * the same qualitative behaviour (e.g. cards still used primarily for card-ready accounts).

   * This changes realised distributions but does not alter the *meaning* of fields or S3’s identity rules.

4. **Adding new S3 diagnostics / optional views**

   * Introducing new datasets clearly marked `status: optional` for QA/observability, as long as:

     * they are declared in the dictionary/registry,
     * they are explicitly derived from S3 base / S2 / S1,
     * no acceptance criteria in §8 depend on them.

5. **Implementation / performance optimisations**

   * Caching, parallelism, streaming, file layout choices, so long as they do not change:

     * the contents of S3 outputs (given the same inputs and seed),
     * RNG family semantics and event accounting,
     * run-report semantics.

These changes typically correspond to **minor/patch** bumps in `spec_version_6A` / `spec_version_6A_S3` and schema `semver`, but do not require changes in downstream consumers beyond the standard “ignore unknown fields” behaviour.

---

### 12.3 Soft-breaking changes (require coordination, can be staged)

The following changes can be made **compatible with care**, but require:

* Coordination between producers and consumers, and
* An explicit **spec/minor version bump** and migration notes.

1. **New required instrument attributes**

   * Making a currently optional column in `s3_instrument_base_6A` **required** (e.g. making `token_type` mandatory for certain instruments) is only safe if:

     * consumers are updated to understand it, or
     * you stage the change:

       1. Introduce the field as optional in the schema and populate it.
       2. Update consumers to recognise/use it.
       3. Promote it to required in a later minor/major version.

2. **New hard constraints in S3 priors/linkage rules**

   * Introducing stricter eligibility / min/max constraints that S3 MUST enforce (e.g. new caps on instruments per account or new region/scheme exclusions):

     * S3 will now reject worlds that were previously allowed (with specific error codes),
     * downstream expects fewer/more/differently distributed instruments.

   * This is soft-breaking from a modelling perspective and must be surfaced via version and documentation.

3. **New instrument types or schemes that are semantically distinct**

   * Adding new instrument types/schemes with non-trivial semantics (e.g. adding a new wallet type that 6B flows treat specially):

     * is backward compatible at the schema level,
     * but may require downstream code to be updated to handle the new types properly.

4. **New required S3 outputs**

   * If you add a new core S3 dataset (e.g. a dedicated base for merchant instruments) and mark it `status: required`, you must coordinate:

     * S3 production,
     * dictionary/registry updates,
     * downstream expectations.

In all these cases:

* bump **minor** `spec_version_6A_S3`,
* communicate clearly which worlds are on which version,
* and have downstream states branch or pin minimum S3 spec versions appropriately.

---

### 12.4 Breaking changes (require major version bump)

The following are **breaking** and MUST NOT be introduced without:

* a **major** bump to `spec_version_6A` / `spec_version_6A_S3`,
* updated schemas/dictionaries/registries, and
* explicit migration guidance for all S3 consumers (S4–S5, 6B, etc.).

1. **Changing S3 identity or partitioning**

   * Changing primary key semantics:

     * dropping or changing `instrument_id`,
     * removing `manifest_fingerprint` or `seed` from the logical PK,
     * changing `instrument_id` from “unique per `(mf, seed)`” to some other uniqueness law.

   * Changing partitioning:

     * altering `[seed, fingerprint]` to anything else,
     * adding `scenario_id` or other keys as partitions.

2. **Changing semantics of core fields**

   * Reinterpreting fields like:

     * `instrument_type`,
     * `scheme`,
     * `owner_party_id`, `owner_merchant_id`,
     * `masked_identifier`, `token_type`,
     * expiry fields,

     so that their meaning is no longer what this spec describes.

   * Reusing existing enum values for completely different constructs (e.g. reusing `CARD_PHYSICAL` to mean a non-card instrument).

3. **Changing the instrument-generation law**

   * Changing the **class of law** that maps priors → instrument counts → allocation → attributes in a way that invalidates downstream assumptions, for example:

     * introducing scenario-dependent instrument universes where S3 was originally scenario-independent,
     * moving from “one instrument universe per `(mf, seed)`” to multiple overlapping instrument universes.

   * Changing the mapping between RNG families and operations (e.g. using `instrument_count_realisation` for something completely different) is also behavioural and must be treated as breaking.

4. **Changing relationships with S1/S2**

   * Allowing instruments that are **not attached to accounts** (e.g. “free-floating” instruments) when the spec currently says every instrument must attach to an account.
   * Removing or weakening foreign key requirements from instruments to `s2_account_base_6A` or `s1_party_base_6A`.

5. **Removing or redefining core S3 datasets**

   * Removing `s3_instrument_base_6A` or `s3_account_instrument_links_6A`, or downgrading them from `status: required` to `status: optional`.
   * Replacing them with differently-shaped datasets without clear migration paths.

6. **Changing PASS criteria and gating semantics**

   * Changing S3’s PASS/FAIL definition in §8 in a way that:

     * makes previously failing worlds PASS *without* tightening checks elsewhere, or
     * makes previously PASS worlds systematically FAIL solely due to a spec-level change, not a bug fix.

Any of the above changes must be treated as a **new major spec version**. Downstream states must explicitly advertise support for that version before consuming worlds produced with it.

---

### 12.5 Compatibility obligations for downstream states

Downstream 6A states (S4–S5) and 6B have obligations under this spec:

1. **Version pinning**

   * Each state MUST declare a **minimum supported S3 spec version** (or range of `spec_version_6A` / `spec_version_6A_S3`), and:

     * inspect S3’s run-report,
     * fail fast if S3’s version for a given `(mf, seed)` is outside its supported band.

2. **Graceful handling of unknown fields**

   * Within a supported major version, downstream code MUST:

     * ignore unknown/optional fields in S3 datasets,
     * avoid strict “exact set of columns” checks.

3. **No hard-coded layout assumptions**

   * Downstream components MUST:

     * resolve S3 datasets via dictionary/registry + `schema_ref`,
     * not rely on specific file names beyond the templated paths,
     * not assume particular partition layouts other than `[seed, fingerprint]`.

4. **No re-definition of S3 semantics**

   * Downstream specs or code MUST NOT:

     * redefine what `instrument_type`, `scheme`, `instrument_id`, `account_id` mean,
     * treat additional ad-hoc datasets as authoritative for instruments.

   * S3’s base table is authoritative for instrument identity and classification; links/holdings/summary are derived views.

---

### 12.6 Migration & co-existence strategy

When a **breaking** S3 change is introduced:

* It MUST be accompanied by a new major `spec_version_6A` / `spec_version_6A_S3`.
* Worlds may be tagged in the catalogue and/or run-reports with the S3 spec version used to generate them.

Deployments that need to support multiple S3 versions at once can:

* Route different `(mf, seed)` universes to appropriate downstream pipelines based on their S3 spec version.
* Run some downstream components in dual-mode, handling both old and new S3 versions.
* Restrict certain features of downstream states (e.g. new fraud patterns) to worlds with a minimum S3 spec version.

However:

* A single `(manifest_fingerprint, seed)` MUST be internally consistent with a **single** S3 spec version.
* It is not permitted to merge S3 outputs from different spec versions into one logical universe.

---

### 12.7 Non-goals

This section does **not**:

* govern versioning of upstream segments (1A–3B, 5A–5B) — they have their own change-control specs,
* mandate how often priors are updated or how instrument density is tuned — that’s a modelling and parameterisation decision,
* define CI/CD pipelines or branching workflows.

It **does** require that:

* any observable change to S3 behaviour (schema, identity, instrument-generation law, gating semantics) is **explicitly versioned**,
* downstream components **never** assume compatibility from context alone,
* and any shift that affects identity, counts, or semantics of the instrument universe is treated as deliberate spec evolution, not a hidden implementation detail.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the short-hands and symbols used in **6A.S3**.
If anything here appears to contradict the binding sections (§1–§12), the binding sections (and JSON-Schemas) win.

---

### 13.1 Identity axes

* **`mf`**
  Shorthand for **`manifest_fingerprint`**.
  Identifies the sealed upstream world (L1+L2) and the 6A input universe. S3 never changes this.

* **`ph`**
  Shorthand for **`parameter_hash`**.
  Identifies the parameter / prior pack set for Layer-3, including S3 priors (instrument mix, per-account priors, linkage rules, attribute priors).

* **`seed`**
  RNG identity for S3 (and Layer-3 more broadly).
  Different seeds under the same `(mf, ph)` correspond to different party+account+instrument universes.

* **`party_id`**
  A party/customer identifier from S1. Uniquely identifies a party within `(mf, seed)`.

* **`account_id`**
  An account identifier from S2. Uniquely identifies an account within `(mf, seed)` and has a FK to `party_id`.

* **`instrument_id`**
  Instrument/credential identifier created by S3.
  Uniquely identifies an instrument within `(mf, seed)`; S3 guarantees uniqueness of `(mf, seed, instrument_id)`.

---

### 13.2 Cells, plans & counts

S3 plans instruments over **instrument cells** derived from accounts and parties.

Common sets:

* **`R`** — set of regions or countries, e.g. `region_id` or `country_iso`.
* **`T_party`** — set of party types (e.g. `RETAIL`, `BUSINESS`, `OTHER`).
* **`S_seg`** — set of segments (e.g. `STUDENT`, `SALARIED`, `SME`, `CORPORATE`, …).
* **`T_acc`** — set of account types (e.g. `CURRENT_ACCOUNT`, `SAVINGS_ACCOUNT`, `CREDIT_CARD`, …).
* **`T_instr`** — set of instrument types (e.g. `CARD_PHYSICAL`, `CARD_VIRTUAL`, `BANK_ACCOUNT_HANDLE`, `WALLET_ID`, `DIRECT_DEBIT_MANDATE`).
* **`Schemes`** — set of card/payment schemes/networks.

We use:

* **Account cell** (from S2, reused by S3):

  ```text
  b_acc ∈ B_acc ≔ (region_id, party_type, segment_id, account_type)
  ```

* **Instrument planning cell**:

  ```text
  c_instr ∈ C_instr ≔ (region_id, party_type, segment_id, account_type, instrument_type[, scheme])
  ```

Key quantities:

* **`N_accounts(b_acc)`**
  Number of accounts in base account cell `b_acc` (from S2).

* **`λ_instr_per_account(c_instr)`**
  Expected number of instruments of the given type (and scheme, if included) per account in cell `c_instr`.

* **`scale_context(c_instr)`**
  Deterministic scaling factor (e.g. from region-level card penetration or scenario/volume hints). Usually `1` unless context is enabled.

* **`N_instr_target(c_instr)`**
  Continuous target number of instruments in cell `c_instr`:

  ```text
  N_instr_target(c_instr) = N_accounts(b_acc(c_instr)) × λ_instr_per_account(c_instr) × scale_context(c_instr)
  ```

* **`N_instr(c_instr)`**
  Realised integer number of instruments in cell `c_instr` after integerisation.

* **`N_instr_world_int`**
  Total realised instruments in the world:

  ```text
  N_instr_world_int = Σ_{c_instr ∈ C_instr} N_instr(c_instr)
  ```

---

### 13.3 Taxonomy & attribute symbols

These refer to classification and static attributes in S3.

* **`instrument_type`**
  Enum describing the instrument/credential class, e.g.:

  * `CARD_PHYSICAL`, `CARD_VIRTUAL`,
  * `BANK_ACCOUNT_HANDLE`,
  * `WALLET_ID`, `DIRECT_DEBIT_MANDATE`, etc.

* **`token_type`**
  Enum describing the “kind” of identifier, e.g. `PAN`, `NETWORK_TOKEN`, `IBAN`, `ALIAS_ID`.

* **`scheme` / `network`**
  Payment scheme/network identifier, e.g. `VISA`, `MASTERCARD`, domestic scheme codes, SEPA, ACH.

* **`brand_tier`**
  Card or product tier, e.g. `STANDARD`, `GOLD`, `PLATINUM`, `BUSINESS`.

* **`masked_identifier`**
  Human-facing, non-sensitive representation of the instrument (e.g. `**** **** **** 1234`, masked IBAN).

* **Identifier components** (optional):

  * `bin_prefix` / `iin` — synthetic issuer identification number,
  * `last4` — last 4 digits of an instrument ID,
  * `issuer_country_iso` — issuer country for scheme card-like instruments.

* **Expiry fields** (if applicable):

  * `expiry_month`, `expiry_year` — static expiry for instruments that have an expiry concept (e.g. cards).

* **Static flags** (examples):

  * `contactless_enabled` — whether instrument supports contactless.
  * `virtual_only` — no physical counterpart.
  * `card_present_capable` / `card_not_present_capable` — whether instrument may be used in those contexts.

These are all **static** from S3’s perspective: later states must not change them.

---

### 13.4 Priors, linkage & holdings notation

* **`π_instr_type|cell(c_instr, t)`**
  Fractional prior (mix) for instrument types (or type+scheme) within a base account cell. Often folded into `λ_instr_per_account(c_instr)`.

* **Instrument-per-account distribution**
  Prior describing `P(k instruments of type t | account_cell b_acc)` for each account, including zero-inflation and caps.

* **`n_instr(a, c_instr)`**
  Realised number of instruments assigned to account `a` for instrument cell `c_instr`. Satisfies:

  ```text
  Σ_{accounts a in cell c_instr} n_instr(a, c_instr) == N_instr(c_instr)
  ```

* **`instrument_count(p, group)`**
  Instrument count recorded in per-party holdings for party `p` and a grouping (e.g. per instrument_type), always derived from base instruments via accounts.

* **Linkage / eligibility rules**
  Configuration that restricts or shapes:

  * which `(party_type, segment_id, region_id, account_type)` combinations may own which `instrument_type` / `scheme`,
  * min/max instruments per account and per party,
  * any mandatory instrument requirements (e.g. one debit instrument per current account).

S3 is responsible for respecting these rules when constructing the instrument universe.

---

### 13.5 Roles, statuses & scopes in `sealed_inputs_6A` (S3-relevant)

From `sealed_inputs_6A`:

* **`role`** (S3 cares about):

  * `PRODUCT_PRIOR` / `INSTRUMENT_PRIOR` — instrument mix and instruments-per-account priors.
  * `INSTRUMENT_LINKAGE_RULES` / `PRODUCT_LINKAGE_RULES` - eligibility and constraint configurations (contract ids: `instrument_linkage_rules_6A`, `product_linkage_rules_6A`).
  * `TAXONOMY` — instrument and scheme taxonomies, brand tiers, token types, etc.
  * `UPSTREAM_EGRESS` — context surfaces, e.g. region-level penetration.
  * `SCENARIO_CONFIG` — optional scenario/volume context (aggregated).
  * `CONTRACT` — S0/S3 schema/dictionary/registry artefacts (metadata only).

* **`status`**:

  * `REQUIRED` — S3 cannot run in its intended mode without this artefact.
  * `OPTIONAL` — S3 may take a simpler path (e.g. use default mixes) if absent.
  * `IGNORED` — S3 must not use this artefact.

* **`read_scope`**:

  * `ROW_LEVEL` — S3 may read the rows for business logic.
  * `METADATA_ONLY` — S3 may only test presence, shape, and digests (no row reads).

S3’s effective inputs are the intersection of `{REQUIRED, OPTIONAL}` and `ROW_LEVEL` rows relevant to its roles, plus the S1/S2 bases.

---

### 13.6 RNG symbols & families

S3 uses the shared Layer-3 Philox envelope with S3-specific RNG families:

* **Philox-2x64-10**
  Underlying counter-based RNG engine (common across the engine).

* **Substream / label**
  Logical name used when deriving Philox keys for S3, e.g.:

  * `"6A.S3.instrument_count_realisation"`
  * `"6A.S3.instrument_allocation_sampling"`
  * `"6A.S3.instrument_attribute_sampling"`

* **`instrument_count_realisation`** (contract id: `rng_event_instrument_count_realisation`; substream_label: `instrument_count_realisation`)
  RNG family used when converting `N_instr_target(c_instr)` into integer counts `N_instr(c_instr)`.

* **`instrument_allocation_sampling`** (contract id: `rng_event_instrument_allocation_sampling`; substream_label: `instrument_allocation_sampling`)
  RNG family used when allocating instruments to specific accounts within each cell (per-account draws).

* **`instrument_attribute_sampling`** (contract id: `rng_event_instrument_attribute_sampling`; substream_label: `instrument_attribute_sampling`)
  RNG family used when sampling per-instrument attributes (e.g. scheme if not fixed, brand tier, expiry, flags, identifier components).

* **`rng_event_instrument_count_realisation`**, **`rng_event_instrument_allocation_sampling`**, **`rng_event_instrument_attribute_sampling`**
  Logical RNG event types that record:

  * `counter_before`, `counter_after`,
  * `blocks`, `draws`,
  * contextual identifiers (world, seed, cell keys, attribute family),
  * optional summary stats.

All RNG usage must:

* respect the Layer-3 RNG envelope,
* be fully accounted in RNG logs,
* be deterministic given `(mf, ph, seed)` and inputs.

---

### 13.7 Miscellaneous shorthand & conventions

* **“World”**
  Shorthand for “all artefacts tied to a single `manifest_fingerprint`”.

* **“Instrument universe”**
  The set of all `instrument_id` rows in `s3_instrument_base_6A` for a given `(mf, seed)`.

* **“Cell (instrument cell)”**
  Unless otherwise qualified, refers to an instrument planning cell `c_instr` combining region, party_type, segment_id, account_type, and instrument_type (and possibly scheme).

* **“Base table” (for S3)**
  Refers to `s3_instrument_base_6A` — the authoritative list of instruments/credentials.

* **“Links”**
  Short for `s3_account_instrument_links_6A` — per-account view of instruments.

* **“Holdings”**
  Short for `s3_party_instrument_holdings_6A` — per-party instrument holdings (optional).

* **“Summary”**
  Short for `s3_instrument_summary_6A` — aggregate counts by region/segment/account_type/instrument_type (optional).

* **“Conservation”**
  Used informally to mean “integer counts and derived views match the plan and base table”; e.g.:

  * Σ per-cell counts equals total base instruments,
  * links/holdings/summary aggregations match the base.

This appendix is **informative** and exists to make the rest of the S3 spec easier to read and implement.

---
