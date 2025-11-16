# 3B.S3 — Edge alias tables & virtual edge universe hash

## 1. Purpose & scope *(Binding)*

1.1 **State identity and role in subsegment 3B**

1.1.1 This state, **3B.S3 — Edge alias tables & virtual edge universe hash** (“S3”), is a **RNG-free control/data-plane packaging state** in Layer-1 subsegment **3B — Virtual merchants & CDN surfaces**. It executes only after:

* **3B.S0 — Gate & environment seal** has successfully sealed the 3B universe for the target `manifest_fingerprint`; and
* **3B.S1 — Virtual classification & settlement node construction** and **3B.S2 — CDN edge catalogue construction** have both completed successfully for the same `{seed, manifest_fingerprint}`.

1.1.2 S3’s primary role is to take the **static edge universe** produced by S2 and transform it into:

* per-merchant **alias tables** over edges, in a layout that 2B can decode efficiently at routing time; and
* a fingerprint-scoped **virtual edge universe hash** that cryptographically ties those alias tables back to S2’s edge catalogue and to the sealed edge-related policies.

1.1.3 S3 does **not** introduce any new business semantics about merchants, settlement, geography or timezones. It is a **representation & integrity layer**: given the edge universe and policies that S2 produced under the sealed environment, S3 creates the alias representation and a hash that 2B and validation can trust.

---

1.2 **High-level responsibilities**

1.2.1 S3 MUST:

* consume the **sealed environment** from S0 (`s0_gate_receipt_3B`, `sealed_inputs_3B`) to establish identity, upstream PASS status, and the set of admissible artefacts for 3B;

* read S2’s outputs for the same `{seed, manifest_fingerprint}`:

  * `edge_catalogue_3B` — authoritative list of edge nodes and weights per virtual merchant;
  * `edge_catalogue_index_3B` — authoritative per-merchant and global counts/digests over the edge catalogue;

* for each virtual merchant present in `edge_catalogue_3B`, construct a **discrete probability distribution over its edges** by:

  * extracting `edge_weight` in a deterministic order;
  * applying any required quantisation or integer-grid mapping as defined by the **alias-layout policy**;

* build a per-merchant **alias table** from that distribution using a deterministic algorithm (e.g. Walker/Vose), and pack all per-merchant alias tables into a single **alias blob** governed by a versioned layout (alignment, endianness, checksums);

* construct a corresponding **alias index** that, for each merchant, records:

  * offset and length of its alias table in the blob;
  * basic counts (number of edges, table length);
  * layout version and checksums needed for safe decode;

* compute a fingerprint-scoped **virtual edge universe hash** that combines digests of:

  * the edge-budget / geography policies (e.g. `cdn_country_weights` and any overrides);
  * the spatial and RNG/alias-layout policies relevant to edge placement and alias construction;
  * S2’s edge catalogue/index;
  * S3’s alias blob and alias index;

* emit a small descriptor object (e.g. `edge_universe_hash_3B`) capturing:

  * the final universe hash;
  * the component digests and version identifiers;
  * enough metadata for 2B and validation to check for drift.

1.2.2 S3 MUST ensure that its outputs are sufficient for:

* **2B’s virtual routing branch** to:

  * look up a merchant’s alias table via `edge_alias_index_3B`;
  * decode and use that alias table at runtime without further knowledge of policy or edge placement;
  * verify, via the edge universe hash, that its view of alias tables matches the S3-signed universe;

* the **3B validation state** to:

  * verify that S3’s alias representation is internally consistent with S2’s edge catalogue;
  * verify that the edge universe hash accurately reflects the sealed policies + S2 + S3 artefacts.

---

1.3 **RNG-free and deterministic scope**

1.3.1 S3 is **strictly RNG-free**. It MUST NOT:

* open or advance any Philox RNG stream;
* emit any RNG events (including routing-oriented events such as `cdn_edge_pick`);
* depend on any non-deterministic source (wall-clock time, process ID, host name, unordered filesystem iteration, etc.) for its decisions.

1.3.2 All S3 outputs MUST be a pure, deterministic function of:

* the identity triple `{seed, parameter_hash, manifest_fingerprint}`;
* the sealed artefacts recorded in `sealed_inputs_3B` that are relevant to S3 (e.g. alias-layout policy, RNG/routing policy IDs, CDN policy digests, spatial policy digests);
* S1 and S2 data-plane outputs (`virtual_classification_3B` for consistency checks, `edge_catalogue_3B` and `edge_catalogue_index_3B` as the edge universe);
* the layout and hashing laws defined in this spec and in the alias-layout / validation schemas.

1.3.3 Given identical inputs (same identity triple, same sealed artefacts, same S1/S2 outputs, same policies and schemas), repeated executions of S3 for the same `{seed, parameter_hash, manifest_fingerprint}` MUST produce **bit-identical**:

* alias blob (`edge_alias_blob_3B`);
* alias index (`edge_alias_index_3B`);
* universe-hash descriptor (`edge_universe_hash_3B`);
* and any S3 run-summary artefacts.

---

1.4 **Relationship to upstream segments and downstream consumers**

1.4.1 S3 relies on upstream segments and states as follows:

* **S0** for:

  * identity and governance (`seed`, `parameter_hash`, `manifest_fingerprint`, numeric/RNG policy);
  * upstream gates (1A, 1B, 2A, 3A) == `PASS`;
  * the sealed 3B artefact universe (`sealed_inputs_3B`).

* **S1** for:

  * virtual merchant semantics (which merchants are virtual);
  * settlement semantics, where needed for consistency checks.

* **S2** for:

  * the actual **edge universe** (edge nodes, countries, operational tzids, weights) via `edge_catalogue_3B`;
  * the authoritative per-merchant and global edge counts/digests via `edge_catalogue_index_3B`.

1.4.2 S3 MUST treat:

* S1 and S2 outputs as **read-only**;
* **alias-layout policy** as the only authority on how alias tables are represented in bytes (layout version, alignment, endianness, quantisation, checksum fields);
* **RNG / routing policy** as the only authority on compatibility requirements with 2B (e.g. what layout 2B decoders expect, which alias layout version is supported).

1.4.3 Downstream, S3’s outputs are binding for:

* **2B’s virtual routing branch**, which MUST:

  * rely on S3’s alias tables instead of reconstructing alias from raw edges;
  * verify S3’s universe hash before routing;

* the **3B validation state**, which MUST:

  * treat S3 outputs as mandatory for segment-level PASS;
  * include them (and their digests) in the 3B validation bundle.

---

1.5 **Out-of-scope behaviour**

1.5.1 The following concerns are explicitly **out of scope** for S3 and are handled elsewhere:

* **Virtual classification of merchants** and construction of settlement nodes (`virtual_classification_3B`, `virtual_settlement_3B`) — solely S1’s responsibility.
* **Edge placement** (deciding where edges are on the globe, how many per merchant/country/tile, how they were jittered, and which RNG streams were used) — solely S2’s responsibility.
* **Per-arrival routing decisions** and emission of routing RNG events (e.g. `cdn_edge_pick`) — solely 2B’s responsibility.
* 3B’s **segment-level validation bundle and `_passed.flag_3B`** — owned by the terminal 3B validation state (though S3’s outputs are mandatory inputs to that bundle).

1.5.2 S3 MUST NOT:

* add, remove, or modify edges in the universe defined by `edge_catalogue_3B`;
* reinterpret `edge_weight`, `country_iso`, `edge_latitude_deg`, `edge_longitude_deg`, or `tzid_operational` semantics;
* construct or modify RNG policy, RNG streams, or per-arrival sampling behaviour;
* emit its own segment-level PASS flag.

1.5.3 S3’s defined scope is therefore:

> **Given a sealed environment and the static edge universe from S2, S3 deterministically constructs per-merchant alias tables plus a fingerprint-scoped virtual edge universe hash, with no new randomness and no change to the underlying edges.**

---

## 2. Preconditions & gated inputs *(Binding)*

2.1 **Execution context & identity**

2.1.1 S3 SHALL execute only in the context of a Layer-1 run where the identity triple

> `{seed, parameter_hash, manifest_fingerprint}`

has already been resolved by the enclosing engine and is consistent with the Layer-1 identity and hashing policy.

2.1.2 At entry, S3 MUST be provided with:

* `seed` — the Layer-1 Philox seed for this run;
* `parameter_hash` — the governed parameter hash for the 3B configuration;
* `manifest_fingerprint` — the enclosing manifest fingerprint.

2.1.3 S3 MUST NOT recompute or override these identity values. It MUST:

* treat them as read-only identity inputs; and
* ensure that any identity echoes embedded in S3 outputs (`edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`) match these values and those recorded in `s0_gate_receipt_3B`.

---

2.2 **Dependence on 3B.S0 (gate & sealed inputs)**

2.2.1 For a given `manifest_fingerprint`, S3 MAY proceed only if both of the following artefacts exist and are schema-valid:

* `s0_gate_receipt_3B` at its canonical fingerprint-partitioned path;
* `sealed_inputs_3B` at its canonical fingerprint-partitioned path.

2.2.2 Before performing any work, S3 MUST:

* load and validate `s0_gate_receipt_3B` against `schemas.3B.yaml#/validation/s0_gate_receipt_3B`;
* load and validate `sealed_inputs_3B` against `schemas.3B.yaml#/validation/sealed_inputs_3B`;
* assert that `segment_id = "3B"` and `state_id = "S0"` in the gate receipt;
* assert that `manifest_fingerprint` in the gate receipt equals the run’s `manifest_fingerprint`;
* where present, assert that `seed` and `parameter_hash` in the gate receipt equal the values provided to S3.

2.2.3 S3 MUST also assert that, in `s0_gate_receipt_3B.upstream_gates`:

* `segment_1A.status = "PASS"`;
* `segment_1B.status = "PASS"`;
* `segment_2A.status = "PASS"`;
* `segment_3A.status = "PASS"`.

If any of these statuses is not `"PASS"`, S3 MUST treat the 3B environment as **not gated** and fail with a FATAL upstream-gate error. S3 MUST NOT attempt to re-verify or repair upstream validation bundles directly.

2.2.4 If `s0_gate_receipt_3B` or `sealed_inputs_3B` is missing, schema-invalid, or inconsistent with the run identity, S3 MUST fail fast and MUST NOT attempt to “re-seal” inputs itself.

---

2.3 **Dependence on 3B.S1 & 3B.S2 (virtual set & edge universe)**

2.3.1 S3 MUST treat S1 and S2 as functional preconditions. For a given `{seed, manifest_fingerprint}`, S3 MAY proceed only if:

* `virtual_classification_3B@seed={seed}, fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/egress/virtual_classification_3B`;
* `virtual_settlement_3B@seed={seed}, fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/egress/virtual_settlement_3B`;
* `edge_catalogue_3B@seed={seed}, fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/egress/edge_catalogue_3B`;
* `edge_catalogue_index_3B@seed={seed}, fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/egress/edge_catalogue_index_3B`.

2.3.2 Before building alias tables, S3 MUST at least:

* verify key invariants between `virtual_classification_3B` and `virtual_settlement_3B` (1:1 mapping for virtual merchants, as per S1’s spec);
* verify that every `merchant_id` present in `edge_catalogue_3B` is classified as virtual in `virtual_classification_3B` (or otherwise conforms to the S1/S2 contract);
* verify that `edge_catalogue_index_3B` is internally consistent with `edge_catalogue_3B` (per-merchant and global edge counts match actual row counts), per S2’s spec.

2.3.3 S3 MUST NOT:

* re-classify merchants as virtual or non-virtual;
* add or remove edges relative to `edge_catalogue_3B`;
* adjust `edge_weight`, `country_iso`, coordinates or `tzid_operational`.

If inconsistencies or schema violations are detected, S3 MUST treat them as S1/S2 contract violations and fail, rather than attempting to “repair” S1/S2 outputs.

2.3.4 In a configuration mode where virtual routing is disabled and S2 legitimately produced an empty edge universe:

* S3 MUST support an alias-trivial mode (e.g. empty alias blob/index, documented semantics);
* S3 MUST still satisfy all schema and universe-hash requirements for that mode;
* behaviour in this mode MUST be explicitly described in the 3B spec.

---

2.4 **Required 3B contracts (schemas, dictionary, registry)**

2.4.1 S3 MUST operate against a coherent set of 3B contracts:

* `schemas.3B.yaml`;
* `dataset_dictionary.layer1.3B.yaml`;
* `artefact_registry_3B.yaml`.

2.4.2 S3 MAY rely on `s0_gate_receipt_3B.catalogue_versions` to determine which versions were sealed by S0, or MAY reload these contracts explicitly. In either case, S3 MUST verify that:

* they form a **compatible triplet** for S3 (per 3B’s versioning rules, e.g. same MAJOR version);
* they define entries for all S3 outputs and any S3-specific run-summary surfaces:

  * `edge_alias_blob_3B`;
  * `edge_alias_index_3B`;
  * `edge_universe_hash_3B`;
  * (optionally) `s3_gate_receipt_3B` / `s3_run_summary_3B` if such datasets are part of the design.

2.4.3 If S3 detects:

* missing schema refs;
* missing dataset IDs for S3 outputs;
* or an incompatible schema/dictionary/registry version set,

it MUST fail with a FATAL contract error (e.g. `E3B_S3_SCHEMA_PACK_MISMATCH`) and MUST NOT guess shapes, paths, or partitioning.

---

2.5 **Required sealed artefacts (alias layout, RNG/routing policy, policy digests)**

2.5.1 S3 MUST treat `sealed_inputs_3B` as the **sole authority** for which policy and layout artefacts it may use. For S3 to run, `sealed_inputs_3B` MUST contain rows for at least the following **mandatory artefacts** (with well-formed entries):

* **Alias-layout policy** for edges (e.g. `edge_alias_layout_policy_v1`):

  * defines alias layout version, header schema, blob encoding, alignment, endianness, integer grid size, quantisation rules, and checksum fields;
  * defines how many bytes per element (prob/alias), and mapping from alias table indices to edge IDs.

* **RNG / routing policy** (even though S3 is RNG-free):

  * defines the compatibility expectations for 2B’s decode (e.g. which alias layout versions are supported; how alias tables are interpreted at routing time);
  * ensures S3 builds alias tables and blob layout that 2B’s decoder understands.

* **Edge-policy digests** required for the universe hash, for example:

  * digests of `cdn_country_weights` and any edge-budget overrides;
  * digests of spatial surfaces used by S2 (tiles/rasters) as sealed by S0/S2;
  * digests of any RNG/alias policies that should be included in the universe hash.

2.5.2 For each such logical artefact, S3 MUST:

* locate its row in `sealed_inputs_3B` (`logical_id`, `owner_segment`, `artefact_kind`);
* resolve `path` and `schema_ref` (if non-null);
* open and validate the artefact against its schema;
* if hardened mode is enabled, recompute its digest and compare it against `sha256_hex`.

2.5.3 If any mandatory artefact required by S3’s algorithm is missing from `sealed_inputs_3B`, unreadable, schema-incompatible or digest-mismatched, S3 MUST fail with a FATAL sealed-input error and MUST NOT fall back to resolving the artefact directly via the dictionary/registry.

---

2.6 **Optional modes / feature flags**

2.6.1 If the engine exposes configuration flags or parameters that affect S3 behaviour (e.g. `alias_layout_version`, `enable_global_alias_header`, `enable_additional_alias_metadata`), these flags MUST:

* be part of the governed 3B parameter set contributing to `parameter_hash`;
* be compatible with the alias-layout and routing policies sealed in `sealed_inputs_3B`.

2.6.2 S3 MUST interpret such flags only within the boundaries allowed by the alias-layout policy and schemas. For example:

* switching between two layout versions is permitted only if both are defined and versioned in `schemas.3B.yaml` and supported by 2B’s decoder;
* optional inclusion of extra metadata (e.g. per-merchant metrics within the index) is permitted only if these fields are schema-optional and do not change core semantics.

2.6.3 If a configuration flag enables a feature that requires additional artefacts (e.g. a second alias layout, or extra policy digests), S3 MUST treat those artefacts as **mandatory** in that mode and fail if they are not present in `sealed_inputs_3B`.

---

2.7 **Scope of gated inputs & downstream obligations**

2.7.1 The union of:

* S2 outputs (`edge_catalogue_3B`, `edge_catalogue_index_3B`), and
* the artefacts S3 is allowed to read according to `sealed_inputs_3B` (alias-layout policies, RNG/routing policy, edge-policy digests, any S3-specific schemas),

SHALL define the **closed input universe** for 3B.S3.

2.7.2 S3 MUST NOT:

* read artefacts that are not listed in `sealed_inputs_3B` for the target `manifest_fingerprint`;
* use environment variables, local ephemeral files, or network resources as additional inputs to alias construction or universe hashing.

2.7.3 Downstream consumers (2B virtual routing, 3B validation) MAY assume that:

* S3’s alias representations and universe hash were constructed **only** from S2’s edge universe and the sealed policies captured in `sealed_inputs_3B`;
* any missing or inconsistent artefact that would affect alias tables or universe hash would have caused S3 to fail rather than silently degrading or changing behaviour.

2.7.4 If S3 discovers at runtime that it requires an artefact that is not present in `sealed_inputs_3B` (e.g. alias-layout version not sealed by S0), S3 MUST:

* treat this as a configuration or S0-sealing error;
* fail fast with an appropriate `E3B_S3_*` error code;
* NOT attempt to resolve the artefact out-of-band via the dictionary/registry or environment.

---

## 3. Inputs & authority boundaries *(Binding)*

3.1 **Control-plane inputs from 3B.S0**

3.1.1 S3 SHALL treat the following S0 artefacts as **required control-plane inputs** for the target `manifest_fingerprint`:

* `s0_gate_receipt_3B` (fingerprint-scoped JSON);
* `sealed_inputs_3B` (fingerprint-scoped table).

3.1.2 For S3, `s0_gate_receipt_3B` is the **sole authority** on:

* the identity triple `{seed, parameter_hash, manifest_fingerprint}` that S3 MUST embed (as echoes) into its outputs where applicable;
* upstream gate status for segments 1A, 1B, 2A, 3A (which MUST all be `status = "PASS"`);
* which versions of `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, and `artefact_registry_3B.yaml` are in force for 3B in this run.

3.1.3 `sealed_inputs_3B` is the **sole authority** on the set of artefacts (policies, schemas, profiles, shared datasets) S3 is permitted to read. S3 MUST NOT:

* resolve or open artefacts that are not listed in `sealed_inputs_3B` for the target `manifest_fingerprint`, even if they exist in the dictionary/registry;
* hard-code paths or look up additional files via environment variables or external configuration.

3.1.4 Whenever S3 consumes an artefact (policy, reference dataset, etc.), it MUST:

* locate the relevant row in `sealed_inputs_3B` by `logical_id` (and, if needed, `owner_segment` and `artefact_kind`);
* treat `path` from that row as the canonical storage location;
* treat `schema_ref` (if non-null) as the canonical schema anchor;
* treat `sha256_hex` as the canonical digest for integrity checks (if S3 recomputes a digest, it MUST match `sha256_hex`).

---

3.2 **Data-plane inputs from S1 & S2**

3.2.1 S3’s **data-plane inputs** are the S1/S2 outputs for the same `{seed, manifest_fingerprint}`:

* `virtual_classification_3B` — authoritative virtual vs non-virtual classification;
* `virtual_settlement_3B` — one legal settlement node per virtual merchant (as defined by S1);
* `edge_catalogue_3B` — authoritative edge universe from S2;
* `edge_catalogue_index_3B` — authoritative per-merchant/global counts & digests over `edge_catalogue_3B`.

3.2.2 The shapes and semantics of these datasets are governed by:

* `schemas.3B.yaml` for 3B datasets;
* S1 and S2 specs for their behaviour and invariants;
* and their own dictionary/registry entries for identity, paths and partitioning.

S3 MUST treat these components as **read-only** and MUST NOT mutate them.

3.2.3 Authority boundaries:

* S1 remains the authority on:

  * which merchants are virtual (`virtual_classification_3B`), and
  * what each merchant’s settlement node is (`virtual_settlement_3B`).

* S2 remains the authority on:

  * which edges exist (`edge_catalogue_3B` rowset and keys);
  * each edge’s attributes: `merchant_id`, `country_iso`, coordinates, `tzid_operational`, `edge_weight`, and spatial/RNG provenance;
  * row counts and global/per-merchant digests in `edge_catalogue_index_3B`.

3.2.4 S3 MUST NOT:

* add or remove edges relative to `edge_catalogue_3B`;
* change any field values in S1 or S2 outputs;
* reinterpret `edge_weight` semantics (e.g. change its normalisation or meaning);
* silently ignore edges: every edge in `edge_catalogue_3B` MUST either be represented in a merchant’s alias table or be handled by an explicitly-documented degenerate case (e.g. all mass on a single “fallback” edge, if the policy allows).

3.2.5 S3 MAY read `virtual_classification_3B` / `virtual_settlement_3B`:

* for **consistency checks** (e.g. “all merchants in `edge_catalogue_3B` are virtual”, “no edges exist for non-virtual merchants”), and
* for **diagnostics and run-reporting**,

but S3 MUST NOT re-classify merchants or reinterpret settlement semantics.

---

3.3 **Alias-layout policy inputs**

3.3.1 S3 MUST consume one or more **alias-layout policy artefacts** (e.g. `edge_alias_layout_policy_v1`) sealed in `sealed_inputs_3B` and registered in `artefact_registry_3B.yaml`. These artefacts are the **sole authority** on:

* the **byte-level layout** of alias tables:

  * layout version identifier;
  * encoding of probabilities and aliases (e.g. 32-bit/64-bit, fixed-point vs float);
  * endianness;
  * alignment requirements and padding rules;

* the **header and index schemas**:

  * blob header contents (layout version, global checksums);
  * per-merchant index schema (offset, length, count, checksum fields);

* the **quantisation discipline**:

  * size of integer grid or fixed-point representation (e.g. 2ᵇ grid);
  * rounding mode (e.g. round-to-nearest-even, largest-remainder);
  * acceptable tolerances between original `edge_weight` and alias probabilities;

* the **checksum and integrity rules**:

  * how per-merchant and global checksums are computed over alias tables and blob;
  * which checksum algorithm(s) (e.g. SHA-256, CRC32) are used.

3.3.2 S3 MUST:

* follow the alias-layout policy exactly when:

  * normalising and quantising per-merchant weights into alias masses;
  * constructing alias tables (prob and alias arrays);
  * packing per-merchant alias tables into the blob;
  * computing per-merchant and global checksums;

* NOT introduce any alternative or “ad-hoc” alias representation that is not described in the alias-layout policy and schemas.

3.3.3 If the alias-layout policy supports multiple **layout versions**, S3 MUST:

* select a layout version deterministically based on configuration and policy metadata (e.g. a parameter in the 3B config; or the only supported layout version);
* record the chosen `layout_version` in all relevant headers and indexes;
* adhere to that version’s rules for the entire run.

S3 MUST NOT mix different alias layout versions within the same `{seed, manifest_fingerprint}`.

---

3.4 **RNG / routing-policy compatibility inputs**

3.4.1 Although S3 is RNG-free, it MUST respect the **RNG / routing policy** sealed in `sealed_inputs_3B` to ensure its outputs are **compatible with 2B’s decoder**. The relevant policy artefacts typically define:

* which alias layout versions 2B supports;
* how 2B expects to interpret alias tables (e.g. index range, mapping from alias entries to `edge_id` indices);
* any assumptions about per-merchant edge ordering (e.g. edge index order derived from `edge_catalogue_3B` sorted by `edge_id`).

3.4.2 S3 MUST ensure that:

* the alias layout it uses is declared compatible with 2B’s routing implementation;
* the ordering of edges for alias construction (i.e. mapping from alias table index → `edge_id`) is clearly defined and stable, and matches 2B’s expectations.

3.4.3 S3 MUST NOT:

* depend on actual RNG streams, budgets or counters;
* emit RNG events of any kind;
* modify or generate RNG policy artefacts.

Compatibility checks are strictly about **layout & decoding assumptions**, not RNG usage.

---

3.5 **3A’s zone-universe hash & cross-layer contracts**

3.5.1 S3 MAY read the 3A **zone-universe hash descriptor** (e.g. `zone_alloc_universe_hash`) if it is sealed in `sealed_inputs_3B`, but:

* 3A remains the authority on **zone universe** semantics and `routing_universe_hash` for zones;
* S3 must treat that value as **read-only** and may only echo or combine it for informational / validation purposes.

3.5.2 If the overall design requires a **combined universe hash** (e.g. combining 3A’s zone-universe hash with 3B’s edge-universe hash for 2B’s global routing), the combination law MUST be:

* defined in the appropriate validation / routing spec(s);
* referenced (but not redefined) by S3.

3.5.3 S3’s own `edge_universe_hash_3B` is authoritative only for the **virtual edge universe** (edges + alias). It MUST NOT claim authority over 3A’s zone universe or over any global combined hash that includes non-3B elements.

---

3.6 **Authority boundaries summary**

3.6.1 S3 SHALL respect the following authority boundaries:

* **JSON-Schema packs** (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.3B.yaml`, and relevant upstream segment schemas) are the **only authorities on shapes** of all datasets and policies S3 reads or writes. S3 MUST NOT loosen or override these definitions.

* **Dataset dictionaries** (Layer-1, 3B, and upstream) are the **only authorities on dataset identities, path templates, partition keys and writer sorts**. S3 MUST NOT invent alternate paths or partition schemes.

* **Artefact registries** are the **only authorities on logical IDs, ownership and licence classes** for policies and datasets. S3 MUST NOT create or use unregistered artefacts.

* **S1 outputs** are the **only authority** on virtual merchant and settlement semantics; S3 only uses them for consistency checks and run-reporting.

* **S2 outputs** (`edge_catalogue_3B`, `edge_catalogue_index_3B`) are the **only authority** on the edge universe and pre-alias counts/digests. S3 MUST NOT change edges or their semantics.

* **Alias-layout policy** is the **only authority** on alias table representation, quantisation and checksum laws; S3 MUST implement alias construction exactly according to this policy.

* **RNG / routing policy** is the **only authority** on compatibility assumptions between S3’s alias outputs and 2B’s routing implementation; S3 MUST align its outputs to those expectations.

* **3A’s zone-universe hash** (if read) is the **only authority** on the zone-level routing universe. S3 may reference it but not reinterpret it.

3.6.2 If S3 detects any conflict between:

* what a schema/dictionary/registry entry claims about an artefact, and
* what S3 observes on disk (e.g. missing fields, invalid enum values, unknown layout version),

S3 MUST treat this as an **input integrity or contract error** (signalled via `E3B_S3_*`) and MUST NOT attempt to auto-correct or reinterpret the artefact in a way that changes its meaning.

3.6.3 Any future extension that introduces new inputs (additional alias layouts, extra policies, additional hash components) MUST:

* be registered and sealed via `sealed_inputs_3B`;
* have schemas and contract entries defined;
* be explicitly documented in this section with clear authority boundaries before S3 is modified to use them.

---

## 4. Outputs (datasets) & identity *(Binding)*

4.1 **Overview of S3 outputs**

4.1.1 For each successful run of S3 at a given `{seed, manifest_fingerprint}`, S3 SHALL emit the following **3B-owned artefacts**:

* **`edge_alias_blob_3B`** — a contiguous binary blob containing all per-merchant alias tables over the S2 edge universe.
* **`edge_alias_index_3B`** — a structured index describing how to locate each merchant’s alias table within the blob, and how to interpret it.

4.1.2 In addition, for each `manifest_fingerprint`, S3 SHALL emit a **fingerprint-scoped universe descriptor**:

* **`edge_universe_hash_3B`** — a JSON document that records:

  * an aggregate **virtual edge universe hash**; and
  * the component digests and version identifiers that contributed to it (S2 catalogue/index digests, policy digests, alias blob/index digests, layout version, etc.).

4.1.3 S3 MAY also emit a small **run-summary / gate receipt** for internal observability (e.g. `s3_run_summary_3B`), but such a dataset:

* MUST be explicitly declared in the 3B schema/dictionary if persisted;
* MUST NOT alter the binding semantics of the three core artefacts above.

4.1.4 S3 MUST NOT emit any additional data-plane egress datasets beyond those explicitly declared in the 3B contracts. In particular, S3 MUST NOT:

* emit a modified edge catalogue;
* emit routing logs or RNG logs (S3 is RNG-free);
* emit a segment-level `_passed.flag_3B` (owned by the terminal 3B validation state).

---

4.2 **Alias blob egress: `edge_alias_blob_3B`**

4.2.1 `edge_alias_blob_3B` SHALL be the **authoritative alias-table blob** for virtual edges in 3B. It is a binary artefact containing, in a single contiguous byte array:

* a fixed, versioned **header**; and
* a concatenation of per-merchant alias table segments, each describing the discrete distribution over edges for one merchant `m ∈ V`.

4.2.2 At minimum, the blob MUST contain:

* **Header section**, including:

  * `layout_version` — an identifier for the alias layout implementation;
  * `endianness` — enumeration (e.g. `"little"` / `"big"`);
  * `alignment_bytes` — minimum required alignment for table segments;
  * `blob_length_bytes` — total byte length of the blob;
  * `blob_sha256_hex` — SHA-256 digest over the entire blob (excluding any non-data padding if the layout policy so specifies);
  * `alias_layout_policy_id` / `alias_layout_policy_version` — logical ID & version of the alias layout policy artefact;
  * optional reserved fields for future extension (must be schema-optional).

* **Per-merchant segments**, each composed of:

  * a contiguous representation of the merchant’s alias table, as specified by the alias-layout policy: typically parallel arrays:

    * `prob[i]` — quantised probability masses;
    * `alias[i]` — alias indices;
  * any per-merchant headers required by the layout (e.g. local checksum, edge count, table length).

4.2.3 Identity & partitioning:

* `edge_alias_blob_3B` MUST be partitioned by:

  * `seed={seed}`
  * `fingerprint={manifest_fingerprint}`

* The normative `path` SHALL be defined in `dataset_dictionary.layer1.3B.yaml`, i.e.:
  `data/layer1/3B/edge_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_blob_3B.bin`

* No other partition keys MAY be used.

4.2.4 The blob format (header fields, segment layout, element sizes, alignment) MUST conform to the alias-layout policy schema and is binding. S3 MUST NOT:

* introduce undocumented fields;
* change struct packing or alignment beyond what is declared in the policy;
* reorder merchants’ segments relative to the ordering declared in the alias-layout policy (typically sorted by `merchant_id`).

4.2.5 The alias blob MUST be **self-describing** enough for 2B to decode it using:

* the layout version and header;
* `edge_alias_index_3B` (for per-merchant offsets/lengths);
* shared decode logic bound to the same alias-layout policy.

---

4.3 **Alias index egress: `edge_alias_index_3B`**

4.3.1 `edge_alias_index_3B` SHALL be the **authoritative index and metadata surface** for the alias blob. It MUST allow downstream consumers (S3 validation, 2B) to:

* locate each merchant’s alias table within `edge_alias_blob_3B` (byte offset + length),
* verify its integrity (checksums, lengths, counts), and
* map alias indices back to S2’s edge rows.

4.3.2 At minimum, `edge_alias_index_3B` MUST contain:

* **Per-merchant rows** (one per merchant with at least one edge):

  * `scope`

    * enum e.g. `{"MERCHANT","GLOBAL"}`;
    * MUST equal `"MERCHANT"` for merchant rows;
    * distinguishes global summary rows.

  * `merchant_id` (or composite `merchant_key`)

    * join key back to S1/S2 outputs;
    * MUST match `merchant_id` domain used in `edge_catalogue_3B`.

  * `edge_count_total`

    * integer; number of edges for this merchant (size of `E_m`);
    * MUST equal `edge_count_total` in `edge_catalogue_index_3B` for the same merchant.

  * `alias_table_length`

    * integer; the number of slots in the alias table for this merchant;
    * typically equals `edge_count_total` but MAY differ if the layout uses padded sizes (e.g. power-of-two length).

  * `blob_offset_bytes`

    * integer; byte offset in `edge_alias_blob_3B` where this merchant’s alias segment begins (from the start of the blob).

  * `blob_length_bytes`

    * integer; length in bytes of this merchant’s alias segment.

  * `merchant_alias_checksum`

    * checksum/digest over the merchant’s alias segment (exact algorithm per alias-layout policy).

  * `alias_layout_version`

    * string/integer matching `layout_version` in the blob header;
    * MAY be redundant but MUST be consistent.

  * optional `edge_index_base` or mapping hints

    * e.g. index of the first edge row in `edge_catalogue_3B` for this merchant, to allow trivial alias index → edge row mapping.

* **Global summary row(s)**:

  * `scope = "GLOBAL"` (per schema) with `merchant_id = null` (or a documented special value), per schema;
  * MUST include at least:

    * `edge_count_total_all_merchants`;
    * `blob_length_bytes` (mirror of header);
    * `blob_sha256_hex`;
    * optional component digests used by `edge_universe_hash_3B` (or those may live solely in that descriptor).

4.3.3 Identity & partitioning:

* `edge_alias_index_3B` MUST be partitioned by:

  * `seed={seed}`
  * `fingerprint={manifest_fingerprint}`

* The normative `path` SHALL be defined in the 3B dictionary, i.e.:
  `data/layer1/3B/edge_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_index_3B.parquet`

* `ordering` MUST follow the declared primary keys, i.e. `["scope","merchant_id"]` with any composite merchant key encoded consistently across 3B.

4.3.4 Structural invariants:

* There MUST be exactly one per-merchant index row for each `merchant_id` that appears in `edge_catalogue_3B` for that `{seed, fingerprint}`.
* `edge_count_total_all_merchants` MUST equal the sum of `edge_count_total` over all per-merchant rows and the row count in `edge_catalogue_3B`.
* For each merchant, `(blob_offset_bytes, blob_length_bytes)` MUST refer to a contiguous alias segment inside `edge_alias_blob_3B` that decodes without error under the alias layout.
* Checksums MUST verify when recomputed over those segments.

---

4.4 **Universe hash descriptor: `edge_universe_hash_3B`**

4.4.1 `edge_universe_hash_3B` SHALL be a fingerprint-scoped JSON descriptor that defines the **virtual edge universe hash** and records the component digests that contribute to it. It is the binding contract for “what edge + alias universe 2B should see” for this manifest.

4.4.2 At minimum, `edge_universe_hash_3B` MUST include:

* `manifest_fingerprint` — identity of the manifest being described;
* `parameter_hash` — (optional but recommended) identity of the governed 3B/edge parameter set;
* `edge_universe_hash` — hex digest (e.g. SHA-256) representing the combined virtual edge universe;
* `components` — an object or array capturing at least:

  * `cdn_policy_id`, `cdn_policy_version`, `cdn_policy_digest`;
  * `spatial_surface_ids` and their digests (e.g. tile surface and raster digests as sealed upstream);
  * `rng_policy_id` / `rng_policy_version` (compatibility reference);
  * `alias_layout_policy_id` / `alias_layout_policy_version`;
  * `edge_catalogue_digest_global` (from `edge_catalogue_index_3B` or recomputed);
  * `edge_alias_blob_sha256_hex` (digest over `edge_alias_blob_3B`);
  * `edge_alias_index_sha256_hex` (digest over `edge_alias_index_3B`).

4.4.3 The combination law for `edge_universe_hash` MUST be:

* deterministic and fully specified (e.g. “concatenate component digests in ASCII-sorted key order of `components` and hash with SHA-256”);
* stable under re-runs and independent of filesystem ordering.

4.4.4 Identity & partitioning:

* `edge_universe_hash_3B` MUST be fingerprint-only:

  * `path: data/layer1/3B/edge_universe_hash/fingerprint={manifest_fingerprint}/edge_universe_hash_3B.json`

  * `partitioning: ["fingerprint"]`.

* No `seed` partition is allowed. The descriptor is **global to the manifest** (and implicit across all seeds) for the virtual edge universe; if multiple seeds are used, S3 MUST define and document whether `edge_universe_hash` is expected to be seed-invariant or per-seed and adjust the design accordingly.

4.4.5 `edge_universe_hash_3B` MUST be readable and sufficient for:

* 2B to confirm “the alias tables I’m decoding match the S3-signed universe”;
* the 3B validation state to recompute or verify `edge_universe_hash` from its components.

---

4.5 **Optional S3 run-summary / receipt**

4.5.1 If the design includes an S3 run-summary dataset (e.g. `s3_run_summary_3B`), it MUST be declared in `schemas.3B.yaml` and the 3B dictionary with:

* `schema_ref: schemas.3B.yaml#/validation/s3_run_summary_3B`;
* `path: data/layer1/3B/s3_run_summary/fingerprint={manifest_fingerprint}/s3_run_summary_3B.json` (or similar);
* `partitioning: ["fingerprint"]`.

4.5.2 Such a summary MAY capture:

* S3 `status ∈ {"PASS","FAIL"}`;
* `error_code` (if any);
* `virtual_merchant_count`;
* `edge_count_total_all_merchants` (echo from S2 index);
* `alias_blob_length_bytes`;
* `edge_universe_hash`;
* references to paths of S2 and S3 outputs.

4.5.3 This summary is **informative**: it does not replace any of the binding artefacts above, and its absence MUST NOT change the semantics of S3; correctness is governed by the alias blob, alias index, and universe-hash descriptor.

---

4.6 **Identity echoes & path↔embed equality**

4.6.1 S3 outputs MAY include identity echo fields in their schemas (e.g. `seed`, `manifest_fingerprint`, `parameter_hash`) as non-key columns. If present, S3 MUST:

* populate them with values matching the run identity;
* ensure that they match the values in `s0_gate_receipt_3B`;
* not use them as partition keys (except `fingerprint` for `edge_universe_hash_3B`).

4.6.2 Path↔embed equality checks (i.e. confirming that embedded identity equals partition identity) are typically enforced by the 3B validation state, not by S3 itself, but S3 MUST write outputs in a way that makes such checks pass.

---

4.7 **Immutability & idempotence of S3 outputs**

4.7.1 For a fixed `{seed, parameter_hash, manifest_fingerprint}`, the following S3 artefacts are **logically immutable**:

* `edge_alias_blob_3B@seed={seed}, fingerprint={manifest_fingerprint}`;
* `edge_alias_index_3B@seed={seed}, fingerprint={manifest_fingerprint}`;
* `edge_universe_hash_3B@fingerprint={manifest_fingerprint}`.

4.7.2 Once S3 has successfully published these artefacts:

* any subsequent run of S3 for the same identity triple MUST:

  * recompute expected outputs;
  * compare them (by bytes or via a documented digest method) to the existing artefacts;
  * if identical, treat the run as idempotent and leave artefacts unchanged;
  * if different, fail with a conflict error and MUST NOT overwrite existing artefacts.

4.7.3 S3 MUST publish its outputs using an **atomic publish** protocol:

* blob and index MUST be written to temporary locations and moved into place together, without exposing a state in which only one is updated;
* `edge_universe_hash_3B` MUST only be written after both blob and index are present and final;
* partial or mixed-version visibility of S3 outputs MUST be treated as invalid by downstream states.

4.7.4 Any implementation that:

* mutates S3 outputs in place without idempotent comparison;
* diverges from the partition law described here;
* or allows partial publication of S3 outputs,

is **non-conformant** with this specification and MUST be corrected under the change-control rules in §12.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

5.1 **`edge_alias_blob_3B` - blob contract**

5.1.1 The alias blob **`edge_alias_blob_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with at least:

* `id: edge_alias_blob_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/binary/edge_alias_blob_header_3B`
* `path: data/layer1/3B/edge_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_blob_3B.bin`
* `partitioning: [seed, fingerprint]`
* `ordering: []` (blob is a single binary file per `{seed,fingerprint}`; sort concept is N/A)

5.1.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* set `name: edge_alias_blob_3B` (matching the dictionary `id`) and reuse the same schema anchor + path tokens;
* declare `type: "dataset"`, the applicable `category` (e.g. `virtual_edges`), `owner`, and runtime environment metadata;
* provide a stable `manifest_key` such as `"mlr.3B.edge_alias_blob_3B"`;
* list known consumers: at minimum 3B.S3 validation, the 3B segment-level validation state, and 2B's virtual routing implementation, along with retention/licensing policy.

5.1.3 `schemas.3B.yaml#/binary/edge_alias_blob_header_3B` MUST define the **header structure** for the blob. At minimum, the header schema MUST include:

* `layout_version` — string or integer enum identifying the alias layout version;
* `endianness` — enum, e.g. `{"little","big"}`;
* `alignment_bytes` — integer ≥ 1;
* `blob_length_bytes` — integer total length of the blob;
* `blob_sha256_hex` — SHA-256 digest of the blob content (canonical definition MUST be documented: e.g. hash over all bytes after a fixed-length header, or entire file except a reserved digest field);
* `alias_layout_policy_id` — string logical ID;
* `alias_layout_policy_version` — string/semver;
* OPTIONAL reserved fields (must be schema-optional, not used to carry semantics without a spec update).

5.1.4 The header schema MAY also include:

* `merchant_count` — number of merchants with alias tables;
* `edge_count_total_all_merchants` — echo of S2’s global edge count;
* `index_digest_hex` — digest of `edge_alias_index_3B` (if S3 chooses to echo it in the blob header).

If present, these fields are binding and MUST be kept consistent with S2/S3 datasets and digests.

5.1.5 The schema for `edge_alias_blob_3B` MUST define:

* the header type and size;
* constraints on the **payload region** (e.g. “the rest of the file after the header is opaque binary alias data, interpreted according to `layout_version`”).

The structure of per-merchant alias tables (probability format, alias format, padding) is governed by the alias-layout policy; S3 MUST obey that policy, but JSON-Schema will only model the header, not the entire binary payload.

---

5.2 **`edge_alias_index_3B` - index contract**

5.2.1 The dataset **`edge_alias_index_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with at least:

* `id: edge_alias_index_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/plan/edge_alias_index_3B`
* `path: data/layer1/3B/edge_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_index_3B.parquet`
* `partitioning: [seed, fingerprint]`
* `ordering: ["scope","merchant_id"]`

  * or `["scope","merchant_key"]` if a composite key is used consistently across 3B; the spec MUST be explicit.

5.2.2 The matching entry in `artefact_registry_3B.yaml` MUST:

* set `name: edge_alias_index_3B` and reuse the same schema anchor/path tokens;
* declare `type: "dataset"`, include `category`, `owner`, `semver`/`version`, and runtime environment metadata;
* provide a stable `manifest_key` (e.g. `"mlr.3B.edge_alias_index_3B"`);
* list primary consumers: 3B.S3 validation, 3B segment validation, and 2B's routing/decoder.

5.2.3 `schemas.3B.yaml#/plan/edge_alias_index_3B` MUST define a table-shaped dataset with at least:

* **Common fields**

  * `layout_version`

    * type: same as blob header;
    * MUST match `edge_alias_blob_3B.header.layout_version`.

* **Per-merchant index rows** (keyed by `merchant_id` / `merchant_key`):

  * `merchant_id` (or `merchant_key`)

    * type: as used in S1/S2;
    * semantics: joins to S2’s `edge_catalogue_3B` and S1’s outputs.

  * `edge_count_total`

    * integer;
    * MUST equal the number of rows in `edge_catalogue_3B` for this merchant.

  * `alias_table_length`

    * integer;
    * size of alias table (number of slots), as per alias layout (may be ≥ `edge_count_total` due to padding).

  * `blob_offset_bytes`

    * integer;
    * byte offset at which this merchant’s alias segment begins in `edge_alias_blob_3B`.

  * `blob_length_bytes`

    * integer;
    * byte length of this merchant’s alias segment.

  * `merchant_alias_checksum`

    * string hex;
    * checksum of this merchant’s alias segment according to alias-layout policy (e.g. SHA-256, CRC32).

  * OPTIONAL: `edge_index_base`

    * integer;
    * starting index in merchant’s edge list, if the alias layout expects “alias index i maps to edge at position `edge_index_base + i`” in some canonical ordering.

* **Global summary row(s)**

  * `scope = "GLOBAL"` (per schema) with `merchant_id = null` (or schema-defined sentinel).
  * MUST include:

    * `edge_count_total_all_merchants` — total edges, equals S2’s global count;
    * `blob_length_bytes` — echo of blob header;
    * `blob_sha256_hex` — echo of blob header;
    * OPTIONAL: `edge_catalogue_digest_global` — from S2 index;
    * OPTIONAL: `edge_alias_blob_sha256_hex` / `edge_alias_index_sha256_hex` — if not available elsewhere.

5.2.4 Structural constraints:

* `(merchant_id)` MUST be unique over merchant rows within a `{seed,fingerprint}` partition.
* For each merchant row, `(blob_offset_bytes, blob_length_bytes)` MUST refer to a contiguous region of `edge_alias_blob_3B` within the data length specified by the blob header.
* `edge_count_total_all_merchants` MUST equal Σ `edge_count_total` over merchant rows and MUST equal S2’s global edge count for that partition.

---

5.3 **`edge_universe_hash_3B` — universe hash descriptor**

5.3.1 The descriptor **`edge_universe_hash_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with:

* `id: edge_universe_hash_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/validation/edge_universe_hash_3B`
* `path: data/layer1/3B/edge_universe_hash/fingerprint={manifest_fingerprint}/edge_universe_hash_3B.json`
* `partitioning: ["fingerprint"]`
* `ordering: []` (single JSON doc per fingerprint)

5.3.2 The registry entry MUST:

* set `name: edge_universe_hash_3B` and reuse the same schema anchor + path tokens;
* declare `type: "dataset"`, include category/owner metadata, and provide runtime environment details;
* provide a `manifest_key` such as `"mlr.3B.edge_universe_hash_3B"`;
* list consumers: 2B virtual routing, 3B validation, 4A/4B-style harness.

5.3.3 `schemas.3B.yaml#/validation/edge_universe_hash_3B` MUST define an object with at least:

* `manifest_fingerprint`

  * type: as per `schemas.layer1.yaml#/validation/manifest_fingerprint_resolved`;
  * MUST equal partition `fingerprint`.

* `parameter_hash` (optional but recommended)

  * type: as per `schemas.layer1.yaml#/validation/parameter_hash_resolved`;
  * MUST equal S0’s `parameter_hash` if present.

* `edge_universe_hash`

  * type: hex string;
  * combined digest of all components (hashing law documented in §6).

* `components` — object containing at minimum:

  * `cdn_policy_id`, `cdn_policy_version`, `cdn_policy_digest`;
  * `alias_layout_policy_id`, `alias_layout_policy_version`;
  * `rng_policy_id`, `rng_policy_version` (compatibility reference only);
  * `spatial_surface_ids` and their digests (if included);
  * `edge_catalogue_digest_global` (from S2 index or recomputed);
  * `edge_alias_blob_sha256_hex`;
  * `edge_alias_index_sha256_hex`.

5.3.4 The schema MUST:

* fix `edge_universe_hash` to a specific digest size (e.g. 64-char hex SHA-256) and encode allowed algorithms;
* constrain `components` keys and types;
* document that 2B and validation rely on this schema to verify universe hash consistency.

---

5.4 **`gamma_draw_log_3B` — observability contract (expected empty)**

5.4.1 `dataset_dictionary.layer1.3B.yaml` lists `gamma_draw_log_3B` with:

* `id: gamma_draw_log_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/validation/gamma_draw_log_entry_3B`
* `path: logs/layer1/3B/gamma_draw/seed={seed}/fingerprint={manifest_fingerprint}/gamma_draw_log_3B.jsonl`
* `partitioning: [seed, fingerprint]`
* `ordering: [merchant_id, day_index]`

5.4.2 S3 is RNG-free, so this dataset functions purely as a **guardrail**:

* S3 MUST publish the log partition (even if empty) so validation can assert "no gamma draws occurred".
* The file SHOULD contain zero records; **any** record or non-empty shard constitutes `E3B_S3_RNG_USED` and is treated as a fatal contract violation.
* Downstream infrastructure MAY compress or omit the physical file entirely if no events were written, provided the publish protocol proves emptiness (e.g. zero-byte file plus digest entry).

5.4.3 If a future S3 design legitimately requires gamma draws, this spec MUST be revised (including §1.3) and the dictionary/registry updated to reflect the non-empty usage; until then, `gamma_draw_log_3B` exists solely to prove S3’s RNG-free status.

---

5.5 **Catalogue links & discoverability**

5.4.1 All S3 outputs MUST be **discoverable** via the dataset dictionary and artefact registry:

* Datasets: `edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B` entries in `dataset_dictionary.layer1.3B.yaml`;
* Artefacts: corresponding entries in `artefact_registry_3B.yaml` with stable manifest keys and explicit 3B ownership metadata.

5.4.2 S3 MUST NOT hard-code paths or bypass the catalogue. It MUST:

* use `dataset_dictionary.layer1.3B.yaml` to construct paths from `id`, `path`, and `partitioning`;
* use `artefact_registry_3B.yaml` to determine ownership, licence class and retention policy for its outputs.

5.4.3 Any new S3-owned dataset (e.g. `s3_run_summary_3B` or an intermediate persisted planning table) is only valid if:

* it has an `id`, `schema_ref`, `path`, `partitioning`, and `ordering` declared in the dataset dictionary;
* it has a corresponding registry entry;
* it is included explicitly in this spec when used in a binding way.

---

5.5 **Input anchors & cross-segment references**

5.5.1 S3’s dataset schemas MUST reference upstream and S2 inputs via their canonical schema anchors, e.g.:

* `virtual_classification_3B` — `schemas.3B.yaml#/egress/virtual_classification_3B`;
* `virtual_settlement_3B` — `schemas.3B.yaml#/egress/virtual_settlement_3B`;
* `edge_catalogue_3B` — `schemas.3B.yaml#/egress/edge_catalogue_3B`;
* `edge_catalogue_index_3B` — `schemas.3B.yaml#/egress/edge_catalogue_index_3B`;
* alias-layout policy — `schemas.3B.yaml#/policy/edge_alias_layout_policy` (or equivalent);
* RNG/routing policy — `schemas.layer1.yaml#/rng/policy` or a 3B-local policy schema that references the layer RNG spec.

5.5.2 `dataset_dictionary.layer1.3B.yaml` MUST declare S1/S2 outputs as S3 inputs, with:

* `consumed_by` or equivalent metadata indicating that S3 reads them;
* `schema_ref` pointing to their owning segment schemas.

5.5.3 S3 MUST treat these anchors as the authoritative descriptions of input shapes and MUST NOT assume alternate shapes for inputs beyond those schemas.

---

5.6 **Binding vs informative elements**

5.6.1 The following are **binding** requirements in this section:

* Existence and names of `edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`.
* Their `schema_ref`, `path`, `partitioning`, and registration in dictionary + registry.
* The requirement that `edge_alias_blob_3B` includes a header with at least the fields described in §5.1.3.
* The requirement that `edge_alias_index_3B` includes, at minimum, the per-merchant and global fields described in §5.2.3.
* The requirement that `edge_universe_hash_3B` includes `manifest_fingerprint`, `edge_universe_hash`, and the component digests listed in §5.3.3 (subject to minor, backwards-compatible extensions).

5.6.2 Optional fields (e.g. extra diagnostics in index or hash descriptor) are binding only in the sense that, if defined in schema, S3 MUST populate them consistently. Their presence MUST NOT alter the semantics of existing required fields.

5.6.3 If any discrepancy exists between this section and:

* `schemas.3B.yaml`
* `dataset_dictionary.layer1.3B.yaml`
* `artefact_registry_3B.yaml`

then those contracts SHALL be treated as authoritative. This section MUST be updated in the next non-editorial revision to match the actual contracts in force.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

6.1 **Phase overview**

6.1.1 S3 SHALL implement a single deterministic, RNG-free algorithm composed of the following phases:

* **Phase A — Environment & input load (RNG-free)**
  Validate S0 gate, load contracts and sealed artefacts, and load S1/S2 outputs for the target `{seed, manifest_fingerprint}`.

* **Phase B — Per-merchant edge list & weight preparation (RNG-free)**
  Derive canonical, ordered per-merchant edge lists and quantised weights from `edge_catalogue_3B` and alias-layout policy.

* **Phase C — Per-merchant alias table construction (RNG-free)**
  For each merchant, construct an alias table over its edges using a deterministic algorithm and the quantised weights.

* **Phase D — Blob layout & index construction (RNG-free)**
  Lay out all alias tables into a contiguous blob, compute per-merchant offsets/lengths/checksums, and build `edge_alias_index_3B`.

* **Phase E — Digest computation & edge universe hash assembly (RNG-free)**
  Compute digests for S2/S3 artefacts and policies, combine them into `edge_universe_hash`, and build `edge_universe_hash_3B`.

* **Phase F — Output materialisation & internal validation (RNG-free)**
  Serialize and atomically publish `edge_alias_blob_3B`, `edge_alias_index_3B`, and `edge_universe_hash_3B`, after verifying internal consistency.

6.1.2 No phase MAY:

* open or advance any RNG stream;
* emit RNG events;
* use non-deterministic sources (e.g. wall-clock time, process ID, unordered filesystem iteration) as part of its decision logic.

6.1.3 All steps MUST be pure functions of:

* `{seed, parameter_hash, manifest_fingerprint}` (identity only; no stochastic use);
* S0’s sealed inputs;
* S1/S2 outputs;
* alias-layout and RNG/routing policy artefacts;
* and the deterministic laws defined in this specification.

---

6.2 **Phase A — Environment & input load (RNG-free)**

6.2.1 S3 MUST perform the precondition checks in §§2–3, including:

1. Load and validate `s0_gate_receipt_3B` and `sealed_inputs_3B`.
2. Confirm identity alignment: `{seed, parameter_hash, manifest_fingerprint}` in S3 matches S0.
3. Confirm upstream gates (1A, 1B, 2A, 3A) are `status="PASS"`.
4. Load or confirm `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, `artefact_registry_3B.yaml` as a compatible triplet.
5. Resolve, from `sealed_inputs_3B`, and validate:

   * alias-layout policy for edges;
   * RNG/routing policy artefact(s) relevant to alias decoding;
   * any policy digests that must feed into the universe hash.

6.2.2 S3 MUST load and validate the following S1/S2 outputs for `{seed, manifest_fingerprint}`:

* `virtual_classification_3B`;
* `virtual_settlement_3B`;
* `edge_catalogue_3B`;
* `edge_catalogue_index_3B`.

6.2.3 S3 MUST verify the minimal S1/S2 invariants needed for alias construction:

* Every edge row in `edge_catalogue_3B` has a valid `merchant_id` and `edge_weight`;
* For each merchant appearing in `edge_catalogue_3B`, `virtual_classification_3B` indicates it is virtual (or the configuration explicitly allows otherwise);
* Per-merchant and global counts in `edge_catalogue_index_3B` match row counts in `edge_catalogue_3B`.

If any invariant is violated, S3 MUST fail with a S1/S2-contract error and MUST NOT proceed.

---

6.3 **Phase B — Per-merchant edge list & weight preparation (RNG-free)**

6.3.1 Canonical ordering of edges

6.3.1.1 S3 MUST derive per-merchant edge lists from `edge_catalogue_3B` in a **canonical order**. The normative rule is:

* first sort `edge_catalogue_3B` by `merchant_id` (or `merchant_key`) ascending,
* then by `edge_id` ascending,

and treat this sorted order as the per-merchant edge order.

6.3.1.2 For each merchant `m` present in `edge_catalogue_3B`, S3 MUST build:

* a sequence of edge identifiers `E_m = (e₀, e₁, …, eₙ₋₁)` in the canonical order;
* the corresponding sequence of raw weights `w_raw(m, i)` = `edge_weight(eᵢ)`.

6.3.2 Handling of empty and degenerate cases

6.3.2.1 If a merchant appears in the virtual set `V` but has `edge_count_total = 0` in `edge_catalogue_index_3B`:

* behaviour MUST follow the semantics described in §8 (e.g. no-edge mode).
* In **default full-edge mode**, this situation MUST be treated as a configuration error and S3 MUST fail.

6.3.2.2 For merchants with exactly one edge in `E_m` (i.e. `n = 1`):

* S3 MUST still construct a valid alias table, typically with a single slot that deterministically picks that edge with probability 1.

6.3.3 Weight normalisation

6.3.3.1 For each merchant `m`, S3 MUST compute a non-negative weight vector from `w_raw(m, i)`. Let:

* `w_pos(m, i) = max(w_raw(m,i), 0)` (if negative weights are not allowed, S3 MUST fail; if a policy permits small negative weights to be clamped, that MUST be codified in the alias-layout policy).

6.3.3.2 Define:

* `Z_m = Σᵢ w_pos(m, i)`.

If `Z_m ≤ 0` and `|E_m| > 0`, S3 MUST either:

* treat this as a FATAL error (preferred), or
* follow a documented fallback in the alias-layout policy (e.g. uniform weighting over edges), in which case S3 MUST set `w_norm(m,i) = 1/|E_m|` and record that behaviour as part of `decision_reason`/metadata if the schema supports it.

6.3.3.3 When `Z_m > 0`, S3 MUST normalise:

* `w_norm(m, i) = w_pos(m, i) / Z_m`.

The numeric policy (rounding, allowed tolerances) MUST align with the Layer-1 numeric profile and any alias-layout policy requirements.

6.3.4 Quantisation to alias grid

6.3.4.1 Alias-layout policy MUST specify:

* an integer grid size `G` (e.g. `G = 2ᵇ` for some `b`, or a fixed integer `G = 10^d`), and
* an allowed maximum discrepancy between `w_norm` and quantised masses.

6.3.4.2 For each merchant `m`, S3 MUST:

1. Compute real-valued targets:

   * `M_target(m, i) = G * w_norm(m, i)`.

2. Compute base integer masses:

   * `M_base(m, i) = floor(M_target(m, i))`.

3. Compute residual capacity:

   * `R_m = G − Σᵢ M_base(m, i)`.

4. Compute residuals:

   * `r(m, i) = M_target(m, i) − M_base(m, i)`.

5. Rank indices `i` in descending `r(m, i)` with deterministic tie-break:

   * larger `r(m, i)` first;
   * ties broken by ascending `edge_id(eᵢ)`;
   * any remaining tie (theoretically impossible under exact arithmetic) by ascending index `i`.

6. Assign +1 to the top `R_m` entries:

   * `M(m, i) = M_base(m, i) + [i among top R_m]`.

6.3.4.3 S3 MUST enforce:

* `M(m, i) ≥ 0` for all `i`;
* Σᵢ `M(m, i) = G` for each merchant;
* the discrepancy between `w_norm(m, i)` and `M(m,i)/G` is within alias-layout policy tolerance.

If these constraints cannot be satisfied (e.g. due to pathological weights or over-tight tolerances), S3 MUST fail with a budget/quantisation error.

6.3.4.4 `M(m, i)` is the canonical mass vector used for alias construction. S3 MUST NOT re-normalise or adjust this vector in subsequent phases, except as required by the alias algorithm (which preserves sums).

---

6.4 **Phase C — Per-merchant alias table construction (RNG-free)**

6.4.1 Canonical edge index mapping

6.4.1.1 For each merchant `m`, S3 MUST define a canonical mapping:

* `i ∈ {0,…,n−1}` ↔ edge `eᵢ` (in the canonical order from §6.3.1).

6.4.1.2 Alias tables (prob/alias arrays) MUST index edges via this mapping. 2B’s decoder MUST be able to map alias-table index `i` back to the underlying `edge_id` either:

* via a known ordering agreed between S2 and S3 (e.g. sorted by `edge_id`), or
* via additional metadata (e.g. per-merchant `edge_index_base` plus an implicit contiguous edge slice in `edge_catalogue_3B`).

6.4.2 Handling degenerate cases

6.4.2.1 If `|E_m| = 0` in a mode that allows merchants with no edges:

* S3 MUST NOT construct an alias table for `m`, and
* MUST either omit `m` from `edge_alias_index_3B` or mark it explicitly as `edge_count_total = 0` with no blob segment, as the schema and configuration dictate.

6.4.2.2 If `|E_m| = 1` and `G > 0`:

* S3 MUST construct an alias table that deterministically picks the single edge. A normative representation is a table of length 1 with:

  * `prob_int[0] = G` (or equivalent full-mass code),
  * `alias[0] = 0`.

6.4.3 Deterministic alias algorithm (multi-edge case)

6.4.3.1 For merchants with `n ≥ 2` and mass vector `M(m,i)`:

1. Construct per-index probabilities on the grid:

   * let `G` be the grid total;
   * define `p_grid(i) = M(m,i)`;
   * define `p_float(i) = M(m,i) / G`.

2. Partition indices into:

   * `L = { i | p_grid(i) < G/n }` (“small”);
   * `H = { i | p_grid(i) > G/n }` (“large”);
   * `E = { i | p_grid(i) = G/n }` (exactly equal).

The threshold `G/n` MUST be integer or handled by a deterministic policy declared in alias layout.

3. Use a deterministic alias-table construction (Walker/Vose), with a **fixed, deterministic stack/queue discipline**, e.g.:

   * represent `L` and `H` as queues of indices sorted ascending by `i`;
   * repeatedly pop `i` from the head of `L` and `j` from the head of `H`;
   * set table entry for `i` as:

     * `prob_int(i) = p_grid(i)`;
     * `alias(i) = j`;
   * update `p_grid(j) = p_grid(j) + p_grid(i) − G/n`;
   * reinsert `j` into `L`, `H` or `E` based on its updated value, maintaining queue ordering.

4. After `L` is empty, for any remaining indices (in `H` and `E`), set:

   * `prob_int(i) = G/n` (or the canonical “full bucket” value given the quantisation law);
   * `alias(i) = i` (self-alias), or another deterministic convention described in the alias-layout policy.

6.4.3.2 S3 MUST ensure:

* the algorithm’s data-structure behaviour (queue vs stack, ordering of `L` and `H`) is fully specified and independent of implementation details;
* the resulting alias table is deterministic for a given `M(m,i)`;
* no RNG is used in any step.

6.4.4 Validity and invariants of alias tables

6.4.4.1 S3 MUST confirm, at least conceptually (and may rely on S3 validation state to check programmatically), that for each merchant:

* alias table indices cover `{0,…, alias_table_length−1}`;
* the implied distribution over indices matches `M(m,i)/G` up to the tolerances specified in the alias-layout policy.

6.4.4.2 Any merchant-level anomalies (e.g. impossible alias construction under specified constraints) MUST cause S3 to fail with an alias-construction error, rather than degrade or skip that merchant silently.

---

6.5 **Phase D — Blob layout & index construction (RNG-free)**

6.5.1 Merchant ordering

6.5.1.1 S3 MUST choose a canonical order over merchants for packing alias tables and writing index rows. The normative rule is:

* merchants sorted ascending by `merchant_id` (or by composite `merchant_key` as declared in schema).

6.5.2 Blob layout

6.5.2.1 Given:

* alias-layout header fields (layout_version, endianness, alignment_bytes, etc.), and
* per-merchant alias tables,

S3 MUST:

1. Serialize the blob header according to `schemas.3B.yaml#/binary/edge_alias_blob_header_3B` and the alias-layout policy.

2. Let `offset₀ = header_length_bytes`. Initialise a running offset `off = offset₀`.

3. For each merchant `m` in canonical order:

   * determine the alias segment byte length `len_m` according to the alias layout (e.g. `len_m = alias_table_length * element_size * 2 + per-merchant-header-size`);

   * apply alignment if required:

     * let `pad = (alignment_bytes − (off mod alignment_bytes)) mod alignment_bytes`;
     * increment `off = off + pad`;
     * per-merchant index MUST record padding implicitly via `blob_offset_bytes = off`.

   * write the merchant’s alias segment at `off`;

   * advance `off = off + len_m`.

4. After all merchants, set `blob_length_bytes = off` (or apply any required final padding as per policy).

6.5.2.2 Once the payload region is constructed, S3 MUST compute:

* `blob_sha256_hex` over the defined region (e.g. entire file including header, or header-excluded region, according to policy), and write it into the header.

6.5.3 Index construction

6.5.3.1 In parallel with packing the blob, S3 MUST construct `edge_alias_index_3B` rows.

For each merchant `m` in canonical order:

* `merchant_id` (or `merchant_key`) from S2;
* `edge_count_total` from `edge_catalogue_index_3B` (or from counting in `edge_catalogue_3B`);
* `alias_table_length` — number of slots in merchant’s alias table;
* `blob_offset_bytes` — value of `off` at which the alias segment was written (post-alignment);
* `blob_length_bytes` — `len_m` as above;
* `merchant_alias_checksum` — computed over the alias segment according to alias layout policy (e.g. SHA-256 or CRC32);
* `layout_version` — echo of the blob header.

6.5.3.2 S3 MUST also create one or more **global summary row(s)** (per §5.2), containing:

* `edge_count_total_all_merchants` (sum over merchants);
* `blob_length_bytes` and `blob_sha256_hex` (echo of header);
* optionally `edge_catalogue_digest_global` (from S2 index) and S3-specific digests.

6.5.3.3 `edge_alias_index_3B` MUST be written in a stable writer sort:

* per-merchant rows sorted by `merchant_id` ascending;
* global summary row(s) positioned deterministically (e.g. at the top, bottom, or distinguished via `scope`), as defined by the schema.

---

6.6 **Phase E — Digest computation & edge universe hash (RNG-free)**

6.6.1 Component digests

6.6.1.1 S3 MUST collect or compute the following component digests (as applicable):

* `cdn_policy_digest` — from sealed CDN policy artefact(s) (from S0 or recomputed by S3);
* `spatial_surface_digests` — digests of spatial surfaces used by S2, if included;
* `rng_policy_digest` — digest of relevant RNG/routing policy artefact(s);
* `alias_layout_policy_digest` — digest of the alias-layout policy;
* `edge_catalogue_digest_global` — from S2’s index or recomputed;
* `edge_alias_blob_sha256_hex` — digest computed in Phase D;
* `edge_alias_index_sha256_hex` — digest of `edge_alias_index_3B` computed by S3 using a canonical path/digest law.

6.6.2 Universe hash law

6.6.2.1 The **virtual edge universe hash** MUST be defined by a canonical combination law. A normative example:

1. Construct a JSON-like object or ordered list `L` of component `(name, digest)` pairs, where `name` is a stable string key (e.g. `"cdn_policy"`, `"alias_layout"`, `"rng_policy"`, `"spatial_surface:<id>"`, `"edge_catalogue"`, `"edge_alias_blob"`, `"edge_alias_index"`).

2. Sort `L` in ascending ASCII-lex order by `name`.

3. Concatenate the `digest` values in this sorted order into a byte string `B` (e.g. interpret each hex digest as bytes and concatenate).

4. Compute `edge_universe_hash = SHA256(B)` and encode as lower-case hex.

6.6.2.2 The exact combination law (component names, order, mandatory vsoptional components) MUST be defined in the 3B/S3 spec and encoded in `schemas.3B.yaml#/validation/edge_universe_hash_3B` documentation. S3 MUST implement it exactly and MUST NOT leave aspects implicit.

6.6.3 Universe hash descriptor

6.6.3.1 S3 MUST construct `edge_universe_hash_3B` as per §5.3, populating:

* `manifest_fingerprint`, `parameter_hash` (if included);
* `edge_universe_hash`;
* a `components` map/array with each component digest and any version/ID metadata.

6.6.3.2 S3 MUST ensure that the values used to compute `edge_universe_hash` are exactly those recorded in `components`. Any mismatch MUST be treated as an internal error.

---

6.7 **Phase F — Output materialisation & internal validation (RNG-free)**

6.7.1 Internal validation before publish

6.7.1.1 Before publishing outputs, S3 MUST perform at least the following checks:

* Blob header values (`layout_version`, `blob_length_bytes`, `blob_sha256_hex`) match the actual blob content.
* For each merchant row in `edge_alias_index_3B`:

  * `edge_count_total` equals count of edges for that merchant in `edge_catalogue_3B`;
  * `blob_offset_bytes + blob_length_bytes` is within the blob length;
  * recalculated `merchant_alias_checksum` over the alias segment matches the stored value.
* Global summary:

  * `edge_count_total_all_merchants` equals sum of per-merchant `edge_count_total` and S2’s global edge count;
  * `blob_sha256_hex` matches the blob header.

6.7.1.2 S3 MUST validate:

* `edge_alias_index_3B` against its JSON-Schema;
* `edge_universe_hash_3B` against its JSON-Schema;
* any optional S3 run-summary outputs against their schemas.

6.7.2 Atomic publish

6.7.2.1 S3 MUST write outputs using an atomic publish protocol for each `{seed, manifest_fingerprint}`:

1. Write `edge_alias_blob_3B` to a temporary location (e.g. `edge_alias_blob_3B.bin.tmp`), fully sync/flushed.
2. Write `edge_alias_index_3B` to a temporary location (e.g. `index.tmp/…`).
3. Write `edge_universe_hash_3B` to a temporary location (e.g. `edge_universe_hash_3B.tmp.json`).
4. Validate all three artefacts in-place (as in 6.7.1).
5. Move/rename temporary artefacts into their canonical paths:

   * `edge_alias_blob_3B.bin.tmp` → `edge_alias_blob_3B.bin` under `edge_alias_blob_3B` path;
   * `index.tmp/…` → final `edge_alias_index_3B` directory;
   * `edge_universe_hash_3B.tmp.json` → final `edge_universe_hash_3B.json` path.

6.7.2.2 If any step in this pipeline fails (write error, schema violation, checksum mismatch), S3 MUST:

* abort publication;
* ensure that partial outputs (temp files) are not treated as canonical;
* report a FATAL error and require a fresh S3 run once underlying issues are resolved.

6.7.3 Idempotence on re-run

6.7.3.1 If S3 is re-run for the same `{seed, parameter_hash, manifest_fingerprint}` and S3 outputs already exist:

* S3 MAY recompute expected alias blob, index and universe hash;
* S3 MUST compare recomputed digests (or bytes) with existing artefacts:

  * if identical, S3 MAY treat the run as idempotent and return PASS without rewriting;
  * if different, S3 MUST treat this as an inconsistency (`E3B_S3_OUTPUT_INCONSISTENT_REWRITE` or equivalent), log it, and MUST NOT overwrite the existing artefacts.

6.7.3.2 Any deviation between expected and existing outputs under unchanged inputs MUST be treated as a determinism or environment-drift bug and corrected via:

* environment restoration and/or
* recomputation under a new `manifest_fingerprint` with updated contracts.

6.7.4 Prohibited behaviours

6.7.4.1 S3 MUST NOT:

* add or remove edges relative to `edge_catalogue_3B`;
* silently change edge weights;
* emit RNG events or use RNG;
* produce different alias blobs/indexes/universe hashes across re-runs with identical inputs.

Any implementation that does so is non-conformant and MUST be corrected under the change-control rules in §12.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

7.1 **Identity model for 3B.S3**

7.1.1 For S3, the **canonical run-identity triple** is:

* `seed`
* `parameter_hash`
* `manifest_fingerprint`

These MUST match the values recorded in `s0_gate_receipt_3B` for the same manifest.

7.1.2 For S3’s persisted outputs, the **primary on-disk identity** is:

* `{seed, manifest_fingerprint}` for **alias-table artefacts**:

  * `edge_alias_blob_3B`
  * `edge_alias_index_3B`

* `{manifest_fingerprint}` only for the **universe hash descriptor**:

  * `edge_universe_hash_3B`.

7.1.3 `parameter_hash` is part of the logical identity of the run, but:

* MUST NOT be used as a partition key for any S3 output;
* MAY appear as an identity echo column in schemas (if present, MUST match S0);
* MUST NOT influence the number or layout of partitions.

7.1.4 If `run_id` is used by the Layer-1 harness, it MAY:

* appear in logs and run-reports;
* be echoed in non-key fields of S3 outputs (e.g. `s3_run_summary_3B`),

but it MUST NOT:

* affect partitioning or file paths;
* influence alias construction or the universe hash;
* be used as an input to any digest that is supposed to be manifest-invariant.

---

7.2 **Partition law**

7.2.1 `edge_alias_blob_3B` MUST be partitioned **exactly** by:

* `seed={seed}`
* `fingerprint={manifest_fingerprint}`

The canonical path is of the form:

```text
data/layer1/3B/edge_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_blob_3B.bin
```

No additional partition keys (e.g. `parameter_hash`, `run_id`, or merchant-level sharding) are allowed unless **explicitly** added via a versioned change to the dataset dictionary and this spec.

7.2.2 `edge_alias_index_3B` MUST be partitioned **exactly** by:

* `seed={seed}`
* `fingerprint={manifest_fingerprint}`

with a canonical path of the form:

```text
data/layer1/3B/edge_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_index_3B.parquet
```

Again, no additional partition keys are allowed without a versioned contract change.

7.2.3 `edge_universe_hash_3B` MUST be **fingerprint-only**:

* `partitioning: ["fingerprint"]`
* canonical path of the form:

```text
data/layer1/3B/edge_universe_hash/fingerprint={manifest_fingerprint}/edge_universe_hash_3B.json
```

It MUST NOT be partitioned by `seed` or any other key. The descriptor is manifest-scoped, not seed-scoped.

7.2.4 For each `{seed, manifest_fingerprint}`:

* all files under `edge_alias_blob_3B`’s partition root constitute **one atomic blob artefact**;
* all files under `edge_alias_index_3B`’s partition root constitute **one atomic index artefact**.

Partial partitions (e.g. only some files, or incomplete index shards) MUST be treated as invalid.

---

7.3 **Primary keys, ordering & writer sort**

7.3.1 **Alias index primary keys**

Within a `{seed, fingerprint}` partition, `edge_alias_index_3B` MUST have:

* per-merchant rows keyed by `merchant_id` (or composite `merchant_key` if adopted consistently across 3B);
* zero or more global rows distinguished by a dedicated `scope` field or a special key value (e.g. `merchant_id = "__GLOBAL__"`), as defined in the schema.

The primary key for merchant rows is:

* `PK_edge_alias_index = (scope, merchant_id)` — with `scope = "MERCHANT"` for per-merchant rows and `"GLOBAL"` for summary rows.
  (or `(merchant_key)` for a composite key).

7.3.2 **Writer sort**

The **ordering** declared in the dictionary is binding and MUST be respected:

* `edge_alias_index_3B.ordering = ["scope","merchant_id"]` (or `["scope","merchant_key"]` if a composite key is adopted) with global rows clearly distinguished, as documented in the schema.
* `edge_alias_blob_3B.ordering = []`, since it is a single binary file; ordering constraints apply **within** the blob as per the alias layout policy (see below).

7.3.3 **Merchant and edge ordering discipline**

7.3.3.1 For alias construction and blob layout, S3 MUST:

* process merchants in a canonical order — normatively: ascending `merchant_id` (or ascending composite `merchant_key`);
* for each merchant, process edges in a canonical order — normatively: ascending `edge_id` from `edge_catalogue_3B` as described in S2/S3 contracts.

7.3.3.2 This ordering MUST be used consistently for:

* defining the mapping “alias table index → `edge_id`”;
* computing per-merchant digests;
* planning byte layouts and offsets.

7.3.3.3 No part of S3 MAY rely on:

* filesystem directory iteration order;
* hash-map iteration order;
* non-deterministic parallel scheduling

for merchant or edge ordering.

---

7.4 **Join discipline**

7.4.1 Natural join keys:

* Between `edge_alias_index_3B` and `edge_catalogue_3B`: join on `merchant_id` (and implicitly `{seed, fingerprint}` via partition);
* Between `edge_alias_index_3B` and S1 outputs: join on `merchant_id`;
* Between alias tables (as represented in `edge_alias_blob_3B`) and S2 edges: “alias table index” maps to the canonical per-merchant edge order `(e₀,…,eₙ₋₁)` defined from `edge_catalogue_3B`.

7.4.2 Any decoding or validation logic (in S3 validation state, 2B, or tooling) MUST:

* use these join keys;
* not rely on incidental join conditions (e.g. relying on numeric ordering of `edge_id` without using the canonical order definition);
* respect partition boundaries — joins MUST occur only between artefacts with the same `{seed, fingerprint}` (or same `fingerprint` for universe-hash joins).

7.4.3 S3 MUST ensure **no edges are “lost” in alias representation**:

* for each merchant `m` with `edge_count_total > 0`, every edge row in `edge_catalogue_3B` for `m` MUST correspond to at least one index in the alias table for `m` (possibly with zero mass only if such a case is explicitly permitted and documented);
* if the alias layout supports zero-weight slots, S3 MUST ensure the mapping from alias index to `edge_id` is still complete and deterministic.

---

7.5 **Immutability, idempotence & merge discipline**

7.5.1 S3 outputs are **logically immutable** for a given identity triple:

* Once S3 reports PASS and publishes:

  * `edge_alias_blob_3B@seed={seed}, fingerprint={manifest_fingerprint}`,
  * `edge_alias_index_3B@seed={seed}, fingerprint={manifest_fingerprint}`,
  * `edge_universe_hash_3B@fingerprint={manifest_fingerprint}`
* these artefacts MUST NOT be mutated in place.

7.5.2 On re-execution of S3 for the same `{seed, parameter_hash, manifest_fingerprint}`:

* S3 MAY recompute the alias blob, index and universe hash;

* S3 MUST compare recomputed results to existing artefacts:

  * either via direct byte comparison, or
  * via canonical digests (e.g. recomputed SHA-256 vs stored values);

* If identical, S3 MAY treat the run as a no-op and exit PASS without modifying artefacts;

* If different, S3 MUST fail with an “inconsistent rewrite” style error and MUST NOT overwrite previous results.

7.5.3 S3 MUST treat **blob + index + universe-hash** as an **all-or-nothing group** for a `{seed, fingerprint}`:

* It MUST NOT expose a state where:

  * `edge_alias_blob_3B` has been updated but `edge_alias_index_3B` has not (or vice versa), or
  * S2/S3 digests referenced in `edge_universe_hash_3B` do not match the underlying artefacts.

7.5.4 Any state observed by downstream consumers where:

* `edge_alias_blob_3B` exists but `edge_alias_index_3B` does not (or vice versa);
* `edge_universe_hash_3B` references digests that do not match recomputed values;
* identity echoes in artefacts do not match partition identity or `s0_gate_receipt_3B`;

MUST be treated as a 3B.S3 failure or environment corruption, not as a valid S3 output.

---

7.6 **Multi-manifest & multi-seed behaviour**

7.6.1 S3 MUST treat each `{seed, manifest_fingerprint}` partition independently:

* S3 does not impose any relationship between alias blobs for different seeds under the same manifest;
* S3 does not impose any relationship between different manifests.

7.6.2 `edge_universe_hash_3B` is fingerprint-only and MUST be defined in a way that matches the intended semantics:

* If the design is **seed-invariant** (preferred), the hash MUST be formed from artefacts that are seed-independent or whose digests are intentionally aggregated across seeds;
* If, in a more complex design, the hash is seed-dependent, this MUST be documented explicitly and encoded in the schema and combination law. By default, this spec assumes **seed-invariant** universe hash for a manifest.

7.6.3 Higher-level tooling may compare S3 outputs across manifests or seeds, e.g. for drift detection, but such comparisons:

* MUST NOT influence S3’s behaviour;
* are outside the normative scope of this state.

---

7.7 **Non-conformance and correction**

7.7.1 Any implementation that:

* deviates from the partition law in §7.2;
* uses alternative keys or unsorted writer order contrary to §7.3;
* mutates S3 outputs in place without idempotent comparison;
* publishes blob, index and universe hash in a non-atomic fashion;

is **non-conformant** with this specification.

7.7.2 Such behaviour MUST be treated as an engine/spec bug. Corrective action MUST:

* restore the partitioning, key and ordering discipline described here;
* re-establish immutability and idempotence guarantees;
* ensure that S3 outputs and their identity echoes are stable functions of sealed inputs and the identity triple.

7.7.3 If historic S3 outputs do not satisfy these constraints, migration tools MAY:

* read them under their existing schema;
* transform them into conformant artefacts under a new `manifest_fingerprint` and/or updated 3B contracts;

but the migrated artefacts MUST then obey the identity, partition, ordering and merge discipline specified in this section going forward.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

8.1 **S3 state-level PASS criteria**

8.1.1 A run of 3B.S3 for a given
`{seed, parameter_hash, manifest_fingerprint}`
SHALL be considered **PASS** if and only if **all** of the following conditions hold.

**Identity & S0 gate**

a. `s0_gate_receipt_3B` and `sealed_inputs_3B` exist for the target `manifest_fingerprint` and validate against their schemas.
b. `segment_id = "3B"` and `state_id = "S0"` in `s0_gate_receipt_3B`.
c. `seed`, `parameter_hash`, and `manifest_fingerprint` used by S3 match values embedded in `s0_gate_receipt_3B` (where present).
d. `upstream_gates.segment_1A/1B/2A/3A.status = "PASS"`.

**Contracts & sealed artefacts**

e. `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` form a compatible triplet for S3 (per 3B versioning rules).
f. Alias-layout policy artefact(s) and RNG/routing policy artefact(s) required by S3 are present in `sealed_inputs_3B`, readable and schema-valid.
g. Any policy digest artefacts that must be included in the edge-universe hash (e.g. CDN policy digests, spatial surface digests, alias-layout policy digest) are present and usable.

**S1 / S2 input contracts**

h. `virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`, and `edge_catalogue_index_3B` for the target `{seed, fingerprint}` exist and validate against their schemas.
i. S1/S2 invariants that S3 relies on hold, at minimum:

* All merchants appearing in `edge_catalogue_3B` are virtual according to `virtual_classification_3B` (or conform to any explicitly documented “no-edge-virtual” mode).
* For each virtual merchant that should have edges in S2, `edge_catalogue_index_3B.edge_count_total > 0` or the configuration explicitly allows zero-edge merchants and S2 has marked them accordingly.
* Per-merchant and global edge counts in `edge_catalogue_index_3B` match actual row counts in `edge_catalogue_3B`.

**Per-merchant weight preparation & quantisation**

j. For every merchant `m` where S2 has edges (`edge_count_total(m) > 0`):

* S3 successfully constructs a canonical ordered edge list `E_m` and corresponding weight vector `w_raw(m,i)` from `edge_catalogue_3B`.
* Normalised weights `w_norm(m,i)` are well-defined (non-negative, sum to 1 within tolerance) or follow an explicitly documented fallback (e.g. uniform weights) in the rare cases allowed by policy.

k. The integer mass vector `M(m,i)` resulting from quantisation to the alias grid (of size `G`):

* satisfies `M(m,i) ≥ 0` for all `i`;
* satisfies Σᵢ `M(m,i) = G` for each merchant;
* approximates `w_norm(m,i)` within alias-layout policy tolerance (e.g. max per-index absolute difference ≤ ε).

If this cannot be achieved for any merchant, S3 MUST fail.

**Alias table construction**

l. For every merchant with `edge_count_total(m) > 0`:

* S3 successfully builds an alias table over indices `{0,…, alias_table_length(m)−1}` using the deterministic algorithm defined in §6;
* any degenerate cases (e.g. single-edge merchants, zero-edge merchants in “no-edge” mode) are handled according to the alias-layout policy and 3B spec;
* the implied alias distribution over indices corresponds to `M(m,i)/G` (and thus `w_norm(m,i)`) within documented tolerance.

m. S3 does **not** drop any merchant that has edges in `edge_catalogue_3B`: for each such merchant, there is exactly one alias segment in `edge_alias_blob_3B` and one per-merchant row in `edge_alias_index_3B`.

**Blob & index structure**

n. `edge_alias_blob_3B@seed={seed}, fingerprint={manifest_fingerprint}` exists and:

* has a header conforming to `schemas.3B.yaml#/binary/edge_alias_blob_header_3B`;
* encodes `layout_version`, `endianness`, `alignment_bytes`, `blob_length_bytes`, `blob_sha256_hex`, and policy IDs/versions as specified;
* has `blob_sha256_hex` equal to the SHA-256 of the blob content as defined by the layout policy.

o. `edge_alias_index_3B@seed={seed}, fingerprint={manifest_fingerprint}` exists and:

* validates against `schemas.3B.yaml#/plan/edge_alias_index_3B`;
* has one per-merchant row for each merchant that appears in `edge_catalogue_3B` with `edge_count_total > 0`, and no extra per-merchant rows;
* has global summary row(s) with `edge_count_total_all_merchants` equal to:

  * sum of per-merchant `edge_count_total`, and
  * the total row count of `edge_catalogue_3B` for that partition;
* has, for each merchant row, `(blob_offset_bytes, blob_length_bytes)` pointing to a contiguous region of the alias blob within `blob_length_bytes` and a `merchant_alias_checksum` that matches a recomputation over that region.

**Edge universe hash descriptor**

p. `edge_universe_hash_3B@fingerprint={manifest_fingerprint}` exists and:

* validates against `schemas.3B.yaml#/validation/edge_universe_hash_3B`;
* contains `manifest_fingerprint` (and `parameter_hash` if present) matching S0 and S3’s run identity;
* contains `edge_universe_hash` computed exactly from the component digests according to the combination law defined in §6;
* lists component digests that match actual digests of the referenced artefacts (policies, S2 catalogue/index, alias blob, alias index, etc.).

**RNG-free guarantee**

q. S3 has emitted **no RNG events** and opened **no RNG streams**:

* there are no 3B.S3 entries in `rng_audit_log` / `rng_trace_log`;
* S3’s code path contains no calls to RNG APIs.

8.1.2 If **any** of the conditions above fail, S3 MUST be considered **FAIL** for that `{seed, parameter_hash, manifest_fingerprint}`. S3 MUST NOT publish `edge_alias_blob_3B`, `edge_alias_index_3B` or `edge_universe_hash_3B` as valid canonical outputs; any partially written artefacts MUST be treated as invalid and MUST NOT be used by downstream states.

---

8.2 **Alias-table correctness & coverage semantics**

8.2.1 In **default full-edge mode**, S3 operates under the assumption that:

* every merchant that has edges in `edge_catalogue_3B` MUST have a valid alias table in `edge_alias_blob_3B` and a corresponding index row in `edge_alias_index_3B`;
* the alias tables must cover all such edges as potential outcomes, with probability masses consistent with S2 `edge_weight`s (modulo quantisation).

8.2.2 If the 3B design supports a **no-edge-virtual or partial-edge** mode (e.g. some virtual merchants intentionally have zero edges):

* such modes MUST be explicitly documented and configured;
* S3 MUST:

  * either omit alias tables/index rows for those merchants and record them in a separate diagnostic surface, **or**
  * include index rows with `edge_count_total = 0` and no alias segment (or a special representation) as defined in schema and layout policy;
* 2B and validation MUST have clear semantics for such merchants (e.g. cannot be routed via CDN edges).

8.2.3 Any unintentional partial coverage (e.g. some S2 edges not represented in alias tables due to logic bugs) MUST cause S3 to fail rather than silently dropping edges.

* For each `(merchant, edge_id)` in `edge_catalogue_3B` for a PASS run:

  * there MUST exist at least one alias index position mapping to that edge (unless zero-mass alias entries are explicitly allowed and recorded).

8.2.4 The distribution implied by alias tables MUST be:

* a valid probability distribution over the merchant’s edge set;
* within the alias-layout policy’s tolerance of the S2 `edge_weight` distribution;
* consistent between S3 and any sampling logic in 2B that uses the alias tables (as per shared alias-layout policy).

---

8.3 **Gating obligations for downstream 2B & 3B validation**

8.3.1 For a given `{seed, manifest_fingerprint}`, any 2B logic that performs **virtual routing of edges** MUST:

* verify that S3 outputs exist and validate:

  * `edge_alias_blob_3B@seed={seed}, fingerprint={manifest_fingerprint}`;
  * `edge_alias_index_3B@seed={seed}, fingerprint={manifest_fingerprint}`;
  * `edge_universe_hash_3B@fingerprint={manifest_fingerprint}`;

* verify that the alias layout version(s) used by S3 are compatible with the decode logic built into 2B (as indicated by the RNG/routing policy).

8.3.2 2B MUST treat:

* `edge_alias_blob_3B` + `edge_alias_index_3B` as the **sole authoritative alias representation** of the virtual edge universe;
* `edge_universe_hash_3B` as the **binding hash** representing the combination of S2 catalogue, policies, and S3 alias representations.

2B MUST NOT:

* derive alternative alias tables directly from `edge_catalogue_3B` in production;
* route against alias tables that do not match the `edge_universe_hash_3B` descriptor.

8.3.3 Any 2B or validation component that detects:

* missing S3 outputs;
* schema violations in S3 outputs;
* mismatches between digests recorded in `edge_universe_hash_3B` and recomputed digests of underlying artefacts;
* alias-table inconsistencies with `edge_catalogue_3B` or layout policy (e.g. invalid offsets, bad checksums),

MUST treat this as a **3B.S3 failure** and:

* fail fast (no routing or segment-level PASS for that manifest);
* not attempt to “repair” or regenerate alias tables locally.

8.3.4 The 3B validation state (segment-level) MUST:

* treat S3 invariants (alias-table correctness, index/cat alignment, correct universe hash) as **hard PASS conditions** for 3B;
* include S3 outputs in the 3B validation bundle index, with their digests;
* refuse to emit `_passed.flag_3B` if any S3 invariants fail.

---

8.4 **Gating obligations with respect to S0/S1/S2**

8.4.1 S3 acceptance is strictly downstream of S0, S1 and S2:

* If S0 fails or is missing, S3 MUST fail as ungated.
* If S1 or S2 outputs are missing, schema-invalid, or inconsistent with their own specs, S3 MUST treat this as a contract violation and fail.

8.4.2 S3 MUST NOT:

* attempt to re-run or “fix” S0, S1 or S2;
* bypass sealed-input discipline by resolving new artefacts outside `sealed_inputs_3B`.

8.4.3 When S3 fails due to upstream issues (e.g. `E3B_S3_S1_CONTRACT_VIOLATION`, `E3B_S3_S2_CONTRACT_VIOLATION`, or equivalent), the run harness MUST:

* attribute the failure to 3B.S3 in logs and run-report;
* prevent 2B virtual routing or 3B validation from treating S3 as PASS for that manifest.

---

8.5 **Failure semantics & propagation**

8.5.1 Any violation of the binding requirements in §§8.1–8.4 MUST result in:

* S3 returning **FAIL** for that `{seed, parameter_hash, manifest_fingerprint}`;
* no S3 outputs being considered valid for that run (partial artefacts MUST be quarantined or ignored);
* a canonical `E3B_S3_*` error code being logged, with context (e.g. merchant, offsets, policy ID).

8.5.2 The run harness MUST:

* prevent 2B’s virtual routing and 3B’s validation state from executing under the assumption that S3 has succeeded;
* ensure S3 failures are surfaced in global run reports (e.g. 4A/4B) as **“3B.S3 alias/universe-hash failure”** for the manifest.

8.5.3 Downstream components that detect latent S3 issues **after** S3 reported PASS (e.g. due to a bug in S3) MUST:

* treat S3 outputs as invalid;
* surface the failure as a S3-contract problem;
* not attempt to salvage or mutate alias tables;
* require a corrected S3 implementation and re-run for that manifest (or a new manifest).

In all cases, **alias-table correctness, blob/index integrity, consistent universe hash and RNG-free determinism** as specified above are the binding conditions under which S3 can be said to have “passed” for a given run.

---

## 9. Failure modes & canonical error codes *(Binding)*

9.1 **Error model & severity**

9.1.1 3B.S3 SHALL use a **state-local error namespace** of the form:

> `E3B_S3_<CATEGORY>_<DETAIL>`

All codes in this section are reserved for 3B.S3 and MUST NOT be reused by other states.

9.1.2 Every surfaced S3 failure MUST carry, at minimum:

* `segment_id = "3B"`
* `state_id = "S3"`
* `error_code`
* `severity ∈ {"FATAL","WARN"}`
* `manifest_fingerprint`
* optional `{seed, parameter_hash}`
* a human-readable `message` (non-normative, for operators)

9.1.3 Unless explicitly marked as `WARN`, all codes defined below are **FATAL** for S3:

* **FATAL** ⇒ S3 MUST NOT publish `edge_alias_blob_3B`, `edge_alias_index_3B` or `edge_universe_hash_3B` as valid canonical outputs for that `{seed,fingerprint}`. The virtual edge alias universe MUST be considered **not constructed** for that manifest.
* **WARN** ⇒ S3 MAY complete and publish outputs, but the condition MUST be observable via logs/run-report and SHOULD be visible in metrics; WARNs MUST NOT be used to hide conditions that this spec treats as FATAL.

---

### 9.2 Identity & gating failures

9.2.1 **E3B_S3_IDENTITY_MISMATCH** *(FATAL)*
Raised when S3’s view of identity is inconsistent with S0:

* `seed`, `parameter_hash` or `manifest_fingerprint` passed to S3 differ from those embedded in `s0_gate_receipt_3B`; or
* `s0_gate_receipt_3B` itself contains conflicting identity fields.

Typical triggers:

* S0 and S3 invoked with different identity triples.
* Manual editing of S0 artefacts.

Remediation:

* Fix run harness so S0 and S3 share the same `{seed, parameter_hash, manifest_fingerprint}`.
* Regenerate S0 artefacts if they were tampered with.

---

9.2.2 **E3B_S3_GATE_MISSING_OR_INVALID** *(FATAL)*
Raised when S3 cannot use S0 outputs as a valid gate:

* `s0_gate_receipt_3B` or `sealed_inputs_3B` is missing for the fingerprint; or
* either artefact fails schema validation.

Typical triggers:

* S3 invoked before S0 ran or succeeded.
* Schema drift or corruption of S0 artefacts.

Remediation:

* Run/fix 3B.S0 for the manifest.
* Restore or regenerate missing/invalid artefacts.

---

9.2.3 **E3B_S3_UPSTREAM_GATE_BLOCKED** *(FATAL)*
Raised when `s0_gate_receipt_3B.upstream_gates` indicates that any of segments 1A, 1B, 2A or 3A does **not** have `status = "PASS"`.

Typical triggers:

* Upstream segment failed validation or was never run for this manifest.

Remediation:

* Diagnose and fix the failing upstream segment.
* Rerun its validation, then rerun S0, S1, S2 and finally S3.

---

9.2.4 **E3B_S3_S1S2_CONTRACT_VIOLATION** *(FATAL)*
Raised when S1/S2 outputs do not satisfy their contracts, from S3’s perspective, e.g.:

* `virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B` or `edge_catalogue_index_3B` is missing or schema-invalid.
* A merchant has edges in `edge_catalogue_3B` but is not marked virtual in `virtual_classification_3B`, in a mode where that is not explicitly allowed.
* `edge_catalogue_index_3B` counts do not match actual row counts in `edge_catalogue_3B`.

Typical triggers:

* Incomplete or inconsistent S1/S2 runs.
* Manual modification of S1/S2 outputs.

Remediation:

* Fix/rerun S1 and/or S2 until their invariants hold;
* then rerun S3.

---

### 9.3 Contract & sealed-input failures

9.3.1 **E3B_S3_SCHEMA_PACK_MISMATCH** *(FATAL)*
Raised when the loaded combination of:

* `schemas.3B.yaml`
* `dataset_dictionary.layer1.3B.yaml`
* `artefact_registry_3B.yaml`

is incompatible for S3, e.g.:

* MAJOR version mismatch;
* S3 outputs missing from dictionary/registry;
* schema refs referenced by dictionary entries do not exist.

Typical triggers:

* Partial deployment of 3B contracts.
* Changing dictionary/registry without updating schemas.

Remediation:

* Align schema, dictionary and registry versions.
* Deploy a coherent set; rerun S0/S1/S2 and then S3.

---

9.3.2 **E3B_S3_REQUIRED_INPUT_NOT_SEALED** *(FATAL)*
Raised when a **mandatory** S3 input artefact is missing from `sealed_inputs_3B`, including:

* alias-layout policy artefact(s);
* RNG/routing policy artefact(s) needed for layout compatibility;
* CDN/spatial/RNG-policy digests required for universe hash assembly.

Typical triggers:

* New S3 dependency added but S0 not updated to seal it.
* Registry entries exist but S0 does not include them in `sealed_inputs_3B`.

Remediation:

* Register artefacts correctly in dictionary/registry.
* Update S0 sealing logic.
* Rerun S0–S3.

---

9.3.3 **E3B_S3_INPUT_OPEN_FAILED** *(FATAL)*
Raised when S3 resolves a required artefact from `sealed_inputs_3B` but cannot open it for read.

Typical triggers:

* `path` in `sealed_inputs_3B` is stale or incorrect.
* Permissions or storage endpoint misconfigured.
* Transient IO failures not handled at the storage layer.

Remediation:

* Fix storage/permissions/network;
* ensure sealed paths match real storage;
* rerun S0 (if paths changed) and S3.

---

9.3.4 **E3B_S3_INPUT_SCHEMA_MISMATCH** *(FATAL)*
Raised when a sealed artefact used by S3 does not conform to its declared `schema_ref`, e.g.:

* alias-layout policy missing required fields (layout version, alignment, grid size, checksum spec);
* RNG/routing policy lacking required alias-compatibility information;
* policy digest artefact missing or malformed.

Typical triggers:

* Schema updated without updating policy file content.
* Incorrect schema_ref in the dictionary/registry.

Remediation:

* Fix the underlying artefact OR its schema_ref.
* Redeploy consistent schema + content.
* Reseal via S0; rerun S3.

---

9.3.5 **E3B_S3_ALIAS_LAYOUT_POLICY_INVALID** *(FATAL)*
Raised when the alias-layout policy artefact:

* fails validation against `schemas.3B.yaml#/policy/edge_alias_layout_policy` (or equivalent);
* specifies inconsistent or unsupported layout parameters (e.g. negative grid size, unknown endianness, missing checksum configuration).

Typical triggers:

* Misconfigured alias-layout file.
* Out-of-date layout policy vs schema.

Remediation:

* Correct the alias-layout policy to conform to schema and 2B’s decode expectations;
* reseal via S0; rerun S3.

---

9.3.6 **E3B_S3_ROUTING_POLICY_INCOMPATIBLE** *(FATAL)*
Raised when the RNG/routing policy artefact indicates that:

* 2B does not support the alias layout version S3 is about to build; or
* there is no overlap between S3’s configured layout version and 2B’s supported versions.

Typical triggers:

* Upgrading alias layout or 2B’s decoder without updating the other.
* Misconfigured layout version selection in 3B parameters.

Remediation:

* Align alias-layout policy and 2B’s decode configuration;
* ensure a supported layout version is selected;
* rerun S3.

---

### 9.4 Weight & quantisation failures

9.4.1 **E3B_S3_WEIGHT_VECTOR_INVALID** *(FATAL)*
Raised when, for at least one merchant `m` with edges:

* all `edge_weight` values are non-finite (NaN, Inf);
* all `edge_weight` values are ≤ 0 and no documented fallback (e.g. uniform) is allowed;
* required normalisation to form `w_norm(m,i)` is impossible (e.g. sum of positive weights is zero).

Typical triggers:

* Upstream bug in S2 weight computation.
* Corrupted `edge_weight` values.

Remediation:

* Fix S2’s weight computation or input policies;
* ensure valid non-negative weights;
* rerun S2 then S3.

---

9.4.2 **E3B_S3_QUANTISATION_FAILED** *(FATAL)*
Raised when S3 cannot quantise a merchant’s normalised weights `w_norm(m,i)` onto the alias grid (size `G`) while:

* ensuring integer masses `M(m,i) ≥ 0`;
* ensuring Σᵢ `M(m,i) = G`;
* respecting alias-layout tolerance bounds.

Typical triggers:

* Overly tight quantisation tolerances vs floating-point rounding;
* Implementation bug in quantisation logic.

Remediation:

* Adjust alias-layout tolerances or grid size in policy;
* fix quantisation logic to use stable rounding and deterministic largest-remainder;
* rerun S3.

---

### 9.5 Alias construction failures

9.5.1 **E3B_S3_ALIAS_CONSTRUCTION_FAILED** *(FATAL)*
Raised when, for at least one merchant, S3’s alias algorithm cannot produce a valid alias table from `M(m,i)`:

* due to unexpected numeric artefacts (e.g. threshold `G/n` not handled correctly);
* or due to an internal bug in the alias algorithm.

Typical triggers:

* Incorrect implementation of the Walker/Vose algorithm;
* Failing to handle boundary cases (e.g. all masses equal, extreme skew).

Remediation:

* Correct alias algorithm implementation and test with representative weight distributions.
* Ensure all boundary cases (1-edge, 2-edge, highly skewed distributions) are handled.

---

9.5.2 **E3B_S3_ALIAS_DISTRIBUTION_INCONSISTENT** *(FATAL)*
Raised when the distribution implied by a merchant’s alias table, when decoded, does not match `M(m,i)/G` within tolerated error bounds:

* per-index probabilities differ beyond allowed tolerance;
* or sum-of-probabilities per merchant deviates from 1 beyond allowed tolerance.

Typical triggers:

* Misinterpretation of integer masses in alias representation;
* Overflow or rounding errors in alias probabilities.

Remediation:

* Fix the mapping from integer masses to alias-table probabilities;
* ensure alias layout and decode logic are consistent.

---

9.5.3 **E3B_S3_ALIAS_COVERAGE_INCOMPLETE** *(FATAL)*
Raised when, for at least one merchant `m`:

* an edge present in `edge_catalogue_3B` for `m` has **no representation** in the alias mapping (i.e. no alias-table index ever yields that edge, even with zero mass not allowed by layout), and this is not a documented special-case mode.

Typical triggers:

* Dropping edges when building the canonical `E_m` list;
* Alias index → edge index mapping not covering all edges.

Remediation:

* Correct mapping between alias indices and edges;
* ensure each edge in `E_m` can be mapped from the alias table or explicitly treated as zero-mass in the documented way.

---

### 9.6 Blob/index structure & digest failures

9.6.1 **E3B_S3_ALIAS_BLOB_SCHEMA_VIOLATION** *(FATAL)*
Raised when `edge_alias_blob_3B` fails validation against `schemas.3B.yaml#/binary/edge_alias_blob_header_3B`, e.g.:

* missing or malformed header fields;
* `layout_version` or `endianness` not in declared enums;
* `blob_length_bytes` inconsistent with actual blob length;
* `blob_sha256_hex` mismatch against recomputed digest.

Typical triggers:

* Incorrect header construction;
* Partial write or corruption of blob.

Remediation:

* Fix header serialisation and digest computation;
* ensure atomic writes;
* rerun S3.

---

9.6.2 **E3B_S3_ALIAS_INDEX_SCHEMA_VIOLATION** *(FATAL)*
Raised when `edge_alias_index_3B` fails validation against `schemas.3B.yaml#/plan/edge_alias_index_3B`, e.g.:

* missing required columns (`merchant_id`, `edge_count_total`, `blob_offset_bytes`, etc.);
* incorrect partitioning or unsorted rows relative to `ordering`.

Typical triggers:

* Incorrect index write logic;
* schema/dictionary drift.

Remediation:

* Fix index construction;
* align schema/dictionary with intended shape;
* rerun S3.

---

9.6.3 **E3B_S3_ALIAS_INDEX_INCONSISTENT_WITH_BLOB** *(FATAL)*
Raised when `edge_alias_index_3B` does not correctly describe `edge_alias_blob_3B`:

* `(blob_offset_bytes, blob_length_bytes)` for some merchant row point outside the blob or overlap in unexpected ways;
* `merchant_alias_checksum` does not match the recomputed checksum of the corresponding alias segment;
* `blob_sha256_hex` in global index row does not match blob header.

Typical triggers:

* Non-atomic write of blob and index;
* Incorrect offset calculations;
* Failure to recompute checksums after changes.

Remediation:

* Fix blob layout and index construction;
* enforce atomic publish;
* rerun S3.

---

9.6.4 **E3B_S3_ALIAS_INDEX_INCONSISTENT_WITH_CATALOGUE** *(FATAL)*
Raised when `edge_alias_index_3B` is inconsistent with `edge_catalogue_3B` / `edge_catalogue_index_3B`:

* `edge_count_total` per merchant differs from S2 index or from actual edge row count;
* `edge_count_total_all_merchants` differs from S2’s global edge count.

Typical triggers:

* Using a stale view of the catalogue;
* Merchant filtering bug;
* Incomplete per-merchant summarisation.

Remediation:

* Ensure S3 reads the correct S2 artefacts;
* correct summarisation logic;
* rerun S3.

---

9.6.5 **E3B_S3_OUTPUT_WRITE_FAILED** *(FATAL)*
Raised when S3 cannot complete atomic writes of any of:

* `edge_alias_blob_3B`;
* `edge_alias_index_3B`;
* `edge_universe_hash_3B`.

Typical triggers:

* IO failure, permission error or disk-space exhaustion.

Remediation:

* Correct storage/permission issues;
* rerun S3;
* ensure temporary and final write procedures are robust.

---

9.6.6 **E3B_S3_OUTPUT_INCONSISTENT_REWRITE** *(FATAL)*
Raised when existing S3 outputs for a given `{seed, manifest_fingerprint}` differ from recomputed outputs under the same inputs:

* blob or index digests differ;
* universe hash differs.

Typical triggers:

* Environment drift (policies or S2 outputs changed) without recomputing `manifest_fingerprint`;
* manual modification of S3 artefacts.

Remediation:

* Treat this as environment/manifest inconsistency;
* either restore original environment or recompute a new manifest and rerun S0–S3.

---

### 9.7 Universe-hash & determinism failures

9.7.1 **E3B_S3_UNIVERSE_COMPONENT_DIGEST_MISMATCH** *(FATAL)*
Raised when a component digest recorded in `edge_universe_hash_3B.components` does not match the recomputed digest of the referenced artefact:

* `cdn_policy_digest`, `alias_layout_policy_digest`, `edge_catalogue_digest_global`, `edge_alias_blob_sha256_hex`, `edge_alias_index_sha256_hex`, etc.

Typical triggers:

* Reading or hashing a different artefact than the one S3 recorded;
* Artefacts modified after S3 ran;
* Incorrect digest computation algorithm.

Remediation:

* Fix digest computation;
* ensure artefacts are immutable once sealed;
* rerun S3 if artefacts have legitimately changed under a new manifest.

---

9.7.2 **E3B_S3_UNIVERSE_HASH_MISMATCH** *(FATAL)*
Raised when the `edge_universe_hash` value in `edge_universe_hash_3B` does not match the value recomputed from the `components` digests using the documented combination law.

Typical triggers:

* Bug in universe-hash assembly;
* Manual tampering with universe-hash descriptor.

Remediation:

* Correct combination law implementation;
* treat tampering as environment corruption and regenerate S3 outputs under a clean environment.

---

9.7.3 **E3B_S3_RNG_USED** *(FATAL)*
Raised when S3 is observed to have used RNG despite being specified as RNG-free, e.g.:

* RNG events attributed to 3B.S3 in `rng_audit_log` / `rng_trace_log`;
* internal instrumentation shows calls to RNG APIs.

Typical triggers:

* Accidental reuse of RNG-based helper code;
* Copy-paste of RNG logic from S2 into S3.

Remediation:

* Remove all RNG usage from S3;
* add tests to ensure S3 remains RNG-free.

---

9.7.4 **E3B_S3_NONDETERMINISTIC_OUTPUT** *(FATAL)*
Raised when S3’s outputs differ across re-runs with identical inputs:

* alias blob bytes differ;
* alias index rows/digests differ;
* `edge_universe_hash` differs;
* merchant or edge ordering changes.

Typical triggers:

* dependence on unordered iteration (dict/hash-map order, unsorted file listings);
* hidden state in alias construction;
* environment-dependent behaviour (e.g. using wall-clock time or process ID in hashing).

Remediation:

* enforce explicit ordering and canonical iteration;
* remove environment-dependent logic;
* verify determinism via regression tests.

---

9.8 **Error propagation & downstream behaviour**

9.8.1 On any FATAL S3 error, S3 MUST:

* log a structured error event including the fields in §9.1.2;
* ensure that no partially written S3 outputs are treated as canonical (using atomic publish or explicit clean-up);
* report FAIL to the run harness.

9.8.2 The run harness MUST:

* prevent 2B virtual routing and 3B segment-level validation from running under the assumption that S3 has succeeded for that manifest;
* surface S3 failures as **3B.S3 alias/universe-hash failures** in any global run-report.

9.8.3 Downstream components (2B, 3B validation) that detect S3-related inconsistencies at consumption time SHOULD:

* re-use the most appropriate `E3B_S3_*` code where possible;
* set their own `state_id` (e.g. `"2B"` or `"3B_validation"`) to indicate detection point.

9.8.4 Any new S3 failure condition introduced in future versions MUST:

* be given a unique `E3B_S3_...` error code;
* be documented here with severity, typical triggers and remediation;
* NOT overload an existing code with incompatible semantics.

---

## 10. Observability & run-report integration *(Binding)*

10.1 **Structured logging requirements**

10.1.1 S3 MUST emit, at minimum, the following **lifecycle log events** for each attempted run:

* a **`start`** event when S3 begins work for a given `{seed, parameter_hash, manifest_fingerprint}`, and
* a **`finish`** event when S3 either completes successfully or fails.

10.1.2 Both `start` and `finish` events MUST be structured and include at least:

* `segment_id = "3B"`
* `state_id = "S3"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `event_type ∈ {"start","finish"}`
* `ts_utc` — UTC timestamp at which the event was logged

10.1.3 The `finish` event MUST additionally include:

* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL; `null` or omitted for PASS)
* `virtual_merchant_count` — number of merchants with edges in `edge_catalogue_3B` (derived from S2 index)
* `alias_merchant_count` — number of merchants for which S3 successfully built alias tables (should equal `virtual_merchant_count` in full-edge mode)
* `edge_count_total_all_merchants` — total number of edges (echo from S2 index)
* `alias_blob_length_bytes` — total bytes in `edge_alias_blob_3B`
* `outputs_written` — boolean flag indicating whether all S3 outputs (`edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`) were successfully written to canonical locations and validated

10.1.4 For every FATAL error, S3 MUST emit at least one **error log event** that includes:

* the fields in 10.1.2,
* `error_code` in the `E3B_S3_*` namespace,
* `severity = "FATAL"`,
* and enough diagnostic context to support triage, e.g.:

  * for alias failures: `merchant_id`, `layout_version`, `edge_count_total`
  * for index/blob mismatches: `merchant_id`, `blob_offset_bytes`, `blob_length_bytes`, expected vs actual checksum
  * for universe-hash mismatches: component name (`cdn_policy`, `edge_catalogue`, `alias_blob`, etc.) and expected vs recomputed digest

10.1.5 If S3 uses WARN-level conditions (e.g. non-fatal anomalies permitted by configuration), WARN logs MUST:

* set `severity = "WARN"` and include an appropriate `E3B_S3_*` code;
* never be used for conditions that this specification classifies as FATAL.

---

10.2 **Run-report record for 3B.S3**

10.2.1 S3 MUST produce a **run-report record** for each `{seed, manifest_fingerprint}` that can be consumed by the Layer-1 run-report / 4A–4B harness. This record MAY be a dedicated dataset or an in-memory structure, but it MUST include at least:

* `segment_id = "3B"`
* `state_id = "S3"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL; `null` or omitted for PASS)
* `virtual_merchant_count`
* `alias_merchant_count`
* `edge_count_total_all_merchants`
* `alias_blob_length_bytes`
* `gate_receipt_path` — canonical path to `s0_gate_receipt_3B`
* `sealed_inputs_path` — canonical path to `sealed_inputs_3B`
* `edge_catalogue_path` — canonical root for `edge_catalogue_3B`
* `edge_catalogue_index_path` — canonical root for `edge_catalogue_index_3B`
* `edge_alias_blob_path` — canonical root/path for `edge_alias_blob_3B`
* `edge_alias_index_path` — canonical root/path for `edge_alias_index_3B`
* `edge_universe_hash_path` — canonical path for `edge_universe_hash_3B`

10.2.2 Where available, the run-report record SHOULD also include:

* `alias_layout_policy_id` / `alias_layout_policy_version`
* `cdn_policy_id` / `cdn_policy_version` (echo from S0/S2)
* `rng_policy_id` / `rng_policy_version` (for decode compatibility)
* `edge_catalogue_digest_global` (from S2 index or recomputed)
* `edge_alias_blob_sha256_hex`
* `edge_alias_index_sha256_hex`
* `edge_universe_hash` (from `edge_universe_hash_3B`)

10.2.3 The run-report harness MUST be able to determine from S3’s record alone:

* whether S3 has **successfully** constructed alias tables and the edge universe hash for `{seed, manifest_fingerprint}`;
* where S3’s outputs live;
* whether there are structural anomalies (e.g. `alias_merchant_count` ≠ `virtual_merchant_count`) that require operator attention.

---

10.3 **Metrics & counters**

10.3.1 S3 MUST emit the following **metrics** (names illustrative; concrete metric names may vary as long as semantics are preserved):

* `3b_s3_runs_total{status="PASS|FAIL"}` — counter, incremented once per S3 run.
* `3b_s3_virtual_merchants` — gauge/histogram; number of merchants with edges (from S2).
* `3b_s3_alias_merchants` — gauge/histogram; number of merchants for which alias tables were built.
* `3b_s3_edge_count_total` — gauge/histogram; total edges from S2 (`edge_count_total_all_merchants`).
* `3b_s3_alias_blob_size_bytes` — gauge/histogram; size of `edge_alias_blob_3B` in bytes.
* `3b_s3_alias_table_length` — histogram of alias table lengths per merchant.
* `3b_s3_errors_total{error_code=...}` — counter; counts of S3 errors per `E3B_S3_*` code.
* `3b_s3_duration_seconds` — latency of S3 run from `start` to `finish`.

10.3.2 Metrics SHOULD be tagged with:

* `segment_id = "3B"`
* `state_id = "S3"`
* a reduced identifier for `manifest_fingerprint` (e.g. a hash prefix or manifest label, to avoid unbounded cardinality)
* where appropriate, `error_code`, `layout_version`, or `merchant_class` (if merchant class information is available from S2/S1 and useful for aggregation).

10.3.3 Operators MUST be able to use these metrics to answer questions such as:

* “Is S3 running and passing for all manifests?”
* “How many merchants have alias tables, and how large are those tables on average?”
* “Is the alias blob size consistent with the expected edge counts?”
* “What are the most common S3 failure codes?”
* “Is S3 latency within expected SLOs?”

---

10.4 **Traceability & correlation**

10.4.1 S3 MUST ensure that its outputs, logs and run-report entries are **correlatable** by identity. Concretely:

* all S3 logs MUST include `{segment_id="3B", state_id="S3", manifest_fingerprint, seed, parameter_hash}` and optionally `run_id`;
* S3 outputs MUST adhere to the partition laws in §7 (blob/index keyed by `{seed,fingerprint}`, universe hash keyed by `fingerprint`);
* any identity echo fields in schemas (e.g. `manifest_fingerprint` in `edge_universe_hash_3B`) MUST match partition identity and S0.

10.4.2 Given a particular merchant (`merchant_id`) and manifest, an operator MUST be able to:

1. Look up the merchant’s edges in `edge_catalogue_3B` (S2).
2. Find the corresponding per-merchant row in `edge_alias_index_3B` (offset, length, checksums).
3. Use the offset/length to locate the merchant’s alias segment inside `edge_alias_blob_3B`.
4. Confirm (with debug tooling) that the decoded alias table probabilities correspond to the S2 `edge_weight` profile.

10.4.3 If the platform uses global **correlation IDs** (e.g. trace IDs), S3 MAY:

* include such IDs in its lifecycle and error logs;
* record them in `s3_run_summary_3B` (if present).

These IDs are informational and MUST NOT influence any deterministic choices or digest computations.

---

10.5 **Integration with Layer-1 / 4A–4B validation harness**

10.5.1 S3 MUST expose enough information for the Layer-1 validation / observability harness (e.g. 4A/4B) to:

* determine S3’s **status** per `{seed, manifest_fingerprint}`;
* attribute failures to specific S3 error codes and categories (identity/gate, contract, alias construction, blob/index consistency, universe hash, determinism).

10.5.2 At minimum, for each `{seed, manifest_fingerprint}`, the harness MUST be able to derive:

* `3B.S3.status ∈ {"PASS","FAIL"}`
* `3B.S3.error_code` (if any)
* `3B.S3.virtual_merchant_count`
* `3B.S3.alias_merchant_count`
* `3B.S3.edge_count_total_all_merchants`
* `3B.S3.alias_blob_length_bytes`
* canonical paths to:

  * `edge_catalogue_3B` / `edge_catalogue_index_3B` (S2)
  * `edge_alias_blob_3B` / `edge_alias_index_3B`
  * `edge_universe_hash_3B`

10.5.3 In a **global manifest summary**, S3 SHOULD contribute:

* a compact description of the virtual edge alias universe, including:

  * number of merchants with edges & alias tables;
  * total edges;
  * alias blob size;
  * the `edge_universe_hash` value;
* any critical WARN-level conditions that may not block S3 but should be visible (e.g. highly skewed alias table sizes, if such skew is allowed but notable).

10.5.4 The 3B segment-level validation state MUST be able to use S3 run-report + metrics to:

* cross-check that S3’s per-merchant aliases cover all S2 edges;
* verify that the universe hash is consistent across runs and with the bundled artefacts;
* decide whether to emit `_passed.flag_3B`.

---

10.6 **Operational diagnostics & debugability**

10.6.1 On any FATAL S3 failure, S3 SHOULD log **diagnostic details** sufficient for root-cause analysis without requiring immediate debugging, such as:

* For identity/gate failures:

  * the conflicting identity values (from S0 vs runtime);
  * missing or invalid artefact IDs (dataset or policy logical IDs).

* For contract / schema mismatches:

  * offending `logical_id`, `path`, `schema_ref`;
  * a concise description of what is wrong (missing field, wrong type, unknown enum value).

* For weight/quantisation issues:

  * `merchant_id`;
  * `edge_count_total` and sample of `edge_weight` values;
  * computed `Z_m` and extremes of `w_norm` / `M(m,i)` vs allowed tolerances.

* For alias construction failures:

  * `merchant_id`;
  * distribution characteristics (e.g. number of edges, min/max `M(m,i)`);
  * a summary of where the algorithm failed (e.g. partitioning into L/H/E sets).

* For blob/index inconsistencies:

  * `merchant_id` (if per-merchant);
  * `blob_offset_bytes`, `blob_length_bytes`;
  * expected vs recomputed checksum;
  * `blob_length_bytes` vs file length.

* For universe-hash mismatches:

  * which component name had mismatched digest;
  * recorded digest vs recomputed digest.

10.6.2 If the engine supports a **debug / dry-run mode** for S3, then:

* S3 MUST run all phases A–E (up to constructing alias tables and universe hash in memory);
* S3 MUST validate internal invariants as in Phase F;
* S3 MUST **not** publish `edge_alias_blob_3B`, `edge_alias_index_3B` or `edge_universe_hash_3B` to canonical locations in dry-run mode.

In this mode, S3 MUST clearly indicate `mode = "dry_run"` vs `mode = "normal"` in logs and run-report, so operators do not confuse a dry-run with a completed alias/ universe-hash publish.

10.6.3 Any additional observability features (e.g. a small “alias debug decode” tooling, or per-merchant sample dumps) MAY be implemented provided they:

* use separate diagnostic datasets or logs;
* do not change the binding shape or semantics of S3 outputs;
* do not introduce non-determinism into core alias construction or universe hashing.

10.6.4 Where this section appears to conflict with schemas or dataset dictionary/registry entries, **schemas and catalogues are authoritative**. This section MUST be updated in the next non-editorial revision to reflect the actual S3 contracts, while preserving the core observability guarantees above.

---

## 11. Performance & scalability *(Informative)*

11.1 **Workload character**

11.1.1 3B.S3 is a **pure packaging and hashing** state:

* It **does not** place edges or route events.
* It **does**:

  * scan the **edge catalogue** from S2 (`edge_catalogue_3B`, `edge_catalogue_index_3B`),
  * build per-merchant alias tables in memory (or in streaming batches),
  * pack those tables into a contiguous blob,
  * build an index and compute digests/universe hash.

11.1.2 Dominant cost drivers:

* Number of virtual merchants with edges (`|V_edge|` ≈ number of merchants in `edge_catalogue_3B`).
* Total number of edges `E_total` (sum over merchants).
* Alias layout parameters (grid size, header size, per-entry size) which drive blob size.

There is **no RNG cost**: all work is CPU + memory + I/O.

---

11.2 **Complexity & expected scale**

11.2.1 Let:

* `|V_edge|` = number of merchants with at least one edge in `edge_catalogue_3B`;
* `E_total` = Σ₍m∈V_edge₎ `edge_count_total(m)`;
* `G` = alias grid size per merchant (e.g. integer probability denominator);
* `n_m` = `edge_count_total(m)`.

Then, asymptotically:

* **Per-merchant edge prep & quantisation**

  * `O(n_m)` per merchant → `O(E_total)` overall.

* **Alias construction**

  * Walker/Vose algorithm is `O(n_m)` per merchant, so `O(E_total)` overall.

* **Blob packing & index building**

  * `O(E_total)` to write alias tables + `O(|V_edge|)` to build index rows.

* **Digest & universe-hash computation**

  * `O(size(edge_catalogue_3B))` (if recomputed),
  * `O(size(alias_blob) + size(alias_index))`,
  * plus negligible cost for policy digests.

11.2.2 In practice:

* `|V_edge|` is typically at most the number of virtual merchants (S1),
* `E_total` is set by S2’s budgets (tunable),
* S3 runtime is roughly **linear in `E_total`**, with small extra overhead.

---

11.3 **Latency considerations**

11.3.1 Latency contributors (roughly in order):

* Read S2 catalogue & index (columnar scan).
* Build per-merchant alias tables (CPU + memory).
* Serialize alias blob and index (sequential writes).
* Compute digests/universe hash (sequential over blob/index).

11.3.2 For reasonable scales (e.g. `E_total` up to 10⁶–10⁷ edges with modest alias grid size), S3 is usually:

* **faster** than S2 (no RNG or spatial work),
* dominated by memory and cache behaviour rather than I/O.

11.3.3 Latency tends to grow with:

* increasing `E_total`,
* more complex alias layouts (e.g. big grids or rich per-merchant headers),
* slower backing storage (especially if S3 must re-read large S2 catalogues to recompute digests instead of using S2 index digests).

---

11.4 **Memory model & parallelism**

11.4.1 A simple single-process implementation can:

* read `edge_catalogue_3B` in merchant-sorted order,
* for each merchant:

  * accumulate edges + weights,
  * quantise and build alias table,
  * append binary alias data to an in-memory buffer (or directly stream to a temp file),
  * collect index row (offset, length, checksum).

Memory usage is roughly:

* O(max alias table size seen at one time) +
* overhead for buffers and index rows.

11.4.2 To handle large `E_total` without excessive memory:

* **Streaming approach**:

  * iterate merchants one at a time or in small batches,
  * write alias segments to the blob file as you go (maintaining `off`/alignment),
  * store only per-merchant index rows in memory (or stream them into the index dataset).

* **In-memory approach** (only if `E_total` is modest):

  * build full blob in memory, then write once;
  * useful for very small/medium runs or tests.

11.4.3 Parallelism:

* S3 is parallelisable over merchants:

  * each worker can build alias tables for a subset of merchants,
  * a coordinator can merge per-merchant binary segments into the final blob in deterministic order.

* To keep determinism:

  * assign merchants to workers based on a deterministic partition (e.g. shard by sorted `merchant_id` ranges),
  * ensure final ordering of segments and index rows follows the canonical sort (e.g. merge outputs by `merchant_id`),
  * avoid any worker-local ordering that leaks into the final output.

---

11.5 **I/O patterns**

11.5.1 Reads:

* `edge_catalogue_3B` and `edge_catalogue_index_3B` (S2 outputs):

  * typically columnar Parquet;
  * throughput scales with `E_total`.
* Alias-layout and policy artefacts:

  * small config files, negligible I/O.

11.5.2 Writes:

* `edge_alias_blob_3B`:

  * one binary file per `{seed, fingerprint}`;
  * size roughly:

    ```text
    blob_size ≈ header_size
              + Σ_m (alias_table_length(m) * bytes_per_slot + per-merchant header)
              + alignment padding
    ```

* `edge_alias_index_3B`:

  * small table, O(|V_edge|) rows.

* `edge_universe_hash_3B`:

  * tiny JSON, few kB at most.

11.5.3 Because the blob and index writes are **sequential** and low-fanout, S3 is generally not heavy on IOPS. Blob size is the main factor for write time.

---

11.6 **SLOs & tuning knobs**

11.6.1 Operators may define SLOs, for example:

* `P95(3b_s3_duration_seconds) < T` for an environment-specific `T` (e.g. 10–60 seconds), given a baseline `E_total` and layout.
* Constraints on blob size, e.g. `max(edge_alias_blob_size_bytes)` under a given config.

11.6.2 Tuning levers include:

* Controlling **edge budgets** in S2 (lower `E_clipped(m)` reduces `E_total` and alias size).
* Reducing **alias grid size** `G` where policy permits (smaller tables, less quantisation precision but faster).
* Simplifying alias layouts (e.g. avoiding very verbose per-merchant headers).
* Using **streaming** construction instead of all-in-memory for large runs.

11.6.3 Any tuning must still respect:

* policy semantics and tolerances,
* determinism guarantees,
* S2’s edge semantics,
* and 2B’s alias decode expectations.

---

11.7 **Testing & performance regression checks**

11.7.1 Performance tests for S3 SHOULD include:

* “Large” runs near expected production maxima:

  * high `|V_edge|` (many virtual merchants with edges);
  * high `E_total` (many edges per merchant).
* Skewed workloads:

  * a few merchants with very large edge sets;
  * many merchants with tiny edge sets, testing alias-table boundary cases.

11.7.2 Tests SHOULD verify that:

* S3 runtime and memory scale approximately linearly with `E_total` (for fixed alias grid and layout);
* alias-blob size matches expectations from `E_total` and layout parameters;
* idempotence holds: re-running S3 with the same inputs yields byte-identical blob, index and universe hash;
* S3 remains RNG-free (no RNG events, no S3 entries in RNG logs).

11.7.3 The exact numeric thresholds (latencies, blob sizes, edge counts) are deployment-specific. What is binding is that S3:

* remains fully deterministic and RNG-free;
* uses only bounded, predictable resources for a given `E_total` and layout;
* scales in an understandable way as `E_total`, `|V_edge|` and layout complexity increase.

---

## 12. Change control & compatibility *(Binding)*

12.1 **Scope of change control**

12.1.1 This section governs all changes that affect **3B.S3 — Edge alias tables & virtual edge universe hash** and its artefacts, specifically:

* The **behaviour** of S3, including:

  * per-merchant weight preparation and quantisation,
  * alias-table construction algorithm,
  * blob layout (header + per-merchant segments, alignment, endianness),
  * index construction,
  * component digest computation and the **edge universe hash** combination law.

* The **schemas and catalogue entries** for S3-owned artefacts:

  * `edge_alias_blob_3B`
  * `edge_alias_index_3B`
  * `edge_universe_hash_3B`
  * any S3 run-summary artefacts that are made persistent (e.g. `s3_run_summary_3B`), if defined.

* Any S3-specific use of:

  * alias-layout policy schemas (e.g. `#/policy/edge_alias_layout_policy`),
  * RNG/routing policy entries relevant to alias decode compatibility (not RNG usage),
  * policy-digest artefacts that contribute to `edge_universe_hash`.

12.1.2 This section does **not** govern:

* S0 contracts (`s0_gate_receipt_3B`, `sealed_inputs_3B`), which have their own change-control rules.
* S1 contracts (`virtual_classification_3B`, `virtual_settlement_3B`), except where S3 depends on their keys and invariants.
* S2 contracts (`edge_catalogue_3B`, `edge_catalogue_index_3B`); S3 consumes these but does not define their shapes or semantics.
* Upstream segments (1A, 1B, 2A, 3A) except insofar as their digests are referenced in `edge_universe_hash_3B`.
* 2B’s routing implementation (including how it decodes alias tables) — that is governed by 2B + routing policy; S3 must remain compatible with those contracts but does not own them.
* The 3B segment-level validation bundle and `_passed.flag_3B`, which are owned by the terminal 3B validation state.

---

12.2 **Versioning of S3-related contracts**

12.2.1 All 3B contracts that affect S3 MUST be versioned explicitly across:

* `schemas.3B.yaml` — shapes for:

  * `edge_alias_blob_3B` header,
  * `edge_alias_index_3B`,
  * `edge_universe_hash_3B`,
  * any S3 run-summary datasets and alias-layout policy schemas.

* `dataset_dictionary.layer1.3B.yaml` - dataset IDs, `schema_ref`, `path`, `partitioning`, `ordering` for:

  * `edge_alias_blob_3B`,
  * `edge_alias_index_3B`,
  * `edge_universe_hash_3B`,
  * any S3 run-summary datasets.

* `artefact_registry_3B.yaml` — manifest keys, ownership, retention and consumers for these datasets.

12.2.2 Alias-layout and RNG/routing policies that S3 uses for compatibility MUST also be versioned explicitly, e.g.:

* `schemas.3B.yaml#/policy/edge_alias_layout_policy` (layout parameters, grid size, checksum law);
* the routing/RNG policy schema that declares supported alias layout versions for 2B.

12.2.3 Implementations SHOULD follow a semantic-style scheme:

* **MAJOR** — incompatible/breaking changes to shapes, keys, partition law, alias representation, universe-hash semantics, or to the alias → edge mapping.
* **MINOR** — backwards-compatible extensions (new optional fields, new optional components, new enum values that old consumers can safely ignore).
* **PATCH** — non-semantic corrections (typos, doc clarifications, stricter validation that only rejects previously invalid configurations).

12.2.4 S3 MUST ensure (directly or via `s0_gate_receipt_3B.catalogue_versions`) that the versions of:

* `schemas.3B.yaml`
* `dataset_dictionary.layer1.3B.yaml`
* `artefact_registry_3B.yaml`

form a **compatible triplet** for the S3 implementation (e.g. same MAJOR version, or an explicit compatibility matrix). If they do not, S3 MUST fail with `E3B_S3_SCHEMA_PACK_MISMATCH` (or equivalent) and MUST NOT write outputs.

---

12.3 **Backwards-compatible vs breaking changes**

12.3.1 The following are considered **backwards-compatible** (MINOR or PATCH) for S3, provided they preserve all binding guarantees in §§4–9:

* Adding **optional fields** to:

  * `edge_alias_blob_3B` header (e.g. extra diagnostics, additional digests),
  * `edge_alias_index_3B` (e.g. extra per-merchant metrics),
  * `edge_universe_hash_3B.components` (e.g. additional component entries),

  as long as:

  * existing required fields are not removed or repurposed, and
  * older consumers can safely ignore new fields while still enforcing invariants.

* Extending **enumerations** with new values where:

  * existing enum values retain their semantics, and
  * consumers that do not recognise new values can treat them as “other” without misinterpretation (e.g. a new `component.type` that validation tools can ignore).

* Introducing new **optional diagnostics datasets** (e.g. S3 debug tables) that are not relied upon by 2B or validation for correctness.

* Tightening **validation** in ways that only reject previously invalid or underspecified states (e.g. enforcing `edge_count_total_all_merchants` consistency that S3 already assumed).

12.3.2 The following are **breaking** (MAJOR) changes for S3:

* Removing or renaming any **required field** in:

  * `edge_alias_blob_3B` header (e.g. `layout_version`, `blob_sha256_hex`),
  * `edge_alias_index_3B` (e.g. `merchant_id`, `blob_offset_bytes`),
  * `edge_universe_hash_3B` (e.g. `edge_universe_hash`, key components).

* Changing the **type or semantics** of required fields, for example:

  * redefining `blob_sha256_hex` to use a different hash algorithm without a new field,
  * changing the interpretation of `blob_length_bytes`,
  * redefining `edge_universe_hash` combination law without versioning.

* Changing `path`, `partitioning` or `ordering` for any S3 dataset in the dictionary.

* Changing **alias layout semantics** in a way that:

  * modifies the mapping from alias index → `edge_id` for a given manifest and S2 catalogue;
  * changes on-disk structure (element sizes, endianness, alignment) without a new `layout_version` and a MAJOR contract bump.

* Changing the **universe-hash combination law** in a way that would produce a different `edge_universe_hash` for the same set of component digests.

* Changing the set of **mandatory components** for the universe hash (e.g. dropping `edge_alias_blob_sha256_hex` or `edge_catalogue_digest_global` from the component set).

* Introducing RNG into S3’s core algorithm (S3 MUST remain RNG-free).

12.3.3 Any breaking change MUST:

* bump the MAJOR version of `schemas.3B.yaml`;
* be accompanied by coherent updates to `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml`;
* be documented in a 3B/3B.S3 changelog with explicit description of behavioural differences and migration steps;
* be coordinated with 2B and 3B validation, since they rely on S3 outputs for alias decode and universe-hash checks.

---

12.4 **Mixed-version environments**

12.4.1 A **mixed-version environment** arises when:

* historical S3 outputs (`edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`) exist on disk that were produced under an older S3 schema/layout version; and
* the currently deployed schemas/dictionary/registry reflect a newer S3 contract.

12.4.2 S3 is responsible only for **writing** outputs for the **current** contract. It MUST:

* use the current schemas, dictionary and registry to produce new outputs;
* **not** rewrite or reinterpret legacy S3 artefacts in place as if they matched the new schema/layout.

12.4.3 Reading and interpreting historical S3 artefacts under older contracts is the responsibility of:

* offline reporting and debugging tools, and/or
* explicit migration tooling and/or
* a version-aware validation harness.

S3 MUST NOT silently assume old artefacts conform to the new layout; they are effectively “frozen” under their original contract.

12.4.4 If S3 is invoked for a `{seed, parameter_hash, manifest_fingerprint}` where S3 artefacts already exist but:

* do not validate against the **current** schemas, or
* differ from the newly recomputed outputs,

S3 MUST:

* treat this as an environment / manifest inconsistency;
* fail with `E3B_S3_OUTPUT_INCONSISTENT_REWRITE` (or equivalent);
* not overwrite existing artefacts.

Operators MUST either:

* keep using the old artefacts under tools that understand their old version, and avoid re-running S3 for that fingerprint; or
* migrate and re-emit S3 artefacts under a **new** manifest (and/or schema version), then update consumers to use the new contract.

---

12.5 **Migration & deprecation**

12.5.1 When introducing new **fields or behaviours** that are intended to become mandatory in S3, the recommended pattern is:

1. **MINOR phase** (introduce as optional):

   * add new fields to `edge_alias_blob_3B` / `edge_alias_index_3B` / `edge_universe_hash_3B` as optional in `schemas.3B.yaml`;
   * update S3 to populate them where possible;
   * update 2B and validation to prefer them when present, but fall back gracefully when absent.

2. **MAJOR phase** (promote to required):

   * after adoption and validation, mark these fields as required in the schemas;
   * remove dependence on older structures in 2B / validation as needed.

12.5.2 Deprecating legacy fields or alias layouts SHOULD also be done in two steps:

* Step 1 (MINOR):

  * mark field(s) or layout version(s) as deprecated in documentation and schema comments;
  * ensure S3 can still produce them, but encourage 2B/validation to move to newer fields/layouts.

* Step 2 (MAJOR):

  * stop producing deprecated fields/layouts;
  * update schemas to reflect removal;
  * ensure consumers are no longer relying on the old behaviour.

12.5.3 For alias layouts specifically:

* A new layout (e.g. `layout_version = 2`) SHOULD be introduced as an additional, optional path, while retaining support for the previous one.
* S3 MUST deterministically choose which layout to use based on configuration, and record the layout version.
* 2B MUST explicitly support the chosen layout before it is used in production.
* Only when all consumers support `layout_version = 2` SHOULD `layout_version = 1` be deprecated and eventually removed in a MAJOR contract bump.

---

12.6 **Compatibility with upstream segments & other 3B states**

12.6.1 Changes to S3 MUST respect the **authority boundaries** of upstream segments:

* S1 remains authority on virtual classification and settlement nodes; S3 cannot alter merchant identity or settlement semantics.
* S2 remains authority on edge universe and `edge_weight` semantics; S3 cannot add/remove edges or reinterpret `edge_weight` beyond quantisation allowed by alias layout.
* 3A remains authority on zone-universe hash and zone allocation; S3 may reference but not redefine it.

12.6.2 If upstream segments change:

* `edge_catalogue_3B` / `edge_catalogue_index_3B` schemas;
* merchant identifier formats;
* alias-relevant policy/digest artefacts,

the 3B contracts and S3 implementation MUST be updated accordingly. S3 MUST:

* adapt to new schemas in a way that preserves existing behaviour where feasible;
* treat changes that alter edge semantics (for the same manifest) as breaking, and require a new manifest and/or MAJOR bump.

12.6.3 Changes to **2B routing** and decode logic MUST be coordinated with S3:

* S3 must build alias tables in a layout that 2B’s decoder supports;
* any change to 2B’s expectations (e.g. alias interpretation, index mapping) that would break compatibility MUST be accompanied by a MAJOR version bump in alias layout contracts and coordinated S3/2B changes.

12.6.4 The 3B validation state relies on S3 outputs to assert segment-level correctness. Any changes to S3 that alter:

* digest semantics;
* alias coverage expectations;
* component list in `edge_universe_hash_3B`,

MUST be reflected in the validation spec and tests.

---

12.7 **Change documentation & review**

12.7.1 Any non-trivial change to S3 behaviour, schemas or catalogues MUST be:

* documented in a human-readable changelog (e.g. `CHANGELOG.3B.S3.md` or a shared `CHANGELOG.3B.md` with S3-specific entries);
* tagged with corresponding schema/dictionary/registry version numbers;
* accompanied by clear migration notes (e.g. any need for a new manifest, changes to 2B/validation expectations).

12.7.2 Before deploying S3-affecting changes, implementers SHOULD:

* run regression tests across representative and worst-case manifests to ensure:

  * alias tables remain deterministic and consistent with S2 weights;
  * blob/index invariants in §§5–8 hold;
  * universe hash is stable under unchanged inputs;
  * 2B and 3B validation continue to work correctly with the new contracts.

* explicitly test **idempotence**:

  * run S3 twice under the same `{seed, parameter_hash, manifest_fingerprint}` and confirm that blob, index and universe hash are byte-identical (or that any difference is intentional and comes with a new manifest/schema version).

12.7.3 Where this section conflicts with `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` or `artefact_registry_3B.yaml`, those artefacts SHALL be treated as **authoritative**. This section MUST be updated in the next non-editorial revision to reflect the contracts actually in force, while preserving the core guarantees of:

* determinism;
* identity/partition discipline;
* alias-layout compatibility;
* and correct edge-universe hashing.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

> This appendix is descriptive only. If anything here conflicts with a Binding section or with JSON-Schema / dictionary / registry entries, those authoritative sources win.

---

### 13.1 Identity & governance

* **`seed`**
  Layer-1 Philox seed for the run. Shared across segments for a given manifest; part of S3’s run identity triple.

* **`parameter_hash`**
  Tuple-hash over the governed 3B parameter set (including S3-relevant config such as alias layout selection). Logical identity input; not a partition key for S3 outputs.

* **`manifest_fingerprint`**
  Hash of the full Layer-1 manifest (ingress assets, code, policies, artefact set). Primary partition key (with `seed`) for S3’s alias artefacts and the sole partition key for the universe-hash descriptor.

* **`run_id`**
  Optional, opaque identifier for a concrete execution of S3 under a given `{seed, parameter_hash, manifest_fingerprint}`. Used for logs / run-report only; MUST NOT influence outputs.

---

### 13.2 Sets & merchant/edge notation

* **`V`**
  Virtual merchant set, as defined by S1 (merchants classified as virtual). S3 does not re-define `V` but may check that all merchants with edges in S2 are in `V`.

* **`V_edge`**
  Subset of `V` that actually has edges in S2:
  `V_edge = { m ∈ V | edge_count_total(m) > 0 }`
  (in full-edge mode; may differ in special “no-edge” modes).

* **`E_m`**
  Ordered edge list for merchant `m`, as seen by S3 after canonical sorting:
  `E_m = (e₀, e₁, …, eₙ₋₁)`
  where each `eᵢ` corresponds to a row in `edge_catalogue_3B` for that merchant.

* **`n_m`**
  Number of edges for merchant `m`:
  `n_m = |E_m| = edge_count_total(m)`.

* **`E_total`**
  Total number of edges in the universe:
  `E_total = Σ₍m∈V_edge₎ n_m`.

---

### 13.3 Weight and grid notation

* **`w_raw(m,i)`**
  Raw edge weight for merchant `m` and edge index `i`, taken directly from S2 `edge_weight` in canonical order.

* **`w_pos(m,i)`**
  Non-negative version of `w_raw`, after clamping or checks (exact behaviour defined by spec / policy).

* **`Z_m`**
  Normalisation constant for merchant `m`:
  `Z_m = Σᵢ w_pos(m,i)`.

* **`w_norm(m,i)`**
  Normalised weight for merchant `m`:
  `w_norm(m,i) = w_pos(m,i) / Z_m` (if `Z_m > 0`), or a policy-defined fallback (e.g. uniform) if allowed.

* **`G`**
  Alias grid size per merchant, e.g. an integer mass total:

  * often `G = 2ᵇ` for some bit width `b`, or
  * some fixed integer chosen in alias layout policy.

* **`M_target(m,i)`**
  Real-valued target mass before integerisation:
  `M_target(m,i) = G * w_norm(m,i)`.

* **`M(m,i)`**
  Final integer mass for merchant `m` and edge index `i` after quantisation and largest-remainder step, such that:

  * `M(m,i) ≥ 0` for all `i`,
  * Σᵢ `M(m,i) = G`.

---

### 13.4 Alias-table notation

* **`alias_table_length(m)`**
  Length (number of slots) of the alias table for merchant `m`. Typically `= n_m`, but may be padded (e.g. to a power of two) if the layout policy requires.

* **`prob_int(m, i)`**
  Integer or fixed-point representation of probability mass for alias slot `i` in merchant `m`’s alias table (encoded per alias layout policy; derived from `M(m,i)` and `G`).

* **`alias(m, i)`**
  Alias index for slot `i` in merchant `m`’s alias table. An integer in `[0, alias_table_length(m)−1]`, representing an alternative edge index when the primary slot is “overflowed”.

* **Alias table semantics (per merchant)**
  At routing time (in 2B), an alias sample for merchant `m` typically works as:

  1. Draw `i ∈ {0,…,alias_table_length(m)−1}` uniformly.
  2. Draw a uniform `u∈[0,1)`.
  3. If `u < prob(i)` → choose edge index `i`, else choose `alias(i)`.

  S3’s job is to provide `prob_int`/`alias` in a layout that encodes this logic.

* **Canonical edge index mapping**
  A deterministic mapping from alias index `i` to an edge in `E_m`:

  * normally “edge at position `i` in the canonical `(e₀,…,eₙ₋₁)` ordering”, or
  * via `edge_index_base` + `i`, as declared in the alias layout policy.

---

### 13.5 Blob/index notation

* **`edge_alias_blob_3B`**
  S3 egress. Single binary blob per `{seed, fingerprint}` containing a header and concatenated per-merchant alias segments.

* **`edge_alias_index_3B`**
  S3 egress. Table dataset that indexes per-merchant alias segments in the blob (offsets, lengths, checksums) plus a global summary row.

* **`layout_version`**
  Version identifier for the alias layout implementation (e.g. integer or string). S3 writes this into the blob header and index rows; 2B’s decoder uses it to choose the decode path.

* **`blob_offset_bytes`**
  For a given merchant row in `edge_alias_index_3B`, the byte offset into `edge_alias_blob_3B` where that merchant’s alias segment begins.

* **`blob_length_bytes`**
  Length of that merchant’s alias segment in bytes.

* **`merchant_alias_checksum`**
  Per-merchant checksum of the alias segment (algorithm defined in alias-layout policy; e.g. SHA-256, CRC32).

* **`blob_sha256_hex`**
  Global digest of the alias blob recorded in header and index; usually a SHA-256 hex string.

---

### 13.6 Universe-hash notation

* **`edge_universe_hash_3B`**
  S3 egress. Fingerprint-scoped JSON descriptor for the **virtual edge universe hash** and its component digests.

* **`edge_universe_hash`**
  Combined digest (typically SHA-256 hex) representing the bound virtual edge universe (S2 edge catalogue + policies + S3 alias blob/index). Used by 2B and validation to detect drift.

* **`components`**
  Structured collection in `edge_universe_hash_3B` listing individual digests, e.g.:

  * `cdn_policy_digest`
  * `alias_layout_policy_digest`
  * `rng_policy_digest` (for compatibility)
  * `spatial_surface_digest_*` (if included)
  * `edge_catalogue_digest_global`
  * `edge_alias_blob_sha256_hex`
  * `edge_alias_index_sha256_hex`

* **Combination law**
  The canonical method of turning `components` into `edge_universe_hash` (e.g. sort components by name, concatenate bytes of their digests, hash with SHA-256). Defined normatively in the S3 spec.

---

### 13.7 Error & status codes (S3)

* **`E3B_S3_*`**
  Namespace for 3B.S3 canonical error codes, for example:

  * `E3B_S3_SCHEMA_PACK_MISMATCH`
  * `E3B_S3_REQUIRED_INPUT_NOT_SEALED`
  * `E3B_S3_ALIAS_LAYOUT_POLICY_INVALID`
  * `E3B_S3_WEIGHT_VECTOR_INVALID`
  * `E3B_S3_QUANTISATION_FAILED`
  * `E3B_S3_ALIAS_CONSTRUCTION_FAILED`
  * `E3B_S3_ALIAS_INDEX_INCONSISTENT_WITH_BLOB`
  * `E3B_S3_UNIVERSE_HASH_MISMATCH`
  * `E3B_S3_NONDETERMINISTIC_OUTPUT`

  (see §9 for full list and semantics).

* **`status ∈ {"PASS","FAIL"}`**
  Run-level status for S3, as used in logs and run-report.

* **`severity ∈ {"FATAL","WARN"}`**
  Severity associated with a given `E3B_S3_*` error code.

---

### 13.8 Miscellaneous abbreviations

* **CDN** — Content Delivery Network (here: logical edge network for virtual merchants).
* **FK** — Foreign key (join key across datasets).
* **IO** — Input/Output (filesystem or object-store operations).
* **RNG** — Random Number Generator (Philox2x64-10 across Layer-1; S3 is RNG-free).
* **SLO** — Service Level Objective (latency / reliability target; informative).
* **tzid** — Timezone identifier (IANA tzid).

---

13.9 **Cross-reference**

Authoritative definitions for the concepts mentioned here are found in:

* Layer-wide schemas & RNG: `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`.
* Upstream segments: `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml` + their dictionaries/registries.
* 3B contracts: `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, `artefact_registry_3B.yaml`.
* S1/S2 specs: for virtual classification, settlement nodes, and edge catalogue semantics.

This appendix is intended as a vocabulary aid when reading and implementing **3B.S3 — Edge alias tables & virtual edge universe hash**; it does not add new normative requirements.

---
