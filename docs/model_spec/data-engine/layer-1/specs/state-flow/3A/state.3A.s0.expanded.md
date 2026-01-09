# State 3A·S0 — Gate & Sealed Inputs for Zone Allocation

## 1. Purpose & scope **(Binding)**

State **3A.S0 — Gate & Sealed Inputs for Zone Allocation** defines the closed-world boundary and trust anchor for Segment 3A. Its role is to prove that 3A runs only against a fully-governed, reproducible set of upstream artefacts and policy inputs, and to expose this fact as a small, stable set of authority surfaces for downstream 3A states and cross-segment validators.

Concretely, 3A.S0:

* **Verifies upstream readiness for zone allocation.**
  For a given `manifest_fingerprint`, S0 confirms that the Layer 1 upstream it depends on is green:

  * The **Layer-wide schema packs** and **ingress schema pack** (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`) are resolvable and schema-valid.
  * The **Layer 1 dictionaries and artefact registries** for segments 1A, 1B, 2A, 2B are available and internally consistent (IDs, paths, schema_refs, roles).
  * The **2A validation bundle and `_passed.flag`** for this `manifest_fingerprint` exist and pass the standard HashGate check.
    S0 relies on these checks to assert that any 3A use of 1A/1B/2A surfaces occurs only after their own segment gates have passed.

* **Seals 3A’s input universe.**
  S0 enumerates and seals the specific artefacts 3A is allowed to read for this `manifest_fingerprint`, including:

  * Upstream **reference data** (e.g. ISO country codes, tz-world geometry, any 2A/ingress surfaces 3A will rely on structurally).
  * Upstream **segment outputs** needed as logical inputs to zone allocation (e.g. 1A country-level outlet counts, 2A tzid universe / cache), but **not** any 2B plan or runtime surfaces.
  * 3A’s **governed policy and prior packs** (e.g. zone mixture policy, country→zone α-priors, zone floor/bump rules, and any 2B day-effect policy that 3A treats as a parameter input rather than an output).
    S0 treats this sealed set as the *only* admissible input universe for 3A; later states MUST NOT reach outside this sealed set.

* **Publishes 3A’s gate and sealed-input inventory as authority surfaces.**
  S0 produces two small, fingerprint-scoped artefacts:

  * A **gate receipt** (`s0_gate_receipt_3A`) that records which upstream validation bundles and flags were verified, which schema/dictionary/registry packs were used, and which policy/prior bundles were sealed.
  * A **sealed-inputs inventory** (`sealed_inputs_3A`) that lists, for this `manifest_fingerprint`, the exact catalogue paths, schema_refs, digests and logical roles of all artefacts 3A is allowed to touch.
    These artefacts are the **only binding evidence** that 3A has a valid, closed-world view of its inputs; all later 3A states (S1–S7) MUST treat their presence as a precondition.

* **Aligns 3A with Layer 1 identity and partition laws.**
  S0 does not define `parameter_hash`, `seed` or `run_id`, but it **binds** 3A to the existing Layer 1 lineage and partition law by:

  * Requiring that `parameter_hash` and `manifest_fingerprint` have already been resolved according to the Layer 1 S0 design.
  * Ensuring that all 3A artefacts it introduces obey the same partitioning regime (e.g. fingerprint-only for gate/validation surfaces) and path↔embed equality rules as 1A/1B/2A/2B.
    S0’s outputs are therefore the root of 3A’s own authority chain, consistent with the rest of the layer.

* **Remains deterministic and RNG-free.**
  3A.S0 MUST NOT consume any Philox stream, generate any random variates, or depend on wall-clock time. Its behaviour is entirely deterministic given:

  * The resolved catalogue (dictionary/registry) for the target `manifest_fingerprint`, and
  * The fixed set of governed policy/prior configs in the current `parameter_hash`.
    This ensures that S0 can be re-run idempotently for the same `manifest_fingerprint` without changing any observable state.

Out of scope for 3A.S0:

* It does **not** perform any zone allocation, Dirichlet sampling, integerisation, or counting of outlets across zones.
* It does **not** read or reason about per-site coordinates or per-arrival routing; those are handled by 1B, 2A, and 2B respectively.
* It does **not** construct any new authority surfaces beyond the gate receipt and sealed-inputs inventory; all zone-mass and hash surfaces are introduced in later 3A states.

Within these boundaries, 3A.S0's purpose is to guarantee that any subsequent 3A state operates in a strictly governed, reproducible environment whose inputs and upstream dependencies are explicit, auditable, and fixed for the life of the run.

---

### Cross-Layer Inputs (Segment 3A)

**Upstream segments required:** 1A (validation bundle + `_passed.flag`; `outlet_catalogue` egress), 1B (validation bundle + `_passed.flag`), 2A (validation bundle + `_passed.flag`; `site_timezones` egress; optional `tz_timetable_cache` / `s4_legality_report`).

**External references/configs (sealed by S0 and listed in `sealed_inputs_3A`):**
* `zone_mixture_policy` (3A escalation policy)
* `country_zone_alphas` (3A country-zone prior pack)
* `zone_floor_policy` (3A floor/bump policy)
* `day_effect_policy_v1` (2B day-effect policy used in universe hash)
* `iso3166_canonical_2024` (ISO country list)
* `tz_world_2025a` (tz-world polygons)

**Gate expectations:** 1A/1B/2A PASS gates (`validation_bundle_*` + `_passed.flag`) MUST verify before any 1A/2A egress or sealed reference reads for this `manifest_fingerprint`.

### Contract Card (S0) - inputs/outputs/authorities

**Inputs (authoritative; see Section 2.2 for full list):**
* `validation_bundle_1A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_1A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_bundle_1B` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_1B` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_bundle_2A` - scope: FINGERPRINT_SCOPED; gate: required
* `validation_passed_flag_2A` - scope: FINGERPRINT_SCOPED; gate: required
* `outlet_catalogue` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `site_timezones` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional
* `tz_timetable_cache` - scope: FINGERPRINT_SCOPED; sealed_inputs: optional
* `s4_legality_report` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional
* `iso3166_canonical_2024` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required
* `tz_world_2025a` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required
* `zone_mixture_policy` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `country_zone_alphas` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `zone_floor_policy` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `day_effect_policy_v1` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required

**Authority / ordering:**
* S0 defines no data ordering; it only seals inputs and verifies upstream gate evidence.

**Outputs:**
* `s0_gate_receipt_3A` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `sealed_inputs_3A` - scope: FINGERPRINT_SCOPED; gate emitted: none

**Sealing / identity:**
* External inputs (upstream gates, egress, and sealed policies/priors) MUST appear in `sealed_inputs_3A` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing/invalid gate evidence or required sealed inputs -> abort; no outputs published.

## 2. Preconditions & upstream gates **(Binding)**

This section defines what **MUST already hold** before `3A.S0 — Gate & Sealed Inputs for Zone Allocation` can be considered to start, and which upstream gates it is responsible for re-verifying as part of its own execution.

### 2.1 Layer-1 global prerequisites

Before 3A.S0 is invoked for any `manifest_fingerprint`, the following **global Layer-1 conditions MUST hold**:

1. **Layer-wide schema packs are available and authoritative.**

   * `schemas.layer1.yaml` and `schemas.ingress.layer1.yaml` MUST be present in the catalogue and MUST be treated as the **sole shape authorities** for:

     * shared primitive types (`id64`, `iso2`, `iana_tzid`, `hex64`, `uint64`, etc.),
     * RNG envelopes and event families,
     * generic validation artefacts (e.g. S6 receipts, passed flags).
   * 3A.S0 MUST NOT attempt to redefine any of these types or envelopes.

2. **Layer-1 identity and partition law are already defined.**

   * The Layer-1 S0 design (outside this segment) MUST already have defined:

     * `parameter_hash` as the hash over the governed parameter set 𝓟, and
     * `manifest_fingerprint` as the hash over the resolved artefact set for a run, including `parameter_hash`.
   * 3A.S0 MUST be invoked with a `parameter_hash` and `manifest_fingerprint` pair that has already been resolved by that Layer-1 mechanism.
   * 3A.S0 MUST treat these as **inputs to verify**, not values to invent or mutate.

3. **Layer-1 catalogues are resolvable.**

   * The Layer-1 dataset dictionaries and artefact registries for segments **1A, 1B, 2A, 2B** MUST be present and schema-valid.
   * 3A.S0 MUST be able to resolve dataset IDs, artefact IDs and `schema_ref` references via these catalogues; it MUST NOT rely on ad-hoc or hard-coded paths.

If any of the above are not true, 3A.S0 MUST NOT proceed and MUST fail with a canonical “layer environment” error (see §9).

---

### 2.2 Upstream segment gates for the target fingerprint

For a given `manifest_fingerprint = F`, 3A.S0 assumes that 1A, 1B and 2A have already run (or been reused) for that fingerprint. As part of its execution, 3A.S0 is responsible for **re-verifying** the following upstream gates before it can declare its own gate surfaces valid:

1. **1A is gated and green for F.**

   * A `validation_bundle_1A` directory for `fingerprint=F` and a corresponding `_passed.flag` MUST exist in the catalogue.
   * The `_passed.flag` content MUST match the bundle index and bytes according to the Layer-1 HashGate rule.
   * Only when this check passes MAY 3A.S0 treat 1A egress (`outlet_catalogue`) and 1A validation surfaces as eligible to appear in 3A’s sealed input set.

2. **1B is gated and green for F.**

   * A `validation_bundle_1B` and `_passed.flag` for `fingerprint=F` MUST exist and satisfy the same HashGate rule.
   * 3A.S0 does not itself read `site_locations`, but it MUST ensure that 2A’s dependence on 1B is sound by verifying the 1B gate before trusting any 2A surfaces (see next bullet).

3. **2A is gated and green for F.**

   * A `validation_bundle_2A` and `_passed.flag` for `fingerprint=F` MUST exist and be HashGate-valid.
   * Only when this check passes MAY 3A.S0 treat 2A outputs (`site_timezones`, `tz_timetable_cache`, `s4_legality_report`, etc.) as admissible sealed inputs for 3A.

4. **2B is not an upstream dependency for 3A.S0.**

   * 3A.S0 MUST NOT require any 2B **runtime or plan** outputs as a precondition; 2B may not have run yet.
   * 3A.S0 MAY treat **2B policy artefacts** (e.g. `day_effect_policy_v1`) as governed configuration inputs, but these are parameter-level dependencies, not “gates” in the sense above.

These upstream gate checks are **part of 3A.S0’s work**; they are not assumed to be pre-validated by the orchestrator. If any of them fails, 3A.S0 MUST abort without writing or modifying any 3A artefacts.

---

### 2.3 Invocation-level preconditions for 3A.S0

For a specific run of 3A.S0, the orchestrating system MUST satisfy the following invocation-level preconditions:

1. **Target identity triple is fixed.**

   * The orchestrator MUST supply (or allow S0 to resolve) a triple:

     * `parameter_hash`,
     * `manifest_fingerprint`,
     * `seed` (for the overall Layer-1 run),
       consistent with the Layer-1 S0 definition.
   * 3A.S0 MUST treat `seed` as an immutable identifier for the logical run; S0 itself remains RNG-free and MUST NOT consume it, but downstream states will rely on this value for partitioning.

2. **Governed policy/prior set is closed.**

   * All 3A-relevant policy and prior artefacts intended to participate in 𝓟 for this run MUST already be present in the catalogue and included in the Layer-1 `parameter_hash` calculation. This includes, at minimum:

     * the **zone mixture policy** (e.g. `zone_mixture_policy.yml`),
     * the **country→zone α-prior pack** (e.g. `country_zone_alphas.yaml`),
     * the **zone floor/bump rules** (e.g. `zone_floor.yml`), and
     * any **day-effect policy** that 3A treats as a governed input (e.g. `day_effect_policy_v1`).
   * 3A.S0 MUST NOT silently add freshly-discovered policy artefacts into 𝓟; any change to this set MUST occur via a new `parameter_hash`.

3. **Catalogue consistency is assumed, but verified.**

   * The orchestrator MUST ensure that the dataset dictionary and artefact registry entries for the artefacts listed above exist and are internally consistent (IDs, paths, `schema_ref`).
   * 3A.S0 will re-validate this consistency for the artefacts it seals; if mismatches are detected (e.g. path on disk vs path in dictionary), S0 MUST fail rather than patch or override.

---

### 2.4 Out-of-scope assumptions

The following are considered **out of scope** for 3A.S0 and are assumed to be handled by Layer-1 infrastructure:

* Container image selection, dependency management, and filesystem layout.
* Low-level details of how the catalogue resolves IDs to concrete storage locations (object store vs filesystem).
* Scheduling, retries, and orchestration of multiple 3A.S0 runs for different fingerprints or seeds.

3A.S0 may rely on these services being available, but it MUST NOT encode any assumptions about them beyond what is already specified in Layer-1’s global S0 and the dataset dictionaries/artefact registries.

Within these constraints, 3A.S0’s job is to **confirm** that all required upstream gates are green for the target `manifest_fingerprint`, that the governed policy/prior set is closed under the current `parameter_hash`, and that it can safely publish 3A’s own gate and sealed-inputs surfaces as the starting point for the rest of Segment 3A.

---

## 3. Inputs & authority boundaries **(Binding)**

This section fixes **what 3A.S0 is allowed to look at**, how it must treat each input class, and where its responsibility stops. Anything not listed here is **out of bounds** for 3A.S0.

---

### 3.1 Catalogue-level inputs (shape & naming authority)

3A.S0 depends on the existing Layer-1 catalogue to tell it **what exists** and **what it is called**. It MUST treat the following as **authoritative for shape and identity only**:

1. **Layer-wide schema packs (shape authority)**

   * `schemas.layer1.yaml`
   * `schemas.ingress.layer1.yaml`
     These define primitive types, RNG envelopes, generic validation artefacts, and ingress dataset shapes. 3A.S0 MAY only use them to:
   * validate the shape of upstream validation bundles and policy/prior configs, and
   * resolve `$ref` anchors for any 3A-specific schemas it introduces.
     It MUST NOT redefine or shadow any type or envelope from these packs.

2. **Segment schema packs (shape authority for upstream segments)**

   * `schemas.1A.yaml`, `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.2B.yaml`.
     3A.S0 MAY use these packs **only** to:
   * confirm that upstream validation bundles are structurally valid, and
   * recognise dataset IDs and schema anchors referenced in dictionaries/registries.

3. **Dataset dictionaries (ID → path/partition/shape authority)**

   * `dataset_dictionary.layer1.1A.yaml`
   * `dataset_dictionary.layer1.1B.yaml`
   * `dataset_dictionary.layer1.2A.yaml`
   * `dataset_dictionary.layer1.2B.yaml`
   * `dataset_dictionary.layer1.3A.yaml` (for its own surfaces)
     For each dataset ID, the dictionary is the **only authority** on:
   * canonical ID,
   * path template and partition keys,
   * `schema_ref` and logical role (`final_in_layer`, `reference_data`, `validation`, etc.).
     3A.S0 MUST NOT hard-code paths or schema anchors for any dataset; it MUST resolve through these dictionaries.

4. **Artefact registries (manifest-scoped binding authority)**

   * `artefact_registry_1A.yaml`, `artefact_registry_1B.yaml`,
   * `artefact_registry_2A.yaml`, `artefact_registry_2B.yaml`,
   * `artefact_registry_3A.yaml`.
     For a given `manifest_fingerprint`, the relevant registry is the **only authority** on:
   * which artefacts exist in that manifest,
   * their concrete `path` (with tokens resolved),
   * their `type` (dataset, bundle, log, policy, etc.),
   * licence and role notes.
     3A.S0 MUST use the registries, not ad-hoc file discovery, to enumerate the artefacts it seals.

3A.S0 MUST treat this **catalogue layer** (schemas + dictionaries + registries) as strictly above 3A in the authority chain: it may validate consistency, but it MUST NOT override IDs, paths, or schema_refs from these inputs.

---

### 3.2 Upstream gate artefacts (segment-level authority)

3A.S0 directly consumes the following artefacts as **truth about upstream PASS state** for the target `manifest_fingerprint`:

1. **1A validation gate (required)**

   * `validation_bundle_1A` for `fingerprint={manifest_fingerprint}`
   * `_passed.flag` in the same directory
     3A.S0 MUST:
   * read `index.json` from the bundle,
   * re-compute its composite SHA-256, and
   * verify `_passed.flag` content against the HashGate rule.
     On success, 1A egress (`outlet_catalogue`) and validation artefacts MAY appear in 3A’s sealed input set.

2. **1B validation gate (required)**

   * `validation_bundle_1B` and `_passed.flag` for the same fingerprint.
     3A.S0 MUST perform the same HashGate verification.
     On success, 1B egress (`site_locations`) and 1B validation artefacts MAY appear in 3A’s sealed input set (even if 3A later chooses not to read them).

3. **2A validation gate (required)**

   * `validation_bundle_2A` and `_passed.flag` for the same fingerprint.
     3A.S0 MUST verify this bundle before treating any 2A outputs (`site_timezones`, `tz_timetable_cache`, `s4_legality_report`) as admissible sealed inputs.

4. **2B validation gate (not an input dependency)**

   * 3A.S0 MUST NOT depend on `validation_bundle_2B` or `_passed.flag`.
   * 2B may not have run yet; its status is explicitly **not** part of 3A.S0’s preconditions or inputs.

These upstream gates are **authoritative for “is this segment green for this fingerprint?”**. 3A.S0 MUST NOT reinterpret their internal semantics; it only checks their integrity and presence.

---

### 3.3 Data-plane artefacts to be sealed (but not interpreted in S0)

3A.S0 does **not** perform any data-plane computation, but it does need to **enumerate and seal** the artefacts that later 3A states are allowed to read.

For the target `manifest_fingerprint`, 3A.S0 MAY include the following dataset IDs in its sealed-input set, discovered via dictionaries and registries:

1. **1A egress and supporting surfaces**

   * `outlet_catalogue@seed={seed}/fingerprint={manifest_fingerprint}`
   * Any 1A validation summary tables that later 3A states rely on diagnostically.
     Authority: 1A is the **sole owner** of merchant/site identity and per-merchant per-country outlet counts; 3A.S0 MUST NOT attempt to recompute or modify these.

2. **2A egress and cache surfaces**

   * `site_timezones@seed={seed}/fingerprint={manifest_fingerprint}`
   * `tz_timetable_cache@fingerprint={manifest_fingerprint}`
   * `s4_legality_report@seed={seed}/fingerprint={manifest_fingerprint}` (if later used for diagnostics).
     Authority: 2A is the **sole owner** of per-site tzid assignments and tzdb compilation; 3A.S0 MUST NOT reinterpret geometry or tzdb.

3. **Reference data from ingress layer (structural)**

   * `iso3166_canonical_2024`
   * `tz_world_2025a`
   * Other Layer-1 ingress references that 3A may need structurally (e.g. for country→tzid maps).
     Authority: these are **reference tables** governed by `schemas.ingress.layer1.yaml`; 3A.S0 may seal them but not edit or resample them.

3A.S0 MUST treat these artefacts as **opaque** in S0: it may compute file-level digests and record catalogue metadata, but it MUST NOT read or interpret row-level contents. All data-plane semantics are deferred to later states.

---

### 3.4 3A policies and priors (parameter-level authority)

3A introduces its own governed configuration and prior artefacts. For the current `parameter_hash`, 3A.S0 MUST treat the following as **binding inputs**:

1. **Zone mixture policy**

   * A configuration artefact (e.g. `zone_mixture_policy.yml`) whose dataset ID and schema_ref are defined in `dataset_dictionary.layer1.3A.yaml`.
   * Authority: defines the decision rules for when a merchant×country pair is treated as monolithic vs escalated into multi-zone allocation.
   * 3A.S0 MUST:

     * verify it exists under the expected ID/path,
     * validate it against its JSON-Schema, and
     * include its digest in the sealed input inventory.

2. **Country→zone α-prior pack**

   * A parameter artefact (e.g. `country_zone_alphas.yaml`) defining Dirichlet concentrations per `(country_iso, tzid)`.
   * Authority: the **only source** of α-vectors for 3A’s Dirichlet draws; later states MUST NOT fabricate α values ad-hoc.
   * 3A.S0 MUST seal its presence and digest; it does not interpret α content.

3. **Zone floor/bump rules**

   * A policy artefact (e.g. `zone_floor.yml`) specifying per-tzid or per-country×tzid minima, bump rules and related constraints.
   * Authority: defines deterministic rules that later 3A states MUST apply when integerising zone counts.
   * 3A.S0 MUST seal it as part of the governed parameter set.

4. **Day-effect policy (from 2B governance)**

   * A policy artefact (e.g. `day_effect_policy_v1.json`) governed by 2B but treated as a **parameter input** for 3A’s notion of the “routing universe”.
   * Authority: 2B is the owner of this policy; 3A.S0 only seals a snapshot and may later include a digest in a “routing universe hash”.
   * 3A.S0 MUST NOT mutate or reinterpret this policy; it only acknowledges which version is in play.

These policy/prior artefacts are the **only parameter-level knobs** that 3A.S0 recognises. If additional policies are introduced in future, they MUST be added to the dataset dictionary, artefact registry, and 3A.S0’s sealed-inputs logic explicitly.

---

### 3.5 Explicit exclusions and authority boundaries

To keep 3A’s authority surface narrow and clear, 3A.S0 MUST NOT treat the following as inputs:

1. **2B plan or runtime datasets**

   * `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`, `s5_selection_log`, `s6_edge_log`, or any other 2B plan/log surface.
   * These belong strictly to 2B; 3A.S0 MUST NOT read or seal them, and later 3A states MUST NOT depend on them.

2. **Raw tzdb archives or system time-zone data**

   * 3A.S0 MUST NOT read the raw IANA tzdb archive or underlying OS tz data.
   * tzdb compilation is a 2A concern; 3A sees only the `tz_timetable_cache` manifest and, optionally, ingress `tz_world` as reference.

3. **Row-level merchant, site or arrival data**

   * No 3A.S0 logic may inspect individual rows of `outlet_catalogue`, `site_locations`, `site_timezones`, or any arrival/routing logs.
   * 3A.S0 operates purely on **catalogue metadata**, validation bundles, and policy/prior artefacts.

4. **Ad-hoc files or operator overrides**

   * Any artefact not registered in the Layer-1 dictionaries/registries for the current `parameter_hash` and `manifest_fingerprint` MUST be ignored by 3A.S0 and MUST NOT appear in the sealed input inventory.
   * Operators MAY NOT “sneak in” new inputs via unregistered files; doing so is out of spec.

Within these boundaries, 3A.S0’s job is to build a **closed, explicit set of inputs** for Segment 3A: upstream segment gates, reference surfaces, and 3A’s own policies/priors, all discovered through the catalogue and recorded in a sealed inventory that later states MUST treat as the only admissible input universe.

---

## 4. Outputs (artefacts) & identity **(Binding)**

3A.S0 produces exactly **two** persistent artefacts. Together they define the **gate** and **sealed input universe** for Segment 3A at a given `manifest_fingerprint`. S0 does **not** emit any zone-allocation data or RNG logs.

---

### 4.1 Overview of S0 outputs

For each `manifest_fingerprint = F`, 3A.S0 MUST produce at most one instance of:

1. **`s0_gate_receipt_3A`**

   * A small, fingerprint-scoped JSON artefact that records:

     * which upstream segment validation bundles and `_passed.flag`s were verified for F,
     * which schema packs, dictionaries, and registries were used, and
     * which 3A policy/prior artefacts were sealed into the parameter set for this run.
   * This is the **authoritative statement** that “3A is permitted to run for `F` and will only touch the sealed artefacts listed.”

2. **`sealed_inputs_3A`**

   * A fingerprint-scoped, row-oriented dataset (typically a table) that enumerates the exact artefacts 3A is allowed to read for `F`, including:

     * upstream segment outputs (1A, 1B, 2A) used by later 3A states,
     * ingress reference datasets required structurally (e.g. ISO, tz_world), and
     * all 3A policy/prior artefacts that participate in the current `parameter_hash`.
   * Each row describes one sealed artefact: its logical ID, resolved path, `schema_ref`, digest, role and owning segment.

No other persistent outputs are in scope for 3A.S0. In particular, S0:

* MUST NOT write any zone-level allocation datasets,
* MUST NOT write any RNG events,
* MUST NOT write any validation bundle or `_passed.flag` for 3A as a whole (that is the responsibility of later 3A states).

---

### 4.2 `s0_gate_receipt_3A` — gate descriptor (fingerprint-scoped)

**Identity & path**

* Dataset ID (logical): **`s0_gate_receipt_3A`** (exact ID defined in `dataset_dictionary.layer1.3A.yaml`).
* Scope: one artefact per `manifest_fingerprint`.
* Physical layout (contract-aligned pattern):

  * Path pattern:
    `data/layer1/3A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json`
  * Partitioning: **`[fingerprint]`** only.
* The embedded `manifest_fingerprint` field in the JSON payload MUST equal the `{manifest_fingerprint}` path token (path↔embed equality).

**Role**

` s0_gate_receipt_3A` is the **Segment-3A gate descriptor** for the given fingerprint. It MUST, at minimum:

* Record the set of upstream gates successfully verified:

  * 1A `validation_bundle_1A` + `_passed.flag`,
  * 1B `validation_bundle_1B` + `_passed.flag`,
  * 2A `validation_bundle_2A` + `_passed.flag`.
* Record the catalogue artefacts used in this verification:

  * schema pack versions,
  * dictionary and registry versions for 1A/1B/2A/2B and 3A.
* Record the 3A policy/prior artefacts sealed into this run:

  * IDs and versions for zone mixture policy, country→zone α-priors, zone floor/bump policy, and any day-effect policy treated as a parameter input.
* Record the timezone geometry/cache universe pinned for this fingerprint (tz-world release/digest, tz-index digest if present, `tz_timetable_cache` digest).
* Record deterministic catalogue pins — the Layer-1 engine commit, dataset dictionary and artefact registry bundle hashes, and per-pack entries in `catalogue_versions`.

**Consumers**

* **Required consumers:**

  * All later 3A states (S1–S7) MUST verify that a `s0_gate_receipt_3A` exists for their target `manifest_fingerprint` and MUST treat its absence as a hard precondition failure.
  * The 3A segment-level validator (later state) MUST include `s0_gate_receipt_3A` in its own bundle.
* **Optional consumers:**

  * Cross-segment validation harnesses and run-report tooling MAY read it to reconstruct “what was sealed” for 3A at fingerprint F.

No downstream consumer may treat the **presence** of `s0_gate_receipt_3A` alone as equivalent to a 3A PASS; the formal PASS surface for 3A is a validation bundle produced by a later state. S0’s gate receipt is a **pre-run attestation**, not a final success indicator.

---

### 4.3 `sealed_inputs_3A` — sealed input inventory (fingerprint-scoped)

**Identity & path**

* Dataset ID (logical): **`sealed_inputs_3A`** (schema defined in `dataset_dictionary.layer1.3A.yaml`).
* Scope: one dataset per `manifest_fingerprint`.
* Physical layout (conceptual pattern):

  * Path pattern:
    `data/layer1/3A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_3A.json`
    (filename and format are implementation details; the path **MUST** include `fingerprint={manifest_fingerprint}` as the only partition key).
  * Partitioning: **`[fingerprint]`** only.
* Each row MUST contain a `manifest_fingerprint` column whose value equals the path token.

**Logical content**

Each row in `sealed_inputs_3A` describes exactly one artefact (dataset, bundle, policy, log, reference) which 3A is allowed to read for this fingerprint. At minimum, rows MUST include:

* A logical identifier (e.g. dataset ID or artefact ID).
* The owning segment/layer (e.g. `1A`, `1B`, `2A`, `2B`, `3A`).
* The artefact type (e.g. `dataset`, `bundle`, `policy`, `reference`).
* The resolved catalogue path with tokens (e.g. `.../seed={seed}/fingerprint={manifest_fingerprint}/…` if applicable).
* The `schema_ref` anchor used to validate this artefact.
* A content digest (at least SHA-256 hex over the on-disk representation).
* A short role/usage tag (e.g. `upstream_gate`, `zone_prior`, `reference_geo`, `input_egress`).

3A.S0 MUST ensure that every artefact later read by 3A.S1–S7 is present in this inventory. Conversely, later 3A states MUST NOT read artefacts that are absent from this table.

**Consumers**

* **Required consumers:**

  * Later 3A states (S1–S7) MUST use `sealed_inputs_3A` as the authoritative list of admissible inputs; they MAY cross-check that any artefact they read appears in this table with matching digest.
* **Optional consumers:**

  * Cross-segment validators and audit tooling MAY use it to reconstruct the exact set of artefacts that influenced 3A’s behaviour for this fingerprint.

`sealed_inputs_3A` is **not** itself a gate flag; it is an inventory. It has no binary PASS/FAIL status; only the presence of a 3A validation bundle + `_passed.flag` (defined in a later state) can be used as a PASS signal for the segment.

---

### 4.4 Identity, uniqueness & immutability guarantees

For both outputs, 3A.S0 MUST uphold the following identity and lifecycle guarantees:

1. **Uniqueness per fingerprint.**

   * For any given `manifest_fingerprint = F`, there MUST be at most one `s0_gate_receipt_3A` and at most one `sealed_inputs_3A` dataset visible in the catalogue.
   * If S0 is re-run for the same `F` under identical `parameter_hash` and catalogue state, the resulting artefacts MUST be byte-for-byte identical; any deviation MUST be treated as a configuration drift.

2. **Fingerprint-only partitioning.**

   * Both artefacts MUST be partitioned only by `fingerprint={manifest_fingerprint}`. They MUST NOT be partitioned by `seed`, `parameter_hash` or `run_id`.
   * The embedded `manifest_fingerprint` column MUST match the partition token exactly; this is used by later validators to assert path↔embed consistency.

3. **Immutability post-PASS in later states.**

   * Once 3A’s segment-level validation bundle (emitted by a later state) marks fingerprint `F` as PASS, `s0_gate_receipt_3A` and `sealed_inputs_3A` for `F` MUST be treated as immutable.
   * Any attempt to overwrite or mutate them after that point is out of spec and SHOULD be rejected by infrastructure.

4. **No implicit identity by file order.**

   * Neither artefact may rely on file order for semantics. For `sealed_inputs_3A`, any ordering guarantees MUST be explicitly defined in its schema (e.g. sort keys) and enforced by writers/validators; readers MUST NOT assume implicit meaning from physical file ordering.

Within these constraints, `s0_gate_receipt_3A` and `sealed_inputs_3A` form the **identity root** for Segment 3A: they are the only artefacts S0 is responsible for producing, and every other 3A state MUST treat them as the starting point and authority for “what world 3A is allowed to see” at a given `manifest_fingerprint`.

---

## 5. Dataset shapes, schema anchors & catalogue links **(Binding)**

This section fixes **where** the 3A.S0 outputs live in the authority chain:

* which JSON-Schema anchors define their shape,
* how they are exposed through the Layer-1 dataset dictionary, and
* how they are recorded in the 3A artefact registry.

Everything below is **normative**; later implementation docs must not introduce additional “shadow” shapes or paths for these artefacts.

---

### 5.1 Segment schema pack for 3A

3A.S0 relies on a dedicated segment schema pack:

* **Schema pack ID:** `schemas.3A.yaml`
* **Role:** shape authority for all Segment-3A artefacts (S0–S7), under the Layer-1 schema packs.

`schemas.3A.yaml` MUST:

1. Import Layer-1 primitives and common definitions via `$ref: schemas.layer1.yaml#/$defs/...` rather than redefining them (e.g. `hex64`, `uint64`, `rfc3339_micros`, `id64`).

2. Define **exact anchors** for the S0 outputs:

   * `#/validation/s0_gate_receipt_3A`
   * `#/validation/sealed_inputs_3A`

3. Use only JSON-Schema 2020-12 (or the Layer-1 standard) and MUST NOT introduce non-standard keywords except those already accepted in Layer-1 packs (e.g. `x-notes`, `x-role`).

Segment 3A MUST NOT create any additional S0-related anchors outside `schemas.3A.yaml`.

---

### 5.2 Schema anchor: `#/validation/s0_gate_receipt_3A`

`schemas.3A.yaml#/validation/s0_gate_receipt_3A` defines the **shape** of the S0 gate descriptor as a single JSON object.

At minimum, the schema MUST enforce:

* **Top-level type:** `object`

* **Required properties:**

  * `version` — `string`, semver, e.g. `"1.0.0"`
  * `manifest_fingerprint` — `$ref: schemas.layer1.yaml#/$defs/hex64`
  * `parameter_hash` — `$ref: schemas.layer1.yaml#/$defs/hex64`
  * `seed` — `$ref: schemas.layer1.yaml#/$defs/uint64`
  * `verified_at_utc` — `$ref: schemas.layer1.yaml#/$defs/rfc3339_micros`
  * `upstream_gates` — `object` with required children:

    * `segment_1A`, `segment_1B`, `segment_2A`
      each child having at least:

      * `bundle_id` (string, dataset ID),
      * `bundle_path` (string),
      * `flag_path` (string),
      * `sha256_hex` (`hex64`),
      * `status` (enum: `"PASS"` only for S0; other values reserved for validators).
  * `catalogue_versions` — `object` summarising catalogue artefacts in use (mandatory keys: `schemas_layer1`, `schemas_ingress_layer1`, `dataset_dictionary_layer1_{1A,1B,2A,2B,3A}`, `artefact_registry_{1A,1B,2A,2B,3A}`), each value an object `{ version_tag: string, sha256_hex: hex64 }`.
  * `engine_commit` — `$ref: schemas.layer1.yaml#/$defs/git_sha256_raw32`.
  * `dictionary_digest` — `$ref: schemas.layer1.yaml#/$defs/hex64` (hash of the resolved dataset dictionary bundle; if multiple bundles are used, encode as a deterministic array of `{ id, sha256_hex }` and hash that array here).
  * `registry_digest` — `$ref: schemas.layer1.yaml#/$defs/hex64` (analogous hash over the artefact registries in play).
  * `tz_universe` — `object` capturing the timezone geometry/cache identity sealed at S0, with required keys:
    * `tz_world_release` — `string`, e.g. `"tz_world_2025a"`,
    * `tz_world_sha256` — `$ref: schemas.layer1.yaml#/$defs/hex64`,
    * `tz_index_digest` — `$ref: schemas.layer1.yaml#/$defs/hex64` (or `null` if 2A does not publish one; field still required),
    * `tz_timetable_cache_sha256` — `$ref: schemas.layer1.yaml#/$defs/hex64`.
  * `sealed_policy_set` — `array` of objects, each with:

    * `logical_id` (string, dataset/artefact ID),
    * `owner_segment` (enum: `"1A" | "1B" | "2A" | "2B" | "3A" | "ingress"`),
    * `role` (string; e.g. `"zone_mixture_policy"`, `"country_zone_alphas"`, `"zone_floor_policy"`, `"day_effect_policy"`),
    * `sha256_hex` (`hex64`),
    * `schema_ref` (string ref into `schemas.3A.yaml` or upstream packs).

* **Additional properties:**

  * MAY include future-compatible optional objects (e.g. `notes`, `operator_metadata`), but these MUST be marked as `additionalProperties: true` only at controlled, documented points.

The schema MUST set `additionalProperties: false` at the top level to prevent accidental shape drift.

**Determinism note:** Producers MUST populate `verified_at_utc` deterministically from already-fixed inputs (e.g. upstream bundle timestamps or a hash-derived pseudo-timestamp). Calling the system clock or any non-deterministic source is prohibited; repeated S0 runs for the same `(parameter_hash, manifest_fingerprint)` MUST yield identical `verified_at_utc` values.

---

### 5.3 Schema anchor: `#/validation/sealed_inputs_3A`

`schemas.3A.yaml#/validation/sealed_inputs_3A` defines the **row shape** for the `sealed_inputs_3A` dataset.

At minimum, each row MUST have:

* **Top-level type:** `object`

* **Required fields:**

  * `manifest_fingerprint` — `$ref: schemas.layer1.yaml#/$defs/hex64`
  * `owner_segment` — enum: `"1A" | "1B" | "2A" | "2B" | "3A" | "ingress"`
  * `artefact_kind` — enum: `"dataset" | "bundle" | "policy" | "reference" | "log"`
  * `logical_id` — `string` (dataset/artefact ID in the dictionary/registry)
  * `path` — `string` (resolved concrete path including tokens like `seed=`/`fingerprint=` if present)
  * `schema_ref` — `string` (`$ref` into a schema pack)
  * `sha256_hex` — `$ref: schemas.layer1.yaml#/$defs/hex64`
  * `role` — `string` (short tag; e.g. `"upstream_gate"`, `"zone_prior"`, `"input_egress"`, `"reference_geo"`)

* **Optional fields:**

  * `notes` — `string` (free-text operator/developer notes)
  * `license_class` — `string` (if propagated from registry)
  * `experiment_tag` — `string` (for A/B or shadow runs; MUST NOT affect `parameter_hash` without explicit design).

The schema MUST ensure:

* `manifest_fingerprint` is always present and tied to the current fingerprint.
* No free-form untyped payloads (e.g. `object` with `additionalProperties: true`) are allowed except where explicitly reserved (e.g. `notes`).

This anchor MUST be used as the `schema_ref` for `sealed_inputs_3A` in the dataset dictionary (see next section).

---

### 5.4 Catalogue bindings (dictionary + registry references)

The authoritative IDs, paths, partition keys, schema anchors, owner metadata, and dependency listings for `s0_gate_receipt_3A` and `sealed_inputs_3A` live in the Layer-1 catalogue:

* **Dataset dictionary** — `dataset_dictionary.layer1.3A.yaml` publishes the `datasets` entries for both outputs (IDs, `owner_subsegment`, fingerprint-scoped versions, paths, `partitioning`, `format`, `schema_ref`, writer ordering, lineage). Implementations MUST read these entries at runtime and MUST NOT hard-code path templates or schema references.
* **Artefact registry** — `artefact_registry_3A.yaml` registers the same outputs per `manifest_fingerprint`, including manifest keys, categories, resolved paths, schema anchors, explicit dependency lists, and digests. Registry entries are the binding truth for “what was actually written” at a given fingerprint.

This state document does **not** repeat those catalogue snippets to avoid double maintenance. Instead, treat the catalogue as the sole contract source for IDs/paths/partitions, and treat this section as a reminder that:

1. 3A.S0 MUST consult the dictionary/registry before emitting outputs (no literal paths).
2. S0’s writers MUST honour the catalogue definitions exactly; any drift (path, version, partition keys, schema refs, dependency lists) is a contract violation.
3. Keeping the JSON-Schema, dataset dictionary, and artefact registry in sync is part of S0’s remit—if any of the three disagree, S0 MUST fail rather than publish mismatched artefacts.

---

## 6. Deterministic algorithm (RNG-free) **(Binding)**

This section defines the **exact behaviour** of 3A.S0. The algorithm is **purely deterministic** and **MUST NOT** consume any Philox stream, generate random variates, or call the system clock.

All steps below are expressed in terms of:

* the **catalogue** (schema packs, dataset dictionaries, artefact registries),
* the **governed parameter set** (via `parameter_hash`), and
* the **resolved manifest** (via `manifest_fingerprint`).

Given those, 3A.S0 MUST be **bit-replayable**: re-running S0 for the same inputs MUST re-produce byte-identical outputs.

---

### 6.1 Phase overview

3A.S0 executes in four phases:

1. **Resolve identity & catalogue handles.**
   Confirm `parameter_hash` and `manifest_fingerprint` and load the Layer-1 catalogue artefacts it needs (schemas, dictionaries, registries).

2. **Verify upstream gates for `manifest_fingerprint`.**
   Re-check 1A, 1B and 2A validation bundles and `_passed.flag`s using the standard HashGate rule; abort on any failure.

3. **Enumerate & digest the sealed input set.**
   Using the dictionaries/registries and the governed parameter set, deterministically construct the full set of artefacts 3A is allowed to read, and compute a content digest for each.

4. **Materialise S0 outputs.**
   Write `sealed_inputs_3A` (row set) and `s0_gate_receipt_3A` (single JSON object) in a way that respects partition and path↔embed laws.

All ordering and tie-breaking MUST be explicit and stable; no step may rely on incidental filesystem order or non-deterministic iteration.

---

### 6.2 Resolve identity & catalogue handles

**Step 1 – Input identity triple.**

* S0 is invoked for a triple `(parameter_hash, manifest_fingerprint, seed)` that has already been fixed by Layer-1.
* S0 MUST:

  * Verify that `parameter_hash` and `manifest_fingerprint` conform to `hex64`.
  * Verify that `seed` conforms to `uint64`.
  * Record these values in memory; they will later be embedded into both S0 outputs.
  * Treat `seed` as **metadata only**: for a fixed `(parameter_hash, manifest_fingerprint)` and unchanged catalogue, S0’s behaviour and outputs MUST be identical regardless of the seed value. No branching or conditional sealing may depend on `seed`.

**Step 2 – Load catalogue artefacts.**

* S0 MUST load (via the catalogue, not by path literals):

  * `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`,
  * `schemas.1A.yaml`, `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.2B.yaml`, `schemas.3A.yaml`,
  * `dataset_dictionary.layer1.{1A,1B,2A,2B,3A}.yaml`,
  * `artefact_registry_{1A,1B,2A,2B,3A}.yaml`.

* For each, S0 MUST:

  * Validate that the file exists and is well-formed YAML/JSON.
  * Validate its shape against the appropriate schema (Layer-1’s schema for dictionaries/registries).

* Any failure (missing file, malformed YAML, schema violation) MUST result in an immediate error in the “Layer catalogue” class; no outputs may be written.

---

### 6.3 Verify upstream gates (HashGate) for 1A, 1B, 2A

For each upstream segment in `{1A, 1B, 2A}`, S0 MUST re-verify the corresponding validation bundle for `manifest_fingerprint`.

**Step 3 – Resolve upstream bundle & flag via dictionary/registry.**

For each segment `S ∈ {1A,1B,2A}`:

* Using the segment’s dataset dictionary and artefact registry, resolve:

  * the dataset ID and concrete path for `validation_bundle_S` at `fingerprint={manifest_fingerprint}`, and
  * the concrete path for `_passed.flag` in the same directory.

* S0 MUST NOT guess or hard-code paths; it MUST use the catalogue mappings.

**Step 4 – Compute bundle digest and compare flag.**

For each segment `S`:

1. Read `validation_bundle_S/index.json` and validate it against the appropriate index schema (`schemas.layer1.yaml` or segment-specific anchor).
2. From `index.json`:

   * Interpret each entry’s `path` as a relative path under the bundle root.
   * Sort entries by `path` in **ASCII lexicographic** order.
3. For each entry in sorted order:

   * Read the file’s raw bytes exactly as stored and compute its SHA-256 digest.
   * Assert equality with the `sha256_hex` recorded in `index.json`.
4. Concatenate the raw bytes of all listed files in sorted order and compute a **composite SHA-256** digest `D_S`.
5. Read `_passed.flag` and verify that it matches the canonical format
   `sha256_hex = <64-lowercase-hex>`
   and that the hex value equals `D_S`.

If **any** of these checks fail for a segment `S`, 3A.S0 MUST:

* Fail with an “upstream gate failed” error indicating which segment and why, and
* NOT produce or modify any 3A outputs.

On success, S0 records, per segment:

* `bundle_path`, `flag_path`, and `sha256_hex = D_S`, to embed later into `s0_gate_receipt_3A`.

---

### 6.4 Enumerate governed policies & priors for 3A

**Step 5 – Resolve policy/prior artefacts by ID.**

Using `dataset_dictionary.layer1.3A.yaml` and `artefact_registry_3A.yaml`, S0 MUST resolve the concrete artefacts corresponding to:

* the 3A **zone mixture policy** (e.g. dataset ID `zone_mixture_policy_3A`),
* the 3A **country→zone α-priors** (e.g. `country_zone_alphas_3A`),
* the 3A **zone floor/bump policy** (e.g. `zone_floor_policy_3A`), and
* the 2B **day-effect policy** that 3A recognises as part of its parameter set (e.g. `day_effect_policy_v1`).

For each artefact:

* S0 MUST ensure:

  * the ID exists in the dictionary and registry,
  * the registry entry for the current `manifest_fingerprint` (if any) resolves to a concrete `path`, and
  * a `schema_ref` is specified and points to a valid anchor in `schemas.3A.yaml` or an upstream pack.

**Step 6 – Compute per-artefact digests.**

For each resolved policy/prior artefact:

* Read its entire on-disk content as a byte sequence (e.g. YAML, JSON).
* Compute the SHA-256 digest and represent it as `sha256_hex` (lowercase hex string).
* Validate the content against its `schema_ref` anchor; any schema violation MUST be treated as a hard error.

S0 accumulates a set `P` of sealed policy descriptors:

* each with `logical_id`, `owner_segment`, `role`, `schema_ref`, and `sha256_hex`.

This `P` becomes the `sealed_policy_set` embedded in `s0_gate_receipt_3A`.

---

### 6.5 Derive the sealed input set (deterministic enumeration)

**Step 7 – Determine which artefacts belong in `sealed_inputs_3A`.**

The sealed input set `𝕊` is the union of:

1. **Upstream gate artefacts** (for documentation and diagnostics):

   * `validation_bundle_1A` + `_passed.flag`,
   * `validation_bundle_1B` + `_passed.flag`,
   * `validation_bundle_2A` + `_passed.flag`.

2. **Upstream data-plane surfaces used by 3A** (even if not used by S0 itself):

   * `outlet_catalogue@seed={seed}/fingerprint={manifest_fingerprint}` (1A egress),
   * `site_timezones@seed={seed}/fingerprint={manifest_fingerprint}` (2A egress),
    * `tz_timetable_cache@fingerprint={manifest_fingerprint}` (2A cache),
    * ingress references required structurally by later 3A states (e.g. `iso3166_canonical_2024`, `tz_world_2025a`).

3. **3A policies and priors**

   * All artefacts sealed in `P` (zone mixture policy, α-priors, zone floor, day-effect policy).

The normative set `𝕊` is defined by this specification; any extension (e.g. sealing additional diagnostic artefacts) MUST follow change-control rules (§12) and be reflected here.

**Step 8 – Resolve each artefact in `𝕊` through the catalogue.**

For each element `x ∈ 𝕊`:

* Use the relevant dataset dictionary and artefact registry to resolve:

  * `owner_segment` (e.g. `1A`, `2A`, `3A`, `ingress`),
  * artefact `type` (`dataset`, `bundle`, `policy`, `reference`, `log`),
  * logical ID (`logical_id`),
  * concrete `path` (with tokens resolved using `seed` and/or `manifest_fingerprint` where required),
  * `schema_ref` (for datasets and JSON/YAML artefacts).

If any artefact in `𝕊` is missing or cannot be resolved uniquely, S0 MUST fail with a “sealed input resolution” error.

**Step 9 – Compute SHA-256 digest per sealed input.**

For each resolved artefact in `𝕊`:

* Read its raw content bytes exactly as stored (for directories like validation bundles, S0 treats the **bundle root directory** as a single logical artefact and may:

  * either digest only the `index.json`, or
  * digest a canonical representation as defined in Layer-1; whichever is explicitly specified in the 3A contracts).
* Compute SHA-256 over that byte sequence; record as `sha256_hex`.

**Step 10 – Construct a row set with deterministic ordering.**

For each artefact in `𝕊`, construct a row with:

* `manifest_fingerprint` = current `F`,
* `owner_segment`,
* `artefact_kind` (as per §3.3/§5.3),
* `logical_id`,
* `path`,
* `schema_ref`,
* `sha256_hex`,
* `role` (short tag, e.g. `"upstream_gate"`, `"input_egress"`, `"reference_geo"`, `"zone_prior"`).

Before writing `sealed_inputs_3A`, S0 MUST sort the rows by the deterministic key:

1. `owner_segment` (lexicographic),
2. `artefact_kind` (lexicographic),
3. `logical_id` (lexicographic),
4. `path` (lexicographic).

Physical writer-sort MUST follow this key; readers MUST NOT infer additional meaning from the order, but determinism guarantees byte-for-byte equality on replay.

---

### 6.6 Materialise `sealed_inputs_3A` (fingerprint-only)

**Step 11 – Write `sealed_inputs_3A`.**

* Use the `dataset_dictionary.layer1.3A.yaml` entry for `sealed_inputs_3A` to determine:

  * the path pattern,
  * partition keys (`fingerprint`),
  * file format (`parquet`),
  * `schema_ref` (`schemas.3A.yaml#/validation/sealed_inputs_3A`).

S0 MUST:

1. Expand `fingerprint={manifest_fingerprint}` in the path.
2. Assert that any existing dataset at that path either:

   * does not exist, or
   * is bit-identical to what S0 is about to write (same rows, same sort, same serialisation). If not, S0 MUST fail with an “immutability violation” error.
3. Validate all rows against `schemas.3A.yaml#/validation/sealed_inputs_3A`.
4. Write the dataset in the specified format with the specified sort order and partitioning.

No RNG or wall-clock calls are permitted in this phase.

---

### 6.7 Materialise `s0_gate_receipt_3A` (fingerprint-only)

**Step 12 – Derive `verified_at_utc` deterministically.**

* S0 MUST obtain `verified_at_utc` from a **deterministic upstream source**, such as a Layer-1 run-environment record (e.g. a `run_environ` or `s6_receipt` artefact) that is itself part of the manifest and does not change between re-runs.
* S0 MUST NOT call the system clock or any equivalent “now()” API.
* If no deterministic upstream timestamp is available by design, `verified_at_utc` MUST be a fixed, deterministically derived value (e.g. a hash-derived pseudo-timestamp) defined in the 3A contracts; in all cases, S0 MUST ensure replay yields the same value.

**Step 13 – Assemble the gate receipt object.**

S0 MUST construct a single JSON object conforming to `schemas.3A.yaml#/validation/s0_gate_receipt_3A` with at least:

* `version` (contract version of S0),
* `manifest_fingerprint`, `parameter_hash`, `seed`,
* `verified_at_utc` (as above),
* `upstream_gates`:

  * For each of 1A, 1B, 2A:

    * `bundle_id`, `bundle_path`, `flag_path`, `sha256_hex` from Step 4,
    * `status: "PASS"`.
* `catalogue_versions`:

  * Version tags for all schema packs, dictionaries and registries loaded in Step 2.
* `sealed_policy_set`:

  * The list `P` from Step 6 (policy/prior artefacts), including their `logical_id`, `owner_segment`, `role`, `schema_ref`, and `sha256_hex`.

**Step 14 – Write `s0_gate_receipt_3A`.**

* Use the dictionary entry for `s0_gate_receipt_3A` to determine path, partition (`fingerprint`) and schema_ref.
* Expand `fingerprint={manifest_fingerprint}` in the path.
* Assert that any existing file at that path either:

  * does not exist, or
  * is byte-identical to the JSON S0 is about to write. Non-identical existing content MUST cause an “immutability violation” error.
* Validate the object against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`.
* Serialise deterministically (e.g. canonical JSON: sorted keys, fixed whitespace rules) to guarantee replay produces identical bytes.

---

### 6.8 Idempotence and side-effect discipline

Throughout the algorithm:

* 3A.S0 MUST NOT:

  * consume or reserve any RNG streams,
  * modify or delete any upstream artefacts,
  * touch any 3A artefacts other than `sealed_inputs_3A` and `s0_gate_receipt_3A`.

* On any failure in Steps 2–14:

  * S0 MUST abort without partially written artefacts (atomic write discipline).
  * No truncated or partially updated versions of S0 outputs may remain visible; infrastructure MUST either not create them or roll them back on failure.

* On replay for the same `(parameter_hash, manifest_fingerprint, seed)` and unchanged catalogue:

  * `sealed_inputs_3A` and `s0_gate_receipt_3A` MUST be identical at the byte level.
  * Any divergence MUST be treated as a configuration or environment drift and surfaced as an error rather than silently updating the artefacts.

Under this algorithm, 3A.S0’s behaviour is fully determined by the Layer-1 catalogue state, the governed parameter set, and the resolved manifest fingerprint, and provides a clean, RNG-free foundation for all subsequent 3A states.

---

## 7. Identity, partitions, ordering & merge discipline **(Binding)**

This section pins down **how 3A.S0’s artefacts are identified**, how they are **partitioned**, what (if any) meaning is attached to **ordering**, and exactly what is and isn’t allowed in terms of **merging / appending** over time.

The goal is that any consumer can reason **purely from keys, partitions and paths** without relying on file layout or accidental conventions.

---

### 7.1 Identity vocabulary for 3A.S0

3A.S0 lives inside the existing Layer-1 identity scheme. It does **not** introduce new global identity primitives; it binds to:

* `parameter_hash` — layer-wide parameter set hash (𝓟), defined by Layer-1;
* `manifest_fingerprint` — layer-wide manifest hash, defined by Layer-1;
* `seed` — layer-wide run seed (uint64), defined by Layer-1;
* `run_id` — Layer-1 logging partition key (if present elsewhere), but **not** used by 3A.S0 outputs.

For 3A.S0:

* **Segment identity** is `(layer="layer1", subsegment="3A")`.
* **State identity** is additionally `state="S0"` but this is carried only in metadata (`lineage.produced_by: ["3A.S0"]`, registry `manifest_key`, etc.), not as a partition.

The two S0 outputs have the following **primary keys** at the logical level:

* `s0_gate_receipt_3A`:

  * Logical PK: `manifest_fingerprint` (one row; one object)
  * There MUST be at most one gate receipt per fingerprint.

* `sealed_inputs_3A`:

  * Logical PK (per row): `(manifest_fingerprint, owner_segment, artefact_kind, logical_id, path)`
  * `(manifest_fingerprint, path)` MUST be unique; two rows MUST NOT describe the same concrete path with conflicting metadata.

Other columns (e.g. `role`, `schema_ref`, `sha256_hex`) are attributes, not identifiers.

---

### 7.2 Partitioning law for 3A.S0 outputs

Both S0 artefacts are **fingerprint-scoped**. They MUST obey the same partitioning law as upstream gate and sealed-inputs datasets in 2A/2B:

1. **`s0_gate_receipt_3A`**

   * Partition key set: `["fingerprint"]` only.
   * Physical layout MUST follow the dictionary entry (conceptually):
     `data/layer1/3A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json`
   * No `seed`, `parameter_hash` or `run_id` partitions are allowed for this dataset.

2. **`sealed_inputs_3A`**

   * Partition key set: `["fingerprint"]` only.
   * Physical layout MUST follow the dictionary entry (conceptually):
     `data/layer1/3A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_3A.json`
   * All rows in a given partition MUST have the same `manifest_fingerprint` value.

**Partitioning invariants:**

* For any `manifest_fingerprint = F`, there MUST be exactly one partition `fingerprint=F` per dataset.
* No dataset writer may create additional partitions (e.g. `fingerprint=F, seed=…`) or change the partition key set; doing so violates the contract.

---

### 7.3 Path↔embed equality & token discipline

3A.S0 MUST enforce strict **path↔embed equality** for its own artefacts and obey existing token laws for any paths it records.

1. **Own outputs**

   * For `s0_gate_receipt_3A`:

     * The JSON object MUST contain a field `manifest_fingerprint` whose value equals the `{manifest_fingerprint}` token in its path.
   * For `sealed_inputs_3A`:

     * Every row MUST have `manifest_fingerprint = F` equal to the `fingerprint=F` partition token.

   Any mismatch between embedded `manifest_fingerprint` and the partition token MUST be treated as a validation error by both 3A.S0 and downstream validators.

2. **Paths recorded in `sealed_inputs_3A`**

   * For artefacts that are themselves partitioned by `{seed}` and `{fingerprint}` (e.g. `outlet_catalogue`, `site_timezones`):

     * The `path` column MUST include **all** path tokens as resolved in the dictionary/registry (e.g. `.../seed=123/fingerprint=abcd.../...`).
     * The `sealed_inputs_3A` writer MUST NOT drop or re-order these tokens; it simply copies them from the catalogue entry or registry instance.

   * For fingerprint-only artefacts (e.g. `tz_timetable_cache`, validation bundles, S0 outputs):

     * The `path` column MUST include `fingerprint={manifest_fingerprint}` as the only partition token.

`sealed_inputs_3A` is not allowed to invent new token schemes; it must mirror exactly what the dictionaries/registries define.

---

### 7.4 Ordering semantics

Only one of the S0 outputs is row-oriented:

* `s0_gate_receipt_3A`: a single JSON object — ordering is irrelevant.
* `sealed_inputs_3A`: table with many rows — ordering is **diagnostic**, not authoritative.

For `sealed_inputs_3A`:

* **Writer-sort key** (normative):

  1. `owner_segment` (lexicographic)
  2. `artefact_kind` (lexicographic)
  3. `logical_id` (lexicographic)
  4. `path` (lexicographic)

  Writers MUST produce files sorted by this key inside each `fingerprint` partition.

* **Semantic meaning:**

  * Consumers MUST NOT attach any **semantic meaning** to the relative order of rows beyond reproducibility and human readability.
  * All **identity and authority** come from `(manifest_fingerprint, owner_segment, artefact_kind, logical_id, path)`, not position.

This matches the Layer-1 pattern: ordering is stable for replay and debugging, but **never** used as an implicit index.

---

### 7.5 Merge & append discipline (single-writer per fingerprint)

3A.S0 acts as a **snapshot writer** for the sealed input universe. Merge behaviour is therefore tightly constrained:

1. **No multi-writer append for the same fingerprint.**

   * For `s0_gate_receipt_3A`:

     * There MUST NOT be multiple JSON files for the same partition `fingerprint=F`.
     * The file MUST be written atomically; partial writes are disallowed.

   * For `sealed_inputs_3A`:

     * There MUST NOT be multiple independent row groups or files that together represent different “epochs” of the sealed set for the same `fingerprint`.
     * The dataset MUST be treated as a single **snapshot** for `F`.
     * Overwriting an existing snapshot with different content is out of spec once any later 3A state has run.

2. **Idempotent re-writes only.**

   * If 3A.S0 is re-run for the same `(parameter_hash, manifest_fingerprint, seed)` while the catalogue and governed parameter set are unchanged:

     * Any existing `s0_gate_receipt_3A` and `sealed_inputs_3A` MUST be **byte-identical** to what S0 would produce.
     * Implementation MAY choose to:

       * detect equality and skip writing, or
       * physically re-write the same bytes; in either case the observable content must be unchanged.
   * If existing content differs, S0 MUST fail with an **immutability violation** rather than silently merging or overwriting.

3. **No row-level merges.**

   * S0 MUST always construct `sealed_inputs_3A` as a full row set; it MAY NOT append or delete individual rows in-place.
   * Any change to the sealed input universe for a fingerprint (e.g. adding a new policy artefact) MUST occur via:

     * a change in the governed parameter set → new `parameter_hash` / new `manifest_fingerprint`, and
     * a fresh S0 run producing a new, distinct partition.

---

### 7.6 Cross-fingerprint usage & analytics

3A.S0 makes **no guarantees** about relationships between different `manifest_fingerprint` values. Cross-fingerprint behaviour is defined by Layer-1, but for S0:

* Each `(fingerprint=F)` partition is a **complete, closed world** of sealed inputs for that manifest.
* Consumers MUST NOT attempt to “union” sealed inputs across fingerprints and treat the result as meaningful for any single run.
* Cross-fingerprint unions are allowed only for **analytics** (e.g. “how many manifests used this policy?”) and MUST NOT be used to infer runtime behaviour for a specific manifest.

---

### 7.7 Interaction with later 3A states

Finally, the **merge discipline between states**:

* 3A.S1–S7 MUST treat `s0_gate_receipt_3A(F)` and `sealed_inputs_3A(F)` as **read-only**, **complete** descriptions of what they may touch for that fingerprint.
* No later state is allowed to:

  * patch `sealed_inputs_3A` to “add” an artefact it forgot to seal,
  * modify `s0_gate_receipt_3A` to change recorded digests, catalogue versions or gate status.

If later states discover that `sealed_inputs_3A` is incomplete (an input they need is missing), the correct remedy is:

1. treat the current run as invalid, and
2. change the design/contracts (or parameter set) so that 3A.S0 is updated and re-run, producing a new sealed snapshot under a new `manifest_fingerprint` if necessary.

Under these rules, 3A.S0’s outputs have clear identity, well-defined partitioning and ordering semantics, and a strictly single-writer, snapshot-only merge discipline that aligns with the rest of Layer-1.

---

## 8. Acceptance criteria & gating obligations **(Binding)**

This section defines **when 3A.S0 is considered successful (“S0 PASS”)** for a given `manifest_fingerprint`, and what **hard obligations** that status imposes on:

* later 3A states (S1–S7), and
* any cross-segment component that wants to rely on 3A surfaces.

S0 itself **does not** signal “Segment 3A PASS” – that is the role of a later validation state – but it **is** the gate that decides whether 3A is allowed to run at all for a given manifest.

---

### 8.1 Local acceptance criteria for 3A.S0

For a given `(parameter_hash, manifest_fingerprint, seed)`, 3A.S0 is considered **PASS** if and only if **all** of the following hold:

1. **Upstream gates re-verified successfully.**

   For segments 1A, 1B and 2A:

   * A `validation_bundle_S` and `_passed.flag` exist at `fingerprint={manifest_fingerprint}`.
   * The bundle’s `index.json` is schema-valid and self-consistent (every listed file exists; per-file `sha256_hex` matches the file’s bytes).
   * The composite SHA-256 of all bundle files (in ASCII-lex path order) matches the `_passed.flag` contents.
   * S0 records `status="PASS"` for that segment in `s0_gate_receipt_3A.upstream_gates.segment_S`.

   If **any** upstream segment gate fails, 3A.S0 MUST be treated as **FAIL** and MUST NOT write or modify any S0 outputs.

2. **Catalogue artefacts resolved and consistent.**

   * All required schema packs (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.{1A,1B,2A,2B,3A}.yaml`), dataset dictionaries, and artefact registries for segments `{1A,1B,2A,2B,3A}` are present and schema-valid.
   * For every artefact referenced in S0 outputs:

     * There is a unique dictionary entry (for datasets) and/or registry entry (for manifest-specific artefacts).
     * The path, `schema_ref` and role recorded by S0 match those catalogue entries exactly.

   Any unresolved or inconsistent catalogue entry for an artefact in the normative sealed set MUST cause S0 to fail.

3. **Governed policy/prior set sealed and valid.**

   * All required 3A policy/prior artefacts (zone mixture policy, country→zone α-priors, zone floor/bump rules) and the relevant day-effect policy are:

     * present in the catalogue for the current `parameter_hash`,
     * schema-valid according to their `schema_ref`, and
     * digested to a deterministic `sha256_hex`.
   * These artefacts appear in `s0_gate_receipt_3A.sealed_policy_set` and in `sealed_inputs_3A` with matching `sha256_hex`.

   Missing, malformed or schema-invalid policies/priors MUST cause an S0 failure.

4. **Sealed input universe `sealed_inputs_3A` is complete and well-formed.**

   * The sealed set includes all artefacts mandated by the design (see §6.5), at least:

     * upstream gates (1A/1B/2A bundles + flags),
     * upstream data-plane inputs required later (1A `outlet_catalogue`, 2A `site_timezones`, `tz_timetable_cache`, ingress reference tables),
     * timezone-geometry artefacts (ingress `tz_world` release and 2A `tz_timetable_cache`) whose digests match the `tz_universe` section of `s0_gate_receipt_3A`,
     * all sealed policies/priors from the current parameter set.
   * Each row in `sealed_inputs_3A`:

     * conforms to `schemas.3A.yaml#/validation/sealed_inputs_3A`,
     * has `manifest_fingerprint` equal to the partition token,
     * has a `path` and `schema_ref` consistent with the catalogue,
     * has a `sha256_hex` equal to the digest of the on-disk artefact.
   * `(manifest_fingerprint, path)` is unique; no two rows describe the same physical artefact with conflicting metadata.

   If any mandated artefact is missing, duplicated or malformed, S0 MUST fail.

5. **Gate receipt `s0_gate_receipt_3A` is self-consistent and catalogue-consistent.**

   * The JSON object conforms to `schemas.3A.yaml#/validation/s0_gate_receipt_3A`.
   * Its `manifest_fingerprint`, `parameter_hash` and `seed` fields exactly match the invocation triple.
   * Its `upstream_gates` entries align with the actual verified bundles (same bundle paths, flag paths, digests).
   * Its `catalogue_versions` reflect the exact versions and digests of schema/dictionary/registry packs loaded in this run.
   * Its `sealed_policy_set` entries all correspond 1:1 to rows in `sealed_inputs_3A` with matching IDs and `sha256_hex`.
   * Its `tz_universe` section matches the sealed rows for `tz_world` and `tz_timetable_cache`.
   * Its `engine_commit`, `dictionary_digest`, and `registry_digest` fields are populated and correspond to the actual commit and catalogue bundles used for S0.

   Any mismatch between gate receipt and actual sealed inputs MUST cause S0 to fail.

6. **Idempotence and immutability preserved.**

   * If S0 outputs already exist for this `(manifest_fingerprint)`:

     * The newly computed `s0_gate_receipt_3A` and `sealed_inputs_3A` are **byte-identical** to the existing ones.
   * S0 MUST NOT overwrite or partially modify existing artefacts with divergent content.

   Detection of non-identical existing outputs MUST cause an immutability error rather than silent overwrite.

Only when **all** conditions 1–6 are satisfied may the orchestrator mark 3A.S0 as **PASS** for that `manifest_fingerprint`.

---

### 8.2 Preconditions imposed on later 3A states (S1–S7)

Once 3A.S0 is PASS for a given `manifest_fingerprint`, it imposes the following **mandatory preconditions** on S1–S7:

1. **Gate receipt presence.**

   * Before reading any upstream artefact (1A/1B/2A/ingress) or any 3A policy/prior, each later state MUST:

     * verify that a `s0_gate_receipt_3A` exists for the target `manifest_fingerprint`, and
     * validate it against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`.
   * Absence or schema failure of `s0_gate_receipt_3A` MUST be treated as a hard precondition failure for that state.

2. **Sealed input membership.**

   * Later states MUST treat `sealed_inputs_3A` as the **sole authority** on what they are allowed to read. For any artefact they wish to access, they MUST verify that:

     * there exists at least one row in `sealed_inputs_3A` with matching `path` and `logical_id`, and
     * the recorded `sha256_hex` matches a freshly computed digest of the artefact.
   * If an artefact is not present in `sealed_inputs_3A`, later states MUST NOT read or depend on it.

3. **No re-opening upstream gates.**

   * S1–S7 MUST NOT re-implement their own variant of the 1A/1B/2A HashGate check.
   * They may **rely on** the `upstream_gates` section in `s0_gate_receipt_3A` as binding evidence that upstream gates have been verified for this fingerprint.

4. **Fixed parameter set.**

   * Later states MUST treat the set of policies/priors recorded in `sealed_policy_set` and `sealed_inputs_3A` as **closed** for this fingerprint.
   * They MUST NOT infer or load additional 3A policies/priors by scanning the filesystem or environment; any policy not sealed by S0 is out-of-bounds.

---

### 8.3 Obligations on cross-segment consumers of 3A

The formal “3A PASS → No read” contract will be defined by the segment-level validation state (e.g. 3A.S7), which will publish its own validation bundle and `_passed.flag`. However, S0 already imposes two obligations on any consumer that wants to **trust 3A surfaces**:

1. **Do not treat S0 PASS as segment PASS.**

   * Consumers MUST NOT interpret the mere existence or validity of `s0_gate_receipt_3A` as “3A is safe to read”.
   * The segment-level PASS gate for 3A is a dedicated validation bundle + `_passed.flag` (defined in a later state).
   * S0 is a **pre-run gate**, not a final verdict.

2. **For audit-level trust, S0 surfaces MUST be part of the 3A PASS bundle.**

   * The 3A validation bundle (later state) MUST include:

     * the canonical `s0_gate_receipt_3A` object, and
     * the canonical `sealed_inputs_3A` dataset (or, at minimum, its digest)
       for the same `manifest_fingerprint`.
   * External auditors or replay harnesses MAY rely on these artefacts to reconstruct the sealed world in which 3A ran.

---

### 8.4 Error handling and retry semantics

From a design perspective:

* Failures of type **“upstream gate failed”**, **“catalogue malformed”**, or **“policy/prior invalid”** are **non-retryable** until the underlying upstream segment or configuration is corrected and, if necessary, a new `parameter_hash` / `manifest_fingerprint` is created.
* Failures of type **“transient I/O”** (e.g. temporary storage unavailability) are **retryable** in infrastructure, but every retry MUST still satisfy all criteria in §8.1 before outputs are considered valid.
* Failures of type **“immutability violation”** indicate a deeper problem (e.g. conflicting writers or environment drift); retries MUST NOT silently overwrite existing artefacts and SHOULD be blocked until an operator has explicitly resolved the conflict.

These classifications are informative for orchestration, but the binding requirement is: **no partial, inconsistent or self-contradictory S0 outputs may be published**.

---

### 8.5 Summary: S0 as the 3A “permission to start”

In summary, for a given `manifest_fingerprint`:

* **3A.S0 PASS** means:

  * “Upstream segments 1A, 1B and 2A are green for this manifest,” and
  * “This is the exact, closed set of artefacts 3A is allowed to see, with fixed digests and catalogue bindings.”

* **3A.S0 FAIL** means:

  * 3A MUST NOT proceed; any attempt by S1–S7 to run for this fingerprint is out of spec.

All later 3A work (Dirichlet zone allocation, integerisation, routing universe hashing, and the eventual segment-level PASS gate) is **conditional** on S0 having met the acceptance criteria in §8.1 and on all downstream states honouring the gating obligations in §8.2.

---

## 9. Failure modes & canonical error codes **(Binding)**

This section defines the **only allowed failure classes** for 3A.S0 and assigns each a **canonical error code**.

Any implementation MUST:

* classify every non-success outcome into *exactly one* of these codes, and
* surface that code (and any structured fields it requires) into the run-report / logs in a machine-readable way.

All codes are **namespaced** to avoid collisions with other segments and states.

---

### 9.1 Error taxonomy overview

3A.S0 can fail only for the following reasons:

1. **Upstream gates invalid or missing**
2. **Catalogue / schema layer malformed or inconsistent**
3. **Sealed policy/prior set invalid or incomplete**
4. **Sealed input resolution or digest mismatch**
5. **Inconsistent or invalid S0 outputs** (schema or self-consistency problems)
6. **Immutability / idempotence violations**
7. **Infrastructure / I/O-level issues**

Each category below specifies:

* a **canonical code**,
* when it MUST be raised, and
* whether it is **retryable** (from an orchestrator point of view) without changing inputs.

---

### 9.2 Upstream gate failures

#### `E3A_S0_001_UPSTREAM_GATE_FAILED`

**Condition**

Raised when **any** of the required upstream gates (1A, 1B, 2A) cannot be verified for the target `manifest_fingerprint`, including:

* `validation_bundle_S` missing,
* `_passed.flag` missing,
* `index.json` malformed or schema-invalid,
* per-file SHA-256 mismatch vs `index.json`,
* composite bundle SHA-256 not equal to `_passed.flag.sha256_hex`.

**Semantics**

* This error class MUST include a structured field:

  * `upstream_segment ∈ {"1A","1B","2A"}`
* S0 MUST NOT write or modify any outputs when this error is raised.

**Retryability**

* **Non-retryable** without upstream intervention.

  * Retrying S0 without fixing the upstream bundle/flag or regenerating the manifest will produce the same failure.
  * Operators MUST repair or re-run the upstream segment, and possibly produce a new `manifest_fingerprint`, before retrying.

---

### 9.3 Catalogue and schema failures

#### `E3A_S0_002_CATALOGUE_MALFORMED`

**Condition**

Raised when any of the following occurs while loading schema packs, dataset dictionaries, or artefact registries:

* A required catalogue artefact (`schemas.*.yaml`, `dataset_dictionary.layer1.*.yaml`, `artefact_registry_*`) is missing.
* A catalogue artefact is present but not well-formed YAML/JSON.
* A catalogue artefact fails validation against its governing schema.

**Semantics**

* MUST include a structured field:

  * `catalogue_id` (e.g. `"dataset_dictionary.layer1.2A"`, `"artefact_registry_1B"`, `"schemas.3A.yaml"`).

**Retryability**

* **Non-retryable** without catalogue correction.

  * Retrying S0 without fixing or restoring the catalogue artefact will reproduce the failure.

---

### 9.4 Policy / prior sealing failures

#### `E3A_S0_003_POLICY_SET_INCOMPLETE`

**Condition**

Raised when the governed 3A policy/prior set required for S0 cannot be fully resolved, for example:

* The zone mixture policy, country→zone α-priors, zone floor/bump policy, or the required day-effect policy is **missing** from the catalogue for the current `parameter_hash`.
* Multiple conflicting artefacts satisfy the same logical ID/role, and S0 cannot choose a single one deterministically.

**Semantics**

* MUST include structured fields:

  * `missing_roles[]` — list of missing logical roles (e.g. `["zone_mixture_policy","country_zone_alphas"]`),
  * `conflicting_ids[]` — list of IDs for which multiple candidates were found (if any).

**Retryability**

* **Non-retryable** without configuration change.

  * The parameter set (or catalogue) MUST be corrected and, if necessary, a new `parameter_hash` computed before retry.

---

#### `E3A_S0_004_POLICY_SCHEMA_INVALID`

**Condition**

Raised when any 3A policy/prior artefact **exists** but fails validation against its `schema_ref`, e.g.:

* `zone_mixture_policy` YAML does not match its JSON-Schema,
* `country_zone_alphas` violates domain/range constraints,
* `zone_floor_policy` or `day_effect_policy_v1` is structurally invalid.

**Semantics**

* MUST include structured fields:

  * `logical_id` — the ID of the invalid policy artefact,
  * `schema_ref` — the schema anchor that failed,
  * `violation_count` — count of validation errors (non-zero).

**Retryability**

* **Non-retryable** without fixing the artefact content.

  * Policy files MUST be corrected; if they are part of 𝓟, a new `parameter_hash` MUST be computed.

---

### 9.5 Sealed input resolution and digest failures

#### `E3A_S0_005_SEALED_INPUT_RESOLUTION_FAILED`

**Condition**

Raised when S0 cannot resolve one or more of the artefacts that are required to be in the sealed set `𝕊`, for example:

* A dictionary or registry entry exists but no concrete `path` for the current `manifest_fingerprint` can be found.
* The artefact type or owner segment is ambiguous or missing in the registry.
* An artefact path resolves to multiple underlying objects and S0 cannot deterministically pick exactly one.

**Semantics**

* MUST include structured fields:

  * `unresolved_ids[]` — list of logical IDs that could not be fully resolved,
  * `owner_segments[]` — optional hints of affected segments.

**Retryability**

* **Non-retryable** without catalogue/environment fix.

  * The dictionary/registry or the underlying artefacts must be corrected.

---

#### `E3A_S0_006_SEALED_INPUT_DIGEST_MISMATCH`

**Condition**

Raised when a sealed artefact’s computed digest does not match an existing canonical digest where one is expected; examples:

* For upstream bundles, the per-file digest or composite digest computed by S0 disagrees with an expected value maintained in a higher-level artefact (if such a mechanism is introduced).
* For artefacts that already carry an embedded `sha256_hex` field (e.g. some Layer-1 validation receipts), S0’s computed digest of the file content disagrees with that embedded field.

If no such embedded or external canonical digest exists for a given artefact, this error MUST NOT be raised; S0’s computed digest becomes the canonical one.

**Semantics**

* MUST include structured fields:

  * `logical_id`,
  * `path`,
  * `expected_sha256_hex`,
  * `computed_sha256_hex`.

**Retryability**

* **Non-retryable** until the underlying artefact or its metadata is reconciled.

  * This error typically indicates corruption or unauthorised modification.

---

### 9.6 Output consistency and schema failures

#### `E3A_S0_007_OUTPUT_SCHEMA_INVALID`

**Condition**

Raised when the S0 outputs that S0 is about to write or has just written fail validation against their own schemas:

* `s0_gate_receipt_3A` does not conform to `schemas.3A.yaml#/validation/s0_gate_receipt_3A`.
* `sealed_inputs_3A` rows do not conform to `schemas.3A.yaml#/validation/sealed_inputs_3A`.

This error MUST be raised **before** any invalid artefact is published (i.e. validation is part of the write path).

**Semantics**

* MUST include structured fields:

  * `output_id ∈ {"s0_gate_receipt_3A","sealed_inputs_3A"}`,
  * `violation_count`.

**Retryability**

* **Retryable** only if the implementation bug causing the invalid shape is fixed; from a spec perspective, this indicates a violation of the design, not input data.

---

#### `E3A_S0_008_OUTPUT_SELF_INCONSISTENT`

**Condition**

Raised when S0’s outputs are internally inconsistent, for example:

* A policy/prior artefact appears in `sealed_policy_set` but not in `sealed_inputs_3A` (or vice versa).
* An upstream gate bundle recorded in `upstream_gates` is missing from `sealed_inputs_3A`.
* A `sha256_hex` recorded in `s0_gate_receipt_3A` does not match the one recorded for the same artefact in `sealed_inputs_3A`.

**Semantics**

* MUST include structured fields:

  * `field_group ∈ {"upstream_gates","sealed_policy_set","sealed_inputs_3A"}`,
  * `logical_id` (if applicable),
  * `path` (if applicable).

**Retryability**

* **Retryable only after implementation or configuration fix**; this error indicates that the S0 implementation did not follow its own rules.

---

### 9.7 Immutability and idempotence failures

#### `E3A_S0_009_IMMUTABILITY_VIOLATION`

**Condition**

Raised when S0 detects that artefacts already exist for `manifest_fingerprint` that differ from what it would produce for the same `(parameter_hash, manifest_fingerprint, seed)` and stable catalogue, for example:

* Existing `s0_gate_receipt_3A` at `fingerprint=F` is not byte-identical to the newly assembled JSON object.
* Existing `sealed_inputs_3A` rows, when read and sorted by the canonical key, do not match the newly constructed row set.

**Semantics**

* MUST include structured fields:

  * `output_id ∈ {"s0_gate_receipt_3A","sealed_inputs_3A","both"}`,
  * `difference_kind ∈ {"content","row_set","encoding"}` (coarse classification).

**Retryability**

* **Non-retryable until conflict is resolved.**

  * Operators MUST determine which snapshot is authoritative (if any) and either:

    * remove/rename conflicting artefacts, or
    * bump `manifest_fingerprint` / `parameter_hash` and rerun.

---

### 9.8 Infrastructure / I/O failures

#### `E3A_S0_010_INFRASTRUCTURE_IO_ERROR`

**Condition**

Raised when S0 cannot complete its work due to environment-level issues that are outside the logical design, for example:

* Transient object-store or filesystem unavailability,
* Permission errors when reading catalogue entries or writing outputs,
* Network timeouts when accessing remote catalogues or bundles.

These errors must be clearly distinguishable from semantic failures (001–009).

**Semantics**

* MUST include structured fields:

  * `operation ∈ {"read","write","list","stat"}`,
  * `path` (if available),
  * `io_error_class` (short string; e.g. `"timeout"`, `"permission_denied"`, `"not_found"`).

**Retryability**

* **Potentially retryable**, subject to infrastructure policy.

  * Orchestration MAY attempt automatic retries with backoff, but every retry MUST still satisfy all acceptance criteria in §8 before any S0 outputs are considered valid.

---

### 9.9 Mapping to run-report

While the detailed run-report spec lives in §10, the binding requirement here is:

* Every 3A.S0 run MUST end in exactly one of:

  * `status="PASS"` with **no error code**, or
  * `status="FAIL"` with **exactly one** of the above error codes and its associated structured fields.

Implementations MAY add additional free-text context, but MUST NOT invent new error codes or conflate multiple categories into a single opaque failure.

---

## 10. Observability & run-report integration **(Binding)**

This section fixes what 3A.S0 **MUST emit** for observability and how it **MUST surface** into the Layer-1 run-report. The intent is that any operator or audit harness can reconstruct:

* what S0 tried to do,
* which upstream gates it saw,
* exactly what it sealed, and
* why it failed, if it failed—

without re-reading every bundle and config by hand.

---

### 10.1 Structured logging requirements

3A.S0 MUST emit **structured log events** for:

1. **State start**

   * Emitted once per invocation, at the beginning of S0.
   * MINIMUM fields:

     * `layer = "layer1"`
     * `segment = "3A"`
     * `state = "S0"`
     * `parameter_hash` (hex64)
     * `manifest_fingerprint` (hex64)
     * `seed` (uint64)
     * `attempt` (monotone integer for retries, if provided by orchestration)
   * Log level: `INFO`.

2. **State success**

   * Emitted once if and only if S0 reaches PASS as per §8.1.
   * MINIMUM fields:

     * All “start” fields above, plus:
     * `status = "PASS"`
     * `error_code = null`
     * `sealed_input_count_total`
     * `sealed_input_count_by_owner_segment` (map: segment → count)
     * `sealed_policy_count` (size of `sealed_policy_set`)
     * `upstream_gates = { "1A": "PASS", "1B": "PASS", "2A": "PASS" }`
     * `elapsed_ms` (deterministic duration measurement from process start to end; source of timing is out of scope but MUST NOT affect any other behaviour).
   * Log level: `INFO`.

3. **State failure**

   * Emitted once if and only if S0 terminates without satisfying §8.1.
   * MINIMUM fields:

     * All “start” fields above, plus:
     * `status = "FAIL"`
     * `error_code` (one of §9’s codes)
     * `error_class` (short, e.g. `"UPSTREAM_GATE"`, `"CATALOGUE"`, `"POLICY"`, `"SEALED_INPUT"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`)
     * `error_details` (structured map with the required fields for that code, per §9)
     * `upstream_gates` (if known)
     * `sealed_input_count_total` (if enumeration progressed that far; else 0)
     * `elapsed_ms` (if measurable).
   * Log level: `ERROR`.

Log events MUST be:

* **structured** (JSON or equivalent key/value)
* **machine-parseable**, and
* **free of row-level data** (no merchant IDs, no per-site information, no raw config bodies).

---

### 10.2 Segment-state run-report row

Layer-1 maintains a run-report over segment states. 3A.S0 MUST contribute exactly **one row** per invocation into the **segment-state run-report** for the triple `(parameter_hash, manifest_fingerprint, seed)`.

The exact dataset ID and schema are defined at the layer level (e.g. `run_report.layer1.segment_states` with schema anchor such as `schemas.layer1.yaml#/run_report/segment_state_run`). For 3A.S0, the row MUST contain at least:

* **Identity & context**

  * `layer = "layer1"`
  * `segment = "3A"`
  * `state = "S0"`
  * `parameter_hash`
  * `manifest_fingerprint`
  * `seed`
  * `attempt` (if available)

* **Outcome**

  * `status ∈ {"PASS","FAIL"}`
  * `error_code` (null on PASS, one of §9 on FAIL)
  * `error_class` (as per §10.1)
  * `first_failure_phase` (optional enum in `{"UPSTREAM_GATES","CATALOGUE","POLICY_SEAL","SEALED_INPUT_ENUMERATION","OUTPUT_WRITE","IMMUTABILITY","INFRASTRUCTURE"}`)

* **Upstream gate summary**

  * `gate_1A_status ∈ {"PASS","FAIL","NOT_CHECKED"}`
  * `gate_1B_status ∈ {"PASS","FAIL","NOT_CHECKED"}`
  * `gate_2A_status ∈ {"PASS","FAIL","NOT_CHECKED"}`

* **Sealed inputs summary**

  * `sealed_input_count_total`
  * `sealed_input_count_by_owner_segment` (serialised map: segment → int)
  * `sealed_input_count_by_kind` (serialised map: artefact_kind → int)

* **Policy/prior summary**

  * `sealed_policy_count`
  * `sealed_policy_roles` (set of logical roles sealed, e.g. `["zone_mixture_policy","country_zone_alphas","zone_floor_policy","day_effect_policy"]`)

* **Catalogue versions**

  * `schemas_layer1_version`
  * `schemas_3A_version`
  * `dictionary_layer1_3A_version`
  * Optionally: versions for other segment dictionaries/registries used.

* **Timing**

  * `started_at_utc` (as recorded by the orchestrator or an upstream run-environ artefact; MUST be deterministic for replay under the same manifest)
  * `finished_at_utc` (same source rule)
  * `elapsed_ms` (derived).

3A.S0 MUST ensure:

* The run-report row is **consistent** with `s0_gate_receipt_3A` and `sealed_inputs_3A` (counts and statuses match).
* For PASS, `gate_*_status` MUST be `"PASS"` for 1A/1B/2A.
* For FAIL, `gate_*_status` MUST reflect the last known status at the point of failure (e.g. `"FAIL"` for the segment where HashGate failed, `"NOT_CHECKED"` for later ones if S0 aborted early).

---

### 10.3 Metrics & counters

In addition to logging and run-report, 3A.S0 MUST expose a small set of **numeric counters** for monitoring (e.g. via metrics backend). At minimum:

* `mlr_3a_s0_runs_total{status="PASS"|"FAIL"}`
* `mlr_3a_s0_upstream_gate_failures_total{segment="1A"|"1B"|"2A"}`
* `mlr_3a_s0_policy_seal_failures_total`
* `mlr_3a_s0_sealed_inputs_count` (gauge; last run)
* `mlr_3a_s0_sealed_inputs_by_segment{segment="1A"|"1B"|"2A"|"2B"|"3A"|"ingress"}` (gauges)
* `mlr_3a_s0_duration_ms` (histogram over `elapsed_ms`)

Exact metric naming and export mechanism are implementation details, but:

* Metrics MUST be derivable from the same underlying data as the run-report rows.
* Metrics MUST NOT contain row-level identifiers or sensitive content (paths may be summarised by IDs / segments / kinds only).

---

### 10.4 Correlation & traceability

To support end-to-end tracing across Layer-1:

1. **Correlation IDs**

   * If the Layer-1 infrastructure provides a correlation or trace ID (e.g. `trace_id`), 3A.S0 MUST:

     * propagate it into all structured logs for S0, and
     * include it in the run-report row (e.g. `trace_id` column), if present.
   * If no such ID exists, S0 MUST NOT invent one; it relies on `(parameter_hash, manifest_fingerprint, seed)` as its primary correlation triple.

2. **Linkage to 3A validation bundle (later state)**

   * The future 3A validation state MUST include:

     * a pointer to `s0_gate_receipt_3A` (path and `sha256_hex`), and
     * a pointer to `sealed_inputs_3A` (path and `sha256_hex`),
       in its own validation bundle index.
   * S0’s run-report row, `s0_gate_receipt_3A` and `sealed_inputs_3A` together MUST be sufficient for a replay harness to:

     * re-locate the S0 outputs, and
     * verify that 3A later ran under the same sealed input set.

---

### 10.5 Retention, access and privacy

Even though S0 handles **only catalogue and digest-level information** and no row-level business data, the following are binding:

1. **Retention**

   * `s0_gate_receipt_3A` and `sealed_inputs_3A` MUST be retained for at least as long as:

     * any 3A outputs derived from them, and
     * any downstream models or artefacts that depend on those outputs.
   * Deleting S0 artefacts while their dependent 3A/Layer-2/Layer-3 artefacts remain in use is out of spec.

2. **Access control**

   * Access to S0 artefacts MAY be less restrictive than access to raw business data, but:

     * only principals authorised to see catalogue metadata and config digests SHOULD be able to read them.
   * S0 MUST NOT log secrets (credentials, tokens, private keys) in any field.

3. **No raw data leakage**

   * S0 logs, run-report row, and outputs MUST NOT include:

     * individual `merchant_id` values,
     * per-site coordinates, tzids, or counts,
     * raw policy bodies (beyond what is already visible in the policy artefacts themselves).
   * Where necessary, S0 MAY include **counts** and **IDs** (dataset/artefact IDs), but not row samples.

---

### 10.6 Relationship to Layer-1 run-report governance

Finally, 3A.S0 MUST obey any additional run-report requirements defined by the Layer-1 governance (e.g. mandatory columns, upstream referential integrity). Where there is a conflict:

* Layer-1 run-report specifications take precedence on **shape**,
* this section defines what 3A.S0 MUST populate for its own fields and how those values relate to its outputs and error codes.

Under these rules, every 3A.S0 run is:

* **visible** (via structured logs),
* **summarised** (via a single, well-defined run-report row), and
* **auditable** (via `s0_gate_receipt_3A` and `sealed_inputs_3A`),

without leaking row-level data or undermining the authority chain established in earlier sections.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on how 3A.S0 is expected to behave at scale, and where implementers should put their optimisation effort. The binding rules remain in §§1–10; this section explains their performance implications.

---

### 11.1 Workload shape

3A.S0 does **not** touch row-level business data and does **not** run any numeric models. Its work is dominated by:

* Loading and validating a **small, fixed set** of catalogue artefacts
  (schema packs, dataset dictionaries, artefact registries).
* Verifying **three upstream validation bundles** (1A, 1B, 2A) using the HashGate rule.
* Reading a **small number of policy/prior artefacts** (3A configs, 2B day-effect policy).
* Computing **SHA-256 digests** for:

  * those policies/priors, and
  * each artefact included in the sealed input set `sealed_inputs_3A`.

There is **no dependence on merchant or outlet count** in S0’s core logic: S0 never scans `outlet_catalogue`, `site_timezones` or other high-cardinality tables row-by-row. Its asymptotic cost is proportional to the **number and size of artefacts** it seals, not to the number of merchants/sites.

---

### 11.2 Cost drivers

The main cost drivers are:

1. **Bundle verification (1A/1B/2A)**

   * Reading `index.json` per bundle is negligible.
   * Re-reading each bundle file to recompute per-file SHA-256 is **O(bytes_in_bundle)**.
   * Since 1A/1B/2A validation bundles are expected to be relatively small (indexes, metrics, checksums, receipts), this cost is usually modest and independent of data volume.

2. **Policy/prior sealing**

   * 3A policies/priors (mixture policy, α-priors, floors, day-effect policy) are expected to be **small to medium** JSON/YAML files with size proportional to the number of countries/tzids.
   * Digesting and validating them is effectively **O(#countries × #zones_per_country)** and small compared to main data volumes.

3. **Digesting sealed inputs**

   * For upstream gates and policies, cost is as above.
   * For **large data-plane artefacts** (e.g. `outlet_catalogue`, `site_timezones`, `tz_timetable_cache`), digest cost is **O(size_of_dataset)** if S0 is specified to hash the full file bytes.
   * In practice, implementers SHOULD consider reusing **existing authoritative digests** where available (e.g. egress checksum manifests emitted by upstream segments) and/or hashing at the **file container level** (Parquet file bytes), not at row level; this preserves the contract while keeping S0’s runtime modest.

---

### 11.3 Scaling with number of fingerprints

3A.S0 is **per-manifest**, partitioned by `fingerprint={manifest_fingerprint}`. Scaling behaviour:

* For a fixed infrastructure, increasing the number of fingerprints increases:

  * the number of times S0 must verify upstream bundles, and
  * the number of times it must seal the same static references (e.g. `iso3166_canonical_2024`, `tz_world_2025a`).

Mitigations / expectations:

* Catalogue artefacts (schemas, dictionaries, registries) are **shared** across fingerprints and SHOULD be cached by the implementation (in memory or via a local cache layer).
* Reference datasets that do not depend on `fingerprint` (e.g. ISO tables) MAY be hashed once and their digests reused across runs; S0 only needs to ensure that the **same version** is being referenced.

Under these assumptions, S0’s marginal cost per additional fingerprint is dominated by:

* reading three upstream validation bundles, and
* re-digesting any fingerprint-specific artefacts it decides to seal (e.g. `tz_timetable_cache@fingerprint`).

---

### 11.4 Concurrency and lock contention

3A.S0 is naturally **embarrassingly parallel** across fingerprints:

* Each `(parameter_hash, manifest_fingerprint, seed)` triple can be processed independently.
* There is no shared mutable state between runs at the logical level.

Implementation guidance:

* Writers MUST still enforce **atomic write** semantics per fingerprint for `s0_gate_receipt_3A` and `sealed_inputs_3A` to avoid immutability violations (§7, §9).
* At the storage level, optimistic write-once or “create if not exists” patterns are preferred to global locks.

As a result, large fleets of manifests can run 3A.S0 in parallel, constrained mainly by:

* underlying object store throughput, and
* CPU capacity for hashing and JSON/YAML validation.

---

### 11.5 Memory footprint

3A.S0’s memory footprint is expected to be modest:

* It needs to hold:

  * a few YAML/JSON documents (catalogue artefacts, policies, bundle indexes), and
  * small to medium metadata structures describing the sealed input set.
* It does **not** need to load entire Parquet tables or large binaries into memory at once; hashing can be performed in a streaming fashion over file chunks.

Implementations SHOULD:

* treat all large inputs as **streamable** (read in fixed-size chunks into the hash),
* avoid constructing in-memory copies of large artefacts when computing digests.

---

### 11.6 Suggested operational SLOs for S0

The design intent is that, in a reasonably provisioned environment:

* **Latency per S0 run** should be dominated by I/O and remain in the **sub-minute** range even when data-plane artefacts are in the multi-GB range, assuming streaming hashing and cached catalogue artefacts.
* **CPU overhead** should be primarily digest computation; this can be offloaded or hardware-accelerated if needed without changing the logical contract.
* **Failure rate** attributable to S0 itself (excluding upstream gate failures and genuine configuration errors) should be very low; most S0 failures ought to signal genuine problems in upstream segments or configuration, not S0 instability.

These numbers are **informative**: actual SLOs are infrastructure-dependent, but S0 is deliberately designed to be lightweight relative to heavy modelling or synthesis states.

---

### 11.7 Trade-offs and tuning levers

While the contracts in §§1–10 fix the **semantics**, implementers retain some performance tuning levers, provided they do not change observable behaviour:

* **Digest strategy for large artefacts**

  * Where the design allows a choice of canonical digest representation (e.g. entire bundle vs index-only), preferred strategies SHOULD be documented in the 3A contracts and applied consistently.

* **Caching of deterministic digests**

  * If upstream segments already publish **authoritative checksums** (e.g. for `site_timezones`, `outlet_catalogue`), S0 MAY rely on those instead of recomputing digests, as long as:

    * the mapping from artefact → digest is itself part of the sealed input set, and
    * any change to those digests would change `manifest_fingerprint` and/or `parameter_hash`.

* **Catalogue fetch optimisation**

  * Schema packs and dictionaries change infrequently; implementations SHOULD treat them as long-lived, cached artefacts rather than re-fetching them on every S0 run.

Within these bounds, S0 is expected to remain a **small, predictable component** in the overall runtime of 3A: heavy work (Dirichlet sampling, integerisation, routing, validation) lives in later states, while S0 simply asserts that 3A is starting from a **clean, sealed, catalogue-consistent world**.

---

## 12. Change control & compatibility **(Binding)**

This section defines **how the 3A.S0 contract is allowed to evolve over time**, and what guarantees consumers can rely on when:

* the S0 spec itself changes,
* new sealed artefacts are introduced, or
* upstream/layer-wide contracts evolve.

The goal is to make S0 **stable enough** that downstream states (S1–S7), validation harnesses, and operators can reason about compatibility from **version tags + fingerprints**, without reverse-engineering behaviour.

---

### 12.1 Scope of change control

Change control for 3A.S0 covers:

1. The **shape and semantics** of its outputs:

   * `s0_gate_receipt_3A`
   * `sealed_inputs_3A`

2. The **normative sealed input set** `𝕊`:

   * which upstream gates, data-plane surfaces, and policies/priors MUST appear in `sealed_inputs_3A`.

3. The **behavioural contract**:

   * upstream gates S0 MUST verify,
   * invariants around path↔embed, partitioning, and immutability,
   * error taxonomy and acceptance criteria.

It explicitly does **not** govern:

* internal implementation details (e.g. hash chunk size, caching strategy), or
* Layer-1 global contracts (e.g. how `parameter_hash` or `manifest_fingerprint` are defined).

---

### 12.2 S0 contract versioning

3A.S0 has a **contract version**, carried as:

* `version` field in `s0_gate_receipt_3A`, and
* `version` string in the `dataset_dictionary.layer1.3A.yaml` entries for:

  * `s0_gate_receipt_3A`,
  * `sealed_inputs_3A`.

Rules:

1. **Single authoritative version number.**

   * The `version` in `s0_gate_receipt_3A` MUST match the dataset dictionary versions for those outputs (e.g. all `"1.0.0"` initially).
   * Any change to the S0 contract MUST be accompanied by a new semver version and an update to all three locations.

2. **Semver semantics.**

   * `MAJOR.MINOR.PATCH`:

     * **PATCH** (`x.y.z → x.y.(z+1)`): bug fixes or clarifications that do not change observable behaviour for any compliant implementation.
     * **MINOR** (`x.y.z → x.(y+1).0`): backwards-compatible extensions (e.g. new optional fields, new artefacts added to sealed set with clear opt-in semantics).
     * **MAJOR** (`x.y.z → (x+1).0.0`): breaking changes in output shape, sealed set semantics, or behavioural invariants.

3. **Version anchoring.**

   * Consumers MUST NOT infer behaviour from calendar time or build IDs; they MUST rely on the `version` field in `s0_gate_receipt_3A` and, if necessary, on schema_refs.

---

### 12.3 Backwards-compatible changes (allowed without new fingerprint semantics)

The following changes are considered **backwards-compatible** (MINOR or PATCH) for S0, provided they follow the rules below:

1. **Adding optional fields.**

   * Adding new optional fields to `s0_gate_receipt_3A` or `sealed_inputs_3A` schemas, with:

     * default meaning = “absent” for older readers, and
     * no change to existing fields’ semantics.
   * Old consumers MUST be able to ignore these fields without misinterpreting the artefacts.

2. **Extending the sealed set with new artefacts of kind “diagnostic” or “reference”.**

   * Adding **extra** entries to the normative sealed set `𝕊` that are:

     * purely diagnostic, or
     * additional reference surfaces whose absence would have made earlier runs **more conservative**, not **incorrect**.
   * These MUST be clearly labeled with new `role` values (e.g. `"diagnostic_only"`) so that older consumers can ignore them safely.

3. **Tightening validation without changing success cases.**

   * Strengthening S0’s internal checks (e.g. more catalogue consistency assertions) that:

     * never change the outputs for runs that would already have been PASS under the old contract, but
     * may convert some previously “silent-bad” runs into explicit FAILs.

4. **Extending error codes.**

   * Splitting an existing error class into more precise subclasses, or adding new codes, as long as:

     * existing codes keep their original meaning, and
     * `status="PASS"` behaviour is unchanged.
   * Consumers must treat **unknown error codes** as generic `FAIL`.

These changes do **not** require a new `manifest_fingerprint` contract; they only affect how S0 interprets and reports on an existing manifest.

---

### 12.4 Breaking changes (requiring a new major version)

The following are **breaking changes** and MUST trigger a **MAJOR** version bump for the S0 contract (and corresponding schema/dictionary versions):

1. **Shape changes that break old readers.**

   * Removing required fields from `s0_gate_receipt_3A` or `sealed_inputs_3A`.
   * Changing types or semantics of existing fields (e.g. reinterpreting `sha256_hex`, `owner_segment`, or `artefact_kind`).
   * Changing the primary identity columns (e.g. no longer using `path` or `logical_id` as part of the key).

2. **Changing the partitioning or path law.**

   * Removing or renaming the `fingerprint` partition for S0 outputs.
   * Introducing additional partition keys (e.g. adding `seed` or `parameter_hash`) for S0 outputs.
   * Changing token formats (e.g. renaming `fingerprint=` to `manifest=`).

3. **Changing the normative sealed set in a way that invalidates old assumptions.**

   * Removing artefacts from the sealed set that later 3A states or cross-segment tools rely on.
   * Changing the **required** status of an artefact (e.g. making `outlet_catalogue` optional in sealed inputs, or no longer sealing `site_timezones` when later states still depend on it).
   * Reclassifying an artefact from “diagnostic” to “required” or vice versa when existing 3A states depend on the prior classification.

4. **Relaxing upstream gate obligations.**

   * No longer verifying 1A, 1B or 2A validation bundles as a precondition.
   * Changing the hash-gate rule in a way that could accept bundles that would previously have been rejected.

5. **Changing the immutability/idempotence contract.**

   * Allowing S0 to overwrite existing `s0_gate_receipt_3A` / `sealed_inputs_3A` with different content for the same `(parameter_hash, manifest_fingerprint, seed)` and stable catalogue.

Any such change requires:

* a new MAJOR version of `s0_gate_receipt_3A` / `sealed_inputs_3A` in the dataset dictionary,
* updated schemas with new anchors or version tags, and
* clear migration strategies for consumers (see below).

---

### 12.5 Policy & prior evolution vs `parameter_hash`

The **governed parameter set** 𝓟 is outside S0’s direct control, but S0 binds to it via `parameter_hash`. The following are binding rules:

1. **Any change to 3A policy/prior content that affects semantics MUST change `parameter_hash`.**

   * Modifying the content of:

     * zone mixture policy,
     * country→zone α-priors,
     * zone floor/bump rules,
     * day-effect policy version used by 3A,
       MUST result in a new `parameter_hash`, even if schemas and paths are unchanged.

2. **S0 must not silently re-seal changed policies under the same `parameter_hash`.**

   * If S0 observes that the digest of a policy/prior artefact differs from what the Layer-1 parameter resolution logic expects for this `parameter_hash`, it MUST fail with `E3A_S0_006_SEALED_INPUT_DIGEST_MISMATCH` or an equivalent parameter-layer error, rather than proceeding.

3. **Adding optional new policies.**

   * Introducing a new 3A policy/prior artefact that is **optional** and does not affect behaviour when absent (e.g. extra diagnostics) MAY or MAY NOT change `parameter_hash` according to Layer-1 governance.
   * If the new policy is ever read by a later 3A state, it MUST be included in 𝓟, and changing it MUST change `parameter_hash`.

---

### 12.6 Catalogue evolution (schemas, dictionaries, registries)

S0 is sensitive to the **catalogue layer**. The following compatibility rules apply:

1. **Schema evolution.**

   * Upgrading schema packs (e.g. `schemas.3A.yaml` v1 → v1.1) MUST:

     * remain backwards compatible with the artefacts that have already been emitted under prior S0 versions, or
     * be accompanied by a MAJOR contract/version bump and an explicit migration plan.

2. **Dictionary evolution.**

   * Renaming dataset IDs or changing their path templates for S0 outputs is a **breaking change** and must follow §12.4.
   * Adding new datasets (e.g. additional 3A diagnostics) with new IDs is backwards-compatible, provided S0’s sealed set rules are updated accordingly and later states treat them as optional.

3. **Registry evolution.**

   * Adding new artefacts to `artefact_registry_3A.yaml` is backwards-compatible if they are not part of S0’s sealed set.
   * Removing or renaming existing artefacts that S0 seals is a **breaking change** for S0 and MUST be synchronised with a contract version bump.

---

### 12.7 Deprecation policy

When the S0 contract needs to change in a way that may affect existing consumers:

1. **Introduce before deprecating.**

   * New fields, artefacts or behaviours SHOULD be introduced under a new MINOR version while still supporting the previous shape and semantics.
   * Consumers SHOULD be given time to adapt to the new version before the old one is removed.

2. **Deprecation signalling.**

   * `s0_gate_receipt_3A` MAY include an optional `deprecation` block (future version) giving:

     * `deprecated_since_version`,
     * `removal_target_version`,
     * `notes`.
   * This is informative but must not be relied on for enforcement; enforcement is still via version and schema evolution.

3. **Hard removal.**

   * Removing fields, artefacts, or obligations MUST be done in a MAJOR version bump, and any consumers that rely on the old behaviour MUST be pinned to the older version until migrated.

---

### 12.8 Cross-version operation

Given that multiple 3A manifests may be produced under different S0 versions:

1. **Per-manifest version binding.**

   * Each `s0_gate_receipt_3A` explicitly states its `version`.
   * Consumers MUST treat the S0 version as **per-manifest**, not global; different fingerprints may legitimately have different S0 versions.

2. **Consumer strategy.**

   * Consumers that need to operate across many manifests (e.g. global analytics) MUST:

     * either explicitly support all S0 versions they encounter, or
     * restrict themselves to the intersection of fields and behaviours shared across those versions.

3. **No in-place upgrade of historic S0 artefacts.**

   * Existing `s0_gate_receipt_3A` and `sealed_inputs_3A` for old manifests MUST NOT be rewritten to match new schema versions.
   * If re-emitting S0 outputs under a new contract is required for an old manifest, this MUST be treated as a new run with a new `manifest_fingerprint` (or clearly marked as such by Layer-1 governance).

---

Under these rules, 3A.S0 can evolve **incrementally** (clarifications, optional fields, extended sealed sets) while providing **strong guarantees** to downstream states and tools:

* No surprise weakening of upstream gate checks.
* No silent redefinition of what “sealed inputs” means for a given manifest.
* A clear semver and versioning story when genuine breaking changes are needed.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix records the symbols, shorthand and abbreviations used in the 3A.S0 design. It has **no normative force**; it is provided to keep notation consistent across 3A states.

---

### 13.1 Scalar identifiers & hashes

* **`parameter_hash`**
  Layer-1 hash over the governed parameter set 𝓟 (policies, priors, tunables). Treated as **input** to 3A.S0; never derived here.

* **`manifest_fingerprint`** (often written **`F`** in prose)
  Layer-1 hash over the resolved manifest for a run, including `parameter_hash` and all artefacts opened by the engine. Primary partition key for S0 outputs.

* **`seed`**
  Layer-1 global RNG seed (uint64). Captured in S0 outputs but **never consumed** by S0 itself (S0 is RNG-free).

* **`run_id`**
  Layer-1 logging/run identifier (string or u128 encoded as string), used elsewhere as a partition key for RNG logs. Not used as a partition for 3A.S0 outputs.

---

### 13.2 Sets & collections

* **𝓟 (governed parameter set)**
  The set of all policy/prior artefacts that participate in `parameter_hash` for this run, e.g.:

  * 3A zone mixture policy,
  * 3A country→zone α-priors,
  * 3A zone floor/bump policy,
  * 2B day-effect policy (as seen by 3A).

* **𝕊 (sealed input set)**
  The set of all artefacts that 3A is allowed to read for a given `manifest_fingerprint`:
  upstream gates, upstream data-plane inputs, ingress references, and 3A policies/priors. 𝕊 is materialised as `sealed_inputs_3A`.

* **`sealed_policy_set`**
  The subset of 𝓟 explicitly recorded in `s0_gate_receipt_3A` (and also present in 𝕊), with role-labels, schema_refs and digests.

---

### 13.3 Segments, states & artefacts

* **Layer-1 / Segment / Subsegment**

  * *Layer-1*: Merchant Location Realism layer.
  * *Segment*: logical grouping of subsegments (e.g. “1A Merchants→Sites”, “2A Civil Time”, “3A Zone Allocation”).
  * *Subsegment*: the concrete numbered part (e.g. `1A`, `1B`, `2A`, `2B`, `3A`).

* **`3A.S0`**
  “Layer-1 · Segment 3A · State S0 — Gate & Sealed Inputs for Zone Allocation.” The state covered by this document.

* **`s0_gate_receipt_3A`**
  Fingerprint-scoped JSON artefact produced by 3A.S0. Records upstream gate status, catalogue versions, and the sealed policy set.

* **`sealed_inputs_3A`**
  Fingerprint-scoped table produced by 3A.S0. Each row describes one artefact that 3A is allowed to read for this `manifest_fingerprint`.

* **`validation_bundle_S`**
  For upstream segment `S ∈ {1A,1B,2A}`, the directory containing that segment’s validation evidence and `index.json` for a given `manifest_fingerprint`.

* **`_passed.flag`**
  For upstream segment `S ∈ {1A,1B,2A}`, the single-line text file that encodes the composite SHA-256 of the validation bundle under the Layer-1 HashGate rule.

---

### 13.4 Catalogue & schema terms

* **Schema pack**
  A JSON-Schema bundle (e.g. `schemas.layer1.yaml`, `schemas.3A.yaml`) that defines shapes (`schema_ref` anchors) for datasets, bundles and receipts.

* **Dataset dictionary**
  Layer-1 mapping from dataset ID → path template, partition keys, format, `schema_ref`, lineage (e.g. `dataset_dictionary.layer1.3A.yaml`).

* **Artefact registry**
  Manifest-scoped inventory for a subsegment (e.g. `artefact_registry_1A.yaml`, `artefact_registry_3A.yaml`) that describes each artefact’s path, type, role and digest.

* **`schema_ref`**
  A string reference (URI fragment) into a schema pack, e.g.
  `schemas.3A.yaml#/validation/sealed_inputs_3A`.

---

### 13.5 Gate, bundle & digest vocabulary

* **HashGate rule**
  Layer-1 validation rule for segment bundles:

  * `index.json` lists files and per-file SHA-256 (`sha256_hex`),
  * files are ordered by ASCII-lex path,
  * composite digest = SHA-256(concat(bytes(files))),
  * `_passed.flag` contains `sha256_hex = <composite_digest>`.

* **`sha256_hex`**
  Hexadecimal representation (lowercase, 64 chars) of a SHA-256 digest. Used both for per-file digests and composite bundle digests.

* **“No PASS → No read”**
  Contract that a consumer MUST verify a segment’s validation bundle + `_passed.flag` before reading that segment’s egress for a given `manifest_fingerprint`. For 3A, this will eventually apply to the 3A validation bundle produced by a later state, not to S0.

---

### 13.6 Error codes & status

* **`error_code`**
  Canonical S0 error code from §9, e.g.:

  * `E3A_S0_001_UPSTREAM_GATE_FAILED`,
  * `E3A_S0_009_IMMUTABILITY_VIOLATION`.

* **`status`**
  State outcome in logs/layer1/3A/run-report:

  * `"PASS"` — S0 met all acceptance criteria in §8.1 and outputs are valid.
  * `"FAIL"` — S0 terminated with one of the canonical error codes.

* **`error_class`**
  Coarse classification of `error_code`, e.g. `"UPSTREAM_GATE"`, `"CATALOGUE"`, `"POLICY"`, `"SEALED_INPUT"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`.

---

### 13.7 Miscellaneous abbreviations

* **ISO-3166**
  ISO standard for country codes (e.g. `iso3166_canonical_2024`).

* **IANA tzid / tzdb**

  * *IANA tzid*: time-zone identifier string (e.g. `"Europe/London"`), as used in 2A and 2B.
  * *tzdb*: IANA time zone database (compiled into `tz_timetable_cache` by 2A).

* **SLO / SRE (contextual)**
  References to Service Level Objectives (SLOs) and Site Reliability Engineering (SRE) best practices in §11 are descriptive only; they are not part of the binding S0 contract.

---

These symbols and abbreviations are chosen to align with existing Layer-1 documentation for 1A, 1B, 2A and 2B. Future 3A states (S1–S7) SHOULD reuse this vocabulary where applicable to minimise friction when reading across design documents.

---
