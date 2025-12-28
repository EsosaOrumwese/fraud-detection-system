# 5A.S1 — Merchant & Zone Demand Classification (Layer-2 / Segment 5A)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5A.S1 — Merchant & Zone Demand Classification** for **Layer-2 / Segment 5A**. It is binding on any implementation of this state.

---

### 1.1 Role of 5A.S1 in Segment 5A

5A.S1 is the **first modelling state** in Segment 5A. For a given closed world `(parameter_hash, manifest_fingerprint)` it:

* takes the **Layer-1 world** (merchants, zones, virtual vs physical) and
* the **5A policy/config pack** and
* produces, for each in-scope `(merchant, zone)` pair, a **deterministic “demand profile”** consisting of:

  * a **demand class** (e.g. local daytime retail, evening-heavy, online-only, etc.), and
  * a set of **base scale parameters** (e.g. expected weekly volume level, relative variability flags) that later states use to build intensity surfaces.

5A.S1 is:

* **RNG-free** — it MUST NOT consume any RNG streams or emit RNG events.
* **Per-merchant×zone only** — it operates at the level of `(merchant, zone)` identities, not at site, arrival, or time-bucket level.
* **Upstream-respecting** — it consumes sealed inputs defined by 5A.S0 and MUST NOT re-derive or override Layer-1 facts (e.g. zone allocation, virtual classification).

It does **not** emit any time-series or intensity surfaces; those are the responsibility of 5A.S2–S4.

---

### 1.2 Objectives

5A.S1 MUST:

* **Summarise the Layer-1 world into traffic personas**

  For each in-scope `(merchant, zone)` (where “zone” is whatever unit Segment 5A uses—e.g. `(legal_country_iso, tzid)` derived from 3A):

  * assign a **demand class** based solely on sealed upstream features and 5A classing policies, and
  * derive **base scale parameters** that capture how “busy” that merchant×zone is expected to be over a week under the active parameter pack.

* **Act as the single authority for demand classes & base scale**

  Downstream 5A states (S2–S4) and any later segments (5B, 6A) MUST treat S1’s outputs as the **only** source of:

  * which demand class a merchant×zone belongs to, and
  * which base scale parameters apply to that merchant×zone under the current `(parameter_hash, manifest_fingerprint)`.

* **Remain lightweight and deterministic**

  * Only perform feature lookups and small aggregations needed for classing & scale.
  * Avoid reading more granular data than necessary (e.g. site-level geometry) once sufficient features are available.
  * Never depend on wall-clock time for logic; use only sealed inputs and policies.

* **Align with S0’s sealed universe**

  * Only use artefacts listed in `sealed_inputs_5A` for the target `manifest_fingerprint`.
  * Respect upstream `"PASS"` / `"FAIL"` / `"MISSING"` statuses recorded in `s0_gate_receipt_5A` and fail fast if required upstream segments are not `"PASS"`.

---

### 1.3 In-scope behaviour

The following activities are **in scope** for 5A.S1 and MUST be handled here (not duplicated in later 5A states):

* **Run-level gating on S0**

  * Reading `s0_gate_receipt_5A` and `sealed_inputs_5A` for the target `manifest_fingerprint`.
  * Verifying that all required upstream segments (1A–3B) are `"PASS"` and that all required 5A policies/configs are present.

* **Defining the classification domain**

  * Constructing the set of `(merchant, zone)` pairs to be profiled, using sealed inputs such as:

    * merchant universe from Layer-1,
    * `zone_alloc` / zone-universe surfaces from 3A,
    * virtual merchant flags / settlement info from 3B (where in scope).

* **Feature assembly for classing/scale**

  * Collecting, per `(merchant, zone)`:

    * merchant attributes (MCC, channel, brand, size bucket, country buckets, etc.),
    * zone attributes (country, tzid, virtual vs physical, number of outlets),
    * minimal scenario metadata needed for classing (e.g. scenario type: baseline vs stress).
  * Any feature engineering required for classification (e.g. deriving “small_local_retailer” vs “large_chain”) from these sealed facts.

* **Demand class assignment**

  * Applying the configured classing policy to map features → `demand_class` (and, if defined, `subclass` or `profile_id`).
  * Ensuring that every in-scope `(merchant, zone)` receives exactly one well-defined class (no missing, no overlapping classes).

* **Base scale parameter derivation**

  * Applying configured scale policies to assign base scale parameters such as:

    * a base weekly expected volume or intensity level, and/or
    * additional scale flags (e.g. “high_variability”, “low_volume_tail”).
  * Ensuring non-negative and finite scale values and consistent units (e.g. “expected arrivals per week” or a dimensionless scale factor).

* **Emitting classification outputs**

  * Producing one or more datasets (e.g. `merchant_zone_profile_5A`) that:

    * are keyed by `(merchant_id, zone_id)` (or equivalent) and
    * contain class and scale fields required by S2–S4.

---

### 1.4 Out-of-scope behaviour

The following activities are explicitly **out of scope** for 5A.S1 and MUST NOT be performed by this state:

* **Randomness or stochastic modelling**

  * S1 MUST NOT call any RNG or implement stochastic classing.
  * Demand class and scale MUST be deterministic functions of sealed inputs and policies.

* **Time-series or intensity construction**

  * S1 MUST NOT:

    * build per-bucket or per-hour curves,
    * construct weekly shapes or daily profiles, or
    * apply calendar/scenario overlays to produce `λ(t)`.
      These are handled by 5A.S2–S4.

* **Entity or arrival-level logic**

  * S1 MUST NOT:

    * generate arrivals or any event-level records,
    * attach routing decisions to sites/edges, or
    * touch entity graphs or fraud labels.

* **Upstream re-derivation**

  * S1 MUST NOT recompute or override:

    * zone allocation (3A),
    * virtual classification / edge semantics (3B),
    * routing weights or day-effects (2B),
    * civil-time assignment (2A).
      It may only **consume** these surfaces via `sealed_inputs_5A`.

* **Segment-level PASS for 5A**

  * S1 does not determine segment-level PASS/FAIL for Segment 5A.
  * It contributes outputs that will be validated and bundled by a later 5A validation state.

---

### 1.5 Downstream obligations

This specification imposes the following obligations on downstream states (5A.S2–S4 and any others that depend on S1):

* **Gating on S1 outputs**

  * A downstream 5A state MUST verify that a schema-valid `merchant_zone_profile_5A` (and any other S1 outputs defined in §4/§5):

    * exists for the target `manifest_fingerprint`, and
    * is consistent with the same `parameter_hash` and `manifest_fingerprint` recorded in `s0_gate_receipt_5A`.

* **Treat S1 profiles as authoritative**

  * Downstream 5A states MUST treat S1’s demand classes and base scale parameters as the **single source of truth** for:

    * which traffic class a merchant×zone belongs to, and
    * what baseline scale level should be used in constructing intensity surfaces.
  * They MUST NOT recompute or second-guess the classing logic; any change to class definitions MUST be expressed via S1’s policies and re-running S1.

* **No back-writes to S1 outputs**

  * No later state may modify or overwrite S1’s classification outputs for any fingerprint.
  * If a new classification logic or policy pack is needed, it MUST be introduced via:

    * a new `parameter_hash` and/or `manifest_fingerprint`, and
    * a fresh run of S1 under those identities.

Within this scope, 5A.S1 cleanly defines **who each merchant×zone is** and **how big their baseline traffic should be**, providing the deterministic backbone that 5A.S2–S4 will use to build full intensity surfaces.

---

## 2. Preconditions & sealed inputs *(Binding)*

This section defines the conditions under which **5A.S1 — Merchant & Zone Demand Classification** is permitted to run, and what “sealed inputs” it is allowed to use. These requirements are **binding**.

---

### 2.1 Invocation context

5A.S1 MUST only be invoked in the context of a well-defined engine run characterised by:

* `parameter_hash` — the parameter pack identity.
* `manifest_fingerprint` — the closed-world manifest identity.
* `run_id` — the execution ID for this 5A run.

These MUST:

* be supplied by the engine orchestration layer;
* match the values used when 5A.S0 ran for the same fingerprint; and
* be treated as immutable for the duration of S1.

S1 MUST NOT attempt to recompute or override `parameter_hash` or `manifest_fingerprint`.

---

### 2.2 Dependency on 5A.S0 (gate receipt + inventory)

Before performing any work, 5A.S1 MUST require:

1. **Presence of S0 outputs**

   * A `s0_gate_receipt_5A` dataset row for `fingerprint={manifest_fingerprint}`.
   * A `sealed_inputs_5A` dataset for `fingerprint={manifest_fingerprint}`.

   Both MUST be located via `dataset_dictionary.layer2.5A.yaml` and `artefact_registry_5A.yaml`, not via ad-hoc paths.

2. **Schema validity**

   * `s0_gate_receipt_5A` MUST validate against `schemas.5A.yaml#/validation/s0_gate_receipt_5A`.
   * `sealed_inputs_5A` MUST validate against `schemas.5A.yaml#/validation/sealed_inputs_5A`, including PK constraints.

3. **Identity consistency**

   * `s0_gate_receipt_5A.parameter_hash` MUST equal the run’s `parameter_hash`.
   * The `parameter_hash` embedded in all `sealed_inputs_5A` rows MUST equal the run’s `parameter_hash`.
   * Embedded `manifest_fingerprint` MUST match the partition token `fingerprint={manifest_fingerprint}` in both outputs.

4. **Sealed inventory digest match**

   * S1 MUST recompute `sealed_inputs_digest` from `sealed_inputs_5A` using the hashing law defined by S0.
   * The recomputed value MUST match `s0_gate_receipt_5A.sealed_inputs_digest`.

If any of these checks fail, 5A.S1 MUST abort with a precondition failure (e.g. `S1_GATE_RECEIPT_INVALID`) and MUST NOT proceed.

---

### 2.3 Upstream segment readiness (1A–3B)

5A.S1 operates **only** when all required Layer-1 segments are green.

From `s0_gate_receipt_5A.verified_upstream_segments`, S1 MUST:

* read the status for each of:

  * `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.

Precondition:

* For 5A.S1 to proceed, the status for **each** of these segments MUST be `"PASS"`.

If any required segment has status `"FAIL"` or `"MISSING"`, 5A.S1 MUST:

* treat this as a hard precondition failure (e.g. `S1_UPSTREAM_NOT_PASS`), and
* MUST NOT attempt to read any upstream fact datasets from that segment, even if they exist in storage.

S1 MUST NOT try to “repair” or re-validate upstream segments; that is upstream’s responsibility.

---

### 2.4 Required sealed inputs for S1

Given a valid S0 gate, 5A.S1’s **input universe** is the subset of `sealed_inputs_5A` rows marked as in-bounds for S1.

S1 MUST be able to resolve, via `sealed_inputs_5A`, the following **required** artefacts (names illustrative; actual IDs come from the dictionary/registry):

1. **Merchant & zone universe**

   * Merchant master / attributes (Layer-1 or ingress), including:

     * `merchant_id`, `legal_country_iso`, MCC, channel, brand/group, size bucket or equivalent.
   * Zone allocation surface from 3A, e.g.:

     * `zone_alloc` (merchant×country×tzid counts / presence).
   * Optional: any per-merchant classification from Layer-1 needed as features (e.g. single vs multi, cross-border flags).

2. **Virtual & hybrid information (if virtual in scope)**

   * From 3B:

     * `virtual_classification_3B` (is_virtual / hybrid flags).
     * Optionally `virtual_settlement_3B` if settlement tzid is needed as a feature.
     * `virtual_routing_policy_3B` (metadata only), if S1 needs to distinguish virtual-only vs hybrid usage patterns.

3. **Scenario metadata (not full calendar)**

   * Scenario-level config sufficient to determine:

     * scenario ID and type (baseline vs stress),
     * any coarse scenario flags that influence classing/scale (e.g. “e-commerce boom”).

   This comes from artefacts in `sealed_inputs_5A` with `role="scenario_config"` and `status="REQUIRED"`.

4. **5A policies for classing & scale**

   * Merchant/zone classing policy, e.g. `merchant_class_policy_5A`.
   * Scale policy, e.g. `demand_scale_policy_5A`.
   * Any lookup tables needed for bucketisation (e.g. merchant size buckets, region groupings) if they are 5A-specific and not already covered by Layer-1 reference data.

Preconditions:

* For each **required** artefact above:

  * At least one row MUST exist in `sealed_inputs_5A` with:

    * matching `owner_segment` / `artifact_id`,
    * `status="REQUIRED"`, and
    * `read_scope` appropriate for S1’s needs (`"ROW_LEVEL"` for facts, `"METADATA_ONLY"` for pure configs).

* S1 MUST fail (e.g. `S1_REQUIRED_POLICY_MISSING` or `S1_REQUIRED_INPUT_MISSING`) if:

  * any required artefact is not present in `sealed_inputs_5A`, or
  * present but with a `status` or `read_scope` that makes it unusable for S1.

---

### 2.5 Permitted but optional sealed inputs

S1 MAY also make use of additional artefacts in `sealed_inputs_5A` flagged as `status="OPTIONAL"`, for example:

* Additional Layer-1 reference data (country-level GDP buckets, region clusters).
* 5A-specific diagnostic configs (e.g. debug profiles).
* Auxiliary merchant descriptors.

Rules:

* Optional inputs MAY be used to refine classes or scale, but S1 MUST define sensible defaults when they are absent.
* Optional artefacts MUST NOT be required for S1 to succeed, and their absence MUST NOT cause S1 to fail precondition checks.

---

### 2.6 Authority boundaries for S1 inputs

The following authority boundaries are binding:

1. **Sealed inputs are the only source of truth**

   * S1 MUST NOT read any dataset or artefact that is not listed in `sealed_inputs_5A` for the fingerprint.
   * If an upstream dataset is physically present but absent from `sealed_inputs_5A`, it is out-of-bounds.

2. **Upstream semantics are not redefined**

   * S1 MUST treat:

     * `zone_alloc` as the authoritative definition of merchant×zone membership.
     * `virtual_classification_3B` as the authoritative virtual/hybrid flag.
     * merchant attributes from Layer-1 as authoritative for MCC, channel, etc.
   * S1 MAY derive new features from these facts, but MUST NOT alter or reinterpret their base semantics.

3. **No back-channel configs**

   * S1 MUST NOT widen or narrow its input universe based on:

     * env variables, CLI flags, or feature switches,
     * that are not reflected in `parameter_hash` and `sealed_inputs_5A`.
   * Any configuration that affects classing/scale MUST be encoded as an artefact in `sealed_inputs_5A`.

Within these preconditions, 5A.S1 runs in a fully sealed, catalogue-defined world: it trusts S0 to tell it **what exists and is allowed**, and trusts upstream segments to tell it **what the world looks like**, then performs a deterministic classification over that sealed domain.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **exactly what 5A.S1 may read**, how those inputs are obtained, and which upstream components are authoritative for particular facts. All rules here are **binding**.

5A.S1 is **RNG-free** and **catalogue-driven**: it can only use inputs that are explicitly sealed by 5A.S0 in `sealed_inputs_5A`.

---

### 3.1 Overview

5A.S1 has three classes of inputs:

1. **Control-plane inputs** from 5A.S0
   – to know *what* is allowed and whether upstream is green.

2. **World surfaces (facts) from Layer-1**
   – merchant, zone, and virtual/physical structure, used as features.

3. **5A-specific policies and scenario configs**
   – classing and scale rules, and coarse scenario metadata.

Everything is resolved through:

* `s0_gate_receipt_5A`,
* `sealed_inputs_5A`, and
* the Layer-1 / Layer-2 dictionaries & registries behind them.

S1 MUST NOT read any artefact that is **not** listed in `sealed_inputs_5A` for the current `manifest_fingerprint`.

---

### 3.2 Control-plane inputs from 5A.S0

5A.S1 has two **mandatory** control-plane inputs:

1. **`s0_gate_receipt_5A`**

   * Shape: `schemas.5A.yaml#/validation/s0_gate_receipt_5A`.
   * Role:

     * provides `parameter_hash`, `manifest_fingerprint`, `run_id` for this fingerprint;
     * provides `verified_upstream_segments` map (`1A`–`3B` → `"PASS"|"FAIL"|"MISSING"`);
     * provides `sealed_inputs_digest`;
     * provides `scenario_id` / `scenario_pack_id` used to contextualise S1’s decisions.

   **Authority boundary:**

   * S1 MUST treat `verified_upstream_segments` as the **sole authority** on upstream PASS/FAIL for 1A–3B; it MUST NOT attempt to re-validate upstream bundles itself.
   * S1 MUST NOT modify or rewrite `s0_gate_receipt_5A`.

2. **`sealed_inputs_5A`**

   * Shape: `schemas.5A.yaml#/validation/sealed_inputs_5A`.
   * Role:

     * defines the **entire input universe** S1 is allowed to use;
     * for each artefact, provides `owner_segment`, `artifact_id`, `schema_ref`, `path_template`, `partition_keys`, `sha256_hex`, `role`, `status`, `read_scope`.

   **Authority boundary:**

   * S1 MUST derive its list of candidate datasets/configs **exclusively** from `sealed_inputs_5A` for the current `manifest_fingerprint`.
   * If an artefact is not present as a row in `sealed_inputs_5A`, it is *out-of-bounds* for S1, even if physically present in storage.
   * S1 MUST respect `read_scope`:

     * `ROW_LEVEL` → S1 MAY read rows;
     * `METADATA_ONLY` → S1 MAY use only metadata (e.g. IDs, digests, policy versions).

---

### 3.3 Upstream world surfaces (facts) S1 may read

The following world surfaces are **authoritative** sources of features for S1. All MUST be discovered via rows in `sealed_inputs_5A` and resolved via the catalogue (dictionary + registry).

#### 3.3.1 Merchant universe & attributes (Layer-1 / ingress)

**Logical input:**

* Merchant reference / attributes table(s) providing, at minimum:

  * `merchant_id` (primary key for merchants).
  * `legal_country_iso` (home/primary country).
  * `mcc` / `mcc_group`.
  * `channel` (e.g. POS, e-commerce, mixed).
  * Optional size / segment attributes (e.g. `turnover_bucket`, `outlet_count_bucket`, `brand_group_id`).

**Authority boundary:**

* These tables are the **only authority** for baseline merchant attributes used in classification (MCC, channel, size, home country, etc.).
* S1 MAY derive engineered features from them (e.g. “small_local_retailer”), but MUST NOT override the base values.

#### 3.3.2 Zone universe (3A: `zone_alloc` / related views)

**Logical input:**

* `zone_alloc` (or its documented egress anchor in `schemas.3A.yaml`), providing at minimum:

  * `merchant_id`
  * `legal_country_iso`
  * `tzid` (or equivalent zone identifier)
  * zone-level counts (e.g. `zone_site_count`, `zone_site_count_sum`).

**Authority boundary:**

* `zone_alloc` is the **sole authority** for the `(merchant, zone)` universe.

* S1 MUST derive its per-merchant zone domain from `zone_alloc` and MUST NOT:

  * re-interpret civil-time data to “invent” alternative zones, or
  * infer zones from site-level geometry independently.

* If S1 introduces an internal `zone_id` key, it MUST be a deterministic function of `merchant_id`, `legal_country_iso`, and `tzid` (or whatever 3A uses), and MUST NOT change zone semantics.

#### 3.3.3 Virtual / hybrid flags (3B)

If virtual merchants are in scope for the engine configuration, S1 may use:

* `virtual_classification_3B` (3B egress), to obtain:

  * `is_virtual` / `virtual_mode` (e.g. VIRTUAL_ONLY / HYBRID / NON_VIRTUAL).
* Optionally `virtual_settlement_3B`, for:

  * `tzid_settlement` (settlement timezone used as a feature).

**Authority boundary:**

* `virtual_classification_3B` is the **only authority** for whether a merchant is treated as virtual or hybrid.
* S1 MUST NOT “guess” virtual status from MCC/channel; rather, it MUST treat virtual flags as input features.
* Any dual-timezone semantics (settlement vs operational) remain governed by 3B; S1 only uses them as static features.

#### 3.3.4 Optional civil time signals (2A)

5A.S1 **does not need** full time-series or tz transitions, but MAY use:

* `site_timezones` (2A egress) and/or derived merchant-level summaries, for:

  * counts of distinct tzids per merchant,
  * flags like “cross-timezone merchant”.

**Authority boundary:**

* `site_timezones` is the only canonical source of per-site tzid.
* If S1 uses any civil-time features, they MUST be derived via `site_timezones` or 3A’s zone surfaces, not from raw lat/lon.

---

### 3.4 5A-specific policies & scenario configs

5A.S1 relies on **5A policy artefacts** (all discovered via `sealed_inputs_5A`, `owner_segment="5A"`).

#### 3.4.1 Merchant & zone classing policy

Logical artefact (name illustrative):

* `merchant_class_policy_5A`

Content (high-level):

* Deterministic rules mapping features → `demand_class` (and optional `subclass`), e.g.:

  * MCC-based templates.
  * Channel-specific overrides.
  * Size / geography-based overrides (e.g. “cross-border large retailer”).

Authority boundary:

* `merchant_class_policy_5A` is **the** authority for how classes are defined.
* S1 MUST NOT embed hard-coded class rules; it MUST implement the policy as data.
* Changing class definitions MUST occur via this policy and a new `parameter_hash`, not via code changes that bypass the policy.

#### 3.4.2 Scale policy

Logical artefact (name illustrative):

* `demand_scale_policy_5A`

Content (high-level):

* Deterministic rules mapping merchant & zone features → base scale parameters, e.g.:

  * expected weekly volume level, perhaps as:

    * an absolute number per `(merchant, zone)`, or
    * a dimensionless scale factor that later shapes will normalise.
  * flags indicating high variability or special regimes.

Authority boundary:

* `demand_scale_policy_5A` is the only authority for how base scale parameters are calculated.
* S1 MUST implement scale logic purely as a function of sealed features + this policy.

#### 3.4.3 Scenario metadata

Logical artefacts (collectively):

* `scenario_config_*` entries in `sealed_inputs_5A` with `role="scenario_config"`.

Content (high-level):

* Scenario identifiers and coarse properties that may influence classing or scale, e.g.:

  * `scenario_id`, `scenario_type` (baseline vs stress),
  * global modifiers like “online-heavy world”, if classing logic depends on them.

Authority boundary:

* Scenario artefacts sealed in `sealed_inputs_5A` are the only authority for which scenario S1 is operating under.
* S1 MUST NOT switch scenario based on CLI flags or env variables that are not reflected in `sealed_inputs_5A`.

---

### 3.5 Authority boundaries & out-of-bounds inputs

The following boundaries are binding for S1:

1. **Sealed inputs as exclusive universe**

   * S1 MUST treat `sealed_inputs_5A` as **exhaustive** for the current fingerprint:

     * It MUST NOT read any artefact not listed there.
     * It MUST NOT assume that “if it exists on disk, it is allowed”.

2. **Read scope respected**

   * For each row in `sealed_inputs_5A` used by S1:

     * If `read_scope="ROW_LEVEL"`, S1 MAY read rows from the dataset.
     * If `read_scope="METADATA_ONLY"`, S1 MAY:

       * read only metadata (schema, digests, IDs), or
       * treat the artefact as a configuration flag (e.g. policy version),
         but MUST NOT read or depend on row-level contents.

3. **No upstream overrides**

   * S1 MUST NOT:

     * adjust `zone_alloc` counts or redefine zones;
     * reclassify merchants as virtual when 3B does not;
     * reinterpret routing or civil-time semantics.
   * These are upstream concerns; S1 can only derive features and classifications on top.

4. **No new implicit identity dimensions**

   * S1 MUST NOT introduce new partition keys or identity dimensions beyond those already defined upstream for merchants and zones.
   * Any internal IDs (e.g. `class_id`, `profile_id`, `zone_profile_id`) MUST be deterministic and reversible from `demand_class` and upstream keys; they MUST NOT re-key merchants/zones in a way that breaks joins.

Within these boundaries, 5A.S1 sees a **sealed, immutable snapshot of the world** as defined by Layer-1 and S0, and its job is to add **one new layer of deterministic structure**: demand classes and base scale per merchant×zone.

---

## 4. Outputs (datasets) & identity *(Binding)*

This section defines the **data products** of **5A.S1 — Merchant & Zone Demand Classification**, and how they are identified and addressed in storage. All rules here are **binding**.

5A.S1 produces **no events and no time-series**. Its outputs are purely **per-merchant×zone profiles** that later states (5A.S2–S4, 5B, 6A) will consume.

---

### 4.1 Overview of outputs

5A.S1 MUST produce exactly one **required** modelling dataset, and MAY produce one optional convenience dataset:

1. **`merchant_zone_profile_5A` *(required)***

   * Per `(merchant, zone)` demand profile.
   * This is the **primary output** and the single authority for:

     * `demand_class` and related classification fields, and
     * base scale parameters used by 5A.S2–S4.

2. **`merchant_class_profile_5A` *(optional)* **

   * Per-merchant aggregate view of demand classes and high-level scale.
   * This is a **convenience surface** for downstream consumers or diagnostics; it MUST not carry any information that cannot be reconstructed from `merchant_zone_profile_5A`.

No other S1 datasets are required. Any additional diagnostic tables (e.g. “classification_debug_5A”) MUST be explicitly marked as **diagnostic/optional** in the dataset dictionary and MUST NOT be required by downstream segments.

---

### 4.2 `merchant_zone_profile_5A` (required)

#### 4.2.1 Semantic role

`merchant_zone_profile_5A` is the **core product** of 5A.S1. Each row describes the **demand persona** of a specific `(merchant, zone)` under the current `(parameter_hash, manifest_fingerprint)`:

* “Who is this merchant×zone from a traffic perspective?”
* “How big / busy is it expected to be at baseline?”

Downstream states use it to attach the right shape and scale.

At minimum, each row MUST include:

* **Identity fields** (linking to Layer-1):

  * `merchant_id` — merchant key, matching Layer-1.
  * `legal_country_iso` — legal country for this zone, matching 3A’s `zone_alloc`.
  * `tzid` (or equivalent zone identifier) — the tzid / zone key used in 3A.

  Together, these fields define the **zone** for that merchant, aligned with 3A egress.

* **Classification fields**:

  * `demand_class` — primary class label for this merchant×zone (e.g. `"local_retail_daytime"`, `"online_24h"`, `"office_hours"`, naming defined by policy).
  * Optional: `demand_subclass`, `profile_id` or similar, if the policy defines sub-structure.

* **Scale fields**:

  * A base scale parameter, e.g.:

    * `weekly_volume_expected` (numeric, expected arrivals per week), **or**
    * `scale_factor` (dimensionless, to be combined with shapes in S2–S3).
  * Optional flags such as:

    * `high_variability_flag`, `low_volume_flag`, `virtual_preferred_flag`, etc.

Exact column shapes and types are specified in §5; here we fix their semantics.

#### 4.2.2 Domain & cardinality

For a given `(parameter_hash, manifest_fingerprint)`:

* The **domain** of `merchant_zone_profile_5A` MUST be:

  > all `(merchant_id, legal_country_iso, tzid)` triplets that appear in `zone_alloc` for this fingerprint and are declared in scope for 5A by policy.

* For each in-scope `(merchant_id, legal_country_iso, tzid)`:

  * There MUST be **exactly one** row in `merchant_zone_profile_5A`.
  * There MUST be **exactly one** `demand_class`, and zero or one `demand_subclass` / `profile_id` per row (no ambiguity).

* Merchant×zone combinations not present in `zone_alloc` MUST NOT appear in `merchant_zone_profile_5A`.

This makes `merchant_zone_profile_5A` a **1:1 overlay** over the 3A zone universe (restricted to whatever subset 5A is designed to handle).

#### 4.2.3 Identity & keys

For this dataset:

* **Partitioning:**

  * `partition_keys: ["fingerprint"]`
  * Path template (illustrative):
    `data/layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/merchant_zone_profile_5A.parquet`

* **Primary key (logical):**

  * `primary_key: ["merchant_id", "legal_country_iso", "tzid"]`

* **Embedded identity fields:**

  * `manifest_fingerprint` — required column; MUST equal the partition token.
  * `parameter_hash` — required column; MUST equal the run’s `parameter_hash` and be constant across all rows for a given fingerprint.

5A.S1 MUST ensure that:

* The `(merchant_id, legal_country_iso, tzid)` key is unique per row within a fingerprint.
* Embedded `manifest_fingerprint` / `parameter_hash` values match the S0 gate.

---

### 4.3 `merchant_class_profile_5A` (optional)

If implemented, `merchant_class_profile_5A` is a **derived convenience view**:

#### 4.3.1 Semantic role

* Per-merchant aggregate class summary, used for:

  * diagnostics (e.g. “how many classes does a merchant span across zones?”),
  * coarse-grained logic in later layers where per-zone detail is not needed.

Possible contents (non-exhaustive):

* `merchant_id`
* `primary_demand_class` (e.g. most frequent or pre-defined precedence across zones)
* `classes_seen` (array or summary of all `demand_class` values across zones)
* `weekly_volume_total_expected` (sum of per-zone `weekly_volume_expected`)

All values MUST be derivable **purely** from `merchant_zone_profile_5A` plus deterministic policy rules (e.g. “pick primary class by precedence list”).

#### 4.3.2 Domain & cardinality

For a given fingerprint:

* Domain: all merchants that appear in `merchant_zone_profile_5A`.
* Exactly one row per `merchant_id` in that domain.

#### 4.3.3 Identity & keys

If this dataset is materialised:

* `partition_keys: ["fingerprint"]`

* Path template (illustrative):
  `data/layer2/5A/merchant_class_profile/fingerprint={manifest_fingerprint}/merchant_class_profile_5A.parquet`

* `primary_key: ["merchant_id"]`

* Embedded identity columns:

  * `manifest_fingerprint` (equals partition token)
  * `parameter_hash` (matches S0)

Downstream logic MUST NOT depend on this dataset for anything that cannot be reconstructed from `merchant_zone_profile_5A`.

---

### 4.4 Relationship to upstream & downstream datasets

#### 4.4.1 Upstream constraints

* `merchant_zone_profile_5A` MUST:

  * Have a foreign-key relationship to 3A’s `zone_alloc` on `(merchant_id, legal_country_iso, tzid)` for the same `manifest_fingerprint`.
  * Not introduce any new cross-country or cross-zone ordering or identity; it is a pure annotation of the zone universe.

* If `merchant_class_profile_5A` is present, every `merchant_id` in it MUST exist in the upstream merchant reference table(s) sealed in `sealed_inputs_5A`.

S1 MUST treat upstream datasets as **read-only**; no mutation is allowed.

#### 4.4.2 Downstream obligations

Downstream 5A states (S2–S4) and any other consumer (5B, 6A) MUST:

* Use `merchant_zone_profile_5A` as the **single source of truth** for:

  * demand class selection per merchant×zone;
  * base scale parameters per merchant×zone.

* Join on `(merchant_id, legal_country_iso, tzid)` (and `manifest_fingerprint`/`parameter_hash` where needed) when combining:

  * S1 profiles with 5A.S2–S4 surfaces;
  * S1 profiles with Layer-1 zone surfaces (3A) and routing artefacts (2B).

They MUST NOT:

* Attempt to reclassify merchants/zones independently;
* Introduce their own ad-hoc class or scale mappings that conflict with S1.

---

### 4.5 Control-plane vs modelling outputs

Unlike 5A.S0, 5A.S1:

* **does not** emit new control-plane datasets (no new gate receipt);
* emits only **modelling outputs** (`merchant_zone_profile_5A`, optionally `merchant_class_profile_5A`) which:

  * are deterministic functions of sealed inputs + policies,
  * are fingerprint-partitioned only, and
  * are immutable once written (no merge/partial updates; rewrites only allowed as idempotent re-runs producing identical content).

Segment-level validation for 5A (a later state) will:

* treat S1 outputs as required inputs, and
* include them in the Layer-2 validation bundle for 5A, but S1 itself does not produce `_passed.flag`.

Within this identity model, 5A.S1’s outputs are fully pinned to the same `(parameter_hash, manifest_fingerprint)` world as S0 and Layer-1, and provide a single, clean demand-profile surface for all later intensity and arrival modelling.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

Schematics for the S1 outputs live in `schemas.5A.yaml` with matching entries in `dataset_dictionary.layer2.5A.yaml` and `artefact_registry_5A.yaml`. This section recaps roles and obligations without duplicating column lists.

Datasets:

1. `merchant_zone_profile_5A` (required)
2. `merchant_class_profile_5A` (optional convenience)

### 5.1 `merchant_zone_profile_5A`

* **Schema anchor:** `schemas.5A.yaml#/model/merchant_zone_profile_5A`
* **Dictionary id:** `merchant_zone_profile_5A`
* **Registry key:** `mlr.5A.model.merchant_zone_profile`

Binding notes: deterministic per `(parameter_hash, manifest_fingerprint)`; written at `data/layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/…` with the PK/order defined in the dictionary. Schema pack governs keys, demand classes, scale factors, and audit fields.

### 5.2 `merchant_class_profile_5A`

* **Schema anchor:** `schemas.5A.yaml#/model/merchant_class_profile_5A`
* **Dictionary id:** `merchant_class_profile_5A`
* **Registry key:** `mlr.5A.model.merchant_class_profile`

Binding notes: optional deterministic aggregation derived from the zone profile. When emitted it MUST follow the dictionary path, partitioning and schema. Downstream states MUST continue to rely on the zone-level profile as the authority.


## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section specifies the **ordered, deterministic algorithm** for **5A.S1 — Merchant & Zone Demand Classification**. Implementations MUST follow these steps and invariants. 5A.S1 is **purely deterministic** and MUST NOT consume RNG.

---

### 6.1 High-level invariants

5A.S1 MUST satisfy the following:

1. **RNG-free**

   * MUST NOT call any RNG primitive.
   * MUST NOT write to `rng_audit_log`, `rng_trace_log`, or any RNG event stream.

2. **Catalogue-driven**

   * MUST discover all inputs via:

     * `s0_gate_receipt_5A`,
     * `sealed_inputs_5A`, and
     * the dataset dictionary + artefact registry.
   * MUST NOT discover inputs via hard-coded paths, directory scans, or network calls.

3. **Upstream-respecting**

   * MUST NOT modify or override upstream datasets (1A–3B).
   * MUST NOT re-derive or reinterpret upstream semantics (zone allocation, virtual classification, etc.).

4. **Domain completeness**

   * For every `(merchant_id, legal_country_iso, tzid)` in the in-scope zone universe (as defined below), S1 MUST produce **exactly one** `merchant_zone_profile_5A` row.

5. **No partial outputs**

   * On failure, S1 MUST NOT commit partial `merchant_zone_profile_5A` (or `merchant_class_profile_5A`) for the fingerprint.
   * Successful runs MUST leave outputs present, schema-valid, and complete for the domain.

---

### 6.2 Step 1 — Load gate receipt & validate sealed inputs

**Goal:** Ensure S0 is valid and upstream is green before doing any work.

**Inputs:**

* `parameter_hash`, `manifest_fingerprint`, `run_id` (run context).
* `s0_gate_receipt_5A` (for this fingerprint).
* `sealed_inputs_5A` (for this fingerprint).

**Procedure:**

1. Locate `s0_gate_receipt_5A` and `sealed_inputs_5A` via the 5A dataset dictionary and artefact registry using `fingerprint={manifest_fingerprint}`.

2. Validate both datasets against their schemas:

   * `s0_gate_receipt_5A` → `schemas.5A.yaml#/validation/s0_gate_receipt_5A`.
   * `sealed_inputs_5A` → `schemas.5A.yaml#/validation/sealed_inputs_5A`.

3. Check identity consistency:

   * `s0_gate_receipt_5A.parameter_hash == parameter_hash`.
   * All rows in `sealed_inputs_5A` have:

     * `parameter_hash == parameter_hash`,
     * `manifest_fingerprint == manifest_fingerprint`.

4. Recompute `sealed_inputs_digest` from `sealed_inputs_5A` using the law defined in 5A.S0 and confirm equality with `s0_gate_receipt_5A.sealed_inputs_digest`.

5. Read `verified_upstream_segments` from the receipt and require `status="PASS"` for each of: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.

**Invariants:**

* If any check fails, S1 MUST abort with a precondition error and MUST NOT read any upstream fact datasets.
* If all checks pass, S1 may proceed.

---

### 6.3 Step 2 — Resolve physical inputs from `sealed_inputs_5A`

**Goal:** Turn sealed inventory rows into concrete logical inputs S1 will use.

**Inputs:**

* `sealed_inputs_5A` rows for this fingerprint.

**Procedure:**

1. From `sealed_inputs_5A`, filter rows with `status="REQUIRED"` and `read_scope` compatible with S1’s needs:

   * **Merchant attributes** (Layer-1 / ingress):
     rows marked `role="reference_data"` or `role="upstream_egress"` that provide merchant fields (`merchant_id`, MCC, channel, size, home country).

   * **Zone allocation** (3A):
     artefact representing `zone_alloc` (e.g. `artifact_id="zone_alloc"`).

   * **Virtual classification** (3B, if in scope):
     `virtual_classification_3B` (and optionally `virtual_settlement_3B`).

   * **Scenario metadata**:
     artefacts marked `role="scenario_config"` that carry scenario ID/type.

   * **5A policies**:
     at least:

     * `merchant_class_policy_5A`,
     * `demand_scale_policy_5A`.

2. For each required artefact:

   * Resolve its `schema_ref`, `path_template`, and `partition_keys` from the dictionary/registry.
   * Instantiate concrete path(s) using `manifest_fingerprint` (and `parameter_hash` if applicable).
   * Confirm `read_scope` is:

     * `ROW_LEVEL` for datasets S1 needs to scan (e.g. merchant attributes, `zone_alloc`), or
     * `METADATA_ONLY` for pure config/policy artefacts.

3. Load policies and scenario metadata into memory as small config objects (respecting their schemas).

**Invariants:**

* If any required artefact cannot be resolved to a valid dataset/config, S1 MUST abort with an appropriate error (e.g. `S1_REQUIRED_POLICY_MISSING` or `S1_REQUIRED_INPUT_MISSING`).
* No data is yet transformed; this step is just resolution/loading.

---

### 6.4 Step 3 — Build the `(merchant, zone)` domain

**Goal:** Determine the exact set of `(merchant_id, legal_country_iso, tzid)` pairs S1 must profile.

**Primary source:**

* `zone_alloc` egress from 3A (or whatever anchor is specified in the dictionary).

**Procedure:**

1. Read `zone_alloc` rows for this fingerprint (ROW_LEVEL, as permitted) with at least:

   * `merchant_id`
   * `legal_country_iso`
   * `tzid`
   * `zone_site_count` (or equivalent count per merchant×country×tzid).

2. Apply any **inclusion/exclusion rules** mandated by 5A policy, for example:

   * Exclude merchant×zone rows flagged in 5A policy as out of scope (e.g. `ignore_for_intensity=true`).
   * Optionally exclude zones with `zone_site_count = 0` if such rows can exist.

   These rules MUST be driven by explicit policy; S1 MUST NOT “guess” exclusions in code.

3. Construct an in-memory domain set `D`:

   ```text
   D = { (merchant_id, legal_country_iso, tzid) | selected from zone_alloc after policy filters }
   ```

4. Enforce that:

   * For each distinct `(merchant_id, legal_country_iso, tzid)` in `D`, there is exactly one `zone_alloc` row.
   * `D` is non-empty for all merchants intended to be in scope for 5A (policy-driven; if empty, this may be acceptable for some fingerprints but should be logged).

**Invariants:**

* `D` is the **sole domain** S1 operates over.
* No `(merchant, zone)` outside `D` may appear in `merchant_zone_profile_5A`.

---

### 6.5 Step 4 — Assemble features per `(merchant, zone)`

**Goal:** For each domain row, derive the feature vector needed for classing and scale.

**Inputs:**

* Domain `D` from Step 3.
* Merchant attributes.
* Optional virtual classification/settlement info.
* Scenario metadata.
* Any additional reference data listed in `sealed_inputs_5A` and required by policy.

**Procedure:**

For each `(m, c, tz)` in `D`:

1. **Join merchant attributes**

   * Join on `merchant_id` to merchant reference tables to retrieve:

     * `mcc`, `mcc_group`, `channel`, `brand_group_id`, `size_bucket`, etc.
   * If joins fail (missing merchant), treat as a configuration error; S1 MUST NOT silently invent defaults for unknown merchants.

2. **Join virtual classification (if in scope)**

   * Join `virtual_classification_3B` on `merchant_id` to obtain `is_virtual` / `virtual_mode`.
   * If needed, join `virtual_settlement_3B` to obtain `tzid_settlement`.
   * Use these only as *features*; do not override zone keys.

3. **Construct engineered features**

   Deterministically derive any higher-level features required by policy, such as:

   * `is_cross_border` — derived from number of distinct `legal_country_iso` for `m` in `zone_alloc`.
   * `zone_site_count` — from 3A’s counts for `(m,c,tz)`.
   * `merchant_size_class` — based on size bucket, outlet counts, etc.
   * `scenario_traits` — from scenario metadata (e.g. scenario type, “online_boosted_world”).

   The exact feature definitions are governed by 5A policies; S1 simply implements them deterministically.

4. **Assemble feature vector**

   * Build a structured “feature record” for `(m,c,tz)`:

     ```text
     features(m,c,tz) = {
       merchant_id,
       legal_country_iso,
       tzid,
       mcc, mcc_group,
       channel,
       brand_group_id,
       size_bucket,
       zone_site_count,
       is_virtual / virtual_mode,
       scenario_traits,
       ... any other required features ...
     }
     ```

**Invariants:**

* `features(m,c,tz)` MUST be a pure function of sealed inputs from `sealed_inputs_5A` and the policies, with no randomness.
* For each domain row, features MUST be well-defined; if necessary data is missing, S1 MUST either:

  * use a policy-defined fallback path, or
  * treat it as a classification error (see §9, not yet written) and abort.

---

### 6.6 Step 5 — Apply classing policy (deterministic rules)

**Goal:** Map each `features(m,c,tz)` to a unique `demand_class` (and optional subclass/profile).

**Inputs:**

* `features(m,c,tz)` from Step 4.
* `merchant_class_policy_5A` loaded in Step 2.

**Procedure:**

1. Interpret `merchant_class_policy_5A` as an ordered set of **rules** or a decision tree, for example:

   * global fallback class(es),
   * MCC/sector-specific rules,
   * channel-specific rules,
   * size/zone/virtual overrides.

2. For each `(m,c,tz)` in `D`:

   * Evaluate rules in the **policy-defined order**, using only `features(m,c,tz)` and global scenario traits.
   * The first matching rule (or the unique rule in a decision tree) MUST assign exactly:

     * `demand_class`, and optionally
     * `demand_subclass` / `profile_id`.

3. Ensure **completeness**:

   * For every `(m,c,tz)` in `D`, at least one rule MUST match.
   * The policy MUST guarantee (and S1 SHOULD assert) that no more than one rule can be applicable when interpreted correctly; if conflicting matches occur, S1 MUST treat this as a configuration error.

4. Optionally, derive a `class_source` field, indicating which rule branch produced the class (useful for debugging).

**Invariants:**

* No randomness is used in rule selection.
* Each `(m,c,tz)` gets **exactly one** `demand_class`.
* Class names / IDs MUST be consistent with the enum/constraints in the schema.

---

### 6.7 Step 6 — Apply scale policy (deterministic base scale)

**Goal:** Assign base scale parameters (e.g. expected weekly volume) per `(merchant, zone)`.

**Inputs:**

* `features(m,c,tz)` from Step 4.
* `demand_class` (and optional subclass/profile) from Step 5.
* `demand_scale_policy_5A`.

**Procedure:**

1. Interpret `demand_scale_policy_5A` as deterministic mapping from:

   * `(demand_class, features, scenario_traits)` →
   * scale parameters, such as:

     * `weekly_volume_expected` or `scale_factor`,
     * flags (`high_variability_flag`, etc.).

2. For each `(m,c,tz)` in `D`:

   * Look up or compute base scale according to policy:

     * e.g. via table lookups keyed by `(demand_class, size_bucket, country_group)`,
     * or via deterministic formulae (no RNG) using features (e.g. log-linear model with fixed coefficients).

   * Enforce:

     * `weekly_volume_expected ≥ 0` (if present),
     * `scale_factor ≥ 0` (if present),
     * no NaNs / Infs.

3. Derive any additional flags or attributes defined by policy:

   * `high_variability_flag`, `low_volume_flag`, `virtual_preferred_flag`, etc.

**Invariants:**

* Scale parameters MUST be reproducible: re-running S1 with the same inputs and policies MUST produce identical values.
* Units and interpretation of scale fields MUST match the schema and be stable across runs for a given `parameter_hash`.

---

### 6.8 Step 7 — Construct `merchant_zone_profile_5A` rows

**Goal:** Turn per-domain class + scale results into well-formed table rows.

**Inputs:**

* Domain `D`.
* `demand_class` / subclass / profile for each `(m,c,tz)` (Step 5).
* Scale parameters for each `(m,c,tz)` (Step 6).
* Run identity: `parameter_hash`, `manifest_fingerprint`.

**Procedure:**

For each `(m,c,tz)` in `D`:

1. Create a row with fields:

   * Identity:

     * `merchant_id = m`
     * `legal_country_iso = c`
     * `tzid = tz`
     * `manifest_fingerprint`
     * `parameter_hash`

   * Classification:

     * `demand_class` (required)
     * `demand_subclass` / `profile_id` if defined

   * Scale:

     * `weekly_volume_expected` or `scale_factor`
     * any derived flags (`high_variability_flag`, etc.)

   * Optional metadata:

     * `class_source` (rule branch identifier)
     * `created_utc` (timestamp of S1 run; informational only, not used in logic)

2. Validate the row against the schema anchor `schemas.5A.yaml#/model/merchant_zone_profile_5A` (in-process).

3. Append the row to an in-memory collection `PROFILE_ROWS`.

After all `(m,c,tz)` have been processed:

* Validate domain coverage:

  * ensure number of rows in `PROFILE_ROWS` equals size of `D`;
  * ensure no duplicate `(merchant_id, legal_country_iso, tzid)`.

* Optionally sort `PROFILE_ROWS` deterministically (e.g. by `(merchant_id, legal_country_iso, tzid)`).

---

### 6.9 Step 8 — Construct `merchant_class_profile_5A` rows (optional)

**Goal:** Build an optional per-merchant aggregate profile derived from `PROFILE_ROWS`.

**Inputs:**

* `PROFILE_ROWS` (in-memory or via `merchant_zone_profile_5A` reread).

**Procedure (if this dataset is implemented):**

1. Group `PROFILE_ROWS` by `merchant_id`.

2. For each merchant `m`:

   * Collect the set of `demand_class` values across zones.

   * Compute `primary_demand_class` using a policy-defined rule, e.g.:

     * precedence order of classes, or
     * majority class; ties broken by deterministic precedence list.

   * Optionally compute:

     * `classes_seen` (e.g. sorted list or canonical encoding).
     * `weekly_volume_total_expected` = Σ `weekly_volume_expected(m,c,tz)` over zones.

3. Construct one row per merchant:

   * `merchant_id`,
   * `manifest_fingerprint`, `parameter_hash`,
   * `primary_demand_class`,
   * optional aggregates.

4. Validate rows against `schemas.5A.yaml#/model/merchant_class_profile_5A` and collect them into `CLASS_ROWS`.

This dataset MUST be a pure function of `PROFILE_ROWS` plus fixed policy; no additional inputs or randomness may be used.

---

### 6.10 Step 9 — Atomic write & idempotency

**Goal:** Persist S1 outputs atomically and idempotently.

**Inputs:**

* `PROFILE_ROWS` (and `CLASS_ROWS` if implemented).
* Path templates and partitioning from the 5A dataset dictionary.

**Procedure:**

1. **Check for existing outputs**

   * Using the dictionary, locate the canonical paths for:

     * `merchant_zone_profile_5A` under `fingerprint={manifest_fingerprint}`;
     * `merchant_class_profile_5A` (if implemented).

   * If outputs already exist:

     * Read them and compare to `PROFILE_ROWS` / `CLASS_ROWS` under a canonical ordering/serialisation.
     * If content is identical, S1 MAY no-op (idempotent).
     * If content differs, S1 MUST fail with an output-conflict error (no overwrite).

2. **Write to staging**

   * Write `PROFILE_ROWS` to a staging file, e.g.:
     `.../merchant_zone_profile/fingerprint={manifest_fingerprint}/.staging/merchant_zone_profile_5A.parquet`.

   * If `merchant_class_profile_5A` is implemented, write `CLASS_ROWS` to its own staging file under a `.staging/` directory.

3. **Validate staged outputs (optional but recommended)**

   * Re-read staged files and validate:

     * schema conformance,
     * key uniqueness,
     * identity fields (fingerprint, parameter_hash).

4. **Atomic commit**

   * Atomically move staged files to canonical locations:

     * staging → `merchant_zone_profile_5A.parquet`
     * staging → `merchant_class_profile_5A.parquet` (if used)

   * Ensure that `merchant_zone_profile_5A` is committed before or at the same time as `merchant_class_profile_5A`, so consumers never see an aggregate without its base.

**Invariants:**

* Partial outputs MUST NOT be visible as canonical data.
* Re-running S1 with identical inputs and policies MUST either:

  * no-op (if outputs match), or
  * reproduce identical files byte-for-byte.

---

Within this algorithm, 5A.S1 is a **pure, deterministic classing and scaling step**: it turns a sealed Layer-1 world plus 5A policy into a stable, per-merchant×zone demand profile, with no randomness, no upstream re-interpretation, and atomic, idempotent outputs.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how **identity** is represented for 5A.S1 outputs, how they are **partitioned and addressed**, and what the **merge/rewrite rules** are. All rules here are **binding**.

5A.S1 produces only **modelling datasets** (no control-plane) which are:

* purely a function of `(parameter_hash, manifest_fingerprint)` plus sealed inputs;
* **not** seed- or run-partitioned;
* immutable once written, except for idempotent re-runs.

---

### 7.1 Identity model

There are two layers of identity:

1. **Run identity** (engine-level, ephemeral):

   * `parameter_hash` — parameter pack identity.
   * `manifest_fingerprint` — closed-world manifest identity.
   * `run_id` — execution ID for this 5A run.

2. **Dataset identity** (storage-level, persistent):

   * For S1 outputs, dataset identity is keyed by **`manifest_fingerprint` only**:

     * each fingerprint has at most one `merchant_zone_profile_5A` instance,
     * and, if implemented, one `merchant_class_profile_5A` instance.

Binding rules:

* `run_id` is **not** part of any primary key or partitioning; it may appear only in logs/run-report (not in the S1 datasets).
* `parameter_hash` and `manifest_fingerprint` MUST be embedded as columns in S1 outputs and MUST match the run context used for S0.

For a given `manifest_fingerprint`, multiple S1 runs (different `run_id`s) MUST either:

* produce identical outputs (idempotent re-runs), or
* trigger an output conflict (see §7.4).

---

### 7.2 Partition law & path contracts

#### 7.2.1 Partition keys

Both S1 outputs are **partitioned only by fingerprint**:

* `merchant_zone_profile_5A`:

  * `partition_keys: ["fingerprint"]`

* `merchant_class_profile_5A` (if implemented):

  * `partition_keys: ["fingerprint"]`

No other partition key (e.g. `parameter_hash`, `seed`, `run_id`) is allowed for S1 outputs.

#### 7.2.2 Path templates

Path templates (illustrative; exact names are binding, root prefix may vary but pattern must match):

* `merchant_zone_profile_5A`:

  ```text
  data/layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/merchant_zone_profile_5A.parquet
  ```

* `merchant_class_profile_5A` (optional):

  ```text
  data/layer2/5A/merchant_class_profile/fingerprint={manifest_fingerprint}/merchant_class_profile_5A.parquet
  ```

These templates MUST be the ones declared in `dataset_dictionary.layer2.5A.yaml` and echoed in `artefact_registry_5A.yaml`.

#### 7.2.3 Path ↔ embed equality

For every row in any S1 dataset:

* Embedded `manifest_fingerprint` column:

  * MUST exist and be non-null.
  * MUST exactly equal the value used in the partition token `fingerprint={manifest_fingerprint}`.

* Embedded `parameter_hash` column:

  * MUST exist and be non-null.
  * MUST equal the `parameter_hash` recorded in `s0_gate_receipt_5A` for this fingerprint.

Any mismatch between:

* partition token vs embedded `manifest_fingerprint`, or
* embedded `parameter_hash` vs S0’s `parameter_hash`

MUST be treated as a hard validation error in S1’s acceptance criteria.

---

### 7.3 Primary keys & logical ordering

#### 7.3.1 Primary keys

Dataset primary keys are binding and MUST be enforced:

* **`merchant_zone_profile_5A`**

  * `primary_key: ["merchant_id","legal_country_iso","tzid"]`

  Constraints:

  * For a given `(manifest_fingerprint)`, at most one row per `(merchant_id, legal_country_iso, tzid)`.
  * All three fields MUST be non-null and reference valid keys in upstream `zone_alloc` and merchant reference tables.

* **`merchant_class_profile_5A`** (if implemented)

  * `primary_key: ["merchant_id"]`

  Constraints:

  * For a given `(manifest_fingerprint)`, at most one row per `merchant_id`.
  * Every `merchant_id` here MUST appear at least once in `merchant_zone_profile_5A` for the same fingerprint.

Violations of these PK constraints MUST cause S1 to fail (no partial or conflicting outputs).

#### 7.3.2 Logical ordering

Physical ordering in storage is **not semantically significant**, but S1 MUST impose a deterministic writer order for reproducibility and validation:

* For `merchant_zone_profile_5A`:
  sort rows by `(merchant_id, legal_country_iso, tzid)` before writing.

* For `merchant_class_profile_5A` (if used):
  sort rows by `merchant_id` before writing.

Consumers MUST NOT rely on any particular physical ordering beyond what is implied by keys; ordering is purely for stable file content and easier debugging.

---

### 7.4 Merge discipline & rewrite semantics

5A.S1 follows a **no-merge, single-writer** discipline per fingerprint.

Binding rules:

1. **No in-place merge or append**

   * For a given `manifest_fingerprint`, S1 MUST NOT:

     * append to an existing `merchant_zone_profile_5A`,
     * update subsets of rows, or
     * perform any row-level “merge” operations.
   * Outputs are conceptually **atomic** for that fingerprint.

2. **Idempotent re-runs allowed**

   * If S1 is re-run for the same `(parameter_hash, manifest_fingerprint)` and existing outputs for that fingerprint are present:

     * S1 MUST recompute outputs in-memory;
     * if the recomputed outputs are byte-identical to existing files (under the same serialisation and ordering), S1 MAY:

       * log that outputs are already up-to-date and
       * exit without writing (idempotent no-op).

3. **Conflicting rewrites forbidden**

   * If existing outputs for this fingerprint differ in any way from what S1 would now produce—different rows, different class/scale values, different counts—S1 MUST:

     * treat this as an output conflict, and
     * fail with a canonical error (e.g. `S1_OUTPUT_CONFLICT`).

   * S1 MUST NOT overwrite or merge away the discrepancy. Any legitimate change to:

     * class definitions,
     * scale policy, or
     * upstream inputs that affect S1 outputs

     MUST be expressed via a new `parameter_hash` and/or `manifest_fingerprint`, not by mutating outputs under the same fingerprint.

4. **No cross-fingerprint merging**

   * S1 MUST NOT aggregate or merge outputs across different `manifest_fingerprint` values.
   * Each fingerprint partition is **self-contained** and represents a sealed world.

---

### 7.5 Interaction with other identity dimensions

#### 7.5.1 Seed

* `seed` plays no role in 5A.S1 outputs:

  * MUST NOT appear as a partition key.
  * MUST NOT be embedded as a column in S1 datasets.

5A.S1 operates at the manifest + parameter pack level only; any seed-specific behaviour belongs to later segments (e.g. 5B, routing).

#### 7.5.2 Run ID

* `run_id` MUST NOT be a partition key or part of dataset primary keys.
* It MAY appear only:

  * in logs/run-report entries, and
  * optionally in in-memory metadata; not as a persisted column in S1 outputs.

#### 7.5.3 Parameter hash

* `parameter_hash` MUST be embedded as a column in all S1 outputs.
* It MUST be constant across all rows for a given `manifest_fingerprint`.
* It MUST equal the `parameter_hash` in `s0_gate_receipt_5A`.

`parameter_hash` is not a partition key for S1 datasets; it is a binding identity attribute.

---

### 7.6 Cross-segment identity alignment

S1 outputs must align with upstream identities:

1. **Alignment with 3A (`zone_alloc`)**

   * Each `(merchant_id, legal_country_iso, tzid)` in `merchant_zone_profile_5A` MUST exist in 3A’s `zone_alloc` for the same `manifest_fingerprint`.
   * There MUST be a foreign-key relationship:

     ```text
     merchant_zone_profile_5A.(merchant_id, legal_country_iso, tzid, manifest_fingerprint)
       → zone_alloc.(merchant_id, legal_country_iso, tzid, manifest_fingerprint)
     ```

2. **Alignment with merchant reference**

   * Every `merchant_id` in S1 outputs MUST exist in the merchant reference tables sealed in `sealed_inputs_5A`.
   * `merchant_class_profile_5A` MUST be derivable purely by aggregating `merchant_zone_profile_5A` over `merchant_id`.

3. **Alignment with S0**

   * `manifest_fingerprint` and `parameter_hash` in S1 outputs MUST match the values recorded in `s0_gate_receipt_5A` for this fingerprint.
   * Any downstream consumer can use `(manifest_fingerprint, parameter_hash)` to join:

     * S0 control-plane outputs,
     * S1 modelling outputs, and
     * later 5A/5B/6A artefacts.

If any of these alignments fail (e.g. S1 produces a row for a `(merchant, zone)` that does not exist in `zone_alloc`), S1 MUST treat this as a validation failure and MUST NOT publish its outputs.

---

Within these constraints, 5A.S1’s identity, partitioning, ordering and merge discipline are fully specified: there is a single, immutable demand profile per `(merchant, zone)` and per fingerprint, keyed and aligned with Layer-1, with no cross-run merging and only idempotent re-runs allowed.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 5A.S1 is considered green** for a given `(parameter_hash, manifest_fingerprint)` and the **hard preconditions** it imposes on downstream states. All rules here are **binding**.

---

### 8.1 Conditions for 5A.S1 to “PASS”

For a given `(parameter_hash, manifest_fingerprint)`, 5A.S1 is considered **successful** only if **all** of the following hold:

1. **S0 gate & sealed inputs are valid**

   1.1 `s0_gate_receipt_5A` and `sealed_inputs_5A` exist for `fingerprint={manifest_fingerprint}` and are:

   * discoverable via the 5A dataset dictionary & artefact registry, and
   * schema-valid against
     `schemas.5A.yaml#/validation/s0_gate_receipt_5A` and
     `schemas.5A.yaml#/validation/sealed_inputs_5A`.

   1.2 Identity and digest invariants hold:

   * `s0_gate_receipt_5A.parameter_hash == parameter_hash`.
   * All rows in `sealed_inputs_5A` have `parameter_hash == parameter_hash` and `manifest_fingerprint == manifest_fingerprint`.
   * Recomputed `sealed_inputs_digest` from `sealed_inputs_5A` equals `s0_gate_receipt_5A.sealed_inputs_digest`.

   1.3 Upstream segment status is acceptable:

   * For each of `1A`, `1B`, `2A`, `2B`, `3A`, `3B`,
     `s0_gate_receipt_5A.verified_upstream_segments[seg].status == "PASS"`.

2. **Required inputs for S1 are present in `sealed_inputs_5A`**

   2.1 All artefacts required by S1 (as per §2–§3) are present in `sealed_inputs_5A` for this fingerprint, with:

   * `status="REQUIRED"`,
   * appropriate `read_scope` (`"ROW_LEVEL"` where rows are needed), and
   * valid `schema_ref`, `path_template`, and `sha256_hex`.

   2.2 No required artefact referenced in the 5A dictionaries/registries for S1 is missing or marked unusable for this fingerprint.

3. **`merchant_zone_profile_5A` exists and is schema-valid**

   3.1 A dataset `merchant_zone_profile_5A` exists under the canonical path for `fingerprint={manifest_fingerprint}` and:

   * conforms to `schemas.5A.yaml#/model/merchant_zone_profile_5A`,
   * uses `partition_keys: ["fingerprint"]`, and
   * declares `primary_key: ["merchant_id","legal_country_iso","tzid"]`.

   3.2 All rows embed:

   * `manifest_fingerprint == {manifest_fingerprint}`,
   * `parameter_hash == {parameter_hash}`.

   3.3 The primary key is respected:

   * No duplicate `(merchant_id, legal_country_iso, tzid)` within the partition.
   * All three key fields are non-null and type-consistent.

4. **Domain coverage & alignment with 3A**

   4.1 Let `D_zone_alloc` be the set of `(merchant_id, legal_country_iso, tzid)` chosen as in-scope domain in §6.5 (i.e. from `zone_alloc` after applying any 5A policy filters).

   4.2 Let `D_profile` be the set of `(merchant_id, legal_country_iso, tzid)` present in `merchant_zone_profile_5A` for this fingerprint.

   Then S1 MUST ensure:

   * `D_profile == D_zone_alloc`
     (i.e. every in-scope `(merchant, zone)` has exactly one profile row and no extra rows exist).

   4.3 For every row in `merchant_zone_profile_5A`:

   * There exists a matching `zone_alloc` row for the same `(merchant_id, legal_country_iso, tzid, manifest_fingerprint)`.

5. **Classification and scale completeness**

   For every row in `merchant_zone_profile_5A`:

   5.1 Classification fields:

   * `demand_class` is non-null and valid according to the 5A classing policy (string constraints / enum).
   * If `demand_subclass` / `profile_id` are defined in the schema, any non-null values MUST be consistent with the policy (no “unknown” IDs).

   5.2 Scale fields (depending on chosen representation):

   * If `weekly_volume_expected` is present:

     * it MUST be finite and `≥ 0`.
   * If `scale_factor` is present:

     * it MUST be finite and `≥ 0`.

   5.3 No row may have *both* scale representations “absent” (e.g. null `weekly_volume_expected` and null `scale_factor`). At least one valid scale field MUST be set per row.

6. **Optional `merchant_class_profile_5A` is consistent (if implemented)**

   If `merchant_class_profile_5A` is materialised:

   6.1 The dataset exists and conforms to `schemas.5A.yaml#/model/merchant_class_profile_5A`, with:

   * `partition_keys: ["fingerprint"]`,
   * `primary_key: ["merchant_id"]`.

   6.2 Every `merchant_id` in `merchant_class_profile_5A` appears in `merchant_zone_profile_5A` for this fingerprint.

   6.3 All fields (e.g. `primary_demand_class`, aggregate volumes) are deterministic functions of `merchant_zone_profile_5A` plus policy.

7. **No partial or conflicting outputs**

   7.1 S1 MUST have either:

   * written both outputs (required-only if `merchant_class_profile_5A` omitted) atomically, or
   * written nothing in the canonical locations if any preceding step failed.

   7.2 If existing outputs were present for this fingerprint, they MUST have been:

   * byte-identical to the newly computed results (idempotent re-run), or
   * treated as an output conflict (in which case S1 MUST fail and NOT overwrite).

If **any** of these conditions fail, S1 MUST treat the state as **FAILED** for this fingerprint and MUST NOT leave partially updated S1 outputs in canonical locations.

---

### 8.2 Minimal content requirements

Even if the structural conditions above are met, S1 MUST enforce the following **content minima**:

1. **At least one sealed policy**

   * `merchant_class_policy_5A` and `demand_scale_policy_5A` MUST both be present in `sealed_inputs_5A` with `status="REQUIRED"` and usable `read_scope`.

2. **At least one merchant×zone row (unless policy explicitly declares “empty domain”)**

   * If `D_zone_alloc` is non-empty, `merchant_zone_profile_5A` MUST contain at least one row.
   * An entirely empty `merchant_zone_profile_5A` is only acceptable if the 5A policies explicitly permit an empty domain (e.g. scenario where 5A is disabled); such a case SHOULD be logged clearly.

3. **Class coverage**

   * There MUST be no row in `merchant_zone_profile_5A` with missing `demand_class`.
   * If the policy defines a “fallback” class, S1 MUST use it rather than leave the class blank.

If these minima are not met, S1 MUST fail even if schemas and identity look structurally correct.

---

### 8.3 Gating obligations on downstream 5A states (S2–S4)

Any downstream 5A state (S2, S3, S4, and the eventual 5A validation state) MUST obey the following gates:

1. **Require S0 and S1**

   Before doing any work, a downstream 5A state MUST:

   * validate S0 as in the S0 spec (present, schema-valid, digest-matching), and
   * validate that `merchant_zone_profile_5A`:

     * exists for `fingerprint={manifest_fingerprint}`,
     * conforms to its schema,
     * embeds the same `parameter_hash` and `manifest_fingerprint` as S0, and
     * covers the expected domain (as per 3A’s `zone_alloc` or as defined in that state’s spec).

2. **Treat S1 as the single authority for demand class & scale**

   * S2–S4 MUST treat `merchant_zone_profile_5A` as the **only** source of truth for:

     * `demand_class` (and any subclass/profile) per `(merchant, zone)`,
     * base scale parameters used to build intensity surfaces.

   * They MUST NOT:

     * recompute `demand_class` from raw features;
     * apply additional “inline” classing rules that conflict with S1;
     * adjust base scale parameters except via transformations defined in their own specs that clearly state they operate **on top of** S1’s scale.

3. **No widening of input universe**

   * If a `(merchant, zone)` is absent from `merchant_zone_profile_5A`, downstream states MUST treat it as **out-of-scope** for 5A.
   * They MUST NOT attempt to reconstruct missing rows by directly interrogating upstream Layer-1 surfaces.

4. **Optional datasets are not required gates**

   * Downstream states MUST NOT treat `merchant_class_profile_5A` as required; they MUST be able to function without it.
   * If they use it for diagnostics, they MUST still derive any critical decisions from `merchant_zone_profile_5A`.

---

### 8.4 Gating obligations on other segments (5B, 6A)

Segments that sit **downstream of 5A as a whole** (e.g. 5B, 6A) have two levels of gating:

1. **Segment-level PASS for 5A**

   * They MUST require `_passed.flag` (produced by the 5A validation state, not S1) to verify the 5A validation bundle before consuming any 5A outputs.

2. **S1-specific gates**

   * When they specifically rely on demand classes or base scale, they MUST:

     * reference `merchant_zone_profile_5A` as the authority;
     * enforce identity alignment (same `manifest_fingerprint` / `parameter_hash`);
     * refuse to proceed if `merchant_zone_profile_5A` is missing or schema-invalid for the fingerprint, even if other 5A components appear present.

---

### 8.5 When 5A.S1 MUST fail

5A.S1 MUST treat the state as **FAILED** and MUST NOT publish/modifiy outputs if any of the following occur:

* S0 gate is missing or invalid:

  * `s0_gate_receipt_5A` / `sealed_inputs_5A` missing, schema-invalid, or digest mismatch.

* Upstream segments not green:

  * any of `1A`, `1B`, `2A`, `2B`, `3A`, `3B` has status `"FAIL"` or `"MISSING"`.

* Required inputs for S1 cannot be resolved:

  * merchant attributes, `zone_alloc`, scenario configs, or required 5A policies missing from `sealed_inputs_5A` or unusable per `read_scope`.

* Domain or FK inconsistencies:

  * `merchant_zone_profile_5A` contains `(merchant, zone)` keys not in `zone_alloc` for this fingerprint, or
  * omits keys that policy declares in-scope.

* Classification/scale incompleteness:

  * any row lacks `demand_class`, or
  * all scale fields are null/invalid for any row, or
  * scale fields contain NaNs/Infs or negative values where prohibited.

* Output conflict:

  * existing `merchant_zone_profile_5A` (and `merchant_class_profile_5A`, if present) differ from recomputed values for this fingerprint.

In all such cases, S1 MUST:

* fail fast,
* leave canonical S1 outputs untouched (or absent), and
* emit a canonical S1 error code (defined in §9) via the run-report/logging mechanism.

---

Within these rules, 5A.S1 has a clear, binary notion of “green”: either the world is sealed, upstream is PASS, required inputs exist, and `merchant_zone_profile_5A` is complete and consistent — **or** S1 fails and downstream states MUST NOT proceed.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error codes** that **5A.S1 — Merchant & Zone Demand Classification** MAY emit, and the exact conditions under which they MUST be raised. These codes are **binding**: implementations MUST either use them directly or maintain a 1:1 mapping.

S1 errors are about **S1 itself** failing to produce a valid `merchant_zone_profile_5A` (and optional `merchant_class_profile_5A`). They are distinct from upstream statuses recorded in `s0_gate_receipt_5A`.

---

### 9.1 Error reporting contract

5A.S1 MUST surface failures via:

* the engine’s **run-report** (per-run summary), and
* structured logs / metrics.

Each failure MUST include, at minimum:

* `segment_id = "5A.S1"`
* `parameter_hash`
* `manifest_fingerprint`
* `run_id`
* `error_code` — one of the canonical codes below
* `severity` — at least `{"FATAL","WARN"}` (S1 failures here are FATAL)
* `message` — short human-readable summary
* `details` — optional structured context (e.g. offending `merchant_id`, `artifact_id`, `segment`)

S1 does **not** write a dedicated “error dataset”; errors live in run-report/logs.

---

### 9.2 Canonical error codes (summary)

| Code                              | Severity | Category                                |
| --------------------------------- | -------- | --------------------------------------- |
| `S1_GATE_RECEIPT_INVALID`         | FATAL    | S0 gate / sealed inputs                 |
| `S1_UPSTREAM_NOT_PASS`            | FATAL    | Upstream segment status (1A–3B)         |
| `S1_REQUIRED_INPUT_MISSING`       | FATAL    | Missing required sealed artefact        |
| `S1_REQUIRED_POLICY_MISSING`      | FATAL    | Missing 5A class/scale policy           |
| `S1_FEATURE_DERIVATION_FAILED`    | FATAL    | Feature assembly for some domain row    |
| `S1_CLASS_ASSIGNMENT_FAILED`      | FATAL    | No / ambiguous class for some row       |
| `S1_SCALE_ASSIGNMENT_FAILED`      | FATAL    | Invalid / missing scale for some row    |
| `S1_DOMAIN_ALIGNMENT_FAILED`      | FATAL    | Mismatch vs 3A zone domain              |
| `S1_OUTPUT_CONFLICT`              | FATAL    | Existing outputs differ from recomputed |
| `S1_IO_READ_FAILED`               | FATAL    | I/O / storage read error                |
| `S1_IO_WRITE_FAILED`              | FATAL    | I/O / storage write/commit error        |
| `S1_INTERNAL_INVARIANT_VIOLATION` | FATAL    | “Should never happen” guard             |

All of these are **fatal** for S1: on any of them, S1 MUST NOT publish or modify S1 outputs for the fingerprint.

---

### 9.3 Code-by-code definitions

#### 9.3.1 `S1_GATE_RECEIPT_INVALID` *(FATAL)*

**Trigger**

Raised when S1 cannot establish a valid S0 gate and sealed inventory for this fingerprint, for example:

* `s0_gate_receipt_5A` missing for `fingerprint={manifest_fingerprint}`, or not discoverable via the dictionary/registry.
* `sealed_inputs_5A` missing for this fingerprint.
* Schema validation failures for either dataset.
* `parameter_hash` in `s0_gate_receipt_5A` or in `sealed_inputs_5A` rows does **not** equal the S1 run’s `parameter_hash`.
* Recomputed `sealed_inputs_digest` from `sealed_inputs_5A` does not match `s0_gate_receipt_5A.sealed_inputs_digest`.

**Effect**

* S1 MUST abort immediately.
* No `merchant_zone_profile_5A` / `merchant_class_profile_5A` MAY be written or updated.
* Downstream 5A states MUST NOT be invoked for this fingerprint.

---

#### 9.3.2 `S1_UPSTREAM_NOT_PASS` *(FATAL)*

**Trigger**

Raised when upstream Layer-1 segments are not in a `"PASS"` status according to `s0_gate_receipt_5A.verified_upstream_segments`, e.g.:

* Any of `1A`, `1B`, `2A`, `2B`, `3A`, `3B` has status `"FAIL"` or `"MISSING"`.

Detected in Step 1 (§6.2).

**Effect**

* S1 MUST abort and MUST NOT attempt to read upstream fact datasets.
* No S1 outputs MAY be written.
* Operator must resolve upstream segment issues and re-run S0/S1.

---

#### 9.3.3 `S1_REQUIRED_INPUT_MISSING` *(FATAL)*

**Trigger**

Raised when a **required upstream artefact** for S1 is not present in `sealed_inputs_5A` or cannot be resolved to a usable dataset/config, for example:

* Merchant reference/attributes dataset absent or unusable.
* `zone_alloc` (or equivalent zone universe surface from 3A) absent.
* Declared required scenario config missing or unusable (`read_scope` incompatible with S1 needs, `schema_ref` invalid, etc.).

This is about **data artefacts**, not policies.

**Effect**

* S1 MUST abort during Step 2 (§6.3) and MUST NOT proceed to domain construction or classing.
* No S1 outputs MAY be written.
* Operator must ensure the missing artefacts are published and referenced in the dictionary/registry, then re-run S0+S1.

---

#### 9.3.4 `S1_REQUIRED_POLICY_MISSING` *(FATAL)*

**Trigger**

Raised when a **5A-specific policy** required for S1 is missing or unusable, for example:

* `merchant_class_policy_5A` missing from `sealed_inputs_5A` for this `parameter_hash`.
* `demand_scale_policy_5A` missing, or present but schema-invalid.
* Policy artefact has incompatible `read_scope` (e.g. mistakenly marked `ROW_LEVEL` when a config shape is expected).

Detected in Step 2 while loading policies.

**Effect**

* S1 MUST abort before building the domain or features.
* No S1 outputs MAY be written.
* Operator must fix policy deployment / parameter pack and re-run S0+S1.

---

#### 9.3.5 `S1_FEATURE_DERIVATION_FAILED` *(FATAL)*

**Trigger**

Raised when S1 cannot construct a valid feature vector `features(m,c,tz)` for at least one in-scope `(merchant, zone)` in domain `D`, for example:

* `merchant_id` present in `zone_alloc` but missing in merchant reference tables.
* Required merchant attributes (e.g. MCC, channel) missing and no policy-defined fallback exists.
* Required virtual flags in `virtual_classification_3B` missing for a merchant policy declares as “must-have”.

Detected in Step 4 (§6.5).

**Effect**

* S1 MUST abort and MUST NOT write any profile outputs for this fingerprint.
* The error `details` SHOULD include the offending `(merchant_id, legal_country_iso, tzid)` and missing fields.
* Operator must fix upstream or adjust the policy to handle the missing case explicitly.

---

#### 9.3.6 `S1_CLASS_ASSIGNMENT_FAILED` *(FATAL)*

**Trigger**

Raised when, for at least one `(merchant, zone)` in `D`, the classing policy cannot assign a valid class, or assigns classes ambiguously, for example:

* **No rule matched**: after evaluating `merchant_class_policy_5A`, no rule fires and no default/fallback class is defined.
* **Multiple conflicting rules matched** when the policy is supposed to be mutually exclusive, producing more than one candidate class.

Detected in Step 5 (§6.6).

**Effect**

* S1 MUST abort and MUST NOT publish outputs.
* `error_details` SHOULD identify the merchant×zone and, if possible, the policy branch(es) involved.
* Fix typically requires updating `merchant_class_policy_5A` or upstream features so every domain row has a unique class.

---

#### 9.3.7 `S1_SCALE_ASSIGNMENT_FAILED` *(FATAL)*

**Trigger**

Raised when base scale parameters cannot be assigned validly for at least one `(merchant, zone)`, for example:

* Policy logic yields `NaN`, `Inf`, or negative values where the schema forbids them.
* All scale fields (e.g. `weekly_volume_expected` and `scale_factor`) are null or missing for a row where at least one is required.
* Policy refers to a lookup key that does not exist (e.g. class×size bucket combination not covered by the scale table).

Detected in Step 6 (§6.7).

**Effect**

* S1 MUST abort and MUST NOT commit outputs.
* `error_details` SHOULD include:

  * the affected `(merchant_id, legal_country_iso, tzid)`, and
  * the offending scale field/value.
* Operator must adjust `demand_scale_policy_5A` or upstream features to ensure all domain rows receive valid, finite non-negative scales.

---

#### 9.3.8 `S1_DOMAIN_ALIGNMENT_FAILED` *(FATAL)*

**Trigger**

Raised when S1 detects a mismatch between:

* the in-scope domain `D` built from 3A `zone_alloc` (plus policy filters), and

* the keyset represented in `merchant_zone_profile_5A`, for example:

* Some `(merchant, zone)` in `zone_alloc` (that should be in-scope) has no corresponding row in `merchant_zone_profile_5A`.

* `merchant_zone_profile_5A` contains extra rows for `(merchant, zone)` pairs not present in `zone_alloc` for this fingerprint.

* Duplicate `(merchant_id, legal_country_iso, tzid)` rows exist in the output.

Detected in domain coverage checks (§6.8) or in a downstream validation state; conceptually owned by S1.

**Effect**

* S1 MUST treat the state as failed and MUST NOT consider the outputs valid.
* If detected post-write (e.g. by a validation step in the same state), S1 MUST either:

  * remove/mark the outputs as invalid (depending on runtime model), or
  * treat the write as failed and signal this via the run-report.
* Operator must fix either:

  * the policy filters defining `D`, or
  * the S1 implementation so that output domain matches 3A.

---

#### 9.3.9 `S1_OUTPUT_CONFLICT` *(FATAL)*

**Trigger**

Raised when outputs already exist for `fingerprint={manifest_fingerprint}` and differ from what S1 would now compute, for example:

* Existing `merchant_zone_profile_5A` under this fingerprint has different rows or values from the recomputed `PROFILE_ROWS`.
* Existing `merchant_class_profile_5A` (if present) is inconsistent with recomputed aggregates.

Detected in Step 9 (§6.10) when comparing recomputed outputs with existing ones.

**Effect**

* S1 MUST NOT overwrite existing outputs.
* S1 MUST abort and report `S1_OUTPUT_CONFLICT`.
* This typically indicates:

  * catalogue state or policies changed without changing `manifest_fingerprint` / `parameter_hash`, or
  * previous S1 run produced inconsistent outputs.

Resolution usually requires:

* minting a new `manifest_fingerprint` / `parameter_hash` for changed inputs, and
* re-running S0+S1 for the new identity.

---

#### 9.3.10 `S1_IO_READ_FAILED` *(FATAL)*

**Trigger**

Raised when S1 encounters I/O failures while reading **required** inputs, for example:

* Storage/permissions errors when reading:

  * `s0_gate_receipt_5A` or `sealed_inputs_5A`,
  * `zone_alloc`, merchant attributes, virtual classification tables,
  * required policies or scenario configs.

This code is for genuine I/O/storage problems, not for logical absence (which is `S1_REQUIRED_INPUT_MISSING` / `S1_REQUIRED_POLICY_MISSING`).

**Effect**

* S1 MUST abort and not attempt partial workarounds.
* No S1 outputs MAY be written or updated.
* Operator must resolve storage/network/permissions issues and may then re-run S1.

---

#### 9.3.11 `S1_IO_WRITE_FAILED` *(FATAL)*

**Trigger**

Raised when S1 fails during writing or committing its outputs, for example:

* Cannot write staging files for `merchant_zone_profile_5A` / `merchant_class_profile_5A`.
* Failure to atomically move staging files to canonical paths.

**Effect**

* S1 MUST treat the state as failed.
* Partially written staging data MUST remain under clearly non-canonical locations (e.g. `.staging/`) that downstream consumers ignore.
* Operator must fix the underlying I/O issue and re-run S1.

---

#### 9.3.12 `S1_INTERNAL_INVARIANT_VIOLATION` *(FATAL)*

**Trigger**

Catch-all for internal logic errors or “impossible” states that do not fit a more specific code, e.g.:

* Duplicates in domain `D` after applying de-duplication rules.
* Inconsistent internal maps (e.g. lost entries between feature-assembly and classing).
* Any situation where the implementation detects it has violated its own invariants before or after writing outputs.

**Effect**

* S1 MUST abort and MUST NOT write or modify outputs.
* `error_details` SHOULD capture enough context (e.g. step name, subset of offending keys) for engineering investigation.
* This usually indicates a bug in the implementation or deployment, not in the data or configuration.

---

### 9.4 Relation to upstream statuses

To avoid confusion:

* **Upstream statuses** (`"PASS" / "FAIL" / "MISSING"`) for 1A–3B are recorded in `s0_gate_receipt_5A.verified_upstream_segments` and are not S1 error codes.
* `S1_UPSTREAM_NOT_PASS` is raised by S1 **only** when those statuses indicate that upstream is not green enough for S1 to proceed.

Downstream states must:

* consult `s0_gate_receipt_5A` for upstream segment status, and
* consult S1’s run-report/logs for the canonical error code when S1 fails.

Together, these error codes provide a complete, unambiguous vocabulary for describing why 5A.S1 could not produce a clean, complete `merchant_zone_profile_5A` for a given world.

---

## 10. Observability & run-report integration *(Binding)*

This section defines how **5A.S1 — Merchant & Zone Demand Classification** MUST report its activity into the engine’s **run-report**, logging, and metrics. These requirements are **binding**.

S1 is modelling-only (no RNG, no events), so observability MUST be **lightweight and aggregate-focused**, not row-dumping.

---

### 10.1 Objectives

Observability for 5A.S1 MUST allow operators and downstream segments to answer:

1. **Did S1 run for this world?**

   * For `(parameter_hash, manifest_fingerprint, run_id)` – did S1 start, succeed, or fail?

2. **If it failed, why?**

   * Which canonical error code?
   * Was it upstream, input, policy, domain, or output conflict?

3. **If it succeeded, what did it produce?**

   * How many merchants/zones were profiled?
   * How are demand classes and scale values distributed?
   * Which policies and scenario were in force?

All without logging individual merchant/zones or data rows.

---

### 10.2 Run-report entries

For **every invocation** of 5A.S1, the engine’s run-report MUST contain a structured record with at least:

* `segment_id = "5A.S1"`
* `parameter_hash`
* `manifest_fingerprint`
* `run_id`
* `state_status ∈ {"STARTED","SUCCESS","FAILED"}`
* `start_utc`, `end_utc` (UTC timestamps)
* `duration_ms`

On **SUCCESS**, the run-report MUST additionally include:

* `domain_size_merchants` — number of distinct `merchant_id` in `merchant_zone_profile_5A`.
* `domain_size_merchant_zones` — total rows in `merchant_zone_profile_5A`.
* `class_distribution` — map `demand_class → count` (aggregated counts only).
* `scale_stats` — high-level stats, e.g.:

  * `weekly_volume_expected_min`, `median`, `p95`, `max` **or**
  * `scale_factor_min`, `median`, `p95`, `max`
    depending on chosen representation.
* `policies_used` — IDs/versions of:

  * `merchant_class_policy_5A`
  * `demand_scale_policy_5A`
* `scenario_id` (from `s0_gate_receipt_5A`).

On **FAILED**, the run-report MUST include:

* `error_code` — one of §9’s codes (e.g. `S1_UPSTREAM_NOT_PASS`).
* `error_message` — short text summary.
* `error_details` — optional structured object (e.g. offending `merchant_id` / `artifact_id` / `segment`), avoiding sensitive values.

The run-report is the **primary authority** for S1’s outcome; logs/metrics support it.

---

### 10.3 Structured logging

5A.S1 MUST emit **structured logs** (e.g. JSON lines) keyed by `segment_id="5A.S1"` and `run_id`, with at least the following events:

1. **State start**

   * Level: `INFO`
   * Fields:

     * `event = "state_start"`
     * `segment_id = "5A.S1"`
     * `parameter_hash`, `manifest_fingerprint`, `run_id`
     * optional: environment tags (e.g. `env`, `ci_build_id`)

2. **Inputs resolved**

   * After Step 2 (§6.3) completes.
   * Level: `INFO`
   * Fields:

     * `event = "inputs_resolved"`
     * `required_inputs`: list or count by type (merchant_attrs, zone_alloc, virtual_classification, policies, scenario_config)
     * `policies_used`: IDs/versions for classing & scale policies
     * `scenario_id` / `scenario_type` (if defined)

3. **Domain summary**

   * After Step 3 (§6.4) constructs the domain `D`.
   * Level: `INFO`
   * Fields:

     * `event = "domain_built"`
     * `domain_size_merchant_zones = |D|`
     * `domain_size_merchants` (distinct `merchant_id` in `D`)
     * optional: counts by `virtual_mode` (e.g. physical vs virtual vs hybrid)

4. **Classification summary**

   * After Step 5 (§6.6), before writing outputs.
   * Level: `INFO`
   * Fields:

     * `event = "classification_summary"`
     * `class_distribution` (demand_class→count)
     * optional: `n_class_assignment_fallbacks` if fallback rules were used.

5. **Scale summary**

   * After Step 6 (§6.7).
   * Level: `INFO`
   * Fields:

     * `event = "scale_summary"`
     * `scale_metric` (e.g. `"weekly_volume_expected"` or `"scale_factor"`)
     * `scale_stats` (min/median/p95/max)
     * `n_high_variability_flag_true`, `n_low_volume_flag_true` (if such flags exist).

6. **State success**

   * Level: `INFO`
   * Fields:

     * `event = "state_success"`
     * `parameter_hash`, `manifest_fingerprint`, `run_id`
     * `domain_size_merchant_zones`
     * `duration_ms`

7. **State failure**

   * Level: `ERROR`
   * Fields:

     * `event = "state_failure"`
     * `parameter_hash`, `manifest_fingerprint`, `run_id`
     * `error_code`
     * `error_message`
     * `error_details` (e.g. `{ "merchant_id": "...", "legal_country_iso": "...", "tzid": "..." }` where safe)

**Prohibited logging:**

* S1 MUST NOT log:

  * full rows from `merchant_zone_profile_5A`,
  * raw upstream data rows (e.g. `zone_alloc`, merchant attributes),
  * or any content that would allow reconstructing bulk data from logs alone.

Only aggregate summaries and minimal key context for errors are permitted.

---

### 10.4 Metrics

5A.S1 MUST emit a small set of metrics suitable for monitoring. Names are implementation-specific; semantics are binding.

Recommended metrics:

1. **Run counters**

   * `fraudengine_5A_s1_runs_total{status="success"|"failure"}`
   * `fraudengine_5A_s1_errors_total{error_code="S1_REQUIRED_POLICY_MISSING"|...}`

2. **Latency**

   * `fraudengine_5A_s1_duration_ms` (histogram/summary metric)

3. **Domain size**

   * `fraudengine_5A_s1_domain_merchant_zones` (gauge, per-run)
   * `fraudengine_5A_s1_domain_merchants` (gauge, per-run)

4. **Class distribution aggregates**

   * `fraudengine_5A_s1_class_count{demand_class="..."}`

     * incremented by the count of rows in that class for the run.

5. **Scale aggregates**

   * `fraudengine_5A_s1_scale_expected_weekly_volume{quantile=...}` or similar, depending on how metrics are implemented;
   * or a small set of bucketed gauges/histograms representing the distribution of scale across merchant×zones.

Metrics MUST NOT include identifiers like `merchant_id` or specific tzids; they are aggregate-only.

---

### 10.5 Correlation & traceability

To support cross-cutting diagnostics, S1 MUST ensure that:

* Every run-report row, log entry, and metric for S1 includes:

  * `segment_id = "5A.S1"`
  * `parameter_hash`
  * `manifest_fingerprint`
  * and, where applicable, `run_id`.

If the engine supports distributed tracing (trace IDs / span IDs), S1 SHOULD:

* create or join a trace span named `"5A.S1"` or similar, and
* annotate it with `parameter_hash` and `manifest_fingerprint`.

This allows:

* tracing a 5A execution from:

  * S0 → S1 → later 5A states, and
  * logs ↔ run-report ↔ data artefacts.

---

### 10.6 Integration with 5A segment-level validation & dashboards

The 5A segment-level validation state (e.g. `5A.SX_validation`) MUST:

* treat `merchant_zone_profile_5A` as a **required input**, and
* use S1’s run-report/logs to:

  * confirm that S1 ran successfully for the fingerprint, and
  * capture domain size, class distribution, and scale stats into the 5A validation bundle or higher-level health reports.

Operational dashboards SHOULD be able to answer, for each active `(parameter_hash, manifest_fingerprint)`:

* Has 5A.S1 run and succeeded?
* How many merchants / merchant×zones are profiled?
* How are demand classes distributed across the world?
* Are there any recurring S1 failure modes (e.g. missing policies, domain alignment issues)?

Downstream segments MUST NOT rely on logs/metrics alone to gate their work; they MUST still obey the **data-level gates** (i.e. presence and validity of `s0_gate_receipt_5A` and `merchant_zone_profile_5A` as per §§2, 4, 8). Observability is a diagnostic layer, not an authority for gating.

Within these rules, 5A.S1 is fully observable: its executions can be tracked, failures diagnosed, and outputs summarised, without leaking or duplicating bulk merchant/zone data.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on the performance profile of **5A.S1 — Merchant & Zone Demand Classification**, and how to scale it sensibly. It explains what grows with data size, what should stay cheap, and where to be careful.

---

### 11.1 Performance summary

* 5A.S1 is **CPU-light and I/O-moderate** compared to event-level segments:

  * It works at **merchant×zone granularity**, not per-site or per-event.
  * It performs **joins + feature engineering + table lookups**, but **no RNG** and **no time series**.
* Runtime is dominated by:

  * scanning the **zone universe** (3A `zone_alloc`),
  * joining merchant attributes and optional virtual flags,
  * applying class & scale policies across all `(merchant, zone)` rows,
  * writing a single `merchant_zone_profile_5A` table (and optional merchant aggregate).

In a typical setup, S1 should be **much cheaper** than, say, 1B / 2B / 5B, and scale roughly linearly with the number of merchant×zone pairs.

---

### 11.2 Workload characteristics

Let:

* `M` = number of merchants in the universe.
* `Z̄` = average number of zones per merchant (from 3A `zone_alloc`).
* `N = M × Z̄` = number of `(merchant, zone)` rows in domain `D`.

Then:

* Input volumes:

  * Merchant attributes: O(`M`) rows (one or a few per merchant).
  * Zone allocation (`zone_alloc`): O(`N`) rows.
  * Virtual classification: O(`M`) rows (one per merchant).
  * Scenario & policies: O(1) small configs.

* Output volumes:

  * `merchant_zone_profile_5A`: O(`N`) rows.
  * `merchant_class_profile_5A` (if implemented): O(`M`) rows.

S1 is effectively a **single pass over `N` rows** with cheap joins + lookups.

---

### 11.3 Complexity bounds

For a fixed fingerprint:

* **Feature assembly (Step 4)**

  * Joins:

    * `zone_alloc` ⨝ merchant attributes ⨝ virtual flags ⨝ any extra reference tables.
  * Complexity: O(`N`) assuming indexed joins / hash joins against O(`M`) tables.

* **Classing (Step 5)**

  * For each `(m,c,tz)`, evaluate a small rule set / decision tree.
  * Complexity: O(`N × R_class`) where `R_class` is the average number of rules evaluated per row (ideally small and bounded).

* **Scaling (Step 6)**

  * For each row, apply table lookup or formula.
  * Complexity: O(`N × R_scale`) with `R_scale` typically small.

Overall:

> **Time complexity** ≈ O(`N × (R_class + R_scale)`)
> **Space complexity** ≈ O(`N`) to hold feature/profile rows (or streaming if implemented that way).

Given that `R_class` and `R_scale` are policy-bounded constants, S1 is essentially **linear in the number of merchant×zone rows**.

---

### 11.4 I/O patterns & hotspots

**Reads**

* `zone_alloc`:

  * Full scan of O(`N`) rows.
  * Access pattern: sequential read is preferred.

* Merchant attributes / virtual classification / extra refs:

  * O(`M`–`N`) rows depending on design.
  * Access pattern: mostly join-style reads (can be loaded fully into memory and hashed).

* Policies & scenario configs:

  * Small config blobs; negligible I/O.

**Writes**

* `merchant_zone_profile_5A`:

  * Single Parquet file of O(`N`) rows, partitioned by fingerprint.
  * Optional `merchant_class_profile_5A`: single O(`M`) rows file.

**Potential hotspots**

* Very large `N` (e.g. very large multizone merchants) can push `merchant_zone_profile_5A` into the tens of millions of rows; classification and scale policy should remain **simple per row** to keep CPU manageable.
* Inefficient feature joins (e.g. repeated non-indexed lookups per row) can cause disproportionate CPU and I/O; pre-loading merchant attributes and virtual flags into in-memory maps greatly reduces this.

---

### 11.5 Parallelisation & partitioning strategy

S1 is naturally parallelisable across the domain `D`.

Recommended approach:

* **Partition by merchant or zone range in memory**, not by additional storage partitions:

  * Read `zone_alloc` for the fingerprint into a distributed or chunked structure (e.g. partition by merchant_id hash or by zone).
  * Broadcast or shard merchant attributes and virtual flags as needed.

* **Per-chunk parallelism**:

  * Each worker:

    * consumes a subset of `D`,
    * applies feature assembly, classing, and scaling,
    * writes into an in-memory buffer;
  * Buffers are then merged and written as a single file (or a small set of files with a deterministic merge order).

* **No extra storage partitions**:

  * Avoid introducing `merchant_id` or `zone_id` as path-level partitions (keeps dictionary/registry simpler, matches spec).

**Scaling out:**

* For very large `N`, S1 can be run on distributed compute (e.g. Spark / Flink / Ray style environment) as long as:

  * identity & ordering rules from §7 are preserved, and
  * the final outputs are reconciled into the single fingerprint partition defined in the dictionary.

---

### 11.6 Memory & streaming considerations

For moderate `N`, keeping `PROFILE_ROWS` (and `CLASS_ROWS` if used) in memory is straightforward.

For very large `N`:

* **Streaming / chunked approach:**

  * Process `zone_alloc` in chunks:

    * derive features → class → scale → write chunk to a staging file,
    * avoid holding the entire `PROFILE_ROWS` in memory at once.
  * Then merge staged chunks into a single Parquet file in a deterministic order.

* **In-memory lookups:**

  * Merchant attributes and virtual classification tables are O(`M`), typically much smaller than `N`.
  * Loading them into in-memory hash maps is usually safe and greatly reduces join overhead.

The spec does not mandate a particular implementation strategy; it only requires:

* deterministic results,
* single fingerprint partition, and
* atomic commit semantics.

---

### 11.7 Failure, retry & backoff

Because S1 is deterministic and idempotent for a given sealed world:

* **Transient failures** (I/O read/write issues):

  * Safe to retry after backoff, as long as no canonical outputs were partially written.
  * On retry, S1 will recompute the same `merchant_zone_profile_5A` for the same fingerprint.

* **Deterministic / config failures** (e.g. `S1_REQUIRED_POLICY_MISSING`, `S1_CLASS_ASSIGNMENT_FAILED`, `S1_DOMAIN_ALIGNMENT_FAILED`):

  * Retrying without changing inputs/policies will not help.
  * Orchestration SHOULD stop retrying and surface the error to operators; fix requires:

    * upstream data repair, or
    * policy updates + new `parameter_hash` / `manifest_fingerprint`.

* **Output conflicts** (`S1_OUTPUT_CONFLICT`):

  * Indicates catalogue drift or policy changes without identity changes.
  * Resolution is to **mint a new world identity** (new fingerprint / parameter hash) and re-run.

---

### 11.8 Suggested SLOs (non-binding)

Actual targets are environment-dependent, but as a rough guideline:

* **Latency per fingerprint** (assuming `N` up to low millions):

  * p50: < 10–30 seconds
  * p95: < 1–2 minutes

  With appropriate parallelism and I/O, considerably lower latencies are realistic.

* **Error rates**:

  * `S1_IO_*` errors: rare and tied to infrastructure issues.
  * `S1_REQUIRED_*_MISSING` and `S1_CLASS/ SCALE_*_FAILED`: treated as configuration/data quality problems, not normal operational noise.

---

Within these guidelines, 5A.S1 should remain a **predictable, linear-time classification step**: easy to parallelise, cheap compared to event-level workloads, and largely bounded by the size and complexity of the merchant×zone universe rather than by deep algorithmic complexity.

---

## 12. Change control & compatibility *(Binding)*

This section defines how **5A.S1 — Merchant & Zone Demand Classification** and its contracts may evolve over time, and what compatibility guarantees MUST hold. All rules here are **binding**.

The aim is:

* no silent breaking changes to S1 outputs,
* a clear separation between **“spec changes”** and **“policy / parameter pack changes”**, and
* a predictable path for adding new capabilities.

---

### 12.1 Scope of change control

Change control for 5A.S1 covers:

1. **Row schemas & shapes**

   * `schemas.5A.yaml#/model/merchant_zone_profile_5A`
   * `schemas.5A.yaml#/model/merchant_class_profile_5A` (if implemented)

2. **Catalogue contracts**

   * `dataset_dictionary.layer2.5A.yaml` entries for:

     * `merchant_zone_profile_5A`
     * `merchant_class_profile_5A` (optional)
   * `artefact_registry_5A.yaml` entries for the same.

3. **Algorithm semantics**

   * The deterministic algorithm in §6 (domain, feature assembly, classing, scale).
   * Identity, partition, and merge discipline in §7.
   * Acceptance & gating rules in §8.

Changes to **policies** (e.g. `merchant_class_policy_5A`, `demand_scale_policy_5A`) and **parameter packs** are governed separately, but they interact with S1 through `parameter_hash` and `sealed_inputs_5A` and are covered in §12.6.

---

### 12.2 Versioning of S1 contracts

#### 12.2.1 Spec version field

To support evolution, S1 MUST expose a **spec / schema version** for its outputs:

* `s1_spec_version` — string (e.g. `"1.0.0"`)

Binding requirements:

* `s1_spec_version` MUST appear as a **required** field in `merchant_zone_profile_5A`.
* It MAY optionally appear in `merchant_class_profile_5A` (if implemented), but the primary anchor is the zone profile.

`schemas.5A.yaml#/model/merchant_zone_profile_5A` MUST define `s1_spec_version` as:

* Type: string
* Non-nullable

#### 12.2.2 Versioning scheme

S1 MUST use a semantic-style version for `s1_spec_version`:

* `MAJOR.MINOR.PATCH`

Interpretation:

* **MAJOR** — Incremented when **backwards-incompatible** changes are introduced (see §12.4).
* **MINOR** — Incremented for **backwards-compatible** enhancements (see §12.3).
* **PATCH** — Incremented for bug fixes / clarifications that do not change schema shapes or observable behaviour.

Downstream consumers (5A.S2–S4, 5B, 6A) MUST:

* read `s1_spec_version`,
* accept only MAJOR versions they explicitly support, and
* fail fast if they encounter an unsupported MAJOR version.

---

### 12.3 Backwards-compatible changes (allowed without MAJOR bump)

The following changes are considered **backwards-compatible** for S1, and MAY be introduced with a **MINOR** (or PATCH) version bump, provided they follow the rules below.

#### 12.3.1 Adding optional fields

Allowed:

* Adding new **optional** fields to:

  * `merchant_zone_profile_5A`,
  * `merchant_class_profile_5A`.

Conditions:

* JSON-Schema MUST mark them as `nullable` or not `required`.
* Default semantics for “field absent” MUST be clearly defined (e.g. “absent == false” for a boolean flag).
* Existing consumers MUST be able to ignore them without semantic breakage.

Examples:

* Adding `virtual_preferred_flag` as an optional boolean.
* Adding a `class_source` string for debugging.

#### 12.3.2 Adding new `demand_class` values

Allowed:

* Introducing new `demand_class` values (e.g. a new segment type) **via policy changes and `parameter_hash`**, without changing the S1 spec.

Conditions:

* The schema for `demand_class` MUST be either:

  * a free-form string with documented semantics, or
  * an enum that is updated in a backwards-compatible way *and* not hard-coded by downstream components.

* Downstream code MUST treat `demand_class` as a **label** looked up via the parameter pack (e.g. into shape libraries), not as a fixed compile-time enum.

Note: introducing new classes is primarily a **policy change**, not a spec change. It should typically be accompanied by a **new `parameter_hash`**, but does **not** require changing `s1_spec_version` unless the structural contract changes.

#### 12.3.3 Adding new flags / attributes

Allowed:

* Adding new optional flags or attributes in profiles, e.g.:

  * `high_variability_flag`, `holiday_sensitive_flag`, etc.

Conditions:

* They MUST be optional in schema.
* They MUST not change semantics of existing fields.
* Downstream components MUST not depend on them being present unless they explicitly check `s1_spec_version` and/or parameter pack.

#### 12.3.4 Additional reference links

Allowed:

* Adding optional foreign-key references (e.g. to new Layer-2 reference tables) in S1 schemas/dictionary, as long as:

  * they do not change existing keys,
  * they are optional, and
  * datasets remain discoverable and valid for existing consumers.

---

### 12.4 Backwards-incompatible changes (require MAJOR bump)

The following changes are **backwards-incompatible** and MUST be accompanied by:

* a new **MAJOR** in `s1_spec_version`, and
* a coordinated rollout across all consumers (S2–S4, 5B, 6A).

#### 12.4.1 Changing primary keys or partitioning

Incompatible:

* Changing `primary_key` or `partition_keys` of:

  * `merchant_zone_profile_5A` (currently `[merchant_id, legal_country_iso, tzid]` and `["fingerprint"]`),
  * `merchant_class_profile_5A` (currently `[merchant_id]` and `["fingerprint"]`).

Any such change would break joins and identity assumptions; it MUST be treated as a new MAJOR.

#### 12.4.2 Renaming or removing required fields

Incompatible:

* Renaming or removing any **required** field in S1 schemas, e.g.:

  * `merchant_id`, `legal_country_iso`, `tzid`,
  * `demand_class`,
  * required scale fields (`weekly_volume_expected` or `scale_factor`),
  * `manifest_fingerprint`, `parameter_hash`, `s1_spec_version`.

* Changing a required field’s type (e.g. `demand_class` from string to object).

#### 12.4.3 Changing scale semantics or units

Incompatible:

* Changing the **meaning or units** of a scale field without changing its name, for example:

  * redefining `weekly_volume_expected` from “expected arrivals per 7-day local week” to “expected arrivals per day”,
  * redefining `scale_factor` to mean a different baseline.

If such a change is needed, it MUST:

* be accompanied by a MAJOR spec bump, and
* be explicitly documented in the S1 spec / release notes.

#### 12.4.4 Changing domain semantics

Incompatible:

* Changing what constitutes the domain of `merchant_zone_profile_5A` in a way that breaks assumptions downstream, e.g.:

  * moving from “all `(merchant, legal_country_iso, tzid)` in 3A’s `zone_alloc` (subject to policy)” to a completely different notion of zone (e.g. physical sites or country-only) without a new MAJOR.

Any domain semantics change that invalidates the “1:1 overlay over 3A zone universe” assumption is breaking.

#### 12.4.5 Changing classing / scale semantics in a way that breaks existing consumers

Incompatible:

* Redefining `demand_class` from “opaque label matched to shapes by policy” to “hard-coded numeric index with fixed meaning” without MAJOR bump.
* Changing the expected relationship between `demand_class` and the shape library contract in S2–S3 (e.g. old classes no longer map cleanly to shape definitions).

In practice, most class/scale changes should be done **via policy + parameter pack** (see §12.6), not via spec changes.

---

### 12.5 Compatibility of code with existing data

Implementations of S1 and its consumers MUST handle **older S1 outputs** correctly.

#### 12.5.1 Reading older `s1_spec_version` data

* If `s1_spec_version.MAJOR` is:

  * **within** the implementation’s supported range:

    * Consumers MUST accept and process the data,
    * MUST treat unknown optional fields as absent, and
    * MUST treat unknown `role`/flags as either “ignored” or “treated as default” as defined by the spec.

  * **greater than** the supported MAJOR:

    * Consumers MUST refuse to operate on these S1 outputs,
    * MUST surface a clear “unsupported S1 spec version” error.

#### 12.5.2 Re-running S1 with newer code

* Re-running S1 with a new implementation for an existing `(parameter_hash, manifest_fingerprint)`:

  * If **policies and upstream sealed inputs are unchanged**, S1 SHOULD produce byte-identical outputs (idempotent).
  * If policies or sealed inputs **have changed**, a new `parameter_hash` and/or `manifest_fingerprint` SHOULD be minted. Using the old fingerprint and `parameter_hash` with changed inputs risks `S1_OUTPUT_CONFLICT`.

#### 12.5.3 Downstream use of `demand_class`

* Downstream code MUST NOT:

  * hard-code exhaustive lists of `demand_class` values, or
  * assume a specific set of classes is universal and static across all parameter packs.

* Instead, they MUST:

  * treat `demand_class` as an opaque label whose semantics are defined in the parameter pack (shape library, configs), and
  * use the parameter pack and `parameter_hash` to map classes to shapes and downstream behaviour.

This allows new classes to be introduced via policy and `parameter_hash` without changing S1’s spec version.

---

### 12.6 Interaction with parameter packs & upstream changes

Most “behavioural” changes in S1 are intended to be carried by **parameter packs and policies**, not by schema changes.

#### 12.6.1 Policy changes (classing/scale) & `parameter_hash`

* Any change in:

  * `merchant_class_policy_5A`,

  * `demand_scale_policy_5A`, or

  * scenario configs that affect S1 output
    MUST cause:

  * a **new `parameter_hash`** (parameter pack identity), and

  * S0/S1 re-runs under that new `parameter_hash`.

* S1 spec version (`s1_spec_version`) may stay constant in such cases, as shapes & logic are unchanged at the contract level—the policies changed, not the spec.

#### 12.6.2 Upstream changes (1A–3B)

* If upstream Layer-1 segments change in a way that affects the domain or features, and those changes are reflected in:

  * new artifacts and/or digests,
  * a new `manifest_fingerprint`,

  then S1 MUST be rerun under the new `manifest_fingerprint`.

* S1’s job is to **follow upstream** via `sealed_inputs_5A`; it MUST NOT try to hide or compensate for upstream drift under the same fingerprint.

---

### 12.7 Governance & documentation

Finally, any change to S1’s contracts MUST be governed and documented:

1. **Spec updates**

   * Changes to §§1–12 for S1 MUST be versioned and reviewed together with:

     * updates to `schemas.5A.yaml` (model anchors),
     * updates to `dataset_dictionary.layer2.5A.yaml` entries,
     * updates to `artefact_registry_5A.yaml`.

2. **Release notes**

   * Every change that bumps `s1_spec_version` MUST be documented in release notes that state:

     * old → new version,
     * whether it is MAJOR / MINOR / PATCH,
     * summary of changes, and
     * any required actions for existing fingerprints (e.g. re-run S1, or treat older fingerprints as frozen).

3. **Testing**

   * New S1 implementations MUST be tested against:

     * synthetic catalogues (small toy worlds, including edge cases),
     * representative real worlds (large `N`).
   * Tests MUST cover:

     * idempotency (same inputs → same outputs),
     * conflict detection (`S1_OUTPUT_CONFLICT`),
     * backwards-compatibility (reading old S1 outputs within supported MAJOR).

Within these rules, 5A.S1 can evolve in a controlled way: class and scale behaviour can change via parameter packs and policies; structural/semantic changes to the tables are explicit, versioned, and coordinated, and downstream segments always know which version of the S1 contract they are dealing with.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix defines short-hands, symbols and abbreviations used in the **5A.S1 — Merchant & Zone Demand Classification** spec. It is **informative** only; if there is any conflict, binding sections (§1–§12) win.

---

### 13.1 Notation conventions

* **Monospace** (`merchant_zone_profile_5A`) → concrete dataset/field/config names.
* **UPPER_SNAKE** (`S1_OUTPUT_CONFLICT`) → canonical error codes.
* `"Quoted"` (`"PASS"`, `"ROW_LEVEL"`) → literal enum/string values.
* Single letters:

  * `m` → merchant
  * `c` → country (usually `legal_country_iso`)
  * `tz` → timezone / zone (IANA `tzid`)

---

### 13.2 Identity & scope symbols

| Symbol / field         | Meaning                                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------------------------- |
| `parameter_hash`       | Opaque identifier of the **parameter pack** (S1 policies, scenario configs, etc.) in force.             |
| `manifest_fingerprint` | Opaque identifier of the **closed-world manifest** of artefacts for this run.                           |
| `run_id`               | Unique identifier of this execution of Segment 5A for a given `(parameter_hash, manifest_fingerprint)`. |
| `fingerprint`          | Partition token derived from `manifest_fingerprint` (e.g. `fingerprint={manifest_fingerprint}`).        |
| `s1_spec_version`      | Semantic version of the 5A.S1 spec that produced the profiles (e.g. `"1.0.0"`).                         |
| `scenario_id`          | Scenario identifier active for this fingerprint (e.g. `"baseline"`, `"bf_2027_stress"`).                |
| `scenario_pack_id`     | Optional identifier of the scenario config bundle.                                                      |

---

### 13.3 Datasets & artefact identifiers (S1-related)

| Name / ID                   | Description                                                                               |
| --------------------------- | ----------------------------------------------------------------------------------------- |
| `merchant_zone_profile_5A`  | Required S1 output: per `(merchant, zone)` demand class + base scale profile.             |
| `merchant_class_profile_5A` | Optional S1 output: per-merchant aggregate view derived from `merchant_zone_profile_5A`.  |
| `s0_gate_receipt_5A`        | S0 control-plane receipt: upstream statuses, scenario binding, sealed-input digest.       |
| `sealed_inputs_5A`          | S0 inventory of all artefacts Segment 5A is allowed to read for this fingerprint.         |
| `zone_alloc`                | 3A egress (Layer-1): merchant×country×tzid zone allocation; S1’s domain authority.        |
| `virtual_classification_3B` | 3B egress: virtual/hybrid flags per merchant (if virtual is in scope).                    |
| `virtual_settlement_3B`     | 3B egress: settlement node per virtual merchant; used as a feature only.                  |
| `merchant_class_policy_5A`  | 5A policy artefact: classing rules mapping features → `demand_class` / `subclass`.        |
| `demand_scale_policy_5A`    | 5A policy artefact: rules mapping classes/features → base scale parameters.               |
| `scenario_config_*`         | Scenario config artefacts (calendar/metadata) sealed by S0; used as coarse inputs for S1. |

(Exact `artifact_id`/`manifest_key` values live in the dataset dictionary and artefact registry.)

---

### 13.4 Fields in `merchant_zone_profile_5A`

*(Exact schema is in §5; this table is conceptual.)*

| Field name               | Meaning                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------- |
| `merchant_id`            | Merchant key, matching Layer-1.                                                       |
| `legal_country_iso`      | ISO country for this merchant×zone, aligned with 3A’s `zone_alloc`.                   |
| `tzid`                   | IANA timezone ID representing the zone, aligned with 3A / 2A.                         |
| `manifest_fingerprint`   | Closed-world identity; MUST equal partition token.                                    |
| `parameter_hash`         | Parameter pack identity; same for all rows in this fingerprint.                       |
| `s1_spec_version`        | Version of the 5A.S1 spec that produced this row.                                     |
| `demand_class`           | Primary demand class label for this merchant×zone (e.g. `"local_retail_daytime"`).    |
| `demand_subclass`        | Optional refinement of `demand_class` (e.g. `"food_service"`), policy-defined.        |
| `profile_id`             | Optional numeric/string profile identifier, policy-defined.                           |
| `weekly_volume_expected` | Base expected arrivals per local 7-day week (if using absolute scale representation). |
| `scale_factor`           | Dimensionless multiplicative scale factor (if using factor-based representation).     |
| `high_variability_flag`  | Optional flag: merchant×zone expected to have high short-run variation.               |
| `low_volume_flag`        | Optional flag: merchant×zone expected to be very low volume.                          |
| `virtual_preferred_flag` | Optional flag: virtual edge routing is preferred for this merchant×zone.              |
| `class_source`           | Optional short string identifying the classing rule/branch applied.                   |
| `created_utc`            | Timestamp of S1 run (informational, not used in logic).                               |

Only some of these are required; see §5 for binding schema.

---

### 13.5 Fields in `merchant_class_profile_5A` (optional)

| Field name                     | Meaning                                                                                 |
| ------------------------------ | --------------------------------------------------------------------------------------- |
| `merchant_id`                  | Merchant key.                                                                           |
| `manifest_fingerprint`         | Fingerprint; same semantics as in zone profile.                                         |
| `parameter_hash`               | Parameter pack identity.                                                                |
| `primary_demand_class`         | Merchant-level primary class (e.g. majority or precedence-based from zone classes).     |
| `classes_seen`                 | Optional encoding of all `demand_class` values observed across zones for this merchant. |
| `weekly_volume_total_expected` | Optional sum of per-zone `weekly_volume_expected` across zones (if defined).            |

All values MUST be derivable from `merchant_zone_profile_5A` plus deterministic policy.

---

### 13.6 Domain & feature shorthand

| Symbol / phrase    | Meaning                                                                                                                    |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| `D`                | Domain of S1: set of `(merchant_id, legal_country_iso, tzid)` taken from 3A `zone_alloc` after applying 5A policy filters. |
| `features(m,c,tz)` | Feature record assembled for merchant×zone `(m,c,tz)` from sealed Layer-1 facts + scenario metadata.                       |
| `zone_site_count`  | Number of sites for `(merchant_id, legal_country_iso, tzid)` from 3A / Layer-1 surfaces.                                   |
| `scenario_traits`  | Coarse scenario characteristics derived from scenario configs (e.g. `baseline`, `stress_type`).                            |

---

### 13.7 Error codes (5A.S1)

Canonical error codes from §9 (for quick reference):

| Code                              | Brief description                                    |
| --------------------------------- | ---------------------------------------------------- |
| `S1_GATE_RECEIPT_INVALID`         | S0 gate / sealed inputs missing or inconsistent.     |
| `S1_UPSTREAM_NOT_PASS`            | Upstream segments 1A–3B not all `"PASS"`.            |
| `S1_REQUIRED_INPUT_MISSING`       | Required sealed artefact for S1 not present/usable.  |
| `S1_REQUIRED_POLICY_MISSING`      | Required S1 policy (class/scale) missing or invalid. |
| `S1_FEATURE_DERIVATION_FAILED`    | Cannot assemble features for some merchant×zone.     |
| `S1_CLASS_ASSIGNMENT_FAILED`      | No/ambiguous class for some merchant×zone.           |
| `S1_SCALE_ASSIGNMENT_FAILED`      | Invalid/missing scale for some merchant×zone.        |
| `S1_DOMAIN_ALIGNMENT_FAILED`      | Output domain does not match 3A `zone_alloc` domain. |
| `S1_OUTPUT_CONFLICT`              | Existing outputs differ from recomputed S1 outputs.  |
| `S1_IO_READ_FAILED`               | I/O error reading required inputs.                   |
| `S1_IO_WRITE_FAILED`              | I/O error writing/committing S1 outputs.             |
| `S1_INTERNAL_INVARIANT_VIOLATION` | Catch-all for internal “should never happen” states. |

These codes appear in run-report/logs, not in the S1 data schemas themselves.

---

### 13.8 Miscellaneous abbreviations

| Abbreviation | Meaning                                                |
| ------------ | ------------------------------------------------------ |
| S0           | State 0 (Gate & Sealed Inputs) in Segment 5A.          |
| S1           | State 1 (Merchant & Zone Demand Classification) in 5A. |
| L1 / L2      | Layer-1 / Layer-2.                                     |
| “zone”       | A `(legal_country_iso, tzid)` combination from 3A.     |
| “profile”    | Shorthand for a `merchant_zone_profile_5A` row.        |

This appendix is meant as quick reference while reading or implementing the 5A.S1 spec; authoritative definitions remain in the binding sections.

---
