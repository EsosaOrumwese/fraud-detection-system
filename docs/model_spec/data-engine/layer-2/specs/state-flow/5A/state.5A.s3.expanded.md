# 5A.S3 — Baseline Merchant×Zone Weekly Intensities (Layer-2 / Segment 5A)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5A.S3 — Baseline Merchant×Zone Weekly Intensities** for **Layer-2 / Segment 5A**. It is binding on any implementation of this state.

---

### 1.1 Role of 5A.S3 in Segment 5A

5A.S3 is the **“scale × shape” composer** for Segment 5A.

Given a sealed world `(parameter_hash, manifest_fingerprint)` with S0, S1 and S2 already in place, S3:

* takes **per-merchant×zone demand profiles** from 5A.S1:

  * `demand_class(m, zone)` and
  * base scale parameters for that `(merchant, zone)` (e.g. `weekly_volume_expected(m, zone)` or `scale_factor(m, zone)`),

* takes **per-class×zone unit-mass weekly shapes** from 5A.S2:

  * `shape_value(demand_class, zone[, channel], bucket_index)` over a local-week grid,

* and produces, for each in-scope `(merchant, zone, local_bucket)`:

> a **deterministic baseline local-time intensity**
> `λ_base_local(m, zone, k)` = “expected volume in bucket k, before calendars, scenarios, or randomness.”

5A.S3 is:

* **RNG-free** — it MUST NOT consume any RNG streams or emit RNG events.
* **Pre-calendar** — it encodes baseline weekly behaviour only, with **no** holidays, paydays, campaigns, or shocks.
* **Pre-event** — it does not generate arrivals or Poisson draws; it only produces expected intensities.

---

### 1.2 Objectives

5A.S3 MUST:

* **Compose S1 scale with S2 shapes**

  For every in-scope `(merchant, zone[, channel])` and every local-week bucket `k`:

  * use S1 to obtain:

    * `demand_class(m, zone)` and
    * base scale (e.g. `weekly_volume_expected(m, zone)`),
  * use S2 to obtain:

    * `shape_value(demand_class(m, zone), zone[, channel], k)` (unit-mass weekly shape),
  * and compute a baseline intensity:

    ```text
    λ_base_local(m, zone, k) = scale(m, zone) × shape_value(class(m,zone), zone[,channel], k)
    ```

  with precise unit semantics defined at spec time (e.g. “expected arrivals in local bucket k”).

* **Preserve upstream semantics**

  * Use S1’s `demand_class` and scale **as-is**; S3 MUST NOT reclassify or re-estimate base scales.
  * Use S2’s shapes **as unit-mass templates**; S3 MUST NOT re-shape or re-normalise them except for validation.

* **Provide a stable baseline surface for downstream use**

  * Produce a baseline intensity dataset that:

    * is keyed by `(merchant, zone[, channel], local_bucket_index)` and identity columns,
    * is deterministic for a given `(parameter_hash, manifest_fingerprint, scenario_id)`,
    * can be used by:

      * S4 to apply calendar/scenario overlays (holidays, paydays, campaigns), and
      * 5B to drive Poisson/LGCP realisation and routing.

* **Remain efficient and bounded**

  * Operate linearly in the size of the `(merchant, zone)` domain × local-week grid, without unnecessary joins or transforms.
  * Avoid scanning any more data than needed: S3 works off S1, S2, and fixed configs — not raw Layer-1 fact tables.

---

### 1.3 In-scope behaviour

The following activities are **in scope** for 5A.S3 and MUST be implemented here (not duplicated in later states):

* **Run-level gating on S0/S1/S2**

  * Checking that S0, S1 and S2 outputs are present, schema-valid, identity-consistent, and green for the current `(parameter_hash, manifest_fingerprint, scenario_id)`.

* **Domain construction**

  * Determining the S3 domain:

    ```text
    D_S3 = { (merchant, zone[, channel]) }
    ```

    based on `merchant_zone_profile_5A` (S1) and any explicit S3 policy filters (e.g. excluding merchants/zones marked as out-of-scope for baseline intensities).

* **Feature lookup per `(merchant, zone)`**

  * For each `(merchant, zone)` in the domain:

    * retrieving `demand_class(m, zone)` from S1,
    * retrieving base scale parameters from S1 (e.g. `weekly_volume_expected` or `scale_factor` plus any flags required by S3’s baseline policy).

* **Shape lookup per `(demand_class, zone[, channel])`**

  * Joining each `(merchant, zone)`’s `demand_class` to S2’s `class_zone_shape_5A` to obtain the vector:

    ```text
    { shape_value(class(m,zone), zone[,channel], k) : k in local_week }
    ```

  * Ensuring that every merchant×zone in S3’s domain has a corresponding class/zone shape from S2.

* **Baseline intensity computation**

  * Computing `λ_base_local(m, zone, k)` for all `(merchant, zone, k)`:

    * enforcing non-negativity and finite values,
    * enforcing per-merchant×zone consistency with S1’s base scale contract (e.g. sum over local week ≈ `weekly_volume_expected(m,zone)` if that is the governing interpretation).

* **Baseline dataset emission**

  * Emitting one or more datasets that:

    * encode `λ_base_local(m, zone, k)` over the local-week grid, keyed appropriately,
    * embed identity (`parameter_hash`, `manifest_fingerprint`, `scenario_id`),
    * are ready for S4 and 5B to consume.

* **Optional class-level aggregates**

  * Optionally producing class/zone baseline aggregates (e.g. summing `λ_base_local` across merchants) for diagnostics and visualisation, provided they are clearly marked as derived from merchant-level intensities.

---

### 1.4 Out-of-scope behaviour

The following activities are explicitly **out of scope** for 5A.S3 and MUST NOT be implemented in this state:

* **Randomness or stochastic modelling**

  * S3 MUST NOT:

    * draw Poisson/Gaussian/LGCP random variables,
    * apply day-to-day stochastic noise,
    * interact with RNG streams or audit logs.

  Stochastic realisation belongs to **5B** (and Layer-1 routing where applicable).

* **Calendar & scenario overlays**

  * S3 MUST NOT:

    * apply public holidays, paydays, campaigns, stress shocks, or maintenance outages,
    * encode seasonal/special-event multipliers.

  These overlays belong to **5A.S4** (calendar/scenario layer) and, to some extent, higher-level scenario logic.

* **Arrivals or event streams**

  * S3 MUST NOT:

    * generate concrete arrival timestamps or counts,
    * define arrival IDs or routing decisions.

  The first concrete arrival layer is **5B**, using S3 (and S4) intensities as input.

* **Upstream re-derivation**

  * S3 MUST NOT:

    * re-compute or override S1 demand classes or base scales,
    * re-compute or renormalise S2 shapes (beyond sanity checks),
    * infer zones or civil-time semantics from Layer-1 directly.

  It may only **consume** S1 and S2 surfaces as sealed, authoritative inputs.

* **Segment-level PASS for 5A**

  * S3 does not decide the overall “5A segment PASS”; it contributes outputs that the dedicated 5A validation state will validate and bundle.
  * S3 MUST NOT write `_passed.flag`; that belongs to the validation state.

---

### 1.5 Downstream obligations

This specification imposes the following obligations on downstream states (5A.S4 and any later consumers, including 5B/6A):

* **Gating on S3 outputs**

  * Before using baseline intensities, downstream states MUST check that:

    * `merchant_zone_baseline_local_5A` (and any other declared S3 outputs) exist for the target `(parameter_hash, manifest_fingerprint, scenario_id)`,
    * they are schema-valid, identity-consistent, and pass S3’s acceptance criteria.

* **Treat S3 as the baseline authority**

  * Downstream logic MUST treat S3’s baseline intensity surface as the **single source of truth** for:

    * merchant×zone×local-week baseline λ, prior to calendar overlays and randomness.

  * They MUST NOT:

    * re-multiply S1 scales and S2 shapes independently in conflicting ways,
    * substitute alternative baseline formulas that bypass S3.

* **No back-writes**

  * No later state may modify or overwrite S3 outputs for any `(parameter_hash, manifest_fingerprint, scenario_id)`.
  * Any required change to baseline behaviour MUST be expressed through:

    * updated S1/S2 policies → new `parameter_hash` / manifest, and
    * a re-run of S1/S2/S3 under those identities.

Within this scope, 5A.S3 cleanly defines **how merchant×zone scale and class shapes combine into a deterministic baseline intensity surface**, providing the anchor that S4 and 5B will build on.

---

## 2. Preconditions & sealed inputs *(Binding)*

This section defines when **5A.S3 — Baseline Merchant×Zone Weekly Intensities** is allowed to run, and what sealed inputs it may rely on. All rules here are **binding**.

---

### 2.1 Invocation context

5A.S3 MUST only be invoked in the context of a well-defined engine run characterised by:

* `parameter_hash` — identity of the parameter pack (S1/S2 policies, scenario config, etc.).
* `manifest_fingerprint` — identity of the closed-world manifest S0/S1 used.
* `scenario_id` — scenario under which baseline intensities are being constructed (baseline or stress).
* `run_id` — identifier for this S3 execution.

These MUST:

* be supplied by the orchestration layer,
* match the values used when **S0, S1 and S2** ran for the same world/parameter pack, and
* be treated as immutable for the duration of S3.

S3 MUST NOT recompute or override `parameter_hash`, `manifest_fingerprint`, or `scenario_id`.

---

### 2.2 Dependency on 5A.S0 (gate receipt & sealed inventory)

Before doing any work, S3 MUST require a valid S0 gate for the target `manifest_fingerprint`:

1. **Presence**

   * `s0_gate_receipt_5A` exists for `fingerprint={manifest_fingerprint}`.
   * `sealed_inputs_5A` exists for `fingerprint={manifest_fingerprint}`.

   Both MUST be located via `dataset_dictionary.layer2.5A.yaml` and `artefact_registry_5A.yaml`, not via ad-hoc paths.

2. **Schema validity**

   * `s0_gate_receipt_5A` MUST validate against `schemas.5A.yaml#/validation/s0_gate_receipt_5A`.
   * `sealed_inputs_5A` MUST validate against `schemas.5A.yaml#/validation/sealed_inputs_5A`.

3. **Identity consistency**

   * `s0_gate_receipt_5A.parameter_hash == parameter_hash`.
   * All rows in `sealed_inputs_5A` for this fingerprint have:

     * `parameter_hash == parameter_hash`, and
     * `manifest_fingerprint == manifest_fingerprint`.

4. **Sealed-inventory digest**

   * S3 MUST recompute `sealed_inputs_digest` from `sealed_inputs_5A` using the S0 hashing law and confirm equality with `s0_gate_receipt_5A.sealed_inputs_digest`.

If any of these checks fail, S3 MUST abort with a gate precondition failure and MUST NOT read upstream datasets or write outputs.

---

### 2.3 Upstream (Layer-1) and S1/S2 readiness

S3 sits on top of **Layer-1, S1 and S2**. It MUST NOT run unless all are green.

From `s0_gate_receipt_5A.verified_upstream_segments`, S3 MUST:

* read statuses for each of: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.

Precondition:

* For S3 to proceed, all of these segments MUST have `status="PASS"`.

If any required upstream segment has `status="FAIL"` or `status="MISSING"`, S3 MUST:

* abort with a precondition failure (e.g. `S3_UPSTREAM_NOT_PASS`), and
* MUST NOT attempt to read their egress datasets, even if present.

In addition, S3 depends directly on S1 and S2:

* **S1:** `merchant_zone_profile_5A` MUST:

  * exist for `(manifest_fingerprint, parameter_hash)`,
  * be schema-valid (`#/model/merchant_zone_profile_5A`),
  * have consistent `parameter_hash` / `manifest_fingerprint`.

* **S2:** `shape_grid_definition_5A` and `class_zone_shape_5A` MUST:

  * exist for `(parameter_hash, scenario_id)`,
  * be schema-valid (`#/model/shape_grid_definition_5A`, `#/model/class_zone_shape_5A`),
  * embed `parameter_hash` / `scenario_id` consistent with the current run.

If any of these S1/S2 conditions fail, S3 MUST treat this as a hard precondition failure and MUST NOT attempt to compose intensities.

---

### 2.4 Required sealed inputs for S3

Given a valid S0 gate, the **only inputs S3 may use** are those listed in `sealed_inputs_5A` for this fingerprint. For S3 to run, the following artefacts MUST be present and usable:

#### 2.4.1 S1: merchant & zone demand profiles

Required dataset:

* `merchant_zone_profile_5A` (owner_segment `"5A"`, role `"model"`, status `"required"`).

Preconditions:

* At least one row exists for this `manifest_fingerprint`.
* `sealed_inputs_5A` includes a row for this artefact with:

  * correct `schema_ref` → `schemas.5A.yaml#/model/merchant_zone_profile_5A`,
  * `read_scope="ROW_LEVEL"` (S3 must read rows),
  * consistent `path_template` and `partition_keys` (fingerprint only).

Role for S3:

* Provides the **(merchant, zone[, channel]) domain**.
* Provides `demand_class(m, zone)` and base scale parameters for each `(merchant, zone)`.

#### 2.4.2 S2: shape grid & class×zone shapes

Required datasets:

* `shape_grid_definition_5A`
* `class_zone_shape_5A`

Preconditions:

* `sealed_inputs_5A` includes rows for these artefacts with:

  * `owner_segment="5A"`,
  * `status="REQUIRED"`,
  * `schema_ref` → `schemas.5A.yaml#/model/shape_grid_definition_5A` and `#/model/class_zone_shape_5A`,
  * `partition_keys: ["parameter_hash","scenario_id"]`,
  * `read_scope="ROW_LEVEL"` (S3 reads rows to join bucket indices and shapes).

Role for S3:

* `shape_grid_definition_5A` defines the **local-week grid** that S3 intensities live on.
* `class_zone_shape_5A` provides the **unit-mass weekly shape** `shape_value(demand_class, zone[, channel], bucket_index)`.

S3 MUST NOT:

* reconstruct its own grid or shapes; it MUST use these as the canonical time and shape definitions.

#### 2.4.3 S3-specific baseline policies (if any)

If S3 defines additional baseline policies (names illustrative), they MUST be present:

* `baseline_intensity_policy_5A` — describes:

  * which base scale field from S1 to use (`weekly_volume_expected` vs `scale_factor`),
  * units conventions (arrivals per week vs per bucket),
  * any clipping or transformation rules (e.g. minimum/maximum allowed intensities).

Artefacts:

* Must appear in `sealed_inputs_5A` with:

  * `owner_segment="5A"`,
  * `role="policy"`,
  * `status="REQUIRED"` (if S3 depends on them),
  * valid `schema_ref` into `schemas.5A.yaml` or `schemas.layer2.yaml`,
  * a `read_scope` that allows reading their contents.

If such a policy is required by the S3 spec and missing, S3 MUST treat this as a precondition failure.

---

### 2.5 Permitted but optional sealed inputs

S3 MAY also use optional artefacts listed in `sealed_inputs_5A` with `status="OPTIONAL"`, for example:

* Diagnostic configs controlling additional logging or validation thresholds (e.g. how strictly to enforce weekly sum ≈ base scale).
* Optional reference tables for merchant/zone grouping used only in observability or aggregate reporting.

Rules:

* Absence of optional artefacts MUST NOT prevent S3 from producing valid outputs, as long as required artefacts exist.
* Optional inputs MUST NOT change core semantics of `λ_base_local`; they may only influence diagnostics or minor, documented refinements.

---

### 2.6 Authority boundaries for S3 inputs

The following boundaries are **binding**:

1. **`sealed_inputs_5A` is the exclusive universe**

   * S3 MUST treat `sealed_inputs_5A` as exhaustive for this fingerprint:

     * Only artefacts listed there may be read.
     * Datasets or configs not present in `sealed_inputs_5A` are out-of-bounds, even if physically present.

2. **S1 is the authority for class & base scale**

   * `merchant_zone_profile_5A` is the **only** source of `demand_class(m, zone)` and base scale for `(merchant, zone)`.
   * S3 MUST NOT:

     * reclassify merchants/zones,
     * recalculate base scale from other inputs,
     * ignore S1’s base scale in favour of ad-hoc logic.

3. **S2 is the authority for shapes & grid**

   * `shape_grid_definition_5A` is the **only** authority for the local-week bucket structure; S3 MUST NOT derive its own grid.
   * `class_zone_shape_5A` is the **only** authority for unit-mass weekly shapes; S3 MUST NOT alter or re-normalise shape profiles except for validation checks.

4. **No direct use of Layer-1 fact tables**

   * S3 MUST NOT read Layer-1 egress (sites, routing weights, civil time, zone_alloc, etc.) directly.
   * Any information needed from Layer-1 MUST arrive via S1/S2 or S3 policies, as sealed in `sealed_inputs_5A`.

5. **No out-of-band configuration**

   * S3 MUST NOT change behaviour based on environment variables, CLI flags, or feature switches that are not encoded in:

     * the parameter pack (`parameter_hash`), and
     * policy/config artefacts in `sealed_inputs_5A`.

Any change affecting baseline intensity behaviour MUST flow through:

* updated S1/S2/S3 policies → new parameter pack (`parameter_hash`), and
* a new S0/S1/S2/S3 run, **not** through ad-hoc runtime switches.

Within these preconditions and boundaries, 5A.S3 operates in a fully sealed, policy-driven world: S0 defines what exists and is trusted, S1 and S2 define classes/scales/shapes, and S3’s job is strictly to compose them into a deterministic baseline intensity surface.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **exactly what 5A.S3 may read**, which fields it is allowed to use, and which upstream components are authoritative for which facts. All rules here are **binding**.

5A.S3 is **RNG-free** and may only use inputs that:

* are explicitly listed in `sealed_inputs_5A` for the current `manifest_fingerprint`, and
* come from S0/S1/S2 or 5A policies/configs.

It MUST NOT talk directly to Layer-1 fact tables or invent new inputs.

---

### 3.1 Input categories (high-level)

S3 has four logical input categories:

1. **Control-plane inputs from S0**
   – to know which world/parameter pack/scenario it is in and what artefacts are sealed.

2. **Merchant×zone demand profiles from S1**
   – `demand_class` + base scale per `(merchant, zone[, channel])`.

3. **Class×zone weekly shapes & time grid from S2**
   – unit-mass shapes and bucket structure.

4. **S3-specific baseline policies/configs**
   – how to interpret base scale, units, and any optional clipping/transform rules.

All of these MUST be discovered via `sealed_inputs_5A` and resolved via the dataset dictionary + artefact registry. Anything else is out-of-bounds.

---

### 3.2 Control-plane inputs (S0)

#### 3.2.1 `s0_gate_receipt_5A`

**Role for S3**

* Identifies the world and pack:

  * `parameter_hash`
  * `manifest_fingerprint`
  * `scenario_id` (or IDs)
* Carries upstream status map:

  * `verified_upstream_segments[1A..3B].status`
* Carries `sealed_inputs_digest` for integrity.

**Authority boundary**

* S3 MUST treat `s0_gate_receipt_5A` as the **single source of truth** for:

  * which `(parameter_hash, manifest_fingerprint)` pair it is operating under,
  * whether upstream Layer-1 segments are `"PASS"`,
  * which scenario pack is bound to this fingerprint.
* S3 MUST NOT re-validate upstream bundles at the bit-level (beyond reading egress shapes), and MUST NOT modify the receipt.

#### 3.2.2 `sealed_inputs_5A`

**Role for S3**

* Defines the **complete set of artefacts** Segment 5A is allowed to read for this fingerprint, with:

  * `owner_segment`, `artifact_id`, `role`, `status`, `read_scope`,
  * `schema_ref`, `path_template`, `sha256_hex`.

**Authority boundary**

* S3 MUST:

  * derive its list of admissible datasets/configs **only** by scanning `sealed_inputs_5A`, and
  * respect each row’s `status` (`"REQUIRED"`, `"OPTIONAL"`, `"IGNORED"`) and `read_scope` (`"ROW_LEVEL"`, `"METADATA_ONLY"`).
* Any dataset/config not listed in `sealed_inputs_5A` for this fingerprint is **out-of-bounds**.

---

### 3.3 S1 merchant×zone demand profiles

**Logical input**

* `merchant_zone_profile_5A` (S1 output, `role="model"`, `status="REQUIRED"`).

**Columns S3 uses (minimal)**

For each `(merchant_id, legal_country_iso, tzid)`:

* Identity / zone:

  * `merchant_id`
  * `legal_country_iso`
  * `tzid` (or zone representation used by S1)
* Identity / pack:

  * `manifest_fingerprint`
  * `parameter_hash`
* Classification:

  * `demand_class` (required)
  * (optional) `demand_subclass` / `profile_id` – used only if S3 policy refers to them.
* Base scale:

  * one or more fields that S3 policy designates as **base scale**, e.g.:

    * `weekly_volume_expected` (expected total per local week), **or**
    * `scale_factor` (dimensionless multiplicative scale),
      plus any companion fields needed (e.g. units flags, confidence flags).

**Authority boundary**

* `merchant_zone_profile_5A` is the **only authority** for:

  * which `(merchant, zone)` pairs exist in S3’s domain, and
  * what `demand_class` and base scale apply to them.

S3 MUST NOT:

* recompute `demand_class` from merchant features or override it,
* re-estimate base scales from other inputs (counts, zone sizes, etc.),
* introduce new `(merchant, zone)` pairs not present in S1’s in-scope domain.

---

### 3.4 S2 shapes & time grid

#### 3.4.1 `shape_grid_definition_5A` (local-week grid)

**Logical input**

* `shape_grid_definition_5A` (S2 output, `role="model_config"`, `status="REQUIRED"`).

**Columns S3 uses (minimal)**

For grid definition per `(parameter_hash, scenario_id, bucket_index)`:

* `parameter_hash`, `scenario_id`
* `bucket_index`
* `local_day_of_week`
* `local_minutes_since_midnight` (or equivalent)
* `bucket_duration_minutes`

**Authority boundary**

* This grid is the **only definition** of the local-week discrete support S3 uses.
* S3 MUST:

  * construct all baseline intensities on this exact grid, and
  * NOT alter bucketisation (no skipping or reshaping buckets).

S3 MUST NOT:

* derive an alternative grid from tz rules, Layer-1 data, or wall-clock;
* add or remove buckets;
* alter `bucket_duration_minutes`.

#### 3.4.2 `class_zone_shape_5A` (unit-mass shapes)

**Logical input**

* `class_zone_shape_5A` (S2 output, `role="model"`, `status="REQUIRED"`).

**Columns S3 uses (minimal)**

For each `(parameter_hash, scenario_id, demand_class, zone[, channel], bucket_index)`:

* `parameter_hash`, `scenario_id`
* `demand_class`
* Zone representation:

  * `legal_country_iso` + `tzid`, or
  * `zone_id` (with a documented mapping back to `(country, tzid)`)
* Optional `channel` / `channel_group` (if shapes differ by channel)
* `bucket_index` (FK to grid)
* `shape_value` (non-negative, unit-mass fraction)
* `s2_spec_version` (for compatibility checks only)

**Authority boundary**

* `class_zone_shape_5A` is the **sole authority** for unit-mass class×zone shapes.
* S3 MUST treat `shape_value` as:

  * non-negative, and
  * normalised over the week (Σ=1 per `(class, zone[, channel])`), as guaranteed by S2.

S3 MUST NOT:

* renormalise these shapes to a different sum, except for local numeric sanity checks,
* alter their relative patterns,
* interpret them in any unit other than “fraction of weekly volume” unless and until the S2 spec is changed and S3 is updated accordingly.

---

### 3.5 S3-specific baseline policies & configs

If defined, S3 relies on one or more 5A configs (names illustrative):

#### 3.5.1 `baseline_intensity_policy_5A`

**Logical content (conceptual)**

* Which base scale field to use from S1:

  * e.g. `scale_source = "weekly_volume_expected"` vs `"scale_factor"`.
* Units:

  * e.g. “`weekly_volume_expected` is expected count per local week, so area under λ_base_local over a local week MUST equal it.”
* Optional clipping rules:

  * minimum allowed per-bucket intensity,
  * maximum allowed per-bucket intensity,
  * default behaviour if S1 base scale is zero or very small.

**Authority boundary**

* This policy is the **only authority** for how S3 interprets base scale and converts it into per-bucket intensities.
* If `baseline_intensity_policy_5A` is present and marked `status="REQUIRED"`, S3 MUST implement its semantics and MUST NOT embed alternative or conflicting logic.

#### 3.5.2 Other S3 configs (optional)

Examples:

* `baseline_validation_policy_5A` — tolerances for weekly sum vs base scale checks (e.g. allowable relative/absolute error).
* Diagnostic configs controlling additional logging.

These MUST be treated as optional enhancements; their absence MUST NOT make S3 unable to produce valid intensities.

---

### 3.6 Optional reference data

S3 MAY use additional artefacts as long as:

* they are present in `sealed_inputs_5A` with `status="OPTIONAL"` and suitable `read_scope`, and
* they are referenced explicitly by S3 policies (e.g. for diagnostics or aggregate stats).

Examples:

* Merchant/zone grouping references for reporting (e.g. “segment A vs B vs C”).
* Region-level metadata used only for grouping in observability, not for intensity calculations.

Authority boundary:

* These artefacts MUST NOT change the definition of `λ_base_local`; they may only inform optional reporting or diagnostics.

---

### 3.7 Authority boundaries & out-of-bounds inputs

The following boundaries are **binding** and summarise what S3 MUST and MUST NOT do with its inputs:

1. **Exclusive reliance on `sealed_inputs_5A`**

   * S3 MUST NOT read datasets or configs not listed in `sealed_inputs_5A` for this `manifest_fingerprint`.

2. **S1 as authority for domain, class, and scale**

   * The S3 domain `(merchant, zone[, channel])` is derived only from `merchant_zone_profile_5A` and any explicit S3 policy filters.
   * `demand_class` and base scale come only from S1; S3 does not invent or recompute them.

3. **S2 as authority for grid and shapes**

   * Time-grid and shapes are taken exclusively from `shape_grid_definition_5A` and `class_zone_shape_5A`.
   * S3 MUST NOT:

     * alter the grid,
     * renormalise shapes for its own purposes,
     * construct alternative shape families.

4. **No Layer-1 fact access**

   * S3 MUST NOT read Layer-1 egress directly (e.g. `zone_alloc`, routing weights, civil time, site data).
   * Any information it needs must flow through S1/S2 or S3 policies.

5. **No out-of-band behaviour**

   * S3 MUST NOT change its inputs or behaviour based on:

     * environment variables,
     * CLI flags,
     * calendar date of execution,
       that are not reflected in:
     * `parameter_hash`,
     * `scenario_id`, and
     * policy/config artefacts listed in `sealed_inputs_5A`.

Within these boundaries, S3 sees exactly the world S0/S1/S2 define, and its role is strictly to compute `λ_base_local(m, zone, k)` as a deterministic function of those sealed inputs.

---

## 4. Outputs (datasets) & identity *(Binding)*

This section defines the **data products** of **5A.S3 — Baseline Merchant×Zone Weekly Intensities** and how they are identified in storage. All rules here are **binding**.

S3 outputs are **world-specific** baselines:

* They depend on the **world** (`manifest_fingerprint`) via S1,
* and on the **parameter pack + scenario** via S2 and 5A policies.

---

### 4.1 Overview of outputs

5A.S3 MUST produce one **required** modelling dataset, and MAY produce up to two **optional** convenience datasets:

1. **`merchant_zone_baseline_local_5A` *(required)***

   * Per `(merchant, zone[, channel], local_bucket)` **baseline local-time intensity** `lambda_local_base`.
   * This is the **primary output** S4 and 5B will consume.

2. **`class_zone_baseline_local_5A` *(optional)***

   * Per `(demand_class, zone[, channel], local_bucket)` **class-level baseline intensity** (i.e. average or aggregate across merchants).
   * Convenience / diagnostic only; MUST be derivable from `merchant_zone_baseline_local_5A`.

3. **`merchant_zone_baseline_utc_5A` *(optional)* **

   * A projection of local baselines into a UTC/horizon grid per `(merchant, zone, utc_bucket)` if you decide to pre-compute this in S3.
   * Entirely optional; S4 may choose to work from local baselines only.

No other S3 datasets are required. Any additional debugging surfaces MUST be clearly marked as diagnostic and MUST NOT be required by downstream segments.

---

### 4.2 `merchant_zone_baseline_local_5A` (required)

#### 4.2.1 Semantic role

`merchant_zone_baseline_local_5A` is the **core product** of S3.

For each in-scope `(merchant, zone[, channel])` and each local-week bucket `k` defined in `shape_grid_definition_5A`, it provides:

* `lambda_local_base(m, zone, k)` — the **baseline expected intensity** for that merchant×zone in that local-time bucket, before calendar effects and stochastic variation.

Semantically, depending on the S3 policy, this is either:

* *“expected number of arrivals in bucket k”* (if base scale is weekly expected count), or
* *“dimensionless baseline intensity”* (if base scale is a factor that later gets applied again).

The unit convention MUST be fixed in the S3 spec and baseline policy and is binding.

#### 4.2.2 Domain & cardinality

For a given triple `(parameter_hash, manifest_fingerprint, scenario_id)`:

* Let `D_S1` be the S1 in-scope domain:

  ```text
  D_S1 = { (merchant_id, legal_country_iso, tzid[, channel]) }
  ```

  after any S3 policy filters applied to `merchant_zone_profile_5A`.

* Let `GRID` be the S2 local-week grid:

  ```text
  bucket_index ∈ [0..T_week-1]
  ```

The domain of `merchant_zone_baseline_local_5A` MUST be:

```text
DOMAIN_S3 = {
  (merchant_id, legal_country_iso, tzid[, channel], bucket_index)
  | (merchant, zone[, channel]) ∈ D_S1
    and bucket_index ∈ GRID
}
```

This implies:

* For every `(merchant, zone[, channel]) ∈ D_S1` there MUST be **exactly T_week** rows in `merchant_zone_baseline_local_5A`.
* There MUST NOT be rows for `(merchant, zone[, channel])` outside `D_S1`.

#### 4.2.3 Identity & keys

**Partitioning**

`merchant_zone_baseline_local_5A` is **world + scenario scoped**:

* `partition_keys: ["fingerprint","scenario_id"]`

where:

* `fingerprint={manifest_fingerprint}`
* `scenario_id` is the scenario bound to this run (baseline/stress).

This keeps S3 outputs aligned with the world-specific S1 inputs, while allowing multiple scenarios per world if needed.

**Primary key**

Within a `(fingerprint, scenario_id)` partition, the primary key MUST be:

```yaml
primary_key:
  - manifest_fingerprint
  - merchant_id
  - legal_country_iso   # or zone_id if you adopt a combined zone key
  - tzid                # omitted if zone_id is used
  - bucket_index
```

If S3 also tracks channel as a dimension, add `channel` / `channel_group` to the PK.

**Embedded identity fields**

Each row MUST embed:

* `manifest_fingerprint` — non-null, equals the partition token `fingerprint`.
* `parameter_hash` — non-null, equals the run’s `parameter_hash` and S0’s value.
* `scenario_id` — non-null, equals the partition token.

Any mismatch between partition tokens and embedded values MUST be treated as invalid.

#### 4.2.4 Core columns (conceptual)

Minimum required fields (exact types fixed in §5):

* Identity:

  * `manifest_fingerprint`
  * `parameter_hash`
  * `scenario_id`
  * `merchant_id`
  * zone representation: `(legal_country_iso, tzid)` **or** `zone_id`
  * optional `channel` / `channel_group`

* Time key:

  * `bucket_index` — FK to `shape_grid_definition_5A` for this `(parameter_hash, scenario_id)`

* Baseline intensity:

  * `lambda_local_base` — numeric, non-null, MUST be ≥ 0.

* Optional metadata:

  * `weekly_volume_expected` or `scale_factor` echoed from S1 (for sanity and audit).
  * `s3_spec_version` — spec version for S3.
  * flags (e.g. `scale_source`, `baseline_clip_applied`).

Exact schema is defined in the next section; here the semantics are binding.

---

### 4.3 `class_zone_baseline_local_5A` (optional)

#### 4.3.1 Semantic role

If implemented, `class_zone_baseline_local_5A` is a **class-level aggregate**:

* It summarises `lambda_local_base` over merchants, per `(demand_class, zone[, channel], bucket_index)`.
* It can be used for diagnostics, visualisation, or coarse modelling where merchant-level detail is not required.

Typical semantics:

* `lambda_local_base_class(class, zone, k)` could be:

  * the **sum** of intensities across merchants in that class/zone, or
  * the **mean** / **median** intensity per merchant in that class/zone — the policy MUST specify which.

#### 4.3.2 Domain & identity

For a given `(parameter_hash, manifest_fingerprint, scenario_id)`:

* Domain is all `(demand_class, zone[, channel], bucket_index)` that appear in `merchant_zone_baseline_local_5A`, with `demand_class` taken from S1.

Partitioning:

* `partition_keys: ["fingerprint","scenario_id"]`

Primary key (if materialised):

* with explicit zone representation:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - demand_class
    - legal_country_iso
    - tzid
    - bucket_index
  ```

* or with `zone_id` if used.

`parameter_hash` MUST be embedded and constant within the `(fingerprint, scenario_id)` partition.

#### 4.3.3 Derivability constraint

All values in `class_zone_baseline_local_5A` MUST be **deterministically derivable** from:

* `merchant_zone_baseline_local_5A`, and
* a fixed aggregation policy (e.g. sum/mean).

No new fundamental information may appear in this dataset.

---

### 4.4 `merchant_zone_baseline_utc_5A` (optional)

#### 4.4.1 Semantic role

If the design elects to pre-compute UTC surfaces in S3, `merchant_zone_baseline_utc_5A` is:

* A projection of local-week baseline intensities into a **UTC-aligned time horizon**, e.g. per `(merchant, zone, utc_bucket)` for a scenario horizon.

This is optional: S4 might instead:

* take local baselines,
* apply calendar overlays, and
* map to UTC/horizon itself.

#### 4.4.2 Identity & domain

If implemented, for each `(parameter_hash, manifest_fingerprint, scenario_id)`:

* Domain: `(merchant_id, zone[, channel], utc_bucket_index)` over a declared UTC grid.

* Partitioning:

  * e.g. `partition_keys: ["fingerprint","scenario_id"]` or `[ "fingerprint", "scenario_id", "utc_day" ]` depending on horizon design.

* Primary key (illustrative):

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - merchant_id
    - legal_country_iso  # or zone_id
    - tzid               # omitted if zone_id is used
    - utc_bucket_index
  ```

Unit semantics (e.g. expected count per UTC bucket) MUST be consistent with:

* S3’s local-intensity units, and
* 2A’s civil-time mapping (`site_timezones` + tz timetable).

Because this dataset adds complexity and overlaps S4’s likely responsibilities, it SHOULD remain optional and only be implemented if you have a clear downstream consumer that needs it.

---

### 4.5 Relationship to upstream & downstream datasets

#### 4.5.1 Upstream references and foreign keys

`merchant_zone_baseline_local_5A` MUST:

* Have a foreign-key relationship to S1:

  ```text
  merchant_zone_baseline_local_5A.(manifest_fingerprint, merchant_id, legal_country_iso, tzid)
    → merchant_zone_profile_5A.(manifest_fingerprint, merchant_id, legal_country_iso, tzid)
  ```

* And to S2 grid:

  ```text
  merchant_zone_baseline_local_5A.(parameter_hash, scenario_id, bucket_index)
    → shape_grid_definition_5A.(parameter_hash, scenario_id, bucket_index)
  ```

* And indirectly, via `(demand_class, zone[, channel])`, to S2 shapes:

  * The class/zone used in S2 for this `(merchant, zone)` MUST have a matching shape in `class_zone_shape_5A`.

`class_zone_baseline_local_5A` and `merchant_zone_baseline_utc_5A` (if present) MUST have corresponding FKs back to `merchant_zone_baseline_local_5A`, the grid, and/or the S1/S2 surfaces as appropriate.

#### 4.5.2 Downstream obligations

Downstream states (S4, 5B, 6A):

* MUST treat `merchant_zone_baseline_local_5A` as the **baseline authority** for merchant×zone×local-week intensities.
* MUST NOT recompute `scale × shape` independently in a way that contradicts S3.
* MAY use `class_zone_baseline_local_5A` for diagnostics and aggregated modelling when a merchant-level view is unnecessary.
* MAY, if present and spec’d, consume `merchant_zone_baseline_utc_5A` instead of performing local→UTC projection themselves.

---

### 4.6 Control-plane vs modelling outputs

S3 produces **only modelling datasets**, not new control-plane artefacts:

* No new gate receipt or sealed-input inventory.
* No `_passed.flag` (segment-level PASS is owned by a later validation state).

Its outputs:

* are deterministic functions of S1/S2 + S3 policies under `(parameter_hash, manifest_fingerprint, scenario_id)`,
* are partitioned by `fingerprint` and `scenario_id` with `parameter_hash` embedded, and
* are immutable once written, except for idempotent re-runs that produce identical content.

Within this identity model, S3 provides a single, world-specific, parameter-pack-aware baseline intensity surface that anchors all later Layer-2 and Layer-3 behaviour.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

The S3 baselines inherit their contracts from the 5A schema pack/dictionary/registry. Datasets:

1. `merchant_zone_baseline_local_5A`
2. `class_zone_baseline_local_5A`
3. `merchant_zone_baseline_utc_5A` (optional UTC projection)

| Dataset | Schema anchor | Dictionary id | Registry key |
|---|---|---|---|
|`merchant_zone_baseline_local_5A`|`schemas.5A.yaml#/model/merchant_zone_baseline_local_5A`|`merchant_zone_baseline_local_5A`|`mlr.5A.model.merchant_zone_baseline_local`|
|`class_zone_baseline_local_5A`|`schemas.5A.yaml#/model/class_zone_baseline_local_5A`|`class_zone_baseline_local_5A`|`mlr.5A.model.class_zone_baseline_local`|
|`merchant_zone_baseline_utc_5A` (opt.)|`schemas.5A.yaml#/model/merchant_zone_baseline_utc_5A`|`merchant_zone_baseline_utc_5A`|`mlr.5A.model.merchant_zone_baseline_utc`|

Binding notes:

- Dictionary-defined partitioning (`fingerprint`/`scenario_id`) and PKs are mandatory; writer ordering ensures deterministic hashing.
- Schema pack controls all columns (local/UTC bucket indices, baselines, audits, provenance). Optional UTC output, when present, must be a deterministic projection of the local baseline using 2A tz law.
- Registry dependencies (S2 shapes, S1 profiles, sealed configs) define allowable inputs.


## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section specifies the **ordered, deterministic algorithm** for **5A.S3 — Baseline Merchant×Zone Weekly Intensities**. Implementations MUST follow these steps and invariants.

5A.S3 is **purely deterministic** and MUST NOT consume RNG.

---

### 6.1 High-level invariants

5A.S3 MUST satisfy:

1. **RNG-free**

   * MUST NOT call any RNG primitive.
   * MUST NOT emit any RNG events or modify RNG audit/trace logs.

2. **Catalogue-driven**

   * MUST discover all inputs via:

     * `s0_gate_receipt_5A`,
     * `sealed_inputs_5A`,
     * dataset dictionaries and artefact registries.
   * MUST NOT use hard-coded paths, directory scans, or network calls.

3. **Upstream-respecting**

   * MUST treat:

     * `merchant_zone_profile_5A` as the single authority for per-merchant×zone `demand_class` and base scale;
     * `shape_grid_definition_5A` as the single authority for local-week buckets;
     * `class_zone_shape_5A` as the single authority for unit-mass shapes.
   * MUST NOT reclassify, re-scale, or re-shape upstream surfaces.

4. **Domain completeness**

   * For each in-scope `(merchant, zone[, channel])` and each time bucket in the local week, S3 MUST produce exactly one `lambda_local_base` value in `merchant_zone_baseline_local_5A`.

5. **No partial outputs**

   * On failure, S3 MUST NOT commit partial S3 outputs in canonical locations.
   * On success, `merchant_zone_baseline_local_5A` (and any declared optional S3 outputs) MUST be present, schema-valid, and domain-complete.

---

### 6.2 Step 1 — Load gate, sealed inputs & validate S1/S2 readiness

**Goal:** Ensure the world, parameter pack, and upstream S1/S2 surfaces are valid for this run.

**Inputs:**

* `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id` (run context).
* `s0_gate_receipt_5A`, `sealed_inputs_5A` for this `manifest_fingerprint`.
* S1 output: `merchant_zone_profile_5A`.
* S2 outputs: `shape_grid_definition_5A`, `class_zone_shape_5A`.

**Procedure:**

1. Resolve `s0_gate_receipt_5A` and `sealed_inputs_5A` via the 5A dataset dictionary & registry using `fingerprint={manifest_fingerprint}`.

2. Validate S0 outputs:

   * `s0_gate_receipt_5A` validates against `#/validation/s0_gate_receipt_5A`.
   * `sealed_inputs_5A` validates against `#/validation/sealed_inputs_5A`.
   * `s0_gate_receipt_5A.parameter_hash == parameter_hash`.
   * All rows in `sealed_inputs_5A` for this fingerprint have:

     * `manifest_fingerprint == manifest_fingerprint`,
     * `parameter_hash == parameter_hash`.
   * Recompute `sealed_inputs_digest` from `sealed_inputs_5A` using the S0 hashing law and confirm equality with `s0_gate_receipt_5A.sealed_inputs_digest`.

3. Check upstream Layer-1 statuses:

   * From `s0_gate_receipt_5A.verified_upstream_segments`, require `status="PASS"` for each of `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.

4. Resolve S1 output:

   * From `sealed_inputs_5A`, locate the `merchant_zone_profile_5A` artefact (status `"REQUIRED"`, `read_scope="ROW_LEVEL"`).
   * Resolve path via dictionary (`fingerprint={manifest_fingerprint}`), then:

     * validate against `#/model/merchant_zone_profile_5A`,
     * verify `parameter_hash == parameter_hash`, `manifest_fingerprint == manifest_fingerprint`,
     * verify no duplicate `(merchant_id, legal_country_iso, tzid[, channel])`.

5. Resolve S2 grid & shapes:

   * From `sealed_inputs_5A`, locate `shape_grid_definition_5A` and `class_zone_shape_5A` (status `"REQUIRED"`).
   * Resolve paths via dictionary (`parameter_hash={parameter_hash}`, `scenario_id={scenario_id}`).
   * Validate:

     * `shape_grid_definition_5A` against `#/model/shape_grid_definition_5A`; check PK and contiguity of `bucket_index`.
     * `class_zone_shape_5A` against `#/model/class_zone_shape_5A`; ensure:

       * `parameter_hash == parameter_hash`, `scenario_id == scenario_id`,
       * PK uniqueness for each `(parameter_hash, scenario_id, demand_class, zone_representation[, channel], bucket_index)`,
       * `shape_value ≥ 0` and normalisation invariants have been met by S2 (optionally re-check for sanity).

6. Load any required S3 policy/config artefacts (e.g. `baseline_intensity_policy_5A`) identified in `sealed_inputs_5A`, validating them against their schemas.

**Invariants:**

* If any validation fails (S0, S1, or S2 surfaces or S3 policies), S3 MUST abort with a suitable error (e.g. `S3_GATE_OR_S2_INVALID` / `S3_REQUIRED_INPUT_MISSING`) and MUST NOT write outputs.
* If all checks pass, S3 proceeds.

---

### 6.3 Step 2 — Construct the S3 domain `D_S3` from S1

**Goal:** Determine exactly which `(merchant, zone[, channel])` pairs S3 must emit intensities for.

**Primary source:** `merchant_zone_profile_5A` (S1).

**Procedure:**

1. Read `merchant_zone_profile_5A` rows for `manifest_fingerprint={manifest_fingerprint}` and `parameter_hash={parameter_hash}`, projecting at least:

   * `merchant_id`,
   * zone representation: `(legal_country_iso, tzid)` or `zone_id`,
   * `demand_class`,
   * base scale fields (e.g. `weekly_volume_expected`, `scale_factor`),
   * optional `channel` / `channel_group` if present and relevant.

2. Apply S3 policy filters (if any):

   * For example, a policy may exclude:

     * merchants marked as “out-of-scope for baseline”,
     * zones with zero base scale, if that is policy, etc.

   These rules MUST be expressed in S3 config; S3 MUST NOT hard-code arbitrary filters.

3. Construct an in-memory set:

   ```text
   D_S3 = {
     (merchant_id, zone_representation[, channel]) 
     | row in merchant_zone_profile_5A after filters
   }
   ```

4. Validate:

   * There are no duplicate entries in `D_S3`.
   * `D_S3` is empty only if the policy explicitly allows an empty domain for this world; otherwise, an empty domain SHOULD be treated as a configuration signal and logged.

**Invariants:**

* `D_S3` is the **sole domain** for S3.
* No `(merchant, zone[, channel])` outside `D_S3` may appear in `merchant_zone_baseline_local_5A`.

---

### 6.4 Step 3 — Assemble S1 scale & class per `(merchant, zone)`

**Goal:** For each `(m,z[,ch])` in `D_S3`, build the input tuple `(class, base_scale)` S3 will combine with S2 shapes.

**Inputs:**

* Rows from `merchant_zone_profile_5A` (Step 2).
* `baseline_intensity_policy_5A` (if defined).

**Procedure:**

For each `(m,z[,ch]) ∈ D_S3`:

1. Extract `demand_class(m,z[,ch])` from S1.

2. Extract **base scale** according to policy:

   * If policy says “use weekly expected volume”:

     * read `weekly_volume_expected(m,z[,ch])`; enforce:

       * non-null, finite, and ≥ 0.
   * If policy says “use scale factor”:

     * read `scale_factor(m,z[,ch])`; enforce non-null, finite, and ≥ 0.
   * If policy uses a combination or derived base (e.g. log-linear transform of S1 fields), apply that deterministically.

3. If scale is missing or invalid and no policy fallback is defined, treat this as a configuration error (`S3_SCALE_JOIN_FAILED`).

4. Record for each domain element:

   ```text
   CLASS_SCALE[m,z[,ch]] = {
     demand_class: demand_class(m,z[,ch]),
     base_scale:   base_scale(m,z[,ch]),
     aux_flags:    any relevant S1 flags (e.g. high_variability_flag)
   }
   ```

**Invariants:**

* Every `(m,z[,ch]) ∈ D_S3` MUST have:

  * a well-defined `demand_class`, and
  * a valid, non-negative base scale.
* S3 MUST NOT compute new base scales from raw data; it only applies policy-defined transforms over S1 outputs.

---

### 6.5 Step 4 — Join S2 shapes per `(class, zone)` and validate coverage

**Goal:** Ensure every `(m,z[,ch])` in `D_S3` has a matching S2 unit-mass shape, and build a joinable shape index.

**Inputs:**

* `class_zone_shape_5A` from S2.
* `shape_grid_definition_5A` from S2.
* `CLASS_SCALE` map from Step 3.

**Procedure:**

1. Read `shape_grid_definition_5A` for `(parameter_hash, scenario_id)` and derive:

   * `T_week` = number of buckets (`|{bucket_index}|`).
   * a set `GRID = {bucket_index}` with expected contiguous range `[0..T_week-1]`.

2. Read `class_zone_shape_5A` for `(parameter_hash, scenario_id)`, projecting:

   * `demand_class`,
   * zone representation (consistent with S1 representation),
   * optional `channel` / `channel_group`,
   * `bucket_index`,
   * `shape_value`.

3. Build a map:

   ```text
   SHAPE[class, zone[,ch], k] = shape_value
   ```

   while validating:

   * For each `(class, zone[,ch])`, shape entries cover all `k ∈ GRID` exactly once.
   * Each `shape_value ≥ 0`.
   * Sum across `k` per `(class, zone[,ch])` ≈ 1 (if not already validated in S2; S3 may perform a lighter re-check).

4. For each `(m,z[,ch]) ∈ D_S3`:

   * Look up `class = CLASS_SCALE[m,z[,ch]].demand_class`.
   * Check that `(class, zone[,ch])` exists in `SHAPE`.
   * If it does not, treat this as `S3_SHAPE_JOIN_FAILED` (or `S3_DOMAIN_ALIGNMENT_FAILED` if many), and abort.

**Invariants:**

* For every `(m,z[,ch]) ∈ D_S3`, there MUST be a corresponding shape in `SHAPE` keyed by `(class(m,z[,ch]), z[,ch])`.
* S3 MUST NOT invent shapes or silently fall back to a flat shape; any fallback MUST be explicitly defined in S2 policy, not S3.

---

### 6.6 Step 5 — Compute baseline local intensities λ_base_local

**Goal:** Compute `lambda_local_base(m,z[,ch],k)` as `base_scale × shape_value`.

**Inputs:**

* Domain `D_S3`.
* `CLASS_SCALE[m,z[,ch]]`.
* `SHAPE[class,z[,ch],k]`.
* `GRID` (bucket indices).
* Optional `baseline_intensity_policy_5A` for unit semantics and clipping.

**Procedure:**

For each `(m,z[,ch]) ∈ D_S3`:

1. Retrieve:

   * `class = CLASS_SCALE[m,z[,ch]].demand_class`
   * `base_scale = CLASS_SCALE[m,z[,ch]].base_scale`

2. For each `bucket_index k ∈ GRID`:

   * Retrieve `shape = SHAPE[class,z[,ch],k]`.

   * Compute preliminary intensity:

     ```text
     λ = base_scale × shape
     ```

   * If policy defines clipping:

     * enforce `λ ≥ λ_min` and/or `λ ≤ λ_max` as per `baseline_intensity_policy_5A`.
     * Clipping MUST be deterministic and minimal; it MUST NOT violate non-negativity.

   * Enforce:

     * `λ` is finite (no NaN / ±Inf).
     * `λ ≥ 0`.

   * Store this value in an in-memory structure:

     ```text
     BASE_LOCAL[m,z[,ch],k] = λ
     ```

3. Weekly consistency check (unit semantics):

   * If base scale is defined as “expected arrivals per local week”, S3 SHOULD (or MUST, if spec says so) verify:

     ```text
     Σ_{k∈GRID} BASE_LOCAL[m,z[,ch],k] ≈ base_scale
     ```

     within a policy-defined tolerance.
   * If base scale is a dimensionless factor, the spec MUST define what—if anything—this weekly constraint should be; S3 MUST enforce that contract.

4. If any numeric checks fail (invalid λ, or sum outside allowed tolerance), S3 MUST treat the situation as `S3_INTENSITY_NUMERIC_INVALID` and abort without committing outputs.

**Invariants:**

* For each `(m,z[,ch],k)`, `BASE_LOCAL` is uniquely defined and ≥ 0.
* For each `(m,z[,ch])`, weekly sum semantics MUST match the agreed base-scale contract.

---

### 6.7 Step 6 — Construct output rows (local baselines and optional aggregates)

#### 6.7.1 Build `merchant_zone_baseline_local_5A` rows

**Goal:** Turn `BASE_LOCAL` into row-level data for storage.

For each `(m,z[,ch]) ∈ D_S3` and each `k ∈ GRID`:

1. Emit a row with fields:

   * Identity:

     * `manifest_fingerprint`
     * `parameter_hash`
     * `scenario_id`

   * Merchant & zone:

     * `merchant_id = m`
     * zone representation (as per S1/S2: `(legal_country_iso, tzid)` or `zone_id`)
     * optional `channel` / `channel_group` if used.

   * Time key:

     * `bucket_index = k`

   * Intensity:

     * `lambda_local_base = BASE_LOCAL[m,z[,ch],k]`

   * Metadata:

     * `s3_spec_version`
     * optionally `scale_source`, and echo of base scale (e.g. `weekly_volume_expected`, `scale_factor`).

2. Validate each row in-process against `#/model/merchant_zone_baseline_local_5A`.

3. Append to in-memory collection `LOCAL_ROWS`.

After processing all elements:

* Validate:

  * `LOCAL_ROWS` row count = `|D_S3| × |GRID|`.
  * PK uniqueness: no duplicate `(manifest_fingerprint, scenario_id, merchant_id, zone_representation[,channel], bucket_index)`.

#### 6.7.2 Build `class_zone_baseline_local_5A` rows (optional)

If you choose to materialise the class-level aggregate:

1. Group `LOCAL_ROWS` by `(manifest_fingerprint, scenario_id, demand_class, zone_representation[,channel], bucket_index)`, where `demand_class` is obtained by joining to S1 or echoing from cached `CLASS_SCALE`.

2. For each group, compute `lambda_local_base_class` according to an explicit aggregation rule (e.g. sum or mean across merchants).

3. Build rows with:

   * `manifest_fingerprint`, `parameter_hash`, `scenario_id`
   * `demand_class`, zone representation, optional `channel`
   * `bucket_index`, `lambda_local_base_class`
   * `s3_spec_version`

4. Validate these rows against `#/model/class_zone_baseline_local_5A` and collect into `CLASS_ROWS`.

Any such aggregation MUST be deterministic and a pure function of `LOCAL_ROWS` + policy; no new randomness or inputs may be used.

#### 6.7.3 Build `merchant_zone_baseline_utc_5A` rows (optional)

If you choose to compute UTC baselines:

1. Use:

   * `LOCAL_ROWS` (local intensities),
   * 2A civil-time surfaces (`site_timezones`, `tz_timetable_cache`) as sealed by S0,
   * a shared UTC-grid configuration for the scenario horizon (could be defined in Layer-2).

2. For each `(m,z[,ch],local_bucket)` and associated local time window, map to one or more UTC horizon buckets, distributing intensity as per deterministic mapping rules (e.g. exact time-window intersection).

3. Aggregate all contributions per `(m,z[,ch], utc_bucket)` to `lambda_utc_base`, enforcing non-negativity and unit consistency.

4. Build `UTC_ROWS` conforming to `#/model/merchant_zone_baseline_utc_5A` and verify PK uniqueness.

Mapping logic and UTC-grid details MUST be defined elsewhere; S3 only implements that deterministic mapping, with no RNG.

---

### 6.8 Step 7 — Atomic write & idempotency

**Goal:** Persist S3 outputs atomically and idempotently per `(manifest_fingerprint, scenario_id)`.

**Inputs:**

* `LOCAL_ROWS` (required).
* Optional `CLASS_ROWS`, `UTC_ROWS`.
* Dataset dictionary entries for S3 outputs.

**Procedure:**

1. **Resolve canonical paths**

   Using the dataset dictionary, compute canonical paths for:

   * `merchant_zone_baseline_local_5A` under:
     `fingerprint={manifest_fingerprint}/scenario_id={scenario_id}`.
   * `class_zone_baseline_local_5A` (if implemented).
   * `merchant_zone_baseline_utc_5A` (if implemented).

2. **Check for existing outputs**

   * If any S3 output already exists for this `(manifest_fingerprint, scenario_id)`:

     * Load existing datasets.
     * Canonically order both existing and candidate rows (e.g. by PK) and compare:

       * If identical under the agreed serialisation, S3 MAY log “idempotent re-run” and exit without writing.
       * If any difference is detected, S3 MUST fail with `S3_OUTPUT_CONFLICT` and MUST NOT overwrite existing data.

3. **Write to staging**

   * Write `LOCAL_ROWS` to staging:

     ```text
     data/layer2/5A/merchant_zone_baseline_local/
       fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/.staging/merchant_zone_baseline_local_5A.parquet
     ```

   * If implemented, write `CLASS_ROWS` and `UTC_ROWS` to analogous `.staging/` paths for their artefacts.

4. **Validate staged outputs (optional but recommended)**

   * Re-read staged files and:

     * validate schemas,
     * validate PK constraints,
     * optionally spot-check weekly sum vs base-scale invariants.

5. **Atomic commit**

   * Atomically move staged files to canonical paths:

     * `merchant_zone_baseline_local_5A` first,
     * then `class_zone_baseline_local_5A` (if any),
     * then `merchant_zone_baseline_utc_5A` (if any).

   * Ensure there is no state where class/UTC baselines are present without local baselines.

**Invariants:**

* On success:

  * All required S3 outputs exist and satisfy the identity/domain/numeric invariants in §§4, 7, 8.
  * Any optional outputs, if present, are consistent with `merchant_zone_baseline_local_5A`.

* On failure:

  * Canonical S3 paths MUST NOT be left with partially written or inconsistent outputs; any partials MUST remain under `.staging/` or be cleaned up.

Within this algorithm, 5A.S3 is a **pure “scale × shape” composer**: it deterministically combines S1 base scales with S2 unit-mass shapes over the S2 grid, enforced by S0’s sealed world, and emits a stable, world-specific baseline intensity surface for all downstream use.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how **identity** is represented for **5A.S3 — Baseline Merchant×Zone Weekly Intensities**, how its datasets are **partitioned and addressed**, and what the **rewrite rules** are. All rules here are **binding**.

S3 outputs are **world + parameter-pack + scenario scoped**:

* World: `manifest_fingerprint` (ties to S1 / Layer-1).
* Parameter pack: `parameter_hash`.
* Scenario: `scenario_id`.

They are **not** seed- or run-scoped.

---

### 7.1 Identity model

There are two layers of identity:

1. **Run identity** (execution context, ephemeral)

   * `parameter_hash` — active parameter pack (including S1/S2/S3 policies, scenario config).
   * `manifest_fingerprint` — closed-world manifest S0/S1 validated.
   * `scenario_id` — scenario under which S3 is computing baselines.
   * `run_id` — concrete execution of S3 for this triple.

   These belong to the *run*, not the persisted datasets.

2. **Dataset identity** (storage-level, persistent)

   * S3 outputs (`merchant_zone_baseline_local_5A`, plus optional S3 tables) are uniquely defined by the triple:

     ```text
     (manifest_fingerprint, parameter_hash, scenario_id)
     ```

   * For a fixed triple, there MUST be at most one canonical set of S3 outputs.

Binding rules:

* `run_id` MUST NOT appear as a partition key or in primary keys, and MUST NOT be stored as a column in S3 outputs.
* `manifest_fingerprint`, `parameter_hash`, and `scenario_id` MUST be embedded as columns in all S3 outputs and MUST match the partition tokens (where applicable).
* For any fixed `(manifest_fingerprint, parameter_hash, scenario_id)`, re-running S3 MUST either:

  * produce byte-identical outputs (idempotent), or
  * error with an output conflict (see §7.4).

---

### 7.2 Partition law & path contracts

#### 7.2.1 Partition keys

S3 outputs are **world+scenario partitioned**:

* `merchant_zone_baseline_local_5A`:

  * `partition_keys: ["fingerprint","scenario_id"]`

* `class_zone_baseline_local_5A` (if implemented):

  * `partition_keys: ["fingerprint","scenario_id"]`

* `merchant_zone_baseline_utc_5A` (if implemented):

  * `partition_keys: ["fingerprint","scenario_id"]`

    * (some designs MAY add an extra horizon partition like `utc_day`, but that MUST be encoded in the dictionary and then treated as binding.)

No S3 output may be partitioned by `parameter_hash`, `seed`, or `run_id`.

#### 7.2.2 Path templates

Paths MUST follow the templates declared in the dataset dictionary (already sketched in §5.5). For example:

* `merchant_zone_baseline_local_5A`:

  ```text
  data/layer2/5A/merchant_zone_baseline_local/
    fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_baseline_local_5A.parquet
  ```

* `class_zone_baseline_local_5A` (optional):

  ```text
  data/layer2/5A/class_zone_baseline_local/
    fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/class_zone_baseline_local_5A.parquet
  ```

* `merchant_zone_baseline_utc_5A` (optional):

  ```text
  data/layer2/5A/merchant_zone_baseline_utc/
    fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_baseline_utc_5A.parquet
  ```

These templates are binding once declared in the dictionary/registry.

#### 7.2.3 Path ↔ embed equality

For every row in any S3 dataset:

* Embedded `manifest_fingerprint` column:

  * MUST exist, be non-null, and equal the partition token `fingerprint={manifest_fingerprint}`.

* Embedded `scenario_id` column:

  * MUST exist, be non-null, and equal the partition token `scenario_id={scenario_id}`.

* Embedded `parameter_hash` column:

  * MUST exist, be non-null, and equal the S3 run’s `parameter_hash` and S0’s `parameter_hash`.

Any mismatch between:

* partition tokens and embedded fields, or
* embedded `parameter_hash` and S0’s `parameter_hash`

MUST be treated as a hard validation error for S3’s outputs.

---

### 7.3 Primary keys & logical ordering

#### 7.3.1 Primary keys

Primary keys (PKs) for S3 datasets are **binding**:

* **`merchant_zone_baseline_local_5A`**

  If zone is explicit `(legal_country_iso, tzid)`:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - merchant_id
    - legal_country_iso
    - tzid
    - bucket_index
  ```

  If zone is encoded as `zone_id`:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - merchant_id
    - zone_id
    - bucket_index
  ```

  If channel is part of the domain, `channel` / `channel_group` MUST be included in the PK.

* **`class_zone_baseline_local_5A`** (if implemented)

  With explicit zone:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - demand_class
    - legal_country_iso
    - tzid
    - bucket_index
  ```

  Or:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - demand_class
    - zone_id
    - bucket_index
  ```

* **`merchant_zone_baseline_utc_5A`** (if implemented)

  Example PK:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - merchant_id
    - legal_country_iso   # or zone_id
    - tzid
    - utc_bucket_index    # or (utc_date, utc_bucket_within_date)
  ```

In all cases:

* PK fields MUST be required and non-null.
* Duplicate PK tuples within a `(fingerprint, scenario_id)` partition MUST be treated as an S3 failure.

#### 7.3.2 Logical ordering

Physical ordering is not semantically significant, but S3 MUST impose a deterministic writer order to support:

* stable diffs,
* idempotency checking,
* reproducible testing.

Recommended ordering:

* `merchant_zone_baseline_local_5A`:

  * order by `(merchant_id, zone_representation[, channel], bucket_index)`.

* `class_zone_baseline_local_5A`:

  * order by `(demand_class, zone_representation[, channel], bucket_index)`.

* `merchant_zone_baseline_utc_5A`:

  * order by `(merchant_id, zone_representation[, channel], utc_bucket_index)`.

Consumers MUST NOT rely on ordering beyond what is implied by PK semantics; ordering is purely for stability and diagnostics.

---

### 7.4 Merge discipline & rewrite semantics

S3 is **single-writer, no-merge** per `(manifest_fingerprint, scenario_id)`.

Binding rules:

1. **No in-place merge or append**

   For a fixed `(manifest_fingerprint, scenario_id)`, S3 MUST NOT:

   * append to existing S3 outputs,
   * perform partial row-level updates, or
   * “merge” new baselines into existing files.

   S3 outputs are **atomic** products for that world+scenario.

2. **Idempotent re-runs allowed**

   When S3 is re-run for a `(manifest_fingerprint, parameter_hash, scenario_id)` with existing outputs:

   * It MUST recompute candidate outputs in-memory (or via staging),
   * Sort existing and candidate rows under the same ordering,
   * Compare them:

     * If they are identical under canonical serialisation, S3 MAY:

       * log an idempotent re-run, and
       * skip writing (no-op).

3. **Conflicting rewrites forbidden**

   If existing S3 outputs for a `(manifest_fingerprint, scenario_id)` differ in any way from recomputed outputs (different rows, intensities, or grid coverage), S3 MUST:

   * fail with a canonical `S3_OUTPUT_CONFLICT` (or equivalent), and
   * MUST NOT overwrite or merge the existing outputs.

Any legitimate change to baseline behaviour (e.g. new policies, changed S1/S2 surfaces) MUST be represented by:

* a new `parameter_hash` and/or `manifest_fingerprint`, and
* a fresh S0/S1/S2/S3 run, not by mutating outputs under the same identity.

4. **No cross-world or cross-scenario merging**

   S3 MUST NOT aggregate or merge data across different:

   * `manifest_fingerprint` values, or
   * `scenario_id` values.

Each `(manifest_fingerprint, scenario_id)` partition is self-contained.

---

### 7.5 Interaction with other identity dimensions

#### 7.5.1 `parameter_hash`

* `parameter_hash` MUST be embedded as a column in all S3 outputs.
* It MUST be constant within any `(manifest_fingerprint, scenario_id)` partition.
* It MUST equal the `parameter_hash` recorded in `s0_gate_receipt_5A` for that fingerprint.

`parameter_hash` is **not** a partition key for S3 datasets; it is a binding identity attribute used to tie the baselines back to the parameter pack.

#### 7.5.2 `seed` & `run_id`

* `seed` MUST NOT be used in any S3 outputs:

  * no partition keys,
  * no columns.
    S3 has no RNG and does not depend on a seed.

* `run_id` MUST NOT be surfaced in S3 datasets, only in logs/run-report.

Any use of `seed` or `run_id` in S3 schemas or path templates is a spec violation.

---

### 7.6 Cross-segment identity alignment

S3 outputs must align with S1 and S2 identities:

1. **Alignment with S1 (`merchant_zone_profile_5A`)**

   * For each `(manifest_fingerprint, scenario_id)` partition of `merchant_zone_baseline_local_5A`:

     * Every `(merchant_id, zone_representation[, channel])` appearing in the baseline MUST have a corresponding row in `merchant_zone_profile_5A` with the same `manifest_fingerprint` and `parameter_hash`.
     * Conversely, after S3’s domain filters, every in-scope `(merchant_id, zone_representation[, channel])` from S1 MUST have `T_week` baseline rows.

2. **Alignment with S2 (`shape_grid_definition_5A`, `class_zone_shape_5A`)**

   * For each `(parameter_hash, scenario_id)`:

     * Every `bucket_index` in `merchant_zone_baseline_local_5A` MUST exist in `shape_grid_definition_5A` for that `(parameter_hash, scenario_id)`.
     * For each `(merchant, zone[, channel])`, the `demand_class` from S1 + zone representation MUST map to a `(demand_class, zone[, channel])` combination in `class_zone_shape_5A`.

3. **Alignment with world & scenario identity**

   * For each S3 row:

     * `manifest_fingerprint` MUST match the world’s fingerprint;
     * `parameter_hash` MUST match the pack used by S1/S2;
     * `scenario_id` MUST match the scenario used by S2 shapes.

Any violation of these alignments MUST cause S3 to treat its outputs as invalid for that world+scenario.

---

Within these constraints, S3’s identity, partitions, ordering, and merge discipline are fully specified: for each world+parameter-pack+scenario triple, there is a single, immutable baseline intensity surface, unambiguously aligned with S1’s demand profiles and S2’s weekly shapes, and safe to consume downstream.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 5A.S3 — Baseline Merchant×Zone Weekly Intensities** is considered green for a given `(parameter_hash, manifest_fingerprint, scenario_id)` and the **hard preconditions** it imposes on downstream states. All rules here are **binding**.

---

### 8.1 Conditions for 5A.S3 to “PASS”

For a given triple `(parameter_hash, manifest_fingerprint, scenario_id)`, S3 is considered **successful** only if **all** of the following hold.

#### 8.1.1 S0 gate, sealed inputs & upstream status

1. **Valid S0 gate & sealed inputs**

   * `s0_gate_receipt_5A` and `sealed_inputs_5A` for `fingerprint={manifest_fingerprint}`:

     * exist and are discoverable via the catalogue,
     * conform to their schemas
       (`#/validation/s0_gate_receipt_5A`, `#/validation/sealed_inputs_5A`),
     * have `parameter_hash == parameter_hash`, and
     * have a recomputed `sealed_inputs_digest` that matches the receipt.

2. **Upstream Layer-1 segments are green**

   * In `s0_gate_receipt_5A.verified_upstream_segments`, each of
     `1A`, `1B`, `2A`, `2B`, `3A`, `3B` MUST have `status="PASS"`.

If any of these checks fail, S3 MUST NOT be treated as green irrespective of its own outputs.

---

#### 8.1.2 S1 & S2 surfaces are present and valid

3. **S1: merchant_zone_profile_5A**

   * `merchant_zone_profile_5A`:

     * exists for this `(manifest_fingerprint, parameter_hash)`,
     * validates against `#/model/merchant_zone_profile_5A`,
     * has `parameter_hash == parameter_hash`, `manifest_fingerprint == manifest_fingerprint`,
     * respects its primary key: no duplicate `(merchant_id, legal_country_iso, tzid[, channel])`.

4. **S2: shape_grid_definition_5A**

   * `shape_grid_definition_5A`:

     * exists for `(parameter_hash, scenario_id)`,
     * validates against `#/model/shape_grid_definition_5A`,
     * has `parameter_hash == parameter_hash`, `scenario_id == scenario_id`,
     * covers a contiguous `bucket_index` range `[0..T_week-1]` with no gaps or duplicates,
     * has consistent `bucket_duration_minutes`, `local_day_of_week`, and `local_minutes_since_midnight` per policy.

5. **S2: class_zone_shape_5A**

   * `class_zone_shape_5A`:

     * exists for `(parameter_hash, scenario_id)`,
     * validates against `#/model/class_zone_shape_5A`,
     * has `parameter_hash == parameter_hash`, `scenario_id == scenario_id`,
     * respects its PK across `(parameter_hash, scenario_id, demand_class, zone_representation[, channel], bucket_index)`,
     * has all `shape_value ≥ 0`, and S2’s own normalisation invariants hold (optionally re-checked by S3).

6. **S3 baseline policy (if required)**

   * Any artefact declared required for S3 (e.g. `baseline_intensity_policy_5A`) is:

     * present in `sealed_inputs_5A` with `status="REQUIRED"`,
     * schema-valid,
     * and usable with the current `parameter_hash`.

---

#### 8.1.3 Domain coverage & identity for merchant_zone_baseline_local_5A

7. **Dataset exists & schema-valid**

   * `merchant_zone_baseline_local_5A`:

     * exists in the canonical partition
       `fingerprint={manifest_fingerprint}/scenario_id={scenario_id}`,
     * conforms to `#/model/merchant_zone_baseline_local_5A`,
     * declares `partition_keys: ["fingerprint","scenario_id"]`,
     * declares the PK as per the spec (zone representation choice fixed in §5).

8. **Identity consistency**

   * For all rows:

     * `manifest_fingerprint` equals the partition token `fingerprint`,
     * `scenario_id` equals the partition token `scenario_id`,
     * `parameter_hash` equals the S0 `parameter_hash` and S1/S2 `parameter_hash`.

9. **Domain alignment with S1**

   Let `D_S3` be the S3 domain constructed from S1:

   ```text
   D_S3 = { (merchant_id, zone_representation[, channel]) } 
          derived from merchant_zone_profile_5A after S3 policy filters
   ```

   Let `D_baseline` be the set of `(merchant_id, zone_representation[, channel])` present in `merchant_zone_baseline_local_5A`.

   S3 MUST ensure:

   * `D_baseline == D_S3`
     (i.e. every in-scope merchant×zone has outputs, and no out-of-scope merchant×zone leaks in).

10. **Per-bucket coverage**

    * For each `(merchant, zone[, channel]) ∈ D_S3`, the set of `bucket_index` values appearing in `merchant_zone_baseline_local_5A` MUST equal the full grid `{0..T_week-1}` defined in `shape_grid_definition_5A` for `(parameter_hash, scenario_id)`.
    * No duplicates of `(merchant_id, zone_representation[, channel], bucket_index)` are allowed.

---

#### 8.1.4 Numeric correctness of λ_base_local

11. **Non-negativity and finiteness**

    * For every row in `merchant_zone_baseline_local_5A`:

      * `lambda_local_base` is finite (no NaN, no ±Inf),
      * `lambda_local_base ≥ 0`.

12. **Weekly sum vs base scale (if applicable)**

    If the baseline policy defines base scale as “expected arrivals per local week” (or similar), then for each `(merchant, zone[, channel]) ∈ D_S3`:

* Let:

  ```text
  base_scale(m,z[,ch]) = S1 base scale for that merchant×zone
  sum_local(m,z[,ch])  = Σ_{k∈GRID} lambda_local_base(m,z[,ch],k)
  ```

* S3 MUST enforce:

  ```text
  | sum_local(m,z[,ch]) - base_scale(m,z[,ch]) | ≤ ε
  ```

  with `ε` defined in a baseline validation policy.

* If the base scale semantics differ (e.g. `scale_factor`), S3 MUST enforce the corresponding contract defined in that policy (e.g. `sum_local` equals a fixed reference, or is dimensionless but bounded).

13. **Consistency with S2 shapes**

* For each `(merchant, zone[, channel])`:

  * The per-bucket pattern of `lambda_local_base` MUST be consistent with S2 shapes, i.e.:

    ```text
    λ_base_local(m,z[,ch],k) ∝ shape_value(demand_class(m,z[,ch]), z[,ch], k)
    ```

    for all k, up to the scaling defined by base_scale and any documented clipping.
  * S3 MUST NOT distort the pattern in a way that effectively defines a new shape.

---

#### 8.1.5 Optional outputs are consistent (if present)

14. **`class_zone_baseline_local_5A` (optional)**

If materialised:

* The dataset exists for `(manifest_fingerprint, scenario_id)` and:

  * validates against `#/model/class_zone_baseline_local_5A`,
  * respects its PK and partitioning.

* All its values are **derived deterministically** from `merchant_zone_baseline_local_5A` using a documented aggregation policy (e.g. sum or mean across merchants).

* There are no extra `(demand_class, zone[, channel], bucket_index)` combinations beyond those implied by S3 domain + S1 classes; any such extras must be treated as an error.

15. **`merchant_zone_baseline_utc_5A` (optional)**

If implemented:

* The dataset exists for `(manifest_fingerprint, scenario_id)` and:

  * validates against `#/model/merchant_zone_baseline_utc_5A`,
  * respects its PK and partitioning,
  * uses `utc_bucket_index` (or equivalent) consistent with the UTC grid definition.

* The values `lambda_utc_base` are deterministically obtained from `lambda_local_base` using 2A civil-time mappings and UTC grid definitions; unit semantics are consistent and non-negative.

---

#### 8.1.6 Atomicity & idempotence

16. **All-or-nothing outputs**

For a given `(manifest_fingerprint, scenario_id)`:

* Either:

  * `merchant_zone_baseline_local_5A` (and any optional S3 outputs) exist and meet all invariants above,
* Or:

  * no S3 outputs are treated as valid; partial/persisted, invalid files in canonical paths are not allowed.

17. **Consistency with previous runs**

* If S3 outputs already existed for this `(manifest_fingerprint, scenario_id)` before the run, recomputation MUST produce the **exact same content** under canonical ordering; otherwise S3 MUST fail with an output-conflict and MUST NOT overwrite.

---

### 8.2 Minimal content requirements

Even if structural checks pass, S3 MUST enforce the following **content minima**:

1. **Non-empty domain (unless policy explicitly allows)**

   * If S1’s in-scope domain `D_S3` (post-filter) is non-empty, `merchant_zone_baseline_local_5A` MUST contain at least one row.
   * An entirely empty baseline is acceptable only if:

     * the domain configured for 5A is genuinely empty for this world+scenario, and
     * this case is explicitly permitted by S3 policy and clearly logged.

2. **Baseline-policy coverage**

   * Every `(merchant, zone[, channel])` in `D_S3` MUST be covered by baseline policy rules:

     * no missing base scale,
     * no “unreachable” class/scale combination without fallback.

---

### 8.3 Gating obligations on downstream 5A states (S4) and other consumers

Any downstream state that uses baseline intensities (e.g. 5A.S4, 5B, 6A) MUST obey the following gates:

1. **Require S0, S1, S2, S3 to be valid**

   Before applying calendar overlays or generating arrivals, a downstream state MUST:

   * validate S0 gate and `sealed_inputs_5A`,
   * validate S1 output (`merchant_zone_profile_5A`),
   * validate S2 outputs (`shape_grid_definition_5A`, `class_zone_shape_5A`), and
   * validate S3 outputs (`merchant_zone_baseline_local_5A` and any optional S3 datasets) against this spec.

2. **Treat S3 as the baseline authority**

   * Downstream logic MUST treat `merchant_zone_baseline_local_5A` as the **single source of truth** for:

     * baseline λ(m, zone[, channel], local_bucket) prior to calendar overlays and randomness.

   * They MUST NOT:

     * recompute base scale × shape independently in a way that conflicts with S3’s values,
     * apply alternative baseline functions over S1/S2 that bypass S3.

3. **Respect S3’s domain**

   * If a downstream state expects to operate on some `(merchant, zone[, channel])` but there is no corresponding baseline in `merchant_zone_baseline_local_5A`, it MUST treat this as a configuration error, not silently assume zero or flat intensities.

4. **Optional outputs are convenience only**

   * `class_zone_baseline_local_5A` and `merchant_zone_baseline_utc_5A` MAY be used as convenience views, but:

     * MUST NOT be considered more authoritative than `merchant_zone_baseline_local_5A`,
     * MUST always be interpreted as derivatives of merchant-level baselines.

---

### 8.4 Gating obligations on 5A segment-level validation & other layers

The 5A segment-level validation state MUST:

* treat `merchant_zone_baseline_local_5A` as a **required input** for any `manifest_fingerprint` it validates, and
* verify S3’s acceptance conditions (schema, domain coverage, numeric invariants) as part of the 5A validation bundle, before writing `_passed.flag`.

Other layers (5B, 6A) MUST:

* require that `_passed.flag` (segment-level PASS) be verified for a given `manifest_fingerprint` **before** assuming S3’s baselines are fit for use.

---

### 8.5 When 5A.S3 MUST fail

5A.S3 MUST treat the state as **FAILED** for a `(parameter_hash, manifest_fingerprint, scenario_id)` and MUST NOT publish or modify canonical S3 outputs if any of the following occur:

* **Gate failures:**

  * `s0_gate_receipt_5A` / `sealed_inputs_5A` missing or inconsistent.
  * Any upstream segment 1A–3B is not `"PASS"`.
  * `merchant_zone_profile_5A` or S2 outputs missing or schema-invalid.

* **Required inputs/policies missing:**

  * Required S3 policy artefacts (e.g. `baseline_intensity_policy_5A`) missing or unusable.

* **Domain misalignment:**

  * `merchant_zone_baseline_local_5A` domain differs from S3’s in-scope domain from S1, or bucket coverage per merchant×zone is incomplete (`S3_DOMAIN_ALIGNMENT_FAILED`).

* **Scale or shape join failures:**

  * No base scale for some `(merchant, zone)` (`S3_SCALE_JOIN_FAILED`).
  * No S2 shape for some `demand_class/zone` needed by S3 (`S3_SHAPE_JOIN_FAILED`).

* **Numeric issues:**

  * Any `lambda_local_base` negative, NaN, or ±Inf.
  * Weekly sum vs base scale deviates beyond allowed tolerance (`S3_INTENSITY_NUMERIC_INVALID`).

* **Output conflicts:**

  * Existing S3 outputs for this world+scenario differ from recomputed ones (`S3_OUTPUT_CONFLICT`).

* **I/O errors or internal invariant violations:**

  * `S3_IO_READ_FAILED`, `S3_IO_WRITE_FAILED`, or `S3_INTERNAL_INVARIANT_VIOLATION`.

In all such cases:

* S3 MUST abort without writing or rewriting canonical outputs,
* MUST surface an appropriate canonical error code in run-report/logs, and
* S4/5B/6A MUST treat this world+scenario as lacking a valid baseline until S3 is fixed and re-run.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error codes** that **5A.S3 — Baseline Merchant×Zone Weekly Intensities** MAY emit, and the conditions under which they MUST be raised. These codes are **binding**: implementations MUST either use them directly or maintain a strict 1:1 mapping.

S3 errors are about **S3 itself** failing to produce a valid `merchant_zone_baseline_local_5A` (and optional aggregates) for a given `(parameter_hash, manifest_fingerprint, scenario_id)`. They are distinct from:

* upstream status flags recorded in `s0_gate_receipt_5A`, and
* S1/S2’s own error codes.

---

### 9.1 Error reporting contract

5A.S3 MUST surface failures through:

* the engine’s **run-report**, and
* structured logs / metrics.

Each failure record MUST include at least:

* `segment_id = "5A.S3"`
* `parameter_hash`
* `manifest_fingerprint`
* `scenario_id`
* `run_id`
* `error_code` — one of the codes below
* `severity` — `FATAL` for all S3 codes
* `message` — short human-readable summary
* `details` — optional structured context (e.g. `{"merchant_id": "...", "legal_country_iso": "...", "tzid": "...", "bucket_index": ...}`)

There is no dedicated “S3 error dataset”; these signals live in the run-report/logs.

---

### 9.2 Canonical error codes (summary)

| Code                              | Severity | Category                                |
| --------------------------------- | -------- | --------------------------------------- |
| `S3_GATE_OR_S2_INVALID`           | FATAL    | S0/S1/S2 gate & alignment               |
| `S3_UPSTREAM_NOT_PASS`            | FATAL    | Upstream Layer-1 not PASS               |
| `S3_REQUIRED_INPUT_MISSING`       | FATAL    | Required S1/S2 artefact missing         |
| `S3_REQUIRED_POLICY_MISSING`      | FATAL    | Required S3 baseline policy missing     |
| `S3_SCALE_JOIN_FAILED`            | FATAL    | Cannot obtain valid base scale          |
| `S3_SHAPE_JOIN_FAILED`            | FATAL    | Cannot find matching S2 shape           |
| `S3_DOMAIN_ALIGNMENT_FAILED`      | FATAL    | Domain mismatch (S1 vs S3 outputs)      |
| `S3_INTENSITY_NUMERIC_INVALID`    | FATAL    | Invalid λ (NaN/Inf/negative or bad sum) |
| `S3_OUTPUT_CONFLICT`              | FATAL    | Existing outputs differ from recomputed |
| `S3_IO_READ_FAILED`               | FATAL    | I/O read error                          |
| `S3_IO_WRITE_FAILED`              | FATAL    | I/O write/commit error                  |
| `S3_INTERNAL_INVARIANT_VIOLATION` | FATAL    | Internal “should never happen” state    |

All are **stop-the-world** for S3: if any occurs, S3 MUST NOT write or alter canonical outputs for that `(parameter_hash, manifest_fingerprint, scenario_id)`.

---

### 9.3 Code-by-code definitions

#### 9.3.1 `S3_GATE_OR_S2_INVALID` *(FATAL)*

**Trigger**

Raised when S3 cannot establish a valid S0/S1/S2 context for this run, for example:

* `s0_gate_receipt_5A` or `sealed_inputs_5A`:

  * missing for `fingerprint={manifest_fingerprint}`,
  * schema-invalid,
  * `parameter_hash` mismatch, or
  * recomputed `sealed_inputs_digest` ≠ recorded digest.

* `merchant_zone_profile_5A`:

  * missing,
  * schema-invalid,
  * `parameter_hash` / `manifest_fingerprint` mismatch,
  * PK violations (duplicate `(merchant_id, zone)`).

* `shape_grid_definition_5A` / `class_zone_shape_5A`:

  * missing for `(parameter_hash, scenario_id)`,
  * schema-invalid or PK/normalisation invariants clearly violated.

**Effect**

* S3 MUST abort in Step 1 (§6.2) and MUST NOT attempt to compute intensities.
* No S3 outputs MAY be written or modified.
* Resolution: fix S0/S1/S2 first, then re-run S3.

---

#### 9.3.2 `S3_UPSTREAM_NOT_PASS` *(FATAL)*

**Trigger**

Raised when S0 indicates that one or more Layer-1 segments are not green:

* Any of `1A`, `1B`, `2A`, `2B`, `3A`, `3B` has `status="FAIL"` or `status="MISSING"` in `s0_gate_receipt_5A.verified_upstream_segments`.

**Effect**

* S3 MUST NOT read upstream fact data, even if physically present.
* No S3 outputs MAY be written.
* Operator must resolve upstream issues, re-run those segments + S0, then re-run S3.

---

#### 9.3.3 `S3_REQUIRED_INPUT_MISSING` *(FATAL)*

**Trigger**

Raised when a **required data artefact** for S3 is absent from `sealed_inputs_5A` or cannot be resolved/used, for example:

* `merchant_zone_profile_5A` missing or not marked as `status="REQUIRED"` with `read_scope="ROW_LEVEL"`.
* `shape_grid_definition_5A` or `class_zone_shape_5A` missing from `sealed_inputs_5A` for the needed `(parameter_hash, scenario_id)`.

This is about S1/S2 **datasets**, not S3 policies.

**Effect**

* S3 MUST abort during input resolution (Step 1/2) and MUST NOT attempt to compute intensities.
* No S3 outputs may be created.
* Fix: ensure required datasets are published, catalogued, and sealed in `sealed_inputs_5A`.

---

#### 9.3.4 `S3_REQUIRED_POLICY_MISSING` *(FATAL)*

**Trigger**

Raised when a **required S3 baseline policy** is missing or unusable, e.g.:

* `baseline_intensity_policy_5A` is absent in `sealed_inputs_5A`, or
* present but schema-invalid, or
* has incompatible `read_scope` (e.g. `"METADATA_ONLY"` when contents must be read).

**Effect**

* S3 MUST abort before domain or intensity computation.
* No outputs MAY be written.
* Fix: deploy the required policy artefacts, update parameter pack / catalogue, and re-run.

---

#### 9.3.5 `S3_SCALE_JOIN_FAILED` *(FATAL)*

**Trigger**

Raised when S3 cannot obtain a valid base scale for at least one `(merchant, zone[, channel])` domain element from S1, for example:

* Base scale field designated by policy (e.g. `weekly_volume_expected` or `scale_factor`) is null, NaN, ±Inf, or negative, and policy does not define a fallback.
* Required auxiliary fields for base scale transformation are missing (e.g. fields needed by a log-linear formula), and no default is allowed.

Detected in Step 4 (§6.4).

**Effect**

* S3 MUST abort and MUST NOT commit any outputs.
* `error_details` SHOULD identify the offending `(merchant_id, zone[,channel])` and base scale field(s).
* Fix: adjust S1 outputs or S3 policy so every in-scope domain row has a valid base scale or a defined fallback.

---

#### 9.3.6 `S3_SHAPE_JOIN_FAILED` *(FATAL)*

**Trigger**

Raised when S3 cannot find a matching S2 shape for at least one domain element, for example:

* For some `(merchant, zone[, channel]) ∈ D_S3`, `demand_class(m,z[,ch])` exists in S1 but there is no corresponding `(demand_class, zone[,channel])` combination in `class_zone_shape_5A`.
* Zone representation in S1 cannot be reconciled with S2 zone keys (e.g. incompatible `(legal_country_iso, tzid)` vs `zone_id`), so S3 cannot join.

Detected in Step 5 (§6.5).

**Effect**

* S3 MUST abort and MUST NOT commit outputs.
* `error_details` SHOULD include `merchant_id`, `demand_class`, zone, and optional channel.
* Fix: align S1 class/zone domains with S2 shapes (policy/config corrections) and re-run.

---

#### 9.3.7 `S3_DOMAIN_ALIGNMENT_FAILED` *(FATAL)*

**Trigger**

Raised when the domain of `merchant_zone_baseline_local_5A` does not match the S3 domain derived from S1, for example:

* Missing rows:

  * For some `(merchant, zone[, channel]) ∈ D_S3`, S3 fails to emit all `T_week` buckets in the baseline output.

* Extra rows:

  * `merchant_zone_baseline_local_5A` contains rows for `(merchant, zone[, channel])` not present in S1’s in-scope domain (after policy filters).

* PK violations:

  * Duplicate rows for the same `(manifest_fingerprint, scenario_id, merchant_id, zone_representation[,channel], bucket_index)`.

Typically detected at the end of Step 6/7 (§6.6–§6.7) when validating domain coverage and PK uniqueness.

**Effect**

* S3 MUST treat the entire run as failed and MUST NOT consider outputs valid.
* Canonical paths SHOULD remain untouched (or partially written files removed or quarantined).
* Fix: correct S3’s domain construction or join logic so `merchant_zone_baseline_local_5A` becomes a 1:1 overlay of `(D_S3 × GRID)`.

---

#### 9.3.8 `S3_INTENSITY_NUMERIC_INVALID` *(FATAL)*

**Trigger**

Raised when baseline intensities are numerically invalid or violate unit contracts, for example:

* Any computed `lambda_local_base` is:

  * NaN, +Inf, -Inf, or
  * negative (after optional clipping rules).

* Weekly sum check fails:

  * For base-scale semantics like “expected arrivals per week”, there exists `(m,z[,ch])` such that:

    ```text
    | Σ_k lambda_local_base(m,z[,ch],k) - base_scale(m,z[,ch]) | > ε
    ```

    where ε is the policy-defined tolerance.

Detected in Step 6 (§6.6).

**Effect**

* S3 MUST abort and leave canonical outputs untouched.
* `error_details` SHOULD identify at least one failing `(merchant, zone[,channel])` and, if possible, the observed vs expected sums.
* Fix: adjust scale/shape policy parameters or numeric handling to restore non-negativity and sum constraints.

---

#### 9.3.9 `S3_OUTPUT_CONFLICT` *(FATAL)*

**Trigger**

Raised when S3 detects that canonical outputs already exist for `(manifest_fingerprint, scenario_id)` and differ from what the current run would produce, for example:

* Existing `merchant_zone_baseline_local_5A` rows differ in any value (intensities, keys) from recomputed `LOCAL_ROWS` under canonical ordering.
* Existing optional S3 outputs (`class_zone_baseline_local_5A`, `merchant_zone_baseline_utc_5A`) are inconsistent with recomputed ones.

Detected in Step 8 (§6.8) when comparing staging outputs with existing files.

**Effect**

* S3 MUST NOT overwrite existing outputs.
* S3 MUST abort with `S3_OUTPUT_CONFLICT`.
* This usually indicates:

  * S1/S2/policies changed without minting a new `parameter_hash` or `manifest_fingerprint`, or
  * previous S3 run produced inconsistent results.

Resolution is to:

* update identity (new parameter pack and/or manifest), and
* rerun S0/S1/S2/S3 under the new identity.

---

#### 9.3.10 `S3_IO_READ_FAILED` *(FATAL)*

**Trigger**

Raised when S3 encounters I/O or storage failures while reading **required** inputs, e.g.:

* read errors or permission issues for:

  * `s0_gate_receipt_5A` / `sealed_inputs_5A`,
  * `merchant_zone_profile_5A`,
  * S2 outputs,
  * required S3 policies/configs.

This is for **technical I/O problems**, not logical absence (which is `S3_REQUIRED_INPUT_MISSING` / `S3_REQUIRED_POLICY_MISSING`).

**Effect**

* S3 MUST abort and MUST NOT compute or write outputs.
* Operator must resolve storage/network/permissions and re-run.

---

#### 9.3.11 `S3_IO_WRITE_FAILED` *(FATAL)*

**Trigger**

Raised when S3 fails while writing or committing its outputs, e.g.:

* cannot write staging files due to capacity/permissions,
* failure during atomic move from `.staging/` to canonical paths.

**Effect**

* S3 MUST treat the run as failed and MUST NOT leave partially written data in canonical locations.
* Staging artefacts MUST remain clearly non-canonical (e.g. in `.staging/`) or be cleaned up.
* Operator must fix infrastructure and re-run S3.

---

#### 9.3.12 `S3_INTERNAL_INVARIANT_VIOLATION` *(FATAL)*

**Trigger**

Catch-all for impossible or internal-error states that cannot be represented by a more specific code, for example:

* Internal maps or sets show duplicates after explicit de-duplication.
* Counts expected to match (`|D_S3| × T_week`) do not match `LOCAL_ROWS` cardinality despite no earlier error.
* Control flow hits “unreachable” branches in the S3 implementation.

**Effect**

* S3 MUST abort, treat outputs as invalid, and MUST NOT write or alter canonical data.
* `error_details` SHOULD capture which invariant failed and relevant context.
* This usually indicates a bug in implementation or deployment, not in user data or policy.

---

### 9.4 Relationship to upstream statuses

To avoid confusion:

* **Upstream statuses** (`"PASS" / "FAIL" / "MISSING"`) for 1A–3B are recorded in `s0_gate_receipt_5A.verified_upstream_segments`; they are *inputs* to S3.
* `S3_UPSTREAM_NOT_PASS` is raised **only** when those statuses indicate that Layer-1 is not green for this world.

S3 MUST NOT:

* ignore upstream `"FAIL"`/`"MISSING"` statuses and attempt to continue;
* downgrade those issues into lower-severity warnings.

Downstream states (S4, 5B, 6A) MUST:

* interpret S3’s canonical error codes as authoritative reasons why baseline intensities are missing or invalid for a given world+scenario, and
* refrain from attempting to reconstruct `λ_base` themselves when S3 has failed.

Within this framework, every S3 failure mode has a clear, named error code, well-defined triggers, and a clear operator action, ensuring that baselines are either trustworthy or clearly marked as unusable.

---

## 10. Observability & run-report integration *(Binding)*

This section defines how **5A.S3 — Baseline Merchant×Zone Weekly Intensities** MUST report its activity into the engine’s **run-report**, logging, and metrics systems. These requirements are **binding**.

S3 is deterministic and works at the **merchant×zone×local-bucket** level; observability MUST make it easy to see:

* *whether* baselines were produced,
* *for which world/pack/scenario*, and
* *whether λ values look sane*,

without dumping rows or exposing sensitive detail.

---

### 10.1 Objectives

Observability for 5A.S3 MUST allow operators and downstream components to answer:

1. **Did S3 run for this world + parameter pack + scenario?**
   For `(parameter_hash, manifest_fingerprint, scenario_id, run_id)`:

   * Did S3 start?
   * Did it succeed or fail?

2. **If S3 failed, why?**

   * Which canonical error code (§9)?
   * Was it S0/S1/S2 gating, missing inputs, shape/scale join problems, domain mismatch, or numeric issues?

3. **If S3 succeeded, what did it produce?**

   * How many merchants, zones, and buckets were involved?
   * What are high-level stats of `lambda_local_base` (min/median/p95/max, weekly-sum error versus base scale)?
   * Which policies and S1/S2 specs were in force?

All **without** logging per-merchant time series.

---

### 10.2 Run-report entries

For **every invocation** of 5A.S3, the engine’s run-report MUST contain a structured entry with at least:

* `segment_id = "5A.S3"`
* `parameter_hash`
* `manifest_fingerprint`
* `scenario_id`
* `run_id`
* `state_status ∈ {"STARTED","SUCCESS","FAILED"}`
* `start_utc`, `end_utc` (timestamps, UTC)
* `duration_ms`

On **SUCCESS**, the S3 run-report entry MUST additionally include:

* **Domain summary**

  * `s3_domain_merchants` — number of distinct `merchant_id` in `merchant_zone_baseline_local_5A`.
  * `s3_domain_merchant_zones` — number of distinct `(merchant_id, zone_representation[,channel])`.
  * `s3_domain_buckets_per_week` — number of buckets per week `T_week` from S2.
  * `s3_domain_rows_local` — total number of rows in `merchant_zone_baseline_local_5A` (should be `s3_domain_merchant_zones × s3_domain_buckets_per_week`).

* **Lambda statistics (local)**

  Over all `lambda_local_base` values in `merchant_zone_baseline_local_5A`:

  * `lambda_local_base_min`
  * `lambda_local_base_median`
  * `lambda_local_base_p95`
  * `lambda_local_base_max`

* **Weekly sum vs base-scale stats**

  If the baseline policy defines a weekly-sum contract:

  * `weekly_sum_relative_error_max` — maximum relative deviation `|sum_local - base_scale| / max(base_scale, ε)` across all `(merchant, zone[,channel])`.
  * `weekly_sum_relative_error_p95` — 95th percentile of that relative error.
  * `weekly_sum_error_violations_count` — count of merchant×zone where error > configured tolerance (if any).

* **Policy and spec metadata**

  * `s1_spec_version` (as observed in S1 output, if available).
  * `s2_spec_version` (as observed in S2 shapes, if available).
  * `s3_spec_version` (current S3 spec).
  * `baseline_intensity_policy_id` / version (if such policy is used).

On **FAILED**, the run-report entry MUST include:

* `error_code` — one of S3’s canonical error codes (§9).
* `error_message` — concise explanation.
* `error_details` — optional structured object (e.g. offending merchant/zone/bucket indices; class/zones for shape join failures), keeping detail minimal but actionable.

The run-report MUST be treated as the **primary source** for S3’s outcome; logs/metrics support deeper diagnosis.

---

### 10.3 Structured logging

5A.S3 MUST emit **structured logs** (e.g. JSON lines) keyed by `segment_id="5A.S3"` and `run_id`. Each log record MUST include:

* `parameter_hash`
* `manifest_fingerprint`
* `scenario_id`
* `run_id`

At minimum, S3 MUST log the following events:

1. **State start**

   * Level: `INFO`
   * Fields:

     * `event = "state_start"`
     * `segment_id = "5A.S3"`
     * `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
     * optional: environment metadata (`env`, `ci_build_id`, etc.)

2. **Inputs resolved**

   * After S0/S1/S2 validation and input resolution succeed.
   * Level: `INFO`
   * Fields:

     * `event = "inputs_resolved"`
     * `s1_present = true/false`, `s2_present = true/false`
     * `s1_spec_version` (if present in S1 output),
     * `s2_spec_version` (if present in S2 shapes),
     * `baseline_intensity_policy_id` / version (if used).

3. **Domain summary**

   * After constructing `D_S3`.
   * Level: `INFO`
   * Fields:

     * `event = "domain_built"`
     * `s3_domain_merchants`
     * `s3_domain_merchant_zones`
     * `s3_domain_buckets_per_week` (from S2 grid)
     * optional counts by channel or other groupings.

4. **Intensity summary**

   * After computing `lambda_local_base` and before writing outputs.
   * Level: `INFO`
   * Fields:

     * `event = "intensity_summary"`
     * `lambda_local_base_min`, `lambda_local_base_median`, `lambda_local_base_p95`, `lambda_local_base_max`
     * `weekly_sum_relative_error_max` and `weekly_sum_relative_error_p95` (if weekly-sum contract is enforced)
     * `weekly_sum_error_violations_count` (if tracked).

5. **State success**

   * Level: `INFO`
   * Fields:

     * `event = "state_success"`
     * `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
     * `s3_domain_merchant_zones`
     * `s3_domain_rows_local`
     * `duration_ms`

6. **State failure**

   * Level: `ERROR`
   * Fields:

     * `event = "state_failure"`
     * `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
     * `error_code`
     * `error_message`
     * `error_details` (e.g. `{"merchant_id": "...", "legal_country_iso": "...", "tzid": "...", "bucket_index": ...}` where safe and necessary).

**Prohibited logging:**

* S3 MUST NOT log:

  * complete λ vectors for individual merchants/zones,
  * entire rows from `merchant_zone_baseline_local_5A`, `merchant_zone_profile_5A`, or S2 shapes,
  * raw policy JSONs or other large blobs beyond minimal identifiers/versions.

Only **aggregate** information and minimal error context are allowed.

---

### 10.4 Metrics

5A.S3 MUST emit a minimal set of metrics for monitoring, with semantics as follows (names are illustrative):

1. **Run counters**

   * `fraudengine_5A_s3_runs_total{status="success"|"failure"}`
   * `fraudengine_5A_s3_errors_total{error_code="S3_SCALE_JOIN_FAILED"|...}`

2. **Latency**

   * `fraudengine_5A_s3_duration_ms` — histogram/summary of S3 runtime per `(parameter_hash, manifest_fingerprint, scenario_id)`.

3. **Domain size**

   * `fraudengine_5A_s3_domain_merchants` — gauge per run (#distinct merchants).
   * `fraudengine_5A_s3_domain_merchant_zones` — gauge per run (#merchant×zone[×channel]).
   * `fraudengine_5A_s3_buckets_per_week` — gauge per run (`T_week`).

4. **Lambda quality**

   * `fraudengine_5A_s3_lambda_min` / `lambda_max` — per-run min/max of `lambda_local_base`.
   * `fraudengine_5A_s3_weekly_sum_relative_error_max` — per-run maximum relative deviation of weekly sums vs base scales (if applicable).
   * `fraudengine_5A_s3_weekly_sum_error_violations` — per-run count of domain rows that exceed tolerance (if tracked).

Metric label cardinality MUST be kept under control:

* **NO** `merchant_id`, `zone_id`, or `demand_class` as metric labels.
* Identifiers like `parameter_hash`, `scenario_id`, and environment may be used as labels, if permitted by infra; country/zone labels are generally discouraged unless governance allows.

---

### 10.5 Correlation & traceability

To ensure cross-state traceability, S3 MUST:

* include the following in all run-report entries and logs:

  * `segment_id = "5A.S3"`
  * `parameter_hash`
  * `manifest_fingerprint`
  * `scenario_id`
  * `run_id`

* If the engine supports distributed tracing:

  * create/join a span for `"5A.S3"`;
  * annotate the span with `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`.

This allows operators to trace a run end-to-end, e.g.:

> 5A.S0 (gate) → 5A.S1 (class/scale) → 5A.S2 (shapes) → **5A.S3 (baseline λ)** → 5A.S4 / 5B.

---

### 10.6 Integration with 5A validation & dashboards

The **5A segment-level validation** state MUST:

* treat `merchant_zone_baseline_local_5A` (and any implemented optional S3 outputs) as **required inputs** when validating a `manifest_fingerprint`,
* perform its own structural and numeric checks (PKs, domain coverage, weekly-sum invariants),
* include summary stats (e.g. domain size, λ stats, weekly sum error distributions) in the 5A validation bundle, and
* use S3’s run-report/logs as additional evidence when building validation reports or dashboards.

Operational dashboards SHOULD be able to show, for each `(parameter_hash, manifest_fingerprint, scenario_id)`:

* whether S3 has run, and if so, with what status;
* how large the baseline domain is (merchants, zones, buckets);
* basic health indicators of λ (range, weekly-sum error);
* recent S3 failure codes and frequencies.

Downstream states (5A.S4, 5B, 6A) MUST NOT rely on logs/metrics alone as gates; they MUST continue to use:

* S0/S1/S2/S3 **data-level gates** (presence/validity of S3 datasets, plus later `_passed.flag`),

and treat observability signals as **diagnostic** rather than authoritative for correctness.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on the performance profile of **5A.S3 — Baseline Merchant×Zone Weekly Intensities** and how to scale it sensibly. It explains what grows with data size and where to be careful.

---

### 11.1 Performance summary

S3 is the first **“heavy-ish”** Layer-2 step:

* It runs at **merchant×zone×bucket** granularity.
* It does:

  * one pass over S1 (`merchant_zone_profile_5A`) to build `D_S3`,
  * one join to S2 shapes over the local-week grid,
  * a scalar multiply `base_scale × shape_value` per `(merchant, zone, bucket)`.

It is:

* more expensive than S2 (which is class×zone×bucket),
* still cheaper than any event-level or arrival-level work,
* essentially linear in:

> `#merchant×zone in S1` × `#buckets in the local week`.

---

### 11.2 Workload characteristics

Let:

* `M` = number of merchants in scope for 5A,
* `Z̄` = average number of zones per merchant (from 3A/S1),
* `N_mz = M × Z̄` = number of `(merchant, zone[, channel])` pairs in S3’s domain after policy filters,
* `T_week` = number of buckets per local week (from S2’s grid).

Then:

* Input sizes (per `(parameter_hash, manifest_fingerprint, scenario_id)`):

  * `merchant_zone_profile_5A`: O(`#merchant×zone`) rows.
  * `shape_grid_definition_5A`: `T_week` rows.
  * `class_zone_shape_5A`: `N_cz × T_week` rows, where `N_cz` is the number of `(demand_class, zone[, channel])` combinations.

* Output sizes:

  * `merchant_zone_baseline_local_5A`: `N_mz × T_week` rows (this is the main cost).
  * Optional `class_zone_baseline_local_5A`: O(`N_cz × T_week`).
  * Optional `merchant_zone_baseline_utc_5A`: complexity depends on horizon and mapping, but same order as local in rows.

In most realistic designs, `N_cz` is significantly smaller than `N_mz` (many merchants share the same class/zone templates).

---

### 11.3 Algorithmic complexity

For a single `(parameter_hash, manifest_fingerprint, scenario_id)`:

* **Input validation & resolution**:

  * S0/S1/S2 checks + policy loads: O(1) or O(#artefacts) — negligible compared to domain size.

* **S3 domain construction** (`D_S3`):

  * one scan of `merchant_zone_profile_5A`, projecting and de-duplicating `(merchant, zone[, channel])`.
  * Complexity: O(`#merchant×zone`) ~ O(`N_mz`).

* **Class/scale assembly**:

  * lookups into per-merchant data from S1 (e.g. via in-memory maps) — O(`N_mz`).

* **Shape join**:

  * reading shapes (`class_zone_shape_5A`), building `SHAPE[class, zone[,ch], k]`.
  * Complexity: O(`N_cz × T_week`) to load, then O(`N_mz × T_week`) to join by `(class,zone[,ch])`.

* **Intensity computation**:

  * for each `(m,z[,ch],k)`:

    * one multiplication + a couple of checks.
  * Complexity: O(`N_mz × T_week`).

Overall:

> **Time complexity** ≈ O(`#merchant×zone` + `N_cz × T_week` + `N_mz × T_week`)
> dominated by **`N_mz × T_week`** in practice.

Space:

* O(`N_mz × T_week`) if you materialise all `BASE_LOCAL` in memory,
* or less if you stream in chunks (see below).

---

### 11.4 I/O profile

**Reads**

* `merchant_zone_profile_5A`:

  * one scan of O(`#merchant×zone`) rows; can be streamed.
* `shape_grid_definition_5A`:

  * tiny (`T_week` rows).
* `class_zone_shape_5A`:

  * O(`N_cz × T_week`) rows; usually manageable and smaller than S3 output.
* S3 policies/configs:

  * a handful of small JSON/YAML/Parquet configs.

**Writes**

* `merchant_zone_baseline_local_5A`:

  * single Parquet file for `(fingerprint, scenario_id)` of size O(`N_mz × T_week`) rows.
* Optional S3 outputs:

  * additional single files of similar or smaller magnitude.

Typical bottlenecks:

* Very large merchant×zone domains (`N_mz`) and fine-grained grids (`T_week` large) will stress both CPU and I/O, but remain linear.

---

### 11.5 Parallelisation & scaling strategy

S3 parallelises naturally across the **merchant×zone domain** and over buckets:

1. **Grid & shape setup** (S2 outputs):

   * `shape_grid_definition_5A` and `class_zone_shape_5A` can be loaded once and broadcast to workers (or partitioned by class/zone).

2. **Domain partitioning:**

   * Partition `D_S3` across workers by:

     * `merchant_id` hash, or
     * `(merchant_id, zone)` stripes.

   * Each worker receives:

     * its subset of `(merchant, zone[,channel])`,
     * read-only access to `CLASS_SCALE` data,
     * read-only access to `SHAPE[class,zone[,ch],k]` and `GRID`.

3. **Per-partition processing:**

   * Each worker:

     * builds intensities `λ_base_local` for its domain fragment over all `bucket_index`,
     * writes to a **staging file** with deterministic ordering.

4. **Merge:**

   * Combine per-partition outputs into:

     * a single `merchant_zone_baseline_local_5A` file, or
     * a small number of files, still obeying the partition/PK rules.

S3 does **not** require extra partitioning in the storage layout; the spec prefers a simple `fingerprint + scenario_id` partition. Scaling is achieved via compute parallelism and internal chunking, not via fragmented on-disk partitions.

---

### 11.6 Memory & streaming considerations

For moderate `N_mz × T_week`:

* You can hold all `BASE_LOCAL` (or equivalent `LOCAL_ROWS`) in memory:

  * simple to implement,
  * easy to validate cardinality and PKs before writing.

For large `N_mz × T_week`, a **chunked/streaming approach** is recommended:

* Process `D_S3` in chunks (e.g. batches of merchants):

  * load a chunk of merchants × zones,
  * compute class/scale + λ’s over the grid,
  * write chunk rows to a staging file in a local sorted order.

* After all chunks:

  * merge sorted chunk files into a final file (or small set) in deterministic PK order.

The spec doesn’t mandate how many files you produce internally, only that:

* externally, the dataset identity and PK/partition rules are respected, and
* the final view is logically a single `(fingerprint, scenario_id)` slice.

---

### 11.7 Failure, retry & backoff

Because S3 is deterministic given:

* S1/S2 outputs,
* S3 policies, and
* `(parameter_hash, manifest_fingerprint, scenario_id)`

it is safe to **retry** in some cases:

* **Transient infra failures** (`S3_IO_READ_FAILED`, `S3_IO_WRITE_FAILED`):

  * May be retried after resolving infra issues, as long as canonical outputs have not been partially overwritten.

* **Deterministic config/data failures** (`S3_REQUIRED_INPUT_MISSING`, `S3_REQUIRED_POLICY_MISSING`, `S3_SCALE_JOIN_FAILED`, `S3_SHAPE_JOIN_FAILED`, `S3_DOMAIN_ALIGNMENT_FAILED`, `S3_INTENSITY_NUMERIC_INVALID`):

  * Retrying without changing inputs/policies will fail again.
  * Orchestration SHOULD stop auto-retrying and surface these as configuration or data quality problems that require human or pipeline fixes.

* **Output conflicts** (`S3_OUTPUT_CONFLICT`):

  * Indicates that S1/S2 outputs or S3 policies changed without minting a new `parameter_hash` or `manifest_fingerprint`.
  * Proper fix:

    * update identity (new parameter pack and/or new manifest fingerprint),
    * re-run S0/S1/S2/S3 under the new identity, and
    * leave old baselines as immutable artefacts for the old world/pack.

---

### 11.8 Suggested SLOs (non-binding)

Actual targets depend on hardware and domain size; indicative (non-binding) numbers for a “medium” world:

* Assume:

  * `N_mz` up to ~1–5 million merchant×zone pairs,
  * `T_week` ≤ ~1 000 buckets (e.g. 7×24=168 hours or 7×96=672 15-min buckets).

Then:

* **Latency per `(parameter_hash, manifest_fingerprint, scenario_id)` run:**

  * p50: on the order of tens of seconds to a couple of minutes.
  * p95: under a few minutes with reasonable parallelism.

* **Error rates:**

  * `S3_IO_*` errors: rare, infra-driven.
  * Scale/shape/domain/numeric errors: treated as configuration or upstream data issues, not normal runtime noise.

The key is that S3 is **predictably linear** in `N_mz × T_week` and easily parallelisable; it shouldn’t become the major bottleneck in a well-sized deployment, especially compared to arrival-level segments.

---

## 12. Change control & compatibility *(Binding)*

This section defines how **5A.S3 — Baseline Merchant×Zone Weekly Intensities** and its contracts may evolve over time, and what compatibility guarantees MUST hold. All rules here are **binding**.

Goals:

* No silent breaking changes to the **meaning or structure** of baseline λ.
* Clear separation between:

  * **spec changes** (what S3 outputs look like / mean), and
  * **policy / parameter-pack changes** (what the numbers are for a given world).
* Predictable behaviour for downstream segments (5A.S4, 5B, 6A).

---

### 12.1 Scope of change control

Change control for 5A.S3 covers:

1. **Row schemas & shapes**

   * `schemas.5A.yaml#/model/merchant_zone_baseline_local_5A`
   * `schemas.5A.yaml#/model/class_zone_baseline_local_5A` *(if implemented)*
   * `schemas.5A.yaml#/model/merchant_zone_baseline_utc_5A` *(if implemented)*

2. **Catalogue contracts**

   * `dataset_dictionary.layer2.5A.yaml` entries for:

     * `merchant_zone_baseline_local_5A`
     * `class_zone_baseline_local_5A` *(optional)*
     * `merchant_zone_baseline_utc_5A` *(optional)*
   * Corresponding `artefact_registry_5A.yaml` entries.

3. **Algorithm & semantics**

   * The deterministic algorithm in §6 (domain construction, joins to S1/S2, λ computation).
   * Identity & partition rules in §7.
   * Acceptance & gating rules in §8.
   * Failure modes & error codes in §9.

Changes to **S1/S2** or **S3 policies** (e.g. `baseline_intensity_policy_5A`) are governed separately, but they feed into S3 via `parameter_hash` and the sealed inputs.

---

### 12.2 S3 spec version field

To support evolution, S3 MUST expose a **spec version**:

* `s3_spec_version` — string, e.g. `"1.0.0"`.

Binding requirements:

* `s3_spec_version` MUST be present as a **required, non-null field** in `merchant_zone_baseline_local_5A`.
* It MAY also appear in `class_zone_baseline_local_5A` and `merchant_zone_baseline_utc_5A` (recommended), but the **baseline local** table is the primary anchor.

The schema anchor `#/model/merchant_zone_baseline_local_5A` MUST define:

* `s3_spec_version`:

  * type: string,
  * non-nullable.

#### 12.2.1 Versioning scheme

`s3_spec_version` MUST follow a semantic-style versioning scheme:

* `MAJOR.MINOR.PATCH`

Interpretation:

* **MAJOR** — incremented for **backwards-incompatible** changes (see §12.4).
* **MINOR** — incremented for **backwards-compatible** enhancements (see §12.3).
* **PATCH** — incremented for bug fixes / clarifications that do not change schemas or observable semantics.

Downstream consumers (5A.S4, 5B, 6A) MUST:

* read and interpret `s3_spec_version`,
* treat a defined set of `MAJOR` versions as supported, and
* fail fast if they encounter an S3 output whose `MAJOR` version is not supported.

---

### 12.3 Backwards-compatible changes (allowed without MAJOR bump)

The following changes are **backwards-compatible**, allowed with a **MINOR** (or PATCH) bump, provided stated conditions hold.

#### 12.3.1 Adding optional fields

Allowed:

* Adding new **optional** fields to:

  * `merchant_zone_baseline_local_5A`,
  * `class_zone_baseline_local_5A`,
  * `merchant_zone_baseline_utc_5A`.

Conditions:

* New fields MUST:

  * not be part of the PK or partition keys,
  * be marked as optional / non-required in JSON-Schema,
  * have well-defined default semantics when absent (e.g. “flag absent ⇒ false or ignore”).

Examples:

* Adding `baseline_clip_applied` (boolean).
* Adding `scale_source` as a free-text or enum describing which base-scale field was used.
* Adding `lambda_unit` as an optional string describing units (if you later support multiple units but keep defaults the same).

#### 12.3.2 Adding optional datasets or aggregates

Allowed:

* Introducing **new optional** S3 datasets (e.g. additional diagnostic aggregates) as long as:

  * They are declared `status="optional"` in the dataset dictionary and registry.
  * Downstream components do not rely on them as required inputs.
  * They are pure deterministic functions of S3’s primary baseline (`merchant_zone_baseline_local_5A`) and sealed inputs.

Such changes do not affect existing consumers that only rely on required S3 outputs.

#### 12.3.3 Adding new optional lambda metadata

Allowed:

* Adding fields that describe λ behaviour but do not change its interpretation, e.g.:

  * flags summarising weekly behaviour (`has_strong_weekend_peak`, `has_night_activity`),
  * bucket-level diagnostic flags indicating clip operations.

Conditions:

* Consumers MUST be able to ignore these without semantic change.
* These fields MUST NOT be used as hidden switches that change how downstream interprets `lambda_local_base`.

#### 12.3.4 Compatible tightening of validation

Allowed:

* Tightening acceptance criteria in ways that reject obviously invalid states that would have caused problems anyway, e.g.:

  * adding extra numeric sanity checks (e.g. sum vs scale absolute bound) that old S3 implementations **already respected**.

Such changes MAY bump `MINOR` or `PATCH` but MUST NOT make previously valid outputs suddenly invalid unless they were genuinely unsafe.

---

### 12.4 Backwards-incompatible changes (require MAJOR bump)

The following changes are **backwards-incompatible** and MUST be accompanied by:

* a new `MAJOR` for `s3_spec_version`, and
* a coordinated update of all S3 consumers.

#### 12.4.1 Changing primary keys or partitioning

Incompatible:

* Changing `primary_key` definitions for S3 datasets, for example:

  * dropping or renaming `merchant_id`, `zone` or `bucket_index` from the PK,
  * adding/removing keys like `scenario_id` from PK.

* Changing partition keys:

  * e.g. switching from `["fingerprint","scenario_id"]` to `["parameter_hash","scenario_id"]` for `merchant_zone_baseline_local_5A`.

Such changes break joins and identity assumptions downstream.

#### 12.4.2 Changing λ semantics (units or meaning)

Incompatible:

* Changing what `lambda_local_base` (or `lambda_utc_base`) means without changing its name/type, for example:

  * defining it as “expected **per-second** rate” instead of “expected **per-bucket** count”,
  * changing it from “expected arrivals per local bucket” to “relative pseudo-intensity” with no explicit mapping to counts.

Any such change MUST:

* either introduce new fields (e.g. new λ columns with different semantics) and deprecate old ones, or
* bump MAJOR in `s3_spec_version` and document the new meaning.

#### 12.4.3 Changing weekly-sum contract

Incompatible:

* Removing or fundamentally changing the relationship:

  ```text
  Σ_k lambda_local_base(m,z[,ch],k)  vs  base_scale(m,z[,ch])
  ```

  – e.g., moving from “weekly sum ≈ base scale” to “weekly sum = base scale × 7” without changing field names.

If the contract changes:

* It MUST be treated as a MAJOR spec change, and
* S3 consumers that assume the old contract MUST be updated.

#### 12.4.4 Changing domain semantics

Incompatible:

* Changing the domain of baselines in a way that breaks downstream assumptions, for example:

  * moving from per-merchant×zone to per-class×zone only (dropping merchant dimension),
  * changing what “zone” means structurally (e.g. using country-only, ignoring tz) while keeping field names the same.

Such changes require a MAJOR bump and likely new schema/field names to avoid confusion.

---

### 12.5 Compatibility of code with existing S3 data

Implementations of S3 and its consumers MUST handle **existing S3 outputs** correctly.

#### 12.5.1 Reading older S3 outputs

When reading S3 outputs:

* If `s3_spec_version.MAJOR` is within the supported set:

  * Consumers MUST accept and interpret the data according to that MAJOR’s contract,
  * treat unknown optional fields as absent,
  * treat unknown flags/metadata as “ignore / default”.

* If `s3_spec_version.MAJOR` is **greater** than any supported MAJOR:

  * Consumers MUST treat S3 outputs for that `(parameter_hash, manifest_fingerprint, scenario_id)` as **unsupported** and fail with a clear “unsupported S3 spec version” error.

#### 12.5.2 Re-running S3 with new code

When S3 is upgraded and re-run for an existing `(parameter_hash, manifest_fingerprint, scenario_id)`:

* If S1/S2 outputs and S3 policies are unchanged:

  * S3 SHOULD produce byte-identical outputs (idempotent).
  * If not, the difference should be attributable only to a **bug fix** and MUST be accompanied by a `PATCH` or `MINOR` bump, plus careful consideration of `S3_OUTPUT_CONFLICT` semantics (you may choose to enforce strict identity and require a new world/pack identity).

* If S1/S2 outputs or S3 policies changed in a way that affects λ:

  * The change MUST be represented by a new `parameter_hash` and/or `manifest_fingerprint`,
  * S3 MUST treat attempts to overwrite outputs under the old identity as `S3_OUTPUT_CONFLICT`.

---

### 12.6 Interaction with parameter packs & upstream changes

Most changes in S3 **values** should come from:

* **parameter pack changes** (`parameter_hash`), and
* **upstream behaviour** (S1/S2 outputs), not from S3 spec.

#### 12.6.1 Policy changes & `parameter_hash`

Any change to:

* S1’s class/scale policies,
* S2’s shape/time-grid policies,
* S3’s baseline policy (`baseline_intensity_policy_5A`), or
* scenario configs that impact intensities,

MUST be represented by a new **parameter pack** and thus a new `parameter_hash`.

Under a new `parameter_hash`:

* S0 must be re-run for that fingerprint (or new fingerprint),
* S1/S2 must be recomputed under the new pack,
* then S3 must be run to produce baselines.

Spec version (`s3_spec_version`) MAY remain unchanged if the contract is the same and only parameters changed.

#### 12.6.2 Upstream structural changes (S1/S2)

If S1 or S2 evolve in a **backwards-incompatible** way (e.g. new PKs, changed semantics of `demand_class` or `shape_value`):

* They will bump their own spec versions (`s1_spec_version`, `s2_spec_version`).
* S3 MUST:

  * bump its own `MAJOR` if it needs to change λ semantics to accommodate, and
  * refuse to read S1/S2 outputs with unsupported `s1_spec_version.MAJOR` / `s2_spec_version.MAJOR`.

---

### 12.7 Governance & documentation

Any change to S3 contracts MUST be governed and documented.

1. **Spec & code updates**

   * Changes to S3 spec (§§1–12) MUST be coupled with:

     * updates to `schemas.5A.yaml` for S3 anchors,
     * updates to `dataset_dictionary.layer2.5A.yaml` entries for S3 datasets,
     * updates to `artefact_registry_5A.yaml` entries for S3 artefacts.

2. **Release notes**

   * Every change that bumps `s3_spec_version` MUST be documented in release notes that include:

     * old → new `s3_spec_version`,
     * MAJOR/MINOR/PATCH classification,
     * description of what changed (schema, semantics, or both),
     * migration guidance (e.g. “re-run S3 for all active worlds” or “only affects new parameter packs”).

3. **Testing**

   * New S3 implementations MUST be tested against:

     * synthetic small worlds (small `M`, small `Z̄`, small `T_week`) to sanity-check domain, joins, and λ invariants,
     * representative larger worlds (realistic `N_mz` and `T_week`) to validate performance and invariants at scale.

   * Tests MUST cover:

     * idempotency (same inputs → same outputs),
     * conflict detection (`S3_OUTPUT_CONFLICT` scenarios),
     * error code coverage (scale/shape join failures, numeric failures, etc.),
     * backwards-compatibility (reading older S3 outputs for supported MAJOR versions).

Within these rules, 5A.S3 can evolve safely: **what** the baseline λ numbers are changes via policies and parameter packs; **how** λ is structured and interpreted is changed only via explicit, versioned spec evolution with clear MAJOR/MINOR/PATCH semantics and a well-defined impact on downstream consumers.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects short-hands, symbols, and abbreviations used in the **5A.S3 — Baseline Merchant×Zone Weekly Intensities** spec. It is **informative** only; binding definitions live in §§1–12.

---

### 13.1 Notation conventions

* **Monospace** (`merchant_zone_baseline_local_5A`) → concrete dataset / field / config names.
* **UPPER_SNAKE** (`S3_INTENSITY_NUMERIC_INVALID`) → canonical error codes.
* `"Quoted"` (`"PASS"`, `"REQUIRED"`) → literal enum/string values.
* Single letters:

  * `m` → merchant
  * `z` → zone (country+tz or `zone_id`)
  * `ch` → channel / channel_group (if present)
  * `k` → local-week bucket index

---

### 13.2 Identity & scope symbols

| Symbol / field         | Meaning                                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------------------------- |
| `parameter_hash`       | Opaque identifier of the **parameter pack** (S1/S2/S3 policies, scenario config) used for this run.           |
| `manifest_fingerprint` | Opaque identifier of the **closed-world manifest** for this world.                                            |
| `scenario_id`          | Scenario identifier (e.g. `"baseline"`, `"stress_bf_2027"`).                                                  |
| `run_id`               | Unique identifier for this execution of S3 for a given `(parameter_hash, manifest_fingerprint, scenario_id)`. |
| `s3_spec_version`      | Semantic version of the 5A.S3 spec that produced the baselines (e.g. `"1.0.0"`).                              |
| `T_week`               | Number of buckets in the local week (from S2’s `shape_grid_definition_5A`).                                   |

---

### 13.3 Key datasets & artefacts (S3-related)

| Name / ID                         | Description                                                                                        |
| --------------------------------- | -------------------------------------------------------------------------------------------------- |
| `merchant_zone_baseline_local_5A` | **Required** S3 output: per `(merchant, zone[, channel], local_bucket)` baseline local λ.          |
| `class_zone_baseline_local_5A`    | Optional S3 output: per `(demand_class, zone[, channel], local_bucket)` class-level baseline λ.    |
| `merchant_zone_baseline_utc_5A`   | Optional S3 output: per `(merchant, zone[, channel], utc_bucket)` baseline UTC λ (if precomputed). |
| `s0_gate_receipt_5A`              | S0 control-plane receipt for this `manifest_fingerprint`.                                          |
| `sealed_inputs_5A`                | S0 sealed inventory of all artefacts 5A may read for this world.                                   |
| `merchant_zone_profile_5A`        | S1 output: per-merchant×zone demand profile — `demand_class` + base scale.                         |
| `shape_grid_definition_5A`        | S2 output: local-week time-grid buckets for `(parameter_hash, scenario_id)`.                       |
| `class_zone_shape_5A`             | S2 output: unit-mass weekly shapes per `(demand_class, zone[, channel], bucket_index)`.            |
| `baseline_intensity_policy_5A`    | S3 policy: defines which base-scale fields to use and how λ relates to the base scale.             |

(Actual `artifact_id` / `manifest_key` live in the dataset dictionary and artefact registry.)

---

### 13.4 Core mathematical symbols

| Symbol / expression           | Meaning                                                                                                              |                                                 |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `D_S3`                        | S3 domain: set of `(merchant_id, zone_representation[, channel])` in scope after S3 policy filters.                  |                                                 |
| `GRID`                        | Local-week bucket set `{k                                                                                            | 0 ≤ k < T_week}`from`shape_grid_definition_5A`. |
| `demand_class(m,z[,ch])`      | Demand class label from S1 for merchant×zone[×channel].                                                              |                                                 |
| `base_scale(m,z[,ch])`        | Base scale for `(m,z[,ch])` from S1, as interpreted by `baseline_intensity_policy_5A` (e.g. weekly expected volume). |                                                 |
| `shape_value(class,z[,ch],k)` | Unit-mass shape fraction from S2 for class×zone[×channel] in bucket `k`.                                             |                                                 |
| `λ_base_local(m,z[,ch],k)`    | Baseline local-time intensity for `(m,z[,ch])` in bucket `k` (S3’s primary output).                                  |                                                 |
| `sum_local(m,z[,ch])`         | Σ over `k` of `λ_base_local(m,z[,ch],k)` across local-week buckets.                                                  |                                                 |

---

### 13.5 Key fields in `merchant_zone_baseline_local_5A`

*(Exact schema in §5; this table summarises semantics.)*

| Field name                                | Meaning                                                                                                 |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `manifest_fingerprint`                    | World identity; MUST match `fingerprint` partition token.                                               |
| `parameter_hash`                          | Parameter pack identity; same as S0/S1/S2 for this run.                                                 |
| `scenario_id`                             | Scenario for which baselines are computed.                                                              |
| `merchant_id`                             | Merchant key (as in Layer-1).                                                                           |
| `legal_country_iso`                       | Country component of the zone (if using explicit `(country, tzid)` representation).                     |
| `tzid`                                    | IANA timezone identifier for the zone (if using explicit representation).                               |
| `zone_id`                                 | Optional combined zone key if you adopt a single-field representation (derived from `(country, tzid)`). |
| `channel` / `channel_group`               | Optional channel dimension (e.g. `"POS"`, `"ECOM"`, `"HYBRID"`).                                        |
| `bucket_index`                            | Local-week bucket index, FK to `shape_grid_definition_5A`.                                              |
| `lambda_local_base`                       | Baseline intensity value for this merchant×zone[×channel] in this local bucket.                         |
| `s3_spec_version`                         | S3 spec version that produced this row.                                                                 |
| `scale_source`                            | Optional description of which base scale field/interpretation was used.                                 |
| `weekly_volume_expected` / `scale_factor` | Optional echoes of S1’s base scale fields, for audit only.                                              |

---

### 13.6 Key fields in `class_zone_baseline_local_5A` (optional)

| Field name                               | Meaning                                                                                            |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `manifest_fingerprint`                   | World identity; same as in `merchant_zone_baseline_local_5A`.                                      |
| `parameter_hash`                         | Parameter pack identity.                                                                           |
| `scenario_id`                            | Scenario identity.                                                                                 |
| `demand_class`                           | Class label for this aggregate row.                                                                |
| `legal_country_iso` / `tzid` / `zone_id` | Zone representation (aligned with S2 & S3 local baselines).                                        |
| `bucket_index`                           | Local-week bucket index.                                                                           |
| `lambda_local_base_class`                | Aggregated baseline λ for this class×zone[×channel] and bucket (e.g. sum or mean; policy-defined). |
| `s3_spec_version`                        | S3 spec version that produced this row.                                                            |

---

### 13.7 Key fields in `merchant_zone_baseline_utc_5A` (optional)

| Field name                                                    | Meaning                                          |
| ------------------------------------------------------------- | ------------------------------------------------ |
| `manifest_fingerprint`                                        | World identity.                                  |
| `parameter_hash`                                              | Parameter pack identity.                         |
| `scenario_id`                                                 | Scenario identity.                               |
| `merchant_id`                                                 | Merchant key.                                    |
| `legal_country_iso` / `tzid` / `zone_id`                      | Zone representation (as above).                  |
| `utc_bucket_index` (or `utc_date` + `utc_bucket_within_date`) | UTC horizon bucket key, per Layer-2 UTC grid.    |
| `lambda_utc_base`                                             | Baseline intensity mapped to the UTC bucket.     |
| `s3_spec_version`                                             | S3 spec version that produced this UTC baseline. |

---

### 13.8 Error codes (5A.S3)

For quick reference, canonical S3 error codes from §9:

| Code                              | Brief description                                              |
| --------------------------------- | -------------------------------------------------------------- |
| `S3_GATE_OR_S2_INVALID`           | S0/S1/S2 gate misaligned or invalid.                           |
| `S3_UPSTREAM_NOT_PASS`            | One or more Layer-1 segments not `"PASS"`.                     |
| `S3_REQUIRED_INPUT_MISSING`       | Required S1/S2 data artefact missing from sealed inputs.       |
| `S3_REQUIRED_POLICY_MISSING`      | Required S3 baseline policy missing or invalid.                |
| `S3_SCALE_JOIN_FAILED`            | Failed to obtain valid base scale for some merchant×zone.      |
| `S3_SHAPE_JOIN_FAILED`            | No matching S2 shape for some `demand_class`×zone combination. |
| `S3_DOMAIN_ALIGNMENT_FAILED`      | Output domain doesn’t match S1 domain (missing/extra rows).    |
| `S3_INTENSITY_NUMERIC_INVALID`    | λ has NaN/Inf/negative or weekly sums violate tolerance.       |
| `S3_OUTPUT_CONFLICT`              | Existing S3 outputs differ from recomputed outputs.            |
| `S3_IO_READ_FAILED`               | I/O/storage read failure on required inputs.                   |
| `S3_IO_WRITE_FAILED`              | I/O/storage write/commit failure.                              |
| `S3_INTERNAL_INVARIANT_VIOLATION` | Internal invariant broken; indicates an implementation bug.    |

These codes appear in run-report/logs, not in the S3 schemas.

---

### 13.9 Miscellaneous abbreviations

| Abbreviation | Meaning                                                                         |
| ------------ | ------------------------------------------------------------------------------- |
| S0           | State 0: Gate & Sealed Inputs for Segment 5A.                                   |
| S1           | State 1: Merchant & Zone Demand Classification.                                 |
| S2           | State 2: Weekly Shape Library.                                                  |
| S3           | State 3: Baseline Merchant×Zone Weekly Intensities (this spec).                 |
| L1 / L2      | Layer-1 / Layer-2.                                                              |
| “zone”       | Shorthand for the zone key; typically `(legal_country_iso, tzid)` or `zone_id`. |
| “baseline”   | Shorthand for `lambda_local_base` (local) or `lambda_utc_base` (UTC).           |

This appendix is a convenience reference; for exact semantics, refer to the binding sections of the S3 spec.

---