# 1B · S1 — Tile Index — Technical Specification

# 0. Document metadata & status *(Binding)*

**Document ID:** `state.1B.s1.expanded.txt`
**Title:** Layer 1 · Subsegment 1B · **S1 — Tile Index (eligible cells per country)**
**Layer/Subsegment/State:** Layer 1 / 1B / S1
**Status:** **Draft** → targets **Alpha** on ratification
**Owners (roles):** Layer 1 (1B) Spec Author · Layer 1 (1B) Spec Reviewer · Program Governance Approver
**Last updated (UTC):** 2025-10-18
**Normative keywords:** **MUST, MUST NOT, SHALL, SHALL NOT, SHOULD, SHOULD NOT, MAY** are to be interpreted as binding requirements for this state.
**Audience:** Implementation agents and reviewers; non-binding notes are clearly marked as *Informative*.

## 0.1 Scope of this document *(Binding)*

This specification defines the **behavioural contract** and **data contract** for **S1 — Tile Index**. It enumerates, deterministically and without RNG, the set of **eligible population-raster cells per ISO country** into the dataset **`tile_index`**. It does **not** define implementation or pseudocode; it binds **inputs, outputs, invariants, prohibitions, validation, and non-functional envelopes** for S1.

## 0.2 Authority set and anchors *(Binding)*

* **Schema (shape authority):** `schemas.1B.yaml#/prep/tile_index`
* **Dictionary (ID→path/partition law):** `dataset_dictionary.layer1.1B.yaml#tile_index`
* **Ingress (sealed inputs referenced by this state):**
  `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` · `#/world_countries` · `#/population_raster_2025`
  JSON-Schema is the **sole** shape authority. Avro/Parquet encodings are non-authoritative.

## 0.3 Precedence chain (tie-break) *(Binding)*

When obligations appear to conflict, S1 SHALL apply this order:

1. **JSON-Schema** (shape/domains/keys).
2. **Dataset Dictionary** (ID→`$ref`, paths, partitions, writer sort, licence/retention/PII text).
3. **Artefact Registry** (licence/provenance and gate artefact bindings).
4. **This S1 spec** (behavioural rules, prohibitions, validations) under (1)–(3).

Schema outweighs Dictionary on shape; Dictionary outweighs any literal path; implementations **MUST NOT** hard-code paths (resolve via Dictionary). *(Same precedence model as S0.)*

## 0.4 Compatibility window *(Binding)*

This document is compatible with and assumes:

* **S0 (1B) state spec:** `state.1B.s0.expanded.txt` (for layer-wide posture and gate language; S1 itself consumes **no** 1A egress).
* **Layer-wide schemas:** current `schemas.layer1.yaml` family as frozen for Layer 1.
* **1B schema & dictionary:** `schemas.1B.yaml` and `dataset_dictionary.layer1.1B.yaml`.
  If any of the above advance in a way that changes `tile_id` definition, partition keys, or column set for `tile_index`, that is a **MAJOR** compatibility event for S1 (see §13).

## 0.5 Identity, partitioning, and determinism posture *(Binding)*

* **RNG usage:** **None** in S1.
* **Determinism:** For a fixed set of sealed inputs and `parameter_hash`, S1 outputs are **byte-identical** across reruns.
* **Partitioning:** `tile_index` partitions by `[parameter_hash]` with primary key `[country_iso, tile_id]` and stable sort `[country_iso, tile_id]`.
* **Path↔embed:** If any embedded keys mirror path tokens, they **MUST** equal those tokens (explicit rules are stated where applicable in later sections).

## 0.6 Non-functional envelope pointers *(Binding)*

This document binds **performance and operational** constraints in §11 and makes their **acceptance tests** part of validity in §8.9. Implementations that satisfy shape but violate the §11 envelope **fail** S1.

## 0.7 Change control & semver for this document *(Binding)*

* **MAJOR**: changes to `tile_id` semantics or formula; default of `inclusion_rule`; partition keys; required columns; CRS or numeric policy that can alter results.
* **MINOR**: addition of optional columns/metrics; tightening of validation bounds without changing valid results.
* **PATCH**: editorial clarifications; non-binding examples; errata that do not change the contract.
  SemVer for this document advances only by these rules; state behaviour follows the highest-precedence authority per §2.

## 0.8 Approvals and ratification *(Binding)*

* **To ratify Alpha:** all **Binding** sections complete; §7 dataset shape anchored; §8 validation and §11 performance thresholds populated; governance sign-off recorded here (name + date).
* **To ratify Stable:** evidence of §8/§11 acceptance on reference inputs attached; no outstanding *Informative-only* gaps affecting behaviour.

---

# 1. Purpose & scope *(Binding)*

## 1.1 Purpose *(Binding)*

This state defines the **deterministic enumeration of eligible population-raster cells per ISO country** into the dataset **`tile_index`**. Given the sealed reference surfaces named in §2 (ISO codes, country polygons, population raster), S1 **MUST** produce, for every eligible cell, a single row keyed by `(country_iso, tile_id)` and partitioned by `parameter_hash`. S1 is **RNG-free** and is concerned only with **eligibility and geometry**, not weighting or sampling. The normative rules for eligibility, tile identity, coordinates and area are specified in §6; the dataset shape is owned by the schema anchor in §2.

## 1.2 Non-goals *(Binding)*

S1 explicitly **does not**:

* read or depend on **1A egress** (S0’s PASS gate remains documented context only);
* compute spatial **weights**, **footfall**, or any stochastic selection;
* perform **timezone** legality checks or assignment;
* alter or repair input geometry beyond what §6 requires (no reprojection policy changes, no topology healing outside the stated tolerances);
* emit any outputs other than **`tile_index`** and its required audits/metrics (see §9), nor write to paths outside the Dictionary law.

## 1.3 Success criteria *(Binding)*

S1 is “valid & done” when **all** of the following hold:

* **Shape & anchors:** the emitted dataset complies with **`schemas.1B.yaml#/prep/tile_index`** and is written at the **Dictionary-governed** path for `tile_index` with partitions and sort keys as declared (see §2, §7).
* **Determinism & idempotence:** for the same sealed inputs and `parameter_hash`, reruns are **byte-identical**.
* **Integrity:** `(country_iso, tile_id)` is unique; `country_iso` **MUST** exist in the ISO surface; coordinates are within legal bounds; `pixel_area_m2` is strictly positive; per-country row counts equal the eligibility predicate’s result (see §8).
* **Prohibitions respected:** no reads of 1A egress; no stochastic behaviour; no writes outside the declared partitions (see §6, §7).
* **Operational envelope:** the performance, memory and I/O thresholds defined in §11 are met; corresponding **Performance Acceptance Tests** in §8.9 pass.

---

# 2. Sources of authority & precedence *(Binding)*

## 2.1 Authority set (normative anchors)

**JSON-Schema is the sole source of truth for shape, columns, domains, PK/UK/FK and partition keys.** The binding anchors for S1 are:

* **S1 output shape:** `schemas.1B.yaml#/prep/tile_index`. 
* **Dictionary law (ID → path/partitions/sort):** `dataset_dictionary.layer1.1B.yaml#tile_index` (partitions `[parameter_hash]`, sort `[country_iso, tile_id]`). 
* **Ingress / FK targets (sealed inputs):**
  `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` · `#/world_countries` · `#/population_raster_2025`. (Declared for 1B in the Dictionary.) 
* **Gate context (read-only, for 1A consumers):** `schemas.1A.yaml#/validation/validation_bundle` (Dictionary entry provided for discoverability; S1 itself does **not** read 1A egress). 

## 2.2 What each authority governs

* **JSON-Schema (above anchors):** row/field shapes, PK/partition keys, constraints. 
* **Dataset Dictionary:** dataset IDs, canonical paths, partitions, ordering, retention/licensing summaries for S1 surfaces and sealed inputs. 
* **Artefact Registry (read-only for S1):** licences, provenance and identity for sealed references (`iso3166_canonical_2024`, `world_countries`, `population_raster_2025`, `tz_world_2025a`). 

## 2.3 Precedence chain (tie-break)

When obligations appear to conflict, S1 SHALL apply this order:

1. **JSON-Schema** (shape/domain/keys).
2. **Dataset Dictionary** (ID→path/partition/order law).
3. **Artefact Registry** (licence/provenance/identity of sealed inputs).
4. **This state specification (S1)** (behavioural rules, prohibitions, validations).

## 2.4 Gate & order-authority boundaries (for coherence)

* **S1 does not read 1A egress**; therefore S0’s PASS gate is **not** a precondition to execute S1. The Dictionary includes the 1A validation bundle anchor only for discoverability. 
* **Inter-country order is never encoded by S1.** Across 1B, the only order authority is 1A’s **S3 `candidate_set.candidate_rank`** (not consumed in S1, noted here to prevent leakage). 

## 2.5 Anchor-resolution rule (normative)

All dataset and field references in this document MUST be resolved first via the **JSON-Schema anchors** above; the Dictionary and Registry MUST NOT be treated as shape authorities. (Avro/Parquet encodings, if present, are non-authoritative.) 

---

# 3. Identity, determinism & partitions *(Binding)*

## 3.1 Identity tokens & scope

* **Identity for S1 outputs:** `parameter_hash` **only**. S1 emits no `seed`- or `fingerprint`-partitioned artefacts. This follows the Dictionary entry for `tile_index` (partitioning `[parameter_hash]`, version `{parameter_hash}`). 
* **No RNG in S1:** S1 is deterministic geometry; it inherits the layer lineage discipline (identity by partitions; publish is atomic; file order non-authoritative) from S0’s law. 

## 3.2 Partition law for `tile_index`

* **Partition path (Dictionary-owned):** `data/layer1/1B/tile_index/parameter_hash={parameter_hash}/`. Writer **MUST** publish only under this partition for a given run. 
* **Sort discipline (for merges):** writer sort is `[country_iso, tile_id]` to guarantee stable, deterministic merges across workers. 

## 3.3 Keys & uniqueness

* **Primary key:** `[country_iso, tile_id]` (schema authority). All rows **MUST** satisfy PK uniqueness within a partition. 
* **File order:** never authoritative; identity is **(partition keys + PK/UK)** only (layer rule). 

## 3.4 Determinism (no RNG) & re-run identity

* **Re-run idempotence:** Given identical sealed inputs (ISO, country polygons, population raster) and the same `parameter_hash`, the emitted `tile_index` **MUST** be byte-identical across re-runs. 
* **Scope of identity:** `tile_index`’s identity is its `{parameter_hash}` partition; publishing a second, non-identical result to the same partition is prohibited (see immutability below). 

## 3.5 Determinism under parallelism *(Binding)*

* **Permitted parallel units:** per-country and/or fixed tile blocks are allowed, but the final materialisation **MUST** be produced by a stable merge **ordered by `[country_iso, tile_id]`**. 
* **Prohibitions:** nondeterministic reducers/aggregations (e.g., unordered floating-point reductions) and data-dependent chunking that can change row order or membership are **forbidden**. The result MUST be independent of task count/scheduling (layer lineage law). 

## 3.6 Incremental recomputation & immutability *(Binding)*

* **Atomic publish:** writers **MUST** stage outputs outside the final partition and perform a single atomic rename into `…/parameter_hash={parameter_hash}/` when complete. Partial contents MUST NOT become visible. 
* **Immutability:** once published, a partition for a given `parameter_hash` is **immutable**; re-publishing to the same partition is either a byte-identical no-op or a **hard error**. 
* **Resume semantics:** if recovery is required, re-compute the entire affected country/chunk deterministically and re-stage; never patch in-place inside the live partition. (Ensures byte-stable results under §3.5.)

## 3.7 Path↔embed equality *(Binding)*

* **If any row-level lineage fields mirror path tokens** (e.g., an optional `parameter_hash` column added in a future schema revision), the embedded value **MUST byte-equal** the partition token. This mirrors the layer’s path↔embed equality rule used elsewhere. 

*Consequence:* With `[parameter_hash]` as the sole partition, PK `[country_iso, tile_id]`, and stable writer sort, S1 outputs are reproducible and byte-identical across re-runs, regardless of parallelism or scheduling, and remain consistent with the Dictionary and Schema authorities for `tile_index`.  

---

# 4. Inputs (sealed) *(Binding)*

S1 consumes only **reference/ingress** surfaces. It does **not** read any 1A egress. Each input below is **sealed** by ID, path family, version, and schema anchor in the Dictionary/Registry; JSON-Schema is the sole shape authority.

## 4.1 `iso3166_canonical_2024` — ISO-2 country list *(FK target)*

* **Anchor:** `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`. 
* **Dictionary facts:** status **approved**; format **parquet**; path `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`; **licence: CC-BY-4.0**; declared **consumed_by: [1B]**. 
* **Registry facts:** mirrors same path/anchor; **licence: CC-BY-4.0**. 
* **Binding use in S1:** provides the FK domain for `country_iso` (uppercase ISO-3166-1 alpha-2; placeholders such as `XX/ZZ/UNK` are **forbidden**). 

## 4.2 `world_countries` — country polygons (GeoParquet)

* **Anchor:** `schemas.ingress.layer1.yaml#/world_countries`. 
* **Dictionary facts:** status **approved**; format **parquet**; path `reference/spatial/world_countries/2024/world_countries.parquet`; **licence: ODbL-1.0**; **consumed_by: [1B]**. 
* **Registry facts:** mirrors same path/anchor; **licence: ODbL-1.0**; depends on `iso3166_canonical_2024`. 
* **Binding use in S1:** geometric conformance surface for per-country eligibility checks (point-in-polygon semantics are specified in §6).

## 4.3 `population_raster_2025` — global population raster (COG GeoTIFF)

* **Anchor:** `schemas.ingress.layer1.yaml#/population_raster_2025`. 
* **Dictionary facts:** status **approved**; format **cog_geotiff** (a.k.a. COG); path `reference/spatial/population/2025/population.tif`; **licence: ODbL-1.0**; **consumed_by: [1B]**. 
* **Registry facts:** mirrors same path/anchor; **licence: ODbL-1.0**. 
* **Binding use in S1:** provides the raster grid from which cells are enumerated; geotransform/centroid/area semantics are bound in §6.

## 4.4 `tz_world_2025a` — time-zone polygons *(provenance; not consumed by S1)*

* **Anchor:** `schemas.ingress.layer1.yaml#/tz_world_2025a`. 
* **Dictionary facts:** status **approved**; format **parquet**; path `reference/spatial/tz_world/2025a/tz_world.parquet`; **licence: ODbL-1.0**; **consumed_by: [1B]**. 
* **Registry facts:** mirrors same path/anchor; **licence: ODbL-1.0**. 
* **Binding note:** listed for layer lineage; **S1 MUST NOT read** this dataset (timezone legality arrives in later states).

---

## 4.5 Licence & provenance requirements *(Binding)*

* Each sealed input **MUST** carry a **concrete** licence in Dictionary/Registry (no placeholders); current licences: **CC-BY-4.0** (ISO) and **ODbL-1.0** (world_countries, population_raster_2025, tz_world_2025a).  
* S1 **MUST NOT** alter provenance (paths/versions/anchors) at runtime; inputs are read exactly as declared above. (JSON-Schema governs shape; Dictionary governs ID→path/partitions.)  

## 4.6 Partitioning & immutability of inputs *(Binding)*

* These reference surfaces are **unpartitioned** (no data path partitions) in the Dictionary; S1 **MUST** treat them as immutable for the duration of a run. 

## 4.7 Domain & FK constraints *(Binding)*

* `country_iso` values produced by S1 **MUST** be uppercase ISO-3166-1 alpha-2 present in `iso3166_canonical_2024`; placeholder codes are **invalid**. 

## 4.8 Out-of-scope inputs *(Binding)*

* Any dataset not listed in §4.1–§4.4 is **out of scope** for S1. In particular, **1A egress** (e.g., `outlet_catalogue`) and **S3 order surfaces** (e.g., `s3_candidate_set`) are **not** read by S1; S0’s PASS gate is noted only for coherence across 1B. 

*This completes the sealed-inputs contract for S1 and aligns with the live Dictionary/Registry and ingress anchors.*

---

# 5. Gate relationships *(Binding)*

## 5.1 Upstream consumer gate (context from S0/1A)

* **S1 does not read 1A egress**; therefore **S0 PASS is *not* a precondition to execute S1**. The **1A validation bundle** entry appears in the 1B Dictionary for discoverability only. 
* For coherence across 1B: **any workflow that *does* read `outlet_catalogue` must verify the 1A consumer gate** for the same `fingerprint` before reads — i.e., recompute the bundle hash from `index.json` (ASCII-lex over `index.path`, excluding the flag) and compare to `_passed.flag`; **No PASS → no read**.  

## 5.2 Allowed reads before any PASS

S1 MAY read **only** the sealed ingress references declared in §4:

* `iso3166_canonical_2024` (ISO FK) · `world_countries` (country polygons) · `population_raster_2025` (COG raster). These are listed as **approved** reference data in the 1B Dictionary. 

## 5.3 Prohibited accesses in S1

* **Prohibited:** any 1A egress (e.g., `outlet_catalogue`) and any S3 order surfaces (e.g., `s3_candidate_set`) — these are out of scope for S1 and **MUST NOT** be read here. When other states do need inter-country order, the **sole** authority is `s3_candidate_set.candidate_rank` (not encoded by S1). 

## 5.4 Gate-verification recipe (normative when 1A is read by other states)

If a downstream state (not S1) reads 1A egress for `fingerprint = f`:

1. Locate `data/layer1/1A/validation/fingerprint=f/`.
2. Read `index.json`; ensure listed files are unique and ASCII-sortable relative paths.
3. Compute `SHA256(concat(bytes(files in ASCII-lex order of index.path)))`, excluding `_passed.flag`.
4. Compare to the contents of `_passed.flag` (`sha256_hex = <hex64>`). **Match → PASS; else ABORT.** 

## 5.5 Order-authority boundary (coherence rule)

* S1 **MUST NOT** encode or rely on inter-country order. Across 1B, that order is provided **only** by `s3_candidate_set.candidate_rank`. Readers of 1A egress are reminded of this boundary in the 1A Dictionary. 

## 5.6 Gate posture for S1 outputs

* `tile_index` has **no separate PASS gate** in 1B at this time; **shape** and **path/partition law** (Schema + Dictionary) are the authorities for S1’s consumers. The 1B schema’s **validation** section currently defines only the S0 receipt; there is **no 1B validation bundle** anchor defined yet.  
* Consequently, consumers of `tile_index` MUST: resolve via Dictionary ID→path, verify schema conformance, and obey partitioning/ordering; **no `_passed.flag` check** applies to S1 outputs. 

## 5.7 Failure semantics (when gate checks apply)

* If any step in §5.4 fails (when applicable in later states), the consumer **MUST abort** and treat it as a **gate failure** for that `fingerprint`; **no** compensating reads or fallbacks are permitted. This mirrors S0’s “**No PASS → no read**” rule. 

*Result:* S1’s gate stance is minimal and precise: **ingress-only reads**, **no 1A dependency**, **no S1 PASS gate**, and crystal-clear instructions for the broader 1B pipeline where 1A gating *does* apply.

---

# 6. Normative behaviour *(Binding)*

> This section defines what S1 **must** do (and must not do) when producing `tile_index`. Shape/columns are owned by the schema anchor; path/partitions by the Dictionary.  

## 6.1 Raster grid interpretation *(Binding)*

* **Grid source:** the grid is taken **only** from `population_raster_2025` (COG). No other surface may redefine the grid. 
* **Indexing convention:** rows and columns are **zero-based**; grid order is **row-major** (top-to-bottom, left-to-right).
* **Tile identity:** for a cell at `(r, c)` in a grid with `ncols`, define
  `tile_id = r * ncols + c` (unsigned 64-bit range). This identity is **stable** for a fixed raster geotransform/resolution; any change that alters this mapping is a **MAJOR** change for S1.
* **Centroid:** `centroid_lon, centroid_lat` are the **cell center** coordinates derived from the raster geotransform in WGS84 (no reprojection here). (Exact column presence is schema-owned; semantics are bound here.) 

## 6.2 Eligibility predicate *(Binding)*

S1 determines whether a grid cell **belongs to** a country using an **inclusion predicate** applied against `world_countries` (union of that country’s polygons, with interior rings treated as **holes**). 

* **Allowed predicates:**  
  - `"center"` (default): **include** if the cell **centroid** lies **inside or on the boundary** of the country polygon; **exclude** if the centroid lies in a hole.  
  - `"any_overlap"`: **include** if the **area of intersection** between the cell polygon and the country polygon is **strictly positive** (line/point contact alone **does not** qualify).  
* **Predicate recording:** The predicate used for the run **MUST** be recorded in the **`inclusion_rule` column** (schema-required). It **MAY** also be echoed in the run report/audit per §9.

## 6.3 Country geometry rules *(Binding)*

* **Source of truth:** `world_countries` (GeoParquet) is the **only** authority for country shapes. Multi-polygons are treated as a **set union**; interior rings remove area; no implicit repairs. 
* **Boundary policy:** boundaries are **inclusive** for the `"center"` predicate (centroid on the boundary → **include**, unless that point lies on a hole boundary).
* **Antimeridian:** logic **must** be dateline-aware (longitudes normalized to **[−180, +180]**); countries that cross the ±180° meridian are treated as seamless polygons.
* **Topological health:** if a country polygon is invalid/topologically broken such that a reliable point-in-polygon test is impossible, S1 **must fail** with `E001_GEO_INVALID` (see §12).

## 6.4 NODATA and raster values *(Binding)*

* **Geometry-only decision:** eligibility is **independent** of pixel values (population, nodata masks, etc.). The presence of nodata in the raster **does not** exclude a cell if the predicate in §6.2 is satisfied. The raster is used for **grid geometry only** in S1. 

## 6.5 Coordinate & area semantics *(Binding)*

* **CRS:** WGS84 geographic (lon/lat degrees).
* **Bounds:** `centroid_lon ∈ [−180, +180]`, `centroid_lat ∈ [−90, +90]`.
* **Area:** `pixel_area_m2` represents the **ellipsoidal** area of the grid cell on WGS84, **strictly positive**. Implementations must use a geodesic/ellipsoidal method (not planar) and produce values within tight numeric tolerance set by the Layer numeric policy inherited across 1B; any non-positive area is `E006_AREA_NONPOS`. 

## 6.6 Determinism, parallelism & merge *(Binding)*

* **No RNG:** S1 is **deterministic** (no random sampling). 
* **Permitted parallel units:** per-country and/or fixed tile blocks are allowed **provided** the final materialisation results from a **stable merge ordered by `[country_iso, tile_id]`** (Dictionary sort law). Outcomes **must not** vary with task count/scheduling. 
* **Prohibitions:** nondeterministic reductions and data-dependent chunking that change row **membership** or **order** are forbidden.

## 6.7 Partitioning & write discipline *(Binding)*

* **Partition law:** `tile_index` **must** be written only under `…/parameter_hash={parameter_hash}/` and sorted by `[country_iso, tile_id]`; file order is **non-authoritative** (identity = partitions + keys). Re-publishing to the same partition must be **byte-identical** or is a hard error.  

## 6.8 Prohibitions *(Binding)*

* **No reads** of 1A egress (`outlet_catalogue`) and **no reliance** on S3 order surfaces in S1.
* **No timezone checks** (e.g., `tz_world_2025a`) in S1. These belong to later states. 

## 6.9 Acceptance hinge *(Binding)*

A produced `tile_index` is **non-conformant** if **any** of the following hold:

* violation of the inclusion predicate semantics in §6.2;
* use of country shapes other than `world_countries`;
* CRS/bounds violations or non-positive `pixel_area_m2`;
* non-deterministic materialisation or sort violation;
* write outside the Dictionary partition law.   

*These norms bind behaviour only; the **shape** (columns/types/keys) is enforced by `schemas.1B.yaml#/prep/tile_index`, and the **path/partition** law by the Dictionary entry for `tile_index`.*  

---

# 7. Output dataset *(Binding)*

## 7.1 Dataset ID & schema anchor

* **ID:** `tile_index`
* **Schema (shape authority):** `schemas.1B.yaml#/prep/tile_index`. This anchor fixes:

  * **Primary key:** `[country_iso, tile_id]`
  * **Partition keys:** `[parameter_hash]`
  * **Sort keys:** `[country_iso, tile_id]` 

## 7.2 Path, partitions, and ordering (Dictionary law)

* **Path family:** `data/layer1/1B/tile_index/parameter_hash={parameter_hash}/`
* **Partitions:** `[parameter_hash]` (one write per partition; write-once)
* **Writer sort:** `[country_iso, tile_id]` (stable, deterministic merge order)
* **Format:** `parquet` (as declared in the Dictionary)  

## 7.3 Immutability & atomic publish

* Writers **MUST** stage outside the final partition and perform a single atomic move into `…/parameter_hash={parameter_hash}/`.
* A subsequent publish to the same partition **MUST** be **byte-identical** or is a hard error (file order is non-authoritative). This mirrors the layer lineage rules established in S0. 

## 7.4 Licence, retention, PII class

* **Licence:** `Proprietary-Internal` (Dictionary)
* **Retention:** `365` days (Dictionary)
* **PII:** `false` (Dictionary)
  These properties are part of the dataset’s contract; implementations **MUST NOT** override them. 

## 7.5 Integrity & conformance obligations

Consumers and validators **MUST** assert, at minimum:

* **Schema conformance** to `#/prep/tile_index` (keys/partitions/sort as per §7.1). 
* **PK uniqueness:** no duplicate `(country_iso, tile_id)` within a `parameter_hash` partition. 
* **Dictionary hygiene:** dataset lives only under the declared partition path and respects the writer sort. 
* **Licence/retention/PII presence:** non-empty entries exist in the Dictionary for this dataset (absence ⇒ run-fail). 

## 7.6 Foreign-key and bounds checks (tied to §8 validation)

Although shape enforcement lives in the schema anchor, S1’s acceptance (see §8) **MUST** also verify that:

* `country_iso` values exist in `iso3166_canonical_2024` (FK domain). 
* Coordinate and area semantics match §6 (bounds; strictly positive area).

## 7.7 Compatibility notes (SemVer for this dataset)

* Any change to **PK**, **partition keys**, or **path family** is **MAJOR** for S1.
* Adding nullable columns is **MINOR**; editorial clarifications are **PATCH**. (See §13 for the MAJOR/MINOR/PATCH matrix.)  

*Result:* `tile_index` is fully specified by the schema (keys/partitions/sort), the Dictionary (path/format/licence/retention/PII), and the behavioural rules already bound in §6. No additional gates apply to S1 outputs.  

---

# 8. Validation & acceptance criteria *(Binding)*

> A run of **S1** is **accepted** only if **all** checks below pass. Where “validator” is mentioned, this refers to any process asserting conformance of the produced `tile_index`. Shape is governed by the schema; path/partitions by the Dictionary.  

## 8.1 Schema conformance (MUST)

* The materialised dataset **MUST** conform to **`schemas.1B.yaml#/prep/tile_index`**: primary key = `[country_iso, tile_id]`; partition keys = `[parameter_hash]`; writer sort = `[country_iso, tile_id]`. These are **shape authorities** and are not negotiable. 
* Validators **MUST** refuse any table that violates the above keys/partitions/sort, regardless of file order or tooling defaults. 

## 8.2 Dictionary/path law (MUST)

* The dataset **MUST** be written only under the Dictionary-declared path family:
  `data/layer1/1B/tile_index/parameter_hash={parameter_hash}/` with `format: parquet`.
  Validators **MUST** fail the run if rows are found outside this partition or if partition tokens do not match embedded lineage fields (if present). 
* Licence/retention/PII entries for `tile_index` **MUST** be non-empty in the Dictionary (licence `Proprietary-Internal`; retention 365; PII=false). Absence is a run-fail. 

## 8.3 Referential integrity & domains (MUST)

* **`country_iso` FK:** every value **MUST** be an uppercase ISO-3166-1 alpha-2 present in `iso3166_canonical_2024`. Validators **MUST** check against the ingress anchor declared for ISO. 
* **Ingress anchors in force:** `iso3166_canonical_2024`, `world_countries`, and `population_raster_2025` are the only sealed inputs for S1; validators **MUST** resolve them via their ingress schema refs. 

## 8.4 Geometric eligibility verification (MUST)

Validators **MUST** independently recompute eligibility using the sealed references in §4 and the predicate declared for the run (default `"center"`; allowed `{center, any_overlap}` per §6):

* **Tile identity:** obtain raster `ncols` from `population_raster_2025`; verify `tile_id == r*ncols + c` for the derived `(r,c)` of each row (row-major, zero-based). Any mismatch is `E003_DUP_TILE` or `E002_RASTER_MISMATCH` depending on symptom. 
* **Predicate check:**
  – `"center"` ⇒ include iff the **cell centroid** lies inside (or on the boundary of) the country polygon **and not inside a hole**.
  – `"any_overlap"` ⇒ include iff **area of intersection > 0** (pure edge/point contact does **not** qualify).
  Use `world_countries` as the sole geometry authority. Any deviation is `E001_GEO_INVALID` or `E008_INCLUSION_RULE`. 
* **Antimeridian & holes:** validators **MUST** treat multi-polygons as set union with interior rings removing area; longitudes normalized to [−180,+180]. Non-compliance fails the run (E001/E004). 

## 8.5 Coordinate & area semantics (MUST)

- `centroid_lon` and `centroid_lat` **MUST** be present and within legal bounds: lon ∈ [−180,+180], lat ∈ [−90,+90] (WGS84).
- `pixel_area_m2` **MUST** be present and **strictly positive**, computed on the WGS84 ellipsoid. Any non-positive area is `E006_AREA_NONPOS`.
- Validators **MUST** be able to recompute expected centroids/areas from the raster geotransform and assert equality within numeric tolerance.

## 8.6 Coverage & uniqueness (MUST)

* **PK uniqueness:** no duplicate `(country_iso, tile_id)` within a `{parameter_hash}` partition. 
* **Per-country coverage:** for each ISO country, the row count **MUST** equal the number of raster cells satisfying the chosen predicate against `world_countries`. Any discrepancy is a hard fail. 

## 8.7 Determinism & idempotence (MUST)

* For fixed sealed inputs and the same `{parameter_hash}`, re-materialising `tile_index` **MUST** yield a **byte-identical** table (order-insensitive at file level; identity = partitions + PK + content). Non-identical results are a hard fail. 

## 8.8 Writer discipline & hygiene (MUST)

* **Writer sort:** files **MUST** be written in `[country_iso, tile_id]` order so that merges from parallel workers are stable and deterministic. 
* **Atomic publish:** validators **MUST** confirm the final partition appears atomically under `…/parameter_hash={parameter_hash}/` (no partials); any subsequent publish to the same partition must be byte-identical or is a failure. 

## 8.9 Performance acceptance tests (PAT) (MUST)

* Validators **MUST** execute the PAT suite defined in §11 (throughput targets, memory & I/O budgets, parallelism invariants). Exceeding any bound is `E009_PERF_BUDGET`. *(PAT datasets, counters, and thresholds are defined normatively in §11 and referenced here.)* 

## 8.10 Evidence & artefacts (MUST)

A conformant run **MUST** provide, at minimum (location defined in §9):

* A per-country **eligibility summary**: total cells visited, cells included, cells excluded (by reason: hole, outside, other).
* A **determinism receipt**: hash of the produced partition contents and re-run hash equality for the same `{parameter_hash}`.
* **Predicate disclosure** used for the run (`"center"` or `"any_overlap"`).
  These artefacts are required for acceptance but do **not** constitute a separate S1 PASS gate (no `_passed.flag` for S1).  

## 8.11 Failure semantics (MUST)

* If **any** check in §8.1–§8.10 fails, validators **MUST** reject the run and emit the canonical error code(s) from §12 (e.g., `E001_GEO_INVALID`, `E002_RASTER_MISMATCH`, `E003_DUP_TILE`, `E004_BOUNDS`, `E005_ISO_FK`, `E006_AREA_NONPOS`, `E008_INCLUSION_RULE`, `E009_PERF_BUDGET`). 

*Result:* Acceptance requires simultaneous compliance with the schema anchor for `tile_index`, the Dictionary path/partition law, sealed-input authority surfaces, deterministic materialisation, and the PAT envelope. There is **no** S1 validation bundle/gate; conformance is established by these checks and evidence.   

---

# 9. Observability & audit *(Non-binding for results, **binding for presence**)*

> S1 produces **no gate bundle** and **no RNG logs**. Observability here means **evidence you must emit** so validators can attest conformance to §§6–8 and §11. These artefacts are **required to exist** but **do not** alter the semantics of `tile_index`. They **must not** be written inside the dataset partition (no stray files under `…/tile_index/parameter_hash={parameter_hash}/`). 

## 9.1 Deliverable overview *(Binding for presence)*

An accepted S1 run **MUST** expose the following, accessible to the validator (control-plane artifact, job attachment, or log stream), **outside** the `tile_index` partition:

* **S1 run report** — a single machine-readable JSON object (see §9.2).
* **Per-country summaries** — one JSON object per ISO2 country (array in the report **or** JSON-lines in logs; see §9.3).
* **Determinism receipt** — a composite SHA-256 of the **produced partition** (see §9.4).
* **PAT counters** — performance metrics required by §11 (see §9.5).
  Presence is **binding**; content is validated against §§8 & 11 (results remain defined solely by the `tile_index` dataset). 

## 9.2 S1 run report — required fields *(Binding for presence)*

A single JSON object named (for example) `s1_run_report.json` **MUST** contain at least:

* `parameter_hash` (hex64) — identifies the partition validated.
* `predicate` (`"center"` | `"any_overlap"`) — predicate actually used.
* `ingress_versions` — `{ iso3166: <string>, world_countries: <string>, population_raster: <string> }`.
* `grid_dims` — `{ nrows: <int>, ncols: <int> }` derived from `population_raster_2025`.
* `countries_total` — count of ISO2 entries visited.
* `rows_emitted` — total `tile_index` rows materialised for this run.
* `determinism_receipt` — object matching §9.4 (hash over the produced partition contents).
* `pat` — object with the §11 counters captured (see §9.5).
  This report **MUST** be available to the validator but **MUST NOT** be stored under the `tile_index` partition. 

## 9.3 Per-country summary — required fields *(Binding for presence)*

For each processed ISO2 country, emit a JSON object with:

* `country_iso` (ISO-3166-1 alpha-2);
* `cells_visited`, `cells_included`, `cells_excluded_outside`, `cells_excluded_hole`;
* `tile_id_min`, `tile_id_max`;
* optional `notes`.
  Delivery **MAY** be an array inside the run report **or** a JSON-lines stream (e.g., log lines prefixed `AUDIT_S1_COUNTRY:`). Validators **MUST** be able to retrieve these objects for the run.

## 9.4 Determinism receipt — composite hash *(Binding for presence; method is normative)*

Compute a **composite SHA-256** over the `tile_index/parameter_hash={parameter_hash}/` partition **files only**:

1. List all files under the partition (relative paths), **ASCII-lex sort** by path.
2. Concatenate raw bytes in that order; compute SHA-256; encode as lowercase hex64.
3. Record as `determinism_receipt = { "partition_path": "<path>", "sha256_hex": "<hex64>" }` in the run report.
   This mirrors the established hash recipe used by the S0 gate (ASCII-lex ordering, content hash), but applies to S1’s produced partition. 

## 9.5 Performance telemetry (ties to §11) *(Binding for presence)*

Emit, at minimum:

* `wall_clock_seconds_total`, `cpu_seconds_total`;
* `countries_processed`, `cells_scanned_total`, `cells_included_total`;
* `bytes_read_raster_total`, `bytes_read_vectors_total`;
* `max_worker_rss_bytes` (peak per worker), `open_files_peak`;
* concurrency facts: `workers_used`, `chunk_size` (if block-parallel).
  Validators use these counters to execute **Performance Acceptance Tests** per §11; exceeding a bound fails with `E009_PERF_BUDGET` (see §8.9/§12). 

## 9.6 Failure event schema *(Binding for presence)*

On any failure, emit an event object:

* `event`: `"S1_ERROR"`;
* `code`: one of §12 codes (e.g., `E001_GEO_INVALID`, `E002_RASTER_MISMATCH`, `E003_DUP_TILE`, `E004_BOUNDS`, `E005_ISO_FK`, `E006_AREA_NONPOS`, `E008_INCLUSION_RULE`, `E009_PERF_BUDGET`);
* `at`: RFC-3339 UTC;
* `parameter_hash`; optional `country_iso`; optional `raster_row`, `raster_col`.
  This event is **in addition** to normal process exit semantics and helps auditors triage systematically (vocabulary aligns with S0’s error style). 

## 9.7 Delivery & retention *(Binding for presence)*

* The artefacts in §9.1 **MUST** be exposed to validators as **control-plane artifacts or logs** and **MUST NOT** be placed inside the `tile_index` partition (keep the partition clean and schema-only). 
* Retain the run report and per-country summaries for **≥ 30 days** (minimum ops retention). This retention does **not** alter dataset semantics.

## 9.8 Privacy & licensing posture *(Binding for presence)*

* Do **not** emit PII; country codes and counts are non-PII.
* When echoing ingress provenance in reports, use their **Dictionary** IDs/versions (not raw file hashes); licensing remains as per the ingress Dictionary/Registry entries.

*Result:* Observability for S1 is **evidence-complete** (report + per-country summaries + deterministic partition hash + PAT metrics), non-intrusive (no files in the dataset partition), and aligned with your existing gate-hash discipline from S0.

---

# 10. Security, licensing, retention *(Binding)*

## 10.1 Security posture & access control

* **Closed-world:** S1 **operates only on sealed, version-pinned references**; no external enrichment or network reads. Provenance (owner, retention, licence, `schema_ref`) comes from the **Dataset Dictionary/Registry** and **must** be respected. 
* **Dictionary-only resolution:** All I/O **must** resolve via Dictionary IDs (no literal paths in code or outputs). JSON-Schema + Dictionary are the single authorities for shapes, paths, partitions, retention, and licence classes. 
* **Least-privilege & secrets:** Use least-privilege identities; **do not embed secrets** in datasets/logs; if credentials are required, use the platform secret store. 
* **Encryption at rest:** **SSE-KMS** (project-scoped key) is required; configure a bucket-level **deny** on unencrypted PUTs; keep server-side checksums (or SHA-256 sidecars). 
* **Atomicity & immutability:** Publish via **stage → fsync → atomic rename**; partitions are **write-once** (immutable). Re-publishing the same identity **must** be byte-identical or is a hard error. 

## 10.2 Licensing (authority, classes, and obligations)

* **Licence authority:** Licence class lives in the **Dictionary/Registry**; S1 **must not** override it. **Absence (or placeholder) is run-fail** per governance. 
* **Ingress licences (sealed inputs):**
  – `iso3166_canonical_2024` → **CC-BY-4.0** · retention **1095 days** · `pii:false` 
  – `world_countries` → **ODbL-1.0** · retention **1095 days** · `pii:false` 
  – `population_raster_2025` → **ODbL-1.0** · retention **1095 days** · `pii:false` 
  – `tz_world_2025a` → **ODbL-1.0** · retention **1095 days** · `pii:false` 
* **S1 output licence:** `tile_index` → **Proprietary-Internal** (Dictionary). 
* **Gate context (FYI only):** the 1A validation bundle is **Proprietary-Internal**; S1 doesn’t read it, but it’s listed for discoverability. 

## 10.3 Retention windows (authority & values)

* **Retention authority:** Retention windows are governed by the **Dictionary**; implementations **must not** override. 
* **Ingress retention:** ISO/country/tz/raster references retain for **1095 days**. 
* **S1 output retention:** `tile_index` retains for **365 days**. 
* **Write-once law:** Re-publishing an existing identity must be **byte-identical** or is a failure. 

## 10.4 Privacy & PII posture

* All sealed inputs and S1 outputs are **`pii:false`**. S1 **must not** introduce PII or re-identification fields. Observability artefacts (reports, per-country summaries, metrics) **must** avoid row-level payloads—**codes & counts only**. 

## 10.5 Validity windows & version pinning (governance)

* If governance declares **validity windows** for references/configs, S1 **must** treat out-of-window artefacts as **abort** (or **warn+abort** where specified). Artefacts without windows are **digest-pinned only (binding)**. 

## 10.6 Prohibitions (fail-closed)

S1 **MUST NOT**:

* read any 1A egress (e.g., `outlet_catalogue`) or S3 order surfaces; S1 is ingress-only. (Inter-country order remains an S3 authority, not used here.) 
* bypass Dictionary resolution with literal paths or alter Dictionary/Registry licence/retention values. 
* publish to the `tile_index` partition non-atomically, without encryption at rest, or with additional files other than the dataset itself (observability lives **outside** the partition). 

## 10.7 Compliance checklist (binding for acceptance)

A conformant S1 run **must** meet all of the following at review time:

1. **Licence fields present and correct** for all sealed inputs and for `tile_index` (classes as listed in §10.2).
2. **Retention windows** match the Dictionary (1095 days for ingress references; 365 days for `tile_index`).
3. **Encryption & atomicity** evidence: SSE-KMS enabled, stage→fsync→atomic-rename observed. 
4. **No PII** introduced; observability artefacts contain only codes/counts. 

*Binding effect:* Section 10 locks S1 to the platform’s **security rails** (closed-world, Dictionary-only, SSE-KMS, atomic publish), enforces **licence/retention governance** (CC-BY/ODbL/Proprietary-Internal as declared), and keeps all outputs and evidence **non-PII**, immutable, and auditable.

---

# 11. Performance, scalability & operational envelope *(Binding)*

> This section sets **objective, validator-enforceable** limits for S1. It is **binding** for acceptance (§8.9) and relies only on counters/evidence defined in §9.5 and the authorities for shape/path in the Schema/Dictionary.

## 11.1 Throughput & runtime bounds *(Binding)*

**Goal:** S1 is **I/O-bound** and must stream the raster once with minimal amplification. Validators compute the bound below using emitted counters (§9.5).

* Let:

  * `B_r` = **bytes_read_raster_total** (from §9.5), `S_r` = on-disk size of `population_raster_2025`.
  * `B_v` = **bytes_read_vectors_total**, `S_v` = on-disk size of `world_countries` + `iso3166_canonical_2024`.
* **I/O amplification (MUST):**

  * `B_r / S_r ≤ 1.25` and `B_v / S_v ≤ 1.25`. (Single-pass streaming with small re-reads only.) **Fail ⇒ `E009_PERF_BUDGET`.** 
* **Wall-clock bound (MUST):**
  Implementations **MUST** measure sustained object-store throughput at start (`io_baseline_raster_bps` by streaming ≥1 GiB contiguous from `population_raster_2025`; similarly `io_baseline_vectors_bps` over vector inputs). Then require:
  `wall_clock_seconds_total ≤ 1.75 × ( B_r / io_baseline_raster_bps + B_v / io_baseline_vectors_bps ) + 300s`.
  (1.75× headroom + 300 s setup budget.) **Fail ⇒ `E009_PERF_BUDGET`.**

## 11.2 Memory & I/O budgets *(Binding)*

* **Peak memory per worker:** `max_worker_rss_bytes ≤ 1.0 GiB`. **Fail ⇒ `E009_PERF_BUDGET`.**
* **Temp disk per worker:** ≤ **2 GiB**. **Fail ⇒ `E009_PERF_BUDGET`.**
* **Open files peak:** `open_files_peak ≤ 256`. **Fail ⇒ `E009_PERF_BUDGET`.**
* **Prohibition:** **No full-grid materialisation** in memory. S1 **MUST** stream in fixed windows; memory use is **O(window)**, not **O(N_cells)**.

## 11.3 Parallelism model (deterministic) *(Binding)*

* **Allowed:** per-country and/or fixed **tile-block** parallelism.
* **Required:** final materialisation is a **stable merge** ordered by `[country_iso, tile_id]` (Dictionary sort law). Outcomes **MUST NOT** vary with worker count/scheduling. 
* **Forbidden:** nondeterministic reducers; data-dependent chunking that changes row **membership** or **order**.

## 11.4 Determinism under contention *(Binding)*

* **Pre-emption/resume:** reprocessing any chunk **MUST** yield identical rows; merge remains byte-stable.
* **Atomicity:** publish is **stage → fsync → atomic rename**; partitions are **write-once**. **Any** non-identical re-publish is a failure (immutability). 

## 11.5 Back-pressure, retries & failure handling *(Binding)*

* **Retries:** at most **3** attempts per chunk; identical input ⇒ identical output (no random backoff that changes results).
* **Back-pressure:** implementations **MUST** throttle to keep `open_files_peak` and memory within §11.2 limits.
* **Cleanup:** on failure, no partials become visible under the live partition (see atomicity). 

## 11.6 Environment tiers *(Binding for PAT execution)*

* **DEV:** functional only (subset of ≤5 ISO2 countries); no performance claims.
* **TEST:** same code path as PROD; PAT **may** be executed on a ¼-world subset.
* **PROD (acceptance):** PAT **MUST** run on the **full** ingress set; acceptance/fail is taken **only** from PROD PAT. (Paths/format/license remain those declared in the Dictionary.) 

## 11.7 PAT definitions & pass/fail *(Binding)*

Validators execute the following using the artefacts in §9:

1. **Counters present** (from §9.5): `wall_clock_seconds_total`, `cpu_seconds_total`, `countries_processed`, `cells_scanned_total`, `cells_included_total`, `bytes_read_raster_total`, `bytes_read_vectors_total`, `max_worker_rss_bytes`, `open_files_peak`, `workers_used`, `chunk_size`. **Absence ⇒ `E009_PERF_BUDGET`.**
2. **I/O amplification checks:** enforce §11.1 ratios using on-disk sizes from the Dictionary/Registry for the sealed inputs. **Fail ⇒ `E009_PERF_BUDGET`.**
3. **Runtime bound:** compute the wall-clock bound via §11.1 using the run-recorded baselines; compare with `wall_clock_seconds_total`. **Fail ⇒ `E009_PERF_BUDGET`.**
4. **Memory/open-files:** enforce §11.2 hard caps. **Fail ⇒ `E009_PERF_BUDGET`.**
5. **Determinism check:** re-run S1 on the same `{parameter_hash}` with a **different** worker count; the **determinism receipt** (§9.4) **MUST** match byte-for-byte. **Mismatch ⇒ failure (determinism).**
6. **Writer sort & atomicity:** confirm stable sort `[country_iso, tile_id]` and atomic publish per §7/§3.6. **Fail ⇒ `E009_PERF_BUDGET`.** 

---

**Binding effect:** A run that satisfies **Schema**/shape (tile_index), **Dictionary** path/partition/sort, and **all** §11 PAT checks **passes** acceptance; any breach triggers `E009_PERF_BUDGET` (or a more specific code where applicable) per §8/§12.

---

# 12. Failure modes & canonical error codes *(Binding)*

> A run of **S1** is **rejected** if **any** condition below is triggered. On first detection the writer **MUST** abort, emit the failure event (§9.6), and ensure **no partials** become visible in `…/tile_index/parameter_hash={parameter_hash}/` (atomic publish law). Shape authority = **Schema**; path/partition/retention/licence = **Dictionary**; sealed inputs = **ingress anchors**.   

## E001_GEO_INVALID — Invalid or unusable country geometry *(ABORT)*

* **Trigger (MUST):** A country’s polygon/multipolygon from **`world_countries`** is topologically invalid or cannot support reliable point-in-polygon tests (including hole handling).
* **Detection:** Validator fails when eligibility can’t be established using **only** `world_countries` (sole geometry authority).
* **Evidence:** Failure event (§9.6) with `code=E001_GEO_INVALID`, offending `country_iso`.
* **Authority refs:** `world_countries` ingress anchor in Dictionary/Registry.  

## E002_RASTER_MISMATCH — Raster grid/transform inconsistent *(ABORT)*

* **Trigger (MUST):** Cell-to-`tile_id` mapping or derived `(r,c)` does not match the grid defined by **`population_raster_2025`** (e.g., wrong `ncols`, geotransform inconsistency).
* **Detection:** Validator recomputes `tile_id == r*ncols + c` (row-major, zero-based) from `population_raster_2025`; any mismatch is a failure.
* **Evidence:** Failure event with `code=E002_RASTER_MISMATCH`, plus `raster_row`, `raster_col` when available.
* **Authority refs:** `population_raster_2025` ingress anchor; S1 output PK includes `tile_id`.  

## E003_DUP_TILE — Primary key duplicate *(ABORT)*

* **Trigger (MUST):** Duplicate `(country_iso, tile_id)` within the `{parameter_hash}` partition of `tile_index`.
* **Detection:** Schema/validator PK check on `tile_index`.
* **Evidence:** Failure event with `code=E003_DUP_TILE`, include an example duplicate key.
* **Authority refs:** `schemas.1B.yaml#/prep/tile_index` — **PK = [country_iso, tile_id]**. 

## E004_BOUNDS — Coordinate bounds violated *(ABORT)*

* **Trigger (MUST):** `centroid_lon ∉ [−180,+180]` or `centroid_lat ∉ [−90,+90]`, or derived centroids (from raster geotransform) differ beyond numeric tolerance.
* **Detection:** Bounds check and tolerance comparison during validation.
* **Evidence:** Failure event with `code=E004_BOUNDS`, include offending values.
* **Authority refs:** `tile_index` shape authority + S1 normative bounds; output owned by `schemas.1B.yaml#/prep/tile_index`. 

## E005_ISO_FK — ISO foreign-key violation *(ABORT)*

* **Trigger (MUST):** A `country_iso` in `tile_index` is not present in **`iso3166_canonical_2024`** (uppercase ISO-2).
* **Detection:** FK check against the ISO ingress dataset.
* **Evidence:** Failure event with `code=E005_ISO_FK`, include offending code.
* **Authority refs:** ISO ingress anchor in the Dictionary/Registry.  

## E006_AREA_NONPOS — Non-positive cell area *(ABORT)*

* **Trigger (MUST):** `pixel_area_m2 ≤ 0` or validator’s ellipsoidal area computation yields non-positive area for a reported cell.
* **Detection:** Check per-row; ellipsoidal method on WGS84.
* **Evidence:** Failure event with `code=E006_AREA_NONPOS`.
* **Authority refs:** `tile_index` shape authority (columns future-compatible) + ingress surfaces for geometry.  

## E007_CRS_MISMATCH — Unexpected CRS semantics *(ABORT)*

* **Trigger (MUST):** Coordinates are not interpretable as WGS84 lon/lat per the Dictionary/Schema contract (e.g., output assumes projected meters).
* **Detection:** Validator infers CRS from inputs (ingress are WGS84) and verifies output semantics; inconsistencies fail.
* **Evidence:** Failure event with `code=E007_CRS_MISMATCH`.
* **Authority refs:** Ingress anchors (WGS84 lon/lat semantics via `world_countries` + `population_raster_2025`) and `tile_index` schema anchor.  

## E008_INCLUSION_RULE — Unsupported or misapplied predicate *(ABORT)*

* **Trigger (MUST):** Run used an inclusion predicate **not in** `{center, any_overlap}`, or applied `"center"`/`"any_overlap"` contrary to §6 semantics (e.g., counting edge-only contact as overlap).
* **Detection:** Validator recomputes eligibility using declared predicate and sealed inputs; mismatch fails.
* **Evidence:** Failure event with `code=E008_INCLUSION_RULE`, include declared predicate.
* **Authority refs:** S1 behaviour binds the predicate set; geometry authority via ingress anchors. 

## E009_PERF_BUDGET — Performance/operational envelope exceeded *(ABORT)*

* **Trigger (MUST):** Any **§11** bound is exceeded (I/O amplification, wall-clock bound, memory, temp disk, open files, determinism under re-run, atomic publish).
* **Detection:** PAT execution using counters in §9.5 (e.g., `bytes_read_raster_total`, `wall_clock_seconds_total`, `max_worker_rss_bytes`, `open_files_peak`), and the Dictionary sizes for sealed inputs.
* **Evidence:** Failure event with `code=E009_PERF_BUDGET`, include failing metric(s).
* **Authority refs:** PAT linkage to Dictionary/Registry (sealed input sizes), plus Dictionary path/sort law for materialisation checks.  

---

## 12.1 Failure handling (normative)

* **Abort semantics:** On any E00x, the writer **MUST** stop the run; **no** files are to be published under the live `tile_index/parameter_hash={parameter_hash}/` partition unless the materialisation is complete and **passes** all checks. (Atomic publish; write-once.) 
* **Event emission:** Emit the **failure event** described in §9.6 (binding for presence) with the canonical `code`, timestamp, `parameter_hash`, and optional `country_iso`, `raster_row`, `raster_col`. 
* **Multi-error policy:** If multiple conditions are detected, **MAY** emit multiple events; acceptance remains **failed**.
* **No gate reinterpretation:** S1 has **no** `_passed.flag`; do **not** create ad-hoc gates for S1 outputs. Conformance is through schema/path checks and PAT (see §7–§8–§11).  

## 12.2 Code space and stability (normative)

* **Reserved codes:** `E001`–`E009` are reserved for S1 as defined above.
* **SemVer impact:** Introducing/removing codes or changing triggers is **MINOR** if strictly tightening; **MAJOR** if it alters what previously passed/failed under the same inputs. (See §13.)

*Binding effect:* This catalogue defines **exact reject conditions** tied to the authorities: **Schema** (shape/keys/partitions), **Dictionary/Registry** (paths/licences/retention; sealed inputs), and S1’s own normative behaviour. Validators enforce these codes alongside §8 acceptance and §11 PAT.   

---

# 13. Change control & compatibility *(Binding)*

> This section defines how **S1 — Tile Index** evolves without breaking consumers, and when a change **must** be treated as MAJOR/MINOR/PATCH. It binds both **behavioural** rules (§6/§11) and the **data contract** (§7). SemVer terms here apply to the **S1 state spec**, its referenced **schema anchor for `tile_index`**, and the **Dictionary entry** for `tile_index`.

## 13.1 SemVer ground rules *(Binding)*

* **MAJOR**: a change that can make previously conformant S1 outputs **invalid** or **different** for the same sealed inputs and `{parameter_hash}`, or that requires consumer code/config changes.
* **MINOR**: a **backward-compatible** addition or tightening that **does not** invalidate previously conformant runs (on the reference ingress set) and **does not** force consumer changes.
* **PATCH**: editorial clarifications and fixes that do **not** alter behaviour, shape, keys, partitions, acceptance, or PAT thresholds.

## 13.2 Dataset contract — compatibility matrix *(Binding)*

**MAJOR** if any of the following change:

* **Identity & layout:** partition keys (currently `[parameter_hash]`); path family; writer sort `[country_iso, tile_id]`.
* **Keys/shape:** primary key `[country_iso, tile_id]`; required columns (if/when schema enumerates them as non-nullable); column **type** narrowing (e.g., number→int) or rename/removal.
* **CRS & semantics:** coordinate CRS (WGS84) or `tile_id` formula (`r*ncols + c` row-major); default `inclusion_rule`; allowed predicate set; area semantics (ellipsoidal→planar).
* **Behavioural gates:** acceptance logic in §8 that would reject a previously accepted result; PAT thresholds (§11) that cause previously passing reference runs to fail.
* **Dataset identity:** dataset ID rename; Dictionary dataset **status/licence** class weakening; retention shortening below published values.

**MINOR** if any of the following change:

* **Additive shape:** add **nullable** columns or optional metrics; widen a type (e.g., int→number) without breaking constraints.
* **Clarified validation:** tighten numeric tolerances **only if** verified not to invalidate prior accepted results on the reference ingress set.
* **Observability:** add optional fields to reports or per-country summaries; add optional PAT counters that are not used for pass/fail.
* **Documentation:** add examples, notes, or informative appendices.

**PATCH** if:

* Spelling/formatting/structure edits that don’t change obligations; cross-reference fixes; correcting non-normative text.

## 13.3 Behavioural compatibility (raster/geometry) *(Binding)*

* **Tile identity is stable.** Any change to grid derivation (e.g., using a different raster, changing `ncols` meaning) or to `tile_id` mapping is **MAJOR**.
* **Predicate semantics are stable.** The allowed set is `{center, any_overlap}`; modifying the semantics or default of `"center"` is **MAJOR**. Adding a new predicate is **MAJOR** unless gated behind a new dataset/anchor (see §13.6).
* **Country conformance rules are stable.** Changing boundary inclusion, hole handling, or antimeridian policy is **MAJOR**.

## 13.4 PAT & non-functional envelope *(Binding)*

* Increasing strictness in §11 (e.g., lower memory cap, tighter I/O amplification) is **MINOR only if** it **does not** fail previously published **reference** runs; otherwise **MAJOR**. Loosening a bound is **MINOR**.
* Adding **new mandatory** PAT counters or converting an optional counter into a pass/fail requirement is **MAJOR**.

## 13.5 Observability artefacts *(Binding)*

* The **presence** of §9 artefacts is binding; changing their **location** into the dataset partition is **MAJOR** (forbidden).
* Adding optional fields is **MINOR**; making new fields **mandatory** for acceptance is **MAJOR**.
* Renaming existing required fields (e.g., `rows_emitted`) is **MAJOR**.

## 13.6 Deprecation & removal policy *(Binding)*

* **Mark-and-wait:** deprecate features with `deprecated_since: x.y.z` and **do not remove** before the next **MAJOR**. Provide a normative migration note.
* **Aliases over renames:** for anchor or column renames, provide a compatibility alias for **≥ one MINOR** release before MAJOR removal.
* **Feature flags:** introducing a new behaviour (e.g., a new predicate) **must** use a **new dataset/anchor** or an explicit feature flag that defaults **off**; turning it **on** by default is **MAJOR**.

## 13.7 Interactions with sealed inputs *(Binding)*

* Updating ingress versions (ISO/countries/raster) **does not** change S1 SemVer, but **will** change outputs for the same `{parameter_hash}`; this is expected and remains acceptable.
* If an ingress update **forces** a change to S1 rules (e.g., CRS shift), that S1 change is classified per §13.2–§13.3 (likely **MAJOR**).

## 13.8 Migration & rollback *(Binding)*

* **Forward migration:** for MAJOR changes, publish a **MIGRATION NOTE** that states consumer impact, code/config deltas, and, if applicable, a dual-write period (old & new anchors) with a clear sunset date.
* **Rollback:** because partitions are **write-once**, rollback means **promoting** the last accepted `{parameter_hash}` partition; **never** mutate files in place.
* **Version pinning:** consumers **must** pin to a specific S1 spec version and schema anchor in CI; upgrades follow SemVer expectations above.

## 13.9 Versioning responsibilities *(Binding)*

* **Spec version (this doc):** bump per changes to behaviour/acceptance/PAT.
* **Schema version (`schemas.1B.yaml#/prep/tile_index`):** bump when shape/keys/constraints change.
* **Dictionary version (`dataset_dictionary.layer1.1B.yaml#tile_index`):** bump on path/partition/sort/licence/retention/status changes.
* **Consistency rule:** if a change crosses boundaries (e.g., both schema and dictionary), bump all affected artefacts in the **same release**, and record the cross-links in release notes.

---

*Binding effect:* With §13 in force, S1 evolves predictably: consumers can rely on **stable identity, shape, semantics, and PAT** within a major version; any change that could invalidate prior conformant outputs or consumer assumptions is **MAJOR**, everything else follows the **MINOR/PATCH** rules above.

---

# Appendix A — Definitions & symbols *(Informative)*

> Plain-English glossary and notation used in **S1 — Tile Index**. These entries explain terms but do not add new obligations beyond the Binding sections.

## A.1 Core identifiers & lineage

* **`parameter_hash`** — Lowercase **hex64** (SHA-256) digest representing the governed parameter set for a run; used as the **sole partition key** for parameter-scoped datasets in 1B (e.g., `tile_index`). In S1 it’s a **path token**; some tables in other states also **embed** it as a column with path↔embed equality.
* **`manifest_fingerprint`** (`fingerprint` in paths) — Lowercase **hex64** lineage digest used by 1A’s validation bundle and any 1A egress. The value in rows (when present) is byte-equal to the `fingerprint` path token. 
* **`seed`** — 64-bit unsigned RNG seed that appears in 1A egress and RNG logs; **not used** by S1 (S1 is RNG-free). 
* **`run_id`** — Run-scoped identifier (lowercase hex per layer); used for RNG logs, not by S1. 
* **`hex64`**, **`uint64`**, **`rfc3339_micros`** — Reusable JSON-Schema primitives defined for 1B (64-hex string; 0…2⁶⁴−1 integer; UTC timestamp `…Z` with 6 fractional digits). 

## A.2 Dataset contract terms

* **PK / UK / FK** — Primary/Unique/Foreign Key constraints owned by the schema anchor. For `tile_index`, **PK = `[country_iso, tile_id]`**; FK is to the ISO ingress surface.
* **Partition keys** — Path tokens that identify a concrete materialisation directory. `tile_index` partitions by **`[parameter_hash]`** only. 
* **Writer sort** — Logical sort to guarantee stable merges (here `[country_iso, tile_id]`); **file order is non-authoritative**. 
* **Path↔embed equality** — When a lineage field is both **embedded in rows** and **present in the path**, values are byte-equal (e.g., `manifest_fingerprint` in 1A egress; some parameter-scoped tables embed `parameter_hash`). 
* **Write-once / atomic publish** — Stage output outside the final path and atomically rename; re-publishing to the same identity must be **byte-identical**. 

## A.3 Geometry & raster terms

* **WGS84** — The geographic CRS used for coordinates (lon/lat degrees). S1 treats `centroid_lon ∈ [−180,+180]`, `centroid_lat ∈ [−90,+90]`. 
* **Country polygon** — Geometry from **`world_countries`** (GeoParquet): union of multipolygons; interior rings are **holes** that remove area; S1 performs no implicit repairs. 
* **Antimeridian** — The ±180° meridian; longitudes are normalised to [−180,+180] so countries crossing the line are handled seamlessly. *(Policy stated in S1 behaviour.)*
* **COG (Cloud-Optimised GeoTIFF)** — Access pattern of `population_raster_2025` used to stream the grid with range requests; S1 uses this raster for **grid geometry only**. 
* **Geotransform** — Mapping from raster `(row, col)` to WGS84 coordinates. The **cell centroid** is derived from the geotransform (center of the pixel). *(Column presence is schema-owned; semantics bound by S1.)*
* **Ellipsoidal area** — `pixel_area_m2` refers to cell area computed on the WGS84 ellipsoid (not planar). *(Behaviour bound by S1.)*

## A.4 Inclusion predicates (used by S1)

* **`"center"`** — Include a cell **iff** its centroid lies **inside or on the boundary** of the country polygon and not inside a hole.
* **`"any_overlap"`** — Include a cell **iff** the intersection area between the cell polygon and the country polygon is **strictly positive** (edge/point contact alone does not qualify).
  *(The predicate actually used is recorded for the run; allowed set and meaning are fixed by S1.)*

## A.5 Tile identity & indexing

* **Zero-based row/col** — `r, c ∈ {0,1,2,…}`; grid traversed in **row-major** order (top→bottom, left→right).
* **`ncols`** — Number of columns in the raster grid.
* **`tile_id`** — Global cell identifier: `tile_id = r * ncols + c` (unsigned 64-bit range). Stable for a fixed geotransform/resolution; any change that alters this mapping is a **MAJOR** change. 

## A.6 Hashing & ordering terminology

* **ASCII-lex order** — Sort file paths by their ASCII byte sequence (e.g., `"MANIFEST.json"` sorts before `"egress_checksums.json"`). Used when computing gate/receipt hashes. 
* **Composite SHA-256 / determinism receipt** — Hash of the **concatenated bytes** of all files under a dataset partition, listed in ASCII-lex relative-path order. S1 emits this for `tile_index` as evidence of byte-stable materialisation; separate from 1A’s validation flag. 

## A.7 Counters & metrics (for PAT; units)

* `wall_clock_seconds_total` (s), `cpu_seconds_total` (s), `countries_processed` (count),
  `cells_scanned_total` (count), `cells_included_total` (count),
  `bytes_read_raster_total` / `bytes_read_vectors_total` (bytes),
  `max_worker_rss_bytes` (bytes), `open_files_peak` (count), `workers_used` (count), `chunk_size` (tiles).
  These are **evidence counters** emitted outside the dataset partition and evaluated against §11 thresholds. 

## A.8 Abbreviations

* **CRS** — Coordinate Reference System (here: WGS84)
* **COG** — Cloud-Optimised GeoTIFF
* **PAT** — Performance Acceptance Tests (S1’s pass/fail envelope)
* **PII** — Personally Identifiable Information (S1 outputs/inputs are `pii:false`) 

## A.9 Symbols & sets (mathematical)

* **ℕ** — `{1,2,3,…}`; **ℕ₀** — `{0,1,2,…}`
* **ℤ** — Integers
* **[a,b]** — Closed interval; **(a,b)** — open interval
* **r, c** — Raster row/column indices in ℕ₀
* **`nrows, ncols`** — Grid dimensions in ℕ
* **A ⊂ B** — Strict subset; **∪, ∩, ∖** — union, intersection, set difference

---

*Informative note:* All definitions above align with the live anchors and contracts: schema primitives and `tile_index` keys/partitions from **`schemas.1B.yaml`** and the **1B Dictionary**; lineage token semantics and ASCII-lex hashing from **S0**; and ingress surfaces from the **ingress Dictionary**.

---

# Appendix B — Worked examples & sanity queries *(Informative)*

> These examples illustrate **S1 — Tile Index** behaviour and give ready-made **sanity queries** for validators. They do not add new obligations beyond the Binding sections. Where shape/path authority matters, we reference the `tile_index` schema anchor and Dictionary entry.

---

## B.1 Micro-grid: tile identity & “center” predicate

**Setup:** Suppose `population_raster_2025` is a tiny 3×4 grid (nrows=3, ncols=4). Row/col are **zero-based**; identity is `tile_id = r * ncols + c`. A country polygon covers cells with centroids at:

* `(r,c) = (0,1), (0,2), (1,1), (1,2)` (a 2×2 block), and excludes a hole overlapping the centroid of `(1,1)`.

**Expected rows (subset):**

```
(country_iso, tile_id) for ncols=4:
(XX,  1)  // r=0,c=1
(XX,  2)  // r=0,c=2
(XX,  6)  // r=1,c=2      (note (1,1) excluded: hole removes centroid)
```

These rows live under the **Dictionary** path `data/layer1/1B/tile_index/parameter_hash={parameter_hash}/` and obey PK `[country_iso, tile_id]` and writer sort `[country_iso, tile_id]`.

---

## B.2 Hole handling vs boundary

* **Hole removal:** If the centroid falls in a hole (interior ring) → **exclude** even if the cell polygon overlaps the country shell.
* **Boundary:** Under `"center"`, a centroid exactly on the **country boundary** counts as **inside**; a centroid exactly on a **hole boundary** counts as **excluded** (treat holes as area-removing).
  Geometry source is **`world_countries`** (GeoParquet). 

---

## B.3 Antimeridian sanity

For a country spanning 179.4°E to −178.8°W, normalise longitudes to **[−180,+180]** and treat the polygon as seamless. A cell with centroid at **179.75°E** (i.e., +179.75) is inside the eastern lobe; a cell at **−179.25°** is inside the western lobe. Inclusion is determined strictly by the chosen predicate; CRS is WGS84. 

---

## B.4 `"center"` vs `"any_overlap"`

* **`"center"`**: include iff centroid ∈ country polygon **and not in a hole**.
* **`"any_overlap"`**: include iff **area of intersection > 0** (touching at a line/point is **not** enough).
  Record the predicate you used in the **run report** (§9). Geometry comes only from `world_countries`.

---

## B.5 NODATA does not exclude

Presence of NODATA pixels in `population_raster_2025` **does not** change eligibility; S1 uses the raster for **grid geometry only** (geotransform → centroid and indexing). 

---

## B.6 Determinism receipt — worked example

**Goal:** Emit a single SHA-256 over the concatenated bytes of all files in the produced **`tile_index/parameter_hash=…/`** partition, listed in **ASCII-lex** relative-path order. (This mirrors the S0 gate’s hashing discipline.) 

Example file list (relative):

```
country=DE/part-000.parquet
country=FR/part-000.parquet
country=US/part-000.parquet
```

ASCII-lex order: `country=DE/part-000.parquet`, `country=FR/part-000.parquet`, `country=US/part-000.parquet` → concatenate bytes in that order → SHA-256 → record in the run report’s `determinism_receipt`.

---

## B.7 Sanity queries (validator sketches)

> These are **declarative checks** you can apply to a materialised `tile_index`. They rely on the schema anchor for keys/partitions and on ingress anchors for FK/geometry.

1. **PK uniqueness**

```sql
SELECT country_iso, tile_id, COUNT(*) c
FROM tile_index
GROUP BY country_iso, tile_id
HAVING c > 1;
-- Expect: no rows. (PK = [country_iso,tile_id])  ─ schema authority
```



2. **FK to ISO**

```sql
SELECT t.country_iso
FROM tile_index t
LEFT JOIN iso3166_canonical_2024 i ON t.country_iso = i.country_iso
WHERE i.country_iso IS NULL;
-- Expect: no rows.  ─ ingress ISO FK
```



3. **Tile identity vs raster**

```sql
-- Using ncols from population_raster_2025 metadata:
SELECT *
FROM tile_index t
WHERE t.tile_id <> (t.raster_row * :ncols + t.raster_col);
-- Expect: no rows.  ─ row-major, zero-based
```



4. **Predicate check (center)**

```sql
-- Pseudocode-ish SQL: centroid_in_polygon() respects holes & WGS84
SELECT country_iso, tile_id
FROM tile_index t
WHERE :predicate = 'center'
  AND NOT centroid_in_polygon(t.centroid_lon, t.centroid_lat,
                              world_countries[country_iso]);
-- Expect: no rows.
```



5. **Bounds & positive area**

```sql
SELECT *
FROM tile_index
WHERE centroid_lon NOT BETWEEN -180 AND 180
   OR centroid_lat NOT BETWEEN -90 AND 90
   OR pixel_area_m2 <= 0;
-- Expect: no rows.  ─ WGS84 bounds; ellipsoidal area > 0
```



6. **Partition/path hygiene (Dictionary law)**

```text
Path must be:
data/layer1/1B/tile_index/parameter_hash={parameter_hash}/   (format=parquet)
```

Check the materialised path; any stray files elsewhere → fail. 

7. **Writer sort stability**

```sql
-- Files should be written in [country_iso, tile_id] order to guarantee stable merges.
-- (Order is logical; file order non-authoritative. Inspect per-file sorted blocks if needed.)
```



8. **Determinism (re-run)**

* Re-run S1 on the same `{parameter_hash}` with a **different** worker count; recompute the determinism receipt (§9).
* **Receipts must match** byte-for-byte; mismatch → fail. (This is S1’s acceptance determinism proof.) 

---

## B.8 PAT walkthrough (numbers are illustrative)

Assume the run report shows:

* `bytes_read_raster_total = 8.0 GiB`, on-disk `population_raster_2025` size `S_r = 7.2 GiB` → `B_r/S_r = 1.11` (**pass**, ≤1.25).
* `bytes_read_vectors_total = 250 MiB`, combined vectors size `S_v = 240 MiB` → `B_v/S_v = 1.04` (**pass**).
* Baselines: `io_baseline_raster_bps = 320 MiB/s`, `io_baseline_vectors_bps = 150 MiB/s`.
* **Bound:** `≤ 1.75 × (8.0 GiB / 320 MiB/s + 250 MiB / 150 MiB/s) + 300 s   = 1.75 × (25.0 s + 1.67 s) + 300 s ≈ 1.75 × 26.67 + 300 ≈ 346.7 s`.
* If `wall_clock_seconds_total = 330 s` → **pass**; if `= 380 s` → **fail (`E009_PERF_BUDGET`)**.

(See §11 for binding thresholds and §9.5 for required counters.) 

---

## B.9 S0 hashing discipline (for comparison)

S0’s validator gate hashes the 1A validation bundle in **ASCII-lex** `index.path` order (flag excluded). S1’s determinism receipt mirrors the same **ASCII-lex concatenation → SHA-256** recipe, but over the **produced partition** rather than a gate bundle. 

---

## B.10 Quick checklist (non-exhaustive)

* **Shape & keys** match `#/prep/tile_index`. ✔︎ 
* **Path** and **partitions** match the Dictionary (only under `…/parameter_hash=…/`, format `parquet`). ✔︎ 
* **Ingress** datasets resolved via **ingress anchors** (ISO/countries/raster). ✔︎ 
* **ASCII-lex receipt** computed and recorded (run report). ✔︎ 

---

*These examples and queries are aligned with the live anchors for `tile_index` (schema & Dictionary), the sealed ingress surfaces, and the S0 hashing discipline that S1 intentionally mirrors for its determinism receipt.*

---

# Appendix C — PAT datasets & measurement recipe *(Informative; references §11/§8.9)*

> This appendix tells you **what to run** and **how to measure** to execute the Performance Acceptance Tests (PAT) defined in §11, and how to package evidence required in §8.10/§9. It references only sealed inputs and authorities already pinned in the Dictionary/Registry and Schema.

---

## C.1 PAT levels & what counts for acceptance

* **DEV** — functional sanity on a **small ISO subset** (≤5 countries). No performance claims are taken from DEV.
* **TEST** — same code path as PROD on a **¼-world subset** (fixed list under CI). Useful for catching regressions early.
* **PROD** — **full ingress set**; **only PROD PAT results** are used for pass/fail against §11 thresholds. Paths/partitions/licensing stay as declared in the Dictionary. 

---

## C.2 PAT datasets (sealed inputs & authorities)

Use the exact ingress surfaces declared for 1B:

* **ISO codes (FK):** `iso3166_canonical_2024` → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`. 
* **Country polygons:** `world_countries` → `#/world_countries`. 
* **Population raster (grid source):** `population_raster_2025` (COG) → `#/population_raster_2025`. 

Dictionary entries pin path, format, retention, and licence; **JSON-Schema stays the sole shape authority** for `tile_index`.

> **Subset selection (DEV/TEST):** choose ISO2 codes **from the ISO table** (e.g., mix of small/large countries, at least one crossing the antimeridian). The spec does **not** freeze a particular list; keep it under CI config, but PROD must be **full ISO coverage**. 

---

## C.3 Evidence you must emit (ties to §9.1/§9.5)

Your run must expose (outside the dataset partition):

* **Run report** with `parameter_hash`, `predicate`, ingress versions, grid dims, rows emitted, **determinism_receipt**, and **PAT counters**.
* **PAT counters:** `wall_clock_seconds_total`, `cpu_seconds_total`, `countries_processed`, `cells_scanned_total`, `cells_included_total`, `bytes_read_raster_total`, `bytes_read_vectors_total`, `max_worker_rss_bytes`, `open_files_peak`, `workers_used`, `chunk_size`. 

---

## C.4 Measurement setup (once per run)

1. **Resolve sealed inputs via the Dictionary** (no literal paths). Record the on-disk sizes of the raster/vector inputs from object-store metadata as `S_r` and `S_v`. 
2. **Warm-up policy:** optional one-pass warm-up *not* counted in `wall_clock_seconds_total`; record whether warm-up was used.
3. **Baseline throughput:** measure sustained read bandwidth by streaming a **contiguous ≥1 GiB** slice of `population_raster_2025` once (range requests) → `io_baseline_raster_bps`. Repeat for vectors (combined `world_countries` + ISO) → `io_baseline_vectors_bps`. Store both in the run report.
4. **Concurrency declaration:** record `workers_used` and `chunk_size` if block-parallel (ties to determinism re-run in C.7).
5. **Start timers & counters:** begin `wall_clock_seconds_total` and `cpu_seconds_total`; zero the byte and object counters. (Counters listed in C.3.)

---

## C.5 What to record during the run

* **Bytes read:** accumulate `bytes_read_raster_total` (raster) and `bytes_read_vectors_total` (vectors only).
* **Scan counters:** `countries_processed`, `cells_scanned_total`, `cells_included_total`.
* **Resource peaks:** `max_worker_rss_bytes`, `open_files_peak`.
  These land in the run report/PAT section (see §9.5). 

---

## C.6 Computing the §11 checks (pass/fail)

Using the counters and baselines:

1. **I/O amplification (MUST satisfy):**
   `B_r/S_r ≤ 1.25` and `B_v/S_v ≤ 1.25`, where `B_r = bytes_read_raster_total`, `B_v = bytes_read_vectors_total`. **Fail ⇒ E009_PERF_BUDGET.** 
2. **Wall-clock bound (MUST satisfy):**
   `wall_clock_seconds_total ≤ 1.75 × ( B_r/io_baseline_raster_bps + B_v/io_baseline_vectors_bps ) + 300`. **Fail ⇒ E009_PERF_BUDGET.** 
3. **Memory / I/O caps (MUST satisfy):**
   `max_worker_rss_bytes ≤ 1.0 GiB`, temp disk ≤ 2 GiB, `open_files_peak ≤ 256`. **Fail ⇒ E009_PERF_BUDGET.** 
4. **Writer discipline / atomicity:** verify partition path, writer sort, and atomic publish per Dictionary/§7. **Fail ⇒ E009_PERF_BUDGET.** 

---

## C.7 Determinism re-run (required by §11.7)

* **Re-run** the exact job with the same `{parameter_hash}` but **different** `workers_used`.
* Recompute the **determinism receipt** as SHA-256 over the **ASCII-lex ordered** bytes of files under `…/tile_index/parameter_hash={parameter_hash}/`. **Receipts must match byte-for-byte; mismatch ⇒ failure.** 

---

## C.8 Packaging the evidence (where to put it)

* **Do not** place reports/counters **inside** the `tile_index` partition. Provide them as control-plane artefacts/logs:
  `s1_run_report.json` (single object) plus optional JSON-lines for per-country summaries. Retain ≥ 30 days. 

---

## C.9 Sanity queries you can run post-PAT

* **PK uniqueness** and **FK to ISO** checks (Appendix B.7 #1/#2).
* **Tile identity** check vs raster `ncols` (Appendix B.7 #3).
* **Bounds & positive area** checks (Appendix B.7 #5).
  These are not performance metrics but help correlate failures (e.g., high `B_r/S_r` due to mis-chunking).

---

## C.10 Troubleshooting guide (symptoms → likely causes)

* **`B_r/S_r > 1.25`** → non-COG streaming (random small reads), repeated raster passes, or unbounded re-tries.
* **`wall_clock_seconds_total` above bound** → low baseline measurement, single-threaded raster read, or excessive per-tile overhead.
* **`open_files_peak > 256`** → leaking file handles across workers or oversharding parquet writes.
* **Determinism receipt mismatch** → nondeterministic reducer, unstable merge (not sorted by `[country_iso, tile_id]`), or post-merge rewrite.
  Use the Dictionary entry for `tile_index` to confirm path/partition/sort law while debugging. 

---

## C.11 Minimal PAT checklist (what validators expect to see)

1. Run report present with all **PAT counters** and **baselines**. 
2. I/O amplification ratios and wall-clock bound computed and **passing**. 
3. Memory/I/O caps respected. 
4. Determinism re-run receipts **identical** (ASCII-lex recipe). 
5. Writer sort & atomic publish proven; Dictionary path verified. 

---

*This recipe keeps PAT fully reproducible and audit-ready while remaining within the authorities pinned for 1B: the **Dictionary** (paths/partitions/licensing for sealed inputs and `tile_index`) and **Schema** (shape/keys). It mirrors the S0 hashing discipline for byte-stable determinism.*

---