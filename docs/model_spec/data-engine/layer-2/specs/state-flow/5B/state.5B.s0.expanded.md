# 5B.S0 — Gate & sealed inputs (Layer-2 / Segment 5B)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5B.S0 — Gate & sealed inputs** for **Layer-2 / Segment 5B**. It is binding on any implementation of this state and on any downstream 5B state that consumes its outputs.

---

### 1.1 Role of 5B.S0 in the engine

5B.S0 is the **entry gate** and **closed-world definition** for Segment 5B (Arrival Realisation).

For a given `(parameter_hash, manifest_fingerprint)` it:

* **Verifies upstream readiness**
  Confirms that all required upstream segments – notably:

  * Layer-1: **1A–3B** (merchant world, site geometry, civil time, routing, zones, virtual overlay), and
  * Layer-2: **5A** (scenario-aware intensity surfaces)

  – have successfully completed and published their own validation bundles and `_passed.flag_*` artefacts for the same `manifest_fingerprint`.

* **Pins the 5B input universe**
  Resolves and records the **exact set of artefacts** that 5B is allowed to read for this world, across:

  * upstream Layer-1 outputs that 5B will rely on (site locations, site timezones, routing alias tables, zone allocations, virtual edge catalogues, universe hashes);
  * Layer-2 / 5A outputs (scenario-aware λ surfaces and scenario metadata);
  * Layer-2 / 5B-specific configuration packs (arrival process / LGCP hyper-parameters, arrival RNG policy, arrival-validation policy).

* **Emits control-plane datasets**
  Produces small, fingerprint-scoped control datasets that downstream 5B states use as their *only* authority for:

  * which upstream segments are considered valid for this run, and
  * which artefacts are in-scope for 5B (and under which schema/version/digest).

5B.S0 is **RNG-free** and **does not produce any counts, timestamps, or arrivals**. It deals only with run identity, upstream gate verification, catalogue-driven discovery, and governance metadata, mirroring the posture of existing gate states such as 2A.S0, 2B.S0 and 5A.S0.

---

### 1.2 Objectives

5B.S0 MUST:

* **Establish a clear trust boundary for 5B**

  * Enforce **“No upstream PASS → No 5B read”** for the set of required upstream segments (at minimum 1A–3B and 5A for the same `manifest_fingerprint`).
  * Refuse to proceed if any required upstream validation bundle or `_passed.flag_*` is missing, structurally invalid, or digest-mismatched according to that segment’s hashing law.

* **Define a sealed input universe for 5B**

  * Discover eligible inputs exclusively via Layer-1/Layer-2 dataset dictionaries and artefact registries (plus 5A’s sealed inventory where appropriate), not via ad-hoc filesystem paths or network calls.
  * Materialise a **sealed inventory** of those inputs – including logical IDs, schema refs, roles, digests, and partition templates – as `sealed_inputs_5B`.
  * Make that sealed inventory available to all later 5B states as a single source of truth for “what 5B is allowed to read” in this world.

* **Minimise downstream coupling**

  * Summarise upstream status and input universe in a compact **gate receipt** (`s0_gate_receipt_5B`), instead of requiring 5B.S1+ to understand every upstream bundle/index/flag format.
  * Expose only the identifiers and digests that later states need to prove consistency (segment IDs, spec versions, artefact IDs, SHA-256 hashes), not the internal structure of upstream bundles.

* **Remain lightweight and deterministic**

  * Operate almost entirely over metadata – validation bundle indices, dictionary/registry entries, small policy/config objects.
  * NEVER read bulk fact tables at row-level (e.g. `site_locations`, `site_timezones`, `zone_alloc`, 5A intensity surfaces); those are reserved for later 5B states.
  * Consume **no RNG** and perform no numerical modelling or arrival-process computation.

---

### 1.3 In-scope behaviour

The following activities are **in scope** for 5B.S0 and MUST be handled by this state (not duplicated elsewhere in 5B):

* **Run identity resolution**

  * Resolving and recording the `(parameter_hash, manifest_fingerprint, run_id)` triple for the 5B run (plus any engine-level context such as environment/CI build), and linking it to the engine’s global manifest / run-report identity.

* **Upstream validation verification**

  * For each required upstream segment (1A, 1B, 2A, 2B, 3A, 3B, 5A), re-verifying that for the target `manifest_fingerprint`:

    * its validation bundle root exists and is schema-valid,
    * its `_passed.flag_*` artefact is present and structurally valid, and
    * the flag’s digest matches the bundle contents according to that segment’s own hashing law.

* **Catalogue-driven input discovery**

  * Using only dataset dictionaries and artefact registries (plus any prior sealed-inputs tables from 5A / Layer-1) to:

    * discover which candidate artefacts (datasets/configs/policies) are eligible as inputs to 5B for this world;
    * resolve their logical IDs, physical path templates, partition keys, schema_refs, and digests;
    * determine which of those belong to the current `(parameter_hash, manifest_fingerprint)` pair and are required vs optional for 5B.

* **Sealed inventory construction**

  * Constructing `sealed_inputs_5B` as a fingerprint-scoped inventory of all artefacts that 5B.S1+ MAY read, including:

    * 5A scenario/intensity surfaces and scenario manifests,
    * Layer-1 civil-time and routing/zone/edge artefacts that 5B will depend on (2A, 2B, 3A, 3B egresses and policies),
    * 5B-specific configs and policy packs (LGCP/arrival hyper-params, arrival RNG layout, arrival validation policy).

* **Gate receipt emission**

  * Constructing `s0_gate_receipt_5B` as a compact, schema-governed object that:

    * records which upstream segments were verified for this `manifest_fingerprint` (and under which spec / catalogue versions),
    * records the `(parameter_hash, manifest_fingerprint, run_id)` bound to this sealed universe,
    * summarises the sealed inputs via a digest (e.g. `sealed_inputs_digest`) and row counts by role, and
    * provides the single pointer that all later 5B states use to locate `sealed_inputs_5B`.

---

### 1.4 Out-of-scope behaviour

The following activities are explicitly **out of scope** for 5B.S0 and MUST NOT be performed by this state:

* **Row-level data processing**

  * 5B.S0 MUST NOT:

    * scan or aggregate bulk rows from Layer-1 egress tables (e.g. `site_locations`, `site_timezones`, `zone_alloc`, `edge_catalogue_3B`);
    * read 5A’s intensity surfaces at row level;
    * compute any bucket-level or event-level statistics.

* **Random number generation**

  * 5B.S0 MUST NOT:

    * consume any RNG streams,
    * emit RNG events, or
    * alter RNG budgets, envelopes, or Philox stream layout.

  All stochastic realisation (LGCP fields, Poisson/NB draws, intra-bucket time placement, routing draws) belongs to later 5B modelling states and to the existing Layer-1 routing segments.

* **Arrival or routing semantics**

  * 5B.S0 MUST NOT:

    * generate arrival counts or timestamps,
    * route arrivals to sites or edges,
    * interpret or modify zone assignments, routing weights, day-effects, or virtual routing policies.

  It may only acknowledge that these artefacts exist and record them in `sealed_inputs_5B`.

* **Segment-level PASS for 5B**

  * 5B.S0 does **not** decide the overall “5B segment PASS” verdict.
  * It participates in any later 5B validation/HashGate state by producing its own outputs, but the final **segment-level PASS / FAIL** for 5B will be owned by a dedicated validation state (analogous to 5A.S5 and 3B.S5).

---

### 1.5 Downstream obligations

This specification imposes the following obligations on all downstream 5B states (S1+):

* **Gating on 5B.S0 outputs**

  * Any 5B state **MUST**:

    * check for a valid `s0_gate_receipt_5B` for the target `(parameter_hash, manifest_fingerprint)` before reading any upstream artefacts, and
    * restrict itself to artefacts listed in `sealed_inputs_5B` for that fingerprint.

  * If `s0_gate_receipt_5B` or `sealed_inputs_5B` is missing, invalid, or inconsistent, downstream 5B states MUST treat this as a **hard precondition failure** and MUST NOT attempt to infer or widen their input universe.

* **Respect upstream status recorded by 5B.S0**

  * Downstream 5B states MUST treat the upstream segment statuses recorded in `s0_gate_receipt_5B` as authoritative for gating decisions (e.g. “No 5A PASS → do not use 5A intensities to drive arrivals”), and MUST NOT silently override or reinterpret those statuses.

* **No back-writes to S5 artefacts**

  * No later state may modify or overwrite `s0_gate_receipt_5B` or `sealed_inputs_5B` for any `(parameter_hash, manifest_fingerprint)`.
  * Any required change to the sealed input universe MUST be expressed via catalogue/config changes, a new `parameter_hash` and/or manifest, and a re-run of 5B.S0 under those identities.

Within this scope, **5B.S0** cleanly defines the **sealed universe** in which arrival realisation is allowed to happen: later 5B states build counts, times and routes **inside** that universe, but they cannot widen it or bypass its gate.

---

## 2. Preconditions, upstream gates & run identity *(Binding)*

This section defines **when** the Gate & sealed inputs state may run, **which upstream gates it depends on**, and **how the 5B run identity is defined and fixed**. These requirements are binding on any implementation of this state.

---

### 2.1 Invocation context (engine/run-level)

5B’s gate state MUST only be invoked in the context of a well-defined engine run, characterised by at least:

* A concrete **`parameter_hash`**
  – identifying the parameter pack in use for this run (including 5B’s arrival-process policy, LGCP hyper-parameters, and any 5B-specific validation settings, plus any shared Layer-2 policies it depends on).

* A concrete **`manifest_fingerprint`**
  – identifying the closed-world manifest (set of artefacts and their digests) for this run, as defined by the engine’s global manifest hashing law.

* A concrete **`seed`**
  – identifying the RNG seed for this run, consistent with the Layer-wide RNG law (Philox-based) and the Layer-2 RNG policy packs that 5B will consume.

* A concrete **`run_id`**
  – an engine-level identifier distinguishing multiple invocations for the same `{parameter_hash, manifest_fingerprint, seed}` combination (e.g. CI vs prod, or replays). `run_id` MAY be used for logging and trace correlation but MUST NOT alter the semantics of sealed inputs.

* A defined **scenario binding**
  – either:

  * a single **`scenario_id`** from the 5A scenario manifest that 5B will realise arrivals for in this run, *or*
  * an explicit, finite set of `scenario_id` values that 5B intends to process.
    The binding MUST be consistent with the 5A scenario manifest for this `{parameter_hash, manifest_fingerprint}`.

If any of these identifiers are missing, inconsistent, or cannot be established from the engine’s run context, the gate state MUST treat this as a **fatal precondition failure** and MUST NOT proceed to seal inputs.

---

### 2.2 Catalogue & contract preconditions

Before the gate state begins, the following catalogue/contract preconditions MUST hold:

1. **Layer-wide schema packs are deployed**

   * The Layer-1 schema packs (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, and segment-local packs for 1A–3B) MUST be present and parseable.
   * The Layer-2 schema packs (`schemas.layer2.yaml`, and the segment-local packs for 5A and 5B) MUST be present and parseable.
   * All schema packs referenced by the 5B Dataset Dictionary and Artefact Registry MUST be self-consistent (no duplicate `$id`, anchors resolve, required `$defs` exist).

2. **Dataset dictionaries are deployed**

   * Dataset dictionaries for Layer-1 segments **1A–3B** MUST be present and consistent with their schema packs.
   * Dataset dictionaries for Layer-2 segments **5A and 5B** MUST be present and reference only valid schema anchors.
   * Any additional dictionaries referenced by 5B’s registry (e.g. global Layer-2 or shared control surfaces) MUST also be available.

3. **Artefact registries are deployed**

   * Artefact registries for **1A–3B** MUST be present and consistent with their dictionaries and schemas.
   * Artefact registries for **5A and 5B** MUST be present and consistent with `dataset_dictionary.layer2.5A.yaml` and `dataset_dictionary.layer2.5B.yaml`.
   * Registries for shared reference data (e.g. time-zone, spatial, and policy packs) that 5B intends to consume MUST be present.

4. **Catalogue-only resolution**

   * The runtime for this state MUST provide access to all required artefacts **via the catalogue abstraction** (dictionary + registry lookups, plus any prior sealed-inputs tables where applicable).
   * The state MUST NOT rely on:

     * hard-coded filesystem paths,
     * ad-hoc network locations,
     * environment-specific or external service discovery
       to locate upstream artefacts.

If any of these catalogue/contract preconditions are violated, this state MUST abort with a canonical “run context / catalogue invalid” error and MUST NOT attempt to infer or reconstruct missing contracts at runtime.

---

### 2.3 Required upstream segment gates (PASS requirements)

This gate state sits in Layer-2 and depends on both Layer-1 and Layer-2 upstream segments. For a given `manifest_fingerprint`, it is responsible for **verifying** the status of at least the following upstream segments:

* **Layer-1**

  * **1A** – Merchant → outlet catalogue
  * **1B** – Site geolocation → `site_locations`
  * **2A** – Civil time → `site_timezones`, `tz_timetable_cache`
  * **2B** – Routing weights, alias tables, day-effects
  * **3A** – Merchant zone allocation → `zone_alloc`, `zone_alloc_universe_hash`
  * **3B** – Virtual overlay & CDN edges → virtual classification & edge universe

* **Layer-2**

  * **5A** – Deterministic intensity surfaces and scenario manifest for the same `manifest_fingerprint`.

For each of these segments, the gate state MUST enforce the upstream **“No PASS → No read”** law:

* For the target `manifest_fingerprint`, the following MUST all hold for each required upstream segment:

  1. A **validation bundle directory** exists at the catalogue-resolved location for that segment and fingerprint.
  2. A **`_passed.flag_*`** file exists in that directory and is structurally valid (exact expected format for that segment).
  3. The digest recorded in `_passed.flag_*` matches the contents of the bundle according to that segment’s own hashing law.
  4. No additional or missing files are present relative to that segment’s declared bundle index, unless explicitly permitted by that segment’s spec.

* If any of these conditions fail for any required upstream segment, this gate state MUST:

  * record the failure in its run-report / logs, and
  * abort with a canonical upstream-gate error, and
  * MUST NOT construct a `sealed_inputs_5B` inventory or any gate receipt implying that 5B may consume those upstream artefacts.

Future 5B states (S1+) MUST treat the upstream PASS/FAIL map recorded by this gate state as **authoritative** when deciding whether they may consume any upstream data.

---

### 2.4 Run identity tuple & invariants

For the purposes of Layer-2 / Segment 5B, the **run identity** for this state is defined as the tuple:

> **`run_identity_5B := (parameter_hash, manifest_fingerprint, seed, run_id)`**

with an associated **scenario set**:

> **`scenario_set_5B ⊆ ScenarioIDs_5A(parameter_hash, manifest_fingerprint)`**

The following invariants are binding:

1. **Fixed for the lifetime of the state**

   * `parameter_hash`, `manifest_fingerprint`, and `seed` MUST be fixed at the start of this state and MUST NOT change for the lifetime of the state invocation.
   * `run_id` MUST remain stable for all artefacts produced by this state and MUST be recorded consistently wherever it is embedded (e.g. in control-plane datasets and run-report artefacts).

2. **Consistency with upstream identity laws**

   * `parameter_hash` and `manifest_fingerprint` MUST respect the Layer-wide identity laws defined elsewhere (e.g. the tuple-hash that defines the fingerprint).
   * The gate state MUST NOT introduce alternate notions of “world identity”; it may only reference and reuse the upstream identity contracts.

3. **Scenario binding**

   * `scenario_set_5B` MUST be a subset of the `scenario_id` values present in the 5A scenario manifest for this `{parameter_hash, manifest_fingerprint}`.
   * If the engine run is configured for a **single scenario**, then `scenario_set_5B` MUST be a singleton `{scenario_id}` and this scenario_id MUST be recorded in the gate receipt.
   * If multiple scenarios are to be processed under the same `{parameter_hash, manifest_fingerprint, seed, run_id}`, the gate state MUST record the full `scenario_set_5B` in the sealed inventory or receipt, and all later 5B states MUST treat that set as the only admissible scenario domain for this run.

4. **Idempotency under the same identity**

   * Multiple invocations of this state with the exact same `run_identity_5B` and `scenario_set_5B` and the same underlying catalogue MUST either:

     * be prevented by the engine (single-writer semantics), or
     * produce byte-identical outputs for all of this state’s datasets (gate receipt + sealed inputs), if re-execution is allowed.
   * Implementations MUST NOT write conflicting receipts or sealed-inputs inventories for the same `run_identity_5B`.

5. **Scope of identity vs sealed inputs**

   * `run_identity_5B` defines **who we are running as** (parameters, world, seed, run);
   * `sealed_inputs_5B` defines **what we are allowed to read** in that world.
     The gate state MUST bind these together by:

     * embedding `run_identity_5B` into its outputs, and
     * ensuring that every row in `sealed_inputs_5B` is consistent with the `{parameter_hash, manifest_fingerprint}` component of the run identity.

Within these invariants, this state provides a stable, deterministic **run context** for the rest of Segment 5B: all later states operate under the same `{parameter_hash, manifest_fingerprint, seed, run_id}` and scenario set, and accept that **only** upstream segments with verified PASS flags may be used as data sources.

---

## 3. Inputs, authorities & closed-world boundary *(Binding)*

This section defines **what 5B.S0 is allowed to read**, **who is authoritative for which facts**, and **how the closed world for Segment 5B is fixed**. These rules are binding on both this state and all later 5B states that consume its outputs.

---

### 3.1 Authority chain & precedence

5B.S0 MUST respect the existing engine authority chain:

1. **JSON-Schema packs**

   * Layer-wide (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.layer2.yaml`), and
   * segment-local packs (1A–3B, 5A, 5B).
     These are the **only** authorities for dataset shapes, validation-bundle shapes, and control-plane object structures.

2. **Dataset dictionaries**

   * For segments 1A–3B and 5A–5B, the dataset dictionaries are the **sole authorities** for:

     * dataset identities and dataset IDs,
     * path templates and partition keys,
     * schema anchors for each dataset,
     * dataset-level lifecycle and “final_in_layer” flags.

3. **Artefact registries**

   * For segments 1A–3B, 5A, 5B and shared reference packs, their registries are the **only authorities** for:

     * which artefacts exist (datasets, configs, logs, bundles),
     * their roles (`dataset`, `config`, `validation`, `log`, etc.),
     * their semver/spec versions and environment bindings,
     * dependencies between artefacts.

4. **State specifications**

   * The expanded state docs (e.g. for 1B, 2A, 2B, 3A, 3B, 5A, 5B) are authoritative for:

     * the behaviour of each state,
     * the meaning of each dataset,
     * the expected invariants and gates.

5B.S0 MUST NOT introduce any new source of authority outside this chain. Where conflicts appear, resolution order is:

> **JSON-Schema pack → Dataset dictionary → Artefact registry → State specification (this document)**

If any of these disagree at runtime, this state MUST treat that as a catalogue/contract error and MUST NOT attempt to “guess” the intended semantics.

---

### 3.2 Input classes & resolution rules

5B.S0 MAY only read from the following classes of inputs, and MUST resolve them exclusively via dictionaries/registries (and any upstream sealed-input manifests), not via literal paths or ad-hoc discovery.

#### 3.2.1 Upstream validation bundles & PASS flags

For each required upstream segment (1A, 1B, 2A, 2B, 3A, 3B, 5A), 5B.S0 MAY read:

* The **validation bundle index** and constituent files for the target `manifest_fingerprint`.
* The corresponding **`_passed.flag_*`** artefact.

Usage constraints:

* These artefacts MUST be located via the upstream segment’s dataset dictionary and/or artefact registry.
* 5B.S0 MAY read them at **file level** (raw bytes) to:

  * re-run the upstream hashing law, and
  * confirm that the bundle digest matches the flag.
* 5B.S0 MUST NOT:

  * reinterpret or modify the upstream bundle contents, or
  * treat any upstream bundle as its own sealed-input inventory; they’re only evidence that the upstream segment is “green”.

#### 3.2.2 Upstream sealed-input manifests

Where upstream segments publish sealed-inputs tables (e.g. `sealed_inputs_v1` in 2A/2B/3A/3B, `sealed_inputs_5A` in 5A), 5B.S0 MAY read those manifests in **row form** as part of its own sealing process.

* These tables are treated as **trusted evidence** of what each upstream segment has already sealed into its own manifest.
* 5B.S0 MAY use them to:

  * avoid re-hashing large upstream artefacts, and
  * propagate upstream asset IDs and digests into `sealed_inputs_5B`.

5B.S0 MUST NOT relax upstream closed-world rules: the presence of an asset in an upstream `sealed_inputs_*` table does not make it automatically in-scope for 5B; 5B.S0 still decides which of those assets become part of the 5B closed world.

#### 3.2.3 Upstream data-plane egress artefacts

5B.S0 MAY *reference* the following upstream data-plane artefacts, **but only at metadata / file level** (never interpreting bulk rows):

* **From Layer-1 / 1B & 2A (world geometry & time)**

  * `site_locations@seed,fingerprint`
  * `site_timezones@seed,fingerprint`
  * `tz_timetable_cache@fingerprint`

* **From Layer-1 / 2B (routing law & day-effects)**

  * `s1_site_weights@seed,fingerprint`
  * `s2_alias_blob@seed,fingerprint` + `s2_alias_index@seed,fingerprint`
  * `s3_day_effects@seed,fingerprint` (if 5B will later depend on γ explicitly)
  * `s4_group_weights@seed,fingerprint` (if 5B will later depend on per-day tz-group weights)

* **From Layer-1 / 3A (zone allocation)**

  * `zone_alloc@seed,fingerprint`
  * `zone_alloc_universe_hash@fingerprint`

* **From Layer-1 / 3B (virtual overlay & edge universe)**

  * `virtual_classification_3B@seed,fingerprint`
  * `virtual_settlement_3B@seed,fingerprint`
  * `edge_catalogue_3B@seed,fingerprint` + `edge_catalogue_index_3B`
  * `edge_alias_blob_3B@seed,fingerprint` + `edge_alias_index_3B`
  * `edge_universe_hash_3B@fingerprint`
  * `virtual_routing_policy_3B@fingerprint`
  * `virtual_validation_contract_3B@fingerprint`

* **From Layer-2 / 5A (intensity surfaces & scenario metadata)**

  * `scenario_manifest_5A@fingerprint`
  * `merchant_zone_profile_5A@fingerprint`
  * `shape_grid_definition_5A@parameter_hash,scenario_id`
  * `class_zone_shape_5A@parameter_hash,scenario_id`
  * `merchant_zone_baseline_local_5A@fingerprint,scenario_id`
  * `merchant_zone_scenario_local_5A@fingerprint,scenario_id`
  * Optional surfaces such as `merchant_zone_overlay_factors_5A` and `merchant_zone_scenario_utc_5A` if defined.

For these artefacts, 5B.S0 MAY:

* Confirm their **existence** (via catalogue and filesystem metadata).
* Read **file-level properties** (size, modification timestamps, raw bytes for hashing).
* Record their **schema_ref**, **logical IDs**, **partition templates**, and **digests** into `sealed_inputs_5B`.

5B.S0 MUST NOT:

* scan or interpret their rows,
* perform any aggregations over their contents, or
* use any row-level values to influence sealing logic.

Row-level processing of these datasets belongs to later 5B states.

#### 3.2.4 5B-local configuration & policy packs

5B.S0 MAY read 5B-local configuration and policy artefacts, as defined in the 5B artefact registry, such as:

* arrival-process configuration (e.g. LGCP kernel choices, dispersion parameters, horizon options);
* 5B RNG policy (stream names, substream labels, draw budgets for arrival RNG events);
* 5B validation policy (acceptable Fano corridors, stress-test thresholds, allowed deviation from λ surfaces, etc.).

These MUST be:

* classified as `config` or `policy` artefacts in the 5B registry;
* schema-governed (JSON/YAML shapes validated against `schemas.layer2.yaml` or `schemas.5B.yaml`); and
* included in `sealed_inputs_5B` with their logical IDs, versions and digests.

5B.S0 MUST NOT invent new, ad-hoc config sources (e.g. environment variables, inline config blobs) that bypass the artefact registry.

---

### 3.3 Closed-world boundary & `sealed_inputs_5B`

`sealed_inputs_5B` is the **canonical representation of the closed world** in which Segment 5B is allowed to operate for a given `manifest_fingerprint`. This state defines its semantics as follows:

1. **Inclusion criteria**

   Each row in `sealed_inputs_5B` corresponds to a single artefact that 5B may reference, and MUST include at least:

   * `manifest_fingerprint`
   * `parameter_hash` — fixed hex string for the governing parameter pack (fingerprint-only artefacts still carry the same value)
   * `owner_layer` / `owner_segment` (e.g. `layer1` + `2A`, `layer2` + `5A`)
   * `artifact_id` and, where applicable, `manifest_key`
   * `role` (e.g. `DATASET`, `CONFIG`, `VALIDATION_BUNDLE`, `POLICY`, `FLAG`, `LOG`)
   * `schema_ref` (JSON-Schema anchor)
   * `path_template` and partition key spec (as per the dataset dictionary / artefact registry)
   * `sha256_hex` (or equivalent digest) resolved from catalogue or sealed-input tables
   * `status` (`REQUIRED`, `OPTIONAL`, `INTERNAL`, or `IGNORED`)
   * `read_scope` (`METADATA_ONLY` or `ROW_LEVEL`)

2. **Whitelist semantics**

   * For a given `manifest_fingerprint`, the set of artefacts that later 5B states MAY read is **exactly** the set of rows in `sealed_inputs_5B` for that fingerprint where `status ∈ {REQUIRED, OPTIONAL, INTERNAL}`.
   * Any artefact not present in `sealed_inputs_5B` for that fingerprint is considered **out of world** for 5B and MUST NOT be read by any 5B state.
   * Any artefact with `status = IGNORED` MUST NOT be read by 5B, even if it physically exists; its presence is recorded solely for audit/book-keeping.

3. **Read-scope semantics**

   * If `read_scope = METADATA_ONLY`, 5B states MAY only:

     * confirm existence,
     * read raw bytes for hashing,
     * inspect file-size and modification timestamps.
       They MUST NOT introspect schema-conforming rows or use row-level values as inputs to modelling logic.
   * If `read_scope = ROW_LEVEL`, later 5B states MAY read rows as needed, but MUST still respect the owning segment’s authority boundaries (see 3.4).

4. **Completeness and consistency**

   * `sealed_inputs_5B` MUST contain **all** artefacts that any later 5B state will read for this `manifest_fingerprint`, across all configured `scenario_id` values for the run.
   * If a 5B state discovers at runtime that it needs an artefact not present in `sealed_inputs_5B`, it MUST treat this as a configuration error (not silently widen the world) and fail.

---

### 3.4 Authority by concern (who owns what)

Within the 5B closed world, the following authority rules apply and MUST be recorded implicitly in `owner_segment` + `role` fields:

* **Merchant universe, outlet counts, and base cross-country order**

  * **Owner:** Segment 1A
  * 5B MUST treat 1A’s merchant and outlet surfaces as fixed and MUST NOT re-encode cross-country order or alter counts.

* **Site geometry**

  * **Owner:** Segment 1B (`site_locations`)
  * 5B MUST NOT modify or reinterpret outlet positions; any location data in arrivals must be derived by join from this surface.

* **Civil time (tzid, gaps/folds)**

  * **Owner:** Segment 2A (`site_timezones`, `tz_timetable_cache`)
  * 5B MUST use these artefacts for local/UTC mapping and DST logic; it MUST NOT invent alternative tz mappings.

* **Routing probabilities, alias tables, and day-effects**

  * **Owner:** Segment 2B
  * 5B MUST treat `s1_site_weights`, `s2_alias_blob/index`, and `s4_group_weights` as the only valid long-run routing law and tz-group mix; it MUST NOT create an independent routing surface.

* **Zone allocation & routing universe hash**

  * **Owner:** Segment 3A (`zone_alloc`, `zone_alloc_universe_hash`)
  * 5B MUST not change the mapping of merchants to zones or the routing universe hash; it may only reference this for consistency.

* **Virtual overlay & edge universe**

  * **Owner:** Segment 3B (`virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`, `edge_alias_blob/index`, `edge_universe_hash_3B`, `virtual_routing_policy_3B`)
  * 5B MUST use these artefacts when routing virtual arrivals; it MUST NOT redefine virtual vs physical semantics or edge geometry.

* **Intensity surfaces & scenarios**

  * **Owner:** Segment 5A
  * `merchant_zone_scenario_local_5A` is the only authority for deterministic λ surfaces; 5B MUST treat this as the mean structure of the arrival process and MUST NOT attempt to recompute or override λ from lower-level priors.

* **Arrival process, arrival RNG and arrival validation**

  * **Owner:** Segment 5B
  * 5B-local configs/policies define the law by which 5B realises arrivals (LGCP, Poisson/NB, Fano corridors, etc.).
  * 5B.S0 MUST seal these configs as part of `sealed_inputs_5B`, but it MUST NOT execute any stochastic logic; that is the job of later 5B states.

---

### 3.5 Prohibited inputs

5B.S0 and its downstream states MUST treat the following as **out-of-bounds** for the closed world:

* Any artefact (dataset, config, log, bundle) that:

  * is not present in the combination of:

    * Layer-1/Layer-2 dictionaries & registries, and
    * upstream sealed-inputs manifests, and
  * is not listed as a row in `sealed_inputs_5B` for the target `manifest_fingerprint`.

* Any external or environment-specific sources, including but not limited to:

  * direct filesystem paths not reachable via catalogue templates,
  * ad-hoc network calls or web APIs,
  * environment variables used as hidden config inputs,
  * local test-only or scratch artefacts not registered in the artefact registries.

* Any future 5B outputs (e.g. arrival streams, bucket counts, latent fields) produced under the same `manifest_fingerprint`. 5B.S0 MUST NOT treat its own segment’s later outputs as inputs; this would break acyclicity of the state graph.

Within this boundary, **5B.S0** fixes the exact world in which the arrival realisation segment is allowed to run. Later 5B states MUST operate strictly within this sealed world and MUST NOT introduce new input dependencies that are not first recorded in `sealed_inputs_5B`.

---

## 4. Outputs (control-plane datasets) & identity *(Binding)*

This state produces **only control-plane artefacts**. They are small, RNG-free, and fingerprint-scoped, and they exist purely to let later 5B states know:

* *“Which upstream segments are green for this world?”*
* *“Exactly which artefacts are in scope for 5B, under which IDs/digests?”*

No data-plane (arrival) artefacts originate here.

---

### 4.1 Output list (normative)

5B.S0 MUST produce exactly these datasets:

1. **`s0_gate_receipt_5B`**

   * One JSON object per `manifest_fingerprint`.
   * A compact receipt that says:

     * which upstream segments (1A–3B, 5A) were verified,
     * which `{parameter_hash, seed, run_id, scenario_set}` this sealing applies to,
     * and which version/digest of `sealed_inputs_5B` is bound to that fingerprint.

2. **`sealed_inputs_5B`**

   * A tabular inventory (Parquet or equivalent) of artefacts that 5B is allowed to read for that `manifest_fingerprint`.
   * One row per artefact (dataset/config/bundle/policy), with logical IDs, schema refs, roles and digests.

No other “S5-owned” datasets are permitted. Any additional logs, run-reports or metrics MUST be produced by other states (e.g. a 5B validation state).

---

### 4.2 `s0_gate_receipt_5B` — contract & identity

**Schema & anchors**

* MUST conform to a JSON-Schema anchor under the 5B schema pack, e.g.:
  `schemas.5B.yaml#/validation/s0_gate_receipt_5B`
* The dataset dictionary for Layer-2 / 5B MUST reference that schema anchor.

**Logical content (high-level)**

Each row (there SHOULD be exactly one per `manifest_fingerprint`) MUST contain at least:

* `manifest_fingerprint` — the world fingerprint this receipt covers.
* `parameter_hash` — parameter pack in effect when sealing.
* `seed` — RNG seed for the run.
* `run_id` — engine run identifier.
* `scenario_set` — list of `scenario_id` values 5B intends to realise under this sealing (MUST be non-empty and match the scenario manifest for this fingerprint).
* `upstream_segments` — map from segment ID (`"1A"`, `"1B"`, `"2A"`, `"2B"`, `"3A"`, `"3B"`, `"5A"`) to a minimal status object:

  * at minimum: `{ status: "PASS" | "FAIL" | "MISSING", bundle_path, flag_path }`.
* `spec_version` — semantic version of the S0 contract implemented by this receipt.
* `sealed_inputs_digest` — a SHA-256 (or equivalent) digest over the normalised bytes of `sealed_inputs_5B` for this fingerprint (schema will define exact hashing law).
* `sealed_inputs_row_count` — row count of `sealed_inputs_5B`.
* `created_utc` — gate execution timestamp.

**Identity & partitioning**

* **Partitioning:**

  * MUST be partitioned on `fingerprint={manifest_fingerprint}`.

* **Primary key:**

  * Logical PK MUST be `manifest_fingerprint`.
  * Exactly one row per fingerprint MUST exist in a valid run.

* **Path template (normative intent):**

  ```text
  data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
  ```

* **Mutability:**

  * MUST be treated as **write-once per `(manifest_fingerprint, run_id)`**.
  * Re-runs with identical `{parameter_hash, manifest_fingerprint, seed, run_id}` and identical upstream catalogue MUST produce byte-identical content.

---

### 4.3 `sealed_inputs_5B` — contract & identity

**Schema & anchors**

* MUST conform to a tabular JSON-Schema anchor under the 5B schema pack, e.g.:
  `schemas.5B.yaml#/control/sealed_inputs_5B`
* The dataset dictionary MUST reference that anchor and classify this dataset as `role: control`.

**Row-level content (high-level)**

Each row describes a single artefact that 5B is allowed to see. It MUST include at least:

* `manifest_fingerprint`
* `parameter_hash` — nullable when the artefact is fingerprint-only.
* `owner_layer` / `owner_segment`
* `artifact_id` (and, where applicable, `manifest_key`)
* `role` — `DATASET` | `CONFIG` | `POLICY` | `VALIDATION_BUNDLE` | `FLAG` | `LOG`
* `schema_ref`
* `path_template`
* `partition_keys`
* `sha256_hex`
* `status` — `REQUIRED` | `OPTIONAL` | `INTERNAL` | `IGNORED`
* `read_scope` — `ROW_LEVEL` | `METADATA_ONLY`

Optional metadata (`notes`, `source_manifest`, `owner_team`, etc.) MAY appear but MUST NOT be required.

**Identity & partitioning**

* **Partitioning:**

  * MUST be partitioned on `fingerprint={manifest_fingerprint}`.

* **Primary key:**

  * At minimum, the tuple `(manifest_fingerprint, owner_segment, artifact_id)` MUST be unique.
  * Schema MAY define a stricter PK if useful (e.g. including `artifact_kind`).

* **Path template (normative intent):**

  ```text
  data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
  ```

* **Mutability:**

  * MUST be treated as **immutable** once written for a given fingerprint.
  * Any change to the set or classification of sealed inputs MUST be expressed by changing:

    * the manifest (new `manifest_fingerprint`), or
    * the parameter pack (`parameter_hash`), and re-running 5B.S0.

---

### 4.4 Relationship to run identity

Both outputs MUST embed the run identity defined in §2:

* `parameter_hash` and `manifest_fingerprint` MUST be present and must match the path tokens.
* `seed` and `run_id` MUST be present in `s0_gate_receipt_5B` and MAY be omitted from `sealed_inputs_5B` rows if redundant.
* `scenario_set` MUST be recorded in `s0_gate_receipt_5B`; `sealed_inputs_5B` MAY carry scenario information only if some artefacts are scenario-scoped.

No 5B state may treat artefacts from a different `{parameter_hash, manifest_fingerprint}` pair as part of the sealed world for this run, even if they are physically reachable.

---

### 4.5 Downstream usage obligations

For all later 5B states (S6+ in your numbering), the following are binding:

* They MUST locate and read **exactly one** `s0_gate_receipt_5B` for their target `manifest_fingerprint` and treat it as authoritative for:

  * upstream segment PASS statuses, and
  * the identity of the sealed input inventory (`sealed_inputs_digest`).

* They MUST treat `sealed_inputs_5B` as the **whitelist** of admissible inputs:

  * MAY read only artefacts listed in `sealed_inputs_5B` for that fingerprint,
  * MUST respect each row’s `read_scope`, and
  * MUST NOT introduce new input dependencies until `sealed_inputs_5B` is regenerated by rerunning 5B.S0 under a new manifest/parameter pack.

With these two control-plane datasets and the identity rules above, 5B’s “world” is precisely defined and reproducible for any `{parameter_hash, manifest_fingerprint, seed, run_id}`.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes the **dataset identities, schema anchors and catalogue links** for the outputs of **5B.S0 — Gate & sealed inputs**. It is binding on:

* the JSON-Schema packs (`schemas.layer2.yaml`, `schemas.5B.yaml`),
* the Layer-2 / 5B dataset dictionary, and
* the 5B artefact registry.

5B.S0 produces **exactly two datasets**:

1. `s0_gate_receipt_5B` – a single, fingerprint-scoped control object.
2. `sealed_inputs_5B` – a fingerprint-scoped inventory table of admissible inputs for 5B.

> **Naming note:**
> Although this state is labelled “5B.S0” in the state-flow, the dataset names follow the existing Layer-1/Layer-2 convention for gate receipts (prefix `s0_…`) to stay aligned with 1A/1B/2A/2B/5A.

---

### 5.1 `s0_gate_receipt_5B` — schema anchor & shape

**Dataset ID (dictionary):**

* `id`: `s0_gate_receipt_5B`
* `owner_segment`: `5B`
* `layer`: `2`

**Schema anchor:**

* `schema_ref`: `schemas.5B.yaml#/validation/s0_gate_receipt_5B`

**Logical shape (minimum fields):**

The `s0_gate_receipt_5B` schema MUST describe a **single JSON object per `manifest_fingerprint`**, with at least the following fields (names may be adjusted in the concrete schema but MUST be stable once published):

* `manifest_fingerprint : string`

  * The fingerprint this receipt applies to.

* `parameter_hash : string`

  * The parameter hash bound to this sealed universe.

* `seed : integer | string`

  * Seed for the engine run (as defined in §2).

* `run_id : string`

  * Engine/run identifier; unique within (`parameter_hash`, `manifest_fingerprint`, `seed`).

* `scenario_set : array<string>`

  * Non-empty list of `scenario_id` values that 5B is allowed to process for this (`parameter_hash`, `manifest_fingerprint`, `seed`, `run_id`).

* `created_utc : string` (RFC3339 with micros)

  * Timestamp of receipt creation.

* `upstream_segments : object`

  * Map from segment ID (`"1A"`, `"1B"`, `"2A"`, `"2B"`, `"3A"`, `"3B"`, `"5A"`) to a small object capturing:

    * `status : "PASS" | "FAIL" | "MISSING"`
    * `spec_version : string`
    * `bundle_digest : string` (the digest from the upstream `_passed.flag_*`, when status is `"PASS"`)

* `sealed_inputs_digest : string`

  * Hex SHA-256 (or future hash) of the raw bytes of `sealed_inputs_5B` for this `manifest_fingerprint`, computed under a deterministic ordering contract (spelled out in the JSON-Schema description).

Implementations MAY add additional optional fields (e.g. `environment`, `build_id`, or per-role row counts), but MUST NOT remove or relax the above **required** fields without bumping the 5B spec version and corresponding schema version.

**Cardinality & PK:**

* Exactly **one row per `manifest_fingerprint`** and `run_id` in the world; dictionary SHOULD mark this dataset as **non-partitioned table** or a single JSON object, partitioned only by `fingerprint` (see §5.2).
* Primary key at schema level: `manifest_fingerprint` (and, if multi-run is allowed, `run_id`).

---

### 5.2 `sealed_inputs_5B` — schema anchor & shape

**Dataset ID (dictionary):**

* `id`: `sealed_inputs_5B`
* `owner_segment`: `5B`
* `layer`: `2`

**Schema anchor:**

* `schema_ref`: `schemas.5B.yaml#/validation/sealed_inputs_5B`

**Logical shape (minimum fields):**

`sealed_inputs_5B` is a **tabular dataset**; each row describes a single artefact that 5B is allowed to use for a given `manifest_fingerprint`. The schema MUST provide at least:

* `manifest_fingerprint : string`

* `parameter_hash : string | null`

  * `null` or omitted when the artefact is fingerprint-only (e.g. a validation bundle).

* `owner_segment : string`

  * Segment which owns the artefact (`"1A"`, `"1B"`, `"2A"`, `"2B"`, `"3A"`, `"3B"`, `"5A"`, `"5B"`, or shared).

* `artifact_id : string`

  * Logical artefact ID as used in the relevant artefact registry (e.g. `mlr.2A.validation_bundle`, `mlr.5A.merchant_zone_scenario_local`).

* `role : string`

  * Controlled vocabulary: `DATASET`, `CONFIG`, `POLICY`, `VALIDATION_BUNDLE`, `FLAG`, `LOG`, etc.

* `schema_ref : string`

  * JSON-Schema `$ref` into the owning schema pack.

* `path_template : string`

  * Canonical path template from the dataset dictionary or registry, including partition tokens (e.g. `data/layer2/5A/merchant_zone_scenario_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/`).

* `partition_keys : array<string>`

  * Ordered list of partition key names that appear in the path template.

* `sha256_hex : string`

  * Content digest of the artefact (or index/bundle digest, as appropriate to its role), as computed or imported from upstream sealed-inputs.

* `status : string`

  * `REQUIRED`, `OPTIONAL`, `INTERNAL`, or `IGNORED` (semantic as per §3.3).

* `read_scope : string`

  * `METADATA_ONLY` or `ROW_LEVEL`, as per §3.3.

Optionally, the schema MAY include:

* `notes : string`
* `last_seen_utc : string` (RFC3339 micros)
* `source_dict_id : string` (which dictionary/registry supplied this entry)

but these fields MUST NOT be required for correctness.

**Cardinality & PK:**

* Partition domain: all rows for a given `manifest_fingerprint` MUST be stored together (see §5.3).
* Recommended primary key: composite of
  `(manifest_fingerprint, owner_segment, artifact_id)`
  plus, if necessary, a disambiguating `role` field.

---

### 5.3 Partitioning, path templates & dictionary links

The 5B dataset dictionary MUST register the S5 outputs as follows (in YAML or equivalent):

#### 5.3.1 `s0_gate_receipt_5B` entry

* `id`: `s0_gate_receipt_5B`

* `schema_ref`: `schemas.5B.yaml#/validation/s0_gate_receipt_5B`

* `format`: `json` (one object)

* `path`:

  ```text
  data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
  ```

* `partitioning`:

  ```yaml
  partition_keys:
    - manifest_fingerprint
  ```

* `version`: `{manifest_fingerprint}`

* `final_in_segment`: `false` (the final HashGate will live in the 5B validation bundle)

* `lifecycle.phase`: `alpha` / `beta` / `prod` as appropriate.

#### 5.3.2 `sealed_inputs_5B` entry

* `id`: `sealed_inputs_5B`

* `schema_ref`: `schemas.5B.yaml#/validation/sealed_inputs_5B`

* `format`: `parquet`

* `path`:

  ```text
  data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
  ```

* `partitioning`:

  ```yaml
  partition_keys:
    - manifest_fingerprint
  ```

* `version`: `{manifest_fingerprint}`

* `final_in_segment`: `false`

* `lifecycle.phase`: aligned with 5B’s current maturity.

The artefact registry for 5B MUST then:

* register `s0_gate_receipt_5B` and `sealed_inputs_5B` as artefacts of `type: dataset`, `category: control` or `validation`,
* associate them with manifest keys such as:

  * `mlr.5B.control.s0_gate_receipt`,
  * `mlr.5B.control.sealed_inputs`,
* declare their dependency on:

  * upstream segment PASS flags (`mlr.1A.validation_bundle`, …, `mlr.5A.validation_bundle`), and
  * the relevant 5B config/policy artefacts (arrival process config, 5B RNG policy, 5B validation policy).

Once these registrations are in place, **all discovery of the S5 outputs** by downstream tooling MUST go via the dataset dictionary and artefact registry; no alternative path conventions or ad-hoc locations are permitted.

---

## 6. Deterministic algorithm (RNG-free control plane) *(Binding)*

This section defines the **exact steps** 5B.S0 MUST follow. The algorithm is **purely deterministic** and **RNG-free**: it never consumes Philox, never emits RNG events, and only reads metadata or sealed-input manifests.

For brevity, write:

* `mf := manifest_fingerprint`
* `ph := parameter_hash`
* `sid_set := scenario_set_5B` (from §2)

---

### 6.1 General constraints

1. **Catalogue-only resolution**

   5B.S0 MUST resolve all artefacts via:

   * Layer-1/Layer-2 dataset dictionaries,
   * Artefact registries for 1A–3B, 5A, 5B, and
   * Any upstream `sealed_inputs_*` tables,

   and MUST NOT construct filesystem paths or URLs by hand.

2. **Metadata-only data-plane access**

   5B.S0 MUST NOT read or interpret **rows** from any data-plane tables (e.g. `site_locations`, `merchant_zone_scenario_local_5A`). It MAY inspect:

   * existence,
   * file size, and
   * raw bytes for hashing,

   as required to verify upstream bundles.

3. **Idempotency**

   Re-running 5B.S0 with the same `(ph, mf, seed, run_id, sid_set)` and unchanged catalogue MUST yield **byte-identical** outputs for:

   * `s0_gate_receipt_5B` and
   * `sealed_inputs_5B`.

---

### 6.2 Step 0 — Load run identity & basic config

Given an engine run context, the state MUST:

1. Read and fix:

   * `ph`
   * `mf`
   * `seed`
   * `run_id`
   * `sid_set` (non-empty set of `scenario_id` values)

2. Validate:

   * `sid_set` is a subset of the `scenario_id` values present in the 5A scenario manifest for `(ph, mf)` (catalogue-level check only).
   * All identifiers are non-empty and syntactically valid (per Layer-2 identity rules).

If this validation fails, the state MUST terminate with a **run-identity precondition** error.

---

### 6.3 Step 1 — Verify upstream segment gates

Let `UPSTREAM_REQUIRED = {1A, 1B, 2A, 2B, 3A, 3B, 5A}`.

For each segment `seg ∈ UPSTREAM_REQUIRED`:

1. **Locate** the segment’s validation bundle and flag for `mf` via its dataset dictionary / artefact registry.

2. **Parse flag**

   * Read `_passed.flag_seg` as raw bytes.
   * Parse according to that segment’s spec (e.g. a single `sha256_hex` line).

3. **Recompute bundle digest**

   * Read the segment’s bundle index (e.g. `index.json` or equivalent) and any additional files that its spec requires to be hashed.
   * Recompute the digest using that segment’s declared hashing law (e.g. ASCII-lex ordering of paths, concatenation of raw bytes, then SHA-256).
   * Compare the recomputed digest with the value in `_passed.flag_seg`.

4. **Set status**

   * If all checks succeed, record in an in-memory map:

     ```text
     upstream_segments[seg] = {
       status = "PASS",
       spec_version = <from registry>,
       bundle_digest = <from flag>
     }
     ```

   * If any check fails (bundle missing, flag missing, parse error, digest mismatch), record:

     ```text
     upstream_segments[seg] = {
       status = "FAIL" or "MISSING",
       spec_version = <from registry if known>,
       bundle_digest = null
     }
     ```

After all segments are processed:

* If any `upstream_segments[seg].status ≠ "PASS"`, the state MUST:

  * NOT write `s0_gate_receipt_5B` or `sealed_inputs_5B`, and
  * terminate with a canonical **upstream-gate-failed** error.

* Otherwise, proceed to Step 2.

---

### 6.4 Step 2 — Discover candidate inputs for 5B

Using the 5B dataset dictionary and artefact registry (plus cross-segment references), 5B.S0 MUST construct an **in-memory list of candidate artefacts** that 5B may need.

Candidate classes:

1. **Upstream “world” artefacts** (all `METADATA_ONLY` for S5):

   * 1B: `site_locations` (by dataset ID).
   * 2A: `site_timezones`, `tz_timetable_cache`.
   * 2B: `s1_site_weights`, `s2_alias_blob`, `s2_alias_index`, `s3_day_effects`, `s4_group_weights`.
   * 3A: `zone_alloc`, `zone_alloc_universe_hash`.
   * 3B: `virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`, `edge_catalogue_index_3B`, `edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`, `virtual_routing_policy_3B`, `virtual_validation_contract_3B`.

2. **Upstream 5A artefacts**:

   * `scenario_manifest_5A`
   * `merchant_zone_profile_5A`
   * `shape_grid_definition_5A`
   * `class_zone_shape_5A`
   * `merchant_zone_baseline_local_5A`
   * `merchant_zone_scenario_local_5A`
   * Optional surfaces explicitly flagged in the 5B spec as usable by 5B.

3. **5B-local config/policy artefacts**:

   * arrival-process / LGCP config,
   * 5B RNG policy,
   * 5B validation policy,
   * any other 5B configs referenced by 5B state specs.

For each candidate logical artefact:

* Resolve its **dataset or config entry** via dictionary/registry:

  * `owner_segment`
  * `artifact_id`
  * `schema_ref`
  * `path_template`
  * `partition_keys`
  * `role` (`DATASET`, `CONFIG`, `POLICY`, `VALIDATION_BUNDLE`, etc.)

* Decide a preliminary `status` and `read_scope` for 5B:

  * `status`:

    * `REQUIRED` for artefacts that later 5B states MUST have (e.g. 5A λ surfaces for `sid_set`, 5B configs).
    * `OPTIONAL` for artefacts that may or may not be present but do not block 5B (e.g. optional overlays).
    * `INTERNAL` for 5B-only control artefacts that never leave the segment.
  * `read_scope`:

    * `METADATA_ONLY` for all upstream data-plane tables in 5B.S0.
    * `ROW_LEVEL` only for upstream sealed-inputs tables and for 5B-local configs that are stored as small, schema-governed rows.

This step builds an in-memory candidate list; it MUST NOT yet write any outputs.

---

### 6.5 Step 3 — Resolve digests & build `sealed_inputs_5B` rows

For each candidate artefact in the in-memory list:

1. **Determine digest source**

   * If the artefact appears in an upstream `sealed_inputs_*` table (e.g. `sealed_inputs_2A`, `sealed_inputs_2B`, `sealed_inputs_3A`, `sealed_inputs_3B`, `sealed_inputs_5A`), 5B.S0 SHOULD:

     * locate that upstream sealed-inputs table via catalogue,
     * read the relevant rows at row level,
     * take `sha256_hex` (or equivalent) from there.

   * Otherwise, compute the digest directly:

     * if a bundle/index: hash according to that artefact’s spec (e.g. validation bundle rules), or
     * if a single-file config: hash raw bytes directly.

2. **Assemble row**

   Construct a row for `sealed_inputs_5B` with:

   * `manifest_fingerprint = mf`
   * `parameter_hash = ph` or `null` if the artefact is fingerprint-only by contract
   * `owner_segment`
   * `artifact_id`
   * `role`
   * `schema_ref`
   * `path_template`
   * `partition_keys`
   * `sha256_hex`
   * `status`
   * `read_scope`

3. **Append row**

   Add the row to an in-memory table `sealed_inputs_rows`.

After all candidates are processed:

* If any `REQUIRED` artefact could not be resolved or digested, the state MUST terminate with a **sealed-inputs incomplete** error and MUST NOT write outputs.
* Otherwise, proceed to Step 4.

---

### 6.6 Step 4 — Persist `sealed_inputs_5B` & compute digest

1. **Write `sealed_inputs_5B`**

   * Materialise `sealed_inputs_rows` to a Parquet (or agreed) file at:

     ```text
     data/layer2/5B/sealed_inputs/fingerprint=mf/sealed_inputs_5B.parquet
     ```

   * Enforce:

     * schema = `schemas.5B.yaml#/validation/sealed_inputs_5B`,
     * writer sort order: by `(owner_segment, artifact_id)` (or the PK you chose in §5),
     * partition key `manifest_fingerprint` embedded in rows matches `mf`.

   * The write MUST be atomic at file level (e.g. temp path + atomic move).

2. **Compute `sealed_inputs_digest`**

   * Read back the written file (raw bytes).
   * Compute `sealed_inputs_digest := sha256_hex(bytes)`; record this value in memory for Step 5.

---

### 6.7 Step 5 — Persist `s0_gate_receipt_5B`

Construct a single JSON object conforming to `schemas.5B.yaml#/validation/s0_gate_receipt_5B`:

* Required fields:

  * `manifest_fingerprint = mf`
  * `parameter_hash = ph`
  * `seed`
  * `run_id`
  * `scenario_set = sorted(sid_set)`
  * `created_utc = <current UTC timestamp>`
  * `upstream_segments = upstream_segments` map from Step 1
  * `sealed_inputs_digest = sealed_inputs_digest` from Step 4

* Write it as:

  ```text
  data/layer2/5B/s0_gate_receipt/fingerprint=mf/s0_gate_receipt_5B.json
  ```

ensuring:

* schema validation passes,
* the file is written atomically, and
* `manifest_fingerprint` in the JSON matches the partition key.

If a file already exists at that path:

* The implementation MAY:

  * treat the run as idempotent and verify that the on-disk object is byte-identical to the one it would write, or
  * treat it as a write conflict and fail with a **duplicate-receipt** error.

It MUST NOT silently overwrite a receipt with different content for the same `(ph, mf, seed, run_id)`.

---

### 6.8 Prohibited actions in S5

Throughout Steps 0–5, implementations of 5B.S0 MUST NOT:

* call or consume any RNG stream;
* emit any RNG events or modify RNG traces;
* read data-plane tables at row level (except upstream `sealed_inputs_*` tables and small 5B config tables);
* alter or rewrite upstream validation bundles or `_passed.flag_*` files;
* alter or rewrite any upstream `sealed_inputs_*` tables;
* widen the input universe beyond what is present in dictionaries/registries and upstream sealed manifests.

Within these constraints, the algorithm above fully defines the RNG-free control-plane behaviour of **5B.S0 — Gate & sealed inputs**.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S5’s datasets are keyed, partitioned, ordered and updated**. It’s binding on both the implementation and the catalogue.

S5 produces:

* `s0_gate_receipt_5B` — one control object per closed world
* `sealed_inputs_5B` — one inventory table per closed world

where “closed world” is defined by `(parameter_hash, manifest_fingerprint)`.

---

### 7.1 Identity scopes

There are two relevant identity scopes:

1. **World identity (closed world)**

   * Defined by `(parameter_hash, manifest_fingerprint)`.
   * Determines **which artefacts exist in the world** and may appear in `sealed_inputs_5B`.
   * `sealed_inputs_5B` is keyed by this world identity only; it is **independent of `seed` and `run_id`**.

2. **Run identity (gate receipt)**

   * Defined in §2 as `run_identity_5B := (parameter_hash, manifest_fingerprint, seed, run_id)` plus `scenario_set_5B`.
   * Determines **who is doing the sealing** and under which RNG seed, but does not change the world.

Binding rules:

* `sealed_inputs_5B` MUST depend only on `(parameter_hash, manifest_fingerprint)`; running 5B with a different `seed` for the same `(ph, mf)` MUST produce a **byte-identical** `sealed_inputs_5B`.
* `s0_gate_receipt_5B` MUST embed the full `run_identity_5B` (including `seed` and `run_id`), but its **path and partition key** are still keyed by `manifest_fingerprint` alone.

---

### 7.2 Partitioning & path law

The partitioning law for S5 outputs is:

* **Partition key:** `manifest_fingerprint`
* **Path token:** `fingerprint={manifest_fingerprint}`

Concretely:

* `s0_gate_receipt_5B`:

  ```text
  data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
  ```

* `sealed_inputs_5B`:

  ```text
  data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
  ```

Binding constraints:

1. **Path ↔ embed equality**

   * For every row in `sealed_inputs_5B`:

     * the `manifest_fingerprint` column MUST equal the `manifest_fingerprint` implied by the `fingerprint=…` partition directory.
   * For the `s0_gate_receipt_5B` JSON object:

     * the `manifest_fingerprint` field in the JSON MUST equal the value in the path token.

2. **Single world per directory**

   * Each `fingerprint={mf}` directory for S5 outputs MUST contain artefacts **only** for that `mf`.
   * It MUST NOT contain rows or files belonging to any other `manifest_fingerprint`.

3. **No seed/parameter-based sub-partitions**

   * `seed` and `parameter_hash` MUST NOT appear as additional partition tokens for these two datasets.
   * `parameter_hash` MUST be carried in-row (for both datasets).
   * `seed` and `run_id` MUST be carried in-row for `s0_gate_receipt_5B`.

---

### 7.3 Primary keys & writer ordering

**`sealed_inputs_5B`**

* **Logical key:**

  ```text
  (manifest_fingerprint, owner_segment, artifact_id, role)
  ```

  (If `role` is not needed for uniqueness, it MAY be omitted from the PK, but the combination MUST be unique per row.)

* **Writer sort order:**
  Implementations MUST write `sealed_inputs_5B` sorted lexicographically by:

  ```text
  owner_segment, artifact_id, role
  ```

  with `manifest_fingerprint` constant within the file.

  This guarantees:

  * deterministic row order for hashing (`sha256_hex` of the file), and
  * stable diffs when the sealed input universe evolves between manifests.

**`s0_gate_receipt_5B`**

* Single JSON object per `(manifest_fingerprint)`; no in-table ordering required.
* If multi-run receipts are allowed, the logical key becomes `(manifest_fingerprint, run_id)`, but this MUST be explicit in the schema and dictionary.

---

### 7.4 Merge & overwrite discipline

**For `sealed_inputs_5B`:**

* For a given `(parameter_hash, manifest_fingerprint)`:

  * there MUST be **exactly one** `sealed_inputs_5B` file in `fingerprint={mf}`;
  * it MUST describe the full closed world for 5B at that `(ph, mf)`.

* Re-running S5 under a different `seed` or `run_id` but the same `(ph, mf)` MUST either:

  * not attempt to rewrite `sealed_inputs_5B`, or
  * rewrite it with **byte-identical** contents.

* Engines MUST NOT “merge” multiple partial inventories for the same `mf` (e.g. one per scenario or per seed). Closed world is **all-or-nothing**.

**For `s0_gate_receipt_5B`:**

* For a given `(manifest_fingerprint, run_id)`:

  * at most one `s0_gate_receipt_5B.json` MAY exist;
  * re-running S5 for the same `(ph, mf, seed, run_id, sid_set)` MUST either:

    * produce a byte-identical receipt, or
    * fail with a “duplicate receipt” error.

* If the engine allows multiple `run_id` values per `mf`, each MUST produce a separate receipt in the same `fingerprint={mf}` directory, but all receipts MUST point to the **same** `sealed_inputs_5B` digest for that `mf`.

**No cross-fingerprint merges**

* An implementation MUST NEVER attempt to merge or diff `sealed_inputs_5B` across different `manifest_fingerprint` values.
  Comparing worlds is a higher-level concern, outside this state.

---

### 7.5 Downstream consumption discipline

Downstream 5B states (S1+) MUST follow these identity/merge rules:

1. **World selection by `manifest_fingerprint`**

   * To determine “which world” they are operating in, S1+ MUST:

     * choose a single `manifest_fingerprint`,
     * read the corresponding `s0_gate_receipt_5B` in `fingerprint={mf}`,
     * read the single `sealed_inputs_5B` in the same directory.

   * They MUST NOT try to synthesise a world from multiple fingerprints or from multiple sealed-input tables.

2. **No local consolidation**

   * If S1+ states need to join multiple artefacts (e.g. 5A λ surfaces, 2B routing, 3B virtual overlay), they MUST do so using the identities and paths recorded in `sealed_inputs_5B`, not by scanning dictionary/registry again.

3. **No widening of the sealed world**

   * If a downstream state finds that it needs an artefact not present in `sealed_inputs_5B` for that `mf`, it MUST fail with a configuration error and MUST NOT silently start reading that artefact anyway.

With these rules, S5’s datasets have:

* a **clear identity** (`(ph, mf)` for the world, `run_id` for the receipt),
* a **simple partition law** (one partition per `mf`),
* a **stable writer order** for deterministic hashing, and
* a **strict merge discipline** that keeps the 5B closed world well-defined and reproducible.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines when **5B.S0 — Gate & sealed inputs** is considered **PASS** vs **FAIL**, and what that implies for all downstream 5B states (S1+). The conditions here are *in addition* to the algorithm in §6 and the identity rules in §7.

---

### 8.1 Local PASS criteria for 5B.S0

For a given `(parameter_hash = ph, manifest_fingerprint = mf, seed, run_id, scenario_set_5B)`, the S5 run MUST be considered **PASS** if and only if **all** of the following hold:

1. **Upstream gates re-verified**

   For every upstream segment in the required set `{1A, 1B, 2A, 2B, 3A, 3B, 5A}`:

   * The segment’s validation bundle for `mf` was located via catalogue.
   * Its `_passed.flag_*` was read and parsed successfully.
   * The digest in the flag exactly matched a recomputation of the bundle digest using that segment’s own hashing law.
   * The in-memory `upstream_segments[seg].status` is `"PASS"`.

2. **`sealed_inputs_5B` materialised and valid**

   * Exactly one file exists at:

     ```text
     data/layer2/5B/sealed_inputs/fingerprint=mf/sealed_inputs_5B.parquet
     ```

   * The file:

     * is readable and schema-valid against `schemas.5B.yaml#/validation/sealed_inputs_5B`,
     * contains at least one row,
     * has **no duplicate** `(manifest_fingerprint, owner_segment, artifact_id, role)` combinations,
     * has `manifest_fingerprint == mf` for all rows,
     * has no `REQUIRED` artefacts missing (i.e. all `REQUIRED` logical artefacts resolved during Step 3 of §6 are present as rows),
     * uses only recognised `role`, `status` and `read_scope` values (per §3.3).

   * The digest `sealed_inputs_digest` recomputed from this file (raw bytes) matches the value that will be written into `s0_gate_receipt_5B`.

3. **`s0_gate_receipt_5B` materialised and valid**

   * Exactly one file exists at:

     ```text
     data/layer2/5B/s0_gate_receipt/fingerprint=mf/s0_gate_receipt_5B.json
     ```

   * The JSON object:

     * is schema-valid against `schemas.5B.yaml#/validation/s0_gate_receipt_5B`,
     * has `manifest_fingerprint == mf`,
     * has `parameter_hash == ph`,
     * has `scenario_set` equal (as a set) to `scenario_set_5B` fixed in §2,
     * has `upstream_segments[seg].status == "PASS"` for every required segment `seg`,
     * has `sealed_inputs_digest` equal to the recomputed digest of `sealed_inputs_5B` for `mf`.

4. **Internal consistency**

   * The pair `(s0_gate_receipt_5B, sealed_inputs_5B)` is consistent:

     * every `owner_segment` referenced in `sealed_inputs_5B` is recognised and allowed by the 5B spec,
     * all 5B-local configs/policies required by later 5B states appear as `REQUIRED` or `INTERNAL` rows in `sealed_inputs_5B`,
     * there is no row with `status = IGNORED` that later 5B state specs declare as required.

If all four conditions above hold, the S5 run is **locally PASS** and its outputs MAY be used by downstream 5B states.

---

### 8.2 Local FAIL criteria for 5B.S0

The S5 run MUST be considered **FAIL** if **any** of the following occurs:

1. At least one required upstream segment has `upstream_segments[seg].status ≠ "PASS"` after Step 1 in §6.

2. The state cannot materialise `sealed_inputs_5B` for `mf`, or the file:

   * fails schema validation,
   * is empty,
   * is missing one or more `REQUIRED` artefacts,
   * has duplicate logical keys, or
   * uses invalid `role`, `status` or `read_scope` values.

3. The state cannot materialise a valid `s0_gate_receipt_5B` for `mf`, or:

   * the JSON fails schema validation,
   * embedded identity fields (`manifest_fingerprint`, `parameter_hash`, `scenario_set`) do not match the run context, or
   * the embedded `sealed_inputs_digest` does not match the recomputed digest of `sealed_inputs_5B`.

4. Any write operation for `sealed_inputs_5B` or `s0_gate_receipt_5B` fails in a way that might leave partial or conflicting outputs on disk (e.g. non-atomic overwrite, partial file).

On **FAIL**, the implementation MUST:

* log or report a clear error code and reason (e.g. `UPSTREAM_GATE_MISSING`, `SEALED_INPUTS_INCOMPLETE`, `GATE_RECEIPT_MISMATCH`), and
* MUST NOT leave a situation where:

  * `s0_gate_receipt_5B` exists but `sealed_inputs_5B` does not, or
  * `sealed_inputs_5B` exists but no valid `s0_gate_receipt_5B` points at it.

If such a partial state is detected (e.g. from a previous failed attempt), a subsequent S5 run MUST treat it as a failure and either repair it by writing a consistent pair atomically or abort before any downstream 5B state is invoked.

---

### 8.3 Gating obligations for 5B.S0 itself

5B.S0 MUST enforce the following gates *before* declaring local PASS:

1. **Upstream segment gate**

   * No consumption of upstream data-plane artefacts (even at metadata level) is permitted until:

     * all required upstream `_passed.flag_*` artefacts have been successfully re-verified for `mf`, and
     * `upstream_segments[seg].status == "PASS"` for every required `seg`.

2. **Closed-world completeness gate**

   * No `s0_gate_receipt_5B` may be written until a complete, schema-valid `sealed_inputs_5B` file exists for `mf` and its digest has been recomputed.

3. **Idempotence gate**

   * If `sealed_inputs_5B` and/or `s0_gate_receipt_5B` already exist for `mf`:

     * either the implementation MUST verify they are byte-identical to what it would write and treat the run as idempotent, or
     * it MUST treat the situation as a conflict (duplicate run) and fail, without silently overwriting.

---

### 8.4 Gating obligations for downstream 5B states (S1+)

All later 5B states (S1, S2, S3, S4, and the terminal 5B validation state) MUST treat the local PASS/FAIL of S5 as a **hard gate**:

1. **Presence & validity checks**

   Before reading any upstream artefact or attempting to derive any arrival-related quantity, a 5B state MUST:

   * locate `s0_gate_receipt_5B` for `mf`,
   * validate it against its schema, and
   * locate and validate `sealed_inputs_5B` for `mf`, then
   * verify that the `sealed_inputs_digest` in the receipt matches a recomputed digest of `sealed_inputs_5B`.

   If any of these checks fail, the downstream state MUST fail fast and MUST NOT attempt to reconstruct its own notion of the sealed inputs.

2. **Respect for upstream statuses**

   * Downstream 5B states MUST treat `upstream_segments` from `s0_gate_receipt_5B` as authoritative.
   * If, in a future spec revision, 5B.S0 is extended to allow some segments to be `"MISSING"` or `"FAIL"` and still proceed, then each 5B state MUST explicitly define how it behaves in that case. In the current spec, S5 only passes if all required segments report `"PASS"`.

3. **Sealed-inputs whitelist**

   * Downstream 5B states MAY only read artefacts that appear as rows in `sealed_inputs_5B` with `status ∈ {REQUIRED, OPTIONAL, INTERNAL}`.
   * If a state needs an artefact not present in `sealed_inputs_5B`, it MUST NOT read it and MUST treat this as a configuration error (e.g. `SEALED_WORLD_VIOLATION`).

4. **No modification of S5 outputs**

   * No later 5B state may modify or overwrite `s0_gate_receipt_5B` or `sealed_inputs_5B` for any `mf`.
   * Any change to the sealed input universe MUST be driven by changes to dictionaries/registries/config and a new `(ph, mf)` manifest, followed by a fresh run of S5.

---

### 8.5 Obligations for external consumers (informative but binding for 5B)

While 5B.S0 is an internal gate for Segment 5B, its outputs are expected to be used by:

* the terminal 5B validation/HashGate state (to build the 5B-wide validation bundle), and
* orchestration tooling that decides whether 5B is allowed to run at all for a given world.

Such consumers MUST:

* treat absence or invalidity of `s0_gate_receipt_5B` / `sealed_inputs_5B` for `mf` as “5B not ready to run” for that world;
* refrain from invoking 5B modelling states (S1–S4) for `mf` until S5 local PASS has been established;
* never attempt to short-circuit S5 by synthesising their own closed world.

Under these acceptance criteria and gating obligations, 5B.S0 serves as a strict, deterministic entrance gate for Segment 5B: either the upstream world is fully green and the 5B closed world is sealed, or **no** 5B arrival realisation work is allowed to proceed.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section enumerates the **only** failure modes that 5B.S0 is allowed to surface, and the **canonical error codes** it MUST use. All of these are **fatal** for S5 (no partial success).

Error codes are namespaced as:

> `5B.S0.<CATEGORY>`

Downstream tooling and later 5B states MUST rely on these codes (not ad-hoc strings).

---

### 9.1 Error code catalogue

5B.S0 MUST use the following codes only (or a strict superset introduced in a future spec revision):

#### (A) Run identity / catalogue

1. **`5B.S0.RUN_IDENTITY_INVALID`**
   Raised when the run identity in §2 cannot be established or is inconsistent, for example:

   * missing or empty `parameter_hash`, `manifest_fingerprint`, `seed`, or `run_id`;
   * `scenario_set_5B` not a subset of 5A’s scenario manifest for `(ph, mf)`;
   * malformed IDs (wrong format, illegal characters).

2. **`5B.S0.CATALOGUE_INCOMPLETE`**
   Raised when required schema packs, dataset dictionaries or artefact registries are missing or inconsistent, e.g.:

   * a 5B dictionary entry references a non-existent schema anchor;
   * a required upstream dictionary or registry cannot be resolved;
   * the engine cannot perform catalogue lookups at all.

---

#### (B) Upstream gates

3. **`5B.S0.UPSTREAM_GATE_MISSING`**
   Raised when a required upstream segment (1A–3B or 5A) does not expose a validation bundle and/or `_passed.flag_*` for `mf` at the location indicated by its own dictionary/registry.

4. **`5B.S0.UPSTREAM_GATE_MISMATCH`**
   Raised when a required upstream segment exposes a validation bundle + flag for `mf`, but:

   * the flag cannot be parsed, or
   * recomputing the bundle digest does not match the value in `_passed.flag_*`.

In both cases, S5 MUST set `upstream_segments[seg].status = "FAIL" | "MISSING"` and MUST abort before attempting to construct `sealed_inputs_5B`.

---

#### (C) Sealed inputs construction

5. **`5B.S0.SEALED_INPUTS_INCOMPLETE`**
   Raised when S5 cannot construct a complete sealed-inputs table for `mf`, for example:

   * a `REQUIRED` artefact cannot be resolved via catalogue;
   * a `REQUIRED` artefact is missing from all upstream `sealed_inputs_*` tables and cannot be hashed directly;
   * a `REQUIRED` 5B config/policy artefact is missing.

6. **`5B.S0.SEALED_INPUTS_SCHEMA_INVALID`**
   Raised when the materialised `sealed_inputs_5B.parquet` fails validation against `schemas.5B.yaml#/validation/sealed_inputs_5B`, e.g.:

   * missing required columns;
   * invalid enum values in `role`, `status`, or `read_scope`.

7. **`5B.S0.SEALED_INPUTS_DUPLICATE_KEY`**
   Raised when `sealed_inputs_5B` contains duplicate logical keys:

   * same `(manifest_fingerprint, owner_segment, artifact_id, role)` appearing more than once.

---

#### (D) Gate receipt construction

8. **`5B.S0.GATE_RECEIPT_SCHEMA_INVALID`**
   Raised when the candidate `s0_gate_receipt_5B` object fails schema validation against `schemas.5B.yaml#/validation/s0_gate_receipt_5B`, e.g.:

   * missing required fields;
   * `scenario_set` inconsistent with the run’s `scenario_set_5B`;
   * `upstream_segments` missing a required segment.

9. **`5B.S0.GATE_RECEIPT_DIGEST_MISMATCH`**
   Raised when:

   * `sealed_inputs_5B` is written and hashed, but
   * the `sealed_inputs_digest` embedded in the on-disk `s0_gate_receipt_5B` does not match a recomputed digest of `sealed_inputs_5B`, or vice versa during a re-run.

---

#### (E) IO / idempotency

10. **`5B.S0.IO_WRITE_FAILED`**
    Raised when S5 fails to write `sealed_inputs_5B` or `s0_gate_receipt_5B` atomically, e.g.:

    * filesystem error;
    * permission error;
    * partial file detected after a failed write.

11. **`5B.S0.IO_WRITE_CONFLICT`**
    Raised when:

    * an existing `sealed_inputs_5B` or `s0_gate_receipt_5B` is found for `mf`, and
    * its contents are **not** byte-identical to what S5 would produce under the current `(ph, mf, seed, run_id, sid_set)`.

In this case S5 MUST NOT overwrite and MUST treat the situation as an idempotency/consistency violation.

---

### 9.2 Error payload & logging requirements

For any of the above errors, 5B.S0 MUST:

* emit the canonical `error_code` exactly as listed, and
* attach, at minimum, the following context in its run-report / log payload:

  * `parameter_hash`
  * `manifest_fingerprint`
  * `seed`
  * `run_id`
  * when applicable, the offending `segment_id` (for upstream errors) and `artifact_id` (for sealed-inputs errors).

The **human-readable message** is implementation-defined but SHOULD be concise and structured; consumers MUST key off `error_code`, not message text.

---

### 9.3 Behaviour on failure

For any non-recoverable error code above, S5 MUST:

1. **Abort before downstream work**

   * NOT write a partially valid combination of `sealed_inputs_5B` and `s0_gate_receipt_5B` (no “receipt without inventory” or vice versa).
   * NOT invoke any later 5B state (S1–S4) for the same `{ph, mf}`.

2. **Leave the world in one of two states**

   * Either **no S5 outputs** for `mf` exist (fresh failure), or
   * **both** `sealed_inputs_5B` and `s0_gate_receipt_5B` already exist and are known to be complete + self-consistent (idempotent re-run).

3. **Never “repair” upstream**

   * S5 MUST NOT attempt to modify or repair upstream validation bundles, flags, or sealed-inputs tables in response to any error; all upstream issues are simply reported via `5B.S0.UPSTREAM_*` codes.

---

### 9.4 Obligations for downstream & orchestration

Downstream 5B states and orchestration tooling MUST:

* treat any missing or invalid `s0_gate_receipt_5B` / `sealed_inputs_5B` for a given `mf` as equivalent to a **failed S5 run**, even if S5 was never invoked explicitly;
* surface the S5 `error_code` (if present) as the authoritative reason for why 5B cannot run in that world;
* never attempt to “work around” an S5 error by fabricating their own sealed inputs or reading artefacts outside `sealed_inputs_5B`.

Under these constraints, failure behaviour in 5B.S0 is:

* **finite and well-typed** (small, named set of codes), and
* **strictly gating** (any error means 5B cannot proceed for that world until the upstream cause is fixed and S5 is re-run).

---

## 10. Observability & run-report integration *(Binding)*

This section fixes **what 5B.S0 MUST emit for observability** and **how it integrates with the engine’s run-report system**. It does **not** introduce new datasets beyond those already defined; it binds how S5 reports its work.

---

### 10.1 Run-report event for 5B.S0

For every attempted invocation of 5B.S0 on a given `(parameter_hash = ph, manifest_fingerprint = mf, seed, run_id)`, the engine MUST emit a **single run-report record** for this state, with at least:

* `state_id = "5B.S0"`
* `parameter_hash = ph`
* `manifest_fingerprint = mf`
* `seed`
* `run_id`
* `scenario_set = sorted(scenario_set_5B)`
* `status ∈ {"PASS","FAIL"}`
* `error_code` (one of §9, or `null` if `status = "PASS"`)
* `started_at_utc`
* `finished_at_utc`

This record MAY live in a shared Layer-2 run-report dataset (e.g. `run_report_layer2`) but MUST be schema-governed elsewhere. 5B.S0 MUST provide these fields to the run-report subsystem; the storage details are outside this spec.

---

### 10.2 Minimum metrics & counters

The run-report record for 5B.S0 MUST include, at minimum, the following **metrics**, captured at the end of the run:

1. **Upstream gate summary**

   * `upstream_total = |{1A,1B,2A,2B,3A,3B,5A}|` (typically 7)
   * `upstream_pass_count`
   * `upstream_fail_count`
   * `upstream_missing_count`

   These MUST be consistent with the `upstream_segments` map written into `s0_gate_receipt_5B`.

2. **Sealed-inputs inventory summary**

   From the committed `sealed_inputs_5B`:

   * `sealed_inputs_row_count_total`
   * `sealed_inputs_row_count_required`
   * `sealed_inputs_row_count_optional`
   * `sealed_inputs_row_count_internal`
   * `sealed_inputs_row_count_ignored`

3. **Artefact-class counts (optional but recommended)**

   If cheap to compute, the run-report SHOULD include:

   * `sealed_inputs_count_dataset` (rows where `role = DATASET`)
   * `sealed_inputs_count_config` (rows where `role = CONFIG` or `POLICY`)
   * `sealed_inputs_count_validation` (rows where `role = VALIDATION_BUNDLE` or `FLAG`)

These metrics are **binding** in the sense that:

* on `status = "PASS"`, they MUST reflect the final committed `sealed_inputs_5B` and `s0_gate_receipt_5B`;
* on `status = "FAIL"`, they MUST reflect whatever partial state was reached (or zero if failure occurred before any inventory was constructed).

---

### 10.3 Logging of upstream status map

In addition to the run-report event, 5B.S0 MUST log the **upstream_segments** map (seg → `{status,spec_version,bundle_digest}`) in a machine-readable form suitable for debugging. This MAY be:

* embedded into the generic run-report `details`/`payload` field, or
* emitted as a separate structured log event.

Binding requirements:

* For `status = "PASS"`, the logged upstream_segments MUST be bit-wise consistent with the map embedded in `s0_gate_receipt_5B`.
* For `status = "FAIL"`, if failure was due to an upstream gate error, the log payload MUST identify at least:

  * the offending `segment_id`, and
  * which condition failed (missing bundle, missing flag, digest mismatch).

---

### 10.4 Sealed-inputs digest visibility

The value of `sealed_inputs_digest` MUST be visible in **both**:

* the `s0_gate_receipt_5B` object, and
* the 5B.S0 run-report record (either as a dedicated field like `sealed_inputs_digest` or inside a structured `details` object).

This ensures:

* operators can correlate a run-report with the exact inventory file without re-reading disk, and
* the Layer-2 / segment-level HashGate state (for 5B as a whole) can reference S5’s digest when building its own validation bundle.

---

### 10.5 Error reporting behaviour

On any failure with one of the error codes from §9:

* 5B.S0 MUST still emit a run-report record for the attempt, with:

  * `status = "FAIL"`,
  * `error_code` set to the canonical value, and
  * metrics filled as far as the state progressed (zero or `null` where not applicable).
* The state MUST NOT write or update `s0_gate_receipt_5B` or `sealed_inputs_5B` after logging a `FAIL`.

Downstream systems (orchestration, dashboards) MUST key off `status` and `error_code` in the run-report; they MUST NOT infer S5 success from the mere presence of files in the filesystem.

---

### 10.6 No RNG / data-plane telemetry

Because 5B.S0 is **RNG-free** and does not perform row-level data-plane work, it:

* MUST NOT emit RNG-related metrics (streams, draws, counters), and
* MUST NOT sample or log data-plane rows for observability.

All RNG observability for 5B is owned by the later RNG-bearing states (S2–S4) and by the final 5B validation/HashGate state.

Within these constraints, 5B.S0’s observability obligations are limited to:

* emitting a **single, well-formed run-report event** per attempt,
* summarising upstream gates and the sealed-inputs inventory, and
* exposing the sealed-inputs digest and upstream status map for higher-level monitoring and debugging.

---

## 11. Performance & scalability *(Informative)*

This section describes **expected scale and performance characteristics** of 5B.S0. It explains how the state should behave under realistic loads, but does *not* add new binding constraints beyond §§1–10.

---

### 11.1 Workload shape

5B.S0 is a **metadata-only** state:

* It touches:

  * a **small, fixed set of upstream bundles & flags** (1A–3B, 5A),
  * a **small to moderate** number of artefacts in `sealed_inputs_5B` (configs, policies, several dozen–few hundred datasets/logs),
* It does **no row-level scans** of large data-plane tables.

Expected complexity:

* Runtime is **O(#artefacts in sealed_inputs_5B)** for dictionary/registry lookups + digest resolution.
* Bundle re-hashing cost is **O(bundle-size)**, but bounded by the (small) size of validation bundles, not massive fact tables.

In other words: even at large overall engine scales, S5 remains “cheap” relative to data-plane states.

---

### 11.2 Latency expectations

Implementations SHOULD aim for:

* **Low, predictable latency**, dominated by:

  * reading ~7 upstream validation bundles + flags, and
  * writing a single Parquet file (`sealed_inputs_5B`) and a single JSON (`s0_gate_receipt_5B`).

Reasonable expectations:

* “Normal” runs: **sub-second to a few seconds** wall-clock, depending mainly on I/O.
* Fail-fast behaviour: if an upstream gate is missing or mismatched, S5 SHOULD detect this early (in Step 1 of §6) and exit quickly rather than walking the whole candidate artefact set.

---

### 11.3 Memory & I/O profile

Memory:

* The primary in-memory structure is `sealed_inputs_rows`:

  * one row per artefact; even with hundreds or a few thousand artefacts this is **tiny** compared to typical data-plane tables.
* No caching of bulk data: upstream bundles and configs SHOULD be streamed as needed and not held fully in memory unless they are themselves small.

I/O:

* S5 reads:

  * a small number of validation bundles + flags,
  * possibly upstream `sealed_inputs_*` tables (small), and
  * 5B config/policy artefacts.
* S5 writes:

  * exactly one Parquet file (`sealed_inputs_5B`),
  * exactly one JSON file (`s0_gate_receipt_5B`).

Implementations SHOULD:

* use streaming reads for bundle hashing,
* avoid unnecessary re-reads of the same bundle, and
* perform writes via temp locations + atomic renames.

---

### 11.4 Concurrency & scheduling

Because S5 is light and metadata-only:

* It can be scheduled **early** in a 5B run, and
* It is safe to run **serially per `(ph, mf)`** without being a bottleneck.

Recommended pattern:

* **One S5 per `(ph, mf)` world**:

  * S5 runs once, seals the closed world for that manifest,
  * multiple S1–S4 runs (different seeds, scenarios, or `run_id`s) can reuse the same `sealed_inputs_5B`.

If the orchestration allows concurrent S5 attempts for the same `(ph, mf)`:

* They SHOULD converge on the same outputs and treat non-identical writes as `IO_WRITE_CONFLICT` (per §9), not race to overwrite each other.

---

### 11.5 Degradation & failure modes

Performance-related trade-offs:

* On **large bundles**:
  re-hashing may be relatively expensive; implementers MAY cache per-bundle digest results across runs, as long as:

  * cache keys include `(segment_id, manifest_fingerprint, bundle_path, bundle_mtime, bundle_size)`, and
  * a digest mismatch always triggers a fresh recomputation.

* On **frequent failures** (e.g. upstream gates misconfigured):
  S5 SHOULD fail fast after Step 1, without attempting to build or write `sealed_inputs_5B`.

In general, if S5 becomes a visible bottleneck, it is a signal that:

* validation bundles are too large or over-stuffed with data-plane content, or
* repeated, redundant runs are happening for the same `(ph, mf)` that should instead be reusing an existing sealed world.

Those are catalogue/architecture issues rather than something 5B.S0 itself should try to solve.

---

## 12. Change control & compatibility *(Binding)*

This section fixes **how 5B.S0 can evolve** without breaking the rest of Segment 5B, and when a **spec / schema version bump is required**. It is binding on:

* the 5B state spec for S5,
* `schemas.5B.yaml` anchors for `s0_gate_receipt_5B` and `sealed_inputs_5B`,
* the Layer-2 / 5B dataset dictionary and artefact registry, and
* any downstream 5B state that consumes S5 outputs.

---

### 12.1 Version signalling (what must carry a version)

The following MUST carry a **5B segment-spec version** (e.g. `5B_spec_version`) and treat it as part of their contract:

* `s0_gate_receipt_5B`

  * MUST include a field (name to be fixed in the schema, e.g. `segment_spec_version`) set to a semantic version string, e.g. `"5B-1.0.0"`.

* The 5B dataset dictionary entry for `s0_gate_receipt_5B` and `sealed_inputs_5B`

  * MUST record the same `segment_spec_version` in metadata (e.g. `spec_version` field).

* The 5B artefact registry entry for the S5 artefacts

  * MUST include a `spec_version` (or equivalent) matching the value embedded in `s0_gate_receipt_5B`.

Downstream 5B states (S1+) MUST read this version and:

* either explicitly support it, or
* fail fast with a clear “unsupported spec version” error if they cannot.

---

### 12.2 Backwards-compatible changes (allowed without breaking consumers)

The following changes are considered **backwards-compatible** for S5 and MAY be made under a **minor** spec version bump (e.g. `5B-1.0.0 → 5B-1.1.0`), provided schemas and dictionaries are updated consistently:

1. **Additive schema changes**

   * Adding new **optional** fields to `s0_gate_receipt_5B` or `sealed_inputs_5B` with:

     * clear defaults for “old” semantics (e.g. `null` or omitted), and
     * no change in meaning of existing fields.
   * Adding new allowed values to `role`, `status`, or `read_scope` *as long as*:

     * they are not used for artefacts that existing downstream states rely on, or
     * downstream states treat unknown values conservatively (e.g. as `IGNORED`).

2. **Adding new rows to `sealed_inputs_5B`**

   * Introducing additional artefacts (datasets/configs/policies) as new rows, with:

     * `status = OPTIONAL` or `INTERNAL`, and
     * `read_scope` chosen so that older 5B states can safely ignore them.
   * Existing rows MUST NOT be removed or have their semantics changed.

3. **New error codes or metrics**

   * Adding new `5B.S0.*` error codes that do not change the meaning of existing codes.
   * Adding new run-report metrics / fields, while keeping existing ones stable.

In all these cases, older consumers that only understand the “old” subset can continue to function; newer consumers can take advantage of the extra information.

---

### 12.3 Breaking changes (require new major spec / anchor)

The following changes are **breaking** and MUST NOT be made under the same `segment_spec_version`. They require:

* a new **major** spec version (e.g. `5B-2.0.0`), and
* either:

  * new schema anchors, or
  * a clearly documented migration plan and explicit version gating in downstream states.

Breaking changes include:

1. **Schema shape changes that alter existing fields**

   * Renaming or removing existing fields in `s0_gate_receipt_5B` or `sealed_inputs_5B`.
   * Changing types or semantics of existing fields (e.g. turning a free-form string into an enum with a different meaning).
   * Changing the primary key or partitioning law for S5 datasets (e.g. introducing `seed` as a partition key).

2. **Changing closed-world semantics**

   * Altering the meaning of `status` such that existing values (`REQUIRED`, `OPTIONAL`, `INTERNAL`, `IGNORED`) change behaviour.
   * Changing the “whitelist” rule (e.g. allowing 5B to read artefacts not present in `sealed_inputs_5B`).

3. **Relaxing or tightening upstream gate requirements**

   * Removing a segment from the required upstream gate set (e.g. allowing 5B to run without 3B PASS) **or** adding new mandatory upstream segments, without version signalling.
   * Changing how upstream bundle hashes are computed (e.g. new hashing law) without either:

     * a new spec version, or
     * explicit dual-mode support in S5.

4. **Changing world identity rules**

   * Introducing `seed` or `run_id` into the identity of `sealed_inputs_5B` (i.e. making it depend on more than `(ph, mf)`).
   * Changing the meaning of `parameter_hash` within S5 (e.g. making some 5B configs no longer parameter-scoped).

Whenever such changes are needed, they MUST be accompanied by:

* an update to `segment_spec_version` in `s0_gate_receipt_5B` and dictionary/registry metadata, and
* updated downstream 5B states that explicitly recognise and handle the new version.

---

### 12.4 Interactions with upstream / downstream versioning

**Upstream segments (1A–3B, 5A)**

* S5 treats upstream segments as **black-box providers** with their own spec versions and bundle laws.
* As long as:

  * their dictionaries/registries remain compatible, and
  * their bundles still expose `_passed.flag_*` with stable hashing semantics,
* S5 does not need a version bump when upstream segments change their internal specs.

If an upstream segment changes its validation bundle/flag format in a way that breaks S5’s ability to re-hash, then:

* either S5 must be updated to support both old and new upstream formats, or
* S5 must bump its own spec version and **explicitly require** the newer upstream versions.

**Downstream 5B states (S1+)**

* MUST treat `segment_spec_version` in `s0_gate_receipt_5B` as a gate:

  * If they do not recognise the version, they MUST fail fast (e.g. `5B.S1.UNSUPPORTED_SPEC_VERSION`) rather than guessing.
* MAY support multiple S5 spec versions concurrently (e.g. `5B-1.x` and `5B-2.x`), but this MUST be explicit in their own specs.

---

### 12.5 Migration principles

When evolving S5, implementers SHOULD:

* Prefer **additive** changes (new optional fields, new optional artefacts) over destructive ones.
* Keep the **world identity contract** stable: `sealed_inputs_5B` stays keyed solely by `(ph, mf)`.
* Avoid changes that force consumers to inspect the filesystem directly; all new behaviour should go via:

  * updated schemas,
  * updated dictionaries/registries, and
  * the `segment_spec_version` field.

In short:

> * Minor, additive enhancements to 5B.S0 are allowed under the same world identity and a bumped minor spec version.
> * Any change that alters the meaning of the sealed world, identity, or gating rules requires a new major spec version and explicit version gating in downstream 5B states.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the short-hands used in the **5B.S0 — Gate & sealed inputs** spec. It does **not** introduce new behaviour; it only explains notation.

---

### 13.1 Identities & keys

* **`ph`**
  Short for `parameter_hash`. Identifies the parameter pack (including 5B arrival/LGCP config, RNG policy, validation policy, etc.) in use for this world.

* **`mf`**
  Short for `manifest_fingerprint`. Identifies the closed world of artefacts (datasets + configs + bundles) that 5B.S0 is sealing.

* **`seed`**
  Global RNG seed for the engine run. Fixed for all RNG-bearing 5B states but **not** used directly in S5 (S5 is RNG-free).

* **`run_id`**
  Engine-level run identifier that distinguishes multiple invocations under the same `(ph, mf, seed)`.

* **`scenario_set_5B` / `sid_set`**
  The set of `scenario_id` values (from 5A) that this 5B run is allowed to materialise.

* **`run_identity_5B`**
  Tuple:
  `run_identity_5B := (parameter_hash, manifest_fingerprint, seed, run_id, scenario_set_5B)`
  Used for logging and receipts; **world identity** is `(ph, mf)`.

---

### 13.2 Datasets & artefacts (5B.S0)

* **`s0_gate_receipt_5B`**
  Fingerprint-scoped control dataset produced by S5, containing:

  * run identity,
  * upstream segment status map,
  * `scenario_set`,
  * and `sealed_inputs_digest`.

* **`sealed_inputs_5B`**
  Fingerprint-scoped table listing all artefacts 5B is allowed to read in this world, with:

  * `owner_segment`,
  * `artifact_id`,
  * `role`,
  * `schema_ref`,
  * `path_template`,
  * `sha256_hex`,
  * `status`,
  * and `read_scope`.

* **`sealed_inputs_digest`**
  SHA-256 (or successor) over the raw bytes of `sealed_inputs_5B` for `mf`. Stored in `s0_gate_receipt_5B` and the run-report.

---

### 13.3 Status & flags

* **`_passed.flag_*`**
  Upstream segment-level PASS flag (1A–3B, 5A) as defined in those segments’ specs. 5B.S0 re-hashes bundles to verify these flags.

* **`upstream_segments`**
  Map in `s0_gate_receipt_5B` from segment ID (`"1A"`, `"1B"`, `"2A"`, `"2B"`, `"3A"`, `"3B"`, `"5A"`) to:

  * `status ∈ {"PASS","FAIL","MISSING"}`,
  * `spec_version`,
  * `bundle_digest`.

* **`status` (in `sealed_inputs_5B`)**
  Per-artefact label:

  * `REQUIRED` — must exist; downstream 5B states depend on it.
  * `OPTIONAL` — may be absent; 5B can run without it.
  * `INTERNAL` — 5B-only control artefact, not meant for external consumers.
  * `IGNORED` — recorded for bookkeeping but MUST NOT be read by 5B.

* **`read_scope` (in `sealed_inputs_5B`)**

  * `METADATA_ONLY` — 5B may only inspect existence, size, and bytes for hashing; no row-level reads.
  * `ROW_LEVEL` — 5B states are allowed to read rows (e.g. upstream `sealed_inputs_*` manifests, 5B configs).

---

### 13.4 Roles & segments

* **`owner_segment`**
  The segment that **owns** an artefact, e.g.:

  * `"1A"`, `"1B"`, `"2A"`, `"2B"`, `"3A"`, `"3B"` — Layer-1 merchant/site/time/routing/zone/virtual segments.
  * `"5A"` — Layer-2 intensity engine.
  * `"5B"` — Layer-2 arrival realisation (this segment).

* **`role` (in `sealed_inputs_5B`)**
  High-level artefact type, e.g.:

  * `DATASET` — data-plane table or log in the lake.
  * `CONFIG` / `POLICY` — small configuration or policy object.
  * `VALIDATION_BUNDLE` — folder containing validation evidence.
  * `FLAG` — `_passed.flag_*` file.
  * `LOG` — structured log stream (if ever included in 5B’s world).

Exact enum values are governed by `schemas.5B.yaml`.

---

### 13.5 Error codes (summary)

All failure codes for S5 are prefixed:

> `5B.S0.`

Examples (see §9 for semantics):

* `5B.S0.RUN_IDENTITY_INVALID`
* `5B.S0.CATALOGUE_INCOMPLETE`
* `5B.S0.UPSTREAM_GATE_MISSING`
* `5B.S0.UPSTREAM_GATE_MISMATCH`
* `5B.S0.SEALED_INPUTS_INCOMPLETE`
* `5B.S0.SEALED_INPUTS_SCHEMA_INVALID`
* `5B.S0.SEALED_INPUTS_DUPLICATE_KEY`
* `5B.S0.GATE_RECEIPT_SCHEMA_INVALID`
* `5B.S0.GATE_RECEIPT_DIGEST_MISMATCH`
* `5B.S0.IO_WRITE_FAILED`
* `5B.S0.IO_WRITE_CONFLICT`

Downstream systems should treat `error_code` as the stable key, not any free-text message.

---

### 13.6 Miscellaneous shorthand

* **“World” / “closed world”**
  The set of artefacts (datasets, bundles, configs) reachable for a given `(ph, mf)` and recorded in `sealed_inputs_5B`.

* **“Upstream required segments”**
  The fixed set `{1A, 1B, 2A, 2B, 3A, 3B, 5A}` that S5 must re-verify via their own HashGates before sealing 5B’s world.

* **“Catalogue”**
  The combined abstraction of:

  * Layer-1/Layer-2 dataset dictionaries,
  * artefact registries, and
  * any upstream sealed-input manifest tables,

  used for discovery. S5 is not allowed to step outside this catalogue.

These symbols are for convenience only; the binding behaviour is defined in §§1–12.

---
