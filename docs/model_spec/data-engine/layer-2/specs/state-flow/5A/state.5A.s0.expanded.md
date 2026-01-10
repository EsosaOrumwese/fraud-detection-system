# 5A.S0 — Gate & sealed inputs (Layer-2 / Segment 5A)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5A.S0 — Gate & Sealed Inputs** for **Layer-2 / Segment 5A**. It is binding on any implementation of this state.

### 1.1 Role of 5A.S0 in the engine

5A.S0 is the **entry gate** and **closed-world definition** for Segment 5A.

For a given `(parameter_hash, manifest_fingerprint)` it:

* **Verifies upstream readiness**
  Confirms that all required Layer-1 segments (1A–3B) have successfully completed and published their own validation bundles and `_passed.flag` artefacts for the same `manifest_fingerprint`.

* **Pins the 5A input universe**
  Resolves and records the **exact set of artefacts** that 5A is allowed to read for this fingerprint, across:

  * upstream Layer-1 outputs (e.g. merchant catalogue and world surfaces),
  * Layer-1 / engine-wide reference data,
  * Layer-2–wide configuration and policy packs (scenario calendar, classing rules, shape library configs, etc.).

* **Emits control-plane datasets**
  Produces small, fingerprint-scoped control datasets that downstream 5A states use as their *only* authority for:

  * which upstream segments are considered valid for this run, and
  * which artefacts are in-scope for 5A (and under which schema/version/digest).

5A.S0 is **RNG-free** and **does not produce any intensity surfaces**. It deals only with identity, catalogue resolution, and governance metadata.

### 1.2 Objectives

5A.S0 MUST:

* **Establish a clear trust boundary** for 5A by:

  * enforcing **“No upstream PASS → No 5A read”** for the set of required Layer-1 segments; and
  * refusing to proceed if any required upstream validation bundle or `_passed.flag` is missing, inconsistent, or invalid.

* **Define a sealed input universe** for 5A by:

  * discovering eligible inputs via the Layer-2 and Layer-1 dataset dictionaries and artefact registries, not via ad-hoc paths;
  * materialising a **sealed inventory** of those inputs (logical IDs, schema_refs, digests, roles); and
  * making that inventory available to all later 5A states as a single source of truth.

* **Minimise downstream coupling** by:

  * summarising upstream state in a compact **gate receipt** structure, instead of requiring 5A.S1+ to understand every upstream bundle format;
  * exposing only the identifiers and digests that later states need to prove consistency, not their internal layouts.

* **Remain lightweight and deterministic** by:

  * operating almost entirely over metadata (bundle indices, dictionary/registry entries, small configs);
  * never reading bulk egress tables (e.g. Layer-1 fact tables) at row-level; and
  * performing no random sampling, numerical modelling, or intensity computation.

### 1.3 In-scope behaviour

The following activities are **in scope** for 5A.S0 and MUST be handled by this state (not duplicated elsewhere in 5A):

* **Run identity resolution**
  Resolving and recording the `(parameter_hash, manifest_fingerprint, run_id)` triple for the 5A run, and linking it to the engine-level manifest or run-report context.

* **Upstream validation verification**
  For each required upstream segment (1A, 1B, 2A, 2B, 3A, 3B), re-verifying that:

  * its validation bundle exists for the given `manifest_fingerprint`;
  * its `_passed.flag` is present and structurally valid; and
  * the flag digest matches the bundle contents according to that segment’s hashing law.

* **Catalogue-driven input discovery**
  Using only the dataset dictionaries and artefact registries to:

  * discover which candidate artefacts are eligible as inputs to 5A;
  * resolve their logical IDs, physical paths, schema_refs, and digests;
  * determine which of those belong to the current `parameter_hash` and `manifest_fingerprint`.

* **Sealed inventory construction**
  Constructing `sealed_inputs_5A` as a fingerprint-scoped inventory of all artefacts that 5A.S1+ MAY read, including:

  * upstream egresses and references (e.g. merchant catalogue, zone allocation, civil-time surfaces),
  * scenario/calendar configs,
  * 5A-specific classing and shape policies.

* **Gate receipt emission**
  Constructing `s0_gate_receipt_5A` as a compact, schema-governed object that:

  * records which upstream segments were verified and at which catalog versions,
  * records which scenario ID(s) and parameter pack(s) are bound to this fingerprint,
  * links to the corresponding `sealed_inputs_5A` inventory.

### 1.4 Out-of-scope behaviour

The following activities are explicitly **out of scope** for 5A.S0 and MUST NOT be performed by this state:

* **Row-level data processing**
  S0 MUST NOT:

  * scan bulk rows from Layer-1 egress tables (e.g. `site_locations`, `site_timezones`, `zone_alloc`);
  * aggregate or transform merchant/site/zone-level facts; or
  * compute any intensities, weekly shapes, or calendar overlays.

* **Random number generation**
  S0 MUST NOT:

  * consume any RNG streams,
  * emit RNG events, or
  * alter RNG budgets or envelopes.

* **Scenario or model semantics**
  S0 MUST NOT:

  * assign merchants to demand classes;
  * select or compose shape functions;
  * interpret scenario semantics (e.g. “Black Friday uplift”) beyond recording which scenario IDs/configs are sealed.
    Those responsibilities belong to later 5A states.

* **Segment-level PASS for 5A**
  S0 does not decide whether Segment 5A as a whole is “green” for consumption.
  It participates in the later segment-level validation bundle by producing its own outputs, but the final **segment-level PASS / FAIL** for 5A is owned by a later 5A validation state.

### 1.5 Downstream obligations

This specification sets the following obligations on downstream 5A states (to be elaborated in later sections, but motivated here):

* Any state **5A.S1 or later MUST**:

  * check for a valid `s0_gate_receipt_5A` for the target `manifest_fingerprint` before reading any upstream artefacts; and
  * restrict itself to artefacts listed in `sealed_inputs_5A` for that fingerprint.

* If `s0_gate_receipt_5A` or `sealed_inputs_5A` is missing, invalid, or inconsistent for a given `(parameter_hash, manifest_fingerprint)`, later 5A states MUST treat this as a **hard precondition failure** and MUST NOT attempt to infer or widen their input universe.

Within this scope, 5A.S0 fully defines the **entry conditions** under which Segment 5A is permitted to run, without re-interpreting any upstream semantics or performing unnecessary computation.

---

### Cross-Layer Inputs (Segment 5A)

**Upstream segments required:** 1A–3B validation bundles + `_passed.flag` (1A, 1B, 2A, 2B, 3A, 3B), plus Layer-1 egress inputs (`outlet_catalogue`, `site_locations`, `site_timezones`, `tz_timetable_cache`, 2B routing surfaces, 3A zone allocation, 3B virtual surfaces).

**External references/configs (sealed by S0 and listed in `sealed_inputs_5A`):**
* `merchant_class_policy_5A`, `demand_scale_policy_5A`, `baseline_intensity_policy_5A`
* `shape_library_5A`, `shape_time_grid_policy_5A`, `zone_shape_modifiers_5A` (optional)
* `scenario_horizon_config_5A`, `scenario_metadata`, `scenario_calendar_5A`
* `scenario_overlay_policy_5A`, `overlay_ordering_policy_5A` (optional), `scenario_overlay_validation_policy_5A` (optional)
* `validation_policy_5A` (optional), `spec_compatibility_config_5A` (optional)

**Gate expectations:** 1A–3B PASS gates (`validation_bundle_*` + `_passed.flag`) MUST verify before any 5A read for the target `manifest_fingerprint`.

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
* `outlet_catalogue` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `site_locations` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `site_timezones` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `tz_timetable_cache` - scope: FINGERPRINT_SCOPED; sealed_inputs: optional
* `s1_site_weights` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `s2_alias_index` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `s2_alias_blob` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `s3_day_effects` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `s4_group_weights` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `zone_alloc` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `zone_alloc_universe_hash` - scope: FINGERPRINT_SCOPED; sealed_inputs: required
* `virtual_classification_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `virtual_settlement_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional
* `edge_catalogue_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `edge_alias_index_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `edge_alias_blob_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `edge_universe_hash_3B` - scope: FINGERPRINT_SCOPED; sealed_inputs: required
* `merchant_class_policy_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `demand_scale_policy_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `baseline_intensity_policy_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `shape_library_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `shape_time_grid_policy_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `zone_shape_modifiers_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: optional
* `scenario_horizon_config_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `scenario_metadata` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `scenario_calendar_5A` - scope: FINGERPRINT_SCOPED; scope_keys: [manifest_fingerprint, scenario_id]; sealed_inputs: required
* `scenario_overlay_policy_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `overlay_ordering_policy_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: optional
* `scenario_overlay_validation_policy_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: optional
* `validation_policy_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: optional
* `spec_compatibility_config_5A` - scope: UNPARTITIONED (sealed policy); sealed_inputs: optional

**Authority / ordering:**
* S0 defines no data ordering; it only seals inputs and verifies upstream gate evidence.

**Outputs:**
* `s0_gate_receipt_5A` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `sealed_inputs_5A` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `scenario_manifest_5A` - scope: FINGERPRINT_SCOPED; gate emitted: none (optional)

**Sealing / identity:**
* External inputs (upstream gates, egress, and sealed policies/refs) MUST appear in `sealed_inputs_5A` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing/invalid gate evidence or required sealed inputs -> abort; no outputs published.

## 2. Preconditions & upstream validity *(Binding)*

This section defines the conditions under which **5A.S0 — Gate & Sealed Inputs** is permitted to execute, and what “upstream validity” means for Layer-2 / Segment 5A. These requirements are **binding** on any implementation.

---

### 2.1 Invocation context

5A.S0 MUST only be invoked in the context of a well-defined engine run, characterised by at least:

* A concrete **`parameter_hash`**
  – identifying the parameter pack (including 5A policies, shape libraries, scenario configs) that the engine has selected.

* A concrete **`manifest_fingerprint`**
  – identifying the closed-world manifest for this run, as defined by the engine’s global manifest hashing law.

* A concrete **`run_id`**
  – uniquely identifying this execution instance among all runs sharing the same `(parameter_hash, manifest_fingerprint)`.

The invocation context MAY include additional engine-level metadata (scenario labels, environment, operator, CI build ID, etc.), but those are non-binding for S0 so long as `(parameter_hash, manifest_fingerprint, run_id)` are present and immutable for the duration of the state.

---

### 2.2 Catalogue and contract availability

Before 5A.S0 begins, the following MUST be true:

1. **Layer-wide contracts are present and compatible**

   * The **Layer-1 wide schema bundle** (e.g. `schemas.layer1.yaml` and `schemas.ingress.layer1.yaml`) MUST be available and schema-valid for this engine deployment.
   * The **Layer-2 wide schema bundle** (e.g. `schemas.layer2.yaml`) and the **Segment 5A schema bundle** (e.g. `schemas.5A.yaml`) MUST be available and mutually consistent (no duplicate `$id`, anchors resolve, required `$defs` exist).

2. **Dataset dictionaries are deployed**

   * Dataset dictionaries for **Layer-1 segments 1A–3B** (e.g. `dataset_dictionary.layer1.1A.yaml`, …, `dataset_dictionary.layer1.3B.yaml`) MUST be present and parseable.
   * The dataset dictionary for **Layer-2 / Segment 5A** (e.g. `dataset_dictionary.layer2.5A.yaml`) MUST be present and reference only valid schema anchors.

3. **Artefact registries are deployed**

   * Artefact registries for **1A–3B** (e.g. `artefact_registry_1A.yaml`, …, `artefact_registry_3B.yaml`) MUST be present and internally consistent with their corresponding dataset dictionaries and schemas.
   * The artefact registry for **5A** (e.g. `artefact_registry_5A.yaml`) MUST be present and consistent with `dataset_dictionary.layer2.5A.yaml`.

4. **No direct-path or network dependencies**

   * The runtime environment for 5A.S0 MUST provide access to all of the above via the catalogue abstraction (dictionary + registry) only.
   * S0 MUST NOT rely on hard-coded filesystem paths, ad-hoc network calls, or external service discovery mechanisms to locate upstream artefacts.

If any of these catalogue/contract preconditions are not met, 5A.S0 MUST fail fast with an appropriate canonical error (see §9), and MUST NOT attempt to infer or reconstruct missing contracts at runtime.

---

### 2.3 Required upstream segments

5A is a Layer-2 segment that sits conceptually “above” all Layer-1 segments. For a given `manifest_fingerprint`, 5A.S0 is responsible for *verifying* the status of the following upstream segments:

* **1A – Merchant to country/outlet catalogue**
* **1B – Site geolocation**
* **2A – Civil time / `site_timezones`**
* **2B – Routing weights, alias tables, day-effects**
* **3A – Merchant zone allocation / `zone_alloc`**
* **3B – Virtual merchants & CDN edge universe**

5A.S0 MUST be able to **discover** the validation bundle and `_passed.flag` artefacts for each of these segments via the Layer-1 dataset dictionaries and artefact registries for the target `manifest_fingerprint`.

**Precondition (discoverability, not success):**

* For each upstream segment in the list above, the corresponding dictionary/registry entries for:

  * `validation_bundle_*` and
  * `_passed.flag`

  MUST resolve to a unique, concrete dataset definition (schema_ref, partitioning, manifest_key) which in turn maps to a physical location under `manifest_fingerprint={manifest_fingerprint}`.

It is **not** a precondition that all upstream segments have actually passed; S0’s job is to inspect and verify that status. It **is** a precondition that their validation artefacts are addressable in the catalogue.

---

### 2.4 Upstream validity requirements (for downstream 5A states)

While S0 itself may execute purely to *determine* upstream status, the following upstream validity conditions are **binding preconditions** for any later 5A state (S1+), and S0 is the state that checks and records them:

* For each of 1A, 1B, 2A, 2B, 3A, 3B:

  1. A validation bundle directory for the target `manifest_fingerprint` exists at the catalogue-resolved location.
  2. A `_passed.flag` file exists in that directory and is structurally valid (exact expected format).
  3. The digest recorded in `_passed.flag` matches the contents of the bundle according to that segment’s hashing law.
  4. No extra or missing files (relative to that segment’s `index.json` / equivalent) are observed in the bundle, unless explicitly allowed by that segment’s spec.

If any of these checks fail for **any** required upstream segment, 5A.S0 MUST:

* Record the failure in its own run-report / logs with a canonical error code (see §9), and
* NOT emit a “successful” `s0_gate_receipt_5A` for that `manifest_fingerprint`.

Later 5A states (S1+) MUST treat the absence of a valid `s0_gate_receipt_5A` as a hard precondition failure and MUST NOT read Layer-1 artefacts, even if they are physically present.

---

### 2.5 Scenario and parameter-pack readiness

For the `(parameter_hash, manifest_fingerprint)` pair that 5A.S0 is invoked with, the following additional conditions MUST hold:

1. **Scenario config resolution**

   * The engine’s scenario configuration (e.g. scenario calendar, campaign schedule, special days) for this `parameter_hash` MUST be discoverable via the Layer-2 dictionaries/registries and resolve to:

     * a unique **scenario ID** (or a small, explicit set of scenario IDs) that 5A will support; and
     * one or more schema-governed configuration artefacts (e.g. `scenario_calendar_5A`, `campaign_overlays`) for that parameter pack.

2. **5A policy readiness**

   * All 5A-specific policies required by later states (e.g. merchant classing policy, baseline shape library, calendar overlay policy) MUST be present in the catalogue for this `parameter_hash` and reference valid schema anchors.

3. **No mixed-parameter context**

   * Within a single 5A.S0 run, all resolved 5A policies and scenario configs MUST share the same `parameter_hash` as the run context. It is a precondition that the engine does not attempt to execute 5A.S0 in a context where multiple conflicting parameter packs are visible.

If any required scenario or 5A policy artefact cannot be resolved for the given `parameter_hash`, S0 MUST fail with a parameter/configuration error and MUST NOT emit `s0_gate_receipt_5A`.

---

### 2.6 Idempotency and single-writer assumptions

Finally, the following environmental assumptions are binding for S0:

* For a given `(parameter_hash, manifest_fingerprint)`, there MUST be at most **one active writer** of `s0_gate_receipt_5A` and `sealed_inputs_5A`. Concurrent writers against the same fingerprint are undefined behaviour and MUST be prevented by the surrounding orchestration layer.

* If `s0_gate_receipt_5A` and `sealed_inputs_5A` already exist for a `(parameter_hash, manifest_fingerprint)` and their contents are byte-for-byte identical to what S0 would produce, re-running S0 MAY no-op; otherwise, any attempt to overwrite MUST be treated as a configuration error.

These assumptions ensure that S0 can safely act as the single authority defining the sealed input universe for Segment 5A.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines what **5A.S0 — Gate & Sealed Inputs** is allowed to read, how those inputs are resolved, and which components are authoritative. All rules here are **binding**.

---

### 3.1 Overview

5A.S0 operates entirely on **metadata** and **contracts**. Its inputs fall into five logical categories:

1. **Engine run context** — the identity of the run.
2. **Layer-wide contracts** — schemas, dictionaries, artefact registries.
3. **Upstream segment validation artefacts** — bundles + `_passed.flag` for 1A–3B.
4. **Upstream world surfaces (facts & reference data)** — datasets that later 5A states *may* read at row level, but S0 does not.
5. **Layer-2 / 5A policies & scenario configs** — inputs that drive 5A’s behaviour.

All of these MUST be discovered and resolved via **catalogue abstractions** (dataset dictionaries + artefact registries) and **engine control-plane** metadata. 5A.S0 MUST NOT reach around the catalogue to fetch inputs ad hoc.

---

### 3.2 Engine run context

5A.S0 MUST treat the engine’s run context as its **primary input**:

* `parameter_hash`
  – Unique identifier for the parameter pack (including 5A policies, scenario configs, shape library) in effect for this run.

* `manifest_fingerprint`
  – Unique identifier for the manifest of artefacts that define the closed world for this run.

* `run_id`
  – Unique identifier for this execution of 5A.S0 under the pair `(parameter_hash, manifest_fingerprint)`.

These values:

* are supplied by the engine’s orchestration layer;
* are considered **authoritative**; and
* MUST be treated as immutable for the duration of 5A.S0.

5A.S0 MUST NOT attempt to recompute `parameter_hash` or `manifest_fingerprint` from raw content; that logic belongs to the engine’s global manifest/parameter hashing mechanism.

---

### 3.3 Layer-wide contracts (schemas, dictionaries, registries)

5A.S0 depends on **layer-wide** and **segment-specific** contracts as *authority* for dataset shapes, paths, and roles:

* **Layer-1 schemas** (e.g. `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`).

* **Layer-1 dataset dictionaries** for segments 1A–3B.

* **Layer-1 artefact registries** for segments 1A–3B.

* **Layer-2 schemas** (e.g. `schemas.layer2.yaml`) and **5A schemas** (e.g. `schemas.5A.yaml`).

* **Layer-2 / 5A dataset dictionary** (e.g. `dataset_dictionary.layer2.5A.yaml`).

* **5A artefact registry** (e.g. `artefact_registry_5A.yaml`).

Authority boundaries:

* These contracts are the **sole authority** for:

  * dataset shapes (columns, types, keys, partitioning),
  * path templates and partition tokens (e.g. `manifest_fingerprint={manifest_fingerprint}`),
  * logical roles (e.g. “validation bundle”, “scenario calendar”, “merchant reference”).

* 5A.S0:

  * MUST use them to resolve all logical dataset IDs and artefact names to physical locations and schema_refs;
  * MUST NOT infer schemas, partitioning, or paths in code (e.g. by string concatenation);
  * MUST treat any contract-level inconsistency (missing anchor, mismatched schema_ref) as a configuration error, not as a runtime “best effort”.

5A.S0 itself does not mutate these contracts; it treats them as read-only inputs.

---

### 3.4 Upstream validation artefacts (1A–3B)

The primary *data* inputs to 5A.S0 are the **validation artefacts** of upstream segments:

* For each of: **1A, 1B, 2A, 2B, 3A, 3B**:

  * `validation_bundle_*` (directory containing `index.json` and evidence files).
  * `_passed.flag` (fingerprint-scoped flag carrying the bundle hash).

5A.S0 MUST:

* Discover these artefacts via the dataset dictionaries + artefact registries, filtered to `manifest_fingerprint={manifest_fingerprint}`.
* Read:

  * the `_passed.flag` file contents;
  * the relevant bundle index (`index.json` or equivalent);
  * any additional small metadata files required by the upstream segment’s hashing law.
* Use them solely to verify:

  * presence,
  * structural validity, and
  * digest equality (flag vs bundle).

Authority boundaries:

* Each upstream segment’s own spec is the **authority** for:

  * the format of its validation bundle and `_passed.flag`;
  * the hashing law used to compute the recorded digest.

* 5A.S0:

  * MUST NOT reinterpret what “PASS” means for that segment; it only checks whether the bundle/flag pair is **self-consistent**;
  * MUST NOT modify or “repair” upstream bundles or flags;
  * MUST NOT read or interpret *data* egress from these segments at this stage (that is left to later 5A states).

---

### 3.5 Upstream world surfaces (facts & reference data)

Certain upstream datasets may be **read row-wise by later 5A states** (e.g. to derive merchant classes, zone-level intensities). 5A.S0’s job is to **seal** which of these are admissible inputs; it does not inspect their rows.

Typical examples include:

* 1A egress / reference:

  * `outlet_catalogue` (merchant × country outlet counts).
  * Merchant reference tables (MCC, channel, etc.).

* 1B egress:

  * `site_locations` (geolocated outlets per merchant × country).

* 2A egress:

  * `site_timezones` (per-site tzid).
  * `tz_timetable_cache` (timezone transition cache).

* 2B plan / egress:

  * `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`.
  * `s3_day_effects`, `s4_group_weights`.
  * 2B routing RNG/policy artefacts (read-only, metadata only).

* 3A egress:

  * `zone_alloc` and `zone_alloc_universe_hash`.

* 3B egress:

  * `virtual_classification_3B`, `virtual_settlement_3B`.
  * `virtual_routing_policy_3B`, `virtual_validation_contract_3B` (context only; not read by 5A states).
  * `edge_catalogue_3B`, `edge_alias_index_3B`, `edge_alias_blob_3B`, `edge_universe_hash_3B`.

Rules for 5A.S0:

* MAY:

  * resolve these datasets via dictionary/registry for the target `manifest_fingerprint` (and, where relevant, `parameter_hash`);
  * verify that their **schema_ref**, **partitioning**, and **path template** match what the contracts declare;
  * record them as rows in `sealed_inputs_5A` (with IDs, schema_refs, digests, roles).

* MUST NOT:

  * read their data bodies (rows) for the purposes of S0;
  * derive any business logic (e.g. merchant classes, statistics, intensities) directly from them;
  * modify, truncate, or re-partition these datasets.

For later 5A states, `sealed_inputs_5A` becomes the **authority** for which of these world surfaces are in-bounds; any upstream dataset not present in `sealed_inputs_5A` MUST be treated as out-of-scope for Segment 5A.

---

### 3.6 Layer-2 / 5A policies & scenario configs

5A.S0 also consumes Layer-2 / 5A–specific configuration artefacts that drive later states:

Examples:

* **Scenario configs** (parameter-scoped, often shared across segments):

  * `scenario_calendar_5A` (holidays, paydays, campaign windows, outages).
  * `scenario_metadata` (scenario IDs, labels, types, horizon).

* **5A policies**:

  * `merchant_class_policy_5A` (rules for grouping merchants into demand classes).
  * `shape_library_5A` (catalogue of normalised weekly shapes per class/zone/channel).
  * `scenario_overlay_policy_5A` (global rules for turning scenario events into multiplicative/additive factors).
  * Any additional Layer-2–wide knobs that 5A will use (e.g. default scale factors, clipping thresholds).

Rules:

* These artefacts MUST:

  * be resolvable via `dataset_dictionary.layer2.5A.yaml` and `artefact_registry_5A.yaml`;
  * be scoped to the correct `parameter_hash`;
  * reference valid schema anchors in `schemas.layer2.yaml` / `schemas.5A.yaml`.

* 5A.S0:

  * MUST resolve and record them in `sealed_inputs_5A` with their logical IDs, schema_refs, digests, and roles;
  * MAY perform minimal structural validation (schema conformance) as part of S0’s acceptance criteria;
  * MUST NOT interpret or apply their business semantics (classification, shape selection, calendar math) — that belongs to later 5A states.

These policies and configs are **authoritative** for 5A’s behaviour. If they are missing or invalid, 5A.S0 MUST fail and MUST NOT emit a successful gate receipt.

---

### 3.7 Authority boundaries and out-of-bounds inputs

The following boundaries are binding:

1. **Catalogue as the only discovery mechanism**

   * All inputs (upstream artefacts, configs, policies) MUST be discovered via:

     * dataset dictionaries,
     * artefact registries, and
     * engine control-plane metadata (for run context).
   * 5A.S0 MUST NOT use:

     * raw filesystem traversal,
     * hard-coded path literals, or
     * ad-hoc network calls
       to discover inputs.

2. **Read-only view of upstream segments**

   * 5A.S0 is a **pure consumer** of upstream artefacts:

     * it MUST NOT modify, rewrite, or delete any upstream dataset or validation artefact;
     * it MUST NOT reinterpret upstream semantics (e.g. redefine what a “PASS” means for 1B).

3. **`sealed_inputs_5A` as the authority for 5A**

   * For the target `manifest_fingerprint`, the contents of `sealed_inputs_5A` define the **entire** input universe for Segment 5A.
   * Any dataset or artefact not listed in `sealed_inputs_5A` MUST be treated by later 5A states as if it does not exist for this run, even if it is physically present in storage.

4. **No out-of-band overrides**

   * 5A.S0 MUST NOT widen or narrow its input universe based on:

     * environment variables,
     * CLI flags, or
     * ad-hoc feature switches
       that are not themselves encoded in the parameter pack and reflected in `parameter_hash` and/or `manifest_fingerprint`.

Within these boundaries, 5A.S0 has a precise, catalogue-driven view of what it may use, and downstream 5A states have a single, unambiguous authority (`sealed_inputs_5A`) for all inputs they are allowed to read.

---

## 4. Outputs (control datasets) & identity *(Binding)*

This section defines the **control-plane outputs** of 5A.S0 and the identity rules that govern them. These requirements are **binding**.

5A.S0 produces **no fact tables and no intensity surfaces**. Its outputs are small, fingerprint-scoped control datasets that:

* define the **closed world** for Segment 5A, and
* are the **only** authority later 5A states may use to decide what inputs are in-bounds.

---

### 4.1 Overview of outputs

5A.S0 MUST produce the following logical datasets:

1. **`s0_gate_receipt_5A`**

   * A single-row, fingerprint-scoped “receipt” describing:

     * the run identity (`parameter_hash`, `manifest_fingerprint`, `run_id`),
     * upstream validation status for 1A–3B,
     * the scenario/parameter pack IDs bound to this run,
     * a summary of the sealed input universe.

2. **`sealed_inputs_5A`**

   * A fingerprint-scoped inventory table containing **one row per artefact** that 5A is permitted to read, including:

     * upstream Layer-1 datasets (facts and references),
     * Layer-1 and Layer-2 contracts (schemas, dictionaries, registries),
     * 5A and scenario-specific policy/config artefacts.

Optionally, 5A.S0 MAY also produce:

3. **`scenario_manifest_5A`** *(optional, but if present, MUST be spec’d)*

   * A fingerprint-scoped, compact descriptor of the scenario(s) active for this run (e.g. IDs, horizon, key tags) derived from the sealed scenario configs.

If `scenario_manifest_5A` is not materialised as a separate dataset, its contents MUST still be representable within `s0_gate_receipt_5A`.

---

### 4.2 `s0_gate_receipt_5A`

**Role**

` s0_gate_receipt_5A` is a compact, fingerprint-scoped receipt that:

* binds the run identity to the set of upstream segments that were verified,
* records which scenario and parameter pack are in force, and
* identifies the corresponding `sealed_inputs_5A` inventory.

**Content (at a high level)**

At minimum, each row in `s0_gate_receipt_5A` MUST contain:

* Run identity:

  * `parameter_hash` (string)
  * `manifest_fingerprint` (string)
  * `run_id` (string or 128-bit identifier)
  * `created_utc` / `verified_utc` (timestamp, UTC)

* Upstream validation summary (per segment 1A–3B):

  * `segment_id` → status map, e.g.:

    * `upstream_1A_status ∈ {"PASS","FAIL","MISSING"}`
    * … similarly for `1B`, `2A`, `2B`, `3A`, `3B`
  * For `PASS` segments, IDs or digests of:

    * their validation bundle indices
    * their `_passed.flag` digests

* Scenario / parameter pack binding:

  * `scenario_id` (or array if multiple scenarios are supported)
  * `scenario_version` / `scenario_pack_id` (if applicable)
  * `parameter_pack_id` / `parameter_profile` (optional descriptive label)

* Sealed-universe summary:

  * `sealed_inputs_version` or `sealed_inputs_digest` (a digest over the `sealed_inputs_5A` rows)
  * counts by role, e.g. `n_upstream_datasets`, `n_policy_artifacts`, `n_reference_surfaces`

**Identity & cardinality**

* Partitioning:

  * `s0_gate_receipt_5A` MUST be **partitioned only by**
    `manifest_fingerprint={manifest_fingerprint}`.
* Primary key:

  * For each `manifest_fingerprint`, there MUST be **exactly one logical row**.
    A composite key such as `(manifest_fingerprint)` or `(manifest_fingerprint, parameter_hash)` MAY be used; in either case, the pair `(manifest_fingerprint, parameter_hash)` MUST be unique.

5A.S1+ MUST treat the presence of exactly one valid `s0_gate_receipt_5A` row for a fingerprint as the **precondition** for proceeding.

---

### 4.3 `sealed_inputs_5A`

**Role**

`sealed_inputs_5A` is the authoritative **inventory** of all artefacts that Segment 5A is allowed to read for a given fingerprint. It defines the **exact closed world** in which all later 5A states operate.

**Content (at a high level)**

Each row in `sealed_inputs_5A` MUST represent one logical artefact and MUST include at least:

* Run / fingerprint binding:

  * `manifest_fingerprint`
  * `parameter_hash`

* Artefact identity:

  * `owner_layer` (e.g. `"layer1"`, `"layer2"`)
  * `owner_segment` (e.g. `"1A"`, `"2B"`, `"3A"`, `"3B"`, `"5A"`)
  * `artifact_id` (logical ID from the relevant artefact registry)
  * `manifest_key` (as declared in the registry, if applicable)
  * `role` (e.g. `"upstream_egress"`, `"reference_data"`, `"scenario_config"`, `"policy"`, `"contract"`)

* Schema and location:

  * `schema_ref` (JSON-Schema anchor, e.g. `schemas.layer1.yaml#/egress/site_locations`)
  * `path_template` (catalogue path template, with tokens like `manifest_fingerprint={manifest_fingerprint}`)
  * `partition_keys` (list of partition columns for data files, if applicable)

* Integrity:

  * `sha256_hex` or equivalent digest for this artefact at this fingerprint
  * `version` / `semver` (if managed separately from `parameter_hash`)
  * `source_dictionary` / `source_registry` (which dictionary/registry defined it)

* Status and scope:

  * `status ∈ {"REQUIRED","OPTIONAL","IGNORED"}` (for 5A)
  * `read_scope ∈ {"ROW_LEVEL","METADATA_ONLY"}`

    * e.g. `ROW_LEVEL` for `outlet_catalogue`, `site_locations`, `site_timezones`
    * `METADATA_ONLY` for schemas, validation bundles, alias blobs where 5A does not read rows.
  * `notes` (optional short free-text for diagnostics/ops)

**Identity & ordering**

* Partitioning:

  * `sealed_inputs_5A` MUST be **partitioned only by**
    `manifest_fingerprint={manifest_fingerprint}`.
* Primary key:

  * The tuple
    `(manifest_fingerprint, owner_segment, artifact_id)`
    MUST be unique.
* Ordering:

  * Writers SHOULD produce rows in a deterministic order (e.g. lexicographically by `(owner_segment, artifact_id, role)`), but consumers MUST NOT rely on physical ordering; the PK/unique constraint is the only binding ordering rule.

Later 5A states MUST treat the set of rows in `sealed_inputs_5A` for a fingerprint as the **complete and exclusive set** of artefacts they may read.

---

### 4.4 Optional: `scenario_manifest_5A`

If implemented, `scenario_manifest_5A` is a convenience projection of the scenario-specific fields in `sealed_inputs_5A` and `s0_gate_receipt_5A`.

**Role**

* Provide a small, fingerprint-scoped record of:

  * `scenario_id`, `scenario_version`, `horizon_start_utc`, `horizon_end_utc`
  * high-level flags (e.g. `is_baseline`, `is_stress`, `has_black_friday_window`)
  * links to the underlying scenario config artefacts listed in `sealed_inputs_5A`.

**Identity**

* Partitioned only by `manifest_fingerprint={manifest_fingerprint}`.
* Exactly one logical row per `manifest_fingerprint`.
* If present, its values MUST be derivable entirely from:

  * `s0_gate_receipt_5A`, and
  * scenario-related entries in `sealed_inputs_5A`.

This dataset is optional; its absence MUST NOT affect correctness if `s0_gate_receipt_5A` and `sealed_inputs_5A` are present and valid.

---

### 4.5 Identity relationships between outputs & upstream artefacts

The following identity relationships are binding:

1. **Fingerprint embedding**

   * Every row in `s0_gate_receipt_5A`, `sealed_inputs_5A`, and (if present) `scenario_manifest_5A` MUST embed a `manifest_fingerprint` value that:

     * exactly matches the partition token `manifest_fingerprint={manifest_fingerprint}`; and
     * matches the fingerprint used to locate upstream validation bundles for 1A–3B.

2. **Parameter-hash consistency**

   * For a given fingerprint, all rows in `sealed_inputs_5A` MUST agree on `parameter_hash` and it MUST equal the `parameter_hash` recorded in `s0_gate_receipt_5A`.
   * If multiple parameter packs are theoretically visible to the engine, 5A.S0 MUST select exactly one `parameter_hash` per fingerprint and record that choice here.

3. **Digest linkage**

   * If `s0_gate_receipt_5A` exposes a field such as `sealed_inputs_digest`, it MUST be a deterministic hash of the `sealed_inputs_5A` contents for that fingerprint (using the hashing law defined later in the spec).
   * Any consumer that wishes to ensure catalogue stability MAY recompute this digest from `sealed_inputs_5A` and compare it to the value in `s0_gate_receipt_5A`.

4. **Upstream PASS linkage**

   * For each upstream segment (1A–3B), `s0_gate_receipt_5A` MUST record the **status** and key IDs/digests of its validation artefacts.
   * Rows in `sealed_inputs_5A` that refer to upstream fact/egress datasets MUST only be present if:

     * the corresponding upstream segment’s status in `s0_gate_receipt_5A` is `"PASS"`; and
     * the artefact’s digest matches what the upstream segment’s registry/dictionary declares for this fingerprint.

Putting these together, a downstream consumer can:

* Start from `s0_gate_receipt_5A` to ensure upstream is green and identify the correct `parameter_hash`, `scenario_id`, and `sealed_inputs_digest`.
* Then read `sealed_inputs_5A` to know **exactly which inputs** are allowed and what shapes/digests they have.

---

### 4.6 Relationship to later 5A validation

The outputs of 5A.S0 participate in, but do not themselves constitute, the **segment-level PASS** for 5A:

* Later 5A validation states MUST:

  * include `s0_gate_receipt_5A` and `sealed_inputs_5A` in their own validation bundles for 5A;
  * verify that:

    * `s0_gate_receipt_5A` is present and schema-valid,
    * `sealed_inputs_5A` is present and schema-valid,
    * the implied digests/links to upstream artefacts remain consistent.

* 5A.S1+ MUST treat:

  * the existence of a valid `s0_gate_receipt_5A` row for a fingerprint, and
  * a non-empty, schema-valid `sealed_inputs_5A` for the same fingerprint

  as **necessary preconditions** for any further computation in Segment 5A.

Within this pattern, `s0_gate_receipt_5A` and `sealed_inputs_5A` serve as the **identity and authority spine** for the entire segment.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

Contract authority for 5A.S0 lives in the 5A schema pack (`schemas.5A.yaml`), dataset dictionary (`dataset_dictionary.layer2.5A.yaml`) and artefact registry (`artefact_registry_5A.yaml`). S0 emits three control-plane datasets:

1. `s0_gate_receipt_5A`
2. `sealed_inputs_5A`
3. `scenario_manifest_5A` (optional convenience view)

### 5.1 `s0_gate_receipt_5A`

* **Schema anchor:** `schemas.5A.yaml#/validation/s0_gate_receipt_5A`
* **Dictionary id:** `s0_gate_receipt_5A`
* **Registry key:** `mlr.5A.control.s0_gate_receipt`

Binding notes:

- Written once per `manifest_fingerprint` at `data/layer2/5A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt_5A.json`.
- Carries the run identity (`parameter_hash`, `manifest_fingerprint`, `run_id`, `scenario_set`) plus the upstream PASS map and `sealed_inputs_digest`; the schema pack is the shape authority.
- Any rerun with the same `(parameter_hash, manifest_fingerprint, run_id)` must reproduce byte-identical JSON; otherwise treat as a write conflict.

### 5.2 `sealed_inputs_5A`

* **Schema anchor:** `schemas.5A.yaml#/validation/sealed_inputs_5A`
* **Dictionary id:** `sealed_inputs_5A`
* **Registry key:** `mlr.5A.control.sealed_inputs`

Binding notes:

- Stored under `data/layer2/5A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_5A.json`; partition key is `manifest_fingerprint` only.
- Rows enumerate the whitelist of artefacts 5A may read (owner segment, manifest key, schema_ref, digest, `status`, `read_scope`). Column definitions and enums live solely in the schema pack.
- Downstream states MUST treat this table as authoritative – no reading artefacts outside the listed rows. Updates require regenerating the manifest and rerunning S0.

### 5.3 `scenario_manifest_5A` (optional)

* **Schema anchor:** `schemas.5A.yaml#/validation/scenario_manifest_5A`
* **Dictionary id:** `scenario_manifest_5A`
* **Registry key:** `mlr.5A.control.scenario_manifest`

Binding notes:

- Optional projection of scenario metadata derived from sealed inputs.
- When produced it must reside at `data/layer2/5A/scenario_manifest/manifest_fingerprint={manifest_fingerprint}/scenario_manifest_5A.parquet` and adhere exactly to the schema pack.
- Absence of this dataset MUST NOT block downstream consumers so long as the gate receipt + sealed inputs are present.


## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section specifies the **step-by-step algorithm** for **5A.S0 — Gate & Sealed Inputs**. It is **purely deterministic** and **MUST NOT** consume or emit any RNG events.

The algorithm is expressed as ordered steps. An implementation MUST follow this sequence and MUST respect all invariants described here.

---

### 6.1 High-level invariants

5A.S0 MUST satisfy the following invariants:

* **RNG-free:**

  * MUST NOT call any RNG primitive.
  * MUST NOT write to `rng_audit_log`, `rng_trace_log` or any RNG event stream.

* **Catalogue-only discovery:**

  * All artefacts MUST be discovered via dataset dictionaries + artefact registries + engine run context.
  * No hard-coded filesystem paths, no network calls, no ad-hoc directory scanning.

* **Upstream read-only:**

  * MUST NOT mutate, delete, or rewrite any upstream dataset or validation artefact.
  * MUST only read upstream validation bundles and `_passed.flag` to the extent required to verify consistency.

* **All-or-nothing outputs:**

  * If any step fails, 5A.S0 MUST NOT publish a partial `s0_gate_receipt_5A` or `sealed_inputs_5A` for the target `manifest_fingerprint`.
  * Successful runs MUST leave both datasets present, schema-valid and mutually consistent.

---

### 6.2 Step 1 — Resolve run identity

**Inputs:**

* Engine-supplied run context:

  * `parameter_hash`
  * `manifest_fingerprint`
  * `run_id`
  * environment metadata (e.g. environment name, CI build ID) — optional.

**Procedure:**

1. Read `parameter_hash`, `manifest_fingerprint`, and `run_id` from the engine control-plane.
2. Validate that:

   * `parameter_hash` and `manifest_fingerprint` are non-empty strings matching the engine’s expected format (e.g. hex or base64; exact format is defined globally, not by 5A).
   * `run_id` is non-empty and unique within the engine’s run-report context.
3. Fetch a monotonic wall-clock timestamp `created_utc` in UTC (e.g. RFC3339 micros).

   * This is the **only** use of wall-clock; it is not used for any branching or hashing logic.

**Invariants:**

* `parameter_hash`, `manifest_fingerprint`, and `run_id` are treated as opaque identifiers.
* 5A.S0 MUST NOT attempt to recompute or override them.

If any of these are missing or invalid, S0 MUST fail with an appropriate configuration error and MUST NOT proceed.

---

### 6.3 Step 2 — Verify upstream segment statuses (1A–3B)

**Goal:** For each upstream segment in `{1A, 1B, 2A, 2B, 3A, 3B}`, verify the presence and internal consistency of its validation artefacts for the target `manifest_fingerprint`.

**Inputs:**

* Layer-1 dictionaries & registries for 1A–3B.
* `manifest_fingerprint` from Step 1.

**Procedure (per segment `seg ∈ {1A,1B,2A,2B,3A,3B}`):**

1. Using the segment’s dataset dictionary + artefact registry, resolve:

   * the dataset representing `validation_bundle_seg` (bundle directory), and
   * the dataset representing `_passed.flag` (flag file),
     for `manifest_fingerprint={manifest_fingerprint}`.

2. If either cannot be resolved in the catalogue:

   * Record `status="MISSING"` for this segment in an internal accumulator.
   * Do **not** attempt filesystem probing.
   * Continue to the next segment (S0 may still run to completion, but later steps will treat missing status as failure for the gate receipt).

3. If both resolve:

   * Read the `index.json` / bundle index as defined by the segment’s own spec.
   * Read the `_passed.flag` file.
   * Apply the **segment’s own hashing law**:

     * Recompute the digest over the bundle contents as that spec defines.
     * Compare it to the digest recorded in `_passed.flag`.

4. If the digests match and the index is structurally valid:

   * Record `status="PASS"` and store any useful metadata:

     * `bundle_sha256_hex`, `flag_sha256_hex` (or equivalent),
     * logical bundle ID from the registry.

5. If the digests do not match or the bundle is structurally invalid:

   * Record `status="FAIL"` for this segment.

**Invariants:**

* 5A.S0 MUST NOT reinterpret or change any upstream hashing rule.
* 5A.S0 MUST NOT modify upstream bundles or flags, even if they appear malformed.

At the end of this step, S0 holds a map:

```text
upstream_status[segment_id] -> { status, bundle_id, bundle_sha256_hex?, flag_sha256_hex? }
```

This map will be embedded into `s0_gate_receipt_5A` in Step 6.

---

### 6.4 Step 3 — Discover candidate artefacts for 5A

**Goal:** Catalogue all datasets/artefacts that 5A is *eligible* to use as inputs, before filtering them into the sealed universe.

**Inputs:**

* Layer-1 dictionaries & registries (1A–3B).
* Layer-2 / 5A dictionary & registry.
* `parameter_hash`, `manifest_fingerprint`.

**Procedure:**

1. Initialise an empty in-memory list `CANDIDATES`.

2. From the **5A dataset dictionary & artefact registry**, enumerate all artefacts that are:

   * declared as potential inputs to 5A (e.g. roles `"upstream_egress"`, `"reference_data"`, `"scenario_config"`, `"policy"`, `"contract"`), and
   * not produced by Segment 5A itself, OR produced by 5A but required as control-plane inputs (e.g. Layer-2–wide contracts).

3. For each such artefact:

   * Resolve its `schema_ref`, `path_template`, `partition_keys`, and logical ID (`artifact_id`, `manifest_key`).
   * Determine if it is parameter-scoped or fingerprint-scoped:

     * If the path template contains `parameter_hash={parameter_hash}`, treat it as parameter-scoped.
     * If it contains `manifest_fingerprint={manifest_fingerprint}`, treat it as fingerprint-scoped.
   * For parameter-scoped artefacts:

     * Ensure the resolved entry’s `parameter_hash` matches the run’s `parameter_hash`.
   * Append an entry to `CANDIDATES` with:

     * `owner_layer`, `owner_segment`, `artifact_id`, `schema_ref`, `path_template`, `partition_keys`, `expected_scope`.

4. From the **Layer-1 dictionaries & registries**, similarly enumerate all artefacts that:

   * are relevant to 5A (via explicit `consumed_by: ["5A"]` or equivalent); and
   * belong to segments 1A–3B.

   For each, resolve schema/path/partition metadata and append to `CANDIDATES` with the same structure.

**Invariants:**

* Discovery MUST be driven by explicit `consumed_by` / `role` / registry flags, not by “search everything under /layer1”.
* No data is read at this stage; only dictionary/registry metadata is loaded.

The result is a superset of all artefacts that might end up in `sealed_inputs_5A`.

---

### 6.5 Step 4 — Construct `sealed_inputs_5A` rows

**Goal:** Turn the `CANDIDATES` list into a concrete, fingerprint-scoped inventory with digests and roles.

**Inputs:**

* `CANDIDATES` from Step 3.
* `upstream_status` from Step 2.
* `parameter_hash`, `manifest_fingerprint`.

**Procedure:**

For each `candidate` in `CANDIDATES`:

1. **Filter by upstream PASS / availability**

   * If `candidate.owner_segment ∈ {1A,1B,2A,2B,3A,3B}` and `upstream_status[owner_segment].status != "PASS"`:

     * Skip this candidate entirely (it is out-of-bounds for this run).
     * Optionally mark it as “ignored” in internal diagnostics.

   * If the candidate is a 5A or Layer-2 artefact (e.g. scenario config, 5A policy) and cannot be resolved for `(parameter_hash, manifest_fingerprint)` in the catalogue:

     * Treat this as a configuration error (5A policy/scenario missing) and fail S0 (see §9).
     * Do not continue to build `sealed_inputs_5A`.

2. **Resolve physical location & digest**

   Using dictionary + registry metadata:

   * Instantiate the concrete path(s) from `path_template`, substituting `parameter_hash` and/or `manifest_fingerprint` as required.
   * If the artefact is a dataset with partitions:

     * Resolve the directory for the relevant partition(s) (commonly just `manifest_fingerprint={manifest_fingerprint}` and, for parameter-scoped, also `parameter_hash={parameter_hash}`).
   * Compute or read the integrity digest:

     * If the registry already provides a `sha256_hex` for this artefact and fingerprint, use that.
     * Otherwise, compute `sha256_hex` over the artefact content according to its spec (e.g. over file bytes, or over an index file if that’s the declared convention).

3. **Assign role and read_scope**

   * Determine `role` for this candidate based on its registry entry:
     e.g. `"upstream_egress"`, `"reference_data"`, `"scenario_config"`, `"policy"`, `"contract"`, `"validation_bundle"`, `"validation_flag"`.
   * Determine `read_scope`:

     * `ROW_LEVEL` if 5A.S1+ is expected to read rows (e.g. `outlet_catalogue`, `site_locations`, `site_timezones`, intensity-related references).
     * `METADATA_ONLY` if 5A will only ever require metadata/statics (e.g. schemas, validation bundles, alias blobs used only by 5B).

4. **Construct row**

   * Build a row conforming to `schemas.5A.yaml#/validation/sealed_inputs_5A`, setting fields:

     * `manifest_fingerprint`, `parameter_hash`,
     * `owner_layer`, `owner_segment`, `artifact_id`, `manifest_key`,
     * `role`, `schema_ref`, `path_template`, `partition_keys`,
     * `sha256_hex`, `version`, `source_dictionary`, `source_registry`,
     * `status` (usually `"REQUIRED"` for 5A inputs driven by configuration, `"OPTIONAL"` where dictionary/registry declares optional consumption),
     * `read_scope`.

5. Append the row to an in-memory list `SEALED_ROWS`.

After all candidates are processed:

* Sort `SEALED_ROWS` deterministically, e.g. by `(owner_layer, owner_segment, role, artifact_id)`.

**Invariants:**

* For each upstream segment with `status="PASS"`, all artefacts 5A depends on from that segment MUST appear in `SEALED_ROWS`.
* For any artefact included in `SEALED_ROWS`, the digest and schema_ref MUST be consistent with the catalogue; mismatches MUST be treated as configuration errors.

---

### 6.6 Step 5 — Compute `sealed_inputs_digest`

**Goal:** Derive a stable digest summarising the sealed input universe for this fingerprint.

**Inputs:**

* Sorted `SEALED_ROWS` from Step 4.

**Procedure:**

1. Serialise `SEALED_ROWS` into a canonical byte representation `B`, using a fixed, documented convention, for example:

   * For each row, construct a JSON object with a fixed field order containing at least:

     * `manifest_fingerprint`, `parameter_hash`,
     * `owner_layer`, `owner_segment`, `artifact_id`,
     * `schema_ref`, `path_template`, `sha256_hex`, `role`, `status`, `read_scope`.
   * Encode each row as UTF-8 JSON with no insignificant whitespace.
   * Concatenate the row bytes in the sorted order determined above.

2. Compute `sealed_inputs_digest = SHA256(B)` and encode it as a 64-character lowercase hex string.

**Invariants:**

* For a given `(parameter_hash, manifest_fingerprint)` and fixed catalogue state, `sealed_inputs_digest` MUST be deterministic and stable across re-runs.
* Any change in:

  * the set of sealed artefacts, or
  * their schema_refs, paths, or digests
    MUST change `sealed_inputs_digest`.

This digest will be embedded into `s0_gate_receipt_5A` and can be used by downstream validations to detect catalogue drift.

---

### 6.7 Step 6 — Construct `s0_gate_receipt_5A`

**Goal:** Assemble a single receipt row summarising run identity, upstream status, scenario binding, and the sealed-input digest.

**Inputs:**

* `parameter_hash`, `manifest_fingerprint`, `run_id`, `created_utc` from Step 1.
* `upstream_status` map from Step 2.
* `sealed_inputs_digest` from Step 5.
* Resolved scenario config(s) from Step 4 (scenario-related artefacts in `SEALED_ROWS`).

**Procedure:**

1. Derive `scenario_id` and (optionally) `scenario_pack_id` from scenario-related entries in `SEALED_ROWS`, according to the Layer-2 scenario config spec.

2. Construct a JSON object `RECEIPT` conforming to `schemas.5A.yaml#/validation/s0_gate_receipt_5A`:

   * Identity fields:

     * `manifest_fingerprint`
     * `parameter_hash`
     * `run_id`
     * `created_utc`

   * Upstream summary:

     * `verified_upstream_segments` as an object mapping each of `{"1A","1B","2A","2B","3A","3B"}` to:

       * `status` (`"PASS"`, `"FAIL"`, `"MISSING"`),
       * `bundle_id` / `bundle_sha256_hex` / `flag_sha256_hex` where available.

   * Scenario binding:

     * `scenario_id` (single ID or array)
     * `scenario_pack_id` / `scenario_version` (optional).

   * Sealed input summary:

     * `sealed_inputs_digest`
     * counts such as `n_upstream_datasets`, `n_reference_data`, `n_policies`, derived from `SEALED_ROWS`.

3. Validate `RECEIPT` against the schema anchor (local JSON-Schema validation).

**Invariants:**

* For each upstream segment with `status="PASS"` in `verified_upstream_segments`, at least one artefact from that segment MUST appear in `SEALED_ROWS`.
* If any upstream segment has `status ∈ {"FAIL","MISSING"}`, 5A.S0 MAY still emit `s0_gate_receipt_5A` depending on your overall engine semantics, but later 5A states MUST treat `"FAIL"` or `"MISSING"` as a hard precondition failure (this mapping is defined in §8).

---

### 6.8 Step 7 — Atomic write & idempotency

**Goal:** Persist `sealed_inputs_5A` and `s0_gate_receipt_5A` atomically and idempotently.

**Inputs:**

* `SEALED_ROWS` from Step 4.
* `RECEIPT` from Step 6.

**Procedure:**

1. **Check for existing outputs**

   * Using the 5A dataset dictionary, determine the canonical locations for:

     * `sealed_inputs_5A` under `manifest_fingerprint={manifest_fingerprint}`, and
     * `s0_gate_receipt_5A` under `manifest_fingerprint={manifest_fingerprint}`.

   * If both datasets already exist:

     * Read existing contents.

     * Canonically sort existing `sealed_inputs_5A` rows and serialise as in Step 5 to compute `existing_sealed_inputs_digest`.

     * Compare `existing_sealed_inputs_digest` with `sealed_inputs_digest`; compare existing receipt fields with `RECEIPT`.

     * If they match byte-for-byte (or field-for-field under the same serialisation), 5A.S0 MAY:

       * log that the state is already up-to-date, and
       * exit without writing (idempotent no-op).

     * If they differ, 5A.S0 MUST treat this as a configuration error (`S0_OUTPUT_CONFLICT` or similar) and MUST NOT overwrite existing data.

2. **Write to staging locations**

   * Write `SEALED_ROWS` to a temporary/staging path, e.g.:
     `data/layer2/5A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/.staging/sealed_inputs_5A.json`
   * Write `RECEIPT` to a temporary/staging path, e.g.:
     `data/layer2/5A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/.staging/s0_gate_receipt_5A.json`

3. **Durability checks (optional but recommended)**

   * Optionally re-read the staged files and validate:

     * that they conform to their schemas, and
     * that their on-disk digests (if recomputed) match the in-memory expectations.

4. **Atomic commit**

   * Perform atomic moves/renames from staging to canonical locations:

     * Staging `sealed_inputs_5A.json` → canonical `sealed_inputs_5A.json`.
     * Staging `s0_gate_receipt_5A.json` → canonical `s0_gate_receipt_5A.json`.

   * The commit MUST be ordered such that:

     * `sealed_inputs_5A` appears on disk **before or at the same instant as** `s0_gate_receipt_5A`.
     * This ensures that any consumer seeing a valid receipt can subsequently read the inventory.

**Invariants:**

* Partial writes (e.g. only one of the two datasets) MUST NOT be visible in a successful run.
* On failure during staging or commit, the state MUST either:

  * roll back temporary files where possible, or
  * leave them clearly marked as staging artefacts (e.g. under `.staging/`), which downstream consumers MUST ignore.

---

Within these steps, 5A.S0 behaves as a **pure, deterministic control-plane state**: it resolves the run identity, verifies upstream status, seals the input universe, and publishes a minimal, well-structured receipt and inventory for all downstream 5A states—without consuming any RNG or doing unnecessary data processing.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how **identity** is represented for 5A.S0 outputs, how they are **partitioned and addressed**, and what the **merge / rewrite discipline** is. All rules are **binding**.

5A.S0 produces only control-plane datasets; their identity model MUST be simple and consistent with Layer-1.

---

### 7.1 Identity model

There are two distinct identity layers to keep straight:

* **Run identity** (engine-level, ephemeral):

  * `parameter_hash` — which parameter pack / policy set is in force.
  * `manifest_fingerprint` — which closed world (manifest) we are in.
  * `run_id` — this particular execution of 5A.S0.

* **Dataset identity** (storage-level, persistent):

  * For `s0_gate_receipt_5A` and `sealed_inputs_5A`, **dataset identity is keyed only by `manifest_fingerprint`**; these datasets represent “the sealed world for this fingerprint”, not “this run”.

Binding rules:

1. For a given `manifest_fingerprint`, there MUST be at most **one logical `s0_gate_receipt_5A` row** and one `sealed_inputs_5A` inventory.
2. Multiple `run_id` values MAY correspond to the same `manifest_fingerprint`, but:

   * they MUST all produce **byte-identical outputs** if the catalogue has not changed, or
   * be treated as conflicts (see §7.4) if they attempt to produce divergent outputs.

`run_id` is **not** part of the dataset primary key; it is part of the receipt content only.

---

### 7.2 Partition law & path contracts

#### 7.2.1 Partitioning for 5A.S0 outputs

Both control datasets are **fingerprint-partitioned only**:

* `s0_gate_receipt_5A`:

  * `partition_keys: ["fingerprint"]`
  * Path template:
    `data/layer2/5A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt_5A.json`

* `sealed_inputs_5A`:

  * `partition_keys: ["fingerprint"]`
  * Path template:
    `data/layer2/5A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_5A.json`

If `scenario_manifest_5A` is implemented:

* `partition_keys: ["fingerprint"]`
* Path template:
  `data/layer2/5A/scenario_manifest/manifest_fingerprint={manifest_fingerprint}/scenario_manifest_5A.parquet`

#### 7.2.2 Path ↔ embed equality

For every row in every 5A.S0 output:

* The embedded column `manifest_fingerprint` MUST:

  * be present and non-null, and
  * exactly equal the value used in the partition token `manifest_fingerprint={manifest_fingerprint}`.

* The embedded `parameter_hash` (where present):

  * MUST equal the `parameter_hash` in the run context, and
  * MUST be consistent across all rows in `sealed_inputs_5A` for a given fingerprint.

An implementation MUST treat any mismatch between:

* path token vs embedded `manifest_fingerprint`, or
* embedded `parameter_hash` vs run-context `parameter_hash`

as a hard error in S0’s acceptance criteria.

---

### 7.3 Primary keys & ordering

#### 7.3.1 Primary keys

Dataset keys MUST be declared and enforced as follows:

* `s0_gate_receipt_5A`:

  * `primary_key: ["manifest_fingerprint"]`
  * Exactly one row per `manifest_fingerprint`.

* `sealed_inputs_5A`:

  * `primary_key: ["manifest_fingerprint", "owner_segment", "artifact_id"]`
  * At most one row per `(manifest_fingerprint, owner_segment, artifact_id)` pair.

* `scenario_manifest_5A` (if implemented):

  * `primary_key: ["manifest_fingerprint", "scenario_id"]`

These keys are **binding**: any attempt to write rows that would violate uniqueness MUST fail.

#### 7.3.2 Logical ordering

Physical row ordering is **not** semantically significant, but 5A.S0 MUST impose a deterministic ordering when producing `sealed_inputs_5A` to support stable hashing:

* Before writing `sealed_inputs_5A`, rows MUST be sorted in-memory by a fixed key, for example:
  `(owner_layer, owner_segment, role, artifact_id)`.

* The hashing law for `sealed_inputs_digest` (described in §6) assumes this deterministic ordering; reordering rows would change the digest.

Consumers MUST NOT rely on any particular physical ordering beyond what is baked into the digest computation.

---

### 7.4 Merge discipline & rewrite semantics

5A.S0 is designed as a **single-writer, no-merge** control state per fingerprint.

Binding rules:

1. **No in-place merge across runs**

   * For a fixed `manifest_fingerprint`, 5A.S0 MUST NOT:

     * append to an existing `sealed_inputs_5A` inventory,
     * partially overwrite rows, or
     * perform any row-level “merge” operation.
   * The inventory for a fingerprint is conceptually **atomic**: it either exists and is final, or does not exist.

2. **Idempotent re-runs are allowed**

   * If `s0_gate_receipt_5A` and `sealed_inputs_5A` already exist for a fingerprint, and 5A.S0 recomputes identical content (same rows, same serialisation, same `sealed_inputs_digest`), then:

     * S0 MAY treat this as a no-op and return successfully without changing storage.
     * This is the **only** allowed “rewrite”.

3. **Conflicting rewrites are forbidden**

   * If existing outputs for a fingerprint differ in any way from what S0 would produce (different rows, digests, upstream statuses, scenario IDs, etc.), S0 MUST:

     * fail with a canonical error (e.g. `S0_OUTPUT_CONFLICT`), and
     * MUST NOT attempt to overwrite or merge the existing outputs.

   * Any change to the sealed input universe or upstream state that should be visible to 5A MUST result in a **new `manifest_fingerprint`** and, therefore, a new fingerprint partition, not a mutation under the same fingerprint.

4. **No cross-fingerprint merging**

   * S0 MUST NOT aggregate or merge sealed inputs across different fingerprints.
   * Each fingerprint partition’s `sealed_inputs_5A` and `s0_gate_receipt_5A` are **self-contained**; cross-fingerprint relationships (e.g. “same parameter pack, different scenario”) are the engine’s concern, not S0’s.

---

### 7.5 Interaction with other partitions (seed, parameter_hash, run_id)

For 5A.S0 outputs:

* **Seed**

  * `seed` is **not** a partition key and MUST NOT appear as a path token for 5A.S0 datasets.
  * 5A.S0 operates at the manifest level, not at the per-seed level.

* **Parameter hash**

  * `parameter_hash` MUST be embedded as a column in both `s0_gate_receipt_5A` and `sealed_inputs_5A`, but:

    * MUST NOT be used as a partition key, and
    * MUST remain constant for all rows under a given `manifest_fingerprint`.

* **Run ID**

  * `run_id` appears only in `s0_gate_receipt_5A` as informational metadata; it is:

    * not part of the primary key,
    * not a partition key, and
    * not used to construct any storage paths.

Downstream 5A states (S1+) MUST treat `manifest_fingerprint` as the **sole partition dimension** for S0 outputs, and MUST join on `manifest_fingerprint` (and `parameter_hash` where present) when combining S0 outputs with other control datasets.

---

### 7.6 Cross-segment identity alignment

Finally, 5A.S0 outputs MUST align with upstream identity in the following ways:

* For each upstream artefact listed in `sealed_inputs_5A`, the combination:

  * `(manifest_fingerprint, owner_segment, artifact_id, schema_ref, sha256_hex)`

  MUST match what that segment’s artefact registry and dataset dictionary declare for this fingerprint.

* `s0_gate_receipt_5A.verified_upstream_segments[seg].bundle_sha256_hex` and `.flag_sha256_hex` MUST match the digests computed in Step 2 of the algorithm, and those in turn MUST match the upstream segment’s own bundle/flag.

Any mismatch indicates catalogue drift or corruption and MUST be treated as a configuration error; 5A.S0 MUST NOT silently “merge” or reconcile such cases.

---

Within these constraints, 5A.S0’s identity, partitions, ordering and merge discipline are fully specified: there is a single, immutable sealed inventory and gate receipt per fingerprint, with deterministic hashing and no cross-run or cross-fingerprint blending.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 5A.S0 itself is considered green**, and the **gating obligations** it imposes on later 5A states (S1+). All rules are **binding**.

---

### 8.1 What it means for 5A.S0 to “PASS”

5A.S0 is considered **successful (green)** for a given `(parameter_hash, manifest_fingerprint)` if and only if **all** of the following hold:

1. **Algorithm completed without internal error**

   * All steps in §6 executed to completion.
   * No configuration or catalogue errors were raised (e.g. missing required 5A policy, inconsistent schema_refs, digest mismatches for required artefacts).

2. **Outputs exist and are schema-valid**

   * A single `s0_gate_receipt_5A` row exists in the expected partition:
     `manifest_fingerprint={manifest_fingerprint}`
     and conforms to `schemas.5A.yaml#/validation/s0_gate_receipt_5A`.
   * A `sealed_inputs_5A` dataset exists in the same fingerprint partition, conforms to `schemas.5A.yaml#/validation/sealed_inputs_5A`, and satisfies its primary-key and non-null constraints.

3. **Identity invariants hold**

   * Embedded `manifest_fingerprint` values in **all** rows equal the partition token `manifest_fingerprint={manifest_fingerprint}`.
   * Embedded `parameter_hash` values in `sealed_inputs_5A` equal the run context `parameter_hash` and are constant for this fingerprint.
   * `s0_gate_receipt_5A.parameter_hash` equals the same `parameter_hash`.

4. **Sealed-input digest is consistent**

   * `sealed_inputs_5A` rows, when serialised using the canonical method in §6.6, produce a digest `sealed_inputs_digest` that:

     * equals the value stored in `s0_gate_receipt_5A.sealed_inputs_digest`.

5. **Upstream status map is complete**

   * `s0_gate_receipt_5A.verified_upstream_segments` contains **exactly one entry** for each segment ID in `{ "1A","1B","2A","2B","3A","3B" }`.
   * Each entry has `status ∈ {"PASS","FAIL","MISSING"}` and, where validation artefacts were discovered, the digests recorded there match the ones recomputed in §6.3.

6. **Scenario binding is well-formed**

   * `scenario_id` (and `scenario_pack_id` / `scenario_version` if present) in `s0_gate_receipt_5A` is consistent with the scenario-related entries in `sealed_inputs_5A` (i.e. they refer to the same parameter pack / config set, and all required scenario artefacts are present).

If any of these criteria fail, 5A.S0 MUST:

* treat the state as **failed** for this `(parameter_hash, manifest_fingerprint)`,
* NOT publish or update `s0_gate_receipt_5A` or `sealed_inputs_5A`, and
* emit a canonical error (see §9).

> **Important:**
> 5A.S0’s own PASS/FAIL is about **internal correctness of the gate**.
> It does **not** by itself assert that upstream segments are green enough to run 5A; that is handled by the gating rules below.

---

### 8.2 Minimal content requirements for `sealed_inputs_5A`

Even if the general conditions above are satisfied, 5A.S0 MUST additionally enforce **content minima** for `sealed_inputs_5A`. For a given fingerprint, the inventory MUST include:

1. **Scenario artefacts**

   * At least one artefact with `role="scenario_config"` for this `parameter_hash`, covering:

     * the scenario calendar and
     * any scenario-level metadata needed by 5A.S1+.

2. **5A policy artefacts**

   * All artefacts marked as `status="REQUIRED"` and `owner_segment="5A"` in the dataset dictionary / registry, e.g.:

     * `merchant_class_policy_5A`,
     * `shape_library_5A`,
     * `scenario_overlay_policy_5A`.

3. **Upstream world surfaces that 5A is designed to consume**

   At minimum, inventory rows for:

   * 1A: merchant/outlet aggregates (e.g. `outlet_catalogue` or equivalent).
   * 2A: `site_timezones` and `tz_timetable_cache` (unless 5A is explicitly configured to operate without them).
   * 3A: `zone_alloc` and `zone_alloc_universe_hash`.
   * 3B: `virtual_classification_3B` (and `virtual_settlement_3B` if settlement features are required).

The exact list is defined in the 5A dataset dictionary and artefact registry via `consumed_by: ["5A"]` and `status: "required"`.

If **any** required artefact is missing from `sealed_inputs_5A` for a fingerprint, 5A.S0 MUST treat this as a failure and MUST NOT mark the state as successful for that fingerprint.

---

### 8.3 Upstream status vs 5A readiness

5A.S0’s `verified_upstream_segments` map can contain `"PASS"`, `"FAIL"` or `"MISSING"` for each upstream segment; S0 is still considered internally green if it recorded those statuses correctly.

However, **5A as a whole MUST NOT proceed** unless upstream segments meet stricter conditions.

For a given `manifest_fingerprint`:

* **5A.S0 itself:**

  * MAY complete successfully even if some upstream segments are `"FAIL"` or `"MISSING"`;
  * MUST accurately reflect those statuses in `s0_gate_receipt_5A`.

* **5A.S1 and all later 5A states:**

  * MUST treat `s0_gate_receipt_5A.verified_upstream_segments[seg].status` as the **sole authority** for upstream readiness.
  * MUST enforce the following gating rule:

    > For Segment 5A to run beyond S0, the status for **all** required upstream segments (1A, 1B, 2A, 2B, 3A, 3B) MUST be `"PASS"`.
    > If any required segment is `"FAIL"` or `"MISSING"`, 5A.S1+ MUST NOT execute business logic and MUST fail fast with a precondition error.

This separates:

* S0’s role as **“what is the current world state?”**, from
* later states’ role as **“are we allowed to proceed with 5A?”**.

---

### 8.4 Gating obligations on downstream 5A states

Any later state in Segment 5A (S1, S2, S3, S4, and the eventual 5A validation state) MUST respect the following **gating obligations**:

1. **Require a valid gate receipt**

   Before performing any work, a 5A state MUST:

   * locate `s0_gate_receipt_5A` for the target `manifest_fingerprint`;
   * validate it against `schemas.5A.yaml#/validation/s0_gate_receipt_5A`;
   * verify that:

     * `parameter_hash` matches its own run context;
     * `sealed_inputs_digest` matches a recomputed digest over the corresponding `sealed_inputs_5A` partition.

   If any of these checks fail, the state MUST abort with a precondition error and MUST NOT attempt to “guess” or reconstruct the sealed universe.

2. **Restrict input universe to `sealed_inputs_5A`**

   * A 5A state MUST only read artefacts that appear as rows in `sealed_inputs_5A` for this fingerprint.
   * If an artefact is not listed, it MUST be treated as out-of-bounds, even if it is physically present in storage.
   * A 5A state MUST respect the `read_scope` value:

     * `ROW_LEVEL` → may read rows;
     * `METADATA_ONLY` → may inspect only metadata or treat as opaque (e.g. alias blob headers).

3. **Require upstream `"PASS"`**

   * Before reading any upstream fact data (e.g. `site_locations`, `site_timezones`, `zone_alloc`), a 5A state MUST check:

     * that the corresponding upstream segment’s status in `s0_gate_receipt_5A.verified_upstream_segments` is `"PASS"`.
   * If not, the state MUST NOT read those datasets and MUST fail with a precondition error.

4. **Scenario binding**

   * A 5A state MUST honour the `scenario_id` (and `scenario_pack_id` / `scenario_version`, if present) recorded in `s0_gate_receipt_5A`.
   * It MUST NOT silently switch to a different scenario, even if multiple scenario config artefacts are present in `sealed_inputs_5A`.

5. **No modification of S0 outputs**

   * No later 5A state may modify or overwrite:

     * `s0_gate_receipt_5A`, or
     * `sealed_inputs_5A`
       for any fingerprint.
   * These datasets are considered **sealed** once S0 has successfully committed them.

---

### 8.5 When 5A.S0 MUST fail (non-acceptance conditions)

Regardless of catalogue state, 5A.S0 MUST treat the state as **failed** (non-accepted) for a fingerprint, and MUST NOT publish its outputs, if any of the following occur:

1. **Missing or inconsistent run identity**

   * `parameter_hash`, `manifest_fingerprint`, or `run_id` are missing or invalid.

2. **Contract-level inconsistencies**

   * Required schema anchors or dictionary/registry entries for 1A–3B or 5A cannot be resolved;
   * `schema_ref` in dictionary/registry does not point to a valid anchor;
   * path templates are malformed or missing required tokens (`fingerprint`).

3. **Required 5A policies or scenario configs unresolved**

   * Any artefact marked as required for 5A in the dictionary/registry (e.g. merchant class policy, shape library, scenario calendar) cannot be resolved for the current `parameter_hash`.

4. **Digest mismatches for required artefacts**

   * For any artefact that **must** be present in `sealed_inputs_5A`, the digest computed by 5A.S0 does not match the digest declared in the registry/dictionary (where such a declaration exists).

5. **Output conflict**

   * An existing `s0_gate_receipt_5A` / `sealed_inputs_5A` for this fingerprint exists and:

     * differs from what S0 would produce (in any field or row), and
     * is not byte-identical under the canonical serialisation.
   * In this case, S0 MUST NOT overwrite; it MUST fail with a conflict error.

In all such cases, 5A.S0 MUST emit a canonical error (see §9) and MUST NOT leave partially updated S0 outputs in the canonical locations.

---

### 8.6 Relationship to the 5A segment-level validation bundle

Later, a dedicated validation state for Segment 5A will produce:

* `validation_bundle_5A`
* `_passed.flag`

using a Layer-2 hashing law similar to Layer-1’s.

Gating obligations:

* That validation state MUST treat:

  * `s0_gate_receipt_5A` and
  * `sealed_inputs_5A`

  as required inputs and MUST re-check their acceptance criteria (schema, identity, digest consistency) as part of Segment 5A’s overall PASS/FAIL.

* Downstream segments (e.g. 5B, 6A) MUST insist on **both**:

  * 5A’s segment-level PASS (`_passed.flag` verified), and
  * a valid `s0_gate_receipt_5A` / `sealed_inputs_5A` pair

  before treating any 5A outputs as readable.

Within these rules, S0 is fully specified as the **gatekeeper** of Segment 5A’s input universe and upstream readiness, and its outputs define the hard preconditions under which any subsequent work in 5A is allowed to proceed.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error codes** that **5A.S0 — Gate & Sealed Inputs** MAY emit, and the exact conditions under which they MUST be raised. These codes are **binding**: implementations MUST use them (or a stable, 1:1 mapping) when reporting failures for 5A.S0.

5A.S0 errors are about **S0 itself** failing to construct a valid gate receipt + sealed inventory.
They are **separate from** upstream segment statuses (`"PASS" / "FAIL" / "MISSING"`) that S0 records in `s0_gate_receipt_5A`.

---

### 9.1 Error reporting contract

5A.S0 MUST surface failures at least via:

* the engine’s **run-report** (per-run, structured log), and
* structured logs / metrics as appropriate.

Each failure MUST include:

* `segment_id = "5A.S0"`
* `error_code` — one of the canonical strings defined below
* `severity` — at least `{"FATAL","WARN"}`
* `message` — short human-readable description
* `details` — optional structured context (e.g. offending artefact IDs, segment IDs, paths)

There is **no dedicated 5A.S0 error dataset**; error reporting reuses the existing engine run-report mechanism.

---

### 9.2 Summary of canonical error codes

The table below lists all canonical error codes for 5A.S0:

| Code                              | Severity | Category                    |
| --------------------------------- | -------- | --------------------------- |
| `S0_RUN_CONTEXT_INVALID`          | FATAL    | Run identity / invocation   |
| `S0_CONTRACT_RESOLUTION_FAILED`   | FATAL    | Schemas / dictionaries      |
| `S0_SCHEMA_ANCHOR_INVALID`        | FATAL    | Schema anchors              |
| `S0_REQUIRED_SCENARIO_MISSING`    | FATAL    | Scenario configuration      |
| `S0_REQUIRED_POLICY_MISSING`      | FATAL    | 5A policy/config            |
| `S0_SEALED_INPUT_SCHEMA_MISMATCH` | FATAL    | Sealed artefact shape       |
| `S0_SEALED_INPUT_DIGEST_MISMATCH` | FATAL    | Sealed artefact digest      |
| `S0_OUTPUT_CONFLICT`              | FATAL    | Existing outputs differ     |
| `S0_IO_READ_FAILED`               | FATAL    | I/O / storage read          |
| `S0_IO_WRITE_FAILED`              | FATAL    | I/O / storage write         |
| `S0_INTERNAL_INVARIANT_VIOLATION` | FATAL    | “Should never happen” guard |

All of these are **stop-the-world** for 5A.S0: if any occurs, S0 MUST NOT publish or modify `s0_gate_receipt_5A` or `sealed_inputs_5A`.

---

### 9.3 Code-by-code definitions

#### 9.3.1 `S0_RUN_CONTEXT_INVALID` *(FATAL)*

**Trigger**

Raised when 5A.S0 cannot establish a valid run identity (§6.2), e.g.:

* `parameter_hash` is missing, empty, or malformed.
* `manifest_fingerprint` is missing, empty, or malformed.
* `run_id` is missing, empty, or otherwise invalid according to engine rules.

**Effect**

* S0 MUST abort immediately.
* No `s0_gate_receipt_5A` or `sealed_inputs_5A` MAY be written.
* Downstream 5A states MUST NOT attempt to run for this (invalid) context.

---

#### 9.3.2 `S0_CONTRACT_RESOLUTION_FAILED` *(FATAL)*

**Trigger**

Raised when 5A.S0 cannot resolve required contracts from schema/dictionary/registry, for example:

* `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.layer2.yaml`, or `schemas.5A.yaml` cannot be loaded or parsed.
* One or more dataset dictionaries for 1A–3B or 5A are missing or invalid.
* One or more artefact registries for 1A–3B or 5A are missing or invalid.

This is **about contracts themselves**, not about specific artefacts for the current fingerprint.

**Effect**

* S0 MUST abort; it cannot safely discover inputs.
* No S0 outputs MAY be written.
* Operator action is to fix deployment/CI (schema/dictionary/registry), not data.

---

#### 9.3.3 `S0_SCHEMA_ANCHOR_INVALID` *(FATAL)*

**Trigger**

Raised when 5A.S0 discovers that a `schema_ref` used for an artefact is not valid, e.g.:

* The JSON Pointer in `schema_ref` does not resolve to any anchor in the referenced schema file.
* The anchor exists but does not describe the expected type (e.g. table vs scalar), according to the dictionary/registry.

Typically detected while building `CANDIDATES` (§6.4) or when preparing `sealed_inputs_5A`.

**Effect**

* S0 MUST abort; it cannot build a trustworthy sealed inventory.
* No outputs MAY be written.
* Fix requires updating schemas/dictionaries so that `schema_ref` values are correct.

---

#### 9.3.4 `S0_REQUIRED_SCENARIO_MISSING` *(FATAL)*

**Trigger**

Raised when scenario-level configuration required by 5A cannot be resolved for this `parameter_hash`, e.g.:

* No artefact marked with `role="scenario_config"` and `status="required"` can be found for the current parameter pack.
* Scenario configs exist but are incompatible (e.g. multiple conflicting scenario IDs without an explicit selection policy).

Typically detected while building `CANDIDATES` or when trying to include scenario artefacts in `SEALED_ROWS`.

**Effect**

* S0 MUST abort; it cannot bind this fingerprint to a well-defined scenario.
* No S0 outputs MAY be written.
* Downstream 5A states MUST NOT attempt to run; operator must fix scenario configuration.

---

#### 9.3.5 `S0_REQUIRED_POLICY_MISSING` *(FATAL)*

**Trigger**

Raised when a 5A-specific policy/config artefact marked as `status="required"` for 5A is not resolvable for this `parameter_hash`, e.g.:

* `merchant_class_policy_5A`, `shape_library_5A`, or `scenario_overlay_policy_5A` is not found in the catalogue for the parameter pack.
* The artefact is present but flagged as deprecated or incompatible by the registry.

**Effect**

* S0 MUST abort.
* No S0 outputs MAY be written.
* Operator must ensure all required 5A policies are deployed and referenced in the dictionary/registry for this parameter pack.

---

#### 9.3.6 `S0_SEALED_INPUT_SCHEMA_MISMATCH` *(FATAL)*

**Trigger**

Raised when, during construction of `sealed_inputs_5A`, S0 discovers that an artefact’s **actual** storage layout does not match what the dictionary/registry claims, e.g.:

* Dataset is missing required columns or has incompatible types.
* Partition keys do not match the declared `partition_keys`.
* The artefact cannot be parsed according to its declared schema (structurally invalid).

This is distinct from `S0_SCHEMA_ANCHOR_INVALID`:

* `S0_SCHEMA_ANCHOR_INVALID` is about the pointer to a schema.
* `S0_SEALED_INPUT_SCHEMA_MISMATCH` is about the **data** not matching that schema.

**Effect**

* S0 MUST abort; this is catalogue drift/corruption.
* No S0 outputs MAY be written.
* Operator must fix the offending dataset or the dictionary/registry to restore consistency.

---

#### 9.3.7 `S0_SEALED_INPUT_DIGEST_MISMATCH` *(FATAL)*

**Trigger**

Raised when, for a required artefact, the digest S0 computes from storage does not match the digest declared in the registry/dictionary (where such a declaration exists), e.g.:

* Registry says `sha256_hex=abc…`, but recomputation yields `def…`.

Typically detected in Step 4 while resolving `sha256_hex` for `SEALED_ROWS`.

**Effect**

* S0 MUST abort; the artefact cannot be trusted.
* No S0 outputs MAY be written.
* Operator must resolve the discrepancy (e.g. stale registry entry, corrupted file, or mis-published artefact).

> Note: This error applies only to artefacts that are required for 5A.
> Optional artefacts may be handled more leniently (e.g. treated as out-of-bounds and marked `status="IGNORED"` without raising an error).

---

#### 9.3.8 `S0_OUTPUT_CONFLICT` *(FATAL)*

**Trigger**

Raised when 5A.S0 detects that **outputs already exist** for this `manifest_fingerprint`, and they are **not** identical to what S0 would compute now, e.g.:

* Existing `sealed_inputs_5A` rows differ from `SEALED_ROWS` under canonical serialisation.
* Existing `s0_gate_receipt_5A` differs in any field from the newly computed receipt.

This includes cases where:

* upstream or catalogue state has changed without a new `manifest_fingerprint`, or
* a previous 5A.S0 run wrote inconsistent outputs.

**Effect**

* S0 MUST NOT overwrite the existing outputs.
* S0 MUST abort with `S0_OUTPUT_CONFLICT`.
* Operator must:

  * either correct/replace the offending outputs manually and re-run, or
  * recompute a new fingerprint for the changed manifest and rerun S0 under that new fingerprint.

This code enforces the **no-merge, no-rewrite** discipline under §7.4.

---

#### 9.3.9 `S0_IO_READ_FAILED` *(FATAL)*

**Trigger**

Raised when I/O problems prevent S0 from reading required inputs, e.g.:

* Storage read errors or permissions issues when accessing:

  * upstream validation bundles or `_passed.flag`,
  * schema/dictionary/registry files,
  * required scenario or policy artefacts.

This code is for genuine I/O/storage failures, not for logical absence (which would be `S0_REQUIRED_*_MISSING` or recorded as `"MISSING"` status for an upstream segment).

**Effect**

* S0 MUST abort; it cannot safely continue.
* No S0 outputs MAY be written.
* Operator must investigate storage/network/permissions issues.

---

#### 9.3.10 `S0_IO_WRITE_FAILED` *(FATAL)*

**Trigger**

Raised when S0 fails to write its outputs robustly, e.g.:

* Failure writing to staging paths for `sealed_inputs_5A` or `s0_gate_receipt_5A`.
* Failure to move staging files to canonical paths atomically.

**Effect**

* S0 MUST treat the state as failed.
* Any partially written staging artefacts MUST remain clearly marked (e.g. under `.staging/`) and MUST be ignored by downstream consumers.
* Operator must fix underlying storage issues and may then re-run S0.

---

#### 9.3.11 `S0_INTERNAL_INVARIANT_VIOLATION` *(FATAL)*

**Trigger**

Catch-all for “should never happen” situations, such as:

* Detected violation of internal invariants that cannot be expressed as a more specific error, e.g.:

  * Duplicate primary-key rows inside `SEALED_ROWS` after de-duplication.
  * Contradictory catalogue information for the same artefact.
  * Logical control paths that are supposed to be unreachable.

**Effect**

* S0 MUST abort and treat the state as failed.
* No outputs MAY be written or modified.
* Operator action is to escalate to engineering; this usually indicates a bug in the implementation or deployment, not in data.

---

### 9.4 Relationship between error codes and upstream statuses

Important distinctions:

* **Upstream `"FAIL"` / `"MISSING"` statuses** in `s0_gate_receipt_5A.verified_upstream_segments` are **not** S0 errors; they are part of S0’s *output* and describe the state of 1A–3B.
* S0’s canonical error codes are raised only when:

  * S0 itself cannot complete correctly, or
  * the catalogue / contracts for 5A are inconsistent, or
  * required artefacts for 5A’s own operation are missing or corrupted.

Downstream 5A states MUST:

* interpret upstream statuses from `s0_gate_receipt_5A` to decide whether 5A may proceed (see §8), and
* interpret these canonical error codes as signals that 5A.S0 itself needs to be fixed or re-run before any other 5A state is invoked.

Within this framework, every failure mode for 5A.S0 is uniquely named, explicitly scoped, and unambiguous in both root cause and required operator behaviour.

---

## 10. Observability & run-report integration *(Binding)*

This section defines how **5A.S0 — Gate & Sealed Inputs** MUST report its activity into the engine’s **run-report** and logging / metrics fabric. These requirements are **binding**.

5A.S0 is control-plane only; observability MUST be **metadata-focused**, not data-heavy.

---

### 10.1 Objectives

Observability for 5A.S0 MUST enable:

1. **Reconstruction of what happened** for a given `(parameter_hash, manifest_fingerprint, run_id)`:

   * Did S0 run?
   * Did it succeed or fail?
   * Which upstream segments were green, red, or missing?
   * Which artefacts were sealed?

2. **Diagnosis of failures**:

   * Clear, canonical error codes (§9).
   * Enough context to locate the offending artefacts/contracts without inspecting bulk data.

3. **Lightweight footprint**:

   * No row-level logging of upstream datasets.
   * No logging of arbitrary JSON blobs that duplicate `sealed_inputs_5A` in-line.

---

### 10.2 Run-report entries

The engine’s **run-report** (or equivalent per-run summary) MUST contain structured entries for 5A.S0.

For each **invocation** of 5A.S0, the run-report MUST include at least:

* `segment_id`: `"5A.S0"`
* `parameter_hash`
* `manifest_fingerprint`
* `run_id`
* `state_status ∈ {"STARTED","SUCCESS","FAILED"}`
* `start_utc` and `end_utc` timestamps
* `duration_ms` (derived)

On **SUCCESS**, the run-report entry for 5A.S0 MUST additionally record:

* `sealed_inputs_digest` (from `s0_gate_receipt_5A`)
* `sealed_inputs_count_total` (row count from `sealed_inputs_5A`)
* `sealed_inputs_count_by_role` (map role→count; e.g. upstream_egress, reference_data, scenario_config, policy, contract)
* `upstream_status_summary` — a compact map of:

  ```json5
  {
    "1A": "PASS" | "FAIL" | "MISSING",
    "1B": "PASS" | "FAIL" | "MISSING",
    "2A": "PASS" | "FAIL" | "MISSING",
    "2B": "PASS" | "FAIL" | "MISSING",
    "3A": "PASS" | "FAIL" | "MISSING",
    "3B": "PASS" | "FAIL" | "MISSING"
  }
  ```

On **FAILED**, the run-report entry MUST record:

* `error_code` (one of §9’s canonical codes)
* `error_message` (short text)
* `error_details` (optional structured context, e.g. offending segment ID, artefact ID)

The run-report MUST be the **primary source** for S0’s outcome; downstream monitoring / dashboards MAY be built on top of it.

---

### 10.3 Structured logging (per-run)

In addition to the run-report, 5A.S0 MUST emit **structured logs** at key lifecycle points. These logs MUST be:

* keyed by `segment_id="5A.S0"` and `run_id`, and
* parseable (e.g. JSON lines).

At minimum:

1. **State start log**

   Emitted once, before any work:

   * level: `INFO`
   * fields:

     * `segment_id = "5A.S0"`
     * `event = "state_start"`
     * `parameter_hash`, `manifest_fingerprint`, `run_id`
     * optional environment tags (e.g. `env`, `ci_build_id`)

2. **Upstream verification summary**

   Emitted once after Step 2 (§6.3) completes:

   * level: `INFO`
   * fields:

     * `event = "upstream_status"`
     * `upstream_status` map as in §8.3
     * `n_upstream_pass`, `n_upstream_fail`, `n_upstream_missing`

   No bundle contents or paths need be logged; only segment IDs and statuses.

3. **Sealed-input inventory summary**

   Emitted once after Step 5 (§6.6) completes:

   * level: `INFO`
   * fields:

     * `event = "sealed_inputs_summary"`
     * `sealed_inputs_digest`
     * `sealed_inputs_count_total`
     * `sealed_inputs_count_by_role` (role→count)
     * `sealed_inputs_policy_ids` (optional: IDs of key 5A policies & scenario configs)

4. **State success log**

   Emitted once on successful commit:

   * level: `INFO`
   * fields:

     * `event = "state_success"`
     * `parameter_hash`, `manifest_fingerprint`, `run_id`
     * `sealed_inputs_digest`
     * `duration_ms`

5. **State failure log**

   Emitted once on failure (any fatal error):

   * level: `ERROR`
   * fields:

     * `event = "state_failure"`
     * `parameter_hash`, `manifest_fingerprint`, `run_id`
     * `error_code`
     * `error_message`
     * `error_details` (where available; e.g. `{ "segment": "1B", "artifact_id": "site_locations" }`)

**Prohibited logging:**

* S0 MUST NOT log:

  * entire rows from upstream fact datasets,
  * entire `sealed_inputs_5A` as an in-line JSON blob, or
  * any content that would allow reconstruction of bulk data.

---

### 10.4 Metrics

5A.S0 MUST expose a small set of **metrics** suitable for time-series monitoring. Exact metric names are implementation-specific, but the semantic intent is binding.

Recommended metrics (per engine / deployment):

1. **State-level counters**

   * `fraudengine_5A_s0_runs_total{status="success"|"failure"}`
   * `fraudengine_5A_s0_upstream_missing_total{segment="1A"|"1B"|...}`
   * `fraudengine_5A_s0_upstream_fail_total{segment="1A"|"1B"|...}`

2. **Latency**

   * `fraudengine_5A_s0_duration_ms` (histogram or summary)

3. **Sealed inventory size**

   * `fraudengine_5A_s0_sealed_inputs_count` (gauge, per-run)
   * `fraudengine_5A_s0_sealed_inputs_by_role{role="upstream_egress"|"reference_data"|...}`

4. **Error codes**

   * `fraudengine_5A_s0_errors_total{error_code="S0_REQUIRED_POLICY_MISSING"|...}`

Metrics MUST be emitted in a way that they can be aggregated across runs and environments, but MUST NOT reveal sensitive paths or schema internals.

---

### 10.5 Correlation & traceability

5A.S0 MUST support correlation across logs, metrics, and datasets:

* Every log entry and run-report record MUST include:

  * `segment_id = "5A.S0"`
  * `parameter_hash`
  * `manifest_fingerprint`
  * `run_id`

* The `run_id` recorded in:

  * logs,
  * run-report, and
  * `s0_gate_receipt_5A`

  MUST match, enabling operators to trace a run from control-plane outputs back through logs and metrics.

If the engine supports distributed tracing (e.g. trace IDs / span IDs), 5A.S0 SHOULD:

* create or join a trace span for `"5A.S0"`, and
* annotate it with the same identifiers (`parameter_hash`, `manifest_fingerprint`, `run_id`).

---

### 10.6 Integration with 5A segment-level validation & dashboards

The eventual 5A segment-level validation state (e.g. `5A.SX_validation`) MUST:

* include `s0_gate_receipt_5A` and `sealed_inputs_5A` as inputs to its bundle, and
* ensure that a valid 5A.S0 run-report entry with `state_status="SUCCESS"` exists for the same `(parameter_hash, manifest_fingerprint)`.

Operational dashboards SHOULD be able to answer, using S0’s observability signals:

* For a given fingerprint:

  * Has 5A.S0 run?
  * Did it succeed?
  * How many artefacts were sealed?
  * Which upstream segments are still failing or missing?

Downstream segments (5A.S1–S4, 5B, 6A) MUST **not** implement their own ad-hoc checks for S0’s success; instead, they MUST:

* consult `s0_gate_receipt_5A` + `sealed_inputs_5A` (as per §§4–8), and
* may use the run-report/metrics purely as secondary diagnostics.

Within these rules, 5A.S0 is fully observable: its behaviour is transparent, diagnosable, and lightweight, and its outputs can be reliably tied back to logs and metrics without leaking or duplicating bulk data.

---

## 11. Performance & scalability *(Informative)*

This section provides **non-binding guidance** on the expected performance profile of **5A.S0 — Gate & Sealed Inputs**, and on how to scale it safely. It explains what should be fast, what grows with catalogue size, and where orchestration should pay attention.

---

### 11.1 Performance summary

* 5A.S0 is **metadata-only** and **RNG-free**.
* It does **not** touch bulk fact tables at row level.
* Its runtime is dominated by:

  * reading small contracts (schemas, dictionaries, registries),
  * reading small validation bundles and `_passed.flag` for 1A–3B,
  * computing digests over those sealed artefacts, and
  * building / writing a small sealed inventory (`sealed_inputs_5A`) and receipt.

In a healthy deployment, S0 should be **much cheaper** than any data-heavy states (e.g. 1B, 2B, 5B) and should scale primarily with the number of **artefacts** in the manifest, not with the number of rows in upstream datasets.

---

### 11.2 Workload characteristics

**Input size characteristics**

* **Contracts** (schemas, dictionaries, registries):

  * Dozens to a few hundred small YAML/JSON files.
  * Typically O(10–100 KiB) each.

* **Validation bundles (1A–3B)**:

  * A small number of JSON/Parquet/sidecar files per segment.
  * Typically O(10–100) files in total, often <10 MiB per bundle.

* **Sealed artefacts**:

  * Number of artefacts that 5A may consume is bounded by:

    * number of upstream segments (fixed at 6 for Layer-1), and
    * number of 5A/Layer-2 configs & policies (usually small).

**Output size characteristics**

* `s0_gate_receipt_5A`:

  * Single JSON object per fingerprint; typically <<10 KiB.

* `sealed_inputs_5A`:

  * One row per admissible artefact; typical row counts O(10–100), rarely exceeding a few hundred.
  * Stored as a small Parquet file; typical size O(10–100 KiB).

S0 is therefore **latency-sensitive**, but not throughput-limited by data volume in normal operation.

---

### 11.3 Complexity bounds

For a given **fingerprint** and **parameter pack**, the steady-state complexity is:

* Let:

  * `N_seg = 6` (fixed: 1A, 1B, 2A, 2B, 3A, 3B),
  * `N_artifacts =` number of artefacts 5A may consume (upstream + 5A-specific),
  * `N_files_bundle =` total number of files across upstream validation bundles.

Then:

* **Catalogue resolution & candidate discovery**:

  * O(`N_artifacts`) metadata lookups (dictionary/registry).
  * Typically small; dictionary/registry are in-memory/fast-cache in most deployments.

* **Upstream bundle verification**:

  * O(`N_seg + N_files_bundle`) file reads and digest computations.
  * `N_seg` is fixed; `N_files_bundle` is designed to be modest (tens, not thousands).

* **Sealed inventory construction**:

  * O(`N_artifacts`) for building rows.
  * Sorting `SEALED_ROWS` is O(`N_artifacts log N_artifacts`) — negligible at tens/hundreds of rows.

* **Digest computation for `sealed_inputs_5A`**:

  * O(`N_artifacts`) to serialise and hash; dominated by hashing speed, not row count.

Overall, for a single fingerprint:

> **Time complexity** ≈ O(`N_artifacts + N_files_bundle`)
> **Space complexity** ≈ O(`N_artifacts`) in memory.

Both are small under reasonable constraints on the catalogue/manifest.

---

### 11.4 I/O patterns & hotspots

**Reads**

* Small, scattered reads:

  * Schema/dictionary/registry files.
  * Validation bundles and `_passed.flag` for 1A–3B.
  * Optionally: reading file headers for required artefacts to compute/verify digests.

**Writes**

* Two small, sequential writes per fingerprint:

  * `sealed_inputs_5A` (single JSON file).
  * `s0_gate_receipt_5A` (single JSON file).

**Potential hotspots**

* **Digest computation** for large artefacts:

  * If some artefacts are large (e.g. big binary blobs or large reference tables) and 5A.S0 is required to compute or re-verify their `sha256_hex`, this can dominate runtime.
  * In such cases, deployments may:

    * pre-materialise digests at publication time and store them in the registry, so S0 can trust them, or
    * limit S0 to hashing index/manifest files rather than full datasets.

* **Shared storage saturation**:

  * If many fingerprints/runs run S0 concurrently, they will all read the same upstream bundles and contracts, potentially hitting shared storage.
  * Caching—at the engine runtime or storage layer—can mitigate this.

---

### 11.5 Parallelisation & scheduling

5A.S0 is naturally **embarrassingly parallel** across fingerprints:

* For distinct `(parameter_hash, manifest_fingerprint)` pairs:

  * S0 runs do not share mutable state.
  * They only read shared contracts and upstream bundles.

Recommended practices:

* **Per-fingerprint isolation**:

  * Schedule one S0 instance per fingerprint in parallel, subject to I/O constraints.
  * Use single-writer semantics per fingerprint to avoid `S0_OUTPUT_CONFLICT`.

* **Warm-up / caching**:

  * Load schemas/dictionaries/registries into a shared cache at process startup to avoid re-parsing them per run.
  * Consider caching upstream bundle indices (`index.json`) across runs for the same fingerprint.

* **Batching**:

  * If many fingerprints share the same `parameter_hash` and upstream contracts, an implementation MAY:

    * batch the contract loading & parsing, and
    * then run the per-fingerprint S0 logic in parallel with shared in-memory contract state.

---

### 11.6 Failure, retry & backoff

Because S0 is control-plane:

* **Transient failures** (e.g. `S0_IO_READ_FAILED`, `S0_IO_WRITE_FAILED`):

  * Often safe to **retry** after a backoff, as long as:

    * the underlying storage/network issue is transient, and
    * no partial S0 outputs were committed to canonical paths.

* **Deterministic failures** (e.g. `S0_REQUIRED_POLICY_MISSING`, `S0_OUTPUT_CONFLICT`):

  * Retrying without changing deployment/catalogue state will not help.
  * Orchestration should:

    * stop retrying,
    * surface the error to operators, and
    * require configuration/catalogue fixes.

S0’s runtime is usually short; frequent retries on transient errors should be inexpensive but should still be bounded to avoid noisy flapping in monitoring.

---

### 11.7 Suggested SLOs (non-binding)

Implementations may choose SLOs along these lines (non-binding suggestions):

* **Latency per fingerprint**:

  * p50: < 1–2 seconds
  * p95: < 5 seconds
    under normal storage conditions and modest `N_files_bundle`.

* **Error budget**:

  * `S0_IO_*` errors kept rare (e.g. < 0.1% of runs),
  * configuration errors (required policy/scenario missing) treated as deployment issues, not operational noise.

* **Scale expectations**:

  * Hundreds or low thousands of fingerprints per day should be feasible on modest infrastructure, given S0’s lightweight profile.

These values are illustrative; actual targets depend on environment, storage, and how often new fingerprints are minted.

---

Within these guidelines, 5A.S0 should remain a **cheap, scalable gate**: quick to run, easy to parallelise, and unlikely to become a bottleneck compared to the data-heavy states in Layer-1 and later Layer-2 segments.

---

## 12. Change control & compatibility *(Binding)*

This section defines how **5A.S0 — Gate & Sealed Inputs** and its contracts may evolve over time, and what compatibility guarantees MUST hold. All rules here are **binding**.

The goal is:

* no silent behaviour changes,
* no “surprise” breakage for downstream segments (5A.S1–S4, 5B, 6A), and
* a clear path for introducing new capabilities via **backwards-compatible** changes.

---

### 12.1 Scope of change control

Change control for 5A.S0 covers:

1. **Row shapes & schemas**

   * `schemas.5A.yaml#/validation/s0_gate_receipt_5A`
   * `schemas.5A.yaml#/validation/sealed_inputs_5A`
   * `schemas.5A.yaml#/validation/scenario_manifest_5A` (if implemented)

2. **Catalogue contracts**

   * `dataset_dictionary.layer2.5A.yaml` entries for
     `s0_gate_receipt_5A`, `sealed_inputs_5A`, `scenario_manifest_5A`.
   * `artefact_registry_5A.yaml` entries for the same artefacts.

3. **Algorithm & semantics**

   * The deterministic algorithm in §6.
   * Identity & merge discipline in §7.
   * Acceptance & gating rules in §8.

Changes to **Layer-1 contracts** (1A–3B) are governed by their own specs; this section only constrains how 5A.S0 responds to such changes.

---

### 12.2 Versioning of 5A.S0 contracts

#### 12.2.1 Schema version field

To support evolution, `s0_gate_receipt_5A` MUST include a **spec/schema version** field:

* `s0_spec_version` — string, e.g. `"1.0.0"`

Requirements:

* `s0_spec_version` MUST be:

  * required in `s0_gate_receipt_5A` schema,
  * set by 5A.S0 to the version of this spec that the implementation claims to follow.

* `sealed_inputs_5A` and `scenario_manifest_5A` MAY omit a per-row version field, but:

  * the schema file `schemas.5A.yaml` SHOULD carry a `$id` / `version` that is bumped according to the same scheme.

#### 12.2.2 Versioning scheme

5A.S0 MUST use a semantic-style versioning scheme for `s0_spec_version`:

* **MAJOR.MINOR.PATCH**

Interpretation:

* **MAJOR** — incremented when **backwards-incompatible** changes are introduced that:

  * change primary keys, partitioning, or path templates;
  * change required fields’ types or semantics;
  * change the hashing law for `sealed_inputs_digest`; or
  * change the gating rules in §8 such that previously valid receipts would now be rejected.

* **MINOR** — incremented when **backwards-compatible** changes are introduced, such as:

  * new optional fields;
  * new `role` or `status` enum values that consumers can safely ignore if unknown;
  * additional artefacts in `sealed_inputs_5A` with `status="OPTIONAL"`.

* **PATCH** — incremented for bug fixes or clarifications that do not change shapes or observable behaviour.

Downstream consumers (5A.S1+, 5B, 6A) MUST:

* parse `s0_spec_version`, and
* refuse to run if the MAJOR version is outside their supported range.

---

### 12.3 Backwards-compatible changes (allowed without forcing a new MAJOR)

The following changes are considered **backwards-compatible** for 5A.S0, provided they follow the rules below:

1. **Adding optional fields**

   * Adding new fields to:

     * `s0_gate_receipt_5A`,
     * `sealed_inputs_5A`,
     * `scenario_manifest_5A`
       is allowed if:
   * they are **optional** in the JSON-Schema;
   * default semantics for “field absent” are clearly defined;
   * existing consumers can safely ignore them.

2. **Adding new roles / statuses / read_scopes**

   * Adding new allowed values to:

     * `role` enum in `sealed_inputs_5A`,
     * `status` enum (e.g. new non-critical statuses for artefacts),
     * `read_scope` enum (e.g. adding `"METADATA_AND_SAMPLE"` in future)

   is allowed if:

   * the spec defines how unknown values MUST be treated by older consumers (e.g. “treat unknown `role` as `IGNORED` / out of bounds”);
   * new values are not used in a way that silently breaks existing behaviour.

3. **Adding new artefacts to `sealed_inputs_5A`**

   * Introducing new sealed artefacts (rows) with:

     * `status="OPTIONAL"` or `status="IGNORED"` for 5A, or
     * `status="REQUIRED"` but **only** for new 5A features that are also guarded by `s0_spec_version` and not required by older binaries.

   is allowed, but:

   * It will change `sealed_inputs_digest` and thus produce a new `s0_gate_receipt_5A` for affected fingerprints.
   * It MUST be accompanied by a change in either:

     * the engine manifest (yielding a new `manifest_fingerprint`), or
     * the `parameter_hash` (if the change is tied to parameter pack updates).

   In other words: **changing the sealed input universe is not transparent**; it must be reflected in identity.

4. **Adding new structured logs or metrics**

   * New log fields and new metrics are allowed.
   * They MUST NOT change the semantics of existing fields/metrics.

5. **Non-breaking acceptance criteria tightening**

   * Adding new checks in §8 that only reject clearly invalid states (e.g. enforcing non-empty `scenario_id`) is allowed, as long as:

     * previously valid runs remain valid, and
     * only “bad” runs that would have caused problems downstream are newly rejected.

These changes MUST bump at least the **MINOR** version of `s0_spec_version`.

---

### 12.4 Backwards-incompatible changes (require new MAJOR)

The following changes are **backwards-incompatible** and MUST be accompanied by a **MAJOR** bump in `s0_spec_version` and a coordinated rollout:

1. **Changing primary keys or partitioning**

   * Changing `primary_key` or `partition_keys` for:

     * `s0_gate_receipt_5A`,
     * `sealed_inputs_5A`,
     * `scenario_manifest_5A`,

   is incompatible and MUST be treated as a new MAJOR version. Existing data would not match the new expectations.

2. **Changing path templates**

   * Changing `path_template` for 5A.S0 outputs (e.g. moving from `data/layer2/5A/...` to another layout) is incompatible.

3. **Changing field types or semantics**

   * Changing the type of a required field (e.g. `scenario_id` from string → array) or its core meaning is incompatible.
   * Changing enumeration semantics (e.g. redefining `"PASS"` to mean something different) is incompatible.

4. **Changing hashing law for `sealed_inputs_digest`**

   * Any change to:

     * which fields are included in the digest,
     * row ordering for serialisation, or
     * the hash algorithm itself (e.g. from SHA-256 to something else),

   is incompatible and MUST be a MAJOR bump. Downstream equality checks depend on this law.

5. **Changing gating rules in a way that rejects previously valid receipts**

   * For example, changing the rule “all upstream segments must be `PASS` for 5A to proceed” to a different set of required segments is a semantic breaking change for downstream gating.
   * Such changes require a new MAJOR version and a coordinated change in all consumers.

6. **Removing or repurposing fields**

   * Removing previously required fields, or
   * repurposing fields with the same name for different semantics,

   is incompatible and MUST be avoided; when unavoidable, treat it as a new MAJOR.

Implementations MUST refuse to interpret `s0_gate_receipt_5A` with an unsupported **MAJOR** version.

---

### 12.5 Compatibility of code with existing data

Implementations of 5A.S0 and its consumers MUST be prepared to see **older data** in storage:

1. **Reading older `s0_gate_receipt_5A` / `sealed_inputs_5A`**

   * Newer code MUST:

     * read and interpret receipts whose `s0_spec_version.MAJOR` is within its supported range;
     * treat **unknown optional fields** as absent;
     * treat **unknown `role` / `status` / `read_scope` values** as “ignored/out-of-bounds”, unless the spec explicitly allows new values.

   * If `s0_spec_version.MAJOR` is **greater** than the implementation supports, the implementation MUST:

     * refuse to process 5A for that fingerprint, and
     * surface a clear “unsupported spec version” error in its own run-report.

2. **Re-running S0 with a newer implementation**

   * When re-running S0 with a new version for an existing `manifest_fingerprint`:

     * If the catalogue state and contracts are unchanged, outputs SHOULD remain byte-identical (idempotent).
     * If catalogue state changed in a way that affects `sealed_inputs_5A`, a new `manifest_fingerprint` SHOULD be minted; reusing the old fingerprint is discouraged and may trigger `S0_OUTPUT_CONFLICT`.

3. **Migrating to a new MAJOR**

   * Major-version changes should usually accompany:

     * a new engine release, and
     * a process to either:

       * re-run S0 for all active fingerprints under the new version, or
       * treat old fingerprints (with old MAJOR) as “frozen” and unsupported for new downstream segments.

---

### 12.6 Interaction with upstream changes

Upstream segments (1A–3B) may themselves evolve. 5A.S0 MUST respond as follows:

1. **New upstream artefacts or fields**

   * If an upstream segment adds new optional fields or artefacts and 5A’s dictionary/registry is updated to consume them:

     * this is treated as the “adding new artefacts” case in §12.3;
     * `sealed_inputs_5A` will change, and so will `sealed_inputs_digest`;
     * this SHOULD be accompanied by a new `manifest_fingerprint` and/or `parameter_hash`.

2. **Upstream schema tightening**

   * If an upstream segment tightens its own schemas (e.g. more required columns), 5A.S0’s responsibility is only to ensure:

     * that artefacts it seals still match their declared schema;
     * if not, it must raise `S0_SEALED_INPUT_SCHEMA_MISMATCH`.

3. **Upstream hashing-law changes**

   * If an upstream segment changes its validation bundle hashing law, that segment’s own spec and versioning cover it.
   * 5A.S0 must always:

     * use the upstream segment’s declared hashing law;
     * treat mismatch as an upstream `"FAIL"` status rather than trying to infer backwards compatibility.

---

### 12.7 Governance & documentation

Finally, any change to 5A.S0 contracts MUST be governed and documented:

1. **Spec updates**

   * Changes to §§1–12 for 5A.S0 MUST be versioned and reviewed alongside corresponding:

     * schema changes in `schemas.5A.yaml` / `schemas.layer2.yaml`,
     * dictionary changes in `dataset_dictionary.layer2.5A.yaml`,
     * registry changes in `artefact_registry_5A.yaml`.

2. **Release notes**

   * Every change that bumps `s0_spec_version` MUST be summarised in release notes that:

     * state the old and new version;
     * clarify whether the change is MAJOR, MINOR, or PATCH;
     * describe any actions required for existing fingerprints (e.g. re-run S0, or treat old fingerprints as frozen).

3. **Testing**

   * New implementations of 5A.S0 MUST be tested against:

     * synthetic catalogues that emulate old spec versions;
     * representative “real” catalogues.
   * Tests MUST include:

     * idempotency checks (same version, same inputs → same outputs),
     * conflict detection checks (`S0_OUTPUT_CONFLICT` scenarios),
     * and backwards-compatibility checks (new code reading old receipts within supported MAJOR).

Within these rules, 5A.S0 can evolve over time without surprising downstream segments or corrupting the authority chain: new capabilities come via clear version bumps, and any incompatible change is explicit, gated, and coordinated.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix standardises the short-hands, symbols and abbreviations used in the 5A.S0 spec. It is **informative** only; where a definition conflicts with a binding section, the binding section wins.

---

### 13.1 Notation conventions

* **Monospace** identifiers (e.g. `parameter_hash`, `sealed_inputs_5A`) refer to concrete fields, datasets or config keys as they appear in schemas, dictionaries or registries.
* **UPPER_SNAKE** identifiers (e.g. `S0_OUTPUT_CONFLICT`) refer to canonical error codes.
* `"Quoted"` identifiers refer to string values of enums or labels (e.g. `"PASS"`, `"ROW_LEVEL"`).
* Segment and layer identifiers use the existing engine convention:

  * `1A`, `1B`, `2A`, `2B`, `3A`, `3B`, `5A`, `5B`, `6A`, etc.
  * `Layer-1`, `Layer-2`, `Layer-3`.

---

### 13.2 Core symbols (identity & scope)

| Symbol / field         | Meaning                                                                                                 |
|------------------------|---------------------------------------------------------------------------------------------------------|
| `parameter_hash`       | Opaque identifier of the **parameter pack** (policies, configs, scenario pack) used for this run.       |
| `manifest_fingerprint` | Opaque identifier of the **closed world manifest** (set of artefacts) for this run.                     |
| `run_id`               | Unique identifier of this execution of 5A.S0 for a given `(parameter_hash, manifest_fingerprint)`.      |
| `fingerprint`          | Partition token derived from `manifest_fingerprint` (e.g. `manifest_fingerprint={manifest_fingerprint}`).        |
| `s0_spec_version`      | Semantic version of the 5A.S0 spec that the implementation claims to follow.                            |
| `scenario_id`          | Identifier of the scenario active for this fingerprint (e.g. `"baseline"`, `"bf_2025_stress"`).         |
| `scenario_pack_id`     | Optional identifier of the scenario configuration pack / bundle.                                        |
| `sealed_inputs_digest` | Digest (e.g. SHA-256) over the canonical serialisation of `sealed_inputs_5A` rows for this fingerprint. |

---

### 13.3 Datasets & artefact identifiers

| Name / ID                           | Description                                                                                      |
|-------------------------------------|--------------------------------------------------------------------------------------------------|
| `s0_gate_receipt_5A`                | Fingerprint-scoped control dataset: one-row receipt summarising S0 run, upstream status, inputs. |
| `sealed_inputs_5A`                  | Fingerprint-scoped inventory: one row per artefact 5A is allowed to read.                        |
| `scenario_manifest_5A`              | Optional fingerprint-scoped summary of scenario horizon & labels.                                |
| `validation_bundle_*`               | Generic name for a segment’s validation bundle directory (Layer-1 or Layer-2).                   |
| `_passed.flag`                    | Generic name for a segment’s PASS flag file (Layer-1 or Layer-2).                                |
| `schemas.layer1.yaml`               | Layer-1 shared schema bundle (primitives, RNG, validation, etc.).                                |
| `schemas.ingress.layer1.yaml`       | Layer-1 ingress schema bundle (worldbank, ISO, tz, rasters).                                     |
| `schemas.layer2.yaml`               | Layer-2 shared schema bundle (validation bundle/index shapes, etc.).                             |
| `schemas.5A.yaml`                   | Segment 5A schema bundle (including `s0_gate_receipt_5A`, `sealed_inputs_5A`, etc.).             |
| `dataset_dictionary.layer2.5A.yaml` | Dataset dictionary for Segment 5A.                                                               |
| `artefact_registry_5A.yaml`         | Artefact registry for Segment 5A.                                                                |

---

### 13.4 Fields within `sealed_inputs_5A`

| Field name          | Meaning                                                                                                                                                                |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `owner_layer`       | Logical layer that owns the artefact (e.g. `"layer1"`, `"layer2"`, `"engine"`).                                                                                        |
| `owner_segment`     | Segment that owns the artefact (e.g. `"1A"`, `"2B"`, `"3A"`, `"3B"`, `"5A"`).                                                                                          |
| `artifact_id`       | Logical artefact identifier from the relevant artefact registry.                                                                                                       |
| `manifest_key`      | Manifest key used to address this artefact in the engine’s manifest (if defined by registry).                                                                          |
| `role`              | 5A-local role classification, e.g. `"upstream_egress"`, `"reference_data"`, `"scenario_config"`, `"policy"`, `"contract"`, `"validation_bundle"`, `"validation_flag"`. |
| `schema_ref`        | JSON-Schema anchor describing the artefact’s shape (e.g. `schemas.layer1.yaml#/egress/site_locations`).                                                                |
| `path_template`     | Catalogue path template with tokens (e.g. `manifest_fingerprint={manifest_fingerprint}`).                                                                                       |
| `partition_keys`    | List of partition columns for the artefact’s dataset (if applicable).                                                                                                  |
| `sha256_hex`        | Integrity digest of the artefact content or index for this fingerprint.                                                                                                |
| `version`           | Version string for the artefact (e.g. semver, data-version).                                                                                                           |
| `source_dictionary` | Name of dataset dictionary that declares the artefact.                                                                                                                 |
| `source_registry`   | Name of artefact registry that declares the artefact.                                                                                                                  |
| `status`            | 5A’s view of necessity: `"REQUIRED"`, `"OPTIONAL"`, `"IGNORED"`.                                                                                                       |
| `read_scope`        | How 5A may use the artefact: `"ROW_LEVEL"` or `"METADATA_ONLY"`.                                                                                                       |

---

### 13.5 Upstream segment codes (1A–3B)

| Code | Segment (informal name)                       |
| ---- | --------------------------------------------- |
| `1A` | Merchants → outlet catalogue (country counts) |
| `1B` | Geolocation of sites (lat/lon per outlet)     |
| `2A` | Civil time (`site_timezones`, tz timetable)   |
| `2B` | Routing weights, alias tables, day effects    |
| `3A` | Zone allocation (merchant×country×tzid)       |
| `3B` | Virtual merchants & CDN edge universe         |

In `s0_gate_receipt_5A.verified_upstream_segments`, these codes appear as object keys (strings).

---

### 13.6 Error codes (5A.S0)

For convenience, the canonical error codes from §9 are listed here:

| Code                              | Brief description                                             |
|-----------------------------------|---------------------------------------------------------------|
| `S0_RUN_CONTEXT_INVALID`          | Run identity (parameter_hash / fingerprint / run_id) invalid. |
| `S0_CONTRACT_RESOLUTION_FAILED`   | Schemas/dictionaries/registries cannot be resolved.           |
| `S0_SCHEMA_ANCHOR_INVALID`        | `schema_ref` points to an invalid/mismatched anchor.          |
| `S0_REQUIRED_SCENARIO_MISSING`    | Required scenario configuration missing.                      |
| `S0_REQUIRED_POLICY_MISSING`      | Required 5A policy/config missing.                            |
| `S0_SEALED_INPUT_SCHEMA_MISMATCH` | Sealed artefact’s data does not match declared schema.        |
| `S0_SEALED_INPUT_DIGEST_MISMATCH` | Digest of sealed artefact does not match registry/dictionary. |
| `S0_OUTPUT_CONFLICT`              | Existing S0 outputs differ from recomputed ones.              |
| `S0_IO_READ_FAILED`               | I/O failure when reading required inputs.                     |
| `S0_IO_WRITE_FAILED`              | I/O failure when writing S0 outputs.                          |
| `S0_INTERNAL_INVARIANT_VIOLATION` | Catch-all for impossible / invariant-breaking states.         |

These codes appear only in logs/layer2/5A/run-report, not in `s0_gate_receipt_5A` or `sealed_inputs_5A` schemas.

---

### 13.7 Miscellaneous abbreviations

| Abbreviation |   | Meaning                                                          |
| ------------ |:--| ---------------------------------------------------------------- |
| S0           |   | State 0 within a segment (here: 5A.S0).                          |
| L1 / L2      |   | Layer-1 / Layer-2.                                               |
| “bundle”     |   | Validation bundle directory for a segment.                       |
| “gate”       |   | A state whose primary role is to verify & seal inputs (e.g. S0). |

This appendix is not exhaustive, but covers the symbols and abbreviations that appear most often in the 5A.S0 spec.

---
