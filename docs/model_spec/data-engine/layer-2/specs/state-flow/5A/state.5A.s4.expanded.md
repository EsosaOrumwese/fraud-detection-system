# 5A.S4 — Calendar & Scenario Overlays (Layer-2 / Segment 5A)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5A.S4 — Calendar & Scenario Overlays** for **Layer-2 / Segment 5A**. It is binding on any implementation of this state.

---

### 1.1 Role of 5A.S4 in Segment 5A

5A.S4 is the **calendar & scenario overlay layer** on top of Segment 5A’s baseline intensities.

Given a sealed world `(parameter_hash, manifest_fingerprint)` with S0–S3 already in place, S4:

* Takes **per-merchant×zone baseline weekly intensities** from S3:

  * `λ_base_local(m, z, k)` over a local-week grid (`k` = local-week bucket index).
* Takes **scenario calendar & configuration**:

  * public holidays, pay cycles, campaigns, outages, stress shocks, and any other scenario-specific events.
* Takes **overlay policies** that describe how events map to **deterministic multipliers** over time.

And produces **scenario-adjusted expected intensities** such as:

* `λ_scenario_local(m, z, h)` — for each merchant×zone and each **local horizon bucket** `h` in the scenario window.

Optionally, S4 may also produce:

* `λ_scenario_utc(m, z, h_utc)` — the same intensities but expressed on a **UTC horizon grid**.

5A.S4 is:

* **RNG-free** — it MUST NOT sample events, LGCPs or Poisson processes; it only applies deterministic overlays.
* **Routing-agnostic** — it does NOT decide which site/edge; routing remains the job of Layer-1/5B.
* **Pre-event** — it does NOT generate concrete arrivals or flows; it only modifies expected intensities.

It answers the question:

> “Given the baseline curve and this scenario’s calendar of events, what should the expected traffic profile look like over the actual horizon?”

---

### 1.2 Objectives

5A.S4 MUST:

* **Apply calendar & scenario overlays to baseline intensities**

  For each in-scope `(merchant, zone[, channel])` and each horizon bucket `h`:

  * derive the relevant **baseline bucket** index `k` in the S2/S3 local-week grid, and
  * compute a **composite overlay factor** `F_overlay(m, z, h)` from scenario/calendar events and overlay policy, then
  * produce:

    ```text
    λ_scenario_local(m, z, h) = λ_base_local(m, z, k) × F_overlay(m, z, h)
    ```

  with clear semantics for what `h` and `k` are (local-time vs local-week bucket, defined in the time/horizon grid configs).

* **Remain deterministic and policy-driven**

  * All overlay factors MUST be deterministic functions of:

    * baseline intensities & local-week grid (S3/S2),
    * scenario calendar & event data,
    * overlay policies/configs,
    * and the run identity `(parameter_hash, manifest_fingerprint, scenario_id)`.
  * S4 MUST NOT depend on wall-clock time for logic (beyond timestamp metadata); the same inputs MUST always yield the same outputs.

* **Respect upstream semantics**

  * Treat S3’s `λ_base_local` as the **authoritative baseline**; S4 MUST NOT recompute or second-guess baseline scale or shape.
  * Treat S2’s grid (`shape_grid_definition_5A`) as the **authoritative local-week time grid**; S4 MUST NOT redefine bucketisation.
  * Treat scenario calendar artefacts and overlay policies as the **only authority** for “what events happen when” and “how events affect intensity”.

* **Produce a horizon-level scenario surface for downstream use**

  * Emit a horizon-level intensity surface that:

    * is keyed by `(merchant, zone[, channel], horizon_bucket)`,
    * is aligned with Scenario + baseline world identity,
    * is suitable as input to:

      * **5A.S5** (validation & HashGate), and
      * **5B** (stochastic realisation of arrivals).

---

### 1.3 In-scope behaviour

The following activities are **in scope** for 5A.S4 and MUST be implemented in this state (not duplicated elsewhere):

* **Gating on S0–S3 and scenario configs**

  * Verifying that:

    * S0 gate and `sealed_inputs_5A` are valid for the target `(parameter_hash, manifest_fingerprint)`.
    * All Layer-1 segments 1A–3B are `"PASS"`.
    * S1, S2 and S3 outputs exist and are schema-valid for the given world/pack/scenario.
    * Scenario calendar & overlay configs required for S4 are present and schema-valid.

* **Horizon grid definition**

  * Defining a **scenario horizon grid** in local time (and optionally UTC), including:

    * horizon start/end (`start_local`, `end_local`),
    * horizon bucket size (e.g. 15 min / 1 hour),
    * mapping from horizon buckets `h` to:

      * calendar dates (e.g. local ISO date), and
      * local time-of-day (`day_of_week`, `time_of_day`).

  * Where needed (if S4 also outputs UTC), defining a UTC horizon grid and mapping local horizon buckets to UTC buckets using 2A civil-time surfaces.

* **Event surface construction**

  * Turning scenario calendar artefacts into **event surfaces** over the horizon:

    * For each `(zone, horizon_bucket)` and/or `(merchant, zone, horizon_bucket)`, determine which events apply:

      * public holidays, paydays, weekends/weekdays,
      * campaigns (global or merchant/segment-specific),
      * outages, stress events, or other scenario features.

* **Overlay factor evaluation**

  * Using overlay policies to compute, for each `(merchant, zone[, channel], horizon_bucket)`:

    ```text
    F_overlay(m, z, h) ≥ 0
    ```

    as a deterministic combination of:

    * baseline-type effects,
    * event-type-specific multipliers,
    * scenario-wide modifiers.

  * Handling overlaps deterministically (e.g. multiply factors, apply precedence rules) as defined by policy.

* **Scenario-intensity composition**

  * For each `(m,z[,ch],h)`:

    * locate the corresponding baseline bucket `k` in the S2/S3 local-week grid (e.g. same `day_of_week` + `time_of_day`),

    * compute:

      ```text
      λ_scenario_local(m,z[,ch],h) =
        λ_base_local(m,z[,ch],k) × F_overlay(m,z[,ch],h)
      ```

    * enforce:

      * `λ_scenario_local ≥ 0`, finite,
      * overlay factors within configured bounds (e.g. not exceeding maximum allowed uplift, not below minimum allowed factor except for explicit “shutdown” semantics).

* **(Optional) UTC projection**

  * If S4 produces UTC intensities, mapping local horizon intensities to UTC grid via deterministic rules using 2A (`site_timezones`, `tz_timetable_cache`) and horizon configs.

* **Scenario-intensity dataset emission**

  * Writing `merchant_zone_scenario_local_5A` (and any optional S4 outputs) as world+scenario-scoped datasets, partitioned and keyed appropriately.

---

### 1.4 Out-of-scope behaviour

The following activities are explicitly **out of scope** for 5A.S4 and MUST NOT be implemented in this state:

* **Random number generation**

  * S4 MUST NOT:

    * draw Poisson / Gamma / Gaussian samples,
    * introduce any stochastic noise,
    * interact with `rng_audit_log`, `rng_trace_log`, or any RNG events.

  Stochastic realisation of event counts belongs to **5B** (and, for routing, Layer-1 RNG segments).

* **Recomputation of baseline or shapes**

  * S4 MUST NOT:

    * recompute or reclassify `demand_class` or base scales (S1’s job),
    * re-derive or reshape the weekly shapes (S2’s job),
    * recompute baseline λ surfaces (S3’s job).

  It may only read and multiply S3 baselines by overlay factors.

* **Routing and site/edge selection**

  * S4 MUST NOT:

    * choose physical sites or virtual edges for arrivals,
    * interact with 2B/3B alias tables or routing RNG.

  Routing remains a separate concern in Layer-1 + 5B.

* **Entity or fraud logic**

  * S4 MUST NOT:

    * attach intensities to specific customers, accounts, devices, or labels,
    * define fraud rates or fraud campaigns;
      those are Layer-3 concerns.

* **Segment-level PASS & `_passed.flag`**

  * S4 does NOT decide segment-level PASS/FAIL for 5A.
  * It contributes inputs to 5A.S5 (validation & HashGate), which is responsible for building the 5A validation bundle and `_passed.flag`.

---

### 1.5 Downstream obligations

This specification imposes the following obligations on downstream states and consumers (primarily 5A.S5, 5B, and any analysis pipelines):

* **Gating on S4 outputs**

  * Any state that needs **scenario-aware intensities** MUST:

    * check that S4 outputs (e.g. `merchant_zone_scenario_local_5A`) exist for the target `(parameter_hash, manifest_fingerprint, scenario_id)`,
    * verify they are schema-valid, identity-consistent, and satisfy S4’s acceptance criteria (once defined in §§8–9).

* **Treat S4 as the scenario-intensity authority**

  * Downstream logic MUST treat S4’s intensities as the **authoritative scenario-aware λ**:

    * `λ_scenario_*` = baseline × all calendar/scenario overlays.

  * They MUST NOT:

    * re-apply calendar overlays directly to S3 baselines,
    * define alternative, conflicting overlay pipelines behind S4’s back.

* **No modification of S4 outputs**

  * Later states MUST NOT mutate or overwrite S4 datasets.
  * Any change to the overlay behaviour MUST be expressed via:

    * updated scenario/overlay policies and parameter packs (`parameter_hash`), and
    * re-running S4 (and S5) under the new identities.

Within this scope, 5A.S4 is the **single deterministic bridge** between:

* the static weekly baseline world (S1–S3), and
* the scenario-specific, horizon-aware intensity world that 5A.S5 and 5B will validate and realise into concrete arrivals.

---

## 2. Preconditions & sealed inputs *(Binding)*

This section defines when **5A.S4 — Calendar & Scenario Overlays** is allowed to run, and what sealed inputs it may rely on. These requirements are **binding**.

---

### 2.1 Invocation context

5A.S4 MUST only be invoked in the context of a well-defined engine run characterised by:

* `parameter_hash` — identity of the parameter pack (including S1–S4 policies + scenario config).
* `manifest_fingerprint` — identity of the closed-world manifest S0/S1/S3 are tied to.
* `scenario_id` — identifier of the scenario whose overlays are being applied (e.g. `"baseline"`, `"bf_2027_stress"`).
* `run_id` — identifier for this S4 execution.

These values:

* MUST be supplied by the orchestration layer;
* MUST match those used when **S0–S3** ran for this world;
* MUST be treated as immutable for the duration of S4.

S4 MUST NOT recompute or override `parameter_hash`, `manifest_fingerprint`, or `scenario_id`.

---

### 2.2 Dependency on 5A.S0 (gate receipt & sealed inventory)

Before any work, S4 MUST require a valid S0 gate for the target `manifest_fingerprint`:

1. **Presence**

   * `s0_gate_receipt_5A` exists for `fingerprint={manifest_fingerprint}`.
   * `sealed_inputs_5A` exists for `fingerprint={manifest_fingerprint}`.

   Both MUST be located via `dataset_dictionary.layer2.5A.yaml` and `artefact_registry_5A.yaml`, not via ad-hoc paths.

2. **Schema validity**

   * `s0_gate_receipt_5A` validates against `schemas.5A.yaml#/validation/s0_gate_receipt_5A`.
   * `sealed_inputs_5A` validates against `schemas.5A.yaml#/validation/sealed_inputs_5A`.

3. **Identity consistency**

   * `s0_gate_receipt_5A.parameter_hash == parameter_hash`.
   * All `sealed_inputs_5A` rows for this fingerprint have:

     * `parameter_hash == parameter_hash`, and
     * `manifest_fingerprint == manifest_fingerprint`.

4. **Sealed-inventory digest**

   * S4 MUST recompute `sealed_inputs_digest` from `sealed_inputs_5A` using the S0 hashing law and confirm equality with `s0_gate_receipt_5A.sealed_inputs_digest`.

If any of these checks fail, S4 MUST abort with a gate precondition failure and MUST NOT read further inputs or write any outputs.

---

### 2.3 Upstream readiness: Layer-1 and S1–S3

S4 sits on top of **Layer-1** and the first three 5A states. It MUST NOT run unless all required upstream pieces are green.

#### 2.3.1 Layer-1 segments (1A–3B)

From `s0_gate_receipt_5A.verified_upstream_segments`, S4 MUST:

* read status for each of: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.

Precondition:

* For S4 to proceed, all listed segments MUST have `status="PASS"`.

If any has `status="FAIL"` or `status="MISSING"`, S4 MUST:

* abort with a precondition error (e.g. `S4_UPSTREAM_NOT_PASS`), and
* MUST NOT attempt to read Layer-1 datasets directly.

#### 2.3.2 5A.S1–S3 outputs

S4 depends on the following 5A outputs:

* **S1 — Merchant & Zone Demand Classification**

  * `merchant_zone_profile_5A` MUST:

    * exist for `(manifest_fingerprint, parameter_hash)`,
    * validate against `#/model/merchant_zone_profile_5A`,
    * have `parameter_hash == parameter_hash`, `manifest_fingerprint == manifest_fingerprint`.

* **S2 — Weekly Shape Library**

  * `shape_grid_definition_5A` MUST:

    * exist for `(parameter_hash, scenario_id)`,
    * validate against `#/model/shape_grid_definition_5A`,
    * define a consistent contiguous bucket range `[0..T_week-1]`.

  * `class_zone_shape_5A` MUST:

    * exist for `(parameter_hash, scenario_id)`,
    * validate against `#/model/class_zone_shape_5A`,
    * embed `parameter_hash == parameter_hash`, `scenario_id == scenario_id`.

* **S3 — Baseline Merchant×Zone Weekly Intensities**

  * `merchant_zone_baseline_local_5A` MUST:

    * exist for `(manifest_fingerprint, parameter_hash, scenario_id)`,
    * validate against `#/model/merchant_zone_baseline_local_5A`,
    * embed `manifest_fingerprint == manifest_fingerprint`, `parameter_hash == parameter_hash`, `scenario_id == scenario_id`.

If any of these datasets are missing, schema-invalid, or identity-inconsistent, S4 MUST treat this as a hard precondition failure and MUST NOT attempt to compute overlays.

---

### 2.4 Required sealed inputs for S4

Given a valid S0 gate, S4’s **input universe** is the subset of `sealed_inputs_5A` rows that are in-bounds for S4.

S4 MUST be able to resolve the following artefacts for this `(manifest_fingerprint, parameter_hash, scenario_id)`:

#### 2.4.1 Baseline & shape artefacts (from S1–S3)

* `merchant_zone_profile_5A`

  * `owner_segment="5A"`, `role="model"`, `status="REQUIRED"`, `read_scope="ROW_LEVEL"`.

* `shape_grid_definition_5A`

  * `owner_segment="5A"`, `role="model_config"`, `status="REQUIRED"`, `read_scope="ROW_LEVEL"`.

* `class_zone_shape_5A`

  * `owner_segment="5A"`, `role="model"`, `status="REQUIRED"`, `read_scope="ROW_LEVEL"`.

* `merchant_zone_baseline_local_5A`

  * `owner_segment="5A"`, `role="model"`, `status="REQUIRED"`, `read_scope="ROW_LEVEL"`.

These rows MUST exist in `sealed_inputs_5A` with valid `schema_ref`, `path_template`, `partition_keys`, and `sha256_hex`. If any required baseline/shape artefact is absent or unusable, S4 MUST fail with a required-input error.

#### 2.4.2 Scenario & calendar configuration

S4 MUST also resolve scenario and calendar artefacts for the active `scenario_id`, e.g.:

* **Scenario metadata**

  * Artefact(s) describing `scenario_id`, `scenario_type`, horizon (start/end), and high-level tags.
  * Typically marked with `role="scenario_config"`, `status="REQUIRED"`.

* **Scenario calendar** (names illustrative, but semantics binding)

  * Tables or configs such as:

    * `scenario_calendar_5A` — list of events with:

      * event type (holiday, payday, campaign, outage, stress-spike, etc.),
      * time range(s) (e.g. local dates/times or UTC),
      * scope (global, per country/zone, per segment, per merchant set).
  * Marked `role="scenario_calendar"` (or similar), `status="REQUIRED"`.

If S4 is scenario-aware but cannot resolve scenario/calendar configs for the current `scenario_id`, it MUST fail; there is no valid way to “guess” overlays.

#### 2.4.3 Overlay policies

S4 MUST have overlay policies describing **how** events affect intensities, e.g.:

* `scenario_overlay_policy_5A`

  * Determine:

    * for each event type and scope, how to produce a multiplicative factor or additive modifier,
    * how to combine multiple events at the same bucket (e.g. multiply, prioritise, clamp).

* (Optional) `overlay_ordering_policy_5A`

  * Details precedence / layering rules if multiple policies apply.

These artefacts MUST:

* appear in `sealed_inputs_5A` with `owner_segment="5A"`, `role="policy"`,
* be marked `status="REQUIRED"` (if S4 relies on them),
* validate against their schemas (`schemas.5A.yaml` / `schemas.layer2.yaml`),
* have `read_scope` that allows S4 to read their contents.

If required overlay policies are missing or schema-invalid, S4 MUST abort with a policy-missing error.

#### 2.4.4 Horizon grid configuration

S4 MUST know the structure of its **horizon time grid**, which may be:

* local-time grid (e.g. `(local_date, local_bucket_index)`), and/or
* UTC grid (e.g. `(utc_bucket_index)` or `(utc_date, utc_bucket_within_date)`).

This can be encoded in:

* a specific `scenario_horizon_config_5A` artefact, or
* a more general Layer-2 horizon config, referenced in `sealed_inputs_5A` with appropriate `role` and `status`.

This config MUST define at least:

* horizon start and end (dates/times),
* bucket duration,
* how horizon buckets map to:

  * local `day_of_week + time_of_day` / S2 grid indices, and
  * (if applicable) UTC horizon buckets.

If such horizon configuration is missing or inconsistent, S4 MUST fail; it MUST NOT hard-code ad-hoc horizons.

---

### 2.5 Permitted but optional sealed inputs

S4 MAY also use artefacts in `sealed_inputs_5A` marked as `status="OPTIONAL"`, such as:

* Additional reference tables for:

  * regional or merchant segment groupings used for event scoping,
  * special-day classifications (e.g. “semi-holiday”, “shoulder_days”).
* Diagnostic configs:

  * stricter/warnings-only numeric tolerances,
  * debug overlay breakdown settings.

Rules:

* Optional inputs MAY refine overlay factors or drive extra diagnostics, but:

  * their absence MUST NOT prevent S4 from producing valid scenario intensities,
  * they MUST NOT change core semantics in a way that breaks downstream assumptions without a spec/param pack change.

---

### 2.6 Authority boundaries for S4 inputs

The following boundaries are **binding**:

1. **`sealed_inputs_5A` as the exclusive input catalogue**

   * S4 MUST NOT read any dataset or config not listed in `sealed_inputs_5A` for this `manifest_fingerprint`, even if it exists physically.
   * Every artefact S4 consumes MUST be declared and sealed via S0.

2. **S3 as baseline authority**

   * `merchant_zone_baseline_local_5A` is the **only** source of baseline λ for S4.
   * S4 MUST NOT recompute base intensities from S1/S2; it only multiplies `λ_base_local` by overlay factors.

3. **S2 as grid authority**

   * `shape_grid_definition_5A` defines the local-week grid that S4 uses to map from weekly baselines to the horizon.
   * S4 MUST NOT redefine the local-week grid or bucket semantics; any change MUST happen via S2 time-grid policies and a new `parameter_hash`.

4. **Scenario calendar & overlay policies as event authority**

   * Scenario calendar artefacts sealed by S0 are the only authority for “what events happen when, and for whom”.
   * Overlay policies are the only authority for mapping events → multiplicative/additive factors.
   * S4 MUST NOT:

     * infer holidays or paydays from external world state,
     * invent overlay semantics outside what policies declare.

5. **No direct Layer-1 reads**

   * S4 MUST NOT read Layer-1 fact tables (e.g. transactions, sites, routing artefacts, civil-time surfaces) directly.
   * Any necessary information from Layer-1 must flow via S1–S3 outputs or validated configs already in `sealed_inputs_5A`.

6. **No out-of-band configuration**

   * S4 MUST NOT alter its behaviour based on environment variables, CLI flags, or wall-clock that are not represented in:

     * `parameter_hash`, `scenario_id`, and
     * artefacts listed in `sealed_inputs_5A`.

Any change that affects calendar/scenario overlays MUST be expressed by:

* updating scenario/overlay policies & calendar artefacts,
* minting a new parameter pack (`parameter_hash`) and, if needed, new `manifest_fingerprint`, and
* re-running S0–S4/S5 under those identities.

Within these preconditions and boundaries, 5A.S4 operates in a fully sealed, catalogue-defined world: S0 says *what exists and is trusted*, S1–S3 provide baseline structures, scenario configs say *what happens when*, and S4’s job is purely to apply those overlays deterministically to produce scenario-aware intensity surfaces.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **exactly what 5A.S4 may read**, how those inputs are resolved, and which upstream components are authoritative for which facts. All rules here are **binding**.

5A.S4 is **RNG-free** and **catalogue-driven**: it can only use inputs that are:

* sealed by S0 in `sealed_inputs_5A` for this `manifest_fingerprint`, and
* produced by S1–S3 or declared as 5A scenario/overlay configs.

It MUST NOT read arbitrary Layer-1 data or unsealed artefacts.

---

### 3.1 Input categories (high-level)

S4 has five logical input categories:

1. **Control-plane inputs from S0**
   – run identity, upstream status, and sealed universe.

2. **Baseline & shape surfaces from S1–S3**
   – domain, classes, baseline λ, and local-week grid.

3. **Scenario & calendar configuration**
   – what events happen when, and for whom.

4. **Overlay policies**
   – how events are turned into multiplicative factors and combined.

5. **Horizon grid & (optional) civil-time mapping**
   – how the scenario horizon is discretised and mapped to the baseline local-week grid (and optionally to UTC).

All of these MUST be discovered via `sealed_inputs_5A` and resolved via dataset dictionaries + artefact registries.

---

### 3.2 Control-plane inputs from S0

#### 3.2.1 `s0_gate_receipt_5A`

**Role**

* Provides the identity & gating context for the run:

  * `parameter_hash` for the parameter pack.
  * `manifest_fingerprint` for the world.
  * `scenario_id` (or scenario pack ID).
  * `verified_upstream_segments` for 1A–3B.

**Authority boundary**

* S4 MUST treat `s0_gate_receipt_5A` as the **only authority** for:

  * which `(parameter_hash, manifest_fingerprint, scenario_id)` it is operating under,
  * whether upstream Layer-1 is `"PASS"`.

* S4 MUST NOT try to re-derive upstream status by rehashing Layer-1 bundles; it trusts S0’s verdict.

#### 3.2.2 `sealed_inputs_5A`

**Role**

* Describes the **entire set of artefacts** Segment 5A may read for this `manifest_fingerprint`:

  * `owner_segment`, `artifact_id`, `role`, `status`, `read_scope`,
  * `schema_ref`, `path_template`, `sha256_hex`.

**Authority boundary**

* S4 MUST:

  * build its list of inputs **only** from rows in `sealed_inputs_5A`, and
  * respect `status` (`"REQUIRED"`, `"OPTIONAL"`), `read_scope` (`"ROW_LEVEL"`, `"METADATA_ONLY"`).

* Any dataset/config not listed in `sealed_inputs_5A` for this fingerprint is **out-of-bounds**, even if it exists in storage.

---

### 3.3 Baseline & shape surfaces from S1–S3

These are the only modelling surfaces S4 may use as *inputs* to overlays.

#### 3.3.1 `merchant_zone_profile_5A` (S1)

**Logical input**

* S1 output containing per-merchant×zone profiles:

  * `merchant_id`
  * zone representation (`legal_country_iso` + `tzid`, or `zone_id`)
  * `demand_class` (+ optional subclass/profile)
  * base scale fields (e.g. `weekly_volume_expected`, `scale_factor`)
  * optional channel dimension.

**Authority boundary**

* S4 may use `merchant_zone_profile_5A` **only** for:

  * reference identity (which merchants/zones exist), and
  * cross-checking that S3 baselines cover the same domain.

* S4 MUST NOT:

  * reclassify merchants/zones,
  * re-estimate base scales or reinterpret S1’s class/scale semantics.

#### 3.3.2 `shape_grid_definition_5A` (S2)

**Logical input**

* S2 output defining the **local-week grid**:

  * `parameter_hash`, `scenario_id`
  * `bucket_index ∈ [0..T_week−1]`
  * `local_day_of_week`, `local_minutes_since_midnight`
  * `bucket_duration_minutes`.

**Authority boundary**

* This grid is the **only definition** of:

  * what “bucket k in a local week” means, and
  * how `(day_of_week, time_of_day)` are discretised.

* S4 MUST:

  * use this grid to map horizon buckets back to baseline buckets;
  * NOT invent an alternative local-week discretisation.

Any change to the local-week structure MUST occur via S2 policy + `parameter_hash`, not by code in S4.

#### 3.3.3 `class_zone_shape_5A` (S2)

**Logical input**

* S2 unit-mass shapes per `(demand_class, zone[, channel], bucket_index)`:

  * `demand_class`
  * zone representation (consistent with S1/S3)
  * optional `channel` / `channel_group`
  * `bucket_index`
  * `shape_value` (fraction of weekly mass, Σ=1 per class×zone).

**Authority boundary**

* S4 may use `class_zone_shape_5A` only if it needs class/zone shape metadata (e.g. sanity checks or shape-aware overlay rules).

* S4 MUST NOT:

  * re-normalise or alter shapes;
  * redefine what a “unit week” looks like.

S2 remains the **shape authority**; S4 works *on top of* S3 baselines, not on shapes directly.

#### 3.3.4 `merchant_zone_baseline_local_5A` (S3)

**Logical input**

* S3 baseline per `(merchant, zone[, channel], local_week_bucket)`:

  * `lambda_local_base(m,z[,ch],k)`.

**Authority boundary**

* `merchant_zone_baseline_local_5A` is the **only baseline intensity surface** S4 may use.

* S4 MUST:

  * treat `lambda_local_base` as authoritative;
  * never re-compute `scale × shape` from S1/S2;
  * never adjust baseline curves other than via documented overlay factors.

---

### 3.4 Scenario & calendar configuration

These define **what events happen when and for whom**.

#### 3.4.1 Scenario metadata

**Logical input**

* Scenario-level configs sealed in `sealed_inputs_5A`, e.g.:

  * `scenario_id`, `scenario_type` (baseline vs stress),
  * horizon start/end (`horizon_start_utc`, `horizon_end_utc`, or local equivalents),
  * tags (e.g. `"black_friday"`, `"peak_online"`).

**Authority boundary**

* Scenario configs are the only authority for:

  * which scenario S4 operates under,
  * what horizon to cover, and
  * high-level scenario semantics used by overlay policies.

S4 MUST NOT switch scenarios via ad-hoc configuration (env vars, CLI flags) that are not reflected in these artefacts.

#### 3.4.2 Scenario calendar events

**Logical input**

* One or more artefacts encoding calendar events, for example:

  * `scenario_calendar_5A` or equivalent, with rows like:

    * `event_type` (holiday, payday, campaign, outage, stress_shock, etc.),
    * `scope` (global, per country/zone, per merchant/segment),
    * `start_local` / `end_local` or UTC time ranges,
    * any additional parameters (e.g. uplift magnitude hints, labels).

**Authority boundary**

* These are the **only source** of event timing and scope.

* S4 MUST:

  * derive its event surfaces from these tables/configs;
  * NOT infer holidays/paydays from raw dates or external world knowledge.

If an event is not in the calendar, S4 MUST NOT pretend it exists.

---

### 3.5 Overlay policies

Overlay policies define **how events turn into multipliers** and how multiple effects combine.

#### 3.5.1 `scenario_overlay_policy_5A` (name illustrative)

**Logical content (conceptual)**

* Rules for mapping event surfaces → overlay factors:

  * per event type (holiday, payday, campaign, outage, stress),
  * per scope (global, region, zone, merchant class, merchant),
  * per time context (pre-event lead-in, event period, post-event decay).

* Rules for combining overlapping effects:

  * e.g. multiply all factors, or
  * apply precedence / caps (e.g. “outage → factor=0, regardless of other events”).

**Authority boundary**

* This policy is the **only authority** for how overlay factors are computed.

* S4 MUST:

  * implement overlay logic strictly according to this policy;
  * not add unconfigured multipliers;
  * not change the combination law without a spec/policy update.

#### 3.5.2 Other overlay-related configs (optional)

Examples:

* `overlay_ordering_policy_5A` — explicit precedence rules (e.g. outages override all).
* `scenario_overlay_validation_policy_5A` — numeric bounds or warning thresholds for overlay factors.

These configs may influence:

* how S4 evaluates overlay factors, and
* what counts as a numeric violation.

They MUST be read-only and policy-driven.

---

### 3.6 Horizon grid & civil-time mapping configs

S4 moves from **weekly templates** to a concrete **horizon**.

#### 3.6.1 Horizon grid definition

**Logical input**

* One or more artefacts defining the horizon grid, e.g.:

  * `scenario_horizon_config_5A`, or
  * shared Layer-2 horizon config.

**Content (conceptual)**

* Horizon start and end:

  * `horizon_start_local` / `horizon_end_local` (per zone), or
  * `horizon_start_utc` / `horizon_end_utc` plus mapping rules.

* Bucketisation:

  * horizon bucket duration,
  * representation of buckets (e.g. `local_date + bucket_within_day`, or single `local_horizon_bucket_index` and mapping to date/time).

* Mapping to S2 grid:

  * how each horizon bucket `(local_date, time_of_day)` maps to a local-week bucket `k` via `(day_of_week, local_minutes_since_midnight)`.

**Authority boundary**

* This config is the only authority for how the horizon is discretised.

* S4 MUST NOT:

  * invent a different horizon grid;
  * modify bucket durations or mapping outside what the config describes.

#### 3.6.2 Civil-time mapping (for UTC, optional)

If S4 outputs a UTC scenario surface, it MAY additionally consume civil-time artefacts sealed via S0, for example:

* `site_timezones` and `tz_timetable_cache` from 2A (referenced via `sealed_inputs_5A` as cross-layer reference data).

Authority boundary:

* These are the authoritative sources for mapping local times to UTC and handling DST transitions.

* S4 MUST:

  * use them only via `sealed_inputs_5A`,
  * obey 2A’s time-mapping semantics (gaps/folds, offset changes),
  * NOT implement its own independent tz logic.

---

### 3.7 Authority boundaries & out-of-bounds inputs

The following high-level boundaries are **binding**:

1. **Exclusive reliance on `sealed_inputs_5A`**

   * S4 MUST NOT read any dataset/config not present as a row in `sealed_inputs_5A` for this fingerprint.

2. **S3 as baseline authority**

   * Baselines MUST come only from `merchant_zone_baseline_local_5A`.
   * S4 MUST NOT recompute or override baseline λ with its own `scale × shape` logic.

3. **S2 as grid authority**

   * The S2 grid (`shape_grid_definition_5A`) defines local-week buckets; S4 MUST NOT change bucket semantics.

4. **Scenario calendar & overlay policy as event authority**

   * S4 MUST not hard-code event dates or behaviour; everything flows from scenario calendar + overlay policies.
   * If an event or behaviour is not configured, S4 MUST either:

     * treat it as “no effect”, or
     * fail clearly, depending on policy — but never invent logic.

5. **No direct Layer-1 facts**

   * S4 MUST NOT read Layer-1 egress (transactions, sites, routing artefacts, raw tzdb) directly; it sees Layer-1 only through 5A outputs and sealed cross-layer references.

6. **No out-of-band behaviour**

   * S4 MUST NOT change behaviour based on environment variables, CLI flags, or wall-clock, unless those knobs are represented in:

     * `parameter_hash`, `scenario_id`, and
     * policy/calendar/horizon artefacts in `sealed_inputs_5A`.

Within these boundaries, 5A.S4’s inputs are fully sealed and well-scoped: S0 defines the world, S1–S3 define baseline structure, scenario configs say what happens when, and overlay policies say how to turn that into overlay factors.

---

## 4. Outputs (datasets) & identity *(Binding)*

This section defines the **data products** of **5A.S4 — Calendar & Scenario Overlays** and how they are identified, partitioned, and keyed. All rules here are **binding**.

S4 outputs are **world + parameter-pack + scenario scoped**:

* **World**: `manifest_fingerprint` (ties back to S0/S1/S3).
* **Parameter pack**: `parameter_hash`.
* **Scenario**: `scenario_id`.

They are **not** seed- or run-scoped, and they sit *on top of* S3 baselines.

---

### 4.1 Overview of outputs

5A.S4 MUST produce one **required** modelling dataset, and MAY produce up to two **optional** modelling datasets:

1. **`merchant_zone_scenario_local_5A` *(required)***

   * Per `(merchant, zone[, channel], local_horizon_bucket)` **scenario-adjusted local-time intensity**
     `lambda_local_scenario(m, z[,ch], h)`.
   * This is the **primary output** that S5 and 5B will consume.

2. **`merchant_zone_overlay_factors_5A` *(optional)***

   * Per `(merchant, zone[, channel], local_horizon_bucket)` the **composite overlay factor**
     `F_overlay(m, z[,ch], h)` applied on top of S3 baselines, with optional breakdown by event-type.
   * Convenience surface for diagnostics, explainability, and S5 validation.

3. **`merchant_zone_scenario_utc_5A` *(optional)***

   * Per `(merchant, zone[, channel], utc_horizon_bucket)` **scenario-adjusted UTC-time intensity**
     `lambda_utc_scenario(m, z[,ch], h_utc)`, if the design elects to pre-project local scenario curves into a UTC horizon in S4.
   * Entirely optional; 5B could instead map local λ_scenario to UTC itself.

No other S4 datasets are required. Any additional debugging surfaces MUST be clearly marked as diagnostic-only and MUST NOT be required by downstream segments.

---

### 4.2 `merchant_zone_scenario_local_5A` (required)

#### 4.2.1 Semantic role

`merchant_zone_scenario_local_5A` is the **core product** of S4.

For each in-scope `(merchant, zone[, channel])` and each **local horizon bucket** `h` in the scenario window, it provides:

* `lambda_local_scenario(m, z[,ch], h)` — the **scenario-adjusted expected local-time intensity** for that merchant×zone[×channel] in that bucket, obtained by:

```text
lambda_local_scenario = lambda_base_local × F_overlay
```

where:

* `lambda_base_local(m, z[,ch], k)` comes from S3, and
* `F_overlay(m, z[,ch], h)` is a deterministic multiplier from scenario/calendar events and overlay policy, and
* `h` is a horizon bucket that maps to a local-week bucket index `k` via the time-grid/horizon configuration.

Units (e.g. “expected arrivals per local horizon bucket”) MUST be defined in the S4 spec and baseline/overlay policies and are binding.

#### 4.2.2 Domain & cardinality

For a given triple `(parameter_hash, manifest_fingerprint, scenario_id)` and chosen **local horizon grid**:

* Let `D_S3` be S3’s in-scope baseline domain:

  ```text
  D_S3 = { (merchant_id, zone_representation[, channel]) }
  ```

* Let `H_local` be the set of local horizon buckets, e.g.:

  ```text
  H_local = { h | 0 ≤ h < H } 
  ```

  or the set of `(local_date, local_bucket_within_date)` pairs defined by the horizon config.

The domain of `merchant_zone_scenario_local_5A` MUST be:

```text
DOMAIN_S4_local =
  { (merchant_id, zone_representation[, channel], h) 
    | (merchant, zone[,channel]) ∈ D_S3
      and h ∈ H_local }
```

That implies:

* For every `(merchant, zone[,channel]) ∈ D_S3`, `merchant_zone_scenario_local_5A` MUST contain **exactly one row per local horizon bucket** `h ∈ H_local`.
* No `(merchant, zone[,channel])` that is out-of-scope in S3 may appear in S4.

#### 4.2.3 Identity & keys

**Partitioning**

`merchant_zone_scenario_local_5A` is **world + scenario scoped**:

* `partition_keys: ["fingerprint","scenario_id"]`

where:

* `fingerprint={manifest_fingerprint}`,
* `scenario_id` is the active scenario.

**Primary key (logical)**

Within a given `(fingerprint, scenario_id)` partition, the primary key MUST be:

* If zone is represented as `(legal_country_iso, tzid)`:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - merchant_id
    - legal_country_iso
    - tzid
    - local_horizon_bucket   # exact field name depends on the chosen horizon grid representation
  ```

* If a combined `zone_id` is used:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - merchant_id
    - zone_id
    - local_horizon_bucket
  ```

If `channel` or `channel_group` is part of the modelling domain, it MUST be included in the PK as well.

**Embedded identity fields**

Each row MUST embed:

* `manifest_fingerprint` — non-null; MUST equal the partition token.
* `parameter_hash` — non-null; MUST equal S0’s `parameter_hash`.
* `scenario_id` — non-null; MUST equal the partition token.

Any mismatch between tokens and embedded values MUST be treated as invalid.

#### 4.2.4 Core columns (conceptual)

Exact types are set in §5; semantically each row MUST include:

* Identity:

  * `manifest_fingerprint`
  * `parameter_hash`
  * `scenario_id`

* Merchant & zone:

  * `merchant_id`
  * zone representation (`legal_country_iso` + `tzid`, or `zone_id`)
  * optional `channel` / `channel_group`

* Time key:

  * a local horizon bucket key, e.g.:

    * `local_horizon_bucket_index`, **or**
    * `(local_date, local_bucket_within_date)`
      with a clear mapping to local time (and thus to S2’s local-week grid).

* Scenario intensity:

  * `lambda_local_scenario` — numeric; non-null; MUST be finite and ≥ 0.

* Optional metadata:

  * `overlay_factor_total` (if not broken out separately),
  * `s4_spec_version` — required spec version field,
  * optional echoes of S3 baseline (`lambda_base_local`, base scale) for audit and validation.

---

### 4.3 `merchant_zone_overlay_factors_5A` (optional)

#### 4.3.1 Semantic role

If implemented, `merchant_zone_overlay_factors_5A` makes the **multiplicative overlay factors explicit**:

* For each `(merchant, zone[, channel], local_horizon_bucket)` it records the **combined factor**:

  ```text
  F_overlay(m, z[,ch], h)
  ```

  such that:

  ```text
  lambda_local_scenario(m,z[,ch],h) =
    lambda_base_local(m,z[,ch],k) × F_overlay(m,z[,ch],h)
  ```

It MAY also carry a **breakdown** by event type (e.g. holiday, payday, campaign, outage) for diagnostics and explainability.

#### 4.3.2 Domain & identity

For a given `(parameter_hash, manifest_fingerprint, scenario_id)` and local horizon grid `H_local`:

* Domain MUST match that of `merchant_zone_scenario_local_5A`:

  ```text
  DOMAIN_overlay = DOMAIN_S4_local
  ```

Partitioning:

* `partition_keys: ["fingerprint","scenario_id"]`

Primary key:

* same as `merchant_zone_scenario_local_5A` (same key fields).

Embedded identity fields:

* `manifest_fingerprint`, `parameter_hash`, `scenario_id` with the same equality rules.

#### 4.3.3 Core fields (conceptual)

At minimum:

* `overlay_factor_total` — numeric; non-null; MUST be ≥ 0, representing the multiplicative factor applied to `lambda_base_local`.

Optional:

* per-event-type factors (e.g. `factor_holiday`, `factor_payday`, `factor_campaign`, `factor_outage`, `factor_stress`), if overlay policy decomposes effects in this way.
* `overlays_applied` — compact list or bitmask of which event types contributed to `overlay_factor_total`.
* `s4_spec_version` — if not already echoed from the scenario-intensity dataset.

This dataset MUST be a **pure function** of S3 baselines, scenario calendar/event surfaces, and overlay policies; no new randomness or external inputs may appear here.

---

### 4.4 `merchant_zone_scenario_utc_5A` (optional)

#### 4.4.1 Semantic role

If the design elects to pre-project scenario intensities to UTC in S4, `merchant_zone_scenario_utc_5A` represents:

* the same scenario-adjusted intensities as `merchant_zone_scenario_local_5A`, but expressed on a **UTC horizon grid**:

  ```text
  lambda_utc_scenario(m, z[,ch], h_utc)
  ```

where `h_utc` is a UTC bucket index (or a `(utc_date, utc_bucket_within_date)` pair) defined in a Layer-2 horizon config.

This is optional: 5B could work entirely in local time and map to UTC internally.

#### 4.4.2 Domain & identity

For a given `(parameter_hash, manifest_fingerprint, scenario_id)` and a chosen UTC horizon grid `H_utc`:

* Domain:

  ```text
  DOMAIN_S4_utc =
    { (merchant_id, zone_representation[, channel], h_utc) 
      | (merchant, zone[,channel]) ∈ D_S3
        and h_utc ∈ H_utc }
  ```

Partitioning:

* `partition_keys: ["fingerprint","scenario_id"]`
  (optional additional UTC horizon partition(s), such as `utc_date`, MAY be introduced but then become binding).

Primary key (illustrative if using explicit `(country,tz)`):

```yaml
primary_key:
  - manifest_fingerprint
  - scenario_id
  - merchant_id
  - legal_country_iso   # or zone_id
  - tzid                # omit if zone_id is used
  - utc_horizon_bucket  # or (utc_date, utc_bucket_within_date)
```

Embedded identity fields:

* `manifest_fingerprint`, `parameter_hash`, `scenario_id` with the same requirements as for local outputs.

#### 4.4.3 Core columns (conceptual)

Each row MUST include:

* Identity:

  * `manifest_fingerprint`
  * `parameter_hash`
  * `scenario_id`

* Merchant & zone:

  * `merchant_id`,
  * zone representation,
  * optional `channel` / `channel_group`.

* UTC time key:

  * e.g. `utc_horizon_bucket_index`, **or** `(utc_date, utc_bucket_within_date)`.

* Scenario intensity:

  * `lambda_utc_scenario` — numeric; non-null; MUST be ≥ 0 and finite.

* Optional metadata:

  * `s4_spec_version`
  * mapping hints to local/horizon bucket(s) used in the projection (e.g. for debugging DST behaviour).

This dataset MUST be a deterministic mapping of `lambda_local_scenario` (plus 2A civil-time mapping) onto a UTC grid; no additional stochasticity or policy deviations are allowed.

---

### 4.5 Relationship to upstream & downstream datasets

#### 4.5.1 Upstream foreign keys

`merchant_zone_scenario_local_5A` MUST have:

* a foreign key back to S3 baselines:

  ```text
  merchant_zone_scenario_local_5A.
    (manifest_fingerprint, scenario_id, merchant_id, zone_representation[,channel])
    → merchant_zone_baseline_local_5A.
      (manifest_fingerprint, scenario_id, merchant_id, zone_representation[,channel])
  ```

* and a linkage to S2’s grid via the horizon–week mapping (though not necessarily a direct FK; the mapping is encoded in horizon config and grid metadata).

If `merchant_zone_overlay_factors_5A` is present, it MUST:

* share the same (world+scenario+domain) keys as `merchant_zone_scenario_local_5A` so that:

  ```text
  lambda_local_scenario = lambda_base_local × overlay_factor_total
  ```

can be reconstructed exactly.

If `merchant_zone_scenario_utc_5A` is present, it MUST:

* be consistent with:

  * `merchant_zone_scenario_local_5A` via the 2A civil-time mapping, and
  * any Layer-2 UTC grid definitions.

#### 4.5.2 Downstream obligations

Downstream components (notably 5A.S5 and 5B) MUST:

* treat `merchant_zone_scenario_local_5A` as the **authoritative scenario-intensity surface** for the given `(parameter_hash, manifest_fingerprint, scenario_id)`.
* use `merchant_zone_overlay_factors_5A` (if present) only as a diagnostic or as a convenient decomposition of `F_overlay`; it MUST NOT contradict the relationship between S3 baselines and S4 intensities.
* treat `merchant_zone_scenario_utc_5A` (if present) as a **projection** of local λ_scenario onto a UTC grid, not as an independent source of semantics.

---

### 4.6 Control-plane vs modelling outputs

S4 produces **modelling datasets only**; it does not produce:

* control-plane artefacts (no new gate receipts or sealed-input inventories),
* or `_passed.flag` (which is the job of 5A.S5).

All S4 outputs:

* are deterministic functions of S3 baselines, S2 grids, scenario/calendar artefacts, overlay policies, `(parameter_hash, manifest_fingerprint, scenario_id)`, and horizon configs;
* are partitioned by `fingerprint` and `scenario_id`, with `parameter_hash` embedded;
* are immutable once written, except for idempotent re-runs that produce identical content.

Within this identity model, S4 provides the single, world- and scenario-specific **scenario-intensity surface** that S5 validates and 5B uses to realise concrete arrival processes.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

Contracts for the S4 scenario projections are defined in the 5A schema pack/dictionary/registry. Outputs:

1. `merchant_zone_scenario_local_5A`
2. `merchant_zone_overlay_factors_5A`
3. `merchant_zone_scenario_utc_5A` (optional)

| Dataset | Schema anchor | Dictionary id | Registry key |
|---|---|---|---|
|`merchant_zone_scenario_local_5A`|`schemas.5A.yaml#/model/merchant_zone_scenario_local_5A`|`merchant_zone_scenario_local_5A`|`mlr.5A.model.merchant_zone_scenario_local`|
|`merchant_zone_overlay_factors_5A`|`schemas.5A.yaml#/model/merchant_zone_overlay_factors_5A`|`merchant_zone_overlay_factors_5A`|`mlr.5A.model.merchant_zone_overlay_factors`|
|`merchant_zone_scenario_utc_5A` (opt.)|`schemas.5A.yaml#/model/merchant_zone_scenario_utc_5A`|`merchant_zone_scenario_utc_5A`|`mlr.5A.model.merchant_zone_scenario_utc`|

Binding notes:

- Dictionary partition rules (`fingerprint, scenario_id`) and PKs enforce deterministic ordering; S4 must follow them exactly.
- Schema pack is the only source of truth for columns (local/UTC buckets, overlays, audit fields).
- Optional UTC surface may be omitted; when present it must be derived deterministically from the local surface and 2A civil-time law.
- Registry dependencies (S3 baselines, overlay configs, sealed inputs) bound what S4 may read.


## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section specifies the **ordered, deterministic algorithm** for **5A.S4 — Calendar & Scenario Overlays**. Implementations MUST follow these steps and invariants.

5A.S4 is **purely deterministic** and MUST NOT consume RNG.

---

### 6.1 High-level invariants

5A.S4 MUST satisfy:

1. **RNG-free**

   * MUST NOT call any RNG primitive.
   * MUST NOT write to `rng_audit_log`, `rng_trace_log`, or any RNG event streams.

2. **Catalogue-driven**

   * MUST discover all inputs via:

     * `s0_gate_receipt_5A`,
     * `sealed_inputs_5A`,
     * dataset dictionaries + artefact registries.
   * MUST NOT use hard-coded filesystem paths, directory scanning, or network calls for discovery.

3. **Upstream-respecting**

   * MUST treat:

     * `merchant_zone_baseline_local_5A` (S3) as the **sole** baseline intensity surface.
     * `shape_grid_definition_5A` (S2) as the **sole** local-week grid.
     * Scenario calendar artefacts as the **sole** description of events.
     * Overlay policies as the **sole** definition of how events map to multipliers.
   * MUST NOT recompute scale×shape, re-derive shapes, or override baseline semantics.

4. **Domain completeness**

   * For each in-scope `(merchant, zone[, channel])` in S3’s domain and each bucket in the local horizon, S4 MUST compute exactly one `lambda_local_scenario` (and exactly one `overlay_factor_total` for that bucket if the overlay table is materialised).

5. **No partial outputs**

   * On failure, S4 MUST NOT commit partial S4 outputs to canonical locations.
   * On success, `merchant_zone_scenario_local_5A` (and any optional S4 outputs) MUST be present, schema-valid, and complete.

---

### 6.2 Step 1 — Load gate, sealed inputs & validate S1–S3 + configs

**Goal:** Ensure the world, parameter pack and upstream S1–S3 surfaces, plus scenario configs/policies, are valid for this run.

**Inputs:**

* `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id` (run context).
* `s0_gate_receipt_5A`, `sealed_inputs_5A`.
* S1/S2/S3 outputs:

  * `merchant_zone_profile_5A`
  * `shape_grid_definition_5A`
  * `class_zone_shape_5A` (for sanity / optional use)
  * `merchant_zone_baseline_local_5A`
* S4 configs/policies:

  * scenario metadata + calendar (`scenario_calendar_5A` etc.),
  * overlay policies (`scenario_overlay_policy_5A`, etc.),
  * horizon grid config (`scenario_horizon_config_5A` or equivalent).

**Procedure:**

1. **S0 validation**

   * Resolve `s0_gate_receipt_5A`, `sealed_inputs_5A` for `fingerprint={manifest_fingerprint}` via dictionary/registry.
   * Validate both against their schemas.
   * Check `s0_gate_receipt_5A.parameter_hash == parameter_hash`.
   * Check all rows in `sealed_inputs_5A` have:

     * `manifest_fingerprint == manifest_fingerprint`,
     * `parameter_hash == parameter_hash`.
   * Recompute `sealed_inputs_digest` from `sealed_inputs_5A` and confirm equality with the digest in the receipt.

2. **Upstream Layer-1 status**

   * From `s0_gate_receipt_5A.verified_upstream_segments`, ensure `status="PASS"` for 1A, 1B, 2A, 2B, 3A, 3B.
   * If any is `"FAIL"` or `"MISSING"`, abort (`S4_UPSTREAM_NOT_PASS`).

3. **S1–S3 presence & identity**

   * Resolve `merchant_zone_profile_5A`, `shape_grid_definition_5A`, `class_zone_shape_5A`, `merchant_zone_baseline_local_5A` via `sealed_inputs_5A` and dictionary/registry.
   * Validate each dataset against its schema anchor.
   * Check embedded `parameter_hash`, `manifest_fingerprint`, `scenario_id` match the run context where applicable.
   * For S1: verify no duplicate `(merchant_id, zone_representation[,channel])`.
   * For S2 grid: verify `bucket_index` is contiguous `[0..T_week-1]` per `(parameter_hash, scenario_id)`.
   * For S3 baselines: verify PK uniqueness and `lambda_local_base ≥ 0`.

4. **Scenario & horizon configuration**

   * From `sealed_inputs_5A`, resolve scenario metadata and horizon config artefacts for `scenario_id`.
   * Validate them against their schemas; extract:

     * horizon start/end;
     * local horizon bucket duration;
     * representation of local horizon buckets (index vs date+slot);
     * mapping rules to local week (e.g. via `(day_of_week, local_minutes_since_midnight)`).

5. **Overlay policies**

   * Resolve `scenario_overlay_policy_5A` (and any related configs) from `sealed_inputs_5A`.
   * Validate schema and internal consistency (e.g. known event types, scopes, combination rules).

6. **Scenario calendar**

   * Resolve scenario calendar artefacts (e.g. `scenario_calendar_5A`) from `sealed_inputs_5A`.
   * Validate:

     * event types recognised by overlay policy;
     * event time ranges within or around horizon as expected;
     * event scopes (global/region/zone/merchant) syntactically valid.

**Invariants:**

* If any required dataset/config fails validation or identity checks, S4 MUST abort with a suitable error (`S4_GATE_OR_S3_INVALID`, `S4_REQUIRED_INPUT_MISSING`, `S4_REQUIRED_POLICY_MISSING`) and MUST NOT write outputs.
* If all checks pass, S4 may proceed.

---

### 6.3 Step 2 — Construct S4 domain from S3 (`D_S4`)

**Goal:** Determine the exact set of `(merchant, zone[, channel])` that S4 must cover.

**Primary source:** `merchant_zone_baseline_local_5A` (S3).

**Procedure:**

1. Read `merchant_zone_baseline_local_5A` for `fingerprint={manifest_fingerprint}`, `scenario_id={scenario_id}`, projecting:

   * `merchant_id`,
   * zone representation (`legal_country_iso` + `tzid` or `zone_id`),
   * optional `channel` / `channel_group`.

2. Apply any S4-specific policy filters (if defined), e.g.:

   * exclude merchant×zone flagged as “no overlay” or “off-grid” by a config;
   * other filters MUST be explicitly expressed in an S4 policy, not hard-coded.

3. Construct an in-memory set:

   ```text
   D_S4 = {
     (merchant_id, zone_representation[, channel])
     | row in merchant_zone_baseline_local_5A after filters
   }
   ```

4. Optionally cross-check with S1 domain (`merchant_zone_profile_5A`) to ensure no merchant×zone appears in S3 that is not in S1; mismatches SHOULD be treated as upstream misalignment.

**Invariants:**

* `D_S4` is the **sole domain** for S4.
* Every `(merchant, zone[,channel])` in `D_S4` MUST correspond to a unique baseline curve in S3; no duplicates allowed.

---

### 6.4 Step 3 — Build the local horizon grid and mapping to local-week buckets

**Goal:** Define the set of **local horizon buckets** and how each maps back to S2/S3’s local-week grid.

**Inputs:**

* Horizon config (from §6.2).
* `shape_grid_definition_5A` (local-week grid: bucket_index → local time-of-week).

**Procedure:**

1. From horizon config, derive:

   * `H_local` = set of local horizon buckets. Representation options:

     * `local_horizon_bucket_index ∈ [0..H−1]`, **or**
     * `(local_date, local_bucket_within_date)` pairs.
   * For each horizon bucket, derive its **local time anchor**:

     * e.g. `local_day_of_week`, `local_minutes_since_midnight` in some reference week.

2. From `shape_grid_definition_5A` (S2 grid), construct a lookup:

   ```text
   GRID_LOOKUP[local_day_of_week, local_minutes_since_midnight]
     -> bucket_index k
   ```

   resolving to the unique `bucket_index` whose `(local_day_of_week, local_minutes_since_midnight)` matches the horizon bucket’s local time-of-week (e.g. Monday 10:00, Friday 18:30).

3. For each horizon bucket `h ∈ H_local`:

   * Compute local time-of-week for that bucket based on horizon config.

   * Use `GRID_LOOKUP` to find `k = kappa(h)` such that:

     ```text
     bucket_index = k
     has same (local_day_of_week, local_minutes_since_midnight) as horizon bucket h
     ```

   * If no matching `k` exists due to config mismatch, treat as `S4_HORIZON_GRID_INVALID` and abort.

4. Record the mapping:

   ```text
   WEEK_MAP[h] = k
   ```

   which will be used later to map baseline λ from S3’s weekly curve onto the horizon.

**Invariants:**

* For each `h ∈ H_local`, `WEEK_MAP[h]` MUST exist and be unique.
* No horizon bucket may be left unmapped; no horizon bucket may map to an invalid `k`.
* S4 MUST NOT modify S2 grid; any mismatch implies misconfigured horizon/grid policy.

---

### 6.5 Step 4 — Construct event surfaces over the horizon

**Goal:** Determine, for each `(zone, local_horizon_bucket)` (and optionally each merchant), which scenario events apply.

**Inputs:**

* Scenario calendar artefacts (events with type, time range, scope).
* Domain `D_S4` (merchant×zone).
* Local horizon grid `H_local` and each bucket’s local time (from Step 3).

**Procedure:**

1. **Preprocess events by time**

   * For each event in scenario calendar:

     * Convert its time range into local horizon bucket indices (or `(local_date, local_bucket_within_date)` ranges) for the scopes it applies to.
     * If events are specified in UTC, convert to local time for each zone using civil-time mapping rules from horizon config and/or 2A.

2. **Preprocess scopes**

   * For each event, determine where it applies:

     * global scope: all `(merchant, zone)`;
     * regional or country scope: all zones in given region/country;
     * zone scope: specific zones;
     * merchant/segment scope: specific subsets of `merchant_id`s or class labels.

   * Build efficient data structures to query “for this `(merchant, zone)` and horizon bucket `h`, which events are active?”.

3. **Build event surfaces**

   For each `(merchant, zone[,ch]) ∈ D_S4` and each `h ∈ H_local`:

   * Compute `EVENTS[m,z[,ch],h]` = set/list of active events in that bucket (by event_type and possibly instance ID).
   * This set is purely deterministic, based on:

     * the event definitions,
     * the horizon mapping, and
     * the domain membership of `(merchant, zone[,ch])`.

**Invariants:**

* Every event from the scenario calendar that falls into the horizon window and has a scope overlapping `D_S4` MUST appear in the corresponding `EVENTS[m,z[,ch],h]`.
* No event may appear outside its declared time or scope.

If event mapping fails (e.g. malformed time ranges or unknown scopes), S4 MUST treat it as `S4_CALENDAR_ALIGNMENT_FAILED`.

---

### 6.6 Step 5 — Evaluate overlay factors per `(m, z[,ch], h)`

**Goal:** For each domain-horizon point, compute a **deterministic overlay factor** `F_overlay(m,z[,ch],h)` using the overlay policy.

**Inputs:**

* `EVENTS[m,z[,ch],h]` from Step 4.
* `scenario_overlay_policy_5A` and any related configs.

**Procedure:**

For each `(m,z[,ch]) ∈ D_S4` and each `h ∈ H_local`:

1. Initialise:

   ```text
   F = 1.0
   CONTEXT = { scenario traits, merchant traits (if allowed), zone traits }
   ```

2. For each event `e ∈ EVENTS[m,z[,ch],h]`:

   * Using overlay policy, compute an event-specific factor `f_e(m,z[,ch],h)` ≥ 0; this may depend on:

     * event type and parameters (e.g. “holiday”, “salary_day”),
     * scope and merchant/zone traits,
     * time position within event (e.g. ramp-up/ramp-down).

   * Combine `f_e` into `F` according to the policy’s combination rules, e.g.:

     * multiplicative:

       ```text
       F ← F × f_e
       ```

     * or layered with precedence:

       * if event is “outage” and policy says outages override everything:

         * set `F ← 0` and optionally skip combining lower-priority events.
       * else if event has limited impact, `F ← clip(F × f_e)`.

3. After processing all events:

   * Apply global constraints from policy:

     * clamp `F` into `[F_min, F_max]` as configured (e.g. avoid insane uplifts) unless a strict “outage”/“shutdown” semantics says `F=0`.
     * ensure `F` is finite and ≥ 0.

4. Store:

   ```text
   F_overlay[m,z[,ch],h] = F
   ```

**Invariants:**

* For every `(m,z[,ch],h)`, `F_overlay` MUST be finite and ≥ 0.
* Overlay policy is the **only** place where mapping `EVENTS → F_overlay` is defined; S4 MUST NOT embed ad-hoc tweaks beyond those rules.

If overlay factor computation fails (e.g. missing policy entries, NaN/Inf, negative factors), S4 MUST treat it as `S4_OVERLAY_EVAL_FAILED` or `S4_INTENSITY_NUMERIC_INVALID`.

---

### 6.7 Step 6 — Compose scenario intensities from baselines and overlay factors

**Goal:** Compute `lambda_local_scenario(m,z[,ch],h)` by multiplying baseline λ from S3 with overlay factors from Step 5.

**Inputs:**

* `D_S4`, `H_local`.
* Baselines: `merchant_zone_baseline_local_5A`.
* Mapping: `WEEK_MAP[h] = k` from Step 3.
* Overlays: `F_overlay[m,z[,ch],h]` from Step 5.

**Procedure:**

1. Build an efficient index over S3 baselines:

   ```text
   BASE_LOCAL[m,z[,ch],k] = lambda_local_base(m,z[,ch],k)
   ```

   being careful to align zone/channel representation with `D_S4`.

2. For each `(m,z[,ch]) ∈ D_S4` and each `h ∈ H_local`:

   * Find `k = WEEK_MAP[h]` (local-week bucket index).

   * Retrieve baseline intensity:

     ```text
     λ_base = BASE_LOCAL[m,z[,ch],k]
     ```

   * Retrieve overlay factor:

     ```text
     F = F_overlay[m,z[,ch],h]
     ```

   * Compute scenario intensity:

     ```text
     λ_scen = λ_base × F
     ```

   * Apply any numeric safeguards from policy:

     * enforce `λ_scen ≥ 0`;
     * ensure `λ_scen` is finite (no NaN, ±Inf).

   * Store:

     ```text
     LAMBDA_LOCAL_SCEN[m,z[,ch],h] = λ_scen
     ```

3. Optional weekly / horizon-coherence checks:

   * If the overlay policy defines any global invariants (e.g. long-run average uplift should equal 1 for baseline scenarios), S4 MAY compute and check such statistics as part of acceptance criteria (see §8).

**Invariants:**

* For every `(m,z[,ch],h)` in the local horizon domain, `LAMBDA_LOCAL_SCEN` is uniquely defined and ≥ 0.
* No horizon bucket uses a baseline bucket outside `[0..T_week−1]`.
* S4 MUST NOT adjust baseline patterns beyond multiplying by `F_overlay`.

---

### 6.8 Step 7 — Optional UTC projection (`merchant_zone_scenario_utc_5A`)

*(Only applicable if you choose to pre-compute UTC scenario intensities in S4.)*

**Goal:** Map local scenario intensities onto a UTC horizon grid.

**Inputs:**

* `LAMBDA_LOCAL_SCEN[m,z[,ch],h]`.
* Local horizon grid (each `h` has a local time window).
* 2A civil-time mapping artefacts (e.g. `site_timezones`, `tz_timetable_cache`) if needed.
* UTC horizon config (bucket duration, start/end, bucket representation).

**Procedure (conceptual):**

1. From UTC horizon config, construct:

   ```text
   H_utc = { h_utc }
   ```

   with each `h_utc` corresponding to a UTC time window.

2. For each `(m,z[,ch])`:

   * For each local horizon bucket `h`:

     * determine its local time window (start/end local).
     * use zone tz info (from 2A) to map this local window into UTC.
     * determine which `h_utc` buckets intersect that UTC window.

   * For each intersecting `(h,h_utc)` pair:

     * compute time-overlap fraction `w_{h,h_utc} ∈ [0,1]` such that Σ over `h_utc` of `w_{h,h_utc}` equals 1 for a fixed `h` (if full coverage).

     * distribute intensity:

       ```text
       contribution = λ_scen(m,z[,ch],h) × w_{h,h_utc}
       ```

     * accumulate:

       ```text
       LAMBDA_UTC_SCEN[m,z[,ch],h_utc] += contribution
       ```

3. Enforce:

   * `LAMBDA_UTC_SCEN ≥ 0`, finite.
   * Optional invariant: Σ over `h_utc` of `LAMBDA_UTC_SCEN` ≈ Σ over `h` of `LAMBDA_LOCAL_SCEN` (total intensity conserved up to tolerance).

**Invariants:**

* UTC intensities MUST be deterministic functions of local intensities + tz mapping + UTC grid.
* No additional policy multiplication beyond documented behaviour.

If this mapping fails due to horizon/tz config issues, S4 MUST treat it as `S4_HORIZON_GRID_INVALID` or `S4_INTERNAL_INVARIANT_VIOLATION`.

---

### 6.9 Step 8 — Construct S4 output rows

#### 6.9.1 Build `merchant_zone_scenario_local_5A` rows

For each `(m,z[,ch]) ∈ D_S4` and each `h ∈ H_local`:

1. Construct a row with:

   * Identity: `manifest_fingerprint`, `parameter_hash`, `scenario_id`.
   * Merchant & zone: `merchant_id`, zone representation, optional `channel` / `channel_group`.
   * Local horizon time key: `local_horizon_bucket_index` or `(local_date, local_bucket_within_date)`.
   * Intensity: `lambda_local_scenario = LAMBDA_LOCAL_SCEN[m,z[,ch],h]`.
   * Metadata: `s4_spec_version`, optional `overlay_factor_total` and/or `lambda_base_local` echo.

2. Validate each row against `#/model/merchant_zone_scenario_local_5A`.

3. Append to an in-memory collection `SCEN_LOCAL_ROWS`.

After all rows:

* Check cardinality:

  ```text
  |SCEN_LOCAL_ROWS| == |D_S4| × |H_local|
  ```

* Check PK uniqueness under the intended PK ordering.

If any invariants fail, treat as `S4_DOMAIN_ALIGNMENT_FAILED` or `S4_INTENSITY_NUMERIC_INVALID`.

#### 6.9.2 Build `merchant_zone_overlay_factors_5A` rows (optional)

If materialised:

1. For each `(m,z[,ch],h)`:

   * Construct a row with:

     * identity & keys as above,
     * `overlay_factor_total = F_overlay[m,z[,ch],h]`,
     * optional per-event-type factor fields,
     * `s4_spec_version`.

2. Validate against `#/model/merchant_zone_overlay_factors_5A`.

3. Append to `OVERLAY_ROWS`.

Ensure `OVERLAY_ROWS` is 1:1 with `SCEN_LOCAL_ROWS` on the PK.

#### 6.9.3 Build `merchant_zone_scenario_utc_5A` rows (optional)

If UTC projection is implemented:

1. For each `(m,z[,ch],h_utc) ∈ DOMAIN_S4_utc`:

   * Construct a row with identity & keys,
   * `lambda_utc_scenario = LAMBDA_UTC_SCEN[m,z[,ch],h_utc]`,
   * `s4_spec_version`,
   * optional mapping hints.

2. Validate against `#/model/merchant_zone_scenario_utc_5A`.

3. Append to `SCEN_UTC_ROWS`.

---

### 6.10 Step 9 — Atomic write & idempotency

**Goal:** Persist S4 outputs atomically and idempotently per `(manifest_fingerprint, scenario_id)`.

**Inputs:**

* `SCEN_LOCAL_ROWS` (required).
* Optional `OVERLAY_ROWS`, `SCEN_UTC_ROWS`.
* Dataset dictionary entries for S4 outputs.

**Procedure:**

1. **Resolve canonical paths**

   * Using the dataset dictionary, compute canonical paths under:

     ```text
     fingerprint={manifest_fingerprint}/scenario_id={scenario_id}
     ```

     for:

     * `merchant_zone_scenario_local_5A`
     * `merchant_zone_overlay_factors_5A` (if used)
     * `merchant_zone_scenario_utc_5A` (if used)

2. **Check for existing outputs**

   * If any S4 outputs already exist for this `(manifest_fingerprint, scenario_id)`:

     * Load them,
     * Canonically order both existing and candidate rows (e.g. by PK),
     * Compare content:

       * If identical, S4 MAY log an idempotent re-run and exit without writing.
       * If any difference exists, S4 MUST fail with `S4_OUTPUT_CONFLICT` and MUST NOT overwrite.

3. **Write to staging paths**

   * Write `SCEN_LOCAL_ROWS` to a `.staging/` location for the local-intensity dataset.
   * If present, write `OVERLAY_ROWS` and `SCEN_UTC_ROWS` to their own `.staging/` paths.

4. **Validate staged outputs (optional but recommended)**

   * Re-read staged files and:

     * validate schemas,
     * validate PK uniqueness,
     * optionally recompute aggregate stats (e.g. min/max λ, overlay factor ranges).

5. **Atomic commit**

   * Atomically move staged files into canonical locations in an order that ensures consistency:

     1. `merchant_zone_scenario_local_5A`
     2. `merchant_zone_overlay_factors_5A` (if present)
     3. `merchant_zone_scenario_utc_5A` (if present)

   * At no point should a consumer see overlays or UTC surfaces without a matching local scenario-intensity surface.

**Invariants:**

* On success, S4 outputs satisfy all identity, domain, and numeric invariants in §§4, 7, 8.
* On failure, no partially written canonical S4 outputs MAY remain; only clearly staged artefacts (e.g. under `.staging/`) may exist and MUST be ignored by consumers.

---

Within this algorithm, 5A.S4 behaves as a **pure, deterministic overlay engine**: it reads sealed baselines, shapes, and scenario configs; constructs event surfaces; evaluates overlay factors; and multiplies baselines to produce scenario-aware intensities — all governed by policies and the sealed world, with no randomness and clean, atomic outputs.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how **identity** is represented for **5A.S4 — Calendar & Scenario Overlays**, how its datasets are **partitioned and keyed**, and what the **rewrite rules** are. All rules here are **binding**.

S4 outputs are **world + parameter-pack + scenario scoped**:

* World: `manifest_fingerprint` (ties back to S0/S1/S3).
* Parameter pack: `parameter_hash`.
* Scenario: `scenario_id`.

They are **not** seed- or run-scoped.

---

### 7.1 Identity model

There are two levels of identity:

1. **Run identity** (execution context, ephemeral)

   * `parameter_hash` — identity of the active parameter pack (5A policies + scenario configs).
   * `manifest_fingerprint` — identity of the closed-world manifest.
   * `scenario_id` — the scenario S4 is computing overlays for.
   * `run_id` — identity of this particular S4 execution.

   These belong to the *run* and are reflected in logs/layer2/5A/run-report/traces.

2. **Dataset identity** (storage-level, persistent)

   * Each S4 output dataset is identified by the triple:

     ```text
     (manifest_fingerprint, parameter_hash, scenario_id)
     ```

   * For a fixed triple, there MUST be at most **one** canonical set of S4 outputs.

Binding rules:

* `run_id` MUST NOT appear as a column or partition key in any S4 dataset.
* Each S4 dataset MUST embed:

  * `manifest_fingerprint`,
  * `parameter_hash`,
  * `scenario_id`

  as columns, and those values MUST be consistent with:

  * the partition tokens (`fingerprint={manifest_fingerprint}`, `scenario_id={scenario_id}`), and
  * the parameter pack identity from S0.

For any fixed `(manifest_fingerprint, parameter_hash, scenario_id)`, re-running S4 MUST either:

* produce byte-identical outputs (idempotent), or
* fail with an output conflict (see §7.4) and NOT overwrite.

---

### 7.2 Partition law & path contracts

#### 7.2.1 Partition keys

All S4 outputs are partitioned by **world + scenario**:

* `merchant_zone_scenario_local_5A`:

  * `partition_keys: ["fingerprint","scenario_id"]`

* `merchant_zone_overlay_factors_5A` (if implemented):

  * `partition_keys: ["fingerprint","scenario_id"]`

* `merchant_zone_scenario_utc_5A` (if implemented):

  * `partition_keys: ["fingerprint","scenario_id"]`
  * (Optionally, an additional UTC horizon partition like `utc_date` MAY be introduced and then becomes binding and must be declared in the dictionary; if you do this, it must be treated as part of the partition law.)

No S4 dataset may be partitioned by `parameter_hash`, `seed`, or `run_id`.

#### 7.2.2 Path templates

Canonical paths MUST follow the templates declared in the dataset dictionary. For example:

* `merchant_zone_scenario_local_5A`:

  ```text
  data/layer2/5A/merchant_zone_scenario_local/
    fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_scenario_local_5A.parquet
  ```

* `merchant_zone_overlay_factors_5A`:

  ```text
  data/layer2/5A/merchant_zone_overlay_factors/
    fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_overlay_factors_5A.parquet
  ```

* `merchant_zone_scenario_utc_5A`:

  ```text
  data/layer2/5A/merchant_zone_scenario_utc/
    fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_scenario_utc_5A.parquet
  ```

These templates are **binding** once declared in `dataset_dictionary.layer2.5A.yaml` and `artefact_registry_5A.yaml`.

#### 7.2.3 Path ↔ embed equality

For every row in every S4 dataset:

* Embedded `manifest_fingerprint` MUST:

  * be non-null, and
  * exactly equal the `fingerprint` partition token.

* Embedded `scenario_id` MUST:

  * be non-null, and
  * exactly equal the `scenario_id` partition token.

* Embedded `parameter_hash` MUST:

  * be non-null, and
  * equal the `parameter_hash` recorded in `s0_gate_receipt_5A` for this fingerprint.

Any mismatch between:

* partition tokens and embedded `manifest_fingerprint` / `scenario_id`, or
* embedded `parameter_hash` and S0’s `parameter_hash`

MUST be treated as a hard validation failure for S4 outputs.

---

### 7.3 Primary keys & logical ordering

#### 7.3.1 Primary keys

Primary keys for S4 datasets are **binding**.

* **`merchant_zone_scenario_local_5A`**

  With explicit `(legal_country_iso, tzid)` zone representation and a scalar local horizon index:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - merchant_id
    - legal_country_iso
    - tzid
    - local_horizon_bucket_index
  ```

  If you use `zone_id`, replace `legal_country_iso` + `tzid` with `zone_id`. If `channel` / `channel_group` is a dimension, it MUST be included in the PK.

* **`merchant_zone_overlay_factors_5A`** (if implemented)

  PK MUST mirror the scenario-local dataset (same domain, same keys):

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - merchant_id
    - legal_country_iso   # or zone_id
    - tzid
    - local_horizon_bucket_index
  ```

* **`merchant_zone_scenario_utc_5A`** (if implemented)

  If UTC horizon is represented by a single index:

  ```yaml
  primary_key:
    - manifest_fingerprint
    - scenario_id
    - merchant_id
    - legal_country_iso   # or zone_id
    - tzid
    - utc_horizon_bucket_index
  ```

  Or, if represented by `(utc_date, utc_bucket_within_date)`, the PK MUST include both these fields instead of a single index.

Constraints (for all PKs):

* All PK fields MUST be required and non-null.
* No duplicate PK tuples are allowed within a `(fingerprint, scenario_id)` partition.

#### 7.3.2 Logical ordering

Physical ordering is not semantically significant, but S4 MUST impose a deterministic writer order to support:

* stable file content,
* idempotency comparison, and
* easier debugging.

Recommended ordering:

* For `merchant_zone_scenario_local_5A`:

  * sort rows by `(merchant_id, zone_representation[,channel], local_horizon_bucket_index)`.

* For `merchant_zone_overlay_factors_5A` (if present):

  * same ordering as `merchant_zone_scenario_local_5A`.

* For `merchant_zone_scenario_utc_5A`:

  * sort rows by `(merchant_id, zone_representation[,channel], utc_horizon_bucket_index)` (or by `(merchant_id, zone_representation, utc_date, utc_bucket_within_date)` if using date+slot).

Consumers MUST NOT rely on ordering beyond what PK semantics guarantee; ordering is purely for reproducibility and diffability.

---

### 7.4 Merge discipline & rewrite semantics

S4 follows a **single-writer, no-merge** model per `(manifest_fingerprint, scenario_id)`.

Binding rules:

1. **No in-place merge or append**

   For a fixed `(manifest_fingerprint, scenario_id)`, S4 MUST NOT:

   * append new rows to existing S4 outputs,
   * partially overwrite subsets of rows, or
   * perform row-level “merge” operations.

   S4 outputs are conceptually **atomic snapshots** for a world+scenario.

2. **Idempotent re-runs allowed**

   When S4 is re-run for a `(manifest_fingerprint, parameter_hash, scenario_id)`:

   * It MUST recompute candidate outputs in-memory or via staging,
   * Canonically sort both existing and candidate rows (by PK),
   * Compare the serialised content:

     * If and only if they are identical, S4 MAY:

       * log that outputs are already up-to-date, and
       * skip replacing the existing files (idempotent no-op).

3. **Conflicting rewrites forbidden**

   * If existing outputs differ in any way from recomputed outputs for the same `(manifest_fingerprint, parameter_hash, scenario_id)` — different rows, different λ values, different overlay factors, different domain coverage — S4 MUST:

     * fail with a canonical output-conflict error (e.g. `S4_OUTPUT_CONFLICT`), and
     * MUST NOT overwrite or merge existing files.

   * Any legitimate change in S3 baselines, scenario calendar, overlay rules, or horizon definition that changes S4 outputs MUST be represented by:

     * a new `parameter_hash` (new parameter pack) and/or
     * a new `manifest_fingerprint` (new world manifest),

     not by mutating outputs under the same identity.

4. **No cross-world or cross-scenario merging**

   * S4 MUST NOT aggregate or merge outputs across distinct:

     * `manifest_fingerprint` values, or
     * `scenario_id` values.

   * Each `(manifest_fingerprint, scenario_id)` partition is self-contained and represents a specific world+scenario.

---

### 7.5 Interaction with other identity dimensions

#### 7.5.1 `parameter_hash`

* `parameter_hash` MUST be embedded as a column in all S4 outputs.
* It MUST be constant across all rows in a given `(manifest_fingerprint, scenario_id)` partition.
* It MUST equal the value recorded in `s0_gate_receipt_5A` for this `manifest_fingerprint`.

S4 outputs are **not** partitioned by `parameter_hash`, but the embedded `parameter_hash` is essential for tying scenario intensities to the correct parameter pack.

#### 7.5.2 `seed` and `run_id`

* `seed`:

  * MUST NOT be used as a partition key or embedded column; S4 does not use RNG and SHOULD be invariant to any seed notion.

* `run_id`:

  * MUST NOT appear in S4 datasets; it remains a logging/run-report concern only.

Any use of `seed` or `run_id` in S4 schemas or path templates is a violation of this spec.

---

### 7.6 Cross-segment identity alignment

S4 outputs MUST align with S3 baselines and S2 grid, and be consistent with S1/S0 identities:

1. **Alignment with S3 (`merchant_zone_baseline_local_5A`)**

   * For a given `(manifest_fingerprint, scenario_id)`:

     * Every `(merchant_id, zone_representation[,channel])` present in `merchant_zone_scenario_local_5A` MUST exist in `merchant_zone_baseline_local_5A`.
     * For every `(merchant_id, zone_representation[,channel])` in S3 domain after S4’s policy filters, `merchant_zone_scenario_local_5A` MUST provide horizon coverage for all local horizon buckets in the scenario window.

2. **Alignment with S2 (`shape_grid_definition_5A`) and horizon config**

   * Horizon mapping (`WEEK_MAP[h] = k`) MUST be consistent with:

     * S2 local-week grid (`shape_grid_definition_5A`), and
     * horizon config (time-of-week mapping).

   * No `local_horizon_bucket` in S4 outputs may map to an invalid `bucket_index` or outside the `[0..T_week-1]` range.

3. **Alignment with S0/S1**

   * Embedded `manifest_fingerprint`, `parameter_hash`, `scenario_id` MUST match:

     * S0 gate receipt values, and
     * S1’s world + pack identity.

   * All `merchant_id` and zone identifiers used in S4 outputs MUST exist in the S1/S3 domain for that world+pack.

If any of these alignments fail (e.g. S4 outputs contain a merchant×zone not present in S3; horizon buckets that cannot be mapped to S2 grid; identity mismatches), S4 MUST treat outputs as invalid for that `(manifest_fingerprint, parameter_hash, scenario_id)` and MUST NOT publish them to canonical paths.

---

Within these constraints, S4’s identity, partitioning, ordering, and merge discipline are fully specified: for each world+pack+scenario triple, there is a single, immutable scenario-intensity surface (and optional overlays/UTC views), aligned with all upstream identities and safe to consume by S5 and 5B.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 5A.S4 — Calendar & Scenario Overlays** is considered green for a given `(parameter_hash, manifest_fingerprint, scenario_id)` and the **hard preconditions** it imposes on downstream consumers (chiefly 5A.S5 and 5B). All rules here are **binding**.

---

### 8.1 Conditions for 5A.S4 to “PASS”

For a given triple `(parameter_hash, manifest_fingerprint, scenario_id)`, S4 is considered **successful** only if **all** the following hold.

#### 8.1.1 S0 gate, sealed inputs & upstream status

1. **Valid S0 gate & sealed inputs**

   * `s0_gate_receipt_5A` and `sealed_inputs_5A` for `fingerprint={manifest_fingerprint}`:

     * exist and are discoverable via the catalogue,
     * validate against their schemas
       (`#/validation/s0_gate_receipt_5A`, `#/validation/sealed_inputs_5A`),
     * have `parameter_hash == parameter_hash`, and
     * recomputed `sealed_inputs_digest` matches the value recorded in the receipt.

2. **Layer-1 segments are green**

   * In `s0_gate_receipt_5A.verified_upstream_segments`, each of
     `1A`, `1B`, `2A`, `2B`, `3A`, `3B` MUST have `status="PASS"`.

If either of these fail, S4 MUST NOT be considered green regardless of its own outputs.

---

#### 8.1.2 S1–S3 surfaces & scenario configs are present and valid

3. **S1: `merchant_zone_profile_5A`**

   * Exists for this `(manifest_fingerprint, parameter_hash)`.
   * Validates against `#/model/merchant_zone_profile_5A`.
   * Embeds `manifest_fingerprint == manifest_fingerprint`, `parameter_hash == parameter_hash`.
   * Respects its PK; no duplicate `(merchant_id, zone_representation[,channel])`.

4. **S2: time grid & shapes**

   * `shape_grid_definition_5A`:

     * exists for `(parameter_hash, scenario_id)`,
     * validates against `#/model/shape_grid_definition_5A`,
     * defines a contiguous `bucket_index` range `[0..T_week−1]`,
     * has consistent `bucket_duration_minutes`, `local_day_of_week`, and `local_minutes_since_midnight`.

   * `class_zone_shape_5A`:

     * exists for `(parameter_hash, scenario_id)`,
     * validates against `#/model/class_zone_shape_5A`,
     * embeds `parameter_hash == parameter_hash`, `scenario_id == scenario_id`,
     * respects its PK, and has `shape_value ≥ 0` and Σ=1 per `(demand_class, zone[,channel])` (as guaranteed by S2; S4 may optionally re-check).

5. **S3: baselines**

   * `merchant_zone_baseline_local_5A`:

     * exists for `(manifest_fingerprint, parameter_hash, scenario_id)`,
     * validates against `#/model/merchant_zone_baseline_local_5A`,
     * embeds `manifest_fingerprint == manifest_fingerprint`, `parameter_hash == parameter_hash`, `scenario_id == scenario_id`,
     * respects its PK; no duplicate `(merchant_id, zone_representation[,channel], bucket_index)`,
     * has `lambda_local_base ≥ 0` and finite.

6. **Scenario & horizon configuration**

   * Scenario configs for `scenario_id` (metadata + horizon definition) exist in `sealed_inputs_5A` and validate against their schemas.
   * Horizon config defines:

     * a finite start/end,
     * bucket duration, and
     * a consistent mapping from horizon buckets to `(local_day_of_week, local_minutes_since_midnight)` used by S2.

7. **Overlay policies & calendar**

   * Overlay policy artefacts (e.g. `scenario_overlay_policy_5A`) exist, validate against their schemas, and are marked `status="REQUIRED"` if used by S4.
   * Scenario calendar artefacts (events with time ranges and scopes) exist and validate against their schemas; all event types referenced in the calendar are recognised by the overlay policy.

If any required S1–S3 dataset, scenario config, or overlay policy/calendar artefact is missing or invalid, S4 MUST fail.

---

#### 8.1.3 Domain & horizon coverage for `merchant_zone_scenario_local_5A`

Let:

* `D_S3` = domain of S3 baselines after S3/S4 policy filters:
  set of `(merchant_id, zone_representation[,channel])` in `merchant_zone_baseline_local_5A`.

* `H_local` = set of local horizon buckets defined by the horizon config.

8. **Dataset exists & schema-valid**

   * `merchant_zone_scenario_local_5A`:

     * exists under `fingerprint={manifest_fingerprint}/scenario_id={scenario_id}`,
     * validates against `#/model/merchant_zone_scenario_local_5A`,
     * declares `partition_keys: ["fingerprint","scenario_id"]`,
     * declares a PK consistent with §5/§7.

9. **Identity consistency**

   * For all rows in `merchant_zone_scenario_local_5A`:

     * `manifest_fingerprint == {manifest_fingerprint}`,
     * `parameter_hash == {parameter_hash}`,
     * `scenario_id == {scenario_id}`.

10. **Domain alignment with S3**

* Let `D_S4` be the set of `(merchant_id, zone_representation[,channel])` present in `merchant_zone_scenario_local_5A`.

S4 MUST ensure:

* `D_S4 == D_S3` (after any explicit S4 policy filters).
* No merchant×zone appears in S4 that is not present in S3’s baselines.
* No in-scope merchant×zone from S3 is missing from S4.

11. **Horizon coverage per merchant×zone**

* For each `(m,z[,ch]) ∈ D_S3`, the set of local horizon buckets present in `merchant_zone_scenario_local_5A` MUST equal `H_local`.
* No duplicates `(m,z[,ch],h)` are allowed.

12. **Mapping to local-week grid**

* For each horizon bucket `h ∈ H_local`, S4’s internal mapping `k = WEEK_MAP[h]` MUST refer to a valid `bucket_index ∈ [0..T_week−1]` in `shape_grid_definition_5A`.
* No `h` in S4 outputs may implicitly refer to an undefined local-week bucket.

---

#### 8.1.4 Numeric correctness for λ_scenario and overlay factors

13. **Non-negativity and finiteness**

* For every row in `merchant_zone_scenario_local_5A`:

  * `lambda_local_scenario` is finite (no NaN, no ±Inf),
  * `lambda_local_scenario ≥ 0`.

14. **Overlay factor consistency (if overlay table exists)**

* If `merchant_zone_overlay_factors_5A` is present, for each `(m,z[,ch],h)`:

  ```text
  lambda_local_scenario(m,z[,ch],h)
    ≈ lambda_base_local(m,z[,ch],kappa(h)) × overlay_factor_total(m,z[,ch],h)
  ```

  within a small numeric tolerance.

* All `overlay_factor_total` values MUST be finite and ≥ 0.

* Where policy defines max/min multipliers (e.g. `F_min`, `F_max`), overlay factors MUST lie within those bounds, unless explicit exceptions (e.g. `F=0` for outages) are documented.

15. **No silent shape distortion**

* For a given `(m,z[,ch])`, the pattern of `lambda_local_scenario(m,z[,ch],h)` across horizon buckets that map to the same `(local_day_of_week, time_of_day)` should only differ from the baseline pattern by the overlay factors:

  * That is, S4 MUST NOT implicitly redefine the weekly shape; any distortions must be a documented result of `F_overlay`.

If these numeric or pattern invariants are violated, S4 MUST treat the outputs as invalid (`S4_INTENSITY_NUMERIC_INVALID` / `S4_OVERLAY_EVAL_FAILED`).

---

#### 8.1.5 Optional outputs are consistent (if present)

16. **`merchant_zone_overlay_factors_5A`**

* If present:

  * exists for the same `(manifest_fingerprint, parameter_hash, scenario_id)`,
  * validates against `#/model/merchant_zone_overlay_factors_5A`,
  * has PK and partitioning as specified,
  * has a 1:1 domain with `merchant_zone_scenario_local_5A` on all key fields (no missing or extra `(m,z[,ch],h)`).

17. **`merchant_zone_scenario_utc_5A`**

* If present:

  * exists and validates against `#/model/merchant_zone_scenario_utc_5A`,
  * respects its PK and partitioning for `(manifest_fingerprint, scenario_id)`.

* The UTC intensities MUST be a deterministic mapping from local scenario intensities via civil-time rules and UTC grid; optional invariants (e.g. conservation of total intensity) SHOULD be enforced if defined in policy.

---

#### 8.1.6 Atomicity & idempotence

18. **All-or-nothing outputs**

* For a given `(manifest_fingerprint, scenario_id)`:

  * either all required S4 datasets (`merchant_zone_scenario_local_5A`, and any optional ones you declare) satisfy these invariants, or
  * none of them are considered valid.
* Partially written or inconsistent outputs in canonical paths MUST NOT be left behind on a successful run.

19. **Consistency across re-runs**

* If S4 outputs already existed for this `(manifest_fingerprint, parameter_hash, scenario_id)` prior to this run, recomputation MUST produce identical content (under canonical ordering).
* If not, S4 MUST fail with `S4_OUTPUT_CONFLICT` and MUST NOT overwrite existing outputs.

---

### 8.2 Minimal content requirements

Even if structural and numeric checks pass, S4 MUST enforce the following **content minima**:

1. **Non-empty horizon (unless explicitly allowed)**

   * The local horizon grid `H_local` MUST contain at least one bucket (non-zero horizon).
   * A zero-length horizon is only acceptable if explicitly permitted by horizon policy and clearly logged.

2. **Non-empty domain (unless truly no merchants/zones)**

   * If S3’s in-scope domain `D_S3` for this `(manifest_fingerprint, parameter_hash, scenario_id)` is non-empty, S4 MUST produce at least one scenario-intensity row.
   * An entirely empty `merchant_zone_scenario_local_5A` is acceptable only if:

     * S3’s domain is genuinely empty (per policy), and
     * this case is explicitly allowed and clearly logged.

3. **Calendar/policy coverage**

   * Overlay policy and scenario calendar MUST be capable of producing valid overlay factors for all `(m,z[,ch],h)` in domain×horizon; there MUST be no “unreachable” combinations where no rule applies and no default is defined.

---

### 8.3 Gating obligations on downstream consumers (5A.S5, 5B, 6A)

Downstream components that depend on scenario-aware intensities MUST obey the following gates:

1. **Require S4 to be present & valid**

   * Before using scenario-adjusted intensities, a downstream component MUST:

     * verify that `merchant_zone_scenario_local_5A` exists for the relevant `(manifest_fingerprint, parameter_hash, scenario_id)`,
     * validate that it matches the schema, PK, partitioning and identity invariants above,
     * ensure that S4’s acceptance criteria (domain coverage, numeric invariants) have been met (either directly or via S5’s validation bundle once that exists).

2. **Treat S4 as scenario λ authority**

   * Downstream logic MUST treat `lambda_local_scenario` (and `lambda_utc_scenario`, if present) as the **authoritative scenario-intensity surface**.
   * It MUST NOT:

     * re-apply calendar overlays independently to S3 baselines in a way that contradicts S4,
     * define alternative overlay pipelines that bypass S4 outputs.

3. **Respect S4 domain & horizon**

   * If downstream expects to model or simulate arrivals for a `(merchant, zone[,channel])` over a time bucket, but there is no corresponding scenario intensity in S4 for that world+scenario, it MUST treat this as an upstream configuration error — not silently assume zero intensity or a flat pattern.

---

### 8.4 When 5A.S4 MUST fail

Regardless of catalogue state, S4 MUST treat itself as **FAILED** for a `(parameter_hash, manifest_fingerprint, scenario_id)` and MUST NOT publish/modify canonical S4 outputs if any of the following occur:

* **Gate failures**

  * `s0_gate_receipt_5A` / `sealed_inputs_5A` invalid or mismatched.
  * Any of 1A–3B marked `"FAIL"` or `"MISSING"`.
  * Required S1–S3 outputs missing or schema-invalid.

* **Required scenario/config/policy missing**

  * Scenario metadata, calendar, horizon config, or overlay policies required for S4 cannot be resolved or validated from `sealed_inputs_5A`.

* **Horizon/grid misconfiguration**

  * Horizon grid cannot be constructed, or cannot be consistently mapped to S2’s local-week grid, i.e. `WEEK_MAP[h]` undefined for some horizon buckets (`S4_HORIZON_GRID_INVALID`).

* **Calendar alignment failures**

  * Scenario calendar events cannot be mapped cleanly into horizon buckets (e.g. time ranges malformed, scopes invalid) and thus event surfaces cannot be built (`S4_CALENDAR_ALIGNMENT_FAILED`).

* **Overlay evaluation failures**

  * Overlay policy cannot produce valid factors for some `(m,z[,ch],h)` (no rule matched/no default) (`S4_OVERLAY_EVAL_FAILED`).

* **Numeric issues**

  * Any `lambda_local_scenario` or `overlay_factor_total` is negative, NaN, or ±Inf, or violates configured numeric bounds (`S4_INTENSITY_NUMERIC_INVALID`).

* **Domain or PK misalignment**

  * Domain of `merchant_zone_scenario_local_5A` does not match S3’s domain; missing or extra rows; PK violations (`S4_DOMAIN_ALIGNMENT_FAILED`).

* **Output conflict**

  * Existing S4 outputs for this `(manifest_fingerprint, parameter_hash, scenario_id)` differ from recomputed outputs (`S4_OUTPUT_CONFLICT`).

* **I/O or internal invariant failures**

  * `S4_IO_READ_FAILED`, `S4_IO_WRITE_FAILED`, or `S4_INTERNAL_INVARIANT_VIOLATION`.

In all such cases, S4 MUST:

* abort without writing or modifying canonical outputs,
* emit an appropriate canonical error code in run-report/logs, and
* rely on fixes to upstream configs/policies or infra before a future S4 run can succeed.

Within these rules, S4’s notion of “green” is unambiguous: the world is sealed, S1–S3 & scenario configs are valid, the horizon and overlays are well-defined, and S4 outputs are complete, numerically sane, and aligned with all upstream identities and domains.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error codes** that **5A.S4 — Calendar & Scenario Overlays** MAY emit, and the conditions under which they MUST be raised. These codes are **binding**: implementations MUST either use them directly or maintain a strict 1:1 mapping.

S4 errors are about **S4 itself** failing to produce a valid scenario-intensity surface for a given
`(parameter_hash, manifest_fingerprint, scenario_id)`. They are distinct from:

* upstream status flags in `s0_gate_receipt_5A`,
* S1/S2/S3 error codes.

---

### 9.1 Error reporting contract

5A.S4 MUST surface failures via:

* the engine’s **run-report** (per-run record), and
* structured logs / metrics.

Each failure record MUST include at least:

* `segment_id = "5A.S4"`
* `parameter_hash`
* `manifest_fingerprint`
* `scenario_id`
* `run_id`
* `error_code` — one of the codes below
* `severity` — `FATAL` for all S4 errors
* `message` — short human-readable summary
* `details` — optional structured context (e.g. `{"merchant_id": "...", "legal_country_iso": "...", "tzid": "...", "local_horizon_bucket_index": ...}`)

S4 does **not** write a dedicated “error dataset”; errors are captured in run-report/logging.

---

### 9.2 Canonical error codes (summary)

| Code                              | Severity | Category                                 |
| --------------------------------- | -------- | ---------------------------------------- |
| `S4_GATE_OR_S3_INVALID`           | FATAL    | S0/S1–S3 gate & alignment                |
| `S4_UPSTREAM_NOT_PASS`            | FATAL    | Upstream Layer-1 status (1A–3B)          |
| `S4_REQUIRED_INPUT_MISSING`       | FATAL    | Required S1–S3/scenario artefact missing |
| `S4_REQUIRED_POLICY_MISSING`      | FATAL    | Required overlay/horizon policy missing  |
| `S4_HORIZON_GRID_INVALID`         | FATAL    | Invalid / inconsistent horizon grid      |
| `S4_CALENDAR_ALIGNMENT_FAILED`    | FATAL    | Scenario calendar cannot be mapped       |
| `S4_OVERLAY_EVAL_FAILED`          | FATAL    | Cannot evaluate overlay factor           |
| `S4_INTENSITY_NUMERIC_INVALID`    | FATAL    | Invalid λ or factors (NaN/Inf/negative)  |
| `S4_OUTPUT_CONFLICT`              | FATAL    | Existing outputs differ from recomputed  |
| `S4_IO_READ_FAILED`               | FATAL    | I/O read error                           |
| `S4_IO_WRITE_FAILED`              | FATAL    | I/O write/commit error                   |
| `S4_INTERNAL_INVARIANT_VIOLATION` | FATAL    | Internal “should never happen” state     |

All of these are **stop-the-world** for S4: if any occurs, S4 MUST NOT publish or modify canonical outputs for that world+scenario.

---

### 9.3 Code-by-code definitions

#### 9.3.1 `S4_GATE_OR_S3_INVALID` *(FATAL)*

**Trigger**

Raised when S4 cannot establish a valid S0/S1–S3 context for this run, for example:

* `s0_gate_receipt_5A` or `sealed_inputs_5A`:

  * missing for `fingerprint={manifest_fingerprint}`,
  * schema-invalid,
  * `parameter_hash` mismatch, or
  * recomputed `sealed_inputs_digest` ≠ digest in receipt.

* `merchant_zone_profile_5A`, `shape_grid_definition_5A`, `class_zone_shape_5A`, or `merchant_zone_baseline_local_5A`:

  * missing,
  * schema-invalid,
  * embedded `parameter_hash` / `manifest_fingerprint` / `scenario_id` inconsistent with run context,
  * or with obvious PK violations (duplicates in keys).

Detected in Step 1 of the algorithm.

**Effect**

* S4 MUST abort and MUST NOT attempt to compute overlays.
* No S4 outputs MAY be written or touched.
* Operator must correct S0/S1–S3 / catalogue issues and re-run S4.

---

#### 9.3.2 `S4_UPSTREAM_NOT_PASS` *(FATAL)*

**Trigger**

Raised when S0 indicates that one or more Layer-1 segments are not green:

* In `s0_gate_receipt_5A.verified_upstream_segments`, any of
  `1A`, `1B`, `2A`, `2B`, `3A`, `3B` has `status="FAIL"` or `status="MISSING"`.

**Effect**

* S4 MUST abort and MUST NOT read upstream fact tables or continue creating scenario intensities.
* Operator must resolve upstream segment issues and re-run those segments + S0 before re-running S4.

---

#### 9.3.3 `S4_REQUIRED_INPUT_MISSING` *(FATAL)*

**Trigger**

Raised when a **required data artefact** (S1–S3 or scenario-related) is absent from `sealed_inputs_5A` or cannot be resolved/used, for example:

* `merchant_zone_profile_5A`, `shape_grid_definition_5A`, `class_zone_shape_5A`, or `merchant_zone_baseline_local_5A`:

  * missing as sealed artefacts,
  * or present but with incompatible `read_scope` (`METADATA_ONLY` when S4 needs `ROW_LEVEL`).

* Required scenario/horizon artefacts for `scenario_id`:

  * scenario metadata, scenario calendar, or horizon config missing or not sealed for this parameter pack.

**Effect**

* S4 MUST abort before constructing the horizon or any overlays.
* No S4 outputs MAY be written.
* Operator must correct the parameter pack / catalogue so all required artefacts appear in `sealed_inputs_5A`, then re-run S0–S4.

---

#### 9.3.4 `S4_REQUIRED_POLICY_MISSING` *(FATAL)*

**Trigger**

Raised when a **required overlay or horizon policy** is missing or unusable, for example:

* `scenario_overlay_policy_5A` not present in `sealed_inputs_5A` (or not marked as required).
* `scenario_overlay_policy_5A` present but schema-invalid.
* Required horizon config (e.g. `scenario_horizon_config_5A`) missing or schema-invalid.
* Policies present but marked with an incompatible `read_scope`.

**Effect**

* S4 MUST abort and MUST NOT compute event surfaces or overlay factors.
* No S4 outputs MAY be published.
* Fix is to deploy the appropriate policies/configs in the parameter pack and re-run.

---

#### 9.3.5 `S4_HORIZON_GRID_INVALID` *(FATAL)*

**Trigger**

Raised when S4 is unable to construct a valid local (or UTC) horizon grid or map it consistently back to S2’s local-week grid, for example:

* Horizon start/end or bucket duration from config produce:

  * negative horizon length,
  * zero buckets when at least one is expected,
  * overlapped or gapped buckets.

* For some horizon bucket `h`:

  * there is no corresponding local-week bucket index `k` in `shape_grid_definition_5A` (`WEEK_MAP[h]` undefined),
  * or mapping would require a local-day/time pair not present in S2 grid.

* If UTC projection is enabled:

  * UTC horizon mapping cannot be constructed or is inconsistent with 2A (e.g. DST handling cannot be resolved according to config).

**Effect**

* S4 MUST abort; no scenario intensities MAY be considered valid.
* Operator must fix horizon configuration (and, if necessary, S2 grid config) and re-run.

---

#### 9.3.6 `S4_CALENDAR_ALIGNMENT_FAILED` *(FATAL)*

**Trigger**

Raised when scenario calendar events cannot be coherently mapped onto the horizon buckets and domain, for example:

* Event time ranges are malformed (start after end, invalid timestamps).
* Event scopes refer to unknown regions/zones/merchants/classes.
* Event definitions conflict in ways the overlay policy cannot interpret (e.g. unknown event types, or missing mapping rules).

Detected in Step 4 when building event surfaces `(EVENTS[m,z,h])`.

**Effect**

* S4 MUST abort without generating overlays or scenario intensities.
* `error_details` SHOULD identify problematic event IDs, types, or scopes.
* Fix is to correct scenario calendar definitions and/or overlay policy coverage, then re-run S4.

---

#### 9.3.7 `S4_OVERLAY_EVAL_FAILED` *(FATAL)*

**Trigger**

Raised when S4 cannot compute a valid overlay factor `F_overlay(m,z[,ch],h)` for some domain/horizon point, for example:

* For a `(m,z[,ch],h)` with non-empty `EVENTS[m,z[,ch],h]`, the overlay policy has:

  * no applicable rule and no default, or
  * multiple conflicting rules with no well-defined precedence.

* Overlay factor computed from rules is undefined (e.g. references missing config values) even though the policies exist.

* Per-event or combined factors rely on external data not sealed in `sealed_inputs_5A`.

Detected in Step 5 when evaluating overlay factors.

**Effect**

* S4 MUST abort and MUST NOT write any outputs.
* `error_details` SHOULD identify a representative `(merchant_id, zone, event_type, local_horizon_bucket)` that failed.
* Fix is to update overlay policies and/or scenario configs so all domain×horizon points can be assigned a factor (including explicit defaults) deterministically.

---

#### 9.3.8 `S4_INTENSITY_NUMERIC_INVALID` *(FATAL)*

**Trigger**

Raised when overlay factors or scenario intensities are numerically invalid or violate configured numeric constraints, for example:

* Any `overlay_factor_total` or `lambda_local_scenario` is:

  * `NaN`, `+Inf`, `-Inf`, or
  * negative (except where policy explicitly defines `λ=0` for shutdown/outage; even then, overlay factors should not be negative).

* Overlay factors exceed or fall below configured bounds without corresponding policy justification:

  * e.g. `overlay_factor_total` > `F_max` or < `F_min` where such minima/maxima are defined.

* Optional added checks fail:

  * e.g. per-scenario or per-merchant mean factors must satisfy expected boundaries (for baseline scenarios vs stress scenarios), if such invariants are defined.

Detected typically in Steps 5–6 when computing `F_overlay` and `lambda_local_scenario`.

**Effect**

* S4 MUST abort; canonical outputs MUST NOT be treated as valid.
* `error_details` SHOULD identify at least one failing `(merchant_id, zone, local_horizon_bucket)` and the offending value(s).
* Fix is to adjust overlay policies, calendar, or numeric handling so resulting factors and λ values are finite, non-negative and within agreed bounds.

---

#### 9.3.9 `S4_OUTPUT_CONFLICT` *(FATAL)*

**Trigger**

Raised when S4 detects that canonical outputs already exist for `(manifest_fingerprint, parameter_hash, scenario_id)` and differ from what the current run would produce, for example:

* Existing `merchant_zone_scenario_local_5A` rows differ from recomputed `SCEN_LOCAL_ROWS` under canonical ordering.
* Optional `merchant_zone_overlay_factors_5A` and/or `merchant_zone_scenario_utc_5A` are inconsistent with recomputed values.

Detected in Step 9 when comparing staging outputs with existing files.

**Effect**

* S4 MUST NOT overwrite existing outputs.
* S4 MUST abort and report `S4_OUTPUT_CONFLICT`.
* This indicates that scenario calendar/overlay policies, horizon config, or upstream baselines changed without updating identity (`parameter_hash` / `manifest_fingerprint` / `scenario_id` as appropriate).
* Fix is to mint a new parameter pack and/or manifest (as appropriate) and re-run S0–S4 under the new identity, leaving old outputs immutable.

---

#### 9.3.10 `S4_IO_READ_FAILED` *(FATAL)*

**Trigger**

Raised when S4 encounters I/O or storage failures while reading **required** inputs, for example:

* filesystem/network/permission errors when reading:

  * `s0_gate_receipt_5A` / `sealed_inputs_5A`,
  * S1–S3 outputs,
  * scenario calendar or horizon configs,
  * overlay policies.

This code is for genuine I/O/storage problems, not logical absence (which is `S4_REQUIRED_INPUT_MISSING` / `S4_REQUIRED_POLICY_MISSING`).

**Effect**

* S4 MUST abort; no attempt to compute overlays or write outputs.
* Operator must resolve storage/network/permissions issues and re-run S4.

---

#### 9.3.11 `S4_IO_WRITE_FAILED` *(FATAL)*

**Trigger**

Raised when S4 fails while writing or committing its outputs, for example:

* cannot write staging files for `merchant_zone_scenario_local_5A` or other S4 datasets;
* fails to atomically move staged files into canonical paths.

**Effect**

* S4 MUST treat the run as failed and MUST NOT leave partially written data in canonical locations.
* Staging artefacts MUST remain under clearly non-canonical paths (e.g. `.staging/`) or be cleaned up; consumers MUST ignore these.
* Operator must fix underlying I/O issues and re-run S4.

---

#### 9.3.12 `S4_INTERNAL_INVARIANT_VIOLATION` *(FATAL)*

**Trigger**

Catch-all for “should never happen” internal-error states that cannot be expressed by more specific codes, for example:

* Size of `SCEN_LOCAL_ROWS` is not equal to `|D_S4| × |H_local|` despite domain/horizon being constructed correctly.
* Internal maps or sets report duplicate PKs after explicit de-duplication.
* Logic reaches branches that are supposed to be unreachable according to the spec.

**Effect**

* S4 MUST abort and MUST NOT publish or mutate canonical outputs.
* `error_details` SHOULD capture which invariant failed and relevant context.
* This typically indicates a bug in S4’s implementation or deployment rather than user data or configuration.

---

### 9.4 Relationship to upstream statuses

To avoid confusion:

* **Upstream statuses** (`"PASS"`, `"FAIL"`, `"MISSING"`) for 1A–3B are recorded in `s0_gate_receipt_5A.verified_upstream_segments` and are inputs to S4’s gating.
* `S4_UPSTREAM_NOT_PASS` is raised by S4 **only** when those statuses indicate that Layer-1 is not green for this world.

S4 MUST NOT:

* ignore upstream `"FAIL"`/`"MISSING"` statuses and proceed, or
* attempt to “self-heal” upstream failures.

Downstream consumers (S5, 5B, 6A) MUST:

* consult S4’s run-report/logs to understand why scenario-intensity surfaces are missing or invalid for a given `(parameter_hash, manifest_fingerprint, scenario_id)`, and
* MUST NOT attempt to silently reconstruct S4’s overlays from S3 + calendar when S4 has failed.

Within this framework, every S4 failure mode has a clear, named error code, precise trigger conditions, and a clear operator action, ensuring that scenario intensities are either trustworthy or clearly marked as unusable.

---

## 10. Observability & run-report integration *(Binding)*

This section defines how **5A.S4 — Calendar & Scenario Overlays** MUST report its activity into the engine’s **run-report**, logging, and metrics systems. These requirements are **binding**.

S4 operates at **merchant×zone×horizon-bucket** granularity. Observability MUST make it clear:

* whether overlays were computed,
* for which world + parameter pack + scenario, and
* whether overlay factors and scenario intensities look numerically sane,

without exposing per-row time series in logs.

---

### 10.1 Objectives

Observability for S4 MUST allow operators and downstream components to answer:

1. **Did S4 run for this `(parameter_hash, manifest_fingerprint, scenario_id)`?**

   * Did it start?
   * Did it complete successfully or fail?

2. **If S4 failed, why?**

   * Which canonical error code (§9)?
   * Was it S0/S1–S3 gating, missing scenario/calendar/policy, horizon/grid issues, or numeric problems with overlays/intensities?

3. **If S4 succeeded, what did it produce?**

   * Size of the domain: #merchants, #merchant×zones, #horizon buckets.
   * Basic stats on:

     * overlay factors (`F_overlay`), and
     * λ_scenario (`lambda_local_scenario` and, if present, `lambda_utc_scenario`).

All without logging individual `(merchant, bucket)` rows.

---

### 10.2 Run-report entries

For **every S4 invocation**, the engine’s run-report MUST contain a structured entry with at least:

* `segment_id = "5A.S4"`
* `parameter_hash`
* `manifest_fingerprint`
* `scenario_id`
* `run_id`
* `state_status ∈ {"STARTED","SUCCESS","FAILED"}`
* `start_utc`, `end_utc` (UTC timestamps)
* `duration_ms`

On **SUCCESS**, the run-report entry MUST additionally include:

* **Domain & horizon summary**

  * `s4_domain_merchants` — number of distinct `merchant_id` in `merchant_zone_scenario_local_5A`.
  * `s4_domain_merchant_zones` — number of distinct `(merchant_id, zone_representation[,channel])`.
  * `s4_horizon_buckets_local` — number of local horizon buckets `|H_local|`.
  * `s4_rows_scenario_local` — total rows in `merchant_zone_scenario_local_5A`; SHOULD equal `s4_domain_merchant_zones × s4_horizon_buckets_local`.

* **Overlay factor statistics** (if overlay factors are computed, either embedded or in a separate table)

  * `overlay_factor_min`, `overlay_factor_median`, `overlay_factor_p95`, `overlay_factor_max` over all `(m,z[,ch],h)`.
  * `overlay_factor_violations_count` — number of `(m,z[,ch],h)` with factors outside policy bounds, if such thresholds exist (e.g. > `F_max_warn`).

* **Scenario intensity statistics**

  Over all `lambda_local_scenario`:

  * `lambda_local_scenario_min`
  * `lambda_local_scenario_median`
  * `lambda_local_scenario_p95`
  * `lambda_local_scenario_max`

  Optional: if UTC projection is implemented, analogous stats for `lambda_utc_scenario`.

* **Policy & spec metadata**

  * `s1_spec_version`, `s2_spec_version`, `s3_spec_version` (if available from those datasets).
  * `s4_spec_version`.
  * IDs/versions of key policies used:

    * `scenario_overlay_policy_id` / version,
    * `scenario_horizon_config_id` / version,
    * `scenario_calendar_id` / version.

On **FAILED**, the run-report entry MUST include:

* `error_code` — one of S4’s canonical error codes (§9).
* `error_message` — concise text summary.
* `error_details` — optional structured details (e.g. failing `merchant_id`, `zone`, horizon bucket, event id), kept as small and non-sensitive as possible.

The run-report is the **primary authority** on S4’s outcome.

---

### 10.3 Structured logging

S4 MUST emit **structured logs** (e.g. JSON lines) for key lifecycle events, tagged with:

* `segment_id = "5A.S4"`
* `parameter_hash`
* `manifest_fingerprint`
* `scenario_id`
* `run_id`

At minimum, S4 MUST log:

1. **State start**

   * Level: `INFO`
   * Fields:

     * `event = "state_start"`
     * `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
     * optional: environment tags (e.g. `env`, `ci_build_id`).

2. **Inputs resolved**

   * After Step 1 (gating/inputs) passes.
   * Level: `INFO`
   * Fields:

     * `event = "inputs_resolved"`
     * `s1_present`, `s2_present`, `s3_present` (booleans)
     * `s1_spec_version`, `s2_spec_version`, `s3_spec_version` (if available)
     * `scenario_calendar_id`, `scenario_overlay_policy_id`, `scenario_horizon_config_id`.

3. **Domain & horizon summary**

   * After constructing `D_S4` and horizon grid.
   * Level: `INFO`
   * Fields:

     * `event = "domain_built"`
     * `s4_domain_merchants`
     * `s4_domain_merchant_zones`
     * `s4_horizon_buckets_local`
     * optional: counts by channel or region if you aggregate them (as aggregates only).

4. **Overlay summary**

   * After evaluating overlay factors and scenario intensities (before writing outputs).
   * Level: `INFO`
   * Fields:

     * `event = "overlay_summary"`
     * `overlay_factor_min`, `overlay_factor_median`, `overlay_factor_p95`, `overlay_factor_max`
     * `lambda_local_scenario_min`, `lambda_local_scenario_median`, `lambda_local_scenario_p95`, `lambda_local_scenario_max`
     * `overlay_factor_violations_count` (if tracked).

5. **State success**

   * Level: `INFO`
   * Fields:

     * `event = "state_success"`
     * `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
     * `s4_domain_merchant_zones`
     * `s4_rows_scenario_local`
     * `duration_ms`

6. **State failure**

   * Level: `ERROR`
   * Fields:

     * `event = "state_failure"`
     * `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
     * `error_code`
     * `error_message`
     * `error_details` (e.g. `{ "merchant_id": "...", "legal_country_iso": "...", "tzid": "...", "local_horizon_bucket_index": ... }` where needed).

**Prohibited logging:**

* S4 MUST NOT log:

  * complete time series for individual merchants/zones,
  * raw rows from `merchant_zone_scenario_local_5A`, `merchant_zone_overlay_factors_5A`, or S3 baselines,
  * entire calendar or policy payloads (beyond IDs/versions and small snippets for debugging).

Only aggregate stats and minimal error context are allowed.

---

### 10.4 Metrics

S4 MUST emit a small, stable set of metrics for monitoring. Names are implementation-specific; semantics are binding.

Recommended metrics (per `(parameter_hash, manifest_fingerprint, scenario_id)` run):

1. **Run counters**

   * `fraudengine_5A_s4_runs_total{status="success"|"failure"}`
   * `fraudengine_5A_s4_errors_total{error_code="S4_REQUIRED_INPUT_MISSING"|...}`

2. **Latency**

   * `fraudengine_5A_s4_duration_ms` — histogram/summarised latency for S4 runs.

3. **Domain & horizon size**

   * `fraudengine_5A_s4_domain_merchants` — gauge of S4 domain merchant count.
   * `fraudengine_5A_s4_domain_merchant_zones` — gauge of `(merchant, zone[,channel])` domain size.
   * `fraudengine_5A_s4_horizon_buckets_local` — gauge of `|H_local|`.

4. **Overlay factor stats**

   * `fraudengine_5A_s4_overlay_factor_min`
   * `fraudengine_5A_s4_overlay_factor_max`
   * optionally a histogram of overlay factors to monitor uplift distributions.
   * `fraudengine_5A_s4_overlay_factor_violations_total` — number of buckets that breach configured bounds.

5. **Scenario intensity stats**

   * `fraudengine_5A_s4_lambda_local_min` / `lambda_local_max` — min/max λ_scenario per run.
   * optionally summary/histogram of λ_scenario to detect unrealistic spikes or zeros.

Constraints:

* Metrics MUST NOT use high-cardinality labels like `merchant_id`, `zone_id`, individual `event_type`, etc., unless explicitly permitted; aggregator labels SHOULD be limited to `parameter_hash`, `scenario_id`, environment, and broad scenario tags.

---

### 10.5 Correlation & traceability

To support traceability across segments:

* Every S4 log entry and run-report row MUST include:

  * `segment_id = "5A.S4"`
  * `parameter_hash`
  * `manifest_fingerprint`
  * `scenario_id`
  * `run_id`

If the engine supports distributed tracing:

* S4 SHOULD create or join a trace span (e.g. `"5A.S4"`), and
* annotate it with `parameter_hash`, `manifest_fingerprint`, `scenario_id`, and `run_id`.

This enables tracing flows like:

> S0 (gate) → S1 (class+scale) → S2 (shapes) → S3 (baseline λ) → **S4 (scenario λ)** → S5 (validation) → 5B (arrivals).

---

### 10.6 Integration with 5A validation & downstream segments

The **5A segment-level validation state (S5)** MUST:

* treat `merchant_zone_scenario_local_5A` (and any optional S4 outputs) as **required inputs** when building `validation_bundle_5A` for a `manifest_fingerprint`,
* re-check key S4 acceptance criteria (domain coverage, numeric bounds, overlay factor consistency) as part of the bundle,
* use S4’s run-report/logs as supporting evidence for checks and dashboards.

Downstream segments (5B, 6A) MUST:

* not use run-report/logs/layer2/5A/metrics alone as gates;
* instead, rely on:

  * data-level checks on S4 outputs, and
  * the presence and verification of `_passed.flag` produced by S5.

Within these rules, S4 is fully observable: its work is transparent, diagnosable, and tied to clear identities, while bulk scenario-intensity data remains in tables rather than logs.

---

## 11. Performance & scalability *(Informative)*

This section provides **non-binding** guidance on the performance profile of **5A.S4 — Calendar & Scenario Overlays** and how to scale it safely. It explains what grows with data size, what should stay cheap, and where to be careful.

---

### 11.1 Performance summary

S4 is a **matrix multiply over events**:

* It operates at **merchant×zone×local-horizon-bucket** granularity.
* It does, per `(m,z[,ch],h)`:

  * look up baseline intensity from S3 (`λ_base_local(m,z[,ch],kappa(h))`),
  * evaluate a deterministic overlay factor `F_overlay(m,z[,ch],h)` from event surfaces + policy,
  * compute `λ_scenario_local = λ_base_local × F_overlay`.

Heavy parts:

* Size of **S3 domain**: `N_mz = #merchant×zone[×channel]`.
* Length of **horizon**: `H_local = # local horizon buckets`.

Roughly linear in `N_mz × H_local`.

It is still cheaper than any event-level simulation (5B), but heavier than S2 because it touches *every horizon bucket*, not just one canonical week.

---

### 11.2 Workload characteristics

Let:

* `M` = # merchants in scope.
* `Z̄` = avg # zones (and channels) per merchant.
* `N_mz = M × Z̄` = # `(merchant, zone[,channel])` pairs in S3 domain (after filters).
* `H_local` = # local horizon buckets (e.g. days×slots).
* `N_events` = # scenario calendar events that intersect the horizon.

Then approximate sizes:

* **Inputs:**

  * `merchant_zone_baseline_local_5A`: O(`N_mz × T_week`) rows – but usually scanned in a coarser way (by `(m,z[,ch],k)`, not every row repeatedly).
  * Shape grid: `shape_grid_definition_5A` – tiny (`T_week` rows).
  * Scenario calendar: O(`N_events`) entries.
  * Overlay policies / configs: O(1) small JSON/YAML/Parquet.

* **Outputs:**

  * `merchant_zone_scenario_local_5A`: O(`N_mz × H_local`) rows.
  * Optional `merchant_zone_overlay_factors_5A`: same cardinality.
  * Optional `merchant_zone_scenario_utc_5A`: O(`N_mz × H_utc`) rows, where `H_utc` is UTC horizon bucket count.

So the **dominant factor** is `N_mz × H_local` (and `× H_utc` if you project to UTC).

---

### 11.3 Algorithmic complexity

For a fixed `(parameter_hash, manifest_fingerprint, scenario_id)`:

* **Input resolution / validation (Step 1)**

  * O(1) in terms of domain size; dominated by reading small control-plane artefacts and schema checks.

* **Domain construction (Step 2)**

  * One scan over `merchant_zone_baseline_local_5A` keys to build `D_S4`.
  * Complexity: O(`#rows in S3 baseline`), i.e. O(`N_mz × T_week`) in worst case, but key projection and dedup are cheap relative to full numeric work.

* **Horizon grid + mapping to local-week (Step 3)**

  * Build `H_local` and `WEEK_MAP[h]` in O(`H_local + T_week`).
  * Small compared to `N_mz × H_local`.

* **Event surfaces (Step 4)**

  * Depends on calendar structure:

    * Pre-processing events: O(`N_events × log H_local`) to map ranges onto buckets.
    * Per `(m,z[,ch],h)` event lookup ideally O(#events_active_for_bucket), which is usually small (often 0–a few events).

* **Overlay evaluation (Step 5)**

  * For each `(m,z[,ch],h)`:

    * apply a small number of policy rules / multiplications.
  * Complexity: O(`N_mz × H_local × R_overlay`) where `R_overlay` is policy complexity per bucket (kept small and bounded).

* **Intensity composition (Step 6)**

  * For each `(m,z[,ch],h)`:

    * one baseline lookup, one multiply, a few checks.
  * Complexity: O(`N_mz × H_local`).

Overall:

> **Time complexity** ≈ O(`N_mz × (T_week + H_local)` + `N_events×log H_local`)
> Dominated by **`N_mz × H_local`**.

Space:

* O(`H_local`) for horizon grid.
* O(`N_mz × H_local`) if you materialise all intensities in memory; can be reduced with chunking/streaming.

---

### 11.4 I/O profile

**Reads**

* `merchant_zone_baseline_local_5A`:

  * one scan of O(`N_mz × T_week`) rows, but you may only need aggregated weekly curves or per-bucket values once per `(m,z[,ch])`.
* `shape_grid_definition_5A`:

  * `T_week` rows, tiny.
* Scenario calendar & overlay/horizon configs:

  * a few tens/hundreds of KB typically.

**Writes**

* `merchant_zone_scenario_local_5A`:

  * O(`N_mz × H_local`) rows.
* Optional `merchant_zone_overlay_factors_5A`:

  * equal cardinality.
* Optional UTC dataset: O(`N_mz × H_utc`) rows.

I/O hotspots:

* Large `N_mz` AND large `H_local` (long horizon with fine granularity) will make S4’s output big:

  * e.g. millions of merchant×zones × thousands of buckets → billions of rows; at that point, you’ll almost certainly want to:

    * limit horizon resolution,
    * chunk across merchants and/or time,
    * and be deliberate about whether you really need UTC surfaces pre-computed.

---

### 11.5 Parallelisation & scaling strategy

S4 is very amenable to **horizontal parallelism**.

Good decomposition options:

1. **By `(merchant, zone[,channel])` domain**

   * Partition `D_S4` across workers (e.g. hash on `merchant_id`, or split by merchant ranges).

   * Each worker:

     * loads shared configs (S2 grid, overlay policy, scenario calendar/horizon) into memory,
     * iterates over its `(m,z[,ch])` subset and over all `h ∈ H_local`,
     * computes `F_overlay` and `lambda_local_scenario`,
     * writes its portion of output to a per-partition staging file.

   * Merge partitioned outputs into final dataset, ensuring deterministic ordering.

2. **By time-axis (horizon)**

   * Partition `H_local` by days or large time windows (e.g. weeks) across workers.
   * Each worker:

     * processes all merchants/zones for a subset of horizon buckets,
     * writes per-time-range staging outputs.
   * This can be attractive if events are dense but domain is moderate.

3. **Hybrid**

   * Partition by merchants and then sub-partition horizon in chunks if extremely large.

Whichever strategy you choose:

* Preserve spec’d PK and partitioning: S4 outputs ultimately sit under `fingerprint={manifest_fingerprint}/scenario_id={scenario_id}` logically as a single dataset (even if physically stored in multiple files).
* Maintain deterministic ordering within each partition (and deterministic concatenation order) to preserve idempotency and easy diffing.

---

### 11.6 Memory & streaming

Depending on scale, you may choose:

1. **In-memory for intensities**

   * For modest `N_mz × H_local`, hold intensities (and optionally overlay factors) in memory as arrays, then write once:

     * simpler implementation,
     * easier global checks.

2. **Chunked/streaming processing**

   * For large domains or horizons, use streaming / chunking:

     * **Chunk by merchants**:

       * load some subset of `(m,z[,ch])` and complete the full horizon for them,
       * write chunk rows to staging file in canonical order for those merchants.

     * **Chunk by time**:

       * process all merchants for a subset of horizon buckets and write them,
       * repeat for remaining horizon segments.

   * Maintain stable ordering (e.g. sort within chunk by PK; when merging chunks, keep a deterministic order).

Memory hotspots:

* Storing `F_overlay` and `lambda_local_scenario` for all `(m,z,h)` simultaneously.
* If memory is tight, calculate and write per chunk instead of materialising everything at once.

---

### 11.7 Failure, retry & backoff

S4 is deterministic given:

* S3 baselines,
* S2 grid,
* scenario calendar & overlay/horizon policies,
* `(parameter_hash, manifest_fingerprint, scenario_id)`.

Thus:

* **Transient failures** (I/O read/write issues):

  * May be safely retried after addressing infra problems, provided canonical outputs have not been partially overwritten.
  * Retrying will recompute the same overlays/intensities.

* **Deterministic configuration/data failures**:

  * Errors like:

    * `S4_REQUIRED_INPUT_MISSING`,
    * `S4_REQUIRED_POLICY_MISSING`,
    * `S4_HORIZON_GRID_INVALID`,
    * `S4_CALENDAR_ALIGNMENT_FAILED`,
    * `S4_OVERLAY_EVAL_FAILED`,
    * `S4_INTENSITY_NUMERIC_INVALID`

    will not be fixed by blind retries.

  * Orchestration SHOULD stop auto-retrying and surface these as configuration/data-quality issues.

  * Fix requires:

    * correcting horizon/overlay/calendar configs, or
    * fixing upstream baselines, or
    * adjusting overlay policies & parameter packs.

* **Output conflicts** (`S4_OUTPUT_CONFLICT`):

  * Indicative that scenario calendar/overlay policies or S3 baselines changed without updating `parameter_hash` or `manifest_fingerprint`.
  * Correct fix:

    * mint a new parameter pack (and/or new manifest if the world changed),
    * re-run S0–S4 under the new identity,
    * leave previous S4 outputs immutable for the old identity.

---

### 11.8 Suggested SLOs (non-binding)

Actual SLOs depend heavily on your domain size (`N_mz`) and horizon length (`H_local`), but as a rough guideline:

* For “reasonable” configurations, e.g.:

  * `N_mz` up to ~10⁵–10⁶,
  * `H_local` on the order of 10²–10³ buckets (e.g. 30–90 days × 24 hourly buckets),

  you might target:

  * **Latency per `(parameter_hash, manifest_fingerprint, scenario_id)` run:**

    * p50: seconds to low tens of seconds.
    * p95: under a few minutes with appropriate parallelism and sensible chunking.

* **Error budgets:**

  * `S4_IO_*` errors: rare, infra/transient.
  * `S4_REQUIRED_*_MISSING`, `S4_HORIZON_GRID_INVALID`, `S4_CALENDAR_ALIGNMENT_FAILED`, `S4_OVERLAY_EVAL_FAILED`, `S4_INTENSITY_NUMERIC_INVALID`:

    * treated as configuration / data issues, not normal operational noise.

---

In summary, S4 should remain a **predictable, linear-time overlay step**:

* Most of the cost is proportional to how many merchant×zones you have and how long/fine-grained the horizon is.
* It parallelises cleanly, doesn’t touch RNG, and doesn’t require complex I/O patterns beyond reading baselines and writing a single (or small set of) horizon-level tables per world+scenario.

---

## 12. Change control & compatibility *(Binding)*

This section defines how **5A.S4 — Calendar & Scenario Overlays** and its contracts may evolve over time, and what compatibility guarantees MUST hold. All rules here are **binding**.

The aims are:

* No silent breaking changes to the **structure or meaning** of scenario intensities.
* A clear separation between:

  * **Spec changes** (what S4 outputs look like / mean), and
  * **Policy / parameter-pack changes** (what the numbers are for a given world & scenario).
* Predictable behaviour for downstream consumers (5A.S5, 5B, 6A, analysis pipelines).

---

### 12.1 Scope of change control

Change control for S4 covers:

1. **Row schemas & shapes**

   * `schemas.5A.yaml#/model/merchant_zone_scenario_local_5A`
   * `schemas.5A.yaml#/model/merchant_zone_overlay_factors_5A` *(if implemented)*
   * `schemas.5A.yaml#/model/merchant_zone_scenario_utc_5A` *(if implemented)*

2. **Catalogue contracts**

   * `dataset_dictionary.layer2.5A.yaml` entries for the above datasets.
   * `artefact_registry_5A.yaml` entries for the same artefacts.

3. **Algorithm & semantics**

   * Deterministic algorithm in §6 (horizon grid, event surface construction, overlay factor evaluation, intensity composition, UTC projection).
   * Identity & partition rules in §7.
   * Acceptance & gating rules in §8.
   * Failure modes & error codes in §9.

Changes to **scenario calendar**, **overlay policies**, and **horizon configs** are treated as *parameter-pack* changes and must be reflected via `parameter_hash`, not via silent spec drift.

---

### 12.2 S4 spec version field

To support safe evolution, S4 MUST expose a **spec version**:

* `s4_spec_version` — string, e.g. `"1.0.0"`.

Binding requirements:

* `s4_spec_version` MUST be present as a **required, non-null field** in `merchant_zone_scenario_local_5A`.
* It SHOULD also be present in:

  * `merchant_zone_overlay_factors_5A`,
  * `merchant_zone_scenario_utc_5A`,
    so those tables always carry their producing spec version.

The schema anchors MUST define `s4_spec_version` as:

* type: string,
* non-nullable.

#### 12.2.1 Versioning scheme

`s4_spec_version` MUST follow semantic-style versioning:

* `MAJOR.MINOR.PATCH`

Interpretation:

* **MAJOR** — incremented for **backwards-incompatible** changes (see §12.4).
* **MINOR** — incremented for **backwards-compatible** enhancements (see §12.3).
* **PATCH** — incremented for bug fixes/clarifications that do not change schemas or observable behaviour.

Downstream components (S5, 5B, 6A) MUST:

* read `s4_spec_version`,
* treat a defined set of `MAJOR` versions as supported,
* fail fast if `s4_spec_version.MAJOR` is outside that supported set.

---

### 12.3 Backwards-compatible changes (allowed without MAJOR bump)

The following changes are considered **backwards-compatible** and MAY be introduced with a **MINOR** (or PATCH) bump, subject to the conditions below.

#### 12.3.1 Adding optional fields

Allowed:

* Adding new fields to S4 schemas that are **optional**, e.g.:

  * additional diagnostic flags (e.g. `is_holiday_bucket`, `is_payday_bucket`),
  * auxiliary metadata (e.g. `scenario_tag`, `overlays_applied`).

Conditions:

* New fields MUST NOT:

  * enter primary keys or partition keys,
  * be added to `required` lists in a way that breaks existing data.

* Consuming code MUST be able to ignore these fields without changing semantics.

#### 12.3.2 Adding optional datasets

Allowed:

* Introduction of new S4 datasets marked as `status="optional"` in the dataset dictionary and registry, provided:

  * they are derived deterministically from:

    * S3 baselines,
    * scenario calendar + overlay policies,
    * and/or S4’s existing outputs,
  * no existing consumers require them as mandatory.

Examples:

* A per-scenario aggregate, e.g. daily total λ per zone or segment, used only for auditing and dashboards.

#### 12.3.3 Adding more overlay breakdown detail

Allowed:

* Adding **decomposed overlay columns** in `merchant_zone_overlay_factors_5A` (or even in `merchant_zone_scenario_local_5A` as optional fields), e.g.:

  * `factor_holiday`, `factor_payday`, `factor_campaign`, `factor_outage`, `factor_stress`.

Conditions:

* They MUST be optional, and MUST not change the meaning of `overlay_factor_total` or `lambda_local_scenario`.
* They MUST be consistent with the current overlay policy — i.e., the product of per-event-type factors (or specified combination rule) still yields `overlay_factor_total`.

#### 12.3.4 Tighter validation & additional checks

Allowed:

* Adding new acceptance checks that only reject states that were already semantically invalid, e.g.:

  * new numeric sanity thresholds that catch obviously broken values (NaNs, huge spikes),
  * new cross-checks between local and UTC sums where UTC projection exists.

These changes are MINOR/PATCH-level and MUST NOT cause valid, previously safe outputs to be rejected unless they were actually in violation of the intended invariants.

---

### 12.4 Backwards-incompatible changes (require MAJOR bump)

The following changes are **backwards-incompatible** and MUST be accompanied by:

* a new `MAJOR` value in `s4_spec_version`, and
* a coordinated update of all S4 consumers.

#### 12.4.1 Changing primary keys or partitioning

Incompatible:

* Changing `primary_key` definitions for any S4 dataset (e.g. dropping `local_horizon_bucket_index`, changing zone representation without new fields, adding/removing `channel` from the PK).
* Changing `partition_keys` (e.g. from `["fingerprint","scenario_id"]` to `["parameter_hash","scenario_id"]`).

Such changes break join and identity assumptions for downstream consumers.

#### 12.4.2 Changing λ_scenario semantics

Incompatible:

* Changing what `lambda_local_scenario` or `lambda_utc_scenario` actually represents without renaming/reshaping fields, e.g.:

  * from “expected arrivals per horizon bucket” to “per-second rate” or “dimensionless index”;
  * changing the implicit time window associated with each horizon bucket without adjusting field names or grid configuration.

These changes MUST either:

* introduce new fields and deprecate old ones, **or**
* bump `MAJOR` and document the new semantics explicitly.

#### 12.4.3 Changing horizon semantics

Incompatible:

* Changing the horizon representation in-place, e.g.:

  * from `local_horizon_bucket_index` to `(local_date, local_bucket_within_date)` without new fields/anchors,
  * changing horizon boundaries in a way that invalidates downstream assumptions (e.g. previously horizon always 30 days, now 90 days, but same interpretation in code).

If horizon semantics change in a way that consumers care about, it MUST be reflected either in:

* new schema fields, or
* a MAJOR bump and a changed contract for horizon interpretation.

#### 12.4.4 Changing overlay combination rules

Incompatible:

* Changing global overlay combination semantics (e.g. from “multiply all factors” to “take max” or “sum of additive factors”):

  * when downstream systems rely on specific expected multiplicative behaviour,
  * when the same `overlay_factor_total` field is used but its meaning is materially changed.

Any such change MUST be treated as a MAJOR spec change, and overlay policies + consumers must be updated accordingly.

---

### 12.5 Compatibility of code with existing S4 data

Implementations of S4 and its consumers MUST handle **older S4 outputs** according to their `s4_spec_version`.

#### 12.5.1 Reading older S4 outputs

When consuming S4 datasets:

* If `s4_spec_version.MAJOR` is within the supported range:

  * Consumers MUST:

    * interpret schemas and semantics according to that MAJOR version,
    * treat unknown optional fields as absent,
    * treat unknown flags and metadata as “ignore / noop”.

* If `s4_spec_version.MAJOR` is **greater** than supported:

  * Consumers MUST treat these outputs as **unsupported** and fail with a clear “unsupported S4 spec version” error, not attempt a best-effort interpretation.

#### 12.5.2 Re-running S4 with newer code

When S4 is upgraded and re-run for the same `(parameter_hash, manifest_fingerprint, scenario_id)`:

* If S1/S2/S3 outputs and S4 policies/configs are unchanged:

  * S4 SHOULD produce byte-identical outputs.
  * If not (due to bug fix or subtle numeric changes), you must consider:

    * whether this should be treated as `S4_OUTPUT_CONFLICT`, forcing a new identity, or
    * whether it’s acceptable to overwrite minor numeric differences; by default, the spec expects **no overwrite** unless explicitly chosen and coordinated.

* If S1/S2/S3 outputs or S4 policies/configs have changed in any way that materially affects outputs:

  * The change MUST be represented via a new `parameter_hash` and/or `manifest_fingerprint`.
  * S4 MUST treat attempts to overwrite old outputs under the old identity as `S4_OUTPUT_CONFLICT`.

---

### 12.6 Interaction with parameter packs & upstream changes

Most changes in S4 **values** (i.e. overlay factors and λ_scenario) should arise from:

* **Parameter pack changes** (`parameter_hash`), and
* **Scenario calendar/overlay config changes**, not spec changes.

#### 12.6.1 Policy/calendar/horizon changes & `parameter_hash`

Any change to:

* scenario calendar artefacts (event times, scopes, event types),
* overlay policies (`scenario_overlay_policy_5A`, etc.),
* horizon config for S4 (`scenario_horizon_config_5A`),
* or other S4-relevant 5A policies,

MUST result in:

* a new **parameter pack**, and thus a new `parameter_hash`, and
* re-running S0–S4 for each affected `manifest_fingerprint` + scenario.

S4 spec version (`s4_spec_version`) may remain constant if the structural/semantic contract does not change.

#### 12.6.2 Upstream S1–S3 spec changes

If S1, S2, or S3 evolve in a backwards-incompatible way:

* they will bump their own spec versions (`s1_spec_version`, `s2_spec_version`, `s3_spec_version`), and
* S4 MUST:

  * be updated to understand the new versions,
  * potentially bump `s4_spec_version.MAJOR` if semantics at S4 level change, and
  * refuse to operate on S1/S2/S3 outputs with unsupported MAJOR spec versions.

---

### 12.7 Governance & documentation

Any change to S4 contracts MUST be governed and documented.

1. **Spec & contract updates**

   * Changes to S4’s spec (§§1–12) MUST be accompanied by:

     * updates to `schemas.5A.yaml` for S4 anchors,
     * updates to `dataset_dictionary.layer2.5A.yaml` entries,
     * updates to `artefact_registry_5A.yaml` entries for S4 outputs.

2. **Release notes**

   * Every change that bumps `s4_spec_version` MUST be documented, including:

     * previous → new version,
     * MAJOR/MINOR/PATCH classification,
     * description of what changed (schema vs semantics vs validation),
     * migration guidance (e.g. “re-run S4 for all active worlds” vs “only new parameter packs are affected”).

3. **Testing**

   * New S4 implementations MUST be tested against:

     * synthetic small worlds (few merchants, zones, events) to validate semantics and invariants,
     * representative large worlds (N_mz large, H_local long) to test performance and numeric stability.

   * Tests MUST cover:

     * idempotency (same inputs → same outputs),
     * conflict detection (`S4_OUTPUT_CONFLICT` scenarios),
     * each canonical error code (required inputs missing, horizon grid invalid, calendar alignment, overlay eval, numeric failures),
     * backwards-compatibility (reading S4 outputs from older `s4_spec_version.MAJOR` values within support).

---

Within these rules, 5A.S4 can evolve in a controlled, predictable way:

* **What** the scenario intensities are changes with parameter packs, calendar content, and overlay policies.
* **How** they are structured, keyed, interpreted, and validated changes only via explicit, versioned spec evolution with clear MAJOR/MINOR/PATCH semantics and coordinated updates to all consumers.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects short-hands, symbols, and abbreviations used in the **5A.S4 — Calendar & Scenario Overlays** spec. It is **informative** only; binding definitions live in §§1–12.

---

### 13.1 Notation conventions

* **Monospace** (e.g. `merchant_zone_scenario_local_5A`) → concrete dataset / field / config names.
* **UPPER_SNAKE** (e.g. `S4_INTENSITY_NUMERIC_INVALID`) → canonical error codes.
* `"Quoted"` (e.g. `"PASS"`, `"REQUIRED"`) → literal enum/string values.
* Single letters:

  * `m` → merchant
  * `z` → zone (country+tz pair or `zone_id`)
  * `ch` → channel / channel_group (if modelled)
  * `k` → local-week bucket index (from S2/S3 grid)
  * `h` → local horizon bucket index (S4 horizon)
  * `h_utc` → UTC horizon bucket index

---

### 13.2 Identity & scope symbols

| Symbol / field         | Meaning                                                                                               |
| ---------------------- | ----------------------------------------------------------------------------------------------------- |
| `parameter_hash`       | Opaque identifier of the **parameter pack** (5A policies, shape configs, scenario configs) used.      |
| `manifest_fingerprint` | Opaque identifier of the **closed-world manifest** for this run.                                      |
| `scenario_id`          | Scenario identifier (e.g. `"baseline"`, `"bf_2027_stress"`).                                          |
| `run_id`               | Identifier of this execution of S4 for a given `(parameter_hash, manifest_fingerprint, scenario_id)`. |
| `s4_spec_version`      | Semantic version of the S4 spec that produced the scenario outputs (e.g. `"1.0.0"`).                  |
| `T_week`               | Number of local-week buckets in the S2/S3 grid (from `shape_grid_definition_5A`).                     |
| `H_local`              | Number of local horizon buckets in the S4 horizon.                                                    |
| `H_utc`                | Number of UTC horizon buckets (if UTC projection is used).                                            |

---

### 13.3 Key datasets & artefacts (S4-related)

| Name / ID                          | Description                                                                                                 |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `merchant_zone_scenario_local_5A`  | **Required** S4 output: per `(m,z[,ch], local_horizon_bucket)` scenario-adjusted local λ.                   |
| `merchant_zone_overlay_factors_5A` | Optional S4 output: per `(m,z[,ch], local_horizon_bucket)` combined overlay factor (and breakdown).         |
| `merchant_zone_scenario_utc_5A`    | Optional S4 output: per `(m,z[,ch], utc_horizon_bucket)` scenario-adjusted UTC λ.                           |
| `merchant_zone_baseline_local_5A`  | S3 output: per `(m,z[,ch], k)` baseline local-week λ (pre-calendar).                                        |
| `shape_grid_definition_5A`         | S2 output: local-week time grid (`bucket_index → local day/time`).                                          |
| `merchant_zone_profile_5A`         | S1 output: per-merchant×zone demand class + base scale.                                                     |
| `scenario_calendar_5A`             | Calendar artefact(s): events (holidays, paydays, campaigns, outages, stress, etc.) with scopes/time ranges. |
| `scenario_horizon_config_5A`       | Horizon config: start/end, bucket duration, and mapping between horizon buckets and local time-of-week.     |
| `scenario_overlay_policy_5A`       | Overlay policy: rules mapping events → multiplicative factors and combination/precedence rules.             |

(Exact `artifact_id` / `manifest_key` live in dictionaries/registries.)

---

### 13.4 Core mathematical symbols

| Symbol / expression              | Meaning                                                                                                               |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `D_S3`                           | S3 domain: set of `(merchant_id, zone_representation[, channel])` pairs with baselines for this world+scenario.       |
| `D_S4`                           | S4 domain: S3 domain after any S4-specific policy filters.                                                            |
| `H_local`                        | Set of local horizon buckets for this scenario.                                                                       |
| `H_utc`                          | Set of UTC horizon buckets (if UTC projection is computed).                                                           |
| `k`                              | Local-week bucket index in S2/S3 grid (`0 ≤ k < T_week`).                                                             |
| `h`                              | Local horizon bucket index in S4 horizon (`0 ≤ h < H_local`), or equivalent `(local_date, local_bucket_within_date)`. |
| `h_utc`                          | UTC horizon bucket index, or equivalent `(utc_date, utc_bucket_within_date)`.                                         |
| `κ(h)` / `kappa(h)`              | Mapping from local horizon bucket `h` to local-week bucket index `k` (via day-of-week/time-of-day).                   |
| `λ_base_local(m,z[,ch],k)`       | Baseline local intensity from S3 for merchant×zone[×channel] at weekly bucket `k`.                                    |
| `F_overlay(m,z[,ch],h)`          | Composite overlay factor applied at horizon bucket `h` (≥ 0).                                                         |
| `λ_scenario_local(m,z[,ch],h)`   | Scenario-adjusted local intensity at horizon bucket `h`: `λ_base_local(m,z,kappa(h)) × F_overlay(m,z,h)`.             |
| `λ_utc_scenario(m,z[,ch],h_utc)` | Scenario-adjusted intensity mapped onto a UTC horizon bucket `h_utc` (if computed).                                   |
| `EVENTS(m,z[,ch],h)`             | Set of active scenario events for merchant×zone[×channel] at horizon bucket `h`.                                      |

---

### 13.5 Key fields in `merchant_zone_scenario_local_5A`

*(Exact schema in §5; this table summarises semantics.)*

| Field name                   | Meaning                                                                                            |
| ---------------------------- | -------------------------------------------------------------------------------------------------- |
| `manifest_fingerprint`       | World identity; MUST match `fingerprint` partition token.                                          |
| `parameter_hash`             | Parameter pack identity; same as in S0/S1/S2/S3 for this run.                                      |
| `scenario_id`                | Scenario identifier; MUST match partition token.                                                   |
| `merchant_id`                | Merchant key.                                                                                      |
| `legal_country_iso`          | Country portion of the zone (if using explicit `(country, tzid)`).                                 |
| `tzid`                       | IANA timezone identifier for the zone (if using explicit representation).                          |
| `zone_id`                    | Optional combined zone key if you adopt a single-field representation.                             |
| `channel` / `channel_group`  | Optional channel dimension (e.g. `"POS"`, `"ECOM"`, `"HYBRID"`).                                   |
| `local_horizon_bucket_index` | Local horizon bucket index (or `(local_date, local_bucket_within_date)` fields) for time position. |
| `lambda_local_scenario`      | Scenario-adjusted local intensity for this `(m,z[,ch])` in this horizon bucket.                    |
| `overlay_factor_total`       | Optional: combined multiplicative factor applied on baseline in this bucket.                       |
| `s4_spec_version`            | S4 spec version that produced this row.                                                            |

---

### 13.6 Key fields in `merchant_zone_overlay_factors_5A` (optional)

| Field name                | Meaning                                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Same identity & time keys | `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `merchant_id`, zone representation, horizon bucket. |
| `overlay_factor_total`    | Combined multiplicative factor applied to `lambda_base_local` for this `(m,z[,ch],h)`.                       |
| `factor_holiday`          | Optional per-type factor for holiday effects (if policy decomposes overlays).                                |
| `factor_payday`           | Optional per-type factor for paydays.                                                                        |
| `factor_campaign`         | Optional per-type factor for campaigns.                                                                      |
| `factor_outage`           | Optional per-type factor for outages (often 0 or strong downscale).                                          |
| `factor_stress`           | Optional per-type factor for stress scenarios.                                                               |
| `overlays_applied`        | Optional list/bitmask of event categories applied at this horizon bucket.                                    |
| `s4_spec_version`         | S4 spec version (same as in local scenario dataset).                                                         |

All per-type factor fields, if present, MUST multiply/compose into `overlay_factor_total` according to the overlay policy.

---

### 13.7 Key fields in `merchant_zone_scenario_utc_5A` (optional)

| Field name                               | Meaning                                                                                  |
| ---------------------------------------- | ---------------------------------------------------------------------------------------- |
| `manifest_fingerprint`                   | World identity.                                                                          |
| `parameter_hash`                         | Parameter pack identity.                                                                 |
| `scenario_id`                            | Scenario identity.                                                                       |
| `merchant_id`                            | Merchant key.                                                                            |
| `legal_country_iso` / `tzid` / `zone_id` | Zone representation.                                                                     |
| `utc_horizon_bucket_index`               | UTC horizon bucket index (or `(utc_date, utc_bucket_within_date)` if you use date+slot). |
| `lambda_utc_scenario`                    | Scenario-adjusted UTC intensity for this `(m,z[,ch])` and UTC horizon bucket.            |
| `s4_spec_version`                        | S4 spec version that produced this row.                                                  |

---

### 13.8 Error codes (5A.S4)

Canonical S4 error codes from §9, for quick reference:

| Code                              | Brief description                                               |
| --------------------------------- | --------------------------------------------------------------- |
| `S4_GATE_OR_S3_INVALID`           | S0/S1–S3 gating or alignment invalid.                           |
| `S4_UPSTREAM_NOT_PASS`            | Upstream Layer-1 segments not all `"PASS"`.                     |
| `S4_REQUIRED_INPUT_MISSING`       | Required S1/S2/S3/scenario artefact missing.                    |
| `S4_REQUIRED_POLICY_MISSING`      | Required overlay or horizon policy missing/invalid.             |
| `S4_HORIZON_GRID_INVALID`         | Horizon grid invalid or cannot be mapped to weekly grid.        |
| `S4_CALENDAR_ALIGNMENT_FAILED`    | Scenario calendar cannot be aligned to horizon/domain.          |
| `S4_OVERLAY_EVAL_FAILED`          | Overlay policy cannot produce a valid factor.                   |
| `S4_INTENSITY_NUMERIC_INVALID`    | λ_scenario or factors invalid (NaN/Inf/negative/out-of-bounds). |
| `S4_OUTPUT_CONFLICT`              | Existing S4 outputs differ from recomputed ones.                |
| `S4_IO_READ_FAILED`               | I/O read error on required inputs.                              |
| `S4_IO_WRITE_FAILED`              | I/O write/commit error.                                         |
| `S4_INTERNAL_INVARIANT_VIOLATION` | Internal “should never happen” condition.                       |

These codes appear only in run-report/logs, not in data schemas.

---

### 13.9 Miscellaneous abbreviations

| Abbreviation | Meaning                                                                            |
| ------------ | ---------------------------------------------------------------------------------- |
| S0           | State 0 — Gate & Sealed Inputs (Segment 5A).                                       |
| S1           | State 1 — Merchant & Zone Demand Classification.                                   |
| S2           | State 2 — Weekly Shape Library.                                                    |
| S3           | State 3 — Baseline Merchant×Zone Weekly Intensities.                               |
| S4           | State 4 — Calendar & Scenario Overlays (this spec).                                |
| S5           | Segment 5A validation & HashGate (validation bundle + `_passed.flag`).          |
| L1 / L2      | Layer-1 / Layer-2.                                                                 |
| “baseline”   | Shorthand for S3’s `lambda_local_base`.                                            |
| “scenario”   | Shorthand for S4’s `lambda_local_scenario` (and `lambda_utc_scenario` if present). |

This appendix is meant as a quick reference when implementing or reviewing S4; authoritative behaviour and contracts are defined in §§1–12.

---