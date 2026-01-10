# 6A.S0 — Gate & sealed inputs for the entity & product world (Layer-3 / Segment 6A)

## 1. Purpose & scope *(Binding)*

6A.S0 is the **entry gate and trust boundary** for the Layer-3 / Segment 6A entity & product world.

Its purpose is to:

* **Bind 6A to a single world** identified by `manifest_fingerprint`, and assert which upstream segments (Layer-1: 1A–3B, Layer-2: 5A–5B) are considered **sealed and trusted** for that world.
* **Discover and freeze** the exact set of artefacts that 6A is allowed to read — upstream egress, Layer-3 contracts, and 6A priors/configs — into a **sealed input universe**.
* Publish this universe as:

  * a **gate receipt** (`s0_gate_receipt_6A`), and
  * a **sealed-inputs manifest** (`sealed_inputs_6A`),
    which all downstream 6A states (and 6B) must treat as the **sole authority** on what 6A may depend on.

S0 is **purely control-plane**:

* It is **RNG-free** and does not derive any new business state.
* It **does not** create entities, accounts, instruments, devices, IPs, or fraud roles.
* It **does not** read or attach individual arrivals from 5B; it only reasons about the existence and validity of upstream HashGates and contracts at the metadata level.

Within 6A, S0’s scope is to:

* Verify, for the current `manifest_fingerprint`, that all **required upstream HashGates** (1A–3B, 5A, 5B) are present and internally consistent according to their own validation-bundle contracts.
* Confirm the presence and internal consistency of **Layer-3 / 6A binding contracts**:

  * `schemas.layer3.yaml` and `schemas.6A.yaml`,
  * `dataset_dictionary.layer3.6A.yaml`,
  * `artefact_registry_6A.yaml`,
  * and all 6A **prior/config** artefacts (population, segmentation, product mix, device/IP, fraud posture, taxonomies) referenced therein.
* Construct a **closed-world list of authorised inputs** for 6A (upstream egress + 6A configs), with explicit roles, digests, and read scopes, and seal it under a deterministic digest (`sealed_inputs_digest_6A`).

S0 is a **hard precondition** for the rest of 6A:

* All later 6A states **MUST** read `s0_gate_receipt_6A` and `sealed_inputs_6A`, verify the sealed-inputs digest, and refuse to run if S0 is missing or not PASS.
* 6B and downstream consumers **MAY** use S0’s gate receipt (together with the eventual 6A segment HashGate) to assert that any 6A entity/graph artefact was produced under a well-defined, sealed upstream universe.

Anything outside this scope - entity generation, assignment of products, construction of the device/IP graph, or static fraud posture - is **out of scope for S0** and belongs to later 6A states.

---

### Cross-Layer Inputs (Segment 6A)

**Upstream segments required:** 1A-3B + 5A-5B validation bundles + `_passed.flag` (1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B) for the target `manifest_fingerprint`.

**Upstream data surfaces (sealed by S0 and listed in `sealed_inputs_6A`):**
* Layer-1 egress: `outlet_catalogue`, `site_locations`, `site_timezones`, `tz_timetable_cache`, `zone_alloc`, `zone_alloc_universe_hash`, `virtual_classification_3B`, `virtual_settlement_3B`, `edge_universe_hash_3B`, `virtual_routing_policy_3B`
* Layer-2 egress: `merchant_zone_profile_5A`, `arrival_events_5B`

**Layer-3 / 6A priors, taxonomies, and policies (sealed by S0):**
* Population/segmentation: `prior_population_6A`, `prior_segmentation_6A`, `taxonomy_party_6A`
* Accounts/products: `prior_account_per_party_6A`, `prior_product_mix_6A`, `taxonomy_account_types_6A`
* Instruments: `prior_instrument_per_account_6A`, `prior_instrument_mix_6A`, `taxonomy_instrument_types_6A`
* Devices/IPs: `prior_device_counts_6A`, `taxonomy_devices_6A`, `prior_ip_counts_6A`, `taxonomy_ips_6A`
* Fraud roles: `prior_party_roles_6A`, `prior_account_roles_6A`, `prior_merchant_roles_6A`, `prior_device_roles_6A`, `prior_ip_roles_6A`, `taxonomy_fraud_roles_6A`
* Linkage and constraints: `graph_linkage_rules_6A`, `device_linkage_rules_6A`, `product_linkage_rules_6A`, `product_eligibility_config_6A`, `instrument_linkage_rules_6A`
* Validation: `validation_policy_6A`

**Gate expectations:** upstream PASS evidence (validation_bundle_* + `_passed.flag`) for 1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B MUST verify before any 6A read.

### Contract Card (S0) - inputs/outputs/authorities

**Inputs (authoritative; see Section 2 for full list):**
* `validation_bundle_1A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_1A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_bundle_1B` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_1B` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_bundle_2A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_2A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_bundle_2B` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_2B` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_bundle_3A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_3A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_bundle_3B` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_3B` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_bundle_5A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_5A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_bundle_5B` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_5B` - scope: FINGERPRINT_SCOPED; gate: required
* `outlet_catalogue` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `site_locations` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `site_timezones` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `tz_timetable_cache` - scope: FINGERPRINT_SCOPED; sealed_inputs: optional
* `zone_alloc` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `zone_alloc_universe_hash` - scope: FINGERPRINT_SCOPED; sealed_inputs: required
* `virtual_classification_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `virtual_settlement_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional
* `edge_universe_hash_3B` - scope: FINGERPRINT_SCOPED; sealed_inputs: required
* `virtual_routing_policy_3B` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `merchant_zone_profile_5A` - scope: FINGERPRINT_SCOPED; sealed_inputs: required
* `arrival_events_5B` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, scenario_id]; sealed_inputs: required
* `prior_population_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `prior_segmentation_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `taxonomy_party_6A` - scope: UNPARTITIONED (sealed taxonomy); sealed_inputs: required
* `prior_account_per_party_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `prior_product_mix_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `taxonomy_account_types_6A` - scope: UNPARTITIONED (sealed taxonomy); sealed_inputs: required
* `prior_instrument_per_account_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `prior_instrument_mix_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `taxonomy_instrument_types_6A` - scope: UNPARTITIONED (sealed taxonomy); sealed_inputs: required
* `prior_device_counts_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `taxonomy_devices_6A` - scope: UNPARTITIONED (sealed taxonomy); sealed_inputs: required
* `prior_ip_counts_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `taxonomy_ips_6A` - scope: UNPARTITIONED (sealed taxonomy); sealed_inputs: required
* `prior_party_roles_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `prior_account_roles_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `prior_merchant_roles_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `prior_device_roles_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `prior_ip_roles_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `taxonomy_fraud_roles_6A` - scope: UNPARTITIONED (sealed taxonomy); sealed_inputs: required
* `graph_linkage_rules_6A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `device_linkage_rules_6A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `product_linkage_rules_6A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `product_eligibility_config_6A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `instrument_linkage_rules_6A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `validation_policy_6A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required

**Authority / ordering:**
* S0 defines no data ordering; it only seals inputs and verifies upstream gate evidence.

**Outputs:**
* `s0_gate_receipt_6A` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `sealed_inputs_6A` - scope: FINGERPRINT_SCOPED; gate emitted: none

**Sealing / identity:**
* External inputs MUST appear in `sealed_inputs_6A` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing/invalid gate evidence or required sealed inputs -> abort; no outputs published.

## 2. Preconditions, upstream gates & sealed inputs *(Binding)*

6A.S0 only runs in a world where **Layer-1 and Layer-2 are already sealed** for a given `manifest_fingerprint`, and where the **Layer-3 / 6A contracts and priors** are present and internally consistent.

This section fixes what “sealed” means for 6A, which upstream HashGates it must verify, and what is in scope for the **sealed inputs universe** that S0 will expose to later 6A states.

---

### 2.1 World & engine preconditions

For a given `manifest_fingerprint` that 6A intends to serve, S0 assumes:

* The engine has **already established** `parameter_hash` and `manifest_fingerprint` using its global law (Layer-0 / control-plane), and these values are stable for the run.

* Layer-1 and Layer-2 **shape authority** is available and schema-valid:

  * `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.layer2.yaml`,
  * corresponding dataset dictionaries and artefact registries for 1A–3B and 5A–5B.

* Layer-3 contracts are present in the catalogue:

  * `schemas.layer3.yaml` (shared Layer-3 primitives),
  * `schemas.6A.yaml` (6A-specific tables),
  * `dataset_dictionary.layer3.6A.yaml`,
  * `artefact_registry_6A.yaml`.

If any of these are missing or fail schema validation, S0 **must not** proceed and must fail with a 6A.S0 contract error (see §9).

---

### 2.2 Required upstream HashGates (Layer-1 & Layer-2)

For the target `manifest_fingerprint`, S0 must verify that all upstream segments 6A conceptually depends on have **sealed and trusted egress** according to their own contracts:

* **Layer-1 (merchant, geo, zone, virtual world):**

  * 1A: `_passed.flag` and `validation_bundle_1A`
  * 1B: `_passed.flag` and `validation_bundle_1B`
  * 2A: `_passed.flag` and `validation_bundle_2A`
  * 2B: `_passed.flag` and `validation_bundle_2B`
  * 3A: `_passed.flag` and `validation_bundle_3A`
  * 3B: `_passed.flag` and `validation_bundle_3B`

* **Layer-2 (intensity & arrivals):**

  * 5A: `_passed.flag` and `validation_bundle_5A`
  * 5B: `_passed.flag` and `validation_bundle_5B`

For each of the above segments S0 must:

1. Locate the `validation_bundle_*` directory for this `manifest_fingerprint` using the shared dataset dictionary and artefact registry (no hard-coded paths).
2. Read the segment’s `validation_bundle_index_*` (or equivalent `index.json`) and compute the **bundle digest** according to that segment’s own HashGate law.
3. Compare the computed digest with the corresponding `_passed.flag` contents.

S0 may only declare **PASS** if **all** of these verifications succeed. If any required flag or bundle is:

* missing,
* not reachable via the catalogue,
* or digest-mismatched,

then S0 must fail with a specific upstream‐gate error and **must not** emit a `s0_gate_receipt_6A` for that `manifest_fingerprint`.

---

### 2.3 Layer-3 / 6A contract preconditions

Before constructing any 6A gate artefacts, S0 must ensure that the **6A contracts themselves are coherent**:

* **Schema preconditions:**

  * `schemas.layer3.yaml` and `schemas.6A.yaml` are present, JSON-Schema valid, and refer only to `$defs` that exist in their declared scope.
  * There are no conflicting definitions between `schemas.layer3.yaml` and `schemas.6A.yaml` for the same `$id` / type name.

* **Catalogue preconditions:**

  * `dataset_dictionary.layer3.6A.yaml` is present, schema-valid, and all `schema_ref` entries resolve into `schemas.layer3.yaml` or `schemas.6A.yaml`.
  * `artefact_registry_6A.yaml` is present, schema-valid, and its entries are consistent with the dataset dictionary (matching `manifest_key`, `path`, `partitioning`, `schema_ref`).

* **Prior/config preconditions:**

  For each 6A prior/config artefact referenced in the 6A registry (population priors, segment priors, product mix priors, device/IP priors, fraud-role priors, taxonomies):

  * the artefact must exist and be schema-valid;
  * its version/digest must match what the registry declares.

If any of these checks fail, S0 must fail with a `6A.S0` contract/prior error and refuse to emit gate artefacts.

---

### 2.4 Universe of sealed inputs S0 is allowed to consider

Subject to §2.2 and §2.3, S0 defines the universe of artefacts that **may** appear in `sealed_inputs_6A`. This universe includes:

* **Upstream egress candidates** (readable later by 6A, but not row-scanned in S0):

  * L1 world surfaces (as seen in their dictionaries):

    * 1A: merchant catalogue (`outlet_catalogue`).
    * 1B: site geometry (`site_locations`).
    * 2A: `site_timezones`, `tz_timetable_cache`.
    * 3A: `zone_alloc`, `zone_alloc_universe_hash`.
    * 3B: virtual classification & routing contracts (`virtual_classification_3B`, `virtual_settlement_3B`, `edge_universe_hash_3B`, `virtual_routing_policy_3B`).

  * L2 context surfaces:

    * 5A: `merchant_zone_profile_5A` and related intensity surfaces.
    * 5B: `arrival_events_5B` and associated contracts (metadata-only from S0’s perspective).

* **Layer-3 / 6A contracts and priors:**

  * Schemas and dataset dictionary entries for 6A itself.
  * 6A prior/config packs (population, segmentation, product mix, devices/IPs, fraud roles).
  * Any Layer-3-wide taxonomies or enumeration bundles consumed by 6A.

For each candidate artefact in this universe, S0 will decide whether it is:

* `REQUIRED` (6A may not proceed without it),
* `OPTIONAL` (6A states may choose to branch on its presence), or
* `IGNORED` (not available to 6A at all),

and will assign an explicit `read_scope`:

* `ROW_LEVEL` — later 6A states may read its rows, or
* `METADATA_ONLY` — only its existence, shape, and digests may be used.

S0 is **not** allowed to add arbitrary, ad-hoc inputs: every artefact it seals must be discoverable via the engine’s schema/dictionary/registry catalogue and must belong to this universe.

---

### 2.5 Preconditions for S0 itself

6A.S0 may start work for a given `manifest_fingerprint` only if:

* a world with that `manifest_fingerprint` is known to the orchestrator, and
* the engine can resolve all required upstream HashGates, schemas, dictionaries, and registries through the catalogue.

S0 **must abort early** if:

* world identity (`manifest_fingerprint`) is unknown or inconsistent with upstream bundles,
* it cannot resolve any of the required upstream or 6A contract artefacts from the catalogue, or
* it detects more than one conflicting candidate for a supposedly unique artefact (e.g. multiple conflicting registry entries for the same manifest key).

Only when all of the above preconditions are satisfied may S0 proceed to construct `sealed_inputs_6A` and `s0_gate_receipt_6A`.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes, for all of 6A, **what S0 treats as input** and **who is allowed to define what**. Later 6A states (S1–S5) must treat this section as the *binding* description of their upstream and contract boundaries — they **must not** silently broaden or shrink these inputs.

---

### 3.1 Logical input groups

S0 reasons about three logical groups of inputs:

1. **Upstream segment HashGates & egress contracts**
   These define the **sealed world** that 6A is allowed to build upon.

   * Layer-1 (world geometry, time, routing, virtuality):

     * 1A: merchant and outlet catalogue.
     * 1B: site geometry (`site_locations`).
     * 2A: civil time (`site_timezones`, `tz_timetable_cache`).
     * 2B: routing surfaces (site weights, alias tables, day effects, tz-group mixes).
     * 3A: zone allocation (`zone_alloc`, `zone_alloc_universe_hash`).
     * 3B: virtual overlay (classification, settlement nodes, CDN edges, `edge_universe_hash_3B`, `virtual_routing_policy_3B`).

   * Layer-2 (intensity & arrivals):

     * 5A: deterministic intensity surfaces (merchant×zone profiles, shapes, baselines, scenario overlays).
     * 5B: arrival realisation (`arrival_events_5B`) and its own validation bundle.

   S0 **reads these only at the level of bundles, flags, schemas, dictionaries and registries**. It does not scan row-level data and does not reinterpret their internal invariants.

2. **Layer-3 / 6A contracts**

   These are the **shape and identity authorities** for 6A itself:

   * `schemas.layer3.yaml` — common Layer-3 primitives (entity IDs, account IDs, device/IP types, fraud role enums).
   * `schemas.6A.yaml` — 6A-specific tables (customers, accounts, instruments, devices, IPs, graphs, fraud-role tables).
   * `dataset_dictionary.layer3.6A.yaml` — dataset IDs, paths, partitions, schema refs for 6A.
   * `artefact_registry_6A.yaml` — manifest keys, digests, and dependency declarations for 6A artefacts.

3. **6A priors & configuration packs**

   These are the **governing knobs** for entity & product generation:

   * Population priors (total population, regional splits, segment mix).
   * Segmentation priors (customer segment distributions, business vs retail, lifecycle stages).
   * Product mix priors (accounts per customer, cards per account, loans per segment, merchant account mixes).
   * Device/IP priors (devices per customer, device types, IP types, sharing patterns).
   * Fraud-role priors (proportions of mules, synthetic IDs, collusive merchants, risky devices/IPs).
   * Taxonomy packs (customer segments, merchant risk classes, fraud-role enums, any other 6A-scope enumerations).

S0’s job is to discover, validate, and seal **exactly which artefacts** from these groups will be available to 6A. It does **not** derive any new business logic from them.

---

### 3.2 Authority boundaries — what 6A may and may not redefine

All later 6A states must respect the following authority boundaries.

#### 3.2.1 Layer-1 / Layer-2 authority

* **Merchant & site geometry** (1A, 1B)

  * *Authority:* 1A/1B schemas + validation bundles.
  * 6A **must not** create, delete, or relabel merchants or sites; it may only refer to them (e.g. to derive customer home regions or merchant risk posture).

* **Civil time** (2A)

  * *Authority:* 2A `site_timezones` and `tz_timetable_cache`.
  * 6A **must not** introduce its own timezone mapping rules; any “home-clock” or “entity local time” semantics that depend on IANA tzids must be derived via 2A.

* **Routing & zones** (2B, 3A, 3B)

  * *Authority:* 2B routing surfaces, 3A `zone_alloc` + universe hash, 3B virtual overlay and universe hash.
  * 6A **must not** change or reinterpret routing weights, alias laws, zone allocations, or virtual edge universes.
  * 6A **may** *consume* zonal, physical/virtual, or region information as context for entity priors (e.g. more cross-border customers where merchants are more cross-zone), but routing itself remains upstream law.

* **Intensity & arrivals** (5A, 5B)

  * *Authority:* 5A λ surfaces, 5B arrival stream + validation bundle.
  * 6A **must not** resample or adjust intensities or arrival counts; it does not own “how many events” or “when they occur”.
  * 6A **may** use aggregate information (e.g. volume per region) as a *prior* for population sizes or fraud posture, but actual arrivals remain 5B’s responsibility and will only be attached to entities in 6B.

#### 3.2.2 6A authority

Within Layer-3:

* **6A contracts** (schemas, dictionary, registry) are the **sole authority** on:

  * the shape of 6A entity tables (customers, accounts, instruments, devices, IPs, graphs, fraud roles),
  * how those datasets are partitioned and keyed,
  * which artefacts belong to 6A and how they are versioned.

* **6A priors & config packs** are the **sole authority** on:

  * how many entities of each kind exist and how they are distributed,
  * product holdings,
  * device/IP sharing structure,
  * static fraud-role proportions.

No upstream segment forbids or constrains these beyond what is stated in its own contracts; 6A is free to choose any entity model that remains **internally consistent** and **compatible with the upstream world** as described above.

#### 3.2.3 Non-inputs and forbidden dependencies

S0 and all later 6A states **must not** depend on:

* Wall-clock time or environment (e.g. “today”, “now”) for business semantics.
* Non-catalogued data sources (no ad-hoc files, network calls, ad-hoc APIs).
* Implementation details of upstream validation bundles beyond:

  * their published `index.json` / validation index,
  * their `_passed.flag` contents,
  * any specific evidence artefacts explicitly referenced in upstream specs.

Any such dependency must be treated as an implementation detail outside the scope of this design and must not affect 6A behaviour.

---

### 3.3 How S0 exposes input authority to later 6A states

S0 does not perform entity modelling itself; it **publishes the input authority** so that S1–S5 can rely on it without rediscovering it.

It does so by:

* Emitting `sealed_inputs_6A`, where each row:

  * names an upstream or 6A artefact,
  * declares its `role` (e.g. `upstream_egress`, `population_prior`, `taxonomy`),
  * declares its `read_scope` (`ROW_LEVEL` or `METADATA_ONLY`),
  * records its `schema_ref`, `path_template`, `partition_keys`, and `sha256_hex`.

* Emitting `s0_gate_receipt_6A`, which:

  * records which upstream segments’ HashGates have been verified,
  * records which 6A contracts and priors are in play,
  * binds them all under a single `sealed_inputs_digest_6A`.

All later 6A states must treat `sealed_inputs_6A` and `s0_gate_receipt_6A` as the **only binding description** of what they may read and how they must interpret authority:

* If an artefact is **absent** from `sealed_inputs_6A`, it is **out of bounds** for 6A.
* If an artefact is present with `read_scope = METADATA_ONLY`, 6A states may test for its existence, schema, and digest, but must **not** read its rows.
* Any attempt to expand 6A’s input universe beyond what S0 has sealed is a **spec violation**, not an implementation detail.

---

## 4. Outputs (gate receipt, sealed-input manifest & contracts) & identity *(Binding)*

6A.S0 produces two **control-plane datasets** and establishes the identity rules that bind 6A to a specific world and contract set:

1. A **gate receipt** for Layer-3 / Segment 6A.
2. A **sealed-input manifest** enumerating all artefacts 6A is authorised to depend on.

These outputs are **binding**: later 6A states (and 6B) must treat them as the authoritative description of 6A’s input universe and world identity.

---

### 4.1 `s0_gate_receipt_6A` — 6A gate receipt

**Role.** `s0_gate_receipt_6A` is the *single-row* summary, per `manifest_fingerprint`, of:

* which upstream segments were verified and with what status,
* which 6A contracts/priors are in scope,
* which `sealed_inputs_6A` digest defines the 6A input universe for this world.

It is the “header page” for all later 6A work.

**Scope & cardinality.**

* Exactly one logical row per `manifest_fingerprint` where 6A.S0 has **completed successfully**.
* Partitioned by `manifest_fingerprint={manifest_fingerprint}` (see §7 for full partition law).
* Updates are **idempotent**: rerunning S0 for the same `(parameter_hash, manifest_fingerprint)` must either:

  * reproduce a byte-identical row, or
  * fail with a conflict; silent mutation is not allowed.

**Minimum fields (logical, not schema syntax):**

* World & parameter identity:

  * `manifest_fingerprint`
  * `parameter_hash`
* Engine & spec identity:

  * `engine_version` / `spec_version_6A` (including S0 spec version)
  * optional `build_id` / `git_commit` for audit
* Upstream gate summary (map or structured fields):

  * For each required segment in `{1A,1B,2A,2B,3A,3B,5A,5B}`:

    * `segment_id` (e.g. `"1B"`, `"5B"`),
    * `gate_status ∈ {PASS, FAIL, MISSING}`,
    * `bundle_path` (catalogue-resolved, relative),
    * `bundle_digest_sha256` (for successfully verified bundles),
    * `flag_path` (for `_passed.flag`),
    * optional `flag_contents` echo (truncated or hashed).
* 6A contract summary:

  * `schemas_layer3_version`, `schemas_6A_version`,
  * `dictionary_6A_version`,
  * `registry_6A_version`,
  * optional digests for these artefacts.
* 6A priors/config summary:

  * identifiers and versions for each prior/config pack that will govern S1–S5 (population, segments, products, devices/IPs, fraud roles, taxonomies).
* Sealed inputs:

  * `sealed_inputs_digest_6A` — SHA-256 digest computed over `sealed_inputs_6A` using the law defined in §6,
  * `sealed_inputs_row_count` — number of rows in `sealed_inputs_6A` for this `manifest_fingerprint`.
* Audit:

  * `created_utc` — when this receipt was first written,
  * optional `verified_utc` — when it was last re-verified (if separate).

**Identity & usage.**

* **Key:** `(manifest_fingerprint)` — no secondary keys are needed at the logical level.
* All later 6A states **must**:

  * locate the single row for their `manifest_fingerprint`,
  * read and trust `sealed_inputs_digest_6A` as the binding fingerprint of their input universe,
  * treat `gate_status` for upstream segments as preconditions (e.g. 6A must not weaken “all upstream PASS” into “some upstream PASS”).
* 6B and downstream consumers **may** use `s0_gate_receipt_6A` (in conjunction with the 6A segment HashGate) as part of their own gating decisions, but **must not** reinterpret or override it.

---

### 4.2 `sealed_inputs_6A` — sealed-input manifest

**Role.** `sealed_inputs_6A` is the **row-level authority** on what 6A is allowed to read. Each row is one artefact (dataset, config pack, schema file, contract file) that:

* has been resolved via the catalogue,
* has a known schema reference and digest,
* has an explicit **role** and **read scope**.

All later 6A states must treat this table as the **closed world of permissible inputs**.

**Scope & cardinality.**

* One logical table per `manifest_fingerprint`.
* Partitioned by `manifest_fingerprint={manifest_fingerprint}`.
* Rows cover:

  * upstream egress 6A is allowed to touch in S1–S5,
  * 6A priors/config packs,
  * 6A schemas/dictionaries/registries (for consistency checking),
  * any Layer-3-wide taxonomies 6A depends on.

**Minimum fields per row:**

* Identity and provenance:

  * `manifest_fingerprint`
  * `owner_layer` (e.g. `1`, `2`, `3`)
  * `owner_segment` (e.g. `"1B"`, `"5A"`, `"6A"`)
  * `manifest_key` or `logical_id` (stable ID in the registry)
* Shape & location:

  * `schema_ref` — JSON-Schema anchor (e.g. `schemas.layer1.yaml#/egress/site_locations`)
  * `path_template` — canonical path with tokens (e.g. `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...`)
  * `partition_keys` — ordered list of partition tokens (e.g. `["seed", "fingerprint"]`)
* Role & scope:

  * `role` — closed enum, e.g.:

    * `UPSTREAM_EGRESS`
    * `SCENARIO_CONFIG`
    * `POPULATION_PRIOR`
    * `SEGMENT_PRIOR`
    * `PRODUCT_PRIOR`
    * `DEVICE_IP_PRIOR`
    * `FRAUD_ROLE_PRIOR`
    * `TAXONOMY`
    * `CONTRACT` (e.g. schema/dictionary/registry)

  * `status ∈ {REQUIRED, OPTIONAL, IGNORED}` — from 6A’s perspective.

  * `read_scope ∈ {ROW_LEVEL, METADATA_ONLY}` — whether S1–S5 may read data rows or only metadata (e.g. for upstream validation bundles).
* Integrity:

  * `sha256_hex` — content digest of the artefact (or of a canonical representation, if non-tabular).
  * optional `size_bytes`, `row_count_estimate` for diagnostics.
* Audit:

  * optional `discovered_from` (which registry/dictionary entry led to this artefact),
  * `created_utc` — when this row was written for this `manifest_fingerprint`.

**Identity & ordering.**

* Logical key per row is:

  * `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)`,

  which must be unique within `sealed_inputs_6A`.

* Rows must be written in a **canonical order** (e.g. sorted lexicographically by `(owner_layer, owner_segment, manifest_key, path_template)`), so that the digest derived in S0 is stable across re-runs.

**Usage.**

* Every later 6A state must:

  * load all rows for its `manifest_fingerprint`,
  * recompute `sealed_inputs_digest_6A` using the agreed law,
  * enforce:

    * *no reads* of artefacts that are **absent**,
    * *no row-level reads* of artefacts with `read_scope = METADATA_ONLY`.

* Any implementation that reads data outside `sealed_inputs_6A` or ignores `read_scope` is out-of-spec, even if it “works” in practice.

---

### 4.3 Relationship between outputs & identity

S0 binds 6A to a world in three ways:

1. **World identity:**
   `manifest_fingerprint` ties 6A to a specific world (upstream L1/L2 configurations and artefacts).

2. **Parameter identity:**
   `parameter_hash` (echoed in `s0_gate_receipt_6A` and, where appropriate, in `sealed_inputs_6A`) ties 6A to a specific configuration / prior pack set.

3. **Input-universe identity:**
   `sealed_inputs_digest_6A` (stored in the gate receipt, derived from the manifest) fixes **exactly which inputs** 6A is allowed to see for that world.

These three identities are binding for all of 6A:

* If any of `{manifest_fingerprint, parameter_hash, sealed_inputs_digest_6A}` changes, the entity & product world defined by S1–S5 is, by construction, a *different* world, even if some upstream artefacts are shared.
* 6A’s eventual segment HashGate (validation bundle + `_passed.flag`) will implicitly depend on all three; downstream consumers must treat any mismatch as a different world, not as a minor version.

No additional “hidden” identity (e.g. wall-clock, engine build) may influence the business semantics of S1–S5 beyond what is recorded in these outputs.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

All binding schema anchors, dataset IDs, partitioning rules, and manifest keys for this state's egress live in the Layer-3 / Segment 6A contracts:
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/dataset_dictionary.layer3.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/artefact_registry_6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/schemas.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/schemas.layer3.yaml`
This specification only summarises semantics so there is a single source of truth for catalogue details. Always consult the files above for precise schema refs, physical paths, partition keys, writer ordering, lifecycle flags, and dependency metadata.

### 5.1 Outputs owned by this state
- `s0_gate_receipt_6A` — Control-plane receipt recording upstream PASS statuses, run identity and the sealed input digest for each manifest.
- `sealed_inputs_6A` — Fingerprint-scoped inventory of every artefact 6A is authorised to read for that world, including digests and read scopes.

### 5.2 Catalogue & downstream obligations
Implementations and downstream consumers MUST resolve datasets via the dictionary/registry, honour the declared schema anchors, and treat any artefact not listed there as out of scope for this state.

## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section defines **exactly what 6A.S0 does**, in which order, and with which constraints. It is **purely deterministic** and **RNG-free**: given the same catalogue state and the same `manifest_fingerprint` / `parameter_hash`, it must always produce the same `s0_gate_receipt_6A` and `sealed_inputs_6A` (or fail with the same error).

S0 is structured as a small sequence of **phases**:

1. Discover world & contracts via the catalogue.
2. Verify upstream HashGates (1A–3B, 5A–5B).
3. Resolve Layer-3 / 6A contracts.
4. Resolve 6A priors & taxonomies.
5. Construct `sealed_inputs_6A`.
6. Compute `sealed_inputs_digest_6A`.
7. Emit / validate `s0_gate_receipt_6A` and `sealed_inputs_6A`.

No other behaviour is permitted.

---

### 6.1 Phase 0 — Inputs & identity (world selection)

**Goal:** Fix which world S0 is acting on and ensure identity is consistent.

1. **Select world identity.**

   * S0 receives `(parameter_hash, manifest_fingerprint)` as *sealed inputs* from the engine’s global control-plane.
   * S0 **must not** recompute or reinterpret these; they are taken as binding.

2. **Verify catalogue consistency.**

   * Using dataset dictionaries and artefact registries (Layer-1, Layer-2, Layer-3), S0 must confirm that:

     * `manifest_fingerprint` appears as a valid partition token wherever required (e.g. upstream validation paths, 6A outputs).
     * `parameter_hash` appears where 6A priors/config packs expect it (if parameter-scoped).

   * If the catalogue cannot resolve a unique candidate for any required artefact id, S0 must fail with a contract/catalogue error.

3. **No data reads.**

   * In Phase 0, S0 may only read **metadata**: schema files, dictionaries, registries.
   * It must not open any upstream egress datasets or priors yet.

---

### 6.2 Phase 1 — Verify upstream HashGates (Layer-1 & Layer-2)

**Goal:** Confirm that all required upstream segments are sealed and trusted for this `manifest_fingerprint`, using their own HashGate laws.

For each required segment in `{1A,1B,2A,2B,3A,3B,5A,5B}`:

1. **Locate validation bundle & flag.**

   * Use the dataset dictionary + artefact registry for that segment to resolve:

     * the validation bundle dataset (e.g. `validation_bundle_1B`) and its `path_template`, `partition_keys`, `schema_ref`;
     * the PASS flag dataset (e.g. `validation_passed_flag_1B` / `_passed.flag`) and its `path_template`, `schema_ref`.

   * S0 must construct physical paths **only** via these catalogue entries; hard-coded paths are disallowed.

2. **Read the segment’s validation index.**

   * Read that segment’s index artefact (e.g. `validation_bundle_index_*` or `index.json`) for the target `manifest_fingerprint`.
   * From the index, obtain:

     * the list of evidence file paths (relative to the bundle root),
     * the expected per-file SHA-256 digests.

3. **Recompute bundle digest according to the segment’s law.**

   * For each listed evidence file, in the **exact path order** specified by that segment:

     * read the raw bytes,
     * compute SHA-256,
     * compare with the digest in the index.

   * If any per-file digest mismatches, S0 must mark that segment as `FAIL`.

   * If the segment’s spec defines a **bundle digest** (e.g. `bundle_digest_sha256 = SHA256(concat(file_bytes_in_index_order))`), S0 must recompute it exactly and compare against:

     * the field in the index, **and**
     * the `_passed.flag` contents.

4. **Set gate status.**

   * If all checks pass for the segment: `gate_status = "PASS"`.
   * If the bundle or flag is missing or unresolved: `gate_status = "MISSING"`.
   * If any digest or structural check fails: `gate_status = "FAIL"`.

5. **Global requirement.**

   * 6A.S0’s own **segment status** is PASS only if **every required segment** has `gate_status = "PASS"`.
   * If any segment is `FAIL` or `MISSING`, S0 must:

     * record the status in its internal map,
     * **abort** before constructing `sealed_inputs_6A`, emitting an error code in the run-report.

S0 must not attempt to “repair” or reinterpret upstream HashGates; it either accepts them or refuses to proceed.

---

### 6.3 Phase 2 — Resolve Layer-3 / 6A contracts

**Goal:** Confirm that 6A’s own binding contracts are present and internally consistent.

1. **Schemas.**

   * Resolve `schemas.layer3.yaml` and `schemas.6A.yaml` via the catalogue.

   * Validate both against the schema-of-schemas (if present):

     * structural correctness,
     * no unknown top-level sections.

   * Confirm that all `schema_ref` entries in `dataset_dictionary.layer3.6A.yaml` resolve into either:

     * `schemas.layer3.yaml`, or
     * `schemas.6A.yaml`.

   * Confirm there are **no conflicting definitions** for the same `$id` / type name across the two schema files.

2. **Dataset dictionary.**

   * Resolve `dataset_dictionary.layer3.6A.yaml`.
   * Check that:

     * each `id` is unique,
     * each entry has a valid `schema_ref`, `path`, and `partitioning` field,
     * all `owner_layer` / `owner_segment` values for 6A entries match `3` / `"6A"` respectively.

3. **Artefact registry.**

   * Resolve `artefact_registry_6A.yaml`.
   * For each registry entry:

     * verify referenced `dataset_id` exists in the dictionary, if applicable,
     * verify `path_template` and `partition_keys` match the dictionary entry,
     * verify `schema_ref` matches the dictionary entry.

4. **Failure rule.**

   * If any of the above checks fail (missing schemas, unresolved refs, inconsistent paths), S0 must fail with a `6A.S0` contract error and **must not** proceed to priors or sealed inputs.

---

### 6.4 Phase 3 — Resolve 6A priors & taxonomy packs

**Goal:** Fix which prior/config artefacts govern 6A’s entity & product modelling for this world.

1. **Discover required priors/configs.**

   * From `artefact_registry_6A.yaml`, identify all entries tagged as 6A prior/config packs, e.g.:

     * population priors,
     * segmentation priors,
     * product mix priors,
     * device/IP priors,
     * fraud-role priors,
     * taxonomies.

2. **Resolve physical artefacts.**

   * For each such registry entry:

     * resolve its `path_template` and `partition_keys` (if any),
     * compute the concrete path(s) for this `manifest_fingerprint` / `parameter_hash` as specified by the registry,
     * confirm that exactly one physical artefact matches the registry expectations.

3. **Validate shape and digest.**

   * Check that each prior/config artefact:

     * is schema-valid with respect to its declared `schema_ref` (from `schemas.layer3.yaml` or `schemas.6A.yaml`),
     * has a SHA-256 digest that matches the digest recorded in the registry (if the registry carries digests).

4. **Summarise priors.**

   * Build an in-memory list of `prior_packs` with:

     * `prior_id`,
     * `prior_version`,
     * `prior_role`,
     * `sha256_hex`.

   * This list will later be embedded in `s0_gate_receipt_6A` and echoed in `sealed_inputs_6A`.

5. **Failure rule.**

   * If any required prior/config artefact is missing or invalid, S0 must fail with a `6A.S0.PRIOR_PACK_*` error and **must not** proceed.

---

### 6.5 Phase 4 — Construct `sealed_inputs_6A`

**Goal:** Enumerate all artefacts 6A S1–S5 are allowed to depend on, with roles, scopes, and digests.

1. **Assemble candidates.**

   * From the combination of:

     * upstream dictionaries/registries (1A–3B, 5A, 5B), and
     * 6A’s own registry,

   build a candidate list of artefacts that 6A may need, including:

   * Upstream egress (merchant/site/world/context surfaces):
     `outlet_catalogue`, `site_locations`, `site_timezones`, `tz_timetable_cache`, `zone_alloc`, `zone_alloc_universe_hash`, `virtual_classification_3B`, `virtual_settlement_3B`, `edge_universe_hash_3B`, `virtual_routing_policy_3B`, `merchant_zone_profile_5A`, `arrival_events_5B`, etc.

   * 6A contracts and priors:
     `schemas.layer3.yaml`, `schemas.6A.yaml`, `data_dictionary_6A`, `artefact_registry_6A`, all prior/config packs, taxonomies.

2. **Classify role and status.**

   For each candidate artefact:

   * Determine `role` (UPSTREAM_EGRESS, POPULATION_PRIOR, PRODUCT_PRIOR, etc.) according to a fixed 6A policy mapping from `owner_layer`, `owner_segment`, and registry tags.

   * Determine `status`:

     * `REQUIRED` if 6A S1–S5 cannot run without it,
     * `OPTIONAL` if 6A can branch behaviour when it is absent,
     * `IGNORED` if it is not intended to be used by 6A (these may be omitted entirely or explicitly recorded as such, but must not be read later).

   * Determine `read_scope`:

     * `ROW_LEVEL` for artefacts whose rows S1–S5 may read,
     * `METADATA_ONLY` for artefacts that are only used at metadata level (e.g. upstream validation bundles).

3. **Resolve shape & path metadata.**

   * For each artefact that is not `IGNORED`:

     * resolve `schema_ref` from its dataset dictionary or registry,
     * capture `path_template` and `partition_keys` from the dictionary/registry,
     * confirm that `partition_keys` includes `manifest_fingerprint` where appropriate.

4. **Compute digests.**

   * For each non-ignored artefact:

     * read its file(s) or canonical representation,
     * compute `sha256_hex` over the configured canonical form:

       * for tabular data: either the file as stored, or the segment’s defined digest law if one exists,
       * for JSON/YAML configs: a canonical byte representation (e.g. UTF-8 without BOM, with a defined serialisation).

   * This is deterministic: given the same artefact bytes, `sha256_hex` must be identical.

5. **Write in canonical order.**

   * Construct a row for each artefact with:

     * `manifest_fingerprint`,
     * `owner_layer`, `owner_segment`,
     * `manifest_key` (or `logical_id`),
     * `schema_ref`, `path_template`, `partition_keys`,
     * `role`, `status`, `read_scope`,
     * `sha256_hex`, optional `size_bytes`, `row_count_estimate`, `discovered_from`,
     * `created_utc`.

   * Sort rows by a fixed comparator, e.g.:

     ```text
     (owner_layer, owner_segment, manifest_key, path_template)
     ```

   * This sorted list is the in-memory representation of `sealed_inputs_6A` and is the basis for the digest in Phase 5.

---

### 6.6 Phase 5 — Compute `sealed_inputs_digest_6A`

**Goal:** Derive a single digest that uniquely represents the entire sealed input universe for this `manifest_fingerprint`.

1. **Canonical row serialisation.**

   * Serialise each row of `sealed_inputs_6A` into bytes using a **canonical, stable format**, e.g.:

     * JSON with:

       * fields in a fixed order,
       * no extra whitespace except a single newline per row,
       * UTF-8 encoding without BOM.

     * or another canonical row encoding defined for the engine.

   * The choice of encoding is binding and must be documented once; changing it is a breaking change.

2. **Concatenate row encodings.**

   * Concatenate the serialised row bytes **in the exact sorted row order** established in Phase 4.
   * No additional separators beyond those already in the row encodings.

3. **Compute digest.**

   * Compute:

     ```text
     sealed_inputs_digest_6A = SHA256(concatenated_row_bytes)
     ```

   * Represent this as a lowercase, 64-character hex string.

4. **Stability requirement.**

   * Given the same underlying artefacts and catalogue, re-running S0 must produce:

     * the same rows in the same order, and
     * the same `sealed_inputs_digest_6A`.

   * Any change in upstream artefacts, priors, or classification of roles will (correctly) produce a different digest.

---

### 6.7 Phase 6 — Emit / validate `s0_gate_receipt_6A` & `sealed_inputs_6A`

**Goal:** Persist S0’s outputs in a way that is idempotent and binding.

1. **Materialise `sealed_inputs_6A`.**

   * Write the sorted row set as a single logical dataset partition under:

     ```text
     data/layer3/6A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/...
     ```

   * Use the schema and path defined in `dataset_dictionary.layer3.6A.yaml`.

   * Enforce `columns_strict: true` and the PK/uniqueness constraint on `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)`.

2. **Materialise `s0_gate_receipt_6A`.**

   * Construct a single logical row containing:

     * `manifest_fingerprint`, `parameter_hash`,
     * upstream gate summary map (`upstream_gates`),
     * schema/dictionary/registry versions,
     * `prior_packs` summary,
     * `sealed_inputs_digest_6A`, `sealed_inputs_row_count`,
     * `created_utc` and any audit fields.

   * Write this under:

     ```text
     data/layer3/6A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt_6A.json
     ```

   * Again, use the schema and path defined in the dictionary/registry.

3. **Re-read and verify.**

   * Immediately re-read both persisted artefacts and:

     * recompute `sealed_inputs_digest_6A` from the stored `sealed_inputs_6A`,
     * compare with the value stored in `s0_gate_receipt_6A`.

   * If there is any mismatch, S0 must treat this as a hard error (`6A.S0.SEALED_INPUTS_DIGEST_MISMATCH`) and either:

     * roll back the outputs (if supported), or
     * leave them marked as invalid and **not** report PASS.

4. **Idempotency rule.**

   * If S0 is invoked again for the same `manifest_fingerprint` and the same upstream world:

     * It must either:

       * detect that existing `s0_gate_receipt_6A` and `sealed_inputs_6A` are **byte-identical** to what it would produce, and succeed without change, or
       * fail with an explicit “already initialised with different contents” error.

   * Silent overwrites with different content are **forbidden**.

---

### 6.8 RNG & side-effect constraints

* S0 **must not**:

  * use any RNG or time-dependent values for business semantics,
  * depend on wall-clock for anything other than `created_utc` audit columns, which are non-semantic.

* S0’s business outputs (`sealed_inputs_6A`, `s0_gate_receipt_6A`) must be fully determined by:

  * the catalogue state (schemas/dictionaries/registries),
  * the upstream validation bundles + flags,
  * the 6A prior/config artefacts,
  * the `(parameter_hash, manifest_fingerprint)` pair.

Any implementation that adds extra implicit inputs (e.g. environment variables, external calls, process IDs) is out of spec.

This deterministic algorithm is **binding**: Codex/implementers are free to choose *how* to implement each phase, but **not** free to change the order, omit phases, or introduce new observable behaviours beyond those described here.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S0’s outputs are identified, partitioned, ordered and merged**. Later 6A states (and 6B, and any orchestration) must treat these rules as binding. They are not implementation hints; they are part of the contract.

---

### 7.1 Identity axes

6A.S0 participates in the engine’s standard identity axes:

* **World identity**:

  * `manifest_fingerprint`
  * This is the primary identity for S0.
  * It pins 6A to a particular upstream world (L1/L2 configurations, bundles, and artefacts).

* **Parameter identity**:

  * `parameter_hash`
  * Echoed as a column in `s0_gate_receipt_6A` and, where appropriate, in `sealed_inputs_6A` rows (for parameter-scoped artefacts).
  * It does **not** appear as a partition key for S0 outputs.

* **Segment identity**:

  * `owner_layer = 3`, `owner_segment = "6A"`
  * Encoded in dataset dictionary, registry, and `sealed_inputs_6A`.

S0 **does not** have any notion of:

* per-seed identity,
* scenario identity,
* run identity (`run_id`),

at the dataset level. Those axes are relevant only for later 6A states and for upstream segments.

---

### 7.2 Partitioning & path tokens

Both S0 outputs are **fingerprint-scoped control-plane datasets**.

* `s0_gate_receipt_6A`:

  * Partition keys:

    * `[manifest_fingerprint]`
  * Path token:

    * `manifest_fingerprint={manifest_fingerprint}`
  * Path template (schematic):

    * `data/layer3/6A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt_6A.json`

* `sealed_inputs_6A`:

  * Partition keys:

    * `[manifest_fingerprint]`
  * Path token:

    * `manifest_fingerprint={manifest_fingerprint}`
  * Path template (schematic):

    * `data/layer3/6A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_6A.json`

Binding rules:

* `manifest_fingerprint` must appear **exactly once** in the partition path for each dataset and must match the `manifest_fingerprint` column inside the data.
* No additional partition keys (`seed`, `parameter_hash`, `scenario_id`) may be introduced for S0 outputs.
* Any consumer that needs S0 for a given world must locate it by:

  1. resolving the dataset via the dictionary/registry, then
  2. substituting `manifest_fingerprint={manifest_fingerprint}`.

---

### 7.3 Primary keys & uniqueness

**`s0_gate_receipt_6A`**

* Logical primary key:

  * `(manifest_fingerprint)`
* There must be **at most one** row per `manifest_fingerprint`.
* Re-running S0 for the same `manifest_fingerprint` must not produce a second, conflicting row; it must either:

  * detect that the existing row is byte-identical and treat the run as idempotent, or
  * fail with a “conflicting gate receipt” error.

**`sealed_inputs_6A`**

* Logical primary key per row:

  * `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)`
* This composite key must be **globally unique** within the `sealed_inputs_6A` dataset.

No other primary keys or uniqueness constraints may be assumed by consumers. If additional unique constraints are introduced (e.g. on `path_template` per manifest), they are **implementation details**, not part of this spec.

---

### 7.4 Ordering: semantic vs canonical

For S0 outputs, we distinguish:

* **Semantic order** — order that has business meaning.
* **Canonical order** — order used to compute digests and for deterministic writeout, but not meaningful to downstream logic.

Rules:

* `s0_gate_receipt_6A`:

  * Semantics: single-row dataset; row order is irrelevant.
  * Canonical form: a single JSON document or 1-row table; any ordering inside composite fields (e.g. `upstream_gates` keys) must be deterministically defined by its schema.

* `sealed_inputs_6A`:

  * Semantics: a set of rows; **no consumer may rely on row order** for business logic.
  * Canonical order:

    * S0 must write rows sorted by a fixed comparator, e.g.:
      `(owner_layer, owner_segment, manifest_key, path_template)`.
    * This order is used **only** for:

      * constructing `sealed_inputs_digest_6A`, and
      * deterministic write-out / re-read.

Downstream 6A states and 6B **must not** draw any business conclusions from physical row order in `sealed_inputs_6A`. They must treat it as an unordered set keyed by `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)`.

---

### 7.5 Merge discipline & lifecycle

S0 outputs are **write-once per world** and have strict merge discipline.

* **No cross-world merges.**

  * Each `manifest_fingerprint` has its own independent partition for `s0_gate_receipt_6A` and `sealed_inputs_6A`.
  * There is no concept of merging or aggregating S0 outputs across different `manifest_fingerprint`s.

* **No incremental appends.**

  * For a given `manifest_fingerprint`, `sealed_inputs_6A` is a *complete manifest* of all artefacts 6A may depend on.
  * S0 must not append more rows later for the same world; any change in the sealed inputs for a world implies a **new world** (i.e., a different `manifest_fingerprint`).

* **Idempotent retries.**

  * If S0 is re-run for the same `manifest_fingerprint` in the same catalogue state:

    * recomputing `sealed_inputs_6A` and `s0_gate_receipt_6A` must yield **byte-identical** artefacts, including the digest.
    * If not, the implementation is out-of-spec; the run must fail with a conflict rather than silently overwrite.

* **No partial updates.**

  * It is not permitted to update `s0_gate_receipt_6A` without updating `sealed_inputs_6A`, or vice versa.
  * S0’s successful completion must be observed as an **atomic pair**:

    * both artefacts exist,
    * their `sealed_inputs_digest_6A` relationship holds,
    * and both are consistent with the current catalogue state.

Orchestration MUST treat any deviation from this pairwise consistency as “S0 not successfully completed” for that world.

---

### 7.6 Consumption discipline

Any state or service that consumes 6A.S0 outputs must:

1. Resolve `s0_gate_receipt_6A` and `sealed_inputs_6A` for its `manifest_fingerprint` via the catalogue.

2. Confirm:

   * that there is exactly one `s0_gate_receipt_6A` row for that world,
   * that `sealed_inputs_6A` has no duplicate PKs,
   * that `sealed_inputs_digest_6A` recomputed from `sealed_inputs_6A` matches the value in the gate receipt.

3. Refuse to proceed if any of the above checks fails.

These identity, partition, ordering, and merge rules are **binding** for all 6A states and for 6B. Implementers are free to choose storage engines and IO libraries, but **not** free to alter these semantics.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 6A.S0 is considered PASS**, what invariants must hold on its outputs, and how **downstream states** are required to use (and enforce) those outputs.

If any condition in this section fails, S0 is **FAIL**, and **no later 6A state is allowed to run** for that `manifest_fingerprint`.

---

### 8.1 Segment-local PASS / FAIL definition

For a given `manifest_fingerprint`, 6A.S0 is **PASS** *iff* all of the following hold:

1. **Upstream HashGates:**

   * For every required upstream segment in `{1A,1B,2A,2B,3A,3B,5A,5B}`:

     * the validation bundle and `_passed.flag` are both present in the catalogue for this `manifest_fingerprint`,
     * the bundle digest recomputed by S0 **exactly** matches the digest recorded in that segment’s index,
     * the digest recorded in `_passed.flag` **exactly** matches the recomputed bundle digest.
   * In `s0_gate_receipt_6A.upstream_gates`, **every** `gate_status` is `"PASS"` (no `"FAIL"` or `"MISSING"` entries).

2. **Layer-3 / 6A contracts:**

   * `schemas.layer3.yaml` and `schemas.6A.yaml` both exist and are schema-valid.
   * Every `schema_ref` in `dataset_dictionary.layer3.6A.yaml` resolves to a definition in one of those schema files.
   * `artefact_registry_6A.yaml` is present and consistent with the dictionary (matching `dataset_id`, `path_template`, `partition_keys`, `schema_ref`).
   * There are **no** conflicting schema definitions or catalogue entries for any 6A dataset ID.

3. **6A priors & taxonomies:**

   * Every 6A prior/config artefact marked **required** in the registry:

     * exists in the catalogue,
     * is schema-valid,
     * has a SHA-256 digest that matches the digest recorded in the registry (if a digest is recorded).
   * `s0_gate_receipt_6A.prior_packs` correctly summarises the IDs, versions, and roles of all such required priors.

4. **`sealed_inputs_6A` contents:**

   * For this `manifest_fingerprint`, there exists exactly **one** logical partition of `sealed_inputs_6A`:

     * all rows share the same `manifest_fingerprint`,
     * the composite key `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)` is unique.

   * Every artefact row:

     * references a real artefact discoverable via the catalogue,
     * has a `schema_ref` that resolves to a known schema,
     * has a `role` and `read_scope` consistent with 6A’s classification policy,
     * has a `sha256_hex` that matches the SHA-256 of the underlying artefact bytes (or its canonical representation).

5. **Digest binding:**

   * When `sealed_inputs_6A` for this `manifest_fingerprint` is sorted according to the canonical comparator and serialised using the canonical row encoding, the computed digest:

     ```text
     SHA256(concatenated_row_bytes) == s0_gate_receipt_6A.sealed_inputs_digest_6A
     ```

   * `s0_gate_receipt_6A.sealed_inputs_row_count` matches the actual row count in `sealed_inputs_6A`.

6. **Idempotency & uniqueness:**

   * There is exactly one `s0_gate_receipt_6A` row for this `manifest_fingerprint`.
   * If S0 is re-run in an unchanged catalogue for the same `(parameter_hash, manifest_fingerprint)`, the newly computed `sealed_inputs_6A` and `s0_gate_receipt_6A` are **byte-identical** to the persisted artefacts.

If **any** of the above conditions is not met, S0 is **FAIL** for that `manifest_fingerprint`, and its outputs must **not** be treated as authoritative.

---

### 8.2 Output-level invariants for a PASS run

When S0 is PASS for a given `manifest_fingerprint`, the following invariants become **obligations** for all consumers:

1. **Closed-world input set:**

   * The input universe for 6A is exactly the set of artefacts listed as non-`IGNORED` in `sealed_inputs_6A` for that `manifest_fingerprint`.
   * No later 6A state may read any artefact **not** present in `sealed_inputs_6A`.

2. **Read-scope enforcement:**

   * For any artefact with `read_scope = "METADATA_ONLY"`, later 6A states:

     * **must not** read its data rows,
     * may only rely on its existence, schema, and digest.

   * For any artefact with `read_scope = "ROW_LEVEL"`, row-level reads are permitted, but only under the binding schema and path defined in the catalogue.

3. **Role consistency:**

   * The `role` field in `sealed_inputs_6A` is binding:

     * artefacts marked as e.g. `POPULATION_PRIOR` must be used only as priors for entity counts,
     * artefacts marked as `UPSTREAM_EGRESS` must not be treated as overrideable configs.

   * Any implementation that reinterprets a role (e.g. treats a prior as an egress override) is out-of-spec.

4. **Upstream gate inheritance:**

   * The `upstream_gates` map in `s0_gate_receipt_6A` is the **binding view** of upstream status for 6A:

     * if a segment is not listed there, it is **not** considered part of 6A’s trusted upstream,
     * if it is listed with `gate_status = "PASS"`, 6A may assume its egress and contracts are correctly sealed,
     * no 6A state may “downgrade” or reinterpret these statuses.

---

### 8.3 Gating obligations for downstream 6A states (S1–S5)

Every downstream 6A state (S1, S2, S3, S4, S5) must treat S0 as a **hard precondition**:

Before doing any work for a given `manifest_fingerprint`, each state **MUST**:

1. Resolve and read `s0_gate_receipt_6A` and `sealed_inputs_6A` for that `manifest_fingerprint`.
2. Recompute `sealed_inputs_digest_6A` from the stored `sealed_inputs_6A` (using the canonical encoding and order) and verify it matches the value in `s0_gate_receipt_6A`.
3. Confirm that every required upstream segment in `upstream_gates` has `gate_status = "PASS"`.

If **any** of these checks fails, the state **must not**:

* read any upstream artefacts for that world,
* write any 6A artefacts for that world,

and must instead **fail fast** with a state-local “S0 gate failed” error (which should be traceable back to the root 6A.S0 failure).

Additionally, every 6A state:

* **MUST** restrict its reads to artefacts present in `sealed_inputs_6A`.
* **MUST NOT** read row-level data from any artefact whose `read_scope` is `METADATA_ONLY`.

These obligations are part of the 6A design, not an implementation detail — an implementation that violates them is not a valid 6A implementation.

---

### 8.4 Gating obligations for 6B and other downstream consumers

6B and any other consumer that reads 6A entity/graph artefacts must treat S0 as part of the 6A trust chain:

* 6B.S0 (or equivalent gate state) **MUST**:

  1. verify that a `s0_gate_receipt_6A` exists for the relevant `manifest_fingerprint`,
  2. recompute and verify `sealed_inputs_digest_6A`,
  3. ensure that all required 6A priors/configs (as summarised in `prior_packs`) are present in `sealed_inputs_6A`,
  4. treat any S0 failure as a hard precondition failure for 6B.

* Once 6A has its own segment-level HashGate (validation bundle + `_passed.flag`):

  * 6B must require **both**:

    * a valid 6A HashGate, and
    * a valid S0 gate receipt and sealed-inputs digest,

    before it may read any 6A outputs.

---

### 8.5 Behaviour on failure & partial outputs

If S0 fails any acceptance criterion for a given `manifest_fingerprint`:

* Any partially written `sealed_inputs_6A` or `s0_gate_receipt_6A` **must not** be treated as valid:

  * downstream states must treat the world as “S0 not complete”,
  * orchestration must either roll back or mark these artefacts as invalid / quarantined.

* S0’s run-report entry **must** have:

  * `status = "FAIL"`,
  * a non-empty `error_code` in the `6A.S0.*` namespace,
  * a human-readable `error_message` explaining the failure category (e.g. “upstream gate missing”, “sealed_inputs digest mismatch”).

Under no circumstances may 6A or 6B “best-effort” their way past an S0 failure. The only valid behaviours are:

* **S0 PASS →** later 6A states may run,
* **S0 FAIL →** later 6A states must not run for that `manifest_fingerprint`.

These acceptance criteria and gating obligations are **binding** and form part of the 6A.S0 specification that Codex/implementers must honour.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section fixes the **canonical error surface** for 6A.S0.
Every failure must be mapped to **exactly one** of these codes, and any state / orchestration looking at 6A.S0’s run-report must be able to reason about the cause from the code alone.

All codes in this section are:

* **Fatal** for 6A.S0 for that `manifest_fingerprint`.
* **Blocking** for all later 6A states (S1–S5).
* **Blocking** for 6B whenever it attempts to consume 6A outputs for that world.

No “best-effort” downgrade or silent fallback is permitted.

---

### 9.1 Error class overview

We group failures into six classes:

1. **Upstream gate / HashGate errors** — problems verifying 1A–3B or 5A–5B.
2. **Layer-3 / 6A contract errors** — schema / dictionary / registry issues.
3. **Prior & taxonomy errors** — missing or invalid 6A priors/configs.
4. **Sealed-input manifest errors** — construction or digest issues for `sealed_inputs_6A`.
5. **Identity & idempotency errors** — conflicts with existing S0 outputs.
6. **IO / unexpected internal errors** — storage or generic runtime failures.

Each class has a small, closed set of codes under the `6A.S0.*` namespace.

---

### 9.2 Canonical error codes

#### 9.2.1 Upstream gate / HashGate errors

These indicate something is wrong with **Layer-1 / Layer-2 gates** from 6A’s point of view.

* `6A.S0.UPSTREAM_HASHGATE_MISSING`

  *Meaning:* One or more required upstream segments `{1A,1B,2A,2B,3A,3B,5A,5B}` have no discoverable validation bundle or PASS flag for this `manifest_fingerprint`.

* `6A.S0.UPSTREAM_HASHGATE_DIGEST_MISMATCH`

  *Meaning:* A validation bundle was found, but recomputed digests do not match either the segment’s index or the `_passed.flag` contents.

* `6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID`

  *Meaning:* An upstream validation bundle or index fails its own schema check (e.g. malformed `index.json`).

All of these mean: **“world is not sealed upstream; 6A must not run”**.

---

#### 9.2.2 Layer-3 / 6A contract errors

These indicate that **6A’s own contracts cannot be trusted**.

* `6A.S0.L3_SCHEMA_MISSING_OR_INVALID`

  *Meaning:* `schemas.layer3.yaml` or `schemas.6A.yaml` is missing, malformed, or fails JSON-Schema validation.

* `6A.S0.DICTIONARY_OR_REGISTRY_INCONSISTENT`

  *Meaning:* `dataset_dictionary.layer3.6A.yaml` and `artefact_registry_6A.yaml` disagree about dataset IDs, schema refs, paths, or partitioning.

* `6A.S0.SCHEMA_REF_UNRESOLVED`

  *Meaning:* At least one `schema_ref` in the 6A dictionary cannot be resolved to any known schema definition.

These errors mean: **“6A’s binding contract is broken; no entity world can be defined safely.”**

---

#### 9.2.3 Prior & taxonomy errors

These indicate problems with **6A prior/config packs**.

* `6A.S0.PRIOR_PACK_MISSING`

  *Meaning:* A prior/config artefact marked as `REQUIRED` in `artefact_registry_6A.yaml` cannot be resolved for this `manifest_fingerprint` / `parameter_hash`.

* `6A.S0.PRIOR_PACK_SCHEMA_INVALID`

  *Meaning:* A located prior/config artefact fails validation against its declared `schema_ref`.

* `6A.S0.PRIOR_PACK_DIGEST_MISMATCH`

  *Meaning:* The SHA-256 of a prior/config artefact does not match the digest recorded in the registry (where such a digest is specified).

These mean: **“6A cannot guarantee which priors govern entity generation; it must not proceed.”**

---

#### 9.2.4 Sealed-input manifest errors

These indicate that **`sealed_inputs_6A` is incomplete, inconsistent or non-deterministic**.

* `6A.S0.SEALED_INPUTS_EMPTY`

  *Meaning:* For this `manifest_fingerprint`, S0 would produce an empty `sealed_inputs_6A` (no authorised inputs). This is considered a configuration error, not a legitimate world.

* `6A.S0.SEALED_INPUTS_ROW_CONFLICT`

  *Meaning:* Duplicate or conflicting rows under the logical key `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)` are detected when constructing or validating `sealed_inputs_6A`.

* `6A.S0.SEALED_INPUTS_DIGEST_MISMATCH`

  *Meaning:* After writing `sealed_inputs_6A`, recomputing its canonical digest does not match `s0_gate_receipt_6A.sealed_inputs_digest_6A`, or there is an inconsistency between in-memory and persisted digests.

* `6A.S0.SEALED_INPUTS_ARTIFACT_UNRESOLVED`

  *Meaning:* A candidate artefact 6A attempted to include cannot be resolved via the catalogue (e.g. missing dataset dictionary entry or registry entry) even though the 6A classification says it should exist.

These mean: **“S0 cannot reliably seal the input universe; its gate receipt cannot be trusted.”**

---

#### 9.2.5 Identity & idempotency errors

These indicate that **S0’s outputs conflict with existing state** for the same world.

* `6A.S0.GATE_RECEIPT_CONFLICT`

  *Meaning:* An existing `s0_gate_receipt_6A` for this `manifest_fingerprint` exists and is *not* byte-identical to what S0 would emit given the current catalogue.

* `6A.S0.SEALED_INPUTS_CONFLICT`

  *Meaning:* An existing `sealed_inputs_6A` for this `manifest_fingerprint` exists and is *not* byte-identical to what S0 would emit, or violates PK / uniqueness constraints.

These mean: **“the world has already been initialised differently; the current attempted run is not allowed to mutate it.”**

---

#### 9.2.6 IO / unexpected internal errors

These indicate infrastructure or generic runtime failures.

* `6A.S0.IO_READ_FAILED`

  *Meaning:* S0 could not read a required schema, dictionary, registry, bundle, or artefact due to IO problems (permissions, network, corruption), despite the catalogue claiming it exists.

* `6A.S0.IO_WRITE_FAILED`

  *Meaning:* S0 attempted to write `s0_gate_receipt_6A` or `sealed_inputs_6A` and the write failed (or could not be made durable/atomic).

* `6A.S0.INTERNAL_ERROR`

  *Meaning:* A non-recoverable, unexpected error occurred in S0 that does not fall cleanly into any of the categories above (e.g. assertion failure, unhandled exception). This should be rare and treated as a bug in the implementation, not a normal operational state.

All IO / internal errors are **fatal** for S0. Operator action is to investigate & remediate infrastructure or implementation, not to try to continue 6A.

---

### 9.3 Mapping detection → error code

This spec requires **one obvious code** per failure type:

* Upstream bundle/flag missing → `6A.S0.UPSTREAM_HASHGATE_MISSING`.
* Bundle found but digest mismatch → `6A.S0.UPSTREAM_HASHGATE_DIGEST_MISMATCH`.
* Schema file missing or invalid → `6A.S0.L3_SCHEMA_MISSING_OR_INVALID`.
* Dictionary vs registry mismatch → `6A.S0.DICTIONARY_OR_REGISTRY_INCONSISTENT`.
* Required prior not found → `6A.S0.PRIOR_PACK_MISSING`.
* Required prior fails schema → `6A.S0.PRIOR_PACK_SCHEMA_INVALID`.
* Prior digest mismatch → `6A.S0.PRIOR_PACK_DIGEST_MISMATCH`.
* `sealed_inputs_6A` would be empty → `6A.S0.SEALED_INPUTS_EMPTY`.
* Duplicate `(mf, owner_layer, owner_segment, manifest_key)` → `6A.S0.SEALED_INPUTS_ROW_CONFLICT`.
* Digest check fails on persisted rows → `6A.S0.SEALED_INPUTS_DIGEST_MISMATCH`.
* Cannot resolve a referenced artefact → `6A.S0.SEALED_INPUTS_ARTIFACT_UNRESOLVED`.
* Conflict with existing gate receipt → `6A.S0.GATE_RECEIPT_CONFLICT`.
* Conflict with existing sealed inputs → `6A.S0.SEALED_INPUTS_CONFLICT`.
* IO read issue → `6A.S0.IO_READ_FAILED`.
* IO write issue → `6A.S0.IO_WRITE_FAILED`.
* Anything else → `6A.S0.INTERNAL_ERROR`.

Implementations **must not invent additional codes** silently. If new codes are needed in future, they must be added to this spec and versioned via the S0 spec version.

---

### 9.4 Run-report & propagation requirements

On any **FAIL**, 6A.S0 must:

* Emit a run-report record for this `manifest_fingerprint` with:

  * `state_id: "6A.S0"`,
  * `status: "FAIL"`,
  * `error_code: "<one of the codes above>"`,
  * `error_message`: short, human-oriented description (not free-form stack trace).

* Ensure that:

  * downstream 6A states,
  * 6B, and
  * any orchestration layer

can see that S0 failed for this world by inspecting that run-report and/or by the absence of a valid `s0_gate_receipt_6A` / `sealed_inputs_6A` pair.

No downstream state may “mask” or override the 6A.S0 `error_code`.

---

### 9.5 Non-goals

The error codes defined here:

* **Do not** expose implementation details (file paths, stack traces, IO backends). Those belong in logs, not in the contract.
* **Do not** attempt to encode operator advice beyond the class of failure; operational runbooks may expand on them, but the codes themselves are stable, machine-readable signals.

Any 6A implementation must map its internal failure conditions onto these canonical codes. If it cannot do so, that failure should be reported as `6A.S0.INTERNAL_ERROR` until the spec is extended.

---

## 10. Observability & run-report integration *(Binding)*

6A.S0 is part of the engine’s **control plane**, so its observability surface is binding.
Every execution for a given `manifest_fingerprint` **MUST** emit a run-report record and **MUST NOT** rely on external logging for correctness.

This section fixes **what gets reported**, **how it’s keyed**, and **how downstream states and operators are expected to use it**.

---

### 10.1 Run-report record for 6A.S0

For each attempted S0 run against a `manifest_fingerprint`, the engine **MUST** emit exactly one run-report record with at least:

* **Identity fields**

  * `state_id = "6A.S0"`
  * `manifest_fingerprint`
  * `parameter_hash`
  * `engine_version`
  * `spec_version_6A` (includes S0 spec version)

* **Execution envelope**

  * `run_id` (control-plane run identifier; non-semantic)
  * `started_utc` (RFC 3339 with micros)
  * `completed_utc` (RFC 3339 with micros)
  * `duration_ms` (integer; derived)

* **Status & error**

  * `status ∈ { "PASS", "FAIL" }`
  * `error_code` (one of the canonical codes from §9 for `status="FAIL"`, empty for PASS)
  * `error_message` (short human-readable description; non-normative)

* **Core S0 outputs**

  * `sealed_inputs_digest_6A`

  * `sealed_inputs_row_count`

  * `upstream_gates_summary` — a compact form of:

    * total required segments,
    * number with `PASS`, `FAIL`, `MISSING`.

  * `prior_packs_summary` — counts of priors per `prior_role` (e.g. how many `POPULATION_PRIOR`, `PRODUCT_PRIOR`, etc.).

The run-report record is **authoritative** for S0’s status; downstream components **MUST NOT** infer S0 success/failure solely from the presence of files on disk.

---

### 10.2 Metrics & counters (binding semantics, not SLOs)

S0 **MUST** report the following metrics for the target `manifest_fingerprint`:

* **Upstream gate metrics**

  * `upstream_segments_required` — count of required segments (normally 8).
  * `upstream_segments_pass` — count of segments with `gate_status="PASS"`.
  * `upstream_segments_fail` — count of segments with `gate_status="FAIL"`.
  * `upstream_segments_missing` — count of segments with `gate_status="MISSING"`.

* **Sealed-inputs metrics**

  * `sealed_inputs_row_count` — as above (also copied into `s0_gate_receipt_6A`).
  * `sealed_inputs_by_role` — map from `role` → count.
  * `sealed_inputs_by_status` — counts for `{REQUIRED, OPTIONAL, IGNORED}`.
  * `sealed_inputs_by_read_scope` — counts for `{ROW_LEVEL, METADATA_ONLY}`.

* **Prior/config metrics**

  * `prior_packs_required` — number of required priors/config packs.
  * `prior_packs_resolved` — number successfully resolved and validated.
  * `prior_packs_missing` — number missing (if any).

These metrics are **non-gating** by themselves (gating is defined in §8), but they are **binding** in that:

* a consumer must be able to reconstruct, from the run-report, **how many** artefacts of each type S0 sealed, and
* operators must be able to distinguish “no priors” vs “few priors” vs “many priors” runs.

---

### 10.3 Relationship between run-report and S0 outputs

The run-report for 6A.S0 and the datasets `s0_gate_receipt_6A` / `sealed_inputs_6A` are linked as follows:

* For a **PASS** run:

  * the run-report’s `sealed_inputs_digest_6A` and `sealed_inputs_row_count` **MUST** match the values in the corresponding `s0_gate_receipt_6A` row, and
  * recomputing the digest from `sealed_inputs_6A` **MUST** match both.

* For a **FAIL** run:

  * S0 may have written partial artefacts, but they are **not authoritative**;
  * the run-report’s `status="FAIL"` and `error_code` take precedence over any partial outputs.

Any orchestration that infers S0 success purely from the presence of `s0_gate_receipt_6A` or `sealed_inputs_6A` without checking the run-report and digest is out of spec.

---

### 10.4 Downstream consumption obligations

All downstream states that rely on S0 — i.e.:

* 6A.S1–S5, and
* 6B.S0 (or equivalent 6B gate) —

**MUST** integrate the run-report as part of their own gating:

Before proceeding for a given `manifest_fingerprint`, they must:

1. Verify that there exists at least one 6A.S0 run-report record for that world.

2. Select the **latest** S0 run-report (by `completed_utc`) for that world.

3. Check:

   * `status == "PASS"`, and
   * `error_code` is empty or null.

4. Confirm that `sealed_inputs_digest_6A` in the run-report matches:

   * the value in `s0_gate_receipt_6A`, and
   * the digest computed from `sealed_inputs_6A`.

If any of these steps fails, downstream states **MUST NOT** treat S0 as complete and must fail their own gate with a “S0 not in PASS state” error.

---

### 10.5 Logging and tracing (non-semantic but required presence)

S0 is RNG-free and relatively small, but implementations **MUST**:

* log, at INFO level or equivalent, a short summary per run containing:

  * `manifest_fingerprint`, `parameter_hash`,
  * final `status`, `error_code`,
  * high-level metrics (rows in `sealed_inputs_6A`, upstream segments PASS/FAIL/MISSING counts).

* log, at DEBUG level, enough detail to reconstruct:

  * which upstream segments failed HashGate verification, if any,
  * which priors/configs were missing or invalid, if any,
  * which artefact (by `manifest_key`) caused sealed-inputs or digest failures.

These logs are **not part of the formal contract** (they may change format over time), but they are **required** for operational debugging; absence of such logs is considered an implementation deficiency.

---

### 10.6 Integration with higher-level health & dashboards

The engine’s higher-level monitoring **MUST** be able to aggregate 6A.S0 status per world. At minimum:

* A dashboard or summary view **MUST** be able to show, per `manifest_fingerprint`:

  * S0 status (`PASS` / `FAIL` / `MISSING`),
  * time of last PASS run,
  * error code and time of last FAIL (if any),
  * counts of upstream segments PASS/FAIL/MISSING,
  * `sealed_inputs_row_count`.

* Alerting **SHOULD** be configured such that:

  * any `6A.S0` failure in a production-like environment raises a signal for operators, and
  * persistent absence of S0 PASS for worlds that have upstream PASS segments is visible (e.g. “world sealed upstream but 6A.S0 not run / not passing”).

These observability requirements ensure that S0’s gate status is:

* **visible** to operators,
* **machine-readable** to downstream states and orchestration, and
* **traceable** back to specific upstream or configuration issues without ad-hoc investigation.

---

## 11. Performance & scalability *(Informative)*

6A.S0 is **control-plane and metadata-heavy** rather than data-heavy. It reads schemas, dictionaries, registries, validation indexes, and a relatively small number of prior/config packs, plus digests a bounded set of upstream bundles. It should be *cheap* compared with entity generation (S1–S4) and any later transaction synthesis.

This section is non-binding; it describes the expected performance envelope and design considerations, not normative behaviour.

---

### 11.1 Complexity profile

At a high level, S0’s work for a single `manifest_fingerprint` scales with:

* the **number of upstream segments** to verify (fixed at 8: 1A,1B,2A,2B,3A,3B,5A,5B),
* the **size and number of files in each validation bundle**,
* the **number of 6A priors/config packs**, and
* the **number of artefacts** that end up in `sealed_inputs_6A`.

Rough complexity:

* **Catalogue lookups**: O(number of segments + number of 6A datasets/priors) — small, bounded.
* **Bundle verification**: O(total bytes in all upstream validation bundles) — typically modest compared to data-plane volumes.
* **Sealed-input manifest**:

  * row count ≈ number of selected upstream egress artefacts + 6A contracts + priors/taxonomies;
  * digest computation is O(number of rows × size of row encoding), usually negligible.

In practice, S0 should be orders of magnitude cheaper than any state that scans `arrival_events_5B` or large entity tables.

---

### 11.2 Expected sizes & growth

Typical scaling expectations:

* **Upstream bundles**:

  * each segment’s validation bundle contains a handful to a few dozen small JSON/metadata artefacts; even with growth over time, total size remains in the MB–low-GB range.

* **`sealed_inputs_6A` rows**:

  * **O(10–100s)** for a minimal engine (few upstream artefacts + a small number of priors),
  * **O(100–1,000s)** for richer deployments with multiple prior packs, taxonomies, and optional surfaces,
  * unlikely to need to grow to O(10⁵) rows unless 6A is made unusually fine-grained.

* **Per-world overhead**:

  * verifying eight HashGates and digesting a few dozen artefacts is small compared to data-plane jobs and is typically amortised across many downstream states.

As more upstream segments or 6A priors are added, the dominant cost will remain I/O for bundle files and prior packs, not the in-memory processing of `sealed_inputs_6A`.

---

### 11.3 Parallelism and concurrency

S0 is naturally parallelisable across two dimensions:

1. **Across upstream segments** (within a world):

   * HashGate checks for 1A,1B,2A,2B,3A,3B,5A,5B can be done in parallel, as they are independent;
   * digest computations for different bundles can be pipelined or distributed;
   * construction of the `upstream_gates` map is a small, final aggregation step.

2. **Across worlds** (across `manifest_fingerprint`s):

   * S0 runs for different worlds are hermetic and can be sharded across workers,
   * the only shared resources are schemas/dictionaries/registries, which are small and cacheable.

Implementations **should** exploit at least per-segment parallelism for bundle verification where this materially improves latency. However, parallelism must not compromise determinism:

* bundle digests must be independent of task scheduling, and
* `sealed_inputs_6A` row ordering must still follow the canonical comparator.

---

### 11.4 Caching and reuse opportunities

Because S0 is digest-heavy, there are natural opportunities for caching, as long as correctness is preserved:

* **Schema & catalogue caching**:

  * parsed versions of `schemas.layer1/2/3`, `schemas.6A`, dictionaries, and registries can be cached across runs and worlds;
  * invalidation is tied to schema/dictionary/registry version changes.

* **Bundle digest caching**:

  * if an upstream segment’s validation bundle is byte-identical across multiple worlds (e.g. same `manifest_fingerprint` reused in different environments), its per-file and bundle digests can be cached and reused;
  * care must be taken to ensure that the cache key includes both the physical path and a strong identifier (e.g. last-modified + size + prior digest) to avoid stale results.

* **Prior pack caching**:

  * large prior/config packs that are parameter-scoped rather than world-scoped can be digested once per `parameter_hash` and reused across all worlds with that parameter pack.

These caching strategies do not change semantics; they should only affect runtime cost.

---

### 11.5 Resource usage and limits

Given its nature, S0’s resource footprint is expected to be:

* **CPU**: light to moderate — mainly used for SHA-256 and parsing JSON/YAML.

* **Memory**: small — it holds only:

  * metadata structures (schemas, dictionaries, registries, validation indices),
  * one in-memory view of `sealed_inputs_6A` for a single world.

* **I/O**: moderate — dominated by reading:

  * upstream validation bundles,
  * 6A priors/config packs,
  * writing the small S0 outputs.

Reasonable design targets (non-binding):

* S0 should be comfortably runnable on a single core for a typical world,
* memory usage should remain well below that of any large data-plane state,
* there should be no need to page or stream `sealed_inputs_6A` beyond straightforward read/write.

---

### 11.6 Behaviour under large-scale deployments

In deployments with many worlds / manifests, or with rich prior packs, S0 should still behave predictably:

* **Many worlds**:

  * orchestrators can throttle S0 concurrency to bound load on shared stores (e.g. object storage, config repo);
  * worlds with identical upstream PASSED bundles and identical priors will share much of the computation via cache.

* **Rich priors / large bundles**:

  * if prior packs become large (e.g. region-level priors with many dimensions), S0’s digest work may become noticeable but remains bounded by the size of those packs;
  * this cost remains minor compared to entity-generation, and can be mitigated by per-prior hashing and caching as described above.

Critically, S0’s cost is **sub-linear** in the size of data-plane artefacts like `arrival_events_5B` or downstream transaction logs, because it never scans them.

---

### 11.7 Operational guidance

While not binding, the following guidelines are recommended:

* Treat 6A.S0 as a **fast, early gate** in the Layer-3 pipeline:

  * run it soon after a world’s upstream HashGates (1A–3B, 5A–5B) are confirmed PASS,
  * fail early if priors/configs are miswired, before costly entity-generation work is kicked off.

* Consider running S0:

  * once per world,
  * once per major change in 6A priors/contracts,
  * as part of any CI path that introduces new 6A configs or schemas.

* Use S0’s run-report metrics (counts of priors, roles, upstream gate statuses) as a quick health signal for the Layer-3 environment before debugging deeper issues in S1–S5.

These performance and scalability notes are **informative** and do not change the binding semantics of S0, but they should help shape an implementation that is efficient, predictable, and easy to operate at scale.

---

## 12. Change control & compatibility *(Binding)*

This section fixes **how S0 is allowed to evolve** and how those changes interact with:

* upstream segments (1A–3B, 5A–5B),
* downstream 6A states (S1–S5),
* 6B and any external consumers that rely on 6A’s gate.

It is **binding**: any change that violates these rules is a **spec violation**, even if an implementation “appears to work”.

---

### 12.1 Versioning model

S0 participates in a layered versioning scheme:

* `spec_version_6A` — version of the **overall 6A segment spec**, including S0–S5.
* `spec_version_6A_S0` (implicit or explicit) — version of the **S0 section** of this spec.
* Dataset schema versions — versioning of `schemas.layer3.yaml#/gate/6A/s0_gate_receipt_6A` and `#/gate/6A/sealed_inputs_6A`.
* Registry/dictionary versions — version for `dataset_dictionary.layer3.6A.yaml` and `artefact_registry_6A.yaml`.

All of these (or a subset) **must** be recorded in `s0_gate_receipt_6A` so downstream code can reason about compatibility.

S0 changes are categorised as:

* **Backwards compatible** — older consumers can still read and understand S0 outputs.
* **Forwards compatible** — new consumers can still work against older S0 outputs.
* **Breaking** — require explicit coordination between producers and consumers.

---

### 12.2 Allowed backwards-compatible changes

The following changes are **backwards compatible** *provided they respect all other sections of this spec*:

1. **Add optional fields** to S0 datasets:

   * Adding new, optional fields to `s0_gate_receipt_6A` or `sealed_inputs_6A` schemas (with sensible defaults) that:

     * do not change the meaning of existing fields,
     * are allowed to be ignored by older consumers.

2. **Add new `role` values**:

   * Extending the `role` enum in `sealed_inputs_6A` with new values, as long as:

     * existing roles retain their meaning,
     * new roles default to safe behaviour for older consumers (e.g. they treat unknown roles as “do not use” until upgraded).

3. **Add new upstream segments** (future layers) as **optional** entries in `upstream_gates`:

   * New upstream segments may be added as additional keys in the `upstream_gates` map, provided:

     * absence of the new segment is treated as “not relevant” by older code,
     * the semantics of existing segments are unchanged.

4. **Refine priors/config classification**:

   * Introducing new `prior_role` values or finer classification of 6A prior packs, as long as:

     * existing priors remain present and keep their meaning,
     * existing consumers can continue to treat them as generic priors.

5. **Non-semantic performance changes**:

   * Any change that purely optimises S0’s internal execution (caching, parallelism, I/O patterns) without changing:

     * the observable contents of `s0_gate_receipt_6A` and `sealed_inputs_6A`, or
     * the error codes/status behaviour,

   is backwards compatible.

Backwards-compatible changes may increment minor or patch components of `spec_version_6A` / S0’s subversion.

---

### 12.3 Changes that require coordination (soft breaks)

The following changes are **not strictly breaking**, but require coordination between producers and consumers and must be accompanied by a **spec version bump** and explicit compatibility code:

1. **New required upstream segments**:

   * Adding a new segment to the required set for S0 (e.g. a future “Layer-1 / 4A” or “Layer-2 / 6C”) is only allowed if:

     * S0 treats it as **optional** for a transitional period (e.g. `gate_status` may be `MISSING` and still allow PASS), and
     * downstream 6A/6B code that *depends* on that segment checks for its presence explicitly, rather than assuming it.

   * Once all environments are upgraded, the segment can shift from “optional” to “required” with a **major** S0 spec version bump.

2. **New required priors/configs**:

   * Adding new prior/config types that S0 insists on (status=`REQUIRED`) must preserve the ability of 6A to run in older environments where those priors are missing, *until* the environment is explicitly migrated.

   * During the transitional window, implementations **should**:

     * allow `status="OPTIONAL"` for the new prior,
     * fail at S1–S5 only if these priors are truly required for new features used in that deployment.

3. **Richer roles and scopes**:

   * Extending `status` or `read_scope` enums, or changing classification of specific artefacts (e.g. moving an artefact from `OPTIONAL` to `REQUIRED`), may require awareness from downstream code.

In all such cases:

* `spec_version_6A` / S0 version must be bumped,
* downstream code must branch on version or explicit presence of new fields/roles to remain compatible.

---

### 12.4 Breaking changes (disallowed without explicit migration)

The following are **breaking changes** and **must not** be introduced without an explicit migration plan and a major spec version bump for S0 and 6A:

1. **Changing shapes of S0 datasets** incompatibly:

   * Removing required fields from `s0_gate_receipt_6A` or `sealed_inputs_6A`.
   * Changing types or semantics of existing fields (e.g. changing `sealed_inputs_digest_6A` from SHA-256 to another hash without a new field name).
   * Changing partitioning (e.g. adding `seed` as a partition key) or path token names (e.g. renaming `manifest_fingerprint={manifest_fingerprint}`).

2. **Changing the digest law** for `sealed_inputs_digest_6A`:

   * Any modification to:

     * row ordering used for the digest,
     * canonical serialisation format,
     * hashing algorithm,

   is breaking. A new digest law must use a new field name (e.g. `sealed_inputs_digest_v2`) and versioned schema, and older consumers must continue to see the old field until deliberately migrated.

3. **Weakening upstream gate requirements**:

   * Treating upstream segments that are currently required as optional (e.g. allowing S0 PASS when `_passed.flag` is missing) changes the trust model and is breaking for any consumer that assumes full upstream sealing.

4. **Changing the set of required upstream segments** without transitional logic:

   * Removing a segment from the required set, or adding a segment and treating it as required immediately, is breaking.

5. **Reinterpreting roles or read scopes**:

   * Changing the meaning of `role` values (e.g. reusing `POPULATION_PRIOR` for a completely different kind of artefact),
   * Changing the behaviour associated with `read_scope` (e.g. permitting row-level reads for `METADATA_ONLY` artefacts) is breaking.

Any of these changes must:

* bump `spec_version_6A` in a **major** position,
* provide clear migration guidance,
* and be coordinated with 6B and any external consumers.

---

### 12.5 Compatibility obligations for downstream states

Downstream states **must** be written to handle S0 evolution within a version band:

* **Version pinning:**

  * Each 6A state (S1–S5) and 6B must declare a **minimum supported S0 spec version** (or `spec_version_6A`), and fail fast if `s0_gate_receipt_6A.spec_version_6A` is older than that.

* **Forwards compatibility within band:**

  * Within a given major version, downstream code must:

    * ignore unknown **fields** in `s0_gate_receipt_6A` and `sealed_inputs_6A`,
    * ignore unknown **role** values (treat as “do not use” or same as `IGNORED`),
    * tolerate additional upstream segments listed in `upstream_gates` beyond the required set, as long as the required ones remain PASS.

* **No assumptions on physical representation:**

  * Downstream code must not assume a particular storage format beyond the schema contract (e.g. Parquet vs JSON) when using catalogue resolution and schema refs.

---

### 12.6 Migration & dual-mode operation

When a breaking S0 change is introduced (new major version), engines that need to support **coexistence** of old and new worlds may operate in dual mode:

* Maintain **two S0 spec versions** side-by-side, keyed by:

  * `spec_version_6A` in `s0_gate_receipt_6A`, and
  * optional per-version schema anchors (e.g. `#/gate/6A/s0_gate_receipt_6A_v2`).

* Downstream states (S1–S5, 6B) may:

  * treat old S0 versions as “legacy worlds” with restricted capabilities,
  * only run newer features against worlds with the newer S0 spec version.

However, this dual-mode behaviour is a **deployment concern**; it does not alter the binding semantics of any **single** S0 spec version.

---

### 12.7 Non-goals

This section does **not** attempt to:

* govern versioning of *upstream* segments (1A–3B, 5A–5B); they have their own change-control specs,
* define CI/CD pipelines or branching strategies,
* dictate how many S0 versions should be supported concurrently in any deployment.

It **does** require that:

* any change to S0 that affects observable behaviour is explicitly versioned,
* consumers **never** infer compatibility by guesswork (e.g. “if field X exists, we must be on version ≥ 1.2.3”) without a clear spec rule, and
* any breaking change is treated as such, with a major version bump and coordinated migration.

These change-control and compatibility rules are binding on both 6A producers and 6A/6B consumers.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the short-hands and symbols used in 6A.S0 so an implementer (or reader of logs) doesn’t have to infer them from context.

---

### 13.1 Identity & hashes

* **`mf`**
  Short-hand for **`manifest_fingerprint`**.
  A world-level, opaque hash that identifies the *entire sealed world* (all upstream segments, policies, and artefacts). All 6A work is scoped to a single `mf`.

* **`ph`**
  Short-hand for **`parameter_hash`**.
  Identifies a specific parameter / config pack set (priors, policies). Multiple worlds (`mf`s) may share the same `ph`.

* **`sealed_inputs_digest_6A`**
  SHA-256 digest over the canonical representation of all rows in `sealed_inputs_6A` for a given `mf`.
  Think: “fingerprint of everything 6A is allowed to read for this world”.

* **`sha256_hex`**
  64-character lowercase hex encoding of a SHA-256 digest. Used for:

  * per-artefact digests in `sealed_inputs_6A`, and
  * bundle digests stored in upstream `_passed.flag` and similar flags.

---

### 13.2 Layers, segments & states

* **`L1` / `L2` / `L3`**
  Shorthands for engine layers:

  * `L1` = Layer-1 (world / merchant / geo / zones / virtual overlay: 1A–3B).
  * `L2` = Layer-2 (arrival surfaces & realisation: 5A–5B).
  * `L3` = Layer-3 (entity & flows: 6A–6B).

* **Segments (examples)**
  Written as `1A`, `2B`, `3A`, `3B`, `5A`, `5B`, `6A`, `6B` to denote:

  * `1A`–`3B` → Layer-1 segments,
  * `5A`, `5B` → Layer-2 segments,
  * `6A`, `6B` → Layer-3 segments.

* **States**
  Written as `6A.S0`, `6A.S1`, … to denote “Segment 6A, State S0 / S1 / …”.
  In this document we are specifying **`6A.S0`** only.

---

### 13.3 Datasets, catalogue & registry

* **Schema files**

  * `schemas.layer1.yaml`, `schemas.layer2.yaml`, `schemas.layer3.yaml` — layer-wide JSON-Schema authorities.
  * `schemas.6A.yaml` — 6A-specific JSON-Schema fragments.

* **Dataset dictionary**

  * `dataset_dictionary.layer3.6A.yaml` — catalogue of 6A datasets:

    * `id`, `path`, `partitioning`, `schema_ref`, lineage, etc.

* **Artefact registry**

  * `artefact_registry_6A.yaml` — manifest-level registry for 6A artefacts:

    * `manifest_key`, `dataset_id`, `semver`, `path_template`, dependencies, digests.

* **`schema_ref`**
  A JSON pointer or `$ref`-like string (e.g. `schemas.layer3.yaml#/gate/6A/sealed_inputs_6A`) indicating where the shape of a dataset/config is defined.

* **`manifest_key` / `logical_id`**
  A stable registry identifier for an artefact (dataset, config, policy, prior pack, etc.).
  Used as part of the primary key in `sealed_inputs_6A`.

---

### 13.4 Gates, bundles & validation

* **Gate / HashGate**
  Informal term for the pair:

  * a **validation bundle** (directory with index + evidence files), and
  * a `_passed.flag` file carrying the bundle digest.

  When we say a segment is “sealed” or “PASS”, we mean “its HashGate verified successfully”.

* **Validation bundle**
  For each upstream segment (1A–3B, 5A–5B) and eventually for 6A itself:

  * a directory rooted at a segment-specific path (e.g. `.../validation/manifest_fingerprint={mf}/`),
  * containing `index.json` / `validation_bundle_index_*` plus evidence files and `_passed.flag`.

* **`_passed.flag` / `validation_passed_flag_*`**
  A small artefact that records the final digest of the validation bundle for a segment.
  S0 re-computes the bundle digest and compares against this flag.

* **`upstream_gates`**
  A field in `s0_gate_receipt_6A` recording, for each upstream segment:

  * `segment_id` (e.g. `"1B"`),
  * `gate_status ∈ {PASS, FAIL, MISSING}`,
  * bundle and flag paths/digests.

---

### 13.5 Roles, statuses & scopes (sealed inputs)

These refer to columns in `sealed_inputs_6A`.

* **`role`** (non-exhaustive examples):

  * `UPSTREAM_EGRESS` — a dataset produced by an upstream segment (1A–3B, 5A–5B) that 6A may use.
  * `SCENARIO_CONFIG` — scenario/horizon configuration inputs.
  * `POPULATION_PRIOR`, `SEGMENT_PRIOR`, `PRODUCT_PRIOR`, `DEVICE_IP_PRIOR`, `FRAUD_ROLE_PRIOR` — types of 6A prior/config packs.
  * `TAXONOMY` — enumerations and classification vocabularies (segments, roles, risk classes).
  * `CONTRACT` — schemas, dictionaries, registries, or contracts.

* **`status`** (from 6A’s perspective):

  * `REQUIRED` — 6A cannot run without this artefact; its absence or invalidity is fatal in S0.
  * `OPTIONAL` — 6A may branch behaviour if present vs absent.
  * `IGNORED` — explicitly acknowledged artefact that 6A will not use (may be omitted in practice).

* **`read_scope`**:

  * `ROW_LEVEL` — later 6A states are allowed to read the artefact’s rows.
  * `METADATA_ONLY` — later 6A states may only use existence, schema, and digests (no row-level reads).

---

### 13.6 Miscellaneous shorthand & conventions

* **“World”**
  A colloquial term for “all artefacts tied to a single `manifest_fingerprint`”.
  When we say “for this world”, we mean “for this `manifest_fingerprint`”.

* **“Control plane” vs “data plane”**

  * *Control plane* — metadata-oriented states like 6A.S0 (schemas, dictionaries, bundles, digests).
  * *Data plane* — states that create large tabular outputs (entities, arrivals, flows).

* **Time notation**

  * `*_utc` — timestamps in UTC, RFC 3339 with microseconds.
  * `created_utc`, `started_utc`, `completed_utc` — audit fields; non-semantic for business logic.

* **“Catalogue”**
  The combination of:

  * schema files (`schemas.*.yaml`),
  * dataset dictionaries (`dataset_dictionary.*.yaml`),
  * artefact registries (`artefact_registry_*.yaml`),

  used to discover shapes, paths, and dependencies. Implementations must resolve artefacts through the catalogue, not through hard-coded paths.

This appendix is **informative** only; if any symbol description here appears to disagree with the binding sections (§1–§12), the binding sections (and the underlying schemas/dictionaries) take precedence.

---
