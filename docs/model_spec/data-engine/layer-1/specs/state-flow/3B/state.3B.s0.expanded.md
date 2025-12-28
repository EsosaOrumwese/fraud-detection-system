# 3B.S0 — Gate & environment seal

## 1. Purpose & scope *(Binding)*

1.1 **State identity and role in the subsegment**

1.1.1 This state, **3B.S0 — Gate & environment seal** (“S0”), is the **mandatory entry point** for the Layer-1 subsegment **3B — Virtual merchants & CDN surfaces**. No other 3B state MAY execute for a given `{seed, parameter_hash, manifest_fingerprint}` triple unless S0 has completed successfully for that triple.

1.1.2 S0’s primary purpose is to establish a **closed, reproducible environment** for all subsequent 3B states by:

* verifying that all required upstream segments have passed their own validation gates;
* resolving and sealing the **exact set of artefacts** (datasets, policies, schemas, RNG profiles, external geospatial assets) that 3B is permitted to read; and
* emitting a fingerprint-scoped **gate receipt** and **sealed-inputs inventory** that downstream 3B states MUST treat as the sole authority on what is in-scope for this subsegment.

1.1.3 S0 does **not** introduce any new business semantics for virtual merchants or routing; instead, it ties 3B to the existing Layer-1 authority chain:

* Layer-wide schemas (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`),
* upstream segment schemas / dictionaries / registries (1A, 1B, 2A, 2B, 3A), and
* 3B’s own contracts (`schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, `artefact_registry_3B.yaml`).

1.2 **Determinism and RNG-free scope**

1.2.1 S0 is **strictly RNG-free**. It MUST NOT open or advance any Philox stream, emit any RNG event, or depend on any non-deterministic source (wall-clock, external network, hostname, etc.).

1.2.2 All S0 behaviour MUST be a pure, deterministic function of:

* the resolved `{seed, parameter_hash, manifest_fingerprint}` triple;
* the catalogues (schemas, dictionaries, registries) visible at the time of execution; and
* the byte content of the artefacts it seals (datasets, policy files, geospatial assets, RNG profiles).

1.2.3 S0’s outputs are therefore replayable: given the same `{seed, parameter_hash, manifest_fingerprint}` and the same sealed artefacts, re-execution MUST produce bit-identical `s0_gate_receipt_3B` and `sealed_inputs_3B`.

1.3 **Relationship to upstream and downstream states**

1.3.1 S0 is responsible for enforcing upstream **HashGate / PASS** requirements on behalf of the 3B subsegment. In particular, for the target `manifest_fingerprint`, S0 MUST:

* verify the 1A, 1B, 2A and 3A validation bundles and `_passed.flag` artefacts using their own published bundle laws; and
* refuse to proceed (FATAL failure) if any mandatory upstream segment fails or is missing.

1.3.2 S0 does **not** read any rows from upstream data-plane datasets (e.g. `outlet_catalogue`, `site_locations`, `site_timezones`, `zone_alloc`). It only verifies their existence, version, schema, and content digest, and records those facts in the sealed-inputs inventory.

1.3.3 For downstream 3B states (S1–S5), S0 defines the **only admissible input universe**:

* S1–S5 MUST treat `s0_gate_receipt_3B` as the canonical identity record for `{seed, parameter_hash, manifest_fingerprint}` and MUST assert that their own embedded identity values match.
* S1–S5 MUST restrict themselves to artefacts enumerated in `sealed_inputs_3B` for the target fingerprint; reading any artefact not listed in `sealed_inputs_3B` is a contract violation.

1.4 **Out-of-scope behaviour**

1.4.1 The following concerns are explicitly out of scope for S0 and are handled by later 3B states:

* classification of merchants as **virtual vs physical** and any per-merchant channel logic;
* construction of **virtual settlement nodes** (legal anchors);
* construction of **CDN edge catalogues** and alias tables;
* per-arrival routing or the emission of routing RNG events (e.g. `cdn_edge_pick`);
* 3B’s segment-level validation bundle and `_passed.flag` (owned by the terminal 3B validation state).

1.4.2 S0 MUST NOT attempt to “peek ahead” or partially implement behaviour belonging to later states. Any logic that depends on virtual classification, settlement geometry, CDN weights, or per-arrival dynamics MUST be captured in the appropriate downstream state specifications and must rely on S0 only for **identity and sealed inputs**, not for data-plane decisions.

---

## 2. Preconditions & gated inputs *(Binding)*

2.1 **Execution context & identity**

2.1.1 S0 SHALL execute only in the context of a Layer-1 run where the triple
`{seed, parameter_hash, manifest_fingerprint}` has already been resolved by the enclosing engine / run harness according to the Layer-1 numeric and hashing policy.

2.1.2 At process start, S0 MUST be provided with:

* `seed` — the Layer-1 Philox seed for this run;
* `parameter_hash` — the tuple-hash over the governed 3B parameter set;
* `manifest_fingerprint` — the enclosing manifest fingerprint for the Layer-1 run.

2.1.3 S0 MUST verify that:

* the numeric profile in effect matches the layer-wide policy (as declared in `schemas.layer1.yaml#/governance/numeric_policy_profile`);
* the RNG algorithm and envelope parameters exposed to 3B (`philox2x64-10`, envelope fields, trace layout) match the layer-wide RNG definitions in `schemas.layer1.yaml#/rng/...`.

2.1.4 If S0 detects that any of these identity or governance values are missing, inconsistent, or incompatible with `schemas.layer1.yaml`, it MUST treat this as a FATAL configuration error and abort without writing any 3B outputs.

---

2.2 **Upstream segment PASS gates**

2.2.1 S0 MUST verify, for the target `manifest_fingerprint`, that the following upstream segments have successfully passed their own validation gates:

* Segment 1A — Merchant outlet counts;
* Segment 1B — Site placement / `site_locations`;
* Segment 2A — Civil time / `site_timezones` + `tz_timetable_cache`;
* Segment 3A — Cross-zone merchant allocation / `zone_alloc` + `zone_alloc_universe_hash`.

2.2.2 For each segment above, S0 MUST:

* locate the segment’s `validation_bundle_*` directory and `_passed.flag` artefact via the dataset dictionary and artefact registry;
* recompute (or delegate to a shared HashGate utility) the bundle digest exactly as defined in that segment’s spec;
* assert that the recomputed digest matches the bytes recorded in `_passed.flag` for the same `manifest_fingerprint`.

2.2.3 If any mandatory upstream segment:

* is missing its validation bundle or `_passed.flag` for the target `manifest_fingerprint`, or
* has a bundle digest that does not match the recorded flag,

then S0 MUST fail with a FATAL upstream-gate error and MUST NOT proceed to seal any 3B inputs.

2.2.4 S0 MUST NOT attempt to “repair” or ignore upstream validation failures. The only supported behaviour is to surface the failure (with a canonical error code) and abort 3B for that `{seed, parameter_hash, manifest_fingerprint}`.

---

2.3 **Schema, dictionary and registry preconditions**

2.3.1 Before sealing any inputs, S0 MUST resolve and load the following schema packs:

* `schemas.layer1.yaml` — Layer-wide primitives, RNG envelopes and validation shapes;
* `schemas.ingress.layer1.yaml` — canonical shapes for ingress datasets used transitively by 3B;
* `schemas.3B.yaml` — segment-local shapes for 3B datasets, including `s0_gate_receipt_3B` and `sealed_inputs_3B`.

2.3.2 S0 MUST resolve and load the following catalogues for 3B:

* `dataset_dictionary.layer1.3B.yaml`;
* `artefact_registry_3B.yaml`.

It MUST verify that the versions of these catalogues are mutually compatible and compatible with the loaded `schemas.3B.yaml` (e.g. by matching a declared `schema_version` / `dictionary_version` / `registry_version` tuple).

2.3.3 If S0 detects an incompatibility between `schemas.3B.yaml`, the dataset dictionary and the artefact registry (e.g. mismatched major versions, missing dataset IDs, or inconsistent schema refs), it MUST fail with a configuration error and MUST NOT emit `s0_gate_receipt_3B` nor `sealed_inputs_3B`.

2.3.4 S0 MUST NOT attempt to infer dataset shapes or paths from hard-coded conventions. All dataset IDs, logical artefact IDs and paths that S0 relies on MUST be obtained via the dataset dictionary and artefact registry.

---

2.4 **Required upstream datasets for 3B (gated inputs)**

2.4.1 S0 MUST confirm that the following upstream datasets are resolvable and readable via the dataset dictionary and artefact registry for the target `manifest_fingerprint` (and `seed` where applicable):

* `outlet_catalogue` (Segment 1A) at `seed={seed}, fingerprint={manifest_fingerprint}`;
* `site_locations` (Segment 1B) at `seed={seed}, fingerprint={manifest_fingerprint}`;
* `site_timezones` (Segment 2A) at `seed={seed}, fingerprint={manifest_fingerprint}`;
* `tz_timetable_cache` (Segment 2A) at `fingerprint={manifest_fingerprint}`;
* `zone_alloc` (Segment 3A) at `seed={seed}, fingerprint={manifest_fingerprint}`;
* `zone_alloc_universe_hash` (Segment 3A) at `fingerprint={manifest_fingerprint}`.

2.4.2 In S0, these datasets are treated as **metadata-only** inputs:

* S0 MAY open them to verify existence, schema ID, partition keys and content digests;
* S0 MUST NOT read or interpret individual data rows from these datasets.

2.4.3 If any of the datasets in 2.4.1 cannot be resolved or fail a basic metadata-level integrity check (e.g. schema mismatch, missing partition, digest mismatch), S0 MUST fail with an upstream-dataset error and MUST NOT proceed.

---

2.5 **Required policy, RNG and geospatial artefacts (to be sealed)**

2.5.1 S0 MUST resolve and seal the following **virtual / CDN policies**, using logical IDs defined in `artefact_registry_3B.yaml`:

* Virtual classification rules (e.g. `mcc_channel_rules.yaml` or equivalent), defining which merchants are eligible for the virtual path;
* Virtual settlement coordinates (e.g. `virtual_settlement_coords.*`), defining the legal settlement anchor per merchant or brand;
* CDN country weight policy (e.g. `cdn_country_weights.yaml`), defining the target country mix for CDN edges;
* Virtual / CDN validation policy (e.g. `virtual_validation.yml`), defining post-hoc tests and thresholds for 3B (used only in downstream validation states).

2.5.2 S0 MUST resolve and seal the following **geospatial and time assets**, which will be used transitively in downstream 3B states:

* HRSL / population rasters or equivalent base raster used for placing CDN edge nodes;
* world polygons / country shapes used for country membership of edge nodes;
* tz-world polygons and the pinned tzdb archive / release tag used for resolving settlement and edge tzids (if 3B uses any tz resolution directly).

2.5.3 S0 MUST resolve and seal the following **RNG and routing policies**:

* the Layer-1 routing RNG policy pack (e.g. `route_rng_policy_v1`) that defines the Philox stream names, budgets and event families for routing and CDN picks;
* any dedicated CDN RNG policy or key material (e.g. `cdn_rng_policy_v1`, `cdn_key_digest`) that will be used to derive Philox stream IDs or keys for virtual edge selection.

2.5.4 For each artefact in 2.5.1–2.5.3, S0 MUST:

* resolve the logical ID to a concrete path and partition (if any) using the dictionary and registry;
* verify that the referenced file exists, is readable, and is of the expected type/format;
* compute or verify a SHA-256 digest over the artefact’s bytes; and
* record the logical ID, path, schema_ref (if applicable), role and digest in `sealed_inputs_3B`.

2.5.5 If any required policy, geospatial or RNG artefact cannot be resolved, opened or digested, S0 MUST fail with a FATAL sealed-input error and MUST NOT proceed.

---

2.6 **Scope of gated inputs & downstream obligations**

2.6.1 The set of artefacts enumerated in `sealed_inputs_3B` SHALL define the **closed input universe** for the 3B subsegment. Downstream states S1–S5:

* MUST treat `sealed_inputs_3B` as the authority on which artefacts they MAY read;
* MUST NOT read from any dataset, policy, schema, RNG profile or external file that is not listed in `sealed_inputs_3B` for the target `manifest_fingerprint`.

2.6.2 S0 MUST ensure that any artefact S1–S5 are expected to use (as per their state specs) is either:

* present in `sealed_inputs_3B`, or
* explicitly marked as optional in both the state spec and the dataset dictionary (with a documented fallback behaviour).

2.6.3 If, at runtime, a downstream 3B state discovers that it needs an artefact that is absent from `sealed_inputs_3B`, that state MUST treat this as a configuration error in 3B.S0 and fail fast rather than attempting to resolve or open the artefact directly.

2.6.4 S0’s own outputs (`s0_gate_receipt_3B`, `sealed_inputs_3B`) are themselves **gated inputs** for S1–S5:

* Any 3B state that does not first verify the existence and schema validity of `s0_gate_receipt_3B` for the target `manifest_fingerprint` is non-compliant;
* Any 3B state that runs when `s0_gate_receipt_3B` or `sealed_inputs_3B` are missing or invalid MUST be considered undefined behaviour for the engine and MUST be treated as a bug in the driver or orchestration layer.

---

## 3. Inputs & authority boundaries *(Binding)*

3.1 **Upstream segment egress (metadata-only in S0)**

3.1.1 For the target `{seed, manifest_fingerprint}`, S0 SHALL treat the following upstream **segment egress datasets** as **in-scope** but **metadata-only** inputs:

* `outlet_catalogue` (Segment 1A), partitioned by `seed={seed}, fingerprint={manifest_fingerprint}`;
* `site_locations` (Segment 1B), partitioned by `seed={seed}, fingerprint={manifest_fingerprint}`;
* `site_timezones` (Segment 2A), partitioned by `seed={seed}, fingerprint={manifest_fingerprint}`;
* `tz_timetable_cache` (Segment 2A), partitioned by `fingerprint={manifest_fingerprint}` only;
* `zone_alloc` (Segment 3A), partitioned by `seed={seed}, fingerprint={manifest_fingerprint}`;
* `zone_alloc_universe_hash` (Segment 3A), partitioned by `fingerprint={manifest_fingerprint}` only.

3.1.2 S0 MAY open these datasets solely to:

* resolve their physical storage locations and partition sets via the dataset dictionary;
* verify that each dataset conforms to its registered `schema_ref` (including partition keys and writer sort, where applicable);
* compute or verify a content digest (e.g. file-level SHA-256) for the purposes of sealing and later validation.

3.1.3 S0 MUST NOT:

* read, filter or aggregate individual data rows from any dataset in 3.1.1;
* derive any business-level facts from their contents (e.g. merchant counts, site counts, zone splits);
* attempt to “repair” or rewrite any upstream dataset.

3.1.4 For the avoidance of doubt, **authority for the semantics** of these datasets remains with the originating segments:

* Segment 1A remains the authority on outlet counts and cross-country order;
* Segment 1B remains the authority on physical site coordinates;
* Segment 2A remains the authority on per-site tzids and tzdb transitions;
* Segment 3A remains the authority on merchant×country×zone site counts and the routing universe hash.

S0 MUST only attest to their presence, shape and digest, not reinterpret their semantics.

---

3.2 **Ingress / external artefacts for 3B**

3.2.1 S0 SHALL treat the following **ingress / external artefacts** as inputs to be sealed for 3B, using logical IDs defined in the 3B dataset dictionary and artefact registry:

* Virtual classification rules (e.g. `mcc_channel_rules.yaml` or equivalent policy pack);
* Virtual settlement coordinate sources (e.g. `virtual_settlement_coords.csv` / `virtual_settlement_coords.parquet`);
* CDN country mix policy (e.g. `cdn_country_weights.yaml` or equivalent);
* One or more validation policy packs for virtual / CDN behaviour (e.g. `virtual_validation.yml`).

3.2.2 S0 MUST obtain, for each ingress artefact:

* the logical ID and role (e.g. `virtual_classification_rules`, `virtual_settlement_coords`, `cdn_country_weights`);
* the concrete path and partition (if any) from the dataset dictionary / artefact registry;
* the declared format (YAML, CSV, Parquet, etc.) and expected `schema_ref` where applicable;
* a SHA-256 digest over the raw bytes.

3.2.3 S0 MUST record each such artefact in `sealed_inputs_3B` with at least:

* `owner_segment = "3B"` (or the relevant upstream segment, for shared policies);
* `artefact_kind ∈ {policy, dataset, external}`;
* `logical_id` (stable, registry-defined identifier);
* `path` and `schema_ref` (if applicable);
* `sha256_hex`;
* a short `role` string describing how 3B states are expected to use the artefact.

3.2.4 S0 MUST NOT make any attempt to validate the **business content** of these artefacts (e.g. whether MCC rules correctly classify merchants, or whether CDN weights sum to 1). Such validation belongs in downstream 3B states and/or in separate configuration pipelines.

---

3.3 **Geospatial, timezone and RNG policy inputs**

3.3.1 S0 SHALL treat the following **geospatial and timezone artefacts** as inputs to be sealed, even if they are physically shared with other segments:

* HRSL / population raster(s) or equivalent sources that S1–S5 will use to place CDN edges;
* world-country polygons, used to derive country membership for CDN edge nodes;
* tz-world polygons and the pinned tzdb archive (tzdata release) that S1–S5 may rely on for settlement / edge tz resolution, to the extent 3B interacts with timezones directly.

3.3.2 Where these artefacts are already sealed and consumed by 1B / 2A, S0 MAY:

* refer to the same logical IDs and digests as those segments;
* record them in `sealed_inputs_3B` as **shared** artefacts, with `owner_segment` pointing to the segment that owns their ingest and validation.

3.3.3 S0 SHALL also seal the **RNG and routing policy packs** relevant for 3B, including but not limited to:

* the Layer-1 routing RNG policy pack (e.g. `route_rng_policy_v1`) which defines Philox stream names, budget envelopes and mapping rules for routing and CDN events;
* any dedicated CDN RNG policy or key material (e.g. `cdn_rng_policy_v1`, `cdn_key_digest`) used to derive `rng_stream_id` values for the `cdn_edge_pick` event family.

3.3.4 S0 MUST treat the layer-wide RNG definitions in `schemas.layer1.yaml` as the **shape and envelope authority** for RNG events. In particular:

* `schemas.layer1.yaml#/rng/core/rng_envelope` defines the base envelope fields that all RNG events MUST carry;
* `schemas.layer1.yaml#/rng/events/cdn_edge_pick` defines the payload shape for the virtual edge-pick events that later 3B states will emit.

S0 MUST NOT introduce any new RNG event families or override these schemas.

---

3.4 **Schema, dictionary, registry and S0 as separate authorities**

3.4.1 For all inputs, S0 MUST respect the following **authority hierarchy**:

* **JSON-Schema** (layer-wide and segment-local) is the **sole authority on shapes**: object structure, field names, types, required/optional fields, enumerations and numeric profile (where specified).
* The **dataset dictionary** is the **sole authority on dataset identities and storage contracts**: dataset IDs, logical roles, schema refs, canonical path templates, partition keys and recommended writer sort.
* The **artefact registry** is the **sole authority on artefact metadata**: ownership, licence class, retention, provenance and, where applicable, additional usage notes.
* **3B.S0** is the **sole authority on which specific artefact instances** (paths + digests) are in-scope for 3B for a given `manifest_fingerprint`.

3.4.2 S0 MUST NOT:

* infer shapes or contracts from file names, directory structures, or ad-hoc conventions;
* override schema declarations from `schemas.layer1.yaml` or `schemas.3B.yaml`;
* change or reinterpret any field in the dataset dictionary or artefact registry.

3.4.3 If S0 detects a mismatch between:

* a dataset’s actual on-disk content and its registered `schema_ref` (e.g. missing columns, wrong types, wrong partitioning), or
* a registry entry and the underlying file (e.g. digest mismatch, missing file),

S0 MUST treat this as a FATAL configuration / ingestion error and MUST NOT attempt to “fix” or adjust the catalogue on-the-fly.

---

3.5 **Division of responsibility between S0 and downstream 3B states**

3.5.1 S0’s responsibility is limited to:

* verifying upstream segment PASS gates;
* resolving and sealing the exact set of artefacts 3B is permitted to use;
* recording those artefacts in `s0_gate_receipt_3B` and `sealed_inputs_3B`.

3.5.2 S0 explicitly **does not**:

* interpret which merchants are virtual vs physical based on `mcc_channel_rules`;
* interpret or normalise CDN weights from `cdn_country_weights`;
* derive or validate settlement coordinates or edge node positions;
* open or emit any RNG envelopes or `cdn_edge_pick` events;
* construct any 3B plan or egress datasets (e.g. `virtual_settlement`, `edge_catalogue`, `cdn_alias`).

3.5.3 Downstream 3B states (S1–S5) are responsible for **data-plane semantics**, including:

* merchant virtual classification;
* creation of virtual settlement nodes;
* generation of CDN edge catalogues, alias tables and any per-merchant universe hashes for virtual edges;
* emission and accounting of `cdn_edge_pick` RNG events;
* construction of 3B’s own validation bundle and `_passed.flag`.

They MUST, however, treat `s0_gate_receipt_3B` and `sealed_inputs_3B` as the **only legitimate source** of “what exists” for 3B and MUST NOT reach outside that sealed universe.

---

## 4. Outputs (bundle & PASS flag) & identity *(Binding)*

4.1 **State-local outputs (S0 artefacts)**

4.1.1 S0 SHALL emit exactly two artefacts for each successful execution at a given `manifest_fingerprint`:

* a **gate receipt**: `s0_gate_receipt_3B`, and
* a **sealed-inputs inventory**: `sealed_inputs_3B`.

4.1.2 The **gate receipt** MUST be written as a single JSON document at a fingerprint-only location:

* Path pattern (normative):
  `data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json`
* Schema reference (normative):
  `schemas.3B.yaml#/validation/s0_gate_receipt_3B`.

4.1.3 The **sealed-inputs inventory** MUST be written as a single-columnar dataset (e.g. Parquet) at a fingerprint-only location:

* Path pattern (normative):
  `data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet`
* Schema reference (normative):
  `schemas.3B.yaml#/validation/sealed_inputs_3B`.

4.1.4 Both outputs MUST be partitioned **only** by `fingerprint={manifest_fingerprint}`. They MUST NOT introduce `seed` or `parameter_hash` as partition keys.

---

4.2 **Structure and required fields of `s0_gate_receipt_3B`**

4.2.1 At minimum, `s0_gate_receipt_3B` MUST include the following identity and governance fields:

* `segment_id` (constant string: `"3B"`),
* `state_id` (constant string: `"S0"`),
* `seed`,
* `parameter_hash`,
* `manifest_fingerprint`,
* `run_id` (if Layer-1 defines run IDs at the segment or subsegment level),
* `verified_at_utc` (UTC timestamp at which upstream gates were last verified).

4.2.2 The receipt MUST also include structured references to upstream gates:

* `upstream_gates.segment_1A`,
* `upstream_gates.segment_1B`,
* `upstream_gates.segment_2A`,
* `upstream_gates.segment_3A`,

each of which MUST contain at least:

* `bundle_path` (relative or absolute path to the upstream validation bundle),
* `flag_path` (path to the upstream `_passed.flag` artefact),
* `sha256_hex` (the recomputed bundle digest),
* `status` (enumeration: `"PASS"` or `"FAIL"`).

4.2.3 The receipt MUST include a **catalogue resolution block**, for example:

* `catalogue_versions.schemas_3B`,
* `catalogue_versions.dataset_dictionary_3B`,
* `catalogue_versions.artefact_registry_3B`,

with version identifiers sufficient to reconstruct which schema/dictionary/registry triplet was in effect when S0 executed.

4.2.4 The receipt MUST include a **summary of sealed inputs**, such as:

* `sealed_input_count_total`,
* `sealed_input_count_by_kind` (e.g. `{dataset, policy, external, rng_profile}`),
* `sealed_inputs_digest` (see 4.4.3).

This summary serves as a compact fingerprint of `sealed_inputs_3B` and MUST be reproducible from that dataset alone.

---

4.3 **Structure and required fields of `sealed_inputs_3B`**

4.3.1 Each row in `sealed_inputs_3B` MUST correspond to exactly one sealed artefact and MUST include at least:

* `owner_segment` — segment that “owns” the artefact’s ingest/validation (e.g. `"1B"`, `"2A"`, `"3A"`, `"3B"`),
* `artefact_kind` — enumeration (e.g. `"dataset"`, `"policy"`, `"schema"`, `"rng_profile"`, `"external"`),
* `logical_id` — stable ID defined in the relevant dataset dictionary or artefact registry,
* `path` — concrete resolved path (including partition tokens where applicable),
* `schema_ref` — JSON-Schema anchor (nullable for non-schema’d artefacts),
* `sha256_hex` — SHA-256 digest of the artefact bytes,
* `role` — short string describing how 3B is expected to use the artefact (e.g. `"virtual_classification_rules"`, `"cdn_country_weights"`),
* `license_class` — value taken from the artefact registry (e.g. `"internal"`, `"3rd_party_commercial"`, `"open_data"`).

4.3.2 The combination `(owner_segment, artefact_kind, logical_id, path)` MUST be unique within a given `sealed_inputs_3B` dataset for one `manifest_fingerprint`.

4.3.3 Rows in `sealed_inputs_3B` MUST be written in a **stable, deterministic order**, lexicographically sorted by:

1. `owner_segment`,
2. `artefact_kind`,
3. `logical_id`,
4. `path`.

This ordering requirement is binding: any change to this ordering law is a breaking change to the 3B.S0 spec.

4.3.4 Downstream 3B states MUST be able to reconstruct, from `sealed_inputs_3B` alone, which artefacts they are permitted to read and the exact digests they MUST validate against. S0 MUST NOT rely on out-of-band lists or conventions.

---

4.4 **Relationship to the 3B validation bundle & PASS flag**

4.4.1 S0 itself does **not** emit the 3B segment-level validation bundle or `_passed.flag`. Those artefacts are owned by the terminal 3B validation state (e.g. S5 or S7, depending on the final 3B design).

4.4.2 However, S0’s outputs are **mandatory members** of the future 3B validation bundle:

* the bundle index for 3B (e.g. `schemas.layer1.yaml#/validation/validation_bundle_index_3B`) MUST include entries for:

  * `s0_gate_receipt_3B`, and
  * `sealed_inputs_3B`,

with their paths and `sha256_hex` computed as part of the 3B validation process.

4.4.3 To support this, S0 SHOULD (and the 3B validation state MUST) be able to compute:

* `gate_receipt_sha256` — SHA-256 digest of `s0_gate_receipt_3B.json` bytes,
* `sealed_inputs_sha256` — SHA-256 digest of the serialized `sealed_inputs_3B` dataset (bundle-level definition of “bytes” MUST follow the layer-wide convention for validation bundles).

These digests MAY be recorded in `s0_gate_receipt_3B` as informative fields, but their authoritative use is in the 3B validation bundle and `_passed.flag`.

4.4.4 The 3B validation bundle and `_passed.flag` MUST follow the layer-wide **HashGate law**:

* the bundle index lists all included files (including S0 artefacts) with `{path, sha256_hex}`,
* paths are relative, ASCII-lex sortable, and `_passed.flag` is excluded from the index,
* `_passed.flag` contains exactly one line:
  `sha256_hex = <bundle_digest>`,

where `<bundle_digest>` is SHA-256 over the concatenation of bytes of all indexed files in ASCII-lex path order.

4.4.5 S0 MUST NOT attempt to read `_passed.flag`. By definition, `_passed.flag` cannot exist yet when S0 runs. Any attempt to gate S0 on 3B’s own PASS flag is a logic error.

---

4.5 **Identity invariants and idempotence**

4.5.1 S0 MUST ensure that `s0_gate_receipt_3B` and `sealed_inputs_3B` embed identity fields that are consistent with the enclosing run:

* `seed` and `parameter_hash` MUST match the values used by the engine to invoke S0,
* `manifest_fingerprint` MUST match the enclosing Layer-1 manifest fingerprint,
* if `run_id` is present, it MUST obey the layer-wide definition (e.g. derived from `segment_id`, `manifest_fingerprint`, `seed`, and a monotone process counter).

4.5.2 S0 MUST be **idempotent** with respect to `{seed, parameter_hash, manifest_fingerprint}`:

* If `s0_gate_receipt_3B` and `sealed_inputs_3B` already exist for a given `manifest_fingerprint`, S0 MAY:

  * verify that their contents are byte-identical to the freshly computed versions, and
  * return success without rewriting;
* If the existing files differ from the freshly computed versions, S0 MUST treat this as a FATAL inconsistency and MUST NOT overwrite them silently.

4.5.3 The engine MUST write `s0_gate_receipt_3B` and `sealed_inputs_3B` using an **atomic write** pattern (e.g. write to a temporary path then move):

* there MUST be no observable state in which one of the two artefacts is present for a fingerprint while the other is missing;
* there MUST be no observable state in which either artefact is present but contains a partially written or schema-invalid payload.

4.5.4 Any downstream 3B state that observes:

* missing `s0_gate_receipt_3B` or `sealed_inputs_3B` for a fingerprint that is supposed to have run S0, or
* schema-invalid or self-inconsistent contents in either artefact,

MUST treat this as an S0 failure and MUST NOT proceed with data-plane work for that fingerprint.

---

4.6 **Interaction with run-report and cross-segment identity**

4.6.1 S0 SHOULD expose, in `s0_gate_receipt_3B`, a minimal **run-report identity block**, e.g.:

* `run_report_ref.segment_id = "3B"`,
* `run_report_ref.state_id = "S0"`,
* `run_report_ref.manifest_fingerprint`,
* `run_report_ref.seed`,
* `run_report_ref.parameter_hash`,
* `run_report_ref.gate_receipt_sha256`,
* `run_report_ref.sealed_inputs_sha256`.

4.6.2 The Layer-1 run-report harness MAY use this block to link 3B.S0’s outputs into a global run overview for the manifest. This section is informative only; the **binding** identity requirements are those in 4.2, 4.3 and 4.5.

4.6.3 In case of future changes to the 3B validation bundle schema (`validation_bundle_index_3B` / `passed_flag_3B`), S0 MUST remain backward compatible as long as:

* its paths and partitioning remain as specified above;
* its core identity fields and sealed-inputs layout remain unchanged;
* any new optional fields in `s0_gate_receipt_3B` or `sealed_inputs_3B` are added in a way that does not break consumers that only understand the previous schema version.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

5.1 **Gate receipt dataset — `s0_gate_receipt_3B`**

5.1.1 The dataset **`s0_gate_receipt_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with:

* `dataset_id: s0_gate_receipt_3B` (or equivalent stable ID),
* `schema_ref: schemas.3B.yaml#/validation/s0_gate_receipt_3B`,
* `path_template: data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json`,
* `partition_keys: ["fingerprint"]`,
* `writer_sort: []` (single JSON document per fingerprint).

5.1.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* reference the same `dataset_id` / `schema_ref`,
* declare `manifest_key: "mlr.3B.s0_gate_receipt_3B"` (or equivalent),
* set `owner_segment: "3B"`,
* set `type: "dataset"`,
* list upstream dependencies on the validation bundles for 1A, 1B, 2A and 3A.

5.1.3 `schemas.3B.yaml#/validation/s0_gate_receipt_3B` MUST define `s0_gate_receipt_3B` as a JSON object with at least:

* identity fields: `segment_id`, `state_id`, `seed`, `parameter_hash`, `manifest_fingerprint`, optional `run_id`, `verified_at_utc`;
* `upstream_gates`: object with required properties for segments `{ "1A", "1B", "2A", "3A" }`, each of which is an object containing `{bundle_path, flag_path, sha256_hex, status}` with `status ∈ {"PASS"}` for a successful gate;
* `catalogue_versions`: object with at least keys `schemas_3B`, `dataset_dictionary_3B`, `artefact_registry_3B`;
* `sealed_input_count_total` and `sealed_input_count_by_kind` (object keyed by `artefact_kind`);
* OPTIONAL digests such as `sealed_inputs_sha256` and `gate_receipt_sha256`.

5.1.4 The schema MUST fix:

* `segment_id` enum to `"3B"` and `state_id` enum to `"S0"`;
* `verified_at_utc` as a `rfc3339_micros` timestamp via `schemas.layer1.yaml#/time/rfc3339_micros` (or equivalent anchor);
* all SHA-256 digests as `hex64` (or `hex256` if that anchor exists) as defined in `schemas.layer1.yaml`.

5.1.5 Any change to the shape of `s0_gate_receipt_3B` that:

* removes a required field,
* renames a field, or
* changes its type or semantics,

MUST be treated as a **breaking change** and MUST be accompanied by a major version bump for `schemas.3B.yaml` and a corresponding update to the dataset dictionary and artefact registry.

---

5.2 **Sealed-inputs dataset — `sealed_inputs_3B`**

5.2.1 The dataset **`sealed_inputs_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with:

* `dataset_id: sealed_inputs_3B`,
* `schema_ref: schemas.3B.yaml#/validation/sealed_inputs_3B`,
* `path_template: data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet`,
* `partition_keys: ["fingerprint"]`,
* `writer_sort: ["owner_segment", "artefact_kind", "logical_id", "path"]`.

5.2.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* reference the same `dataset_id` / `schema_ref`,
* declare `manifest_key: "mlr.3B.sealed_inputs_3B"` (or equivalent),
* set `owner_segment: "3B"`,
* set `type: "dataset"`.

5.2.3 `schemas.3B.yaml#/validation/sealed_inputs_3B` MUST define `sealed_inputs_3B` as a table-shaped dataset with one row per sealed artefact. Required columns:

* `owner_segment` — string, typically `"1A"`, `"1B"`, `"2A"`, `"3A"` or `"3B"`, with closed enum if desired;
* `artefact_kind` — enum, e.g. `{"dataset","policy","schema","rng_profile","external"}`;
* `logical_id` — string identifier from the relevant dataset dictionary / artefact registry;
* `path` — string, absolute or root-relative path, including any partition tokens;
* `schema_ref` — string, nullable for artefacts without JSON-Schema (e.g. some binaries);
* `sha256_hex` — digest as a fixed-length lowercase hex string;
* `role` — short free-text string or enum describing 3B’s usage (e.g. `"virtual_classification_rules"`, `"cdn_country_weights"`);
* `license_class` — enum as defined in the artefact registry (e.g. `"internal"`, `"3rd_party_commercial"`, `"open_data"`).

5.2.4 The schema MUST enforce that the composite key `(owner_segment, artefact_kind, logical_id, path)` is unique per `fingerprint`, either via explicit primary-key semantics or via an acceptance criterion in the 3B validation state.

5.2.5 Any additional columns (e.g. `notes`, `shared_with_segment`, `optional_flag`) MUST be declared optional in the schema and MUST NOT change the meaning of existing required fields.

---

5.3 **Links to upstream dataset shapes and anchors**

5.3.1 For all upstream datasets that S0 touches (metadata-only), the **authoritative schema anchors** remain those defined in their originating segment schemas, for example:

* `outlet_catalogue` — `schemas.1A.yaml#/egress/outlet_catalogue`;
* `site_locations` — `schemas.1B.yaml#/egress/site_locations`;
* `site_timezones` — `schemas.2A.yaml#/egress/site_timezones`;
* `tz_timetable_cache` — `schemas.2A.yaml#/cache/tz_timetable_cache`;
* `zone_alloc` — `schemas.3A.yaml#/egress/zone_alloc`;
* `zone_alloc_universe_hash` — `schemas.3A.yaml#/validation/zone_alloc_universe_hash`.

5.3.2 `dataset_dictionary.layer1.3B.yaml` MUST reference these upstream schemas via `schema_ref` when describing cross-segment inputs that 3B is permitted to read, even though S0 itself does not read their rows.

5.3.3 S0 MUST validate that any upstream dataset it seals has:

* the `schema_ref` declared in its own segment’s dataset dictionary, and
* the partition keys and path shape declared there (e.g. `seed={seed}, fingerprint={manifest_fingerprint}` for per-run egress; `fingerprint={manifest_fingerprint}` only for global caches and universe hashes).

S0 MUST NOT substitute or guess schema anchors.

---

5.4 **Layer-wide RNG and validation schemas**

5.4.1 Although S0 is RNG-free, it MUST still rely on the layer-wide RNG and validation schemas to validate its environment:

* `schemas.layer1.yaml#/rng/core/rng_envelope` — canonical envelope for all RNG events;
* `schemas.layer1.yaml#/rng/events/cdn_edge_pick` — payload schema for the virtual edge-pick events used later in 3B;
* `schemas.layer1.yaml#/validation/parameter_hash_resolved` and `#/validation/manifest_fingerprint_resolved` — shapes for identity objects in the run harness.

5.4.2 `s0_gate_receipt_3B` MAY embed subdocuments conforming to these layer-wide validation schemas (e.g. an embedded `parameter_hash_resolved` block), in which case:

* `schemas.3B.yaml#/validation/s0_gate_receipt_3B` MUST reference the layer-wide definitions via `$ref`;
* S0 MUST validate those blocks against the layer-wide schema during write.

5.4.3 S0 MUST treat the Layer-1 bundle and flag schemas—`schemas.layer1.yaml#/validation/validation_bundle_index_3B` and `#/validation/passed_flag_3B`—as the **external authority** for 3B’s segment-level validation. S0 MUST NOT define its own bundle or flag structure; it only ensures that its outputs can be consumed by those schemas (and any future revisions of them governed at Layer-1).

---

5.5 **Catalogue links and discoverability**

5.5.1 All datasets and artefacts that S0 writes or seals MUST be discoverable via the 3B dataset dictionary and artefact registry. In particular:

* `s0_gate_receipt_3B` and `sealed_inputs_3B` MUST have entries in both the dictionary and registry, with consistent IDs and schema refs;
* every artefact row in `sealed_inputs_3B.logical_id` MUST correspond to a real logical artefact in some dictionary or registry (1A–3B).

5.5.2 The engine MUST NOT hard-code S0 paths. It MUST always:

* look up `s0_gate_receipt_3B` and `sealed_inputs_3B` via `dataset_dictionary.layer1.3B.yaml`, using the declared `path_template` and `partition_keys`, and
* look up upstream validation bundles and egress datasets via their own dictionaries/registries.

5.5.3 The 3B dataset dictionary SHOULD annotate `s0_gate_receipt_3B` and `sealed_inputs_3B` with:

* `lifecycle_phase: "alpha" | "beta" | "stable"` as appropriate,
* `egress_role: "control_plane"` (or equivalent) to make clear that these are control-plane, not data-plane, outputs.

5.5.4 Any change to the catalogue entries for `s0_gate_receipt_3B` or `sealed_inputs_3B` that affects:

* `schema_ref`,
* `path_template`,
* `partition_keys`, or
* `writer_sort`,

MUST be treated as a breaking change to the 3B.S0 contract and MUST be accompanied by a coordinated update to:

* `schemas.3B.yaml`,
* `dataset_dictionary.layer1.3B.yaml`,
* `artefact_registry_3B.yaml`, and
* any 3B validation bundle schemas that reference these artefacts.

---

5.6 **Non-normative cross-reference (informative)**

5.6.1 For operator tooling and documentation (non-binding), it is RECOMMENDED that:

* `s0_gate_receipt_3B` and `sealed_inputs_3B` be listed together in a “3B control-plane” section of any generated catalogue or run-report documentation;
* the logical IDs used in `sealed_inputs_3B.logical_id` match exactly the IDs used in human-facing documentation, to avoid confusion between control-plane names and physical paths.

5.6.2 In case of any discrepancy between this section and the JSON-Schema definitions, **JSON-Schema and the dataset dictionary SHALL take precedence**, and this section MUST be updated accordingly.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

6.1 **Algorithm overview**

6.1.1 S0 SHALL execute as a **pure, deterministic, RNG-free algorithm** composed of the following logical phases:

* **Phase A — Identity & governance check**
  Validate `{seed, parameter_hash, manifest_fingerprint}` and the active Layer-1 governance / RNG profile.

* **Phase B — Upstream gate verification**
  Verify that 1A, 1B, 2A and 3A have each emitted a valid validation bundle and PASS flag for `manifest_fingerprint`.

* **Phase C — Catalogue resolution**
  Load and sanity-check the 3B schemas, dataset dictionary and artefact registry, and resolve all logical IDs that 3B expects to use.

* **Phase D — Sealed input enumeration**
  Enumerate the exact set of artefacts (datasets, policies, schemas, RNG profiles, external assets) to be sealed, resolving paths and computing digests.

* **Phase E — Output construction & atomic write**
  Construct `s0_gate_receipt_3B` and `sealed_inputs_3B` from the enumerated artefacts, and write both atomically under `fingerprint={manifest_fingerprint}`.

6.1.2 S0 MUST NOT:

* open or advance any Philox RNG stream;
* emit any RNG event (including `cdn_edge_pick`);
* read any data-plane rows from upstream datasets;
* depend on wall-clock time for any decision other than stamping `verified_at_utc` in the gate receipt.

---

6.2 **Phase A — Identity & governance check**

6.2.1 On entry, S0 SHALL be provided with:

* `seed` (scalar, integer type as per Layer-1 convention),
* `parameter_hash` (binary/string, as defined in the Layer-1 hashing spec),
* `manifest_fingerprint` (binary/string, as defined in the Layer-1 hashing spec).

6.2.2 S0 MUST verify, via a Layer-1 identity utility or equivalent, that:

* `parameter_hash` is a valid hash of the current governed 3B parameter set;
* `manifest_fingerprint` is consistent with the run’s manifest description (i.e. it matches the enclosing engine’s view of the manifest for this run).

6.2.3 S0 MUST load the Layer-1 governance block from `schemas.layer1.yaml` and assert:

* that the **numeric policy profile** in effect (e.g. rounding mode, subnormal handling) matches the profile declared in `schemas.layer1.yaml#/governance/numeric_policy_profile`;
* that the configured RNG algorithm and envelope shape match `schemas.layer1.yaml#/rng/core/rng_envelope` and associated RNG configuration, even though S0 will not open any streams.

6.2.4 If any identity or governance check in 6.2.2–6.2.3 fails, S0 MUST abort with a FATAL configuration error and MUST NOT proceed to Phase B.

---

6.3 **Phase B — Upstream gate verification**

6.3.1 For each upstream segment `seg ∈ {1A, 1B, 2A, 3A}`, S0 MUST:

1. Use the segment’s dataset dictionary and artefact registry to resolve:

   * `validation_bundle_seg@fingerprint={manifest_fingerprint}`, and
   * `validation_passed_flag_<SEG>@fingerprint={manifest_fingerprint}` (file `_passed.flag` for each upstream segment).

2. Open `validation_passed_flag_<SEG>` and parse the expected bundle digest (e.g. `sha256_hex = <digest>`).

3. Call a shared **HashGate** routine with the bundle root to:

   * locate and parse the segment’s `index.json` (or equivalent index) according to that segment’s spec,
   * verify each indexed file’s `sha256_hex` matches the actual file bytes,
   * recompute the **bundle digest** from the index and file contents according to the segment’s bundle law.

4. Compare the recomputed digest with the value recorded in `validation_passed_flag_<SEG>`.

6.3.2 If any of the following holds for a segment `seg`, S0 MUST mark `upstream_gates.segment_seg.status = "FAIL"` and MUST abort the run:

* the validation bundle or PASS flag cannot be resolved;
* the PASS flag cannot be parsed;
* the recomputed digest does not equal the value recorded in the PASS flag;
* the segment’s bundle fails its own internal index or checksum validation.

6.3.3 S0 MUST construct `upstream_gates.segment_seg` entries for each `seg ∈ {1A,1B,2A,3A}` with:

* `bundle_path` — a canonical path to the validation bundle directory;
* `flag_path` — the path to the PASS flag artefact;
* `sha256_hex` — the recomputed bundle digest;
* `status` — `"PASS"` (only if all checks above succeeded).

6.3.4 S0 MUST set `verified_at_utc` in `s0_gate_receipt_3B` to the UTC timestamp of the last successful upstream gate verification in Phase B. This field is informational only and MUST NOT influence any deterministic decisions.

---

6.4 **Phase C — Catalogue resolution**

6.4.1 S0 MUST load:

* `schemas.layer1.yaml`,
* `schemas.ingress.layer1.yaml`,
* `schemas.3B.yaml`,
* `dataset_dictionary.layer1.3B.yaml`,
* `artefact_registry_3B.yaml`.

6.4.2 Using explicit version metadata in these artefacts (e.g. `schema_version`, `dictionary_version`, `registry_version`), S0 MUST assert that they form a **compatible triplet** for segment 3B. A compatibility matrix or explicit version matching rule SHOULD be specified out-of-band; S0 MUST enforce it.

6.4.3 S0 MUST resolve, via the dataset dictionary, all dataset IDs that 3B expects to use, including at least:

* `s0_gate_receipt_3B`,
* `sealed_inputs_3B`,
* all upstream datasets in 3.1.1 that 3B will consume (even if S0 only uses them for metadata),
* any 3B data-plane and validation datasets referenced in downstream 3B state specs (to ensure their catalog entries exist and are well-formed).

6.4.4 S0 MUST resolve, via the artefact registry, all logical artefact IDs that 3B expects to use as policies, RNG profiles or external assets, including:

* virtual classification rules,
* virtual settlement coordinates,
* CDN country weights,
* virtual validation policies,
* HRSL / population rasters,
* world polygons,
* tz-world polygons and tzdb archives (if 3B directly uses them),
* routing / CDN RNG policies (e.g. `route_rng_policy_v1`, `cdn_rng_policy_v1`, `cdn_key_digest`).

6.4.5 If any expected dataset ID or logical artefact ID is missing, has an invalid or unknown `schema_ref`, or is inconsistent between dictionary and registry, S0 MUST abort with a FATAL catalogue-resolution error and MUST NOT proceed to Phase D.

---

6.5 **Phase D — Sealed input enumeration**

6.5.1 S0 MUST construct an in-memory collection **`SEALED`** of artefacts to be recorded in `sealed_inputs_3B`. `SEALED` SHALL contain at least:

* all upstream validation bundles and PASS flags for 1A, 1B, 2A, 3A;
* all upstream egress datasets 3B will read (as per 2.4.1) — recorded as dataset artefacts, even though S0 will not read their rows;
* all virtual / CDN policies, geospatial assets and RNG profiles listed in 2.5.1–2.5.3;
* any 3B-local schemas, policies or RNG profiles prescribed by downstream 3B state specs (even if they are not used by S0 directly).

6.5.2 For each artefact `a ∈ SEALED`, S0 MUST:

1. Use the dataset dictionary / artefact registry to resolve its **logical ID** into:

   * `owner_segment`,
   * `artefact_kind` (`dataset`, `policy`, `schema`, `rng_profile`, `external`),
   * `path` (including partition tokens where applicable),
   * `schema_ref` (nullable for non-schema’d assets),
   * `license_class`.

2. Attempt to open `path` for read and confirm:

   * the file or dataset exists;
   * where applicable, the dataset structure is compatible with `schema_ref` (columns and partition keys present; the engine MAY use a “schema-only” read for this).

3. Compute a SHA-256 digest over the artefact’s bytes:

   * For file-based artefacts: read the file as a raw byte stream and apply SHA-256;
   * For partitioned datasets: apply whatever “bundle digest” convention is mandated by Layer-1 for dataset digests (e.g. hash over concatenation of file digests, in lexicographic file-path order).

4. Construct a candidate `sealed_inputs_3B` row with fields:

   * `owner_segment`,
   * `artefact_kind`,
   * `logical_id`,
   * `path`,
   * `schema_ref`,
   * `sha256_hex`,
   * `role` (derived from role metadata in the registry, or a fixed vocabulary wired into the 3B spec),
   * `license_class`.

6.5.3 S0 MUST ensure there are no duplicate `(owner_segment, artefact_kind, logical_id, path)` tuples in `SEALED`. If duplicates are discovered (e.g. two registry entries pointing to the same path), S0 MUST either:

* treat this as a configuration error and abort, or
* collapse duplicates into a single row with a clearly defined precedence rule (this MUST be documented if allowed).

6.5.4 Once `SEALED` is fully populated, S0 MUST:

* sort the rows using the stable ordering defined in §5.2.3 (by `owner_segment`, `artefact_kind`, `logical_id`, `path`);
* compute:

  * `sealed_input_count_total = |SEALED|`,
  * `sealed_input_count_by_kind` = count of rows per `artefact_kind`;
* optionally compute `sealed_inputs_sha256` = SHA-256 digest of the serialized `sealed_inputs_3B` representation (this is authoritative only once written, but S0 MAY pre-compute it for embedding into the gate receipt).

---

6.6 **Phase E — Output construction & atomic write**

6.6.1 S0 MUST construct the `s0_gate_receipt_3B` object with fields populated as follows:

* Identity:

  * `segment_id = "3B"`,
  * `state_id = "S0"`,
  * `seed`, `parameter_hash`, `manifest_fingerprint`,
  * `run_id` (if present; generated by the run harness, not by S0),
  * `verified_at_utc` (from Phase B).

* Upstream gates:

  * `upstream_gates.segment_1A`, `segment_1B`, `segment_2A`, `segment_3A` as constructed in 6.3.3; all MUST have `status="PASS"` for S0 to succeed.

* Catalogue versions:

  * `catalogue_versions.schemas_3B`, `dataset_dictionary_3B`, `artefact_registry_3B` populated from the loaded catalogue metadata.

* Sealed input summary:

  * `sealed_input_count_total`,
  * `sealed_input_count_by_kind`,
  * optionally `sealed_inputs_sha256`.

* Optional digests:

  * If S0 chooses to compute `gate_receipt_sha256` over the JSON payload it is about to write, it MAY include that field as an informational value; however, the authoritative bundle digest for 3B will be computed later by the 3B validation state.

6.6.2 S0 MUST serialize `s0_gate_receipt_3B` as JSON conforming to `schemas.3B.yaml#/validation/s0_gate_receipt_3B`, using UTF-8 encoding and a deterministic field-ordering and pretty-printing strategy (or a canonical JSON writer) so that repeated runs produce byte-identical output for the same inputs.

6.6.3 S0 MUST serialize `sealed_inputs_3B` as a table dataset conforming to `schemas.3B.yaml#/validation/sealed_inputs_3B`, with:

* partition directory `fingerprint={manifest_fingerprint}`;
* rows exactly matching the sorted `SEALED` collection computed in 6.5.4;
* writer sort exactly equal to `["owner_segment","artefact_kind","logical_id","path"]`.

6.6.4 S0 MUST perform an **atomic write** of both artefacts:

1. Write `s0_gate_receipt_3B` to a temporary location under the target fingerprint (e.g. `.../tmp.s0_gate_receipt_3B.json`).
2. Write `sealed_inputs_3B` to a temporary location under the target fingerprint (e.g. `.../tmp.sealed_inputs_3B/`).
3. Move / rename both temporary artefacts into their canonical locations as a single atomic commit (or in an order where partial writes are not observable by downstream components, e.g. via directory-level rename).

6.6.5 If either write fails or the engine detects an inconsistent state (e.g. one artefact moved, the other not), S0 MUST:

* fail the run (FATAL),
* treat both outputs as invalid for that `manifest_fingerprint`, and
* require a clean re-run of S0 before any downstream 3B state may proceed.

---

6.7 **Idempotence and re-execution**

6.7.1 If S0 is invoked for a `{seed, parameter_hash, manifest_fingerprint}` for which `s0_gate_receipt_3B` and `sealed_inputs_3B` already exist:

* S0 MAY re-run Phases A–D to recompute the expected outputs;
* S0 MUST then read the existing artefacts and compare them byte-for-byte with the freshly computed versions.

6.7.2 If the existing and freshly-computed artefacts are:

* **byte-identical**: S0 MAY return success without rewriting (idempotent no-op);
* **different**: S0 MUST treat this as a FATAL inconsistency (environment drift under the same fingerprint) and MUST NOT overwrite the existing artefacts.

6.7.3 S0 MUST log (via the observability hooks in §10) whether it:

* wrote new artefacts,
* validated and reused existing artefacts, or
* failed due to inconsistency.

---

6.8 **RNG and non-determinism guardrails**

6.8.1 S0 MUST NOT call any APIs or system functions that introduce non-determinism into:

* the set or ordering of sealed artefacts,
* the content of `s0_gate_receipt_3B`, or
* the content of `sealed_inputs_3B`.

This includes (non-exhaustively) calls that depend on:

* wall-clock time (except for stamping `verified_at_utc`),
* process IDs or hostnames used for any decision logic,
* non-deterministic filesystem iteration orders (e.g. directory listing without sorting).

6.8.2 When enumerating artefacts from catalogues or directories, S0 MUST explicitly sort:

* dictionary/registry entries, if used as a source of artefact IDs;
* dataset file paths, before computing any dataset-level digests;
* the final `SEALED` list, as specified in 6.5.4.

6.8.3 Any call to an RNG API from within S0 (including for testing) is prohibited. If an RNG envelope is accidentally emitted under 3B.S0, this MUST be treated as a bug and corrected; S0 MUST remain RNG-free by design.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

7.1 **Identity model**

7.1.1 For the purpose of 3B.S0, the **canonical identity triple** for a run is:

* `seed`,
* `parameter_hash`,
* `manifest_fingerprint`.

These values MUST be identical to those used by the enclosing Layer-1 run harness for the 3B subsegment.

7.1.2 The **primary identity key** of S0’s outputs on disk is `manifest_fingerprint`. There MUST be at most one pair of artefacts:

* `s0_gate_receipt_3B`,
* `sealed_inputs_3B`

for any given `manifest_fingerprint` in the storage namespace.

7.1.3 Within `s0_gate_receipt_3B`, S0 MUST embed the full identity triple:

* `segment_id = "3B"`,
* `state_id = "S0"`,
* `seed`,
* `parameter_hash`,
* `manifest_fingerprint`,
* optional `run_id`.

These fields MUST be considered **authoritative** identity for downstream 3B states.

7.1.4 For a given `manifest_fingerprint`, S0 MUST enforce that all of the following are true:

* there is at most one recorded `seed` value in `s0_gate_receipt_3B`;
* there is at most one recorded `parameter_hash` value in `s0_gate_receipt_3B`;
* downstream 3B states that rely on `seed` and `parameter_hash` MUST use exactly the values recorded in `s0_gate_receipt_3B`.

7.1.5 If the engine attempts to invoke 3B.S0 for the same `manifest_fingerprint` with a different `(seed, parameter_hash)` pair than the one already recorded in `s0_gate_receipt_3B`, S0 MUST treat this as a FATAL identity conflict and MUST NOT overwrite the existing artefacts (see §6.7).

---

7.2 **Partition law**

7.2.1 Both S0 outputs are **fingerprint-partitioned only**:

* `s0_gate_receipt_3B` MUST live at
  `data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json`.
* `sealed_inputs_3B` MUST live at
  `data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet`.

No other partition keys (e.g. `seed`, `parameter_hash`, `run_id`) MAY appear in the on-disk path for these datasets.

7.2.2 Inside `sealed_inputs_3B`, the schema DOES NOT require a `seed` or `parameter_hash` column. Instead:

* identities such as `seed` and `parameter_hash` are expressed via the **paths and logical IDs** of the sealed artefacts (e.g. upstream datasets that include `seed={seed}` in their own paths);
* the association between `seed` / `parameter_hash` and `manifest_fingerprint` is recorded in `s0_gate_receipt_3B` and in the upstream validation bundles.

7.2.3 S0 MUST ensure that for a given `manifest_fingerprint`, the set of rows in `sealed_inputs_3B` is **self-contained** and sufficient to reconstruct all artefact identities without any additional partitioning context.

7.2.4 Any downstream 3B state that materialises per-seed outputs MUST:

* obtain `seed` and `parameter_hash` from `s0_gate_receipt_3B` (or from the enclosing run harness),
* respect the **partition law of upstream datasets** as declared in their own dictionaries (e.g. `seed={seed}, fingerprint={manifest_fingerprint}` for 1B/2A/3A egress).

S0 MUST NOT redefine or shadow upstream partition laws.

---

7.3 **Ordering within datasets and documents**

7.3.1 `sealed_inputs_3B` MUST be written with a **stable, deterministic writer order**:

* primary sort: `owner_segment` (ascending, e.g. `"1A" < "1B" < "2A" < "3A" < "3B"`),
* secondary sort: `artefact_kind`,
* tertiary sort: `logical_id`,
* quaternary sort: `path`.

This ordering MUST be applied before writing, and any re-serialization of the dataset MUST preserve this sort (unless and until a new major spec version changes it).

7.3.2 `s0_gate_receipt_3B` MUST be serialized using a **deterministic JSON encoding**. At minimum:

* object members MUST be emitted in a fixed field order as defined in `schemas.3B.yaml#/validation/s0_gate_receipt_3B` (e.g. identity block first, then `upstream_gates`, `catalogue_versions`, `sealed_input_count_*`, optional digests);
* any arrays contained in the receipt (if introduced in future versions) MUST have a defined sort order that is independent of ambient runtime factors (e.g. sorted list of segments, not hash-map iteration order).

7.3.3 When computing any digest that depends on ordering (e.g. `sealed_inputs_sha256` or a future 3B bundle digest), S0 and the 3B validation state MUST rely on:

* the row ordering defined in 7.3.1 for table-shaped datasets;
* ASCII-lexicographic ordering for any lists of paths (e.g. when building dataset-level bundle digests).

7.3.4 No part of 3B.S0 MAY rely on filesystem directory iteration order, registry iteration order, or hash-map iteration order. All such sources MUST be explicitly sorted before use.

---

7.4 **Merge discipline, immutability and re-runs**

7.4.1 S0 outputs (`s0_gate_receipt_3B`, `sealed_inputs_3B`) are **logically immutable** for a given `manifest_fingerprint`. Once written:

* they MUST NOT be mutated in place;
* any attempt to regenerate them for the same `manifest_fingerprint` MUST follow the idempotence and conflict rules in §6.7.

7.4.2 If a later S0 run recomputes a different set of sealed inputs for the same `manifest_fingerprint` (e.g. due to catalogue changes, added policies, or changed upstream digests), this indicates that the environment associated with that fingerprint has changed. The engine MUST treat this as:

* either a signal that a **new manifest_fingerprint** should have been computed (i.e. the manifest changed and the run should be re-planned), or
* a configuration error (e.g. manual modification of artefacts without re-hashing the manifest).

Under no circumstances MAY S0 silently merge or “incrementally update” `sealed_inputs_3B` for an existing fingerprint.

7.4.3 Downstream 3B states MUST treat `s0_gate_receipt_3B` and `sealed_inputs_3B` as **read-only control-plane inputs**:

* they MUST NOT attempt to append rows, rewrite fields or mutate JSON documents;
* any per-run or per-state metadata they need MUST be stored in their own segment-local datasets.

7.4.4 When upgrading 3B to a new version (schemas/dictionary/registry), the merge discipline is:

* existing fingerprints that were produced under an older 3B schema MAY continue to be read by tools that understand that version;
* new runs using the updated 3B schema MUST produce new `s0_gate_receipt_3B` and `sealed_inputs_3B` artefacts whose shapes match the new schema version;
* cross-version compatibility handling (e.g. transforming old receipts into new shape) MUST occur in tooling or orchestration layers, not by mutating historical S0 outputs.

---

7.5 **Cross-segment join and reference discipline**

7.5.1 S0 MUST respect the **identity join rules** established by upstream segments:

* `outlet_catalogue`, `site_locations`, `site_timezones`, and `zone_alloc` share merchant- and country-level keys (`merchant_id`, `legal_country_iso`, and segment-specific keys like `site_order`, `tzid`);
* the correct join keys and partitioning behaviour for these datasets are defined in their own segment specs and dictionaries.

7.5.2 Although S0 does not perform joins on data rows, any downstream 3B state that performs such joins MUST:

* use the key sets defined in the upstream schemas and dictionaries;
* not introduce ad-hoc or ambiguous join keys;
* not reinterpret the meaning of `manifest_fingerprint`, `seed` or `parameter_hash` across segments.

7.5.3 `sealed_inputs_3B.logical_id` MUST be chosen such that downstream 3B states can unambiguously resolve each artefact back to its owning segment and spec. In particular:

* logical IDs for upstream datasets SHOULD match those used in their native segment dictionaries;
* logical IDs for shared artefacts (e.g. HRSL, tzdb) SHOULD be identical across segments (1B, 2A, 3B) so that cross-segment reasoning about shared assets is trivial.

7.5.4 Any future extension that introduces additional S0 outputs or modifies identity handling MUST:

* preserve the **on-disk partition law** in 7.2;
* preserve the **immutability and idempotence** rules in 7.4;
* explicitly document how new identity fields interact with existing ones, and MUST NOT overload existing fields with new semantics.

Where there is any conflict between this section and the JSON-Schema / dataset dictionary definitions, the schemas and catalogues SHALL prevail and this section MUST be updated accordingly.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

8.1 **S0 state-level PASS criteria**

8.1.1 A run of 3B.S0 for a given `{seed, parameter_hash, manifest_fingerprint}` SHALL be considered **PASS** if and only if **all** of the following conditions hold:

* **Identity & governance**
  a. `seed`, `parameter_hash`, and `manifest_fingerprint` are present and internally consistent (§6.2).
  b. The active numeric and RNG governance matches the Layer-1 definitions in `schemas.layer1.yaml` (§6.2.3).
  c. `segment_id = "3B"` and `state_id = "S0"` are correctly set in the gate receipt.

* **Upstream gates**
  d. For each of 1A, 1B, 2A and 3A, S0 successfully resolves the segment’s validation bundle and PASS flag for `manifest_fingerprint`.
  e. The recomputed bundle digest matches the value in each `_passed.flag`.
  f. `upstream_gates.segment_1A/1B/2A/3A.status` are all `"PASS"` in `s0_gate_receipt_3B`.

* **Catalogue and schema resolution**
  g. `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` are all resolved and mutually compatible (§6.4).
  h. All dataset IDs and logical artefact IDs referenced in the 3B state specs (S0–S5) exist and have well-formed entries in the dictionary/registry.

* **Sealed inputs completeness & integrity**
  i. Every **mandatory** artefact identified in §§2.4–2.5 (upstream egress, validation bundles, virtual/CDN policies, geospatial assets, RNG policies) is present in the constructed `SEALED` set and resolvable on disk.
  j. Each artefact in `SEALED` can be opened, and where a `schema_ref` is declared, its structure is compatible with the referenced schema.
  k. A SHA-256 digest can be computed for each artefact without error.
  l. The composite key `(owner_segment, artefact_kind, logical_id, path)` is unique across all rows in `sealed_inputs_3B`.
  m. `sealed_input_count_total` and `sealed_input_count_by_kind` in `s0_gate_receipt_3B` are consistent with the rows actually written to `sealed_inputs_3B`.

* **Output correctness & self-consistency**
  n. `s0_gate_receipt_3B` validates against `schemas.3B.yaml#/validation/s0_gate_receipt_3B`.
  o. `sealed_inputs_3B` validates against `schemas.3B.yaml#/validation/sealed_inputs_3B`, with correct partition (`fingerprint={manifest_fingerprint}`) and writer sort (`["owner_segment","artefact_kind","logical_id","path"]`).
  p. If `sealed_inputs_sha256` and/or `gate_receipt_sha256` are present in the gate receipt, they match the digests of the on-disk artefacts.
  q. No RNG events were emitted and no Philox streams were opened under 3B.S0 (verifiable via absence of 3B.S0 entries in `rng_audit_log` / `rng_trace_log`).

8.1.2 If any of the conditions 8.1.1(d)–(q) fails, the 3B.S0 run MUST be marked **FAIL** and MUST NOT publish `s0_gate_receipt_3B` nor `sealed_inputs_3B` at their canonical locations. Any partially written outputs MUST be treated as invalid and discarded.

---

8.2 **Mandatory vs optional sealed inputs**

8.2.1 The 3B spec SHALL distinguish between **mandatory** and **optional** sealed inputs for S0:

* **Mandatory** artefacts are those without which 3B cannot safely execute any state (e.g. upstream validation bundles, upstream egress, virtual classification rules, CDN weights, required geospatial assets, core RNG policies).
* **Optional** artefacts are those that are only needed when specific 3B features are enabled (e.g. an experimental validation policy pack).

8.2.2 Until the catalogue grows first-class metadata for this, the authoritative list of mandatory vs optional artefacts is maintained in this spec (see §§2.4–2.5) and the associated governance notes. Any change to an artefact’s status MUST be captured in those lists (and, once the dictionary/registry gain such fields, reflected there as well) so that S0 can apply the correct acceptance logic.

8.2.3 Acceptance rules:

* If a **mandatory** artefact is missing, unreadable, schema-incompatible or undigestible, S0 MUST fail (FATAL) and MUST NOT emit outputs.
* If an **optional** artefact is missing or invalid:

  * and the corresponding 3B feature is **disabled** by configuration, S0 MAY omit it from `sealed_inputs_3B` (and SHOULD record this omission in logs);
  * and the corresponding 3B feature is **enabled**, S0 MUST treat it as mandatory and fail if it cannot be sealed.

8.2.4 S0 MUST NOT silently “downgrade” a mandatory artefact to optional based on runtime heuristics. Any such change in status MUST be reflected in the authoritative dictionary/registry and in a version bump of the relevant contracts.

---

8.3 **Gating obligations for downstream 3B states**

8.3.1 For a given `manifest_fingerprint`, every downstream 3B state (S1–S5) MUST check, before performing any data-plane work, that:

* `s0_gate_receipt_3B` exists at the canonical path for that fingerprint;
* `sealed_inputs_3B` exists at the canonical path for that fingerprint;
* both artefacts validate against their schemas;
* the embedded `segment_id`, `state_id`, `seed`, `parameter_hash` and `manifest_fingerprint` in `s0_gate_receipt_3B` match the current run.

8.3.2 If any of these checks fails, the downstream state MUST:

* treat S0 as **not having successfully completed** for that fingerprint;
* fail fast with a “gate missing/invalid” error;
* MUST NOT attempt to re-run S0 implicitly or to access inputs that would have been sealed by S0.

8.3.3 When a downstream 3B state opens any artefact (dataset, policy, RNG profile, external file), it MUST first locate the corresponding row in `sealed_inputs_3B` and verify:

* that the artefact exists at the `path` recorded in that row;
* that the SHA-256 digest of the on-disk artefact matches `sha256_hex` in that row.

Any mismatch MUST be treated as a hardened failure in the 3B environment, and the downstream state MUST not proceed with that artefact.

8.3.4 Downstream 3B states MUST NOT read or depend on any artefact that is **not** listed in `sealed_inputs_3B` for the target `manifest_fingerprint`, even if such artefacts can be resolved via the dictionary/registry. Doing so violates the 3B closed-world assumption.

8.3.5 Where a downstream state’s spec marks a particular artefact as optional, that state MUST:

* consult `sealed_inputs_3B` to determine whether the artefact was sealed;
* follow the documented fallback behaviour if the artefact is absent;
* treat unexpected presence/absence (e.g. sealed but feature disabled) as a configuration anomaly, and log it at least at WARN level.

---

8.4 **Gating obligations with respect to upstream segments**

8.4.1 3B.S0 is responsible for enforcing upstream “No PASS → No read” obligations on behalf of the entire 3B subsegment. Therefore:

* No downstream 3B state MAY attempt to re-verify upstream validation bundles independently;
* Instead, downstream states MUST rely on the `upstream_gates` block in `s0_gate_receipt_3B` as the authoritative record that 1A, 1B, 2A and 3A have passed.

8.4.2 If a downstream 3B state observes, via `s0_gate_receipt_3B`, that any upstream `segment_seg.status != "PASS"`, it MUST:

* treat the entire 3B run for that `manifest_fingerprint` as **blocked by upstream**;
* fail fast with an upstream-gate error;
* not attempt to read any upstream egress datasets for that segment, even if they are listed in `sealed_inputs_3B` (since their validation has not been attested for this run).

8.4.3 Any change in upstream bundle law (e.g. different index shapes or hash combination rules) MUST be reflected in segment-local specs for those upstream segments. S0 MUST adapt its HashGate verification accordingly, but 3B downstream states remain insulated from those details and MUST continue to rely solely on S0’s `upstream_gates` entries.

---

8.5 **Interaction with 3B segment-level PASS and higher-level harness**

8.5.1 The S0 PASS/FAIL result is a **necessary but not sufficient** condition for the overall 3B segment PASS:

* S0 PASS is required before S1–S5 may execute;
* the final 3B segment PASS flag `_passed.flag` will be produced only by the terminal 3B validation state, after all 3B states have completed successfully.

8.5.2 The Layer-1 orchestration / run harness MUST enforce that:

* S1–S5 are not invoked for a given `manifest_fingerprint` unless S0 has completed successfully (PASS) for that fingerprint;
* any S0 failure is surfaced explicitly in run reports as a **3B gate failure**, and prevents 3B’s validation bundle from being emitted for that fingerprint.

8.5.3 If the harness supports partial runs or re-runs, it MUST ensure:

* that re-running 3B.S0 for an existing `manifest_fingerprint` respects the idempotence and conflict rules in §6.7;
* that re-running S1–S5 without re-running S0 is allowed **only** if S0 artefacts are still valid and match the current catalogues (no environment drift). Any detected drift MUST trigger a fresh S0 run or a new manifest.

8.5.4 Higher-level validation harnesses (e.g. 4A/4B) MAY treat the presence of valid `s0_gate_receipt_3B` and `sealed_inputs_3B` as evidence that:

* upstream segments 1A–3A have passed for this fingerprint;
* 3B is operating within a well-defined, sealed environment.

Such usage is informative; the binding obligations on 3B are those specified in this section and in the 3B validation state spec.

---

8.6 **Failure semantics**

8.6.1 Any violation of the binding requirements in §§8.1–8.5 MUST result in one of:

* a **hard failure** of 3B.S0 (for identity, governance, upstream gate, catalogue, sealing or output correctness issues), or
* a **hard failure** of the downstream 3B state that detected the problem (for missing/invalid S0 artefacts or digest mismatches at consumption time).

8.6.2 In all such cases, the engine MUST:

* avoid emitting or updating any 3B segment-level PASS flag;
* avoid emitting any 3B egress datasets that depend on S0;
* clearly log the failure with a canonical error code (enumerated in §9) and enough context to allow operators to diagnose whether the issue lies in upstream segments, catalogue configuration, or the 3B environment.

---

## 9. Failure modes & canonical error codes *(Binding)*

9.1 **Error model & severity**

9.1.1 3B.S0 SHALL use a **segment-local error namespace** of the form:

* `E3B_S0_<CATEGORY>_<DETAIL>`

All error codes in this section are reserved for 3B.S0 and MUST NOT be reused by other states.

9.1.2 Every S0 failure that is surfaced to logs or run-reports MUST include, at minimum:

* `segment_id = "3B"`,
* `state_id = "S0"`,
* `error_code`,
* `severity ∈ {"FATAL","WARN"}`,
* `manifest_fingerprint`,
* optional `{seed, parameter_hash}`,
* a human-readable `message` (non-normative).

9.1.3 Unless explicitly marked as `WARN`, all error codes in this section are **FATAL** for 3B.S0:

* FATAL ⇒ S0 MUST NOT publish `s0_gate_receipt_3B` nor `sealed_inputs_3B` at their canonical locations and the 3B segment MUST be considered **not gated** for that fingerprint.
* WARN ⇒ S0 MAY complete and publish outputs, but the condition SHALL be surfaced in logs / run-reports for operator attention.

---

### 9.2 Identity & governance failures

9.2.1 **E3B_S0_IDENTITY_MISSING** *(FATAL)*
Raised when one or more of `seed`, `parameter_hash`, or `manifest_fingerprint` is absent, null, or unusable at S0 entry.

* Typical triggers:

  * Run harness invoked S0 without a manifest fingerprint.
  * Parameter hash was not computed by the Layer-1 parameter pipeline.
* Remediation:

  * Fix the run harness / configuration so that the identity triple is always resolved before S0.

9.2.2 **E3B_S0_IDENTITY_INCONSISTENT** *(FATAL)*
Raised when `parameter_hash` or `manifest_fingerprint` provided to S0 disagrees with the Layer-1 identity utilities (e.g. recomputing the hash set yields a different value).

* Typical triggers:

  * Manifest or parameter set changed without recomputing `manifest_fingerprint` or `parameter_hash`.
  * Manual editing of identity artefacts.
* Remediation:

  * Rebuild the manifest and parameter hashes; re-plan the run.

9.2.3 **E3B_S0_GOVERNANCE_MISMATCH** *(FATAL)*
Raised when the active numeric / RNG governance does not match `schemas.layer1.yaml` (e.g. wrong RNG algorithm or numeric profile).

* Typical triggers:

  * Binary compiled with a different numeric profile than the one encoded in the schema.
  * Misconfiguration of the RNG engine.
* Remediation:

  * Align runtime configuration with the declared layer-wide governance; redeploy or reconfigure the engine.

---

### 9.3 Upstream gate & validation failures

9.3.1 **E3B_S0_UPSTREAM_BUNDLE_MISSING** *(FATAL)*
Raised when the validation bundle for 1A, 1B, 2A or 3A cannot be resolved for the target `manifest_fingerprint`.

* Typical triggers:

  * Upstream segment not run for this manifest.
  * Data retention / housekeeping removed the bundle prematurely.
* Remediation:

  * Rerun the missing upstream segment; fix retention policies.

9.3.2 **E3B_S0_UPSTREAM_FLAG_MISSING** *(FATAL)*
Raised when the `_passed.flag` artefact for an upstream segment cannot be resolved.

* Typical triggers:

  * Bundle written without a flag due to upstream failure.
  * Flag deleted or moved independent of its bundle.
* Remediation:

  * Rerun upstream validation; ensure bundle+flag are written atomically.

9.3.3 **E3B_S0_UPSTREAM_HASH_MISMATCH** *(FATAL)*
Raised when the recomputed bundle digest for an upstream segment does not match the digest recorded in `_passed.flag`.

* Typical triggers:

  * Bundle contents changed after the flag was written.
  * Partial or corrupted bundle.
* Remediation:

  * Treat as data corruption; rebuild the upstream bundle from scratch and re-emit the flag.

9.3.4 **E3B_S0_UPSTREAM_INDEX_INVALID** *(FATAL)*
Raised when an upstream bundle’s index (e.g. `index.json`) is missing, malformed, or fails its own internal checks (e.g. per-file hashes incorrect).

* Typical triggers:

  * Manual tampering with bundle contents.
  * Bug in upstream segment’s validation write path.
* Remediation:

  * Fix upstream segment; regenerate its validation bundle.

---

### 9.4 Catalogue / schema / registry failures

9.4.1 **E3B_S0_SCHEMA_PACK_MISMATCH** *(FATAL)*
Raised when the loaded combination of `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` is detected as incompatible (e.g. mismatched major versions, missing required schemas).

* Typical triggers:

  * Partial upgrade of schemas without synchronised dictionary/registry changes.
  * Editing one contract in isolation.
* Remediation:

  * Align schema/dictionary/registry versions; redeploy a coherent set.

9.4.2 **E3B_S0_DATASET_ID_UNKNOWN** *(FATAL)*
Raised when a dataset ID required by 3B (S0–S5) is not present in the dataset dictionary.

* Typical triggers:

  * Dataset not registered.
  * Typo in dataset ID in spec vs dictionary.
* Remediation:

  * Add / correct the dictionary entry; bump versions as appropriate.

9.4.3 **E3B_S0_ARTEFACT_ID_UNKNOWN** *(FATAL)*
Raised when a logical artefact ID required by 3B (e.g. virtual rules, CDN weights, RNG policy) is not found in the artefact registry.

* Typical triggers:

  * Policy file added without registry entry.
  * Registry stale relative to actual configuration files.
* Remediation:

  * Register the artefact with a proper logical ID and schema_ref (if any).

9.4.4 **E3B_S0_CATALOGUE_RESOLUTION_FAILED** *(FATAL)*
Raised when dictionary or registry entries exist but cannot be resolved into valid paths or partition templates (e.g. missing substitution keys, invalid template syntax).

* Typical triggers:

  * Incorrect `path_template` in dictionary.
  * Missing partition tokens (e.g. `{manifest_fingerprint}`) in the template.
* Remediation:

  * Fix catalogue templates and re-run; ensure all required tokens are present.

---

### 9.5 Sealed input enumeration & integrity failures

9.5.1 **E3B_S0_SEALED_INPUT_MISSING** *(FATAL)*
Raised when a **mandatory** artefact identified in §§2.4–2.5 cannot be found on disk at the resolved path.

* Typical triggers:

  * File not produced by upstream;
  * Manual deletion;
  * Misconfigured path in registry/dictionary.
* Remediation:

  * Produce or restore the missing artefact; fix paths if required.

9.5.2 **E3B_S0_SEALED_INPUT_OPEN_FAILED** *(FATAL)*
Raised when an artefact path is resolved but cannot be opened for read (permissions, format, or IO error).

* Typical triggers:

  * Permissions issues;
  * Wrong storage endpoint;
  * Transient IO failure not retried at correct layer.
* Remediation:

  * Fix access; re-run with reliable storage and correct credentials.

9.5.3 **E3B_S0_SEALED_INPUT_SCHEMA_MISMATCH** *(FATAL)*
Raised when a dataset artefact declares a `schema_ref`, but the actual on-disk dataset does not conform (e.g. missing columns, wrong types, wrong partitions).

* Typical triggers:

  * Upstream wrote a dataset with a different schema than the one registered.
  * Dictionary schema_ref not updated after a change.
* Remediation:

  * Bring schema, dictionary and data into alignment; regenerate the dataset if necessary.

9.5.4 **E3B_S0_SEALED_INPUT_DIGEST_FAILED** *(FATAL)*
Raised when S0 is unable to compute a SHA-256 digest for an artefact (e.g. due to read errors or inconsistent file set for a dataset-level digest).

* Typical triggers:

  * Partially written dataset (some files missing).
  * IO errors during digest computation.
* Remediation:

  * Fix storage issues; ensure artefact is fully written before S0.

9.5.5 **E3B_S0_SEALED_INPUT_DUPLICATE_KEY** *(FATAL)*
Raised when the composite key `(owner_segment, artefact_kind, logical_id, path)` is not unique within `SEALED`.

* Typical triggers:

  * Duplicate registry entries pointing to the same logical artefact and path.
  * Spec error causing the same artefact to be added more than once.
* Remediation:

  * De-duplicate registry entries or clarify logical IDs; update dictionary/registry so that S0 sees a single canonical entry.

---

### 9.6 Output construction & consistency failures

9.6.1 **E3B_S0_GATE_RECEIPT_SCHEMA_VIOLATION** *(FATAL)*
Raised when the constructed `s0_gate_receipt_3B` object fails validation against `schemas.3B.yaml#/validation/s0_gate_receipt_3B`.

* Typical triggers:

  * Missing required field (e.g. `upstream_gates.segment_2A`).
  * Wrong type (e.g. non-enum status value).
* Remediation:

  * Fix the S0 implementation to conform to schema; adjust schema only via proper versioning.

9.6.2 **E3B_S0_SEALED_INPUTS_SCHEMA_VIOLATION** *(FATAL)*
Raised when the constructed `sealed_inputs_3B` dataset fails validation against `schemas.3B.yaml#/validation/sealed_inputs_3B` (including partitioning and writer sort).

* Typical triggers:

  * Missing columns (e.g. `license_class`).
  * Incorrect partition directory or unsorted rows.
* Remediation:

  * Fix S0 write path and sorting; regenerate outputs.

9.6.3 **E3B_S0_OUTPUT_WRITE_FAILED** *(FATAL)*
Raised when S0 cannot complete the atomic write of either `s0_gate_receipt_3B` or `sealed_inputs_3B`.

* Typical triggers:

  * Storage outage or permission issues at write time.
  * Insufficient space or quota.
* Remediation:

  * Resolve storage issues; retry S0 from a clean slate.

9.6.4 **E3B_S0_OUTPUT_INCONSISTENT_REWRITE** *(FATAL)*
Raised when S0 detects that existing outputs for the same `manifest_fingerprint` differ from freshly computed outputs (§6.7).

* Typical triggers:

  * Environment change (catalogue, policies, upstream digests) without re-hashing the manifest.
  * Manual modification of S0 outputs.
* Remediation:

  * Treat as environment drift; either recompute a new manifest fingerprint or restore the original environment.

---

### 9.7 RNG & non-determinism violations

9.7.1 **E3B_S0_RNG_USED** *(FATAL)*
Raised if S0 is observed to have opened or advanced any RNG stream or emitted any RNG event (e.g. a `cdn_edge_pick` event recorded under S0).

* Typical triggers:

  * Accidental reuse of RNG utilities in S0 implementation.
  * Mis-structured code that invokes RNG-bearing helpers.
* Remediation:

  * Remove RNG usage from S0; ensure RNG utilities are only called from downstream 3B states and that tests guard against this regression.

9.7.2 **E3B_S0_NONDETERMINISTIC_ENUMERATION** *(FATAL or WARN, implementation-defined)*
Raised when S0 detects inconsistencies in sealed-inputs ordering between repeated runs with identical inputs (e.g. different ordering of `sealed_inputs_3B` rows across idempotent re-runs).

* Typical triggers:

  * Reliance on unsorted directory listings or hash-map iteration order.
  * Non-canonical JSON encoding.
* Remediation:

  * Fix enumeration and sorting logic; enforce explicit ordering as per §7.3.

For production, this SHOULD be treated as FATAL until determinism is proven.

---

### 9.8 Error reporting & propagation

9.8.1 Whenever S0 raises a FATAL error code, it MUST:

* log a structured error event containing the fields in 9.1.2;
* ensure that neither `s0_gate_receipt_3B` nor `sealed_inputs_3B` is visible at their canonical paths for the affected `manifest_fingerprint`.

9.8.2 The run harness MUST surface 3B.S0 FATAL errors as **“3B gate failure”** for the affected manifest and MUST:

* prevent downstream 3B states (S1–S5) from running for that manifest;
* avoid emitting any 3B segment-level validation bundle or `_passed.flag`.

9.8.3 Downstream 3B states that detect problems at consumption time (e.g. sealed-input digest mismatch) SHOULD re-use the same error codes where applicable (e.g. `E3B_S0_SEALED_INPUT_DIGEST_FAILED`), but MUST mark themselves as the **originating state** in logs (e.g. `state_id: "S2"`), to make clear whether the failure arose during S0 or during later use of its outputs.

9.8.4 Any new 3B.S0 failure condition introduced in future versions MUST:

* be assigned a unique `E3B_S0_...` code;
* be documented in this section with severity, responsibilities and remediation guidance;
* not overload existing codes with new, incompatible semantics.

---

## 10. Observability & run-report integration *(Binding)*

10.1 **Structured logging requirements**

10.1.1 S0 MUST emit, at minimum, the following **lifecycle log events** for each attempted run:

* a **`start`** event when S0 begins work for a given `{seed, parameter_hash, manifest_fingerprint}`, and
* a **`finish`** event when S0 either completes successfully or fails.

10.1.2 Both `start` and `finish` events MUST be structured and include at least:

* `segment_id = "3B"`,
* `state_id = "S0"`,
* `manifest_fingerprint`,
* `seed`,
* `parameter_hash`,
* `run_id` (if present),
* `event_type ∈ {"start","finish"}`,
* `ts_utc` (UTC timestamp of the log event).

10.1.3 The `finish` event MUST additionally include:

* `status ∈ {"PASS","FAIL"}`,
* `error_code` (for FAIL; `null` or omitted for PASS),
* `sealed_input_count_total` (0 on failure before enumeration),
* `sealed_input_count_by_kind` (empty or partial map on early failure),
* a boolean flag `outputs_written` indicating whether `s0_gate_receipt_3B` and `sealed_inputs_3B` were successfully written to their canonical locations.

10.1.4 If S0 raises a FATAL error, it MUST emit at least one **error log event** containing the fields defined in §9.1.2 (including `error_code`, `severity`, and a human-readable `message`).

---

10.2 **Run-report record for 3B.S0**

10.2.1 S0 MUST produce a **run-report record** for each attempted run that can be consumed by a Layer-1 run-report harness (e.g. 4A/4B). This record MAY be materialised as a dedicated dataset or as an in-memory structure passed to the run-report system.

10.2.2 The run-report record for 3B.S0 MUST include at least:

* `segment_id = "3B"`,
* `state_id = "S0"`,
* `manifest_fingerprint`,
* `seed`,
* `parameter_hash`,
* `run_id` (if present),
* `status ∈ {"PASS","FAIL"}`,
* `error_code` (for FAIL),
* `verified_at_utc` (from `s0_gate_receipt_3B`, if written),
* `sealed_input_count_total`,
* `sealed_input_count_by_kind`,
* `gate_receipt_path` (canonical path of `s0_gate_receipt_3B` if written),
* `sealed_inputs_path` (canonical path of `sealed_inputs_3B` if written).

10.2.3 Where available, the run-report record SHOULD also include:

* `gate_receipt_sha256` (if S0 or a later validation state has computed it),
* `sealed_inputs_sha256` (if computed),
* `catalogue_versions.schemas_3B`, `dataset_dictionary_3B`, `artefact_registry_3B`.

10.2.4 The run-report harness MUST be able to reconstruct, from this record alone, whether:

* S0 gated 3B successfully for this `manifest_fingerprint`, and
* all required control-plane artefacts are present and where they are located.

---

10.3 **Metrics & counters**

10.3.1 S0 MUST emit the following **metrics** for observability and SLO monitoring (names are illustrative; actual metric names MAY be adapted to the engine’s metrics framework):

* `3b_s0_runs_total{status="PASS|FAIL"}` — counter, incremented once per S0 run;
* `3b_s0_sealed_inputs_total` — gauge or histogram per run, equal to `sealed_input_count_total`;
* `3b_s0_sealed_inputs_by_kind{artefact_kind=...}` — gauge or histogram per run (mirroring `sealed_input_count_by_kind`);
* `3b_s0_duration_seconds` — latency of the S0 run, measured from `start` to `finish`;
* `3b_s0_upstream_gate_failures_total{segment="1A|1B|2A|3A"}` — counter for upstream gate failures attributed to each segment;
* `3b_s0_errors_total{error_code=...}` — counter of error occurrences per canonical error code (see §9).

10.3.2 Metrics MUST be tagged (labels or equivalent) with:

* `segment_id = "3B"`,
* `state_id = "S0"`,
* `manifest_fingerprint` (where cardinality is acceptable) OR a reduced identifier derived from it (e.g. a hash prefix),
* and, where appropriate, `artefact_kind` or `segment` (for upstream gate metrics).

10.3.3 Operators SHOULD be able to use these metrics to answer, at minimum:

* “What fraction of manifests fail at 3B.S0, and why?”
* “Which upstream segment most frequently blocks 3B gating?”
* “How many artefacts are typically sealed per 3B run, and of what kinds?”
* “Is S0 meeting its latency SLOs across production runs?”

---

10.4 **Traceability & correlation**

10.4.1 S0 MUST ensure that **correlation across logs, run-reports and datasets** is possible via the identity triple and, if used, `run_id`. In particular:

* `s0_gate_receipt_3B` MUST contain `seed`, `parameter_hash`, `manifest_fingerprint`, and OPTIONAL `run_id`;
* `sealed_inputs_3B` is keyed by `manifest_fingerprint` and uses `logical_id` and `path` to link back to upstream artefacts;
* all S0 log events MUST include `manifest_fingerprint`, and SHOULD include `seed`, `parameter_hash`, and `run_id`.

10.4.2 The combination of:

* `run-report` record,
* `s0_gate_receipt_3B`, and
* `sealed_inputs_3B`

MUST be sufficient for an operator (or an offline tool) to reconstruct **exactly which artefacts** were sealed for a given 3B run, and which upstream bundles and policies were in force.

10.4.3 In particular, given a `manifest_fingerprint`, an operator MUST be able to answer:

* “Which version of `mcc_channel_rules` did 3B use?”
* “Which `zone_alloc_universe_hash` (routing universe) was S0 pinned to?”
* “Which HRSL raster and tzdb release were sealed as inputs for 3B?”

without needing to inspect any 3B data-plane outputs.

10.4.4 If the engine supports **trace IDs** or similar cross-service correlation IDs, S0 SHOULD include such IDs in its logs and MAY embed them in `s0_gate_receipt_3B` under an optional `trace_id` field (marked as optional in the schema). This is informational and MUST NOT affect determinism.

---

10.5 **Integration with Layer-1 / 4A–4B validation harness**

10.5.1 S0’s outputs MUST be consumable by the Layer-1 top-level validation and observability harness (e.g. segments 4A / 4B) as part of the global run report for each manifest.

10.5.2 At minimum, S0 MUST make it possible for the harness to:

* detect that 3B gating has either **succeeded** or **failed** per `manifest_fingerprint`;
* surface a summary per manifest such as:

  * `3B.S0.status`,
  * `3B.S0.error_code` (if any),
  * `3B.S0.sealed_input_count_total`,
  * `3B.S0.sealed_input_count_by_kind`,
  * `3B.S0.catalogue_versions.schemas_3B/dataset_dictionary_3B/artefact_registry_3B`.

10.5.3 The harness MAY also consume `upstream_gates` from `s0_gate_receipt_3B` as a convenient summary of upstream segment health for that manifest. S0 MUST ensure that this block is complete and accurate so that higher-level tooling can safely rely on it.

10.5.4 S0 MUST NOT make assumptions about the presence or shape of the **3B segment-level validation bundle** in this state. It MUST only ensure that:

* its own outputs (`s0_gate_receipt_3B`, `sealed_inputs_3B`) are suitable members of that bundle (paths stable, digests computable), and
* all information the future 3B validation state will need from S0 is present in these artefacts.

---

10.6 **Operational diagnostics & debugability**

10.6.1 On any FATAL failure, S0 SHOULD log **diagnostic context** sufficient for an operator to triage the issue without re-running in a debugger, for example:

* for catalogue errors: the offending dataset / logical ID, dictionary entry, registry entry and resolved path;
* for upstream gate failures: the affected `segment`, the upstream bundle path, and the expected vs actual digest;
* for sealed input issues: the logical ID, path, artefact kind and a concise description of the mismatch.

10.6.2 S0 MAY expose a **“dry-run” / debug mode** (controlled entirely by configuration and outside the scope of this spec) in which:

* it performs all checks and logs the same diagnostics,
* but does not write `s0_gate_receipt_3B` or `sealed_inputs_3B`.

If such a mode exists, S0 MUST clearly distinguish `mode="dry_run"` vs `mode="normal"` in logs and MUST NOT confuse operators about gating status.

10.6.3 Any additional observability features (e.g. detailed timing breakdowns, per-artefact debug logs) are **informative** and MAY be added as long as they do not:

* change the binding fields or shapes of `s0_gate_receipt_3B` and `sealed_inputs_3B`,
* introduce non-deterministic behaviour into S0, or
* conflict with the logging and metrics requirements in this section.

Where discrepancies arise between this section and the schemas or dataset dictionary, the schemas/dictionary SHALL prevail, and this section MUST be updated accordingly.

---

## 11. Performance & scalability *(Informative)*

11.1 **Workload character**

11.1.1 3B.S0 is a **control-plane, metadata-heavy** state, not a data-plane one:

* It touches **tens to low-hundreds** of artefacts (schemas, policies, upstream bundles, egress datasets),
* But never scans or aggregates high-volume tables (no full `outlet_catalogue` / `site_locations` reads).

11.1.2 The dominant cost drivers for S0 are:

* filesystem / object-store **metadata lookups** (resolving paths, listing bundle contents),
* **hashing** of artefact bytes for SHA-256 digests,
* JSON/YAML/schema parsing and validation for a small number of configuration files.

11.1.3 CPU and memory footprint are expected to be modest for typical deployments; I/O throughput and latency (especially to remote object stores) will dominate runtime variance.

---

11.2 **Expected scale & complexity**

11.2.1 Let:

* `A` = number of artefacts in `SEALED` (datasets, policies, schemas, RNG profiles, external assets),
* `F` = total number of files across all sealed datasets and bundles.

Then:

* The **enumeration cost** is approximately `O(A + F)` (dictionary/registry lookups + directory listings).
* The **hashing cost** is `O(total_bytes(F))` (sum of file sizes), but typically bounded by:

  * upstream validation bundles (few files, moderate size), and
  * a small number of policy / config files (kB–MB scale).

11.2.2 In a representative environment, you can expect:

* `A` in the range **20–200**,
* `F` in the range **50–500**,
* total bytes hashed in the range **MBs to low GBs**, depending on bundle sizes.

11.2.3 Under these assumptions, **single-threaded** S0 should be comfortably sub-minute in typical production environments, with most of the time spent waiting on storage, not CPU.

---

11.3 **Concurrency & parallelism**

11.3.1 S0 is naturally parallelisable across artefacts for digest computation:

* SHA-256 hashing of different files can be parallelised across cores,
* but the spec does **not require** such parallelism; it is an implementation choice.

11.3.2 Implementations SHOULD be careful to:

* preserve the deterministic ordering constraints (sort before writing / digesting),
* ensure that parallel hashing does not introduce non-deterministic ordering in `sealed_inputs_3B` (e.g. via race conditions on collection insertion).

11.3.3 It is RECOMMENDED to treat S0 as a **single-task per manifest** operation, not sharded by seed or partition, to avoid unnecessary duplication of work: the sealed universe is fingerprint-scoped, not seed-scoped.

---

11.4 **I/O patterns & storage considerations**

11.4.1 Typical I/O for S0:

* **Small, random reads** of:

  * schema packs (layer and segment),
  * dictionaries and registries,
  * policy / RNG config files.
* **Sequential reads** of:

  * upstream validation bundle indices and evidence files,
  * a small number of dataset files for hash computation (if dataset-level digests are used).

11.4.2 Storage footprint of S0 outputs is negligible compared to data-plane artefacts:

* `s0_gate_receipt_3B` — single JSON document (kB–10s of kB),
* `sealed_inputs_3B` — small Parquet table, O(A) rows with a handful of columns.

11.4.3 Because S0 outputs are fingerprint-scoped and immutable:

* the number of S0 artefacts grows linearly with the number of **distinct manifests**;
* retention policies MAY safely keep S0 outputs for as long as upstream bundles are retained, since they are small but valuable for audit and reproducibility.

---

11.5 **SLOs and recommended thresholds**

11.5.1 Operators MAY define a soft SLO for S0 latency, e.g.:

* P95 `3b_s0_duration_seconds` < **N seconds** per manifest (N chosen based on environment; e.g. 30–60 seconds),
* with stronger expectations in low-latency or CI environments.

11.5.2 If S0 frequently exceeds its SLO, likely causes include:

* slow or overloaded object storage,
* excessively large upstream bundles (e.g. unbounded evidence in validation),
* misconfigured hashing strategy (e.g. recomputing dataset-level digests from scratch on very large datasets instead of reusing upstream digests where appropriate).

11.5.3 In such cases, recommended mitigations are:

* ensuring S0 runs **close to** the storage endpoint (minimising network latency),
* reusing upstream dataset digests when those are already validated and exposed in upstream bundles (so 3B can hash those digests instead of re-hashing the raw data),
* pruning unnecessary evidence files from upstream validation bundles where allowed by upstream specs.

---

11.6 **Scalability considerations for future extensions**

11.6.1 As 3B evolves, new features may introduce additional sealed artefacts (e.g. more policy packs, alternate edge manifests). This will increase `A` and possibly `F`, but S0 remains linear in both.

11.6.2 To maintain good performance as the number of artefacts grows:

* avoid adding very large, frequently changing data-plane tables to `SEALED` unless absolutely necessary;
* prefer sealing **summaries or hashes** of such tables (e.g. `zone_alloc_universe_hash`) when the upstream segment already exposes a stable digest;
* consider caching SHA-256 digests for artefacts that are shared across many manifests and do not change frequently (e.g. tzdb archives, static rasters).

11.6.3 Any future change that makes S0 depend on row-level computations over large tables (e.g. full scans of `outlet_catalogue`) SHOULD be treated as a **design smell** and carefully reviewed. Where possible, such work belongs in data-plane states, not in the gating state.

---

11.7 **Testing & regression checks**

11.7.1 Performance testing for S0 SHOULD include:

* runs against a “maximal” configuration with the largest expected number of sealed artefacts and biggest bundle sizes;
* runs under degraded storage conditions (e.g. higher latency) to ensure behaviour remains acceptable or alarms are raised appropriately.

11.7.2 Regression tests SHOULD verify that:

* small changes in catalogue content (e.g. adding an optional artefact) do not disproportionately increase S0 latency;
* the number of S0 artefacts and their sizes remain within expected budget envelopes as manifests evolve.

11.7.3 Since this section is informative, implementations MAY adapt specific numeric thresholds and metrics naming, but SHOULD uphold the qualitative goals:

* S0 remains fast,
* S0’s cost is dominated by a small number of metadata and hashing operations,
* and S0 does not become a bottleneck relative to data-plane segments.

---

## 12. Change control & compatibility *(Binding)*

12.1 **Scope of change control**

12.1.1 This section governs all changes that affect **3B.S0** and its control-plane artefacts, specifically:

* `s0_gate_receipt_3B` (schema, path, content),
* `sealed_inputs_3B` (schema, path, content),
* their entries in `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml`,
* any 3B-specific references to upstream catalogues and artefact IDs used by S0.

12.1.2 It does **not** govern:

* data-plane behaviour in downstream 3B states (S1–S5), except where they depend on the shapes or semantics of S0 outputs;
* layer-wide contracts in `schemas.layer1.yaml`, which follow their own change-control rules;
* upstream segment contracts (1A, 1B, 2A, 3A), except where 3B.S0 relies on their bundle laws and dataset identities.

---

12.2 **Versioning of 3B contracts**

12.2.1 The 3B contracts **MUST** use an explicit versioning scheme across:

* `schemas.3B.yaml`,
* `dataset_dictionary.layer1.3B.yaml`,
* `artefact_registry_3B.yaml`.

12.2.2 Implementations SHOULD follow a semantic-style scheme:

* **MAJOR** — incompatible/breaking changes to shapes, paths, partition law, or core semantics;
* **MINOR** — backwards-compatible extensions (e.g. new optional fields, new optional artefacts, new error codes);
* **PATCH** — non-semantic corrections (typos, doc-only fixes, clarifications that do not change behaviour).

12.2.3 S0 MUST verify at startup that the versions of:

* `schemas.3B.yaml`,
* `dataset_dictionary.layer1.3B.yaml`,
* `artefact_registry_3B.yaml`

form a **compatible triplet**, according to a version matrix or rule encoded in configuration (e.g. “all must share the same MAJOR version”).

12.2.4 If the triplet is not compatible (e.g. MAJOR mismatch, or a dictionary that references schema refs that don’t exist in the loaded `schemas.3B.yaml`), S0 MUST fail with `E3B_S0_SCHEMA_PACK_MISMATCH`.

---

12.3 **Backwards-compatible vs breaking changes**

12.3.1 The following are considered **backwards-compatible** (MINOR or PATCH) changes for 3B.S0, provided they respect all other sections of this spec:

* Adding new **optional fields** to `s0_gate_receipt_3B` or `sealed_inputs_3B` schemas, as long as:

  * existing required fields are unchanged,
  * new fields have sensible defaults for older readers (e.g. nullable, or with default semantics “unknown/absent”).

* Adding new **artefact kinds or logical IDs** that S0 MAY seal, as long as:

  * they are clearly marked as optional in the dictionary/registry, and
  * S0’s mandatory vs optional logic is updated accordingly.

* Adding new **error codes** (`E3B_S0_...`) without changing the semantics of existing codes.

* Tightening **validation** in ways that reject previously invalid but never-intended configurations (e.g. enforcing uniqueness or non-empty fields that were already expected by all valid runs).

12.3.2 The following are considered **breaking** (MAJOR) changes for 3B.S0:

* Removing or renaming any **required** field in `s0_gate_receipt_3B` or `sealed_inputs_3B`.

* Changing the **type or semantics** of a required field (e.g. changing `sha256_hex` format, or redefining the meaning of `owner_segment` or `artefact_kind`).

* Changing the **path_template**, **partition_keys**, or **writer_sort** for `s0_gate_receipt_3B` or `sealed_inputs_3B` in the dataset dictionary.

* Changing the definition of the **composite key** `(owner_segment, artefact_kind, logical_id, path)` in `sealed_inputs_3B`, or the uniqueness requirement for that tuple.

* Changing the meaning of `sealed_input_count_total` or `sealed_input_count_by_kind` so that they are no longer a direct function of the rows in `sealed_inputs_3B`.

* Altering the **identity rules** in §7 (e.g. allowing multiple S0 receipts per fingerprint, introducing additional partition keys) in a way that invalidates existing runs.

12.3.3 Any breaking change MUST:

* bump the MAJOR version of `schemas.3B.yaml`, and
* be accompanied by coherent updates to the dataset dictionary, artefact registry, and any tooling that reads S0 outputs.

12.3.4 When in doubt, change authors MUST err on the side of treating a change as **breaking** and performing a MAJOR bump, rather than silently altering semantics under the same MAJOR version.

---

12.4 **Handling mixed-version environments**

12.4.1 A runtime environment is **mixed-version** if:

* previously-produced fingerprints exist with `s0_gate_receipt_3B` / `sealed_inputs_3B` that were written under an **older 3B schema version**, but
* the current engine is running with a **newer schema/dictionary/registry version**.

12.4.2 3B.S0 itself is concerned only with **producing** outputs for **current** runs. It MUST:

* use the **current** schema/dictionary/registry versions when writing new S0 artefacts;
* not attempt to rewrite or upgrade historic S0 artefacts in place.

12.4.3 Reading historic S0 artefacts produced under older 3B versions is the responsibility of:

* downstream tooling or harnesses that explicitly support multiple schema versions, or
* explicit migration utilities.

S0 MUST NOT implicitly “upgrade” old artefacts, nor assume that it can read or rewrite them using the current schema.

12.4.4 If S0 is invoked in an environment where:

* historic S0 artefacts exist under an older MAJOR version, and
* the same `manifest_fingerprint` is being re-run with a newer MAJOR version,

S0 MUST observe the rules in §6.7:

* If the existing artefacts do not conform to the current schema, S0 MUST treat them as incompatible and MUST NOT overwrite them;
* Operators MUST treat this as a signal that a **new manifest_fingerprint** should be computed, or that an explicit migration step is required.

---

12.5 **Migration & deprecation**

12.5.1 When introducing a new field or artefact that is intended to become **mandatory** in a future version, the recommended pattern is:

1. Add the field/artefact as **optional** (MINOR version bump), with clear semantics and default behaviour when absent.
2. Update downstream states and tooling to **prefer** the new field/artefact when present.
3. After sufficient adoption, introduce a new MAJOR version where:

   * the field/artefact becomes required, and
   * old contracts (e.g. fallback behaviour) are formally deprecated.

12.5.2 Deprecation of existing fields MUST be handled via:

* schema annotations (e.g. `deprecated: true` in documentation), and
* clear run-report / documentation guidance,

before any MAJOR version removes or repurposes those fields.

12.5.3 For artefacts in `sealed_inputs_3B`:

* Deprecating a sealed artefact (e.g. an older policy pack) SHOULD be done by:

  * marking it as optional and unused in future 3B logic,
  * eventually removing it from future `SEALED` sets under a new MAJOR version.

* Removing a **mandatory** sealed artefact is a breaking change and MUST be accompanied by a documented replacement and MAJOR bump.

12.5.4 If new **categories** of artefacts (e.g. additional policy classes or RNG profiles) are added to 3B, they SHOULD be introduced as:

* new `artefact_kind` values or new `role` values in `sealed_inputs_3B`,
* with explicit documentation and updated downstream specs,
* and only later, if required, made mandatory in a MAJOR version.

---

12.6 **Compatibility with upstream and layer-wide changes**

12.6.1 Changes to upstream segments (1A, 1B, 2A, 3A) that affect:

* validation bundle shapes,
* PASS flag formats, or
* dataset IDs and schemas for egress assets that 3B consumes,

MUST be accompanied by updates to S0 logic and/or configuration so that Phase B (upstream gate verification) and Phase D (sealed enumeration) remain correct.

12.6.2 In particular, if an upstream segment changes its **bundle law** (index format or digest computation):

* 3B.S0 MUST adopt the new HashGate verification rules for that segment;
* the values stored in `upstream_gates.segment_*` MUST reflect the updated behaviour;
* the 3B spec MUST be updated to reference the correct upstream schema anchors for validation bundles if those anchors move.

12.6.3 Changes to layer-wide RNG or validation schemas in `schemas.layer1.yaml` that affect:

* the RNG envelope or event families, or
* the definition of identity objects (`parameter_hash_resolved`, `manifest_fingerprint_resolved`),

MUST be treated as layer-level changes. S0 MUST:

* reflect those changes when validating governance in Phase A;
* remain RNG-free itself;
* ensure that any embedded references (e.g. to RNG or validation schema anchors) are updated to the new layer schema version.

12.6.4 If the layer-level **3B validation bundle** schemas (`validation_bundle_index_3B`, `passed_flag_3B`) are introduced or modified in `schemas.layer1.yaml`, S0 MUST:

* ensure that its own outputs (`s0_gate_receipt_3B`, `sealed_inputs_3B`) remain valid members for that bundle;
* not attempt to implement the bundle law itself (that belongs to the 3B validation state), but MUST maintain stable paths, digests and identity fields that the validation state expects.

---

12.7 **Change documentation & review**

12.7.1 Any change to the 3B.S0 behaviour, schemas, or catalogues that is more than editorial MUST be:

* recorded in a human-readable change log (e.g. `CHANGELOG.3B.md`),
* linked to specific version increments (MAJOR/MINOR/PATCH),
* accompanied by a short rationale and migration notes.

12.7.2 Before deploying changes that affect 3B.S0, implementers SHOULD:

* run regression tests that re-execute S0 over representative manifests and assert:

  * deterministic behaviour across re-runs,
  * expected effects on `SEALED` contents,
  * and compatibility with downstream 3B states and top-level harnesses;
* verify that historic S0 artefacts (under old schema versions) remain readable by tools expected to consume them, or that appropriate migration strategies are in place.

12.7.3 Where this section conflicts with `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` or `artefact_registry_3B.yaml`, those artefacts SHALL be treated as **authoritative**, and this section MUST be updated as part of the next non-editorial version bump.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

> This appendix is descriptive only. Where it conflicts with any Binding section or JSON-Schema / dictionary / registry entry, those sources take precedence.

---

### 13.1 Identity & governance

* **`seed`**
  Layer-1 Philox seed for the run. Shared across segments for a given manifest.

* **`parameter_hash`**
  Tuple-hash over the governed parameter set for Layer-1 / 3B (configuration side). Used to scope parameter-bound artefacts in other states; for S0 it is an identity input only.

* **`manifest_fingerprint`**
  Hash of the full run manifest (ingress assets, policies, code version, etc.) as defined by the Layer-1 spec. Primary partition key for S0 outputs.

* **`run_id`**
  Optional, opaque identifier for a concrete execution of S0 under a given `{seed, parameter_hash, manifest_fingerprint}`. Used only for logging / correlation; not part of partition law.

* **Numeric policy / RNG governance**
  Short-hand for the layer-wide numeric and RNG definitions encoded in `schemas.layer1.yaml#/governance/*` and `#/rng/*` (e.g. `philox2x64-10`, rounding mode, subnormal behaviour).

---

### 13.2 Segments & states

* **`1A`**
  Layer-1 Segment 1A — merchant outlet counts and cross-country allocation.

* **`1B`**
  Layer-1 Segment 1B — site placement on the planet (`site_locations`).

* **`2A`**
  Layer-1 Segment 2A — civil time and per-site time zone (`site_timezones`, `tz_timetable_cache`).

* **`2B`**
  Layer-1 Segment 2B — routing and alias tables (site-level routing; virtual branch in data plane).

* **`3A`**
  Layer-1 Segment 3A — cross-zone merchants (zone-level counts, `zone_alloc`, `routing_universe_hash`).

* **`3B`**
  Layer-1 Segment 3B — virtual merchants & CDN surfaces (this subsegment).

* **`3B.S0` / `S0`**
  The 3B **Gate & environment seal** state; mandatory entry gate, RNG-free, control-plane only.

* **S1–S5 (3B)**
  Downstream 3B data-plane states (virtual classification, settlement, edge catalogue, CDN alias, 3B validation) — referenced but not specified here.

---

### 13.3 Datasets & artefacts (high-level)

* **`outlet_catalogue`**
  1A egress; per-merchant × country outlet stubs with `site_order`. Partitioned by `{seed, fingerprint}`.

* **`site_locations`**
  1B egress; per-site physical coordinates and related attributes. Partitioned by `{seed, fingerprint}`.

* **`site_timezones`**
  2A egress; per-site IANA tzid and tz provenance. Partitioned by `{seed, fingerprint}`.

* **`tz_timetable_cache`**
  2A cache; fingerprint-scoped tzdb transition table and associated digests.

* **`zone_alloc`**
  3A egress; per-merchant × country × tzid zone-level site counts and policy lineage. Partitioned by `{seed, fingerprint}`.

* **`zone_alloc_universe_hash`**
  3A validation artefact; fingerprint-scoped JSON summarising component digests and the combined `routing_universe_hash`.

* **`validation_bundle_*` / `_passed.flag`**
  Segment-level validation bundle and PASS flag for upstream segments (1A, 1B, 2A, 3A). S0 verifies these but does not create them.

* **`s0_gate_receipt_3B`**
  3B.S0 JSON gate receipt, fingerprint-scoped; records identity, upstream gates, catalogue versions, sealed-input summary.

* **`sealed_inputs_3B`**
  3B.S0 sealed-inputs inventory; one row per artefact (dataset, policy, schema, RNG profile, external asset) in the 3B input universe.

---

### 13.4 Policies, profiles & RNG

* **`mcc_channel_rules`**
  Short-hand for the virtual classification policy pack (e.g. `mcc_channel_rules.yaml`), used downstream to decide which merchants enter the 3B virtual path.

* **`virtual_settlement_coords`**
  Short-hand for artefacts providing legal settlement coordinates for virtual merchants (e.g. CSV or Parquet of `(merchant/brand, lat, lon, evidence)`).

* **`cdn_country_weights`**
  Policy defining the target country-level mix for CDN edge nodes (e.g. weights over ISO country codes).

* **`virtual_validation`**
  Policy pack (e.g. `virtual_validation.yml`) describing validation checks and thresholds for virtual / CDN behaviour.

* **HRSL / population raster**
  Human-settlement / population density raster used by downstream 3B states to place CDN edge nodes (shared with 1B).

* **`route_rng_policy_v1` / `cdn_rng_policy_v1`**
  Shorthand for RNG policy artefacts describing Philox stream layout, budgets and stream IDs for routing and CDN edge picks.

* **`cdn_edge_pick`**
  RNG event family defined in `schemas.layer1.yaml#/rng/events/cdn_edge_pick`, emitted by downstream 3B states when selecting a CDN edge per virtual arrival. Mentioned here only as a dependency; S0 does not emit such events.

---

### 13.5 S0-local terms & sets

* **`SEALED`**
  Informal name for the in-memory collection of artefacts that S0 enumerates and then writes into `sealed_inputs_3B`. Each element of `SEALED` becomes one row in `sealed_inputs_3B`.

* **`upstream_gates`**
  Object inside `s0_gate_receipt_3B` capturing, for each upstream segment (1A, 1B, 2A, 3A), the bundle path, flag path, recomputed digest and PASS/FAIL status.

* **`sealed_input_count_total`**
  Scalar count in `s0_gate_receipt_3B` equal to the number of rows in `sealed_inputs_3B` for that fingerprint.

* **`sealed_input_count_by_kind`**
  Map in `s0_gate_receipt_3B` keyed by `artefact_kind` (e.g. dataset, policy, schema, rng_profile, external) giving per-kind counts of sealed artefacts.

* **`gate_receipt_sha256` / `sealed_inputs_sha256`**
  Optional digests computed over `s0_gate_receipt_3B` and `sealed_inputs_3B` respectively; informative in S0, authoritative only when used in the 3B validation bundle.

---

### 13.6 Abbreviations & notation

* **CDN** — Content Delivery Network (here: logical representation of edge nodes and their country mix for virtual merchants).

* **FK** — Foreign key (relational integrity between datasets).

* **IO** — Input/output (file or object-store access).

* **RNG** — Random Number Generator (Philox2x64-10 throughout Layer-1).

* **SLO** — Service Level Objective (performance or reliability targets; informative only).

* **PASS / FAIL** — Binary status labels for S0 runs, upstream segment bundles, and (eventually) the 3B segment-level validation.

* **FATAL / WARN** — Severity levels for error codes (§9), where FATAL blocks gating and WARN allows completion with highlighted issues.

---

13.7 **Relationship to other specs**
This appendix is intended as a convenience cross-reference for implementers and reviewers. For exact field sets, types and allowed values, refer to:

* `schemas.layer1.yaml` — layer-wide primitives, RNG envelopes, validation bundle shapes.
* `schemas.1A.yaml`, `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml` — upstream segment schemas.
* `schemas.3B.yaml` — authoritative shapes for `s0_gate_receipt_3B` and `sealed_inputs_3B`.
* `dataset_dictionary.layer1.*.yaml` and `artefact_registry_*.yaml` — dataset identities, paths, and ownership.

---
