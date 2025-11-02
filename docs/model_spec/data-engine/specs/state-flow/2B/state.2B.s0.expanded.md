# State 2B.S0 — Gate & Environment Seal

## 1. **Document metadata & status (Binding)**

**Component:** Layer-2 · Segment **2B** — **State-0 (S0)** · *Gate, identity & sealed inputs*
**Document ID:** `seg_2B.s0.gate`
**Version (semver):** `v1.0.0-alpha`
**Status:** `alpha` *(normative; semantics lock at `frozen` in a ratified release)*
**Owners:** Design Authority (DA): **Esosa Orumwese** · Review Authority (RA): **Layer-2 Governance**
**Effective date:** **2025-11-02 (UTC)**
**Canonical location:** `contracts/specs/l2/seg_2B/state.2B.s0.expanded.v1.0.0.txt`

**Authority chain (Binding):**
**JSON-Schema pack** = shape authority → `schemas.2B.yaml`
**Dataset Dictionary** = ID→path/partitions/format → `dataset_dictionary.layer1.2B.yaml`
**Artefact Registry** = existence/licence/retention → `artefact_registry_2B.yaml`

**Normative cross-references (Binding):**

* Upstream gate: **`validation_bundle_1B/`** (root) + companion **`_passed.flag`**; egress **`site_locations`** (Layer-1 · 1B).
* Optional pins (if declared for this fingerprint): **`site_timezones`**, **`tz_timetable_cache`** (Layer-2 · 2A).
* Segment overview: `state-flow-overview.2B.txt` (context only; this spec governs).
* Layer-1/Layer-2 **Identity & Gate** laws (No PASS → No read; path↔embed equality).

**Segment invariants (Binding):**

* **Run identity:** `{ seed, manifest_fingerprint }` (2B outputs partition as specified in downstream states; S0 outputs are **fingerprint-only**).
* **RNG posture:** **S0 is RNG-free**; later RNG-bounded states in 2B use governed **Philox** sub-streams and recorded policy digests.

---

## 2. **Purpose & scope (Binding)**

**Purpose.** Establish **read authority** and **run identity** for Segment 2B by verifying upstream gates, sealing the minimum input set, and fixing the deterministic context that all downstream 2B states rely on.

**S0 SHALL:**

* **Verify upstream 1B PASS** for the target `manifest_fingerprint` (bundle root + companion `_passed.flag`) **before** any read of 1B egress.
* **Seal the minimum input set** required to start routing work:
  (a) `site_locations` for this `{seed, manifest_fingerprint}`,
  (b) governed **RNG policy pack(s)** for 2B (e.g., route/alias/day-effect policies; each with `version_tag` and `sha256_hex`).
  **Optional pins (all-or-none):** `site_timezones`, `tz_timetable_cache` (read-only) for tz-group coherence checks used later in 2B.
* **Bind run identity** (`seed`, `manifest_fingerprint`) and assert **path↔embed equality** for S0 outputs.
* **Materialise proof artefacts** of authority and identity: a gate **receipt** and a **sealed-inputs inventory** enumerating every sealed asset with IDs, tags, digests, paths, and partitions.
* **Constrain resolution to the Catalogue**: all inputs resolve by **Dictionary IDs**; literal paths are forbidden.
* **Guarantee determinism & immutability**: S0 is RNG-free; outputs are single-writer, write-once, and idempotent under the same sealed inputs.

**Out of scope.** No business transforms or sampling: S0 does **not** freeze weights (S1), build alias tables (S2), draw day effects (S3), re-normalise groups (S4), route arrivals (S5/S6), run audits (S7), or publish the 2B PASS bundle (S8).

---

## 3. **Preconditions & sealed inputs (Binding)**

### 3.1 Preconditions (Abort on failure)

* **Upstream gate present & verified.** The **1B PASS bundle (root)** and its companion **`_passed.flag`** for the target **`manifest_fingerprint`** MUST exist and verify (bundle-hash equals flag value) **before** any read of 1B egress.
* **Run identity fixed.** The pair **`{ seed, manifest_fingerprint }`** for this 2B run is fixed at start and MUST NOT change for the lifetime of the run.
* **RNG posture.** S0 performs no random draws (RNG-free).
* **Resolution discipline.** All inputs resolve by **Dataset Dictionary IDs**; **literal paths are forbidden**.

### 3.2 Minimum sealed set (Abort if any missing)

S0 seals the following assets into the run context (each with **`asset_id`**, **`version_tag`**, **`sha256_hex`**, **`path`**, and **`partition`** recorded in the inventory):

1. **Gate artefacts (fingerprint-only):**

   * `validation_bundle_1B/` (bundle **root folder**) for the target fingerprint
   * `_passed.flag` (companion flag at the same root)

2. **Cross-segment egress (seed + fingerprint):**

   * **`site_locations`** — Layer-1 · 1B egress at `seed={seed} / fingerprint={manifest_fingerprint}`

3. **Governed RNG policy pack(s) for 2B (fingerprint-only):**

   * **`route_rng_policy_v1`** (sub-streams/budgets for S5/S6)
   * **`alias_layout_policy_v1`** (byte layout, endianness, alignment for alias tables)
   * **`day_effect_policy_v1`** (draw cadence, variance, clipping for S3)
     *(Names illustrative; the concrete **IDs** and counts are whatever the Dictionary declares for this fingerprint. Each MUST carry `version_tag` and `sha256_hex`.)*

> **All listed assets MUST be present and resolvable by ID.** Any additional diagnostics sealed by the Dictionary MAY appear but confer no extra authority.

### 3.3 Optional pins (all-or-none set)

If declared for this fingerprint, S0 MAY seal the following **as a set** (either **all present** or **all absent**):

* **`site_timezones`** — Layer-2 · 2A egress at `seed={seed} / fingerprint={manifest_fingerprint}` (read-only)
* **`tz_timetable_cache`** — Layer-2 · 2A cache at `fingerprint={manifest_fingerprint}` (read-only)

These pins are used only for coherence/audit in later 2B states; they confer no additional read authority beyond the verified 1B gate.

### 3.4 Hashing & verification law (Binding)

* **Bundle hash.** Recompute the 1B bundle digest by hashing the **raw bytes** of all files listed in the bundle **index** in **ASCII-lex order of `index.path`**.
* **Flag exclusion.** The `_passed.flag` file is **excluded** from the hash and contains exactly: `sha256_hex = <hex64>`.
* **Abort on mismatch.** If the recomputed digest differs from the flag value, S0 MUST abort before any downstream reads.

### 3.5 Partition selection & path↔embed equality (Binding)

* **Partition law.** For `site_locations`, S0 MUST read **exactly** the partition `seed={seed} / fingerprint={manifest_fingerprint}`. For policy packs and bundle artefacts, selection is **fingerprint-only**.
* **Equality.** All S0 outputs MUST embed the same `manifest_fingerprint` they are written under; any mismatch is an error.

### 3.6 Aliasing & duplicates (Binding)

* If multiple **IDs** resolve to the **same bytes**, S0 MUST record each as a separate inventory row (same `sha256_hex`, distinct `asset_id`). This is **not** an error; it preserves catalogue truth.

---

## 4. **Inputs & authority boundaries (Binding)**

### 4.1 Catalogue authorities

* **Schema pack** (`schemas.2B.yaml`) is the **shape authority** for all S0 outputs and any inputs it references.
* **Dataset Dictionary** (`dataset_dictionary.layer1.2B.yaml`) is the **sole authority** for resolving **IDs → path templates, partitions, and formats**. Token expansion (e.g., `seed={seed}`, `fingerprint={manifest_fingerprint}`) MUST follow the Dictionary.
* **Artefact Registry** (`artefact_registry_2B.yaml`) declares **existence, licence, retention, and ownership**; it does **not** grant read authority or override Dictionary paths.

### 4.2 Inputs S0 MAY read (and nothing else)

S0 SHALL resolve **only** these IDs via the Dictionary (no literal paths):

1. **Gate artefacts (fingerprint-only):**

   * `validation_bundle_1B/` (bundle **root folder** for the target `manifest_fingerprint`)
   * `_passed.flag` (companion flag co-located with the bundle root)
2. **Cross-segment egress (seed + fingerprint):**

   * `site_locations` — Layer-1 · 1B egress at `seed={seed} / fingerprint={manifest_fingerprint}`
3. **Governed policies for 2B (fingerprint-only):**

   * `route_rng_policy_v1`
   * `alias_layout_policy_v1`
   * `day_effect_policy_v1`
     *(Concrete IDs/names are those listed in the Dictionary for this fingerprint; each policy MUST carry `version_tag` and `sha256_hex`.)*
4. **Optional pins (all-or-none set; read-only):**

   * `site_timezones` — Layer-2 · 2A egress at `seed={seed} / fingerprint={manifest_fingerprint}`
   * `tz_timetable_cache` — Layer-2 · 2A cache at `fingerprint={manifest_fingerprint}`

### 4.3 Prohibited resources & reads

* **No literal paths.** Any attempt to read a path not obtained from a Dictionary ID is an error.
* **No reads before gate verification.** S0 MUST verify the 1B bundle/flag **before** reading any 1B egress (including `site_locations`).
* **No additional inputs.** S0 MUST NOT read any other dataset, policy, or diagnostic beyond §4.2.
* **No network fetches.** All bytes are local/managed; network access is forbidden.

### 4.4 Resolution & token discipline

* **Token expansion** MUST produce paths that embed `fingerprint={manifest_fingerprint}` (for fingerprint-scoped artefacts) and `seed={seed}` where required.
* **Partition selection** MUST be exact: for `site_locations` read **only** the partition `seed={seed} / fingerprint={manifest_fingerprint}`; for policies and bundle artefacts, selection is **fingerprint-only**.
* **Path↔embed equality** MUST hold for all S0 outputs; any mismatch is an error.

### 4.5 Trust boundary & sequencing

* The **1B PASS bundle + flag** constitute the upstream trust boundary. S0 SHALL:

  1. Resolve both by ID via the Dictionary.
  2. Recompute the bundle hash from the index (ASCII-lex on `index.path`; hash raw bytes; exclude the flag).
  3. **Abort** on any mismatch.
     Only after (2) succeeds may S0 resolve/read `site_locations` or optional pins.

### 4.6 Inventory boundary

* **Every asset read or trusted by S0** MUST appear in `sealed_inputs_v1` with `{asset_id, version_tag, sha256_hex, path, partition}`.
* It is an error to access any asset not present in the inventory, even if resolvable via the Dictionary.

---

## 5. **Outputs (datasets) & identity (Binding)**

### 5.1 Products (IDs)

* **`s0_gate_receipt_2B`** — receipt that attests upstream gate verification, fixed run identity, and catalogue-only resolution.
* **`sealed_inputs_v1`** — **mandatory** inventory enumerating every asset sealed by S0 (authority record for inputs).

### 5.2 Partitioning & identity law

* **Partitioning:** Both outputs are **fingerprint-only** and SHALL be written under
  `…/fingerprint={manifest_fingerprint}/`.
* **Run identity:** The run is identified by `{ seed, manifest_fingerprint }`. S0 outputs embed `manifest_fingerprint` and MAY echo `seed` as metadata, but **do not** partition by `seed`.
* **Path↔embed equality:** The embedded `manifest_fingerprint` in each output **MUST** equal the fingerprint token in its path.

### 5.3 Path family & format (Dictionary authority)

* The **Dataset Dictionary** binds each ID to its **path template**, **partition tokens**, and **storage format**. S0 SHALL write:

  * `s0_gate_receipt_2B` to the Dictionary’s **receipt path family** for 2B, **stored as JSON**.
  * `sealed_inputs_v1` to the Dictionary’s **inventory path family** for 2B, **stored as a strict table** (columns fixed by schema).
* Literal paths are forbidden; only Dictionary-resolved locations are valid targets.

### 5.4 Write-once, atomic publish, re-emit discipline

* **Single-writer, write-once:** Target partitions **MUST** be empty prior to publish.
* **Atomic publish:** S0 writes each product atomically (no partial files visible).
* **Idempotent re-emit:** A second publish to the same partition is permitted **only** if the produced bytes are **bit-for-bit identical**; otherwise S0 **MUST** abort.

### 5.5 Deterministic writer order

* `sealed_inputs_v1` rows **MUST** be written in a deterministic order: lexicographic by `asset_id`, then by `path` when `asset_id` ties.
* The `s0_gate_receipt_2B` JSON object **MUST** be serialised with a deterministic field order as defined by the schema pack’s receipt anchor.

### 5.6 Provenance & timing

* `s0_gate_receipt_2B` **MUST** include `verified_at_utc` marking the instant the upstream bundle hash was verified; this timestamp also serves as the canonical creation time for S0 outputs.
* `sealed_inputs_v1` **MUST** capture, per row: `asset_id`, `version_tag`, `sha256_hex`, `path`, and `partition` exactly as resolved.

### 5.7 Content constraints

* `sealed_inputs_v1` **MUST** enumerate **every** asset trusted or read by S0 (gate bundle, flag, `site_locations`, policy pack(s), and any optional pins if present). No extras; no omissions.
* Duplicate physical bytes referenced by multiple IDs are represented as **distinct rows** (same `sha256_hex`, different `asset_id`).

### 5.8 Downstream visibility

* Downstream 2B states (S1–S8) **MUST** treat `s0_gate_receipt_2B` as the **sole evidence** that gate verification and input sealing occurred; they SHALL NOT re-hash the 1B bundle.
* Any downstream read **MUST** be preceded by verifying that a matching `s0_gate_receipt_2B` exists for the target `manifest_fingerprint`.

---

## 6. **Dataset shapes & schema anchors (Binding)**

### 6.1 Shape authority

All shapes in this state are governed by **`schemas.2B.yaml`** (shape authority). The **Dataset Dictionary** binds IDs → paths/partitions/format. Shapes are **fields-strict** (no extra fields).

---

### 6.2 Output anchor — `schemas.2B.yaml#/validation/s0_gate_receipt_v1`

**Type:** JSON object (fields-strict)
**Required:** `fingerprint`, `seed`, `verified_at_utc`, `sealed_inputs`, `catalogue_resolution`, `determinism_receipt`

**Fields**

* `fingerprint` — string, hex64 (the `manifest_fingerprint`).
* `seed` — string (opaque run identifier; echoed for downstream context).
* `verified_at_utc` — string, ISO-8601 `date-time` (UTC) when the upstream bundle hash was verified.
* `sealed_inputs` — array of objects (fields-strict); **item required:** `id`, `partition`, `schema_ref`

  * `id` — string (Dictionary ID of the sealed asset).
  * `partition` — object (fields-strict); keys are token names present for that asset (e.g., `fingerprint`, `seed`); values are strings.
  * `schema_ref` — string (JSON-Schema anchor for the asset’s shape).
* `catalogue_resolution` — object (fields-strict); **required:** `dictionary_version`, `registry_version`

  * `dictionary_version` — string (Dictionary semver used to resolve IDs).
  * `registry_version` — string (Registry semver observed during resolution).
* `determinism_receipt` — object (fields-strict; **no required** keys; allowed keys listed below)

  * `engine_commit` — string (VCS commit or package digest for the engine build).
  * `python_version` — string.
  * `platform` — string.
  * `policy_ids` — array of strings (IDs captured from sealed policy pack(s)).
  * `policy_digests` — array of strings, hex64 (aligned 1:1 with `policy_ids`).

**Notes (binding semantics):**

* `sealed_inputs` enumerates membership only; **version tags and digests live in the inventory** (see §6.3).
* Field order for serialisation is deterministic as defined by this anchor.

---

### 6.3 Output anchor — `schemas.2B.yaml#/validation/sealed_inputs_v1`

**Type:** JSON table (array of row objects, fields-strict)
**Required row fields:** `asset_id`, `version_tag`, `sha256_hex`, `path`, `partition`
**Optional row field:** `schema_ref`

**Row field shapes**

* `asset_id` — string (Dictionary ID).
* `version_tag` — string (opaque tag/version for the asset, e.g., release label).
* `sha256_hex` — string, hex64 (digest of the asset bytes).
* `path` — string (resolved absolute or repo-root-relative path from the Dictionary).
* `partition` — object (fields-strict); keys = token names (e.g., `fingerprint`, `seed`); values = strings.
* `schema_ref` — string (JSON-Schema anchor for the asset’s shape).

**Notes (binding semantics):**

* **Every asset read or trusted by S0** MUST have exactly one row.
* Multiple IDs pointing to the same bytes appear as **distinct rows** (same `sha256_hex`, different `asset_id`).
* Row order is deterministic: lexicographic by `asset_id`, then `path`.

---

### 6.4 Referenced anchors (inputs)

S0 references (but does not redefine) the following input shapes; `schema_ref` values in the receipt/inventory MUST point to these anchors (or their catalogue-declared successors):

* **Upstream gate (Layer-1 / 1B)**

  * `schemas.1A.yaml#/validation/validation_bundle.index_schema` — bundle index shape used for hash recomputation.
  * `schemas.1B.yaml#/egress/site_locations` — 1B egress consumed by 2B.

* **Optional pins (Layer-2 / 2A)**

  * `schemas.2A.yaml#/egress/site_timezones`
  * `schemas.2A.yaml#/egress/tz_timetable_cache`

* **2B policy packs (shape IDs live in the 2B schema pack)**

  * `schemas.2B.yaml#/policy/route_rng_policy_v1`
  * `schemas.2B.yaml#/policy/alias_layout_policy_v1`
  * `schemas.2B.yaml#/policy/day_effect_policy_v1`

---

### 6.5 Common definitions (within `schemas.2B.yaml`)

* `$defs.hex64` — `^[a-f0-9]{64}$`
* `$defs.partition_kv` — object (fields-strict); keys are token names (`seed`, `fingerprint`, …), values are strings; `minProperties: 1`.
* `$defs.iso_datetime_utc` — string, RFC 3339/ISO-8601 `date-time` in UTC.

---

### 6.6 Format bindings (Dictionary authority)

* `s0_gate_receipt_2B` — **stored as JSON** at the Dictionary’s receipt path family, partitioned by `fingerprint`.
* `sealed_inputs_v1` — **stored as JSON table** at the Dictionary’s inventory path family, partitioned by `fingerprint`.
* Both outputs are **write-once**; path tokens MUST equal embedded identity.

---

## 7. **Deterministic behaviour (RNG-free) (Binding)**

**Overview.** S0 performs a fixed, reproducible sequence: snapshot the catalogue, verify the upstream gate, resolve and seal the minimum input set, and publish two outputs atomically. No random draws; no network access.

### 7.1 Catalogue snapshot & run identity

1. **Fix identity.** Capture `{seed, manifest_fingerprint}` from the caller’s run context.
2. **Snapshot catalogue.** Read `Dataset Dictionary` and `Artefact Registry` versions; store as `catalogue_resolution.{dictionary_version, registry_version}` in the receipt.
3. **Prohibit literals.** Mark the resolver to accept **Dictionary IDs only**; literal paths are invalid.

### 7.2 Verify upstream gate (must succeed before any 1B/2A read)

4. **Resolve gate artefacts by ID** for the target fingerprint:
   a) `validation_bundle_1B/` (bundle root), b) companion `_passed.flag`.
5. **Load & validate index** (`validation_bundle.index_schema`); assert all `index.path` entries are **relative**.
6. **Recompute bundle digest**: stream the **raw bytes** of each indexed file in **ASCII-lex order of `index.path`** into a single SHA-256; **exclude** `_passed.flag`.
7. **Compare with flag.** Parse `_passed.flag` (`sha256_hex = <hex64>`); if digest ≠ flag value → **Abort**.
8. **Stamp `verified_at_utc`** = current UTC instant; this timestamp will be echoed in outputs.

### 7.3 Resolve & seal required inputs

9. **Resolve by ID** (no content reads yet):
   a) `site_locations` at `seed={seed} / fingerprint={manifest_fingerprint}`;
   b) governed **2B policy pack(s)** (`route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`, as declared in the Dictionary).
10. **Compute per-asset digests** for the inventory row (`sha256_hex`) using this rule, in order of preference:
    i) **Published canonical digest** provided by the producing segment (if present in its manifest/receipt); else
    ii) **Byteset digest**: SHA-256 over the **raw bytes** of all leaf files under the asset’s path, taken in **ASCII-lex order of relative path**; exclude transient control files (e.g., `_passed.flag`).
11. **Assign `version_tag`** from the catalogue for each asset (e.g., release label or `{seed}.{manifest_fingerprint}` where that is the declared tag).

### 7.4 Optional pins (all-or-none set)

12. If the fingerprint declares optional pins, resolve **both** by ID:
    a) `site_timezones` at `seed={seed} / fingerprint={manifest_fingerprint}`,
    b) `tz_timetable_cache` at `fingerprint={manifest_fingerprint}`.
13. **All-or-none rule.** If exactly one is resolvable, record the **WARN** condition for validation; continue. If both are present, include both in the inventory (apply the same digest/tag rules as §7.3).

### 7.5 Materialise outputs (atomic; write-once)

14. **Compose `s0_gate_receipt_2B` (JSON, fields-strict):**

* `fingerprint`, `seed`, `verified_at_utc`.
* `sealed_inputs`: membership list with `{id, partition, schema_ref}` for every sealed asset.
* `catalogue_resolution`: `{dictionary_version, registry_version}` from §7.1.
* `determinism_receipt`: `{engine_commit?, python_version?, platform?, policy_ids[], policy_digests[]}` where `policy_ids/digests` enumerate the sealed 2B policy pack rows from the inventory.

15. **Compose `sealed_inputs_v1` (table, fields-strict):** one row per sealed asset with `{asset_id, version_tag, sha256_hex, path, partition, schema_ref?}`.

* **Row order** is deterministic: sort by `asset_id`, then `path`.
* If multiple IDs resolve to identical bytes, emit **distinct rows** (same `sha256_hex`, different `asset_id`).

16. **Immutability check.** Assert target partitions for both outputs are **empty**; else **Abort**.
17. **Atomic publish.** Write the receipt and inventory to their Dictionary-bound locations. No partial files may become visible.

### 7.6 Post-publish assertions

18. **Path↔embed equality.** Re-open outputs and assert embedded `fingerprint` equals the path token.
19. **Idempotency.** A re-run with the identical sealed set MUST reproduce **byte-identical** outputs; otherwise abort on attempted overwrite.

### 7.7 Prohibitions (always in force)

* **No RNG**; **no network** I/O.
* **No extra reads** beyond §4.2; **no literal paths** at any point.
* **No re-hashing** of upstream assets in downstream states; S0’s receipt is the sole attestation of the gate and sealed set.

---

## 8. **Identity, partitions, ordering & merge discipline (Binding)**

### 8.1 Identity law

* **Run identity:** `{ seed, manifest_fingerprint }` fixed at start of S0.
* **S0 output identity:** **`manifest_fingerprint` only** (fingerprint-scoped products). `seed` may be echoed as metadata but **MUST NOT** appear as a partition token for S0 outputs.

### 8.2 Partitioning

* **Receipt path:** `…/s0_gate_receipt_2B/fingerprint={manifest_fingerprint}/s0_gate_receipt_2B.json`
* **Inventory path:** `…/sealed_inputs_v1/fingerprint={manifest_fingerprint}/sealed_inputs_v1.json`
* **Selection:** exact match on `fingerprint={manifest_fingerprint}`. No wildcarding, globbing, or multi-partition writes.

### 8.3 Path↔embed equality

* Each S0 output **MUST** embed the same `manifest_fingerprint` it is written under. Inequality is an error.

### 8.4 Writer order & serialisation determinism

* **Inventory row order:** primary sort by `asset_id` (lexicographic), secondary by `path`.
* **Receipt field order:** deterministic as defined by the receipt anchor; arrays (`sealed_inputs`, `policy_ids`, `policy_digests`) **MUST** be emitted in a stable order derived from catalogue resolution.
* **Canonical encoding:** UTF-8, no BOM, normalised line endings (`\n` only).

### 8.5 Single-writer, write-once

* Target partitions **MUST** be empty prior to publish.
* If any target exists:

  * **Byte-identical:** treat as no-op (idempotent re-emit).
  * **Byte-different:** **Abort** with immutable-overwrite error.

### 8.6 Atomic publish

* Write to a sibling **staging path** within the same parent directory, then **atomic rename** into the final path. No partial files may become visible at any time.

### 8.7 Concurrency & locking

* At most one active publisher per `(component=2B.S0, manifest_fingerprint)`.
* A second concurrent publisher **MUST**: (a) observe the existing byte-identical artefacts and no-op; or (b) abort on immutable-overwrite if bytes would differ.

### 8.8 Merge discipline

* **No merges.** Receipt and inventory are **unitary artefacts**; no record-level appends, updates, compactions, or merges are permitted. Any change requires a **new** `manifest_fingerprint` and a fresh publish.

### 8.9 Determinism & replay

* Re-running S0 with the **same sealed set** (same catalogue versions, same input bytes) **MUST** reproduce byte-identical outputs.
* Any drift in sealed inputs (e.g., policy tag/digest) **MUST** change the recorded inventory and is therefore **not** the same run.

### 8.10 Downstream propagation

* Downstream 2B states **MUST**:

  * Verify the presence of `s0_gate_receipt_2B` for the target `manifest_fingerprint`.
  * Treat the receipt and inventory as the **sole authority** for what was sealed; they **MUST NOT** re-hash the upstream 1B bundle.

### 8.11 Token hygiene

* Partition tokens **MUST** appear exactly once per path segment (`fingerprint={…}`); no additional, missing, or reordered tokens are allowed.
* Literal paths and environment-injected overrides are prohibited.

### 8.12 Retention & provenance

* Each output **MUST** carry `verified_at_utc` (receipt) and echo provenance in the run-report (inventory row counts, digests recorded).
* Retention/ownership is governed by the Registry; immutability is enforced by this section.

---

## 9. **Acceptance criteria (validators) (Binding)**

**Outcome rule.** **PASS** iff all **Abort** validators succeed. **WARN** validators may fail without blocking publish but MUST be recorded in the run-report.

**V-01 — Gate artefacts present (Abort).**
`validation_bundle_1B/` (root) and companion `_passed.flag` exist for the target `manifest_fingerprint`.

**V-02 — Bundle hash = flag (Abort).**
Recomputed SHA-256 over the bundle index (ASCII-lex by `index.path`, raw bytes; flag excluded) equals the value in `_passed.flag`.

**V-03 — Dictionary-only resolution (Abort).**
Every input read/Trusted asset was resolved by **Dictionary ID**; zero literal paths.

**V-04 — Minimum sealed set present (Abort).**
Sealed assets include: bundle root, `_passed.flag`, `site_locations` at `seed={seed}/fingerprint={manifest_fingerprint}`, and all required 2B policy pack IDs declared for this fingerprint.

**V-05 — Optional pins all-or-none (Warn).**
If any of `{site_timezones, tz_timetable_cache}` is present, both are present; otherwise none. Mixed presence → WARN.

**V-06 — Receipt shape valid (Abort).**
` s0_gate_receipt_2B` validates against `schemas.2B.yaml#/validation/s0_gate_receipt_v1` (fields-strict), including `verified_at_utc` and `catalogue_resolution`.

**V-07 — Inventory shape valid (Abort).**
` sealed_inputs_v1` validates against `schemas.2B.yaml#/validation/sealed_inputs_v1` (fields-strict).

**V-08 — Receipt ↔ inventory membership match (Abort).**
Set of **IDs** in `receipt.sealed_inputs[]` equals set of `inventory.asset_id` (no extras/omissions).

**V-09 — Digests & tags present (Abort).**
Every `sealed_inputs_v1` row has **non-empty** `version_tag` and `sha256_hex` (hex64).

**V-10 — Policy capture coherent (Abort).**
`determinism_receipt.policy_ids`/`policy_digests` are present, equal-length, and each pair matches the corresponding `sealed_inputs_v1` rows for the 2B policy pack(s).

**V-11 — Partition selection exact (Abort).**
Reads used only `site_locations@seed={seed}/fingerprint={manifest_fingerprint}` and fingerprint-only selection for bundle/flag/policies (no wildcards, no cross-seed reads).

**V-12 — No duplicate IDs (Abort).**
`sealed_inputs_v1.asset_id` has no duplicates. (Multiple IDs may reference identical bytes; same-ID duplicates are illegal.)

**V-13 — Path↔embed equality (Abort).**
Each S0 output embeds the same `manifest_fingerprint` as in its path token.

**V-14 — Write-once immutability (Abort).**
Target partitions for the receipt and inventory were empty prior to publish **or** contain byte-identical prior artefacts; otherwise abort.

**V-15 — Idempotent re-emit (Abort).**
A same-inputs rerun reproduces byte-identical receipt and inventory; if not, abort rather than overwrite.

**V-16 — No network & no extra reads (Abort).**
Execution performed with network I/O disabled and accessed **only** the assets enumerated in `sealed_inputs_v1`.

**Reporting.** The run-report MUST include: validator outcomes, counts (`inputs_total`, `inventory_rows`, `digests_recorded`), the recomputed bundle digest, and the list of sealed policy `{id, version_tag, sha256_hex}`.

---

## 10. **Failure modes & canonical error codes (Binding)**

**Code format.** `2B-S0-XYZ` where `XYZ` is a zero-padded integer. **Severity** ∈ {**Abort**, **Warn**}. Each failure MUST be logged with a machine-readable payload containing at least: `code`, `severity`, `message`, `fingerprint`, `seed`, and a `context{}` object as noted below.

### 10.1 Gate & hashing law

* **2B-S0-010 MINIMUM_SET_MISSING (Abort)** — One or more required gate/inputs are absent (`validation_bundle_1B/`, `_passed.flag`, `site_locations@seed,fingerprint`, or required policy pack IDs).
  *Context:* `missing_ids[]`.  *(V-04)*

* **2B-S0-011 BUNDLE_FLAG_HASH_MISMATCH (Abort)** — Recomputed SHA-256 of bundle contents (ASCII-lex by `index.path`, raw bytes, flag excluded) ≠ value in `_passed.flag`.
  *Context:* `expected_sha256`, `actual_sha256`.  *(V-02)*

* **2B-S0-012 BUNDLE_INDEX_INVALID (Abort)** — Bundle index fails shape rules or contains non-relative `path` entries.
  *Context:* `offending_path`.  *(V-02, V-06)*

* **2B-S0-013 FLAG_FORMAT_INVALID (Abort)** — `_passed.flag` line doesn’t match `sha256_hex = <hex64>`.
  *Context:* `flag_line`.  *(V-02)*

### 10.2 Catalogue resolution & prohibitions

* **2B-S0-020 DICTIONARY_RESOLUTION_ERROR (Abort)** — An input ID could not be resolved by the Dataset Dictionary for the required partition(s).
  *Context:* `id`, `partition`.  *(V-03, V-11)*

* **2B-S0-021 PROHIBITED_LITERAL_PATH (Abort)** — Attempted read/write using a literal path not obtained from a Dictionary ID.
  *Context:* `path`.  *(V-03, V-16)*

* **2B-S0-022 UNDECLARED_ASSET_ACCESSED (Abort)** — Asset was read/trusted but not listed in `sealed_inputs_v1`.
  *Context:* `id|path`.  *(V-16)*

* **2B-S0-023 NETWORK_IO_ATTEMPT (Abort)** — Network I/O detected.
  *Context:* `endpoint`.  *(V-16)*

### 10.3 Shape & inventory coherence

* **2B-S0-030 RECEIPT_SCHEMA_INVALID (Abort)** — `s0_gate_receipt_2B` fails schema.
  *Context:* `schema_errors[]`.  *(V-06)*

* **2B-S0-031 INVENTORY_SCHEMA_INVALID (Abort)** — `sealed_inputs_v1` fails schema.
  *Context:* `schema_errors[]`.  *(V-07)*

* **2B-S0-040 INVENTORY_RECEIPT_MISMATCH (Abort)** — Set of IDs in `receipt.sealed_inputs[]` ≠ set of `inventory.asset_id`.
  *Context:* `missing_in_inventory[]`, `missing_in_receipt[]`.  *(V-08)*

* **2B-S0-041 MISSING_DIGEST_OR_TAG (Abort)** — A row in `sealed_inputs_v1` lacks `version_tag` or `sha256_hex`.
  *Context:* `asset_id`.  *(V-09)*

* **2B-S0-042 POLICY_CAPTURE_INCOHERENT (Abort)** — `determinism_receipt.policy_ids/digests` are missing, unequal length, or don’t match the sealed policy rows.
  *Context:* `policy_ids[]`, `policy_digests[]`.  *(V-10)*

* **2B-S0-043 DUPLICATE_ASSET_ID (Abort)** — Duplicate `asset_id` rows in the inventory.
  *Context:* `asset_id`.  *(V-12)*

### 10.4 Identity, partitions, immutability

* **2B-S0-050 PARTITION_SELECTION_INCORRECT (Abort)** — Read didn’t target exactly `site_locations@seed={seed}/fingerprint={fingerprint}` or a fingerprint-only partition for bundle/flag/policies.
  *Context:* `id`, `expected_partition`, `actual_partition`.  *(V-11)*

* **2B-S0-070 PATH_EMBED_MISMATCH (Abort)** — Embedded `fingerprint` in an S0 output ≠ the path token.
  *Context:* `embedded`, `path_token`.  *(V-13)*

* **2B-S0-080 IMMUTABLE_OVERWRITE (Abort)** — Target partition not empty and bytes differ.
  *Context:* `id`, `target_path`.  *(V-14)*

* **2B-S0-081 NON_IDEMPOTENT_REEMIT (Abort)** — Re-emit produced byte-different output for identical sealed inputs.
  *Context:* `id`, `digest_prev`, `digest_now`.  *(V-15)*

* **2B-S0-082 ATOMIC_PUBLISH_FAILED (Abort)** — Staging/rename could not guarantee atomic publish.
  *Context:* `id`, `staging_path`, `final_path`.  *(Runtime)*

### 10.5 Optional pins

* **2B-S0-090 OPTIONAL_PINS_MIXED (Warn)** — Exactly one of `{site_timezones, tz_timetable_cache}` present.
  *Context:* `present_ids[]`, `absent_ids[]`.  *(V-05)*

### 10.6 Standard message fields (Binding)

For each failure, the payload **MUST** include:

* `code`, `severity`, `message` (short, stable), `fingerprint`, `seed`.
* `context{}` with relevant keys per code above.
* `validator` (e.g., `"V-02"`) when the failure is tied to a validator; `"runtime"` otherwise.

### 10.7 Validator → code map (Binding)

| Validator                            | Canonical codes (may emit multiple) |
|--------------------------------------|-------------------------------------|
| **V-01 Gate artefacts present**      | 2B-S0-010                           |
| **V-02 Bundle hash = flag**          | 2B-S0-011, 2B-S0-012, 2B-S0-013     |
| **V-03 Dictionary-only resolution**  | 2B-S0-020, 2B-S0-021                |
| **V-04 Minimum sealed set present**  | 2B-S0-010                           |
| **V-05 Optional pins all-or-none**   | 2B-S0-090 *(Warn)*                  |
| **V-06 Receipt shape valid**         | 2B-S0-030                           |
| **V-07 Inventory shape valid**       | 2B-S0-031                           |
| **V-08 Receipt ↔ inventory match**   | 2B-S0-040                           |
| **V-09 Digests & tags present**      | 2B-S0-041                           |
| **V-10 Policy capture coherent**     | 2B-S0-042                           |
| **V-11 Partition selection exact**   | 2B-S0-050, 2B-S0-020                |
| **V-12 No duplicate IDs**            | 2B-S0-043                           |
| **V-13 Path↔embed equality**         | 2B-S0-070                           |
| **V-14 Write-once immutability**     | 2B-S0-080                           |
| **V-15 Idempotent re-emit**          | 2B-S0-081                           |
| **V-16 No network & no extra reads** | 2B-S0-023, 2B-S0-022, 2B-S0-021     |

**Note.** `2B-S0-082 ATOMIC_PUBLISH_FAILED` is a runtime safeguard associated with §8.6 (atomic publish); it has no direct validator row but remains binding.

---

## 11. **Observability & run-report (Binding)**

### 11.1 Purpose

Emit a **single, structured run-report** that proves what S0 verified, what it sealed, and what it published—sufficient for offline audits and CI. The run-report is **diagnostic (non-authoritative)**; the **receipt** and **inventory** remain the sources of truth.

### 11.2 Emission

* S0 **MUST** write the run-report to **STDOUT** as a single JSON document on successful publish (and on abort, if possible).
* S0 **MAY** also persist the same JSON to an implementation-defined log location. Persisted copies **MUST NOT** be referenced by downstream contracts.

### 11.3 Top-level shape (fields-strict)

A run-report **MUST** contain the following top-level fields:

* `component`: `"2B.S0"`
* `fingerprint`: `<hex64>`
* `seed`: `<string>`
* `verified_at_utc`: ISO-8601 UTC (same value written in the receipt)
* `catalogue_resolution`: `{ dictionary_version: <semver>, registry_version: <semver> }`
* `gate`:

  * `bundle_index_count`: `<int>`
  * `bundle_sha256_expected`: `<hex64>` *(from `_passed.flag`)*
  * `bundle_sha256_actual`: `<hex64>` *(recomputed)*
  * `flag_path`: `<string>` *(Dictionary-resolved)*
* `inputs_summary`:

  * `inputs_total`: `<int>`
  * `required_present`: `<int>`
  * `optional_pins_present`: `<int>` *(0 or 2)*
  * `policy_ids`: `[<string>…]`
  * `policy_digests`: `[<hex64>…]` *(1:1 with `policy_ids`)*
* `inventory_summary`:

  * `inventory_rows`: `<int>`
  * `digests_recorded`: `<int>`
  * `duplicate_byte_sets`: `<int>` *(count of distinct `sha256_hex` shared by >1 `asset_id`)*
* `publish`:

  * `targets`: `[ { id: "s0_gate_receipt_2B", path: <string>, bytes: <int> }, { id: "sealed_inputs_v1", path: <string>, bytes: <int> } ]`
  * `write_once_verified`: `<bool>`
  * `atomic_publish`: `<bool>`
* `validators`: `[ { id: "V-01", status: "PASS|FAIL|WARN", codes: [ "2B-S0-011", … ] } … ]`
* `summary`:

  * `overall_status`: `"PASS" | "FAIL"` *(WARNs allowed under PASS)*
  * `warn_count`: `<int>`
  * `fail_count`: `<int>`
* `environment`:

  * `engine_commit`: `<string>` *(if available)*
  * `python_version`: `<string>`
  * `platform`: `<string>`
  * `network_io_detected`: `<int>` *(events; MUST be 0)*

### 11.4 Evidence & samples (bounded)

To aid audits without leaking large payloads, S0 **MUST** include:

* `sealed_inputs_sample`: up to **20** inventory rows (deterministic pick: lexicographic by `asset_id`, then first N). Each row contains `{ asset_id, version_tag, sha256_hex, path, partition }`.
* `gate_index_sample`: up to **20** `index.path` entries (deterministic pick: ASCII-lex first N).

Field values in samples **MUST** be copied from the authoritative artefacts; no reformatting.

### 11.5 Counters (minimum set)

S0 **MUST** emit the following counters; units are integers unless noted:

* `inputs_total`, `required_present`, `optional_pins_present`
* `inventory_rows`, `digests_recorded`, `duplicate_byte_sets`
* `bundle_index_count`
* `publish_bytes_total` *(sum of published artefact sizes)*
* Durations (milliseconds): `gate_verify_ms`, `inventory_emit_ms`, `publish_ms`

### 11.6 Determinism of lists

Arrays in the run-report **MUST** be emitted in deterministic order:

* `policy_ids`/`policy_digests`: lexicographic by `policy_id` with 1:1 alignment.
* `validators`: sorted by validator ID (`"V-01" … "V-16"`).
* `targets`: fixed order `["s0_gate_receipt_2B", "sealed_inputs_v1"]`.
* Samples per §11.4 follow their stated deterministic picks.

### 11.7 PASS/WARN/FAIL semantics

* `overall_status = "PASS"` iff **all Abort-class validators** succeeded.
* Any WARN-class validator failure increments `warn_count` and **MUST** appear in `validators[]` with `status: "WARN"`.
* On any Abort-class failure, `overall_status = "FAIL"`; publish **MUST NOT** occur, but an attempted run-report **SHOULD** still be emitted with partial data where available.

### 11.8 Privacy & retention

* Run-report content **MUST NOT** include raw data bytes; only digests, counts, paths, and IDs.
* Retention is governed by the Registry’s policy for diagnostic logs; the run-report itself is not an authoritative artefact and **MUST NOT** be hashed into any bundle.

### 11.9 ID-to-artifact echo

For traceability, S0 **MUST** echo a compact list:

```
id_map: [
  { id: "validation_bundle_1B", path: "<…/validation/fingerprint=…/>" },
  { id: "site_locations",        path: "<…/site_locations/seed=…/fingerprint=…/>" },
  { id: "route_rng_policy_v1",   path: "<…>" }, …
]
```

Paths **MUST** be the exact Dictionary-resolved values used during the run.

---

## 12. **Performance & scalability (Informative)**

### 12.1 Workload model

Let:

* **B** = number of files listed in the upstream **1B bundle index**
* **Σbundle** = total bytes of those B files (raw, as read for hashing)
* **N** = number of assets recorded in `sealed_inputs_v1` (gate artefacts + `site_locations` + policy packs [+ optional pins])
* **Σdigest** = additional bytes hashed for assets that **lack** a canonical digest (ideally small; e.g., policy packs)

S0 is predominantly **I/O-bound**. CPU cost is minimal (SHA-256 over streamed bytes + JSON serialisation).

### 12.2 Time & space characteristics

* **Time complexity:** `O(Σbundle + Σdigest) + O(N)` for catalogue resolution and inventory emission.
* **Memory footprint:** `O(1)` w.r.t. data size (streaming hash; fixed-size buffers). Avoid materialising large datasets in memory.
* **Output size:** two small JSON artefacts (receipt, inventory); constant-scale per run.

### 12.3 I/O discipline (determinism-friendly)

* **Streaming hash:** Read bundle files in **ASCII-lex order of `index.path`**, feed bytes directly into a single SHA-256 stream.
* **Prefetching:** Implementations MAY prefetch/read-ahead, but the **effective hash order** MUST be identical to the lexicographic concatenation.
* **Digest reuse:** Prefer **published canonical digests** (e.g., from upstream manifests) to avoid re-hashing large egresses; fall back to a streamed byteset hash only when a canonical digest is unavailable.
* **Filesystem locality:** Perform **atomic rename within the same filesystem** as the final path to avoid cross-device penalties.

### 12.4 Concurrency & throughput

* **Within a fingerprint:** Single logical publisher (see §8). Background prefetch is allowed; final publish remains single-writer.
* **Across fingerprints/seeds:** Independent runs parallelise trivially; S0 has no cross-run locks.
* **Tiny-file bundles:** When B is large and files are small, throughput is dominated by open/close latency. Use sequential access and OS readahead to mitigate syscall overhead.

### 12.5 Failure, retry & idempotency

* **Cold vs warm cache:** First pass over the bundle may be slower; OS cache typically accelerates retries.
* **Idempotent re-emit:** Re-running S0 with identical sealed inputs should become a near-no-op (metadata refresh + equality checks).
* **Partial writes:** Always stage then atomic-rename to prevent partial artefacts; on failure, retry is safe due to write-once semantics.

### 12.6 Observability budgets (guidance)

* Track and alert on: `gate_verify_ms`, `inventory_emit_ms`, `publish_ms`, `bundle_index_count`, `publish_bytes_total`.
* CI can flag regressions when **`Σbundle` or B** grows unexpectedly (e.g., spike in tiny files), or when `gate_verify_ms` outliers occur without a corresponding data growth.

### 12.7 Scalability limits & mitigations

* **Large Σbundle:** Bound by sequential read bandwidth; ensure hashing is truly streaming and not buffered into memory wholesale.
* **Many policy packs (high N):** Inventory emission is linear; keep policy packs compact and with canonical digests to avoid extra hashing.
* **Optional pins present:** Adds only resolution + small metadata; no additional heavy I/O unless their canonical digests are missing.

### 12.8 Non-goals

* No network I/O, compression, or content transforms occur in S0. Performance tuning must **not** alter hashing order, catalogue resolution rules, or write-once semantics.

---

## 13. **Change control & compatibility (Binding)**

### 13.1 Scope

This section governs **what may change** after this spec is ratified and **how** such changes are versioned and rolled out. It applies to: the S0 procedure, its **outputs** (`s0_gate_receipt_2B`, `sealed_inputs_v1`), the **minimum sealed set**, and **validators/error codes**.

---

### 13.2 Stable, non-negotiable surfaces (unchanged without a **major** bump)

S0 **MUST NOT** change the following within the same major version:

* **Gate law:** upstream 1B bundle root + `_passed.flag`; **No PASS → No read**; hashing law (ASCII-lex by `index.path`; hash raw bytes; flag excluded).
* **Outputs & partitions:** presence of both outputs; fingerprint-only partitioning; **path↔embed equality**; write-once + atomic publish.
* **Output shapes & IDs:** anchor names and required fields of
  `schemas.2B.yaml#/validation/s0_gate_receipt_v1` and
  `schemas.2B.yaml#/validation/sealed_inputs_v1`.
* **Minimum sealed set:** `validation_bundle_1B/`, `_passed.flag`, `site_locations@seed,fingerprint`, and **required 2B policy pack(s)**.
* **Prohibitions:** dictionary-only resolution; no literal paths; no network I/O.
* **Acceptance posture:** the set of **Abort** validators (by ID) and their semantics.

Any change here is **breaking** and requires a **new major** of this spec and schema anchors.

---

### 13.3 Backward-compatible changes (allowed with **minor** or **patch** bump)

* **Editorial clarifications** (wording, examples) that do not change behaviour. *(patch)*
* **Run-report** additions (new fields/counters/samples) — diagnostic only. *(minor/patch)*
* **Receipt `determinism_receipt`**: adding **optional** fields. *(minor)*
* **Inventory**: adding an **optional** `schema_ref` (already allowed) or extra optional columns that validators ignore. *(minor)*
* **Validators**: adding **WARN-class** checks; tightening messages/contexts; mapping multiple codes to an existing validator. *(minor)*
* **Optional pins**: permitting them where previously absent, keeping the **all-or-none** rule and **WARN** on mixed presence. *(minor)*
* **Policy packs**: introducing **optional** policy artefacts (diagnostic) that are **not** part of the minimum sealed set. *(minor)*

---

### 13.4 Breaking changes (require **major** bump + migration)

* Changing **required** fields or anchor names of S0 outputs; re-partitioning; renaming output IDs.
* Altering the **hashing law**, gate artefact identities, or bundle location semantics.
* Promoting any **optional** item to the **minimum sealed set** (e.g., making 2A pins mandatory).
* Changing the **required policy pack list** (add/remove/rename) or their semantics such that V-04/V-10 differ.
* Reclassifying a **WARN** validator to **Abort**, or adding a new **Abort** validator that can fail for previously valid runs.
* Allowing **literal paths** or network I/O, or removing dictionary-only resolution.

---

### 13.5 SemVer & release discipline

* **Major**: any change listed in §13.4 → bump spec, schema anchors (e.g., `…/s0_gate_receipt_v2`), Dictionary IDs if needed. Old and new may coexist during a migration window.
* **Minor**: additive, backward-compatible behaviour (new optional diagnostics/WARN validators/fields).
* **Patch**: editorial clarifications only (no shape, no validators, no identity change).

Status **`frozen`** constrains post-freeze edits to **patch-only** unless a formally ratified major/minor is published.

---

### 13.6 Compatibility guarantees to downstream states (S1–S8)

* S1–S8 **MAY** rely on: the **presence and shapes** of S0 outputs; fingerprint partitioning; dictionary-only resolution evidence; and the **gate verification** having been performed (they **MUST NOT** re-hash the 1B bundle).
* Downstreams **MUST NOT** depend on the **run-report** structure; it is non-authoritative.
* If a new major is published (e.g., `…/s0_gate_receipt_v2`), downstreams MUST either:
  (a) continue to accept `v1` until EOL, or (b) advertise support for both during a migration window.

---

### 13.7 Deprecation & migration protocol

* **Proposal → Ratification → Release** documented in the change log with: impact, validator deltas, new anchors, migration steps.
* **Dual-publish window (recommended for majors):** S0 MAY emit both `…/v1` and `…/v2` outputs **in parallel** (v2 authoritative; v1 legacy) for a time-boxed period.
* **EOL notice:** at least one release cycle of advance notice; explicit date after which legacy anchors are no longer emitted.

---

### 13.8 Rollback policy

* Because outputs are **write-once**, rollback means **publishing a new fingerprint** under the old major/minor with the prior behaviour. No in-place mutation is allowed.
* Downstreams select by **fingerprint**; therefore rollback requires re-pointing consumers to the prior fingerprint or replaying with the older catalogue.

---

### 13.9 Evidence of compatibility

* Each release **MUST** include: schema diffs, validator table diffs, and a conformance run demonstrating that previously valid S0 inputs still **PASS** (for minor/patch).
* CI **MUST** execute a regression suite: inventory equality, path↔embed checks, and idempotent re-emit under unchanged inputs.

---

### 13.10 Registry/Dictionary coordination

* Dictionary changes that affect S0 (IDs, path families, partition tokens) are **breaking** unless accompanied by new anchors/IDs and a migration window.
* Registry changes limited to **metadata** (licence/owner/retention) are **compatible**; changes that alter **existence** of required artefacts (e.g., removing a policy pack) are **breaking**.

---

### 13.11 Optional pins policy (consistency rule)

* The all-or-none presence rule for `{site_timezones, tz_timetable_cache}` is stable. Making these **required** or changing the rule is **breaking**; adding additional optional pins is **minor** if validators remain WARN-only.

---

### 13.12 Validator/code namespace stability

* Validator IDs (`V-01`…`V-16`) and canonical codes (`2B-S0-…`) are **reserved**. New codes may be added; existing codes’ meanings **MUST NOT** change within a major.

---

## Appendix A — Normative cross-references *(Informative)*

> This appendix lists the authoritative artefacts and anchors that S0 references. Shapes are governed by **schemas**; ID→path/partition/format by the **Dataset Dictionary**; metadata/ownership by the **Artefact Registry**.

### A.1 Authority chain (this segment)

* **Schema pack (shape authority):** `schemas.2B.yaml`

  * Validation/output anchors used by S0:

    * `#/validation/s0_gate_receipt_v1` — gate receipt
    * `#/validation/sealed_inputs_v1` — sealed-inputs inventory
  * Policy anchors captured (IDs only, bytes sealed):

    * `#/policy/route_rng_policy_v1`
    * `#/policy/alias_layout_policy_v1`
    * `#/policy/day_effect_policy_v1`
  * Common defs: `#/$defs/hex64`, `#/$defs/partition_kv`, `#/$defs/iso_datetime_utc`
* **Dataset Dictionary (catalogue authority):** `dataset_dictionary.layer1.2B.yaml`

  * Output IDs & path families:

    * `s0_gate_receipt_2B` → `…/fingerprint={manifest_fingerprint}/s0_gate_receipt_2B.json`
    * `sealed_inputs_v1` → `…/fingerprint={manifest_fingerprint}/sealed_inputs_v1.json`
  * Input IDs S0 resolves:

    * `validation_bundle_1B` (root), `_passed.flag`
    * `site_locations` (seed, fingerprint)
    * `route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`
    * *(optional pins)* `site_timezones`, `tz_timetable_cache`
* **Artefact Registry (metadata authority):** `artefact_registry_2B.yaml`

  * Ownership/retention for the above IDs; cross-layer pointers (1B egress, 2A pins).

### A.2 Upstream gate (Layer-1 · Segment 1B)

* **PASS bundle (root):** `data/layer1/1B/validation/fingerprint={manifest_fingerprint}/`

  * **Index shape (hashing law):** `schemas.1A.yaml#/validation/validation_bundle.index_schema`
  * **Flag format:** `_passed.flag` with single line `sha256_hex = <hex64>`
* **Egress consumed by 2B:**

  * `site_locations` → `data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/`
  * **Shape:** `schemas.1B.yaml#/egress/site_locations`

### A.3 Optional pins (Layer-2 · Segment 2A)

* **`site_timezones`** → `data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/`
  **Shape:** `schemas.2A.yaml#/egress/site_timezones`
* **`tz_timetable_cache`** → `data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/`
  **Shape:** `schemas.2A.yaml#/egress/tz_timetable_cache`

### A.4 Outputs produced by this state (2B.S0)

* **`s0_gate_receipt_2B`** (JSON; fingerprint-scoped)
  **Shape:** `schemas.2B.yaml#/validation/s0_gate_receipt_v1`
* **`sealed_inputs_v1`** (JSON table; fingerprint-scoped)
  **Shape:** `schemas.2B.yaml#/validation/sealed_inputs_v1`

### A.5 Policy packs captured (IDs; bytes & digests sealed)

* `route_rng_policy_v1` — Philox sub-stream layout/budgets for routing states
* `alias_layout_policy_v1` — alias table byte layout/endianness/alignment
* `day_effect_policy_v1` — daily modulation cadence/variance/clipping

### A.6 Identity & tokens (path discipline)

* **Tokens:** `seed={seed}`, `fingerprint={manifest_fingerprint}`
* **Partition law:** S0 outputs are **fingerprint-only**; `site_locations` reads require **seed + fingerprint**.
* **Path↔embed equality:** embedded `fingerprint` in S0 outputs must equal the path token.

### A.7 Context documents

* **Segment overview:** `state-flow-overview.2B.txt` *(context only; this spec governs)*
* **Layer Identity & Gate laws:** project-wide authority note (No PASS → No read; hashing law; write-once discipline).

---