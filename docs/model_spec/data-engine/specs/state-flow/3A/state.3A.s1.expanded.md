# State 3A·S1 — Mixture Policy & Escalation Queue

## 1. Purpose & scope *(Binding)*

State **3A.S1 — Mixture Policy & Escalation Queue** is the first data-bearing state in Segment 3A. Its role is to decide, for each **merchant×country** pair, whether that pair should remain **monolithic** (treated as effectively single-zone) or be **escalated** into full zone-level allocation, and to materialise that decision as the **only authority** on which pairs flow into the Dirichlet / integerisation pipeline in later 3A states.

Concretely, 3A.S1:

* **Applies the 3A zone mixture policy deterministically.**
  For each `(merchant_id, legal_country_iso)` that has non-zero outlet mass in 1A, S1:

  * derives the total outlet count `N(m,c)` from 1A’s egress (`outlet_catalogue`), using grouping only;
  * determines the set of IANA tzids present in that country from the sealed reference/2A surfaces (e.g. `tz_world`, `tz_timetable_cache`);
  * applies the **zone mixture policy** (sealed in 3A.S0) to classify the pair as either:

    * **Monolithic** — 3A will **not** run Dirichlet zone allocation for this pair; or
    * **Escalated** — 3A will run Dirichlet zone allocation for this pair in S3/S4.
      S1’s classification is **RNG-free** and must be a deterministic function of sealed inputs and policy parameters.

* **Constructs the 3A escalation queue as an authority surface.**
  S1 produces a dataset (e.g. `s1_escalation_queue`) keyed by `(merchant_id, legal_country_iso)` that, for each pair:

  * records `is_escalated ∈ {true,false}`,
  * records `N(m,c)` and any policy-relevant features (e.g. number of tzids in country, dominant tzid share category, reason codes), and
  * is explicitly marked as the **exclusive authority** on escalation decisions for Segment 3A.
    Later 3A states (S2–S4) MUST derive their worklists exclusively from this queue and MUST NOT re-evaluate the mixture policy independently.

* **Defines the scope of 3A over merchant×country pairs.**
  S1 precisely specifies which merchant×country pairs are in scope for zone allocation:

  * Every `(merchant_id, legal_country_iso)` with outlets in 1A MUST appear exactly once in S1’s output.
  * Only those rows with `is_escalated = true` are eligible to participate in zone-level Dirichlet draws and integerisation in S3/S4.
  * Non-escalated pairs are still part of 3A’s logical domain, but 3A will treat them as single-zone (or defer completely) according to later state specs; S1 does **not** decide which tzid they will map to, only that no split is performed.

* **Respects upstream authority boundaries.**
  S1:

  * relies on 3A.S0 outputs (`s0_gate_receipt_3A`, `sealed_inputs_3A`) as proof that upstream gates (1A/1B/2A) and policies are sealed;
  * treats 1A’s per-merchant per-country counts and 2A’s country/tzid universe as **read-only authority**;
  * does **not** inspect per-site tzids or geometry, and does **not** read any 2B plan or runtime artefacts.
    S1 MUST NOT alter 1A outlet counts, 2A tzid definitions, or any upstream validation artefacts.

* **Remains deterministic and RNG-free.**
  3A.S1 MUST NOT consume any Philox stream, generate random numbers, or depend on wall-clock time. Its behaviour is completely determined by:

  * the sealed input universe from S0,
  * the current `parameter_hash` (which fixes the mixture policy and any thresholds), and
  * upstream egress and reference datasets.
    Re-running S1 for the same `manifest_fingerprint`, `parameter_hash` and catalogue state MUST yield byte-identical outputs.

Out of scope for 3A.S1:

* S1 does **not** construct zone share vectors, perform Dirichlet draws or integerisation across zones; that is the work of later 3A states (S2–S4).
* S1 does **not** write any zone-level allocation egress, routing universe hash, or 3A validation bundles.
* S1 does **not** reason about arrivals, day-effects, or per-arrival routing; those concerns belong to Layer-2 and Segment 2B.

Within these boundaries, 3A.S1’s scope is to provide a **complete, deterministic classification** of merchant×country pairs into monolithic vs escalated and to publish the escalation queue that all subsequent 3A logic must honour.

---

## 2. Preconditions & gated inputs *(Binding)*

This section defines **what MUST already hold** before 3A.S1 can execute, and which inputs it is explicitly allowed to read. Anything not listed here is **out of bounds** for S1.

---

### 2.1 Segment- and layer-level preconditions

Before 3A.S1 is invoked for a given triple `(parameter_hash, manifest_fingerprint, seed)`, the orchestrator MUST ensure:

1. **Layer-1 identity is fixed.**

   * `parameter_hash` and `manifest_fingerprint` have already been resolved by Layer-1 S0 and conform to the layer-wide definitions.
   * `seed` is fixed for the run and consistent with the rest of Layer-1; S1 itself remains RNG-free but will embed `seed` in lineage where required.

2. **3A.S0 has completed successfully for this `manifest_fingerprint`.**

   * Artefacts:

     * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`
     * `sealed_inputs_3A@fingerprint={manifest_fingerprint}`
       MUST exist and MUST be schema-valid under `schemas.3A.yaml#/validation/s0_gate_receipt_3A` and `#/validation/sealed_inputs_3A`.
   * S1 MUST treat the absence or invalidity of either artefact as a **hard precondition failure**; it MUST NOT attempt to reconstruct or bypass them.

3. **Upstream segment gates are green (via S0).**

   * S1 MUST NOT re-implement HashGate checks for segments 1A, 1B, or 2A.
   * Instead, it MUST verify, by reading `s0_gate_receipt_3A`, that:

     * `upstream_gates.segment_1A.status == "PASS"`,
     * `upstream_gates.segment_1B.status == "PASS"`,
     * `upstream_gates.segment_2A.status == "PASS"`.
   * If any upstream gate status is not `"PASS"`, S1 MUST treat this as a **precondition violation** and fail without producing outputs.

4. **3A mixture policy is part of the governed parameter set.**

   * The zonal mixture policy artefact (e.g. `zone_mixture_policy_3A`) MUST:

     * be present in `sealed_inputs_3A` with `owner_segment="3A"` and an appropriate `role` (e.g. `"zone_mixture_policy"`), and
     * be listed in `s0_gate_receipt_3A.sealed_policy_set` with a matching `sha256_hex`.
   * If the mixture policy is missing from either S0 output, S1 MUST NOT run.

These preconditions are **binding**: S1 MUST fail fast if any are not met and MUST NOT attempt to proceed “best effort”.

---

### 2.2 Gated inputs from 3A.S0

3A.S1 MUST treat the S0 outputs as its **primary gate** and **input catalogue**.

1. **Gate descriptor (`s0_gate_receipt_3A`).**

   * S1 MUST read `s0_gate_receipt_3A` for the current `manifest_fingerprint` and use it to:

     * confirm upstream gate PASS status (as above),
     * know which schema packs, dictionaries and registries were in force, and
     * know which policy/prior artefacts comprise the sealed 3A parameter set.

2. **Sealed input inventory (`sealed_inputs_3A`).**

   * For any artefact S1 wishes to read (1A egress, references, mixture policy), S1 MUST first confirm that:

     * there exists at least one row in `sealed_inputs_3A` with matching `logical_id` and `path`, and
     * that row’s `sha256_hex` matches a freshly computed digest of the concrete artefact.
   * If an artefact needed by S1 is **not** present in `sealed_inputs_3A`, S1 MUST treat this as a precondition failure rather than reading it anyway.

S1 MUST NOT read any artefact that is not listed in `sealed_inputs_3A` for the current `manifest_fingerprint`.

---

### 2.3 Data-plane inputs S1 is allowed to use

Within the sealed universe defined by S0, S1 is allowed to read and interpret the following artefacts:

1. **1A outlet counts (aggregated only).**

   * 1A egress dataset: `outlet_catalogue@seed={seed}/fingerprint={manifest_fingerprint}`.
   * S1 MAY read this dataset but MUST only use it to derive **merchant×country counts**:

     * For each `(merchant_id, legal_country_iso)`, compute `N(m,c) = COUNT(*)`.
   * S1 MUST NOT:

     * read or depend on any per-site fields beyond what is required to perform the group-by,
     * attempt to alter, re-emit, or reinterpret 1A’s counts (e.g. no re-integerisation).

2. **Ingress and 2A reference geometry for zone presence.**
   S1 MAY read the following reference surfaces, provided they are sealed in `sealed_inputs_3A`:

   * `iso3166_canonical_2024` (or equivalent) to determine the canonical set of countries used in Layer-1.
   * `tz_world_2025a` (or its Layer-1 ingress equivalent) to derive, per `legal_country_iso`, the set of IANA tzids present in that country according to ingress geometry.
   * Optionally, 2A’s `tz_timetable_cache` manifest to validate that any tzids considered by policy for a country exist in the compiled tz universe.

   S1 MUST treat these surfaces as **read-only reference**; it MUST NOT attempt to modify or re-compile tzdb.

3. **3A zone mixture policy.**

   * The mixture policy artefact (e.g. YAML or JSON) that defines:

     * conditions under which a `(merchant_id, legal_country_iso)` pair is considered **eligible for escalation**, and
     * any thresholds or classification rules used in deciding monolithic vs escalated.
   * This artefact MUST have:

     * a `schema_ref` into `schemas.3A.yaml` (e.g. `#/policy/zone_mixture_policy_3A`), and
     * a corresponding row in both `sealed_inputs_3A` and `sealed_policy_set`.

S1’s business logic MUST be expressed purely in terms of these inputs and constants derived from them. It MUST NOT introduce new external inputs (env vars, ad-hoc files, runtime flags) that can change escalation decisions without passing through S0 and `parameter_hash`.

---

### 2.4 Inputs that S1 MUST NOT consume

To preserve clean authority boundaries, S1 is explicitly forbidden from consuming or depending on:

1. **2B plan or runtime artefacts.**

   * No reads of:

     * `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`,
     * `s3_day_effects`, `s4_group_weights`,
     * `s5_selection_log`, `s6_edge_log`, or any other 2B surface.
   * S1’s decisions MUST NOT depend on routing behaviour; they are based solely on static counts, references and the mixture policy.

2. **Per-site 2A outputs.**

   * S1 MUST NOT read `site_timezones` at per-site granularity to drive decisions (e.g. no site-by-site counting of tzids).
   * The presence/absence and count of zones per country MUST come from reference surfaces and/or policy, not from scanning 2A egress per site.

3. **Row-level geometry from 1B.**

   * S1 MUST NOT read `site_locations` or any other 1B egress; geometric placement of outlets is not in scope for escalation decisions.

4. **Unsealed artefacts or ad-hoc configuration.**

   * Any artefact not present in `sealed_inputs_3A` for this `manifest_fingerprint` is out of scope.
   * S1 MUST NOT read environment variables or local files as implicit configuration knobs for mixture behaviour; all parameters MUST come via the governed 𝓟 and S0.

---

### 2.5 Invocation-level assumptions

For a specific run of 3A.S1 on `(parameter_hash, manifest_fingerprint, seed)`:

* The orchestrator MAY schedule S1 independently of other 3A states, but:

  * S1 MUST see the same catalogue state and S0 outputs that any later 3A state will see for this `manifest_fingerprint`.
  * If the catalogue or sealed inputs change (e.g. new policy version), Layer-1 governance MUST require a new `parameter_hash` and/or `manifest_fingerprint`; S1 MUST NOT be run under partially updated conditions.

Within these preconditions and gated inputs, 3A.S1 has a well-defined, deterministic view of its input world and is ready to perform the mixture classification and escalation queue construction defined in the subsequent sections.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes **exactly what 3A.S1 is allowed to read**, how it must treat each input, and where its authority **stops**. Anything outside these inputs, or used beyond the roles defined here, is out-of-spec.

---

### 3.1 Catalogue & gate inputs (shape + trust anchor)

3A.S1 sits under the same catalogue and gate regime as S0. It MUST treat the following as **shape / trust authorities**, not things it can redefine:

1. **Schema packs (shape authority)**

   * `schemas.layer1.yaml`
   * `schemas.ingress.layer1.yaml`
   * `schemas.1A.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml`

   S1 MAY only use these to:

   * validate the shape of the datasets it reads (`outlet_catalogue`, reference tables, mixture policy), and
   * resolve `schema_ref` anchors for its own outputs.

   S1 MUST NOT introduce new primitive types or event families; it reuses those defined in Layer-1 packs.

2. **Dataset dictionaries & artefact registries (catalogue authority)**

   * `dataset_dictionary.layer1.{1A,2A,3A}.yaml`
   * `artefact_registry_{1A,2A,3A}.yaml`

   For any dataset or artefact S1 reads, the dictionary/registry is the **only authority** on:

   * dataset/artefact ID,
   * path template (including `seed=` / `fingerprint=` tokens),
   * partition keys and format,
   * `schema_ref` and role.

   S1 MUST NOT hard-code paths or schema anchors; all resolution MUST go via these catalogue artefacts.

3. **3A.S0 outputs (gate authority)**

   * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`
   * `sealed_inputs_3A@fingerprint={manifest_fingerprint}`

   S1 MUST:

   * use `s0_gate_receipt_3A` to trust that upstream gates (1A/1B/2A) are PASS and to discover which policies are sealed, and
   * use `sealed_inputs_3A` as the **only whitelist** of artefacts it may read for this `manifest_fingerprint`.

   S1 has **no authority** to alter these artefacts or to interpret upstream bundles beyond what S0 already attested.

---

### 3.2 Upstream data-plane inputs (business facts)

S1’s classification operates on **aggregated outlet counts per merchant×country** and **static zone structure per country**.

Within the sealed set from S0, S1 MAY read:

1. **1A outlet catalogue (for counts only)**

   * Dataset ID: `outlet_catalogue`
   * Scope: `seed={seed}/fingerprint={manifest_fingerprint}`

   S1’s allowed use:

   * Group rows by `(merchant_id, legal_country_iso)` to derive:
     [
     N(m,c) = \text{COUNT rows from outlet_catalogue where merchant_id = m, legal_country_iso = c}
     ]
   * Optionally derive simple per-pair diagnostics such as:

     * whether `N(m,c) ≥ 2`,
     * whether the merchant has outlets in multiple countries (via distinct `legal_country_iso` per `merchant_id`).

   S1 MUST NOT:

   * modify or re-output `outlet_catalogue`,
   * recalculate any country-level counts other than `N(m,c)` (no new integerisation),
   * rely on per-site fields (e.g. `site_order`, `site_id`) for policy logic other than forming the group-by.

2. **Country & zone structure (ingress/2A references)**
   S1 MAY read the following reference surfaces, provided they appear in `sealed_inputs_3A`:

   * `iso3166_canonical_2024` (or equivalent)

     * to validate that `legal_country_iso` values from 1A are canonical Layer-1 countries.

   * `tz_world_2025a` (or equivalent ingress tz geometry)

     * to determine, per `legal_country_iso`, the set of IANA tzids that exist in that country:
       [
       Z(c) = {, \text{tzid} \mid tz_polygon(tzid) \cap country_polygon(c) \neq \emptyset ,}
       ]

   * Optionally, 2A’s `tz_timetable_cache` manifest

     * to cross-check that any tzid in `Z(c)` also exists in the compiled tz universe.

   S1 MUST treat these as **read-only reference**: it does not change zone boundaries or tzid sets; it only observes them.

S1 has **no authority** to decide which tzid a specific site is in; that belongs to Segment 2A.

---

### 3.3 3A mixture policy inputs (decision rules)

Escalation decisions are governed entirely by the **3A zone mixture policy**, which is part of the sealed parameter set 𝓟.

Within `sealed_inputs_3A` and `s0_gate_receipt_3A.sealed_policy_set`, S1 MUST locate and read:

1. **Zone mixture policy (required)**

   * Logical ID: e.g. `zone_mixture_policy_3A`
   * `owner_segment = "3A"`
   * `role = "zone_mixture_policy"` (or equivalent agreed tag)
   * `schema_ref: schemas.3A.yaml#/policy/zone_mixture_policy_3A`

   The policy defines, at minimum:

   * eligibility criteria per `(merchant_id, legal_country_iso)` and/or per `legal_country_iso`:

     * minimum outlets `N(m,c)` required to consider escalation,
     * minimum number of tzids in `Z(c)` for escalation,
     * any allow/deny lists or MCC-based overrides,
     * dominance thresholds (e.g. “if a single tzid would hold ≥ θ of mass, treat monolithic”).

   S1 MUST:

   * validate the policy against its schema,
   * apply its rules deterministically to each `(m,c)`, and
   * treat the policy content as **read-only**; any change to the policy MUST occur via 𝓟 and `parameter_hash`.

2. **Other policies/priors (read-only presence check)**

   * S1 may require the *presence* of other 3A policies/priors (e.g. α-priors or zone floors) only to ensure future states are well-posed.
   * S1 MUST NOT read or interpret α values or floors; it may only:

     * assert that the relevant artefacts are sealed and schema-valid, and
     * surface errors if required artefacts are missing (to avoid escalating into a world with no priors).

In short, **S1 owns the mechanics of applying the mixture policy**, but it does **not** own the policy itself; that authority lies with the governed parameter set and its schema.

---

### 3.4 What S1 is and isn’t allowed to authoritatively decide

S1’s **only new authority surface** (fleshed out in §4) is:

* the **escalation decision** per merchant×country:

  * `is_escalated ∈ {true,false}`,
  * `decision_reason` or similar code from a closed vocabulary,
  * any policy-derived features that explain the decision.

S1 MUST treat the following as **out of its authority**:

1. **Per-zone outlet shares / counts.**

   * S1 MUST NOT attempt to assign any mass or count to specific tzids; it only decides whether a pair is escalated or not.
   * Zone shares and integer counts are owned by later states (Dirichlet & integerisation) and must not be “pre-baked” in S1.

2. **Which tzid a monolithic pair implicitly maps to.**

   * For `is_escalated = false`, S1 does not decide “which zone gets all the outlets”; that is either:

     * determined by a later 3A state (e.g. a default zone selection rule), or
     * inherited from an upstream default.
   * S1’s authority stops at the boolean “split vs don’t split”.

3. **Any modification to upstream counts or zone sets.**

   * S1 MUST NOT change or reinterpret:

     * `N(m,c)` as determined by `outlet_catalogue`, or
     * `Z(c)` as derived from ingress/2A references.
   * If policy would require impossible changes to these facts (e.g. requesting escalation where `Z(c)` is empty), S1 MUST raise a policy/config error rather than “fixing” the inputs.

---

### 3.5 Explicit “MUST NOT” list

To keep the authority boundaries sharp, S1 is explicitly forbidden from:

* consuming **any RNG** or Philox streams;
* reading **2B** plan or runtime datasets of any kind;
* using **per-site** tzids (`site_timezones`) or geometry (`site_locations`) to drive escalation decisions;
* reading any artefact **not present** in `sealed_inputs_3A` for the current `manifest_fingerprint`;
* introducing hidden configuration through environment variables, local files, or runtime flags that bypass 3A.S0 and `parameter_hash`;
* emitting any new authority surfaces beyond the escalation decisions and diagnostics defined for S1’s outputs.

Within these boundaries, S1’s inputs and authority are narrowly scoped:

* It trusts S0 for gates and sealed inputs,
* trusts 1A and ingress/2A for counts and zone structure,
* applies a sealed 3A mixture policy, and
* owns only the **classification** of each merchant×country into monolithic vs escalated.

---

## 4. Outputs (datasets) & identity *(Binding)*

3A.S1 produces a **single authoritative dataset** that captures, for each merchant×country pair with non-zero outlet mass, the result of applying the zone mixture policy: **monolithic vs escalated**, plus supporting features. S1 does **not** emit any RNG logs or validation bundles.

---

### 4.1 Overview of S1 outputs

For each `(parameter_hash, manifest_fingerprint, seed)` triple and associated outlet universe, 3A.S1 MUST produce at most one instance of:

1. **`s1_escalation_queue`**

   * A per-merchant×country classification table that:

     * covers **every** `(merchant_id, legal_country_iso)` for which 1A’s `outlet_catalogue` has at least one row under this `{seed,fingerprint}`,
     * records whether the pair is **escalated** into zone allocation (`is_escalated = true`) or remains **monolithic** (`is_escalated = false`), and
     * records the key policy-relevant features and reason codes that led to that decision.

No other persistent outputs are in scope for 3A.S1. In particular, S1:

* MUST NOT emit any zone-level allocation datasets (no tzid-level counts or shares),
* MUST NOT emit any segment-level validation bundle or `_passed.flag` (those belong to a later 3A state),
* MUST NOT mutate or re-emit `outlet_catalogue`.

---

### 4.2 `s1_escalation_queue` — merchant×country mixture decisions

#### 4.2.1 Identity & domain

**Logical dataset ID (conceptual):** `s1_escalation_queue`
(The exact ID and path will be defined in `dataset_dictionary.layer1.3A.yaml`, but the semantics below are binding.)

For a given `{seed, manifest_fingerprint}`, the **domain** of `s1_escalation_queue` is:

* all pairs `(merchant_id, legal_country_iso)` such that there exists at least one row in
  `outlet_catalogue@seed={seed}/fingerprint={manifest_fingerprint}` with those keys.

Identity and cardinality:

* There MUST be **exactly one** row in `s1_escalation_queue` for each such `(merchant_id, legal_country_iso)` pair.
* There MUST NOT be any rows for `(merchant_id, legal_country_iso)` pairs that are absent from 1A’s `outlet_catalogue` for this `{seed,fingerprint}`.

**Logical primary key:**

* `PK = (merchant_id, legal_country_iso)` within each `(seed, manifest_fingerprint)` partition.

#### 4.2.2 Partitioning & path (conceptual)

` s1_escalation_queue` is a seed/fingerprint-scoped planning dataset:

* Partition key set: `["seed", "fingerprint"]`.

* Path pattern (conceptual; final form in the dictionary):

  ```text
  data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest_fingerprint}/...
  ```

* The embedded `manifest_fingerprint` and `seed` columns (see below) MUST equal the corresponding path tokens (path↔embed equality).

* There MUST be at most one partition for each `{seed, manifest_fingerprint}`.

#### 4.2.3 Required columns & meaning

At minimum, each row in `s1_escalation_queue` MUST contain:

* **Lineage / partitions**

  * `seed` — Layer-1 run seed (`uint64` via `schemas.layer1.yaml`), identical across all rows in this partition.
  * `manifest_fingerprint` — `hex64`, identical across all rows in this partition.

* **Identity**

  * `merchant_id` — Layer-1 merchant identifier (`id64` via `schemas.layer1.yaml`), matching 1A.
  * `legal_country_iso` — ISO-3166 alpha-2 country code (`iso2` via `schemas.layer1.yaml`), matching 1A.

* **Counts / structural features**

  * `site_count` — integer ≥ 1;
    `site_count(m,c) = N(m,c) = COUNT(*)` in `outlet_catalogue` for this `(merchant_id, legal_country_iso)` under `{seed,fingerprint}`.
  * `zone_count_country` — integer ≥ 0;
    `zone_count_country(c) = |Z(c)|`, where `Z(c)` is the set of IANA tzids present in that country according to sealed reference surfaces (e.g. `tz_world_2025a`).

* **Mixture decision**

  * `is_escalated` — boolean;

    * `true` ⇒ this `(m,c)` pair MUST be processed by the Dirichlet / integerisation pipeline in later 3A states,
    * `false` ⇒ this `(m,c)` pair MUST NOT be processed by that pipeline (treated as monolithic under later rules).
  * `decision_reason` — short string code from a **closed vocabulary** defined in the 3A policy schema (e.g. `"below_min_sites"`, `"single_zone_country"`, `"dominant_zone_threshold"`, `"forced_escalation"`, `"forced_monolithic"`).
    This field is primarily for diagnostics but MUST be present and MUST correspond to the actual policy branch taken.

* **Policy lineage**

  * `mixture_policy_id` — string; logical ID of the mixture policy artefact applied (e.g. `zone_mixture_policy_3A`).
  * `mixture_policy_version` — string; typically a semver or hash derived from the policy artefact (MUST be consistent across all rows in the partition for a given `parameter_hash`).

Other informative columns MAY be added (e.g. `eligible_for_escalation`, `dominant_zone_share_bucket`) but MUST NOT change the meaning of `is_escalated`.

#### 4.2.4 Writer-sort and immutability

S1 MUST write `s1_escalation_queue` with a deterministic sort order inside each `(seed, fingerprint)` partition, for example:

1. `merchant_id` ascending,
2. `legal_country_iso` ascending.

This ordering is **not semantically authoritative**; all semantics come from the primary key and column values. It exists for reproducibility and human inspection.

Once written for a given `{seed, manifest_fingerprint}` and `parameter_hash`:

* `s1_escalation_queue` MUST be treated as **immutable**; later states MUST NOT overwrite or append different rows for the same partition.
* Re-running S1 under identical conditions MUST reproduce the same row set and bytes; any divergence MUST be treated as a violation of S1’s immutability and idempotence rules (to be detailed in §§7–9).

---

### 4.3 Consumers and role in the 3A authority chain

` s1_escalation_queue` is an internal-but-authoritative planning surface for Segment 3A:

* **Required consumers:**

  * 3A.S2/S3/S4 (zone prior loading, Dirichlet draws, integerisation) MUST:

    * derive their worklist of merchant×country pairs exclusively from `s1_escalation_queue`, and
    * restrict Dirichlet / zone-count computation to those rows with `is_escalated = true`.
  * The 3A validation state MUST:

    * use `s1_escalation_queue` as the domain to check that all escalated pairs received zone shares/counts, and that no non-escalated pair did.

* **Optional consumers:**

  * Cross-segment validation harnesses and observability tools MAY consume `s1_escalation_queue` to:

    * track the fraction of volume subject to zone allocation,
    * analyse policy application across merchants/countries.

` s1_escalation_queue` is **not** a public egress dataset and MUST NOT be used outside 3A and validation tooling as a stable contract without additional governance. Its authority is limited to Segment 3A’s internal decision about which merchant×country pairs flow into zone-level allocation.

---

### 4.4 Non-outputs (explicit exclusions)

For avoidance of doubt, 3A.S1 does **not** introduce:

* any egress dataset that changes outlet counts or site identity (those remain owned by 1A),
* any per-tzid allocation tables (those are introduced in later 3A states),
* any RNG-related logs or receipts (S1 is RNG-free),
* any new validation bundles or `_passed.flag` surfaces (segment-level PASS remains the job of a later 3A state).

Within this section’s constraints, `s1_escalation_queue` is the **only dataset** S1 is responsible for producing, and it is the **sole authority** on the monolithic vs escalated classification of merchant×country pairs for Segment 3A.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes where the **S1 output** lives in the authority chain:

* which JSON-Schema anchor defines its shape,
* how it is exposed through the Layer-1 dataset dictionary, and
* how it is registered in the 3A artefact registry.

Everything here is **normative**; implementations MUST NOT invent shadow IDs, shapes, or paths for this dataset.

---

### 5.1 Segment schema pack for S1

3A.S1 reuses the existing segment schema pack:

* **Schema pack ID:** `schemas.3A.yaml`
* **Role:** shape authority for all Segment-3A artefacts (S0–S7).

`schemas.3A.yaml` MUST:

1. Import Layer-1 primitive defs via `$ref: "schemas.layer1.yaml#/$defs/…"`, including:

   * `id64`, `iso2`, `hex64`, `uint64`, `rfc3339_micros`, etc.

2. Define a dedicated anchor for S1’s output:

   * `#/plan/s1_escalation_queue`

3. Avoid redefining any primitives already present in `schemas.layer1.yaml`.

No other schema pack may define the shape of `s1_escalation_queue`.

---

### 5.2 Schema anchor: `schemas.3A.yaml#/plan/s1_escalation_queue`

`#/plan/s1_escalation_queue` defines the **row shape** of the S1 escalation queue.

At minimum, the schema MUST enforce:

* **Type:** `object`

* **Required properties:**

  * `seed`

    * `$ref: "schemas.layer1.yaml#/$defs/uint64"`

  * `manifest_fingerprint`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `merchant_id`

    * `$ref: "schemas.layer1.yaml#/$defs/id64"`

  * `legal_country_iso`

    * `$ref: "schemas.layer1.yaml#/$defs/iso2"`

  * `site_count`

    * `type: "integer"`, `minimum: 1`

  * `zone_count_country`

    * `type: "integer"`, `minimum: 0`

  * `is_escalated`

    * `type: "boolean"`

  * `decision_reason`

    * `type: "string"`
    * `enum` over a **closed vocabulary** defined in the policy schema (e.g. `{ "below_min_sites", "single_zone_country", "dominant_zone_threshold", "forced_escalation", "forced_monolithic" }`). The exact enum list is owned by the `zone_mixture_policy_3A` schema.

  * `mixture_policy_id`

    * `type: "string"`

  * `mixture_policy_version`

    * `type: "string"`

* **Optional properties (non-exhaustive):**

  * `eligible_for_escalation` — `type: "boolean"` (pre-decision eligibility flag).
  * `dominant_zone_share_bucket` — `type: "string"` (e.g. `"0-50"`, `"50-80"`, `">=80"`), if defined in the mixture policy schema.
  * `notes` — `type: "string"` (free-text diagnostics).

* **Additional properties:**

  * At the top level, the schema SHOULD set
    `additionalProperties: false`
    to prevent accidental shape drift, except where explicitly allowed for future-proof extension (e.g. in a dedicated `x_debug` sub-object if needed).

This anchor MUST be used as the `schema_ref` for `s1_escalation_queue` in the dataset dictionary.

---

### 5.3 Dataset dictionary entry: `dataset_dictionary.layer1.3A.yaml`

The Layer-1 dataset dictionary for subsegment 3A MUST define a dataset entry for S1:

```yaml
datasets:
  - id: "s1_escalation_queue"
    subsegment: "3A"
    version: "1.0.0"              # S1 contract version for this dataset
    path: "data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest_fingerprint}/"
    format: "parquet"
    partitioning: ["seed", "fingerprint"]
    ordering: ["merchant_id", "legal_country_iso"]
    schema_ref: "schemas.3A.yaml#/plan/s1_escalation_queue"
    lineage:
      produced_by: ["3A.S1"]
      consumed_by: ["3A.S2", "3A.S3", "3A.S4", "3A.validation"]
    final_in_layer: false
    role: "3A internal planning surface — escalation decisions per merchant×country"
```

Binding points:

* **`id`** MUST be `"s1_escalation_queue"`; no other dataset may reuse this ID.
* **`path`** MUST contain both `seed={seed}` and `fingerprint={manifest_fingerprint}` tokens and no additional partition tokens.
* **`partitioning`** MUST be exactly `["seed", "fingerprint"]`.
* **`schema_ref`** MUST point to `schemas.3A.yaml#/plan/s1_escalation_queue`.
* **`ordering`** expresses the writer-sort key; readers MUST NOT assign semantics to physical file order beyond reproducibility.

Any alternative path, partitioning scheme, or schema_ref for this dataset is out-of-spec.

---

### 5.4 Artefact registry entry: `artefact_registry_3A.yaml`

For each `manifest_fingerprint`, the 3A artefact registry MUST include an entry for `s1_escalation_queue`. A representative registry item (field names aligned to existing Layer-1 style) is:

```yaml
- manifest_key: "mlr.3A.s1_escalation_queue"
  name: "Segment 3A S1 escalation queue"
  subsegment: "3A"
  type: "dataset"
  category: "plan"
  path: "data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest_fingerprint}/"
  schema: "schemas.3A.yaml#/plan/s1_escalation_queue"
  version: "1.0.0"
  digest: "<sha256_hex>"          # resolved per manifest at runtime
  dependencies:
    - "mlr.1A.outlet_catalogue"
    - "mlr.ingress.iso3166_canonical_2024"
    - "mlr.ingress.tz_world_2025a"
    - "mlr.3A.zone_mixture_policy"
    - "mlr.3A.s0_gate_receipt"
  role: "Authority on monolithic vs escalated classification for merchant×country in Segment 3A"
  cross_layer: true               # relevant to validation & analytics across segments
  notes: "RNG-free; one row per merchant×country with ≥1 outlet; consumed by 3A.S2–S4."
```

Binding requirements:

* `manifest_key` MUST be unique within the registry and clearly namespaced to 3A.S1 (e.g. `mlr.3A.s1_escalation_queue`).
* `path` and `schema` MUST match the dataset dictionary entry.
* `dependencies` MUST include, at minimum:

  * 1A outlet catalogue (`outlet_catalogue`),
  * ingress/2A references used to compute `zone_count_country` (ISO + tz_world),
  * the 3A zone mixture policy artefact,
  * `s0_gate_receipt_3A` (which provides the trust anchor for upstream gates and sealed policies).

The registry entry MUST be kept in sync with the dataset dictionary and actual written artefacts; **path↔embed equality** and digest correctness are validated by later 3A validation states.

---

### 5.5 No additional S1 datasets

3A.S1 MUST NOT register or emit any additional datasets beyond `s1_escalation_queue` (and any implicit run-report entries governed by Layer-1). In particular:

* There MUST be no “temporary” or “debug” planning datasets that alter behaviour or are consumed by later states without being present in the dataset dictionary and artefact registry.
* Any future additional S1 datasets (e.g. extra diagnostics) MUST go through the same process:

  * new schema anchors in `schemas.3A.yaml`,
  * new `datasets` entries in `dataset_dictionary.layer1.3A.yaml`, and
  * corresponding artefact registry entries.

Within these bindings, `schemas.3A.yaml`, `dataset_dictionary.layer1.3A.yaml`, and `artefact_registry_3A.yaml` together define the **only valid shape, identity, and catalogue view** of S1’s escalation queue.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section defines the **exact behaviour** of 3A.S1. The algorithm is:

* **Purely deterministic** (no RNG, no wall-clock),
* **Catalogue-driven** (no hard-coded paths), and
* **Idempotent** (same inputs ⇒ byte-identical outputs).

Given:

* a fixed `(parameter_hash, manifest_fingerprint, seed)`,
* a stable catalogue, and
* the sealed inputs defined by 3A.S0,

re-running S1 MUST always produce the same `s1_escalation_queue`.

---

### 6.1 Phase overview

3A.S1 executes in five phases:

1. **Resolve S0 gate & sealed inputs.**
   Validate that S0 succeeded and locate the artefacts S1 needs.

2. **Load mixture policy & structural references.**
   Load the 3A zone mixture policy and reference tables for countries and zones.

3. **Aggregate outlet counts per merchant×country.**
   Derive `site_count = N(m,c)` from 1A’s `outlet_catalogue`.

4. **Derive per-country zone counts.**
   For each country in scope, compute `zone_count_country = |Z(c)|` from sealed references.

5. **Apply mixture policy per merchant×country & materialise `s1_escalation_queue`.**
   For each pair, apply the policy deterministically and emit a single row with `is_escalated` and `decision_reason`.

No phase may call the RNG or read wall-clock time.

---

### 6.2 Phase 1 — Resolve S0 gate & sealed inputs

**Step 1 – Load and validate S0 artefacts**

* Using the Layer-1 dictionary and registry for 3A, S1 resolves paths for:

  * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`
  * `sealed_inputs_3A@fingerprint={manifest_fingerprint}`

S1 MUST:

* Read both artefacts.
* Validate `s0_gate_receipt_3A` against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`.
* Validate `sealed_inputs_3A` against `schemas.3A.yaml#/validation/sealed_inputs_3A`.

If either artefact is missing or schema-invalid, S1 MUST fail (precondition violation).

**Step 2 – Check upstream gates via S0**

From `s0_gate_receipt_3A.upstream_gates`, S1 MUST verify:

* `segment_1A.status == "PASS"`
* `segment_1B.status == "PASS"`
* `segment_2A.status == "PASS"`

If any status differs from `"PASS"`, S1 MUST fail and MUST NOT attempt to run its own gate logic.

**Step 3 – Confirm required artefacts are sealed**

Using `sealed_inputs_3A`, S1 MUST confirm the presence of rows for:

* 1A egress: `outlet_catalogue` at `seed={seed}, fingerprint={manifest_fingerprint}`.
* Ingress references:

  * `iso3166_canonical_2024` (or equivalent),
  * `tz_world_2025a` (or equivalent).
* 3A zone mixture policy: logical ID e.g. `zone_mixture_policy_3A` with `owner_segment="3A"` and `role="zone_mixture_policy"`.

For each required artefact:

* S1 MUST verify that there is at least one row in `sealed_inputs_3A` with matching `logical_id` and `path`.
* S1 MUST recompute the SHA-256 digest of the artefact and assert equality with the `sha256_hex` recorded in that row.

If any required artefact is missing or mismatched, S1 MUST fail with an appropriate error (policy set or sealed-input resolution failure).

---

### 6.3 Phase 2 — Load mixture policy & structural references

**Step 4 – Load and validate the mixture policy**

* From `sealed_inputs_3A` and `s0_gate_receipt_3A.sealed_policy_set`, S1 resolves:

  * `mixture_policy_id` (e.g. `zone_mixture_policy_3A`),
  * `mixture_policy_path`,
  * `mixture_policy_schema_ref` (e.g. `schemas.3A.yaml#/policy/zone_mixture_policy_3A`).

S1 MUST:

* Read the policy artefact and validate it against `mixture_policy_schema_ref`.
* Derive a **policy version** deterministically, e.g.:

  * either from an explicit `version` field inside the policy, or
  * by using its `sha256_hex` from `sealed_policy_set`.

This `mixture_policy_id` and `mixture_policy_version` will later be echoed in every row of `s1_escalation_queue`.

**Step 5 – Load country & zone reference tables**

S1 MUST load:

* `iso3166_canonical_2024` — to validate country codes;
* `tz_world_2025a` — to derive per-country zone sets.

Using `tz_world_2025a` and `iso3166_canonical_2024`, S1 MUST compute, in a deterministic manner, a mapping:

[
Z(c) = {\text{tzid}}
]

for each `legal_country_iso = c` that may appear in `outlet_catalogue`. At minimum:

* `zone_count_country(c) = |Z(c)|`
* `Z(c)` MUST contain only tzids that belong to country `c` according to the sealed `tz_world_2025a` semantics.
* S1 MUST NOT consult per-site `site_timezones` for this computation.

The exact geometric criteria (any overlap vs centre-in-country) are inherited from Layer-1’s definition of `tz_world_2025a` and MUST be applied consistently; S1 MUST not invent new geometry rules.

S1 MAY precompute a table `country_zone_structure` keyed by `legal_country_iso` with columns:

* `zone_count_country`,
* optionally `has_multiple_zones` (boolean),
* any other policy-relevant flags derived from `Z(c)`.

---

### 6.4 Phase 3 — Aggregate outlet counts per merchant×country

**Step 6 – Resolve and read `outlet_catalogue`**

Using the dictionary/registry and `sealed_inputs_3A`, S1 resolves:

* dataset ID: `outlet_catalogue`
* path: `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…`
* `schema_ref: schemas.1A.yaml#/egress/outlet_catalogue`.

S1 MUST:

* Validate that this dataset is present and schema-valid.
* Read only the columns required for grouping:

  * `merchant_id`,
  * `legal_country_iso`.

**Step 7 – Group by merchant×country**

S1 MUST compute, in deterministic order:

* For each distinct pair `(merchant_id = m, legal_country_iso = c)` in `outlet_catalogue`:

  * `site_count(m,c) = COUNT(*)`.

All pairs with `site_count(m,c) ≥ 1` form the **domain** of S1’s output:

[
D = { (m,c) \mid site_count(m,c) \ge 1 }.
]

S1 MUST NOT:

* drop any pair in `D`, nor
* invent any extra `(m,c)` pairs not present in `outlet_catalogue`.

The grouping MUST be stable and deterministic; e.g. aggregating with a fixed sort order or dictionary iteration with a defined key ordering.

---

### 6.5 Phase 4 — Apply zone mixture policy per merchant×country

**Step 8 – Construct decision context per pair**

For each `(m,c) ∈ D`, S1 constructs a **decision context** from sealed data:

* `site_count = site_count(m,c)` from Step 7,
* `zone_count_country = zone_count_country(c)` from Step 5 (if no entry exists for `c`, this is a policy/config error),
* any additional static attributes specified in the mixture policy that S1 is allowed to use (e.g. country-level flags or thresholds embedded in the policy).

No per-site or per-tzid data may enter the context; S1’s decisions MUST be expressible purely in terms of:

* the decision context variables above, and
* static values from the mixture policy.

**Step 9 – Evaluate mixture policy (RNG-free)**

S1 MUST evaluate the mixture policy for each `(m,c)` in a fixed, deterministic order (e.g. sorted by `merchant_id`, then `legal_country_iso`). The policy is declarative; S1 serves as its evaluation engine.

The evaluation MUST:

1. **Check hard preconditions** (fail vs classify):

   Examples (exact logic defined by the policy schema):

   * If `zone_count_country(c) == 0` ⇒ this is a configuration error (country has outlets but no zones); S1 MUST fail rather than classify.
   * If policy requires at least one potential zone (e.g. `min_zones_for_escalation >= 1`) and `zone_count_country(c) < 1`, classification may still proceed but policy may force `is_escalated=false` with a suitable `decision_reason` (e.g. `"single_zone_country"`).

2. **Apply forced decisions first (if supported by policy):**

   If the mixture policy defines any explicit lists such as:

   * `force_escalate_countries`,
   * `force_monolithic_countries`,

   S1 MUST check them first, in a deterministic order:

   * If `(m,c)` matches a **forced escalation** rule ⇒
     `is_escalated = true`, `decision_reason = "forced_escalation"` (or equivalent code).
   * Else if `(m,c)` matches a **forced monolithic** rule ⇒
     `is_escalated = false`, `decision_reason = "forced_monolithic"`.

3. **Apply general eligibility rules:**

   For pairs not caught by forced rules, the policy may specify:

   * minimum outlet count per pair, e.g.
     `if site_count < min_sites_for_escalation(c) then monolithic`.
   * minimum number of zones per country, e.g.
     `if zone_count_country < min_zones_for_escalation then monolithic`.

   S1 MUST:

   * compute these predicates purely from decision context + policy values,
   * assign deterministic `decision_reason` codes (e.g. `"below_min_sites"`, `"single_zone_country"`),
   * set `is_escalated` accordingly.

4. **Default decision:**

   If none of the above rules force a monolithic decision, S1 MUST set:

   * `is_escalated = true`,
   * `decision_reason = "default_escalation"` (or another code defined in the policy).

At no point may S1:

* call into any RNG,
* consult per-site tzids, coordinates, or 2B outputs,
* change or reinterpret 1A or ingress/2A facts (counts or zone presence).

**Step 10 – Derive derived/convenience fields**

After determining `is_escalated` and `decision_reason`, S1 MAY populate additional convenience fields that are deterministic functions of the decision context and policy, for example:

* `eligible_for_escalation` (boolean used internally to distinguish “eligible but not chosen” vs “never eligible”),
* `dominant_zone_share_bucket` (if the policy partitions countries into buckets based on a static assumption of zone dominance).

These fields MUST NOT affect downstream semantics beyond what is already implied by `is_escalated` and `decision_reason`.

---

### 6.6 Phase 5 — Materialise `s1_escalation_queue`

**Step 11 – Row construction**

For each `(m,c) ∈ D`, S1 constructs a row in `s1_escalation_queue` with:

* `seed` — from the invocation triple,
* `manifest_fingerprint` — from the invocation triple,
* `merchant_id = m`,
* `legal_country_iso = c`,
* `site_count = site_count(m,c)`,
* `zone_count_country = zone_count_country(c)`,
* `is_escalated` and `decision_reason` — from Steps 8–9,
* `mixture_policy_id` and `mixture_policy_version` — from Step 4,
* any optional diagnostic fields derived deterministically as in Step 10.

S1 MUST produce exactly one row per `(m,c)` in `D` and no rows for pairs outside `D`.

**Step 12 – Sort and write**

Using the dataset dictionary entry for `s1_escalation_queue`:

* Expand path:
  `data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest_fingerprint}/…`

* Within this partition, S1 MUST sort rows by the declared writer-sort key (e.g.):

  1. `merchant_id` ascending,
  2. `legal_country_iso` ascending.

* S1 MUST validate rows against `schemas.3A.yaml#/plan/s1_escalation_queue`.

**Existing data handling (idempotence):**

* If no dataset exists at the target path, S1 writes the new dataset.
* If a dataset already exists:

  * S1 MUST read it, sort by the same key, and compare row-by-row with the newly constructed row set.
  * If they are identical (including all field values and types), S1 MAY:

    * skip writing, or
    * overwrite with identical bytes (implementation choice).
  * If they differ, S1 MUST fail with an immutability error and MUST NOT overwrite the existing dataset.

---

### 6.7 Side-effect and RNG discipline

Throughout all phases:

* S1 MUST NOT:

  * consume any Philox stream or call any RNG API,
  * read system time or any non-deterministic source,
  * create, modify or delete any artefacts other than `s1_escalation_queue` for the current `{seed, fingerprint}`.

* On failure at any step:

  * S1 MUST NOT leave any partially written `s1_escalation_queue` visible; writes MUST be atomic or rolled back.

Under this algorithm, `s1_escalation_queue` is a purely deterministic function of:

* the sealed input universe established by 3A.S0,
* the governed 3A mixture policy for the current `parameter_hash`, and
* 1A and ingress/2A reference surfaces.

It provides a stable, RNG-free authority surface for later 3A states to decide which merchant×country pairs proceed into zone-level allocation.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how `3A.S1`’s output is **identified**, how it is **partitioned**, what (if any) meaning is attached to **ordering**, and what is allowed in terms of **merge / overwrite behaviour**. Consumers MUST be able to reason purely from keys, partitions and paths.

---

### 7.1 Identity: what a row *is*

For 3A.S1, the identity of a row in `s1_escalation_queue` is:

* **Run-level identity** (shared across many rows):

  * `seed` — from the Layer-1 run triple,
  * `manifest_fingerprint` — from the Layer-1 manifest.

* **Business identity** (within a run):

  * `merchant_id` — the Layer-1 merchant identifier,
  * `legal_country_iso` — ISO country code as in 1A.

**Domain definition**

For a given `{seed, manifest_fingerprint}`, define:

[
D = { (m,c) \mid \exists\ \text{row in 1A.outlet_catalogue with } merchant_id=m, legal_country_iso=c }
]

Then:

* `s1_escalation_queue` MUST contain **exactly one row** for every `(m,c) ∈ D`.
* `s1_escalation_queue` MUST NOT contain any `(m,c)` not in `D`.

**Logical primary key**

Within each `{seed, manifest_fingerprint}` partition:

* Logical PK:
  [
  (\text{merchant_id}, \text{legal_country_iso})
  ]

There MUST NOT be duplicates of this pair.

---

### 7.2 Partitions & path tokens

` s1_escalation_queue` is a **plan** dataset keyed by both `seed` and `manifest_fingerprint`.

**Partition key set**

* Partition keys MUST be exactly:

  ```text
  ["seed", "fingerprint"]
  ```

No additional partition keys (e.g. `parameter_hash`, `run_id`) are allowed for this dataset.

**Path template (conceptual)**

From the dataset dictionary:

```text
data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest_fingerprint}/...
```

Binding rules:

* For any concrete partition, the path MUST include:

  * `seed=<decimal-uint64>`,
  * `fingerprint=<hex64>`.
* There MUST be at most one `s1_escalation_queue` partition for any given `{seed, manifest_fingerprint}` pair.

**Path↔embed equality**

Every row in a given partition MUST satisfy:

* `row.seed == {seed_token}`
* `row.manifest_fingerprint == {fingerprint_token}`

Any mismatch between embedded values and path tokens is a hard schema/validation error for S1 and for downstream validators.

---

### 7.3 Keys & uniqueness invariants

Within each `{seed, manifest_fingerprint}` partition:

* `(merchant_id, legal_country_iso)` MUST appear exactly once.
* No row may have `site_count < 1`.
* No row may have `zone_count_country < 0`.

Uniqueness invariants:

* `(seed, manifest_fingerprint, merchant_id, legal_country_iso)` MUST be unique across all rows.
* `(manifest_fingerprint, merchant_id, legal_country_iso)` is sufficient to identify a row if `seed` is fixed by context; however, the canonical key is the full 4-tuple.

The dataset MUST be free of:

* duplicate rows for the same `(m,c)`,
* rows with a `(m,c)` pair that does not appear in 1A’s `outlet_catalogue` for that `{seed, fingerprint}`.

---

### 7.4 Ordering semantics (writer-sort)

Physical file order is **not authoritative** for semantics. However, S1 MUST enforce a deterministic writer-sort to ensure reproducibility:

* Inside each partition `{seed, fingerprint}`, rows MUST be sorted by the `ordering` key declared in the dictionary, for example:

  1. `merchant_id` ascending,
  2. `legal_country_iso` ascending.

Consumers MUST NOT attach any extra meaning to this order (e.g. “earlier rows are more important”); all semantics come from the key and column values.

The only contract on ordering is:

* Re-running S1 under identical conditions will produce the **same row set in the same order**, ensuring byte-identical outputs.

---

### 7.5 Merge & append discipline (single-snapshot per run)

` s1_escalation_queue` is a **snapshot** of the mixture policy decisions for a given run; it is not an append log.

**Single-writer per `{seed, fingerprint}`**

* For each `{seed, manifest_fingerprint}`, there MUST be at most one `s1_escalation_queue` dataset at the configured path.
* S1 is the **only state** allowed to write this dataset.

**No row-level merges or partial updates**

* S1 MUST always construct `s1_escalation_queue` as a complete row set for `D`.
* It MUST NOT:

  * append rows to an existing partition,
  * delete or mutate individual rows in-place, or
  * split a single `{seed,fingerprint}` snapshot across multiple, conceptually different “epochs”.

**Idempotent re-writes only**

If a dataset is already present for `{seed, manifest_fingerprint}` when S1 runs:

1. S1 MUST read it, normalise to the same schema and sort order, and compare against the newly computed row set.

2. If they are **identical**:

   * S1 MAY skip writing, or
   * re-write byte-identical content (implementation choice).
     In either case, the observable content MUST remain unchanged.

3. If they **differ**:

   * S1 MUST NOT overwrite the existing dataset.
   * S1 MUST signal an immutability violation error (to be classified in §9) and abort.

This ensures that there is never ambiguity about which escalation decisions apply to a given `{seed, manifest_fingerprint}` run.

---

### 7.6 Cross-fingerprint semantics

` s1_escalation_queue` makes **no claims** about relationships between different `manifest_fingerprint` values:

* Each partition `seed={s}/fingerprint={F}` describes escalation decisions only for that manifest.
* It is out-of-spec to combine rows from different fingerprints and treat them as a single logical plan for any one run.

Cross-fingerprint unions are allowed **only for analytics**, e.g.:

* “What fraction of merchant×country pairs were escalated across all manifests this month?”

Such analytics MUST NOT be used to drive runtime decisions for a specific manifest.

---

### 7.7 Interaction with upstream & downstream identity

**Upstream (1A)**

* 1A’s `outlet_catalogue` is the authority on which `(merchant_id, legal_country_iso)` pairs exist and how many sites they have.
* S1 MUST ensure that its domain `D` matches the set of distinct `(merchant_id, legal_country_iso)` present in `outlet_catalogue` for the same `{seed, fingerprint}`.
* S1 MUST NOT change 1A identity or counts.

**Downstream (3A.S2–S4 and validators)**

* Later 3A states MUST use `(seed, manifest_fingerprint, merchant_id, legal_country_iso)` as the join key to `s1_escalation_queue`.
* They MUST NOT invent escalation decisions for `(m,c)` pairs not present in S1, nor ignore S1’s `is_escalated` flag for any pair.

Under these rules, `s1_escalation_queue` is a **clean, snapshot-style authority surface**: its identity and partitions are clear, its ordering is stable but non-semantic, and its merge discipline guarantees that a given run’s escalation decisions cannot silently drift over time.

---

## 8. Acceptance criteria & validator hooks *(Binding)*

This section defines **when 3A.S1 is considered PASS** for a given `(parameter_hash, manifest_fingerprint, seed)`, and what a later validator (3A validation state and/or cross-segment harness) **MUST** check against `s1_escalation_queue`.

S1 is either **PASS** (its output is a valid authority surface) or **FAIL** (no output or output must be treated as unusable). There is no “partial success”.

---

### 8.1 Local acceptance criteria for 3A.S1

For a given `(parameter_hash, manifest_fingerprint, seed)`, 3A.S1 is **PASS** if and only if **all** of the following hold:

1. **S0 gate and sealed inputs were honoured**

   * `s0_gate_receipt_3A` and `sealed_inputs_3A` for the target `manifest_fingerprint` exist and are schema-valid.
   * `s0_gate_receipt_3A.upstream_gates.segment_1A.status == "PASS"`,
     `segment_1B.status == "PASS"`,
     `segment_2A.status == "PASS"`.
   * Every artefact S1 reads (1A egress, `iso3166_canonical_2024`, `tz_world_2025a`, mixture policy) appears in `sealed_inputs_3A` with:

     * matching `logical_id` and `path`, and
     * `sha256_hex` equal to the digest S1 computes.

   If any of these checks fail, S1 MUST be treated as FAIL.

2. **Mixture policy is present and schema-valid**

   * Exactly one mixture policy artefact for 3A is present in `sealed_inputs_3A` and `sealed_policy_set` with role `"zone_mixture_policy"` (or the agreed role string).
   * The mixture policy content validates against its `schema_ref` (e.g. `schemas.3A.yaml#/policy/zone_mixture_policy_3A`).
   * S1 successfully derives a deterministic `mixture_policy_id` and `mixture_policy_version` and echoes them consistently in all rows of `s1_escalation_queue`.

3. **Country & zone structure is well-defined for all countries in scope**

   * Every `legal_country_iso` that appears in 1A’s `outlet_catalogue` for this `{seed, fingerprint}`:

     * exists in `iso3166_canonical_2024` (or equivalent), and
     * has a well-defined `zone_count_country(c)` derived from sealed `tz_world_2025a`.
   * For each such `c`, `zone_count_country(c)` is a finite integer ≥ 0.
   * If the mixture policy requires at least one potential zone for escalation, `zone_count_country(c) == 0` MUST be either:

     * deterministically classified as monolithic (`is_escalated=false`, `decision_reason` describing the condition), or
     * treated as a configuration error which causes S1 to FAIL; the choice MUST be specified in the mixture policy schema and applied consistently.

4. **Domain coverage and cardinality match 1A**

   Let:

   * `D_1A = { (m,c) }` be the set of distinct `(merchant_id, legal_country_iso)` pairs in `outlet_catalogue` for this `{seed, fingerprint}`.
   * `D_S1 = { (m,c) }` be the corresponding set in `s1_escalation_queue`.

   S1 is PASS only if:

   * `D_S1 == D_1A` (set equality), i.e.:

     * every `(m,c)` in 1A appears exactly once in S1, and
     * S1 does not introduce any extra `(m,c)` pairs.
   * For every `(m,c) ∈ D_1A`,
     `site_count(m,c)` in S1 equals `COUNT(*)` from 1A’s `outlet_catalogue` for that pair.

5. **Per-row invariants hold in `s1_escalation_queue`**

   For every row in `s1_escalation_queue`:

   * `seed` equals the partition token `{seed}`.
   * `manifest_fingerprint` equals the partition token `{manifest_fingerprint}`.
   * `site_count ≥ 1`.
   * `zone_count_country ≥ 0`.
   * `is_escalated` is boolean.
   * `decision_reason`:

     * is a value from the closed vocabulary defined in the mixture policy schema, and
     * is logically consistent with visible fields (e.g. `decision_reason="below_min_sites"` only when `site_count` is below the configured threshold).
   * `mixture_policy_id` and `mixture_policy_version` are present and identical across all rows for this `{seed,fingerprint}`.

   Any schema violation or inconsistent `decision_reason` MUST cause S1 to FAIL.

6. **Decisions are consistent with the mixture policy**

   Given the sealed mixture policy and the decision context (including `site_count`, `zone_count_country`, and any other policy-governed attributes S1 is allowed to use), `is_escalated` and `decision_reason` MUST be the **unique deterministic outcome** of evaluating the policy.

   * If a later validator, replaying the mixture policy logic on `s1_escalation_queue` inputs, finds any row where `is_escalated` or `decision_reason` diverges from the policy, S1 MUST be considered FAIL for that run.

7. **Idempotence**

   * If an existing `s1_escalation_queue` already exists for the same `{seed, manifest_fingerprint}`:

     * Reading, normalising (schema + sort) and comparing it to the newly computed row set yields **exact equality** (row-by-row, field-by-field).
   * If any difference is detected (in rows or values), S1 MUST NOT overwrite the dataset and MUST treat this as an immutability violation (classified under S1’s error taxonomy).

Only when **all** of the above conditions hold may 3A.S1 be marked **PASS** for that `{parameter_hash, manifest_fingerprint, seed}`.

---

### 8.2 Validator hooks for a 3A validation state

A later 3A validation state (e.g. 3A.Sx “Validation & PASS bundle”) MUST treat S1 as follows:

1. **Schema & domain checks**

   * Re-validate `s1_escalation_queue` against `schemas.3A.yaml#/plan/s1_escalation_queue`.
   * Join `s1_escalation_queue` to 1A’s `outlet_catalogue` on `(seed, manifest_fingerprint, merchant_id, legal_country_iso)` and assert:

     * set equality of domains (`D_S1 == D_1A`),
     * `site_count` matches the group-by count from `outlet_catalogue`.

2. **Country/zone consistency**

   * For each distinct `legal_country_iso` in S1:

     * verify that `zone_count_country` matches the counts derived from the sealed `tz_world` reference used elsewhere in 3A,
     * raise a validation error if any `zone_count_country` is inconsistent with the reference.

3. **Policy replay**

   * Read the same mixture policy artefact sealed in S0 (`mixture_policy_id`, `mixture_policy_version`).
   * For each row in `s1_escalation_queue`, recompute the mixture decision from:

     * `site_count`,
     * `zone_count_country`, and
     * any other policy-governed fields (if the policy schema specifies them).
   * Assert that the recomputed `(is_escalated, decision_reason)` matches the stored values for each row.

4. **Aggregate sanity metrics**

   The validation state SHOULD compute and, if appropriate, record in its metrics:

   * `total_pairs = |D_S1|`,
   * `escalated_pairs = COUNT(*) WHERE is_escalated = true`,
   * `monolithic_pairs = COUNT(*) WHERE is_escalated = false`,
   * `escalation_rate = escalated_pairs / total_pairs`,
   * breakdowns by country and/or zone-count buckets (e.g. escalation rate for `zone_count_country ≥ 2`).

These aggregates are non-binding but provide hooks for CI baselines and drift detection.

---

### 8.3 Obligations imposed on downstream 3A states

S1’s acceptance criteria also impose **behavioural obligations** on S2–S4 and the 3A validation state:

1. **Worklist authority**

   * S2/S3/S4 MUST derive their list of merchant×country pairs directly from `s1_escalation_queue` and MUST NOT:

     * add new `(m,c)` pairs not present in S1, or
     * silently drop any `(m,c)` pairs.

2. **Escalation flag is binding**

   * Pairs with `is_escalated = true`:

     * MUST be considered in-scope for zone-level Dirichlet & integerisation.
   * Pairs with `is_escalated = false`:

     * MUST NOT be sent through the Dirichlet / integerisation pipeline.
   * Any zone-level allocation dataset MUST be constructed so that its domain over `(merchant_id, legal_country_iso)` is a subset of the S1 escalated set.

3. **Policy lineage is respected**

   * Downstream states MUST use `mixture_policy_id` and `mixture_policy_version` only for lineage and diagnostics.
   * They MUST NOT try to “re-apply” a different mixture policy to modify which pairs are escalated within the same `{parameter_hash, manifest_fingerprint}`.

---

### 8.4 Handling of S1 failures

If any validator (either an online 3A validation state or an offline harness) detects a violation of the acceptance criteria above, then:

* `s1_escalation_queue` for that `{parameter_hash, manifest_fingerprint, seed}` MUST NOT be used to drive zone allocation.
* Any 3A outputs derived from that S1 snapshot MUST be treated as invalid and excluded from release.
* Recovery MUST follow the change-control process:

  * fix catalogue or policy configuration, or
  * correct implementation bugs, and then
  * re-run 3A.S0 and 3A.S1 (and subsequent states) for a new, clean `manifest_fingerprint` / `parameter_hash` if required.

Under these rules, 3A.S1 is only considered **acceptable** when its escalation decisions are:

* based solely on sealed inputs,
* complete and consistent with 1A and reference structure, and
* reproducible under replay of the sealed mixture policy.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only allowed failure classes** for 3A.S1 and assigns each a **canonical error code**.

Any implementation of S1 MUST:

* classify every non-success outcome into **exactly one** of these codes, and
* surface that code (plus required structured fields) into logs / run-report.

No additional error codes may be invented at this level; if a new class is needed, the spec must be revised.

---

### 9.1 Error taxonomy overview

3A.S1 can fail only for these reasons:

1. S0 gate or upstream gate status is unusable.
2. Catalogue / schema layer is malformed or inconsistent.
3. Mixture policy is missing or invalid.
4. Country/zone structure is inconsistent with references.
5. Sealed input resolution or digest mismatch.
6. Domain / count mismatch vs 1A.
7. Output schema or decision inconsistency.
8. Immutability / idempotence violations.
9. Infrastructure / I/O failures.

Each is mapped to a specific `E3A_S1_XXX_*` code.

---

### 9.2 S0 / upstream gate failures

#### `E3A_S1_001_S0_GATE_MISSING_OR_INVALID`

**Condition**

Raised when S1 cannot rely on 3A.S0 for this `manifest_fingerprint`, e.g.:

* `s0_gate_receipt_3A` or `sealed_inputs_3A` is missing,
* either S0 artefact fails its own schema validation,
* the `manifest_fingerprint` embedded in `s0_gate_receipt_3A` or `sealed_inputs_3A` does not match the partition token,
* `parameter_hash` or `seed` in `s0_gate_receipt_3A` does not match the invocation triple.

**Semantics**

* S1 MUST NOT attempt to proceed “without S0”; S0 is a hard prerequisite.

**Required fields**

* `reason ∈ {"missing_gate_receipt","missing_sealed_inputs","schema_invalid","identity_mismatch"}`

**Retryability**

* **Non-retryable** until S0 is successfully rerun and corrected for this `manifest_fingerprint`.

---

#### `E3A_S1_002_UPSTREAM_GATE_NOT_PASS`

**Condition**

Raised when S1 successfully reads `s0_gate_receipt_3A` but finds that any upstream gate status is not `"PASS"`, i.e.:

* `upstream_gates.segment_1A.status != "PASS"` or
* `upstream_gates.segment_1B.status != "PASS"` or
* `upstream_gates.segment_2A.status != "PASS"`.

**Semantics**

* S1 MUST treat this as a hard precondition failure. It MUST NOT re-run HashGate itself or ignore upstream failures.

**Required fields**

* `segment ∈ {"1A","1B","2A"}`
* `reported_status` — the non-PASS value from `s0_gate_receipt_3A`.

**Retryability**

* **Non-retryable** until the affected upstream segment is fixed and its gate is PASS, then S0 re-run if necessary.

---

### 9.3 Catalogue & schema failures

#### `E3A_S1_003_CATALOGUE_MALFORMED`

**Condition**

Raised when S1 cannot load or validate catalogue artefacts it needs, e.g.:

* missing or malformed:

  * `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, `schemas.3A.yaml`,
  * `dataset_dictionary.layer1.{1A,3A}.yaml`,
  * `artefact_registry_{1A,3A}.yaml`,
* schema validation failures for any of the above.

**Required fields**

* `catalogue_id` — identifier of the failing artefact (e.g. `"dataset_dictionary.layer1.1A"`, `"schemas.3A.yaml"`).

**Retryability**

* **Non-retryable** until the catalogue is corrected.

---

### 9.4 Mixture policy failures

#### `E3A_S1_004_POLICY_MISSING_OR_AMBIGUOUS`

**Condition**

Raised when S1 cannot get a unique, required mixture policy artefact, e.g.:

* no row in `sealed_inputs_3A` / `sealed_policy_set` with `role="zone_mixture_policy"` for this `manifest_fingerprint`,
* more than one distinct artefact appears to satisfy the mixture policy role and S1 cannot deterministically choose one.

**Required fields**

* `missing_roles[]` — SHOULD include `"zone_mixture_policy"` when missing.
* `conflicting_ids[]` — list of logical IDs where multiple candidates exist (may be empty if purely missing).

**Retryability**

* **Non-retryable** without configuration / parameter set change (fix policy wiring and potentially recompute `parameter_hash`).

---

#### `E3A_S1_005_POLICY_SCHEMA_INVALID`

**Condition**

Raised when the mixture policy artefact exists but fails validation against its `schema_ref` (e.g. `schemas.3A.yaml#/policy/zone_mixture_policy_3A`), including:

* missing required fields (e.g. `min_sites_for_escalation`),
* invalid enum values,
* inconsistent thresholds (e.g. min > max) that violate the schema.

**Required fields**

* `logical_id` — mixture policy ID (e.g. `"zone_mixture_policy_3A"`),
* `schema_ref` — full schema anchor string,
* `violation_count` — number of schema validation errors detected.

**Retryability**

* **Non-retryable** until the policy content is fixed and, if part of 𝓟, a new `parameter_hash` computed.

---

### 9.5 Country/zone structure failures

#### `E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT`

**Condition**

Raised when S1 cannot derive a coherent `zone_count_country(c)` for all countries in scope, in ways that the mixture policy defines as unrecoverable, for example:

* `legal_country_iso` appears in 1A `outlet_catalogue` but not in `iso3166_canonical_2024`,
* `tz_world_2025a` contains no tz polygons for a country that has outlets, and the mixture policy does **not** define a deterministic monolithic fallback,
* zone sets derived for a country violate internal policy assumptions (e.g. required “multi-zone only” rule but `zone_count_country(c) == 1` and policy does not allow monolithic classification).

**Required fields**

* `country_iso` — the offending `legal_country_iso`,
* `reason ∈ {"unknown_country","no_zones_defined","policy_incompatible_zone_structure"}`.

**Retryability**

* **Non-retryable** without fixing references (e.g. `tz_world`/ISO mapping) or updating the mixture policy schema and content.

---

### 9.6 Sealed input resolution / digest failures

#### `E3A_S1_007_SEALED_INPUT_MISMATCH`

**Condition**

Raised when S1 attempts to read an artefact that S0 claims is sealed, but:

* no matching row exists in `sealed_inputs_3A` (by `logical_id` and `path`), or
* the SHA-256 digest S1 computes does not match `sha256_hex` recorded in `sealed_inputs_3A`.

Typical examples:

* `outlet_catalogue` path returned by dictionary/registry disagrees with `sealed_inputs_3A.path`,
* mixture policy bytes changed after S0 ran, but `sealed_inputs_3A` still reflects the old digest.

**Required fields**

* `logical_id` — ID of the problematic artefact (e.g. `"outlet_catalogue"`, `"zone_mixture_policy_3A"`),
* `path` — resolved path S1 attempted to read,
* `sealed_sha256_hex` — digest from `sealed_inputs_3A` (if present),
* `computed_sha256_hex` — digest computed by S1 (if a file existed).

**Retryability**

* **Non-retryable** until the sealed artefacts, catalogue and/or S0 run are reconciled. This usually indicates corruption, unsynchronised updates, or an incorrect manifest.

---

### 9.7 Domain / count / consistency failures vs 1A

#### `E3A_S1_008_DOMAIN_MISMATCH_1A`

**Condition**

Raised when the domain of `s1_escalation_queue` does not match 1A for this `{seed, manifest_fingerprint}`, i.e.:

* there exists `(m,c)` in 1A’s `outlet_catalogue` with no corresponding row in S1, or
* there exists `(m,c)` in S1 with no corresponding rows in `outlet_catalogue`.

**Required fields**

* `missing_pairs_in_s1_count` — number of `(m,c)` present in 1A but missing in S1,
* `extra_pairs_in_s1_count` — number of `(m,c)` present in S1 but absent in 1A`,
* MAY include sampled examples for diagnostics (IDs must adhere to any privacy constraints).

**Retryability**

* **Non-retryable** until the S1 implementation or its grouping logic is fixed; indicates a defect in S1’s aggregation or join logic, not transient data.

---

#### `E3A_S1_009_SITE_COUNT_MISMATCH`

**Condition**

Raised when there is a mismatch between `site_count` in S1 and the true count in 1A, i.e.:

* for some `(m,c)`,
  `s1_escalation_queue.site_count(m,c) != COUNT(*)` from `outlet_catalogue` for that pair.

**Required fields**

* `pair_examples[]` — one or more sample `(merchant_id, legal_country_iso)` pairs where the mismatch occurs,
* `expected_count` and `observed_count` for at least one example.

**Retryability**

* **Non-retryable** until S1’s counting logic is corrected; indicates data corruption or implementation bug.

---

### 9.8 Output schema & decision consistency failures

#### `E3A_S1_010_OUTPUT_SCHEMA_INVALID`

**Condition**

Raised when the constructed `s1_escalation_queue` fails validation against `schemas.3A.yaml#/plan/s1_escalation_queue`, for example:

* missing required fields (`is_escalated`, `decision_reason`, etc.),
* invalid values (e.g. negative `site_count`, `decision_reason` not in the allowed enum),
* path↔embed mismatch (`seed`/`manifest_fingerprint` fields not matching partition tokens).

S1 MUST validate its output before publishing; this error indicates a violation of the contract.

**Required fields**

* `violation_count` — number of validation errors,
* `example_field` — one representative field that failed (if safe to log).

**Retryability**

* **Retryable only after implementation fix**; indicates S1 is not respecting its own schema.

---

#### `E3A_S1_011_POLICY_REPLAY_MISMATCH`

**Condition**

Raised when S1’s decisions cannot be justified by the sealed mixture policy under deterministic replay, e.g.:

* When a validation harness (or S1 in a self-check mode) replays the mixture policy on `site_count`, `zone_count_country` and any other context fields, it finds that:

  * `is_escalated` in S1 disagrees with what the policy would produce for one or more rows, or
  * `decision_reason` does not match the branch actually taken according to the policy.

This code is used by S1 if it performs an internal consistency check, or by a 3A validation state when evaluating S1.

**Required fields**

* `pair_examples[]` — list of one or more `(merchant_id, legal_country_iso)` pairs that fail replay (IDs may be redacted or hashed if required).
* `policy_id` and `policy_version` — from the mixture policy.

**Retryability**

* **Non-retryable** until S1’s implementation or the policy schema/semantics are corrected; indicates a bug or configuration mismatch.

---

### 9.9 Immutability / idempotence failures

#### `E3A_S1_012_IMMUTABILITY_VIOLATION`

**Condition**

Raised when S1 detects that a dataset already exists at the target path for `{seed, manifest_fingerprint}` and its content is **not** identical to the newly computed `s1_escalation_queue`, e.g.:

* existing rows differ in `is_escalated` or `decision_reason` for some `(m,c)`,
* existing rows differ in `site_count`, `zone_count_country`, or policy metadata.

**Required fields**

* `difference_kind ∈ {"row_set","field_value"}`
* `difference_count` — number of differing rows detected (may be capped for logging).

**Retryability**

* **Non-retryable** until the conflict is resolved. Operators MUST decide which snapshot (if any) is authoritative and either:

  * remove/rename the conflicting artefacts, or
  * re-run S0/S1 with a new `manifest_fingerprint` / `parameter_hash` as appropriate.

---

### 9.10 Infrastructure / I/O failures

#### `E3A_S1_013_INFRASTRUCTURE_IO_ERROR`

**Condition**

Raised when S1 cannot complete due to non-logical environment issues, e.g.:

* transient connectivity or object store errors when reading inputs or writing outputs,
* permission errors,
* filesystem exhaustion or similar.

This code MUST NOT be used for logical failures covered by 001–012.

**Required fields**

* `operation ∈ {"read","write","list","stat"}`
* `path` — where the operation failed (if available),
* `io_error_class` — short string classification (e.g. `"timeout"`, `"permission_denied"`, `"not_found"`, `"quota_exceeded"`).

**Retryability**

* **Potentially retryable**, subject to infrastructure policy.

  * Orchestration MAY retry automatically, but S1 MUST still meet all acceptance criteria (§8) before any output is considered valid.

---

### 9.11 Run-report mapping

As with S0, each S1 run MUST end in exactly one of:

* `status="PASS"` with `error_code = null`, or
* `status="FAIL"` with `error_code` equal to one of the codes above.

Any consumer that sees `status="FAIL"` MUST treat `s1_escalation_queue` as **non-authoritative** for that `(parameter_hash, manifest_fingerprint, seed)`; zone allocation MUST NOT rely on it until the cause is addressed and S1 has been successfully re-run.

---

## 10. Observability & run-report integration *(Binding)*

This section defines what **3A.S1 MUST emit** for observability, and how it must integrate with the Layer-1 run-report. The aim is that an operator or audit harness can answer, for any `(parameter_hash, manifest_fingerprint, seed)`:

* Did S1 run?
* Did it succeed or fail, and why?
* How many merchant×country pairs were classified, and how many were escalated?
* Which policy/version was in force?

—without re-deriving everything from scratch.

S1 MUST NOT log row-level business data (e.g. full merchant IDs in bulk, per-site information, raw policy content beyond IDs/versions).

---

### 10.1 Structured logging requirements

3A.S1 MUST emit **structured logs** (e.g. JSON records) for three lifecycle events: **start**, **success**, and **failure**.

#### 10.1.1 State start

One log event at the beginning of each invocation:

* Required fields:

  * `layer = "layer1"`
  * `segment = "3A"`
  * `state = "S1"`
  * `parameter_hash` (hex64)
  * `manifest_fingerprint` (hex64)
  * `seed` (uint64)
  * `attempt` (integer, if supplied by the orchestrator; otherwise a fixed default such as 1)
* Optional fields:

  * `trace_id` or equivalent correlation ID, if provided by infrastructure.
* Log level: `INFO`.

#### 10.1.2 State success

One log event if and only if S1 meets all acceptance criteria in §8:

* Required fields:

  * All “start” fields
  * `status = "PASS"`
  * `error_code = null`
  * `pairs_total` — |D|, number of merchant×country pairs in `s1_escalation_queue`
  * `pairs_escalated` — count where `is_escalated = true`
  * `pairs_monolithic` — count where `is_escalated = false`
  * `escalation_rate` — `pairs_escalated / pairs_total` as a float or rational
  * `mixture_policy_id`
  * `mixture_policy_version`
* Recommended additional fields:

  * `pairs_by_zone_count_bucket` — serialised map, e.g.
    `{ "zone_count=0": n0, "zone_count=1": n1, "zone_count>=2": n2 }`
* Optional:

  * `elapsed_ms` — wall-clock duration measured by the orchestrator; this MUST NOT feed back into any S1 logic.
* Log level: `INFO`.

#### 10.1.3 State failure

One log event if and only if S1 terminates without satisfying §8:

* Required fields:

  * All “start” fields
  * `status = "FAIL"`
  * `error_code` — one of the codes from §9 (e.g. `E3A_S1_004_POLICY_MISSING_OR_AMBIGUOUS`)
  * `error_class` — coarse label (e.g. `"S0_GATE"`, `"UPSTREAM_GATE"`, `"CATALOGUE"`, `"POLICY"`, `"ZONE_STRUCTURE"`, `"SEALED_INPUT"`, `"DOMAIN_MISMATCH"`, `"OUTPUT_SCHEMA"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`)
  * `error_details` — structured object containing the required fields for that error code from §9 (e.g. `segment`, `logical_id`, `country_iso`, etc.)
* Recommended additional fields:

  * `pairs_total` — if S1 reached the aggregation step before failing (else omitted or `0`)
  * `pairs_escalated` — if defined (else omitted)
* Optional:

  * `elapsed_ms` — if available.
* Log level: `ERROR`.

All structured logs MUST be machine-parseable, and MUST NOT include raw policy bodies or per-row business data.

---

### 10.2 Segment-state run-report row (Layer-1 integration)

Layer-1 maintains a **segment-state run-report** dataset (e.g. `run_report.layer1.segment_states`) covering all states (including 3A.S1). For each invocation of S1 at `(parameter_hash, manifest_fingerprint, seed)`, exactly **one row** MUST be written.

The run-report schema is defined at Layer-1, but for S1, the row MUST include at least:

* **Identity & context**

  * `layer = "layer1"`
  * `segment = "3A"`
  * `state = "S1"`
  * `parameter_hash`
  * `manifest_fingerprint`
  * `seed`
  * `attempt` (if available)

* **Outcome**

  * `status ∈ {"PASS","FAIL"}`
  * `error_code` — `null` on PASS; one of §9 codes on FAIL
  * `error_class` — as in §10.1.3
  * `first_failure_phase` — optional enum in
    `{ "S0_GATE", "SEALED_INPUTS", "POLICY_LOAD", "ZONE_STRUCTURE", "AGGREGATE_COUNTS", "DECISION_EVAL", "OUTPUT_WRITE", "IMMUTABILITY", "INFRASTRUCTURE" }`

* **Upstream gate summary (from S0)**

  * `s0_gate_status ∈ {"PASS","FAIL","NOT_FOUND"}`
  * `gate_1A_status ∈ {"PASS","FAIL","NOT_CHECKED"}`
  * `gate_1B_status ∈ {"PASS","FAIL","NOT_CHECKED"}`
  * `gate_2A_status ∈ {"PASS","FAIL","NOT_CHECKED"}`

* **Mixture policy summary**

  * `mixture_policy_id`
  * `mixture_policy_version`

* **Escalation classification summary** (only required when `status="PASS"`; MAY be populated on FAIL if available)

  * `pairs_total`
  * `pairs_escalated`
  * `pairs_monolithic`
  * `escalation_rate` — float or rational
  * `pairs_by_zone_count_bucket` — serialised map or JSON object (e.g. as in §10.1.2)

* **Catalogue versions**

  * At minimum, the same catalogue version fields S0 records (or a subset), such as:

    * `schemas_layer1_version`
    * `schemas_3A_version`
    * `dictionary_layer1_1A_version`
    * `dictionary_layer1_3A_version`

* **Timing and correlation**

  * `started_at_utc` — orchestrator-provided or derived from a deterministic run-environment artefact; MUST NOT affect S1 behaviour.
  * `finished_at_utc` — same source.
  * `elapsed_ms` — derived.
  * `trace_id` — if infrastructure provides one.

The S1 run-report row MUST be:

* consistent with `s1_escalation_queue` (counts and escalation_rate match), and
* consistent with `s0_gate_receipt_3A` (upstream gate statuses and catalogue versions).

---

### 10.3 Metrics & counters

In addition to logs and run-report, S1 MUST expose a minimal set of **numeric metrics** suitable for dashboards/alerts (export mechanism is implementation-specific but semantics are binding).

At minimum:

* `mlr_3a_s1_runs_total{status="PASS"|"FAIL"}`

  * Monotone counter, incremented once per S1 run.

* `mlr_3a_s1_pairs_total` (gauge)

  * Number of merchant×country pairs processed in the most recent successful run for a given `{seed, fingerprint}` (labelled appropriately).

* `mlr_3a_s1_pairs_escalated` (gauge)

  * As above, restricted to `is_escalated = true`.

* `mlr_3a_s1_escalation_rate` (gauge)

  * `pairs_escalated / pairs_total` for the most recent successful run.

* `mlr_3a_s1_zone_structure_errors_total`

  * Counter incremented whenever `E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT` occurs.

* `mlr_3a_s1_policy_errors_total`

  * Counter incremented for any `E3A_S1_004_*` or `E3A_S1_005_*` failure.

* `mlr_3a_s1_duration_ms` (histogram)

  * Distribution of S1 run durations (`elapsed_ms`), for capacity planning and SLOs.

Metrics MUST:

* be derivable from the same information recorded in logs/run-report, and
* contain no raw merchant IDs or paths; labels should be limited to state/segment/status and coarse classes (e.g. error_class).

---

### 10.4 Correlation & traceability

To enable tracing across the full 3A pipeline:

1. **Correlation with S0 and later 3A states**

   * S1’s run-report row MUST be joinable to S0 and later 3A states via the common tuple:

     * `(layer="layer1", segment="3A", parameter_hash, manifest_fingerprint, seed)`.
   * If a `trace_id` is used, it SHOULD be consistent across S0, S1, and subsequent 3A states invoked for the same run.

2. **Linkage to artefacts**

   * Although S1 does not produce new validation bundles, the future 3A validation state MUST:

     * include `s1_escalation_queue` (or at least its digest and schema_ref) in its own validation bundle index, so that an auditor can trace from:

       * run-report row →
       * validation bundle →
       * S1 artefact (`s1_escalation_queue`) →
       * S0 artefacts and sealed inputs.

---

### 10.5 Retention, access control & privacy

Even though S1 operates on aggregated counts, the following are binding:

1. **Retention**

   * `s1_escalation_queue` MUST be retained for at least:

     * as long as any 3A outputs computed from it remain in use, and
     * as long as any downstream models or analysis relying on 3A zone allocation are considered live.
   * Deleting `s1_escalation_queue` while its dependent artefacts remain in circulation is out-of-spec.

2. **Access control**

   * Access to S1 logs, run-report and `s1_escalation_queue` SHOULD be limited to principals authorised to see aggregated planning data and configuration.
   * None of S1’s observability artefacts may include:

     * per-site data,
     * raw policy bodies (beyond IDs/versions), or
     * any secrets/credentials.

3. **No row-level leakage via observability**

   * Logs and metrics MUST NOT include:

     * full merchant identifiers in bulk,
     * detailed decision context per merchant×country.
   * Where sample IDs are needed for debugging (e.g. in `pair_examples` for an error), redaction or hashing policies defined at Layer-1 MUST be followed.

---

### 10.6 Relationship to Layer-1 run-report governance

Layer-1 may impose additional run-report fields (e.g. generic columns for all states). Where there is a conflict:

* Layer-1 run-report schema controls the **shape and required columns**.
* This section controls what 3A.S1 MUST populate for its slice of that schema and how those values relate to `s1_escalation_queue` and S0 artefacts.

Under these rules, every S1 invocation is:

* **observable** (through structured logs),
* **summarised** (via a single run-report row), and
* **auditable** (via `s1_escalation_queue` + S0 artefacts + the future 3A validation bundle),

without exposing raw business data or violating the authority chain set up by 3A.S0.

---

## 11. Performance & scalability *(Informative)*

This section describes how 3A.S1 is expected to behave at scale, and where implementation effort should go to keep it cheap and predictable. The binding rules remain in §§1–10.

---

### 11.1 Workload shape

3A.S1 is deliberately lightweight:

* It does **one group-by** over 1A egress (`outlet_catalogue`) to compute `site_count` per merchant×country.
* It does **one pass** over country-level references (`iso3166_canonical_2024`, `tz_world_2025a`) to derive `zone_count_country`.
* It evaluates the **mixture policy** per merchant×country row.
* It writes a single table `s1_escalation_queue` with **O(#merchant×country pairs)** rows.

S1 never:

* touches per-site geometry (no lat/lon),
* touches per-site tzids,
* uses RNG, or
* scans any Layer-2 or 2B surfaces.

Asymptotically, cost is dominated by the number of **rows in `outlet_catalogue`** and the number of **distinct merchant×country pairs**.

---

### 11.2 Complexity drivers

The main complexity components are:

1. **Grouping 1A egress**

   * Input: `outlet_catalogue` with `R` rows.
   * Operation: group by `(merchant_id, legal_country_iso)` to compute counts `site_count`.
   * Complexity: ~O(R) with a hash-aggregate or O(R log R) if sorting; in practice R is “number of outlets”, which is large but already unavoidable upstream.

2. **Country-zone structure**

   * Input: `tz_world_2025a` + `iso3166_canonical_2024`.
   * Operation: derive `Z(c)` sets and `zone_count_country(c)` for countries used by `outlet_catalogue`.
   * Complexity: depends on how `tz_world` is indexed; with a pre-built mapping (e.g. precomputed ingress artefact) it is effectively O(#countries × #zones_per_country).
   * This work is typically small compared to 1A’s outlet volume.

3. **Policy evaluation**

   * Input domain: `D` = set of merchant×country pairs.
   * Operation: evaluate a few predicates per row (min sites, min zones, allow/deny lists, etc.).
   * Complexity: O(|D|) with tiny constant factors; negligible compared to the group-by.

4. **Writing `s1_escalation_queue`**

   * Row count: |D|.
   * Writing a Parquet table with a few columns is O(|D|) and typically small relative to the upstream 1A write.

In short, S1 scales linearly in:

* number of outlets (for aggregation), and
* number of merchant×country pairs (for decision evaluation).

---

### 11.3 Typical size relationships

In realistic workloads:

* |D| ≪ R:

  * Many outlets exist per merchant×country; S1 produces one row per pair, not per outlet.
* Reference tables are tiny compared to `outlet_catalogue`.

So:

* **CPU & memory**: dominated by 1A’s volume; S1 adds a single additional pass over `outlet_catalogue` and writes a much smaller table.
* **I/O**: S1’s extra I/O is “read `outlet_catalogue` once more + read `tz_world` / ISO once + write a small Parquet”.

If 1A handles, say, 10M outlets, S1 might handle:

* ~10M rows in the group-by,
* but only ~O(100k) rows in `s1_escalation_queue` (depending on merchant/country granularity).

---

### 11.4 Memory footprint

S1 can be implemented with modest memory use:

* The group-by over `outlet_catalogue` can be:

  * streaming with a hash map `(merchant_id, legal_country_iso) → count`, or
  * sort-then-aggregate to reduce peak memory (at the cost of I/O).
* The `country_zone_structure` table is small:

  * one row per country, not per site.

Memory is proportional to:

* number of distinct merchant×country pairs (for counts and decision structs), and
* number of countries (for zone structure),

not total outlets.

Implementations SHOULD:

* avoid loading full `outlet_catalogue` into memory if it’s huge;
* use streaming aggregation and/or external sort as needed.

---

### 11.5 Concurrency & parallelism

S1 is a natural candidate for **intra-run parallelism**:

* The group-by and policy evaluation can be parallelised over partitions of `outlet_catalogue`:

  * e.g. shard by `merchant_id` hash, then merge partial aggregates.
* Decisions per `(m,c)` are embarrassingly parallel once `site_count` and `zone_count_country` are known.

It is also **embarrassingly parallel across runs**:

* Different `(parameter_hash, manifest_fingerprint, seed)` triples can run S1 independently.

Constraints:

* Writers must still enforce **atomic snapshot semantics** per `{seed, fingerprint}` (no concurrent conflicting writers).
* Any global caches (e.g. `tz_world` decode) must be thread-safe if shared.

---

### 11.6 Expected runtime and bottlenecks

Given a reasonably provisioned environment:

* **Time to classify** is close to time to scan `outlet_catalogue` once more.
* Reference and policy loads are negligible.
* Writing `s1_escalation_queue` is quick compared to writing 1A/1B/2A egress.

Potential bottlenecks:

* If `outlet_catalogue` is extremely large and stored in many small files, file-open overhead and seek patterns can dominate; implementers SHOULD:

  * coalesce files sensibly upstream,
  * or use a columnar store with efficient metadata to reduce open cost.

S1 is deliberately designed so that its runtime is **small compared to**:

* 1A (NB fitting, sampling),
* 1B (spatial allocation & jitter),
* future 3A states (Dirichlet & integerisation), and
* 2B routing.

---

### 11.7 Tuning levers (non-normative)

Implementers can tune S1 without changing semantics by:

* **Choosing aggregation strategy**:

  * hash-aggregate vs sort-aggregate based on the cardinality of `(merchant_id, legal_country_iso)`.

* **Precomputing zone structure**:

  * If another process already maintains a `country → {tzid}` view consistent with `tz_world`, S1 can reuse that instead of re-deriving from geometry, as long as the artefact is sealed and referenced in S0.

* **Caching reference artefacts**:

  * `iso3166_canonical_2024` and `tz_world_2025a` change rarely; they can be cached across runs.

Any such optimisation MUST NOT:

* change the domain or contents of `s1_escalation_queue`,
* bypass the requirement that inputs be sealed via 3A.S0, or
* introduce non-determinism.

Under these expectations, 3A.S1 remains a **lightweight, scalable classification step** whose cost is dominated by a single additional group-by over 1A egress, and whose performance should not be a limiting factor in end-to-end 3A throughput.

---

## 12. Change control & compatibility *(Binding)*

This section defines **how the 3A.S1 contract is allowed to evolve over time**, and what guarantees consumers can rely on when:

* the S1 spec itself changes,
* the mixture policy schema/content changes, or
* upstream/layer-wide contracts evolve.

The goal is that downstream 3A states (S2–S4), validation harnesses and operators can reason about compatibility from **version tags + fingerprints + `parameter_hash`**, without guessing.

---

### 12.1 Scope of change control

Change control for 3A.S1 covers:

1. The **shape and semantics** of its output dataset:

   * `s1_escalation_queue` (columns, keys, partitioning, meaning of `is_escalated`, `decision_reason`, etc.).

2. The **normative mapping** from inputs to outputs:

   * domain equality `D_S1 == D_1A` (all merchant×country pairs present in 1A),
   * how `site_count` and `zone_count_country` are derived,
   * how the mixture policy is applied to produce `is_escalated` and `decision_reason`.

3. The **error taxonomy** and acceptance criteria in §§8–9.

It explicitly does **not** govern:

* physical execution strategy (single-process vs distributed, streaming vs batch), or
* global Layer-1 definitions of `parameter_hash`, `manifest_fingerprint`, or `seed`.

---

### 12.2 S1 contract versioning

The S1 contract has a **dataset-level version**, carried as:

* the `version` field in the `dataset_dictionary.layer1.3A.yaml` entry for `s1_escalation_queue` (e.g. `"1.0.0"`), and
* the version tag in `artefact_registry_3A.yaml` for `mlr.3A.s1_escalation_queue`.

Rules:

1. **Single authoritative version per dataset contract.**

   * `dataset_dictionary.layer1.3A.yaml` and `artefact_registry_3A.yaml` MUST agree on the `version` for `s1_escalation_queue`.
   * Any change to the S1 contract that affects shape or semantics of `s1_escalation_queue` MUST be accompanied by a semver bump and updates in both places.

2. **Semver meaning.**

   * `MAJOR.MINOR.PATCH`:

     * **PATCH** (`x.y.z → x.y.(z+1)`): clarifications or bug fixes that do not change the observable dataset for any compliant implementation (e.g. tightening docs, fixing typos in the spec, making validators stricter without changing PASS cases).
     * **MINOR** (`x.y.z → x.(y+1).0`): backwards-compatible extensions (e.g. new optional columns in `s1_escalation_queue`, new error codes, new diagnostic fields) that older consumers can ignore safely.
     * **MAJOR** (`x.y.z → (x+1).0.0`): breaking changes to S1’s output shape, semantics, or mapping from inputs to decisions.

3. **Version anchoring for consumers.**

   * Consumers MUST NOT infer behaviour from deployment date or binary build IDs; they MUST rely on:

     * the `version` declared for `s1_escalation_queue` in the dictionary/registry, and
     * the schema anchor `schemas.3A.yaml#/plan/s1_escalation_queue`.

---

### 12.3 Backwards-compatible changes (MINOR/PATCH)

The following changes are considered **backwards-compatible** for S1, provided they follow the rules below:

1. **Adding optional fields to `s1_escalation_queue`.**

   * New optional columns (e.g. `eligible_for_escalation`, `dominant_zone_share_bucket`, `extra_diagnostics`) MAY be added to the schema if:

     * they have clear default semantics when absent, and
     * they do not change the meaning of existing fields (`is_escalated`, `decision_reason`, `site_count`, `zone_count_country`).
   * Older consumers MUST be able to ignore these columns without misinterpreting the dataset.

2. **Extending `decision_reason` vocabulary in a compatible way.**

   * New reason codes MAY be added to the `decision_reason` enum (e.g. to distinguish different “forced monolithic” variants), if:

     * each new code’s semantics are a refinement of a previous lumped category, and
     * existing consumer logic treating “anything monolithic” or “anything escalated” continues to work.
   * Removing or renaming existing codes is **not** backward-compatible (see §12.4).

3. **Stronger validation / additional error codes.**

   * Introducing new internal validations (e.g. extra consistency checks between `site_count`, `zone_count_country`, and policy thresholds) that:

     * never change which runs are PASS under the old contract, but
     * may convert some previously “silently bad” runs into explicit FAILs.
   * Adding new `E3A_S1_XXX_*` error codes is allowed so long as:

     * existing codes keep their original meaning, and
     * downstream systems treat unknown codes as generic FAIL.

4. **Adding diagnostics / metrics / logging fields.**

   * New metrics, run-report fields or log fields that do not alter decisions or the shape of `s1_escalation_queue` are backwards-compatible.

These changes do **not** require a new `manifest_fingerprint` contract; they only tighten or extend how S1 reports on its work. They MAY require a MINOR or PATCH bump of the dataset version depending on whether schema changes are visible.

---

### 12.4 Breaking changes (MAJOR)

The following are **breaking changes** and MUST trigger a **MAJOR** bump of the S1 contract version (and co-ordinated schema/dictionary/registry updates):

1. **Altering output identity, shape, or partitions.**

   * Changing the primary key semantics (e.g. dropping `legal_country_iso` or changing the domain from “merchant×country” to something else).
   * Changing the partition key set (e.g. adding or removing `seed` or `fingerprint`).
   * Renaming `s1_escalation_queue` or changing its path template in a way not expressible as a simple version bump in the dictionary.
   * Removing or changing the type of required columns (e.g. making `is_escalated` tri-state, dropping `site_count`).

2. **Changing core semantics of `is_escalated` or `decision_reason`.**

   * Reinterpreting `is_escalated = true/false` to mean anything other than “MUST be processed by zone allocation” / “MUST NOT be processed by zone allocation” for Segment 3A.
   * Reusing existing `decision_reason` codes for different logical conditions than originally defined (e.g. turning `"below_min_sites"` into “too many zones”).

3. **Relaxing domain and count invariants vs 1A.**

   * Allowing `s1_escalation_queue` to omit certain `(merchant_id, legal_country_iso)` pairs from 1A’s `outlet_catalogue` without marking S1 as FAIL.
   * Allowing `site_count` in S1 to differ from the true count in 1A without marking S1 as FAIL.

4. **Relaxing S0 / sealed-input obligations.**

   * Allowing S1 to read artefacts that are not present in `sealed_inputs_3A`, or to proceed without a valid `s0_gate_receipt_3A`.
   * Allowing S1 to re-implement its own upstream gate logic rather than deferring to S0.

5. **Changing immutability and idempotence guarantees.**

   * Allowing S1 to overwrite an existing `s1_escalation_queue` with a different row set or different escalation decisions for the same `{seed, manifest_fingerprint}` and stable catalogue.

Any such change requires:

* a new **MAJOR** version for the `s1_escalation_queue` dataset in the dictionary,
* updated schema anchor (or updated schema at that anchor, depending on the Layer-1 versioning strategy), and
* explicit migration guidance for downstream consumers (e.g. validators, S2–S4) on how to handle different versions.

---

### 12.5 Mixture policy evolution vs `parameter_hash`

The 3A zone mixture policy artefact is part of the governed parameter set 𝓟 and is referenced explicitly in S1 via `mixture_policy_id` and `mixture_policy_version`.

Binding rules:

1. **Any semantic change to the mixture policy content MUST change `parameter_hash`.**

   * Modifying the content of the `zone_mixture_policy_3A` artefact in a way that could change classification decisions (e.g. different thresholds, new force-escalate lists) MUST be treated as a parameter change.
   * Layer-1 governance MUST recompute `parameter_hash` and typically `manifest_fingerprint` to reflect the new governed parameter set.

2. **S1 MUST NOT silently re-seal a changed policy under the same `parameter_hash`.**

   * If S1 observes that the digest (`sha256_hex`) of the mixture policy artefact no longer matches what S0 sealed for this `parameter_hash`, it MUST fail (e.g. `E3A_S1_007_SEALED_INPUT_MISMATCH`), not proceed.

3. **Adding optional policy knobs.**

   * Adding new optional fields to the mixture policy schema that have no effect when left at default (e.g. extra diagnostics) is backward-compatible, provided:

     * they are correctly covered by the schema, and
     * turning them on (i.e. changing behaviour) is treated as a parameter change (new `parameter_hash`).

4. **Breaking policy schema changes.**

   * Removing or repurposing existing fields in the mixture policy schema, or changing their meaning, is a breaking change for the **policy**, not necessarily for S1.
   * Such changes MUST:

     * go through the policy’s own versioning (e.g. `policy_version`), and
     * be co-ordinated with S1 spec/runtime changes if they alter how decisions are evaluated.

In all cases, **classification differences** for the same `(manifest_fingerprint, seed)` MUST only happen when either:

* `parameter_hash` changed (policy content change), or
* the S1 contract version changed (spec-level change, requiring explicit migration).

---

### 12.6 Catalogue evolution (schemas, dictionaries, registries)

S1 depends heavily on catalogue artefacts. The following apply:

1. **Schema evolution for `s1_escalation_queue`.**

   * Adding optional fields in `schemas.3A.yaml#/plan/s1_escalation_queue` is allowed as a MINOR change.
   * Removing or changing the type/meaning of required fields is a MAJOR change (see §12.4).

2. **Dictionary evolution.**

   * Changing the `id`, `path`, `partitioning` or `schema_ref` of `s1_escalation_queue` is a breaking change and must be accompanied by:

     * a MAJOR version bump of the dataset contract, and
     * co-ordinated updates in users of S1 (S2–S4, validators).
   * Adding new datasets for extra diagnostics is backwards-compatible as long as:

     * they have their own IDs and schema_refs, and
     * S1 spec is updated explicitly if it starts producing them.

3. **Registry evolution.**

   * Adding additional artefacts to `artefact_registry_3A.yaml` that S1 does not use is backwards-compatible.
   * Removing or renaming the `mlr.3A.s1_escalation_queue` artefact, or changing its `path` or `schema` fields, is a breaking change and must be synchronised with a MAJOR version bump.

---

### 12.7 Deprecation strategy

When evolving S1, the preferred strategy is:

1. **Introduce new behaviour alongside old.**

   * Add new optional columns, error codes, or diagnostics with a MINOR version bump.
   * Keep existing semantics intact so old consumers continue to work.

2. **Signal deprecation explicitly.**

   * If a field or behaviour is planned to be removed, the S1 spec and/or a later validation state MAY include a non-normative `deprecation` note, such as:

     * “`decision_reason="legacy_default"` is deprecated and will be removed in version 2.0.0”.

3. **Remove only with a MAJOR bump.**

   * When incompatible removal or redefinition is required, perform a MAJOR version bump and update all dependent components accordingly.

Historic outputs (produced under older S1 versions) MUST NOT be mutated in-place to fit a new schema; they remain as they were and are interpreted under their original contract.

---

### 12.8 Cross-version operation

Different manifests may legitimately use different S1 versions over time. Consumers MUST respect this:

1. **Per-manifest contract.**

   * For each `{parameter_hash, manifest_fingerprint, seed}`, the version of `s1_escalation_queue` in the dictionary/registry defines the applicable S1 contract.
   * Downstream tools (e.g. validators, analytics) MUST NOT assume that all manifests share the same S1 version.

2. **Consumer behaviour.**

   * Version-aware consumers SHOULD:

     * explicitly support all S1 versions they need, or
     * operate on the intersection of fields/behaviours common to those versions.

3. **No retroactive upgrades.**

   * Historic `s1_escalation_queue` datasets MUST NOT be rewritten to match new versions of the schema or spec.
   * If there is a need to “re-run” S1 under a new contract for the same underlying data, this MUST be treated as a new run with a new `manifest_fingerprint` (and likely a new `parameter_hash`), per Layer-1 governance.

---

Under these rules, 3A.S1 can evolve **safely and predictably**:

* Minor changes can add observability and diagnostics without breaking callers.
* Major changes are clearly marked via versioning and require explicit migration.
* Policy content changes are tracked via `parameter_hash` and policy versions, not hidden under a stable S1 contract.

Downstream states can trust that, for any given manifest, `s1_escalation_queue` has a clear, versioned contract that won’t silently shift under their feet.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix records the symbols and shorthand used in the 3A.S1 design. It has **no normative force**; it exists to keep notation consistent across 3A documents.

---

### 13.1 Scalars, hashes & identifiers

* **`parameter_hash`**
  Layer-1 hash over the governed parameter set 𝓟 (policies, priors, tunables). Fixed before any 3A state runs.

* **`manifest_fingerprint`** (often written **`F`**)
  Layer-1 hash over the resolved manifest for a run, including `parameter_hash` and all opened artefacts. Primary partition key for S0, S1 and later 3A states.

* **`seed`**
  Layer-1 global RNG seed (uint64). Embedded in S1 outputs but never consumed by S1 (RNG-free).

* **`merchant_id`**
  Layer-1 merchant identity (`id64` via `schemas.layer1.yaml`), inherited from 1A.

* **`legal_country_iso`**
  ISO-3166 alpha-2 code (e.g. `"GB"`, `"US"`) identifying the legal country of a merchant location.

---

### 13.2 Sets & derived quantities

* **`D` (domain of S1)**
  The set of all merchant×country pairs with at least one outlet in 1A for the current `{seed, manifest_fingerprint}`:

  [
  D = { (m,c) \mid \text{COUNT rows in 1A.outlet_catalogue with } merchant_id=m, legal_country_iso=c \ge 1 }
  ]

* **`D_1A` / `D_S1`**

  * `D_1A` — domain derived from 1A `outlet_catalogue`.
  * `D_S1` — domain derived from `s1_escalation_queue`.
    Acceptance criteria require `D_S1 = D_1A`.

* **`site_count(m,c)`**
  For merchant×country pair `(m,c)`:

  [
  site_count(m,c) = N(m,c) = \text{COUNT rows in 1A.outlet_catalogue with } (merchant_id=m, legal_country_iso=c).
  ]

  This is stored per row as `site_count`.

* **`Z(c)`**
  The set of IANA tzids present in legal country `c` according to sealed references (e.g. `tz_world_2025a`):

  [
  Z(c) = {\text{tzid} \mid tz_polygon(\text{tzid}) \cap country_polygon(c) \neq \emptyset}.
  ]

* **`zone_count_country(c)`**
  The cardinality of `Z(c)`:

  [
  zone_count_country(c) = |Z(c)|.
  ]

  Stored per row in S1 as `zone_count_country`.

---

### 13.3 Policy & decision notation

* **Mixture policy**
  The 3A configuration artefact (e.g. `zone_mixture_policy_3A`) that governs whether `(m,c)` is treated as monolithic or escalated.

* **`mixture_policy_id`**
  Logical ID of the mixture policy artefact (dataset/artefact ID in the catalogue); echoed in each S1 row.

* **`mixture_policy_version`**
  Version tag for the mixture policy (e.g. semver or digest-derived string), used for lineage and diagnostics.

* **`is_escalated`**
  Boolean flag in `s1_escalation_queue`:

  * `true`  ⇒ `(m,c)` is escalated and MUST be processed by the 3A zone allocation pipeline.
  * `false` ⇒ `(m,c)` is monolithic and MUST NOT be processed by that pipeline.

* **`decision_reason`**
  Short string code explaining why S1 chose monolithic vs escalated for a row; drawn from a closed vocabulary defined in the mixture policy schema (e.g. `"below_min_sites"`, `"single_zone_country"`, `"default_escalation"`, `"forced_escalation"`).

* **`eligible_for_escalation`** *(optional diagnostic)*
  Boolean sometimes used to differentiate “would have been escalated on structural grounds” from “was forced monolithic”.

---

### 13.4 Artefacts & datasets

* **`s0_gate_receipt_3A`**
  Fingerprint-scoped JSON artefact from 3A.S0. Attests upstream gate status (1A/1B/2A PASS), catalogue versions, and sealed policy/prior set for 3A.

* **`sealed_inputs_3A`**
  Fingerprint-scoped table from 3A.S0. Each row describes one artefact (dataset/bundle/policy/reference/log) that 3A is allowed to read for this `manifest_fingerprint`.

* **`outlet_catalogue` (1A egress)**
  Seed+fingerprint-scoped table defining per-site outlet stubs with `(merchant_id, legal_country_iso, site_order)` identity and 1A outlet counts. S1 uses it only for aggregation to `site_count(m,c)`.

* **`iso3166_canonical_2024`**
  Canonical country reference table used to validate `legal_country_iso`.

* **`tz_world_2025a`**
  Ingress time-zone world geometry; used to derive `Z(c)` and `zone_count_country(c)`.

* **`s1_escalation_queue`**
  S1’s output table, partitioned by `seed` and `fingerprint`, with one row per `(merchant_id, legal_country_iso)` indicating `site_count`, `zone_count_country`, `is_escalated`, `decision_reason`, and policy lineage.

---

### 13.5 Segments, states & shorthand

* **Segments / subsegments**

  * `1A` — Merchants → country-level outlet counts.
  * `1B` — Country-level outlets → coordinates.
  * `2A` — Civil time (site → IANA tzid, tzdb cache).
  * `2B` — Routing / alias engine (group / site routing).
  * `3A` — Zone allocation (this segment).

* **States in 3A (relevant here)**

  * `3A.S0` — Gate & sealed inputs for zone allocation.
  * `3A.S1` — Mixture policy & escalation queue (this document).
  * Later 3A states (e.g. S2–S4) handle priors, Dirichlet draws, integerisation, etc.

* **“Monolithic”**
  Informal term for `(m,c)` with `is_escalated=false`; 3A does not split that merchant×country into multiple zones in later states.

* **“Escalated”**
  Informal term for `(m,c)` with `is_escalated=true`; 3A will allocate that merchant×country’s outlet mass across zones in later states.

---

### 13.6 Error codes & status (S1)

* **`error_code`**
  Canonical S1 error code from §9, e.g.:

  * `E3A_S1_001_S0_GATE_MISSING_OR_INVALID`
  * `E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT`
  * `E3A_S1_012_IMMUTABILITY_VIOLATION`

* **`status`**
  S1 outcome in logs/run-report:

  * `"PASS"` — S1 met all acceptance criteria; `s1_escalation_queue` is authoritative.
  * `"FAIL"` — S1 terminated with one of the error codes above; its output (if any) must not be used.

* **`error_class`**
  Coarse classification of `error_code`, e.g. `"S0_GATE"`, `"POLICY"`, `"ZONE_STRUCTURE"`, `"DOMAIN_MISMATCH"`, `"OUTPUT_SCHEMA"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`.

---

These symbols and abbreviations are meant to align with those used for S0 and the upstream 1A/2A specs, so 3A documents read as a single, coherent family rather than as separate dialects.

---