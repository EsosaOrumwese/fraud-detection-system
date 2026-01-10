# 5B.S3 — Bucket-level arrival counts (Layer-2 / Segment 5B)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5B.S3 — Bucket-level arrival counts (Layer-2 / Segment 5B)**. It is binding on any implementation of this state and on all downstream 5B states that consume its outputs.

---

### 1.1 Role of 5B.S3 in the engine

Given:

* a sealed world from **5B.S0**,
* the **time grid & grouping** from **5B.S1**, and
* the **realised intensity surface** `λ_realised(m, zone[, channel], bucket)` from **5B.S2**,

**5B.S3** is the **count realisation layer** for arrivals:

* It takes `λ_realised` as the per-bucket mean structure.
* It applies the configured **arrival law** (e.g. Poisson, NB, or a small family of compatible laws) to compute per-bucket mean parameters (e.g. `μ = λ_realised × bucket_duration`).
* It uses Philox (under the 5B RNG policy) to draw **integer counts**:

> `N(m, zone[, channel], bucket)`

for every entity×bucket×scenario in domain.

5B.S3 is **RNG-bearing**: it consumes Philox streams and emits RNG events/traces for count draws. It does **not**:

* assign intra-bucket timestamps, or
* route arrivals to sites/edges.

Those jobs belong to S4.

---

### 1.2 Objectives

5B.S3 MUST:

* **Respect upstream authorities**

  * Treat the S1 time grid as the **only** authority on bucket structure (`scenario_id`, `bucket_index`, bucket durations).
  * Treat S1 grouping as the **only** authority on the domain of `(merchant, zone[, channel])`.
  * Treat S2’s `λ_realised` as the **only** authority for intensity per entity×bucket.

* **Realise counts according to a configured arrival law**

  * Use the arrival-process config (sealed via S0) to:

    * derive per-bucket mean parameter(s) from `λ_realised` and bucket duration (e.g. Poisson μ, NB `(μ, k)`),
    * choose the correct distribution for each entity×bucket (e.g. Poisson vs NB),
    * apply any law-specific constraints (e.g. Fano corridors).

* **Produce a clean bucket-count surface**

  * For every `(scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)` in domain, produce exactly one row with:

    * `N` (non-negative integer count),
    * the mean parameter(s) used for the draw,
    * references to `λ_realised` and any group metadata needed downstream.

* **Emit well-formed RNG events**

  * For each entity×bucket draw (or per configured group of draws), emit RNG events adhering to:

    * Philox envelope rules (counters, draws, blocks),
    * the 5B RNG policy (stream IDs, substream labels, expected budget).
  * Append matching trace rows as required by the Layer-wide RNG discipline.

---

### 1.3 In-scope behaviour

The following are **in scope** for 5B.S3 and MUST be handled by this state:

* **Joining λ_realised with grid & grouping**

  * Deterministically join:

    * `s2_realised_intensity_5B` (λ_realised per entity×bucket),
    * `s1_time_grid_5B` (to get bucket duration & scenario tags),
    * `s1_grouping_5B` (if group metadata is needed for configuration-dependent arrival parameters),

  to define the full count domain and per-bucket parameters.

* **Count parameter computation**

  * For each domain element, compute the arrival-law mean/shape parameters `θ` from:

    * `λ_realised`,
    * bucket duration,
    * and any group/entity-level modifiers defined in the arrival-process config.

* **Count sampling under Philox**

  * Use Philox, via the count-draw stream/substreams defined in the 5B RNG policy, to sample counts:

    ```text
    N ~ arrival_law(θ)
    ```

  * Emit one or more RNG events per draw (according to policy), each with:

    * proper envelopes (counters, draws, blocks),
    * scenario/seed/identity fields,
    * and a matching trace row.

* **Bucket-count dataset construction**

  * Build a count dataset (e.g. `s3_bucket_counts_5B`) with:

    * PK = entity×bucket (plus world/seed IDs),
    * fields: `N`, `λ_realised`, mean parameters `θ`, and any flags needed by downstream logic or validation.

* **Local structural & numeric sanity checks**

  * Ensure:

    * every domain element has exactly one count row,
    * `N` is a non-negative integer and finite,
    * any configured hard constraints (e.g. zero counts when λ_realised = 0) are met.
  * Detailed statistical validation (Fano corridors, distributional properties) may be deferred to the final 5B validation state, but S3 MUST not knowingly emit obviously invalid counts.

---

### 1.4 Out-of-scope behaviour

The following are explicitly **out of scope** for 5B.S3 and MUST NOT be performed by this state:

* **Latent-field and intensity modelling**

  * S3 MUST NOT:

    * recompute or modify latent fields from S2,
    * change `λ_realised`,
    * add an additional latent/noise layer over counts beyond the arrival law.

* **Time-grid and grouping changes**

  * S3 MUST NOT:

    * change `s1_time_grid_5B` (bucket definitions),
    * change `s1_grouping_5B` (group assignments or domain).

* **Intra-bucket timestamp assignment**

  * S3 MUST NOT assign specific times to arrivals within a bucket; it only decides **how many** arrivals occur per bucket.
  * Intra-bucket time placement is the responsibility of S4.

* **Routing to sites or virtual edges**

  * S3 MUST NOT map counts to physical sites or virtual edges, or interact with 2B/3B alias tables.
  * Routing is handled in S4.

* **Segment-level HashGate**

  * S3 does not build the final 5B validation bundle or `_passed.flag`; it only contributes its datasets and RNG logs. The segment-wide PASS decision is owned by a dedicated 5B validation state.

---

### 1.5 Downstream obligations

This specification imposes the following obligations on downstream 5B states:

* **S4 (arrivals & routing) MUST:**

  * treat S3’s count dataset as the **only authority** on “how many arrivals happened” per entity×bucket×scenario×seed;
  * not resample counts or introduce its own count-realisation logic.

* **Final 5B validation state MUST:**

  * incorporate S3’s RNG logs and count dataset into:

    * RNG accounting checks, and
    * statistical checks (e.g. Fano corridor, mean vs λ_realised consistency).

* **No reimplementation of arrival law**

  * No later state may re-implement the arrival law independently. If the arrival law needs to change, that change MUST be expressed via:

    * updated arrival-process config,
    * possibly a new `parameter_hash` / 5B spec version, and
    * a fresh S2–S3 run.

Within this scope, **5B.S3** is the unique, well-defined step that converts **realised intensities** into **integer bucket counts**, ready to be expanded into timestamped, routed arrival events in S4.

---

### Contract Card (S3) - inputs/outputs/authorities

**Inputs (authoritative; see Section 2 for full list):**
* `s0_gate_receipt_5B` - scope: FINGERPRINT_SCOPED; source: 5B.S0
* `sealed_inputs_5B` - scope: FINGERPRINT_SCOPED; source: 5B.S0
* `s1_time_grid_5B` - scope: FINGERPRINT_SCOPED; scope_keys: [manifest_fingerprint, scenario_id]; source: 5B.S1
* `s1_grouping_5B` - scope: FINGERPRINT_SCOPED; scope_keys: [manifest_fingerprint, scenario_id]; source: 5B.S1 (optional)
* `s2_realised_intensity_5B` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, scenario_id]; source: 5B.S2
* `arrival_count_config_5B` - scope: UNPARTITIONED (sealed config); sealed_inputs: required
* `arrival_rng_policy_5B` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required

**Authority / ordering:**
* S3 is the sole authority for bucket-level count draws for 5B.

  **Outputs:**
  * `s3_bucket_counts_5B` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, scenario_id]
  * `rng_event_arrival_bucket_count` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]
  * `rng_audit_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]
  * `rng_trace_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]

**Sealing / identity:**
* External inputs MUST appear in `sealed_inputs_5B` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or RNG/policy violations -> abort; no outputs published.

## 2. Preconditions & dependencies *(Binding)*

This section defines **when 5B.S3 — Bucket-level arrival counts** is allowed to run and **what it depends on**. If any precondition fails, S3 MUST NOT produce outputs and MUST be treated as FAIL for that `(parameter_hash, manifest_fingerprint, seed)`.

---

### 2.1 Dependency on S0 (Gate & sealed inputs)

Before S3 may execute for a given `(parameter_hash = ph, manifest_fingerprint = mf, seed, run_id)`:

1. **S0 outputs MUST exist and be valid**

   * `s0_gate_receipt_5B` and `sealed_inputs_5B` for `mf` MUST:

     * exist at their canonical paths,
     * validate against their schemas, and
     * satisfy the digest equality (recomputed `sealed_inputs_5B` digest = `sealed_inputs_digest` in the receipt).

   * `s0_gate_receipt_5B.parameter_hash` MUST equal `ph`.

2. **Upstream segments MUST all be PASS**

   * In `s0_gate_receipt_5B.upstream_segments`, every required upstream segment
     `{1A, 1B, 2A, 2B, 3A, 3B, 5A}` MUST have `status = "PASS"`.

S3 MUST NOT re-hash upstream validation bundles itself; S0’s upstream status map is authoritative for gating.

---

### 2.2 Dependency on S1 (time grid & grouping)

For each `scenario_id` S3 intends to process (the `scenario_set` in `s0_gate_receipt_5B`):

1. **S1 outputs MUST exist and be valid**

   * `s1_time_grid_5B@manifest_fingerprint=mf/scenario_id={scenario_id}` MUST exist and validate against `schemas.5B.yaml#/model/s1_time_grid_5B`.
   * `s1_grouping_5B@manifest_fingerprint=mf/scenario_id={scenario_id}` MUST exist and validate against `schemas.5B.yaml#/model/s1_grouping_5B`.

2. **Identity and domain consistency**

   * In both S1 datasets:

     * `manifest_fingerprint == mf`, `parameter_hash == ph`.
   * `s1_time_grid_5B` MUST expose a finite, ordered, contiguous set of `bucket_index` values per `scenario_id`.
   * `s1_grouping_5B` MUST expose a finite, duplicate-free set of `(merchant_id, zone_representation[, channel_group])` per `scenario_id`.

If any of these checks fail for any `scenario_id` in scope, S3 MUST NOT run.

---

### 2.3 Dependency on S2 (realised intensities)

S3 operates **only** on intensities realised by S2. For each `scenario_id` and `seed`:

1. **S2 outputs MUST exist and be valid**

   * `s2_realised_intensity_5B@seed={seed}/manifest_fingerprint={mf}/scenario_id={scenario_id}` MUST:

     * exist,
     * validate against `schemas.5B.yaml#/model/s2_realised_intensity_5B`, and
     * have `manifest_fingerprint == mf`, `parameter_hash == ph`, `seed == seed`, `scenario_id == scenario_id`.

2. **Domain coverage**

   * For each `(scenario_id)` S3 intends to process, S2’s realised intensity domain MUST be joinable to S1’s domain:

     * every `(merchant_id, zone_representation[, channel_group], bucket_index)` that S3 will count against MUST have a `lambda_realised` row.

S3 MUST treat S2’s domain as authoritative for “where intensities exist”; it MUST NOT fabricate intensities for missing entity×bucket combinations.

---

### 2.4 Required configs & policies for S3

Before S3 runs, the following 5B artefacts MUST be present in `sealed_inputs_5B` for `mf` with `status ∈ {REQUIRED, INTERNAL}` and be resolvable via catalogue:

1. **Arrival-process / count-law config** (e.g. `arrival_count_config_5B`)

   * Defines, at minimum:

     * the **arrival law** to use (e.g. Poisson, NB, or allowed family),
     * how to derive the mean parameter(s) from `lambda_realised` and bucket duration (e.g. `μ = λ_realised × bucket_duration_seconds`),
     * any per-group/per-entity/per-bucket tweaks (e.g. different NB dispersion per group),
     * any hard constraints or Fano corridor targets S3 must honour locally (e.g. “if μ=0, force N=0”).

2. **S3 RNG policy** (may be shared with other 5B RNG or a unified `arrival_rng_policy_5B`)

   * Defines:

     * Philox stream IDs and substream labels for **count draws**, distinct from S2’s latent-field streams,
     * expected event-per-draw mapping (e.g. one RNG event per entity×bucket),
     * `draws`/`blocks` expectations per event, and
     * how to map `(scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)` to counters or offsets.

3. **(Optional) S3 validation/guardrail config**

   * If present, defines local numeric guardrails (e.g. refusal to draw from absurdly large μ, or behaviour for extremely small μ) and local Fano checks S3 should perform.

All of the above MUST validate against their schemas (in `schemas.5B.yaml` or `schemas.layer2.yaml`) before S3 proceeds.

---

### 2.5 Data-plane access scope for S3

Given `sealed_inputs_5B` and catalogue:

* S3 MAY read **row-level** from:

  * `s1_time_grid_5B` (bucket durations, scenario tags),
  * `s1_grouping_5B` (entity domain; group_id if needed for per-group params),
  * `s2_realised_intensity_5B` (λ_target, lambda_random_component, lambda_realised),
  * S3 configs / policies (small tables/objects).

* S3 MAY read **metadata-only** from:

  * 2A `tz_timetable_cache` (if bucket durations or cross-day mapping need to be double-checked),
  * upstream λ surfaces from 5A (if required only to verify shape, not to drive counts directly).

* S3 MUST honour `read_scope` in `sealed_inputs_5B`:

  * If an artefact is marked `METADATA_ONLY`, S3 MUST NOT read rows from it.

S3 MUST NOT:

* read any artefact not listed in `sealed_inputs_5B` for `mf`,
* re-derive λ_target or λ_realised from upstream surfaces (it must consume S2’s outputs instead).

---

### 2.6 Invocation order within 5B

Within Segment 5B, S3 MUST:

* run **after**:

  * S0 (gate & sealed inputs) has locally PASSed for `(ph, mf)`,
  * S1 (time grid & grouping) has locally PASSed,
  * S2 (latent fields) has locally PASSed for `(ph, mf, seed)` and produced `s2_realised_intensity_5B` for all required `scenario_id`.

* run **before**:

  * S4 (micro-time & routing) for that `(ph, mf, seed)`, which depends on the bucket counts from S3.

S3 MUST NOT:

* run concurrently with S2 for the same `(ph, mf, seed)` and `scenario_id` (to avoid racing on S2 outputs), or
* re-run for the same `(ph, mf, seed)` in a way that would change counts without changing `parameter_hash` and/or arrival-process config.

Any change to the arrival law or count-parametrisation that alters count distributions for a world MUST be expressed via a new `parameter_hash` and/or 5B spec version and a fresh S0/S1/S2/S3 run.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes **what 5B.S3 is allowed to read** and **who is authoritative for which facts**. S3 MUST operate strictly inside the closed world sealed by **5B.S0** and MUST NOT override upstream responsibilities.

---

### 3.1 Inputs S3 MAY use

S3 MAY only use artefacts that:

* are listed in `sealed_inputs_5B` for this `manifest_fingerprint = mf`, and
* are resolved via catalogue (dictionary + registry + upstream sealed-inputs), not hard-coded paths.

Within that universe, S3’s logical inputs are:

#### (a) 5B.S0 / S1 / S2 control & planning (mandatory)

* **`s0_gate_receipt_5B` + `sealed_inputs_5B`**

  * For `parameter_hash = ph`, `manifest_fingerprint = mf`, `seed`, `scenario_set`, upstream status, and the whitelist of artefacts S3 may read.

* **`s1_time_grid_5B` (row-level)**

  * For each `scenario_id` S3 processes:

    * bucket structure: `bucket_index`, `bucket_start_utc`, `bucket_end_utc`,
    * bucket duration (direct or derivable),
    * scenario tags if needed (baseline/stress/holiday).

* **`s1_grouping_5B` (row-level)**

  * For each `scenario_id`:

    * the entity domain `(merchant_id, zone_representation[, channel_group])`,
    * `group_id` if the arrival law uses group-level parameters (e.g. NB dispersion per group).

* **`s2_realised_intensity_5B` (row-level)**

  * For each `(seed, mf, scenario_id)`:

    * `lambda_baseline` (if echoed),
    * `lambda_realised`,
    * `lambda_random_component` (if needed for diagnostics),
    * keys matching S1 domain: `(merchant_id, zone_representation[, channel_group], bucket_index)`.

S3 MUST treat S1+S2 as authoritative for the domain and intensity surface; it cannot “correct” or extend them.

#### (b) 5B local configs & RNG policy (row-level)

S3 MUST read the following 5B artefacts (present in `sealed_inputs_5B` as `status ∈ {REQUIRED, INTERNAL}`):

* **Arrival/count-law config** (e.g. `arrival_count_config_5B`)

  * Defines:

    * which arrival law to use (Poisson, NB, etc.),
    * how to derive distribution parameters `(μ, k, …)` from `lambda_realised` and bucket duration,
    * any law-specific constraints (e.g. `N = 0 if lambda_realised = 0`, caps on μ).

* **S3 RNG policy** (or shared `arrival_rng_policy_5B`)

  * Defines:

    * Philox stream IDs and substream labels for count draws,
    * expected event granularity (e.g. one RNG event per entity×bucket),
    * mapping from `(scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)` to counters/substreams,
    * expected `draws` and `blocks` semantics per event.

* **(Optional) count-validation / guardrail config**

  * If present, defines additional local checks (e.g. how to handle extremely large μ, or minimum/maximum sensible Fano ratios) that S3 should enforce before handing off to the final 5B validation state.

These configs are small, schema-governed objects; S3 MUST treat them as the **only** source for count-law and S3 RNG behaviour. It MUST NOT bake count-law parameters directly into code outside these configs.

#### (c) Optional upstream metadata (metadata-only)

S3 MAY inspect **metadata only** (no row-level modelling) from:

* 2A `tz_timetable_cache` or other civil-time surfaces

  * e.g. to double-check bucket duration or to tag cross-day transitions, if required by arrival config.

* Upstream surfaces from 5A / 2B / 3A / 3B

  * **only** to derive small structural hints (e.g. group size, merchant class) if the arrival config says count-law parameters depend on such metadata.

For these artefacts, S3 MUST honour `read_scope = METADATA_ONLY` in `sealed_inputs_5B` and MUST NOT:

* treat them as an alternative source of λ or counts,
* scan their rows as part of the core arrival process.

---

### 3.2 Authority boundaries (who owns what)

Within S3, ownership is:

* **Closed world & upstream PASS status**

  * **Owner:** 5B.S0
  * S3 MUST:

    * trust S0’s `sealed_inputs_5B` as the exact whitelist of inputs, and
    * trust `upstream_segments` as the upstream PASS/FAIL map.
  * It MUST NOT widen the input set or reinterpret upstream PASS/FAIL itself.

* **Time grid & entity domain**

  * **Owner:** 5B.S1
  * S3 MUST:

    * use `s1_time_grid_5B` as the canonical bucket set (`scenario_id`, `bucket_index`, bucket duration),
    * use `s1_grouping_5B` as the canonical domain of `(merchant_id, zone_representation[, channel_group])` per scenario.
  * S3 MUST NOT:

    * add buckets not present in S1,
    * redefine entity domain,
    * change group_ids.

* **Realised intensity surface**

  * **Owner:** 5B.S2
  * S3 MUST:

    * treat `lambda_realised` from `s2_realised_intensity_5B` as the **only** mean intensity per entity×bucket,
    * not recompute λ from 5A or S1,
    * not apply additional latent noise or rescaling on top of `lambda_realised` (beyond any minimal clipping dictated by the arrival config for numerical safety).

* **Civil-time semantics**

  * **Owner:** 2A
  * If S3 uses bucket duration or day-type information, it MUST:

    * rely on S1’s grid (which is already aligned to 5A/2A), and/or
    * follow 2A’s rules (if it has to recompute duration from UTC times).
  * It MUST NOT invent its own notion of “time distance” that contradicts 2A.

* **Count-law & RNG semantics**

  * **Owner:** 5B.S3 + its configs
  * The **arrival/count-law config** and **S3 RNG policy** (sealed by S0) are the only authorities for:

    * which distributions are allowed,
    * how their parameters are derived from λ_realised + bucket_duration,
    * how Philox streams/counters are used for count draws.

Downstream S4 MUST accept that S3 owns “how many per bucket” and may only consume its results.

---

### 3.3 Prohibited inputs & behaviours

To keep boundaries clean, S3 MUST NOT:

* Read any artefact that is **not** present in `sealed_inputs_5B` for `mf`.
* Bypass `sealed_inputs_5B` to discover additional artefacts via direct filesystem paths or network calls.
* Read row-level data from artefacts marked `METADATA_ONLY` in `sealed_inputs_5B` (e.g. large upstream tables meant only for sealing/validation).

S3 also MUST NOT:

* Modify or overwrite:

  * S1 outputs (`s1_time_grid_5B`, `s1_grouping_5B`),
  * S2 outputs (`s2_realised_intensity_5B`),
  * upstream validation bundles or `_passed.flag`,
  * any upstream `sealed_inputs_*` tables.

* Introduce a second, independent arrival-process layer:

  * No additional latent fields over counts;
  * No ad-hoc reparameterisations of the arrival law outside what the config allows.

If S3 finds that it “needs” information or behaviour outside these boundaries, that is a **spec/config problem**, not an invitation to improvise: S3 MUST fail with a canonical error rather than widening its inputs or crossing authority lines.

---

## 4. Outputs (datasets) & identity *(Binding)*

This section fixes **what 5B.S3 produces** and **how those outputs are identified**.

S3 has **one required data-plane output**:

* `s3_bucket_counts_5B` — bucket-level arrival counts per entity×bucket×scenario×seed.

RNG event logs for count draws are handled via the Layer-wide RNG log schemas and are not considered here as S3 “datasets”.

---

### 4.1 Identity scope

S3’s bucket-count output is determined by:

* **World identity:**
  `world_id = (parameter_hash = ph, manifest_fingerprint = mf)`
  (what world we’re in — sealed via S0).

* **Stochastic identity:**
  `stochastic_id = (ph, mf, seed)`
  (which Philox realisation of counts we’re using).

* **Scenario identity:**
  `scenario_id ∈ scenario_set_5B`
  (which scenario horizon and λ_realised slice we’re on).

Binding rules:

* For fixed `(ph, mf, seed, scenario_id)` and fixed upstream artefacts/configs, `s3_bucket_counts_5B` MUST be **deterministic and byte-identical** across re-runs, independent of `run_id`.
* Changing `seed` MAY change the counts; that is the point of multiple stochastic realisations for the same world.

---

### 4.2 `s3_bucket_counts_5B` — bucket-level counts *(REQUIRED)*

**Role**

` s3_bucket_counts_5B` is the **authoritative bucket-count surface** for arrivals. For each:

* `scenario_id`,
* `(merchant_id, zone_representation[, channel_group])` in S1’s grouping domain, and
* `bucket_index` in S1’s time grid,

and for a given `seed`, it records:

* the integer **count** `N`, and
* the **distribution parameters** used for the draw (derived from `lambda_realised` and bucket duration).

Downstream S4 MUST use this dataset as the only source for “how many arrivals” per entity×bucket×scenario×seed.

**Domain (conceptual)**

For each `scenario_id`, define:

```text
D_s := {
  (merchant_id, zone_representation[, channel_group], bucket_index)
  : exists lambda_realised in s2_realised_intensity_5B
    and bucket_index in s1_time_grid_5B
}
```

For fixed `(ph, mf, seed, scenario_id)`, `s3_bucket_counts_5B` MUST have **exactly one row** for each element of `D_s`, and MUST NOT contain any rows outside `D_s`.

**Key columns (at a minimum)**

The concrete schema is pinned in `schemas.5B.yaml#/model/s3_bucket_counts_5B`, but at a high level each row MUST include:

* Identity & keys:

  * `manifest_fingerprint : string`
  * `parameter_hash : string`
  * `seed : integer | string`
  * `scenario_id : string`
  * `merchant_id` (via Layer-1 `id64` type)
  * `zone_representation` (the chosen zone representation; must match S1/S2 conventions)
  * optional `channel_group : string`
  * `bucket_index : integer` (aligned to S1 grid)

* Intensity / parameters:

  * either:

    * `lambda_realised : number` echoed from S2, or
    * a stable reference that lets S3 reconstruction be checked (schema will fix this);
  * `bucket_duration_seconds : integer` (or an equivalent),
  * arrival-law parameter(s), e.g.:

    * `mu : number` (Poisson mean), and/or
    * `nb_r : number`, `nb_p : number` for NB, etc.
      Names/types are fixed by the schema and arrival config.

* Count:

  * `count_N : integer`

    * non-negative, finite, the realised count for this entity×bucket.

Optional diagnostic fields (e.g. flags for clipping, Fano category) MAY exist but are not required for the core contract.

**Identity**

* Logical key per row:

  ```text
  (manifest_fingerprint, parameter_hash, seed,
   scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)
  ```

* This combination MUST be unique.

Downstream S4 and the 5B validation state MUST rely on this dataset as:

* the **one source of bucket counts**, and
* the way to link back to λ_realised (via shared keys and any echoed λ/parameter fields).

---

### 4.3 Required vs optional datasets

For S3:

* `s3_bucket_counts_5B` — **REQUIRED**, `final_in_state: true`, not final in segment.

  * S3 MUST NOT claim PASS without fully materialising and validating this dataset for all `(scenario_id ∈ scenario_set_5B)`.

No separate S3 diagnostic dataset is defined at this stage; any per-bucket diagnostics (e.g. Fano flags) SHOULD be carried as extra columns on `s3_bucket_counts_5B` rather than a separate table, to avoid unnecessary bloat.

RNG event logs for count draws:

* are registered separately as `LOG` artefacts using the Layer-wide RNG schemas,
* are required for RNG accounting and replay,
* but are not treated as “outputs (datasets)” in this section.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

The S3 egress contracts are fully specified in:

* docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml
* docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml
* docs/model_spec/data-engine/layer-2/specs/contracts/5B/artefact_registry_5B.yaml

S3 emits a single dataset: `s3_bucket_counts_5B` (integer counts per `(seed, scenario, merchant, zone, channel_group, bucket_index)`).

### 5.1 `s3_bucket_counts_5B`

* **Schema anchor:** `schemas.5B.yaml#/model/s3_bucket_counts_5B`
* **Dictionary entry:** `datasets[].id == "s3_bucket_counts_5B"`
* **Registry manifest key:** `mlr.5B.model.s3_bucket_counts`

Binding rules:

* Partitioning/path layout (`seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}`) and the composite primary key are defined in the dictionary; S3 MUST adhere to them when writing shards.
* Column meanings (counts, RNG receipts, integrity flags) are governed by the schema pack. This state spec only enforces that counts reflect the exact integerisation performed in §6 and that every in-scope entity appears exactly once per bucket.
* Registry dependencies (realised intensities, grouping, RNG policy, scenario surfaces) are authoritative; no additional artefacts may be read unless they appear in `sealed_inputs_5B` and the registry first.
* Determinism: for a fixed `(seed, parameter_hash, manifest_fingerprint, scenario_id)`, reruns MUST produce byte-identical output.

Any schema or catalogue changes MUST occur in the contract files before S3 alters its egress behaviour.
## 6. Deterministic algorithm with RNG (count realisation) *(Binding)*

This section defines the **exact responsibilities and structure** of **5B.S3 — Bucket-level arrival counts**.

The algorithm is:

* **Deterministic given**
  `(parameter_hash = ph, manifest_fingerprint = mf, seed, scenario_set_5B)` + sealed inputs (S0), S1 outputs, S2 outputs, and 5B configs.
* **RNG-bearing**
  It consumes Philox streams and emits RNG events + trace rows for count draws.
* **Scope-limited**
  It only maps `λ_realised` → integer counts per bucket; no timestamps, no routing.

For fixed `(ph, mf, seed)` and fixed configs, re-running S3 MUST produce **byte-identical** outputs and RNG logs, independent of `run_id`.

---

### 6.1 General constraints

1. **No RNG before preconditions**

   * S3 MUST NOT consume Philox or emit RNG events until:

     * S0/S1/S2 preconditions in §§2–3 are validated.

2. **Domain comes from S1 + S2**

   * S3 MUST NOT invent buckets or entities outside:

     * S1 grid (`s1_time_grid_5B`), and
     * S2 realised-intensity domain (`s2_realised_intensity_5B`).

3. **λ ownership**

   * S3 MUST treat `lambda_realised` from S2 as canonical and MUST NOT:

     * rescale, blur, or recompute λ from upstream sources,
     * add extra latent noise on top of `lambda_realised`.

4. **Idempotency**

   * For fixed `(ph, mf, seed, scenario_set_5B)` and configs, S3 outputs and RNG logs MUST be identical if re-run.

---

### 6.2 Step 0 — Load & validate context

1. **Load S0 outputs**

   * Read `s0_gate_receipt_5B@mf` and `sealed_inputs_5B@mf`.
   * Validate:

     * schemas,
     * `parameter_hash == ph`, `manifest_fingerprint == mf`,
     * `sealed_inputs_digest` equals recomputed digest of `sealed_inputs_5B`,
     * `upstream_segments[seg].status == "PASS"` for all required segments `{1A,1B,2A,2B,3A,3B,5A}`.

2. **Load S1 outputs**

   For each `scenario_id ∈ scenario_set_5B`:

   * Load and validate:

     * `s1_time_grid_5B@mf, scenario_id`
     * `s1_grouping_5B@mf, scenario_id`
   * Confirm:

     * `manifest_fingerprint == mf`, `parameter_hash == ph`,
     * contiguous, ordered `bucket_index` per scenario,
     * no duplicate grouping keys.

3. **Load S2 outputs**

   For each `(scenario_id ∈ scenario_set_5B)`:

   * Load and validate
     `s2_realised_intensity_5B@seed, mf, scenario_id`.
   * Confirm:

     * `manifest_fingerprint == mf`, `parameter_hash == ph`, `seed == seed`, `scenario_id` as expected,
     * keys `(merchant_id, zone_representation[, channel_group], bucket_index)` match S1 domain shape.

4. **Load S3 configs & RNG policy**

   From `sealed_inputs_5B`:

   * Locate and validate:

     * **arrival/count config** (`arrival_count_config_5B` or equivalent),
     * **S3 RNG policy** (or shared `arrival_rng_policy_5B`).

   * Extract at least:

     * arrival law (`"poisson"`, `"nb"`, etc.),
     * how to derive distribution parameters from `(lambda_realised, bucket_duration, group/entity attributes)`,
     * clipping or special-case rules (e.g. `lambda_realised == 0 → N = 0`),
     * RNG stream ID and substream label for count draws,
     * expected “one event per draw” or other event structure,
     * how to map keys to counters.

If any of these validations fail, S3 MUST raise an S3 error and abort before any RNG is consumed.

---

### 6.3 Step 1 — Assemble count domain per scenario

For each `scenario_id = s ∈ scenario_set_5B`:

1. **Derive bucket set**

   * From `s1_time_grid_5B`:

     * collect ordered `H_s := {bucket_index}` for scenario `s`.
     * derive or read `bucket_duration_seconds(b)` per bucket.

2. **Derive entity set**

   * From `s1_grouping_5B`:

     * collect domain `E_s := {(merchant_id, zone_representation[, channel_group])}` for scenario `s`.

3. **Join with λ_realised**

   * From `s2_realised_intensity_5B` for `(seed, mf, s)`:

     * join on `(merchant_id, zone_representation[, channel_group], bucket_index)`.

   * Define S3’s domain for scenario `s`:

     ```text
     D_s := {
       (merchant_id, zone_representation[, channel_group], bucket_index)
       : row exists in s2_realised_intensity_5B for (seed, mf, s)
     }
     ```

   * For each element of `D_s`, retain:

     * `lambda_realised`,
     * `lambda_baseline` (if present),
     * `bucket_duration_seconds`,
     * optional `group_id` or other traits (if needed for params).

If, per the arrival config, some entities/buckets in S1 must have counts but are missing from S2, S3 MUST fail with a domain/alignment error rather than silently skipping or fabricating intensities.

---

### 6.4 Step 2 — Compute distribution parameters per bucket

For each `(s, key, b) ∈ D_s`, where:

* `key := (merchant_id, zone_representation[, channel_group])`,
* `b := bucket_index`,

S3 MUST deterministically compute the arrival-law parameters.

1. **Compute base mean**

   * Using `lambda_realised = λ_realised(key, b)` and bucket duration `Δ_b` (e.g. in seconds):

     ```text
     mu_base = f_mu(lambda_realised, Δ_b, config, [group_id, key traits])
     ```

     where `f_mu` is defined by the arrival-count config (e.g. `μ = λ_realised × Δ_b`).

2. **Apply any config-driven adjustments**

   * If the config defines adjustments (e.g. scaling by entity traits, floors or caps), apply them deterministically:

     * Example: `mu = min(mu_base, mu_max)`,
     * Example: if `lambda_realised == 0`, enforce `mu = 0`.

3. **Derive full distribution parameters**

   * For Poisson:

     * `theta = { mu }`.

   * For NB or other laws:

     * derive additional parameters, e.g.
       `theta = { mu, r, p }` using config and optional group/entity-specific hyper-parameters.

All of this is purely deterministic, no RNG yet.

If the config leads to invalid parameters (e.g. negative μ, NB `p` not in (0,1)), S3 MUST treat this as a configuration error and abort.

---

### 6.5 Step 3 — Sample counts with Philox RNG

S3 now samples integer counts `N` using the arrival law and Philox.

1. **RNG stream and event family**

   From the S3 RNG policy, S3 obtains:

   * `stream_id` for count draws (e.g. `"arrival_counts"`),
   * `substream_label` for the count event family (e.g. `"bucket_count"`),
   * a mapping from `(scenario_id, key, bucket_index)` to:

     * an initial counter or an offset,
     * or a specified emitting order that implies a deterministic counter sequence.

2. **Per-domain-element draw**

   For each `(s, key, b) ∈ D_s` in deterministic order (e.g. sorted by `scenario_id, merchant_id, zone_representation[, channel_group], bucket_index`):

   * Retrieve the distribution parameters `theta` computed in Step 2.

   * Use Philox to obtain the required `U(0,1)` random values according to the arrival law, for example:

     * Poisson: inversion or PTRS algorithm, with known upper bounds for number of uniforms,
     * NB: via gamma–Poisson mixture or direct algorithm, again with known draw patterns.

   * Using these uniforms, compute an integer count:

     ```text
     N = sample_count(theta, uniforms, arrival_count_config)
     ```

   * Emit an RNG event for this draw (or one event for a fixed batch of draws, if the policy says so), for example:

     * `module = "5B.S3"`
     * `substream_label = "bucket_count"`
     * fields: `manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`, `scenario_id`, `merchant_id`, `zone_representation[, channel_group]`, `bucket_index`
     * `rng_counter_before_{lo,hi}`, `rng_counter_after_{lo,hi}`,
     * `draws` = decimal string with the number of uniforms consumed,
     * `blocks` = number of Philox blocks used.

   * Immediately append a trace entry in the RNG trace log as per Layer-wide RNG rules.

3. **Determinism guarantee**

   * For fixed `(ph, mf, seed)` and fixed configs, the combination of:

     * event ordering,
     * stream choices and counter mapping,
     * arrival algorithms
       MUST ensure that re-running S3 produces identical sequences of uniforms and thus identical `N` per domain element.

---

### 6.6 Step 4 — Persist `s3_bucket_counts_5B`

Once counts have been sampled for all `(s, key, b) ∈ D_s` for all `scenario_id ∈ scenario_set_5B`:

1. **Build rows**

   For each `(s, key, b)`:

   * Construct a row with:

     * `manifest_fingerprint = mf`
     * `parameter_hash = ph`
     * `seed`
     * `scenario_id = s`
     * `merchant_id`, `zone_representation[, channel_group]`
     * `bucket_index = b`
     * `lambda_realised` (or reference to it)
     * `bucket_duration_seconds`
     * arrival-law parameters (`mu`, and `nb_r`/`nb_p` if applicable)
     * `count_N = N`

2. **Write per `(seed, mf, scenario_id)`**

   * For each scenario `s`, write a Parquet file:

     ```text
     data/layer2/5B/s3_bucket_counts/
       seed={seed}/manifest_fingerprint={mf}/scenario_id={s}/
       s3_bucket_counts_5B.parquet
     ```

   * Enforce:

     * schema = `schemas.5B.yaml#/model/s3_bucket_counts_5B`,
     * partition keys `[seed, manifest_fingerprint, scenario_id]`,
     * writer sort order = `(scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)`.

3. **Idempotency & conflict handling**

   * Writes MUST be atomic at file level (temp path + rename).
   * If a file already exists for `(seed, mf, scenario_id)`:

     * either validate that its content is byte-identical to what S3 would write (idempotent re-run), or
     * raise `5B.S3.IO_WRITE_CONFLICT` and do not overwrite.

---

### 6.7 RNG invariants & prohibited actions

Throughout S3:

1. **RNG invariants**

   * The total number of count RNG events and draws MUST match the expectations from the RNG policy (e.g. one event per domain element, or whatever pattern is defined).
   * For each `(scenario_id, key, b)`:

     * the RNG event(s) and trace entry MUST be present,
     * counters MUST be monotonically increasing within the stream and not overlap across draws when the policy forbids it.

2. **No additional RNG usage**

   * S3 MUST NOT consume Philox for any other purpose (no ad-hoc randomness or hidden draws) beyond the count draws defined here.

3. **No upstream/output tampering**

   * S3 MUST NOT write to or modify:

     * S1 outputs,
     * S2 outputs,
     * upstream validation bundles or flags,
     * upstream sealed-input manifests.

If any of these invariants cannot be met or verified, S3 MUST surface an appropriate `5B.S3.*` error rather than silently proceeding.

Within these constraints, this algorithm completely specifies the RNG-bearing behaviour of **5B.S3 — Bucket-level arrival counts**: it takes `λ_realised` on a fixed grid, computes law parameters, draws counts per bucket with Philox, and writes a canonical bucket-count surface for S4 to consume.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how 5B.S3’s dataset is keyed, partitioned, ordered and updated**. It is binding on implementations, catalogue entries, and all downstream 5B states.

S3 produces one data-plane dataset:

* `s3_bucket_counts_5B` — bucket-level counts per entity×bucket×scenario×seed.

---

### 7.1 Identity scopes

There are three scopes to keep distinct:

1. **World identity**

   * `world_id := (parameter_hash, manifest_fingerprint) = (ph, mf)`
   * Fixed by S0; determines the sealed world, S1 grid/domain, and S2 intensities.

2. **Stochastic identity**

   * `stochastic_id := (ph, mf, seed)`
   * For a given world and seed, S3’s counts and RNG logs MUST be deterministic.

3. **Scenario identity**

   * `scenario_id ∈ scenario_set_5B`
   * Specifies which S1 grid and S2 λ slice the counts refer to.

**Binding rule:**
For fixed `(ph, mf, seed, scenario_id)` and fixed configs/inputs, `s3_bucket_counts_5B` MUST be **byte-identical** across S3 re-runs, regardless of `run_id`.

`run_id` is used for logging and RNG trace correlation only; it MUST NOT affect S3’s dataset identity.

---

### 7.2 Partitioning & path law

`s3_bucket_counts_5B` uses the same partitioning pattern as S2 outputs:

* **Partition keys:**
  `seed`, `manifest_fingerprint`, `scenario_id`

* **Path tokens:**

  ```text
  seed={seed}
  manifest_fingerprint={manifest_fingerprint}
  scenario_id={scenario_id}
  ```

Canonical path:

```text
data/layer2/5B/s3_bucket_counts/
  seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/
  s3_bucket_counts_5B.parquet
```

**Path ↔ embed equality (binding):**

For every row in a given file:

* `manifest_fingerprint` column MUST equal `{manifest_fingerprint}` from the path.
* `parameter_hash` column MUST equal `ph` for this world.
* `seed` column MUST equal `{seed}` from the path.
* `scenario_id` column MUST equal `{scenario_id}` from the path.

S3 MUST NOT mix rows for different seeds, manifests, or scenarios in the same file.

---

### 7.3 Primary key & writer ordering

**Logical primary key:**

```text
(manifest_fingerprint,
 parameter_hash,
 seed,
 scenario_id,
 merchant_id,
 zone_representation[, channel_group],
 bucket_index)
```

This combination MUST be unique across all rows.

**Writer sort order (within each file):**

For each `(seed, mf, scenario_id)` partition, S3 MUST write rows sorted lexicographically by:

```text
scenario_id,
merchant_id,
zone_representation[, channel_group],
bucket_index
```

This deterministic ordering is required so that:

* file-level hashes are reproducible, and
* diffs across seeds or between runs are stable and interpretable.

---

### 7.4 Merge & overwrite discipline

For each fixed quadruple `(ph, mf, seed, scenario_id)`:

* There MUST be **at most one** `s3_bucket_counts_5B` file at the canonical path.
* That file MUST cover the entire count domain `D_s` (every `(merchant, zone[, channel], bucket_index)` with λ_realised from S2).

**Idempotent re-runs:**

* Re-running S3 with the same `(ph, mf, seed, scenario_id)` and unchanged inputs/configs MUST either:

  * not attempt to write a new file, or
  * write a file that is **byte-identical** to the existing one.

If S3 finds an existing file for `(ph, mf, seed, scenario_id)` whose content would differ from what it would now produce, it MUST:

* treat this as an `IO_WRITE_CONFLICT` (or equivalent) error, and
* MUST NOT overwrite or merge the content.

**No cross-world or cross-seed merges:**

* Files for different `manifest_fingerprint` values MUST reside under different `manifest_fingerprint=…` directories and MUST NOT be combined.
* Files for different `seed` values MUST reside under different `seed=…` partitions and MUST NOT be combined into a single dataset by S3.

Aggregation across seeds or manifests (e.g. for analysis) is an external concern, outside S3.

---

### 7.5 Downstream consumption discipline

Downstream states (S4 and the final 5B validation state) MUST:

1. **Select `(ph, mf, seed, scenario_id)` explicitly**

   * To use bucket counts, S4 MUST:

     * choose a specific `(ph, mf, seed, scenario_id)`,
     * read exactly the `s3_bucket_counts_5B` file at the canonical path for that tuple, and
     * validate it against its schema and PK uniqueness.

   * S4 MUST NOT:

     * synthesise counts by mixing files from different seeds or manifests, or
     * infer counts by re-running S3 logic internally.

2. **Treat S3 counts as canonical**

   * S4 MUST treat `count_N` from `s3_bucket_counts_5B` as the **only** authority on how many arrivals occurred per entity×bucket×scenario×seed.
   * It MUST NOT:

     * re-sample counts,
     * change `count_N` in place,
     * generate its own counts from λ_realised.

3. **Not modify S3 outputs**

   * No downstream state may overwrite, append to, or delete rows from `s3_bucket_counts_5B`.
   * Any change to the arrival law or count semantics that would change `count_N` for a given `(ph, mf, seed)` must be expressed via:

     * a new `parameter_hash` and/or 5B spec version, and
     * fresh S0/S1/S2/S3 runs for that world.

Within these rules, S3’s output has a clear, stable identity and merge discipline: **one world, one seed, one scenario → one canonical bucket-count table**, ready for S4 to expand into timestamped, routed arrivals.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 5B.S3 — Bucket-level arrival counts is considered PASS** and what that implies for downstream 5B states (S4 + final validation) and orchestration. If any criterion fails, S3 MUST be treated as **FAIL** for `(parameter_hash, manifest_fingerprint, seed)` and its outputs MUST NOT be used.

---

### 8.1 Local PASS criteria for 5B.S3

For a fixed `(ph, mf, seed, scenario_set_5B)`, S3 is **PASS** iff **all** of the following hold:

1. **S0 / S1 / S2 prerequisites satisfied**

   * `s0_gate_receipt_5B@mf` and `sealed_inputs_5B@mf`:

     * exist,
     * validate against their schemas, and
     * carry `parameter_hash = ph`, `manifest_fingerprint = mf`, `sealed_inputs_digest` consistent with the actual `sealed_inputs_5B`.
   * `upstream_segments[seg].status == "PASS"` for all required segments `{1A,1B,2A,2B,3A,3B,5A}`.
   * For every `scenario_id ∈ scenario_set_5B`:

     * `s1_time_grid_5B` and `s1_grouping_5B` exist and validate against their schemas,
     * `s2_realised_intensity_5B` exists for `(seed, mf, scenario_id)` and validates against its schema.

2. **Configuration & RNG policy resolved**

   * Arrival/count config and S3 RNG policy:

     * are present in `sealed_inputs_5B` with `status ∈ {REQUIRED, INTERNAL}`,
     * validate against their schemas,
     * provide all required fields (arrival law, parameter mapping, clipping/guardrails, stream IDs, substream labels, expected draws/blocks per event, mapping from keys to counters).

3. **Domain coverage**

   For each `scenario_id`:

   * S3 derives a domain `D_s` comprising all `(merchant_id, zone_representation[, channel_group], bucket_index)` that:

     * appear in `s2_realised_intensity_5B` for `(seed, mf, scenario_id)`, and
     * correspond to valid buckets in `s1_time_grid_5B` for that scenario.
   * `s3_bucket_counts_5B@seed, mf, scenario_id` exists and:

     * passes schema validation,
     * contains **exactly one** row for each element of `D_s`,
     * contains **no rows** outside `D_s`.

4. **Key uniqueness & identity consistency**

   * In each `(seed, mf, scenario_id)` S3 output file:

     * the logical PK `(manifest_fingerprint, parameter_hash, seed, scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)` is unique,
     * `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id` columns match the partition and run context.

5. **Distribution parameter correctness**

   For each row:

   * Distribution parameters are finite and respect the arrival-law config:

     * e.g. for Poisson, `mu ≥ 0`;
     * for NB, `mu ≥ 0`, `nb_r > 0`, `0 < nb_p < 1`, etc.
   * Parameter derivation from `(lambda_realised, bucket_duration_seconds, group/entity traits)` follows the configured mapping; no “out-of-contract” values are produced.

6. **Count validity**

   For each row:

   * `count_N` is a finite integer with `count_N ≥ 0`.
   * Any special rules from config are respected, e.g.:

     * if `lambda_realised == 0`, then `count_N == 0` (if this is mandated),
     * no draws are attempted where the config says not to (e.g. forbidden μ).

7. **RNG accounting invariants**

   * For each `(scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)` in `D_s`:

     * the expected RNG event(s) for the count draw exist in the event log,
     * each event’s envelope (counters, draws, blocks) obeys the RNG policy and global RNG law,
     * there is exactly one trace entry per event append.
   * At aggregate level:

     * total count RNG events, total `draws`, and total `blocks` reconcile with:

       * the size of `D_s`, and
       * the arrival algorithms used.

If all of the above hold for all `scenario_id ∈ scenario_set_5B`, S3 is **locally PASS** for `(ph, mf, seed)`.

---

### 8.2 Local FAIL conditions

5B.S3 MUST be considered **FAIL** if **any** of the following occurs:

1. **S0 / S1 / S2 preconditions fail**

   * S0 outputs invalid or inconsistent,
   * any required upstream segment not PASS,
   * S1 or S2 outputs missing or invalid for any `scenario_id` in scope.

2. **Config / RNG policy issues**

   * Arrival/count config or S3 RNG policy is missing, cannot be resolved, or fails schema validation.
   * Required parameters (arrival law, parameter mapping, stream IDs) are missing or invalid.

3. **Domain or alignment errors**

   * Cannot align λ_realised domain with S1 grid/grouping for any scenario, e.g.:

     * S2 has λ_realised for an entity×bucket not present in S1, or
     * S1 domain requires counts for entities/buckets that have no λ_realised when config says they must.

4. **Bucket-count dataset errors**

   * `s3_bucket_counts_5B`:

     * fails schema validation,
     * has missing rows for some domain elements `D_s`,
     * has duplicates for the logical PK,
     * mixes multiple seeds/manifests/scenarios in a single partition.

5. **Numeric issues**

   * Derived distribution parameters are invalid (negatives where forbidden, probabilities out of range).
   * Any `count_N` is NaN, Inf, or negative, or violates hard constraints defined in count config.

6. **RNG accounting / determinism issues**

   * Count RNG events do not match the expected pattern (wrong number of events, wrong draws/blocks, missing trace entries).
   * Replay or verification detects that repeated runs for the same `(ph, mf, seed)` do not produce identical counts or RNG logs.

7. **IO / idempotency issues**

   * Writes of `s3_bucket_counts_5B` fail (I/O errors, partial writes), or
   * Existing S3 outputs for `(ph, mf, seed, scenario_id)` differ byte-for-byte from what S3 would now produce for the same world/config (idempotency violation), and S3 attempts to overwrite rather than error.

On any such condition, S3 MUST raise an appropriate `5B.S3.*` error and treat the run as FAIL.

---

### 8.3 Gating obligations for 5B.S3 itself

Before declaring PASS, S3 MUST ensure:

1. **All-or-nothing per `(ph, mf, seed)`**

   * For a given world & seed, S3 MUST either:

     * successfully produce a valid `s3_bucket_counts_5B` for **every** `scenario_id ∈ scenario_set_5B`, or
     * treat the entire S3 run as FAIL for that `(ph, mf, seed)`.

   No “partial scenario” success is allowed.

2. **No counts without valid S2**

   * S3 MUST NOT draw counts for any `(scenario_id)` lacking a valid `s2_realised_intensity_5B` for `(ph, mf, seed)`.

3. **No RNG before preconditions**

   * S3 MUST NOT call Philox or emit RNG events until all preconditions in §§2–3 are verified.

---

### 8.4 Gating obligations for downstream 5B states (S4 + final validation)

All later 5B states MUST treat S3 as a **hard gate**:

1. **Presence & schema checks**

   * Before using counts, S4 MUST:

     * verify that `s3_bucket_counts_5B` exists for each `(ph, mf, seed, scenario_id)` it intends to process,
     * validate it against `schemas.5B.yaml#/model/s3_bucket_counts_5B`.

2. **Treat counts as canonical**

   * S4 MUST:

     * use `count_N` from `s3_bucket_counts_5B` as the **only** count for entity×bucket×scenario×seed,
     * not resample counts or apply its own arrival law.

3. **No modification of S3 outputs**

   * No downstream state may overwrite or append to `s3_bucket_counts_5B`.
   * Any change to count behaviour that alters N distributions for a world MUST be introduced via config/spec changes → new `parameter_hash` and fresh S2–S3 runs.

4. **Validation state obligations**

   * The final 5B validation/HashGate state MUST:

     * treat S3 counts and RNG logs as inputs to its statistical checks (e.g. Fano corridors, mean vs λ_realised consistency),
     * fail the segment-level PASS if S3’s local invariants are not met.

---

### 8.5 Orchestration-level obligations

Pipeline orchestration MUST:

* not invoke S4 or final 5B validation for a given `(ph, mf, seed)` unless S3 has locally PASSed, or at least:

  * `s3_bucket_counts_5B` exists and is schema-valid,
  * S3’s run-report for that `(ph, mf, seed)` says `status = "PASS"`.

If S3 reports `status = "FAIL"` or any `5B.S3.*` error:

* that `{ph, mf, seed}` is not considered to have valid counts, and
* S4 MUST NOT attempt to create arrivals based on that seed/world.

Under these acceptance and gating rules, **5B.S3** cleanly owns the transition from intensities to counts: everything downstream either uses S3’s counts exactly as written or does not run at all.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only failure modes** that **5B.S3 — Bucket-level arrival counts** may surface and the **canonical error codes** it MUST use.

All S3 error codes are namespaced:

> **`5B.S3.<CATEGORY>`**

Any such error is **fatal** for S3 on `(parameter_hash, manifest_fingerprint, seed)`: its outputs MUST NOT be used by downstream states.

---

### 9.1 Error code catalogue

#### (A) S0 / S1 / S2 prerequisites

1. **`5B.S3.S0_GATE_INVALID`**
   Raised when S3 cannot establish a valid S0 context for `mf`, e.g.:

   * `s0_gate_receipt_5B` or `sealed_inputs_5B` missing or schema-invalid,
   * `parameter_hash` or `manifest_fingerprint` mismatch,
   * `sealed_inputs_digest` mismatch vs recomputed digest.

2. **`5B.S3.UPSTREAM_NOT_PASS`**
   Raised when `s0_gate_receipt_5B.upstream_segments` reports any required upstream segment `{1A,1B,2A,2B,3A,3B,5A}` with `status ≠ "PASS"`.

3. **`5B.S3.S1_OUTPUT_MISSING`**
   Raised when, for any `scenario_id ∈ scenario_set_5B`:

   * `s1_time_grid_5B` or `s1_grouping_5B` is missing or fails schema validation.

4. **`5B.S3.S2_OUTPUT_MISSING`**
   Raised when, for any `scenario_id ∈ scenario_set_5B` and this `seed`:

   * `s2_realised_intensity_5B` is missing, cannot be resolved via catalogue, or fails schema validation.

---

#### (B) Config / RNG policy issues

5. **`5B.S3.COUNT_CONFIG_MISSING`**
   Raised when the arrival/count config (e.g. `arrival_count_config_5B`) is:

   * not present in `sealed_inputs_5B` for this `mf`, or
   * not resolvable via catalogue.

6. **`5B.S3.COUNT_CONFIG_INVALID`**
   Raised when the arrival/count config:

   * fails schema validation, or
   * lacks required fields (arrival law, parameter mapping, clipping/guardrails).

7. **`5B.S3.RNG_POLICY_INVALID`**
   Raised when the S3 RNG policy:

   * is missing from `sealed_inputs_5B`, or
   * fails schema validation, or
   * does not define the required stream IDs, substream labels, or draw/block expectations for count draws.

---

#### (C) Domain & alignment

8. **`5B.S3.DOMAIN_ALIGN_FAILED`**
   Raised when S3 cannot form a consistent count domain `D_s` for one or more scenarios, e.g.:

   * λ_realised rows in `s2_realised_intensity_5B` cannot be joined to S1 grid/grouping by keys,
   * S1 domain requires counts for entity×bucket combinations with no λ_realised, contrary to config expectations.

9. **`5B.S3.BUCKET_SET_INCONSISTENT`**
   Raised when the bucket set implied by S1 and the λ_realised surface disagree in a way that breaks S3, e.g.:

   * λ_realised is defined for bucket indices that do not exist in `s1_time_grid_5B`,
   * or vice versa, where config requires full coverage.

---

#### (D) Count parameter / sampling issues

10. **`5B.S3.PARAM_DERIVATION_INVALID`**
    Raised when S3 cannot derive valid arrival-law parameters for some domain element, e.g.:

* computed `mu < 0`,
* NB parameters out of range (`r ≤ 0`, `p ≤ 0` or `p ≥ 1`),
* other law-specific parameter violations.

11. **`5B.S3.COUNT_SAMPLING_ERROR`**
    Raised when the sampling algorithm fails for some draw, e.g.:

* numeric failure in Poisson/NB sampler,
* internal overflow/underflow not handled by configured guardrails.

---

#### (E) Bucket-count dataset errors

12. **`5B.S3.COUNTS_SCHEMA_INVALID`**
    Raised when the written `s3_bucket_counts_5B` file for any `(seed, mf, scenario_id)`:

* fails validation against `schemas.5B.yaml#/model/s3_bucket_counts_5B`,
* is missing required columns or has wrong types/enums.

13. **`5B.S3.COUNTS_DOMAIN_INCOMPLETE`**
    Raised when, for any scenario:

* some domain elements in `D_s` (entity×bucket combinations derived from S2+S1) have no corresponding row in `s3_bucket_counts_5B`.

14. **`5B.S3.COUNTS_DUPLICATE_KEY`**
    Raised when `s3_bucket_counts_5B` contains duplicate logical keys:

```text
(manifest_fingerprint, parameter_hash, seed,
 scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)
```

---

#### (F) Numeric validity

15. **`5B.S3.COUNTS_NUMERIC_INVALID`**
    Raised when any row in `s3_bucket_counts_5B` has:

* `count_N` NaN or Inf,
* `count_N < 0`,
* or numerical values (`lambda_realised`, μ, law parameters) violating hard constraints from the arrival config (e.g. μ not finite).

---

#### (G) RNG accounting & determinism

16. **`5B.S3.RNG_ACCOUNTING_MISMATCH`**
    Raised when count RNG usage does not match policy, e.g.:

* wrong number of RNG events for the domain size,
* `draws` or `blocks` values inconsistent with the arrival algorithms,
* RNG trace log does not reconcile with event log (missing trace entries, overlapping counters).

17. **`5B.S3.NON_DETERMINISTIC_OUTPUT`**
    Raised when a repeat run for the same `(ph, mf, seed)` and inputs produces different counts or RNG logs (as detected by a higher-level consistency check).

---

#### (H) IO / idempotency

18. **`5B.S3.IO_WRITE_FAILED`**
    Raised when S3 cannot atomically write `s3_bucket_counts_5B` (filesystem error, permission error, partial write).

19. **`5B.S3.IO_WRITE_CONFLICT`**
    Raised when S3 detects an existing `s3_bucket_counts_5B` for `(ph, mf, seed, scenario_id)` whose contents are **not** byte-identical to what S3 would produce for the same inputs/configs.

In this case S3 MUST NOT overwrite and MUST signal this error.

---

### 9.2 Error payload & logging

For any `5B.S3.*` error, S3 MUST log/include at least:

* `error_code` (exact string),
* `parameter_hash`, `manifest_fingerprint`, `seed`,
* `scenario_id` if scenario-specific,
* and where relevant:

  * offending `segment_id` (for S0/S1/S2 issues),
  * offending `merchant_id`, `zone_representation`, `bucket_index` for count/domain errors.

Textual messages may vary, but orchestration and downstream logic MUST key on `error_code`.

---

### 9.3 Behaviour on failure

On any S3 error:

1. **Abort before downstream work**

   * S3 MUST NOT treat the run as PASS or allow S4 to use counts for this `(ph, mf, seed)`.
   * No partial “scenario-level success” is allowed to be advertised as global S3 PASS.

2. **Filesystem state**

   * S3 SHOULD avoid leaving partially written files.
   * If a partial file exists, a subsequent S3 run MUST either:

     * repair by writing a complete, consistent file, or
     * fail again with `IO_WRITE_CONFLICT` / `IO_WRITE_FAILED`, and S4 MUST NOT run.

3. **No upstream/S1/S2 repair**

   * S3 MUST NOT attempt to modify upstream bundles, S0/S1/S2 outputs, or upstream sealed-inputs in response to any S3 error; those issues must be fixed at the appropriate upstream state or configuration.

Under this error model, any `5B.S3.*` error means there is **no valid bucket-count surface** for that world/seed, and S4 is not allowed to proceed until the cause is fixed and S3 is successfully re-run.

---

## 10. Observability & run-report integration *(Binding)*

This section fixes **what 5B.S3 MUST report** and **how it integrates with the engine’s run-report system**. It does not define new datasets; it constrains how S3 describes its work.

---

### 10.1 Run-report record for 5B.S3

For every attempted invocation of S3 on
`(parameter_hash = ph, manifest_fingerprint = mf, seed, run_id)`,
the engine MUST emit **one** run-report record with at least:

* `state_id = "5B.S3"`
* `parameter_hash = ph`
* `manifest_fingerprint = mf`
* `seed`
* `run_id`
* `scenario_set = sorted(scenario_set_5B)`
* `status ∈ {"PASS","FAIL"}`
* `error_code` (one of `5B.S3.*`, or `null` if `status = "PASS"`)
* `started_at_utc`
* `finished_at_utc`

Where this is stored (shared Layer-2 run-report, per-segment table, etc.) is implementation-defined, but S3 MUST provide these fields.

---

### 10.2 Required structural metrics

For each S3 run (PASS or FAIL), the run-report record MUST include at least:

1. **Scenario coverage**

   * `scenario_count_requested = |scenario_set_5B|`
   * `scenario_count_succeeded`

     * number of scenarios for which S3 successfully materialised and validated `s3_bucket_counts_5B`.
   * `scenario_count_failed = scenario_count_requested - scenario_count_succeeded`

   For `status = "PASS"`, S3 MUST have `scenario_count_succeeded == scenario_count_requested`.

2. **Domain size**

   Derived from S2+S1 for the scenarios S3 actually processed:

   * `total_entity_bucket_domain = Σ_scenario |D_s|`
     where `D_s` is the entity×bucket domain S3 drew counts for.

3. **Counts scale**

   From `s3_bucket_counts_5B` (for PASS runs):

   * `total_count_rows` (row count in `s3_bucket_counts_5B` over all scenarios)
   * `sum_count_N` (sum of `count_N` over all rows)
   * Optionally, per-scenario summaries:

     * `count_rows_min / max / mean` across scenarios
     * `sum_count_N_min / max / mean` across scenarios.

4. **RNG usage**

   From S3’s RNG event/trace logs:

   * `count_rng_event_count`

     * total number of RNG events emitted for count draws.
   * `count_rng_total_draws`

     * total number of `U(0,1)` draws consumed by count RNG events (sum of `draws` across events).
   * `count_rng_total_blocks`

     * total number of Philox blocks consumed.

On `status = "PASS"`, these metrics MUST be consistent with:

* the size of `s3_bucket_counts_5B`, and
* the RNG policy’s expectations.

On `status = "FAIL"`, metrics MAY be partial but MUST not exaggerate what was actually attempted.

---

### 10.3 Optional statistical summaries

For **PASS** runs, S3 SHOULD compute and include basic summaries of its output (for debugging / sanity checks):

1. **Counts vs means**

   Over all rows in `s3_bucket_counts_5B` (or by scenario):

   * `mu_min`, `mu_max`, `mu_mean`
   * `count_N_min`, `count_N_max`, `count_N_mean`

2. **Fano-related hints (if configured)**

   If the arrival config or validation policy defines Fano corridors, S3 MAY include:

   * simple aggregate Fano statistics (e.g. variance of `count_N` vs mean `μ` at some aggregation level), or
   * counts of buckets falling into bands (e.g. `"FANO_LOW"`, `"FANO_WITHIN"`, `"FANO_HIGH"`), if S3 is configured to compute those locally.

These stats SHOULD appear in a structured `details` / `payload` field in the run-report, not as separate datasets.

---

### 10.4 Error reporting integration

On any `status = "FAIL"` with a `5B.S3.*` error (see §9):

* The run-report record MUST include:

  * `error_code`, and
  * minimal context in the payload, e.g.:

    * offending `scenario_id`,
    * offending `merchant_id`, `zone_representation`, `bucket_index` (for domain or numeric errors),
    * name of missing/misconfigured artefact (for config/RNG-policy issues).

S3 MUST NOT mark any scenario as “succeeded” in metrics if its counts or RNG invariants failed.

Downstream tooling and orchestration MUST key off `status` and `error_code`, not free-text messages.

---

### 10.5 Relationship to downstream gating

Downstream S4 and the final 5B validation state MUST use S3’s run-report together with schema checks to decide whether they may run:

* If `status != "PASS"` or `error_code != null`, orchestration MUST treat S3 as failed for `(ph, mf, seed)` and MUST NOT invoke S4 for that world/seed.
* If `status = "PASS"`, S4 MUST still:

  * verify the existence and schema validity of `s3_bucket_counts_5B` for all required scenarios,
  * honour S3’s identity and partitioning rules.

Run-report is **not** a substitute for dataset-level validation.

---

### 10.6 Data-plane logging constraints

Because `s3_bucket_counts_5B` can be large, S3:

* MUST NOT log arbitrary sample rows of the counts dataset into the run-report or general logs by default.
* MAY, if explicitly configured for debugging, include tiny samples or anonymised examples, but this is optional and must be bounded.

Detailed statistical validation of counts vs λ_realised (beyond light summaries) belongs to:

* the dedicated 5B validation / HashGate state, or
* offline analysis tools that read S2/S3 outputs directly.

Within these constraints, 5B.S3’s observability obligation is to:

> Clearly report whether counts were successfully realised for a world+seed, how large the domain was, how many RNG draws were consumed, and (optionally) basic count vs mean summaries — so that S4 and validation can safely decide whether to proceed.

---

## 11. Performance & scalability *(Informative)*

This section is descriptive, not normative. It explains how **5B.S3 — Bucket-level arrival counts** is expected to behave at scale and what levers exist to keep it tractable.

---

### 11.1 Workload shape

S3’s work is conceptually simple:

* For each scenario `s` and seed, it operates over the **domain**:

  ```text
  D_s = { (merchant_id, zone_representation[, channel_group], bucket_index) }
  ```

  where `λ_realised` is defined (from S2) and `bucket_index` is in the S1 grid.

* For every element of `D_s`, S3:

  * computes distribution parameters (e.g. Poisson μ or NB parameters),
  * performs a single random draw to get `count_N`.

So time complexity is roughly:

```text
O( Σ_scenario |D_s| )
```

and scales linearly with the number of entity×bucket combinations.

---

### 11.2 Time complexity

Per domain element, S3 does:

* **A small amount of deterministic arithmetic**

  * parameter calculation from `lambda_realised` and bucket duration,
  * simple clipping/bounds checks.

* **A constant-cost RNG draw**

  * Poisson / NB samplers are O(1) amortised for reasonable parameter ranges, using standard algorithms (inversion for small μ, PTRS or similar for larger μ, gamma–Poisson for NB, etc.).

As a result:

* Overall runtime is dominated by:

  * iterating through `D_s`,
  * serialising `s3_bucket_counts_5B`,
  * and RNG overhead (which is also O(|D_s|)).

If `λ_realised` is dense (e.g. most entities active in most buckets), S3 cost will scale with the product:

```text
#merchants × #zones_per_merchant × #buckets_per_scenario × #scenarios
```

---

### 11.3 Memory & I/O profile

**Memory:**

* S3 can process per scenario (or even per chunk of entities within a scenario):

  * read `s2_realised_intensity_5B` and S1 slices,
  * compute counts,
  * stream out `s3_bucket_counts_5B` for that scenario.

* Peak memory is thus bounded by:

  * the largest subset of `D_s` held in memory at once (which can be controlled by chunking), plus
  * the workspace needed by the RNG/count samplers (small).

**I/O:**

* Reads:

  * S2 intensities (potentially large table per `(seed, mf, scenario_id)`),
  * S1 grid & grouping (moderate),
  * configs (tiny).

* Writes:

  * exactly one `s3_bucket_counts_5B` file per `(seed, mf, scenario_id)`.

If needed, S3 can be implemented as a streaming transform:

* read λ_realised in sorted order,
* compute counts row-by-row,
* write out immediately in the same sort order.

---

### 11.4 Concurrency & scheduling

S3 is highly parallelisable along several axes:

* **Across seeds**

  * Different seeds are fully independent; each `(ph, mf, seed)` can be processed in parallel.

* **Across scenarios**

  * For a given `(ph, mf, seed)`, each `scenario_id` can be handled independently in its own job or task, as long as:

    * the correct partition paths are used, and
    * identity/idempotency rules are respected.

* **Within scenarios**

  * Work can be chunked by subsets of `D_s` (e.g. by merchant ranges) to exploit multi-core CPUs, provided:

    * RNG stream/counter allocation is deterministic across chunks, and
    * the final output still respects the required sort order.

A simple and safe scheduling strategy is:

* treat `(ph, mf, seed, scenario_id)` as an atomic unit for S3 writes,
* allow internal parallelism per unit if RNG and output ordering are carefully controlled.

---

### 11.5 Degradation & tuning levers

If S3 becomes a bottleneck, it is usually because `|D_s|` is large. The main tuning levers are **not** in S3 itself, but in upstream configuration:

* **Bucket granularity (via S1 / time_grid_policy_5B)**

  * Coarser buckets ⇒ fewer `bucket_index` values ⇒ smaller `|D_s|`.
  * Fine-grained buckets over long horizons can explode domain size.

* **Scenario set size (S0 / 5A scenario design)**

  * Fewer scenarios per run ⇒ proportionally fewer domain elements per seed.

* **Domain shaping (S1 grouping + 5A surfaces)**

  * You may choose to limit which merchants/zones are active in which scenarios or buckets (e.g. by making λ_target = 0 for dormant combinations) so `D_s` is sparser.

* **Distribution choice**

  * Poisson draws are typically cheaper than NB. If you only need NB-like dispersion in certain regions, you can restrict NB usage (per arrival config) to a subset of `D_s`.

At the S3 implementation level:

* exploit streaming and chunking to avoid large in-memory buffers,
* avoid expensive per-row overhead (e.g. redundant joins or complex conditionals in tight loops),
* ensure RNG draws are batched efficiently where possible, while preserving determinism.

In most realistic configurations, S3 will be **heavier** than S0/S1 but still manageable, and generally cheaper than any state that must handle full per-arrival events (S4) or complex kernel mathematics (S2).

---

## 12. Change control & compatibility *(Binding)*

This section defines **how 5B.S3 — Bucket-level arrival counts may evolve** and when a **spec/schema version bump** is required. It binds:

* the behaviour described for S3 in this state spec,
* the `schemas.5B.yaml` anchor for `s3_bucket_counts_5B`,
* the 5B dataset dictionary and artefact registry entries for S3, and
* downstream 5B states (S4 + final validation) that consume S3 outputs.

---

### 12.1 Version signalling

S3 does **not** have its own independent version; it inherits the **5B segment spec version** (e.g. `5B_spec_version`) announced by S0.

Binding requirements:

* `s0_gate_receipt_5B` MUST embed `segment_spec_version` (or equivalent).
* The dataset dictionary entry for `s3_bucket_counts_5B` MUST carry the same `segment_spec_version`.
* The 5B artefact registry entry for `mlr.5B.model.s3_bucket_counts` MUST also carry this version.

Downstream 5B states (S4, 5B validation) MUST:

* read `segment_spec_version` from S0/dictionary, and
* either explicitly support it, or fail fast (e.g. `5B.S4.UNSUPPORTED_SPEC_VERSION`) if they do not.

---

### 12.2 Backwards-compatible changes (allowed with minor 5B bump)

The following S3 changes are **backwards-compatible** and MAY be made under a **minor** 5B spec bump (e.g. `5B-1.0 → 5B-1.1`), provided schemas, dictionary and registry are updated consistently:

1. **Additive schema fields**

   * Adding new **optional** columns to `s3_bucket_counts_5B`, such as:

     * extra diagnostics (`count_clipped_flag`, `fano_band`, `group_id`, `config_version`),
     * additional arrival-law parameters that have clear defaults (e.g. optional NB parameters when Poisson is still valid).

   These MUST NOT change the meaning of existing fields (`lambda_realised`, `count_N`, `mu`, etc.).

2. **Additional diagnostics / metrics**

   * Using new optional columns in `s3_bucket_counts_5B` for:

     * per-bucket QA flags,
     * references to S2 latent fields (e.g. `lambda_random_component` echoed),
     * other purely diagnostic information.

   * Adding new run-report metrics or debug payload fields in S3’s observability (e.g. more detailed count/μ summaries).

3. **Config / policy extensions with safe defaults**

   * Extending the arrival/count config with new optional knobs (e.g. extra NB hyper-parameters, alternative law choices) that:

     * default to existing behaviour when unset, and
     * do not change semantics of current configurations.

4. **Implementation improvements under the same law**

   * Changing the internal algorithms for Poisson/NB sampling (e.g. switching to more stable or faster variants) as long as:

     * the law and parameterisation remain the same,
     * RNG accounting and determinism guarantees are preserved for given `(ph, mf, seed)`.

In all these cases, older S4/validation logic that only reads the original required fields can continue to operate correctly.

---

### 12.3 Breaking changes (require new major 5B spec)

The following S3 changes are **breaking** and MUST NOT be made under the same `segment_spec_version`. They require:

* a new **major** 5B spec version (e.g. `5B-1.x → 5B-2.0`), and
* explicit updates to S0/S1/S2/S3/S4 to handle the new semantics.

Breaking changes include (non-exhaustive):

1. **Changing arrival-law semantics or parameterisation**

   * Redefining what `mu` or `count_N` means:

     * e.g. switching from Poisson `N ~ Poisson(μ)` to a different distribution for all buckets without a version change.
   * Changing how `mu` is derived from `lambda_realised` and bucket duration (e.g. from “expected count in bucket” to “intensity at bucket midpoint”) in a way that affects counts.

2. **Changing the count law without clear config gating**

   * Introducing a new law (e.g. zero-inflated Poisson) and making it the default without leaving the previous behaviour accessible through config defaults.
   * Changing NB parameterisation (e.g. from `(r, p)` to `(mean, dispersion)` with different mapping) in a way that changes output for existing configs.

3. **Partitioning / identity changes**

   * Altering partition keys for `s3_bucket_counts_5B` (e.g. adding/removing `scenario_id` or `seed` from the partition) under the same version.
   * Changing logical PK semantics (e.g. allowing multiple rows per entity×bucket under the same `(seed, mf, scenario_id)`).

4. **Grid/domain source changes**

   * Making S3 use a different time grid than S1 (e.g. separate internal bucketing) without updating S1/S2/S4 and versioning accordingly.
   * Allowing S3 to count entities or buckets that are not in the S1+S2 domain under the same spec.

5. **RNG/event semantics changes**

   * Changing which events are emitted for count draws (e.g. event family names, stream IDs, draw/block semantics) in a way that breaks RNG accounting or replay.
   * Making counts depend on `run_id` rather than `(ph, mf, seed)`.

If any of these are required, S3 MUST be updated together with:

* a 5B spec major bump, and
* S4/validation specs updated to understand the new semantics.

---

### 12.4 Interaction with S0, S1, S2, S4

* **S0 (Gate & sealed inputs)**

  * Owns the sealed world and `5B_spec_version`.
  * Any change to S3 that alters:

    * input requirements, or
    * world identity assumptions (e.g. which artefacts must be present)
      must be reflected in S0’s spec and sealed-inputs logic.

* **S1 (Grid & grouping)**

  * Owns bucket structure & entity domain.
  * S3 MUST remain compatible with S1’s contracts; any change that uses a different grid or domain must be done in S1 and versioned across S1–S3 together.

* **S2 (Realised intensities)**

  * Owns `lambda_realised`.
  * S3 MUST continue treating `lambda_realised` as the sole intensity source for counts; any change to S3 that bypasses S2 requires a coordinated redesign and new spec.

* **S4 (Arrivals & routing)**

  * Consumes `count_N` and MUST treat S3 counts as canonical.
  * Any change to S3 that changes the meaning or domain of `count_N` (beyond configuration) requires S4 to update and gate on the new 5B spec version.

---

### 12.5 Migration principles

When evolving S3:

* Prefer **additive, backwards-compatible** changes:

  * new optional columns,
  * richer configs with safe defaults,
  * more detailed run-report metrics.

* Keep core contracts stable:

  * S1 defines **when** (buckets) and **where** (entity domain).
  * S2 defines **how intense** (λ_realised).
  * S3 defines **how many** (counts per bucket, via a well-specified arrival law).

* Avoid silent changes in distribution:

  * If a change affects the distribution of `count_N` relative to `lambda_realised` (for the same config), either:

    * treat it as a new config choice under the same spec, with old behaviour still available, or
    * bump the 5B spec version and update S4/validation to explicitly understand the new behaviour.

In short:

> Minor, additive evolution of S3 is allowed under a minor 5B spec bump.
> Any change that meaningfully alters count semantics, identity, or dependence on S1/S2 must be accompanied by a **major** 5B spec bump and explicit downstream support.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix just collects shorthand used in **5B.S3 — Bucket-level arrival counts**. It does **not** define new behaviour; the binding rules are in §§1–12.

---

### 13.1 Identities & sets

* **`ph`**
  Shorthand for `parameter_hash`. Identifies the parameter pack (including arrival/count config and RNG policy) for this world.

* **`mf`**
  Shorthand for `manifest_fingerprint`. Identifies the sealed world (artefact set) for this run.

* **`seed`**
  Philox seed for this stochastic realisation. Together with `(ph, mf)` it fixes the counts S3 generates.

* **`scenario_set_5B` / `sid_set`**
  The set of `scenario_id` values S0 bound 5B to for this `(ph, mf)`.

* **`world_id`**
  `(ph, mf)` — world identity (closed world sealed by S0).

* **`stochastic_id`**
  `(ph, mf, seed)` — identity of a particular count realisation in S2+S3.

* **`D_s`**
  For a scenario `s`, the domain of entity×bucket combinations over which S3 draws counts:

  ```text
  D_s = { (merchant_id, zone_representation[, channel_group], bucket_index) }
  ```

  as implied by S1 grid and S2’s `λ_realised`.

---

### 13.2 S3 dataset

* **`s3_bucket_counts_5B`**
  Required S3 output. Per `(world, seed, scenario)` it contains:

  * identity keys: `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`, `merchant_id`, `zone_representation[, channel_group]`, `bucket_index`
  * intensity/parameters: `lambda_realised`, `bucket_duration_seconds`, `mu`, (and any other law-specific parameters)
  * result: `count_N` — the realised bucket count.

---

### 13.3 Variables & parameters

* **`λ_realised` / `lambda_realised`**
  Realised intensity per entity×bucket (from S2). Used by S3 as the base intensity.

* **`Δ_b` / `bucket_duration_seconds`**
  Duration of bucket `b` in seconds (or another time unit defined in S1/time-grid policy).

* **`μ` / `mu`**
  Mean parameter for the arrival law in a bucket. For Poisson:

  ```text
  mu = lambda_realised × Δ_b
  ```

  (adjusted/clipped as defined by the count config).

* **`N` / `count_N`**
  Integer bucket count sampled by S3 for a given entity×bucket.

* **NB parameters (if used)**

  * `nb_r` — shape/dispersion parameter.
  * `nb_p` — success probability.
    Other parameterisations may be used but will be documented in the count config and schema.

---

### 13.4 RNG shorthand

* **`stream_id`**
  Philox stream assigned to S3 count draws (e.g. `"arrival_counts"`), defined in the RNG policy.

* **`substream_label`**
  Label for the RNG event family used for bucket counts (e.g. `"bucket_count"`).

* **`rng_counter_before_{lo,hi}` / `rng_counter_after_{lo,hi}`**
  64-bit halves of the Philox counter before/after a count-draw event, per the Layer-wide RNG envelope schema.

* **`draws`**
  Decimal string in each RNG event indicating how many uniforms were consumed for that draw (or batch of draws), per the RNG policy.

* **`blocks`**
  Number of Philox blocks consumed for that event.

S3 must respect the global RNG envelope semantics; these names appear in the prose but are defined by the Layer-wide RNG schema.

---

### 13.5 Error code prefix

All S3 error codes are prefixed:

> **`5B.S3.`**

Examples (see §9 for full definitions):

* `5B.S3.S0_GATE_INVALID`
* `5B.S3.S2_OUTPUT_MISSING`
* `5B.S3.COUNT_CONFIG_INVALID`
* `5B.S3.DOMAIN_ALIGN_FAILED`
* `5B.S3.COUNTS_SCHEMA_INVALID`
* `5B.S3.COUNTS_DOMAIN_INCOMPLETE`
* `5B.S3.RNG_ACCOUNTING_MISMATCH`
* `5B.S3.IO_WRITE_CONFLICT`

Downstream tooling should key on `error_code`, not free-text messages.

---

These symbols are purely for readability; the binding behaviour of **5B.S3 — Bucket-level arrival counts** is fully specified in §§1–12.

---
