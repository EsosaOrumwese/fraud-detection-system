# 3B.S2 — CDN edge catalogue construction

## 1. Purpose & scope *(Binding)*

1.1 **State identity and role in subsegment 3B**

1.1.1 This state, **3B.S2 — CDN edge catalogue construction** (“S2”), is the first **RNG-bearing data-plane state** in Layer-1 subsegment **3B — Virtual merchants & CDN surfaces**. It executes only after:

* **3B.S0 — Gate & environment seal** has successfully sealed the 3B universe for the target `manifest_fingerprint`, and
* **3B.S1 — Virtual classification & settlement node construction** has successfully produced the authoritative virtual merchant set and settlement nodes for the same `{seed, manifest_fingerprint}`.

1.1.2 S2’s primary role is to materialise, for each virtual merchant, a governed **CDN edge universe** that downstream routing can use. Concretely, S2:

* takes the **virtual merchant universe** and **settlement nodes** from S1,
* applies a governed **edge-budget and geography policy** to decide how many edges to place per merchant and per country, and
* uses governed spatial and timezone assets, together with Philox RNG, to construct a **catalogue of edge nodes** with:

  * fixed coordinates,
  * assigned countries,
  * operational timezones, and
  * per-edge weights.

1.1.3 S2 does **not** perform per-arrival routing. Instead, it produces a **static edge catalogue** that later states (3B.S3 and 2B’s virtual routing branch) treat as the only source of edge nodes for virtual merchants.

---

1.2 **High-level responsibilities**

1.2.1 S2 MUST:

* read the **sealed environment** produced by S0 (`s0_gate_receipt_3B`, `sealed_inputs_3B`);

* consume S1 outputs:

  * `virtual_classification_3B` — to identify the virtual merchant set `V`, and
  * `virtual_settlement_3B` — to anchor each virtual merchant in a legal settlement jurisdiction;

* apply **CDN edge-budget policies** (e.g. `cdn_country_weights` and any per-merchant overrides) to determine, for each `m ∈ V`:

  * the total number of edges to allocate, and
  * the integer numbers of edges per country;

* use governed **spatial surfaces** (1B/3B tile & weight surfaces, HRSL / population rasters, world polygons) to place edge nodes:

  * choose which tiles or cells receive edge nodes,
  * use Philox RNG to jitter edge coordinates within tiles,
  * enforce that edge coordinates lie inside the intended country polygon;

* compute a per-edge **operational timezone** (`tzid_operational`) using tz-world / tzdb / overrides sealed by S0;

* construct a deterministic **edge identity** (`edge_id`) per `(merchant, edge_slot)` and associate:

  * `merchant_id`,
  * `country_iso`,
  * `edge_latitude`, `edge_longitude`,
  * `tzid_operational`,
  * `edge_weight`,
  * and provenance fields tying each edge back to its policies and spatial artefacts;

* materialise these results in 3B-owned datasets (e.g. `edge_catalogue_3B` and an index/digest surface) under the paths and partition laws declared in `dataset_dictionary.layer1.3B.yaml`.

1.2.2 S2 MUST ensure that its outputs are sufficient for:

* **3B.S3** to build stable **edge alias tables** and a **virtual edge universe hash** without re-examining raw policy/raster configuration;
* **2B’s virtual routing branch** to select an edge per transaction using only 2B’s routing RNG streams and S3’s alias/universe surfaces, without re-doing edge placement.

---

1.3 **RNG scope and determinism**

1.3.1 S2 is **RNG-bearing by design**. It MUST use Philox-based RNG only for:

* selecting edges within tile/cell allocations (if a further random permutation is required), and
* jittering edge coordinates within tiles or cells (e.g. uniform in pixel bounds, with bounded resampling).

1.3.2 S2 MUST NOT use RNG for:

* merchant-level classification (this is owned by S1);
* per-arrival routing or edge selection (this is owned by 2B);
* determining total edge budgets or per-country integer allocations (those MUST be RNG-free and reproducible functions of policies and counts).

1.3.3 S2 MUST:

* adhere to the layer-wide RNG envelope defined in `schemas.layer1.yaml` (Philox algorithm, envelope fields, audit/trace discipline);
* use only the RNG streams, labels and budgets reserved for 3B.S2 in the routing/3B RNG policy pack;
* emit one or more explicit RNG event families for edge placement (e.g. tile assignment and jitter), with each event carrying a valid envelope and “actual-use” draw counts.

1.3.4 Given:

* the identity triple `{seed, parameter_hash, manifest_fingerprint}`,
* the sealed artefacts recorded in `sealed_inputs_3B`,
* and a fixed 3B RNG policy,

S2’s outputs MUST be **reproducible**: re-executing S2 with the same inputs MUST yield bit-identical `edge_catalogue_3B` and index/digest datasets, and identical RNG audit/trace logs, modulo any explicitly documented versioned changes to the RNG policy.

---

1.4 **Relationship to upstream segments and other 3B states**

1.4.1 S2 relies on upstream segments as follows:

* **1A (merchant outlets)** — for the merchant universe and attributes;
* **1B (site placement)** — for spatial tiling and prior surfaces (e.g. `tile_index`, `tile_weights`) and for geospatial assets (HRSL rasters, world polygons);
* **2A (civil time)** — for tz-world and tzdb artefacts, and semantic rules for converting coordinates to tzids;
* **3A (cross-zone merchants)** — for zone allocation and routing universe hash (used by 2B and validation, but S2 does not modify 3A’s results);
* **3B.S1 (virtual classification & settlement)** — for the virtual merchant set `V` and per-merchant settlement nodes.

S2 MUST treat all these upstream artefacts as **read-only** and MUST NOT modify or reinterpret their semantics.

1.4.2 Within subsegment 3B:

* S2 MUST treat S1 outputs as the **sole authority** on which merchants are virtual and what their legal settlement nodes are;
* S2 MUST publish `edge_catalogue_3B` (and any S2 indexes/digests) as the **sole authority** on static CDN edge nodes for virtual merchants;
* downstream 3B states MUST NOT regenerate edges themselves but rely on S2’s catalogue.

1.4.3 For **2B’s virtual routing branch**, S2 provides the edge-level “world” on top of which 2B can:

* construct or consume alias tables (via S3) for efficient per-arrival edge selection;
* derive apparent geolocation, IP-like country and operational tz features from `edge_catalogue_3B`, while using settlement information from S1 for accounting.

---

1.5 **Out-of-scope behaviour**

1.5.1 The following concerns are explicitly **out of scope** for S2 and are handled by other states:

* **Virtual classification** of merchants (S1) — S2 MUST NOT re-decide which merchants are virtual or non-virtual.
* Construction of **settlement nodes** and assignment of `tzid_settlement` (S1) — S2 consumes these as inputs.
* Construction of **edge alias tables** and **virtual edge universe hashes** (S3) — S2 only provides the raw edge catalogue and any supporting index/digest surfaces needed for S3.
* **Per-arrival routing** and emission of `cdn_edge_pick` or similar routing events (2B) — S2 does not route individual transactions.
* 3B’s segment-level validation bundle and `_passed.flag` — these are owned by the terminal 3B validation state.

1.5.2 S2 MUST NOT:

* alter or delete physical outlets or `site_locations` from 1B;
* alter or delete `site_timezones` or re-interpret 2A’s time semantics;
* synthesize merchant-level behaviour not derived from S1 or sealed policies (e.g. inventing new virtual merchants or settlement nodes);
* emit its own segment-level PASS flag or validation bundle.

1.5.3 S2’s scope is therefore strictly:

> Given a sealed environment and a set of virtual merchants with settlement nodes, **construct a reproducible, policy-governed CDN edge catalogue (nodes, countries, coordinates, operational timezones, weights) for each virtual merchant**, and nothing more.

---

### Contract Card (S2) - inputs/outputs/authorities

**Inputs (authoritative; see Section 2 for full list):**
* `s0_gate_receipt_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S0
* `sealed_inputs_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S0
* `virtual_classification_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3B.S1
* `virtual_settlement_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3B.S1
* `cdn_country_weights` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `hrsl_raster` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required
* `route_rng_policy_v1` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `site_locations` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional
* `site_timezones` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional

**Authority / ordering:**
* S2 is the sole authority on edge catalogue construction and S2 RNG evidence.

**Outputs:**
* `edge_catalogue_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; gate emitted: none
* `edge_catalogue_index_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; gate emitted: none
* `rng_event_edge_tile_assign` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; gate emitted: none
* `rng_event_edge_jitter` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; gate emitted: none
* `rng_audit_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; gate emitted: none (shared append-only log)
* `rng_trace_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; gate emitted: none (shared append-only log)

**Sealing / identity:**
* External policy/ref inputs MUST appear in `sealed_inputs_3B` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or RNG envelope violations -> abort; no outputs published.

## 2. Preconditions & gated inputs *(Binding)*

2.1 **Execution context & identity**

2.1.1 S2 SHALL execute only in the context of a Layer-1 run where the identity triple

> `{seed, parameter_hash, manifest_fingerprint}`

has already been resolved by the enclosing engine and is consistent with the Layer-1 identity and hashing policy.

2.1.2 At entry, S2 MUST be provided with:

* `seed` — the Layer-1 Philox seed for this run;
* `parameter_hash` — the governed parameter-hash for the 3B configuration;
* `manifest_fingerprint` — the enclosing manifest fingerprint.

2.1.3 S2 MUST NOT recompute or override these identity values. It MUST:

* treat them as read-only inputs; and
* later embed `seed` and `manifest_fingerprint` into its own outputs exactly as provided, and ensure they match the values recorded in `s0_gate_receipt_3B`.

---

2.2 **Dependence on 3B.S0 (gate & sealed inputs)**

2.2.1 For a given `manifest_fingerprint`, S2 MAY proceed only if the following artefacts exist and are schema-valid:

* `s0_gate_receipt_3B` at its canonical fingerprint-partitioned path;
* `sealed_inputs_3B` at its canonical fingerprint-partitioned path.

2.2.2 Before performing any data-plane work, S2 MUST:

* load and validate `s0_gate_receipt_3B` against `schemas.3B.yaml#/validation/s0_gate_receipt_3B`;
* load and validate `sealed_inputs_3B` against `schemas.3B.yaml#/validation/sealed_inputs_3B`;
* assert that `segment_id = "3B"` and `state_id = "S0"` in the gate receipt;
* assert that `manifest_fingerprint` in the gate receipt equals the run’s `manifest_fingerprint`;
* where present, assert that `seed` and `parameter_hash` in the gate receipt equal the values provided to S2.

2.2.3 S2 MUST also assert that, in `s0_gate_receipt_3B.upstream_gates`:

* `segment_1A.status = "PASS"`;
* `segment_1B.status = "PASS"`;
* `segment_2A.status = "PASS"`;
* `segment_3A.status = "PASS"`.

If any of these statuses is not `"PASS"`, S2 MUST treat the 3B environment as **not gated** and fail with a FATAL upstream-gate error. S2 MUST NOT attempt to re-verify or repair upstream validation bundles.

2.2.4 If `s0_gate_receipt_3B` or `sealed_inputs_3B` is missing, schema-invalid, or inconsistent with the run identity, S2 MUST fail fast and MUST NOT attempt to “re-seal” inputs itself.

---

2.3 **Dependence on 3B.S1 (virtual set & settlement nodes)**

2.3.1 S2 MUST treat 3B.S1 as a hard functional precondition. For a given `{seed, manifest_fingerprint}`, S2 MAY proceed only if:

* `virtual_classification_3B@seed={seed}, fingerprint={manifest_fingerprint}` exists and is schema-valid;
* `virtual_settlement_3B@seed={seed}, fingerprint={manifest_fingerprint}` exists and is schema-valid.

2.3.2 Before constructing edges, S2 MUST:

* load and validate `virtual_classification_3B` against `schemas.3B.yaml#/plan/virtual_classification_3B`;
* load and validate `virtual_settlement_3B` against `schemas.3B.yaml#/plan/virtual_settlement_3B`;
* verify key invariants required by S1 (identity echoes, key uniqueness, join consistency between the two datasets).

2.3.3 S2 MUST derive the virtual merchant set

> `V = { m | virtual_classification_3B(m).is_virtual = 1 }`

only from `virtual_classification_3B`. S2 MUST NOT re-evaluate MCC/channel rules or any classification policy to decide which merchants are virtual.

2.3.4 For each `m ∈ V`, S2 MUST verify that exactly one settlement row exists in `virtual_settlement_3B` for the corresponding key (e.g. `merchant_id`). If this 1:1 mapping is violated (where S1’s spec requires it), S2 MUST fail with a FATAL S1-contract error and MUST NOT attempt to invent or modify settlement nodes.

2.3.5 In “virtual-disabled” configurations (where S1 deliberately produces `V = ∅`), S2 MUST treat `V = ∅` as a valid precondition and behave according to its own spec for that mode (typically: produce empty edge outputs).

---

2.4 **Required 3B contracts (schemas, dictionary, registry)**

2.4.1 S2 MUST operate against a coherent set of 3B contracts:

* `schemas.3B.yaml`;
* `dataset_dictionary.layer1.3B.yaml`;
* `artefact_registry_3B.yaml`.

2.4.2 S2 MAY rely on the versions recorded in `s0_gate_receipt_3B.catalogue_versions` or MAY reload these contracts. In either case, S2 MUST verify:

* that they form a **compatible triplet** according to 3B’s versioning rules (e.g. shared MAJOR version); and
* that they define entries for all S2 outputs (`edge_catalogue_3B`, `edge_catalogue_index_3B`, S2 RNG logs) and inputs (S1 outputs, spatial/tz policies, etc.) it expects to use.

2.4.3 If S2 detects:

* missing schema refs,
* missing dataset IDs for S2 outputs,
* or an incompatible schema/dictionary/registry version set,

it MUST fail with a FATAL contract error and MUST NOT attempt to guess shapes or write outputs with ad-hoc paths.

---

2.5 **Required sealed artefacts for S2 (policies, spatial, tz, RNG)**

2.5.1 S2 MUST treat `sealed_inputs_3B` as the **sole authority** for which artefacts are permissible inputs. For S2 to run, `sealed_inputs_3B` MUST contain rows for at least the following **mandatory artefacts**, with well-formed entries:

**CDN edge-budget & geography policies**

* `cdn_country_weights` (or equivalent) — defining, at minimum:

  * country-level weights over ISO country codes;
  * any global configuration needed to map weights into per-merchant edge budgets (e.g. target total edges per merchant, min/max constraints, scaling factors).
* Optional per-merchant override policy IDs (if used) — e.g. “large merchant” overrides for higher edge budgets.

**Spatial inputs**

* Either:

  * 1B’s tile surfaces (`tile_index`, `tile_weights`) for each country, as declared in the 1B dictionary/registry, **or**
  * 3B-specific tiling surfaces declared as inputs for S2.
* HRSL / population raster(s) (or equivalent spatial priors) if S2 works below tile granularity or needs to verify tile priors.
* World-country polygons used to confirm that jittered edge coordinates stay within the intended country.

**Timezone inputs**

* tz-world polygons sealed by S0 (same release as 2A uses);
* a pinned tzdb archive / release tag;
* any tz override packs if S2 applies overrides for operational tz (e.g. for special jurisdictions).

**RNG and routing policy packs**

* The Layer-1 routing / 3B RNG policy artefact(s) that define:

  * the RNG algorithm and envelope (in alignment with `schemas.layer1.yaml`);
  * the stream IDs, substream labels and budgets assigned to 3B.S2 edge-placement events (e.g. `module="3B.S2"`, `substream_label ∈ {"edge_tile_assign","edge_jitter"}`).

2.5.2 For each such logical artefact, S2 MUST be able to:

* find its row in `sealed_inputs_3B` (using `logical_id`, `owner_segment`, `artefact_kind`);
* resolve `path` and `schema_ref` (if non-null);
* open the artefact;
* and, if hardened mode is enabled, recompute its SHA-256 digest and assert equality to `sha256_hex`.

2.5.3 If **any** mandatory artefact required by S2’s algorithm is missing from `sealed_inputs_3B`, unreadable, schema-incompatible, or digest-mismatched, S2 MUST fail with a FATAL sealed-input error and MUST NOT fall back to resolving the artefact directly via the dictionary/registry.

---

2.6 **Required data-plane inputs (spatial surfaces & upstream datasets)**

2.6.1 If S2 reuses 1B’s tiling, S2 MUST have access (via `sealed_inputs_3B`) to:

* `tile_index` (per-country tile definitions with centroid, bounds and membership rules);
* `tile_weights` (per-country tile weights consistent with the raster(s) and quantisation policy).

These remain owned by 1B; S2 consumes them read-only.

2.6.2 If 3B defines its own tiling surfaces, equivalent datasets MUST be declared and sealed, with schemas that clearly define:

* key fields identifying country and tile;
* geometric extent of each tile;
* weight or mass per tile.

2.6.3 S2 MAY also read upstream datasets for consistency checks (e.g. `site_locations` or `site_timezones`) if they are present in `sealed_inputs_3B`. Such reads:

* MUST be read-only;
* MUST not be required for S2’s correctness unless explicitly called out in the 3B spec;
* MUST respect the owning segment’s schema and partition law.

---

2.7 **Feature flags and operational modes**

2.7.1 If the engine exposes configuration flags that affect S2 behaviour (e.g. `enable_virtual_edges`, `shared_tile_surfaces`, `fixed_edges_per_merchant`), S2 MUST treat them as part of the governed 3B parameter set that contributed to `parameter_hash`.

2.7.2 S2’s spec MUST clearly document the behaviour in each mode, including:

* **Virtual edges enabled** — normal mode:

  * S2 builds a full edge catalogue for each `m ∈ V` using `cdn_country_weights` and tile surfaces.
* **Virtual edges disabled**:

  * S2 either short-circuits and writes empty edge outputs, **or**
  * skips execution entirely (with the harness treating S2 as intentionally inactive for that manifest).

The chosen semantics MUST be unambiguous and MUST be encoded in `schemas.3B.yaml` and 3B documentation.

2.7.3 If a feature flag enabling additional policies or artefacts is set (e.g. “special regions policy”, “high-traffic merchant tiering”), S2 MUST:

* treat the corresponding policy artefacts as **mandatory** in that mode;
* fail if they are not present in `sealed_inputs_3B`.

---

2.8 **Scope of gated inputs & downstream obligations**

2.8.1 The union of:

* S1 outputs (`virtual_classification_3B`, `virtual_settlement_3B`), and
* the artefacts S2 is allowed to read according to `sealed_inputs_3B` (policies, spatial and tz assets, RNG policies, upstream tiling),

SHALL define the **closed input universe** for 3B.S2.

2.8.2 S2 MUST NOT:

* read any artefact that is not listed in `sealed_inputs_3B` for the target `manifest_fingerprint`;
* use environment variables, local files, network calls, or hard-coded paths as additional edge-construction inputs.

2.8.3 Downstream 3B states (S3, 3B validation) and 2B’s virtual routing branch MAY assume that:

* S2’s edge catalogue was constructed **only** from artefacts sealed in `sealed_inputs_3B` and S1 outputs;
* any missing or inconsistent artefact that would affect edge placement would have caused S2 to fail rather than produce partial or silently degraded results.

2.8.4 If, during execution, S2 discovers that it requires an artefact that is not present in `sealed_inputs_3B` (e.g. a new policy introduced in the spec but not in S0’s sealing logic), S2 MUST treat this as an S0/contract configuration error and:

* fail fast;
* NOT attempt on-the-fly resolution of the missing artefact;
* rely on S0 and catalogue updates to correct the environment before a subsequent run.

---

## 3. Inputs & authority boundaries *(Binding)*

3.1 **Control-plane inputs from 3B.S0**

3.1.1 S2 SHALL treat the following 3B.S0 artefacts as required control-plane inputs for the target `manifest_fingerprint`:

* `s0_gate_receipt_3B` (fingerprint-scoped JSON);
* `sealed_inputs_3B` (fingerprint-scoped table).

3.1.2 For S2, `s0_gate_receipt_3B` is the **sole authority** on:

* the identity triple `{seed, parameter_hash, manifest_fingerprint}` that S2 MUST embed in its outputs;
* upstream gate status for segments 1A, 1B, 2A, 3A;
* the catalogue versions (`schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, `artefact_registry_3B.yaml`) S2 is expected to be compatible with.

3.1.3 `sealed_inputs_3B` is the **sole authority** on which artefacts S2 MAY read. S2 MUST NOT:

* resolve or open artefacts that are not listed in `sealed_inputs_3B` for the target `manifest_fingerprint`, even if they are resolvable via other catalogues;
* infer additional inputs from hard-coded paths or environment variables.

3.1.4 When S2 uses any artefact, it MUST:

* locate its row in `sealed_inputs_3B` by `logical_id` (and, if needed, `owner_segment` / `artefact_kind`);
* treat `path` in that row as the canonical storage location;
* treat `schema_ref` as the canonical JSON-Schema anchor (if non-null);
* treat `sha256_hex` as the canonical digest for integrity checks.

---

3.2 **Virtual merchant & settlement inputs (from 3B.S1)**

3.2.1 S2 MUST treat the following datasets as **binding data-plane inputs** from S1 for the target `{seed, manifest_fingerprint}`:

* `virtual_classification_3B` — authoritative virtual membership surface;
* `virtual_settlement_3B` — authoritative settlement node per virtual merchant.

3.2.2 The shapes and semantics of these datasets are governed by `schemas.3B.yaml` and the 3B.S1 spec. S2 MUST:

* treat S1’s schemas and the 3B dataset dictionary as the **only authority** on their structure (keys, types, required fields);
* treat their contents as **read-only**;
* not delete, append or update any rows in these datasets.

3.2.3 S2 MUST derive the virtual merchant set `V` **only** from `virtual_classification_3B`:

* `V = { m | virtual_classification_3B(m).is_virtual = 1 }`
  (or equivalent, if a `classification` enum is used).

S2 MUST NOT re-evaluate raw MCC/channel rules, brand rules, or any other classification policy to determine virtual vs non-virtual merchants.

3.2.4 S2 MUST treat `virtual_settlement_3B` as the **sole authority** on settlement nodes for virtual merchants:

* S2 MUST NOT invent alternative settlement coordinates;
* S2 MUST NOT alter `tzid_settlement` or settlement coordinates;
* if S2 needs to reconcile edge geography with settlement geography (e.g. for validation or reporting), it MUST do so by **referencing**, not modifying, `virtual_settlement_3B`.

---

3.3 **CDN edge-budget & geography policy inputs**

3.3.1 S2 MUST consume one or more **CDN policy artefacts** that define:

* the **country-level edge mix** (e.g. `cdn_country_weights`), and
* any **per-merchant edge-budget rules** or overrides.

These artefacts SHALL be registered in `artefact_registry_3B.yaml` and sealed in `sealed_inputs_3B`.

3.3.2 The CDN policy pack(s) MUST be treated as the **sole authority** on:

* the target country-mix vector over `country_iso` codes;
* any rules mapping merchants into classes with different edge budgets (e.g. small/medium/large merchant tiers);
* any hard constraints on edge counts (e.g. `min_edges_per_merchant`, `max_edges_per_merchant`).

3.3.3 S2 MUST:

* compute per-merchant **total edge budgets** and per-merchant, per-country **fractional edge targets** as a deterministic, RNG-free function of these policies;
* integerise these targets using a documented, deterministic rounding + tie-break procedure;
* NOT introduce any additional ad-hoc or implicit rules for budgets that are not encoded in the policy artefacts or 3B spec.

3.3.4 If separate policies exist for:

* global country weights, and
* merchant-class-specific overrides,

S2 MUST apply them according to a documented precedence order (e.g. merchant override ≻ class override ≻ global default). That order MUST be encoded in policy or in this spec and MUST NOT be left implicit in code.

---

3.4 **Spatial inputs (tiles, rasters, polygons)**

3.4.1 S2 SHALL use **spatial surfaces** to place edge nodes. Depending on design, these surfaces are either:

* 1B-owned tiling datasets (`tile_index`, `tile_weights`) sealed and documented in 1B’s contracts, **or**
* 3B-specific tiling datasets created for virtual edge placement.

In either case, S2 MUST treat the owning segment’s schema/dictionary as the **authority** on these surfaces.

3.4.2 For tiling surfaces, S2 MUST know, at minimum, per tile:

* `country_iso` (or equivalent),
* `tile_id` (unique within the country or globally),
* tile geometry (extent or centroid and size),
* tile weight (mass) consistent with a declared prior (e.g. uniform / area / population).

3.4.3 S2 MUST:

* treat `tile_index` as the sole authority on which raster cells / tiles belong to which country;
* treat `tile_weights` as the sole authority on per-tile prior mass under the chosen basis (e.g. area, population);
* NOT manipulate tile membership rules or recompute tile weights except as explicitly allowed (e.g. normalising weights or projecting them into S2-specific edge budgets).

3.4.4 S2 MAY consume **HRSL/population rasters** and **world-country polygons** for:

* validating that tile surfaces are consistent (optional checks), and/or
* jittering within tiles or constructing finer-grained edge placements.

In doing so, S2 MUST:

* respect their schemas and ownership (typically ingress / 1B);
* treat them as read-only;
* not redefine country boundaries, CRS, or semantics of “support” beyond what is encoded in their owning specs.

3.4.5 If S2 defines any 3B-specific derived spatial surfaces (e.g. per-merchant tiled edge plans or pre-computed jitter grids), those MUST:

* be declared as 3B datasets in `dataset_dictionary.layer1.3B.yaml` / `artefact_registry_3B.yaml`;
* be clearly marked as **S2 outputs** or **intermediate surfaces**, not as input authorities;
* not replace or override 1B’s definitions of `tile_index`, `tile_weights`, or country polygons.

---

3.5 **Timezone inputs & tz-semantics**

3.5.1 S2 MUST use the tz assets sealed in `sealed_inputs_3B` (and owned primarily by 2A) for computing `tzid_operational` for each edge node, specifically:

* tz-world polygons (pinning the tzid geometry);
* tzdb archive / release (pinning the chronology and offsets);
* any tz override packs (if used) that adjust tz assignment for known exceptions.

3.5.2 2A remains the **authority** on tz semantics: meaning of tzids, offset rules, DST gaps/folds, and the canonical mapping from coordinates to tzids. S2 MUST:

* reuse 2A’s mapping logic (e.g. 2A.S1’s point-in-polygon + ε-nudge pattern and override precedence), or a documented compatible variant;
* not introduce a divergent interpretation of tzids (e.g. non-IANA identifiers or ad-hoc tz names).

3.5.3 If `edge_catalogue_3B` includes `tzid_operational`:

* S2 MUST ensure that each `tzid_operational` is either:

  * derived from tz-world/tzdb + overrides using 2A-compatible logic, or
  * ingested from a trusted upstream artefact validated against tz-world/tzdb;
* S2 MUST record tz provenance via a closed enum (e.g. `tz_source ∈ {"POLYGON","OVERRIDE","INGESTED"}`) and MUST NOT infer tzids from non-authoritative sources.

---

3.6 **RNG & routing-policy inputs**

3.6.1 S2 MUST adhere to the layer-wide RNG contract defined in `schemas.layer1.yaml` and the 3B/route RNG policy artefact sealed in `sealed_inputs_3B`. Together, these define:

* the RNG algorithm (Philox2x64-10) and envelope shape;
* the valid RNG streams and substream labels (e.g. `module="3B.S2"`, `substream_label ∈ {"edge_tile_assign","edge_jitter"}`);
* per-stream budgets (`blocks`, `draws`) for S2’s RNG activities.

3.6.2 S2 MUST treat the RNG policy artefact(s) as the **sole authority** on:

* which streams S2 is allowed to use;
* how many draws per edge placement / jitter event are permitted;
* how to map `{seed, parameter_hash, manifest_fingerprint}` into concrete Philox keys/counters for S2.

3.6.3 S2 MUST NOT:

* invent new RNG streams or substream labels not declared in the policy;
* exceed the configured draw budgets;
* re-use or “borrow” RNG streams reserved for other segments or states.

3.6.4 All RNG events S2 emits for edge placement MUST conform to the layer-wide RNG envelope schema and any S2-specific event payload schemas anchored either in `schemas.layer1.yaml` or `schemas.3B.yaml`. S2 MUST NOT define ad-hoc log formats outside these schemas.

---

3.7 **Authority boundaries summary**

3.7.1 S2 SHALL respect the following **authority boundaries**:

* **JSON-Schema packs** (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.3B.yaml`) are the **only authorities on shapes** of datasets, policies, and RNG events. S2 MUST NOT loosen or override these shape definitions.

* **Dataset dictionaries** (for ingress, 1B, 2A, 3B) are the **only authorities on dataset identities, paths, partition keys, and writer sorts**. S2 MUST NOT hard-code alternative paths or partitioning schemes.

* **Artefact registries** (for ingress, 1B, 2A, 3B) are the **only authorities on artefact ownership, licence class, and logical IDs**. S2 MUST NOT invent unregistered logical IDs or reassign ownership.

* **S1 outputs** (`virtual_classification_3B`, `virtual_settlement_3B`) are the **only authorities** on the virtual merchant set and settlement nodes for 3B.

* **CDN policy artefacts** are the **only authorities** on edge budgets and country mix.

* **Spatial surfaces** (`tile_index`, `tile_weights`, rasters, country polygons) are the **only authorities** on spatial support and priors; S2 uses them but does not redefine them.

* **Tz assets** (tz-world, tzdb, overrides) remain owned by 2A; S2 may use them to derive `tzid_operational` but may not change their semantics.

* **RNG & routing policy** is the **only authority** on permitted RNG usage; S2 must conform to its streams & budgets.

3.7.2 If S2 detects any conflict between:

* what an artefact’s schema/dictionary/registry entry claims, and
* what S2 observes at runtime (e.g. missing fields, mismatched shapes, invalid tzids),

S2 MUST treat this as an **input integrity error** (to be raised under `E3B_S2_*` error codes) and MUST NOT attempt to repair or reinterpret the artefact in a way that changes its meaning.

3.7.3 Any future S2 extension that introduces new inputs (e.g. additional policies, alternate tiling schemes, extra RNG families) MUST:

* be registered in the appropriate dictionary/registry;
* be added to `sealed_inputs_3B` by S0;
* have its semantics defined in its own schema;
* and be reflected in this section’s authority-boundary description.

---

## 4. Outputs (datasets) & identity *(Binding)*

4.1 **Overview of S2 outputs**

4.1.1 For each successful run of S2 at a given `{seed, manifest_fingerprint}`, S2 SHALL emit exactly two **3B-owned datasets**:

* **`edge_catalogue_3B`** — the per-edge **CDN edge universe** for all virtual merchants in `V`, including coordinates, country, operational timezone and weights.
* **`edge_catalogue_index_3B`** — a compact **index / digest surface** summarising the edge universe (e.g. per-merchant edge counts and digests, and a global edge universe digest) to be used by S3 and the validation harness.

4.1.2 In addition, S2 WILL contribute RNG evidence to the **layer-wide RNG logs**:

* `rng_audit_log` and `rng_trace_log` (as defined in `schemas.layer1.yaml`),
* and one or more S2-specific RNG event families (e.g. `edge_tile_assign`, `edge_jitter`) anchored in the layer or 3B schemas.

These RNG logs are **not** 3B-specific datasets; they are shared, layer-owned outputs that S2 writes into. Their existence and partitioning are governed by the layer-wide RNG contracts, not by this section.

4.1.3 S2 MUST NOT emit any additional persisted datasets beyond:

* `edge_catalogue_3B`,
* `edge_catalogue_index_3B`,
* and any explicitly specified diagnostic / run-summary surfaces described elsewhere in the S2 spec.

Any further outputs MUST be explicitly added to the 3B contracts and to this section.

---

4.2 **Primary egress: `edge_catalogue_3B` (edge universe)**

4.2.1 `edge_catalogue_3B` SHALL be the **authoritative edge-node dataset** for virtual merchants in 3B. Each row represents one CDN edge node associated with exactly one virtual merchant.

4.2.2 At minimum, each row in `edge_catalogue_3B` MUST contain:

* **Identity & keys**

  * `merchant_id` (or `merchant_key` if a composite key is adopted in 3B):

    * key tying the edge back to S1’s `virtual_classification_3B` and `virtual_settlement_3B`,
    * MUST be consistent with S1’s key choice.
  * `edge_id`:

    * deterministic identifier for the edge node,
    * unique within `{seed, manifest_fingerprint}` and per `merchant_id`,
    * constructed via a documented, RNG-free function (e.g. hash of `(merchant_id, country_iso, edge_index)`).

* **Geography**

  * `country_iso`

    * ISO country code representing the **country attribution** of this edge,
    * MUST be consistent with the country-level weights policy and spatial surfaces used for placement.
  * `edge_latitude_deg`, `edge_longitude_deg`

    * WGS84 coordinates in degrees for the edge node,
    * derived from tile/jitter logic and validated to lie inside the intended country polygon.

* **Operational time**

  * `tzid_operational`

    * IANA timezone for the edge’s **operational** location (where the customer appears to be),
    * MUST conform to `schemas.layer1.yaml#/time/iana_tzid`.
  * `tz_source`

    * enum describing how `tzid_operational` was obtained (`"POLYGON"`, `"OVERRIDE"`, `"INGESTED"`, etc.),
    * closed vocabulary declared in `schemas.3B.yaml`.

* **Weights and provenance**

  * `edge_weight`

    * non-negative scalar weight used to construct alias tables and to reflect relative importance/traffic share of this edge within the merchant’s edge set,
    * semantics and normalisation rules MUST be defined in §6 and §5 (e.g. per-merchant weights sum to 1.0 or to a fixed integer grid).
  * `cdn_policy_id`, `cdn_policy_version`

    * logical ID and version of the `cdn_country_weights` / edge-budget policy used.
  * `spatial_surface_id`

    * logical ID of the tile / spatial surface used (e.g. 1B tile surface vs 3B-specific surface).

4.2.3 The rowset of `edge_catalogue_3B` for the `{seed, manifest_fingerprint}` partition MUST satisfy:

* Let `V = {m | S1 classifies m as virtual}`. Then:

  * every edge row’s `merchant_id` is in `V`;
  * no rows exist for merchants not in `V`, unless explicitly allowed by a future extension (which MUST be documented and versioned).
* For each `m ∈ V`:

  * the number of edges `|E_m|` is finite, non-negative, and consistent with the edge-budget policy (min/max and total budget constraints);
  * the sum of `edge_weight` over `E_m` follows the policy’s declared law (e.g. normalised to 1, or integer grid with fixed sum).

4.2.4 Partitioning and path:

* `edge_catalogue_3B` MUST be partitioned by:

  * `seed={seed}`
  * `fingerprint={manifest_fingerprint}`
* The normative path pattern SHALL be defined in `dataset_dictionary.layer1.3B.yaml`, e.g.:
  `data/layer1/3B/edge_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/…`
* `writer_sort` MUST be defined in the dictionary and respected by S2. A recommended law is:

  * `writer_sort: ["merchant_id","edge_id"]` (or composite merchant key first, then `edge_id`).

---

4.3 **Index / digest egress: `edge_catalogue_index_3B`**

4.3.1 `edge_catalogue_index_3B` SHALL provide a **compact summary and digest** of `edge_catalogue_3B` for the same `{seed, manifest_fingerprint}`. Its primary roles are:

* to give 3B.S3 and validation harnesses a stable, small surface from which to compute a **virtual-edge universe hash**;
* to provide per-merchant and global counts for monitoring and sanity checks (e.g. average edges per merchant, country coverage).

4.3.2 At minimum, `edge_catalogue_index_3B` MUST include:

* **Per-merchant rows** (if the design is per-merchant indexed), containing:

  * `merchant_id` (or merchant key),
  * `edge_count_total` (number of edges for this merchant),
  * optional `edge_count_by_country` (map or structured fields per country),
  * `edge_catalogue_digest_merchant` — deterministic digest (e.g. SHA-256) of all edge rows for this merchant, computed using a documented ordering (e.g. sorted by `edge_id`).

* **Global summary row(s)** (e.g. one row per `{seed, fingerprint}`), containing:

  * `edge_count_total_all_merchants`,
  * `edge_count_by_country_overall`,
  * `edge_catalogue_digest_global` — deterministic digest of the entire `edge_catalogue_3B` partition,
  * optional fields needed to compute or cross-check a combined **virtual edge universe hash** used later with `zone_alloc_universe_hash` and 2B.

4.3.3 `edge_catalogue_index_3B` MUST be declared in `dataset_dictionary.layer1.3B.yaml` with:

* `id: edge_catalogue_index_3B`;
* `owner_subsegment: 3B`;
* `schema_ref: schemas.3B.yaml#/plan/edge_catalogue_index_3B`;
* `path: data/layer1/3B/edge_catalogue_index/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`;
* `partitioning: [seed, fingerprint]`;
* `ordering` reflecting the key structure (e.g. `["scope","merchant_id"]`, as defined in the schema).

4.3.4 Downstream obligations:

* S3 MUST treat `edge_catalogue_index_3B` as the canonical source of per-merchant and global digests for edge-universe hashing; it SHOULD NOT re-scan `edge_catalogue_3B` at large scale except for validation or sampling.
* Any validation or observability tooling MUST rely on the documented digest combination law when recomputing or checking universe hashes, not on ad-hoc recomputation.

---

4.4 **Identity & partitioning for S2 outputs**

4.4.1 Both `edge_catalogue_3B` and `edge_catalogue_index_3B` are **run-scoped** datasets. Their identity is determined by:

* the `{seed, fingerprint}` partition declared in the dictionary (the `fingerprint` token equals the run’s `manifest_fingerprint`);
* the fact that they are produced by 3B.S2 for that run under the 3B contracts version in effect.

4.4.2 On disk, identity SHALL be expressed via:

* `seed={seed}` and `fingerprint={manifest_fingerprint}` in the directory path (exactly as declared in the dictionary);
* a single set of files per `{seed, fingerprint}` for each dataset.

4.4.3 The schemas for these datasets MAY include explicit columns:

* `seed`
* `manifest_fingerprint`
* `parameter_hash`

as identity echoes. If present, S2 MUST:

* write these columns such that they exactly match the run identity and S0 receipt;
* rely on the 3B validation state (not S2) to perform path↔embed equality checks as part of segment-level validation.

4.4.4 No S2 output MAY include `parameter_hash` or `run_id` as a **partition key**. They may appear only as columns if needed, and MUST NOT affect dataset path or partition layout.

---

4.5 **RNG events & logs (shared, not S2-owned datasets)**

4.5.1 As an RNG-bearing state, S2 SHALL emit RNG events for any random edge-placement activities (e.g. tile selection permutations, jitter in tiles) in accordance with:

* the layer-wide RNG envelope schema in `schemas.layer1.yaml`;
* the 3B/route RNG policy pack sealed in `sealed_inputs_3B`.

4.5.2 RNG events produced by S2 MUST be recorded in:

* `rng_audit_log` and `rng_trace_log` datasets shared at the Layer-1 level (as already defined for 1A/1B/2B), and/or
* any S2-specific event streams declared in `schemas.layer1.yaml` or `schemas.3B.yaml` (e.g. `rng_event_edge_tile_assign`, `rng_event_edge_jitter`).

4.5.3 These RNG logs are **authoritatively owned** by the layer-wide RNG contract, not by 3B.S2. S2’s obligations here are:

* to write events that are schema-conformant, with correct identity (`segment_id`, `state_id`, `rng_stream_id`, counters, blocks/draws);
* to ensure that event counts and trace totals align with S2’s internal edge-placement logic and budgets;
* to enable downstream validation to reconcile RNG usage with the number of edges placed.

4.5.4 RNG logs MUST NOT be treated as S2-specific egress datasets in the 3B dictionary. They are cross-cutting Layer-1 artefacts that other segments (including S2) write to and read from under the layer’s RNG governance.

---

4.6 **Downstream consumption & authority**

4.6.1 Within 3B, S2 outputs SHALL be consumed as follows:

* **3B.S3 (edge alias & universe hash)**

  * MUST treat `edge_catalogue_3B` as the **sole source** of edge nodes for virtual merchants;
  * MUST use `edge_catalogue_index_3B` for digests and counts when constructing alias tables and universe hashes;
  * MUST NOT re-run edge placement logic itself.

* **3B validation state (segment-level)**

  * MUST validate S2 outputs against their schemas and invariants (identity, counts, digests, RNG accounting) as part of 3B’s PASS criteria;
  * MUST include `edge_catalogue_3B` and `edge_catalogue_index_3B` in the 3B validation bundle index.

4.6.2 Within 2B and other segments:

* Any 2B virtual routing logic that needs edge nodes MUST do so **indirectly via S3** (alias/universe surfaces) and MUST NOT attempt to rebuild edges from policies if S2 is present;
* If 2B or a higher layer needs to inspect edge placement details (e.g. for debugging), it MAY read `edge_catalogue_3B` directly, but MUST respect its contracts (no mutation, no inference of new edges).

4.6.3 No other state MAY mutate `edge_catalogue_3B` or `edge_catalogue_index_3B` in place. Any additional per-state annotations (e.g. coverage flags, validation metrics) MUST be written to separate datasets keyed to S2’s outputs via their primary keys.

---

4.7 **Immutability & idempotence**

4.7.1 For a fixed `{seed, parameter_hash, manifest_fingerprint}`, S2 outputs (`edge_catalogue_3B`, `edge_catalogue_index_3B`) are **logically immutable**:

* Once S2 has successfully written these datasets, any subsequent run of S2 for the same identity triple MUST:

  * either recompute the outputs and confirm that they are bit-identical to the existing datasets (idempotent no-op), or
  * detect a conflict due to environment drift and fail, without overwriting, according to the error rules in §9.

4.7.2 S2 MUST write both datasets using an **atomic publish** protocol per `{seed, fingerprint}`:

* S2 MUST NOT expose a state where one of the two datasets has been updated but the other has not;
* if publishing fails for either dataset, both MUST be considered invalid and S2 MUST report a failure.

4.7.3 Downstream states and validation MUST treat any partial or mismatched presence of S2 outputs (e.g. `edge_catalogue_3B` exists but `edge_catalogue_index_3B` does not) as a **3B.S2 failure**, not as a valid output state.

4.7.4 Any implementation that:

* changes partition law,
* rewrites S2 outputs in place without idempotence checks, or
* relies on mutable edge catalogues during a run,

is non-conformant with this specification and MUST be corrected or versioned appropriately under the change-control rules in §12.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

5.1 **`edge_catalogue_3B` — dataset contract**

5.1.1 The dataset **`edge_catalogue_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with, at minimum:

* `id: edge_catalogue_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/plan/edge_catalogue_3B`
* `path: data/layer1/3B/edge_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
* `partitioning: [seed, fingerprint]`
* `ordering: ["merchant_id","edge_id"]`
  (or `["merchant_key","edge_id"]` if a composite merchant key is adopted across 3B; in that case the spec MUST be explicit).

5.1.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* set `name: edge_catalogue_3B` (matching the dictionary `id`);
* reuse the same `path` tokens and schema anchor (`schemas.3B.yaml#/plan/edge_catalogue_3B`);
* declare `type: dataset`, an appropriate `category` (e.g. `virtual_edges`), and supply the standard registry metadata (`semver`, `version`, `owner`, `environment`);
* provide a stable `manifest_key` such as `"mlr.3B.edge_catalogue_3B"`;
* list known consumers (at least `3B.S3`, the 3B validation state, and any routing components that read edges directly);
* specify a retention / cross-layer posture consistent with other Layer-1 datasets of similar sensitivity.

5.1.3 `schemas.3B.yaml#/plan/edge_catalogue_3B` MUST define `edge_catalogue_3B` as a table-shaped dataset with one row per edge node. Required columns:

* **Identity & keys**

  * `merchant_id` (or `merchant_key`)

    * type: as per S1 (`virtual_classification_3B` / `virtual_settlement_3B`);
    * semantics: ties edge back to S1 and upstream merchant universe;
    * MUST be non-null.

  * `edge_id`

    * type: e.g. `hex64` / `id64` (referencing `schemas.layer1.yaml#/id/id64` or equivalent);
    * semantics: deterministic, unique identifier within `{seed,fingerprint}`;
    * MUST be non-null and unique for each `(merchant_id, edge_id)` pair.

* **Geography**

  * `country_iso`

    * type: ISO 3166-1 alpha-2 or alpha-3 code, referencing the layer ingress schema (e.g. `schemas.ingress.layer1.yaml#/geo/country_iso`);
    * semantics: edge’s attribution country for CDN / geography;
    * MUST be non-null and belong to the canonical country set.

  * `edge_latitude_deg`

    * type: numeric, WGS84 latitude in degrees;
    * MUST satisfy `-90.0 ≤ edge_latitude_deg ≤ 90.0`.

  * `edge_longitude_deg`

    * type: numeric, WGS84 longitude in degrees;
    * MUST lie within the declared longitude range (e.g. `(-180.0, 180.0]` or `[−180.0,180.0]` as defined in the schema).

* **Operational time**

  * `tzid_operational`

    * type: string, `schemas.layer1.yaml#/time/iana_tzid`;
    * semantics: operational timezone at the edge node;
    * MUST be non-null.

  * `tz_source`

    * type: enum; examples (non-exhaustive but MUST be closed in the schema):

      * `"POLYGON"` — derived from tz-world polygons + tzdb;
      * `"OVERRIDE"` — derived via explicit override;
      * `"INGESTED"` — taken from a trusted upstream artefact.
    * MUST be non-null and one of the enumerated values.

* **Weights & policy provenance**

  * `edge_weight`

    * type: numeric (with explicit bounds and precision in schema);
    * semantics: relative weight for alias-table construction / apparent traffic mix;
    * MUST be ≥ 0; further normalisation rules are specified in §6 and MUST be encoded in the 3B validation state.

  * `cdn_policy_id` / `cdn_policy_version`

    * type: string;
    * MUST match the logical ID and version of the `cdn_country_weights` (or equivalent) policy sealed in `sealed_inputs_3B`.

  * `spatial_surface_id`

    * type: string;
    * identifies which spatial surface was used to place the edge (e.g. `"1B.tiles.v1"` vs `"3B.virtual_tiles.v1"`).

5.1.4 Optional, but recommended columns (MUST be schema-optional and non-semantic for core behaviour):

* `tile_id` — the originating tile or cell index, if useful for debugging / validation;
* `coord_source_id` / `coord_source_version` — identify underlying raster/polygon artefacts;
* `created_utc` — RFC3339 timestamp of S2 output creation (informative);
* `seed`, `manifest_fingerprint`, `parameter_hash` — identity echoes (MUST match path and S0 receipt if present).

5.1.5 Structural constraints for acceptance (enforced either via schema or via S2/validation logic):

* `(merchant_id, edge_id)` MUST be unique within `{seed,fingerprint}`;
* `country_iso`, `edge_latitude_deg`, `edge_longitude_deg`, `tzid_operational`, and `edge_weight` MUST be non-null;
* `edge_weight` MUST satisfy any declared normalisation (e.g. per-merchant weights summing to 1.0 within tolerance or to a fixed integer grid);
* `tzid_operational` MUST be valid according to tz assets sealed in `sealed_inputs_3B`.

---

5.2 **`edge_catalogue_index_3B` — dataset contract**

5.2.1 The dataset **`edge_catalogue_index_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with at least:

* `id: edge_catalogue_index_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/plan/edge_catalogue_index_3B`
* `path: data/layer1/3B/edge_catalogue_index/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
* `partitioning: [seed, fingerprint]`
* `ordering`:

  * typically `["merchant_id"]` for per-merchant rows;
  * global summary rows may be keyed by a dedicated label (e.g. `merchant_id = "__GLOBAL__"`), as defined in the schema.

5.2.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* set `name: edge_catalogue_index_3B` and reuse the same schema anchor / path tokens as the dictionary entry;
* declare `type: dataset`, include the usual registry metadata (`category`, `semver`, `version`, `owner`, `environment`);
* provide a stable `manifest_key` (e.g. `"mlr.3B.edge_catalogue_index_3B"`);
* list `3B.S3`, the 3B validation state, and any routing or observability tooling as primary consumers.

5.2.3 `schemas.3B.yaml#/plan/edge_catalogue_index_3B` MUST define an index structure with at least two possible row types (distinguished by a field or by separate collections):

* **Per-merchant index rows** (keyed by `merchant_id` / `merchant_key`):

  * `merchant_id` — consistent key with `edge_catalogue_3B`;
  * `edge_count_total` — total number of edges for this merchant;
  * optional `edge_count_by_country` — structured object or fixed columns encoding counts per `country_iso` bucket;
  * `edge_catalogue_digest_merchant` — digest (e.g. hex SHA-256) of all edge rows in `edge_catalogue_3B` for this merchant, computed over a canonical ordering (e.g. by `edge_id` ascending).

* **Global summary row** (or rows):

  * a dedicated key indicating global scope (e.g. `scope = "GLOBAL"` or `merchant_id = "__GLOBAL__"`);
  * `edge_count_total_all_merchants`;
  * `edge_count_by_country_overall`;
  * `edge_catalogue_digest_global` — digest of the entire edge catalogue partition;
  * optional fields needed for universe-hash construction later (e.g. digests of `cdn_country_weights`, spatial surfaces, etc., if S2 is responsible for computing or echoing them).

5.2.4 Structural constraints:

* For each merchant `m ∈ V` with at least one edge, there MUST be exactly one per-merchant index row;
* `edge_count_total` per merchant MUST equal the number of `edge_catalogue_3B` rows with that `merchant_id`;
* `edge_count_total_all_merchants` MUST equal the total row count of `edge_catalogue_3B` for the partition;
* digest fields MUST be consistent with the canonical digest laws defined in the S2/S3/validation specs.

---

5.3 **RNG event shapes & anchors (informative for datasets, binding for schemas)**

5.3.1 While RNG logs are not 3B-owned datasets, any S2-specific RNG event families (e.g. `rng_event_edge_tile_assign`, `rng_event_edge_jitter`) MUST be defined in:

* `schemas.layer1.yaml#/rng/events/...` or
* `schemas.3B.yaml#/rng/events/...` (if the layer-wide schema is designed to delegate to segment-level defs),

and referenced by `schema_ref` in the relevant catalogues or internal config.

5.3.2 If S2 introduces such events, their schemas MUST:

* extend or embed the layer-wide RNG envelope (`rng_envelope`);
* define payload fields sufficient to correlate events with `edge_catalogue_3B` rows (e.g. `merchant_id`, `country_iso`, `tile_id`, `edge_seq_index`);
* be used consistently in RNG audit/trace logs.

5.3.3 S2 MUST NOT define ad-hoc RNG event structures outside the declared schemas. This is primarily a **schema** concern; RNG logs remain governed by the layer RNG contracts.

---

5.4 **Input anchors & cross-segment links**

5.4.1 All S1 and upstream inputs S2 reads MUST be anchored to existing schemas. For example:

* `virtual_classification_3B` — `schemas.3B.yaml#/plan/virtual_classification_3B`;
* `virtual_settlement_3B` — `schemas.3B.yaml#/plan/virtual_settlement_3B`;
* `tile_index` / `tile_weights` — schemas in `schemas.1B.yaml` (e.g. `#/internal/tile_index`, `#/internal/tile_weights`);
* `cdn_country_weights` — `schemas.3B.yaml#/policy/cdn_country_weights` (or equivalent);
* tz-world / tzdb artefacts — anchors in `schemas.ingress.layer1.yaml` and/or `schemas.2A.yaml`.

5.4.2 `dataset_dictionary.layer1.3B.yaml` MUST list S1 outputs and any reused 1B/2A datasets as **inputs** to S2, with `schema_ref` pointing to their owning segment’s schema packs. S2 MUST rely on those anchors for validation and not on separate ad-hoc shape assumptions.

5.4.3 If 3B defines its own tiling or spatial surfaces, those MUST:

* have schemas under `schemas.3B.yaml#/spatial/...`;
* have entries in `dataset_dictionary.layer1.3B.yaml` with correct `schema_ref`, `path_template`, `partition_keys` and `writer_sort`;
* be clearly distinguished from 1B surfaces to avoid ambiguous authority.

---

5.5 **Keys, sort order & join discipline**

5.5.1 Keys and joins:

* `edge_catalogue_3B` primary key: `(merchant_id, edge_id)` (or `(merchant_key, edge_id)`);
* natural join from `edge_catalogue_3B` to S1 outputs: join key = `merchant_id`/`merchant_key`;
* natural join from `edge_catalogue_index_3B` to `edge_catalogue_3B`: join key = `merchant_id` and, when necessary, `seed`/`fingerprint`.

5.5.2 Writer sort:

* `edge_catalogue_3B.writer_sort` MUST follow the key order (e.g. `["merchant_id","edge_id"]`);
* `edge_catalogue_index_3B.writer_sort` MUST reflect its primary keys (e.g. `["merchant_id"]` plus any scope indicator), so that the digest computation order is well-defined.

5.5.3 S2 MUST:

* sort its in-memory edge rows by these keys before writing;
* ensure that any digest computations that depend on ordering are based on these sort orders;
* avoid relying on incidental file or partition ordering for either algorithmic behaviour or digest construction.

5.5.4 Downstream 3B states (S3, validation) and any other consumers MUST use these keys and sort declarations when:

* joining edge datasets to S1 outputs or to each other;
* streaming through edges in a reproducible order;
* recomputing or verifying digests.

---

5.6 **Binding vs informative elements**

5.6.1 The following aspects of this section are **binding**:

* Existence and names of `edge_catalogue_3B` and `edge_catalogue_index_3B`;
* Their `schema_ref`, `path_template`, `partition_keys`, and `writer_sort` entries in the dataset dictionary;
* Required columns and structural constraints described in §§5.1–5.2;
* The requirement that these datasets be discoverable and addressable via the 3B dictionary/registry, not via hard-coded paths.

5.6.2 Optional columns and global summary/diagnostics are binding only in the sense that, if they are defined in schemas, S2 MUST populate them in a way consistent with their semantics. However, their presence or absence MUST NOT alter:

* the semantics of required fields, or
* the invariants used by downstream states to interpret edge catalogues.

5.6.3 If any discrepancy arises between this section and:

* the actual `schemas.3B.yaml` definitions;
* `dataset_dictionary.layer1.3B.yaml`;
* `artefact_registry_3B.yaml`,

then the schemas and dictionary/registry SHALL be treated as authoritative. This section MUST be updated in the next non-editorial revision to reflect the contracts actually in force.

---

## 6. Deterministic algorithm (with RNG) *(Binding)*

6.1 **Phase overview**

6.1.1 S2 SHALL implement a **single deterministic algorithm**, with clearly separated RNG-free and RNG-bearing phases:

* **Phase A — Environment & input load (RNG-free)**
  Load S0 + S1 outputs, sealed inputs, contracts and policies; construct the virtual merchant set `V` and verify basic invariants.

* **Phase B — Edge-budget computation per merchant & country (RNG-free)**
  Use CDN policy to compute per-merchant total edge budgets and per-merchant, per-country fractional edge targets; integerise these into country-level edge counts.

* **Phase C — Tile-level edge allocation (RNG-free)**
  For each `(merchant, country)`, allocate its country-level edge counts across tiles using 1B/3B tile surfaces and deterministic integerisation.

* **Phase D — Edge placement within tiles (RNG-bearing)**
  For each tile allocation, use Philox RNG to jitter edge coordinates within the tile, enforcing that each edge lies inside the intended country polygon; record RNG events.

* **Phase E — Operational timezone resolution (RNG-free)**
  From edge coordinates, derive `tzid_operational` using tz-world / tzdb / overrides in a 2A-compatible way.

* **Phase F — Edge identity construction & output assembly (RNG-free)**
  Construct `edge_id`, compute `edge_weight` and policy provenance, and materialise `edge_catalogue_3B` and `edge_catalogue_index_3B` in canonical order.

6.1.2 All non-trivial decisions in Phases B, C, E and F MUST be **RNG-free** and pure functions of:

* `{seed, parameter_hash, manifest_fingerprint}`,
* S0’s sealed inputs,
* S1 outputs, and
* the CDN/spatial/tz/RNG policy artefacts.

6.1.3 All RNG usage MUST be **explicitly confined** to Phase D, and:

* use only the streams, substream labels and budgets authorised for S2 in the RNG policy;
* emit fully-specified RNG events conforming to the layer-wide RNG envelope.

---

6.2 **Phase A — Environment & input load (RNG-free)**

6.2.1 S2 MUST perform the precondition checks described in §§2–3 (S0 gate, S1 outputs, sealed artefacts, contracts). Implementation MAY reuse shared utilities but MUST enforce all binding constraints.

6.2.2 After Phase A, S2 MUST have in memory:

* `V` — the set of virtual merchants derived from `virtual_classification_3B`;
* `virtual_settlement_3B` rows for all `m ∈ V`;
* the CDN policy structures (country weights, merchant classes, optional overrides);
* pointers / accessors to spatial surfaces (tiles & weights), tz assets and RNG policy;
* any configuration flags that affect algorithm choices (edge budgets, shared tile mode, etc.).

6.2.3 If `V = ∅` and virtual edges are disabled by configuration, S2 MAY take an early-exit path per §8/§11 (e.g. write empty outputs). Otherwise, S2 MUST proceed through the remaining phases.

---

6.3 **Phase B — Edge-budget computation per merchant & country (RNG-free)**

6.3.1 S2 MUST load and parse the **CDN edge-budget policy** (e.g. `cdn_country_weights`) into an internal representation that, at minimum, defines:

* a global country mix vector
  `w_global(c)` over countries `c ∈ C`, with:

  * `w_global(c) ≥ 0`,
  * Σ₍c∈C₎ `w_global(c) > 0`, and
  * Σ₍c∈C₎ `w_global(c)` normalised (e.g. to 1.0 or an integer grid);

* a per-merchant class mapping, if used:

  * function `class(m) ∈ CLASSES` (e.g. SMALL/MEDIUM/LARGE), derived deterministically from merchant attributes or allow/deny lists;

* per-class budget parameters:

  * `E_total(class)` — nominal total edges per merchant in that class;
  * `min_edges_per_merchant`, `max_edges_per_merchant`;
  * optional per-country floors/caps.

6.3.2 For each virtual merchant `m ∈ V` S2 MUST:

1. Determine `class(m)` using a deterministic, policy-defined rule.
2. Compute a nominal total edge budget `E_nominal(m) = E_total(class(m))`.
3. Apply any per-merchant overrides (if present in the policy), using a documented precedence:

   * merchant-level override ≻ class-level ≻ global default.
4. Apply min/max clipping:

   * `E_clipped(m) = clamp(E_nominal(m), min_edges_per_merchant, max_edges_per_merchant)`.

`E_clipped(m)` MUST be an integer or be deterministically integerised (e.g. via rounding, with a fixed rule).

6.3.3 Per-merchant, per-country fractional targets:

6.3.3.1 S2 MUST define, for each virtual merchant `m` and country `c`:

* a **country weight** `w_m(c)` used for that merchant. By default, `w_m(c) = w_global(c)`; the policy MAY allow per-class or per-merchant overrides:

  * `w_m(c) = w_class(class(m), c)` if defined, else
  * `w_m(c) = w_global(c)`.

All such variants MUST be documented and deterministic.

6.3.3.2 S2 MUST normalise `w_m(c)` over countries `c` that are allowed by policy for this merchant:

* define `C_m = { c | w_m(c) > 0 and c is allowed for merchant m }`;
* compute `Z_m = Σ₍c∈C_m₎ w_m(c)`;
* require `Z_m > 0` (else treat as configuration error);
* define normalised shares `s_m(c) = w_m(c) / Z_m` for `c ∈ C_m`.

6.3.4 Per-merchant, per-country integer edge counts:

6.3.4.1 For each `m ∈ V`, S2 MUST compute real-valued targets:

* `T_m(c) = E_clipped(m) * s_m(c)` for each `c ∈ C_m`.

6.3.4.2 S2 MUST integerise `T_m(c)` into `E_m(c) ∈ ℕ` using a deterministic largest-remainder scheme:

1. Compute base counts `b_m(c) = floor(T_m(c))`.

2. Compute residual capacity `R_m = E_clipped(m) − Σ₍c∈C_m₎ b_m(c)`.

3. For each `c ∈ C_m`, compute fractional residual `r_m(c) = T_m(c) − b_m(c)`.

4. Rank countries in descending `r_m(c)`, with deterministic tie-break:

   * larger `r_m(c)` first;
   * ties broken by lexicographic `country_iso`;
   * if still tied, by a stable secondary key (e.g. ASCII-lex of `(country_iso, merchant_id)`).

5. Assign +1 to the top `R_m` countries in this ranking:
   `E_m(c) = b_m(c) + [c among top R_m]`.

6.3.4.3 S2 MUST ensure:

* Σ₍c∈C_m₎ `E_m(c) = E_clipped(m)` for each `m ∈ V`;
* `E_m(c) ≥ 0` for all `c ∈ C_m`;
* any policy-defined per-country floors/caps are respected (e.g. if the policy requires a minimum of 1 edge in certain countries, S2 MUST ensure `E_m(c) ≥ floor_policy(c)` for those countries, adjusting E_clipped or redistributing edges deterministically as needed).

---

6.4 **Phase C — Tile-level edge allocation (RNG-free)**

6.4.1 For each country `c`, S2 MUST obtain a **tiling surface**:

* either `tile_index` and `tile_weights` from 1B under `schema_ref` in `schemas.1B.yaml`, or
* 3B-specific tiling datasets registered in `schemas.3B.yaml`.

6.4.2 For a given `(merchant m, country c)` with `E_m(c) > 0`, S2 MUST:

1. Enumerate the set of tiles `T_c = { t | tile_index(c, t) exists and is eligible for edge placement }`.
2. Associate each tile `t ∈ T_c` with a **tile weight** `w_tile(c,t)` from `tile_weights` (or similar).
3. Normalise tile weights over `T_c`:

   * require `Σ₍t∈T_c₎ w_tile(c,t) > 0`, else treat as configuration error;
   * define `p_tile(c,t) = w_tile(c,t) / Σ₍t∈T_c₎ w_tile(c,t)`.

6.4.3 Tile-level integer edge counts:

6.4.3.1 S2 MUST compute continuous targets:

* `U_m(c,t) = E_m(c) * p_tile(c,t)` for each tile `t ∈ T_c`.

6.4.3.2 S2 MUST integerise `U_m(c,t)` into `E_m(c,t) ∈ ℕ` via a deterministic procedure similar to §6.3:

1. `b_m(c,t) = floor(U_m(c,t))`.

2. `R_m(c) = E_m(c) − Σ₍t∈T_c₎ b_m(c,t)`.

3. `r_m(c,t) = U_m(c,t) − b_m(c,t)` for each tile.

4. Rank tiles by:

   * descending `r_m(c,t)`;
   * then ascending `tile_id`;
   * then (if required) by `(country_iso, merchant_id)` as a stable tertiary tie-break.

5. Assign +1 to the top `R_m(c)` tiles in this ranking:
   `E_m(c,t) = b_m(c,t) + [t among top R_m(c)]`.

6.4.3.3 S2 MUST enforce:

* Σ₍t∈T_c₎ `E_m(c,t) = E_m(c)` for each `(m,c)`;
* `E_m(c,t) ≥ 0` for all tiles;
* no edges assigned to tiles not in `T_c`.

6.4.4 S2 MAY materialise an intermediate, RNG-free planning dataset (e.g. `edge_tile_plan_3B`) with rows `(merchant_id, country_iso, tile_id, edge_count_tile = E_m(c,t))`, but such a dataset MUST be declared in the 3B dictionary/registry if persisted. Otherwise it MUST remain an internal structure.

---

6.5 **Phase D — Edge placement within tiles (RNG-bearing)**

6.5.1 For each `(merchant m, country c, tile t)` with `E_m(c,t) > 0`, S2 MUST place `E_m(c,t)` edge nodes inside the geometry of tile `t` using Philox RNG under the 3B RNG policy.

6.5.2 RNG stream selection:

6.5.2.1 S2 MUST use one or more dedicated RNG streams specified in the RNG policy, e.g.:

* `module = "3B.S2"`;
* `substream_label = "edge_jitter"`.

A separate substream (e.g. `edge_tile_assign`) MAY be used if S2 performs additional random permutations, but all such streams MUST be declared in the RNG policy.

6.5.2.2 The mapping from logical identifiers to `rng_stream_id` MUST be deterministic and documented, typically as a function of:

* `seed`,
* `manifest_fingerprint`,
* S2’s module name and substream label, and
* (when needed) a merchant- or tile-level index.

6.5.3 Jitter within tiles:

6.5.3.1 For each edge slot `k ∈ {1,…,E_m(c,t)}`, S2 MUST:

1. Use two independent `u ∈ (0,1)` variates from the chosen Philox stream for that tile (or from a per-edge offset within the stream), producing `u_lon` and `u_lat`.

2. Compute a candidate point within the tile bounds:

   * For a rectangular tile defined in lon/lat:

     * `lon_candidate = lon_min(t) + u_lon * (lon_max(t) − lon_min(t))`
     * `lat_candidate = lat_min(t) + u_lat * (lat_max(t) − lat_min(t))`.

   * For more complex tile geometries, the mapping MUST be defined in 3B’s spatial spec (e.g. using rejection sampling within the polygon at the tile level).

3. Check:

   * that `(lon_candidate, lat_candidate)` lies within tile `t` according to the tile geometry;
   * that the point lies within the intended country polygon `country_iso = c` as defined in the sealed world-country polygons.

4. If both checks pass, accept this coordinate for the edge;

5. If either check fails, treat as a jitter resample and retry up to a bounded maximum `JITTER_MAX_ATTEMPTS` (policy-specified, e.g. 64).

6.5.3.2 S2 MUST record each jitter attempt as a RNG event (e.g. `rng_event_edge_jitter`) with:

* a valid RNG envelope (stream id, pre/post counters, blocks/draws);
* `draws` field correctly reflecting the **actual** number of Philox draws for that event (typically `"2"` for two uniforms, `"0"` for an event that logs a failure without drawing);
* sufficient payload to attribute the event to `(merchant_id, country_iso, tile_id, edge_seq_index)`.

6.5.3.3 If `JITTER_MAX_ATTEMPTS` is reached without finding a valid point:

* S2 MUST fail with a FATAL spatial/jitter error (see §9);
* S2 MUST NOT “force” an invalid coordinate into the country polygon.

6.5.4 RNG determinism and budgets:

6.5.4.1 S2 MUST ensure that:

* every edge slot uses a predictable, reproducible sequence of draws given `{seed, parameter_hash, manifest_fingerprint}` and the RNG policy;
* the total number of RNG events and draws is:

  * exactly `E_total_edges * draws_per_edge` (plus any resamples, bounded and accounted for);
  * within the budget declared in the RNG policy for S2’s streams.

6.5.4.2 After S2 completes, the RNG trace log MUST be reconcilable with:

* the number of edges placed;
* the number of jitter attempts per edge (actual successes plus resamples).

---

6.6 **Phase E — Operational timezone resolution (RNG-free)**

6.6.1 Once all edge coordinates `(edge_latitude_deg, edge_longitude_deg)` are determined, S2 MUST assign an operational timezone `tzid_operational` for each edge using tz assets sealed in `sealed_inputs_3B`.

6.6.2 If the design chooses to ingest tzids from a trusted upstream artefact (rare for edges):

* S2 MUST validate that provided tzids conform to `iana_tzid`;
* S2 MAY optionally check that the coordinate plausibly lies in that tzid’s polygon;
* S2 MUST set `tz_source = "INGESTED"` for such edges.

6.6.3 If S2 computes `tzid_operational` from tz-world/tzdb:

* it MUST reuse the 2A-style procedure (or a documented variant):

  1. Evaluate point-in-polygon for `(edge_latitude_deg, edge_longitude_deg)` against tz polygons.
  2. If ambiguous or on a boundary, apply a deterministic ε-nudge (using the same or a 3B-specific nudge policy) and re-evaluate.
  3. If a unique tzid is found: set `tzid_operational` and `tz_source = "POLYGON"`.
  4. If multiple tzids remain or none is found, apply any tz overrides (site/merchant/country), with documented precedence (`edge_id` / merchant overrides ≻ country ≻ default).
  5. If an override changes the polygon-derived result, set `tz_source = "OVERRIDE"`.

* If S2 cannot assign any tzid after these steps, it MUST fail with a FATAL tz-resolution error.

6.6.4 S2 MUST NOT invent non-IANA tz identifiers or re-use settlement tz semantics (`tzid_settlement`) as the operational tz unless the specification explicitly says so, in which case the schema and spec MUST record that behaviour.

---

6.7 **Phase F — Edge identity, weight and output assembly (RNG-free)**

6.7.1 Edge identity construction:

6.7.1.1 S2 MUST construct a deterministic `edge_id` for each edge slot. A normative scheme (binding once adopted) is:

* Let `k_bytes = UTF8("3B.EDGE") || 0x1F || UTF8(merchant_id) || 0x1F || LE32(edge_seq_index)`
  where `edge_seq_index` is a 0-based or 1-based integer index of edges for merchant `m`, assigned in deterministic order (e.g. sorted by `(country_iso, tile_id, jitter_rank)`).

* Compute `digest = SHA256(k_bytes)`.

* Define `edge_id_u64 = LOW64(digest)` and encode as a 16-character, zero-padded lower-case hex string.

6.7.1.2 The chosen construction MUST be:

* a pure function of `merchant_id` (or `merchant_key`), `edge_seq_index` and a static namespace tag;
* independent of RNG draws and other runtime factors;
* stable across re-runs for the same inputs.

6.7.2 Edge weights:

6.7.2.1 For each merchant `m`, S2 MUST assign `edge_weight` to edges in its set `E_m` in a way that is consistent with the budget and tile allocations, e.g.:

* start from per-country weights `s_m(c)` and per-tile weights `p_tile(c,t)`;
* derive per-edge weight `w_edge(m,c,t,k)` as:

  * either uniform within each tile (`w_edge ∝ 1`) and then combined so that Σ₍edges of m₎ `edge_weight = 1`, or
  * proportional to underlying tile weights and per-country weights, with a documented law.

6.7.2.2 S2 MUST specify and implement a normalisation rule, e.g.:

* for each merchant `m`:

  * compute raw edge masses `μ_edge` for edges in `E_m`;
  * ensure Σ `μ_edge > 0`;
  * normalise `edge_weight = μ_edge / Σ μ_edge` (or map to an integer grid, as per 3B’s routing requirements).

6.7.2.3 Any rounding or quantisation MUST be deterministic (e.g. round-to-nearest-even, largest remainder) and MUST obey documented tolerances (e.g. per-merchant sum within ε of 1.0 or exact sum in integer grid).

6.7.3 Output assembly:

6.7.3.1 S2 MUST:

* construct in-memory edge rows populated with all required fields from §5.1;
* sort them by `writer_sort` (e.g. `["merchant_id","edge_id"]`);
* write them to `edge_catalogue_3B@seed={seed}, fingerprint={manifest_fingerprint}` using an atomic publish protocol.

6.7.3.2 S2 MUST then construct `edge_catalogue_index_3B`:

* derive per-merchant counts and digests from `edge_catalogue_3B` using the canonical key and ordering;
* compute a global edge digest using a documented law (e.g. concatenating per-merchant digests in sorted merchant order and hashing that);
* populate index rows in a stable order;
* write `edge_catalogue_index_3B@seed={seed}, fingerprint={manifest_fingerprint}` atomically.

6.7.3.3 S2 MUST ensure that:

* `edge_catalogue_3B` and `edge_catalogue_index_3B` are mutually consistent (counts and digests match);
* both datasets are fully written and schema-valid before S2 reports **PASS**.

---

6.8 **RNG discipline and determinism guarantees**

6.8.1 S2 MUST obey the following **RNG discipline**:

* All RNG usage is confined to Phase D;
* All RNG events have their envelopes logged in the shared RNG logs;
* No S2 code outside Phase D calls RNG APIs or emits RNG events.

6.8.2 S2 MUST ensure that:

* Given the same `{seed, parameter_hash, manifest_fingerprint}`, sealed inputs, RNG policy and contracts, S2 produces:

  * identical edge coordinates;
  * identical `tzid_operational` values;
  * identical `edge_id` and `edge_weight` values;
  * identical `edge_catalogue_3B` and `edge_catalogue_index_3B` bytes;
  * identical RNG audit/trace logs.

6.8.3 Any observed divergence across re-runs with identical inputs (e.g. different edge coordinates, different edge order, different digests or RNG traces) MUST be treated as a **non-determinism bug** (see §9) and MUST be corrected; such divergence is not permitted as a variation of this spec.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

7.1 **Identity model for 3B.S2**

7.1.1 For S2, the **canonical run-identity triple** is:

* `seed`
* `parameter_hash`
* `manifest_fingerprint`

These MUST match the values recorded for the same manifest in `s0_gate_receipt_3B`.

7.1.2 For **persisted S2 outputs**, the **primary on-disk identity** is the pair:

* `seed`
* `manifest_fingerprint`

There MUST be at most one `edge_catalogue_3B` dataset and at most one `edge_catalogue_index_3B` dataset for each `{seed, manifest_fingerprint}` pair in the storage namespace.

7.1.3 `parameter_hash` is part of the logical identity of the run, but:

* MUST NOT be used as a partition key for S2 outputs;
* MAY appear as a column for identity echo only;
* when present as a column, MUST exactly match the value in `s0_gate_receipt_3B`.

7.1.4 If `run_id` is in use at the Layer-1 harness, it MAY be:

* recorded in logs and run-reports for S2;
* optionally echoed in non-key columns of S2 datasets,

but it MUST NOT:

* influence partitioning or path structure;
* affect edge placement outcomes or RNG stream selection.

7.1.5 For a given `{seed, parameter_hash, manifest_fingerprint}`, downstream components MUST be able to locate S2 outputs uniquely by:

* resolving `edge_catalogue_3B` and `edge_catalogue_index_3B` via `dataset_dictionary.layer1.3B.yaml`;
* substituting `seed` and `manifest_fingerprint` into the declared `path_template`s.

---

7.2 **Partition law**

7.2.1 `edge_catalogue_3B` MUST be partitioned **exactly** by:

* `seed={seed}`
* `fingerprint={manifest_fingerprint}`

and by no additional partition keys. Its `path_template` MUST embed these tokens and no others.

7.2.2 `edge_catalogue_index_3B` MUST also be partitioned **exactly** by:

* `seed={seed}`
* `fingerprint={manifest_fingerprint}`

with a `path_template` of the same form, and MUST share the same `{seed, manifest_fingerprint}` as the corresponding `edge_catalogue_3B`.

7.2.3 S2 MUST NOT introduce:

* per-`parameter_hash` partitions;
* per-`run_id` partitions;
* ad-hoc sharding (e.g. per-merchant subdirectories) beyond what is declared in the dataset dictionary.

If future performance requirements demand additional sharding, such sharding MUST be:

* modelled explicitly in `dataset_dictionary.layer1.3B.yaml`;
* reflected in this spec and versioned accordingly.

7.2.4 For each `{seed, manifest_fingerprint}` partition:

* all files under the `edge_catalogue_3B` root MUST be considered a single atomic dataset;
* all files under the `edge_catalogue_index_3B` root must likewise form a single atomic dataset;
* partial partitions (e.g. only some files, or only one dataset present) MUST be treated as invalid.

---

7.3 **Primary keys, ordering & writer sort**

7.3.1 `edge_catalogue_3B` MUST have the logical **primary key**:

* `PK_edge_catalogue = (merchant_id, edge_id)`
  (or `(merchant_key, edge_id)` if a composite merchant key is adopted consistently across 3B).

Within each `{seed, fingerprint}` partition, there MUST be at most one row for any `(merchant_id, edge_id)` pair.

7.3.2 `edge_catalogue_index_3B` MUST have a key structure consistent with its schema, typically:

* **per-merchant rows**: key = `merchant_id` (or `merchant_key`);
* **global summary rows**: key indicated by a dedicated scope field (e.g. `scope = "GLOBAL"` or `merchant_id = "__GLOBAL__"`).

The exact keying MUST be defined in `schemas.3B.yaml#/plan/edge_catalogue_index_3B` and mirrored in the dataset dictionary.

7.3.3 Natural join keys:

* From `edge_catalogue_3B` to S1 outputs: join on `merchant_id` (or the adopted merchant key).
* From `edge_catalogue_index_3B` to `edge_catalogue_3B`: join on `merchant_id` and the shared `{seed, fingerprint}` partition.

Downstream states MUST use these join keys and MUST NOT rely on incidental fields for joining.

7.3.4 Writer sort MUST align with join and key structure:

* `edge_catalogue_3B.writer_sort` = `["merchant_id","edge_id"]` (or equivalent composite key first, then `edge_id`).
* `edge_catalogue_index_3B.writer_sort` = key fields as declared in §5 (e.g. `["merchant_id"]` plus a clear mechanism to locate global rows).

S2 MUST sort rows according to these `writer_sort` definitions before writing.

7.3.5 Digest and universe-hash computations in S2/S3/validation MUST use:

* the writer sort for `edge_catalogue_3B` (e.g. edges ordered by `(merchant_id, edge_id)`), and
* a well-defined ordering for per-merchant index rows (e.g. merchants in ASCII-lex order of `merchant_id`).

S2 MUST NOT rely on filesystem iteration order, shard ordering or any other non-deterministic ordering when computing counts or digests.

---

7.4 **Idempotence, immutability & atomic publish**

7.4.1 S2 outputs (`edge_catalogue_3B`, `edge_catalogue_index_3B`) for a given `{seed, parameter_hash, manifest_fingerprint}` are **logically immutable**. Once S2 reports **PASS** and both outputs are written:

* they MUST NOT be mutated in place;
* any subsequent S2 run for the same `{seed, parameter_hash, manifest_fingerprint}` MUST NOT overwrite them without conflict detection.

7.4.2 On re-execution of S2 for an identity triple that already has outputs:

* S2 MAY recompute expected outputs;
* S2 MUST compare recomputed outputs and existing on-disk outputs (either via byte comparison or via a documented digest comparison).
* If they are identical, S2 MAY treat the run as idempotent and return PASS without modifying the outputs.
* If they differ, S2 MUST fail with a FATAL conflict (e.g. `E3B_S2_OUTPUT_INCONSISTENT_REWRITE`) and MUST NOT overwrite existing outputs.

7.4.3 S2 MUST use an **atomic publish** protocol per `{seed, fingerprint}`:

* write `edge_catalogue_3B` to a temporary location;
* write `edge_catalogue_index_3B` to a temporary location;
* move/rename both into their canonical paths in a way that prevents observers from seeing one updated without the other.

7.4.4 Any observed state where:

* `edge_catalogue_3B` exists but `edge_catalogue_index_3B` does not (or vice versa);
* or either dataset is present but schema-invalid or internally inconsistent,

MUST be treated by downstream states and validation as a **3B.S2 failure**, not as valid output.

---

7.5 **Cross-segment identity & join discipline**

7.5.1 The `merchant_id` (or composite merchant key) used in S2 outputs MUST be:

* identical in type and semantics to that used in S1 outputs (`virtual_classification_3B`, `virtual_settlement_3B`);
* compatible with the keys used in upstream segments for merchants (ingress / 1A).

S2 MUST NOT introduce a different merchant identifier scheme without explicit change control and corresponding schema/dictionary updates.

7.5.2 Any state (S2, S3, 2B, validation) that joins:

* S2 outputs to S1 outputs, or
* S2 outputs to upstream segment outputs (for diagnostics or validation),

MUST:

* respect the declared keys and partition law on both sides;
* use `{seed, fingerprint}` to ensure joins are within the same run;
* treat missing or extra rows as data-quality or contract violations, not as “optional” noise.

7.5.3 S2 MUST NOT:

* create edges for non-virtual merchants;
* create edges for merchant IDs not present in S1’s virtual universe (unless explicitly allowed by a future extension and documented as such);
* drop virtual merchants from the edge catalogue unless a configuration mode explicitly defines a “no-edge” policy and S2 records that fact in its index/run-report.

---

7.6 **Multi-manifest & multi-seed behaviour**

7.6.1 S2 MUST treat each `{seed, manifest_fingerprint}` as an independent world:

* S2 behaviour and outputs are scoped to that identity;
* there is no requirement that edge catalogues across different manifests be comparable, stable or merged.

7.6.2 For different seeds under the same manifest:

* S2 MAY be invoked with multiple `seed` values (if the engine supports multi-seed runs);
* each `(seed, manifest_fingerprint)` pair MUST produce its own S2 outputs under separate partitions;
* the spec does not require any relation between edge catalogues for different seeds, except that each must be internally deterministic and valid for its seed.

7.6.3 Higher-level tooling MAY compare S2 outputs across manifests or seeds (e.g. for drift detection), but such cross-run analysis is outside the scope of S2 and MUST NOT feed back into S2’s behaviour.

---

7.7 **Non-conformance and correction**

7.7.1 Any implementation that:

* deviates from the partition law in §7.2;
* uses alternative keys or unsorted writer order contrary to §7.3;
* overwrites S2 outputs without idempotent comparison;
* or allows partial publishes of S2 outputs,

is **non-conformant** with this specification.

7.7.2 Such behaviour MUST be treated as an engine/spec bug. Corrective action MUST:

* restore the partitioning and key discipline described here;
* enforce immutability and idempotence;
* ensure all digest computations, universe hashes and RNG accounting are based on the canonical ordering and identity rules defined above.

7.7.3 If historical S2 outputs exist that violate these rules, migration tools MAY:

* read them under their existing schema;
* transform them into conformant datasets under a new `manifest_fingerprint` or schema version;

but the migrated outputs MUST then obey the identity, partition, ordering and merge discipline described in this section.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

8.1 **S2 state-level PASS criteria**

8.1.1 A run of 3B.S2 for a given `{seed, parameter_hash, manifest_fingerprint}` SHALL be considered **PASS** if and only if **all** of the following groups of conditions hold.

**Identity & gating**

a. `s0_gate_receipt_3B` and `sealed_inputs_3B` exist for the target `manifest_fingerprint` and validate against their schemas.
b. `segment_id = "3B"` and `state_id = "S0"` in `s0_gate_receipt_3B`.
c. `seed`, `parameter_hash`, and `manifest_fingerprint` used by S2 match those embedded in `s0_gate_receipt_3B` (where present).
d. `upstream_gates.segment_1A/1B/2A/3A.status = "PASS"` in `s0_gate_receipt_3B`.

**Contracts & sealed inputs**

e. `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` form a compatible triplet for S2 (per 3B’s versioning rules).
f. All S2-mandatory artefacts (virtual S1 outputs, CDN policy packs, required spatial surfaces, tz assets, RNG policy artefacts) are present in `sealed_inputs_3B`, readable, and schema-conformant.
g. Any feature flags/modes that S2 depends on (e.g. virtual edges enabled/disabled, shared tiles vs 3B tiles, fixed per-merchant budgets) are part of the governed parameter set (i.e. consistent with `parameter_hash`), and S2’s behaviour matches the configured mode.

**S1 contracts & virtual set**

h. `virtual_classification_3B@seed={seed},fingerprint={manifest_fingerprint}` and `virtual_settlement_3B@seed={seed},fingerprint={manifest_fingerprint}` exist and validate against their schemas.
i. The virtual merchant set `V` is derived **only** from `virtual_classification_3B` as those rows with `is_virtual = 1` (or `classification = "VIRTUAL"`).
j. For each `m ∈ V`, there is exactly one matching row in `virtual_settlement_3B` with the same merchant key.
k. There are no rows in `virtual_settlement_3B` for merchants not in `V`, unless explicitly allowed by S1’s contract and documented.

**Edge budgets & country allocation (Phase B)**

l. CDN country weights and any per-class/per-merchant overrides are parsed successfully and validate against their policy schemas.
m. For each `m ∈ V`:

* S2 computes a nominal total edge budget `E_nominal(m)` and a clipped integer `E_clipped(m)` using the documented class/override and min/max rules.
* `E_clipped(m) ≥ 0` and finite; if policy disallows zero-edge virtual merchants, `E_clipped(m) ≥ 1` where required.

n. For each `m ∈ V`:

* S2 computes a set of allowed countries `C_m` and normalised country shares `s_m(c)` with `Σ₍c∈C_m₎ s_m(c) = 1` within numeric tolerance.
* S2 computes integer per-country edge counts `E_m(c)` via the documented largest-remainder (or equivalent) scheme, with:

  * `E_m(c) ≥ 0`, and
  * Σ₍c∈C_m₎ `E_m(c) = E_clipped(m)`.

o. Any policy-defined per-country floors/caps (e.g. minimum 1 edge in certain countries) are all satisfied, or the run fails with a policy-consistency error.

**Tile-level allocation (Phase C)**

p. For each country `c` referenced in budgets, S2 either:

* uses 1B/3B tiling surfaces and validates their shapes, or
* explicitly has a configured “no-tiling” mode (which MUST be documented and validated in the 3B spec).

q. For each `(m,c)` with `E_m(c) > 0`, S2 constructs tile sets `T_c` and normalised tile shares `p_tile(c,t)` such that:

* `p_tile(c,t) ≥ 0`,
* Σ₍t∈T_c₎ `p_tile(c,t) = 1` within tolerance.

r. For each `(m,c)`, S2 computes integer tile counts `E_m(c,t)` with:

* `E_m(c,t) ≥ 0` for all `t`,
* Σ₍t∈T_c₎ `E_m(c,t) = E_m(c)`.

s. If an intermediate `edge_tile_plan_3B` or equivalent planning surface is persisted, it validates against its schema and obeys the above invariants.

**Edge placement & RNG accounting (Phase D)**

t. For each `(m,c,t)` with `E_m(c,t) > 0`, S2 places exactly `E_m(c,t)` edges inside tile `t` using the Philox streams authorised by the RNG policy.

u. For every successful edge placement:

* the chosen coordinate lies inside tile `t` according to the tiling surface, and
* lies inside the country polygon for `country_iso = c`.

v. S2 respects the jitter retry bound `JITTER_MAX_ATTEMPTS`; if any edge cannot be placed within this bound, S2 aborts (does not silently emit an invalid coordinate) and surfaces an appropriate spatial/jitter error.

w. RNG evidence:

* All RNG activity originates from S2-approved streams and substream labels.
* Each jitter event carries a valid RNG envelope and payload, with `draws` equal to the actual number of Philox draws.
* The total number of RNG events and draws is consistent with `|E_m(c,t)|` for all `(m,c,t)` and with the configured budgets in the RNG policy.

**Timezone resolution (Phase E)**

x. For each edge, a `tzid_operational` is assigned via either:

* ingestion from a trusted field that validates as a correct IANA tzid, or
* polygon/override logic that is compatible with 2A’s tz semantics.

y. All `tzid_operational` values:

* are non-null;
* match the tzid schema (IANA tzid);
* optionally, when checked, are consistent with `(edge_latitude_deg, edge_longitude_deg)` and tz-world polygons.

z. `tz_source` is set to an allowed enum value and reflects the actual resolution path (`POLYGON`, `OVERRIDE`, `INGESTED`, etc.).

**Edge catalogue & index correctness (Phase F)**

aa. `edge_catalogue_3B@seed={seed},fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/plan/edge_catalogue_3B`.

bb. `edge_catalogue_index_3B@seed={seed},fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/plan/edge_catalogue_index_3B`.

cc. Structural invariants:

* `(merchant_id, edge_id)` is unique within `edge_catalogue_3B` for the partition.

* For each `m ∈ V`, the number of edge rows with `merchant_id = m`:

  * equals `E_clipped(m)` (or a documented no-edge configuration, see 8.2), and
  * matches `edge_count_total` in the per-merchant row of `edge_catalogue_index_3B`.

* `edge_count_total_all_merchants` equals the total row count of `edge_catalogue_3B` for the partition.

dd. `edge_weight` fields:

* are non-negative and finite;
* respect the declared normalisation rule per merchant (e.g. Σ₍edges of m₎ `edge_weight = 1` within tolerance, or exact integer grid sum).

ee. All required provenance fields (`cdn_policy_id`, `cdn_policy_version`, `spatial_surface_id`, etc.) are present and consistent with the sealed artefacts.

ff. Any `edge_catalogue_digest_*` fields in the index are consistent with a documented canonical digest law applied over `edge_catalogue_3B` (per-merchant and global).

8.1.2 If **any** of the criteria in 8.1.1 fail, S2 MUST be considered **FAIL** for that `{seed, parameter_hash, manifest_fingerprint}`. S2 MUST NOT publish incomplete or partially correct outputs as if they were valid; any artefacts written before detecting failure MUST be treated as invalid and MUST NOT be used by downstream states.

---

8.2 **Coverage semantics (per-merchant edges)**

8.2.1 By default, in **full-edge mode**, S2 operates under the assumption that:

* every merchant `m ∈ V` MUST have `E_clipped(m) ≥ 1` and thus at least one edge in `edge_catalogue_3B`.

In this mode, `E_m(c)` and `E_m(c,t)` MUST distribute those edges across allowed countries and tiles; a virtual merchant with zero edges is treated as a configuration error.

8.2.2 If the 3B design supports a **no-edge-virtual** mode (e.g. some virtual merchants are logically virtual but not routed via CDN):

* this mode MUST be explicitly documented and wired via configuration / policy;

* S2 MUST:

  * either assign `E_clipped(m) = 0` deterministically for such merchants and record them in `edge_catalogue_index_3B` as “no-edge” cases (e.g. `edge_count_total = 0`, with an explicit reason code), or
  * skip those merchants entirely, with a separate diagnostic dataset recording them.

* Downstream routing or validation MUST have clear semantics for these merchants (e.g. they receive no traffic).

8.2.3 Any partial coverage that is **not** explicitly configured (e.g. some `m ∈ V` unexpectedly receiving zero edges due to data errors or misconfiguration) MUST cause S2 to fail rather than silently dropping those merchants from the edge universe.

---

8.3 **Gating obligations for downstream 3B states (S3 & validation)**

8.3.1 For a given `{seed, manifest_fingerprint}`, **3B.S3** (edge alias & universe hash) MUST, before doing any work:

* verify that `edge_catalogue_3B` and `edge_catalogue_index_3B` exist and validate against their schemas;
* verify key structural invariants (uniqueness, counts, digests) as per §5 and §6;
* verify that S1 outputs (`virtual_classification_3B`, `virtual_settlement_3B`) still exist and have keys consistent with `edge_catalogue_3B` (e.g. no edges for non-virtual merchants).

8.3.2 S3 MUST treat:

* `edge_catalogue_3B` as the **sole source** of edge nodes for virtual merchants;
* `edge_catalogue_index_3B` as the **canonical summary** to be used when building alias tables and virtual edge universe hashes.

S3 MUST NOT:

* recompute edges from CDN policy/raster inputs;
* patch or mutate S2’s edge catalogue.

8.3.3 The 3B validation state MUST:

* treat S2 compliance with this section as a prerequisite for segment-level PASS;
* include S2 outputs in the validation bundle index;
* perform additional checks (e.g. joining edges back to S1 and S0 artefacts) to confirm S2 has adhered to identity, partition and RNG laws.

---

8.4 **Gating obligations for 2B virtual routing and other consumers**

8.4.1 Any 2B logic that performs **virtual routing** MUST be gated on:

* 3B’s segment-level PASS flag (once implemented), and
* any S3-specific PASS conditions (e.g. alias/universe hash construction PASS).

8.4.2 2B MUST NOT:

* construct its own edge catalogue from policy/raster inputs when S2 is present;
* route virtual merchants against a different edge universe than the one described by `edge_catalogue_3B` and its derived alias/universe surfaces.

8.4.3 If 2B, S3, or any other consumer detects:

* missing S2 outputs;
* schema violations in S2 outputs;
* join inconsistencies between S1 and S2 (edges for non-virtual merchants, missing edges for virtual merchants in coverage-required mode);

they MUST:

* treat this as a **3B.S2 failure**;
* fail fast rather than attempting to improvise edges;
* report an appropriate error (re-using S2’s error namespace where applicable) and stop processing for that manifest.

---

8.5 **Interaction with S0/S1 gating**

8.5.1 S2 acceptance is strictly downstream of S0 + S1 acceptance:

* S0 PASS and the existence of valid `sealed_inputs_3B` is a **hard precondition**;
* S1 PASS (in the sense of correct classification and settlement surfaces) is a **functional precondition**.

8.5.2 If S2 detects a violation of S0 or S1 contracts (e.g. missing S1 outputs, join inconsistencies, misaligned identity), S2 MUST:

* fail immediately;
* not attempt to rerun or repair S0 or S1;
* surface the issue as a configuration / upstream problem via S2 error codes and run-report.

---

8.6 **Failure semantics and propagation**

8.6.1 Any violation of the binding requirements in §§8.1–8.5 MUST result in:

* S2 returning **FAIL** for that `{seed, parameter_hash, manifest_fingerprint}`;
* no S2 outputs being considered valid for that `{seed, fingerprint}` (partial artefacts MUST be treated as invalid);
* a canonical `E3B_S2_*` error code being logged with sufficient diagnostic context.

8.6.2 The run harness MUST:

* prevent downstream states (S3, 3B validation, and any 2B virtual routing using this manifest) from executing when S2 has failed;
* avoid emitting any 3B segment-level PASS flag that implies S2 success.

8.6.3 If a downstream state detects a latent S2 violation after S2 has reported PASS (e.g. due to an implementation bug in S2), that state MUST:

* treat S2’s outputs as invalid;
* surface the failure as a S2-contract problem;
* not attempt to work around the inconsistency by altering edge catalogues or alias tables.

In all cases, **edge catalogue correctness, coverage, and RNG/identity integrity** as specified above are the binding conditions under which S2 can be said to have “passed” for a given run.

---

## 9. Failure modes & canonical error codes *(Binding)*

9.1 **Error model & severity**

9.1.1 3B.S2 SHALL use a **state-local error namespace** of the form:

* `E3B_S2_<CATEGORY>_<DETAIL>`

All codes in this section are reserved for 3B.S2 and MUST NOT be reused by other states.

9.1.2 Every surfaced S2 failure MUST carry, at minimum:

* `segment_id = "3B"`
* `state_id = "S2"`
* `error_code`
* `severity ∈ {"FATAL","WARN"}`
* `manifest_fingerprint`
* optional `{seed, parameter_hash}`
* a human-readable `message` (non-normative)

9.1.3 Unless explicitly marked as `WARN`, all codes below are **FATAL** for S2:

* **FATAL** ⇒ S2 MUST NOT publish `edge_catalogue_3B` or `edge_catalogue_index_3B` as valid outputs for that `{seed,fingerprint}`; the virtual edge universe MUST be considered **not constructed** for that manifest.
* **WARN** ⇒ S2 MAY complete and publish outputs, but the condition MUST be observable via logs / run-report and SHOULD be visible in metrics.

---

### 9.2 Identity & gating failures

9.2.1 **E3B_S2_IDENTITY_MISMATCH** *(FATAL)*
Raised when identity as seen by S2 does not agree with the S0 gate:

* `seed`, `parameter_hash`, or `manifest_fingerprint` provided to S2 differ from those embedded in `s0_gate_receipt_3B`; or
* `s0_gate_receipt_3B` itself contains conflicting identity fields.

Typical triggers:

* S0 and S2 invoked with different identity triples;
* manual modification of S0 artefacts.

Remediation:

* Fix the run harness so that S0 and S2 see the same `{seed, parameter_hash, manifest_fingerprint}`;
* regenerate S0 artefacts if they were altered.

---

9.2.2 **E3B_S2_GATE_MISSING_OR_INVALID** *(FATAL)*
Raised when S2 cannot treat S0 outputs as a valid gate:

* `s0_gate_receipt_3B` or `sealed_inputs_3B` missing for the fingerprint;
* OR either artefact fails schema validation.

Typical triggers:

* S2 invoked before S0;
* S0 failed and its failure was ignored;
* schema drift or storage corruption.

Remediation:

* Run/fix S0 for the manifest;
* restore or regenerate missing/invalid artefacts.

---

9.2.3 **E3B_S2_UPSTREAM_GATE_BLOCKED** *(FATAL)*
Raised when `s0_gate_receipt_3B.upstream_gates` indicates any of 1A, 1B, 2A, 3A is not `status = "PASS"`.

Typical triggers:

* upstream segment failed validation or was not run for this manifest.

Remediation:

* Diagnose and repair the failing upstream segment;
* re-run its validation and S0, then S2.

---

9.2.4 **E3B_S2_S1_CONTRACT_VIOLATION** *(FATAL)*
Raised when S1 outputs do not satisfy S1’s contract from S2’s perspective, e.g.:

* `virtual_classification_3B` or `virtual_settlement_3B` missing or schema-invalid;
* virtual set `V` implies a merchant has `is_virtual = 1` but no matching settlement row;
* settlement rows exist for merchants not in `V` in a mode where that is not allowed.

Typical triggers:

* incomplete or inconsistent S1 run;
* manual modification of S1 outputs.

Remediation:

* Fix/rerun S1 until classification and settlement nodes are coherent;
* re-run S2 afterwards.

---

### 9.3 Contract & sealed-input failures

9.3.1 **E3B_S2_SCHEMA_PACK_MISMATCH** *(FATAL)*
Raised when `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` are incompatible for S2:

* missing schema refs for S2 outputs;
* MAJOR-version mismatch;
* dictionary refers to datasets not defined in the schema.

Typical triggers:

* partial deployment of 3B contracts;
* editing dictionary/registry without schema updates.

Remediation:

* Align schema/dictionary/registry versions;
* redeploy a coherent set and rerun S0/S1/S2.

---

9.3.2 **E3B_S2_REQUIRED_INPUT_NOT_SEALED** *(FATAL)*
Raised when a **mandatory** S2 input artefact (S1 outputs, CDN policy, tile surfaces, tz assets, RNG policy, etc.) does not appear in `sealed_inputs_3B`.

Typical triggers:

* new artefact added but not included in S0 sealing;
* S2 spec updated without S0 changes.

Remediation:

* Register artefact in dictionary/registry;
* update S0 to seal it;
* rerun S0 and S2.

---

9.3.3 **E3B_S2_INPUT_OPEN_FAILED** *(FATAL)*
Raised when S2 resolves an artefact from `sealed_inputs_3B` but cannot open it for read.

Typical triggers:

* path in `sealed_inputs_3B` stale or wrong;
* permissions / storage endpoint misconfigured;
* transient IO errors not retried at the correct layer.

Remediation:

* Fix storage/permissions/connectivity;
* ensure sealed paths match actual storage;
* rerun S0 (if paths changed) and S2.

---

9.3.4 **E3B_S2_INPUT_SCHEMA_MISMATCH** *(FATAL)*
Raised when a sealed dataset or policy artefact does not conform to its declared `schema_ref`.

Typical triggers:

* CDN policy with missing or malformed fields;
* tile surfaces missing required columns;
* tz assets not matching expected shapes.

Remediation:

* Fix the underlying artefact and/or its schema;
* or update dictionary/schema consistently;
* reseal via S0 and rerun S2.

---

9.3.5 **E3B_S2_RNG_POLICY_INVALID** *(FATAL)*
Raised when the RNG / routing policy artefact for S2:

* is missing required stream definitions or budgets;
* fails validation against its schema;
* conflicts with the layer-wide RNG envelope (e.g. mismatched algorithm).

Typical triggers:

* incomplete RNG policy;
* misconfigured stream labels or budget structure.

Remediation:

* Correct RNG policy to define all S2 streams and budgets;
* ensure alignment with `schemas.layer1.yaml` RNG definitions.

---

### 9.4 Edge-budget & integerisation failures

9.4.1 **E3B_S2_BUDGET_POLICY_INVALID** *(FATAL)*
Raised when the CDN edge-budget policy cannot be parsed or fails schema validation.

Typical triggers:

* malformed YAML/JSON;
* missing required fields (`country_iso`, weights, class configs);
* invalid enum values.

Remediation:

* Fix the policy file content;
* ensure conformity with its schema;
* reseal in S0 and rerun S2.

---

9.4.2 **E3B_S2_BUDGET_COUNTRY_WEIGHTS_INVALID** *(FATAL)*
Raised when country weights are unusable, for example:

* negative weights;
* `Σ₍c∈C₎ w_global(c) ≤ 0`;
* normalisation impossible with current policy.

Typical triggers:

* data bugs in `cdn_country_weights`;
* mis-specified weights.

Remediation:

* Correct weight values and re-normalise;
* enforce non-negativity and valid sums in the policy.

---

9.4.3 **E3B_S2_BUDGET_CLASS_MAPPING_INVALID** *(FATAL)*
Raised when S2 cannot determine a valid merchant class for one or more virtual merchants:

* `class(m)` undefined for some `m ∈ V`;
* overlapping or conflicting class rules.

Typical triggers:

* class-mapping policy not covering all merchants;
* ambiguous conditions without precedence.

Remediation:

* Fix class mapping definitions;
* add default/fallback classes;
* encode precedence clearly.

---

9.4.4 **E3B_S2_BUDGET_TOTAL_INVALID** *(FATAL)*
Raised when S2 cannot compute a valid total edge budget `E_clipped(m)` for some merchant:

* computed value is negative, NaN or infinite;
* cannot respect min/max constraints without violating other hard constraints in an unsatisfiable way.

Typical triggers:

* conflicting min/max vs class budgets;
* numeric overflow/underflow in policy arithmetic.

Remediation:

* Fix policy parameters for class budgets and min/max;
* adjust constraints to be satisfiable.

---

9.4.5 **E3B_S2_COUNTRY_INTEGERISATION_FAILED** *(FATAL)*
Raised when S2 cannot derive integer per-country edge counts `E_m(c)` that satisfy:

* Σ₍c∈C_m₎ `E_m(c) = E_clipped(m)` and
* all configured floors/caps.

Typical triggers:

* combination of floors/caps and total edges is mathematically impossible;
* bugs in integerisation logic.

Remediation:

* Adjust policy constraints;
* or correct integerisation algorithm.

---

9.4.6 **E3B_S2_TILE_INTEGERISATION_FAILED** *(FATAL)*
Raised when S2 cannot distribute `E_m(c)` across tiles:

* sum of `E_m(c,t)` over tiles ≠ `E_m(c)`;
* required floors/caps per tile incompatible with `E_m(c)`.

Typical triggers:

* unrealistic tile floors given E_m(c);
* implementation bug in tile allocation.

Remediation:

* Relax or correct tile-level constraints in policy;
* fix allocation logic.

---

### 9.5 Spatial & timezone failures

9.5.1 **E3B_S2_TILE_SURFACE_INVALID** *(FATAL)*
Raised when tiling surfaces are not usable:

* `tile_index` or `tile_weights` missing required fields;
* negative or zero weights for all tiles in a country;
* country referenced in budgets has no tiles.

Typical triggers:

* incomplete or inconsistent 1B/3B spatial configurations;
* misaligned tile/country sets.

Remediation:

* Correct tiling artefacts;
* ensure coverage for all countries in `C_m` for all `m ∈ V`.

---

9.5.2 **E3B_S2_EDGE_OUTSIDE_COUNTRY** *(FATAL)*
Raised when an edge coordinate, after jitter, lies outside the intended country polygon:

* `(edge_latitude_deg, edge_longitude_deg)` not in polygon for `country_iso`.

Typical triggers:

* incorrect tile-country mapping;
* jitter logic not constrained to tile/country geometry.

Remediation:

* Fix tile index definitions and/or jitter algorithm;
* ensure membership tests are correct.

---

9.5.3 **E3B_S2_JITTER_RESAMPLE_EXHAUSTED** *(FATAL)*
Raised when S2 attempts to jitter an edge inside a tile but fails to find a valid point within `JITTER_MAX_ATTEMPTS`.

Typical triggers:

* tile geometry inconsistent with country polygon (e.g. tile lightly overlaps or is entirely outside polygon);
* overly restrictive inclusion criteria;
* too small jitter bounds.

Remediation:

* Fix tile geometry or inclusion criteria;
* adjust jitter bounds or MAX attempts where appropriate.

---

9.5.4 **E3B_S2_TZ_RESOLUTION_FAILED** *(FATAL)*
Raised when S2 cannot assign any valid `tzid_operational` to one or more edges:

* point does not fall into any tz polygon and overrides do not apply;
* tz-world / tzdb artefacts incomplete or inconsistent.

Typical triggers:

* edge coordinates near or outside tz coverage;
* misaligned tz assets.

Remediation:

* Correct tz assets;
* adjust tz resolution logic or override policy for problematic regions.

---

9.5.5 **E3B_S2_TZID_INVALID** *(FATAL)*
Raised when `tzid_operational` values in `edge_catalogue_3B`:

* are not valid IANA tzids; or
* do not appear in the sealed tz-world/tzdb index (if cross-checked).

Typical triggers:

* ingestion of arbitrary tz strings;
* mismatch between tzdb version and tzids used.

Remediation:

* normalise to canonical IANA tzids;
* align tz assets and S2’s logic.

---

### 9.6 Output structure, consistency & digest failures

9.6.1 **E3B_S2_EDGE_CATALOGUE_SCHEMA_VIOLATION** *(FATAL)*
Raised when `edge_catalogue_3B` fails validation against its schema:

* missing required columns;
* wrong types;
* wrong partitioning or unsorted writer order.

Typical triggers:

* implementation error in S2 write path;
* schema/dictionary drift.

Remediation:

* Correct S2 output assembly logic;
* update schema/dictionary in a versioned way if shape was intentionally changed.

---

9.6.2 **E3B_S2_EDGE_INDEX_SCHEMA_VIOLATION** *(FATAL)*
Raised when `edge_catalogue_index_3B` fails its schema:

* missing per-merchant rows;
* missing or malformed global summary row;
* wrong key or writer sort.

Typical triggers:

* incomplete index construction;
* schema mismatch.

Remediation:

* Fix index construction;
* align schema and implementation.

---

9.6.3 **E3B_S2_EDGE_INDEX_INCONSISTENT_WITH_CATALOGUE** *(FATAL)*
Raised when index values do not match `edge_catalogue_3B`:

* `edge_count_total` per merchant ≠ actual number of edges for that merchant;
* `edge_count_total_all_merchants` ≠ total row count;
* per-merchant or global digests do not match recomputed digests.

Typical triggers:

* index computed from a different or partially written catalogue;
* logic bug in digest computation.

Remediation:

* fix index/digest computation;
* enforce atomic publish of catalogue and index.

---

9.6.4 **E3B_S2_OUTPUT_WRITE_FAILED** *(FATAL)*
Raised when S2 cannot complete the atomic write of either `edge_catalogue_3B` or `edge_catalogue_index_3B`.

Typical triggers:

* IO failures, permission issues, space constraints.

Remediation:

* Resolve storage issues;
* retry S2 after ensuring atomic write semantics.

---

9.6.5 **E3B_S2_OUTPUT_INCONSISTENT_REWRITE** *(FATAL)*
Raised when S2 detects that existing outputs for the same `{seed, manifest_fingerprint}` are not identical to recomputed outputs.

Typical triggers:

* environment drift (policies, tiles, tz assets) under a fixed `manifest_fingerprint`;
* manual tampering with S2 outputs.

Remediation:

* treat as manifest/environment inconsistency;
* either restore the original environment or recompute a new `manifest_fingerprint` and rerun S0–S2.

---

### 9.7 RNG & determinism violations

9.7.1 **E3B_S2_RNG_POLICY_VIOLATION** *(FATAL)*
Raised when S2’s RNG usage violates the configured policy:

* uses an undeclared RNG stream or substream label;
* exceeds draw budgets per stream;
* misreports `draws` or `blocks` in RNG envelopes.

Typical triggers:

* incorrect mapping from logical streams to policy entries;
* changes in policy not reflected in S2 implementation.

Remediation:

* correct S2 RNG stream usage;
* update RNG policy or S2 to be consistent.

---

9.7.2 **E3B_S2_RNG_ENVELOPE_INVALID** *(FATAL)*
Raised when S2 emits RNG events that do not conform to the layer-wide RNG envelope schema:

* missing or malformed fields;
* non-monotonic counters;
* inconsistent before/after values vs `draws` and `blocks`.

Typical triggers:

* envelope construction bugs;
* incorrect counter increment logic.

Remediation:

* fix envelope construction and counter handling;
* add tests to ensure envelope validity.

---

9.7.3 **E3B_S2_NONDETERMINISTIC_OUTPUT** *(FATAL)*
Raised when S2’s outputs are observed to differ across re-runs with identical inputs:

* different edge coordinates;
* different ordering of edges or edge IDs;
* different digests or RNG traces.

Typical triggers:

* reliance on unordered iteration (e.g. dict or directory order);
* hidden state or non-reproducible RNG seeding.

Remediation:

* enforce explicit ordering at all critical steps;
* ensure RNG streams are seeded and advanced only as per spec;
* remove any hidden non-deterministic behaviour.

---

### 9.8 Error propagation & downstream behaviour

9.8.1 On any FATAL S2 error, S2 MUST:

* log a structured error event containing the fields in §9.1.2;
* ensure no partially written outputs are treated as valid (atomic publish or clean-up);
* return **FAIL** for the run.

9.8.2 The run harness MUST:

* prevent 3B.S3, 3B validation and any 2B virtual routing that depends on S2 from running for that `{seed, manifest_fingerprint}`;
* surface S2 failures as **“edge catalogue construction failure”** for the manifest.

9.8.3 Downstream states (S3, 3B validation, 2B virtual routing) that detect S2-related inconsistencies at consumption time SHOULD:

* re-use the most appropriate `E3B_S2_*` error code, but
* tag themselves as the originator in logs (`state_id` = `"S3"` or `"2B"`),

to make clear that S2’s contract was violated, even if the detection came later.

9.8.4 Any new S2 failure condition introduced in future versions MUST:

* be assigned a unique `E3B_S2_...` code;
* be documented with severity, typical triggers and remediation;
* NOT overload existing codes with incompatible semantics.

---

## 10. Observability & run-report integration *(Binding)*

10.1 **Structured logging requirements**

10.1.1 S2 MUST emit, at minimum, the following **lifecycle log events** for each attempted run:

* a **`start`** event when S2 begins work for a given `{seed, parameter_hash, manifest_fingerprint}`, and
* a **`finish`** event when S2 either completes successfully or fails.

10.1.2 Both `start` and `finish` events MUST be structured and include at least:

* `segment_id = "3B"`
* `state_id = "S2"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `event_type ∈ {"start","finish"}`
* `ts_utc` — UTC timestamp of the event

10.1.3 The `finish` event MUST additionally include:

* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL; `null` or omitted for PASS)
* `virtual_merchant_count` — size of `V`, the virtual merchant set derived from S1
* `edge_count_total_all_merchants` — total number of edges written to `edge_catalogue_3B`
* `edge_count_zero_merchants` — number of virtual merchants with `E_clipped(m) = 0` (0 in full-edge mode)
* `outputs_written` — boolean indicating whether both `edge_catalogue_3B` and `edge_catalogue_index_3B` were successfully written and validated for the partition

10.1.4 For every FATAL error, S2 MUST emit at least one **error log event** that includes:

* the fields in 10.1.2,
* `error_code` in the `E3B_S2_*` namespace,
* `severity = "FATAL"`,
* and **diagnostic context** appropriate to the failure (e.g. `merchant_id`, `country_iso`, `tile_id`, `rng_stream_id`, or failed artefact `logical_id`).

10.1.5 If the implementation emits WARN-level conditions (e.g. soft anomalies permitted in certain modes), these MUST:

* include `severity = "WARN"` and an appropriate `E3B_S2_*` code;
* never mask conditions that, per this spec, should be FATAL.

---

10.2 **Run-report record for 3B.S2**

10.2.1 S2 MUST produce a **run-report record** for each `{seed, manifest_fingerprint}` that the Layer-1 run-report / 4A–4B harness can consume. This record MAY be:

* a row in a dedicated run-report dataset, and/or
* an in-memory structure passed to the harness,

but the payload MUST contain at least:

* `segment_id = "3B"`
* `state_id = "S2"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL; `null` or omitted for PASS)
* `virtual_merchant_count`
* `edge_count_total_all_merchants`
* `edge_count_zero_merchants`
* `gate_receipt_path` — canonical path to `s0_gate_receipt_3B`
* `sealed_inputs_path` — canonical path to `sealed_inputs_3B`
* `virtual_classification_path` — canonical root for `virtual_classification_3B`
* `virtual_settlement_path` — canonical root for `virtual_settlement_3B`
* `edge_catalogue_path` — canonical root for `edge_catalogue_3B`
* `edge_catalogue_index_path` — canonical root for `edge_catalogue_index_3B`

10.2.2 Where available, the run-report record SHOULD also include:

* `cdn_policy_id` / `cdn_policy_version` used for this run
* identifiers of spatial surfaces used:

  * `tile_surface_id` (e.g. `"1B.tiles.v1"` or `"3B.tiles.v1"`)
  * `raster_surface_id` for HRSL/population if applicable
* `tz_assets_version` (e.g. tz-world release and tzdb release tag)
* basic **distribution metrics**, such as:

  * `edges_per_virtual_merchant_p50/p90/p99`
  * `edge_count_by_country_top_k` (top-k countries by total edges)

10.2.3 The run-report harness MUST be able to determine from S2’s record alone:

* whether S2 has **successfully constructed** the edge universe for `{seed, manifest_fingerprint}`;
* where to locate S2’s outputs;
* whether there are coverage anomalies (e.g. `edge_count_zero_merchants > 0` in a full-edge configuration) that require operator attention.

---

10.3 **Metrics & counters**

10.3.1 S2 MUST emit the following **metrics** (names illustrative; the concrete metric names may vary but semantics must match):

* `3b_s2_runs_total{status="PASS|FAIL"}` — counter, incremented once per S2 run.
* `3b_s2_virtual_merchants` — gauge/histogram; value = `virtual_merchant_count`.
* `3b_s2_edge_count_total` — gauge/histogram; value = `edge_count_total_all_merchants`.
* `3b_s2_edge_count_zero_merchants` — gauge; count of virtual merchants with zero edges (should be 0 in full-edge mode).
* `3b_s2_edges_per_merchant` — histogram of edges per virtual merchant, for capacity and skew analysis.
* `3b_s2_duration_seconds` — latency of S2 run from `start` to `finish`.
* `3b_s2_errors_total{error_code=...}` — counter of S2 error occurrences aggregated by `E3B_S2_*` code.
* `3b_s2_jitter_resamples_total` — counter of jitter resample attempts (sum over all edges);
* `3b_s2_jitter_exhausted_total` — counter of edges that hit `JITTER_MAX_ATTEMPTS` (should be 0 on PASS).

10.3.2 Metrics SHOULD be tagged with:

* `segment_id = "3B"`
* `state_id = "S2"`
* a reduced identifier for `manifest_fingerprint` (e.g. hash prefix or stable manifest label) to avoid unbounded cardinality
* where applicable, `error_code`, `country_iso`, or `merchant_class` for breakdowns.

10.3.3 Operators MUST be able to use these metrics to answer, at minimum:

* “How many virtual merchants do we have, and how many edges are we generating per run?”
* “Are there any virtual merchants unexpectedly receiving zero edges?”
* “Which error codes are causing S2 failures most frequently?”
* “Is S2 meeting its latency SLOs across manifests?”

---

10.4 **Traceability & correlation**

10.4.1 S2 MUST ensure that its outputs, logs and run-report records are **correlatable** via the identity triple. Concretely:

* `edge_catalogue_3B` and `edge_catalogue_index_3B` paths MUST include `seed` and `fingerprint`;
* any identity echo columns in these datasets MUST match `{seed, manifest_fingerprint, parameter_hash}`;
* S2 logs MUST include `{seed, parameter_hash, manifest_fingerprint}` and `run_id` (if available).

10.4.2 Given a specific merchant (`merchant_id`) and manifest, an operator MUST be able to:

* retrieve the merchant’s classification (`virtual_classification_3B` row) and settlement node (`virtual_settlement_3B` row);
* list all edges for that merchant from `edge_catalogue_3B`;
* inspect per-merchant index information (edge counts, digests) from `edge_catalogue_index_3B`;
* locate associated RNG jitter events in RNG logs via recorded keys (`merchant_id`, `country_iso`, `tile_id`, `edge_id` or equivalent).

10.4.3 If the platform uses **correlation IDs** (e.g. trace IDs, run IDs), S2 MAY:

* include a `trace_id` or similar field in log events;
* expose it as a non-binding field in run-report records.

Such values are informational and MUST NOT influence S2’s algorithmic behaviour or outputs.

---

10.5 **Integration with Layer-1 / 4A–4B validation harness**

10.5.1 S2 MUST provide enough information for the Layer-1 validation / observability harness (e.g. 4A/4B) to:

* detect, for each `{seed, manifest_fingerprint}`, whether S2 has **run** and whether it **passed**;
* attribute failures to specific error codes and broad categories (identity/gate, inputs, budgets, spatial/tz, RNG, output structure).

10.5.2 At minimum, the harness MUST be able to derive from S2’s run-report record:

* `3B.S2.status ∈ {"PASS","FAIL"}`
* `3B.S2.error_code` (if any)
* `3B.S2.virtual_merchant_count`
* `3B.S2.edge_count_total_all_merchants`
* `3B.S2.edge_count_zero_merchants`
* pointers to S2 outputs:

  * `edge_catalogue_path`
  * `edge_catalogue_index_path`

10.5.3 In a **global manifest summary**, S2 SHOULD contribute:

* high-level virtual-edge statistics (e.g. “X virtual merchants, Y edges, top countries by edge count”);
* any critical WARN-level conditions that might not block S2 but should be visible to operators (e.g. unusual edge skew, edges concentrated in few countries beyond configured expectations if that is allowed as WARN).

10.5.4 The 3B validation state MUST be able to use S2’s observability information (metrics, run-report record, RNG logs) to:

* cross-check RNG accounting vs edge counts;
* verify index/cat alignment (counts and digests);
* build any higher-level “edge universe hash” surfaces without ambiguity.

---

10.6 **Operational diagnostics & debugability**

10.6.1 On any FATAL S2 failure, S2 SHOULD log **diagnostic details** sufficient for root-cause analysis without immediate use of a debugger. Examples:

* For **budget failures**:

  * sample `merchant_id`(s) affected;
  * `class(m)`, `E_nominal(m)`, `E_clipped(m)`;
  * relevant country weights `s_m(c)` and any floor/cap that made the budget unsatisfiable.

* For **tile or spatial failures**:

  * `country_iso`, `tile_id`;
  * `E_m(c)`, `E_m(c,t)`;
  * indication whether tiling surface is missing, empty, or has bad weights.

* For **jitter failures** (`JITTER_MAX_ATTEMPTS` exhausted):

  * `merchant_id`, `country_iso`, `tile_id`;
  * number of attempts;
  * summary of why candidates failed (e.g. “outside tile”, “outside country polygon”).

* For **tz failures**:

  * `merchant_id`, `edge_id` (or coordinate);
  * `(edge_latitude_deg, edge_longitude_deg)`;
  * brief description (e.g. “no tz polygon match”, “tzid not in tzdb index”).

10.6.2 If the engine supports a **debug / dry-run mode** for S2, then:

* S2 MUST run the full deterministic algorithm through Phases A–F, including RNG usage and validation,
* but MUST NOT publish `edge_catalogue_3B` and `edge_catalogue_index_3B` to their canonical locations.

In this mode, S2 MUST:

* log `mode = "dry_run"` vs `mode = "normal"` in lifecycle events and run-report;
* ensure that RNG and edge placement remain deterministic (identical between dry-run and normal-run with the same inputs, aside from the absence of persisted datasets).

10.6.3 Additional observability enhancements (e.g. per-country coverage reports, sampled edge dumps for a subset of merchants) MAY be implemented as long as they:

* use separate, clearly documented diagnostic datasets or log streams,
* do not alter any binding dataset schemas, paths or partitioning,
* do not introduce non-determinism into S2’s core behaviour.

10.6.4 Where this section appears to conflict with actual schemas or dataset dictionary entries, **schemas and catalogues are authoritative**. In such cases, this section MUST be brought up to date in the next non-editorial revision so that observability and data contracts remain aligned.

---

## 11. Performance & scalability *(Informative)*

11.1 **Workload character**

11.1.1 3B.S2 is **edge-centric** and primarily CPU + RNG + spatial I/O bound:

* It visits each **virtual merchant** once for budget computation.
* It visits each **(merchant, country, tile)** combination implied by those budgets.
* It generates and writes **one row per edge node** into `edge_catalogue_3B`, plus a compact index in `edge_catalogue_index_3B`.

11.1.2 Unlike high-volume transaction states, S2 does not handle per-event streams; its scale is dominated by:

* number of virtual merchants `|V|`, and
* total number of edges `E_total = Σ₍m∈V₎ E_clipped(m)`.

---

11.2 **Complexity & expected scale**

11.2.1 Let:

* `|V|` = number of virtual merchants;
* `|C_m|` = number of eligible countries per merchant (typically bounded by global country set size `|C|`);
* `T_c` = tile set for country `c`;
* `E_clipped(m)` = total edges allocated to merchant `m`;
* `E_total = Σ₍m∈V₎ E_clipped(m)` = total edges in the catalogue.

Then, asymptotically:

* **Budget computation (Phase B)**

  * `O(|V| · |C|)` in the worst case (per-merchant country mix), typically much lower if `C_m` is sparse.
* **Tile allocation (Phase C)**

  * `O(Σ₍m∈V₎ Σ₍c∈C_m₎ |T_c|)` — but for realistic tilings, `|T_c|` per country is bounded and can be indexed/filterable.
* **Edge placement (Phase D)**

  * `O(E_total)` RNG draws and coordinate constructions (plus bounded resampling), dominated by the number of edges.

11.2.2 For practical deployments:

* `|V|` is usually in the range 10²–10⁵;
* `E_clipped(m)` is typically O(10²–10³) per merchant;
* `E_total` is thus O(10⁴–10⁷), depending on configuration.

The cost of S2 grows roughly linearly with `E_total` plus a smaller overhead from budgets and tile allocation.

---

11.3 **Latency considerations**

11.3.1 Critical latency factors:

* Reading S1 outputs (`virtual_classification_3B`, `virtual_settlement_3B`) and spatial surfaces.
* Walking all virtual merchants and computing budgets.
* Rolling through all edges and performing jitter + tz resolution.
* Writing `edge_catalogue_3B` (O(`E_total` rows)) and `edge_catalogue_index_3B` (O(`|V|` rows plus a small number of global rows)).

11.3.2 In typical environments:

* Tile lookup and jitter are cheap per edge;
* tz resolution is slightly more expensive (polygon lookups) but still linear and local per edge;
* the main cost is simply **how many edges you choose to create**.

11.3.3 If S2 becomes slow, likely causes include:

* overly large `E_clipped(m)` values (e.g. “thousands of edges per merchant” across many merchants);
* slow object-store or filesystem performance for reading large spatial assets;
* inefficient implementation of budget or tile allocation (e.g. repeated scanning over large tile sets).

Mitigations typically involve:

* tuning edge budgets downward (reduce `E_clipped(m)`);
* caching spatial index structures (e.g. country→tiles maps) across manifests;
* co-locating S2 compute with storage to minimise I/O latency.

---

11.4 **Memory model & parallelism**

11.4.1 A straightforward implementation that:

* streams the virtual merchant list;
* loads CDN policies and tiling surfaces once;
* holds temporary per-merchant edges in memory until write,

will keep memory usage roughly proportional to the maximum number of edges buffered at once.

11.4.2 For very large `E_total`, recommended patterns:

* **Streaming edge writes**:

  * generate edges in merchant-sorted order and write them incrementally to `edge_catalogue_3B`;
  * build per-merchant counts and digests incrementally, then write `edge_catalogue_index_3B` from those summaries.

* **Batching**:

  * process merchants in batches (size chosen to fit memory),
  * flush batches of edges to disk while retaining only per-merchant counters/digests in memory.

11.4.3 Parallelism:

* S2 is naturally parallelisable over merchants and/or countries.
* Any parallel implementation MUST preserve determinism by:

  * using deterministic partitioning of work (e.g. assign merchants to workers by sorted blocks),
  * enforcing a canonical order when combining partial outputs, and
  * ensuring RNG streams and counters are allocated in a way that is independent of thread scheduling (e.g. keyed streams per `(merchant, tile)` rather than shared streams across threads).

---

11.5 **I/O patterns**

11.5.1 Typical I/O for S2:

* **Reads**:

  * S1 outputs: modest, merchant-level tables;
  * CDN policies: small config files;
  * spatial surfaces: tile index & weights, rasters, polygons (these can be MB–GB scale depending on resolution);
  * tz assets: tz-world polygons and tzdb index (typically moderate size, reused from 2A).

* **Writes**:

  * `edge_catalogue_3B`: O(`E_total`) rows, columnar writes;
  * `edge_catalogue_index_3B`: O(`|V|`) rows;
  * RNG logs: `O(E_total)` RNG events, but these are shared Layer-1 log streams, not 3B-specific datasets.

11.5.2 As a result:

* S2 is usually read-heavy for spatial assets (one-time load per process) and write-heavy for `edge_catalogue_3B`;
* performance is best when spatial assets and outputs are stored on fast, locally accessible storage or in a low-latency object-store.

---

11.6 **SLOs & tuning levers**

11.6.1 Operators may define high-level SLOs such as:

* `P95(3b_s2_duration_seconds) < T` for a chosen `T` (e.g. 30–120 seconds), conditional on a reference scale of `|V|` and `E_total`;
* constraints on edge density, e.g. `max(edges_per_virtual_merchant)` or skew thresholds for `edges_per_merchant` histograms.

11.6.2 Tuning levers include:

* adjusting **per-merchant budget policies** (`E_total(class)`, min/max edges) to control `E_total`,
* limiting **country sets** (e.g. excluding very low-weight countries from allocation) where allowed by the policy,
* coarsening **tiling resolution** (fewer tiles per country) at the cost of spatial granularity,
* applying **sampling or downscaling** in development environments while keeping full budgets for production.

11.6.3 Any tuning must still respect:

* policy semantics encoded in sealed configs;
* RNG and determinism guarantees;
* invariants specified in §§6–8.

---

11.7 **Testing & performance regressions**

11.7.1 Performance/regression tests for S2 SHOULD include:

* configurations at or above the largest expected `|V|` and `E_total` for production;
* tests with dense country mixes (many `C_m`) and complex tiles to exercise integerisation and jitter logic;
* tests with “pathological” but valid inputs (e.g. edge budgets that are just at min/max, extremely skewed country weights) to ensure the integerisation and jitter remain efficient.

11.7.2 Tests SHOULD verify that:

* runtime and memory use scale roughly linearly in `E_total` for fixed spatial resolution;
* adding a small number of new virtual merchants or modestly raising budgets yields correspondingly modest increases in runtime;
* reruns with identical inputs produce identical outputs (edge catalogue, index, digests, RNG logs).

11.7.3 As this section is informative, specific numeric thresholds (e.g. acceptable `P95` latencies) are environment-dependent. The binding requirements remain:

* S2 MUST be deterministic,
* MUST respect input and RNG contracts,
* MUST not become a hidden bottleneck due to unbounded edge or tile complexity without explicit, governed configuration decisions.

---

## 12. Change control & compatibility *(Binding)*

12.1 **Scope of change control**

12.1.1 This section governs all changes that affect **3B.S2 — CDN edge catalogue construction** and its artefacts, specifically:

* The **behaviour** of S2 (edge budgets, country and tile allocation, jitter, tz resolution, edge identity, edge weights).
* The **schemas and catalogue entries** for S2-owned datasets:

  * `edge_catalogue_3B`
  * `edge_catalogue_index_3B`
  * any explicitly defined S2 planning surfaces (e.g. `edge_tile_plan_3B`) if/when they are made persistent.
* Any S2-specific use of:

  * CDN edge-budget policy schemas (e.g. `cdn_country_weights`),
  * spatial surface schemas used by S2 (if 3B-specific),
  * RNG policy entries and RNG event schemas used by S2 for edge placement.

12.1.2 It does **not** govern:

* S0 contracts (`s0_gate_receipt_3B`, `sealed_inputs_3B`), which have their own change-control rules.
* S1 contracts (`virtual_classification_3B`, `virtual_settlement_3B`), except where S2 depends on their keys and semantics.
* Upstream segment contracts and artefacts for 1A, 1B, 2A, 3A (merchant reference, tiles, rasters, tz assets, zone allocation, etc.), which are owned by those segments.
* The 3B segment-level validation bundle and `_passed.flag`, which are owned by the terminal 3B validation state.
* S3 contracts (edge alias & universe hash) except where S2 must remain consumable by S3.

---

12.2 **Versioning of S2-related contracts**

12.2.1 All 3B contracts that affect S2 MUST be versioned explicitly across:

* `schemas.3B.yaml` — defining shapes for `edge_catalogue_3B`, `edge_catalogue_index_3B`, and any S2-specific RNG events or planning surfaces;
* `dataset_dictionary.layer1.3B.yaml` — defining dataset IDs, `schema_ref`, `path_template`, `partition_keys`, and `writer_sort` for S2 outputs (and any S2 intermediates that are persisted);
* `artefact_registry_3B.yaml` — defining manifest keys, owners, licence, retention, and known consumers for S2 datasets.

12.2.2 CDN edge-budget and spatial policy schemas that S2 consumes MUST also be versioned, for example:

* `schemas.3B.yaml#/policy/cdn_country_weights`,
* `schemas.3B.yaml#/spatial/virtual_tile_surface` (if 3B defines its own tiling),
* RNG policy schemas that define S2-specific streams.

12.2.3 Implementations SHOULD follow a semantic-style scheme:

* **MAJOR** — incompatible/breaking changes to shapes, keys, partition law, RNG usage, or core semantics (e.g. redefining `edge_weight`, changing how many edges a merchant gets for the same manifest).
* **MINOR** — backwards-compatible extensions (e.g. new optional fields or diagnostics, additional enum values that old consumers can safely ignore).
* **PATCH** — non-semantic fixes (typos, documentation clarifications, tightening validation for cases that were already invalid).

12.2.4 S2 MUST ensure (directly or via `s0_gate_receipt_3B.catalogue_versions`) that the versions of:

* `schemas.3B.yaml`
* `dataset_dictionary.layer1.3B.yaml`
* `artefact_registry_3B.yaml`

form a **compatible triplet** for the S2 implementation (e.g. same MAJOR version, or explicit compatibility matrix).

If they do not, S2 MUST fail with `E3B_S2_SCHEMA_PACK_MISMATCH` (or equivalent) and MUST NOT write outputs.

---

12.3 **Backwards-compatible vs breaking changes**

12.3.1 The following are considered **backwards-compatible** (MINOR or PATCH) changes for S2, provided they preserve all binding guarantees in §§4–9:

* Adding **optional columns** to `edge_catalogue_3B` or `edge_catalogue_index_3B` (e.g. `tile_id`, `coord_source_id`, `created_utc`, additional diagnostics), as long as:

  * existing required fields are unchanged;
  * new fields have clearly defined default semantics when absent (e.g. “unknown / not recorded”).

* Extending **enumerations** with new values where:

  * existing enum values retain their semantics;
  * consumers that do not understand the new values can safely treat them as “other” without mis-routing or miscounting (e.g. a new `tz_source` value).

* Introducing **new optional policy artefacts** or spatial surfaces that S2 can use when present (e.g. additional merchant tiers, special-region overrides), provided:

  * behaviour when they are absent is well-defined and compatible with previous semantics.

* Tightening **validation checks** that reject only configurations that were already invalid or unspecified (e.g. enforcing non-negative weights, stricter tzid conformity).

12.3.2 The following are **breaking** (MAJOR) changes for S2:

* Removing or renaming any **required field** in `edge_catalogue_3B` or `edge_catalogue_index_3B`.

* Changing the **type or semantics** of required fields, for example:

  * redefining `edge_weight` from “per-merchant normalised weight” to “raw traffic count” without a separate field;
  * changing `country_iso` domain (e.g. from ISO3 to ISO2) without preserving a compatible representation.

* Changing `path_template`, `partition_keys` or `writer_sort` for S2 outputs in the dataset dictionary.

* Changing the **primary keys** or join keys (e.g. moving from `merchant_id` to a different identifier without preserving the original key).

* Changing S2’s **edge identity law** such that `edge_id` is no longer a pure, deterministic function of the defined inputs (merchant key + edge index + namespace), or such that existing edge IDs are no longer reproducible under the same manifest.

* Changing the **edge-budget semantics** so that, for unchanged inputs and policies, the set of edges `E_m` for merchant `m` would change (e.g. new default per-class budgets or country eligibility) without bumping MAJOR and clearly documenting the behavioural shift.

* Changing the **RNG event families or stream mappings** in a way that breaks compatibility with existing RNG audit/trace logs (e.g. switching S2 to a different RNG stream or substream label, or changing draw counts per edge event).

12.3.3 Any breaking change MUST:

* bump the MAJOR version of `schemas.3B.yaml`;
* be accompanied by coordinated updates to `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml`;
* be documented in a 3B/3B.S2 change log, with explicit description of how S2 behaviour differs and what migration is required.

---

12.4 **Mixed-version environments**

12.4.1 A **mixed-version** environment arises when:

* historic S2 outputs (`edge_catalogue_3B`, `edge_catalogue_index_3B`) exist on disk that conform to an **older** 3B schema/dictionary version, and
* the engine and contracts currently loaded for 3B use a **newer** version.

12.4.2 S2 is responsible only for **writing** outputs for the **current** version. It MUST:

* write new S2 outputs using the current schema/dictionary/registry;
* not silently rewrite, upgrade or reinterpret historical S2 outputs created under an older MAJOR version.

12.4.3 Reading historical S2 outputs produced under older schema versions is the responsibility of:

* offline analysis or reporting tools,
* explicit migration utilities, or
* a version-aware validation harness.

S2 MUST NOT silently treat old outputs as if they match the new schema.

12.4.4 If S2 is invoked for a `{seed, parameter_hash, manifest_fingerprint}` where S2 outputs already exist but:

* those outputs do not validate against the **current** schemas, or
* recomputed outputs differ from existing outputs,

S2 MUST:

* treat this as an environment / manifest inconsistency;
* fail with `E3B_S2_OUTPUT_INCONSISTENT_REWRITE` (or equivalent);
* not overwrite the existing datasets.

Operators MUST then:

* either preserve the old outputs as belonging to their older contract version and refrain from re-running S2 under the same fingerprint, or
* explicitly migrate and re-emit S2 outputs under a **new** manifest and/or schema version.

---

12.5 **Migration & deprecation**

12.5.1 Introducing a new field or behaviour intended to become **mandatory** in S2 SHOULD follow a two-step pattern:

1. **MINOR**: add the field/behaviour as optional:

   * update `schemas.3B.yaml` to declare the new field as optional;
   * update S2 to populate it when possible;
   * update downstream consumers to prefer the new field when present.

2. **MAJOR** (after adoption): promote to required:

   * mark the field as required in the schema;
   * remove reliance on legacy behaviour in S2 and downstream states.

12.5.2 Deprecating existing fields or artefacts used by S2 SHOULD also be done in two steps:

* Step 1 (MINOR): mark the field/artefact as deprecated in documentation/schema annotations; ensure S2 and downstream consumers can operate without it (e.g. by switching to newer fields).
* Step 2 (MAJOR): remove or repurpose the field/artefact only after consumers no longer depend on it.

12.5.3 For edge-budget and spatial policies:

* Deprecating a legacy `cdn_country_weights` pack or tile surface SHOULD involve:

  * introducing a new policy/surface artefact;
  * updating S0 to seal, and S2 to consume, the new artefact;
  * ensuring S2 behaviour is defined when only the new artefact is present.
* Only after S2 fully relies on the new artefact SHOULD the old one be dropped from `sealed_inputs_3B` and S2’s logic, typically as part of a MAJOR bump.

12.5.4 If new **variants** of S2’s behaviour are needed (e.g. alternative tiling strategies or budget regimes), they SHOULD be expressed as:

* configuration modes and/or new policy packs under the same S2 framework,
* with clear semantics and versioned contracts,

rather than as silent changes to the meaning of existing policies.

---

12.6 **Compatibility with upstream segments & other 3B states**

12.6.1 Changes to S2 MUST remain compatible with **upstream authority boundaries**:

* S2 cannot redefine what `merchant_id`, `country_iso`, `tile_id`, or `tzid` mean; their semantics are governed by ingress/1A/1B/2A.
* S2 cannot change the contract of `virtual_classification_3B` or `virtual_settlement_3B`; classification and settlement semantics remain owned by S1.

12.6.2 If upstream segments change:

* validation bundle laws;
* dataset schemas relevant to S2 (e.g. 1B’s `tile_index` / `tile_weights` or 2A’s tz assets);
* identification of merchants or countries,

the 3B contracts and S2 spec MUST be updated. S2 MUST:

* adapt its use of upstream inputs while respecting new schema definitions;
* ensure that any such changes are either behaviour-preserving for existing manifests (MINOR/PATCH) or signalled via MAJOR version bumps and a new manifest when they are not.

12.6.3 S2 MUST remain compatible with **3B.S3** and the 3B validation state:

* S3 relies on `edge_catalogue_3B` and `edge_catalogue_index_3B` being present, stable, and correctly shaped;
* S2 changes that alter key structure, weights, or digest semantics MUST be coordinated with S3’s alias/universe-hash logic and with the 3B validation state.

12.6.4 If changes to other 3B states (e.g. new alias-table layout in S3) require different edge-level metadata (e.g. additional fields in `edge_catalogue_3B`), the preferred order is:

1. Add new optional fields in S2 outputs;
2. Update S3/validation to use them;
3. Only later, if needed, make them required in a MAJOR version.

---

12.7 **Change documentation & review**

12.7.1 Any non-trivial change to S2 behaviour, schemas or catalogues MUST be:

* recorded in a human-readable change log (e.g. `CHANGELOG.3B.S2.md` or `CHANGELOG.3B.md` with S2-specific entries);
* associated with specific schema/dictionary/registry version increments;
* accompanied by migration guidance (e.g. required manifest or configuration changes, expected impact on edge counts or distributions).

12.7.2 Before deploying S2-impacting changes, implementers SHOULD:

* run regression tests on representative and worst-case manifests to verify:

  * deterministic behaviour is preserved;
  * S2 still satisfies all acceptance criteria in §8;
  * downstream 3B states (S3, validation) and any 2B virtual routing components continue to function correctly.

* explicitly test **idempotence**:

  * re-run S2 under the same `{seed, parameter_hash, manifest_fingerprint}` and confirm that outputs, counts, digests and RNG logs are unchanged (or that any changes are intentional and accompanied by a new manifest/schema version).

12.7.3 Where this section conflicts with `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` or `artefact_registry_3B.yaml`, those artefacts SHALL be treated as **authoritative**. This section MUST be updated in the next non-editorial revision to reflect the contracts actually in force.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

> This appendix is descriptive only. If anything here conflicts with a Binding section or with JSON-Schema / dictionary / registry entries, those authoritative sources win.

---

### 13.1 Identity & governance

* **`seed`**
  Layer-1 Philox seed for the run. Shared across segments for a given manifest. Part of S2’s run identity triple.

* **`parameter_hash`**
  Tuple-hash over the governed 3B parameter set (including S2-related config such as feature flags, budget regimes). Logical identity input; not a partition key for S2 outputs.

* **`manifest_fingerprint`**
  Hash of the full Layer-1 manifest (ingress assets, policies, code, artefacts). Primary partition key (with `seed`) for S2 outputs.

* **`run_id`**
  Optional, opaque identifier for a concrete execution of S2 under a given `{seed, parameter_hash, manifest_fingerprint}`. Used for logs / run-report only; never affects behaviour.

---

### 13.2 Sets & per-merchant notation

* **`M`**
  Merchant universe (from upstream). S2 itself doesn’t re-define `M`, but uses the virtual subset `V`.

* **`V`**
  Virtual merchant set for 3B; derived from S1’s classification surface, e.g.:
  `V = { m | virtual_classification_3B(m).is_virtual = 1 }`.

* **`C`**
  Global set of countries considered by the CDN country-weight policy (domain of `cdn_country_weights`).

* **`C_m`**
  Subset of countries for merchant `m ∈ V` that are allowed by policy and have positive weight:
  `C_m ⊆ C`.

* **`T_c`**
  Set of tiles in country `c`, as defined by 1B/3B tiling surfaces (`tile_index` / `tile_weights`).

* **`E_m` / `E_m(c)` / `E_m(c,t)`**

  * `E_clipped(m)` — total edges assigned to merchant `m`.
  * `E_m(c)` — integer edge count assigned to merchant `m` in country `c`.
  * `E_m(c,t)` — integer edge count assigned to merchant `m` in tile `t` of country `c`.
  * `E_total = Σ₍m∈V₎ E_clipped(m)` — total edges in the S2 edge universe.

* **`E_m` (set notation)**
  The set of edge nodes for merchant `m`, e.g. `E_m = { e | edge row with merchant_id = m }`.

---

### 13.3 Policy & weight notation

* **`w_global(c)`**
  Global country weight from the CDN policy for country `c ∈ C`.

* **`w_class(class, c)`**
  Optional class-level weight for a merchant class (e.g. SMALL/MEDIUM/LARGE) and country `c`.

* **`class(m)`**
  Merchant class (tier) assigned to merchant `m ∈ V` according to the CDN policy.

* **`E_total(class)`**
  Nominal total edges per merchant for a given class (before clipping to min/max).

* **`s_m(c)`**
  Normalised country share for merchant `m` in country `c` (after applying overrides and normalising over `C_m`).

* **`w_tile(c,t)` / `p_tile(c,t)`**

  * `w_tile(c,t)` — raw tile weight for tile `t` in country `c` (from `tile_weights` or equivalent).
  * `p_tile(c,t)` — normalised tile share over all `t ∈ T_c`.

---

### 13.4 Tile, jitter & RNG notation

* **`T_c`**
  (Repeated) Tile set for country `c`.

* **`JITTER_MAX_ATTEMPTS`**
  Policy-configured maximum number of jitter attempts allowed when trying to place an edge inside a tile/country before failing.

* **`u_lon`, `u_lat`**
  Uniform random variates in (0,1) generated from Philox, used to jitter within tile bounds for longitude and latitude.

* **`rng_stream_id`**
  Identifier for an RNG stream, as defined by the layer RNG policy (e.g. keyed by `"3B.S2"` plus substream label). Encoded in RNG envelopes.

* **`substream_label`**
  Label distinguishing logical RNG uses (e.g. `"edge_jitter"` vs `"edge_tile_assign"`).

* **`rng_event_edge_jitter`**, **`rng_event_edge_tile_assign`**
  Illustrative names for S2 RNG event families used to record jitter attempts and any tile-level randomisation, conforming to the layer RNG envelope schema.

---

### 13.5 Edge catalogue notation

* **`edge_catalogue_3B`**
  S2 egress. One row per CDN edge node, including `merchant_id`, `edge_id`, `country_iso`, coordinates, `tzid_operational`, `edge_weight`, and provenance.

* **`edge_catalogue_index_3B`**
  S2 egress. Per-merchant and global index/digest surface summarising edge counts and digests for `edge_catalogue_3B`.

* **`edge_id`**
  Deterministic identifier for an edge node, typically derived from a hash of `(merchant_id, edge_seq_index, "3B.EDGE")`. Unique per `(seed, fingerprint)`.

* **`edge_weight`**
  Per-edge weight used for alias-table construction and apparent traffic mix. Usually normalised per merchant so that Σ₍e∈E_m₎ `edge_weight(e)` follows a declared law (e.g. = 1 or = fixed integer grid).

* **`edge_seq_index`**
  Deterministic sequence index for an edge within merchant `m` (e.g. its position in a sorted list of edges), used as part of `edge_id` construction.

* **`edge_catalogue_digest_merchant`**
  Digest (e.g. SHA-256 hex) over all edge rows for a given merchant in `edge_catalogue_3B`, computed in a canonical order.

* **`edge_catalogue_digest_global`**
  Digest over the entire `edge_catalogue_3B` partition, used (with other components) in virtual edge universe hashing.

---

### 13.6 Timezone & spatial notation

* **`tzid_operational`**
  IANA timezone identifier for the operational location of an edge node (customer-facing world). Derived from tz-world/tzdb or an ingested field.

* **`tz_source`**
  Enum describing how `tzid_operational` was obtained, e.g.:

  * `"POLYGON"` — from tz polygons + tzdb;
  * `"OVERRIDE"` — tz override changed the polygon result;
  * `"INGESTED"` — tzid taken from an upstream artefact.

* **`edge_latitude_deg`, `edge_longitude_deg`**
  WGS84 latitude and longitude in degrees for the edge location.

* **`country_iso`**
  Country attribution for the edge node (ISO code), consistent with the CDN country-weight domain and world-country polygons.

---

### 13.7 Error & status codes (S2)

* **`E3B_S2_*`**
  Namespace for 3B.S2 canonical error codes, e.g.:

  * `E3B_S2_REQUIRED_INPUT_NOT_SEALED`
  * `E3B_S2_BUDGET_COUNTRY_WEIGHTS_INVALID`
  * `E3B_S2_TILE_SURFACE_INVALID`
  * `E3B_S2_EDGE_OUTSIDE_COUNTRY`
  * `E3B_S2_JITTER_RESAMPLE_EXHAUSTED`
  * `E3B_S2_TZ_RESOLUTION_FAILED`
  * `E3B_S2_EDGE_CATALOGUE_SCHEMA_VIOLATION`
  * `E3B_S2_RNG_POLICY_VIOLATION`
    and others defined in §9.

* **`status ∈ {"PASS","FAIL"}`**
  Run-level status for S2, as recorded in S2 logs and run-report.

* **`severity ∈ {"FATAL","WARN"}`**
  Error severity associated with `E3B_S2_*` codes.

---

### 13.8 Miscellaneous abbreviations

* **CDN** — Content Delivery Network. In this context: logical edge-node network for virtual merchants.
* **HRSL** — High Resolution Settlement Layer (or similar population raster).
* **FK** — Foreign key (join key across datasets).
* **IO** — Input/Output (filesystem / object-store operations).
* **RNG** — Random Number Generator (Philox2x64-10 across Layer-1).
* **SLO** — Service Level Objective (latency / reliability target; informative).

---

13.9 **Cross-reference**

For authoritative definitions of shapes and contracts referenced here:

* Layer-wide: `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`.
* Upstream segments: `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml` and their dictionaries/registries (tiles, tz assets, zone allocation).
* This subsegment: `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, `artefact_registry_3B.yaml`.

This appendix is a vocabulary aide for reading and implementing **3B.S2 — CDN edge catalogue construction**; it does not introduce additional normative requirements.

---
