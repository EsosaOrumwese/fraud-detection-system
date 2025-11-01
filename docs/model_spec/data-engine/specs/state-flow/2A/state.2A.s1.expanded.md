# State 2A.S1 — Provisional time-zone lookup

## 1. Document metadata & status **(Binding)**

**Title:** Layer-1 · Segment 2A · State-1 — Provisional time-zone lookup
**Short name:** 2A.S1 “Provisional TZ”
**Layer/Segment/State:** L1 / 2A (Civil Time) / S1
**Doc ID:** `layer1/2A/state-1`
**Version (semver):** `v1.0.0-alpha` *(advance per change control)*
**Status:** `draft | alpha | frozen` *(normative at ≥ `alpha`; semantics locked at `frozen`)*
**Owners:** Design Authority (DA): ‹name› • Review Authority (RA): ‹name›
**Effective date:** ‹YYYY-MM-DD›
**Canonical location:** ‹repo path to this spec file›

**Normative cross-references (pointers only):**

* **2A.S0 Gate & Sealed Inputs:** receipt and sealed manifest for the target `manifest_fingerprint`.
* **Schema anchors (this segment):** `schemas.2A.yaml#/plan/s1_tz_lookup` (output), `#/policy/tz_nudge_v1` (policy), `#/validation/s0_gate_receipt_v1` (receipt reference).
* **Upstream egress:** `schemas.1B.yaml#/egress/site_locations`.
* **Ingress polygons:** `schemas.ingress.layer1.yaml#/tz_world_2025a` (or current release).
* **Layer-1 governance:** Identity & Path Law (path↔embed equality), Gate Law (“No PASS → No Read”), Numeric Policy, Hashing/Fingerprint Law.

**Conformance & interpretation:**

* Sections marked **Binding** are normative; **Informative** sections do not create obligations.
* Keywords **MUST/SHALL/SHOULD/MAY** are as defined in RFC 2119/8174.
* This is a **design specification**: it defines required behaviours, identities, inputs/outputs, and inter-state contracts; it does **not** prescribe implementations or pseudocode.

**Change log (summary):**

* `v1.0.0-alpha` — Initial specification for 2A.S1 (Provisional TZ lookup). Subsequent edits follow §13 Change Control.

---

## 2. Purpose & scope **(Binding)**

**Intent.** Produce a per-site, **geometry-only** provisional time zone by mapping each site’s `(lat, lon)` to an IANA **`tzid`** using the sealed `tz_world` polygons. Where a point lies on a border or is otherwise ambiguous, apply the sealed **ε-nudge policy** and **record** the nudged coordinates.

**Objectives (normative).** 2A.S1 SHALL:

* **Assert eligibility:** Rely on the 2A.S0 **gate receipt** for the target `manifest_fingerprint` before referencing any 1B egress.
* **Resolve sealed inputs:** Use the `tz_world` release and the `tz_nudge` policy **as sealed in S0**; no other sources are permitted.
* **Assign exactly one zone per site:** For every row of `site_locations` at the same `[seed, fingerprint]`, produce exactly one `tzid_provisional`.
* **Tie-break deterministically:** When geometric membership is ambiguous, apply the ε-nudge **as defined by policy**; if applied, persist `nudge_lat_deg`/`nudge_lon_deg`.
* **Emit the plan table:** Write **`s1_tz_lookup`** under `[seed, fingerprint]`, obeying identity/path law and schema anchors.
* **Remain RNG-free and idempotent.**

**In scope.**

* Point-in-polygon membership against `tz_world`.
* Deterministic tie-break using the sealed ε-nudge policy and recording of any nudge applied.
* Row-coverage discipline: **bijective projection** from `site_locations` rows (same `[seed, fingerprint]`) to `s1_tz_lookup` rows.

**Out of scope.**

* **Policy overrides** (applied in S2).
* **Timetable/cache construction** and **DST legality** checks (S3/S4).
* Any re-hashing or restatement of S0 gate logic; S1 consumes S0’s receipt **by reference**.
* Implementation choices (indexing strategy, geometry engine specifics).

**Interfaces (design relationship).**

* **Upstream:** 2A.S0 receipt (gate), `site_locations` (1B egress), `tz_world` polygons, `tz_nudge` policy — all for the same `manifest_fingerprint`.
* **Downstream:** 2A.S2 consumes `s1_tz_lookup` and may replace `tzid_provisional` where an authorised override applies.

**Completion semantics.** S1 is complete when `s1_tz_lookup` is written under the correct `[seed, fingerprint]` partition, schema-valid, path↔embed equality holds, and every input site has exactly one corresponding provisional assignment.

---

## 3. Preconditions & sealed inputs **(Binding)**

### 3.1 Preconditions

2A.S1 SHALL start only when:

* **S0 gate is verified.** A valid **2A.S0 gate receipt** exists for the target `manifest_fingerprint`, and it schema-validates. *(S1 relies on this receipt for read permission; it does not re-hash upstream bundles.)*
* **Run context is fixed.** The pair **`(seed, manifest_fingerprint)`** for this run is selected and constant throughout S1.
* **Authorities are addressable.** The 2A schema pack, Dataset Dictionary, and Artefact Registries that enumerate the inputs below are available and free of placeholders for assets in scope.
* **RNG posture.** S1 is **RNG-free** and deterministic.

### 3.2 Inputs (consumed from the S0-sealed manifest)

S1 **consumes only** the following inputs, all of which MUST resolve via the Dataset Dictionary and be authorised by the Artefact Registry. Every input MUST correspond to the same **`manifest_fingerprint`** as the S0 receipt (where applicable).

1. **2A.S0 gate receipt (evidence)**
   *Role:* proves eligibility to read sealed inputs for this `manifest_fingerprint`.
   *Use in S1:* referenced for verification only; not joined to rows.

2. **`site_locations` (1B egress)** — **partitioned by `[seed, fingerprint]`**
   *Required identity:* the **same** `seed` and `manifest_fingerprint` as this S1 run.
   *Required columns (by anchor):* the per-site identity and coordinate fields used by 2A (e.g., `merchant_id`, `legal_country_iso`, `site_order`, latitude/longitude per the 1B anchor).
   *Use in S1:* provides one input row per site to be assigned a provisional `tzid`.

3. **`tz_world` polygons (ingress release sealed in S0)**
   *Required invariants:* CRS **WGS84**; non-empty geometry set; valid `tzid` domain (per ingress anchor).
   *Use in S1:* point-in-polygon membership to derive `tzid_provisional`.

4. **`tz_nudge` policy (sealed in S0)**
   *Required invariants:* positive ε (strictly > 0) and documented units.
   *Use in S1:* deterministic tie-break when a site lies on or ambiguously near a zone boundary; any applied nudge MUST be recorded in output.

> *Note:* The **tzdb release** and **override list** sealed by S0 are **not consumed** in S1. Overrides are applied in S2; tzdb is used in later states.

### 3.3 Binding constraints on input use

* **Same-fingerprint constraint.** All fingerprinted inputs S1 reads (e.g., `site_locations`) **MUST** match the S0 `manifest_fingerprint`.
* **Partition discipline.** For `site_locations`, the selected partition **MUST** be exactly the run’s `(seed, manifest_fingerprint)`; reading across seeds or fingerprints is **forbidden**.
* **Dictionary-only resolution.** Inputs **MUST** be resolved by **ID → path/partitions/format** via the Dataset Dictionary; literal/ad-hoc paths are **forbidden**.
* **Shape authority.** The JSON-Schema anchors for each input are the **sole** shape authority; S1 SHALL not assume undeclared columns or tolerances.
* **Scope minimisation.** Inputs enumerated in §3.2 are the **entire** set S1 may read; additional datasets are out of scope for S1.
* **Non-mutation.** S1 SHALL NOT mutate or persist any of the inputs; it emits only `s1_tz_lookup`.

### 3.4 Null/empty allowances

* **Nudge application:** It is **per-site optional**—ε is applied only when required to break border ambiguity. (Policy asset itself MUST be present and sealed.)
* **Overrides:** May be empty in S0 but are **not** read in S1; their emptiness has no effect on S1.

---

## 4. Inputs & authority boundaries **(Binding)**

### 4.1 Authority model (normative)

* **Shape authority:** JSON-Schema anchors fix columns, domains, PK, partitions, and strictness.
* **Catalogue authority:** The Dataset Dictionary fixes **IDs → canonical paths/partitions/format**.
* **Existence/licensing authority:** The Artefact Registry fixes **presence, licence class, retention, provenance**.
* **Precedence on disputes:** **Schema › Dictionary › Registry**. 
* **Gate law:** Read permission flows from the **2A.S0 gate receipt** for the target `manifest_fingerprint` (S1 does not re-hash upstream bundles). 
* **Identity law:** Path tokens MUST equal embedded lineage where both appear (Layer-1 Identity & Path Law). *(By reference.)*
* **Dictionary-only resolution:** Inputs MUST be resolved by **ID**, not literal paths. 

### 4.2 Per-input boundaries

1. **2A.S0 gate receipt (evidence)**

   * **Shape:** `schemas.2A.yaml#/validation/s0_gate_receipt_v1`.
   * **Catalogue:** `s0_gate_receipt_2A` (fingerprint-scoped). 
   * **Registry:** validation receipt entry (fingerprint partition). 
   * **Boundary:** S1 SHALL only verify presence + schema validity for the **same** `manifest_fingerprint`; no re-hash, no joins. 

2. **`site_locations` (1B egress; required)**

   * **Shape:** `schemas.1B.yaml#/egress/site_locations` (PK & partitions). 
   * **Catalogue:** path family `data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/` with partitions `[seed, fingerprint]`. 
   * **Registry:** 1B egress posture (order-free; write-once; atomic publish). 
   * **Boundary:** S1 MAY read only the columns required to map `(lat, lon)` to a provisional `tzid`; it SHALL read **only** the run’s `(seed, fingerprint)` partition; no mutation. 

3. **`tz_world` polygons (ingress; required)**

   * **Shape:** `schemas.ingress.layer1.yaml#/tz_world_2025a` (release-specific anchor). 
   * **Catalogue/Registry:** release id → canonical path; licence class recorded (ODbL-1.0). 
   * **Boundary:** S1 SHALL use `tz_world` **as sealed in S0** for point-in-polygon membership; minimal invariants enforced here are **CRS=WGS84** and **non-empty** geometry. No topology edits or re-projection in S1. 

4. **`tz_nudge` policy (required)**

   * **Shape:** `schemas.2A.yaml#/policy/tz_nudge_v1`.
   * **Catalogue:** `config/timezone/tz_nudge.yml`. 
   * **Registry:** policy/config entry with digest & semver. 
   * **Boundary:** S1 SHALL read only the ε parameter (strictly > 0) and units; S1 applies at most one deterministic nudge per ambiguous site and MUST record the nudged coordinates when used.

> *Note:* Although sealed by S0, **tzdb release** and **override list** are **out of scope** for S1 (used by later 2A states). 

### 4.3 Validation responsibilities (S1 scope)

* **Receipt presence & fingerprint match** (same `manifest_fingerprint`). 
* **Dictionary resolution** succeeds for each input; no literal paths. 
* **Partition discipline:** `site_locations` read strictly under the run’s `[seed, fingerprint]`. 
* **Ingress minima:** `tz_world` validates (WGS84, non-empty); `tz_nudge` ε > 0.

### 4.4 Prohibitions

S1 SHALL NOT: apply policy **overrides** (S2), parse **tzdb rules** (S3), read any 1B or ingress surface beyond those in §4.2, mutate any input, rely on implicit/relative paths, or perform any RNG activity.

---

## 5. Outputs (datasets) & identity **(Binding)**

### 5.1 Primary deliverable — `s1_tz_lookup`

**Role.** Geometry-only provisional TZ assignment per site for the selected `(seed, manifest_fingerprint)`.
**Shape (authority).** `schemas.2A.yaml#/plan/s1_tz_lookup` fixes PK, partitions, columns (incl. `tzid_provisional`, optional `nudge_*`). 
**Catalogue.** Dataset Dictionary binds ID→path/partitions/format and writer order:
`data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/` with **partitions** `[seed, fingerprint]`, **ordering** `[merchant_id, legal_country_iso, site_order]`, **format** Parquet. 
**Registry.** Registered as a plan dataset; dependencies reference `site_locations` and `tz_world_2025a`; schema anchor as above. 

### 5.2 Identity & path law

* **Partition set:** `[seed, fingerprint]` (no additional partitions). 
* **Path↔embed equality:** Where lineage appears both in **path tokens** and **row fields**, values **MUST** byte-equal (Layer-1 Identity & Path Law).
* **Single-writer & immutability:** One successful publish per `(seed, fingerprint)`; re-emitting MUST be **byte-identical** or **ABORT**. (Registry posture mirrors other 2A datasets.) 
* **Writer order:** Files **SHOULD** be written in the catalogue order `[merchant_id, legal_country_iso, site_order]`; file order is non-authoritative. 

### 5.3 No additional S1 outputs

S1 emits only `s1_tz_lookup`. Final per-site `tzid` egress (`site_timezones`) is produced by S2 and is not an S1 deliverable. (Dictionary/Registry entries shown for context.)

### 5.4 Format, licensing & retention (by catalogue/registry)

* **Format:** Parquet (Dictionary authority). 
* **Licence/TTL:** Proprietary-Internal; typical retention 365 days (Registry/Dictionary authority).

**Binding effect.** Downstream 2A states **MUST** select by `(seed, manifest_fingerprint)`, verify the presence and schema-validity of `s1_tz_lookup`, and rely on the Dictionary as the sole authority for path/partition/format.

---

## 6. Dataset shapes & schema anchors **(Binding)**

**Shape authority.** JSON-Schema anchors are the **sole** source of truth for columns, domains, PK/partitions, sort discipline, and strictness. This section enumerates the anchors S1 binds to and the catalogue/registry entries that reference them. 

### 6.1 Output table — `s1_tz_lookup` (plan)

* **ID → Schema:** `schemas.2A.yaml#/plan/s1_tz_lookup` (**columns_strict: true**). The anchor fixes **PK** `[merchant_id, legal_country_iso, site_order]`, **partitions** `[seed, fingerprint]`, and writer **sort** `[merchant_id, legal_country_iso, site_order]`. Required columns include site identity, `(lat_deg, lon_deg)`, and `tzid_provisional`; `nudge_lat_deg`/`nudge_lon_deg` are nullable fields that record an applied ε-nudge. 
* **Dictionary binding:** `data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/` with **partitioning** `[seed, fingerprint]`, **ordering** `[merchant_id, legal_country_iso, site_order]`, **format** Parquet. 
* **Registry reference:** Registered as a **plan** dataset; dependencies: `site_locations`, `tz_world_2025a`; schema ref as above. 

### 6.2 Referenced inputs (read-only in S1)

* **`site_locations` (1B egress):** `schemas.1B.yaml#/egress/site_locations`; Dictionary path `data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/` with **partitions** `[seed, fingerprint]`, **ordering** `[merchant_id, legal_country_iso, site_order]`; **final in layer: true**.
* **`tz_world_2025a` (ingress polygons):** `schemas.ingress.layer1.yaml#/tz_world_2025a` (GeoParquet, WGS84). Dictionary lists the canonical path under `reference/spatial/tz_world/2025a/tz_world.parquet`. 
* **`tz_nudge` (policy config):** `schemas.2A.yaml#/policy/tz_nudge_v1` (ε > 0, units documented); catalogued at `config/timezone/tz_nudge.yml`.

### 6.3 Identity & partition posture (binding)

* **Output partitions:** `s1_tz_lookup` is partitioned by **`[seed, fingerprint]`**; path tokens are governed by the Dataset Dictionary and **MUST** match any embedded lineage fields (path↔embed equality). 
* **Single-writer & immutability:** One successful publish per `(seed, fingerprint)`; re-emits must be **byte-identical** or abort (Registry posture). 

### 6.4 Binding constraints (shape-level, S1)

* **Strict columns.** `s1_tz_lookup` is **columns_strict: true**; undeclared columns are invalid. 
* **Nudge fields as a pair.** When ε-nudge is applied, **both** `nudge_lat_deg` and `nudge_lon_deg` SHALL be present; otherwise **both** SHALL be null (validated in §9). *(Schema permits nulls; validator enforces the pair rule.)* 
* **Valid tzid domain.** `tzid_provisional` values MUST conform to the layer-wide `iana_tzid` definition and SHALL belong to the sealed `tz_world` release (validated in §9).

**Result.** With these anchors and catalogue bindings, S1’s single deliverable `s1_tz_lookup` is fully specified; inputs are pinned to their authoritative schemas; and identity/partition discipline matches the Dictionary and Registry contracts.

---

## 7. Deterministic behaviour (RNG-free) **(Binding)**

### 7.1 Posture & scope

* S1 is **strictly deterministic** and **RNG-free**.
* S1 relies on the **2A.S0 gate receipt** for the target `manifest_fingerprint` to establish read permission; it does **not** re-hash upstream bundles. 
* Inputs are resolved **only via the Dataset Dictionary**; literal paths are forbidden. The only fingerprinted input S1 reads is `site_locations` at the run’s `(seed, manifest_fingerprint)`. 
* Output is the **`s1_tz_lookup`** plan table under `[seed, fingerprint]`, with shape fixed by the S1 anchor.

### 7.2 Gate → resolve → assign (canonical order)

1. **Verify gate.** Assert presence & schema validity of the **2A.S0 gate receipt** for the target fingerprint. *(S1 may proceed only if valid.)* 
2. **Resolve inputs.**

   * Select `site_locations` **exactly** at `[seed, fingerprint]` for this run.
   * Bind `tz_world` to the **sealed release** from S0 (WGS84, non-empty).
   * Bind the **`tz_nudge`** policy sealed in S0 (ε strictly > 0).
3. **Per-site assignment (geometry-only).** For each input site row:
   a. Evaluate point-in-polygon membership against the sealed `tz_world`.
   b. **Cardinality = 1 ⇒** set `tzid_provisional` to that zone; `nudge_*` remain null.
   c. **Ambiguous/border case (cardinality ≠ 1) ⇒** apply a **single ε-nudge**: `(lat', lon') = (lat + ε, lon + ε)` in degrees; re-evaluate membership.

   * Record `nudge_lat_deg = lat'`, `nudge_lon_deg = lon'` when a nudge is used.
   * If nudging would exit the valid coordinate domain, flip the sign on the offending component to keep the point in range.
   * If membership remains ambiguous or empty after this single nudge, **abort** (see §10 failure codes).
     d. The assigned `tzid_provisional` **MUST** conform to the layer `iana_tzid` domain **and** belong to the sealed `tz_world` release. 

### 7.3 Row coverage & bijection

* S1 **SHALL** produce **exactly one** `s1_tz_lookup` row for **every** `site_locations` row in the selected `[seed, fingerprint]` partition; no drops, no extras. 

### 7.4 Output emission (identity & immutability)

* Emit **`s1_tz_lookup`** under `data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/` with partitions `[seed, fingerprint]` and writer order `[merchant_id, legal_country_iso, site_order]`. Path↔embed equality **MUST** hold where lineage appears in rows. 
* **Single-writer, write-once** posture applies; any non-identical re-emit to an existing `(seed, fingerprint)` partition **MUST** abort. 

### 7.5 Prohibitions (non-behaviours)

S1 **SHALL NOT**:

* apply **policy overrides** (handled in S2),
* parse or use **tzdb** transition rules (S3),
* read any dataset beyond those bound in §7.2,
* mutate any input surfaces, or
* perform any RNG activity. 

### 7.6 Idempotency

Given the same **gate receipt**, the same **`site_locations`** partition, the same **`tz_world`** release, and the same **`tz_nudge`** policy, S1 **SHALL** produce byte-identical `s1_tz_lookup` output.

---

## 8. Identity, partitions, ordering & merge discipline **(Binding)**

### 8.1 Identity tokens

* **Identity for S1 output:** exactly one pair **`(seed, manifest_fingerprint)`** per publish.
* **No new tokens:** `parameter_hash` is **not** a partition for S1.
* **Path↔embed equality:** where lineage appears both in **path tokens** and **row fields**, values **MUST** byte-equal (Layer-1 Identity & Path Law). 

### 8.2 Partitions & path family

* **Dataset:** `s1_tz_lookup` → `data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/`.
* **Partitions (binding):** `[seed, fingerprint]` (no others). Dictionary is the **catalogue authority** for path/format. 
* **Registry echo:** Registry lists the same identity family and schema anchor for `s1_tz_lookup`. 

### 8.3 Keys, uniqueness & aliasing

* **Primary key (shape authority):** `[merchant_id, legal_country_iso, site_order]` per the schema anchor.
* **Uniqueness:** one output row per input site key in the selected `[seed, fingerprint]` partition; no duplicates, no omissions (validated in §9). 

### 8.4 Writer order (discipline)

* **Writer sort (Dictionary):** `[merchant_id, legal_country_iso, site_order]`.
* **File order:** **non-authoritative**; consumers MUST NOT infer semantics from file order.

### 8.5 Merge & immutability

* **Write-once per `(seed, fingerprint)`** identity. A re-emit into an existing partition **MUST** be **byte-identical**; otherwise the run **MUST ABORT**.
* **Publish posture:** stage → fsync → **single atomic move** into the identity partition. 

### 8.6 Concurrency & conflict detection

* **Single-writer per identity.** Concurrent writes targeting the same `(seed, fingerprint)` are not permitted; the presence of existing artefacts under that partition constitutes a **conflict** and S1 **MUST** abort. (Global posture mirrored from Layer-1 egress conventions.) 

### 8.7 Discovery & selection (downstream contract)

* Downstream 2A states **MUST** select `s1_tz_lookup` by **`(seed, manifest_fingerprint)`** using **Dictionary resolution** (no literal paths) and verify schema validity before read. 

### 8.8 Retention & relocation

* **Retention/TTL** and licence class are governed by Dictionary/Registry (typical retention: 365 days).
* **Relocation** that preserves the Dictionary path family and partitioning is non-breaking; changes that affect partition keys or path tokens are **breaking** and out of scope for S1.

**Effect.** These constraints make `s1_tz_lookup` uniquely addressable by `(seed, fingerprint)`, immutable once published, and safely consumable without ambiguity, with Schema as **shape authority**, Dictionary as **catalogue authority**, and Registry as **existence/licensing authority**.

---

## 9. Acceptance criteria (validators) **(Binding)**

**PASS definition.** A run of 2A.S1 is **ACCEPTED** iff **all** mandatory validators below pass. Any validator marked **Abort** failing causes the run to **FAIL**; **Warn** does not block emission.

### 9.1 Gate & input resolution (mandatory)

**V-01 — S0 receipt present (Abort).** A valid **2A.S0 gate receipt** exists for the target `manifest_fingerprint` and schema-validates.
**V-02 — Dictionary resolution (Abort).** All S1 inputs resolve by **ID** via the Dataset Dictionary:
`site_locations` (1B egress, `[seed,fingerprint]`), `tz_world_<release>`, and `tz_nudge`. Literal paths are forbidden.
**V-03 — Partition selection (Abort).** `site_locations` is read **only** from the run’s `(seed, manifest_fingerprint)` partition. 

### 9.2 Ingress minima (mandatory)

**V-04 — `tz_world` invariants (Abort).** The chosen `tz_world` release is present, **WGS84** and **non-empty** (as catalogued). 
**V-05 — `tz_nudge` invariants (Abort).** The sealed policy schema-validates and `epsilon_degrees` is **> 0**.

### 9.3 Output shape & identity (mandatory)

**V-06 — Schema validity (Abort).** The emitted `s1_tz_lookup` table validates against `schemas.2A.yaml#/plan/s1_tz_lookup` (**columns_strict: true**). 
**V-07 — Path↔embed equality (Abort).** Output partition tokens `[seed, fingerprint]` **byte-equal** any embedded lineage fields, per Layer-1 identity law; dataset is written under `…/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/`. 
**V-08 — Write-once semantics (Abort).** If the target `(seed, fingerprint)` partition already exists, newly written bytes MUST be **byte-identical**; otherwise **ABORT**. 

### 9.4 Coverage, uniqueness & assignment (mandatory)

**V-09 — 1:1 coverage (Abort).** There is **exactly one** `s1_tz_lookup` row for **every** `site_locations` row in the selected `[seed, fingerprint]` partition (no drops, no extras). 
**V-10 — PK uniqueness (Abort).** No duplicate primary keys `[merchant_id, legal_country_iso, site_order]` in `s1_tz_lookup`. 
**V-11 — Non-null provisional tzid (Abort).** Every output row has **non-null** `tzid_provisional`. (Schema permits nulls, but S1 must resolve all sites or abort.) 
**V-12 — Valid tzid domain & membership (Abort).** Each `tzid_provisional` conforms to the layer `iana_tzid` domain **and** appears in the sealed `tz_world` release.
**V-13 — Nudge pair rule (Abort).** If a border tie occurred, **both** `nudge_lat_deg` and `nudge_lon_deg` are present; otherwise **both** are null. 
**V-14 — Border ambiguity resolved (Abort).** No output row remains with unresolved border ambiguity after applying a **single** ε-nudge per policy. 

### 9.5 Catalogue discipline (mandatory)

**V-15 — Writer order (Warn).** Files are written in catalogue order `[merchant_id, legal_country_iso, site_order]` (file order is non-authoritative). 

### 9.6 Outcome semantics

* **PASS:** V-01…V-14 pass; V-15 may warn.
* **FAIL:** Any **Abort** validator fails.
* **WARN:** Only non-blocking advisories (e.g., V-15) fail; they MUST surface in the run-report when §11 is introduced.

### 9.7 (For §10) Validator → error-code mapping (normative)

| Validator                    | Error code(s) (to be defined in §10)       |
| ---------------------------- | ------------------------------------------ |
| V-01 S0 receipt present      | 2A-S1-001 MISSING_S0_RECEIPT               |
| V-02 Dictionary resolution   | 2A-S1-010 INPUT_RESOLUTION_FAILED          |
| V-03 Partition selection     | 2A-S1-011 WRONG_PARTITION_SELECTED         |
| V-04 `tz_world` invariants   | 2A-S1-020 TZ_WORLD_INVALID                 |
| V-05 `tz_nudge` invariants   | 2A-S1-021 NUDGE_POLICY_INVALID             |
| V-06 Schema validity         | 2A-S1-030 OUTPUT_SCHEMA_INVALID            |
| V-07 Path↔embed equality     | 2A-S1-040 PATH_EMBED_MISMATCH              |
| V-08 Write-once semantics    | 2A-S1-041 IMMUTABLE_PARTITION_OVERWRITE    |
| V-09 1:1 coverage            | 2A-S1-050 COVERAGE_MISMATCH                |
| V-10 PK uniqueness           | 2A-S1-051 PRIMARY_KEY_DUPLICATE            |
| V-11 Non-null tzid           | 2A-S1-052 NULL_TZID                        |
| V-12 Valid tzid & membership | 2A-S1-053 UNKNOWN_TZID                     |
| V-13 Nudge pair rule         | 2A-S1-054 NUDGE_PAIR_VIOLATION             |
| V-14 Border resolved         | 2A-S1-055 BORDER_AMBIGUITY_UNRESOLVED      |
| V-15 Writer order (Warn)     | 2A-S1-070 WRITER_ORDER_NONCOMPLIANT (Warn) |

*Authorities:* Output shape and PK/partitions are owned by the S1 anchor; catalogue paths/partitions/order by the 2A Dictionary; presence/licensing by the 2A Registry; gate evidence by the S0 receipt.

---

## 10. Failure modes & canonical error codes **(Binding)**

**Code format.** `2A-S1-XXX NAME` (stable identifiers).
**Effect classes.** `Abort` = run MUST fail and emit nothing; `Warn` = non-blocking, MUST be surfaced in the run-report.
**Required context on raise.** Include: `manifest_fingerprint`, `seed`, and—where applicable—`dataset_id`, `catalog_path`, and the **site key** `(merchant_id, legal_country_iso, site_order)`.

### 10.1 Gate & input resolution

* **2A-S1-001 MISSING_S0_RECEIPT (Abort)** — No valid 2A.S0 gate receipt for the target `manifest_fingerprint`.
  *Remediation:* publish/repair S0; rerun S1.
* **2A-S1-010 INPUT_RESOLUTION_FAILED (Abort)** — An input (`site_locations`, `tz_world_<release>`, or `tz_nudge`) failed **Dictionary** resolution or Registry authorisation.
  *Remediation:* correct Dictionary/Registry entries or IDs; rerun.
* **2A-S1-011 WRONG_PARTITION_SELECTED (Abort)** — `site_locations` not read **exactly** from `(seed, manifest_fingerprint)`.
  *Remediation:* select the exact partition; rerun.

### 10.2 Ingress minima (sealed inputs)

* **2A-S1-020 TZ_WORLD_INVALID (Abort)** — `tz_world` release missing, CRS ≠ WGS84, or geometry set empty.
  *Remediation:* seal a valid release in S0; rerun S1.
* **2A-S1-021 NUDGE_POLICY_INVALID (Abort)** — `tz_nudge` policy missing/invalid or `epsilon_degrees ≤ 0`.
  *Remediation:* fix the policy asset; rerun.

### 10.3 Output shape & identity

* **2A-S1-030 OUTPUT_SCHEMA_INVALID (Abort)** — `s1_tz_lookup` fails the schema anchor (columns_strict/PK/types).
  *Remediation:* emit schema-valid rows only.
* **2A-S1-040 PATH_EMBED_MISMATCH (Abort)** — Any embedded lineage token does not byte-equal the `seed`/`fingerprint` path tokens.
  *Remediation:* correct identity fields or path; rerun.
* **2A-S1-041 IMMUTABLE_PARTITION_OVERWRITE (Abort)** — Attempt to write non-identical bytes into an existing `(seed, fingerprint)` partition.
  *Remediation:* either produce byte-identical output or use a new identity.

### 10.4 Coverage, uniqueness & assignment

* **2A-S1-050 COVERAGE_MISMATCH (Abort)** — Not **exactly one** output row per `site_locations` row in the selected partition (missing or extra rows).
  *Remediation:* ensure 1:1 projection; rerun.
* **2A-S1-051 PRIMARY_KEY_DUPLICATE (Abort)** — Duplicate `[merchant_id, legal_country_iso, site_order]` in `s1_tz_lookup`.
  *Remediation:* deduplicate; rerun.
* **2A-S1-052 NULL_TZID (Abort)** — Any output row has `tzid_provisional = null`.
  *Remediation:* resolve membership (with ε-nudge if needed) or fail the run explicitly.
* **2A-S1-053 UNKNOWN_TZID (Abort)** — `tzid_provisional` not in layer `iana_tzid` domain **or** not present in the sealed `tz_world` release.
  *Remediation:* correct assignment or update sealed inputs; rerun.
* **2A-S1-054 NUDGE_PAIR_VIOLATION (Abort)** — Only one of `nudge_lat_deg`/`nudge_lon_deg` is set, or both set when no nudge path was taken.
  *Remediation:* enforce the pair rule; rerun.
* **2A-S1-055 BORDER_AMBIGUITY_UNRESOLVED (Abort)** — After the single ε-nudge pass, membership remains ambiguous or empty.
  *Remediation:* review geometry or policy; if policy cannot resolve, treat as hard failure.

### 10.5 Catalogue discipline

* **2A-S1-070 WRITER_ORDER_NONCOMPLIANT (Warn)** — Files not written in catalogue order `[merchant_id, legal_country_iso, site_order]` (file order is non-authoritative).
  *Remediation:* align writer sort; advisory only.

### 10.6 Authority conflict (resolution rule)

* **2A-S1-080 AUTHORITY_CONFLICT (Abort)** — Irreconcilable disagreement among **Schema, Dictionary, Registry** for the same asset after applying precedence (**Schema › Dictionary › Registry**).
  *Remediation:* fix the lower-precedence authority (or the schema if wrong), then rerun.

**Binding note.** New failure conditions introduced by future revisions MUST allocate **new codes** (append-only) and MUST NOT repurpose existing identifiers.

---

## 11. Observability & run-report **(Binding)**

### 11.1 Scope & posture

* **Purpose.** Surface auditable evidence of S1’s gate verification, input resolution, and geometry-only assignment outcomes.
* **Not identity-bearing.** The run-report does **not** affect dataset identity or gates.
* **One per run.** Exactly one report per attempted S1 run (success or failure).

---

### 11.2 Run-report artefact (normative content)

A single UTF-8 JSON object **SHALL** be written for the run with at least the fields below. Missing required fields are **Warn** (policy may escalate).

**Top level (run header):**

* `segment : "2A"`
* `state : "S1"`
* `status : "pass" | "fail"`
* `manifest_fingerprint : hex64`
* `seed : uint64`
* `started_utc, finished_utc : rfc3339_micros`
* `durations : { wall_ms : uint64 }`

**Gate & inputs (as used by S1):**

* `s0.receipt_path : string` — Dictionary path to the verified 2A.S0 receipt
* `s0.verified_at_utc : rfc3339_micros`
* `inputs.site_locations.path : string` — Dictionary path for the selected `(seed,fingerprint)` partition
* `inputs.tz_world.id : string` — release ID (e.g., `tz_world_2025a`)
* `inputs.tz_world.license : string`
* `inputs.tz_nudge.semver : string`
* `inputs.tz_nudge.sha256_hex : hex64`

**Lookup summary (geometry-only outcomes):**

* `counts.sites_total : uint64` — rows read from `site_locations`
* `counts.rows_emitted : uint64` — rows written to `s1_tz_lookup`
* `counts.border_nudged : uint64` — rows where ε-nudge was applied
* `counts.distinct_tzids : uint32` — number of unique `tzid_provisional`
* `checks.pk_duplicates : uint32` — detected primary-key duplicates (0 on PASS)
* `checks.coverage_mismatch : uint32` — missing/excess rows vs input (0 on PASS)
* `checks.null_tzid : uint32` — rows with `tzid_provisional = null` (0 on PASS)
* `checks.unknown_tzid : uint32` — tzids not in sealed `tz_world` (0 on PASS)

**Outputs:**

* `output.path : string` — Dictionary path to `s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/`
* `output.format : "parquet"`

**Diagnostics:**

* `warnings : array<error_code>` — any non-blocking codes raised (e.g., writer-order)
* `errors : array<{code, message, context}>` — on failure, list canonical codes and brief context

---

### 11.3 Structured logs (minimum event kinds)

S1 **SHALL** emit machine-parseable log records correlating to the report. Minimum events:

* **`GATE`** — start/end + result of S0 receipt verification; include `manifest_fingerprint`.
* **`INPUTS`** — resolved IDs/paths for `site_locations`, `tz_world`, `tz_nudge`.
* **`LOOKUP`** — totals (`sites_total`, `border_nudged`, `distinct_tzids`).
* **`VALIDATION`** — each validator outcome `{id, result, code?}` for §9.
* **`EMIT`** — successful publication of `s1_tz_lookup` with Dictionary path.

Every record **SHALL** include: `timestamp_utc (rfc3339_micros)`, `segment`, `state`, `seed`, `manifest_fingerprint`, and `severity (INFO|WARN|ERROR)`.

---

### 11.4 Discoverability, retention & redaction

* **Discoverability.** The run-report path **MUST** be surfaced in CI/job metadata alongside the output Dictionary path.
* **Retention.** Programme policy governs report TTL; changes to retention **MUST NOT** alter dataset identity or partitions.
* **Redaction.** Reports/logs **MUST NOT** include raw site rows or PII; coordinates are not logged per-row. Only counts, IDs, paths, digests, and timestamps are permitted.

---

## 12. Performance & scalability **(Informative)**

### 12.1 Workload shape

* **Reads:** one `site_locations` partition for the selected `(seed, manifest_fingerprint)`, the sealed `tz_world` release, and the sealed `tz_nudge` policy.
* **Compute:** point-in-polygon tests per site; optional single ε-nudge for border cases.
* **Writes:** one row per input site into `s1_tz_lookup`. No RNG, no timetable/DST logic.

### 12.2 Complexity (N = sites in the selected partition; M = tz polygons)

* **Without spatial indexing:** worst-case ~ **O(N × M)** membership checks.
* **With any spatial index/filtering:** expected ~ **O(N × log M)** (or **O(N × k)** with small candidate sets), where `k ≪ M` is average polygons tested per site.
* **Overall:** wall time scales linearly with `N` given a fixed polygon index.

### 12.3 Memory model

* **Streaming-friendly.** Process sites row-wise; no need to materialise all sites.
* **Resident set dominated by:** polygon index + modest read/write buffers.
* **Nudge storage:** only per-row nudged coordinates when used; no extra structures.

### 12.4 I/O profile

* **Input:** sequential scan of `site_locations`; one-time load of `tz_world` (and any index the implementation builds).
* **Output:** sequential write of `s1_tz_lookup` in catalogue order `[merchant_id, legal_country_iso, site_order]` (file order non-authoritative).

### 12.5 Parallelism & concurrency posture

* **Across identities:** different `(seed, manifest_fingerprint)` pairs are embarrassingly parallel.
* **Within an identity:** internal parallelism (e.g., sharding by geography/PK ranges) is fine **behind a single final writer**; the publish into the partition remains **single-writer, write-once**.

### 12.6 Geometry considerations (hot spots)

* **Border density:** coastal/island regions and micro-polygons increase candidate sets and the chance of ε-nudge.
* **Degenerate geometries:** self-intersections/invalid rings should be excluded by ingress guarantees; S1 assumes a valid, WGS84, non-empty `tz_world`.
* **Nudge rate:** typically small; track `border_nudged` in the run-report for early warning if it spikes.

### 12.7 Scalability knobs (programme-level)

* Cap on **max sites per job** (split large seeds into batches, then merge behind the final writer).
* Cap on **polygon index size / build time** (e.g., prebuilt or cached index per `tz_world` release).
* Back-pressure & retry policy for remote object stores (if applicable).
* Advisory threshold for **border-nudged share** (warn-only; doesn’t change acceptance).

### 12.8 Re-run & churn costs

* Changing **`tz_world`** or **`tz_nudge`** (sealed in S0) yields a new `manifest_fingerprint`, requiring recomputation for all seeds that target it.
* Re-running with unchanged inputs is **idempotent** and should reproduce bytes exactly.

### 12.9 Typical envelopes (order-of-magnitude)

* `tz_world` size tends to dominate warm-up (index build/load); site scan and row emission scale ~linearly with input row count.
* Output footprint ~ one row per site (adds `tzid_provisional` and, rarely, `nudge_*`).

*Summary:* S1 is I/O- and geometry-bound, deterministic, and scales linearly with the number of sites once a polygon index is available. Parallelise across identities or shard internally behind a single atomic publish to preserve the write-once contract.

---

## 13. Change control & compatibility **(Binding)**

### 13.1 Versioning & document status

* **SemVer** applies to this state spec (`MAJOR.MINOR.PATCH`).

  * **PATCH:** editorial clarifications that do **not** alter behaviour, validators, or shapes.
  * **MINOR:** strictly backward-compatible additions that do **not** change identity, partitions, PK, or acceptance outcomes.
  * **MAJOR:** any change that can alter identity, shape/PK/partitions, the assignment law, or validator results.

### 13.2 Stable compatibility surfaces (must remain invariant)

1. **Identity:** output selected by **`(seed, manifest_fingerprint)`**; partitions are **`[seed, fingerprint]`** only; path↔embed equality.
2. **Output surface:** dataset **`s1_tz_lookup`** exists with its **schema anchor** and **ID** unchanged.
3. **Shape/keys:** PK = `[merchant_id, legal_country_iso, site_order]`; required columns include `lat_deg`, `lon_deg`, `tzid_provisional`; `nudge_lat_deg`/`nudge_lon_deg` are nullable and paired.
4. **Assignment law:** geometry-only membership against the sealed `tz_world` with at most **one ε-nudge** per ambiguous site; if nudged, record both `nudge_*`.
5. **Coverage:** 1:1 projection from `site_locations` rows in the selected partition to `s1_tz_lookup` rows (no drops/extras).
6. **Gate posture:** S1 reads inputs **only after** verifying the 2A.S0 receipt for the target `manifest_fingerprint`; S1 does **not** re-hash upstream bundles.
7. **Catalogue posture:** Dictionary is the authority for IDs→paths/partitions/format; Registry for existence/licence/retention; Schema is shape authority.
8. **Validator & code semantics:** meanings of §9 validators and §10 error codes.

### 13.3 Backward-compatible changes (**MINOR** or **PATCH**)

Permitted when they do **not** change identity or acceptance:

* **Diagnostics only:** tighten or add **Warn-only** validators (e.g., advisory checks on writer order, nudge rate).
* **Error codes:** append **new** codes without changing existing meanings.
* **Dictionary/Registry metadata:** add provenance/licence/TTL fields; refine descriptions/owners.
* **Schema clarifications:** tighten textual descriptions, add explicit bounds that match existing implementations.
* **Enum growth for diagnostics:** expand diagnostic enums (if any) with an **escape hatch** (e.g., `*_ext`) that consumers may ignore.

> Note: The S1 anchor is **columns_strict**. Adding new **data columns** to `s1_tz_lookup` **is not** backward-compatible unless introduced under a predeclared extension mechanism (see §13.7). Otherwise it is **MAJOR**.

### 13.4 Breaking changes (**MAJOR**)

Require a MAJOR bump and downstream coordination:

* Change to **partitions** (adding/removing/renaming partition keys) or to **PK**.
* Renaming/removing **`s1_tz_lookup`** or its **schema anchor**, or relocating it to another path family.
* Altering the **assignment law** (e.g., different border policy, more than one nudge, new tie-break direction) or making `nudge_*` non-nullable/mandatory.
* Changing **coverage semantics** (e.g., allowing >1 output row per site or permitting drops).
* Turning any existing **Warn** into **Abort**, or changing error-code meanings.
* Admitting additional inputs (e.g., applying overrides or tzdb logic in S1) or reading beyond §3’s input set.
* Any change that makes previously valid S1 outputs **fail** schema/validators unchanged.

### 13.5 Deprecation policy

* **Announce → grace → remove.** A feature slated for removal is marked **Deprecated** at least **one MINOR** before removal with an **effective date**.
* **No repurposing.** Deprecated fields/codes/IDs are never reused; removal occurs only at a **MAJOR** bump.
* **Alias window (anchors/IDs).** When renaming, provide aliases for at least one MINOR; both anchors validate to identical shapes during the window.

### 13.6 Co-existence & migration

* **Dual-anchor window.** When evolving `s1_tz_lookup`, publish a new anchor (e.g., `s1_tz_lookup_v2`) and allow both in Dictionary for a grace period; downstream selects by **anchor version** while still keying identity by `(seed, fingerprint)`.
* **Re-fingerprinting is upstream.** Changing `tz_world` or `tz_nudge` happens in S0 and yields a **new `manifest_fingerprint`**; S1 recomputes for that fingerprint without spec change.
* **Idempotent re-runs.** Re-running with unchanged inputs must reproduce identical bytes.

### 13.7 Reserved extension points

* **Not defined in v1.0.0-alpha**: the current anchor is **columns_strict** and does **not** admit arbitrary extension columns.
* A future **MINOR** may introduce an **`extensions` object** or pattern-based `ext_*` columns **if** the anchor simultaneously permits them and downstream is specified to ignore unknown extension members. Without such a mechanism, adding columns is **MAJOR**.

### 13.8 External dependency evolution

* **`tz_world` release churn** is **not** a spec change; it changes only sealed bytes → `manifest_fingerprint` (handled by S0).
* **`tz_nudge` policy** version bumps (semver) are sealed by S0 and likewise flow through via fingerprint; S1’s law (single ε-nudge, record when applied) remains invariant.

### 13.9 Governance & change process

Every change SHALL include: (i) version bump rationale, (ii) compatibility impact (Patch/Minor/Major), (iii) updated anchors/Dictionary/Registry stanzas (if any), (iv) validator/error-code diffs, and (v) migration notes.
Frozen specs SHALL record an **Effective date**; downstream pipelines target frozen or explicitly authorised alpha versions.

### 13.10 Inter-state coupling

* **Upstream:** depends only on S0’s receipt and the sealed inputs (`site_locations`, `tz_world`, `tz_nudge`).
* **Downstream:** S2 consumes `s1_tz_lookup` and may replace `tzid_provisional` via policy overrides; any S1 change that forces S2 to recompute S0 hashes or alters S2’s read contract is **breaking**.

---

## Appendix A — Normative cross-references *(Informative)*

> Pointers only. These define authorities S1 relies on. Shapes come from JSON-Schema anchors; IDs→paths/partitions/format come from the Dataset Dictionary; existence/licensing/retention from the Artefact Registry.

### A1. Layer-1 governance (global rails)

* **Closed-world & gates:** JSON-Schema is the only shape authority; runs are sealed by `{parameter_hash, manifest_fingerprint}`; downstream reads enforce **No PASS → No Read**.
* **Bundle/index/flag law:** PASS flag = SHA-256 over raw bytes of files listed in `index.json` (ASCII-lex order, flag excluded); bundles are fingerprint-scoped and write-once/atomic.
* **Layer primitives used by S1:** `id64`, `iso2`, `iana_tzid`, `rfc3339_micros` in the layer schema pack. 

### A2. Upstream receipt and sealed inputs used by S1

* **2A.S0 gate receipt** (`s0_gate_receipt_2A`) — Dictionary path family (fingerprint-scoped) and schema anchor in the 2A pack. *(S1 verifies presence/validity; does not re-hash bundles.)* 
* **`site_locations`** (1B egress) — Schema anchor, path/partitions `[seed,fingerprint]`, writer sort `[merchant_id, legal_country_iso, site_order]`; final-in-layer; order-free.
* **`tz_world_2025a`** (ingress polygons) — Dictionary entry (GeoParquet, WGS84) and Registry cross-layer pointer; ingress anchor referenced.
* **`tz_nudge`** (policy) — Dictionary entry and schema anchor (`schemas.2A.yaml#/policy/tz_nudge_v1`).

### A3. S1 output surface

* **`s1_tz_lookup`** — Schema anchor (`schemas.2A.yaml#/plan/s1_tz_lookup`) with PK `[merchant_id, legal_country_iso, site_order]`, partitions `[seed,fingerprint]`; Dictionary path family and writer order; Registry stanza.

### A4. Downstream (for context; not read by S1)

* **`site_timezones`** (S2 egress) — anchor (2A pack), Dictionary path family (`…/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/`), Registry stanza.
* **`tzdb_release`** (S3 input) — 2A schema object anchor and Registry entry (release tag + archive digest).
* **2A validation bundle/flag** (S5 gate for 2A egress) — bundle/flag schema stubs in 2A pack; Registry path uses the same index/flag law as 1A/1B.

### A5. Segment 2A overview

* **State flow (S0→S5)** — S1 = geometry-only `tzid` lookup; S2 = overrides; S3 = tzdb timetables; S4 = legality; S5 = validation bundle. 

### A6. 1B egress gate posture (why S0 receipt matters)

* **Consumers must verify 1B PASS before reading `site_locations`**; Dictionary echoes the rule; Registry defines 1B bundle/flag with the 1A-style hashing law.

### A7. Additional anchor references touched by S1 spec text

* **Layer `$defs`** referenced by S1 (`iso2`, `iana_tzid`, `rfc3339_micros`). 
* **2A pack — validation/manifests stubs** used by S0 and S5 (receipt, inventory, bundle index, passed flag).

*Consumers of this specification should resolve all shapes from the anchors above and all IDs→paths/partitions solely via the Dataset Dictionary; Registry entries provide licensing/provenance and do not override shape or path law.*

---