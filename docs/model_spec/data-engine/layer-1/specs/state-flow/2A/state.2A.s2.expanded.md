# State 2A.S2 — Overrides & finalisation

## 1. Document metadata & status **(Binding)**

**Title:** Layer-1 · Segment 2A · State-2 — Overrides & finalisation
**Short name:** 2A.S2 “Overrides”
**Layer/Segment/State:** L1 / 2A (Civil Time) / S2
**Doc ID:** `layer1/2A/state-2`
**Version (semver):** `v1.0.0-alpha` *(advance per change control)*
**Status:** `draft | alpha | frozen` *(normative at ≥ `alpha`; semantics locked at `frozen`)*
**Owners:** Design Authority (DA): ‹name› • Review Authority (RA): ‹name›
**Effective date:** ‹YYYY-MM-DD›
**Canonical location:** ‹repo path to this spec file›

**Normative cross-references (pointers only):**

* **2A.S0 Gate & Sealed Inputs:** `schemas.2A.yaml#/validation/s0_gate_receipt_v1` (receipt for target `manifest_fingerprint`).
* **Upstream plan (S1):** `schemas.2A.yaml#/plan/s1_tz_lookup` (input).
* **Policy:** `schemas.2A.yaml#/policy/tz_overrides_v1` (governed overrides; precedence site » mcc » country).
* **Egress (this state):** `schemas.2A.yaml#/egress/site_timezones`.
* **Catalogue & registry:** Dataset Dictionary entries for `s1_tz_lookup`, `site_timezones`, `tz_overrides`; Artefact Registry stanzas for same.
* **Layer-1 governance:** Identity & Path Law (path↔embed equality), Gate Law (“No PASS → No Read”), Numeric Policy, Hashing/Fingerprint Law.

**Conformance & interpretation:**

* Sections marked **Binding** are normative; **Informative** sections do not create obligations.
* Keywords **MUST/SHALL/SHOULD/MAY** are as defined in RFC 2119/8174.
* This is a **design specification**: it defines required behaviours, identities, inputs/outputs, and inter-state contracts; it does **not** prescribe implementations or pseudocode.

**Change log (summary):**

* `v1.0.0-alpha` - Initial specification for 2A.S2 (Overrides & finalisation). Subsequent edits follow §13 Change Control.

---

### Contract Card (S2) - inputs/outputs/authorities

**Inputs (authoritative; see Section 3.2 for full list):**
* `s0_gate_receipt_2A` - scope: FINGERPRINT_SCOPED; source: 2A.S0
* `s1_tz_lookup` - scope: SEED+FINGERPRINT; source: 2A.S1
* `tz_overrides` - scope: UNPARTITIONED (sealed config); sealed_inputs: required
* `tz_world_2025a` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required
* `merchant_mcc_map` - scope: VERSION_SCOPED (sealed reference); sealed_inputs: optional (MCC overrides only)

**Authority / ordering:**
* S2 emits order-free egress; no new order authority is created.

**Outputs:**
* `site_timezones` - scope: EGRESS_SCOPED; gate emitted: none

**Sealing / identity:**
* External inputs (ingress/reference/1B egress/2A policy) MUST appear in `sealed_inputs_2A` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or invalid overrides -> abort; no outputs published.

## 2. Purpose & scope **(Binding)**

**Intent.** Convert S1’s geometry-only `tzid_provisional` into the **final per-site IANA `tzid`** by applying the governed **`tz_overrides`** policy. Record provenance for every site.

**Objectives (normative).** 2A.S2 SHALL:

* **Assert eligibility:** Rely on the **2A.S0 gate receipt** for the target `manifest_fingerprint` before referencing any inputs.
* **Consume sealed inputs only:** Read **`s1_tz_lookup`** for the same `(seed, manifest_fingerprint)` and the sealed **`tz_overrides`** policy; no other sources are permitted.
* **Apply precedence deterministically:** Where policy applies, select **at most one** active override according to **site » mcc » country**; otherwise retain the polygon result.
* **Define “active” override:** An override is **active** iff its `expiry_yyyy_mm_dd` is **null** or **≥ the date of S0.receipt.verified_at_utc** (no wall-clock dependence).
* **Bind targets:**
  • `site` → the site key `(merchant_id, legal_country_iso, site_order)`;
  • `mcc` → merchant’s MCC (from the sealed mapping if used by the programme);
  • `country` → `legal_country_iso`.
* **Validate tzids:** Any override `tzid` MUST conform to the layer `iana_tzid` domain (and MAY be required to appear in the sealed `tz_world` release per validators).
* **Emit final egress:** Write **`site_timezones`** under `[seed, manifest_fingerprint]`, setting `tzid`, `tzid_source ∈ {polygon, override}`, and `override_scope` when overridden; carry forward S1 `nudge_*` unchanged.
* **Remain RNG-free & idempotent.**

**In scope.**

* Deterministic selection and application of a single highest-precedence **active** override per site.
* 1:1 row coverage with `s1_tz_lookup` for the same `(seed, manifest_fingerprint)`.
* Provenance capture (`tzid_source`, `override_scope`) and conformance checks for override `tzid`.

**Out of scope.**

* Building timetables or evaluating tzdb rules (S3).
* DST legality/folds reporting (S4).
* Validation bundle/flag for Segment 2A (S5).
* Any mutation of input datasets or reliance on non-sealed assets.

**Interfaces (design relationship).**

* **Upstream:** Consumes S0 receipt (gate), `s1_tz_lookup` (S1 output), and `tz_overrides` (policy), all for the target `manifest_fingerprint`.
* **Downstream:** `site_timezones` is the egress consumed by later 2A states and other segments under **No PASS → No Read** at segment level.

**Completion semantics.** S2 is complete when `site_timezones` is published for the selected `(seed, manifest_fingerprint)` partition, schema-valid, path↔embed equality holds, and each input site has exactly one final `tzid` with correct provenance.

---

## 3. Preconditions & sealed inputs **(Binding)**

### 3.1 Preconditions

S2 SHALL begin only when:

* **Gate verified.** A valid **2A.S0 gate receipt** exists and schema-validates for the target `manifest_fingerprint`. S2 relies on this for read permission; it does not re-hash bundles. 
* **Run identity fixed.** The pair **`(seed, manifest_fingerprint)`** is selected and constant for the run.
* **Authorities addressable.** The 2A schema pack, Dataset Dictionary, and Artefact Registry entries required below resolve without placeholders. 
* **Posture.** S2 is **RNG-free** and deterministic.

### 3.2 Sealed inputs (consumed in S2)

S2 **consumes only** the following inputs. All MUST be resolved **by ID via the Dataset Dictionary** (no literal paths) and be authorised by the Registry.

1. **`s1_tz_lookup` (from S1) — partitioned by `[seed, manifest_fingerprint]`**
   *Role:* provides one provisional row per site (including any `nudge_*`).
   *Catalogue:* `data/layer1/2A/s1_tz_lookup/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`.
   *Shape:* `schemas.2A.yaml#/plan/s1_tz_lookup`. 

2. **`tz_overrides` (policy) — sealed in S0**
   *Role:* governed list of override directives; precedence **site » mcc » country**.
   *Catalogue:* `config/layer1/2A/timezone/tz_overrides.yaml`.
   *Shape:* `schemas.2A.yaml#/policy/tz_overrides_v1`. 

3. **`tz_world` polygons (ingress; sealed in S0)**
   *Role:* authoritative tzid domain for membership validation of final output.
   *Catalogue:* `reference/spatial/tz_world/<release>/tz_world.parquet`.
   *Shape:* `schemas.ingress.layer1.yaml#/tz_world_2025a`.

4. **(Optional) Merchant→MCC mapping (if programme uses MCC-scope overrides)**
   *Role:* authoritative mapping to evaluate `mcc`-scope overrides.
   *Catalogue/Shape:* `merchant_mcc_map` (schema `schemas.ingress.layer1.yaml#/merchant_mcc_map`); MUST be present in the sealed manifest if MCC overrides are to be applied in this run.

> *Context for downstream:* S2 emits **`site_timezones`** as egress under `[seed, manifest_fingerprint]` (catalogue and anchor already defined), but this is an **output**, not a precondition.

### 3.3 Binding constraints on input use

* **Same-identity constraint.** Any fingerprinted input S2 reads (e.g., `s1_tz_lookup`) **MUST** match the S0 `manifest_fingerprint`; `s1_tz_lookup` **MUST** be read exactly from this run’s `(seed, manifest_fingerprint)` partition. 
* **Dictionary-only resolution.** Inputs SHALL be resolved by **ID → path/partitions/format** via the Dataset Dictionary; literal/relative paths are **forbidden**. 
* **Shape authority.** JSON-Schema anchors are the **sole** shape authority; S2 SHALL NOT assume undeclared columns or enums. 
* **Override “active” cut-off.** For S2, an override is **active** iff `expiry_yyyy_mm_dd` is **null** or **≥** the **date component** of `verified_at_utc` in the S0 receipt (no wall-clock dependence). 
* **MCC scope gating.** MCC-scope overrides MAY be applied **only** if an authoritative merchant→MCC mapping is present in the sealed inputs for this run; otherwise MCC-scope entries are **not active** for S2.
* **Non-mutation.** S2 SHALL NOT mutate or persist any input datasets; it emits only `site_timezones`. 

### 3.4 Null/empty allowances

* **Overrides may be empty.** `tz_overrides` MAY be an empty list; when empty, S2 SHALL pass through the S1 `tzid_provisional` for all sites (provenance still recorded as `polygon`). 
* **MCC mapping optional.** If no MCC mapping is sealed, S2 SHALL ignore MCC-scope entries; **site** and **country** scopes remain eligible.
* **No other inputs.** Datasets not enumerated in §3.2 are **out of scope** for S2 and SHALL NOT be read.

---

## 4. Inputs & authority boundaries **(Binding)**

### 4.1 Authority model (normative)

* **Shape authority:** JSON-Schema anchors fix columns, domains, PK/partitions, and strictness. *(S2 relies on anchors for `s1_tz_lookup`, `tz_overrides_v1`, and `site_timezones`.)* 
* **Catalogue authority:** The Dataset Dictionary fixes **IDs → canonical paths/partitions/format**; S2 MUST resolve inputs by ID (no literal paths). 
* **Existence/licensing authority:** The Artefact Registry declares presence/licence/retention and dataset roles/dependencies. 
* **Precedence on disputes:** **Schema › Dictionary › Registry** (Schema wins for shape; Dictionary wins for path/partitions).
* **Gate law:** Read permission flows from the **2A.S0 receipt** for the target `manifest_fingerprint`; S2 does **not** re-hash upstream bundles. *(Receipt is catalogued and anchored in 2A.)* 

### 4.2 Per-input boundaries

1. **`s1_tz_lookup` (required)**

   * **Shape:** `schemas.2A.yaml#/plan/s1_tz_lookup` (PK `[merchant_id, legal_country_iso, site_order]`; partitions `[seed, manifest_fingerprint]`). 
   * **Catalogue:** `data/layer1/2A/s1_tz_lookup/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (format Parquet; writer order `[merchant_id, legal_country_iso, site_order]`). 
   * **Registry:** plan dataset; depends on `site_locations`, `tz_world_2025a`, and `tz_nudge`. 
   * **Boundary:** S2 SHALL read exactly the run’s `(seed, manifest_fingerprint)` partition; it SHALL NOT mutate or re-write S1. 

2. **`tz_overrides` policy (required)**

   * **Shape:** `schemas.2A.yaml#/policy/tz_overrides_v1` (scope∈{site,mcc,country}, `tzid`, optional expiry). 
   * **Catalogue:** `config/layer1/2A/timezone/tz_overrides.yaml`. 
   * **Registry:** policy/config entry with precedence note (**site » mcc » country**). 
   * **Boundary:** S2 SHALL apply **at most one** active override per site using the precedence above; non-active or malformed entries are ignored (validators will raise errors where specified).

3. **`tz_world` polygons (read-only; membership validation only)**

   * **Shape:** `schemas.ingress.layer1.yaml#/tz_world_2025a`.
   * **Boundary:** S2 MAY read tzid values to validate final output membership; no spatial work or geometry access is performed in S2.

4. **2A.S0 gate receipt (evidence)**

   * **Shape:** `schemas.2A.yaml#/validation/s0_gate_receipt_v1`.
   * **Catalogue:** manifest_fingerprint-scoped receipt under `…/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/…`.
   * **Boundary:** S2 SHALL only verify presence and manifest_fingerprint match; it SHALL NOT re-compute bundle hashes. 

5. **(Optional) Merchant→MCC mapping** *(only if MCC-scope overrides are in use)*

   * **Shape/Catalogue:** `merchant_mcc_map` (schema `schemas.ingress.layer1.yaml#/merchant_mcc_map`); MUST be present in the sealed manifest if MCC overrides are to be evaluated; otherwise MCC-scope entries are not active in this run.

> *Note:* `site_timezones` is the **output** of S2, not an input; its anchor and catalogue family are fixed for downstream.

### 4.3 Validation responsibilities (S2 scope)

* **Receipt check:** S0 receipt exists and matches the target `manifest_fingerprint`. 
* **Dictionary resolution:** IDs for `s1_tz_lookup` and `tz_overrides` resolve to canonical paths/partitions/format; S2 MUST NOT use literal paths.
* **Partition discipline:** Only the run’s `(seed, manifest_fingerprint)` is read from S1. 
* **Policy minima:** `tz_overrides` schema-valid; precedence enforced; expiry semantics honoured; any applied `tzid` conforms to `iana_tzid` **and belongs to the sealed `tz_world` release’s tzid domain** (membership check; read-only). 

### 4.4 Prohibitions

S2 SHALL NOT: read datasets beyond §4.2; invent tzids not present in policy or S1; apply more than one override per site; parse tzdb rules (S3 scope); mutate inputs; or rely on non-catalogue paths.

---

## 5. Outputs (datasets) & identity **(Binding)**

### 5.1 Primary deliverable — `site_timezones` (egress)

**Role.** Final per-site IANA `tzid` with provenance after applying S2 overrides. Order-free egress for Layer-1. 

**Shape (authority).** `schemas.2A.yaml#/egress/site_timezones` (**columns_strict: true**) fixes:

* **PK:** `[merchant_id, legal_country_iso, site_order]`
* **Partitions:** `[seed, manifest_fingerprint]`
* **Required columns:** `tzid`, `tzid_source ∈ {polygon, override}`, optional `override_scope ∈ {site,mcc,country}`, carry-through `nudge_lat_deg`, `nudge_lon_deg`, and `created_utc`. 

**Catalogue (Dictionary).**
`data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` with **partitioning** `[seed, manifest_fingerprint]`, **ordering** `[merchant_id, legal_country_iso, site_order]`, **format** Parquet, **final_in_layer: true**.

**Registry (existence/licensing).**
Registered as output; **dependencies:** `s1_tz_lookup`, `tz_overrides`; **schema:** `#/egress/site_timezones`. 

### 5.2 Identity & path law

* **Selection identity:** exactly one `(seed, manifest_fingerprint)` per publish.
* **Path↔embed equality:** where lineage appears in both **path tokens** and **row fields**, values **MUST** byte-equal (Layer-1 Identity & Path Law).
* **Single-writer & immutability:** one successful publish per `(seed, manifest_fingerprint)`; any re-emit **MUST** be byte-identical or **ABORT**. (Registry posture mirrors other 2A datasets.) 

### 5.3 Writer discipline

* **Writer order:** files SHOULD be written in catalogue order `[merchant_id, legal_country_iso, site_order]`; file order is non-authoritative. 

### 5.4 Format, licensing & retention (by catalogue/registry)

* **Format:** Parquet.
* **Licence/TTL:** Proprietary-Internal; typical retention 365 days. (Dictionary/Registry are authorities for these attributes.) 

**Binding effect.** Downstream consumers **MUST** select `site_timezones` by `(seed, manifest_fingerprint)`, resolve via the **Dataset Dictionary**, and verify schema validity before read. Segment-level **No PASS → No Read** for 2A egress is enforced at S5 (validation bundle/flag), not by S2.

---

## 6. Dataset shapes & schema anchors **(Binding)**

**Shape authority.** JSON-Schema anchors are the **sole** source of truth for columns, domains, PK/partitions, sort discipline, and strictness. This section enumerates the anchors S2 binds to and the catalogue/registry entries that reference them. 

### 6.1 Output table — `site_timezones` (egress)

* **ID → Schema:** `schemas.2A.yaml#/egress/site_timezones` (**columns_strict: true**). The anchor fixes **PK** `[merchant_id, legal_country_iso, site_order]`, **partitions** `[seed, manifest_fingerprint]`, writer **sort** `[merchant_id, legal_country_iso, site_order]`, and required columns:
  `tzid` (layer `iana_tzid`), `tzid_source ∈ {polygon, override}`, optional `override_scope ∈ {site, mcc, country}`, carry-through `nudge_lat_deg`, `nudge_lon_deg`, `created_utc` (`rfc3339_micros`). 
* **Dictionary/Registry binding:** Path family
  `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` with **partitions** `[seed, manifest_fingerprint]`; registered as **egress** with dependencies on `s1_tz_lookup` and `tz_overrides`.

### 6.2 Referenced inputs (read-only in S2)

* **`s1_tz_lookup` (S1 plan):** `schemas.2A.yaml#/plan/s1_tz_lookup` (PK `[merchant_id, legal_country_iso, site_order]`; partitions `[seed, manifest_fingerprint]`; includes `tzid_provisional` and optional `nudge_*`). Catalogue path
  `data/layer1/2A/s1_tz_lookup/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`. Registry classifies it as a **plan** dataset.
* **`tz_overrides` (policy):** `schemas.2A.yaml#/policy/tz_overrides_v1` (scope∈{site,mcc,country}, `tzid`, optional expiry). Catalogue path `config/layer1/2A/timezone/tz_overrides.yaml`; registry lists it under **policy/config**.
* **`tz_world_<release>` (ingress tz polygons; read-only membership source):** `schemas.ingress.layer1.yaml#/tz_world_2025a`. Catalogue path `reference/spatial/tz_world/<release>/tz_world.parquet`.
* **(Optional, for programme where needed) Merchant→MCC mapping:** `merchant_mcc_map` dataset (schema `schemas.ingress.layer1.yaml#/merchant_mcc_map`); MUST be present in the sealed manifest if MCC-scope overrides are to be evaluated; otherwise MCC-scope entries are treated as not active.

### 6.3 Identity & partition posture (binding)

* **Output partitions:** `site_timezones` is partitioned by **`[seed, manifest_fingerprint]`**; the **Dataset Dictionary** governs the path family; **path↔embed equality** MUST hold where lineage appears in rows. 
* **Single-writer & immutability:** One successful publish per `(seed, manifest_fingerprint)`; re-emits must be **byte-identical** or abort (registry posture). 

### 6.4 Binding constraints (shape-level, S2)

* **Strict columns.** `site_timezones` is **columns_strict: true**; undeclared columns are invalid. 
* **Domain validity.** `tzid` MUST conform to layer `$defs.iana_tzid`; `tzid_source` and `override_scope` MUST take only the enumerated values defined by the anchor. 
* **Carry-through fields.** If present in S1, `nudge_lat_deg`/`nudge_lon_deg` are carried through unchanged into `site_timezones`. (The anchor permits nulls.) 

**Result.** With these anchors and catalogue bindings, S2’s single deliverable `site_timezones` is fully specified; inputs are pinned to their authoritative schemas; and identity/partition discipline matches the Dictionary and Registry contracts.

---

## 7. Deterministic behaviour (RNG-free) **(Binding)**

### 7.1 Posture & scope

* S2 is **strictly deterministic** and **RNG-free**.
* Read permission derives from the **2A.S0 gate receipt** for the target `manifest_fingerprint`; S2 does **not** re-hash bundles.
* Inputs are resolved **only via the Dataset Dictionary**; literal/relative paths are forbidden.
* Output is the single egress **`site_timezones`** under `[seed, manifest_fingerprint]`.

### 7.2 Canonical order of operations

1. **Verify gate.** Assert presence & schema validity of the 2A.S0 receipt for the target `manifest_fingerprint`.
2. **Resolve inputs.**

   * Select `s1_tz_lookup` **exactly** at `[seed, manifest_fingerprint]`.
   * Bind the sealed `tz_overrides` policy.
   * Bind the sealed `tz_world` release for membership validation.
   * If MCC-scope overrides exist, bind the **authoritative merchant→MCC mapping** (must be present in the sealed inputs for this run); otherwise MCC-scope entries are **not active**.
3. **Fix timestamps.** For determinism, set `created_utc` in output rows to **S0.receipt.verified_at_utc** (observational fields must be a deterministic function of sealed inputs).

### 7.3 Override selection semantics (per-site)

For each row in `s1_tz_lookup`:

a) **Define “active”.** An override is **active** iff `expiry_yyyy_mm_dd` is **null** or **≥** the **date** of `S0.receipt.verified_at_utc`. (No wall-clock dependence.)

b) **Compute candidate sets (by scope).**

* **site:** `scope=site` and `target == (merchant_id, legal_country_iso, site_order)`
* **mcc:** `scope=mcc` and `target == merchant_mcc` (only if MCC mapping is sealed)
* **country:** `scope=country` and `target == legal_country_iso`

c) **Uniqueness within scope.** If **>1 active** override exists **within any single scope** for the site, raise **OVERRIDES_DUPLICATE_SCOPE_TARGET (Abort)**.

d) **Precedence.** Choose the **highest-precedence** non-empty set in the order **site » mcc » country**. If all are empty, **no override applies**.

e) **Validate final tzid.** The chosen tzid (override or polygon pass-through) **MUST**:

* conform to layer `$defs.iana_tzid`; and
* belong to the sealed `tz_world` release’s tzid domain (membership check).
  Violations raise **UNKNOWN_TZID** (domain) or **TZID_NOT_IN_TZ_WORLD** (membership) as per §9.

f) **Finalise assignment & provenance.**

* If an override is selected and its `tzid` **differs** from `tzid_provisional`, set `tzid = override.tzid`, `tzid_source = "override"`, and `override_scope ∈ {site,mcc,country}`.
* Otherwise (no override, or override equals provisional), set `tzid = tzid_provisional`, `tzid_source = "polygon"`, and leave `override_scope = null`.
* Carry through `nudge_lat_deg` / `nudge_lon_deg` exactly as in S1.

### 7.4 Output emission (identity & immutability)

* Emit **`site_timezones`** to `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` with partitions `[seed, manifest_fingerprint]`.
* **Path↔embed equality** MUST hold wherever lineage appears in rows.
* **Single-writer, write-once** posture: re-emitting to an existing `(seed, manifest_fingerprint)` **MUST** be byte-identical; otherwise **ABORT**.

### 7.5 Prohibitions (non-behaviours)

S2 **SHALL NOT**:

* apply more than **one** override per site;
* treat MCC-scope overrides as active without a sealed MCC mapping;
* invent or synthesise tzids;
* modify any inputs (`s1_tz_lookup`, `tz_overrides`, MCC mapping);
* parse tzdb transition rules (S3 scope) or perform spatial work (S1 scope);
* read any dataset not enumerated in §3.

### 7.6 Idempotency

Given the same **S0 receipt**, **`s1_tz_lookup`** partition, **`tz_overrides`** policy (and MCC mapping, if used), S2 **SHALL** produce **byte-identical** `site_timezones`.
*(The requirement that `created_utc = S0.receipt.verified_at_utc` ensures determinism of observational fields.)*

---

## 8. Identity, partitions, ordering & merge discipline **(Binding)**

### 8.1 Identity tokens

* **Selection identity:** exactly one pair **`(seed, manifest_fingerprint)`** per publish of `site_timezones`.
* **No new tokens:** `parameter_hash` is recorded elsewhere in the programme but is **not** a partition for S2 egress.
* **Path↔embed equality:** wherever lineage appears both in **path tokens** and in **row fields**, values **MUST** byte-equal (Layer-1 Identity & Path Law). 

### 8.2 Partitions & path family

* **Dataset:** `site_timezones` →
  `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`.
* **Partitions (binding):** `[seed, manifest_fingerprint]` (no others). **Dictionary** is the catalogue authority for path/partitions/format.

### 8.3 Keys, uniqueness & coverage

* **Primary key (shape authority):** `[merchant_id, legal_country_iso, site_order]` (per schema anchor). 
* **Uniqueness & coverage:** exactly one output row per input site key from `s1_tz_lookup` in the selected `(seed, manifest_fingerprint)`; no duplicates, no omissions (validators enforce in §9). 

### 8.4 Writer order (discipline)

* **Writer sort (catalogue):** `[merchant_id, legal_country_iso, site_order]`.
* **File order is non-authoritative**—consumers MUST NOT infer semantics from file ordering. 

### 8.5 Merge & immutability

* **Write-once per `(seed, manifest_fingerprint)`.** Re-emitting into an existing partition **MUST** be **byte-identical**; otherwise the run **MUST ABORT**.
* **Publish posture:** stage → fsync → single **atomic move** into the identity partition (mirrors Layer-1 egress posture). 

### 8.6 Concurrency & conflict detection

* **Single-writer per identity.** Concurrent writes targeting the same `(seed, manifest_fingerprint)` are not permitted; the presence of any artefact under that partition constitutes a **conflict** and S2 **MUST** abort. (Registry classifies `site_timezones` as an egress with write-once semantics.) 

### 8.7 Discovery & selection (downstream contract)

* Downstream states and segments **MUST** select `site_timezones` by **`(seed, manifest_fingerprint)`**, resolve via the **Dataset Dictionary**, and verify schema validity before read. (This egress is marked **final_in_layer: true** in the catalogue.) 

### 8.8 Retention, licensing & relocation

* **Retention/TTL & licence** are governed by Dictionary/Registry (typical retention: 365 days; Proprietary-Internal). 
* **Relocation** that preserves the Dictionary path family and partitioning is non-breaking; any change that alters partition keys or path tokens is **breaking** and out of scope for S2.

**Effect.** These constraints make `site_timezones` uniquely addressable by `(seed, manifest_fingerprint)`, immutable once published, and safely consumable without ambiguity—**Schema** as shape authority, **Dictionary** as catalogue authority, **Registry** for existence/licensing/retention.

---

## 9. Acceptance criteria (validators) **(Binding)**

**PASS definition.** A run of 2A.S2 is **ACCEPTED** iff **all** mandatory validators below pass. Any **Abort** failure causes the run to **FAIL** and no egress from §5 may be published. **Warn** does not block emission.

### 9.1 Gate & input resolution (mandatory)

**V-01 — S0 receipt present (Abort).** A valid **2A.S0 gate receipt** exists and schema-validates for the target `manifest_fingerprint`.
**V-02 — Dictionary resolution (Abort).** Inputs resolve by **ID** via the Dataset Dictionary (no literal paths): `s1_tz_lookup` `[seed, manifest_fingerprint]`, `tz_overrides`, and `tz_world_<release>` (and merchant→MCC mapping if MCC scope is used).
**V-03 — Partition selection (Abort).** `s1_tz_lookup` is read **only** from the run’s `(seed, manifest_fingerprint)` partition.

### 9.2 Policy readiness & precedence (mandatory)

**V-04 — Overrides schema validity (Abort).** `tz_overrides` validates (scope ∈ {site,mcc,country}; required fields present).
**V-05 — Duplicate scope/target ban (Abort).** Within `tz_overrides`, there is **at most one** active entry per `(scope, target)` under the S0 cut-off date.
**V-06 — MCC gating (Abort).** If any applied override has `override_scope="mcc"`, an authoritative merchant→MCC mapping is sealed **and** contains a mapping for that site’s merchant; otherwise MCC-scope overrides are **not active**.
**V-07 — Active override expiry (Abort).** For any output row with `tzid_source="override"`, there **exists** a matching override row (by scope/target) whose `expiry_yyyy_mm_dd` is **null** or **≥** the **date** of `S0.receipt.verified_at_utc`.

### 9.3 Output shape, identity & determinism (mandatory)

**V-08 — Schema validity (Abort).** `site_timezones` validates against `schemas.2A.yaml#/egress/site_timezones` (**columns_strict: true**).
**V-09 — Path↔embed equality (Abort).** Output partition tokens `[seed, manifest_fingerprint]` **byte-equal** any embedded lineage fields.
**V-10 — Write-once semantics (Abort).** If the target `(seed, manifest_fingerprint)` partition already exists, newly written bytes MUST be **byte-identical**; otherwise **ABORT**.
**V-11 — Deterministic `created_utc` (Abort).** `created_utc` equals **`S0.receipt.verified_at_utc`** in every emitted row.

### 9.4 Coverage, uniqueness, provenance & value checks (mandatory)

**V-12 — 1:1 coverage (Abort).** Exactly one `site_timezones` row exists for each `s1_tz_lookup` row in the selected `(seed, manifest_fingerprint)`; no drops/extras.
**V-13 — PK uniqueness (Abort).** No duplicate `[merchant_id, legal_country_iso, site_order]` in `site_timezones`.
**V-14 — Non-null tzid (Abort).** Every output row has non-null `tzid`.
**V-15 — tzid domain (Abort).** Every `tzid` conforms to the layer-wide **`iana_tzid`** domain.
**V-15b — tzid membership (Abort).** Every `tzid` appears in the sealed `tz_world` release (compare against `schemas.ingress.layer1.yaml#/tz_world_2025a.tzid`).
**V-16 — Provenance coherence (Abort).**
  • If `tzid_source="override"`, then `override_scope ∈ {site,mcc,country}`;
  • If `tzid_source="polygon"`, then `override_scope` **is null**.
**V-17 — Override has effect (Abort).** If `tzid_source="override"`, then `tzid ≠ tzid_provisional` from the matching `s1_tz_lookup` row. (If equal, treat as polygon; reporting override is invalid.)
**V-18 — Nudge carry-through (Abort).** For each site key, `(nudge_lat_deg, nudge_lon_deg)` in `site_timezones` equals the pair in `s1_tz_lookup`. The pair is either **both null** or **both set**.

### 9.5 Catalogue discipline (advisory)

**V-19 — Writer order (Warn).** Files are written in catalogue order `[merchant_id, legal_country_iso, site_order]` (file order is non-authoritative).

### 9.6 Outcome semantics

* **PASS:** V-01…V-18 pass; V-19 may warn.
* **FAIL:** Any **Abort** validator fails.
* **WARN:** Only non-blocking advisories (e.g., V-19) fail; they MUST surface in the run-report when §11 is introduced.

### 9.7 (For §10) Validator → error-code mapping (normative)

| Validator                        | Error code(s)                                                                  |
|----------------------------------|--------------------------------------------------------------------------------|
| V-01 S0 receipt present          | **2A-S2-001 MISSING_S0_RECEIPT**                                               |
| V-02 Dictionary resolution       | **2A-S2-010 INPUT_RESOLUTION_FAILED**                                          |
| V-03 Partition selection         | **2A-S2-011 WRONG_PARTITION_SELECTED**                                         |
| V-04 Overrides schema validity   | **2A-S2-020 OVERRIDES_SCHEMA_INVALID**                                         |
| V-05 Duplicate scope/target ban  | **2A-S2-021 OVERRIDES_DUPLICATE_SCOPE_TARGET**                                 |
| V-06 MCC gating                  | **2A-S2-022 MCC_MAPPING_MISSING** · **2A-S2-023 MCC_TARGET_UNKNOWN**           |
| V-07 Active override expiry      | **2A-S2-024 OVERRIDE_EXPIRED**                                                 |
| V-08 Schema validity (egress)    | **2A-S2-030 OUTPUT_SCHEMA_INVALID**                                            |
| V-09 Path↔embed equality         | **2A-S2-040 PATH_EMBED_MISMATCH**                                              |
| V-10 Write-once semantics        | **2A-S2-041 IMMUTABLE_PARTITION_OVERWRITE**                                    |
| V-11 Deterministic `created_utc` | **2A-S2-042 CREATED_UTC_NONDETERMINISTIC**                                     |
| V-12 1:1 coverage                | **2A-S2-050 COVERAGE_MISMATCH**                                                |
| V-13 PK uniqueness               | **2A-S2-051 PRIMARY_KEY_DUPLICATE**                                            |
| V-14 Non-null tzid               | **2A-S2-052 NULL_TZID**                                                        |
| V-15 tzid domain                 | **2A-S2-053 UNKNOWN_TZID**                                                     |
| V-15b tzid membership            | **2A-S2-057 TZID_NOT_IN_TZ_WORLD**                                             |
| V-16 Provenance coherence        | **2A-S2-054 PROVENANCE_INVALID**                                               |
| V-17 Override has effect         | **2A-S2-055 OVERRIDE_NO_EFFECT**                                               |
| V-18 Nudge carry-through         | **2A-S2-056 NUDGE_CARRY_MISMATCH**                                             |
| V-19 Writer order (Warn)         | **2A-S2-070 WRITER_ORDER_NONCOMPLIANT**                                        |
| — Authority conflict (any stage) | **2A-S2-080 AUTHORITY_CONFLICT** *(Schema › Dictionary › Registry precedence)* |

*Authorities:* Output shape and PK/partitions are owned by the S2 anchor; catalogue paths/partitions/order by the 2A Dictionary; presence/licensing by the 2A Registry; gate evidence by the S0 receipt.

---

## 10. Failure modes & canonical error codes **(Binding)**

**Code format.** `2A-S2-XXX NAME` (stable identifiers).
**Effect classes.** `Abort` = run MUST fail and emit nothing; `Warn` = non-blocking, MUST be surfaced in the run-report.
**Required context on raise.** Include: `manifest_fingerprint`, `seed`, and—where applicable—`dataset_id`, `catalog_path`, `scope`, `target`, `tzid`, and the **site key** `(merchant_id, legal_country_iso, site_order)`.

### 10.1 Gate & input resolution

* **2A-S2-001 MISSING_S0_RECEIPT (Abort)** — No valid 2A.S0 receipt for the target `manifest_fingerprint`.
  *Remediation:* publish/repair S0; rerun S2.
* **2A-S2-010 INPUT_RESOLUTION_FAILED (Abort)** — `s1_tz_lookup`, `tz_overrides` (or MCC mapping, if used) failed **Dictionary** resolution or Registry authorisation.
  *Remediation:* fix Dictionary/Registry entries or IDs; rerun.
* **2A-S2-011 WRONG_PARTITION_SELECTED (Abort)** — `s1_tz_lookup` not read **exactly** from `(seed, manifest_fingerprint)`.
  *Remediation:* select the exact partition; rerun.

### 10.2 Policy readiness & precedence

* **2A-S2-020 OVERRIDES_SCHEMA_INVALID (Abort)** — `tz_overrides` fails its schema (missing/invalid fields; bad scope).
  *Remediation:* fix policy file to the `tz_overrides_v1` anchor; rerun.
* **2A-S2-021 OVERRIDES_DUPLICATE_SCOPE_TARGET (Abort)** — More than one **active** override exists for the same `(scope, target)` under the S0 cut-off date.
  *Remediation:* consolidate to a single active row or expire duplicates.
* **2A-S2-022 MCC_MAPPING_MISSING (Abort)** — An MCC-scope override would apply but no authoritative merchant→MCC mapping is sealed for this run.
  *Remediation:* seal the mapping in S0 or remove MCC overrides.
* **2A-S2-023 MCC_TARGET_UNKNOWN (Abort)** — MCC-scope override targets a merchant without a mapping entry.
  *Remediation:* complete the mapping or remove the override.
* **2A-S2-024 OVERRIDE_EXPIRED (Abort)** — Applied override’s `expiry_yyyy_mm_dd` is **<** S0 receipt date.
  *Remediation:* update/renew policy date or treat as non-active.

### 10.3 Output shape, identity & determinism

* **2A-S2-030 OUTPUT_SCHEMA_INVALID (Abort)** — `site_timezones` fails its schema (columns_strict, PK/types/enums).
  *Remediation:* emit schema-valid rows only.
* **2A-S2-040 PATH_EMBED_MISMATCH (Abort)** — Embedded lineage tokens don’t byte-equal the `seed`/`manifest_fingerprint` path tokens.
  *Remediation:* correct identity fields or path; rerun.
* **2A-S2-041 IMMUTABLE_PARTITION_OVERWRITE (Abort)** — Attempt to write non-identical bytes into an existing `(seed, manifest_fingerprint)` partition.
  *Remediation:* either reproduce byte-identical output or target a new identity.
* **2A-S2-042 CREATED_UTC_NONDETERMINISTIC (Abort)** — `created_utc` not equal to **S0.receipt.verified_at_utc**.
  *Remediation:* set to the receipt timestamp; rerun.

### 10.4 Coverage, uniqueness, provenance & value checks

* **2A-S2-050 COVERAGE_MISMATCH (Abort)** — Not **exactly one** output row per `s1_tz_lookup` row for the selected `(seed, manifest_fingerprint)` (missing or extra rows).
  *Remediation:* ensure 1:1 projection; rerun.
* **2A-S2-051 PRIMARY_KEY_DUPLICATE (Abort)** — Duplicate `[merchant_id, legal_country_iso, site_order]` in `site_timezones`.
  *Remediation:* deduplicate; rerun.
* **2A-S2-052 NULL_TZID (Abort)** — Any output row has `tzid = null`.
  *Remediation:* retain polygon result or provide a valid override; rerun.
* **2A-S2-053 UNKNOWN_TZID (Abort)** — `tzid` fails the layer `iana_tzid` domain.
  *Remediation:* correct the tzid; rerun.
* **2A-S2-057 TZID_NOT_IN_TZ_WORLD (Abort)** — `tzid` not found in the sealed `tz_world` domain for this manifest_fingerprint.
  *Remediation:* correct tzid or update the sealed `tz_world` release; rerun.
* **2A-S2-054 PROVENANCE_INVALID (Abort)** — Inconsistent provenance:
  `tzid_source="override"` but `override_scope ∉ {site,mcc,country}`, or
  `tzid_source="polygon"` but `override_scope ≠ null`.
  *Remediation:* set coherent provenance fields; rerun.
* **2A-S2-055 OVERRIDE_NO_EFFECT (Abort)** — `tzid_source="override"` but `tzid == tzid_provisional`.
  *Remediation:* mark as polygon if identical, or remove redundant override.
* **2A-S2-056 NUDGE_CARRY_MISMATCH (Abort)** — `(nudge_lat_deg, nudge_lon_deg)` don’t exactly match S1 for the same site key (pair rule violated).
  *Remediation:* carry through both fields unchanged (both null or both set).

### 10.5 Catalogue discipline (advisory)

* **2A-S2-070 WRITER_ORDER_NONCOMPLIANT (Warn)** — Files not written in catalogue order `[merchant_id, legal_country_iso, site_order]` (file order is non-authoritative).
  *Remediation:* align writer sort; advisory only.

### 10.6 Authority conflict (resolution rule)

* **2A-S2-080 AUTHORITY_CONFLICT (Abort)** — Irreconcilable disagreement among **Schema, Dictionary, Registry** for the same asset after applying precedence (**Schema › Dictionary › Registry**).
  *Remediation:* fix the lower-precedence authority (or the schema if wrong), then rerun.

> The validator → code mapping in §9.7 is **normative**. New failure conditions introduced by future revisions MUST allocate **new codes** (append-only) and MUST NOT repurpose existing identifiers.

---

## 11. Observability & run-report **(Binding)**

### 11.1 Scope & posture

* **Purpose.** Surface auditable evidence of S2’s gate verification, policy application (overrides), and final egress publish.
* **Not identity-bearing.** The run-report does **not** affect dataset identity or gates.
* **One per run.** Exactly one report per attempted S2 run (success or failure).

---

### 11.2 Run-report artefact (normative content)

A single UTF-8 JSON object **SHALL** be written for the run with at least the fields below. Missing required fields are **Warn** (programme policy may escalate).

**Top level (run header):**

* `segment : "2A"`
* `state : "S2"`
* `status : "pass" | "fail"`
* `manifest_fingerprint : hex64`
* `seed : uint64`
* `started_utc, finished_utc : rfc3339_micros`
* `durations : { wall_ms : uint64 }`

**Gate & inputs:**

* `s0.receipt_path : string` — Dictionary path to verified 2A.S0 receipt
* `s0.verified_at_utc : rfc3339_micros`
* `inputs.s1_tz_lookup.path : string` — Dictionary path for the selected `(seed, manifest_fingerprint)`
* `inputs.tz_overrides.semver : string`
* `inputs.tz_overrides.sha256_digest : hex64`
* `inputs.mcc_mapping.id : string|null` — present iff MCC overrides are active
* `inputs.mcc_mapping.sha256_digest : hex64|null`

**Override & assignment summary:**

* `counts.sites_total : uint64` — rows read from `s1_tz_lookup`
* `counts.rows_emitted : uint64` — rows written to `site_timezones`
* `counts.overridden_total : uint64` — rows where `tzid_source="override"`
* `counts.overridden_by_scope : { site:uint64, mcc:uint64, country:uint64 }`
* `counts.override_no_effect : uint64` — rows where override tzid == provisional (EXPECT 0 on PASS)
* `counts.expired_skipped : uint64` — overrides seen but not active at the S0 cut-off
* `counts.dup_scope_target : uint64` — duplicate active `(scope,target)` entries (EXPECT 0 on PASS)
* `counts.mcc_targets_missing : uint64` — MCC overrides whose merchant lacked a mapping (EXPECT 0 on PASS)
* `counts.distinct_tzids : uint32`
* `checks.pk_duplicates : uint32` — duplicate PKs in output (EXPECT 0 on PASS)
* `checks.coverage_mismatch : uint32` — missing/excess rows vs input (EXPECT 0 on PASS)
* `checks.null_tzid : uint32` — (EXPECT 0 on PASS)
* `checks.unknown_tzid : uint32` — (EXPECT 0 on PASS)
* `checks.tzid_not_in_tz_world : uint32` — (EXPECT 0 on PASS)

**Outputs & identity:**

* `output.path : string` — Dictionary path to `site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
* `output.format : "parquet"`
* `output.created_utc : rfc3339_micros` — MUST equal `s0.verified_at_utc` (see §9 V-11)
* `catalogue.writer_order_ok : bool` — advisory (writer-order check)

**Diagnostics:**

* `warnings : array<error_code>` — any non-blocking codes raised (e.g., writer-order)
* `errors : array<{code, message, context}>` — on failure, list canonical codes with brief context

---

### 11.3 Structured logs (minimum event kinds)

S2 **SHALL** emit machine-parseable log records correlating to the report. Minimum events:

* **`GATE`** — start/end + result of S0 receipt verification; include `manifest_fingerprint`.
* **`INPUTS`** — resolved IDs/paths for `s1_tz_lookup`, `tz_overrides`, and MCC mapping (if any).
* **`OVERRIDES`** — totals (`overridden_total`, `overridden_by_scope`, `override_no_effect`, `expired_skipped`, `dup_scope_target`, `mcc_targets_missing`).
* **`VALIDATION`** — each validator outcome `{id, result, code?}` for §9.
* **`EMIT`** — successful publication of `site_timezones` with Dictionary path and `created_utc`.

Every record **SHALL** include: `timestamp_utc (rfc3339_micros)`, `segment`, `state`, `seed`, `manifest_fingerprint`, and `severity (INFO|WARN|ERROR)`.

---

### 11.4 Discoverability, retention & redaction

* **Discoverability.** The run-report path **MUST** be surfaced in CI/job metadata alongside the output Dictionary path.
* **Retention.** Programme policy governs report TTL; changes to retention **MUST NOT** alter dataset identity or partitions.
* **Redaction.** Reports/logs **MUST NOT** include per-row PII or raw site data; only counts, IDs, paths, digests, timestamps, and code identifiers are permitted.

---

## 12. Performance & scalability **(Informative)**

### 12.1 Workload shape

* **Reads:** one `s1_tz_lookup` partition for the selected `(seed, manifest_fingerprint)`, the sealed `tz_overrides` policy, and (if used) the sealed merchant→MCC mapping.
* **Compute:** per-site precedence evaluation (**site » mcc » country**), expiry check against the S0 receipt date, and tzid validity checks.
* **Writes:** one row per input site into `site_timezones` (carry-through of `nudge_*`, deterministic `created_utc`).

### 12.2 Complexity (N = sites; Oₛ/Oₘ/O𝚌 = active overrides by scope)

* **Time:** ~ **O(N + Oₛ + Oₘ + O𝚌)** assuming constant-time keyed lookups by scope (e.g., dictionary/index on `(scope,target)`).
* **Space:** **O(1)** in `N` for streaming, plus **O(Oₛ+Oₘ+O𝚌)** to hold in-memory indices for overrides (and O(#merchants) for MCC mapping if used).

### 12.3 Memory model

* **Streaming-friendly.** Process sites row-wise; no need to materialise `s1_tz_lookup`.
* **Indexes:** Small, immutable in-memory maps keyed by `(scope,target)` (and `merchant_id→mcc` if applicable).
* **Deterministic timestamps:** `created_utc` is derived from S0’s receipt—no runtime clocks needed.

### 12.4 I/O profile

* **Input:** sequential scan over `s1_tz_lookup` partition; one-time load of `tz_overrides` (and MCC mapping).
* **Output:** sequential write of `site_timezones` in catalogue order `[merchant_id, legal_country_iso, site_order]` (file order non-authoritative).

### 12.5 Parallelism & concurrency

* **Across identities:** different `(seed, manifest_fingerprint)` pairs are embarrassingly parallel.
* **Within an identity:** shard by PK ranges or geography behind a **single final writer**; publish remains **single-writer, write-once**.

### 12.6 Hot spots & guardrails

* **High override density:** large `site` or `mcc` override sets increase index size but remain linear. Monitor `overridden_total` and `overridden_by_scope`.
* **Data hygiene:** duplicates per `(scope,target)` or expired overrides are caught by validators; high counts indicate policy issues.
* **MCC reliance:** if MCC overrides are common, ensure the mapping is sealed and complete to avoid aborts for unknown targets.

### 12.7 Scalability knobs (programme-level)

* **Batch size** for site streaming;
* **Index build policy** for overrides/MCC (e.g., precomputed maps per manifest_fingerprint);
* **Writer buffer size** / target row group size for Parquet;
* **Advisory thresholds** for `override_no_effect`, duplicate `(scope,target)`, and expired-skipped counts (warn-only).

### 12.8 Re-run & churn costs

* **Fingerprint churn:** Changing **`tz_overrides`** (or MCC mapping, if sealed) produces a **new S0 `manifest_fingerprint`**, requiring S2 recomputation for all seeds selecting that manifest_fingerprint.
* **Idempotent re-runs:** With unchanged inputs for the same `(seed, manifest_fingerprint)`, S2 reproduces bytes exactly (write-once partition).

### 12.9 Typical envelopes (order-of-magnitude)

* **Overrides:** usually << sites; memory footprint dominated by the site scan, not policy size.
* **Runtime:** scales linearly with `N`; overhead from loading policy/mapping is negligible relative to the site pass.
* **Output size:** ~ one row per site; close to `s1_tz_lookup` footprint with a few extra columns (provenance + `tzid`).

---

## 13. Change control & compatibility **(Binding)**

### 13.1 Versioning & document status

* **SemVer** governs this state spec (`MAJOR.MINOR.PATCH`).

  * **PATCH:** editorial clarifications that **do not** change behaviour, shapes, validators, or outcomes.
  * **MINOR:** strictly backward-compatible additions that **do not** alter identity, partitions/PK, precedence law, or PASS/FAIL results.
  * **MAJOR:** any change that can affect identity, shape/PK/partitions, override/precedence semantics, or validator outcomes.

### 13.2 Stable compatibility surfaces (must remain invariant)

1. **Identity:** output is selected by **`(seed, manifest_fingerprint)`**; partitions are **`[seed, manifest_fingerprint]`** only; path↔embed equality MUST hold.
2. **Output surface:** dataset **`site_timezones`** exists with its **schema anchor/ID** unchanged; `columns_strict: true`.
3. **Shape/keys:** PK = `[merchant_id, legal_country_iso, site_order]`; required columns include `tzid`, `tzid_source ∈ {polygon, override}`; `override_scope ∈ {site,mcc,country|null}`; `nudge_*` carry-through; `created_utc` present.
4. **Determinism:** `created_utc` **= S0.receipt.verified_at_utc**; S2 is RNG-free.
5. **Precedence & activity law:** exactly **one** active override at most, with precedence **site » mcc » country**; “active” means `expiry_yyyy_mm_dd` is **null** or **≥** S0 receipt **date** (no wall clock).
6. **Coverage:** 1:1 from `s1_tz_lookup` rows (same `(seed, manifest_fingerprint)`) to `site_timezones` rows; no drops/extras.
7. **Catalogue posture:** **Dictionary** is authority for IDs→paths/partitions/format; **Registry** for existence/licence/retention; **Schema** is sole shape authority.
8. **Validator & code semantics:** §9 validators and §10 error codes retain their meanings.

### 13.3 Backward-compatible changes (**MINOR** or **PATCH**)

Permitted when they **do not** change identity or acceptance:

* Add **Warn-only** diagnostics/validators (e.g., advisory checks on writer order, override density, MCC coverage).
* Extend **run-report** fields or structured logs (non-identity metadata).
* Tighten textual descriptions or add explicit bounds **already met** by existing outputs.
* Add optional, non-authoritative **Registry/Dictionary metadata** (provenance URLs, owner team, TTL notes).
* Permit additional **policy metadata fields** in `tz_overrides` *without affecting precedence or activity law* (e.g., new optional rationale URLs) via a schema **MINOR** that preserves existing behaviour.

> Note: `site_timezones` is **columns_strict**. Adding data columns to the egress **is not** backward-compatible unless introduced under a predeclared extension mechanism (see §13.7) or a new anchor/version.

### 13.4 Breaking changes (**MAJOR**)

Require a MAJOR bump and downstream coordination:

* Changing **partitions** (adding/removing/renaming partition keys) or **PK**; renaming/removing the dataset/anchor.
* Altering **precedence** (order or tie handling) or the **definition of “active”** (e.g., switching to wall-clock time).
* Allowing >1 override per site, or applying overrides when an MCC mapping is absent (today MCC requires a sealed mapping).
* Making `tzid_source/override_scope` enums broader or mandatory in new ways; changing carry-through rules for `nudge_*`.
* Turning an existing **Warn** into **Abort**, or changing meanings of §10 error codes.
* Mandating new inputs (e.g., requiring tzid membership in `tz_world` if previously optional) that can flip PASS→FAIL.
* Any change that causes previously valid `site_timezones` to **fail** schema or validators under unchanged inputs.

### 13.5 Deprecation policy

* **Announce → grace → remove.** Mark features **Deprecated** at least **one MINOR** before removal and record an **effective date**.
* **No repurposing.** Deprecated fields/codes/IDs are never reused; removal only at **MAJOR**.
* **Alias window.** When renaming anchors/IDs, provide aliases for at least one MINOR; both validate to identical shapes during the window.

### 13.6 Co-existence & migration

* **Dual-anchor window.** Evolving `site_timezones` uses a new anchor (e.g., `…/site_timezones_v2`) while the old one remains valid; Dictionary may list both; identity remains `(seed, manifest_fingerprint)`.
* **Re-fingerprinting is upstream.** Changes to `tz_overrides` (or MCC mapping) are sealed in S0 and yield a new **`manifest_fingerprint`**; S2 recomputes for that manifest_fingerprint without spec change.
* **Idempotent re-runs.** Reruns with unchanged inputs reproduce bytes exactly (write-once partition).

### 13.7 Reserved extension points

* **Not defined in v1.0.0-alpha:** current `site_timezones` anchor is **columns_strict** and **does not** admit arbitrary extension columns.
* A future MINOR **may** introduce an **`extensions` object** or `ext_*` pattern fields (ignored by consumers) **if and only if** the anchor is updated concurrently to allow them; otherwise any new column is **MAJOR**.

### 13.8 External dependency evolution

* **Override schema growth.** Adding optional metadata fields to `tz_overrides` that do not affect precedence/activity is **MINOR**; changing scopes, activity semantics, or required fields is **MAJOR**.
* **MCC mapping posture.** Changing the gating rule (e.g., permitting MCC overrides without a sealed mapping) is **MAJOR**.

### 13.9 Governance & change process

Every change SHALL include: (i) version bump rationale, (ii) compatibility impact (Patch/Minor/Major), (iii) updated anchors/Dictionary/Registry stanzas (if any), (iv) validator/error-code diffs, and (v) migration notes.
Frozen specs SHALL record an **Effective date**; downstream pipelines target frozen or explicitly authorised alpha versions.

### 13.10 Inter-state coupling

* **Upstream:** relies only on S0 receipt and S1 output (`s1_tz_lookup`) plus the sealed `tz_overrides` (and MCC mapping if used).
* **Downstream:** `site_timezones` is egress consumed by later 2A states and other segments; any S2 change that forces downstream to re-implement S0 gates or alters the egress read contract is **breaking**.

---

## Appendix A — Normative cross-references *(Informative)*

> Pointers only. These define the authorities S2 relies on. **Schema = shape authority**; **Dictionary = IDs → paths/partitions/format**; **Registry = existence/licensing/retention**. S2 reads only the inputs listed; all IDs resolve via the Dictionary.

### A1. Layer-1 governance (global rails)

* **Identity & Path Law** — path↔embed equality; partition keys are authoritative.
* **Gate Law** — “No PASS → No Read”; S2 relies on the 2A.S0 receipt (does not re-hash bundles).
* **Hashing/Fingerprint Law** — canonical manifest → `manifest_fingerprint` (fixed upstream in S0).
* **Numeric policy** — layer-wide numeric/encoding rules (by reference).

### A2. Upstream receipts & inputs used by S2

* **2A.S0 gate receipt** — `schemas.2A.yaml#/validation/s0_gate_receipt_v1` (manifest_fingerprint-scoped, catalogue path family `…/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/…`).
* **S1 output** — `s1_tz_lookup`: `schemas.2A.yaml#/plan/s1_tz_lookup`; Dictionary path `data/layer1/2A/s1_tz_lookup/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (partitions `[seed, manifest_fingerprint]`).
* **Policy overrides** — `tz_overrides`: `schemas.2A.yaml#/policy/tz_overrides_v1`; Dictionary path `config/layer1/2A/timezone/tz_overrides.yaml` (precedence site » mcc » country).
* **(Optional) Merchant→MCC mapping** — `merchant_mcc_map` dataset (schema `schemas.ingress.layer1.yaml#/merchant_mcc_map`); must be sealed and enumerated in the S0 manifest for the run.

### A3. S2 egress (this state)

* **Final per-site tz** — `site_timezones`: `schemas.2A.yaml#/egress/site_timezones` (PK `[merchant_id, legal_country_iso, site_order]`; partitions `[seed, manifest_fingerprint]`; provenance fields `tzid_source`, `override_scope`; carry-through `nudge_*`).
  Dictionary path family `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`; Registry marks as **final in layer**.

### A4. Ingress/time-zone domain (membership source)

* **`tz_world_<release>` polygons** — `schemas.ingress.layer1.yaml#/tz_world_2025a` (GeoParquet, WGS84); this sealed surface supplies the authoritative tzid set used by S2’s V-15b membership validator.
* **Layer `$defs`** — `schemas.layer1.yaml#/$defs/iana_tzid`, `#/$defs/iso2`, `#/$defs/rfc3339_micros` (domains referenced by S2 shapes/validators).

### A5. Dataset Dictionary entries (catalogue authority)

* **Inputs:** `s1_tz_lookup` (plan; `[seed, manifest_fingerprint]`), `tz_overrides` (policy file), *(optional)* MCC mapping (if used).
* **Output:** `site_timezones` (egress; `[seed, manifest_fingerprint]`; Parquet; writer order `[merchant_id, legal_country_iso, site_order]`).
* **Evidence:** 2A.S0 receipt (manifest_fingerprint-scoped).

### A6. Artefact Registry entries (existence/licensing posture)

* **`s1_tz_lookup`** — plan dataset; depends on `site_locations`, `tz_world_<release>`, `tz_nudge`.
* **`tz_overrides`** — policy/config (precedence and retention recorded).
* **`site_timezones`** — egress (write-once; atomic publish; final-in-layer).
* **2A validation bundle/flag (S5)** — manifest_fingerprint-scoped gate for 2A egress (enforced downstream; noted here for programme continuity).

### A7. Segment-level context

* **2A overview flow** — S0 (gate) → S1 (geometry) → **S2 (overrides & finalise)** → S3 (timetables) → S4 (legality) → S5 (validation bundle/flag for 2A).
* S2 remains RNG-free and idempotent; identity is `(seed, manifest_fingerprint)`; selection and reads are **Dictionary-resolved only**.

*Consumers of this specification MUST resolve shapes from the anchors above and resolve all dataset IDs via the Dataset Dictionary; Registry entries provide licensing/provenance and do not override shape or path law.*

---
