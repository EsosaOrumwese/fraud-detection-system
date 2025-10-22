# State-7 — Site synthesis & conformance (deterministic)

# 1) Document metadata & status **(Binding)**

**State ID (canonical):** `layer1.1B.S7` — *Site synthesis & conformance (deterministic).*
**Document type:** Contractual specification (behavioural + data contracts; no code/pseudocode). **Shapes** are owned by JSON-Schema; **IDs→paths/partitions/writer policy** resolve via the Dataset Dictionary; provenance/licence notes live in the Artefact Registry. Implementations **MUST NOT** hard-code paths. 

## 1.1 Status & governance

**Status:** planning → alpha → beta → **stable** (governance-controlled).
**Precedence (tie-break):** **Schema** ≻ **Dictionary** ≻ **Registry** ≻ **this state spec**. If Dictionary prose and Schema ever disagree on **shape**, **Schema wins**; Dictionary still governs **paths/partitions/writer policy**. 

## 1.2 Normative language (RFC 2119/8174)

Key words **MUST, MUST NOT, SHALL, SHALL NOT, SHOULD, SHOULD NOT, MAY** are normative. Anything marked *Informative* is non-binding. (Matches the posture used across S1/S2.)  

## 1.3 Compatibility window (baselines this spec assumes)

S7 is written against—and assumes—these frozen surfaces are in effect:

* **Upstream datasets (1B):** `s5_site_tile_assignment` and `s6_site_jitter` with partitions `[seed, fingerprint, parameter_hash]`, writer-sorts fixed by Schema/Dictionary, and write-once/atomic-move posture.  
* **Authoritative geometry (S1):** `tile_bounds` partitioned by `[parameter_hash]` (read-only to S7).
* **Gate law:** 1A egress is read only after verifying the fingerprint-scoped S0 receipt (**No PASS → No read**). 

Any MAJOR change to those (e.g., partition keys, writer sort, identity semantics, or gate law) requires re-ratifying S7.  

## 1.4 Identity & lineage posture (state-wide)

* **Identity tokens:** exactly one `{seed, manifest_fingerprint, parameter_hash}` for the entire S7 publish; path token `fingerprint=…` MUST byte-equal any embedded `manifest_fingerprint` field where present (path↔embed equality). This mirrors S3–S6 identity law.  
* **Partition law:** S7 outputs (see §5/§6 later) follow the 1B pattern `[seed, fingerprint, parameter_hash]`; logs are **not** introduced by S7 (deterministic; RNG-free). Upstream S5/S6 and their RNG logs retain their existing partition families (`[seed, parameter_hash, run_id]` for RNG).  
* **Immutability:** write-once per identity; publish via stage → fsync → **single atomic move**; file order non-authoritative. 

## 1.5 Audience & scope notes

**Audience:** implementation agents, validators, and reviewers. **This document binds behaviour** for S7 only; **shapes** remain exclusively defined by Schema anchors (S5/S6/S1 today; S7 anchor is defined in §6). **Order authority** stays outside 1B egress—downstreams join 1A `s3_candidate_set.candidate_rank` when order is required. 

---

# 2) Purpose & scope **(Binding)**

**Mission.** S7 **deterministically synthesises per-site records** by stitching **S5** (site→tile) with **S6** (effective in-pixel deltas) and required S1 geometry into a clean, conformed row per site—ready for S8 egress. It MUST ensure **1:1 coverage with `outlet_catalogue`**, **preserve `site_order`**, and **introduce no duplicates**. Inter-country order is **not encoded** in 1B; downstreams join 1A **S3 `candidate_rank`** when order is needed. 

## 2.1 In-scope (what S7 SHALL do)

* **Join & reconstruct (deterministic).** For every site key `(merchant_id, legal_country_iso, site_order)` in **S5**, join **S6** to get `(δ_lat, δ_lon)` and **S1** to get the tile centroid/bounds; reconstruct absolutes `(lon*,lat*) = centroid + δ`. (S7 is RNG-free.)  
* **Conformance checks.** Deterministically verify that `(lon*,lat*)` lies **inside the S1 pixel rectangle** for the site’s `tile_id`; S7 MAY also re-assert “point-in-country” as a deterministic check. 
* **1:1 with 1A outlet stubs.** Assert exact one-to-one coverage with **`outlet_catalogue`** and **preserve `site_order`**; S7 produces exactly one record per outlet stub. 
* **Prepare for egress.** Produce rows suitable for S8 **`site_locations`** (order-free) which publishes under partitions **`[seed, fingerprint]`**; S7 must not impose order beyond its writer sort. 

## 2.2 Out of scope (what S7 SHALL NOT do)

* **No reassignment or RNG.** SHALL NOT change S5 tile choices, re-sample, or consume RNG. 
* **No order encoding.** SHALL NOT encode or imply any **inter-country** order (authority remains 1A S3). 
* **No egress publish.** SHALL NOT publish or mutate S8 **`site_locations`** (that happens in S8 under `[seed, fingerprint]`). 

## 2.3 Success definition (pointer)

S7 is successful only if its acceptance suite (later §9) passes: **row parity with S5**, **1:1 coverage with `outlet_catalogue`**, **inside-pixel** reconstruction against S1, **path↔embed equality**, and **no order leakage**; and its output is **egress-ready** for S8’s partition law.  

---

# 3) Preconditions & sealed inputs **(Binding)**

## 3.1 Run identity is sealed before S7

S7 SHALL execute under a fixed lineage tuple **`{seed, manifest_fingerprint, parameter_hash, run_id}`**. Any embedded lineage fields in rows (e.g., `manifest_fingerprint`) MUST byte-equal their path tokens (`fingerprint=…`). This mirrors the 1B partition law used by S5/S6.  

## 3.2 Gate condition (must hold before any read)

**No PASS → No read.** The fingerprint-scoped 1A gate (verified in S0) MUST already be valid before S7 reads 1A egress (for the `outlet_catalogue` coverage check). This is the 1B overview’s standing consumer discipline. 

## 3.3 Sealed inputs required for this identity

S7 SHALL read **only** the following sealed surfaces for **this** `{seed, fingerprint, parameter_hash}` (or `{parameter_hash}` where noted). Shapes are governed by Schema; paths/partitions/writer policy by the Dictionary.

* **S5 — `s5_site_tile_assignment`** (authoritative site→tile keyset)
  Path family: `…/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  Partitions: `[seed, fingerprint, parameter_hash]` · Writer sort: `[merchant_id, legal_country_iso, site_order]` · Shape: `schemas.1B.yaml#/plan/s5_site_tile_assignment`.  

* **S6 — `s6_site_jitter`** (effective in-pixel deltas per site)
  Path family: `…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  Partitions: `[seed, fingerprint, parameter_hash]` · Writer sort: `[merchant_id, legal_country_iso, site_order]` · Shape: `schemas.1B.yaml#/plan/s6_site_jitter`.  

**S1 geometry — `tile_bounds`** (read-only)
  Used to reconstruct/check absolutes from S6 deltas and to assert “inside pixel.”
  Path family: `…/tile_bounds/parameter_hash={parameter_hash}/` · Partitions: `[parameter_hash]` · Writer sort: `[country_iso, tile_id]` · Shape: `schemas.1B.yaml#/prep/tile_bounds`.

* **1A `outlet_catalogue`** (read-only; coverage parity)
  S7 uses it to assert **1:1** coverage and preserved `site_order` (S7 does not encode inter-country order; consumers join 1A S3). Gate law from §3.2 applies. 

> **FK invariant (binding):** `(legal_country_iso, tile_id)` in S7’s joins MUST exist in the S1 geometry for the **same** `parameter_hash` (S5/S6 already bind this via their schema + Dictionary).  

## 3.4 Resolution rule (no literal paths)

Implementations SHALL resolve dataset/log **IDs → path families, partitions, writer policy** exclusively via the **Dataset Dictionary**. Hard-coded paths are non-conformant. 

## 3.5 Identity & partition posture (S7 outputs)

Any S7 output dataset (see §5/§6) MUST publish under `[seed, fingerprint, parameter_hash]` with writer sort `[merchant_id, legal_country_iso, site_order]`, and MUST satisfy path↔embed equality for lineage fields. This keeps S7 aligned with S5/S6 identity law.  

## 3.6 Fail-closed access

S7 SHALL read **only** the inputs enumerated in §3.3. Reading any unlisted spatial/time surface (e.g., policy files, priors) is a validation failure. S7 is RNG-free and introduces **no** new RNG logs; existing S5/S6 RNG logs remain read-only audit artefacts. 

*(With these preconditions set, §4 will bind the inputs & authority boundaries explicitly, and §7 will define the deterministic join/reconstruction steps.)*

---

# 4) Inputs & authority boundaries **(Binding)**

## 4.1 Authority stack (precedence)

* **Shape authority:** JSON-Schema owns all shapes. S7 uses the existing anchors for S5/S6/S1 and will add its own S7 anchor (see §6). If Dictionary prose and Schema disagree on shape, **Schema wins**. 
* **IDs → paths/partitions/writer policy:** resolve **only** via the **Dataset Dictionary**; no hard-coded paths. 
* **Provenance/notes & operational posture:** **Artefact Registry** (write-once; atomic move; file order non-authoritative). 

## 4.2 Bound inputs (sealed for this identity)

S7 SHALL read **only** these inputs for the fixed `{seed, fingerprint, parameter_hash}` (or `{parameter_hash}` where noted):

* **S5 — `s5_site_tile_assignment`** (site→tile keyset)
  Path family `…/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`; partitions `[seed, fingerprint, parameter_hash]`; writer sort `[merchant_id, legal_country_iso, site_order]`; schema `schemas.1B.yaml#/plan/s5_site_tile_assignment`. 

* **S6 — `s6_site_jitter`** (effective in-pixel deltas per site)
  Same path family & partitions as S5; writer sort `[merchant_id, legal_country_iso, site_order]`; schema `schemas.1B.yaml#/plan/s6_site_jitter`. 

* **S1 geometry — `tile_bounds`** (read-only, parameter-scoped)
  Path family `…/tile_bounds/parameter_hash={parameter_hash}/`; partitions `[parameter_hash]`; writer sort `[country_iso, tile_id]`; schema `schemas.1B.yaml#/prep/tile_bounds`.

* **1A egress — `outlet_catalogue`** (coverage parity check)
  Path family `…/seed={seed}/fingerprint={manifest_fingerprint}/`; partitions `[seed, fingerprint]`; order-free; **read only after verifying** the 1A validation bundle `_passed.flag`. 

> **FK invariant (binding):** any `(legal_country_iso, tile_id)` S7 touches MUST exist in S1 geometry for the **same** `parameter_hash` (S5/S6 already bind this). 

## 4.3 Order authority (what S7 must not encode)

**Inter-country order is solely 1A S3 `candidate_rank`.** S7 SHALL NOT encode cross-country order; downstreams obtain order by joining S3.  

## 4.4 Consumer gate (read discipline)

**No PASS → No read.** S7’s read of `outlet_catalogue` is permitted only when the fingerprint-scoped **1A validation bundle** has a valid `_passed.flag` per 1A’s hashing law. 

## 4.5 Partition/identity posture for S7 outputs (preview)

Any S7 dataset SHALL publish under `[seed, fingerprint, parameter_hash]` with writer sort `[merchant_id, legal_country_iso, site_order]`, mirroring S5/S6 identity law (see §5/§6 for S7’s own anchor). 

## 4.6 Prohibited surfaces (fail-closed)

S7 SHALL NOT read any surface outside §4.2 (e.g., priors, policies, or alternative geometries). RNG logs from S6 are audit-only; S7 introduces **no** new RNG events.  

---

# 5) Outputs (datasets/logs) & identity **(Binding)**

## 5.1 S7 dataset — `s7_site_synthesis`

**ID (Dictionary):** `s7_site_synthesis`
**Path family:**
`data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
**Partitions (binding):** `[seed, fingerprint, parameter_hash]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]` · **Format:** parquet · **Write-once; atomic move; file order non-authoritative**.
**Shape authority:** `schemas.1B.yaml#/plan/s7_site_synthesis` (PK `[merchant_id, legal_country_iso, site_order]`, columns_strict=true).
**Notes:** Aligns with S5/S6 partition/sort law.   

**Content (owned by Schema):** one row per site key from S5, carrying at least:

* `merchant_id, legal_country_iso, site_order, tile_id` (from S5);
* reconstructed **absolutes** `lon_deg, lat_deg` (WGS84 degrees) **as specified by the S7 anchor**; S6 remains the sole store of effective deltas;
* lineage fields as required by house style.
  (*Exact columns are defined by the S7 anchor; this spec does not restate them.*)

**Path↔embed equality (binding):** wherever `manifest_fingerprint` appears as a column, its value MUST byte-equal the `fingerprint=` path token. Mirrors S5/S6 law.  

## 5.2 Downstream reference — S8 egress `site_locations` (order-free)

**Target path family:**
`data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/`
**Partitions:** `[seed, fingerprint]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]` (file order non-authoritative).
S7 SHALL prepare rows that can be published under this identity without encoding inter-country order. 

## 5.3 Logs

S7 is deterministic and introduces **no RNG event streams**. Existing RNG logs from S5/S6 remain read-only audit artefacts under `[seed, parameter_hash, run_id]`. 

---

# 6) Dataset shapes & schema anchors **(Binding)**

**JSON-Schema is the sole shape authority.** S7 binds to the anchors below; implementations **MUST** validate against these anchors and **MUST NOT** restate columns outside Schema. Paths/partitions/writer policy resolve via the **Dataset Dictionary** only.

## 6.1 Output data table (S7 shape authority)

**ID → Schema:** `s7_site_synthesis` → `schemas.1B.yaml#/plan/s7_site_synthesis`.
**Identity:** partitions **`[seed, fingerprint, parameter_hash]`**; **PK** `[merchant_id, legal_country_iso, site_order]`; **writer sort** `[merchant_id, legal_country_iso, site_order]`; **columns_strict: true**.
**Dictionary path family:**  
`data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
*Rationale for identity/sort is parity with approved S5/S6 tables (same partitions and writer sort).* 

## 6.2 Referenced input anchors (read-only)

* **S5 assignment:** `schemas.1B.yaml#/plan/s5_site_tile_assignment`
  *(Dictionary binds path/partitions `[seed, fingerprint, parameter_hash]`, writer sort `[merchant_id, legal_country_iso, site_order]`.)* 
* **S6 jitter:** `schemas.1B.yaml#/plan/s6_site_jitter`
  *(Dictionary binds path/partitions `[seed, fingerprint, parameter_hash]`, writer sort `[merchant_id, legal_country_iso, site_order]`.)* 
* **S1 geometry:** `schemas.1B.yaml#/prep/tile_bounds`
  *(Dictionary binds parameter-scoped path/partitions `[parameter_hash]`; writer sort `[country_iso, tile_id]`.)*

## 6.3 Downstream egress anchor (reference only)

* **S8 egress:** `schemas.1B.yaml#/egress/site_locations`
  *(Dictionary binds path/partitions `[seed, fingerprint]`; order-free; writer sort `[merchant_id, legal_country_iso, site_order]`.)* 

## 6.4 Resolution & path law (Binding)

Dataset/log **IDs → path families / partitions / writer policy** resolve **exclusively** via the **Dataset Dictionary**; no hard-coded paths are permitted. 

---

# 7) Deterministic algorithm (RNG-free) **(Binding)**

## 7.1 Iteration order

S7 SHALL iterate the S5 keyset in **writer-sort** order:
`[merchant_id, legal_country_iso, site_order]`. 

## 7.2 Per-site join frame (exactly one)

For each site key `(merchant_id, legal_country_iso, site_order)`:

1. **Join S5 → S6 (1:1).** Inner-join `s5_site_tile_assignment` to `s6_site_jitter` on the site key; there MUST be **exactly one** S6 row per S5 row. (Both datasets are partitioned `[seed, fingerprint, parameter_hash]` and share the same writer sort.) 

2. **Join S1 geometry (by tile).** Join the pair to S1 **tile geometry** for the **same `parameter_hash`** using `(legal_country_iso, tile_id)` to fetch `centroid` and `bounds` for the pixel. (Use the parameter-scoped S1 surface: `tile_bounds`)  

## 7.3 Reconstruct absolutes (RNG-free)

Compute the realised coordinates from S6 **effective deltas** and the S1 centroid:

```
lon* = centroid_lon_deg + delta_lon_deg
lat* = centroid_lat_deg + delta_lat_deg
```

This reconstruction is deterministic and uses only sealed inputs. 

## 7.4 Deterministic conformance checks (per row)

S7 SHALL enforce, deterministically:

* **Inside-pixel:** `(lon*, lat*)` lies **inside** the S1 rectangle for `tile_id` (use S1 bounds; handle antimeridian exactly as S1). **FAIL** otherwise. 
* **S5↔S7 key parity:** one S7 row **per** S5 site key; no extras/dups. 
* **1A coverage (read-side parity):** the site key MUST join to `outlet_catalogue` for this `fingerprint`; `site_order` continuity preserved. (**No PASS → No read** of 1A per S0.)  

> S7 **MAY** re-assert *point-in-country* against the S1-governed country surface as an additional deterministic check; this does not alter identity or paths. 

## 7.5 Emit S7 row (write-once)

Write exactly one `s7_site_synthesis` row for the site with fields per the S7 schema anchor (PK `[merchant_id, legal_country_iso, site_order]`; partitions `[seed, fingerprint, parameter_hash]`; writer sort as in §7.1). Publish via stage → fsync → **single atomic move**; file order is non-authoritative. 

## 7.6 Identity & order discipline (run-wide)

* **Path↔embed equality:** where lineage is embedded (e.g., `manifest_fingerprint`), its value SHALL byte-equal the path token `fingerprint=…`. 
* **No inter-country order:** S7 SHALL NOT encode cross-country order; downstreams join 1A **S3 `candidate_rank`** if order is needed. 

---

# 8) Identity, partitions, ordering & merge discipline **(Binding)**

## 8.1 Identity tokens (one tuple per publish)

* **Dataset identity:** exactly one `{seed, manifest_fingerprint, parameter_hash}` for the entire S7 publish. Where lineage is embedded (e.g., `manifest_fingerprint`), its value **MUST** byte-equal the `fingerprint=` path token (path↔embed equality). This mirrors the 1B lineage law established at S0. 
* **No RNG logs introduced:** S7 is deterministic; existing S5/S6 RNG logs remain read-only audit artefacts under `[seed, parameter_hash, run_id]`. 

## 8.2 Partition law & path family (resolve via Dictionary; no literal paths)

* **S7 dataset:**
  Path family:
  `data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  **Partitions:** `[seed, fingerprint, parameter_hash]` · **Format:** parquet · **Writer sort:** `[merchant_id, legal_country_iso, site_order]`.
  *(Identity/sort mirror approved S5/S6 tables to keep 1B uniform.)*  

## 8.3 Path↔embed equality (lineage law)

Where lineage appears in both **path** and **rows**, values **MUST** be byte-identical (e.g., `fingerprint` path token equals embedded `manifest_fingerprint`). This naming/equality rule is part of the 1B gate contract and is binding here as well. 

## 8.4 Ordering posture (writer sort vs file order)

* **Binding writer sort:** S7 publishes in `[merchant_id, legal_country_iso, site_order]`. Merge/sink stages **MUST** respect the writer-sort; **file order is non-authoritative**. (Same posture as S5/S6.)  
* **No inter-country order encoded:** 1B egress is order-free; downstreams join **1A S3 `candidate_rank`** for any cross-country order (the egress dictionary text explicitly says “order-free; join S3”). S7 MUST NOT encode or imply it. 

## 8.5 Parallelism & stable merge (determinism)

Parallel materialisation (e.g., sharding by merchant or country) is **permitted** iff the final dataset is the result of a **stable merge** ordered by `[merchant_id, legal_country_iso, site_order]`, with outcomes independent of worker count/scheduling. (Matches S3/S6 discipline.)  

## 8.6 Atomic publish, immutability & idempotence

Publish via **stage → fsync → single atomic move** into the identity partition. Re-publishing the same `{seed, manifest_fingerprint, parameter_hash}` **MUST** be byte-identical or is a hard error. Registry notes codify **write-once; atomic move; file order non-authoritative**.  

## 8.7 Identity-coherence checks (must hold before publish)

* **Receipt parity (fingerprint):** any S7 publish for `fingerprint=f` implies the S0 gate receipt for `f` exists and is valid (“No PASS → No read” discipline). 
* **Parameter parity:** `parameter_hash` used in S7 equals the `parameter_hash` of the S1 geometry read (**`tile_bounds`** is parameter-scoped). 
* **Seed parity:** dataset `seed` equals the seed used by S5/S6 inputs (same identity tuple across 1B planning tables). 

## 8.8 Prohibitions (fail-closed)

* **MUST NOT** mix identities within a publish (no cross-seed/fingerprint/parameter_hash contamination). 
* **MUST NOT** rely on file order for semantics. Writer-sort governs; file order is non-authoritative. 
* **MUST NOT** encode or infer inter-country order (egress remains order-free; consumers join 1A S3). 

---

# 9) Acceptance criteria (validators) **(Binding)**

A run **PASSES** S7 only if **all** checks below succeed.

## A701 — Row parity S5 ↔ S7

**Rule.** `|S7| = |S5|` and keyset matches exactly on `[merchant_id, legal_country_iso, site_order]`; no extras/dups.
**Detection.** Two-way anti-join on the PK; enforce PK uniqueness in S7. 

## A702 — Schema conformance (S7)

**Rule.** Every S7 row validates against `schemas.1B.yaml#/plan/s7_site_synthesis` (columns_strict = true).
**Detection.** JSON-Schema validate all S7 files. *(Anchor added per §6.)*

## A703 — Partition & identity law

**Rule.** S7 lives at
`…/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` with partitions `[seed, fingerprint, parameter_hash]`; any embedded lineage (e.g., `manifest_fingerprint`) byte-equals path tokens (path↔embed equality).
**Detection.** Compare path-derived identity to embedded fields; verify Dictionary partitions. 

## A704 — Writer sort

**Rule.** Non-decreasing `[merchant_id, legal_country_iso, site_order]` within each identity partition; file order non-authoritative.
**Detection.** Scan per-file row order and merged partition order. 

## A705 — Reconstruct-equals-stored & inside-pixel

**Rule.** Using S1 geometry for the same `parameter_hash`, reconstruct
`lon* = centroid_lon_deg + delta_lon_deg`, `lat* = centroid_lat_deg + delta_lat_deg`, then require:
1) **Binary64 equality** (per S0 numeric policy) between `(lon*,lat*)` and stored `(lon_deg,lat_deg)`, **and**
2) `(lon*,lat*)` lies **inside** the S1 rectangle for `(legal_country_iso, tile_id)`.
**Detection.** Join S7→S1 **`tile_bounds`**; recompute `(lon*,lat*)` and assert **binary64 equality to `(lon_deg,lat_deg)`** and inclusive rectangle bounds (dateline semantics per S1).

## A706 — 1A coverage parity (read discipline)

**Rule.** For this `fingerprint`, every S7 site key joins **1:1** to `outlet_catalogue`; `site_order` continuity preserved. S7 reads 1A only if the 1A bundle for the same `fingerprint` **PASS**es; **No PASS → No read**.
**Detection.** Verify 1A `_passed.flag` by recomputing the ASCII-lex index hash, then join coverage. 

## A707 — Tile FK (same parameter set)

**Rule.** `(legal_country_iso, tile_id)` present in S1 geometry for the **same** `parameter_hash`.
**Detection.** FK join to **`tile_bounds`** (parameter-scoped).

## A708 — Order-authority pledge

**Rule.** S7 does **not** encode inter-country order; any ordering needs are satisfied downstream by joining 1A **S3 `candidate_rank`**.
**Detection.** Audit that S7 contains no order columns/implications beyond writer sort; cross-check Dictionary egress note. 

## A709 — Dictionary/Schema coherence

**Rule.** For all referenced IDs, Dictionary **paths/partitions/sort** match bound Schema anchors; no hard-coded paths.
**Detection.** Cross-check each `schema_ref` against its Dictionary entry. 

## A710 — Publish posture

**Rule.** Write-once; atomic move into the identity partition; file order non-authoritative.
**Detection.** Check atomic publish logs and Registry posture. 

---

# 10) Failure modes & canonical error codes **(Binding)**

### E701_ROW_MISSING — Missing S7 row for an S5 site *(ABORT)*

**Trigger:** A `(merchant_id, legal_country_iso, site_order)` present in **S5** has **no** matching row in **S7**.
**Detection:** Anti-join `S5 \ S7` on the PK is empty; S5 keyset is authoritative. 

### E702_ROW_EXTRA — Extra S7 row *(ABORT)*

**Trigger:** A site key exists in **S7** that is **not** in **S5**.
**Detection:** Anti-join `S7 \ S5` on the PK is empty. 

### E703_DUP_KEY — Duplicate primary key in S7 *(ABORT)*

**Trigger:** Duplicate `(merchant_id, legal_country_iso, site_order)` within the S7 partition.
**Detection:** Enforce PK uniqueness per the S7 anchor (columns_strict=true) and writer-sort posture. 

### E704_SCHEMA_VIOLATION — S7 row fails schema *(ABORT)*

**Trigger:** Any S7 row does **not** validate the `schemas.1B.yaml#/plan/s7_site_synthesis` anchor.
**Detection:** JSON-Schema validation fails; unknown/missing columns or invalid types detected. 

### E705_PARTITION_OR_IDENTITY — Partition/path or path↔embed mismatch *(ABORT)*

**Trigger:** Any of:

* S7 not under `…/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`, or
* embedded lineage (e.g., `manifest_fingerprint`) ≠ path tokens.
  **Detection:** Compare path-derived `{seed,fingerprint,parameter_hash}` to embedded fields; verify Dictionary partitions. 

### E706_WRITER_SORT_VIOLATION — Writer sort not respected *(ABORT)*

**Trigger:** Records in S7 are not in non-decreasing `[merchant_id, legal_country_iso, site_order]`.
**Detection:** Validate stable-merge order; file order is non-authoritative. 

### E707_POINT_OUTSIDE_PIXEL — Reconstructed point outside S1 pixel *(ABORT)*

**Trigger:** `lon* = centroid_lon_deg + delta_lon_deg`, `lat* = centroid_lat_deg + delta_lat_deg` fall **outside** S1 bounds for `(legal_country_iso, tile_id)`.
**Detection:** Join to S1 geometry (**`tile_bounds`**) for the same `parameter_hash`; assert inclusive rectangle bounds (S1 semantics).  

### E708_1A_COVERAGE_FAIL — 1:1 coverage with `outlet_catalogue` not satisfied *(ABORT)*

**Trigger:** For this `fingerprint`, any S7 site key fails to join **1:1** to `outlet_catalogue`, or the 1A consumer gate is not honoured.
**Detection:** Verify 1A `_passed.flag` (ASCII-lex index → SHA-256) then assert 1:1 join coverage. **No PASS → No read.** 

### E709_TILE_FK_VIOLATION — `(country,tile_id)` not in S1 geometry *(ABORT)*

**Trigger:** `(legal_country_iso, tile_id)` in S7 does **not** exist in S1 **`tile_bounds`** for the **same** `parameter_hash`.
**Detection:** FK join to the parameter-scoped S1 surface (**`tile_bounds`**) fails.

### E710_ORDER_LEAK — Inter-country order encoded *(ABORT)*

**Trigger:** S7 encodes or implies cross-country order (columns or semantics beyond writer-sort).
**Detection:** Audit S7 columns/notes; 1B **never** encodes inter-country order—downstreams join 1A **S3 `candidate_rank`**.  

### E711_DICT_SCHEMA_MISMATCH — Dictionary vs Schema disagreement *(ABORT)*

**Trigger:** Any referenced ID’s **path/partitions/sort** per Dictionary disagree with bound Schema anchors (or vice-versa), or literal paths used.
**Detection:** Cross-check each `schema_ref` against its Dictionary entry; resolve IDs via Dictionary only. 

### E712_ATOMIC_PUBLISH_VIOLATION — Not write-once / non-atomic publish *(ABORT)*

**Trigger:** Re-publishing the same `{seed, manifest_fingerprint, parameter_hash}` is not byte-identical, or publish skipped the **stage → fsync → single atomic move** discipline.
**Detection:** Check publish logs and registry posture: **write-once; atomic move; file order non-authoritative**. 

---

# 11) Observability & run-report **(Binding)**

## 11.1 Required run-level counters S7 SHALL compute

Produce a single run-scoped summary (JSON object) with at least:

**Identity**

```
{ "seed": u64, "parameter_hash": "<hex64>", "manifest_fingerprint": "<hex64>", "run_id": "<opaque>" }
```

**Parity & sizes**

* `sites_total_s5` = |S5 `s5_site_tile_assignment`| for this `{seed,fingerprint,parameter_hash}`. 
* `sites_total_s6` = |S6 `s6_site_jitter`| for this identity. 
* `sites_total_s7` = |S7 `s7_site_synthesis`| (this output).
* `parity_s5_s7_ok` (bool) — exact keyset equality on `[merchant_id, legal_country_iso, site_order]`.
* `parity_s5_s6_ok` (bool) — optional aid for triage; not an acceptance gate of S7.

**Validation counters**

* `fk_tile_ok_count`, `fk_tile_fail_count` — `(legal_country_iso,tile_id)` present in S1 geometry for **same** `parameter_hash`. 
* `inside_pixel_ok_count`, `inside_pixel_fail_count` — reconstruction within S1 rectangle. 
* `path_embed_mismatches` — any lineage field ≠ path token (`fingerprint` ↔ `manifest_fingerprint`). 
* `coverage_1a_ok_count`, `coverage_1a_miss_count` — 1:1 join to 1A `outlet_catalogue` **after** gate verification. 

**By-country rollup (diagnostic)**

```
by_country[ISO]: {
  sites_s7, fk_tile_fail, outside_pixel, coverage_1a_miss
}
```

## 11.2 Gate posture (read discipline)

If S7 reads 1A `outlet_catalogue` for coverage checks, it **MUST** first verify the fingerprint-scoped **1A validation bundle**: recompute SHA-256 over files listed in `index.json` (ASCII-lex by `path`, flag excluded) and compare to `_passed.flag`. **No PASS → No read.** Record the verified `flag_sha256_hex` in the run summary.  

## 11.3 Sources S7 SHALL use for the summary

* **S5** `s5_site_tile_assignment` — partitions `[seed,fingerprint,parameter_hash]`; writer sort `[merchant_id, legal_country_iso, site_order]`. 
* **S6** `s6_site_jitter` — same partitions/sort. 
* **S1** geometry (**`tile_bounds`**) — parameter-scoped `[parameter_hash]`; sort `[country_iso, tile_id]`. 
* **1A** `outlet_catalogue` (read only after PASS) — partitions `[seed,fingerprint]`; order-free. 

## 11.4 Emission & packaging posture

* S7 **does not** introduce RNG logs. The run summary is **non-identity-bearing** and MAY be persisted as a small JSON sidecar or forwarded to the downstream packaging state for inclusion in the 1B bundle. (Write-once/atomic-move posture for datasets applies; file order remains non-authoritative.)  

## 11.5 Minimal JSON shape (binding keys)

S7 SHALL expose a JSON object with at least these keys (values as defined above):

```json
{
  "identity": { "seed": 0, "parameter_hash": "", "manifest_fingerprint": "", "run_id": "" },
  "sizes": { "sites_total_s5": 0, "sites_total_s6": 0, "sites_total_s7": 0,
             "parity_s5_s7_ok": false, "parity_s5_s6_ok": false },
  "validation_counters": {
    "fk_tile_ok_count": 0, "fk_tile_fail_count": 0,
    "inside_pixel_ok_count": 0, "inside_pixel_fail_count": 0,
    "coverage_1a_ok_count": 0, "coverage_1a_miss_count": 0,
    "path_embed_mismatches": 0
  },
  "by_country": { "GB": { "sites_s7": 0, "fk_tile_fail": 0, "outside_pixel": 0, "coverage_1a_miss": 0 } },
  "gates": { "outlet_catalogue_pass_flag_sha256": "" }
}
```

## 11.6 Retention & immutability

* **S7 dataset** (when added): follow the S5/S6 posture — **write-once; atomic move; file order non-authoritative; retention 365d** (Dictionary governs exact retention). 
* **Inputs referenced** (S5/S6/S1) retain their Dictionary retentions (S5/S6: datasets 365d; S6 RNG events 30d — audit only; not used by S7).  

## 11.7 Optional diagnostics (non-authoritative)

* Determinism receipt for S7 partition: `{partition_path, sha256_hex}` over concatenated file bytes in ASCII-lex path order (mirrors existing practice in earlier states). 

---

# 12) Performance & scalability *(Informative)*

**Goal:** make S7 fast and replayable at scale while honoring the binding contracts (Schema shapes; Dictionary paths/partitions/writer-sort; Registry’s write-once/atomic-move posture).  

## 12.1 Parallelism & stable merge

* **Shard safely.** Split work by **country** or by **merchant buckets**; each worker processes a disjoint slice of the S5 keyset. Finalise with a **stable merge** in the binding writer-sort `[merchant_id, legal_country_iso, site_order]`. (S5/S6 already use this sort and partitions `[seed, fingerprint, parameter_hash]`, so shards are naturally well-defined.) 
* **Determinism under concurrency.** Never rely on file order; only the writer-sort governs semantics. Publish once per identity via atomic move. 

## 12.2 Join strategy (S5 ↔ S6 ↔ S1)

* **Sorted streams.** S5 and S6 share the same partitions and writer-sort, enabling **streaming inner-joins** on the site PK without global shuffles. 
* **Parameter-scoped geometry.** Cache S1 geometry (**`tile_bounds`**) **per `parameter_hash`** as a keyed map `(country_iso, tile_id) → {centroid, bounds}` to avoid repeated parquet scans.
* **Border-only checks (optional micro-optimisation).** If you maintain a “border-tile bitset” from S1, you can skip repeat rectangle checks for tiles known to be interior; S7 still revalidates *inside-pixel* cheaply.

## 12.3 Geometry & numerics

* **Rectangle math.** Reconstruct `(lon*,lat*) = centroid + δ` and test against S1 **bounds**; use the same antimeridian handling as S1 to keep checks O(1). 
* **Numeric profile.** Keep the layer’s deterministic numeric posture (RNE; no FTZ/DAZ; no FMA) used upstream so replays regenerate identical results when S8 later reconstructs absolutes.

## 12.4 I/O layout & throughput

* **Row groups aligned to sort.** Write parquet in **writer-sort** with balanced row groups (tens of MB) to improve downstream range scans over `[merchant_id, legal_country_iso, site_order]`. (Identity partitions for S7 mirror S5/S6: `[seed, fingerprint, parameter_hash]`.) 
* **Single-pass materialisation.** Do S5↔S6 join, S1 lookup, reconstruction, and validation **in one pass**; emit directly to a **staging** location under the final identity path family and perform a **single atomic move** at the end. 

## 12.5 Memory model & batching

* **Country batching.** Process by country to keep the S1 geometry cache hot (keys are `(country_iso, tile_id)`); this also localises any error spikes for triage. 
* **Streaming joins.** Prefer iterator-style joins over PK with small look-ahead buffers; S7 is RNG-free, so CPU is dominated by joins and rectangle checks.

## 12.6 Observability hooks (cheap, useful)

* **Run summary.** Emit the S7 run-summary counters from §11 (parity, inside-pixel, FK counts, 1A coverage). These are computed from S5/S6/S1 and 1A egress (after PASS), so no extra heavy scans are needed. 
* **Cross-state breadcrumbs.** For triage, you can reference S6’s RNG audit/trace logs when present (events are per attempt; logs live under `[seed, parameter_hash, run_id]`)—read-only and outside S7’s hot path. 

## 12.7 Failure-aware scheduling

* **Short-circuit on invariant breaks.** If the S5↔S6 join is not 1:1 or a tile FK fails against S1 for the current `parameter_hash`, abort the shard early; these are acceptance gates later anyway. 
* **Gate discipline up front.** Verify the 1A PASS receipt once per `fingerprint` before any 1A read (coverage parity stage), then reuse the result across shards. (S7 mirrors the layer’s **No PASS → No read** discipline.) 

## 12.8 Idempotence & publish

* **Write-once, atomic.** Stage outputs under the exact identity path, fsync, then **single atomic move**. Re-publishing the same `{seed, manifest_fingerprint, parameter_hash}` must be byte-identical. File order remains non-authoritative. 

## 12.9 What S7 deliberately does **not** do

* **No RNG emission.** S7 introduces **no** RNG event streams (all RNG evidence sits in S6), keeping the hot path purely deterministic. 
* **No egress publish.** S7 prepares rows only; S8 writes `site_locations` under `[seed, fingerprint]` and remains order-free (downstreams join 1A S3 for inter-country order). 

This guidance keeps S7 fast, deterministic, and consistent with the **Dictionary partitions & writer-sort**, the **Registry’s write-once/atomic-move** posture, and upstream S5/S6 contract surfaces.  

---

# 13) Change control & compatibility **(Binding)**

## 13.1 Versioning model (SemVer)

S7 uses **MAJOR.MINOR.PATCH**. Artefacts are **write-once; atomic move; file order non-authoritative**. 

## 13.2 What counts as **MAJOR** (non-exhaustive)

Changes that can invalidate previously valid runs or alter identity/shape/gates:

1. **Identity / path law**

   * Changing S7 partitions from **`[seed, fingerprint, parameter_hash]`** or its path family.
   * Changing writer sort from **`[merchant_id, legal_country_iso, site_order]`**. 

2. **Schema-owned shape**

   * Any change to the S7 table anchor (`schemas.1B.yaml#/plan/s7_site_synthesis`) that adds/removes/renames columns or relaxes **columns_strict**. *(Anchor per §6; S5/S6 anchors illustrate the posture.)*

3. **Behavioural gates**

   * Modifying S7 acceptance in a way that would fail prior valid outputs (e.g., relaxing *inside-pixel* into advisory only; removing S5↔S7 parity).
   * Altering the 1A consumer gate posture (**No PASS → No read**) required before using `outlet_catalogue`. 

4. **Authority surfaces / semantics**

   * Replacing or re-scoping S1 geometry surfaces used here (e.g., `tile_bounds` partitioned by **`[parameter_hash]`**). 

5. **Order authority**

   * Encoding any inter-country order in S7; order remains downstream via 1A **S3 `candidate_rank`**. Changing this pledge is MAJOR. 

6. **Downstream egress law**

   * Changing S8 `site_locations` partitions from **`[seed, fingerprint]`** would require S7 re-ratification (S7 prepares rows for that law). 

## 13.3 What may be **MINOR** (backward-compatible only)

* Adding **non-identity** diagnostics or fields to the S7 **run-summary** (not to the dataset anchor).
* Tightening **non-gating** validator messages or adding advisory counters.
* Registry/Dictionary **notes** that don’t alter schema, partitions, writer-sort, or acceptance. 

## 13.4 What is **PATCH**

Editorial fixes: typos, cross-references, clarifications that do **not** change behaviour, shapes, paths/partitions, writer-sort, or acceptance outcomes.

## 13.5 Compatibility baselines (this spec line)

S7 assumes the following are in effect:

* **Dictionary (1B):**
  – `s5_site_tile_assignment` and `s6_site_jitter` → partitions **`[seed, fingerprint, parameter_hash]`**, writer sort **`[merchant_id, legal_country_iso, site_order]`**. 
  – `tile_bounds` → partitions **`[parameter_hash]`**, sort **`[country_iso, tile_id]`**. 
  – **Egress** `site_locations` → partitions **`[seed, fingerprint]`**; order-free.
* **Registry (1B):** write-once, atomic-move posture for 1B datasets/logs (mirrors S5/S6 entries). 

A **MAJOR** change to any baseline that affects S7’s bound interfaces requires an S7 **MAJOR** (or an explicit compatibility shim).

## 13.6 Forward-compatibility guidance

* If S8’s egress law changes (e.g., partitions), introduce an S8 **MAJOR** and version S7 with at least a **MINOR** to adjust references; avoid silently rewiring IDs. 
* If S1 geometry keys/partitions change, re-ratify S7 with at least a **MINOR** (likely **MAJOR** if acceptance changes).

## 13.7 Deprecation & migration (binding posture)

* **Dual-lane window:** When replacing the S7 dataset, run old and new lanes for **≥1 MINOR** with validators accepting either lane (IDs remain distinct).
* **Removal:** Removing a superseded lane is **MAJOR** and MUST be called out in the S7 header with a migration note.

## 13.8 Cross-state compatibility

* **Upstream handshake:** S7 requires S5/S6 shapes and partitions as above; a MAJOR in S5/S6 that alters keys/partitions requires S7 re-ratification. 
* **Downstream neutrality:** S7 does **not** publish egress or RNG logs; S8 packages `site_locations` under `[seed, fingerprint]`. 

---

# Appendix A — Symbols *(Informative)*

## A.1 Keysets & primary keys

* **S5_keys** — exact site keyset produced by S5:
  `S5_keys = {(merchant_id, legal_country_iso, site_order)}`. S5/S6 partition and sort on this key. 
* **S7_keys** — S7 emits **one** row per element of `S5_keys` (same PK). *(Anchor added per §6.)*
* **Join keys** — S7 joins S5↔S6 on the site PK; joins to S1 geometry by `(legal_country_iso, tile_id)` with the **same `parameter_hash`**.  

## A.2 Identity & lineage tokens

* **seed** — 64-bit unsigned; partitions S5/S6 (and S7). 
* **parameter_hash** — hex64 identifying the sealed parameter bundle; partitions S1 geometry and S5/S6 (and S7).  
* **manifest_fingerprint** — hex64 fingerprint of the run manifest; path token is `fingerprint={manifest_fingerprint}`. S5/S6 (and S7) use it in partitions; egress uses `[seed, fingerprint]`.  

## A.3 Dataset IDs → path families & partitions (Dictionary law)

* **S5 — `s5_site_tile_assignment`**
  `data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  Partitions `[seed, fingerprint, parameter_hash]` · Writer sort `[merchant_id, legal_country_iso, site_order]`. 
* **S6 — `s6_site_jitter`**
  `data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  Partitions `[seed, fingerprint, parameter_hash]` · Writer sort `[merchant_id, legal_country_iso, site_order]`. 
* **S7 — `s7_site_synthesis`**
  `data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  Partitions `[seed, fingerprint, parameter_hash]` · Writer sort `[merchant_id, legal_country_iso, site_order]`. *(Matches S5/S6.)*
* **S1 geometry — `tile_bounds`**
  `…/parameter_hash={parameter_hash}/` · Partitions `[parameter_hash]` · Sort `[country_iso, tile_id]`. 
* **S8 egress — `site_locations`**
  `data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/`
  Partitions `[seed, fingerprint]` · Order-free; consumers join 1A S3 for inter-country order. 

*(All datasets are write-once; publish via single atomic move; file order non-authoritative — Registry posture.)* 

## A.4 Geometry & placement (WGS84 / degrees)

For a site assigned to `(legal_country_iso, tile_id)`:

* **S1 rectangle** — `[min_lon, max_lon] × [min_lat, max_lat]` from S1 geometry; **centroid** `(centroid_lon_deg, centroid_lat_deg)`. 
* **Effective deltas (from S6)** — `δ_lon_deg`, `δ_lat_deg`. S6 stores effective, in-pixel deltas per site. 
* **Reconstruction** — realised absolutes used by S7 checks:
  `lon* = centroid_lon_deg + δ_lon_deg` · `lat* = centroid_lat_deg + δ_lat_deg`.
  Inside-pixel check uses S1 bounds (dateline handling per S1). 

## A.5 Foreign keys & order authority

* **Tile FK (parameter-scoped)** — `(legal_country_iso, tile_id)` **FK→** S1 **`tile_bounds`** for the **same `parameter_hash`**. (Schema encodes this style in 1B plan tables with an explicit `partition_keys: [parameter_hash]` hint.) 
* **Order authority** — 1B **never** encodes inter-country order; downstreams join 1A S3 `candidate_rank`. Egress `site_locations` is order-free. 

## A.6 Writer sort & file-order posture

* **Writer sort** — `[merchant_id, legal_country_iso, site_order]` for S5/S6 (and S7). File order is **non-authoritative**; stable merge under writer sort governs.  

## A.7 Abbreviations

* **PK** — Primary key (within an identity partition).
* **FK** — Foreign key.
* **RNG** — Random number generation (S7 is RNG-free; S6 holds RNG evidence). 
* **U(0,1)** — continuous uniform on the open interval (used upstream in S6). 

## A.8 Identity equality (path↔embed)

Where lineage appears both as **path tokens** and **embedded columns** (e.g., `manifest_fingerprint`), values MUST byte-equal; the path token is always `fingerprint=…`. (Applied throughout 1B planning tables and egress.)  

---

# Appendix B — Worked example *(Informative)*

## B.1 Identity (fixed for the run)

```
seed                 = 4242424242
parameter_hash       = "c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00"   # hex64
manifest_fingerprint = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"   # hex64
run_id               = "6f4d2c3b9e0a11d2acbd4e5f6a1b2c3d"
```

**Relevant path families (from Dictionary; S7 mirrors S5/S6’s identity/sort):**

* S5: `…/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` · partitions `[seed,fingerprint,parameter_hash]` · writer sort `[merchant_id, legal_country_iso, site_order]`. 
* S6: `…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` · same partitions/sort. 
* S1 geometry (parameter-scoped): `…/tile_bounds/parameter_hash={parameter_hash}/` · partitions `[parameter_hash]`. 
* Egress reference (for S8): `…/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/` · partitions `[seed,fingerprint]`. 

---

## B.2 Inputs (one site)

**S5 site key** *(writer-sort PK)*:
`(merchant_id=1234567890123, legal_country_iso="GB", site_order=17, tile_id=240104)`

**S6 deltas for that site** *(effective in-pixel)*:

```
delta_lon_deg = +0.01162105
delta_lat_deg = -0.01977055
```

*(S6 table lives under `[seed,fingerprint,parameter_hash]` with the same PK and writer-sort.)* 

**S1 geometry for (GB, tile_id=240104)** *(parameter-scoped)*:

```
bounds:
  min_lon = -0.250000
  max_lon = -0.200000
  min_lat =  51.500000
  max_lat =  51.550000
centroid:
  centroid_lon_deg = -0.225000
  centroid_lat_deg =  51.525000
```

*(Tile geometry path/partitions: `…/tile_bounds/parameter_hash={parameter_hash}/`, sort `[country_iso,tile_id]`.)* 

---

## B.3 Stitch & reconstruct (RNG-free)

Use S6 effective deltas with S1 centroid:

```
lon* = -0.225000 + 0.01162105 = -0.21337895
lat* =  51.525000 - 0.01977055 =  51.50522945
```

**Inside-pixel check (S1 rectangle, inclusive):**
`-0.250000 ≤ -0.21337895 ≤ -0.200000` and `51.500000 ≤ 51.50522945 ≤ 51.550000` → **PASS**.
*(S7 enforces “inside pixel” deterministically using S1 bounds.)* 

**1A coverage parity gate:** before joining `outlet_catalogue` for coverage, verify the **1A validation bundle** for this `fingerprint` (ASCII-lex index → SHA-256 equals `_passed.flag`). **No PASS → No read.** 

---

## B.4 S7 output (illustrative row)*

*(Exact columns owned by the S7 anchor; partitions & writer-sort mirror S5/S6.)*

**Partition path:**
`data/layer1/1B/s7_site_synthesis/seed=4242424242/fingerprint=deadbeef…/parameter_hash=c0ffee…/part-0000.snappy.parquet`

**Row (CSV-style rendering):**

| merchant_id   | legal_country_iso | site_order | tile_id |     lon_deg |     lat_deg | manifest_fingerprint |
|---------------|-------------------|-----------:|--------:|------------:|------------:|----------------------|
| 1234567890123 | GB                |         17 |  240104 | -0.21337895 | 51.50522945 | deadbeefdeadbeef…    |

* **Writer sort respected:** `[merchant_id, legal_country_iso, site_order]`. 
* **Path↔embed equality:** embedded `manifest_fingerprint` == path token `fingerprint=…`. *(Same lineage law used across 1B planning tables.)* 

*S7 stores **absolutes** `lon_deg, lat_deg`. Validators reconstruct `(lon*,lat*)` as above and require equality to the stored fields (A705); identity/partitions/sort are unchanged.

---

## B.5 Validator perspective (S7 §9 mapping)

* **A701 Row parity S5↔S7:** the key `(1234567890123,GB,17)` appears exactly once in S7; anti-joins empty.
* **A702 Schema conformance:** row validates `#/plan/s7_site_synthesis` (columns_strict).
* **A703 Partition & identity law:** path partitions `[seed,fingerprint,parameter_hash]`; embedded lineage equals path tokens. 
* **A704 Writer sort:** non-decreasing by `[merchant_id, legal_country_iso, site_order]`. 
* **A705 Reconstruct-equals-stored & inside-pixel:** recompute `lon* = centroid_lon_deg + delta_lon_deg`, `lat* = centroid_lat_deg + delta_lat_deg`, assert **binary64 equality** to stored `(lon_deg,lat_deg)` **and** inside the S1 rectangle for `(GB,240104)` at this `parameter_hash`. 
* **A706 1A coverage parity:** after PASS check, 1:1 join to `outlet_catalogue` for this `fingerprint`. 
* **A707 Tile FK (same parameter):** `(GB,240104)` exists in S1 geometry at this `parameter_hash`. 
* **A708 Order pledge:** S7 contains no inter-country order; egress remains order-free; downstreams join 1A S3 when needed. 

---

## B.6 Negative case (outside-pixel) — what **FAIL** looks like

Suppose a bad row had `lon_deg = -0.255` (west of `min_lon`).

* **A705 Reconstruct-equals-stored & inside-pixel:** **FAIL** → **E707_POINT_OUTSIDE_PIXEL**.
* Other parity/sort/identity checks may still pass, but the run **ABORTS** on this gate.

---

## B.7 Run-summary snippet (what S7 exposes to S8)

```json
{
  "identity": {
    "seed": 4242424242,
    "parameter_hash": "c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00",
    "manifest_fingerprint": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    "run_id": "6f4d2c3b9e0a11d2acbd4e5f6a1b2c3d"
  },
  "sizes": { "sites_total_s5": 1, "sites_total_s6": 1, "sites_total_s7": 1,
             "parity_s5_s7_ok": true, "parity_s5_s6_ok": true },
  "validation_counters": {
    "fk_tile_ok_count": 1, "fk_tile_fail_count": 0,
    "inside_pixel_ok_count": 1, "inside_pixel_fail_count": 0,
    "coverage_1a_ok_count": 1, "coverage_1a_miss_count": 0,
    "path_embed_mismatches": 0
  }
}
```

*(Counters derive from S5/S6 under `[seed,fingerprint,parameter_hash]`, S1 geometry under `[parameter_hash]`, and 1A egress **after** the PASS check.)*   

---

**Where to look up each contract in your artefacts:**

* S5/S6 partitions & writer-sort (mirror for S7): Dictionary. 
* S1 geometry partitions (parameter-scoped): Dictionary. 
* Egress `site_locations` is `[seed,fingerprint]` and order-free: Dictionary. 
* 1A consumer gate (“**No PASS → No read**” recipe): S1 expanded doc (normative when later states read 1A). 

This example shows the deterministic S7 stitch, identity/partition discipline, and how the acceptance suite is satisfied end-to-end.

---