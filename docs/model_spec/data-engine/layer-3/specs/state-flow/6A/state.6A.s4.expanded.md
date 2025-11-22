# 6A.S4 — Devices, IPs & network graph (Layer-3 / Segment 6A)

## 1. Purpose & scope *(Binding)*

6A.S4 is the **device, IP and network-graph realisation state** for Layer-3 / Segment 6A.
Its job is to take the **party universe** (S1), the **account & product universe** (S2), and the **instrument universe** (S3), and turn them into a **closed-world device/IP graph** for each `(manifest_fingerprint, seed)`.

Concretely, S4 must:

* Create the set of **devices** that exist in the synthetic bank, for example:

  * customer devices (phones, tablets, laptops, browsers),
  * merchant devices (POS terminals, kiosks, ATMs),
  * any other client endpoints that show up in access logs and transaction metadata.
* Create the set of **IP / network endpoints**, for example:

  * residential IPs,
  * mobile / carrier IPs,
  * corporate / branch IPs,
  * data-centre / cloud / hosting IPs,
  * VPN / proxy / anonymiser IP ranges.
* Attach these devices and IPs to existing entities to form a **static interaction graph**, including edges such as:

  * device ↔ party (primary owner or household/shared devices),
  * device ↔ account and/or instrument (accounts primarily accessed from the device),
  * device ↔ merchant (merchant-owned POS/terminal fleets),
  * IP ↔ device (device last-seen / typical endpoints),
  * IP ↔ party / merchant (if you carry direct edges at that level).

Within 6A, S4 is the **sole authority** on:

* **Device existence and identity** — which `device_id`s exist for a given `(manifest_fingerprint, seed)` and their static attributes (device_type, OS/UA families, simple risk tags).
* **IP / endpoint existence and identity** — which `ip_id`s exist (or endpoint IDs, if abstracted) and their static attributes (ip_type, ASN/ISP class, coarse geo, static risk tags).
* **Static graph structure** — which devices/IPs are attached to which parties/accounts/instruments/merchants at initialisation (who appears to “share” what with whom, ignoring time).

S4’s scope is **deliberately limited**:

* S4 **does not**:

  * create or modify parties (S1’s responsibility),
  * create or modify accounts/products (S2’s responsibility),
  * create or modify instruments/credentials (S3’s responsibility),
  * simulate **sessions**, **requests**, or **transactions** (that is 6B’s job),
  * assign **fraud roles** or dynamic risk flags (those are reserved for the fraud posture state, e.g. S5).
* S4 **does not** alter or reinterpret upstream Layer-1 / Layer-2 constructs:

  * merchants, sites, civil time, zones, routing, arrival intensities and realised arrivals remain under 1A–3B and 5A–5B and are treated as sealed context.

Within Layer-3, S4 sits **downstream of S0–S3**:

* It only runs for worlds where:

  * S0 has sealed the 6A input universe (`sealed_inputs_6A` + `s0_gate_receipt_6A` PASS), and
  * S1, S2 and S3 are all PASS for the same `(manifest_fingerprint, seed)` and have produced consistent party, account and instrument universes.
* It uses **device priors**, **IP priors**, **device/IP taxonomies**, and **graph/linkage rules** (sealed by S0) to:

  * decide how many devices and IPs exist per region/segment/product cell, and
  * wire those devices and IPs into a static graph over parties, accounts, instruments and merchants, subject to configured sharing patterns and degree constraints.

All later 6A states (e.g. fraud posture) and 6B’s flow/fraud logic must treat S4’s device/IP bases and link tables as **read-only ground truth** for:

> “which devices and IPs exist in this world, and how they are statically wired to parties, accounts, instruments and merchants”

for that `(manifest_fingerprint, seed)`.

---

## 2. Preconditions, upstream gates & sealed inputs *(Binding)*

6A.S4 only runs where **Layer-1, Layer-2, 6A.S0, 6A.S1, 6A.S2 and 6A.S3 are already sealed** for the relevant world and seed, and where the **S4-specific priors/configs** have been sealed into `sealed_inputs_6A`.

This section fixes those preconditions and the **minimum sealed inputs** S4 expects to see.

---

### 2.1 World-level preconditions (Layer-1 & Layer-2)

For a given `manifest_fingerprint` that S4 will serve, the engine MUST already have:

* Successfully run all required upstream segments:

  * Layer-1: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.
  * Layer-2: `5A`, `5B`.

* Successfully verified their HashGates (validation bundles + PASS flags), as recorded by 6A.S0.

S4 **does not** re-implement upstream HashGate logic. It **trusts S0’s view** via `s0_gate_receipt_6A`:

* For this `manifest_fingerprint`, every required segment in `upstream_gates` MUST have:

```text
gate_status == "PASS"
```

If any required segment has `gate_status ∈ {"FAIL","MISSING"}`, S4 MUST treat the world as **not eligible** and fail fast with a gate error (e.g. `6A.S4.S0_S1_S2_S3_GATE_FAILED`).

---

### 2.2 6A.S0 preconditions (gate & sealed inputs)

S4 is not allowed to run unless the **6A.S0 gate is fully satisfied**.

For the target `manifest_fingerprint`, S4 MUST:

1. **Validate S0 artefacts**

   * Confirm `s0_gate_receipt_6A` and `sealed_inputs_6A` exist under the correct `fingerprint={manifest_fingerprint}` partitions.
   * Validate both against their schema anchors in `schemas.layer3.yaml`:

     * `#/gate/6A/s0_gate_receipt_6A`
     * `#/gate/6A/sealed_inputs_6A`.

2. **Verify sealed-inputs digest**

   * Recompute `sealed_inputs_digest_6A` from `sealed_inputs_6A` using the canonical row encoding and ordering defined in S0.
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

If any of these checks fails, S4 MUST NOT attempt to read priors or generate any devices/IPs for that world and MUST fail with a S0/inputs gate error.

---

### 2.3 6A.S1, 6A.S2 and 6A.S3 preconditions (party, account & instrument bases)

S4 sits directly downstream of S1, S2 and S3. For each `(manifest_fingerprint, seed)` S4 will process, it MUST ensure that **all three** upstream 6A states are PASS and their bases are available and valid.

For the target `(mf, seed)`:

1. **S1 (party base) preconditions**

   * Latest 6A.S1 run-report for `(mf, seed)` has:

```text
status     == "PASS"
error_code == "" or null
```

* `s1_party_base_6A` partition for `(seed={seed}, fingerprint={mf})`:

  * exists,
  * validates against `schemas.6A.yaml#/s1/party_base`,
  * has `COUNT(*) == total_parties` in the S1 run-report.

2. **S2 (account base) preconditions**

   * Latest 6A.S2 run-report for `(mf, seed)` has:

```text
status     == "PASS"
error_code == "" or null
```

* `s2_account_base_6A` and `s2_party_product_holdings_6A` partitions for `(seed={seed}, fingerprint={mf})`:

  * exist,
  * validate against their schema anchors,
  * `COUNT(*)` over `s2_account_base_6A` equals `total_accounts` in the S2 run-report.

3. **S3 (instrument base) preconditions**

   * Latest 6A.S3 run-report for `(mf, seed)` has:

```text
status     == "PASS"
error_code == "" or null
```

* `s3_instrument_base_6A` and `s3_account_instrument_links_6A` partitions for `(seed={seed}, fingerprint={mf})`:

  * exist,
  * validate against their schema anchors,
  * have counts that match S3 run-report metrics (e.g. `total_instruments`).

If **any** of S1, S2 or S3 is missing or not PASS for `(mf, seed)`, S4 MUST fail with `6A.S4.S0_S1_S2_S3_GATE_FAILED` (or equivalent) and MUST NOT construct any device/IP/graph outputs for that world+seed.

---

### 2.4 Required sealed inputs for S4

S4 may only read artefacts that appear in `sealed_inputs_6A` for its `manifest_fingerprint` and have:

* `status ∈ {"REQUIRED","OPTIONAL"}`, and
* `read_scope = "ROW_LEVEL"` for data-level logic, or
* `read_scope = "METADATA_ONLY"` where only presence/shape is consulted.

Among those, S4 requires at minimum:

#### 2.4.1 Device priors & taxonomies

Artefacts with roles such as `"DEVICE_PRIOR"`, `"PRODUCT_PRIOR"` (if reused), or similar:

* **Device count priors**:

  * expected number of devices per “entity cell”, e.g. per `(region, party_type, segment_id)` or `(region, segment, account_type)`;
  * distributions for devices per party/account/merchant (e.g. `P(k devices | cell)`).

* **Device taxonomies** (`role="TAXONOMY"`):

  * `device_type` (e.g. `MOBILE_PHONE`, `TABLET`, `DESKTOP`, `POS_TERMINAL`, `ATM`, `KIOSK`),
  * `os_family` (e.g. `ANDROID`, `IOS`, `WINDOWS`, `LINUX`, embedded OS families),
  * `ua_family` / browser families if modelled,
  * any device-level risk tags or categories (e.g. `JAILBROKEN`, `ROOTED`, `EMULATOR`) if they are static.

These artefacts MUST be present and schema-valid if the S4 schemas reference their enums.

#### 2.4.2 IP / endpoint priors & taxonomies

Artefacts with roles such as `"IP_PRIOR"`, `"ENDPOINT_PRIOR"`, `"TAXONOMY"`:

* **IP count priors**:

  * expected number of IPs per device/party/merchant or per IP-type cell (e.g. `(region, ip_type)`),
  * distributions for IPs per device/party (e.g. “how many distinct IPs a device typically uses”).

* **IP taxonomies**:

  * `ip_type` (e.g. `RESIDENTIAL`, `MOBILE`, `CORPORATE`, `DATACENTRE`, `VPN_PROXY`),
  * `asn_class` / ISP classes (e.g. `CONSUMER_ISP`, `MNO`, `HOSTING`, `ENTERPRISE`),
  * static IP risk categories (if modelled).

Again, required taxonomies must appear in `sealed_inputs_6A` and be schema-valid.

#### 2.4.3 Graph / linkage rules

Artefacts (priors or config packs) with roles like `"GRAPH_LINKAGE_RULES"`, `"DEVICE_LINKAGE_RULES"`:

* allowed / typical patterns such as:

  * device sharing patterns:

    * probability that a device is single-party vs shared across multiple parties,
    * typical number of parties/accounts per shared device.

  * IP sharing patterns:

    * typical number of devices per IP (e.g. home router vs public WiFi vs datacentre IP),
    * typical number of parties per IP, per IP_type.

  * constraints:

    * max devices per party/account/merchant,
    * max IPs per device,
    * forbidden combinations (e.g. certain device types cannot belong to certain segments, certain IP types disallowed for some regions or merchant types).

If S4 treats these as required to enforce graph structure, they MUST be present in `sealed_inputs_6A` with `status="REQUIRED"` and `read_scope="ROW_LEVEL"`.

#### 2.4.4 6A contracts (metadata-only)

From `sealed_inputs_6A` with `role="CONTRACT"` and `read_scope="METADATA_ONLY"`:

* `schemas.layer3.yaml`
* `schemas.6A.yaml`
* `dataset_dictionary.layer3.6A.yaml`
* `artefact_registry_6A.yaml`

S4 uses these to:

* resolve S4 output dataset IDs, schema refs, and paths,
* ensure its outputs are declared consistently with the catalogue.

S4 MUST NOT modify these artefacts.

#### 2.4.5 Optional upstream context

If the design uses them and they are present in `sealed_inputs_6A`, S4 MAY also read:

* **Geo / connectivity surfaces**:

  * e.g. “mobile vs fixed broadband penetration per region”,
  * “typical ASN mix per country”.

* **Merchant / channel surfaces**:

  * e.g. which merchants are more online/mobile, which are more in-store, to bias device/IP attachment.

Such context artefacts MUST:

* have appropriate `role` (e.g. `UPSTREAM_EGRESS`, `POPULATION_PRIOR`, `SCENARIO_CONFIG`),
* have `read_scope` consistent with intended use (`ROW_LEVEL` for data; `METADATA_ONLY` for presence/shape only).

They are **hints**, not new authorities.

---

### 2.5 Axes of operation: world & seed

S4’s natural domain is the pair `(manifest_fingerprint, seed)`:

* `manifest_fingerprint` identifies the sealed upstream world and 6A input universe.
* `seed` identifies the specific party+account+instrument+device/IP realisation for that world.

Per axis:

* For each `manifest_fingerprint`:

  * S0 MUST be PASS and upstream HashGates MUST be PASS,
  * S4 MUST only use inputs artefacts listed in `sealed_inputs_6A` for that world.

* For each `(mf, seed)`:

  * S1, S2 and S3 MUST all be PASS and have produced their bases,
  * S4 then constructs **one** device/IP graph on top of that world+seed.

Scenario identity (`scenario_id`) is **not** an axis for S4:

* devices and IPs are not re-realised per scenario; they are shared across scenarios in 6B,
* if a future version introduces scenario-dependent devices/IPs, that will be a breaking change and MUST be versioned accordingly.

---

### 2.6 Out-of-scope inputs

S4 explicitly **must not depend on**:

* individual arrivals from `arrival_events_5B` (no per-event logic here),
* any 6B datasets (flows, labels, features),
* environment or wall-clock time (beyond non-semantic `created_utc` audit fields),
* any artefact **not present** in `sealed_inputs_6A` for this `manifest_fingerprint`,
* any artefact present but marked with `read_scope="METADATA_ONLY"` for row-level logic.

Any implementation that reads such inputs is **out of spec**, even if it appears to work.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes, for **6A.S4**, exactly:

* **what it is allowed to read**, and
* **who is allowed to define what** (L1, L2, S0–S3, S4),

so that later 6A states (S5) and 6B can safely assume S4 never redraws upstream responsibilities or pulls in “mystery” inputs.

S4 **must only** consume artefacts that:

* appear in `sealed_inputs_6A` for its `manifest_fingerprint` with `status ∈ {"REQUIRED","OPTIONAL"}`, and appropriate `read_scope`, **plus**
* the party, account and instrument bases from S1, S2 and S3.

Anything else is out of bounds.

---

### 3.1 Logical inputs S4 is allowed to use

Subject to §2 and `sealed_inputs_6A`, S4’s inputs fall into four groups.

#### 3.1.1 S0 / S1 / S2 / S3 control-plane & base inputs

These are mandatory and **read-only**:

* **From 6A.S0** (control plane):

  * `s0_gate_receipt_6A`

    * fixes `manifest_fingerprint`, `parameter_hash`,
    * records upstream gate statuses (`upstream_gates`),
    * carries `sealed_inputs_digest_6A` and 6A contract/priors summary.

  * `sealed_inputs_6A`

    * enumerates all artefacts 6A may use, with:

      * `role`, `status`, `read_scope`,
      * `schema_ref`,
      * `path_template`, `partition_keys`,
      * `sha256_hex`.

* **From 6A.S1**:

  * `s1_party_base_6A`

    * authoritative party universe for `(mf, seed)`:

      * `party_id`,
      * party type (retail/business/other),
      * segment, home geography (country/region),
      * static attributes (e.g. lifecycle, income bands, etc.).

* **From 6A.S2**:

  * `s2_account_base_6A`

    * authoritative account/product universe for `(mf, seed)`:

      * `account_id`,
      * `owner_party_id`, optional `owner_merchant_id`,
      * `account_type`, `product_family`, `currency_iso`, region, static account flags.

  * `s2_party_product_holdings_6A`

    * per-party product holdings; used only as a convenience/QA surface where helpful.

* **From 6A.S3**:

  * `s3_instrument_base_6A`

    * authoritative instrument universe:

      * `instrument_id`,
      * `account_id`, optional `owner_party_id`/`owner_merchant_id`,
      * `instrument_type`, `scheme`, static flags.

  * `s3_account_instrument_links_6A`

    * per-account instrument links, used to understand which accounts are “carded”, tokenised, etc.

S4 MUST treat:

* S0 as the *only* description of what is sealed and trusted,
* S1 as the **only** authority on parties,
* S2 as the **only** authority on accounts,
* S3 as the **only** authority on instruments.

S4 may only **reference** these bases; it may not change them.

---

### 3.1.2 S4 priors & taxonomies (ROW_LEVEL)

From `sealed_inputs_6A` with `status ∈ {"REQUIRED","OPTIONAL"}` and `read_scope = "ROW_LEVEL"`:

* **Device priors** (role e.g. `"DEVICE_PRIOR"` / `"PRODUCT_PRIOR"`):

  * distributions for **devices per entity**, e.g.:

    * `P(k devices | region, party_type, segment)` per party,
    * `P(k devices | merchant_type, region)` per merchant,
    * optional `P(k devices | account_type, instrument_type)` if you bias devices by product.

  * optional splits by device_type (e.g. fraction of devices that are mobile vs desktop vs POS).

* **Device taxonomies** (`role="TAXONOMY"`):

  * `device_type` (MOBILE_PHONE, TABLET, DESKTOP, POS_TERMINAL, ATM, KIOSK, …),
  * `os_family` (ANDROID, IOS, WINDOWS, LINUX, etc.),
  * `ua_family` (browser / app families) if modelled,
  * any static device risk tags (e.g. `EMULATOR`, `ROOTED`) if the model uses them at S4.

* **IP / endpoint priors** (role e.g. `"IP_PRIOR"` / `"ENDPOINT_PRIOR"`):

  * distributions for **IPs per entity/device**, e.g.:

    * `P(k IPs | device_type, region)` per device,
    * `P(k IPs | party_type, segment, region)` per party, if direct edges exist,
    * `P(k IPs | merchant_type, region)` for merchant endpoints.

  * IP-type mix per cell (`π_ip_type|cell`) — share of RESIDENTIAL vs MOBILE vs CORPORATE vs DATACENTRE vs VPN_PROXY.

* **IP taxonomies** (`role="TAXONOMY"`):

  * `ip_type` enum (RESIDENTIAL, MOBILE, CORPORATE, DATACENTRE, VPN_PROXY, …),
  * `asn_class` (CONSUMER_ISP, MNO, HOSTING_PROVIDER, ENTERPRISE, …),
  * optional static risk classes (e.g. `KNOWN_PROXY_PROVIDER`).

* **Graph / linkage rules** (role e.g. `"GRAPH_LINKAGE_RULES"`, `"DEVICE_LINKAGE_RULES"`):

  * *Device sharing*:

    * probabilities of single-party vs multi-party devices,
    * max/min parties per device,
    * patterns like “household devices” vs “personal devices”.

  * *IP sharing*:

    * distributions of devices per IP and parties per IP for each `ip_type`/`asn_class`,
    * special rules for data-centre/VPN IPs (large fan-out, many parties).

  * *Attachment constraints*:

    * max devices per party/account/merchant,
    * max IPs per device/party/merchant,
    * disallowed combinations (e.g. some device types not allowed for certain segments, some ip_types disallowed for some regions or merchant types).

S4 uses these priors/configs to:

* compute continuous and integer device/IP targets at the “cell” level, and
* realise a device/IP graph that respects these sharing and eligibility rules.

---

### 3.1.3 Optional upstream context (ROW_LEVEL or METADATA_ONLY)

If present in `sealed_inputs_6A` and selected by the design, S4 MAY also consume **context surfaces**:

* **Geo / connectivity surfaces** (role `"UPSTREAM_EGRESS"` / `"POPULATION_PRIOR"`):

  * region-level stats like mobile vs fixed broadband penetration,
  * typical ASN mix per country,
  * regional “online-ness” indices.

* **Merchant / channel surfaces**:

  * e.g. share of e-commerce vs physical POS for a merchant segment,
  * may influence how many POS terminals or mobile devices a merchant is assigned.

* **Scenario / volume hints** (role `"SCENARIO_CONFIG"` / `"UPSTREAM_EGRESS"`):

  * aggregated hints from L2 (not per-arrival) about expected channel mix (e.g. proportion of CNP vs CP traffic in a region).

Usage rules:

* If `read_scope="ROW_LEVEL"`, S4 may use row data to tilt device/IP priors (e.g. more mobiles in mobile-heavy regions).
* If `read_scope="METADATA_ONLY"`, S4 may only test presence/version/digests (e.g. a boolean “volume-aware mode is enabled”) and must not read rows.

These context artefacts are **hints only** — they do not override taxonomies or define identity.

---

### 3.1.4 6A contracts & schemas (METADATA_ONLY)

From `sealed_inputs_6A` with `role="CONTRACT"` and `read_scope="METADATA_ONLY"`:

* `schemas.layer3.yaml`
* `schemas.6A.yaml`
* `dataset_dictionary.layer3.6A.yaml`
* `artefact_registry_6A.yaml`

S4 uses these to:

* discover dataset IDs, `schema_ref`s, and path templates for S4 outputs,
* ensure its outputs follow the declared shapes and partitioning.

S4 MUST NOT modify or reinterpret these contracts.

---

### 3.2 Upstream authority boundaries (Layer-1 & Layer-2)

S4 sits on top of a sealed world from Layers 1 and 2. The following authority boundaries are **binding**.

#### 3.2.1 Merchants, sites, geo & time (1A–2A)

**Authority:**

* 1A — merchants, `merchant_id`, outlet catalogue, merchant metadata (MCC, channels, home country).
* 1B — site locations (lat/lon per outlet).
* 2A — civil time (`site_timezones`, `tz_timetable_cache`) and IANA tz semantics.

S4 **must not**:

* create or delete merchants or sites,
* change merchant attributes (MCC, channel, geo),
* modify site coordinates or assign new timezones.

S4 **may**:

* derive geo hints for devices/IPs (e.g. “device home region”, “IP country”) using upstream geo assets and taxonomies, but only through artefacts listed in `sealed_inputs_6A` (e.g. reference tables), and must not contradict upstream geometry/time.

#### 3.2.2 Zones, routing & virtual overlay (2B, 3A, 3B)

**Authority:**

* 2B — routing and site selection (how flows get to `site_id`/`edge_id`).
* 3A — zone allocations (`zone_alloc`, `zone_alloc_universe_hash`).
* 3B — virtual merchants & CDN edge universe.

S4 **must not**:

* reinterpret routing weights or alias laws,
* change how zones are defined or how merchants are cross-zoned,
* modify or depend on individual routing decisions for arrivals.

S4 **may**:

* use high-level information (e.g. “merchant is heavily virtual/online”, “multi-zone merchant”) — via upstream egress that S0 has sealed — to influence device/IP priors (e.g. more data-centre IPs for virtual merchants).

#### 3.2.3 Intensities & arrivals (5A, 5B)

**Authority:**

* 5A — arrival surfaces (λ).
* 5B — realised arrival skeleton (`arrival_events_5B`).

S4 **must not**:

* read or adjust individual arrivals,
* change arrival counts or timings,
* attach devices/IPs directly to specific arrivals — that is 6B’s job.

Any use of volume information must come through explicitly sealed aggregates (if any) and only to shape priors, not to touch event streams.

---

### 3.3 6A authority boundaries: S1 vs S2 vs S3 vs S4 vs S5/6B

Within Layer-3, each state owns a distinct piece of the world.

#### 3.3.1 S1 ownership (parties)

S1 is the sole authority on:

* which `(mf, seed, party_id)` exist,
* party types, segments, home geography, and S1-owned static attributes.

S4 **must not**:

* create or delete parties,
* change S1 attributes.

S4 may only reference `party_id` and S1 attributes when deciding device/IP counts and connections.

#### 3.3.2 S2 ownership (accounts/products)

S2 is the sole authority on:

* which `(mf, seed, account_id)` exist,
* mapping `account_id → owner_party_id / owner_merchant_id`,
* static account attributes (account_type, product_family, currency, flags).

S4 **must not**:

* create or delete accounts,
* change any S2 attributes.

S4 may only attach devices/IPs to existing accounts, and must obey any account-level constraints derived from S2.

#### 3.3.3 S3 ownership (instruments)

S3 is the sole authority on:

* which `(mf, seed, instrument_id)` exist,
* mapping `instrument_id → account_id / owner_party_id / owner_merchant_id` (if carried),
* static instrument attributes (instrument_type, scheme, brand, masked identifiers, flags).

S4 **must not**:

* create or delete instruments,
* change S3 fields.

S4 may reference `instrument_id` in its graph edges (e.g. to represent device↔instrument relationships) but must never introduce instruments or mutate S3 outputs.

#### 3.3.4 S4 ownership (devices, IPs, graph)

S4 exclusively owns:

* **Device universe:**

  * which `device_id` values exist per `(mf, seed)`,
  * static device attributes (device_type, os_family, ua_family, static risk tags).

* **IP / endpoint universe:**

  * which `ip_id` (and masked endpoint representations) exist per `(mf, seed)`,
  * static IP attributes (ip_type, asn_class, geo hints, static risk tags).

* **Static graph structure:**

  * which devices are linked to which parties/accounts/instruments/merchants,
  * which IPs are linked to which devices/parties/merchants,
  * degree distributions and sharing patterns implied by those links.

No other state may create devices/IPs or change these static links. Later states may *read* and *derive* from this graph; they must not mutate it.

#### 3.3.5 Later states (S5 & 6B) boundaries

S4 **must not**:

* assign static or dynamic fraud roles (e.g. “risky device”, “mule IP”) — that belongs to S5 or 6B’s labelling logic,
* create flows, sessions, or transaction events — that is 6B.

S5 and 6B may:

* attach fraud labels or dynamic risk measures to `device_id` / `ip_id` / edges,
* attach flows/transactions to devices/IPs,

but they must treat S4’s base & link datasets as read-only ground truth for “who is connected to whom”.

---

### 3.4 Forbidden dependencies & non-inputs

S4 explicitly **must not depend on**:

* any dataset or config **not present** in `sealed_inputs_6A` for its `manifest_fingerprint`,

* any artefact present in `sealed_inputs_6A` with `read_scope="METADATA_ONLY"` for row-level business logic,

* external, non-catalogued sources of data or configuration, such as:

  * arbitrary files whose IDs don’t appear in the dataset dictionary/registry,
  * environment variables for anything other than non-semantic knobs (e.g. logging),
  * wall-clock time (“now”), random OS state, process IDs as semantics,
  * network calls to external APIs or databases.

* raw upstream validation bundles beyond what S0 already validated (S4 has no business parsing their internals beyond any specific contract artefacts explicitly exposed in `sealed_inputs_6A` as `role="CONTRACT"`).

Any implementation behaviour that pulls in unsealed or out-of-catalogue inputs is **out of spec**, even if it appears to work in dev.

---

### 3.5 How S0’s sealed-input manifest constrains S4

S4’s **effective input universe** is:

> all rows in `sealed_inputs_6A` for its `manifest_fingerprint` with `status ∈ {"REQUIRED","OPTIONAL"}`, plus the bases from S1/S2/S3.

S4 MUST:

1. Load `s0_gate_receipt_6A` and `sealed_inputs_6A`.

2. Verify `sealed_inputs_digest_6A` matches the recomputed digest.

3. Filter `sealed_inputs_6A` to:

   * device priors and taxonomies,
   * IP priors and taxonomies,
   * graph/linkage rules,
   * optional context surfaces,
   * contracts (schemas/dictionary/registry, `METADATA_ONLY`).

4. Treat any artefact that:

   * is **absent** from `sealed_inputs_6A` for this `mf`,
   * or has `status="IGNORED"`,
   * or has `read_scope="METADATA_ONLY"` but is not a contract,

   as **out of bounds** for S4 business logic.

Downstream S5 and 6B can then safely assume:

* the device/IP graph was built solely from sealed, catalogued inputs for that world,
* there are no implicit, environment-specific dependencies, and
* any change to the priors/taxonomies/linkage rules will be reflected via a different `sealed_inputs_digest_6A` and thus correspond to a *different* world from S4’s point of view.

---

## 4. Outputs (datasets) & identity *(Binding)*

6A.S4 produces the **device & IP universes** and a small set of **graph/linkage views** that describe how those devices/IPs are wired to existing entities.

This section pins down *what* those datasets are, *what they mean*, and *how they are identified* in the world. All other S4 artefacts (planning tables, RNG logs, QA reports) are internal and not part of the public contract.

S4 has:

* **Required base datasets**

  * `s4_device_base_6A` — device universe.
  * `s4_ip_base_6A` — IP / endpoint universe.
* **Required link datasets**

  * `s4_device_links_6A` — device→entity edges.
  * `s4_ip_links_6A` — IP→entity/device edges.
* **Optional derived datasets**

  * `s4_entity_neighbourhoods_6A` — per-entity neighbourhood summaries.
  * `s4_network_summary_6A` — global graph diagnostics.

---

### 4.1 Required dataset — device base

**Logical name:** `s4_device_base_6A`
**Role:** the *only* authoritative list of devices that exist in the world for S4/6B.

#### 4.1.1 Domain & scope

For each `(manifest_fingerprint, seed)`, `s4_device_base_6A` contains **one row per device**.

* Domain axes:

  * `manifest_fingerprint` — world identity (same as S0–S3).
  * `parameter_hash` — parameter/prior-pack identity (embedded as a column).
  * `seed` — RNG identity for this party+account+instrument+device/IP realisation.

* S4 is **scenario-independent**:

  * the same device universe is shared across all scenarios for that `(mf, seed)`.

#### 4.1.2 Required content (logical fields)

Schema names can vary, but semantics are fixed. Each device row MUST include at least:

* **Identity & axes**

  * `device_id`

    * stable identifier for the device within `(manifest_fingerprint, seed)`,
    * globally unique per world+seed.
  * `manifest_fingerprint`
  * `parameter_hash`
  * `seed`

* **Device classification**

  * `device_type` — enum from device taxonomy, e.g.:

    * `MOBILE_PHONE`, `TABLET`, `LAPTOP`, `DESKTOP`,
    * `POS_TERMINAL`, `ATM`, `KIOSK`, etc.

  * `os_family` — enum, e.g. `ANDROID`, `IOS`, `WINDOWS`, `MACOS`, `LINUX`, `EMBEDDED`.

  * optional `ua_family` — browser/app family if user-agent is modelled.

  * optional `device_class` — coarse buckets (e.g. `CONSUMER_PERSONAL`, `CONSUMER_SHARED`, `MERCHANT_FIXED`, `MERCHANT_MPOS`).

* **Ownership & linkage context**

  These are *contextual*, not full graph edges (which live in link tables):

  * optional `primary_party_id` — FK into `s1_party_base_6A` for the “primary owner” party (for consumer devices).
  * optional `primary_merchant_id` — FK into merchant universe (for merchant-owned devices such as POS terminals).
  * optional `home_region_id` / `home_country_iso` — derived home region for the device (e.g. from primary owner or merchant).

  The full, many-to-many relationships (e.g. shared devices used by multiple parties) are expressed in `s4_device_links_6A`.

* **Static risk & capability flags (if modelled)**

  Examples:

  * `is_emulator`, `is_jailbroken`, `is_rooted` (flags for static risk posture).
  * `supports_biometric_auth`, `supports_3ds_app`, `supports_contactless`.
  * `device_risk_tier` — static tier enum (e.g. `LOW`, `STANDARD`, `HIGH`), derived from priors.

These attributes are **static from S4’s point of view**: later states can read them but must not modify them.

#### 4.1.3 Identity & invariants

For `s4_device_base_6A`:

* **Logical primary key:**

  ```text
  (manifest_fingerprint, seed, device_id)
  ```

* **Uniqueness:**

  * `device_id` MUST be unique within `(mf, seed)`.
  * No duplicate `(mf, seed, device_id)` rows.

* **World consistency:**

  * All rows in a `(seed={seed}, fingerprint={mf})` partition MUST have those `seed` and `manifest_fingerprint` values.
  * All rows for `(mf, seed)` MUST share the same `parameter_hash`.

* **Closed-world semantics for devices:**

  For a given `(mf, seed)`, the set of `device_id` values in `s4_device_base_6A` is the **complete device universe**. No other dataset may introduce new devices.

---

### 4.2 Required dataset — IP / endpoint base

**Logical name:** `s4_ip_base_6A`
**Role:** the *only* authoritative list of IPs / network endpoints that exist in the world for S4/6B.

#### 4.2.1 Domain & scope

For each `(manifest_fingerprint, seed)`, `s4_ip_base_6A` contains **one row per IP / endpoint**.

* Domain axes:

  * `manifest_fingerprint`, `parameter_hash`, `seed` — as above.

* The notion of “IP” here can be:

  * a single public IP,
  * a CIDR bucket, or
  * an abstracted endpoint (e.g. “residential endpoint #1234”) depending on modelling choice. The schema must encode what is being represented.

#### 4.2.2 Required content (logical fields)

Each row MUST include at least:

* **Identity & axes**

  * `ip_id` — stable identifier for the IP/endpoint within `(mf, seed)`.
  * `manifest_fingerprint`
  * `parameter_hash`
  * `seed`

* **IP / endpoint representation**

  Depending on your abstraction:

  * `ip_address_masked` — masked or bucketed IP (e.g. `192.0.2.0/24`, or obfuscated form).
  * optional `asn` / `asn_id` — ASN identifier if modelled.
  * optional `ip_prefix` / `cidr` — prefix notation if you use ranges.

* **Classification**

  * `ip_type` — enum from IP taxonomy, e.g.:

    * `RESIDENTIAL`, `MOBILE`, `CORPORATE`, `DATACENTRE`, `VPN_PROXY`, `PUBLIC_WIFI`.

  * `asn_class` — enum indicating provider type, e.g.:

    * `CONSUMER_ISP`, `MNO`, `HOSTING_PROVIDER`, `ENTERPRISE_NETWORK`.

  * optional `ip_risk_tier` — static risk tier (e.g. `STANDARD`, `SUSPICIOUS`, `HIGH_RISK`) if modelled at S4.

* **Geo & context**

  * `country_iso`, optional `region_id` — coarse geolocation for the IP/endpoint.
  * optional `city_bucket` / `geo_bucket` if you use coarser buckets.

These fields are **static**; dynamic usage (e.g. observed geo per session) is 6B’s responsibility.

#### 4.2.3 Identity & invariants

For `s4_ip_base_6A`:

* **Logical primary key:**

  ```text
  (manifest_fingerprint, seed, ip_id)
  ```

* **Uniqueness:**

  * `ip_id` MUST be unique within `(mf, seed)`.
  * No duplicate `(mf, seed, ip_id)` rows.

* **World consistency:**

  * All rows in a `(seed={seed}, fingerprint={mf})` partition MUST use those values.
  * All rows for `(mf, seed)` MUST share the same `parameter_hash`.

* **Closed-world semantics for IPs:**

  For a given `(mf, seed)`, the set of `ip_id` values in `s4_ip_base_6A` is the **complete IP/endpoint universe**. No other dataset may create new IPs.

---

### 4.3 Required datasets — link tables

Links express the **graph edges** between devices/IPs and entities. They are required because downstream states and 6B must be able to navigate the graph without recomputing it.

#### 4.3.1 Device links

**Logical name:** `s4_device_links_6A`
**Role:** device→entity edges (who uses what device).

Depending on your design, you may have a single wide table or multiple narrower ones (e.g. `device_party_links`, `device_account_links`, `device_merchant_links`). For this spec, we describe a unified logical view; if you physically split it, the union must still obey these semantics.

##### 4.3.1.1 Domain & scope

For each `(mf, seed)`, `s4_device_links_6A` contains **zero or more rows per device** describing its links to entities such as:

* parties (`party_id`),
* accounts (`account_id`),
* instruments (`instrument_id`),
* merchants (`merchant_id`).

##### 4.3.1.2 Required content (logical fields)

Minimum required fields:

* `manifest_fingerprint`, `parameter_hash`, `seed`.

* `device_id` — FK to `s4_device_base_6A`.

* One or more of:

  * `party_id` — FK to S1 base,
  * `account_id` — FK to S2 base,
  * `instrument_id` — FK to S3 base,
  * `merchant_id` — FK to merchant universe.

* `link_role` — enum describing the semantics, e.g.:

  * `PRIMARY_OWNER`,
  * `SECONDARY_USER`,
  * `MERCHANT_TERMINAL`,
  * `ASSOCIATED_ACCOUNT_ACCESS`, etc.

The exact set of link roles is part of the S4 taxonomy; this section just requires that there **is** such a field and that its semantics are fixed in the S4 schemas.

##### 4.3.1.3 Identity & invariants

* Logical key (for a single unified link table), for example:

  ```text
  (manifest_fingerprint, seed, device_id, party_id?, account_id?, instrument_id?, merchant_id?, link_role)
  ```

* Invariants:

  * Every `device_id` MUST exist in `s4_device_base_6A`.
  * All `party_id` / `account_id` / `instrument_id` / `merchant_id` values MUST resolve to existing entities in their respective bases.
  * Links MUST respect S4’s graph/linkage rules (no forbidden combinations, no exceeding configured max degrees).

---

#### 4.3.2 IP links

**Logical name:** `s4_ip_links_6A`
**Role:** IP→device/entity edges (who is seen behind which IPs).

Again, this may be a single wide table or multiple narrower ones; the logical semantics are the same.

##### 4.3.2.1 Domain & scope

For each `(mf, seed)`, `s4_ip_links_6A` contains **zero or more rows per IP** describing its links to:

* devices (`device_id`),
* parties (`party_id`),
* merchants (`merchant_id`), and any other entities you choose to directly connect.

##### 4.3.2.2 Required content (logical fields)

Minimum fields:

* `manifest_fingerprint`, `parameter_hash`, `seed`.

* `ip_id` — FK to `s4_ip_base_6A`.

* One or more of:

  * `device_id` — FK to `s4_device_base_6A`,
  * `party_id` — FK to S1 base,
  * `merchant_id` — FK to merchant universe.

* `link_role` — enum describing the semantics, e.g.:

  * `TYPICAL_DEVICE_IP`,
  * `RECENT_LOGIN_IP`,
  * `MERCHANT_ENDPOINT`,
  * `SHARED_PUBLIC_WIFI`, etc.

##### 4.3.2.3 Identity & invariants

* Logical key example:

  ```text
  (manifest_fingerprint, seed, ip_id, device_id?, party_id?, merchant_id?, link_role)
  ```

* Invariants:

  * Every `ip_id` MUST exist in `s4_ip_base_6A`.
  * Linked `device_id` / `party_id` / `merchant_id` MUST exist in their respective universes.
  * Sharing/degree patterns implied by links MUST respect graph/linkage priors/configs (e.g. distribution of devices per IP per `ip_type`).

---

### 4.4 Optional datasets — neighbourhood & network summary

These datasets are **optional** but, if implemented, MUST be strictly derived from the base and link datasets.

#### 4.4.1 `s4_entity_neighbourhoods_6A` (optional)

**Role:** pre-aggregated graph neighbourhood metrics per entity; convenient for QA and fraud-feature modelling.

* Domain: for each `(mf, seed)`, one or more rows per entity:

  * `party_id`,
  * `account_id`,
  * `instrument_id`,
  * `merchant_id`,

  depending on what you choose to include.

* Example fields per entity:

  * `device_count` — number of distinct devices linked to that entity.
  * `ip_count` — number of distinct IPs linked via devices or directly.
  * `shared_device_degree` — number of other parties sharing at least one device.
  * `shared_ip_degree` — number of other parties sharing at least one IP.
  * optional flags like `has_datacentre_ip`, `has_vpn_proxy_ip`.

**Invariants:**

* All counts and flags must be derivable by aggregating `s4_device_links_6A` and `s4_ip_links_6A` (plus the bases).
* No new entity identifiers may appear; all `party_id`/`account_id`/`instrument_id`/`merchant_id` values must exist upstream.

#### 4.4.2 `s4_network_summary_6A` (optional)

**Role:** global / per-segment diagnostics of the graph, used for QA and tuning.

* Domain: for each `(mf, seed)`, table of summary rows keyed by:

  * segment/region/product cell, or
  * global aggregate.

* Example metrics:

  * distributions (or coarse bins) of:

    * devices per party, accounts per device, parties per device,
    * devices per IP, parties per IP.

  * counts of special patterns:

    * number of parties with unusually many devices,
    * number of IPs with unusually high degree (potential proxies/datacentres),
    * counts of entities with no devices or no IPs (if that’s allowed/disallowed).

**Invariants:**

* All metrics must be calculable from `s4_device_base_6A`, `s4_ip_base_6A`, and link tables.
* No new IDs may appear; this is a pure diagnostic view.

---

### 4.5 Relationship to upstream and downstream identity

S4 outputs align with upstream identity and downstream expectations:

* **Upstream alignment:**

  * `manifest_fingerprint` and `parameter_hash` tie S4 to a sealed world and prior pack.
  * All FKs (`party_id`, `account_id`, `instrument_id`, `merchant_id`) refer to S1, S2, S3, and L1 universes.

* **Downstream alignment:**

  * S5 (fraud posture) and 6B (flows/fraud) will use:

    * `(mf, seed, device_id)` to index device-level risk and behaviour,
    * `(mf, seed, ip_id)` to index IP-level risk and behaviour,
    * link tables to compute shared-device/shared-IP structures, neighbourhood features, etc.

  * They MUST NOT:

    * introduce new devices/IPs,
    * change S4’s static attributes or edges.

* **Closed-world semantics for the graph:**

  * S1: **who exists** (parties).
  * S2: **what accounts/products exist and who owns them**.
  * S3: **what instruments exist and who owns them**.
  * **S4:** **what devices & IPs exist and how they are wired to entities**.
  * 6B: **when and how these entities, instruments, devices & IPs are used over time**, without changing the underlying graph.

The semantics and identity rules defined in this section are **binding**; the exact column names and JSON-Schema live in `schemas.6A.yaml`, but any implementation of S4 must respect these meanings for the device base, IP base, link tables, and optional graph summaries.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes **where the shapes for S4’s datasets live**, how they are wired into the **catalogue**, and how S4 and downstream states must discover and use them.

As with the rest of the engine:

* **JSON-Schema + dataset dictionary are the only shape authorities.**
* This doc defines semantics and constraints; it must not be treated as an alternative schema.

S4 has:

* **Required base datasets**

  * `s4_device_base_6A`
  * `s4_ip_base_6A`
* **Required link datasets**

  * `s4_device_links_6A`
  * `s4_ip_links_6A`
* **Optional derived datasets**

  * `s4_entity_neighbourhoods_6A`
  * `s4_network_summary_6A`

---

### 5.1 JSON-Schema anchors (shape authority)

All S4 dataset shapes live under **Layer-3 / 6A schemas**.

Binding anchors (names indicative, but paths must exist):

* `schemas.6A.yaml#/s4/device_base`
* `schemas.6A.yaml#/s4/ip_base`
* `schemas.6A.yaml#/s4/device_links`
* `schemas.6A.yaml#/s4/ip_links`
* `schemas.6A.yaml#/s4/entity_neighbourhoods` *(if implemented)*
* `schemas.6A.yaml#/s4/network_summary` *(if implemented)*

The schema files **must**:

* Reuse shared primitives/enums from `schemas.layer3.yaml` where appropriate (ID types, ISO codes, region IDs, risk tiers, etc.).
* Fully define:

  * columns,
  * types,
  * nullability,
  * per-field constraints (e.g. enum sets, FK-like constraints at schema level where supported).
* Use `additionalProperties: false` for record types unless there is a documented extensibility mechanism.

Informally, each anchor must encode the logical content from §4 (device/IP base, links, neighbourhoods, network summary). The JSON-Schema is the **source of truth**.

---

### 5.2 Dataset dictionary entries (catalogue links)

The Layer-3 / 6A dataset dictionary (`dataset_dictionary.layer3.6A.yaml`) MUST contain entries for all S4 datasets.

Below are informal sketches; the actual YAML in your repo will follow your house style.

#### 5.2.1 `s4_device_base_6A` (required)

```yaml
- id: s4_device_base_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    Device universe for Layer-3 / Segment 6A. One row per device per
    (manifest_fingerprint, seed), with device classification, primary
    owner context and static device risk/capability flags.
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s4_device_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_device_base_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [device_type, primary_party_id, primary_merchant_id, device_id]
  schema_ref: schemas.6A.yaml#/s4/device_base
  columns_strict: true
  lineage:
    produced_by: [ '6A.S4' ]
    consumed_by:
      - '6A.S5'
      - '6B.S0'
      - '6B.S1'
  pii_class: synthetic_customer
  retention_class: core_entity
```

Key binding points:

* Partitioning is exactly `[seed, fingerprint]`.
* `version` ties together `seed`, `manifest_fingerprint`, `parameter_hash`.
* `schema_ref` is the only shape authority; `columns_strict: true` must be set.

#### 5.2.2 `s4_ip_base_6A` (required)

```yaml
- id: s4_ip_base_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    IP / network endpoint universe for Layer-3 / Segment 6A. One row
    per IP/endpoint per (manifest_fingerprint, seed), including masked
    representation, ip_type, asn_class, geo hints and static risk tags.
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s4_ip_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_ip_base_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [ip_type, asn_class, country_iso, ip_id]
  schema_ref: schemas.6A.yaml#/s4/ip_base
  columns_strict: true
  lineage:
    produced_by: [ '6A.S4' ]
    consumed_by:
      - '6A.S5'
      - '6B.S0'
      - '6B.S1'
  pii_class: synthetic_customer
  retention_class: core_entity
```

#### 5.2.3 `s4_device_links_6A` (required)

```yaml
- id: s4_device_links_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    Device-to-entity edges for Layer-3 / Segment 6A. Links each
    device_id to one or more parties/accounts/instruments/merchants
    with a link_role describing the semantics.
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s4_device_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_device_links_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [device_id, party_id, account_id, instrument_id, merchant_id, link_role]
  schema_ref: schemas.6A.yaml#/s4/device_links
  columns_strict: true
  lineage:
    produced_by: [ '6A.S4' ]
    consumed_by:
      - '6A.S5'
      - '6B.S0'
      - '6B.S1'
  pii_class: synthetic_customer
  retention_class: core_entity
```

If you physically split links (e.g. device→party vs device→account), you’ll have multiple IDs here, but the logical semantics above must still be satisfied across them.

#### 5.2.4 `s4_ip_links_6A` (required)

```yaml
- id: s4_ip_links_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    IP-to-device/entity edges for Layer-3 / Segment 6A. Links each ip_id
    to one or more devices/parties/merchants with a link_role
    describing the semantics.
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s4_ip_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_ip_links_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [ip_id, device_id, party_id, merchant_id, link_role]
  schema_ref: schemas.6A.yaml#/s4/ip_links
  columns_strict: true
  lineage:
    produced_by: [ '6A.S4' ]
    consumed_by:
      - '6A.S5'
      - '6B.S0'
      - '6B.S1'
  pii_class: synthetic_customer
  retention_class: core_entity
```

#### 5.2.5 `s4_entity_neighbourhoods_6A` (optional)

```yaml
- id: s4_entity_neighbourhoods_6A
  owner_layer: 3
  owner_segment: 6A
  status: optional
  description: >
    Per-entity graph neighbourhood metrics for Layer-3 / Segment 6A
    (devices per party, IPs per device, shared-device/shared-IP
    degrees, etc.), derived from S4 base and link datasets.
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s4_entity_neighbourhoods_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_entity_neighbourhoods_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [entity_type, entity_id]
  schema_ref: schemas.6A.yaml#/s4/entity_neighbourhoods
  columns_strict: true
  lineage:
    produced_by: [ '6A.S4' ]
    consumed_by:
      - '6A.S5'
      - '6B.S0'
  pii_class: synthetic_customer
  retention_class: diagnostics
```

Where `entity_type`/`entity_id` encode whether the row is for a party, account, instrument, merchant, etc.

#### 5.2.6 `s4_network_summary_6A` (optional)

```yaml
- id: s4_network_summary_6A
  owner_layer: 3
  owner_segment: 6A
  status: optional
  description: >
    Aggregate graph diagnostics for Layer-3 / Segment 6A: degree
    distributions and sharing summaries per region/segment/account_type
    and globally.
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s4_network_summary_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_network_summary_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [region_id, segment_id, account_type, metric_id]
  schema_ref: schemas.6A.yaml#/s4/network_summary
  columns_strict: true
  lineage:
    produced_by: [ '6A.S4' ]
    consumed_by:
      - '6A.S4'   # QA
      - '6A.S5'
      - '6B.S0'
  pii_class: none
  retention_class: diagnostics
```

The exact grouping keys and metrics are defined in your S4 design and schema.

---

### 5.3 Artefact registry entries (runtime manifests)

`artefact_registry_6A.yaml` MUST register S4 datasets with stable `manifest_key`s and explicit dependencies.

#### 5.3.1 Device base registry entry

```yaml
- manifest_key: engine.layer3.6A.s4.device_base
  owner_layer: 3
  owner_segment: 6A
  dataset_id: s4_device_base_6A
  semver: 1.0.0
  path_template: data/layer3/6A/s4_device_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_device_base_6A.parquet
  partition_keys: [seed, fingerprint]
  schema_ref: schemas.6A.yaml#/s4/device_base
  produced_by: 6A.S4
  dependencies:
    - engine.layer3.6A.s0_gate_receipt
    - engine.layer3.6A.sealed_inputs
    - engine.layer3.6A.s1.party_base
    - engine.layer3.6A.prior.device_counts
    - engine.layer3.6A.taxonomy.devices
  retention_class: core_entity
  pii_class: synthetic_customer
```

#### 5.3.2 IP base registry entry

```yaml
- manifest_key: engine.layer3.6A.s4.ip_base
  owner_layer: 3
  owner_segment: 6A
  dataset_id: s4_ip_base_6A
  semver: 1.0.0
  path_template: data/layer3/6A/s4_ip_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_ip_base_6A.parquet
  partition_keys: [seed, fingerprint]
  schema_ref: schemas.6A.yaml#/s4/ip_base
  produced_by: 6A.S4
  dependencies:
    - engine.layer3.6A.s0_gate_receipt
    - engine.layer3.6A.sealed_inputs
    - engine.layer3.6A.prior.ip_counts
    - engine.layer3.6A.taxonomy.ips
  retention_class: core_entity
  pii_class: synthetic_customer
```

#### 5.3.3 Links registry entries

```yaml
- manifest_key: engine.layer3.6A.s4.device_links
  owner_layer: 3
  owner_segment: 6A
  dataset_id: s4_device_links_6A
  semver: 1.0.0
  path_template: data/layer3/6A/s4_device_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_device_links_6A.parquet
  partition_keys: [seed, fingerprint]
  schema_ref: schemas.6A.yaml#/s4/device_links
  produced_by: 6A.S4
  dependencies:
    - engine.layer3.6A.s4.device_base
    - engine.layer3.6A.s1.party_base
    - engine.layer3.6A.s2.account_base
    - engine.layer3.6A.s3.instrument_base
  retention_class: core_entity
  pii_class: synthetic_customer
```

```yaml
- manifest_key: engine.layer3.6A.s4.ip_links
  owner_layer: 3
  owner_segment: 6A
  dataset_id: s4_ip_links_6A
  semver: 1.0.0
  path_template: data/layer3/6A/s4_ip_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_ip_links_6A.parquet
  partition_keys: [seed, fingerprint]
  schema_ref: schemas.6A.yaml#/s4/ip_links
  produced_by: 6A.S4
  dependencies:
    - engine.layer3.6A.s4.ip_base
    - engine.layer3.6A.s4.device_base
    - engine.layer3.6A.s1.party_base
  retention_class: core_entity
  pii_class: synthetic_customer
```

Optional registry entries for `s4_entity_neighbourhoods_6A` and `s4_network_summary_6A` follow the same pattern, with `produced_by: 6A.S4` and dependencies on S4 base/link datasets.

These registry entries give CI/orchestration:

* stable keys to resolve S4 outputs,
* explicit dependency graphs for change impact and ordering.

---

### 5.4 Catalogue discovery rules (for S4 and downstream consumers)

All S4 implementations and all consumers of S4 outputs (S5, 6B, tooling) MUST use the catalogue, not hard-coded paths or ad-hoc schemas.

**Shape discovery:**

1. Given a dataset ID (e.g. `s4_device_base_6A`):

   * Look up the entry in `dataset_dictionary.layer3.6A.yaml`.
   * Read its `schema_ref`.
   * Resolve `schema_ref` in `schemas.6A.yaml` (and `schemas.layer3.yaml` for shared defs).
   * Treat the resolved JSON-Schema as the **only** shape authority.

2. Do **not** derive schemas from existing data, ORMs, or manually coded models; those must conform to `schemas.6A.yaml`, not redefine it.

**Location discovery:**

1. From the dictionary entry (and registry if needed):

   * Read `path` / `path_template` and `partitioning`.
   * Substitute `seed={seed}`, `fingerprint={manifest_fingerprint}` to compute the partition path.

2. Do **not** rely on hard-coded filesystem/object-store paths.

**No shadow datasets / shapes:**

* S4 MUST NOT write additional, undocumented tables for devices/IPs/links that are not in the dictionary/registry.
* Downstream states MUST NOT read “sidecar” variants of S4 outputs with altered schemas or locations.

**No hidden merge rules:**

* Merge/replace semantics for S4 datasets are defined in §7 (replace-not-append per `(mf, seed)`);
* Dictionary/registry partitioning/path templates must be consistent with those semantics.

With these anchors, dictionary entries and registry manifests in place, S4’s datasets are:

* globally **discoverable** via the catalogue,
* **uniquely shaped** by JSON-Schema,
* and correctly scoped to `(seed, manifest_fingerprint)` for consistent consumption across the rest of Layer-3 and 6B.

---

## 6. Deterministic algorithm (with RNG — device & IP counts & graph wiring) *(Binding)*

6A.S4 is **deterministic given**:

* the sealed 6A input universe (`s0_gate_receipt_6A`, `sealed_inputs_6A`),
* the S1/S2/S3 bases (`s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A` + links),
* S4 priors/configs (device/IP priors, taxonomies, graph/linkage rules),
* `manifest_fingerprint`, `parameter_hash`, and `seed`.

This section fixes **what S4 does, in which order, and which parts are RNG-bearing vs RNG-free**.
Implementers are free to choose data structures, batching and parallelism; they are **not** free to change the observable behaviour.

---

### 6.0 Overview & RNG discipline

For each `(manifest_fingerprint, seed)`:

1. Load gates, priors, taxonomies & graph rules (RNG-free).
2. Define planning domains & derive **continuous targets** for devices/IPs per cell (RNG-free).
3. Realise **integer device counts** per cell (RNG-bearing).
4. Realise **integer IP counts** per cell (RNG-bearing).
5. Instantiate devices and attach them to entities (parties/accounts/merchants) (RNG-bearing).
6. Instantiate IPs and wire them to devices/entities (RNG-bearing).
7. Assign static attributes for devices & IPs (RNG-bearing).
8. Materialise S4 datasets & run internal checks (RNG-free).

RNG discipline:

* S4 uses the shared Layer-3 Philox envelope, with substreams keyed on:

  ```text
  (manifest_fingerprint, seed, "6A.S4", substream_label, context...)
  ```

* S4 defines distinct RNG families (names indicative, semantics binding):

  * `device_count_realisation` — for realising integer device counts per planning cell.
  * `device_allocation_sampling` — for assigning devices to parties/accounts/merchants.
  * `device_attribute_sampling` — for sampling device attributes.
  * `ip_count_realisation` — for realising integer IP counts per IP-cell.
  * `ip_allocation_sampling` — for wiring IPs to devices/parties/merchants.
  * `ip_attribute_sampling` — for sampling IP attributes.

Each RNG event is logged with:

* `counter_before`, `counter_after`,
* `blocks`, `draws`,
* contextual identifiers (world, seed, cell keys, attribute family).

No RNG may be used for identity axes, schema, paths, or partitions.

---

### 6.1 Phase 1 — Load gates, priors & taxonomies (RNG-free)

**Goal:** Ensure S4 operates in a sealed world, with valid S1/S2/S3 bases and S4 priors/taxonomies/linkage rules.

1. **Verify S0 gate & sealed inputs**

   * Read `s0_gate_receipt_6A` and `sealed_inputs_6A` for `manifest_fingerprint`.
   * Recompute `sealed_inputs_digest_6A` and verify equality.
   * Check `upstream_gates` shows `gate_status = "PASS"` for `{1A,1B,2A,2B,3A,3B,5A,5B}`.

2. **Verify S1/S2/S3 gates for `(mf, seed)`**

   * Latest S1 run-report: `status="PASS"`, `error_code` empty.
   * Latest S2 run-report: `status="PASS"`, `error_code` empty.
   * Latest S3 run-report: `status="PASS"`, `error_code` empty.
   * Load and validate partitions:

     * `s1_party_base_6A` for `(seed, mf)`; `COUNT(*) == total_parties`.
     * `s2_account_base_6A` for `(seed, mf)`; `COUNT(*) == total_accounts`.
     * `s3_instrument_base_6A` for `(seed, mf)`; `COUNT(*) == total_instruments`.

3. **Select S4-relevant `sealed_inputs_6A` rows**

   Filter rows with:

   * `role ∈ {"DEVICE_PRIOR","IP_PRIOR","GRAPH_LINKAGE_RULES","TAXONOMY","UPSTREAM_EGRESS","SCENARIO_CONFIG"}`,
   * `status ∈ {"REQUIRED","OPTIONAL"}`.

   Partition into:

   * device priors,
   * device taxonomies,
   * IP priors,
   * IP taxonomies,
   * graph/linkage rules,
   * optional context surfaces,
   * contracts (`role="CONTRACT"`, `read_scope="METADATA_ONLY"`).

4. **Load & validate priors/taxonomies/linkage rules**

   For each **required** artefact:

   * resolve path via `path_template` + `partition_keys`,
   * read rows; validate against `schema_ref`,
   * recompute SHA-256 and check `sha256_hex`.

   Build in-memory structures:

   * device priors: distributions of devices per cell and per device_type,
   * IP priors: distributions of IPs per device/party/merchant and ip_type mixes,
   * device taxonomies: `device_type`, `os_family`, `ua_family`, static risk tags,
   * IP taxonomies: `ip_type`, `asn_class`, IP risk tiers,
   * graph/linkage rules: sharing patterns, degree caps, forbidden combinations.

5. **Load optional context surfaces**

   If present and configured:

   * read context surfaces (e.g. connectivity/per-region stats, merchant channel profiles).
   * treat these as multiplicative or additive adjustments to priors, never as schema or identity sources.

This phase is **RNG-free**, deterministic, and must fail with appropriate S4 error codes if prerequisites are not satisfied.

---

### 6.2 Phase 2 — Define planning cells & continuous targets (RNG-free)

**Goal:** Define the planning domains for devices and IPs and compute continuous targets from priors.

#### 6.2.1 Device planning cells

Define a **device planning cell** `c_dev` such as:

```text
c_dev = (region_id, party_type, segment_id)
```

or

```text
c_dev = (region_id, party_type, segment_id, account_type_class)
```

depending on final design. The chosen cell schema becomes part of the binding spec later (this section stays generic but consistent).

Steps:

1. **Derive base entity counts per cell**

   From S1 (parties), and optionally S2/S3 (accounts/instruments), derive:

   * `N_parties(c_dev)` — number of parties in cell.
   * optionally `N_accounts(c_dev)` — accounts in cell (if device priors depend on accounts).
   * optionally `N_merchants(c_dev)` — merchants in cell (for merchant devices).

2. **Determine expected devices per cell**

   For each `c_dev`, from device priors (and optional context) compute:

   * `λ_devices_per_party(c_dev)` and/or `λ_devices_per_account(c_dev)` and/or `λ_devices_per_merchant(c_dev)`.

   Derive:

   ```text
   N_device_target(c_dev) =
       N_parties(c_dev)  * λ_devices_per_party(c_dev)  +
       N_accounts(c_dev) * λ_devices_per_account(c_dev) +
       N_merchants(c_dev)* λ_devices_per_merchant(c_dev)   # where applicable
   ```

   plus optional context scaling factor `scale_dev(c_dev)` (e.g. more devices in mobile-heavy regions).

3. **Optional device-type decomposition**

   For each `c_dev`, from priors determine type mix:

   ```text
   π_device_type | c_dev (device_type)
   ```

   giving continuous device-type targets:

   ```text
   N_device_target(c_dev, device_type) =
       N_device_target(c_dev) * π_device_type | c_dev (device_type)
   ```

#### 6.2.2 IP planning cells

Define an **IP planning cell** `c_ip`, e.g.:

```text
c_ip = (region_id, ip_type, asn_class)
```

or richer depending on design.

Steps:

1. **Derive base “owners” per IP cell**

   From device base plan (once we have `N_device_target`), and possibly parties/merchants:

   * `N_devices_ref(c_ip)` — expected number of devices in `c_ip`’s region that will need IPs,
   * optionally `N_parties_ref(c_ip)` / `N_merchants_ref(c_ip)` if priors depend on entity counts.

2. **Determine expected IPs per cell**

   From IP priors and context surfaces, compute:

   ```text
   N_ip_target(c_ip) = f(N_devices_ref(c_ip), N_parties_ref(c_ip), N_merchants_ref(c_ip), π_ip_type|cell, scale_ip_context(c_ip))
   ```

   where `f` encodes how many IPs are needed (e.g. some IPs shared by many devices vs one-per-device etc.).

3. **Sanity checks**

   For all cells:

   * `N_device_target(...)`, `N_ip_target(...)` are finite, ≥ 0.
   * Global continuous totals `Σ N_device_target` and `Σ N_ip_target` are within configured safety caps.
   * Expected per-entity ranges (devices per party, IPs per device) are within configured min/max constraints, or else S4 must fail with e.g. `DEVICE_TARGETS_INCONSISTENT` / `IP_TARGETS_INCONSISTENT`.

Phase 2 is **RNG-free** and purely arithmetic.

---

### 6.3 Phase 3 — Realise integer device/IP counts per cell (RNG-bearing)

**Goal:** Convert continuous targets into **integer counts** per cell for devices and IPs.

This phase introduces RNG via `device_count_realisation` and `ip_count_realisation`.

#### 6.3.1 Integerise device counts

For devices:

1. **Per-cell floors & residuals**

   * For each `(c_dev, device_type)` (if device-type decomposition is used):

     ```text
     N_dev_floor(c_dev, type) = floor(N_device_target(c_dev, type))
     r_dev(c_dev, type)       = N_device_target(c_dev, type) - N_dev_floor(...)
     ```

   * Compute:

     ```text
     N_dev_floor_world = Σ_{c_dev,type} N_dev_floor(...)
     N_dev_target_world = Σ_{c_dev,type} N_device_target(...)
     ```

2. **Choose integer total**

   * Determine integer `N_dev_world_int` via deterministic rounding of `N_dev_target_world` (e.g. nearest integer with ties broken in a fixed way).

3. **Allocate residuals via RNG**

   * Remaining devices:

     ```text
     R_dev_world = N_dev_world_int - N_dev_floor_world
     ```

   * Use `device_count_realisation` RNG to allocate `R_dev_world` units across `(c_dev, type)` cells proportionally to `r_dev` (e.g. via multinomial-style or RNG-driven largest-remainder).

   * Result: integer `N_device(c_dev, type)` such that:

     ```text
     N_device(c_dev, type) >= 0
     Σ_{c_dev,type} N_device(c_dev, type) == N_dev_world_int
     ```

4. **Emit RNG events**

   * For each RNG batch (world-level or grouped), emit `rng_event_device_count` with:

     * `(mf, ph, seed, region_id, device_type, …)`,
     * `counter_before`, `counter_after`, `blocks`, `draws`,
     * optional summary: `N_device_target_total`, `N_device_realised_total`.

#### 6.3.2 Integerise IP counts

Similarly for IPs:

1. **Per-cell floors & residuals**

   * For each `c_ip`:

     ```text
     N_ip_floor(c_ip) = floor(N_ip_target(c_ip))
     r_ip(c_ip)       = N_ip_target(c_ip) - N_ip_floor(c_ip)
     ```

   * Compute:

     ```text
     N_ip_floor_world = Σ_{c_ip} N_ip_floor(c_ip)
     N_ip_target_world = Σ_{c_ip} N_ip_target(c_ip)
     ```

2. **Choose integer total & allocate**

   * Determine `N_ip_world_int` from `N_ip_target_world`.

   * Use `ip_count_realisation` RNG to allocate residual `N_ip_world_int - N_ip_floor_world` across `c_ip` according to `r_ip`.

   * Result: integer `N_ip(c_ip) ≥ 0`, with:

     ```text
     Σ_{c_ip} N_ip(c_ip) == N_ip_world_int
     ```

3. **Emit RNG events**

   * Emit `rng_event_ip_count` batches with envelope + summary.

4. **Conservation & bound checks**

   * Validate that per-cell and global integer totals are within configured limits (e.g. no `N_device` or `N_ip` exceeding caps).
   * If integerisation cannot respect min/max constraints, fail with `DEVICE_INTEGERISATION_FAILED` / `IP_INTEGERISATION_FAILED`.

---

### 6.4 Phase 4 — Instantiate devices & attach to entities (RNG-bearing)

**Goal:** For each `(c_dev, device_type)` cell, create `N_device(c_dev, device_type)` concrete `device_id`s and attach them to underlying entities according to device-sharing priors and linkage rules.

This phase uses `device_allocation_sampling`.

#### 6.4.1 Build entity sets & device weights per cell

For each `c_dev`:

1. **Entity sets**

   * From S1/S2 (and optionally merchants), derive the set of candidate “owners”:

     * `P(c_dev)` — parties in the cell,
     * `A(c_dev)` — accounts in/under the cell (if accounts drive device ownership),
     * `M(c_dev)` — merchants in the cell (for merchant devices).

   * Depending on your ownership model, devices might be attached primarily to parties, accounts, merchants, or some blend.

2. **Device ownership priors per entity**

   For each candidate entity `e` (party/account/merchant) in `c_dev`:

   * derive a non-negative weight `w_e(c_dev, device_type)` from priors:

     * more devices for some segments or high-usage merchants,
     * fewer for low-usage or “digital minimalist” segments.

   * ensure at least one entity in the cell has `w_e > 0` if `N_device(c_dev, device_type) > 0`; otherwise this is a linkage/prior inconsistency.

3. **Normalise weights**

   For the cell:

   ```text
   W_total = Σ_e w_e
   π_e = w_e / W_total
   ```

   S4 must fail with a linkage/target error if `W_total == 0` but `N_device(c_dev, type) > 0`.

#### 6.4.2 Sample device ownership

For each `(c_dev, device_type)`:

1. **Sample entity counts**

   * Using `device_allocation_sampling`, sample an allocation:

     ```text
     n_devices(e, c_dev, type) ∈ ℕ
     Σ_e n_devices(e, c_dev, type) == N_device(c_dev, type)
     ```

   * Implementation may be multinomial or repeated draws, but must respect:

     * per-entity constraints (max devices per party/account/merchant),
     * any required minima (e.g. at least one device for some segments).

2. **Assign device_id per entity**

   For each entity `e` and device index `i = 0..n_devices(e, c_dev, type)-1`:

   * define a local index `k` within the cell,
   * later (Phase 7) we’ll derive `device_id` as a deterministic hash of `(mf, seed, c_dev, type, local_index)`.

3. **Emit RNG events**

   * For each cell/group, emit `rng_event_device_allocation` with context (cell, device_type), envelope, and optional summary (e.g. distribution of devices per party).

4. **Constraint enforcement**

   * If hard caps cause infeasible allocations (e.g. more devices required than allowed by max per entity), S4 must fail with `LINKAGE_RULE_VIOLATION` or `DEVICE_INTEGERISATION_FAILED`.

---

### 6.5 Phase 5 — Instantiate IPs & wire to devices/entities (RNG-bearing)

**Goal:** For each IP cell `c_ip`, create `N_ip(c_ip)` concrete `ip_id`s and attach them to devices/parties/merchants according to sharing structure priors.

This phase uses `ip_allocation_sampling`.

#### 6.5.1 Build device / entity sets per IP cell

For each IP cell `c_ip = (region_id, ip_type, asn_class, …)`:

1. **Identify candidate devices & entities**

   * From the device plan and classification:

     * `D(c_ip)` — devices eligible for this IP type/class (e.g. mobile devices for MOBILE IPs, merchant POS devices for CORPORATE/dedicated merchant IPs).

   * Optionally `P(c_ip)` / `M(c_ip)` — parties/merchants in the region, if direct edges beyond device-level are modelled.

2. **IP-sharing priors**

   From IP priors and graph rules:

   * distributions for:

     * devices per IP (`deg_D_per_IP`),
     * parties per IP (`deg_P_per_IP`) for each `ip_type`/`asn_class`.

   * these priors dictate how “wide” an IP’s fan-out can be.

#### 6.5.2 Sample IP-level sharing patterns

For each `c_ip`:

1. **For each IP to be created (1..N_ip(c_ip)):**

   * using `ip_allocation_sampling`, sample:

     * number of devices `k_D` attached to this IP,
     * number of parties `k_P` attached (if modelled directly).

   * enforce per-IP caps and minima:

     * e.g. `k_D >= 1` for most IPs;
     * some `ip_type`s (datacentre) may permit large `k_D`, others (residential) might be capped small.

2. **Assign devices/parties to each IP**

   * For each IP in `c_ip`:

     * draw `k_D` distinct devices from `D(c_ip)` (with appropriate weighting),
     * optionally draw `k_P` distinct parties from `P(c_ip)` if direct party-IP links exist.

   * Ensure:

     * device degree constraints per `ip_type` are respected (max IPs per device),
     * party/merchant degree constraints are respected.

3. **Emit RNG events**

   * For each `c_ip`, emit `rng_event_ip_allocation` summarising:

     * number of IPs,
     * distribution of `k_D`, `k_P`,
     * envelope counters.

4. **Constraint enforcement**

   * If you cannot find a feasible assignment of devices/parties to IPs that respects per-IP and per-device caps within retry limits, S4 must fail with `LINKAGE_RULE_VIOLATION` or `IP_INTEGERISATION_FAILED`.

---

### 6.6 Phase 6 — Assign device & IP attributes (RNG-bearing)

**Goal:** For each device and IP instance, assign static attributes consistent with taxonomies and attribute priors.

This phase uses `device_attribute_sampling` and `ip_attribute_sampling`.

#### 6.6.1 Device attributes

For each device instance (cell `c_dev`, device_type, owning entity context):

1. **Determine conditioning context**

   * `c_dev` cell (region, party_type, segment, account_type class),
   * device_type,
   * possibly owner’s attributes (e.g. party segment, merchant type).

2. **Sample attributes as needed**

   * For each attribute S4 owns:

     * `os_family`: sample from `π_os_family | device_type, c_dev`.
     * `ua_family`: sample from relevant prior, if modelled.
     * static risk flags: sample from Bernoulli/Beta-Binomial priors conditioned on cell and device_type.
     * home region for device: typically deterministic from `c_dev` or owner.

3. **Emit RNG events**

   * Batch draws per `(cell, device_type, attribute_family)` and emit `rng_event_device_attribute` events with envelope + summary.

#### 6.6.2 IP attributes

For each IP instance (cell `c_ip`, and its attached devices/entities):

1. **Determine conditioning context**

   * `c_ip` (region, ip_type, asn_class, etc.),
   * optionally composition of devices/entities attached to this IP (e.g. party mix, degree).

2. **Sample attributes as needed**

   * For each attribute S4 owns:

     * IP representation mask (if not directly deterministic from priors),
     * IP risk tier (e.g. high-risk for some VPS ranges),
     * geo buckets (if coarse geolocation includes some uncertainty bands).

3. **Emit RNG events**

   * Batch draws per `(c_ip, attribute_family)` and emit `rng_event_ip_attribute` events.

All attribute sampling must be deterministic given inputs and seed.

---

### 6.7 Phase 7 — Materialise outputs & internal validation (RNG-free)

**Goal:** Write S4 outputs with canonical identity, and verify they are consistent with plans, priors and upstream bases.

#### 6.7.1 Materialise `s4_device_base_6A`

For each device instance:

1. **Assign `device_id`**

   * Use a deterministic hash or sequence, e.g.:

     ```text
     device_id = LOW64(
       SHA256( mf || seed || "device" || cell_key(c_dev, device_type) || uint64(local_index) )
     )
     ```

   * Guaranteed injective within `(mf, seed)`.

2. **Build record**

   * `manifest_fingerprint`, `parameter_hash`, `seed`,
   * `device_id`, `device_type`, `os_family`, `ua_family`, `device_class`,
   * `primary_party_id`, `primary_merchant_id` (if modelled),
   * `home_region_id`, `home_country_iso`,
   * static flags (`is_emulator`, `is_jailbroken`, `supports_biometric_auth`, etc.).

3. **Write dataset**

   * To `data/layer3/6A/s4_device_base_6A/seed={seed}/fingerprint={mf}/...`
   * Using canonical ordering from the dataset dictionary.
   * Validate against `schemas.6A.yaml#/s4/device_base`.

4. **PK & FK checks**

   * PK uniqueness: `(mf, seed, device_id)` unique.
   * FK checks: primaries reference existing parties/merchants if present.

#### 6.7.2 Materialise `s4_ip_base_6A`

Similarly, for each IP instance:

1. Assign `ip_id` via deterministic hash or sequence.
2. Build record with `ip_id`, `ip_address_masked`, `ip_type`, `asn_class`, `country_iso`, `region_id`, static risk flags.
3. Write to `s4_ip_base_6A` path with canonical ordering & validate schema.
4. Ensure `(mf, seed, ip_id)` uniqueness.

#### 6.7.3 Materialise link tables

1. **`s4_device_links_6A`**

   * For each device→entity relationship (from allocation steps):

     * write rows with `(mf, ph, seed, device_id, party_id?, account_id?, instrument_id?, merchant_id?, link_role)`.

   * Validate schema and FKs:

     * `device_id` in `s4_device_base_6A`,
     * `party_id` in S1, `account_id` in S2, `instrument_id` in S3, `merchant_id` in L1.

2. **`s4_ip_links_6A`**

   * For each IP→device/entity relationship:

     * write rows with `(mf, ph, seed, ip_id, device_id?, party_id?, merchant_id?, link_role)`.

   * Validate schema, FKs and adherence to sharing caps.

#### 6.7.4 Materialise optional neighbourhood/summary datasets

If implemented:

* **`s4_entity_neighbourhoods_6A`**

  * Derive per-entity metrics by aggregating S4 base + link tables.
  * Write and validate; ensure all IDs exist in upstream bases.

* **`s4_network_summary_6A`**

  * Compute graph statistics (degree distributions, counts, etc.) from base + links.
  * Write and validate; ensure metrics align with observed degrees.

#### 6.7.5 Internal validation & RNG reconciliation

Before marking S4 as PASS for `(mf, seed)`, S4 must:

1. **Plan vs base consistency**

   * For each cell:

     * counts of devices in `s4_device_base_6A` must equal `N_device(c_dev, type)`,
     * counts of IPs in `s4_ip_base_6A` must equal `N_ip(c_ip)`.

2. **Graph invariants**

   * Degree distributions match configured constraints and expectations, or at least lie within allowed ranges (e.g. max devices per party, max parties per IP, etc.).
   * No structural anomalies that violate hard rules (e.g. ip_type `RESIDENTIAL` with extremely high fan-out if that’s disallowed).

3. **Link & derived view consistency**

   * Device/IP link tables faithfully reflect allocations; no missing or extra edges.
   * Optional neighbourhood/summary tables match base + links.

4. **RNG accounting**

   * Aggregate RNG event logs for S4 families; ensure:

     * event counts, draws and blocks line up with expectations,
     * no overlapping or out-of-order Philox counter ranges,
     * budgets (if configured) are respected.

Any failure in these checks yields an S4 **FAIL** with an appropriate `6A.S4.*` error code, and S4 must not be considered sealed for that `(mf, seed)`.

---

### 6.8 Determinism guarantees

Given:

* `manifest_fingerprint`,
* `parameter_hash`,
* `seed`,
* sealed S0 inputs,
* sealed S1/S2/S3 bases,
* fixed S4 priors/taxonomies/linkage configs,

S4’s business outputs:

* `s4_device_base_6A`,
* `s4_ip_base_6A`,
* `s4_device_links_6A`,
* `s4_ip_links_6A`,
* and any optional neighbourhood/summary views,

MUST be:

* **bit-stable & idempotent** — re-running S4 with the same inputs and seed in the same catalogue state produces byte-identical outputs,
* independent of:

  * internal parallelism / scheduling,
  * physical file layout beyond canonical ordering,
  * environment-specific properties (hostnames, wall-clock, process IDs, etc.).

All randomness MUST flow exclusively through the declared RNG families under the Layer-3 envelope and be fully accounted by RNG logs. Any change to:

* cell definitions,
* mapping from priors to device/IP counts or allocation,
* RNG family semantics,

is a behavioural change and must be handled via S4’s change control (§12), not as a hidden implementation tweak.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S4’s outputs are identified, partitioned, ordered and merged**.
All downstream 6A states (S5) and 6B **must** treat these rules as part of the S4 contract, not as implementation hints.

S4’s business outputs are:

* **Required base datasets**

  * `s4_device_base_6A`
  * `s4_ip_base_6A`
* **Required link datasets**

  * `s4_device_links_6A`
  * `s4_ip_links_6A`
* **Optional derived datasets**

  * `s4_entity_neighbourhoods_6A`
  * `s4_network_summary_6A`

RNG logs are governed by the Layer-3 RNG envelope and are not covered here.

---

### 7.1 Identity axes

S4 uses the same three primary identity axes as S1–S3:

* **World identity**

  * `manifest_fingerprint`
  * Identifies the sealed upstream world (L1 + L2) and the 6A input universe.
  * S4 must never change or reinterpret this value.

* **Parameter identity**

  * `parameter_hash`
  * Identifies the priors/config pack (device/IP priors, taxonomies, graph rules).
  * Stored as a **column** in S4 outputs, **not** as a partition key.
  * For a given `(manifest_fingerprint, seed)`, there MUST be exactly one `parameter_hash` present in S4 business datasets.

* **RNG identity**

  * `seed`
  * Identifies the specific party+account+instrument+device/IP realisation within a world.
  * Different seeds under the same `(mf, ph)` correspond to different device/IP graphs.

`run_id` is used only for logs/run-reporting; it MUST NOT influence S4 business outputs.

---

### 7.2 Partitioning & path tokens

All S4 datasets are **world+seed scoped** and partitioned identically.

#### 7.2.1 `s4_device_base_6A`

* Partition keys:

```text
[seed, fingerprint]
```

* Path template (schematic):

```text
data/layer3/6A/s4_device_base_6A/
  seed={seed}/
  fingerprint={manifest_fingerprint}/
  s4_device_base_6A.parquet
```

#### 7.2.2 `s4_ip_base_6A`

* Partition keys:

```text
[seed, fingerprint]
```

* Path template:

```text
data/layer3/6A/s4_ip_base_6A/
  seed={seed}/
  fingerprint={manifest_fingerprint}/
  s4_ip_base_6A.parquet
```

#### 7.2.3 `s4_device_links_6A` & `s4_ip_links_6A`

* Partition keys:

```text
[seed, fingerprint]
```

* Path templates (schematic):

```text
data/layer3/6A/s4_device_links_6A/
  seed={seed}/
  fingerprint={manifest_fingerprint}/
  s4_device_links_6A.parquet

data/layer3/6A/s4_ip_links_6A/
  seed={seed}/
  fingerprint={manifest_fingerprint}/
  s4_ip_links_6A.parquet
```

#### 7.2.4 Optional `s4_entity_neighbourhoods_6A`, `s4_network_summary_6A`

If implemented:

* Partition keys:

```text
[seed, fingerprint]
```

* Path templates:

```text
data/layer3/6A/s4_entity_neighbourhoods_6A/seed={seed}/fingerprint={mf}/...
data/layer3/6A/s4_network_summary_6A/seed={seed}/fingerprint={mf}/...
```

**Binding rules:**

* `seed={seed}` and `fingerprint={manifest_fingerprint}` path tokens MUST match the `seed` and `manifest_fingerprint` columns in the data.
* No additional partition keys (e.g. `parameter_hash`, `scenario_id`) may be introduced for S4 business datasets.
* Consumers MUST discover locations via the catalogue (dictionary/registry) and substitute these tokens; hard-coded paths are out-of-spec.

---

### 7.3 Primary keys, foreign keys & uniqueness

#### 7.3.1 `s4_device_base_6A`

* **Logical primary key:**

```text
(manifest_fingerprint, seed, device_id)
```

* **Uniqueness:**

  * `device_id` MUST be unique within each `(manifest_fingerprint, seed)`.
  * No duplicate `(mf, seed, device_id)` rows.

* **Parameter consistency:**

  * All rows for a given `(mf, seed)` MUST share the same `parameter_hash`.

#### 7.3.2 `s4_ip_base_6A`

* **Logical primary key:**

```text
(manifest_fingerprint, seed, ip_id)
```

* **Uniqueness:**

  * `ip_id` MUST be unique within each `(mf, seed)`.
  * No duplicate `(mf, seed, ip_id)` rows.

* **Parameter consistency:**

  * All rows for a given `(mf, seed)` MUST share the same `parameter_hash`.

#### 7.3.3 `s4_device_links_6A`

Depending on whether you implement a unified link table or split by link type, the logical key may vary. For a unified table:

* **Logical key (example):**

```text
(manifest_fingerprint, seed,
 device_id,
 party_id?, account_id?, instrument_id?, merchant_id?,
 link_role)
```

**Invariants:**

* `device_id` MUST exist in `s4_device_base_6A` for the same `(mf, seed)`.
* Any `party_id` MUST exist in `s1_party_base_6A`.
* Any `account_id` MUST exist in `s2_account_base_6A`.
* Any `instrument_id` MUST exist in `s3_instrument_base_6A`.
* Any `merchant_id` MUST exist in the merchant universe (L1).
* Links MUST respect S4’s graph/linkage rules (no forbidden combinations, no degree caps exceeded).

If you split links into multiple tables (e.g. device↔party vs device↔account), each table must have an appropriate PK that includes `(mf, seed, device_id, …)` and must still obey the above FK invariants.

#### 7.3.4 `s4_ip_links_6A`

Similarly, for a unified IP link table:

* **Logical key (example):**

```text
(manifest_fingerprint, seed,
 ip_id,
 device_id?, party_id?, merchant_id?,
 link_role)
```

**Invariants:**

* `ip_id` MUST exist in `s4_ip_base_6A` for the same `(mf, seed)`.
* Any `device_id` referenced MUST exist in `s4_device_base_6A`.
* Any `party_id` / `merchant_id` MUST exist upstream.
* Sharing patterns implied by links (devices per IP, parties per IP) MUST respect IP-sharing priors and degree constraints.

#### 7.3.5 Optional views

If implemented:

* **`s4_entity_neighbourhoods_6A`**

  * Logical key (example):

    ```text
    (manifest_fingerprint, seed, entity_type, entity_id)
    ```

  * `entity_type` enumerates the kind of entity (PARTY, ACCOUNT, INSTRUMENT, MERCHANT).

  * `entity_id` must refer back to S1/S2/S3/L1 universes.

* **`s4_network_summary_6A`**

  * Key depends on chosen grouping (e.g. `(mf, seed, region_id, segment_id, account_type, metric_id)`).
  * All metrics must be derivable from S4 base/link tables; no new IDs.

---

### 7.4 Ordering: canonical vs semantic

We distinguish:

* **Canonical ordering** — required writer ordering for deterministic, idempotent outputs.
* **Semantic ordering** — ordering guarantees consumers are allowed to rely on.

#### 7.4.1 Canonical writer ordering

The dataset dictionary MUST specify an `ordering` for each S4 dataset, e.g.:

* `s4_device_base_6A`:

```text
ORDER BY device_type, primary_party_id, primary_merchant_id, device_id
```

* `s4_ip_base_6A`:

```text
ORDER BY ip_type, asn_class, country_iso, ip_id
```

* `s4_device_links_6A`:

```text
ORDER BY device_id, party_id, account_id, instrument_id, merchant_id, link_role
```

* `s4_ip_links_6A`:

```text
ORDER BY ip_id, device_id, party_id, merchant_id, link_role
```

* Optional datasets: appropriate orderings (e.g. by `entity_type, entity_id` for neighbourhoods).

Writers MUST honour these orderings when materialising partitions, to ensure:

* stable write-outs across re-runs,
* predictable higher-level digests (if you ever hash S4 outputs).

#### 7.4.2 Semantic ordering

Consumers **must not** derive business meaning from physical row order:

* They MUST rely on keys and filters (device_id, ip_id, party_id, account_id, region, etc.) and not on “first N rows”.
* Expected graph structure must be inferred from base + link keys, not from the ordering of those rows.

Canonical ordering is a *writer invariance* for determinism; it is not a business semantics guarantee.

---

### 7.5 Merge discipline & lifecycle

S4 behaves as **replace-not-append** at the granularity of `(manifest_fingerprint, seed)`.

#### 7.5.1 Replace-not-append per world+seed

For each `(mf, seed)`:

* `s4_device_base_6A` is **one complete device universe snapshot**.
* `s4_ip_base_6A` is **one complete IP/endpoint universe snapshot**.
* `s4_device_links_6A` and `s4_ip_links_6A` are **complete graph edge sets** for that world+seed.
* Any optional neighbourhood/summary tables are complete derived views.

Behavioural rules:

* Re-running S4 for the same `(mf, seed)` with the same inputs (`ph`, sealed inputs, S1/S2/S3 bases and S4 priors) MUST either:

  * produce **byte-identical** outputs for all S4 datasets, or
  * fail with `6A.S4.OUTPUT_CONFLICT` (or equivalent) and leave existing outputs untouched.

* S4 MUST NOT:

  * append “more devices/IPs” to an existing `(mf, seed)` universe,
  * merge two independently computed S4 outputs for the same `(mf, seed)`.

Any attempt to “top up” or partially re-run S4 for a world+seed is out-of-spec unless you explicitly design and version a new S4 mode to support that.

#### 7.5.2 No cross-world / cross-seed merges

* **No cross-world merges:**

  * Devices/IPs from different `manifest_fingerprint`s MUST NOT be mixed.
  * An analysis that aggregates across worlds must be explicit; it does not define a single unified graph.

* **No cross-seed merges within a world:**

  * Different `seed`s under the same `mf` correspond to different universes.
  * S4 (and downstream modelling) must treat each `(mf, seed)` as a self-contained graph.
  * Cross-seed analysis is allowed for QA, but not as a basis for building flows/fraud logic that assumes a single universe.

---

### 7.6 Consumption discipline for S5 and 6B

Downstream states **must** respect S4’s identity and merge discipline.

#### 7.6.1 6A.S5 (fraud posture)

For each `(mf, seed)` it operates on, S5 MUST:

* Verify S0–S3 gates as per its own spec, **and** S4 PASS for `(mf, seed)` via S4’s run-report (`status="PASS"`, `error_code` empty).
* Confirm that:

  * `s4_device_base_6A` exists and is schema-valid,
  * `s4_ip_base_6A` exists and is schema-valid,
  * `s4_device_links_6A` and `s4_ip_links_6A` exist and are schema-valid.

S5 MUST NOT:

* create new `device_id`s or `ip_id`s,
* alter static attributes in S4 base datasets,
* alter S4 link structure (device/IP edges).

Any fraud posture surfaces it creates must **reference** S4’s graph and treat it as read-only ground truth.

#### 7.6.2 6B (flows & fraud)

6B MUST:

* treat `s4_device_base_6A` and `s4_ip_base_6A` as the **only** lists of devices/IPs for that `(mf, seed)`,
* attach flows/sessions/transactions to `device_id`/`ip_id` only if those IDs exist in S4 for the same `(mf, seed)`,
* treat any `device_id`/`ip_id` not present in S4 for `(mf, seed)` as an error (not as an “external” or “unknown” entity).

6B is free to:

* add dynamic state (e.g. counts of logins, risky IP usage, session histories),
* attach labels or risk scores to devices/IPs/edges,

but it MUST NOT:

* introduce new devices/IPs,
* change static S4 attributes or edges.

---

These identity, partition, ordering and merge rules are **binding**.
Storage format, execution strategy and data structures are implementation details; any implementation that violates these semantics is **not** a correct implementation of 6A.S4.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 6A.S4 is considered PASS** for a given `(manifest_fingerprint, seed)` and how **downstream states (S5, 6B)** must gate on S4 before using any device/IP/graph data.

If any condition here fails, S4 is **FAIL for that `(mf, seed)`**, and **no later 6A state nor 6B may treat S4 outputs as valid**.

---

### 8.1 Segment-local PASS / FAIL definition

For a given `(manifest_fingerprint, seed)`, 6A.S4 is **PASS** *iff* **all** of the following hold.

#### 8.1.1 S0–S3 & upstream worlds are sealed

1. **S0 gate & sealed-inputs valid for this world**

   * `s0_gate_receipt_6A` and `sealed_inputs_6A` exist for `manifest_fingerprint`, validate against their schemas, and satisfy:

     ```text
     recompute_digest(sealed_inputs_6A) == s0_gate_receipt_6A.sealed_inputs_digest_6A
     ```

   * Latest 6A.S0 run-report for this `mf` has:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

2. **Upstream segments sealed**

   * In `s0_gate_receipt_6A.upstream_gates`, each required segment `{1A,1B,2A,2B,3A,3B,5A,5B}` has:

     ```text
     gate_status == "PASS"
     ```

3. **S1 sealed for this `(mf, seed)`**

   * Latest 6A.S1 run-report for `(mf, seed)` has `status="PASS"` and empty `error_code`.
   * `s1_party_base_6A` for `(seed={seed}, fingerprint={mf})` exists, validates against `#/s1/party_base`, and `COUNT(*)` equals `total_parties` reported by S1.

4. **S2 sealed for this `(mf, seed)`**

   * Latest 6A.S2 run-report for `(mf, seed)` has `status="PASS"` and empty `error_code`.
   * `s2_account_base_6A` for `(seed={seed}, fingerprint={mf})` exists, validates against `#/s2/account_base`, and `COUNT(*)` equals `total_accounts` reported by S2.

5. **S3 sealed for this `(mf, seed)`**

   * Latest 6A.S3 run-report for `(mf, seed)` has `status="PASS"` and empty `error_code`.
   * `s3_instrument_base_6A` and `s3_account_instrument_links_6A` for `(seed={seed}, fingerprint={mf})` exist, validate against their schemas, and counts are consistent with S3 run-report metrics (e.g. `total_instruments`).

If any of 1–5 fail, S4 MUST NOT create devices/IPs for that `(mf, seed)` and MUST fail with `6A.S4.S0_S1_S2_S3_GATE_FAILED` (or equivalent).

---

#### 8.1.2 Priors, taxonomies & graph/linkage rules

6. **Required S4 priors / taxonomies / linkage packs present and usable**

   For every artefact S4 classifies as required (device priors, IP priors, device/IP taxonomies, graph/linkage rules):

   * There is a row in `sealed_inputs_6A` for this `mf` with:

     ```text
     status     == "REQUIRED"
     read_scope == "ROW_LEVEL"   # except pure contracts, which may be METADATA_ONLY
     ```

   * The artefact:

     * can be resolved via its `path_template` and `partition_keys`,
     * validates against its `schema_ref`,
     * has `sha256_hex` matching its contents (and any registry digest, if present).

7. **Taxonomy consistency**

   * Device taxonomies (device_type, os_family, ua_family, static device risk tags, etc.) exist and are schema-valid.
   * IP taxonomies (ip_type, asn_class, IP risk tiers) exist and are schema-valid.
   * All values that S4 *intends* to emit (e.g. any `device_type` or `ip_type` codes) appear in the relevant taxonomy.

If any required prior/config/taxonomy is missing/invalid, S4 MUST fail with one of:

* `6A.S4.PRIOR_PACK_MISSING`
* `6A.S4.PRIOR_PACK_INVALID`
* `6A.S4.PRIOR_PACK_DIGEST_MISMATCH`
* `6A.S4.TAXONOMY_MISSING_OR_INVALID`
* `6A.S4.LINKAGE_RULES_MISSING_OR_INVALID`

---

#### 8.1.3 Device/IP target derivation & integer counts

8. **Continuous device/IP targets well-formed**

   * For all device planning cells `c_dev` (and device_type where used):

     * `N_device_target(c_dev, device_type)` is finite and ≥ 0.

   * For all IP planning cells `c_ip`:

     * `N_ip_target(c_ip)` is finite and ≥ 0.

   * Global totals:

     ```text
     N_device_target_world = Σ_{c_dev,type} N_device_target(c_dev, type)
     N_ip_target_world     = Σ_{c_ip} N_ip_target(c_ip)
     ```

     are finite and within configured safety caps.

   * Implied expected **devices per entity** and **IPs per device/entity** fall within configured min/max ranges (e.g. no absurd “hundreds of devices per party” unless explicitly allowed).

9. **Integer device counts consistent**

   After integerisation:

   * For each `(c_dev, device_type)`:

     ```text
     N_device(c_dev, device_type) ∈ ℕ,  N_device(c_dev, device_type) ≥ 0
     ```

   * For each configured conservation group (e.g. per region or globally):

     ```text
     Σ_{c_dev, type in group} N_device(c_dev, type) == N_dev_group_int
     ```

   * Global integer total `N_dev_world_int = Σ N_device(c_dev, type)` is finite and within configured caps.

10. **Integer IP counts consistent**

Similarly, after IP integerisation:

* For each `c_ip`:

  ```text
  N_ip(c_ip) ∈ ℕ,  N_ip(c_ip) ≥ 0
  ```

* For each configured IP conservation group (e.g. per region/ip_type):

  ```text
  Σ_{c_ip in group} N_ip(c_ip) == N_ip_group_int
  ```

* Global integer total `N_ip_world_int = Σ N_ip(c_ip)` is finite and within caps.

If targets or integerisation fail these invariants, S4 MUST fail with:

* `6A.S4.DEVICE_TARGETS_INCONSISTENT` / `6A.S4.DEVICE_INTEGERISATION_FAILED`
* or `6A.S4.IP_TARGETS_INCONSISTENT` / `6A.S4.IP_INTEGERISATION_FAILED`

as appropriate.

---

#### 8.1.4 Base-table correctness & linkage invariants

11. **Device base exists and is schema-valid**

* `s4_device_base_6A` partition for `(seed={seed}, fingerprint={mf})`:

  * exists,
  * validates against `schemas.6A.yaml#/s4/device_base`,
  * has a unique PK `(manifest_fingerprint, seed, device_id)`.

* All rows in that partition:

  * carry the correct `manifest_fingerprint` and `seed`,
  * share the same `parameter_hash`.

12. **IP base exists and is schema-valid**

* `s4_ip_base_6A` for `(seed={seed}, fingerprint={mf})`:

  * exists,
  * validates against `schemas.6A.yaml#/s4/ip_base`,
  * has a unique PK `(manifest_fingerprint, seed, ip_id)`.

* All rows:

  * carry the correct `manifest_fingerprint` and `seed`,
  * share the same `parameter_hash`.

13. **Device/IP bases respect plan counts**

* For each device planning cell `c_dev` (and device_type where applicable):

  ```text
  count_devices_in_base(c_dev, type) == N_device(c_dev, type)
  ```

* For each IP planning cell `c_ip`:

  ```text
  count_ips_in_base(c_ip) == N_ip(c_ip)
  ```

* Summed over all cells:

  ```text
  COUNT(*)_device_base == N_dev_world_int
  COUNT(*)_ip_base     == N_ip_world_int
  ```

Violation yields `6A.S4.GRAPH_COUNTS_MISMATCH` or a more specific device/IP base error.

14. **Taxonomy compatibility in bases**

* All values of `device_type`, `os_family`, `ua_family`, static device risk flags, etc., appear in the relevant device taxonomy tables and obey any compatibility rules (e.g. `device_type` vs `os_family`).
* All values of `ip_type`, `asn_class`, static IP risk fields, etc., appear in IP taxonomies and obey compatibility rules (e.g. `ip_type` vs `asn_class` vs `country_iso`).

Violations MUST surface as `6A.S4.TAXONOMY_COMPATIBILITY_FAILED`.

---

#### 8.1.5 Link-table & derived-view correctness

15. **Device link table consistent with bases & rules**

* `s4_device_links_6A` exists and validates against `schemas.6A.yaml#/s4/device_links`.

* For every row:

  * `device_id` exists in `s4_device_base_6A` for `(mf, seed)`,
  * any `party_id` exists in `s1_party_base_6A`,
  * any `account_id` exists in `s2_account_base_6A`,
  * any `instrument_id` exists in `s3_instrument_base_6A`,
  * any `merchant_id` exists in the merchant universe.

* Degree constraints from linkage rules are respected:

  * devices attached to no more than the allowed number of parties/accounts/merchants,
  * parties/accounts/merchants have numbers of devices consistent with priors and hard caps.

Violations yield `6A.S4.ORPHAN_DEVICE_OR_IP_OWNER` or `6A.S4.LINKAGE_RULE_VIOLATION`.

16. **IP link table consistent with bases & rules**

* `s4_ip_links_6A` exists and validates against `schemas.6A.yaml#/s4/ip_links`.

* For every row:

  * `ip_id` exists in `s4_ip_base_6A`,
  * any `device_id` exists in `s4_device_base_6A`,
  * any `party_id`/`merchant_id` exists upstream.

* IP-sharing patterns respect priors and hard caps:

  * devices per IP within configured bounds per `ip_type`/`asn_class`,
  * parties per IP per `ip_type` consistent with priors and not exceeding caps.

17. **Optional neighbourhood & summary views are derived correctly (if present)**

If `s4_entity_neighbourhoods_6A` is implemented:

* Every `(entity_type, entity_id)` refers to a valid entity (party/account/instrument/merchant).
* Counts (device_count, ip_count, shared_device_degree, shared_ip_degree, etc.) are consistent with aggregations over base/link tables.

If `s4_network_summary_6A` is implemented:

* Each metric row is derivable from base/link tables (e.g. degree distributions, counts of high-degree IPs).
* Aggregated counts in `s4_network_summary_6A` do not contradict observed degrees in link tables.

Any inconsistency here must be treated as `6A.S4.GRAPH_COUNTS_MISMATCH` or a more specific S4 summary/neighbourhood error.

---

#### 8.1.6 RNG accounting

18. **RNG usage fully accounted & within budget**

* All uses of randomness in S4 are confined to the declared RNG families:

  * `device_count_realisation`,
  * `device_allocation_sampling`,
  * `device_attribute_sampling`,
  * `ip_count_realisation`,
  * `ip_allocation_sampling`,
  * `ip_attribute_sampling`.

* For each family, aggregate RNG metrics from S4 RNG event tables and the Layer-3 RNG logs reconcile:

  * expected number of events,
  * total draws and blocks,
  * no overlapping or out-of-order Philox counter ranges.

* Any configured RNG budgets (max draws per family per `(mf, seed)`) are respected.

If these checks fail, S4 MUST fail with `6A.S4.RNG_ACCOUNTING_MISMATCH` or `6A.S4.RNG_STREAM_CONFIG_INVALID`.

---

### 8.2 Gating obligations for downstream 6A state (S5)

S5 (fraud posture / role assignment) MUST treat S4 as a **hard precondition** for any device/IP-based labelling or feature derivation.

For each `(mf, seed)`:

1. S5 MUST confirm (via run-reports) that S0–S3 and S4 are PASS:

   * in particular, the latest S4 run-report for `(mf, seed)` has:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

2. S5 MUST confirm, via the catalogue and schema validation, that:

   * `s4_device_base_6A` and `s4_ip_base_6A` exist and are valid,
   * `s4_device_links_6A` and `s4_ip_links_6A` exist and are valid.

If any of these checks fails, S5 MUST NOT:

* read or rely on S4 device/IP/graph data for that `(mf, seed)`,
* produce fraud roles or risk signals that refer to non-existent or uncertified devices/IPs.

Instead, it MUST fail its own gate with a state-local error (e.g. `6A.S5.S4_GATE_FAILED`).

---

### 8.3 Gating obligations for 6B and external consumers

6B and any external consumer that uses device/IP/graph information MUST:

1. Require S4 PASS for each `(mf, seed)` they operate on:

   * via S4’s run-report `status="PASS"` and empty `error_code`.

2. Treat S4’s base/link datasets as **authoritative**:

   * the only sources of `device_id` and `ip_id` for that `(mf, seed)`,
   * the only description of static device/IP attributes,
   * the only description of static device/IP→entity edges.

3. Treat any `device_id` or `ip_id` not found in S4 for `(mf, seed)` as an **error**, not as an “external” or “unknown” entity, unless explicitly supported by a separate, versioned extension.

6B may build sessions/flows/transactions on top of S4’s graph and compute dynamic graph features, but it MUST NOT:

* mutate S4’s base/link tables,
* introduce new devices/IPs outside S4’s universe.

---

### 8.4 Behaviour on failure & partial outputs

If S4 fails for a given `(manifest_fingerprint, seed)`:

* Any partially written S4 datasets (`s4_device_base_6A`, `s4_ip_base_6A`, link tables, optional neighbourhood/summary) MUST NOT be treated as valid.
* Downstream states (S5, 6B) MUST treat that world+seed as **having no S4 graph** and MUST NOT proceed.

S4’s run-report MUST be updated with:

* `status = "FAIL"`,
* a non-empty `error_code` from the `6A.S4.*` namespace,
* a short `error_message`.

The only valid states are:

* **S4 PASS →** S5 and 6B may operate on device/IP/graph data for that `(mf, seed)`.
* **S4 FAIL →** S5 and 6B MUST NOT operate on device/IP/graph data for that `(mf, seed)` until S4 is re-run and PASS.

These acceptance criteria and gating obligations are **binding** and define exactly what it means for S4 to be “done and safe to build on” within Layer-3 and for the enterprise shell.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error surface** for 6A.S4.

Every failure for a given `(manifest_fingerprint, seed)` **must** be mapped to exactly one of these codes.

All codes here are:

* **Fatal** for S4 for that `(manifest_fingerprint, seed)`.
* **Blocking** for S5 and 6B for that `(manifest_fingerprint, seed)`.

There is no “best effort” downgrade. If S4 fails, the device/IP graph for that world+seed is **not usable**.

---

### 9.1 Error class overview

We group S4 failures into six classes:

1. **Gate / sealed-input / S1–S3 errors**
2. **Priors, taxonomies & linkage-rule errors**
3. **Target derivation & integerisation errors**
4. **Base-table, link & graph-consistency errors**
5. **RNG & accounting errors**
6. **IO / identity / internal errors**

Each class has a small, closed set of codes in the `6A.S4.*` namespace.

---

### 9.2 Canonical error codes

#### 9.2.1 Gate / sealed-input / S1–S3 errors

These mean S4 cannot trust the world-level gate, the sealed input universe, or the upstream 6A bases.

* `6A.S4.S0_S1_S2_S3_GATE_FAILED`
  *Meaning:* At least one of the following holds for the `(mf, seed)` S4 is asked to process:

  * S0 is missing or not PASS for this `manifest_fingerprint`, or
  * recomputed `sealed_inputs_digest_6A` does not match `s0_gate_receipt_6A.sealed_inputs_digest_6A`, or
  * one or more required upstream segments `{1A,1B,2A,2B,3A,3B,5A,5B}` have `gate_status != "PASS"` in `upstream_gates`, or
  * S1 is missing or not PASS for this `(mf, seed)`, or
  * S2 is missing or not PASS for this `(mf, seed)`, or
  * S3 is missing or not PASS for this `(mf, seed)`.

* `6A.S4.SEALED_INPUTS_MISSING_REQUIRED`
  *Meaning:* One or more artefacts that S4 considers **required** (device/IP priors, taxonomies, graph/linkage configs) do not appear as rows in `sealed_inputs_6A` for this `manifest_fingerprint`.

* `6A.S4.SEALED_INPUTS_SCOPE_INVALID`
  *Meaning:* A required artefact appears in `sealed_inputs_6A`, but:

  * `status="IGNORED"`, or
  * `read_scope="METADATA_ONLY"` where S4 requires `ROW_LEVEL`.

These codes all mean: **“S4 cannot even start; the gate or sealed input universe is not valid for this world.”**

---

#### 9.2.2 Priors, taxonomies & linkage-rule errors

These indicate S4’s own priors/configs and taxonomies are not usable.

* `6A.S4.PRIOR_PACK_MISSING`
  *Meaning:* A required S4 prior/config artefact (device priors, IP priors, or graph/linkage rules) referenced in `sealed_inputs_6A` cannot be resolved for this `(mf, ph)`.

* `6A.S4.PRIOR_PACK_INVALID`
  *Meaning:* A required prior/config artefact exists but fails validation against its `schema_ref` (bad structure, missing required fields, invalid types, etc.).

* `6A.S4.PRIOR_PACK_DIGEST_MISMATCH`
  *Meaning:* SHA-256 digest computed from a prior/config artefact does not match `sha256_hex` recorded in `sealed_inputs_6A` (and/or registry).

* `6A.S4.TAXONOMY_MISSING_OR_INVALID`
  *Meaning:* A required taxonomy (for `device_type`, `os_family`, `ip_type`, `asn_class`, risk-tier enums, etc.) is missing, malformed, or missing codes that S4 needs to emit.

* `6A.S4.LINKAGE_RULES_MISSING_OR_INVALID`
  *Meaning:* Required graph/linkage rules (device-sharing/IP-sharing/degree caps) are:

  * missing from `sealed_inputs_6A`,
  * schema-invalid, or
  * internally contradictory (e.g. no allowed device or ip pattern for a cell that has non-zero party/account counts).

These errors all mean: **“S4 does not have a coherent, trusted set of priors/taxonomies/linkage rules to define devices, IPs and the graph.”**

---

#### 9.2.3 Target derivation & integerisation errors

These indicate that S4 cannot derive or realise a consistent plan for device/IP counts from priors.

* `6A.S4.DEVICE_TARGETS_INCONSISTENT`
  *Meaning:* Continuous device targets `N_device_target(c_dev, type)` are ill-formed or inconsistent. Examples:

  * some `N_device_target` entries are negative or NaN/Inf,
  * implied expected devices-per-entity for some cells exceed configured bounds (e.g. thousands of devices per party with no such allowance),
  * required cells implied by priors/linkage rules are missing from the planning domain.

* `6A.S4.DEVICE_INTEGERISATION_FAILED`
  *Meaning:* Device integerisation to `N_device(c_dev, type)` cannot satisfy constraints. Examples:

  * some `N_device(c_dev, type) < 0`,
  * conservation fails at required group levels (e.g. total devices per region or globally),
  * configured min/max constraints (e.g. mandatory devices, max devices per entity) cannot be satisfied, even before wiring devices to specific entities.

* `6A.S4.IP_TARGETS_INCONSISTENT`
  *Meaning:* Continuous IP targets `N_ip_target(c_ip)` are ill-formed or inconsistent:

  * negative / NaN / Inf targets,
  * implied IPs-per-device or IPs-per-party heavily violate configured bounds without being permitted by priors,
  * required IP-cells are absent.

* `6A.S4.IP_INTEGERISATION_FAILED`
  *Meaning:* Integerisation of `N_ip_target(c_ip)` to `N_ip(c_ip)` cannot satisfy conservation or min/max constraints, e.g.:

  * some `N_ip(c_ip) < 0`,
  * conservation for groups (e.g. per region/ip_type) fails,
  * safety caps on `N_ip_world_int` are exceeded or cannot be enforced without breaking the spec.

These codes mean: **“We cannot derive a sane integer device/IP plan from S4 priors; any graph built on top would be invalid.”**

---

#### 9.2.4 Base-table, link & graph-consistency errors

These mean that the **materialised S4 datasets** are inconsistent with the plan, upstream entities, or taxonomies, or that the graph links do not match bases/prior constraints.

* `6A.S4.DEVICE_BASE_SCHEMA_OR_KEY_INVALID`
  *Meaning:* `s4_device_base_6A` exists but:

  * fails validation against `schemas.6A.yaml#/s4/device_base`, and/or
  * violates PK/uniqueness `(manifest_fingerprint, seed, device_id)`.

* `6A.S4.IP_BASE_SCHEMA_OR_KEY_INVALID`
  *Meaning:* `s4_ip_base_6A` exists but:

  * fails validation against `schemas.6A.yaml#/s4/ip_base`, and/or
  * violates PK/uniqueness `(manifest_fingerprint, seed, ip_id)`.

* `6A.S4.GRAPH_COUNTS_MISMATCH`
  *Meaning:* Aggregate counts in S4 bases and/or link tables do not match the realised integer plans, e.g.:

  * total devices per planning cell or globally differ from `N_device(c_dev, type)` / `N_dev_world_int`,
  * total IPs per IP cell or globally differ from `N_ip(c_ip)` / `N_ip_world_int`,
  * degree aggregates in links/neighbourhoods do not reconcile with base counts.

* `6A.S4.ORPHAN_DEVICE_OR_IP_OWNER`
  *Meaning:* Devices/IPs or link rows reference non-existent owners. Examples:

  * a `device_id` in links is missing from `s4_device_base_6A`,
  * an `ip_id` in links is missing from `s4_ip_base_6A`,
  * `party_id` not found in `s1_party_base_6A`,
  * `account_id` not found in `s2_account_base_6A`,
  * `instrument_id` not found in `s3_instrument_base_6A`,
  * `merchant_id` not found in L1 merchant universe.

* `6A.S4.LINKAGE_RULE_VIOLATION`
  *Meaning:* Materialised graph link structure violates S4’s linkage rules. Examples:

  * more devices per party/account/merchant than the configured max for that segment/region/product,
  * IPs with degrees that exceed configured bounds for their `ip_type`/`asn_class`,
  * disallowed combinations of device/IP type and entity type/segment (e.g. a merchant-only device attached to a consumer party where that is prohibited).

* `6A.S4.TAXONOMY_COMPATIBILITY_FAILED`
  *Meaning:* Values in S4 bases or link tables are incompatible with taxonomies. Examples:

  * `device_type`, `os_family`, `ua_family`, device risk tags not present in device taxonomies,
  * `ip_type`, `asn_class`, IP risk tiers not present in IP taxonomies,
  * incompatible combinations (e.g. `ip_type=RESIDENTIAL` with `asn_class=HOSTING_PROVIDER` when that combination is explicitly disallowed).

* `6A.S4.NEIGHBOURHOODS_INCONSISTENT_WITH_BASE` *(if `s4_entity_neighbourhoods_6A` is implemented)*
  *Meaning:* Neighbourhood metrics (devices per entity, IPs per entity, shared-device/shared-IP degrees) do not match what would be computed from base + link tables.

* `6A.S4.SUMMARY_INCONSISTENT_WITH_BASE` *(if `s4_network_summary_6A` is implemented)*
  *Meaning:* Summaries (degree distributions, counts, etc.) in `s4_network_summary_6A` are not consistent with underlying base/link tables.

All of these mean: **“The concrete device/IP bases and graph links are not a valid, faithful instance of S4’s plan and contracts.”**

---

#### 9.2.5 RNG & accounting errors

These indicate that S4’s randomness **cannot be trusted or audited**.

* `6A.S4.RNG_ACCOUNTING_MISMATCH`
  *Meaning:* Aggregate RNG metrics for S4 families:

  * `device_count_realisation`,
  * `device_allocation_sampling`,
  * `device_attribute_sampling`,
  * `ip_count_realisation`,
  * `ip_allocation_sampling`,
  * `ip_attribute_sampling`,

  do not reconcile with expectations. Examples:

  * missing or extra RNG events for a family,
  * overlapping or out-of-order Philox counter ranges between events,
  * total draws/blocks significantly outside configured budgets.

* `6A.S4.RNG_STREAM_CONFIG_INVALID`
  *Meaning:* S4’s RNG configuration is inconsistent with the Layer-3 RNG envelope, e.g.:

  * substream labels not registered or incorrectly specified,
  * multiple logical contexts mapping to the same substream key,
  * mismatch between RNG event schemas and envelope requirements.

These errors mean: **“We cannot reliably reproduce or audit the S4 random choices; this S4 run is not trustworthy.”**

---

#### 9.2.6 IO / identity / internal errors

These indicate storage issues, identity conflicts, or unexpected internal failures.

* `6A.S4.IO_READ_FAILED`
  *Meaning:* S4 failed to read a required artefact (priors, taxonomies, S0/S1/S2/S3 outputs, dictionary/registry) due to IO issues (permissions, network, corruption), despite the catalogue asserting its existence.

* `6A.S4.IO_WRITE_FAILED`
  *Meaning:* S4 attempted to write one or more of its outputs (`s4_device_base_6A`, `s4_ip_base_6A`, link tables, neighbourhood/summary) and the write did not complete atomically/durably.

* `6A.S4.OUTPUT_CONFLICT`
  *Meaning:* For a given `(mf, seed)`, S4 outputs already exist and are **not** byte-identical to what S4 would produce from the current inputs. Under the replace-not-append law, S4 is not allowed to overwrite; this is treated as a conflict.

* `6A.S4.INTERNAL_ERROR`
  *Meaning:* A non-classified internal error occurred (e.g. assertion failure, unhandled exception) that cannot be mapped cleanly to any of the more specific codes above. This should be treated as a bug in the implementation rather than a normal operational condition.

These all mean: **“This S4 run is structurally broken; its outputs must not be used for this world+seed.”**

---

### 9.3 Mapping detection → error code

Implementations **must** map detected conditions to these codes deterministically. Examples:

* S0/S1/S2/S3 gate or digest checks fail → `6A.S4.S0_S1_S2_S3_GATE_FAILED`.
* A required device/IP prior is missing from `sealed_inputs_6A` → `6A.S4.SEALED_INPUTS_MISSING_REQUIRED`.
* A device/IP prior exists but fails schema → `6A.S4.PRIOR_PACK_INVALID`.
* Device taxonomy missing or missing codes that S4 intends to use → `6A.S4.TAXONOMY_MISSING_OR_INVALID`.
* Continuous device targets contain NaNs or negative values → `6A.S4.DEVICE_TARGETS_INCONSISTENT`.
* Device integerisation fails conservation or min/max constraints → `6A.S4.DEVICE_INTEGERISATION_FAILED`.
* IP integerisation fails → `6A.S4.IP_INTEGERISATION_FAILED`.
* A link row references a non-existent `device_id` or `ip_id` → `6A.S4.ORPHAN_DEVICE_OR_IP_OWNER`.
* Graph links clearly break linkage rules (e.g. too many parties per residential IP) → `6A.S4.LINKAGE_RULE_VIOLATION`.
* Device/IP base or links contain invalid taxonomic codes → `6A.S4.TAXONOMY_COMPATIBILITY_FAILED`.
* Aggregate graph counts do not match plans or base tables → `6A.S4.GRAPH_COUNTS_MISMATCH`.
* RNG logs don’t reconcile with expected events/draws → `6A.S4.RNG_ACCOUNTING_MISMATCH`.
* Attempt to overwrite existing non-identical S4 outputs → `6A.S4.OUTPUT_CONFLICT`.

If a situation cannot be cleanly mapped to a more specific code, `6A.S4.INTERNAL_ERROR` MUST be used and the spec extended later, rather than inventing ad-hoc codes.

---

### 9.4 Run-report integration & propagation

On each S4 run for `(manifest_fingerprint, seed)`, the S4 run-report record **must** include:

* `state_id = "6A.S4"`,
* `manifest_fingerprint`, `parameter_hash`, `seed`,
* `status ∈ {"PASS","FAIL"}`,
* `error_code` (empty/null on PASS; one of `6A.S4.*` on FAIL),
* `error_message` (short, human-readable).

Downstream S5 and 6B MUST:

* consult S4’s run-report for `(mf, seed)`,
* treat any `status != "PASS"` or non-empty `error_code` as “S4 gate failed”,
* refuse to use S4 outputs for that world+seed in that case.

The `6A.S4.*` codes in this section are the **primary machine-readable signal** of S4’s failure modes; logs and stack traces are diagnostic only and are not part of the formal contract.

---

## 10. Observability & run-report integration *(Binding)*

6A.S4 defines the **device & IP graph** that all downstream fraud and flow logic relies on, so its status and high-level structure must be **explicitly visible** and **machine-checkable**.

Downstream states (S5, 6B) must gate on S4’s **run-report**, not on “files exist”.

This section fixes:

* what S4 must emit in its run-report,
* how that report relates to S4 datasets, and
* how downstream components must use it.

---

### 10.1 Run-report record for 6A.S4

For every attempted S4 run on a `(manifest_fingerprint, seed)`, the engine **MUST** emit exactly one run-report record with at least:

#### Identity

* `state_id = "6A.S4"`
* `manifest_fingerprint`
* `parameter_hash`
* `seed`
* `engine_version`
* `spec_version_6A` (and/or `spec_version_6A_S4` if you split it per state)

#### Execution envelope

* `run_id` (execution identifier; non-semantic)
* `started_utc` (RFC 3339, micros)
* `completed_utc` (RFC 3339, micros)
* `duration_ms` (integer; derived)

#### Status & error

* `status ∈ { "PASS", "FAIL" }`
* `error_code`

  * empty / null for PASS,
  * one of the `6A.S4.*` codes from §9 for FAIL.
* `error_message`

  * short, human-oriented explanation (non-normative; not parsed by machines).

#### Core graph metrics (binding for PASS)

For a PASS run, at minimum:

* **Universe sizes**

  * `total_devices` — `COUNT(*)` over `s4_device_base_6A` for `(mf, seed)`.
  * `total_ips` — `COUNT(*)` over `s4_ip_base_6A` for `(mf, seed)`.

* **Device splits**

  * `devices_by_type` — counts per `device_type`.
  * `devices_by_os_family` — counts per `os_family`.
  * `devices_by_region` — counts per device home `region_id` / `country_iso`.
  * optional `devices_by_party_segment` — counts per party `segment_id` (via join to S1).

* **IP splits**

  * `ips_by_type` — counts per `ip_type`.
  * `ips_by_asn_class` — counts per `asn_class`.
  * `ips_by_region` — counts per IP `country_iso` / `region_id`.

#### Degree / neighbourhood metrics (binding for PASS)

To indicate graph structure:

* **Devices per entity**

  * `devices_per_party_min`, `devices_per_party_max`, `devices_per_party_mean`, `devices_per_party_pXX` (e.g. p50, p90, p99).
  * optional `devices_per_merchant_*` (similar metrics for merchants if merchant devices are modelled).

* **IPs per entity/device**

  * `ips_per_device_min`, `ips_per_device_max`, `ips_per_device_mean`, `ips_per_device_pXX`.
  * optional `ips_per_party_*` / `ips_per_merchant_*` if you model direct party/merchant–IP links.

* **Sharing indicators (global summaries)**

  * counts of:

    * devices used by more than one party,
    * IPs shared by more than one party,
    * high-degree IPs (e.g. “IPs with ≥K devices/parties”) per `ip_type`/`asn_class`.

#### RNG metrics

Per S4 RNG family:

* `rng_device_count_events`, `rng_device_count_draws`
* `rng_device_allocation_events`, `rng_device_allocation_draws`
* `rng_device_attribute_events`, `rng_device_attribute_draws`
* `rng_ip_count_events`, `rng_ip_count_draws`
* `rng_ip_allocation_events`, `rng_ip_allocation_draws`
* `rng_ip_attribute_events`, `rng_ip_attribute_draws`

These **must** reconcile with the RNG envelope/trace logs (see §8.1.6).

---

### 10.2 PASS vs FAIL semantics

For a **PASS** S4 run on `(mf, seed)`:

* `status == "PASS"`
* `error_code` is empty or null.
* All reported metrics **MUST** be consistent with S4 datasets:

  * `total_devices == COUNT(*)` over `s4_device_base_6A`.
  * `total_ips == COUNT(*)` over `s4_ip_base_6A`.
  * `devices_by_type`, `devices_by_os_family`, `devices_by_region` match `GROUP BY` results on the device base.
  * `ips_by_type`, `ips_by_asn_class`, `ips_by_region` match `GROUP BY` results on the IP base.
  * degree metrics (devices per party, ips per device, etc.) match aggregations computed from the link tables.

For a **FAIL** run:

* `status == "FAIL"`
* `error_code` is a non-empty `6A.S4.*` code.
* `total_devices`, `total_ips` and other metrics may be omitted or set to sentinel values; they are **not authoritative**.
* Downstream states MUST NOT treat a FAIL record as “good enough” to proceed.

S4 MUST NOT report `status="PASS"` unless:

* all acceptance criteria in §8 are satisfied, and
* all S4 datasets have been successfully written and validated.

---

### 10.3 Relationship between run-report and S4 datasets

For a **PASS** S4 run on `(mf, seed)`:

* The following partitions MUST exist and be schema-valid:

  * `s4_device_base_6A` at `(seed={seed}, fingerprint={mf})`,
  * `s4_ip_base_6A` at `(seed={seed}, fingerprint={mf})`,
  * `s4_device_links_6A` at `(seed={seed}, fingerprint={mf})`,
  * `s4_ip_links_6A` at `(seed={seed}, fingerprint={mf})`,
  * any implemented optional views (`s4_entity_neighbourhoods_6A`, `s4_network_summary_6A`).

* The run-report’s **binding metrics** MUST agree with queries over these datasets:

  * `total_devices` = `COUNT(*)` on `s4_device_base_6A`.
  * `total_ips` = `COUNT(*)` on `s4_ip_base_6A`.
  * `devices_by_type` = `GROUP BY device_type` on device base.
  * `ips_by_type`/`ips_by_asn_class`/`ips_by_region` = `GROUP BY` on IP base.
  * degree metrics = aggregations over link tables, expressed as:

    * devices per party: `COUNT(DISTINCT device_id)` grouped by `party_id` on `s4_device_links_6A`,
    * ips per device: `COUNT(DISTINCT ip_id)` grouped by `device_id` on `s4_ip_links_6A`,
    * etc.

If any of these basic reconciliations fails, S4 is not truly PASS and this is a spec violation.

For a **FAIL** run:

* S4 datasets (if present) MUST NOT be treated as valid for that `(mf, seed)`.
* Orchestration may delete/quarantine them, but downstream gating MUST be based on run-report `status` & `error_code`, not on file presence.

---

### 10.4 Gating behaviour in downstream states

All downstream states that depend on S4 — i.e.:

* 6A.S5 (fraud posture / roles), and
* 6B (flows / fraud), plus any external consumers of device/IP/graph data —

**MUST** incorporate S4’s run-report into their gates.

Before using S4 outputs for `(mf, seed)`, a downstream state MUST:

1. Locate the **latest** 6A.S4 run-report record for that `(mf, seed)`.

2. Require:

   ```text
   status     == "PASS"
   error_code == "" or null
   ```

3. Confirm that:

   * `s4_device_base_6A` exists, is schema-valid, and `COUNT(*)` matches `total_devices`.
   * `s4_ip_base_6A` exists, is schema-valid, and `COUNT(*)` matches `total_ips`.
   * `s4_device_links_6A` and `s4_ip_links_6A` exist and validate against their schemas.

If any of these checks fails, the downstream state MUST:

* treat S4 as **not available** for that `(mf, seed)`, and
* fail its own gate with an appropriate state-local error (e.g. `6A.S5.S4_GATE_FAILED`, `6B.S0.S4_GATE_FAILED`).

No downstream state may proceed on “partial” S4 outputs or on an S4 run that is not explicitly PASS.

---

### 10.5 Additional observability (recommended, non-semantic)

While not binding for correctness, implementations **should** also provide:

* Additional metrics in the run-report or in separate QA logs, such as:

  * number of **high-degree IPs** per `ip_type` (e.g. `degree ≥ K`),
  * number of **parties with no devices** or **no IPs** (if allowed),
  * counts of **shared devices** (devices linked to >1 party) and **shared IPs** (IPs linked to >1 party).

* INFO-level logs per S4 run summarising:

  * `(manifest_fingerprint, seed, parameter_hash)`,
  * `status`, `error_code`,
  * `total_devices`, `total_ips`,
  * high-level splits (devices_by_type, ips_by_type, degree summaries).

* DEBUG-level logs when troubleshooting:

  * lists of cells where realised device/IP density is significantly off priors (within configured tolerance bands),
  * detailed RNG accounting comparisons when a `RNG_ACCOUNTING_MISMATCH` occurs.

These are **operational conveniences**, not part of the formal contract; their formats may change over time, as long as the binding run-report fields and semantics remain stable.

---

### 10.6 Integration with higher-level monitoring

Engine-level monitoring / dashboards **MUST** be able to summarise S4’s health across worlds and seeds. At minimum:

* Per `manifest_fingerprint`:

  * S4 status per seed (PASS / FAIL / MISSING),
  * `total_devices` and `total_ips` per seed,
  * simple breakdowns (devices_by_type, ips_by_type, degree summaries).

* Cross-world/seed views:

  * distribution of `total_devices` and `total_ips`,
  * distribution of degree metrics (e.g. devices_per_party_mean across worlds),
  * counts of S4 FAILs by `error_code`,
  * correlations between S4 failures and upstream failures (S1/S2/S3).

The goal is that, from observability alone, an operator can answer:

> “For this world and seed, do we have a valid device/IP graph? How large is it, and how is it structured?”

without manually querying raw S4 datasets.

These observability and run-report integration rules are **binding** for S4’s contract with the rest of the engine.

---

## 11. Performance & scalability *(Informative)*

6A.S4 is the heaviest *graph* state in Layer-3: it can create **millions of devices**, **millions of IPs**, and **tens of millions of edges** per `(manifest_fingerprint, seed)` depending on how aggressive your priors are.

This section is **non-binding** — it describes expected scaling, not behaviour. The binding bits are in §§1–10 & 12.

---

### 11.1 Complexity profile

For a given `(manifest_fingerprint, seed)`, define:

* `P` — number of parties in `s1_party_base_6A`.
* `A` — number of accounts in `s2_account_base_6A`.
* `I_instr` — number of instruments in `s3_instrument_base_6A`.
* `D` — number of devices in `s4_device_base_6A` (what we generate).
* `I_ip` — number of IPs/endpoints in `s4_ip_base_6A`.
* `E_dev` — number of device edges (rows in `s4_device_links_6A`).
* `E_ip` — number of IP edges (rows in `s4_ip_links_6A`).
* `C_dev` — number of device planning cells.
* `C_ip` — number of IP planning cells.

Rough complexity:

* **Phase 1: Load gates/priors/taxonomies**

  * O(size of priors + taxonomies + S1/S2/S3 metadata), usually small compared to `P`, `A`, `D`, `I_ip`.

* **Phase 2: Continuous targets**

  * O(`C_dev + C_ip`) — per-cell arithmetic; typically hundreds–low thousands.

* **Phase 3: Integerisation**

  * O(`C_dev + C_ip`) — plus RNG calls; negligible vs per-entity/edge work.

* **Phase 4–6: Instantiation & wiring**

  * **Devices:** O(`D + P + A + |merchants|`) to build weights and allocate devices to entities.
  * **IPs:** O(`I_ip + D + P + |merchants|`) to build sharing structures and allocate IPs.
  * **Edges:** `E_dev` and `E_ip` scale with the realised degrees; this is usually the dominant cost.

* **Phase 7: Writing outputs & internal checks**

  * O(`D + I_ip + E_dev + E_ip`) for writes and basic validation, plus smaller overhead for neighbourhood/summary aggregations.

In practice:

> S4’s time is roughly linear in **D + I_ip + E_dev + E_ip**.
> `C_dev` and `C_ip` are tiny; the big knobs are “how many devices/IPs?” and “how dense is the graph?”.

---

### 11.2 Expected sizes & regimes

The actual numbers are governed by S4 priors, but a plausible ballpark for a “bank-sized” world:

* Parties: `P ≈ 10⁶ – 10⁷`

* Accounts: `A ≈ 1 – 5 × P`

* Devices:

  * a few per party on average → `D ≈ 2 – 4 × P` for consumer devices,
  * plus merchant devices (POS, ATMs, back-office terminals).

* IPs:

  * fewer than devices (bytes are expensive; IPs are more shared), often `I_ip ≈ 0.1 – 1 × D`,
  * with fan-out varying by `ip_type` (e.g. residential small fan-out, data-centre large).

* Edges:

  * `E_dev` (device links) ≈ O(D) in low-sharing worlds; can grow towards O(D × average_degree) if devices are heavily shared across entities.
  * `E_ip` (IP links) can grow large if IPs are highly shared — data-centre and VPN endpoints can have very high degrees by design.

As with S2/S3, the model is flexible enough to aim for *reduced* worlds for dev/CI (small P, A, D, I_ip) and much larger for production.

---

### 11.3 Parallelism & sharding

S4 is naturally parallelisable across several axes:

1. **Across seeds**

   * Each `(mf, seed)` is a hermetic universe; runs for different seeds can be fully parallel.
   * This is the primary horizontal sharding axis.

2. **Across planning cells within a seed**

   * Device and IP planning, integerisation, allocation and attribute sampling can be done per cell or per group of cells (e.g. per `(region, segment)`):

     * Device plan & allocation per `c_dev`,
     * IP plan & allocation per `c_ip`.

   * To stay deterministic:

     * define a **canonical ordering** over cells,
     * derive RNG substreams from `(mf, seed, "6A.S4", substream_label, cell_id)` independent of scheduling,
     * ensure canonical writer ordering when writing outputs, regardless of execution order.

3. **Streaming / batched generation**

   * You do **not** need full `D` devices or `I_ip` IPs in memory:

     * for each cell or batch of cells:

       * compute integer counts,
       * allocate to entities,
       * generate attributes,
       * stream out device/IP rows and links.

   * This pattern keeps memory bounded to “a few cells worth” of devices/IPs instead of the whole graph.

Given those levers, you can scale S4 from laptops to clusters without changing its observable behaviour.

---

### 11.4 Memory & IO considerations

**Memory**

* Priors, taxonomies, cell-level plans: small and easily cached.
* Heavy parts:

  * per-cell entity lists (e.g. parties/accounts/merchants in that cell),
  * per-entity degree counts,
  * per-cell allocations (devices/IPs) prior to write.

Recommended approach:

* **Chunk by cell or region:**

  * Build entity lists and plan for a small number of cells at a time,
  * allocate devices/IPs and write them out,
  * discard per-cell working sets and move to the next cell.

* **Track degrees in lightweight maps:**

  * running counts of devices per party/account/merchant and IPs per device/party,
  * only keep simple counters, not full adjacency in memory (links are persisted to storage).

**IO**

* Read side:

  * S1/S2/S3 bases — these can be scanned or accessed via partitioned joins (e.g. by region/segment) rather than loaded wholesale;
  * S4 priors/taxonomies — small; read once and cache;
  * optional context surfaces — moderate but still smaller than S4’s own graph.

* Write side:

  * dominated by `s4_device_base_6A`, `s4_ip_base_6A`, `s4_device_links_6A`, `s4_ip_links_6A`.
  * use columnar formats and sensible row-group sizes to minimise IO.

At realistic sizes, S4 is IO-heavy but not more so than 5B or a moderately large S2/S3 — as long as device/IP densities and degrees are kept within the intended ranges.

---

### 11.5 RNG cost & accounting

RNG cost is typically smaller than IO and graph operations but becomes noticeable for very large `D`, `I_ip`, `E_dev`, `E_ip`.

Approximate scaling:

* `device_count_realisation` & `ip_count_realisation`: O(`C_dev + C_ip`).
* `device_allocation_sampling`: O(`D` + `E_dev`), depending on whether you sample per device or per entity.
* `ip_allocation_sampling`: O(`I_ip` + `E_ip`).
* `device_attribute_sampling` & `ip_attribute_sampling`: O((`D` + `I_ip`) × attributes_per_entity).

Guidance:

* Use **vectorised Philox** draws (per cell / per batch) rather than one event per entity, while:

  * recording a single `rng_event_*` per batch,
  * correctly tracking `blocks` and `draws` metadata.

* Design RNG events so they are coarse enough for performance (e.g. per cell or per `(cell, attribute_family)`), but fine-grained enough to give meaningful auditability.

RNG budgets (max draws/events per family per `(mf, seed)`) should be tuned based on expected `D`, `I_ip`, `E_dev`, `E_ip`.

---

### 11.6 Operational tuning knobs

To keep S4 manageable across dev/CI/staging/prod, you can expose **non-semantic tuning parameters** via S4 priors/config (captured in `parameter_hash`):

* **Device density factors**

  * global or per-cell multipliers for `λ_devices_per_party` / `λ_devices_per_account` / `λ_devices_per_merchant`.
  * Example: 0.1× for CI (fewer devices), 1× for production-scale runs.

* **IP density & sharing factors**

  * global or per-cell multipliers for `λ_ips_per_device` / `λ_ips_per_party`,
  * adjustments to sharing distributions (e.g. fewer very high-degree IPs in test environments).

* **Degree caps**

  * hard caps on:

    * max devices per party/account/merchant,
    * max IPs per device/party/merchant,
    * max devices or parties per IP per `ip_type`/`asn_class`.

  * If caps make a plan infeasible, S4 should fail cleanly with explicit error codes, rather than emit an unreasonably dense graph.

* **Global safety caps**

  * maximum allowed `D`, `I_ip`, `E_dev`, `E_ip` per `(mf, seed)`.
  * if integerised totals exceed caps (e.g. due to misconfigured priors), S4 fails early.

* **Sharding hints**

  * non-semantic config describing preferred sharding for jobs (e.g. by region or segment), which orchestration can use to dispatch work.

All of these should be sealed as part of the S4 prior/config packs and thus reflected in `parameter_hash`.

---

### 11.7 Behaviour in stress & failure regimes

If priors/configs are mis-set or upstream worlds are very large, you might see:

* very high `total_devices` / `total_ips`,
* extreme `devices_per_party_*` or `ips_per_device_*` metrics,
* many residential IPs with unexpectedly high degrees, etc.

The design intent:

* S4 should detect **gross inconsistencies** and fail with specific codes:

  * `DEVICE_TARGETS_INCONSISTENT`, `DEVICE_INTEGERISATION_FAILED`,
  * `IP_TARGETS_INCONSISTENT`, `IP_INTEGERISATION_FAILED`,
  * `LINKAGE_RULE_VIOLATION`, `GRAPH_COUNTS_MISMATCH`, etc.

* S4’s run-report metrics (universes sizes, degree distributions, sharing summaries) should make failures and pathologies visible to operators.

For dev/CI:

* Use “small worlds” (reduced P/A) and low device/IP densities;
* keep the same structural priors so that behaviour scales predictably when densities are increased for production.

None of the above alters S4’s **binding** semantics; these notes are here to help ensure that implementations remain performant, auditable, and predictable as you scale to realistic fraud-modelling workloads.

---

## 12. Change control & compatibility *(Binding)*

This section fixes **how 6A.S4 is allowed to evolve** and what “compatible” means for:

* Upstream segments (1A–3B, 5A–5B).
* Upstream 6A states (S0–S3).
* Downstream 6A state (S5).
* 6B and any external consumers that rely on S4’s **device/IP graph**.

Any change that violates these rules is a **spec violation**, even if an implementation appears to work.

---

### 12.1 Versioning model for S4

S4 participates in the 6A versioning stack:

* `spec_version_6A` — overall 6A spec version (S0–S5).
* `spec_version_6A_S4` — effective version identifier for the S4 portion of the spec (you can encode this as a field in the run-report or within `spec_version_6A`).

Schema versions:

* `schemas.6A.yaml#/s4/device_base`
* `schemas.6A.yaml#/s4/ip_base`
* `schemas.6A.yaml#/s4/device_links`
* `schemas.6A.yaml#/s4/ip_links`
* `schemas.6A.yaml#/s4/entity_neighbourhoods` *(if present)*
* `schemas.6A.yaml#/s4/network_summary` *(if present)*

Catalogue versions:

* `dataset_dictionary.layer3.6A.yaml` entries for S4 datasets.
* `artefact_registry_6A.yaml` entries with `produced_by: 6A.S4` and S4 priors/taxonomies/config.

S4’s run-report **must** carry enough information (e.g. `spec_version_6A`, optional `spec_version_6A_S4`) for consumers to know **which S4 spec version** produced the graph for a given `(manifest_fingerprint, seed)`.

---

### 12.2 Backwards-compatible changes (allowed within a major version)

The following are **backwards compatible** *within a given major S4 spec version*, provided all binding constraints in §§1–11 still hold:

1. **Adding optional fields to S4 outputs**

   * New *optional* columns in:

     * `s4_device_base_6A`,
     * `s4_ip_base_6A`,
     * `s4_device_links_6A`,
     * `s4_ip_links_6A`,
     * optional `s4_entity_neighbourhoods_6A` / `s4_network_summary_6A`.

   * Examples:

     * extra static risk tags,
     * additional device/IP classification flags,
     * extra diagnostic counters/flags in neighbourhood/summary tables.

   * Existing consumers must be able to ignore unknown columns and treat them as non-semantic.

2. **Extending taxonomies**

   * Adding new enum values to device/IP taxonomies:

     * new `device_type` entries (e.g. a new wearable, a new POS variant),
     * new `ip_type`/`asn_class` entries,
     * new risk-tier enum values.

   * As long as:

     * existing codes retain their meaning,
     * compatibility rules are preserved (or extended in a backwards-compatible way).

   * Consumers should be written to tolerate unknown enum values (e.g. treating them as “other” until upgraded).

3. **Refining priors numerically (same semantics)**

   * Changing numeric parameters in S4 priors (device/IP densities, sharing distribution parameters, risk probabilities) while **keeping the same structure and interpretation**, e.g.:

     * slightly higher mobile device share in some regions,
     * slightly lower max degree for some IP types (within previously allowed ranges).

   * This changes realised graph statistics, but not:

     * identity rules,
     * PK/FK structure,
     * meaning of fields.

4. **Adding optional diagnostics / views**

   * Introducing new *optional* S4 datasets for QA/observability, provided they:

     * are registered in the dictionary/registry,
     * are clearly marked `status: optional`,
     * are strictly derived from existing bases/links,
     * do not affect S4 PASS criteria.

5. **Implementation & performance optimisations**

   * Changes to how S4 is implemented (caching, parallelism, streaming strategy, storage layout, indexing) that do not:

     * change the content of S4 outputs for fixed `(mf, ph, seed)` and inputs,
     * change RNG-family semantics,
     * or alter run-report semantics.

These changes typically correspond to **minor/patch** bumps to `spec_version_6A` / `spec_version_6A_S4` or schema semver, and require no behavioural changes from downstream beyond the standard “ignore unknown fields”.

---

### 12.3 Soft-breaking changes (require coordination but can be staged)

These changes can be made **compatible with care**, but require:

* a **spec/minor version bump**, and
* coordination between S4 and its consumers (S5, 6B, tooling).

1. **New required attributes in base or link schemas**

   * Making certain fields **required** where they were previously optional (e.g. introducing a mandatory `device_risk_tier` or `ip_risk_tier`) is only safe if:

     * consumers are updated to handle them, or
     * you stage the change:

       1. Add the field as optional and start populating it.
       2. Update consumers to recognise/use it.
       3. Promote it to `required` in a later spec version.

2. **New hard constraints in priors/linkage rules**

   * Tightening rules so S4 now rejects some graphs that were previously allowed, e.g.:

     * stricter maximum devices per party,
     * lower allowed parties per residential IP,
     * new disallowed `(device_type, segment_id)` or `(ip_type, asn_class)` combinations.

   * This can change which `(mf, seed)` worlds are valid and may increase S4 FAILs if priors/worlds aren’t adjusted accordingly.

3. **New S4 outputs considered “required”**

   * Upgrading a diagnostic dataset (e.g. neighbourhoods) from `status: optional` to `status: required`:

     * introduces a new dependency for S5/6B,
     * requires dictionary/registry updates and consumer changes.

4. **New device/IP types with non-trivial semantics**

   * Adding taxonomic categories that **downstream logic relies on** (e.g. a new `ip_type` that 6B treats as high-risk by design) can be soft-breaking for downstream if they don’t know how to handle them.

In all such cases:

* bump **minor** `spec_version_6A_S4`,
* document the change and its impact,
* consumers should check S4’s spec version and branch behaviour if needed.

---

### 12.4 Breaking changes (require major version bump)

The following are **breaking changes** and MUST NOT be introduced without:

* a **major** bump to `spec_version_6A` / `spec_version_6A_S4`,
* updated schemas, dictionaries and registries, and
* explicit migration guidance for S5, 6B and tooling.

1. **Changing identity or partitioning**

   * Changing primary key semantics, e.g.:

     * dropping `manifest_fingerprint` or `seed` from PKs,
     * changing `device_id` / `ip_id` uniqueness guarantees.

   * Changing partitioning:

     * altering `[seed, fingerprint]` to something else,
     * adding `scenario_id` as a partition key (moving from scenario-independent to scenario-dependent devices/IPs),
     * or removing `seed` from partitioning.

2. **Changing semantics of core fields**

   * Reinterpreting core fields, e.g.:

     * `device_type` changed to mean something else,
     * `ip_type` or `asn_class` reused for totally different categories,
     * `link_role` semantics changing in ways that contradict this spec,
     * `primary_party_id` / `primary_merchant_id` semantics being repurposed.

   * Reusing existing enum labels for unrelated concepts is especially breaking.

3. **Changing the device/IP generation & wiring law**

   * Any change in how priors → integer counts → allocations → attributes works that invalidates downstream assumptions, for example:

     * allowing devices/IPs that are not attached to any entity (e.g. free-floating nodes) where previously “everything attached” was assumed,
     * collapsing multiple devices into one or splitting one device into many in ways that change identity semantics,
     * drastically changing sharing logic (e.g. IPs no longer shared at all vs previously shared).

   * Changing the mapping between RNG families and operations (e.g. re-using `ip_allocation_sampling` for something else) is also behavioural and breaking.

4. **Changing relationships with S1/S2/S3**

   * Allowing device/IP links that do not conform to S1/S2/S3 universes (e.g. devices referencing non-account-backed pseudo-entities, without versioned extension),
   * removing the requirement that all device/IP links be to entities in S1/S2/S3/L1.

5. **Removing or renaming core S4 datasets**

   * Removing `s4_device_base_6A`, `s4_ip_base_6A`, `s4_device_links_6A`, or `s4_ip_links_6A`,
   * or renaming/replacing them with structurally incompatible datasets.

6. **Changing PASS criteria / gating semantics**

   * Relaxing acceptance criteria such that previously FAIL worlds would now be considered PASS *without* any corrective modelling, or
   * tightening them in ways that break previously valid worlds, without a clear migration path and version change.

Any such change must be treated as a **new major S4 spec version**, with downstream states updated to explicitly support that version.

---

### 12.5 Compatibility obligations for downstream states (S5, 6B)

Downstream S5 and 6B have explicit obligations:

1. **Version pinning**

   * Each state MUST declare a **minimum supported S4 spec version** (or version range), and:

     * inspect S4’s run-report,
     * fail fast if the S4 spec version for `(mf, seed)` is older than this minimum,
     * optionally reject or run in “legacy mode” for newer versions it does not yet understand.

2. **Graceful handling of unknown fields/enums**

   * Within a supported major version, downstream code MUST:

     * ignore additional optional fields in S4 outputs,
     * tolerate unknown enum values where the semantics are not critical (often treating them as “other”).

3. **No hard-coded layout**

   * S5/6B MUST:

     * resolve S4 datasets via dictionary/registry and `schema_ref`,
     * NOT assume fixed file names beyond templated `{seed, fingerprint}`,
     * NOT assume particular physical shard layouts beyond what is declared in the dictionary.

4. **No redefinition of S4 semantics**

   * Downstream specs or code MUST NOT:

     * redefine what `device_id`, `ip_id`, `device_type`, `ip_type`, `link_role` mean,
     * treat ad-hoc or external data sources as authoritative over S4 for devices/IPs/links.

   * S4’s base/link datasets are the **only** source of truth for device/IP existence and static wiring.

---

### 12.6 Migration & co-existence strategy

When a **breaking** S4 change is introduced:

* It MUST be released as a new major `spec_version_6A` / `spec_version_6A_S4`.
* Worlds produced under different S4 major versions MUST be clearly distinguishable via:

  * S4’s run-report `spec_version_6A[_S4]`,
  * optional annotations in the catalogue.

Deployments that need to support multiple S4 versions concurrently can:

* route different `(mf, seed)` universes to different downstream pipelines based on the S4 spec version,
* run S5/6B in dual-mode for a time (supporting both old/new S4) if necessary,
* restrict some downstream features to worlds with a minimum S4 spec version.

A single `(manifest_fingerprint, seed)` MUST be internally consistent with **one** S4 spec version; mixing outputs from different S4 versions into one logical graph is not allowed.

---

### 12.7 Non-goals

This section does **not**:

* version or constrain upstream segments (1A–3B, 5A–5B); they have their own change-control specs,
* determine how often device/IP priors are updated,
* specify CI/CD pipelines or branching strategies.

It **does** require that:

* any observable change to S4 behaviour (schema, identity, device/IP generation law, graph wiring, PASS criteria) is **explicitly versioned**,
* downstream components never assume compatibility purely from context,
* and any change that affects device/IP identity, counts, or graph semantics is treated as deliberate spec evolution, not a hidden implementation tweak.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the short-hands and symbols used in **6A.S4**.
If anything here appears to contradict §§1–12 or the JSON-Schemas, the binding sections and schemas win.

---

### 13.1 Identity axes & core IDs

* **`mf`**
  Shorthand for **`manifest_fingerprint`**.
  Identifies the sealed upstream world (L1+L2) and the 6A input universe. All S4 work is scoped to a single `mf`.

* **`ph`**
  Shorthand for **`parameter_hash`**.
  Identifies the parameter / prior pack set (including S4 device/IP priors, taxonomies, graph/linkage configs). Must be consistent across all S4 outputs for a given `(mf, seed)`.

* **`seed`**
  RNG identity for S4 (and Layer-3 more broadly).
  Different seeds under the same `(mf, ph)` correspond to different party+account+instrument+device/IP universes.

* **`party_id`**
  Identifier for a party/customer, defined by S1.
  Unique within `(mf, seed)`; S4 treats `(mf, seed, party_id)` as FK into `s1_party_base_6A`.

* **`account_id`**
  Identifier for an account/product, defined by S2.
  Unique within `(mf, seed)`; S4 treats `(mf, seed, account_id)` as FK into `s2_account_base_6A`.

* **`instrument_id`**
  Identifier for an instrument/credential, defined by S3.
  Unique within `(mf, seed)`; S4 treats `(mf, seed, instrument_id)` as FK into `s3_instrument_base_6A`.

* **`device_id`**
  Identifier for a device, created by S4.
  S4 guarantees uniqueness of `(mf, seed, device_id)`.

* **`ip_id`**
  Identifier for an IP / endpoint, created by S4.
  S4 guarantees uniqueness of `(mf, seed, ip_id)`.

---

### 13.2 Counts, sets & graph notation

High-level counts (per `(mf, seed)`):

* **`P`** — number of parties:
  `P = COUNT(*) in s1_party_base_6A`.

* **`A`** — number of accounts:
  `A = COUNT(*) in s2_account_base_6A`.

* **`I_instr`** — number of instruments:
  `I_instr = COUNT(*) in s3_instrument_base_6A`.

* **`D`** — number of devices:
  `D = COUNT(*) in s4_device_base_6A`.

* **`I_ip`** — number of IPs/endpoints:
  `I_ip = COUNT(*) in s4_ip_base_6A`.

* **`E_dev`** — number of device edges:
  `E_dev = COUNT(*) in s4_device_links_6A`.

* **`E_ip`** — number of IP edges:
  `E_ip = COUNT(*) in s4_ip_links_6A`.

Sets & domains:

* **`R`** — set of regions or countries (e.g. region_id or ISO country codes).
* **`T_party`** — set of party types (e.g. `RETAIL`, `BUSINESS`, `OTHER`).
* **`S_seg`** — set of segments (e.g. `STUDENT`, `SALARIED`, `SME`, `CORPORATE`, …).
* **`T_acc`** — set of account types (e.g. `CURRENT_ACCOUNT`, `SAVINGS_ACCOUNT`, `CREDIT_CARD`, …) if used in S4 priors.
* **`T_ip`** — set of IP types (e.g. `RESIDENTIAL`, `MOBILE`, `CORPORATE`, `DATACENTRE`, `VPN_PROXY`, `PUBLIC_WIFI`, …).
* **`ASN_classes`** — set of ASN classes (e.g. `CONSUMER_ISP`, `MNO`, `HOSTING_PROVIDER`, `ENTERPRISE_NETWORK`, …).

Graph-related notation:

* **`deg_D(p)`** — degree of party `p` in the **device** graph (number of distinct devices linked to that party).
* **`deg_IP(p)`** — degree of party `p` in the **IP** graph (number of distinct IPs linked).
* **`deg_D(ip)`** — number of devices linked to IP `ip`.
* **`deg_P(ip)`** — number of parties linked to IP `ip` (directly or via devices, depending on modelling choice).

---

### 13.3 Planning cells & targets

S4 plans devices and IPs over **planning cells**. The exact structure of cells is locked in the concrete S4 design, but we use generic notation here.

#### 13.3.1 Device planning cells

A typical **device planning cell**:

```text
c_dev ∈ C_dev ≔ (region_id, party_type, segment_id[, account_type_class])
```

Where:

* `region_id` / `country_iso` — derived from S1/S2 (party or account home region).
* `party_type`, `segment_id` — from S1.
* `account_type_class` — optional coarse grouping of account types if device priors depend on products.

Key quantities:

* **`N_parties(c_dev)`** — number of parties in cell `c_dev`.

* **`N_accounts(c_dev)`** — number of accounts in cell `c_dev` (if used).

* **`N_merchants(c_dev)`** — number of merchants in cell `c_dev` (for merchant devices, if used).

* **`λ_devices_per_party(c_dev)`** — expected devices per party in this cell.

* **`λ_devices_per_account(c_dev)`** — expected devices per account in this cell (if used).

* **`λ_devices_per_merchant(c_dev)`** — expected devices per merchant (if used).

* **`N_device_target(c_dev)`** — continuous target number of devices in cell:

  ```text
  N_device_target(c_dev) =
      N_parties(c_dev)   × λ_devices_per_party(c_dev)
    + N_accounts(c_dev)  × λ_devices_per_account(c_dev)
    + N_merchants(c_dev) × λ_devices_per_merchant(c_dev)
  ```

* **Device-type mix:**

  * `π_device_type | c_dev(device_type)` — fractional share per device_type in cell `c_dev`.
  * `N_device_target(c_dev, device_type) = N_device_target(c_dev) × π_device_type | c_dev(device_type)`.

* **Realised counts:**

  * `N_device(c_dev, device_type)` — integer number of devices in cell `(c_dev, device_type)` after integerisation.
  * `N_dev_world_int = Σ_{c_dev,type} N_device(c_dev, type)` — total devices for `(mf, seed)`.

#### 13.3.2 IP planning cells

A typical **IP planning cell**:

```text
c_ip ∈ C_ip ≔ (region_id, ip_type, asn_class)
```

Where:

* `ip_type` — as per IP taxonomy (RESIDENTIAL, MOBILE, …).
* `asn_class` — provider class (CONSUMER_ISP, MNO, HOSTING_PROVIDER, …).

Key quantities:

* **`N_ip_target(c_ip)`** — continuous target number of IPs/endpoints in `c_ip`.

* **`N_ip(c_ip)`** — realised integer number of IPs/endpoints in `c_ip`.

* **`N_ip_world_int = Σ_{c_ip} N_ip(c_ip)`** — total IPs for `(mf, seed)`.

* IP-sharing priors:

  * distributions for **devices per IP** and **parties per IP** per `ip_type`/`asn_class`.

---

### 13.4 Taxonomy & attribute symbols

Device taxonomy fields (examples):

* **`device_type`**
  Enum describing device class, e.g.:

  * `MOBILE_PHONE`, `TABLET`, `LAPTOP`, `DESKTOP`,
  * `POS_TERMINAL`, `ATM`, `KIOSK`, etc.

* **`os_family`**
  Enum, e.g. `ANDROID`, `IOS`, `WINDOWS`, `MACOS`, `LINUX`, `EMBEDDED`, etc.

* **`ua_family`** (optional)
  Enum capturing UA / browser/app families (e.g. `CHROME`, `SAFARI`, `APP_X`, …).

* **`device_class`** (optional)
  Coarse bucket for device role, e.g. `CONSUMER_PERSONAL`, `CONSUMER_SHARED`, `MERCHANT_FIXED`, `MERCHANT_MPOS`.

* **Device risk flags** (examples):
  `is_emulator`, `is_jailbroken`, `is_rooted`, `device_risk_tier ∈ {LOW, STANDARD, HIGH}`.

IP taxonomy fields (examples):

* **`ip_type`**
  Enum for IP role, e.g.:

  * `RESIDENTIAL`, `MOBILE`, `CORPORATE`,
  * `DATACENTRE`, `VPN_PROXY`, `PUBLIC_WIFI`.

* **`asn_class`**
  Enum for ASN/provider class, e.g.:

  * `CONSUMER_ISP`, `MNO`, `HOSTING_PROVIDER`, `ENTERPRISE_NETWORK`.

* **IP risk fields** (optional):
  `ip_risk_tier`, boolean flags like `is_known_proxy_range`, etc.

IP representation fields:

* **`ip_address_masked`**
  Masked / bucketed representation of an IP or prefix (e.g. `203.0.113.0/24`, or obfuscated token).
* **`cidr` / `ip_prefix`**
  If you model IP ranges.

Geo & context fields (device/IP):

* **`home_region_id`**, **`home_country_iso`** (device-level) — coarse geolocation of device.
* **`country_iso`**, **`region_id`** (IP-level) — coarse geolocation of IP/endpoint.

---

### 13.5 Roles, status & scope in `sealed_inputs_6A` (S4-relevant)

From `sealed_inputs_6A`:

* **`role`** (S4 cares about):

  * `DEVICE_PRIOR` — device density and device-type mix priors.
  * `IP_PRIOR` / `ENDPOINT_PRIOR` — IP density and IP-type mix priors.
  * `GRAPH_LINKAGE_RULES` / `DEVICE_LINKAGE_RULES` — graph structure & sharing rules.
  * `TAXONOMY` — device & IP taxonomies (device_type, os_family, ip_type, asn_class, risk tiers).
  * `UPSTREAM_EGRESS` / `POPULATION_PRIOR` — optional context surfaces (connectivity, region-level stats).
  * `SCENARIO_CONFIG` — optional scenario/volume context (aggregated; never per-arrival).
  * `CONTRACT` — schemas/dictionaries/registries (metadata-only).

* **`status`**:

  * `REQUIRED` — S4 cannot run without this artefact.
  * `OPTIONAL` — S4 can branch behaviour when this artefact is present vs absent.
  * `IGNORED` — S4 must not use this artefact.

* **`read_scope`**:

  * `ROW_LEVEL` — S4 may read rows and use them in business logic.
  * `METADATA_ONLY` — S4 may only use presence, schema and digest (no row-level reads).

S4’s effective input set is: rows with `status ∈ {REQUIRED, OPTIONAL}` and `read_scope=ROW_LEVEL` for business logic, plus contracts with `METADATA_ONLY`.

---

### 13.6 RNG symbols & families

S4 uses the shared **Layer-3 Philox-2x64-10** engine with S4-specific RNG families:

* **Philox-2x64-10**
  Counter-based RNG engine with 2×64-bit state and 10 rounds, used everywhere in the engine.

* **Substream / label**
  A logical tag used to derive Philox keys for S4:

  * `"6A.S4.device_count_realisation"`
  * `"6A.S4.device_allocation_sampling"`
  * `"6A.S4.device_attribute_sampling"`
  * `"6A.S4.ip_count_realisation"`
  * `"6A.S4.ip_allocation_sampling"`
  * `"6A.S4.ip_attribute_sampling"`

* **`device_count_realisation`**
  RNG family for converting continuous device targets `N_device_target(c_dev, type)` into integer counts `N_device(c_dev, type)`.

* **`device_allocation_sampling`**
  RNG family for allocating devices to parties/accounts/merchants in each cell, consistent with sharing/linkage priors.

* **`device_attribute_sampling`**
  RNG family for sampling device attributes (os_family, ua_family, risk flags, etc.) from conditional priors.

* **`ip_count_realisation`**
  RNG family for converting continuous IP targets `N_ip_target(c_ip)` into integer counts `N_ip(c_ip)`.

* **`ip_allocation_sampling`**
  RNG family for wiring IPs to devices/parties/merchants (IP-sharing topology).

* **`ip_attribute_sampling`**
  RNG family for sampling IP attributes (ip_risk_tier, masked representation, geo buckets, etc.).

RNG events:

* **`rng_event_device_count`**
* **`rng_event_device_allocation`**
* **`rng_event_device_attribute`**
* **`rng_event_ip_count`**
* **`rng_event_ip_allocation`**
* **`rng_event_ip_attribute`**

Each event records:

* `counter_before`, `counter_after` (Philox counters),
* `blocks`, `draws`,
* contextual keys (world, seed, cell identifiers, attribute family),
* optional summary statistics (e.g. realised degree distribution per cell).

---

### 13.7 Miscellaneous shorthand & conventions

* **“World”**
  Shorthand for “all artefacts tied to a single `manifest_fingerprint`”.

* **“Device universe”**
  The set of all `device_id` rows in `s4_device_base_6A` for `(mf, seed)`.

* **“IP universe”**
  The set of all `ip_id` rows in `s4_ip_base_6A` for `(mf, seed)`.

* **“Graph” / “device/IP graph”**
  The combined structure defined by S4’s base and link datasets:

  * nodes: parties, accounts, instruments, merchants (from S1–S3/L1) plus devices and IPs,
  * edges: `s4_device_links_6A` and `s4_ip_links_6A`.

* **“Neighbourhood”**
  The set of directly connected devices/IPs or entities around a node (party/account/instrument/merchant), often summarised in `s4_entity_neighbourhoods_6A`.

* **“Degree” / “fan-out”**
  Number of edges incident to a node (devices per party; IPs per device; devices per IP; parties per IP, etc.).

* **“Conservation”** (informal)
  That integer counts and graph structures match the planned targets and invariants:

  * Σ realised device/IP counts equals planned totals,
  * neighbourhoods and summaries match base+link tables,
  * degree distributions lie within configured bounds.

This appendix is **informative**, intended to make the S4 spec easier to read and implement.

---