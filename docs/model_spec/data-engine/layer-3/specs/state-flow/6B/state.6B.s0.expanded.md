# 6B.S0 — Behavioural universe gate & sealed inputs (Layer-3 / Segment 6B)

## 1. Purpose & scope *(Binding)*

This state defines the **behavioural universe gate** for Layer-3 / Segment 6B.

6B.S0 is the *only* state in 6B that is allowed to decide whether the segment may run at all for a given `manifest_fingerprint`. Its job is to:

* Verify that the **world below 6B is sealed and trustworthy** (Layer-1, Layer-2 and 6A HashGates are all PASS for this fingerprint).
* Discover, via catalogues and upstream sealed-input manifests, **exactly which artefacts 6B is allowed to read**, and at what scope.
* Materialise a **sealed, fingerprint-scoped manifest** of those artefacts (`sealed_inputs_6B`), and a compact **gate receipt** (`s0_gate_receipt_6B`) that downstream states and external orchestrators can rely on.
* Do all of the above **without reading any data-plane rows** and **without consuming RNG**.

Once 6B.S0 has succeeded for a given `manifest_fingerprint` (and spec version), the rest of the 6B segment may treat the upstream engine as a **closed behavioural universe**:

* Arrivals are fixed and authoritative via **5B** (`arrival_events_5B`, gated by `_passed.flag`).
* The entity graph and static fraud posture are fixed and authoritative via **6A** (`s1…s5_*_6A`, gated by `_passed.flag`).
* Geometry, civil time, routing, zone allocation and virtual edges are fixed and authoritative via **Layer-1** segments (1A–3B).
* Scenario and intensity context are fixed and authoritative via **5A** (`merchant_zone_*_5A`, gated by `_passed.flag`).

6B.S0 does **not** design or simulate behaviour. It does not attach arrivals to entities, does not create flows, does not define campaigns, does not label transactions, and does not talk to the Philox engine. Those responsibilities belong to later states (6B.S1–S4). Instead, this state concerns itself solely with:

* **Trust**: are all required upstream HashGates present and valid for this fingerprint?
* **Contracts**: are 6B’s own schemas, dictionaries, registries and config packs present and self-consistent?
* **Inventory**: for this fingerprint, which upstream datasets, policy bundles and config artefacts are 6B allowed to read, and how do we describe them canonically?

The outputs of 6B.S0 are binding for the rest of the segment:

* Every later 6B state **MUST** check that a corresponding `s0_gate_receipt_6B` exists and is marked as PASS for its target `manifest_fingerprint` before it runs.
* Every later 6B state **MUST** treat `sealed_inputs_6B` as the **complete and exclusive list** of artefacts it may read. No state may reach “around” this manifest to ad-hoc paths, or to upstream datasets that are not explicitly listed.
* The eventual 6B segment HashGate (`validation_bundle_6B` + `_passed.flag`) **MUST** be computed under the assumption that S0 is the only authority on what 6B considered “in scope” for that fingerprint.

This specification for 6B.S0 is therefore limited in scope to:

* The **definition of the gate** (which upstream segments and artefact types are required; which are optional or ignored).
* The **identity and storage model** for `s0_gate_receipt_6B` and `sealed_inputs_6B`.
* The **high-level algorithm** S0 uses to verify upstream gates, interrogate catalogues, derive its sealed inventory and record its own receipt.
* The **obligations** S0 places on downstream 6B states and on orchestrators (no S1–S4 run unless S0 PASS; no read of artefacts not listed in `sealed_inputs_6B`).

It is explicitly *out of scope* for 6B.S0 to:

* Define or impose any behavioural logic on arrivals, flows, campaigns or labels.
* Redefine or reinterpret upstream semantics (e.g. arrival counts, civil time, routing, fraud roles).
* Perform any heavy data-plane analysis or validation beyond what upstream segments and the eventual 6B validation state will do.

If 6B.S0 is implemented as specified, then for each `manifest_fingerprint`:

* The behavioural segment 6B will have a **single, deterministic description** of “what world it ran against” and “what inputs it was allowed to see”.
* Later states (6B.S1–S4) and the 6B validation/HashGate state will be able to **rely on that description**, rather than rediscovering or guessing the environment.
* Orchestrators and external consumers will have a **clear, machine-readable gate** indicating whether 6B is in a valid position to generate and expose behavioural data for that world.

---

## 2. Preconditions & upstream gates *(Binding)*

This section defines **what must already be true** before 6B.S0 is allowed to run, and which upstream HashGates it is required to honour.

6B.S0 is **fingerprint-scoped**: every invocation is parameterised by a single `manifest_fingerprint`. All preconditions below apply *per fingerprint*.

---

### 2.1 Required upstream segments & HashGates

For a given `manifest_fingerprint`, 6B.S0 **MUST NOT** start unless the following segments have completed successfully and published their own validation bundles and PASS flags:

* **Layer-1** (world geometry, time, routing, virtual universe)

  * Segment 1A – Merchant→country outlet counts & HashGate
  * Segment 1B – Site placement & `site_locations` HashGate
  * Segment 2A – Civil time (`site_timezones`, `tz_timetable_cache`) HashGate
  * Segment 2B – Routing / alias & day-effect HashGate
  * Segment 3A – Zone allocation & `zone_alloc_universe_hash` HashGate
  * Segment 3B – Virtual merchants & CDN / edge universe HashGate

* **Layer-2** (intensity & arrivals)

  * Segment 5A – Intensity surfaces (`merchant_zone_*_5A`) HashGate
  * Segment 5B – Arrival skeleton (`arrival_events_5B`) HashGate

* **Layer-3** (static entities & posture)

  * Segment 6A – Entity graph & static fraud posture HashGate

For each of these segments, 6B.S0 **MUST**:

1. Locate the segment’s validation bundle directory and `_passed.flag` for the target `manifest_fingerprint` using the segment’s dataset dictionary and artefact registry (no hard-coded paths).
2. Recompute or otherwise verify the bundle digest according to that segment’s own hashing law (ASCII-lex index, SHA-256, etc.), rather than assuming correctness.
3. Treat any of the following as a **fatal precondition failure** for 6B.S0:

   * Missing validation bundle directory for a required segment.
   * Missing `_passed.flag` for a required segment.
   * Digest mismatch between `_passed.flag` and the evidence files listed in that segment’s index.
   * Segment’s own validation report indicating a non-PASS verdict for that fingerprint.

If any required upstream segment fails these checks, 6B.S0 **MUST** abort without producing `s0_gate_receipt_6B` or `sealed_inputs_6B`, and **no 6B state MAY run** for that `manifest_fingerprint`.

> As of this specification, *all* of the segments listed above are treated as **required**. Introducing optional dependencies or reduced-mode operation is a future-version change and is out of scope for 6B.S0 v1.

---

### 2.2 6B contract availability

Before 6B.S0 runs, the **Layer-3 / 6B contract set** for the active `6B_spec_version` **MUST** already be present and self-consistent in the catalogue. Concretely, 6B.S0 must be able to locate and validate:

* Layer-3 shared schema pack:

  * `schemas.layer3.yaml` (including the `gate/6B/*` and `validation/6B/*` schema anchors that S0 will use).
* 6B segment schema pack:

  * `schemas.6B.yaml` (even though S0 itself only uses layer-wide gate schemas, later S-states will rely on this pack and S0’s gate receipt must bind to a specific schema version).
* 6B dataset dictionary:

  * `dataset_dictionary.layer3.6B.yaml`, with entries for at least:

    * `s0_gate_receipt_6B`,
    * `sealed_inputs_6B`,
    * the eventual `validation_bundle_6B` and `validation_passed_flag_6B` artefacts.
* 6B artefact registry:

  * `artefact_registry_6B.yaml`, registering the same datasets/artefacts with consistent `schema`, `path_template`, `partitioning`, and `role` fields.

6B.S0 **MUST** validate, at minimum:

* That dictionary and registry both reference the same logical IDs for S0’s outputs.
* That the schema refs declared in dictionary/registry resolve into `schemas.layer3.yaml` / `schemas.6B.yaml`.
* That the declared partitioning and path templates for S0’s outputs are consistent with this specification (fingerprint-only partition, no extraneous keys).

If the 6B contract set is missing or inconsistent, S0 **MUST** fail with a contract-related error and refrain from writing any outputs.

---

### 2.3 Availability of upstream sealed-inputs manifests

Where upstream segments expose their own **sealed-inputs manifests** (e.g. `sealed_inputs_5B`, `sealed_inputs_6A`), 6B.S0 **SHOULD** treat those as the primary source for discovering:

* Which upstream artefacts exist for this `manifest_fingerprint`.
* Which of those artefacts are considered in scope for downstream consumers.
* How those artefacts are partitioned and where they are stored.

6B.S0 **MUST** ensure that:

* Required upstream sealed-inputs tables for 6B’s purposes (notably from 5B and 6A) are present and valid under their own schemas.
* The upstream sealed-inputs digests (where present) are consistent with the actual contents of those manifests.

If an upstream segment has published a PASS flag but its `sealed_inputs_*` manifest is missing or malformed in a way that prevents 6B from discovering required artefacts (e.g. arrivals for 5B, entity tables for 6A), S0 **MUST** treat this as a fatal precondition failure for 6B and abort.

---

### 2.4 Execution parameters & environment assumptions

6B.S0 assumes the following execution parameters and environment are already fixed and valid when it starts:

* A concrete `manifest_fingerprint` has been selected for the run, corresponding to a single, sealed world snapshot across Layers 1–3.
* A `parameter_hash` and `6B_spec_version` have been provided or inferred, such that:

  * The combination `(manifest_fingerprint, parameter_hash, 6B_spec_version)` uniquely identifies the intended 6B configuration.
  * The contract set described in §2.2 is compatible with this version triple.
* The engine has access to:

  * All relevant dictionaries and registries for Layers 1–3.
  * The underlying storage needed to read upstream bundles, flags and sealed-inputs manifests.

6B.S0 **MUST NOT** rely on any wall-clock time, environment-dependent random seeds, or ad-hoc configuration outside of the catalogued artefacts. Any such dependency would violate reproducibility and is disallowed.

---

### 2.5 No partial or speculative invocation

Given these preconditions, 6B.S0 **MUST NOT** be invoked in the following situations:

* While any of the required upstream segments (1A–3B, 5A, 5B, 6A) are still running or have not yet produced their validation bundles for this `manifest_fingerprint`.
* Against a `manifest_fingerprint` that does not appear in the upstream dictionaries/registries as a valid world snapshot.
* In a “speculative” mode where S0 is allowed to run with missing upstream gates or missing contract files on the assumption that they will exist later.

S0 is a **hard gate**: either the world below 6B is fully sealed and all required contracts are in place, or S0 fails and **no 6B work is permitted** for that fingerprint.

These preconditions are binding. Any implementation of 6B.S0 **MUST** enforce them before performing the discovery and sealing logic described in subsequent sections.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **what 6B.S0 is allowed to read** and **where its authority stops**. Anything outside these boundaries is out of scope for this state and **MUST NOT** be touched.

6B.S0 is **metadata-only**: it interrogates catalogues, schemas, manifests, config bundles, and upstream HashGates. It does **not** read data-plane rows (arrivals, entities, flows) and it does **not** consume RNG.

---

### 3.1 Engine parameters (implicit inputs)

6B.S0 is always invoked with, or can deterministically derive, the following run parameters:

* `manifest_fingerprint`
  The identifier of the sealed world snapshot across Layers 1–3. All upstream gates and all 6B.S0 outputs are scoped to this value.

* `parameter_hash`
  The hash of the 6B parameter/config pack in use (behaviour priors, campaign configs, label policies). S0 does not interpret the contents of those packs, but it must bind to a specific `parameter_hash` to describe “which configuration universe” 6B will run under.

* `6B_spec_version`
  A version tag for the 6B contracts/spec. S0 must treat this as fixed for the run and use it to resolve the correct schema/dictionary/registry versions.

These parameters are treated as **given** by the orchestration layer. S0 **MUST NOT** derive them from wall-clock time, environment variables, or ad-hoc configuration.

---

### 3.2 Catalogue & contract inputs

6B.S0 **MUST** discover all other inputs through the engine’s catalogues and contract artefacts. Specifically, S0 may read:

1. **JSON-Schema packs (authoritative schemas)**

   * `schemas.layer1.yaml`, `schemas.layer2.yaml`, `schemas.layer3.yaml`
   * `schemas.1A.yaml`, …, `schemas.5B.yaml`, `schemas.6A.yaml`, `schemas.6B.yaml`

   These files are the *only* schema authority. Their `$id` and `$ref` anchors define the shape of:

   * Upstream validation bundles and flags.
   * Upstream `sealed_inputs_*` tables.
   * 6B’s own gate and validation outputs (`s0_gate_receipt_6B`, `sealed_inputs_6B`, `validation_bundle_6B`, `validation_passed_flag_6B`).

   6B.S0 **MUST** validate that any dataset or artefact it reads conforms to the referenced schema before trusting its contents.

2. **Dataset dictionaries**

   * `dataset_dictionary.layer1.*.yaml` for segments 1A–3B.
   * `dataset_dictionary.layer2.*.yaml` for segments 5A and 5B.
   * `dataset_dictionary.layer3.6A.yaml`, `dataset_dictionary.layer3.6B.yaml`.

   Dictionaries are authoritative for:

   * Dataset IDs and roles.
   * Partitioning keys and path templates (with `fingerprint={manifest_fingerprint}`, `parameter_hash={parameter_hash}`, `seed={seed}`, etc.).
   * `schema_ref` anchors into the schema packs.

   S0 uses dictionaries to locate upstream validation bundles/flags and sealed-inputs tables for the target `manifest_fingerprint`, and to register its own outputs. If a dictionary entry contradicts its schema (wrong `schema_ref`, missing `manifest_fingerprint` column where required), S0 **MUST** treat that as a contract error and fail.

3. **Artefact registries**

   * `artefact_registry_1A.yaml`, …, `artefact_registry_3B.yaml`.
   * `artefact_registry_5A.yaml`, `artefact_registry_5B.yaml`.
   * `artefact_registry_6A.yaml`, `artefact_registry_6B.yaml`.

   Registries are authoritative for:

   * Realised artefacts (directories, bundle layouts, `_passed.flag` files).
   * Whether an artefact is `final_in_layer`, `cross_layer`, or segment-local.
   * Additional roles (e.g. `validation_bundle`, `passed_flag`, `sealed_inputs`).

   S0 uses registries to turn dictionary-level dataset IDs into concrete artefact locations and to confirm that required upstream bundles and flags exist for the target `manifest_fingerprint`.

4. **6B contract artefacts**
   Under `dataset_dictionary.layer3.6B.yaml` / `artefact_registry_6B.yaml`, S0 **MUST** be able to find:

   * Entries for `s0_gate_receipt_6B` and `sealed_inputs_6B`.
   * Entries for the eventual `validation_bundle_6B` and `validation_passed_flag_6B`.
   * Any 6B-specific config/validation packs that are treated as artefacts (e.g. `behaviour_prior_pack_6B`, `fraud_campaign_catalogue_config_6B`, `truth_labelling_policy_6B`, `segment_validation_policy_6B`).

   S0 binds to these via dictionary/registry; it does **not** interpret the internal semantics of the config packs, only their identity and checksums.

---

### 3.3 Upstream HashGate & sealed-inputs inputs

Within the authority stack above, 6B.S0 is allowed to read the following **upstream segment artefacts**:

1. **Validation bundles & flags (HashGates)**
   For each required upstream segment (1A–3B, 5A, 5B, 6A), S0 may read:

   * The segment’s `validation_bundle_*` directory for `manifest_fingerprint`, including:

     * `index.json` (or equivalent bundle index),
     * validation reports and issue tables,
     * RNG accounting summaries where present.
   * The segment’s `_passed.flag` file for this fingerprint.

   S0’s authority here is limited to:

   * Verifying existence and structure under the upstream schemas.
   * Recomputing the upstream bundle digest according to the upstream spec and checking it against `_passed.flag`.

   S0 **MUST NOT** reinterpret or override the upstream validation logic itself. If upstream says “PASS” for a fingerprint and the bundle+flag are consistent, 6B.S0 treats that segment as sealed; if not, S0 fails.

2. **Upstream sealed-inputs manifests**

   Where upstream segments have published sealed-inputs tables (notably:

   * `sealed_inputs_5A`,
   * `sealed_inputs_5B`,
   * `sealed_inputs_6A`,

   and any other Layer-1 sealed-inputs surfaces that are relevant for 6B), S0 may read:

   * The entire sealed-inputs tables under `[fingerprint]`.
   * Any digests, roles, and `read_scope` annotations stored there.

   These manifests are the **primary authority** for:

   * “Which artefacts exist in the upstream world for this fingerprint?”
   * “Which of those artefacts are intended to be consumable downstream?”

   6B.S0 may **augment** this view by cross-checking dictionaries/registries, but it must not contradict an upstream sealed-inputs manifest; if there is a mismatch, S0 treats that as a precondition failure for 6B (see §2).

3. **No data-plane tables**

   6B.S0 **MUST NOT** read *rows* from upstream data-plane tables, including but not limited to:

   * `arrival_events_5B` and any S2/S3/S4 Layer-2 tables.
   * 6A entity tables (`s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`, `s4_device_base_6A`, `s4_ip_base_6A`, and their link surfaces).
   * 5A intensity surfaces or 2B routing surfaces.

   S0 may **only** reason about these datasets indirectly via their presence in sealed-inputs manifests, dictionaries, and registries (dataset ID, path template, partitioning, schema_ref, `sha256_hex`), not by scanning or aggregating their contents.

---

### 3.4 6B configuration & policy inputs

6B.S0 is responsible for **binding** the segment to specific config and policy packs, but not for interpreting them. It may read the following configuration inputs in full:

* Behaviour priors (e.g. `behaviour_prior_pack_6B`)
  Priors describing typical behaviours per segment, channel, geography, etc.

* Campaign configuration packs (e.g. `fraud_campaign_catalogue_config_6B`)
  Template definitions for fraud and abuse campaigns, their target populations, and scheduling/activation rules.

* Labelling & outcome policies (e.g. `truth_labelling_policy_6B`)
  Rules and distributions governing truth labels, bank-view labels, dispute/chargeback delays, and case evolution.

* 6B validation policy (e.g. `segment_validation_policy_6B`)
  Which checks the final 6B validation state must run, thresholds for PASS/WARN/FAIL, and what evidence must be present in `validation_bundle_6B`.

All such packs:

* **MUST** be registered in `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml` with clear `schema_ref`, `path_template`, and `role` fields.
* **MUST** be included in `sealed_inputs_6B` with their `sha256_hex`.

S0’s authority over these packs is limited to:

* Verifying their presence and schema conformance.
* Recording their identities and digests in `sealed_inputs_6B`.

S0 **MUST NOT** apply any behavioural, campaign, or labelling logic itself; those responsibilities start in 6B.S1.

---

### 3.5 Authority stack & boundaries

The **authority stack** for 6B.S0 is:

1. **JSON-Schema packs** (layer-wide and per segment)
   → define valid shapes for all inputs and S0 outputs.

2. **Dataset dictionaries**
   → define dataset identities, partition laws, schema refs.

3. **Artefact registries**
   → define realised artefacts (paths, roles, cross-layer status).

4. **Upstream HashGates & sealed-inputs manifests**
   → define which upstream worlds are sealed and which upstream artefacts are in scope.

5. **This specification (6B.S0)**
   → defines how S0 uses the above to decide whether 6B may run, and how it emits `s0_gate_receipt_6B` and `sealed_inputs_6B`.

Where there is a conflict:

* S0 **MUST NOT** override JSON-Schema definitions.
* S0 **MUST NOT** reinterpret upstream HashGate semantics (hashing law, PASS/FAIL meaning).
* S0 **MUST NOT** introduce new upstream requirements beyond those declared in the 6B segment spec and the segment-wide contract set (`6B_spec_version`).

Any such conflict is a **contract error** and must be surfaced as a failure of S0 itself.

---

### 3.6 Prohibited inputs and behaviours

For clarity, the following are expressly disallowed for 6B.S0:

* Reading or aggregating data-plane rows from any upstream or 6B dataset (arrivals, entity tables, flows, events, labels).
* Consuming any Philox RNG streams or emitting any RNG events/logs.
* Accessing external network resources, ad-hoc files, or environment variables as configuration.
* Writing any dataset other than `s0_gate_receipt_6B` and `sealed_inputs_6B`.

6B.S0’s sole authority is to **verify gates, bind to contracts, and enumerate inputs**. All behavioural design and simulation remains the responsibility of 6B.S1–S4.

---

## 4. Outputs (datasets) & identity *(Binding)*

6B.S0 produces **two** and only two data-plane artefacts:

1. A **gate receipt** describing the world and contract set 6B is binding to for a given `manifest_fingerprint`.
2. A **sealed-inputs manifest** listing every artefact 6B is authorised to read for that `manifest_fingerprint`.

Both outputs are:

* **Fingerprint-scoped control-plane datasets** (no `seed`, no `run_id` in partitioning).
* **RNG-free** and **idempotent**: re-running S0 for the same `(manifest_fingerprint, parameter_hash, 6B_spec_version)` MUST reproduce byte-identical outputs or fail with a contract error.
* Registered in `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml` as **engine control-plane** artefacts (not final business outputs).

No other datasets may be written by 6B.S0.

---

### 4.1 `s0_gate_receipt_6B` — behavioural gate receipt

**Dataset id**

* `id: s0_gate_receipt_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

One **logical row per `manifest_fingerprint`** summarising:

* Which upstream segments (1A–3B, 5A, 5B, 6A) were required and whether their HashGates were verified as PASS.
* Which 6B contract artefacts (schemas, dictionary, registry, policy packs) were located and validated.
* Which `parameter_hash` and `6B_spec_version` this run is bound to.
* A deterministic `sealed_inputs_digest_6B` covering the `sealed_inputs_6B` table content for this fingerprint.

Downstream 6B states (S1–S4) and the 6B validation state **MUST** treat this dataset as the canonical statement of:

> *“What world did 6B think it was running against, and which inputs were in scope?”*

**Format, path & partitioning**

The gate receipt MUST be registered in the 6B dataset dictionary and artefact registry as:

* `version: '{manifest_fingerprint}'`
* `format: json`
* `path: data/layer3/6B/gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json`
* `partitioning: [fingerprint]`
* `primary_key: [manifest_fingerprint]`
* `ordering: []` (single logical row per fingerprint; writer is free to serialise fields in any JSON object order consistent with the schema)
* `schema_ref: schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B`

The `manifest_fingerprint` column embedded in the JSON **MUST** exactly match the `fingerprint` partition token.

**Identity fields (non-exhaustive)**

The schema for `s0_gate_receipt_6B` MUST include, at a minimum:

* `manifest_fingerprint` — the world snapshot key; primary key.
* `parameter_hash` — the parameter pack hash 6B is binding to.
* `spec_version_6B` — the 6B spec/contract version.
* `upstream_segments` — a structured map of required upstream segments and their `status` / bundle digests.
* `contracts_6B` — a structured map of 6B contract artefacts (schemas, dictionary, registry, policy packs) and their digests.
* `sealed_inputs_digest_6B` — a deterministic digest computed over the `sealed_inputs_6B` table for this fingerprint (the exact hashing law is defined in Section 6).

Additional fields (timestamps, tooling metadata, free-form notes) MAY be added in future spec versions, but MUST be optional and MUST NOT alter the primary key or partitioning.

---

### 4.2 `sealed_inputs_6B` — behavioural sealed-inputs manifest

**Dataset id**

* `id: sealed_inputs_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

The sealed-inputs manifest is a **fingerprint-scoped inventory** of all artefacts 6B is authorised to read for a given world. Each row describes exactly one artefact (dataset or file) that may be consumed by 6B.S1–S4.

For each artefact, the row MUST record:

* Where it comes from (layer, segment, logical id).
* How it is addressed (path template, partition keys).
* How it should be interpreted (schema_ref, role, read_scope).
* How it was validated (sha256 digest, optional upstream bundle id).

Downstream 6B states and the 6B validation state **MUST** treat this table as the **complete and exclusive list** of allowed inputs; they MUST NOT read any artefact that is not represented by a row in `sealed_inputs_6B`.

**Format, path & partitioning**

The sealed-inputs manifest MUST be registered in the 6B dataset dictionary and artefact registry as:

* `version: '{manifest_fingerprint}'`
* `format: parquet`
* `path: data/layer3/6B/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet`
* `partitioning: [fingerprint]`
* `primary_key: [manifest_fingerprint, owner_layer, owner_segment, manifest_key]`
* `ordering: [owner_layer, owner_segment, manifest_key]`
* `schema_ref: schemas.layer3.yaml#/gate/6B/sealed_inputs_6B`

The `manifest_fingerprint` column embedded in each row **MUST** exactly match the partition token. The primary key columns MUST uniquely identify each artefact row for a given fingerprint.

**Row identity & key fields (non-exhaustive)**

Each row in `sealed_inputs_6B` MUST contain, at minimum:

* `manifest_fingerprint` — the world snapshot key.
* `owner_layer` — the layer that owns the artefact (1, 2, or 3).
* `owner_segment` — the segment id (e.g. `1B`, `2A`, `5B`, `6A`, `6B`).
* `manifest_key` — a logical identifier for the artefact, typically matching the id used in the owning segment’s artefact registry (e.g. `arrival_events_5B`, `s1_party_base_6A`, `behaviour_prior_pack_6B`).
* `path_template` — the resolved path template for the artefact, with partition tokens such as `seed={seed}`, `fingerprint={manifest_fingerprint}`, `scenario_id={scenario_id}` as appropriate.
* `partition_keys` — the list of partition columns required to access the artefact (e.g. `["seed","fingerprint","scenario_id"]` for `arrival_events_5B`).
* `schema_ref` — a JSON-Schema `$ref` into the owning layer’s schema pack (e.g. `schemas.5B.yaml#/s4/arrival_events_5B`, `schemas.6A.yaml#/s1/party_base`).
* `role` — a short classification of the artefact’s role from 6B’s perspective (e.g. `arrival_stream`, `entity_graph`, `static_posture`, `behaviour_prior`, `campaign_config`, `labelling_policy`).
* `status` — `REQUIRED`, `OPTIONAL`, or `IGNORED` in the context of 6B.
* `read_scope` — `ROW_LEVEL` vs `METADATA_ONLY`, indicating whether 6B states are allowed to read the full dataset or only use its metadata/digest.
* `sha256_hex` — a hex-encoded SHA-256 digest of the artefact in its canonical serialisation (as defined by the owning segment or policy).

The schema MAY include additional fields (e.g. `upstream_bundle_id`, `notes`, `min_version`, `max_version`), but these MUST NOT be required for all rows and MUST NOT alter the primary key or partitioning.

---

### 4.3 Relationship to identity axes

The outputs of 6B.S0 are deliberately **fingerprint-only**:

* Neither `s0_gate_receipt_6B` nor `sealed_inputs_6B` are partitioned by `seed` or `run_id`.
* Both datasets **MUST** include `manifest_fingerprint` as a first-class column and **MUST NOT** include `seed` or `run_id` columns.

The receipt and manifest both record the `parameter_hash` and `6B_spec_version` they are bound to, but these are **data fields**, not partitioning keys. This ensures that:

* For a given world (`manifest_fingerprint`) and 6B spec version, there is exactly **one** gate receipt and one sealed-inputs manifest, even if multiple seeds or runs are later used by 6B.S1–S4.
* Downstream states can join on `manifest_fingerprint` without ambiguity.

Any attempt to vary `s0_gate_receipt_6B` or `sealed_inputs_6B` by `seed`, `run_id` or scenario MUST be treated as a contract violation and is out of scope for this spec.

---

### 4.4 Relationship to dictionaries, registries & HashGate

The dataset dictionary and artefact registry for Layer-3 / Segment 6B **MUST** register these outputs exactly as described above:

* `dataset_dictionary.layer3.6B.yaml`:

  * Declares `id`, `version`, `path`, `partitioning`, `primary_key`, `ordering`, and `schema_ref` for `s0_gate_receipt_6B` and `sealed_inputs_6B`.
  * Marks both as `status: required`, with `columns_strict: true`.
  * Assigns appropriate lineage (`produced_by: [ '6B.S0' ]`, `consumed_by: [ '6B.S1', '6B.S2', '6B.S3', '6B.S4', '6B.S5' ]`).

* `artefact_registry_6B.yaml`:

  * Registers the same artefacts with consistent `manifest_key`, `type`, `category`, `environment`, `schema`, `path_template`, and `partitioning`.
  * Marks them as control-plane artefacts (e.g. `retention_class: engine_control_plane`), not business egress.

The eventual 6B validation bundle (`validation_bundle_6B`) and flag (`validation_passed_flag_6B`) are **not** produced by S0, but they will:

* Depend on the correctness of `s0_gate_receipt_6B` and `sealed_inputs_6B`.
* Be registered in the same dictionary/registry and sit under `data/layer3/6B/validation/manifest_fingerprint={manifest_fingerprint}/…` with `partitioning: [fingerprint]`.

This section fully defines the output surfaces and identity model for 6B.S0. Subsequent sections describe how these outputs are populated (algorithm), how their partitions are written (merge discipline), and how downstream states are required to use them.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

All binding schema anchors, dataset IDs, partitioning rules, and manifest keys for this state's egress live in the Layer-3 / Segment 6B contracts:
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/schemas.layer3.yaml`
This specification only summarises semantics so there is a single source of truth for catalogue details. Always consult the files above for precise schema refs, physical paths, partition keys, writer ordering, lifecycle flags, and dependency metadata.

### 5.1 Outputs owned by this state
- `s0_gate_receipt_6B` — Control-plane receipt recording upstream PASS statuses, run identity and the sealed input digest for Segment 6B.
- `sealed_inputs_6B` — Fingerprint-scoped inventory of artefacts 6B is authorised to read once gating succeeds.

### 5.2 Catalogue & downstream obligations
Implementations and downstream consumers MUST resolve datasets via the dictionary/registry, honour the declared schema anchors, and treat any artefact not listed there as out of scope for this state.

## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section specifies **how** 6B.S0 constructs its two outputs in a fully deterministic way, using only catalogue and control-plane artefacts. No RNG, data-plane scans, or external side effects are permitted.

At a high level, for a given `(manifest_fingerprint, parameter_hash, 6B_spec_version)`, S0:

1. Loads and validates the 6B contract set.
2. Verifies the required upstream HashGates for this fingerprint.
3. Discovers the upstream artefacts 6B is allowed to see.
4. Materialises `sealed_inputs_6B` as a canonical manifest of those artefacts.
5. Computes `sealed_inputs_digest_6B`.
6. Writes `s0_gate_receipt_6B` and `sealed_inputs_6B` atomically for this fingerprint.

If any step fails, S0 **MUST NOT** produce or modify either output.

---

### 6.1 Determinism envelope

All behaviour in this state is defined as a pure function of:

* `manifest_fingerprint`,
* `parameter_hash`,
* `6B_spec_version`,
* the contents of the catalogues (schemas, dictionaries, registries),
* upstream validation bundles and sealed-inputs manifests,
* 6B config/policy packs.

S0 **MUST NOT**:

* read a wall-clock time,
* derive configuration from environment variables or host state,
* read or write any RNG state,
* branch on process-local conditions (e.g. hostname, PID) that are not part of the configuration universe.

Re-running S0 for the same inputs **MUST** either:

* reproduce byte-identical artefacts for `s0_gate_receipt_6B` and `sealed_inputs_6B`, or
* fail with a contract error that indicates a catalogue/config drift.

---

### 6.2 Step 1 — Load & validate 6B contract set

**Inputs**

* `schemas.layer3.yaml`, `schemas.6B.yaml`.
* `dataset_dictionary.layer3.6B.yaml`.
* `artefact_registry_6B.yaml`.
* 6B configuration packs (behaviour priors, campaign configs, labelling policy, validation policy).

**Algorithm**

1. Using the engine’s catalogue index, resolve:

   * the exact versions of `schemas.layer3.yaml` and `schemas.6B.yaml` compatible with `6B_spec_version`,
   * the corresponding dictionary and registry entries for `owner_layer=3, owner_segment=6B`.

2. Validate that:

   * All `schema_ref` values in `dataset_dictionary.layer3.6B.yaml` resolve into one of the schema packs.
   * For `s0_gate_receipt_6B` and `sealed_inputs_6B`, the dictionary’s `path`, `partitioning`, `primary_key`, and `format` match the requirements in Sections 4–5.
   * The registry entries for these artefacts use the same `manifest_key`, `schema`, `path_template`, and `partitioning` as the dictionary.

3. Resolve and schema-validate the 6B configuration packs using their `schema_ref`s (they may be simple JSON/YAML configs with their own anchors in `schemas.layer3.yaml` / `schemas.6B.yaml`).

4. If any contract artefact is missing or fails schema validation, or if dictionary/registry disagree on any of the S0 output properties, S0 **MUST** fail with a contract error and **MUST NOT** proceed to Step 2.

This step does **not** yet inspect any upstream segments; it only ensures that 6B’s own contracts are internally consistent.

---

### 6.3 Step 2 — Verify upstream HashGates for `manifest_fingerprint`

**Inputs**

* Layer-1, Layer-2, and 6A dataset dictionaries and artefact registries.
* Upstream schemas for validation bundles and flags.
* Required segment list: `{1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B, 6A}`.

**Algorithm**

For each required upstream segment `SEG` in the list above:

1. From the owning segment’s dictionary/registry, resolve:

   * the dataset/artefact entries for `validation_bundle_SEG`,
   * the `validation_passed_flag_SEG` (file `_passed.flag`) artefact.

2. Using those entries, construct the expected bundle and flag locations for the target `manifest_fingerprint`, e.g.:

   ```text
   data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/index.json
   data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
   ```

3. Check for existence of both the bundle directory and the flag file. If either is missing, record `status="MISSING"` for that segment in a working `upstream_segments` map and mark S0 as not runnable.

4. If both exist:

   1. Parse the upstream bundle index and validate it against the owning segment’s validation schema.
   2. For each member listed in the index, recompute its `sha256_hex` digest from bytes on disk (or verify against a pre-computed digest if the upstream spec allows).
   3. Compute the upstream bundle digest according to that segment’s hashing law (e.g. concatenated bytes of evidence files in ASCII-lex order, SHA-256).
   4. Read the upstream `_passed.flag` file and verify that its recorded digest exactly matches the recomputed bundle digest.

5. If any of (4)(a–d) fails, record `status="FAIL"` for that segment with whichever partial digests could be computed.

6. After processing all required segments:

   * If any segment is `"MISSING"` or `"FAIL"`, S0 **MUST** abort with a precondition failure (see Section 2), without writing outputs.
   * Otherwise, all segments are `"PASS"` with verified `bundle_sha256` values that will be copied into `s0_gate_receipt_6B`.

At the end of Step 2, S0 has a fully populated `upstream_segments` map with status and digest information for all required segments, but has not yet touched any data-plane tables.

---

### 6.4 Step 3 — Discover upstream artefacts for 6B

**Inputs**

* Upstream sealed-inputs manifests (especially `sealed_inputs_5B` and `sealed_inputs_6A`).
* Upstream dictionaries and registries for any segments whose artefacts 6B may consume.
* 6B configuration packs (to know which categories of artefacts are required/optional).

**Algorithm**

1. Using `dataset_dictionary.layer2.5B.yaml` and `artefact_registry_5B.yaml`, locate `sealed_inputs_5B` for this `manifest_fingerprint` and validate it against its schema.

   * If 5B is a required upstream segment (it is), then absence of `sealed_inputs_5B` or a schema failure here is a fatal error.

2. Do the same for `sealed_inputs_6A`. Treat it as required, since 6B depends on the 6A entity graphs and posture.

3. Optionally (depending on the 6B spec version), locate sealed-inputs manifests for other upstream segments that 6B wishes to refer to indirectly (e.g. for completeness or metadata-only consumption). These additional manifests are usually `METADATA_ONLY` from 6B’s perspective.

4. Build a working set `CANDIDATE_ARTIFACTS` by scanning:

   * Required upstream sealed-inputs tables (`sealed_inputs_5B`, `sealed_inputs_6A`).
   * 6B configuration packs (for 6B-local artefacts that are not already in upstream sealed-inputs).
   * Any additional upstream artefacts 6B is mandated to list (e.g. upstream validation bundles, some Layer-1 control-plane artefacts), discovered via dictionaries/registries.

5. For each candidate artefact, resolve:

   * `owner_layer` and `owner_segment` from the owning dictionary/registry.
   * The `manifest_key` (dataset id or manifest key, as per the owning artefact registry).
   * The `path_template` and `partition_keys` from the owning dictionary/registry.
   * The `schema_ref` anchor.
   * 6B’s role classification (`arrival_stream`, `entity_graph`, `static_posture`, `behaviour_prior`, etc.) by applying 6B’s role-mapping logic to `(owner_layer, owner_segment, manifest_key, schema_ref)`.
   * The required vs optional `status` and `read_scope` (`ROW_LEVEL` vs `METADATA_ONLY`) using 6B’s validation policy.

6. For each candidate artefact:

   * Compute or verify `sha256_hex` for the artefact. For datasets partitioned on `seed` or `scenario_id`, this may be a digest of a higher-level control artefact (e.g. a manifest listing partitions) as defined by the owning segment.
   * If the owning segment’s sealed-inputs manifest already provides a digest and hashing law that S0 trusts, S0 MAY reuse that digest rather than recalculating from bytes.

7. Filter `CANDIDATE_ARTIFACTS` to a final set based on 6B’s requirements:

   * Any artefact that is marked `IGNORED` by 6B’s policy MUST NOT be included.
   * Any artefact that is marked `REQUIRED` and is missing or fails digest verification MUST cause S0 to fail.
   * Optional artefacts MAY be dropped if missing; they simply do not appear in `sealed_inputs_6B`.

At the end of Step 3, S0 has a complete in-memory representation of every artefact that will be written as a row in `sealed_inputs_6B`.

---

### 6.5 Step 4 — Materialise `sealed_inputs_6B`

**Inputs**

* The in-memory `CANDIDATE_ARTIFACTS` set from Step 3.
* The schema for `sealed_inputs_6B`.

**Algorithm**

1. For each artefact in `CANDIDATE_ARTIFACTS` that survived filtering:

   * Construct a row object with fields:

     ```text
     manifest_fingerprint
     owner_layer
     owner_segment
     manifest_key
     path_template
     partition_keys
     schema_ref
     role
     status
     read_scope
     sha256_hex
     [optional extra fields as defined in schema]
     ```

2. Validate each row against `schemas.layer3.yaml#/gate/6B/sealed_inputs_6B`.

3. Sort all rows by `(owner_layer, owner_segment, manifest_key)` as per the dataset dictionary’s `ordering` clause.

4. Write the sorted rows into a single parquet file under:

   ```text
   data/layer3/6B/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet
   ```

   taking care to:

   * Embed the `manifest_fingerprint` column value matching the partition token.
   * Ensure no duplicates on `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)`.

5. If any validation or write error occurs, S0 MUST abort and must not write a gate receipt.

At the end of Step 4, the `sealed_inputs_6B` dataset exists on disk, but no gate receipt has been published yet.

---

### 6.6 Step 5 — Compute `sealed_inputs_digest_6B`

**Inputs**

* The persisted `sealed_inputs_6B` parquet file.
* A fixed, engine-wide rule for canonical row serialisation.

**Algorithm**

1. Read the rows of `sealed_inputs_6B` for `manifest_fingerprint` in the canonical order `(owner_layer, owner_segment, manifest_key)`.

2. For each row, produce a **canonical byte representation**, using an engine-wide, versioned rule (e.g.):

   * Serialise to JSON with:

     * UTF-8 encoding,
     * a fixed key order that matches the schema,
     * no extra whitespace,
     * no trailing commas.
   * Or serialise to another canonical format (e.g. CBOR canonical mode) as agreed by the engine contracts.

   The particular encoding is not prescribed here, but it **MUST** be:

   * deterministic across platforms and runs,
   * documented and versioned as part of the Layer-3 contracts.

3. Concatenate the canonical serialisations of all rows in order into a single byte stream.

4. Compute:

   ```text
   sealed_inputs_digest_6B = SHA-256(concatenated_bytes)
   ```

   and express it as a 64-character lower-case hex string.

5. Retain this digest in memory for use when constructing `s0_gate_receipt_6B`.

If any problem occurs in reading or serialising `sealed_inputs_6B`, S0 MUST treat this as a failure and not emit a gate receipt.

---

### 6.7 Step 6 — Emit `s0_gate_receipt_6B` atomically

**Inputs**

* `upstream_segments` map from Step 2.
* 6B contract digests from Step 1.
* `sealed_inputs_digest_6B` from Step 5.
* `manifest_fingerprint`, `parameter_hash`, `6B_spec_version`.

**Algorithm**

1. Construct an in-memory JSON object conforming to `schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B` with:

   * `manifest_fingerprint` = the target fingerprint.
   * `parameter_hash` and `spec_version_6B` as given to S0.
   * `upstream_segments` filled with segment ids, `status="PASS"` and the verified `bundle_sha256` values from Step 2.
   * `contracts_6B` filled with the logical ids, paths, `schema_ref`s and `sha256_hex` for 6B contract artefacts from Step 1.
   * `sealed_inputs_digest_6B` set to the value computed in Step 5.
   * `created_utc` set according to the engine’s deterministic timestamping rule (e.g. taken from the orchestrator envelope rather than local wall-clock).

2. Validate the object against its schema.

3. Perform an **atomic write** to:

   ```text
   data/layer3/6B/gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json
   ```

   using the engine’s standard write-once semantics:

   * If no file exists yet for this fingerprint, write it.
   * If a file already exists, read it and compare against the in-memory object:

     * If they are byte-identical, treat the operation as a no-op (idempotent re-run).
     * If they differ, treat this as a non-idempotent conflict and fail, without overwriting the existing file.

4. Only after a successful write/validation of `s0_gate_receipt_6B` should S0 mark itself as **PASS** in the run-report for this `manifest_fingerprint`.

At the end of Step 6, both `sealed_inputs_6B` and a consistent `s0_gate_receipt_6B` exist for the target fingerprint and are visible to downstream states.

---

### 6.8 Summary of invariants

The algorithm above enforces the following invariants:

* S0 is **RNG-free** and never touches data-plane rows.
* S0 never runs on a world where any required upstream HashGate is missing or failing.
* Every artefact 6B is allowed to read appears exactly once in `sealed_inputs_6B`.
* `sealed_inputs_digest_6B` deterministically summarises the manifest contents.
* `s0_gate_receipt_6B` is uniquely and idempotently defined per `(manifest_fingerprint, parameter_hash, 6B_spec_version)`.

These invariants are binding; any implementation of 6B.S0 MUST behave as an equivalent deterministic algorithm, even if internal data structures or encoding details differ.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how 6B.S0’s outputs are **identified**, how they are **partitioned and ordered** on disk, and what **merge / re-run discipline** implementations MUST follow.

The goal is that, for any given **world** (`manifest_fingerprint`), there is a single, unambiguous and reproducible view of:

* which inputs 6B is allowed to read (`sealed_inputs_6B`), and
* what 6B believed about the upstream gates and its own contracts (`s0_gate_receipt_6B`).

---

### 7.1 Identity axes for 6B.S0

6B.S0 is defined over the following axes:

* `manifest_fingerprint` — **primary identity axis** (world snapshot).
* `spec_version_6B` — version tag for the 6B contracts/spec.
* `parameter_hash` — hash of the 6B parameter/config pack used when populating `sealed_inputs_6B`.

**Binding rules:**

1. 6B.S0 is always invoked with a single **target** `manifest_fingerprint`.
2. For that fingerprint, 6B.S0 binds to exactly one `spec_version_6B` and one `parameter_hash`.
3. S0’s outputs encode `spec_version_6B` and `parameter_hash` as data fields in `s0_gate_receipt_6B`, but **do not** partition on them.

Consequences:

* For a given world (`manifest_fingerprint`), there is at most **one** valid S0 gate receipt and sealed-inputs manifest in a given deployment of 6B. If you want to run alternative 6B configurations against the same world, that MUST be introduced via a spec/contract change (new `spec_version_6B`) or a separate segment, not by mutating S0’s outputs.

---

### 7.2 Partitioning & file layout

Both outputs of 6B.S0 are **fingerprint-partitioned control-plane datasets**:

* `s0_gate_receipt_6B`:

  * Path (template):
    `data/layer3/6B/gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json`
  * Partitioning: `[fingerprint]`
  * Primary key: `[manifest_fingerprint]`

* `sealed_inputs_6B`:

  * Path (template):
    `data/layer3/6B/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet`
  * Partitioning: `[fingerprint]`
  * Primary key: `[manifest_fingerprint, owner_layer, owner_segment, manifest_key]`

Binding constraints:

* The `fingerprint` path token MUST equal the `manifest_fingerprint` column value in all rows for that file.
* No `seed`, `scenario_id`, `run_id` or other dimensions MAY appear in the partitioning list for these datasets.
* There MUST be exactly one `sealed_inputs_6B` parquet file per `manifest_fingerprint`, and at most one `s0_gate_receipt_6B.json` file per `manifest_fingerprint`.

The presence or absence of `seed` and `scenario_id` is a property of **artefacts listed in** `sealed_inputs_6B`, not of S0’s own outputs.

---

### 7.3 Ordering discipline

Ordering is used solely to enforce determinism and stable digests, not as a substitute for proper keys.

#### 7.3.1 `sealed_inputs_6B`

Writers of `sealed_inputs_6B` MUST:

* Emit rows in strictly non-decreasing order of the tuple:

  ```text
  (owner_layer, owner_segment, manifest_key)
  ```

* Maintain uniqueness of the primary key:

  ```text
  (manifest_fingerprint, owner_layer, owner_segment, manifest_key)
  ```

This ordering MUST be reflected both in:

* the physical parquet row order, and
* any in-memory enumeration used when computing `sealed_inputs_digest_6B`.

Readers MUST NOT rely on ordering alone; they MUST use primary-key equality for joins. Ordering is only a determinism constraint for the hashing law and for human sanity when inspecting the manifest.

#### 7.3.2 `s0_gate_receipt_6B`

`s0_gate_receipt_6B` is a single JSON object per fingerprint, so no intra-dataset ordering is needed. The JSON schema does NOT enforce ordering of object keys; they may appear in any order.

However:

* When computing digests or comparing receipts for idempotence, implementations MUST use byte-for-byte comparison of the serialised JSON produced by S0.
* Any library-level re-serialisation (pretty-printing, re-ordering keys) is a consumer’s concern and MUST NOT feed back into S0’s own idempotence logic.

---

### 7.4 Join discipline for downstream states

Downstream 6B states (S1–S4) and the 6B validation state MUST observe the following join discipline:

* **Primary join key:** `manifest_fingerprint`

  * Every 6B data-plane dataset (flows, events, labels) and every upstream artefact it reads MUST include `manifest_fingerprint` as a column, consistent with the owning segment’s schema.
  * 6B.S1–S4 MUST join their own business datasets to `s0_gate_receipt_6B` and `sealed_inputs_6B` on `manifest_fingerprint` only.

* **No implicit dependence on `seed` or `scenario_id` in S0 outputs:**

  * S0’s outputs do not carry `seed` or `scenario_id`. Downstream states are free to partition their own datasets by `seed`, `scenario_id`, etc., but must treat S0’s outputs as purely world-scoped.

* **Use of `sealed_inputs_6B` as authority:**

  * When a downstream state needs to access `arrival_events_5B`, `s1_party_base_6A`, or any other upstream dataset, it MUST obtain the relevant `path_template`, `partition_keys` and `schema_ref` from `sealed_inputs_6B` (filtered by `manifest_fingerprint`, `owner_layer`, `owner_segment`, `manifest_key`), rather than reconstructing paths manually.

This ensures that all 6B behaviour is tied back to the gate that S0 recorded for that world.

---

### 7.5 Merge & re-run discipline

6B.S0 is designed to be **write-once, idempotent, non-merging** for each fingerprint.

#### 7.5.1 Single-writer assumption per fingerprint

For a given `(manifest_fingerprint, spec_version_6B)`, there MUST be at most one *successful* invocation of 6B.S0.

The engine MAY allow multiple attempts to run S0 concurrently or sequentially, but the merge discipline is:

* If no outputs exist yet for this fingerprint:

  * The first successful S0 invocation writes `sealed_inputs_6B` and `s0_gate_receipt_6B`.
* If outputs already exist:

  * A re-run MUST either reproduce byte-identical outputs (same parquet rows, same JSON, same digests), or fail with a `STATE_NOT_IDEMPOTENT` / equivalent error.
  * Overwriting or mutating existing outputs is forbidden.

There is no concept of “incremental” or “append” writes for S0 outputs; they are full replacements keyed by `manifest_fingerprint`.

#### 7.5.2 Write ordering & atomicity

The write discipline for S0 outputs is:

1. **Write `sealed_inputs_6B` first.**

   * Only after a complete, schema-valid parquet file has been written and flushed for the target fingerprint does S0 proceed to write the gate receipt.

2. **Compute `sealed_inputs_digest_6B` from the persisted file.**

   * The digest MUST be computed from the **on-disk** representation, not from a pre-write buffer.

3. **Write `s0_gate_receipt_6B` atomically.**

   * If `s0_gate_receipt_6B.json` does not exist, create it with the computed digest.
   * If it does exist, S0 MUST compare the existing file with the would-be new content:

     * If byte-identical: treat as a no-op.
     * If different: fail with an idempotence/merge error and MUST NOT overwrite.

If a failure occurs after writing `sealed_inputs_6B` but before writing `s0_gate_receipt_6B`, the state is considered **incomplete** for that fingerprint. Orchestrators MUST treat “sealed_inputs present, gate receipt absent” as “S0 has not PASSed” and MUST NOT run S1–S4.

#### 7.5.3 No partial merges or compaction

S0 outputs MUST NOT be subject to:

* partial merges across fingerprints,
* compaction that alters row order or row content,
* partition coalescing that causes multiple fingerprints to share the same file.

Any such process would break the determinism guarantees and invalidate `sealed_inputs_digest_6B`.

If storage-level compaction is unavoidable, it MUST be defined as a **lossless, digest-preserving transform** whose effects are accounted for in the hash law and explicitly permitted by a future contract version; it is out of scope for this version of 6B.S0.

---

### 7.6 Consistency with upstream identity model

The above identity and merge rules are chosen to align with the existing engine identity model:

* **Upstream segments** use:

  * `manifest_fingerprint` for world snapshots and validation bundles/flags.
  * `seed` (and sometimes `parameter_hash`) for per-run data-plane outputs.
* **6A** exposes a world+seed entity graph sealed behind `_passed.flag`.
* **5B** exposes per-seed arrival tables sealed behind `_passed.flag`.

6B.S0 sits strictly at the **world level**:

* It is indifferent to `seed` and `scenario_id`.
* It records only which upstream artefacts (whose own identities include `seed` etc.) 6B is allowed to read.

By respecting the partitioning and merge discipline described above, S0 ensures that there is a single, coherent, reproducible definition of “what 6B could see” for each world, which all behaviour and validation states can rely on.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines:

* When 6B.S0 itself is considered **PASS** or **FAIL** for a given `manifest_fingerprint`.
* What obligations this places on **downstream 6B states**, **Layer-3 validation**, and **external orchestrators**.

All conditions below are **binding**. An implementation that deviates from them MUST be treated as non-conforming.

---

### 8.1 Acceptance criteria for 6B.S0 (per `manifest_fingerprint`)

6B.S0 is evaluated **per world** (`manifest_fingerprint`). For a given fingerprint, S0 is considered **PASS** if and only if all of the following hold:

1. **6B contract set is valid**

   * `schemas.layer3.yaml` and `schemas.6B.yaml` have been loaded and schema-validated.
   * `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml` have been loaded and are internally consistent for:

     * `s0_gate_receipt_6B`,
     * `sealed_inputs_6B`,
     * the eventual `validation_bundle_6B` and `validation_passed_flag_6B`.
   * All `schema_ref` values used for these artefacts resolve into one of the schema packs.
   * Any 6B configuration packs (behaviour priors, campaign configs, labelling policy, validation policy) required by the active `6B_spec_version`:

     * are present,
     * conform to their schemas, and
     * are listed in the local “contracts_6B” view used to build the gate receipt.

2. **All required upstream HashGates are present and verified**
   For each segment in `{1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B, 6A}`:

   * A validation bundle directory for `manifest_fingerprint` exists at the path implied by that segment’s dictionary/registry.
   * The corresponding `_passed.flag` exists.
   * The bundle index passes the owning segment’s validation schema.
   * S0 has successfully recomputed the segment’s bundle digest according to the owning spec and confirmed:

     * The digest in `_passed.flag` matches the recomputed value.
     * The segment’s own validation verdict is “PASS” for this fingerprint (if encoded in the bundle/report).

   If **any** required upstream segment is `MISSING` or `FAIL` according to S0’s checks, S0 MUST be considered **FAIL** and MUST NOT produce or update its outputs.

3. **Upstream sealed-inputs manifests needed by 6B are present and valid**

   * `sealed_inputs_5B` exists, is schema-valid, and covers all artefacts 6B requires from segment 5B (`arrival_events_5B` at minimum).
   * `sealed_inputs_6A` exists, is schema-valid, and covers all artefacts 6B requires from segment 6A (entity graph tables and posture surfaces at minimum).
   * Any additional upstream sealed-inputs tables that 6B marks as `REQUIRED` in its validation policy are also present and schema-valid.

   If a required upstream sealed-inputs manifest is missing, malformed, or does not enumerate artefacts that 6B considers `REQUIRED`, then S0 MUST be considered **FAIL**.

4. **`sealed_inputs_6B` is complete, consistent and schema-valid**

   * For this `manifest_fingerprint`, `sealed_inputs_6B` contains **exactly one** row per authorised artefact `(owner_layer, owner_segment, manifest_key)` that 6B intends to read.
   * For every row:

     * `manifest_fingerprint` equals the partition token.
     * `owner_layer`, `owner_segment`, `manifest_key`, `path_template`, `partition_keys`, `schema_ref`, `role`, `status`, `read_scope`, and `sha256_hex` conform to the schema.
     * The `schema_ref` resolves into the owning layer’s schema pack.
     * The `(path_template, partition_keys)` pair is consistent with the owning segment’s dictionary/registry.
   * There are **no duplicate** primary keys `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)`.
   * All artefacts that 6B’s policy marks as `REQUIRED` are present with `status="REQUIRED"` and a valid `sha256_hex`.

   Optional artefacts (`status="OPTIONAL"`) MAY be absent entirely (no row) or present; their absence MUST NOT, on its own, cause S0 to fail. Artefacts marked `IGNORED` MUST NOT appear in `sealed_inputs_6B`.

5. **`sealed_inputs_digest_6B` is correctly computed**

   * The `sealed_inputs_6B` parquet for this fingerprint has been read back using the canonical ordering and serialisation rules.
   * `sealed_inputs_digest_6B` has been computed over the on-disk contents as specified in Section 6.6.
   * The computed digest is embedded into `s0_gate_receipt_6B.sealed_inputs_digest_6B`.

6. **`s0_gate_receipt_6B` is schema-valid and aligned with `sealed_inputs_6B`**

   * The JSON object written as `s0_gate_receipt_6B`:

     * conforms to `schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B`,
     * has `manifest_fingerprint` equal to the partition token,
     * reflects the upstream segment statuses and bundle digests computed in Step 2,
     * lists all 6B contract artefacts and their digests as discovered in Step 1,
     * contains `sealed_inputs_digest_6B` equal to the value computed from `sealed_inputs_6B`.
   * Any pre-existing `s0_gate_receipt_6B` for this fingerprint, if present, is **byte-identical** to the newly computed receipt (idempotence).

If **all** of the above hold, S0 is **PASS** for the target fingerprint. Any violation MUST be surfaced as a failure of S0, with an appropriate canonical error code (see Section 9), and S0 MUST NOT claim success or permit downstream 6B states to run.

---

### 8.2 Conditions that MUST cause S0 to fail

For clarity, the following conditions are **fatal** for 6B.S0:

* Any required upstream segment’s HashGate cannot be located or cannot be verified (missing bundle, missing flag, digest mismatch, non-PASS verdict).
* Any required upstream sealed-inputs manifest (`sealed_inputs_5B`, `sealed_inputs_6A`, or others marked `REQUIRED` by 6B policy) is absent or fails schema validation.
* The 6B contract set (schemas, dictionary, registry) is missing, inconsistent, or refers to invalid schema anchors.
* A 6B configuration pack required by the active `6B_spec_version` is missing or fails schema validation.
* `sealed_inputs_6B` cannot be materialised to a schema-valid parquet (schema violation, duplicate primary keys, inconsistent path/schema_ref for any `REQUIRED` artefact).
* The digest computed for `sealed_inputs_6B` cannot be computed (I/O errors, serialisation errors) or is inconsistent with an existing `s0_gate_receipt_6B`.
* An existing `s0_gate_receipt_6B.json` for the same fingerprint exists on disk but differs byte-for-byte from the newly produced receipt (non-idempotent re-run).

In all such cases:

* S0 MUST write no new outputs and MUST NOT modify existing outputs.
* The run-report entry for 6B.S0 MUST record `status="FAIL"` for the target fingerprint, along with a canonical error code and diagnostic message.

---

### 8.3 Gating obligations for 6B.S1–S4

6B.S0 is the **hard gate** for all other 6B states. The following obligations are binding:

1. **Precondition: S0 PASS required**

   For a given `manifest_fingerprint`, 6B.S1–S4 (and the 6B validation state) **MUST NOT** run unless:

   * A `s0_gate_receipt_6B` exists at the expected path for that fingerprint, and
   * It has been validated against its schema, and
   * The engine’s run-report records 6B.S0 as `status="PASS"` for that fingerprint.

   Implementations MAY additionally recompute `sealed_inputs_digest_6B` and confirm alignment with the receipt, but this is not required for every downstream state as long as S0 has already done so.

2. **Use `sealed_inputs_6B` as the only input inventory**

   6B.S1–S4 MUST treat `sealed_inputs_6B` as the **complete and exclusive** inventory of artefacts they may read:

   * To access an upstream dataset (e.g. `arrival_events_5B`, `s1_party_base_6A`), a 6B state MUST:

     * locate the corresponding row in `sealed_inputs_6B` using `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)`,
     * derive the path and partition keys from `path_template` and `partition_keys`,
     * rely on the `schema_ref` for shape.

   * A 6B state **MUST NOT**:

     * construct ad-hoc paths by string concatenation,
     * read datasets that are not present in `sealed_inputs_6B`,
     * access artefacts whose `status` is `IGNORED`.

3. **Respect `status` and `read_scope` flags**

   * Artefacts with `status="REQUIRED"`:

     * Downstream states MAY assume these artefacts exist and are readable at run time; their absence is a bug in S0 or in orchestration.

   * Artefacts with `status="OPTIONAL"`:

     * Downstream states MUST be coded defensively: if no row exists in `sealed_inputs_6B` for such an artefact, the state MUST degrade gracefully (e.g. skip a non-critical validation, disable a non-essential feature) rather than failing the run.

   * Artefacts with `read_scope="METADATA_ONLY"`:

     * 6B.S1–S4 MUST NOT read data rows from these datasets. They may only use metadata (e.g. existence, size, digest) as conveyed indirectly (e.g. via upstream sealed-inputs or validation bundles).

4. **No bypass or mutation of S0 outputs**

   * 6B.S1–S4 MUST NOT modify `s0_gate_receipt_6B` or `sealed_inputs_6B`.
   * If a downstream state detects that `s0_gate_receipt_6B` or `sealed_inputs_6B` is missing or malformed for its target fingerprint, it MUST treat that as a hard error and fail, rather than attempting to “repair” S0.

---

### 8.4 Gating obligations for 6B segment validation (S5) and 4A/4B

Although 6B.S5 (validation/HashGate) is specified separately, 6B.S0 places the following obligations on it:

1. **S5 MUST depend on S0 PASS**

   * The 6B validation/HashGate state MUST treat a PASSed S0 as a strict precondition: if S0 is not PASS for a given fingerprint, S5 MUST NOT attempt to validate or publish `validation_bundle_6B` and `_passed.flag` for that fingerprint.

2. **S5 MUST treat S0 outputs as part of its own bundle**

   * `s0_gate_receipt_6B` and `sealed_inputs_6B` MUST be included in the 6B validation bundle (or referenced by digest) and MUST be validated as part of S5’s checks.
   * Any mismatch between the S0 receipt and the actual sealed inputs (e.g. digest mismatch, missing required artefact) MUST cause S5 to fail, even if all downstream behaviour states appear to be well-formed.

For **4A/4B and external consumers**:

* 4A/4B MUST NOT consider any 6B business outputs (flows, events, labels) as **readable** for a given fingerprint unless:

  * 6B.S0 is PASS for that fingerprint (so the 6B behavioural universe is well-defined), AND
  * the 6B segment HashGate (`validation_bundle_6B` + `_passed.flag`) is PASS according to the Layer-3 validation spec.

S0 alone is **not** a consumption gate for 6B’s business outputs; it is the precondition for compute. 4A/4B MUST gate on S5’s HashGate, which in turn depends on S0.

---

### 8.5 Interaction with orchestrators & run-report

Engine orchestrators and run-report consumers MUST honour the following:

* If 6B.S0 is marked `FAIL` or is absent for a given `manifest_fingerprint`:

  * No 6B state (S1–S5) MUST be scheduled for that fingerprint.
  * Any user-facing run-report MUST show 6B as “Not initialised” / “Failed gate” for that world.

* If 6B.S0 is `PASS`, but any downstream state fails:

  * Orchestrators MAY choose to re-run S1–S5, but MUST NOT re-run S0 unless the contracts or upstream gates have changed.
  * Any re-run of S0 that would produce different outputs MUST be treated as a **breaking change** and resolved via contract evolution (e.g. new `6B_spec_version`), not as routine operational retry.

These obligations ensure that 6B.S0 truly functions as the **behavioural gate** for Segment 6B: if it passes, downstream states know what world and contracts they are running against; if it fails, no behaviour MUST be generated or exposed for that world.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical failure modes** for 6B.S0 and the **error codes** that MUST be emitted when they occur.

For any invocation of 6B.S0 against a given `manifest_fingerprint`, the state MUST:

* End in exactly one of: `status="PASS"` or `status="FAIL"`.
* If `status="FAIL"`, attach a **single primary error code** from the list below and MAY attach secondary codes and diagnostic fields.

All failure modes in this section are **fatal** for 6B.S0 and MUST prevent 6B.S1–S4 and 6B.S5 from running for that fingerprint (see §8).

---

### 9.1 Error model overview

* **Primary error code**
  A short, machine-friendly string (e.g. `UPSTREAM_HASHGATE_MISSING`) from the enumeration defined below. Exactly one per failed S0 attempt.

* **Secondary error codes (optional)**
  A list of additional codes providing more colour (e.g. both `UPSTREAM_HASHGATE_INVALID` and `UPSTREAM_VALIDATION_NONPASS` for the same upstream segment). Secondary codes MUST NOT be used without a primary.

* **Context fields**
  Where applicable, the run-report and logs SHOULD include contextual fields:

  * `manifest_fingerprint`
  * `owner_layer`, `owner_segment` (for upstream failures)
  * `manifest_key` (for artefact-level failures)
  * `detail` (human-readable string)

S0’s run-report schema MUST allow these fields but MUST NOT require any specific `detail` text.

---

### 9.2 Upstream HashGate failures

These codes cover failures when verifying **upstream validation bundles & flags** for `{1A,1B,2A,2B,3A,3B,5A,5B,6A}`.

#### 9.2.1 `UPSTREAM_HASHGATE_MISSING`

**Definition**

Emitted when S0 cannot locate the required upstream validation bundle and/or `_passed.flag` for a segment and fingerprint, despite dictionary/registry entries indicating that such artefacts should exist.

**Examples**

* Bundle directory not found at the expected `fingerprint={manifest_fingerprint}` path.
* `_passed.flag` file missing inside an otherwise present bundle directory.

**Obligations**

* S0 MUST set `status="FAIL"` and MUST NOT proceed to sealed-inputs discovery.
* Run-report MUST include `owner_layer`, `owner_segment` of the failing upstream segment.

---

#### 9.2.2 `UPSTREAM_HASHGATE_INVALID`

**Definition**

Emitted when S0 locates the upstream bundle and flag, but **cannot verify** the HashGate according to the owning segment’s hashing law.

**Examples**

* Bundle index fails upstream schema validation.
* SHA-256 digests listed in the upstream index do not match the actual files.
* Recomputed bundle digest does not match the value recorded in `_passed.flag`.

**Obligations**

* S0 MUST treat the upstream segment as `status="FAIL"` in its internal `upstream_segments` map.
* S0 MUST terminate with `status="FAIL"` and MUST NOT emit S0 outputs.

---

#### 9.2.3 `UPSTREAM_VALIDATION_NONPASS`

**Definition**

Emitted when the upstream validation bundle is structurally sound and the HashGate is valid, but the upstream **own validation verdict** is not `"PASS"` for this fingerprint.

**Examples**

* Upstream validation report or receipt includes `overall_status="FAIL"` or `"WARN_ONLY_DISALLOWED"` for the target fingerprint.

**Obligations**

* S0 MUST NOT second-guess the upstream verdict; it MUST fail with this code.

---

### 9.3 Upstream sealed-inputs failures

These codes cover failures when reading required upstream `sealed_inputs_*` tables (notably 5B & 6A).

#### 9.3.1 `UPSTREAM_SEALED_INPUTS_MISSING`

**Definition**

Emitted when a required upstream sealed-inputs manifest cannot be found for this fingerprint.

**Examples**

* `sealed_inputs_5B` does not exist, even though 5B’s HashGate is PASS.
* `sealed_inputs_6A` is absent.

**Obligations**

* S0 MUST fail; 6B cannot safely infer which artefacts exist upstream.

---

#### 9.3.2 `UPSTREAM_SEALED_INPUTS_INVALID`

**Definition**

Emitted when a required upstream sealed-inputs manifest exists but fails **schema validation** or is internally inconsistent.

**Examples**

* `sealed_inputs_5B` fails its schema in `schemas.layer2.yaml`.
* A row in `sealed_inputs_6A` lists a dataset whose path/schema_ref contradict the owning dictionary/registry.

**Obligations**

* S0 MUST fail; 6B MUST NOT guess around malformed manifests.

---

### 9.4 6B contract & config failures

These codes cover failures in the **6B contract set** (schemas, dictionary, registry) and config packs.

#### 9.4.1 `CONTRACT_SET_INCOMPLETE`

**Definition**

Emitted when required 6B contract artefacts cannot be resolved.

**Examples**

* `schemas.layer3.yaml` or `schemas.6B.yaml` not found for `spec_version_6B`.
* `dataset_dictionary.layer3.6B.yaml` missing or empty.
* `artefact_registry_6B.yaml` missing required entries.

---

#### 9.4.2 `SCHEMA_ANCHOR_UNRESOLVED`

**Definition**

Emitted when a `schema_ref` used by 6B’s dictionary/registry does **not** resolve into the published schema packs.

**Examples**

* `schema_ref: schemas.layer3.yaml#/gate/6B/sealed_inputs_6B` does not point to an existing `$id`.
* `schema_ref` typo or stale anchor after a schema refactor.

**Obligations**

* S0 MUST fail; dictionary/registry MUST be corrected before 6B can run.

---

#### 9.4.3 `CONFIG_VALIDATION_FAILED`

**Definition**

Emitted when a 6B configuration pack required by the active `6B_spec_version` fails its own schema validation.

**Examples**

* Behaviour prior pack missing required fields or violating type constraints.
* Campaign config or labelling policy invalid under `schemas.6B.yaml`.

**Obligations**

* S0 MUST fail; 6B may not run with uncontrolled or malformed behaviour policies.

---

### 9.5 `sealed_inputs_6B` construction failures

These codes cover problems constructing the **local sealed-inputs manifest**.

#### 9.5.1 `SEALED_INPUTS_REQUIRED_ARTIFACT_MISSING`

**Definition**

Emitted when 6B’s policy marks an artefact as `REQUIRED`, but S0 cannot resolve it or verify its presence for the current fingerprint.

**Examples**

* `arrival_events_5B` not present in `sealed_inputs_5B` even though 5B is PASS.
* A required 6A entity table missing from upstream manifests.

---

#### 9.5.2 `SEALED_INPUTS_SCHEMA_VIOLATION`

**Definition**

Emitted when S0 can construct rows for `sealed_inputs_6B`, but the resulting table fails schema validation.

**Examples**

* Duplicate `(manifest_fingerprint, owner_layer, owner_segment, manifest_key)` rows.
* Row missing a required field (e.g. `schema_ref` or `sha256_hex`).
* `partition_keys` or `path_template` inconsistent with the owning segment’s dictionary.

---

#### 9.5.3 `SEALED_INPUTS_DIGEST_COMPUTE_FAILED`

**Definition**

Emitted when S0 cannot compute `sealed_inputs_digest_6B` from the persisted `sealed_inputs_6B` file.

**Examples**

* I/O error when reading the parquet file back.
* Serialisation error under the canonical encoding rule.
* Internal error in the digest calculation pipeline.

---

#### 9.5.4 `SEALED_INPUTS_DRIFT`

**Definition**

Emitted when S0 detects that `sealed_inputs_6B` has changed across invocations for the same fingerprint in a way that violates idempotence.

**Examples**

* Existing `sealed_inputs_6B` on disk differs in content (rows, order, or field values) from what S0 now computes, without a corresponding spec/contract bump.

**Obligations**

* S0 MUST NOT overwrite the existing manifest; it MUST fail and surface this as a contract drift that requires operator intervention.

---

### 9.6 Gate receipt emission & idempotence failures

These codes cover failures around writing or reconciling `s0_gate_receipt_6B`.

#### 9.6.1 `GATE_RECEIPT_SCHEMA_VIOLATION`

**Definition**

Emitted when the in-memory `s0_gate_receipt_6B` object fails validation against its schema.

**Examples**

* Missing `sealed_inputs_digest_6B`.
* `upstream_segments` missing an entry for a required segment.
* Invalid enum value for an upstream `status`.

---

#### 9.6.2 `GATE_RECEIPT_WRITE_FAILED`

**Definition**

Emitted when S0 cannot write the gate receipt to its target path for this fingerprint (I/O errors, permission issues, etc.).

**Obligations**

* S0 MUST fail and leave the state as “no valid receipt” for that fingerprint, even if `sealed_inputs_6B` was successfully written.

---

#### 9.6.3 `GATE_RECEIPT_IDEMPOTENCE_VIOLATION`

**Definition**

Emitted when a gate receipt already exists for this fingerprint and re-running S0 produces **different** content.

**Examples**

* Existing JSON differs byte-for-byte from the newly computed receipt.
* Existing receipt encodes a different `parameter_hash` or `sealed_inputs_digest_6B`.

**Obligations**

* S0 MUST NOT overwrite the existing receipt.
* S0 MUST fail with this code, as this indicates a serious contract or environment drift.

---

### 9.7 Internal / unexpected failures

#### 9.7.1 `INTERNAL_ERROR`

**Definition**

Catch-all for failures that do not fit any of the categories above and are not attributable to user/caller misconfiguration or upstream gating/state.

**Examples**

* Uncaught exceptions in S0 implementation.
* Unexpected type mismatches or panics in catalogue access layers.
* CRC errors or low-level filesystem issues not attributable to a single artefact.

**Obligations**

* S0 MUST fail and log sufficient diagnostic context for debugging.
* Future versions of this spec SHOULD refine recurring `INTERNAL_ERROR` cases into more specific codes where possible.

---

### 9.8 Surfaces & propagation

For every S0 attempt (per `manifest_fingerprint`):

* The **Layer-3 run-report** MUST record:

  * `status: "PASS"` or `"FAIL"`,
  * `primary_error_code` (if FAIL),
  * optional `secondary_error_codes`,
  * minimal context (e.g. failing segment or manifest_key if applicable).

* S0’s structured logs SHOULD emit:

  * One log event for each upstream segment gate check,
  * One log event summarising the sealed-inputs manifest construction,
  * One final log event with the primary error code on failure.

* The 6B validation state (S5) MUST:

  * Treat any non-PASS S0 for a given fingerprint as a **hard precondition failure**, mapping S0’s `primary_error_code` into its own diagnostic output (S5 MUST NOT attempt to “repair” S0).

* Orchestrators and 4A/4B MUST:

  * Use `primary_error_code` for routing and operator feedback,
  * Avoid scheduling 6B.S1–S5 for fingerprints where S0 has `status="FAIL"`.

These error codes and behaviours are binding and form part of the 6B.S0 external contract.

---

## 10. Observability & run-report integration *(Binding)*

This section defines **what 6B.S0 must expose for observability**, and **how it must appear in the engine run-report**, so that:

* operators can see **why** S0 passed or failed for a world, and
* downstream states (6B.S1–S5, 4A/4B) can reason about 6B’s gate status in a machine-readable way.

Everything here is **binding** for 6B.S0.

---

### 10.1 Run-report presence and scope

For each `manifest_fingerprint` that 6B.S0 attempts, the Layer-3 run-report **MUST** include a dedicated section for `segment=6B`, `state=S0`, containing at least:

* `manifest_fingerprint`
* `spec_version_6B`
* `parameter_hash`
* `status` — `"PASS"` or `"FAIL"`
* `primary_error_code` — one of the codes from §9 (or `null` if `status="PASS"`)
* `secondary_error_codes` — list of additional codes (possibly empty)
* `sealed_inputs_digest_6B` — the value persisted in `s0_gate_receipt_6B` (or `null` on failure before digest computation)
* `upstream_segment_summary` — a compact summary of upstream gate statuses (see §10.2)
* `sealed_inputs_summary` — key metrics about `sealed_inputs_6B` (see §10.3)

The run-report MUST treat S0 as **world-scoped**:

* There MUST be at most one S0 entry per `manifest_fingerprint`.
* S0’s run-report section MUST NOT be repeated per `seed` or `scenario_id`.

---

### 10.2 Upstream segment status summary

The run-report MUST provide a **machine-readable summary** of upstream gate status as seen by S0. At minimum:

* `upstream_segment_summary.required_segments` — array of segment ids

  * MUST contain exactly `{ "1A", "1B", "2A", "2B", "3A", "3B", "5A", "5B", "6A" }` for this spec version.

* `upstream_segment_summary.status_by_segment` — map from segment id → object with:

  * `status` — `"PASS"`, `"FAIL"`, or `"MISSING"` as determined in §6.3
  * `bundle_sha256` — 64-char hex digest S0 recomputed for the upstream bundle (or `null` if missing/invalid)
  * `flag_path` — relative path of the `_passed.flag` file S0 attempted to read (or `null` if missing)

Binding rules:

* If any segment has `status != "PASS"`, S0 **MUST** have `status="FAIL"` and an upstream-related `primary_error_code` (§9.2 / §9.3).
* If `status="PASS"` for S0, then every required segment MUST appear with `status="PASS"` and a non-null `bundle_sha256`.

This summary allows consumers to quickly answer: *“What did 6B think about each upstream gate when it ran?”*

---

### 10.3 Sealed-inputs summary

The run-report MUST expose key metrics about the constructed `sealed_inputs_6B` table for the target world. At minimum:

* `sealed_inputs_summary.total_rows` — total row count.
* `sealed_inputs_summary.rows_by_layer` — map `{ "1": int, "2": int, "3": int }`.
* `sealed_inputs_summary.rows_by_segment` — map `{ "1A": int, "1B": int, ..., "6B": int }`.
* `sealed_inputs_summary.required_rows` — count of rows with `status="REQUIRED"`.
* `sealed_inputs_summary.optional_rows` — count of rows with `status="OPTIONAL"`.
* `sealed_inputs_summary.metadata_only_rows` — count of rows with `read_scope="METADATA_ONLY"`.
* `sealed_inputs_summary.arrivals_present` — boolean flag indicating whether the manifest includes a `REQUIRED` arrival stream artefact (e.g. `arrival_events_5B`).
* `sealed_inputs_summary.entity_graph_present` — boolean flag indicating whether required entity / posture artefacts from 6A are present.

Binding rules:

* If S0 is `status="PASS"`, then:

  * `total_rows` MUST be > 0.
  * All `REQUIRED` rows MUST correspond to artefacts that exist and are accessible at runtime.

These metrics are informative but must be accurate; they are used by operators and test harnesses to detect misconfiguration (e.g. “why is 6B not seeing any upstream 6A artefacts?”).

---

### 10.4 Logging requirements

6B.S0 MUST emit **structured logs** suitable for tracing and debugging. At minimum, the state MUST log:

1. **Invocation start**

   * At the beginning of S0 evaluation for a fingerprint:

     * `event_type: "6B.S0.START"`
     * `manifest_fingerprint`
     * `spec_version_6B`
     * `parameter_hash`

2. **Upstream gate checks**

   For each required upstream segment:

   * `event_type: "6B.S0.UPSTREAM_CHECK"`
   * `owner_layer`, `owner_segment`
   * `manifest_fingerprint`
   * `check_result` — `"PASS"`, `"FAIL"`, or `"MISSING"`
   * `error_code` — if `"FAIL"` or `"MISSING"`, the specific upstream error (e.g. `UPSTREAM_HASHGATE_INVALID`)

3. **Sealed-inputs construction**

   After constructing but before persisting `sealed_inputs_6B`:

   * `event_type: "6B.S0.SEALED_INPUTS_BUILT"`
   * `manifest_fingerprint`
   * `total_rows`
   * `required_rows`
   * `optional_rows`
   * `rows_by_layer` (aggregated)

4. **Digest computation**

   After computing `sealed_inputs_digest_6B`:

   * `event_type: "6B.S0.SEALED_INPUTS_DIGEST"`
   * `manifest_fingerprint`
   * `sealed_inputs_digest_6B`

5. **Gate receipt write / idempotence**

   When writing or reconciling `s0_gate_receipt_6B`:

   * `event_type: "6B.S0.GATE_RECEIPT_WRITE"`
   * `manifest_fingerprint`
   * `action` — `"CREATE"`, `"NOOP_IDEMPOTENT"`, or `"CONFLICT"`

6. **Invocation end**

   * `event_type: "6B.S0.END"`
   * `manifest_fingerprint`
   * `status` — `"PASS"` / `"FAIL"`
   * `primary_error_code` — or `null`
   * `secondary_error_codes` — list

All logs MUST include enough context to be correlated back to the specific `manifest_fingerprint` and to support debugging of repeated/failed runs.

---

### 10.5 Metrics & SLI-style counters

6B.S0 SHOULD expose coarse metrics suitable for SLI/SLO monitoring (binding in *shape*, but not in thresholds). At minimum:

* `6B_S0_runs_total`

  * Counter; labels: `status` (`"PASS"`, `"FAIL"`).

* `6B_S0_upstream_segment_status_total`

  * Counter; labels: `owner_layer`, `owner_segment`, `status` (`"PASS"`, `"FAIL"`, `"MISSING"`).

* `6B_S0_sealed_inputs_rows_total`

  * Gauge or histogram; labels: `owner_layer`, `owner_segment`.

* `6B_S0_failure_primary_code_total`

  * Counter; label: `primary_error_code`.

These metrics allow operators to answer:

* “Are S0 runs consistently passing for new worlds?”
* “Which upstream segments frequently block 6B?”
* “Is the set of sealed inputs growing/shrinking unexpectedly?”

The specific metric backend (Prometheus, etc.) is out of scope; only the conceptual metrics and labels are binding.

---

### 10.6 Consumption by 6B.S1–S5 and 4A/4B

Downstream states and layers MUST integrate S0’s observability signals as follows:

* **6B.S1–S4 & S5:**

  * Before reading any upstream artefact, a 6B state MUST:

    * Check the run-report (or equivalent control-plane interface) to confirm S0 `status="PASS"` for the target fingerprint.
    * Optionally log a reference to the S0 run-report entry (e.g. by including the S0 `sealed_inputs_digest_6B`) when starting their own work.

  * If S0 is `FAIL` or absent, S1–S5 MUST NOT attempt to construct flows or labels and MUST fail early with a `PRECONDITION_S0_FAILED`-style code (defined in their own specs).

* **4A/4B & external consumers:**

  * For any consumption of 6B business outputs (flows, events, labels), 4A/4B MUST:

    * Verify that S0 is `PASS` for the relevant `manifest_fingerprint`.
    * Verify that the 6B segment HashGate (S5) is `PASS` (S5 spec).
    * Surface S0 status and `primary_error_code` as part of any user-facing diagnostic for 6B failures.

This ensures S0’s observability is not just “nice to have”, but actually shapes how the rest of the engine responds to gate failures.

---

### 10.7 Audit trail and reproducibility

6B.S0’s observability signals are part of the **audit trail** for behavioural runs:

* The combination of:

  * `s0_gate_receipt_6B`,
  * `sealed_inputs_6B`, and
  * the S0 run-report section

  MUST be sufficient for an auditor to answer:

  > “Given a world (`manifest_fingerprint`), which upstream segments and artefacts did 6B treat as sealed and in-scope, and which contracts did it bind to, at the time it generated behaviour?”

Any implementation of 6B.S0 MUST therefore treat run-report emission and logging as integral to the state, not as optional side effects.

---

## 11. Performance & scalability *(Informative)*

This section provides **non-binding** guidance on how to keep 6B.S0 cheap, predictable and scalable as the engine grows. It does **not** relax any binding requirements from Sections 1–10; it only suggests implementation strategies that fit within them.

---

### 11.1 Cost model — what S0 actually does

6B.S0 is deliberately **metadata-only**. Its work can be thought of as three buckets:

1. **Catalogue & contract resolution**

   * Read and parse:

     * 6B schemas, dictionary, registry.
     * Upstream segment dictionaries and registries for 1A–3B, 5A, 5B, 6A.
   * Expected size: O(hundreds–low thousands) YAML/JSON entries across the full engine.

2. **Upstream gate verification**

   * For each required upstream segment:

     * Read one bundle index file.
     * Touch each evidence file **once** to verify digests (or reuse upstream digests if those are themselves HashGated and trusted).
     * Read a single `_passed.flag` file.

   * Expected cost: O(number of evidence files in all required bundles). For a typical world, this is dominated by:

     * a small number of JSON reports / manifests,
     * a handful of RNG accounting artefacts,
     * **not** large data-plane tables.

3. **Sealed-inputs construction**

   * Read `sealed_inputs_5B`, `sealed_inputs_6A` and any other upstream manifests 6B depends on.
   * Construct `sealed_inputs_6B` in memory with O(N) rows, where N = number of artefacts 6B is allowed to see.
   * Compute `sealed_inputs_digest_6B` by reading back the parquet and serialising each row once.

   For realistic engine sizes, N is expected to be O(10²–10³); even pessimistically, O(10⁴) rows is tractable for a per-world, one-time gate.

End-to-end, runtime is roughly:

```text
O(#upstream_bundle_files + #upstream_sealed_inputs_rows + #sealed_inputs_6B_rows)
```

with constant factors dominated by filesystem I/O and (re)parsing YAML/JSON.

---

### 11.2 Expected frequency & amortisation

S0 runs **per world** (`manifest_fingerprint`), not per seed or scenario. Typical usage patterns:

* For a given world, S0 is run:

  * once as part of initial world bring-up,
  * and re-run only if:

    * contracts change (new `spec_version_6B`), or
    * upstream bundles / sealed-inputs surfaces are regenerated.

* For multiple seeds or scenarios in 6B.S1–S4:

  * S0’s cost is amortised; downstream states only pay the per-seed/per-scenario data-plane cost, not repeated gating.

Implementers SHOULD aim to:

* Run S0 **once per world** by default, and
* Treat non-idempotent re-runs as exceptional (see Section 7).

---

### 11.3 Catalogue & schema caching (in-process)

Because S0 operates almost entirely on control-plane artefacts, implementations SHOULD:

* **Cache parsed schemas in-process** for the duration of a run:

  * `schemas.layer1.yaml`, `schemas.layer2.yaml`, `schemas.layer3.yaml`, `schemas.6B.yaml`.
  * Avoid re-parsing the same schema pack for each upstream segment.

* **Cache dictionary/registry lookups**:

  * Build in-memory maps keyed by `(owner_layer, owner_segment, manifest_key)` that can be reused across:

    * upstream gate verification, and
    * sealed-inputs construction.

* **Avoid deep recursive `$ref` re-resolution**:

  * Most S0 validation is on small control-plane objects; using a schema resolver with memoisation reduces repeated work.

These optimisations are internal and MUST NOT alter the externally visible behaviour.

---

### 11.4 HashGate verification strategies

Upstream HashGate verification can be a noticeable cost if bundles contain many files. To keep this manageable:

* **Trust existing upstream digests where possible**
  If a segment’s own HashGate already covers a large dataset (e.g. a bundle that includes `sealed_inputs_*` and RNG accounting), S0 does **not** need to re-hash those large datasets; it only needs to:

  * validate the segment’s bundle index,
  * recompute digests for the evidence files named there, and
  * confirm that the upstream `_passed.flag` matches.

* **Avoid double-hashing data-plane datasets**
  S0 should never hash large data-plane tables (e.g. `arrival_events_5B`), only the **control artefacts** that upstream segments expose to prove those tables are valid.

* **Batch file I/O where available**
  If the runtime supports it, S0 can:

  * prefetch multiple index/evidence files,
  * or parallelise digest computations across CPU cores.

These are optimisations; S0’s correctness does not depend on parallelism, and S0 MUST remain deterministic under any scheduling.

---

### 11.5 `sealed_inputs_6B` size considerations

`sealed_inputs_6B` grows with:

* the number of segments in the engine, and
* the number of artefacts each segment exposes for downstream consumption.

To keep this manageable:

* **Keep the manifest at the artefact level, not per-partition level**

  * A single row in `sealed_inputs_6B` can describe:

    * an entire dataset family (`arrival_events_5B`) with `partition_keys: ["seed", "fingerprint", "scenario_id"]`,
    * rather than one row per `(seed, scenario_id)` file.

  * Detailed partition metadata (per-seed/per-scenario) can remain in upstream segments’ own manifests (e.g. 5B’s sealed-inputs).

* **Avoid listing internal scratch datasets**

  * Only list artefacts that 6B actually reads or needs to refer to for validation.
  * Scratch/intermediate datasets that are not exposed to 6B SHOULD remain internal to their segments and excluded from `sealed_inputs_6B`.

These choices reduce manifest size and make digest computation inexpensive.

---

### 11.6 I/O patterns and locality

To limit I/O overhead:

* **Group control-plane artefacts by fingerprint**

  * Upstream bundles and sealed-inputs are already partitioned by `fingerprint`.
  * S0 benefits if these directories reside in the same locality (e.g. same storage bucket / volume) to reduce latency.

* **Sequence I/O to avoid thrash**

  * Verify all upstream HashGates first (control-plane only).
  * Then read required upstream `sealed_inputs_*`.
  * Finally, write and re-read `sealed_inputs_6B` once to compute its digest.

* **Keep S0 stateless across fingerprints**

  * Avoid global caches that mix state from different worlds; this simplifies concurrency and reduces risk of cross-world contamination.

---

### 11.7 Concurrency & contention

S0 is fingerprint-scoped and naturally parallelisable across worlds:

* It is safe to run **multiple S0 instances in parallel** for different `manifest_fingerprint` values, provided:

  * each instance writes only to its own `fingerprint={manifest_fingerprint}` partitions, and
  * the underlying storage permits such concurrent writes.

* Implementations SHOULD avoid parallel S0 runs for the **same** fingerprint:

  * This increases the chance of idempotence conflicts.
  * If parallel invocations are unavoidable (e.g. due to orchestration retries), they SHOULD coordinate via a higher-level lock or by letting one invocation “win” and the others detect the existing gate receipt and no-op.

No part of this concurrency behaviour changes the single-writer/idempotence rules in Section 7.

---

### 11.8 Memory footprint

S0’s memory usage is dominated by:

* Parsed schemas and dictionaries (shared with other states in the same process).
* In-memory representation of:

  * the upstream `upstream_segments` map (small),
  * the `CANDIDATE_ARTIFACTS` set / `sealed_inputs_6B` row model (up to O(10³–10⁴ rows).

Guidance:

* Implementations SHOULD stream large upstream manifests where possible (e.g. read `sealed_inputs_5B` in chunks, filter to the artefacts 6B needs) rather than loading them entirely if they become large.
* `sealed_inputs_6B` itself is expected to be small enough to keep in memory for sorting and digest computation.

---

### 11.9 Impact on end-to-end pipeline

In the overall pipeline:

* S0’s cost is typically **small** compared to:

  * 5A (intensity surfaces over large merchant×zone×time domains),
  * 5B (arrival generation),
  * 6A (entity/graph construction), and
  * future 6B states (flow/campaign/label generation over potentially millions of arrivals).

However, because S0 is a **hard gate**:

* If S0 becomes significantly slower than expected (e.g. due to growing upstream bundles or poor I/O locality), it can delay all subsequent behaviour and validation for that world.
* Implementations SHOULD therefore monitor S0 latency as an SLI and treat regressions as a signal to:

  * prune unnecessary artefacts from `sealed_inputs_6B`,
  * tighten upstream bundled evidence to only what is needed for HashGates,
  * or optimise cataloguing/storage patterns.

None of these tuning measures may relax the binding correctness and determinism rules from Sections 1–10; they are purely about keeping S0 light enough that it is never the bottleneck for bringing a new world online.

---

## 12. Change control & compatibility *(Binding)*

This section defines how the 6B.S0 contract may evolve over time, and what counts as a **backwards-compatible** vs **breaking** change. It is binding on:

* authors of future 6B specs,
* implementers of 6B.S0, and
* downstream consumers (6B.S1–S5, 4A/4B, orchestration).

The goal is that:

* existing worlds and runs remain **replayable**, and
* consumers can safely decide which versions of 6B.S0 they support.

---

### 12.1 Version identifiers and scope

6B.S0 participates in three version tracks:

1. `spec_version_6B`

   * A logical version string (e.g. `1.0.0`, `1.1.0`) carried in `s0_gate_receipt_6B`.
   * Identifies the **behavioural contract version** for 6B as a whole (S0–S5), not just S0.

2. Schema pack versions

   * `schemas.layer3.yaml` and `schemas.6B.yaml` each carry their own `$id` / versioning.
   * Changes to the shapes of `s0_gate_receipt_6B` or `sealed_inputs_6B` MUST be reflected here.

3. Catalogue versions

   * `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml` evolve as new datasets/artefacts are introduced.

Binding rules:

* For any given run of 6B.S0, the triple `(spec_version_6B, schemas.layer3.yaml version, schemas.6B.yaml version)` MUST be internally consistent and MUST be discoverable from the catalogue.
* The **behavioural contract** described in this document corresponds to a specific `spec_version_6B` (e.g. `"1.0.0"`); any incompatible change MUST bump this version.

---

### 12.2 Backwards-compatible changes

A change is considered **backwards-compatible** with respect to 6B.S0 if:

* Existing consumers (6B.S1–S5, 4A/4B, orchestration) operating under the previous `spec_version_6B`:

  * can still parse `s0_gate_receipt_6B` and `sealed_inputs_6B`, and
  * can still apply the same gating logic (Sections 8–10) without modification.

**Examples of allowed backwards-compatible changes:**

1. **Adding optional fields**

   * Adding new, optional fields to the `s0_gate_receipt_6B` schema (e.g. extra metadata under `contracts_6B` or an `"extra"` object).
   * Adding optional, nullable columns to `sealed_inputs_6B` with defaults that do not change interpretation of existing rows.

2. **Adding new artefacts with `status="OPTIONAL"`**

   * Registering new `manifest_key`s (e.g. new diagnostic datasets) in `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml`.
   * Including these in `sealed_inputs_6B` as `status="OPTIONAL"` and with roles that downstream states can ignore.

3. **Extending role enums conservatively**

   * Adding new `role` enum values for `sealed_inputs_6B` that are not used by existing downstream states.
   * Existing states may treat unknown roles as `OTHER` or ignore them.

4. **Enhancing run-report / metrics detail**

   * Adding new fields to the run-report S0 section or new metrics/counters, provided existing fields retain their meaning and remain present.

Backwards-compatible changes MAY be introduced under a **minor** `spec_version_6B` bump (e.g. `1.0.0 → 1.1.0`), provided all binding behaviour described in Sections 1–11 is preserved.

---

### 12.3 Breaking changes

A change is **breaking** if it can cause:

* an implementation of 6B.S1–S5 built against an older S0 contract to misinterpret S0 outputs,
* an existing world replay (for a given `manifest_fingerprint`) to produce different gate decisions or input inventories without an explicit version bump, or
* 4A/4B and orchestration to mis-gate 6B.

**Examples of breaking changes:**

1. **Removing or renaming required fields**

   * Removing any required field from `s0_gate_receipt_6B` (e.g. `sealed_inputs_digest_6B`, `upstream_segments`, `contracts_6B`).
   * Renaming or changing the type of required fields in `sealed_inputs_6B` (`manifest_fingerprint`, `owner_layer`, `owner_segment`, `manifest_key`, `path_template`, `schema_ref`, `status`, `read_scope`, `sha256_hex`).

2. **Changing semantics of enums**

   * Changing the meaning of `status="REQUIRED"`, `status="OPTIONAL"`, or `status="IGNORED"`.
   * Changing the semantics of `read_scope` values (`ROW_LEVEL`, `METADATA_ONLY`).
   * Reusing existing role names for different semantics.

3. **Changing identity / partition laws**

   * Changing the partitioning of S0 outputs from `[fingerprint]` to any other key set.
   * Introducing `seed` or `scenario_id` as additional partitioning dimensions for `s0_gate_receipt_6B` or `sealed_inputs_6B`.
   * Making `manifest_fingerprint` nullable or non-unique in S0 outputs.

4. **Changing digest or idempotence behaviour**

   * Changing the hashing law used for `sealed_inputs_digest_6B` without updating `spec_version_6B` and schema anchors.
   * Allowing S0 re-runs to overwrite existing receipts/manifests with different content for the same `(manifest_fingerprint, spec_version_6B)`.

5. **Modifying gating rules**

   * Changing which upstream segments are treated as required (e.g. making 5B optional) without a spec version bump.
   * Changing the rule that 6B.S1–S5 MUST NOT run unless S0 is PASS for the target fingerprint.
   * Allowing 6B to read artefacts not present in `sealed_inputs_6B`.

Any such change MUST be treated as a **new major** `spec_version_6B` (e.g. `1.x → 2.0.0`) and MUST be accompanied by:

* updated schema anchors,
* updated dictionary/registry entries,
* updated 6B.S1–S5 specs that document how to consume the new S0 outputs, and
* migration guidance (see §12.4).

---

### 12.4 Migration & co-existence

Because worlds and downstream pipelines may be pinned to different contracts, 6B.S0 MUST support **co-existence** of multiple spec versions and schemas over time.

Binding rules:

1. **Version-aware orchestration**

   * Orchestrators MUST decide which `spec_version_6B` to use per `manifest_fingerprint` (or per environment), based on configuration.
   * They MUST NOT attempt to run multiple S0 versions concurrently for the same fingerprint under the same logical deployment.

2. **Schema anchors & dictionary**

   * When introducing a new major `spec_version_6B`, new schema anchors MAY be added under `schemas.layer3.yaml` and `schemas.6B.yaml` (e.g. `#/gate/6B/v2/s0_gate_receipt_6B`).
   * The dataset dictionary MAY either:

     * switch `schema_ref` to the new anchor (for new deployments), or
     * create separate dataset IDs for the new contract version (e.g. `s0_gate_receipt_6B_v2`) and allow both to co-exist.

3. **Read-only compatibility for old worlds**

   * Once a world has been processed under an older `spec_version_6B`, its S0 outputs MUST remain **readable and reproducible**.
   * New 6B implementations MAY choose to support reading old receipts/manifests for diagnostic or migration purposes, but MUST NOT silently reinterpret them under the new rules.

4. **Forward-compatibility expectations**

   * S0 outputs SHOULD be designed so that newer 6B.S1–S5 implementations can:

     * ignore unknown fields in `s0_gate_receipt_6B`,
     * ignore unknown roles or optional fields in `sealed_inputs_6B`,
     * and still apply safe gating logic.

   * Conversely, older implementations MUST NOT be expected to parse receipts/manifests from a newer major `spec_version_6B` without explicit compatibility code.

---

### 12.5 Evolving upstream dependencies

6B.S0 depends on a fixed set of upstream segments in this version: `{1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B, 6A}`.

Binding rules for changes:

1. **Adding new upstream segments**

   * Making a new upstream HashGate a **required** precondition for 6B.S0 (e.g. a new Layer-2 segment) is a breaking change and MUST be accompanied by a new `spec_version_6B`.
   * New upstream segments MAY be integrated as **optional** sources (e.g. additional control-plane manifests) in a backwards-compatible way, provided:

     * they are treated as `status="OPTIONAL"` in `sealed_inputs_6B`, and
     * S0 acceptance criteria do not depend on their presence.

2. **Upstream schema / bundle changes**

   * If an upstream segment changes its validation bundle or `_passed.flag` schema in a backwards-compatible way (e.g. extra optional fields), S0 MAY adopt that change without a `spec_version_6B` bump.
   * If an upstream segment changes its hashing law or semantics in a breaking way, 6B.S0 MUST either:

     * bump `spec_version_6B` and explicitly document the new dependency, or
     * maintain compatibility code that can verify both old and new formats during a transition period.

3. **Upstream sealed-inputs changes**

   * If upstream `sealed_inputs_*` schemas expand in a backwards-compatible way, S0 MAY ignore the new fields or incorporate them as optional metadata.
   * If upstream sealed-inputs semantics change (e.g. different interpretation of rows), S0 MUST be updated accordingly and this spec MUST be revised.

---

### 12.6 Run-report & error code evolution

The run-report and error code shapes are part of the external contract.

* Adding new **secondary error codes** or additional context fields in the run-report is backwards-compatible.
* Removing existing primary error codes, or changing their meaning, is breaking and MUST be accompanied by:

  * a new `spec_version_6B`,
  * run-report schema changes, and
  * updated documentation for orchestrators and operators.

Consumers SHOULD be written to:

* treat unknown secondary error codes as opaque but ignorable, and
* key their logic only on primary error codes they explicitly recognise.

---

### 12.7 Non-negotiable stability points

The following aspects of 6B.S0 are explicitly designated as **stable** for the lifetime of this `spec_version_6B` and MUST NOT change without a major version bump:

* S0 produces exactly two datasets: `s0_gate_receipt_6B` and `sealed_inputs_6B`.
* Both are partitioned solely by `[fingerprint]`.
* `sealed_inputs_6B` is the **exclusive** inventory of artefacts that 6B is allowed to read.
* S1–S5 MUST gate on S0 PASS and use `sealed_inputs_6B` to resolve inputs.
* S0 is RNG-free, metadata-only, and treats upstream HashGates as authoritative.

Any future 6B.S0 variant that wishes to relax or change these stability points MUST:

* define a new major `spec_version_6B`,
* update schema anchors and catalogue entries, and
* provide explicit migration guidance from this contract to the new one.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the symbols and abbreviations used in the 6B.S0 specification. It is **informative** only; where there is any tension, the binding sections §1–§12 take precedence.

---

### 13.1 Identity & versioning

* **`manifest_fingerprint` / `fingerprint`**
  The world snapshot identifier. A stable hash (e.g. 64-char hex) that uniquely identifies a sealed engine “world” across Layers 1–3. Used as:

  * the partition key for S0 outputs, and
  * the scope for upstream HashGates (`validation_bundle_*` + `_passed.flag`).

* **`parameter_hash`**
  Hash of the configuration / parameter pack used by 6B (behaviour priors, campaign configs, labelling policies, validation policy, etc.). S0 records it in `s0_gate_receipt_6B` but does not interpret it.

* **`spec_version_6B`**
  The behavioural contract version for 6B as a whole (S0–S5). Used by S0 to bind to the correct schema packs, dictionaries and registries.

* **`owner_layer`**
  Integer layer identifier (`1`, `2`, or `3`) indicating which layer owns a given artefact listed in `sealed_inputs_6B`.

* **`owner_segment`**
  Segment identifier string for the owning segment of an artefact, e.g. `"1A"`, `"1B"`, `"2A"`, `"2B"`, `"3A"`, `"3B"`, `"5A"`, `"5B"`, `"6A"`, `"6B"`.

* **`manifest_key`**
  Logical key for an artefact as used in its owning segment’s artefact registry (e.g. `arrival_events_5B`, `s1_party_base_6A`, `behaviour_prior_pack_6B`). Combined with `(manifest_fingerprint, owner_layer, owner_segment)` it uniquely identifies a row in `sealed_inputs_6B`.

---

### 13.2 Datasets, artefacts & paths

* **Dataset dictionary**
  YAML file (e.g. `dataset_dictionary.layer3.6B.yaml`) that defines:

  * dataset ids,
  * `path` and `partitioning`,
  * `schema_ref`,
  * primary keys and writer ordering,
  * `produced_by` / `consumed_by` relationships.

* **Artefact registry**
  YAML file (e.g. `artefact_registry_6B.yaml`) that lists concrete artefacts (datasets, bundles, flags) with:

  * `manifest_key`,
  * `schema`,
  * `path_template`,
  * `partitioning`,
  * `category` / `role`,
  * `final_in_layer` / `cross_layer` flags.

* **`path_template`**
  A string with placeholder tokens (e.g. `seed={seed}`, `fingerprint={manifest_fingerprint}`, `scenario_id={scenario_id}`) that describes where an artefact is stored.

* **`partition_keys`**
  Ordered list of logical partition columns required to read an artefact (e.g. `["seed","fingerprint"]`, `["fingerprint"]`).

* **`schema_ref`**
  A JSON-Schema `$ref` string pointing into a schema pack (e.g. `schemas.layer3.yaml#/gate/6B/sealed_inputs_6B`, `schemas.5B.yaml#/s4/arrival_events_5B`).

* **`role` (in sealed_inputs)**
  Short classification of an artefact from 6B’s perspective, e.g.:

  * `arrival_stream` — arrivals from 5B,
  * `entity_graph` — 6A entities / links,
  * `static_posture` — 6A fraud-role surfaces,
  * `behaviour_prior`, `campaign_config`, `labelling_policy`, `validation_policy`,
  * `sealed_inputs_upstream`, `validation_bundle`, `other`.

---

### 13.3 Status & scope flags

* **`status` (in sealed_inputs)**
  6B’s requirement level for a particular artefact:

  * `REQUIRED` — must exist and be readable; absence is fatal for S0.
  * `OPTIONAL` — nice-to-have; absence does not cause S0 to fail, but downstream states must handle it gracefully.
  * `IGNORED` — listed only for completeness; 6B.S1–S4 must not read it.

* **`read_scope`**
  Allowed access mode for 6B:

  * `ROW_LEVEL` — 6B states may read full rows from this dataset.
  * `METADATA_ONLY` — 6B may only use metadata (existence, digest, size) but must not scan rows.

* **`sha256_hex`**
  Hex-encoded SHA-256 digest of an artefact’s canonical serialisation, as defined by the owning segment or policy. Used in `sealed_inputs_6B`, upstream bundles, and 6B’s own receipt.

---

### 13.4 Upstream gates & bundles

* **HashGate**
  The combination of:

  * a validation bundle directory (evidence files + an index), and
  * a `_passed.flag` file containing the bundle digest.
    When verified, it establishes a sealed contract for an upstream segment at a given `manifest_fingerprint`.

* **`validation_bundle_*`**
  A directory of validation artefacts for a segment and fingerprint (e.g. `validation_bundle_5B`). Typically includes:

  * `index.json`,
  * validation reports,
  * optional issue tables and RNG accounting.

* **`validation_passed_flag_*` / `_passed.flag`**
  A small text file, usually with a single line `sha256_hex = <digest>`, whose digest must match the recomputed digest of the validation bundle contents according to that segment’s law.

* **`sealed_inputs_*` (upstream)**
  Sealed-inputs manifests from upstream segments (e.g. `sealed_inputs_5B`, `sealed_inputs_6A`) describing which artefacts those segments read and/or expose, per `manifest_fingerprint`.

---

### 13.5 6B.S0 outputs & digests

* **`s0_gate_receipt_6B`**
  Fingerprint-scoped JSON document that records:

  * upstream segment statuses and bundle digests,
  * the 6B contract set (schemas, dictionary, registry, config packs),
  * `parameter_hash`, `spec_version_6B`,
  * and `sealed_inputs_digest_6B`.

* **`sealed_inputs_6B`**
  Fingerprint-scoped parquet table where each row describes one artefact that 6B is authorised to read:

  * identity (`manifest_fingerprint`, `owner_layer`, `owner_segment`, `manifest_key`),
  * location (`path_template`, `partition_keys`),
  * schema (`schema_ref`),
  * policy (`role`, `status`, `read_scope`),
  * integrity (`sha256_hex`).

* **`sealed_inputs_digest_6B`**
  SHA-256 digest summarising the on-disk contents of `sealed_inputs_6B` for a given fingerprint, using a canonical row ordering and serialisation. Stored in `s0_gate_receipt_6B` and used by downstream validation as an integrity anchor.

---

### 13.6 States & shorthand

* **6B.S0**
  Behavioural universe gate & sealed inputs (this state).

* **6B.S1–S4**
  Later 6B states (not defined in this doc) responsible for:

  * S1 — attaching arrivals to entities and sessions,
  * S2 — building baseline flows,
  * S3 — overlaying fraud/abuse campaigns,
  * S4 — assigning labels and outcomes.

* **6B.S5**
  6B segment validation / HashGate state that will:

  * depend on S0 outputs, and
  * publish `validation_bundle_6B` + `_passed.flag`.

* **S0 “PASS” / “FAIL”**
  Run-level status for 6B.S0 in the Layer-3 run-report for a given `manifest_fingerprint`. Determines whether downstream 6B states may run.

---

### 13.7 Error codes & observability (names only)

For convenience, the primary error codes from §9 are summarised here (semantics remain defined in §9):

* Upstream gates:

  * `UPSTREAM_HASHGATE_MISSING`
  * `UPSTREAM_HASHGATE_INVALID`
  * `UPSTREAM_VALIDATION_NONPASS`

* Upstream sealed-inputs:

  * `UPSTREAM_SEALED_INPUTS_MISSING`
  * `UPSTREAM_SEALED_INPUTS_INVALID`

* 6B contracts & configs:

  * `CONTRACT_SET_INCOMPLETE`
  * `SCHEMA_ANCHOR_UNRESOLVED`
  * `CONFIG_VALIDATION_FAILED`

* 6B sealed-inputs:

  * `SEALED_INPUTS_REQUIRED_ARTIFACT_MISSING`
  * `SEALED_INPUTS_SCHEMA_VIOLATION`
  * `SEALED_INPUTS_DIGEST_COMPUTE_FAILED`
  * `SEALED_INPUTS_DRIFT`

* Gate receipt & idempotence:

  * `GATE_RECEIPT_SCHEMA_VIOLATION`
  * `GATE_RECEIPT_WRITE_FAILED`
  * `GATE_RECEIPT_IDEMPOTENCE_VIOLATION`

* Catch-all:

  * `INTERNAL_ERROR`

These symbols and abbreviations are intended purely as a convenience map: they do not introduce new behaviour beyond what is already specified in the binding sections.

---
