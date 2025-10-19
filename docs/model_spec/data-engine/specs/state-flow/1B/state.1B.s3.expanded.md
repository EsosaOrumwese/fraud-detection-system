# 1B * State-3 · Country Requirements Frame (Nᵢ)

# 1) Purpose & scope **(Binding)**

**1.1 Problem statement.**
S3 deterministically derives the **exact number of sites to place per `(merchant_id, legal_country_iso)`**, denoted `n_sites`, by grouping **1A’s `outlet_catalogue`** rows after S0’s consumer-gate PASS for the same fingerprint. S3 is **RNG-free** and **does not** allocate sites to tiles; it only produces a per-country **requirements frame** for use by S4/S5+. `outlet_catalogue` is the sole count source; it is fingerprint-scoped and order-free, with “**No PASS → No read**” enforced upstream.   

**1.2 Out of scope.**
S3 **does not** (a) encode or infer **inter-country order** (authority remains **1A `s3_candidate_set.candidate_rank`**, home=0), (b) allocate counts to **tiles** or **coordinates**, (c) perform **jitter** or any RNG, or (d) read any surface beyond those sealed by S0 and listed in the S3 Inputs header (later section).  

**1.3 Authority boundaries & invariants.**
a) **Read gate:** S3 relies on the S0 receipt (`s0_gate_receipt_1B`) which proves the 1A bundle PASS for the fingerprint; S3 must not reopen the bundle logic or read `outlet_catalogue` without that PASS.  
b) **Shape vs. paths:** **JSON-Schema is the sole shape authority**; **Dataset Dictionary** governs dataset IDs → paths/partitions/writer-sort/licence. S3 introduces a new output dataset (defined later) but **does not redefine** existing IDs.  
c) **Coverage dependency (parameter-scoped):** For every `(merchant_id, legal_country_iso)` with `n_sites>0`, the **country must exist in S2 `tile_weights`** for the same `{parameter_hash}` (S3 asserts this coverage; S2 defines identity/shape).  
d) **FK domain:** `legal_country_iso` values are **uppercase ISO-3166-1 alpha-2** and must exist in **`iso3166_canonical_2024`** (ingress anchor). 
e) **Order law:** Inter-country order is **external** to S3 and remains solely on **`s3_candidate_set`**; `outlet_catalogue` is order-free by contract.  

**1.4 Deliverable from S3 (named, but not specified here).**
S3 will emit one deterministic table (ID **`s3_requirements`**) partitioned so it can join S4 cleanly (seed + fingerprint + parameter hash). The exact shape/partitions and validators are defined in later sections of the S3 doc (Schema & Acceptance). This new dataset is **additive** to your pack and does not modify or replace existing 1A/1B artifacts. 

---

# 2) Preconditions & sealed inputs **(Binding)**

**2.1 Consumer gate (must hold before any read).**
S0 has verified the 1A validation bundle for the target `manifest_fingerprint` (ASCII-lex index → SHA-256) and published exactly one `s0_gate_receipt_1B` under `fingerprint={manifest_fingerprint}`. Absence or mismatch ⇒ ABORT; `outlet_catalogue` must not be read.   

**2.2 Sealed inputs authorised by S0 (enumerated in the receipt).**
S0’s `sealed_inputs[]` names the surfaces 1B may read, each with its schema anchor and (where applicable) partitions:

* `outlet_catalogue` — `[seed, fingerprint]`; `schemas.1A.yaml#/egress/outlet_catalogue`. **Order-free; join 1A.S3 `s3_candidate_set` for inter-country order.** Read only after PASS.  
* `s3_candidate_set` — `[parameter_hash]`; `schemas.1A.yaml#/s3/candidate_set` (order authority; used later, not by S3).  
* `iso3166_canonical_2024` — FK target; `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`.  
* `world_countries` — spatial reference; `schemas.ingress.layer1.yaml#/world_countries`. *(Not read by S3.)*  
* `population_raster_2025` — spatial prior; `schemas.ingress.layer1.yaml#/population_raster_2025`. *(Not read by S3.)*  
* `tz_world_2025a` — time-zone polygons. *(Not read by S3.)*  

**2.3 Inputs S3 will actually read.**

* **`outlet_catalogue`** (counts source; fingerprint-scoped; order-free; PASS-gated). 
* **`tile_weights`** (coverage authority per country for the selected `{parameter_hash}`); `schemas.1B.yaml#/prep/tile_weights`.  
* **`iso3166_canonical_2024`** (FK domain for `legal_country_iso`). 

**2.4 Identity & parameter selection.**
S3 binds to a single `{manifest_fingerprint}` (from S0) and a single `{parameter_hash}` (matching S2 outputs). `tile_weights` identity and partitions are `{parameter_hash}` with writer sort `[country_iso, tile_id]`. `outlet_catalogue` identity and partitions are `{seed, fingerprint}` with writer sort `[merchant_id, legal_country_iso, site_order]`.   

**2.5 Resolution & read rules.**
All reads resolve via the **Dataset Dictionary**; path strings are owned there. Path tokens **must equal** embedded columns where specified (e.g., `manifest_fingerprint`). Do not introduce literal paths in code.  

**2.6 RNG posture.**
S3 **consumes no RNG**; no RNG logs are written. 

---

# 3) Inputs & authority boundaries **(Binding)**

**3.1 Required datasets (IDs → `$ref` → partitions).**

* **`outlet_catalogue`** → `schemas.1A.yaml#/egress/outlet_catalogue` · **partitions:** `[seed, fingerprint]` · **writer sort:** `[merchant_id, legal_country_iso, site_order]` · **law:** order-free; **read only after PASS** (S0 proves PASS).  
* **`tile_weights`** → `schemas.1B.yaml#/prep/tile_weights` · **partitions:** `[parameter_hash]` · **writer sort:** `[country_iso, tile_id]` · identity is **parameter-scoped**.  
* **`iso3166_canonical_2024`** (FK domain for `legal_country_iso`) → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` · **unpartitioned**. 

**3.2 Sealed but not read by S3 (declared for lineage/forward use).**

* **`s3_candidate_set`** — sole inter-country order authority (`candidate_rank`, home=0). **Not** read by S3. 
* **`tile_index`** — S1 eligible tiles; S3 asserts coverage via `tile_weights` only. **Not** read by S3. 
* **`validation_bundle_1A`** — basis of the consumer gate proven by S0; S3 does **not** reopen the bundle.  

**3.3 Precedence & read-resolution rules.**

* **Schema vs Dictionary vs Registry.** **JSON-Schema is the sole shape authority** (columns, domains, PK/partition/sort); the **Dataset Dictionary** governs IDs→paths/partitions/writer sort/licence; the **Artefact Registry** records provenance/licences. If Dictionary and Schema conflict, **Schema wins**. **No hard-coded paths**; all reads resolve by Dictionary.  
* **Gate law.** S3 reads `outlet_catalogue` **only** under the fingerprint proven in S0’s `s0_gate_receipt_1B` (No PASS → No read). 
* **Path↔embed equality.**
  • For `outlet_catalogue`: embedded `manifest_fingerprint` (and `global_seed` if present) **equals** the `{fingerprint}` (`{seed}`) path token(s). 
  • For `tile_weights`: embedded `parameter_hash` **equals** the `{parameter_hash}` path token. 

**3.4 Authority boundaries (what S3 MUST / MUST NOT do).**

* **Counts source.** `outlet_catalogue` is the **only** source of counts; S3 **MUST NOT** derive counts from any other surface. 
* **Order authority.** Inter-country order is **external** to S3 and remains solely on `s3_candidate_set`; S3 **MUST NOT** encode or imply order. 
* **Coverage dependency.** For each `(merchant_id, legal_country_iso)` with `n_sites>0`, **that `legal_country_iso` MUST exist in `tile_weights`** for the selected `{parameter_hash}`; absence is a hard fail (see §9 codes).  
* **FK domain.** `legal_country_iso` **MUST** be uppercase ISO-3166-1 alpha-2 present in `iso3166_canonical_2024`. 
* **Out-of-scope reads.** S3 **MUST NOT** read `world_countries`, `population_raster_2025`, `tz_world_2025a`, or any dataset not listed in §3.1; any other access **fails closed**.  

**3.5 Identities bound for this state.**

* Run binds to **one** `{manifest_fingerprint}` (from S0) and **one** `{parameter_hash}` (matching S2). Mixing identities within the same S3 publish is **forbidden**.  

**3.6 RNG posture.**

* S3 **consumes no RNG** and writes **no RNG logs**. 

---

# 4) Outputs (datasets) & identity **(Binding)**

**4.1 Dataset ID & schema anchor.**

* **ID:** `s3_requirements`
* **Schema (sole shape authority):** `schemas.1B.yaml#/plan/s3_requirements` *(canonical anchor)*.
  **Keys:** **PK** = [merchant_id, legal_country_iso]; **partition_keys** = [manifest_fingerprint, parameter_hash]; **sort_keys** = [merchant_id, legal_country_iso].
  **Columns (strict):**

  * `merchant_id` — `$ref: schemas.layer1.yaml#/$defs/id64`. 
  * `legal_country_iso` — `$ref: schemas.1B.yaml#/$defs/iso2`. 
  * `n_sites` — `integer (≥1)`; per-merchant×country site count.

**4.2 Path, partitions, writer sort & format (Dictionary law).**
The **Dataset Dictionary** MUST declare this path family and writer policy:

```
data/layer1/1B/s3_requirements/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
```

* **Partitions:** `[fingerprint, parameter_hash]` (one write per identity; write-once). This matches established multi-key partitioning patterns in Layer-1. 
* **Writer sort:** `[merchant_id, legal_country_iso]` (stable merge order; file order non-authoritative). Pattern mirrors S1/S2 writer-sort discipline.  
* **Format:** `parquet` (as per Dictionary conventions for 1B tables). 

**4.3 Immutability & atomic publish.**

* **Write-once:** Re-publishing under the same identity `{seed, manifest_fingerprint, parameter_hash}` **MUST** be byte-identical or fail. 
* **Atomicity:** Stage outside the final partition; fsync; single atomic rename into the partition. File order is **non-authoritative**. 

**4.4 Licence, retention, PII (Dictionary authority).**

* **Licence:** `Proprietary-Internal` · **Retention:** `365` days · **PII:** `false`. These fields are owned by the Dictionary and **MUST NOT** be overridden at write time; align with existing 1B dataset entries. 

**4.5 Identity & lineage constraints.**

* A run **binds to exactly one** `{manifest_fingerprint}` (from S0 receipt) and one `{parameter_hash}` (matching S2). Mixing identities within a publish is forbidden.  
* **No literal paths in code.** All reads/writes resolve by **Dataset Dictionary**; JSON-Schema remains the **sole** shape authority.  

**4.6 Row admission rules.**

* Emit a row **iff** the grouped count from `outlet_catalogue` is **≥1** for `(merchant_id, legal_country_iso)`; zero-count pairs are not materialised. `outlet_catalogue` is fingerprint-scoped, order-free, and read-gated (S0 proves PASS).  

**4.7 Forward consumers (non-authoritative note).**

* **Produced by:** `1B.S3` → **consumed by:** `1B.S4` (rounding/alloc plan) and `1B.S5+`. Writer/reader joins rely on the keys and partitions above; **inter-country order remains external** to S3.  

*(All obligations above mirror existing 1B patterns: schema-owned shape, dictionary-owned path/partitions/sort, write-once/atomic publish, and identity separation by `{manifest_fingerprint, parameter_hash}` consistent with Layer-1 lineage law.)*

---

# 5) Dataset shapes & schema anchors **(Binding)**

**5.1 Canonical anchor (single source of truth).**
The dataset shape for this state is defined **exclusively** by the JSON-Schema anchor **`schemas.1B.yaml#/plan/s3_requirements`**. This document **does not** restate columns, domains, PK/partition/sort, or FKs.

**5.2 Precedence & ownership.**

* **Shape authority:** JSON-Schema (the anchor above).
* **Paths/partitions/writer policy/licensing:** Dataset Dictionary.
* **Provenance/licences:** Artefact Registry.
  If Dictionary text and Schema differ, **Schema wins**.

**5.3 Validation obligation.**
All writers/validators **must** validate any `s3_requirements` publish against the anchor in 5.1. Any deviation (missing/extra/mistyped columns; PK/partition/sort drift) is a **schema-conformance failure** (see §8/§9).

**5.4 Columns-strict posture.**
The anchor enforces a **strict column set** (no undeclared columns). This document relies on the anchor for that rule and does not duplicate it here.

**5.5 Compatibility & change control.**
Any change to the anchor’s shape (PK, partition keys, sort keys, column set/types, or FK targets) is **MAJOR** per §12. Editorial updates to this section do **not** alter shape.

**5.6 Cross-file `$ref` hygiene.**
Cross-schema references (e.g., shared ID/ISO defs or FK surfaces) are **declared in the schema pack**; this spec references only the anchor in 5.1.

---

# 6) Deterministic algorithm (no RNG) **(Binding)**

**6.1 Resolve identities (inputs are fixed before compute).**
a) Read **`s0_gate_receipt_1B`** for the target `manifest_fingerprint`; assert `_passed.flag` equivalence as recorded there. If missing/mismatch ⇒ **ABORT**.  
b) Fix **`parameter_hash`** to the same value used for **S2 `tile_weights`**. 

**6.2 Locate inputs via Dictionary (no literals).**
a) **`outlet_catalogue`** under `…/seed={seed}/fingerprint={manifest_fingerprint}/` (order-free; writer sort `[merchant_id, legal_country_iso, site_order]`). Assert **path↔embed equality** for `manifest_fingerprint` (and `global_seed` if present).  
b) **`tile_weights`** under `…/parameter_hash={parameter_hash}/` (writer sort `[country_iso, tile_id]`). 
c) **`iso3166_canonical_2024`** as FK domain. 

**6.3 Build the requirements frame (pure grouping; no RNG).**
From **`outlet_catalogue`**, compute per `(merchant_id, legal_country_iso)` the integer **`n_sites`**:

* `n_sites := COUNT(*)` over rows for that pair.
* Assert **site-order integrity**: `MIN(site_order) = 1`, `MAX(site_order) = n_sites`, and `COUNT(DISTINCT site_order) = n_sites`. Violations ⇒ **reject** this identity. 

**6.4 FK & normalisation checks (deterministic asserts).**
a) **FK (ISO):** every `legal_country_iso` ∈ `iso3166_canonical_2024`. Fail closed otherwise. 
b) **Uppercase law:** do not transform; assert values are already ISO-2 uppercase per upstream contracts. 

**6.5 Coverage against S2 (parameter-scoped).**
For the fixed `parameter_hash`, assert that **every country emitted by 6.3 exists in `tile_weights`** (i.e., at least one row with `tile_weights.country_iso = legal_country_iso`). Absence ⇒ **ABORT** (downstream states cannot allocate to non-covered countries).  

**6.6 Materialise output rows (shape owned by schema).**
Emit exactly one row per `(merchant_id, legal_country_iso)` with `n_sites ≥ 1` into **`s3_requirements`** under:
`data/layer1/1B/s3_requirements/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
Writer sort: `[merchant_id, legal_country_iso]`. Columns and keys are **exactly** those fixed at `schemas.1B.yaml#/plan/s3_requirements` (no extras). 

**6.7 Immutability & idempotence.**
Write-once per `{manifest_fingerprint, parameter_hash}`; re-publishing to the same partition **must be byte-identical** (file order non-authoritative). Stage → fsync → single atomic move. 

**6.8 Prohibitions (fail closed).**

* **Must not** read any surface not listed in §3 (e.g., `world_countries`, `population_raster_2025`, `tz_world_2025a`). 
* **Must not** encode or infer **inter-country order**; that authority remains **`s3_candidate_set.candidate_rank`** (read-only in later states).  
* **Must not** introduce RNG or RNG logs. S3 is **RNG-free**. 

**6.9 Determinism receipt (optional but recommended).**
Record `{ partition_path, sha256_hex }` for the produced partition by hashing concatenated file bytes in ASCII-lex path order (mirrors the layer’s hashing discipline). Store in the run report; non-semantic for dataset shape. 

---

# 7) Identity, partitions, ordering & merge discipline **(Binding)**

**7.1 Identity tokens (one pair per publish).**

* **Identity:** `{seed, manifest_fingerprint, parameter_hash}`.
* `manifest_fingerprint` is the same value proven by **S0**’s `s0_gate_receipt_1B` (fingerprint-only identity). 
* `parameter_hash` is the same parameter-set used by **S2 `tile_weights`** (parameter-scoped identity). 

**7.2 Partition law (Dictionary-resolved path family).**

* **Path family:**
  `data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
* **Partitions:** `[fingerprint, parameter_hash]` (write **once** per identity; no appends; no compaction).
* **Format:** `parquet` (Dictionary governs format & location; no literal paths in code). 

**7.3 Writer sort & file-order posture.**

* **Writer sort:** `[merchant_id, legal_country_iso]`.
* **File order is non-authoritative**; the stable merge order is authoritative. *(Matches 1B S1/S2 discipline.)*  

**7.4 Identity-coherence checks (must hold before publish).**

* **Receipt parity:** `partition.fingerprint == s0_gate_receipt_1B.manifest_fingerprint`. 
* **Parameter parity:** `partition.parameter_hash` equals the `parameter_hash` used to read **`tile_weights`**.  
* If any lineage field is embedded in rows in a future schema revision, **embedded == path token** (path↔embed equality). 

**7.5 Determinism & parallelism.**

* Parallel materialisation **allowed** (e.g., per-merchant or per-country), **provided** the final dataset results from a **stable merge ordered by `[merchant_id, legal_country_iso]`** and outcomes do **not** vary with worker/scheduling.  

**7.6 Atomic publish, immutability & idempotence.**

* **Stage → fsync → single atomic move** into the identity partition. Re-publishing the same `{manifest_fingerprint, parameter_hash}` **MUST** be **byte-identical** or is a hard error.   
* **Resume semantics:** on failure, recompute deterministically and re-stage; **never** patch in place under the live partition. 

**7.7 Prohibitions (fail closed).**

* **No mixed identities** in a single publish (do not mix fingerprints or parameter hashes). 
* **No stray files/alternate layouts** inside the partition (Dictionary path/sort law; violations ⇒ writer-hygiene fail). 
* **No literal paths in code**; all IO resolves via the Dataset Dictionary (Schema remains sole shape authority). 

**7.8 Evidence (non-shape).**

* Record a determinism receipt `{partition_path, sha256_hex}` computed over bytes of all files in ASCII-lex order; include in the run report. *(Mirrors layer hashing discipline.)* 

---

# 8) Acceptance criteria (validators) **(Binding)**

**8.1 Gate & identity (pre-write).**

* Exactly one `s0_gate_receipt_1B` exists for the target `manifest_fingerprint`, it schema-validates, and its `flag_sha256_hex` matches the `_passed.flag`.
* **Fail:** `E301_NO_PASS_FLAG`, `E_RECEIPT_SCHEMA_INVALID`.

**8.2 Parameter parity.**

* The `{parameter_hash}` used to read `tile_weights` equals the publish token, and the `{seed}` used to read `outlet_catalogue` equals the publish token in `s3_requirements`.
* **Fail:** `E306_TOKEN_MISMATCH`.

**8.3 Schema conformance (shape is authoritative).**

* `s3_requirements` validates against `schemas.1B.yaml#/plan/s3_requirements` with `columns_strict: true`.
* **Fail:** `E305_SCHEMA_EXTRAS`, `E305_SCHEMA_INVALID`.

**8.4 Primary key uniqueness.**

* No duplicate `(merchant_id, legal_country_iso)` within the identity `{manifest_fingerprint, parameter_hash}` partition.
* **Fail:** `E307_PK_DUPLICATE`.

**8.5 Count equality (authoritative source = `outlet_catalogue`).**

* For each emitted pair `(merchant_id, legal_country_iso)`, `n_sites` equals the number of rows in `outlet_catalogue` for the same `{seed, fingerprint}` and the same pair.
* Zero-count pairs are not materialised.
* **Fail:** `E308_COUNTS_MISMATCH`, `E309_ZERO_SITES_ROW`.

**8.6 Site-order integrity (inherited from source).**

* For each pair, `site_order` in `outlet_catalogue` forms a contiguous, duplicate-free sequence `1..n_sites`.
* **Fail:** `E314_SITE_ORDER_INTEGRITY`.

**8.7 FK domain (ISO-2, uppercase).**

* Every `legal_country_iso` in `s3_requirements` exists in `iso3166_canonical_2024`; placeholders (e.g., `XX`, `ZZ`, `UNK`) are forbidden.
* **Fail:** `E302_FK_COUNTRY`.

**8.8 Coverage vs S2 weights (parameter-scoped).**

* For the fixed `{parameter_hash}`, every distinct `legal_country_iso` present in `s3_requirements` appears at least once in `tile_weights/parameter_hash={parameter_hash}`.
* **Fail:** `E303_MISSING_WEIGHTS`.

**8.9 Partition, immutability & atomic publish.**

* Published under `…/s3_requirements/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`.
* If the identity partition already exists and the new bytes differ, reject. Publish is staged, fsynced, and atomically moved.
* **Fail:** `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`.

**8.10 Writer sort (stable merge order).**

* Rows are stored in non-decreasing `[merchant_id, legal_country_iso]`. File order is non-authoritative.
* **Fail:** `E310_UNSORTED`.

**8.11 Prohibitions (fail-closed).**

* S3 reads only the inputs listed in §3. Any other surface (e.g., `world_countries`, `population_raster_2025`, `tz_world_2025a`) is disallowed.
* S3 must not encode or imply inter-country order; that authority remains `s3_candidate_set.candidate_rank`.
* **Fail:** `E311_DISALLOWED_READ`, `E312_ORDER_AUTHORITY_VIOLATION`.

**8.12 Determinism receipt (binding evidence).**

* Compute SHA-256 over the concatenated bytes of all files in the published partition, enumerated in ASCII-lex path order; record `{partition_path, sha256_hex}` in the run report. Re-reading and re-hashing must reproduce the same value.
* **Fail:** `E313_NONDETERMINISTIC_OUTPUT`.

---

# 9) Failure modes & canonical error codes **(Binding)**

> A run of **S3** is **rejected** if **any** condition below is triggered. On first detection the writer **MUST** abort, emit the failure record per Layer-1 failure-payload conventions, and ensure **no partials** are visible under `…/s3_requirements/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` (atomic publish; write-once). **Shape authority = JSON-Schema; IDs→paths/partitions/sort/licence = Dataset Dictionary; gate & lineage rules from S0/1A are binding.**   

### E301_NO_PASS_FLAG — 1A gate not proven *(ABORT)*

**Trigger (MUST):** Missing S0 receipt for the `manifest_fingerprint`, or `_passed.flag` content hash ≠ `SHA256(validation_bundle_1A)` for that fingerprint. **S3 MUST NOT read `outlet_catalogue` without PASS.**  
**Detection:** validate `s0_gate_receipt_1B` against `#/validation/s0_gate_receipt` and confirm its `manifest_fingerprint` equals the publish path token. S3 does not re-hash the 1A bundle.
**Authority refs:** S0 gate; 1A Dictionary gate text (“No PASS → no read”).  

### E302_FK_COUNTRY — ISO foreign-key violation *(ABORT)*

**Trigger (MUST):** Any `legal_country_iso` in S3 output not present in `iso3166_canonical_2024` (uppercase ISO-3166-1 alpha-2). 
**Detection:** FK check against the ingress ISO surface (Dictionary/Schema). 

### E303_MISSING_WEIGHTS — Coverage vs S2 weights *(ABORT)*

**Trigger (MUST):** For the fixed `{parameter_hash}`, at least one emitted `legal_country_iso` lacks a row in **`tile_weights/parameter_hash={parameter_hash}`**.  
**Detection:** Presence/coverage check only (S2’s per-country sums stay owned by S2). 

### E304_ZERO_SITES_ROW — Attempt to emit `n_sites = 0` *(ABORT)*

**Trigger (MUST):** S3 materialises any `(merchant_id, legal_country_iso)` with `n_sites = 0`. **Zero-count pairs are not materialised; this mirrors the 1A egress “zero-count elision” precedent.** 

### E305_SCHEMA_INVALID — Shape/keys do not validate *(ABORT)*

**Trigger (MUST):** `s3_requirements` fails its schema anchor (columns/types/PK/partition/sort).
**Variant:** **E305_SCHEMA_EXTRAS** — undeclared column(s) present (strict-columns posture, as used across 1B tables). 

### E306_TOKEN_MISMATCH — Path↔embed lineage inequality *(ABORT)*

**Trigger (MUST):** Any embedded lineage column (e.g., `manifest_fingerprint`, `parameter_hash`) differs from the corresponding partition token. 

### E307_PK_DUPLICATE — Primary-key duplication *(ABORT)*

**Trigger (MUST):** Duplicate `(merchant_id, legal_country_iso)` within the identity `{seed, manifest_fingerprint, parameter_hash}` partition. *(PK uniqueness is schema-owned in Layer-1 tables.)* 

### E308_COUNTS_MISMATCH — Count not equal to source rows *(ABORT)*

**Trigger (MUST):** For any `(merchant_id, legal_country_iso)`, `n_sites ≠` the number of rows in **`outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}`** for that pair (authority = 1A egress).  

### E309_ZERO_SITES_ROW — (see E304) *(ABORT)*

**Note:** Kept as an explicit code so validators can signal “zero-row emission” distinctly from general count mismatches.

### E310_UNSORTED — Writer sort not honoured *(ABORT)*

**Trigger (MUST):** Output rows are not in non-decreasing `[merchant_id, legal_country_iso]`; file order remains non-authoritative but stable writer sort is binding. 

### E311_DISALLOWED_READ — Out-of-scope surface read *(ABORT)*

**Trigger (MUST):** S3 reads surfaces other than the inputs fixed in §3 (e.g., `world_countries`, `population_raster_2025`, `tz_world_2025a`, or any separately gated convenience surface) to derive `n_sites`. **Counts source is `outlet_catalogue` only.** 

### E312_ORDER_AUTHORITY_VIOLATION — Cross-country order implied/encoded *(ABORT)*

**Trigger (MUST):** S3 output encodes or implies **inter-country order** (sole authority is 1A `s3_candidate_set.candidate_rank`; home rank=0).  

### E313_NONDETERMINISTIC_OUTPUT — Re-run produces different bytes *(ABORT)*

**Trigger (MUST):** Re-running S3 on identical sealed inputs and identities yields a different partition hash (ASCII-lex ordered bytes → SHA-256) or differing content. *(Determinism receipt pattern follows S1/S2.)* 

### E314_SITE_ORDER_INTEGRITY — Source `site_order` not contiguous *(ABORT)*

**Trigger (MUST):** In `outlet_catalogue`, any `(merchant_id, legal_country_iso)` block used for counting violates the **contiguous `site_order = {1..n}`** rule. *(Upstream egress invariant.)* 

### E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL — Publish immutability breach *(ABORT)*

**Trigger (MUST):** A partition for `{seed, manifest_fingerprint, parameter_hash}` already exists and the newly staged bytes differ. **Do not overwrite.** *(Cross-state, layer-wide immutability code retained verbatim for consistency.)* 

### E_RECEIPT_SCHEMA_INVALID — S0 receipt fails JSON-Schema *(ABORT)*
**Trigger (MUST):** `s0_gate_receipt_1B` does not validate against `schemas.1B.yaml#/validation/s0_gate_receipt`.
**Detection:** JSON-Schema validation failure on the receipt object.
**Authority refs:** S0 defines the receipt shape and gate vocabulary; S3 inherits the check before reads.

---

## 9.1 Failure handling *(normative)*

* **Abort semantics:** On any code above, stop the run; **no** files may be promoted into the live `s3_requirements` partition unless materialisation passes all checks. *(Atomic publish; write-once.)* 
* **Failure record:** Emit a failure record with at least `{code, scope ∈ {run,pair}, reason, manifest_fingerprint, parameter_hash}`; when applicable include `{merchant_id, legal_country_iso}`. *(Payload conventions mirror Layer-1 failure records used elsewhere.)* 
* **Multi-error policy:** Multiple failures **may** be recorded; acceptance remains **failed**. *(Do not attempt partial publishes.)* 

## 9.2 Code space & stability *(normative)*

* **Reserved:** `E301`–`E314` are reserved for S3 as defined here; `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL` is a shared cross-state code retained for immutability violations. 
* **SemVer impact:** Tightening triggers or adding strictly stronger checks without flipping prior PASS→FAIL on reference runs is **MINOR**; any change that can flip prior outcomes is **MAJOR** and requires re-ratification (pattern mirrors S1/S2).  

---

# 10) Observability & run-report **(Binding)**

> Observability artefacts are **required to exist** and be **retrievable** by validators, but they do **not** alter the semantics of `s3_requirements`. They **must not** be written inside the dataset partition. This posture mirrors S1/S2.  

**10.1 Deliverables (outside the dataset partition; binding for presence)**
An accepted S3 run **MUST** expose, outside `…/s3_requirements/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`:

* **S3 run report** — single machine-readable JSON object (fields in §10.2). 
* **Determinism receipt** — composite SHA-256 over the produced **partition files only** (recipe in §10.4).  
* *(Optional but recommended)* **Summaries** for auditor convenience (formats in §10.3). Presence of the run report + receipt is binding; summaries are optional. 

**10.2 S3 run report — required fields (binding for presence)**
The run report **MUST** include at least:

* `seed`
* `manifest_fingerprint` (hex64) — identity proven by S0. 
* `parameter_hash` (hex64) — parameter identity used to read `tile_weights`. 
* `rows_emitted` — total rows written to `s3_requirements`. 
* `merchants_total` — distinct `merchant_id` in the output. 
* `countries_total` — distinct `legal_country_iso` in the output. 
* `source_rows_total` — total rows counted from `outlet_catalogue` for the same `{seed,fingerprint}`. 
* `ingress_versions` — `{ iso3166: <string> }` (the ISO surface version actually read). 
* `determinism_receipt` — object per §10.4. 
* `notes` — optional, non-semantic.

> Location: control-plane artefact or job attachment/log; **MUST NOT** be stored under the dataset partition. Retain ≥ 30 days.  

**10.3 Summaries (optional; recommended formats)**

* **Per-merchant summary**: for each `merchant_id`: `countries`, `n_sites_total` (Σ of `n_sites`), `pairs` (rows for that merchant).
* **Run-scale health counters**: `fk_country_violations`, `coverage_missing_countries` (both expected 0 on acceptance).
  These may appear as an array inside the run report **or** as JSON-lines in logs; validators **must** be able to retrieve them if present.  

**10.4 Determinism receipt — composite hash (method is normative)**
Compute a **composite SHA-256** over the **produced S3 partition files only**:

1. List all files under `…/s3_requirements/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` as **relative paths**, **ASCII-lex sort** them.
2. Concatenate raw bytes in that order; compute SHA-256; encode as lowercase hex64.
3. Store as `{ "partition_path": "<path>", "sha256_hex": "<hex64>" }` in the run report.
   This mirrors the established S1/S2 determinism-receipt recipe.  

**10.5 Packaging & retention (binding)**

* Do **not** place reports/counters **inside** the dataset partition. Provide them as control-plane artefacts/logs and retain for **≥ 30 days**.  
* IO resolution for any evidence **must** follow the Dataset Dictionary (no literal paths). 

**10.6 Failure event schema (binding for presence on failure)**
On any §9 failure, emit a structured event (outside the dataset partition):

* `event: "S3_ERROR"`, `code: <one of §9>`, `at: <RFC-3339 UTC>`, `manifest_fingerprint`, `parameter_hash`; optionally `merchant_id`, `legal_country_iso`.
  This mirrors S1/S2’s failure-event posture and vocabulary.  

**10.7 Auditor checklist (what validators expect to retrieve)**

* Run report present with all **required fields**. 
* Determinism receipt present and recomputable to the same hash. 
* (If provided) summaries retrievable.
* Evidence stored **outside** the dataset partition; retention policy satisfied. 

---

# 11) Performance & scalability *(Informative)*

**11.1 Workload shape.**
S3 is a single-pass **streaming group-by** over **`outlet_catalogue`** (fingerprint partition), emitting one row per `(merchant_id, legal_country_iso)`. Because `outlet_catalogue` is writer-sorted by `[merchant_id, legal_country_iso, site_order]`, the count can be maintained with constant memory per open group. 

**11.2 Asymptotics.**
Time ≈ **O(|outlet_catalogue| + |tile_weights countries|)**; memory ≈ **O(1)** for the running counter plus **O(#countries)** for a coverage set from `tile_weights`. (S3 only checks **presence** of each country in `tile_weights` for the fixed `{parameter_hash}`.) 

**11.3 Streaming & materialisation posture.**
Prefer **no full-partition materialisation**; read `outlet_catalogue` once and stream-aggregate. This mirrors the streaming posture used in S1/S2 performance sections and avoids `O(n)` memory blowups.  

**11.4 Parallelism & determinism.**
Shard by **merchant ranges** or **country**; final publish uses a **stable merge** ordered by `[merchant_id, legal_country_iso]`. Deterministic outcomes must not depend on shard/worker layout (file order remains non-authoritative).  

**11.5 I/O posture (targets).**
Aim for **≤1.25× I/O amplification** per surface used (e.g., bytes read vs on-disk size for `outlet_catalogue` and `tile_weights`), following the same baseline-and-ratio pattern used in S1/S2.  

**11.6 Resource envelope (targets).**
Keep per-worker caps in line with S1/S2 guidance: **peak RSS ≤ 1 GiB**, **temp disk ≤ 2 GiB**, **open files ≤ 256**. These targets have proven sufficient for Layer-1 streaming jobs and preserve headroom for retries/merges.  

**11.7 Chunking & back-pressure.**
Chunk `outlet_catalogue` on contiguous **merchant** ranges (aligns with its sort) to enable strict streaming and bounded memory; throttle producers so FD/memory targets remain within §11.6 while preserving stable merge guarantees.  

**11.8 Coverage check strategy.**
Pre-scan `tile_weights` once (parameter partition) to materialise the set of **covered countries** and test membership per S3 group; the table is sorted `[country_iso, tile_id]`, so the country set can be derived with a cheap streaming distinct. 

**11.9 Observability counters (recommended additions to the run report).**
Add non-binding counters aligned with S1/S2 patterns: `bytes_read_outlet_catalogue_total`, `bytes_read_tile_weights_total`, `wall_clock_seconds_total`, `cpu_seconds_total`, `workers_used`, `max_worker_rss_bytes`, `open_files_peak`. These make the optional **PAT** replays straightforward without altering S3’s acceptance law.  

**11.10 Environment tiers (operational guidance).**
DEV: tiny ISO subset for functional checks; TEST: same code path as PROD on a fixed subset; PROD: full-scale run where any PAT is evaluated—mirroring S1/S2 operational tiers.  

*(Informative guidance above is consistent with the existing S1/S2 envelopes and with Dictionary/Schema authorities for `outlet_catalogue` and `tile_weights`; no additional binding limits are introduced here.)*

---

# 12) Change control & compatibility **(Binding)**

**12.1 SemVer ground rules.**
This S3 spec follows **MAJOR.MINOR.PATCH**. A change is **MAJOR** if it can make previously conformant S3 outputs invalid/different for the same sealed inputs and identity, or if it requires consumer changes. **MINOR** is backward-compatible tightening/additions that do not flip prior accepted reference runs to fail. **PATCH** is editorial only. This mirrors S0/S2 precedent.  

**12.2 What requires a MAJOR bump (breaking).**
S3 **MUST** increment **MAJOR** and be re-ratified if any of the following change:

* **Dataset contract for `s3_requirements`:** primary key, column set/types, `columns_strict` posture, partition keys (`[manifest_fingerprint, parameter_hash]`), writer sort, or path family. (Identity/layout/keys are breaking by precedent.) 
* **Authority/precedence model:** JSON-Schema as sole shape authority; Dictionary for IDs→paths/partitions/writer policy; Registry for provenance/licences.  
* **Gate or lineage law:** consumer-gate semantics (“**No PASS → No read**”), `_passed.flag` hashing rule/location, or path↔embed byte-equality rules used by S3. 
* **Dataset IDs / `$ref` anchors** S3 binds to (e.g., renaming `outlet_catalogue`, `tile_weights`, or this anchor). 
* **Governance weakening:** licence class reduction or retention reduction below published Dictionary/Registry values for S3 or its inputs. 

**12.3 What qualifies as MINOR (backward-compatible).**

* Tightening validators or PAT bounds **only if** proven not to flip previously accepted **reference** runs to fail. 
* Adding **non-semantic** fields to the run-report or observability outputs (outside the dataset partition). 
* Pinning/changing **writer policy** in the Registry (e.g., compression, row-group sizes) where value semantics are unchanged. *(Byte-identity requirements, if newly enforced, are documented by the Registry.)* 

**12.4 What is PATCH (non-behavioural).**
Editorial clarifications, typos, cross-reference fixes that **do not** change schemas, IDs, partitions, lineage rules, acceptance, or PAT envelopes. 

**12.5 Compatibility window (assumed baselines).**
S3 **v1.* **assumes these authorities remain on their **v1.* **line; a **MAJOR** bump in any **requires** S3 re-ratification and a **MAJOR** bump here:
`schemas.layer1.yaml` · `schemas.ingress.layer1.yaml` · `schemas.1A.yaml` · `dataset_dictionary.layer1.1A.yaml` · `schemas.1B.yaml` · `dataset_dictionary.layer1.1B.yaml`.  

**12.6 Migration & deprecation rules.**
On a **MAJOR** change: (a) freeze the old **v1.* **spec; (b) publish S3 **v2.0.0** with explicit diffs; (c) introduce a **new anchor** (e.g., `schemas.1B.yaml#/plan/s3_requirements_v2`) and **new Dictionary ID** if shape/paths change; (d) do **not** rely on Dictionary aliases to “bridge” breaking ID/path changes. 

**12.7 Lineage keys vs SemVer.**
`parameter_hash` and `manifest_fingerprint` are **orthogonal** to SemVer: they flip when governed bytes/opened artefacts change, producing a **new partition** without implying a spec change. Merging/splitting these lineage tokens would be **MAJOR**. 

**12.8 Consumer compatibility covenant (within v1.*).**
Within **v1.* **for S3:

* `s3_requirements` identity (`[manifest_fingerprint, parameter_hash]`), PK, writer sort, and count semantics (“`n_sites` equals rows in `outlet_catalogue` for the same identity; zero-count pairs elided”) remain stable. 
* Inter-country order remains **external** (authority = `s3_candidate_set.candidate_rank`); S3 neither encodes nor implies order. 
* Dictionary/Schema remain the authorities for paths/shape; implementations **must not** hard-code paths. 

**12.9 Ratification & recording.**
On release, record in governance: `semver`, `effective_date`, ratifiers, repo commit (and optional SHA-256 of this file). Keep a link to the prior major’s frozen copy. 

---

# Appendix A — Definitions & symbols *(Informative)*

## A.1 Identity & lineage tokens

* **`manifest_fingerprint`** — Lowercase **hex64** SHA-256 identifying a run’s validated artefacts; for S3 reads it **equals** the `fingerprint` path token and is proven by S0’s `s0_gate_receipt_1B`.  
* **`parameter_hash`** — Lowercase **hex64** SHA-256 of the governed **parameter bundle**; partitions parameter-scoped datasets (e.g., `tile_index`, `tile_weights`).  
* **`seed`** — Unsigned 64-bit master Philox seed for the run (S3 does not consume RNG but inherits the lineage token). 
* **`run_id`** — Lowercase **hex32** identifier for RNG event logs (not used by S3). 

## A.2 Closed domains & primitive types

* **`id64`** — Positive 64-bit identifier used for `merchant_id`. 
* **`iso2`** — ISO-3166-1 **alpha-2**, **uppercase** (placeholders such as `XX/ZZ/UNK` are **forbidden**).  
* **`hex64`** — 64-hex lowercase SHA-256 string. 
* **`uint32`/`uint64`** — Unsigned 32/64-bit integers (layer-wide `$defs`). 

## A.3 Dataset IDs, anchors, and partitions used by S3

* **`outlet_catalogue`** — Authority for outlet rows and within-country `site_order`; **order-free across countries**; partitions `[seed, fingerprint]`; schema `schemas.1A.yaml#/egress/outlet_catalogue`; **No PASS → No read** (must verify the 1A validation bundle for the same fingerprint).  
* **`s3_candidate_set`** — **Sole** cross-country order authority (`candidate_rank`, home=0); partitions `[parameter_hash]`; schema `schemas.1A.yaml#/s3/candidate_set`. *(Not read in S3; pinned for later states.)*  
* **`tile_index`** — S1 output; eligible tiles per country; partitions `[parameter_hash]`; schema `schemas.1B.yaml#/prep/tile_index`. *(Not read in S3.)* 
* **`tile_weights`** — S2 output; fixed-dp weights per eligible tile; partitions `[parameter_hash]`; schema `schemas.1B.yaml#/prep/tile_weights`. *(S3 checks **coverage** against this for the fixed `parameter_hash`.)* 
* **`iso3166_canonical_2024`** — FK target for ISO-2; schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`. 
* **`s0_gate_receipt_1B`** — Fingerprint-scoped proof of the 1A gate; schema `schemas.1B.yaml#/validation/s0_gate_receipt`.  
* **`s3_requirements`** — *(This document’s output)* deterministic counts per `(merchant_id, legal_country_iso)`; partitions `[manifest_fingerprint, parameter_hash]`; schema `schemas.1B.yaml#/plan/s3_requirements`. *(Shape defined by the canonical anchor referenced in §5.1.)* 

## A.4 Laws & posture (used repeatedly in S3)

* **Schema authority** — **JSON-Schema is the sole shape authority** (columns, domains, PK/partition/sort). Dictionary governs IDs→paths/partitions/writer policy; Registry records provenance/licences. If Dictionary and Schema disagree, **Schema wins**. 
* **Gate law** — A consumer must verify 1A’s `_passed.flag` equals `SHA256(validation_bundle_1A)` for the same fingerprint **before** reading `outlet_catalogue` (**No PASS → No read**). Proof is recorded by `s0_gate_receipt_1B`.  
* **Path↔embed equality** — Where lineage fields are embedded, they **must** byte-equal the corresponding path tokens (e.g., `manifest_fingerprint`). 
* **Order authority boundary** — Cross-country order is **not** encoded in `outlet_catalogue` or any 1B egress; consumers join `s3_candidate_set.candidate_rank`. 
* **Writer-sort vs file order** — File order is **non-authoritative**; stable writer sort is binding (e.g., S3 uses `[merchant_id, legal_country_iso]`). 

## A.5 Symbols (this state)

* **`n_sites`** — Deterministic integer count of outlets for a `(merchant_id, legal_country_iso)` pair; equals the number of rows in `outlet_catalogue` for the same `{seed, fingerprint}` and pair; **S3 elides zeros**. 
* **`candidate_rank`** — Total, contiguous rank over countries per merchant from **1A.S3**; `home = 0`. *(Not produced here.)* 

## A.6 Abbreviations

* **FK** — Foreign key.
* **PASS/ABORT** — Gate outcomes permitting/forbidding reads under this spec.
* **PK** — Primary key (per identity partition).
* **RNG** — Random number generation; S3 is **RNG-free**. 

---