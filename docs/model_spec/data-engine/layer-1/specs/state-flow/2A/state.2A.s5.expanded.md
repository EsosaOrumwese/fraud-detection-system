# State 2A.S5 — Validation bundle & PASS flag

## 1. Document metadata & status **(Binding)**

**Title:** Layer-1 · Segment 2A · State-5 — Validation bundle & PASS flag
**Short name:** 2A.S5 “PASS gate”
**Layer/Segment/State:** L1 / 2A (Civil Time) / S5
**Doc ID:** `layer1/2A/state-5`
**Version (semver):** `v1.0.0-alpha` *(advance per change control)*
**Status:** `draft | alpha | frozen` *(normative at ≥ `alpha`; semantics locked at `frozen`)*
**Owners:** Design Authority (DA): ‹name› • Review Authority (RA): ‹name›
**Effective date:** ‹YYYY-MM-DD›
**Canonical location:** ‹repo path to this spec file›

**Normative cross-references (pointers only):**

* **Gate & sealed inputs:** `schemas.2A.yaml#/validation/s0_gate_receipt_v1` (receipt for target `manifest_fingerprint`).
* **Upstream evidence:**
  • `schemas.2A.yaml#/egress/site_timezones` (S2; `[seed,fingerprint]`)
  • `schemas.2A.yaml#/cache/tz_timetable_cache` (S3; `[fingerprint]`)
  • `schemas.2A.yaml#/validation/s4_legality_report` (S4; `[seed,fingerprint]`)
* **Outputs (this state):**
  • `schemas.2A.yaml#/validation/validation_bundle_2A`
  • `schemas.2A.yaml#/validation/bundle_index_v1`
  • `schemas.2A.yaml#/validation/passed_flag`
* **Catalogue & registry:** Dataset Dictionary entries for `validation_bundle_2A` and `_passed.flag` (partition `[fingerprint]`); Artefact Registry lineage (bundle/flag depend on S2/S3/S4 evidence).
* **Layer-1 governance:** Identity & Path Law (path↔embed equality), Gate Law (“No PASS → No Read”), Fingerprint/Hashing Law (ASCII-lex index; raw-bytes digest; flag excluded), Numeric Policy.

**Conformance & interpretation:**

* Sections marked **Binding** are normative; **Informative** sections do not create obligations.
* Keywords **MUST/SHALL/SHOULD/MAY** follow RFC 2119/8174.
* This is a **design specification**: it defines behaviours, identities, inputs/outputs, and inter-state contracts; it does **not** prescribe implementations or pseudocode.

**Change log (summary):**

* `v1.0.0-alpha` - Initial specification for 2A.S5 (fingerprint-scoped validation bundle + PASS flag sealing S2-S4 evidence). Subsequent edits follow §13 Change Control.

---

### Contract Card (S5) - inputs/outputs/authorities

**Inputs (authoritative; see Section 3.2 for full list):**
* `s0_gate_receipt_2A` - scope: FINGERPRINT_SCOPED; source: 2A.S0
* `tz_timetable_cache` - scope: FINGERPRINT_SCOPED; source: 2A.S3
* `site_timezones` - scope: SEED+FINGERPRINT; source: 2A.S2
* `s4_legality_report` - scope: SEED+FINGERPRINT; source: 2A.S4

**Authority / ordering:**
* Validation bundle index + hash gate is the sole consumer gate for 2A.

**Outputs:**
* `validation_bundle_2A` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `validation_passed_flag_2A` - scope: FINGERPRINT_SCOPED; gate emitted: final consumer gate

**Sealing / identity:**
* External inputs (ingress/reference/1B egress/2A policy) MUST appear in `sealed_inputs_2A` for the target `manifest_fingerprint`.

**Failure posture:**
* Any validation failure -> do not publish `_passed.flag`; bundle records failure evidence.

## 2. Purpose & scope **(Binding)**

**Intent.** Establish the **segment PASS gate** for 2A by verifying all required evidence for a single **`manifest_fingerprint`** and publishing a fingerprint-scoped **validation bundle** plus a cryptographic **`_passed.flag`** that downstream systems SHALL enforce as **“No PASS → No Read.”**

**Objectives (normative).** 2A.S5 SHALL:

* **Assert eligibility:** Use the 2A.S0 **gate receipt** for the target `manifest_fingerprint` before any read.
* **Verify required evidence:**
  • **S3 cache** exists and is valid for the fingerprint (schema-valid, path↔embed equality, non-empty).
  • **Discover all seeds** that have `site_timezones/seed={seed}/fingerprint={manifest_fingerprint}`.
  • For **every discovered seed**, a matching **S4 legality report** exists with **`status="PASS"`**.
* **Assemble a canonical bundle:** Create a fingerprint-scoped directory containing at least an **`index.json`** (fields-strict) that lists every bundled file as `{path, sha256_hex}` in **ASCII-lex order**, plus the referenced evidence files (e.g., all S4 reports for the fingerprint, an S3 cache manifest snapshot, optional checks/metrics).
* **Seal with a flag:** Write **`_passed.flag`** as the single line
  `sha256_hex = <64 lowercase hex>`
  where the value is the SHA-256 over the **raw bytes** of all files listed in `index.json`, concatenated in **ASCII-lex path order**; the flag itself is **excluded** from the hash.
* **Bind identity & immutability:** Emit under **`[fingerprint]`** only, enforce **path↔embed equality**, and **write-once/atomic** publish.
* **Remain RNG-free & idempotent.**

**In scope.**

* Fingerprint-scoped **seed discovery** for S2 egress and completeness checks against S4.
* Schema/identity checks for S3 cache and S4 reports; construction of `index.json`; computation of the bundle digest; emission of `_passed.flag`.
* Optional inclusion of non-identity **checks/metrics** files referenced by the index.

**Out of scope.**

* Recomputing S2/S3/S4 logic, modifying any 2A datasets, parsing raw tzdb, using geometry, or consuming non-sealed assets.
* Introducing any new identity tokens or partitions; changing the hashing or bundle law defined for Layer-1.

**Interfaces (design relationship).**

* **Upstream:** S0 receipt (gate), S2 `site_timezones` (for seed discovery), S3 `tz_timetable_cache` (cache manifest), S4 `s4_legality_report` (per-seed PASS).
* **Downstream:** Consumers MUST verify `_passed.flag` against the bundle per the canonical index/digest law before reading 2A egress.

**Completion semantics.** S5 is complete when the **validation bundle** and **`_passed.flag`** are written under the correct `[fingerprint]` partition, `index.json` is schema-valid and **ASCII-lex ordered**, the recomputed digest over the indexed files equals the flag value, and all acceptance validators pass.

---

## 3. Preconditions & sealed inputs **(Binding)**

### 3.1 Preconditions

S5 SHALL begin only when:

* **Gate verified.** A valid **2A.S0 gate receipt** exists and schema-validates for the target `manifest_fingerprint`. S5 relies on this for read permission; it does **not** re-hash upstream bundles.
* **Run identity fixed.** The **`manifest_fingerprint`** for this publish is selected and constant; S5 is **fingerprint-scoped** (no `seed`).
* **Authorities addressable.** The 2A schema pack, Dataset Dictionary, and Artefact Registry required below resolve without placeholders (Schema = shape; Dictionary = IDs→paths/partitions/format; Registry = existence/licence/retention/lineage).
* **Posture.** S5 is **RNG-free** and deterministic; all observational timestamps in optional diagnostics **MUST** be derived from sealed inputs (e.g., S0 receipt), not wall-clock time.

### 3.2 Inputs (consumed / verified by S5)

S5 **consumes only** the inputs below. All inputs **MUST** resolve **by ID via the Dataset Dictionary** (no literal/relative paths) and be authorised by the Registry.

1. **2A.S0 gate receipt (evidence)**
   *Role:* proves eligibility to read fingerprint-scoped assets; binds the sealed-inputs set for this `manifest_fingerprint`.
   *Use in S5:* presence + schema validity + fingerprint match (no bundle re-hash).

2. **`tz_timetable_cache` (from S3) — partition `[fingerprint]`**
   *Role:* authoritative cache manifest produced by S3 for this fingerprint.
   *Use in S5:* schema validity, path↔embed equality, non-empty payload; a **snapshot** (e.g., the manifest) **MAY** be included in the bundle as evidence.

3. **`site_timezones` (from S2) — discovery surface**
   *Role:* determine the **set of seeds** that have egress under this fingerprint.
   *Discovery rule (binding):* S5 SHALL enumerate **SEEDS = { seed | exists path `…/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/` }** via the Dictionary; **no heuristics**.
   *Use in S5:* discovery only; S5 SHALL NOT read or re-emit `site_timezones` data.

4. **`s4_legality_report` (from S4) — one per discovered seed**
   *Role:* per-seed legality evidence.
   *Use in S5 (binding):* for **every `seed ∈ SEEDS`**, S5 SHALL require a matching S4 report at `[seed,fingerprint]` with **`status="PASS"`**. These reports **SHALL** be included in the bundle and listed in `index.json`.

> *Note:* S5 does **not** parse raw tzdb, geometry, or any non-sealed assets; it verifies and **seals** evidence produced by prior states.

### 3.3 Binding constraints on input use

* **Same-fingerprint constraint.** All fingerprinted inputs S5 references **MUST** match the target `manifest_fingerprint`.
* **Dictionary-only resolution.** Inputs SHALL be resolved by **ID → path/partitions/format** via the Dictionary; literal/relative paths are **forbidden**.
* **Shape authority.** JSON-Schema anchors are the **sole** shape authority; S5 SHALL NOT assume undeclared fields.
* **Seed completeness.** For the discovered **SEEDS**, a corresponding S4 report **MUST** exist for **each** seed and **MUST** have `status="PASS"`; otherwise S5 **MUST ABORT**.
* **Bundle scope.** Files hashed by S5 **MUST** reside under the fingerprint’s **bundle root**; `index.json` **MUST NOT** reference `_passed.flag` or any path outside the bundle root.
* **Non-mutation.** S5 SHALL NOT mutate any input datasets; it emits only the **validation bundle** and the **`_passed.flag`**.

### 3.4 Null/empty allowances

* **No egress seeds (SEEDS = ∅).** Allowed. S5 SHALL still produce a fingerprint-scoped bundle/flag (e.g., with S3 evidence and an empty seed list) provided all other validators pass.
* **Optional diagnostics.** S5 MAY include non-identity diagnostics (checks/metrics JSON) in the bundle; if present, they **MUST** be listed in `index.json` and are covered by the digest.
* **No other inputs.** Datasets not enumerated in §3.2 are **out of scope** for S5 and SHALL NOT be read.

---

## 4. Inputs & authority boundaries **(Binding)**

### 4.1 Authority model (normative)

* **Shape authority:** JSON-Schema anchors fix fields, domains, PK/partitions, and strictness
  *(S5 relies on: `#/validation/s0_gate_receipt_v1`, `#/cache/tz_timetable_cache`, `#/egress/site_timezones`, `#/validation/s4_legality_report`).*
* **Catalogue authority:** The Dataset Dictionary fixes **IDs → canonical paths/partitions/format**. S5 **MUST** resolve all inputs by **ID only** (no literal/relative paths).
* **Existence/licensing/lineage:** The Artefact Registry declares **presence, licence class, retention, lineage**.
* **Precedence on disputes:** **Schema › Dictionary › Registry** (Schema wins for shape; Dictionary wins for path/partitions; Registry supplies existence/licence).
* **Gate law:** Read permission derives from the **2A.S0 receipt** for the target `manifest_fingerprint`; S5 does **not** re-hash upstream bundles.
* **Identity law:** **Path↔embed equality** applies wherever lineage appears both in path tokens and embedded fields.

### 4.2 Per-input boundaries

1. **2A.S0 gate receipt (evidence)**

   * **Shape:** `schemas.2A.yaml#/validation/s0_gate_receipt_v1`.
   * **Catalogue:** fingerprint-scoped receipt.
   * **Boundary:** S5 **SHALL** verify presence and **fingerprint match** only; it **SHALL NOT** recompute any upstream bundle hash or alter receipt content.

2. **`tz_timetable_cache` (S3 output; required)**

   * **Shape:** `schemas.2A.yaml#/cache/tz_timetable_cache`.
   * **Catalogue:** `…/tz_timetable_cache/fingerprint={manifest_fingerprint}/` (partition `[fingerprint]`).
   * **Boundary:** S5 **SHALL** treat the cache manifest as **authoritative**; verify schema validity, **path↔embed equality**, and **non-empty payload**.
     S5 **MAY** copy a manifest snapshot into the bundle as evidence; if copied, the bytes **MUST** match the source exactly.

3. **`site_timezones` (S2 egress; discovery surface)**

   * **Shape:** `schemas.2A.yaml#/egress/site_timezones`.
   * **Catalogue:** `…/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/` (partitions `[seed, fingerprint]`).
   * **Boundary (discovery-only):** S5 **SHALL** discover **SEEDS** by testing catalogue existence of the path family for this fingerprint.
     S5 **SHALL NOT** read, copy, or re-emit site rows; only the **set of seeds** is used.

4. **`s4_legality_report` (S4 evidence; one per discovered seed)**

   * **Shape:** `schemas.2A.yaml#/validation/s4_legality_report`.
   * **Catalogue:** `…/legality_report/seed={seed}/fingerprint={manifest_fingerprint}/s4_legality_report.json`.
   * **Boundary:** For **every `seed ∈ SEEDS`**, S5 **SHALL** require exactly one report at the matching `[seed,fingerprint]` with **`status="PASS"`**.
     These reports **SHALL** be included in the bundle and listed in the index; S5 **SHALL NOT** modify their bytes.

> **Out of scope inputs:** raw tzdb, geometry, overrides, or any dataset not listed above are **forbidden** in S5.

### 4.3 Validation responsibilities (S5 scope)

* **Receipt & identity:** S0 receipt exists and matches the target `manifest_fingerprint`.
* **Dictionary resolution:** All inputs resolve by **ID**; selected partitions are exact (no literal paths).
* **Cache readiness:** Cache manifest is schema-valid, **path↔embed** correct, and payload **non-empty**.
* **Seed completeness:** `SEEDS` is discovered from the catalogue; for **each** seed a matching S4 report exists with **`status="PASS"`** (none missing, none failing).
* **Bundle evidence discipline:** Any evidence file S5 copies into the bundle **MUST** be byte-for-byte identical to the catalogued source.
* **Root scoping (for later index checks):** All files S5 will hash **MUST** reside under the fingerprint’s **bundle root**; S5 **MUST NOT** reference paths outside the root or include `_passed.flag` in the index.

### 4.4 Prohibitions

S5 **SHALL NOT**:

* use network or implicit paths;
* read site rows or recompute S2/S3/S4 logic;
* mutate any input artefact;
* include `_passed.flag` itself in the hashed set;
* introduce RNG or wall-clock time (any optional diagnostics timestamps must be derived from sealed inputs).

---

## 5. Outputs (bundle & flag) & identity **(Binding)**

### 5.1 Validation bundle — `validation_bundle_2A` (fingerprint-scoped directory)

**Role.** The authoritative, immutable evidence set that proves 2A is publishable for a single **`manifest_fingerprint`**.

**Catalogue (Dictionary).** Path family (fingerprint only):
`data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/`

**Required contents (binding):**

* **`index.json`** — **fields-strict** (`#/validation/bundle_index_v1`), listing **every** bundled file as:
  `[{ "path": "<relative-path>", "sha256_hex": "<hex64>" }, …]`
  **Rules:**

  * Paths are **relative** to the bundle root (no leading `/`, no `..` segments, no symlinks).
  * Entries are sorted in **ASCII-lexicographic order by `path`**.
  * No duplicates; all listed files **exist in the bundle root**; **`_passed.flag` MUST NOT appear** in the index.
* **Evidence files** (bytes **unchanged** from their catalogued sources):

  * **All S4 reports** for the **discovered seed set** under this fingerprint (one per seed).
  * An **S3 cache manifest snapshot** for this fingerprint.
  * *(Optional, non-identity)* `checks.json` / `metrics.json` (if present, they **MUST** be listed in `index.json` and are covered by the digest).

**Prohibitions:** The bundle **MUST NOT** contain data from outside the sealed 2A evidence (no raw tzdb, no site rows).

---

### 5.2 PASS flag — `_passed.flag` (single file, one line)

**Role.** Cryptographic attestation of the bundle’s contents.

**Location.** Same bundle root as above.

**Canonical format (binding):**
A single ASCII line **exactly**:

```
sha256_hex = <64 lowercase hex>
```

**Digest law (binding):** The `<hex>` value is the **SHA-256 over the raw bytes** of **all files listed in `index.json`**, concatenated in the index’s **ASCII-lex path order**. The flag file **is excluded** from the hash.

**Strictness:** Whitespace, casing, and newline handling are **exact**; casing of hex **must be lowercase**; additional lines are **forbidden**.

---

### 5.3 Identity & path law

* **Partitions:** **`[fingerprint]` only** (no `seed`).
* **Path↔embed equality:** Wherever lineage appears in embedded fields of any bundled evidence (e.g., S4 reports), their bytes are copied **verbatim**; S5 does **not** alter embedded values.
* **Dictionary-only resolution:** The bundle root and its files are addressed via the Dictionary path family; no literal or out-of-root paths are permitted in `index.json`.

---

### 5.4 Write posture & merge discipline

* **Single-writer, write-once per fingerprint.** Any re-emit to an existing fingerprint **MUST** be **byte-identical**; otherwise the run **MUST ABORT**.
* **Atomic publish (binding):** Stage bundle files → write `index.json` (ASCII-lex) → compute digest over raw bytes of indexed files → write `_passed.flag` with the canonical line → **single atomic move** into the fingerprint partition.
* **File order non-authoritative:** Only the index’s order is authoritative for hashing; directory listing order has no meaning.

---

### 5.5 Format, licensing & retention (by catalogue/registry)

* **Formats:** `index.json` (JSON, fields-strict), evidence files as originally catalogued, `_passed.flag` (text, one line).
* **Licence/TTL:** As declared in Dictionary/Registry (e.g., Proprietary-Internal; typical retention ≥ 3 years for validation artefacts).

---

## 6. Dataset shapes & schema anchors **(Binding)**

**Shape authority.** JSON-Schema anchors are the **sole** source of truth for fields, domains, strictness, and identity. S5 binds to:

* **Outputs (this state):**
  `schemas.2A.yaml#/validation/validation_bundle_2A` · `#/validation/bundle_index_v1` · `#/validation/passed_flag`. 
* **Referenced inputs (evidence):**
  `#/validation/s4_legality_report` · `#/cache/tz_timetable_cache` · `#/validation/s0_gate_receipt_v1` (and the catalogue presence of `site_timezones` for seed discovery).

---

### 6.1 Bundle directory — `validation_bundle_2A`

* **ID → Schema:** `schemas.2A.yaml#/validation/validation_bundle_2A` (**fields-strict container** whose `index_json` follows `#/validation/bundle_index_v1`). 
* **Index schema (`bundle_index_v1`) minimum:**

  ```json
  { "files": [ { "path": "<relative>", "sha256_hex": "<hex64>" }, … ] }
  ```

  **Binding rules:** paths are **relative** to the bundle root (no leading `/`, no `..`); entries are **ASCII-lexicographically** ordered by `path`; **no duplicates**; every listed file **exists in the bundle root**; `_passed.flag` **MUST NOT** be listed. 
* **Optional non-identity artefacts:** `checks_json` (`#/validation/checks_v1`) and `metrics_json` (`#/validation/metrics_v1`) MAY be present; if present they **MUST** be listed in the index and are covered by the digest. 

**Dictionary binding (catalogue authority).** Bundle is fingerprint-scoped under the validation path family; **partition:** `[fingerprint]`; the catalogue governs filenames/layout. 

**Registry posture (existence/licensing/lineage).** Registered as **validation**; lineage depends on **`site_timezones`**, **`tz_timetable_cache`**, and **`s4_legality_report`**; write-once/atomic publish; index law is the 2A pack’s `bundle_index_v1`. 

---

### 6.2 PASS flag — `validation_passed_flag_2A`

* **ID → Schema:** `schemas.2A.yaml#/validation/passed_flag`.
  **Pattern (binding):**

  ```
  sha256_hex = <64 lowercase hex>
  ```

  (Single ASCII line; exact casing/spacing; no extra lines.) 

**Digest law (binding).** The flag value is the **SHA-256 over the raw bytes** of **all files listed in `index.json`**, concatenated in **ASCII-lex** `path` order; the flag itself is **excluded** from the hash. *(Index schema + registry notes cross-reference this law.)*

**Dictionary binding.** Fingerprint-scoped text file at the validation path family; **partition:** `[fingerprint]`. 

**Registry posture.** Depends on `validation_bundle_2A`; write-once; atomic publish. 

---

### 6.3 Referenced inputs (read-only in S5)

* **S4 report (one per discovered seed):** `schemas.2A.yaml#/validation/s4_legality_report` (**fields-strict**; includes `manifest_fingerprint`, `seed`, `generated_utc`, `status`, and `counts{…}`); partitions `[seed,fingerprint]`. These reports are **bundled verbatim** and listed in the index. 
* **S3 cache (fingerprint):** `schemas.2A.yaml#/cache/tz_timetable_cache`; S5 verifies manifest validity, path↔embed equality, and non-empty payload; a manifest snapshot MAY be bundled. 
* **S0 receipt (fingerprint):** `#/validation/s0_gate_receipt_v1`—used to assert gate/fingerprint; not necessarily bundled. 
* **S2 egress discovery:** presence of `site_timezones` partitions is determined via the catalogue path family; rows are **not** read or bundled. 

---

### 6.4 Identity & partition posture (binding)

* **Outputs:** `validation_bundle_2A`, `validation_passed_flag_2A` are partitioned by **`[fingerprint]`** only (no `seed`).
* **Path↔embed equality:** Any embedded lineage within bundled evidence remains **verbatim**; the bundle does not alter embedded fields.
* **Catalogue authority:** The Dataset Dictionary owns exact filenames/layout under the validation path family. 

---

### 6.5 Binding constraints (shape-level, S5)

* **Fields-strict.** `validation_bundle_2A.index_json` MUST validate against `bundle_index_v1`; `passed_flag` MUST match its regex exactly. 
* **Root scoping.** `index.json` MUST NOT reference paths outside the bundle root and MUST NOT list `_passed.flag`. 
* **Write-once.** Bundle and flag are immutable per fingerprint; any re-emit MUST be byte-identical (Registry posture). 

*Result:* With these anchors and catalogue/registry bindings, S5’s outputs—the **validation bundle** and **PASS flag**—are fully specified, fingerprint-scoped, and immutable, with a canonical index/digest law that downstream systems can verify to enforce **“No PASS → No Read.”***

---

## 7. Deterministic behaviour (RNG-free) **(Binding)**

### 7.1 Posture & scope

* S5 is **strictly deterministic** and **RNG-free**.
* Read permission derives from the **2A.S0 receipt** for the target `manifest_fingerprint`.
* Inputs are resolved **only via the Dataset Dictionary**; literal/relative host paths are **forbidden**.
* S5 **does not** re-compute S2–S4 logic, read site rows, or parse raw tzdb; it **verifies** evidence and **seals** it.

### 7.2 Fingerprint & seed discovery (canonical)

1. **Bind fingerprint.** Select the target `manifest_fingerprint` (S5 is fingerprint-scoped; no `seed`).
2. **Discover seeds (SEEDS).** Using the **Dictionary path family** for S2 egress, define
   **`SEEDS = { seed | exists data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/ }`**.
   Discovery is **catalogue-only**; S5 SHALL NOT read site rows.
3. **Require S4 PASS per seed.** For **every `seed ∈ SEEDS`**, require a matching `s4_legality_report` at `[seed,fingerprint]` with **`status="PASS"`**. Absence or non-PASS **ABORTS** the run.

### 7.3 Evidence checks (authoritative sources)

* **S3 cache:** Verify `tz_timetable_cache` (schema-valid, **path↔embed equality**, `rle_cache_bytes>0`).
* **S4 reports:** For each `seed ∈ SEEDS`, verify the report validates against its anchor and has `status="PASS"`.
* **S0 receipt:** Verify presence and fingerprint match (no bundle re-hash).

### 7.4 Bundle assembly (staging; bytes must be verbatim)

S5 SHALL assemble a **staging directory** that becomes the bundle root. All copied files **MUST** be **byte-identical** to their catalogued sources.

**Canonical relative paths (binding):**

* Per-seed legality reports:
  `evidence/s4/seed={seed}/s4_legality_report.json` (one file for each `seed ∈ SEEDS`).
* Cache manifest snapshot (optional but recommended):
  `evidence/s3/tz_timetable_cache.manifest.json` (verbatim copy of the cache manifest).
* Optional diagnostics (non-identity):
  `checks.json` (matches `checks_v1`), `metrics.json` (matches `metrics_v1`).

**Path constraints (binding):**

* Every `index.json` entry `path` is **relative** to the bundle root; **no leading “/”**, **no “.” or “..” segments**.
* `_passed.flag` **MUST NOT** be copied into the staging set and **MUST NOT** appear in the index.

### 7.5 Index construction (authoritative order)

S5 SHALL create **`index.json`** listing **every** bundled file as `{path, sha256_hex}` where `sha256_hex` is the SHA-256 of the file’s **raw bytes**.

**Binding rules:**

* The array **MUST** be sorted in **ASCII-lexicographic order by `path`** (byte-wise comparison of UTF-8).
* **No duplicates**; every listed file **exists**; no entry references a path outside the bundle root.
* The index **MUST NOT** list `_passed.flag`.

### 7.6 Flag computation (canonical hashing law)

* Concatenate the **raw bytes** of the files listed in `index.json` in **exact index order**.
* Compute SHA-256 over that concatenation → **`<digest>`**.
* Write `_passed.flag` in the bundle root as the **single ASCII line**:

  ```
  sha256_hex = <digest>
  ```

  where `<digest>` is **64 lowercase hex**. Whitespace/casing is **exact**; extra lines are **forbidden**.
* The flag **itself is excluded** from the hash.

### 7.7 Emission & identity discipline

* **Partitioning:** publish to `data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/` (**`[fingerprint]`** only).
* **Atomic publish (binding):** stage files → write `index.json` → compute digest → write `_passed.flag` → **single atomic move** into the fingerprint partition.
* **Write-once:** if the partition already exists, any re-emit **MUST** be **byte-identical**; otherwise **ABORT**.
* **Path↔embed equality:** bundled evidence is copied **verbatim**; embedded lineage values remain unchanged.

### 7.8 Prohibitions (non-behaviours)

S5 **SHALL NOT**:

* include `_passed.flag` in `index.json` or hash it;
* reference paths outside the bundle root;
* modify any evidence bytes (S4 reports, cache manifest);
* read site rows or parse raw tzdb;
* use network or non-catalogue paths;
* introduce RNG or wall-clock time (any diagnostics timestamps must be derived from sealed inputs).

### 7.9 Idempotency

Given the same **S0 receipt**, the same **S3 cache**, and the same **set of S4 PASS reports for SEEDS** discovered from the catalogue, S5 **SHALL** produce **byte-identical** bundle contents, an identical `index.json` (including order), and the same `_passed.flag` value.

---

## 8. Identity, partitions, ordering & merge discipline **(Binding)**

### 8.1 Identity tokens

* **Selection identity:** exactly one **`manifest_fingerprint`** per publish of the S5 outputs.
* **No seed:** S5 outputs are **fingerprint-scoped only**; `seed` is not a partition key for S5.
* **Path↔embed equality:** Any embedded lineage present inside bundled evidence (e.g., S4 reports) remains **verbatim**; S5 SHALL NOT alter embedded values. The bundle’s identity is the **partition path** itself.

### 8.2 Partitions & path family

* **Outputs:**
  `validation_bundle_2A`, `validation_passed_flag_2A` →
  `data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/`
* **Partitions (binding):** **`[fingerprint]` only**; no additional partitions are permitted.
* **Catalogue authority:** The Dataset Dictionary governs filenames/layout inside the validation path family.

### 8.3 Index order is the only authoritative order

* **Authoritative order:** The ordering of entries in `index.json` (sorted **ASCII-lex by `path`**) is the **sole** order used for hashing and attestation.
* **Non-authoritative order:** Filesystem/directory listing order and write order are **non-authoritative**.

### 8.4 Write posture & immutability

* **Single-writer, write-once per fingerprint.** If any artefact already exists under the target fingerprint, any re-emit **MUST** be **byte-identical**; otherwise the run **MUST ABORT**.
* **Atomic publish (binding):** stage bundle files → write `index.json` (ASCII-lex) → compute digest → write `_passed.flag` → **single atomic move** into the fingerprint partition.
* **No in-place edits/tombstones.** Updates occur only by producing a **new fingerprint** upstream (S0 reseal).

### 8.5 Concurrency & conflict detection

* **Single-writer per identity.** Concurrent writes targeting the same `fingerprint` are not permitted.
* **Conflict definition:** the presence of any file in `…/validation/fingerprint={manifest_fingerprint}/` constitutes a conflict; S5 **MUST** abort rather than overwrite or mutate.

### 8.6 Discovery & selection (downstream contract)

* **Selection:** Downstream systems **MUST** select the S5 outputs by **`manifest_fingerprint`** via the **Dataset Dictionary** (no literal paths).
* **Gate enforcement:** Consumers **MUST** verify `_passed.flag` by recomputing the digest over the files listed in `index.json` (ASCII-lex order of `path`, raw bytes, flag excluded) before reading any 2A egress.

### 8.7 Retention, licensing & relocation

* **Retention/licence:** As declared by Dictionary/Registry (validation artefacts typically have longer TTL).
* **Relocation:** Movement that preserves the Dictionary path family and partitioning is non-breaking; any change that alters the partition key or path tokens is **breaking** and out of scope for S5.

*Effect:* These rules make the S5 outputs uniquely addressable by **`manifest_fingerprint`**, immutable once published, and unambiguous to verify—ensuring a stable PASS gate for all downstream 2A consumers.

---

## 9. Acceptance criteria (validators) **(Binding)**

**PASS definition.** A run of 2A.S5 is **ACCEPTED** iff **all** mandatory validators below pass. Any **Abort** failure causes the run to **FAIL** and nothing from §5 may be published. (**Warn** not used in S5.)

### 9.1 Gate & input resolution (mandatory)

**V-01 — S0 receipt present (Abort).** A valid 2A.S0 gate receipt exists and schema-validates for the target `manifest_fingerprint`.
**V-02 — Dictionary resolution (Abort).** Inputs resolve by **ID** via the Dataset Dictionary (no literal paths): `tz_timetable_cache` `[fingerprint]`, `site_timezones` `[seed,fingerprint]` (for discovery), and `s4_legality_report` `[seed,fingerprint]`.
**V-03 — Seed discovery completeness (Abort).** The discovered seed set **SEEDS** equals exactly the set of `seed` partitions present for `site_timezones` at the target `manifest_fingerprint`.

### 9.2 Evidence readiness (mandatory)

**V-04 — Cache ready (Abort).** `tz_timetable_cache` manifest is schema-valid, **path↔embed equality** holds, and payload is non-empty (all referenced files exist).
**V-05 — S4 coverage & PASS (Abort).** For **each `seed ∈ SEEDS`**, a single `s4_legality_report` exists at `[seed,fingerprint]`, schema-valid, with `status="PASS"`.

### 9.3 Bundle structure (mandatory)

**V-06 — Index present & schema-valid (Abort).** `index.json` validates against `#/validation/bundle_index_v1`.
**V-07 — Index order & uniqueness (Abort).** `index.json.files[*].path` are **ASCII-lex** ordered; no duplicates.
**V-08 — Root scoping (Abort).** Every `index.json` path is **relative** to the bundle root, contains no leading “/”, and no “.”/“..” segments; no entry points outside the root.
**V-09 — All files indexed (Abort).** Every file in the bundle root **except** `_passed.flag` appears in `index.json`; no unlisted files.
**V-10 — Flag excluded from index (Abort).** `_passed.flag` does **not** appear in `index.json`.

### 9.4 Byte integrity & attestation (mandatory)

**V-11 — Evidence is verbatim (Abort).** Each bundled evidence file (e.g., every S4 report; cache manifest snapshot if included) is **byte-identical** to its catalogued source.
**V-12 — Hex format validity (Abort).** Every `sha256_hex` in `index.json` and the flag value are **64 lowercase hex**.
**V-13 — Flag format exact (Abort).** `_passed.flag` is a **single ASCII line** exactly `sha256_hex = <hex64>` (lowercase; no extra whitespace/lines).
**V-14 — Digest correctness (Abort).** Recompute SHA-256 over the **raw bytes** of files listed in `index.json`, concatenated in **index order** → equals the flag value.

### 9.5 Identity & merge (mandatory)

**V-15 — Partitioning (Abort).** Outputs are emitted under `data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/` (**`[fingerprint]`** only).
**V-16 — Write-once (Abort).** If the target fingerprint partition already exists, newly written bytes must be **byte-identical**; otherwise **ABORT**.

### 9.6 Outcome semantics

* **PASS:** V-01…V-16 pass.
* **FAIL:** Any **Abort** validator fails.

### 9.7 (For §10) Validator → error-code mapping (normative)

| Validator                        | Error code(s)                                                             |
|----------------------------------|---------------------------------------------------------------------------|
| V-01 S0 receipt present          | **2A-S5-001 MISSING_S0_RECEIPT**                                          |
| V-02 Dictionary resolution       | **2A-S5-010 INPUT_RESOLUTION_FAILED**                                     |
| V-03 Seed discovery completeness | **2A-S5-011 WRONG_PARTITION_SELECTED** *(or context: discovery mismatch)* |
| V-04 Cache ready                 | **2A-S5-020 CACHE_INVALID**                                               |
| V-05 S4 coverage & PASS          | **2A-S5-030 MISSING_OR_FAILING_S4**                                       |
| V-06 Index schema-valid          | **2A-S5-040 INDEX_SCHEMA_INVALID**                                        |
| V-07 Index order & uniqueness    | **2A-S5-041 INDEX_NOT_ASCII_LEX** · **2A-S5-043 INDEX_DUPLICATE_ENTRY**   |
| V-08 Root scoping                | **2A-S5-042 INDEX_PATH_OUT_OF_ROOT**                                      |
| V-09 All files indexed           | **2A-S5-044 INDEX_UNLISTED_FILE**                                         |
| V-10 Flag excluded from index    | **2A-S5-045 FLAG_LISTED_IN_INDEX**                                        |
| V-11 Evidence is verbatim        | **2A-S5-046 EVIDENCE_NOT_VERBATIM**                                       |
| V-12 Hex format validity         | **2A-S5-051 FLAG_OR_INDEX_HEX_INVALID**                                   |
| V-13 Flag format exact           | **2A-S5-052 FLAG_FORMAT_INVALID**                                         |
| V-14 Digest correctness          | **2A-S5-050 FLAG_DIGEST_MISMATCH**                                        |
| V-15 Partitioning                | **2A-S5-012 PARTITION_PURITY_VIOLATION**                                  |
| V-16 Write-once                  | **2A-S5-060 IMMUTABLE_PARTITION_OVERWRITE**                               |

*Authorities:* Bundle/index/flag shapes by the 2A schema pack; catalogue paths/partition by the 2A Dictionary; existence/licensing/lineage by the 2A Registry; gate evidence by the S0 receipt.

---

## 10. Failure modes & canonical error codes **(Binding)**

**Code format.** `2A-S5-XXX NAME` (stable identifiers).
**Effect classes.** `Abort` = run MUST fail and emit nothing; `Warn` = non-blocking, MUST be surfaced in the run-report (S5 defines no Warns).
**Required context on raise.** Include: `manifest_fingerprint` and, where relevant, `seed`, `dataset_id`, `catalog_path`, `index_path`, `flag_value`, and a short hint (e.g., offending `path`).

### 10.1 Gate & input resolution

* **2A-S5-001 MISSING_S0_RECEIPT (Abort)** — No valid 2A.S0 receipt for the target fingerprint.
  *Remediation:* publish/repair S0; rerun S5.
* **2A-S5-010 INPUT_RESOLUTION_FAILED (Abort)** — Any required input (cache, S4 report, or discovery catalogue) fails **Dictionary** resolution or Registry authorisation.
  *Remediation:* fix Dictionary/Registry entries/IDs; rerun.
* **2A-S5-011 WRONG_PARTITION_SELECTED (Abort)** — Seed discovery mismatch (e.g., probing the wrong fingerprint or misreading seed partitions).
  *Remediation:* restrict discovery to `…/site_timezones/seed={seed}/fingerprint={fingerprint}/`; rerun.

### 10.2 Evidence readiness

* **2A-S5-020 CACHE_INVALID (Abort)** — `tz_timetable_cache` manifest invalid, path↔embed mismatch, or payload empty/missing files.
  *Remediation:* repair S3 cache; rerun S5 after S3 passes.
* **2A-S5-030 MISSING_OR_FAILING_S4 (Abort)** — For at least one discovered seed, no S4 report exists **or** status ≠ `PASS`.
  *Remediation:* ensure S4 produces `status="PASS"` for every seed; rerun.

### 10.3 Bundle structure (index rules)

* **2A-S5-040 INDEX_SCHEMA_INVALID (Abort)** — `index.json` violates `#/validation/bundle_index_v1` (shape/fields).
  *Remediation:* emit schema-valid index only.
* **2A-S5-041 INDEX_NOT_ASCII_LEX (Abort)** — `files[*].path` not strictly **ASCII-lex** sorted.
  *Remediation:* sort strictly byte-wise by `path`; rerun.
* **2A-S5-042 INDEX_PATH_OUT_OF_ROOT (Abort)** — Index contains absolute paths, `.`/`..` segments, or references outside the bundle root.
  *Remediation:* restrict to **relative** in-root paths only.
* **2A-S5-043 INDEX_DUPLICATE_ENTRY (Abort)** — Duplicate `path` entries in `files[*]`.
  *Remediation:* de-duplicate; rerun.
* **2A-S5-044 INDEX_UNLISTED_FILE (Abort)** — A file exists under the bundle root but is not listed in `index.json`.
  *Remediation:* list every file (except `_passed.flag`) or remove extras.
* **2A-S5-045 FLAG_LISTED_IN_INDEX (Abort)** — `_passed.flag` appears in `index.json`.
  *Remediation:* remove it from the index; recompute digest; rerun.

### 10.4 Byte integrity & attestation

* **2A-S5-046 EVIDENCE_NOT_VERBATIM (Abort)** — Any bundled evidence (e.g., S4 report, cache manifest snapshot) differs from its catalogued bytes.
  *Remediation:* copy verbatim bytes; rerun.
* **2A-S5-051 FLAG_OR_INDEX_HEX_INVALID (Abort)** — Any `sha256_hex` (in index or flag) is not **64 lowercase hex**.
  *Remediation:* fix casing/length/content; rerun.
* **2A-S5-052 FLAG_FORMAT_INVALID (Abort)** — `_passed.flag` is not exactly `sha256_hex = <hex64>` on a single ASCII line (or contains extra whitespace/lines).
  *Remediation:* write the exact canonical line; rerun.
* **2A-S5-050 FLAG_DIGEST_MISMATCH (Abort)** — SHA-256 over the **raw bytes** of indexed files (in index order) ≠ flag value.
  *Remediation:* correct index order/content or recompute flag; rerun.

### 10.5 Output identity & merge

* **2A-S5-012 PARTITION_PURITY_VIOLATION (Abort)** — Outputs not emitted under `…/validation/fingerprint={manifest_fingerprint}/` (extra partitions present).
  *Remediation:* emit only under the fingerprint partition.
* **2A-S5-060 IMMUTABLE_PARTITION_OVERWRITE (Abort)** — Attempt to write non-identical bytes to an existing fingerprint partition.
  *Remediation:* publish byte-identically or use a new fingerprint (via S0 reseal).

### 10.6 Authority conflict (resolution rule)

* **2A-S5-080 AUTHORITY_CONFLICT (Abort)** — Irreconcilable disagreement among **Schema, Dictionary, Registry** after applying precedence (**Schema › Dictionary › Registry**).
  *Remediation:* fix the lower-precedence authority (or the schema if wrong); rerun.

> The §9 validator→code mapping MUST reflect these identifiers exactly. New failure conditions introduced by future revisions MUST allocate **new codes** (append-only) and MUST NOT repurpose existing identifiers.

---

## 11. Observability & run-report **(Binding)**

### 11.1 Scope & posture

* **Purpose.** Record auditable evidence of S5’s gate verification, seed discovery, evidence checks, bundle assembly, index/digest computation, and flag emission.
* **Not identity-bearing.** The run-report does **not** affect dataset identity or the PASS gate.
* **One per run.** Exactly one report per attempted S5 run (success or failure).

---

### 11.2 Run-report artefact (normative content)

A single UTF-8 JSON object **SHALL** be written with at least the fields below. Missing required fields are **non-fatal** only when explicitly marked “optional”; otherwise they **MUST** be present.

**Header**

* `segment : "2A"`
* `state : "S5"`
* `status : "pass" | "fail"`
* `manifest_fingerprint : hex64`
* `started_utc, finished_utc : rfc3339_micros`
* `durations : { wall_ms : uint64 }`

**Gate & inputs**

* `s0.receipt_path : string`
* `s0.verified_at_utc : rfc3339_micros`
* `inputs.cache.path : string` — Dictionary path to `tz_timetable_cache/fingerprint={manifest_fingerprint}/`
* `inputs.cache.tzdb_release_tag : string`
* `inputs.cache.rle_cache_bytes : uint64`
* `inputs.cache.tz_index_digest : hex64`

**Seed discovery & S4 coverage**

* `seeds.discovered : uint32`
* `seeds.list : uint64[]` — **exact** set of `seed` values discovered from `site_timezones` for this fingerprint
* `s4.covered : uint32` — number of seeds with a report
* `s4.missing : uint32` — EXPECT `0` on PASS
* `s4.failing : uint32` — EXPECT `0` on PASS
* `s4.sample_missing : uint64[]` — optional, small non-exhaustive sample (only on FAIL)

**Bundle assembly**

* `bundle.path : string` — Dictionary path to `data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/`
* `bundle.files_indexed : uint32` — count of entries in `index.json`
* `bundle.bytes_indexed : uint64` — sum of sizes for indexed files
* `bundle.index_sorted_ascii_lex : bool` — EXPECT `true` on PASS
* `bundle.index_path_root_scoped : bool` — EXPECT `true` on PASS (`no /, ., ..`)
* `bundle.includes_flag_in_index : bool` — EXPECT `false` on PASS

**Attestation**

* `digest.computed_sha256 : hex64` — SHA-256 over **raw bytes** of indexed files in **ASCII-lex** order
* `flag.value : hex64` — value written in `_passed.flag`
* `flag.format_exact : bool` — single ASCII line, exactly `sha256_hex = <hex64>`
* `digest.matches_flag : bool` — **MUST** be `true` on PASS

**Diagnostics**

* `warnings : array<error_code>` — none expected in S5, but allowed if programme policy adds Warns
* `errors : array<{code, message, context}>` — on failure, canonical codes with brief context

**Optional (advisory, non-binding)**

* `determinism.partition_hash : hex64` — directory-level hash of the emitted fingerprint partition (post-publish)
* `checks : object` — any non-identity checks/metrics S5 chose to emit in the bundle (keys mirror `checks_v1` / `metrics_v1`)

---

### 11.3 Structured logs (minimum event kinds)

S5 **SHALL** emit machine-parseable log records correlated to the report. Minimum events:

* **`GATE`** — start/end + result of S0 receipt verification; include `manifest_fingerprint`.
* **`DISCOVERY`** — seeds discovered (`seeds.list`, counts).
* **`EVIDENCE`** — cache readiness (tag, digest, bytes), S4 coverage (covered/missing/failing).
* **`INDEX`** — index entries count, ASCII-lex order check, root-scoping check.
* **`DIGEST`** — computed SHA-256 over indexed raw bytes, flag value, match result.
* **`VALIDATION`** — each validator outcome `{id, result, code?}` for §9 V-01…V-16.
* **`EMIT`** — successful publication of bundle + `_passed.flag` with Dictionary path.

Every record **SHALL** include: `timestamp_utc (rfc3339_micros)`, `segment`, `state`, `manifest_fingerprint`, and `severity (INFO|WARN|ERROR)`.

---

### 11.4 Discoverability, retention & redaction

* **Discoverability.** The run-report path **MUST** be surfaced in CI/job metadata alongside the Dictionary path of the validation output.
* **Retention.** Run-report retention is programme policy; changing TTL **MUST NOT** alter dataset identity or partitioning.
* **Redaction.** Reports/logs **MUST NOT** embed raw evidence bytes or any per-site rows; only IDs, paths, counts, digests, timestamps, and canonical error codes are permitted.

---

## 12. Performance & scalability **(Informative)**

### 12.1 Workload shape

* **Reads:** fingerprint-scoped **S3 cache manifest** (small), **S4 reports for each discovered seed** (one JSON per seed).
* **Compute:** discover seeds via **catalogue listing** → validate evidence presence/PASS → assemble **index.json** (ASCII-lex) → **streaming SHA-256** over indexed files → write `_passed.flag`.
* **Writes:** one fingerprint-scoped **bundle directory** (small JSONs + verbatim evidence) and a single-line **`_passed.flag`**.

### 12.2 Asymptotics (N = files indexed; B = sum of indexed file sizes)

* **Time:** `O(N log N)` to sort index paths (ASCII-lex) + **Θ(B)** to stream-hash raw bytes.
* **Space:** **O(1)** in B (hashing is streamed) + **O(N)** for the in-memory file list and per-file metadata.

### 12.3 Memory model

* Maintain an in-memory list of **relative paths + sha256_hex** for `index.json`.
* Hash **files one by one** in index order; do not buffer entire evidence.
* Copy evidence **verbatim** (byte-for-byte) from catalogue to staging; avoid JSON re-encoding of S4/S3 artefacts.

### 12.4 I/O profile

* **Input:** a handful of JSON files (S4 per seed) + the S3 cache manifest; typically KB–MB scale.
* **Output:**

  * `index.json` (KBs)
  * optional `checks.json`/`metrics.json` (KBs)
  * copied S4 reports (aggregate ≈ number_of_seeds × small JSON)
  * `_passed.flag` (single line)

### 12.5 Parallelism & concurrency

* **Evidence reads:** may be performed in parallel (per-seed), but final **index.json** **MUST** be materialised and sorted deterministically (ASCII-lex).
* **Hashing:** may precompute per-file hashes in parallel; the **attestation hash** is computed over **raw bytes concatenated in index order**, so perform a final serial pass (or a deterministic chunked concatenation).
* **Publish:** still **single-writer, write-once** for the fingerprint partition.

### 12.6 Hot spots & guardrails

* **Large seed count:** the dominant cost becomes reading many small S4 JSONs; mitigate with parallel reads and minimal JSON parse (schema validation only).
* **Index stability:** enforce strict **ASCII-lex** ordering; normalise path strings once (no locale-dependent compares).
* **Hex/format errors:** validate hex length/case early to avoid recomputing the digest only to fail formatting later.
* **Root scoping:** reject absolute paths or `.`/`..` early, before hashing or copy.
* **Verbatim copy:** compare file sizes + hash against catalogue source when staging to guard against accidental re-encoding.

### 12.7 Determinism considerations

* Discovery set **SEEDS** comes **only** from the catalogue path family; use a stable enumeration.
* Build `index.json` in a **pure function** of the evidence set (relative paths + per-file SHA-256) → sort → emit; avoid timestamps or non-deterministic fields.
* Any optional diagnostics timestamps **MUST** derive from sealed inputs (e.g., S0 time), never wall-clock.

### 12.8 Scalability knobs (programme-level)

* Cap on **max seeds per bundle** (advisory) or shard publish jobs by fingerprint if seeds are extremely numerous; still ends as a single bundle emit.
* **Parallel read degree** for S4 report validation and per-file hashing.
* **Hash chunk size** for streamed SHA-256 to balance CPU vs syscalls.
* Optional toggle to include/exclude **checks/metrics** files (non-identity) in the bundle.

### 12.9 Re-run & churn costs

* Re-running S5 with **unchanged evidence** for the same fingerprint reproduces **byte-identical** bundle, `index.json`, and `_passed.flag`.
* Any upstream change (new/changed S4 report, new cache manifest, different seed set) entails a **new fingerprint** (via S0 reseal) and a fresh S5 emit; prior bundles remain immutable.

### 12.10 Typical envelopes (order-of-magnitude)

* **Seeds per fingerprint:** tens to low hundreds (programme-dependent).
* **Bundle file count (N):** `|SEEDS|` (S4 reports) + 1 (S3 manifest snapshot, if included) + 1–2 (checks/metrics).
* **Indexed bytes (B):** MBs at most for typical configurations (dominated by S4 JSONs).
* **Runtime:** seconds to low minutes, dominated by I/O and hashing **Θ(B)**; CPU is light.

---

## 13. Change control & compatibility **(Binding)**

### 13.1 Versioning & document status

* **SemVer** applies to this state spec (`MAJOR.MINOR.PATCH`).

  * **PATCH:** editorial clarifications that **do not** change behaviour, shapes, validators, or outcomes.
  * **MINOR:** strictly backward-compatible additions that **do not** alter identity, partitions, bundle/index/flag laws, discovery rule, or PASS/FAIL results.
  * **MAJOR:** any change that can affect identity, partitioning, evidence requirements, index/digest/flag law, discovery/completeness rules, or validator outcomes.

### 13.2 Stable compatibility surfaces (must remain invariant)

1. **Identity:** S5 outputs are selected by **`manifest_fingerprint`**; partitions are **`[fingerprint]`** only; **path↔embed equality** holds.
2. **Outputs:** existence and IDs/anchors of **`validation_bundle_2A`**, **`bundle_index_v1`**, and **`validation_passed_flag_2A`**; write-once/atomic publish.
3. **Index law:** `index.json` lists **every** bundled file (except `_passed.flag`) as `{path, sha256_hex}`, paths are **relative**, **ASCII-lex** sorted by `path`, no duplicates, no out-of-root entries.
4. **Digest & flag law:** flag line **exactly** `sha256_hex = <hex64>`; `<hex64>` is SHA-256 over the **raw bytes** of indexed files in **index order**; flag file **excluded**.
5. **Evidence rule:** for the target fingerprint, **S3 cache** is valid/non-empty; **SEEDS** are discovered strictly from the **Dictionary**; for **every** discovered seed, an **S4 report with `status="PASS"`** exists and is bundled verbatim.
6. **No site-row reads / no tzdb parsing:** S5 verifies and seals; it does not recompute S2–S4.
7. **Authorities:** **Schema** = shape; **Dictionary** = IDs→paths/partitions/format; **Registry** = existence/licence/retention/lineage; precedence **Schema › Dictionary › Registry**.
8. **Validator/code semantics:** §9 validators and §10 error codes maintain their meanings.

### 13.3 Backward-compatible changes (**MINOR** or **PATCH**)

Allowed when they **do not** change identity or acceptance:

* Add **non-identity** files to the bundle (e.g., `checks.json`, `metrics.json`), provided they are **listed in `index.json`** and follow existing laws.
* Extend **run-report**/logs with extra non-identity fields.
* Add **Warn-only** diagnostics (programme policy) without converting any existing PASS to FAIL.
* Clarify text or expand accepted formats that **do not** alter index/flag/digest law (e.g., documenting additional advisory files or directory naming within the bundle root).
* Extend `bundle_index_v1` **optionally** (e.g., allow extra non-identity fields per entry) while keeping existing required fields and rules unchanged.

> Note: S5 is fields/format **strict** for the flag and index ordering. Any change that alters the canonical line, the hashing inputs, or their order is **MAJOR**.

### 13.4 Breaking changes (**MAJOR**)

Require a MAJOR bump and downstream coordination:

* Changing **partitions** (adding `seed`, renaming keys) or relaxing **path↔embed** rules.
* Renaming/removing **`validation_bundle_2A`**, **`bundle_index_v1`**, or **`validation_passed_flag_2A`** anchors/IDs; relocating outputs to a new path family.
* Altering the **index law** (e.g., sort order, path relativity, inclusion/exclusion set), the **digest law** (algorithm or byte concatenation rule), or the **flag format**.
* Modifying **evidence requirements** (e.g., changing seed discovery rule, allowing S4 FAIL, or dropping cache readiness checks).
* Converting any existing **Warn** to **Abort**, or repurposing error codes.
* Making new **required** fields in index/flag schemas or removing existing required fields.
* Allowing non-verbatim evidence copies or admitting paths outside the bundle root.

### 13.5 Deprecation policy

* **Announce → grace → remove.** Mark features **Deprecated** at least **one MINOR** before removal and record an **Effective date**.
* **No repurposing.** Deprecated fields/codes/IDs are never reused; removal only at **MAJOR**.
* **Alias window.** For index schema evolution, provide **`bundle_index_v2`** alongside `v1` for at least one MINOR with identical hashing semantics before removing `v1`.

### 13.6 Co-existence & migration

* **Dual-anchor window:** introduce new index or bundle anchors (e.g., `bundle_index_v2`) while keeping `v1`; hashing law must remain identical during the window.
* **New seeds after publish:** Because S5 is **write-once per fingerprint**, additional `site_timezones` seeds discovered **after** a bundle is published **cannot** be added in place. Programme policy **MUST** reseal in **S0** (new `manifest_fingerprint`) and re-run S2–S5 to produce a new bundle for the updated fingerprint.
* **Idempotent re-runs:** With unchanged evidence for the same fingerprint, S5 reproduces byte-identical bundle, index, and `_passed.flag`.

### 13.7 Reserved extension points

* **Bundle root structure:** Additional subdirectories under the bundle root (e.g., `evidence/s4/…`, `evidence/s3/…`, `diag/…`) are allowed **only** if listed in `index.json` and do not affect identity; consumers must ignore unknown folders.
* **Checks/metrics:** Optional `checks.json`/`metrics.json` may evolve additively (non-identity); their presence is not required for PASS.

### 13.8 External dependency evolution

* If upstream states (S2–S4) **add non-identity fields** or change internal formats without altering their identities, S5 may continue to copy evidence verbatim—**no spec change**.
* If upstream acceptance changes (e.g., S4 alters legality semantics) affect PASS determination, this is **breaking** for S5 only if S5’s validators must change; coordinate as a MAJOR across 2A.

### 13.9 Governance & change process

Every change SHALL include: (i) version bump rationale, (ii) compatibility impact (Patch/Minor/Major), (iii) updated anchors/Dictionary/Registry stanzas (if any), (iv) validator/error-code diffs, and (v) migration notes.
Frozen specs SHALL record an **Effective date**; downstream pipelines target **frozen** or explicitly authorised **alpha** versions.

### 13.10 Inter-state coupling

* **Upstream:** depends only on S0 receipt, S3 cache, seed discovery from S2 catalogue, and S4 PASS per discovered seed.
* **Downstream:** any reader of 2A egress **MUST** verify `_passed.flag` against `index.json` per the hashing law; any S5 change that would force different verification or alter the gate semantics is **breaking**.

---

## Appendix A — Normative cross-references *(Informative)*

> Pointers only. **Schema = shape authority**; **Dictionary = IDs → paths/partitions/format**; **Registry = existence/licensing/retention/lineage**. S5 reads only the inputs listed; all IDs resolve via the Dictionary.

### A1. Layer-1 governance (global rails)

* **Identity & Path Law** — path↔embed equality; partition keys are authoritative.
* **Gate Law** — “No PASS → No Read”; S5 relies on the S0 receipt (does not re-hash upstream bundles).
* **Fingerprint Law** — canonical sealed-manifest → `manifest_fingerprint` (fixed upstream in S0).
* **Index/Digest/Flag Law** — ASCII-lex ordering of `index.json` paths; digest over **raw bytes** of indexed files in **index order**; `_passed.flag` excluded; flag line exactly `sha256_hex = <hex64>`.
* **Numeric policy** — layer-wide binary64 and RFC-3339 timestamp conventions (applies to any optional diagnostics).

### A2. Upstream evidence S5 verifies

* **S0 gate receipt** — `schemas.2A.yaml#/validation/s0_gate_receipt_v1` (fingerprint-scoped).
* **S3 cache** — `schemas.2A.yaml#/cache/tz_timetable_cache` (fingerprint) — manifest validity, path↔embed equality, non-empty payload.
* **S2 egress (discovery surface)** — `schemas.2A.yaml#/egress/site_timezones` (partitions `[seed,fingerprint]`) — used **only** to discover the seed set for the fingerprint.
* **S4 legality report (per discovered seed)** — `schemas.2A.yaml#/validation/s4_legality_report` (partitions `[seed,fingerprint]`) — must exist with `status="PASS"` for every discovered seed.

### A3. S5 outputs (this state)

* **Validation bundle** — `schemas.2A.yaml#/validation/validation_bundle_2A` containing
  **`#/validation/bundle_index_v1`** (`files[*].path`, `files[*].sha256_hex`, ASCII-lex ordered).
* **PASS flag** — `schemas.2A.yaml#/validation/passed_flag` (single-line canonical format).
* **Catalogue path family** — `data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/` (partitions `[fingerprint]` only).

### A4. Dataset Dictionary (catalogue authority)

* **Inputs:**
  • `site_timezones` → `…/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/` (discovery only)
  • `tz_timetable_cache` → `…/tz_timetable_cache/fingerprint={manifest_fingerprint}/`
  • `s4_legality_report` → `…/legality_report/seed={seed}/fingerprint={manifest_fingerprint}/s4_legality_report.json`
* **Outputs:**
  • `validation_bundle_2A` and `_passed.flag` → `…/validation/fingerprint={manifest_fingerprint}/`

### A5. Artefact Registry (existence/licensing/lineage)

* **`site_timezones`** — egress; write-once; final-in-layer.
* **`tz_timetable_cache`** — cache; lineage `→ tzdb_release`; write-once.
* **`s4_legality_report`** — validation evidence; lineage depends on S2/S3.
* **`validation_bundle_2A`** — validation artefact; lineage depends on `site_timezones` (seed discovery), `tz_timetable_cache`, and all `s4_legality_report`s for the fingerprint; index law = 2A pack’s `bundle_index_v1`.
* **`validation_passed_flag_2A`** — depends on the bundle; write-once/atomic publish.

### A6. Seed discovery rule (catalogue-only)

* Define **SEEDS** as the exact set of `seed` partitions present under
  `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` in the Dictionary.
* For **every** `seed ∈ SEEDS`, a matching S4 report **must** exist at the same `(seed,fingerprint)` with `status="PASS"` and be bundled verbatim.

### A7. Programme context

* **State flow:** S0 (gate) → S1 (geometry) → S2 (overrides) → S3 (cache) → S4 (legality) → **S5 (bundle + flag; PASS gate)**.
* **Downstream contract:** Consumers of 2A egress **MUST** verify `_passed.flag` by re-computing the digest over `index.json`’s files (ASCII-lex order, raw bytes, flag excluded) before any read.

---
