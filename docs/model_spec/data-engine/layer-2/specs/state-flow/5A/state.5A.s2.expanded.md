# 5A.S2 — Weekly Shape Library (Layer-2 / Segment 5A)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5A.S2 — Weekly Shape Library** for **Layer-2 / Segment 5A**. It is binding on any implementation of this state.

---

### 1.1 Role of 5A.S2 in Segment 5A

5A.S2 is the **class/zone-level shape engine** for Segment 5A.

Given a sealed world `(parameter_hash, manifest_fingerprint)` and an established S0/S1:

* It takes:

  * the **traffic personas** from 5A.S1 (the set of `demand_class` × zone combinations that exist), and
  * the **shape library configuration** from the 5A parameter pack (how each class/zone should behave over a local week),

* and produces a **deterministic, normalised weekly local-time shape** for each in-scope combination, typically over a fixed time grid such as:

> `bucket_index = 0..T_week-1` representing local hour-of-week or another fixed partition of a local 7-day week.

5A.S2 is:

* **RNG-free** — it MUST NOT consume RNG or introduce stochastic variation.
* **Class/zone-level only** — it does **not** know about individual merchants or their scale; it works at `(demand_class, zone[, channel])`.
* **Template-producing** — it outputs **unit-mass templates** (shapes that sum to 1 per class/zone), which later states scale and overlay.

It does **not** compute merchant-level intensities or calendar-modified curves; it only defines “if this class had one unit of volume over a week, how would that unit be distributed across the week in local time?”.

---

### 1.2 Objectives

5A.S2 MUST:

* **Define a stable local-week time grid**

  * Establish a clear, schema-governed definition of:

    * bucket size (e.g. 1 hour, 30 min, 15 min),
    * total number of buckets `T_week` per local week,
    * mapping from `bucket_index` to local `(day_of_week, time_of_day)`.

* **Provide normalised shapes per class/zone**

  * For every `(demand_class, zone[, channel])` that is in scope for 5A:

    * produce a vector of non-negative shape values over the week;
    * enforce that the sum over buckets for each `(class, zone[, channel])` is exactly 1 (within numerical tolerance).

* **Remain deterministic and policy-driven**

  * Derive shapes solely from:

    * S1 output (`merchant_zone_profile_5A`) for the **domain** of classes/zones, and
    * 5A shape policies/configs for **shape definitions**,
      with no randomness and no dependence on wall-clock time.

* **Provide a single authority for weekly patterns**

  * Downstream states (S3/S4) MUST treat S2 outputs as the **only source** of weekly local-time patterns per `(demand_class, zone[, channel])`.
  * Any change to shapes MUST be expressed via shape-policy/parameter-pack changes and re-running S2, not via ad-hoc logic elsewhere.

---

### 1.3 In-scope behaviour

The following tasks are **in scope** for 5A.S2 and MUST be handled here:

* **Gating on S0/S1 and shape configs**

  * Verifying that:

    * S0 gate / sealed inputs are valid for the fingerprint;
    * S1 successfully produced `merchant_zone_profile_5A` for the same `(parameter_hash, manifest_fingerprint)`;
    * all required shape-related configs (time grid, base templates, modifiers) are present and schema-valid.

* **Domain discovery for the shape library**

  * Determining the set of `(demand_class, zone[, channel])` for which shapes must exist, by:

    * scanning `merchant_zone_profile_5A` to find which combinations are actually used, and/or
    * complementing that with any explicitly configured class/zone combos in the shape policy (e.g. allowed but not yet populated domains).

* **Time-grid and local-week definition**

  * Constructing a precise, schema-governed model of the local week:

    * `bucket_index` range and step,
    * mapping to local `(day_of_week, time_in_day)`,
    * handling the wrap from end-of-week back to start-of-week.

* **Shape construction per class/zone**

  * For each `(demand_class, zone[, channel])` in the domain:

    * applying the base shape definition from policy (e.g. “retail business hours”, “online 24/7”, “restaurant evening peak”),
    * applying any deterministic adjustments driven by:

      * zone/country attributes (e.g. weekend on Fri–Sat vs Sat–Sun),
      * channel attributes (e.g. POS vs e-com),
      * scenario-independent modifiers (e.g. “night economy zone”).

  * Ensuring shapes are non-negative and numerically stable.

* **Shape normalisation and validation**

  * Enforcing, for each `(class, zone[, channel])`:

    ```text
    Σ_{k=0..T_week-1} shape_value(class, zone, k) = 1
    ```

    within a defined tolerance, and
  * ensuring no NaNs/Infs and no negative values.

* **Emitting class/zone shape datasets**

  * Producing:

    * a **grid definition** dataset describing the week’s bucket structure, and
    * a **shape dataset** containing one row per `(demand_class, zone[, channel], bucket_index)`.

---

### 1.4 Out-of-scope behaviour

The following are explicitly **out of scope** for 5A.S2 and MUST NOT be implemented in this state:

* **Merchant-level specialisation**

  * S2 MUST NOT use:

    * individual `merchant_id`s,
    * per-merchant base scale,
    * per-merchant quirks or exceptions.

  Its outputs are **class/zone templates** only; per-merchant tailoring is handled by S3/S4 via composition with S1.

* **Calendar & scenario overlays**

  * S2 MUST NOT:

    * apply public holidays, paydays, campaign windows, or stress-scenario shocks;
    * encode event-specific spikes (e.g. “Black Friday”, “Cyber Monday”).

  Those effects belong to 5A.S4 (calendar overlays) and/or 5B (stochastic realisation).

* **Randomness or stochastic modulation**

  * S2 MUST NOT:

    * draw from any RNG,
    * implement LGCP/Gaussian random fields,
    * introduce per-week or per-class noise.

  Stochastic variation belongs to 5B and, for routing, Layer-1 RNG.

* **Arrivals, counts, or intensities**

  * S2 MUST NOT:

    * generate arrival timestamps or counts,
    * compute full `λ(m,zone,t)` surfaces, or
    * combine shapes with S1’s base scale.

  That composition is the responsibility of S3 (baseline intensities) and S4 (calendar overlays).

* **Upstream reinterpretation**

  * S2 MUST NOT re-derive or reinterpret:

    * zone allocation (3A),
    * virtual semantics (3B),
    * routing weights (2B),
    * civil-time semantics (2A).

  It only uses these indirectly via S1’s classification outputs and shape policies where needed.

---

### 1.5 Downstream obligations

This specification imposes the following obligations on downstream states (5A.S3–S4 and any other consumers):

* **Use S2 as the sole weekly-shape authority**

  * 5A.S3 and S4 MUST treat S2’s `class_zone_shape_5A` (or equivalent) as the **only source of weekly local-time shape templates**.
  * They MUST NOT implement separate, conflicting shape logic; any changes to shape behaviour must be encoded in S2’s policies/configs and parameter packs.

* **Require valid S2 outputs before proceeding**

  * Before constructing merchant-level intensities or applying calendar overlays, S3/S4 MUST:

    * validate that S2 outputs exist for the relevant `(parameter_hash, manifest_fingerprint[, scenario_id])`,
    * ensure shapes are schema-valid, normalised, and complete over the domain implied by S1.

* **Do not mutate S2 outputs**

  * No later state may modify or overwrite S2’s shape datasets for any fingerprint.
  * If different shapes are needed (e.g. new class definitions, different time-grid), these MUST be introduced via:

    * a new 5A shape policy / parameter pack (`parameter_hash`), and
    * a new run of S2 under that identity.

Within this scope, 5A.S2 cleanly defines the **deterministic, class/zone-level weekly patterns** that S3/S4 will scale and overlay, without encroaching on merchant-level logic, stochastic behaviour, or temporal overlays.

---

## 2. Preconditions & sealed inputs *(Binding)*

This section defines when **5A.S2 — Weekly Shape Library** is allowed to run, and what sealed inputs it may rely on. All rules here are **binding**.

---

### 2.1 Invocation context

5A.S2 MUST only be invoked in the context of a well-defined engine run characterised by:

* `parameter_hash` — the parameter pack identity for this run.
* `manifest_fingerprint` — the closed-world manifest identity.
* `run_id` — the execution identifier for this 5A run.

These MUST:

* be supplied by the orchestration layer,
* match the values used by **5A.S0** and **5A.S1** for the same world, and
* be treated as immutable for the duration of S2.

5A.S2 MUST NOT attempt to recompute or override `parameter_hash` or `manifest_fingerprint`.

---

### 2.2 Dependency on S0 (gate receipt & sealed inventory)

Before any work, 5A.S2 MUST require a valid S0 gate:

1. **Presence**

   * `s0_gate_receipt_5A` exists for `fingerprint={manifest_fingerprint}`.
   * `sealed_inputs_5A` exists for `fingerprint={manifest_fingerprint}`.

   Both MUST be discovered via `dataset_dictionary.layer2.5A.yaml` and `artefact_registry_5A.yaml`, not via ad-hoc paths.

2. **Schema validity**

   * `s0_gate_receipt_5A` validates against `schemas.5A.yaml#/validation/s0_gate_receipt_5A`.
   * `sealed_inputs_5A` validates against `schemas.5A.yaml#/validation/sealed_inputs_5A`.

3. **Identity consistency**

   * `s0_gate_receipt_5A.parameter_hash == parameter_hash`.
   * All rows in `sealed_inputs_5A` have:

     * `parameter_hash == parameter_hash`, and
     * `manifest_fingerprint == manifest_fingerprint`.

4. **Sealed-inventory digest**

   * S2 MUST recompute `sealed_inputs_digest` from `sealed_inputs_5A` using the hashing law defined for S0 and confirm equality with `s0_gate_receipt_5A.sealed_inputs_digest`.

If **any** of these checks fail, 5A.S2 MUST abort with a precondition failure (e.g. `S2_GATE_OR_S1_INVALID`) and MUST NOT read any further inputs or attempt to write outputs.

---

### 2.3 Upstream segment readiness (Layer-1) & S1

5A.S2 sits on top of Layer-1 and S1. It MUST NOT run unless the world beneath it is green.

From `s0_gate_receipt_5A.verified_upstream_segments`, S2 MUST:

* read status for each of `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.

Precondition:

* For S2 to proceed, **all** of these segments MUST have `status="PASS"`.

If any required upstream segment has `status="FAIL"` or `status="MISSING"`, S2 MUST:

* abort with a precondition error (e.g. `S2_GATE_OR_S1_INVALID` or `S2_UPSTREAM_NOT_PASS` if you define one), and
* MUST NOT attempt to read Layer-1 tables, even if they are physically present.

In addition, S2 depends on S1:

* 5A.S1 MUST have completed successfully for this `(parameter_hash, manifest_fingerprint)` and produced a valid `merchant_zone_profile_5A`.
* S2 MUST treat any inability to locate or validate `merchant_zone_profile_5A` as a hard precondition failure (see below).

S2 MUST NOT attempt to “rebuild” S1 logic; it can only proceed if S1 is present and valid.

---

### 2.4 Required sealed inputs for S2

Given a valid S0 gate, S2’s **input universe** is defined by `sealed_inputs_5A`. S2 MUST be able to resolve at least the following artefacts for this fingerprint.

#### 2.4.1 S1 output (domain discovery)

Required dataset:

* `merchant_zone_profile_5A` (owner segment `"5A"`, role `"model"`, status `"required"`).

Preconditions:

* At least one row MUST exist for the fingerprint (unless the engine explicitly allows an empty 5A domain and S2 is configured to handle it).
* The dataset MUST be resolvable via the 5A dictionary/registry with:

  * `schema_ref: schemas.5A.yaml#/model/merchant_zone_profile_5A` (or equivalent anchor),
  * `partition_keys: ["fingerprint"]`, and
  * `primary_key: ["merchant_id","legal_country_iso","tzid"]`.

Authority:

* S2 MUST use `merchant_zone_profile_5A` only to discover the **set of `(demand_class, zone[, channel])` combinations** that are in use.
* It MUST NOT reinterpret per-merchant scale or override S1’s class assignments.

#### 2.4.2 Time-grid / local-week configuration

Required artefact(s):

* One or more configuration objects that define the **local-week time grid**, for example:

  * `shape_time_grid_policy_5A` — bucket size, number of buckets `T_week`, mapping from `bucket_index` to `(day_of_week, time_of_day)`, and any “week start” convention.

Preconditions:

* The relevant artefact(s) MUST appear in `sealed_inputs_5A` with:

  * `owner_segment="5A"`,
  * `role` such as `"time_grid_config"` or `"policy"`,
  * `status="REQUIRED"`,
  * valid `schema_ref` into `schemas.5A.yaml` or `schemas.layer2.yaml`.

Authority:

* These artefacts are the **sole authority** for how the local week is discretised in S2.
* S2 MUST NOT hard-code alternative bucket sizes or week definitions; any change to the grid MUST go via this config and `parameter_hash`.

#### 2.4.3 Shape library / template policies

Required artefact(s):

* One or more 5A-specific policy/config objects that define the **shape library**, e.g.:

  * `shape_library_5A`

    * per `demand_class` base template types and parameters,
    * optional zone/country/channel modifiers,
    * constraints (e.g. minimum night-time mass, max number of peaks).

* Optional supporting configs:

  * class-to-template mapping tables,
  * region / tz-group hint tables, if they affect shapes.

Preconditions:

* These artefacts MUST be present in `sealed_inputs_5A` with:

  * `owner_segment="5A"`,
  * `role="policy"` or equivalent,
  * `status="REQUIRED"`,
  * valid `read_scope` (`"METADATA_ONLY"` or `"ROW_LEVEL"` depending on representation).

Authority:

* These policies are the **only authority** for how weekly shapes are constructed.
* `shape_time_grid_policy_5A` is the sole grid authority; `shape_library_5A` MUST NOT redefine time-grid parameters.
* S2 MUST NOT embed its own alternate shape rules; it MUST implement what these policies describe.

#### 2.4.4 Scenario metadata (if shapes vary by scenario)

In the base design, S2 is **scenario-agnostic** and defines shapes for a baseline class/zone world. However, if the spec allows shapes to differ by high-level scenario type (e.g. baseline vs extreme stress) then S2 MAY depend on:

* scenario metadata artefacts sealed in `sealed_inputs_5A` (same ones S1 sees), to derive coarse traits such as `scenario_id` and `scenario_type`.

Preconditions:

* If S2 is scenario-sensitive, the relevant scenario config(s) MUST be present in `sealed_inputs_5A` and schema-valid.

Authority:

* Scenario artefacts sealed by S0 remain the **only authority** for which scenario S2 is operating under; S2 MUST NOT switch scenario via out-of-band configuration.

---

### 2.5 Permitted but optional sealed inputs

5A.S2 MAY also use additional artefacts marked as `status="OPTIONAL"` in `sealed_inputs_5A`, for example:

* Country/region reference tables (e.g. “weekend day patterns” per country group).
* Optional “class override” tables for a small number of special zones.
* Diagnostic configs controlling extra logging or validation thresholds.

Rules:

* S2 MUST treat optional inputs as **enhancements only**: their absence MUST NOT prevent S2 from producing valid shapes, provided required artefacts exist.
* If an optional artefact is absent, S2 MUST fall back to documented default behaviour.

---

### 2.6 Authority boundaries for S2 inputs

The following boundaries are binding:

1. **`sealed_inputs_5A` is the only discovery mechanism**

   * S2 MUST use `sealed_inputs_5A` to determine **which** artefacts it may read.
   * It MUST NOT read datasets or configs not present in `sealed_inputs_5A` for this fingerprint, even if they are physically present.

2. **S1 output is domain authority, not a free-form feature set**

   * `merchant_zone_profile_5A` is used by S2 **only** to:

     * discover which `demand_class` values exist, and
     * which zones those classes appear in.
   * S2 MUST NOT:

     * override `demand_class` assignments,
     * use per-merchant scale fields to drive shapes, or
     * depend on merchant IDs beyond domain discovery.

3. **Time grid & shape policies are configuration authority**

   * Time-grid config and shape policies from 5A are the **only** sources for grid structure and shape semantics.
   * S2 MUST NOT derive a time grid from external notions (e.g. directly from 2A tz rules) or embed implicit shape semantics in code.

4. **No out-of-band overrides**

   * S2 MUST NOT widen or narrow its input universe based on environment variables, CLI flags, or feature switches that are **not encoded** in:

     * the parameter pack (and thus `parameter_hash`), and
     * `sealed_inputs_5A`.

   Any configuration change that affects S2 behaviour MUST flow through policy/config artefacts and be reflected in `parameter_hash`.

Within these preconditions and boundaries, 5A.S2 runs in a sealed, catalogue-defined world: S0 tells it **what exists and is allowed**, S1 tells it **which classes/zones are in use**, and 5A shape/time-grid policies tell it **how to construct deterministic weekly shapes** over that domain.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **exactly what 5A.S2 may read**, how those inputs are obtained, and which upstream components are authoritative for particular facts. All rules here are **binding**.

5A.S2 is **RNG-free** and **template-only**: it can only use inputs that are:

* explicitly sealed by **5A.S0** in `sealed_inputs_5A`, and
* compatible with a **class/zone-level** view of the world (no per-merchant randomness, no arrivals).

---

### 3.1 Overview

5A.S2 has three main input categories:

1. **Control-plane inputs from S0 & S1**
   – to know whether the world is green and what class/zone combinations exist.

2. **Shape-relevant configuration from 5A**
   – time-grid (local-week) config and shape library policies/templates.

3. **Optional reference data for shape variation**
   – country/region/time-use patterns, if used by shape policy.

All inputs MUST be:

* discovered via `sealed_inputs_5A` for the current `manifest_fingerprint`, and
* resolved via the dataset dictionary + artefact registry.

S2 MUST NOT read artefacts that are **not** present in `sealed_inputs_5A` for this fingerprint.

---

### 3.2 Control-plane inputs (S0 and S1)

#### 3.2.1 `s0_gate_receipt_5A` (S0)

**Logical input**

* `s0_gate_receipt_5A` — the S0 control-plane record for this fingerprint.

**Role for S2**

* Confirms:

  * the engine is running with the expected `parameter_hash` / `manifest_fingerprint`,
  * upstream segments 1A–3B are `"PASS"`,
  * which scenario ID/pack is in force (if S2 is scenario-aware).

**Authority boundary**

* S2 MUST treat `s0_gate_receipt_5A` as the **sole authority** for:

  * upstream segment status,
  * `parameter_hash` for this fingerprint,
  * `sealed_inputs_digest` over `sealed_inputs_5A`.

* S2 MUST NOT re-validate upstream segments directly (beyond what’s needed for its own inputs), nor modify `s0_gate_receipt_5A`.

#### 3.2.2 `sealed_inputs_5A` (S0)

**Logical input**

* `sealed_inputs_5A` — inventory of all artefacts that 5A is allowed to read for this fingerprint.

**Authority boundary**

* `sealed_inputs_5A` is the **exclusive catalogue** S2 may use:

  * If an artefact is not listed in `sealed_inputs_5A`, S2 MUST treat it as out-of-bounds.
  * S2 MUST respect `role`, `status`, and `read_scope` for each artefact.

S2 must discover all shape-related configs/datasets **only** by scanning `sealed_inputs_5A` and matching on:

* `owner_segment`,
* `artifact_id`,
* `role`, `status`, and `read_scope`.

#### 3.2.3 `merchant_zone_profile_5A` (S1)

**Logical input**

* Required modelling dataset from S1; shape anchor in `schemas.5A.yaml#/model/merchant_zone_profile_5A`.

**Role for S2**

* Used **only** to determine the **domain of the shape library**, i.e.:

  ```text
  DOMAIN_S2 = { (demand_class, zone[, channel]) }
  ```

  where:

  * `demand_class` comes from S1,
  * `zone` derives from `(legal_country_iso, tzid)` (or a derived `zone_id`),
  * optional `channel` if S1 encodes it as a dimension.

Authority boundaries:

* S2 MUST NOT:

  * override `demand_class` assignments,
  * read or use per-merchant scale values to define shapes,
  * treat `merchant_id` as a meaningful dimension.

* For S2, `merchant_zone_profile_5A` is **domain authority** (which classes/zones exist), not a source of scale or per-merchant nuance.

---

### 3.3 Time-grid / local-week configuration

Logical inputs may include one or more artefacts like:

* `shape_time_grid_policy_5A`
* `local_week_definition_5A`

**Content (conceptual)**

* Global or per-parameter-pack configuration specifying:

  * `bucket_duration` (e.g. 1h, 30m, 15m).
  * `buckets_per_day` and `buckets_per_week` (`T_week`).
  * Mapping from `bucket_index` → `(local_day_of_week, local_time_of_day)`.
  * Week start convention (e.g. Monday 00:00 local time).
  * Any alignment constraints (e.g. bucket indices always represent local civil time with DST handled upstream).

**Authority boundary**

* These artefacts are the **sole authority** for:

  * how a “local week” is discretised, and
  * how bucket indices map to local time semantics.

S2 MUST NOT:

* infer its own bucketisation from 2A tz rules or from ad-hoc assumptions;
* hard-code a different bucket resolution than the one declared in the config.

Any change in time grid MUST be enacted via these configs and a new `parameter_hash`.

---

### 3.4 Shape library policies / templates

Logical inputs may include artefacts such as:

* `shape_library_5A`
* `class_shape_templates_5A`
* optional `zone_shape_modifiers_5A`, `channel_shape_modifiers_5A`

**Content (conceptual)**

* For each `demand_class` (and possibly per zone/channel group):

  * a **base template** type (e.g. “office-hours”, “nightlife”, “online-flat”, “two-peak-retail”),
  * template parameters (e.g. peak times, relative peak heights, weekend factors),
  * constraints (e.g. enforce zero mass outside configured opening windows),
  * optional adjustments per:

    * country or region group,
    * tz group or zone type,
    * channel (POS vs e-com).

Authority boundary:

* These policies are the **only authority** for shape semantics:

  * S2 MUST implement them as data, not encode additional hard-wired behaviour.
  * Every `(demand_class, zone[, channel])` used by S2 MUST derive its shape from these policies (directly or via documented defaults).

* If a combination is not covered by the policy, S2 MUST either:

  * use a documented default, or
  * treat it as a configuration error (not silently make up behaviour).

---

### 3.5 Optional reference data for zone/channel variation

S2 MAY depend on additional reference data **only if** they are present in `sealed_inputs_5A` and referenced by shape policies, e.g.:

* Country/region grouping tables:

  * `country_weekend_policy` (which days are weekend).
  * `region_time_use_profile` (e.g. lunch peaks or late-night economies).

* Channel grouping / classification:

  * `channel_shape_overrides` mapping coarse channels to alternate templates.

Authority boundary:

* Such reference tables are **read-only** and understood solely via their `schema_ref` and 5A policies.
* S2 MUST NOT redefine upstream geographic or channel semantics; it only uses these to condition shape templates.

If they are absent and marked `status="OPTIONAL"`, S2 MUST fall back to documented defaults and still be able to produce valid shapes.

---

### 3.6 Authority boundaries & out-of-bounds inputs

The following boundaries are **binding**:

1. **`sealed_inputs_5A` is the exclusive universe**

   * S2 MUST NOT read any dataset or config that does not appear in `sealed_inputs_5A` for the current `manifest_fingerprint`.
   * This applies even if a dataset exists physically in storage.

2. **Class/zone domain comes from S1, not ad-hoc scans**

   * S2 MUST derive its domain of `(demand_class, zone[, channel])` from:

     * `merchant_zone_profile_5A`, and
     * any explicit shape-policy config that declares additional “allowed but currently unused” class/zone combos.

   * S2 MUST NOT infer domain by scanning Layer-1 fact tables directly.

3. **Time-grid and shapes are configuration-defined**

   * Bucketisation and shapes are defined by 5A configs/policies; S2 MUST NOT:

     * assume a fixed `T_week` independent of config,
     * adjust bucket structures on the fly,
     * or introduce time-dependent behaviour beyond what the policies describe.

4. **No use of per-merchant signals**

   * S2 MUST NOT use:

     * per-merchant scale,
     * per-merchant behavioural quirks,
     * merchant IDs beyond domain discovery.

   All per-merchant variability belongs to S1 (for classification/scale) and to later states (S3/S4/5B).

5. **No out-of-band configuration**

   * S2 MUST NOT change behaviour based on environment variables, CLI flags, feature switches, or temporal conditions that are not encoded in:

     * the parameter pack (captured in `parameter_hash`), and
     * policy/config artefacts listed in `sealed_inputs_5A`.

Any change to shape behaviour MUST go through parameter pack + policy updates (and thus a new `parameter_hash`), not via hidden runtime switches.

Within these boundaries, 5A.S2 sees a **sealed, class/zone level view** of the world and uses only S0/S1 outputs + 5A shape/time-grid policies to build deterministic weekly shapes.

---

## 4. Outputs (datasets) & identity *(Binding)*

This section defines the **data products** of **5A.S2 — Weekly Shape Library** and how they are identified in storage. All rules here are **binding**.

5A.S2 produces **class/zone-level templates**, not merchant-level surfaces and not events.

---

### 4.1 Overview of outputs

5A.S2 MUST produce two **required** modelling datasets and MAY produce one **optional** convenience dataset:

1. **`shape_grid_definition_5A` *(required)***

   * Defines the **local-week time grid**: bucket size, number of buckets, and mapping from `bucket_index` → `(day_of_week, time_of_day)`.

2. **`class_zone_shape_5A` *(required)***

   * Defines the **normalised weekly shape** for each in-scope `(demand_class, zone[, channel], bucket_index)` combination.
   * Each shape is a non-negative vector over the week that sums to 1 for its `(demand_class, zone[, channel])`.

3. **`class_shape_catalogue_5A` *(optional)*

   * A **base template library** per `demand_class` (and possibly per channel/type), prior to zone-specific adjustments.
   * Convenience / audit surface only; MUST be derivable from 5A policies and MUST NOT carry information that contradicts `class_zone_shape_5A`.

These datasets are:

* **parameter-pack + scenario scoped** (keyed by `parameter_hash` and, if used, `scenario_id`),
* **not seed- or run-scoped**, and
* **not fingerprint-partitioned** (they are reusable across manifests that share the same parameter pack and scenario).

---

### 4.2 `shape_grid_definition_5A` (required)

#### 4.2.1 Semantic role

`shape_grid_definition_5A` describes the **canonical local-week grid** that all S2 shapes live on. It tells downstream components:

* how many buckets there are in a local week (`T_week`),
* what each `bucket_index` means in local time (day-of-week, time-of-day), and
* how that ties back to the 5A time-grid policy.

Every row describes **one time bucket**.

#### 4.2.2 Required content (conceptual)

For each bucket `k` in `[0, T_week-1]`, a row MUST include at least:

* `parameter_hash` — the parameter pack identity.

* `scenario_id` — scenario identifier (if S2 is scenario-specific; otherwise a baseline ID).

* `bucket_index` — integer in `[0, T_week-1]`.

* `local_day_of_week` — integer or enum (e.g. 1=Monday … 7=Sunday), as defined in the time-grid policy.

* `local_time_of_day` — representation of time within the day, such as:

  * `minutes_since_midnight`, or
  * `(hour_of_day, minute_of_hour)`.

* `bucket_duration_minutes` (or equivalent) — duration of the bucket.

* Optional metadata:

  * `is_weekend` flag,
  * `is_open_hours_default` flag, etc., if the policy defines them.

These fields are pinned in detail in §5 (schema section); here the semantics are binding.

#### 4.2.3 Identity & keys

For `shape_grid_definition_5A`:

* **Partitioning:**

  * `partition_keys: ["parameter_hash","scenario_id"]`

* **Primary key:**

  * `primary_key: ["parameter_hash","scenario_id","bucket_index"]`

* **Uniqueness & coverage:**

  * For each `(parameter_hash, scenario_id)` pair:

    * `bucket_index` MUST cover a contiguous range `[0, T_week-1]` with no gaps or duplicates.
    * `T_week` MUST be consistent with the time-grid policy.

`shape_grid_definition_5A` MUST NOT embed `manifest_fingerprint`; it is parameter-pack + scenario specific, not world-specific.

---

### 4.3 `class_zone_shape_5A` (required)

#### 4.3.1 Semantic role

`class_zone_shape_5A` is the **core shape library** output: it defines, for each in-scope `(demand_class, zone[, channel])`, a non-negative vector over the week that sums to 1.

Intuitively:

> For a given class/zone[/channel], if total weekly volume = 1, `shape_value` says *what fraction of that volume* lands in each local-week bucket.

#### 4.3.2 Domain & minimal content

For a given `(parameter_hash, scenario_id)`:

* Let `DOMAIN_S1` be the set of `(demand_class, zone[, channel])` combinations that actually appear in `merchant_zone_profile_5A` for this parameter pack (and, if used, for this scenario), after any S2 policy filtering.
* Let `ZONE` be represented in S2 as `(legal_country_iso, tzid)` or a canonical `zone_id` derived deterministically from those fields.

The **domain** of `class_zone_shape_5A` MUST be:

* all `(parameter_hash, scenario_id, demand_class, zone[, channel], bucket_index)` such that:

  * `(demand_class, zone[, channel]) ∈ DOMAIN_S2`, and
  * `bucket_index ∈ [0, T_week-1]` as defined by `shape_grid_definition_5A`.

Each row MUST include, at minimum:

* Identity fields:

  * `parameter_hash`
  * `scenario_id`
  * `demand_class` (string label as per S1/policy)
  * `legal_country_iso` and `tzid` **or** a canonical `zone_id` that can be mapped back to those; the spec MUST define which representation is used.
  * Optional `channel_group` or `channel` if S2 distinguishes per-channel shapes.

* Time-grid key:

  * `bucket_index` — integer, FK to `shape_grid_definition_5A` for this `(parameter_hash, scenario_id)`.

* Shape value:

  * `shape_value` — numeric (e.g. `dec_u128`), MUST be ≥ 0, representing the fraction of weekly volume in this bucket.

Optional fields MAY include:

* `template_id` — ID of the base template used.
* `adjustment_flags` — e.g. `"weekend_shift_applied"`, `"night_peak_applied"`.
* `s2_spec_version` — spec version (if stored per-row; could also appear in a separate header record).

#### 4.3.3 Identity & keys

For `class_zone_shape_5A`:

* **Partitioning:**

  * `partition_keys: ["parameter_hash","scenario_id"]`

* **Primary key (logical):**

  * If zone is represented as `(legal_country_iso, tzid)`:

    ```yaml
    primary_key:
      - parameter_hash
      - scenario_id
      - demand_class
      - legal_country_iso
      - tzid
      - bucket_index
    ```

  * If a separate `zone_id` is used, replace `legal_country_iso,tzid` with `zone_id`, but the mapping to 3A’s zone universe MUST be defined elsewhere.

* **Normalisation invariant:**

  For each distinct combination of `(parameter_hash, scenario_id, demand_class, zone[, channel])`, S2 MUST ensure:

  ```text
  Σ_{k over all buckets for this local week} shape_value = 1
  ```

  within a defined numerical tolerance, and all `shape_value ≥ 0`.

`class_zone_shape_5A` MUST NOT embed `manifest_fingerprint`; it is reusable across worlds that share the same parameter pack and scenario.

---

### 4.4 `class_shape_catalogue_5A` (optional)

#### 4.4.1 Semantic role

If implemented, `class_shape_catalogue_5A` is a **base-template catalogue**:

* It describes, for each `demand_class` (and possibly channel group), a **canonical base shape** or template identifier used by S2 before zone-specific modifications.

This is useful for:

* debugging (e.g. “what is the canonical template for class X?”),
* validating shape policy coverage,
* comparing shapes across zones.

#### 4.4.2 Domain & content

For a given `(parameter_hash, scenario_id)`:

* Domain: all `demand_class` (and optional `channel_group`) that are configured in the shape library policy for this parameter pack.

Each row SHOULD include:

* `parameter_hash`
* `scenario_id`
* `demand_class`
* Optional `channel_group` / `channel`

Plus template descriptors:

* `template_id` — identifier of the base template.
* `template_type` — e.g. `"office_hours"`, `"nightlife"`, `"online_flat"`.
* `template_params` — structured field (JSON/object) with template parameters (e.g. peak positions, peak heights, weekday/weekend splits).
* Optional: `notes`, `policy_version`, etc.

#### 4.4.3 Identity & keys

If materialised:

* `partition_keys: ["parameter_hash","scenario_id"]`
* `primary_key: ["parameter_hash","scenario_id","demand_class"` (and `channel_group` if present)]`.

This dataset MUST be derivable from 5A shape policies and MUST NOT contradict `class_zone_shape_5A`. Any discrepancy is a configuration error.

---

### 4.5 Relationship between S2 outputs and other segments

#### 4.5.1 Relationship to S1 (`merchant_zone_profile_5A`)

* `class_zone_shape_5A` operates at the granularity of `(demand_class, zone[, channel])`, not `(merchant, zone)`.
* For every `(demand_class, zone[, channel])` combination used in `merchant_zone_profile_5A`, there MUST be a corresponding set of rows in `class_zone_shape_5A` that defines a complete, normalised weekly shape.

Downstream states (S3/S4) will combine:

* S1’s per-merchant base scale, and
* S2’s per-class/zone shape,

to produce merchant-level intensities.

#### 4.5.2 Relationship to Layer-1 zones (3A)

* Zones referenced in `class_zone_shape_5A` MUST map 1:1 onto the zone universe defined by 3A (`zone_alloc`) for the relevant countries/tzids, via:

  * direct use of `(legal_country_iso, tzid)`, or
  * a canonical `zone_id` that is a deterministic, reversible encoding of those.

S2 MUST NOT invent new zones; it only attaches shapes to zones defined upstream.

---

### 4.6 Control-plane vs modelling outputs

Unlike S0, S2:

* **does not** produce control-plane datasets (no new gate receipt or sealed inventory);
* produces only **modelling outputs** (`shape_grid_definition_5A`, `class_zone_shape_5A`, and optionally `class_shape_catalogue_5A`), which:

  * are deterministic functions of `parameter_hash`, `scenario_id`, and sealed policies/configs;
  * are partitioned by `parameter_hash` and `scenario_id`, not by `manifest_fingerprint`;
  * are immutable once written, except for idempotent re-runs that produce identical content.

Later, the 5A segment-level validation state will:

* treat S2 outputs as required inputs, and
* include them in the 5A validation bundle / `_passed.flag` story, but S2 itself does not write a validation bundle.

Within this identity model, S2’s outputs provide a single, reusable library of **class/zone/week shapes** for each parameter pack and scenario, aligned with S1’s demand classes and 3A’s zone universe.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

Contracts for the S2 “shape library” live in the standard files under `docs/model_spec/data-engine/layer-2/specs/contracts/5A/`. S2 writes:

1. `shape_grid_definition_5A`
2. `class_zone_shape_5A`
3. `class_shape_catalogue_5A` (optional)

| Dataset | Schema anchor | Dictionary id | Registry key |
|---|---|---|---|
|`shape_grid_definition_5A`|`schemas.5A.yaml#/model/shape_grid_definition_5A`|`shape_grid_definition_5A`|`mlr.5A.model.shape_grid_definition`|
|`class_zone_shape_5A`|`schemas.5A.yaml#/model/class_zone_shape_5A`|`class_zone_shape_5A`|`mlr.5A.model.class_zone_shape`|
|`class_shape_catalogue_5A` (opt.)|`schemas.5A.yaml#/model/class_shape_catalogue_5A`|`class_shape_catalogue_5A`|`mlr.5A.model.class_shape_catalogue`|

Binding notes:

- Partition keys, primary keys, writer ordering, and storage paths are exactly as stated in the dictionary.
- Column definitions (bucket indices, normalised shape values, metadata) are governed solely by the schema pack; S2 MUST NOT restate them.
- Registry dependencies constrain inputs to sealed artefacts (S1 profiles, sealed configs, time-grid policy). Any new dependency requires sealed-input + registry updates first.
- Outputs must be deterministic per `(parameter_hash, manifest_fingerprint, scenario_id)`.


## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section specifies the **ordered, deterministic algorithm** for **5A.S2 — Weekly Shape Library**. Implementations MUST follow these steps and invariants. S2 is **purely deterministic** and MUST NOT consume RNG.

---

### 6.1 High-level invariants

5A.S2 MUST satisfy:

1. **RNG-free**

   * MUST NOT call any RNG primitive.
   * MUST NOT write to `rng_audit_log`, `rng_trace_log` or any RNG event streams.

2. **Catalogue-driven**

   * MUST discover all inputs via:

     * `s0_gate_receipt_5A`,
     * `sealed_inputs_5A`,
     * dataset dictionaries + artefact registries.
   * MUST NOT use hard-coded paths, directory scans, or network calls to discover inputs.

3. **Class/zone-level only**

   * MUST NOT use `merchant_id` beyond domain discovery.
   * MUST NOT read or depend on per-merchant scale or any event-level data.

4. **Normalised shapes**

   * For each `(parameter_hash, scenario_id, demand_class, zone[, channel])`, the weekly shape vector MUST:

     * have all `shape_value ≥ 0`, and
     * sum to exactly 1 (within a defined numeric tolerance).

5. **Atomic outputs**

   * On failure, S2 MUST NOT commit partial outputs.
   * On success, `shape_grid_definition_5A` and `class_zone_shape_5A` MUST both be present, schema-valid, and internally consistent.

---

### 6.2 Step 1 — Load S0 gate, sealed inputs & validate upstream

**Goal:** Ensure the world is sealed and upstream + S1 are ready.

**Inputs:**

* `parameter_hash`, `manifest_fingerprint`, `run_id`.
* `s0_gate_receipt_5A`, `sealed_inputs_5A`.
* `merchant_zone_profile_5A`.

**Procedure:**

1. Resolve `s0_gate_receipt_5A` and `sealed_inputs_5A` via the 5A dictionary/registry for this `manifest_fingerprint`.
2. Validate schemas and identity, as in S1:

   * `parameter_hash` and `manifest_fingerprint` match run context.
   * recomputed `sealed_inputs_digest` matches the value in the receipt.
3. Check upstream segment statuses in `verified_upstream_segments`:

   * require `"PASS"` for `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.
4. Resolve `merchant_zone_profile_5A` for this `parameter_hash` via dictionary/registry (note: S2 is parameter-pack/scenario scoped; S1’s output is still keyed by fingerprint but contains `parameter_hash`).
5. Validate that `merchant_zone_profile_5A`:

   * exists and is schema-valid;
   * has `parameter_hash` equal to run context;
   * covers expected domain (no duplicate `(merchant_id, legal_country_iso, tzid)`).

**Invariants:**

* If any of these checks fail, S2 MUST abort (e.g. `S2_GATE_OR_S1_INVALID`) and MUST NOT write outputs.
* On success, S2 may proceed.

---

### 6.3 Step 2 — Resolve time-grid & shape policies

**Goal:** Load configuration that defines the local-week grid and shape behaviour.

**Inputs (from `sealed_inputs_5A`):**

* Time-grid config, e.g. `shape_time_grid_policy_5A`.
* Shape policy artefacts, e.g. `shape_library_5A` and any supporting configs.
* Scenario metadata (if shapes are scenario-sensitive).

**Procedure:**

1. From `sealed_inputs_5A`, select rows with:

   * `owner_segment="5A"`,
   * `role in {"time_grid_config","policy","scenario_config"}`,
   * `status="REQUIRED"`.

2. Resolve time-grid config(s):

   * Load and validate against their schema (e.g. `#/policy/shape_time_grid`).
   * Extract:

     * `bucket_duration_minutes`,
     * `buckets_per_day`, `buckets_per_week = T_week`,
     * mapping rules for `(bucket_index → local_day_of_week, local_minutes_since_midnight)`,
     * any week-start conventions.

3. Resolve shape policy artefacts:

   * Load `shape_library_5A` and any auxiliary configs (class→template mapping tables, region/channel modifiers, etc.).
   * Validate against their schemas; verify they reference known `demand_class` labels and zone/channel groupings.

4. Resolve scenario metadata (if needed):

   * Read scenario configs, derive `scenario_id` and `scenario_type` for this `parameter_hash`.
   * If S2 is scenario-agnostic, treat `scenario_id` as a fixed baseline (still used for partitioning outputs).

**Invariants:**

* Missing or schema-invalid time-grid or shape policies MUST cause S2 to abort (`S2_REQUIRED_SHAPE_POLICY_MISSING` or similar).
* No RNG or data scanning occurs in this step.

---

### 6.4 Step 3 — Build time-grid rows (`shape_grid_definition_5A` in-memory)

**Goal:** Materialise the local-week time grid for `(parameter_hash, scenario_id)`.

**Inputs:**

* Time-grid config from Step 2.

**Procedure:**

1. Determine `T_week` from the policy (e.g. `buckets_per_day × 7`).

2. For each `bucket_index = 0..T_week-1`:

   * Compute `local_day_of_week` using policy rules (e.g. integer div / modulo based on `buckets_per_day` and week start).
   * Compute `local_minutes_since_midnight` (or equivalent hours/minutes representation) using `bucket_index mod buckets_per_day` and `bucket_duration_minutes`.
   * Set `bucket_duration_minutes` from policy.
   * Set identity fields:

     * `parameter_hash` (from run context),
     * `scenario_id` (from Step 2).

3. Build an in-memory collection `GRID_ROWS` of these rows.

4. Validate:

   * Coverage: `bucket_index` values are exactly the contiguous range `[0, T_week-1]`.
   * No duplicates or gaps.
   * All rows conform to `shape_grid_definition_5A` schema.

**Invariants:**

* Time grid is **fully determined** by policy and parameter pack; no data from S1/S0 is used to construct it.
* No randomness is used.

---

### 6.5 Step 4 — Discover S2 domain from S1 (`class×zone[×channel]`)

**Goal:** Determine the set of `(demand_class, zone[, channel])` combinations that need shapes.

**Inputs:**

* `merchant_zone_profile_5A` from S1.
* Optional shape-policy hints about domain (e.g. classes/zones allowed even if not currently populated).

**Procedure:**

1. Scan `merchant_zone_profile_5A` for this `parameter_hash` and fingerprint, retrieving at least:

   * `demand_class`,
   * `legal_country_iso`, `tzid` (or fields used to determine `zone_id`),
   * optional `channel` / `channel_group` (if S1 encodes it).

2. For each row, derive a zone representation for S2:

   * Either use `(legal_country_iso, tzid)` directly, **or**
   * compute a canonical `zone_id = f(legal_country_iso, tzid)` if the spec chose that representation.
   * This mapping MUST be deterministic and reversible, and MUST not change zone semantics.

3. Build an in-memory set:

   ```text
   DOMAIN_S1 = {
     (demand_class, zone[, channel]) | seen in merchant_zone_profile_5A
   }
   ```

4. Optionally merge with shape-policy hints:

   * If the shape policy declares extra class/zone combinations that should have predefined shapes even when not used yet, form:

     ```text
     DOMAIN_S2 = DOMAIN_S1 ∪ DOMAIN_policy
     ```

   * Otherwise, `DOMAIN_S2 = DOMAIN_S1`.

5. Validate:

   * Each `demand_class` in `DOMAIN_S2` is known to the shape policy.
   * Each zone representation is consistent with the time-grid assumptions (e.g. no invalid `tzid`).

**Invariants:**

* S2 MUST NOT use Layer-1 fact tables directly to expand the domain; only S1 + policy may define which classes/zones are in-scope.
* `merchant_id` MUST NOT appear in `DOMAIN_S2`.

---

### 6.6 Step 5 — Construct base shapes per `(demand_class, zone[, channel])`

**Goal:** For each domain element, construct an **unnormalised** local-week shape according to policy.

**Inputs:**

* `DOMAIN_S2` from Step 4.
* Time grid (`GRID_ROWS`), giving bucket indices and local-time semantics.
* Shape policies from Step 2 (templates, modifiers).

**Procedure:**

For each `(class, zone[, channel]) ∈ DOMAIN_S2`:

1. **Determine base template**

   * Use shape policy to select a template for this combination:

     * e.g. `template_id = select_template(demand_class, channel_group, zone_group, scenario_traits)`.
   * Template MUST be defined in policy; if not, S2 MUST either:

     * use a documented default template, or
     * treat this as configuration error (`S2_TEMPLATE_RESOLUTION_FAILED` in §9).

2. **Generate template shape over the grid**

   * For all `bucket_index` in `[0, T_week-1]`, compute an **unnormalised** value:

     ```text
     v(class, zone, k) ≥ 0
     ```

   * This may be done by:

     * evaluating parametric functions (e.g. Gaussians, step functions) over `local_day_of_week` / `local_minutes_since_midnight`,
     * using piecewise constants per DOW/time segment, etc., strictly following policy.

3. **Apply deterministic modifiers**

   * Apply any zone/channel modifiers defined in policy, e.g.:

     * weekend pattern adjustments for particular countries;
     * “night economy” adjustments;
     * slight tilt toward evenings for certain channels.

   * Resulting values `v'(class, zone, k)` MUST remain ≥ 0 (enforce non-negativity by policy rules).

4. Store the resulting unnormalised vector:

   ```text
   UNNORMALISED[class, zone[, channel], k] = v'(class, zone, k)
   ```

This step is **purely functional**: no shape depends on other classes/zones beyond what policy explicitly specifies.

---

### 6.7 Step 6 — Normalise shapes & validate per-class/zone

**Goal:** Convert unnormalised shapes into normalised weekly shapes (sum=1) and validate numerics.

**Inputs:**

* `UNNORMALISED[class, zone[, channel], k]`
* Time-grid (`GRID_ROWS`)

**Procedure:**

For each `(class, zone[, channel]) ∈ DOMAIN_S2`:

1. Compute the total mass:

   ```text
   total = Σ_{k=0..T_week-1} UNNORMALISED[class, zone, k]
   ```

2. Handle degenerate cases according to policy:

   * If `total > 0`:

     * define:

       ```text
       shape_value(class, zone, k) = UNNORMALISED[class, zone, k] / total
       ```

   * If `total == 0` (degenerate template):

     * The policy MUST define a deterministic fallback, e.g.:

       * use a simple flat shape: `shape_value = 1 / T_week` for all `k`, **or**
       * throw a configuration error if this template is not permitted to be flat.

     * S2 MUST NOT silently assign arbitrary shapes; any default fallback MUST be documented.

3. After normalisation, check:

   * `shape_value(class, zone, k) ≥ 0` for all k.
   * `Σ_k shape_value(class, zone, k)` is within tolerance of 1 (e.g. `|sum - 1| ≤ ε` with small ε defined in policy).

4. If any check fails, S2 MUST treat this as a configuration error (e.g. `S2_SHAPE_NORMALISATION_FAILED`) and abort without writing outputs.

5. Store the normalised values in an in-memory structure:

   ```text
   SHAPES[class, zone[, channel], k] = shape_value(class, zone, k)
   ```

---

### 6.8 Step 7 — Build `class_zone_shape_5A` & optional `class_shape_catalogue_5A`

**Goal:** Materialise the normalised shapes and optional template catalogue as row sets.

#### 6.8.1 Build `class_zone_shape_5A` rows

For each `(class, zone[, channel]) ∈ DOMAIN_S2` and each `bucket_index k`:

1. Create a row with:

   * Identity:

     * `parameter_hash` (from run context)
     * `scenario_id` (from Step 2)
   * Class/zone keys:

     * `demand_class = class`
     * zone representation (either `(legal_country_iso, tzid)` or `zone_id`), derived deterministically from S1 / zone policy
     * optional `channel` / `channel_group`
   * Time key:

     * `bucket_index = k`
   * Shape value:

     * `shape_value = SHAPES[class, zone, k]`
   * `s2_spec_version` set to the current S2 spec version.

2. Validate each row against `schemas.5A.yaml#/model/class_zone_shape_5A`.

3. Append to an in-memory collection `SHAPE_ROWS`.

After all rows are created:

* Check that for each `(parameter_hash, scenario_id, demand_class, zone[, channel])`, the sum of `shape_value` across its buckets is ~1 (sanity re-check).
* Check that PK constraints hold (no duplicates).

#### 6.8.2 Build `class_shape_catalogue_5A` rows (optional)

If the optional catalogue is implemented:

1. For each `(demand_class[, channel_group])` present in the shape policy:

   * Determine `template_id`, `template_type`, and `template_params` from policy.
   * Create a row:

     * `parameter_hash`, `scenario_id`
     * `demand_class`
     * optional `channel_group`
     * `template_id`, `template_type`, `template_params`
     * `policy_version` (if available)
     * `s2_spec_version`

2. Validate against `schemas.5A.yaml#/model/class_shape_catalogue_5A`.

3. Append to `CATALOGUE_ROWS`.

**Invariants:**

* `class_shape_catalogue_5A`, if present, MUST be consistent with `class_zone_shape_5A` (i.e. no template IDs that have no corresponding shapes, and no shapes whose templates are missing from the catalogue).

---

### 6.9 Step 8 — Atomic write & idempotency

**Goal:** Persist S2 outputs in an atomic, idempotent way.

**Inputs:**

* `GRID_ROWS`
* `SHAPE_ROWS`
* optional `CATALOGUE_ROWS`
* Dataset dictionary entries for S2 outputs.

**Procedure:**

1. **Resolve canonical paths**

   * Using the dictionary, compute canonical paths for:

     * `shape_grid_definition_5A` under `parameter_hash={parameter_hash}/scenario_id={scenario_id}`.
     * `class_zone_shape_5A` under the same partition.
     * `class_shape_catalogue_5A` if implemented.

2. **Check for existing outputs**

   * If any of these outputs already exist for `(parameter_hash, scenario_id)`:

     * Load them and compare to `GRID_ROWS`, `SHAPE_ROWS`, `CATALOGUE_ROWS` under a canonical ordering.
     * If all match byte-for-byte (or field-for-field under canonical serialisation), S2 MAY no-op (idempotent re-run).
     * If any differ, S2 MUST fail with `S2_OUTPUT_CONFLICT` and MUST NOT overwrite existing outputs.

3. **Write to staging**

   * Write `GRID_ROWS` to a staging file, e.g.:

     ```text
     .../shape_grid_definition/parameter_hash={parameter_hash}/scenario_id={scenario_id}/.staging/shape_grid_definition_5A.parquet
     ```

   * Write `SHAPE_ROWS` to a staging file under `.staging/` for `class_zone_shape_5A`.

   * If `CATALOGUE_ROWS` is present, write to a `.staging/` path for `class_shape_catalogue_5A`.

4. **Validate staged outputs (optional but strongly recommended)**

   * Re-read staged files and:

     * validate schemas,
     * verify PK constraints,
     * optionally re-check normalisation for a small sample of `(class, zone[, channel])`.

5. **Atomic commit**

   * Atomically rename/move the staged files into their canonical locations, ensuring:

     * `shape_grid_definition_5A` is committed before or with `class_zone_shape_5A`,
     * `class_shape_catalogue_5A` (if any) is committed last.

   * At no point should a consumer see `class_zone_shape_5A` without a matching `shape_grid_definition_5A`.

**Invariants:**

* On success, for each `(parameter_hash, scenario_id)`:

  * `shape_grid_definition_5A` and `class_zone_shape_5A` exist, are schema-valid, and satisfy all invariants.
  * `class_shape_catalogue_5A` either does not exist (if unused) or is fully consistent with shapes.

* On failure, no canonical S2 outputs MAY be partially written; staging artefacts MUST remain in `.staging/` or be cleaned up.

---

Within this algorithm, 5A.S2 acts as a **pure, deterministic template generator**: it uses S0/S1’s sealed world and 5A’s time-grid + shape policies to create a normalised weekly shape library per class/zone[/channel], ready for S3/S4 to scale and overlay.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how **identity** is represented for **5A.S2 — Weekly Shape Library**, how its datasets are **partitioned and addressed**, and what the **rewrite rules** are. All rules here are **binding**.

S2 outputs are **parameter-pack + scenario scoped templates**, not world-specific facts:

* They are keyed by `(parameter_hash, scenario_id)`.
* They do **not** depend on `manifest_fingerprint`, `seed`, or `run_id`.

---

### 7.1 Identity model

There are two identity layers to keep distinct:

1. **Run identity** (engine-level, ephemeral)

   * `parameter_hash` — identity of the parameter pack (includes shape policies, time-grid config, scenario config).
   * `manifest_fingerprint` — identity of the closed-world manifest used to *verify* inputs via S0.
   * `run_id` — identity of this particular execution of S2.

   These belong to the *execution* context.

2. **Dataset identity** (storage-level, persistent)

   * S2 outputs (`shape_grid_definition_5A`, `class_zone_shape_5A`, and optional `class_shape_catalogue_5A`) are keyed by **`(parameter_hash, scenario_id)` only**:

     * A given `(parameter_hash, scenario_id)` pair has at most one set of S2 outputs.
     * Multiple `manifest_fingerprint` values may reuse the same S2 outputs if they share the same parameter pack and scenario.

Binding rules:

* `manifest_fingerprint` and `run_id` MUST NOT appear as partition keys or part of S2 dataset primary keys.
* S2 outputs MUST be **identical** (byte-for-byte under canonical serialisation) for any two runs with the same `(parameter_hash, scenario_id)` and the same underlying parameter pack; otherwise, S2 MUST reject the attempt as an output conflict.

---

### 7.2 Partition law & path contracts

#### 7.2.1 Partition keys

All S2 outputs are partitioned by **parameter pack + scenario**:

* `shape_grid_definition_5A`:

  * `partition_keys: ["parameter_hash","scenario_id"]`

* `class_zone_shape_5A`:

  * `partition_keys: ["parameter_hash","scenario_id"]`

* `class_shape_catalogue_5A` (if implemented):

  * `partition_keys: ["parameter_hash","scenario_id"]`

No other partition key (e.g. `fingerprint`, `seed`, `run_id`) is allowed for S2 outputs.

#### 7.2.2 Path templates

Paths MUST follow the patterns declared in the dataset dictionary (illustrative but semantically binding):

* `shape_grid_definition_5A`:

  ```text
  data/layer2/5A/shape_grid_definition/
    parameter_hash={parameter_hash}/scenario_id={scenario_id}/shape_grid_definition_5A.parquet
  ```

* `class_zone_shape_5A`:

  ```text
  data/layer2/5A/class_zone_shape/
    parameter_hash={parameter_hash}/scenario_id={scenario_id}/class_zone_shape_5A.parquet
  ```

* `class_shape_catalogue_5A` (optional):

  ```text
  data/layer2/5A/class_shape_catalogue/
    parameter_hash={parameter_hash}/scenario_id={scenario_id}/class_shape_catalogue_5A.parquet
  ```

#### 7.2.3 Path ↔ embed equality

For every row in **all** S2 outputs:

* Embedded `parameter_hash` column:

  * MUST exist and be non-null.
  * MUST exactly equal the value used in the path token `parameter_hash={parameter_hash}`.

* Embedded `scenario_id` column:

  * MUST exist and be non-null.
  * MUST exactly equal the value used in `scenario_id={scenario_id}`.

Any mismatch between:

* path tokens and embedded `parameter_hash` / `scenario_id`, or
* embedded `parameter_hash` and the S2 run context

MUST be treated as a hard validation error; such outputs MUST NOT be considered valid.

---

### 7.3 Primary keys & logical ordering

#### 7.3.1 Primary keys

Primary keys for S2 modelling tables are **binding**:

* **`shape_grid_definition_5A`**

  ```yaml
  primary_key:
    - parameter_hash
    - scenario_id
    - bucket_index
  ```

  Constraints:

  * For each `(parameter_hash, scenario_id)`, `bucket_index` MUST cover the contiguous range `[0, T_week-1]` with no gaps or duplicates.

* **`class_zone_shape_5A`**

  If using explicit `(legal_country_iso, tzid)`:

  ```yaml
  primary_key:
    - parameter_hash
    - scenario_id
    - demand_class
    - legal_country_iso
    - tzid
    - bucket_index
  ```

  If using `zone_id`:

  ```yaml
  primary_key:
    - parameter_hash
    - scenario_id
    - demand_class
    - zone_id
    - bucket_index
  ```

  Constraints:

  * For each `(parameter_hash, scenario_id, demand_class, zone[, channel])`, there MUST be exactly one row per `bucket_index` in `[0, T_week-1]`.
  * No duplicate PK tuples are allowed.

* **`class_shape_catalogue_5A`** (if implemented)

  ```yaml
  primary_key:
    - parameter_hash
    - scenario_id
    - demand_class         # and channel_group if schema so defines
  ```

  Constraints:

  * At most one catalogue row per `(parameter_hash, scenario_id, demand_class[, channel_group])`.

Violations of PK uniqueness MUST cause S2 to treat the state as failed for that `(parameter_hash, scenario_id)`.

#### 7.3.2 Logical ordering

Physical ordering is not semantically significant, but S2 MUST impose a deterministic writer order for reproducibility and stable diffing:

* `shape_grid_definition_5A`:

  * sorted by `bucket_index` (and by `scenario_id`, `parameter_hash` if multiple partitions are written in a single file — usually they aren’t).

* `class_zone_shape_5A`:

  * sorted by `(demand_class, zone_representation, bucket_index)`, where `zone_representation` is `(legal_country_iso, tzid)` or `zone_id` according to the spec.

* `class_shape_catalogue_5A` (if present):

  * sorted by `(demand_class[, channel_group])`.

Consumers MUST NOT rely on any particular ordering beyond PK semantics; ordering exists only to ensure stable file content and diagnostics.

---

### 7.4 Merge discipline & rewrite semantics

S2 follows a **single-writer, no-merge** discipline per `(parameter_hash, scenario_id)`.

Binding rules:

1. **No in-place merges or appends**

   For any fixed `(parameter_hash, scenario_id)`, S2 MUST NOT:

   * append new rows to existing S2 outputs,
   * partially overwrite subsets of rows, or
   * perform row-level merges.

   Outputs are conceptually **atomic** templates for that parameter pack + scenario.

2. **Idempotent re-runs allowed**

   * If, for a given `(parameter_hash, scenario_id)`, S2 is re-run and existing outputs are present, the implementation MUST:

     * recompute `GRID_ROWS`, `SHAPE_ROWS`, and (if present) `CATALOGUE_ROWS` in memory;
     * compare them to existing files under canonical ordering and serialisation.

   * If and only if these are **byte-identical** (or field-identical under the agreed serialisation), S2 MAY:

     * log that outputs are already up-to-date, and
     * exit without writing (idempotent no-op).

3. **Conflicting rewrites forbidden**

   * If existing S2 outputs for `(parameter_hash, scenario_id)` differ in any way from what S2 would now compute — extra/missing rows, different shape values, different grid structure, etc. — S2 MUST:

     * fail with a canonical output conflict error (e.g. `S2_OUTPUT_CONFLICT`), and
     * MUST NOT overwrite or merge the existing outputs.

   * Any legitimate change to:

     * time grid definition,
     * shape policy semantics, or
     * class/zone domain coverage

     MUST be represented by a new **`parameter_hash`** (and, if relevant, scenario configuration) rather than by mutating the S2 outputs under the same `(parameter_hash, scenario_id)`.

4. **No cross-parameter or cross-scenario merging**

   * S2 MUST NOT merge data across different `parameter_hash` values or `scenario_id`s.
   * Each `(parameter_hash, scenario_id)` partition is self-contained and independent.

---

### 7.5 Interaction with other identity dimensions

#### 7.5.1 `manifest_fingerprint`

* `manifest_fingerprint`:

  * is part of the **run context**, used by S0/S1 to validate upstream artefacts;
  * MUST NOT appear in S2’s partition keys or S2 primary keys;
  * MUST NOT be embedded as an identity column in S2 outputs.

Multiple different `manifest_fingerprint` values (different “worlds”) may safely share the same S2 outputs as long as they share the same `parameter_hash` and `scenario_id`.

#### 7.5.2 `seed` and `run_id`

* `seed`:

  * MUST NOT be used as a partition key or column in S2 outputs; S2 contains no RNG and does not depend on a seed.

* `run_id`:

  * MUST NOT be a partition key or column in S2 outputs.
  * It appears only in logs/run-report/tracing.

Any use of `seed` or `run_id` in S2 data schemas is a spec violation.

---

### 7.6 Cross-segment identity alignment

S2 outputs must align with S1 and 3A in the following ways:

1. **Alignment with S1 (`merchant_zone_profile_5A`)**

   * For every `(parameter_hash, scenario_id, demand_class, zone[, channel])` in S2’s domain:

     * There MUST exist at least one merchant×zone row in `merchant_zone_profile_5A` (for some fingerprint) with the same `parameter_hash` and `demand_class` and zone representation.

   * Conversely, for any `(parameter_hash, demand_class, zone[, channel])` actually used in `merchant_zone_profile_5A` for a world under this parameter pack and scenario, S2 MUST produce a shape in `class_zone_shape_5A`.

   Practically:

   * S2 domain `DOMAIN_S2` MUST be a superset of `DOMAIN_S1` (the set of class/zone combos seen in S1), possibly augmented by policy-declared domain extensions.

2. **Alignment with 3A (`zone_alloc`)**

   * Zone identifiers used in S2 (`legal_country_iso` + `tzid` or `zone_id`) MUST correspond to zones coming from 3A’s zone universe.

   * There MUST exist a deterministic mapping:

     ```text
     zone_representation(S2)  ↔  (legal_country_iso, tzid) in 3A
     ```

   * S2 MUST NOT invent zone values that have no counterpart in 3A.

3. **Alignment with time grid**

   * All `bucket_index` values present in `class_zone_shape_5A` MUST appear in `shape_grid_definition_5A` for the same `(parameter_hash, scenario_id)`.

   * Both datasets must share the same `bucket_duration_minutes` and `T_week` implied by `shape_grid_definition_5A`.

If any of these alignments fail (e.g. shapes for a `demand_class` or `zone` not present in S1/3A, or bucket indices not present in the grid), S2 MUST treat the state as failed for that `(parameter_hash, scenario_id)` and MUST NOT consider outputs valid.

---

Within these constraints, 5A.S2’s identity, partitions, ordering, and merge discipline are fully specified: each `(parameter_hash, scenario_id)` yields a single, immutable local-week shape grid and class/zone shape library, reusable across worlds, with no cross-run merging and only idempotent re-runs allowed.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 5A.S2 — Weekly Shape Library is green** for a given `(parameter_hash, scenario_id)` and the **hard preconditions** it imposes on downstream states. All rules here are **binding**.

---

### 8.1 Conditions for 5A.S2 to “PASS”

For a given `(parameter_hash, scenario_id)` (and underlying `manifest_fingerprint` used for validation), 5A.S2 is considered **successful** only if **all** of the following hold:

#### 8.1.1 S0 and S1 are valid and aligned

1. **Valid S0 gate & sealed inputs**

   * `s0_gate_receipt_5A` and `sealed_inputs_5A` for the relevant `manifest_fingerprint`:

     * exist and are discoverable via the catalogue,
     * are schema-valid,
     * have `parameter_hash == parameter_hash`, and
     * have a recomputed `sealed_inputs_digest` that matches the receipt.

2. **Upstream segments are green**

   * In `s0_gate_receipt_5A.verified_upstream_segments`, each of:

     * `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
       MUST have `status="PASS"`.

3. **S1 output present and valid**

   * `merchant_zone_profile_5A`:

     * exists for the target `(parameter_hash, manifest_fingerprint)`,
     * is schema-valid (`#/model/merchant_zone_profile_5A`),
     * has `parameter_hash == parameter_hash`,
     * has a unique `(merchant_id, legal_country_iso, tzid)` per row.

If any of these fail, S2 MUST NOT be treated as green, regardless of its own outputs.

---

#### 8.1.2 Required S2 configs & policies are present

4. **Time-grid configuration ready**

   * At least one artefact that defines the local-week time grid (e.g. `shape_time_grid_policy_5A`) is present in `sealed_inputs_5A` with:

     * `owner_segment="5A"`,
     * `status="REQUIRED"`,
     * valid `schema_ref` and `read_scope`.

5. **Shape library policies ready**

   * Shape policy artefacts (e.g. `shape_library_5A` and supporting tables) are present in `sealed_inputs_5A` with:

     * `owner_segment="5A"`,
     * `status="REQUIRED"`,
     * valid `schema_ref` and `read_scope`.

   * They reference only known `demand_class` labels and zone/channel groupings.

6. **Scenario metadata (if shapes are scenario-sensitive)**

   * Scenario config artefacts are present in `sealed_inputs_5A` and provide a well-defined `scenario_id` used in S2’s partitioning.

If any required config/policy is missing or schema-invalid, S2 MUST fail and MUST NOT publish outputs.

---

#### 8.1.3 Time grid (`shape_grid_definition_5A`) is correct

7. **Dataset exists & schema-valid**

   * `shape_grid_definition_5A` exists for `(parameter_hash, scenario_id)` and:

     * conforms to `#/model/shape_grid_definition_5A`,
     * has `partition_keys: ["parameter_hash","scenario_id"]`,
     * has `primary_key: ["parameter_hash","scenario_id","bucket_index"]`.

8. **Coverage & contiguity**

   * For this `(parameter_hash, scenario_id)`, buckets cover a contiguous range:

     ```text
     bucket_index ∈ [0, T_week-1]  with no gaps or duplicates
     ```

   * `T_week` is consistent with the time-grid policy (e.g. `buckets_per_day × 7`).

9. **Local-time mapping consistency**

   * For each row, `local_day_of_week`, `local_minutes_since_midnight`, and `bucket_duration_minutes` are:

     * non-null,
     * consistent with `bucket_index` and the time-grid policy, and
     * within valid ranges (e.g. day-of-week in [1..7], minutes in [0..1440)).

---

#### 8.1.4 Shape library (`class_zone_shape_5A`) is correct

Let:

* `DOMAIN_S1` = set of `(demand_class, zone[, channel])` combinations derived from `merchant_zone_profile_5A` under this `parameter_hash`.
* `DOMAIN_policy` = any additional class/zone combos the shape policy declares as in-scope even if not currently used.
* `DOMAIN_S2 = DOMAIN_S1 ∪ DOMAIN_policy` as constructed in §6.5.

10. **Dataset exists & schema-valid**

* `class_zone_shape_5A` exists for `(parameter_hash, scenario_id)` and:

  * conforms to `#/model/class_zone_shape_5A`,
  * has `partition_keys: ["parameter_hash","scenario_id"]`,
  * has the declared primary key (either with `(legal_country_iso, tzid)` or `zone_id`).

11. **Domain alignment**

* For every `(demand_class, zone[, channel]) ∈ DOMAIN_S2`, there is a full set of rows in `class_zone_shape_5A` with `bucket_index` in `[0..T_week-1]`.
* No `(demand_class, zone[, channel])` appears in `class_zone_shape_5A` if it is not in `DOMAIN_S2`.
* Each `(parameter_hash, scenario_id, demand_class, zone[, channel], bucket_index)` appears at most once.

12. **Non-negativity and normalisation**

* For each fixed `(parameter_hash, scenario_id, demand_class, zone[, channel])`:

  * `shape_value ≥ 0` for every bucket.
  * The sum across all buckets satisfies:

    ```text
    | Σ_k shape_value - 1 | ≤ ε
    ```

    where ε is a small tolerance defined in policy.

* No `shape_value` is NaN or ±Inf.

13. **Time-grid consistency**

* Every `bucket_index` in `class_zone_shape_5A` appears in `shape_grid_definition_5A` for the same `(parameter_hash, scenario_id)`.
* No out-of-range `bucket_index` values occur.

---

#### 8.1.5 Optional catalogue (`class_shape_catalogue_5A`) is consistent (if used)

14. **Dataset validity**

* If `class_shape_catalogue_5A` is implemented:

  * it exists and conforms to `#/model/class_shape_catalogue_5A`,
  * has `partition_keys: ["parameter_hash","scenario_id"]`,
  * has `primary_key` as defined (e.g. `[parameter_hash, scenario_id, demand_class]`).

15. **Consistency with shapes**

* For each `demand_class` (and optional `channel_group`) in `class_shape_catalogue_5A`:

  * there exists at least one corresponding `(demand_class, zone[, channel])` in `class_zone_shape_5A` or in `DOMAIN_S2`.
* No `template_id` is declared for a class that has no shapes, unless explicitly allowed as “unused template” in policy.

---

#### 8.1.6 Output integrity & idempotence

16. **Atomicity**

* For each `(parameter_hash, scenario_id)`:

  * either both required datasets (`shape_grid_definition_5A`, `class_zone_shape_5A`) exist and satisfy all invariants, or
  * neither is considered published / valid (no partially-written outputs).

17. **Consistency with previous runs**

* If S2 outputs already existed for the same `(parameter_hash, scenario_id)`:

  * recomputing the outputs must yield byte-identical content; otherwise S2 must have failed with an output-conflict and not written anything.

If any of these conditions fail, S2 MUST treat the state as **FAILED** for this `(parameter_hash, scenario_id)` and its outputs MUST NOT be considered valid.

---

### 8.2 Minimal content requirements

Even if structural checks pass, S2 MUST enforce the following **content minima**:

1. **Non-empty time grid**

   * `shape_grid_definition_5A` MUST contain at least one bucket (`T_week ≥ 1`).
   * For normal operation, `T_week` SHOULD correspond to at least one full 24-hour day (and typically a full 7-day week), but that’s policy-level.

2. **Non-empty domain**

   * If `DOMAIN_S1` (class/zone domain from S1) is non-empty, then `class_zone_shape_5A` MUST contain at least one shape.
   * An entirely empty `class_zone_shape_5A` is acceptable only if:

     * `DOMAIN_S1` is empty *and* the shape policy explicitly allows an empty domain for this parameter pack,
     * and this case is clearly logged.

3. **Class coverage**

   * For every `demand_class` present in `merchant_zone_profile_5A`, there MUST be at least one corresponding class/zone shape in `class_zone_shape_5A`; if policies intend to “ignore” some classes, that MUST be explicitly documented and reflected in `DOMAIN_S2`.

---

### 8.3 Gating obligations on downstream 5A states (S3–S4)

5A.S3–S4 (and any other 5A states that consume shapes) MUST obey the following gates:

1. **Require valid S0, S1, and S2**

   Before constructing merchant-level intensities or calendar overlays, a downstream 5A state MUST:

   * validate S0 gate (`s0_gate_receipt_5A`, `sealed_inputs_5A`) as in the S0 spec;
   * validate S1 output (`merchant_zone_profile_5A`) as in the S1 spec;
   * validate S2 outputs (`shape_grid_definition_5A` and `class_zone_shape_5A`) as per this section, ensuring that:

     * they exist for the target `(parameter_hash, scenario_id)`,
     * they are schema-valid,
     * they pass normalisation and domain alignment checks.

2. **Use S2 as sole weekly-shape authority**

   * S3/S4 MUST treat `class_zone_shape_5A` (and its grid) as the **only** source of weekly local-time shape templates.
   * They MUST NOT:

     * introduce independent class/zone shapes,
     * reimplement shape policies, or
     * adjust shapes in ways that contradict S2.

   Any shape tweaks must either be:

   * explicitly defined in S3/S4 as higher-level transforms on top of S2, or
   * encoded via a new parameter pack and re-run of S2.

3. **Domain behaviour**

   * If a `(demand_class, zone[, channel])` exists in S1 but not in S2, downstream states MUST treat this as a configuration error and fail, not silently assume a flat shape.
   * Conversely, shapes present in S2 for classes/zones never used in S1 MAY be ignored by S3/S4 unless explicitly needed.

---

### 8.4 Gating obligations on other segments (5B, 6A)

Other segments that rely on class/zone weekly patterns (e.g. 5B, 6A) MUST:

1. **Check 5A segment-level PASS**

   * Require a verified `_passed.flag` (produced by the 5A validation state) for the relevant `manifest_fingerprint`, which implies S0–S2 (and other 5A states) are green.

2. **Respect S2’s role**

   * Whenever they need class/zone weekly patterns (e.g. for monitoring, or as part of synthetic labelling logic), they MUST:

     * read `shape_grid_definition_5A` + `class_zone_shape_5A` via the dictionary/registry,
     * obey the same partitioning and identity rules,
     * avoid adding separate logic that conflicts with S2.

They MUST NOT rely on any stale or alternative notion of weekly patterns that bypasses S2’s outputs.

---

### 8.5 When 5A.S2 MUST fail

Regardless of catalogue state, 5A.S2 MUST treat itself as **failed** for a given `(parameter_hash, scenario_id)` and MUST NOT publish or update outputs if any of the following occur:

* **S0/S1 gating failure**

  * `s0_gate_receipt_5A` / `sealed_inputs_5A` invalid or mismatched (`S2_GATE_OR_S1_INVALID`-class issues).
  * S1 output missing or invalid (`merchant_zone_profile_5A` absent or schema-invalid).
  * Any upstream segment (1A–3B) not `PASS`.

* **Required configs/policies missing**

  * Time-grid policy or shape policy artefacts missing from `sealed_inputs_5A` (`S2_REQUIRED_SHAPE_POLICY_MISSING`-class).
  * Scenario metadata missing when S2 is scenario-sensitive.

* **Time-grid inconsistencies**

  * `shape_grid_definition_5A` cannot be constructed or validated from the time-grid policy (`S2_TIME_GRID_INVALID`-class error).

* **Domain or FK misalignment**

  * `class_zone_shape_5A` domain does not align with `DOMAIN_S2` (missing shapes for required combos, extra shapes for invalid combos).
  * Zone identifiers cannot be mapped to 3A’s zone universe.

* **Shape normalisation or numeric failures**

  * Any `shape_value` is negative, NaN, or Inf.
  * Sum of `shape_value` over buckets for any `(class, zone[, channel])` deviates from 1 beyond tolerance (`S2_SHAPE_NORMALISATION_FAILED`-class).

* **Output conflict**

  * Existing S2 outputs for `(parameter_hash, scenario_id)` differ from recomputed ones (`S2_OUTPUT_CONFLICT`).

* **I/O failures**

  * `S2_IO_READ_FAILED` or `S2_IO_WRITE_FAILED` scenarios while reading required inputs or committing outputs.

* **Internal invariant violations**

  * `S2_INTERNAL_INVARIANT_VIOLATION` cases (e.g. duplicate PKs after de-duplication, impossible branch conditions).

In all such cases, S2 MUST:

* abort without publishing or altering canonical S2 outputs,
* surface the appropriate canonical error code (via run-report/logs), and
* rely on operators (or configuration changes / new parameter packs) to correct the issue before S2 is run again.

Within these rules, S2 has a crisp notion of “green”: the world is sealed, upstream and S1 are PASS, the time grid and shape policies are well-defined, and S2 produces a complete, normalised, and domain-aligned weekly shape library for every class/zone[/channel] in scope.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error codes** that **5A.S2 — Weekly Shape Library** MAY emit, and the exact conditions under which they MUST be raised. These codes are **binding**: implementations MUST either use them directly or maintain a 1:1 mapping.

S2 errors are about **S2 itself** failing to produce a valid time grid and class/zone shape library for a given `(parameter_hash, scenario_id)`. They are distinct from upstream statuses recorded in `s0_gate_receipt_5A` or from S1’s own errors.

---

### 9.1 Error reporting contract

5A.S2 MUST surface failures through:

* the engine’s **run-report** (per-run summary), and
* structured logs / metrics.

Each failure record MUST include at least:

* `segment_id = "5A.S2"`
* `parameter_hash`
* `scenario_id`
* `manifest_fingerprint` (the S0/S1 world used for validation)
* `run_id`
* `error_code` — one of the canonical codes below
* `severity` — `FATAL` for all S2 errors defined here
* `message` — short human-readable summary
* `details` — optional structured context (e.g. offending `demand_class`, `zone`, `bucket_index`)

There is no dedicated S2 error dataset; S2 uses the same run-report/logging machinery as other states.

---

### 9.2 Canonical error codes (summary)

| Code                               | Severity | Category                                |
| ---------------------------------- | -------- | --------------------------------------- |
| `S2_GATE_OR_S1_INVALID`            | FATAL    | S0/S1 gate & alignment                  |
| `S2_UPSTREAM_NOT_PASS`             | FATAL    | Upstream segment status (1A–3B)         |
| `S2_REQUIRED_INPUT_MISSING`        | FATAL    | Missing required S1/5A inputs           |
| `S2_REQUIRED_SHAPE_POLICY_MISSING` | FATAL    | Missing time-grid/shape policies        |
| `S2_TIME_GRID_INVALID`             | FATAL    | Invalid or inconsistent time grid       |
| `S2_TEMPLATE_RESOLUTION_FAILED`    | FATAL    | Could not resolve base template         |
| `S2_DOMAIN_ALIGNMENT_FAILED`       | FATAL    | Class/zone domain mismatch              |
| `S2_SHAPE_NORMALISATION_FAILED`    | FATAL    | Negative / NaN / non-normalised         |
| `S2_OUTPUT_CONFLICT`               | FATAL    | Existing outputs differ from recomputed |
| `S2_IO_READ_FAILED`                | FATAL    | I/O / storage read error                |
| `S2_IO_WRITE_FAILED`               | FATAL    | I/O / storage write/commit error        |
| `S2_INTERNAL_INVARIANT_VIOLATION`  | FATAL    | “Should never happen” guard             |

All are **stop-the-world** for S2: if any occurs, S2 MUST NOT publish or modify canonical outputs for that `(parameter_hash, scenario_id)`.

---

### 9.3 Code-by-code definitions

#### 9.3.1 `S2_GATE_OR_S1_INVALID` *(FATAL)*

**Trigger**

Raised when S2 cannot validate that S0 and S1 are both correctly established for this run, for example:

* `s0_gate_receipt_5A` or `sealed_inputs_5A`:

  * missing for the relevant `manifest_fingerprint`, or
  * schema-invalid, or
  * `parameter_hash` in the receipt does not equal the run’s `parameter_hash`, or
  * recomputed `sealed_inputs_digest` from `sealed_inputs_5A` does not match the receipt.

* `merchant_zone_profile_5A`:

  * missing for this `parameter_hash` and `manifest_fingerprint`, or
  * schema-invalid, or
  * has inconsistent `parameter_hash` / `manifest_fingerprint`, or
  * violates its own PK constraints (duplicate `(merchant_id, legal_country_iso, tzid)`).

Detected in Steps 1–2 of the S2 algorithm.

**Effect**

* S2 MUST abort immediately.
* No `shape_grid_definition_5A`, `class_zone_shape_5A` or `class_shape_catalogue_5A` MAY be written or updated.
* Downstream 5A states (S3–S4) MUST NOT be invoked for this `(parameter_hash, scenario_id)` until S0 and S1 are fixed and re-run.

---

#### 9.3.2 `S2_UPSTREAM_NOT_PASS` *(FATAL)*

**Trigger**

Raised when upstream Layer-1 segments are not all `"PASS"` according to S0:

* Any of `1A`, `1B`, `2A`, `2B`, `3A`, `3B` has `status="FAIL"` or `status="MISSING"` in `s0_gate_receipt_5A.verified_upstream_segments`.

This is a more precise refinement of “S0 gate is valid but says upstream is not green”.

**Effect**

* S2 MUST abort and MUST NOT read upstream feature datasets (even if present).
* No S2 outputs MAY be written.
* Operator must resolve upstream segment issues and re-run S0/S1/S2.

---

#### 9.3.3 `S2_REQUIRED_INPUT_MISSING` *(FATAL)*

**Trigger**

Raised when a **required sealed artefact** for S2 cannot be resolved or is unusable, for example:

* `merchant_zone_profile_5A` is absent from `sealed_inputs_5A`, mis-typed, or has an incompatible `read_scope`.
* Required scenario metadata (if S2 is scenario-aware) is missing or invalid.

This is about S1/5A **data artefacts**, not policies (those have their own code).

**Effect**

* S2 MUST abort before constructing any time grid or shapes.
* No S2 outputs MAY be written.
* Operator must ensure that all required datasets for S2 are declared in the dictionary/registry, appear in `sealed_inputs_5A`, and are accessible, then re-run S0/S1/S2.

---

#### 9.3.4 `S2_REQUIRED_SHAPE_POLICY_MISSING` *(FATAL)*

**Trigger**

Raised when **time-grid or shape policies** required for S2 are missing or unusable, for example:

* No `shape_time_grid_policy_5A` (or equivalent) in `sealed_inputs_5A`, or its `schema_ref` is invalid.
* `shape_library_5A` or required supporting configs are missing or fail schema validation.
* `read_scope` prevents S2 from reading the policy contents (e.g. erroneously marked `METADATA_ONLY` for a config that must be read).

Detected in Step 2 (§6.3).

**Effect**

* S2 MUST abort and MUST NOT attempt to construct a time grid or shapes.
* No S2 outputs MAY be written.
* Operator must fix policy deployment / parameter pack and re-run S2.

---

#### 9.3.5 `S2_TIME_GRID_INVALID` *(FATAL)*

**Trigger**

Raised when S2 cannot construct a valid local-week time grid from the time-grid configuration, for example:

* The implied `T_week` is ≤ 0 or not an integer.
* Derived `bucket_index` range is non-contiguous, misaligned, or incompatible with the declared `buckets_per_day` and `bucket_duration_minutes`.
* Mapping from `bucket_index` to `(local_day_of_week, local_minutes_since_midnight)` produces out-of-range values (e.g. day-of-week outside allowed range, minutes <0 or ≥ 1440).

Detected in Step 3 (§6.4) while building `shape_grid_definition_5A`.

**Effect**

* S2 MUST abort and MUST NOT publish any outputs.
* Operator must correct the time-grid policy (or parameter pack) and re-run S2.

---

#### 9.3.6 `S2_TEMPLATE_RESOLUTION_FAILED` *(FATAL)*

**Trigger**

Raised when S2 cannot resolve a coherent base template for at least one `(demand_class, zone[, channel])` in `DOMAIN_S2`, for example:

* `shape_library_5A` has no entry for a `demand_class` that appears in `DOMAIN_S2`, and no default template is defined.
* Policy rules conflict, yielding multiple templates for the same `(class, zone[, channel])` when only one is allowed.
* Referenced `template_id` or template parameters are missing or inconsistent with the template schema.

Detected in Step 5 (§6.6) while selecting and parameterising templates.

**Effect**

* S2 MUST abort and MUST NOT commit outputs.
* `error_details` SHOULD identify the affected `demand_class`, zone, and (if relevant) `channel`.
* Fix requires updating shape policies and/or class definitions so every domain element has a unique, well-defined template.

---

#### 9.3.7 `S2_DOMAIN_ALIGNMENT_FAILED` *(FATAL)*

**Trigger**

Raised when S2 detects a mismatch between the intended domain `DOMAIN_S2` and the actual `class_zone_shape_5A` coverage, for example:

* Missing shapes:

  * at least one `(demand_class, zone[, channel])` in `DOMAIN_S2` has no full set of bucket rows in `class_zone_shape_5A`.

* Extra shapes:

  * shapes exist in `class_zone_shape_5A` for `(demand_class, zone[, channel])` that are not present in `DOMAIN_S2` (i.e. not seen in S1 nor declared in shape policy).

* FK misalignment:

  * zone identifiers in `class_zone_shape_5A` cannot be mapped back to a valid 3A zone (e.g. unknown `tzid` or malformed `zone_id`).

Detected in domain checks around Steps 6–8.

**Effect**

* S2 MUST treat the state as failed for this `(parameter_hash, scenario_id)`.
* No S2 outputs MAY be considered valid; if written to staging, they MUST NOT be moved to canonical paths.
* Operator must fix either domain derivation (S1 / policy) or the S2 implementation.

---

#### 9.3.8 `S2_SHAPE_NORMALISATION_FAILED` *(FATAL)*

**Trigger**

Raised when S2 fails to produce valid, normalised shapes for at least one `(demand_class, zone[, channel])`, for example:

* After normalisation:

  * some `shape_value` are negative, NaN, or ±Inf.
  * the sum of `shape_value` for a given `(class, zone[, channel])` differs from 1 by more than the allowed tolerance ε.

* `total` mass (sum of unnormalised values) is zero and:

  * no valid fallback is defined by policy, or
  * fallback would violate invariants (e.g. produce negative values).

Detected in Step 6 (§6.7).

**Effect**

* S2 MUST abort and MUST NOT commit outputs.
* `error_details` SHOULD include the affected `(demand_class, zone[, channel])` and, if useful, summary of unnormalised totals.
* Fix typically requires adjusting shape policy parameters or fallback rules.

---

#### 9.3.9 `S2_OUTPUT_CONFLICT` *(FATAL)*

**Trigger**

Raised when outputs already exist for `(parameter_hash, scenario_id)` and differ from what S2 would now compute, for example:

* Existing `shape_grid_definition_5A` for this `(parameter_hash, scenario_id)` has different `T_week` or `bucket_index` mapping than recomputed.
* Existing `class_zone_shape_5A` has different shape values, domain coverage, or PK sets than recomputed `SHAPE_ROWS`.
* Existing `class_shape_catalogue_5A` (if present) is inconsistent with recomputed catalogue rows.

Detected in Step 8 (§6.9) when comparing recomputed outputs with existing ones.

**Effect**

* S2 MUST NOT overwrite existing outputs.
* S2 MUST abort and log `S2_OUTPUT_CONFLICT`.
* Resolution generally requires:

  * minting a new `parameter_hash` (reflecting new policies/configs), and
  * re-running S2 under the new parameter pack, rather than mutating outputs under the old identity.

---

#### 9.3.10 `S2_IO_READ_FAILED` *(FATAL)*

**Trigger**

Raised when S2 encounters I/O or storage failures while reading **required** inputs, for example:

* Storage or permissions errors reading:

  * `s0_gate_receipt_5A` / `sealed_inputs_5A`,
  * `merchant_zone_profile_5A`,
  * time-grid policies or shape libraries.

This code is for genuine I/O/storage problems, not for logical absence (which is `S2_REQUIRED_INPUT_MISSING` / `S2_REQUIRED_SHAPE_POLICY_MISSING`).

**Effect**

* S2 MUST abort; no outputs MAY be written or changed.
* Operator must resolve storage/network/permissions issues and re-run S2.

---

#### 9.3.11 `S2_IO_WRITE_FAILED` *(FATAL)*

**Trigger**

Raised when S2 fails during writing or committing its outputs, for example:

* Cannot write staging files for `shape_grid_definition_5A` or `class_zone_shape_5A`.
* Failure to atomically move staged files to canonical paths.

**Effect**

* S2 MUST treat the state as failed for this `(parameter_hash, scenario_id)`.
* Any partially written staging artefacts MUST remain in `.staging/` locations that consumers ignore, or be cleaned up; canonical paths MUST not show partially written data.
* Operator must fix underlying storage issues and re-run S2.

---

#### 9.3.12 `S2_INTERNAL_INVARIANT_VIOLATION` *(FATAL)*

**Trigger**

Catch-all for impossible or internal-error states that cannot be expressed as a more specific code, for example:

* Duplicated PKs in-memory after explicit de-duplication.
* Inconsistent `T_week` values derived from the same time-grid config.
* Control paths that should be unreachable according to the algorithm (e.g. empty `DOMAIN_S2` when policy declares it must be non-empty).

**Effect**

* S2 MUST abort and MUST NOT publish outputs.
* `error_details` SHOULD include which invariant was violated and relevant context (e.g. class/zone identifiers, grid parameters).
* This usually indicates a bug in the S2 implementation or deployment, not in data/policies.

---

### 9.4 Relationship to upstream statuses

To avoid confusion:

* **Upstream statuses** (`"PASS" / "FAIL" / "MISSING"`) for 1A–3B live in `s0_gate_receipt_5A.verified_upstream_segments`.
* S2 uses these statuses to decide whether it may proceed; any non-PASS status yields `S2_UPSTREAM_NOT_PASS`.

S2 MUST NOT:

* reinterpret S1 or upstream segment statuses;
* hide upstream problems by “falling back” to alternative shapes.

Downstream states (S3–S4, 5B, 6A) MUST:

* consult S2’s run-report/logs (and eventually the 5A validation bundle) to understand **why** shapes are missing or invalid for a given parameter pack, using these canonical error codes as the vocabulary.

Within this framework, every failure mode for 5A.S2 has a clear, named error code, well-defined triggers, and a clear operator action, so that the shape library either exists and is trustworthy — or is clearly marked as failed and unusable.

---

## 10. Observability & run-report integration *(Binding)*

This section defines how **5A.S2 — Weekly Shape Library** MUST report its activity into the engine’s **run-report**, logging and metrics systems. These requirements are **binding**.

S2 is deterministic and template-only; observability MUST focus on:

* **which parameter pack + scenario** was processed,
* **what domain and grid** were produced, and
* **whether shapes are numerically sane**,

without logging individual shape vectors in detail.

---

### 10.1 Objectives

Observability for 5A.S2 MUST allow operators and downstream segments to answer:

1. **Did S2 run for this parameter pack + scenario?**

   * For `(parameter_hash, scenario_id, manifest_fingerprint, run_id)` — did S2 start, succeed, or fail?

2. **If it failed, why?**

   * Which canonical error code (from §9)?
   * Was it S0/S1, upstream status, missing config, domain mismatch, or shape normalisation?

3. **If it succeeded, what did it produce?**

   * How many buckets in the local-week grid?
   * How many `(demand_class, zone[, channel])` shapes?
   * Basic sanity of shape values (non-negative, normalised).

All without logging full arrays of `shape_value` per class/zone.

---

### 10.2 Run-report entries

For **every invocation** of 5A.S2, the engine’s run-report MUST contain a structured record with at least:

* `segment_id = "5A.S2"`
* `parameter_hash`
* `scenario_id`
* `manifest_fingerprint` (used for S0/S1 gating)
* `run_id`
* `state_status ∈ {"STARTED","SUCCESS","FAILED"}`
* `start_utc`, `end_utc` (UTC timestamps)
* `duration_ms`

On **SUCCESS**, the run-report for S2 MUST additionally include:

* **Grid summary**

  * `shape_grid_buckets_per_week` (i.e. `T_week`).
  * `shape_grid_bucket_duration_minutes`.
  * Optional: `shape_grid_buckets_per_day`.

* **Domain summary**

  * `s2_domain_num_classes` — count of distinct `demand_class` in `DOMAIN_S2`.
  * `s2_domain_num_class_zone` — count of distinct `(demand_class, zone[, channel])` combinations.

* **Shape sanity stats** (aggregated, not per-class)

  * `shape_value_min`, `shape_value_median`, `shape_value_p95`, `shape_value_max` across all rows.
  * `shape_l1_error_max` — maximum absolute `|Σ_k shape_value - 1|` across all `(class, zone[, channel])`.
  * Optional: `num_shapes_with_large_l1_error` (count above a tighter, “warning” threshold).

* **Policies and configs**

  * `s2_time_grid_policy_id` / version.
  * `s2_shape_policy_id` / version.
  * `s2_spec_version` (if not already embedded in the data).

On **FAILED**, the run-report MUST include:

* `error_code` — one of the canonical codes from §9 (e.g. `S2_TIME_GRID_INVALID`, `S2_SHAPE_NORMALISATION_FAILED`).
* `error_message` — brief summary.
* `error_details` — optional structured object (e.g. `{ "demand_class": "...", "legal_country_iso": "...", "tzid": "...", "bucket_index": 123 }`), avoiding excessive detail.

The run-report is the **primary source of truth** for S2’s outcome.

---

### 10.3 Structured logging

5A.S2 MUST emit **structured logs** (e.g. JSON lines) for key lifecycle events, tagged with:

* `segment_id = "5A.S2"`
* `parameter_hash`
* `scenario_id`
* `manifest_fingerprint`
* `run_id`

At minimum, S2 MUST log:

1. **State start**

   * Level: `INFO`
   * Fields:

     * `event = "state_start"`
     * `parameter_hash`, `scenario_id`, `manifest_fingerprint`, `run_id`
     * optional: environment tags (e.g. `env`, `ci_build_id`)

2. **Inputs resolved**

   * After resolving S0/S1 and shape/time-grid policies.
   * Level: `INFO`
   * Fields:

     * `event = "inputs_resolved"`
     * `time_grid_policy_id` / version
     * `shape_policy_id` / version
     * `scenario_id` / `scenario_type` (if applicable)
     * counts of required vs optional inputs found (e.g. `required_policy_count`, `optional_policy_count`).

3. **Domain summary**

   * After constructing `DOMAIN_S2`.
   * Level: `INFO`
   * Fields:

     * `event = "domain_built"`
     * `s2_domain_num_classes`
     * `s2_domain_num_class_zone`
     * optional: `s2_domain_num_zones`, `s2_domain_num_channel_groups`.

4. **Grid summary**

   * After building `shape_grid_definition_5A`.
   * Level: `INFO`
   * Fields:

     * `event = "grid_built"`
     * `shape_grid_buckets_per_week` (`T_week`)
     * `shape_grid_bucket_duration_minutes`
     * optional: `shape_grid_buckets_per_day`

5. **Shape summary**

   * After normalisation and before writing outputs.
   * Level: `INFO`
   * Fields:

     * `event = "shape_summary"`
     * `shape_value_min`, `shape_value_median`, `shape_value_p95`, `shape_value_max`
     * `shape_l1_error_max`
     * `num_shapes_with_large_l1_error` (if applicable)
     * optional: `num_flat_shapes` if a flat fallback is used anywhere.

6. **State success**

   * Level: `INFO`
   * Fields:

     * `event = "state_success"`
     * `parameter_hash`, `scenario_id`, `manifest_fingerprint`, `run_id`
     * `shape_grid_buckets_per_week`
     * `s2_domain_num_class_zone`
     * `duration_ms`

7. **State failure**

   * Level: `ERROR`
   * Fields:

     * `event = "state_failure"`
     * `parameter_hash`, `scenario_id`, `manifest_fingerprint`, `run_id`
     * `error_code`
     * `error_message`
     * `error_details` (e.g. offending `demand_class`, zone, `bucket_index` where safe)

**Prohibited logging:**

* S2 MUST NOT log:

  * full per-class/zone shape vectors,
  * full contents of `class_zone_shape_5A`,
  * raw policy configs or large JSON blobs exceeding what’s needed for diagnostics.

Only aggregate statistics and minimal key context for failures are allowed.

---

### 10.4 Metrics

5A.S2 MUST emit a small, stable set of metrics to support monitoring. Names are implementation-specific; semantics are binding.

Recommended metrics:

1. **Run counters**

   * `fraudengine_5A_s2_runs_total{status="success"|"failure"}`
   * `fraudengine_5A_s2_errors_total{error_code="S2_REQUIRED_SHAPE_POLICY_MISSING"|...}`

2. **Latency**

   * `fraudengine_5A_s2_duration_ms` (histogram or summary) — duration per `(parameter_hash, scenario_id, manifest_fingerprint)` run.

3. **Grid size**

   * `fraudengine_5A_s2_buckets_per_week` — gauge per run (should be fairly stable).
   * Optional: `fraudengine_5A_s2_buckets_per_day`.

4. **Domain size**

   * `fraudengine_5A_s2_domain_class_count` — number of distinct classes in `DOMAIN_S2`.
   * `fraudengine_5A_s2_domain_class_zone_count` — number of `(class, zone[, channel])` combos.

5. **Shape quality**

   * `fraudengine_5A_s2_shape_l1_error_max` — max `|Σ_k shape_value - 1|` per run.
   * Optional histogram for `shape_value` distribution to detect skew or unexpected spikes:

     * e.g. `fraudengine_5A_s2_shape_value_histogram`.

Metrics MUST NOT encode sensitive identifiers (e.g. specific `demand_class` names, country codes) as labels unless explicitly allowed by governance; they SHOULD be aggregate-only.

---

### 10.5 Correlation & traceability

To enable traceability across states:

* Every S2 log, metric, and run-report row MUST include:

  * `segment_id = "5A.S2"`
  * `parameter_hash`
  * `scenario_id`
  * `manifest_fingerprint`
  * `run_id`

If the engine supports distributed tracing, S2 SHOULD:

* create or join a trace span (e.g. `"5A.S2"`), and
* annotate it with the same identifiers.

This allows operators to trace a path like:

> “S0 gate → S1 profiles → S2 shapes → S3 baseline intensities → S4 overlays → 5B arrivals”

and understand where things failed or changed.

---

### 10.6 Integration with 5A segment-level validation & dashboards

The 5A segment-level validation state (e.g. `5A.SX_validation`) MUST:

* treat S2 outputs (`shape_grid_definition_5A`, `class_zone_shape_5A`, optional `class_shape_catalogue_5A`) as **required inputs** for any `(parameter_hash, scenario_id)` it validates;
* verify:

  * schema conformance,
  * domain alignment with S1,
  * normalisation constraints,
  * consistency with time-grid policy.

Dashboards and health checks SHOULD be able to answer, per `(parameter_hash, scenario_id)`:

* Has S2 run successfully?
* What is the size of the shape domain and weekly grid?
* Are there systematic shape issues (e.g. large normalisation errors, too many flat shapes)?
* Are there recurring S2 failures, and with which canonical error codes?

Downstream states (S3/S4/5B/6A) MUST NOT use logs/metrics alone as gates; they MUST continue to obey:

* S0/S1/S2 **data-level gates** (presence/validity of S0, S1, S2 datasets and, eventually, 5A’s `_passed.flag`),
* and treat observability signals as diagnostic, not authoritative, in deciding whether to run.

Within these constraints, 5A.S2 is fully observable: its runs are traceable, its failures are diagnosable, and its grid/domain/shape health is visible without leaking or duplicating bulk shape data.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on the performance profile of **5A.S2 — Weekly Shape Library** and how to scale it sensibly. It explains what grows with data size and where to be careful.

---

### 11.1 Performance summary

5A.S2 is generally **cheap** compared to S1 and all event-level work:

* It works at **class×zone×bucket** granularity, not per-merchant or per-event.
* It does:

  * one pass over `merchant_zone_profile_5A` to discover the domain,
  * a bit of policy evaluation per `(class, zone[, channel])`,
  * one pass over the time grid per domain element to compute shapes.

It is:

* CPU-bound on simple numeric ops and policy evaluation,
* I/O-light (one S1 scan, one or two small policy loads, and two or three write operations).

---

### 11.2 Workload characteristics

Let:

* `C` = number of distinct `demand_class` values in use,
* `Z̄` = average number of zones (and channel splits) per class,
* `N_cz = C × Z̄` = number of `(class, zone[, channel])` combinations in `DOMAIN_S2`,
* `T_week` = buckets per local week.

Then:

* Input:

  * `merchant_zone_profile_5A`: O(#merchant×zone) rows, but scanned only to build distinct `(class, zone[, channel])` — we only keep distinct combinations.
  * Policies/configs: O(1) in size.

* Output:

  * `shape_grid_definition_5A`: `T_week` rows.
  * `class_zone_shape_5A`: `N_cz × T_week` rows.
  * Optional `class_shape_catalogue_5A`: O(`C`) rows.

So the dominant factor is `N_cz × T_week`.

---

### 11.3 Algorithmic complexity

For a fixed `(parameter_hash, scenario_id)`:

* **Domain discovery**

  * Scan `merchant_zone_profile_5A` once:

    * Complexity: O(#merchant×zone) to build a set of distinct `(class, zone[, channel])`.
    * In practice, this costs less than S1 because S1 already did the heavier joins.

* **Time grid construction**

  * Build `T_week` rows:

    * Complexity: O(`T_week`) — usually small (e.g. 7×24 = 168 hourly buckets, or 7×96 = 672 15-min buckets).

* **Shape construction & normalisation**

  * For each `(class, zone[, channel])`:

    * evaluate a template over all `T_week` buckets,
    * apply deterministic modifiers,
    * sum and normalise.

  Complexity: O(`N_cz × T_week × R_shape`), where:

  * `R_shape` is the cost of evaluating the template per bucket (ideally a small constant).

Overall:

> Time ≈ O(#merchant×zone) for domain discovery + O(`N_cz × T_week`) for shape building

Space can be:

* O(`T_week`) for the grid,
* O(`N_cz × T_week`) if you buffer all shapes in memory, or
* lower if you stream shapes in chunks.

---

### 11.4 I/O patterns

**Reads**

* One scan of `merchant_zone_profile_5A`:

  * can be done as a streaming projection of just `(demand_class, zone[, channel])` and deduped in memory or via a group-by.
* A handful of small policy/config files:

  * time-grid policy, shape library policy, maybe a couple of lookup tables.

**Writes**

* One `shape_grid_definition_5A` file per `(parameter_hash, scenario_id)`:

  * tiny (order of thousands of rows at most).
* One `class_zone_shape_5A` file per `(parameter_hash, scenario_id)`:

  * size O(`N_cz × T_week`).
* Optional `class_shape_catalogue_5A`: tiny.

Typical bottlenecks:

* Very large `N_cz` (tons of classes or zones per class) will grow `class_zone_shape_5A` and shape evaluation time, but still linear.

---

### 11.5 Parallelisation & scaling strategy

S2 parallelises naturally across `(class, zone[, channel])`:

* **Grid construction** is trivial and can be done once on a single worker.

* **Shape computation**:

  * Partition `DOMAIN_S2` (e.g. by `demand_class` or hash of `(class, zone)`) across workers.
  * Each worker:

    * receives the shared `GRID_ROWS` and shape policies,
    * computes shapes for its subset,
    * emits rows into a local buffer or staging file.

* **Merge**:

  * Merge outputs from workers into a single `class_zone_shape_5A` file (or a small, fixed number of files) in a deterministic ordering.

S2 **does not need** to shard storage by zone or class; a single partition per `(parameter_hash, scenario_id)` is sufficient. Scaling is mostly about compute parallelism, not storage complexity.

---

### 11.6 Memory & streaming considerations

For typical sizes:

* `GRID_ROWS` is tiny.
* `SHAPE_ROWS` can be large if `N_cz × T_week` is big.

Approaches:

* **In-memory** (simplest, fine when `N_cz × T_week` is moderate):

  * Hold all `SHAPE_ROWS` in memory, sort, write once.

* **Chunked streaming** (for very large domains):

  * Process `DOMAIN_S2` in chunks:

    * compute shapes for a subset,
    * write to per-chunk staging files with a deterministic local sort,
    * then merge sorted chunks once.
  * This keeps peak memory bounded by chunk size, not full `N_cz × T_week`.

In both scenarios, the spec only cares that:

* ordering is deterministic;
* PKs are unique;
* shape invariants hold;
* final write is atomic.

---

### 11.7 Failure, retry & backoff

Because S2 is deterministic for a given `(parameter_hash, scenario_id)`:

* **Transient failures** (e.g. `S2_IO_READ_FAILED`, `S2_IO_WRITE_FAILED`):

  * Safe to retry after backoff, provided:

    * no canonical outputs were partially overwritten, and
    * staging paths are cleaned or ignored.

* **Configuration/policy failures** (`S2_REQUIRED_SHAPE_POLICY_MISSING`, `S2_TIME_GRID_INVALID`, `S2_TEMPLATE_RESOLUTION_FAILED`, `S2_SHAPE_NORMALISATION_FAILED`):

  * Retrying without changing configs will just fail again.
  * Orchestration SHOULD stop retrying and surface the error; fix requires:

    * correcting shape/time-grid policies or
    * updating the parameter pack.

* **Output conflicts** (`S2_OUTPUT_CONFLICT`):

  * Indicates that you changed policies/configs without changing `parameter_hash`.
  * Correct fix: mint a new `parameter_hash` and run S2 for the new pack.

---

### 11.8 Suggested SLOs (non-binding)

Depending on `N_cz` and `T_week`, reasonable (non-binding) targets:

* **Latency per `(parameter_hash, scenario_id)`**

  * For modest grids (e.g. `T_week ≤ 1000`) and moderate domains (`N_cz` up to a few tens of thousands):

    * p50: < 10–30 seconds
    * p95: < 1–2 minutes

* **Error budgets**

  * `S2_IO_*` errors: rare, infra-related.
  * Shape-config errors: treated as config/data-quality issues, not normal operational noise.

---

In short: 5A.S2 should be a **small, predictable component** — linear in the size of the shape domain, easy to parallelise, and much cheaper than any per-merchant or per-event work.

---

## 12. Change control & compatibility *(Binding)*

This section defines how **5A.S2 — Weekly Shape Library** and its contracts may evolve over time, and what compatibility guarantees MUST hold. All rules here are **binding**.

The goals are:

* No silent breaking changes in the **shape grid** or **shape semantics**.
* Clear separation between:

  * **spec changes** (structure/semantics), and
  * **policy/parameter-pack changes** (which simply change `parameter_hash`).
* Predictable behaviour for downstream consumers (5A.S3–S4, 5B, 6A).

---

### 12.1 Scope of change control

Change control for 5A.S2 covers:

1. **Row schemas & shapes**

   * `schemas.5A.yaml#/model/shape_grid_definition_5A`
   * `schemas.5A.yaml#/model/class_zone_shape_5A`
   * `schemas.5A.yaml#/model/class_shape_catalogue_5A` (if implemented)

2. **Catalogue contracts**

   * `dataset_dictionary.layer2.5A.yaml` entries for:

     * `shape_grid_definition_5A`
     * `class_zone_shape_5A`
     * `class_shape_catalogue_5A` (optional)
   * `artefact_registry_5A.yaml` entries for the same artefacts.

3. **Algorithm semantics**

   * The deterministic algorithm in §6 (time grid, domain derivation, template construction, normalisation).
   * Identity & partition rules in §7.
   * Acceptance & gating rules in §8.
   * Failure modes & error codes in §9.

Changes to **shape/time-grid policies** and **parameter packs** are governed separately, but their impact on S2 is captured via `parameter_hash` and `scenario_id` and discussed in §12.6.

---

### 12.2 S2 spec version field

To support evolution, S2 MUST expose a **spec version**:

* `s2_spec_version` — string, e.g. `"1.0.0"`.

Binding requirements:

* `s2_spec_version` MUST be present as a **required, non-null field** in `class_zone_shape_5A`.
* It MAY also appear in `shape_grid_definition_5A` and `class_shape_catalogue_5A` (optional but recommended), but the primary anchor is the shape table.

The schema anchors in `schemas.5A.yaml` MUST define `s2_spec_version` as:

* Type: string
* Non-nullable

#### 12.2.1 Versioning scheme

`s2_spec_version` MUST use semantic-style versioning:

* `MAJOR.MINOR.PATCH`

Interpretation:

* **MAJOR** — incremented for **backwards-incompatible** changes (see §12.4).
* **MINOR** — incremented for **backwards-compatible** enhancements (see §12.3).
* **PATCH** — incremented for bug fixes or clarifications that do not change schemas or observable behaviour.

Downstream consumers (S3–S4, 5B, 6A) MUST:

* read `s2_spec_version`,
* support an explicit set of MAJOR versions, and
* refuse to operate on S2 outputs whose `MAJOR` version is outside that set.

---

### 12.3 Backwards-compatible changes (allowed without MAJOR bump)

The following are considered **backwards-compatible** and MAY be introduced with a **MINOR** (or PATCH) bump, provided conditions are met.

#### 12.3.1 Adding optional fields

Allowed:

* Adding new **optional** fields to:

  * `shape_grid_definition_5A`,
  * `class_zone_shape_5A`,
  * `class_shape_catalogue_5A`.

Conditions:

* Fields MUST NOT be added to `primary_key` or partition keys.
* New fields MUST be marked as optional in JSON-Schema (not under `required`).
* Absence MUST have a clear default meaning (e.g. “flag absent ⇒ treat as false or ignore”).

Example:

* Adding `is_weekend` or `is_nominal_open_hours` to the grid.
* Adding `adjustment_flags` to shapes to describe which policy knobs were applied.

#### 12.3.2 Adding new `demand_class` or zone combinations via policy

Allowed:

* Adding new `demand_class` values or new class/zone combinations in `DOMAIN_S2` **by changing shape policies and parameter packs only**.

Conditions:

* S2 schemas continue to treat `demand_class` as a string label, not a fixed compile-time enum.
* Downstream consumers interpret `demand_class` via the parameter pack (e.g. shape library), not via a hard-coded list.

This is primarily a policy/parameter change, reflected in a **new `parameter_hash`**, and does not require S2 spec changes if shapes are still constructed & normalised the same way.

#### 12.3.3 Adding new optional shape attributes

Allowed:

* Adding new attributes to `class_zone_shape_5A` that describe shapes but do not alter how downstream segments interpret `shape_value`, e.g.:

  * `template_id`, `template_type`,
  * diagnostic flags or labels.

Conditions:

* Downstream code MUST treat them as optional and must function if they’re absent.
* These fields MUST NOT change the meaning of `shape_value`.

#### 12.3.4 Additional reference links

Allowed:

* Adding optional foreign-key references from S2 tables to new reference tables (e.g. region group, time-use profiles), as long as:

  * they don’t change primary keys or partition keys,
  * they’re optional, and
  * missing refs are handled by defaults.

---

### 12.4 Backwards-incompatible changes (require MAJOR bump)

The following are **backwards-incompatible** and MUST be accompanied by:

* a new **MAJOR** version in `s2_spec_version`, and
* a coordinated rollout in all S2 consumers.

#### 12.4.1 Changing primary keys or partitioning

Incompatible:

* Changing:

  * `primary_key: ["parameter_hash","scenario_id","bucket_index"]` for `shape_grid_definition_5A`, or
  * `primary_key` for `class_zone_shape_5A` (currently `[parameter_hash, scenario_id, demand_class, zone_representation, bucket_index]`), or
  * `partition_keys: ["parameter_hash","scenario_id"]` for these tables.

Any such change breaks joins and must be treated as a new MAJOR.

#### 12.4.2 Changing time-grid semantics

Incompatible:

* Changing the fundamental semantics of the grid without changing column names/types, for example:

  * redefining `bucket_index` from “local-week index” to “UTC index”,
  * redefining `local_day_of_week` to use a different day-numbering convention,
  * changing `bucket_duration_minutes` in a way that invalidates existing shapes.

Such changes require:

* a new MAJOR `s2_spec_version`, and
* downstream updates to interpret the new grid correctly.

Minor adjustments that are fully backward compatible (e.g. adding metadata fields) are allowed, but any change that redefines **what a bucket means** is breaking.

#### 12.4.3 Changing `shape_value` semantics

Incompatible:

* Changing the meaning of `shape_value` without renaming or re-scheming it, e.g.:

  * redefining it from “fraction of weekly volume” to “absolute expected count per bucket”,
  * redefining normalisation constraints (sum=1 → sum=7 for some reason).

If such a change is ever needed, it MUST:

* introduce new fields or new tables, and/or
* bump MAJOR and clearly document the new semantics.

#### 12.4.4 Changing domain semantics

Incompatible:

* Redefining the domain from “per `(demand_class, zone[, channel])` over a local-week grid” to something structurally different, e.g.:

  * moving to per-country only (no tz dimension), or
  * using merchant-specific shapes inside S2.

Those are significant conceptual changes and require a new MAJOR.

---

### 12.5 Compatibility of code with existing S2 data

Implementations of S2 and its consumers MUST handle **existing S2 outputs** correctly.

#### 12.5.1 Reading older `s2_spec_version` data

When reading S2 outputs:

* If `s2_spec_version.MAJOR` is within the implementation’s supported range:

  * Consumers MUST accept the data.
  * Unknown optional fields MUST be ignored or handled using defaults.
  * Known fields MUST be interpreted according to the relevant `MINOR.PATCH`.

* If `s2_spec_version.MAJOR` is greater than the implementation supports:

  * Consumers MUST treat S2 outputs for that `(parameter_hash, scenario_id)` as **unsupported**.
  * They MUST fail fast with a clear “unsupported S2 spec version” error.

#### 12.5.2 Re-running S2 with newer code

Re-running S2 with a newer implementation for the same `(parameter_hash, scenario_id)`:

* If time-grid + shape policies are unchanged and upstream S1 output is unchanged:

  * S2 SHOULD produce byte-identical outputs (idempotent).

* If configs/policies changed in any way that affects the grid or shapes:

  * A new `parameter_hash` MUST be minted to represent the new parameter pack.
  * The old `(parameter_hash, scenario_id)` outputs should be treated as immutable.

Attempts to re-run S2 under the old `parameter_hash` with changed policies risk `S2_OUTPUT_CONFLICT` and MUST be treated as errors.

---

### 12.6 Interaction with parameter packs & policies

Most behaviour changes in S2 are expected to come from:

* **Policy updates**, and
* **parameter pack changes**, not spec changes.

#### 12.6.1 Policy changes & `parameter_hash`

Any change to:

* time-grid policy (`shape_time_grid_policy_5A`),
* shape library policy (`shape_library_5A`), or
* any supporting tables that affect shapes,

MUST trigger:

* a new **`parameter_hash`** (new parameter pack), and
* re-running S0/S1/S2 for relevant worlds.

S2’s spec version (`s2_spec_version`) may remain unchanged if contracts and semantics are the same and only parameter values changed.

#### 12.6.2 Upstream changes (S1 or Layer-1)

If upstream changes alter domain or class labels:

* Domain changes (e.g. new `demand_class`, new zones) will be picked up in S1 → S2 through `parameter_hash` and `sealed_inputs_5A`.
* S2 must be re-run under any fingerprint whose S1 output changed.

Breaking structural changes in S1 (e.g. changing keys or semantics of `merchant_zone_profile_5A`) are governed by S1’s own spec; S2 must upgrade to a compatible `s1_spec_version` before consuming such outputs.

---

### 12.7 Governance & documentation

Any change to S2 contracts MUST be governed and documented:

1. **Spec updates**

   * Changes to §§1–12 for S2 MUST be versioned alongside:

     * updates to `schemas.5A.yaml` for S2 anchors,
     * updates to `dataset_dictionary.layer2.5A.yaml` entries,
     * updates to `artefact_registry_5A.yaml` entries for S2 outputs.

2. **Release notes**

   * Every change that bumps `s2_spec_version` MUST be noted in release documentation:

     * previous → new version,
     * whether change is MAJOR / MINOR / PATCH,
     * summary of schema/semantic changes,
     * required actions for existing `(parameter_hash, scenario_id)` pairs (e.g. re-run S2 vs treat old outputs as frozen).

3. **Testing**

   * New S2 implementations MUST be regression-tested against:

     * synthetic small worlds (few classes/zones, sanity-checking shapes and grid), and
     * representative large worlds (large `N_cz`, reasonable `T_week`).

   * Tests MUST include:

     * idempotency (same inputs → same outputs),
     * conflict detection (`S2_OUTPUT_CONFLICT` cases),
     * backwards-compatibility (reading S2 outputs from older `s2_spec_version.MAJOR` values within support),
     * failure-case coverage for key error codes (`S2_TIME_GRID_INVALID`, `S2_TEMPLATE_RESOLUTION_FAILED`, `S2_SHAPE_NORMALISATION_FAILED`).

Within these constraints, 5A.S2 can evolve in a controlled way: *what* the shapes look like changes via policies and parameter packs; *how* shapes are structured, normalised, and exposed to downstream segments changes via explicit, versioned spec evolution with clear MAJOR/MINOR/PATCH semantics.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix defines short-hands, symbols, and abbreviations used in the **5A.S2 — Weekly Shape Library** spec. It is **informative** only; binding definitions live in §§1–12.

---

### 13.1 Notation conventions

* **Monospace** (`class_zone_shape_5A`) → concrete dataset/field/config names.
* **UPPER_SNAKE** (`S2_SHAPE_NORMALISATION_FAILED`) → canonical error codes.
* `"Quoted"` (`"PASS"`, `"REQUIRED"`, `"policy"`) → literal enum/string values.
* Single letters:

  * `k` → time-bucket index within a local week.
  * `c` → country (`legal_country_iso`).
  * `tz` → timezone / zone (`tzid` or `zone_id`).

---

### 13.2 Identity & scope symbols

| Symbol / field         | Meaning                                                                                                   |
| ---------------------- | --------------------------------------------------------------------------------------------------------- |
| `parameter_hash`       | Opaque identifier of the **parameter pack** (time-grid policy, shape library, scenario config, etc.).     |
| `manifest_fingerprint` | Opaque identifier of the **closed-world manifest** used for S0/S1 gating; S2 outputs are not keyed on it. |
| `scenario_id`          | Scenario identifier under which S2 templates are defined (e.g. `"baseline"`, `"bf_2027_stress"`).         |
| `run_id`               | Identifier of this execution of S2 for the given `(parameter_hash, scenario_id, manifest_fingerprint)`.   |
| `s2_spec_version`      | Semantic version of the 5A.S2 spec that produced the shapes (e.g. `"1.0.0"`).                             |
| `T_week`               | Number of buckets per local week (e.g. `7×24 = 168` for hourly buckets).                                  |

---

### 13.3 Datasets & artefact identifiers (S2-related)

| Name / ID                   | Description                                                                                    |
| --------------------------- | ---------------------------------------------------------------------------------------------- |
| `shape_grid_definition_5A`  | Required S2 output: one row per local-week bucket for a given `(parameter_hash, scenario_id)`. |
| `class_zone_shape_5A`       | Required S2 output: class×zone[×channel] weekly shapes over the local-week grid, normalised.   |
| `class_shape_catalogue_5A`  | Optional S2 output: base template catalogue per `demand_class` (and optional channel group).   |
| `s0_gate_receipt_5A`        | S0 gate record: upstream statuses, scenario binding, sealed-input digest.                      |
| `sealed_inputs_5A`          | S0 inventory of all artefacts 5A may read for a given `manifest_fingerprint`.                  |
| `merchant_zone_profile_5A`  | S1 output: per-merchant×zone demand profiles; S2 uses it to derive the class/zone domain only. |
| `shape_time_grid_policy_5A` | 5A config: defines bucket size, buckets per week, mapping `bucket_index → local time`.         |
| `shape_library_5A`   | 5A config: defines base templates and modifiers per `demand_class` / zone / channel group.     |

(Exact `artifact_id` / `manifest_key` values come from the dataset dictionary and artefact registry.)

---

### 13.4 Fields in `shape_grid_definition_5A`

| Field name                     | Meaning                                                                           |
| ------------------------------ | --------------------------------------------------------------------------------- |
| `parameter_hash`               | Parameter pack identity; partition and join key for S2 outputs.                   |
| `scenario_id`                  | Scenario identifier; partition and join key for S2 outputs.                       |
| `bucket_index`                 | Integer index of the bucket in the local week, in `[0, T_week-1]`.                |
| `local_day_of_week`            | Local day-of-week for this bucket (e.g. 1=Monday…7=Sunday), per time-grid policy. |
| `local_minutes_since_midnight` | Minutes since local midnight at the start of this bucket.                         |
| `bucket_duration_minutes`      | Length (in minutes) of this bucket, as dictated by the time-grid policy.          |
| `is_weekend`                   | Optional flag indicating weekend buckets, as defined in configuration.            |
| `is_nominal_open_hours`        | Optional flag indicating “typical business hours” buckets.                        |
| `time_grid_version`            | Optional version string for the time-grid policy.                                 |

---

### 13.5 Fields in `class_zone_shape_5A`

*(Exact schema in §5; this table summarises semantics.)*

| Field name                  | Meaning                                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------------------ |
| `parameter_hash`            | Parameter pack identity; matches S2 partition and S1’s `parameter_hash`.                         |
| `scenario_id`               | Scenario identity used for partitioning.                                                         |
| `demand_class`              | Class label from S1/policy (`merchant_zone_profile_5A` & shape library).                         |
| `legal_country_iso`         | Country code for the zone (if using explicit country+tz representation).                         |
| `tzid`                      | IANA timezone identifier for the zone (if using explicit country+tz representation).             |
| `zone_id`                   | Optional derived zone key (if using combined zone representation instead of `(country,tzid)`).   |
| `channel` / `channel_group` | Optional channel dimension (e.g. `"POS"`, `"ECOM"`, or grouped).                                 |
| `bucket_index`              | Time-bucket index, FK to `shape_grid_definition_5A`.                                             |
| `shape_value`               | Non-negative fraction of total weekly volume for this `(class, zone[, channel])` in this bucket. |
| `s2_spec_version`           | Version of the S2 spec that produced this row.                                                   |
| `template_id`               | Optional reference to base template from `class_shape_catalogue_5A`.                             |
| `adjustment_flags`          | Optional diagnostic field describing which modifiers were applied.                               |

---

### 13.6 Fields in `class_shape_catalogue_5A` (optional)

| Field name        | Meaning                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------- |
| `parameter_hash`  | Parameter pack identity.                                                                           |
| `scenario_id`     | Scenario identity.                                                                                 |
| `demand_class`    | Class label to which this template applies.                                                        |
| `channel_group`   | Optional channel grouping (e.g. `"POS"`, `"ECOM"`, `"UNSPECIFIED"`).                               |
| `template_id`     | Identifier of the base template used by S2 for this class[/channel].                               |
| `template_type`   | Short descriptor (e.g. `"office_hours"`, `"nightlife"`, `"online_flat"`, `"two_peak_retail"`).     |
| `template_params` | Structured parameter payload (e.g. peak times, peak heights, weekday/weekend weights), per schema. |
| `policy_version`  | Optional version string for the shape policy that defined this template.                           |
| `s2_spec_version` | S2 spec version (if stored here as well).                                                          |

All catalogue information MUST be derivable from 5A shape policies; no new fundamental semantics may appear only here.

---

### 13.7 Domain & shape shorthand

| Symbol / phrase               | Meaning                                                                                             |
| ----------------------------- | --------------------------------------------------------------------------------------------------- |
| `DOMAIN_S1`                   | Set of `(demand_class, zone[, channel])` combinations observed in `merchant_zone_profile_5A`.       |
| `DOMAIN_policy`               | Set of additional class/zone combinations declared in shape policies (allowed even if not in S1).   |
| `DOMAIN_S2`                   | S2 domain: `DOMAIN_S1 ∪ DOMAIN_policy`, the full set of `(demand_class, zone[, channel])` to shape. |
| `v(class, zone, k)`           | Unnormalised shape value for class/zone in bucket `k` before normalisation.                         |
| `shape_value(class, zone, k)` | Final normalised fraction for class/zone in bucket `k` (after division by total mass).              |
| `total(class, zone)`          | Σ over `k` of `v(class, zone, k)` — the pre-normalisation mass for that class/zone.                 |

---

### 13.8 Error codes (5A.S2)

For quick reference, the canonical S2 error codes from §9:

| Code                               | Brief description                                      |
| ---------------------------------- | ------------------------------------------------------ |
| `S2_GATE_OR_S1_INVALID`            | S0/S1 gate invalid or misaligned for this run.         |
| `S2_UPSTREAM_NOT_PASS`             | Upstream segments (1A–3B) not all `"PASS"`.            |
| `S2_REQUIRED_INPUT_MISSING`        | Required S1 or 5A artefact missing from sealed inputs. |
| `S2_REQUIRED_SHAPE_POLICY_MISSING` | Time-grid or shape policy missing/invalid.             |
| `S2_TIME_GRID_INVALID`             | Local-week grid inconsistent or out of range.          |
| `S2_TEMPLATE_RESOLUTION_FAILED`    | No/ambiguous base template for some class/zone.        |
| `S2_DOMAIN_ALIGNMENT_FAILED`       | Shape domain doesn’t match S1/policy domain.           |
| `S2_SHAPE_NORMALISATION_FAILED`    | Negative/NaN values or bad normalisation (Σ≠1).        |
| `S2_OUTPUT_CONFLICT`               | Existing S2 outputs differ from recomputed outputs.    |
| `S2_IO_READ_FAILED`                | I/O failures reading required inputs.                  |
| `S2_IO_WRITE_FAILED`               | I/O failures writing or committing outputs.            |
| `S2_INTERNAL_INVARIANT_VIOLATION`  | Internal “should never happen” state.                  |

These codes appear in logs/run-report, not in S2 data schemas.

---

### 13.9 Miscellaneous abbreviations

| Abbreviation | Meaning                                                     |
| ------------ | ----------------------------------------------------------- |
| S0           | State 0: Gate & Sealed Inputs for Segment 5A.               |
| S1           | State 1: Merchant & Zone Demand Classification.             |
| S2           | State 2: Weekly Shape Library (this spec).                  |
| L1 / L2      | Layer-1 / Layer-2.                                          |
| “zone”       | A `(legal_country_iso, tzid)` combination or its `zone_id`. |
| “shape”      | The weekly template vector `shape_value(·,·,k)` per domain. |

This appendix is intended as a quick reference when reading or implementing the S2 spec; binding behaviour and structure are fully defined in §§1–12.

---
