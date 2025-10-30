# State-5 · Site → Tile Assignment (RNG)

# 1) Purpose & scope **(Binding)**

**1.1 Problem statement.**
S5 assigns each outlet stub `(merchant_id, legal_country_iso, site_order)` to an **eligible `tile_id`** such that, for every `(merchant_id, legal_country_iso)`, the **count of assigned sites per tile equals** the S4 integer quota `n_sites_tile`. S5 introduces **randomisation in the *selection of which specific sites*** fill each tile’s quota, but it **does not change any counts** (S4’s per-tile integers are authoritative). S5 is part of the same run identity **`{seed, manifest_fingerprint, parameter_hash}`**.

**1.2 Out of scope.**
S5 **does not**: (a) alter S4 quotas or re-normalise weights; (b) generate lat/lon, jitter, or any coordinate output; (c) encode or imply **inter-country order** (order authority remains **1A `s3_candidate_set`**); (d) read any surfaces beyond those enumerated for S5.

**1.3 Authority boundaries & invariants.**
a) **Counts to satisfy (S4):** S4’s `s4_alloc_plan` is the sole authority for per-tile integers; S5 **must not** modify them.
b) **Tile universe (S1):** Only tiles present in `tile_index` for the fixed `{parameter_hash}` are eligible; **no extras**.
c) **Gate law (S0):** S5 **relies on** the fingerprint-scoped receipt established in S0 (**No PASS → No read**); S5 **does not** re-hash the 1A bundle.
d) **Identity:** All reads and writes in S5 bind to exactly **one** `{seed, manifest_fingerprint, parameter_hash}`; mixing identities within a publish is **forbidden**.
e) **Resolution & shape:** All IO **must** resolve via the **Dataset Dictionary** (no literal paths). **JSON-Schema** remains the **sole shape authority** for datasets and RNG events; this spec does not restate columns/keys.

**1.4 Deliverables.**
S5 emits two artefacts for the run identity `{seed, manifest_fingerprint, parameter_hash}`:
a) **Dataset:** a site→tile assignment table with exactly **one row per site** (positives only), writer-sorted, immutable, and byte-stable on re-publish.
b) **RNG event logs:** a stream under the layer RNG envelope capturing the **assignment draws** (budgeted and validated in S5) to demonstrate that the randomisation is correctly scoped and reproducible.

---

# 2) Preconditions & sealed inputs **(Binding)**

**2.1 Gate (must hold before any read).**
Exactly one **`s0_gate_receipt_1B`** exists under `fingerprint={manifest_fingerprint}` for this run and **schema-validates**. S5 **relies on the receipt** (No PASS → No read) and **does not** re-hash the 1A bundle.

**2.2 Fixed identities (for the entire publish).**
All S5 reads and writes bind to exactly one **`{seed, manifest_fingerprint, parameter_hash}`**. Mixing identities within a publish is **forbidden**.

**2.3 Sealed inputs (resolve via Dataset Dictionary; no literal paths).**

* **`s4_alloc_plan`** — path family: `…/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` · partitions: `[seed, fingerprint, parameter_hash]` · *authority for per-tile integers `n_sites_tile` (positives only).*
* **`tile_index`** — path family: `…/tile_index/parameter_hash={parameter_hash}/` · partitions: `[parameter_hash]` · *eligible tile universe.*
* **`iso3166_canonical_2024`** — ingress FK surface for `legal_country_iso`.
* *(Optional, diagnostics only)* **`s3_requirements`** — same identity as S4; may be read only to echo pair-level sums (not required for assignment).

**2.4 Inputs S5 will actually read.**
` s4_alloc_plan`, `tile_index`, `iso3166_canonical_2024`. *(No other surfaces are read by S5 logic.)*

**2.5 RNG envelope (pre-run commitments).**

* **Substream:** `site_tile_assign` (assignment draws).
* **Budget:** **exactly one** U(0,1) draw **per assigned site** (i.e., per output row in `s5_site_tile_assignment`).
* **Partitioning for logs:** `logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.
* **Run ID:** a single `run_id` is minted at job start and used for all S5 RNG events in this publish; it is recorded in the run report.
* **Shape authority:** the RNG events **must** validate against the canonical layer RNG event anchor for `site_tile_assign`. *(This spec does not restate event fields.)*

**2.6 Path↔embed & identity parity (must be true before publish).**

* The `{seed}` used to read `s4_alloc_plan` **equals** the dataset publish token.
* The `{parameter_hash}` used to read `tile_index` **equals** the dataset publish token.
* Where lineage fields are embedded in rows in any future revision, embedded values **equal** their path tokens.
* RNG logs’ `{seed, parameter_hash}` tokens **match** the dataset’s identity; a single `run_id` is used consistently.

**2.7 Prohibitions (fail-closed).**

* **No out-of-scope reads:** S5 must not read `world_countries`, `population_raster_2025`, `tz_world_2025a`, or any surface not listed in §2.4.
* **No count/weight tampering:** S5 must not modify S4 `n_sites_tile`, renormalise weights, or introduce any alternative quota logic.
* **No order encoding:** inter-country order remains solely with **1A `s3_candidate_set`** and is not encoded or implied here.

---

# 3) Inputs & authority boundaries **(Binding)**

**3.1 Required datasets (resolve via Dataset Dictionary; Schema owns shape).**

* **`s4_alloc_plan`** — authoritative **per-tile integers** `n_sites_tile` for each `(merchant_id, legal_country_iso, tile_id)` under `{seed, manifest_fingerprint, parameter_hash}`.
* **`tile_index`** — **eligible tile universe** for the fixed `{parameter_hash}`; only tiles present here may receive assignments.
* **`iso3166_canonical_2024`** — **FK domain** for `legal_country_iso` (uppercase ISO-2).

**3.2 Sealed but **not** read by S5 (declared for boundary clarity).**

* **`s3_requirements`** — per-pair totals (may be used for diagnostics; **not** required for assignment logic).
* **`outlet_catalogue`** — site stubs (seed+fingerprint); S5 **does not** read it and may reconstruct the **site_order list** as `1..n_sites` per pair (contiguity is guaranteed upstream).
* **`s3_candidate_set`** — sole **inter-country order** authority (1A); **not** read by S5.
* **`tile_weights`** — fixed-dp fractional mass (S2); **not** read by S5 (counts already integerised in S4).

**3.3 Resolution & precedence rules.**

* **Shape authority:** JSON-Schema pack (columns, domains, PK/partition/sort) for both the dataset and RNG event anchors.
* **IDs → paths/partitions/sort/licence:** Dataset Dictionary.
* **Provenance/licences:** Artefact Registry.
  If Dictionary text ever diverges from Schema on **shape**, **Schema wins**. **No literal paths** in code; all IO resolves by Dictionary.

**3.4 Authority boundaries (what S5 MUST / MUST NOT do).**

* **Counts to satisfy:** S5 **MUST** satisfy S4 `n_sites_tile` exactly; **MUST NOT** re-scale, re-optimise, or otherwise alter counts.
* **Universe constraint:** Assign **only** to tiles present in `tile_index` for the same `{parameter_hash}`; tiles outside this set are **ineligible**.
* **Order boundary:** S5 **MUST NOT** encode or imply inter-country order (authority remains **1A `s3_candidate_set`**).
* **RNG envelope:** Assignment randomness **MUST** be expressed via the canonical RNG event anchor (substream `site_tile_assign`) with the documented **budget** (one uniform per assigned site) and envelope fields; missing/extra events are a failure.
* **Gate reliance:** S5 **relies on** the fingerprint-scoped S0 receipt; it **does not** re-hash the 1A bundle.

**3.5 Identities bound for this state.**
All reads/writes bind to exactly **one** identity triple **`{seed, manifest_fingerprint, parameter_hash}`** for the entire publish; mixing identities is **forbidden**.

**3.6 Prohibited surfaces (fail-closed).**
S5 **MUST NOT** read `world_countries`, `population_raster_2025`, `tz_world_2025a`, or any surface not listed in §3.1 for assignment logic.

**3.7 Path↔embed equality (where embedded).**
If lineage fields are embedded in rows in this or a future revision, their values **MUST equal** the corresponding path tokens `{seed, manifest_fingerprint, parameter_hash}`; RNG logs **MUST** use the matching `{seed, parameter_hash}` and a single `run_id` for the publish.

---

# 4) Outputs (datasets) & identity **(Binding)**

**4.1 Dataset & canonical anchors.**

* **Dataset ID:** `s5_site_tile_assignment`
* **Schema (sole shape authority):** `schemas.1B.yaml#/plan/s5_site_tile_assignment` *(canonical anchor; this spec does not restate columns/keys).*
* **RNG event stream (authority):** `schemas.layer1.yaml#/rng/events/site_tile_assign` *(layer RNG envelope for assignment draws).*

**4.2 Path family, partitions, writer sort & format (Dictionary law).**
Resolve via the **Dataset Dictionary** only (no literal paths).

```
data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
```

* **Partitions:** `[seed, fingerprint, parameter_hash]` (one publish per identity; write-once).
* **Writer sort:** `[merchant_id, legal_country_iso, site_order]` (stable merge order; file order non-authoritative).
* **Format:** `parquet`.

**4.3 RNG logs (path family & partitions).**
Assignment RNG events are published under the layer RNG log space:

```
logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Partitions:** `[seed, parameter_hash, run_id]` (no fingerprint in RNG logs).
* **Envelope:** events must validate against the `site_tile_assign` event anchor (module/substream/blocks/draws/trace as defined there).
* **Budget (binding):** exactly **one** assignment event per output row in `s5_site_tile_assignment` for this publish.

**4.4 Row admission (dataset).**
Emit **exactly one** row per outlet stub `(merchant_id, legal_country_iso, site_order)` with its assigned `tile_id`. No duplicates; no omissions; no zero/placeholder rows.

**4.5 Immutability & atomic publish (dataset).**
Write-once per `{seed, manifest_fingerprint, parameter_hash}`. Re-publishing to the same identity **must be byte-identical**. Publish via stage → fsync → single atomic move; file order is non-authoritative.

**4.6 Identity & lineage constraints.**

* **Dataset identity:** `{seed, manifest_fingerprint, parameter_hash}` (triple) for all reads/writes.
* **RNG logs identity:** `{seed, parameter_hash, run_id}`; a single `run_id` is minted and used consistently for the publish.
* **Parity:** `{seed}` used to read `s4_alloc_plan` and `{parameter_hash}` used to read `tile_index` **equal** the dataset publish tokens.
* **Path↔embed:** where lineage fields are embedded in rows in any future revision, values **must equal** the corresponding path tokens.

**4.7 Licence, retention, PII (Dictionary authority).**
Licence/retention/PII for `s5_site_tile_assignment` are governed by its Dictionary entry. Writers **must not** override these at write time. (RNG logs follow the layer’s log retention policy.)

**4.8 Forward consumers (non-authoritative note).**
Produced by **1B.S5**; consumed by **S6+** (e.g., jitter/lat-lon synthesis and downstream egress shaping). Inter-country order remains external (authority = **1A `s3_candidate_set`**).

---

# 5) Dataset shapes & schema anchors **(Binding)**

**5.1 Canonical anchors (single sources of truth).**

* **Dataset:** `schemas.1B.yaml#/plan/s5_site_tile_assignment`
* **RNG events:** `schemas.layer1.yaml#/rng/events/site_tile_assign`
  This spec **does not** restate columns, domains, PK/partition/sort, or event fields. Those live **only** in the schema packs, which **must** include these anchors before any S5 publish.

**5.2 Ownership & precedence.**

* **Shape authority:** the schema packs above (dataset + RNG envelope).
* **IDs→paths/partitions/writer policy/licence:** Dataset Dictionary.
* **Provenance/licences:** Artefact Registry.
  If Dictionary text and Schema ever differ on **shape**, **Schema wins**.

**5.3 Validation obligation.**

* The `s5_site_tile_assignment` dataset **must validate** against `#/plan/s5_site_tile_assignment` (including PK/partition/sort and any FKs).
* All assignment RNG events **must validate** against `#/rng/events/site_tile_assign` (envelope + substream constraints). Any deviation is a schema-conformance failure (see §8/§9).

**5.4 Columns-strict posture.**
The dataset anchor enforces a **strict column set** (no undeclared columns). The RNG event anchor enforces its envelope fields (module/substream/blocks/draws/trace). This document **relies on** those anchors and **does not duplicate** them here.

**5.5 Compatibility (schema-owned).**
Changes to dataset keys/columns/partitioning/sort, RNG substream/envelope fields, or FK targets are **MAJOR** per §12. Additive, non-semantic observability outside the dataset partition is **MINOR**. Editorial wording is **PATCH**.

**5.6 Cross-file `$ref` hygiene.**
Any cross-schema references (e.g., FK to `tile_index`, FK to the ingress ISO surface, layer RNG `$defs`) are declared **in the schema packs**. This spec references **only** the canonical anchors in §5.1.

---

# 6) Deterministic algorithm (with RNG) **(Binding)**

**6.1 Fix identity & gate (once per run).**
a) Fix the identity triple **`{seed, manifest_fingerprint, parameter_hash}`** for the whole publish.
b) Validate the **S0 receipt** for `manifest_fingerprint` (schema-valid; **No PASS → No read**). S5 **relies on** this receipt and **does not** re-hash 1A’s bundle.
c) Resolve all inputs/outputs strictly via the **Dataset Dictionary** (no literal paths).

**6.2 Locate inputs (identity parity checks).**
a) Read **`s4_alloc_plan`** for the fixed `{seed, fingerprint, parameter_hash}`.
b) Read **`tile_index`** (same `{parameter_hash}`) and **`iso3166_canonical_2024`** (FK domain).
c) Assert **parity** before any emit: the `{seed}` used to read `s4_alloc_plan` and the `{parameter_hash}` used to read `tile_index` **equal** the intended publish tokens.

**6.3 Prepare pair frames (per `(merchant_id, legal_country_iso)`).**
a) **Tile multiset** `T`: expand `s4_alloc_plan` into a multiset of `tile_id`s with multiplicity `n_sites_tile` (positives only). Sort `T` by **ascending numeric `tile_id`**.
b) **Site list** `S`: let `N := Σ_{tiles} n_sites_tile` for the pair; construct `S = [1, 2, …, N]` (this is the **site_order** list; contiguity is guaranteed by upstream contracts).

**6.4 RNG draws (one per site).**
For each `site_order ∈ S`, draw **one** uniform `u ∈ (0,1)` under the layer RNG envelope, substream **`site_tile_assign`**.

* **Budget (binding):** exactly **one** RNG event **per site**.
* Each event records the substream and the single draw for this site (envelope fields as defined by the RNG schema).
* Open-interval mapping is enforced by the envelope; if the envelope produces a boundary value, it is mapped per envelope rules (no restatement here).

**6.5 Deterministic permutation of sites (stable tie-break).**
Sort `S` **ascending by** the key **`(u, site_order)`**, producing `S_perm`.

* This yields a reproducible random permutation with exactly one draw per site.
* Ties on `u` (rare but possible by quantisation) break by **ascending `site_order`**.

**6.6 Assignment (quota-exact, RNG-driven pairing).**
Iterate the sorted tile multiset **`T`** in ascending `tile_id`. For each run of identical `tile_id` of length `a` in `T`, **take the next `a` elements** from `S_perm` and assign those `site_order`s to that `tile_id`.

* This guarantees, for the pair, **count per tile = `n_sites_tile`** and **Σ across tiles = `N`**.
* No additional randomness or re-scaling is performed.

**6.7 Emit outputs.**
a) **Dataset rows:** emit **exactly one** row per site `(merchant_id, legal_country_iso, site_order)` with its assigned `tile_id`.
b) **Writer sort:** output rows in non-decreasing **`[merchant_id, legal_country_iso, site_order]`**. **File order is non-authoritative**.
c) **RNG events:** for each emitted row, write the corresponding **one** RNG event (the draw used for that site) under `…/logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.
d) **Budget equality:** total RNG events **equals** total dataset rows for the publish.

**6.8 Universe & FK integrity (during emit).**
Every `(legal_country_iso, tile_id)` assigned **must exist** in `tile_index` for the same `{parameter_hash}`; `legal_country_iso` **must** be in the ISO FK surface. Violations fail closed.

**6.9 Idempotence & identity discipline.**
Given identical sealed inputs and the same identity triple `{seed, manifest_fingerprint, parameter_hash}`, S5 **must** reproduce **byte-identical** output (dataset) and the **same RNG events** (order/content).

* Publish under `data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`.
* **Write-once:** re-publishing to the same identity must be byte-identical (stage → fsync → single atomic move).

**6.10 Prohibitions (fail-closed).**

* Do **not** read surfaces outside §2.4.
* Do **not** alter S4 counts or introduce any alternative quota logic.
* Do **not** encode or imply inter-country order (authority remains 1A `s3_candidate_set`).
* Do **not** exceed or under-spend the RNG budget (exactly one event per assigned site).

---

# 7) Identity, partitions, ordering & merge discipline **(Binding)**

**7.1 Identity tokens.**

* **Dataset identity:** exactly one **`{seed, manifest_fingerprint, parameter_hash}`** for the entire S5 publish. Mixing identities within a publish is **forbidden**.
* **RNG logs identity:** **`{seed, parameter_hash, run_id}`**. A single **`run_id`** is minted at job start and used for all S5 assignment events.

**7.2 Partition law & path families (resolve via Dataset Dictionary; no literal paths).**

* **Dataset path family:**
  `data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  **Partitions:** `[seed, fingerprint, parameter_hash]` · **Format:** parquet · **Write-once** (no appends/compaction).
* **RNG logs path family:**
  `logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  **Partitions:** `[seed, parameter_hash, run_id]` · **Append-only during job**, then frozen on success.

**7.3 Writer sort & file-order posture.**

* **Dataset writer sort:** `[merchant_id, legal_country_iso, site_order]` (stable merge order; file order **non-authoritative**).
* **RNG logs:** no row order requirement; validators rely on counts/budget and event content per the RNG envelope, not file order.

**7.4 Identity-coherence checks (must hold before publish).**

* **Receipt parity (fingerprint):** dataset `fingerprint` equals **S0 receipt** `manifest_fingerprint` (S0 is fingerprint-scoped).
* **Seed parity (S3/S4 scope):** dataset `seed` equals the `seed` used to read **`s4_alloc_plan`**; RNG logs `seed` equals dataset `seed`.
* **Parameter parity (S2 scope):** dataset `parameter_hash` equals the value used to read **`tile_index`**; RNG logs `parameter_hash` equals dataset `parameter_hash`.
* **Path↔embed equality:** if lineage fields are embedded in rows in this or a future revision, embedded values **must equal** their path tokens.

**7.5 Parallelism & determinism.**
Parallel materialisation is allowed (e.g., sharding by `merchant_id` or by `(merchant_id, legal_country_iso)`), **provided** the final dataset results from a **stable merge** ordered by `[merchant_id, legal_country_iso, site_order]` and outcomes do **not** vary with worker/scheduling. RNG events may be emitted from multiple workers, but all must use the single minted `run_id` and satisfy the **exact budget** (one event per assigned site).

**7.6 Atomic publish, immutability & idempotence.**

* **Dataset:** stage → fsync → **single atomic move** into the identity partition. Re-publishing under the same `{seed, manifest_fingerprint, parameter_hash}` must be **byte-identical** or is a hard error.
* **RNG logs:** append-only within the `run_id` partition during the run; on **success**, freeze the partition (no edits/deletes). Re-running with the same inputs and identity **must** reproduce the **same events** (content) under the same `run_id` or use a new `run_id`.

**7.7 Prohibitions (fail-closed).**

* **No mixed identities** (no mixing seeds, fingerprints, or parameter hashes within a publish).
* **No literal paths** in code; all IO resolves by **Dataset Dictionary**.
* **No post-publish mutation** of dataset or RNG log partitions.

---

# 8) Acceptance criteria (validators) **(Binding)**

**8.1 Gate & identity (pre-write).**

* Exactly one `s0_gate_receipt_1B` exists for the target `manifest_fingerprint` and **schema-validates**; S5 **relies on** the receipt (no bundle re-hash).
* **Identity parity:** publish tokens `{seed, manifest_fingerprint, parameter_hash}` **match** the tokens used to read `s4_alloc_plan` (seed+fingerprint+param) and `tile_index` (param). RNG logs use the same `{seed, parameter_hash}` and a **single** `run_id`.
* **Fail:** `E301_NO_PASS_FLAG`, `E_RECEIPT_SCHEMA_INVALID`, `E508_TOKEN_MISMATCH`.

**8.2 Schema conformance (dataset).**

* `s5_site_tile_assignment` **validates** against `schemas.1B.yaml#/plan/s5_site_tile_assignment` (strict columns; PK/partition/sort as the anchor).
* **Fail:** `E506_SCHEMA_INVALID`, `E506_SCHEMA_EXTRAS`.

**8.3 RNG envelope conformance (logs).**

* Every assignment event **validates** against the layer RNG anchor `#/rng/events/site_tile_assign` (module/substream/blocks/draws/trace).
* Substream equals `site_tile_assign`; **draws = 1** per event; `{seed, parameter_hash, run_id}` match the publish; event `manifest_fingerprint` **equals** the dataset `manifest_fingerprint`.
* **Fail:** `E507_RNG_EVENT_MISMATCH`.

**8.4 PK uniqueness & completeness (dataset).**

* No duplicate `(merchant_id, legal_country_iso, site_order)` within the identity partition.
* Every site for each `(merchant_id, legal_country_iso)` appears **exactly once**.
* **Fail:** `E502_PK_DUPLICATE_SITE`, `E504_SUM_TO_N_MISMATCH`.

**8.5 Quota satisfaction (pair & per-tile).**

* For each `(merchant_id, legal_country_iso, tile_id)`:
  `count(assignments) == s4_alloc_plan.n_sites_tile`.
* Across tiles for the pair:
  `Σ assignments == Σ s4_alloc_plan.n_sites_tile == s3_requirements.n_sites` (same identity).
* **Fail:** `E503_TILE_QUOTA_MISMATCH`, `E504_SUM_TO_N_MISMATCH`.

**8.6 Universe & FK.**

* Every `(legal_country_iso, tile_id)` assigned **exists** in `tile_index` for `{parameter_hash}`; `legal_country_iso` is in the ingress ISO surface.
* **Fail:** `E505_TILE_NOT_IN_INDEX`, `E302_FK_COUNTRY`.

**8.7 RNG budgeting (one-to-one).**

* **Exactly one** RNG event per emitted dataset row; **no missing/extra** events; all events belong to the single `run_id`.
* **Fail:** `E507_RNG_EVENT_MISMATCH`.

**8.8 Partition, immutability & atomic publish (dataset).**

* Published under `…/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`.
* Re-publishing to the same identity must be **byte-identical**; stage → fsync → atomic move.
* **Fail:** `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`.

**8.9 Writer sort (stable merge order).**

* Rows in non-decreasing `[merchant_id, legal_country_iso, site_order]`; file order non-authoritative.
* **Fail:** `E509_UNSORTED`.

**8.10 Prohibitions (fail-closed).**

* No reads outside §2.4 (e.g., `world_countries`, `population_raster_2025`, `tz_world_2025a`).
* No alteration of S4 counts; no order encoding (authority = 1A `s3_candidate_set`).
* **Fail:** `E510_DISALLOWED_READ`, `E312_ORDER_AUTHORITY_VIOLATION`, `E414_WEIGHT_TAMPER`.

**8.11 Determinism receipt (binding evidence).**

* Run report contains a composite SHA-256 over ASCII-lex ordered bytes of all files in the dataset partition; re-read reproduces the **same** hash.
* **Fail:** `E410_NONDETERMINISTIC_OUTPUT`.

**8.12 Required run-report fields (presence).**

* Present **outside** the dataset partition: `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`, `rows_emitted`, `rng_events_emitted`, `pairs_total`, determinism receipt `{partition_path, sha256_hex}`.
* **Fail:** `E515_RUN_REPORT_MISSING_FIELDS`.

---

# 9) Failure modes & canonical error codes **(Binding)**

> **Fail-closed posture.** On first detection of any condition below, the writer **MUST** abort the run, emit a failure record, and ensure **no partials** are visible under
> `…/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
> (write-once; atomic publish). RNG logs are **append-only during the job** under
> `logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/` and then **frozen** on success.

### E301_NO_PASS_FLAG — S0 gate not proven *(ABORT)*

**Trigger:** Missing S0 receipt for `manifest_fingerprint` or receipt not retrievable.
**Detection:** Receipt lookup fails (absence or unreadable).

### E_RECEIPT_SCHEMA_INVALID — S0 receipt fails schema *(ABORT)*

**Trigger:** `s0_gate_receipt_1B` does not validate against its schema.
**Detection:** JSON-Schema validation failure (shape/required keys/types).

### E502_PK_DUPLICATE_SITE — Duplicate site key *(ABORT)*

**Trigger:** Duplicate `(merchant_id, legal_country_iso, site_order)` within the identity partition.
**Detection:** PK uniqueness check over `s5_site_tile_assignment`.

### E503_TILE_QUOTA_MISMATCH — Per-tile quota not satisfied *(ABORT)*

**Trigger:** For any `(merchant_id, legal_country_iso, tile_id)`,
`count(assignments) ≠ s4_alloc_plan.n_sites_tile`.
**Detection:** Join counts vs S4 for the same identity.

### E504_SUM_TO_N_MISMATCH — Pair sum not conserved *(ABORT)*

**Trigger:** For any `(merchant_id, legal_country_iso)`,
`Σ_tile count(assignments) ≠ Σ_tile s4_alloc_plan.n_sites_tile` (and hence ≠ S3 `n_sites`).
**Detection:** Conservation check per pair for the same identity.

### E505_TILE_NOT_IN_INDEX — Tile outside universe *(ABORT)*

**Trigger:** Any assigned `(legal_country_iso, tile_id)` not present in `tile_index` for `{parameter_hash}`.
**Detection:** FK/universe check vs `tile_index`.

### E506_SCHEMA_INVALID — Dataset shape/keys invalid *(ABORT)*

**Variant:** **E506_SCHEMA_EXTRAS** — undeclared column(s) present.
**Trigger:** `s5_site_tile_assignment` fails its canonical schema anchor (columns/PK/partition/sort).
**Detection:** JSON-Schema validation failure.

### E507_RNG_EVENT_MISMATCH — RNG envelope/budget invalid *(ABORT)*

**Trigger (any of):**

* Event fails the `site_tile_assign` RNG anchor (envelope/substream/blocks/draws).
* Substream ≠ `site_tile_assign`.
* **Budget mismatch:** number of events ≠ number of emitted dataset rows.
* Identity mismatch on events: `{seed, parameter_hash}` or multiple `run_id`s in one publish.
  **Detection:** Validate all events; count-match events ↔ dataset rows; check identities and single-`run_id` use.

### E508_TOKEN_MISMATCH — Path↔identity inequality *(ABORT)*

**Trigger:** Any publish token `{seed|fingerprint|parameter_hash}` differs from the tokens used to read inputs (S4/S1) or from embedded lineage fields (where present).
**Detection:** Identity parity checks prior to publish; path↔embed equality where embedded.

### E509_UNSORTED — Writer sort violated *(ABORT)*

**Trigger:** Rows not in non-decreasing `[merchant_id, legal_country_iso, site_order]`.
**Detection:** Sort-order validator.

### E510_DISALLOWED_READ — Out-of-scope surface read *(ABORT)*

**Trigger:** S5 reads any surface not listed in §2.4 (e.g., `world_countries`, `population_raster_2025`, `tz_world_2025a`).
**Detection:** Access audit / job IO tracing.

### E312_ORDER_AUTHORITY_VIOLATION — Order implied/encoded *(ABORT)*

**Trigger:** Output encodes or implies **inter-country order** (authority is 1A `s3_candidate_set`).
**Detection:** Presence of order fields or cross-country ordering derivations.

### E414_WEIGHT_TAMPER — Counts/weights tampered *(ABORT)*

**Trigger:** S5 renormalises or alters S4 `n_sites_tile` semantics (any re-scaling/re-optimisation).
**Detection:** Compare produced assignments’ per-tile totals against S4; any systematic drift → tamper.

### E410_NONDETERMINISTIC_OUTPUT — Re-run hash differs *(ABORT)*

**Trigger:** Determinism receipt over the dataset partition does not reproduce on clean re-read.
**Detection:** Composite SHA-256 mismatch (ASCII-lex file order).

### E515_RUN_REPORT_MISSING_FIELDS — Required run-report fields missing *(ABORT)*

**Trigger:** One or more required fields from §10.2 absent (e.g., `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`, `rows_emitted`, `rng_events_emitted`, determinism receipt).
**Detection:** Run-report presence/shape check (outside the dataset partition).

---

## 9.1 Failure handling *(normative)*

* **Abort semantics:** Stop the run; **no** files promoted under the live dataset partition unless all validators PASS. Use stage → fsync → **single atomic move** only after PASS.
* **Failure record (outside the dataset partition):** `{code, scope ∈ {run,pair}, reason, seed, manifest_fingerprint, parameter_hash, run_id}`; include `{merchant_id, legal_country_iso}` when applicable.
* **RNG logs on failure:** Log partitions for the active `run_id` may remain as evidence; they are **not** considered acceptance artefacts.
* **Multi-error policy:** Multiple failures **may** be recorded; acceptance remains **failed**.

## 9.2 Code space & stability *(normative)*

* **Reserved (this state):** `E501`–`E515` as used above, plus reused cross-state codes `E301_*`, `E312_*`, `E410`, and `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`.
* **SemVer impact:** Tightening triggers that cannot flip prior accepted reference runs = **MINOR**; changes that can flip outcomes or alter identities/partitioning = **MAJOR**.

---

# 10) Observability & run-report **(Binding)**

> Observability artefacts are **required** and **retrievable** by validators but do **not** alter the semantics of `s5_site_tile_assignment`. They **must not** be written inside the dataset partition. This mirrors S3/S4 posture.

**10.1 Deliverables (outside the dataset partition; binding for presence)**
An accepted S5 run **MUST** expose, outside
`…/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`:

* **S5 run report** — single machine-readable JSON object (fields in §10.2).
* **Determinism receipt** — composite SHA-256 over the produced **dataset partition files only** (recipe in §10.4).
* *(Optional but recommended)* **Summaries** for auditor convenience (formats in §10.3). Presence of the run report + receipt is **binding**; summaries are optional.

**10.2 S5 run report — required fields (binding for presence)**
The run report **MUST** include at least:

* `seed` — lineage token for the run identity.
* `manifest_fingerprint` — fingerprint proven by S0.
* `parameter_hash` — parameter identity used for S1/S2 surfaces.
* `run_id` — RNG log stream identifier minted at job start.
* `rows_emitted` — total rows written to `s5_site_tile_assignment`.
* `pairs_total` — distinct `(merchant_id, legal_country_iso)` in the dataset.
* `rng_events_emitted` — total `site_tile_assign` events written for this publish.
* `determinism_receipt` — object per §10.4 `{ partition_path, sha256_hex }`.

**10.3 Summaries (optional; recommended formats)**

* **Per-merchant summary:** for each `merchant_id`: `countries`, `sites_total`, `tiles_distinct`, `assignments_by_country`.
* **RNG budgeting summary:** `{ expected_events: rows_emitted, actual_events: rng_events_emitted }` and (if useful) counts by worker/shard; expected = actual on acceptance.
* **Health counters:** `fk_country_violations`, `tile_not_in_index`, `quota_mismatches`, `dup_sites` — all expected **0** on acceptance.

**10.4 Determinism receipt — composite hash (method is normative)**
Compute a **composite SHA-256** over the **dataset partition files only**:

1. List all files under
   `…/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
   as **relative paths**, **ASCII-lex sort** them.
2. Concatenate raw bytes in that order; compute SHA-256; encode as lowercase hex64.
3. Store `{ "partition_path": "<path>", "sha256_hex": "<hex64>" }` as `determinism_receipt` in the run report.
   *(RNG logs are not included in this receipt; they have their own identity `{seed, parameter_hash, run_id}` and are validated by budget/event-shape checks.)*

**10.5 Packaging, location & retention (binding)**

* Place run report, determinism receipt, and any summaries **outside** the dataset partition (control-plane artefacts or job attachments/logs).
* Retain for **≥ 30 days** (or your programme’s configured retention).
* All paths for evidence retrieval **must** resolve via the Dataset Dictionary (no literal paths).

**10.6 Failure event schema (binding for presence on failure)**
On any §9 failure, emit a structured event (outside the dataset partition):

* `event: "S5_ERROR"`, `code: <one of §9>`, `at: <RFC-3339 UTC>`,
  **`seed`**, **`manifest_fingerprint`**, **`parameter_hash`**, **`run_id`**; optionally `merchant_id`, `legal_country_iso`.
  RNG-log partitions for the active `run_id` may remain as evidence; they are **not** acceptance artefacts.

**10.7 Auditor checklist (retrievability expectations)**

* Run report present with all **required fields** in §10.2.
* Determinism receipt present and recomputable to the **same** hash.
* `rng_events_emitted == rows_emitted` (one event per dataset row), all events under a **single** `run_id`, identities match.
* Evidence stored **outside** the dataset partition; retention policy satisfied; paths resolve via the Dictionary.

---

# 11) Performance & scalability *(Informative)*

**11.1 Workload model.**
Process **pair-by-pair** `(merchant_id, legal_country_iso)` from `s4_alloc_plan`. For each pair, build the **tile multiset** from S4 (`n_sites_tile` copies per `tile_id`), generate **one RNG draw per site**, derive a reproducible permutation of `site_order`, and pair sites to tiles exactly as S4 quotas require. Emit only positives; no cross-product materialisation beyond a pair’s sites.

**11.2 Asymptotics (per pair).**
Let **N** = number of sites for the pair (Σ `n_sites_tile`), **M** = number of tiles with `n_sites_tile>0`.

* **Time:** O(N log N) with a straight sort-by-`(u, site_order)` (reference method), or O(N log (N/B)) with external/chunked sort (block size **B**).
* **Space:** In-memory permutation → O(N). External sort → O(B) memory + sequential spill/merge; O(M) for the tile multiset iterator.

**11.3 External-sort strategy (recommended for large N).**
Generate the **one** RNG draw `u` per site and write `(u, site_order)` to bounded **sorted runs**; K-way merge them to form the global permutation `S_perm`. This preserves: (i) **exactly one** RNG event per site, (ii) stable tie-break `(u, site_order)`, and (iii) reproducible output under concurrency.

**11.4 Chunking & back-pressure.**
Chunk the work by **merchant** or by **(merchant, country)** so that per-pair memory stays within your cap. Apply back-pressure to the RNG-event sink and dataset writer to keep peak RSS and open-files within target envelopes while maintaining steady throughput.

**11.5 Parallelism (deterministic).**
Shard by merchant or by (merchant, country). Each shard independently produces its pair assignments and **RNG events**; all shards share the **single `run_id`** for the publish. The final dataset is a **stable merge** ordered by `[merchant_id, legal_country_iso, site_order]`. Outcomes must not vary with worker layout.

**11.6 I/O posture.**
Single pass over `s4_alloc_plan`; per-country reads from `tile_index` can be cached and reused across pairs in the same country. Write **one** dataset partition per identity and append RNG events under `{seed, parameter_hash, run_id}`. Aim for **≤ 1.25×** amplification per surface (bytes read vs on-disk).

**11.7 Caching.**
Maintain a tiny cache keyed by `legal_country_iso` with that country’s **eligible tile set** (from `tile_index`) and, if helpful, precomputed **tile spans** (prefix sums of `n_sites_tile`) for quick multiset iteration. Evict LRU by country to respect memory caps.

**11.8 RNG event throughput & integrity.**
Batch RNG events in small buffers and flush frequently; verify **event budget == rows emitted** at shard boundaries and again at job end. Enforce that **all events** use the **same `run_id`** and the correct `{seed, parameter_hash}` tokens.

**11.9 Determinism safeguards.**

* Use stable comparison `(u, site_order)`; never rely on non-deterministic tie resolution.
* Keep file order **non-authoritative**; rely on writer-sort and the **composite determinism receipt** over ASCII-lex file listing.
* Ensure that any parallel K-way merge produces the **same** byte output given the same inputs and identity.

**11.10 Operational targets (non-binding).**
Per worker: set caps for **RSS**, temp disk, and open files consistent with S4; pick a block size **B** that fits comfortably under those caps; adopt compressed columnar output with moderate row-groups to balance scan efficiency and memory.

**11.11 Health counters (suggested, non-binding).**
Record in the run report: `rows_emitted`, `pairs_total`, `rng_events_emitted`, `expected_rng_events` (should equal `rows_emitted`), `quota_mismatches`, `dup_sites`, `tile_not_in_index`, plus basic resource stats (`bytes_read_s4`, `bytes_read_index`, `wall_clock_seconds_total`, `max_worker_rss_bytes`). These aid PAT and regressions without affecting acceptance.

---

# 12) Change control & compatibility **(Binding)**

**12.1 SemVer ground rules.**
This state follows **MAJOR.MINOR.PATCH**.

* **MAJOR**: any change that can make previously conformant S5 outputs/logs **invalid or different** for the same sealed inputs and identity, or that requires consumer changes.
* **MINOR**: strictly backward-compatible additions/tightenings that do **not** flip accepted reference runs from PASS→FAIL.
* **PATCH**: editorial only (no behaviour change).

**12.2 What requires a MAJOR bump (breaking).**

* **Dataset contract** for `s5_site_tile_assignment`: PK, column set/types, `columns_strict` posture, **partition keys** (`[seed, manifest_fingerprint, parameter_hash]`), **writer sort** (`[merchant_id, legal_country_iso, site_order]`), or **path family**.
* **RNG event contract** for `site_tile_assign`: substream name, envelope fields (module/substream/blocks/draws/trace), identity/partitioning (`[seed, parameter_hash, run_id]`).
* **RNG budgeting semantics**: changing “**exactly one** event per assigned site” or the rule that produces the permutation (e.g., replacing the `(u, site_order)` ordering with another).
* **Authority/precedence model**: Schema as sole shape authority; Dictionary governs IDs→paths/partitions/sort/licence; Registry records provenance/licences.
* **Gate/lineage law**: reliance on S0 receipt (no bundle re-hash in S5), path↔embed equality rules.
* **Inputs/identity set**: adding/removing required inputs or altering the identity tokens (adding/removing any of `{seed, manifest_fingerprint, parameter_hash}` for the dataset or `{seed, parameter_hash, run_id}` for RNG logs).

**12.3 What qualifies as MINOR (backward-compatible).**

* Adding **non-semantic** fields to the run report or optional summaries (outside the dataset partition).
* Tightening validators proven not to flip previously accepted **reference** runs (e.g., clearer diagnostics, additional checks that only catch invalid publishes).
* Registry/Dictionary **writer-policy** refinements that leave value semantics unchanged (e.g., compression/row-group sizing), or clarifying notes that don’t alter shape or identity.

**12.4 What is PATCH (non-behavioural).**

* Wording fixes, cross-reference repairs, examples/figures, or clarifications that **do not** change schemas, anchors, identities, acceptance rules, RNG budgeting, or failure codes.

**12.5 Compatibility window (assumed upstream stability).**
Within S5 **v1.***, the following remain on their own **v1.*** lines:

* **S4** `s4_alloc_plan` (dataset identity = `[seed, manifest_fingerprint, parameter_hash]`; authoritative per-tile integers).
* **S1/S2** (`tile_index`/`tile_weights`) parameter-scoped shapes/semantics.
  If any of those bump **MAJOR** or move anchors/IDs materially, S5 must be **re-ratified** and bump **MAJOR** accordingly.

**12.6 Migration & deprecation.**
On a MAJOR:
a) Freeze the old S5 spec/version and anchors;
b) Introduce a **new schema anchor** (e.g., `#/plan/s5_site_tile_assignment_v2`) and, if shape/paths change, a **new Dictionary ID**;
c) Document exact diffs and a cut-over plan;
d) Do **not** rely on Dictionary aliases to silently bridge breaking ID/path changes; consumers must explicitly adopt the new ID/anchor.

**12.7 Lineage tokens vs SemVer.**
`seed`, `manifest_fingerprint`, `parameter_hash`, and `run_id` are **orthogonal** to SemVer. They change with governed inputs/parameters or job execution, producing new partitions/streams **without implying** a spec change. Any renaming, merging/splitting, or removal of these tokens is **MAJOR**.

**12.8 Consumer compatibility covenant (within v1.*).**
For S5 **v1.***:

* Dataset identity = `[seed, manifest_fingerprint, parameter_hash]`; RNG logs identity = `[seed, parameter_hash, run_id]`.
* One dataset row **per site**; RNG **one event per row** (budget equality).
* Counts preserved: per-tile assignments equal S4 `n_sites_tile`; per-pair sums equal S3/S4 `n_sites`.
* Universe constraint: assigned `(legal_country_iso, tile_id)` exists in `tile_index` for the parameter.
* Writer sort and immutability laws remain as specified; file order **non-authoritative**.
* No inter-country order encoded; order authority remains with **1A**.

**12.9 Ratification record.**
Record for each release: `semver`, `effective_date`, ratifiers, code commit (and optional SHA-256 of this file). Keep a link to the prior MAJOR’s frozen copy.

---

# Appendix A — Symbols & notational conventions *(Informative)*

**A.1 Identity & lineage tokens**

* **`seed`** — Unsigned 64-bit master seed for the run; scopes S3/S4/S5 datasets and RNG logs.
* **`manifest_fingerprint`** — Lowercase **hex64** SHA-256 proving the S0 gate; used in dataset paths (not RNG logs).
* **`parameter_hash`** — Lowercase **hex64** SHA-256 of the governed **parameter bundle**; scopes S1/S2 tables and S3–S5 datasets.
* **`run_id`** — Lowercase **hex32** identifier for the S5 RNG event stream; one per S5 publish.

**A.2 Dataset & stream IDs (referenced in S5)**

* **`s4_alloc_plan`** — Per-tile integers `n_sites_tile ≥ 1` for each `(merchant_id, legal_country_iso, tile_id)` under `{seed, manifest_fingerprint, parameter_hash}`.
* **`s5_site_tile_assignment`** — *(This state’s dataset)* one row per site with assigned `tile_id` under `{seed, manifest_fingerprint, parameter_hash}`.
* **`tile_index`** — Eligible tile universe for `{parameter_hash}`.
* **`site_tile_assign`** — RNG **substream** name under the layer RNG envelope for S5 assignment draws (logs partitioned by `{seed, parameter_hash, run_id}`).

**A.3 Entities & keys**

* **Pair** — `(merchant_id, legal_country_iso)`.
* **Site key (PK columns)** — `(merchant_id, legal_country_iso, site_order)`.
* **Tile key** — `(legal_country_iso, tile_id)`; must exist in `tile_index` (same `{parameter_hash}`).

**A.4 Quantities used in S5**

* **`n_sites_tile`** — Integer quota from S4 for a specific `(merchant_id, legal_country_iso, tile_id)`; positives only.
* **`N`** — Number of sites for a pair: `N = Σ_tile n_sites_tile`.
* **`S`** — The site list for a pair: `[1, 2, …, N]` (site_order, contiguous).
* **`T`** — Tile **multiset** built by expanding S4 quotas (each `tile_id` replicated `n_sites_tile` times); iterated in **ascending numeric `tile_id`**.
* **`u`** — One uniform draw in **(0,1)** per site from the layer RNG envelope (substream `site_tile_assign`).
* **`S_perm`** — Deterministic permutation of sites produced by sorting **`S`** by key **`(u, site_order)`** (tie-break by ascending `site_order`).

**A.5 Laws repeatedly referenced**

* **Sum-to-N:** For each pair, the number of assigned sites equals `N` and, for every tile, `count(assignments) = n_sites_tile`.
* **RNG budget:** Exactly **one** RNG event per emitted dataset row (one per site).
* **Identity parity:** Dataset identity `{seed, manifest_fingerprint, parameter_hash}` matches the tokens used to read inputs; RNG logs use `{seed, parameter_hash, run_id}` and the single minted `run_id`.
* **Gate law:** Read authority relies on the **S0 receipt** for `manifest_fingerprint` (**No PASS → No read**).
* **Resolution & shape:** IO resolves via the **Dataset Dictionary** (no literal paths); **JSON-Schema** is the **sole shape authority** for both dataset and RNG events.
* **Path↔embed equality:** If lineage fields are embedded in rows in this or a future revision, their values equal the corresponding path tokens.

**A.6 Abbreviations**

* **PK** — Primary key (within an identity partition).
* **FK** — Foreign key.
* **PASS/ABORT** — Gate outcomes or validator results.
* **RNG** — Random number generation (here: layer envelope with substream `site_tile_assign`).

---

# Appendix B — Worked example *(Informative)*

This miniature walk-through shows S5’s assignment mechanics and how the validators pass, without restating any schema shapes.

---

## B.1 Identity & inputs

**Identity (this publish):**
`seed = 42` · `manifest_fingerprint = 6f…a1` · `parameter_hash = 3c…9d` · `run_id = a7e2`

**From S4 (`s4_alloc_plan`) for one pair:** `(merchant_id=101, legal_country_iso=GB)`

| tile_id | n_sites_tile |
|--------:|-------------:|
|    7001 |            2 |
|    7002 |            1 |
|    7005 |            2 |

So **N = Σ n_sites_tile = 5**. All three `(GB, tile_id)` exist in `tile_index` for the same `{parameter_hash}`.

---

## B.2 Construct site list and tile multiset

* **Site list** `S` (by upstream contract, contiguous): `[1, 2, 3, 4, 5]`
* **Tile multiset** `T` (ascending numeric `tile_id`):
  `T = [7001, 7001, 7002, 7005, 7005]`  (two copies of 7001, one of 7002, two of 7005)

---

## B.3 RNG draws (one per site) and permutation

Under the `site_tile_assign` substream (RNG envelope), draw **one** `u ∈ (0,1)` per site:

| site_order | u (uniform) |
|-----------:|------------:|
|          1 |        0.37 |
|          2 |        0.82 |
|          3 |        0.37 |
|          4 |        0.05 |
|          5 |        0.41 |

**Permutation rule:** sort by `(u, site_order)` → `S_perm = [4, 1, 3, 5, 2]`
(Note the tie on `u=0.37` resolves by ascending `site_order` → `1` before `3`.)

**RNG budget:** 5 events (exactly one per site). Events are written to
`logs/rng/events/site_tile_assign/seed=42/parameter_hash=3c…9d/run_id=a7e2/…`

---

## B.4 Assignment (quota-exact pairing)

Iterate the tile multiset `T` in order and take the next `a` sites from `S_perm` for each run of `tile_id` with length `a`:

* For `7001` (length 2) → assign sites `4, 1`
* For `7002` (length 1) → assign site `3`
* For `7005` (length 2) → assign sites `5, 2`

**Produced dataset rows** (writer sort `[merchant_id, legal_country_iso, site_order]`):

| merchant_id | legal_country_iso | site_order | tile_id |
|------------:|:-----------------:|-----------:|--------:|
|         101 |        GB         |          1 |    7001 |
|         101 |        GB         |          2 |    7005 |
|         101 |        GB         |          3 |    7002 |
|         101 |        GB         |          4 |    7001 |
|         101 |        GB         |          5 |    7005 |

---

## B.5 Validator checklist (why this passes)

* **PK uniqueness & completeness:** each `(101, GB, site_order)` appears **exactly once**; no duplicates/omissions.
* **Quota satisfaction (per-tile):**

  * `7001` has 2 assignments (sites 4,1) → equals S4 `n_sites_tile=2`.
  * `7002` has 1 assignment (site 3) → equals 1.
  * `7005` has 2 assignments (sites 5,2) → equals 2.
* **Sum-to-N:** across tiles, `2+1+2 = 5 = N = Σ n_sites_tile`.
* **Universe & FK:** all assigned `(GB, tile_id)` exist in `tile_index` (same `{parameter_hash}`); `GB` is in the ISO FK surface.
* **RNG envelope & budget:** **5** `site_tile_assign` events (one per dataset row), identity `{seed=42, parameter_hash=3c…9d, run_id=a7e2}`, substream correct, `draws=1`.
* **Identity parity:** dataset identity `{seed=42, manifest_fingerprint=6f…a1, parameter_hash=3c…9d}` matches the tokens used to read S4 and S1; RNG logs share `{seed, parameter_hash}` and the single `run_id`.
* **Writer sort & immutability:** dataset sorted by `[merchant_id, legal_country_iso, site_order]`; publish is write-once; determinism receipt computed over the partition’s files.

> This example intentionally includes a tie on `u` to illustrate the **stable tie-break** by `site_order`; any other numeric values will produce a different permutation but the same quota-exact counts per tile and the same acceptance outcomes.

---