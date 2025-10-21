# State-6 — In-pixel Uniform Jitter with Point-in-Country (RNG)

# 1) Document metadata & status **(Binding)**

**State ID (canonical):** `layer1.1B.S6` — “In-pixel uniform jitter with bounded resample (point-in-country).”
**Document type:** Contractual specification (behavioural + data contracts; no code/pseudocode). Implementations resolve shapes via JSON-Schema anchors and IDs/paths via the Dictionary; Registry is provenance/notes only. 

## 1.1 Versioning (SemVer) & effective date

**Versioning scheme:** **MAJOR.MINOR.PATCH**.
**Effective date:** set on ratification (release tag governs).

**MAJOR** when any binding interface changes, including (non-exhaustive): dataset IDs or `$ref` schema anchors; partition law; RNG **event family** shape/envelope; PASS-gate semantics; lineage equality rules.  
**MINOR** for backward-compatible additions (optional diagnostics/metrics, run-report fields) or documentation notes that do not alter schemas/paths/keys. 
**PATCH** for clarifications/typos that do not change behaviour, schemas, paths, partitions, or gates. 

## 1.2 Normative language (RFC 2119/8174)

Key words **MUST/SHALL/SHOULD/MAY** are normative. Unless explicitly marked *Informative*, all clauses are **Binding**. (Matches S0/S1/S3 practice.)  

## 1.3 Sources of authority & precedence

**JSON-Schema is the single shape authority** for all inputs/outputs/logs; the **Dataset Dictionary** governs dataset IDs → path/partitions/writer policy; the **Artefact Registry** records runtime bindings/licences; this state spec binds behaviour **under** those. If Schema and Dictionary disagree on shape, **Schema wins**; implementations must not hard-code paths.  

* **Shape anchors used by S6:**
  – Data table: `schemas.1B.yaml#/plan/s6_site_jitter` (PK/partitions/writer-sort are binding). 
  – RNG events: `schemas.layer1.yaml#/rng/events/in_cell_jitter` (common envelope: `draws` dec-u128, `blocks` u64, counters, etc.). 
* **Dictionary law (IDs → paths/partitions):**
  – `s6_site_jitter` at `…/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` with ordering `[merchant_id, legal_country_iso, site_order]`. 
  – RNG log `in_cell_jitter` under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`. 

## 1.4 Compatibility window (assumed baselines)

S6 v1.* assumes the following remain on their **v1.* line**; a **MAJOR** bump in any requires S6 re-ratification:

* `schemas.layer1.yaml` (RNG envelope/events) and `schemas.1B.yaml` (S6 table).  
* `dataset_dictionary.layer1.1B.yaml` (IDs, canonical paths/partitions for S5/S6). 
* S0 gate & 1A gate model (“**No PASS → No read**”): consumers of 1A egress verify `_passed.flag` per the hashing law before S6’s upstream reads occur. 

## 1.5 Identity & lineage (binding)

* **Dataset identity (S6 table):** exactly one `{seed, manifest_fingerprint, parameter_hash}` per publish; **partition keys** are `[seed, fingerprint, parameter_hash]`, with **path token** `fingerprint=…` and **column** `manifest_fingerprint` (path↔embed equality holds wherever both appear). 
* **RNG log identity:** `{seed, parameter_hash, run_id}`; one `run_id` per publish. Envelope must include `draws` (dec-u128) and `blocks` (u64) consistent with counters. 
* **Order law:** file order is **non-authoritative**; writer sort is binding. Cross-country order is never encoded in 1B; downstreams join 1A S3 for `candidate_rank`.  

## 1.6 Scope note & alignment to the overview (informative summary)

This S6 spec **implements the overview’s S6 line**: *uniform jitter inside the chosen pixel (two-uniform family), enforce point-in-country with bounded resample on predicate failure*. (Details and acceptance tests appear in later sections.) 

## 1.7 Compatibility note vs earlier S6 draft (informative)

Earlier S6 text used **Gaussian (Box–Muller) + single clamp** and a fixed note “draws=2” in Registry prose. This spec **supersedes** that lane by adopting the overview-standard **uniform-within-pixel + bounded resample**. The event schema remains **fixed per event** (`blocks=1`, `draws="2"`); **resample is represented as multiple events (one per attempt)** rather than variable per-event budgets. Registry prose SHOULD note “≥1 events per site; last event corresponds to the accepted sample.”

---

# 2) Purpose & scope **(Binding)**

**Mission.** S6 **produces per-site, effective jitter deltas** `(delta_lat_deg, delta_lon_deg)` so that the realised point is **uniformly distributed inside the assigned raster cell (pixel)** from S5/S1 **and** lies **inside the legal country polygon**. When a sampled point fails the country predicate, S6 performs a **bounded resample**; on exhausting the cap, S6 **ABORTS**.

## 2.1 In-scope (what S6 SHALL do)

* **One row per site.** For every `(merchant_id, legal_country_iso, site_order)` from S5, S6 SHALL emit exactly one jitter row in `s6_site_jitter`.
* **Uniform-in-pixel.** S6 SHALL sample `(lon*,lat*)` **uniformly over the S1 pixel rectangle** (WGS84 degrees).
* **Point-in-country.** S6 SHALL enforce that `(lon*,lat*)` lies **inside** the polygon for `legal_country_iso` (dateline-aware).
* **Bounded resample.** On predicate failure, S6 SHALL resample within a fixed **MAX_ATTEMPTS** (≥1). If exceeded, **ABORT** this state.
* **RNG evidence.** S6 SHALL record **one RNG event per attempt** under `in_cell_jitter` (**≥1 events per site**). **Each event** MUST have `blocks = 1` and `draws = "2"` (two-uniform family). The **last** event for a site corresponds to the **accepted** sample.
* **Identity & partitions.** All outputs/logs SHALL bind to one `{seed, manifest_fingerprint, parameter_hash}`; path↔embed equality is binding; writer sort is binding; file order is non-authoritative.
* **Authority surfaces.** S6 SHALL read only sealed inputs: S5 assignment, S1 tile geometry, country polygons, and the S0 gate receipt.

## 2.2 Out of scope (what S6 SHALL NOT do)

* **No reassignment.** SHALL NOT change S5 tile choices, counts, or ordering.
* **No policy-fitting.** SHALL NOT read or derive any σ/shape policy (uniform lane ignores `jitter_policy`).
* **No new egress.** SHALL NOT publish or mutate 1B egress bundles (that packaging/flagging occurs elsewhere).
* **No alternative geometry/time semantics.** SHALL NOT use non-S1 geometry, timezone logic, or any surface not listed in §2.1.

## 2.3 Success definition (pointer)

S6 is **successful** only if the acceptance criteria in **§9** hold—uniform-in-pixel, point-in-country, FK to `tile_index`, correct RNG evidence (**≥1** events/site; **each event** has `blocks=1`, `draws="2"`; run totals reconcile with trace), path↔embed equality, and writer sort.

---

# 3) Sources of authority & invariants **(Binding)**

## 3.1 Authority stack & resolution

* **Shape authority:** All input/output/log **shapes** are owned by JSON-Schema. This spec MUST NOT restate columns/keys; implementations validate against the canonical anchors. 
* **Paths & partitions:** Dataset **IDs → path/partitions/writer-sort** resolve only via the **Dataset Dictionary** (no literal paths). 
* **Provenance/notes:** The **Artefact Registry** binds runtime notes/roles and echoes the canonical schema anchors. 

## 3.2 Authoritative inputs for S6 (sealed)

S6 SHALL read only these sealed surfaces for the fixed identity `{seed, manifest_fingerprint, parameter_hash}`:

* **S5 assignment** (`s5_site_tile_assignment`): authoritative mapping `(merchant_id, legal_country_iso, site_order) → tile_id`. Partitions `[seed, fingerprint, parameter_hash]`; writer-sort `[merchant_id, legal_country_iso, site_order]`. 
* **S1 tile geometry** (`tile_index`): pixel centroid & bounds; partition `[parameter_hash]`; writer-sort `[country_iso, tile_id]`. 
* **Country polygons** (`world_countries`): the **only** authority for the *point-in-country* predicate; dateline-aware geometry semantics are bound in S1 and inherited here. 
* **Gate receipt** (`s0_gate_receipt_1B` / 1A PASS): consumers MUST have verified **`_passed.flag`** before any upstream read (**No PASS → No read**). 

## 3.3 Identity & partitions (binding)

* **Dataset identity (S6 table):** exactly one publish per `{seed, manifest_fingerprint, parameter_hash}`; partitions are `[seed, fingerprint, parameter_hash]` (path token is `fingerprint=…`; embedded column is `manifest_fingerprint`). Writer-sort `[merchant_id, legal_country_iso, site_order]`.  
* **RNG events identity:** partitions `[seed, parameter_hash, run_id]` (no fingerprint in logs); one `run_id` per publish. 
* **Path↔embed equality:** whenever lineage fields are embedded, their values MUST byte-equal the corresponding path tokens for both datasets and logs. 

## 3.4 Foreign keys & geometry invariants

* **Country code FK:** `legal_country_iso` MUST FK to the canonical ISO-3166 surface (ingress anchor referenced by the schema). 
* **Tile FK (same parameter):** `(legal_country_iso, tile_id)` in S5/S6 MUST exist in `tile_index` for the **same** `{parameter_hash}`. The schema encodes this with an FK to `#/prep/tile_index` and an explicit `partition_keys: ['parameter_hash']` hint. 
* **Pixel bounds authority:** the rectangle used to sample uniform in-pixel candidates comes **only** from S1 `tile_index` (centroid & min/max bounds).  
* **Country predicate authority:** *point-in-country* is computed against `world_countries` (S1 rules on topology/antimeridian apply). 

## 3.5 RNG envelope & invariants

* **Envelope shape:** Every jitter event MUST validate the layer **RNG envelope** (required fields including `draws` **dec-u128 string** and `blocks` **u64**, open-interval U(0,1) deviates). 
* **Event family/partition law:** Jitter events live under `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`; **events are per attempt (≥1 per site)**; budget semantics are verified in §9.

## 3.6 Ordering & non-authoritative file semantics

* **Writer-sort is binding; file order is non-authoritative.** Datasets adhere to the Dictionary’s writer-sort; validators MUST ignore file order. 
* **Inter-country order is never encoded in 1B.** Downstreams join **1A S3 `candidate_rank`** if they need an order. 

## 3.7 Fail-closed surface access

S6 SHALL access **only** the surfaces in §3.2. Reading any unlisted spatial/time surface is a validation failure. (Geometry authority for country checks is `world_countries`; S1’s semantics govern.) 

*(All subsequent sections rely on this authority model; acceptance criteria in §9 will enforce the identity, FK, envelope, and gate invariants above.)*

---

# 4) Preconditions & sealed inputs **(Binding)**

## 4.1 Run identity is sealed before S6

S6 runs **only** under a fixed lineage tuple **`{seed, manifest_fingerprint, parameter_hash, run_id}`**. Any embedded lineage fields in rows/logs **MUST** byte-equal their path tokens (path token is `fingerprint=…`; embedded column is `manifest_fingerprint`). The S0 gate schema explicitly binds the **`fingerprint` path token ↔ `manifest_fingerprint`** value. 

## 4.2 Gate condition (must hold before any read)

**No PASS → No read.** The **S0 gate receipt** for 1B **MUST** be present and valid for this `fingerprint` before S6 reads any upstream 1B datasets. The S0 schema is fingerprint-scoped and marks this receipt as the authorisation to read 1A egress used upstream. 

## 4.3 Upstream states (existence & conformance)

The following upstream 1B datasets **MUST** already exist for **this** `{seed, fingerprint, parameter_hash}` and conform to their schema **and** Dictionary partitions/sort:

* **S5 — `s5_site_tile_assignment`**
  **Path/partitions:** `…/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  **Writer-sort:** `[merchant_id, legal_country_iso, site_order]`
  **Shape:** `schemas.1B.yaml#/plan/s5_site_tile_assignment` (FK to ISO; FK to `tile_index` with same `parameter_hash`).  

* **S1 geometry — `tile_index`** (authoritative pixel bounds/centroids)
  **Path/partitions:** `…/parameter_hash={parameter_hash}/`
  **Keys/sort:** PK `[country_iso, tile_id]`, partition `[parameter_hash]`, sort `[country_iso, tile_id]`.
  **Shape:** `schemas.1B.yaml#/prep/tile_index`. 

> **FK invariant (binding):** `(legal_country_iso, tile_id)` in S5/S6 **MUST** exist in `tile_index` for the **same** `parameter_hash` (explicit FK with `partition_keys: ['parameter_hash']` in the schema). 

## 4.4 Country geometry (point-in-country authority)

S6’s point-in-country predicate **MUST** use the **`world_countries`** surface bound in S1; using any other country shape is non-conformant per S1 acceptance. 

## 4.5 RNG envelope availability (for logging)

When S6 emits RNG events (`in_cell_jitter`), each JSONL record **MUST** validate the **layer RNG envelope** (`draws` as **decimal u128 string**, `blocks` as **u64**, counters before/after, etc.). (Identity for logs is `[seed, parameter_hash, run_id]` per Dictionary/Registry.)   

## 4.6 Resolution rule for inputs (no literal paths)

Implementations **SHALL** resolve dataset IDs → **path family, partitions, writer policy** via the **Dataset Dictionary** only (e.g., S5 and S6 table entries above); this spec does not permit hard-coded paths. 

## 4.7 Fail-closed access

S6 **SHALL** read **only** the sealed inputs enumerated here: **S5 assignment**, **S1 `tile_index`**, **`world_countries`**, and the **S0 gate receipt**. Reading any unlisted spatial/time surface is a validation failure (S1 already binds `world_countries` as the sole country-polygon authority).  

*(Downstream sections assume these preconditions; §9 will assert FK to `tile_index`, path↔embed equality, and RNG envelope correctness as acceptance tests.)*

---

# 5) Outputs (datasets/logs) & identity **(Binding)**

## 5.1 Data table — `s6_site_jitter`

**ID (Dictionary):** `s6_site_jitter` → `schemas.1B.yaml#/plan/s6_site_jitter`. **Path family:**
`data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` 

**Identity & partitions (binding).** Partitions are **`[seed, fingerprint, parameter_hash]`**. Primary key `[merchant_id, legal_country_iso, site_order]`. Writer sort `[merchant_id, legal_country_iso, site_order]`. Path token `fingerprint=…` MUST byte-equal the embedded `manifest_fingerprint` column wherever present.  

**Shape (owned by schema).** One row **per site** with effective (post-boundary) deltas:
`delta_lat_deg`, `delta_lon_deg` (bounded guards e.g. `[-1,1]`, columns_strict=true). *(The exact columns/constraints are defined by the anchor and SHALL NOT be restated here.)* 

**Writer policy & publish.** Write-once, atomic move into the live partition; file order is **non-authoritative**; retention **365 days** per Dictionary.  

## 5.2 RNG event log — `in_cell_jitter`

**ID (Dictionary):** `rng_event_in_cell_jitter` → `schemas.layer1.yaml#/rng/events/in_cell_jitter`. **Path family:**
`logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` 

**Identity & partitions (binding).** Partitions are **`[seed, parameter_hash, run_id]`**; **events are per attempt** (**≥1 per site**). Envelope fields are owned by the layer schema (e.g., `draws` as **decimal u128 string**, `blocks` as **u64**, counters before/after, etc.).

**Budget semantics (binding for S6).** For **each event (attempt)**: consume **one** Philox block → **two** uniforms; thus **`blocks = 1`**, **`draws = "2"`**. A site that resamples will therefore emit multiple events; **event_count_per_site = attempts**. 

**Writer policy & retention.** Events are append-only; file order non-authoritative; retention **30 days** per Dictionary. 

## 5.3 Path↔embed equality (binding)

Where lineage appears both in the **path** and as **embedded fields** (e.g., `manifest_fingerprint`), values MUST be byte-identical across **all** S6 outputs (dataset and logs). Violations are **FAIL** under acceptance tests. 

## 5.4 No egress mutation

S6 **does not** publish or mutate the 1B egress `site_locations`. That surface remains partitioned by `[seed, fingerprint]` and is governed elsewhere in 1B; S6 only produces the jitter dataset and its RNG events. 

## 5.5 Resolution rule (no literal paths)

Implementations SHALL resolve dataset/log IDs → **path families, partitions, writer policies** via the **Dataset Dictionary**. Schema anchors remain the sole **shape authority**.  

---

# 6) Dataset shapes & schema anchors **(Binding)**

**JSON-Schema is the sole shape authority**. This section enumerates the exact anchors S6 binds to; implementations MUST validate against these anchors and MUST NOT restate columns outside of Schema. 

## 6.1 Output data table (shape authority)

**ID → Schema:** `s6_site_jitter` → `schemas.1B.yaml#/plan/s6_site_jitter`.
This anchor fixes **PK**, **partition keys**, **writer sort**, and **columns_strict** for the S6 table. In v2.4 it is:

* **PK:** `[merchant_id, legal_country_iso, site_order]`
* **Partitions:** `[seed, fingerprint, parameter_hash]` (path token `fingerprint=…`; embedded column is `manifest_fingerprint`)
* **Writer sort:** `[merchant_id, legal_country_iso, site_order]`
* **Columns (excerpt):** `merchant_id`, `legal_country_iso` (FK to ISO ingress), `site_order`, and **effective** deltas `delta_lat_deg`, `delta_lon_deg` *(bounded guard e.g. [-1,1])*; **columns_strict: true**. 

The **Dictionary** entry for `s6_site_jitter` binds the **path family** and repeats the same **partitions/sort** (write-once, atomic move):
`data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`. 

## 6.2 RNG event stream (shape authority)

**ID → Schema:** `rng_event_in_cell_jitter` → `schemas.layer1.yaml#/rng/events/in_cell_jitter`.
This anchor inherits the **layer RNG envelope** (shared `$defs.rng_envelope`) and pins the per-event fields for S6 jitter events: `module="1B.S6.jitter"`, `substream_label="in_cell_jitter"`, `merchant_id`, `legal_country_iso`, `site_order`. **As of v1.2, the event schema constrains `blocks: 1` and `draws: "2"`** (two uniforms per event).
The **RNG envelope** defines required lineage + accounting fields (`ts_utc` RFC-3339 with exactly 6 fractional digits, `run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`, counters, `draws` as **dec-u128 string**, `blocks` as **u64**). 

The **Dictionary** entry binds the **path family** and partitions for this stream:
`logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (partitions `[seed, parameter_hash, run_id]`). 

> **Compatibility note (Binding):** S6’s behavioural spec uses **uniform in-pixel + bounded resample**; however, **the current event anchor still pins `draws="2"` and `blocks=1`**. S6 MUST comply with this shape. Any future change to log per-site resample attempts would require a **MINOR** schema/stream addition; until then, attempts are surfaced via run-report metrics, not per-event `draws`. 

## 6.3 Referenced (read-only) input anchors

S6 **reads** these shapes and inherits their constraints; this spec does not restate them:

* **S5 assignment table:** `schemas.1B.yaml#/plan/s5_site_tile_assignment` (PK `[merchant_id, legal_country_iso, site_order]`, partitions `[seed, fingerprint, parameter_hash]`, FK of `tile_id` → `prep.tile_index` with **partition hint `['parameter_hash']`** in the FK block). 
* **S1 tile geometry:** `schemas.1B.yaml#/prep/tile_index` (PK `[country_iso, tile_id]`, partition `[parameter_hash]`, writer sort `[country_iso, tile_id]`). 
* **ISO country codes (ingress):** `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` (FK target for `legal_country_iso`). *(Referenced from the 1B schema columns via FK.)* 

## 6.4 Resolution & path law (Binding)

Dataset/log **IDs → path/partitions/writer policy** resolve via the **Dataset Dictionary**; implementations MUST NOT hard-code paths. For `s6_site_jitter`, the Dictionary entry matches the schema’s partitions/sort; for `in_cell_jitter`, the Dictionary binds the `[seed, parameter_hash, run_id]` partition law under `logs/rng/events/…`.  

## 6.5 What this section does **not** assert

* **Distributional claims** (uniformity in pixel; point-in-country) and **RNG budgeting semantics** are behavioural and validated in §9; they are **not** expressible in JSON-Schema and therefore do not appear in the anchors above. *(Schema owns shape only; acceptance tests own behaviour.)* 

---

# 7) Deterministic algorithm (with RNG) **(Binding)**

## 7.1 Deterministic iteration order

S6 SHALL iterate sites **in the writer-sort** of S5:
`[merchant_id, legal_country_iso, site_order]`.
For each site key, S6 performs a bounded **attempt loop** that yields one accepted sample (or ABORTS).

## 7.2 RNG stream discipline (per attempt)

* **Substream scope.** All attempts for a site use the **`in_cell_jitter`** event family; **`substream_label` MUST equal `"in_cell_jitter"`** (site identity is carried by the event’s key fields).
* **Per-attempt budget.** Each **attempt** consumes exactly **one Philox block** → **two** open-interval uniforms `u_lon,u_lat ∈ (0,1)`; **per-event** envelope fields therefore MUST be `blocks = 1`, `draws = "2"`.
* **Counters.** Envelope counters before/after MUST reconcile with the per-attempt consumption.
  *(If multiple attempts occur, there will be multiple events for that site—each with `blocks=1`, `draws="2"`; the **final** event corresponds to the accepted sample.)*

## 7.3 Candidate generation (uniform in pixel)

Let the pixel rectangle from S1 be `[min_lon,max_lon] × [min_lat,max_lat]` (WGS84). For each attempt:

1. Map uniforms to the rectangle:

```
lon* = min_lon + u_lon · (max_lon − min_lon)
lat* = min_lat + u_lat · (max_lat − min_lat)
```

Dateline-crossing tiles SHALL be handled by the same unwrapping convention as S1 (width computed on the unwrapped interval, then normalized back to WGS84).

2. Compute **effective deltas** relative to the pixel centroid `(centroid_lon_deg, centroid_lat_deg)` from S1:

```
delta_lon_deg = lon* − centroid_lon_deg
delta_lat_deg = lat* − centroid_lat_deg
```

(*No clamp is applied; sampling is inside the pixel by construction.*)

## 7.4 Country predicate & bounded resample

* **Predicate.** `(lat*,lon*)` MUST lie **inside** the `world_countries` polygon for `legal_country_iso` (dateline-aware topology as in S1).
* **Resample rule.** If the predicate fails, **retry** with a new attempt (new event) up to **MAX_ATTEMPTS = 64**.
* **Accept.** On first success, **commit** this sample and stop attempting for the site.
* **Fail-closed.** If attempts exceed the cap with no success, **ABORT** this state with `E613_RESAMPLE_EXHAUSTED`.

## 7.5 Event emission & dataset write

For each **attempt**, emit one RNG **event** (JSONL) under
`logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`
with the layer envelope (including `draws="2"`, `blocks=1`). After an **accepted** attempt:

* **Write exactly one row** to `s6_site_jitter` for that site using the accepted `(delta_lat_deg, delta_lon_deg)`.
* **Writer sort** MUST be `[merchant_id, legal_country_iso, site_order]`.

## 7.6 Identity & determinism guarantees

* **Path↔embed equality.** Embedded `manifest_fingerprint` MUST byte-equal the `fingerprint=` path token for both dataset rows and any lineage fields in events.
* **Run stability.** Given identical `{seed, manifest_fingerprint, parameter_hash, run_id}` and identical inputs (S5, S1, country polygons), the sequence of attempts and the accepted sample for each site MUST be reproducible.
* **Concurrency.** Parallel execution MUST NOT alter per-site RNG sequencing: attempts are ordered per site; inter-site interleaving is permitted, but each site’s event sequence MUST remain in-order.

## 7.7 Prohibited behaviours (fail conditions)

* **No reassignment.** S6 MUST NOT change S5’s `(site → tile_id)` mapping.
* **No alternative geometry.** S6 MUST NOT use any country or pixel geometry other than S1 `tile_index` and `world_countries`.
* **No hidden draws.** All uniforms used MUST be evidenced by `in_cell_jitter` events (i.e., one event per attempt; no unlogged RNG).

## 7.8 Algorithm stop conditions & errors

* **Success:** one accepted sample per site → exactly one S6 row per site; ≥1 RNG event per site; last event corresponds to the accepted sample.
* **Abort:** `E613_RESAMPLE_EXHAUSTED` if no accepted sample after 64 attempts.
* **Other failures (enforced in §9):** FK violation to `tile_index`; point outside pixel or country; envelope/counter mismatch; path↔embed mismatch; unsorted write.

---

# 8) Identity, partitions, ordering & merge discipline **(Binding)**

## 8.1 Identity tokens (one tuple per publish)

* **Dataset identity:** exactly one `{seed, manifest_fingerprint, parameter_hash}` for the entire S6 publish. Mixing identities within a publish is **forbidden**. The Dictionary fixes `s6_site_jitter` under
  `data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` with partitions `[seed, fingerprint, parameter_hash]` and writer sort `[merchant_id, legal_country_iso, site_order]`. 
* **RNG logs identity:** `{seed, parameter_hash, run_id}` for the `in_cell_jitter` stream under
  `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`. *(“version: {run_id}” in Registry.)*  

## 8.2 Partition law & path families (resolve via Dictionary; no literal paths)

* **S6 dataset:** `…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  **Partitions:** `[seed, fingerprint, parameter_hash]` · **Format:** parquet · **Writer sort:** `[merchant_id, legal_country_iso, site_order]`. 
* **RNG events:** `…/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  **Partitions:** `[seed, parameter_hash, run_id]` · **Ordering:** none (append-only; file order non-authoritative). 

## 8.3 Path↔embed equality (lineage law)

Where lineage appears both in the **path** and as **embedded fields**, values MUST be byte-identical (e.g., the `fingerprint` path token equals any embedded `manifest_fingerprint`). This mirrors the S0 receipt’s binding equality rule and applies to all S6 outputs. 

## 8.4 Ordering posture (writer sort vs file order)

* **Binding writer sort:** S6 dataset publishes in `[merchant_id, legal_country_iso, site_order]`. Merge/sink stages MUST respect writer-sort determinism; **file order is non-authoritative**.  
* **Inter-country order is never encoded in 1B.** Any cross-country ordering required downstream comes **only** from **1A S3 `candidate_rank`**; S6 MUST NOT encode or imply it. 

## 8.5 Parallelism & stable merge (determinism)

Parallel materialisation (e.g., sharding by merchant or country) is **allowed** iff the final dataset is the result of a **stable merge** ordered by `[merchant_id, legal_country_iso, site_order]` and outcomes do **not** vary with worker count or scheduling. This mirrors S3/S4 discipline.  

## 8.6 Atomic publish, immutability & idempotence

Publish via **stage → fsync → single atomic move** into the identity partition. Re-publishing the same `{seed, manifest_fingerprint, parameter_hash}` MUST be **byte-identical** or is a hard error. Registry notes codify “Write-once; atomic move; file order non-authoritative.” 

## 8.7 RNG logs discipline (job lifecycle)

RNG events are **append-only during the job**, partitioned by `[seed, parameter_hash, run_id]`, then frozen on success. No row order is required; validators rely on the envelope & counts, not on file order. (This mirrors S5’s log discipline and the Dictionary’s “ordering: []” posture.)  

## 8.8 Identity-coherence checks (must hold before publish)

* **Receipt parity (fingerprint):** any S6 publish for `fingerprint=f` implies the S0 gate receipt for `f` exists and is valid. 
* **Parameter parity:** `parameter_hash` in both dataset and logs equals the `parameter_hash` used to read `tile_index`. 
* **Seed parity:** dataset `seed` equals the seed used by upstream S5; logs `seed` equals dataset `seed`. 

## 8.9 Prohibitions (fail-closed)

* **MUST NOT** mix identities within a publish (no cross-seed/fingerprint/parameter_hash contamination). 
* **MUST NOT** rely on file order for semantics (dataset or logs). 
* **MUST NOT** encode or infer inter-country order (join 1A S3 when order is required). 

---

# 9) Acceptance criteria (validators) **(Binding)**

A run **PASSES** S6 only if **all** checks below succeed. Shapes/paths/partitions come from the **Schema**/**Dictionary**/**Registry**; geometry and RNG rules come from the **overview**, **S1**, and the **layer RNG envelope**.      

---

## A601 — Row parity with S5 *(Binding)*

**Rule.** `|S6| == |S5|` and the keyset matches exactly: one S6 row for every `(merchant_id, legal_country_iso, site_order)` in S5; no missing/extra/duplicate site keys.
**Detection.** Anti-join both directions on `[merchant_id, legal_country_iso, site_order]` must be empty; check PK uniqueness on S6.
**Why.** S6 is “one row per site.” S5 writer-sort/keys/partitions are authoritative for the keyset. 

## A602 — Schema conformance *(Binding)*

**Rule.** Every S6 row validates **exactly** against `schemas.1B.yaml#/plan/s6_site_jitter` (columns_strict = true).
**Detection.** JSON-Schema validate S6 files; reject unknown/missing columns or invalid values (e.g., delta guards if present). 

## A603 — Partition & identity law *(Binding)*

**Rule.** S6 dataset lives at
`…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` with **partitions** `[seed, fingerprint, parameter_hash]`; embedded lineage (when present) byte-equals path tokens (**path↔embed equality**).
**Detection.** Derive identity from the path and compare to any embedded lineage fields (must match). 

## A604 — Writer sort *(Binding)*

**Rule.** Files are a **stable merge** in `[merchant_id, legal_country_iso, site_order]`. File order itself is **non-authoritative**; only writer sort matters.
**Detection.** Verify non-decreasing sort by the writer key inside each partition. 

## A605 — FK to `tile_index` *(Binding)*

**Rule.** For every S6 row, `(legal_country_iso, tile_id)` exists in **S1 `tile_index`** for the **same** `parameter_hash`.
**Detection.** Enforce the FK with the explicit partition hint (`partition_keys: ['parameter_hash']`) encoded in schema refs for S5/S4→`tile_index`; S6 inherits the same relation. 

## A606 — Uniform-in-pixel geometry *(Binding)*

**Rule.** Reconstruct `(lon*, lat*)` from S1 pixel bounds and the S6 **effective deltas** relative to the S1 centroid; the reconstructed point **must be inside the pixel rectangle** (dateline-aware).
**Detection.** For each row:
`lon* = centroid_lon_deg + delta_lon_deg`, `lat* = centroid_lat_deg + delta_lat_deg`; assert `min_lon ≤ lon* ≤ max_lon` and `min_lat ≤ lat* ≤ max_lat` using **S1 `tile_index`** bounds; handle ±180° unwrapping as in S1. 

## A607 — Point-in-country *(Binding)*

**Rule.** The reconstructed `(lon*, lat*)` lies **inside** the `world_countries` polygon for `legal_country_iso` (S1’s topology and antimeridian semantics apply).
**Detection.** Country PIP against the S1-governed `world_countries` surface; failure on any site is a hard FAIL. 

## A608 — RNG event coverage *(Binding)*
**Rule.** There is **at least one** `in_cell_jitter` RNG **event per site** (events are per attempt), partitioned by `[seed, parameter_hash, run_id]`; events can be joined to the site key.
**Detection.** For every site key in S6: verify **event_count ≥ 1** and joinability; verify partitions and basic envelope fields.

## A613 — Last event corresponds to accepted sample *(Binding)*
**Rule.** For each site, the **last** event (by per-site event order derived from envelope counters or append order within run_id) corresponds to the **accepted** `(delta_lat_deg, delta_lon_deg)` written to S6.
**Detection:** Order per-site events by envelope counters (`rng_counter_before/after`) and assert **monotonicity**; since the event schema does not carry uniforms or per-event deltas, validators treat “last event corresponds to the accepted sample” as an **implementation invariant**. Behavioural outcome remains enforced via **A606/A607** (inside pixel & inside country).

## A609 — RNG budget & counters *(Binding)*

**Rule.** Each `in_cell_jitter` **event** has **`blocks = 1`** and **`draws = "2"`** (two-uniform family), and 128-bit counter deltas satisfy `after − before = blocks` (u128).
**Detection.** Validate per-event envelope per the **layer RNG envelope** invariants; reject budget/counter mismatches.  

## A610 — Paths & partitions for RNG logs *(Binding)*

**Rule.** RNG events live under
`logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` with **partitions** `[seed, parameter_hash, run_id]`.
**Detection.** Validate path family and partition equality for every event file. 

## A611 — Dictionary/Schema coherence *(Binding)*

**Rule.** Dataset/log **IDs → path/partitions/sort** resolved via the **Dictionary** must match the **Schema** constraints for keys/columns; no hard-coded paths.
**Detection.** Cross-check each referenced ID against its `schema_ref`, `path`, `partitioning`, and `ordering` in the Dictionary.  

## A612 — Overview compliance (behavioural) *(Binding)*

**Rule.** S6 implements the overview’s S6 semantics: **uniform jitter inside the chosen pixel**; **point-in-country enforced** (bounded resample is the intended behaviour at the spec level; today’s event family is fixed-budget per event).
**Detection.** The geometry checks **A606** and **A607** together prove the behavioural outcome; resample mechanics (if any) are not asserted by the current event schema. 

---

## Failure codes (canonical)

* **E601_ROW_MISSING / E602_ROW_EXTRA / E603_DUP_KEY** — A601/A602 violations (parity/uniqueness).
* **E604_PARTITION_OR_IDENTITY** — A603 violation (path↔embed or partition law).
* **E605_SORT_VIOLATION** — A604 violation (writer sort).
* **E606_FK_TILE_INDEX** — A605 violation (FK not found for same `parameter_hash`).
* **E607_POINT_OUTSIDE_PIXEL** — A606 violation.
* **E608_POINT_OUTSIDE_COUNTRY** — A607 violation.
* **E609_RNG_EVENT_COUNT** — A608 violation (coverage mismatch).
* **E610_RNG_BUDGET_OR_COUNTERS** — A609 violation (wrong `blocks/draws` or counter delta).
* **E611_LOG_PARTITION_LAW** — A610 violation (wrong log partitions/path family).
* **E612_DICT_SCHEMA_MISMATCH** — A611 violation (Dictionary vs Schema).

---

### Notes & references the validator relies on

* **S6 table ID, partitions, writer-sort**: `s6_site_jitter` → `[seed, fingerprint, parameter_hash]`, sort `[merchant_id, legal_country_iso, site_order]`. 
* **RNG stream ID & path family**: `rng_event_in_cell_jitter` → logs under `[seed, parameter_hash, run_id]`; **events are per attempt (≥1 per site)**; per-event budget `blocks=1`, `draws="2"`.  
* **Layer RNG envelope invariants**: counters (128-bit) and budget semantics. 
* **S1 geometry authority (tile bounds & country PIP)**. 
* **Overview S6 behavioural intent** (uniform-in-pixel + point-in-country). 

---

# 10) Failure modes & canonical error codes **(Binding)**

### E601_ROW_MISSING — Missing S6 row for a site *(ABORT)*

**Trigger:** A `(merchant_id, legal_country_iso, site_order)` present in **S5** has **no** matching row in **S6**.
**Detection:** Anti-join `S5 \ S6` on the PK must be empty. Writer-sort/PK come from Schema/Dictionary.  

### E602_ROW_EXTRA — Extra S6 row *(ABORT)*

**Trigger:** A site key exists in **S6** that is **not** in **S5**.
**Detection:** Anti-join `S6 \ S5` must be empty.  

### E603_DUP_KEY — Duplicate primary key in S6 *(ABORT)*

**Trigger:** Duplicate `(merchant_id, legal_country_iso, site_order)` in **S6**.
**Detection:** Enforce PK uniqueness per `schemas.1B.yaml#/plan/s6_site_jitter` and Dictionary writer-sort.  

### E604_PARTITION_OR_IDENTITY — Partition/path or path↔embed mismatch *(ABORT)*

**Trigger:** Any of:

* Dataset not under `…/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`,
* Embedded lineage (where present) ≠ path tokens.
  **Detection:** Compare path-derived `{seed,fingerprint,parameter_hash}` to embedded fields; assert partitioning and writer policy match Dictionary. 

### E605_SORT_VIOLATION — Writer sort violated *(ABORT)*

**Trigger:** Records in **S6** are not in non-decreasing `[merchant_id, legal_country_iso, site_order]`.
**Detection:** Validate stable merge order per Dictionary. 

### E606_FK_TILE_INDEX — `tile_id` not found in `tile_index` for same parameter set *(ABORT)*

**Trigger:** `(legal_country_iso, tile_id)` in **S6** (or S5 when joined) does **not** exist in `prep.tile_index` for the **same** `parameter_hash`.
**Detection:** FK join using the schema-encoded FK with explicit `partition_keys: ['parameter_hash']`. 

### E607_POINT_OUTSIDE_PIXEL — Reconstructed point outside pixel rectangle *(ABORT)*

**Trigger:** Reconstructing `(lon*,lat*)` = S1 centroid + S6 effective deltas falls **outside** the S1 pixel bounds.
**Detection:** Use `tile_index` min/max bounds (dateline-aware) to check `min_lon ≤ lon* ≤ max_lon` and `min_lat ≤ lat* ≤ max_lat`. 

### E608_POINT_OUTSIDE_COUNTRY — Point not inside country polygon *(ABORT)*

**Trigger:** Reconstructed `(lon*,lat*)` is **not** inside `world_countries` for `legal_country_iso`.
**Detection:** PIP against the S1-governed country surface (same authority used by tiling). 

### E609_RNG_EVENT_COUNT — Event coverage mismatch *(ABORT)*

**Trigger:** Any site key in S6 has **no** corresponding `rng_event_in_cell_jitter` events (i.e., event_count = 0).
**Detection:** For every site key, assert **event_count ≥ 1** and joinability to site keys; partitions are `[seed, parameter_hash, run_id]`. 

### E610_RNG_BUDGET_OR_COUNTERS — Budget/counter law violated *(ABORT)*

**Trigger:** Any `in_cell_jitter` event fails the envelope law (e.g., wrong `draws`/`blocks` or counter delta).
**Detection:** Validate envelope per **layer schema**: `draws` is **dec-u128 string**, `blocks` is **u64**, and **u128(after) − u128(before) = blocks**. (Budget for this stream: two-uniform family per event.)

### E611_LOG_PARTITION_LAW — RNG log path/partition mismatch *(ABORT)*

**Trigger:** RNG events not under
`logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.
**Detection:** Verify path family and partitions `[seed, parameter_hash, run_id]`. 

### E612_DICT_SCHEMA_MISMATCH — Dictionary vs Schema disagreement *(ABORT)*

**Trigger:** Any referenced ID’s **path/partitions/sort** per Dictionary disagree with the bound Schema anchors (or vice-versa).
**Detection:** Cross-check `schema_ref` ↔ Dictionary entries for `s6_site_jitter` and `rng_event_in_cell_jitter`; Schema is the **shape** authority.  

### E613_RESAMPLE_EXHAUSTED — Bounded resample cap hit *(ABORT)*
**Trigger:** A site exceeds MAX_ATTEMPTS uniform attempts without passing the country predicate.
**Detection:** For a site, event_count ≥ MAX_ATTEMPTS and no accepted sample; validators observe ≥1 `in_cell_jitter` events for the site (each with blocks=1, draws="2") and failure of A607 (point-in-country). The run aborts.

---

**Notes (binding references used by these validators):**

* `s6_site_jitter` path & partitions, writer-sort: Dictionary (v1.9). 
* `in_cell_jitter` log path & partitions: Dictionary/Registry; **events are per attempt (≥1 per site)**; per-event budget `blocks=1`, `draws="2"`.  
* FK hint to `tile_index` with `partition_keys: ['parameter_hash']`: Schema (v2.4). 
* RNG envelope requirements (`draws` dec-u128 string, `blocks` u64, counter delta law): Layer schema. 

---

# 11) Observability & run-report **(Binding)**

## 11.1 Required logs S6 MUST write/update

* **RNG event stream — `in_cell_jitter`.** One JSONL **event per attempt** under
  `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  (partitions `[seed, parameter_hash, run_id]`; schema `schemas.layer1.yaml#/rng/events/in_cell_jitter`). Each event carries the **layer RNG envelope** (pre/after 128-bit counters, `blocks` u64, `draws` dec-u128 string).  
* **RNG core logs (run-scoped):**
  – **`rng_audit_log`** — one row at run start (if not already present for this `{seed,parameter_hash,run_id}`) under `logs/rng/audit/...` (schema `#/rng/core/rng_audit_log`). 
  – **`rng_trace_log`** — **append exactly one cumulative row after each RNG event append** under `logs/rng/trace/...` (schema `#/rng/core/rng_trace_log`). Trace rows carry **saturating totals** `{events_total, draws_total, blocks_total}` per `(module, substream_label)` and reconcile counters.  

**Envelope law (must hold for every S6 event).**
`blocks == u128(after) − u128(before)`; `draws` is the **actual** uniforms used by that event (decimal u128). For `in_cell_jitter`, the event schema pins **two-uniform family** → `blocks=1`, `draws="2"`.  

**Lineage parity (events & cores).** Embedded `{seed, parameter_hash, run_id}` (where present) **MUST** byte-equal the path tokens. 

---

## 11.2 Run-report: mandatory counters S6 MUST compute

S6 MUST compute (and surface to the next state) the following **run-level counters**; they MAY be printed to stdout or emitted as an ephemeral JSON object for S7 to persist in the 1B bundle. No new Dictionary surface is introduced here.

**Identity block**

```
{ "seed": u64, "parameter_hash": hex64, "manifest_fingerprint": hex64, "run_id": hex32 }
```

**Counts & reconciliation (binding expectations)**

- `sites_total = |S5| = |S6|` (row parity).
- `rng.events_total = count(in_cell_jitter)`; **MUST satisfy** `rng.events_total ≥ sites_total` (resamples add events).
- `rng.draws_total = Σ parse_u128(draws)` from **events** and from the **final trace row** for `(module, "in_cell_jitter")`; both MUST equal **`2 * rng.events_total`**.
- `rng.blocks_total = Σ blocks` from events and from trace; both MUST equal **`rng.events_total`** (since `blocks=1` per event).
- `rng.counter_span = u128(last_after) − u128(first_before)` from trace MUST equal `rng.blocks_total`.

**Geometry/FK/lineage summaries (counts)**

* `fk_tile_index_failures` (S6↔S1 FK on `(legal_country_iso,tile_id)` for same `parameter_hash`). 
* `point_outside_pixel` (reconstruct with S1 bounds; dateline-aware). 
* `point_outside_country` (PIP against `world_countries`). 
* `path_embed_mismatches` (any lineage ≠ path tokens across S6 + events). 

**Per-country roll-ups (diagnostic)**

```
by_country[ISO]: {
  sites, rng_events, rng_draws, outside_pixel, outside_country
}
```

*(Purely diagnostic roll-ups; authority remains per-row validation.)*

---

## 11.3 Optional diagnostics S6 SHOULD compute (non-authoritative)

* **Uniform-in-pixel heuristics:** simple χ² or bucketed uniformity checks of `(lon*,lat*)` within each pixel (or aggregated per country); report p-values/counts only (no gating). 
* **Edge-hit rate:** fraction of samples within `ε=1e−6` deg of pixel edges (sanity guard for numeric clipping). 
* **Latency & throughput:** rows/sec overall and by country; shard skew (p90/p99). *(Performance is informative.)*

---

## 11.4 Where these numbers come from (sources)

* **Events:** `rng_event_in_cell_jitter` under `[seed, parameter_hash, run_id]` (`draws="2"`, `blocks=1` **per event**). 
* **Trace:** `rng_trace_log` under `[seed, parameter_hash, run_id]` (cumulative `{events_total, draws_total, blocks_total}`; one append **after each event**). 
* **Audit:** `rng_audit_log` row at run start (seed/fingerprint/parameter/algorithm/build recorded). 
* **Data & geometry:** S6 table + S1 `tile_index` + `world_countries` for reconstructions and PIP checks. 

---

## 11.5 Retention & immutability (for observability artefacts)

* **S6 dataset** `s6_site_jitter`: retention **365 days**; write-once; atomic move; file order non-authoritative. 
* **RNG events** `in_cell_jitter`: retention **30 days**; append-only; partitions `[seed, parameter_hash, run_id]`. 
* **Core logs** (`rng_audit_log`, `rng_trace_log`): run-scoped under `[seed, parameter_hash, run_id]`; one audit row per run; one trace row **per event append**. 

---

## 11.6 Minimal JSON shape for the S6 run-report (non-authoritative, forwarded to S7)

S6 SHALL expose, at minimum, a JSON object with these keys to be embedded by S7 (naming/stability binding here; precise schema owned by S7):

```json
{
  "identity": { "seed": 0, "parameter_hash": "", "manifest_fingerprint": "", "run_id": "" },
  "counts": {
    "sites_total": 0,
    "rng": { "events_total": 0, "draws_total": "0", "blocks_total": 0, "counter_span": "0" }
  },
  "validation_counters": {
    "fk_tile_index_failures": 0,
    "point_outside_pixel": 0,
    "point_outside_country": 0,
    "path_embed_mismatches": 0
  },
  "by_country": { "GB": { "sites": 0, "rng_events": 0, "rng_draws": "0", "outside_pixel": 0, "outside_country": 0 } }
}
```

This object is **informative** (not identity-bearing), but its values MUST be consistent with the authoritative artefacts listed above (events, trace, dataset).  

---

# 12) Performance & scalability **(Informative)**

This section offers **non-binding** guidance to make S6 fast, predictable, and replayable at scale while staying within the **shape/identity** contracts (Schema + Dictionary) and the S6/overview behaviour (uniform-in-pixel; point-in-country).  

## 12.1 Parallelism & stable merge

* **Shard safely.** Parallelise by **country** or by disjoint merchant buckets; each worker processes a disjoint slice of the S5 keyset. Final dataset is a **stable merge** in the binding writer sort `[merchant_id, legal_country_iso, site_order]`; file order remains non-authoritative. 
* **RNG logs are append-only.** Emit `in_cell_jitter` events under `[seed, parameter_hash, run_id]`; events are **per attempt (≥1 per site)**, so **`rng.events_total ≥ sites_total`**. Do not depend on file order in logs; validators use the envelope/counters.

## 12.2 Geometry fast-paths (point-in-country)

* **Interior-tile shortcut.** Build an ephemeral **“border-tile bitset”** per country: mark tiles whose pixel rectangle fully lies inside the country polygon. For interior tiles, **skip PIP** (predicate is always true); run PIP only on border tiles. (Tile rectangles and centroids come from S1 `tile_index`; country polygons from `world_countries`.) 
* **Prepared predicates.** Pre-index country polygons per run (e.g., prepared geometry / spatial index). Reuse these immutable objects across threads; this avoids repeated topology cost while honouring S1’s **dateline-aware** semantics. 
* **Dateline handling.** Use the exact unwrapping convention implied by S1 when mapping uniforms to `[min,max]` bounds, then normalise back to WGS84; this keeps “inside-rectangle” checks O(1). 

## 12.3 RNG throughput & counters

* **Counter-based wins.** Philox lets you generate uniforms **without shared state**; derive substreams deterministically from the site key and emit **one event per attempt** with `blocks=1`, `draws="2"` (two-uniform family). This matches the **layer event schema** and Dictionary text.
* **Open-interval mapping.** Ensure the U(0,1) mapping is strict-open (never 0.0/1.0) per the layer rule; this avoids edge artefacts in uniform-in-pixel sampling. 

> **Note on attempts:** The overview allows bounded resample to satisfy point-in-country, and today’s event schema is fixed-budget **per event** (`blocks=1`, `draws="2"`). **Resamples appear as additional events (one per attempt)**; surface attempt statistics in the **run-report** (observability).

## 12.4 Join strategy (S5 ↔ S1)

* **Cache S1 rows.** Hot-path the `(country_iso, tile_id) → [bounds, centroid]` join via an in-memory map keyed by tile_id **scoped by parameter_hash** (S1 partitions are parameter-scoped). This avoids repeated parquet scans. 
* **FK locality.** Keep the FK check local to the join (S6/S5 → `tile_index` for the **same** `parameter_hash`); the schema encodes this with an explicit `partition_keys: ['parameter_hash']` hint. 

## 12.5 I/O & file layout

* **Dataset (parquet).** Write S6 in **writer sort** to help columnar encoders and downstream range scans; aim for **balanced row groups** (tens of MBs) aligned to sort runs. Dictionary fixes **format and partitions**:
  `…/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`. 
* **Logs (JSONL).** Emit `in_cell_jitter` as **streaming appends**; partitions `[seed, parameter_hash, run_id]`; retention **30 days** in the Dictionary keeps the footprint bounded. 

## 12.6 Work scheduling & memory

* **Country batching.** Batch by country to maximize cache hits on polygon predicates and S1 tile rows.
* **Zero-copy deltas.** Compute `(lon*,lat*)` then write **effective deltas**; avoid storing absolutes until S7/S8. The S6 shape already carries the effective deltas and is **columns_strict** for safety. 
* **Bounded resample cap.** Choose a conservative `MAX_ATTEMPTS` (e.g., 64) to bound tail latency; instrument **attempt histograms** in the run-report (non-authoritative). Overview still expects bounded resample semantics. 

## 12.7 Determinism under concurrency

* **Substream derivation.** Derive the per-site RNG substream deterministically from the site key; counters define order, not file position. This mirrors the layer’s **substream/counter** model and keeps replay stable irrespective of parallelism. 
* **Atomic publish.** Stage → fsync → **single atomic move** into the identity partitions for the dataset; logs are append-only within `[seed, parameter_hash, run_id]`. (Immutability and writer-sort determinism are reiterated in the Registry/Dictionary.)  

## 12.8 Numeric environment (guardrails)

* Honour the **binary64** regime pinned in S0 (RNE, FMA off, no FTZ/DAZ; deterministic libm). These are part of the sealed manifest and guarantee the same `(lon*,lat*)` are reconstructed from deltas across reruns. 

## 12.9 What to watch (operational SLO hints)

* **Row/event relation:** `|S6| = |S5|` and **`rng.events_total ≥ sites_total`**. Large gaps suggest frequent resamples or logging back-pressure.
* **RNG identities:** From the **trace** (if enabled for your run), `draws_total == 2·rng.events_total` and `blocks_total == rng.events_total`. (Event schema fixes `draws="2"`, `blocks=1` per event.)
* **PIP workload split:** interior vs border-tile share; a healthy run should spend the majority of cycles on border tiles only.

---

# 13) Change control & compatibility **(Binding)**

## 13.1 Versioning model (SemVer)

S6 uses **MAJOR.MINOR.PATCH**. Artefact entries record a `semver` and are governed as immutable once published (write-once; atomic move). 

* **PATCH** — editorial fixes/clarifications; no change to shapes, paths/partitions, writer-sort, validators, or RNG budgets.
* **MINOR** — backward-compatible additions that **cannot** cause a previously valid run to fail (e.g., extra non-authoritative run-report fields/diagnostics; doc corrections in Registry notes). 
* **MAJOR** — any change that could invalidate a previously valid run or alters identity/shape/gate semantics.

## 13.2 What counts as **MAJOR** (non-exhaustive)

The following **SHALL** be treated as **MAJOR** and require re-ratification of S6:

1. **Dataset/log identity or path law**

   * Changing **partitions** for `s6_site_jitter` from `[seed, fingerprint, parameter_hash]` or its path family, or changing writer-sort `[merchant_id, legal_country_iso, site_order]`. 
   * Changing RNG log partitions `[seed, parameter_hash, run_id]` or path family for `rng_event_in_cell_jitter`. 

2. **Schema-owned shape**

   * Any change to `schemas.1B.yaml#/plan/s6_site_jitter` keys/columns or `columns_strict` posture (e.g., adding/removing columns, tightening bounds so existing rows could fail). 
   * Any change to the **layer RNG event schema** for `in_cell_jitter` that alters its budget constants (`blocks=1`, `draws="2"`) or envelope fields. 

3. **Behavioural gates & acceptance**

   * Modifying acceptance rules so that a previously conformant run would fail (e.g., new hard geometry constraints beyond “inside pixel” / “inside country”). 
   * Altering “**No PASS → No read**” upstream gate semantics. (Gate law is part of the state flow.) 

4. **Authority surfaces / semantics**

   * Replacing S1 **`tile_index`** bounds/centroids authority or the **`world_countries`** surface or their topology/antimeridian semantics. S6 depends on these definitions for A606/A607.  

5. **Distributional lane**

   * Changing S6 away from the overview’s **uniform-in-pixel** semantics (e.g., switching to Gaussian jitter) is a **behavioural** change and **MAJOR**. 

## 13.3 What may be **MINOR**

The following are **MINOR** only if strictly backward-compatible:

* **Observability/diagnostics:** adding optional run-report fields, per-country histograms, or non-authoritative metrics (no schema for datasets/logs changed). 
* **Registry/doc notes:** correcting Registry roles/notes without altering schema/paths (e.g., removing `jitter_policy` from S6 dependencies in Registry v1.7 text — S6 uniform lane does not consume it). 
* **Loosening numeric guards:** widening S6 delta bounds (e.g., from `[-1,1]` to `[-1.5,1.5]`) only if all existing valid rows remain valid. Tightening is **MAJOR**. 
* **Run-report delivery:** surfacing the same counters via an additional non-identity file (S7 will own any bundle schema).

## 13.4 What is **PATCH** only

* Typos, naming clarifications, cross-references, or prose reflows that **do not** change any binding behaviour, schema, path/partitions, writer-sort, RNG budgets, or acceptance outcomes.

## 13.5 Compatibility baselines (this spec line)

S6 v1.* is validated against the following **frozen** surfaces:

* **Schema (1B):** `schemas.1B.yaml` — `s6_site_jitter` anchor (PK, partitions `[seed,fingerprint,parameter_hash]`, writer-sort, `columns_strict`). 
* **Dictionary (1B):** `dataset_dictionary.layer1.1B.yaml` — IDs→paths/partitions for `s6_site_jitter` and `rng_event_in_cell_jitter`, retentions (365d / 30d). 
* **Registry (1B):** `artefact_registry_1B.yaml` — notes on write-once/atomic-move and RNG event family roles. 
* **Layer schema:** `schemas.layer1.yaml` — RNG **envelope** (`draws` dec-u128, `blocks` u64) and event constants for `in_cell_jitter` (`draws="2"`, `blocks=1`). 
* **Overview:** S6 behaviour = **uniform inside pixel**, **point-in-country enforced**. 

A **MAJOR** bump in any of the above that changes a bound interface requires an S6 **MAJOR** (or an explicit compatibility shim).

## 13.6 Forward-compatibility guidance

* **If per-site resample attempts need to be logged:** do **not** mutate the existing `in_cell_jitter` event schema (fixed `draws="2"`, `blocks=1`) — instead **add** a new event family (e.g., `in_cell_jitter_v2`) or a separate diagnostic stream. That is a **MINOR** addition if it doesn’t alter acceptance; changing the existing stream’s budget would be **MAJOR**. 
* **If egress partitions change upstream:** S6 does **not** publish egress; `site_locations` remains `[seed, fingerprint]` per Dictionary. Altering that is outside S6 and would be handled in the egress state’s change control. 

## 13.7 Deprecation & migration (binding posture)

* **Dual-lane window:** When introducing a replacement stream/dataset, maintain both old and new for **at least one MINOR** version, with validators accepting either (but never silently rewiring IDs).
* **Removal:** Removing the old lane is **MAJOR** and MUST be announced in the state header with a migration note.

## 13.8 Cross-state compatibility

* **Upstream handshake:** S6 is compatible only with S5/S1 shapes stated in §6; a **MAJOR** in S5/S1 that alters keys, partitions, or the `tile_index`/country semantics requires re-ratifying S6 (likely as **MAJOR**). 
* **Downstream neutrality:** S6 does not alter egress; S7/S8 may tighten checks or add packaging, but such changes **must not** require an S6 change unless they change S6’s contracts.

---

# Appendix A — Symbols *(Informative)*

## A.1 Sets, keys, and indices

* **S5_keys** — the exact keyset of sites produced by S5; one tuple per site:
  `S5_keys = {(merchant_id, legal_country_iso, site_order)}`. S6 emits **one row per key**. 
* **country set:** `ISO = {iso2}` — canonical ISO-3166 codes used across the layer. FK from `legal_country_iso` to the ingress ISO surface (via schema refs). 

## A.2 Identity & lineage tokens

* **seed** — 64-bit unsigned integer that parameterises all RNG substreams for the run. Appears in dataset partitions and RNG log partitions.  
* **parameter_hash** — 256-bit hex string (formatted) identifying the sealed parameter bundle; appears in both dataset and RNG log partitions. 
* **manifest_fingerprint** — 256-bit hex string (formatted) fingerprint of the run manifest; **path token** is `fingerprint={manifest_fingerprint}`; **embedded column** remains `manifest_fingerprint` when present. 
* **run_id** — opaque identifier (string/hex) for the RNG-log partition; one `run_id` per publish under `[seed, parameter_hash, run_id]`. 

## A.3 Datasets, logs, partitions (dictionary law)

* **S6 dataset ID:** `s6_site_jitter`
  Path family: `data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  Partitions: `[seed, fingerprint, parameter_hash]` · Writer sort: `[merchant_id, legal_country_iso, site_order]`. 
* **RNG events ID:** `rng_event_in_cell_jitter`
  Path family: `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  Partitions: `[seed, parameter_hash, run_id]` (no fingerprint in logs). 

## A.4 Geometry & placement symbols (WGS84 / degrees)

Let the S1 tile rectangle be `[min_lon, max_lon] × [min_lat, max_lat]` and the S1 centroid be `(centroid_lon_deg, centroid_lat_deg)` for a given `(legal_country_iso, tile_id)`.

* **lon***, **lat*** — the **realised** longitude/latitude inside the pixel.
  Uniformly sampled by mapping open-interval uniforms (see A.6):

  ```
  lon* = min_lon + u_lon · (max_lon − min_lon)
  lat* = min_lat + u_lat · (max_lat − min_lat)
  ```

  *(Dateline handling follows S1’s unwrapping/normalisation rules.)* 
* **δ_lon_deg**, **δ_lat_deg** — **effective** S6 deltas (degrees):
  `δ_lon_deg = lon* − centroid_lon_deg`, `δ_lat_deg = lat* − centroid_lat_deg`. (S6 stores these deltas; absolutes are reconstructed when needed.) 
* **tile_id** — 64-bit integer key of the pixel (FK to S1 `tile_index` **for the same `parameter_hash`**). 

**Country predicate:**

* **pip_country(lat,lon, iso2)** → `bool` — point-in-polygon against `world_countries[iso2]` (S1’s authority and antimeridian semantics). S6 requires accepted samples to satisfy this predicate. 

## A.5 RNG envelope & event fields (layer schema)

Each event in `rng_event_in_cell_jitter` validates the **layer RNG envelope**:

* **module** = `"1B.S6.jitter"` · **substream_label** = `"in_cell_jitter"` · **ts_utc** = RFC-3339 (exact 6 fractional digits).
* **draws** — **decimal-encoded u128** count of uniforms consumed by the event.
* **blocks** — **u64** count of PRNG blocks consumed by the event.
* **rng_counter_before_{lo,hi} / rng_counter_after_{lo,hi}** — 128-bit counters (split fields); **u128(after) − u128(before) = blocks**.
* **Per-event budget (current anchor):** `blocks = 1`, `draws = "2"` (two-uniform family). 

*(Note: S6 emits **one event per attempt (≥1 per site)**; acceptance checks require **≥1 event per site**, the **last** event to match the accepted sample, and the per-event fixed budget above.)*

## A.6 Random variables & domains

* **u_lon, u_lat ∼ U(0,1)** — **open-interval** uniforms (never 0 or 1) drawn under the layer’s U(0,1) mapping. 
* **lat, lon units** — decimal degrees on **WGS84 (EPSG:4326)**; typical domains: `lat ∈ [−90, 90]`, `lon ∈ [−180, 180]` (normalised as per S1). *(Schema anchors own exact bounds/guards for S6 columns.)* 
* **MAX_ATTEMPTS** — bounded resample cap used by implementations to satisfy the country predicate; **not identity-bearing** and **not logged** in the current event schema (surface resample stats in the run-report if computed). 

## A.7 Helper functions (informal)

* **unwrap_lon(min,max)** — returns a consistent interval for dateline-crossing tiles used to compute `(max−min)`; S1’s convention governs.
* **wrap_lon(x)** — normalise longitude back to the canonical interval after arithmetic (WGS84 wrap).
* **inside_rect(lat,lon, bounds)** — inclusive rectangle check using S1 tile bounds.

*(These helpers are conceptual; the authoritative rectangle and centroid come from S1 `tile_index`.)* 

## A.8 Abbreviations

* **PK** — Primary key (within an identity partition).
* **FK** — Foreign key.
* **PASS / ABORT** — Gate/validator outcome.
* **RNG** — Random number generation (counter-based; Philox family per layer).
* **U(0,1)** — continuous uniform distribution on the **open** interval (0,1). 

## A.9 Numeric environment (layer governance)

Unless explicitly stated otherwise, numeric behaviour follows the layer profile: **round-to-nearest even (RNE)**, **FMA off**, **FTZ/DAZ off**, **subnormals preserved**. This ensures deterministic reconstruction of `(lon*, lat*)` from S6 deltas across reruns and platforms. 

---

**Where to look up shapes/paths:**

* **S6 table shape:** `schemas.1B.yaml#/plan/s6_site_jitter`. **Paths/partitions/sort:** Dataset Dictionary (`s6_site_jitter`). 
* **RNG event shape:** `schemas.layer1.yaml#/rng/events/in_cell_jitter`. **Log partitions:** Dataset Dictionary (`rng_event_in_cell_jitter`).  

This appendix is **informative** only; the **Schema** remains the sole authority for shapes and the **Dictionary** for path families, partitions, and writer policy.  

---

# Appendix B — Worked example *(Informative)*

## B.1 Identity (fixed for the run)

```
seed                    = 987654321
parameter_hash          = "7b1e6e0f1b9a4ac2bb8f2b1a0d88c0e2c9f9c4d1f3a2b5c6d7e8f90123456789"   # hex64
manifest_fingerprint    = "f2c0a4d3b1e5907e8f66caa9d4e1b2c3f4a5968790b1c2d3e4f5a6b7c8d9e0f1"   # hex64
run_id                  = "r20251021a"
```

**Partitions used**

* S6 dataset: `…/s6_site_jitter/seed=987654321/fingerprint=f2c0…/parameter_hash=7b1e…/`
* RNG events: `…/in_cell_jitter/seed=987654321/parameter_hash=7b1e…/run_id=r20251021a/`

---

## B.2 Inputs (one interior tile example)

**S5 site key:** `(merchant_id="m000001", legal_country_iso="GB", site_order=1, tile_id=240104)`

**S1 `tile_index` (tile_id=240104)**

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

*(This tile lies entirely inside GB, so the country predicate will succeed for any in-rectangle sample.)*

---

## B.3 Jitter sampling (uniform in pixel)

Draw two open-interval uniforms for this site (two-uniform family; **in this example the first attempt is accepted**, so there is one event for the site):

```
u_lon = 0.732421
u_lat = 0.104589
```

Map to the rectangle:

```
lon* = min_lon + u_lon·(max_lon−min_lon)
     = -0.25 + 0.732421·0.05
     = -0.21337895

lat* = min_lat + u_lat·(max_lat−min_lat)
     =  51.50 + 0.104589·0.05
     =  51.50522945
```

Compute **effective deltas** relative to the centroid:

```
delta_lon_deg = lon* − centroid_lon_deg = -0.21337895 − (-0.225000) =  0.01162105
delta_lat_deg = lat* − centroid_lat_deg =  51.50522945 − 51.525000 = -0.01977055
```

**Checks (informative):**

* Inside-rectangle: `-0.250000 ≤ -0.213379 ≤ -0.200000` and `51.500000 ≤ 51.505229 ≤ 51.550000` ✅
* Point-in-country (GB): true (interior tile) ✅

---

## B.4 RNG event (JSONL; for this site’s accepted attempt)

*(Shape owned by the layer RNG event anchor; `draws` is a **decimal u128 string**, `blocks` is **u64**.)*

```json
{
  "module": "1B.S6.jitter",
  "substream_label": "in_cell_jitter",
  "ts_utc": "2025-10-21T08:52:34.123456Z",
  "seed": 987654321,
  "parameter_hash": "7b1e6e0f1b9a4ac2bb8f2b1a0d88c0e2c9f9c4d1f3a2b5c6d7e8f90123456789",
  "run_id": "r20251021a",
  "merchant_id": "m000001",
  "legal_country_iso": "GB",
  "site_order": 1,
  "rng_counter_before_lo": "12345678901234567890",
  "rng_counter_before_hi": "0",
  "rng_counter_after_lo":  "12345678901234567891",
  "rng_counter_after_hi":  "0",
  "blocks": 1,
  "draws": "2"
}
```

Envelope law holds: `u128(after) − u128(before) = 1 (blocks)`; `draws="2"`.

---

## B.5 S6 dataset row (Parquet)

*(Columns owned by `schemas.1B.yaml#/plan/s6_site_jitter`; shown here as a CSV-style rendering for readability.)*

| merchant_id | legal_country_iso | site_order | tile_id | delta_lat_deg | delta_lon_deg | manifest_fingerprint                                             |
| ----------- | ----------------- | ---------: | ------: | ------------: | ------------: | ---------------------------------------------------------------- |
| m000001     | GB                |          1 |  240104 |   -0.01977055 |    0.01162105 | f2c0a4d3b1e5907e8f66caa9d4e1b2c3f4a5968790b1c2d3e4f5a6b7c8d9e0f1 |

**Partition path:**
`…/s6_site_jitter/seed=987654321/fingerprint=f2c0…/parameter_hash=7b1e…/part-0000.snappy.parquet`

Writer sort (`merchant_id, legal_country_iso, site_order`) is respected.

---

## B.6 Validator perspective (what will PASS here)

* **A601 Row parity:** `|S6| == |S5|` for the key `(m000001,GB,1)` ✅
* **A602 Schema:** row validates; columns_strict honored ✅
* **A603 Partition & identity:** path partitions match, and the embedded `manifest_fingerprint` equals `fingerprint` ✅
* **A604 Writer sort:** non-decreasing by `[merchant_id, legal_country_iso, site_order]` ✅
* **A605 FK:** `(GB, 240104)` exists in `tile_index` for this `parameter_hash` ✅
* **A606 Inside pixel:** reconstructed `(lon*,lat*)` inside rectangle ✅
* **A607 Point-in-country:** inside GB polygon ✅
* **A608 Event coverage:** exactly **1** `in_cell_jitter` event for this site ✅
* **A609 Budget & counters:** `blocks=1`, `draws="2"`, counter delta = 1 ✅
* **A610 Log partition law:** event under `[seed, parameter_hash, run_id]` ✅

---

## B.7 Minimal S6 run-report payload (what S7 will package)

```json
{
  "identity": {
    "seed": 987654321,
    "parameter_hash": "7b1e6e0f1b9a4ac2bb8f2b1a0d88c0e2c9f9c4d1f3a2b5c6d7e8f90123456789",
    "manifest_fingerprint": "f2c0a4d3b1e5907e8f66caa9d4e1b2c3f4a5968790b1c2d3e4f5a6b7c8d9e0f1",
    "run_id": "r20251021a"
  },
  "counts": {
    "sites_total": 1,
    "rng": { "events_total": 1, "draws_total": "2", "blocks_total": 1, "counter_span": "1" }
  },
  "validation_counters": {
    "fk_tile_index_failures": 0,
    "point_outside_pixel": 0,
    "point_outside_country": 0,
    "path_embed_mismatches": 0
  },
  "by_country": { "GB": { "sites": 1, "rng_events": 1, "rng_draws": "2", "outside_pixel": 0, "outside_country": 0 } }
}
```

---

## B.8 Negative case (border tile) — what failure looks like

Suppose a different S5 site maps to a **border tile** (rectangle straddles the coastline). With uniforms
`u_lon=0.95`, `u_lat=0.05`, the sample is inside the pixel but **outside** the country polygon:

* **A606 Inside pixel:** ✅
* **A607 Point-in-country:** ❌ → **E608_POINT_OUTSIDE_COUNTRY**
* **A608/A609:** **≥2 events** (multiple attempts), each with `draws="2"`, `blocks=1` (per-event budget OK).
* **Outcome:** If all attempts fail the country predicate up to the cap, S6 **ABORTS** with `E606_RESAMPLE_EXHAUSTED`. (If an implementation wrongly wrote an outside-country row, `A607` would FAIL—but the normative algorithm resamples instead.)

*(Operationally you’d avoid frequent border failures by tiling so most tiles are interior, or by choosing seeds where empirical outside-rate is negligible. The spec itself remains unchanged.)*

---

## B.9 Reproducibility note

Re-running with the **same** `{seed, parameter_hash, manifest_fingerprint, run_id}` and the same sealed inputs yields **identical** events, deltas, and run-report numbers. Changing **any** member of the identity tuple changes output partitions and/or event lineage, and validation **MUST** fail if path↔embed equality is broken.

---