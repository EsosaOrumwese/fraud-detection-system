# 1B · S2 — Tile Weights — Technical Specification

# 0. Document metadata & status *(Binding)*

**Document ID:** `state.1B.s2.expanded`
**Title:** Layer 1 · Subsegment 1B · **S2 — Tile Weights (deterministic fixed-decimal weights per eligible tile)**
**Layer/Subsegment/State:** Layer 1 / 1B / S2
**Status:** **Draft** → targets **Alpha** on ratification
**Owners (roles):** 1B Spec Author · 1B Spec Reviewer · Program Governance Approver
**Last updated (UTC):** 2025-10-18
**Normative keywords:** **MUST, MUST NOT, SHALL, SHALL NOT, SHOULD, SHOULD NOT, MAY** are binding as used herein.
**Audience:** Implementation agents and reviewers; anything marked *Informative* is non-binding.

## 0.1 Scope of this document *(Binding)*

This specification defines the **behavioural** and **data** contract for **S2 — Tile Weights**. S2 takes the **eligible tiles** enumerated by S1’s `tile_index` and assigns **deterministic, fixed-decimal (fixed-dp)** weights per tile **without RNG**. It binds **inputs, outputs, invariants, prohibitions, validation, and performance envelope** for S2. Implementation details/pseudocode are **out of scope**.

## 0.2 Authority set and anchors *(Binding)*

* **Output shape (sole shape authority):** `schemas.1B.yaml#/prep/tile_weights`
* **Dictionary law (ID→path/partitions/sort/licence/retention):** `dataset_dictionary.layer1.1B.yaml#tile_weights`
* **Upstream input:** `schemas.1B.yaml#/prep/tile_index` (S1 universe of eligible tiles)
* **Ingress (sealed references available to S2):**
  `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` · `#/world_countries` · `#/population_raster_2025` *(S2 remains RNG-free; geometry is consulted only if explicitly bound later)*
  JSON-Schema is the **sole** shape authority. Avro/Parquet encodings are non-authoritative; the Dictionary governs **paths/partitions/sort/licensing/retention**; the Artefact Registry governs **licences & provenance**.

## 0.3 Compatibility window *(Binding)*

This document is compatible with and assumes:

* **S1 (1B) state spec** is ratified (S2 reads `tile_index`).
* **Layer-1/1B schema and dictionary** anchors listed above exist and are current.
  Any change to **`tile_weights`** PK, partition keys, path family, or required columns; to the **fixed-dp quantization law** (including dp semantics or tie-break); or to the **weighting basis** that alters outputs for the same inputs **is MAJOR** for S2 (see §13).

## 0.4 Identity, partitioning, and determinism posture *(Binding)*

* **RNG usage:** **None** in S2.
* **Identity:** S2 outputs are **parameter-scoped**; identity is `{parameter_hash}` **only**.
* **Partitioning:** `tile_weights` partitions by `[parameter_hash]` and **MUST** be written only under `…/tile_weights/parameter_hash={parameter_hash}/` with writer sort `[country_iso, tile_id]` (Dictionary law).
* **Determinism & idempotence:** For fixed sealed inputs and the same `{parameter_hash}`, S2 outputs are **byte-identical** across re-runs (file order is non-authoritative).
* **Path↔embed:** If any lineage field is both embedded and present in the path, values **MUST** byte-equal (explicit rules given where applicable later).

## 0.5 Non-functional envelope pointers *(Binding)*

This document binds **performance and operational** constraints in **§11** and makes their **Performance Acceptance Tests (PAT)** part of validity in **§8.9**. Evidence obligations (run report, per-country normalization summaries, determinism receipt, counters) are bound in **§8.10** and §9. Implementations that satisfy shape but violate §11 **fail** S2.

## 0.6 Change control & SemVer for this document *(Binding)*

* **MAJOR:** changes that can alter valid S2 outputs for the same inputs/`{parameter_hash}` (e.g., PK/partition/path; required columns; dp/tie-break law; weighting basis semantics; acceptance rules).
* **MINOR:** backward-compatible additions/tightenings that do **not** invalidate previously accepted runs (e.g., optional columns; additional non-blocking metrics).
* **PATCH:** editorial clarifications; *Informative* examples; errata that do not change obligations.
  SemVer for this document advances only by these rules; behaviour follows the highest-precedence authority per §2.

## 0.7 Approvals & ratification *(Binding)*

* **To ratify Alpha:** all **Binding** sections complete; the `tile_weights` columns **are enumerated** in the schema anchor; §8 acceptance and **§11 PAT** thresholds are populated; Dictionary entry for `tile_weights` is present with correct **path/partition/sort/licence/retention**; governance sign-off recorded here (name + date).
* **To ratify Stable:** evidence of §8/§11 acceptance on reference inputs is attached; no outstanding *Informative* gaps affecting behaviour.

---

# 1. Purpose & scope *(Binding)*

## 1.1 Purpose *(Binding)*

S2 defines how **every eligible tile** in S1’s `tile_index` receives a **deterministic, fixed-decimal (fixed-dp)** weight. For each `country_iso`, S2 forms a per-country distribution over `(country_iso, tile_id)` and materialises it as the dataset **`tile_weights`**. The weighting is **RNG-free** and fully reproducible from sealed inputs and the governed parameter set captured by `{parameter_hash}`. The **shape** of `tile_weights` is owned by its schema anchor, while **paths/partitions/sort/licence/retention** are owned by the Dictionary; this specification binds the **behavioural rules** and **acceptance criteria** that implementations must meet.

## 1.2 Non-goals *(Binding)*

S2 explicitly **does not**:

* read any 1A egress or depend on S0’s PASS gate (S2 is ingress + S1-only);
* perform per-merchant/per-outlet adjustments, timezone legality, or sampling;
* introduce randomness, stochastic smoothing, or heuristic “nudges” to weights;
* encode inter-country order or any order authority beyond the declared writer sort;
* change S1’s universe — if a tile is absent from `tile_index`, S2 must not invent it;
* prescribe implementation details or pseudocode (only contract and invariants are binding).

## 1.3 Success criteria *(Binding)*

An S2 run is “valid & done” only if **all** of the following hold:

* **Authority conformance**

  * **Shape:** The emitted table conforms to the **`tile_weights`** schema anchor (columns, PK, required fields).
  * **Dictionary law:** The dataset is written **only** at the Dictionary-governed path family for `tile_weights`, partitioned by `{parameter_hash}`, with writer sort `[country_iso, tile_id]`, declared format, licence, retention, and PII posture.

* **Determinism & identity**

  * For identical sealed inputs and the same `{parameter_hash}`, re-runs are **byte-identical** (file order non-authoritative; identity = partitions + keys + content).
  * Stable merge: outcomes do **not** vary with worker count or scheduling.

* **Normalization & quantization invariants**

  * For each `country_iso`, unquantized real weights (derived from the declared **basis** in §6) form a probability distribution that sums to **1.0**.
  * Fixed-dp quantization uses the **governed `dp`** and a **deterministic largest-remainder** allocation with a stated tie-break (defined in §6), yielding an exact per-country integer sum of **`10^dp`**.
  * **Monotonicity:** if basis mass(A) ≥ mass(B), then the quantized weight of A ≥ that of B, up to integerization residues defined in §6.

* **Referential integrity**

  * `(country_iso, tile_id)` in `tile_weights` **must** exist in `tile_index` for the same `{parameter_hash}`.
  * `country_iso` values are valid ISO-2 codes per the ingress FK surface.

* **Write discipline & immutability**

  * Atomic publish (stage → fsync → atomic rename); the partition for a given `{parameter_hash}` is **write-once**. Any subsequent publish to the same identity is byte-identical or a failure.

* **Evidence & performance**

  * Required **evidence** is produced (see §9/§8.10): run report including `parameter_hash`, **basis** and **dp**, per-country normalization summaries, and a **determinism receipt** (ASCII-lex partition hash).
  * **PAT** (Performance Acceptance Tests) in §11 are executed and pass; acceptance incorporates PAT per **§8.9**.

---

# 2. Sources of authority & precedence *(Binding)*

## 2.1 Authority set (normative anchors)

* **Output shape (sole shape authority):** `schemas.1B.yaml#/prep/tile_weights`. *(Required columns and keys (PK/partition/sort) are enumerated here.)* 
* **Dictionary law (ID → path/partitions/sort/licence/retention):** `dataset_dictionary.layer1.1B.yaml#tile_weights` → `path = data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/`, `partitioning = [parameter_hash]`, `ordering = [country_iso, tile_id]`, `format = parquet`, `licence = Proprietary-Internal`, `retention = 365`. 
* **Upstream input (universe of eligible rows):** `schemas.1B.yaml#/prep/tile_index` (shape) and `dataset_dictionary.layer1.1B.yaml#tile_index` (path/partitions/sort).
* **Ingress references (sealed; read-only for S2):** `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`, `#/world_countries`, `#/population_raster_2025` — pinned in the Dictionary with licences/paths. 

> JSON-Schema is the **sole** shape authority. Avro/Parquet encodings are non-authoritative for shape. The **Dictionary** governs canonical paths, partitions, writer sort, licence and retention. The **Artefact Registry** governs ingress/licensing provenance and is informative for S2 behaviour.

## 2.2 What each authority governs

* **JSON-Schema (tile_weights / tile_index anchors):** row/field shapes; PK/partition/sort keys; domain primitives. 
* **Dataset Dictionary:** dataset IDs → canonical path families; partitioning & writer sort; format; licence/retention/PII posture. 
* **Artefact Registry:** licences, provenance, roles for ingress references (ISO, countries, population raster, tz), and internal dataset notes (non-shape). 
* **This S2 specification:** behavioural obligations (basis, normalization, quantization, tie-break), prohibitions, validations, PAT. *(Subordinate to Schema/Dictionary for shape/path law.)*

## 2.3 Precedence chain (tie-break)

When obligations appear to conflict, S2 SHALL apply this order:

1. **JSON-Schema** (shape/domains/keys). 
2. **Dataset Dictionary** (ID→path/partitions/sort; licence/retention/PII). 
3. **Artefact Registry** (licence/provenance for sealed inputs). 
4. **This S2 spec** (behavioural rules) under (1)–(3).

Schema outweighs Dictionary on **shape**; Dictionary outweighs any literal path. Implementations **MUST NOT** hard-code paths; resolve via the Dictionary. 

## 2.4 Upstream dependency (universe of tiles)

S2’s universe is **exactly** the rows of `tile_index` for the same `{parameter_hash}`. No row may be created in `tile_weights` unless `(country_iso, tile_id)` exists in `tile_index`; conversely, S2 must not delete or coalesce rows from that universe. *(FK/coverage checks are bound in §8.)*

## 2.5 Gate & order-authority boundaries (coherence)

S2 does **not** read any 1A egress; therefore S0’s 1A consumer gate is **not** a precondition to execute S2. The Dictionary carries a discoverability entry for the 1A validation bundle for other states; S2’s readers do not consult it. Inter-country order is **not** encoded by S2 (writer sort is `[country_iso, tile_id]` only). Details of gate posture are specified in §5. 

## 2.6 Anchor-resolution rule (normative)

All dataset/field references in this document **MUST** resolve via:

* **JSON-Schema anchors** for shape, keys, and domains; and
* the **Dataset Dictionary** for paths, partitions, sort, format, licence, retention.
  The Artefact Registry **must not** be treated as a shape authority.

*Result:* Authority boundaries for S2 are explicit and unambiguous: **Schema→shape**, **Dictionary→path/partition/sort/licensing**, **Registry→licence/provenance**, with `tile_index` (S1) as the sole upstream universe. This is the basis against which all later sections (inputs, behaviour, validation, PAT) are enforced.

---

# 3. Identity, determinism & partitions *(Binding)*

## 3.1 Identity tokens & scope

* **Identity for S2 outputs:** `{parameter_hash}` **only**. `tile_weights` is parameter-scoped; it does **not** partition by `seed` or `fingerprint`. This follows the Dictionary entry for `tile_weights`. 

## 3.2 Partition law for `tile_weights`

* **Path family (Dictionary-owned):**
  `data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/`
  **Partitions:** `[parameter_hash]` (write once per partition).
  **Writer sort:** `[country_iso, tile_id]` (stable, deterministic merge order).
  **Format:** `parquet`. Implementations **MUST** write only under this partition family for a given run; no auxiliary files inside the dataset partition. 

## 3.3 Keys & uniqueness (Schema authority)

* **Primary key:** `[country_iso, tile_id]`.
* **Partition keys:** `[parameter_hash]`.
* **Sort keys:** `[country_iso, tile_id]`.
  All rows **MUST** satisfy PK uniqueness **within** a `{parameter_hash}` partition. Shape/keys are owned solely by the Schema anchor for `tile_weights`. 

## 3.4 Determinism & re-run identity

* **No RNG in S2:** outputs are a deterministic function of sealed inputs + governed parameters captured by `{parameter_hash}`.
* **Idempotence:** re-materialising `tile_weights` with the same inputs and `{parameter_hash}` **MUST** yield a **byte-identical** table (file order non-authoritative; identity = partitions + keys + content).

## 3.5 Determinism under parallelism *(Binding)*

* **Permitted parallel units:** per-country and/or fixed tile-blocks.
* **Required:** the final materialisation **MUST** result from a **stable merge ordered by `[country_iso, tile_id]`** (the Dictionary’s writer sort). Outcomes **MUST NOT** vary with worker count/scheduling; nondeterministic reducers are **forbidden**. 

## 3.6 Incremental recomputation & immutability *(Binding)*

* **Atomic publish:** writers **MUST** stage output outside the live partition and perform a single atomic move into `…/parameter_hash={parameter_hash}/` once complete.
* **Write-once:** republishing to an existing `{parameter_hash}` partition **MUST** be byte-identical or is a hard error.
* **Resume semantics:** on failure, recompute the affected unit(s) deterministically and re-stage; never patch files in-place under the live partition. *(This mirrors the established lineage/write discipline used in 1B.)* 

## 3.7 Path↔embed equality *(Binding)*

* If a future schema revision embeds any lineage field that also appears in the path (e.g., an optional `parameter_hash` column), the embedded value **MUST byte-equal** the corresponding path token. This preserves path↔row consistency across the layer’s datasets. 

*Consequence:* With `{parameter_hash}` as the **sole** partition, PK `[country_iso, tile_id]`, and stable writer sort, S2 outputs are reproducible and byte-stable across re-runs and parallel configurations, and they align exactly with the **Schema** (`#/prep/tile_weights`) and **Dictionary** (`#tile_weights`) authorities.

---

# 4. Inputs (sealed) *(Binding)*

S2 reads the **ratified S1 universe** and (optionally) a small set of ingress references. It does **not** read any 1A egress. Each input below is **sealed** by ID, path family, version, and schema anchor in the Dictionary/Registry; **JSON-Schema is the sole shape authority**.

## 4.1 `tile_index` — S1 universe of eligible tiles *(required)*

* **Anchors:** `schemas.1B.yaml#/prep/tile_index` (shape) and `dataset_dictionary.layer1.1B.yaml#tile_index` (path/partitions/sort).
* **Dictionary facts:** **status: approved**; **format: parquet**; path `data/layer1/1B/tile_index/parameter_hash={parameter_hash}/`; **partitioning: [parameter_hash]**; **ordering: [country_iso, tile_id]**; **licence: Proprietary-Internal**. 
* **Binding use in S2:** defines the complete row universe `(country_iso, tile_id)` and provides required geometry-derived columns (`centroid_lon/lat`, `pixel_area_m2`, `inclusion_rule`) for area-based or geometry-checked bases. No row may be created in `tile_weights` unless it exists here. *(FK/coverage checks bound in §8.)* 

## 4.2 `iso3166_canonical_2024` — ISO-2 country list *(FK target; read-only)*

* **Anchor:** `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`. 
* **Dictionary facts:** **approved**; **format: parquet**; path `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`; **licence: CC-BY-4.0**; **consumed_by: [1B]**; **retention: 1095 days**. 
* **Registry facts:** mirrors the same path/anchor; **licence: CC-BY-4.0**. 
* **Binding use in S2:** FK domain for `country_iso` (uppercase ISO-3166-1 alpha-2; placeholders `XX/ZZ/UNK` **forbidden**). *(Enforced in §8.)*

## 4.3 `world_countries` — country polygons *(read-only; optional for S2)*

* **Anchor:** `schemas.ingress.layer1.yaml#/world_countries`. 
* **Dictionary facts:** **approved**; **format: parquet**; path `reference/spatial/world_countries/2024/world_countries.parquet`; **licence: ODbL-1.0**. 
* **Registry facts:** mirrors same path/anchor; **licence: ODbL-1.0**; depends on ISO table. 
* **Binding use in S2:** available for **geometry-based validations** only (e.g., sanity that every `centroid` in S1 lies within its country). S2’s weighting **must not** change S1 geometry; primary weighting mass should come from the **basis** defined in §6.

## 4.4 `population_raster_2025` — population raster (COG) *(conditionally read-only)*

* **Anchor:** `schemas.ingress.layer1.yaml#/population_raster_2025`. 
* **Dictionary facts:** **approved**; **format: cog_geotiff**; path `reference/spatial/population/2025/population.tif`; **licence: ODbL-1.0**. 
* **Registry facts:** mirrors same path/anchor; **licence: ODbL-1.0**. 
* **Binding use in S2:** **only if** the governed **basis** in §6 requires population intensity. When basis ≠ population, S2 **must not** read this surface.

## 4.5 `tz_world_2025a` — time-zone polygons *(provenance only; not consumed by S2)*

* **Anchor:** `schemas.ingress.layer1.yaml#/tz_world_2025a`. 
* **Dictionary facts:** **approved**; **format: parquet**; path `reference/spatial/tz_world/2025a/tz_world.parquet`; **licence: ODbL-1.0**. 
* **Registry facts:** mirrors same path/anchor; **licence: ODbL-1.0**. 
* **Binding note:** listed for layer lineage; **S2 MUST NOT read** this dataset.

---

## 4.6 Licence & provenance requirements *(Binding)*

* Each sealed input **MUST** carry a **concrete** licence in Dictionary/Registry; current classes: **CC-BY-4.0** (ISO) and **ODbL-1.0** (world_countries, population_raster_2025, tz_world_2025a); **Proprietary-Internal** for `tile_index`. **Placeholders are forbidden.**
* S2 **MUST NOT** alter provenance (paths/versions/anchors) at runtime; inputs are resolved **only** via the Dictionary. 

## 4.7 Partitioning & immutability of inputs *(Binding)*

* **`tile_index`** is partitioned by `{parameter_hash}` and **MUST** be treated as immutable for the duration of a run. 
* Ingress references (`iso`, `world_countries`, `population_raster_2025`, `tz_world_2025a`) are **unpartitioned** in the Dictionary and **MUST** be treated as immutable during a run. 

## 4.8 Domain & FK constraints *(Binding)*

* `country_iso` in S2 **MUST** be uppercase ISO-2 present in `iso3166_canonical_2024`. *(FK check bound in §8.)* 
* Every `(country_iso, tile_id)` in `tile_weights` **MUST** appear in `tile_index` for the **same** `{parameter_hash}`. *(Coverage/consistency checks bound in §8.)* 

## 4.9 Out-of-scope inputs *(Binding)*

* Any dataset not listed in §4.1–§4.5 is **out of scope** for S2. In particular, **1A egress** (e.g., `outlet_catalogue`) and **S3 order surfaces** (e.g., `s3_candidate_set`) are **not** read by S2; S3 remains the inter-country order authority for other states, not for S2 weighting. 

*This completes S2’s sealed-inputs contract and aligns with the live Dictionary/Registry and schema anchors.*

---

# 5. Gate relationships *(Binding)*

## 5.1 Upstream consumer gate (context from 1A/S0)

* **S2 does not read any 1A egress**; therefore **S0’s 1A consumer gate is *not* a precondition to execute S2**. The Dictionary carries the 1A **validation bundle** only for discoverability (partition `fingerprint={…}` with the 1A bundle schema anchor).
* For coherence across Layer-1: any state that *does* read 1A egress (e.g., `outlet_catalogue`) must first verify `_passed.flag` by recomputing the bundle hash over the **ASCII-lex ordered** files listed in `index.json`, excluding the flag; **no PASS → no read**. *(S2 never performs this check because it doesn’t read 1A.)*

## 5.2 Pre-read checks for S1 input (tile_index) *(normative for S2)*

Before S2 reads **`tile_index`**, the reader **MUST** assert:

1. **Schema conformance** to `schemas.1B.yaml#/prep/tile_index` (PK `[country_iso, tile_id]`, partitions `[parameter_hash]`, writer sort `[country_iso, tile_id]`, required columns present).
2. **Dictionary/path law**: dataset exists only under
   `data/layer1/1B/tile_index/parameter_hash={parameter_hash}/` with `format: parquet`, `partitioning: [parameter_hash]`, `ordering: [country_iso, tile_id]`. 
   A failure of (1) or (2) is an **abort** for S2 (see §12: `E101_TILE_INDEX_MISSING` / `E108_WRITER_HYGIENE`).

## 5.3 Allowed reads (before any gate)

S2 **MAY** read **only**:

* `tile_index` (S1 output; required).
* Ingress references pinned in the Dictionary (read-only):
  – **`population_raster_2025`** (COG, **only when `basis="population"`**),
  – **`world_countries`** (optional; validations only, per §4.3),
  – the ISO FK surface.
  *(Per §4.5, `tz_world_2025a` is listed for layer lineage and **MUST NOT** be read by S2.)*

## 5.4 Prohibited accesses in S2

* **Prohibited:** any **1A egress** (e.g., `outlet_catalogue`) and any **S3 order surface** (e.g., `s3_candidate_set`). Across 1B, S3 remains the **sole inter-country order authority** for consumers that need order; S2 does **not** use it.

## 5.5 Gate-verification recipe for 1A consumers (for reference)

When a *downstream* 1B state (not S2) reads 1A egress for a `fingerprint=f`:

1. Locate `data/layer1/1A/validation/manifest_fingerprint=f/`.
2. Read **`index.json`**; list files by **ASCII-lex** `index.path`.
3. Compute `SHA256(concat(bytes(files in that order)))` (exclude `_passed.flag`).
4. Compare to `_passed.flag`’s `sha256_hex`. **Match ⇒ PASS; else ABORT.** 

## 5.6 Gate posture for S2 outputs

* **No S2 PASS bundle exists.** Acceptance of `tile_weights` is by **Schema** (`#/prep/tile_weights`) + **Dictionary** law (path/partition/sort/licence/retention) + §8 validation + §11 **PAT**; consumers must not invent additional “gate” semantics for S2.

## 5.7 Failure semantics (when a gate or pre-read check applies)

* If §5.2 fails (S1 input invalid/missing), S2 **MUST abort** with `E101_TILE_INDEX_MISSING` (or `E108_WRITER_HYGIENE` for path/partition violations).
* If an implementation attempts any prohibited access in §5.4, it **MUST abort** with `E108_WRITER_HYGIENE`.
* S2 **never** performs the 1A PASS check, but states that do must treat a mismatch as a **gate failure** and **abort** per §12. 

*Effect:* S2 is ingress+S1-only, with precise pre-read obligations for `tile_index`, no separate S2 gate, and a clear boundary against 1A/S3 surfaces. All enforcement rests on **Schema**/**Dictionary** authorities and the §8/§11 acceptance rules.

---

# 6. Normative behaviour *(Binding)*

> This section fixes *how* S2 must compute deterministic, fixed-decimal weights for every row of **`tile_index`** and materialise **`tile_weights`**. Shape is owned by the schema anchor for each dataset; path/partition/sort by the Dictionary.

## 6.1 Weighting basis *(Binding)*

S2 uses a **governed basis** to assign a non-negative mass **`m_i`** to each eligible tile `i = (country_iso, tile_id)` from **`tile_index`**:

* **Allowed basis values (enum):**

  * **`uniform`** — `m_i := 1` for all tiles in a country. *(No extra reads.)*
  * **`area_m2`** — `m_i := pixel_area_m2(i)` from **`tile_index`**. *(Uses S1’s area semantics on WGS84.)*
  * **`population`** — `m_i := population_intensity(i)` derived from **`population_raster_2025`** for the cell containing `i`. *(COG read; NODATA counts as zero.)* 

The chosen `basis` is part of the governed parameters captured by `{parameter_hash}` and **MUST** be disclosed in the run report (see §9). No other basis is permitted without updating this specification (see §13). 

**Constraints:**

* All masses **MUST** be **finite and ≥ 0**. Any negative or non-finite value is an error and SHALL be treated as **`E105_NORMALIZATION`**. If sanitisation yields `M_c=0` with `|U_c|>0`, validators expect the §6.7 uniform fallback; absence ⇒ **`E104_ZERO_MASS`**.
* If `basis = area_m2`, S2 **must** use the **`pixel_area_m2`** column from `tile_index` (S1’s definition is authoritative).
* If `basis = population`, reads are permitted **only** from `population_raster_2025` (Dictionary/ingress anchor). 

## 6.2 Normalisation domain *(Binding)*

Weights are **per-country** distributions. For each country `c`:

* Let **`U_c`** be the set of tiles in `tile_index` with `country_iso = c` (for the same `{parameter_hash}`); **no other tiles may appear** in S2. 
* Compute **`M_c := Σ_{i∈U_c} m_i`**. If `U_c = ∅` ⇒ `E103_ZERO_COUNTRY`.
* Define real weights **`w_i := m_i / M_c`** when `M_c > 0` (see §6.7 for zero-mass policy).

## 6.3 Fixed-dp quantisation *(Binding)*

Let **`dp ∈ ℕ₀`** be the governed decimal precision (declared in the run report). Define **`K := 10^dp`**. For each country `c`:

1. **Quota**: `q_i := w_i * K`.
2. **Base integers**: `z_i := ⌊ q_i ⌋` (floor).
3. **Residues**: `r_i := q_i − z_i` (in `[0,1)`).
4. **Shortfall**: `S := K − Σ z_i` (an integer in `[0, |U_c|)`).

**Largest-remainder allocation (deterministic):**
Allocate **`+1`** to exactly **`S`** tiles with the **largest** `r_i`, breaking ties by ascending numeric `tile_id`. The final fixed-dp integers are:

* **`weight_fp(i) := z_i + 1`** if `i` is among the top-`S` residues (after tie-break), else **`weight_fp(i) := z_i`**.

**Required invariants per country `c`:**

* **Exact sum**: `Σ weight_fp = K` (i.e., **`10^dp`**) — no error allowed.
* **Monotone residue law**: If `m_a > m_b` and `⌊q_a⌋ = ⌊q_b⌋`, then either `weight_fp(a) = weight_fp(b) + 1` because `r_a > r_b`, or both remain equal if both are not selected; if `⌊q_a⌋ > ⌊q_b⌋` then `weight_fp(a) ≥ weight_fp(b)` always (see §6.5).

> **Numeric rule:** Implementations **MUST** compute steps (1)–(4) so that the result is **independent of floating-point rounding**. It is acceptable to compute `q_i` using integer arithmetic via `(m_i * K, M_c)` with exact comparisons on the fractional parts; if binary64 is used, it **MUST** reproduce the same allocation as the exact method. (Validators will recompute and compare.)

## 6.4 Tie-break order *(Binding)*

* The tie-break for residue selection is **strict**: **descending `r_i`**, then **ascending numeric `tile_id`**.
* The tie-break **MUST** be stable across re-runs and independent of task count/scheduling (see §3.5). 

## 6.5 Monotonicity & stability *(Binding)*

For each country `c`:

* **Mass monotonicity:** If `m_a ≥ m_b`, then after quantisation **`weight_fp(a) ≥ weight_fp(b)`** except a possible difference of **1 unit** caused by residue allocation.
* **Residue stability:** If `m_a = m_b`, then `q_a = q_b` ⇒ `r_a = r_b`; any difference in `weight_fp` can only be due to the deterministic **`tile_id`** tie-break.
* **No cross-country effects:** The distribution in `c` **must not** depend on tiles in other countries (no global renormalisation).

## 6.6 Valid mass sources *(Binding)*

* **`uniform`** requires **no** extra reads (pure function of `U_c`).
* **`area_m2`** uses the **`pixel_area_m2`** column from `tile_index` (authoritative S1 semantics; ellipsoidal; positive).
* **`population`** uses **`population_raster_2025`** intensities for the tile’s cell; NODATA ⇒ `0`. Reads must resolve via the Dictionary ingress anchor (COG). 

## 6.7 Zero/empty country policy *(Binding)*

* **Empty country (`U_c = ∅`)** ⇒ **abort** with `E103_ZERO_COUNTRY`.
* **Zero-mass country (`M_c = 0` with `|U_c| > 0`)** ⇒ **deterministic fallback to `uniform`** for that country: set `m_i := 1` for all `i ∈ U_c`, recompute §6.2–§6.3, and record `zero_mass_fallback=true` in the run report (§9). If fallback is not engaged when required ⇒ `E104_ZERO_MASS`.

## 6.8 Determinism & prohibitions *(Binding)*

* **No RNG:** S2 is deterministic; **no** stochastic smoothing, sampling, or noise injection.
* **No universe drift:** S2 **must not** add/remove/merge rows vs `tile_index`.
* **No out-of-scope reads:** Only the inputs in §4 may be read (and only as permitted by the chosen `basis`). 

## 6.9 Write discipline *(Binding)*

Materialise `tile_weights` **only** under the Dictionary partition family with writer sort `[country_iso, tile_id]` and format `parquet`; file order is non-authoritative. Publishing is **atomic** (stage → fsync → atomic rename). Re-publishing to the same `{parameter_hash}` must be **byte-identical** or is a failure. *(See §3 & §7 for the authoritative path/sort law.)* 

---

**Binding effect:** With §6 in force, S2 produces a **per-country**, **deterministic**, **fixed-dp** distribution over the exact `tile_index` universe, with a **largest-remainder** integerisation that guarantees **exact sums**, a **stable tie-break**, and **monotone** behaviour, while respecting the **Schema**/**Dictionary** authorities and the sealed-input boundaries.

---

# 7. Output dataset *(Binding)*

## 7.1 Dataset ID & schema anchor

* **ID:** `tile_weights`
* **Schema (sole shape authority):** `schemas.1B.yaml#/prep/tile_weights`.
  As of the current schema, this anchor **fixes keys and required columns** — **PK** = `[country_iso, tile_id]`, **partition_keys** = `[parameter_hash]`, **sort_keys** = `[country_iso, tile_id]`, and required columns `country_iso`, `tile_id`, `weight_fp`, `dp`. 

## 7.2 Path, partitions, ordering & format (Dictionary law)

* **Path family:** `data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/`
* **Partitions:** `[parameter_hash]` (one write per partition; write-once)
* **Writer sort:** `[country_iso, tile_id]` (stable, deterministic merge order)
* **Format:** `parquet`
  These properties are governed by the **Dataset Dictionary** entry for `tile_weights` and **MUST** be observed exactly. 

## 7.3 Licence, retention, PII (Dictionary authority)

* **Licence:** `Proprietary-Internal`
* **Retention:** `365` days
* **PII:** `false`
  Implementations **MUST NOT** override these values at write time. 

## 7.4 Shape semantics *(schema-owned)*

The **names/types live in the schema**; the following **semantics are binding** and are reflected by those columns:

* A **fixed-decimal integer** weight per row (the quantised result of §6.3), and the **scale exponent** `dp` used for that run.
* PK columns `(country_iso, tile_id)` as per the schema keys above.
* Optional, non-authoritative audit fields (e.g., a real-valued weight or a declared basis enum) may be present; if present they **do not** alter acceptance criteria.

## 7.5 Foreign-key & coverage obligations

* Every `(country_iso, tile_id)` in `tile_weights` **MUST** appear in **`tile_index`** for the same `{parameter_hash}` (coverage).
* `country_iso` **MUST** be an uppercase ISO-3166-1 alpha-2 present in the ingress ISO table (FK domain). *(FK checks are enforced in §8.)* 

## 7.6 Immutability & atomic publish

* Writers **MUST** stage outside the final partition and perform a single atomic move into `…/parameter_hash={parameter_hash}/`.
* A subsequent publish to the same partition **MUST** be **byte-identical** or is a hard error.
* File order is **non-authoritative**; identity is **(partition keys + PK + content)**. 

## 7.7 Consumer obligations (minimum)

Consumers and validators **MUST** assert, at minimum:

* **Schema conformance** to `#/prep/tile_weights` (keys/partitions/sort as per 7.1). 
* **Dictionary hygiene:** dataset appears **only** under the declared partition family with `format=parquet` and writer sort `[country_iso, tile_id]`. 
* **FK/coverage:** every row is present in `tile_index` for the same `{parameter_hash}`; ISO FK holds.

*Result:* `tile_weights` is contract-defined by the **Schema** (keys **and required columns**) and the **Dictionary** (path/partition/sort/licence/retention). All other behavioural guarantees (normalisation, fixed-dp quantisation, monotonicity, determinism) are bound in §6 and enforced in §8.

---

# 8. Validation & acceptance criteria *(Binding)*

> A run of **S2** is **accepted** only if **all** checks below pass. “Validator” refers to any process asserting conformance of the produced **`tile_weights`**. Shape is governed by the **Schema**; path/partitions/sort/licence/retention by the **Dictionary**.

## 8.1 Schema conformance (MUST)

* The materialised dataset **MUST** conform to **`schemas.1B.yaml#/prep/tile_weights`** as published, including **enumerated required columns** and keys (PK/partition/sort). Validators enforce the schema’s columns/keys as authoritative.

## 8.2 Dictionary/path law (MUST)

* The dataset **MUST** be written only under the Dictionary-declared path family:
  `data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/` with `format: parquet`, `partitioning: [parameter_hash]`, and **writer sort** `[country_iso, tile_id]`.
  Any stray files or alternate partitioning/order ⇒ **fail** (`E108_WRITER_HYGIENE`). 
* Licence/retention/PII entries for `tile_weights` **MUST** be present in the Dictionary (Proprietary-Internal / 365 / PII=false). Absence or override at write-time ⇒ **fail**. 

## 8.3 Referential integrity & coverage (MUST)

* **FK to S1:** Every `(country_iso, tile_id)` in `tile_weights` **MUST** appear in **`tile_index`** for the **same `{parameter_hash}`**. **No extras.** 
* **Coverage:** For each `country_iso`, the **row count equals** the `tile_index` row count (no drops/coalesces). **No misses.** 
* **ISO FK:** `country_iso` **MUST** be uppercase ISO-3166-1 alpha-2 present in the ingress ISO surface. 

## 8.4 Basis & `dp` disclosure (MUST)

* The run **MUST** disclose `basis ∈ {"uniform","area_m2","population"}` and `dp ∈ ℕ₀` in the run report (§9). The **same `dp` value** applies to the entire partition.
* A **`dp` column MUST exist in `tile_weights`** and **MUST** equal the run-report `dp` for **all** rows.

## 8.5 Normalisation & fixed-dp correctness (MUST)

For each country `c`:

1. Reconstruct the **mass** `m_i` for each tile `i ∈ U_c` per the declared **basis** (see §6.1/§6.6); if `basis=area_m2`, read from `tile_index.pixel_area_m2`; if `basis=population`, derive from `population_raster_2025` (NODATA⇒0). 
2. Compute `M_c = Σ m_i`.

   * If `|U_c| = 0` ⇒ **fail** `E103_ZERO_COUNTRY`.
   * If `|U_c| > 0` and `M_c = 0` ⇒ validator **expects uniform fallback** (§6.7). Absence of fallback ⇒ **fail** `E104_ZERO_MASS`.
3. Let `K = 10^dp`. Form quotas `q_i = (m_i / M_c) * K`, base integers `z_i = ⌊q_i⌋`, residues `r_i = q_i − z_i`, shortfall `S = K − Σ z_i`.
4. **Residue law:** Identify exactly **S** tiles with largest `r_i`, breaking ties **by ascending numeric `(tile_id)`**; each selected tile receives `+1`.
5. **Compare:** `weight_fp(i)` in `tile_weights` **MUST** equal `z_i` (+1 for the residue-selected tiles).
6. **Exact sum:** `Σ weight_fp = K` **MUST hold exactly** per country (no rounding slack).
7. **Monotonicity:** If `m_a ≥ m_b`, then `weight_fp(a) ≥ weight_fp(b)` allowing at most the 1-unit residue effect defined above; systematic violations ⇒ **fail** `E106_MONOTONICITY`.

> **Numeric invariance:** Validators **MUST** not accept implementations whose allocation differs from the exact method due to floating-point rounding. (Implementations MAY compute quotas/ordering using exact integer comparisons; if binary64 is used, it **MUST** reproduce the exact allocation.)

## 8.6 Basis-specific constraints (MUST)

* **`uniform`** ⇒ masses are all **1** (per country).
* **`area_m2`** ⇒ masses come **only** from `tile_index.pixel_area_m2` (positive, ellipsoidal). **Any** alternate area computation in S2 ⇒ **fail**. 
* **`population`** ⇒ masses come **only** from `population_raster_2025` via Dictionary/ingress; random resampling/smoothing is **forbidden**; NODATA ⇒ 0. 

## 8.7 Determinism & idempotence (MUST)

* For fixed sealed inputs and the same `{parameter_hash}`, re-materialising `tile_weights` **MUST** yield a **byte-identical** partition (file order non-authoritative).
* Validators **MUST** compute the **determinism receipt** (ASCII-lex concatenation of partition files → SHA-256) and require equality across re-runs; mismatch ⇒ **fail** `E107_DETERMINISM`. *(Receipt format in §9.)*

## 8.8 Writer discipline & immutability (MUST)

* **Writer sort:** files **MUST** be written in `[country_iso, tile_id]` order so merges are stable/deterministic.
* **Atomic publish & write-once:** partition appears atomically; any later publish to the same `{parameter_hash}` must be **byte-identical**; else ⇒ **fail** `E108_WRITER_HYGIENE`. 

## 8.9 Performance acceptance tests (PAT) (MUST)

* Validators **MUST** execute the PAT suite defined in **§11** (I/O amplification, runtime bound, memory/FD caps, determinism re-run). Exceeding **any** bound ⇒ **fail** `E109_PERF_BUDGET`. *(Counters supplied in §9.)*

## 8.10 Evidence & artefacts (MUST)

The following **MUST** be emitted **outside** the dataset partition (control-plane artefacts/logs):

* **Run report**: `parameter_hash`, `basis`, `dp`, `rows_emitted`, determinism receipt, and per-country counts.
* **Per-country normalisation summaries**: `|U_c|`, `Σ m_i`, `Σ w_i` (real), `Σ weight_fp` (= `10^dp`), number of residue allocations, `zero_mass_fallback` flags.
* **PAT counters**: the metrics required by §11 (I/O bytes, wall clock, memory/FD peaks, worker count, chunk size).
  Absence/inaccessibility ⇒ **fail** `E108_WRITER_HYGIENE` or `E109_PERF_BUDGET` depending on which check is blocked.

## 8.11 Failure semantics (MUST)

Fail with the canonical code(s) in §12 when any check above fails:

* `E101_TILE_INDEX_MISSING` (S1 input invalid/missing), `E102_FK_MISMATCH` (tile not in `tile_index`), `E103_ZERO_COUNTRY`, `E104_ZERO_MASS`, `E105_NORMALIZATION` (Σ `weight_fp` ≠ `10^dp`), `E106_MONOTONICITY`, `E107_DETERMINISM`, `E108_WRITER_HYGIENE`, `E109_PERF_BUDGET`.

*Result:* Acceptance requires simultaneous compliance with the **Schema** anchor for `tile_weights` (as published), the **Dictionary** path/partition/sort law, strict **FK & coverage** against `tile_index`, **deterministic** fixed-dp allocation with **exact sums**, **stable tie-break**, and a **passing PAT** envelope.

---

# 9. Observability & audit *(Non-binding for results, **binding for presence**)*

> S2 has **no gate bundle** and **no RNG logs**. Observability here means the **evidence you must emit** so validators can prove §§6–8 and §11 were obeyed. These artefacts are **required to exist** but **do not** change the semantics of `tile_weights`. They **must not** be written inside the dataset partition (`…/tile_weights/parameter_hash={parameter_hash}/`).

## 9.1 Deliverables overview *(Binding for presence)*

An accepted S2 run **MUST** expose, outside the dataset partition, and retrievable by the validator:

* **S2 run report** — one machine-readable JSON object (see §9.2).
* **Per-country normalization summaries** — one object per ISO country (as an array in the report **or** JSON-lines; see §9.3).
* **Determinism receipt** — composite SHA-256 over the produced partition files (see §9.4).
* **PAT counters** — performance/operational metrics required by §11 (see §9.5).

Presence is **binding**; content is checked against §8 and §11. The observability artefacts themselves are **not** a gate.

## 9.2 S2 run report — required fields *(Binding for presence)*

A single JSON object (e.g., `s2_run_report.json`) **MUST** contain at least:

* `parameter_hash` (hex64) — identifies the partition validated.
* `basis` (`"uniform" | "area_m2" | "population"`) — weighting basis actually used.
* `dp` (non-negative integer) — the fixed-decimal precision (applies to the entire partition).
* `ingress_versions` — `{ iso3166: <string>, world_countries: <string>, population_raster: <string>|null }`
* `rows_emitted` — total rows written to `tile_weights`.
* `countries_total` — number of ISO countries processed.
* `determinism_receipt` — object per §9.4.
* `pat` — object with the §11 counters **and baselines** captured (see §9.5).

This report **MUST** be available to the validator but **MUST NOT** be stored under the `tile_weights` partition.

## 9.3 Per-country normalization summary — required fields *(Binding for presence)*

For each ISO2 country `c`, emit a JSON object with:

* `country_iso` (ISO-3166-1 alpha-2)
* `tiles` — `|U_c|` (row count in `tile_index` for `c`)
* `mass_sum` — `Σ m_i` according to the declared **basis**
* `prequant_sum_real` — `Σ w_i` (should be 1.0 before quantization)
* `K` — `10^dp`
* `postquant_sum_fp` — `Σ weight_fp` (must equal `K`)
* `residue_allocations` — number of `+1` allocations (the shortfall `S`)
* `zero_mass_fallback` — `true|false` (see §6.7)
* optional `notes`

Delivery **MAY** be an array inside the run report **or** a JSON-lines stream (e.g., log lines prefixed `AUDIT_S2_COUNTRY:`). Validators **MUST** be able to retrieve these objects for the run.

## 9.4 Determinism receipt — composite hash *(Binding for presence; method is normative)*

Compute a **composite SHA-256** over `…/tile_weights/parameter_hash={parameter_hash}/` **files only**:

1. List all files under the partition as **relative paths**; **ASCII-lex sort** them.
2. Concatenate the raw bytes in that order; compute SHA-256; encode as lowercase hex64.
3. Record in the run report as
   `determinism_receipt = { "partition_path": "<path>", "sha256_hex": "<hex64>" }`.

This mirrors the layer’s established hashing discipline and is used by validators to assert byte-identical re-runs (§8.7).

## 9.5 Performance & operational telemetry (ties to §11) *(Binding for presence)*

Emit, at minimum:

* `wall_clock_seconds_total`, `cpu_seconds_total`
* `countries_processed`, `rows_emitted`
* `bytes_read_tile_index_total`, `bytes_read_raster_total` (if `basis="population"`), `bytes_read_vectors_total` (if applicable)
* `max_worker_rss_bytes` (peak per worker), `open_files_peak`
* concurrency facts: `workers_used`, `chunk_size` (if block-parallel)
* **Baselines (measured at start of run; §11.1):**
  `io_baseline_ti_bps` (tile_index),
  `io_baseline_raster_bps` (population basis only),
  `io_baseline_vectors_bps` (if vectors read).

Validators use these counters to execute **Performance Acceptance Tests** (§11). Exceeding any bound fails with `E109_PERF_BUDGET`.

## 9.6 Failure event schema *(Binding for presence)*

On any failure, emit an event object:

* `event`: `"S2_ERROR"`
* `code`: one of §12 (e.g., `E101_TILE_INDEX_MISSING`, `E104_ZERO_MASS`, `E105_NORMALIZATION`, `E106_MONOTONICITY`, `E107_DETERMINISM`, `E108_WRITER_HYGIENE`, `E109_PERF_BUDGET`)
* `at`: RFC-3339 UTC
* `parameter_hash`
* optional `country_iso`
* optional `tile_id` (when relevant)

This event augments normal process exit semantics and enables structured audit.

## 9.7 Delivery location & retention *(Binding for presence)*

* **Location:** All artefacts in §9.1 **MUST** be exposed as **control-plane artefacts or logs** and **MUST NOT** be placed inside the `tile_weights` partition. Keep the dataset partition schema-clean.
* **Retention:** Retain the run report and per-country summaries for **≥ 30 days** (minimum ops retention). This retention does **not** alter dataset semantics.

## 9.8 Privacy & licensing posture *(Binding for presence)*

* Do **not** emit PII; country codes, counts, and aggregates are non-PII.
* When echoing ingress provenance in reports, use **Dictionary** IDs/versions (not raw file hashes). Licensing remains as per the ingress Dictionary/Registry entries.

*Result:* Observability for S2 is evidence-complete (run report + country summaries + determinism receipt + PAT metrics), non-intrusive (no files in the dataset partition), and aligned with the deterministic, fixed-dp contract and §11 PAT enforcement.

---

# 10. Security, licensing, retention *(Binding)*

## 10.1 Security posture & access control

* **Closed-world:** S2 reads only **sealed, version-pinned** artefacts resolved via the **Dataset Dictionary** (no literal paths; no network enrichment). JSON-Schema is the **sole shape authority**. 
* **Dictionary-only resolution:** All inputs/outputs must be addressed by **Dictionary IDs**; paths/partitions/sort/licence/retention come from the Dictionary; the Artefact Registry provides provenance/licence but is **not** a shape authority. 
* **Least-privilege & secrets:** Use least-privilege identities; do **not** emit secrets into datasets/logs; if credentials are required, use the platform secret store (non-semantic for data).
* **Encryption at rest:** Output objects **MUST** be encrypted at rest (e.g., SSE-KMS or equivalent). Buckets should deny unencrypted PUTs.
* **Atomicity & immutability:** Publish via **stage → fsync → atomic rename**; the partition for a given `{parameter_hash}` is **write-once**. Any subsequent publish to the same identity must be **byte-identical** or is a failure (see §7/§8). 

## 10.2 Licensing (authority & classes)

* **Licence authority:** Licence classes are governed by the **Dictionary/Registry**. Implementations **MUST NOT** override them.
* **S2 output licence:** `tile_weights` → **Proprietary-Internal** (Dictionary). 
* **Ingress/S1 inputs (read-only) licence classes:**
  – `iso3166_canonical_2024` → **CC-BY-4.0**. 
  – `world_countries` → **ODbL-1.0**. 
  – `population_raster_2025` → **ODbL-1.0** (used only when `basis="population"`). 
  – `tile_index` (S1 output) → **Proprietary-Internal** (Dictionary). 
* **No placeholders:** A missing or placeholder licence in Dictionary/Registry is **run-fail** under governance.

## 10.3 Retention windows (authority & values)

* **Retention authority:** Retention is governed by the **Dictionary**; implementations **must not** change it at write-time. 
* **S2 output retention:** `tile_weights` retains for **365 days** (Dictionary). 
* **Ingress retention (for reference):** ISO/world/tz/raster references retain for **≈1095 days** per Dictionary. 

## 10.4 Privacy & PII posture

* All sealed inputs listed for S2 and the S2 output `tile_weights` are **`pii:false`** in the Dictionary. S2 **must not** introduce PII or re-identification signals; observability artefacts (§9) use **codes & counts only**. 

## 10.5 Validity windows & version pinning

* If governance declares **validity windows** for references/configs, S2 **must** treat out-of-window artefacts as **abort** (or **warn+abort** where specified).
* Artefacts without validity windows are **digest/ID pinned** via the Dictionary/Registry entries; S2 **must not** substitute alternative paths or versions at runtime. 

## 10.6 Prohibitions (fail-closed)

S2 **MUST NOT**:

* read any **1A egress** or **S3 order surface** (S2 is ingress+S1 only); see §5 for gate boundaries.
* bypass Dictionary resolution with literal paths or override Dictionary licence/retention values at write time. 
* publish non-schema artefacts into the dataset partition (observability lives **outside** `…/tile_weights/parameter_hash={parameter_hash}/`).

## 10.7 Compliance checklist *(Binding for acceptance)*

A conformant S2 run **MUST** demonstrate at review time:

1. **Licence fields present/correct** for `tile_weights` and all sealed inputs (classes as listed in §10.2).
2. **Retention windows** match the Dictionary (365 days for `tile_weights`; ingress ~1095 days).
3. **Encryption & atomicity**: evidence of encryption at rest and stage→fsync→atomic-rename publish; partition is write-once (any re-publish is byte-identical). 
4. **No PII** introduced; observability artefacts contain only codes/counts; delivery is **outside** the dataset partition (§9). 

*Binding effect:* §10 locks S2 to the platform’s **security rails** (closed-world, Dictionary-only, encryption at rest, atomic publish), enforces **licence/retention governance** (Proprietary-Internal for `tile_weights`; CC-BY/ODbL for ingress), and keeps all outputs and evidence **non-PII**, immutable, and auditable.

---

# 11. Performance, scalability & operational envelope *(Binding)*

> These limits are **objective and validator-enforceable**. They rely on the counters in **§9.5** and the contract authorities (Schema for shape; Dictionary for path/partition/sort/licence/retention). A breach of any **MUST** bound is `E109_PERF_BUDGET` per §12.

## 11.1 Throughput & runtime bounds *(MUST)*

Define the following per run (reported in the run report; see §9.2/§9.5):

* `B_ti` = **bytes_read_tile_index_total**
* `B_r`  = **bytes_read_raster_total** (0 when `basis ≠ "population"`)
* `B_v`  = **bytes_read_vectors_total** (0 unless vectors are read for validations)
* `S_ti` = on-disk size of **tile_index** partition (sum of object sizes)
* `S_r`  = on-disk size of **population_raster_2025** (if used)
* `S_v`  = on-disk size of vector refs used (ISO + world_countries, if read)

**I/O amplification (per surface):**

* `B_ti / S_ti ≤ 1.25`
* If `basis="population"`: `B_r / S_r ≤ 1.25`, else `B_r = 0`
* If vectors are read: `B_v / S_v ≤ 1.25`
  Violations ⇒ **fail** `E109_PERF_BUDGET`.

**Baseline throughput & wall-clock bound:** Measure sustained read baselines at start:

* `io_baseline_ti_bps`: stream ≥1 GiB contiguously from the **tile_index** partition family
* If `basis="population"`: `io_baseline_raster_bps` from **population_raster_2025** (COG)
* If vectors are read: `io_baseline_vectors_bps` from the combined vector inputs

Then require:

```
wall_clock_seconds_total
  ≤ 1.75 × ( B_ti/io_baseline_ti_bps
           + B_r /io_baseline_raster_bps
           + B_v /io_baseline_vectors_bps ) + 300
```

(1.75× headroom + 300 s setup budget.) Violation ⇒ **fail** `E109_PERF_BUDGET`.

## 11.2 Memory & I/O budgets *(MUST)*

* **Peak memory per worker:** `max_worker_rss_bytes ≤ 1.0 GiB`
* **Temp disk per worker:** ≤ **2 GiB**
* **Open files peak:** `open_files_peak ≤ 256`
* **Streaming requirement:** **No full-partition or full-country materialisation** in memory; memory use is `O(window)`, not `O(|tile_index|)`.
  Any breach ⇒ **fail** `E109_PERF_BUDGET`.

## 11.3 Parallelism model (deterministic) *(MUST)*

* **Allowed:** per-country and/or fixed **tile-block** parallelism.
* **Required merge:** final materialisation is a **stable merge ordered by `[country_iso, tile_id]`** (Dictionary writer sort). Outcomes **must not** vary with worker count/scheduling; nondeterministic reducers are **forbidden**. 

## 11.4 Determinism under contention *(MUST)*

* **Pre-emption/resume:** reprocessing any chunk produces identical rows; merge remains byte-stable.
* **Atomicity:** publish is **stage → fsync → atomic rename**; partitions are **write-once** (any non-identical re-publish fails). 

## 11.5 Back-pressure, retries & cleanup *(MUST)*

* **Retries:** at most **3** attempts per chunk; retry logic must not change results (no random jitter that affects ordering).
* **Back-pressure:** throttle so memory/FD caps in §11.2 are never exceeded.
* **Cleanup:** on failure, no partials become visible under the live partition; re-stage and atomically replace only when complete.

## 11.6 Environment tiers *(Binding for PAT execution)*

* **DEV:** functional only on a small ISO subset (≤ 5 countries). No performance claims.
* **TEST:** same code path as PROD; PAT **may** run on a fixed ¼-world subset.
* **PROD (acceptance):** PAT **MUST** run on the **full** ingress set; acceptance/fail derives **only** from PROD PAT. (Paths/format/licence remain those in the Dictionary.) 

## 11.7 PAT definitions & pass/fail *(MUST)*

Validators execute the PAT using the §9 artefacts:

1. **Counters present:** `wall_clock_seconds_total`, `cpu_seconds_total`, `countries_processed`, `rows_emitted`, `bytes_read_tile_index_total`, `bytes_read_raster_total` (if population), `bytes_read_vectors_total` (if used), `max_worker_rss_bytes`, `open_files_peak`, `workers_used`, `chunk_size`. **Absence ⇒ fail** (`E109_PERF_BUDGET`).
2. **Baselines present:** `io_baseline_ti_bps` (and, when applicable, `io_baseline_raster_bps`, `io_baseline_vectors_bps`). **Absence ⇒ fail** (`E109_PERF_BUDGET`).
3. **I/O amplification:** enforce §11.1 ratios using object-store sizes for `S_ti`, `S_r`, `S_v`. **Fail ⇒ `E109_PERF_BUDGET`.**
4. **Runtime bound:** compute the wall-clock inequality from §11.1 with the recorded baselines; compare to `wall_clock_seconds_total`. **Fail ⇒ `E109_PERF_BUDGET`.**
5. **Memory/FD caps:** enforce §11.2. **Fail ⇒ `E109_PERF_BUDGET`.**
6. **Determinism check:** **re-run S2** on the same `{parameter_hash}` with a **different** worker count; recompute the **determinism receipt** (ASCII-lex ordered partition bytes → SHA-256). Receipts **must match** byte-for-byte; mismatch ⇒ **fail** `E107_DETERMINISM`.
7. **Writer law & atomicity:** confirm Dictionary path/partition/format and writer sort; verify atomic publish (no partials). **Fail ⇒ `E108_WRITER_HYGIENE`.** 

---

**Binding effect:** An S2 run passes only if it simultaneously satisfies **Schema** (shape/keys), **Dictionary** (path/partition/sort/licence/retention), **deterministic fixed-dp** behaviour (§6), and **all** PAT bounds above—verified from the §9 evidence.

---

# 12. Failure modes & canonical error codes *(Binding)*

> A run of **S2** is **rejected** if **any** condition below is triggered. On first detection the writer **MUST** abort, emit the failure event (§9.6), and ensure **no partials** become visible in `…/tile_weights/parameter_hash={parameter_hash}/` (atomic publish law, write-once). Shape authority = **Schema**; path/partition/sort/licence/retention = **Dictionary**; sealed inputs = **S1 `tile_index`** and ingress anchors; behaviour = **this S2 spec** (§6–§11).

## E101_TILE_INDEX_MISSING — S1 input absent or non-conformant *(ABORT)*

* **Trigger (MUST):** `tile_index` for the target `{parameter_hash}` is missing **or** fails its Schema/Dictionary checks (PK/partition/sort/required columns/path/format).
* **Detection:** Pre-read checks in §5.2 fail.
* **Evidence:** Failure event with `code=E101_TILE_INDEX_MISSING`, include `{parameter_hash}` and a short reason (e.g., “schema key mismatch” / “path not found”).
* **Authority refs:** §5.2, §7.5, §8.3.

## E102_FK_MISMATCH — Row not present in `tile_index` *(ABORT)*

* **Trigger (MUST):** Any `(country_iso, tile_id)` emitted by S2 is not present in S1’s `tile_index` for the same `{parameter_hash}`.
* **Detection:** Coverage/FK check in §8.3.
* **Evidence:** Failure event with `code=E102_FK_MISMATCH`, include example key(s).
* **Authority refs:** §6.2 (universe), §7.5, §8.3.

## E103_ZERO_COUNTRY — Empty country universe *(ABORT)*

* **Trigger (MUST):** For some ISO `c` selected by the run, `U_c = ∅` (no eligible tiles) even though S2 attempts to produce weights for `c`.
* **Detection:** §6.2 detects empty `U_c` before normalisation.
* **Evidence:** Failure event with `code=E103_ZERO_COUNTRY`, include `country_iso`.
* **Authority refs:** §6.2, §8.5(2).

## E104_ZERO_MASS — Zero total mass without fallback *(ABORT)*

* **Trigger (MUST):** `|U_c| > 0` but `M_c = Σ m_i = 0` and the **uniform fallback** of §6.7 is **not** engaged (or engaged inconsistently).
* **Detection:** §8.5(2) basis recomputation + fallback expectation.
* **Evidence:** Failure event with `code=E104_ZERO_MASS`, include `country_iso` and basis.
* **Authority refs:** §6.1, §6.7, §8.5.

## E105_NORMALIZATION — Fixed-dp sum or `dp` consistency error *(ABORT)*

* **Trigger (MUST):** Any of:
  – For any `country_iso`, the integerised sum **does not equal** `10^dp`; or
  – Rows in the same partition disagree on `dp`; or
  – **Invalid mass domain** detected in §6.1 (any negative or non-finite `m_i`).
* **Detection:** §8.5(6) exact-sum check; §8.4 `dp` disclosure/consistency.
* **Evidence:** Failure event with `code=E105_NORMALIZATION`, include `country_iso`, observed Σ`weight_fp`, expected `10^dp`, and `dp` value(s).
* **Authority refs:** §6.1, §6.3, §8.4–§8.5.

## E106_MONOTONICITY — Monotone/residue law violated *(ABORT)*

* **Trigger (MUST):** There exist tiles `a,b` in the same country with `m_a ≥ m_b` but **after** quantisation `weight_fp(a) < weight_fp(b)` beyond the single-unit residue effect defined in §6.3 **or** tie-break is not `(tile_id)` ascending among equal residues.
* **Detection:** §8.5(7) monotonicity and residue-order checks.
* **Evidence:** Failure event with `code=E106_MONOTONICITY`, include `country_iso` and a minimal counterexample `(tile_id_a, tile_id_b)`.
* **Authority refs:** §6.3–§6.5, §8.5(4,7).

## E107_DETERMINISM — Re-run produces different bytes *(ABORT)*

* **Trigger (MUST):** Re-running S2 on the same inputs and `{parameter_hash}` yields a **different** determinism receipt (ASCII-lex partition hash) or content differences.
* **Detection:** §11.7(6) determinism check; §9.4 receipt comparison.
* **Evidence:** Failure event with `code=E107_DETERMINISM`, include both receipts.
* **Authority refs:** §3.4–§3.6, §8.7, §9.4, §11.7.

## E108_WRITER_HYGIENE — Path/partition/sort/format/immutability/evidence hygiene *(ABORT)*

* **Trigger (MUST):** Any of: wrong path family; wrong partitioning; writer sort not `[country_iso, tile_id]`; non-parquet files **inside** the dataset partition; partial visibility (non-atomic publish); re-publish not byte-identical; missing Dictionary licence/retention/PII; **required evidence** (run report / per-country summaries) not exposed to validators.
* **Detection:** §7.2–§7.6 & §8.2 & §8.8 checks; §9 presence checks.
* **Evidence:** Failure event with `code=E108_WRITER_HYGIENE`, include a concise reason.
* **Authority refs:** §7, §8.2/§8.8/§8.10, §9.

## E109_PERF_BUDGET — Performance/operational envelope exceeded *(ABORT)*

* **Trigger (MUST):** Any §11 bound is exceeded (I/O amplification ratios, wall-clock inequality, memory/FD caps) **or** PAT counters required to evaluate those bounds are missing/invalid.
* **Detection:** §11.1–§11.7 PAT execution using §9.5 counters.
* **Evidence:** Failure event with `code=E109_PERF_BUDGET`, include failing metric(s) and recorded thresholds.
* **Authority refs:** §9.5, §11.

---

## 12.1 Failure handling *(normative)*

* **Abort semantics:** On any E10x, the writer **MUST** stop the run; **no** files are to be published under the live `…/tile_weights/parameter_hash={parameter_hash}/` partition unless materialisation is complete and **passes** all checks. (Atomic publish; write-once.)
* **Event emission:** Emit the **failure event** in §9.6 with the canonical `code`, timestamp, `parameter_hash`, and, where relevant, `country_iso`/`tile_id`.
* **Multi-error policy:** If multiple conditions are detected, the writer **MAY** emit multiple events; acceptance remains **failed**.
* **No ad-hoc gates:** S2 defines **no** `_passed.flag`; do **not** create bespoke gates for S2 outputs. Conformance is via Schema/Dictionary checks, §6 behaviour, §8 acceptance, and §11 PAT.

## 12.2 Code space & stability *(normative)*

* **Reserved codes:** `E101`–`E109` are reserved for S2 as defined above.
* **SemVer impact:** Introducing/removing codes or changing triggers is **MINOR** if strictly tightening and does **not** flip prior pass→fail on reference runs; otherwise **MAJOR** (see §13).

---

# 13. Change control & compatibility *(Binding)*

> This section defines how **S2 — Tile Weights** evolves without breaking consumers. It applies to: (a) this state specification; (b) the **`tile_weights`** schema anchor; and (c) the **Dictionary** entry for `tile_weights`. When in doubt, changes must **not** silently alter previously valid outputs for the same sealed inputs and `{parameter_hash}`.

## 13.1 SemVer ground rules *(Binding)*

* **MAJOR** — A change that can make previously conformant S2 outputs **invalid** or **different** for the same inputs/`{parameter_hash}`, or that requires consumer code/config changes.
* **MINOR** — Backward-compatible additions/tightenings that **do not** invalidate previously accepted runs on the reference ingress set and **do not** require consumer changes.
* **PATCH** — Editorial clarifications and non-binding notes that **do not** change behaviour, shape, acceptance, or PAT thresholds.

## 13.2 Dataset contract matrix for `tile_weights` *(Binding)*

**MAJOR** if any of the following change:

* **Identity & layout:** partition keys (`[parameter_hash]`), path family, writer sort (`[country_iso, tile_id]`).
* **Keys/shape:** primary key (`[country_iso, tile_id]`); required columns (once enumerated); column **type** narrowing or removal; column rename without a compatibility alias.
* **CRS/semantics:** any redefinition that would change the meaning of keys or values (e.g., changing `dp` semantics or integerisation law).
* **Governance:** dataset ID rename; licence class weakening; retention reduction below published values.

**MINOR** if:

* Add **nullable**/optional columns; widen a type (e.g., int→number) without breaking constraints.
* Add non-authoritative audit fields (e.g., reporting the basis or a real-valued weight) that do not affect acceptance.
* Tighten validation bounds **only if** proven not to flip prior accepted runs to fail.

**PATCH** if:

* Spelling/structure/formatting fixes; cross-reference corrections; clarifying examples.

## 13.3 Behavioural compatibility (basis, quantisation, tie-break) *(Binding)*

* **Basis set**: Allowed values are `{uniform, area_m2, population}`.
  – Changing the **meaning** of an existing basis or the **default** basis is **MAJOR**.
  – Adding a new basis is **MAJOR** unless surfaced via a **new dataset/anchor** or a feature flag default-off with an announced migration path.
* **Quantisation law**: `dp` (fixed-decimal precision), quota computation, **largest-remainder** allocation, and **tie-break = ascending numeric (tile_id)** are **stable**; any change is **MAJOR**.
* **Monotonicity rule**: The monotone/residue guarantees are **stable**; weakening them is **MAJOR**.

## 13.4 PAT envelope & operational limits *(Binding)*

* Tightening a PAT bound (I/O amplification, runtime inequality, memory/FD caps) is **MINOR** **only if** it **does not** cause previously accepted **reference** runs to fail; otherwise **MAJOR**.
* Loosening a PAT bound is **MINOR**.
* Requiring **new mandatory counters** (previously optional) is **MAJOR**.

## 13.5 Observability artefacts *(Binding)*

* Presence of §9 artefacts (run report, per-country summaries, determinism receipt, PAT counters) is **binding**.
* Moving artefacts **into** the dataset partition is **MAJOR** (forbidden).
* Adding optional fields is **MINOR**; making new fields **mandatory** for acceptance is **MAJOR**.
* Renaming existing required fields in reports is **MAJOR** unless dual-emitted with an overlap window.

## 13.6 Deprecation & removal policy *(Binding)*

* **Mark-and-wait:** deprecate with `deprecated_since: x.y.z`; do **not** remove before the next **MAJOR**. Provide a normative **Migration Note**.
* **Aliases over renames:** for column/anchor renames, provide a compatibility alias for **≥ one MINOR** before MAJOR removal.
* **Feature flags:** new behaviours (e.g., a new basis) must ship behind a flag default-**off**; flipping to **on** by default is **MAJOR**.

## 13.7 Interactions with sealed inputs *(Binding)*

* Upgrading ingress references (ISO/countries/raster) or S1 `tile_index` versions **changes outputs** but **does not** change S2 SemVer. This is expected data drift.
* If an ingress update forces a change to S2 rules (e.g., basis semantics or CRS assumptions), classify the S2 change via §13.2–§13.3 (often **MAJOR**).

## 13.8 Migration & rollback *(Binding)*

* **Forward migration:** for MAJOR changes, publish a **Migration Note** with consumer impact, code/config deltas, and (if applicable) a **dual-write** period (old & new columns/anchors) plus a clear sunset date.
* **Rollback:** partitions are **write-once**; rollback means **promoting** the last accepted `{parameter_hash}` partition. Never mutate files in place.
* **Pinning:** consumers must pin to a specific S2 spec version and schema anchor in CI; upgrades follow the SemVer expectations herein.

## 13.9 Versioning responsibilities *(Binding)*

* **Spec (this doc):** bump when behaviour/acceptance/PAT rules change.
* **Schema (`#/prep/tile_weights`):** bump when shape/keys/constraints change or columns are enumerated/altered.
* **Dictionary (`#tile_weights`):** bump on path/partition/sort/licence/retention/status changes.
* **Lock-step rule:** if a change spans spec/schema/dictionary, bump all affected artefacts **together** and record cross-links in release notes.

*Binding effect:* Within a **major** line, consumers can rely on **stable identity, shape, basis semantics, quantisation law, tie-break, and PAT envelope**. Any change that could invalidate prior conformant outputs or consumer assumptions is **MAJOR**; all others follow the **MINOR/PATCH** rules above.

---

# Appendix A — Definitions & symbols *(Informative)*

> Plain-English glossary and notation used in **S2 — Tile Weights**. These entries explain terms but do not add new obligations beyond the Binding sections.

## A.1 Core identifiers & lineage

* **`parameter_hash`** — Lowercase **hex64** (SHA-256) digest representing the governed parameter set for a run; the **sole partition key** for `tile_index` and `tile_weights`. Identity is path-scoped by `{parameter_hash}` in the Dictionary. 
* **`tile_index`** — The S1 output (universe of eligible tiles) with **PK = `[country_iso, tile_id]`**, **partition_keys = `[parameter_hash]`**, **sort_keys = `[country_iso, tile_id]`**; Parquet; Proprietary-Internal; retention 365 days. 
* **`tile_weights`** — The S2 output (fixed-dp weights per tile) with **PK/partition/sort and required columns enumerated in the schema**; Parquet; Proprietary-Internal; retention 365 days.
* **JSON-Schema anchor** — The schema reference that is the **sole shape authority**: `schemas.1B.yaml#/prep/tile_index` and `#/prep/tile_weights`. Keys/partitions/sort are fixed here.
* **Dataset Dictionary** — Authority for **ID→path/partition/sort/format/licence/retention**; no literal paths in code. `#tile_index`, `#tile_weights`. 

## A.2 Sealed ingress references (read-only)

* **`iso3166_canonical_2024`** — ISO-2 FK surface; Parquet; **CC-BY-4.0**; retention ≈1095 days. 
* **`world_countries`** — Country polygons (GeoParquet); **ODbL-1.0**; retention ≈1095 days. 
* **`population_raster_2025`** — Population raster (COG GeoTIFF); **ODbL-1.0**; retention ≈1095 days. *(Used only when `basis="population"`.)* 

## A.3 Weighting basis (S2)

* **`basis`** — Governed enum defining **mass** assignment per tile:
  **`uniform`** (all ones), **`area_m2`** (from `tile_index.pixel_area_m2`), **`population`** (from `population_raster_2025` intensity). The chosen value is disclosed in the run report. 

## A.4 Notation for per-country distributions

For each ISO country **`c`**:

* **`U_c`** — Set of tiles `{ i = (country_iso, tile_id) ∈ tile_index | country_iso = c }`. *(No tiles outside `U_c` may appear in S2.)* 
* **`m_i`** — Non-negative **mass** assigned to tile `i` per the **basis** (see A.3).
* **`M_c`** — Total mass in `c`: `M_c = Σ_{i∈U_c} m_i`.
* **`w_i`** — Real weight: `w_i = m_i / M_c` (when `M_c > 0`), defining a probability distribution over `U_c`.

## A.5 Fixed-decimal (fixed-dp) quantisation

* **`dp`** — Non-negative integer **decimal precision**; the run uses a single `dp` across the entire partition and discloses it in the run report.
* **`K`** — Scaling factor `K = 10^dp`.
* **`q_i`** — Quota `q_i = w_i * K`.
* **`z_i`** — Base integer `z_i = ⌊q_i⌋`.
* **`r_i`** — Residue `r_i = q_i − z_i ∈ [0,1)`.
* **`S`** — Shortfall `S = K − Σ z_i` (integer in `[0, |U_c|)`).
* **Largest-remainder allocation** — Give **`+1`** to exactly **`S`** tiles with the largest `r_i`, breaking ties by ascending numeric `tile_id`. The final fixed-dp integer **`weight_fp`** is `z_i` or `z_i+1` accordingly. *(Per-country exact sum: `Σ weight_fp = 10^dp`.)*
* **Monotonicity rule** — If `m_a ≥ m_b`, then after quantisation **`weight_fp(a) ≥ weight_fp(b)`**, allowing at most a **1-unit** difference from residue allocation.

## A.6 Keys, partitions & ordering

* **Primary key (PK)** — `[country_iso, tile_id]` for both `tile_index` and `tile_weights`.
* **Partition keys** — `[parameter_hash]` for both datasets.
* **Writer sort** — `[country_iso, tile_id]` (stable merge order); **file order is non-authoritative**.

## A.7 Hashing & ordering terminology

* **ASCII-lex order** — Sort file paths by their ASCII byte sequence; used when computing the **determinism receipt** (composite SHA-256 over concatenated bytes of partition files in ASCII-lex order). *(S2 mirrors the established hashing discipline used elsewhere in Layer-1.)*
* **Determinism receipt** — `{ partition_path, sha256_hex }` proving a byte-identical re-run of a partition; emitted in the run report. *(See §9 of the S2 spec.)*

## A.8 Counters & metrics (for PAT; units)

* **Wall-clock / CPU:** `wall_clock_seconds_total` (s), `cpu_seconds_total` (s)
* **Dataset scale:** `countries_processed` (count), `rows_emitted` (count)
* **I/O:** `bytes_read_tile_index_total` (bytes), `bytes_read_raster_total` (bytes, population basis only), `bytes_read_vectors_total` (bytes, if used)
* **Resources:** `max_worker_rss_bytes` (bytes), `open_files_peak` (count)
* **Parallelism facts:** `workers_used` (count), `chunk_size` (tiles)

## A.9 Abbreviations

* **CRS** — Coordinate Reference System (WGS84 for S1 coordinates)
* **COG** — Cloud-Optimised GeoTIFF (ingress raster format) 
* **PAT** — Performance Acceptance Tests (S2’s pass/fail envelope)
* **PII** — Personally Identifiable Information (all listed datasets are `pii:false` in the Dictionary) 

## A.10 Sets & symbols (mathematical)

* **ℕ** — `{1,2,3,…}`; **ℕ₀** — `{0,1,2,…}`
* **ℤ** — Integers
* **[a,b]** — Closed interval; **(a,b)** — open interval
* **A ⊂ B** — Strict subset; **∪, ∩, ∖** — union, intersection, set difference

---

*Informative note:* Definitions above align with the live **Dictionary** entries for `tile_index`/`tile_weights` (path/partition/sort/licence/retention) and the **Schema** anchors for `prep/tile_index` and `prep/tile_weights`. Ingress surfaces and their licences are as declared in the Dictionary/Registry.

---

# Appendix B — Worked examples & sanity queries *(Informative)*

> These examples illustrate **S2 — Tile Weights** behaviour and give **validator-friendly checks** you can run after a materialisation. They don’t add obligations beyond the Binding sections; where shape/path authority matters we reference the anchors for **`tile_index`** and **`tile_weights`** in the Schema/Dictionary.

---

## B.1 Micro-example (uniform basis, exact division)

**Setup** (one country `c`): five tiles in `tile_index` with `tile_id ∈ {1,3,5,8,10}`. Choose `basis="uniform"`, `dp=2` ⇒ `K = 10^2 = 100`.
Masses: `m_i = 1` for all; total `M_c = 5`.

* Real weights: `w_i = m_i / M_c = 1/5 = 0.2`
* Quotas: `q_i = w_i·K = 20.0` ⇒ bases `z_i = 20`, residues `r_i = 0`
* Shortfall: `S = K − Σ z_i = 100 − 100 = 0` ⇒ **no** `+1` allocations

**Result:** `weight_fp = 20` for each tile. Sum per country = `100` exactly. (Writer sort and path come from the Dictionary.) 

---

## B.2 Micro-example (area basis, tie-break engages)

**Setup** (one country `c`): three tiles with `tile_id ∈ {7,11,20}`, `basis="area_m2"`, `dp=1` ⇒ `K=10`. From **`tile_index.pixel_area_m2`**, take masses:

* `m_7 = 1.10`, `m_11 = 1.10`, `m_20 = 0.80` (ellipsoidal areas from S1). Total `M_c = 3.00`. 

* Real weights: `w = (0.366…, 0.366…, 0.266…)`

* Quotas: `q = (3.666…, 3.666…, 2.666…)`

* Bases: `z = (3,3,2)`, residues `r = (0.666…, 0.666…, 0.666…)`

* Shortfall: `S = 10 − (3+3+2) = 2`

**Largest-remainder (deterministic):** select **two** highest residues; all equal ⇒ **tie-break by ascending numeric `tile_id`** → tiles `7`, then `11` get `+1`.

**Result:** `weight_fp(7,11,20) = (4,4,2)`; per-country sum `= 10` exactly; monotonicity holds (`m_7=m_11>m_20` ⇒ weights `(4,4)≥2`). 

---

## B.3 Zero-mass fallback (population basis)

**Setup:** `basis="population"`, `dp=2`, a small country where each tile’s population intensity is **NODATA or 0** in **`population_raster_2025`**. Then `M_c = Σ m_i = 0` with `|U_c| = n > 0`. 

**Policy (§6.7):** fall back **deterministically** to uniform in `c`: set `m_i:=1`, recompute, and set `zero_mass_fallback=true` in the run report. Expected per-country weights are as B.1 (equal, with exact sum = `10^dp`). *(Validators fail `E104_ZERO_MASS` if fallback is not engaged.)*

---

## B.4 Tie-break sanity

If two or more tiles in a country have equal residues `r_i`, the **ascending numeric `tile_id`** order decides who receives the `+1`. In the B.2 example, if the three residues were equal and `S=1`, **`tile_id=7`** alone gets `+1`. This rule must be stable under any parallelism (see §3.5/§6.4). 

---

## B.5 Determinism receipt — what to hash (Illustrative)

**Goal:** produce a single SHA-256 over the concatenated bytes of all files in the **`tile_weights/parameter_hash=…/`** partition, listed in **ASCII-lex** relative-path order. (This mirrors the layer’s established hashing discipline.) Example list:

```
country_iso=DE/part-000.parquet
country_iso=FR/part-000.parquet
country_iso=US/part-000.parquet
```

ASCII-lex order ⇒ `country_iso=DE/...`, `country_iso=FR/...`, `country_iso=US/...` → concatenate bytes in that order → SHA-256 → record `{ partition_path, sha256_hex }` in the run report (§9). 

Note: Any `country_iso=XX/` subfolders shown here are writer layout only. The only authoritative partition key for `tile_weights` is `{parameter_hash}`.

---

## B.6 Sanity queries (validator sketches)

> These sketches assume a SQL engine that can read Parquet and (optionally) sample the COG raster for the **population** basis. **`dp` is a required column** (and also recorded in the run report). Shape authority is the **Schema**; path/partition/sort come from the **Dictionary**.

**(1) FK & coverage vs S1** — rows match **exactly** the S1 universe

```sql
-- Expect: no rows (every S2 row exists in S1)
SELECT w.country_iso, w.tile_id
FROM tile_weights w
LEFT JOIN tile_index t
  ON t.country_iso = w.country_iso
 AND t.tile_id     = w.tile_id
WHERE t.country_iso IS NULL;

-- Coverage per country: counts must match
WITH s1 AS (SELECT country_iso, COUNT(*) c FROM tile_index GROUP BY country_iso),
     s2 AS (SELECT country_iso, COUNT(*) c FROM tile_weights GROUP BY country_iso)
SELECT COALESCE(s1.country_iso,s2.country_iso) AS country_iso, s1.c AS s1_rows, s2.c AS s2_rows
FROM s1 FULL OUTER JOIN s2 USING (country_iso)
WHERE s1.c IS DISTINCT FROM s2.c;  -- Expect: no rows
```



**(2) Per-country exact sum** — `Σ weight_fp = 10^dp` (using the **dp column**)

```sql
SELECT country_iso,
       SUM(weight_fp)        AS s,
       POWER(10, MAX(dp))    AS k
FROM tile_weights
GROUP BY country_iso
HAVING SUM(weight_fp) <> POWER(10, MAX(dp));  -- Expect: no rows
```

**(3) dp consistency** — all rows agree on the same `dp`

```sql
SELECT COUNT(DISTINCT dp) AS dps
FROM tile_weights;
-- Expect: 1
```

**(4) Uniform basis quick-check** — max/min differ by ≤ 1

```sql
-- Only when basis="uniform": in each country, weights must be equal up to residue allocation.
SELECT country_iso
FROM (
  SELECT country_iso, MAX(weight_fp) - MIN(weight_fp) AS spread
  FROM tile_weights
  GROUP BY country_iso
) s
WHERE spread > 1;   -- Expect: no rows
```

**(5) Area basis monotonicity** — heavier area ⇒ no lighter integer weight (beyond 1-unit residue)

```sql
-- Join S2 with S1's authoritative area column
WITH joined AS (
  SELECT w.country_iso, w.tile_id, w.weight_fp, t.pixel_area_m2
  FROM tile_weights w
  JOIN tile_index  t USING (country_iso, tile_id)
)
SELECT a.country_iso, a.tile_id AS a_id, b.tile_id AS b_id
FROM joined a
JOIN joined b
  ON a.country_iso = b.country_iso
 AND a.pixel_area_m2 >= b.pixel_area_m2
WHERE a.weight_fp + 1 < b.weight_fp;     -- Expect: no rows
```



**(6) Per-country residue accounting** — shortfall `S = 10^dp − Σ⌊q_i⌋`

```sql
-- Illustrative; a validator may recompute quotas with exact arithmetic.
-- This check is typically done in code, not SQL.
```

**(7) Population basis** — intensities from **`population_raster_2025`** (COG)

* Verify NODATA ⇒ mass 0.
* Recompute per-country `M_c` and quotas; confirm residue selection and exact sums (as in §8.5). *(Requires a georaster reader bound to the Dictionary path.)* 

**(8) Writer law & partition hygiene** — Dictionary path/sort

```text
Path must be:
data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/   (format=parquet)
Writer sort must be [country_iso, tile_id].
```



**(9) Determinism (re-run)** — second run with a different worker count

* Recompute the **determinism receipt** (ASCII-lex partition hash).
* **Receipts must match** byte-for-byte; mismatch ⇒ `E107_DETERMINISM`. (See §9.4/§11.7.)

---

## B.7 PAT walkthrough (numbers are illustrative)

Assume the run report shows (`basis="population"`):

* `B_ti = 8.8 GiB`, size `S_ti = 8.0 GiB` ⇒ `B_ti/S_ti = 1.10` (**pass**)
* `B_r = 7.6 GiB`, size `S_r = 7.2 GiB`   ⇒ `B_r/S_r = 1.06` (**pass**)
* `B_v = 0` (no vectors read)

Baselines: `io_baseline_ti_bps = 320 MiB/s`, `io_baseline_raster_bps = 300 MiB/s`.
**Bound:**
`≤ 1.75 × ( 8.8 GiB/320 MiB/s + 7.6 GiB/300 MiB/s ) + 300 s`
`= 1.75 × ( 28.16 s + 25.33 s ) + 300 s ≈ 1.75 × 53.49 + 300 ≈ 393.6 s`

If `wall_clock_seconds_total = 380 s` ⇒ **pass**;
if `= 410 s` ⇒ **fail** (`E109_PERF_BUDGET`). (Memory/FD caps must also pass.)

*(I/O ratios, baselines and caps are bound in §11.1–§11.2; counters in §9.5.)*

---

## B.8 Quick mapping from symptoms → failure codes

* Missing or non-conformant `tile_index` ⇒ `E101_TILE_INDEX_MISSING`
* Rows in S2 not present in S1 ⇒ `E102_FK_MISMATCH`
* Country has zero tiles ⇒ `E103_ZERO_COUNTRY`
* Country has tiles but zero mass and no uniform fallback ⇒ `E104_ZERO_MASS`
* Per-country sum `Σ weight_fp ≠ 10^dp` or dp disagreement ⇒ `E105_NORMALIZATION`
* Monotonicity/residue-law broken or wrong tie-break ⇒ `E106_MONOTONICITY`
* Determinism receipt mismatch across re-runs ⇒ `E107_DETERMINISM`
* Wrong path/partition/sort/format; partial publish; evidence missing ⇒ `E108_WRITER_HYGIENE`
* PAT ratios/inequality/memory/FD caps failed ⇒ `E109_PERF_BUDGET`

---

## B.9 Where to look (anchors)

* **`tile_index` (S1)**: Schema anchor fixes keys/columns (area, centroids, inclusion_rule); Dictionary fixes path/partition/sort/format/licence.
* **`tile_weights` (S2)**: Schema anchor (keys reserved; columns enumerated at ratification); Dictionary path/partition/sort/format/licence/retention.
* **Ingress** (ISO, world_countries, population raster): Dictionary/Registry carry paths/licences for read-only checks/basis.

---

*These examples and checks align with the live anchors for **`tile_index`** and **`tile_weights`** (Schema & Dictionary), the sealed ingress surfaces, and the deterministic fixed-dp law (basis → quotas → largest-remainder with `(tile_id)` tie-break) defined in the S2 spec.*

---

# Appendix C — PAT datasets & measurement recipe *(Informative; references §11/§8)*

> This appendix describes **what to run** and **how to measure** to execute the Performance Acceptance Tests (PAT) defined **normatively** in §11, and how to package the evidence required by §8.9–§8.10 and §9. It is **informative**; pass/fail comes only from the binding rules in those sections.

---

## C.1 PAT levels & what counts for acceptance

* **DEV** — functional sanity on a small ISO subset (≤ 5 countries). *No* performance claims.
* **TEST** — same code path as PROD; may run on a fixed ~¼-world subset for early detection.
* **PROD (acceptance)** — **full ingress set**; only **PROD PAT** results determine pass/fail against §11.

---

## C.2 Datasets to use (and when)

* **Required input:** `tile_index` (S1) for the **same `{parameter_hash}`** being produced by S2.
* **Ingress references (read-only):**

  * `iso3166_canonical_2024` (FK checks in §8.3).
  * `world_countries` *(optional; validations only — S2 does not alter geometry)*.
  * `population_raster_2025` **only** when `basis="population"` (see §6.1/§6.6).
* **Output under test:** `tile_weights/parameter_hash={parameter_hash}/` (parquet; writer sort `[country_iso, tile_id]`).

---

## C.3 Counters & fields the run **must** emit (recap)

Emit **outside** the dataset partition (see §9):

* Run-level: `parameter_hash`, `basis`, `dp`, `rows_emitted`, `countries_total`.
* PAT counters:
  `wall_clock_seconds_total`, `cpu_seconds_total`,
  `countries_processed`,
  `bytes_read_tile_index_total` (**B_ti**),
  `bytes_read_raster_total` (**B_r**, population basis only),
  `bytes_read_vectors_total` (**B_v**, if vectors read),
  `max_worker_rss_bytes`, `open_files_peak`,
  `workers_used`, `chunk_size`.
* Determinism receipt: `{ partition_path, sha256_hex }`.

---

## C.4 One-time measurement setup (per run)

1. **Resolve inputs via the Dictionary** (no literal paths).
2. **Record on-disk sizes** (object-store metadata, not by reading):
   `S_ti` = total bytes for the `tile_index` partition used;
   `S_r`  = bytes for `population_raster_2025` (if used);
   `S_v`  = bytes for any vector inputs actually read.
3. **Measure sustained read baselines** (same bucket/paths):

   * `io_baseline_ti_bps`: stream ≥ **1 GiB** contiguous from the `tile_index` partition family.
   * If `basis="population"`: `io_baseline_raster_bps` from `population_raster_2025` (COG; contiguous range).
   * If vectors are read: `io_baseline_vectors_bps` from the combined vector set.
4. **Start PAT timers/counters**: zero all byte counters; start wall-clock/CPU timers; record `workers_used` and `chunk_size` if block-parallel.

---

## C.5 What to accumulate during the run

* **I/O bytes:** increment `B_ti`, `B_r` (if population), `B_v` (if vectors).
* **Scale:** `countries_processed`, `rows_emitted`.
* **Resources:** peak `max_worker_rss_bytes`, `open_files_peak`.

---

## C.6 Computing the §11 checks (pass/fail)

Using the counters and baselines:

**I/O amplification (per surface)**

* Enforce: `B_ti/S_ti ≤ 1.25`, and when applicable `B_r/S_r ≤ 1.25`, `B_v/S_v ≤ 1.25`.

**Wall-clock bound (with headroom)**

* Require:

```
wall_clock_seconds_total
  ≤ 1.75 × ( B_ti/io_baseline_ti_bps
           + B_r /io_baseline_raster_bps
           + B_v /io_baseline_vectors_bps ) + 300
```

**Memory / I/O caps**

* Enforce: `max_worker_rss_bytes ≤ 1.0 GiB`, temp disk ≤ 2 GiB, `open_files_peak ≤ 256`.

**Determinism re-run**

* Re-run the job on the same `{parameter_hash}` with a **different** `workers_used`; recompute the determinism receipt (ASCII-lex list of partition files → concatenate bytes → SHA-256). Receipts **must** match exactly.

**Writer law & atomicity**

* Path family, parquet format, partitioning `[parameter_hash]`, writer sort `[country_iso, tile_id]`; one atomic publish; write-once identity.

> Any breach of the above **MUST** result in `E109_PERF_BUDGET` (or `E107_DETERMINISM` / `E108_WRITER_HYGIENE` for the determinism/writer checks), as bound in §11/§8.

---

## C.7 Packaging the evidence

* Produce a single **`s2_run_report.json`** (or equivalent) with all fields from **C.3**, plus:
  `ingress_versions` (ISO/countries/raster), and a per-country **normalization summary** array (see §9.3).
* Locate the report and any JSON-lines summaries **outside** the dataset partition (control-plane artefacts/logs). Retain ≥ **30 days**.

---

## C.8 Minimal validator checklist (what must be present)

1. Run report present with **all** counters/baselines.
2. I/O amplification ratios computed and **≤ 1.25** per surface used.
3. Wall-clock inequality holds.
4. Memory/FD caps respected.
5. Determinism re-run receipts **identical**.
6. Writer law satisfied (path/partition/sort/format), atomic publish, write-once.
7. FK & coverage vs `tile_index` (from Appendix B sanity queries) pass.

---

## C.9 Troubleshooting: symptoms → likely causes

* **High `B_ti/S_ti`** — repeated scans over `tile_index`, or inefficient row-group filtering; ensure single-pass streaming.
* **High `B_r/S_r`** (population basis) — many small random reads; use COG-friendly windows; reduce re-tries.
* **Wall-clock above bound** — mis-measured baselines, under-parallelisation, or excessive per-tile overhead.
* **`open_files_peak` > 256** — handle leaks or oversharded parquet output.
* **Determinism mismatch** — nondeterministic reducers, unstable merge (not `[country_iso, tile_id]`), or post-merge rewrite.

---

## C.10 DEV/TEST shortcuts (non-binding hints)

* DEV: run on 2–5 diverse ISO codes (tiny, medium, dateline-crossing).
* TEST: use a fixed ISO list covering multiple continents; keep `{parameter_hash}` stable to compare runs; verify residue distributions qualitatively.

---

*This recipe keeps PAT reproducible and audit-ready while remaining within S2’s authorities: **Schema** for shape, **Dictionary** for path/partition/sort/licence/retention, and the deterministic fixed-dp law defined in §6, with pass/fail thresholds bound in §11 and acceptance wired through §8.9–§8.10.*

---