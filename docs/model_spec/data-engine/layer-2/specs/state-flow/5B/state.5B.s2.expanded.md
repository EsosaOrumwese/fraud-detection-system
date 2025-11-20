# 5B.S2 — Latent intensity fields (Layer-2 / Segment 5B)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5B.S2 — Latent intensity fields (Layer-2 / Segment 5B)**. It is binding on any implementation of this state and on all downstream 5B states that consume its outputs.

---

### 1.1 Role of 5B.S2 in the engine

Given a closed world sealed by **5B.S0** and the planning outputs of **5B.S1**, **5B.S2** is the **latent-field / LGCP layer** for arrivals:

* It takes:

  * 5A’s **deterministic scenario intensity surfaces** `λ_target(m, zone[, channel], bucket)` on the S1 grid.
  * S1’s **time grid** (`s1_time_grid_5B`) and **grouping map** (`s1_grouping_5B`).
  * 5B’s **arrival-process / LGCP configuration** and **5B RNG policy** (as sealed by S0).

* It **introduces correlated stochastic variation** by:

  * sampling latent Gaussian (or equivalent) fields over the S1 bucket grid for each group, and
  * transforming those fields into multiplicative factors `ξ(group, bucket)` that modulate `λ_target`.

* It produces a **realised intensity surface**:

> `λ_realised(m, zone[, channel], bucket) = λ_target(m, …, bucket) × ξ(group(m,…), bucket)`

which S3 will then use as the mean structure for bucket-level count draws.

5B.S2 is **RNG-bearing** (Philox discipline, with explicit event/trace logging) but does **not** itself create counts, timestamps, or routed arrivals.

---

### 1.2 Objectives

5B.S2 MUST:

* **Respect upstream authorities**

  * Treat 5A’s scenario surfaces as the **only authority** for deterministic λ (`λ_target`).
  * Treat S1’s time grid and grouping map as the **only authority** for:

    * which `(scenario_id, bucket_index)` pairs exist,
    * which `(merchant, zone[, channel])` belong to which `group_id`.

* **Introduce correlated noise cleanly**

  * Apply a 5B-local LGCP/arrival-process config to build per-group, per-scenario latent fields over the S1 bucket grid.
  * Ensure the latent fields are:

    * sampled using Philox with well-defined event families and envelopes,
    * reproducible given `(parameter_hash, manifest_fingerprint, seed, run_id)`.

* **Produce a well-formed realised intensity surface**

  * Compute `λ_realised` for every `(scenario_id, merchant, zone[, channel], bucket)` where `λ_target` exists.
  * Ensure `λ_realised` satisfies the constraints defined by the arrival-process config (e.g. non-negative, finite, within any configured clipping bounds).
  * Optionally expose latent-field diagnostics (e.g. per-group Gaussian/log fields) for debugging and validation, without changing the binding meaning of `λ_realised`.

* **Stay focused on intensities**

  * Do **not** produce counts or arrivals; S2’s job stops at “intensity with correlated noise”.
  * Provide outputs that S3 can consume directly as the mean parameters for its bucket-level count draws.

---

### 1.3 In-scope behaviour

The following activities are **in scope** for 5B.S2 and MUST be handled by this state (not duplicated elsewhere in 5B):

* **Joining grid, grouping and λ_target**

  * Deterministically join:

    * `s1_time_grid_5B` (bucket structure),
    * `s1_grouping_5B` (entity→group assignment), and
    * 5A scenario intensity surfaces (`λ_target`)
      into a coherent domain for latent-field sampling and realised λ.

* **Latent-field construction**

  * For each `(scenario_id, group_id)`:

    * derive the bucket index set from `s1_time_grid_5B`,
    * construct the latent-field domain (e.g. covariance kernel, correlation structure) according to the LGCP/arrival config, and
    * sample latent values over that domain using Philox and the 5B RNG policy.

* **Mapping latent fields to merchants/zones**

  * Map group-level latent values to each `(merchant, zone[, channel])` via `s1_grouping_5B`, so that each entity/bucket gets a stochastic factor `ξ`.

* **Computing realised intensities**

  * Combine `λ_target` with `ξ` under the configured transformation (e.g. log-Gaussian, additive on log-scale then exponentiate) to produce `λ_realised` per entity/bucket.
  * Apply any necessary clipping or guardrails defined by config (e.g. cap at a multiple of λ_target or global max).

* **RNG event & trace emission**

  * Emit RNG events for latent-field draws, with:

    * clearly specified event families,
    * correct Philox counter usage,
    * matching trace entries as per Layer-wide RNG law.

* **Structural and numerical sanity checks (local)**

  * Check that:

    * every entity/bucket in domain has a latent value and a `λ_realised`,
    * no NaN/Inf values propagate to outputs,
    * any configured variance/correlation constraints are met at least structurally (detailed validation belongs to the final 5B validation state).

---

### 1.4 Out-of-scope behaviour

The following are explicitly **out of scope** for 5B.S2 and MUST NOT be performed by this state:

* **Bucket-level counts**

  * S2 MUST NOT draw counts `N` from `λ_realised`. That is the job of S3 (bucket-level arrival counts).

* **Intra-bucket time & routing**

  * S2 MUST NOT:

    * assign intra-bucket arrival times,
    * map arrivals to sites or virtual edges, or
    * touch routing/alias tables from 2B/3B.

  All of that belongs to S4.

* **Changing S1 grid or grouping**

  * S2 MUST NOT modify or reinterpret:

    * `s1_time_grid_5B` (bucket structure),
    * `s1_grouping_5B` (group assignments).

  If grouping or grid is unsuitable, the fix is to change S1 / config (often via a new `parameter_hash`), not to override in S2.

* **Changing deterministic λ_target**

  * S2 MUST NOT:

    * recompute `λ_target` from upstream priors/calendars, or
    * modify 5A’s deterministic surfaces in place.

  It only applies stochastic modulation on top.

* **Segment-level HashGate for 5B**

  * S2 does not decide the final 5B PASS verdict or build the segment’s validation bundle; that’s the responsibility of the terminal 5B validation state.

---

### 1.5 Downstream obligations

This specification imposes the following obligations on downstream 5B states:

* **S3 (bucket-level counts) MUST:**

  * treat S2’s `λ_realised` as the **only authority** for bucket-level mean parameters when drawing counts,
  * not resample or modify the latent fields or re-apply its own independent noise layer.

* **S4 (arrivals & routing) MUST:**

  * not change `λ_realised` or add additional intensity noise; it only uses counts from S3 and routes/places events in time.

* **No re-implementation of S2 logic**

  * No downstream state may re-implement LGCP/latent logic independently; if additional latent structure is ever required, it MUST be introduced as an extension of S2 (and reflected in this spec) rather than as ad-hoc per-state behaviour.

Within this scope, **5B.S2** is the **single, well-defined place** where correlated stochastic variation enters the intensity surface. Everything upstream defines the deterministic world and λ_target; everything downstream consumes `λ_realised` to generate counts and events, but cannot change how that variation is introduced.

---

## 2. Preconditions & dependencies *(Binding)*

This section defines **when 5B.S2 is allowed to run** and **what it may depend on**. If any precondition fails, S2 MUST NOT produce outputs and MUST be treated as FAIL for that `(parameter_hash, manifest_fingerprint)`.

---

### 2.1 Dependency on S0 (Gate & sealed inputs)

Before S2 may execute for a given `(parameter_hash = ph, manifest_fingerprint = mf)`:

1. **S0 outputs MUST exist and be valid**

   * `s0_gate_receipt_5B` and `sealed_inputs_5B` MUST exist for `mf` and pass their own schema and digest checks (as per S0 spec).
   * `s0_gate_receipt_5B.parameter_hash` MUST equal `ph`.
   * The recomputed digest of `sealed_inputs_5B` MUST equal `sealed_inputs_digest` in the receipt.

2. **Upstream status MUST be all PASS**

   * In `s0_gate_receipt_5B.upstream_segments`, each required upstream segment `{1A, 1B, 2A, 2B, 3A, 3B, 5A}` MUST have `status = "PASS"`.

S2 MUST NOT independently re-hash or override upstream flags; S0’s upstream status map is authoritative.

---

### 2.2 Dependency on S1 (Time grid & grouping)

S2 builds latent fields **on top of** S1. For each `scenario_id` S2 intends to process (the `scenario_set` in `s0_gate_receipt_5B`):

1. **S1 outputs MUST exist**

   * `s1_time_grid_5B@fingerprint=mf/scenario_id={scenario_id}` MUST exist and validate against `schemas.5B.yaml#/model/s1_time_grid_5B`.
   * `s1_grouping_5B@fingerprint=mf/scenario_id={scenario_id}` MUST exist and validate against `schemas.5B.yaml#/model/s1_grouping_5B`.

2. **S1 identity & domain MUST be consistent**

   * For each `scenario_id`, `manifest_fingerprint` and `parameter_hash` columns in both datasets MUST equal `mf` and `ph`.
   * The time grid MUST expose a finite, ordered set of `bucket_index` values per scenario.
   * The grouping table MUST expose a finite, non-duplicated set of `(merchant_id, zone_representation[, channel_group])` keys per scenario.

If either S1 dataset is missing or invalid for any `scenario_id` in scope, S2 MUST fail fast and MUST NOT attempt to reconstruct its own grid or grouping.

---

### 2.3 Required configs & policies for S2

S2 is the first RNG-bearing state in 5B. Before S2 runs, the following artefacts MUST be present in `sealed_inputs_5B` for `mf` as `status ∈ {REQUIRED, INTERNAL}` and be resolvable via the catalogue:

1. **Arrival-process / LGCP config** (name to be fixed, e.g. `arrival_lgcp_config_5B`)

   * Defines:

     * latent field type (e.g. log-Gaussian Cox, OU-on-log-λ, or “no latent field” case),
     * kernel / covariance structure (e.g. variance `σ²`, length-scale `ℓ`, correlation shape),
     * any per-group/per-scenario overrides,
     * any clipping rules for `λ_realised` (min/max factors).

2. **5B RNG policy** (e.g. `arrival_rng_policy_5B`)

   * Defines:

     * Philox stream IDs / substream labels for S2’s latent-field draws,
     * expected draws-per-event and blocks-per-event,
     * any budget/limit semantics for latent draws.

3. **(If applicable) S2-specific validation config**

   * If there is a dedicated S2 validation policy (e.g. target variance corridor checks on `ξ`), it MUST be present and valid, but it is primarily consumed by the later 5B validation state. S2 only needs it if it performs local guardrails.

All of these configs MUST validate against their schemas (`schemas.5B.yaml` or `schemas.layer2.yaml`) before S2 proceeds.

---

### 2.4 Inputs from 5A (λ surfaces)

S2 needs 5A’s deterministic λ as `λ_target`. Preconditions:

1. **Presence in sealed world**

   * The 5A dataset chosen as S2’s intensity source (e.g. `merchant_zone_scenario_local_5A`) MUST be listed in `sealed_inputs_5B` for `mf` with:

     * `status ∈ {REQUIRED, INTERNAL}`,
     * `read_scope = ROW_LEVEL`.

2. **Shape compatibility**

   * The λ surface MUST:

     * carry `scenario_id`, `merchant_id`, and zone key(s) in a form that can be joined to `s1_grouping_5B`,
     * carry a bucket coordinate (e.g. local bucket index) that can be mapped deterministically to `s1_time_grid_5B.bucket_index` for each scenario.

If the λ surface cannot be aligned to the S1 grid/grouping by key, that is a spec/config error; S2 MUST fail rather than inventing a different grid.

---

### 2.5 Data-plane access scope for S2

Given `sealed_inputs_5B` and catalogue:

* S2 MAY read **row-level** from:

  * `s1_time_grid_5B` and `s1_grouping_5B`,
  * the designated 5A λ surface(s) (for `λ_target`),
  * S2 configs/policies (they are small tables/objects).

* S2 MAY read **metadata-only** (no row-level semantics) from:

  * civil-time tables (`tz_timetable_cache`, `site_timezones`) if needed for kernel structure,
  * 2B/3A/3B metadata (e.g. group sizes, if used in kernel parametrisation).

* S2 MUST honour `read_scope` from `sealed_inputs_5B`:

  * If an artefact is marked `METADATA_ONLY`, S2 MUST NOT scan its rows.

S2 MUST NOT touch artefacts not present in `sealed_inputs_5B` for `mf`.

---

### 2.6 Invocation order within 5B

Within Segment 5B, S2 MUST:

* run **after** S0 and S1 have successfully completed (local PASS) for `(ph, mf, scenario_set_5B)`, and
* run **before** S3 (count realisation) and S4 (arrivals & routing), which depend on `λ_realised`.

S2 MUST NOT:

* run concurrently with S1 for the same `(ph, mf)` and `scenario_id`, or
* run after S3/S4 for the same `(ph, mf, scenario_id)` if that would imply re-defining `λ_realised` in place.

Any change to latent-field or arrival-process configuration that changes the realised intensities for a world MUST be expressed via a new `parameter_hash` and/or spec version, followed by fresh S0/S1/S2 runs.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes **what 5B.S2 is allowed to read** and **who is authoritative for which facts**. S2 MUST stay inside the world sealed by **5B.S0** and MUST NOT widen or override upstream authorities.

---

### 3.1 Inputs S2 MAY use

S2 MAY only use artefacts that:

* are listed in `sealed_inputs_5B` for this `manifest_fingerprint`, and
* are resolved via catalogue (dictionary + registry + upstream sealed-inputs), not ad-hoc paths.

Within that universe, S2’s logical inputs are:

#### (a) 5B.S0 / S1 control & planning

* `s0_gate_receipt_5B` + `sealed_inputs_5B`

  * For `parameter_hash`, `manifest_fingerprint`, `scenario_set`, upstream status, and the whitelist of artefacts S2 may touch.

* `s1_time_grid_5B` (row-level)

  * Canonical bucket grid per `(scenario_id, bucket_index)` with `bucket_start_utc`, `bucket_end_utc`, and tags.

* `s1_grouping_5B` (row-level)

  * Mapping from each in-scope `(merchant_id, zone_representation[, channel_group])` to a `group_id` per `scenario_id`.

S2 MUST treat these as *given*; it cannot change grid or grouping.

#### (b) 5A deterministic intensity surfaces (row-level)

S2’s λ_source MUST be a 5A dataset explicitly designated in the spec (e.g. `merchant_zone_scenario_local_5A`):

* It MUST be present in `sealed_inputs_5B` with `status ∈ {REQUIRED, INTERNAL}` and `read_scope = ROW_LEVEL`.
* It MUST carry at least:

  * `scenario_id`,
  * entity keys compatible with S1 grouping (`merchant_id`, `zone_representation[, channel_group]`),
  * a bucket coordinate that can be mapped to S1’s `bucket_index`, and
  * a deterministic intensity value (e.g. `lambda_local_scenario`).

S2 reads this as **λ_target** and MUST NOT try to recompute it from lower-level priors.

#### (c) 5B-local config & RNG policy (row-level)

S2 MUST read the following 5B artefacts (present in `sealed_inputs_5B` as `REQUIRED`/`INTERNAL`):

* **Arrival-process / LGCP config**

  * Defines latent-field type, kernel parameters, clipping rules, and any special cases (e.g. “no latent” mode).

* **5B RNG policy**

  * Defines event family names, stream IDs, substream labels, expected draws/blocks per event, and RNG accounting rules for S2.

* **(Optional) S2 validation config**

  * If present, defines local guardrails on latent fields / λ_realised that S2 should enforce before handing off to the final 5B validation state.

These configs are small, schema-governed objects; S2 MUST treat them as the **only source** for its stochastic law and RNG layout.

#### (d) Optional upstream metadata (metadata-only)

S2 MAY *inspect metadata only* (no row-level modelling) from:

* 2A `tz_timetable_cache` — if kernel design depends on actual time in days/hours (e.g. daily correlation structure).
* 2B/3A/3B dimension tables — if kernel or hyper-parameters depend on group size, zone type, or virtual/physical flags.

For these artefacts, `read_scope` in `sealed_inputs_5B` MUST be `METADATA_ONLY` for S2, and S2 MUST NOT use them to derive its own λ or group definitions.

---

### 3.2 Authority boundaries

Within S2, ownership is:

* **World identity & sealed universe**

  * **Owner:** 5B.S0
  * S2 MUST NOT add/remove artefacts from the world; it only consumes what S0 sealed.

* **Time grid & grouping**

  * **Owner:** 5B.S1
  * S2 MUST:

    * only use `(scenario_id, bucket_index)` from `s1_time_grid_5B`, and
    * only use `group_id` from `s1_grouping_5B`.
  * It MUST NOT change bucket boundaries or reassign entities to different groups.

* **Deterministic λ (λ_target)**

  * **Owner:** 5A
  * S2 MUST:

    * treat the 5A scenario intensity surface as the only deterministic λ source,
    * not rescale, smooth, or otherwise alter λ_target except via the defined stochastic modulation (latent fields) and any explicit clipping rules in config.

* **Civil time / calendar semantics**

  * **Owner:** 2A
  * If S2’s kernel depends on “distance in time” (e.g. correlation by days or hours), that mapping MUST follow 2A’s rules (UTC and/or tz-aware) and MUST NOT invent new time semantics.

* **Routing, zones, virtual overlay**

  * **Owners:** 2B, 3A, 3B
  * S2 does *not* manipulate routing, zone allocation, or virtual edges. At most, it may read metadata (e.g. group size, zone type) if the LGCP config allows hyper-parameters to depend on those, but routing semantics remain upstream’s responsibility.

* **Latent fields & λ_realised**

  * **Owner:** 5B.S2
  * This state and its spec are the only authority on:

    * how latent fields are sampled,
    * how they are applied to λ_target, and
    * what `λ_realised` means.
  * Downstream S3–S4 MUST treat S2’s realised intensities as canonical and MUST NOT add extra latent layers.

---

### 3.3 Prohibited inputs & behaviours

To keep boundaries clean, S2 MUST NOT:

* Read any artefact not present in `sealed_inputs_5B` for this `mf`.

* Re-query dictionaries/registries to “discover” extra inputs beyond what S0 sealed and listed.

* Read row-level data from:

  * 2A / 2B / 3A / 3B data-plane surfaces, except where explicitly allowed in future spec revisions;
  * any upstream tables marked `METADATA_ONLY` in `sealed_inputs_5B`.

* Modify or rewrite:

  * `s1_time_grid_5B` or `s1_grouping_5B`;
  * any 5A intensity surface;
  * any upstream bundles, `_passed.flag_*`, or upstream `sealed_inputs_*` tables.

* Introduce new external dependencies (env variables, ad-hoc config files, network calls) as implicit inputs to latent-field behaviour.

If S2 discovers at runtime that it “needs” information beyond what is allowed here, that is a **spec/config issue**, not a runtime permission: S2 MUST fail rather than widening its input set or redefining upstream responsibilities.

---

## 4. Outputs (datasets) & identity *(Binding)*

This section fixes **what 5B.S2 produces** and **how those outputs are identified**. These outputs are RNG-bearing and depend on the LGCP config and Philox seed, but are still deterministic for a given world and seed.

5B.S2 has:

* **One required model output:**

  * `s2_realised_intensity_5B` — authoritative per-bucket realised λ.

* **One optional diagnostic output:**

  * `s2_latent_field_5B` — per-group latent field over buckets (for debugging/validation).

RNG event logs for latent draws are covered by the Layer-wide RNG schema and artefact registry; they’re not treated as data-plane outputs here.

---

### 4.1 Identity scope (world vs stochastic identity)

Two identity scopes matter:

1. **World identity**

   * `world_id := (parameter_hash = ph, manifest_fingerprint = mf)`
   * Fixed by S0; determines the sealed world, S1 grid/grouping and 5A λ surfaces.

2. **Stochastic identity for S2 outputs**

   * `stochastic_id := (ph, mf, seed)`
   * For a fixed LGCP/arrival config and fixed S1/5A upstream, `s2_realised_intensity_5B` and `s2_latent_field_5B` MUST be deterministic functions of `(ph, mf, seed)` and **independent of `run_id`**.

Binding rules:

* Re-running S2 with the same `(ph, mf, seed)` and unchanged config MUST produce **byte-identical** outputs for all S2 datasets.
* Changing `seed` MAY change the realised intensities and latent fields; these are different stochastic realisations for the same world.

---

### 4.2 `s2_realised_intensity_5B` — realised λ per entity × bucket *(REQUIRED)*

**Role**

` s2_realised_intensity_5B` is the **authoritative realised-intensity surface** for S3. For each:

* `scenario_id`,
* `(merchant_id, zone_representation[, channel_group])` in S1’s grouping domain, and
* `bucket_index` in S1’s time grid,

it carries:

* deterministic λ from 5A (`λ_target`), and
* the **stochastic modulation** from S2 (latent effect), yielding `λ_realised`.

S3 MUST use this dataset as the **only** λ source for bucket-level count draws.

**Identity**

* Deterministically keyed by `(ph, mf, seed, scenario_id)`:

  * world identity `(ph, mf)` from S0,
  * stochastic identity `seed`,
  * scenario identity `scenario_id`.

`run_id` is used only for logging / RNG traces, not as part of this dataset’s identity.

**Domain (conceptual)**

* Rows cover exactly:

  ```text
  {(scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)}
  ```

  where:

  * `scenario_id ∈ scenario_set_5B`,
  * `(merchant_id, zone_representation[, channel_group])` is in `s1_grouping_5B` for that scenario, and
  * there is a corresponding λ_target in the chosen 5A surface, aligned to `bucket_index` from `s1_time_grid_5B`.

There MUST be no extra rows outside this domain and no missing rows inside it.

**Key columns (high level)**

At minimum, rows MUST include:

* `manifest_fingerprint`
* `parameter_hash`
* `seed`
* `scenario_id`
* `merchant_id`
* `zone_representation` (and `channel_group` if S1 uses it)
* `bucket_index`
* `lambda_baseline` (deterministic scale carried through from 5A/S1; optional)
* `lambda_random_component` (the stochastic contribution from the latent field; optional)
* `lambda_realised` (final mean intensity used by downstream states)

`lambda_baseline` is the renamed “λ_target” from earlier drafts; `lambda_random_component` is the materialised latent factor that used to be described as `latent_effect`.

Exact column names and types are pinned in `schemas.5B.yaml#/model/s2_realised_intensity_5B` and will be wired into the dictionary/registry in the contracts section.

---

### 4.3 `s2_latent_field_5B` — latent field per group × bucket *(OPTIONAL, diagnostic)*

**Role**

` s2_latent_field_5B` is a **diagnostic/validation** dataset exposing the latent field directly, typically at the group level defined by S1. It is helpful for:

* debugging LGCP behaviour,
* validating that correlation/variance look as configured,
* powering offline analysis of latent dynamics.

It is **not required** for S3/S4 operation; S3 operates on `s2_realised_intensity_5B`.

**Identity**

* Same stochastic identity as realised λ:

  * `(ph, mf, seed, scenario_id)`

**Domain (conceptual)**

* Rows cover:

  ```text
  {(scenario_id, group_id, bucket_index)}
  ```

  where:

  * `group_id` comes from `s1_grouping_5B`,
  * `bucket_index` comes from `s1_time_grid_5B` for that scenario.

**Key columns (high level)**

At minimum, rows SHOULD include:

* `manifest_fingerprint`
* `parameter_hash`
* `seed`
* `scenario_id`
* `group_id`
* `bucket_index`
* latent scalar(s), e.g.:

  * `latent_gaussian` (pre-transform)
  * `lambda_random_component` (post-transform, e.g. multiplicative factor or log-factor)

Exact column definitions belong to `schemas.5B.yaml#/model/s2_latent_field_5B`. The dataset is **optional**; if not produced, downstream code MUST rely solely on `s2_realised_intensity_5B`.

---

### 4.4 Required vs optional datasets (S2)

For S2:

* `s2_realised_intensity_5B` — **REQUIRED**, `final_in_state: true`, not final in segment.
* `s2_latent_field_5B` — **OPTIONAL**, `final_in_state: true`; may be omitted in minimal deployments, but if present it MUST obey this spec.

RNG event logs for S2’s latent draws:

* are registered as `LOG` artefacts (e.g. `rng_event_arrival_lgcp_gaussian`),
* use the Layer-wide RNG log/trace schemas,
* are **not** treated as data-plane outputs in this section but will be referenced in S2’s RNG/validation sections.

Downstream obligations:

* **S3 MUST** gate on the presence and schema validity of `s2_realised_intensity_5B` for each `(mf, seed, scenario_id)` it wants to process.
* **S4 MUST NOT** alter λ_realised; it only consumes counts derived from it.

Within this identity model, S2’s outputs are clearly scoped: **world + seed + scenario** determine the realised-intensity surface (and any latent diagnostics), and those surfaces are the only λ inputs that later 5B states are allowed to use.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes the **dataset identities, schema anchors and catalogue wiring** for the outputs of **5B.S2 — Latent intensity fields**:

* `s2_realised_intensity_5B` *(required)*
* `s2_latent_field_5B` *(optional, diagnostic)*

No other S2 datasets are allowed without updating this spec and the 5B schemas/dictionaries.

---

### 5.1 Common conventions

Both S2 datasets MUST:

* Live in the 5B schema pack: `schemas.5B.yaml`.
* Reuse Layer-1 primitives via `$ref` to `schemas.layer1.yaml` for:

  * `id64` (merchant IDs),
  * `iana_tzid`,
  * `iso2`,
  * `rfc3339_micros`,
  * numeric scalar types (e.g. `dec_u128` if used).
* Be registered in `dataset_dictionary.layer2.5B.yaml` and the 5B artefact registry with:

  * `owner_segment: 5B`,
  * `layer: 2`.

Identity & scope:

* Deterministic function of `(parameter_hash, manifest_fingerprint, seed, scenario_id)`.
* Independent of `run_id`.

Partitioning convention (S2):

* `partition_keys: [seed, manifest_fingerprint, scenario_id]`
* Path token for world: `fingerprint={manifest_fingerprint}` (consistent with Layer-1/Layer-2).

---

### 5.2 `s2_realised_intensity_5B` — schema & catalogue links *(REQUIRED)*

#### 5.2.1 Schema anchor

* **Dataset ID** (dictionary): `s2_realised_intensity_5B`
* **Schema anchor**:
  `schemas.5B.yaml#/model/s2_realised_intensity_5B`

#### 5.2.2 Logical shape (required fields)

Each row represents a **realised intensity** for one entity×bucket×scenario for a given seed.

Required columns (names illustrative but MUST be fixed in the schema):

* Identity & keys:

  * `manifest_fingerprint : string`
  * `parameter_hash : string`
  * `seed : integer | string`
  * `scenario_id : string`
  * `merchant_id` — `$ref: schemas.layer1.yaml#/$defs/id64`
  * `zone_representation` — the chosen zone representation for 5B; schema MUST fix shape, e.g.:

    * either `tzid : $ref: .../iana_tzid`, or
    * `country_iso : $ref: .../iso2` + `tzid : $ref: .../iana_tzid`
  * optional `channel_group : string`
  * `bucket_index : integer` — must align with `s1_time_grid_5B.bucket_index` for `(mf, scenario_id)`.

* Intensity & latent effect:

  * `lambda_baseline : number`

    * deterministic λ from 5A, echoed or aligned to 5A S4 surface.
  * `lambda_random_component : number`

    * the multiplicative (or log-scale) factor from the latent field; exact interpretation documented in schema description (e.g. log-normal factor vs additive-on-log).
  * `lambda_realised : number`

    * the final intensity used by S3; MUST satisfy:

      * `lambda_realised ≥ 0`,
      * finite (no NaN/Inf),
      * any additional bounds from the arrival/LGCP config (documented elsewhere).

* Provenance (recommended):

  * `group_id : string | integer` — group from `s1_grouping_5B` for this entity.
  * `kernel_id : string` — ID of kernel/hyper-parameter set applied.
  * `config_version : string` — version of `arrival_lgcp_config_5B` used.

Exact field names, types and any optional extras MUST be pinned in `schemas.5B.yaml#/model/s2_realised_intensity_5B`.

#### 5.2.3 Keys, partitions & dictionary entry

**Logical primary key:**

```text
(manifest_fingerprint, parameter_hash, seed,
 scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)
```

**Writer sort order (per file):**

```text
scenario_id, merchant_id, zone_representation[, channel_group], bucket_index
```

**Dictionary entry (sketch):**

```yaml
datasets:
  - id: s2_realised_intensity_5B
    owner_segment: 5B
    layer: 2
    schema_ref: "schemas.5B.yaml#/model/s2_realised_intensity_5B"
    format: parquet
    path: "data/layer2/5B/s2_realised_intensity/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s2_realised_intensity_5B.parquet"
    partition_keys: ["seed", "manifest_fingerprint", "scenario_id"]
    version: "{manifest_fingerprint}"
    final_in_segment: false
```

**Registry entry (sketch):**

* Manifest key: `mlr.5B.model.s2_realised_intensity`
* `type: dataset`, `category: model`
* `depends_on`:

  * `mlr.5B.model.s1_time_grid`,
  * `mlr.5B.model.s1_grouping`,
  * 5A λ surface manifest key (e.g. `mlr.5A.model.merchant_zone_scenario_local`),
  * 5B arrival/LGCP config,
  * 5B RNG policy.

---

### 5.3 `s2_latent_field_5B` — schema & catalogue links *(OPTIONAL)*

#### 5.3.1 Schema anchor

* **Dataset ID** (dictionary): `s2_latent_field_5B`
* **Schema anchor**:
  `schemas.5B.yaml#/model/s2_latent_field_5B`

#### 5.3.2 Logical shape (required fields)

Each row represents a **latent field value** for a group×bucket×scenario for a given seed. This dataset is optional and diagnostic.

Required columns:

* Identity & keys:

  * `manifest_fingerprint : string`
  * `parameter_hash : string`
  * `seed : integer | string`
  * `scenario_id : string`
  * `group_id : string | integer`
  * `bucket_index : integer`

* Latent values:

* `latent_value : number`

  * the raw latent sample (e.g. Gaussian draw) for the group×bucket.
* `latent_mean : number`, `latent_std : number`

  * echo whatever parameters were used to produce `latent_value` (useful for diagnostics).
* `lambda_random_component : number`

  * the derived effect applied in intensity space (e.g. `exp(latent_value)`), matching the `lambda_random_component` stored in `s2_realised_intensity_5B`.

Optional fields:

* `kernel_id : string`
* `config_version : string`
* any diagnostic tags (e.g. per-group hyper-parameters echoed).

Exact shape MUST be fixed by `schemas.5B.yaml#/model/s2_latent_field_5B`.

#### 5.3.3 Keys, partitions & dictionary entry

**Logical primary key:**

```text
(manifest_fingerprint, parameter_hash, seed,
 scenario_id, group_id, bucket_index)
```

**Writer sort order (per file):**

```text
scenario_id, group_id, bucket_index
```

**Dictionary entry (sketch):**

```yaml
datasets:
  - id: s2_latent_field_5B
    owner_segment: 5B
    layer: 2
    schema_ref: "schemas.5B.yaml#/model/s2_latent_field_5B"
    format: parquet
    path: "data/layer2/5B/s2_latent_field/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s2_latent_field_5B.parquet"
    partition_keys: ["seed", "manifest_fingerprint", "scenario_id"]
    version: "{manifest_fingerprint}"
    final_in_segment: false
```

**Registry entry (sketch):**

* Manifest key: `mlr.5B.model.s2_latent_field`
* `type: dataset`, `category: diagnostic`
* `depends_on`:

  * `mlr.5B.model.s1_time_grid`,
  * `mlr.5B.model.s1_grouping`,
  * 5B arrival/LGCP config,
  * 5B RNG policy.

Downstream code MUST treat this dataset as **optional**: if absent, all operational logic must use `s2_realised_intensity_5B` only.

---

### 5.4 Catalogue usage rules

* All discovery of S2 outputs by S3/S4 or validation MUST go via:

  * `dataset_dictionary.layer2.5B.yaml`, and
  * the 5B artefact registry (manifest keys above).
* No code may hard-code paths or filenames; all must be derived from these catalogues.
* Both S2 datasets MUST be marked `final_in_state: true` for S2, but **not** `final_in_segment` (they are still gated by 5B’s terminal HashGate, not by S2 itself).

With these shapes and links in place, S2’s outputs are:

* clearly typed (`schemas.5B.yaml`),
* discoverable (dictionary/registry),
* and consistent with 5B’s identity and partitioning rules from §4.

---

## 6. Deterministic algorithm with RNG (LGCP core) *(Binding)*

This section defines the **exact responsibilities and structure** of the 5B.S2 algorithm. It is:

* **Deterministic given**:
  `(parameter_hash = ph, manifest_fingerprint = mf, seed, scenario_set_5B)` + sealed inputs (S0) + S1 outputs + 5A λ surfaces + 5B configs.
* **RNG-bearing**: it consumes Philox streams and emits RNG events/traces.
* **Purely about intensities**: it does **not** produce counts or arrivals.

For a fixed world and seed, rerunning S2 MUST produce **byte-identical** outputs and RNG logs.

---

### 6.1 Step 0 — Load & validate context

S2 MUST:

1. **Read and validate S0 outputs**

   * Load `s0_gate_receipt_5B@mf` and `sealed_inputs_5B@mf`.
   * Confirm:

     * `parameter_hash == ph`, `manifest_fingerprint == mf`.
     * `sealed_inputs_digest` matches a recomputed digest of `sealed_inputs_5B`.
     * `upstream_segments[seg].status == "PASS"` for all `{1A,1B,2A,2B,3A,3B,5A}`.

2. **Read and validate S1 outputs**

   For each `scenario_id ∈ scenario_set_5B`:

   * Load and schema-validate:

     * `s1_time_grid_5B@mf, scenario_id`
     * `s1_grouping_5B@mf, scenario_id`

   * Confirm:

     * `parameter_hash == ph`, `manifest_fingerprint == mf` in both.
     * `bucket_index` is contiguous and ordered per scenario.
     * grouping PK `(manifest_fingerprint, scenario_id, merchant_id, zone_representation[, channel_group])` has no duplicates.

3. **Resolve S2 configs & RNG policy**

   * From `sealed_inputs_5B`, locate and load:

     * **arrival/LGCP config** (e.g. `arrival_lgcp_config_5B`),
     * **5B RNG policy** (e.g. `arrival_rng_policy_5B`),
     * optional S2-specific validation/guardrail config.

   * Validate each against its schema; extract at least:

     * latent model type (e.g. `latent_model: "none" | "log_gaussian"`),
     * kernel / covariance law and hyper-parameters (e.g. `sigma2`, `length_scale`),
     * clipping rules for `lambda_realised`,
     * RNG stream IDs and substream labels for S2’s event family (e.g. `stream_id = "arrival_lgcp"`, `substream_label = "latent_vector"`),
     * expected RNG accounting semantics (e.g. “one event per (scenario, group)”, `draws = actual uniform draws used`, `blocks` as per Philox block semantics).

If any of these validations fail, S2 MUST raise the appropriate S2 error and abort before any RNG is consumed.

---

### 6.2 Step 1 — Assemble λ_target domain

For each `scenario_id ∈ scenario_set_5B`:

1. **Load λ_target from 5A**

   * From the designated 5A intensity surface (e.g. `merchant_zone_scenario_local_5A`), read rows for this `scenario_id` and world `(ph, mf)`.

2. **Align keys with S1**

   * Join λ_target rows to:

     * `s1_grouping_5B` on `(scenario_id, merchant_id, zone_representation[, channel_group])`, and
     * `s1_time_grid_5B` on `(scenario_id, bucket_index)` (or via agreed mapping from 5A’s local bucket coordinate to S1’s `bucket_index`).

3. **Define S2 domain**

   * The S2 intensity domain `D_s` for scenario `s` is:

     ```text
     D_s := {
       (merchant_id, zone_representation[, channel_group], bucket_index)
       : there exists λ_target and a group_id in S1 for this combination
     }
     ```

   * For each such entity, record:

     * `group_id` from `s1_grouping_5B`,
     * `λ_target` from 5A,
     * `bucket_index` and any tags from `s1_time_grid_5B`.

If any λ_target row cannot be aligned to grid+grouping (or vice versa where policy requires full coverage), S2 MUST fail with a domain/alignment error, not guess.

---

### 6.3 Step 2 — Build latent-field domains per (scenario, group)

S2 next constructs the **latent-field domain** per `(scenario_id, group_id)`.

For each `scenario_id`:

1. **Group membership**

   * From `s1_grouping_5B`, determine the set of groups:

     ```text
     G_s := { group_id : exists (merchant_id, zone_representation[, channel_group]) in s1_grouping_5B for scenario s }
     ```

2. **Bucket set**

   * From `s1_time_grid_5B`, determine the ordered bucket set:

     ```text
     H_s := { bucket_index : rows in s1_time_grid_5B for scenario s }
     ```

   * The ordered list of buckets for scenario `s` is `H_s_sorted = [b0, b1, …, bN-1]` with `b0 < b1 < …`.

3. **Kernel / covariance specification**

   For each `(s, g)`:

   * Using the LGCP config, define the latent model over `H_s_sorted`, e.g.:

     * a stationary covariance kernel `K_s,g(b_i, b_j)` if using a general MVN, or
     * an OU/AR(1)-style recursion law on bucket indices if using a Markovian approximation.

   * The **exact form** of `K_s,g` or the recursion law is governed by config; S2 MUST NOT hard-code it.

The outcome of this step is a conceptual latent domain:

```text
For each scenario s and group g:
  domain H_s_sorted and a law over ℝ^{|H_s|} (mean, covariance / recursion)
```

---

### 6.4 Step 3 — Sample latent fields with Philox RNG

S2 now uses Philox to sample latent Gaussian (or equivalent) fields for each `(scenario_id, group_id)`.

1. **RNG stream & event family**

   * From the 5B RNG policy, S2 obtains:

     * a **stream_id** for latent draws (e.g. `"arrival_lgcp"`),
     * a **substream_label** for the event family (e.g. `"latent_vector"`),
     * rules for mapping `(scenario_id, group_id)` to substream offsets or counters.

2. **Per-(scenario, group) latent draw**

   For each `(scenario_id = s, group_id = g)`:

   * Determine:

     * the bucket list `H_s_sorted` (length `T_s`),
     * latent model parameters for `(s, g)` (kernel/hyper-params).

   * Using Philox and the Layer-wide RNG law:

     * consume a deterministic sequence of `U(0,1)` draws from the configured stream/substream for `(s, g)`,
     * transform these uniforms into a latent vector `Z_s,g` in ℝ^{T_s}`, distributed according to the latent model for `(s,g)`:

       * e.g. `Z_s,g ~ N(0, Σ_s,g)` via Cholesky/matrix factorisation, or
       * equivalent OU/AR(1) recursion giving a Gaussian process with the configured law.

   * Record a **single RNG event** (or a small, fixed number, as per RNG policy) for the entire `(s,g)` vector, e.g.:

     * `module = "5B.S2"`
     * `substream_label = "latent_vector"`
     * `scenario_id`, `group_id`, `manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`
     * `rng_counter_before_{lo,hi}`, `rng_counter_after_{lo,hi}`
     * `draws` = decimal string of total uniforms consumed (as per Layer-wide spec)
     * `blocks` = count of Philox blocks used

   * Append a corresponding row into the RNG trace log, as per the global RNG discipline (one trace entry per event append).

**Requirements:**

* For fixed `(ph, mf, seed, scenario_id, group_id)` and config, the resulting `Z_s,g` MUST be deterministic.
* The RNG policy MUST ensure no overlap of counters/streams between different `(s,g)` pairs or other 5B states.

---

### 6.5 Step 4 — Transform latent fields into factors and λ_realised

For each `(s, g)` and each bucket index `b ∈ H_s_sorted`:

1. **Derive bucket-level latent effect**

   From `Z_s,g(b)` and the LGCP config, compute a scalar latent effect:

   * e.g. for log-Gaussian Cox:

     ```text
     latent_gaussian = Z_s,g(b)             # zero-mean Gaussian
     lambda_random_component   = exp(latent_gaussian) # multiplicative factor
     ```

   * or more generally, apply the configured transform `f_latent`:

     ```text
     lambda_random_component = f_latent(Z_s,g(b), config_s,g)
     ```

2. **Map to entities via grouping**

   For each `(merchant_id, zone_representation[, channel_group])` in `s1_grouping_5B` with `group_id = g` and for bucket `b`:

   * Join the latent effect for `(s,g,b)` with `λ_target(m, zone, b)` from Step 1.

3. **Compute λ_realised**

   For each such entity/bucket, compute:

   ```text
   lambda_baseline   = λ_target(m, zone[, ch], b)
   lambda_random_component   = value from (s, g, b)
   lambda_realised = f_intensity(lambda_baseline, lambda_random_component, config)
   ```

   where:

   * `f_intensity` is a deterministic mapping defined in the LGCP config (e.g. `λ_realised = λ_target × lambda_random_component`, possibly with clipping).

4. **Apply clipping/guardrails**

   If the config defines bounds or guardrails (e.g. `min_factor`, `max_factor`, or `max_lambda`):

   * apply the clipping deterministically,
   * ensure:

     * `lambda_realised ≥ 0`,
     * no NaN or Inf,
     * any violations are flagged for later validation (e.g. S2 may log a local counter; overall checks belong to 5B’s validation state).

Intermediate result: for each scenario, a complete mapping from `D_s` to `(lambda_baseline, lambda_random_component, lambda_realised)`.

---

### 6.6 Step 5 — Persist S2 outputs

After latent fields and λ_realised are computed for all `(s,g)`:

1. **Write `s2_realised_intensity_5B`**

   * For each `(seed, mf, scenario_id)`, materialise a Parquet file at:

     ```text
     data/layer2/5B/s2_realised_intensity/seed={seed}/fingerprint={mf}/scenario_id={scenario_id}/s2_realised_intensity_5B.parquet
     ```

   * Enforce:

     * schema = `schemas.5B.yaml#/model/s2_realised_intensity_5B`,
     * partition keys = `[seed, manifest_fingerprint, scenario_id]`,
     * writer sort order: `(scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)`.

   * Ensure:

     * every domain element in `D_s` has exactly one row,
     * no duplicates for the logical PK.

2. **Write `s2_latent_field_5B` (if configured)**

   * If the LGCP config dictates a latent diagnostic output:

     * For each `(seed, mf, scenario_id)`, write:

       ```text
       data/layer2/5B/s2_latent_field/seed={seed}/fingerprint={mf}/scenario_id={scenario_id}/s2_latent_field_5B.parquet
       ```

     * Enforce:

       * schema = `schemas.5B.yaml#/model/s2_latent_field_5B`,
       * partition keys = `[seed, manifest_fingerprint, scenario_id]`,
       * writer sort order: `(scenario_id, group_id, bucket_index)`.

3. **Atomicity & idempotency**

   * All writes MUST be atomic at file level (temp path + rename).
   * If files already exist for `(seed, mf, scenario_id)`:

     * either verify they are byte-identical to what S2 would write and treat the run as idempotent, or
     * fail with an IO write-conflict error; S2 MUST NOT silently overwrite differing outputs.

---

### 6.7 RNG invariants & prohibited actions

Throughout S2, the following RNG invariants MUST hold:

1. **No RNG before preconditions**

   * No RNG event may be emitted, and no Philox stream referenced, before:

     * S0/S1/5A/config preconditions are validated (Sections 2 & 3).

2. **Event ↔ trace discipline**

   * Each latent-field RNG event append MUST be followed by exactly one append to the RNG trace log, as per the Layer-wide RNG spec (one trace row per event).

3. **Determinism**

   * For fixed `(ph, mf, seed)` and fixed configs, S2’s RNG draws, latent fields, λ_realised and RNG logs MUST be deterministic, independent of `run_id`.

4. **No other RNG usage**

   * S2 MUST NOT consume RNG for anything other than latent-field draws (no extra “utility” randomness).

Prohibited behaviours:

* Re-sampling or modifying λ_target outside the defined `f_intensity` + latent effect mapping.
* Changing S1’s buckets or grouping.
* Using external randomness (outside Philox and RNG policy).
* Widening the RNG footprint beyond what is defined in the 5B RNG policy (e.g. ad-hoc new event families without schema/policy).

Within these constraints, the algorithm above fully specifies how **5B.S2** joins S1 and 5A, samples latent fields under Philox discipline, and produces a realised-intensity surface that S3 can safely treat as its only λ source.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S2’s datasets are keyed, partitioned, ordered and updated**. It is binding on implementations, catalogue entries, and all downstream 5B states.

S2 outputs (from this state):

* **Required:** `s2_realised_intensity_5B`
* **Optional:** `s2_latent_field_5B`

---

### 7.1 Identity scopes

There are three relevant scopes:

1. **World identity**

   * `world_id := (parameter_hash = ph, manifest_fingerprint = mf)`
   * Fixed by S0; identifies the sealed world (upstream artefacts, S1 grid/grouping, 5A λ surfaces).

2. **Stochastic identity**

   * `stochastic_id := (ph, mf, seed)`
   * For fixed LGCP config and S1/5A upstream, S2’s outputs and RNG logs MUST be deterministic functions of this triple and **independent of `run_id`**.

3. **Scenario identity**

   * `scenario_id ∈ scenario_set_5B`
   * Specifies which S1 grid and 5A λ slices are in play.

**Binding rule:**
For fixed `(ph, mf, seed, scenario_id)` and fixed configs/policies, the contents of `s2_realised_intensity_5B` and `s2_latent_field_5B` MUST be byte-identical across S2 re-runs, regardless of `run_id`.

---

### 7.2 Partitioning & path law

Both S2 datasets use the same partitioning law:

* **Partition keys:** `seed`, `manifest_fingerprint`, `scenario_id`
* **Path tokens:**

  * `seed={seed}`
  * `fingerprint={manifest_fingerprint}`
  * `scenario_id={scenario_id}`

Canonical paths:

* `s2_realised_intensity_5B`:

  ```text
  data/layer2/5B/s2_realised_intensity/
    seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/
    s2_realised_intensity_5B.parquet
  ```

* `s2_latent_field_5B`:

  ```text
  data/layer2/5B/s2_latent_field/
    seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/
    s2_latent_field_5B.parquet
  ```

**Path ↔ embed equality:**

For every row in either dataset:

* `manifest_fingerprint` column MUST equal `{manifest_fingerprint}` from the path.
* `parameter_hash` column MUST equal `ph` from S0.
* `seed` column MUST equal `{seed}` from the path.
* `scenario_id` column MUST equal `{scenario_id}` from the path.

No S2 file may mix rows for different seeds, manifests or scenarios.

---

### 7.3 Primary keys & writer ordering

#### 7.3.1 `s2_realised_intensity_5B`

**Logical primary key:**

```text
(manifest_fingerprint, parameter_hash, seed,
 scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)
```

This combination MUST be unique per row.

**Writer sort order within each file:**

```text
scenario_id,
merchant_id,
zone_representation[, channel_group],
bucket_index
```

This ordering is required so that:

* file-level hashes are reproducible, and
* diffs across runs/seeds are stable.

#### 7.3.2 `s2_latent_field_5B` (if produced)

**Logical primary key:**

```text
(manifest_fingerprint, parameter_hash, seed,
 scenario_id, group_id, bucket_index)
```

**Writer sort order within each file:**

```text
scenario_id,
group_id,
bucket_index
```

Same reasons: deterministic file hashes and stable diffs.

---

### 7.4 Merge & overwrite discipline

For a fixed `(ph, mf, seed, scenario_id)`:

* There MUST be **at most one** `s2_realised_intensity_5B` file and, if produced, **at most one** `s2_latent_field_5B` file at their canonical paths.

**Re-runs:**

* Re-running S2 for the same `(ph, mf, seed, scenario_id)` and unchanged configs MUST either:

  * not write new files (treat run as a no-op), or
  * write files that are **byte-identical** to the existing ones.

If S2 detects an existing file whose content would differ from what it is about to write for the same `(ph, mf, seed, scenario_id)`:

* It MUST treat this as an **idempotency violation** and raise an IO write-conflict error.
* It MUST NOT silently overwrite or merge contents.

**No cross-world merges:**

* Files for different `manifest_fingerprint` values MUST live in different `fingerprint=…` directories and MUST NOT be combined.
* Files for different `seed` values MUST live in different `seed=…` partitions and MUST NOT be combined.

---

### 7.5 Downstream consumption discipline

Downstream states (S3, S4, final 5B validation) MUST obey:

1. **Explicit selection of `(ph, mf, seed, scenario_id)`**

   * For count realisation, S3 MUST:

     * pick a specific `(ph, mf, seed, scenario_id)`,
     * read exactly the `s2_realised_intensity_5B` file at the canonical path for that tuple,
     * verify schema and PK uniqueness.

   * S3 MUST NOT attempt to synthesise a λ surface by stitching across seeds or manifests.

2. **Treat S2 outputs as canonical intensities**

   * S3 MUST use `lambda_realised` from `s2_realised_intensity_5B` as the **only** mean parameter for its bucket-level draws.
   * S3–S4 MUST NOT:

     * reintroduce an independent latent layer, or
     * change λ_realised in place.

3. **No modification of S2 datasets**

   * No downstream state may overwrite or append to S2 outputs. Any change to latent model, kernel, or intensity transformation MUST be expressed via a new `parameter_hash` and/or 5B spec version and a fresh S0+S1+S2 run.

Under these rules, S2’s datasets have:

* a clear identity (`world + seed + scenario`),
* a simple, consistent partitioning scheme,
* deterministic ordering for reproducible hashes,
* and a strict “no in-place edits” discipline that keeps the stochastic surface well-defined for anything that consumes it.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 5B.S2 — Latent intensity fields is considered PASS** and what that implies for downstream 5B states (S3–S4) and orchestration. If any criterion here fails, S2 MUST be treated as **FAIL** for that `(parameter_hash, manifest_fingerprint, seed)` and its outputs MUST NOT be used.

---

### 8.1 Local PASS criteria for 5B.S2

For a fixed `(ph, mf, seed, scenario_set_5B)`, a run of S2 is **PASS** if and only if **all** of the following hold:

1. **S0/S1 preconditions satisfied**

   * `s0_gate_receipt_5B@mf` and `sealed_inputs_5B@mf`:

     * exist and are schema-valid,
     * embed `parameter_hash = ph`, `manifest_fingerprint = mf`, and the correct `scenario_set`.
   * `sealed_inputs_digest` matches a recomputed digest of `sealed_inputs_5B`.
   * `upstream_segments[seg].status == "PASS"` for all required segments `{1A,1B,2A,2B,3A,3B,5A}`.
   * For every `scenario_id ∈ scenario_set_5B`:

     * `s1_time_grid_5B` and `s1_grouping_5B` exist, are schema-valid, and consistent with `(ph, mf)`.

2. **Configs & RNG policy resolved and valid**

   * The 5B **arrival/LGCP config** and **5B RNG policy**:

     * are present in `sealed_inputs_5B` with `status ∈ {REQUIRED, INTERNAL}`,
     * pass schema validation, and
     * supply all parameters S2 needs (latent model type, kernel law, clipping rules, stream IDs/labels, draw/block rules).

3. **Domain consistency (λ_target, grid, grouping)**

   For each `scenario_id ∈ scenario_set_5B`:

   * The designated 5A λ surface (λ_target) is present in the sealed world and schema-valid.
   * Every row of `λ_target` that falls within the scenario horizon can be aligned to:

     * a unique `(bucket_index)` from `s1_time_grid_5B`, and
     * a unique `(group_id)` via `s1_grouping_5B`.
   * There are no “dangling” S1 group entries that have λ_target when config says they should not, or vice versa, unless explicitly allowed by config (e.g. zero λ for some buckets).

4. **Latent-field coverage**

   * For each `(scenario_id, group_id)` in S1’s grouping domain:

     * a latent field value is constructed for **every** `bucket_index` in that scenario’s grid.
   * If `s2_latent_field_5B` is produced:

     * it exists and is schema-valid,
     * for each `(s, g)` it has exactly one `latent_gaussian`/`lambda_random_component` per `bucket_index` in the grid,
     * no missing or duplicate `(scenario_id, group_id, bucket_index)` keys.

5. **Realised intensity coverage & correctness**

   For each `scenario_id ∈ scenario_set_5B` and seed:

   * `s2_realised_intensity_5B` exists, is schema-valid, and for its `(seed, mf, scenario_id)` partition:

     * for every domain element in `D_s` (as defined in §6.2–6.4), there is exactly one row with:

       * `(merchant_id, zone_representation[, channel_group], bucket_index)`,
       * `lambda_baseline`, `lambda_random_component`, and `lambda_realised`.
     * there are **no duplicate** rows for the logical PK
       `(manifest_fingerprint, parameter_hash, seed, scenario_id, merchant_id, zone_representation[, channel_group], bucket_index)`.

   * Numerically:

     * `lambda_realised` is finite (no NaN/Inf) for every row,
     * `lambda_realised ≥ 0`,
     * any configured clipping rules (min/max factors, max λ, etc.) have been applied.

6. **RNG accounting invariants**

   * For each `(scenario_id, group_id)`:

     * exactly the expected RNG event(s) were emitted (per RNG policy) for the latent vector draw(s),
     * the event envelopes (counters, draws, blocks) obey the Layer-wide RNG law and the 5B RNG policy,
     * the RNG trace log contains exactly one trace row per event append and reconciles to event counts and draw totals.

   * For fixed `(ph, mf, seed)` the RNG usage and resulting latent draws are deterministic; this is typically checked via a combination of:

     * counter monotonicity,
     * no overlaps between (scenario, group) substreams,
     * optional replay in the validation state (not necessarily in S2).

If all of the above hold, S2 is **locally PASS**, and its outputs (`s2_realised_intensity_5B`, plus `s2_latent_field_5B` if present) may be consumed by S3/S4 and the final 5B validation state.

---

### 8.2 Local FAIL conditions

5B.S2 MUST be considered **FAIL** if **any** of the following occurs:

1. **S0/S1/5A preconditions fail**

   * S0 outputs are missing/invalid or upstream status has non-PASS segments.
   * S1 outputs are missing/invalid for any `scenario_id ∈ scenario_set_5B`.
   * λ surfaces from 5A are missing, malformed, or not alignable to S1 grid/grouping.

2. **Config / RNG policy issues**

   * Arrival/LGCP config or RNG policy is missing from `sealed_inputs_5B`, cannot be resolved, or fails schema validation.
   * Required parameters (e.g. kernel type, σ², length-scale) are absent or invalid.

3. **Domain or alignment errors**

   * S2 cannot form a coherent domain `D_s` for any scenario (e.g. λ_target has buckets/outlets that cannot be joined to S1, or S1 domain includes entities that have no λ_target when config says they must).

4. **Latent-field construction errors**

   * Latent vectors cannot be constructed for some `(scenario_id, group_id)` due to kernel/config problems (e.g. non-positive-definite covariance where the model requires it).
   * If `s2_latent_field_5B` is produced:

     * it fails schema validation,
     * has missing or duplicate `(scenario_id, group_id, bucket_index)` rows.

5. **Realised intensity errors**

   * `s2_realised_intensity_5B` fails schema validation.
   * Missing rows for some required domain elements (holes in `D_s`).
   * Duplicates in the logical PK.
   * Any `lambda_realised` is NaN/Inf, negative in violation of config, or otherwise outside configured numeric bounds without being caught and recorded as a violation for downstream validation.

6. **RNG accounting / determinism issues**

   * Latent RNG events do not match expectations:

     * wrong number of events per `(scenario_id, group_id)`,
     * unexpected `draws` or `blocks` values,
     * counter ranges overlapping across groups or scenarios where policy forbids it.
   * Re-running S2 with the same `(ph, mf, seed)` produces different outputs or different RNG logs (determinism broken).

7. **IO / overwrite issues**

   * S2 fails to write outputs atomically (`IO_WRITE_FAILED`), or
   * S2 detects existing S2 outputs for `(ph, mf, seed, scenario_id)` whose contents differ byte-for-byte from the new run (idempotency failure) and cannot be safely reconciled.

On any such condition, S2 MUST report the appropriate error code (see §9) and the run MUST be treated as FAIL for this `(ph, mf, seed)`.

---

### 8.3 Gating obligations for 5B.S2 itself

S2 MUST enforce the following **before** declaring PASS:

1. **No RNG before preconditions**

   * It MUST NOT consume Philox or emit RNG events until S0/S1/5A/config preconditions in §§2–3 have all been validated.

2. **All-or-nothing per seed & scenario_set**

   * For a given `(ph, mf, seed)` and `scenario_set_5B`, S2 MUST either:

     * successfully produce and validate outputs for **every** `scenario_id ∈ scenario_set_5B`, or
     * treat the entire S2 run as FAIL for this `(ph, mf, seed)`; partial success is not allowed.

3. **Write only after latent & λ_realised computed**

   * It MUST fully compute latent fields and λ_realised in memory (or via safe streaming) and pass local numerical sanity checks before writing `s2_realised_intensity_5B` (and `s2_latent_field_5B` if applicable).

4. **Idempotent re-runs**

   * On detecting pre-existing outputs for `(ph, mf, seed, scenario_id)`, S2 MUST:

     * confirm they are byte-identical to what it would write and treat the run as idempotent, or
     * fail with an IO write-conflict error.
   * It MUST NOT silently overwrite or merge outputs.

---

### 8.4 Gating obligations for downstream 5B states (S3–S4)

All later 5B states MUST treat S2 as a **hard gate** for realised intensities:

1. **Presence & schema checks**

   Before consuming λ_realised, S3 and the 5B validation state MUST:

   * verify that `s2_realised_intensity_5B` exists for each `(ph, mf, seed, scenario_id)` they intend to process, and
   * validate it against `schemas.5B.yaml#/model/s2_realised_intensity_5B`.

   If S2 is configured to produce `s2_latent_field_5B`, validation of that dataset SHOULD also be checked, but operationally S3 MUST be able to run using `s2_realised_intensity_5B` alone.

2. **No independent latent/noise layers**

   * S3 MUST use `lambda_realised` as its **only** mean parameter for bucket-level count draws.
   * S3–S4 MUST NOT:

     * introduce an additional latent/noise layer that changes the mean intensity,
     * resample or perturb λ_realised.

3. **No direct dependence on λ_target**

   * Once S2 is defined, S3 and S4 MUST NOT read λ_target directly from 5A surfaces to drive counts; they operate exclusively on λ_realised (plus any S2-provided diagnostics if explicitly allowed).

4. **No modification of S2 datasets**

   * S3–S4 MUST NOT overwrite or append to `s2_realised_intensity_5B` or `s2_latent_field_5B`.
   * Any change in latent behaviour or realised intensities MUST be done via:

     * config changes → new `parameter_hash`, and
     * fresh S0/S1/S2 runs for that world.

---

### 8.5 Orchestration-level obligations

Pipeline orchestration MUST:

* treat absence or invalidity of S2 outputs for a given `(ph, mf, seed, scenario_set_5B)` as **“5B not ready for counts/arrivals under this seed”**;
* not invoke S3 or S4 for that `(ph, mf, seed)` until S2 has locally PASSed;
* surface S2’s status and error code (`5B.S2.*`) alongside S0/S1 when diagnosing why arrivals cannot be realised for a world and seed.

Under these acceptance and gating rules, **5B.S2** cleanly owns the step “deterministic λ → λ_realised with correlated noise”. Everything downstream either uses that surface exactly as written or does not run at all.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only failure modes** that **5B.S2 — Latent intensity fields** may surface and the **canonical error codes** it MUST use.

All codes are fatal for S2: if any of these occurs, S2 is **FAIL** for `(parameter_hash, manifest_fingerprint, seed)` and its outputs MUST NOT be used.

All S2 error codes are namespaced as:

> `5B.S2.<CATEGORY>`

Downstream 5B states (S3–S4) and orchestration MUST key on these codes, not free-text messages.

---

### 9.1 Error code catalogue

#### (A) S0 / S1 / 5A prerequisites

1. **`5B.S2.S0_GATE_INVALID`**
   Raised when S2 cannot establish a valid S0 context for `mf`, e.g.:

   * `s0_gate_receipt_5B` or `sealed_inputs_5B` missing,
   * schema invalid, or
   * `sealed_inputs_digest` mismatch between receipt and recomputed digest.

2. **`5B.S2.UPSTREAM_NOT_PASS`**
   Raised when `s0_gate_receipt_5B.upstream_segments` reports any required upstream segment `{1A,1B,2A,2B,3A,3B,5A}` with `status ≠ "PASS"`.

3. **`5B.S2.S1_OUTPUT_MISSING`**
   Raised when, for any `scenario_id ∈ scenario_set_5B`:

   * `s1_time_grid_5B` or `s1_grouping_5B` is missing for `(mf, scenario_id)`, or
   * fails schema validation.

4. **`5B.S2.LAMBDA_SOURCE_MISSING`**
   Raised when the designated 5A λ surface:

   * is not present in `sealed_inputs_5B` with appropriate `status`/`read_scope`, or
   * cannot be resolved via catalogue.

---

#### (B) Config / RNG policy

5. **`5B.S2.LGCP_CONFIG_INVALID`**
   Raised when the arrival/LGCP config:

   * is missing from `sealed_inputs_5B`, or
   * fails schema validation, or
   * lacks required fields (e.g. latent model type, kernel parameters, clipping rules).

6. **`5B.S2.RNG_POLICY_INVALID`**
   Raised when the 5B RNG policy:

   * is missing from `sealed_inputs_5B`, or
   * fails schema validation, or
   * does not specify required fields (stream IDs, substream labels, expected draws/blocks per event).

---

#### (C) Domain & alignment

7. **`5B.S2.DOMAIN_ALIGN_FAILED`**
   Raised when S2 cannot form a consistent domain `D_s` for any `scenario_id`, for example:

   * λ_target rows cannot be joined to S1 grid/grouping by keys,
   * S1 grouping references entities with no λ_target where config requires one,
   * or the mapping from 5A’s bucket coordinate to `s1_time_grid_5B.bucket_index` is ambiguous or impossible.

8. **`5B.S2.BUCKET_SET_INCONSISTENT`**
   Raised when bucket sets implied by 5A and S1 disagree in a way that breaks S2, e.g.:

   * λ_target claims buckets outside the S1 grid,
   * S1 grid buckets have no possible λ_target where config requires coverage.

---

#### (D) Latent-field construction

9. **`5B.S2.KERNEL_CONSTRUCTION_FAILED`**
   Raised when S2 cannot construct a valid latent model for some `(scenario_id, group_id)`, e.g.:

   * covariance matrix is not positive semidefinite when required,
   * kernel parameters from config are invalid (negative variance, non-sensical length-scale).

10. **`5B.S2.LATENT_DOMAIN_INCOMPLETE`**
    Raised when the latent field is not defined over the full bucket set for some `(scenario_id, group_id)`, e.g.:

* missing latent values for some `bucket_index` ∈ `H_s`,
* or the latent vector length disagrees with the grid length.

11. **`5B.S2.LATENT_SCHEMA_INVALID`**
    Raised when `s2_latent_field_5B` is produced but:

* missing required columns,
* fails schema validation,
* contains duplicate `(manifest_fingerprint, parameter_hash, seed, scenario_id, group_id, bucket_index)` keys.

---

#### (E) Realised intensities

12. **`5B.S2.REALISED_SCHEMA_INVALID`**
    Raised when `s2_realised_intensity_5B` fails schema validation against `schemas.5B.yaml#/model/s2_realised_intensity_5B`.

13. **`5B.S2.REALISED_DOMAIN_INCOMPLETE`**
    Raised when, for any `(scenario_id)`:

* some domain elements `(merchant_id, zone_representation[, channel_group], bucket_index)` in `D_s` lack a corresponding row in `s2_realised_intensity_5B`, or
* duplicates exist for the logical PK.

14. **`5B.S2.REALISED_NUMERIC_INVALID`**
    Raised when any row in `s2_realised_intensity_5B` has:

* `lambda_realised` NaN or Inf, or
* `lambda_realised < 0` in violation of config, or
* other numeric violations of configured bounds (e.g. factor outside `[min_factor, max_factor]`) that S2 is obligated to catch.

---

#### (F) RNG accounting & determinism

15. **`5B.S2.RNG_ACCOUNTING_MISMATCH`**
    Raised when latent RNG usage does not match RNG policy, e.g.:

* wrong number of events for `(scenario_id, group_id)`,
* `draws` or `blocks` in events inconsistent with the latent model (too few/many),
* RNG trace log does not reconcile with event log (missing trace entries, overlapping counters).

16. **`5B.S2.NON_DETERMINISTIC_OUTPUT`**
    Raised when a repeat run for the same `(ph, mf, seed)` and inputs produces different latent fields, λ_realised, or RNG logs (as detected by a higher-level consistency check).

---

#### (G) IO / idempotency

17. **`5B.S2.IO_WRITE_FAILED`**
    Raised when S2 cannot atomically write `s2_realised_intensity_5B` or `s2_latent_field_5B` due to I/O issues (filesystem, permissions, partial write).

18. **`5B.S2.IO_WRITE_CONFLICT`**
    Raised when S2 detects existing S2 outputs for `(ph, mf, seed, scenario_id)` that are **not** byte-identical to what it would produce for the same inputs and configs.

In this case S2 MUST NOT overwrite and MUST treat it as an idempotency/consistency violation.

---

### 9.2 Error payload & logging

For any of the error codes above, S2 MUST log or include at least:

* `error_code` (exact string, e.g. `"5B.S2.DOMAIN_ALIGN_FAILED"`),
* `parameter_hash`, `manifest_fingerprint`, `seed`,
* `scenario_id` if the error is scenario-specific,
* and where applicable:

  * offending `segment_id` (for upstream issues),
  * offending `group_id` (for latent domain issues),
  * offending `(merchant_id, zone_representation[, channel_group], bucket_index)` (for realised intensity issues).

Human-readable messages may vary, but tooling MUST rely on `error_code`.

---

### 9.3 Behaviour on failure

On any S2 error:

1. **Abort before downstream work**

   * S2 MUST NOT signal success to orchestration or allow S3/S4 to treat its outputs as usable.
   * S2 MUST NOT allow partial success per scenario or group to be treated as globally PASS for this `(ph, mf, seed)`.

2. **File system state**

   * S2 SHOULD avoid leaving partially written files.
   * If partial files exist due to an I/O error, subsequent runs MUST either:

     * repair by writing fully consistent outputs, or
     * fail again with `5B.S2.IO_WRITE_CONFLICT` or `5B.S2.IO_WRITE_FAILED`, and S3/S4 MUST NOT run.

3. **No upstream or S1 repair**

   * S2 MUST NOT attempt to modify S0/S1 outputs, upstream λ surfaces, or any upstream validation bundles in response to errors; those issues must be resolved upstream or via config.

Under this error model, consumers can safely interpret S2’s status:

* If any `5B.S2.*` error is raised, the latent-field step is **not valid** for that world/seed, and no count or arrival realisation (S3/S4) is permitted until the underlying cause is fixed and S2 is re-run.

---

## 10. Observability & run-report integration *(Binding)*

This section fixes **what 5B.S2 MUST report** and **how it integrates with the engine’s run-report system**. It does not introduce new datasets; it constrains how S2 describes its work.

---

### 10.1 Run-report record for 5B.S2

For every attempted invocation of S2 on
`(parameter_hash = ph, manifest_fingerprint = mf, seed, run_id)`,
the engine MUST emit **one** run-report record with at least:

* `state_id = "5B.S2"`
* `parameter_hash = ph`
* `manifest_fingerprint = mf`
* `seed`
* `run_id`
* `scenario_set = sorted(scenario_set_5B)`
* `status ∈ {"PASS","FAIL"}`
* `error_code` (one of `5B.S2.*`, or `null` if `status = "PASS"`)
* `started_at_utc`
* `finished_at_utc`

Storage location (shared Layer-2 report, per-segment table, etc.) is an implementation detail, but S2 MUST provide these fields.

---

### 10.2 Required structural metrics

For each S2 run (PASS or FAIL), the run-report record MUST include at least the following metrics:

1. **Scenario coverage**

   * `scenario_count_requested = |scenario_set_5B|`
   * `scenario_count_succeeded`

     * number of scenarios for which S2 successfully constructed latent fields and `s2_realised_intensity_5B`.
   * `scenario_count_failed = scenario_count_requested - scenario_count_succeeded`

   For `status = "PASS"`, we expect `scenario_count_succeeded == scenario_count_requested`.

2. **Grid & domain scale**

   Derived from S1+S2 for the scenarios S2 actually processed:

   * `total_bucket_count`

     * Σ over scenarios of `|H_s|` (bucket count per scenario).
   * `total_entity_bucket_count`

     * Σ over scenarios of `|D_s|` (entity×bucket combinations with λ_target).

3. **Grouping & latent-field scale**

   Derived from S1/S2:

   * `total_group_count`

     * Σ over scenarios of number of `group_id` values used.
   * `total_latent_values`

     * Σ over scenarios and groups of `|H_s|` (i.e. total `(scenario, group, bucket)` latent points).
   * If `s2_latent_field_5B` is produced:

     * `latent_field_rows_written` (row count in that dataset).

4. **RNG activity**

   From S2’s RNG event / trace logs:

   * `latent_rng_event_count`

     * total number of latent-field RNG events emitted.
   * `latent_rng_total_draws`

     * sum of `draws` over those events (after converting to integers).
   * `latent_rng_total_blocks`

     * sum of `blocks` over those events.

These metrics MUST be consistent with the final committed S2 datasets and RNG logs when `status = "PASS"`.

---

### 10.3 λ and latent summary statistics (optional but recommended)

For **PASS** runs, S2 SHOULD compute and include basic summary statistics for:

1. **Latent effect (if defined)**

   Over all latent points (either from `s2_latent_field_5B` or reconstructed from S2’s internal structures):

   * `lambda_random_component_min`
   * `lambda_random_component_max`
   * `lambda_random_component_mean`

   And, if latent_gaussian exists:

   * `latent_gaussian_mean`
   * `latent_gaussian_var`

   These are for validation/diagnostics only; they do not change semantics.

2. **λ_realised**

   Over all rows in `s2_realised_intensity_5B`:

   * `lambda_realised_min`
   * `lambda_realised_max`
   * `lambda_realised_mean`

   Optionally stratified by scenario (e.g. min/max/mean per scenario).

These stats SHOULD be included in a structured `details`/`payload` field in the run-report. They MUST not be used as a substitute for formal validation but can help operators detect mis-tuned hyper-parameters or obvious numerical problems.

---

### 10.4 Error reporting integration

On any `status = "FAIL"` with a `5B.S2.*` error code (see §9):

* The run-report record MUST include:

  * `error_code`, and
  * enough contextual fields in the payload to make the failure debuggable, e.g.:

    * failing `scenario_id`,
    * offending `group_id` (for latent domain errors),
    * offending `merchant_id` / `zone_representation` / `bucket_index` (for realised intensity errors),
    * or the name of the missing/misconfigured artefact (for config / λ_source errors).

S2 MUST NOT claim any scenario as “succeeded” in metrics if its latent-field or realised-intensity outputs failed validation.

---

### 10.5 Relationship to downstream gating

Downstream S3–S4 and the 5B validation state MUST use S2’s run-report plus presence of S2 datasets to decide whether to run:

* If `status != "PASS"` or `error_code` is non-null, orchestration MUST treat S2 as failed for `(ph, mf, seed)` and skip S3/S4 for that seed.
* If `status = "PASS"`, downstream states MUST still:

  * verify existence and schema of `s2_realised_intensity_5B` (and `s2_latent_field_5B` if required), and
  * honour S2’s identity/partitioning rules.

Run-report alone is not a substitute for schema validation.

---

### 10.6 Data-plane logging constraints

Because S2 operates on potentially large λ surfaces:

* It MUST NOT log raw rows of `s2_realised_intensity_5B` or λ_target into run-report or standard logs.
* Any example values included in payloads MUST be:

  * minimal and non-sensitive, and
  * clearly marked as samples for debugging (if configured at all).

All detailed, row-level validation (e.g. distribution of λ_realised, correlation checks) belongs either in:

* the dedicated 5B validation / HashGate state, or
* offline analysis tools reading the S2 datasets directly.

Within these constraints, 5B.S2’s observability obligation is to:

> Report whether the latent-field step succeeded, how big it was (groups, buckets, draws), and provide enough structured metrics and error codes for operators and downstream states to make safe decisions about using `λ_realised` for counts and arrivals.

---

## 11. Performance & scalability *(Informative)*

This section is descriptive, not normative. It explains how **5B.S2 — Latent intensity fields** is expected to behave at scale and what knobs exist to keep it tractable.

---

### 11.1 Workload shape

S2’s cost is dominated by two things:

1. **Latent-field work**
   Roughly proportional to:

   ```text
   Σ_scenario |G_s| × |H_s|
   ```

   where:

   * `G_s` = set of `group_id` for scenario `s` (from `s1_grouping_5B`),
   * `H_s` = set of buckets for scenario `s` (from `s1_time_grid_5B`).

   Intuitively: number of **groups × buckets** you’re drawing latent values for.

2. **Realised λ assembly**
   Roughly proportional to:

   ```text
   Σ_scenario |D_s|
   ```

   where `D_s` is the entity×bucket domain (all `(merchant, zone[, channel], bucket)` combinations with λ_target).

In most realistic workloads, `|D_s|` will be significantly larger than `|G_s| × |H_s|`, so S2’s runtime will often feel like “intensity table construction” more than “kernel math”, unless horizons and group counts are very large.

---

### 11.2 Time complexity considerations

The **latent field kernel** choice drives the asymptotic cost:

* **Full covariance per group** (dense Gaussian):

  * naive construction and Cholesky per `(scenario, group)` is `O(|H_s|³)` in bucket count;
  * this becomes expensive for long horizons with fine granularity (e.g. thousands of buckets per scenario).

* **Structured / Markov kernels** (e.g. OU / AR(1) on log-λ):

  * sampling cost per group is `O(|H_s|)`, with simple recursions;
  * this scales well even when `H_s` is large.

The spec doesn’t mandate one or the other, but in practice:

* For **short horizons** or **small |H_s|** (coarse buckets), full covariance may be acceptable.
* For **long horizons** or **fine buckets**, implementations will typically want:

  * Markovian kernels,
  * low-rank or sparse approximations,
  * or other scalable GP approximations.

Whatever algorithm is chosen, it must still respect the logical rules in this spec (one latent effect per group×bucket, deterministic under `(ph, mf, seed)`).

---

### 11.3 Memory & I/O profile

Memory:

* Latent fields can be processed **per scenario** and often **per group**:

  * build latent vector for `(scenario, group)`, apply it, emit rows, discard, and move on.
* The largest in-memory structures are usually:

  * the λ_target + realised λ slice for a single `(scenario)` (over `D_s`), and
  * the kernel factors for the largest `(scenario, group)`.

I/O:

* Reads:

  * S1 grid + grouping (modest),
  * 5A λ surfaces (`ROW_LEVEL`, potentially large),
  * S2 configs and RNG policy (tiny).
* Writes:

  * `s2_realised_intensity_5B` per `(seed, mf, scenario_id)` (can be large),
  * optional `s2_latent_field_5B` per `(seed, mf, scenario_id)` (size ≈ |G_s|×|H_s|).

A natural implementation pattern is:

* Stream through λ_target and grouping by scenario,
* keep only a single scenario (plus one or a few groups) in memory at once,
* write realised λ incrementally in sorted order.

---

### 11.4 Concurrency & scheduling

S2 is highly parallelisable along several axes:

* **Across seeds**

  * Different `seed` values are completely independent runs.

* **Across scenarios for a given world/seed**

  * Different `scenario_id` values can be processed in parallel, as long as filesystem/partition rules are obeyed.

* **Across groups within a scenario**

  * Latent-field sampling for different `group_id` is embarrassingly parallel in many kernel constructions, provided:

    * RNG streams/counters are partitioned correctly across groups;
    * outputs are eventually written in a deterministic order.

Typical safe patterns:

* Serial per `(ph, mf, seed)` with internal parallelism per scenario/group, or
* Coarse-grained parallelism per scenario, with careful coordination of writes and RNG streams.

---

### 11.5 Degradation & tuning levers

If S2 becomes a performance bottleneck, the levers usually live in **config**, not in this state’s control-flow:

* **Bucket duration / grid density**

  * Coarser buckets ⇒ smaller `|H_s|` ⇒ fewer latent points and fewer λ rows.

* **Grouping policy**

  * More pooling (fewer groups) ⇒ fewer latent vectors, but each latent vector affects more entities.
  * Less pooling (more groups) ⇒ more latent vectors but smaller per-group domains.

* **Kernel complexity**

  * Switching from full covariance to Markovian kernels drastically reduces cost when `|H_s|` is large.

* **Diagnostic output**

  * Dropping `s2_latent_field_5B` (or making it optional) saves I/O when you don’t need per-group latent-level analysis.

In short, S2 is typically heavier than S0/S1 but still manageable if you:

* keep horizon × bucket resolution reasonable,
* choose scalable kernel structures, and
* avoid generating more groups than necessary for your modelling story.

---

## 12. Change control & compatibility *(Binding)*

This section defines **how 5B.S2 may evolve** and when a **spec / schema version bump** is required. It binds:

* the S2 behaviour described in this state spec,
* the `schemas.5B.yaml` anchors for S2 datasets,
* the 5B dataset dictionary and artefact registry, and
* downstream 5B states (S3–S4) that depend on S2 outputs.

---

### 12.1 Version signalling

5B as a segment has a single **segment spec version** (e.g. `5B_spec_version`), carried by S0.

For S2:

* S2 does **not** introduce its own separate version; it inherits `5B_spec_version` from S0.
* `s0_gate_receipt_5B` MUST embed `segment_spec_version` (or equivalent), and that version governs S2 semantics as well.
* The dataset dictionary entries for:

  * `s2_realised_intensity_5B`, and
  * `s2_latent_field_5B` (if present)

  MUST include the same `segment_spec_version`.

Downstream 5B states (S3–S4) MUST:

* read `segment_spec_version` from S0 or catalogue, and
* either explicitly support it, or fail fast (e.g. `5B.S3.UNSUPPORTED_SPEC_VERSION`) if they do not.

---

### 12.2 Backwards-compatible changes (allowed with minor bump)

The following are considered **backwards-compatible** for S2 and MAY be made under a **minor** 5B spec bump (e.g. `5B-1.0 → 5B-1.1`), provided schemas, dictionary and registry are updated consistently:

1. **Additive schema fields**

   * Adding new **optional** fields to:

     * `s2_realised_intensity_5B` (e.g. extra diagnostics like `lambda_random_component_log`, `lambda_clipped_flag`, `group_size`), or
     * `s2_latent_field_5B` (e.g. `kernel_id`, `hyperparam_hash`, `group_metadata`).

   These must have clear defaults and must not alter the meaning of existing fields.

2. **Additional metrics / diagnostics**

   * Introducing new optional S2 outputs (e.g. a small per-group summary dataset) registered as `status = OPTIONAL` or `INTERNAL` in `sealed_inputs_5B`.
   * Adding new run-report metrics or structured debug payload fields (e.g. extra λ_realised summaries, correlation diagnostics).

3. **Config / policy extensions with safe defaults**

   * Adding optional parameters to the arrival/LGCP config or RNG policy that:

     * default to current behaviour when omitted, and
     * do not change semantics for existing configurations.

4. **Implementation improvements under same semantics**

   * Changing the internal numerical method used to sample the latent fields (e.g. from exact Cholesky to a numerically more stable equivalent), provided:

     * the resulting latent distribution is the same up to negligible numerical tolerance, and
     * determinism and RNG accounting rules remain unchanged for given `(ph, mf, seed)`.

In all these cases, existing S3–S4 consumers that only rely on the old fields and semantics will continue to behave correctly.

---

### 12.3 Breaking changes (require new major 5B spec)

The following are **breaking** and MUST NOT be made under the same `5B_spec_version`. They require:

* a new **major** 5B spec version (e.g. `5B-1.x → 5B-2.0`), and
* explicit updates to S0/S1/S2/S3/S4 to support the new behaviour.

Breaking changes include, but are not limited to:

1. **Changing λ_realised semantics**

   * Redefining `lambda_realised` so that it no longer has the current “λ_target × lambda_random_component (with optional clipping)” semantics, e.g.:

     * switching from multiplicative to additive noise in intensity space,
     * changing its interpretation from intensity per bucket to something else (e.g. per-time-step probability) without a new version.

2. **Changing latent model class or field representation**

   * Redefining the latent model from, say, log-Gaussian to a fundamentally different model (e.g. heavy-tailed, spike-and-slab) **without** clearly version-gated behaviour.
   * Changing the meaning or type of `lambda_random_component` / `latent_gaussian` in ways that break current or future validation logic.

3. **Partitioning / identity changes**

   * Altering partition keys for S2 datasets (e.g. dropping `seed` or `scenario_id` or adding `run_id` to the partition) under the same spec version.
   * Changing the logical primary key (e.g. allowing multiple rows per `(seed, mf, scenario_id, merchant, bucket)`).

4. **Reinterpreting grouping or grid dependencies**

   * Changing S2 to ignore S1’s grid or grouping and use a different bucket structure or group definition.
   * Making S2’s domain include entities or buckets that do not correspond to S1+5A under the same `(ph, mf, scenario_id)`.

5. **RNG / event semantics changes**

   * Changing the RNG event family names, stream IDs, or draw/block expectations in a way that breaks existing RNG accounting or replay, without explicit dual-support for old and new formats.
   * Changing determinism guarantees (e.g. starting to depend on `run_id` or parallelism ordering in a way that alters outputs for the same `(ph, mf, seed)`).

Whenever such changes are needed, S2 MUST be updated together with:

* an increment of `5B_spec_version`, and
* updated S3–S4 specs that explicitly recognise and consume the new semantics.

---

### 12.4 Interactions with S0, S1, S3 and S4

* **S0**

  * Owns the sealed world and `5B_spec_version`.
  * Any major change to S2 that affects world identity or sealed inputs MUST be reflected in S0’s spec (and version) as well.

* **S1**

  * Owns the time grid and grouping.
  * S2 MUST remain compatible with S1’s contracts: if S1 changes its schema or semantics in a breaking way, S2 MUST be updated in lock-step and versioned accordingly.

* **S3–S4**

  * Own bucket counts and arrivals, respectively.
  * They MUST treat `lambda_realised` from S2 as canonical. Any change in S2 that alters the meaning or domain of λ_realised requires S3–S4 to be updated and gated on the new 5B spec version.

---

### 12.5 Migration principles

When evolving S2:

* Prefer **additive, backwards-compatible** changes:

  * new optional diagnostics,
  * richer hyper-parameter options that default to current behaviour.

* Keep the core contract stable:

  * S1 defines the **grid and grouping**; S2 MUST not move that responsibility.
  * 5A defines **λ_target**; S2 only adds stochastic modulation on top.
  * S2 defines **λ_realised** and latent-field behaviour; S3–S4 rely on it as-is.

* Avoid “silent behaviour drift”: if a change could alter the distribution of λ_realised or latent fields in a way that matters for downstream logic or validation, either:

  * express it as a configuration change under the same spec, with clear documentation and tests, or
  * bump the 5B spec version and update consumers explicitly.

In short:

> Minor, additive enhancements to S2 are allowed under the same world identity and a bumped **minor** 5B spec version.
> Any change that alters λ_realised semantics, latent model class, identity/partitioning, or reliance on S1/5A requires a **new major 5B spec version** and explicit downstream support.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects shorthand used in **5B.S2 — Latent intensity fields**. It does **not** introduce any new behaviour; all binding rules are in §§1–12.

---

### 13.1 Identities & sets

* **`ph`**
  Shorthand for `parameter_hash`. Identifies the parameter pack (including arrival/LGCP config and RNG policy) for this world.

* **`mf`**
  Shorthand for `manifest_fingerprint`. Identifies the sealed world of artefacts for this run.

* **`seed`**
  Global RNG seed for the run. Together with `(ph, mf)` determines the stochastic realisation in S2.

* **`scenario_set_5B` / `sid_set`**
  The set of `scenario_id` values S0 bound 5B to for this `(ph, mf)`.

* **`world_id`**
  `(ph, mf)` — the closed world identity.

* **`stochastic_id`**
  `(ph, mf, seed)` — the identity of a particular stochastic realisation of latent fields / λ_realised.

---

### 13.2 S2 datasets

* **`s2_realised_intensity_5B`**
  Required S2 model dataset. Contains:

  * `lambda_baseline` — deterministic λ from 5A, aligned to S1 grid.
  * `lambda_random_component` — latent multiplicative (or log-scale) factor per entity×bucket.
  * `lambda_realised` — final realised intensity per entity×bucket used by S3.

* **`s2_latent_field_5B`** *(optional)*
  Diagnostic dataset with latent fields at the **group** level, typically:

  * `latent_gaussian` — raw Gaussian latent value, per `(scenario, group, bucket)`.
  * `lambda_random_component` — transformed effect used in intensity space.

---

### 13.3 S1 notions reused in S2

* **`bucket_index`**
  Integer index of a time bucket within a scenario, defined by `s1_time_grid_5B`.

* **`H_s`**
  For a scenario `s`, the ordered set of bucket indices from `s1_time_grid_5B`.

* **`group_id`**
  Group identifier from `s1_grouping_5B`. All entities with the same `(scenario_id, group_id)` share a latent field in S2.

* **`G_s`**
  For a scenario `s`, the set of `group_id` values present in `s1_grouping_5B`.

* **`D_s`**
  For a scenario `s`, the S2 domain of entity×bucket combinations:

  ```text
  D_s = { (merchant_id, zone_representation[, channel_group], bucket_index) }
  ```

  where S1 has a grouping entry and 5A provides λ_target.

---

### 13.4 Intensity & latent notation

* **`λ_target` (`lambda_baseline`)**
  Deterministic intensity from 5A, aligned to S1 grid. This is the mean intensity before stochastic modulation.

* **`λ_realised` (`lambda_realised`)**
  Realised intensity after applying latent effects (and any configured clipping):

  ```text
  lambda_realised = f_intensity(lambda_baseline, lambda_random_component, config)
  ```

* **`ξ(group, bucket)` / `lambda_random_component`**
  Latent modulation factor for a `(group_id, bucket_index)` pair, as derived from the latent model and 5B config. Typically:

  ```text
  lambda_random_component = exp(latent_gaussian)
  ```

  for a log-Gaussian Cox model, but the exact transform is config-driven.

* **`latent_gaussian`**
  The raw Gaussian latent value in the latent space before any transform, per `(scenario_id, group_id, bucket_index)`.

---

### 13.5 Kernel & covariance (conceptual)

These appear in prose, not as fields:

* **`K_s,g(b_i, b_j)`**
  Covariance (or correlation) between bucket indices `b_i` and `b_j` for scenario `s` and group `g`, as defined by the LGCP config (e.g. stationary kernel, OU/AR(1), etc.).

* **`σ²` / `sigma2`**
  Variance parameter for the latent Gaussian process (per group or per kernel family), if used.

* **`ℓ` / `length_scale`**
  Correlation length in “time units” (e.g. buckets or hours/days), if used by the kernel.

These are conceptual; their concrete representation and names live in the LGCP config schema.

---

### 13.6 RNG-related shorthand

* **`stream_id`**
  String ID of the Philox stream reserved for S2 latent draws (e.g. `"arrival_lgcp"`), as defined in the 5B RNG policy.

* **`substream_label`**
  Additional label for the RNG event family used by S2 (e.g. `"latent_vector"`). Combined with `stream_id` to partition RNG usage.

* **`rng_counter_before_{lo,hi}` / `rng_counter_after_{lo,hi}`**
  64-bit halves of the Philox counter before/after an event, as defined by the Layer-wide RNG envelope schema.

* **`draws`**
  Decimal string in event payload indicating how many uniforms were consumed by that event (per Layer-wide RNG law).

* **`blocks`**
  Number of Philox blocks consumed by that event (per the RNG policy).

S2 must follow the global RNG envelope semantics; these names are mentioned here only as shorthand.

---

### 13.7 Error code prefix

All S2 error codes are prefixed:

> **`5B.S2.`**

Examples (see §9 for definitions):

* `5B.S2.S0_GATE_INVALID`
* `5B.S2.S1_OUTPUT_MISSING`
* `5B.S2.LGCP_CONFIG_INVALID`
* `5B.S2.DOMAIN_ALIGN_FAILED`
* `5B.S2.KERNEL_CONSTRUCTION_FAILED`
* `5B.S2.REALISED_NUMERIC_INVALID`
* `5B.S2.RNG_ACCOUNTING_MISMATCH`
* `5B.S2.IO_WRITE_CONFLICT`

Downstream tooling and humans should key off these codes rather than free-text messages.

---

These symbols are for readability only. The binding behaviour of **5B.S2 — Latent intensity fields** is fully defined in §§1–12.

---
