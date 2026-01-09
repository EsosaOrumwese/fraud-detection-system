# State 2A.S4 — Legality (DST gaps & folds)

## 1. Document metadata & status **(Binding)**

**Title:** Layer-1 · Segment 2A · State-4 — Legality (DST gaps & folds)
**Short name:** 2A.S4 “Legality”
**Layer/Segment/State:** L1 / 2A (Civil Time) / S4
**Doc ID:** `layer1/2A/state-4`
**Version (semver):** `v1.0.0-alpha` *(advance per change control)*
**Status:** `draft | alpha | frozen` *(normative at ≥ `alpha`; semantics locked at `frozen`)*
**Owners:** Design Authority (DA): ‹name› • Review Authority (RA): ‹name›
**Effective date:** ‹YYYY-MM-DD›
**Canonical location:** ‹repo path to this spec file›

**Normative cross-references (pointers only):**

* **Gate & sealed inputs:** `schemas.2A.yaml#/validation/s0_gate_receipt_v1` (receipt for target `manifest_fingerprint`).
* **Inputs:** `schemas.2A.yaml#/egress/site_timezones` (from S2, `[seed,fingerprint]`), `schemas.2A.yaml#/cache/tz_timetable_cache` (from S3, `[fingerprint]`).
* **Output (this state):** `schemas.2A.yaml#/validation/s4_legality_report`.
* **Catalogue & registry:** Dataset Dictionary entries for `site_timezones`, `tz_timetable_cache`, and `s4_legality_report`; Artefact Registry stanzas (existence/licence/retention; lineage).
* **Layer-1 governance:** Identity & Path Law (path↔embed equality), Gate Law (“No PASS → No Read”), Hashing/Fingerprint Law, Numeric Policy.

**Conformance & interpretation:**

* Sections marked **Binding** are normative; **Informative** sections do not create obligations.
* Keywords **MUST/SHALL/SHOULD/MAY** follow RFC 2119/8174.
* This is a **design specification**: it defines required behaviours, identities, inputs/outputs, and inter-state contracts; it does **not** prescribe implementations or pseudocode.

**Change log (summary):**

* `v1.0.0-alpha` - Initial specification for 2A.S4 (Legality report using S2 `site_timezones` + S3 `tz_timetable_cache`). Subsequent edits follow §13 Change Control.

---

### Contract Card (S4) - inputs/outputs/authorities

**Inputs (authoritative; see Section 3.2 for full list):**
* `s0_gate_receipt_2A` - scope: FINGERPRINT_SCOPED; source: 2A.S0
* `site_timezones` - scope: SEED+FINGERPRINT; source: 2A.S2
* `tz_timetable_cache` - scope: FINGERPRINT_SCOPED; source: 2A.S3

**Authority / ordering:**
* S4 emits a report only; no new order authority is created.

**Outputs:**
* `s4_legality_report` - scope: SEED+FINGERPRINT; gate emitted: none

**Sealing / identity:**
* External inputs (ingress/reference/1B egress/2A policy) MUST appear in `sealed_inputs_2A` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or schema violations -> abort; no outputs published.

## 2. Purpose & scope **(Binding)**

**Intent.** Assess **civil-time legality** for every site’s assigned `tzid` using the compiled transition cache—i.e., detect **gaps** (non-existent local times) and **folds** (ambiguous local times)—and publish a fingerprint+seed **legality report**.

**Objectives (normative).** 2A.S4 SHALL:

* **Assert eligibility:** Rely on the **2A.S0 gate receipt** for the target `manifest_fingerprint` before any read.
* **Consume sealed inputs only:** Read **`site_timezones`** for the same `(seed, manifest_fingerprint)` and **`tz_timetable_cache`** for the same `manifest_fingerprint`; no other sources are permitted.
* **Check coverage:** Ensure every `tzid` found in `site_timezones` exists in the cache.
* **Evaluate legality deterministically:** From the cache’s per-`tzid` transitions (offset minutes and change instants), derive **gap** and **fold** windows and aggregate per-site coverage via its `tzid`.
* **Report, don’t modify:** Produce **`s4_legality_report`** with summary counts and a PASS/FAIL status; S4 **does not** change any `tzid`.
* **Remain RNG-free & idempotent;** set `generated_utc = S0.receipt.verified_at_utc`.

**In scope.**

* Deterministic derivation of **gap** and **fold** windows from the cache (size = |Δoffset_minutes|).
* Counting/aggregating checked windows per `tzid` and overall; optional small samples in diagnostics.
* Verifying that offsets used in computation are finite integers within layer bounds.

**Out of scope.**

* Zone assignment or overrides (S1/S2).
* Rebuilding the cache or parsing tzdb directly (S3 owns compilation).
* Segment PASS bundle/flag emission (S5).
* Any geometry, raw `site_locations`, or non-sealed assets.

**Interfaces (design relationship).**

* **Upstream:** Consumes S0 receipt (gate), **`site_timezones`** (S2), **`tz_timetable_cache`** (S3), all for the target identity.
* **Downstream:** S5 may incorporate the S4 report into the 2A validation bundle; other consumers may read the report for operational dashboards.

**Completion semantics.** S4 is complete when **`s4_legality_report`** is written under the correct `[seed, fingerprint]` partition, schema-valid, **path↔embed equality** holds, `generated_utc` is deterministic as specified, coverage is complete, and all acceptance validators pass.

---

## 3. Preconditions & sealed inputs **(Binding)**

### 3.1 Preconditions

S4 SHALL begin only when:

* **Gate verified.** A valid **2A.S0 gate receipt** exists and schema-validates for the target `manifest_fingerprint`. S4 relies on this receipt for read permission and sealed-input identity; it does not re-hash upstream bundles.
* **Run identity fixed.** The pair **`(seed, manifest_fingerprint)`** is selected and constant for the run. S4 is seed+fingerprint scoped.
* **Authorities addressable.** The 2A schema pack, Dataset Dictionary, and Artefact Registry entries required below resolve without placeholders (Schema = shape; Dictionary = IDs→paths/partitions/format; Registry = existence/licence/retention).
* **Posture.** S4 is **RNG-free** and deterministic; observational fields (e.g., `generated_utc`) derive from sealed inputs.

### 3.2 Sealed inputs (consumed in S4)

S4 **consumes only** the following inputs. All MUST be resolved **by ID via the Dataset Dictionary** (no literal paths) and be authorised by the Registry.

1. **`site_timezones` (from S2) — partitioned by `[seed, fingerprint]`**
   *Role:* per-site final `tzid` (and provenance fields) to be checked for legality.
   *Catalogue:* `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`.
   *Shape:* `schemas.2A.yaml#/egress/site_timezones` (PK `[merchant_id, legal_country_iso, site_order]`).

2. **`tz_timetable_cache` (from S3) — partitioned by `[fingerprint]`**
   *Role:* authoritative per-`tzid` transition series (UTC change instants, offset minutes) used to derive **gap** and **fold** windows.
   *Catalogue:* `data/layer1/2A/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/`.
   *Shape:* `schemas.2A.yaml#/cache/tz_timetable_cache` (manifest with `tzdb_release_tag`, `tz_index_digest`, `rle_cache_bytes`, etc.).

3. **2A.S0 gate receipt (evidence)**
   *Role:* proves eligibility to read the sealed inputs for the target `manifest_fingerprint`; S4 verifies presence/fingerprint only (no re-hash).

> *Note:* S4 does **not** read raw tzdb, geometry, overrides, or any site-level datasets other than `site_timezones`.

### 3.3 Binding constraints on input use

* **Same-identity constraint.** `site_timezones` **MUST** be read exactly from this run’s `(seed, manifest_fingerprint)` partition; `tz_timetable_cache` **MUST** share the same `manifest_fingerprint`.
* **Dictionary-only resolution.** Inputs **MUST** be resolved by **ID → path/partitions/format** via the Dataset Dictionary; literal/relative paths are **forbidden**.
* **Shape authority.** JSON-Schema anchors are the **sole** shape authority; S4 SHALL NOT assume undeclared columns or relax declared domains.
* **Cache authority.** For per-`tzid` transitions, S4 **SHALL** treat `tz_timetable_cache` as authoritative; S4 SHALL NOT parse tzdb directly.
* **Non-mutation.** S4 SHALL NOT mutate or persist any input datasets; it emits only `s4_legality_report`.

### 3.4 Null/empty allowances

* **Empty `site_timezones`.** Allowed. S4 SHALL emit a report with zero counts (PASS if all validators hold).
* **Cache presence.** `tz_timetable_cache` **MUST** exist for the fingerprint (S3 guarantees non-empty payload via its own validators).
* **No other inputs.** Datasets not enumerated in §3.2 are **out of scope** for S4 and SHALL NOT be read.

---

## 4. Inputs & authority boundaries **(Binding)**

### 4.1 Authority model (normative)

* **Shape authority:** JSON-Schema anchors fix columns/fields, domains, PK/partitions, and strictness
  *(S4 relies on `schemas.2A.yaml#/egress/site_timezones`, `#/cache/tz_timetable_cache`, `#/validation/s4_legality_report`).*
* **Catalogue authority:** The Dataset Dictionary fixes **IDs → canonical paths/partitions/format**. S4 **MUST** resolve inputs by **ID only** (no literal/relative paths).
* **Existence/licensing authority:** The Artefact Registry declares **presence, licence class, retention, lineage**.
* **Precedence on disputes:** **Schema › Dictionary › Registry** (Schema wins for shape; Dictionary wins for paths/partitions; Registry supplies existence/licence).
* **Gate law:** Read permission derives from the **2A.S0 receipt** for the target `manifest_fingerprint` (S4 does **not** re-hash bundles).
* **Identity law:** **Path↔embed equality** applies wherever lineage appears both in path tokens and embedded fields.

### 4.2 Per-input boundaries

1. **`site_timezones`** *(required; S2 egress)*

   * **Shape:** `schemas.2A.yaml#/egress/site_timezones`
   * **Catalogue:** `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` *(partitions `[seed, fingerprint]`)*
   * **Registry:** egress; write-once; final-in-layer
   * **Boundary:** S4 **SHALL** read **exactly** the run’s `(seed, manifest_fingerprint)` partition; columns are used only to obtain the site key and final `tzid`. S4 **SHALL NOT** modify or re-emit this dataset.

2. **`tz_timetable_cache`** *(required; S3 output)*

   * **Shape:** `schemas.2A.yaml#/cache/tz_timetable_cache`
   * **Catalogue:** `data/layer1/2A/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/` *(partition `[fingerprint]`)*
   * **Registry:** cache; lineage `→ tzdb_release`; write-once
   * **Boundary:** S4 **SHALL** treat the cache as **authoritative** for per-`tzid` transition series (UTC instants, offset minutes). S4 **SHALL NOT** parse raw tzdb or rely on any unsealed source.

3. **2A.S0 gate receipt** *(evidence)*

   * **Shape:** `schemas.2A.yaml#/validation/s0_gate_receipt_v1`
   * **Catalogue:** fingerprint-scoped receipt
   * **Boundary:** S4 **SHALL** verify presence and **fingerprint match** only; no re-computation of bundle hashes.

> **Out of scope inputs:** raw tzdb, geometry, overrides, or any site-level dataset other than `site_timezones` are **forbidden** in S4.

### 4.3 Validation responsibilities (S4 scope)

* **Receipt & identity:** S0 receipt exists and matches the target `manifest_fingerprint`.
* **Dictionary resolution:** `site_timezones` and `tz_timetable_cache` resolve by ID with the **exact** partitions required; no literal paths.
* **Partition discipline:** `site_timezones` read strictly at the run’s `(seed, manifest_fingerprint)`; cache at the same `manifest_fingerprint`.
* **Cache authority:** For every `tzid` used by `site_timezones`, S4 **MUST** obtain its transition series from the cache (or fail if absent).
* **Domain minima:** Offsets used in legality computation are integer minutes within layer bounds; timestamps are finite; no NaN/Inf.
* **Non-mutation:** Inputs are read-only; only `s4_legality_report` is emitted.

### 4.4 Prohibitions

S4 **SHALL NOT**:

* read any dataset beyond §4.2;
* use network/implicit paths or parse unsealed tzdb;
* alter `site_timezones` or `tz_timetable_cache`;
* introduce RNG or wall-clock time (observational fields derive from sealed inputs).

---

## 5. Outputs (dataset) & identity **(Binding)**

### 5.1 Primary deliverable — `s4_legality_report` (JSON)

**Role.** Fingerprint+seed **legality summary**: counts of gap/fold windows checked (by using the S3 cache over the S2 `tzid`s), coverage status, and an overall **PASS/FAIL**. Evidence for programme QA and S5.

**Shape (authority).** `schemas.2A.yaml#/validation/s4_legality_report` (**fields-strict**) with at least:

* `manifest_fingerprint : hex64`
* `seed : uint64`
* `generated_utc : rfc3339_micros` *(= S0.receipt.verified_at_utc)*
* `status : "PASS" | "FAIL"`
* `counts : { sites_total:uint64, tzids_total:uint32, gap_windows_total:uint64, fold_windows_total:uint64 }`
* *(optional diagnostics)* `missing_tzids : string[]` (non-empty only on FAIL), `notes : string`

**Catalogue (Dictionary).** Path family (seed + fingerprint):
`data/layer1/2A/legality_report/seed={seed}/manifest_fingerprint={manifest_fingerprint}/s4_legality_report.json`
**Partitions:** `[seed, fingerprint]` · **Format:** JSON. Dictionary governs exact filename/layout.

**Registry (existence/licensing/lineage).** Registered as **validation** evidence; lineage depends on **`site_timezones`** (S2) and **`tz_timetable_cache`** (S3). Write-once/atomic publish posture.

### 5.2 Identity & path law

* **Selection identity:** exactly one pair **`(seed, manifest_fingerprint)`** per publish.
* **Path↔embed equality (binding):** Embedded `manifest_fingerprint` and `seed` in the report **MUST** byte-equal their path tokens.
* **Deterministic timestamp:** `generated_utc` **MUST** equal `S0.receipt.verified_at_utc`.

### 5.3 Write posture & merge discipline

* **Single-writer, write-once per `(seed, fingerprint)`.** Any re-emit to an existing partition **MUST** be **byte-identical**; otherwise the run **MUST ABORT**.
* **Atomic publish.** Stage → fsync → single atomic move into the identity partition.

### 5.4 Format, licensing & retention (by catalogue/registry)

* **Format:** JSON (fields-strict per anchor).
* **Licence/TTL:** Per Dictionary/Registry (e.g., Proprietary-Internal; typical retention 365 days).
* **Consumption note:** S4 emits **evidence** only; the **segment PASS gate** for 2A egress is enforced in S5 (bundle/flag), not by S4.

---

## 6. Dataset shapes & schema anchors **(Binding)**

**Shape authority.** JSON-Schema anchors are the **sole** source of truth for fields, domains, strictness, and identity. S4 binds to:

* **Output:** `schemas.2A.yaml#/validation/s4_legality_report`
* **Inputs:** `schemas.2A.yaml#/egress/site_timezones`, `schemas.2A.yaml#/cache/tz_timetable_cache`

---

### 6.1 Output artefact — `s4_legality_report` (fingerprint+seed report)

* **ID → Schema:** `schemas.2A.yaml#/validation/s4_legality_report` (**fields-strict**; stored as JSON; anchor defines the fields).
* **Minimum fields (binding):**
  `manifest_fingerprint: hex64` · `seed: uint64` · `generated_utc: rfc3339_micros` ·
  `status: enum{"PASS","FAIL"}` · `counts: { sites_total:uint64, tzids_total:uint32, gap_windows_total:uint64, fold_windows_total:uint64 }`
* **Optional diagnostics (non-identity):**
  `missing_tzids: string[]` (present only when non-zero) · `notes: string`
* **Dictionary binding (catalogue authority):**
  Path family `data/layer1/2A/legality_report/seed={seed}/manifest_fingerprint={manifest_fingerprint}/s4_legality_report.json`
  **Partitions:** `[seed, fingerprint]` · **Format:** JSON.
* **Registry posture (existence/licensing/lineage):**
  Class **validation**; lineage **depends on** `site_timezones` (S2) and `tz_timetable_cache` (S3); write-once/atomic publish.

---

### 6.2 Referenced inputs (read-only in S4)

* **`site_timezones` (S2 egress):** `schemas.2A.yaml#/egress/site_timezones`
  **Partitions:** `[seed, fingerprint]` · **Role:** supplies per-site final `tzid` set to be checked.
* **`tz_timetable_cache` (S3 cache):** `schemas.2A.yaml#/cache/tz_timetable_cache`
  **Partitions:** `[fingerprint]` · **Role:** authoritative per-`tzid` transition series (UTC instants, offset minutes).

---

### 6.3 Identity & partition posture (binding)

* **Output partitions:** `[seed, fingerprint]`.
* **Path↔embed equality:** `seed` and `manifest_fingerprint` embedded in the report **MUST** byte-equal their path tokens.
* **No secondary keys:** Report is a single JSON document; no table PK/ordering applies.

---

### 6.4 Binding constraints (shape-level, S4)

* **Strict fields.** The report schema is **fields-strict**; undeclared fields are invalid.
* **Deterministic timestamp.** `generated_utc` **MUST** equal `S0.receipt.verified_at_utc`.
* **Counts domain.** All `counts.*` are **non-negative** integers; `sites_total` equals the number of input rows read; `tzids_total` equals the number of distinct `tzid` values observed in `site_timezones`.
* **Diagnostics discipline.** `missing_tzids` **MUST** be empty/absent on **PASS**; if present, entries **MUST** be valid `iana_tzid` strings.
* **No PII.** Report **MUST NOT** include per-site identifiers or raw rows; only aggregate counts, identity tokens, and optional `tzid` strings in diagnostics.

*Result:* With these anchors and catalogue/registry bindings, S4’s single deliverable `s4_legality_report` is fully specified; inputs are pinned to their authoritative schemas; and the `[seed, fingerprint]` identity/immutability posture matches programme law.

---

## 7. Deterministic behaviour (RNG-free) **(Binding)**

### 7.1 Posture & scope

* S4 is **strictly deterministic** and **RNG-free**.
* Read permission derives from the **2A.S0 receipt** for the target `manifest_fingerprint`.
* Inputs are resolved **only via the Dataset Dictionary**; literal/relative paths are forbidden.
* S4 reads **`site_timezones`** (seed+fingerprint) and **`tz_timetable_cache`** (fingerprint). No other sources are read.
* Observational fields are deterministic: `generated_utc` **SHALL** equal `S0.receipt.verified_at_utc`.

### 7.2 Canonical processing order

1. **Verify gate.** Assert presence & schema validity of the 2A.S0 receipt for the target `manifest_fingerprint`.
2. **Bind inputs.**

   * Select `site_timezones` **exactly** at `[seed, fingerprint]`.
   * Bind `tz_timetable_cache` for the same `manifest_fingerprint`.
3. **Derive working sets.**

   * Compute `sites_total` = row count of `site_timezones`.
   * Compute the set `TZ_USED` = **distinct** `tzid` values present in `site_timezones` (order by ASCII-lex for stability).

### 7.3 Gap & fold window derivation (by `tzid`)

For each `tzid ∈ TZ_USED`, obtain its **ordered** transition series from the cache (UTC change instants with **integral** offset minutes). Let consecutive entries be
`(tᵢ, offsetᵢ)` and `(tᵢ₊₁, offsetᵢ₊₁)` with `tᵢ < tᵢ₊₁`. Define `Δᵢ = offsetᵢ₊₁ − offsetᵢ` (minutes).

* **No window:** `Δᵢ = 0` → no gap/fold.
* **Gap window:** `Δᵢ > 0` → a **non-existent local-time window** of length `Δᵢ` minutes occurs at the transition.
* **Fold window:** `Δᵢ < 0` → an **ambiguous local-time window** of length `|Δᵢ|` minutes occurs starting at the transition.

S4 **SHALL**:

* treat the cache as **authoritative** (no re-parsing of tzdb);
* require transition instants to be strictly increasing and offsets within layer bounds (S3 guarantees; S4 may assert);
* count windows **per `tzid`** only (windows are **not** multiplied by the number of sites using that `tzid`).

### 7.4 Aggregation & report construction

* Compute:
  • `tzids_total` = `|TZ_USED|`
  • `gap_windows_total` = Σ over `tzid ∈ TZ_USED` of its gap windows (per §7.3)
  • `fold_windows_total` = Σ over `tzid ∈ TZ_USED` of its fold windows (per §7.3)
* **Coverage check:** if any `tzid ∈ TZ_USED` is **absent** from the cache index, add it to `missing_tzids` and **FAIL**.
* Set `status = "PASS"` iff all validators in §9 pass (including coverage) and counts computed without error.
* Set `generated_utc = S0.receipt.verified_at_utc`.
* Populate the report fields exactly as fixed by the `s4_legality_report` anchor (fields-strict).

### 7.5 Emission & identity discipline

* Emit **`s4_legality_report`** to
  `data/layer1/2A/legality_report/seed={seed}/manifest_fingerprint={manifest_fingerprint}/s4_legality_report.json`.
* **Path↔embed equality:** embedded `seed` and `manifest_fingerprint` **MUST** byte-equal path tokens.
* **Write-once:** re-emitting to an existing `(seed, fingerprint)` partition **MUST** be byte-identical; otherwise **ABORT**.
* **Atomic publish:** stage → fsync → single atomic move into the partition.

### 7.6 Prohibitions (non-behaviours)

S4 **SHALL NOT**:

* parse raw tzdb or read geometry/overrides/other site datasets;
* alter `site_timezones` or `tz_timetable_cache`;
* introduce RNG or wall-clock time;
* include per-site identifiers or raw rows in the report (aggregate counts only, plus optional `tzid` strings in diagnostics).

### 7.7 Idempotency

Given the same **S0 receipt**, the same `site_timezones` partition, and the same `tz_timetable_cache`, S4 **SHALL** produce **byte-identical** `s4_legality_report` (including `generated_utc`, counts, and diagnostics).

---

## 8. Identity, partitions, ordering & merge discipline **(Binding)**

### 8.1 Identity tokens

* **Selection identity:** exactly one pair **`(seed, manifest_fingerprint)`** per publish of `s4_legality_report`.
* **No new tokens:** `parameter_hash` is not a partition for S4.
* **Path↔embed equality (binding):** the embedded `seed` and `manifest_fingerprint` in the report **MUST** byte-equal the respective path tokens.

### 8.2 Partitions & path family

* **Dataset:** `s4_legality_report` →
  `data/layer1/2A/legality_report/seed={seed}/manifest_fingerprint={manifest_fingerprint}/s4_legality_report.json`.
* **Partitions (binding):** **`[seed, fingerprint]` only**; no other partitions are permitted.
* **Catalogue authority:** exact filename/layout/format are governed by the Dataset Dictionary.

### 8.3 Keys, uniqueness & coverage

* **Single document per identity:** one JSON report per `(seed, manifest_fingerprint)` identity.
* **Coverage coupling:** the identity selected **MUST** correspond to the same `(seed, fingerprint)` used to read `site_timezones` and the same `fingerprint` used to read `tz_timetable_cache`.

### 8.4 Writer order (discipline)

* **Not applicable to JSON report content.** There is no row-level writer sort. Any internal field ordering in the JSON is non-authoritative; consumers **MUST NOT** infer semantics from member order.

### 8.5 Merge & immutability

* **Write-once per `(seed, fingerprint)`.** If the target partition already contains a report, any re-emit **MUST** be **byte-identical**; otherwise the run **MUST ABORT**.
* **Atomic publish.** Stage → fsync → single **atomic move** into the identity partition.
* **No in-place edits/tombstones.** Updates occur only by producing a new identity (i.e., a different `seed` or a new `manifest_fingerprint` upstream).

### 8.6 Concurrency & conflict detection

* **Single-writer per identity.** Concurrent writes targeting the same `(seed, fingerprint)` are not permitted.
* **Conflict definition:** the presence of any artefact under the target partition constitutes a conflict; S4 **MUST** abort rather than overwrite.

### 8.7 Discovery & selection (downstream contract)

* Downstream consumers **MUST** select the report by **`(seed, manifest_fingerprint)`** via the **Dataset Dictionary**, verify schema validity, and enforce **path↔embed equality** before use.

### 8.8 Retention, licensing & relocation

* **Retention/licence:** governed by Dictionary/Registry (e.g., Proprietary-Internal; typical TTL 365 days).
* **Relocation:** moving files that preserves the Dictionary path family and partitions is non-breaking; any change that alters partition keys or path tokens is **breaking** and out of scope for S4.

*Effect:* These rules make `s4_legality_report` uniquely addressable by `(seed, manifest_fingerprint)`, immutable once published, and unambiguous to consume—**Schema** as shape authority, **Dictionary** as catalogue authority, **Registry** for existence/licensing.

---

## 9. Acceptance criteria (validators) **(Binding)**

**PASS definition.** A run of 2A.S4 is **ACCEPTED** iff **all** mandatory validators below pass. Any **Abort** failure causes the run to **FAIL** and no report from §5 may be published. **Warn** does not block emission.

### 9.1 Gate & input resolution (mandatory)

**V-01 — S0 receipt present (Abort).** A valid 2A.S0 gate receipt exists and schema-validates for the target `manifest_fingerprint`.
**V-02 — Dictionary resolution (Abort).** Inputs resolve by **ID** via the Dataset Dictionary (no literal paths):
`site_timezones` `[seed,fingerprint]` and `tz_timetable_cache` `[fingerprint]`.
**V-03 — Partition selection (Abort).** `site_timezones` is read **only** from the run’s `(seed, manifest_fingerprint)` partition; the cache is read at the **same `manifest_fingerprint`**.

### 9.2 Cache readiness (mandatory)

**V-04 — Cache manifest valid (Abort).** The cache manifest validates against `#/cache/tz_timetable_cache`.
**V-05 — Cache path↔embed equality (Abort).** Manifest `manifest_fingerprint` equals the cache partition token.
**V-06 — Cache non-empty (Abort).** `rle_cache_bytes > 0` and all files referenced by the manifest exist.

### 9.3 Output report shape, identity & determinism (mandatory)

**V-07 — Report schema validity (Abort).** The emitted report validates against `#/validation/s4_legality_report` (**fields-strict**).
**V-08 — Report path↔embed equality (Abort).** Embedded `seed` and `manifest_fingerprint` byte-equal the output path tokens.
**V-09 — Deterministic timestamp (Abort).** `generated_utc == S0.receipt.verified_at_utc`.

### 9.4 Coverage & legality computation (mandatory)

**V-10 — Coverage: tzids in use present in cache (Abort).** Every `tzid` that appears in `site_timezones` exists in the cache index; otherwise add to `missing_tzids` and **FAIL**.
**V-11 — Counts sanity (Abort).**
  • `sites_total` equals the number of rows read from `site_timezones`.
  • `tzids_total` equals the number of **distinct** `tzid` values in `site_timezones`.
  • `gap_windows_total, fold_windows_total` are **non-negative** integers.
**V-12 — Window derivation coherence (Abort).** For each `tzid` used, fold/gap window counts are computed from the cache as:
  – gap when `Δoffset_minutes > 0`; fold when `Δoffset_minutes < 0`; none when `Δ = 0`; window size = `|Δ|` minutes.
**V-13 — Numeric domain (Abort).** All offsets used are **integral minutes** within layer bounds (e.g., −900…+900); no NaN/Inf instants or counts.

### 9.5 Merge & immutability (mandatory)

**V-14 — Write-once partition (Abort).** If the target `(seed, fingerprint)` partition already exists, newly written bytes must be **byte-identical**; otherwise **ABORT**.

### 9.6 Outcome semantics

* **PASS:** V-01…V-14 pass.
* **FAIL:** Any **Abort** validator fails.
* **WARN:** (none defined for S4).

### 9.7 (For §10) Validator → error-code mapping (normative)

| Validator                          | Error code(s)                                                                          |
|------------------------------------|----------------------------------------------------------------------------------------|
| V-01 S0 receipt present            | **2A-S4-001 MISSING_S0_RECEIPT**                                                       |
| V-02 Dictionary resolution         | **2A-S4-010 INPUT_RESOLUTION_FAILED**                                                  |
| V-03 Partition selection           | **2A-S4-011 WRONG_PARTITION_SELECTED**                                                 |
| V-04 Cache manifest valid          | **2A-S4-020 CACHE_MANIFEST_INVALID**                                                   |
| V-05 Cache path↔embed equality     | **2A-S4-021 CACHE_PATH_EMBED_MISMATCH**                                                |
| V-06 Cache non-empty               | **2A-S4-022 CACHE_BYTES_MISSING** · **2A-S4-023 CACHE_FILE_MISSING**                   |
| V-07 Report schema validity        | **2A-S4-030 REPORT_SCHEMA_INVALID**                                                    |
| V-08 Report path↔embed equality    | **2A-S4-040 PATH_EMBED_MISMATCH**                                                      |
| V-09 Deterministic `generated_utc` | **2A-S4-042 GENERATED_UTC_NONDETERMINISTIC**                                           |
| V-10 Coverage (tzids)              | **2A-S4-024 TZID_MISSING_IN_CACHE** |
| V-11 Counts sanity                 | **2A-S4-060 COUNT_COMPUTATION_ERROR**                                                  |
| V-12 Window derivation coherence   | **2A-S4-061 WINDOW_DERIVATION_INVALID**                                                |
| V-13 Numeric domain                | **2A-S4-050 OFFSET_NONFINITE_OR_OUT_OF_RANGE**                                         |
| V-14 Write-once partition          | **2A-S4-041 IMMUTABLE_PARTITION_OVERWRITE**                                            |

*Authorities:* Output report shape by the S4 anchor; catalogue paths/partitions by the 2A Dictionary; existence/licensing/lineage by the 2A Registry; cache content authority by `tz_timetable_cache`; gate evidence by the S0 receipt.

---

## 10. Failure modes & canonical error codes **(Binding)**

**Code format.** `2A-S4-XXX NAME` (stable identifiers).
**Effect classes.** `Abort` = run MUST fail and emit nothing; `Warn` = non-blocking, MUST be surfaced in the run-report.
**Required context on raise.** Include: `manifest_fingerprint`, `seed`, and—where relevant—`dataset_id`, `catalog_path`, `tzid`, and brief location (e.g., counter names).

### 10.1 Gate & input resolution

* **2A-S4-001 MISSING_S0_RECEIPT (Abort)** — No valid 2A.S0 receipt for the target `(seed, fingerprint)`.
  *Remediation:* publish/repair S0; rerun S4.
* **2A-S4-010 INPUT_RESOLUTION_FAILED (Abort)** — `site_timezones` or `tz_timetable_cache` failed **Dictionary** resolution or Registry authorisation.
  *Remediation:* fix Dictionary/Registry entries or IDs; rerun.
* **2A-S4-011 WRONG_PARTITION_SELECTED (Abort)** — `site_timezones` not read **exactly** from `(seed, manifest_fingerprint)` or cache not from the same `manifest_fingerprint`.
  *Remediation:* select the exact partitions; rerun.

### 10.2 Cache readiness

* **2A-S4-020 CACHE_MANIFEST_INVALID (Abort)** — Cache manifest violates `#/cache/tz_timetable_cache`.
  *Remediation:* emit a schema-valid manifest only.
* **2A-S4-021 CACHE_PATH_EMBED_MISMATCH (Abort)** — Cache manifest `manifest_fingerprint` ≠ cache partition token.
  *Remediation:* correct embedded value or path; rerun.
* **2A-S4-022 CACHE_BYTES_MISSING (Abort)** — `rle_cache_bytes ≤ 0`.
  *Remediation:* ensure cache payloads are emitted and accounted for.
* **2A-S4-023 CACHE_FILE_MISSING (Abort)** — A cache file referenced by the manifest does not exist.
  *Remediation:* publish all referenced files atomically; rerun.

### 10.3 Coverage & legality computation

* **2A-S4-024 TZID_MISSING_IN_CACHE (Abort)** — One or more `tzid` observed in `site_timezones` are absent from the cache index.
  *Remediation:* fix S3 coverage or inputs; rerun S3/S4.
* **2A-S4-050 OFFSET_NONFINITE_OR_OUT_OF_RANGE (Abort)** — Non-finite or out-of-bounds offset minutes encountered during window derivation.
  *Remediation:* verify cache integrity (S3) and layer bounds; rerun.
* **2A-S4-060 COUNT_COMPUTATION_ERROR (Abort)** — Inconsistent totals (`sites_total`, `tzids_total`, `gap_windows_total`, `fold_windows_total`) or negative counts.
  *Remediation:* correct aggregation logic; rerun.
* **2A-S4-061 WINDOW_DERIVATION_INVALID (Abort)** — Gap/fold rule contradicted (e.g., window derived when `Δoffset_minutes = 0`, or sign handling wrong).
  *Remediation:* enforce: gap iff `Δ>0`, fold iff `Δ<0`, none iff `Δ=0`; window size `|Δ|`.

### 10.4 Output report, identity & merge

* **2A-S4-030 REPORT_SCHEMA_INVALID (Abort)** — `s4_legality_report` violates `#/validation/s4_legality_report`.
  *Remediation:* emit a schema-valid report only.
* **2A-S4-040 PATH_EMBED_MISMATCH (Abort)** — Report `seed`/`manifest_fingerprint` ≠ path tokens.
  *Remediation:* correct embedded identity or path; rerun.
* **2A-S4-041 IMMUTABLE_PARTITION_OVERWRITE (Abort)** — Attempt to write non-identical bytes into an existing `(seed, fingerprint)` partition.
  *Remediation:* either reproduce byte-identical output or target a new identity.
* **2A-S4-042 GENERATED_UTC_NONDETERMINISTIC (Abort)** — `generated_utc` ≠ `S0.receipt.verified_at_utc`.
  *Remediation:* set timestamp deterministically; rerun.

### 10.5 Authority conflict (resolution rule)

* **2A-S4-080 AUTHORITY_CONFLICT (Abort)** — Irreconcilable disagreement among **Schema, Dictionary, Registry** for the same asset after applying precedence (**Schema › Dictionary › Registry**).
  *Remediation:* correct the lower-precedence authority (or the schema, if wrong); rerun.

> The validator→code mapping in §9.7 MUST reflect these identifiers exactly. New failure conditions introduced by future revisions MUST allocate **new codes** (append-only) and MUST NOT repurpose existing identifiers.

---

## 11. Observability & run-report **(Binding)**

### 11.1 Scope & posture

* **Purpose.** Record auditable evidence of S4’s gate verification, cache usage, legality computations (gaps/folds), and publish.
* **Not identity-bearing.** The run-report does **not** affect dataset identity or gates.
* **One per run.** Exactly one report per attempted S4 run (success or failure).

---

### 11.2 Run-report artefact (normative content)

A single UTF-8 JSON object **SHALL** be written with at least the fields below. Missing required fields are **Warn** (programme policy may escalate).

**Header:**

* `segment : "2A"`
* `state : "S4"`
* `status : "pass" | "fail"`
* `manifest_fingerprint : hex64`
* `seed : uint64`
* `started_utc, finished_utc : rfc3339_micros`
* `durations : { wall_ms : uint64 }`

**Gate & inputs:**

* `s0.receipt_path : string`
* `s0.verified_at_utc : rfc3339_micros`
* `inputs.site_timezones.path : string` — Dictionary path for selected `(seed,fingerprint)`
* `inputs.cache.path : string` — Dictionary path for `tz_timetable_cache/fingerprint={manifest_fingerprint}/`
* `inputs.cache.tzdb_release_tag : string`
* `inputs.cache.tz_index_digest : hex64`
* `inputs.cache.rle_cache_bytes : uint64`

**Legality summary (derived from cache):**

* `counts.sites_total : uint64` — rows read from `site_timezones`
* `counts.tzids_total : uint32` — distinct tzids used
* `counts.gap_windows_total : uint64`
* `counts.fold_windows_total : uint64`
* `coverage.missing_tzids_count : uint32` — EXPECT 0 on PASS
* `coverage.missing_tzids_sample : string[]` — optional, short non-exhaustive sample on FAIL

**Output & identity:**

* `output.path : string` — Dictionary path to the report
* `output.generated_utc : rfc3339_micros` — **MUST** equal `s0.verified_at_utc`
* `catalogue.writer_order_ok : bool` — always `true`/omitted (advisory; JSON report has no row order)

**Diagnostics:**

* `warnings : array<error_code>` — any non-blocking codes
* `errors : array<{code, message, context}>` — on failure, canonical codes with brief context

**Optional (advisory, non-binding):**

* `determinism.partition_hash : hex64` — directory-level hash of the emitted `(seed,fingerprint)` partition.

---

### 11.3 Structured logs (minimum event kinds)

S4 **SHALL** emit machine-parseable records correlating to the report. Minimum events:

* **`GATE`** — start/end + result of S0 receipt verification; include `manifest_fingerprint`.
* **`INPUTS`** — resolved IDs/paths for `site_timezones` and `tz_timetable_cache`; echo cache `tzdb_release_tag`.
* **`CHECK`** — `sites_total`, `tzids_total`, `gap_windows_total`, `fold_windows_total`, `missing_tzids_count`.
* **`VALIDATION`** — each validator outcome `{id, result, code?}` for §9.
* **`EMIT`** — successful publication of the report with Dictionary path and `generated_utc`.

Every record **SHALL** include: `timestamp_utc (rfc3339_micros)`, `segment`, `state`, `seed`, `manifest_fingerprint`, and `severity (INFO|WARN|ERROR)`.

---

### 11.4 Discoverability, retention & redaction

* **Discoverability.** The run-report path **MUST** be surfaced in CI/job metadata alongside the output Dictionary path.
* **Retention.** Report TTL is governed by programme policy; changing TTL **MUST NOT** alter dataset identity or partitions.
* **Redaction.** Reports/logs **MUST NOT** include per-site identifiers or raw rows; only aggregate counts, IDs, paths, digests, timestamps, and error codes are permitted.

---

## 12. Performance & scalability **(Informative)**

### 12.1 Workload shape

* **Reads:** one `site_timezones` partition for the selected `(seed, manifest_fingerprint)` and the `tz_timetable_cache` for the same `manifest_fingerprint`.
* **Compute:** build `TZ_USED` (distinct tzids in `site_timezones`) → for each tzid, scan its transition series from the cache and tally **gap**/**fold** windows (based on `Δoffset_minutes`).
* **Writes:** a single JSON `s4_legality_report` (small, fields-strict).

### 12.2 Asymptotics (U = |TZ_USED|, T_U = total transitions across tzids in use)

* **Time:** ~ **O(|site_timezones| + T_U)** (distinct aggregation + per-tzid linear scans).
* **Space:** **O(1)** w.r.t. input size for streaming, plus **O(max transitions for any one tzid)** working set; negligible for aggregates/counters.

### 12.3 Memory model

* Stream `site_timezones` to accumulate `sites_total` and `TZ_USED` (use a hash/set of tzids).
* For each tzid, stream its ordered transitions from the cache; no need to materialise all tzids simultaneously.
* Report object is tiny; no row buffers are persisted.

### 12.4 I/O profile

* **Input:** one sequential pass over `site_timezones`; one sequential pass over each used tzid’s transition list in the cache.
* **Output:** single JSON file; file order is non-authoritative.

### 12.5 Parallelism & concurrency

* **Across tzids:** embarrassingly parallel (independent window counts per tzid). Reduce into final totals in a deterministic order.
* **Across identities:** different `(seed, manifest_fingerprint)` pairs run independently.
* **Publish:** still **single-writer, write-once** for the `(seed, fingerprint)` partition.

### 12.6 Hot spots & guardrails

* **Skewed tzid usage:** a single tzid with many historical transitions can dominate runtime; ensure its transition list is streamed once.
* **Large seeds:** high `sites_total` increases set-build time for `TZ_USED`; deduplicate tzids on the fly to cap memory.
* **Numeric bounds:** enforce integral offset minutes within layer bounds (e.g., −900…+900) to avoid overflow/invalid windows.
* **Cache integrity:** treat cache manifest and referenced files as authoritative; avoid touching raw tzdb.

### 12.7 Determinism considerations

* Derive `generated_utc` from S0’s receipt; no wall clock.
* Use a stable reduction order (e.g., tzid ASCII-lex) when combining partial counts so re-runs reproduce identical bytes.
* Avoid floating-point arithmetic in identity/bounds checks (offsets are integer minutes).

### 12.8 Scalability knobs (programme-level)

* **Shard degree by tzid** (parallel window counting).
* **Set implementation** for `TZ_USED` (e.g., compact hash set) and optional pre-cardinality hints.
* **Row-group/scan settings** for `site_timezones` to keep I/O sequential.
* **Advisory thresholds** for `missing_tzids_count` (should be 0) and unusually high gap/fold totals (Warn-only telemetry).

### 12.9 Re-run & churn costs

* Re-running with unchanged `site_timezones` and cache is **idempotent** (byte-identical report).
* Changing `site_timezones` (new seed run) scales with rows; changing the fingerprint (new cache/inputs) requires a fresh S4 run for each seed that targets it.

### 12.10 Typical envelopes (order-of-magnitude)

* **`TZ_USED` cardinality:** tens–hundreds typical; occasionally low thousands.
* **Transitions per used tzid:** dozens–thousands (historical depth dependent).
* **Report size:** KBs; compute time dominated by scanning `T\_U`.

---

## 13. Change control & compatibility **(Binding)**

### 13.1 Versioning & document status

* **SemVer** applies to this state spec (`MAJOR.MINOR.PATCH`).

  * **PATCH:** editorial clarifications that **do not** change behaviour, shapes, validators, or outcomes.
  * **MINOR:** strictly backward-compatible additions that **do not** alter identity, partitions, legality definitions, or PASS/FAIL results.
  * **MAJOR:** any change that can affect identity, partitions, required fields, legality definitions (gap/fold), or validator outcomes.

### 13.2 Stable compatibility surfaces (must remain invariant)

1. **Identity:** output is selected by **`(seed, manifest_fingerprint)`**; partitions are **`[seed, fingerprint]`** only; **path↔embed equality** MUST hold.
2. **Output surface:** dataset **`s4_legality_report`** exists with its **schema anchor/ID** unchanged; **fields-strict**.
3. **Determinism:** `generated_utc == S0.receipt.verified_at_utc`; S4 is RNG-free.
4. **Inputs & authority:** inputs limited to **`site_timezones`** and **`tz_timetable_cache`** (authoritative for transitions).
5. **Legality definitions:**

   * **Gap** iff `Δoffset_minutes > 0`; **Fold** iff `Δoffset_minutes < 0`; **None** iff `Δ == 0`; window size `|Δ|` minutes.
6. **Coverage law:** every `tzid` used in `site_timezones` **must** be present in the cache index (superset allowed).
7. **Catalogue posture:** **Dictionary** is authority for IDs→paths/partitions/format; **Registry** for existence/licence/retention/lineage; **Schema** is sole shape authority.
8. **Validator & code semantics:** §9 validators and §10 error codes keep their meanings.

### 13.3 Backward-compatible changes (**MINOR** or **PATCH**)

Permitted when they **do not** change identity or acceptance:

* Add **Warn-only** diagnostics/validators (e.g., advisory thresholds on unusually high gap/fold totals).
* Add **non-identity, optional** fields in the report (e.g., `gap_sample[]`, `fold_sample[]`, brief notes) that consumers MAY ignore.
* Extend run-report / logs with extra non-identity fields.
* Tighten textual descriptions or numeric bounds already met by current outputs.
* Expand accepted cache metadata (echo fields from S3 manifest) without making them required.

> Note: The report is **fields-strict**. Adding **required** fields or retyping existing ones is **not** backward-compatible (see 13.4).

### 13.4 Breaking changes (**MAJOR**)

Require a MAJOR bump and downstream coordination:

* Changing **partitions** (adding/removing/renaming keys) or altering **path↔embed** rules.
* Renaming/removing the dataset/anchor **`s4_legality_report`**, or relocating it to a different path family.
* Modifying **legality definitions** (gap/fold sign rule, window sizing) or the **coverage law**.
* Turning a **Warn** into **Abort**, or changing meanings of §10 error codes.
* Adding new **required** report fields or retyping existing ones; removing existing fields.
* Admitting **new inputs** beyond `site_timezones`/`tz_timetable_cache`, or introducing wall-clock/RNG elements.
* Any validator change that flips previously PASSing runs to FAIL under unchanged inputs.

### 13.5 Deprecation policy

* **Announce → grace → remove.** Mark a feature **Deprecated** at least **one MINOR** before removal with an **effective date**.
* **No repurposing.** Deprecated fields/codes/IDs are never reused; removal only at **MAJOR**.
* **Alias window.** When renaming anchors/IDs, provide alias anchors for at least one MINOR; both validate to identical shapes during the window.

### 13.6 Co-existence & migration

* Use a **dual-anchor window** for material changes (e.g., `#/validation/s4_legality_report_v2`) while the old anchor remains valid; Dictionary may list both; identity remains `(seed,fingerprint)`.
* **Re-fingerprinting is upstream.** Changes to inputs that alter `manifest_fingerprint` (via S0) naturally select a new partition; S4 re-runs per seed for that fingerprint.
* **Idempotent re-runs.** With unchanged inputs for the same identity, S4 reproduces bytes exactly.

### 13.7 Reserved extension points

* Current report anchor does **not** admit arbitrary extension fields.
* A future MINOR **may** introduce an `extensions` object (ignored by consumers) **iff** the anchor is updated concurrently to allow it; otherwise any new field is **MAJOR**.

### 13.8 External dependency evolution

* **Cache format evolution (from S3).** If S3 adds non-identity manifest fields or shard layouts, S4 may MINOR-accept them provided S3’s identity/digest law is unchanged.
* **Transition domain drift.** If a new `tz_world` release changes `tzid` names upstream, re-fingerprinting via S0/S3 handles it; S4’s coverage law stands.

### 13.9 Governance & change process

Every change SHALL include: (i) version bump rationale, (ii) compatibility impact (Patch/Minor/Major), (iii) updated anchors/Dictionary/Registry stanzas (if any), (iv) validator/error-code diffs, and (v) migration notes.
Frozen specs SHALL record an **Effective date**; downstream pipelines target frozen or explicitly authorised alpha versions.

### 13.10 Inter-state coupling

* **Upstream:** depends only on S0 receipt, S2 `site_timezones`, and S3 `tz_timetable_cache`; no site-row data beyond the `tzid`.
* **Downstream:** S5 may incorporate `s4_legality_report` into the 2A validation bundle. Any S4 change that forces downstream to reinterpret identity, partitions, or legality definitions is **breaking**.

---

## Appendix A — Normative cross-references *(Informative)*

> Pointers only. **Schema = shape authority**; **Dictionary = IDs → paths/partitions/format**; **Registry = existence/licensing/retention/lineage**. S4 reads only the inputs listed; all IDs resolve via the Dictionary.

### A1. Layer-1 governance (global rails)

* **Identity & Path Law** — path↔embed equality; partition keys are authoritative.
* **Gate Law** — “No PASS → No Read”; S4 relies on the 2A.S0 receipt (no bundle re-hash).
* **Fingerprint Law** — canonical sealed-manifest → `manifest_fingerprint` (fixed upstream in S0).
* **Numeric policy** — layer-wide numeric/encoding rules (integral minute offsets, RFC-3339 timestamps).

### A2. Upstream receipt & inputs used by S4

* **2A.S0 gate receipt** — `schemas.2A.yaml#/validation/s0_gate_receipt_v1` (fingerprint-scoped).
* **Final per-site tz** — `site_timezones`: `schemas.2A.yaml#/egress/site_timezones` (partitions `[seed,fingerprint]`).
* **Transition cache** — `tz_timetable_cache`: `schemas.2A.yaml#/cache/tz_timetable_cache` (partition `[fingerprint]`; authoritative per-`tzid` transitions).

### A3. S4 output surface

* **Legality report** — `s4_legality_report`: `schemas.2A.yaml#/validation/s4_legality_report` (fields-strict; includes `manifest_fingerprint`, `seed`, `generated_utc`, `status`, and counts).
* **Catalogue path family** — `data/layer1/2A/legality_report/seed={seed}/manifest_fingerprint={manifest_fingerprint}/s4_legality_report.json` (partitions `[seed,fingerprint]`).

### A4. Dataset Dictionary (catalogue authority)

* **Inputs:**
  • `site_timezones` → path family with `[seed,fingerprint]`, Parquet, writer order `[merchant_id, legal_country_iso, site_order]`.
  • `tz_timetable_cache` → fingerprint-scoped path family, manifest + cache files.
* **Output:**
  • `s4_legality_report` → fingerprint+seed JSON report at the path family above.
* **Evidence:**
  • 2A.S0 receipt (fingerprint-scoped).

### A5. Artefact Registry (existence/licensing/lineage)

* **`site_timezones`** — egress; write-once; final-in-layer.
* **`tz_timetable_cache`** — cache; lineage `→ tzdb_release`; write-once.
* **`s4_legality_report`** — validation evidence; lineage depends on `site_timezones` (S2) and `tz_timetable_cache` (S3); write-once/atomic publish.

### A6. Segment-level context

* **State flow:** S0 (gate) → S1 (geometry) → S2 (overrides) → S3 (compile cache) → **S4 (legality report)** → S5 (2A validation bundle/flag).
* **Selection & identity:** consumers select S4 by **`(seed, manifest_fingerprint)`** via the Dictionary and verify **schema + path↔embed equality** before use.

---
