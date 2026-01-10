# 6A.S1 — Customer & party base population (Layer-3 / Segment 6A)

## 1. Purpose & scope *(Binding)*

6A.S1 is the **population realisation state** for Layer-3 / Segment 6A. Its purpose is to construct, for each `(manifest_fingerprint, seed)`, the **closed-world party universe** that all later 6A and 6B states operate on.

Concretely, S1:

* Creates the set of **parties/customers** that exist in the bank’s synthetic world:

  * retail customers (e.g. individuals),
  * business customers (e.g. SMEs, corporates),
  * and any other party types defined in 6A’s taxonomies (e.g. “organisation”, “non-profit”) as needed.
* Assigns each party:

  * a stable **party identifier** (`party_id` / `customer_id`) that is globally unique within `(manifest_fingerprint, seed)`,
  * a **home geography** (e.g. country/region, optionally zone representation),
  * a **segment** (e.g. student, salaried, SME, corporate) and other static classification attributes derived from 6A’s priors and taxonomies,
  * optional static attributes that later states may use as context (e.g. income band, lifecycle stage, channel affinity flags), without fixing any dynamic behaviour.

S1 is the **sole authority** within 6A on:

* **“Who exists?”** — the number of parties and how they are distributed across regions, segments and types.
* **Static party segmentation** — how parties are classified into segments and high-level categories that drive product mix, device usage, and fraud posture downstream.

S1’s scope is deliberately limited:

* It **does not** create accounts, products, instruments, devices, IPs, graph edges, or fraud roles; those are introduced in later 6A states (S2–S5).
* It **does not** read or attach individual arrivals from 5B, and **does not** define transaction behaviour; Layer-2 (5A/5B) and 6B own arrival/flow dynamics.
* It **does not** alter or reinterpret upstream world geometry, time, routing, or virtual semantics; those remain under 1A–3B and 5A–5B.

Within 6A, S1 sits directly downstream of S0:

* It only runs for worlds where 6A.S0 is PASS and has sealed the input universe via `sealed_inputs_6A` and `s0_gate_receipt_6A`.
* It uses the **6A population and segmentation priors** (and, where configured, coarse upstream context such as region surfaces) to realise an integer population per world+seed, subject to the constraints and RNG discipline defined later in this state’s spec.

All downstream 6A states (accounts/products, instruments, devices/IPs, fraud posture) and 6B's flow/fraud logic must treat S1's party base as **read-only ground truth** for the identity and segmentation of parties in the synthetic bank.

---

### Contract Card (S1) - inputs/outputs/authorities

**Inputs (authoritative; see Section 2 for full list):**
* `s0_gate_receipt_6A` - scope: FINGERPRINT_SCOPED; source: 6A.S0
* `sealed_inputs_6A` - scope: FINGERPRINT_SCOPED; source: 6A.S0
* `prior_population_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `prior_segmentation_6A` - scope: UNPARTITIONED (sealed prior); sealed_inputs: required
* `taxonomy_party_6A` - scope: UNPARTITIONED (sealed taxonomy); sealed_inputs: required

**Authority / ordering:**
* S1 is the sole authority for the party base and static party segmentation.

**Outputs:**
* `s1_party_base_6A` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, parameter_hash]
* `s1_party_summary_6A` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, parameter_hash] (optional)
* `rng_event_party_count_realisation` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]
* `rng_event_party_attribute_sampling` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]
* `rng_audit_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]
* `rng_trace_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]

**Sealing / identity:**
* External inputs MUST appear in `sealed_inputs_6A` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or RNG/policy violations -> abort; no outputs published.

## 2. Preconditions, upstream gates & sealed inputs *(Binding)*

6A.S1 only runs in worlds where **Layer-1, Layer-2 and 6A.S0 are already sealed** for the relevant identity axes. This section fixes those preconditions and the **minimum sealed inputs** S1 expects to see.

---

### 2.1 World-level preconditions (Layer-1 & Layer-2)

For a given `manifest_fingerprint` that S1 will process, the engine MUST have:

* Successfully run all required upstream segments for that world:

  * Layer-1: 1A, 1B, 2A, 2B, 3A, 3B
  * Layer-2: 5A, 5B

* Successfully verified their HashGates (validation bundles + PASS flags), as recorded by 6A.S0.

S1 **does not** re-implement upstream HashGate logic. Instead, it **trusts S0’s view**:

* From `s0_gate_receipt_6A.upstream_gates`, every required segment MUST have:

  ```text
  gate_status == "PASS"
  ```

If any required segment is `FAIL` or `MISSING` in `upstream_gates` for this `manifest_fingerprint`, S1 MUST treat the world as **not eligible** and fail fast with a `6A.S1.S0_GATE_FAILED` (or equivalent) error.

---

### 2.2 S0 gate & sealed-inputs preconditions

S1 only runs for a `(manifest_fingerprint, seed)` pair if **all** of the following hold:

1. **S0 gate artefacts exist and are structurally valid** for the world:

   * `s0_gate_receipt_6A` exists under the correct `manifest_fingerprint={manifest_fingerprint}` partition and validates against `schemas.layer3.yaml#/gate/6A/s0_gate_receipt_6A`.
   * `sealed_inputs_6A` exists under the same partition and validates against `schemas.layer3.yaml#/gate/6A/sealed_inputs_6A`.

2. **Digest check passes**:

   * S1 must recompute `sealed_inputs_digest_6A` from the stored `sealed_inputs_6A` rows, using the canonical row encoding and order defined in S0.
   * The recomputed digest MUST equal `s0_gate_receipt_6A.sealed_inputs_digest_6A` for that `manifest_fingerprint`.

3. **Run-report says S0 is PASS**:

   * The latest 6A.S0 run-report for this `manifest_fingerprint` MUST have:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

If any of these checks fails, S1 MUST NOT attempt to load priors or generate any parties for that world.

---

### 2.3 Required sealed inputs for S1

S1 may only read artefacts that appear in `sealed_inputs_6A` for the world and have `read_scope = "ROW_LEVEL"`. Among those, S1 requires at minimum:

1. **6A population & segmentation priors** (all with `status="REQUIRED"` and `read_scope="ROW_LEVEL"`):

   * One or more artefacts with `role = "POPULATION_PRIOR"` covering global or regional population scales.
   * One or more artefacts with `role = "SEGMENT_PRIOR"` describing how parties are split into segments (e.g. student, salaried, SME, corporate) per region/cohort.
   * Any additional priors needed for party-level attributes that S1 is responsible for (e.g. income band, lifecycle stage), if those attributes are part of the binding S1 output schema.

2. **Taxonomies for party types & segments**:

   * One or more artefacts with `role = "TAXONOMY"` covering:

     * party/party-type enumerations (retail, business, etc.),
     * customer segment enumerations (segment IDs/names),
     * any code lists S1 needs to emit stable enum values in `s1_party_base_6A`.

   These may be marked `status="REQUIRED"` or `status="OPTIONAL"` depending on design, but if the S1 schema references them (e.g. via enum), their absence MUST be treated as fatal.

3. **6A contracts** (metadata-only):

   * Entries in `sealed_inputs_6A` with `role="CONTRACT"` and `read_scope="METADATA_ONLY"` for:

     * `schemas.layer3.yaml`,
     * `schemas.6A.yaml`,
     * `dataset_dictionary.layer3.6A.yaml`,
     * `artefact_registry_6A.yaml`.

   S1 MUST use these to verify that its output datasets are correctly declared, but MUST NOT attempt to change them.

4. **Optional contextual priors** (if the design uses them):

   Depending on the final 6A design, S1 MAY also require or optionally consume:

   * upstream **region or country surfaces** (e.g. country population / GDP buckets) as `role="UPSTREAM_EGRESS"` or `role="POPULATION_PRIOR"`,
   * coarse 5A/5B volume summaries (e.g. merchant×region expected volumes) as `role="SCENARIO_CONFIG"` or `role="UPSTREAM_EGRESS"`.

   In all such cases, S1 must **only** read them if:

   * they appear in `sealed_inputs_6A` for the world,
   * `status ∈ {"REQUIRED","OPTIONAL"}`,
   * `read_scope="ROW_LEVEL"` (for row-level use) or `METADATA_ONLY` (for presence/shape checks only).

If any artefact that S1 classifies as `REQUIRED` is missing from `sealed_inputs_6A`, or present but with incompatible `read_scope`, S1 MUST fail with a suitable `6A.S1.PRIOR_PACK_*` or `6A.S1.SEALED_INPUTS_*` error (to be defined in the S1 failure section).

---

### 2.4 Seed and scenario axes

S1’s natural domain is `(manifest_fingerprint, seed)`:

* The set of `seed` values for which S1 runs in a world is defined by the **engine orchestrator** and/or 6A configuration. S1 does **not** infer seeds from upstream data; it is given a concrete `(mf, seed)` to work on.
* Scenario identity (`scenario_id`) originates from Layer-2 / 5A/5B and is **not** directly used by S1:

  * S1 does not vary population per scenario; it creates a single party universe per `(mf, seed)` that all scenarios share.
  * If a future extension needs scenario-dependent populations, that will be a breaking change for S1 and must be versioned accordingly.

For a given `(mf, seed)`:

* S0 preconditions MUST hold (as above),
* all required S1 priors/taxonomies MUST be resolvable and valid,
* and S1 MUST treat its outputs as the **only** party base for that world+seed (see identity & merge discipline later).

---

### 2.5 Out-of-scope inputs

S1 explicitly **does not** depend on:

* individual arrivals from `arrival_events_5B`,
* any transaction-level, flow-level, or label-level datasets from 6B or downstream,
* environment or wall-clock time (beyond non-semantic `created_utc` audit fields),
* any artefact not present in `sealed_inputs_6A` for the world.

If an implementation reads such inputs, it is out of spec. S1 preconditions are strictly limited to:

* S0 PASS + sealed inputs,
* upstream HashGate statuses as recorded by S0, and
* the presence and validity of the 6A contracts and priors it requires.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes, for **6A.S1**, exactly:

* **what it is allowed to read**, and
* **who is allowed to define what** (Layer-1, Layer-2, 6A itself),

so that later 6A states and 6B can safely assume S1 never oversteps into upstream responsibilities.

S1 **must only** consume artefacts that appear in `sealed_inputs_6A` for its `manifest_fingerprint`, and must respect the `role` and `read_scope` assigned there by S0.

---

### 3.1 Logical inputs S1 may consume

Subject to §2 and `sealed_inputs_6A`, S1’s logical inputs are:

#### 3.1.1 S0 gate & sealed-inputs (control plane)

* `s0_gate_receipt_6A`

  * World & parameter identity (`manifest_fingerprint`, `parameter_hash`).
  * Upstream segment gate statuses (`upstream_gates`).
  * 6A contract/priors summary and `sealed_inputs_digest_6A`.

* `sealed_inputs_6A`

  * Enumerates all artefacts 6A may rely on, with `role`, `status`, `read_scope`, `schema_ref`, `path_template`, `partition_keys`, `sha256_hex`.

S1 **must** treat these as the *sole* authority on what inputs it can use.

#### 3.1.2 6A priors & taxonomies (ROW_LEVEL)

All of the following must appear in `sealed_inputs_6A` with `read_scope = "ROW_LEVEL"` and appropriate `role` values:

* **Population priors** (`role = "POPULATION_PRIOR"`):

  * Global population scale (e.g. total parties per world or per seed).
  * Regional/geo splits (e.g. per-country or per-region expected shares).

* **Segmentation priors** (`role = "SEGMENT_PRIOR"`):

  * Segment mix per region / cohort (e.g. student vs salaried vs SME vs corporate).
  * Optional conditioning on simple attributes (e.g. age bands, income bands) if S1 is responsible for those attributes.

* **Taxonomies** (`role = "TAXONOMY"`):

  * Party type taxonomy (retail / business / other).
  * Customer/segment code lists.
  * Any enum/lookup tables S1 needs to populate fields in `s1_party_base_6A` (e.g. region codes, segment IDs).

S1 uses these priors to:

* compute target party counts per `(region, segment, type)`, and
* sample static attributes for each party.

#### 3.1.3 Optional upstream context (ROW_LEVEL or METADATA_ONLY)

Depending on the final design, S1 **may** also consume, via `sealed_inputs_6A`:

* **World/geo context** (`role = "UPSTREAM_EGRESS"` or `role = "POPULATION_PRIOR"`):

  * Country/region reference tables (e.g. ISO, region groupings).
  * Optional L1 surfaces like population or GDP buckets per country/region.

* **Intensity/volume context** (`role = "SCENARIO_CONFIG"` or `role = "UPSTREAM_EGRESS"`), *if enabled*:

  * Coarse 5A/5B summaries (e.g. expected total arrivals or spend per region/segment/merchant class),
  * **only** at an aggregate level (no per-arrival or per-bucket use).

Where these appear:

* If `read_scope = "ROW_LEVEL"`, S1 may read rows as inputs to its population scaling logic.
* If `read_scope = "METADATA_ONLY"`, S1 may only test their presence / digests (e.g. to decide whether a “volume-aware” mode is enabled), and must not read rows.

These are **hints**, not authorities: they may influence how big the population is in a region, but they do not override priors or define party identity.

#### 3.1.4 6A contracts (METADATA_ONLY)

From `sealed_inputs_6A` with `role = "CONTRACT"` and `read_scope = "METADATA_ONLY"`:

* `schemas.layer3.yaml`
* `schemas.6A.yaml`
* `dataset_dictionary.layer3.6A.yaml`
* `artefact_registry_6A.yaml`

S1 must use these only to:

* validate that its outputs conform to declared schemas and paths, and
* discover dataset IDs / partitioning for its outputs.

It must **not** attempt to mutate or reinterpret these contracts.

---

### 3.2 Upstream authority boundaries (L1 & L2)

S1 sits on top of a sealed world from Layers 1 and 2. The following boundaries are binding:

#### 3.2.1 Merchant, site, geo & time (1A–2A)

* **Merchants & outlets** (1A), **site locations** (1B), **site timezones** / `tz_timetable_cache` (2A) are fully owned by those segments.

S1 **must not**:

* create or delete merchants or sites,
* change geo coordinates,
* assign or override site timezones,
* interpret iso/country/zone boundaries differently from the upstream schemas.

S1 **may**:

* use these artefacts indirectly (e.g. via region/country surfaces) to inform population splits (more customers where there are more outlets), but only through artefacts that appear in `sealed_inputs_6A`.

#### 3.2.2 Zone allocation, routing & virtual overlay (2B,3A,3B)

* **Zone allocation** (3A) and **routing / virtual overlay** (2B,3B) define where merchants “live” across zones, how site/edge routing works, and what is virtual vs physical.

S1 **must not**:

* introduce its own routing or zoning laws,
* redefine what “virtual merchant” means,
* depend on per-site or per-edge routing details.

S1 **may**:

* use high-level region or risk classifications that are derived upstream (e.g. merchant risk class, cross-border-heavy region tags) as inputs to priors, but those classifications remain authored by their own segments.

#### 3.2.3 Intensities & arrivals (5A, 5B)

* **5A** and **5B** fully own:

  * intensity surfaces (λ),
  * latent fields and LGCP choices,
  * bucket counts and arrival times,
  * routing of arrivals to site/edge.

S1 **must not**:

* read `arrival_events_5B` at row level,
* resample or adjust intensities or counts,
* encode any assumptions about arrival ordering or counts per bucket.

If S1 uses volume information at all, it may only do so via **aggregated**, explicitly sealed surfaces (e.g. totals per region/segment) that appear in `sealed_inputs_6A`, and those surfaces are *hints* rather than hard constraints.

---

### 3.3 6A.S1 authority boundaries

Within 6A, S1 has clear ownership, and clear “do not touch” lines.

#### 3.3.1 What S1 exclusively owns

S1 is the **only authority** inside 6A on:

* **Party existence and counts**:

  * how many parties exist for each `(manifest_fingerprint, seed)` and per region/segment/type,
  * consistent with, but not dictated by, the population priors.

* **Static segmentation & basic attributes**:

  * assignment of parties into segments (e.g. student, salaried, SME, corporate),
  * any static attributes required by the S1 output schema (e.g. party type, home geography, optional coarse demographics).

All later 6A states (S2–S5) and 6B must treat `s1_party_base_6A` as:

> the complete, read-only universe of parties for that world+seed.

They may **join to it**, but not **expand or alter** it.

#### 3.3.2 What S1 must not do

S1 **must not**:

* Create **accounts, products, instruments, devices or IPs** — those are S2–S4.
* Assign **fraud roles** (mule, synthetic, collusive merchant, risky device/IP) — that is S5’s responsibility.
* Attach arrivals or flows to parties — that is 6B.
* Change any upstream artefacts (no in-place edits, no shadow copies with new semantics).

If an implementation attempts to, e.g., add extra parties “on the fly” during S2–S4, that is out of spec; only S1 may define who exists.

---

### 3.4 Forbidden dependencies & non-inputs

S1 explicitly **must not depend on**:

* Any artefact that is **absent** from `sealed_inputs_6A` for its `manifest_fingerprint`.

* Any artefact listed in `sealed_inputs_6A` with `read_scope = "METADATA_ONLY"` for **row-level logic**.

* External systems or environment:

  * wall-clock time or dates (beyond non-semantic `created_utc`),
  * process IDs, hostnames, random OS state, etc.,
  * network calls or ad-hoc configuration outside the catalogue.

* Raw upstream validation bundles beyond:

  * their presence and digests as already validated in S0,
  * any specific evidence artefacts that S0 chose to expose as `role="CONTRACT"` with `read_scope="METADATA_ONLY"`.

Any such dependence makes the implementation non-compliant, even if it “works” in a particular deployment.

---

### 3.5 How S0’s sealed-input manifest constrains S1

Finally, the relationship between S0 and S1 is binding:

* S1’s **effective input universe** is **exactly** the set of rows in `sealed_inputs_6A` for its `manifest_fingerprint` with:

  * `status ∈ {"REQUIRED","OPTIONAL"}`, and
  * `read_scope` interpreted as above.

* S1 must:

  1. Load `sealed_inputs_6A` and `s0_gate_receipt_6A`.
  2. Verify the digest (`sealed_inputs_digest_6A`).
  3. Filter rows to the subset relevant for S1 (population/segment priors, taxonomies, optional context, contracts).
  4. Refuse to read or rely on any artefact that is not described there.

Downstream S2–S5 and 6B can therefore assume:

* that S1’s party base was generated **only** from the sealed, catalogued inputs for that world, and
* that any change to those inputs will be reflected as a different `sealed_inputs_digest_6A` and, therefore, a different 6A world.

---

## 4. Outputs (datasets) & identity *(Binding)*

6A.S1 produces the **party / customer base** for 6A. This section fixes what those datasets are, what they mean, and how they are identified in the world. Later sections (§5, §7) will pin the exact shapes and partitioning; here we care about **semantics and identity**.

S1 has **one required** business dataset and **one optional** diagnostic dataset.

---

### 4.1 Required dataset — party base

**Logical name:** `s1_party_base_6A` (short: “party base”).
**Role:** The *only* authoritative list of parties/customers that exist in the world for 6A/6B.

#### 4.1.1 Domain & scope

For a given `(manifest_fingerprint, seed)`, `s1_party_base_6A` contains **one row per party** in that world+seed.

* Domain axes:

  * `manifest_fingerprint` — world identity.
  * `seed` — RNG identity for that world.
  * `parameter_hash` — parameter pack identity (embedded as a column).

* S1 is **scenario-independent**:

  * the party base is shared across all scenarios that operate on this `(manifest_fingerprint, seed)`; S1 does not vary the population per `scenario_id`.

#### 4.1.2 Required content (logical fields)

The party base MUST include, at minimum, the following logical fields (names can be tuned in the schema, semantics cannot):

* **Identity & keys**

  * `party_id` (or `customer_id`):

    * stable identifier for the party within `(manifest_fingerprint, seed)`,
    * globally unique for that world+seed.
  * `manifest_fingerprint`
  * `parameter_hash`
  * `seed`

* **Type & taxonomy**

  * `party_type`: enum keyed off the 6A taxonomy (e.g. `RETAIL`, `BUSINESS`, `OTHER`).
  * `segment_id`: segment code (e.g. student, salaried, SME, corporate), from the 6A segment taxonomy.
  * optional `segment_group` / `segment_family` if the taxonomy is hierarchical.

* **Home geography**

  * `country_iso` (or equivalent) — party’s home country.
  * optional `region_id` / `region_group` — supra-national or sub-national grouping, if used in priors.
  * optional `zone_representation` if S1 needs zone-level segments (e.g. coarse time-zone buckets, not routing zones).

* **Static attributes (if in scope for S1)**

  (Only those attributes S1 is responsible for; anything else belongs to later states.)

  Examples:

  * `lifecycle_stage` (e.g. `STUDENT`, `EARLY_CAREER`, `MID_CAREER`, `RETIRED`).
  * `income_band` or `turnover_band` (banded, not raw amounts).
  * `customer_tenure_band` (if tenure is modelled as static at S1, otherwise belongs later).
  * boolean flags such as `is_business_owner`, `eligible_for_business_products`, `eligible_for_cards`.

Each of these attributes is:

* derived from the **sealed 6A priors** and taxonomies,
* immutable for the party throughout the life of the world (later states may derive behaviour from them but must not change them).

#### 4.1.3 Identity & invariants

For `s1_party_base_6A`:

* **Primary key (logical):**

  * `(manifest_fingerprint, seed, party_id)`

* **Uniqueness invariants:**

  * `party_id` MUST be unique within `(manifest_fingerprint, seed)`.
  * There MUST be no two rows with the same `(manifest_fingerprint, seed, party_id)`.

* **World consistency:**

  * All rows in a given partition (for that `manifest_fingerprint`) MUST share the same `manifest_fingerprint`.
  * All rows in a given `(seed, manifest_fingerprint)` partition MUST share the same `parameter_hash` (echoing the S0/S1 run identity), i.e. the population is realised under a single parameter pack.

* **Closed world:**

  * For a given `(manifest_fingerprint, seed)`, the union of all party_ids in `s1_party_base_6A` is the **entire party universe** for that world+seed.
  * No later 6A state or 6B is permitted to introduce new party IDs that do not appear here.

---

### 4.2 Optional dataset — party summary

**Logical name:** `s1_party_summary_6A` (short: “party summary”).
**Role:** Diagnostic/aggregate view of the party base; convenient for QA and for downstream sizing, but strictly **derived** from `s1_party_base_6A`.

#### 4.2.1 Domain & scope

For a given `(manifest_fingerprint, seed)`, `s1_party_summary_6A` contains aggregate counts over some grouping dimensions (e.g. `(country_iso, segment_id, party_type)`).

S1 may choose a grouping scheme that matches 6A priors, for example:

* `(country_iso, segment_id, party_type)`,
* or `(region_id, segment_id)` if regions are the primary axis.

#### 4.2.2 Required properties (if present)

If `s1_party_summary_6A` is implemented, it MUST:

* be a pure aggregation of `s1_party_base_6A`:

  * total parties per group MUST equal the count of matching rows in the base table,
  * no group may appear in the summary that has zero corresponding parties.

* include at least:

  * `manifest_fingerprint`, `parameter_hash`, `seed`,
  * grouping columns (e.g. `country_iso`, `segment_id`, `party_type`),
  * `party_count` (integer),
  * optional `population_prior_id` or `prior_reference` if you want to echo which prior record governed that group.

The summary is **informative** for downstream states; it is not a source of new semantics. If it ever disagrees with the base table, the base table wins and S1 is considered invalid.

---

### 4.3 Relationship to upstream and downstream identity

S1 outputs are designed to align with existing identity axes in the engine:

* **Upstream alignment:**

  * S1 uses the **same `manifest_fingerprint`** as upstream L1/L2 segments, as fixed by S0.
  * It uses the same `parameter_hash` as S0 and any 6A priors, so population realisation can be tied back to the parameter pack.
  * It introduces **no new world identity dimension**.

* **Downstream alignment:**

  * Later 6A states (S2–S5) and 6B will join on:

    * `manifest_fingerprint`,
    * `seed`,
    * `party_id` (plus `parameter_hash` as a consistency check where needed).

  * S1’s outputs must therefore be **stable and idempotent** given `(manifest_fingerprint, parameter_hash, seed)` and the sealed priors.

Any downstream table that claims to describe parties/customers must:

* either be **derived from `s1_party_base_6A`** (directly or via joins), or
* explicitly document why it is not (and, in that case, is outside the 6A world we are defining here).

No other dataset may redefine the answer to “who exists” for 6A/6B.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

All binding schema anchors, dataset IDs, partitioning rules, and manifest keys for this state's egress live in the Layer-3 / Segment 6A contracts:
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/dataset_dictionary.layer3.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/artefact_registry_6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/schemas.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/schemas.layer3.yaml`

This specification only summarises semantics so there is a single source of truth for catalogue details. Always consult the files above for precise schema refs, physical paths, partition keys, writer ordering, lifecycle flags, and dependency metadata.

### 5.1 Outputs owned by this state
- `s1_party_base_6A` — Deterministic party universe for Layer-3, keyed by party identifiers and seeded/manifest partitions.
- `s1_party_summary_6A` — Aggregated diagnostics over the party base (counts, coverage by merchant/country/class) for monitoring S1 policy outcomes.

### 5.2 Catalogue & downstream obligations
Implementations and downstream consumers MUST resolve datasets via the dictionary/registry, honour the declared schema anchors, and treat any artefact not listed there as out of scope for this state.

## 6. Deterministic algorithm (with RNG — population & segmentation) *(Binding)*

6A.S1 is **deterministic given**:

* the sealed 6A priors & taxonomies,
* the upstream world identity (`manifest_fingerprint`),
* the parameter pack (`parameter_hash`),
* and the RNG seed.

This section fixes **what S1 does, in which order, and which parts are RNG-bearing vs RNG-free**.
Codex is free to choose *how* to implement each step, but **not** free to change the observable behaviour described here.

---

### 6.0 Overview & RNG discipline

For each `(manifest_fingerprint, seed)`:

1. Load gate & priors (RNG-free).
2. Derive **continuous target populations** per region/segment/type (RNG-free).
3. Realise **integer party counts** per cell, conserving total population (RNG-bearing).
4. Construct **party rows** with stable IDs and attributes, using priors + RNG (RNG-bearing).
5. Emit `s1_party_base_6A` (and optional `s1_party_summary_6A`) with deterministic ordering (RNG-free).

RNG discipline:

* S1 uses the same Philox-based envelope as the rest of the engine (Layer-3 RNG environment, analogous to Layer-1):

  * a single Philox-2x64-10 generator,
  * keyed substreams based on `(manifest_fingerprint, seed, "6A.S1", substream_label, group-identifiers…)`,
  * each RNG event recorded under a `rng_event_*` schema with:

    * before/after counters,
    * `blocks`, `draws` metadata,
    * and one row appended to the layer-wide RNG trace log.

* S1 uses **two logical RNG families**:

  * `party_count_realisation` (contract id: `rng_event_party_count_realisation`; substream_label: `party_count_realisation`) - for sampling integer counts per population cell.
  * `party_attribute_sampling` (contract id: `rng_event_party_attribute_sampling`; substream_label: `party_attribute_sampling`) - for sampling per-party attributes (within each cell).

The exact event schema and trace integration live in `schemas.layer3.yaml` / `schemas.6A.yaml`; this spec fixes their **intended meaning**.

---

### 6.1 Phase 1 — Load gate, priors & taxonomies (RNG-free)

**Goal:** Ensure S1 is operating under a sealed S0 world and load the priors it needs.

Steps:

1. **Verify S0 gate and digest**

   * Read `s0_gate_receipt_6A` and `sealed_inputs_6A` for the target `manifest_fingerprint`.

   * Recompute `sealed_inputs_digest_6A` from `sealed_inputs_6A` using the canonical law from S0; compare to the value in the gate receipt.

   * Verify that:

     * all required upstream segments in `upstream_gates` have `gate_status="PASS"`,
     * the latest S0 run-report for this `manifest_fingerprint` has `status="PASS"` and empty `error_code`.

   * If any check fails → **FAIL** (`6A.S1.S0_GATE_FAILED`).

2. **Locate S1-relevant sealed inputs**

   * From `sealed_inputs_6A`, select rows with:

     * `role ∈ { "POPULATION_PRIOR", "SEGMENT_PRIOR", "TAXONOMY" }`,
     * `status ∈ { "REQUIRED", "OPTIONAL" }`,
     * `read_scope = "ROW_LEVEL"`.

   * From those, identify the specific artefacts S1’s design requires (e.g. world population prior, region splits, segment mix priors, party & segment taxonomies).

3. **Load priors & taxonomies**

   * For each required prior/taxonomy:

     * resolve its physical path via its `path_template` + `partition_keys`,
     * read its rows and validate them against `schema_ref` (from the catalogue).

   * Build in-memory surfaces, such as:

     * `π_region` — expected share per region or country,
     * `N_world_target` — target total parties per world or per seed,
     * `π_segment | region` — expected segment mix per region,
     * taxonomy maps for `party_type`, `segment_id`, `region_id`/`country_iso`.

4. **Optional: load contextual hints**

   * If the design uses them and they are present in `sealed_inputs_6A`:

     * load upstream context surfaces (e.g. country population or GDP buckets, low-res volume hints from 5A/5B) with appropriate `role` and `read_scope`.

   * These hints may scale or shape target counts but **must not override** basic priors.

This phase is **purely deterministic** and RNG-free.

---

### 6.2 Phase 2 — Derive continuous target populations (RNG-free)

**Goal:** Compute **fractional** target counts per population cell using priors.

Define a **population cell** as a tuple:

```text
c = (region_id, party_type, segment_id)
```

or another fixed grouping scheme chosen for 6A; the scheme itself is part of the binding spec once decided.

Steps:

1. **Define population domain**

   * Build the set of cells `C` from the Cartesian product of:

     * regions (from population priors / taxonomies),
     * party types (from party-type taxonomy),
     * segments (from segment taxonomy).

   * Optionally mask out invalid combinations according to priors (e.g. some segments allowed only for certain regions or party types).

2. **Compute world and region targets**

   * Using priors:

     * `N_world_target` — target total parties in the world (real number).
     * `π_region` — fractional share per region (Σ over regions = 1).

   * Compute **continuous** region targets:

     ```text
     N_region_target(r) = N_world_target * π_region(r)
     ```

   * This is deterministic, using fixed-precision arithmetic (e.g. decimal or binary64 with explicit rounding rules).

3. **Compute cell targets within each region**

   * Using segmentation priors conditional on region and type:

     * `π_segment | region, type` — fractional share per segment given region & party_type; sums to 1 within each `(region, party_type)`.

   * For each cell `c = (r, t, s)`:

     ```text
     N_cell_target(c) = N_region_target(r) * π_party_type|region(r, t) * π_segment|region,type(r, t, s)
     ```

   * Again, defined with fixed deterministic arithmetic.

4. **Enforce sanity checks (RNG-free)**

   * Verify:

     * `N_region_target(r) ≥ 0` and finite,
     * `N_cell_target(c) ≥ 0` and finite,
     * the sum of `N_region_target(r)` over regions is within a small tolerance of `N_world_target`,
     * the sum of `N_cell_target(c)` over cells is within a small tolerance of `N_world_target`.

   * Fail fast (`6A.S1.TARGET_COUNTS_INCONSISTENT`) if these invariants are violated.

The output of this phase is a deterministic table of **continuous target counts** per cell, which S1 will convert into integers next.

---

### 6.3 Phase 3 — Realise integer party counts per cell (RNG-bearing)

**Goal:** Convert continuous targets into **integer counts** per cell while preserving total population and respecting priors as closely as possible.

At this point, S1 introduces RNG, using the `party_count_realisation` family.

#### 6.3.1 Region-level integerisation (optional split)

Depending on your chosen design, you may:

* either integerise directly at the cell level, or
* first integerise at region level, then split region totals into cells.

A typical two-step, conservation-friendly approach:

1. **Region integerisation (RNG-free)**

   * For each region `r`, compute:

     ```text
     N_region_floor(r)  = floor(N_region_target(r))
     r_region_resid(r)  = N_region_target(r) - N_region_floor(r)
     ```

   * Let:

     ```text
     N_world_floor = Σ_r N_region_floor(r)
     R_world       = N_world_target - N_world_floor
     ```

   * Use deterministic **largest-remainder** assignment across regions (no RNG) to allocate the remaining `round(R_world)` units by sorting regions by `r_region_resid(r)` (and tie-breaking by region_id).

   * Result: integer `N_region(r)` such that:

     * `N_region(r) ≥ 0`,
     * Σ_r `N_region(r)` equals a chosen integer `N_world_int` that approximates `N_world_target`.

2. **Cell integerisation within a region (RNG-bearing)**

   * For each region `r`:

     * You now have total `N_region(r)` and fractional cell shares `π_cell|region(r,c)` derived from `N_cell_target(c)`.

   * Use a **multinomial-style realisation** controlled by `party_count_realisation` RNG:

     * Sample integer counts `{N_cell(c): c in region r}` such that:

       * Σ_c in region r `N_cell(c) = N_region(r)`,
       * marginal distribution approximates the pi-cell weights.

   * Implementation may be via:

     * true multinomial draw, or
     * sequential binomial decompositions, or
     * weighted largest-remainder with tie-breaking driven by RNG.

   * For the spec, the only obligations are:

     * counts are non-negative integers,
     * **exact conservation** per region,
     * any randomness is solely via the defined RNG family, and
     * the law is documented in the RNG event schema.

#### 6.3.2 RNG event semantics

For each region or per-cell batch, S1 emits a `rng_event_party_count` (or equivalent) with:

* static context: `manifest_fingerprint`, `parameter_hash`, `seed`, region/cell identifiers,
* required RNG envelope:

  * `counter_before`, `counter_after`,
  * `blocks`, `draws` (how many Philox blocks and draws were consumed),
  * optional summary of the realised counts or sufficient stats.

`rng_trace_log` for Layer-3 must account for all such events and ensure there are:

* no overlapping counter ranges between events,
* no gaps relative to the configured budget for `party_count_realisation`.

#### 6.3.3 Invariants

After Phase 3:

* For each region `r`:

  ```text
  Σ_c in region r N_cell(c) == N_region(r)
  ```

* Overall:

  ```text
  Σ_c N_cell(c) == N_world_int
  ```

* If any region or cell ends up with `N_cell(c) < 0` or conservation is broken, S1 must fail (`6A.S1.POPULATION_INTEGERISATION_FAILED` or variant).

---

### 6.4 Phase 4 — Construct party rows & sample attributes (RNG-bearing)

**Goal:** For each cell `c`, instantiate **N_cell(c)** parties with unique IDs and static attributes drawn from priors.

This phase uses the `party_attribute_sampling` RNG family.

#### 6.4.1 Party ID assignment (deterministic)

For each `(manifest_fingerprint, seed)`:

1. Define a deterministic **party index**:

   * e.g. enumerate cells `c` in a fixed, sorted order (by `region_id`, `party_type`, `segment_id`).
   * within each cell, enumerate local index `i = 0..N_cell(c)-1` in a deterministic order.

2. Define `party_id` as a deterministic function of `(manifest_fingerprint, seed, c, i)`, for example:

   * either a 64-bit hash:

     ```text
     party_id = LOW64( SHA256( mf || seed || cell_key(c) || uint64(i) ) )
     ```

   * or a sequential index encoded in a stable way.

Whatever law is chosen must be:

* **injective** within `(mf, seed)`,
* independent of RNG,
* stable across re-runs.

#### 6.4.2 Attribute sampling per party (RNG-bearing)

For each party row `(mf, seed, party_id)` belonging to cell `c = (region, party_type, segment_id)`:

1. **Base attributes from cell**

   * Set:

     * `party_type` = party_type(c),
     * `segment_id` = segment(c),
     * `country_iso` / `region_id` as per region(c).

2. **Sample extra attributes from conditional priors**

   * For each attribute that S1 owns (e.g. `lifecycle_stage`, `income_band`, `turnover_band`, `customer_tenure_band`):

     * use the appropriate **conditional prior** (e.g. `π_lifecycle | region, segment, type`, `π_income_band | lifecycle, region, segment`),
     * draw a categorical sample using `party_attribute_sampling` RNG:

       * either one RNG event per attribute family per cell, or per party, depending on your chosen event granularity.

   * Attributes may be:

     * independent conditional on cell and other attributes, or
     * sampled sequentially with dependencies (e.g. lifecycle → income → tenure), as defined by the prior pack.

3. **Emit RNG events**

   * For groups of attribute draws (per cell or per batch), emit `rng_event_party_attribute` entries containing:

     * context (cell identifiers, attribute family),
     * counters before/after, `blocks`, `draws`,
     * optional histograms or summary stats.

Implementation may vectorise draws for performance, but must preserve:

* that all randomness is issued via the `party_attribute_sampling` family,
* that the RNG envelope constraints are respected,
* that for fixed inputs and seed, the resulting attribute assignments are deterministic.

---

### 6.5 Phase 5 — Materialise outputs & internal validation (RNG-free)

**Goal:** Persist the base and summary datasets consistently and perform cheap internal checks.

#### 6.5.1 Write `s1_party_base_6A`

* Construct `s1_party_base_6A` rows with all required fields:

  * identity fields (`mf`, `ph`, `seed`, `party_id`),
  * type/segment/geo fields,
  * static attributes.

* Write to:

  ```text
  data/layer3/6A/s1_party_base_6A/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...
  ```

  with partitioning and ordering as per the dictionary:

  * partitions: `[seed, manifest_fingerprint]`,
  * writer sort, e.g.: `(country_iso, segment_id, party_type, party_id)`.

* Enforce:

  * schema validation against `schemas.6A.yaml#/s1/party_base`,
  * uniqueness of `(manifest_fingerprint, seed, party_id)`.

#### 6.5.2 Write `s1_party_summary_6A` (optional)

* If the summary dataset is implemented:

  * aggregate `s1_party_base_6A` by the chosen grouping keys (e.g. `country_iso, segment_id, party_type`),
  * compute `party_count` as the exact count of base rows per group,
  * write the result to the path and partitioning defined in the dictionary.

* Confirm that:

  * re-aggregating the base from the summary reproduces `party_count` (for self-check).

#### 6.5.3 Internal validation checks

Before marking S1 as PASS for this `(mf, seed)`:

* Re-scan (or partial-scan with strong invariants) `s1_party_base_6A` to verify:

  * all `party_id` values are unique per `(mf, seed)`,
  * grouping by `(region, segment, party_type)` yields integer counts exactly equal to `N_cell(c)` from Phase 3,
  * any attribute-level constraints from priors (e.g. segment/party_type compatibility) are satisfied.

* If any check fails → **FAIL** with a suitable S1 error code (e.g. `6A.S1.POPULATION_ZERO_WHEN_DISALLOWED`, `6A.S1.SEGMENT_ASSIGNMENT_INVALID`), and the run-report must reflect this.

---

### 6.6 Determinism guarantees

Given:

* `manifest_fingerprint`,
* `parameter_hash`,
* `seed`,
* sealed 6A priors/taxonomies and any contextual surfaces used,

S1’s business outputs (`s1_party_base_6A`, and `s1_party_summary_6A` if present) must be:

* **bit-stable idempotent** — re-running S1 in the same catalogue state produces byte-identical outputs,
* independent of:

  * run order of regions/cells,
  * parallelism strategy,
  * physical file layout decisions within a partition (as long as canonical writer ordering is enforced).

All randomness flows through the two RNG families with fixed substream labelling. Changing the RNG family definitions or their mapping to attributes is considered a behavioural change for S1 and must be handled under change control (§12).

This algorithm is **binding**: implementations may optimise or vectorise, but must preserve all invariants, conservation laws, and identity properties described here.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S1’s outputs are identified, partitioned, ordered, and merged**.
Downstream 6A states (S2–S5) and 6B must treat these rules as **binding**, not implementation hints.

S1’s business outputs are:

* **Required:** `s1_party_base_6A`
* **Optional:** `s1_party_summary_6A`

(plus RNG logs, which follow the Layer-3 RNG envelope and are covered in the layer-wide RNG spec rather than here.)

---

### 7.1 Identity axes

S1 operates on three key identity axes:

* **World identity**

  * `manifest_fingerprint`
  * Shared with all L1/L2 segments and 6A.S0, and treated as the **world ID**.
  * S1 must not change or reinterpret this value.

* **Parameter identity**

  * `parameter_hash`
  * Identifies the parameter/prior pack set used to generate the population.
  * Embedded as a **column** in S1 outputs (not a partition key).
  * For a given `(manifest_fingerprint, seed)`, S1 is expected to run under a single `parameter_hash`. If it does not, that world+seed is considered invalid.

* **RNG identity**

  * `seed`
  * Distinguishes independent population realisations **within the same world**.
  * Two runs with different `seed` values but the same `(manifest_fingerprint, parameter_hash)` define **different party universes**, even though they share upstream world and priors.

S1’s business datasets **must not depend** on `run_id`; `run_id` is for logs and run-reporting only.

---

### 7.2 Partitioning & path tokens

Both S1 datasets are **world+seed scoped**.

#### 7.2.1 `s1_party_base_6A`

* Partition keys:

  ```text
  [seed, manifest_fingerprint]
  ```

* Path token usage (schematic):

  ```text
  data/layer3/6A/s1_party_base_6A/
    seed={seed}/
    manifest_fingerprint={manifest_fingerprint}/
    s1_party_base_6A.parquet
  ```

#### 7.2.2 `s1_party_summary_6A` (if present)

* Partition keys:

  ```text
  [seed, manifest_fingerprint]
  ```

* Path token usage (schematic):

  ```text
  data/layer3/6A/s1_party_summary_6A/
    seed={seed}/
    manifest_fingerprint={manifest_fingerprint}/
    s1_party_summary_6A.parquet
  ```

**Binding rules:**

* The **path tokens** `seed={seed}` and `manifest_fingerprint={manifest_fingerprint}` must match the corresponding columns inside the datasets (no “lying” partitions).

* No additional partition keys (e.g. `parameter_hash`, `scenario_id`) may be introduced for S1 business datasets.

* Any consumer that wants S1 data for a given `(manifest_fingerprint, seed)` **must** resolve the dataset via the catalogue and then substitute those tokens; hard-coded paths are out-of-spec.

---

### 7.3 Primary keys & uniqueness

#### 7.3.1 `s1_party_base_6A`

* **Logical primary key:**

  ```text
  (manifest_fingerprint, seed, party_id)
  ```

* **Uniqueness:**

  * `party_id` MUST be unique within each `(manifest_fingerprint, seed)`.

* **Row-level invariants:**

  * Every row must carry the correct `manifest_fingerprint`, `parameter_hash`, and `seed` consistent with its partition.
  * No row with `(mf, seed)` may be stored in a different partition `(seed', mf')`.

#### 7.3.2 `s1_party_summary_6A` (if present)

* **Logical primary key:**

  * Depends on chosen grouping; for example, if grouped by `(country_iso, segment_id, party_type)`:

    ```text
    (manifest_fingerprint, seed, country_iso, segment_id, party_type)
    ```

* **Relationship to base:**

  * For any group key `g` (whatever grouping you choose), `party_count(g)` **must equal** the count of rows in `s1_party_base_6A` that match `g`.
  * The summary may not introduce any group that has zero parties in the base.

No other PKs or uniqueness invariants are assumed by the spec; implementations may add secondary uniqueness constraints for internal use but they are not part of the contract.

---

### 7.4 Ordering: canonical vs semantic

We distinguish:

* **Canonical ordering** — how writers must order rows to ensure idempotence and stable digests.
* **Semantic ordering** — ordering assumptions that consumers are allowed to rely on.

#### 7.4.1 `s1_party_base_6A`

* **Canonical writer ordering** (example and recommended):

  ```text
  ORDER BY country_iso, segment_id, party_type, party_id
  ```

  This is what the dictionary example encodes as `ordering`.

* **Semantic rules:**

  * Consumers must **not** rely on physical row order for business semantics (e.g. “first N rows are region X”).
  * Any logic that depends on grouping or aggregation must do so via explicit GROUP BY / filters, not via ordering.

The canonical order is binding for writers and for any engine-level digests; it is **not** a semantic contract for downstream code.

#### 7.4.2 `s1_party_summary_6A`

* A canonical sort order (e.g. `country_iso, segment_id, party_type`) should be used for writing, but:

  * downstream consumers must treat the summary as an unordered set keyed by its PK.

---

### 7.5 Merge discipline & lifecycle

S1 must behave as **replace-not-append** at the granularity of `(manifest_fingerprint, seed)`.

#### 7.5.1 Replace-not-append per world+seed

For each `(manifest_fingerprint, seed)`:

* `s1_party_base_6A` is **one complete population snapshot**:

  * It must represent the entire party universe for that world+seed.
  * Implementations must not rely on “append more parties later” semantics.

* If S1 is re-run for the same `(manifest_fingerprint, seed)` under the same `parameter_hash` and same sealed inputs:

  * the newly computed output set **must be byte-identical** to the existing one, or
  * S1 must fail with an “output conflict” error and leave the existing outputs unchanged.

No partial or incremental merges of two different S1 runs for the same `(manifest_fingerprint, seed)` are allowed.

#### 7.5.2 No cross-world or cross-seed merges

* **No cross-world merges:**

  * Populations from different `manifest_fingerprint`s must never be mixed; each world is hermetic.

* **No cross-seed merges within the same world:**

  * `seed` is a first-class identity axis.
  * Joining or aggregating across seeds may be done for meta-analysis, but **business semantics** (e.g. building accounts or flows) must treat each `(mf, seed)` as a separate, self-contained universe.

S2–S5 and 6B must always join S1 on `(manifest_fingerprint, seed, party_id)` as appropriate; any logic that conflates distinct seeds is out-of-spec.

---

### 7.6 Consumption discipline for downstream states

Downstream states **must honour** S1’s identity and merge discipline:

* **6A.S2–S5:**

  * For each `(manifest_fingerprint, seed)`:

    * must verify that `s1_party_base_6A` exists and is schema-valid,
    * must not create new parties; all accounts/products/devices/fraud roles must be attached to existing `party_id`s,
    * must treat `parameter_hash` on S1 rows as a consistency check; mismatches indicate a configuration error.

* **6B:**

  * When attaching arrivals to parties:

    * must only use `party_id` values that exist in `s1_party_base_6A` for the same `(manifest_fingerprint, seed)`,
    * must treat the absence of a `party_id` in the base as a modelling/implementation bug, not as “unknown party”.

* **Orchestration / tooling:**

  * must treat `(manifest_fingerprint, seed)` as the natural unit of S1 work and retries,
  * must not attempt to combine multiple S1 outputs for the same `(mf, seed)` with different `parameter_hash` or different priors.

These identity, partition, ordering, and merge rules are **binding**. Implementations can choose storage layout, query engines, or file formats freely, but they **cannot** change these semantics and still be considered a correct implementation of 6A.S1.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 6A.S1 is considered PASS**, which invariants **must hold on its outputs**, and how **downstream states** are required to gate on S1.

If any condition in this section fails, S1 is **FAIL for that `(manifest_fingerprint, seed)`**, and **no later 6A state (S2–S5) nor 6B is allowed to treat the S1 population as valid**.

---

### 8.1 Segment-local PASS / FAIL definition

For a given `(manifest_fingerprint, seed)`, 6A.S1 is **PASS** *iff* **all** of the following hold.

#### 8.1.1 S0 gate & upstream world

1. **S0 is structurally present and valid for the world:**

   * `s0_gate_receipt_6A` and `sealed_inputs_6A` exist for `manifest_fingerprint`.
   * Both datasets validate against their schema anchors.
   * Recomputing `sealed_inputs_digest_6A` from `sealed_inputs_6A` **exactly** matches the value in the gate receipt.

2. **S0 run-report says PASS:**

   * Latest 6A.S0 run-report for `manifest_fingerprint` has:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

3. **Upstream segments are sealed:**

   * In `s0_gate_receipt_6A.upstream_gates`, every required segment in `{1A,1B,2A,2B,3A,3B,5A,5B}` has:

     ```text
     gate_status == "PASS"
     ```

If any of these fail → S1 **must** report `6A.S1.S0_GATE_FAILED` (or equivalent) and **MUST NOT** generate any population for that world+seed.

---

#### 8.1.2 Priors & taxonomies

4. **Required priors and taxonomies are present and usable:**

   * For all artefacts S1 classifies as *required* in its design (e.g. global and regional `POPULATION_PRIOR`, `SEGMENT_PRIOR`, required `TAXONOMY` tables):

     * there is a corresponding row in `sealed_inputs_6A` with:

       ```text
       status     == "REQUIRED"
       read_scope == "ROW_LEVEL"
       ```

     * the artefact can be resolved via `path_template` and `partition_keys`,

     * it validates against its `schema_ref`,

     * and its `sha256_hex` matches the digest computed from its content.

   * Any required taxonomy entries (e.g. party types, segments) used in S1 outputs **must be present** in their taxonomy tables.

If any required prior/config/taxonomy is missing, invalid, or mis-scoped, S1 MUST fail with one of its prior-related codes (e.g. `6A.S1.PRIOR_PACK_MISSING`, `6A.S1.PRIOR_PACK_INVALID`, `6A.S1.PRIOR_PACK_DIGEST_MISMATCH`).

---

#### 8.1.3 Integer population realisation

5. **Continuous targets are well-formed:**

   * All computed `N_region_target(r)` and `N_cell_target(c)` are finite, non-negative reals.
   * Summations over regions and cells satisfy the configured tolerances against `N_world_target`.
   * No region or cell target is NaN/Inf or otherwise ill-defined.

6. **Integer counts conserve population:**

   After integerisation:

   * For each region `r` (if regions are used):

     ```text
     Σ_c in region r N_cell(c) == N_region(r)
     ```

   * Overall:

     ```text
     Σ_c N_cell(c) == N_world_int
     ```

   * Every `N_cell(c)` is a non-negative integer.

7. **Non-zero population constraints (if configured):**

   * If priors/config dictate that certain regions/segments *must* have non-zero population (e.g. `min_parties_per_cell > 0`), those constraints must be honoured.
   * If the design allows truly empty populations for some cells, S1 must respect those rules and not produce parties where priors prohibit them.

Violations here should surface as e.g. `6A.S1.TARGET_COUNTS_INCONSISTENT`, `6A.S1.POPULATION_INTEGERISATION_FAILED`, or `6A.S1.POPULATION_ZERO_WHEN_DISALLOWED`.

---

#### 8.1.4 Base table correctness

8. **Base table schema and key invariants:**

   * `s1_party_base_6A` exists at the expected path and partitioning for `(seed, manifest_fingerprint)`.
   * It validates against `schemas.6A.yaml#/s1/party_base`.
   * The logical primary key `(manifest_fingerprint, seed, party_id)` is unique:

     * no duplicate `party_id` within the same `(manifest_fingerprint, seed)`,
     * all rows in the partition share the correct `manifest_fingerprint` and `seed`.

9. **Base table matches realised counts:**

   * For each population cell `c` chosen by S1’s grouping (e.g. `(region, party_type, segment_id)`):

     ```text
     count_rows_in_base(c) == N_cell(c)
     ```

   * Summing `count_rows_in_base(c)` over all cells equals `N_world_int`.

10. **Taxonomy compatibility:**

    * Every `party_type`, `segment_id`, `region_id` / `country_iso`, and any other code emitted in the base table:

      * exists in the corresponding taxonomy,
      * respects any compatibility rules (e.g. some segments only valid for certain party_types or regions).

    * No “unknown” or out-of-domain codes appear in the base.

11. **Attribute constraints:**

    * Any attribute-level constraints encoded in priors (e.g. “no high-income STUDENT segments”, “SME only for `party_type=BUSINESS`”) are enforced across the base.
    * Violations are treated as state failures (e.g. `6A.S1.SEGMENT_ASSIGNMENT_INVALID`, `6A.S1.REGION_ASSIGNMENT_INVALID`).

---

#### 8.1.5 Summary table correctness (if present)

12. **Summary table is consistent with base:**

    * If `s1_party_summary_6A` is implemented:

      * it exists and validates against `schemas.6A.yaml#/s1/party_summary`,

      * its partitioning and world/seed columns are correct,

      * for each group key `g` in the summary:

        ```text
        party_count(g) == count_rows_in_base(matching g)
        ```

      * aggregating `party_count` over all groups equals the total rows in `s1_party_base_6A`.

Any discrepancy between base and summary is a failure of S1.

---

#### 8.1.6 RNG accounting

13. **RNG usage is accounted and within budget:**

* All uses of randomness in S1:

  * go through the designated RNG families (e.g. `party_count_realisation`, `party_attribute_sampling`),
  * are logged with proper before/after counters and `blocks`/`draws` metadata,
  * are consistent with the Layer-3 RNG envelope spec.

* Aggregate RNG metrics from:

  * S1-specific RNG event tables, and
  * the layer-wide RNG logs,

  must reconcile:

  * number of events,
  * total draws,
  * no overlapping or out-of-order counter ranges.

Any mismatch here is a hard failure (e.g. `6A.S1.RNG_ACCOUNTING_MISMATCH`).

---

### 8.2 Gating obligations for downstream 6A states (S2–S5)

For each `(manifest_fingerprint, seed)`, **S2–S5 MUST treat S1 as a hard precondition**:

Before doing any work, a downstream 6A state **MUST**:

1. Confirm S0 PASS for the world (as per S2/S3 spec) **and**:

2. Confirm S1 PASS for that `(mf, seed)` by:

   * locating the latest 6A.S1 run-report record for that `(mf, seed)`,

   * checking:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

   * verifying that `s1_party_base_6A` exists and validates against its schema.

3. Refuse to proceed if:

   * the S1 run-report is missing,
   * `status != "PASS"`, or
   * S1 outputs are missing or malformed.

Additionally, S2–S5 must respect S1’s **ownership** of the party universe:

* They **MUST NOT** create new parties (no new `party_id`s).
* They **MUST NOT** change S1’s static attributes; they may only read them as context.
* They **MUST** join to S1 on `(manifest_fingerprint, seed, party_id)` to attach accounts, products, devices, graph edges, and fraud roles.

If a downstream state detects that a `party_id` referenced in its own outputs is missing from `s1_party_base_6A` for the same `(mf, seed)`, it must treat this as an error and fail, not silently create or discard parties.

---

### 8.3 Gating obligations for 6B and external consumers

6B (and any other external consumer that works with parties) **MUST**:

1. Require both:

   * S0 PASS for the world, and
   * S1 PASS for the world+seed,

   as reflected in their respective run-reports.

2. Treat `s1_party_base_6A` as the **sole authority** on:

   * which `party_id`s exist for `(mf, seed)`,
   * how they are typed (retail/business/other), segmented, and located.

3. Refuse to run any arrival→entity attachment logic if:

   * S1 has not run or failed,
   * `s1_party_base_6A` is missing or corrupt,
   * or there is any inconsistency between S1 outputs and the world identity.

6B may optionally consume `s1_party_summary_6A` for sizing and validation, but must never treat it as a replacement for the base table.

---

### 8.4 Behaviour on failure & partial outputs

If S1 fails for a given `(manifest_fingerprint, seed)`:

* Any partially written `s1_party_base_6A` / `s1_party_summary_6A` **must not** be treated as valid:

  * downstream states must consider that world+seed as having **no S1 population**,
  * orchestration may clean up or quarantine partial outputs, but must not use them.

* The 6A.S1 run-report record **must** be updated with:

  * `status = "FAIL"`,
  * the appropriate `error_code` from the S1 error namespace,
  * a short `error_message`.

No state is permitted to “limp on” by partially using S1 outputs after a failure; the only valid behaviours are:

* **S1 PASS →** S2–S5 and 6B may run for that `(mf, seed)`.
* **S1 FAIL →** S2–S5 and 6B must not run for that `(mf, seed)` until S1 is re-run and PASS.

These acceptance criteria and gating obligations are **binding** and define what “S1 is done and safe to build on” means for the rest of Layer-3.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error surface** for 6A.S1.

Every failure for a given `(manifest_fingerprint, seed)` **must** be mapped to exactly one of these codes.
All are:

* **Fatal** for S1 for that `(manifest_fingerprint, seed)`.
* **Blocking** for S2–S5 and 6B for that `(manifest_fingerprint, seed)`.

No “best effort” downgrade is allowed.

---

### 9.1 Error class overview

We group failures into six classes:

1. **Gate / sealed-input errors** — problems with S0 or sealed inputs.
2. **Prior & taxonomy errors** — missing/bad priors or taxonomies.
3. **Target derivation & integerisation errors** — inconsistent or invalid population counts.
4. **Base-table & attribute errors** — invalid or inconsistent `s1_party_base_6A`.
5. **RNG & accounting errors** — misuse or mis-accounting of randomness.
6. **IO / identity / internal errors** — storage conflicts or unexpected failures.

Each error has a stable code in the `6A.S1.*` namespace.

---

### 9.2 Canonical error codes

#### 9.2.1 Gate / sealed-input errors

These mean S1 cannot trust the world-level gate or its own input universe.

* `6A.S1.S0_GATE_FAILED`
  *Meaning:* S0 is missing or not PASS for this `manifest_fingerprint`, or the recomputed `sealed_inputs_digest_6A` does not match the value in `s0_gate_receipt_6A`, or one or more required upstream segments `{1A,1B,2A,2B,3A,3B,5A,5B}` have `gate_status != "PASS"`.

* `6A.S1.SEALED_INPUTS_MISSING_REQUIRED`
  *Meaning:* One or more artefacts that S1 considers **required** (e.g. a population prior, a taxonomy table) do not appear in `sealed_inputs_6A` for this `manifest_fingerprint`.

* `6A.S1.SEALED_INPUTS_SCOPE_INVALID`
  *Meaning:* A required artefact appears in `sealed_inputs_6A`, but with an incompatible `read_scope` or `status` (e.g. `read_scope="METADATA_ONLY"` where S1 needs `ROW_LEVEL`, or `status="IGNORED"` for an artefact S1 expects to use).

These codes all mean: **“S1 cannot even start; the input universe is not correctly sealed.”**

---

#### 9.2.2 Prior & taxonomy errors

These indicate that the **6A priors/configs needed for population and segmentation are not usable**.

* `6A.S1.PRIOR_PACK_MISSING`
  *Meaning:* A required prior/config artefact (e.g. a population prior or segmentation prior) referenced in `sealed_inputs_6A` cannot be resolved from the catalogue for this `manifest_fingerprint`/`parameter_hash`.

* `6A.S1.PRIOR_PACK_INVALID`
  *Meaning:* A required prior/config artefact is present but fails validation against its `schema_ref` (structural or type errors).

* `6A.S1.PRIOR_PACK_DIGEST_MISMATCH`
  *Meaning:* The SHA-256 digest computed from a prior/config artefact does not match `sha256_hex` recorded in `sealed_inputs_6A` (and/or the registry, where applicable).

* `6A.S1.TAXONOMY_MISSING_OR_INVALID`
  *Meaning:* A required taxonomy artefact (party types, segments, region codes, etc.) is missing or invalid (schema failure or missing required labels).

These mean: **“S1 cannot trust the priors/taxonomies that define who should exist.”**

---

#### 9.2.3 Target derivation & integerisation errors

These indicate S1 cannot derive a sane or consistent population from the priors.

* `6A.S1.TARGET_COUNTS_INCONSISTENT`
  *Meaning:* Continuous targets `N_world_target`, `N_region_target`, or `N_cell_target` are inconsistent or ill-formed; e.g.:

  * negative or NaN/Inf values,
  * sums over regions or cells are outside tolerated bounds,
  * required regions/cells are missing from the domain.

* `6A.S1.POPULATION_INTEGERISATION_FAILED`
  *Meaning:* Converting continuous targets into integer counts failed to satisfy conservation or non-negativity constraints; e.g.:

  * some `N_cell(c) < 0`,
  * Σ counts per region does not equal the region total,
  * global Σ cell counts doesn’t match the intended integer total.

* `6A.S1.POPULATION_ZERO_WHEN_DISALLOWED`
  *Meaning:* Priors or configuration indicate that a region/segment/type combination must have non-zero population (e.g. `min_parties_per_cell > 0`), but integerisation produced zero parties for that cell.

These mean: **“we could not consistently realise a population from the priors; don’t trust any downstream entities.”**

---

#### 9.2.4 Base-table & attribute errors

These indicate that the **materialised `s1_party_base_6A` is not a valid population** for that world+seed.

* `6A.S1.BASE_TABLE_SCHEMA_OR_KEY_INVALID`
  *Meaning:* `s1_party_base_6A` exists but:

  * fails validation against `schemas.6A.yaml#/s1/party_base`, or
  * violates the PK/uniqueness constraint `(manifest_fingerprint, seed, party_id)`.

* `6A.S1.BASE_TABLE_COUNT_MISMATCH`
  *Meaning:* Aggregating `s1_party_base_6A` by S1’s cell grouping does not match the integer counts realised in S1’s internal population plan (`N_cell(c)`); or the total number of rows does not equal `Σ_c N_cell(c)`.

* `6A.S1.TAXONOMY_COMPATIBILITY_FAILED`
  *Meaning:* Base-table codes (party_type, segment_id, region_id/country_iso, etc.) are inconsistent with taxonomies; e.g.:

  * unknown codes,
  * segment used with an invalid party_type or region,
  * codes that violate explicit compatibility rules.

* `6A.S1.SEGMENT_ASSIGNMENT_INVALID`
  *Meaning:* Attribute combinations in the base table violate segmentation rules/priors; e.g.:

  * segments with zero prior probability in a particular region/type,
  * segments whose realised shares are outside explicit bounds (where the spec requires enforcement, not just reporting).

* `6A.S1.REGION_ASSIGNMENT_INVALID`
  *Meaning:* Party home geography assignments violate configured rules; e.g.:

  * parties assigned to regions that do not exist in priors,
  * region splits inconsistent with required constraints.

These mean: **“the base table is not a faithful or valid instance of the population plan or taxonomies.”**

---

#### 9.2.5 RNG & accounting errors

These indicate that S1’s randomness **cannot be trusted**.

* `6A.S1.RNG_ACCOUNTING_MISMATCH`
  *Meaning:* Recorded RNG events for `party_count_realisation` and/or `party_attribute_sampling` do not reconcile with expectations:

  * missing or extra events,
  * overlapping or out-of-order Philox counter ranges,
  * total draws/blocks outside configured budgets.

* `6A.S1.RNG_STREAM_CONFIG_INVALID`
  *Meaning:* RNG configuration for S1 (e.g. stream labels, seeding policy, event-family registration) is missing or inconsistent with the Layer-3 RNG envelope.

These mean: **“we cannot reproduce or audit the randomness behind the population; the run is not trustworthy.”**

---

#### 9.2.6 IO / identity / internal errors

These indicate storage or generic runtime failures.

* `6A.S1.IO_READ_FAILED`
  *Meaning:* S1 couldn’t read a required artefact (priors, taxonomies, S0 gate, sealed inputs, or catalogue entries) due to IO issues (permissions, network, corruption) even though the catalogue claims it exists.

* `6A.S1.IO_WRITE_FAILED`
  *Meaning:* S1 attempted to write `s1_party_base_6A` or `s1_party_summary_6A` (if present) and the write could not be completed atomically or durably.

* `6A.S1.OUTPUT_CONFLICT`
  *Meaning:* Existing S1 outputs for `(manifest_fingerprint, seed)` are present and are **not** byte-identical to what S1 would produce given the current inputs (violating the replace-not-append and idempotency rules).

* `6A.S1.INTERNAL_ERROR`
  *Meaning:* An unexpected, non-classified error occurred (e.g. assertion failure, unhandled exception) and cannot be cleanly mapped into any of the more specific codes. This should be rare and treated as an implementation bug.

These all mean: **“this S1 run failed structurally; do not use its outputs for this world+seed.”**

---

### 9.3 Mapping detection → error code

Implementations **must** map detected failures to these codes deterministically. Examples:

* S0 gate missing / digest mismatch → `6A.S1.S0_GATE_FAILED`.
* Required population prior hasn’t got a `sealed_inputs_6A` row → `6A.S1.SEALED_INPUTS_MISSING_REQUIRED`.
* Prior file present but schema-invalid → `6A.S1.PRIOR_PACK_INVALID`.
* Target sums don’t match within tolerance → `6A.S1.TARGET_COUNTS_INCONSISTENT`.
* Integerisation yields negative or non-conserving counts → `6A.S1.POPULATION_INTEGERISATION_FAILED`.
* Some cell required to be non-empty ends up with `N_cell(c)=0` → `6A.S1.POPULATION_ZERO_WHEN_DISALLOWED`.
* `party_id` duplicates detected → `6A.S1.BASE_TABLE_SCHEMA_OR_KEY_INVALID`.
* Base-table counts don’t match plan → `6A.S1.BASE_TABLE_COUNT_MISMATCH`.
* RNG trace doesn’t match expected draws/events → `6A.S1.RNG_ACCOUNTING_MISMATCH`.
* Trying to overwrite an existing, different S1 output → `6A.S1.OUTPUT_CONFLICT`.

If an implementation cannot find a specific code that matches, it must fall back to `6A.S1.INTERNAL_ERROR` and the spec should be extended later, rather than silently inventing new codes.

---

### 9.4 Run-report integration & propagation

On any S1 run for `(manifest_fingerprint, seed)`:

* The S1 run-report record **must** include:

  * `state_id = "6A.S1"`,
  * `manifest_fingerprint`, `parameter_hash`, `seed`,
  * `status ∈ {"PASS","FAIL"}`,
  * `error_code` (empty/null on PASS; one of the codes above on FAIL),
  * `error_message` (short, human-readable, non-normative).

* On **FAIL**, S1:

  * MUST NOT mark the population as usable,
  * MUST NOT be treated as gating-success by any downstream state.

Downstream S2–S5 and 6B **must**:

* check this run-report before using S1 outputs,
* refuse to proceed if `status != "PASS"`, regardless of whether `s1_party_base_6A` files happen to exist.

The error codes here are designed to be the **primary machine-readable signal** of S1’s failure modes; raw logs and stack traces are for debugging only and are not part of the contract.

---

## 10. Observability & run-report integration *(Binding)*

6A.S1 is a **core modelling state** for Layer-3. Its status and key metrics **must** be visible and machine-readable so that:

* S2–S5 and 6B can safely gate on it, and
* operators can understand “what population did we actually generate for this world+seed?”.

This section fixes **what S1 must report**, how it is **keyed**, and how **downstream** components must use it.

---

### 10.1 Run-report record for 6A.S1

For every attempted S1 run on a `(manifest_fingerprint, seed)`, the engine **MUST** emit exactly one run-report record with at least the following fields:

* **Identity**

  * `state_id = "6A.S1"`
  * `manifest_fingerprint`
  * `parameter_hash`
  * `seed`
  * `engine_version`
  * `spec_version_6A` (includes S1 spec version)

* **Execution envelope**

  * `run_id` (non-semantic execution identifier)
  * `started_utc` (RFC 3339 with micros)
  * `completed_utc` (RFC 3339 with micros)
  * `duration_ms` (derived)

* **Status & error**

  * `status ∈ { "PASS", "FAIL" }`
  * `error_code` (empty/null for PASS; one of the §9 codes for FAIL)
  * `error_message` (short, human-oriented explanation; non-normative)

* **Core population metrics**

  At minimum:

  * `total_parties` — total number of rows in `s1_party_base_6A` for this `(mf, seed)`.
  * `parties_by_region` — map/array summarising `party_count` per `region_id` or `country_iso` (using the grouping chosen in the spec).
  * `parties_by_segment` — summary of counts per `segment_id` (optionally broken down by `party_type`).
  * `parties_by_party_type` — summary counts per `party_type`.

* **Priors / plan metrics**

  * `N_world_target` — continuous world population target used in Phase 2.
  * `N_world_int` — realised integer total from Phase 3.
  * Optional summary stats of `N_region_target` and `N_region` (e.g. min/mean/max over regions).

* **RNG metrics**

  * `rng_party_count_events` — number of RNG events emitted for `party_count_realisation`.
  * `rng_party_count_draws` — total draws for that family.
  * `rng_party_attribute_events` — number of RNG events for `party_attribute_sampling`.
  * `rng_party_attribute_draws` — total draws for that family.

This record is **binding**: downstream code must not try to infer S1 success/failure solely from the presence of data files.

---

### 10.2 PASS vs FAIL semantics in the run-report

* For **PASS**:

  * `status == "PASS"`
  * `error_code` is empty or null
  * `total_parties` and the summary metrics **must** be consistent with what you would compute from `s1_party_base_6A` (they are hints, but must not lie).

* For **FAIL**:

  * `status == "FAIL"`
  * `error_code` is one of the canonical `6A.S1.*` codes from §9
  * `total_parties` and other metrics may be omitted or set to a sentinel (e.g. `0`); they are not authoritative.
  * Downstream states must never treat a FAIL record as “good enough to proceed”.

Implementations **must not** report `status="PASS"` while omitting `error_code` and required metrics; a PASS record is a strong statement that S1 population for `(mf, seed)` is complete and usable.

---

### 10.3 Relationship between run-report and S1 datasets

For a **PASS** S1 run on `(manifest_fingerprint, seed)`:

* There **must exist** a corresponding partition of `s1_party_base_6A` (and `s1_party_summary_6A` if implemented) that:

  * validates against its schema anchor(s),
  * has row counts and grouped counts matching the metrics in the run-report.

* The run-report’s `total_parties` **must** equal `COUNT(*)` over `s1_party_base_6A` for that `(mf, seed)`.

For **FAIL**:

* `s1_party_base_6A` and `s1_party_summary_6A` (if present) **must not** be considered authoritative for that `(mf, seed)`:

  * downstream components must use the run-report status to decide, not just the presence of files,
  * orchestration may clean up/quarantine partially written datasets, but they should not be read.

---

### 10.4 Gating behaviour in downstream states

All 6A downstream states (S2–S5) and 6B **MUST** integrate S1’s run-report into their own gating logic.

Before using S1 outputs for `(manifest_fingerprint, seed)`, a downstream state must:

1. Locate the **latest** 6A.S1 run-report record for that `(mf, seed)`.

2. Check:

   ```text
   status     == "PASS"
   error_code == "" or null
   ```

3. Confirm that `s1_party_base_6A` exists, is schema-valid, and has `COUNT(*) == total_parties` from the run-report.

If any of these checks fails, the downstream state **must not**:

* read or rely on `s1_party_base_6A` or `s1_party_summary_6A` for that `(mf, seed)`,
* proceed to generate accounts, products, devices, IPs, fraud roles, or flows.

Instead it must fail with a state-local gating error (e.g. `6A.S2.S1_GATE_FAILED`, `6B.S0.S1_GATE_FAILED`).

---

### 10.5 Additional observability (recommended but non-semantic)

While not binding for correctness, implementations **should** also:

* Record simple histograms or percentiles for:

  * `parties_per_region`, `parties_per_segment`,
  * any notable attribute distributions (e.g. lifecycle stage, income bands) to help detect skew.

* Log at INFO level, per S1 run:

  * `(manifest_fingerprint, seed, parameter_hash)`,
  * `status`, `error_code`,
  * `total_parties`,
  * key distribution summaries (e.g. top N segments by count).

* Log at DEBUG level:

  * lists of cells where realised counts deviate from priors beyond configured tolerances (for QA),
  * detailed RNG accounting checks when troubleshooting.

These are **operational tools**, not part of the formal spec; formats may change as long as the binding run-report semantics above are maintained.

---

### 10.6 Integration with higher-level monitoring

Higher-level monitoring and dashboards **MUST** be able to summarise S1’s health across worlds and seeds, for example:

* per `manifest_fingerprint`:

  * S1 status per seed (PASS/FAIL/MISSING),
  * total parties per seed,
  * simple region/segment breakdowns.

* cross-world views:

  * distribution of `total_parties` across worlds,
  * counts of S1 FAILs by error code.

The goal is that, from observability alone, an operator can answer:

> “For this world and seed, did we successfully generate a population, how big is it, and how is it distributed?”

without needing to manually inspect S1’s data files.

All of the above observability requirements are **binding** for S1’s run-report surface, and form part of what it means for 6A.S1 to be correctly integrated into the engine.

---

## 11. Performance & scalability *(Informative)*

6A.S1 is the first **data-heavy** state in Layer-3: it can easily create millions of parties per world+seed. This section is non-binding, but it describes the expected scale profile and design considerations so an implementation doesn’t accidentally turn S1 into the bottleneck of the engine.

---

### 11.1 Complexity profile

For a given `(manifest_fingerprint, seed)`:

* Let:

  * `R` = number of regions/countries in the population priors domain.
  * `T` = number of party types (usually small: retail/business/other).
  * `S` = number of segments.
  * `C` = number of population cells = |{(region, type, segment) combinations that are allowed}|.
  * `N` = realised total parties (`N_world_int`).

Then the main phases scale roughly as:

* **Phase 1 – load priors/taxonomies:**

  * O(R + S + size of prior/config tables) — usually small compared with N.

* **Phase 2 – continuous targets:**

  * O(C) — per cell arithmetic.

* **Phase 3 – integerisation:**

  * O(C) — plus multicell RNG calls; negligible compared with per-party work.

* **Phase 4 – party construction & attributes:**

  * O(N) time and O(k) memory overhead, where `k` is the number of attributes per party (constant).
  * This phase dominates S1 for large populations.

* **Phase 5 – writing outputs:**

  * O(N) for serialisation and IO to `s1_party_base_6A` (plus O(C) for an optional summary).

So S1’s cost is essentially **linear in the number of parties `N`**; priors and targets are cheap by comparison.

---

### 11.2 Expected sizes & regime

You should expect the following orders of magnitude (non-binding):

* **Priors & taxonomies:**

  * Rows: O(10²–10³) per prior table (countries × segments × types).
  * Negligible compared with party rows.

* **Party base (`s1_party_base_6A`):**

  * Small test worlds: O(10⁴ – 10⁵) parties.
  * Realistic “bank-sized” worlds: O(10⁶ – 10⁸) parties per `(mf, seed)` depending on model ambition.
  * Beyond ~10⁸, you are intentionally exploring extreme scale and should plan accordingly.

* **Summary table (`s1_party_summary_6A`):**

  * Rows: O(C) (since it aggregates the base).
  * Typically O(10²–10³), negligible in IO and memory.

The design assumes that **upstream worlds** (L1/L2) are already scaled to handle similar orders of magnitude (e.g. 10⁶–10⁹ arrivals over a horizon, many sites/merchants), so S1 should be engineered not to become the new ceiling.

---

### 11.3 Parallelism & sharding

S1 lends itself naturally to parallelisation:

* **Across seeds:**

  * Each `(mf, seed)` defines an independent universe; runs for different seeds can be fully parallel.
  * This is the primary axis for scaling out S1 horizontally.

* **Across regions/cells within a seed:**

  * Integerisation and party generation per population cell can be parallelised per region or per cell bucket:

    * Phase 3: integerisation per region can be done in parallel,
    * Phase 4: party rows per region/cell can be generated and flushed independently.

  * Care is needed to maintain deterministic ordering and ID assignment; typically you fix a global ordering of cells and generate in that order even if execution is parallel under the hood.

* **Streaming generation:**

  * Implementation can generate and write parties **batch-by-batch** (per region or per group of cells), rather than holding all `N` rows in memory:

    * stream out Parquet/ORC row groups incrementally,
    * keep only a small working buffer per worker.

As long as:

* the canonical writer ordering is preserved, and
* RNG counters are allocated deterministically per cell,

parallelism does not affect semantics.

---

### 11.4 Memory & IO considerations

**Memory:**

* Priors/taxonomies: small; can be fully cached in memory.
* Population plan (`N_cell(c)`): size O(C), easily kept in memory.
* Party rows: should be **streamed**, not fully buffered.

Recommended approach:

* Use a streaming / chunked writer for `s1_party_base_6A`, emitting parties in canonical order as they are generated.
* Keep per-cell or per-region queues small (bounded by a configurable batch size).
* Avoid data structures that require holding the entire population (N rows) in RAM at once.

**IO:**

* Read side:

  * dominated by priors/configs and any optional context tables; usually tiny compared with L2 data.
  * can be cached across seeds if priors are parameter-scoped rather than world-scoped.

* Write side:

  * dominated by `s1_party_base_6A`, which is essentially a full scan of N rows.
  * use columnar formats and compression to minimise disk / object-store footprint.

Because S1 is write-heavy, you should ensure the underlying storage system has enough throughput for the target N and expected execution window.

---

### 11.5 RNG cost and accounting

RNG is conceptually “cheap” compared with IO, but in extreme N regimes it may matter:

* **Count realisation:**

  * RNG cost scales with `C` (cells); typically negligible even for large worlds.

* **Attribute sampling:**

  * RNG cost scales with N and the number of attributes per party.
  * If each party draws a handful of categorical attributes, you can expect O(N × A) uniform draws (plus any transforms).

Design guidance:

* Use **vectorised** RNG where possible (e.g. generating multiple uniforms per call/batch) while still respecting the Philox counter discipline.
* Ensure RNG accounting structures are efficient to update (append-only logs, minimal per-event overhead).

The RNG envelope and trace logs are primarily about **auditability**, not resource constraints; but implementations should still ensure they do not become bottlenecks.

---

### 11.6 Operational levers for tuning

To support different environments (local dev, CI, staging, production), you can expose non-semantic **tuning knobs** for S1:

* **Population scale factor** per world/seed:

  * a configuration that scales `N_world_target` up or down (e.g. 0.01× for local tests, 1× for production-grade runs),
  * as long as the scale factor is encoded in the priors / parameter pack and therefore reflected in `parameter_hash`.

* **Maximum parties per seed**:

  * a hard cap to prevent runaway populations (e.g. misconfigured priors); runs that breach the cap should fail clearly, not silently truncate.

* **Sharding strategies**:

  * per-region or per-party-type sharding for parallel execution,
  * with deterministic cell ordering to preserve bit-stable outputs.

These knobs should be part of the 6A configuration / priors and therefore included in the S0 sealed input universe, not ad-hoc flags.

---

### 11.7 Behaviour in stress and failure scenarios

Under unexpected conditions (e.g. huge N due to misconfigured priors, slow storage, or constrained CPUs), you should expect:

* **Longer runtimes** proportional to N.
* Potential pressure on:

  * storage bandwidth (writing large base tables),
  * scheduler queues (if many worlds/seeds are queued).

Recommended practice:

* Treat S1 as a **visible stage** in orchestration:

  * use its run-report metrics (total_parties, parties_by_region/segment) to spot unusual spikes early.
* In CI / development:

  * use smaller N or fewer seeds,
  * but keep the same structure (regions, segments, priors) so behaviour scales predictably.

None of the performance details above change S1’s formal contract; they are guidance to help keep 6A.S1 **practical** at realistic scales, while maintaining the deterministic, reproducible behaviour required by the binding sections.

---

## 12. Change control & compatibility *(Binding)*

This section fixes **how 6A.S1 is allowed to evolve** and what “compatible” means for:

* upstream segments (1A–3B, 5A–5B),
* downstream 6A states (S2–S5),
* 6B and any external consumers that rely on the party base.

Any change that violates these rules is a **spec violation**, even if an implementation appears to “work”.

---

### 12.1 Versioning model for S1

S1 participates in the 6A versioning stack:

* `spec_version_6A` — overall 6A spec version (S0–S5).

* `spec_version_6A_S1` — the effective version of this S1 section.

* Schema versions:

  * `schemas.6A.yaml#/s1/party_base`,
  * `schemas.6A.yaml#/s1/party_summary` (if present).

* Catalogue versions:

  * `dataset_dictionary.layer3.6A.yaml` (entries for S1 datasets),
  * `artefact_registry_6A.yaml` entries for S1 outputs and priors.

S1 **must** record enough information in its run-report (and optionally in S1 outputs) so that consumers can see:

* which `spec_version_6A` / `spec_version_6A_S1` produced the population, and
* which schema versions are in play.

---

### 12.2 Backwards-compatible changes (allowed within a major version)

The following are **backwards compatible**, provided all other binding sections remain satisfied:

1. **Add optional fields to S1 outputs**

   * Adding new, optional columns to `s1_party_base_6A` or `s1_party_summary_6A` **without** changing the meaning of existing fields:

     * examples: extra static attributes, additional “tag” fields, optional QA flags,
     * older consumers can safely ignore them.

2. **Add new attribute values / taxonomy entries**

   * Extending taxonomies (segments, party types, regions) with **additional allowed values** that:

     * obey existing type compatibility rules,
     * do not invalidate existing codes.

   * Existing consumers should be written to ignore **unknown enum values** or treat them as generic segments until upgraded.

3. **Refine priors without changing semantics**

   * Updating values in prior packs (e.g. changing `π_segment|region` numbers) while **keeping the same structure and interpretation** is allowed:

     * this changes the realised population statistics, but not the meaning of fields or the S1 identity rules.

4. **Performance/implementation improvements**

   * Caching, parallelism, streaming, or IO-layer optimisations that:

     * do not change S1 outputs or run-report semantics, and
     * do not change RNG family mapping or event semantics.

Backwards-compatible changes typically bump **minor/patch** components of `spec_version_6A` / `spec_version_6A_S1` and/or schema `semver`, but do not require changes in downstream consumers beyond the usual “ignore unknown fields” behaviour.

---

### 12.3 Soft-breaking changes (require coordination, but can be staged)

The following changes are **not strictly breaking** if managed carefully, but require coordination and explicit version checks:

1. **New required attributes in the base schema**

   * Adding a new **required** column to `s1_party_base_6A` (e.g. `lifecycle_stage` becoming mandatory) is only safe if:

     * downstream consumers are updated to understand it, or
     * the change is staged:

       * first introduce the field as optional,
       * ensure all consumers are version-aware,
       * then upgrade the schema to make it required.

2. **New priors / constraints that must be enforced**

   * Introducing new priors that enforce hard constraints (e.g. max/min party counts per cell, mandatory non-zero populations, new compatibility rules between attributes):

     * S1 must start enforcing them,
     * downstream code that *assumes* looser distributions should be updated to pin to a minimum S1 version and/or detect the new constraints.

3. **New S1 outputs**

   * Adding new S1 datasets (e.g. additional diagnostic tables) is safe if:

     * they are declared in the dictionary/registry,
     * they are clearly marked as `status: optional`,
     * consumers treat them as optional.

These changes should bump **minor** version and come with explicit compatibility notes. Consumers must check `spec_version_6A` (or a dedicated S1 version field) and branch if needed.

---

### 12.4 Breaking changes (require major version bump)

The following are **breaking changes** and must not be introduced without:

* a **major version bump** to `spec_version_6A` / `spec_version_6A_S1`,
* schema/registry updates, and
* explicit migration guidance for downstream states.

1. **Changing identity or partitioning**

   * Modifying primary key semantics (e.g. dropping `seed` or `manifest_fingerprint` from the PK).
   * Changing partitioning for `s1_party_base_6A` (e.g. removing `seed` or adding new partition keys).
   * Renaming `party_id` or changing its uniqueness semantics.

2. **Changing the meaning of core fields**

   * Reinterpreting `party_type`, `segment_id`, `region_id` / `country_iso`, or `parameter_hash` in ways that change business meaning.
   * Reusing existing codes for completely different segments/types (taxonomy-breaking changes).

3. **Changing the population realisation law**

   * Changing the high-level law that maps priors → integer counts → base table, in ways that break downstream assumptions, for example:

     * introducing scenario-dependent populations where S1 was originally scenario-independent,
     * shifting from “one party base per `(mf, seed)`” to multiple, overlapping populations.

   * Changing the **RNG family mapping** (e.g. `party_count_realisation` semantics) such that the same inputs and seed would produce different distributions is also considered breaking at the behavioural level.

4. **Changing digest/compatibility with S0 and run-report surfaces**

   * Removing or renaming required fields in the S1 run-report.
   * Changing how `total_parties` or other key metrics are defined, in ways that break existing consumers.

Any of these changes require:

* explicit spec updates,
* a major version bump,
* and downstream states (S2–S5, 6B) to reject worlds with older/newer S1 versions they do not explicitly support.

---

### 12.5 Compatibility obligations for downstream states

Downstream 6A states and 6B have explicit responsibilities:

1. **Version pinning**

   * Each state (S2–S5, 6B) must declare a **minimum supported S1 spec version** (or `spec_version_6A` band).
   * Before consuming S1 outputs, they must check the S1 run-report:

     * if S1’s version is older than the minimum → gate fail (`S1 version too old`),
     * if S1’s version is newer and incompatible → either gate fail or run in a safe “legacy” mode, as defined.

2. **Ignore unknown fields gracefully**

   * Within a supported major version:

     * downstream code must ignore unfamiliar additional columns in `s1_party_base_6A` and `s1_party_summary_6A`,
     * it must not crash or misinterpret them.

3. **Do not hard-wire layout**

   * Downstream logic must not hard-code path layouts or assume fixed file naming within partitions.

     * Always resolve via dictionary/registry,
     * always discover the schema via `schema_ref` → schema file.

4. **Do not re-encode semantics**

   * Downstream specs or code must not redefine what fields like `party_type`, `segment_id`, `region_id` mean; they must rely on the S1/6A taxonomies.

---

### 12.6 Migration & co-existence strategy

When a **breaking S1 change** is introduced:

* It should be rolled out as a **new major version** of `spec_version_6A` / `spec_version_6A_S1`.

* In environments that need to support multiple worlds:

  * Worlds can be tagged in the catalogue with their 6A spec version,
  * Orchestration can decide which worlds are eligible for which downstream pipelines,
  * Downstream states may support:

    * both old and new versions (dual-mode), or
    * only one version and reject the other.

This is a deployment concern, but the contract here ensures:

* a world is always internally consistent with a single S1 spec version, and
* consumers know what they are getting.

---

### 12.7 Non-goals

This section does **not** attempt to:

* constrain how often S1 priors are updated (that is a modelling decision),
* version upstream segments (1A–3B, 5A–5B),
* define CI/CD pipelines or branching strategies.

It **does** require that:

* any observable change in S1 behaviour is **versioned**,
* downstream code never assumes compatibility purely from context,
* and any breaking shift in S1’s identity, semantics, or RNG law is treated as a deliberate, coordinated version change rather than a silent drift.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the short-hands and symbols used in **6A.S1** so you don’t have to reverse-engineer them from the text. If anything here appears to contradict the binding sections (§1–§12), the binding sections (and the JSON-Schemas) win.

---

### 13.1 Identity axes

* **`mf`**
  Shorthand for **`manifest_fingerprint`**.
  The world identity — pins S1 to a specific upstream Layer-1/Layer-2 world and S0 sealed input universe.

* **`ph`**
  Shorthand for **`parameter_hash`**.
  Identifies the parameter / prior pack set (population priors, segmentation priors, etc.) that S1 uses.

* **`seed`**
  RNG identity for S1 (and Layer-3 more broadly). Different seeds under the same `(mf, ph)` define different party universes.

* **`party_id`** (or `customer_id`)
  Stable identifier for a single party/customer within `(mf, seed)`.
  S1 guarantees uniqueness of `(mf, seed, party_id)`.

---

### 13.2 Population & cell notation

Let:

* **`R`** — set of regions (or countries), e.g. region IDs or ISO country codes.
* **`T`** — set of party types (e.g. `RETAIL`, `BUSINESS`, etc.).
* **`S`** — set of segments (e.g. `STUDENT`, `SALARIED`, `SME`, `CORPORATE`, …).
* **`C`** — set of **population cells** S1 uses, typically tuples:

  ```text
  c ∈ C  ≔  (region_id, party_type, segment_id)
  ```

Core scalars/vectors:

* **`N_world_target`**
  Continuous target total population (real) implied by priors.

* **`N_world_int`**
  Realised integer total number of parties after integerisation.

* **`π_region(r)`**
  Region share; fractional prior over regions (`Σ_r π_region(r) = 1`).

* **`π_type|region(r, t)`**
  Fractional split of party types given region.

* **`π_segment|region,type(r, t, s)`**
  Fractional segment split given region and party type.

* **`N_region_target(r)`**
  Continuous target population for region `r`.

* **`N_region(r)`**
  Realised integer population in region `r` (after integerisation).

* **`N_cell_target(c)`**
  Continuous target for cell `c`.

* **`N_cell(c)`**
  Realised integer count for cell `c` (how many parties S1 will generate in that cell).

---

### 13.3 Taxonomy & attribute symbols

* **`party_type`**
  Enum field for high-level party classification (e.g. `RETAIL`, `BUSINESS`, `OTHER`) — values come from a 6A taxonomy.

* **`segment_id`**
  Enum field for customer segment (e.g. `STUDENT`, `SALARIED`, `SME`, `CORPORATE`), from the 6A segment taxonomy.

* **`segment_group` / `segment_family`**
  Optional higher-level grouping of segments (e.g. `RETAIL_CONSUMER`, `BUSINESS_CUSTOMER`).

* **`country_iso`**
  Party’s home country (ISO code), consistent with Layer-1 geography.

* **`region_id` / `region_group`**
  Optional supra-national or sub-national region identifier used in priors.

* **Examples of static attributes S1 may own** (names indicative, not binding):

  * `lifecycle_stage` — e.g. `STUDENT`, `EARLY_CAREER`, `MID_CAREER`, `RETIRED`.
  * `income_band` / `turnover_band` — banded income/revenue levels.
  * `customer_tenure_band` — e.g. `NEW`, `ESTABLISHED`, `LONG_TENURE`.
  * eligibility flags such as `eligible_for_business_products`.

All of these are **static** from S1’s perspective: later states may read them but must not change them.

---

### 13.4 Roles, status & scope in `sealed_inputs_6A`

These are values used in `sealed_inputs_6A.role`, `status`, and `read_scope` that S1 cares about.

* **`role`** (non-exhaustive, S1-relevant):

  * `POPULATION_PRIOR` — priors controlling total and regional/cell population.
  * `SEGMENT_PRIOR` — priors for segment mix per region/type.
  * `TAXONOMY` — code lists for party types, segments, regions, etc.
  * `UPSTREAM_EGRESS` — upstream datasets S1 might use as context (e.g. region surfaces).
  * `SCENARIO_CONFIG` — optional aggregate volume or scenario metadata.
  * `CONTRACT` — schemas / dictionaries / registries (metadata only).

* **`status`** (from S1’s point of view):

  * `REQUIRED` — S1 must have this artefact to run.
  * `OPTIONAL` — S1 can branch behaviour based on presence/absence.
  * `IGNORED` — artefact is not used by 6A.

* **`read_scope`**:

  * `ROW_LEVEL` — S1 is allowed to read rows from this artefact.
  * `METADATA_ONLY` — S1 may only rely on existence, schema, digests; no row-level reads.

S1 treats the intersection of `{REQUIRED, OPTIONAL}` and `ROW_LEVEL` entries with relevant `role`s as its effective input set.

---

### 13.5 RNG symbols

S1 uses the shared Layer-3 RNG envelope; these names describe **families**, not concrete APIs.

* **Philox-2x64-10**
  The underlying counter-based RNG engine (same as elsewhere in the engine).

* **Substream / label**
  A logical name used when deriving Philox keys for S1, e.g.:

  * `"6A.S1.party_count_realisation"`
  * `"6A.S1.party_attribute_sampling"`

* **`party_count_realisation`**
  RNG family used to realise integer counts from continuous targets (e.g. multinomial / binomial draws per region/cell).

* **`party_attribute_sampling`**
  RNG family used for sampling per-party attributes (segment-conditioned demographic bands, etc.).

* **`rng_event_*`**
  Logical event types for RNG logs, e.g.:

  * `rng_event_party_count`,
  * `rng_event_party_attribute`.

Each event records:

* `counter_before`, `counter_after` (Philox counters),
* `blocks`, `draws` (how many blocks/draws were consumed),
* contextual identifiers (world, seed, region/cell, attribute family).

---

### 13.6 Miscellaneous shorthand & conventions

* **“World”**
  Shorthand for “all artefacts tied to a single `manifest_fingerprint`”.

* **“Cell”**
  A `(region, party_type, segment_id)` triple (or chosen equivalent logical combination) that S1 uses as the unit of population planning.

* **“Population plan”**
  The internal table of `N_cell_target(c)` and `N_cell(c)` per cell before materialising parties.

* **“Base table”**
  Refers to `s1_party_base_6A` — the authoritative party list.

* **“Summary table”**
  Refers to `s1_party_summary_6A` — the optional aggregate counts, strictly derived from the base.

* **Conservation**
  Used informally for “sums match”: e.g. Σ cell counts equals the world total, and summary counts match the base table.

This appendix is purely **informative**; it’s here to make the rest of the S1 spec easier to read and implement.

---
