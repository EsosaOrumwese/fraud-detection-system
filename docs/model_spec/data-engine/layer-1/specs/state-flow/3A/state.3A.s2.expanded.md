# State 3A·S2 — Country→Zone Priors & Floors

## 1. Purpose & scope *(Binding)*

State **3A.S2 — Country→Zone Priors & Floors** is the **prior-preparation state** for Segment 3A. It takes the sealed country→zone prior pack and zone floor/bump policy from the governed parameter set, aligns them with the Layer-1 zone universe, and publishes a **single, deterministic authority surface** for the Dirichlet parameters that S3 will sample from.

Concretely, 3A.S2:

* **Loads and normalises country→zone Dirichlet α-priors.**
  For each country `c` in scope, S2:

  * reads the sealed `country_zone_alphas` artefact from the 3A parameter set, containing one or more α values per `(country_iso, tzid)`,
  * aligns those entries with the authoritative zone set `Z(c)` derived from sealed references (e.g. `tz_world_2025a` / 2A’s tz universe), and
  * constructs a cleaned, deterministic α-vector
    [
    \boldsymbol{\alpha}(c) = {\alpha_z(c)}_{z \in Z(c)}
    ]
    that is **complete** (no missing zones in `Z(c)`), **consistent** (no α assigned to zones outside `Z(c)`), and **non-degenerate** (total mass per country is positive and respects the prior schema).

* **Applies zone floor/bump policy deterministically.**
  S2 is responsible for applying 3A’s **zone floor and bump rules** to the prior mass at the country×zone level. Given:

  * a floor/bump policy artefact (e.g. `zone_floor_policy_3A`), and
  * a raw α-vector from `country_zone_alphas`,
    S2 MUST:
  * enforce any specified lower bounds on zone presence (e.g. micro-zones must retain at least some pseudo-count mass if they exist in `Z(c)`),
  * enforce any “bump” behaviour (e.g. prevent high-prior-mass zones from being rounded effectively to zero in later integerisation), and
  * do so **purely deterministically** from the sealed policies and reference surfaces.
    The result is an **effective α-vector** per `(country_iso, tzid)` that already incorporates floor/bump policy, so S3 does not need to interpret those rules again.

* **Publishes a parameter-scoped prior surface for S3.**
  S2’s primary output is a parameter-scoped dataset (e.g. `s2_country_zone_priors`) keyed by `(country_iso, tzid)` under `parameter_hash`, containing for each pair, at minimum:

  * the effective Dirichlet α value `α_z(c)`,
  * the total mass `α_sum(c)`, and
  * optional derived normalised shares (for diagnostics) and policy provenance flags (e.g. whether a floor or bump bound was active).
    This dataset is the **only authority** for the α-vectors that S3 will use when drawing country→zone share vectors; S3 MUST treat S2’s output as read-only truth and MUST NOT re-interpret raw `country_zone_alphas` or floor policies directly.

* **Respects upstream zone and country authority.**
  S2:

  * relies on 3A.S0 outputs (`s0_gate_receipt_3A`, `sealed_inputs_3A`) to ensure that:

    * upstream gates (1A, 1B, 2A) are PASS for the current `manifest_fingerprint`, and
    * the prior pack and floor/bump policy artefacts are fully sealed and schema-valid,
  * treats ingress/2A zone universe definitions (country→set of tzids) as **authority** on which zones actually exist in each country, and
  * does **not** modify those definitions.
    If priors mention zones that do not exist in a country, or omit zones that do, S2’s job is to detect and reconcile this at the **parameter level** (or fail), never to change the upstream zone universe.

* **Defines priors independently of merchant-level detail.**
  S2 operates entirely at the **country×zone** level; it does not depend on:

  * merchant IDs,
  * outlet counts,
  * escalation decisions for specific merchant×country pairs.
    S1’s escalation queue determines *which* countries matter for zone allocation in practice, but S2’s priors are defined purely as functions of:
  * the sealed prior pack,
  * the zone universe per country, and
  * any hyperparameters embedded in the policy.
    This separation ensures that priors are stable and reusable across merchants and runs sharing the same `parameter_hash`.

* **Remains deterministic and RNG-free.**
  3A.S2 MUST NOT consume any Philox stream or call any RNG API. Its behaviour is completely determined by:

  * the current `parameter_hash` (which fixes `country_zone_alphas`, floor/bump policy, and hyperparameters),
  * the sealed input universe from S0, and
  * the upstream zone universe from ingress/2A.
    Re-running S2 for the same `parameter_hash` and catalogue state MUST yield byte-identical outputs for all S2 datasets.

Out of scope for 3A.S2:

* S2 does **not** draw any random zone-share vectors or construct merchant-level zone splits; that is the responsibility of 3A.S3.
* S2 does **not** decide which merchant×country pairs are escalated; that is fixed by 3A.S1.
* S2 does **not** construct any 3A validation bundles or `_passed.flag` surfaces; segment-level PASS for 3A is handled by a later validation state.
* S2 does **not** reason about arrivals, day effects, routing groups or alias tables; those belong to Layer-2 and Segment 2B.

Within these boundaries, 3A.S2’s scope is to provide a **clean, stable, parameter-scoped prior surface** over `(country_iso, tzid)` that reflects the governed 3A priors and floor/bump policies and can be trusted by S3 and validators as the single source of truth for country-level zone priors.

---

## 2. Preconditions & gated inputs *(Binding)*

This section fixes **what MUST already hold** before 3A.S2 can run, and which inputs it is explicitly allowed to read. Anything else is out of scope for S2.

S2 is **parameter-scoped**: its outputs are keyed by `parameter_hash`, not by `seed`. It still runs *in the context* of a manifest (so it can use S0’s sealed inputs), but its artefacts are shared across any runs that share the same `parameter_hash`.

---

### 2.1 Layer-1 and segment-level preconditions

Before 3A.S2 is invoked for a given `parameter_hash`, the orchestrator MUST ensure:

1. **Layer-1 identity is fixed.**

   * `parameter_hash` MUST already have been computed by the Layer-1 mechanism and MUST identify a closed governed parameter set 𝓟.
   * A `manifest_fingerprint` that uses this `parameter_hash` MUST be available; S2 will use this fingerprint only to read 3A.S0 outputs and sealed inputs.
   * `seed` is irrelevant to S2’s *outputs* but may be present in the run context; S2 MUST NOT consume RNG.

2. **3A.S0 has completed successfully for the chosen manifest.**
   For at least one `manifest_fingerprint` compatible with `parameter_hash` (and typically for the specific manifest for which the engine is being prepared):

   * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}` exists and is schema-valid.
   * `sealed_inputs_3A@fingerprint={manifest_fingerprint}` exists and is schema-valid.
   * `s0_gate_receipt_3A.upstream_gates.segment_1A.status == "PASS"`,
     `segment_1B.status == "PASS"`,
     `segment_2A.status == "PASS"`.

   S2 MUST treat the absence or invalidity of either S0 artefact as a **hard precondition failure** and MUST NOT attempt to reconstruct or bypass S0.

3. **Global catalogue is available and well-formed.**

   * `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, and `schemas.3A.yaml` MUST be present and schema-valid.
   * `dataset_dictionary.layer1.{2A,3A}.yaml` and `artefact_registry_{2A,3A}.yaml` MUST be present and schema-valid.
   * S2 MUST resolve all of its inputs via these catalogues; hard-coded paths are out-of-spec.

S2 does **not** require 3A.S1 to have run: priors are defined at the **country×zone** level and are independent of which merchant×country pairs are escalated. Later states (S3/S4) will intersect S2’s priors with S1’s escalation domain.

---

### 2.2 Gated inputs from 3A.S0

3A.S2 MUST treat `s0_gate_receipt_3A` and `sealed_inputs_3A` as its **gate** and **input whitelist**.

1. **Gate descriptor: `s0_gate_receipt_3A`**
   S2 MUST read `s0_gate_receipt_3A` for the chosen `manifest_fingerprint` and:

   * verify it conforms to `schemas.3A.yaml#/validation/s0_gate_receipt_3A`,
   * confirm upstream gates (1A, 1B, 2A) are `"PASS"`, as described above,
   * locate the IDs and `sha256_hex` values of the following policy/prior artefacts in `sealed_policy_set`:

     * `country_zone_alphas` prior pack (name/ID per contracts),
     * `zone_floor` / bump policy artefact,
     * any global hyperparameter packs relevant to priors (e.g. τ, smoothing rules) if present.

2. **Sealed input inventory: `sealed_inputs_3A`**
   For each artefact S2 intends to read, it MUST:

   * find at least one row in `sealed_inputs_3A@fingerprint={manifest_fingerprint}` with matching `logical_id` and `path`,
   * recompute the SHA-256 digest over the artefact bytes, and
   * assert equality with the `sha256_hex` recorded in that row.

If any required artefact is missing from `sealed_inputs_3A`, or if the digests disagree, S2 MUST fail with a sealed-input mismatch and MUST NOT read that artefact anyway.

---

### 2.3 Priors, floors and zone-universe inputs S2 MAY read

Within the sealed input universe from S0, S2 is allowed to read and interpret the following artefacts:

1. **Country→zone α-prior pack (required)**

   * Logical ID (example): `country_zone_alphas_3A` (exact ID defined in 3A contracts).
   * `owner_segment = "3A"`; `role = "country_zone_alphas"`.
   * `schema_ref` MUST point to a dedicated policy schema, e.g. `schemas.3A.yaml#/policy/country_zone_alphas_v1`.

   S2 MUST:

   * validate this artefact against its schema,
   * treat it as the **only authoritative source** of raw α values per `(country_iso, tzid)` for 3A,
   * never modify it in place (any changes require a new `parameter_hash` and S0 re-seal).

2. **Zone floor / bump policy (required)**

   * Logical ID (example): `zone_floor_policy_3A`.
   * `owner_segment = "3A"`; `role = "zone_floor_policy"`.
   * `schema_ref` MUST point to a dedicated policy schema, e.g. `schemas.3A.yaml#/policy/zone_floor_policy_v1`.

   S2 MUST:

   * validate it against its schema,
   * treat it as the only source of floor and bump semantics (e.g. `min_mass_per_zone`, “bump dominant zones to at least ε”),
   * apply its rules deterministically when constructing effective α-vectors.

3. **Optional hyperparameter packs**
   If the design introduces separate hyperparameter artefacts (e.g. a pack containing a global τ, smoothing strategies, etc.), S2 MAY read them, provided they:

   * are part of 𝓟 and listed in both `sealed_policy_set` and `sealed_inputs_3A`, and
   * have dedicated `schema_ref`s in `schemas.3A.yaml`.

   These artefacts MUST be treated as read-only and included in `parameter_hash`.

4. **Zone-universe references (country→zone sets)**
   S2 MAY read sealed reference/2A artefacts that define the **zone universe** per country, including:

   * `iso3166_canonical_2024` (canonical country list).
   * `tz_world_2025a` or equivalent ingress tz geometry:

     * used to derive, for each `country_iso = c`, the set
       [
       Z(c) = {\text{tzid}}
       ]
       of tzids that actually exist in that country.
   * Optionally, a fixed, sealed mapping from country→tzids if such a dataset exists as a Layer-1 reference derived from `tz_world_2025a`.

   S2 MUST treat these references as **authoritative** on whether a `(country_iso, tzid)` combination is even meaningful; priors for zones not in `Z(c)` are invalid.

S2’s core job is to reconcile **priors + floors** with the **zone universe**. It MUST NOT invent additional zones or silently drop zones implied by `Z(c)` unless explicitly governed by policy and clearly reflected in its outputs.

---

### 2.4 Inputs S2 MUST NOT consume

To preserve clean authority boundaries and keep S2 purely parameter-level, S2 is explicitly forbidden from:

1. **Reading merchant- or site-level data.**

   * S2 MUST NOT read 1A `outlet_catalogue`, 1B `site_locations`, or 2A `site_timezones`.
   * Priors are defined at `(country_iso, tzid)` level and MUST NOT depend on merchant IDs, site counts, or S1’s escalation decisions.

2. **Reading 2B plan or runtime artefacts.**

   * No reads of `s1_site_weights`, `s2_alias_index/blob`, `s3_day_effects`, `s4_group_weights`, routing logs, or virtual edge policies.
   * S2’s output is independent of routing; it defines parameter priors only.

3. **Reading any artefact not sealed in `sealed_inputs_3A`.**

   * S2 MUST NOT read config files, reference tables, or policy artefacts that are not present in `sealed_inputs_3A` for the `manifest_fingerprint` used.
   * It MUST NOT read environment variables or local files as implicit configuration knobs that affect priors.

4. **Using S1’s output in its semantics.**

   * S2 MUST NOT use `s1_escalation_queue` as an input to its prior calculations; escalation is a **consumer** of priors, not an input to them.
   * Any intersection between “countries with priors” and “countries actually used by escalated merchant×country pairs” is enforced later, in S3/S4.

5. **Consuming RNG or wall-clock time.**

   * S2 MUST NOT consume Philox streams, generate random numbers, or call any “now()” API; it is strictly deterministic.

---

### 2.5 Invocation-level assumptions

For a specific S2 run:

* The orchestrator MUST provide (or allow S2 to resolve):

  * a `parameter_hash` identifying the prior/floor parameter set;
  * a `manifest_fingerprint` for which 3A.S0 has successfully run and sealed the relevant artefacts.

* S2’s outputs are partitioned by `parameter_hash` only. The same `s2_country_zone_priors` snapshot can and SHOULD be reused across any number of manifests and seeds that share the same parameter set.

If the governed parameter set 𝓟 changes (e.g. new `country_zone_alphas`, new floor policy), Layer-1 MUST produce a new `parameter_hash` and S0 MUST be re-run; S2 MUST then run under the new `parameter_hash` to produce a new, distinct prior surface.

Within these preconditions and gated inputs, S2 has a well-defined, RNG-free view of its inputs and is ready to construct the country→zone prior surface defined in the following sections.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes **exactly what 3A.S2 is allowed to read**, what each input is **authoritative** for, and where S2’s authority **stops**. Anything outside these inputs, or used beyond the roles defined here, is out of spec.

---

### 3.1 Catalogue & S0 inputs (shape + trust)

S2 stands on the same catalogue + gate foundation as S0 and S1. It MUST treat the following as **shape and trust authorities**, not things it can redefine:

1. **Schema packs (shape authority)**

   * `schemas.layer1.yaml`
   * `schemas.ingress.layer1.yaml`
   * `schemas.2A.yaml` (for any zone-related references derived from 2A)
   * `schemas.3A.yaml`

   S2 MAY only use these to:

   * validate the shape of the artefacts it reads (`country_zone_alphas`, floor/bump policy, zone-universe references), and
   * define the shapes of its own outputs via `schema_ref` anchors.

   S2 MUST NOT redefine primitive types, RNG envelopes, or validation receipts defined at Layer-1.

2. **Dataset dictionaries & artefact registries (catalogue authority)**

   * `dataset_dictionary.layer1.{2A,3A}.yaml`
   * `artefact_registry_{2A,3A}.yaml`

   For every dataset/artefact S2 reads or writes, the dictionary/registry pair is the **only authority** on:

   * dataset/artefact ID,
   * path template and partition keys,
   * `schema_ref`,
   * role and lineage.

   S2 MUST resolve paths and schemas via these catalogues; hard-coded paths or anchors are not allowed.

3. **3A.S0 outputs (gate & whitelist)**

   * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`
   * `sealed_inputs_3A@fingerprint={manifest_fingerprint}`

   These artefacts are **authoritative for**:

   * which upstream segments are PASS for this manifest (1A/1B/2A), and
   * which concrete artefacts (datasets/policies/references) 3A is allowed to read for this `manifest_fingerprint`.

   S2 MUST:

   * treat `s0_gate_receipt_3A` as the only evidence of upstream gate status, and
   * treat `sealed_inputs_3A` as the **exclusive whitelist** of admissible inputs; if an artefact isn’t listed there, S2 MUST NOT read it.

S2 has **no authority** to change S0 outputs, to weaken their checks, or to add extra inputs behind S0’s back.

---

### 3.2 Prior & policy artefacts (governed parameter authority)

S2’s job is to transform **governed prior and policy artefacts** into an effective α surface. It MUST treat the following as **binding inputs** for each `parameter_hash`:

1. **Country→zone α-prior pack (`country_zone_alphas`)**

   * Logical ID: e.g. `country_zone_alphas_3A` (exact ID defined in 3A contracts).
   * `owner_segment = "3A"`; `role = "country_zone_alphas"`.
   * `schema_ref`: `schemas.3A.yaml#/policy/country_zone_alphas_v1` (or equivalent).

   Authority:

   * This artefact is the **only source** of raw Dirichlet α values per `(country_iso, tzid)` in Segment 3A.
   * S2 MAY:

     * validate, normalise, combine, and floor these α values to produce an effective α surface, and
     * compute derived diagnostics (e.g. normalised shares, mass buckets).
   * S2 MUST NOT:

     * silently ignore entries in this pack that reference valid `(country_iso, tzid)` in the zone universe, or
     * fabricate α entries that are not implied by this pack and the zone-universe references, except where the floor/bump policy explicitly instructs how to fill missing zones.

   Any change to this artefact’s content that can alter α-vectors MUST go through the parameter set 𝓟 and trigger a new `parameter_hash`.

2. **Zone floor / bump policy (`zone_floor_policy`)**

   * Logical ID: e.g. `zone_floor_policy_3A`.
   * `owner_segment = "3A"`; `role = "zone_floor_policy"`.
   * `schema_ref`: `schemas.3A.yaml#/policy/zone_floor_policy_v1`.

   Authority:

   * Defines all **constraints** on α-vectors at the country×zone level, such as:

     * minimum pseudo-count `α_min` per zone or per `(country_iso, tzid)`,
     * relative floor and “bump” rules (e.g. “if zone is present in Z(c), ensure α_z(c) ≥ ε(c)”, “ensure high-mass zones are not effectively truncated to zero”),
     * ordering rules for how to redistribute mass when enforcing floors.
   * S2 MUST:

     * validate this artefact against its schema,
     * apply its rules deterministically to the raw α-vectors, and
     * reflect any active floor/bump conditions in its outputs (either as flags or via effective α values).
   * S2 MUST NOT:

     * invent extra policy knobs,
     * ignore the policy when constructing α-vectors, or
     * reinterpret the policy semantics beyond what the schema and S2 spec describe.

3. **Optional hyperparameter packs**

   If the parameter set defines additional hyperparameter artefacts (e.g. global τ smoothing, logistic transforms):

   * They MUST be:

     * present in `sealed_policy_set` in `s0_gate_receipt_3A`, and
     * present in `sealed_inputs_3A` with their own `schema_ref`.
   * S2 MAY use them to transform raw α values (e.g. blend with a uniform prior, re-scale α-sums by country) but MUST:

     * remain deterministic, and
     * ensure that any such hyperparameter content changes trigger a new `parameter_hash`.

In all cases, S2 is the **consumer** of these priors/policies. Authority over their content and inclusion in 𝓟 sits above S2 (Layer-1 parameter governance + S0).

---

### 3.3 Zone-universe references (country→tzid authority)

S2 needs to know, for each country, **which zones exist**; it MUST defer to sealed references and 2A’s zone universe for this.

Within the sealed inputs, S2 MAY read:

1. **Country list**

   * `iso3166_canonical_2024` (or equivalent Layer-1 ISO table).

   Authority:

   * Defines the canonical set of `country_iso` codes in Layer-1.
   * S2 MUST validate that any `country_iso` mentioned in priors or floor policies exists here.
   * S2 MUST NOT introduce new country codes not present in this reference.

2. **Zone universe per country**

   At least one of the following (depending on how Layer-1 provides it) MUST be present and sealed:

   * Ingress tz geometry: `tz_world_2025a`, from which S2 can derive per-country tzid sets `Z(c)`; or
   * A pre-derived reference dataset: e.g. `country_tz_universe` with rows `(country_iso, tzid)` that is guaranteed to be consistent with `tz_world_2025a` and/or `tz_timetable_cache`.

   Authority:

   * The combination of ISO + tz-universe reference is the **only authority** on whether a `(country_iso, tzid)` pair is meaningful.
   * S2 MUST:

     * build or read a mapping `Z(c)` per country,
     * ensure that any priors for zones outside `Z(c)` are treated as errors or re-mapped according to explicit policy, and
     * ensure that all zones in `Z(c)` are either assigned α mass or handled by explicit “zero-mass allowed” rules in the policy.
   * S2 MUST NOT:

     * create zones not in `Z(c)`,
     * silently drop zones from `Z(c)` when building α-vectors, unless the policy explicitly says they should have α = 0 and the schema allows this.

3. **2A tzdb cache (optional structural check)**

   * `tz_timetable_cache@fingerprint={manifest_fingerprint}` from 2A.

   Authority:

   * Confirms that any tzid in `Z(c)` belongs to the compiled tzdb universe.
   * S2 MAY use this for sanity checks (e.g. no priors for tzids missing from tzdb), but MUST NOT re-compile tzdb or override 2A’s zone definitions.

Zone-universe references are **structural inputs**, not tunables. S2 consumes them but has no authority to alter them.

---

### 3.4 S2’s authority vs upstream and downstream

S2’s **authority surface** is:

* the effective α-vector per `(country_iso, tzid)`, after applying all of:

  * raw priors from `country_zone_alphas`,
  * floor/bump rules from `zone_floor_policy`, and
  * any hyperparameters in the prior set,

for a given `parameter_hash`.

Within that:

* S2 **owns**:

  * the rules for reconciling the prior pack with the zone universe (as specified in this doc),
  * the exact α-values it publishes in `s2_country_zone_priors`,
  * any derived diagnostic flags (e.g. `floor_applied`, `bump_applied`).

* S2 explicitly does **not** own:

  * merchant×country escalation decisions (`s1_escalation_queue`),
  * per-merchant or per-site routing behaviour (Segment 2B),
  * per-site tzid assignments (Segment 2A).

Downstream:

* 3A.S3 MUST treat `s2_country_zone_priors` as the **sole authority** for α-vectors; it MUST NOT re-interpret `country_zone_alphas` or `zone_floor_policy` directly.
* Validation states MUST replay S3’s Dirichlet behaviour against S2’s published α-vectors, not against raw configs.

Upstream:

* Any change to priors/policy content MUST go through 𝓟 and `parameter_hash` and be sealed via S0; S2 has no authority to “patch” priors on the fly.

---

### 3.5 Explicit “MUST NOT” list for S2

To keep boundaries sharp, S2 is explicitly forbidden from:

* **Reading merchant- or site-level datasets**:
  no `outlet_catalogue`, `site_locations`, `site_timezones`, routing logs, or arrivals.

* **Reading any 2B artefact**:
  no `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`, etc.

* **Reading any artefact not sealed in `sealed_inputs_3A`**:
  no unsealed configs, env vars, or local files that influence priors.

* **Consuming RNG or wall-clock**:
  S2 MUST remain RNG-free; all variance in S2’s outputs across runs is explained by differences in `parameter_hash` or catalogue, not pseudo-randomness.

Within these boundaries, S2’s input world is **precisely defined**:

* Priors and policies from the governed parameter set (𝓟),
* Zone-universe structure from ingress/2A references,
* Gate & whitelist from S0.

Its job is to turn those into a **clean, deterministic α surface** that downstream Dirichlet sampling can trust.

---

## 4. Outputs (datasets) & identity *(Binding)*

3A.S2 is **parameter-scoped**: it produces a single, reusable prior surface keyed by `parameter_hash` that is independent of `seed` and `manifest_fingerprint`. S2 does **not** emit RNG logs or validation bundles.

---

### 4.1 Overview of S2 outputs

For each `parameter_hash`, 3A.S2 MUST produce at most one instance of:

1. **`s2_country_zone_priors`**

   * A parameter-scoped table that, for each `(country_iso, tzid)` in scope, records the **effective Dirichlet α** and related diagnostics after applying:

     * the sealed `country_zone_alphas` prior pack, and
     * the sealed zone floor/bump policy.
   * This dataset is the **only authority** for the α-vectors that S3 will use when drawing country→zone share vectors.

No other persistent outputs are in scope for S2. In particular, S2:

* MUST NOT emit any merchant- or site-level datasets,
* MUST NOT emit any per-country “zones actually used by merchants” datasets (those are derived later by intersecting with S1),
* MUST NOT emit any 3A validation bundles or `_passed.flag` surfaces (segment-level PASS is a later state’s job).

---

### 4.2 Domain & identity of `s2_country_zone_priors`

#### 4.2.1 Domain

Define:

* `C_priors` — the set of countries that appear in the prior/policy universe, i.e. all `country_iso` such that:

  * the `country_zone_alphas` prior pack contains at least one entry for that country, **or**
  * the zone floor/bump policy explicitly references that country or its zones.

* For each `c ∈ C_priors`, let `Z(c)` be the authoritative set of tzids in that country, derived from the sealed zone-universe references (e.g. `tz_world_2025a` / `country_tz_universe`).

Then the **domain** of `s2_country_zone_priors` for a given `parameter_hash` is:

[
D_{\text{S2}} = { (c,z) \mid c \in C_{\text{priors}},\ z \in Z(c) }.
]

S2 MUST ensure:

* For every `(c,z) ∈ D_S2`, there is exactly one row in `s2_country_zone_priors`.
* There are **no rows** for `(c,z)` pairs where `z ∉ Z(c)` or `c ∉ C_priors`.

Later acceptance criteria will additionally require that for any `country_iso` appearing in S1’s escalation domain, the corresponding `(c,z)` rows exist in `s2_country_zone_priors` for all `z ∈ Z(c)`.

#### 4.2.2 Logical primary key

Within a given `parameter_hash` partition:

* Logical primary key:
  [
  (\text{country_iso}, \text{tzid})
  ]

There MUST NOT be duplicate rows for the same `(country_iso, tzid)`.

---

### 4.3 Partitioning & path (conceptual)

` s2_country_zone_priors` is a pure **parameter-scoped** dataset.

* Partition key set:

  ```text
  ["parameter_hash"]
  ```

* Conceptual path template (exact value will be fixed in the dataset dictionary):

  ```text
  data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/...
  ```

* Every row in a given partition MUST have `parameter_hash` equal to the `{parameter_hash}` token in the path (path↔embed equality).

There MUST be at most one `parameter_hash={parameter_hash}` partition for this dataset.

`seed` and `manifest_fingerprint` MUST NOT be used as partition keys for `s2_country_zone_priors`.

---

### 4.4 Required columns & semantics

Each row in `s2_country_zone_priors` MUST contain at least:

* **Lineage / partition**

  * `parameter_hash`

    * Type: `hex64` via `schemas.layer1.yaml#/$defs/hex64`.
    * Identifies the governed parameter set 𝓟 this row belongs to.

* **Identity**

  * `country_iso`

    * Type: `iso2` via `schemas.layer1.yaml#/$defs/iso2`.
    * MUST be present in `iso3166_canonical_2024`.

  * `tzid`

    * Type: `iana_tzid` via `schemas.layer1.yaml#/$defs/iana_tzid`.
    * MUST belong to the zone universe `Z(c)` for this `country_iso`.

* **Prior mass**

  * `alpha_raw`

    * Type: non-negative number (`number`, `minimum: 0.0`).
    * The raw α value for `(country_iso, tzid)` as derived directly from the `country_zone_alphas` pack *before* enforcing floor/bump rules.
    * If the prior pack has no explicit entry for `(c,z)` but policy defines a deterministic default, that default MUST be reflected here.

  * `alpha_effective`

    * Type: strictly positive number (`number`, `exclusiveMinimum: 0.0`) unless the policy explicitly allows zero-mass zones.
    * The final α value for `(country_iso, tzid)` after applying all policy-driven smoothing, floors and bumps.
    * S3 MUST use these `alpha_effective` values when drawing Dirichlet vectors.

  * `alpha_sum_country`

    * Type: strictly positive number (`number`, `exclusiveMinimum: 0.0`).
    * The sum of `alpha_effective` over all zones in this country:
      [
      \alpha_sum_country(c) = \sum_{z \in Z(c)} \alpha_effective(c,z).
      ]
    * Repeated in each row for the same `country_iso` for ease of consumption and validation.

* **Derived share (optional-but-recommended)**

  * `share_effective`

    * Type: number in `[0,1]` with sum per country equal to 1 within a small tolerance.
    * Defined as:
      [
      share_effective(c,z) = \alpha_effective(c,z) / \alpha_sum_country(c).
      ]
    * This is a convenience field; S3 MAY recompute it from `alpha_effective` and `alpha_sum_country`.

* **Policy lineage / diagnostics**

  * `prior_pack_id`

    * Type: `string`; logical ID of the prior pack (e.g. `"country_zone_alphas_3A"`).

  * `prior_pack_version`

    * Type: `string`; version or digest tag of the prior pack used when computing this row.

  * `floor_policy_id`

    * Type: `string`; logical ID of the floor/bump policy artefact.

  * `floor_policy_version`

    * Type: `string`; version or digest tag of the floor/bump policy.

  * `floor_applied`

    * Type: `boolean`; `true` if a floor constraint changed `alpha_effective` relative to `alpha_raw` for this `(country_iso, tzid)`.

  * `bump_applied`

    * Type: `boolean`; `true` if a bump rule (e.g. dominance protection) altered `alpha_effective` for this `(country_iso, tzid)`.

Implementations MAY add more diagnostic fields (e.g. `alpha_before_floor`, `alpha_after_floor_before_bump`, `zone_role`), but MUST NOT change the semantics of the required columns.

---

### 4.5 Writer-sort & immutability

Within each `parameter_hash={parameter_hash}` partition, S2 MUST write rows in a deterministic order, e.g.:

1. `country_iso` ascending (ASCII),
2. `tzid` ascending (ASCII).

This **writer-sort** is:

* required for reproducibility (re-runs produce identical byte layouts), but
* not semantically authoritative; consumers MUST NOT infer meaning from physical order beyond that it is stable.

Once written for a given `parameter_hash`:

* `s2_country_zone_priors` MUST be treated as **immutable**.
* If S2 is re-run for the same `parameter_hash` under an unchanged catalogue and parameter set:

  * the newly computed row set MUST match the existing dataset row-for-row and field-for-field;
  * any difference MUST result in an immutability error, and S2 MUST NOT overwrite the existing artefact.

---

### 4.6 Consumers and role in the 3A authority chain

` s2_country_zone_priors` is an internal-but-authoritative **parameter-level surface**:

* **Required consumers:**

  * 3A.S3 (Dirichlet sampling):

    * MUST construct α-vectors for each country directly from `s2_country_zone_priors`, grouped by `country_iso`,
    * MUST NOT read `country_zone_alphas` or `zone_floor_policy` directly for sampling behaviour.
  * 3A validation state:

    * MUST use `s2_country_zone_priors` to:

      * check that S3’s Dirichlet draws used the correct α-vectors, and
      * verify consistency with the sealed prior pack and floor policy.

* **Optional consumers:**

  * Cross-segment validation/analytics tools MAY use this dataset to:

    * inspect prior mass distributions across countries/zones,
    * monitor how floor/bump rules are affecting priors over time.

` s2_country_zone_priors` is not a public egress dataset; its authority is limited to:

* defining α-vectors for Segment 3A’s Dirichlet sampling, and
* providing a stable audit surface for priors.

---

### 4.7 Explicit non-outputs

For avoidance of doubt, 3A.S2 does **not** introduce:

* any merchant- or site-level priors,
* any per-merchant or per-country “escalation” flags (those belong to S1),
* any RNG logs or receipts,
* any new validation bundles or `_passed.flag` artefacts.

Within this section’s constraints, `s2_country_zone_priors` is the **only dataset** S2 is responsible for, and it is the **sole authority** on effective Dirichlet α-vectors per `(country_iso, tzid)` for a given `parameter_hash`.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section pins down **where S2’s output “lives” in the authority chain**:

* which JSON-Schema anchor defines its row shape,
* how it appears in the Layer-1 dataset dictionary, and
* how it is registered in the 3A artefact registry.

Everything here is normative for **`s2_country_zone_priors`**.

---

### 5.1 Segment schema pack for S2

3A.S2 uses the existing segment schema pack:

* **Schema pack ID:** `schemas.3A.yaml`
* **Role:** shape authority for all Segment-3A datasets (S0–S7).

`schemas.3A.yaml` MUST:

1. Reuse Layer-1 primitive definitions via `$ref: "schemas.layer1.yaml#/$defs/…"`, including:

   * `hex64`, `iso2`, `iana_tzid`, `uint64`, standard numeric types, etc.

2. Define a dedicated anchor for S2’s output:

   * `#/plan/s2_country_zone_priors`

3. Avoid redefining primitives or shared envelopes already present in `schemas.layer1.yaml`.

No other schema pack may define the shape of `s2_country_zone_priors`.

---

### 5.2 Schema anchor: `schemas.3A.yaml#/plan/s2_country_zone_priors`

The anchor `#/plan/s2_country_zone_priors` defines the **row shape** for S2’s prior table.

At minimum, the schema MUST enforce:

* **Type:** `object`

* **Required properties:**

  * `parameter_hash`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `country_iso`

    * `$ref: "schemas.layer1.yaml#/$defs/iso2"`

  * `tzid`

    * `$ref: "schemas.layer1.yaml#/$defs/iana_tzid"`

  * `alpha_raw`

    * `type: "number"`
    * `minimum: 0.0`

  * `alpha_effective`

    * `type: "number"`
    * `exclusiveMinimum: 0.0`
    * (If the design later allows explicit zero-mass zones, this constraint would move into a versioned schema change.)

  * `alpha_sum_country`

    * `type: "number"`
    * `exclusiveMinimum: 0.0`

  * `prior_pack_id`

    * `type: "string"`

  * `prior_pack_version`

    * `type: "string"`

  * `floor_policy_id`

    * `type: "string"`

  * `floor_policy_version`

    * `type: "string"`

  * `floor_applied`

    * `type: "boolean"`

  * `bump_applied`

    * `type: "boolean"`

* **Optional properties (diagnostic / convenience):**

  * `share_effective`

    * `type: "number"`
    * `minimum: 0.0`
    * `maximum: 1.0`
    * If present, consumers MAY assume that for each `country_iso`, these values sum to 1 within numeric tolerance.

  * `notes`

    * `type: "string"` (free-text diagnostics; optional).

  * Future diagnostic fields MAY be added in later MINOR/MAJOR versions as long as they do not change the semantics of the required fields.

* **Additional properties:**

  * At the top level, the schema MUST set:
    `additionalProperties: false`
    to prevent shape drift, except when extended in a future version per §12.

This anchor MUST be used as the `schema_ref` for `s2_country_zone_priors` in the dataset dictionary.

---

### 5.3 Dataset dictionary entry: `dataset_dictionary.layer1.3A.yaml`

The Layer-1 dataset dictionary for subsegment 3A MUST define S2’s dataset as follows (YAML shown conceptually):

```yaml
datasets:
  - id: s2_country_zone_priors
    owner_subsegment: 3A
    description: Parameter-scoped Dirichlet α-vectors per country×tzid.
    version: '{parameter_hash}'
    format: parquet
    path: data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/
    partitioning: [parameter_hash]
    ordering: [country_iso, tzid]
    schema_ref: schemas.3A.yaml#/plan/s2_country_zone_priors
    lineage:
      produced_by: 3A.S2
      consumed_by: [3A.S3, 3A.S4, 3A.S5]
    final_in_layer: false
    pii: false
    licence: Proprietary-Internal
```

Binding points:

* `id` MUST be `s2_country_zone_priors` with `owner_subsegment: 3A`.
* `path` MUST contain `parameter_hash={parameter_hash}` and no additional partition tokens; the dataset is parameter-scoped.
* `partitioning` MUST be exactly `[parameter_hash]`.
* `schema_ref` MUST be `schemas.3A.yaml#/plan/s2_country_zone_priors`.
* `ordering` expresses the deterministic writer-sort (`country_iso`, `tzid`); consumers MUST NOT ascribe extra semantics to file order.

Any alternative ID, path, partitioning scheme or schema_ref for S2’s primary output is out of spec.

---

### 5.4 Artefact registry entry: `artefact_registry_3A.yaml`

For each `parameter_hash` that participates in a manifest, the 3A artefact registry carries an entry of the form:

```yaml
- manifest_key: mlr.3A.s2.country_zone_priors
  name: "Segment 3A S2 country-zone priors"
  subsegment: "3A"
  type: "dataset"
  category: "plan"
  path: data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/
  schema: schemas.3A.yaml#/plan/s2_country_zone_priors
  semver: '1.0.0'
  version: '{parameter_hash}'
  digest: '<sha256_hex>'
  dependencies:
    - mlr.3A.country_zone_alphas
    - mlr.3A.zone_floor_policy
  source: internal
  owner: {owner_team: "mlr-3a-core"}
  cross_layer: true
```

Binding requirements:

* `manifest_key` MUST be `mlr.3A.s2.country_zone_priors`.
* `version` is the instance identifier `{parameter_hash}`; contract versioning is handled via `semver`.
* `path` and `schema` MUST match the dataset dictionary.
* Dependencies MUST include, at minimum, the prior pack artefact and zone-floor policy artefact listed above. If additional artefacts become required, both the registry entry and this spec MUST be updated in lockstep.

The registry entry MUST remain consistent with the dataset dictionary entry and the actual stored dataset (path↔embed equality, digest correctness) so that downstream states and validators can trust it.

---

### 5.5 No additional S2 datasets (in this contract version)

Under this version of the contract:

* 3A.S2 MUST NOT register or emit any additional datasets beyond `s2_country_zone_priors`.
* Any future diagnostic datasets (e.g. `s2_zone_floor_effects`) MUST:

  * be introduced via a schema change in `schemas.3A.yaml` (new anchor),
  * get their own dataset dictionary entries with IDs, paths, and partitioning, and
  * be added to `artefact_registry_3A.yaml` with appropriate `manifest_key` and dependencies.

Until such a change is formally made under §12 (change control & compatibility), `s2_country_zone_priors` is the **only** dataset owned by 3A.S2, and it is the **sole authority** on effective Dirichlet α values per country×zone for a given `parameter_hash`.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section defines the **exact behaviour** of 3A.S2. The algorithm is:

* **Purely deterministic** (no RNG, no wall-clock),
* **Parameter-scoped** (keyed by `parameter_hash`, independent of `seed`),
* **Catalogue-driven** (no hard-coded paths), and
* **Idempotent** (same inputs ⇒ byte-identical outputs).

Given:

* a fixed `parameter_hash` (governed parameter set 𝓟),
* a stable catalogue, and
* at least one `manifest_fingerprint` for which S0 has sealed inputs,

re-running S2 MUST always produce the same `s2_country_zone_priors` for that `parameter_hash`.

---

### 6.1 Phase overview

3A.S2 executes in five phases:

1. **Resolve S0 outputs & catalogue handles.**
   Confirm S0 PASS for a compatible `manifest_fingerprint` and locate the prior/policy artefacts.

2. **Load prior pack, floor policy & zone-universe references.**
   Validate shapes and build a zone-universe mapping `Z(c)` per country.

3. **Derive domain and raw α values per `(country_iso, tzid)`.**
   Construct `alpha_raw(c,z)` over the domain `D_S2`.

4. **Apply floor/bump policy & compute effective α and sums.**
   Compute `alpha_effective(c,z)`, `alpha_sum_country(c)` and optional `share_effective(c,z)`.

5. **Materialise `s2_country_zone_priors` with parameter-scoped partitioning.**
   Write the dataset under `parameter_hash={parameter_hash}`, enforcing idempotence.

No phase may consume RNG or read wall-clock time.

---

### 6.2 Phase 1 — Resolve S0 & catalogue

**Step 1 – Fix identity & reference manifest**

* S2 is invoked with:

  * `parameter_hash` (hex64), identifying the governed parameter set 𝓟.
  * A chosen `manifest_fingerprint` **compatible** with this `parameter_hash` (i.e. whose S0 run sealed the same parameter set).

S2 MUST:

* Validate the format of `parameter_hash` and `manifest_fingerprint` (`hex64`).
* Record them in memory for lineage only; S2’s output is partitioned by `parameter_hash` *only*.

**Step 2 – Load S0 outputs**

Using 3A’s dictionary/registry, S2:

* resolves `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`,
* resolves `sealed_inputs_3A@fingerprint={manifest_fingerprint}`.

S2 MUST:

* read both artefacts,
* validate them against:

  * `schemas.3A.yaml#/validation/s0_gate_receipt_3A`,
  * `schemas.3A.yaml#/validation/sealed_inputs_3A`.

If either is missing or schema-invalid, S2 MUST fail.

**Step 3 – Check upstream gates via S0**

From `s0_gate_receipt_3A.upstream_gates`, S2 MUST confirm:

* `segment_1A.status == "PASS"`,
* `segment_1B.status == "PASS"`,
* `segment_2A.status == "PASS"`.

If any is not `"PASS"`, S2 MUST fail without producing outputs.

**Step 4 – Resolve catalogue artefacts**

S2 MUST load and validate (via Layer-1 schema for catalogue objects):

* `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml`,
* `dataset_dictionary.layer1.{2A,3A}.yaml`,
* `artefact_registry_{2A,3A}.yaml`.

Any missing or malformed catalogue artefact required by S2 MUST cause failure.

---

### 6.3 Phase 2 — Load prior pack, floor policy & zone universe

**Step 5 – Resolve and validate `country_zone_alphas`**

From `s0_gate_receipt_3A.sealed_policy_set` and `sealed_inputs_3A`, S2 MUST locate:

* a unique prior pack artefact with:

  * `role = "country_zone_alphas"` (or agreed role string),
  * `owner_segment = "3A"`.

From the catalogue, S2 resolves:

* `prior_pack_id` (logical ID),
* `prior_pack_path`,
* `prior_pack_schema_ref` (e.g. `schemas.3A.yaml#/policy/country_zone_alphas_v1`).

Then S2 MUST:

* read the artefact contents,
* validate against `prior_pack_schema_ref`,
* recompute the SHA-256 digest of the artefact bytes and assert equality with `sha256_hex` in `sealed_inputs_3A`.

If any of these checks fail, S2 MUST fail.

**Step 6 – Resolve and validate `zone_floor_policy`**

Similarly, S2 MUST locate:

* a unique floor/bump policy artefact with:

  * `role = "zone_floor_policy"`,
  * `owner_segment = "3A"`.

S2 resolves:

* `floor_policy_id`,
* `floor_policy_path`,
* `floor_policy_schema_ref` (e.g. `schemas.3A.yaml#/policy/zone_floor_policy_v1`).

Then:

* read the artefact,
* validate against `floor_policy_schema_ref`,
* recompute `sha256_hex` and compare to `sealed_inputs_3A`.

Failure at this step MUST cause S2 to fail.

**Step 7 – Load zone-universe references**

Using `sealed_inputs_3A` and the catalogue, S2 MUST resolve and load:

* `iso3166_canonical_2024` (or equivalent),
* either:

  * a derived `country_tz_universe` reference dataset, with rows `(country_iso, tzid)`, **or**
  * the ingress tz geometry `tz_world_2025a`, from which S2 can derive `country_tz_universe` deterministically.

S2 MUST:

* validate these references against their schema_refs in `schemas.ingress.layer1.yaml` / `schemas.2A.yaml`,
* assert that every `country_iso` in the prior pack or floor policy appears in `iso3166_canonical_2024`.

**Step 8 – Build `Z(c)` mapping**

S2 constructs an in-memory or streaming view:

* For each `country_iso = c` present in:

  * the prior pack, or
  * the floor policy,

derive the set:

[
Z(c) = {\text{tzid}}
]

from the zone-universe reference:

* If using `country_tz_universe`: collect all `tzid` where `country_iso = c`.
* If deriving from `tz_world_2025a`: apply the agreed Layer-1 rule (e.g. polygon intersection) to determine which tzids belong to each country.

S2 MUST:

* treat `Z(c)` as the authoritative zone set per country,
* fail if any `country_iso` in priors/policies has `Z(c) = ∅` *and* the contract does not explicitly allow countries with no zones (policy must dictate whether this is an error or maps to a special case).

---

### 6.4 Phase 3 — Derive domain & raw α per `(country_iso, tzid)`

**Step 9 – Determine country domain `C_priors`**

Let:

* `C_prior_pack` = set of countries appearing in the prior pack,
* `C_floor_policy` = set of countries appearing in the floor policy (if any per-country rules exist).

Define:

[
C_{\text{priors}} = C_{\text{prior_pack}} \cup C_{\text{floor_policy}}.
]

S2 MUST:

* ensure `C_priors ⊆` the country set in `iso3166_canonical_2024`,
* fail if any `country_iso ∈ C_priors` is not present in the ISO reference.

**Step 10 – Define domain `D_S2`**

Given `C_priors` and `Z(c)` from Step 8, define S2’s domain:

[
D_{\text{S2}} = { (c,z) \mid c \in C_{\text{priors}} \land z \in Z(c) }.
]

S2 MUST produce exactly one row in `s2_country_zone_priors` for each `(c,z) ∈ D_S2`.

**Step 11 – Extract/derive `alpha_raw(c,z)`**

Using the prior pack and its schema, S2 MUST:

* For each `(c,z) ∈ D_S2`:

  1. Find if the prior pack has an explicit entry for `(c,z)`.

     * If yes, extract the raw α value for this pair as prescribed by the prior schema (e.g. directly from a table, or by combining component priors).
  2. If the prior pack has **no explicit entry** for `(c,z)`:

     * Apply the defaulting rule defined in the prior schema, e.g.:

       * `alpha_raw(c,z) = 0`, or
       * `alpha_raw(c,z) = α_default(c)` (country-level default), or
       * another deterministic policy.

* For any `(c,z)` **present in the prior pack** but with `z ∉ Z(c)` (i.e. tzid not in the zone universe for that country), S2 MUST:

  * either map/remap the tzid according to an explicit rule in the prior schema (e.g. aliasing obsolete tzids to new canonical ones), or
  * fail with a zone-universe mismatch error if no such rule exists.

After this step S2 has, for each `(c,z) ∈ D_S2`:

* `alpha_raw(c,z) ≥ 0`.

---

### 6.5 Phase 4 — Apply floor/bump policy & compute effective α

**Step 12 – Compute per-zone floors**

For each `(c,z) ∈ D_S2`, S2 MUST determine a **floor pseudo-count** `floor_alpha(c,z)` from the floor/bump policy, according to its schema. Typical patterns include:

* Global floors per tzid, e.g.
  `floor_alpha(c,z) = φ_z` for all countries where `z ∈ Z(c)`.
* Country-specific overrides, e.g.
  `floor_alpha(c,z) = φ_{c,z}` if explicitly specified, else fallback to `φ_z`.

If no explicit floor applies, the default is:

* `floor_alpha(c,z) = 0`.

S2 MUST compute `floor_alpha(c,z)` deterministically from:

* the floor policy artefact, and
* the zone-universe mapping (which tells us whether `(c,z)` exists).

**Step 13 – Derive effective α per zone**

For each `(c,z) ∈ D_S2`, S2 computes:

[
\alpha_effective(c,z) = \max\big(\alpha_raw(c,z),\ floor_alpha(c,z)\big).
]

This gives a simple, deterministic floor/bump behaviour:

* any zone with raw mass below the floor is “bumped” up to the floor;
* zones above the floor are unchanged by floors.

S2 MUST then set:

* `floor_applied(c,z) = true` if `alpha_effective(c,z) > alpha_raw(c,z)`, else `false`.
* `bump_applied(c,z)` MAY mirror `floor_applied` or encode more detailed policy semantics (if the policy differentiates between “floor due to micro-zone status” and other bumps), but MUST be a deterministic function of `alpha_raw`, `floor_alpha` and any other policy fields.

**Step 14 – Compute per-country sums and shares**

For each `c ∈ C_priors`, S2 computes:

[
\alpha_sum_country(c) = \sum_{z \in Z(c)} \alpha_effective(c,z).
]

S2 MUST ensure:

* `alpha_sum_country(c) > 0` for all `c` (unless the floor/policy schema explicitly allows degenerate zero-mass countries, in which case S2 MUST follow that rule and mark such cases accordingly).

Optionally, S2 computes:

[
share_effective(c,z) = \frac{\alpha_effective(c,z)}{\alpha_sum_country(c)},
]

and stores it in `share_effective`, ensuring it lies in `[0,1]` and sums to 1 per `c` within numeric tolerance.

If `share_effective` is omitted from the dataset, S3 MUST recompute it from `alpha_effective` and `alpha_sum_country` as needed.

---

### 6.6 Phase 5 — Materialise `s2_country_zone_priors`

**Step 15 – Construct rows**

For each `(c,z) ∈ D_S2`, S2 constructs a row with:

* `parameter_hash` — current `parameter_hash`,
* `country_iso = c`,
* `tzid = z`,
* `alpha_raw = alpha_raw(c,z)`,
* `alpha_effective = alpha_effective(c,z)`,
* `alpha_sum_country = alpha_sum_country(c)` (same value repeated for all zones in `c`),
* `share_effective` — if S2 chooses to include it, as per Step 14,
* `prior_pack_id`, `prior_pack_version` — from Step 5 (ID and version/digest of the prior pack),
* `floor_policy_id`, `floor_policy_version` — from Step 6 (ID and version/digest of the floor policy),
* `floor_applied`, `bump_applied` — as per Step 13,
* any additional diagnostic fields that are deterministic functions of the prior pack and floor policy.

S2 MUST have exactly one row per `(c,z)` in `D_S2` and no rows outside `D_S2`.

**Step 16 – Sort and validate**

Using the dataset dictionary entry for `s2_country_zone_priors`:

* Determine the path:
  `data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/...`.

* Sort rows by the declared writer-sort key, e.g.:

  1. `country_iso` ascending,
  2. `tzid` ascending.

* Validate all rows against `schemas.3A.yaml#/plan/s2_country_zone_priors`.

Any validation failure MUST cause S2 to fail before publishing output.

**Step 17 – Idempotent write**

If no dataset exists yet for `parameter_hash={parameter_hash}`:

* S2 writes the new dataset at the configured path with partitioning `["parameter_hash"]`.

If a dataset already exists:

* S2 MUST read it, normalise to the same schema and sort order, and compare row-for-row and field-for-field against the newly computed row set.
* If they are **identical**, S2 MAY:

  * skip writing, or
  * overwrite with byte-identical content (implementation choice).
* If they **differ**, S2 MUST NOT overwrite the existing dataset and MUST raise an immutability violation error.

---

### 6.7 RNG and side-effect discipline

Throughout all phases, S2 MUST:

* **Not consume RNG**

  * No Philox streams, no `u01`, no sampling at all.
  * S2 only prepares deterministic α-vectors; S3 will consume RNG when drawing Dirichlet samples.

* **Not read wall-clock time**

  * Any timestamps associated with S2 (e.g. in run-report) MUST come from the orchestrator or a deterministic run-environment artefact and MUST NOT influence S2’s computations.

* **Not mutate upstream artefacts**

  * S2 MUST NOT alter any input artefacts (priors, policies, references, S0 outputs).
  * Only `s2_country_zone_priors` is written, and only under the idempotence rules above.

* **Fail atomically**

  * On any failure in Steps 1–17, S2 MUST NOT leave partially written, visible `s2_country_zone_priors` artefacts. Writes MUST be atomic or rolled back.

Under this algorithm, for a given `parameter_hash`, 3A.S2 produces a **single, deterministic, parameter-scoped prior surface** over `(country_iso, tzid)` that:

* is fully aligned with the sealed prior pack and floor/bump policy,
* respects the zone universe from ingress/2A, and
* can be relied upon by S3 and validators as the **sole authority** on effective Dirichlet α-vectors for Segment 3A.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how `3A.S2`’s output is **identified**, how it is **partitioned**, what ordering guarantees exist, and what is allowed in terms of **merge / overwrite behaviour**.

Consumers MUST be able to reason purely from:

* `parameter_hash`,
* `(country_iso, tzid)`, and
* documented invariants—

without relying on file layout or implementation details.

---

### 7.1 What a row *is* (logical identity)

For `s2_country_zone_priors`, a row is identified at two levels:

* **Parameter-level identity (run context):**

  * `parameter_hash` — identifies the governed parameter set 𝓟 (priors + floor/bump policy + any hyperparameters).

* **Business-level identity (within a parameter set):**

  * `country_iso` — canonical country code (ISO-3166 alpha-2),
  * `tzid` — canonical IANA time-zone identifier.

**Domain definition**

For a given `parameter_hash`, S2’s domain is:

[
D_{\text{S2}} = { (c,z) \mid c \in C_{\text{priors}} \land z \in Z(c) }
]

where:

* `C_priors` is the union of countries referenced by the prior pack and the floor policy, and
* `Z(c)` is the authoritative zone set for country `c` from the sealed zone-universe references.

Binding requirements:

* `s2_country_zone_priors` MUST contain **exactly one** row for every `(country_iso=c, tzid=z) ∈ D_S2`.
* It MUST NOT contain rows for `(c,z)` pairs outside `D_S2`.

**Logical primary key**

Within each `parameter_hash` partition:

* Logical PK:
  [
  (\text{country_iso}, \text{tzid})
  ]

There MUST NOT be duplicates of this pair.

---

### 7.2 Partitioning law & path tokens

` s2_country_zone_priors` is **parameter-scoped**, not seed- or manifest-scoped.

**Partition keys**

* The partition key set MUST be exactly:

  ```text
  ["parameter_hash"]
  ```

No other partition keys (e.g. `seed`, `fingerprint`, `run_id`) are allowed for this dataset.

**Path template (conceptual)**

From the dataset dictionary:

```text
data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/...
```

Binding rules:

* For any concrete partition, the path MUST include only:

  * `parameter_hash=<hex64>` as a token.
* There MUST be at most one `parameter_hash={parameter_hash}` partition for this dataset.

**Path↔embed equality**

Every row in a given `parameter_hash={H}` partition MUST satisfy:

* `row.parameter_hash == H`

Any mismatch between embedded `parameter_hash` and the partition token MUST be treated as a validation error by both S2 and downstream validators.

---

### 7.3 Uniqueness & per-country invariants

Within a given `parameter_hash` partition, S2 MUST enforce the following invariants:

1. **Uniqueness**

   * `(country_iso, tzid)` MUST be unique across all rows.
   * There MUST NOT be multiple rows for the same `(country_iso, tzid)` pair.

2. **Country membership**

   * Every `country_iso` in the dataset MUST belong to `iso3166_canonical_2024`.
   * For any `country_iso = c`, the set of `tzid` values observed MUST be exactly `Z(c)` as defined by the sealed zone-universe references (no missing zones, no extra zones).

3. **Per-row α constraints**

   For each row:

   * `alpha_raw ≥ 0.0`
   * `alpha_effective > 0.0`
     (unless and until a versioned schema explicitly allows zero-mass zones).
   * `alpha_sum_country > 0.0`

   If `share_effective` is present:

   * `share_effective ∈ [0.0, 1.0]`.

4. **Per-country α-sum consistency**

   For each `country_iso = c`:

   * Let `rows_c` be all rows where `country_iso = c`.
   * All rows in `rows_c` MUST share the same `alpha_sum_country` value.
   * That value MUST equal the sum over zones:

     [
     alpha_sum_country(c) = \sum_{z \in Z(c)} alpha_effective(c,z).
     ]

   If `share_effective` is present:

   * (\sum_{z \in Z(c)} share_effective(c,z)) MUST equal 1 within a specified numeric tolerance.

5. **Policy lineage consistency**

   Within a `parameter_hash` partition:

   * `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version` MUST be constant across **all** rows.
   * These fields MUST match the prior pack and floor policy artefacts sealed in S0 for this `parameter_hash`.

---

### 7.4 Ordering semantics (writer-sort)

Physical file order is **not authoritative** for semantics, but S2 MUST use a deterministic writer-sort for reproducibility.

Inside each `parameter_hash` partition:

* Rows MUST be written sorted by the `ordering` key declared in the dataset dictionary, e.g.:

  1. `country_iso` ascending (ASCII),
  2. `tzid` ascending (ASCII).

Consumers MUST:

* NOT attach any semantic meaning to row order (e.g. “first rows are special”), and
* rely only on the key and field values for all business logic.

The only role of ordering is to ensure that re-running S2 for the same `parameter_hash` produces **byte-identical** outputs.

---

### 7.5 Merge, overwrite & idempotence discipline

` s2_country_zone_priors` is a **single snapshot per `parameter_hash`**. There is no concept of appends or incremental updates for a given parameter set.

**Single snapshot per `parameter_hash`**

* For each `parameter_hash = H`, there MUST be at most one partition with `parameter_hash=H`.
* S2 is the only state allowed to write or update this dataset.

**No row-level merges**

* S2 MUST always construct the full row set for `D_S2` and write it as a single snapshot.
* It MUST NOT:

  * append rows to an existing snapshot,
  * delete or mutate individual rows in-place, or
  * split one logical snapshot across multiple “epochs” at the same `parameter_hash`.

**Idempotent re-writes only**

If a dataset already exists at `parameter_hash=H` when S2 runs:

1. S2 MUST read the existing dataset, normalise it to the same schema and writer-sort, and compare against the newly computed rows.
2. If they are **identical** (row set and field values match exactly):

   * S2 MAY skip writing entirely, or
   * re-write the same bytes; either way, the observable content MUST remain unchanged.
3. If they **differ**:

   * S2 MUST NOT overwrite the dataset, and
   * MUST signal an immutability violation error; this indicates that either:

     * the governed parameter set has changed without updating `parameter_hash`, or
     * a previous S2 implementation produced a different interpretation of the same inputs.

Under no circumstances may S2 silently replace an existing `s2_country_zone_priors` snapshot with a different one for the same `parameter_hash`.

---

### 7.6 Cross-`parameter_hash` semantics

` parameter_hash` partitions represent **distinct parameter universes**. S2 makes no claims about relationships between them:

* Each `parameter_hash = H` defines a complete, closed-world view of `s2_country_zone_priors` for that governed parameter set 𝓟(H).
* Consumers MUST NOT mix rows from different `parameter_hash` values and treat the result as a single coherent prior surface for any one run.

Cross-`parameter_hash` unions are allowed **only for analytics**, e.g.:

* comparing how priors changed between parameter sets,
* monitoring floor/bump usage over time.

Such analytics MUST NOT be used to drive runtime S3 behaviour for a specific `parameter_hash`.

---

### 7.7 Interaction with upstream & downstream identity

**Upstream authority**

* The set of `country_iso` values is owned by `iso3166_canonical_2024`.
* The set of `tzid` values per country is owned by the sealed zone-universe (`Z(c)` as derived from ingress/2A).
* The raw α-values and policy rules are owned by `country_zone_alphas` and `zone_floor_policy`.

S2 MUST:

* respect these identities and domain definitions,
* not alter upstream country or zone identity, and
* not produce priors for non-existent `country_iso` or `tzid`.

**Downstream use**

* 3A.S3 (Dirichlet sampling) MUST consume `s2_country_zone_priors` by:

  * grouping rows by `country_iso` for a given `parameter_hash`, and
  * forming α-vectors (\boldsymbol{\alpha}(c) = {\alpha_effective(c,z)}_{z \in Z(c)}).

* 3A validation MUST:

  * check that S3’s Dirichlet draws used exactly these α-vectors, and
  * ensure no country/zone combination used in S3 is missing from `s2_country_zone_priors` for the relevant `parameter_hash`.

Under these rules, `s2_country_zone_priors` is a clean, parameter-scoped, snapshot-style authority surface: its identity and partitions are clear, its ordering is stable but non-semantic, and its merge discipline ensures that a prior universe for any given `parameter_hash` cannot silently change once published.

---

## 8. Acceptance criteria & validator hooks *(Binding)*

This section defines **when 3A.S2 is considered PASS** for a given `parameter_hash`, and what later validators MUST check.

S2 is **parameter-scoped**: acceptance is per-`parameter_hash`, independent of `seed`/`manifest_fingerprint`. Different manifests may reuse the same priors; S2 only uses a `manifest_fingerprint` to locate S0’s sealed inputs, and MUST emit byte-identical `s2_country_zone_priors` whenever the underlying `parameter_hash` and sealed artefacts are unchanged.

---

### 8.1 Local acceptance criteria for 3A.S2

For a given `parameter_hash`, 3A.S2 is **PASS** if and only if **all** of the following hold:

1. **S0 gate & sealed inputs honoured**

   For at least one compatible `manifest_fingerprint`:

   * `s0_gate_receipt_3A` and `sealed_inputs_3A` exist and are schema-valid.
   * `s0_gate_receipt_3A.upstream_gates.segment_1A.status == "PASS"`,
     `segment_1B.status == "PASS"`,
     `segment_2A.status == "PASS"`.
   * Every artefact S2 reads (`country_zone_alphas`, `zone_floor_policy`, ISO and zone-universe references) appears in `sealed_inputs_3A` with:

     * matching `logical_id` and `path`, and
     * `sha256_hex` equal to the digest S2 computes.

   If any of these checks fail, S2 MUST be treated as FAIL for this `parameter_hash`.

2. **Prior pack and floor policy present & schema-valid**

   * Exactly one prior pack with `role="country_zone_alphas"` is present in `sealed_policy_set` and `sealed_inputs_3A`.
   * Exactly one floor/bump policy with `role="zone_floor_policy"` is present in the same way.
   * Both artefacts validate against their `schema_ref`s (e.g. `#/policy/country_zone_alphas_v1`, `#/policy/zone_floor_policy_v1`).
   * S2 successfully derives:

     * `prior_pack_id`, `prior_pack_version`,
     * `floor_policy_id`, `floor_policy_version`,
       and uses these consistently in all output rows for this `parameter_hash`.

   Missing or schema-invalid priors/policies MUST cause S2 to FAIL.

3. **Country and zone universe are coherent**

   * Every `country_iso` referenced by the prior pack or floor policy appears in `iso3166_canonical_2024` (or equivalent).
   * For each such `country_iso = c`, S2 successfully derives a non-contradictory `Z(c)` from the sealed zone-universe references (e.g. `country_tz_universe` or `tz_world_2025a`), i.e.:

     * there is a finite set of tzids `Z(c)` associated with `c`, and
     * any tzids mentioned in priors/policies for `c` that are not in `Z(c)` are either:

       * mapped according to an explicit alias/remap rule in the prior/policy schema, or
       * treated as configuration errors that cause S2 to FAIL.

   If zone-universe references and priors/policies cannot be reconciled for any country, S2 MUST fail (zone structure inconsistent).

4. **Domain of `s2_country_zone_priors` matches the defined universe**

   Let:

   * `C_priors` be the union of countries referenced by the prior pack and the floor policy.
   * For each `c ∈ C_priors`, `Z(c)` be the set of tzids derived from zone-universe references.
   * `D_S2 = { (c,z) | c ∈ C_priors, z ∈ Z(c) }`.

   Define:

   * `D_table = { (country_iso, tzid) }` as the set of pairs present in `s2_country_zone_priors` for this `parameter_hash`.

   Then S2 is PASS only if:

   * `D_table == D_S2` (set equality):

     * Every `(c,z) ∈ D_S2` appears exactly once in the table, and
     * No extra `(country_iso, tzid)` pairs exist in the table.

5. **Per-row invariants in `s2_country_zone_priors`**

   For every row in `s2_country_zone_priors`:

   * `parameter_hash` equals the partition token.
   * `country_iso` is a valid ISO-3166 code present in the canonical reference.
   * `tzid` is in `Z(country_iso)` for this `parameter_hash`.
   * `alpha_raw ≥ 0.0`.
   * `alpha_effective > 0.0` (unless a future version of the schema explicitly allows zero-mass zones; under this spec, zero is not allowed).
   * `alpha_sum_country > 0.0`.
   * If present, `share_effective ∈ [0.0, 1.0]`.
   * `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version` are non-empty strings and:

     * constant across all rows in this `parameter_hash` partition, and
     * consistent with the IDs/versions sealed in S0.

   Any schema violation, path↔embed mismatch, or inconsistent lineage MUST cause S2 to FAIL.

6. **Per-country α-sum consistency**

   For each `country_iso = c` in the table:

   * All rows with `country_iso = c` share the same value of `alpha_sum_country`.

   * This value equals the sum of `alpha_effective` for that country:

     [
     alpha_sum_country(c) = \sum_{z \in Z(c)} alpha_effective(c,z).
     ]

   * If `share_effective` is present, then for that country:

     [
     \sum_{z \in Z(c)} share_effective(c,z) = 1
     ]

     within an agreed numeric tolerance (e.g. 1e−12 in float64).

   Any country where these equalities do not hold MUST cause a FAIL.

7. **Floor/bump flags consistent with α-values**

   For every row:

   * If `alpha_effective > alpha_raw` then `floor_applied` MUST be `true`.
   * If `alpha_effective == alpha_raw` then `floor_applied` MUST be `false`.
   * `bump_applied` MUST be a deterministic function of:

     * `alpha_raw`, `alpha_effective`,
     * floor policy content, and any additional bump semantics specified therein.

   Exact semantics of `bump_applied` are defined by the floor policy schema, but they MUST NOT contradict the numeric α-values.

8. **Idempotence & immutability**

   * If no dataset exists for `parameter_hash = H`, S2 writes `s2_country_zone_priors` for `H`.
   * If a dataset **does** exist for `parameter_hash = H`:

     * S2 MUST read and normalise it (schema + sort) and compare row-for-row with the newly computed dataset.
     * If they are identical, S2 MAY skip the write or overwrite with identical bytes.
     * If they differ, S2 MUST NOT overwrite and MUST signal an immutability violation.

   S2 is PASS only if the written (or pre-existing) dataset is consistent with the newly computed rows.

Only when **all** criteria 1–8 are met for a given `parameter_hash` may 3A.S2 be marked **PASS**.

---

### 8.2 Validator hooks for 3A validation & cross-checks with S3

A later 3A validation state MUST treat S2 as follows:

1. **Schema & domain validation**

   * Re-validate `s2_country_zone_priors` against `schemas.3A.yaml#/plan/s2_country_zone_priors`.
   * Reconstruct `C_priors` and `Z(c)` using the same sealed artefacts S2 did (`country_zone_alphas`, `zone_floor_policy`, zone-universe references).
   * Recompute `D_S2` and assert `D_table == D_S2` as in §8.1.4.

2. **Policy replay for priors and floors**

   * Read the same prior pack and floor policy artefacts as S2, using `prior_pack_id/prior_pack_version` and `floor_policy_id/floor_policy_version`.

   * For each `(c,z)` in `D_S2`, re-derive:

     * `alpha_raw(c,z)` from the prior pack (including defaulting logic),
     * `floor_alpha(c,z)` from the floor policy schema,
     * `alpha_effective(c,z)` by applying the same max/floor rules,
     * `alpha_sum_country(c)` as the sum across `z ∈ Z(c)`.

   * Compare these replayed values with those in `s2_country_zone_priors` and assert equality within numerical tolerance.

3. **α-vector vs Dirichlet draws (S3 cross-check)**

   When S3 introduces a Dirichlet RNG event family, the validation state MUST:

   * For each country `c` where S3 draws a Dirichlet vector, reconstruct the α-vector:

     [
     \boldsymbol{\alpha}(c) = (\alpha_effective(c,z))_{z \in Z(c)}
     ]

     from `s2_country_zone_priors`.
   * Assert that S3’s Dirichlet draws (as logged in RNG events and/or S3’s internal tables) used exactly these α values and zone ordering.

4. **Aggregate metrics**

   Optionally, the validation state SHOULD compute and record:

   * `countries_total = |C_priors|`
   * `zones_total = |D_S2|`
   * `countries_multi_zone = COUNT(c | |Z(c)| ≥ 2)`
   * `zones_with_floor_applied` = number of `(c,z)` where `floor_applied = true`
   * Derived ratios such as:

     * fraction of zones touched by floors,
     * distribution of `alpha_sum_country` across countries.

These metrics are not themselves acceptance criteria, but they provide hooks for CI thresholds and drift monitoring.

---

### 8.3 Obligations imposed on downstream 3A.S3 and validators

Once S2 is PASS for a given `parameter_hash`, it imposes **mandatory obligations** on:

1. **3A.S3 (Dirichlet sampling)**

   * S3 MUST treat `s2_country_zone_priors` as the **sole authority** on α-vectors for Dirichlet draws.

   * For each country `c` where S3 draws a Dirichlet vector:

     * It MUST obtain the set `Z(c)` and the α values `alpha_effective(c,z)` **from `s2_country_zone_priors`**.
     * It MUST NOT re-parse `country_zone_alphas` or `zone_floor_policy` directly in its sampling logic.
     * It MUST NOT include zones not present in `s2_country_zone_priors` for that `parameter_hash`.

   * If S3 attempts to draw a Dirichlet vector for a country `c` not present in `s2_country_zone_priors` under the current `parameter_hash`, this is a hard error and MUST cause S3 to fail.

2. **3A validation**

   * The 3A validation state MUST include `s2_country_zone_priors` (or at least its digest and schema_ref) in the 3A validation bundle for PASS manifests.
   * It MUST use S2’s outputs to:

     * replay the prior/floor application logic (as in §8.2.2), and
     * verify S3’s Dirichlet draws (as in §8.2.3).

3. **Cross-segment consumers**

   * Any cross-segment or external component (e.g. a diagnostic tool looking at priors) MUST use `s2_country_zone_priors` for effective α-values; raw prior packs or floor policies alone are **not** sufficient to know what priors were actually applied by the engine for this `parameter_hash`.

---

### 8.4 Handling of S2 failures

If any validator (either online in a later state, or offline) detects violation of the acceptance criteria above:

* `s2_country_zone_priors` for that `parameter_hash` MUST be treated as **non-authoritative**.
* Any S3/S4 outputs derived from that prior surface MUST NOT be released or used for model training/evaluation.
* Recovery MUST follow the 3A change-control and parameter governance process:

  * fix configuration or policy schema/content, or
  * fix S2 implementation bugs, then
  * re-run S0 and S2 (and S3/S4 as needed) under a new `parameter_hash` if required.

Under these rules, S2 is only considered **acceptable** when it produces a **coherent, deterministic, and replayable prior surface** that is fully aligned with sealed priors/policies and the zone universe, and when S3 and validators both use that surface as their only α authority.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only allowed failure classes** for 3A.S2 and assigns each a **canonical error code**.

Any S2 implementation MUST:

* end each run in exactly one of:

  * `status="PASS"` with `error_code = null`, or
  * `status="FAIL"` with `error_code` equal to one of the codes below;
* surface that code (plus its required structured fields) into logs and the run-report.

No additional error codes may be introduced without updating this specification.

---

### 9.1 Error taxonomy overview

3A.S2 can fail only for these reasons:

1. S0 gate or sealed inputs are unusable.
2. Catalogue / schema layer malformed or inconsistent.
3. Priors or floor/bump policies missing or invalid.
4. Country/zone universe inconsistent with priors/policies.
5. Domain or α-vector consistency failures.
6. Output schema or lineage inconsistency.
7. Immutability / idempotence violations.
8. Infrastructure / I/O failures.

Each category maps to a specific `E3A_S2_XXX_*` code.

---

### 9.2 S0 / sealed-input failures

#### `E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID`

**Condition**

Raised when S2 cannot rely on 3A.S0 for the chosen `manifest_fingerprint`, e.g.:

* `s0_gate_receipt_3A` or `sealed_inputs_3A` is missing for that fingerprint,
* either artefact fails its own schema validation,
* embedded `manifest_fingerprint` or `parameter_hash` in S0 artefacts does not match the S2 invocation context,
* the S0 artefacts indicate upstream segment gates (1A/1B/2A) are not `"PASS"`.

**Required fields**

* `reason ∈ { "missing_gate_receipt", "missing_sealed_inputs", "schema_invalid", "identity_mismatch", "upstream_gate_not_pass" }`
* If `reason="upstream_gate_not_pass"`:

  * `segment ∈ {"1A","1B","2A"}`
  * `reported_status` — the non-PASS status from S0.

**Retryability**

* **Non-retryable** until S0 is successfully re-run and upstream segments are green for a compatible manifest.

---

### 9.3 Catalogue & schema failures

#### `E3A_S2_002_CATALOGUE_MALFORMED`

**Condition**

Raised when S2 cannot load or validate required catalogue artefacts, e.g.:

* missing or malformed:

  * `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml`,
  * `dataset_dictionary.layer1.2A.yaml`, `dataset_dictionary.layer1.3A.yaml`,
  * `artefact_registry_2A.yaml`, `artefact_registry_3A.yaml`,
* schema validation failures for any of these.

**Required fields**

* `catalogue_id` — identifier of the failing artefact (e.g. `"dataset_dictionary.layer1.3A"`, `"schemas.3A.yaml"`).

**Retryability**

* **Non-retryable** until the catalogue artefact is corrected.

---

### 9.4 Priors & floor policy failures

#### `E3A_S2_003_PRIOR_OR_POLICY_MISSING_OR_AMBIGUOUS`

**Condition**

Raised when S2 cannot obtain a unique required policy/prior artefact for this `parameter_hash`, e.g.:

* no `country_zone_alphas` artefact with the expected role is present in `sealed_policy_set` / `sealed_inputs_3A`,
* no `zone_floor_policy` artefact is present,
* multiple distinct artefacts appear to satisfy a given role and S2 cannot deterministically choose one.

**Required fields**

* `missing_roles[]` — list of missing roles (e.g. `["country_zone_alphas","zone_floor_policy"]`), may be empty.
* `conflicting_roles[]` — list of roles for which multiple candidates were found.
* `conflicting_ids[]` — optional list of conflicting logical IDs (if safe to log).

**Retryability**

* **Non-retryable** without configuration / parameter set changes (fix policy wiring and possibly recompute `parameter_hash` and re-run S0).

---

#### `E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID`

**Condition**

Raised when a required prior or floor policy artefact exists but fails validation against its `schema_ref`, including:

* missing required fields,
* invalid numeric ranges (e.g. negative α where not allowed),
* internal invariants violated (e.g. sum constraints in the prior pack schema).

**Required fields**

* `logical_id` — ID of the invalid artefact (e.g. `"country_zone_alphas_3A"`, `"zone_floor_policy_3A"`).
* `schema_ref` — full schema anchor string.
* `violation_count` — number of validation errors.

**Retryability**

* **Non-retryable** until the artefact content is corrected and, if part of 𝓟, a new `parameter_hash` is computed and sealed via S0.

---

### 9.5 Country/zone universe inconsistencies

#### `E3A_S2_005_ZONE_UNIVERSE_MISMATCH`

**Condition**

Raised when S2 cannot reconcile the country→zone universe with priors/policies, for example:

* a `country_iso` in priors/policies does not exist in `iso3166_canonical_2024`,
* for some `country_iso = c`:

  * `Z(c)` is empty (no tzids found) and the prior/floor policy schema does not define a valid way to handle such a country,
* priors/policies refer to tzids that cannot be mapped into `Z(c)` and no alias/remap rule is defined (e.g. obsolete tzid not present in the zone-universe references).

**Required fields**

* `country_iso` — offending country code (or one representative example if multiple).
* `reason ∈ { "unknown_country", "no_zones_for_country", "unmappable_tzid" }`.
* Optionally `tzid` when `reason="unmappable_tzid"`.

**Retryability**

* **Non-retryable** until either:

  * references (ISO / zone-universe) are fixed, or
  * the prior/floor policy is updated with explicit remap/handling rules, and a new `parameter_hash` is generated.

---

### 9.6 Sealed-input mismatch failures

#### `E3A_S2_006_SEALED_INPUT_MISMATCH`

**Condition**

Raised when S2 detects a mismatch between S0’s sealed-input inventory and the artefacts it reads, e.g.:

* a required artefact (prior pack, floor policy, ISO reference, zone-universe reference) is not present in `sealed_inputs_3A`,
* or S2’s recomputed SHA-256 digest of an artefact’s bytes differs from `sha256_hex` in `sealed_inputs_3A`.

**Required fields**

* `logical_id` — ID of the offending artefact.
* `path` — resolved path S2 attempted to read.
* `sealed_sha256_hex` — digest from `sealed_inputs_3A` (if present).
* `computed_sha256_hex` — digest computed by S2 (if a file existed).

**Retryability**

* **Non-retryable** until the sealed inputs and actual artefacts are reconciled, which may require rerunning S0 or regenerating the manifest.

---

### 9.7 Domain & α-vector consistency failures

#### `E3A_S2_007_DOMAIN_MISMATCH_UNIVERSE`

**Condition**

Raised when the domain of `s2_country_zone_priors` does not match the defined S2 domain `D_S2`, i.e.:

* some `(country_iso, tzid)` pairs in `D_S2` are missing from the table, or
* some pairs in the table are not in `D_S2` (e.g. zones not in `Z(c)`).

Formally, if:

* `D_table = { (country_iso, tzid) }` from `s2_country_zone_priors`,
* `D_S2` from priors/policies + zone-universe,

and `D_table != D_S2`, this error MUST be raised.

**Required fields**

* `missing_pairs_count` — count of `(c,z) ∈ D_S2` missing from the table.
* `extra_pairs_count` — count of `(c,z)` in the table but not in `D_S2`.
* Optionally `sample_country_iso` and `sample_tzid` for diagnostics (subject to logging policies).

**Retryability**

* **Non-retryable** until S2’s domain construction logic or prior/policy configuration is fixed.

---

#### `E3A_S2_008_ALPHA_VECTOR_DEGENERATE_OR_INCONSISTENT`

**Condition**

Raised when α-vector invariants fail, e.g.:

* For some country `c`, `alpha_sum_country(c) <= 0`.
* For some `(c,z)`, `alpha_raw < 0` or `alpha_effective <= 0` in violation of the spec.
* For some country `c`,
  [
  \alpha_sum_country(c) \neq \sum_{z \in Z(c)} \alpha_effective(c,z)
  ]
  beyond numeric tolerance.
* If `share_effective` is present, its per-country sum deviates significantly from 1.

**Required fields**

* `country_iso` — at least one example country where the invariant fails.
* `reason ∈ {"alpha_sum_nonpositive","alpha_negative_or_zero","alpha_sum_mismatch","share_sum_mismatch"}`.
* Optionally `expected` and `observed` values for one failing metric.

**Retryability**

* **Non-retryable** until either:

  * S2’s computations are fixed, or
  * the priors and/or floor policy schema/content are corrected.

---

### 9.8 Output schema & lineage failures

#### `E3A_S2_009_OUTPUT_SCHEMA_INVALID`

**Condition**

Raised when the constructed `s2_country_zone_priors` fails validation against `schemas.3A.yaml#/plan/s2_country_zone_priors`, for example:

* missing required fields (`alpha_effective`, `alpha_sum_country`, etc.),
* invalid types or ranges (e.g. `share_effective` outside [0,1]),
* path↔embed mismatch (`parameter_hash` column not matching the partition token).

S2 MUST validate its output before publishing; this error indicates a violation of this spec.

**Required fields**

* `violation_count` — number of validation errors found.
* Optionally `example_field` — representative field name that failed.

**Retryability**

* **Retryable only after implementation fix**; indicates that the implementation is not conforming to the S2 schema contract.

---

#### `E3A_S2_010_LINEAGE_INCONSISTENT`

**Condition**

Raised when lineage fields in `s2_country_zone_priors` are inconsistent, e.g.:

* `prior_pack_id`/`prior_pack_version` or `floor_policy_id`/`floor_policy_version` differ across rows within the same `parameter_hash` partition,
* these fields do not match the IDs/versions sealed in S0 for the current `parameter_hash`.

**Required fields**

* `field ∈ {"prior_pack_id","prior_pack_version","floor_policy_id","floor_policy_version"}`
* `expected` — value implied by S0 / sealed inputs,
* `observed` — a conflicting value seen in the dataset.

**Retryability**

* **Retryable only after implementation or configuration fix**; indicates either a bug in S2 or a misalignment between parameter governance and S2.

---

### 9.9 Immutability / idempotence failures

#### `E3A_S2_011_IMMUTABILITY_VIOLATION`

**Condition**

Raised when S2 detects that an existing `s2_country_zone_priors` snapshot at `parameter_hash={parameter_hash}` differs from what it would produce for the same `parameter_hash` and catalogue state, e.g.:

* rows differ (missing/extra `(country_iso, tzid)` pairs),
* α-values differ for some `(country_iso, tzid)`,
* lineage fields differ.

**Required fields**

* `difference_kind ∈ {"row_set","field_value"}`
* `difference_count` — number of differing rows detected (may be approximate/capped).

**Retryability**

* **Non-retryable** until conflict is resolved. Operators MUST decide whether:

  * the existing snapshot is authoritative and S2 logic is wrong, or
  * the prior/policy universe changed without updating `parameter_hash`.

Remediation typically involves fixing configuration and/or regenerating the parameter set → new `parameter_hash`.

---

### 9.10 Infrastructure / I/O failures

#### `E3A_S2_012_INFRASTRUCTURE_IO_ERROR`

**Condition**

Raised when S2 cannot complete due to environment-level issues unrelated to logical design, such as:

* transient storage or network unavailability,
* permission errors reading or writing artefacts,
* filesystem or object-store quota exhaustion.

This code MUST NOT be used for any logical failures covered by `E3A_S2_001`–`E3A_S2_011`.

**Required fields**

* `operation ∈ {"read","write","list","stat"}`
* `path` — artefact path involved (if available)
* `io_error_class` — short classification (e.g. `"timeout"`, `"permission_denied"`, `"not_found"`, `"quota_exceeded"`).

**Retryability**

* **Potentially retryable**, subject to infrastructure policy.

  * Orchestration MAY retry automatically, but S2 MUST still satisfy all acceptance criteria (§8) before any output is considered valid.

---

### 9.11 Run-report mapping

As with S0 and S1, each S2 run MUST:

* set `status="PASS"` with `error_code = null`, **or**
* set `status="FAIL"` with `error_code` equal to one of the codes above.

Downstream components MUST treat any `status="FAIL"` for S2 at a given `parameter_hash` as meaning:

* `s2_country_zone_priors` for that `parameter_hash` is **non-authoritative**, and
* 3A.S3 MUST NOT use it to drive Dirichlet sampling until the cause of failure is fixed and S2 has been successfully re-run.

---

## 10. Observability & run-report integration *(Binding)*

This section fixes what **3A.S2 MUST emit** for observability, and how it integrates with the Layer-1 run-report.

Because S2 is **parameter-scoped**, observability must make it clear:

* which `parameter_hash` this prior surface belongs to, and
* which `manifest_fingerprint` was used to resolve S0 / sealed inputs during the run.

S2 MUST NOT log row-level prior values for all countries/zones; observability is summary-level only.

---

### 10.1 Structured logging requirements

3A.S2 MUST emit **structured logs** (e.g. JSON records) for three lifecycle events: **start**, **success**, and **failure**.

#### 10.1.1 State start

Exactly one log event at the beginning of each S2 invocation.

Required fields:

* `layer = "layer1"`
* `segment = "3A"`
* `state = "S2"`
* `parameter_hash` (hex64)
* `manifest_fingerprint_ref` (hex64) — the manifest fingerprint whose S0 outputs / sealed inputs were used as the trust anchor for this run
* `attempt` (integer, if provided by orchestration; otherwise default `1`)

Optional fields:

* `trace_id` (if infrastructure provides a correlation ID)

Log level: `INFO`.

#### 10.1.2 State success

Exactly one log event **only if** S2 meets all acceptance criteria in §8 for this `parameter_hash`.

Required fields:

* All “start” fields above
* `status = "PASS"`
* `error_code = null`
* `countries_total` — number of distinct `country_iso` in `s2_country_zone_priors`
* `zones_total` — number of rows (distinct `(country_iso, tzid)` pairs)
* `countries_multi_zone` — count of countries with `|Z(c)| ≥ 2`
* `zones_with_floor_applied` — count where `floor_applied = true`
* `prior_pack_id`
* `prior_pack_version`
* `floor_policy_id`
* `floor_policy_version`

Recommended additional fields:

* `countries_with_degenerate_raw` — number of countries where raw α-sum was zero or below a configured threshold *before* floors (if S2 tracks this as a diagnostic).
* `fraction_zones_with_floor_applied` — derived ratio.

Optional fields:

* `elapsed_ms` — wall-clock duration of the S2 run, provided by the orchestrator; this MUST NOT influence S2’s logic.

Log level: `INFO`.

#### 10.1.3 State failure

Exactly one log event **only if** S2 terminates without satisfying §8.

Required fields:

* All “start” fields
* `status = "FAIL"`
* `error_code` — one of the `E3A_S2_***` codes from §9
* `error_class` — coarse label for the failure, e.g.

  * `"S0_GATE"`
  * `"CATALOGUE"`
  * `"PRIOR_POLICY"`
  * `"ZONE_UNIVERSE"`
  * `"SEALED_INPUT"`
  * `"DOMAIN_MISMATCH"`
  * `"ALPHA_VECTOR"`
  * `"OUTPUT_SCHEMA"`
  * `"IMMUTABILITY"`
  * `"INFRASTRUCTURE"`
* `error_details` — structured map containing the code-specific fields from §9 (e.g. `country_iso`, `logical_id`, `reason`, etc.)

Recommended additional fields (if reached before failure):

* `countries_total`
* `zones_total`

Optional:

* `elapsed_ms` — if available.

Log level: `ERROR`.

All logs MUST be machine-parseable and MUST NOT contain full dumps of priors or policies (no large YAML/JSON bodies; just IDs, versions and summary counts).

---

### 10.2 Segment-state run-report integration

Layer-1 maintains a **segment-state run-report** (e.g. `run_report.layer1.segment_states`) covering all states, including 3A.S2.

For each S2 invocation, exactly **one row** MUST be written.

Because S2 is parameter-scoped but run in the context of a specific manifest, the run-report row MUST contain at least:

* **Identity & context**

  * `layer = "layer1"`
  * `segment = "3A"`
  * `state = "S2"`
  * `parameter_hash`
  * `manifest_fingerprint_ref` — the fingerprint of the manifest whose S0 outputs were used
  * `attempt` (if available)

* **Outcome**

  * `status ∈ {"PASS","FAIL"}`
  * `error_code` — `null` on PASS; one of §9 on FAIL
  * `error_class` — as in §10.1.3
  * `first_failure_phase` — optional enum in:
    `{ "S0_GATE", "SEALED_INPUTS", "PRIOR_LOAD", "POLICY_LOAD", "ZONE_UNIVERSE", "DOMAIN_BUILD", "ALPHA_COMPUTE", "OUTPUT_WRITE", "IMMUTABILITY", "INFRASTRUCTURE" }`

* **Priors & policy summary**

  * `prior_pack_id`
  * `prior_pack_version`
  * `floor_policy_id`
  * `floor_policy_version`

* **Country/zone summary** (required on PASS; MAY be populated on FAIL if S2 progressed far enough)

  * `countries_total`
  * `zones_total`
  * `countries_multi_zone`
  * `zones_with_floor_applied`
  * `fraction_zones_with_floor_applied`

* **Catalogue versions**
  (mirroring or subset of S0’s catalogue version fields)

  * `schemas_layer1_version`
  * `schemas_3A_version`
  * `dictionary_layer1_3A_version`
  * optionally versions for `dictionary_layer1_2A`, `artefact_registry_3A`.

* **Timing & correlation**

  * `started_at_utc` — as recorded by the orchestrator or a deterministic run-environment artefact; MUST NOT influence S2 logic.
  * `finished_at_utc`
  * `elapsed_ms`
  * `trace_id` — if provided.

The run-report row MUST be:

* consistent with `s2_country_zone_priors` (counts match),
* consistent with S0 artefacts (prior/floor IDs/versions match those sealed in `sealed_policy_set`).

---

### 10.3 Metrics & counters

S2 MUST expose a small set of metrics for monitoring. Names and export mechanisms are implementation details, but semantics are binding.

At minimum:

* `mlr_3a_s2_runs_total{status="PASS"|"FAIL"}`

  * Monotone counter, incremented once per S2 run.

* `mlr_3a_s2_countries_total` (gauge)

  * Number of `country_iso` in the most recent successful S2 run for a given `parameter_hash`.

* `mlr_3a_s2_zones_total` (gauge)

  * Number of `(country_iso, tzid)` pairs in the most recent successful run.

* `mlr_3a_s2_zones_with_floor_applied` (gauge)

  * Count of rows where `floor_applied = true`.

* `mlr_3a_s2_zone_universe_mismatch_total` (counter)

  * Incremented whenever `E3A_S2_005_ZONE_UNIVERSE_MISMATCH` occurs.

* `mlr_3a_s2_prior_or_policy_error_total` (counter)

  * Aggregates `E3A_S2_003_*` and `E3A_S2_004_*` failures.

* `mlr_3a_s2_duration_ms` (histogram)

  * Distribution of S2 run durations.

Labels for these metrics MUST NOT embed raw country or tzid codes. At most, they may be labelled by:

* `state="S2"`,
* `status="PASS"/"FAIL"`,
* `error_class`, or
* coarse buckets (e.g. “zones_total” size class).

---

### 10.4 Correlation & traceability

To support end-to-end tracing across 3A and Layer-1:

1. **Correlation with S0 / S1 / S3**

   * S2’s run-report rows MUST be joinable with S0, S1 and later 3A states via the tuple:

     * `(layer="layer1", segment="3A", parameter_hash, manifest_fingerprint_ref)`
       (plus `seed` where relevant for S1/S3).
   * If a `trace_id` is used, it SHOULD be consistent across all 3A states invoked as part of a larger orchestration for a given parameter set.

2. **Linkage to artefacts and validation bundle**

   * The future 3A validation state MUST:

     * include `s2_country_zone_priors` (or at least its path and `sha256_hex`) in the 3A validation bundle index, and
     * record the `parameter_hash` associated with that snapshot.
   * This allows an auditor to trace from:

     * run-report row →
     * validation bundle →
     * priors surface →
     * sealed prior/policy artefacts and zone-universe references.

---

### 10.5 Retention, access control & privacy

Although S2 operates on **parameter-level** data rather than per-merchant/site data, the following are binding:

1. **Retention**

   * `s2_country_zone_priors` MUST be retained for at least as long as:

     * any 3A/S3/S4 outputs derived from it remain in use, and
     * any models or analysis downstream that depend on those outputs are considered live.
   * Deleting S2’s artefacts while their descendants remain deployed is out-of-spec.

2. **Access control**

   * Access to S2 artefacts (dataset, logs, run-report) SHOULD be limited to principals authorised to see configuration and aggregated zone priors.
   * S2’s observability surfaces MUST NOT expose:

     * raw, full prior pack bodies,
     * explicit α values per zone for all countries in logs/metrics (unless Layer-1 governance explicitly permits this for internal tooling).

3. **No row-level leakage via observability**

   * Logs and metrics MUST NOT enumerate every `(country_iso, tzid)` pair.
   * If sample identifiers are needed for debugging (e.g. in error details for `E3A_S2_005_ZONE_UNIVERSE_MISMATCH`), they MUST respect Layer-1 logging/redaction policy (e.g. limited sampling, no sensitive territories if so classified).

---

### 10.6 Relationship to Layer-1 run-report governance

Any additional run-report requirements defined by Layer-1 (e.g. mandatory columns for all states, retention SLAs, or global error-class vocabularies) take precedence on:

* **schema shape**, and
* any extra required fields.

This section then defines, within that framework, what 3A.S2 MUST populate for its slice of the run-report and how those values must relate to:

* `s2_country_zone_priors`,
* the sealed prior/policy artefacts, and
* the S0 gate and sealed input inventory.

Under these rules, each S2 run is:

* **observable** (via structured logs),
* **summarised** (via a single, parameter-scoped run-report row), and
* **auditable** (via `s2_country_zone_priors` + S0 artefacts + the future 3A validation bundle),

without leaking raw parameter content or undermining the authority chain established by S0 and the Layer-1 catalogue.

---

## 11. Performance & scalability *(Informative)*

This section explains how 3A.S2 behaves at scale and what actually dominates its cost. The binding rules are still in §§1–10; this is just how to think about them operationally.

---

### 11.1 Workload shape

S2 operates **only** on:

* the **prior pack** (`country_zone_alphas`): one or a few entries per `(country_iso, tzid)`,
* the **floor/bump policy**: configuration-sized,
* the **zone-universe mapping**: one entry per `(country_iso, tzid)` that exists,
* the **ISO country list**.

It never touches:

* merchant-level data,
* site-level data,
* arrivals or routing.

So the effective problem size is:

* `#countries` × `#zones_per_country`, not `#merchants` or `#sites`.

Even with a few hundred countries and a few dozen tzids per country, S2 is operating on “thousands to tens of thousands of rows”, not millions.

---

### 11.2 Complexity drivers

The main complexity components:

1. **Zone-universe mapping**

   * Build or read `Z(c)` per country from `country_tz_universe` or `tz_world_2025a`.
   * Complexity: ~O(#countries × #zones_per_country).
   * Done once per `parameter_hash` and can be cached.

2. **Prior unpacking**

   * Scan `country_zone_alphas` and align it to `D_S2 = {(c,z) | c ∈ C_priors, z ∈ Z(c)}`.
   * Complexity: ~O(|D_S2|) to map priors onto the zone-universe grid plus any defaulting logic.

3. **Floor/bump application**

   * For each `(c,z) ∈ D_S2`:

     * compute `alpha_effective = max(alpha_raw, floor_alpha)` and update flags;
     * per-country Σ to get `alpha_sum_country(c)` (another O(|D_S2|) pass).
   * Complexity: linear in |D_S2| with very small constant factors.

4. **Writing `s2_country_zone_priors`**

   * Write ~|D_S2| rows in a single Parquet partition per `parameter_hash`.
   * Again, linear in |D_S2| and typically tiny compared to Layer-1 data volumes.

Net: S2 is essentially O(|D_S2|) and |D_S2| is “countries × zones”, not “outlets”.

---

### 11.3 Memory footprint

S2’s memory needs are dominated by:

* the zone-universe map `Z(c)`,
* a working representation of the prior pack,
* intermediate `alpha_raw` / `alpha_effective` arrays or streaming equivalents.

Even in a pessimistic world:

* ~250 countries × ~50 zones per country = 12,500 rows;
* each row is a handful of floats + strings.

This is easily small enough for in-memory processing in any reasonable deployment.

Still, the spec doesn’t require everything to be loaded at once:

* `country_zone_alphas` and `country_tz_universe` can be processed in **streaming fashion**, deriving `α` and writing rows country-by-country.
* α sums can be computed per-country, then attached to each row in a second streaming pass, without keeping the entire space in memory.

No part of S2 relies on “read the whole thing into RAM then operate”.

---

### 11.4 Reuse across manifests

Because S2 is **parameter-scoped**:

* A given `parameter_hash` is expected to be reused across many Layer-1 manifests and seeds.
* S2 only needs to run once per unique `parameter_hash`:

  * the resulting `s2_country_zone_priors/parameter_hash={parameter_hash}` snapshot can be shared by all S3 runs that use that parameter set.

That means:

* As long as priors/policies don’t change, S2’s cost is amortised across potentially many runs.
* If you tune or version priors/policies, that produces a **new** `parameter_hash`, and S2 runs once to produce a new snapshot.

Operationally: S2 is something you run “once per parameter configuration”, not “once per data run”.

---

### 11.5 Concurrency and parallelism

Even though S2 is already light:

* It is **embarrassingly parallel** across `parameter_hash` values:

  * different parameter sets can run S2 independently.
* Within a single run, you *can* parallelise per-country:

  * split `C_priors` across workers, each computing α for its subset of countries,
  * then concatenate results into the final `s2_country_zone_priors` partition (keeping writer-sort consistent).

This is more a convenience than a necessity; most deployments can run S2 single-threaded without noticing its cost.

---

### 11.6 Expected runtime

In a typical environment:

* **Time to run S2** should be negligible compared to:

  * 1A (NB fitting & sampling),
  * 1B (spatial allocation, jitter),
  * 3A.S1 (group-by over outlets),
  * S3 (Dirichlet sampling per escalated country).

S2’s cost is dominated by:

* reading and validating a handful of policy/prior YAML/JSON artefacts,
* computing α on a few thousand `(country, tzid)` pairs,
* writing a small Parquet file.

It’s designed to be effectively “configuration prep”, not a heavy data-flow state.

---

### 11.7 Tuning levers (non-normative)

Implementers can tune S2 without changing semantics by:

* **Caching zone-universe mappings**

  * If `country_tz_universe` is used, it can be shared across runs.
  * If `tz_world_2025a` is used, pre-derive a stable `country_tz_universe` reference in ingress instead of redoing polygon logic in S2.

* **Separating validation passes**

  * Validate policy/prior artefacts once per `parameter_hash` before computing α (to fail fast) and cache validation results.

* **Streaming writes**

  * Write `s2_country_zone_priors` in a streaming fashion (country-by-country) rather than buffering all rows, if needed.

All of these are implementation choices; the spec cares only that, for a given `parameter_hash`, the resulting `s2_country_zone_priors` is deterministic and meets the invariants in §§7–8.

---

Net effect: S2 is intentionally small and cheap. It’s a parameter-prep step whose complexity is driven by **how many countries and zones you support**, not by how much data you have flowing through the engine.

---

## 12. Change control & compatibility *(Binding)*

This section defines **how the 3A.S2 contract is allowed to evolve**, and what guarantees consumers (S3, validators, tooling) can rely on when:

* the S2 spec changes,
* the prior/floor policy schemas change, or
* the governed parameter set 𝓟 changes (hence `parameter_hash`).

The goal: given `(parameter_hash, version_of_s2_country_zone_priors)`, S3 and validators know **exactly** what α surface they’re getting.

---

### 12.1 Scope of change control

Change control for 3A.S2 covers:

1. The **shape and semantics** of its output dataset:

   * `s2_country_zone_priors`
   * partitioning by `parameter_hash`
   * meaning of `alpha_raw`, `alpha_effective`, `alpha_sum_country`, `share_effective`, `floor_applied`, `bump_applied`.

2. The **mapping** from inputs to outputs:

   * how `C_priors` and `Z(c)` are derived,
   * how `alpha_raw(c,z)` is obtained from `country_zone_alphas`,
   * how floors/bump rules are applied,
   * how sums and shares are computed.

3. The **error taxonomy** and acceptance criteria in §§8–9.

It does **not** govern:

* the internal execution model (single-node vs distributed, streaming vs batch), or
* Layer-1 definitions of `parameter_hash`, `manifest_fingerprint` or S0.

---

### 12.2 S2 contract versioning

The S2 contract has a **dataset version**, carried as:

* `version` in the `dataset_dictionary.layer1.3A.yaml` entry for `s2_country_zone_priors` (e.g. `"1.0.0"`), and
* the matching `version` in the `artefact_registry_3A.yaml` entry `mlr.3A.s2_country_zone_priors`.

Rules:

1. **Single authoritative version.**

   * Dictionary and registry MUST agree on the dataset `version`.
   * Any change to S2’s observable shape or semantics MUST bump this version.

2. **Semver semantics.**

   * `MAJOR.MINOR.PATCH`:

     * **PATCH** (`x.y.z → x.y.(z+1)`): clarifications or bug fixes that do not change outputs for any compliant implementation (e.g. doc fixes, stricter validators that only convert previously “silently bad” runs into FAIL).
     * **MINOR** (`x.y.z → x.(y+1).0`): backwards-compatible extensions (e.g. new optional diagnostic fields, new metrics) that old consumers can ignore safely.
     * **MAJOR** (`x.y.z → (x+1).0.0`): breaking changes (shape, semantics or partitioning) that require S3/validators to change.

3. **Consumers MUST key off version.**

   * Behaviour MUST NOT be inferred from deployment date or binary build ID; consumers MUST rely on dataset `version` + schema_ref to decide how to interpret `s2_country_zone_priors`.

---

### 12.3 Backwards-compatible changes (MINOR/PATCH)

The following are **backwards-compatible** for S2, provided they obey the rules below.

1. **Adding optional columns to `s2_country_zone_priors`.**
   Examples:

   * `alpha_before_floor`,
   * `alpha_after_floor_before_bump`,
   * `zone_role` (e.g. `"dominant"`, `"micro"`, `"standard"`),
   * additional diagnostic flags.

   Conditions:

   * New fields MUST be optional in the schema, with clear “absent = legacy behaviour” semantics.
   * They MUST NOT change the meaning of existing fields.

2. **Adding new metrics / run-report fields.**

   * Additional summary metrics (e.g. “avg alpha_sum per country”) are allowed, as long as they do not affect data-plane behaviour or acceptance criteria.

3. **Adding new error codes.**

   * New `E3A_S2_XXX_*` codes may be added, as long as:

     * existing codes keep their original meaning, and
     * callers treat unknown codes as generic FAIL.

4. **Tightening validation that only affects bad runs.**

   * Stronger checks that:

     * never change which runs are PASS under the old contract, but
     * may convert some previously-invalid-but-silently-accepted runs into FAIL.

These changes MAY require a MINOR bump if schema/run-report shapes change; pure doc/validator clarifications may be PATCH-level.

---

### 12.4 Breaking changes (MAJOR)

The following are **breaking** and MUST trigger a **MAJOR** version bump for `s2_country_zone_priors` (plus co-ordinated changes in S3/validators):

1. **Changing dataset identity or partitioning.**

   * Removing or changing `parameter_hash` as the sole partition key.
   * Adding `seed`, `manifest_fingerprint` or other partition keys.
   * Renaming the dataset ID from `s2_country_zone_priors` or altering its path pattern in a non-compatible way.

2. **Changing the core semantics of α-fields.**

   * Reinterpreting `alpha_effective` as anything other than “the α used for Dirichlet draws after floors/bump”.
   * Changing `alpha_sum_country` to mean something else (e.g. sum of raw α, not effective α).
   * Reusing `share_effective` for a concept other than `alpha_effective / alpha_sum_country`.

3. **Relaxing α invariants.**

   * Allowing `alpha_effective <= 0` for countries/zones that S3 may draw on, without explicitly versioning that behaviour.
   * Allowing `alpha_sum_country <= 0` without making this a hard FAIL.

4. **Relaxing domain invariants.**

   * Allowing `s2_country_zone_priors` to omit `(c,z)` pairs that are in `Z(c)` without failing S2.
   * Allowing rows for zones not in the authoritative `Z(c)`.

5. **Weakening S0 / sealed-input obligations.**

   * Allowing S2 to read priors/policies that are not in `sealed_inputs_3A`.
   * Allowing S2 to run without verifying S0 status and upstream gates.

6. **Relaxing immutability.**

   * Allowing S2 to overwrite a non-identical `s2_country_zone_priors` for the same `parameter_hash` under stable inputs.

Any of these require:

* a MAJOR dataset version bump,
* updated schema(s) in `schemas.3A.yaml`, and
* explicit migration guidance for S3 and validation states.

---

### 12.5 Parameter set evolution vs `parameter_hash`

The governed parameter set 𝓟 includes:

* `country_zone_alphas` prior pack,
* `zone_floor_policy`,
* any hyperparameter packs S2 uses.

Binding rules:

1. **Any semantic change to priors or floor policy MUST change `parameter_hash`.**

   * Modifying the content of `country_zone_alphas` or `zone_floor_policy` in any way that can alter α-vectors MUST be treated as a parameter change and reflected in a new `parameter_hash`.
   * That, in turn, implies a new `s2_country_zone_priors/parameter_hash={new}` snapshot.

2. **S2 MUST NOT “accept” changed priors under the same `parameter_hash`.**

   * If S2’s recomputed digest for `country_zone_alphas` or `zone_floor_policy` does not match the digest sealed in `sealed_inputs_3A` for this `parameter_hash`, S2 MUST fail with a sealed-input mismatch, not proceed.

3. **Adding optional policy knobs.**

   * Adding new optional fields to priors or floor policy (e.g. marking some zones as “debug only”) is compatible provided:

     * the schema is updated appropriately, and
     * they have no effect unless activated, in which case activating them MUST change 𝓟 and `parameter_hash`.

4. **Breaking changes to prior/floor policy schema.**

   * Removing or repurposing fields in the prior or floor policy schemas, or changing their semantics, is governed by the policy specs themselves.
   * If such changes alter the way α-vectors are computed, they require both:

     * a new `parameter_hash` (parameter change), and
     * possibly an S2 MAJOR version bump if S2’s contract is affected (e.g. different α semantics).

---

### 12.6 Catalogue evolution (schemas, dictionary, registry)

S2 depends on Layer-1 catalogue artefacts.

1. **Schema pack evolution (`schemas.3A.yaml`).**

   * Adding optional fields to `#/plan/s2_country_zone_priors` is a MINOR-compatible change.
   * Changing or removing required fields is MAJOR and MUST correspond to a dataset version bump.

2. **Dataset dictionary evolution.**

   * Changing `id`, `path`, `partitioning`, or `schema_ref` of `s2_country_zone_priors` is a **breaking** change and MUST follow §12.4.
   * Adding new datasets (e.g. extra diagnostics) for S2 is compatible; S2’s spec must be updated if it starts producing them.

3. **Artefact registry evolution.**

   * Adding new artefacts unrelated to `s2_country_zone_priors` is compatible.
   * Renaming/removing `mlr.3A.s2_country_zone_priors` or changing its `path`/`schema` fields is a breaking change and MUST be synchronised with a MAJOR dataset version bump.

---

### 12.7 Deprecation policy

When evolving S2:

1. **Introduce before removing.**

   * New behaviour (e.g. new diagnostic columns) SHOULD be added in a MINOR version while keeping old behaviour intact.
   * Downstream code should be given time to adjust before any removal.

2. **Signal deprecation.**

   * The S2 spec (and/or a 3A validation state) MAY include non-normative deprecation notes (e.g. “`share_effective` will be removed in v2.0.0; consumers should recompute it from α”).

3. **Remove only with a MAJOR bump.**

   * Removing fields or relaxing invariants MUST be done in a MAJOR version, coordinated with S3 and validators.

Historic snapshots produced under older versions MUST NOT be rewritten to conform to newer schema; they remain valid under their original contract.

---

### 12.8 Cross-version operation

Multiple S2 versions may coexist across different parameter sets.

1. **Per-`parameter_hash` contract.**

   * For each `parameter_hash`, the `version` of `s2_country_zone_priors` defines the contract governing that slice.
   * S3 and validators MUST interpret each slice according to its own version.

2. **Consumer strategy.**

   * Version-aware consumers (e.g. global analytics) SHOULD:

     * either explicitly support all S2 versions they encounter, or
     * operate on the intersection of fields/semantics common to those versions.

3. **No retroactive upgrades.**

   * Existing `s2_country_zone_priors/parameter_hash={H}` artefacts MUST NOT be mutated to conform to a new S2 version.
   * If there’s a need to “re-run” S2 under a new contract for the same underlying parameters, that MUST be treated as a new parameter set with a new `parameter_hash` and new outputs.

---

Under these rules, 3A.S2 can evolve **safely**:

* Minor changes can add diagnostics or tighten validation without breaking S3.
* Major changes are explicit and versioned.
* Priors/floor policy changes are always tracked via `parameter_hash`, so S3 and validators never see α-vectors that silently shifted under the same parameter identity.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix records the symbols and shorthand used in the 3A.S2 design. It has **no normative force**; it’s here so S2/S3 docs speak the same language.

---

### 13.1 Scalars, hashes & identifiers

* **`parameter_hash`**
  Layer-1 hash over the governed parameter set 𝓟 (priors, floor/bump policy, any hyperparameters). S2 is partitioned by `parameter_hash`.

* **`manifest_fingerprint`**
  Layer-1 manifest hash used by S0 to seal inputs. S2 uses one `manifest_fingerprint` as a **reference** to locate S0 outputs and sealed inputs, but does **not** partition its outputs by it.

* **`country_iso`**
  ISO-3166 alpha-2 code (e.g. `"GB"`, `"US"`), drawn from `iso3166_canonical_2024`.

* **`tzid`**
  IANA time zone identifier (e.g. `"Europe/London"`), as used in 2A and 2B and defined by the Layer-1 tz universe.

---

### 13.2 Sets & domains

* **𝓟 (governed parameter set)**
  The set of all parameter artefacts that participate in `parameter_hash`, at minimum:

  * `country_zone_alphas` prior pack,
  * `zone_floor_policy`,
  * any hyperparameter packs S2 uses.

* **`C_priors` (country domain for priors)**
  Set of countries that appear in priors and/or floor/bump policy:

  [
  C_{\text{priors}} = C_{\text{prior_pack}} \cup C_{\text{floor_policy}},
  ]

  where each set is derived from the artefact content.

* **`Z(c)` (zone universe per country)**
  For a country `c`:

  [
  Z(c) = {\text{tzid} \mid \text{tzid is in the sealed zone universe for country } c}.
  ]

  Derived from `country_tz_universe` or from `tz_world_2025a` + ISO mapping.

* **`D_S2` (S2 domain)**

  The full domain over which S2 defines priors:

  [
  D_{\text{S2}} = { (c,z) \mid c \in C_{\text{priors}},, z \in Z(c) }.
  ]

  `s2_country_zone_priors` has exactly one row per element of `D_S2`.

---

### 13.3 Prior & floor notation

For a given `(country_iso = c, tzid = z)`:

* **`alpha_raw(c,z)`**
  Raw Dirichlet concentration parameter before floors/bump, derived from the `country_zone_alphas` pack (plus any defaulting logic defined by its schema):

  * `alpha_raw(c,z) ≥ 0`.

* **`floor_alpha(c,z)`**
  The floor pseudo-count applied to `(c,z)` by the floor/bump policy:

  * Often a function of global/per-country/per-zone rules,
  * Default is `0` if no floor applies.

* **`alpha_effective(c,z)`**
  Final Dirichlet α used by S3 after applying floors/bump:

  [
  \alpha_effective(c,z) = \max(\alpha_raw(c,z),\ floor_alpha(c,z)).
  ]

  * Under this spec, `alpha_effective(c,z) > 0`.

* **`alpha_sum_country(c)`**

  Total α mass for country `c`:

  [
  \alpha_sum_country(c) = \sum_{z \in Z(c)} \alpha_effective(c,z).
  ]

  * Must be strictly > 0.

* **`share_effective(c,z)`** *(optional convenience field)*

  Normalised share implied by `alpha_effective` for `(c,z)`:

  [
  share_effective(c,z) = \frac{\alpha_effective(c,z)}{\alpha_sum_country(c)}.
  ]

  * If present, per-country sums over `z ∈ Z(c)` should be 1 within numerical tolerance.

---

### 13.4 Policy & artefact identifiers

* **`country_zone_alphas`**
  Logical name for the 3A prior pack artefact (exact ID defined in dictionary/registry). It contains the raw α information and any defaulting/smoothing logic.

* **`zone_floor_policy`**
  Logical name for the floor/bump policy artefact. It governs:

  * minimum allowed pseudo-count per `(country_iso, tzid)` or per tzid,
  * any “bump” rules protecting high-prior zones from being effectively zeroed.

* **`prior_pack_id` / `prior_pack_version`**

  * `prior_pack_id`: logical ID of the prior pack (e.g. `"country_zone_alphas_3A"`).
  * `prior_pack_version`: semver or digest tag associated with that pack.
    Both are repeated in every row of `s2_country_zone_priors`.

* **`floor_policy_id` / `floor_policy_version`**

  * `floor_policy_id`: logical ID of the floor/bump policy artefact.
  * `floor_policy_version`: semver or digest tag for that policy.

* **`s2_country_zone_priors`**
  Parameter-scoped dataset produced by S2, partitioned by `parameter_hash`, containing the fields above per `(country_iso, tzid)`.

---

### 13.5 Flags & diagnostics

For a row `(c,z)` in `s2_country_zone_priors`:

* **`floor_applied`**
  Boolean:

  * `true` if `alpha_effective(c,z) > alpha_raw(c,z)` (a floor/bump changed this zone’s α),
  * `false` otherwise.

* **`bump_applied`**
  Boolean summarising bump-rule activity (e.g. cases where a “dominant” zone was pushed up to a minimum mass for robustness). Exact semantics are defined by the floor policy schema; they MUST be a deterministic function of `alpha_raw`, `alpha_effective` and the policy content.

---

### 13.6 Error codes & status (S2)

* **`error_code`**
  Canonical S2 error code from §9, e.g.:

  * `E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID`
  * `E3A_S2_005_ZONE_UNIVERSE_MISMATCH`
  * `E3A_S2_008_ALPHA_VECTOR_DEGENERATE_OR_INCONSISTENT`
  * `E3A_S2_011_IMMUTABILITY_VIOLATION`

* **`status`**
  S2 outcome in logs/run-report:

  * `"PASS"` — S2 met all acceptance criteria; `s2_country_zone_priors` is authoritative for this `parameter_hash`.
  * `"FAIL"` — S2 terminated with one of the error codes above; its output (if any) MUST NOT be used.

* **`error_class`**
  Coarse category for `error_code`, e.g.:

  * `"S0_GATE"`, `"CATALOGUE"`, `"PRIOR_POLICY"`, `"ZONE_UNIVERSE"`, `"SEALED_INPUT"`, `"DOMAIN_MISMATCH"`, `"ALPHA_VECTOR"`, `"OUTPUT_SCHEMA"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`.

---

These symbols and abbreviations are chosen to align with 3A.S0/S1 and with upstream Layer-1 specs so that when you read across S0 → S1 → S2 → S3, all the notation for `parameter_hash`, `Z(c)`, `α_z(c)`, etc., stays consistent.

---
