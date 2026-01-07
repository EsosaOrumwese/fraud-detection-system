# State 2A.S0 — Gate, Manifest & Sealed Inputs

## 1. Document metadata & status **(Binding)**

**Title:** Layer-1 · Segment 2A · State-0 — Gate & Sealed Inputs
**Short name:** 2A.S0 “Gate”
**Layer/Segment/State:** L1 / 2A (Civil Time) / S0
**Doc ID:** `layer1/2A/state-0`
**Version (semver):** `v1.0.0-alpha` *(update as this spec advances)*
**Status:** `alpha` *(this document is **normative**; semantics lock at `frozen` in a ratified release)*
**Owners:** Design Authority (DA): Esosa Orumwese • Review Authority (RA): Layer 1 Governance
**Effective date:** 2025-11-01 (UTC)
**Canonical location:** ‹repo path to this spec file›

**Normative cross-references (by pointer, not restated):**

* Layer-1 Governance: Identity & Path Law; Hashing/Fingerprint Law; Numeric Policy; Gate Law “No PASS → No Read”.
* Segment 1B: Egress contract for `site_locations` and 1B Validation Bundle + `_passed.flag`.
* Segment 2A Overview: state flow and outputs inventory for 2A.
* Layer-1 Ingress Schemas: `tz_world` (WGS84 polygons), IANA tzdb release metadata.
* 2A Schemas (this segment): anchors for `validation/s0_gate_receipt_v1` and `manifests/sealed_inputs_v1`.
* Dataset dictionary & artefact registries that enumerate/authorise the assets consumed/emitted by 2A.S0.

**Informative references (terminology only):** IANA tzdb release notes; data-source licensing pages as cited in the artefact registry.

**Conformance & interpretation:**

* Sections labelled **Binding** are normative for design; **Informative** sections do not create obligations.
* Normative keywords **MUST/SHALL/SHOULD/MAY** are as defined in RFC 2119/8174.
* This is a **design specification**: it defines required behaviours, identities, inputs/outputs, and inter-state contracts; it does **not** prescribe implementations or pseudocode.

**Change log (summary):**

* `v1.0.0-alpha` — Initial spec for 2A.S0 (Gate & Sealed Inputs). Subsequent edits follow semver and the segment’s Change-Control section.

---

## 2. Purpose & scope **(Binding)**

**Intent.** Establish the **entry gate** for Segment 2A (Civil Time) by proving upstream eligibility and **sealing all 2A ingress assets** into a canonical manifest that defines the segment’s run identity. The state produces a **fingerprint-scoped gate receipt** that all downstream 2A states MUST verify before any read.

**Objectives (normative).** 2A.S0 SHALL:

* **Assert upstream validity:** Confirm that Segment 1B completed successfully under the Layer-1 Gate Law (**No PASS → No Read**), using the upstream validation bundle and flag.
* **Seal 2A ingress:** Enumerate and pin all inputs required by Segment 2A (e.g., `site_locations`, `tz_world` polygons, IANA tzdb release, and declared override lists) as **immutable, content-addressed assets**.
* **Fix 2A identity:** Derive and record the segment’s `manifest_fingerprint` from the sealed-inputs manifest (per Layer-1 Fingerprint Law) and bind it with the run’s `parameter_hash`.
* **Emit the gate receipt:** Publish `s0_gate_receipt_2A` and the per‑asset `sealed_inputs_v1` inventory for use by subsequent 2A states and external auditors.
* **Remain deterministic and RNG-free:** No random draws, sampling, or probabilistic behaviour occur in S0.

**In scope.**

* Verifying the **existence, immutability, and version pinning** of each required 2A input under the correct authorities (schema, dictionary, registry).
* Canonicalising the **naming and inclusion** of inputs (no duplicates or aliasing) and recording their provenance (URIs, digests, version tags/licences as applicable).
* Defining the **run identity** for Segment 2A via `manifest_fingerprint` and documenting it in the receipt for downstream verification.

**Out of scope.**

* Assigning time zones to sites, building time-tables/caches, or assessing DST legality/folds (these are performed by later 2A states).
* Restating Layer-1 global laws (identity, hashing, numeric policy, gate semantics) beyond normative cross-reference.
* Any implementation guidance, algorithms, or pseudocode.

**Interfaces (design relationship).**

* **Upstream:** Consumes 1B egress strictly **after** verifying the 1B PASS artefacts.
* **Downstream:** 2A states (e.g., time-zone assignment and timetable/cache construction) **MUST** verify `s0_gate_receipt_2A` and match the `manifest_fingerprint` before reading sealed inputs.

**Completion semantics.**

* 2A.S0 is considered complete when the gate receipt is written under the correct identity path, the sealed-inputs manifest is fixed and reproducible, and all downstream prerequisites for verification are present.

---

## 3. Preconditions & sealed inputs **(Binding)**

### 3.1 Preconditions

2A.S0 SHALL begin only when all of the following hold:

* **Upstream PASS present.** Segment 1B has published a **validation bundle** and a matching **`_passed.flag`** under `fingerprint={manifest_fingerprint}` as defined in the Dataset Dictionary (IDs: `validation_bundle_1B`, `validation_passed_flag_1B`). Consumers MUST treat “No PASS → No Read.” 
* **Run identity fixed.** `parameter_hash` for the 2A run is fixed (Layer-1 identity law, by reference).
* **Authority sets available.** The schema set, dataset dictionary, and artefact registries that enumerate the inputs below are addressable and free of placeholders for assets in scope (licensing and retention specified). *(By reference to Layer-1 governance.)*
* **RNG posture.** 2A.S0 is **RNG-free** (deterministic).

### 3.2 Sealed inputs (enumerated)

S0 **seals** the following assets into the 2A manifest. Each item MUST be **immutable**, **content-addressed** (digest recorded), and **uniquely named** within the manifest (no aliasing/duplicates). JSON-Schema is the **sole shape authority**; IDs→paths/partitions resolve via the Dataset Dictionary; provenance/licensing via the Artefact Registry.

1. **Upstream 1B PASS artefacts (gate evidence).**

   * `validation_bundle_1B` — Dictionary‑resolved folder under `data/layer1/1B/validation/fingerprint={manifest_fingerprint}/` (**partition:** `[fingerprint]`). Do not assume a subfolder name; Dictionary governs the exact layout.
   * `validation_passed_flag_1B` — `_passed.flag` under `data/layer1/1B/validation/fingerprint={manifest_fingerprint}/`.
     *Role:* proves eligibility to read any 1B egress for this fingerprint. 

2. **1B egress pointer required by 2A.**

   * `site_locations` — `data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/` (**partitions:** `[seed, fingerprint]`). Order-free egress; writer sort as per Dictionary. *(Read is permitted only after PASS verification.)*

3. **Time-zone polygons (tz-world).**

   * Example current ID: `tz_world_2025a` → `reference/spatial/tz_world/2025a/tz_world.parquet` (unpartitioned). Anchor: `schemas.ingress.layer1.yaml#/tz_world_2025a`. CRS MUST be WGS84; non-empty geometry set.

4. **IANA zoneinfo (tzdata) release.**

   * Archive and version metadata pinned as governed artefacts (e.g., `artefacts/priors/tzdata/tzdata2025a.tar.gz` with `zoneinfo_version.yml`). The **release tag** and the archive’s **SHA-256** are sealed. *(Exact filenames may vary; Dictionary/Registry SHALL enumerate the concrete items for this run.)* 

5. **Override registry (policy).**

   * `config/timezone/tz_overrides.yaml` — governed list of overrides with `semver`, `sha256_digest`, and per-entry fields (`scope`, `tzid`, `evidence_url`, `expiry_yyyy_mm_dd`). Empty file is allowed; if present, it is sealed and later applied by 2A (precedence is defined downstream). 

6. **Border-nudge constant (policy).**

   * `config/timezone/tz_nudge.yml` — carries ε and its digest; sealed for reproducibility (used later for deterministic tie-breaks at polygon borders). 

7. **Auxiliary reference tables actually used by 2A (if referenced).**

   * Examples: `iso3166_canonical_2024` (ISO-2 FK surface), `world_countries` (country polygons) — both are unpartitioned reference surfaces with declared licences and anchors in the ingress schema set. *(Include **only** if later 2A states reference them; otherwise omit from the manifest.)* 

### 3.3 Sealing constraints (normative)

* **Content addressing.** For every sealed asset, S0 SHALL record: ID, canonical URI (Dictionary path), **version tag**, **byte digest (SHA-256)**, format, size in bytes, and licence class from Registry/Dictionary. *(Hashing/fingerprint law by reference.)*
* **No aliasing / no duplicates.** Two differently named entries that resolve to identical bytes (same digest) are **forbidden**; duplicate basenames are **forbidden**.
* **Scope minimisation.** Only inputs enumerated in §3.2 MAY be sealed. Any dataset not listed is **out of scope** for S0.
* **Gate order.** S0 SHALL verify the **1B PASS** artefacts **before** admitting `site_locations` into the sealed manifest. *(No PASS → No Read.)* 

### 3.4 Null/empty allowances

* **Overrides:** The override registry MAY be empty; if present, it MUST still be sealed with digest and version. 
* **Optional auxiliaries:** ISO/country tables MAY be omitted if not referenced by any 2A state; when included, they MUST meet the same sealing rules. 

*Result:* When §3 completes, 2A.S0 holds a **canonical sealed-inputs manifest** whose digest defines `manifest_fingerprint` for the segment, and a **gate receipt** can be emitted in §5–§7 (by reference to later sections).

---

## 4. Inputs & authority boundaries **(Binding)**

### 4.1 Authority model (normative)

* **Shape authority:** JSON-Schema anchors define column sets, types, nullability, and invariants. *(See §6 for anchors.)*
* **Catalogue authority:** The Dataset Dictionary defines dataset **IDs → canonical paths/partitions/order/format**.
* **Existence/licensing authority:** The Artefact Registry defines **presence, licence class, retention, provenance URIs**.
* **Precedence on disputes:** Shape ⟨Schema⟩ › Path & partitions ⟨Dictionary⟩ › Existence/licence ⟨Registry⟩. Implementations SHALL resolve conflicts by this order.
* **Gate law:** Upstream consumption is subject to **No PASS → No Read** (by reference).
* **Identity law:** Path tokens **MUST** equal their embedded columns (by reference).

### 4.2 Per-input authority & boundaries

For each sealed input listed in §3.2, S0 binds authorities and limits behaviour as follows:

1. **1B PASS artefacts** *(validation bundle; `_passed.flag`)*

   * **Shape:** 1B validation schemas (bundle index; flag semantics).
   * **Catalogue:** Dictionary entries for 1B validation assets.
   * **Existence/licence:** 1B registry entries.
   * **Boundary:** S0 SHALL only **verify** presence and digest equality; it SHALL NOT read or interpret 1B payloads beyond what is necessary to prove PASS.

2. **`site_locations` (1B egress pointer)**

   * **Shape:** 1B egress schema for `site_locations`.
   * **Catalogue:** Dictionary entry defining partitions (incl. `fingerprint={manifest_fingerprint}`; `seed={seed}`).
   * **Existence/licence:** 1B registry.
   * **Boundary:** S0 may **reference** the dataset in the sealed manifest but SHALL NOT **read** records; eligibility depends solely on verified PASS.

3. **`tz_world` polygons (WGS84)**

   * **Shape:** Ingress schema anchor for the chosen `tz_world` release.
   * **Catalogue:** Dictionary entry (release-tagged ID → canonical path).
   * **Existence/licence:** Ingress/Reference registry.
   * **Boundary:** S0 verifies **version pinning, CRS=WGS84, non-emptiness**; it SHALL NOT perform spatial derivations (those occur in later 2A states).

4. **IANA tzdb (zoneinfo) release**

   * **Shape:** Artefact metadata schema for archive + version (release tag, checksums).
   * **Catalogue:** Dictionary entry mapping the release tag to URIs.
   * **Existence/licence:** Registry for third-party artefacts.
   * **Boundary:** S0 records **release tag and digests** only; it SHALL NOT expand or interpret zone rules.

5. **Time-zone override list (policy)**

   * **Shape:** 2A override list schema (scope, target keys, `tzid`, justification, expiry).
   * **Catalogue:** Dictionary entry (config asset).
   * **Existence/licence:** Registry entry under policy/config domain.
   * **Boundary:** S0 **seals** the list (allowing empty) and records precedence metadata; **no application** of overrides occurs in S0.

6. **Border-nudge constant (policy)**

   * **Shape:** 2A nudge schema (scalar ε and units).
   * **Catalogue:** Dictionary entry (config asset).
   * **Existence/licence:** Registry policy/config.
   * **Boundary:** S0 **seals** the constant; it SHALL NOT apply any geometric nudge.

7. **Auxiliary reference tables (if used by 2A)**

   * **Shape:** Ingress schema anchors (e.g., ISO country tables).
   * **Catalogue:** Dictionary entries for the specific releases included.
   * **Existence/licence:** Reference registry.
   * **Boundary:** S0 **includes** only those actually referenced downstream; no transformation or denormalisation in S0.

### 4.3 Validation responsibilities (S0 scope)

* **Presence & pinning.** Every declared input MUST exist, be readable, and be **content-addressed** (digest recorded).
* **Version discipline.** Releases/tags MUST be explicit and recorded; ambiguous “latest” pointers are forbidden.
* **Uniqueness.** Basenames and byte digests MUST be unique within the sealed manifest (no aliasing/duplicates).
* **Minimal sanity.** Where stated above (e.g., CRS=WGS84; non-empty), S0 checks only **minimal** invariants required to trust identity; all substantive semantic checks are deferred to later 2A states.

### 4.4 Prohibitions

* S0 SHALL NOT: read 1B egress rows, apply overrides, perform spatial joins, interpret tz rules, or mutate any sealed asset.
* Any operation outside §4.3 is **out of scope** for S0 and belongs to subsequent 2A states.

---

## 5. Outputs (bundle) & identity **(Binding)**

### 5.1 Primary deliverable — `s0_gate_receipt_2A` (fingerprint-scoped)

**Purpose.** A minimal, fingerprint-scoped receipt that (i) attests **1B PASS** for the same fingerprint and (ii) freezes the **sealed-inputs manifest** for Segment 2A. It is the artefact downstream 2A states MUST verify before any read. This mirrors the 1B S0 receipt posture (fingerprint-only identity; path↔embed equality) for cross-segment consistency.

**Partition & path law.**

* **Partition:** `[fingerprint]` (no `seed`; parameter hash is embedded, not a partition). The path token **MUST** byte-equal the embedded `manifest_fingerprint`. 
* **Canonical template (Dictionary owns exact path):**
  `data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json`
  *(Dictionary governs format/path; this spec fixes partition and equality.)* 

**Required fields (design intent; shape owned by `schemas.2A.yaml#/validation/s0_gate_receipt_v1`).**

* `manifest_fingerprint : hex64` — **equals** the `fingerprint` path token. 
* `validation_bundle_path : string` — Dictionary‑resolved location of the verified 1B bundle, e.g. `data/layer1/1B/validation/fingerprint={manifest_fingerprint}/` (no hardcoded subfolder; Dictionary is authority). 
* `parameter_hash : hex64` — recorded lineage token (not a partition in S0).
* `flag_sha256_hex : hex64` — value proven against the bundle’s ASCII-lex hash rule. 
* `verified_at_utc : RFC-3339` — observational timestamp (non-semantic). 
* `sealed_inputs : array<object>` — each entry names an input S0 sealed for 2A with its **partition set** and **schema anchor** (per‑asset digests and version tags live in the mandatory `sealed_inputs_v1` inventory), e.g.:
  • `site_locations` (partition `["seed","fingerprint"]`, `schemas.1B.yaml#/egress/site_locations`). 
  • `tz_world_<release>` (ingress anchor for the chosen release). 
  • `tzdb_release` (archive + version metadata; registry/dictionary authority). 
  • Overrides/nudge config (2A policy assets; listed for sealing, not application in S0). *(Anchor to be defined in 2A schema set.)*
* *(Optional)* `notes : string` — non-semantic. 

**Write posture.** Single-writer, **write-once** per fingerprint; publish via stage → fsync → **atomic move**. Re-publishing to an existing partition **MUST** be byte-identical; otherwise **ABORT** (immutable partition). This mirrors 1B’s immutability law. 

### 5.2 Diagnostic deliverable (mandatory) — `sealed_inputs_v1`

**Purpose.** Row-wise inventory of every asset sealed in §3, to aid audits without reopening the 1B bundle. This table is mandatory and carries per‑asset `version_tag` and `sha256_hex` used for fingerprinting.

**Identity & path.**

* **Partition:** `[fingerprint]` (same as the receipt).
* **Canonical template (Dictionary owns exact path/format):**
  `data/layer1/2A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.parquet`
* **Columns (design intent; shape owned by `schemas.2A.yaml#/manifests/sealed_inputs_v1`):** `asset_id`, `kind`, `basename`, `version_tag`, `schema_ref`, `catalog_path`, `sha256_hex`, `size_bytes`, `license_class`. Authority split mirrors Layer-1 practice (Schema=shape; Dictionary=IDs→paths/partitions; Registry=licence/retention).

### 5.3 Identity discipline & downstream contract

* **Gate dependence.** Downstream 2A states MUST verify that a single `s0_gate_receipt_2A` exists for the target `manifest_fingerprint` and **schema-validates**; they **do not** re-hash the 1B bundle. *(Same pattern 1B used for its S0 receipt.)* The mandatory `sealed_inputs_v1` inventory carries the per‑asset digests and version tags used for fingerprinting.
* **Path↔embed equality.** Wherever lineage appears both in path tokens and embedded fields (e.g., `manifest_fingerprint`), values **MUST** byte-equal. This mirrors the 1B egress/receipt law. 
* **Dictionary-only resolution.** All IDs resolve via the Dataset Dictionary; **no literal paths**. Schema remains the **sole shape authority**; Registry governs existence/licensing/retention. 

### 5.4 Format, licensing & retention (by reference)

* **Formats.** Receipt is **JSON**; diagnostics typically **Parquet** (owned by Dictionary entries). 1B’s receipt used JSON; 2A follows the same convention. 
* **Licensing & retention.** Licence class and TTL are owned by the Dictionary/Registry; S0 MUST NOT override them. (Typical retention mirrors validation artefacts and egress norms in Layer-1.) 

**Binding effect.** With a fingerprint-scoped receipt and mandatory sealed-inputs table published under strict path↔embed equality and write-once atomicity, 2A gains a reproducible **read permission** boundary identical in spirit to 1B’s S0. All later 2A states rely on this receipt + inventory—not on re-implementing the 1B bundle hash—and MUST match the same `manifest_fingerprint` before consuming sealed inputs.

---

## 6. Dataset shapes & schema anchors **(Binding)**

**Shape authority.** JSON-Schema is the **sole** shape authority. This section **enumerates the anchors** 2A.S0 binds to and the **identity/partition posture** each anchor fixes. IDs→paths/partitions/format resolve **only** via the Dataset Dictionary; provenance/licensing resolve via the Artefact Registry. 

### 6.1 Schema pack & `$defs` used

* **Segment pack:** `schemas.2A.yaml` (this segment).
* **Layer pack (shared types):** use the layer `$defs` for closed domains, notably **`hex64`**, **`uint64`**, and **`rfc3339_micros`** (these live in `schemas.layer1.yaml`; 2A references them).

**Anchor rule (by reference):** `#/validation/*` and `#/manifests/*` live in `schemas.2A.yaml`; ingress FK surfaces (e.g., ISO/tz/world polygons) live in the ingress pack; 1B egress anchors (e.g., `site_locations`) live in `schemas.1B.yaml`. 

---

### 6.2 Gate receipt (fingerprint-scoped)

**ID → Schema:** `s0_gate_receipt_2A` → `schemas.2A.yaml#/validation/s0_gate_receipt_v1` (table; **columns_strict: true**; stored as JSON; anchor defines the columns).
**Identity & keys (binding):**

* **Primary key:** `[manifest_fingerprint]` (one row per fingerprint).
* **Partitions:** `[fingerprint]` (path token **must** byte-equal the embedded `manifest_fingerprint`).
* **Sort:** `[]` (no writer-sort requirement for the single-row receipt).

**Required columns (design intent; exact types live in the anchor):**

* `manifest_fingerprint` — **hex64** (Layer `$defs`). Path↔embed **MUST** byte-equal. 
* `validation_bundle_path` — string that **resolves to the 1B validation bundle** for the same fingerprint (Dictionary owns exact path; Registry mirrors provenance). Reference pattern: 1B bundles sit under `data/layer1/1B/validation/fingerprint={manifest_fingerprint}/`. 
* `parameter_hash` — **hex64** (Layer `$defs`), recorded lineage token (not a partition in S0).
* `flag_sha256_hex` — **hex64** of the verified 1B bundle (flag content). 
* `verified_at_utc` — **rfc3339_micros** (UTC). 
* `sealed_inputs` — **array<object>** listing every input 2A has sealed (minimum properties:
  `id : string`, `partition : array<string>` (e.g., `["seed","fingerprint"]`), `schema_ref : string`). The object shape mirrors the sealed-inputs list used by 1B’s S0 gate receipt. 
* *(Optional)* `notes : string`.

**Downstream contract.** Every 2A state **MUST** verify the presence and schema-validity of `s0_gate_receipt_2A` for the target fingerprint **instead of** re-hashing the 1B bundle. (Pattern matches 1B’s S0.) 

---

### 6.3 Sealed-inputs inventory (diagnostic; mandatory)

**ID → Schema:** `sealed_inputs_v1` → `schemas.2A.yaml#/manifests/sealed_inputs_v1` (table; **columns_strict: true**).
**Identity & keys (binding):**

* **Primary key:** `[manifest_fingerprint, asset_id]`.
* **Partitions:** `[fingerprint]` (same as the receipt).
* **Writer sort:** `[asset_kind, basename]` (stable audit order; file order is non-authoritative).

**Required columns (design intent; exact typing in the anchor):**

* `manifest_fingerprint` — **hex64** (Layer `$defs`). 
* `asset_id` — string ID (Dictionary ID or governed config name).
* `asset_kind` — enum `{dataset, bundle, log, manifest, config}`.
* `basename` — string (filename or dataset stem).
* `version_tag` — string (e.g., `2025a`, `{manifest_fingerprint}`, or `{parameter_hash}` as applicable).
* `schema_ref` — string (canonical **JSON-Schema** anchor for the asset).
* `catalog_path` — string (Dictionary path for the asset; Dictionary is the only authority for IDs→paths). 
* `sha256_hex` — **hex64** (content digest). 
* `size_bytes` — **uint64**. 
* `license_class` - string (must match Dictionary/Registry licence class; e.g., Proprietary-Internal, Public-Domain, ODbL-1.0, CC-BY-4.0).
* `created_utc` — **rfc3339_micros** (observational, non-semantic). 

---

### 6.4 Anchors for **referenced inputs** (pinned by the receipt)

The receipt’s `sealed_inputs[]` **MUST** point to authoritative anchors for every asset it seals. At minimum, 2A.S0 binds the following anchors (examples shown; actual list is the manifest produced in §3):

* **1B egress pointer:**
  `site_locations` → `schemas.1B.yaml#/egress/site_locations` (readable only after 1B PASS; partitions `[seed,fingerprint]`; order-free by contract). 
* **Ingress FK surfaces (ingress pack):**
  `iso3166_canonical_2024` → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`;
  `world_countries` → `schemas.ingress.layer1.yaml#/world_countries`;
  `tz_world_2025a` → `schemas.ingress.layer1.yaml#/tz_world_2025a`. 
* **Tzdb release metadata (this segment):**
  `tzdb_release` → `schemas.2A.yaml#/ingress/tzdb_release_v1` *(object; records release tag and archive digest; Dictionary/Registry own the location).* (Pattern follows how 1B pins external references.) 

---

### 6.5 Dictionary binding (IDs → path/partitions/format)

For the two 2A surfaces in §6.2–§6.3, the Dataset Dictionary **SHALL** declare:

* **`s0_gate_receipt_2A`** → path family `data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/…` · **partitioning:** `[fingerprint]` · **format:** JSON. *(Dictionary owns exact filenames and retention.)*
* **`sealed_inputs_v1`** → path family `data/layer1/2A/sealed_inputs/fingerprint={manifest_fingerprint}/…` · **partitioning:** `[fingerprint]` · **format:** Parquet.
  This mirrors the 1B convention for S0 receipts and keeps the receipt **fingerprint-only**. 

---

### 6.6 Binding constraints (shape-level)

* **Path↔embed equality.** Wherever lineage appears both in **path tokens** and **row fields** (e.g., `manifest_fingerprint`), values **MUST** byte-equal. (Same rule used across Layer-1.) 
* **Strict columns.** Both anchors are **columns_strict: true**; undeclared columns are invalid (Schema enforces). 
* **Authority split.** Schema anchors govern **columns/domains/PK/partitions/sort**; Dictionary governs **IDs→paths/partitions/format/licence**; Registry records **licence/provenance**. If prose and Schema ever differ on shape, **Schema wins**. 

*Result:* With these anchors, 2A.S0 publishes a minimal, fingerprint-scoped **gate receipt** and a **sealed-inputs inventory** (mandatory), and it pins every referenced surface to its authoritative schema—`site_locations` (1B egress) and ingress FK/timezone assets—under the same schema/dictionary/registry discipline used elsewhere in Layer-1.

---

## 7. Deterministic behaviour (RNG-free) **(Binding)**

### 7.1 Posture and scope

* 2A.S0 is **strictly deterministic** and **RNG-free**.
* Behaviour is limited to **(i)** upstream gate verification, **(ii)** sealing inputs into a canonical manifest, **(iii)** fixing the segment’s identity (`manifest_fingerprint`), and **(iv)** emitting the fingerprint-scoped receipt and mandatory `sealed_inputs_v1` inventory.
* All references to hashing, identity tokens, and gate semantics are by cross-reference to Layer-1 governance; this section binds **order and conditions**, not implementation.

### 7.2 Gate sequence and isolation barrier

* **Upstream first.** Before admitting any 1B egress into the sealed manifest, S0 **SHALL** verify the 1B PASS artefacts for the *same* fingerprint (Gate Law: **No PASS → No Read**).
* **Isolation.** Until PASS is verified, S0 **SHALL NOT** read, sample, or infer from any 1B egress (including `site_locations`).
* **Same-fingerprint constraint.** The upstream artefacts and any 1B egress referenced **MUST** share the target `manifest_fingerprint` fixed for this 2A run.

### 7.3 Sealed-inputs manifest formation (canonical)

To form the sealed set for 2A:

1. **Enumerate** only the inputs authorised for 2A (§3): required 1B egress pointer(s), `tz_world` polygons, tzdb release, declared override lists, and only those auxiliary tables actually referenced by 2A.
2. **Normalise identity** for each asset using the Dataset Dictionary (IDs → canonical paths/partitions/format) and bind its **schema anchor** (shape authority) and **registry entry** (existence/licence).
3. **Pin content** by recording version/release tags and **byte digests** for every sealed item; ambiguous pointers (e.g., “latest”) are **forbidden**.
4. **Forbid aliasing and duplicates.** Two differently named entries resolving to identical bytes are **not permitted**; duplicate basenames are **not permitted**.
5. **Canonical order.** The sealed manifest **SHALL** be constructed in a stable, total order suitable for hashing (e.g., by `(asset_kind, basename)`), and this order **SHALL** be fixed by the schema/dictionary cross-reference to avoid re-ordering across runs.

### 7.4 Fingerprint derivation and binding

* **Derivation.** S0 **SHALL** compute the segment’s `manifest_fingerprint` from the canonical sealed-inputs manifest per the Layer-1 **Fingerprint Law** (canonical encoding, stable ordering, SHA-256).
* **Binding.** The computed `manifest_fingerprint` **SHALL** be used as the **partition token** for all S0 outputs (§5) and **SHALL** byte-equal any embedded `manifest_fingerprint` fields (Path↔Embed Equality).
* **Parameter linkage.** The 2A run’s `parameter_hash` is **recorded** in the receipt but does not alter the fingerprint (fingerprint is a function of sealed inputs only).

### 7.5 Emission discipline (write-once, atomic)

* **Receipt first-class.** After fingerprint derivation, S0 **SHALL** emit `s0_gate_receipt_2A` under the fingerprint partition; emission is **write-once** for that partition.
* **Diagnostics mandatory.** `sealed_inputs_v1` **SHALL** be co-partitioned by the same fingerprint and reflect exactly the sealed manifest used to compute the fingerprint.
* **Atomicity.** Outputs **SHALL** be published atomically (stage → fsync → atomic move). Re-emitting different bytes to an existing partition is **forbidden**; attempts **MUST** abort.

### 7.6 Prohibitions (non-behaviours)

* S0 **SHALL NOT**:
  • read or transform 1B egress rows;
  • parse or evaluate tzdb rule content;
  • apply overrides or geometric nudges;
  • perform spatial joins or topology checks beyond minimal asset sanity declared elsewhere;
  • generate, consume, or persist any RNG state.

### 7.7 Idempotency and re-runs

* **Idempotent by construction.** Given identical upstream PASS artefacts and an identical sealed-inputs set, rerunning S0 **SHALL** produce byte-identical outputs and the same `manifest_fingerprint`.
* **Divergence detection.** Any change to the sealed set (bytes, versions, membership, order) **SHALL** produce a different `manifest_fingerprint`, thereby selecting a distinct output partition.
* **No partials.** Partially written outputs are invalid; downstream states **MUST NOT** proceed without a complete, schema-valid receipt in the target partition.

### 7.8 Determinism receipt and observability (binding link)

* S0 **SHALL** produce a **determinism receipt** for the emitted partition (directory-level canonical hash) and surface it via the run-report/metrics (cf. §11).
* Downstream states **SHALL** verify `s0_gate_receipt_2A` (and MAY record the determinism receipt) instead of re-computing the upstream bundle hash; only the receipt and fingerprint govern read permission in 2A.

---

## 8. Identity, partitions, ordering & merge discipline **(Binding)**

### 8.1 Identity tokens

* **`manifest_fingerprint`** — the sole partition key for 2A.S0 outputs; defined only by the sealed-inputs manifest (by reference to the Layer-1 Fingerprint Law).
* **`parameter_hash`** — recorded **inside** outputs for lineage; **not** a partition key in S0.
* **`seed`** — **absent** in S0 (RNG-free state).
* **Path↔embed equality.** Any identity that appears both in the **path** and **row fields** (e.g., `manifest_fingerprint`) **MUST byte-equal** (Layer-1 Identity Law).

### 8.2 Partitions & path families

* **Receipt:** `s0_gate_receipt_2A` is partitioned by `[fingerprint]` only.
* **Diagnostics:** `sealed_inputs_v1` is co-partitioned by `[fingerprint]`.
* **Dictionary authority:** Exact path templates, filenames, and formats are governed by the Dataset Dictionary; this spec binds the **partition set** and equality law.
* **Prohibitions:** No additional partitions (e.g., `seed`) are permitted in S0 outputs; `parameter_hash` MUST NOT appear as a partition.

### 8.3 Keys, uniqueness & aliasing

* **Primary keys.**
  • `s0_gate_receipt_2A`: `[manifest_fingerprint]` (one row per fingerprint).
  • `sealed_inputs_v1`: `[manifest_fingerprint, asset_id]`.
* **Uniqueness within a fingerprint.**
  • Each `asset_id` MUST be unique.
  • **Aliasing is forbidden:** two entries that resolve to identical bytes (same digest) or duplicate basenames within a fingerprint are not allowed.
* **Single receipt rule:** Exactly **one** valid receipt exists per fingerprint partition.

### 8.4 Ordering (writer discipline)

* **Receipt:** no writer sort requirement (single-row).
* **Sealed-inputs inventory:** stable writer order by `(asset_kind, basename)` to match the canonical manifest order used for fingerprinting; file order remains non-authoritative.

### 8.5 Merge & immutability

* **Write-once per fingerprint.** A fingerprint partition is **append-only and immutable**.
* **Byte-identity rule.** Any attempt to re-emit an artefact into an existing fingerprint partition **MUST** either:
  • produce **byte-identical** content (allowed no-op), or
  • **ABORT** (if bytes would differ).
* **No in-place edits.** Updates, deletions, or tombstones within an existing fingerprint partition are **forbidden**. Any change to the sealed set (membership, versions, bytes, or canonical order) **MUST** yield a **new** `manifest_fingerprint` and therefore a new partition.

### 8.6 Concurrency & conflict detection

* **Single-writer per fingerprint.** Concurrent writes targeting the same fingerprint are not permitted. The presence of an existing receipt or inventory in the target partition constitutes a **conflict** and the run **MUST** abort.
* **Parallelism across fingerprints** is unrestricted (subject to storage policy).

### 8.7 Discovery & selection (downstream contract)

* Downstream 2A states **MUST** select by **`manifest_fingerprint`** and verify the existence and schema-validity of the **single** `s0_gate_receipt_2A` in that partition **before any read**.
* Downstream consumers **MUST NOT** infer identity from wall-clock time, directory mtime, or non-authoritative filenames.

### 8.8 Retention & relocation

* **Retention class** and any archival/relocation policies are owned by the Dictionary/Registry and **MUST NOT** alter identity tokens or partition layout.
* Relocation that preserves the Dictionary-governed canonical path family and partitioning is non-breaking; changes that affect partition keys or path tokens are **breaking** and out of scope for S0.

*Effect:* These constraints ensure every S0 emission is uniquely and immutably addressed by its `manifest_fingerprint`, reproducible across re-runs, and safely consumable by downstream states without ambiguity or re-merging.

---

## 9. Acceptance criteria (validators) **(Binding)**

**PASS definition.** A run of 2A.S0 is **ACCEPTED** iff **all** mandatory validators below pass. Any failure with **Abort** effect causes the run to **FAIL** and no outputs of §5 may be published. Validators map to canonical error codes enumerated in §10.

### 9.1 Upstream gate (mandatory)

**V-01 — `_passed.flag` present (Abort).** The upstream 1B `_passed.flag` exists at the Dictionary-resolved location for the **same** `manifest_fingerprint`.
**V-02 — Flag digest equality (Abort).** Recomputed bundle digest (per Layer-1 hashing law) **equals** the recorded `flag_sha256_hex`.
**V-03 — Same-fingerprint constraint (Abort).** Any 1B egress referenced by S0 (e.g., `site_locations`) is addressed under the **same** `manifest_fingerprint`. *(No PASS → No Read applies by reference.)*

### 9.2 Sealed-inputs manifest (mandatory)

**V-04 — Minimum set present (Abort).** The sealed set contains, at minimum: (i) upstream 1B PASS artefacts, (ii) `site_locations` pointer, (iii) `tz_world` polygons, (iv) IANA tzdb release, (v) declared override list (empty allowed), and (vi) the border-nudge constant (`tz_nudge`).
**V-05 — Pinning & authorities (Abort).** For **each** sealed item: (a) Schema anchor exists, (b) Dictionary resolves ID→canonical path/partitions/format, (c) Registry entry exists with licence/retention, (d) **version tag** and **SHA-256** digest are recorded. Ambiguous pointers (e.g., “latest”) are forbidden.
**V-06 — No aliasing / no duplicates (Abort).** Within a fingerprint: (a) no duplicate `asset_id` or `basename`, (b) no two entries resolve to identical bytes (same digest).
**V-07 — `tz_world` invariants (Abort).** CRS is **WGS84** and geometry set is **non-empty**. *(No spatial derivations required.)*
**V-08 — tzdb release invariants (Abort).** Release **tag present** and **well-formed** (e.g., `20YY[a-z]?`), and archive digest recorded.
**V-09 — Overrides invariants (Abort/Warn).** The override list (if present) validates against its schema and has unique keys per `(scope, target)`; if an authoritative tzid index is sealed in §3, all referenced `tzid` **MUST** belong to that set (**Abort**). Otherwise, only structural validity is required (**Warn**).

### 9.3 Receipt correctness (mandatory)

**V-10 — Path↔embed equality (Abort).** In `s0_gate_receipt_2A`, the embedded `manifest_fingerprint` **byte-equals** the `fingerprint` partition token.
**V-11 — Upstream proof fields (Abort).** `validation_bundle_path` resolves (via Dictionary) to the 1B bundle for the **same** fingerprint; exact folder layout is Dictionary‑defined (no assumed subfolder). `flag_sha256_hex` is present and hex‑valid.
**V-12 — Sealed-inputs concordance (Abort).** The combination of the receipt’s `sealed_inputs[]` and the mandatory `sealed_inputs_v1` inventory **exactly** enumerates the assets used to compute the fingerprint (membership and IDs in the receipt; version tags and digests in the inventory).
**V-13 — Determinism receipt (Abort).** The determinism receipt for the emitted partition is present (directory-level canonical hash), and its value is non-empty.

### 9.4 Diagnostics inventory

**V-14 — Inventory identity (Abort).** `sealed_inputs_v1` exists under the target fingerprint and its rows’ `manifest_fingerprint` pass Path↔embed equality.
**V-15 — Inventory = receipt (Abort).** The set of `asset_id` values in `sealed_inputs_v1` **matches exactly** the IDs listed in the receipt’s `sealed_inputs[]` (no extras, no omissions). Per‑asset `version_tag` and `sha256_hex` are validated via V‑16.
**V-16 — Authority echo (Abort).** For each row: `schema_ref` is an existing anchor; `catalog_path` matches the Dictionary; `license_class` matches the Registry; `version_tag` is present; `sha256_hex` is a valid hex64.

### 9.5 Identity, immutability & merge

**V-17 — Single receipt rule (Abort).** Exactly **one** `s0_gate_receipt_2A` exists under the target fingerprint; additional rows/objects are invalid.
**V-18 — Write-once semantics (Abort).** If any artefact already exists in the target fingerprint partition, newly written bytes must be **byte-identical**; otherwise, the run **MUST** abort.
**V-19 — Partition purity (Abort).** No disallowed partitions (e.g., `seed`) appear; `parameter_hash` is embedded but **not** a partition.

### 9.6 Observability & run-report

**V-20 — Run-report completeness (Warn).** The run-report records: upstream verification result, counts/bytes of sealed inputs, tzdb release tag, computed `manifest_fingerprint`, and output locations. Missing report fields are **Warn** unless required by programme-level CI.

**Outcome semantics.**

* **PASS:** V-01..V-16 and V-17..V-19 pass. (V-20 is Warn and non-blocking.)
* **FAIL:** Any **Abort** validator fails.
* **WARN:** V-09 (second clause) or V-20 fail when programme-level policy treats them as non-fatal; warnings do not block emission but MUST be surfaced in the run-report.

*All validators rely on the Layer-1 Identity, Fingerprint, and Gate laws by cross-reference; Schema remains the sole shape authority; the Dataset Dictionary governs IDs→paths/partitions/format; and the Artefact Registry governs existence/licensing/retention.*

---

## 10. Failure modes & canonical error codes **(Binding)**

**Code format.** Errors in 2A.S0 use stable identifiers of the form **`2A-S0-XXX NAME`**.
**Effect classes.** `Abort` = the run MUST fail and emit nothing from §5. `Warn` = non-blocking, MUST be surfaced in the run-report; programme policy MAY escalate to `Abort`.
**Context.** Each raised error MUST carry the **fingerprint**, and where relevant an **asset_id** and **catalog_path**.

### 10.1 Upstream gate (No PASS → No Read)

* **2A-S0-001 MISSING_1B_FLAG (Abort)** — Upstream `_passed.flag` not found for the target `manifest_fingerprint`.
* **2A-S0-002 FLAG_DIGEST_MISMATCH (Abort)** — Recomputed bundle digest ≠ `flag_sha256_hex`.
* **2A-S0-003 MISSING_1B_BUNDLE (Abort)** — `validation_bundle_path` does not resolve or is unreadable.
* **2A-S0-004 UPSTREAM_FINGERPRINT_MISMATCH (Abort)** — Any referenced 1B egress (e.g., `site_locations`) is not addressed under the **same** `manifest_fingerprint`.

### 10.2 Sealed-inputs manifest formation

* **2A-S0-010 MINIMUM_SET_MISSING (Abort)** — Required assets set incomplete (bundle/flag, `site_locations` pointer, `tz_world`, tzdb release, overrides, `tz_nudge`).
* **2A-S0-011 SCHEMA_ANCHOR_UNKNOWN (Abort)** — Asset lacks a valid JSON-Schema anchor.
* **2A-S0-012 DICTIONARY_RESOLUTION_FAILED (Abort)** — Dataset ID does not resolve to a canonical path/partitions/format.
* **2A-S0-013 REGISTRY_ENTRY_MISSING (Abort)** — No registry/licence record for the asset.
* **2A-S0-014 UNPINNED_VERSION (Abort)** — Version tag absent/ambiguous (e.g., “latest”).
* **2A-S0-015 DIGEST_MISSING_OR_INVALID (Abort)** — SHA-256 missing or not well-formed hex64.
* **2A-S0-016 DUPLICATE_ASSET_ID (Abort)** — Duplicate `asset_id` within the fingerprint.
* **2A-S0-017 ALIASING_BYTES (Abort)** — Two differently named entries resolve to identical bytes (same digest).
* **2A-S0-018 DUPLICATE_BASENAME (Abort)** — Duplicate `basename` within the sealed set.

### 10.3 Time-zone assets (ingress constraints)

* **2A-S0-020 TZ_WORLD_CRS_INVALID (Abort)** — `tz_world` CRS ≠ WGS84.
* **2A-S0-021 TZ_WORLD_EMPTY (Abort)** — `tz_world` has zero features.
* **2A-S0-022 TZDB_VERSION_INVALID (Abort)** — tzdb release tag missing or malformed.
* **2A-S0-023 TZDB_DIGEST_MISSING (Abort)** — tzdb archive digest absent/invalid.

### 10.4 Overrides (policy inputs)

* **2A-S0-030 OVERRIDES_SCHEMA_INVALID (Abort)** — Override list fails its schema.
* **2A-S0-031 OVERRIDES_DUPLICATE_SCOPE_TARGET (Abort)** — Duplicate `(scope, target)` entries.
* **2A-S0-032 OVERRIDES_UNKNOWN_TZID (Abort/Warn)** — An override references a `tzid` not present in the sealed tz-index.

  * **Effect:** `Abort` when a tz-index is sealed; otherwise `Warn`.

### 10.5 Receipt correctness (fingerprint-scoped)

* **2A-S0-040 RECEIPT_PATH_EMBED_MISMATCH (Abort)** — Embedded `manifest_fingerprint` ≠ `fingerprint` path token.
* **2A-S0-041 RECEIPT_BUNDLE_PATH_INVALID (Abort)** — `validation_bundle_path` does not resolve to the 1B bundle for the same fingerprint.
* **2A-S0-042 RECEIPT_FLAG_HEX_INVALID (Abort)** — `flag_sha256_hex` not well-formed hex64.
* **2A-S0-043 RECEIPT_SEALED_INPUTS_MISMATCH (Abort)** — `sealed_inputs[]` does not exactly match the sealed manifest used for fingerprinting.
* **2A-S0-044 DETERMINISM_RECEIPT_MISSING (Abort)** — Determinism receipt absent/empty for the emitted partition.

### 10.6 Diagnostics inventory

* **2A-S0-050 INVENTORY_WRONG_PARTITION (Abort)** — `sealed_inputs_v1` not under the target fingerprint or fails path↔embed equality.
* **2A-S0-051 INVENTORY_RECEIPT_MISMATCH (Abort)** — Set of `asset_id` values in `sealed_inputs_v1` differs from the IDs listed in the receipt’s `sealed_inputs[]` (no extras, no omissions).
* **2A-S0-052 INVENTORY_AUTHORITY_MISMATCH (Abort)** — `schema_ref` not an existing anchor, `catalog_path` disagrees with Dictionary, or `license_class` disagrees with Registry.

### 10.7 Identity, partitions, immutability

* **2A-S0-060 DUPLICATE_RECEIPT (Abort)** — More than one `s0_gate_receipt_2A` row/object exists for a fingerprint.
* **2A-S0-061 PARTITION_PURITY_VIOLATION (Abort)** — Disallowed partitions present (e.g., `seed`); or `parameter_hash` appears as a partition.
* **2A-S0-062 IMMUTABLE_PARTITION_OVERWRITE (Abort)** — Attempt to write non-identical bytes into an existing fingerprint partition.

### 10.8 Observability & run-report

* **2A-S0-070 RUN_REPORT_INCOMPLETE (Warn)** — Required run-report fields missing (upstream verification result, sealed-inputs counts/bytes, tzdb tag, fingerprint, output locations).

### 10.9 Authority conflict (resolution rule)

* **2A-S0-080 AUTHORITY_CONFLICT (Abort)** — Irreconcilable disagreement among Schema, Dictionary, and Registry for the same asset (after applying the precedence **Schema › Dictionary › Registry**).

  * **Effect:** `Abort`.
  * **Note:** Minor metadata gaps that do not affect shape/path/licence SHOULD be raised as `Warn` via programme policy rather than this code.

---

### 10.10 Validator ↔ error code mapping (normative)

| Validator                        | Error code(s)                     |
|----------------------------------|-----------------------------------|
| V-01 `_passed.flag` present      | 2A-S0-001                         |
| V-02 Flag digest equality        | 2A-S0-002                         |
| V-03 Same-fingerprint (upstream) | 2A-S0-004                         |
| V-04 Minimum set present         | 2A-S0-010                         |
| V-05 Pinning & authorities       | 2A-S0-011 · 012 · 013 · 014 · 015 |
| V-06 No aliasing / duplicates    | 2A-S0-016 · 017 · 018             |
| V-07 `tz_world` invariants       | 2A-S0-020 · 021                   |
| V-08 tzdb invariants             | 2A-S0-022 · 023                   |
| V-09 Overrides invariants        | 2A-S0-030 · 031 · 032             |
| V-10 Path↔embed equality         | 2A-S0-040                         |
| V-11 Upstream proof fields       | 2A-S0-003 · 041 · 042             |
| V-12 Sealed-inputs concordance   | 2A-S0-043                         |
| V-13 Determinism receipt         | 2A-S0-044                         |
| V-14 Inventory identity          | 2A-S0-050                         |
| V-15 Inventory = receipt         | 2A-S0-051                         |
| V-16 Authority echo              | 2A-S0-052                         |
| V-17 Single receipt rule         | 2A-S0-060                         |
| V-18 Write-once semantics        | 2A-S0-062                         |
| V-19 Partition purity            | 2A-S0-061                         |
| V-20 Run-report completeness     | 2A-S0-070                         |

**Binding effect.** These codes are **exhaustive** for 2A.S0 as specified. New failure conditions introduced by future spec revisions MUST allocate new codes and MUST NOT reuse retired identifiers.

---

## 11. Observability & run-report **(Binding)**

### 11.1 Scope & posture

* **Purpose.** Provide auditable visibility of S0’s gate decision and sealed-inputs outcome.
* **Not identity-bearing.** The run-report is **not** a dataset consumed by downstream states and **does not** influence identity or gates.
* **Severity.** Missing/partial report fields surface as **Warn** (cf. §9 V-20) unless programme policy escalates.

---

### 11.2 Run-report artefact (design contract)

* **Form.** A single UTF-8 JSON object (“run-report”) written for the run. File name/location are programme-level, out of scope for identity.
* **One per run.** Exactly one report per attempted S0 run (success or failure).
* **Immutability.** Once written for a **PASS**, the report is append-forbidden; re-runs that would modify content must target a different run context.

**Required top-level fields (normative):**

* `segment : "2A"`
* `state : "S0"`
* `status : "pass" | "fail"` — overall outcome of validators in §9
* `manifest_fingerprint : hex64` — the fingerprint fixed by S0
* `parameter_hash : hex64` — recorded lineage token (non-partition)
* `started_utc, finished_utc : rfc3339_micros` — wall-clock boundaries
* `durations : object` — at minimum `wall_ms : uint64`

**Upstream gate section (normative):**

* `upstream.bundle_path : string` — Dictionary-resolved path to 1B bundle (same fingerprint)
* `upstream.flag_sha256_hex : hex64` — value proved equal during gate
* `upstream.verified_at_utc : rfc3339_micros`
* `upstream.result : "verified" | "failed"`
* `upstream.errors : array<error_code>` — empty on success

**Sealed-inputs summary (normative):**

* `sealed_inputs.count : uint32` — number of assets sealed
* `sealed_inputs.bytes_total : uint64` — summed byte size of sealed assets
* `sealed_inputs.inventory_path : string` — Dictionary path of the mandatory `sealed_inputs_v1` table
* `sealed_inputs.manifest_digest : hex64` — digest actually used to derive `manifest_fingerprint` (echo)

**Timezone assets summary (normative):**

* `tz_assets.tzdb_release_tag : string`
* `tz_assets.tzdb_archive_sha256 : hex64`
* `tz_assets.tz_world_id : string` — Dictionary ID of the chosen release
* `tz_assets.tz_world_crs : "WGS84"`
* `tz_assets.tz_world_feature_count : uint64|null` — non-null if measured; MAY be `null` when only minimal sanity was performed

**Outputs & determinism (normative):**

* `outputs.receipt_path : string` — Dictionary path of `s0_gate_receipt_2A` for this fingerprint
* `outputs.inventory_path : string` — path of the mandatory `sealed_inputs_v1` inventory
* `determinism.partition_hash : hex64` — directory-level canonical hash (the **determinism receipt**) for the emitted fingerprint partition
* `determinism.computed_at_utc : rfc3339_micros`

**Diagnostics (normative):**

* `warnings : array<error_code>` — any non-fatal codes raised (e.g., policy-level warns)
* `errors : array<object>` — on failure, list `{code, message, context}` entries mapping to §10 codes

**Optional advisory fields (informative):**

* `engine_commit : string` — implementation provenance (e.g., git SHA)
* `host_info : object` — non-identifying environment facts (OS, arch)
* `notes : string`

---

### 11.3 Structured logs (binding minima)

S0 SHALL emit structured log records that are machine-parseable and correlate to the run-report. Minimum event kinds:

* **`GATE`** — start/end + result of upstream verification; include `manifest_fingerprint`, `bundle_path`, `flag_sha256_hex` (redacted if policy requires).
* **`SEAL`** — counts/bytes of assets sealed; list of `(asset_id, digest)` **may** be sampled in logs but the authoritative inventory is the receipt/diagnostic table.
* **`HASH`** — `manifest_fingerprint` derivation event including the canonicalisation mode identifier.
* **`EMIT`** — successful publication of `s0_gate_receipt_2A` and `sealed_inputs_v1` with their Dictionary paths.
* **`DETERMINISM`** — emission of the partition-level determinism receipt with `partition_hash`.
* **`VALIDATION`** — each validator outcome `{id, result, code?}` for §9 V-01…V-20.

Each log record SHALL contain: `timestamp_utc (rfc3339_micros)`, `segment`, `state`, `manifest_fingerprint`, `severity (INFO|WARN|ERROR)`, and, when applicable, a canonical `error_code` from §10.

---

### 11.4 Determinism receipt (binding)

* A **determinism receipt** for the fingerprint partition **MUST** be produced and referenced in the run-report (`determinism.partition_hash`).
* The receipt is an audit marker (not a downstream dataset). Its computation/format follow the programme’s canonical directory-hashing law; presence is required for §9 V-13.
* The receipt **MUST** be stored under the same fingerprint partition that houses the S0 outputs.

---

### 11.5 Discoverability & retention (binding split)

* **Discoverability.** The run-report path **MUST** be surfaced in CI logs and/or job metadata so auditors can retrieve it alongside the Dictionary paths for outputs.
* **Retention.** Report retention is governed by programme policy and MAY differ from dataset TTLs; altering retention MUST NOT alter dataset identity or partition layout.

---

### 11.6 Redaction & privacy (binding)

* Reports and logs **MUST NOT** contain PII or raw data rows from `site_locations` or other sealed assets.
* Paths, IDs, digests, counts, sizes, error codes, and timestamps are permissible. Any additional content is subject to programme-level redaction policy.

**Effect.** With these observability guarantees, every 2A.S0 run leaves an auditable trail tying the upstream gate decision, the sealed-inputs manifest (and its fingerprint), and the emitted artefacts together—without creating new identity surfaces or leaking implementation details.

---

## 12. Performance & scalability **(Informative)**

### 12.1 Workload shape

* **I/O-bound.** S0 reads upstream **PASS artefacts** (bundle index per programme hashing law) and the bytes of each **sealed input** to record/verify digests; it **does not** read `site_locations` rows or perform spatial/tz computations.
* **CPU-light.** Dominated by streaming SHA-256 and JSON canonicalisation for the sealed manifest.
* **Memory-light.** Streaming I/O; working set is O(size of largest single asset’s read buffer + manifest object).

### 12.2 Complexity

* **Time:** `O(∑ bytes of sealed inputs + bytes of upstream bundle index)`; constant factors depend on storage throughput and checksum implementation.
* **Space:** `O(1)` w.r.t. total asset size (streaming), plus `O(#assets)` for manifest metadata.

### 12.3 Throughput considerations

* **Parallelism across assets.** Sealing (digesting) distinct inputs MAY be performed in parallel provided the **canonical order** used to derive `manifest_fingerprint` remains fixed and independent of read order.
* **Single-stream per asset.** Avoid concurrent reads of the **same** asset to prevent thrash against remote stores.
* **Remote stores.** End-to-end time is often gated by network egress and object-store per-prefix limits; batching requests and respecting back-pressure improves stability.
* **Compression.** Digests are over **stored bytes**; no decompression is required for archives to seal identity (extraction is out of scope for S0).

### 12.4 Asset size envelope (non-normative)

Typical sealed set sizes (order-of-magnitude only):

* **1B PASS artefacts (bundle index + flag):** KBs–low MBs.
* **`tz_world` polygons (release-dependent):** tens–hundreds of MBs.
* **IANA tzdb archive + metadata:** low MBs.
* **Overrides / policy configs:** KBs.
  Total sealed bytes commonly sit in the **tens–hundreds of MBs** range; S0 runtime scales linearly with this total.

### 12.5 Concurrency & scheduling

* **One fingerprint at a time.** Writes are **single-writer** per `manifest_fingerprint`; runs for **different** fingerprints are embarrassingly parallel.
* **Idempotent retries.** If a run restarts with the same sealed set, outputs are byte-identical; partial emissions must be treated as invalid until the receipt is fully present.

### 12.6 Storage & layout

* **Small output footprint.** S0 emits one tiny **receipt** (JSON) and a modest **inventory** (Parquet).
* **Catalogue lookups.** Dictionary/Registry lookups are negligible compared to asset reads; caching those lookups lowers tail latency without affecting identity.

### 12.7 Hot spots & guardrails

* **Large polygon sets.** `tz_world` dominates I/O; keep release churn deliberate since any change forces a **new fingerprint** and downstream recomputation.
* **Alias/duplicate scans.** Duplicate/alias detection is metadata-driven; ensure `basename` discipline to avoid quadratic checks.
* **Clock skew.** Observational timestamps (`*_utc`) don’t affect identity but SHOULD be monotonic within a run to keep diagnostics clear.

### 12.8 Scalability knobs (programme-level)

* **Max sealed bytes / max asset count** per run to bound wall time.
* **Digest concurrency cap** to balance network and CPU.
* **Retry/back-off policy** for transient storage errors.
* **Inventory is always emitted**; programme-level knobs MAY control only extended diagnostics (e.g., additional non-identity columns), not the presence of `sealed_inputs_v1` itself.

*Summary:* S0 scales linearly with the total size of the sealed assets, remains memory-light via streaming, and benefits from modest parallelism across assets while keeping a fixed canonical order for fingerprinting. The dominant cost is hashing `tz_world` (release-dependent); outputs themselves are tiny and immutable.

---

## 13. Change control & compatibility **(Binding)**

### 13.1 Versioning & document status

* **SemVer applies to this state spec** (`MAJOR.MINOR.PATCH`).

  * **PATCH:** clarifications or non-behavioural editorial changes.
  * **MINOR:** strictly backward-compatible additions (fields/assets that downstream can ignore by contract).
  * **MAJOR:** any change that could alter identity, validation outcomes, or downstream read contracts.
* **Status lifecycle:** `draft → alpha → frozen`. Semantics are **normative** at `alpha`; they are **locked** at `frozen`.

### 13.2 Compatibility surfaces (what must stay stable)

S0 defines the following **stable surfaces**. Changes here are **breaking** unless explicitly allowed below.

1. **Identity:** definition of `manifest_fingerprint`; partition key set (`[fingerprint]` only); Path↔Embed equality.
2. **Outputs:** the existence, IDs, and anchors of `s0_gate_receipt_2A` (required) and `sealed_inputs_v1` (required).
3. **Gate posture:** “**No PASS → No Read**” with respect to Segment 1B.
4. **Authority model:** Schema = shape authority; Dictionary = IDs→paths/partitions/format; Registry = existence/licensing/retention; precedence **Schema › Dictionary › Registry**.
5. **Validator set & error code meanings** for S0 (§§9–10).

### 13.3 Backward-compatible changes (**MINOR** or **PATCH**)

The following are permitted without breaking downstream 2A states:

* **Additive, optional columns** to `sealed_inputs_v1` with **default/nullable** values; downstream **MUST** ignore unknown fields.
* **New optional fields** in `s0_gate_receipt_2A` that **do not** alter acceptance criteria and are **not** required for downstream reads.
* **New error codes** (append-only) that do not change the semantics of existing codes.
* **Tightened diagnostics** that remain **Warn** (do not flip a passing run to fail).
* **New allowed values** for descriptive enumerations in diagnostics **when accompanied by an `ext_*` escape hatch** (e.g., `asset_kind_ext`), leaving existing enum semantics intact.
* **Registry/Dictionary metadata additions** (licence text, provenance URLs, TTLs) that do **not** change IDs, paths, partitions, or acceptance criteria.
* **Expanded tzdb tag regex** to admit new official release forms, where the original forms remain valid.

### 13.4 Breaking changes (**MAJOR**)

The following require a **MAJOR** version and downstream coordination:

* Any change to the **fingerprint law**, canonical ordering of the sealed manifest, or what contributes to `manifest_fingerprint`.
* Altering S0 **partitions** (adding `seed`, moving `parameter_hash` into partitions, etc.).
* Renaming/removing either output dataset, or changing their **schema anchors**/IDs.
* Removing or retyping **existing columns** in `s0_gate_receipt_2A`; making an optional column **mandatory**.
* Changing the **minimum sealed set** (e.g., dropping `tz_world` or the tzdb release) or the **override precedence declaration**.
* Flipping a previously **Warn** diagnostic into an **Abort** validator, or changing the semantics of any existing **error code**.
* Changing Dictionary path families or ID → path resolution for S0 outputs.
* Any modification that would cause previously valid receipts to **fail** schema or acceptance under unchanged inputs.

### 13.5 Deprecation policy

* **Announce → grace → remove.** A feature slated for removal MUST be marked **Deprecated** at least **one MINOR** version before removal, with an **effective date**.
* **Alias period.** When renaming anchors/IDs, provide **alias anchors** for at least one MINOR version; both must validate to identical shapes.
* **Non-repurposing.** Deprecated fields/codes SHALL NOT be repurposed; removal occurs only at a **MAJOR** bump.

### 13.6 Co-existence & migration

* **Downstream tolerance.** 2A consumers **MUST** ignore unknown receipt fields and **MUST NOT** rely on ordering of `sealed_inputs[]`, beyond the canonicalisation used for fingerprinting.
* **Dual-receipt window.** During migration across MAJORs, programmes MAY permit concurrent operation of both versions by selecting by **manifest_fingerprint** and verifying against the target **anchor version**.
* **Re-fingerprinting.** Any change in sealed membership/bytes/order yields a **new fingerprint**; downstream selection by fingerprint automatically de-conflicts runs across versions.

### 13.7 External dependency evolution

* **tzdb format/tag drift.** If IANA modifies release tagging, S0 MAY add acceptance for the new form under a **MINOR** change, preserving acceptance of the old form.
* **Reference dataset churn.** Introducing a new `tz_world` release is **not** a spec change; it changes only the sealed bytes and thus the fingerprint. Schema anchors and Dictionary IDs for the chosen release MUST still validate.

### 13.8 Governance & change process

* Every change SHALL include: **(i)** version bump rationale (Patch/Minor/Major), **(ii)** compatibility impact, **(iii)** updated anchors (if any), **(iv)** validator/error-code diffs, **(v)** migration notes.
* **Test vectors.** For MINOR/MAJOR, publish at least one **before/after** sealed-set manifest and the resulting `manifest_fingerprint` to exercise acceptance criteria.
* **Effective date.** Frozen specs MUST record an **Effective date**; downstream pipelines SHALL target only frozen or explicitly authorised alpha versions.

### 13.9 Reserved extension points

* `sealed_inputs_v1` MAY include future **`ext_*`** columns (e.g., `asset_kind_ext`, `notes_ext`) that consumers SHALL ignore.
* `s0_gate_receipt_2A` MAY include an optional `extensions` object whose keys are namespaced (`vendor.key`) and **MUST NOT** affect acceptance.

### 13.10 Inter-state & inter-segment coupling

* S0’s contract with 1B and with downstream 2A states is **limited to**: gate posture, outputs (IDs/anchors), and the fingerprint identity. Changes elsewhere in 1B/2A are out of scope unless they alter those surfaces.
* Downstream states **MUST** treat the S0 receipt as the **sole** read permission artefact; changes that force downstream to recompute upstream hashes are **breaking**.

**Binding effect.** With this policy, S0 can evolve additively without disrupting downstream, while any change that would alter identity, validation outcomes, or read contracts is clearly flagged as **MAJOR** and gated by an explicit migration path.

---

## Appendix A — Normative cross-references *(Informative)*

> Pointers only; these define the authorities S0 relies on. Where anchors/IDs are “this segment”, they live in `schemas.2A.yaml` and the Layer-1 Dataset Dictionary.

### A1. Layer-1 governance (global)

* **Identity & path law (path↔embed equality).** Enforced across Layer-1 datasets; see 1B egress spec & anchors for the fingerprint/partition posture.
* **Gate law (PASS bundle + `_passed.flag`).** 1B registry defines the hashing law (ASCII-lex index, SHA-256; flag excluded) and “No PASS → No read”. 1A establishes the same pattern for upstream.
* **Validation bundle index shape (1A reference).** Bundle/index schema pattern used by downstream segments. 
* **Numeric policy.** IEEE-754 binary64 environment pinned in Layer-1 registry. 
* **RNG envelope & events (layer pack).** Common RNG event families referenced by 1B (and inherited at layer scope). 

### A2. Upstream (Segment 1B) surfaces consumed/verified by 2A.S0

* **Egress dataset — `site_locations`.** Schema anchor & Dictionary path/partitions `[seed,fingerprint]`; order-free egress; final in layer.
* **Validation bundle & PASS artefacts (1B).** Dictionary IDs and registry entry for fingerprint-scoped bundle and `_passed.flag`. *(S0 verifies PASS before any read.)*

### A3. Ingress/reference surfaces used by 2A

* **`tz_world_2025a` polygons (GeoParquet, WGS84).** Dictionary entries (ingress pack anchors).
* **`iso3166_canonical_2024` (ISO-2).** Dictionary entries (FK surface; licence: Public-Domain).
* **`world_countries` polygons.** Dictionary/registry references (ingress anchor; licence: Public-Domain).
* **IANA tzdb release (archive + tag).** 2A overview/narrative establishes the pinned zoneinfo version as a sealed input. *(Shape lives in this segment’s schema pack.)*

### A4. Segment 2A (this segment) — surfaces introduced downstream of S0

* **Overview of 2A states & deliverables.** `site_timezones` egress (per-site `tzid`), `tz_timetable_cache`, and a 2A validation bundle with `_passed.flag`. *(S0 emits only the gate receipt/manifest and seals these inputs.)* 
* **Gate receipt & sealed-inputs inventory (2A).** Anchors `#/validation/s0_gate_receipt_v1` and `#/manifests/sealed_inputs_v1` live in `schemas.2A.yaml` (this segment). *(Pointers defined by this spec; no external file.)*

### A5. Dataset Dictionary (IDs → canonical paths/partitions/format)

* **1B egress & validation entries.** `site_locations`, `validation_bundle_1B`, `validation_passed_flag_1B` with their path families and partition sets. 
* **Ingress IDs used by 2A.** `tz_world_2025a`, `iso3166_canonical_2024`, `world_countries` with ingress anchors.

### A6. Artefact Registries (existence/licence/operational posture)

* **1B registry stanzas.** `site_locations` (write-once; atomic move), `validation_bundle_1B` (hashing law & PASS), ingress `tz_world_2025a`.
* **1A registry stanzas (gate precedent & numeric policy).** `validation_bundle_1A`/`_passed.flag` (gate precedent), `ieee754_binary64`. 

### A7. Programme/overview documents (context)

* **2A state overview.** S0 purpose, inputs to seal, and downstream deliverables. 
* **Closed-world governance (concept).** Sealed universe, JSON-Schema authority, `parameter_hash` + `manifest_fingerprint`, and universal gates.
* **Progress map (where 2A fits).** Layer-1 open/locked status and 4A/4B overlay. 

*Use:* Downstream 2A states **must** resolve shapes from Schema anchors, **must** resolve IDs→paths/partitions via the Dictionary, and **must** treat Registry entries as the existence/licensing authority; S0 binds only the gate and the sealed manifest that fixes `manifest_fingerprint` (identity).

---
