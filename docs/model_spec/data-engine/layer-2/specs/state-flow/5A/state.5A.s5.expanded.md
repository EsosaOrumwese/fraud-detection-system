# 5A.S5 — Segment Validation & HashGate (Layer-2 / Segment 5A)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5A.S5 — Segment Validation & HashGate** for **Layer-2 / Segment 5A**. It is binding on any implementation of this state.

---

### 1.1 Role of 5A.S5 in Segment 5A

5A.S5 is the **final validation and sealing state** for Segment 5A.

For a given **world** identified by `manifest_fingerprint` (and, within that world, for all 5A parameter packs and scenarios that have been produced), S5:

* Re-reads the **control-plane** artefacts:

  * `s0_gate_receipt_5A`, `sealed_inputs_5A`.

* Re-reads the **modelling outputs** from 5A.S1–S4:

  * S1: `merchant_zone_profile_5A`.
  * S2: `shape_grid_definition_5A`, `class_zone_shape_5A`.
  * S3: `merchant_zone_baseline_local_5A` (and any optional S3 aggregates/UTC surfaces).
  * S4: `merchant_zone_scenario_local_5A` (and any optional overlay/UTC surfaces).

* Re-checks, in a **coherent, cross-state way**, that all binding contracts are satisfied:

  * S0’s sealed input universe and upstream status invariants.
  * S1’s classing and base-scale contracts.
  * S2’s grid and shape normalisation contracts.
  * S3’s baseline λ contracts.
  * S4’s overlay and scenario-intensity contracts.

* Produces a **validation artefact bundle and pass flag**:

  * `validation_bundle_5A` under
    `data/layer2/5A/validation/fingerprint={manifest_fingerprint}/…`
  * `_passed.flag_5A` in the same fingerprint partition, containing a digest over the bundle.

5A.S5 is:

* **RNG-free** — it MUST NOT consume RNG or emit new RNG events; it only reads and checks existing outputs.
* **Non-modelling** — it MUST NOT generate new data surfaces beyond validation reports/index/flag; it validates the existing S0–S4 surfaces.
* **Authoritative for 5A PASS** — it is the **sole state** allowed to declare a 5A world “PASS” via `_passed.flag_5A`.

S5 exists to enforce the Layer-2 gate:

> For a given `manifest_fingerprint`:
> **no verified `_passed.flag_5A` → no consumer is allowed to treat any 5A outputs (S1–S4) as authoritative.**

---

### 1.2 Objectives

5A.S5 MUST:

* **Establish a single, unambiguous PASS/FAIL verdict for 5A per world**

  * For each `manifest_fingerprint`, S5 MUST determine whether 5A is **globally healthy enough** to be consumed, based on the state of:

    * S0: gate & sealed inputs, upstream 1A–3B PASS status.
    * S1: class & base-scale integrity.
    * S2: time-grid and shape integrity.
    * S3: baseline λ integrity.
    * S4: horizon mapping and scenario λ integrity.

* **Materialise a reproducible validation bundle**

  * Build a `validation_bundle_5A` tree containing:

    * machine-readable **reports** of the checks performed,
    * any **issue tables** and metrics,
    * an **index** listing all bundle members and their digests.

* **Produce a cryptographically bound pass flag**

  * Compute a deterministic `bundle_digest` (e.g. SHA-256) over the bundle contents (as listed in the index).
  * Write `_passed.flag_5A` as a tiny, schema-governed artefact containing this digest.
  * Downstream can re-compute and cross-check this digest to ensure that:

    * the bundle is complete, and
    * no files have been altered.

* **Remain deterministic and side-effect-free on upstream**

  * Never edit, delete, or regenerate S0–S4 outputs; only read and verify them.
  * Be safe to re-run: rerunning S5 for a given `manifest_fingerprint` with unchanged inputs either:

    * reproduces the same bundle and flag, or
    * no-ops if the bundle is already present and identical.

---

### 1.3 In-scope behaviour

The following activities are **in scope** for 5A.S5 and MUST be performed in this state (not spread across S1–S4 or downstream):

* **Global gating on S0 / upstream 1A–3B**

  * Re-validate S0’s gate and sealed inputs, including:

    * `s0_gate_receipt_5A.parameter_hash` / `manifest_fingerprint` consistency,
    * sealed-inputs digest consistency,
    * `verified_upstream_segments` all `status="PASS"` for 1A–3B.

* **Discovery of 5A outputs to validate**

  * Using `sealed_inputs_5A` and the 5A dataset dictionary/registry, discover all 5A outputs associated with this fingerprint, including:

    * all `(parameter_hash, scenario_id)` combinations for which S1–S4 datasets exist.

* **Per-state validation of S1–S4**

  For each discovered `(parameter_hash, scenario_id)`:

  * **S1 checks**:

    * `merchant_zone_profile_5A` schema & PK,
    * completeness of `demand_class`,
    * base scale fields non-negative / finite,
    * domain against upstream merchant/zone references.

  * **S2 checks**:

    * `shape_grid_definition_5A` contiguity of `bucket_index`,
    * `class_zone_shape_5A` non-negative `shape_value`,
    * per-class×zone[×channel] Σ shape = 1 (within tolerance),
    * domain alignment with S1 classes/zones.

  * **S3 checks**:

    * `merchant_zone_baseline_local_5A` non-negative λ and PK integrity,
    * domain alignment with S1×S2 (per `(merchant, zone)` has `T_week` baselines),
    * weekly sum vs base scale invariants (if that is the contract).

  * **S4 checks**:

    * horizon grid mapping correctness (no unmapped buckets),
    * domain/horizon coverage (every baseline merchant×zone has scenario λ across horizon),
    * overlay factor bounds and numeric sanity,
    * λ_scenario non-negative and finite.

* **Aggregation of validation results into structured artefacts**

  * Building:

    * a consolidated `validation_report_5A` (or equivalent) capturing:

      * per-check status (`PASS` / `FAIL` / `WARN`),
      * key metrics (max errors, counts, domain sizes, etc.),
      * per-parameter-pack / per-scenario summaries.
    * optional `validation_issue_table_5A` listing individual issues with codes and references to offending keys.

* **Bundle index and digest computation**

  * Constructing a canonical `validation_bundle_index_5A.json` (or similar) listing:

    * every evidence file in the bundle,
    * each file’s relative path and digest.
  * Computing a single `bundle_digest` from the bundle contents according to the fixed hashing law.

* **Creation of `_passed.flag_5A`**

  * Writing a small, schema-governed flag artefact that:

    * references the bundle, and
    * encodes the `bundle_digest`.

---

### 1.4 Out-of-scope behaviour

The following activities are explicitly **out of scope** for 5A.S5 and MUST NOT be performed by this state:

* **Any modelling or transformation of 5A outputs**

  * S5 MUST NOT:

    * recompute S1 classes or base scales,
    * recompute S2 shapes,
    * recompute S3 baselines,
    * recompute S4 overlays or intensities.

  It may repeat calculations only for validation (e.g. re-sum shapes to check Σ=1), not to write new modelling surfaces.

* **Changing or patching upstream artefacts**

  * S5 MUST NOT:

    * modify, delete, or republish S0–S4 artefacts,
    * “fix up” data or apply hot-patches to broken outputs.
  * If S5 detects invalidities, it must report them and treat the world as failed, not attempt silent repairs.

* **Generating any new 5A model datasets**

  * S5 outputs are strictly validation artefacts (reports, indices, flags).
  * It MUST NOT emit new S1–S4-style modelling tables (e.g. alternate baselines, alternate scenario surfaces).

* **Consuming or producing RNG**

  * S5 MUST NOT consume RNG or log RNG events.
  * It is entirely deterministic w.r.t. inputs.

* **Partial PASS semantics**

  * S5 MUST NOT introduce partial “PASS for S1–S3 but FAIL for S4” semantics at the gate level.
  * Its job is to express internal detail in the report, but the **gate itself** is binary per fingerprint: PASS or FAIL.

---

### 1.5 Downstream obligations

This specification imposes the following obligations on all downstream segments and consumers (including 5B, 6A, and any external analysis/serving pipelines):

* **Enforce the 5A PASS gate**

  * Any component that reads Segment 5A modelling artefacts (S1–S4 outputs) for a given `manifest_fingerprint` MUST:

    1. Locate `validation_bundle_5A` and `_passed.flag_5A` for that fingerprint via the catalogue.
    2. Verify that `_passed.flag_5A` is structurally valid and that its digest matches a recomputed `bundle_digest` over the bundle contents.

  * If `_passed.flag_5A` is missing or invalid, the consumer MUST treat all 5A outputs for that world as **non-authoritative** and MUST NOT use them to drive simulations, decisions, or evaluations.

* **Treat S5 as the authoritative summary of 5A health**

  * Consumers concerned with 5A quality MUST:

    * consult `validation_report_5A` and any `validation_issue_table_5A` to understand:

      * which internal checks passed or failed,
      * which `(parameter_hash, scenario_id)` combinations are degraded.

  * They MUST NOT rely on ad-hoc local checks of S1–S4 in place of S5 if a bundle is present.

* **Do not modify 5A validation artefacts**

  * No downstream component may modify or regenerate:

    * `validation_bundle_5A`,
    * `_passed.flag_5A`,
      for any `manifest_fingerprint`.
  * Any change in 5A behaviour (including bug fixes or new policies) MUST go through:

    * regenerated S0–S4 outputs,
    * a new S5 run producing a new bundle/flag,
    * or (if behaviour-breaking) a new `manifest_fingerprint`.

Within this scope, 5A.S5 is the **single, deterministic authority** that says “this 5A world is green and sealed” and provides verifiable evidence; every downstream consumer of 5A data is expected to honour that gate.

---

## 2. Preconditions & sealed inputs *(Binding)*

This section defines **when 5A.S5 — Segment Validation & HashGate** is allowed to run, and what sealed inputs it must have access to. These requirements are **binding**.

S5 is designed to be able to run even when S1–S4 are incomplete or broken — in that case it will produce a **FAILED** validation bundle, not throw its hands up and disappear.
Preconditions here are about *being able to inspect* the world, not about the world already being valid.

---

### 2.1 Invocation context

5A.S5 MUST only be invoked in the context of a well-defined **world**:

* `manifest_fingerprint` — identifies the closed-world manifest whose 5A outputs S5 will validate.
* `run_id` — identifies this execution of S5 for that fingerprint.

These values:

* MUST be supplied by the orchestration layer;
* MUST remain constant for the duration of the S5 run;
* MUST be used to resolve all fingerprint-scoped artefacts (S0, sealed inputs, validation bundle paths).

> **Note:**
> `parameter_hash` and `scenario_id` are *discovered* from S0/5A outputs, not fixed in the S5 invocation. A given `manifest_fingerprint` may have multiple scenarios; S5 validates *all* parameter packs / scenarios it discovers for that world.

S5 MUST NOT try to redefine `manifest_fingerprint` or inject its own parameter packs or scenarios.

---

### 2.2 Catalogue & contract availability

Before S5 can run, the following **contracts** MUST be available and parseable in the environment:

1. **Layer-1 contracts**

   * `schemas.layer1.yaml` and `schemas.ingress.layer1.yaml`.
   * Dataset dictionaries and artefact registries for segments 1A–3B.

2. **Layer-2 / 5A contracts**

   * `schemas.layer2.yaml` and `schemas.5A.yaml` containing:

     * all S0–S4 schema anchors,
     * S5 validation schema anchors (bundle index, report, issue table, etc.).
   * `dataset_dictionary.layer2.5A.yaml` with entries for:

     * S0–S4 datasets,
     * S5 validation bundle & `_passed.flag_5A`.
   * `artefact_registry_5A.yaml` with entries for:

     * S0–S4 artefacts,
     * S5 validation artefacts.

3. **No direct-path / network discovery**

   * S5 MUST rely exclusively on dictionaries/registries + `sealed_inputs_5A` + `s0_gate_receipt_5A` for discovering all artefacts.
   * It MUST NOT use:

     * hard-coded filesystem paths,
     * ad-hoc directory walks,
     * direct network calls to find inputs.

If any of these contracts are missing or unparsable, S5 MUST treat this as a configuration error and MUST NOT proceed.

---

### 2.3 Required sealed inputs for S5

S5 works over a **sealed world**; the minimum sealed inputs for a `manifest_fingerprint` are:

1. **S0 gate & sealed inventory**

   * `s0_gate_receipt_5A` — fingerprint-scoped, must exist and be schema-valid.
   * `sealed_inputs_5A` — fingerprint-scoped, must exist and be schema-valid.

These two artefacts are **non-negotiable preconditions**. Without them, S5 cannot even know what it is allowed to read.

2. **Bindings between S0 fields and run context**

   From `s0_gate_receipt_5A`, S5 MUST be able to read:

   * `parameter_hash` — active parameter pack for this fingerprint.
   * `verified_upstream_segments[1A..3B]` — upstream status map.
   * `sealed_inputs_digest` — digest over `sealed_inputs_5A`.

And from `sealed_inputs_5A`, S5 MUST be able to resolve:

* which 5A artefacts (S1–S4 outputs, 5A policies/configs) exist for this fingerprint, and
* their `schema_ref`, `path_template`, `role`, `status`, `read_scope`, and `sha256_hex`.

If either `s0_gate_receipt_5A` or `sealed_inputs_5A` is missing or cannot be parsed/schema-validated, S5 MUST fail immediately and MUST NOT attempt to inspect S1–S4 outputs.

---

### 2.4 Discoverable 5A outputs & policies

For a given `manifest_fingerprint`, S5’s job is to validate **whatever 5A has produced** — not to require that every possible combination is present as a precondition.

However, S5 MUST be able to *discover* the following via `sealed_inputs_5A` + dictionary/registry:

1. **S1–S4 modelling datasets (by class of artefact)**

   For each discovered `(parameter_hash, scenario_id)` pair present in S3/S4, S5 MUST be able to resolve entries for:

   * S1:

     * `merchant_zone_profile_5A`.
   * S2:

     * `shape_grid_definition_5A`,
     * `class_zone_shape_5A`.
   * S3:

     * `merchant_zone_baseline_local_5A`
     * (and any optional S3 aggregates/UTC datasets declared in the dictionary).
   * S4:

     * `merchant_zone_scenario_local_5A`
     * (and any optional overlay/UTC datasets declared in the dictionary).

**Important:**

* Existence of these artefacts on disk is **not** a precondition for running S5.
* If they are missing or invalid, S5 is expected to record this as a validation failure (and the world will not PASS), not to refuse to run.

2. **5A policies & configs relevant to validation**

S5 MUST also be able to resolve the policies/configs that encode the **contracts** it validates, including at least:

* S1 policies:

  * classing & scale policies that define valid `demand_class` values and base-scale semantics.

* S2 policies:

  * time-grid policy (bucket duration, `T_week`, local-week mapping),
  * shape library policy (normalisation expectations, domain of `(demand_class, zone[,channel])`).

* S3 policies:

  * baseline intensity policy (weekly-sum vs base-scale constraints; numeric bounds).

* S4 policies:

  * scenario overlay policy (event→factor mapping; factor bounds; precedence rules),
  * horizon configuration (local/UTC grids and mapping).

If these policies/configs are not discoverable for the relevant `parameter_hash` (as indicated by S0), S5 can still run, but MUST treat the affected checks as failing and report them as configuration/contract failures.

---

### 2.5 Mode of operation vs preconditions

S5 MAY be invoked in one of two logical modes (implementation detail), but its **preconditions** do not change:

1. **Per-fingerprint mode (recommended)**

   * Invocation context is just `manifest_fingerprint` + `run_id`.
   * S5:

     * reads S0/S1–S4 + policies,
     * discovers all `(parameter_hash, scenario_id)` combinations present in sealed inputs and 5A outputs for this world,
     * validates all of them,
     * emits a **single** `validation_bundle_5A` and `_passed.flag_5A` summarising the entire world.

2. **Per-fingerprint, multi-run mode**

   * Implementation may internally batch-check each `(parameter_hash, scenario_id)` separately, but MUST still:

     * write a single bundle/flag per `manifest_fingerprint`,
     * reflect every sub-run’s status in the final bundle.

In both cases, the **only hard preconditions** are:

* S0 gate + sealed_inputs are present and valid.
* Dictionaries/registries are available and coherent.
* S5 can *attempt* to resolve S1–S4 outputs and 5A policies (even if some are missing).

S5 MUST NOT require that S1–S4 are “complete” as a precondition; their absence/incompleteness is precisely what S5 is supposed to detect and record.

---

### 2.6 Authority of sealed inputs

The following boundaries are binding for S5:

1. **`sealed_inputs_5A` is the universe of admissible inputs**

   * S5 MUST NOT read any artefact (dataset, policy, config) that is not represented as a row in `sealed_inputs_5A` for this `manifest_fingerprint`.
   * Even if files exist on disk, if they are not sealed in `sealed_inputs_5A`, they are considered **out-of-bounds** for S5.

2. **S0 is the authority for upstream status & parameter pack**

   * S5 MUST treat:

     * `s0_gate_receipt_5A.parameter_hash` as the pack identity for this world, and
     * `s0_gate_receipt_5A.verified_upstream_segments` as the authoritative record of 1A–3B `PASS`/`FAIL`/`MISSING` status.

   * S5 MAY re-check presence of upstream validation bundles/flags as part of its own evidence, but MUST NOT attempt to redefine the upstream hashing laws.

3. **No “side-door” inputs**

   * S5 MUST NOT:

     * fetch external metrics/event logs,
     * pull in raw Layer-1 fact tables,
     * use environment variables/flags as hidden inputs to change validation semantics.

   Any input that materially affects validation logic MUST be part of the parameter pack and recorded in `sealed_inputs_5A`.

Within these preconditions and boundaries, 5A.S5 always runs against a **sealed, catalogue-defined world**: it knows exactly what 5A claims to have produced, exactly what contracts apply, and its job is to validate and seal that world — not to improvise or depend on unversioned state.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **exactly what 5A.S5 may read**, how those inputs are discovered, and which components are authoritative for which facts. All rules here are **binding**.

S5 is **RNG-free** and **read-only**: it may only inspect artefacts that are:

* declared in `sealed_inputs_5A` for the target `manifest_fingerprint`, and
* described in the dataset dictionary and artefact registry.

It MUST NOT read or mutate anything outside that sealed universe.

---

### 3.1 Input categories (high-level)

S5’s inputs fall into five categories:

1. **Control-plane from S0**
   – `s0_gate_receipt_5A` and `sealed_inputs_5A`.

2. **5A modelling outputs (S1–S4)**
   – the actual 5A datasets whose invariants S5 re-checks.

3. **5A policies & configs**
   – class/scale, shape, baseline and overlay policies that define the contracts S5 validates.

4. **Upstream validation artefacts (Layer-1, optional)**
   – 1A–3B bundles/flags, used to corroborate S0’s upstream status if desired.

5. **Validation-level configuration (tolerances, spec versions)**
   – optional configs that parameterise S5’s checks.

All of these MUST be discovered via `sealed_inputs_5A` and must be schema-governed through `schemas.*` and the dataset dictionary.

---

### 3.2 Control-plane inputs (S0)

#### 3.2.1 `s0_gate_receipt_5A`

**Role**

* Anchors S5’s understanding of the world and parameter pack:

  * `manifest_fingerprint` — world identity.
  * `parameter_hash` — parameter pack identity.
  * `verified_upstream_segments` — 1A–3B statuses.
  * `sealed_inputs_digest` — digest over `sealed_inputs_5A`.

**Authority boundary**

* S5 MUST treat `s0_gate_receipt_5A` as the **only authority** for:

  * which `(manifest_fingerprint, parameter_hash)` pair it is validating,
  * what S0 believes the 1A–3B statuses to be,
  * which sealed-inputs universe is in scope.

* S5 MAY corroborate upstream status (e.g. by checking upstream bundles/flags) but MUST NOT redefine upstream hashing laws or silently contradict S0 without reporting it as an error.

#### 3.2.2 `sealed_inputs_5A`

**Role**

* Enumerates all artefacts that 5A is allowed to use for this `manifest_fingerprint`.

Each row provides:

* `owner_layer`, `owner_segment`, `artifact_id`, `role`, `status`, `read_scope`,
* `schema_ref`, `path_template`, `partition_keys`, `sha256_hex`,
* `source_dictionary`, `source_registry`.

**Authority boundary**

* `sealed_inputs_5A` is the **exclusive catalogue** S5 may use:

  * If an artefact is not present as a row in `sealed_inputs_5A`, S5 MUST treat it as **out-of-bounds**, even if it exists physically.
  * S5 MUST respect `status`:

    * `"REQUIRED"` → absence or schema mismatch is a **validation failure**.
    * `"OPTIONAL"` → absence may degrade some checks, but MUST NOT prevent S5 from running.
  * S5 MUST respect `read_scope`:

    * `ROW_LEVEL` → may read rows to validate invariants.
    * `METADATA_ONLY` → may only inspect metadata (schema, digests, etc.).

---

### 3.3 5A modelling outputs (S1–S4)

These are the artefacts whose invariants S5 checks. S5’s job is to validate them, not to regenerate or modify them.

For each discovered `(parameter_hash, scenario_id)` in this fingerprint (deduced from S3/S4 entries in `sealed_inputs_5A` and the dictionary), S5 MAY read:

#### 3.3.1 S1 — `merchant_zone_profile_5A`

**Logical input**

* Per-merchant×zone demand profiles, used to validate:

  * domain of merchants/zones in 5A,
  * completeness of `demand_class`,
  * base scale correctness.

**Fields S5 uses (at minimum)**

* Keys: `merchant_id`, zone representation (`legal_country_iso` + `tzid` or `zone_id`), optional `channel`.
* Identity: `manifest_fingerprint`, `parameter_hash`.
* Classification: `demand_class` (and any subclass/profile IDs).
* Base scale: fields designated by policy (e.g. `weekly_volume_expected`, `scale_factor`, flags).

**Authority boundary**

* S1 is the **only authority** for:

  * which merchant×zone pairs are in 5A’s modelling domain,
  * which demand class & base scale each pair has under this parameter pack.

S5 MUST NOT:

* reclassify merchants/zones,
* recompute base scales from raw data; it only validates that S1’s assignments satisfy S1’s contracts.

#### 3.3.2 S2 — `shape_grid_definition_5A`, `class_zone_shape_5A`

**Logical inputs**

* `shape_grid_definition_5A` defines the **local-week grid** (bucket indices and local times).
* `class_zone_shape_5A` defines **unit-mass shapes** per `(demand_class, zone[,channel], bucket_index)`.

S5 uses them to validate:

* contiguity and consistency of the grid,
* non-negativity and normalisation of shapes,
* domain alignment with S1 (all classes/zones used by S1 have shapes).

**Authority boundary**

* S2 is the **sole authority** for:

  * time-grid structure of a local week,
  * unit-mass weekly shapes.

S5 MUST NOT:

* adjust shapes or re-grid time; it only checks they obey the S2 contracts.

#### 3.3.3 S3 — `merchant_zone_baseline_local_5A` (and optional S3 outputs)

**Logical input**

* Baseline per `(merchant, zone[,channel], weekly_bucket)`:

  * `lambda_local_base(m,z[,ch],k)`.

S5 uses it to check:

* domain alignment with S1 and S2 grid (each S1 domain row has T_week baselines),
* non-negativity and finiteness of λ,
* weekly sum vs base scale (if that is the defined contract).

Optional S3 outputs (class aggregates, UTC baselines) MAY also be read and validated if present and declared in `sealed_inputs_5A`.

**Authority boundary**

* S3 is the **only source of baseline λ**; S5 must not recompute baseline intensities from S1/S2.

#### 3.3.4 S4 — `merchant_zone_scenario_local_5A` (and optional S4 outputs)

**Logical input**

* Scenario-adjusted local intensities per `(merchant, zone[,channel], horizon_bucket)`:

  * `lambda_local_scenario(m,z[,ch],h)`.

S5 uses it to validate:

* horizon/grid consistency,
* domain + horizon coverage relative to S3,
* non-negativity and finiteness,
* correct relationship to baseline and overlays (if overlay factors are materialised).

Optional S4 outputs:

* `merchant_zone_overlay_factors_5A` — used to check `lambda_local_scenario ≈ lambda_base_local × overlay_factor_total`.
* `merchant_zone_scenario_utc_5A` — optional UTC projection S5 can check for consistency with local intensities + 2A mapping.

**Authority boundary**

* S4 is the **only source** of scenario-aware intensities; S5 must not apply its own overlays or adjust λ, only validate.

---

### 3.4 5A policies & configs

These artefacts define the **contracts** that S5 enforces. They are not optional: if missing, S5 either fails checks or marks the world as misconfigured.

S5 MAY read, as sealed in `sealed_inputs_5A`:

#### 3.4.1 S1 policy artefacts

* e.g. `merchant_class_policy_5A`, `demand_scale_policy_5A`.

Used to validate:

* that all observed `demand_class` values are permitted,
* that base scale semantics (e.g. “weekly expected count”) match what S3’s weekly sums show.

#### 3.4.2 S2 shape/time-grid policies

* e.g. `shape_time_grid_policy_5A`, `shape_library_policy_5A`.

Used to validate:

* T_week and bucket duration vs `shape_grid_definition_5A`,
* shape normalisation and domain coverage.

#### 3.4.3 S3 baseline policies

* e.g. `baseline_intensity_policy_5A`.

Used to validate:

* relationship between weekly sums of λ_base and S1 base scales,
* numeric bounds for λ_base.

#### 3.4.4 S4 overlay & horizon policies

* e.g. `scenario_overlay_policy_5A`, `scenario_horizon_config_5A`.

Used to validate:

* that horizon grids line up with S2 grid and scenario configs,
* that overlay factors lie within policy-declared ranges,
* that overlapping events are combined according to documented rules.

**Authority boundary**

* These policies are the **sole authority** for the formal contracts S5 checks.
* S5 MUST NOT “change the rules” during validation; it only enforces what policies and specs declare.

---

### 3.5 Upstream validation artefacts (Layer-1) *(optional but allowed)*

S5’s primary upstream view is via S0’s `verified_upstream_segments`, but it MAY also read:

* 1A–3B validation bundles & `_passed.flag_*` artefacts, as declared in `sealed_inputs_5A`, to:

  * confirm that S0’s upstream status matches actual flags/bundles,
  * include upstream evidence or summary in the 5A validation bundle.

**Authority boundary**

* Each Layer-1 segment’s own spec remains the authority for:

  * how its validation bundle and flag are formed,
  * what “PASS” means at that layer.

S5 MUST NOT:

* change Layer-1 hashing laws,
* try to “fix” upstream bundles,
* reinterpret Layer-1 contracts.

If S5 discovers discrepancies between S0’s `verified_upstream_segments` and actual Layer-1 flags/bundles, it MUST record this as a validation failure for the world.

---

### 3.6 Validation-level configuration

S5 may also use dedicated validation configs sealed in `sealed_inputs_5A`, for example:

* `validation_policy_5A` — defining:

  * numeric tolerances for:

    * S2 shape normalisation errors,
    * S3 weekly sum vs base scale errors,
    * S4 overlay factor bounds and λ_scenario ranges.
  * which checks are **blocking** vs **warning**.

* `spec_compatibility_config_5A` — defining which `s1_spec_version`, `s2_spec_version`, `s3_spec_version`, `s4_spec_version` combinations are supported.

**Authority boundary**

* These configs adjust *how strict* S5 is, not *what contracts exist*.
* If a validation policy is missing, S5 MUST fall back to safe defaults (strictness) or treat certain checks as failures, not silently skip them.

---

### 3.7 Authority boundaries & out-of-bounds inputs

The following boundaries are **binding**:

1. **`sealed_inputs_5A` is the only input universe**

   * S5 MUST NOT read artefacts that are not represented in `sealed_inputs_5A` for this `manifest_fingerprint`.
   * It MUST not read arbitrary files from storage or external systems.

2. **Read-only behaviour**

   * S5 MUST NOT modify, delete, or republish any S0–S4 artefacts.
   * It creates only its own validation artefacts (bundle/index/flag) in its own namespaces.

3. **No hidden config channels**

   * S5 MUST NOT alter behaviour based on environment variables, CLI flags, or wall-clock that are not encoded in:

     * `parameter_hash`, `manifest_fingerprint`, `scenario_id`, and
     * sealed configs in `sealed_inputs_5A`.

4. **No reinterpretation of semantics**

   * S5 MUST treat S1–S4 specs and policies as **source-of-truth** about semantics:

     * If S2 says shapes must sum to 1, S5 checks that contract; it does not change it.
     * If S3 defines weekly sum vs base scale, S5 enforces that; it doesn’t define a new relationship.

5. **Incomplete inputs → validation FAIL, not “can’t run”**

   * If certain S1–S4 outputs or policies are missing or invalid for a discovered `(parameter_hash, scenario_id)`, S5 MUST:

     * record these as validation failures in its reports, and
     * ensure `_passed.flag_5A` does not signal PASS.

   * It MUST NOT treat missing S1–S4 outputs as an excuse not to produce a bundle; its job is to signal *exactly that* the world is not acceptable.

Within these boundaries, 5A.S5’s inputs are fully controlled and well-scoped: it sees a sealed set of 5A surfaces and contracts, and its responsibility is to **measure reality against those contracts** and report, not to improvise or mutate the system.

---

## 4. Outputs (datasets) & identity *(Binding)*

This section defines the **data products** of **5A.S5 — Segment Validation & HashGate** and how they are identified and addressed in storage. All rules here are **binding**.

S5 produces **no new modelling surfaces**. Its outputs are purely **validation artefacts** for Segment 5A:

1. A fingerprint-scoped **validation bundle** containing evidence, reports and an index.
2. A fingerprint-scoped **pass flag** that cryptographically binds the bundle content.

---

### 4.1 Overview of outputs

5A.S5 MUST produce exactly two logical artefacts per **world** (`manifest_fingerprint`):

1. **`validation_bundle_5A` *(required)*
   – evidence & reports directory**

2. **`_passed.flag_5A` *(required)*
   – small flag file containing a digest over the bundle**

Both are **fingerprint-only**:

* They are scoped to `manifest_fingerprint` (world),
* They are **not** parameter-pack or scenario partitioned,
* They describe and seal **all** 5A outputs for that fingerprint.

---

### 4.2 `validation_bundle_5A` (required)

#### 4.2.1 Semantic role

`validation_bundle_5A` is a **directory-like artefact** that contains all evidence S5 uses to justify its PASS/FAIL verdict for the fingerprint. It typically includes:

* An **index** file (e.g. `validation_bundle_index_5A.json`), listing bundle members and their digests.
* One or more **reports**:

  * a main `validation_report_5A` (summary, metrics, per-check status),
  * optional per-state receipts (S1–S4 summaries).
* Optional **issue tables**:

  * `validation_issue_table_5A` with structured issues (check code, severity, affected artefact/key).

S5 may include additional small evidence files (e.g. per-parameter-pack summaries) so long as they are referenced from the index.

#### 4.2.2 Identity & layout

**Partitioning**

* The bundle is **fingerprint-scoped only**:

  ```text
  partition_keys: ["fingerprint"]
  path: data/layer2/5A/validation/fingerprint={manifest_fingerprint}/...
  ```

This bundle root may contain multiple files and subdirectories, but must respect the dictionary/registry path template.

**Index**

* There MUST be a single index file under the bundle root, e.g.:

  ```text
  data/layer2/5A/validation/
    fingerprint={manifest_fingerprint}/
      validation_bundle_index_5A.json
      reports/...
      issues/...
      ...
  ```

* The index MUST conform to a schema anchor (e.g. `schemas.layer2.yaml#/validation/validation_bundle_index_5A`) and include, at minimum:

  * `manifest_fingerprint`
  * `bundle_version` or `s5_spec_version`
  * `entries`: an array of objects with:

    * `path` — relative path (from bundle root) to a file in the bundle,
    * `sha256_hex` — digest of that file’s bytes.

* Paths MUST be unique and MUST NOT include `..` or absolute segments; ordering SHOULD be ASCII-lex by `path`.

**Other files**

* Each evidence/report/issue file in the bundle:

  * MUST be listed in the index with its digest,
  * MUST have a schema anchor if it is structured (e.g. `validation_report_5A`, `validation_issue_table_5A`).

Files not listed in the index MUST be ignored for validation purposes.

---

### 4.3 `_passed.flag_5A` (required)

#### 4.3.1 Semantic role

`_passed.flag_5A` is a **tiny fingerprint-scoped artefact** that encodes a single digest:

* It binds the **current contents of `validation_bundle_5A`** under that fingerprint to a single hash value.
* Downstream consumers can:

  * read `_passed.flag_5A`,
  * recompute the digest from the bundle using the same law, and
  * confirm that the bundle is complete and unmodified.

A verified `_passed.flag_5A` is the **only acceptable indicator** that 5A is “green” for that world.

#### 4.3.2 Identity & location

* `_passed.flag_5A` MUST live in the **same fingerprint partition** as the bundle, e.g.:

  ```text
  data/layer2/5A/validation/
    fingerprint={manifest_fingerprint}/
      validation_bundle_index_5A.json
      reports/...
      _passed.flag_5A
  ```

* `_passed.flag_5A` MUST be fingerprint-only:

  ```text
  partition_keys: ["fingerprint"]
  ```

* Its contents MUST conform to a small schema anchor (e.g. `schemas.layer2.yaml#/validation/passed_flag_5A`), which at minimum includes:

  * `manifest_fingerprint` — string; MUST equal partition token.
  * `bundle_digest_sha256` — 64-char lowercase hex string representing the digest of the bundle.

#### 4.3.3 Digest law

The hashing law used to compute `bundle_digest_sha256` MUST be:

* **Deterministic and simple**, e.g.:

  1. Load `validation_bundle_index_5A.json`.
  2. For each entry in `entries`, in **ASCII-lex order by `path`**:

     * read the file at that relative path,
     * append its raw bytes to an in-memory buffer or incremental hash state.
  3. Compute SHA-256 over that concatenation; encode as 64-char lowercase hex.

* `_passed.flag_5A.bundle_digest_sha256` MUST equal this computed digest.

Any change in bundle contents (add/remove file, modify bytes, reorder entries) MUST change the digest and invalidate the flag.

---

### 4.4 Relationship between outputs & upstream artefacts

#### 4.4.1 Binding to S0 and 5A outputs

For a given `manifest_fingerprint`:

* `validation_bundle_5A` and `_passed.flag_5A`:

  * MUST explicitly reference:

    * `s0_gate_receipt_5A`, `sealed_inputs_5A`,
    * all discovered `(parameter_hash, scenario_id)` combinations and their S1–S4 outputs,
    * relevant S1–S4 policies/configs.

* The `validation_report_5A` SHOULD summarise:

  * status of S0 & upstream 1A–3B,
  * status of each `(parameter_hash, scenario_id)` for S1–S4,
  * any issues found and their severity.

The presence of `_passed.flag_5A` implies that:

* S5 has seen the world defined by S0 & sealed inputs,
* S5 has executed its validation algorithm over all discovered 5A outputs,
* and the corresponding evidence & report files are present and digested in `validation_bundle_5A`.

#### 4.4.2 Downstream gating

Downstream consumers (5B, 6A, external pipelines) MUST:

* treat `_passed.flag_5A` as the **gate** for 5A:

  * if the flag is missing, malformed, or its digest does not match the bundle, they MUST NOT treat 5A outputs as authoritative.

* use `validation_bundle_5A` (and especially `validation_report_5A`) as:

  * the source of detailed information about which checks were performed,
  * which are PASS/FAIL/WARN,
  * and which artefacts `(parameter_hash, scenario_id)` are degraded.

S5 outputs themselves (bundle + flag) MUST NOT be modified by any other segment; any change in 5A world state requires regenerating the bundle and flag.

---

### 4.5 Control-plane vs modelling outputs

To emphasise:

* S5 does **not** produce additional modelling datasets.
* Its outputs are strictly **validation/control-plane artefacts**:

  * `validation_bundle_5A` (directory with reports, indices, issue tables, etc.),
  * `_passed.flag_5A`.

They are:

* **fingerprint-scoped**,
* **immutable** once published, except in the idempotent case where recomputation yields identical bytes, and
* the **only** objects that signal “5A is safe to use for this world”.

Within this identity model, S5 provides a clean, verifiable boundary between “5A was produced” and “5A has been checked and sealed”.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes **where** the 5A.S5 validation artefacts live in your schema hierarchy, **what their shapes are**, and **how the dataset dictionary and artefact registry must refer to them**. All rules here are **binding**.

S5 defines **validation/control-plane** artefacts, not modelling tables:

* `validation_bundle_5A` — a fingerprint-scoped directory with:

  * an **index** (`validation_bundle_index_5A`),
  * one or more **reports** and optional **issue tables**.

* `_passed.flag_5A` — a fingerprint-scoped flag file that binds the bundle via a digest.

---

### 5.1 Schema files & sections

S5’s validation artefacts MUST be defined in the **Layer-2** schema bundle, with 5A-specific anchors:

* **File:** `schemas.layer2.yaml`

This file MUST contain a top-level `validation` section with at least:

* `schemas.layer2.yaml#/validation/validation_bundle_index_5A`
* `schemas.layer2.yaml#/validation/validation_report_5A`
* `schemas.layer2.yaml#/validation/validation_issue_table_5A` *(optional but recommended)*
* `schemas.layer2.yaml#/validation/passed_flag_5A`

You MAY also define lightweight 5A-specific receipts:

* `schemas.layer2.yaml#/validation/validation_receipt_5A` *(optional)*

Each anchor MUST fully describe the JSON/row shape for that artefact, including required fields and types.

---

### 5.2 `validation_bundle_index_5A` — schema anchor & shape

**Anchor**

* `schemas.layer2.yaml#/validation/validation_bundle_index_5A`

**Type**

* A **single JSON document** (one object per fingerprint) that describes the contents of `validation_bundle_5A`.

**Required fields (minimum)**

* `manifest_fingerprint` — string; non-null.

* `segment_id` — string; MUST equal `"5A"`.

* `s5_spec_version` — string; non-null; semantic version of the S5 spec.

* `generated_utc` — RFC3339 timestamp; non-null; time the bundle was constructed.

* `entries` — array of objects; non-empty if bundle has any evidence.
  Each entry MUST have:

  * `path` — string; relative path from the bundle root to a file included in the bundle; MUST NOT contain `..` or absolute elements.
  * `sha256_hex` — string; 64-character lowercase hex digest of that file’s bytes.

Optional but recommended:

* `overall_status` — string enum, e.g. `"PASS"` or `"FAIL"` for the world.
* `summary` — object with a few high-level metrics (e.g. `n_parameter_hashes`, `n_scenarios`, `max_shape_error`, etc.).

There is no PK here; this is a **single-object document** in the fingerprint partition.

---

### 5.3 `validation_report_5A` — schema anchor & shape

**Anchor**

* `schemas.layer2.yaml#/validation/validation_report_5A`

**Type**

* A JSON/row-level schema representing a **summary report** for 5A validation.

**Required fields (suggested minimum)**

* `manifest_fingerprint` — string; non-null.
* `s5_spec_version` — string; non-null.
* `parameter_hashes` — array of strings; list of parameter packs validated for this fingerprint.
* `scenarios` — array of scenario descriptors (e.g. `{ "parameter_hash": "...", "scenario_id": "...", "status": "PASS"|"FAIL"|"WARN" }`).
* `checks` — array of check summaries, each with:

  * `check_id` — string (e.g. `"S2_SHAPE_NORMALISATION"`, `"S3_WEEKLY_SUM_VS_SCALE"`).
  * `status` — string enum `"PASS"|"FAIL"|"WARN"`.
  * `metrics` — object with check-specific numeric metrics.

Optional:

* `issues_path` — relative path to the issue table file (if any).
* `notes` — free-text.

You MAY choose to treat this as a one-row Parquet/JSON file or an object stored as JSON; either way, it MUST be schema-valid.

---

### 5.4 `validation_issue_table_5A` — schema anchor & row shape *(optional)*

**Anchor**

* `schemas.layer2.yaml#/validation/validation_issue_table_5A`

**Type**

* A **row-level table** of validation issues, zero or more rows.

**Recommended columns**

* `manifest_fingerprint` — string; non-null.
* `parameter_hash` — string; non-null.
* `scenario_id` — string; nullable (issue may be parameter-pack-wide, not scenario-specific).
* `segment` — string, e.g. `"5A.S1"`, `"5A.S2"`, `"5A.S3"`, `"5A.S4"`, `"5A.S0"`.
* `check_id` — string; corresponds to a check in the report.
* `issue_code` — string; canonical code (e.g. `S2_SHAPE_SUM_EXCEEDS_TOLERANCE`).
* `severity` — enum (`"ERROR"|"WARN"|"INFO"`).
* `context` — object with key identifiers (e.g. merchant_id, class, zone, bucket_index).
* `message` — short human-readable description.

PK is not strictly required; this is fundamentally an **issues log**. If you wish, you can define a PK such as `(manifest_fingerprint, issue_code, context_hash)`.

---

### 5.5 `_passed.flag_5A` — schema anchor & shape

**Anchor**

* `schemas.layer2.yaml#/validation/passed_flag_5A`

**Type**

* A **tiny JSON (or single-line text) object** encoding the bundle digest.

**Required fields (if JSON)**

* `manifest_fingerprint` — string; non-null; MUST equal partition token.
* `bundle_digest_sha256` — string; 64-character lowercase hex.

You MAY instead store this as a very simple text file:

```text
sha256_hex = <64-char lowercase hex>
```

but if you do, you should still define a small schema for text structure, or document the format clearly in this spec.

---

### 5.6 Dataset dictionary entries (5A)

In `dataset_dictionary.layer2.5A.yaml`, S5 MUST define entries for:

#### 5.6.1 `validation_bundle_index_5A`

```yaml
- id: validation_bundle_index_5A
  owner_subsegment: "5A"
  schema_ref: schemas.layer2.yaml#/validation/validation_bundle_index_5A
  path: data/layer2/5A/validation/
        fingerprint={manifest_fingerprint}/validation_bundle_index_5A.json
  partitioning:
    - fingerprint
  # Single-object JSON; no row-level PK
  status: "required"
  produced_by: ["5A.S5"]
  consumed_by:
    - "5A.S5"        # for revalidation / idempotency
    - "5B"
    - "6A"
    - "5A.validation_tools"
  # 'ordering' not meaningful; single JSON object
```

#### 5.6.2 `validation_report_5A`

```yaml
- id: validation_report_5A
  owner_subsegment: "5A"
  schema_ref: schemas.layer2.yaml#/validation/validation_report_5A
  path: data/layer2/5A/validation/
        fingerprint={manifest_fingerprint}/reports/validation_report_5A.json
  partitioning:
    - fingerprint
  status: "required"
  produced_by: ["5A.S5"]
  consumed_by:
    - "5A.validation_tools"
    - "5B"
    - "6A"
```

#### 5.6.3 `validation_issue_table_5A` *(optional)*

```yaml
- id: validation_issue_table_5A
  owner_subsegment: "5A"
  schema_ref: schemas.layer2.yaml#/validation/validation_issue_table_5A
  path: data/layer2/5A/validation/
        fingerprint={manifest_fingerprint}/issues/validation_issue_table_5A.parquet
  partitioning:
    - fingerprint
  status: "optional"
  produced_by: ["5A.S5"]
  consumed_by:
    - "5A.validation_tools"
    - "ops_dashboards"
```

#### 5.6.4 `_passed.flag_5A`

```yaml
- id: passed_flag_5A
  owner_subsegment: "5A"
  schema_ref: schemas.layer2.yaml#/validation/passed_flag_5A
  path: data/layer2/5A/validation/
        fingerprint={manifest_fingerprint}/_passed.flag_5A
  partitioning:
    - fingerprint
  status: "required"
  produced_by: ["5A.S5"]
  consumed_by:
    - "5B"
    - "6A"
    - "5A.validation_tools"
```

You may choose to add other auxiliary report/metric files to the dictionary as needed; all MUST be referenced from the index and/or main report.

---

### 5.7 Artefact registry entries (5A)

In `artefact_registry_5A.yaml`, S5 MUST register these as high-level artefacts:

#### 5.7.1 `validation_bundle_5A`

Since the bundle is directory-like, you can treat the **index** as the canonical dataset:

```yaml
- artifact_id: "validation_bundle_5A"
  name: "Layer-2 / 5A validation bundle"
  type: "dataset"
  category: "validation"
  owner_subsegment: "5A"
  manifest_key: "mlr.5A.validation.bundle"
  schema: "schemas.layer2.yaml#/validation/validation_bundle_index_5A"
  path_template: "data/layer2/5A/validation/fingerprint={manifest_fingerprint}/validation_bundle_index_5A.json"
  partition_keys: ["fingerprint"]
  produced_by: ["5A.S5"]
  consumed_by: ["5B","6A","5A.validation_tools"]
  dependencies:
    - s0_gate_receipt_5A
    - sealed_inputs_5A
    - merchant_zone_profile_5A
    - shape_grid_definition_5A
    - class_zone_shape_5A
    - merchant_zone_baseline_local_5A
    - merchant_zone_scenario_local_5A
    # ... plus any policy/config artefacts used in validation
  cross_layer: true
```

#### 5.7.2 `_passed.flag_5A`

```yaml
- artifact_id: "passed_flag_5A"
  name: "Layer-2 / 5A validation pass flag"
  type: "dataset"          # small control-plane artefact
  category: "validation"
  owner_subsegment: "5A"
  manifest_key: "mlr.5A.validation.passed_flag"
  schema: "schemas.layer2.yaml#/validation/passed_flag_5A"
  path_template: "data/layer2/5A/validation/fingerprint={manifest_fingerprint}/_passed.flag_5A"
  partition_keys: ["fingerprint"]
  produced_by: ["5A.S5"]
  consumed_by: ["5B","6A","5A.validation_tools"]
  dependencies:
    - validation_bundle_5A
  cross_layer: true
```

You MAY also register `validation_report_5A` and `validation_issue_table_5A` as separate artefacts if you want them discoverable at the manifest level.

---

### 5.8 Foreign-key & compatibility constraints

Finally, S5 validation artefacts MUST be **joinable** and compatible with the rest of the catalogue:

* `validation_bundle_index_5A` and `validation_report_5A` MUST embed the same `manifest_fingerprint` as the `fingerprint` partition.
* `_passed.flag_5A` MUST embed (or encode) the same `manifest_fingerprint` and a `bundle_digest_sha256` that matches a recomputed digest over the files listed in the index.
* If `validation_issue_table_5A` refers to specific 5A artefacts or states, its `context` fields SHOULD be consistent with key structures from S1–S4 (e.g. merchant_id types, zone ids).

Within this structure, S5’s outputs are fully schema-governed, catalogue-visible, and strongly bound to the rest of the 5A world, providing a clean and verifiable validation surface for downstream consumers.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section specifies the **ordered, deterministic algorithm** for **5A.S5 — Segment Validation & HashGate**. Implementations MUST follow these steps and invariants.

5A.S5 is **purely deterministic** and MUST NOT consume RNG or modify any S0–S4 artefacts.

---

### 6.1 High-level invariants

5A.S5 MUST satisfy:

1. **RNG-free**

   * MUST NOT call any RNG primitive.
   * MUST NOT write to `rng_audit_log`, `rng_trace_log`, or any RNG event streams.

2. **Catalogue-driven, sealed-world operation**

   * MUST discover all artefacts via:

     * `s0_gate_receipt_5A`,
     * `sealed_inputs_5A`,
     * dataset dictionaries + artefact registries.
   * MUST NOT discover inputs via hard-coded paths, directory scanning, or network calls.

3. **Read-only over S0–S4**

   * MUST NOT modify, delete, or regenerate any S0–S4 artefacts.
   * MAY recompute quantities *in memory* for validation only.

4. **Deterministic bundle and flag**

   * For a given `manifest_fingerprint` and sealed world state, the contents of `validation_bundle_5A` and `_passed.flag_5A` MUST be uniquely determined.
   * Re-running S5 with unchanged inputs MUST either:

     * reproduce identical bundle + flag, or
     * no-op if S5 detects they already exist and match.

5. **Binary gate per fingerprint**

   * S5’s verdict is binary at the gate level: the world either has a **valid PASS bundle + flag** or it does not.
   * Internal per-parameter-pack / per-scenario failures MUST be captured in the report, not hidden, but they do not change the gate from “one bundle per fingerprint” to “multiple partial bundles”.

---

### 6.2 Step 1 — Load S0 and verify sealed inputs

**Goal:** Confirm that S5 is operating on a sealed, well-defined world.

**Inputs:**

* `manifest_fingerprint` (run context).
* `s0_gate_receipt_5A`, `sealed_inputs_5A` for this fingerprint.

**Procedure:**

1. Resolve `s0_gate_receipt_5A` and `sealed_inputs_5A` via the 5A dataset dictionary + artefact registry using `fingerprint={manifest_fingerprint}`.

2. Validate both datasets against their schemas:

   * `s0_gate_receipt_5A` → `schemas.5A.yaml#/validation/s0_gate_receipt_5A`.
   * `sealed_inputs_5A` → `schemas.5A.yaml#/validation/sealed_inputs_5A`.

3. Check identity consistency:

   * For `s0_gate_receipt_5A`:

     * `manifest_fingerprint` field equals the run’s `manifest_fingerprint`.
     * `parameter_hash_gate = s0_gate_receipt_5A.parameter_hash` is non-empty.

   * For all rows in `sealed_inputs_5A`:

     * `manifest_fingerprint == {manifest_fingerprint}`.
     * `parameter_hash` MUST be either:

       * equal to `parameter_hash_gate`, or
       * treated as an inconsistency that will be recorded as a validation issue.

4. Recompute sealed-inputs digest:

   * Canonically serialise `sealed_inputs_5A` according to the S0 hashing law,
   * Compute `sealed_inputs_digest_recomputed`,
   * Check `sealed_inputs_digest_recomputed == s0_gate_receipt_5A.sealed_inputs_digest`.

5. Record upstream statuses from `s0_gate_receipt_5A.verified_upstream_segments` (1A–3B) for later inclusion in the validation report.

**Invariants:**

* If `s0_gate_receipt_5A` or `sealed_inputs_5A` is missing or schema-invalid, S5 MUST still proceed to produce a **FAILED** validation bundle (with S0 checks marked as FAIL), not skip validation altogether.
* Digest mismatch or parameter_hash inconsistencies MUST be recorded as validation failures (and will prevent a PASS flag), but do not prevent bundle construction.

---

### 6.3 Step 2 — Discover 5A outputs & parameter/scenario combinations

**Goal:** Identify all 5A modelling outputs (S1–S4) and `(parameter_hash, scenario_id)` combinations present in this world.

**Inputs:**

* `sealed_inputs_5A`.
* Dataset dictionary `dataset_dictionary.layer2.5A.yaml`.
* Artefact registry `artefact_registry_5A.yaml`.

**Procedure:**

1. Scan `sealed_inputs_5A` for rows where:

   * `owner_segment="5A"` and `role` is one of:

     * `"model"`, `"model_config"`, `"scenario_config"`, `"policy"`, `"validation"`, etc.

2. From these rows, build:

   * A **set of parameter hashes** referenced (`PARAMS = {row.parameter_hash}`) — SHOULD be a singleton `{parameter_hash_gate}`; if not, record inconsistencies as issues.
   * A **set of `(parameter_hash, scenario_id)`** pairs for which modelling outputs (S3/S4) exist. For example:

     * Look at entries for `merchant_zone_baseline_local_5A` and `merchant_zone_scenario_local_5A` and derive their `(parameter_hash, scenario_id)`.

3. For each `(parameter_hash, scenario_id)` in this set, record which S1–S4 artefacts are **expected** (based on dictionary & registry):

   * S1: `merchant_zone_profile_5A` (expected global; not scenario-scoped).
   * S2: `shape_grid_definition_5A`, `class_zone_shape_5A` (per `(parameter_hash, scenario_id)`).
   * S3: `merchant_zone_baseline_local_5A` (per `(parameter_hash, manifest_fingerprint, scenario_id)`).
   * S4: `merchant_zone_scenario_local_5A` (and optional overlay/UTC datasets).

4. Build a data structure (e.g. a map):

   ```text
   RUNS = {
     (parameter_hash, scenario_id) -> {
       expected_s1_present: bool,
       expected_s2_present: bool,
       expected_s3_present: bool,
       expected_s4_present: bool,
       sealed_artifacts: [rows from sealed_inputs_5A for this combo]
     }
   }
   ```

**Invariants:**

* S5 MUST be able to discover **all** 5A outputs that exist for this fingerprint via `sealed_inputs_5A` + dictionary/registry.
* S5 MUST NOT infer extra `(parameter_hash, scenario_id)` beyond what sealed inputs indicate.

---

### 6.4 Step 3 — Per-state validation over S1–S4

**Goal:** For each discovered `(parameter_hash, scenario_id)` run, re-check S1–S4 invariants and collect PASS/FAIL/WARN status and metrics.

**Inputs:**

* `RUNS` from Step 2.
* S1–S4 datasets resolved via dictionary/registry for this fingerprint.
* 5A policies/configs referenced in S1–S4 specs.

**Procedure (conceptual outline):**

For each `(parameter_hash, scenario_id)` in `RUNS`:

1. **Initial state record**

   * Initialise a per-run validation record `R` with:

     * `parameter_hash`, `scenario_id`,
     * default `status = "FAIL"` (to be updated once checks complete),
     * an empty list of `check_results`.

2. **S1 checks — `merchant_zone_profile_5A`**

   * If expected S1 artefact is missing or schema-invalid:

     * record check `S1_PRESENT` with `status="FAIL"`.
   * Else:

     * verify PK (`merchant_id, zone_representation[,channel]`), non-null required fields,
     * verify `demand_class` non-null for all domain rows,
     * verify base scales (per policy) are finite and ≥ 0.
     * record metrics (e.g. counts, min/median/max base scale, class distribution) and check statuses (`PASS` / `WARN` / `FAIL`).

3. **S2 checks — `shape_grid_definition_5A`, `class_zone_shape_5A`**

   * If expected S2 artefacts missing or schema-invalid:

     * record `S2_PRESENT` with `status="FAIL"`.
   * Else:

     * verify grid PK and contiguity (`bucket_index` range, no gaps/duplicates).
     * verify shapes:

       * `shape_value ≥ 0`;
       * Σ shape per `(demand_class, zone[,channel])` ≈ 1 within tolerance.
     * verify S2 domain covers all `(demand_class, zone[,channel])` referenced by S1 for this parameter pack.
     * record metrics (max normalisation error, domain counts, etc.) and statuses.

4. **S3 checks — `merchant_zone_baseline_local_5A`**

   * If expected S3 artefact missing or schema-invalid:

     * record `S3_PRESENT` with `status="FAIL"`.
   * Else:

     * verify PK and domain parity with S1 and S2 (for each `(merchant, zone[,channel])` domain row, there are exactly `T_week` baseline buckets).
     * verify `lambda_local_base ≥ 0`, finite.
     * where policy requires, compute weekly sums per `(merchant, zone[,channel])` and compare to S1’s base scale; record max relative error; mark `PASS`/`WARN`/`FAIL` accordingly.

5. **S4 checks — `merchant_zone_scenario_local_5A` (and optional S4 artefacts)**

   * If expected S4 artefact(s) missing or schema-invalid:

     * record `S4_PRESENT` with `status="FAIL"`.
   * Else:

     * verify PK and domain parity with S3 (same `(merchant, zone[,channel])` domain).
     * verify horizon coverage (each domain element has all horizon buckets; no duplicates).
     * verify `lambda_local_scenario ≥ 0`, finite.
     * if overlay factors table exists:

       * verify 1:1 mapping with scenario local;
       * verify `overlay_factor_total ≥ 0`, finite and within policy bounds;
       * recompute small sample of `lambda_local_scenario` and confirm `≈ lambda_base_local × overlay_factor_total` within tolerance.
     * if UTC scenario output exists:

       * optionally verify total intensity preservation local vs UTC up to tolerance.

6. **Per-run status aggregation**

   * Based on all S1–S4 check statuses for this `(parameter_hash, scenario_id)`, assign:

     ```text
     R.status = "PASS"   if all blocking checks PASS
                "FAIL"   if any blocking check FAIL
                "WARN"   if no blocking FAIL but some checks WARN
     ```

   * Append `R` to a list of per-run validation records.

**Invariants:**

* S5 MUST NOT “fix” any S1–S4 artefacts; it only measures and records.
* Missing artefacts or policy/configs are **failures** for the affected run, not reasons to skip S5 or silently PASS.

---

### 6.5 Step 4 — Build 5A validation report & issue table

**Goal:** Aggregate per-run validation results into concise, structured artefacts.

**Inputs:**

* Per-run validation records `R` from Step 3.
* Per-check metrics and issues collected along the way.

**Procedure:**

1. **Determine overall world status**

   * If S0 checks are valid and all `(parameter_hash, scenario_id)` runs have `status="PASS"` (or `"WARN"` where warnings are non-blocking), set:

     ```text
     overall_status_5A = "PASS"
     ```

   * Otherwise, set:

     ```text
     overall_status_5A = "FAIL"
     ```

2. **Construct `validation_report_5A`**

   * Create a JSON object conforming to `#/validation/validation_report_5A` with fields such as:

     * `manifest_fingerprint`
     * `s5_spec_version`
     * `overall_status = overall_status_5A`
     * `parameter_hashes`
     * `scenarios`: list of `{ parameter_hash, scenario_id, status }` from `R`.
     * `checks`: list of per-check summaries, each including:

       * `check_id` (e.g. `"S2_SHAPES_SUM_TO_ONE"`),
       * `status`,
       * `metrics` (e.g. `max_error`, `n_violations`).

3. **Construct `validation_issue_table_5A` (optional but recommended)**

   * Flatten collected issues into rows conforming to `#/validation/validation_issue_table_5A`, each row capturing:

     * `manifest_fingerprint`, `parameter_hash`, `scenario_id`,
     * `segment` (S0, S1, S2, S3, S4),
     * `check_id`, `issue_code`, `severity`,
     * `context` (e.g. `merchant_id`, `zone`, `bucket_index`, etc.),
     * `message`.

4. Add these artefacts to an in-memory list of bundle members `BUNDLE_FILES` with their relative paths and content.

**Invariants:**

* `validation_report_5A` MUST represent the full set of runs and checks S5 performed.
* If `validation_issue_table_5A` exists, it MUST be consistent with the report (e.g. every `issue_code` refers to a known `check_id`).

---

### 6.6 Step 5 — Build `validation_bundle_index_5A`

**Goal:** Create a canonical index over all bundle files with their digests.

**Inputs:**

* The list of bundle files `BUNDLE_FILES` from Step 4 (and any additional evidence files S5 writes).

**Procedure:**

1. For each bundle file:

   * Determine its relative path `path` under the bundle root (e.g. `reports/validation_report_5A.json`, `issues/validation_issue_table_5A.parquet`).
   * Compute its SHA-256 digest over raw bytes → `sha256_hex` (64 lowercase hex characters).

2. Construct an `entries` array:

   ```json
   [
     { "path": "reports/validation_report_5A.json", "sha256_hex": "..." },
     { "path": "issues/validation_issue_table_5A.parquet", "sha256_hex": "..." },
     ...
   ]
   ```

3. Sort `entries` lexicographically by `"path"` (ASCII-lex order).

4. Construct the index object:

   ```json
   {
     "manifest_fingerprint": "<fingerprint>",
     "segment_id": "5A",
     "s5_spec_version": "<MAJOR.MINOR.PATCH>",
     "generated_utc": "<RFC3339 timestamp>",
     "overall_status": "PASS" | "FAIL",
     "entries": [ ... ]
   }
   ```

5. Validate this object against `#/validation/validation_bundle_index_5A`.

**Invariants:**

* Every file in `BUNDLE_FILES` MUST have a corresponding `entries` entry; nothing in `entries` may point to a non-existent file.
* No two entries may share the same `path`.
* The ordering by `path` MUST be stable and deterministic.

---

### 6.7 Step 6 — Compute bundle digest & construct `_passed.flag_5A`

**Goal:** Compute a single digest for the bundle and create the pass flag artefact.

**Inputs:**

* `validation_bundle_index_5A` and the files listed in its `entries`.

**Procedure:**

1. Using the sorted `entries` list, concatenate file bytes in that order:

   * For each `entry` in `entries`:

     * Read the file at the given relative `path`.
     * Append its raw bytes to a running SHA-256 hash state.

2. Compute final hash:

   ```text
   bundle_digest_sha256 = SHA256(concatenated_bytes)
   ```

   Represented as a 64-character lowercase hex string.

3. Construct `_passed.flag_5A` object, e.g.:

   ```json
   {
     "manifest_fingerprint": "<fingerprint>",
     "bundle_digest_sha256": "<64-char hex>"
   }
   ```

   or, if using text format, a single line:

   ```text
   sha256_hex = <64-char hex>
   ```

4. Validate `_passed.flag_5A` against `#/validation/passed_flag_5A` (if JSON), or at least verify it matches the documented format (if text).

**Invariants:**

* Any change to any file listed in `entries` MUST change `bundle_digest_sha256`.
* `_passed.flag_5A` MUST solely reflect this computed digest; no additional fields or hidden information may influence the gate.

---

### 6.8 Step 7 — Atomic write & idempotency

**Goal:** Persist the validation bundle + flag atomically and idempotently for the fingerprint.

**Inputs:**

* `validation_bundle_index_5A`, `_passed.flag_5A`, and other bundle files (reports, issue tables, etc.).
* Canonical paths from the dataset dictionary.

**Procedure:**

1. **Resolve bundle root and flag paths**

   * From dictionary/registry:

     ```text
     bundle_root = data/layer2/5A/validation/fingerprint={manifest_fingerprint}/
     index_path = bundle_root + "validation_bundle_index_5A.json"
     flag_path  = bundle_root + "_passed.flag_5A"
     ```

2. **Check for existing bundle & flag**

   * If `index_path` and `flag_path` both exist:

     * Load existing index and recompute digest over listed entries.
     * Compare existing `bundle_digest` with newly computed `bundle_digest`.

       * If identical:

         * S5 MAY treat this as an idempotent re-run and return SUCCESS without overwriting (optional).
       * If different:

         * S5 MUST fail with `S5_OUTPUT_CONFLICT` and MUST NOT overwrite existing bundle or flag.

   * If only one of them exists (index or flag), S5 MUST treat this as a prior inconsistent run and record it as an issue; it MAY choose to treat this as a conflict and require manual cleanup, or may elect to overwrite with a fresh bundle+flag depending on governance rules (must be clearly defined in S5 spec implementation).

3. **Write bundle to staging**

   * Write all bundle files (index, report, issues, etc.) to a staging location, e.g.:

     ```text
     data/layer2/5A/validation/fingerprint={manifest_fingerprint}/.staging/...
     ```

4. **Validate staging contents**

   * Optionally re-validate index and flag against staged files:

     * recompute digests for staged files,
     * ensure they match index entries,
     * ensure the flag digest equals the bundle digest.

5. **Atomic commit**

   * Atomically move all staged files into canonical locations under `bundle_root`, ensuring:

     * the index and all referenced files are present before or at the same time as `_passed.flag_5A` becomes visible,
     * no intermediate state exists where `_passed.flag_5A` points at an incomplete bundle.

   * Remove any stale `.staging/` directories after a successful commit, if applicable.

**Invariants:**

* On success:

  * the bundle root contains exactly the index + evidence files listed in `entries`, and `_passed.flag_5A` whose digest matches the bundle.
* On failure:

  * no partial or inconsistent state must be present in canonical paths; any incomplete bundle files must remain under `.staging/` or be cleaned up.

---

Within this algorithm, 5A.S5 acts as a **pure, deterministic, read-only validator**: it inspects S0–S4 + policies for a world, computes a structured validation bundle, and seals it with a digest-bearing flag. It never alters upstream artefacts and provides a crisp, verifiable gate for all downstream consumers.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how **identity** is represented for **5A.S5 — Segment Validation & HashGate**, how its artefacts are **partitioned and addressed**, and what the **rewrite rules** are. All rules here are **binding**.

S5 outputs are **world-scoped**:

* keyed only by `manifest_fingerprint`,
* independent of individual `parameter_hash` or `scenario_id` (they summarise *all* 5A outputs for that world).

---

### 7.1 Identity model

There are two identity layers:

1. **Run identity** (execution context, ephemeral)

   * `manifest_fingerprint` — world being validated.
   * `run_id` — execution ID for this S5 run.

   These appear in logs/run-report, not as partitioning keys.

2. **Validation artefact identity** (storage-level, persistent)

   * For a given `manifest_fingerprint`, there MUST be at most **one canonical** pair of:

     * `validation_bundle_5A` (represented by `validation_bundle_index_5A`), and
     * `_passed.flag_5A`.

Binding rules:

* All S5 artefacts MUST embed:

  * `manifest_fingerprint` — as a field in index/report/issue table (and optionally in flag), and
  * this value MUST equal the partition token `fingerprint={manifest_fingerprint}`.

* S5 MUST treat each `manifest_fingerprint` as defining a **closed world** whose validation state is captured entirely by that bundle + flag.

---

### 7.2 Partition law & path contracts

#### 7.2.1 Partition keys

All S5 artefacts are **fingerprint-partitioned only**:

* `validation_bundle_index_5A`
* `validation_report_5A`
* `validation_issue_table_5A` (if present)
* `_passed.flag_5A`

Each MUST have:

```yaml
partition_keys: ["fingerprint"]
```

No S5 artefact MAY be partitioned by `parameter_hash`, `scenario_id`, `seed`, or `run_id`.

#### 7.2.2 Path templates

Canonical paths MUST follow the patterns declared in the dataset dictionary. For example:

* Bundle root (directory-like; not explicitly a dataset but implied):

  ```text
  data/layer2/5A/validation/
    fingerprint={manifest_fingerprint}/
      validation_bundle_index_5A.json
      reports/...
      issues/...
      _passed.flag_5A
  ```

* Index:

  ```text
  data/layer2/5A/validation/
    fingerprint={manifest_fingerprint}/validation_bundle_index_5A.json
  ```

* Report:

  ```text
  data/layer2/5A/validation/
    fingerprint={manifest_fingerprint}/reports/validation_report_5A.json
  ```

* Issue table (if present):

  ```text
  data/layer2/5A/validation/
    fingerprint={manifest_fingerprint}/issues/validation_issue_table_5A.parquet
  ```

* Flag:

  ```text
  data/layer2/5A/validation/
    fingerprint={manifest_fingerprint}/_passed.flag_5A
  ```

These templates are **binding** once defined in `dataset_dictionary.layer2.5A.yaml` / `artefact_registry_5A.yaml`.

#### 7.2.3 Path ↔ embed equality

For all S5 artefacts:

* Embedded `manifest_fingerprint` (where present, e.g. in index/report/issue table) MUST:

  * be non-null, and
  * exactly equal the `fingerprint={manifest_fingerprint}` partition token.

For `_passed.flag_5A`:

* If the flag has a JSON structure, it MUST contain `manifest_fingerprint` with the same equality requirement.
* If the flag is bare text (only `sha256_hex = ...`), its **location** in the `fingerprint={manifest_fingerprint}` partition is the binding identity; it MUST NOT be used outside that context.

Any mismatch between partition token and embedded `manifest_fingerprint` MUST be treated as invalid and MUST be surfaced as a validation inconsistency.

---

### 7.3 Ordering & hashing discipline

S5’s **hashing law** for the bundle is binding:

1. **Index ordering**

   * The `entries` array in `validation_bundle_index_5A` MUST be ordered in **ASCII-lexicographic order of `path`**.
   * Paths MUST be unique and relative to the bundle root.

2. **Digest computation**

   * The bundle digest MUST be computed by:

     * iterating `entries` in index order,
     * reading each file’s raw bytes,
     * feeding bytes into a SHA-256 hash state,
     * encoding the final hash as 64-character lowercase hex.

   * `_passed.flag_5A` MUST encode exactly this computed digest (and nothing else) as `bundle_digest_sha256` (or `sha256_hex` in text).

3. **Index ↔ content equality**

   * Every file included in the bundle MUST be listed in `entries`.
   * No `entries` entry may reference a non-existent file.
   * S5 MUST ensure that `sha256_hex` in `entries` matches the current content of each file at commit time.

Consumers MUST:

* trust `_passed.flag_5A` **only** if they can recompute the digest using this law and match it.

---

### 7.4 Merge discipline & rewrite semantics

S5 follows a **single-writer, no-merge** discipline per `manifest_fingerprint`.

Binding rules:

1. **No multi-bundle worlds**

   * For a given `manifest_fingerprint`, there MUST NOT be multiple distinct `validation_bundle_5A` directories that S5 considers canonical.
   * The combination of bundle + flag under `data/layer2/5A/validation/fingerprint={manifest_fingerprint}/` is the **single authoritative validation artefact**.

2. **No incremental merge**

   * S5 MUST NOT:

     * append new evidence files to an existing bundle without regenerating the index+digest,
     * partially update index or reports while reusing old `_passed.flag_5A`.

   * Any change to bundle content **requires**:

     * a new index,+
     * a new digest,
     * a new `_passed.flag_5A`.

3. **Idempotent re-runs**

   * If S5 is re-run for a `manifest_fingerprint` where:

     * `validation_bundle_index_5A` and `_passed.flag_5A` already exist, and
     * recomputing the bundle from current inputs produces **identical files and index**, including the same digest,

     then:

     * S5 MAY treat this as an idempotent re-run and exit without rewriting any files.

4. **Conflicting rewrites forbidden**

   * If S5 recomputes the bundle and finds that:

     * some evidence file content would differ, or
     * the index entries would differ (paths or listed digests), or
     * the new bundle digest differs from the existing `_passed.flag_5A`,

     then S5 MUST:

     * fail with a canonical conflict error (e.g. `S5_OUTPUT_CONFLICT`), and
     * MUST NOT overwrite existing bundle or flag.

   * Any legitimate change in 5A world state (S1–S4 outputs or policies) MUST lead to:

     * a new `manifest_fingerprint` (new world), and
     * a new S5 run for that new fingerprint,
       rather than mutating the old fingerprint’s validation artefacts.

5. **Partial prior state**

   * If S5 finds an inconsistent prior state (e.g. bundle index exists but flag missing; or flag exists but index missing/invalid), it MUST:

     * record this as an issue for this fingerprint, and
     * follow a governance-defined policy:

       * either treat this as a conflict that requires manual cleanup, or
       * fully overwrite with a fresh bundle+flag (this choice MUST be documented in the implementation; the spec’s default stance is to treat it as a conflict and NOT overwrite).

---

### 7.5 Interaction with other identity dimensions

#### 7.5.1 `parameter_hash` & `scenario_id`

* S5 itself is fingerprint-scoped; its outputs do **not** partition by `parameter_hash` or `scenario_id`.
* However:

  * `validation_report_5A` MUST include lists of all `parameter_hash` and `(parameter_hash, scenario_id)` combinations discovered and validated.
  * `validation_issue_table_5A` rows SHOULD include `parameter_hash` and `scenario_id` where applicable, so issues can be attributed to specific packs/scenarios.

No S5 artefact may be partitioned or keyed directly on `parameter_hash` or `scenario_id`; these are **content fields**, not partition keys.

#### 7.5.2 `seed` & `run_id`

* `seed`:

  * S5 does not use RNG and MUST NOT embed or rely on any `seed` field.

* `run_id`:

  * MUST NOT appear in S5 artefact schemas; it lives only in logs/run-report/traces.

---

### 7.6 Cross-segment identity alignment

S5’s artefacts MUST align cleanly with both upstream and downstream identity requirements:

1. **Alignment with S0**

   * `manifest_fingerprint` in index/report/issues MUST match S0’s `manifest_fingerprint`.
   * `parameter_hash` values listed in the report MUST be drawn from S0/S1–S4 and/or `sealed_inputs_5A`, not invented.

2. **Alignment with S1–S4**

   * Any issue referring to `(parameter_hash, scenario_id)` MUST correspond to an actual sealed combination discovered in 5A outputs for this fingerprint.
   * Any reference to artefacts (by `owner_segment`, `artifact_id`) MUST correspond to entries in `sealed_inputs_5A` and the dictionary.

3. **Alignment with downstream consumers**

   * S5’s `_passed.flag_5A` MUST be the *only* flag consumed by 5B, 6A, etc. to decide whether 5A is usable for a given `manifest_fingerprint`.
   * If multiple flags or bundles are present (e.g. due to manual corruption), consumers MUST treat the situation as **invalid** and require human intervention.

Within these constraints, S5’s identity, partitioning, ordering and merge rules produce a **single, immutable, verifiable gate** per world: if `_passed.flag_5A` is valid for a `manifest_fingerprint`, the corresponding `validation_bundle_5A` is guaranteed to match exactly what S5 produced for that world.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines:

* **When a world is considered “5A-PASS”** for a given `manifest_fingerprint`, and
* The **gating obligations** that `_passed.flag_5A` imposes on all downstream consumers.

All rules here are **binding**.

---

### 8.1 Conditions for a world to be “5A-PASS”

For a given `manifest_fingerprint`, Segment 5A is considered **PASS** only if **all** the following hold:

1. **S5 completed successfully (no internal fatal error)**
   1.1 The 5A.S5 algorithm (Steps 1–7) ran to completion for this fingerprint without encountering:

   * `S5_IO_READ_FAILED`,
   * `S5_IO_WRITE_FAILED`,
   * `S5_INTERNAL_INVARIANT_VIOLATION`, or any other fatal S5 error, **during** bundle construction.

   1.2 S5 produced a structurally valid `validation_report_5A` summarising its checks.

2. **S0 gate & sealed inputs are internally consistent**
   2.1 `s0_gate_receipt_5A` and `sealed_inputs_5A`:

   * exist for `fingerprint={manifest_fingerprint}`,
   * are schema-valid,
   * embed `manifest_fingerprint` equal to this fingerprint,
   * refer to a non-empty `parameter_hash`.

   2.2 Recomputed `sealed_inputs_digest` from `sealed_inputs_5A` matches `s0_gate_receipt_5A.sealed_inputs_digest`.

   2.3 All Layer-1 segments 1A–3B in `verified_upstream_segments` have `status="PASS"`.

3. **Per-parameter-pack & per-scenario checks are green**
   For every discovered `(parameter_hash, scenario_id)` in this fingerprint (i.e. every combination for which S3/S4 outputs exist or are expected):

   3.1 **S1 checks** for `merchant_zone_profile_5A` are acceptable:

   * dataset is present and schema-valid,
   * PK is respected; `demand_class` non-null for all in-scope domain rows,
   * base scale fields are finite and non-negative,
   * any missing/broken S1 artefacts are either:

     * absent entirely (so no S3/S4 domain for that parameter pack), or
     * recorded as blocking failures in the report.

   3.2 **S2 checks** for `shape_grid_definition_5A` and `class_zone_shape_5A` are acceptable:

   * grid contiguous and consistent with time-grid policy,
   * shapes non-negative and normalised per `(demand_class, zone[,channel])` within specified tolerance,
   * S2 domain covers all classes/zones used by S1 under that pack.

   3.3 **S3 checks** for `merchant_zone_baseline_local_5A` are acceptable:

   * dataset present & schema-valid,
   * baseline λ non-negative and finite,
   * domain parity: each in-scope `(merchant, zone[,channel])` has exactly `T_week` baseline buckets,
   * where policy defines a weekly sum vs base scale invariant, the maximum relative/absolute error is within configured tolerances.

   3.4 **S4 checks** for `merchant_zone_scenario_local_5A` (and any optional overlay/UTC datasets) are acceptable:

   * dataset present & schema-valid,
   * horizon grid is valid; every baseline `(merchant, zone[,channel])` has complete horizon coverage,
   * `lambda_local_scenario` is non-negative and finite,
   * overlay factors (if materialised) are finite, non-negative, and within policy bounds; sample recomposition `λ ≈ λ_base × F` holds within tolerance,
   * any UTC projection (if present) is consistent with local intensities and 2A civil-time mapping, within tolerance.

   3.5 Per-run status summarised in `validation_report_5A`:

   * for each `(parameter_hash, scenario_id)`, `status ∈ {"PASS","WARN"}` (no blocking `FAIL`),
   * any `WARN` statuses correspond only to non-blocking checks as defined in validation policy.

4. **Overall 5A world status is PASS**

   4.1 The `overall_status` field in `validation_report_5A` is `"PASS"`.
   4.2 There are **no issues** in `validation_issue_table_5A` (if present) with:

   * `severity="ERROR"` or
   * `severity="WARN"` flagged as **blocking** by the validation policy.
     (Informational or non-blocking warnings are allowed.)

5. **Bundle index is complete and correct**

   5.1 `validation_bundle_index_5A` exists, is schema-valid, and lives under:

   ```text
   data/layer2/5A/validation/fingerprint={manifest_fingerprint}/validation_bundle_index_5A.json
   ```

   5.2 Every bundle evidence file (report, issue table, etc.) is listed in `entries` with:

   * the correct relative `path`, and
   * a `sha256_hex` that matches the actual file content.

   5.3 No `entries` entry references a non-existent file.

6. **`_passed.flag_5A` exists and matches the bundle**

   6.1 `_passed.flag_5A` exists at:

   ```text
   data/layer2/5A/validation/fingerprint={manifest_fingerprint}/_passed.flag_5A
   ```

   6.2 Its format matches the documented schema (JSON or text), and if JSON, `manifest_fingerprint` in the flag equals the partition token.

   6.3 The `bundle_digest_sha256` (or equivalent `sha256_hex`) stored in `_passed.flag_5A` equals the SHA-256 digest recomputed from all files listed in `validation_bundle_index_5A.entries` in index order.

**If any of these conditions fail, the world MUST NOT be treated as 5A-PASS**, even if a bundle exists; S5 MUST NOT (re)write `_passed.flag_5A` for that fingerprint, or MUST clearly indicate that the existing flag is invalid.

---

### 8.2 What S5 MUST do when the world is not “PASS”

When 5A.S5 detects that one or more checks fail for a `manifest_fingerprint`:

1. **Bundle, not flag**

   * S5 MUST still attempt to write a **validation bundle** (`validation_bundle_5A`) containing:

     * a `validation_bundle_index_5A`,
     * a `validation_report_5A` with `overall_status="FAIL"`,
     * issue table(s) describing the problems.

   * S5 MUST **NOT** write (or must remove/mark invalid) `_passed.flag_5A` for this fingerprint.

2. **Visibility of failure**

   * The report MUST clearly indicate which checks failed and why.
   * Downstream tools MUST be able to inspect the bundle to understand the failure without relying on logs alone.

3. **No partial PASS**

   * S5 MUST NOT introduce multiple flags or partial gate semantics (e.g. “PASS for some scenarios, FAIL for others”).
   * Partial health is expressed in the report/issue table, not in the gate.
   * At the gate level, a world without a valid `_passed.flag_5A` is simply **not PASS**.

---

### 8.3 Gating obligations on downstream consumers

All downstream components that consume 5A outputs (S1–S4) MUST honour the following gates.

#### 8.3.1 Trusting 5A outputs

For a given `manifest_fingerprint`:

* Before reading 5A modelling outputs (S1–S4) for **production** use (simulation, decisioning, external-facing evaluation, etc.), a consumer (5B, 6A, others) MUST:

  1. Locate `validation_bundle_index_5A` and `_passed.flag_5A` for that fingerprint via the catalogue.

  2. Verify that:

     * `_passed.flag_5A` exists in the right partition,
     * it is structurally valid,
     * `bundle_digest` recomputed from `validation_bundle_index_5A.entries` and the listed files equals the digest embedded in `_passed.flag_5A`.

  3. Optionally, confirm that `validation_report_5A.overall_status == "PASS"`.

* If **any** of these checks fail:

  * The world MUST be treated as **not 5A-PASS**.
  * The consumer MUST NOT treat S1–S4 outputs as authoritative or use them to drive critical behaviour.

#### 8.3.2 Handling multiple or conflicting flags/bundles

* If more than one `_passed.flag_5A` or multiple conflicting `validation_bundle_index_5A` files are found for the same fingerprint:

  * Consumers MUST treat this as an invalid state.
  * They MUST NOT choose an arbitrary one; instead, they MUST escalate to operators or validation tools.

#### 8.3.3 Non-production / dev exceptions

* For non-production or exploratory workflows (e.g. ad-hoc analysis), you MAY allow consumers to read S1–S4 outputs without a verified flag, but:

  * such usage MUST be clearly marked as **“unsealed / dev-only”**,
  * consumers MUST NOT treat such worlds as production-quality or consistent;
  * in prod or CI pipelines, the presence of a valid `_passed.flag_5A` MUST remain the gate.

---

### 8.4 Gating obligations on 5A itself and validation tooling

#### 8.4.1 5A internal states (S1–S4)

* S1–S4 MAY run without waiting for S5, and **MUST NOT** block on `_passed.flag_5A`.
* However, if 5A is re-run under a modified `manifest_fingerprint` or `parameter_hash`, S5 MUST be re-run to produce a fresh bundle/flag.

#### 8.4.2 Validation & ops tools

* Tools that surface 5A health MUST:

  * read `validation_report_5A` and, if present, `validation_issue_table_5A` for a fingerprint,
  * show `overall_status` and per-check statuses,
  * distinguish between:

    * “S5 hasn’t been run yet for this fingerprint”, and
    * “S5 has run and this fingerprint is FAIL”.

---

### 8.5 When S5 MUST treat a world as FAIL

S5 MUST treat a world as **FAIL** (no `_passed.flag_5A` may be written) in at least the following cases:

* S0 gate/ sealed-inputs are missing or inconsistent.
* Any upstream Layer-1 segment 1A–3B is not `PASS` in S0.
* Any expected 5A artefact (S1–S4 outputs, required policies/configs) is missing or schema-invalid.
* Any binding contract for S1–S4 (domain coverage, S2 normalisation, S3 weekly sums, S4 overlay behaviour, identity alignment) fails beyond allowed tolerance.
* The bundle/index or flag cannot be constructed consistently (e.g. digests don’t match, partial previous state, etc.).
* Any S5 internal invariant violation prevents producing a coherent bundle.

In all such cases:

* S5 MUST still attempt to build a **FAILED bundle** describing the issues, unless internal I/O or invariants make that impossible;
* S5 MUST NOT create or reuse a `_passed.flag_5A` that would signal PASS.

Within these rules, S5 provides a crisp, unambiguous gate: a world is either sealed and green for 5A (`_passed.flag_5A` verified) or it is not, and all downstream components are required to respect that gate.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error codes** that **5A.S5 — Segment Validation & HashGate** MAY emit, and the conditions under which they MUST be raised. These codes are **binding**: implementations MUST either use them directly or maintain a strict 1:1 mapping.

Very important distinction:

* **World-level FAIL (validation result)**
  – S5 runs to completion, builds a `validation_bundle_5A` with `overall_status="FAIL"`, and **does not** write a valid `_passed.flag_5A`.
  – This is **not** an S5 error; `state_status` in the run-report is `"SUCCESS"`.
  – Failures are expressed via `validation_report_5A` and `validation_issue_table_5A`.

* **S5-level FAIL (state failure)**
  – S5 itself cannot produce a coherent bundle/flag (I/O problems, index/flag inconsistencies, internal invariants broken, etc.).
  – In this case, `state_status="FAILED"` and an **error_code** from this section MUST be surfaced.

The codes below are only for the second case.

---

### 9.1 Error reporting contract

Whenever 5A.S5 **fails as a state** (cannot produce a consistent bundle+flag), it MUST surface a failure via:

* the engine’s **run-report**, and
* structured logs / metrics.

Each such failure record MUST include at least:

* `segment_id = "5A.S5"`
* `manifest_fingerprint`
* `run_id`
* `state_status = "FAILED"`
* `error_code` — one of the codes in §9.2
* `severity = "FATAL"`
* `message` — short human-readable summary
* `details` — optional structured context (e.g. explaining which path or artefact caused the failure)

S5 does **not** write a separate “errors dataset”; error reporting is via run-report/logs.

---

### 9.2 Canonical error codes (summary)

| Code                              | Severity | Category                                    |
| --------------------------------- | -------- | ------------------------------------------- |
| `S5_IO_READ_FAILED`               | FATAL    | I/O / storage read errors                   |
| `S5_IO_WRITE_FAILED`              | FATAL    | I/O / storage write/commit errors           |
| `S5_INDEX_BUILD_FAILED`           | FATAL    | Could not build a coherent index            |
| `S5_FLAG_DIGEST_MISMATCH`         | FATAL    | Existing flag digest inconsistent           |
| `S5_OUTPUT_CONFLICT`              | FATAL    | Existing bundle/flag differ from recomputed |
| `S5_INTERNAL_INVARIANT_VIOLATION` | FATAL    | Internal “should never happen” bug          |

All of these codes indicate that **S5 could not reliably create or verify `validation_bundle_5A`/`_passed.flag_5A` for this fingerprint**. They are not used to represent “the world failed validation”; that’s in the bundle report.

---

### 9.3 Code-by-code definitions

#### 9.3.1 `S5_IO_READ_FAILED` *(FATAL)*

**Trigger**

Raised when S5 cannot read required inputs due to I/O or storage problems, for example:

* Filesystem or object-store read errors when accessing:

  * `s0_gate_receipt_5A` or `sealed_inputs_5A` for this fingerprint,
  * 5A outputs `merchant_zone_profile_5A`, `shape_grid_definition_5A`, `class_zone_shape_5A`, `merchant_zone_baseline_local_5A`, `merchant_zone_scenario_local_5A`,
  * required policies/configs needed to interpret contracts,
  * or an existing `validation_bundle_index_5A` / `_passed.flag_5A` during idempotency checking.

**Effect**

* S5 MUST:

  * set `state_status="FAILED"` for this run,
  * emit `error_code="S5_IO_READ_FAILED"`,
  * NOT attempt to commit or update `validation_bundle_5A` or `_passed.flag_5A`.

* Operator action: fix storage/network/permissions; rerun S5.

(Because input is unreadable, S5 cannot reliably build a bundle; this is not a world FAIL but an infra failure.)

---

#### 9.3.2 `S5_IO_WRITE_FAILED` *(FATAL)*

**Trigger**

Raised when S5 encounters I/O/storage failures while **writing** or committing its outputs, for example:

* Cannot write staged files for:

  * `validation_bundle_index_5A.json`,
  * `validation_report_5A`,
  * `validation_issue_table_5A`, or other evidence files,
  * `_passed.flag_5A`.

* Cannot atomically move staged files to canonical locations under
  `data/layer2/5A/validation/fingerprint={manifest_fingerprint}/`.

**Effect**

* S5 MUST:

  * set `state_status="FAILED"`,
  * emit `error_code="S5_IO_WRITE_FAILED"`,
  * ensure canonical paths are not left in a partially written or inconsistent state.

* Staging artefacts MUST remain clearly non-canonical (e.g. under `.staging/`) or be cleaned up; downstream MUST ignore them.

* Operator action: fix storage capacity, permissions or availability, then rerun S5.

---

#### 9.3.3 `S5_INDEX_BUILD_FAILED` *(FATAL)*

**Trigger**

Raised when S5 cannot construct a **coherent bundle index** even though it has in-memory evidence files, for example:

* `BUNDLE_FILES` includes duplicate relative paths that cannot be resolved.
* Paths contain invalid components (`..`, absolute paths) that violate the spec.
* The constructed index object fails schema validation and cannot be easily corrected (e.g. required fields missing in ways that indicate code bug or corrupt evidence set).
* S5 detects conflict between expected evidence set and what can be written/registered.

This code is for structural index computation failures, not for typical world validation errors.

**Effect**

* S5 MUST:

  * set `state_status="FAILED"`,
  * emit `error_code="S5_INDEX_BUILD_FAILED"`,
  * NOT write or update the index, bundle or flag.

* Operator action: usually a bug in S5 implementation or deployment; requires engineering intervention.

---

#### 9.3.4 `S5_FLAG_DIGEST_MISMATCH` *(FATAL)*

**Trigger**

Raised when S5 detects that **existing `_passed.flag_5A` and bundle index disagree**, for example:

* `validation_bundle_index_5A` exists and passes schema validation.
* S5 recomputes `bundle_digest` by hashing files listed in the index.
* An existing `_passed.flag_5A` is present but:

  * either its format is invalid, or
  * its `bundle_digest_sha256` value does **not** match the recomputed digest.

This indicates that the existing PASS flag no longer matches the bundle contents (or that one of them has been corrupted).

**Effect**

* S5 MUST:

  * set `state_status="FAILED"`,
  * emit `error_code="S5_FLAG_DIGEST_MISMATCH"`,
  * treat the world as **not sealed**; do **not** rely on or refresh the existing flag.

* S5 MAY:

  * either treat this as a hard conflict requiring manual intervention (preferred), or
  * depending on governance, decide to rebuild the bundle and write a new flag (if allowed).
  * This choice MUST be clearly implemented and documented; the default assumption in this spec is to treat it as an error requiring operator review.

Downstream MUST treat such a world as having an invalid 5A PASS state.

---

#### 9.3.5 `S5_OUTPUT_CONFLICT` *(FATAL)*

**Trigger**

Raised when S5 recomputes the validation bundle for a fingerprint and discovers that:

* A canonical bundle and flag already exist, and
* The **new** bundle it would build from current inputs is **different** from the existing one, for example:

  * New `validation_report_5A` or `validation_issue_table_5A` content differs.
  * The set of evidence files or index entries differs.
  * Recomputed `bundle_digest` differs from that recorded in existing `_passed.flag_5A`.

This indicates that either:

* the sealed world has changed under the same `manifest_fingerprint` (broken identity semantics), or
* S5’s own logic has changed, and governance requires manual decision.

**Effect**

* S5 MUST:

  * set `state_status="FAILED"`,
  * emit `error_code="S5_OUTPUT_CONFLICT"`,
  * NOT overwrite existing `validation_bundle_5A` or `_passed.flag_5A`.

* Operator action:

  * if the world has legitimately changed, mint a **new `manifest_fingerprint`** and re-run S0–S5;
  * if bundle/flag are corrupt, follow governance (e.g. manual deletion + re-run);
  * if S5’s logic changed, treat as a spec upgrade with appropriate migration strategy.

---

#### 9.3.6 `S5_INTERNAL_INVARIANT_VIOLATION` *(FATAL)*

**Trigger**

Catch-all for internal “should never happen” states in S5’s own logic, for example:

* After building `RUNS` and per-check structures, S5 finds contradictory records for the same `(parameter_hash, scenario_id)` that cannot be explained by sealed inputs.
* The per-world overall status computed from checks cannot be reconciled with details in a consistent way (e.g. both “no runs found” and “runs with severe FAIL” statuses appear simultaneously, indicating a logic bug).
* S5’s internal expectations about S0/S1–S4 spec versions and contracts are violated in ways that do not fit other error codes.

**Effect**

* S5 MUST:

  * set `state_status="FAILED"`,
  * emit `error_code="S5_INTERNAL_INVARIANT_VIOLATION"`,
  * NOT write or update `validation_bundle_5A` or `_passed.flag_5A`.

* Operator action:

  * treat as an implementation defect; requires engineering investigation and likely code changes.

---

### 9.4 Distinguishing S5 errors from world validation failures

To avoid confusion, S5 must clearly separate:

* **State-level errors (S5 fails to run)**
  – represented by the error codes above;
  – `state_status="FAILED"` in the run-report;
  – no new bundle/flag is produced (or they are known to be inconsistent).

* **World-level validation failures (S1–S4 or configurations are bad)**
  – S5 runs successfully, but checks show problems;
  – `state_status="SUCCESS"` in run-report;
  – `validation_report_5A.overall_status="FAIL"`;
  – `_passed.flag_5A` is either not written or not trusted;
  – **no** `error_code` from §9.2 is emitted.

Downstream MUST:

* look at **presence and verification of `_passed.flag_5A`** to decide if a world is 5A-PASS, and
* use **`validation_report_5A` + `validation_issue_table_5A`** to understand *why* a world failed validation, not `error_code` fields.

Within this framework, S5’s error codes only represent failures of the **S5 machinery itself**, not routine failures of the world under validation.

---

## 10. Observability & run-report integration *(Binding)*

This section defines how **5A.S5 — Segment Validation & HashGate** MUST report its activity into the engine’s **run-report**, logging, and metrics systems. These requirements are **binding**.

Unlike S1–S4, S5 doesn’t generate model data; it generates **evidence + a verdict**. Observability must make it clear:

* Did S5 run for this `manifest_fingerprint`?
* Did S5 itself succeed or fail?
* What is the **world-level 5A status** (`PASS`/`FAIL`)?
* How many parameter packs / scenarios were validated and how they fared?

---

### 10.1 Objectives

Observability for S5 MUST allow operators and downstream components to answer, for a given `manifest_fingerprint`:

1. **Did S5 run?**

   * Has S5 ever attempted validation for this world?
   * Did the last S5 run complete successfully as a state?

2. **What is the 5A validation verdict?**

   * Is there a `validation_bundle_5A`?
   * What is `overall_status` in `validation_report_5A` (`PASS` or `FAIL`)?
   * Is `_passed.flag_5A` present and digest-consistent with the bundle?

3. **How “healthy” is the world?**

   * How many `(parameter_hash, scenario_id)` runs?
   * How many passed, warned, or failed?
   * Where do the worst numeric errors / violations live (aggregated)?

All without logging the full contents of S1–S4 outputs.

---

### 10.2 Run-report entries

For **every invocation** of S5, the engine’s run-report MUST contain a record with at least:

* `segment_id = "5A.S5"`
* `manifest_fingerprint`
* `run_id`
* `state_status ∈ {"STARTED","SUCCESS","FAILED"}`
* `start_utc`, `end_utc` (UTC timestamps)
* `duration_ms`

On **SUCCESS** (S5 ran to completion and produced a bundle, regardless of world PASS/FAIL):

The run-report entry MUST additionally include:

* **Bundle & flag summary**

  * `validation_bundle_present` — boolean.
  * `passed_flag_present` — boolean.
  * `bundle_digest_sha256` — the digest written into `_passed.flag_5A` **if and only if** `overall_status="PASS"` and the flag/digest check succeeded; otherwise MAY be omitted or set null.
  * `overall_status_5A` — string; MUST equal `validation_report_5A.overall_status` (`"PASS"` or `"FAIL"`).

* **Scope of validation**

  * `n_parameter_hashes_validated` — number of distinct parameter packs seen in this world.
  * `n_scenarios_validated` — number of `(parameter_hash, scenario_id)` combinations validated.

* **Per-run status breakdown**

  * `n_runs_pass` — count of `(parameter_hash, scenario_id)` with `status="PASS"` in the report.
  * `n_runs_warn` — count with `status="WARN"` (non-blocking warnings only).
  * `n_runs_fail` — count with `status="FAIL"` (blocking).

Optionally:

* Selected numeric metrics from the report, e.g.:

  * `max_shape_norm_error` (max S2 normalisation error over all runs).
  * `max_baseline_sum_error` (max relative difference in S3 weekly sum vs base scale).
  * `max_overlay_factor` / `min_overlay_factor`.
  * `max_lambda_scenario` (largest scenario intensity observed).

On **FAILED** (S5 itself failed before producing a consistent bundle/flag):

* The run-report MUST include:

  * `error_code` — one of S5’s canonical error codes (§9).
  * `error_message` — short text summary.
  * `error_details` — optional structured object (e.g. failing path, reason for index/flag conflict).

In this case, **no new bundle/flag may be trusted**; operators MUST check logs and remediate infra/spec issues.

---

### 10.3 Structured logging

S5 MUST emit **structured logs** (e.g. JSON lines) for key lifecycle events, tagged with:

* `segment_id = "5A.S5"`
* `manifest_fingerprint`
* `run_id`

At minimum, S5 MUST log:

1. **State start**

   * Level: `INFO`
   * Fields:

     * `event = "state_start"`
     * `manifest_fingerprint`, `run_id`
     * optional: environment tags (`env`, `ci_build_id`, etc.)

2. **Inputs resolved**

   * After S0, `sealed_inputs_5A`, dictionaries and registries have been loaded and basic identity checks done.
   * Level: `INFO`
   * Fields:

     * `event = "inputs_resolved"`
     * `parameter_hash_gate` (from S0)
     * `upstream_status` summary from S0 (counts of `PASS`/`FAIL`/`MISSING`)
     * `sealed_inputs_digest_recomputed` and `sealed_inputs_digest_recorded` (for debugging drift).

3. **Runs discovered**

   * After discovering all `(parameter_hash, scenario_id)` combos.
   * Level: `INFO`
   * Fields:

     * `event = "runs_discovered"`
     * `n_parameter_hashes`
     * `n_scenarios`
     * optional: a compact list of `(parameter_hash, scenario_id, expected_s1_s4_presence)`.

4. **Per-state validation summary**

   * After S1–S4 checks have been executed.
   * Level: `INFO`
   * Fields (example):

     ```json
     {
       "event": "validation_summary",
       "per_state": {
         "S1": { "n_runs_pass": ..., "n_runs_fail": ..., "max_base_scale_error": ... },
         "S2": { "n_runs_pass": ..., "n_runs_fail": ..., "max_shape_norm_error": ... },
         "S3": { "n_runs_pass": ..., "n_runs_fail": ..., "max_weekly_sum_rel_error": ... },
         "S4": { "n_runs_pass": ..., "n_runs_fail": ..., "max_overlay_factor": ... }
       },
       "overall_status_5A": "PASS" | "FAIL"
     }
     ```

5. **Bundle built**

   * After index, report and issue table are written to staging and validated.
   * Level: `INFO`
   * Fields:

     * `event = "bundle_built"`
     * `bundle_files_count` — number of files listed in the index.
     * `bundle_digest_sha256` — recomputed digest (to match flag later).
     * `overall_status_5A`.

6. **Flag written**

   * Once `_passed.flag_5A` is successfully committed (only if `overall_status_5A="PASS"` and index/files check out).
   * Level: `INFO`
   * Fields:

     * `event = "flag_written"`
     * `bundle_digest_sha256`
     * `manifest_fingerprint`.

7. **State success**

   * Level: `INFO`
   * Fields:

     * `event = "state_success"`
     * `manifest_fingerprint`, `run_id`
     * `overall_status_5A`
     * `duration_ms`

8. **State failure**

   * Level: `ERROR`
   * Fields:

     * `event = "state_failure"`
     * `manifest_fingerprint`, `run_id`
     * `error_code`
     * `error_message`
     * `error_details`

**Prohibited logging:**

* S5 MUST NOT log:

  * raw rows from S1–S4 datasets,
  * entire policy/config payloads (beyond IDs/versions),
  * full bundle content (reports/issue tables) inline.

Only aggregated metrics and concise error contexts are allowed.

---

### 10.4 Metrics

S5 MUST emit a small set of metrics useful for monitoring. Names are implementation-specific; semantics are binding.

Recommended metrics (per `manifest_fingerprint` run):

1. **Run counters**

   * `fraudengine_5A_s5_runs_total{status="success"|"failed"}` — number of S5 executions, partitioned by state outcome.
   * `fraudengine_5A_s5_errors_total{error_code="S5_IO_READ_FAILED"|...}` — count of S5 state failures by error code.

2. **Latency**

   * `fraudengine_5A_s5_duration_ms` — histogram/summary of S5 runtime.

3. **World coverage**

   * `fraudengine_5A_s5_parameter_hash_count` — number of parameter packs discovered for this fingerprint.
   * `fraudengine_5A_s5_scenario_count` — number of `(parameter_hash, scenario_id)` combinations validated.

4. **Per-state validation status**

   * `fraudengine_5A_s5_runs_state_pass{state="S1"|"S2"|"S3"|"S4"}` — counts of per-state PASS runs.
   * `fraudengine_5A_s5_runs_state_fail{state="S1"|"S2"|"S3"|"S4"}` — counts of per-state FAIL runs.

5. **Key numeric maxima (optional)**

   * `fraudengine_5A_s5_max_shape_norm_error` — max S2 shape normalisation error observed (over all runs in this world).
   * `fraudengine_5A_s5_max_baseline_sum_rel_error` — max S3 weekly-sum relative error.
   * `fraudengine_5A_s5_max_overlay_factor` — max S4 overlay factor (if overlay factors exist).
   * `fraudengine_5A_s5_max_lambda_scenario` — max scenario λ seen.

Metrics MUST NOT include high-cardinality label values like `merchant_id`, `zone_id` or specific `scenario_id` values unless governance explicitly allows them. Typically, labels are limited to environment/cluster and perhaps coarse “PASS vs FAIL” tags.

---

### 10.5 Correlation & traceability

To support end-to-end traceability:

* Every S5 log entry and run-report record MUST include:

  * `segment_id = "5A.S5"`,
  * `manifest_fingerprint`,
  * `run_id`.

If distributed tracing is used:

* S5 SHOULD create/join a trace span (e.g. `"5A.S5"`), and
* annotate the span with `manifest_fingerprint` and key summary metrics (e.g. final `overall_status_5A`).

This allows operators to follow flows like:

> S0 → S1 → S2 → S3 → S4 → **S5** → 5B

and see precisely when and why a world became 5A-PASS or FAIL.

---

### 10.6 Integration with dashboards & validation tooling

Validation & ops tools SHOULD:

* Use S5’s run-report + metrics as the **first-cut view** of 5A health per world, e.g.:

  * list of fingerprints,
  * their latest S5 run status,
  * `overall_status_5A`,
  * counts of PASS/WARN/FAIL runs.

* Then read `validation_report_5A` and `validation_issue_table_5A` for deeper diagnostics, not S1–S4 directly.

Downstream modelling/simulation components (5B, 6A) MUST:

* treat S5’s validated bundle + flag as the **single gate** for “is 5A safe for this world?”, and
* use S1–S4 outputs only after that gate has been verified, relying on S5’s evidence rather than re-implementing the full validation themselves.

Within these rules, S5 is fully observable: its runs can be tracked, its own failures are clear, and its world-level PASS/FAIL verdicts and coverage are inspectable via run-report, logs, metrics, and the validation bundle itself.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on the performance profile of **5A.S5 — Segment Validation & HashGate**, and how to scale it safely.

S5 is fundamentally a **validator + packager**:

* It reads S0–S4 + policies,
* recomputes checks and aggregates,
* then writes a relatively small bundle (reports, index, flag).

It is intended to be **cheap compared to S1–S4** and far cheaper than 5B (event-level work).

---

### 11.1 Performance summary

Key points:

* S5 does **not** generate merchant×zone×bucket surfaces.

* Most of the cost is:

  * scanning S1–S4 datasets to compute **summary statistics and invariants**,
  * merging per-run results into a small report / issue table.

* S5 can be thought of as:

> “One final pass over all 5A outputs, plus hashing a handful of small files.”

So, even for large worlds, S5 is usually **CPU-light** and **I/O-moderate**, and should not be the bottleneck in the pipeline.

---

### 11.2 Workload characteristics

Let, for a given `manifest_fingerprint`:

* `P` = number of distinct parameter packs (`parameter_hash`) discovered.
* `S` = total number of `(parameter_hash, scenario_id)` combinations.
* `N_mz(p,s)` = number of `(merchant, zone[,channel])` pairs in the S3/S4 domain for run `(p,s)`.
* `T_week` = number of local-week buckets (S2/S3).
* `H_local(p,s)` = horizon buckets per scenario `(p,s)` for S4.

Then S5 sees:

* **Inputs by layer:**

  * S1: `O(Σ_p N_mz(p,·))` rows (merchant×zone domain)
  * S2: `O(Σ_p (T_week + #class×zone×T_week))` rows
  * S3: `O(Σ_(p,s) N_mz(p,s) × T_week)` rows
  * S4: `O(Σ_(p,s) N_mz(p,s) × H_local(p,s))` rows

  plus a small number of configs/policies.

* **Outputs:**

  * `validation_report_5A`: ~single JSON object per fingerprint.
  * `validation_issue_table_5A`: `O(#issues)` rows, typically much smaller than modelling datasets.
  * `validation_bundle_index_5A`: single small JSON object.
  * `_passed.flag_5A`: tiny file.

Importantly, S5 **does not need to read or compute on every row in full detail**:

* Many checks can be done via streaming aggregation (no full materialisation), and
* S5 can choose to down-sample for very heavy numeric diagnostics (implementation choice).

---

### 11.3 Algorithmic complexity (upper bound)

Naïve upper bound if S5 fully scans everything:

* **S1 checks**: O(Σ_p N_mz(p,·))
* **S2 checks**: O(Σ_p (T_week + #class×zone×T_week))
* **S3 checks**: O(Σ_(p,s) N_mz(p,s) × T_week)
* **S4 checks**: O(Σ_(p,s) N_mz(p,s) × H_local(p,s))

However:

* S2 datasets are comparatively small (class×zone×bucket, not merchant×zone×bucket).
* S3/S4 datasets can be large, but S5 doesn’t need to keep them all in memory.

In practice, with streaming:

> **Time complexity** ≈ one or two **sequential passes** over each of S1–S4 for each `(p,s)`
> so total is proportional to the combined size of those datasets.

Because S5 is end-of-pipeline, the expectation is:

* S3/S4 have already done the heavy compute, and
* S5 just runs **sequential scans with cheap arithmetic + aggregation**.

---

### 11.4 I/O profile

**Reads**

* S0: tiny (gate + sealed_inputs).
* S1–S4: read once each per relevant `(parameter_hash, scenario_id)`, often with column projection (e.g. only keys + a few numeric columns).
* Policies/configs: trivial.

**Writes**

* A handful of small files per fingerprint:

  * `validation_report_5A.json`: O(10–100 KiB).
  * `validation_issue_table_5A.parquet`: O(#issues × (tens of bytes)) — often small-to-moderate.
  * `validation_bundle_index_5A.json` and `_passed.flag_5A`: tiny.

I/O hotspots:

* If S3/S4 outputs are very large (many billions of rows), scanning them for checks can be non-trivial — but S5 is still **O(size)**, nothing worse.

Guidance:

* Columnar stores (Parquet) + projection help a lot: S5 typically needs only a subset of columns per dataset.

---

### 11.5 Parallelisation strategy

S5 is mostly **aggregation and validation**, making it embarrassingly parallel across:

* `(parameter_hash, scenario_id)` combinations, and/or
* individual datasets (S1, S2, S3, S4).

Reasonable approaches:

1. **Per-run parallelism**

   * For each `(parameter_hash, scenario_id)` in `RUNS`:

     * Spawn a worker to perform S1–S4 checks for that run.
     * Gather results into the final `validation_report_5A` / issue table.

   * Bundle construction (index + flag) remains single-threaded at the end.

2. **Per-dataset parallelism**

   * Within each run, you can parallelise across:

     * S2 shape-check computations (e.g. partition by `(demand_class, zone[,channel])`).
     * S3/S4 checks by partitioning rows by merchant or zones.

3. **Streaming / chunked scans**

   * For very large S3/S4 surfaces, use chunking:

     * process baselines or scenario intensities in batches (e.g. per merchant ranges or per date windows),
     * update running aggregates and invariants,
     * never loading the entire table into memory.

S5’s final outputs (report, index, flag) are tiny, so **merge pressure is minimal**.

---

### 11.6 Memory considerations

S5’s memory footprint should be dominated by:

* in-memory aggregates / counters / histograms,
* temporary buffers for reading S1–S4 in chunks,
* per-run validation metadata.

S5 SHOULD avoid:

* holding entire S3/S4 datasets in memory; instead, it SHOULD:

  * stream rows and update aggregates, or
  * use windowed scans.

Guidance:

* Keep S5 memory bounded by:

  * `O(#distinct (parameter_hash, scenario_id) + #distinct (check_ids) + #distinct (issues to represent))`,
  * plus a small working set for streaming validation.

---

### 11.7 Failure, retry & backoff

S5 is deterministic, given:

* S0, S1–S4 outputs,
* sealed policies/configs,
* and spec version.

So:

* **Transient S5 errors**
  – `S5_IO_READ_FAILED`, `S5_IO_WRITE_FAILED` – are **safe to retry** after infra fixes; re-running S5 will re-read the same sealed world and produce the same bundle.

* **World-level validation failures**
  – are **not** S5 errors: S5 runs successfully, but the report says `"FAIL"`.
  – Retrying S5 without altering S1–S4 or policies will not change this; you must fix upstream.

* **Output conflicts** (`S5_OUTPUT_CONFLICT`)
  – indicate that the validated world changed under the same `manifest_fingerprint`, or that S5’s behaviour changed.
  – You must **either**:

  * keep the old bundle/flag and treat new results as for a different world (new `manifest_fingerprint`),
  * or follow a governance process to delete & regenerate.

* **Index/flag mismatch** (`S5_FLAG_DIGEST_MISMATCH`)
  – indicates corruption/tampering; you should treat the world as unsealed and investigate before regenerating.

---

### 11.8 Expected runtime envelope (rough, non-binding)

Ballpark expectations (assuming reasonable infra and streaming validation):

* For “typical” worlds:

  * S3/S4 domains up to ~10⁵–10⁶ merchant×zone pairs,
  * `T_week` and horizon lengths in the low 10²–10³ buckets,
  * a handful of `(parameter_hash, scenario_id)` combinations.

  S5 runtime should be:

  * p50: seconds to tens of seconds,
  * p95: well under a few minutes.

* S5 runtime should scale roughly linearly with:

  * number of `(parameter_hash, scenario_id)` combinations, and
  * total size of S3/S4 tables it needs to scan.

It is perfectly acceptable to schedule S5:

* **after** a batch of S0–S4 jobs complete (e.g. as a nightly validation), or
* as part of CI / publishing pipelines whenever a new `manifest_fingerprint` is minted.

In either case, S5’s cost should be small compared to the work needed to produce S1–S4 in the first place.

---

In summary, 5A.S5 is deliberately designed to be:

* **Read-heavy**,
* **streamable**,
* **parallelisable**, and
* strictly cheaper than the modelling work it validates,

so that sealing a world with `_passed.flag_5A` is operationally lightweight but semantically strong.

---

## 12. Change control & compatibility *(Binding)*

This section defines how **5A.S5 — Segment Validation & HashGate** and its contracts may evolve over time, and what compatibility guarantees MUST hold. All rules here are **binding**.

The goals are:

* No silent breaking changes to the **meaning or structure** of 5A validation (bundle + flag).
* Clear separation between:

  * **Spec changes** (what S5 outputs look like / mean), and
  * **world changes** (what S1–S4 outputs or policies are).
* Predictable behaviour for all consumers that rely on `_passed.flag_5A`.

---

### 12.1 Scope of change control

Change control for S5 covers:

1. **Validation artefact schemas**

   * `schemas.layer2.yaml#/validation/validation_bundle_index_5A`
   * `schemas.layer2.yaml#/validation/validation_report_5A`
   * `schemas.layer2.yaml#/validation/validation_issue_table_5A` (if implemented)
   * `schemas.layer2.yaml#/validation/passed_flag_5A`

2. **Catalogue contracts**

   * `dataset_dictionary.layer2.5A.yaml` entries for:

     * `validation_bundle_index_5A` (representing `validation_bundle_5A`),
     * `validation_report_5A`,
     * `validation_issue_table_5A` (if any),
     * `passed_flag_5A`.

   * `artefact_registry_5A.yaml` entries for:

     * `validation_bundle_5A`,
     * `passed_flag_5A`,
     * optionally `validation_report_5A`, `validation_issue_table_5A` as separate artefacts.

3. **Algorithm & hashing law**

   * The deterministic algorithm defined in §6 (S0 + S1–S4 validation, index construction, digest computation, flag creation).
   * Identity & partition discipline in §7.
   * Gating obligations in §8.

Changes to **S1–S4 specs or policies** are handled by those states and reflected as validation results, not by S5 spec changes.

---

### 12.2 S5 spec version

To support safe evolution, S5 MUST expose a **spec version**, referred to as:

* `s5_spec_version` — string, e.g. `"1.0.0"`.

Binding requirements:

* `s5_spec_version` MUST appear as a required field in `validation_bundle_index_5A`.
* It SHOULD also appear in `validation_report_5A` and, if present, in `validation_issue_table_5A`, so that all validation artefacts can be traced back to a spec version.

Schema rules:

* In `validation_bundle_index_5A`:

  ```yaml
  properties:
    s5_spec_version:
      type: string
  required:
    - s5_spec_version
  ```

#### 12.2.1 Versioning scheme

`s5_spec_version` MUST follow semantic-style versioning:

* `MAJOR.MINOR.PATCH`

Interpretation:

* **MAJOR** — incremented when changes are **backwards-incompatible**, e.g.:

  * hashing law changes,
  * bundle layout changes that break older consumers,
  * fundamental reinterpretation of what `overall_status` means.

* **MINOR** — incremented when changes are **backwards-compatible** enhancements, e.g.:

  * new optional fields in the index/report/issue table,
  * additional non-blocking checks logged in the report.

* **PATCH** — incremented for bug fixes / clarifications that do **not** change shapes or observable semantics (e.g. fixing a typo in a metric name, adjusting a purely informational field).

Downstream consumers MUST:

* parse `s5_spec_version`,
* support a defined set of `MAJOR` versions,
* treat any S5 artefacts with unsupported `MAJOR` as **not trustworthy** for gating.

---

### 12.3 Backwards-compatible changes (allowed without MAJOR bump)

The following are considered **backwards-compatible** provided they obey the rules below and may be introduced with a **MINOR** or **PATCH** bump.

#### 12.3.1 Adding optional fields to index/report/issue table

Allowed:

* Adding **optional** fields to:

  * `validation_bundle_index_5A` (e.g. `summary` metrics, extra metadata),
  * `validation_report_5A` (e.g. new `checks[*].metrics` entries),
  * `validation_issue_table_5A` (e.g. new columns in `context`).

Conditions:

* New fields MUST NOT be required for existing consumers; they MUST be optional and have documented defaults (e.g. “absent means value is unknown or not computed”).
* New fields MUST NOT alter the meaning of existing fields.

#### 12.3.2 Adding non-blocking checks

Allowed:

* Adding new **non-blocking** validation checks (e.g. additional informative metrics, more detailed warnings) that:

  * only introduce new `check_id` entries in `validation_report_5A.checks`,
  * may add issues with `severity="WARN"` or `severity="INFO"`, but
  * do not change when `overall_status_5A` becomes `"PASS"` vs `"FAIL"`.

Downstream consumers that only look at `overall_status_5A` remain unaffected; those that reason about individual checks MUST be able to ignore unknown `check_id` values.

#### 12.3.3 Adding additional evidence files to the bundle

Allowed:

* Including new evidence files in `validation_bundle_5A` (e.g. per-run summaries, compressed histograms) and listing them in the index, **as long as**:

  * old consumers that don’t know about them can safely ignore them after verifying the bundle digest,
  * no previously existing files are removed or repurposed without appropriate versioning.

This will change `bundle_digest`, but that is expected when adding files—consumers verify consistency, not content semantics.

#### 12.3.4 Tightening numeric tolerances (within reason)

Allowed:

* Adjusting validation tolerances to catch more subtle issues (e.g. stricter shape normalisation thresholds, more detailed S4 factor bounds), **as long as**:

  * such changes do not flip a substantial population of previously “healthy” worlds into “FAIL” without aligned governance;
  * when in doubt, treat tolerance tightening as a MINOR bump and communicate in release notes.

---

### 12.4 Backwards-incompatible changes (require MAJOR bump)

The following changes are **backwards-incompatible** and MUST be accompanied by:

* a new `MAJOR` in `s5_spec_version`, and
* a coordinated update of all S5 consumers.

#### 12.4.1 Changing hashing law

Incompatible:

* Changing **how the bundle digest is computed**, e.g.:

  * using a different hash algorithm (e.g. SHA-512 instead of SHA-256),
  * changing from “concatenate file bytes in index order and hash” to “hash of hash-of-files” or similar,
  * changing which files are included in the bundle digest while keeping the same field name.

Such changes break any existing `_passed.flag_5A` verification logic and MUST be MAJOR.

#### 12.4.2 Changing index semantics/structure

Incompatible:

* Removing or renaming fields in `validation_bundle_index_5A`, particularly:

  * removing `entries` or changing its type;
  * changing from `path` + `sha256_hex` per entry to some other representation without new field names.

* Changing index semantics such that older consumers cannot reconstruct the bundle digest correctly.

Any such change must be treated as a new `MAJOR` spec and documented thoroughly.

#### 12.4.3 Changing “PASS” semantics

Incompatible:

* Redefining what `overall_status_5A="PASS"` means in a way that contradicts previous versions, for example:

  * previously, all `(parameter_hash, scenario_id)` needed to have `status ∈ {"PASS","WARN"}` with WARN non-blocking;
  * new semantics might require some additional global check that older consumers don’t know about, yet still treat as PASS.

If the meaning of `PASS` changes in a way that affects gating decisions, consumers must be updated and `MAJOR` bumped.

#### 12.4.4 Dropping required artefacts

Incompatible:

* Removing `validation_report_5A` or changing `_passed.flag_5A` from a digest-bearing file to some other form without a new field/schema.

---

### 12.5 Compatibility of code with existing S5 artefacts

Implementations of S5 and its consumers MUST handle **existing** S5 artefacts according to `s5_spec_version`.

#### 12.5.1 Reading older validation bundles

When consumers load S5 artefacts:

* If `s5_spec_version.MAJOR` is in the set of supported MAJOR versions:

  * They MUST interpret fields according to that MAJOR’s contract.
  * Unknown optional fields MUST be ignored or handled using default behaviours.

* If `s5_spec_version.MAJOR` is **greater** than the max supported MAJOR:

  * They MUST treat the world as having an **unsupported validation spec**,
  * They MUST NOT treat `_passed.flag_5A` as authoritative,
  * They SHOULD surface an “unsupported S5 spec version” error or equivalent.

#### 12.5.2 Re-running S5 with newer code

If S5 is upgraded and run again for a `manifest_fingerprint` that already has a bundle+flag:

* If S1–S4 outputs and policies have not changed, and `s5_spec_version` remains the same:

  * S5 SHOULD produce identical bundle+flag; if not, this indicates:

    * a bug fix, or
    * a previously uninitialised field, etc.

  * The default behaviour in this spec is:

    * if recomputed bundle differs → `S5_OUTPUT_CONFLICT` and no overwrite,
    * operators decide whether to:

      * keep the old bundle (and treat it as the recorded verdict), or
      * manually delete & regenerate.

* If S1–S4 outputs / policies changed legitimately:

  * they SHOULD have a new `manifest_fingerprint`;
  * S5 SHOULD be run for the new fingerprint;
  * old validation artefacts SHOULD remain with the old fingerprint (immutable history).

---

### 12.6 Interaction with S1–S4 spec changes & parameter packs

Most changes in 5A behaviour occur upstream:

* via S1–S4 spec/version changes, or
* via parameter-pack changes (`parameter_hash`).

S5 interacts with these as follows:

1. **S1–S4 spec changes**

   * S1–S4 each have their own spec version fields (`s1_spec_version`, `s2_spec_version`, etc.).
   * S5 SHOULD be aware of compatible ranges of these versions; compatibility enforcement may be configured in a `spec_compatibility_config_5A`.
   * If S1–S4 spec MAJOR versions change in ways S5 does not understand, S5 may treat this as an **invariant violation** or record it as a configuration-level validation failure.

2. **Parameter-pack changes**

   * New parameter packs (`parameter_hash`) or scenario configs are reflected in S0 and `sealed_inputs_5A` for a fingerprint.
   * S5 must discover and validate all `(parameter_hash, scenario_id)` under that fingerprint.
   * A change in parameter packs for a world does **not** require an S5 spec change, only a new run of S5.

---

### 12.7 Governance & documentation

Any change to S5 contracts MUST be governed, versioned, and documented:

1. **Spec changes**

   * Changes to §§1–12 for S5 MUST be coordinated with:

     * updates to `schemas.layer2.yaml` for validation anchors,
     * updates to `dataset_dictionary.layer2.5A.yaml`,
     * updates to `artefact_registry_5A.yaml`.

2. **Release notes**

   * Every time `s5_spec_version` changes, release notes MUST include:

     * old → new version,
     * MAJOR/MINOR/PATCH classification,
     * description of changes (schema vs semantics vs new checks),
     * instructions on:

       * whether existing bundles remain valid,
       * whether re-running S5 is required for existing fingerprints.

3. **Testing**

   New S5 implementations MUST be tested against:

   * Synthetic worlds with small S1–S4 surfaces, including:

     * fully PASS cases,
     * partial FAIL cases,
     * missing artefacts.

   * Representative real worlds with large S3/S4 surfaces, focusing on:

     * performance,
     * idempotency,
     * correct detection of world-level PASS/FAIL.

   Tests MUST cover:

   * idempotent re-run behaviour,
   * all S5 error codes (`S5_IO_*`, `S5_INDEX_BUILD_FAILED`, `S5_FLAG_DIGEST_MISMATCH`, `S5_OUTPUT_CONFLICT`, `S5_INTERNAL_INVARIANT_VIOLATION`),
   * standards for handling existing bundles/flags, including conflict detection.

Within these rules, 5A.S5 can evolve safely:

* **World behaviour** changes via S1–S4 + parameter packs and is expressed in validation reports;
* **Validation meta-contract** (bundle layout, hashing law, gating semantics) changes only via explicit, versioned S5 spec evolution with MAJOR/MINOR/PATCH semantics and coordinated consumer updates.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects short-hands, symbols, and abbreviations used in the **5A.S5 — Segment Validation & HashGate** spec. It is **informative** only; binding definitions are in §§1–12.

---

### 13.1 Notation conventions

* **Monospace** (e.g. `validation_bundle_5A`) → concrete dataset / field / config names.
* **UPPER_SNAKE** (e.g. `S5_OUTPUT_CONFLICT`) → canonical S5 error codes.
* `"Quoted"` (e.g. `"PASS"`, `"FAIL"`) → literal enum/string values.
* Single letters:

  * `p` → `parameter_hash` (parameter pack)
  * `s` → `scenario_id`
  * `w` → world (`manifest_fingerprint`)

---

### 13.2 Identity & scope symbols

| Symbol / field         | Meaning                                                                                            |
| ---------------------- | -------------------------------------------------------------------------------------------------- |
| `manifest_fingerprint` | Opaque identifier of the **closed world** whose 5A outputs are being validated and sealed.         |
| `parameter_hash`       | Opaque identifier of a **parameter pack** (policies, configs, scenario definitions) used in 5A.    |
| `scenario_id`          | Scenario identifier within a parameter pack (e.g. `"baseline"`, `"stress_2027"`).                  |
| `run_id`               | Identifier of this execution of S5 for a given `manifest_fingerprint`.                             |
| `s5_spec_version`      | Semantic version (MAJOR.MINOR.PATCH) of the S5 spec that produced the validation artefacts.        |
| `overall_status_5A`    | World-level validation verdict in `validation_report_5A` — `"PASS"` or `"FAIL"`.                   |
| `bundle_digest_sha256` | SHA-256 digest of the validation bundle contents (over files listed in the index, in index order). |

---

### 13.3 Key artefacts & shorthands

| Name / ID                    | Description                                                                                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `validation_bundle_5A`       | Directory-like artefact containing all S5 evidence for a world (index + reports + issue tables).                                                 |
| `validation_bundle_index_5A` | Single JSON index file listing bundle member paths and their SHA-256 digests.                                                                    |
| `validation_report_5A`       | Summary report of all S0–S4 validations for this world (per-check status + metrics).                                                             |
| `validation_issue_table_5A`  | Optional table of individual validation issues with codes, severity, and context.                                                                |
| `_passed.flag_5A`            | Tiny artefact holding `bundle_digest_sha256` for the corresponding `validation_bundle_5A`.                                                       |
| `s0_gate_receipt_5A`         | S0 gate receipt (sealed inputs + upstream 1A–3B status) for this world.                                                                          |
| `sealed_inputs_5A`           | S0 inventory of all artefacts 5A is allowed to read for this fingerprint.                                                                        |
| S1–S4 artefacts              | Shorthand in S5 for 5A modelling outputs being validated (e.g. S1 `merchant_zone_profile_5A`, S2 shapes, S3 baselines, S4 scenario intensities). |

---

### 13.4 Validation sets & domains

| Symbol / expression | Meaning                                                                                                    |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `PARAMS`            | Set of `parameter_hash` values discovered in `sealed_inputs_5A` for this world.                            |
| `RUNS`              | Set/map of `(parameter_hash, scenario_id)` pairs for which 5A outputs exist and S5 performs checks.        |
| `check_id`          | Identifier of a specific validation check (e.g. `"S2_SHAPES_NORMALISED"`, `"S3_WEEKLY_SUM_VS_SCALE"`).     |
| `issue_code`        | Canonical code for a specific issue instance (e.g. `S3_BASELINE_NEGATIVE_LAMBDA`).                         |
| `severity`          | Severity of an issue: `"ERROR"`, `"WARN"`, `"INFO"`.                                                       |
| `context`           | Structured object in issue table describing where an issue occurred (keys like merchant_id, zone, bucket). |

---

### 13.5 Core hashing notation

| Symbol / expression    | Meaning                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| `entries`              | Array in `validation_bundle_index_5A`, each with `{path, sha256_hex}` for one bundle file.       |
| `digest(file)`         | SHA-256 digest (hex) of file `file`’s raw bytes.                                                 |
| `bundle_digest_sha256` | SHA-256 digest computed by concatenating bytes of all files in `entries` order and hashing them. |

Digest law in short:

```text
bundle_digest_sha256
  = SHA256( concat( bytes(file[path_1]), bytes(file[path_2]), ... ) )
```

with `path_i` taken from `entries` sorted ASCII-lex by `path`.

---

### 13.6 S5 error codes (state failures)

For quick reference, S5 state-level error codes (from §9):

| Code                              | Brief description                                                               |
| --------------------------------- | ------------------------------------------------------------------------------- |
| `S5_IO_READ_FAILED`               | S5 could not read required inputs (infra/storage issue).                        |
| `S5_IO_WRITE_FAILED`              | S5 could not write/commit bundle or flag (infra/storage issue).                 |
| `S5_INDEX_BUILD_FAILED`           | S5 could not build a coherent `validation_bundle_index_5A`.                     |
| `S5_FLAG_DIGEST_MISMATCH`         | Existing `_passed.flag_5A` digest does not match recomputed bundle digest.      |
| `S5_OUTPUT_CONFLICT`              | Recomputation produced a different bundle/flag than the existing canonical one. |
| `S5_INTERNAL_INVARIANT_VIOLATION` | A “should never happen” internal inconsistency in S5 implementation.            |

**Important:** these codes are *not* used to signal “world FAIL” (i.e. S1–S4 failing checks); world failures are reported via `validation_report_5A` / issue table with `overall_status_5A="FAIL"`.

---

### 13.7 PASS/FAIL vocabulary

| Term                 | Meaning                                                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **World-level PASS** | For a `manifest_fingerprint`, S5 ran successfully, `validation_report_5A.overall_status="PASS"`, and `_passed.flag_5A` is present and digest-consistent with the bundle. |
| **World-level FAIL** | For a `manifest_fingerprint`, S5 ran successfully, but `validation_report_5A.overall_status="FAIL"`; no valid `_passed.flag_5A` is considered authoritative.             |
| **S5-level FAIL**    | S5 itself failed as a state (I/O error, index/flag inconsistency, internal bug) and could not reliably produce a bundle/flag.                                            |

Downstream components gate on **world-level PASS** (verified `_passed.flag_5A`), not on absence of S5 errors alone.

---

### 13.8 Miscellaneous abbreviations

| Abbreviation | Meaning                                                                         |
| ------------ | ------------------------------------------------------------------------------- |
| S0           | 5A.S0 — Gate & Sealed Inputs                                                    |
| S1           | 5A.S1 — Merchant & Zone Demand Classification                                   |
| S2           | 5A.S2 — Weekly Shape Library                                                    |
| S3           | 5A.S3 — Baseline Merchant×Zone Weekly Intensities                               |
| S4           | 5A.S4 — Calendar & Scenario Overlays                                            |
| S5           | 5A.S5 — Segment Validation & HashGate (this spec)                               |
| “bundle”     | Shorthand for `validation_bundle_5A` (the directory of evidence files + index). |
| “flag”       | Shorthand for `_passed.flag_5A`.                                                |

This appendix is meant as a quick reference when implementing or reviewing S5; authoritative behaviour and contracts remain in §§1–12.

---