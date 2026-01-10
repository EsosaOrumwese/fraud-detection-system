# State 2A.S3 — Time-table / cache build

## 1. Document metadata & status **(Binding)**

**Title:** Layer-1 · Segment 2A · State-3 — Time-table / cache build
**Short name:** 2A.S3 “Timetable cache”
**Layer/Segment/State:** L1 / 2A (Civil Time) / S3
**Doc ID:** `layer1/2A/state-3`
**Version (semver):** `v1.0.0-alpha` *(advance per change control)*
**Status:** `draft | alpha | frozen` *(normative at ≥ `alpha`; semantics locked at `frozen`)*
**Owners:** Design Authority (DA): ‹name› • Review Authority (RA): ‹name›
**Effective date:** ‹YYYY-MM-DD›
**Canonical location:** ‹repo path to this spec file›

**Normative cross-references (pointers only):**

* **2A.S0 Gate & Sealed Inputs:** `schemas.2A.yaml#/validation/s0_gate_receipt_v1` (receipt for target `manifest_fingerprint`).
* **Inputs:** `schemas.2A.yaml#/ingress/tzdb_release_v1` (sealed IANA tzdb release); `schemas.ingress.layer1.yaml#/tz_world_2025a` (tzid coverage domain, read-only).
* **Output (this state):** `schemas.2A.yaml#/cache/tz_timetable_cache` (cache manifest).
* **Catalogue & registry:** Dataset Dictionary entries for `tz_timetable_cache` (partition `[manifest_fingerprint]`) and `tzdb_release`; Artefact Registry stanzas recording lineage `tz_timetable_cache → tzdb_release`.
* **Layer-1 governance:** Identity & Path Law (path↔embed equality), Gate Law (“No PASS → No Read”), Hashing/Fingerprint Law, Numeric Policy.

**Conformance & interpretation:**

* Sections marked **Binding** are normative; **Informative** sections do not create obligations.
* Keywords **MUST/SHALL/SHOULD/MAY** follow RFC 2119/8174.
* This is a **design specification**: it defines behaviours, identities, inputs/outputs, and inter-state contracts; it does **not** prescribe implementations or pseudocode.

**Change log (summary):**

* `v1.0.0-alpha` - Initial specification for 2A.S3 (compile tzdb into manifest_fingerprint-scoped `tz_timetable_cache`). Subsequent edits follow §13 Change Control.

---

### Contract Card (S3) - inputs/outputs/authorities

**Inputs (authoritative; see Section 3.2 for full list):**
* `s0_gate_receipt_2A` - scope: FINGERPRINT_SCOPED; source: 2A.S0
* `tzdb_release` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required
* `tz_world_2025a` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required

**Authority / ordering:**
* S3 compiles a manifest_fingerprint-scoped cache; no order authority is created.

**Outputs:**
* `tz_timetable_cache` - scope: FINGERPRINT_SCOPED; gate emitted: none

**Sealing / identity:**
* External inputs (ingress/reference/1B egress/2A policy) MUST appear in `sealed_inputs_2A` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required sealed inputs or schema violations -> abort; no outputs published.

## 2. Purpose & scope **(Binding)**

**Intent.** Transform the sealed **IANA tzdb release** into a **manifest_fingerprint-scoped transition cache** for all relevant `tzid`s, suitable for fast, deterministic civil-time lookups in downstream states.

**Objectives (normative).** 2A.S3 SHALL:

* **Assert eligibility:** Rely on the **2A.S0 gate receipt** for the target `manifest_fingerprint` before referencing any inputs.
* **Consume sealed inputs only:** Read **`tzdb_release`** (required) and **`tz_world`** (read-only domain for coverage checks) as sealed in S0; no site-level data is read.
* **Compile a canonical index:** Produce a compact timetable/cache for each `tzid` (offsets & change instants) and record a deterministic **`tz_index_digest`** of the compiled index (canonicalisation & hashing law by reference).
* **Emit cache artefact:** Publish **`tz_timetable_cache`** under **`[manifest_fingerprint]`** with a manifest including at least `manifest_fingerprint`, `tzdb_release_tag`, `tzdb_archive_sha256`, `tz_index_digest`, `rle_cache_bytes`, and `created_utc`.
* **Remain RNG-free & idempotent**; set `created_utc = S0.receipt.verified_at_utc`.

**In scope.**

* Resolving `tzdb_release` (version tag + archive digest) and compiling per-`tzid` transitions.
* Optional coverage verification that **every `tzid` present in sealed `tz_world`** is included in the compiled index.
* Emitting cache files and a manifest that fully identify the compiled content.

**Out of scope.**

* Per-site processing (S1/S2), overrides, or geometry.
* Legality/DST validation and reporting (S4).
* Segment-level PASS bundle/flag emission (S5).
* Any implementation guidance beyond the canonical outputs and identities defined here.

**Interfaces (design relationship).**

* **Upstream:** Consumes S0 receipt (gate), `tzdb_release` (required), and `tz_world` (coverage domain), all for the target `manifest_fingerprint`.
* **Downstream:** S4 (legality) and other consumers read **`tz_timetable_cache`** by `manifest_fingerprint` to evaluate gaps/folds and legal times; S5 will gate 2A egress using the standard bundle/flag.

**Completion semantics.** S3 is complete when **`tz_timetable_cache`** is written under the correct `manifest_fingerprint` partition, the manifest schema-validates, **path↔embed equality** holds, `created_utc` is deterministic as specified, and the compiled index passes coverage and integrity checks.

---

## 3. Preconditions & sealed inputs **(Binding)**

### 3.1 Preconditions

S3 SHALL begin only when:

* **Gate verified.** A valid **2A.S0 gate receipt** exists and schema-validates for the target `manifest_fingerprint`. S3 relies on this receipt for read permission and sealed-input identity; it does not re-hash upstream bundles.
* **Run identity fixed.** The **`manifest_fingerprint`** is selected and constant for the run; S3 is manifest_fingerprint-scoped (no `seed`). The Dictionary lists the S3 output under a manifest_fingerprint-only path. 
* **Authorities addressable.** The 2A schema pack, Dataset Dictionary, and Artefact Registry entries required below resolve without placeholders (Schema=shape, Dictionary=IDs→paths/partitions/format, Registry=existence/licence/retention).
* **Posture.** S3 is **RNG-free** and deterministic; observational fields are derived from sealed inputs (cf. `created_utc`). 

### 3.2 Sealed inputs (consumed in S3)

S3 **consumes only** the following inputs. All MUST be resolved **by ID via the Dataset Dictionary** (no literal paths) and be authorised by the Registry. Where an input is not manifest_fingerprint-partitioned, its **bytes and version tag are fixed by the S0 sealed manifest** for this `manifest_fingerprint`. 

1. **`tzdb_release` (required)**
   *Role:* authoritative IANA tzdata archive and release tag used to compile the transition index.
   *Shape:* `schemas.2A.yaml#/ingress/tzdb_release_v1`. 
   *Catalogue/Registry:* registered as a cross-layer ingress artefact.

2. **`tz_world_<release>` polygons (read-only; required for tzid coverage checks)**
   *Role:* canonical domain of `tzid` values for this programme; used to verify that every `tzid` present in `tz_world` is represented in the compiled cache.
   *Shape:* `schemas.ingress.layer1.yaml#/tz_world_2025a`. 
   *Catalogue/Registry:* listed as a cross-layer reference sealed by S0. 

3. **2A.S0 gate receipt (evidence)**
   *Role:* proves eligibility to read the sealed inputs for the target `manifest_fingerprint`; binds the exact `tzdb_release`/`tz_world` bytes via the S0 manifest/inventory. (Read is verification-only; no re-hash.) 

> *Note:* S3 **does not** read site-level data (`site_locations`, `s1_tz_lookup`, `site_timezones`). Its sole purpose is compiling a manifest_fingerprint-scoped cache from `tzdb_release`. The S3 output surface is catalogued at
> `data/layer1/2A/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/`. 

### 3.3 Binding constraints on input use

* **Same-manifest_fingerprint constraint.** All fingerprinted references and sealed input identities **MUST** match the S0 `manifest_fingerprint`. S3 SHALL use only the assets sealed for that manifest_fingerprint in the S0 manifest. 
* **Dictionary-only resolution.** Inputs SHALL be resolved by **ID → path/format** via the Dataset Dictionary; literal/relative paths are **forbidden**. 
* **Shape authority.** JSON-Schema anchors are the **sole** shape authority; S3 SHALL NOT assume undeclared fields or relax declared domains. 
* **Non-mutation.** S3 SHALL NOT mutate or persist any input datasets; it emits only `tz_timetable_cache`. 

### 3.4 Null/empty allowances

* **None.** Both `tzdb_release` and `tz_world_<release>` MUST be present as sealed inputs for the target manifest_fingerprint. Absence or unreadability is a hard failure and shall be surfaced by S3 validators (see §9/§10).

---

## 4. Inputs & authority boundaries **(Binding)**

### 4.1 Authority model (normative)

* **Shape authority:** JSON-Schema anchors fix columns/fields, domains, and strictness (S3 relies on `schemas.2A.yaml#/ingress/tzdb_release_v1`, `#/cache/tz_timetable_cache`, and `schemas.ingress.layer1.yaml#/tz_world_<release>`).
* **Catalogue authority:** The Dataset Dictionary fixes **IDs → canonical paths/partitions/format**. S3 **MUST** resolve inputs by ID only (no literal/relative paths).
* **Existence/licensing authority:** The Artefact Registry declares presence, licence class, retention, and lineage (`tz_timetable_cache → tzdb_release`).
* **Precedence on disputes:** **Schema › Dictionary › Registry** (Schema wins for shape; Dictionary wins for path/partitions; Registry supplies existence/licence).
* **Gate law:** Read permission derives from the **2A.S0 receipt** for the target `manifest_fingerprint`; S3 does **not** re-hash upstream bundles.
* **Identity law:** **Path↔embed equality** applies wherever lineage appears both in path tokens and manifest fields.

### 4.2 Per-input boundaries

1. **`tzdb_release` (required)**

* **Shape:** `schemas.2A.yaml#/ingress/tzdb_release_v1` (release tag, archive digest).
* **Catalogue/Registry:** Cross-layer ingress artefact sealed in S0 (version tag + SHA-256).
* **Boundary:** S3 **MAY** read the archive bytes to compile transitions and **SHALL** record tag/digest in the output manifest. S3 **SHALL NOT** fetch from the network, mutate the artefact, or rely on any unsealed tzdb source.

2. **`tz_world_<release>` polygons (read-only; membership/coverage only)**

* **Shape:** `schemas.ingress.layer1.yaml#/tz_world_<release>` (e.g., `…#/tz_world_2025a`).
* **Catalogue/Registry:** Cross-layer reference sealed in S0.
* **Boundary:** S3 **MAY** read the **set of `tzid` values** for coverage checks; it **SHALL NOT** perform geometry operations, reprojection, or modify the surface.

3. **2A.S0 gate receipt (evidence)**

* **Shape:** `schemas.2A.yaml#/validation/s0_gate_receipt_v1`.
* **Catalogue:** Fingerprint-scoped receipt.
* **Boundary:** S3 **SHALL** verify presence and **manifest_fingerprint match**; it **SHALL NOT** re-compute any bundle hash or depend on site-level datasets.

> **Out of scope inputs:** S3 **MUST NOT** read site data (`site_locations`, `s1_tz_lookup`, `site_timezones`) or policy assets (`tz_overrides`, `tz_nudge`).

### 4.3 Validation responsibilities (S3 scope)

* **Receipt check:** S0 receipt exists and matches the target `manifest_fingerprint`.
* **Dictionary resolution:** `tzdb_release` and `tz_world_<release>` resolve by ID; paths/format match the Dictionary.
+ **Pinning & tag/digest:** `tzdb_release` has a supported release tag and a well-formed SHA-256, and S3 SHALL verify (offline) that the SHA-256 of the sealed archive bytes equals the sealed digest; no network sources permitted.
* **Coverage domain:** `tz_world` tzid set is readable (non-empty) and used for coverage checks (see §9).
* **No literal paths / no mutation:** Inputs are read-only and resolved strictly via the catalogue.

### 4.4 Prohibitions

S3 **SHALL NOT**:

* use literal/implicit paths or network sources;
* read or rely on any site-level datasets;
* mutate, subset, or rewrite `tzdb_release`/`tz_world`;
* introduce RNG or wall-clock time (observational fields derive from sealed inputs);
* emit anything other than `tz_timetable_cache` under the manifest_fingerprint partition.

---

## 5. Outputs (datasets) & identity **(Binding)**

### 5.1 Primary deliverable — `tz_timetable_cache`

**Role.** Fingerprint-scoped cache of time-zone transitions compiled from the sealed tzdb; referenced by downstream states (e.g., legality checks).

**Shape (authority).** `schemas.2A.yaml#/cache/tz_timetable_cache` (**object manifest; columns/fields are strict**) fixing at least:

* `manifest_fingerprint : hex64`
* `tzdb_release_tag : string`
* `tzdb_archive_sha256 : hex64`
* `tz_index_digest : hex64` *(canonical digest of the compiled index)*
* `rle_cache_bytes : uint64` *(total bytes of emitted cache payloads)*
* `created_utc : rfc3339_micros` *(= S0.receipt.verified_at_utc)*

**Catalogue (Dictionary).** Path family (manifest_fingerprint-only):
`data/layer1/2A/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/`
Dictionary governs filenames/layout (e.g., manifest filename, cache shard names) and format (`files` + JSON manifest).

**Registry (existence/licensing/lineage).** Registered as a cache artefact with lineage
`tz_timetable_cache → tzdb_release` (S3 reads tzdb; `tz_world` may be read only for coverage checks and is **not** a content dependency).

### 5.2 Identity & path law

* **Partitions (binding):** `[manifest_fingerprint]` only (no `seed`).
* **Path↔embed equality (binding):** Embedded `manifest_fingerprint` in the manifest **MUST** byte-equal the `manifest_fingerprint` path token.
* **Deterministic timestamp:** `created_utc` **MUST** equal `S0.receipt.verified_at_utc` for the target manifest_fingerprint.

### 5.3 Write posture & merge discipline

* **Single-writer, write-once per manifest_fingerprint.** If any artefact already exists under the target manifest_fingerprint, a re-emit **MUST** be byte-identical; otherwise **ABORT**.
* **Atomic publish.** Stage → fsync → single atomic move into the manifest_fingerprint partition.
* **File order non-authoritative.** No consumer may infer semantics from file ordering; the manifest is the sole authority for cache contents.

### 5.4 Format, licensing & retention (by catalogue/registry)

* **Format:** Manifest (JSON) plus one or more cache files (Dictionary governs names/layout).
* **Licence/TTL:** As declared in Dictionary/Registry (e.g., Proprietary-Internal; typical retention 365 days).

**Binding effect.** Downstream consumers **MUST** select `tz_timetable_cache` by `manifest_fingerprint`, resolve via the **Dataset Dictionary**, verify manifest shape, enforce **path↔embed equality**, and treat the partition as immutable once published.

---

## 6. Dataset shapes & schema anchors **(Binding)**

**Shape authority.** JSON-Schema anchors are the **sole** source of truth for fields, domains, strictness, and identity. S3 binds to:

* **Output:** `schemas.2A.yaml#/cache/tz_timetable_cache`.
* **Inputs:** `schemas.2A.yaml#/ingress/tzdb_release_v1` and `schemas.ingress.layer1.yaml#/tz_world_2025a` (tzid coverage domain).

### 6.1 Output artefact — `tz_timetable_cache` (manifest_fingerprint-scoped cache)

* **ID → Schema:** `schemas.2A.yaml#/cache/tz_timetable_cache` (**object manifest; strict fields**).
  **Manifest fields (minimum):**
  `manifest_fingerprint (hex64)`, `tzdb_release_tag (string)`, `tzdb_archive_sha256 (hex64)`,
  `tz_index_digest (hex64)`, `rle_cache_bytes (uint64)`, `created_utc (rfc3339_micros)`.
* **Dictionary binding (catalogue authority):**
  `data/layer1/2A/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/` · **partitioning:** `[manifest_fingerprint]` · **format:** files (+ JSON manifest). 
* **Registry (existence/licensing/lineage):** registered as a cache with lineage **`tz_timetable_cache → tzdb_release`**. 

### 6.2 Referenced inputs (read-only in S3)

* **`tzdb_release` (required):** `schemas.2A.yaml#/ingress/tzdb_release_v1` (release tag + archive digest).
  **Dictionary path:** `artefacts/priors/tzdata/{release_tag}/` (unpartitioned). 
* **`tz_world_2025a` (required for coverage checks):** `schemas.ingress.layer1.yaml#/tz_world_2025a` (GeoParquet, WGS84) — authoritative **tzid** domain; sealed by S0 and listed in the 2A catalogue. 

### 6.3 Identity & partition posture (binding)

* **Output partitions:** `[manifest_fingerprint]` **only** (no `seed`). **Path↔embed equality** MUST hold: the embedded `manifest_fingerprint` in the manifest **byte-equals** the partition token. 
* **Write posture:** single-writer, write-once per manifest_fingerprint; any re-emit must be **byte-identical** or **ABORT** (Registry posture). 

### 6.4 Binding constraints (shape-level)

* **Strict fields.** The cache manifest is **columns/fields-strict**—undeclared fields are invalid. (Schema anchor governs.) 
* **Deterministic timestamp.** `created_utc` **MUST** equal `S0.receipt.verified_at_utc` (observational fields derive from sealed inputs).
* **Integrity.** `tz_index_digest` equals the canonical digest of the compiled index; `rle_cache_bytes > 0`; all cache files referenced by the manifest exist. (Validators enforce.)
* **Coverage.** The compiled index **MUST** include every `tzid` present in the sealed `tz_world` release (superset allowed). 

*Result:* With these anchors and catalogue/registry bindings, S3’s single deliverable `tz_timetable_cache` is fully specified; inputs are pinned to their authoritative schemas; and the manifest_fingerprint-only identity matches the Dictionary and Registry contracts.

---

## 7. Deterministic behaviour (RNG-free) **(Binding)**

### 7.1 Posture & scope

* S3 is **strictly deterministic** and **RNG-free**.
* Read permission derives from the **2A.S0 gate receipt** for the target `manifest_fingerprint`.
* Inputs are resolved **only via the Dataset Dictionary**; literal/relative paths are forbidden.
* S3 reads **`tzdb_release`** (required) and **`tz_world_<release>`** (read-only for tzid coverage). It **does not** read any site-level datasets.
* Observational fields are deterministic: `created_utc` **SHALL** equal `S0.receipt.verified_at_utc`.

### 7.2 Canonical processing order

1. **Verify gate.** Assert presence & schema validity of the 2A.S0 receipt for the target `manifest_fingerprint`.
2. **Bind sealed inputs.**

   * Bind **`tzdb_release`**; record its `release_tag` and `archive_sha256`.
   * Bind **`tz_world_<release>`**; extract the authoritative set of `tzid` values for coverage checks.
3. **Compile transitions (per `tzid`).**

   * Parse the sealed tzdb into a per-`tzid` sequence of **civil-time change instants** (UTC) and **offset minutes**.
   * For each `tzid`, the transition instants **MUST** be strictly increasing; offset minutes **MUST** fall within the layer bounds (−900…+900) (see V-13).
   * If consecutive transitions would yield **identical effective offsets**, **coalesce** them (remove redundant entries) without altering semantics.
4. **Normalise & canonicalise.**

   * Establish a **stable total order**: primary sort by `tzid` (ASCII-lex), secondary by transition instant (UTC ascending).
   * Apply a **canonical encoding** of the compiled index (by programme hashing law; no locale, no platform-dependent serialisation).
   * Compute **`tz_index_digest`** as the SHA-256 of the canonical index bytes.
5. **Emit cache artefact.**

   * Write cache payload file(s) and a **manifest** containing at least: `manifest_fingerprint`, `tzdb_release_tag`, `tzdb_archive_sha256`, `tz_index_digest`, `rle_cache_bytes`, `created_utc`.
   * Publish under `…/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/` with **write-once** atomic semantics.

### 7.3 Coverage & sanity (binding)

* **Coverage:** The compiled index **SHALL** include **every `tzid` present in the sealed `tz_world_<release>`** (a superset is allowed).
* **Ordering:** Within each `tzid`, transition instants **SHALL** be strictly increasing.
* **Bounds:** Each recorded offset **SHALL** be an integer number of minutes within the layer range; non-finite/NaN values are forbidden.
* **Integrity:** Recomputing the canonical index **MUST** yield the recorded `tz_index_digest`; `rle_cache_bytes` **MUST** be strictly greater than zero; all cache files referenced by the manifest **MUST** exist.

### 7.4 Emission & identity discipline

* **Partitioning:** Output is manifest_fingerprint-scoped (**`[manifest_fingerprint]` only**; no `seed`).
* **Path↔embed equality:** The manifest’s `manifest_fingerprint` **MUST** byte-equal the `manifest_fingerprint` path token.
* **Write-once:** Re-emitting into an existing manifest_fingerprint partition **MUST** be byte-identical; otherwise the run **MUST ABORT**.
* **Atomic publish:** Stage → fsync → single atomic move into the manifest_fingerprint partition. File order is **non-authoritative**; the manifest is the sole content authority.

### 7.5 Prohibitions (non-behaviours)

S3 **SHALL NOT**:

* read or depend on site-level datasets (`site_locations`, `s1_tz_lookup`, `site_timezones`);
* use network sources or unsealed tzdb assets;
* perform any geometry operations on `tz_world` (read its tzid set only);
* introduce RNG or wall-clock time (all observational fields derive from sealed inputs);
* emit any dataset other than `tz_timetable_cache`.

### 7.6 Idempotency

Given the same **S0 receipt**, the same sealed **`tzdb_release`**, and the same sealed **`tz_world_<release>`**, S3 **SHALL** produce **byte-identical** cache payloads and an identical manifest (including `tz_index_digest` and `created_utc`).

---

## 8. Identity, partitions, ordering & merge discipline **(Binding)**

### 8.1 Identity tokens

* **Selection identity:** exactly one **`manifest_fingerprint`** per publish of `tz_timetable_cache`.
* **No seed in S3:** `seed` is **absent** (manifest_fingerprint-only state).
* **Path↔embed equality:** the manifest field **`manifest_fingerprint` MUST byte-equal** the `manifest_fingerprint` path token.

### 8.2 Partitions & path family

* **Dataset:** `tz_timetable_cache` → `data/layer1/2A/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/`.
* **Partitions (binding):** **`[manifest_fingerprint]` only**; no additional partitions are permitted.
* **Catalogue authority:** Exact filenames/layout/format are governed by the Dataset Dictionary.

### 8.3 Keys, uniqueness & content authority

* **Manifest as authority:** The **manifest** is the sole content authority for the cache (fields, referenced files, digests, byte counts).
* **File order non-authoritative:** Consumers **MUST NOT** infer semantics from file ordering or directory listings.

### 8.4 Writer order (discipline)

* **No row sort requirement** (object/manifest artefact).
* **Canonical content order** (for hashing) is fixed by S3’s deterministic behaviour (§7) and reflected in `tz_index_digest`; it is **not** implied by file order.

### 8.5 Merge & immutability

* **Write-once per manifest_fingerprint.** If any artefact already exists under the target `manifest_fingerprint`, a re-emit **MUST** be **byte-identical**; otherwise the run **MUST ABORT**.
* **Atomic publish.** Stage → fsync → single **atomic move** into the manifest_fingerprint partition.
* **No in-place edits / tombstones.** Updates occur only by producing a **new manifest_fingerprint** (i.e., new sealed inputs in S0).

### 8.6 Concurrency & conflict detection

* **Single-writer per identity.** Concurrent writes targeting the same `manifest_fingerprint` are not permitted.
* **Conflict:** The presence of any existing file in the target partition constitutes a conflict; S3 **MUST** abort rather than overwrite.

### 8.7 Discovery & selection (downstream contract)

* Downstream states **MUST** select `tz_timetable_cache` by **`manifest_fingerprint`**, resolve via the **Dataset Dictionary**, verify manifest shape, and enforce **path↔embed equality** before use.

### 8.8 Retention, licensing & relocation

* **Retention/licence** are owned by the Dictionary/Registry (e.g., Proprietary-Internal; typical TTL 365 days).
* **Relocation** that preserves the Dictionary path family and partitioning is non-breaking; any change that alters partition keys or path tokens is **breaking** and out of scope for S3.

*Effect:* These constraints make `tz_timetable_cache` uniquely addressable by **`manifest_fingerprint`**, immutable once published, and unambiguous for downstream consumers, with Schema as **shape authority**, Dictionary as **catalogue authority**, and Registry for **existence/licensing**.

---

## 9. Acceptance criteria (validators) **(Binding)**

**PASS definition.** A run of 2A.S3 is **ACCEPTED** iff **all** mandatory validators below pass. Any **Abort** failure causes the run to **FAIL**; **Warn** does not block emission.

### 9.1 Gate & input resolution (mandatory)

**V-01 — S0 receipt present (Abort).** A valid 2A.S0 gate receipt exists and schema-validates for the target `manifest_fingerprint`.
**V-02a — `tzdb_release` resolves (Abort).** The tzdb artefact resolves by **Dictionary** and is authorised by Registry (no literal paths).
**V-02b — `tz_world_<release>` resolves (Abort).** The tzid coverage surface resolves by **Dictionary** and is readable (no literal paths).
**V-03 — Tag & digest verified (Abort).** `tzdb_release_tag` matches the supported pattern; `tzdb_archive_sha256` is hex64 and equals the SHA-256 of the archive bytes.

### 9.2 Tzdb compilation (mandatory)

**V-04 — Tzdb parseable (Abort).** The sealed archive can be parsed into per-`tzid` transitions.
**V-05 — Non-empty index (Abort).** The compiled index contains ≥1 `tzid`.

### 9.3 Output manifest, identity & determinism (mandatory)

**V-06 — Manifest schema validity (Abort).** The emitted manifest validates against `#/cache/tz_timetable_cache` (fields-strict).
**V-07 — Path↔embed equality (Abort).** Embedded `manifest_fingerprint` equals the `manifest_fingerprint` partition token.
**V-08 — Deterministic timestamp (Abort).** `created_utc == S0.receipt.verified_at_utc`.

### 9.4 Integrity of compiled content (mandatory)

**V-09 — Canonical digest match (Abort).** Recomputed digest of the canonical index equals `tz_index_digest`.
**V-10 — Cache bytes present (Abort).** `rle_cache_bytes > 0`.
**V-11 — Files exist & size matches (Abort).** All cache files referenced by the manifest exist; their total bytes equal `rle_cache_bytes`.

### 9.5 Transition sanity (mandatory)

**V-12 — Strict order per `tzid` (Abort).** Transition instants are strictly increasing.
**V-13 — Offset bounds (Abort).** All offsets are integral minutes within the layer range (−900…+900).
**V-14 — No non-finite values (Abort).** No NaN/Inf in instants or offsets.

### 9.6 Coverage (mandatory)

**V-15 — `tz_world` coverage (Abort).** Every `tzid` present in sealed `tz_world_<release>` appears in the compiled index (superset allowed).

### 9.7 Merge & immutability (mandatory)

**V-16 — Write-once partition (Abort).** If the target manifest_fingerprint partition already exists, newly written bytes must be **byte-identical**; otherwise **ABORT**.

### 9.8 Outcome semantics

* **PASS:** V-01…V-16 pass.
* **FAIL:** Any **Abort** validator fails.
* **WARN:** (none defined for S3).

### 9.9 (For §10) Validator → error-code mapping (normative)

| Validator                        | Error code(s)                                                        |
|----------------------------------|----------------------------------------------------------------------|
| V-01 S0 receipt present          | **2A-S3-001 MISSING_S0_RECEIPT**                                     |
| V-02a `tzdb_release` resolves    | **2A-S3-010 TZDB_RESOLVE_FAILED**                                    |
| V-02b `tz_world` resolves        | **2A-S3-012 TZ_WORLD_RESOLVE_FAILED**                                |
| V-03 Tag & digest verified       | **2A-S3-011 TZDB_TAG_INVALID** · **2A-S3-013 TZDB_DIGEST_INVALID**   |
| V-04 Tzdb parseable              | **2A-S3-020 TZDB_PARSE_ERROR**                                       |
| V-05 Non-empty index             | **2A-S3-021 INDEX_EMPTY**                                            |
| V-06 Manifest schema validity    | **2A-S3-030 MANIFEST_SCHEMA_INVALID**                                |
| V-07 Path↔embed equality         | **2A-S3-040 PATH_EMBED_MISMATCH**                                    |
| V-08 Deterministic `created_utc` | **2A-S3-042 CREATED_UTC_NONDETERMINISTIC**                           |
| V-09 Canonical digest match      | **2A-S3-050 INDEX_DIGEST_MISMATCH**                                  |
| V-10 Cache bytes present         | **2A-S3-060 CACHE_BYTES_MISSING**                                    |
| V-11 Files exist & size matches  | **2A-S3-061 CACHE_FILE_MISSING** · **2A-S3-062 CACHE_SIZE_MISMATCH** |
| V-12 Strict order per `tzid`     | **2A-S3-051 TRANSITION_ORDER_INVALID**                               |
| V-13 Offset bounds               | **2A-S3-052 OFFSET_OUT_OF_RANGE**                                    |
| V-14 No non-finite values        | **2A-S3-055 NONFINITE_VALUE**                                        |
| V-15 `tz_world` coverage         | **2A-S3-053 TZID_COVERAGE_MISMATCH**                                 |
| V-16 Write-once partition        | **2A-S3-041 IMMUTABLE_PARTITION_OVERWRITE**                          |

*Authorities:* Output shape/fields by the S3 anchor; catalogue paths/partition by the 2A Dictionary; existence/licensing by the 2A Registry; gate evidence by the S0 receipt.

---

## 10. Failure modes & canonical error codes **(Binding)**

**Code format.** `2A-S3-XXX NAME` (stable identifiers).
**Effect classes.** `Abort` = run MUST fail and emit nothing; `Warn` = non-blocking, MUST be surfaced in the run-report.
**Required context on raise.** Include: `manifest_fingerprint`; and where applicable `tzdb_release_tag`, `tzdb_archive_sha256`, `tzid`, `cache_file`, and brief location (e.g., byte range, transition index).

### 10.1 Gate & input resolution

* **2A-S3-001 MISSING_S0_RECEIPT (Abort)** — No valid 2A.S0 receipt for the target manifest_fingerprint.
  *Remediation:* publish/repair S0; rerun S3.
* **2A-S3-010 TZDB_RESOLVE_FAILED (Abort)** — `tzdb_release` failed Dictionary resolution or Registry authorisation.
  *Remediation:* fix Dictionary/Registry entries; ensure the sealed artefact exists; rerun.
* **2A-S3-011 TZDB_TAG_INVALID (Abort)** — Release tag missing/malformed/unsupported.
  *Remediation:* correct to a supported tag; reseal in S0.
* **2A-S3-012 TZ_WORLD_RESOLVE_FAILED (Abort)** — `tz_world_<release>` failed Dictionary resolution or is unreadable.
  *Remediation:* correct ingress entry; reseal in S0. 
* **2A-S3-013 TZDB_DIGEST_INVALID (Abort)** — `tzdb_archive_sha256` is not well-formed hex64 OR the SHA-256 of the sealed archive bytes ≠ `tzdb_archive_sha256`.
  *Remediation:* fix digest/artefact; reseal in S0.

### 10.2 Tzdb compilation

* **2A-S3-020 TZDB_PARSE_ERROR (Abort)** — Tzdb archive cannot be parsed into transitions.
  *Remediation:* verify archive integrity/version; reseal or select a valid release.
* **2A-S3-021 INDEX_EMPTY (Abort)** — Compiled index contains zero `tzid`s.
  *Remediation:* confirm release content; fix parser/config; rerun.

### 10.3 Output manifest, identity & determinism

* **2A-S3-030 MANIFEST_SCHEMA_INVALID (Abort)** — Manifest violates `#/cache/tz_timetable_cache` (fields/typing).
  *Remediation:* emit schema-valid manifest only.
* **2A-S3-040 PATH_EMBED_MISMATCH (Abort)** — Manifest `manifest_fingerprint` ≠ partition token.
  *Remediation:* correct path or embedded value; rerun.
* **2A-S3-041 IMMUTABLE_PARTITION_OVERWRITE (Abort)** — Non-identical bytes written to an existing manifest_fingerprint partition.
  *Remediation:* either produce byte-identical output or target a new manifest_fingerprint.
* **2A-S3-042 CREATED_UTC_NONDETERMINISTIC (Abort)** — `created_utc` ≠ S0.receipt.verified_at_utc.
  *Remediation:* set timestamp deterministically; rerun.

### 10.4 Integrity of compiled content

* **2A-S3-050 INDEX_DIGEST_MISMATCH (Abort)** — Recomputed canonical index digest ≠ `tz_index_digest`.
  *Remediation:* correct canonicalisation/hash or fix compiled index; rerun.
* **2A-S3-060 CACHE_BYTES_MISSING (Abort)** — `rle_cache_bytes ≤ 0`.
  *Remediation:* ensure cache payloads are emitted and accounted for.
* **2A-S3-061 CACHE_FILE_MISSING (Abort)** — Manifest references a cache file that does not exist.
  *Remediation:* publish all referenced files atomically; rerun.
* **2A-S3-062 CACHE_SIZE_MISMATCH (Abort)** — Sum of referenced file sizes ≠ `rle_cache_bytes`.
  *Remediation:* fix manifest byte counts or payloads; rerun.

### 10.5 Transition sanity

* **2A-S3-051 TRANSITION_ORDER_INVALID (Abort)** — Non-monotonic transition instants for a `tzid`.
  *Remediation:* sort/validate per-`tzid` transitions strictly ascending; rerun.
* **2A-S3-052 OFFSET_OUT_OF_RANGE (Abort)** — Offset minutes outside allowed layer bounds (−900…+900).
  *Remediation:* clamp/validate bounds according to layer policy; rerun.
* **2A-S3-055 NONFINITE_VALUE (Abort)** — NaN/Inf encountered in instants or offsets.
  *Remediation:* sanitise inputs; ensure numeric policy compliance.

### 10.6 Coverage

* **2A-S3-053 TZID_COVERAGE_MISMATCH (Abort)** — Any `tzid` present in sealed `tz_world_<release>` is missing from the compiled index.
  *Remediation:* extend compilation to include all programme tzids; rerun.

### 10.7 Authority conflict (resolution rule)

* **2A-S3-080 AUTHORITY_CONFLICT (Abort)** — Irreconcilable disagreement among **Schema, Dictionary, Registry** for the same asset after applying precedence (**Schema › Dictionary › Registry**).
  *Remediation:* correct the lower-precedence authority (or the schema, if wrong); rerun.

> The validator → code mapping in §9.9 is **normative**. New failure conditions introduced by future revisions MUST allocate **new codes** (append-only) and MUST NOT repurpose existing identifiers.

---

## 11. Observability & run-report **(Binding)**

### 11.1 Scope & posture

* **Purpose.** Record auditable evidence of S3’s gate verification, tzdb compilation, canonicalisation, coverage check, and publish.
* **Not identity-bearing.** The run-report does **not** affect dataset identity or gates.
* **One per run.** Exactly one report per attempted S3 run (success or failure).

---

### 11.2 Run-report artefact (normative content)

A single UTF-8 JSON object **SHALL** be written for the run with at least the fields below. Missing required fields are **Warn** (programme policy may escalate).

**Top level (run header):**

* `segment : "2A"`
* `state : "S3"`
* `status : "pass" | "fail"`
* `manifest_fingerprint : hex64`
* `started_utc, finished_utc : rfc3339_micros`
* `durations : { wall_ms : uint64 }`
* `tzdb.digest_verified : true`

**Gate & inputs:**

* `s0.receipt_path : string` — path of verified 2A.S0 receipt
* `s0.verified_at_utc : rfc3339_micros`
* `tzdb.release_tag : string`
* `tzdb.archive_sha256 : hex64`
* `tz_world.id : string` — e.g., `tz_world_2025a`
* `tz_world.license : string`

**Compilation summary:**

* `compiled.tzid_count : uint32` — number of tzids in the compiled index
* `compiled.transitions_total : uint64` — total transitions across all tzids
* `compiled.offset_minutes_min : int32`
* `compiled.offset_minutes_max : int32`
* `compiled.tz_index_digest : hex64` — canonical index digest
* `compiled.rle_cache_bytes : uint64` — total bytes of emitted cache payloads

**Coverage summary:**

* `coverage.world_tzids : uint32` — distinct tzids in sealed `tz_world`
* `coverage.cache_tzids : uint32` — distinct tzids in compiled index
* `coverage.missing_count : uint32` — EXPECT 0 on PASS
* `coverage.missing_sample : string[]` — optional, small sample for debugging (non-exhaustive; may be empty on PASS)

**Output & identity:**

* `output.path : string` — path to `tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/`
* `output.created_utc : rfc3339_micros` — **MUST** equal `s0.verified_at_utc`
* `output.files : array<{name:string, bytes:uint64}>` — manifest-listed cache payloads (advisory)

**Diagnostics:**

* `warnings : array<error_code>` — any non-blocking codes raised
* `errors : array<{code, message, context}>` — on failure, canonical codes with brief context

**Optional (advisory, non-binding):**

* `determinism.partition_hash : hex64` — directory-level hash of the emitted manifest_fingerprint partition.

---

### 11.3 Structured logs (minimum event kinds)

S3 **SHALL** emit machine-parseable log records correlating to the report. Minimum events:

* **`GATE`** — start/end + result of S0 receipt verification; include `manifest_fingerprint`.
* **`INPUTS`** — resolved IDs/paths for `tzdb_release` and `tz_world_<release>`.
* **`TZDB_PARSE`** — parse outcome (release tag, archive digest, tzid_count discovered).
* **`COMPILE`** — totals (`tzid_count`, `transitions_total`, `offset_minutes_min/max`).
* **`CANONICALISE`** — computed `tz_index_digest` and `rle_cache_bytes`.
* **`COVERAGE`** — `world_tzids`, `cache_tzids`, `missing_count` (and small sample if non-zero).
* **`VALIDATION`** — each validator outcome `{id, result, code?}` for §9.
* **`EMIT`** — successful publication of `tz_timetable_cache` with path and `created_utc`.

Every record **SHALL** include:
`timestamp_utc (rfc3339_micros)`, `segment`, `state`, `manifest_fingerprint`, and `severity (INFO|WARN|ERROR)`.

---

### 11.4 Discoverability, retention & redaction

* **Discoverability.** The run-report path **MUST** be surfaced in CI/job metadata alongside the `tz_timetable_cache` Dictionary path.
* **Retention.** Report TTL is governed by programme policy; changing TTL **MUST NOT** alter dataset identity or partitions.
* **Redaction.** Reports/logs **MUST NOT** include raw tzdb bytes or large dumps of tzids/transitions. Counts, digests, short samples (for coverage misses), IDs, paths, and timestamps are permitted.

---

## 12. Performance & scalability **(Informative)**

### 12.1 Workload shape

* **Reads:** sealed `tzdb_release` archive (single artefact) and `tz_world_<release>` tzid list (for coverage).
* **Compute:** parse tzdb → assemble per-`tzid` transition sequences (UTC instant, offset minutes) → canonicalise → hash to `tz_index_digest`.
* **Writes:** one manifest_fingerprint-scoped cache (payload file(s) + JSON manifest).

### 12.2 Asymptotics (Z = #tzids, T = total transitions across all tzids)

* **Time:** ~ **O(T log T)** worst-case if a global sort is used; **O(T)** with per-`tzid` monotone construction + stable merge (canonical order is `tzid` ASCII-lex, then instant).
* **Space:** streaming **O(1)** in archive size plus **O(max transitions for a single tzid)** working set; additional **O(Z)** for per-`tzid` indices/metadata.

### 12.3 Memory model

* **Streaming parse** of the archive; avoid materialising all transitions simultaneously.
* Keep a bounded in-memory buffer for the **largest single tzid** and flush canonicalised segments incrementally.
* Manifest fields are tiny; dominant resident set is the largest per-`tzid` sequence during normalisation/coalescing.

### 12.4 I/O profile

* **Input:** one sequential read of `tzdb_release`; a light scan of `tz_world_<release>` to collect distinct tzids.
* **Output:** sequential write of cache payload(s) and a small manifest; file order is non-authoritative.

### 12.5 Parallelism & concurrency

* **Across tzids:** embarrassingly parallel. Partition the tzid set into shards; compile shards independently; reduce into the canonical order before hashing.
* **Across fingerprints:** independent; S3 is manifest_fingerprint-scoped (no `seed`).
* **Publish:** still **single-writer, write-once** for the final partition; perform parallel work behind a single atomic emit.

### 12.6 Hot spots & guardrails

* **Large transition eras:** tzids with frequent historical rule changes inflate `T`; ensure coalescing removes redundant adjacent offsets.
* **Offset bounds:** clamp/validate to the layer range (−900..+900) to avoid outliers cascading through hashing.
* **Canonicalisation stability:** normalise encodings (byte order, number formats, newline discipline) so recomputation reproduces `tz_index_digest`.
* **Coverage join:** compute the `tz_world` tzid set once; treat it as a pure set membership check (no geometry).

### 12.7 Determinism considerations

* Derive **`created_utc` from S0** (no wall clock).
* Ensure sort keys are total (`tzid` ASCII-lex; instant UTC ascending).
* Use integer minutes for offsets; avoid floating-point in identity-bearing paths.

### 12.8 Scalability knobs (programme-level)

* **Shard size / parallelism:** number of tzid shards compiled concurrently.
* **Payload layout:** number/size of cache files (e.g., per-shard vs single blob); does not affect identity as long as manifest + digest match.
* **Digest windowing:** compute `tz_index_digest` incrementally over canonicalised chunks to cap memory.
* **Retry/back-off:** object-store reads/writes; verify bytes on read to avoid silent corruption.

### 12.9 Re-run & churn costs

* S3 runs **once per manifest_fingerprint**; downstream seeds reuse the same cache.
* Changing **`tzdb_release`** or **`tz_world_<release>`** in S0 produces a **new manifest_fingerprint**, requiring a fresh compile; otherwise reruns reproduce bytes exactly.

### 12.10 Typical envelopes (order-of-magnitude)

* **Z (tzids):** ~ few hundred to low thousands (release-dependent).
* **T (transitions):** tens to hundreds of thousands total.
* **Manifest size:** KBs; **payload size:** MBs–tens of MBs depending on compression and format.
* **Runtime:** scales ~linearly with `T` given a streaming parse and modest sharding.

---

## 13. Change control & compatibility **(Binding)**

### 13.1 Versioning & document status

* **SemVer** applies to this state spec (`MAJOR.MINOR.PATCH`).

  * **PATCH:** editorial clarifications that **do not** change behaviour, shapes, validators, or outcomes.
  * **MINOR:** strictly backward-compatible additions that **do not** alter identity, partitions, canonicalisation/digest law, or PASS/FAIL results.
  * **MAJOR:** any change that can affect identity, partitioning, required manifest fields, canonical order/digest, coverage requirement, or validator outcomes.

### 13.2 Stable compatibility surfaces (must remain invariant)

1. **Identity:** output is selected by **`manifest_fingerprint`**; partitions are **`[manifest_fingerprint]`** only; **path↔embed equality** MUST hold.
2. **Output surface:** dataset **`tz_timetable_cache`** exists with its **schema anchor/ID** unchanged (fields-strict manifest).
3. **Manifest minima:** fields present and meanings stable: `manifest_fingerprint`, `tzdb_release_tag`, `tzdb_archive_sha256`, `tz_index_digest`, `rle_cache_bytes`, `created_utc`.
4. **Determinism:** `created_utc == S0.receipt.verified_at_utc`; S3 is RNG-free; no site-level inputs.
5. **Canonicalisation & digest:** stable canonical ordering/encoding of the compiled index and its hashing law (source of `tz_index_digest`).
6. **Coverage law:** compiled index **includes all `tzid` present in the sealed `tz_world_<release>`** (superset allowed).
7. **Catalogue posture:** **Dictionary** is authority for IDs→paths/partitions/format; **Registry** for existence/licence/retention/lineage; **Schema** is sole shape authority.
8. **Validator & code semantics:** §9 validators and §10 error codes retain their meanings.

### 13.3 Backward-compatible changes (**MINOR** or **PATCH**)

Permitted when they **do not** change identity or acceptance:

* Add **non-identity manifest fields** (nullable/optional) and corresponding run-report/log fields.
* Add **Warn-only** diagnostics/validators (e.g., extra sanity checks on cache payload layout).
* Allow multiple cache payload shard layouts under the same manifest, when the manifest already lists file names and `rle_cache_bytes` (file order remains non-authoritative).
* Expand accepted **tzdb tag** regex to include new official forms while retaining prior forms.
* Refine textual descriptions/bounds where current outputs already comply.

> Note: The manifest is **fields-strict**; adding **required** fields or retyping existing ones is **not** backward-compatible (see 13.4).

### 13.4 Breaking changes (**MAJOR**)

Require a MAJOR bump and downstream coordination:

* Changing **partitions** (adding `seed`, renaming keys) or altering **path↔embed** rules.
* Renaming/removing **`tz_timetable_cache`** or its **schema anchor**, or relocating it to a different path family.
* Modifying **canonicalisation/digest law** (ordering, encoding, or hash algorithm) that feeds `tz_index_digest`.
* Changing **coverage law** (e.g., making the index a strict **equal** set vs `tz_world`, or dropping the coverage requirement).
* Removing/retyping any **existing manifest field**, or making an optional field **required**.
* Admitting new **inputs** (e.g., site data) or introducing wall-clock/RNG elements.
* Any validator change that flips previously PASSing runs to FAIL under unchanged inputs.

### 13.5 Deprecation policy

* **Announce → grace → remove.** Mark a feature **Deprecated** at least **one MINOR** before removal with an **effective date**.
* **No repurposing.** Deprecated fields/codes/IDs are never reused; removal only at **MAJOR**.
* **Alias window.** When renaming anchors/IDs, provide alias anchors for at least one MINOR; both validate to identical shapes during the window.

### 13.6 Co-existence & migration

* Use a **dual-anchor window** for material changes (e.g., `#/cache/tz_timetable_cache_v2`) while the old anchor remains valid; Dictionary may list both; identity remains the same (**`[manifest_fingerprint]`**).
* **Re-fingerprinting is upstream.** Changing `tzdb_release` or `tz_world_<release>` happens in S0, producing a **new `manifest_fingerprint`**; S3 recomputes for that manifest_fingerprint with no spec change.
* **Idempotent re-runs.** Reruns with unchanged sealed inputs reproduce bytes exactly (write-once partition).

### 13.7 Reserved extension points

* The current manifest is fields-strict and **does not** admit arbitrary extension fields.
* A future MINOR **may** introduce an `extensions` object (ignored by consumers) **if and only if** the anchor is updated concurrently to allow it; otherwise any new field is **MAJOR**.

### 13.8 External dependency evolution

* **Tzdb format/tag drift.** If IANA modifies release tagging or minor archive structure, S3 may **MINOR**-expand acceptance (e.g., regex, non-identity parse tolerance) while preserving canonicalisation/digest law.
* **`tz_world` churn.** Introducing a new `tz_world` release is not a spec change; it only changes sealed bytes → manifest_fingerprint in S0; S3’s coverage rule remains the same.

### 13.9 Governance & change process

Every change SHALL include: (i) version bump rationale, (ii) compatibility impact (Patch/Minor/Major), (iii) updated anchors/Dictionary/Registry stanzas (if any), (iv) validator/error-code diffs, and (v) migration notes.
Frozen specs SHALL record an **Effective date**; downstream pipelines target frozen or explicitly authorised alpha versions.

### 13.10 Inter-state coupling

* **Upstream:** depends only on S0 receipt, `tzdb_release`, and the `tz_world` tzid domain; no site-level coupling.
* **Downstream:** S4 and others read `tz_timetable_cache` by manifest_fingerprint; any S3 change that forces downstream to re-implement S0 gates, alters the digest/coverage law, or changes the cache identity is **breaking**.

---

## Appendix A — Normative cross-references *(Informative)*

> Pointers only. These are the authorities S3 relies on. **Schema = shape authority**; **Dictionary = IDs → paths/partitions/format**; **Registry = existence/licensing/retention/lineage**. S3 reads only the inputs listed; all IDs resolve via the Dictionary.

### A1. Layer-1 governance (global rails)

* **Identity & Path Law** — path↔embed equality; partition keys are authoritative.
* **Gate Law** — “No PASS → No Read”; S3 relies on the 2A.S0 receipt (does not re-hash bundles).
* **Fingerprint Law** — canonical sealed-manifest → `manifest_fingerprint` (fixed upstream in S0).
* **Numeric policy** — layer-wide numeric/encoding rules (by reference).

### A2. Upstream receipt & inputs used by S3

* **2A.S0 gate receipt** — `schemas.2A.yaml#/validation/s0_gate_receipt_v1` (manifest_fingerprint-scoped).
* **IANA tzdb release** — `schemas.2A.yaml#/ingress/tzdb_release_v1` (release tag + archive digest; sealed in S0).
* **Time-zone world (tzid domain)** — `schemas.ingress.layer1.yaml#/tz_world_2025a` (GeoParquet, WGS84; read only for tzid coverage; sealed in S0).

### A3. S3 output surface

* **Timetable/cache artefact** — `schemas.2A.yaml#/cache/tz_timetable_cache` (manifest with `manifest_fingerprint`, `tzdb_release_tag`, `tzdb_archive_sha256`, `tz_index_digest`, `rle_cache_bytes`, `created_utc`).
* **Catalogue path family** — `data/layer1/2A/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/` (partition **`[manifest_fingerprint]`** only).

### A4. Dataset Dictionary (catalogue authority)

* **Inputs:** `tzdb_release` (artefacts/priors; unpartitioned), `tz_world_2025a` (reference/spatial; unpartitioned).
* **Output:** `tz_timetable_cache` (manifest_fingerprint-scoped; format/files governed by catalogue).
* **Evidence:** 2A.S0 receipt (manifest_fingerprint-scoped).

### A5. Artefact Registry (existence/licensing/lineage)

* **`tzdb_release`** — ingress artefact with licence/provenance and sealed digest.
* **`tz_world_2025a`** — cross-layer reference with licence and release metadata.
* **`tz_timetable_cache`** — cache artefact with lineage **`tz_timetable_cache → tzdb_release`**, write-once posture, atomic publish.

### A6. Segment-level context

* **State flow:** S0 (gate) → S1 (geometry) → S2 (overrides) → **S3 (compile tzdb to cache)** → S4 (legality using the cache) → S5 (2A validation bundle/flag).
* **Selection & identity:** all consumers of the cache select by **`manifest_fingerprint`** via the Dictionary and verify schema + path↔embed equality before use.

---
