# State-6 · In-cell Jitter (RNG)

# 1) Purpose & scope **(Binding)**

**1.1 Problem statement.**
S6 produces **per-site, in-tile jitter** offsets so that when applied (in S7) the resulting coordinates remain **inside the site’s assigned tile**. S6 **consumes RNG** (two uniforms per site → Box–Muller) to randomise **sub-tile placement**, but **does not** alter S5 assignments, counts, or tiles. The run identity for all reads/writes is **`{seed, manifest_fingerprint, parameter_hash}`**.

**1.2 Out of scope.**
S6 **does not**: (a) change S5 site→tile assignments or any S4/S3 counts; (b) generate final lat/lon egress (that is S7); (c) encode or imply **inter-country order** (authority remains 1A `s3_candidate_set`); (d) read any surfaces beyond those enumerated for S6.

**1.3 Authority boundaries & invariants.**
a) **Assignment source (S5):** `(merchant_id, legal_country_iso, site_order) → tile_id` is authoritative; S6 must **respect** it as read-only.
b) **Universe & bounds (S1):** `tile_index` is the sole authority for each tile’s centroid and bounding box (`[min_lat,max_lat]×[min_lon,max_lon]`); S6 **must not** emit offsets that would place a site outside these bounds.
c) **Policy authority:** `jitter_policy` governs the σ parameters (degrees) used to scale the jitter per axis; S6 **must not** invent or re-fit σ.
d) **Gate law (S0):** S6 **relies on** the fingerprint-scoped receipt (**No PASS → No read**) and **does not** re-hash the 1A bundle.
e) **Resolution & shape:** All IO **must** resolve via the **Dataset Dictionary** (no literal paths). **JSON-Schema** is the **sole shape authority** for both the dataset and RNG events; this spec does not restate columns/keys.
f) **RNG budgeting:** Exactly **two** uniforms per site (substream `in_cell_jitter`; `draws="2"`); budget shortfall/excess is a failure.

**1.4 Deliverables.**
S6 emits, for the fixed identity **`{seed, manifest_fingerprint, parameter_hash}`**:
a) **Dataset — `s6_site_jitter`**: one row **per site** with the **effective** jitter deltas (after boundary handling). Writer-sorted, immutable, and byte-stable on re-publish.
b) **RNG event stream — `in_cell_jitter`**: one event **per site** (two draws) under the layer envelope to evidence the randomisation is correctly scoped and reproducible.

---

# 2) Preconditions & sealed inputs **(Binding)**

**2.1 Gate (must hold before any read).**
Exactly one **`s0_gate_receipt_1B`** exists for the target `manifest_fingerprint` and **schema-validates**. S6 **relies on the receipt** (**No PASS → No read**) and **does not** re-hash the 1A bundle. The receipt establishes which 1B surfaces may be read.

**2.2 Fixed identities (for the entire publish).**
All S6 reads and writes bind to a single identity triple **`{seed, manifest_fingerprint, parameter_hash}`**. Mixing identities within a publish is **forbidden**.

**2.3 Sealed inputs (resolve via Dataset Dictionary; no literal paths).**

* **`s5_site_tile_assignment`** — path family `…/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` · **partitions:** `[seed, fingerprint, parameter_hash]` · *authoritative site→tile mapping (one row per site).*
* **`tile_index`** — path family `…/tile_index/parameter_hash={parameter_hash}/` · **partitions:** `[parameter_hash]` · *tile centroid and bounding box (eligible universe).*
* **`jitter_policy`** — policy/config artefact providing **σ_lat_deg**, **σ_lon_deg** rules (deterministic function of latitude and/or policy knobs).
* **`iso3166_canonical_2024`** — ingress FK surface for `legal_country_iso`.

**2.4 Inputs S6 will actually read.**
`s5_site_tile_assignment`, `tile_index`, `jitter_policy`, `iso3166_canonical_2024`. *(No other surfaces.)*

**2.5 RNG envelope (pre-run commitments).**

* **Substream:** `in_cell_jitter`.
* **Budget (binding):** **exactly one** RNG event **per site**, with **`draws="2"`** (two uniforms → Box–Muller).
* **Log path family:** `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.
* **Run ID:** a single **`run_id`** is minted at job start and used for **all** S6 events in this publish.
* **Shape authority:** events **must** validate against the canonical layer RNG event anchor for `in_cell_jitter`. *(This spec does not restate event fields.)*

**2.6 Path↔embed & identity parity (must hold before publish).**

* `{seed}` used to read `s5_site_tile_assignment` **equals** the dataset publish token.
* `{parameter_hash}` used to read `tile_index` (and policy if parameter-scoped) **equals** the dataset publish token.
* RNG logs’ `{seed, parameter_hash}` **match** the dataset identity; a **single** `run_id` is used consistently.
* Where lineage fields are embedded in rows in any future revision, embedded values **equal** their path tokens.

**2.7 Prohibitions (fail-closed).**

* **No out-of-scope reads:** S6 must not read `world_countries`, `population_raster_2025`, `tz_world_2025a`, or any surface not listed in §2.4.
* **No assignment or count tampering:** S6 must not modify S5 site→tile assignments or any S4/S3 counts.
* **No policy invention/override:** σ parameters **must** come from `jitter_policy`; S6 must not re-fit or infer σ.
* **No inter-country order:** S6 must not encode or imply order (authority remains 1A `s3_candidate_set`).

---

# 3) Inputs & authority boundaries **(Binding)**

**3.1 Required inputs (resolve via Dataset Dictionary; Schema owns shape).**

* **`s5_site_tile_assignment`** — authoritative **site→tile** mapping (one row per site) under identity `{seed, manifest_fingerprint, parameter_hash}`.
* **`tile_index`** — **eligible tile universe** and per-tile bounds/centroid for the fixed `{parameter_hash}`.
* **`jitter_policy`** — σ rules (degrees) used to scale per-axis jitter; deterministic from policy knobs/latitude.
* **`iso3166_canonical_2024`** — FK domain for `legal_country_iso` (uppercase ISO-2).

**3.2 Sealed but **not** read by S6 (declared for boundary clarity).**

* **`s4_alloc_plan`** — per-tile integers (already satisfied by S5; **not** read here).
* **`s3_requirements`** — pair-level counts (diagnostic only; **not** required).
* **`tile_weights`** — fractional mass (S2; **not** read).
* **`outlet_catalogue`** — site stubs (seed+fingerprint; **not** read).
* **`s3_candidate_set`** — **inter-country order** authority (1A; **not** read).

**3.3 Precedence & resolution rules.**

* **Shape authority:** JSON-Schema packs (dataset + RNG events).
* **IDs→paths/partitions/sort/licence:** Dataset Dictionary.
* **Provenance/licences:** Artefact Registry.
  If Dictionary text and Schema ever differ on **shape**, **Schema wins**. **No literal paths** in code; all IO resolves via the Dictionary.

**3.4 Authority boundaries (what S6 MUST / MUST NOT do).**

* **Assignments:** S6 **MUST** respect S5 site→tile; **MUST NOT** alter tiles or counts.
* **Universe/bounds:** S6 **MUST** use `tile_index` as the **only** source for per-tile centroid and `[min,max]` bounds; offsets **MUST NOT** place a site outside these bounds.
* **Policy:** σ parameters **MUST** come from `jitter_policy`; S6 **MUST NOT** invent/re-fit σ.
* **RNG envelope:** S6 **MUST** express randomness via substream **`in_cell_jitter`** with the documented budget (**two** uniforms per site; `draws="2"`).
* **Order boundary:** S6 **MUST NOT** encode or imply inter-country order (authority remains 1A `s3_candidate_set`).
* **Gate reliance:** S6 **relies on** the fingerprint-scoped S0 receipt; it **does not** re-hash 1A’s bundle.

**3.5 Identities bound for this state.**

* **Dataset identity:** exactly one `{seed, manifest_fingerprint, parameter_hash}` for all reads/writes in the publish.
* **RNG logs identity:** `{seed, parameter_hash, run_id}` (single `run_id` for the publish).

**3.6 Prohibited surfaces (fail-closed).**
S6 **MUST NOT** read `world_countries`, `population_raster_2025`, `tz_world_2025a`, or any surface not listed in §3.1 for jitter logic. Evidence of such reads is a validation failure.

**3.7 Path↔embed equality (where embedded).**
If lineage fields are embedded in rows (now or in future revisions), their values **MUST equal** the corresponding path tokens. RNG events **MUST** carry the matching `{seed, parameter_hash}` and the single `run_id`.

---

# 4) Outputs (datasets) & identity **(Binding)**

**4.1 Dataset & canonical anchors.**

* **Dataset ID:** `s6_site_jitter`
* **Schema (sole shape authority):** `schemas.1B.yaml#/plan/s6_site_jitter` *(canonical anchor; this spec does not restate columns/keys).*
* **RNG event stream (authority):** `schemas.layer1.yaml#/rng/events/in_cell_jitter` *(layer RNG envelope; substream `in_cell_jitter`).*

**4.2 Path family, partitions, writer sort & format (Dictionary law).**
Resolve via the **Dataset Dictionary** only (no literal paths).

```
data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
```

* **Partitions:** `[seed, fingerprint, parameter_hash]` (one publish per identity; write-once).
* **Writer sort:** `[merchant_id, legal_country_iso, site_order]` (stable merge order; file order non-authoritative).
* **Format:** `parquet`.

**4.3 RNG logs (path family & partitions).**
Per-site jitter RNG events are published under the layer RNG log space:

```
logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Partitions:** `[seed, parameter_hash, run_id]` (no fingerprint in RNG logs).
* **Envelope:** events must validate against the `in_cell_jitter` event anchor (module/substream/blocks/draws/trace as defined there).
* **Budget (binding):** exactly **one** jitter event **per site**, with **`draws="2"`** (two uniforms → Box–Muller).

**4.4 Row admission (dataset).**
Emit **exactly one** row per outlet stub `(merchant_id, legal_country_iso, site_order)` containing the **effective in-tile deltas** after boundary handling. No duplicates; no omissions; no zero/placeholder rows.

**4.5 Immutability & atomic publish.**
Write-once per `{seed, manifest_fingerprint, parameter_hash}`. Re-publishing to the same identity **must be byte-identical**. Publish via stage → fsync → single atomic move; file order is **non-authoritative**.

**4.6 Identity & lineage constraints.**

* **Dataset identity:** `{seed, manifest_fingerprint, parameter_hash}` for all reads/writes.
* **RNG logs identity:** `{seed, parameter_hash, run_id}`; a single `run_id` is minted and used consistently for the publish.
* **Parity:** `{seed}` used to read `s5_site_tile_assignment` and `{parameter_hash}` used to read `tile_index` **equal** the dataset publish tokens.
* **Path↔embed:** if lineage fields are embedded in rows now or in a future revision, values **must equal** the corresponding path tokens.

**4.7 Licence, retention, PII (Dictionary authority).**
Licence/retention/PII for `s6_site_jitter` are governed by its Dictionary entry. Writers **must not** override these at write time. (RNG logs follow the layer’s log retention policy.)

**4.8 Forward consumers (non-authoritative note).**
Produced by **1B.S6**; consumed by **S7** (coordinate synthesis/egress shaping). Inter-country order remains external (authority = **1A `s3_candidate_set`**).

---

# 5) Dataset shapes & schema anchors **(Binding)**

**5.1 Canonical anchors (single sources of truth).**

* **Dataset:** `schemas.1B.yaml#/plan/s6_site_jitter`
* **RNG events:** `schemas.layer1.yaml#/rng/events/in_cell_jitter`
  This spec **does not** restate columns, domains, PK/partition/sort, or event fields. Those live **only** in the schema packs, which **must** include these anchors before any S6 publish.

**5.2 Ownership & precedence.**

* **Shape authority:** the schema packs above (dataset + RNG envelope).
* **IDs→paths/partitions/writer policy/licence:** Dataset Dictionary.
* **Provenance/licences:** Artefact Registry.
  If Dictionary text and Schema ever differ on **shape**, **Schema wins**.

**5.3 Validation obligation.**

* The `s6_site_jitter` dataset **must validate** against `#/plan/s6_site_jitter` (including PK/partition/sort and any FKs).
* All `in_cell_jitter` RNG events **must validate** against `#/rng/events/in_cell_jitter` (envelope + substream constraints). Any deviation is a schema-conformance failure (see §8/§9).

**5.4 Columns-strict posture.**
The dataset anchor enforces a **strict column set** (no undeclared columns). The RNG event anchor enforces its envelope fields (module/substream/blocks/draws/trace). This document **relies on** those anchors and **does not duplicate** them here.

**5.5 Compatibility (schema-owned).**
Any change to dataset keys/columns/partitioning/sort, RNG substream/envelope fields, or FK targets is **MAJOR** per §12. Additive, non-semantic observability outside the dataset partition is **MINOR**. Editorial wording is **PATCH**.

**5.6 Cross-file `$ref` hygiene.**
Any cross-schema references (e.g., FK to `tile_index`, ingress ISO surface, RNG `$defs`) are declared **in the schema packs**. This spec references **only** the canonical anchors in §5.1.

---

# 6) Deterministic algorithm (with RNG) **(Binding)**

**6.1 Fix identity & gate (once).**
a) Fix **`{seed, manifest_fingerprint, parameter_hash}`** for the entire publish.
b) Validate the **S0 receipt** for `manifest_fingerprint` (schema-valid; **No PASS → No read**). S6 **relies on** this receipt and **does not** re-hash 1A’s bundle.
c) Resolve all inputs/outputs strictly via the **Dataset Dictionary** (no literal paths).

**6.2 Locate inputs (identity parity before compute).**
a) Read **`s5_site_tile_assignment`** under `…/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`.
b) Read **`tile_index`** under `…/parameter_hash={parameter_hash}/`.
c) Read **`jitter_policy`** (policy/config surface).
d) Assert **parity** before any emit: the `{seed}` used for (a) and the `{parameter_hash}` used for (b,c) **equal** the intended publish tokens.

**6.3 Per-site frame (authoritative inputs).**
For each site row `(merchant_id, legal_country_iso, site_order, tile_id)` from S5:
a) From **`tile_index`**, fetch the tile’s **centroid** `(centroid_lat_deg, centroid_lon_deg)` and **bounds** `([min_lat_deg,max_lat_deg], [min_lon_deg,max_lon_deg])`.
b) From **`jitter_policy`**, deterministically derive **σ parameters in degrees**: `σ_lat_deg`, `σ_lon_deg` (function of latitude band and/or policy knobs).

**6.4 RNG events (budget is binding).**
For each site, emit **exactly one** RNG event on substream **`in_cell_jitter`** with **`draws="2"`**, producing two uniforms `u1,u2 ∈ (0,1)` under the layer RNG envelope.

* Logs path: `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.
* A single **`run_id`** is minted at job start and used for **all** S6 events in this publish.

**6.5 Box–Muller transform (deterministic).**
From `u1,u2`, compute two independent standard normals `(Z_lat, Z_lon)` via Box–Muller.

* Propose deltas (degrees): `δ_lat = σ_lat_deg · Z_lat`, `δ_lon = σ_lon_deg · Z_lon`.

**6.6 Boundary law (no extra RNG).**
Compute tentative coordinates:
`lat′ = centroid_lat_deg + δ_lat`, `lon′ = centroid_lon_deg + δ_lon`.
Clamp once (no resample) to tile bounds:
`lat′ := min(max(lat′, min_lat_deg), max_lat_deg)`;
`lon′ := min(max(lon′, min_lon_deg), max_lon_deg)`.
Define **effective deltas**:
`δ_lat_eff = lat′ − centroid_lat_deg`, `δ_lon_eff = lon′ − centroid_lon_deg`.

**6.7 Emit outputs.**
a) **Dataset row (one per site):** write `(merchant_id, legal_country_iso, site_order, …)` with the **effective** in-tile jitter fields as specified by the dataset anchor.
b) **Writer sort:** output rows in non-decreasing `[merchant_id, legal_country_iso, site_order]`; **file order is non-authoritative**.
c) **Event:** the corresponding `in_cell_jitter` RNG event (from §6.4) is the **only** event for this site.

**6.8 Integrity & invariants (must hold per site).**
a) **Bounds:** `(lat′, lon′)` (centroid ± effective deltas) lies **inside** the tile’s min/max rectangle.
b) **Completeness:** exactly **one** dataset row and **one** RNG event per site.
c) **Policy use:** `σ_lat_deg, σ_lon_deg` originate from `jitter_policy` (no invention/re-fit).

**6.9 Determinism & identity discipline.**
Given the same sealed inputs and identity **`{seed, manifest_fingerprint, parameter_hash}`**, S6 must reproduce **byte-identical** dataset output and **identical RNG events** (content).

* Publish dataset under `…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`.
* **Write-once:** re-publishing to the same identity must be byte-identical (stage → fsync → single atomic move).

**6.10 Prohibitions (fail-closed).**
a) Do **not** read surfaces outside §2.4.
b) Do **not** alter S5 assignments, S4/S3 counts, or `tile_index` bounds.
c) Do **not** exceed/underspend the RNG budget (`draws="2"` per site; one event per site).
d) Do **not** encode or imply inter-country order (authority remains 1A `s3_candidate_set`).

---

# 7) Identity, partitions, ordering & merge discipline **(Binding)**

**7.1 Identity tokens (one triple per publish).**

* **Dataset identity:** exactly **`{seed, manifest_fingerprint, parameter_hash}`** for the entire S6 publish. Mixing identities within a publish is **forbidden**.
* **RNG logs identity:** **`{seed, parameter_hash, run_id}`**. A single **`run_id`** is minted at job start and used for **all** S6 jitter events.

**7.2 Path families & partitions (resolve via Dataset Dictionary; no literal paths).**

* **Dataset path family:**
  `data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  **Partitions:** `[seed, fingerprint, parameter_hash]` · **Format:** parquet · **Write-once** (no appends/compaction).
* **RNG logs path family:**
  `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  **Partitions:** `[seed, parameter_hash, run_id]` · **Append-only during job**, then **frozen** on success.

**7.3 Writer sort & file-order posture.**

* **Dataset writer sort:** `[merchant_id, legal_country_iso, site_order]` (stable merge order; file order **non-authoritative**).
* **RNG logs:** no row-order guarantee; validators rely on event **shape/identity/budget**, not file order.

**7.4 Identity-coherence checks (must hold before publish).**

* **Receipt parity (fingerprint):** dataset `fingerprint` equals the S0 receipt `manifest_fingerprint`.
* **Seed parity (S5 scope):** dataset `seed` equals the `seed` used to read **`s5_site_tile_assignment`**; RNG logs `seed` equals dataset `seed`.
* **Parameter parity (S1/S2 scope):** dataset `parameter_hash` equals the value used to read **`tile_index`** (and `jitter_policy` if parameter-scoped); RNG logs `parameter_hash` equals dataset `parameter_hash`.
* **Single run_id:** all S6 RNG events for this publish use the **same `run_id`**.
* **Path↔embed equality:** if lineage fields are embedded in rows in this or a future revision, embedded values **must equal** their path tokens.

**7.5 Parallelism & determinism.**
Parallel materialisation is allowed (e.g., sharding by `merchant_id` or by `(merchant_id, legal_country_iso)`), **provided** the final dataset results from a **stable merge** ordered by `[merchant_id, legal_country_iso, site_order]` and outcomes do **not** vary with worker/scheduling. RNG events may be emitted concurrently, but: **(a)** all use the single `run_id`, **(b)** identity tokens match, **(c)** the **budget equals the number of dataset rows** (one event per site).

**7.6 Atomic publish, immutability & idempotence.**

* **Dataset:** stage → fsync → **single atomic move** into the identity partition. Re-publishing under the same `{seed, manifest_fingerprint, parameter_hash}` must be **byte-identical** or is a hard error.
* **RNG logs:** append-only within the `run_id` partition during the job; on **success**, freeze the partition (no edits/deletes). Re-running with the same sealed inputs and identity **must** reproduce the **same event set and content** (and, if your emitter is deterministic, the same bytes).

**7.7 Prohibitions (fail-closed).**

* **No mixed identities** (no mixing seeds, fingerprints, or parameter hashes within a publish).
* **No literal paths** in code; all IO resolves via the **Dataset Dictionary**.
* **No post-publish mutation** of dataset or RNG log partitions.

---

# 8) Acceptance criteria (validators) **(Binding)**

**8.1 Gate & identity (pre-write).**

* Exactly one `s0_gate_receipt_1B` exists for the target `manifest_fingerprint` and **schema-validates**; S6 relies on it (no bundle re-hash).
* **Identity parity:** publish tokens `{seed, manifest_fingerprint, parameter_hash}` **match** the tokens used to read `s5_site_tile_assignment` (seed+fingerprint+param) and `tile_index` (param).
* **Logs identity:** all `in_cell_jitter` events use the same `{seed, parameter_hash, run_id}`; exactly **one** `run_id` for the publish.
* **Fail:** `E301_NO_PASS_FLAG`, `E_RECEIPT_SCHEMA_INVALID`, `E604_TOKEN_MISMATCH`.

**8.2 Schema conformance (dataset + logs).**

* Dataset `s6_site_jitter` **validates** against `schemas.1B.yaml#/plan/s6_site_jitter` (strict columns; PK/partition/sort as the anchor).
* Every RNG event **validates** against `schemas.layer1.yaml#/rng/events/in_cell_jitter` (correct substream, envelope fields).
* **Fail:** `E603_SCHEMA_INVALID`, `E603_SCHEMA_EXTRAS`, `E606_RNG_EVENT_MISMATCH`.

**8.3 PK uniqueness & completeness (dataset).**

* No duplicate `(merchant_id, legal_country_iso, site_order)` within the identity partition.
* **Completeness vs S5:** the count of rows in `s6_site_jitter` equals the count of rows in `s5_site_tile_assignment` for the **same identity**.
* **Fail:** `E605_PK_DUPLICATE_SITE`, `E601_NO_S5_ASSIGNMENT` (if missing), or completeness treated under `E610_NONDETERMINISTIC_OUTPUT` if counts drift after re-read.

**8.4 Bounds integrity (tile universe & clamps).**

* For each site, let `(centroid_lat, centroid_lon, min/max_lat, min/max_lon)` come from `tile_index` (same `{parameter_hash}`). Using **effective deltas** in the dataset, reconstructed `(lat′, lon′)` = `(centroid ± deltas)` **lies inside** the tile’s min/max rectangle.
* **Fail:** `E607_BOUNDS_VIOLATION`.

**8.5 ISO FK domain.**

* Every `legal_country_iso` appears in `iso3166_canonical_2024` (uppercase ISO-2).
* **Fail:** `E302_FK_COUNTRY`.

**8.6 RNG budgeting (one event per site; two draws).**

* **Event budget equality:** number of `in_cell_jitter` events **equals** number of dataset rows.
* Each event has `blocks=1`, `draws="2"` and substream `in_cell_jitter`.
* **Fail:** `E606_RNG_EVENT_MISMATCH`.

**8.7 Partition, immutability & atomic publish (dataset).**

* Published under `…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`; no appends/compaction.
* Re-publishing to the same identity must be **byte-identical**; publish via stage → fsync → single atomic move.
* **Fail:** `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`.

**8.8 Writer sort (stable merge order).**

* Rows are in non-decreasing `[merchant_id, legal_country_iso, site_order]`; file order non-authoritative.
* **Fail:** `E608_UNSORTED`.

**8.9 Prohibitions (fail-closed).**

* No reads outside §2.4 (e.g., `world_countries`, `population_raster_2025`, `tz_world_2025a`).
* No changes to S5 assignments or S4/S3 counts; no σ invention/override (must come from `jitter_policy`).
* No inter-country order encoded (authority = 1A `s3_candidate_set`).
* **Fail:** `E609_DISALLOWED_READ`, `E414_WEIGHT_TAMPER`, `E312_ORDER_AUTHORITY_VIOLATION`.

**8.10 Determinism receipt (binding evidence).**

* Run report contains a composite SHA-256 over ASCII-lex ordered bytes of all files in the **dataset** partition; re-read reproduces the **same** hash. *(RNG logs are validated by budget/shape, not included in this receipt.)*
* **Fail:** `E610_NONDETERMINISTIC_OUTPUT`.

**8.11 Required run-report fields (presence).**

* Present **outside** the dataset partition: `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`, `rows_emitted`, `rng_events_emitted`, `bounds_clamped_rows`, determinism receipt `{partition_path, sha256_hex}`.
* **Fail:** `E615_RUN_REPORT_MISSING_FIELDS`.

---

# 9) Failure modes & canonical error codes **(Binding)**

> **Fail-closed posture.** On first detection of any condition below, the writer **MUST** abort the run, emit a failure record, and ensure **no partials** are visible under
> `…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
> (write-once; atomic publish). RNG logs are **append-only during the job** under
> `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/` and then **frozen** on success.

### E301_NO_PASS_FLAG — S0 gate not proven *(ABORT)*

**Trigger:** Missing/unreadable S0 receipt for `manifest_fingerprint`.
**Detection:** Receipt lookup fails (absence/unreadable).

### E_RECEIPT_SCHEMA_INVALID — S0 receipt fails schema *(ABORT)*

**Trigger:** `s0_gate_receipt_1B` does not validate against its schema.
**Detection:** JSON-Schema validation failure (shape/required keys/types).

### E601_NO_S5_ASSIGNMENT — Missing S5 input *(ABORT)*

**Trigger:** No `s5_site_tile_assignment` rows for `{seed, manifest_fingerprint, parameter_hash}`.
**Detection:** Dictionary-resolved path empty/unreadable for that identity.

### E602_POLICY_MISSING_OR_INVALID — Jitter policy missing/invalid *(ABORT)*

**Trigger:** `jitter_policy` absent or fails its schema (or required fields missing).
**Detection:** Policy presence + schema validation failure.

### E603_SCHEMA_INVALID — Dataset shape/keys invalid *(ABORT)*

**Variant:** **E603_SCHEMA_EXTRAS** — undeclared column(s) present.
**Trigger:** `s6_site_jitter` fails its canonical schema anchor (columns/PK/partition/sort).
**Detection:** JSON-Schema validation failure.

### E604_TOKEN_MISMATCH — Path↔identity inequality *(ABORT)*

**Trigger:** Any publish token `{seed|fingerprint|parameter_hash}` differs from tokens used to read inputs (S5/S1/policy), or embedded lineage (where present) ≠ path tokens.
**Detection:** Identity parity checks; path↔embed equality where embedded.

### E605_PK_DUPLICATE_SITE — Duplicate site key *(ABORT)*

**Trigger:** Duplicate `(merchant_id, legal_country_iso, site_order)` within the identity partition.
**Detection:** PK uniqueness check over `s6_site_jitter`.

### E606_RNG_EVENT_MISMATCH — RNG envelope/budget invalid *(ABORT)*

**Trigger (any):**
• Event fails the `in_cell_jitter` RNG anchor (envelope/substream/fields).
• Substream ≠ `in_cell_jitter`.
• **Budget mismatch:** number of events ≠ number of dataset rows.
• Wrong `draws`/`blocks` (expected `blocks=1`, `draws="2"`).
• Identity mismatch on events: `{seed, parameter_hash}` don’t match dataset, or multiple `run_id`s in one publish.
**Detection:** Validate all events; count-match events ↔ dataset rows; check identities and single-`run_id` use.

### E607_BOUNDS_VIOLATION — Effective deltas escape tile bounds *(ABORT)*

**Trigger:** For any site, reconstructed `(lat′,lon′) = (centroid ± effective deltas)` lies **outside** the tile’s `[min/max_lat, min/max_lon]`.
**Detection:** Bounds check vs `tile_index` for the same `{parameter_hash}`.

### E302_FK_COUNTRY — ISO FK violation *(ABORT)*

**Trigger:** `legal_country_iso` not present in `iso3166_canonical_2024` (uppercase ISO-2).
**Detection:** FK domain check.

### E608_UNSORTED — Writer sort violated *(ABORT)*

**Trigger:** Rows not in non-decreasing `[merchant_id, legal_country_iso, site_order]`.
**Detection:** Sort-order validator.

### E609_DISALLOWED_READ — Out-of-scope surface read *(ABORT)*

**Trigger:** S6 reads any surface not listed in §2.4 (e.g., `world_countries`, `population_raster_2025`, `tz_world_2025a`).
**Detection:** Access audit / job IO tracing.

### E610_NONDETERMINISTIC_OUTPUT — Re-run hash differs *(ABORT)*

**Trigger:** Determinism receipt over the **dataset** partition does not reproduce on clean re-read.
**Detection:** Composite SHA-256 mismatch (ASCII-lex file order).

### E312_ORDER_AUTHORITY_VIOLATION — Order implied/encoded *(ABORT)*

**Trigger:** Output encodes or implies **inter-country order** (authority is 1A `s3_candidate_set`).
**Detection:** Presence of order fields/cross-country ordering derivations.

### E414_WEIGHT_TAMPER — Counts/weights/policy tampered *(ABORT)*
**Trigger:** S6 attempts to alter S5 site→tile assignments, any S4/S3 counts, or σ parameters outside `jitter_policy`.
**Detection:** Compare produced rows against S5 for identity; verify σ values originate from `jitter_policy`; any re-scaling/re-fit/tamper ⇒ fail.

### E615_RUN_REPORT_MISSING_FIELDS — Required run-report fields missing *(ABORT)*
**Trigger:** One or more required fields from §10.2 absent (e.g., `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`, `rows_emitted`, `rng_events_emitted`, `bounds_clamped_rows`, or determinism receipt).
**Detection:** Run-report presence/shape check (outside the dataset partition).

### E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL — Overwrite attempt *(ABORT)*

**Trigger:** A partition for `{seed, manifest_fingerprint, parameter_hash}` already exists with **different bytes**.
**Detection:** Byte comparison before atomic publish; reject non-identical writes.

## 9.1 Failure handling *(normative)*

* **Abort semantics:** Stop the run; **no** files promoted under the live dataset partition unless all validators PASS. Use stage → fsync → **single atomic move** only after PASS.
* **Failure record (outside the dataset partition):** `{code, scope ∈ {run,pair,site}, reason, seed, manifest_fingerprint, parameter_hash, run_id}`; include `{merchant_id, legal_country_iso, site_order}` when applicable.
* **RNG logs on failure:** Log partitions for the active `run_id` may remain as evidence; they are **not** acceptance artefacts.
* **Multi-error policy:** Multiple failures **may** be recorded; acceptance remains **failed**.

## 9.2 Code space & stability *(normative)*

* **Reserved (this state):** `E601`–`E610` as defined above, plus reused cross-state codes `E301_*`, `E302`, `E312_*`, and `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`.
* **SemVer impact:** Tightening triggers that cannot flip prior accepted reference runs = **MINOR**; changes that can flip outcomes or alter identities/partitioning = **MAJOR**.

---

# 10) Observability & run-report **(Binding)**

> Observability artefacts are **required** and **retrievable** by validators but do **not** alter the semantics of `s6_site_jitter`. They **must not** be written inside the dataset partition. Posture mirrors S3–S5.

**10.1 Deliverables (outside the dataset partition; binding for presence)**
An accepted S6 run **MUST** expose, outside
`…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`:

* **S6 run report** — single machine-readable JSON object (fields in §10.2).
* **Determinism receipt** — composite SHA-256 over the produced **dataset partition files only** (recipe in §10.4).
* *(Optional, recommended)* **Summaries** for auditor convenience (formats in §10.3). Presence of the run report + receipt is **binding**; summaries are optional.

**10.2 S6 run report — required fields (binding for presence)**
The run report **MUST** include at least:

* `seed` — lineage token for the run identity.
* `manifest_fingerprint` — fingerprint proven by S0.
* `parameter_hash` — parameter identity used for S1/S2 surfaces.
* `run_id` — RNG log stream identifier minted at job start (used by all `in_cell_jitter` events).
* `rows_emitted` — total rows written to `s6_site_jitter`.
* `rng_events_emitted` — total `in_cell_jitter` events written for this publish.
* `bounds_clamped_rows` — count of rows where clamping to tile bounds occurred (non-semantic; for visibility).
* `determinism_receipt` — object per §10.4 `{ partition_path, sha256_hex }`.

**10.3 Summaries (optional; recommended formats)**

* **Clamp distribution:** histogram or percentiles of `|δ_lat_eff|`, `|δ_lon_eff|`; per-country clamp rates.
* **RNG budget summary:** `{ expected_events: rows_emitted, actual_events: rng_events_emitted }` (expected = actual on acceptance).
* **Health counters:** `fk_country_violations`, `bounds_violations`, `dup_sites` — all expected **0** on acceptance.
  (If provided, summaries **must** be retrievable by validators.)

**10.4 Determinism receipt — composite hash (method is normative)**
Compute a **composite SHA-256** over the **dataset partition files only**:

1. List all files under
   `…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
   as **relative paths**, **ASCII-lex sort** them.
2. Concatenate raw bytes in that order; compute SHA-256; encode as lowercase hex64.
3. Store `{ "partition_path": "<path>", "sha256_hex": "<hex64>" }` as `determinism_receipt` in the run report.
   *(RNG logs are **not** included in this receipt; they are validated by event-budget and envelope checks.)*

**10.5 Packaging, location & retention (binding)**

* Place run report, determinism receipt, and any summaries **outside** the dataset partition (control-plane artefacts or job attachments/logs).
* Retain for **≥ 30 days** (or programme policy).
* All paths for evidence retrieval **must** resolve via the Dataset Dictionary (no literal paths).

**10.6 Failure event schema (binding for presence on failure)**
On any §9 failure, emit a structured event (outside the dataset partition):

* `event: "S6_ERROR"`, `code: <one of §9>`, `at: <RFC-3339 UTC>`,
  **`seed`**, **`manifest_fingerprint`**, **`parameter_hash`**, **`run_id`**; optionally `merchant_id`, `legal_country_iso`, `site_order`.
  RNG-log partitions for the active `run_id` may remain as evidence; they are **not** acceptance artefacts.

**10.7 Auditor checklist (retrievability expectations)**

* Run report present with all **required fields** in §10.2.
* Determinism receipt present and recomputable to the **same** hash.
* `rng_events_emitted == rows_emitted` (exactly one `in_cell_jitter` event per dataset row), all events under a **single** `run_id`, identities match.
* Evidence stored **outside** the dataset partition; retention satisfied; paths resolve via the Dictionary.

---

# 11) Performance & scalability *(Informative)*

**11.1 Workload model.**
Process **site-by-site** from `s5_site_tile_assignment` (triple identity). For each site, fetch the tile’s bounds/centroid from `tile_index`, derive σ from `jitter_policy`, draw **two** uniforms (RNG envelope), do Box–Muller, clamp once, emit one dataset row + one RNG event. No cross-product materialisation; no joins beyond key lookups.

**11.2 Asymptotics.**
Let **N** = rows in `s5_site_tile_assignment`.

* **Time:** `O(N)` (constant work per site).
* **Memory:** `O(1)` per site, plus small caches for tile metadata/σ (see §11.3).
* **Writes:** exactly **N** dataset rows and **N** RNG events.

**11.3 Data-access & caching.**

* Cache a **tile record** map keyed by `(legal_country_iso, tile_id)` → `{centroid, bounds}`; warm per country; LRU-evict to a fixed ceiling.
* Cache **policy lookups** keyed by latitude band (or policy key) → `{σ_lat_deg, σ_lon_deg}`.
* Prefer **read-through** caching from `tile_index`; avoid re-reading the same tile bounds within a shard.

**11.4 RNG throughput & budgeting.**

* Emit **exactly one** `in_cell_jitter` event **per site** with `draws="2"`.
* Batch events in small buffers and **flush frequently** to keep FD/memory low; verify **event_count == rows_emitted** per shard and at job end.
* All shards must use the **single** `run_id` for the publish.

**11.5 Parallelism (deterministic).**

* Shard by `merchant_id` or by `(merchant_id, legal_country_iso)`; each shard reads S5 rows, consults caches, draws RNG, and writes outputs.
* Final dataset is a **stable merge** ordered by `[merchant_id, legal_country_iso, site_order]`; outcomes must not depend on worker layout.
* RNG logs may be written from multiple workers; identity must match and **budget must equal** dataset rows.

**11.6 I/O posture.**

* Single pass over `s5_site_tile_assignment`; random-access or streaming reads from `tile_index` satisfied by the cache.
* Aim for **≤ 1.25×** amplification per surface (bytes read vs on-disk).
* Write **one** dataset partition per identity; RNG events are append-only under `{seed, parameter_hash, run_id}`.

**11.7 Chunking & back-pressure.**

* Chunk by **merchant ranges** sized so a shard’s tile/policy caches fit comfortably in memory.
* Apply back-pressure to the RNG-event sink and dataset writer to maintain steady throughput without breaching resource caps.

**11.8 Resource envelope (targets).**

* Per worker: **RSS ≤ 1 GiB**, temp disk **≤ 2 GiB**, **≤ 256** open files.
* Output as compressed columnar (Parquet) with moderate row-groups (e.g., ~100k–250k rows) to balance scan efficiency and memory.

**11.9 Fast-fail preflights (optional but helpful).**

* Verify **S5 presence** for the identity and **non-zero** row count before spinning workers.
* Pre-scan `tile_index` keys referenced by S5 rows (per country) and fail early if any are missing.
* Validate `jitter_policy` once up-front (schema + required fields) to avoid mid-run aborts.

**11.10 Observability counters (non-binding).**
Record in the run report: `rows_emitted`, `rng_events_emitted`, `bounds_clamped_rows`, `bytes_read_{s5,index,policy}`, `wall_clock_seconds_total`, `cpu_seconds_total`, `workers_used`, `max_worker_rss_bytes`, `open_files_peak`. These aid PAT/replays without affecting acceptance.

**11.11 Environment tiers.**

* **DEV:** tiny, fixed subset (few merchants/countries) to validate envelope and clamping.
* **TEST:** same code path as PROD on a reproducible slice; enforce all validators.
* **PROD:** full scale with determinism receipt and complete validator suite.

---

# 12) Change control & compatibility **(Binding)**

**12.1 SemVer ground rules.**
This state follows **MAJOR.MINOR.PATCH**.

* **MAJOR** — any change that can make previously conformant S6 outputs/logs **invalid or different** for the same sealed inputs and identity, or that requires consumer changes.
* **MINOR** — strictly backward-compatible tightening/additions that do **not** flip accepted reference runs from PASS→FAIL.
* **PATCH** — editorial only (no behaviour change).

**12.2 What requires a MAJOR bump (breaking).**

* **Dataset contract (`s6_site_jitter`)**: PK, column set/types, `columns_strict` posture, **partition keys** (`[seed, manifest_fingerprint, parameter_hash]`), **writer sort** (`[merchant_id, legal_country_iso, site_order]`), or **path family**.
* **RNG event contract (`in_cell_jitter`)**: substream name, envelope fields (module/substream/blocks/draws/trace), identity/partitioning (`[seed, parameter_hash, run_id]`).
* **RNG budgeting semantics**: changing “**one event per site** with **`draws="2"`**”.
* **Boundary-handling law**: replacing “single clamp, no resample” with any other method.
* **Policy interface**: altering how `jitter_policy` supplies/derives σ (e.g., units, required keys, or mapping from latitude bands).
* **Authority/precedence model**: changing that **Schema owns shape**, **Dictionary** owns IDs→paths/partitions/sort/licence, **Registry** records provenance/licences.
* **Gate/lineage rules**: removing reliance on S0 receipt, or changing path↔embed equality rules.
* **Inputs/identity set**: adding/removing required inputs or altering the identity tokens for dataset (`{seed, manifest_fingerprint, parameter_hash}`) or logs (`{seed, parameter_hash, run_id}`).

**12.3 What qualifies as MINOR (backward-compatible).**

* Adding **non-semantic** fields to the run-report/summaries (outside the dataset partition).
* Tightening validators proven not to flip previously accepted **reference** runs (e.g., clearer diagnostics, extra checks that only catch invalid publishes).
* Registry/Dictionary **writer-policy** refinements that leave value semantics unchanged (compression, row-group sizing, file layout notes).

**12.4 What is PATCH (non-behavioural).**

* Wording fixes, cross-reference repairs, examples/figures, or clarifications that **do not** change schemas, anchors, identities, acceptance rules, RNG budgeting, boundary law, or failure codes.

**12.5 Compatibility window (assumed upstream stability).**
Within S6 **v1.***, these remain stable on their **v1.*** lines:

* **S5** `s5_site_tile_assignment` (dataset identity = `[seed, manifest_fingerprint, parameter_hash]`; authoritative site→tile mapping).
* **S1/S2** `tile_index`/`tile_weights` (parameter-scoped shapes/semantics).
* **Layer RNG envelope** (common defs used by `in_cell_jitter`).
  If any of the above bump **MAJOR** or move anchors/IDs materially, S6 must be **re-ratified** and bump **MAJOR** accordingly.

**12.6 Migration & deprecation.**
On a MAJOR change:
a) Freeze the old S6 spec/version and anchors;
b) Introduce a **new dataset anchor** (e.g., `#/plan/s6_site_jitter_v2`) and, if shape/paths change, a **new Dictionary ID**;
c) Introduce a **new RNG event anchor** if the event contract changes;
d) Document exact diffs and a cut-over plan;
e) Do **not** rely on Dictionary aliases to silently bridge breaking ID/path changes—consumers must adopt the new IDs/anchors explicitly.

**12.7 Lineage tokens vs SemVer.**
`seed`, `manifest_fingerprint`, `parameter_hash`, and `run_id` are **orthogonal** to SemVer. They change with governed inputs/parameters or job execution, producing new partitions/streams **without implying** a spec change. Any renaming, merging/splitting, or removal of these tokens is **MAJOR**.

**12.8 Consumer compatibility covenant (within v1.*).**
For S6 **v1.***:

* Dataset identity **=`[seed, manifest_fingerprint, parameter_hash]`**; RNG logs identity **=`[seed, parameter_hash, run_id]`**.
* Exactly **one** dataset row **per site** and exactly **one** `in_cell_jitter` event **per site** with **`draws="2"`**.
* **Boundary law**: single clamp to tile bounds; no resample.
* **Policy use**: σ comes from `jitter_policy`; no re-fit/invention.
* Writers honour **writer sort**, **write-once immutability**, and **path↔embed equality** (where embedded).
* No inter-country order encoded; order authority remains with **1A**.

**12.9 Ratification record.**
Record for each release: `semver`, `effective_date`, ratifiers, code commit (and optional SHA-256 of this file). Keep a link to the prior MAJOR’s frozen copy.

---

# Appendix A — Symbols & notational conventions *(Informative)*

**A.1 Identity & lineage tokens**

* **`seed`** — Unsigned 64-bit master seed for the run; scopes S3–S6 datasets and RNG logs.
* **`manifest_fingerprint`** — Lowercase **hex64** SHA-256 proving the S0 gate; used in dataset paths (not RNG logs).
* **`parameter_hash`** — Lowercase **hex64** SHA-256 of the governed **parameter bundle**; scopes S1/S2 tables and S3–S6 datasets.
* **`run_id`** — Lowercase **hex** identifier for the S6 RNG event stream; **one per S6 publish**.

**A.2 Dataset & stream IDs referenced in S6**

* **`s5_site_tile_assignment`** — Site→tile mapping (one row per site) under identity **`[seed, manifest_fingerprint, parameter_hash]`**.
* **`s6_site_jitter`** — *(This state’s dataset)* one row per site with **effective** in-tile jitter deltas under identity **`[seed, manifest_fingerprint, parameter_hash]`**.
* **`tile_index`** — Eligible tile universe and per-tile centroid/bounds for the fixed **`parameter_hash`**.
* **`in_cell_jitter`** — RNG **substream** name under the layer RNG envelope for S6 jitter draws (logs are partitioned by **`[seed, parameter_hash, run_id]`**).

**A.3 Entities & keys**

* **Pair** — `(merchant_id, legal_country_iso)`.
* **Site key (dataset PK columns)** — `(merchant_id, legal_country_iso, site_order)`.
* **Tile key** — `(legal_country_iso, tile_id)`; must exist in `tile_index` for the same `{parameter_hash}`.

**A.4 Quantities & symbols used in S6**

* **`centroid_lat_deg`, `centroid_lon_deg`** — Tile centroid (degrees).
* **`min_lat_deg`, `max_lat_deg`, `min_lon_deg`, `max_lon_deg`** — Tile bounding rectangle (degrees).
* **`σ_lat_deg`, `σ_lon_deg`** — Policy-provided standard-deviation scales (degrees) for latitude/longitude jitter.
* **`u1`, `u2`** — Two independent uniforms in **(0,1)** drawn per site (substream `in_cell_jitter`).
* **`Z_lat`, `Z_lon`** — Independent standard normals from **Box–Muller** using `(u1,u2)`.
* **`δ_lat`, `δ_lon`** — **Proposed** jitter deltas in degrees: `δ_lat = σ_lat_deg · Z_lat`, `δ_lon = σ_lon_deg · Z_lon`.
* **`lat′`, `lon′`** — Tentative coordinates: `centroid ± δ`; **clamped once** to tile bounds (no resample).
* **`δ_lat_eff`, `δ_lon_eff`** — **Effective** jitter deltas after clamping: `lat′ − centroid_lat_deg`, `lon′ − centroid_lon_deg`.

**A.5 Laws repeatedly referenced**

* **Gate law** — Reads rely on the S0 receipt for `manifest_fingerprint` (**No PASS → No read**).
* **Identity parity** — Dataset identity **`[seed, manifest_fingerprint, parameter_hash]`** matches tokens used to read inputs; RNG logs use **`[seed, parameter_hash, run_id]`** with a single `run_id`.
* **RNG budget** — **Exactly one** `in_cell_jitter` event **per site**, with **`draws="2"`** (two uniforms → Box–Muller).
* **Bounds integrity** — `(centroid ± effective deltas)` **must lie inside** the tile’s `[min/max_lat, min/max_lon]`.
* **Resolution & shape** — IO resolves via the **Dataset Dictionary** (no literal paths). **JSON-Schema** is the **sole shape authority** for both dataset and RNG events.
* **Writer discipline** — Writer sort is binding; file order is **non-authoritative**. Publish is **write-once** with an atomic move.
* **Determinism receipt** — SHA-256 over ASCII-lex ordered dataset files proves byte-stability on re-read.

**A.6 Abbreviations**

* **PK** — Primary key (within an identity partition).
* **FK** — Foreign key.
* **PASS/ABORT** — Gate or validator outcome.
* **RNG** — Random number generation (here: layer envelope, substream `in_cell_jitter`).
* **σ** — Standard deviation scale (degrees) from `jitter_policy`.

---

# Appendix B — Worked example *(Informative)*

This miniature walk-through shows S6’s jitter workflow, including RNG budgeting, Box–Muller, clamping, and what validators will check. Numbers are illustrative but consistent with the rules.

---

## B.1 Identity & inputs

**Identity (this publish):**
`seed = 42` · `manifest_fingerprint = 6f…a1` · `parameter_hash = 3c…9d` · `run_id = a7e2`

**One pair & two sites from S5 (`s5_site_tile_assignment`):** `(merchant_id=101, legal_country_iso=GB)` with site orders `12` and `13`. Both sites are assigned the same tile `tile_id = 7001` (context from S5; S6 treats it read-only).

**Tile record from `tile_index` (for {parameter_hash}):**

| field                         | value             |
| ----------------------------- | ----------------- |
| `centroid_lat_deg`            | 51.5000           |
| `centroid_lon_deg`            | −0.1200           |
| `min_lat_deg` / `max_lat_deg` | 51.4800 / 51.5200 |
| `min_lon_deg` / `max_lon_deg` | −0.1500 / −0.0900 |

**Policy lookup (`jitter_policy`) for this latitude band:**

| parameter   | value (deg) |
| ----------- | ----------- |
| `σ_lat_deg` | 0.0060      |
| `σ_lon_deg` | 0.0100      |

---

## B.2 RNG draws (budget = one event per site, `draws="2"`)

RNG events are written under:
`logs/rng/events/in_cell_jitter/seed=42/parameter_hash=3c…9d/run_id=a7e2/part-*.jsonl`
Each event (one per site) consumes **two** uniforms `u1,u2 ∈ (0,1)`.

**Site 12** (example draws): `u1 = e^{-2} = 0.1353352832`, `u2 = 0.75`
**Site 13** (example draws): `u1 = e^{-8} = 0.0003354626`, `u2 ≈ 1.0×10^{-10}` *(still in (0,1))*

---

## B.3 Box–Muller → proposed deltas

Let `R = sqrt(-2 ln u1)` and `θ = 2πu2`. Then
`Z_lat = R cos θ`, `Z_lon = R sin θ` (independent `N(0,1)`).

**Site 12:**
`R = sqrt(4) = 2`, `θ = 1.5π` → `cos θ = 0`, `sin θ = −1`
`Z_lat = 0`, `Z_lon = −2`
`δ_lat = σ_lat_deg · Z_lat = 0.0060 · 0 = 0.0000`
`δ_lon = σ_lon_deg · Z_lon = 0.0100 · (−2) = −0.0200`

**Site 13:**
`R = sqrt(16) = 4`, `θ ≈ 6.283e−10` → `cos θ ≈ 1`, `sin θ ≈ 6.283e−10`
`Z_lat ≈ 4.000000000`, `Z_lon ≈ 2.513e−9`
`δ_lat = 0.0060 · 4 = +0.0240`
`δ_lon ≈ 0.0100 · 2.513e−9 = +2.513e−11` *(≈ 0)*

---

## B.4 Boundary handling (single clamp; no resample)

Compute tentative coordinates and clamp once to the tile rectangle.

**Site 12:**
`lat′ = 51.5000 + 0.0000 = 51.5000` (inside)
`lon′ = −0.1200 − 0.0200 = −0.1400` (inside)
**Effective deltas:** `δ_lat_eff = 0.0000`, `δ_lon_eff = −0.0200` *(no clamp)*

**Site 13:**
`lat′ = 51.5000 + 0.0240 = 51.5240` (**above** `max_lat=51.5200`) → **clamp** to `51.5200`
`lon′ = −0.1200 + ~0 = −0.1200` (inside)
**Effective deltas:** `δ_lat_eff = +0.0200`, `δ_lon_eff ≈ 0.0000` *(clamped on latitude)*

---

## B.5 Produced outputs

**Dataset partition (writer sort `[merchant_id, legal_country_iso, site_order]`):**
`data/layer1/1B/s6_site_jitter/seed=42/fingerprint=6f…a1/parameter_hash=3c…9d/`

| merchant_id | legal_country_iso | site_order | δ_lat_eff (deg) | δ_lon_eff (deg) | clamped?  |
|------------:|:-----------------:|-----------:|----------------:|----------------:|:---------:|
|         101 |        GB         |         12 |          0.0000 |         −0.0200 |    no     |
|         101 |        GB         |         13 |         +0.0200 |         ~0.0000 | yes (lat) |

**RNG events (one per site, `draws="2"`; same `{seed, parameter_hash, run_id}`):**
`…/in_cell_jitter/seed=42/parameter_hash=3c…9d/run_id=a7e2/…`
*(Event bodies validate the `in_cell_jitter` anchor; exact fields are owned by the schema pack.)*

---

## B.6 Validator checklist (why this passes)

* **Gate & identity:** S0 receipt present/valid; dataset identity `{seed=42, fingerprint=6f…a1, parameter_hash=3c…9d}` matches tokens used to read S5/S1/policy; all events use `{seed=42, parameter_hash=3c…9d, run_id=a7e2}`.
* **Schema conformance:** dataset validates `#/plan/s6_site_jitter`; events validate `#/rng/events/in_cell_jitter`.
* **PK uniqueness & completeness:** one row per site; counts equal S5 rows (for the identity).
* **Bounds integrity:** `(centroid ± effective deltas)` lies inside tile bounds for both rows; Site 13 shows a legal **clamp**.
* **RNG budgeting:** **2** dataset rows ↔ **2** jitter events; each has `draws="2"` and substream `in_cell_jitter`.
* **Writer & immutability:** dataset sorted by `[merchant_id, legal_country_iso, site_order]`; publish is write-once; determinism receipt computed over the dataset partition.

---