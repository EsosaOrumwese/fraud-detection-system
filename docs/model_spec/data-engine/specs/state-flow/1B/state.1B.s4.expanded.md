# State-4 · Tile Allocation Plan (integerising per-tile counts)

# 1) Purpose & scope **(Binding)**

**1.1 Problem statement.**
S4 deterministically **integerises** each S3 per-country requirement `n_sites` over that country’s **eligible tiles** by applying S2’s **fixed-dp tile weights**, producing per-tile integers that **sum exactly** to the S3 count for the same `(merchant_id, legal_country_iso)`. S4 is **RNG-free**.  

**1.2 Out of scope.**
S4 does **not** perform cell selection, jitter, or lat/lon egress; it does **not** encode or imply **inter-country order** (the sole order authority remains **1A `s3_candidate_set`**). 

**1.3 Authority boundaries & invariants.**
a) **Counts source (S3):** `s3_requirements` is the only source of `n_sites` per `(merchant_id, legal_country_iso)` and is **seed+fingerprint+parameter_hash** scoped. 
b) **Weight authority (S2):** `tile_weights` defines the fractional mass over tiles (fixed-dp; **parameter_hash** scoped). 
c) **Tile universe (S1):** only tiles present in `tile_index` for the same **parameter_hash** are eligible. 
d) **Gate law (S0):** S4 **relies on** the fingerprint-scoped `s0_gate_receipt_1B` (No PASS → No read) and **does not** re-hash the 1A bundle.  
e) **Read resolution:** All reads **must** resolve by the **Dataset Dictionary** (IDs → paths/partitions/sort/licence). Shape authority remains with the JSON-Schema pack.  

**1.4 Deliverable.**
S4 emits a single **integer allocation plan** dataset (ID: **`s4_alloc_plan`**) with rows only where the per-tile allocation `n_sites_tile ≥ 1`, and for each `(merchant_id, legal_country_iso)` the **sum of per-tile allocations equals** the S3 `n_sites` for the same identity. (Identity for S4 remains `{seed, manifest_fingerprint, parameter_hash}`; counts are verified against `s3_requirements`.) 

---

# 2) Preconditions & sealed inputs **(Binding)**

**2.1 Gate (must hold before any read).**
S0 has published exactly one **`s0_gate_receipt_1B`** under `fingerprint={manifest_fingerprint}` for this run; it **schema-validates** and proves the 1A PASS. S4 **relies on the receipt** and **does not** re-hash the 1A bundle. The receipt enumerates the sealed inputs 1B may read.  

**2.2 Identities (fixed for the whole run).**
All S4 reads and writes bind to **one** `{seed}`, **one** `{manifest_fingerprint}`, and **one** `{parameter_hash}`. Mixing identities within an S4 publish is **forbidden**. (This matches S3’s identity and S2’s parameter scope.)  

**2.3 Sealed inputs (IDs → path/partitions → `$ref`).**
Resolved via the **Dataset Dictionary** (no literal paths).

* **`s3_requirements`** → `data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` · **partitions:** `[seed, fingerprint, parameter_hash]` · **schema:** `schemas.1B.yaml#/plan/s3_requirements`. *(Counts source for `n_sites`.)*  
* **`tile_weights`** → `…/parameter_hash={parameter_hash}/` · **partitions:** `[parameter_hash]` · **writer sort:** `[country_iso, tile_id]` · **schema:** `schemas.1B.yaml#/prep/tile_weights`. *(Fixed-dp weights authority.)* 
* **`tile_index`** → `…/parameter_hash={parameter_hash}/` · **partitions:** `[parameter_hash]` · **writer sort:** `[country_iso, tile_id]` · **schema:** `schemas.1B.yaml#/prep/tile_index`. *(Eligible tile universe.)* 
* **`iso3166_canonical_2024`** → **schema:** `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`. *(FK domain for `legal_country_iso`.)* 

**2.4 Inputs S4 will actually read.**
`s3_requirements`, `tile_weights`, `tile_index`, and `iso3166_canonical_2024`. *(No other surfaces.)*  

**2.5 Prohibitions (fail-closed).**
S4 **must not** read any surface not listed in §2.4 (e.g., `world_countries`, `population_raster_2025`, `tz_world_2025a`), and **must not** encode or imply inter-country order (authority remains **1A `s3_candidate_set`**).  

**2.6 Path↔embed & identity parity.**
Where lineage fields are embedded, they **must equal** the corresponding path tokens; the `{parameter_hash}` used to read **S2** tables equals the publish token; the `{seed}` used to read `s3_requirements` equals the publish token. *(Same parity rules as S3.)* 

**2.7 RNG posture.**
S4 **consumes no RNG** and writes **no RNG logs**; it is purely deterministic. *(Consistent with S3/S2 posture.)* 

---

# 3) Inputs & authority boundaries **(Binding)**

**3.1 Required datasets (IDs → `$ref` → partitions; resolve via Dictionary only).**

* **`s3_requirements`** → `schemas.1B.yaml#/plan/s3_requirements` · **partitions:** `[seed, fingerprint, parameter_hash]` · **writer sort:** `[merchant_id, legal_country_iso]` · **law:** sole authority for `n_sites` (count source).  
* **`tile_weights`** → `schemas.1B.yaml#/prep/tile_weights` · **partitions:** `[parameter_hash]` · **writer sort:** `[country_iso, tile_id]` · **law:** fixed-dp fractional mass; S4 **must not** alter weights. 
* **`tile_index`** → `schemas.1B.yaml#/prep/tile_index` · **partitions:** `[parameter_hash]` · **law:** eligible tile universe (no extras outside this set). 
* **`iso3166_canonical_2024`** → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` · **law:** FK domain for `legal_country_iso`. 

**3.2 Sealed but **not** read by S4 (declared for boundary clarity).**

* **`outlet_catalogue`** — upstream egress (seed+fingerprint); not read by S4. 
* **`s3_candidate_set`** — sole inter-country order authority (1A); **not** read by S4. 

**3.3 Precedence & resolution rules.**

* **Shape authority:** JSON-Schema pack (columns, domains, PK/partition/sort).
* **IDs→paths/partitions/sort/licence:** Dataset Dictionary.
* If Dictionary text and Schema differ on shape, **Schema wins**. **No literal paths** in code; all IO resolves by Dictionary. 

**3.4 Authority boundaries (what S4 MUST / MUST NOT do).**

* **Counts source:** use **only** `s3_requirements` to obtain `n_sites` per `(merchant_id, legal_country_iso)`. S4 **must not** derive counts from any other surface. 
* **Weights:** use **only** `tile_weights` (for the fixed `{parameter_hash}`) as fractional mass; **no re-normalisation** beyond the fixed-dp rounding plan defined for S4. 
* **Universe:** allocate **only** over tiles present in `tile_index` for the same `{parameter_hash}`; any tile not in `tile_index` is **ineligible**. 
* **Order boundary:** S4 **does not** encode or imply inter-country order; authority remains **1A `s3_candidate_set`**. 
* **Gate law:** S4 **relies on** the fingerprint-scoped `s0_gate_receipt_1B`; it **does not** re-hash 1A’s bundle. 

**3.5 Identities bound for this state.**

* All reads/writes use **one** `{seed}`, **one** `{manifest_fingerprint}`, **one** `{parameter_hash}` for the entire S4 publish; mixing identities is **forbidden**. 

**3.6 Prohibited surfaces (fail-closed).**

* S4 **must not** read `world_countries`, `population_raster_2025`, `tz_world_2025a`, or any surface not listed in §3.1 for allocation logic. Evidence of such reads is a validation failure. 

**3.7 Path↔embed equality (where embedded).**

* If lineage fields are embedded in rows in future revisions, their values **must equal** the corresponding path tokens. (Same parity rule as S3.) 

---

# 4) Outputs (datasets) & identity **(Binding)**

**4.1 Dataset ID & canonical schema anchor.**

* **ID:** `s4_alloc_plan`
* **Schema (sole shape authority):** `schemas.1B.yaml#/plan/s4_alloc_plan` *(canonical anchor; shape lives in schema, not repeated here).*  

**4.2 Path family, partitions, writer sort & format (Dictionary law).**
Writers **must** resolve via the Dataset Dictionary (no literal paths). The path family is:

```
data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
```

* **Partitions:** `[seed, fingerprint, parameter_hash]` (one publish per identity; write-once).
* **Writer sort:** `[merchant_id, legal_country_iso, tile_id]` (stable merge order; file order non-authoritative).
* **Format:** `parquet`.
  These mirror the S3/S2 identity and sorting posture already in your packs.  

**4.3 Row admission.**
Emit a row **iff** the computed per-tile allocation `n_sites_tile ≥ 1` for `(merchant_id, legal_country_iso, tile_id)` under the fixed identity triple. (Zeros are not materialised.)

**4.4 Immutability & atomic publish.**
Write-once per `{seed, manifest_fingerprint, parameter_hash}`. Re-publishing to the same identity **must be byte-identical** or is a hard error. Publish via stage → fsync → single atomic move; file order is non-authoritative. 

**4.5 Identity & lineage constraints.**
A run **binds to exactly one** `{seed}`, **one** `{manifest_fingerprint}` (proven by S0 receipt), and **one** `{parameter_hash}` (matching S2). Mixing identities within an S4 publish is **forbidden**. Where lineage fields are embedded in rows in future revisions, values **must equal** the corresponding path tokens. 

**4.6 Licence, retention, PII (Dictionary authority).**
Licence/retention/PII are governed by the Dataset Dictionary entry for `s4_alloc_plan`. Writers **must not** override these at write time. (Follows the same policy used for `s3_requirements`.) 

**4.7 Forward consumers (non-authoritative note).**
Produced by **1B.S4**; consumed by **1B.S5+** (cell selection/jitter) and ultimately by egress shaping. Inter-country order remains external (authority = **1A `s3_candidate_set`**). 

---

# 5) Dataset shapes & schema anchors **(Binding)**

**5.1 Canonical anchor (single source of truth).**
The dataset shape for this state is defined **exclusively** by the JSON-Schema anchor **`schemas.1B.yaml#/plan/s4_alloc_plan`**. This document **does not** restate columns, domains, PK/partition/sort, or FKs. The schema pack **MUST** include this anchor before any S4 publish.

**5.2 Ownership & precedence.**

* **Shape authority:** JSON-Schema (the anchor above).
* **IDs→paths/partitions/writer policy/licence:** Dataset Dictionary.
* **Provenance/licences:** Artefact Registry.
  If Dictionary text and Schema ever differ on shape, **Schema wins**.

**5.3 Validation obligation.**
All writers/validators **must** validate any `s4_alloc_plan` publish against the anchor in §5.1. Any deviation (missing/extra/mistyped columns; PK/partition/sort drift) is a **schema-conformance failure** (see §8/§9).

**5.4 Columns-strict posture.**
The anchor enforces a **strict column set** (no undeclared columns). This spec relies on the anchor for that rule and does not duplicate it here.

**5.5 Compatibility (schema-owned).**
Any change to the anchor’s keys/columns/partitioning/sort or FK targets is **MAJOR** per §12. Additive, non-semantic observability fields outside the dataset partition are **MINOR**. Editorial text changes here are **PATCH** and do **not** alter shape.

**5.6 Cross-file `$ref` hygiene.**
Cross-schema references (e.g., shared ID/ISO defs or FK surfaces) are **declared in the schema pack**; this spec references only the canonical anchor in §5.1.

---

# 6) Deterministic algorithm (no RNG) **(Binding)**

**6.1 Fix identity & gate (precompute once).**
a) Fix the **identity triple** `{seed, manifest_fingerprint, parameter_hash}` for the whole run.
b) Validate the **S0 receipt** for `manifest_fingerprint` (schema-valid; No PASS → No read). S4 **relies on the receipt** and **does not** re-hash the 1A bundle.
c) Resolve all surfaces via the **Dataset Dictionary** (no literal paths).

**6.2 Locate inputs (identity-parity checks).**
a) `s3_requirements` under `…/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`.
b) `tile_weights` and `tile_index` under `…/parameter_hash={parameter_hash}/`.
c) **Parity:** the `{seed}` used to read `s3_requirements` and the `{parameter_hash}` used to read S2 tables **must equal** the S4 publish tokens.

**6.3 Country frame (eligibility & coverage).**
For each distinct `legal_country_iso` present in `s3_requirements` for the fixed identity:
a) **Eligibility (universe):** `tile_index` rows for that country form the eligible tile set.
b) **Coverage (weights):** `tile_weights` for that country provide fixed-dp integer weights over the same eligible tiles.
c) **Non-emptiness:** both sets must be non-empty; otherwise fail closed per §9.

**6.4 Per-pair allocation (no RNG).**
For each `(merchant_id, legal_country_iso, n_sites)` in `s3_requirements`:

1. **Read weights.** From `tile_weights` for that `legal_country_iso`, read rows `(tile_id, weight_fp, dp)` on the eligible tiles. Let `K := 10^dp`. (Group law: per-country `Σ weight_fp = K` is guaranteed by S2.)
2. **Quotas.** For each tile `i`:

   * `q_i := (weight_fp[i] / K) × n_sites` (conceptual).
   * **Integer base:** `z_i := ⌊(weight_fp[i] × n_sites) / K⌋` (integer arithmetic).
   * **Residue (integer numerator):** `rnum_i := (weight_fp[i] × n_sites) mod K`.
3. **Shortfall.** `S := n_sites − Σ_i z_i`. (By construction, `0 ≤ S < #tiles`.)
4. **Residue law (deterministic):** add **+1** to exactly `S` tiles with **largest** `rnum_i`; **tie-break** by **ascending numeric `tile_id`**.
5. **Emit positives only.** For each tile, `n_sites_tile := z_i (+1 if bumped)`; **emit a row iff `n_sites_tile ≥ 1`**.

**6.5 Conservation & integrity (must hold per pair).**
a) **Sum-to-n:** `Σ_tile n_sites_tile = n_sites`.
b) **Universe:** every `(legal_country_iso, tile_id)` emitted **must exist** in `tile_index` for the same `{parameter_hash}`.
c) **No renormalisation:** S4 **must not** alter or re-scale `weight_fp` or `dp`.

**6.6 Materialisation & writer discipline.**
a) **Path family:** publish under `…/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`.
b) **Writer sort:** rows in non-decreasing `[merchant_id, legal_country_iso, tile_id]`; **file order is non-authoritative**.
c) **Write-once:** re-publishing to the same identity must be **byte-identical**; stage → fsync → single atomic move.

**6.7 Identity & lineage equality.**
Where lineage fields are embedded in rows (now or in future revisions), their values **must equal** the corresponding path tokens `{seed, manifest_fingerprint, parameter_hash}`.

**6.8 Determinism & arithmetic guarantees.**
a) **No RNG** anywhere in S4.
b) Use **integer arithmetic** for `weight_fp × n_sites`, `div`, and `mod` to avoid FP rounding; `K = 10^dp`.
c) Re-running S4 on identical sealed inputs and identity must reproduce **byte-identical** output (file order non-authoritative).

**6.9 Prohibitions (fail-closed).**
a) Do **not** read any surface outside §2.4.
b) Do **not** encode or imply inter-country order (authority remains 1A `s3_candidate_set`).
c) Do **not** emit zero-allocation rows.
d) Do **not** mix identities within a publish.

---

# 7) Identity, partitions, ordering & merge discipline **(Binding)**

**7.1 Identity tokens (one triple per publish).**
S4 binds all reads/writes to exactly one **`{seed, manifest_fingerprint, parameter_hash}`**. Mixing identities within a single publish is **forbidden**. (Matches S3’s run identity and S2’s parameter scope.) 

**7.2 Partition law (Dictionary-resolved path family).**
All IO **must** resolve via the Dataset Dictionary (no literal paths). The S4 path family is:
`data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
**Partitions:** `[seed, fingerprint, parameter_hash]` · **Format:** parquet · **Write-once** per identity; no appends/compaction. (Partitioning mirrors the S3 path law and triple identity.)  

**7.3 Writer sort & file-order posture.**
Rows **must** be written in non-decreasing `[merchant_id, legal_country_iso, tile_id]`. File order is **non-authoritative**; the stable writer sort is binding (same posture used by S3). 

**7.4 Identity-coherence checks (must hold before publish).**

* **Receipt parity (fingerprint):** `partition.fingerprint == s0_gate_receipt_1B.manifest_fingerprint`. (S0 receipt is fingerprint-scoped.)  
* **Parameter parity (S2 scope):** `partition.parameter_hash` equals the `{parameter_hash}` used to read `tile_weights`/`tile_index`. (Those tables are parameter-scoped.) 
* **Seed parity (S3 scope):** `partition.seed` equals the `{seed}` used to read `s3_requirements`. (S3 is seed+fingerprint+parameter_hash scoped.)  
* **Path↔embed equality:** where lineage fields are embedded in rows, values **must equal** their path tokens. (Same equality law used by S0 for `manifest_fingerprint`.) 

**7.5 Parallelism & determinism.**
Parallel materialisation is allowed (e.g., sharding by `merchant_id` or `(merchant_id, legal_country_iso)`), **provided** the final dataset is the stable merge ordered by `[merchant_id, legal_country_iso, tile_id]` and outcomes do **not** vary with worker layout. 

**7.6 Atomic publish, immutability & idempotence.**
Publish via **stage → fsync → single atomic move** into the identity partition. Re-publishing under the same `{seed, manifest_fingerprint, parameter_hash}` must be **byte-identical** or is a hard error. (Matches S3’s publish law.) 

**7.7 Prohibitions (fail-closed).**

* **No mixed identities** (no mixing seeds, fingerprints, or parameter hashes within one publish). 
* **No literal paths in code;** all reads/writes resolve by Dataset Dictionary. 

**7.8 Evidence (non-shape).**
Record a determinism receipt `{ partition_path, sha256_hex }` computed over ASCII-lex ordered file bytes of the published partition; store outside the dataset partition (run report). (Same receipt posture as S3.) 

---

# 8) Acceptance criteria (validators) **(Binding)**

**8.1 Gate & identity (pre-write).**

* Exactly one `s0_gate_receipt_1B` exists for the target `manifest_fingerprint` and **schema-validates**; S4 **relies on the receipt** (does **not** re-hash the 1A bundle).
* **Identity parity:** publish path tokens `{seed, manifest_fingerprint, parameter_hash}` **match** the tokens used to read `s3_requirements` (seed+fingerprint+param) and S2 tables (param).
* **Fail:** `E301_NO_PASS_FLAG`, `E406_TOKEN_MISMATCH`, `E_RECEIPT_SCHEMA_INVALID`.    

**8.2 Schema conformance (shape is authoritative).**

* `s4_alloc_plan` **validates** against `schemas.1B.yaml#/plan/s4_alloc_plan` (strict columns; PK/partition/sort exactly as the anchor).
* **Fail:** `E405_SCHEMA_INVALID`, `E405_SCHEMA_EXTRAS`. 

**8.3 Primary-key uniqueness.**

* No duplicate `(merchant_id, legal_country_iso, tile_id)` within a `{seed, manifest_fingerprint, parameter_hash}` partition.
* **Fail:** `E407_PK_DUPLICATE`. 

**8.4 Sum-to-n (conservation).**

* For every `(merchant_id, legal_country_iso)`, `Σ_tile n_sites_tile == s3_requirements.n_sites` for the **same identity**.
* **Fail:** `E404_ALLOCATION_MISMATCH`. 

**8.5 Universe & coverage.**

* Every `(legal_country_iso, tile_id)` emitted **exists** in `tile_index` for the selected `{parameter_hash}`; the country is **present** in `tile_weights` for that `{parameter_hash}`.
* **Fail:** `E403_ZERO_TILE_UNIVERSE`, `E402_MISSING_TILE_WEIGHTS`, `E413_TILE_NOT_IN_INDEX`. 

**8.6 Residue law (deterministic tie-break).**

* Integerisation follows **largest-remainder** on `rnum_i = (weight_fp × n_sites) mod 10^dp`, and ties break by **ascending numeric `tile_id`**.
* **Fail:** `E411_TIE_RULE_VIOLATION`. 

**8.7 Positivity & integers.**

* All `n_sites_tile` are integers with `n_sites_tile ≥ 1`; zero rows are **not** materialised.
* **Fail:** `E412_ZERO_ROW_EMITTED`. 

**8.8 Partition & immutability.**

* Published under `…/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`; re-publishing to the same identity must be **byte-identical**; stage → fsync → atomic move.
* **Fail:** `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`.  

**8.9 Writer sort (stable merge order).**

* Rows in non-decreasing `[merchant_id, legal_country_iso, tile_id]`; file order non-authoritative.
* **Fail:** `E408_UNSORTED`. 

**8.10 Prohibitions (fail-closed).**

* S4 reads **only** the inputs in §2.4; no reads of `world_countries`, `population_raster_2025`, `tz_world_2025a`.
* S4 does **not** alter `weight_fp`/`dp`, re-scale weights, or encode inter-country order (authority = 1A `s3_candidate_set`).
* **Fail:** `E409_DISALLOWED_READ`, `E414_WEIGHT_TAMPER`, `E312_ORDER_AUTHORITY_VIOLATION`.  

**8.11 Determinism receipt (binding evidence).**

* Run report contains a composite SHA-256 over ASCII-lex ordered bytes of all files in the published partition; re-reading reproduces the **same** hash.
* **Fail:** `E410_NONDETERMINISTIC_OUTPUT`. 

**8.12 Required run-report fields (presence only).**

* `seed`, `manifest_fingerprint`, `parameter_hash`, `rows_emitted`, and determinism receipt `{partition_path, sha256_hex}` present **outside** the dataset partition.
* **Fail:** `E415_RUN_REPORT_MISSING_FIELDS`. 

---

# 9) Failure modes & canonical error codes **(Binding)**

> **Fail-closed posture.** Any condition below **ABORTS** the run. On first detection the writer **must** stop, emit a failure record, and ensure **no partials** are visible under `…/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` (write-once; atomic publish). Shape authority = **Schema**; IDs→paths/partitions/sort/licence = **Dictionary**; gate law relies on **S0 receipt**.   

### E301_NO_PASS_FLAG — S0 gate not proven *(ABORT)*

**Trigger:** Missing/incorrect `s0_gate_receipt_1B` for `manifest_fingerprint`.
**Detection:** Receipt not found or fails the S0 schema; S4 does **not** re-hash 1A’s bundle. 

### E_RECEIPT_SCHEMA_INVALID — S0 receipt fails schema *(ABORT)*

**Trigger:** `s0_gate_receipt_1B` does not validate against its schema.
**Detection:** JSON-Schema validation failure on the receipt object. 

### E401_NO_S3_REQUIREMENTS — Missing S3 input *(ABORT)*

**Trigger:** No `s3_requirements` for `{seed, manifest_fingerprint, parameter_hash}`.
**Detection:** Dictionary-resolved path empty or unreadable for that identity.  

### E402_MISSING_TILE_WEIGHTS — Country lacks weights *(ABORT)*

**Trigger:** A country in `s3_requirements` has **no** rows in `tile_weights` for `{parameter_hash}`.
**Detection:** Presence check on `tile_weights` by `country_iso`. 

### E403_ZERO_TILE_UNIVERSE — No eligible tiles *(ABORT)*

**Trigger:** `tile_index` has **zero** tiles for a required country (same `{parameter_hash}`).
**Detection:** Universe check on `tile_index` by `country_iso`. 

### E404_ALLOCATION_MISMATCH — Sum-to-n violated *(ABORT)*

**Trigger:** For any `(merchant_id, legal_country_iso)`, `Σ_tile n_sites_tile ≠ s3_requirements.n_sites`.
**Detection:** Conservation validator over the produced partition. 

### E405_SCHEMA_INVALID — Shape/keys invalid *(ABORT)*

**Variant:** **E405_SCHEMA_EXTRAS** — undeclared column(s) present.
**Trigger:** `s4_alloc_plan` fails `#/plan/s4_alloc_plan` (columns/PK/partition/sort).
**Detection:** JSON-Schema validation failure. 

### E406_TOKEN_MISMATCH — Path↔identity inequality *(ABORT)*

**Trigger:** Any publish token `{seed|fingerprint|parameter_hash}` differs from the tokens used to read inputs (S3 or S2).
**Detection:** Identity parity checks prior to publish. 

### E407_PK_DUPLICATE — Duplicate PK *(ABORT)*

**Trigger:** Duplicate `(merchant_id, legal_country_iso, tile_id)` within the identity partition.
**Detection:** PK uniqueness validator. 

### E408_UNSORTED — Writer sort violated *(ABORT)*

**Trigger:** Rows not in non-decreasing `[merchant_id, legal_country_iso, tile_id]`.
**Detection:** Sort-order validator. 

### E409_DISALLOWED_READ — Out-of-scope surface read *(ABORT)*

**Trigger:** S4 reads any surface not listed in §2.4 (e.g., `world_countries`, `population_raster_2025`, `tz_world_2025a`).
**Detection:** Access logs / audit checks. 

### E410_NONDETERMINISTIC_OUTPUT — Re-run hash differs *(ABORT)*

**Trigger:** Determinism receipt over the published partition does not reproduce on re-read.
**Detection:** Composite SHA-256 mismatch (ASCII-lex file order). 

### E411_TIE_RULE_VIOLATION — Residue tie-break wrong *(ABORT)*

**Trigger:** Largest-remainder applied but ties not broken by **ascending numeric `tile_id`**.
**Detection:** Recompute residues and compare tie selection. 

### E412_ZERO_ROW_EMITTED — Zero allocations materialised *(ABORT)*

**Trigger:** Any emitted row has `n_sites_tile = 0`.
**Detection:** Positivity validator.

### E413_TILE_NOT_IN_INDEX — Tile outside universe *(ABORT)*

**Trigger:** Emitted `(legal_country_iso, tile_id)` not present in `tile_index` for `{parameter_hash}`.
**Detection:** FK/universe check against `tile_index`. 

### E414_WEIGHT_TAMPER — Weights altered *(ABORT)*

**Trigger:** S4 renormalises or mutates `weight_fp`/`dp` semantics (beyond deterministic residue allocation).
**Detection:** Compare against `tile_weights` for `{parameter_hash}`. 

### E415_RUN_REPORT_MISSING_FIELDS — Required run-report fields missing *(ABORT)*
**Trigger:** One or more required fields from §10.2 are absent (e.g., seed, manifest_fingerprint, parameter_hash, rows_emitted, or determinism_receipt).
**Detection:** Run-report presence/shape check outside the dataset partition.

### E312_ORDER_AUTHORITY_VIOLATION — Order implied/encoded *(ABORT)*

**Trigger:** S4 output encodes or implies inter-country order (sole authority = 1A `s3_candidate_set`).
**Detection:** Presence of order fields or derivations across countries. 

### E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL — Overwrite attempt *(ABORT)*

**Trigger:** A partition for `{seed, manifest_fingerprint, parameter_hash}` already exists with different bytes.
**Detection:** Byte comparison before atomic publish; reject non-identical writes. 

---

## 9.1 Failure handling *(normative)*

* **Abort semantics:** Stop the run; **no** files promoted into the live `s4_alloc_plan` partition unless all validators PASS. (Stage → fsync → **single atomic move** only after PASS.) 
* **Failure record (outside dataset partition):** `{code, scope ∈ {run,pair}, reason, seed, manifest_fingerprint, parameter_hash}`; when applicable add `{merchant_id, legal_country_iso}`. Retain per your Dictionary/Registry practice. 
* **Multi-error policy:** Multiple failures **may** be recorded; acceptance remains **failed**.

## 9.2 Code space & stability *(normative)*

* **Reserved (this state):** `E401`–`E415` as defined above. Cross-state codes reused here: `E301_*`, `E312_*`, and `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`.
* **SemVer impact:** Tightening triggers that do not flip prior accepted reference runs = **MINOR**; any change that can flip prior outcomes (or identity/partitioning) = **MAJOR**. 

---

# 10) Observability & run-report **(Binding)**

> Observability artefacts are **required to exist** and be **retrievable** by validators, but they do **not** alter the semantics of `s4_alloc_plan`. They **must not** be written inside the dataset partition. This posture mirrors S3/S1/S2. 

**10.1 Deliverables (outside the dataset partition; binding for presence)**
An accepted S4 run **MUST** expose, outside
`…/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`:

* **S4 run report** — single machine-readable JSON object (fields in §10.2).
* **Determinism receipt** — composite SHA-256 over the produced **partition files only** (recipe in §10.4).
* *(Optional but recommended)* **Summaries** for auditor convenience (formats in §10.3). Presence of the run report + receipt is binding; summaries are optional.
  (Location: control-plane artefact or job attachment/log; **MUST NOT** be stored under the dataset partition. Retain ≥ 30 days.) 

**10.2 S4 run report — required fields (binding for presence)**
The run report **MUST** include at least:

* `seed` — lineage token used for S3/S4 identity. 
* `manifest_fingerprint` (hex64) — identity proven by S0 receipt. 
* `parameter_hash` (hex64) — parameter identity used to read S2 tables. 
* `rows_emitted` — total rows written to `s4_alloc_plan`.
* `merchants_total` — distinct `merchant_id` in the output.
* `pairs_total` — distinct `(merchant_id, legal_country_iso)` in the output.
* `alloc_sum_equals_requirements` — boolean (true iff §8.4 conservation holds across all pairs).
* `ingress_versions` — `{ iso3166: <string> }` (the ISO surface version actually read). 
* `determinism_receipt` — object per §10.4.

**10.3 Summaries (optional; recommended formats)**

* **Per-merchant summary**: per `merchant_id` — `countries`, `n_sites_total` (Σ of `n_sites_tile` across tiles), `pairs` (rows for that merchant at pair-level).
* **Run-scale health counters**: `fk_country_violations`, `coverage_missing_countries`, `tile_not_in_index` — all expected **0** on acceptance.
  (These may appear inside the run report or alongside it as JSON-lines; validators **must** be able to retrieve them if present.) 

**10.4 Determinism receipt — composite hash (method is normative)**
Compute a **composite SHA-256** over the **produced S4 partition files only**:

1. List all files under
   `…/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
   as **relative paths**, **ASCII-lex sort** them.
2. Concatenate raw bytes in that order; compute SHA-256; encode as lowercase hex64.
3. Store as `{ "partition_path": "<path>", "sha256_hex": "<hex64>" }` in the run report.
   (Mirrors the established S3 determinism-receipt recipe.) 

**10.5 Packaging & retention (binding)**

* Do **not** place reports/receipts/summaries **inside** the dataset partition. Provide them as control-plane artefacts/logs and retain for **≥ 30 days**. 
* All IO resolution for evidence **must** follow the Dataset Dictionary (no literal paths). 

**10.6 Failure event schema (binding for presence on failure)**
On any §9 failure, emit a structured event (outside the dataset partition):

* `event: "S4_ERROR"`, `code: <one of §9>`, `at: <RFC-3339 UTC>`,
  **`seed`**, **`manifest_fingerprint`**, **`parameter_hash`**; optionally `merchant_id`, `legal_country_iso`.
  (Posture mirrors S3’s failure-event vocabulary.) 

**10.7 Auditor checklist (retrievability expectations)**

* Run report present with all **required fields** in §10.2.
* Determinism receipt present and recomputable to the same hash.
* If summaries exist, they’re retrievable.
* Evidence stored **outside** the dataset partition; retention policy satisfied. 

---

# 11) Performance & scalability **(Informative)**

**11.1 Workload model.**
Stream over **`s3_requirements`** (seed+fingerprint+param partition) by `(merchant_id, legal_country_iso)`. For each country, read its **`tile_weights`** slice (and eligible **`tile_index`** rows) once, integerise, and emit only **positive** per-tile allocations. No cross-product materialisation.

**11.2 Asymptotics.**
Time ≈ `O(|s3_requirements| + Σ_c |weights_c|)`; memory ≈ `O(max_c |weights_c|)` (per active country) plus small buffers for merge/write. Integer arithmetic only (`K=10^dp`) to avoid FP drift.

**11.3 Caching strategy.**
For a fixed `{parameter_hash}`, keep an in-memory or on-disk cache keyed by `legal_country_iso` with `(tile_id, weight_fp, dp)` and the **eligible tile set**. Evict LRU by country to respect memory caps.

**11.4 Parallelism (deterministic).**
Shard by **merchant ranges** or by `(merchant_id, legal_country_iso)`. Each shard operates independently but the final publish is a **stable merge** ordered by `[merchant_id, legal_country_iso, tile_id]`. Outcomes must not vary with worker layout.

**11.5 I/O posture.**
Aim for **≤1.25×** I/O amplification per surface (bytes read vs on-disk). Single pass over `s3_requirements`; per-country streaming reads from `tile_weights`/`tile_index`. Avoid fan-out shuffles; writer sort yields sequential, append-friendly output.

**11.6 Resource envelope (targets).**
Per worker: **RSS ≤ 1 GiB**, temp disk **≤ 2 GiB**, **≤ 256** open files. Prefer compressed columnar output with moderate row-groups (e.g., ~100k–250k rows) to balance read/scan efficiency and memory.

**11.7 Chunking & back-pressure.**
Chunk `s3_requirements` by **merchant ranges** that keep the largest country’s weight slice resident. Apply back-pressure to keep peak RSS within §11.6 while sustaining throughput.

**11.8 Fast-fail guards.**
Before allocation, pre-check per-country **coverage** (present in `tile_weights`) and **universe** (non-empty in `tile_index`). Fail early for any missing or zero-universe country to avoid wasted compute.

**11.9 Observability (performance counters).**
Record non-binding counters in the run report: `bytes_read_{s3,weights,index}`, `rows_emitted`, `pairs_total`, `ties_broken_total`, `wall_clock_seconds_total`, `cpu_seconds_total`, `workers_used`, `max_worker_rss_bytes`, `open_files_peak`. These enable PAT replays and regressions without altering acceptance.

**11.10 Environment tiers.**
DEV: tiny, fixed ISO subset for function checks. TEST: same code path as PROD on a reproducible slice. PROD: full scale; determinism receipt and all validators enforced.

---

# 12) Change control & compatibility **(Binding)**

**12.1 SemVer ground rules.**
This state follows **MAJOR.MINOR.PATCH**.

* **MAJOR**: any change that can make previously conformant S4 outputs **invalid or different** for the same sealed inputs and identity, or that requires consumer changes.
* **MINOR**: strictly backward-compatible additions/tightenings that do **not** flip accepted reference runs from PASS→FAIL.
* **PATCH**: editorial only (no behaviour change).

**12.2 What requires a MAJOR bump (breaking).**

* **Dataset contract for `s4_alloc_plan`**: PK, column set/types, `columns_strict` posture, **partition keys** (`[seed, manifest_fingerprint, parameter_hash]`), **writer sort** (`[merchant_id, legal_country_iso, tile_id]`), or **path family**.
* **Integerisation semantics**: quota formula, residue computation (`mod 10^dp`), **tie-break rule** (ascending numeric `tile_id`).
* **Authority/precedence model**: Schema as sole shape authority; Dictionary governs IDs→paths/partitions/sort/licence; Registry holds provenance/licences.
* **Gate/lineage law**: reliance on S0 receipt (no bundle re-hash in S4), path↔embed equality rules.
* **Inputs or identity set**: changing the required inputs (e.g., adding/removing `tile_weights`/`tile_index`) or altering the identity token set (adding/removing any of `{seed, manifest_fingerprint, parameter_hash}`).

**12.3 What qualifies as MINOR (backward-compatible).**

* Adding **non-semantic** fields to the run-report/summaries (outside the dataset partition).
* Tightening validators where proven not to flip prior accepted **reference** runs (e.g., clearer diagnostics, additional checks that only catch genuinely invalid publishes).
* Registry/Dictionary **writer-policy** refinements that leave value semantics unchanged (e.g., compression/row-group sizing), or clarifying notes that don’t alter shape or identity.

**12.4 What is PATCH (non-behavioural).**

* Wording fixes, cross-reference repairs, examples/figures, or clarifications that **do not** change schemas, anchors, identities, acceptance rules, or failure codes.

**12.5 Compatibility window (assumed upstream stability).**
Within S4 **v1.***, the following remain on their own **v1.*** lines:

* **S3** `s3_requirements` (counts source; identity = `[seed, manifest_fingerprint, parameter_hash]`).
* **S2** `tile_weights`, **S1** `tile_index` (parameter-scoped shapes/semantics).
  If any of those bumps **MAJOR** or their anchors/IDs move, S4 must be **re-ratified** and bump **MAJOR** accordingly.

**12.6 Migration & deprecation.**
On a MAJOR:
a) Freeze the old S4 spec/version and anchors;
b) Introduce a **new schema anchor** (e.g., `#/plan/s4_alloc_plan_v2`) and, if shape/paths change, a **new Dictionary ID**;
c) Document exact diffs and a cut-over plan;
d) Do **not** rely on Dictionary aliases to silently bridge breaking ID/path changes.

**12.7 Lineage tokens vs SemVer.**
`seed`, `manifest_fingerprint`, and `parameter_hash` are **orthogonal** to SemVer. They change with governed inputs/parameters, producing new partitions **without implying** a spec change. Merging/splitting or renaming these identity tokens is **MAJOR**.

**12.8 Consumer compatibility covenant (within v1.*).**
For S4 **v1.***:

* `s4_alloc_plan` identity = `[seed, manifest_fingerprint, parameter_hash]`; PK and writer sort remain as specified.
* Integerisation preserves **sum-to-n** and uses **largest-remainder + ascending numeric `tile_id` tie-break**.
* Inputs/authority boundaries remain: counts from **S3**, weights from **S2**, universe from **S1**; **no RNG**; order authority remains with **1A** (not encoded here).
* Evidence (run report, determinism receipt) stays **outside** the dataset partition.

**12.9 Ratification record.**
Each release must record: `semver`, `effective_date`, ratifiers, code commit (and optional SHA-256 of this file). Keep a link to the prior MAJOR’s frozen copy.

---