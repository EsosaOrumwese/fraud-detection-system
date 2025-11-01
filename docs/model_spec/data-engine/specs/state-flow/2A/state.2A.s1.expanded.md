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