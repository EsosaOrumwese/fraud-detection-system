# State 3A·S4 — Integer Zone Allocation (Counts per Merchant×Country×Zone)

## 1. Purpose & scope *(Binding)*

State **3A.S4 — Integer Zone Allocation (Counts per Merchant×Country×Zone)** is the **RNG-free integerisation state** of Segment 3A. It takes the **continuous zone shares** produced by 3A.S3 and the **total outlet counts** per merchant×country from 3A.S1, and turns them into **integer outlet counts per zone** in a way that is deterministic, reproducible, and aligned with the priors and policies established by S2.

Concretely, 3A.S4:

* **Transforms continuous shares + total counts into integer zone counts.**
  For every merchant×country pair `(merchant_id=m, legal_country_iso=c)` that S1 has marked as **escalated** (`is_escalated = true`), S4:

  * reads the **total outlet count**
    [
    N(m,c) = site_count(m,c)
    ]
    from `s1_escalation_queue` (which is itself derived from 1A’s `outlet_catalogue`),
  * reads the **zone share vector**
    [
    \Theta(m,c,z),\quad z \in Z(c)
    ]
    from `s3_zone_shares` for that `(m,c)` and its country’s zone set `Z(c)`,
  * and computes a set of **integer counts**
    [
    zone_site_count(m,c,z) \in \mathbb{N}
    ]
    such that:

    * `Σ_z zone_site_count(m,c,z) = N(m,c)` (exact count conservation), and
    * the integer counts are as close as possible to `N(m,c) * Θ(m,c,z)` under a deterministic rounding scheme.

  S4 is the only state in 3A that turns S3’s continuous shares into discrete zone-level counts for each merchant×country.

* **Implements a deterministic, RNG-free integerisation algorithm.**
  S4 MUST NOT consume any RNG. Given S1/S2/S3 outputs and the Layer-1 catalogue, it MUST:

  * compute continuous targets `T_z(m,c) = N(m,c) * Θ(m,c,z)` per zone,
  * apply a fixed, deterministic rounding scheme (e.g. floor + residual ranking) to obtain integer counts,
  * resolve ties using only deterministic criteria (e.g. residual magnitude, `tzid` ordering, stable tie-break indices),
  * guarantee that re-running S4 for the same inputs yields bit-identical outputs.

  Any aleatory variation in zone counts is attributable solely to S3’s Dirichlet draws; S4 adds no new randomness.

* **Respects priors and escalation decisions without re-deriving them.**
  S4:

  * treats S1’s `s1_escalation_queue` as the **sole authority** on:

    * which `(m,c)` pairs are escalated, and
    * what `site_count(m,c)` must be conserved,
  * treats S2’s `s2_country_zone_priors` as the **sole authority** on:

    * which zones `Z(c)` exist per country,
    * and any prior-level metadata (α sums, policy IDs/versions),
  * treats S3’s `s3_zone_shares` as the **sole authority** on:

    * the realised zone share vector `Θ(m,c,z)` for each escalated `(m,c)`.

  S4 MUST NOT:

  * re-classify `(m,c)` pairs as escalated/non-escalated,
  * re-interpret or adjust α-priors,
  * resample shares or perturb `Θ(m,c,z)`.

  Its authority is limited to turning `(N(m,c), Θ(m,c,·))` into integer counts.

* **Publishes a stable zone-count surface for downstream 3A / Layer-2 logic.**
  S4’s primary output is a seed+fingerprint-scoped dataset (e.g. `s4_zone_counts`) that, for each **escalated** `(m,c)` and each `z ∈ Z(c)`, records:

  * `zone_site_count(m,c,z)` — integer outlet count for that zone,
  * `zone_site_count_sum(m,c)` — per-pair integer sum (equal to `site_count(m,c)`),
  * lineage back to S3 (share draw) and S2 (priors and policy IDs/versions).

  This dataset becomes the **zone-level count authority** for any later state that needs to:

  * map individual outlets into zones,
  * construct zone-aware site assignment or routing behaviour, or
  * validate spatial/temporal behaviour against the integerised zone footprint.

* **Ensures count conservation and consistency with upstream shapes.**
  S4’s scope explicitly includes:

  * **Count conservation:** for each `(m,c)`, the sum of zone counts equals `site_count(m,c)`; there are no lost or created outlets.
  * **Domain consistency:** for escalated `(m,c)`, the set of zones with counts equals the `Z(c)` zone set implied by S2/S3; no missing or extra zones.
  * **Deterministic alignment with S3:** integer counts can be replayed from `(N(m,c), Θ(m,c,·))` via the specified rounding scheme, with no hidden adjustments.

Out of scope for 3A.S4:

* S4 does **not**:

  * create or adjust Dirichlet samples; it consumes `s3_zone_shares` as-is,
  * operate at the site level (e.g. mapping individual outlets to zones or sites),
  * produce final zone+site egress; that is the job of subsequent states if needed,
  * touch RNG or RNG logs; all stochastic behaviour is upstream in S3.

Within these boundaries, 3A.S4’s purpose is to provide a **clean, deterministic, count-conserving zone-count surface** for escalated merchant×country pairs, bridging the gap between continuous Dirichlet shares and discrete outlet distributions while remaining fully consistent with S1/S2/S3 and the Layer-1 authority chain.

---

## 2. Preconditions & gated inputs *(Binding)*

This section defines **what MUST already hold** before 3A.S4 can run, and which gate artefacts it must honour. Anything outside these constraints is **out of scope** for S4.

S4 is **run-scoped** over a triple `(parameter_hash, manifest_fingerprint, seed)` (plus `run_id` for tracking), and writes seed+fingerprint-scoped outputs. It is **RNG-free**.

---

### 2.1 Layer-1 and segment-level preconditions

Before 3A.S4 is invoked for a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, the orchestrator MUST ensure:

1. **Layer-1 identity is fixed.**

   * `parameter_hash` is a valid `hex64` and already identifies a closed governed parameter set 𝓟.
   * `manifest_fingerprint` is a valid `hex64` and was produced by the Layer-1 manifest logic using this `parameter_hash`.
   * `seed` is a valid `uint64` run seed for this Layer-1 run.
   * `run_id` is fixed for this execution and used consistently in run-report / logging (even though S4 consumes no RNG).

2. **3A.S0 has succeeded for this `manifest_fingerprint`.**

   * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}` exists and is schema-valid.
   * `sealed_inputs_3A@fingerprint={manifest_fingerprint}` exists and is schema-valid.
   * `s0_gate_receipt_3A.upstream_gates.segment_1A.status == "PASS"`,
     `segment_1B.status == "PASS"`,
     `segment_2A.status == "PASS"`.
   * If any of these conditions fail, S4 MUST treat this as a **hard precondition failure** and MUST NOT proceed.

3. **3A.S1 has produced a valid escalation queue for this `{seed, manifest_fingerprint}`.**

   * `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}` exists.
   * It validates against `schemas.3A.yaml#/plan/s1_escalation_queue`.
   * The S1 run-report row for this `{seed, manifest_fingerprint}` indicates `status="PASS"`.
   * If the dataset is missing, schema-invalid, or S1 is not PASS, S4 MUST NOT run.

4. **3A.S2 has produced priors for this `parameter_hash`.**

   * `s2_country_zone_priors@parameter_hash={parameter_hash}` exists and is schema-valid under `schemas.3A.yaml#/plan/s2_country_zone_priors`.
   * The S2 run-report row for this `parameter_hash` indicates `status="PASS"`.
   * Even though S4 does not need α-values for its core algorithm, priors MUST be present and coherent so that domain checks (zone sets per country) are well-posed.
   * Absence or invalidity of S2’s prior surface is a precondition failure.

5. **3A.S3 has produced a valid share surface for this run.**

   * `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}` exists and is schema-valid under `schemas.3A.yaml#/plan/s3_zone_shares`.
   * There is a corresponding S3 run-report row for this `(parameter_hash, manifest_fingerprint, seed, run_id)` (or, at minimum, for this `{seed, manifest_fingerprint}` under the relevant `parameter_hash`) with `status="PASS"`.
   * S4 MUST NOT attempt to “fix up” or re-derive shares; it only runs when S3 is green.

If any of the above are not true, S4 MUST treat the run as **invalid** and MUST NOT write or modify any S4 outputs.

---

### 2.2 Gated inputs from 3A.S0 (gate & whitelist)

S4 is RNG-free but still operates under S0’s gate and sealed-input whitelist for **external** artefacts.

1. **Gate descriptor: `s0_gate_receipt_3A`**
   S4 MUST read `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}` and:

   * validate it against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`,
   * confirm that upstream segment gates are `"PASS"` (as in §2.1),
   * confirm that key policy/prior artefacts (S1 mixture policy, S2 prior/floor policy, any zone universe reference / RNG policy if referenced by S4 for diagnostics) appear in `sealed_policy_set` with stable IDs/versions.

   If `s0_gate_receipt_3A` is missing, invalid, or indicates any upstream gate is not PASS, S4 MUST fail and MUST NOT proceed.

2. **Sealed input inventory: `sealed_inputs_3A`**
   For any **external reference** S4 reads directly (e.g. ISO country list, zone-universe reference) S4 MUST:

   * confirm there is at least one row in `sealed_inputs_3A` with matching `logical_id` and `path`, and
   * recompute SHA-256 over the artefact bytes and assert equality with `sha256_hex` recorded there.

S4 MUST NOT read any external artefact (reference or policy) that is not present in `sealed_inputs_3A` for this `manifest_fingerprint`.

Note: `s1_escalation_queue`, `s2_country_zone_priors`, and `s3_zone_shares` are **internal 3A datasets**, not external reference inputs; they are governed by the 3A catalogue and their own state contracts rather than S0’s sealed-input inventory.

---

### 2.3 Upstream 3A inputs S4 depends on

Within the 3A segment, S4 depends on three core internal surfaces:

1. **Escalation queue (`s1_escalation_queue`)**

   * Provides:

     * the full merchant×country domain `D` and escalated subset `D_esc`,
     * `site_count(m,c)` per `(merchant_id, legal_country_iso)`.
   * S4 MUST treat `site_count(m,c)` and `is_escalated` as authoritative:

     * it MUST integerise counts only for `(m,c) ∈ D_esc`,
     * and MUST conserve `site_count(m,c)` exactly.

2. **Zone priors (`s2_country_zone_priors`)**

   * Provides, per `country_iso = c`:

     * the zone set `Z(c)` (via rows `(country_iso, tzid)`),
     * `alpha_sum_country(c)` and prior lineage (prior pack / floor policy IDs).
   * S4 uses this **structurally**:

     * to know which zones `Z(c)` exist for each country,
     * to assert that S3/S4 domain is consistent with S2.
   * S4 MUST NOT change these priors; it uses them only for domain/lineage checks.

3. **Zone share surface (`s3_zone_shares`)**

   * Provides, for each escalated `(m,c)` and each `z ∈ Z(c)`:

     * `share_drawn(m,c,z)` and `share_sum_country(m,c)`,
     * `alpha_sum_country(c)` and prior lineage,
     * RNG lineage fields (module, substream, stream_id) for replay diagnostics.

   * S4 MUST:

     * treat `share_drawn(m,c,z)` as the **sole stochastic input** to integerisation for each `(m,c,z)`,
     * not attempt to re-sample or perturb these shares.

S4 MUST see these three surfaces in a mutually consistent state (domains, country codes, tzids). Inconsistencies (e.g. escalation pairs with no shares, shares for non-escalated pairs) are handled as S4 failures in later sections.

---

### 2.4 Invocation-level assumptions

For a specific S4 run:

* The orchestrator MUST supply or allow S4 to resolve:

  * `parameter_hash` (prior universe),
  * `manifest_fingerprint` (sealed inputs for this run),
  * `seed` (for partitioning lineage; no RNG consumption),
  * `run_id` (for run-report and correlation only).

* S4’s outputs are:

  * `s4_zone_counts` partitioned by `{seed, fingerprint}`, and
  * contributions to run-report and logs; **no RNG logs** are produced by S4.

If any of the preconditions in §2.1 or the gate/whitelist conditions in §2.2 are not met, S4 MUST treat the run as **FAIL** and MUST NOT write or modify `s4_zone_counts` for that `{seed, manifest_fingerprint}`.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes **exactly what 3A.S4 is allowed to read**, what each input is **authoritative for**, and where S4’s authority **stops**. Anything outside these inputs, or used beyond the roles defined here, is out of spec for S4.

---

### 3.1 Catalogue & S0-level inputs (shape & trust only)

S4 sits under the same Layer-1 catalogue and S0 gate as S0–S3. It MUST treat the following as **shape/metadata authorities**, not things it can redefine:

1. **Schema packs**

   * `schemas.layer1.yaml` — primitive types (`id64`, `iso2`, `hex64`, `uint64`, etc.) and any shared validation/receipt types.
   * `schemas.ingress.layer1.yaml` — shapes of ingress reference tables (ISO, tz-world, etc.).
   * `schemas.2A.yaml` — shapes of any zone-universe references reused.
   * `schemas.3A.yaml` — shapes for `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`, and `s4_zone_counts`.

   S4 MAY only use these to:

   * validate inputs/outputs against their `schema_ref`, and
   * define its own output shapes.

   S4 MUST NOT:

   * redefine primitive types,
   * change upstream schema semantics, or
   * rely on any schema not declared in the Layer-1 / 3A packs.

2. **Dataset dictionaries & artefact registries**

   * `dataset_dictionary.layer1.{2A,3A}.yaml`
   * `artefact_registry_{2A,3A}.yaml`

   These are the **only authorities** on:

   * dataset IDs,
   * path templates and partition keys,
   * `schema_ref`, format and role,
   * lineage (`produced_by`, `consumed_by`).

   S4 MUST resolve all dataset locations and schemas through these catalogues. Hard-coded paths or ad-hoc file discovery are out of spec.

3. **3A.S0 outputs (`s0_gate_receipt_3A`, `sealed_inputs_3A`)**

   S4 MUST treat:

   * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}` as the **only evidence** that upstream segments (1A, 1B, 2A) are PASS and that the 3A parameter set is sealed for this manifest;
   * `sealed_inputs_3A@fingerprint={manifest_fingerprint}` as the **only list** of external reference/policy artefacts S4 may read directly.

   S4 MUST NOT:

   * re-implement upstream gate logic, or
   * read external artefacts not present in `sealed_inputs_3A`.

---

### 3.2 3A internal inputs: S1, S2, S3 (business & stochastic authority)

Within Segment 3A, S4 depends primarily on three internal datasets.

#### 3.2.1 `s1_escalation_queue` — domain & total counts authority

Dataset:

* `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}`
* Schema: `schemas.3A.yaml#/plan/s1_escalation_queue`.

Authority:

* Defines the full merchant×country domain:

  [
  D = { (m,c) }
  ]

* Provides, for each `(m,c)`:

  * `site_count(m,c)` — the total number of outlets N for this merchant in this legal country;
  * `is_escalated(m,c)` — boolean, indicating whether 3A is allowed to split this pair across zones.

Binding rules:

* S4 MUST define its worklist as:

  [
  D_{\text{esc}} = { (m,c) \in D \mid is_escalated(m,c) = true }.
  ]

* S4 MUST:

  * integerise **only** for `(m,c) ∈ D_esc`;
  * conserve counts per pair:
    [
    \sum_{z} zone_site_count(m,c,z) = site_count(m,c).
    ]

* S4 MUST NOT:

  * change `is_escalated` for any pair;
  * modify or re-compute `site_count(m,c)`;
  * generate counts for `(m,c)` not present in `s1_escalation_queue`.

S1 is the **sole authority** on which pairs exist and how many outlets they have.

#### 3.2.2 `s2_country_zone_priors` — structural zone universe (read-only)

Dataset:

* `s2_country_zone_priors@parameter_hash={parameter_hash}`
* Schema: `schemas.3A.yaml#/plan/s2_country_zone_priors`.

Authority:

* For each `country_iso = c`, defines the **zone universe**:

  [
  Z(c) = {\ tzid \mid (country_iso=c, tzid) \text{ in } s2_country_zone_priors }.
  ]

* Provides prior lineage (`prior_pack_id`, `floor_policy_id`, etc.) and `alpha_sum_country(c)`.

S4’s allowed use:

* **Structurally**:

  * to confirm that the zones seen in `s3_zone_shares` for `country_iso=c` equal `Z(c)`,
  * to propagate prior/floor lineage into its own outputs (for traceability).

* It MUST NOT:

  * change or re-scale α values;
  * derive any new stochastic behaviour from priors.

S2 remains the **sole authority** on priors and the zone universe per country.

#### 3.2.3 `s3_zone_shares` — share vector authority

Dataset:

* `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}`
* Schema: `schemas.3A.yaml#/plan/s3_zone_shares`.

Authority:

* For each escalated `(m,c) ∈ D_esc` and each `z ∈ Z(c)`:

  * `share_drawn(m,c,z)` — Dirichlet sample component Θ(m,c,z),
  * `share_sum_country(m,c)` — sum of shares for this `(m,c)` (≈1),
  * copy of `alpha_sum_country(c)` and prior lineage fields.

S4 MUST:

* treat `share_drawn(m,c,z)` as the **only stochastic input** to the integerisation for each `(m,c,z)`,
* compute continuous targets:

  [
  T_z(m,c) = site_count(m,c) \cdot share_drawn(m,c,z)
  ]

  and derive integer counts deterministically from `T_z(m,c)`.

S4 MUST NOT:

* resample or perturb `share_drawn(m,c,z)`,
* normalise shares in a way that changes the underlying stochastic sample; it may rely on `share_sum_country(m,c)` for diagnostics but must treat Θ as the realised draw from S3.

S3 is the **sole authority** on zone shares; S4 is a pure deterministic transform on top.

---

### 3.3 External references S4 MAY read (structural checks only)

S4 can carry over some structural checks, but they are **not** required for integerisation logic and are always read via `sealed_inputs_3A`:

1. **Country reference** — `iso3166_canonical_2024`

   * S4 MAY use it to assert that any `legal_country_iso` seen in S1/S2/S3 is a valid ISO country.
   * S4 MUST NOT create or use country codes not present in this reference.

2. **Zone-universe reference** — `country_tz_universe` or `tz_world_2025a`

   * If present and sealed, S4 MAY use it to cross-check that S2’s `Z(c)` is consistent with the global zone universe.
   * S4 MUST NOT change `Z(c)` based on these references; they are for diagnostics/validation only.

These references are **read-only**; S4 has zero authority to alter them.

---

### 3.4 S4’s own authority vs upstream/downstream

S4’s **only new authority** in Segment 3A is:

* for each escalated merchant×country `(m,c)` and each zone `z ∈ Z(c)`, the integer count:

  [
  zone_site_count(m,c,z)
  ]

* and its sum per pair:

  [
  zone_site_count_sum(m,c) = \sum_{z \in Z(c)} zone_site_count(m,c,z)
  ]

Within this scope:

* S4 **owns**:

  * the deterministic mapping
    [
    (site_count(m,c), \Theta(m,c,\cdot)) \mapsto { zone_site_count(m,c,z) }
    ]
    under the specified integerisation scheme (floors + residual ranking, etc.), and
  * the `s4_zone_counts` dataset that records those counts and their lineage.

* S4 explicitly does **not** own:

  * which pairs `(m,c)` are escalated or their total counts (`site_count`) — S1’s authority,
  * which zones exist per country or what priors they have — S2’s authority,
  * the stochastic shares Θ(m,c,·) — S3’s authority,
  * any RNG behaviour — Layer-1 RNG and S3; S4 is RNG-free.

Downstream:

* Any later 3A state that needs zone-level outlet counts MUST treat `s4_zone_counts` as the **sole authority** for those counts and MUST NOT re-integerise from shares independently.

---

### 3.5 Explicit “MUST NOT” list for S4

To keep boundaries sharp, S4 is explicitly forbidden from:

* **Re-classifying sources**

  * MUST NOT change `is_escalated` for any pair; MUST NOT produce zone counts for non-escalated `(m,c)`.

* **Changing totals or priors**

  * MUST NOT alter `site_count(m,c)` from S1, or `alpha_sum_country(c)` / `Z(c)` from S2.

* **Resampling or perturbing shares**

  * MUST NOT resample, jitter, or otherwise perturb `share_drawn(m,c,z)` from S3;
  * MUST NOT introduce any RNG.

* **Reading merchant/site/arrival data outside S1/S3 surfaces**

  * No direct reads of 1A `outlet_catalogue`, 1B `site_locations`, 2A `site_timezones`, or any arrival/routing logs.

* **Reading unsealed external artefacts**

  * MUST NOT read any reference/policy artefacts that are not present in `sealed_inputs_3A` for this `manifest_fingerprint`.

Within these boundaries, S4’s inputs and authority are tightly scoped: it trusts S1/S2/S3 for domain, priors and shares, and contributes a purely deterministic, count-conserving mapping from those inputs to zone-level integer counts.

---

## 4. Outputs (datasets) & identity *(Binding)*

3A.S4 produces **one** new dataset. It is the **only** authority on **integer outlet counts per merchant×country×zone** for Segment 3A. S4 emits no RNG logs and no validation bundles.

---

### 4.1 Overview of S4 outputs

For each run `{seed, manifest_fingerprint}` under a given `parameter_hash`, 3A.S4 MUST produce at most one instance of:

1. **`s4_zone_counts`**

   * A seed+fingerprint-scoped table that, for every **escalated** merchant×country pair `(merchant_id, legal_country_iso)` and every zone `tzid ∈ Z(legal_country_iso)`, records:

     * the **integer outlet count** assigned to that zone, and
     * per-pair summary and lineage fields.
   * It is a **deterministic integerisation** of S3’s `s3_zone_shares` under S1’s `site_count`.

No other persistent outputs are in scope for S4 in this contract version.

---

### 4.2 Domain & identity of `s4_zone_counts`

#### 4.2.1 Domain

For a given `{seed, manifest_fingerprint}`:

* From S1, define:
  [
  D = {(m,c)} = {(merchant_id,legal_country_iso)}
  ]
  and
  [
  D_{\text{esc}} = {(m,c) \in D \mid is_escalated(m,c) = true}.
  ]

* From S2/S3, for each country `c`, define:
  [
  Z(c) = { tzid \mid (country_iso=c, tzid) \in s2_country_zone_priors }
  ]

Then the **intended domain** for `s4_zone_counts` is:

[
D_{\text{S4}} = {(m,c,z) \mid (m,c) \in D_{\text{esc}},\ z \in Z(c)}.
]

Binding requirements:

* For each `(m,c) ∈ D_esc` and each `z ∈ Z(c)`, S4 MUST produce **exactly one** row with `(merchant_id=m, legal_country_iso=c, tzid=z)`.
* There MUST be **no rows** for:

  * any `(m,c)` with `is_escalated = false`, or
  * any `tzid` not in `Z(c)` for that `legal_country_iso`.

#### 4.2.2 Logical primary key

Within each `{seed, manifest_fingerprint}` partition:

* Logical primary key:
  [
  (\text{merchant_id}, \text{legal_country_iso}, \text{tzid})
  ]

There MUST NOT be duplicate rows for the same triple.

---

### 4.3 Partitioning & path

` s4_zone_counts` is a **run-scoped** dataset, aligned with S1/S3.

**Partition keys**

* Partition key set MUST be exactly:

  ```text
  ["seed", "fingerprint"]
  ```

**Conceptual path template** (finalised in dictionary):

```text
data/layer1/3A/s4_zone_counts/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...
```

Binding rules:

* For each partition, the path MUST include:

  * `seed=<uint64>`,
  * `fingerprint=<hex64>`.
* There MUST be at most one `s4_zone_counts` partition per `{seed, manifest_fingerprint}`.

**Path↔embed equality**

Every row in a given partition MUST satisfy:

* `row.seed == {seed_token}`,
* `row.fingerprint == {fingerprint_token}`.

Any mismatch MUST be treated as a validation error by S4 and downstream validators.

---

### 4.4 Required columns & semantics

Each row in `s4_zone_counts` MUST contain at least:

#### 4.4.1 Lineage / partitions

* `seed`

  * Type: `uint64` (`schemas.layer1.yaml#/$defs/uint64`).
  * Same for all rows in the partition.

* `fingerprint`

  * Type: `hex64` (`schemas.layer1.yaml#/$defs/hex64`).
  * Same for all rows in the partition and equal to the run’s `manifest_fingerprint` token.

#### 4.4.2 Identity

* `merchant_id`

  * Type: `id64`.
  * Matches S1/S3/1A.

* `legal_country_iso`

  * Type: `iso2`.
  * Matches S1/S2/S3; MUST be a valid ISO-3166 code.

* `tzid`

  * Type: `iana_tzid`.
  * MUST belong to `Z(legal_country_iso)` as defined by `s2_country_zone_priors`.

#### 4.4.3 Integer counts

For each row `(m,c,z)`:

* `zone_site_count`

  * Type: integer (`type: "integer"`).
  * MUST satisfy `zone_site_count(m,c,z) ≥ 0`.
  * Represents the number of outlets of merchant `m` in country `c` allocated to zone `z`.

* `zone_site_count_sum`

  * Type: integer (`type: "integer"`, `minimum: 0`).
  * Same for all zone rows of a given `(m,c)`.
  * MUST satisfy:
    [
    zone_site_count_sum(m,c) = \sum_{z \in Z(c)} zone_site_count(m,c,z) = site_count(m,c) \text{ from S1}.
    ]

Optional but recommended (for diagnostics):

* `fractional_target`

  * Type: `number`.
  * The continuous target `T_z(m,c) = site_count(m,c) * share_drawn(m,c,z)` used by the integerisation algorithm.

* `residual_rank`

  * Type: `integer`, `minimum: 1`.
  * Rank of this zone’s residual in the rounding scheme (e.g. if S4 uses floor+residual sort).

These optional fields MUST be deterministic functions of S1/S3 inputs and do not change semantics of required fields.

#### 4.4.4 Lineage from S2/S3

To preserve traceability:

* `prior_pack_id`, `prior_pack_version`

  * Type: `string`.
  * Copied from S2 (`s2_country_zone_priors`).
  * MUST be constant across all rows in this `{seed,fingerprint}` partition.

* `floor_policy_id`, `floor_policy_version`

  * Type: `string`.
  * Copied from S2 floor policy lineage; constant across the partition.

* `share_sum_country`

  * Type: `number`, `exclusiveMinimum: 0.0`.
  * Copy of `share_sum_country(m,c)` from S3 for this `(m,c)`; repeated across zones for that pair.
  * Used for diagnostics to confirm that integerisation was applied to shares that sum ≈ 1.

* (Optional) `alpha_sum_country`

  * Type: `number`, `exclusiveMinimum: 0.0`.
  * Copy of `alpha_sum_country(c)` from S2; repeated across zones. Useful to join to the prior surface.

All lineage fields MUST be deterministic and MUST match S2/S3 values for this `parameter_hash`.

---

### 4.5 Writer-sort & immutability

Within each `{seed, manifest_fingerprint}` partition, S4 MUST write rows in a deterministic order, e.g.:

1. `merchant_id` ascending,
2. `legal_country_iso` ascending,
3. `tzid` ascending.

Ordering has **no semantic meaning** beyond reproducibility. All semantics come from keys and fields; file order is only for:

* ensuring re-runs produce identical outputs.

Once `s4_zone_counts` is written for a given `{seed, manifest_fingerprint}`:

* It MUST be treated as a **snapshot**.
* If S4 is re-run for the same inputs:

  * and the newly computed rows (normalised & sorted) are **identical** to the existing dataset → S4 MAY skip writing or write identical bytes;
  * if they **differ** → S4 MUST NOT overwrite and MUST raise an immutability violation.

---

### 4.6 Consumers & authority chain

` s4_zone_counts` is an **internal 3A planning surface**, but it is authoritative for zone-level counts.

**Required consumers:**

* Any later 3A state that needs **zone-level integer counts** for merchants (e.g. a state that places zone-level counts onto individual sites, or a state that validates spatial distributions) MUST:

  * use `s4_zone_counts` as the source of `(m,c,z) → count`,
  * not re-integerise from shares independently.

* The 3A validation state MUST:

  * use `s4_zone_counts` to check:

    * domain alignment with S1/S2/S3,
    * per-pair count conservation,
    * deterministic replay of integerisation from `(site_count, share_drawn)`.

**Optional consumers:**

* Cross-segment analytics/diagnostics MAY use `s4_zone_counts` for aggregate insights (e.g. how outlet mass is distributed across zones per country).

**Non-outputs (explicit exclusions):**

S4 does **not** introduce:

* any site-level mapping of counts to specific outlets (that is a later mapping/routing concern),
* any new priors or share surfaces,
* any validation bundles or `_passed.flag` artefacts (segment-level PASS remains responsibility of a later validation state).

Within these constraints, `s4_zone_counts` is the **only dataset** produced by 3A.S4 and the **sole authority** on integer outlet counts per `(merchant_id, legal_country_iso, tzid)` for escalated pairs, consistent with upstream S1/S2/S3 outputs.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes **where S4’s output lives** in the authority chain:

* which JSON-Schema anchor defines its row shape,
* how it is exposed via the Layer-1 dataset dictionary, and
* how it is registered in the 3A artefact registry.

Everything here is **normative** for `s4_zone_counts`.

---

### 5.1 Segment schema pack for S4

S4 uses the existing 3A schema pack:

* **Schema pack ID:** `schemas.3A.yaml`
* **Role:** shape authority for all Segment-3A datasets (S0–S7).

`schemas.3A.yaml` MUST:

1. Reuse Layer-1 primitives via `$ref: "schemas.layer1.yaml#/$defs/…"`, including:

   * `uint64`, `hex64`, `id64`, `iso2`, `iana_tzid`, standard numeric types, etc.
2. Define a dedicated anchor for S4’s output:

   * `#/plan/s4_zone_counts`

No other schema pack may define the shape of `s4_zone_counts`.

---

### 5.2 Schema anchor: `schemas.3A.yaml#/plan/s4_zone_counts`

The anchor `#/plan/s4_zone_counts` defines the **row shape** for the zone-level integer counts.

At minimum, the schema MUST enforce:

* **Type:** `object`

* **Required properties:**

  * `seed`

    * `$ref: "schemas.layer1.yaml#/$defs/uint64"`

  * `fingerprint`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `merchant_id`

    * `$ref: "schemas.layer1.yaml#/$defs/id64"`

  * `legal_country_iso`

    * `$ref: "schemas.layer1.yaml#/$defs/iso2"`

  * `tzid`

    * `$ref: "schemas.layer1.yaml#/$defs/iana_tzid"`

  * `zone_site_count`

    * `type: "integer"`
    * `minimum: 0`

  * `zone_site_count_sum`

    * `type: "integer"`
    * `minimum: 0`

  * `share_sum_country`

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

* **Optional properties (diagnostic / convenience):**

  * `fractional_target`

    * `type: "number"`
    * (represents the continuous target `N(m,c) * share_drawn(m,c,z)` if S4 chooses to expose it).

  * `residual_rank`

    * `type: "integer"`
    * `minimum: 1`
    * (deterministic rank of this zone when distributing residual counts, if S4 uses a floor+residual scheme).

  * `alpha_sum_country`

    * `type: "number"`
    * `exclusiveMinimum: 0.0`
    * (copy of S2’s `alpha_sum_country(c)` if included).

  * `notes`

    * `type: "string"` (free-text diagnostics; optional).

* **Additional properties:**

  * At the top level, the schema MUST set:

    ```yaml
    additionalProperties: false
    ```

    to prevent accidental shape drift (future extensions MUST go through a versioned schema change per §12).

This anchor MUST be used as the `schema_ref` for `s4_zone_counts` in the dataset dictionary.

---

### 5.3 Dataset dictionary entry: `dataset_dictionary.layer1.3A.yaml`

The Layer-1 dataset dictionary for subsegment 3A MUST define S4’s dataset as follows (conceptual YAML):

```yaml
datasets:
  - id: s4_zone_counts
    owner_subsegment: 3A
    description: Integer outlet counts per merchant×country×zone after floor/bump.
    version: '{seed}.{manifest_fingerprint}'
    format: parquet
    path: data/layer1/3A/s4_zone_counts/seed={seed}/manifest_fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    ordering: [merchant_id, legal_country_iso, tzid]
    schema_ref: schemas.3A.yaml#/plan/s4_zone_counts
    lineage:
      produced_by: 3A.S4
      consumed_by: [3A.S5]
    final_in_layer: false
    pii: false
    licence: Proprietary-Internal
```

Binding points:

* `id` MUST be `s4_zone_counts` under `owner_subsegment: 3A`.
* `path` MUST include `seed={seed}` and `fingerprint={manifest_fingerprint}` and MUST NOT introduce additional partition tokens.
* `partitioning` MUST be exactly `[seed, fingerprint]`.
* `schema_ref` MUST be `schemas.3A.yaml#/plan/s4_zone_counts`.
* `ordering` expresses the writer-sort key (merchant, then country, then tzid); consumers MUST NOT infer extra semantics from file order.

Any alternative dataset ID, path template, partitioning, or schema_ref for this surface is out of spec.

---

### 5.4 Artefact registry entry: `artefact_registry_3A.yaml`

For each `{seed, manifest_fingerprint}`, the 3A artefact registry records `s4_zone_counts` as:

```yaml
- manifest_key: mlr.3A.s4.zone_counts
  name: "Segment 3A S4 zone-level outlet counts"
  subsegment: "3A"
  type: "dataset"
  category: "plan"
  path: data/layer1/3A/s4_zone_counts/seed={seed}/manifest_fingerprint={manifest_fingerprint}/
  schema: schemas.3A.yaml#/plan/s4_zone_counts
  semver: '1.0.0'
  version: '{seed}.{manifest_fingerprint}'
  digest: '<sha256_hex>'
  dependencies:
    - mlr.3A.s3.zone_shares
    - mlr.3A.zone_floor_policy
  source: internal
  owner: {owner_team: "mlr-3a-core"}
  cross_layer: true
```

Binding requirements:

* `manifest_key` MUST be `mlr.3A.s4.zone_counts`.
* `version` MUST encode `{seed}.{manifest_fingerprint}`; contract versioning remains in `semver`.
* `path`/`schema` MUST match the dataset dictionary entry.
* Dependencies MUST include, at minimum, the S3 zone-share surface (providing fractional targets) and the zone-floor policy artefact. If S4 later relies on additional artefacts, both the registry entry and this spec MUST be updated accordingly.

The registry entry MUST remain consistent with the dictionary entry and the actual dataset (path↔embed equality, digest correctness); later validation relies on this consistency.

---

### 5.5 No additional S4 datasets in this contract version

Under this version of the contract:

* 3A.S4 MUST NOT register or emit any datasets beyond `s4_zone_counts`.

If, in future, S4 needs extra diagnostics (e.g. a summary of zero-allocated zones by country), those MUST be introduced via:

1. New schema anchors in `schemas.3A.yaml` (e.g. `#/plan/s4_zone_counts_summary`),
2. New dictionary entries in `dataset_dictionary.layer1.3A.yaml` with their own IDs, paths, and partitioning, and
3. New artefact registry entries with appropriate `manifest_key`, `path`, `schema`, and dependencies.

Until such changes are made under §12 (change control & compatibility), the shapes and catalogue links above are the **only** valid ones for 3A.S4’s output.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section defines the **exact behaviour** of 3A.S4. The algorithm is:

* **Purely deterministic** (no RNG, no wall-clock),
* **Run-scoped** over `{seed, manifest_fingerprint}` (under a fixed `parameter_hash`), and
* **Idempotent** (same inputs ⇒ byte-identical `s4_zone_counts`).

Given:

* S1’s `s1_escalation_queue` (domain + `site_count` + `is_escalated`),
* S2’s `s2_country_zone_priors` (zone universe per country),
* S3’s `s3_zone_shares` (Dirichlet share vectors),

S4 MUST produce integer counts that obey domain, conservation and consistency rules, without consuming any RNG.

---

### 6.1 Phase overview

For a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, S4 executes in five phases:

1. **Resolve S0/S1/S2/S3 & catalogue.**
2. **Build the escalated worklist and per-country zone sets.**
3. **For each escalated pair `(m,c)`, compute continuous targets and base counts.**
4. **Apply a deterministic residual-based rounding scheme to get final integers.**
5. **Materialise `s4_zone_counts` and enforce idempotence.**

---

### 6.2 Phase 1 — Resolve S0/S1/S2/S3 & catalogue

**Step 1 – Fix run identity**

S4 is invoked with:

* `parameter_hash` (hex64),
* `manifest_fingerprint` (hex64),
* `seed` (uint64),
* `run_id` (string / u128-encoded).

S4 MUST:

* validate these values (correct formats),
* treat them as immutable for this run.

**Step 2 – Load S0 artefacts**

Using 3A’s dictionary/registry, S4 resolves and reads:

* `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`,
* `sealed_inputs_3A@fingerprint={manifest_fingerprint}`.

S4 MUST:

* validate both against their schemas (`#/validation/s0_gate_receipt_3A`, `#/validation/sealed_inputs_3A`),
* confirm upstream segment gates (1A/1B/2A) are `"PASS"` as required in §2.

Failure ⇒ S4 MUST abort; no outputs may be written.

**Step 3 – Load S1, S2, S3 datasets**

Using dictionary/registry, S4 resolves:

* `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}`
  (`schema_ref: schemas.3A.yaml#/plan/s1_escalation_queue`),
* `s2_country_zone_priors@parameter_hash={parameter_hash}`
  (`schema_ref: schemas.3A.yaml#/plan/s2_country_zone_priors`),
* `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}`
  (`schema_ref: schemas.3A.yaml#/plan/s3_zone_shares`).

S4 MUST:

* validate each dataset against its schema before using it,
* treat schema invalidity as a precondition failure.

**Step 4 – Load catalogue artefacts**

S4 MUST load and validate (via Layer-1 catalogue schemas):

* `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml`,
* `dataset_dictionary.layer1.{2A,3A}.yaml`,
* `artefact_registry_{2A,3A}.yaml`.

Missing/malformed catalogue artefacts required by S4 MUST cause a failure.

---

### 6.3 Phase 2 — Build escalated worklist & zone universe

**Step 5 – Derive domain from S1**

From `s1_escalation_queue` for this `{seed, fingerprint}`, S4 MUST derive:

* `D = { (m,c) }` — all `(merchant_id, legal_country_iso)` pairs in S1,
* `D_esc = { (m,c) ∈ D | is_escalated(m,c) = true }`.

For each `(m,c) ∈ D_esc`, S4 MUST read:

* `site_count(m,c)` — total outlet count for the pair; MUST have `site_count ≥ 1`.

S4 MUST use a deterministic ordering of `D_esc` for its per-pair processing, e.g.:

1. `merchant_id` ascending,
2. `legal_country_iso` ascending.

Physical row order in S1 MUST NOT be used as a source of non-determinism.

**Step 6 – Derive zone universe per country from S2**

From `s2_country_zone_priors@parameter_hash`, S4 MUST derive, for each `country_iso = c` present in S3/S1:

* `Z(c) = { tzid | (country_iso=c, tzid) exists in s2_country_zone_priors }`.

For each `c`:

* S4 MUST ensure `Z(c)` is non-empty for any `c` appearing in `D_esc`; if not, this is a prior-surface inconsistency and MUST be treated as a failure.

S4 MUST define a deterministic **ordered** zone list per country:

[
Z_{\text{ord}}(c) = [z_1, z_2, \dots, z_{K(c)}]
]

obtained by sorting `Z(c)` lexicographically by `tzid`. This order MUST be used consistently whenever S4 needs to rank or iterate zones for that country.

---

### 6.4 Phase 3 — Join S3 shares and compute continuous targets

**Step 7 – Check S3 coverage and align domains**

From `s3_zone_shares@{seed,fingerprint}`, S4 MUST:

* project onto `(merchant_id, legal_country_iso)` to get `D_S3`,
* assert `D_S3 == D_esc`:

  * every escalated `(m,c)` appears in S3,
  * no non-escalated `(m,c)` appears in S3.

For each `(m,c) ∈ D_esc`:

* collect all S3 rows where `merchant_id=m` and `legal_country_iso=c`; denote this set `rows_S3(m,c)`.

S4 MUST verify:

* `rows_S3(m,c)` contains exactly `K(c)` rows, one for each `z ∈ Z(c)`,
* there are no extra tzids outside `Z(c)`.

Any mismatch MUST be treated as a domain consistency failure (handled in acceptance/error sections).

**Step 8 – Read shares and sanity-check sums**

For each `(m,c) ∈ D_esc`, S4 MUST read from `rows_S3(m,c)`:

* `share_drawn(m,c,z)` for each `z ∈ Z(c)`,
* a single common `share_sum_country(m,c)` value.

S4 MUST:

* assert that all rows for `(m,c)` share the same `share_sum_country`;
* check that `share_sum_country(m,c)` is within a fixed tolerance of 1 (e.g. `[1 - ε_share, 1 + ε_share]` for some small ε_share > 0 defined in the 3A validation spec).

If `share_sum_country(m,c)` is outside tolerance, S4 MUST treat this as a S3 inconsistency and fail; it MUST NOT renormalise shares to “fix” them.

**Step 9 – Compute continuous targets per zone**

For each `(m,c) ∈ D_esc` and each `z ∈ Z(c)`:

* Let `N = site_count(m,c)` (integer ≥ 1).
* Let `p_z = share_drawn(m,c,z)`.

S4 MUST compute:

[
T_z(m,c) = N \cdot p_z
]

in binary64 (double precision), in a fixed order over `Z_{\text{ord}}(c)`.

S4 MAY optionally record `T_z(m,c)` in `fractional_target` for diagnostics; even if not stored, it MUST be internally well-defined and reproducible.

---

### 6.5 Phase 4 — Deterministic integerisation per `(m,c)`

For each escalated pair `(m,c) ∈ D_esc`, S4 MUST derive integer counts from `T_z(m,c)`.

The algorithm MUST be **RNG-free** and **fully deterministic** given `(N, {T_z})`.

A canonical scheme (aligned with 1A’s S7) is:

#### 6.5.1 Base counts via floor

For fixed `(m,c)`:

* For each `z ∈ Z_{\text{ord}}(c)`:

  * Compute base count:
    [
    b_z(m,c) = \lfloor T_z(m,c) \rfloor
    ]
    as an integer.

* Compute:

  * `base_sum(m,c) = Σ_{z} b_z(m,c)`
  * Residual capacity:
    [
    R(m,c) = N - base_sum(m,c).
    ]

S4 MUST:

* assert `base_sum(m,c) ≤ N`;
* if `base_sum(m,c) > N` (which should not occur if `share_sum_country` is close to 1), treat this as a numeric failure; S4 MUST NOT attempt ad-hoc repairs.

If `R(m,c) == 0`, S4 MAY skip residual redistribution (all counts are already integers summing to N) and set `zone_site_count(m,c,z) = b_z(m,c)`.

If `R(m,c) > 0`, proceed to residual ranking.

#### 6.5.2 Residuals & ranking

For each `z ∈ Z_{\text{ord}}(c)`:

* Compute residual:

  [
  r_z(m,c) = T_z(m,c) - b_z(m,c)
  ]

  in binary64. By construction, `r_z(m,c) ∈ [0, 1)`.

S4 MUST then define a **deterministic ordering** of zones for this `(m,c)` to allocate the remaining `R(m,c)` units:

* sort zones by the tuple:

  1. `r_z(m,c)` descending (largest residual first),
  2. `tzid` ascending (ASCII lexicographic),
  3. any stable tie-breaker if needed (e.g. a deterministic index position).

Let this order be:

[
z^{(1)}, z^{(2)}, \dots, z^{(K(c))}
]

where ties are fully resolved by the deterministic criteria above.

#### 6.5.3 Distribute residual units

S4 MUST allocate the remaining `R(m,c)` units as +1 increments to the top residual zones:

* For each zone `z`:

  [
  zone_site_count(m,c,z) =
  \begin{cases}
  b_z(m,c) + 1 & \text{if } z \in {z^{(1)}, \dots, z^{(R(m,c))}} \
  b_z(m,c)     & \text{otherwise.}
  \end{cases}
  ]

This guarantees:

[
\sum_{z \in Z(c)} zone_site_count(m,c,z) = base_sum(m,c) + R(m,c) = N = site_count(m,c).
]

S4 MUST:

* ensure `zone_site_count(m,c,z) ≥ 0` for all `z`,
* optionally compute a deterministic `residual_rank(m,c,z)` as the rank of `z` in the residual ordering, storing it in `residual_rank` if present.

If `R(m,c) < 0` (which should not occur under normal S3 behaviour), this MUST be treated as an error; S4 MUST NOT distribute “negative” residuals or silently clamp counts.

Any additional integerisation constraints (e.g. zone floors for minimum outlet presence) MUST be handled in later revisions; in this contract, S4’s integerisation is purely floor+residual, anchored on S2/S3’s priors/shares.

---

### 6.6 Phase 5 — Materialise `s4_zone_counts`

**Step 10 – Construct row set for `s4_zone_counts`**

After integerisation for all `(m,c) ∈ D_esc`, S4 has a conceptual row set:

* For every `(m,c,z) ∈ D_S4`:

  * `seed`, `manifest_fingerprint`,
  * `merchant_id = m`,
  * `legal_country_iso = c`,
  * `tzid = z`,
  * `zone_site_count(m,c,z)` from §6.5.3,
  * `zone_site_count_sum(m,c) = N` (computed once per `(m,c)` and repeated per zone),
  * `share_sum_country(m,c)` copied from S3,
  * `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version` copied from S2 (and consistent with S3),
  * optionally `fractional_target = T_z(m,c)`, `residual_rank(m,c,z)`, `alpha_sum_country(c)`.

S4 MUST ensure:

* There is exactly one row per `(m,c,z)` in `D_S4`.
* No rows exist for `(m,c)` not in `D_esc` or `z` not in `Z(c)`.

**Step 11 – Sort & validate rows**

Using the dictionary entry for `s4_zone_counts`:

* Determine the target path:

  ```text
  data/layer1/3A/s4_zone_counts/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...
  ```

* Sort rows by the declared writer-sort key:

  1. `merchant_id` ascending,
  2. `legal_country_iso` ascending,
  3. `tzid` ascending.

* Validate all rows against `schemas.3A.yaml#/plan/s4_zone_counts`.

Any validation error (including path↔embed mismatch) MUST cause S4 to fail before publishing output.

**Step 12 – Idempotent write**

If no dataset exists yet for this `{seed, manifest_fingerprint}`:

* S4 writes `s4_zone_counts` with partitioning `["seed","fingerprint"]` and the sorted row set.

If a dataset already exists:

* S4 MUST read it, normalise to the same schema and sort order, and compare row-for-row and field-for-field with the newly computed row set.
* If they are **identical**, S4 MAY skip writing, or re-write identical bytes; either way, the visible content MUST remain unchanged.
* If they **differ**, S4 MUST NOT overwrite and MUST treat this as an immutability violation.

---

### 6.7 RNG & side-effect discipline

Throughout all phases, S4 MUST:

* **not consume any RNG**

  * no Philox calls, no `u01`, no RNG events.

* **not read wall-clock time**

  * any timestamps in logs/layer1/3A/run-report are provided by the orchestrator, NOT used in S4’s data-plane logic.

* **not mutate upstream artefacts**

  * S4 MUST NOT modify S1/S2/S3 datasets or S0 artefacts.
  * The only data-plane artefact S4 is allowed to write is `s4_zone_counts` for the current `{seed, manifest_fingerprint}`.

* **fail atomically**

  * On any failure in Steps 1–12, S4 MUST NOT leave a partially written `s4_zone_counts` visible.
  * Writes MUST be atomic (or rolled back).

Under this algorithm, for a fixed `(parameter_hash, manifest_fingerprint, seed, run_id)` and catalogue state, S4 deterministically and reproducibly turns:

* S1’s total counts and escalated domain, and
* S3’s zone share vectors (grounded in S2’s priors),

into a single **integer zone-count surface** that conserves counts, respects zone universes, and is fully aligned with the rest of the Layer-1 / 3A authority chain.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how `3A.S4`’s output:

* is **identified** (keys),
* is **partitioned** (path tokens),
* what its **ordering** means (and doesn’t), and
* what is allowed in terms of **merge/overwrite** behaviour.

Everything here applies to the single S4 dataset: **`s4_zone_counts`**.

---

### 7.1 Logical identity: what a row *is*

For `s4_zone_counts`, the identity of a row lives at two levels:

* **Run context** (shared across many rows in the partition):

  * `seed` — Layer-1 run seed.
  * `manifest_fingerprint` — Layer-1 manifest hash.

* **Business identity** (within a run):

  * `merchant_id` — merchant (`id64`).
  * `legal_country_iso` — ISO-3166 country code.
  * `tzid` — IANA time zone identifier.

**Domain recap**

For a given `{seed, manifest_fingerprint}`:

* From S1:
  [
  D = {(m,c)},\quad D_{\text{esc}} = {(m,c) \in D \mid is_escalated(m,c) = true}.
  ]

* From S2/S3:

  * For each `c`,
    [
    Z(c) = { tzid \mid (country_iso=c, tzid)\ \text{in S2 priors} }.
    ]

S4’s **intended domain** is:

[
D_{\text{S4}} = { (m,c,z) \mid (m,c) \in D_{\text{esc}},\ z \in Z(c) }.
]

Binding requirements:

* For each `(m,c) ∈ D_esc` and each `z ∈ Z(c)`, there MUST be **exactly one** row in `s4_zone_counts` with:

  * `merchant_id = m`,
  * `legal_country_iso = c`,
  * `tzid = z`.

* There MUST be **no rows** for:

  * any `(m,c)` where `is_escalated = false` or `(m,c) ∉ D`, or
  * any `tzid` not in `Z(c)` for that `legal_country_iso`.

**Logical primary key**

Within each `{seed, manifest_fingerprint}` partition:

[
PK = (\text{merchant_id},\ \text{legal_country_iso},\ \text{tzid})
]

There MUST NOT be duplicate rows for the same triple.

---

### 7.2 Partitioning & path tokens

` s4_zone_counts` is a **run-scoped** dataset, aligned with S1/S3.

**Partition keys**

* Partition key set MUST be exactly:

```text
["seed", "fingerprint"]
```

No additional partition keys (e.g. `parameter_hash`, `run_id`) are allowed for this dataset.

**Path template (conceptual)**

From the dictionary:

```text
data/layer1/3A/s4_zone_counts/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...
```

Binding rules:

* For each partition, the path MUST include:

  * `seed=<uint64>`,
  * `fingerprint=<hex64>`.

* There MUST be at most one `s4_zone_counts` partition for any `{seed, manifest_fingerprint}` pair.

**Path↔embed equality**

Every row in a given `{seed, fingerprint}` partition MUST satisfy:

* `row.seed == {seed_token}`,
* `row.fingerprint == {fingerprint_token}`.

Any mismatch between embedded values and path tokens is a schema/validation error.

---

### 7.3 Alignment with S1, S2, S3 domains

Within each `{seed, manifest_fingerprint}` partition:

1. **Alignment with S1 (merchant×country domain & totals)**

   * Let `D` and `D_esc` be derived from `s1_escalation_queue`.
   * Projection of `s4_zone_counts` onto `(merchant_id, legal_country_iso)` MUST equal `D_esc`:
     [
     {(m,c)\ \text{seen in S4}} = D_{\text{esc}}.
     ]
   * For each `(m,c)`, `zone_site_count_sum(m,c)` MUST equal `site_count(m,c)` from S1.

2. **Alignment with S2/S3 (zone universe per country)**

   * For each escalated country `c`:

     * `Z(c)` = `{tzid}` from `s2_country_zone_priors`.
   * For each `(m,c)`:

     * the set of `tzid` values in `s4_zone_counts` with `(m,c)` MUST equal `Z(c)`.
   * `alpha_sum_country` and lineage fields (if present) MUST match S2/S3.

In other words, S4’s domain is exactly `D_esc × Z(c)`; nothing more, nothing less.

---

### 7.4 Ordering semantics (writer-sort)

Physical row order in `s4_zone_counts` is **not semantically authoritative**, but S4 MUST use a deterministic writer-sort.

Inside each `{seed, manifest_fingerprint}` partition, rows MUST be written sorted by the `ordering` key declared in the dictionary, e.g.:

1. `merchant_id` ascending,
2. `legal_country_iso` ascending,
3. `tzid` ascending.

Consumers MUST NOT:

* infer any additional meaning from row order (no “first zone is special”), or
* rely on order for logic (joins, grouping, etc.).

Ordering exists solely to guarantee:

* re-running S4 with the same inputs produces **byte-identical** files.

---

### 7.5 Merge, overwrite & idempotence discipline

` s4_zone_counts` is a **snapshot per `{seed, manifest_fingerprint}`**. It is not an append or log dataset.

**Single snapshot per run**

* For each `{seed, manifest_fingerprint}`, there MUST be at most one `s4_zone_counts` partition at the configured path.
* 3A.S4 is the only state allowed to write this dataset.

**No row-level merges**

* S4 MUST always construct the **complete** row set for `D_S4` and write it as a single snapshot.
* It MUST NOT:

  * append additional rows to an existing snapshot,
  * delete or mutate individual rows in place, or
  * treat multiple physical partitions under the same `{seed, fingerprint}` as distinct “epochs” for S4.

**Idempotent re-writes only**

If a dataset already exists at `{seed, manifest_fingerprint}` when S4 runs:

1. S4 MUST read it, normalise it to the same schema and writer-sort, and compare it against the newly computed row set.
2. If they are **identical**:

   * S4 MAY skip the write, or
   * re-write identical content; observable data MUST NOT change.
3. If they **differ**:

   * S4 MUST NOT overwrite the existing dataset, and
   * MUST surface an immutability violation (error code in §9), treating the run as FAIL.

Under no circumstances may S4 silently replace one `s4_zone_counts` snapshot with a different one for the same `{seed, manifest_fingerprint}`.

---

### 7.6 Cross-run semantics

S4 makes **no claims** about relationships between different `{seed, manifest_fingerprint}` pairs:

* Each partition `{seed, fingerprint}` describes a single run’s zone-count snapshot.
* Consumers MUST NOT combine rows from different runs and treat them as a single coherent allocation for any one run.

Cross-run unions (e.g. aggregating counts across runs for analytics) are allowed only for:

* diagnostics,
* monitoring, or
* “what-if” analysis.

They MUST NOT be used to infer or override S4’s integerisation for a specific run.

---

### 7.7 Interaction with upstream & downstream identity

**Upstream:**

* S1 owns `(merchant_id, legal_country_iso, site_count, is_escalated)`.
* S2 owns `(country_iso, tzid)` and `Z(c)`.
* S3 owns `Θ(m,c,z) = share_drawn(m,c,z)`.

S4 MUST:

* respect these identities and domain definitions,
* conserve `site_count(m,c)` exactly,
* keep `(m,c,z)` domain equal to `D_esc × Z(c)`.

**Downstream:**

* Any later state that needs zone-level outlet counts MUST:

  * join on `(seed, manifest_fingerprint, merchant_id, legal_country_iso, tzid)`,
  * treat `zone_site_count(m,c,z)` from S4 as authoritative for outlet counts per zone,
  * not re-integerise from S3’s shares.

Under these rules, `s4_zone_counts` has a clear identity, predictable partitions and ordering, and a strictly controlled merge discipline, ensuring that once a particular run’s integer zone allocation is published, it remains stable and unambiguous.

---

## 8. Acceptance criteria & validator hooks *(Binding)*

This section defines **when 3A.S4 is considered PASS** for a given run
`(parameter_hash, manifest_fingerprint, seed, run_id)` and what a later validation state MUST verify.

S4 is PASS **only** if:

* its `s4_zone_counts` snapshot is complete and consistent with S1/S2/S3, and
* its integerisation can be deterministically replayed from the upstream inputs.

---

### 8.1 Local acceptance criteria for 3A.S4

For a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, 3A.S4 is **PASS** if and only if **all** of the following hold:

#### 8.1.1 Preconditions satisfied (S0/S1/S2/S3)

* `s0_gate_receipt_3A` and `sealed_inputs_3A` exist for this `manifest_fingerprint` and are schema-valid.
* `s0_gate_receipt_3A.upstream_gates.segment_1A/1B/2A.status == "PASS"`.
* `s1_escalation_queue@{seed,fingerprint}` exists and is schema-valid.
* `s2_country_zone_priors@parameter_hash` exists and is schema-valid.
* `s3_zone_shares@{seed,fingerprint}` exists and is schema-valid.
* Run-report rows for S1, S2 and S3 indicate `status="PASS"` for the relevant identities.

Any failure here ⇒ S4 MUST be treated as FAIL.

---

#### 8.1.2 Domain alignment with S1 (merchant×country)

Let:

* `D` = set of `(merchant_id, legal_country_iso)` in `s1_escalation_queue@{seed,fingerprint}`.
* `D_esc` = `{ (m,c) ∈ D | is_escalated(m,c) = true }`.
* `D_S4_proj` = projection of `s4_zone_counts` onto `(merchant_id, legal_country_iso)`.

S4 is PASS only if:

* `D_S4_proj == D_esc`:

  * Every escalated `(m,c)` has at least one row in `s4_zone_counts`.
  * No non-escalated `(m,c)` appears in `s4_zone_counts`.

For each `(m,c) ∈ D_esc`:

* `zone_site_count_sum(m,c)` MUST equal `site_count(m,c)` from S1.
* `zone_site_count_sum(m,c) ≥ 0`.

If any `(m,c) ∈ D_esc` is missing from S4, or any `(m,c)` with `is_escalated=false` appears in S4, or `zone_site_count_sum(m,c) ≠ site_count(m,c)`, S4 MUST be treated as FAIL.

---

#### 8.1.3 Domain alignment with S2/S3 (zone universe per country)

For each `country_iso = c` observed in `D_esc`:

* From S2, define `Z(c) = { tzid | (country_iso=c, tzid) ∈ s2_country_zone_priors }`.
* For each `(m,c) ∈ D_esc`, define:

  * `Z_S4(m,c)` = `{ tzid | (m,c,tzid) appears in s4_zone_counts }`,
  * `Z_S3(m,c)` = `{ tzid | (m,c,tzid) appears in s3_zone_shares }`.

S4 is PASS only if for each `(m,c) ∈ D_esc`:

* `Z_S4(m,c) == Z(c) == Z_S3(m,c)`.

That is:

* S4 has counts for **all and only** the zones in S2 priors for that country,
* S4 and S3 agree exactly on the zone sets per `(m,c)`.

Any missing or extra `tzid` in S4 relative to S2/S3 MUST cause FAIL.

---

#### 8.1.4 Per-row invariants for `s4_zone_counts`

For every row in `s4_zone_counts`:

* `seed` and `manifest_fingerprint` equal the partition tokens.
* `zone_site_count` is an integer ≥ 0.
* `zone_site_count_sum` is an integer ≥ 0.
* `share_sum_country` is a number > 0.0.
* `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version`:

  * are non-empty strings, and
  * are constant across all rows in this `{seed,fingerprint}` partition and match S2/S3.

Any schema violation or path↔embed mismatch MUST cause S4 to FAIL.

---

#### 8.1.5 Per-(merchant×country) count conservation & consistency

For each `(m,c) ∈ D_esc`:

* Let `rows(m,c)` be all rows in S4 with `(merchant_id=m, legal_country_iso=c)`.
* Let `N = site_count(m,c)` from S1.
* S4 is PASS only if:

  * `zone_site_count_sum(m,c)` is constant across `rows(m,c)`, and
  * `zone_site_count_sum(m,c) = Σ_z zone_site_count(m,c,z) = N`.

If `fractional_target` and/or `residual_rank` are present:

* they MUST be consistent with the stated integerisation scheme:

  * `fractional_target(m,c,z)` ≈ `N * share_drawn(m,c,z)` for the corresponding S3 share,
  * residual ordering (as per the spec) must match which zones received +1 when `R(m,c) > 0`.

Any violation of conservation or internal consistency MUST cause FAIL.

---

#### 8.1.6 Consistency with S3 shares (algorithm-level)

Given S1’s `site_count(m,c)` and S3’s `share_drawn(m,c,z)`:

* there exists a deterministic integerisation mapping `(N, {T_z}) → {zone_site_count(m,c,z)}` defined in §6.
* For each `(m,c)`, the S4-produced `{zone_site_count(m,c,z)}` MUST equal what this mapping produces from:

  * `N = site_count(m,c)`,
  * `T_z = N * share_drawn(m,c,z)`.

If replaying the integerisation algorithm on S3’s shares for any `(m,c)` yields a different count vector than what is stored in S4, S4 MUST be considered FAIL.

---

#### 8.1.7 Idempotence & immutability

If a `s4_zone_counts` dataset already exists for `{seed, manifest_fingerprint}` when S4 runs:

* After normalising existing and newly computed rows (schema + sort), S4 MUST either:

  * find them identical (row set and field values) and leave the dataset unchanged, or
  * detect differences and treat this as an immutability violation, not overwrite.

Any attempt to overwrite non-identical `s4_zone_counts` for the same `{seed,fingerprint}` MUST be treated as FAIL.

---

### 8.2 Validator hooks for a 3A validation state

A later 3A validation state MUST treat S4 as follows:

#### 8.2.1 Schema & domain checks

* Re-validate `s4_zone_counts` against `schemas.3A.yaml#/plan/s4_zone_counts`.

* Recompute:

  * `D` and `D_esc` from S1,
  * `Z(c)` and `D_S3` from S2/S3.

* Assert:

  * projection of S4 onto `(m,c)` equals `D_esc`,
  * per `(m,c)`, S4’s `tzid` set equals `Z(c)` and S3’s zone set.

#### 8.2.2 Count conservation replay

For each `(m,c) ∈ D_esc`:

* join to S1 to get `N = site_count(m,c)`,
* join to S3 to get `share_drawn(m,c,z)` and `share_sum_country(m,c)`,
* recompute:

  * `T_z = N * share_drawn(m,c,z)`,
  * base counts `b_z = floor(T_z)`,
  * residuals `r_z = T_z - b_z`,
  * residual sorting order,
  * final `zone_site_count_replayed(m,c,z)` according to the deterministic scheme in §6.

Validators MUST assert that:

* `zone_site_count_replayed(m,c,z) == zone_site_count(m,c,z)` for all zones `z` and all `(m,c)`,
* `zone_site_count_sum(m,c)` equals `Σ_z zone_site_count(m,c,z)` and equals `N`.

Any mismatch is treated as an S4 integerisation mismatch.

#### 8.2.3 Aggregate metrics

The validation state SHOULD compute and (optionally) surface:

* `pairs_escalated` — |D_esc|.
* `zones_total` — number of `(m,c,z)` rows.
* `zones_zero_allocated` — count of rows with `zone_site_count = 0`.
* `pairs_with_single_zone` — number of `(m,c)` where exactly one zone has `zone_site_count > 0`.
* Distribution of `zone_site_count_sum` versus `site_count` (should match exactly).

These metrics are informative but provide useful hooks for CI thresholds and drift detection.

---

### 8.3 Obligations imposed on downstream consumers

Once S4 is PASS for a given `{seed, manifest_fingerprint}`:

1. **Downstream zone-aware states MUST treat S4 as count authority**

   * Any later 3A or Layer-2 state that needs zone-level outlet counts (e.g. mapping counts to sites, constructing zone-level routing behaviour) MUST:

     * use `s4_zone_counts` as the source of `zone_site_count(m,c,z)`, and
     * MUST NOT recompute integer counts directly from S3’s shares.

2. **3A segment-level validation MUST include S4 in its PASS bundle**

   * The 3A validation bundle MUST include `s4_zone_counts` (or at least its digest and schema_ref) for each run declared PASS.
   * It MUST use S4 outputs as described above (replay integerisation, domain checks, count conservation).

---

### 8.4 Handling of S4 failures

If S4 or a later validation state detects a violation of any acceptance criterion above:

* `s4_zone_counts` for that `{seed, manifest_fingerprint}` MUST be treated as **non-authoritative**.
* Any downstream artefact that depends on these zone counts MUST NOT be released or used for modelling.
* Recovery requires:

  * correcting configuration or bug (in S1/S2/S3 or S4), and
  * re-running S0/S1/S2/S3/S4 as necessary for a clean run.

Under these criteria, S4 is only considered acceptable when its integerisation:

* exactly conserves per-pair totals,
* aligns perfectly with S1’s domain and S2/S3’s zone universe, and
* can be deterministically replayed from upstream inputs.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only allowed failure classes** for 3A.S4 and assigns each a **canonical error code**.

Any S4 implementation MUST end each run in exactly one of:

* `status="PASS"` with `error_code = null`, or
* `status="FAIL"` with `error_code` equal to one of the codes below.

No additional error codes may be introduced without revising this specification.

---

### 9.1 Error taxonomy overview

3A.S4 can fail only for these reasons:

1. **Preconditions not met** (S0/S1/S2/S3 missing or not PASS).
2. **Catalogue / schema layer malformed.**
3. **Domain mismatches vs S1 (merchant×country).**
4. **Domain mismatches vs S2/S3 (zone universe per country).**
5. **Count conservation failures (per merchant×country).**
6. **Output schema or internal consistency failures.**
7. **Immutability / idempotence violations.**
8. **Infrastructure / I/O failures.**

Each is mapped to a specific `E3A_S4_XXX_*` code.

---

### 9.2 Precondition failures (S0/S1/S2/S3)

#### `E3A_S4_001_PRECONDITION_FAILED`

**Condition**

Raised when any required upstream 3A artefact is missing or invalid for this `(parameter_hash, manifest_fingerprint, seed, run_id)`, including:

* `s0_gate_receipt_3A` or `sealed_inputs_3A` missing or schema-invalid,
* S0 indicates any upstream segment gate (1A, 1B, or 2A) is not `"PASS"`,
* `s1_escalation_queue@{seed,fingerprint}` missing or schema-invalid,
* `s2_country_zone_priors@parameter_hash` missing or schema-invalid,
* `s3_zone_shares@{seed,fingerprint}` missing or schema-invalid,
* or the run-report rows for S1/S2/S3 indicate `status != "PASS"` for the relevant identities.

**Required fields**

* `component ∈ {"S0_GATE","S0_SEALED_INPUTS","S1_ESCALATION_QUEUE","S2_PRIORS","S3_ZONE_SHARES"}`
* `reason ∈ {"missing","schema_invalid","upstream_gate_not_pass","upstream_state_not_pass"}`
* If `reason="upstream_gate_not_pass"`:

  * `segment ∈ {"1A","1B","2A"}`
  * `reported_status` — non-`"PASS"` value.
* If `reason="upstream_state_not_pass"`:

  * `state ∈ {"S1","S2","S3"}`
  * `reported_status` — non-`"PASS"` value from that state’s run-report.

**Retryability**

* **Non-retryable** until the underlying failing components (S0/S1/S2/S3 or upstream segments) are corrected and rerun successfully.

---

### 9.3 Catalogue & schema failures

#### `E3A_S4_002_CATALOGUE_MALFORMED`

**Condition**

Raised when S4 cannot load or validate required catalogue artefacts, e.g.:

* missing or malformed:

  * `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml`,
  * `dataset_dictionary.layer1.3A.yaml`,
  * `artefact_registry_3A.yaml`,
* schema validation failures for any of these.

**Required fields**

* `catalogue_id` — identifier of the failing artefact (e.g. `"schemas.3A.yaml"`, `"dataset_dictionary.layer1.3A"`).

**Retryability**

* **Non-retryable** until the catalogue artefact is fixed and conforms to the Layer-1 catalogue schema.

---

### 9.4 Domain mismatches vs S1/S2/S3

#### `E3A_S4_003_DOMAIN_MISMATCH_S1`

**Condition**

Raised when the merchant×country domain of `s4_zone_counts` does not match S1’s escalated domain for this `{seed,fingerprint}`, i.e.:

* there exists `(m,c)` with `is_escalated=true` in `s1_escalation_queue` but no rows in `s4_zone_counts`, and/or
* there exists `(m,c)` in `s4_zone_counts` where S1 either:

  * has `is_escalated=false`, or
  * has no entry for `(m,c)`.

**Required fields**

* `missing_escalated_pairs_count` — number of `(m,c)` pairs with `is_escalated=true` in S1 but absent from S4.
* `unexpected_pairs_count` — number of `(m,c)` pairs present in S4 but not present as escalated in S1.
* Optionally:

  * `sample_merchant_id`,
  * `sample_country_iso`
    for one example of each class (subject to logging policy).

**Retryability**

* **Non-retryable** until S4’s implementation or orchestration is corrected; indicates a logic bug in building the domain or applying `is_escalated`.

---

#### `E3A_S4_004_DOMAIN_MISMATCH_ZONES`

**Condition**

Raised when the per-(merchant×country×zone) domain in `s4_zone_counts` does not match the zone universe defined by S2 and observed in S3 for escalated countries, i.e. for some `(m,c)`:

* the set of `tzid` values in S4, `Z_S4(m,c)`, is not equal to:

  * `Z(c)` from S2 (`s2_country_zone_priors`), or
  * `Z_S3(m,c)` from S3 (`s3_zone_shares`),

so that at least one of the following holds:

* a zone `z ∈ Z(c)` has no row in S4 for `(m,c,z)`, or
* S4 contains rows for a `tzid` that does not appear in S2’s priors for `country_iso=c` or in S3’s shares for `(m,c)`.

**Required fields**

* `affected_pairs_count` — number of `(m,c)` pairs with zone-domain mismatches.
* Optionally:

  * `sample_merchant_id`,
  * `sample_country_iso`,
  * `sample_tzid`
    for one offending example (subject to logging policy).

**Retryability**

* **Non-retryable** until either S4’s domain construction is fixed or S2/S3 surfaces are corrected; indicates inconsistency between integerisation domain and upstream shapes.

---

### 9.5 Count conservation failures

#### `E3A_S4_005_COUNT_CONSERVATION_BROKEN`

**Condition**

Raised when per-pair count conservation fails, i.e. for some `(m,c) ∈ D_esc`:

* `zone_site_count_sum(m,c)` does not equal the sum of `zone_site_count(m,c,z)` over all zones, and/or
* `zone_site_count_sum(m,c)` does not equal `site_count(m,c)` from S1.

Formally, if:

[
N = site_count(m,c),\quad
N' = zone_site_count_sum(m,c),\quad
N'' = \sum_{z \in Z(c)} zone_site_count(m,c,z),
]

and `N' ≠ N` or `N'' ≠ N`, this error MUST be raised.

**Required fields**

* `affected_pairs_count` — number of `(m,c)` pairs where conservation fails.
* Optionally one representative example with:

  * `sample_merchant_id`, `sample_country_iso`,
  * `site_count`, `zone_site_count_sum`, `sum_zone_site_count`.

**Retryability**

* **Non-retryable** until S4’s integerisation implementation is corrected; indicates an arithmetic or logic error in the transform from `(N, Θ)` to counts.

---

### 9.6 Output schema & internal consistency failures

#### `E3A_S4_006_OUTPUT_SCHEMA_INVALID`

**Condition**

Raised when the constructed `s4_zone_counts` dataset fails validation against `schemas.3A.yaml#/plan/s4_zone_counts`, for example:

* missing required fields,
* wrong types (e.g. `zone_site_count` not integer),
* invalid ranges (e.g. negative counts, non-positive `share_sum_country`),
* path↔embed mismatch (`seed`, `manifest_fingerprint` fields not matching partition tokens).

S4 MUST validate its output against the schema before treating the run as PASS; this error indicates a breach of the contract.

**Required fields**

* `violation_count` — number of schema validation errors detected.
* Optionally:

  * `example_field` — a field name involved in a representative violation.

**Retryability**

* **Retryable only after implementation fix**; indicates a bug in how S4 writes or serialises its output.

---

#### `E3A_S4_007_OUTPUT_INCONSISTENT`

**Condition**

Raised when `s4_zone_counts` is schema-valid but internally inconsistent with the deterministic integerisation contract, e.g.:

* For some `(m,c)`:

  * `zone_site_count_sum(m,c)` equals Σ counts, but `fractional_target` and/or `residual_rank` (if present) do not correspond to a valid floor+residual scheme applied to `T_z = N * share_drawn`,
* Prior lineage fields (`prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version`) are not constant across rows for a given `{seed,fingerprint}`, or do not match S2/S3 for this `parameter_hash`.
* `share_sum_country(m,c)` values copied into S4 do not match S3’s `share_sum_country` for the same `(m,c)`.

**Required fields**

* `reason ∈ {"integerisation_mismatch","lineage_inconsistent","share_sum_inconsistent"}`
* Optionally one representative example with:

  * `sample_merchant_id`, `sample_country_iso`,
  * and relevant `expected` vs `observed` values for the failing metric.

**Retryability**

* **Non-retryable** until S4 implementation or its integration with S2/S3 is corrected.

---

### 9.7 Immutability / idempotence failures

#### `E3A_S4_008_IMMUTABILITY_VIOLATION`

**Condition**

Raised when S4 detects that an existing `s4_zone_counts` snapshot for `{seed, manifest_fingerprint}` differs from what it would produce under the same `(parameter_hash, manifest_fingerprint, seed, run_id)` and catalogue state, e.g.:

* row sets differ (missing/extra `(m,c,z)` rows),
* one or more fields per row differ (e.g. `zone_site_count`, lineage fields).

**Required fields**

* `difference_kind ∈ {"row_set","field_value"}`
* `difference_count` — number of differing rows detected (may be approximate/capped).

**Retryability**

* **Non-retryable** until the conflict is resolved. Operators MUST determine:

  * whether the existing snapshot is authoritative (and S4 logic is wrong), or
  * whether S4 logic is correct and the previous snapshot was incorrect,

and then either:

* remove or archive the conflicting artefact and rerun S4, or
* generate a new manifest/run identity for corrected outputs.

S4 MUST NOT silently overwrite the existing snapshot.

---

### 9.8 Infrastructure / I/O failures

#### `E3A_S4_009_INFRASTRUCTURE_IO_ERROR`

**Condition**

Raised when S4 cannot complete due to environment-level issues unrelated to logical design, e.g.:

* transient object-store or filesystem failures while reading or writing artefacts,
* permission errors,
* network timeouts,
* storage quota exhaustion.

This code MUST NOT be used for logical failures already covered by `E3A_S4_001`–`E3A_S4_008`.

**Required fields**

* `operation ∈ {"read","write","list","stat"}`
* `path` — the path involved (if known)
* `io_error_class` — short label, e.g. `"timeout"`, `"permission_denied"`, `"not_found"`, `"quota_exceeded"`.

**Retryability**

* **Potentially retryable**, subject to infrastructure policy.

  * Orchestrators MAY retry S4 under the same inputs.
  * However, a retried run MUST still satisfy all acceptance criteria in §8 before `s4_zone_counts` is considered authoritative.

---

### 9.9 Run-report mapping

Each S4 run MUST set:

* `status="PASS", error_code=null` **or**
* `status="FAIL", error_code ∈ {E3A_S4_001 … E3A_S4_009}`.

Downstream components MUST treat any `status="FAIL"` for S4 as meaning:

* `s4_zone_counts` for that `{seed, manifest_fingerprint}` is **non-authoritative**, and
* any later component that needs zone-level counts MUST NOT use this dataset until the cause of failure is addressed and S4 has been successfully re-run.

---

## 10. Observability & run-report integration *(Binding)*

This section defines what **3A.S4 MUST emit** for observability and how it MUST integrate with the Layer-1 run-report.

S4 is **RNG-free** but **run-scoped** over
`(parameter_hash, manifest_fingerprint, seed, run_id)`, and its output (`s4_zone_counts`) is the *only* authority on zone-level integer counts. Observability must make it possible to answer, for any run:

* Did S4 run?
* Did it succeed or fail, and why?
* How many merchant×country pairs were escalated and integerised?
* How many zones per country received non-zero counts?
* Were counts conserved exactly per merchant×country?

—without inspecting every row.

S4 MUST NOT log bulk row-level content (e.g. all `(merchant_id, country, tzid, count)` rows).

---

### 10.1 Structured logging requirements

3A.S4 MUST emit **structured logs** (e.g. JSON records) for three lifecycle events: **start**, **success**, and **failure**.

#### 10.1.1 State start

Exactly one log event at the beginning of each S4 invocation.

Required fields:

* `layer = "layer1"`
* `segment = "3A"`
* `state = "S4"`
* `parameter_hash` (hex64)
* `manifest_fingerprint` (hex64)
* `seed` (uint64)
* `run_id` (string / u128-encoded)
* `attempt` (integer, if provided by orchestration; otherwise a fixed default such as `1`)

Optional fields:

* `trace_id` — correlation ID if provided by infrastructure.

Log level: `INFO`.

---

#### 10.1.2 State success

Exactly one log event **only if** S4 meets all acceptance criteria in §8 for this run.

Required fields:

* All “start” fields above

* `status = "PASS"`

* `error_code = null`

* **Domain summary:**

  * `pairs_total` — |D|, number of merchant×country pairs in `s1_escalation_queue`.
  * `pairs_escalated` — |D_esc|, number of pairs with `is_escalated = true`.
  * `pairs_monolithic` — `pairs_total − pairs_escalated`.

* **Zone & count summary (for escalated pairs):**

  * `zone_rows_total` — number of rows in `s4_zone_counts` (|D_S4|).
  * `zones_per_pair_avg` — average number of zones per escalated `(m,c)` (i.e. average |Z(c)| over `D_esc`).
  * `zones_zero_allocated` — total number of `(m,c,z)` rows where `zone_site_count = 0`.
  * `pairs_with_single_zone_nonzero` — number of `(m,c)` where exactly one zone has `zone_site_count > 0`.

* **Count conservation summary:**

  * `pairs_count_conserved` — number of `(m,c)` where `Σ_z zone_site_count(m,c,z) = site_count(m,c)`.
  * `pairs_count_conservation_violations` — MUST be `0` when `status="PASS"`.

* **Prior / policy lineage (from S2/S3):**

  * `prior_pack_id`
  * `prior_pack_version`
  * `floor_policy_id`
  * `floor_policy_version`

Optional fields:

* `elapsed_ms` — wall-clock duration of S4, provided by orchestration; MUST NOT influence S4 logic.
* `zone_zero_allocated_histogram` — small JSON map with coarse buckets (e.g. `{ "0": n0, "1-2": n1, "3+": n2 }`) summarising how many zones per `(m,c)` ended up with `zone_site_count = 0`.

Log level: `INFO`.

---

#### 10.1.3 State failure

Exactly one log event **only if** S4 terminates without satisfying §8.

Required fields:

* All “start” fields

* `status = "FAIL"`

* `error_code` — one of the `E3A_S4_***` codes from §9

* `error_class` — coarse label, e.g.:

  * `"PRECONDITION"` (for `E3A_S4_001_PRECONDITION_FAILED`),
  * `"CATALOGUE"`,
  * `"DOMAIN_S1"`,
  * `"DOMAIN_ZONES"`,
  * `"COUNT_CONSERVATION"`,
  * `"OUTPUT_SCHEMA"`,
  * `"OUTPUT_INCONSISTENT"`,
  * `"IMMUTABILITY"`,
  * `"INFRASTRUCTURE"`.

* `error_details` — structured object containing the code-specific fields required by §9 (e.g. `component`, `missing_escalated_pairs_count`, `affected_pairs_count`, `reason`, etc.).

Recommended additional fields (if available at failure time):

* `pairs_total` and `pairs_escalated`, if S4 progressed to loading S1.
* `zone_rows_total`, if S4 progressed to constructing/validating some zone rows.

Optional:

* `elapsed_ms` — if measurable.

Log level: `ERROR`.

All logs MUST be machine-parseable and MUST NOT include bulk row-by-row dumps of `s4_zone_counts`.

---

### 10.2 Segment-state run-report integration

Layer-1 maintains a **segment-state run-report** (e.g. `run_report.layer1.segment_states`) across all states, including S4.

For each S4 invocation, exactly **one row** MUST be written.

Because S4 is run-scoped and deterministic, the run-report row MUST uniquely identify the run and summarise the integerisation:

* **Identity & context**

  * `layer = "layer1"`
  * `segment = "3A"`
  * `state = "S4"`
  * `parameter_hash`
  * `manifest_fingerprint`
  * `seed`
  * `run_id`
  * `attempt`

* **Outcome**

  * `status ∈ {"PASS","FAIL"}`
  * `error_code` — `null` on PASS; one of §9 on FAIL
  * `error_class` — as above
  * `first_failure_phase` — optional enum, e.g.:
    `{ "S0_GATE", "S1_INPUT", "S2_PRIORS", "S3_SHARES", "DOMAIN_BUILD", "INTEGERISATION", "OUTPUT_WRITE", "IMMUTABILITY", "INFRASTRUCTURE" }`

* **Domain & escalation summary**

  * `pairs_total` — |D| from S1.
  * `pairs_escalated` — |D_esc|.
  * `pairs_monolithic` — `pairs_total − pairs_escalated`.

* **Zone & count summary** (required on PASS; MAY be populated on FAIL if available):

  * `zone_rows_total` — number of rows in `s4_zone_counts`.
  * `zones_per_pair_avg` — average number of zones per escalated pair.
  * `zones_zero_allocated` — global count of `(m,c,z)` rows with `zone_site_count = 0`.
  * `pairs_with_single_zone_nonzero` — number of `(m,c)` where exactly one zone has non-zero count.

* **Count conservation summary**

  * `pairs_count_conserved` — number of `(m,c)` that passed conservation checks.
  * `pairs_count_conservation_violations` — number of `(m,c)` where conservation failed (MUST be `0` on PASS).

* **Prior / policy lineage**

  * `prior_pack_id`
  * `prior_pack_version`
  * `floor_policy_id`
  * `floor_policy_version`

* **Catalogue / schema versions**

  * At minimum, to stay consistent with S0–S3:

    * `schemas_layer1_version`
    * `schemas_3A_version`
    * `dictionary_layer1_3A_version`
    * optionally `artefact_registry_3A_version`.

* **Timing & correlation**

  * `started_at_utc` — orchestrator-provided; MUST NOT feed back into S4 logic.
  * `finished_at_utc`
  * `elapsed_ms`
  * `trace_id` — if provided.

The run-report row MUST be:

* consistent with `s1_escalation_queue`, `s3_zone_shares`, and `s4_zone_counts` (domains and counts), and
* sufficient for operators and validation tooling to see S4’s behaviour and whether it respected conservation and domain rules.

---

### 10.3 Metrics & counters

S4 MUST expose a minimal set of metrics for monitoring and SLOs. Names/export mechanism are implementation details; semantics are binding.

At minimum:

* `mlr_3a_s4_runs_total{status="PASS"|"FAIL"}`

  * Monotone counter, incremented once per S4 run.

* `mlr_3a_s4_pairs_escalated` (gauge)

  * Number of escalated `(merchant_id, country)` pairs in the most recent successful run for a given `{seed,fingerprint}`.

* `mlr_3a_s4_zone_rows_total` (gauge)

  * Number of rows (zone-level counts) in `s4_zone_counts` for the most recent successful run.

* `mlr_3a_s4_zones_zero_allocated` (gauge)

  * Count of rows with `zone_site_count = 0` in the most recent successful run.

* `mlr_3a_s4_pairs_count_conservation_violations_total` (counter)

  * Incremented whenever `E3A_S4_005_COUNT_CONSERVATION_BROKEN` is raised.

* `mlr_3a_s4_domain_mismatch_s1_total` (counter)

  * Incremented whenever `E3A_S4_003_DOMAIN_MISMATCH_S1` occurs.

* `mlr_3a_s4_domain_mismatch_zones_total` (counter)

  * Incremented whenever `E3A_S4_004_DOMAIN_MISMATCH_ZONES` occurs.

* `mlr_3a_s4_duration_ms` (histogram)

  * Distribution of `elapsed_ms` per S4 run.

Metric labels MUST NOT include raw `merchant_id` or `tzid` values. Labels SHOULD be limited to:

* `state="S4"`,
* `status="PASS"|"FAIL"`,
* `error_class`,
* coarse buckets for domain size (e.g. small/medium/large).

---

### 10.4 Correlation & traceability

To support end-to-end tracing across the 3A pipeline:

1. **Correlation with S0–S3 and future S5+**

   * S4’s run-report rows MUST be joinable to S0, S1, S2, S3 (and any later 3A states) via:

     * `(layer="layer1", segment="3A", parameter_hash, manifest_fingerprint, seed, run_id)`,

     with the understanding that S2 is parameter-scoped and may omit `seed`/`run_id`.

   * If a `trace_id` is used by the orchestrator, S4 MUST propagate it into:

     * structured logs, and
     * the run-report row.

2. **Linkage to artefacts**

   A 3A validation state MUST be able to:

   * locate `s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}` via the 3A dictionary/registry,
   * join it to:

     * `s1_escalation_queue@{seed,fingerprint}` (for domain and `site_count`),
     * `s3_zone_shares@{seed,fingerprint}` (for `share_drawn`),
     * `s2_country_zone_priors@parameter_hash` (for `Z(c)` and prior lineage),
     * and S0 artefacts (for sealed input and gate provenance).

S4’s logging and run-report fields MUST expose enough identity for these joins to be unambiguous.

---

### 10.5 Retention, access control & privacy

Even though S4 operates on synthetic data, its outputs are still **behaviourally sensitive** (they encode spatial distribution of outlets). The following are binding:

1. **Retention**

   * `s4_zone_counts` MUST be retained for at least as long as:

     * any downstream artefact (e.g. site-level allocations, Layer-2 behaviour, models) derived from it remains in use, and
     * any analyses that rely on those derived artefacts are considered active.

   * Deleting S4 outputs while their dependants are still deployed is out of spec.

2. **Access control**

   * Access to `s4_zone_counts`, S4 logs and run-report rows SHOULD be limited to principals authorised to inspect internal engine behaviour.
   * S4 observability surfaces MUST NOT contain:

     * bulk per-merchant per-zone breakdowns in logs,
     * secrets (credentials, keys),
     * any PII beyond what Layer-1 logging policy permits (which, for synthetic data, is typically not an issue but still governed centrally).

3. **No bulk row-level leakage via observability**

   * Logs and metrics MUST NOT emit full lists of `(merchant_id, country, tzid, zone_site_count)`;
   * Where sample identities are needed in error details (for debugging `E3A_S4_003`/`004`/`005`/`007`), they MUST respect Layer-1 redaction/sampling policies (e.g. only a small sampled subset, or hashed IDs if so required).

---

### 10.6 Relationship to Layer-1 run-report governance

Layer-1 may impose additional run-report requirements (e.g. mandatory columns for all states, environment identifiers, cluster ID).

Where there is a conflict:

* **Layer-1 run-report schema** takes precedence for:

  * shape,
  * required fields.

* This S4 section then governs what S4 MUST populate in its part of that schema and how those values relate to:

  * `s1_escalation_queue`,
  * `s2_country_zone_priors`,
  * `s3_zone_shares`,
  * `s4_zone_counts`, and
  * S0’s gate and sealedinputs.

Under these rules, every S4 run is:

* **observable** (via structured logs),
* **summarised** (via a single run-report row), and
* **auditable** (via joins over `s4_zone_counts`, S1–S3 outputs and S0 artefacts),

while preserving privacy and maintaining the Layer-1 authority chain.

---

## 11. Performance & scalability *(Informative)*

This section explains how 3A.S4 behaves at scale. The binding rules remain in §§1–10; here we just interpret them operationally.

---

### 11.1 Workload shape

S4 only touches:

* **Escalated merchant×country pairs** `D_esc` from S1, and
* **Zone sets** `Z(c)` from S2/S3.

It never:

* scans 1A `outlet_catalogue` row-by-row,
* touches site-level geometry or tzids,
* looks at arrivals/routing, or RNG.

So the effective work is proportional to:

[
\text{Work} \sim \sum_{(m,c)\in D_{\text{esc}}} |Z(c)|
]

i.e. “number of escalated pairs × average zones per country”, not total outlets or transactions.

---

### 11.2 Complexity drivers

Per run `{seed, manifest_fingerprint}`:

1. **Domain joins**

   * Join `s1_escalation_queue` and `s3_zone_shares` on `(m,c)` and `s2_country_zone_priors` on `c` to derive:

     * `D_esc`,
     * `Z(c)` per country,
     * share vectors per `(m,c)`.

   * Complexity: O(|D| + |D_esc| × avg|Z(c)|); typically dominated by `s3_zone_shares` size.

2. **Integerisation per `(m,c)`**

   For each escalated `(m,c)`:

   * Compute `T_z = N * share_drawn` per zone (K multiplications).
   * Compute `b_z = floor(T_z)` and residuals `r_z`.
   * Sort zones by residual (cost O(K log K) per country; K is number of zones for that country).
   * Allocate `R` residual units.

   Overall: roughly O(Σ K log K); with small K (few tzids per country) this is effectively linear.

3. **Writing `s4_zone_counts`**

   * One row per `(m,c,z)` in `D_S4`.
   * Complexity: linear in row count.

Net effect: S4’s asymptotic complexity is governed by the **size of `s3_zone_shares`**, which itself is already filtered to escalated pairs and zone sets.

---

### 11.3 Memory footprint

S4 does **not** need to hold everything in memory at once.

A reasonable implementation can:

* **Group & stream**:

  * Iterate `s3_zone_shares` grouped by `(merchant_id, legal_country_iso)`,
  * For each group:

    * read `site_count(m,c)` from S1,
    * read or cache `Z(c)` from S2,
    * integerise locally into `zone_site_count(m,c,z)`,
    * immediately write out the corresponding rows (or buffer a modest batch),
  * then discard per-pair state and move on.

Peak memory is then roughly:

* O(max zones per country × max active `(m,c)` in a batch),
* plus small caches for `Z(c)` and prior lineage.

No part of S4’s design requires loading all `s3_zone_shares` or all `(m,c,z)` into RAM at once.

---

### 11.4 Reuse & scheduling

S4 is tied to a **specific run**:

* Outputs depend on:

  * S1’s `site_count(m,c)`,
  * S3’s realised shares `Θ(m,c,z)` for that `{seed,fingerprint}`.

So:

* S2 priors can be **reused** across manifests via `parameter_hash`.
* S3/S4 must run per `{seed, manifest_fingerprint, run_id}` combination you care about (one snapshot per run).

Operationally:

* S4 is typically scheduled **after** S3 completes and passes for that run.
* If S3 is re-run with a new `run_id` (e.g. different RNG realisation), S4 must be re-run for the new shares.

---

### 11.5 Parallelism & streaming

S4 is “embarrassingly parallel” over `(m,c)`:

* Different merchant×country pairs can be processed independently, as long as:

  * S1/S3 inputs are partitioned consistently,
  * each worker writes into the correct `{seed,fingerprint}` partition without conflicting writes (e.g. partitioned by merchant hash).

Within a worker:

* process `(m,c)` groups in streaming fashion,
* integerise and flush outputs per group or batch.

This allows S4 to scale with cluster size without changing semantics.

---

### 11.6 Expected runtime profile

Relative to other states:

* S4 is lighter than:

  * S1 (full group-by of outlets),
  * S2 (prior prep across all countries×zones),
  * S3 (Gamma/Dirichlet sampling with RNG).

* It’s pure arithmetic + sorting over relatively small per-country zone sets.

The main knobs that affect runtime:

* `pairs_escalated` = |D_esc| (how aggressive S1 is),
* `avg_zones_per_country` = average |Z(c)|,
* implementation details (e.g. whether residual ranking is vectorised or heavily boxed).

---

### 11.7 Tuning levers (non-normative)

Implementers can tune S4 without changing semantics by:

* **Batching:**

  * Choose a batch size of `(m,c)` pairs per worker to balance memory and I/O.

* **Precomputing `Z(c)` and caches:**

  * Build a small in-memory map `country → Z_ord(c)` once per `parameter_hash` from S2, avoiding repeated scans.

* **Numeric tolerance checks:**

  * Use stable, consistent tolerances when checking `share_sum_country ≈ 1`; keep those tolerances in the validation spec so they don’t drift unnoticed.

All these must preserve:

* domain equality,
* exact count conservation,
* determinism of `zone_site_count(m,c,z)` given `(N, Θ)`, and
* idempotence guarantees in §7–§8.

Under this design, S4 remains a small, predictable step whose cost scales with “how many escalated pairs and zones you actually have,” not with the overall engine volume.

---

## 12. Change control & compatibility *(Binding)*

This section defines **how the 3A.S4 contract is allowed to evolve**, and what guarantees downstream consumers (later 3A states, validation, analytics) can rely on when:

* the S4 spec or dataset changes,
* the integerisation scheme changes, or
* upstream contracts (S1/S2/S3, parameter set 𝓟) evolve.

Given a run identified by:

`(parameter_hash, manifest_fingerprint, seed, run_id, version_of_s4_zone_counts)`

consumers must be able to unambiguously understand:

* which `(merchant_id, legal_country_iso, tzid)` triples are present,
* what `zone_site_count` means,
* how it relates to `site_count` and `share_drawn`, and
* how to replay / validate the integerisation.

---

### 12.1 Scope of change control

Change control for 3A.S4 covers:

1. The **shape and semantics** of its output dataset:

   * `s4_zone_counts`
   * partitioning by `["seed","fingerprint"]`
   * meaning of `zone_site_count`, `zone_site_count_sum`, `share_sum_country`, and lineage fields.

2. The **deterministic mapping** from inputs to outputs:

   * how S4 maps from:

     * S1 domain + counts (`D`, `D_esc`, `site_count`),
     * S2 zone universe (`Z(c)`),
     * S3 shares `Θ(m,c,z) = share_drawn(m,c,z)`,
       to:
     * integer counts `zone_site_count(m,c,z)`.

   * in particular, the integerisation scheme (e.g. floor + residual ranking) and its tie-breaking rules.

3. The **error taxonomy** and acceptance criteria (Sections 8–9).

It does **not** govern:

* the internal execution model (single-node vs distributed, streaming vs batch), as long as observable behaviour is unchanged;
* global Layer-1 definitions of `parameter_hash`, `manifest_fingerprint`, `seed` or `run_id`.

---

### 12.2 S4 dataset contract versioning

The S4 dataset contract has a **version**, carried as:

* `version` in the `dataset_dictionary.layer1.3A.yaml` entry for `s4_zone_counts`, and
* the matching `version` in `artefact_registry_3A.yaml` for `mlr.3A.s4_zone_counts`.

Rules:

1. **Single authoritative version.**

   * The dictionary and registry MUST agree on the `version` of `s4_zone_counts`.
   * Any change that affects dataset shape or semantics MUST be accompanied by a version bump.

2. **Semver semantics.**

   * `MAJOR.MINOR.PATCH`:

     * **PATCH** (`x.y.z → x.y.(z+1)`):

       * fixes or clarifications that do not change outputs for any compliant implementation (e.g. doc clarifications, stricter internal validation that only converts silently-bad runs into explicit FAIL).

     * **MINOR** (`x.y.z → x.(y+1).0`):

       * backwards-compatible extensions, e.g.

         * adding optional columns (`fractional_target`, `residual_rank`, more diagnostics),
         * adding new error codes,
         * adding log/run-report fields.
       * Existing consumers that ignore new fields remain correct.

     * **MAJOR** (`x.y.z → (x+1).0.0`):

       * breaking changes, including shape, identity, partitioning, or integerisation semantics that alter `zone_site_count` for a given input.

3. **Consumers MUST key off version.**

   * Consumers MUST NOT infer S4 behaviour from date or build; they MUST rely on:

     * the `schema_ref` for `s4_zone_counts`, and
     * its `version` from the dictionary/registry.

---

### 12.3 Backwards-compatible changes (MINOR/PATCH)

The following changes are **backwards-compatible** for S4, provided they obey the constraints below.

1. **Adding optional columns to `s4_zone_counts`.**
   Examples:

   * `fractional_target` (if not already present),
   * `residual_rank`,
   * extra diagnostics like `max_residual` or `is_zero_allocated` (boolean).

   Conditions:

   * New fields MUST be optional or have defaults.
   * They MUST be deterministic, derived from existing inputs, and MUST NOT change:

     * which `(m,c,z)` rows appear, or
     * the values of `zone_site_count`, `zone_site_count_sum`, or `share_sum_country`.

2. **Adding new metrics / run-report fields.**

   * Additional summary metrics (e.g. more detailed histograms, per-country summaries) are allowed as long as they do not alter the dataset or the acceptance criteria.

3. **Adding new error codes.**

   * New `E3A_S4_XXX_*` codes may be added to refine failure reporting, as long as:

     * existing codes keep their original meaning, and
     * existing consumers treat unknown codes as generic FAIL.

4. **Tightening validation.**

   * Additional internal checks (e.g. tighter tolerances on joining S2/S3, or stricter lineages) are allowed if they:

     * do not change outputs for previously valid runs, but
     * may convert previously invalid runs into explicit FAILs.

5. **Performance improvements.**

   * Changing execution strategy (vectorising, parallelising, streaming) is fine as long as:

     * for the same S1/S2/S3 inputs, S4 produces identical `s4_zone_counts` and passes all acceptance criteria.

These changes may require a MINOR bump if they alter the schema; pure doc or validator changes are usually PATCH-level.

---

### 12.4 Breaking changes (MAJOR)

The following are **breaking changes** for S4 and MUST trigger a **MAJOR** version bump for the dataset contract (and co-ordinated updates in downstream consumers and validation):

1. **Changing dataset identity or partitioning.**

   * Altering the partition key set for `s4_zone_counts` (e.g. adding `parameter_hash` or `run_id`, dropping `seed` or `fingerprint`).
   * Renaming the dataset ID away from `"s4_zone_counts"` or modifying the path template in a non-compatible way.
   * Changing the logical primary key `(merchant_id, legal_country_iso, tzid)`.

2. **Changing the integerisation semantics.**

   * Switching from the current floor+residual scheme to a fundamentally different rounding approach (e.g. stochastic rounding, different tie-break ordering), **if** that can change `zone_site_count(m,c,z)` for the same inputs.
   * Changing the deterministic tie-break order in residual ranking that can change which zones receive the +1 residual units.
   * Introducing additional constraints (e.g. per-zone minimums or hard caps) in a way that alters the resulting count vectors for existing inputs.

3. **Changing the domain semantics for S4.**

   * Allowing `s4_zone_counts` to omit some `(m,c)` in `D_esc` or omit zones in `Z(c)` without marking the run as FAIL.
   * Including zone counts for non-escalated `(m,c)`, or for tzids not present in S2/S3.

4. **Relaxing count-conservation invariants.**

   * Allowing `zone_site_count_sum(m,c) ≠ site_count(m,c)` without treating this as a failure.
   * Allowing `zone_site_count_sum(m,c) ≠ Σ_z zone_site_count(m,c,z)`.

5. **Relaxing immutability.**

   * Allowing S4 to overwrite an existing `s4_zone_counts` snapshot for the same `{seed, manifest_fingerprint}` with different counts, without treating it as an immutability violation.

Any such change requires:

* a MAJOR version bump in the dictionary/registry for `s4_zone_counts`,
* updated schema/contract in `schemas.3A.yaml`, and
* co-ordinated updates in:

  * downstream states that consume S4, and
  * validation states that replay integerisation and enforce invariants.

---

### 12.5 Upstream evolution vs `parameter_hash` and S1/S2/S3

S4’s outputs depend on:

* S1: domain `D` and `site_count(m,c)`,
* S2: zone universe `Z(c)` (and priors, for lineage),
* S3: Dirichlet shares `Θ(m,c,z)`.

Binding rules:

1. **Priors & floor policy changes → new `parameter_hash`.**

   * Any semantic change to S2’s inputs (prior pack or floor policy) that alters `Z(c)` or α-vectors MUST result in a new `parameter_hash` and new S2 outputs.
   * S4 indirectly depends on this via S2 and S3. S4 does not need to know the old priors, but it MUST treat `parameter_hash` as the identity of the prior universe.

2. **S1 & S3 changes are run-level, not parameter-level.**

   * Changes in S1’s escalation decisions or S3’s Dirichlet draws are run-specific effects (domain and stochastic draw respectively).
   * As long as S1/S3 remain within their own contracts, S4 does not need a new contract version; it simply obeys the current S1/S3 surfaces.

3. **S4 MUST NOT silently accept inconsistent upstream inputs.**

   * If S4 detects domain mismatches between S1/S3/S2 (e.g. escalated pairs with no shares, or shares that do not cover all `Z(c)`), it MUST fail (see §9), not attempt to “repair” or supplement upstream artefacts.
   * If S4 detects priors or floor/policy digests in S0 that do not match S2/S3’s actual content for this `parameter_hash`, that mismatch MUST be handled via S0/S2/S3 error paths, not hidden by S4.

In short: for a given run, S4 assumes S1/S2/S3 are already a coherent, sealed world; it does not attempt to adapt to param/policy changes under the same `parameter_hash`.

---

### 12.6 Catalogue evolution (schemas, dictionary, registry)

S4 depends on:

* `schemas.3A.yaml#/plan/s4_zone_counts`,
* `dataset_dictionary.layer1.3A.yaml` (for `s4_zone_counts`),
* `artefact_registry_3A.yaml` (`mlr.3A.s4_zone_counts` entry).

1. **Schema evolution.**

   * Adding optional fields to the `s4_zone_counts` schema is a MINOR-compatible change.
   * Removing fields or changing the type/meaning of required fields (e.g. dropping `zone_site_count_sum`, changing `zone_site_count` from integer to float) is **breaking**, requiring a MAJOR contract bump.

2. **Dictionary evolution.**

   * Changing `id`, `path`, `partitioning`, or `schema_ref` for `s4_zone_counts` is a breaking change per §12.4 and MUST be co-ordinated with a MAJOR version bump.
   * Adding new datasets (e.g. `s4_zone_counts_summary`) is compatible, as long as the S4 spec is updated to describe them and they have distinct IDs.

3. **Registry evolution.**

   * Adding unrelated artefacts to `artefact_registry_3A.yaml` is compatible.
   * Renaming/removing `mlr.3A.s4_zone_counts`, or changing its `path` or `schema` entries, is breaking and MUST be synchronised with a MAJOR version bump.

---

### 12.7 Deprecation strategy

When evolving S4:

1. **Introduce before removing.**

   * New behaviour (e.g. new diagnostic fields) SHOULD be introduced in a MINOR version while preserving the old fields and semantics.

2. **Deprecation signalling.**

   * The S4 spec and/or the 3A validation state MAY include non-normative notes, such as:

     * “`fractional_target` will be added in v1.1.0.”
     * “`zone_site_count_sum` may be deprecated in favour of recomputing sums from `zone_site_count` in v2.0.0.”

3. **Hard removal only with MAJOR bump.**

   * Removing fields, relaxing invariants, or changing integerisation semantics MUST be done only with a MAJOR version bump and co-ordinated updates in all consumers.

Historic `s4_zone_counts` outputs MUST NOT be rewritten to conform to newer contracts; they remain valid under the contract version they were produced with.

---

### 12.8 Cross-version operation

Different runs and parameter sets may see different S4 versions over time.

1. **Per-run contract.**

   * For each `{seed, manifest_fingerprint}`, the `version` of `s4_zone_counts` in the dictionary/registry defines the contract for that run’s zone-count snapshot.
   * S4’s consumers (validation, downstream 3A states) MUST interpret each partition according to its own S4 version.

2. **Consumer strategy.**

   * Consumers that deal with multiple runs (e.g. global analytics) SHOULD:

     * explicitly support all S4 versions they expect to encounter, or
     * operate on the intersection of fields and semantics common to those versions (e.g. always using `zone_site_count` and `site_count` relations).

3. **No retroactive upgrades.**

   * Existing `s4_zone_counts/seed={s}/fingerprint={F}` artefacts MUST NOT be mutated to fit new contracts.
   * If a re-integerisation under a new S4 contract is required, it MUST be treated as a new run:

     * either with a new `{seed, manifest_fingerprint, run_id}`, or
     * under a different environment, clearly separated in the catalogue.

---

Under these rules, 3A.S4 can evolve:

* **safely** (minor changes add diagnostics or strengthen validation, without changing semantics), and
* **explicitly** (any change that can alter integer counts for the same inputs is clearly versioned and coordinated),

so that downstream code and validators never see zone-count surfaces whose meaning has silently shifted under their feet.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix records the symbols and shorthand used in the 3A.S4 design. It has **no normative force**; it’s here so S0–S4 and the validation docs use a consistent vocabulary.

---

### 13.1 Scalars, hashes & identifiers

* **`parameter_hash`**
  Layer-1 hash over the governed parameter set 𝓟 (priors, floor policy, RNG policy, etc.). Fixed before any 3A state runs; S4 itself is not partitioned by it, but it defines which S2/S3 surfaces are in force.

* **`manifest_fingerprint`**
  Layer-1 manifest hash for a run, used by S0, and as a partition token for S1/S3/S4. For S4, appears as `fingerprint={manifest_fingerprint}`.

* **`seed`**
  Layer-1 global RNG seed (`uint64`). S4 does **not** consume RNG, but uses `seed` as part of its partition key and lineage.

* **`run_id`**
  Run identifier (string or u128-encoded), used for run-report and correlation. Does not affect S4’s data-plane logic.

* **`merchant_id`**
  Layer-1 merchant identity (`id64`), inherited from 1A/S1/S3.

* **`legal_country_iso` / `country_iso`**
  ISO-3166 alpha-2 country code (e.g. `"GB"`, `"US"`).

  * In S1/S3/S4: `legal_country_iso`.
  * In S2/S3 priors/shares, sometimes referred to generically as `country_iso`.

* **`tzid`**
  IANA time-zone identifier (e.g. `"Europe/London"`), as defined by 2A and the ingress tz universe.

---

### 13.2 Sets & domains

For a fixed `{seed, manifest_fingerprint}`:

* **`D` (S1 merchant×country domain)**

  [
  D = {(m,c)} = {(merchant_id, legal_country_iso)\ \text{present in } s1_escalation_queue}.
  ]

* **`D_{\text{esc}}` (escalated domain)**

  [
  D_{\text{esc}} = {(m,c) \in D \mid is_escalated(m,c) = true}.
  ]

  Only these pairs get zone splits.

* **`Z(c)` (zone universe per country)**

  For a given country `c`:

  [
  Z(c) = { tzid \mid (country_iso=c, tzid) \in s2_country_zone_priors}.
  ]

  This is the set of zones for which priors exist for country `c`.

* **`Z_{\text{ord}}(c)` (ordered zone list)**

  Deterministic ordering of `Z(c)`, e.g.:

  [
  Z_{\text{ord}}(c) = [z_1, \dots, z_{K(c)}]
  ]

  where the `z_i` are `tzid` values sorted lexicographically. S3 and S4 use this order consistently.

* **`D_{\text{S4}}` (S4 domain)**

  Domain of `s4_zone_counts` for this `{seed, fingerprint}`:

  [
  D_{\text{S4}} = { (m,c,z) \mid (m,c) \in D_{\text{esc}},\ z \in Z(c) }.
  ]

  There is one row per triple in `D_S4`.

---

### 13.3 Counts, shares & targets

For a given escalated merchant×country pair `(m,c)`:

* **`site_count(m,c)`**
  Total number of outlets in 1A for merchant `m` in country `c`, as surfaced by S1:

  [
  N(m,c) = site_count(m,c) \in \mathbb{N},\ N(m,c) \ge 1.
  ]

* **`Θ(m,c,z)` (S3 share vector)**

  For `z ∈ Z(c)`, S3’s Dirichlet sample:

  [
  \Theta(m,c,z) = share_drawn(m,c,z) \in [0,1],
  ]

  with:

  [
  share_sum_country(m,c) = \sum_{z \in Z(c)} \Theta(m,c,z) \approx 1.
  ]

  In S3/S4 tables: `share_drawn` and `share_sum_country`.

* **`T_z(m,c)` (fractional targets)**

  Continuous target (expected count) for zone `z`:

  [
  T_z(m,c) = N(m,c) \cdot \Theta(m,c,z).
  ]

  Stored in S4 as `fractional_target` if that optional column is present.

* **`b_z(m,c)` (base counts)**

  Floor of the target count:

  [
  b_z(m,c) = \lfloor T_z(m,c) \rfloor.
  ]

* **`r_z(m,c)` (residuals)**

  Residual fraction per zone:

  [
  r_z(m,c) = T_z(m,c) - b_z(m,c) \in [0,1).
  ]

* **`base_sum(m,c)`**

  Sum of base counts:

  [
  base_sum(m,c) = \sum_{z \in Z(c)} b_z(m,c).
  ]

* **`R(m,c)` (residual capacity)**

  Remaining units to distribute after flooring:

  [
  R(m,c) = N(m,c) - base_sum(m,c).
  ]

  `R(m,c)` is the number of `+1` bumps to allocate via residual ranking.

---

### 13.4 Final integer counts

For an escalated pair `(m,c)` and zone `z ∈ Z(c)`:

* **`zone_site_count(m,c,z)`**

  Final integer outlet count for this zone, as output by S4:

  [
  zone_site_count(m,c,z) \in \mathbb{N},\quad
  zone_site_count(m,c,z) \ge 0.
  ]

  In S4: `zone_site_count`.

* **`zone_site_count_sum(m,c)`**

  Sum of zone counts for this pair (repeated on each row for `(m,c)`):

  [
  zone_site_count_sum(m,c) = \sum_{z \in Z(c)} zone_site_count(m,c,z).
  ]

  Acceptance criterion requires:

  [
  zone_site_count_sum(m,c) = site_count(m,c).
  ]

* **`residual_rank(m,c,z)`** *(optional)*

  If S4 exposes it, a 1-based rank of `z` in the residual ordering used to allocate `R(m,c)` units:

  * largest residual → rank 1,
  * ties broken deterministically (e.g. by `tzid`).

  In S4: `residual_rank`.

---

### 13.5 Priors & policy lineage

These are carried into S4 from S2/S3 for traceability:

* **`alpha_sum_country(c)`**

  Total prior α mass for country `c` from S2:

  [
  \alpha_\text{sum_country}(c) = \sum_{z \in Z(c)} \alpha_\text{effective}(c,z).
  ]

  May be stored in S4 per row (optional).

* **`prior_pack_id` / `prior_pack_version`**

  * `prior_pack_id`: logical ID for S2’s prior pack artefact (e.g. `"country_zone_alphas_3A"`).
  * `prior_pack_version`: semver or digest tag for that prior pack.

* **`floor_policy_id` / `floor_policy_version`**

  * `floor_policy_id`: logical ID for S2’s floor/bump policy artefact.
  * `floor_policy_version`: corresponding version or digest tag.

These fields are repeated on all rows of `s4_zone_counts` for a given run and should match the lineage values seen in S2/S3.

---

### 13.6 Error codes & status (S4)

* **`error_code`**

  Canonical S4 error code from §9, e.g.:

  * `E3A_S4_001_PRECONDITION_FAILED`
  * `E3A_S4_003_DOMAIN_MISMATCH_S1`
  * `E3A_S4_004_DOMAIN_MISMATCH_ZONES`
  * `E3A_S4_005_COUNT_CONSERVATION_BROKEN`
  * `E3A_S4_008_IMMUTABILITY_VIOLATION`

* **`status`**

  S4 outcome in logs/layer1/3A/run-report:

  * `"PASS"` — S4 met all acceptance criteria; `s4_zone_counts` is authoritative for this `{seed,fingerprint}`.
  * `"FAIL"` — S4 terminated with one of the error codes above; its outputs for that run MUST NOT be used.

* **`error_class`**

  Coarse category for `error_code`, e.g.:

  * `"PRECONDITION"`, `"CATALOGUE"`, `"DOMAIN_S1"`, `"DOMAIN_ZONES"`, `"COUNT_CONSERVATION"`, `"OUTPUT_SCHEMA"`, `"OUTPUT_INCONSISTENT"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`.

---

These symbols line up with those used in S1–S3 and Layer-1, so that when you read across the chain:

> S1 (domain & `site_count`) → S2 (`Z(c)`, priors) → S3 (`Θ(m,c,z)`) → S4 (`zone_site_count(m,c,z)`),

the notation for `(D_esc, Z(c), N(m,c), Θ(m,c,z), T_z, b_z, r_z, R(m,c), zone_site_count)` stays consistent and unambiguous.

---
