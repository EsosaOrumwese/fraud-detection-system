# State 3A ·S5 — Zone Allocation Egress & Routing Universe Hash

## 1. Purpose & scope *(Binding)*

State **3A.S5 — Zone Allocation Egress & Routing Universe Hash** is the **packaging and sealing** state for Segment 3A. It does **not** change any counts or shares; instead it takes the final zone-level allocation computed by S4, combines it with the priors and policies from S2 and the day-effect configuration used by 2B, and publishes:

1. A **cross-layer egress dataset** that exposes each merchant’s zone allocations in a stable, well-typed shape that 2B and other layers can consume, and
2. A small, fingerprint-scoped **routing universe hash artefact** that cryptographically ties together:

   * the zone prior surface,
   * the escalation / mixture policy,
   * the zone floor/bump policy,
   * the 2B day-effect policy (which governs γ-process behaviour), and
   * the final zone allocation egress itself.

Concretely, 3A.S5:

* **Projects S4’s zone-level counts into a cross-layer egress dataset.**
  For each merchant×country×zone triple `(merchant_id=m, country_iso=c, tzid=z)` in the final integer allocation:

  * S5 reads the authoritative integer counts:
    [
    zone_site_count(m,c,z)
    ]
    from `s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}`, where `c` corresponds to `legal_country_iso` and `z ∈ Z(c)` from S2.
  * It optionally derives or copies per-merchant/country totals (e.g. `zone_site_count_sum(m,c)` and `site_count(m,c)`), but it MUST NOT change any counts.
  * It then writes a **zone allocation egress dataset** (`zone_alloc`) in a form suitable for 2B and cross-layer consumers, with:

    * stable primary keys (e.g. `(merchant_id, country_iso, tzid)` per `{seed,fingerprint}`),
    * explicit counts and totals,
    * and embedded lineage to the 3A priors/policies and the universe hash.

  S5 is the **only** 3A state that produces a cross-layer “this is how many outlets merchant *m* has in zone *z* of country *c*” dataset.

* **Computes digests for all configuration surfaces that affect zone allocation and routing.**
  To make 3A’s zone world auditable and to allow 2B and validation to detect any drift, S5 computes canonical digests over:

  * The **zone prior surface** (S2), e.g.
    `zone_alpha_digest = SHA256(canonical_bytes(s2_country_zone_priors@parameter_hash))`.
  * The **zone mixture policy** used in S1 (`zone_mixture_policy_3A`), e.g.
    `theta_digest = SHA256(canonical_bytes(zone_mixture_policy_3A))`.
  * The **zone floor/bump policy** (`zone_floor_policy_3A`), e.g.
    `zone_floor_digest = SHA256(canonical_bytes(zone_floor_policy_3A))`.
  * The 2B **day-effect policy** (`day_effect_policy_v1` or equivalent), e.g.
    `gamma_variance_digest = SHA256(canonical_bytes(day_effect_policy_v1))`.
  * The **zone allocation egress** itself (`zone_alloc`), e.g.
    `zone_alloc_parquet_digest = SHA256(canonical_concat(all files in zone_alloc, in a canonical path order))`.

  These digests are the only sanctioned summary of the configuration and allocation universe that S5 exposes.

* **Publishes a routing universe hash that ties all components together.**
  Using the digests above, S5 constructs a single, fingerprint-scoped **routing universe hash**:

  [
  routing_universe_hash = \mathrm{SHA256}\big(
  zone_alpha_digest ,|, theta_digest ,|, zone_floor_digest ,|, gamma_variance_digest ,|, zone_alloc_parquet_digest
  \big),
  ]

  where `∥` denotes a canonical byte concatenation. S5 then:

  * embeds `routing_universe_hash` (and, where appropriate, its component digests) into a small, fingerprint-scoped artefact (`zone_alloc_universe_hash`), and
  * embeds the same `routing_universe_hash` into each `zone_alloc` row for convenient join-free checks.

  This combined hash is the **only** cross-layer handle that 2B and validation should use to decide “am I looking at the same zone allocation universe (priors + floors + mixture + day-effects + allocation) as the engine used when generating these counts?”.

* **Defines the cross-layer contract for zone allocation, without changing semantics.**
  S5 **does not**:

  * change which merchant×country pairs are escalated (S1’s job),
  * change which zones exist per country or the α-priors (S2’s job),
  * change the sampled zone share vectors (S3’s job),
  * change or re-integerise counts (S4’s job).

  Instead, S5:

  * enforces that `zone_alloc` is a faithful projection of `s4_zone_counts` (and, through that, S1/S2/S3),
  * attaches a well-defined universe hash that encodes **all** inputs relevant to 2B’s routing/day-effect semantics,
  * and publishes both as egress/validation artefacts so that any later component can enforce a strict **“no universe drift”** rule: if any of the priors/policies or allocation change, the hash changes.

* **Remains deterministic and RNG-free.**
  3A.S5 MUST NOT consume any Philox stream, generate random variates, or depend on wall-clock time. Its behaviour is entirely determined by:

  * the sealed inputs and gates from S0 for this `manifest_fingerprint`,
  * the fixed `parameter_hash` (which pins the priors and policies),
  * the S1/S2/S3/S4 outputs for this `{seed, manifest_fingerprint}`, and
  * the Layer-1 catalogue state (paths, schemas, registry entries).

  Given the same inputs and catalogue, re-running S5 MUST produce:

  * byte-identical `zone_alloc`, and
  * byte-identical `zone_alloc_universe_hash` (including `routing_universe_hash` and component digests).

Out of scope for 3A.S5:

* S5 does **not** introduce or alter any new stochastic behaviour; it consumes only already-materialised states.
* S5 does **not** participate in per-arrival routing or day-effect simulation; those are the responsibility of Segment 2B and Layer-2 states that will **consume** `zone_alloc` and `routing_universe_hash`.
* S5 does **not** perform validation over S1–S4 beyond what is needed to ensure that its own artefacts are internally consistent; the full 3A segment-level PASS bundle and any cross-layer “universe sanity” checks are handled by a dedicated validation state that uses S5’s outputs as inputs.

Within these boundaries, 3A.S5’s purpose is to **seal** Segment 3A’s zone allocation into a small, stable set of egress and hash artefacts that downstream systems can trust, and to provide a clear, cryptographic guarantee that “routing and day-effect behaviour” is being applied against exactly the allocation universe that 3A specified.

---

## 2. Preconditions & gated inputs *(Binding)*

This section defines **what MUST already hold** before `3A.S5 — Zone Allocation Egress & Routing Universe Hash` can run, and which gate artefacts it must honour. Anything outside these constraints is **out of scope** for S5.

S5 is **RNG-free** and effectively “end-of-chain”: it only runs once S0–S4 have completed successfully for the relevant run.

---

### 2.1 Layer-1 & segment-level preconditions

Before 3A.S5 is invoked for a given tuple
`(parameter_hash, manifest_fingerprint, seed, run_id)`, the orchestrator MUST ensure:

1. **Layer-1 identity is fixed.**

   * `parameter_hash` (hex64) has already been computed by the Layer-1 parameter resolution logic and identifies a closed governed parameter set 𝓟.
   * `manifest_fingerprint` (hex64) is a valid Layer-1 manifest hash referencing this `parameter_hash` and the same set of sealed artefacts S0 used.
   * `seed` (uint64) is the Layer-1 run seed for this manifest.
   * `run_id` is fixed for this execution and used consistently in run-reporting and, if referenced, in any digest metadata.
   * S5 MUST NOT mutate these identities or derive new ones.

2. **3A.S0 has completed successfully for this `manifest_fingerprint`.**

   * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}` exists and validates against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`.
   * `sealed_inputs_3A@fingerprint={manifest_fingerprint}` exists and validates against `schemas.3A.yaml#/validation/sealed_inputs_3A`.
   * `s0_gate_receipt_3A.upround_gates.segment_1A.status == "PASS"`,
     `segment_1B.status == "PASS"`,
     `segment_2A.status == "PASS"`.
   * If any of these checks fail, S5 MUST treat the run as **invalid** and MUST NOT proceed.

3. **3A.S1–S4 have produced PASS outputs for this run.**

   * `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}` exists, validates, and the S1 run-report row for this `{seed,fingerprint}` has `status = "PASS"`.
   * `s2_country_zone_priors@parameter_hash={parameter_hash}` exists, validates, and the S2 run-report row for this `parameter_hash` has `status = "PASS"`.
   * `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}` exists, validates, and the S3 run-report row for `(parameter_hash, manifest_fingerprint, seed, run_id)` (or equivalent identifier for this run) has `status = "PASS"`.
   * `s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}` exists, validates, and the S4 run-report row for this run has `status = "PASS"`.

   If any of S1–S4 is missing, schema-invalid, or its run-report status is not PASS, S5 MUST NOT run.

4. **2B day-effect policy is sealed in the parameter set.**

   * A day-effect policy artefact (e.g. `day_effect_policy_v1`) that governs 2B’s γ-process MUST:

     * be part of the governed parameter set 𝓟 for this `parameter_hash`,
     * appear in `s0_gate_receipt_3A.sealed_policy_set` with a stable `logical_id`, `schema_ref` and `sha256_hex`,
     * appear in `sealed_inputs_3A` with a matching `path` and `sha256_hex`.
   * Without a sealed day-effect policy, S5 cannot compute a complete routing universe hash, and MUST fail.

---

### 2.2 Gated inputs from 3A.S0 (gate & whitelist)

Although S5 does not consume RNG or raw business data, it still operates under 3A.S0’s gate and whitelist for external artefacts.

1. **Gate descriptor: `s0_gate_receipt_3A` (trust anchor)**
   S5 MUST read `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}` and:

   * confirm upstream gates (1A/1B/2A) are `status="PASS"` as per §2.1;
   * extract IDs and digests for all 3A policy/prior artefacts it will include in the routing universe hash, at least:

     * 3A zone mixture policy (e.g. `zone_mixture_policy_3A`),
     * 3A country→zone prior pack (e.g. `country_zone_alphas_3A`),
     * 3A zone floor/bump policy (e.g. `zone_floor_policy_3A`),
     * 2B day-effect policy (e.g. `day_effect_policy_v1`).

   If `s0_gate_receipt_3A` is missing, invalid, or does not list the policies S5 expects, S5 MUST fail with a precondition/policy error.

2. **Sealed input inventory: `sealed_inputs_3A` (external whitelist)**
   For each **external** artefact used in digest computation, S5 MUST:

   * locate exactly one row in `sealed_inputs_3A@fingerprint={manifest_fingerprint}` with the expected `logical_id` and `path`, and
   * recompute SHA-256 over the artefact bytes and assert equality with `sha256_hex` recorded in that row.

This applies, at minimum, to:

* the zone mixture policy artefact,
* the prior pack artefact,
* the floor/bump policy artefact,
* the day-effect policy artefact,
* any referenced zone-universe or ISO reference if S5 chooses to include them in its digests.

If any required external artefact is missing from `sealed_inputs_3A` or exhibits a digest mismatch, S5 MUST treat this as a sealed-input failure and MUST NOT proceed.

> **Note:** `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares` and `s4_zone_counts` are **internal 3A datasets**, not external references. They are governed via the 3A catalogue and their own state contracts, not via S0’s sealed-input table.

---

### 2.3 3A internal inputs S5 depends on

Within Segment 3A, S5 depends on four internal surfaces, each with a distinct authority role:

1. **`s1_escalation_queue`** — escalation & total counts (for sanity)

   * Used to:

     * confirm the set of merchants and legal countries covered by S4/S3,
     * verify that per-merchant/per-country totals in `zone_alloc` match `site_count(m,c)` for escalated pairs (and, if monolithic countries are also projected, that trivial allocations sum correctly).
   * S5 MUST NOT modify escalation decisions or `site_count`.

2. **`s2_country_zone_priors`** — priors & zone universe (for lineage & digests)

   * Used to:

     * compute `zone_alpha_digest` (digest over the α surface),
     * confirm that `zone_alloc` only includes `(country_iso, tzid)` pairs in the sealed zone universe,
     * propagate prior/floor lineage (IDs/versions) into egress rows.
   * S5 MUST NOT change priors or zone universes; it reads them for digesting and lineage only.

3. **`s3_zone_shares`** — share surface (for structural cross-check, optional)

   * Used to:

     * reaffirm zones present per `(m,c)` and ensure S4’s integer counts were derived from a complete share vector,
     * cross-check that `s4_zone_counts` domain matches `s3_zone_shares` domain.
   * S5 MUST NOT resample or modify shares.

4. **`s4_zone_counts`** — zone integer counts (authority for counts)

   * Used as the **exclusive source** of `zone_site_count(m,c,z)` per `(merchant_id, legal_country_iso, tzid)` when constructing `zone_alloc`.
   * S5 MUST:

     * project these counts into `zone_alloc` without change (modulo field renaming/reformatting),
     * ensure per-pair sums in `zone_alloc` match `zone_site_count_sum(m,c)` and `site_count(m,c)`.
   * S5 MUST NOT re-integerise counts or introduce any new arithmetic beyond straightforward projection and aggregation.

---

### 2.4 Invocation-level assumptions

For a given S5 invocation:

* The orchestrator MUST provide (or allow S5 to resolve):

  * `parameter_hash` (defines which S2 priors and 2B policy apply),
  * `manifest_fingerprint` (defines which sealed inputs and 3A internal surfaces apply),
  * `seed` (for egress partitioning and run lineage),
  * `run_id` (for correlation/run-report).

* S5’s outputs are:

  * `zone_alloc@seed={seed}/fingerprint={manifest_fingerprint}` — cross-layer egress of zone counts, and
  * `zone_alloc_universe_hash@fingerprint={manifest_fingerprint}` (optionally with an embedded `parameter_hash` field) — digest summary and `routing_universe_hash` for this manifest.

S5 MUST be invoked only after S4 has produced a stable `s4_zone_counts` snapshot and the upstream policy/prior configuration has been fully sealed via S0. If any prerequisite is missing or not PASS, S5 MUST not attempt to “patch around” it and MUST fail fast with an appropriate precondition error.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes **exactly what 3A.S5 is allowed to read**, what each input is **authoritative for**, and where S5’s own authority **starts and stops**. Anything outside these inputs, or used beyond the roles defined here, is out of spec for S5.

S5 is purely about **projection and hashing**. It does not introduce new business semantics or RNG.

---

### 3.1 Catalogue & schema packs (shape, not behaviour)

S5 sits under the same Layer-1 catalogue and schema regime as the rest of the engine. It MUST treat the following as **shape/metadata authorities**, not things it can redefine:

1. **Schema packs**

   * `schemas.layer1.yaml` – defines core types (`id64`, `iso2`, `iana_tzid`, `hex64`, `uint64`), validation receipts, and any Layer-1-level egress / validation anchors.
   * `schemas.ingress.layer1.yaml` – shapes for ingress references (e.g. `iso3166_canonical_2024`, `tz_world_2025a`).
   * `schemas.2A.yaml` – shapes of 2A outputs and zone-universe references (e.g. `tz_timetable_cache`).
   * `schemas.3A.yaml` – shapes of 3A internal outputs (`s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`, `s4_zone_counts`) and of S5’s own outputs (`zone_alloc`, `zone_alloc_universe_hash`).

   S5 MAY only use these packs to:

   * validate shapes of inputs/outputs via `schema_ref`, and
   * define its own output shapes.

   S5 MUST NOT:

   * redefine primitive types or RNG envelopes,
   * alter upstream schema semantics,
   * depend on undocumented or “hidden” schema extensions.

2. **Dataset dictionaries & artefact registries**

   * `dataset_dictionary.layer1.{2A,3A}.yaml`
   * `artefact_registry_{2A,3A}.yaml`

   For each dataset/artefact S5 reads or writes, the dictionary/registry is the **only authority** on:

   * logical ID,
   * path template and partition keys,
   * `schema_ref` and format,
   * role (`plan`, `egress`, `validation`, etc.), and
   * lineage (`produced_by`, `consumed_by`).

   S5 MUST resolve locations and schemas through these catalogues only. It MUST NOT:

   * hard-code paths or anchors,
   * “discover” files by scanning directories,
   * write datasets that lack dictionary/registry entries.

3. **3A.S0 outputs (`s0_gate_receipt_3A`, `sealed_inputs_3A`)**

   * `s0_gate_receipt_3A` is S5’s **trust anchor** for:

     * upstream segment gates (1A/1B/2A),
     * which schema/dictionary/registry versions were used,
     * which priors/policies (mixture, priors, floors, day-effect) are in scope for this `manifest_fingerprint`.

   * `sealed_inputs_3A` is S5’s **whitelist of external artefacts**; any external policy/reference used in digest computation MUST appear here with a matching `sha256_hex`.

   S5 MUST NOT:

   * relax upstream gate checks,
   * read external artefacts not present in `sealed_inputs_3A`,
   * change the recorded catalogue/policy versions in `s0_gate_receipt_3A`.

---

### 3.2 3A internal inputs: S1–S4 (business & stochastic authority)

Within Segment 3A, S5 consumes only the final, already-authoritative surfaces. It does not reinterpret or modify them.

#### 3.2.1 `s1_escalation_queue` – merchant×country domain & totals (sanity only)

Dataset:

* `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}`
* Schema: `schemas.3A.yaml#/plan/s1_escalation_queue`.

Authority:

* Defines:

  * full merchant×country domain `D = {(m,c)}`,
  * escalated subset `D_esc = {(m,c) | is_escalated=true}`,
  * total outlet count per pair `site_count(m,c)`.

S5’s allowed use:

* **Sanity and aggregation**:

  * verify that all `(m,c)` pairs with zone allocations in S4/S5 are present and properly classified (`is_escalated`),
  * optionally re-compute or verify merchant-level totals (e.g. sum of `zone_site_count(m,c,·)` equals `site_count(m,c)`),
  * if `zone_alloc` includes per-merchant aggregates, copy `site_count(m,c)` as a total field.

S5 MUST NOT:

* change `is_escalated` values,
* modify or reinterpret `site_count(m,c)`,
* create zone allocations for `(m,c)` not present in S1.

S1 remains the **sole authority** on merchant×country presence and totals.

#### 3.2.2 `s2_country_zone_priors` – zone universe & prior lineage

Dataset:

* `s2_country_zone_priors@parameter_hash={parameter_hash}`
* Schema: `schemas.3A.yaml#/plan/s2_country_zone_priors`.

Authority:

* Defines, for each `country_iso = c`:

  * the zone universe `Z(c) = {tzid}`,
  * prior-related metadata (e.g. `alpha_sum_country(c)`, `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version`).

S5’s allowed use:

* **Structural & lineage checks**:

  * ensure that all zones used in S4/S5 for country `c` are in `Z(c)`,
  * ensure no `tzid` appears in zone allocation that is not in `Z(c)`,
  * copy `prior_pack_id/prior_pack_version` and `floor_policy_id/floor_policy_version` into `zone_alloc` for traceability,
  * compute a canonical digest `zone_alpha_digest` over the S2 surface for inclusion in the universe hash.

S5 MUST NOT:

* change priors or α-values,
* add or drop zones from `Z(c)`,
* use `s2_country_zone_priors` to drive business logic beyond these structural/veracity checks and digesting.

S2 remains the **sole authority** on zone universes and priors.

#### 3.2.3 `s3_zone_shares` – optional structural confirmation

Dataset:

* `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}`
* Schema: `schemas.3A.yaml#/plan/s3_zone_shares`.

Authority:

* For each escalated `(m,c)` and each `z ∈ Z(c)`, contains `share_drawn(m,c,z)` and `share_sum_country(m,c)`.

S5’s allowed use:

* **Optional cross-checks**:

  * confirm that zones present in S4 (`s4_zone_counts`) for `(m,c)` match zones present in S3,
  * cross-validate that domain and lineage are coherent before packaging egress.

S5 MUST NOT:

* resample, alter or “renormalise” shares,
* recompute integer counts from shares (that is S4’s responsibility),
* introduce any business logic based on share magnitudes (S4 is the last place shares matter numerically).

S3 remains the **sole authority** on stochastic realisations.

#### 3.2.4 `s4_zone_counts` – integer counts authority

Dataset:

* `s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}`
* Schema: `schemas.3A.yaml#/plan/s4_zone_counts`.

Authority:

* For each escalated `(m,c)` and `z ∈ Z(c)`, contains:

  * `zone_site_count(m,c,z)` — integer outlet count,
  * `zone_site_count_sum(m,c)` — sum across zones, equal to `site_count(m,c)`.

S5’s allowed use:

* **Projection into egress**:

  * S5 MUST treat `zone_site_count(m,c,z)` as the **sole source of truth** for zone-level counts and MUST copy or aggregate these counts into `zone_alloc` without change (other than any required reshaping).
  * Any consistency checks (e.g. verifying count conservation vs S1) MUST be read-only; failures are S4 bugs or corrupt data and MUST result in S5 failure, not adjustment.

S5 MUST NOT:

* recompute or adjust integer counts,
* attempt its own integerisation or apply additional rounding logic,
* “balance” counts to match expectations if discrepancies are found; it must fail.

S4 is the **sole authority** on zone-level integer counts.

---

### 3.3 2B and other external policies (digest-only authority)

S5 also depends on one or more external policy artefacts that will be incorporated into the routing universe hash but are not otherwise interpreted at the data-plane level.

Within `sealed_inputs_3A` and via the catalogue, S5 MAY read:

1. **Zone mixture policy (`zone_mixture_policy_3A`)**

   * Logical ID: e.g. `"zone_mixture_policy_3A"`.
   * `owner_segment = "3A"`, `role = "zone_mixture_policy"`.
   * `schema_ref` into `schemas.3A.yaml#/policy/zone_mixture_policy_3A`.

   Authority for S5:

   * S5 does **not** apply this policy; S1 already did.
   * S5 uses it only to compute a canonical digest (`theta_digest`) and to record which version of the mixture policy was in effect for this universe.

2. **Country→zone prior pack (`country_zone_alphas_3A`)**

   * Logical ID: e.g. `"country_zone_alphas_3A"`.
   * `owner_segment = "3A"`, `role = "country_zone_alphas"`.
   * `schema_ref` into `schemas.3A.yaml#/policy/country_zone_alphas_v1`.

   Authority for S5:

   * S5 does not interpret α-values afresh; S2 already did.
   * S5 uses this artefact (or the S2 prior surface) to compute `zone_alpha_digest`.

3. **Zone floor/bump policy (`zone_floor_policy_3A`)**

   * Logical ID: e.g. `"zone_floor_policy_3A"`.
   * `owner_segment = "3A"`, `role = "zone_floor_policy"`.
   * `schema_ref` into `schemas.3A.yaml#/policy/zone_floor_policy_v1`.

   Authority for S5:

   * S5 does not apply floors/bump rules; S2 already did.
   * S5 uses this artefact to compute `zone_floor_digest`.

4. **Day-effect policy (`day_effect_policy_v1`)**

   * Logical ID: e.g. `"day_effect_policy_v1"` (owned by 2B governance).
   * `owner_segment = "2B"`; `role = "day_effect_policy"`.
   * `schema_ref` into `schemas.2B.yaml#/policy/day_effect_policy_v1` or similar.

   Authority for S5:

   * S5 does not simulate γ-process day effects; 2B does.
   * S5 uses this artefact to compute `gamma_variance_digest` (or a more general `day_effect_digest`) for inclusion in the routing universe hash.

For all these artefacts:

* S5 MUST treat them as **opaque bytes** for hashing and versioning; it does not apply business logic beyond validating them against their schemas.
* S5 MUST fail if any expected artefact is missing or its digest cannot be reconciled with `sealed_inputs_3A` and/or the catalogue.

---

### 3.4 S5’s own authority vs upstream & downstream

S5’s **only new authority surfaces** are:

1. The **zone allocation egress** dataset (`zone_alloc`), which is a *projection* of S4’s zone counts into a cross-layer shape, and
2. The **routing universe hash** artefact (`zone_alloc_universe_hash`), which encodes a canonical digest over:

   * S2’s prior surface or pack (`zone_alpha_digest`),
   * S1’s mixture policy (`theta_digest`),
   * S2’s floor policy (`zone_floor_digest`),
   * the day-effect policy (`gamma_variance_digest`),
   * and the `zone_alloc` egress (`zone_alloc_parquet_digest`),
     making a single `routing_universe_hash`.

Within those boundaries:

* S5 **owns**:

  * the exact shape and content of `zone_alloc`, insofar as it embeds counts and lineage correctly,
  * the computation and publication of the component digests and the combined `routing_universe_hash`.

* S5 explicitly does **not** own:

  * which merchants or countries/zones exist (`D_esc`, `Z(c)`),
  * how many outlets each merchant has in each country (`site_count`),
  * how shares were drawn or integerised,
  * the semantics of priors, floors, mixture, or day-effect parameters.

Downstream:

* 2B and validation MUST use `zone_alloc` and `zone_alloc_universe_hash` to enforce **“no universe drift”**:

  * If any of S2/S1/S2/S2/zone_alloc changes, `routing_universe_hash` changes.
  * 2B’s routing/day-effect logic MUST check this hash (and, if desired, its components) and treat mismatches as a configuration error.

---

### 3.5 Explicit “MUST NOT” list for S5

To keep the authority boundaries strict, S5 is explicitly forbidden from:

* **Changing any counts or shares**

  * MUST NOT modify `zone_site_count(m,c,z)` from S4;
  * MUST NOT recompute or adjust `share_drawn(m,c,z)` from S3;
  * MUST NOT re-integerise or redistribute counts.

* **Re-applying priors or mixture/day-effect logic**

  * MUST NOT re-run mixture policy decisions over `(m,c)`;
  * MUST NOT re-apply α/floor policies or day-effect logic;
  * MUST NOT infer any new α or γ parameters beyond what S2/2B define and seal.

* **Consuming RNG or wall-clock**

  * MUST NOT draw any RNG;
  * MUST NOT use system time in hash inputs or field values (timestamps in logs/run-report may be provided by the orchestrator but must not affect any digests).

* **Reading unsealed external artefacts**

  * MUST NOT read/configure from environment variables, local files, or catalogued artefacts not present in `sealed_inputs_3A` for this `manifest_fingerprint`.

Within these constraints, S5’s inputs and authority are tightly scoped: it trusts S1–S4 for all business semantics and counts, treats priors/policies as opaque for digesting, and contributes only **projection and hashing** to produce the final zone allocation egress and routing universe hash.

---

## 4. Outputs (datasets) & identity *(Binding)*

3A.S5 produces **two** persistent artefacts:

1. A **zone allocation egress dataset** that exposes zone-level counts per merchant×country×zone in a cross-layer-friendly shape.
2. A **routing universe hash artefact** that ties together all configuration and allocation surfaces relevant to zone-aware routing and day effects.

S5 is **not** allowed to change any counts or shares; it only reshapes and seals what S4 (and upstream) have already established.

---

### 4.1 Overview of S5 outputs

For a given run `{seed, manifest_fingerprint}` under `parameter_hash`, S5 MUST produce at most one instance of:

1. **`zone_alloc`** (dataset)

   * Seed+fingerprint-scoped table.
   * One row per `(merchant_id, legal_country_iso, tzid)` for every **escalated** merchant×country×zone triple in `s4_zone_counts`.
   * Contains:

     * integer outlet count per zone,
     * per-merchant×country totals,
     * lineage to priors/policies,
     * the **routing_universe_hash** for this manifest.

2. **`zone_alloc_universe_hash`** (digest/summary artefact)

   * Fingerprint-scoped (optionally also keyed by `parameter_hash`).
   * Single-row (or a small set of rows) describing:

     * digests over the key configuration surfaces: S2 priors, S1 mixture policy, S2 floor policy, 2B day-effect policy, `zone_alloc` egress,
     * the combined `routing_universe_hash` computed from these digests.

These are the only outputs owned by S5 in this contract version.

> **Note:** In this version, `zone_alloc` covers **only escalated merchant×country pairs**. Non-escalated (“monolithic”) pairs remain represented implicitly by S1 + 2A + 2B as single-zone merchants. Explicit inclusion of monolithic pairs in `zone_alloc` is a potential future extension (see Change Control).

---

### 4.2 `zone_alloc` — zone allocation egress

#### 4.2.1 Domain & identity

For the given `{seed, manifest_fingerprint}`:

* From S1:

  * `D` = all `(merchant_id, legal_country_iso)` with outlets.
  * `D_esc` = `{ (m,c) ∈ D | is_escalated(m,c) = true }`.

* From S2, for each `c`:

  * `Z(c)` = `{ tzid | (country_iso=c, tzid) ∈ s2_country_zone_priors }`.

From S4:

* For each `(m,c) ∈ D_esc` and `z ∈ Z(c)`, S4 has `zone_site_count(m,c,z)`.

The **intended domain** of `zone_alloc` is exactly the S4 domain:

[
D_{\text{zone_alloc}} = { (m,c,z) \mid (m,c) \in D_{\text{esc}},\ z \in Z(c)}.
]

Binding requirements:

* For each `(m,c) ∈ D_esc` and `z ∈ Z(c)`, S5 MUST create **exactly one** row in `zone_alloc` with:

  * `merchant_id = m`,
  * `legal_country_iso = c`,
  * `tzid = z`.

* S5 MUST NOT create rows for:

  * any `(m,c)` where `is_escalated = false` or `(m,c) ∉ D`, or
  * any `tzid` not in `Z(c)` for that `legal_country_iso`.

**Logical primary key** within a `{seed, manifest_fingerprint}` partition:

[
PK = (\text{merchant_id},\ \text{legal_country_iso},\ \text{tzid})
]

No duplicates of this triple are permitted.

#### 4.2.2 Partitioning & path

` zone_alloc` is a **run-scoped** egress dataset.

* Partition keys:

  ```text
  ["seed", "fingerprint"]
  ```

* Conceptual path template (finalised in the dataset dictionary):

  ```text
  data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/...
  ```

Binding rules:

* For each partition:

  * The path MUST contain `seed=<uint64>` and `fingerprint=<hex64>`.
  * There MUST be at most one `zone_alloc` partition per `{seed, manifest_fingerprint}`.

* **Path↔embed equality:**

  * Every row MUST have `seed` equal to the `seed` path token, and
  * `fingerprint` equal to the `fingerprint` path token (this value carries the run’s `manifest_fingerprint`).

Any mismatch is a schema/validation error.

#### 4.2.3 Required columns & semantics

Each row in `zone_alloc` MUST contain at minimum:

**Lineage / partitions**

* `seed` — `uint64`, as above.
* `fingerprint` — `hex64`; equal to the manifest fingerprint for this run.

**Identity**

* `merchant_id` — `id64`.
* `legal_country_iso` — `iso2`; MUST be a valid ISO country, consistent with S1/S2/S3/S4.
* `tzid` — `iana_tzid`; MUST be in `Z(legal_country_iso)` from S2.

**Counts**

* `zone_site_count`

  * Type: integer (`minimum: 1`).
  * MUST equal `zone_site_count(m,c,z)` from `s4_zone_counts` for the same `(seed, fingerprint, merchant_id, legal_country_iso, tzid)`.

* `zone_site_count_sum`

  * Type: integer (`minimum: 1`).
  * For all rows with the same `(merchant_id, legal_country_iso)`, this value MUST be identical and satisfy:
    [
    zone_site_count_sum(m,c) = \sum_{z \in Z(c)} zone_site_count(m,c,z) = site_count(m,c).
    ]

Optionally (for convenience and consistency):

* `site_count` — integer total outlets per `(m,c)`, copied from S1; MUST equal `zone_site_count_sum(m,c)` and inherit its `minimum: 1`.

**Lineage (priors & policies)**

* `prior_pack_id`, `prior_pack_version` — strings; MUST match S2 lineage.
* `floor_policy_id`, `floor_policy_version` — strings; MUST match S2 lineage.
* `mixture_policy_id`, `mixture_policy_version` — strings; identify the S1 mixture policy used (from S0/sealed policies).
* `day_effect_policy_id`, `day_effect_policy_version` — strings; identify the 2B day-effect policy used (from S0/sealed policies).

All lineage fields MUST be constant across all rows in a `{seed,fingerprint}` partition for a given `parameter_hash`.

**Routing universe hash**

* `routing_universe_hash`

  * Type: `string`, representing a `hex64` or longer SHA-256 hash.
  * MUST be identical across all rows in the partition and equal to the `routing_universe_hash` computed and published in `zone_alloc_universe_hash` (see 4.3).
  * Serves as the primary cross-layer handle for “what universe are these allocations part of?”.

Additional diagnostic fields MAY be added in later versions (see Change Control), but MUST NOT alter the meaning of the required fields.

#### 4.2.4 Writer-sort & immutability

Within each `{seed, manifest_fingerprint}` partition, S5 MUST write `zone_alloc` rows in a deterministic order, e.g.:

1. `merchant_id` ascending,
2. `legal_country_iso` ascending,
3. `tzid` ascending.

Ordering is **not** semantically meaningful; all semantics derive from keys and values. Ordering exists only to guarantee:

* re-running S5 with the same inputs produces **byte-identical** output.

Once `zone_alloc` is written for a given `{seed, manifest_fingerprint}`:

* It MUST be treated as a **snapshot**.
* If S5 is re-run with the same inputs:

  * and the newly computed rows (normalised & sorted) are identical to the existing dataset → S5 MAY skip writing or re-write identical bytes;
  * if they differ → S5 MUST NOT overwrite and MUST signal an immutability violation.

---

### 4.3 `zone_alloc_universe_hash` — routing universe digest artefact

#### 4.3.1 Identity & scope

` zone_alloc_universe_hash` is a **fingerprint-scoped** (optionally parameter-scoped) small artefact that summarises all configuration and allocation digests for this manifest.

* Scope: one row per `manifest_fingerprint` (potentially also storing `parameter_hash` as a column).
* Logical identity:

  * `manifest_fingerprint`
  * optionally `parameter_hash` if multiple parameter sets can share a manifest.

#### 4.3.2 Partitioning & path

* Partition keys:

  * Minimum: `["fingerprint"]`.
  * Optionally `["parameter_hash","fingerprint"]` if required by catalogue conventions.

* Conceptual path template (fingerprint-only case):

  ```text
  data/layer1/3A/zone_universe/fingerprint={manifest_fingerprint}/zone_universe_hash.json
  ```

Binding rules:

* For each `manifest_fingerprint`, there MUST be at most one `zone_alloc_universe_hash` artefact at the configured path.
* The embedded `manifest_fingerprint` field in the JSON MUST equal the `{fingerprint}` token.

#### 4.3.3 Required fields & semantics

The JSON object (or single-row table) MUST contain at minimum:

* `manifest_fingerprint` — `hex64`; identifies the manifest.
* `parameter_hash` — `hex64`; identifies the parameter set 𝓟.

**Component digests**:

* `zone_alpha_digest`

  * Type: `string`, `hex64` (or longer).
  * SHA-256 digest over a canonical representation of the S2 prior surface or prior pack (as defined in §6).

* `theta_digest`

  * Digest over the S1 mixture policy artefact (`zone_mixture_policy_3A`), canonical representation.

* `zone_floor_digest`

  * Digest over the zone floor/bump policy artefact (`zone_floor_policy_3A`), canonical representation.

* `day_effect_digest` (or `gamma_variance_digest`)

  * Digest over the day-effect policy artefact used by 2B (e.g. `day_effect_policy_v1`).

* `zone_alloc_parquet_digest`

  * Digest over the `zone_alloc` egress dataset for this `{seed,fingerprint}`:

    * computed as SHA-256 of a canonical concatenation of the data files listed in a small index (e.g. `index.json`) in lexicographic path order.

**Combined routing hash**:

* `routing_universe_hash`

  * Type: `string`, `hex64` (or larger).

  * MUST be the SHA-256 of the canonical concatenation of the component digests above, in a defined order, e.g.:

    ```text
    routing_universe_hash = SHA256(
      zone_alpha_digest || theta_digest || zone_floor_digest || day_effect_digest || zone_alloc_parquet_digest
    )
    ```

  * This value MUST be identical to the `routing_universe_hash` field embedded in each row of `zone_alloc` for this `{seed,fingerprint}`.

**Optional metadata**:

* `version` — version of this universe-hash schema.
* `created_at_utc` — timestamp for audit (MUST NOT affect digest content).
* `notes` — free-text for human diagnostics.

No other fields are required; extra fields may be added in future versions as long as they do not alter the semantics of the digests or combined hash.

#### 4.3.4 Immutability

Once `zone_alloc_universe_hash` has been written for a given `manifest_fingerprint`:

* It MUST never be changed.
* Recomputing digests under the same inputs MUST yield the same JSON object; any discrepancy indicates either data corruption or a change in upstream artefacts that was not accompanied by a new `manifest_fingerprint`/`parameter_hash`.

---

### 4.4 Consumers & authority of S5 outputs

**`zone_alloc`**:

* **Required consumers:**

  * Segment 2B (routing & day-effect logic):

    * reads `zone_alloc` as the cross-layer source of long-run zone allocations per merchant×country×zone,
    * uses `routing_universe_hash` (and optionally the component digests) to enforce that the routing/day-effect configuration it is using matches the allocation universe.
  * 3A/Layer-1 validation:

    * uses `zone_alloc` to cross-check that S4’s counts were projected correctly and to validate `zone_alloc_parquet_digest`.

**`zone_alloc_universe_hash`**:

* **Required consumers:**

  * 2B:

    * reads `routing_universe_hash` (and/or component digests) to verify that its own priors/floor/day-effect policies and `zone_alloc` match the universe it expects;
    * MUST treat any mismatch as a configuration error (“universe drift”) and fail fast or refuse to use the allocation.
  * 3A/Layer-1 validation:

    * recomputes the component digests and combined hash from the actual artefacts and compares to this record.

Neither `zone_alloc` nor `zone_alloc_universe_hash` may be treated as mutable. They are the **terminal authority surfaces** for Segment 3A’s contribution to zone-aware routing: once written and validated, any change in priors, mixture, floors, day-effect policy, or zone allocation MUST surface as a change in the component digests and thus the `routing_universe_hash`.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes the **shape and placement** of 3A.S5’s outputs in the Layer-1 authority chain:

* the JSON-Schema anchors that define their structure,
* the dataset dictionary entries that define their IDs, paths and partitions, and
* the artefact registry entries that bind them into the manifest.

Everything here is **normative** for:

* the zone allocation egress dataset: `zone_alloc`, and
* the routing universe hash artefact: `zone_alloc_universe_hash`.

---

### 5.1 Segment schema pack for S5

S5 uses the existing Segment-3A schema pack:

* **Schema pack ID:** `schemas.3A.yaml`
* **Role:** shape authority for all Segment-3A datasets (S0–S5).

`schemas.3A.yaml` MUST:

1. Reuse Layer-1 primitives via `$ref: "schemas.layer1.yaml#/$defs/…"`, including:

   * `id64`, `iso2`, `iana_tzid`, `hex64`, `uint64`, `rfc3339_micros`, etc.
2. Define two new anchors:

   * `#/egress/zone_alloc` — for the **zone allocation egress** rows.
   * `#/validation/zone_alloc_universe_hash` — for the **routing universe hash** artefact.

No other schema pack may define the shapes of these artefacts.

---

### 5.2 Schema anchor: `schemas.3A.yaml#/egress/zone_alloc`

This anchor defines the **row shape** of the `zone_alloc` dataset.

At minimum, it MUST enforce:

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

  * `tzid`

    * `$ref: "schemas.layer1.yaml#/$defs/iana_tzid"`

  * `zone_site_count`

    * `type: "integer"`
    * `minimum: 1`

  * `zone_site_count_sum`

    * `type: "integer"`
    * `minimum: 1`

  * `site_count`

    * `type: "integer"`
    * `minimum: 1`

  * `prior_pack_id`

    * `type: "string"`

  * `prior_pack_version`

    * `type: "string"`

  * `floor_policy_id`

    * `type: "string"`

  * `floor_policy_version`

    * `type: "string"`

  * `mixture_policy_id`

    * `type: "string"`

  * `mixture_policy_version`

    * `type: "string"`

  * `day_effect_policy_id`

    * `type: "string"`

  * `day_effect_policy_version`

    * `type: "string"`

  * `routing_universe_hash`

    * `type: "string"`
    * SHOULD be constrained to a hex digest pattern (e.g. 64/128 lowercase hex chars) via a regex or `$ref` to a `hex64`/`hex128`-like `$defs` entry.

* **Optional properties (diagnostic / convenience):**

  * `alpha_sum_country`

    * `type: "number"`
    * `exclusiveMinimum: 0.0`
    * copy of S2’s `alpha_sum_country(c)` if you choose to surface it.

  * `notes`

    * `type: "string"` — free-text diagnostics.

  * Other diagnostic fields MAY be added in future versions (per §12) provided they do not change the semantics of the required fields.

* **Additional properties:**

  * At the top level, the schema MUST set:

    ```yaml
    additionalProperties: false
    ```

    to prevent accidental shape drift.

Every row that S5 writes to `zone_alloc` MUST validate against this anchor.

---

### 5.3 Schema anchor: `schemas.3A.yaml#/validation/zone_alloc_universe_hash`

This anchor defines the shape of the small, fingerprint-scoped **universe hash** artefact.

It is a single-row (or logically single-row) `object` with:

* **Type:** `object`

* **Required properties:**

  * `manifest_fingerprint`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `parameter_hash`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `zone_alpha_digest`

    * `type: "string"` — hex SHA-256 digest of S2’s prior surface/pack.

  * `theta_digest`

    * `type: "string"` — hex SHA-256 digest of S1’s mixture policy artefact.

  * `zone_floor_digest`

    * `type: "string"` — hex SHA-256 digest of the floor/bump policy artefact.

  * `day_effect_digest`

    * `type: "string"` — hex SHA-256 digest of the day-effect policy artefact (e.g. `day_effect_policy_v1`).

  * `zone_alloc_parquet_digest`

    * `type: "string"` — hex SHA-256 digest of the canonical concatenation of `zone_alloc` data files for this `{seed,fingerprint}` (as defined in the algorithm section).

  * `routing_universe_hash`

    * `type: "string"` — combined SHA-256 digest over the concatenation of the component digests above, in the specified order.

* **Optional properties:**

  * `version`

    * `type: "string"` — version of this summary schema (e.g. `"1.0.0"`).

  * `created_at_utc`

    * `$ref: "schemas.layer1.yaml#/$defs/rfc3339_micros"` (for audit/debug only; MUST NOT feed into digest computation).

  * `notes`

    * `type: "string"` — free-text diagnostics.

* **Additional properties:**

  * MUST set `additionalProperties: false` for the top-level object.

This anchor MUST be used as the `schema_ref` for the universe-hash dataset in the dictionary.

---

### 5.4 Dataset dictionary entries: `dataset_dictionary.layer1.3A.yaml`

The 3A dataset dictionary MUST declare two datasets: `zone_alloc` and `zone_alloc_universe_hash`.

#### 5.4.1 `zone_alloc` dataset entry

```yaml
datasets:
  - id: zone_alloc
    owner_subsegment: 3A
    description: Cross-layer zone allocation egress for routing segment.
    version: '{seed}.{manifest_fingerprint}'
    format: parquet
    path: data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    ordering: [merchant_id, legal_country_iso, tzid]
    schema_ref: schemas.3A.yaml#/egress/zone_alloc
    lineage:
      produced_by: 3A.S5
      consumed_by: [2B, validation, cross_segment_validation]
    final_in_layer: true
    pii: false
    licence: Proprietary-Internal
```

Binding points:

* `id` MUST be `zone_alloc` with `owner_subsegment: 3A`.
* `path` MUST include `seed={seed}` and `fingerprint={manifest_fingerprint}`, and no other partition tokens.
* `partitioning` MUST be exactly `[seed, fingerprint]`.
* `schema_ref` MUST be `schemas.3A.yaml#/egress/zone_alloc`.
* `ordering` expresses the writer-sort key; consumers MUST NOT infer additional semantics from file order.

#### 5.4.2 `zone_alloc_universe_hash` dataset entry

```yaml
datasets:
  - id: zone_alloc_universe_hash
    owner_subsegment: 3A
    description: Fingerprint-scoped summary tying priors/policies to the published zone allocation.
    version: '{manifest_fingerprint}'
    format: json
    path: data/layer1/3A/zone_universe/fingerprint={manifest_fingerprint}/zone_alloc_universe_hash.json
    partitioning: [fingerprint]
    ordering: []
    schema_ref: schemas.3A.yaml#/validation/zone_alloc_universe_hash
    lineage:
      produced_by: 3A.S5
      consumed_by: [2B, validation]
    final_in_layer: false
    pii: false
    licence: Proprietary-Internal
```

Binding points:

* `id` MUST be `zone_alloc_universe_hash`.
* `path` MUST include `fingerprint={manifest_fingerprint}` as the only partition token.
* `partitioning` MUST be exactly `[fingerprint]`.
* `schema_ref` MUST be `schemas.3A.yaml#/validation/zone_alloc_universe_hash`.
* `ordering` MAY be an empty list or omitted; there is logically one row per fingerprint.

---

### 5.5 Artefact registry entries: `artefact_registry_3A.yaml`

For each manifest (`manifest_fingerprint`), the 3A artefact registry MUST register both S5 artefacts.

#### 5.5.1 `zone_alloc` artefact entry

```yaml
- manifest_key: "mlr.3A.zone_alloc"
  name: "Segment 3A zone allocation egress"
  subsegment: "3A"
  type: "dataset"
  category: "plan"
  path: "data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/"
  schema: "schemas.3A.yaml#/egress/zone_alloc"
  semver: "1.0.0"
  version: "{seed}.{manifest_fingerprint}"
  digest: "<sha256_hex>"
  dependencies:
    - "mlr.3A.s4.zone_counts"
    - "mlr.3A.zone_alloc_universe_hash"
  source: "internal"
  owner: {owner_team: "mlr-3a-core"}
  cross_layer: true
```

Binding requirements:

* `manifest_key` MUST be `"mlr.3A.zone_alloc"`.
* `path` and `schema` MUST match the dictionary entry.
* `version` MUST equal `{seed}.{manifest_fingerprint}`.
* `dependencies` MUST include `s4.zone_counts` and the paired `zone_alloc_universe_hash`; new dependencies MUST be reflected in both registry and spec before sealing a manifest.

#### 5.5.2 `zone_alloc_universe_hash` artefact entry

```yaml
- manifest_key: "mlr.3A.zone_alloc_universe_hash"
  name: "Segment 3A routing universe hash (zone allocation)"
  subsegment: "3A"
  type: "dataset"
  category: "validation"
  path: "data/layer1/3A/zone_universe/fingerprint={manifest_fingerprint}/zone_alloc_universe_hash.json"
  schema: "schemas.3A.yaml#/validation/zone_alloc_universe_hash"
  semver: "1.0.0"
  version: "{manifest_fingerprint}"
  digest: "<sha256_hex>"
  dependencies:
    - "mlr.3A.country_zone_alphas"
    - "mlr.3A.zone_mixture_policy"
    - "mlr.3A.zone_floor_policy"
    - "mlr.2B.policy.day_effect_v1"
    - "mlr.3A.zone_alloc"
  source: "internal"
  owner: {owner_team: "mlr-3a-core"}
  cross_layer: true
```

Binding requirements:

* `manifest_key` MUST be `"mlr.3A.zone_alloc_universe_hash"`.
* `dependencies` MUST include each artefact whose digest appears in the JSON (prior pack, mixture policy, floor policy, day-effect policy, and the `zone_alloc` output). Additional components require updating this entry and the spec.
* `digest` for this artefact is the SHA-256 of the JSON body; the component digests inside it must be validated by recomputing them from the listed artefacts.

---

### 5.6 No additional S5 datasets in this version

Under this version of the contract:

* 3A.S5 MUST NOT register or emit any outputs other than `zone_alloc` and `zone_alloc_universe_hash`.

If additional S5 surfaces are needed in future (e.g. a more detailed per-policy digest table or a per-merchant universe summary), they MUST be introduced via:

1. New schema anchors in `schemas.3A.yaml`.
2. New dataset entries in `dataset_dictionary.layer1.3A.yaml` with their own IDs, paths and partitioning.
3. Corresponding entries in `artefact_registry_3A.yaml` with clear `manifest_key`, `schema`, `dependencies` and roles.

Until such changes are made (and versioned per §12), the shapes and catalogue links in this section are the **only** valid definitions of S5’s outputs.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section defines the **exact behaviour** of `3A.S5 — Zone Allocation Egress & Routing Universe Hash`.

The algorithm is:

* **RNG-free** (no Philox, no other RNG),
* **deterministic** given `(parameter_hash, manifest_fingerprint, seed, run_id)` and the catalogue, and
* **idempotent** (re-running S5 with unchanged inputs produces byte-identical outputs).

S5 never changes counts or shares; it only:

1. Projects `s4_zone_counts` into the `zone_alloc` egress shape.
2. Computes digests over relevant inputs and `zone_alloc`.
3. Writes the `zone_alloc` dataset and the `zone_alloc_universe_hash` artefact, enforcing immutability.

---

### 6.1 Phase overview

For a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, S5 executes:

1. **Resolve S0/S1/S2/S3/S4 & catalogue** — confirm all prerequisites and load metadata.
2. **Construct `zone_alloc` rows** from `s4_zone_counts` (plus S1/S2 lineage).
3. **Write `zone_alloc` in a canonical, sorted form** and compute its digest.
4. **Compute component digests** for priors/policies and build `routing_universe_hash`.
5. **Write `zone_alloc_universe_hash`** and enforce immutability for both artefacts.

No step may depend on wall-clock time or non-deterministic sources.

---

### 6.2 Phase 1 — Resolve prerequisites & catalogue

**Step 1 – Fix run identity**

S5 is invoked with:

* `parameter_hash` (hex64),
* `manifest_fingerprint` (hex64),
* `seed` (uint64),
* `run_id` (string or u128-encoded).

S5 MUST:

* validate these formats,
* treat them as immutable for the duration of the run.

**Step 2 – Load S0 artefacts**

Using the 3A dictionary/registry, S5 resolves and reads:

* `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`,
* `sealed_inputs_3A@fingerprint={manifest_fingerprint}`.

S5 MUST:

* validate `s0_gate_receipt_3A` against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`,
* validate `sealed_inputs_3A` against `schemas.3A.yaml#/validation/sealed_inputs_3A`,
* assert `segment_1A/1B/2A.status == "PASS"` in `upstream_gates`.

Failure at this step ⇒ S5 FAIL; no outputs may be written.

**Step 3 – Load S1–S4 datasets**

Using the 3A dataset dictionary and registries, S5 resolves and reads:

* `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}`
  (`schema_ref: schemas.3A.yaml#/plan/s1_escalation_queue`),
* `s2_country_zone_priors@parameter_hash={parameter_hash}`
  (`schema_ref: schemas.3A.yaml#/plan/s2_country_zone_priors`),
* `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}`
  (`schema_ref: schemas.3A.yaml#/plan/s3_zone_shares`),
* `s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}`
  (`schema_ref: schemas.3A.yaml#/plan/s4_zone_counts`).

S5 MUST validate each dataset against its schema. Any schema failure, or absence of a required dataset, is an `E3A_S4/S5_001_PRECONDITION_FAILED` and S5 MUST NOT proceed.

**Step 4 – Confirm upstream PASS status**

S5 MUST consult the 3A segment-state run-report (as defined in S1–S4) and assert that:

* S1 `status="PASS"` for this `{seed,fingerprint}`,
* S2 `status="PASS"` for this `parameter_hash`,
* S3 `status="PASS"` for this `(parameter_hash, manifest_fingerprint, seed, run_id)` (or equivalent identifier),
* S4 `status="PASS"` for this `(parameter_hash, manifest_fingerprint, seed, run_id)`.

If any status is not `PASS`, S5 MUST fail with a precondition error.

**Step 5 – Resolve external policy/prior artefacts**

Using `s0_gate_receipt_3A.sealed_policy_set` and `sealed_inputs_3A`, S5 MUST locate and validate:

* 3A zone mixture policy artefact (e.g. `zone_mixture_policy_3A`) — obtain `logical_id`, `path`, `schema_ref`.
* 3A prior pack artefact (e.g. `country_zone_alphas_3A`).
* 3A floor/bump policy artefact (e.g. `zone_floor_policy_3A`).
* 2B day-effect policy artefact (e.g. `day_effect_policy_v1`).

For each:

* ensure it has a row in `sealed_inputs_3A` (matching `logical_id` and `path`),
* read its bytes,
* validate against its `schema_ref`,
* recompute SHA-256 digest and assert equality with `sha256_hex` in `sealed_inputs_3A`.

Any missing artefact or digest mismatch ⇒ S5 FAIL with a sealed-input/policy error.

**Step 6 – Load catalogue artefacts**

S5 MUST also load and validate:

* `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml`,
* `dataset_dictionary.layer1.3A.yaml`,
* `artefact_registry_3A.yaml`.

Any malformed or missing catalogue artefact S5 depends on ⇒ `E3A_S5_002_CATALOGUE_MALFORMED`.

---

### 6.3 Phase 2 — Construct `zone_alloc` rows from `s4_zone_counts`

**Step 7 – Derive domain consistency**

From `s1_escalation_queue`:

* Compute:

  * `D = { (m,c) }` — all `(merchant_id, legal_country_iso)`.
  * `D_esc = { (m,c) ∈ D | is_escalated(m,c) = true }`.

From `s2_country_zone_priors`:

* For each `country_iso = c` in `D_esc`, compute:

  * `Z(c) = { tzid | (country_iso=c, tzid) in s2_country_zone_priors }`.

From `s4_zone_counts`:

* For each row, read `(merchant_id, legal_country_iso, tzid, zone_site_count, zone_site_count_sum, share_sum_country, prior lineage)`.

S5 MUST assert:

* Projection of S4 onto `(m,c)` equals `D_esc`.
* For each `(m,c)`, the set of `tzid` in S4 equals `Z(c)`.
* For each `(m,c)`, `zone_site_count_sum(m,c) = Σ_z zone_site_count(m,c,z) = site_count(m,c)` from S1.

Any mismatch indicates a bug or data corruption in S1–S4 and MUST yield an S4/S5 domain or conservation error (not corrected in S5).

**Step 8 – Build `zone_alloc` row skeletons**

For each row `(m,c,z)` in `s4_zone_counts@{seed,fingerprint}`:

* Construct a corresponding `zone_alloc` row with:

  * `seed` = run’s `seed`,
  * `manifest_fingerprint` = run’s `manifest_fingerprint`,
  * `merchant_id` = `m`,
  * `legal_country_iso` = `c`,
  * `tzid` = `z`,
  * `zone_site_count` = `zone_site_count(m,c,z)` from S4,
  * `zone_site_count_sum` = `zone_site_count_sum(m,c)` from S4,
  * `site_count` = `site_count(m,c)` from S1 (MUST equal `zone_site_count_sum(m,c)`),
  * `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version` = values from S2 lineage (constant per `parameter_hash`),
  * `mixture_policy_id`, `mixture_policy_version` = from mixture policy artefact resolved in Step 5,
  * `day_effect_policy_id`, `day_effect_policy_version` = from day-effect policy artefact resolved in Step 5,
  * `routing_universe_hash` left unset for now (to be filled after digest computation).

Optional fields (if present in the schema), such as `alpha_sum_country`, may be copied from S2/S4 for the appropriate `country_iso`.

This builds an in-memory or streamed representation of the `zone_alloc` rows, without changing any counts.

---

### 6.4 Phase 3 — Write `zone_alloc` and compute `zone_alloc_parquet_digest`

**Step 9 – Determine target path & writer-sort**

Using the dictionary entry for `zone_alloc`:

* Compute the target directory:
  `data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/`.

* Inside this partition, S5 MUST sort the row set by:

  1. `merchant_id` ascending,
  2. `legal_country_iso` ascending,
  3. `tzid` ascending.

This sorted order is the **canonical writer-sort** for both correctness and digest computation.

**Step 10 – Idempotent write & digest**

S5 MUST:

1. Check if `zone_alloc` already exists at the target path.

   * If it does not exist:

     * Write the sorted `zone_alloc` rows to Parquet files in the target directory, ensuring:

       * only data files under that path are part of this dataset,
       * non-data files (e.g. `_SUCCESS`, logs) are either not written or excluded from digest computation.

   * If it does exist:

     * Read the existing dataset, normalise it to the same schema and writer-sort,
     * Compare row-for-row and field-for-field with the newly constructed rows.
     * If identical:

       * S5 MAY choose to reuse the existing files and their digest, **but MUST** confirm that the stored `zone_alloc_parquet_digest` (if previously computed) still matches the bytes on disk.
     * If different:

       * S5 MUST NOT overwrite; raise `E3A_S5_007_IMMUTABILITY_VIOLATION` and FAIL.

2. Compute `zone_alloc_parquet_digest` as follows (canonical digest):

   * Enumerate all Parquet data files under the target directory (excluding non-data markers and versioning metadata),
   * Sort their relative paths in **ASCII lexicographic** order,
   * Concatenate their raw bytes in that order into a conceptual byte stream,
   * Compute `zone_alloc_parquet_digest = SHA-256(concatenated_bytes)`, encoded as a lowercase hex string.

S5 MUST hold this digest value in memory for later use; it is also stored in `zone_alloc_universe_hash`.

---

### 6.5 Phase 4 — Compute component digests & `routing_universe_hash`

**Step 11 – Compute `zone_alpha_digest`**

S5 MUST choose and document a canonical basis for this digest; in this version:

* Basis: the S2 prior surface `s2_country_zone_priors@parameter_hash`.

Procedure:

* Enumerate all data files of `s2_country_zone_priors` under `parameter_hash={parameter_hash}` as resolved by the dictionary/registry.
* Sort relative paths ASCII-lexicographically.
* Concatenate raw file bytes in that order.
* Compute `zone_alpha_digest = SHA-256(concatenated_bytes)` as lowercase hex.

**Step 12 – Compute `theta_digest` (mixture policy)**

From the mixture policy artefact (e.g. `zone_mixture_policy_3A`):

* Using the `path` resolved via the catalogue and verified against `sealed_inputs_3A`, read the raw bytes exactly as stored (e.g. YAML/JSON).
* Compute `theta_digest = SHA-256(file_bytes)` as lowercase hex.

No re-serialisation or pretty-printing; the on-disk bytes are the canonical representation.

**Step 13 – Compute `zone_floor_digest` (floor/bump policy)**

From the floor/bump policy artefact (e.g. `zone_floor_policy_3A`):

* Read raw bytes as stored at the sealed path.
* Compute `zone_floor_digest = SHA-256(file_bytes)` as lowercase hex.

**Step 14 – Compute `day_effect_digest` (day-effect policy)**

From the day-effect policy artefact (e.g. `day_effect_policy_v1`):

* Read raw bytes as stored.
* Compute `day_effect_digest = SHA-256(file_bytes)` as lowercase hex.

**Step 15 – Derive `routing_universe_hash`**

S5 MUST define the exact concatenation order of component digests. In this version:

* Concatenate the raw bytes of the hex-encoded digests in this order:

  ```text
  concat = zone_alpha_digest
           || theta_digest
           || zone_floor_digest
           || day_effect_digest
           || zone_alloc_parquet_digest
  ```

  where `||` denotes direct byte concatenation of the ASCII characters of each hex string, with no delimiters.

* Compute:

  [
  routing_universe_hash = \mathrm{SHA256}(\text{concat}),
  ]

  encoded as a lowercase hex string.

This `routing_universe_hash` is the **single universe identifier** that downstream components will check.

---

### 6.6 Phase 5 — Write `zone_alloc_universe_hash` & finalise `zone_alloc`

**Step 16 – Fill `routing_universe_hash` into `zone_alloc` rows**

Before finalising `zone_alloc`:

* For every row in the in-memory (or stream-augmented) representation, set:

  * `routing_universe_hash` = the value computed in Step 15.

If S5 wrote `zone_alloc` before computing the hash, it MUST either:

* rewrite `zone_alloc` with the hash included (ensuring idempotence checks are updated against the new content), or
* define the algorithm so that digest computation is done on the final representation that includes `routing_universe_hash` (recommended).

To avoid ambiguity, the canonical procedure is:

1. Construct rows without `routing_universe_hash`.
2. Compute `zone_alloc_parquet_digest` on that representation.
3. Compute `routing_universe_hash`.
4. Set `routing_universe_hash` on all rows.
5. Write final `zone_alloc` and compute its digest again (because changing the rows changes bytes) — this final digest is what is stored as `zone_alloc_parquet_digest`.

The spec requires that the `zone_alloc_parquet_digest` and `routing_universe_hash` in the universe-hash artefact match the **final** on-disk `zone_alloc`.

**Step 17 – Write (or confirm) `zone_alloc`**

Using the idempotence rules from Step 10 with the final row set (including `routing_universe_hash`):

* If no dataset exists at the target path, write `zone_alloc` with:

  * partitioning `["seed","fingerprint"]`,
  * sorted by the writer-sort key.

* If a dataset exists, verify it matches exactly; if not, raise `E3A_S5_007_IMMUTABILITY_VIOLATION`.

**Step 18 – Build `zone_alloc_universe_hash` object**

S5 constructs an in-memory JSON object conforming to `schemas.3A.yaml#/validation/zone_alloc_universe_hash` with at least:

* `manifest_fingerprint` = current `manifest_fingerprint`.
* `parameter_hash` = current `parameter_hash`.
* `zone_alpha_digest`, `theta_digest`, `zone_floor_digest`, `day_effect_digest`, `zone_alloc_parquet_digest`.
* `routing_universe_hash`.
* Optional: `version` (e.g. `"1.0.0"`), `created_at_utc` (from orchestrator), `notes`.

S5 MUST NOT include the raw artefact contents themselves; only their digests and minimal metadata.

**Step 19 – Write `zone_alloc_universe_hash` and enforce immutability**

Using the dictionary entry:

* Path:
  `data/layer1/3A/zone_universe/fingerprint={manifest_fingerprint}/zone_alloc_universe_hash.json`.

Procedure:

1. Check if a file already exists at this path.

   * If not:

     * Serialise the object to JSON deterministically (e.g. key-sorted, fixed encoding).
     * Validate against `schemas.3A.yaml#/validation/zone_alloc_universe_hash`.
     * Write the file.

   * If yes:

     * Read existing JSON, validate it, and compare all fields to the newly computed object.
     * If they are identical:

       * S5 MAY leave the file as-is (idempotent).
     * If they differ:

       * S5 MUST NOT overwrite and MUST raise `E3A_S5_007_IMMUTABILITY_VIOLATION`.

2. Optionally compute and store the file’s own SHA-256 in the artefact registry `digest` field; this does not feed back into `routing_universe_hash`.

---

### 6.7 RNG & side-effect discipline

Throughout the algorithm, S5 MUST:

* **Never consume RNG**

  * No calls to Philox or any other RNG.
  * S5 is purely deterministic; all randomness is upstream (S3).

* **Not depend on wall-clock time**

  * Any timestamps (e.g. `created_at_utc`) MUST be supplied by the orchestration layer and MUST NOT participate in any digest or affect the content of `zone_alloc` or `routing_universe_hash`.
  * S5 itself MUST NOT call `now()` or similar functions.

* **Not mutate upstream artefacts**

  * S5 MUST NOT modify S1–S4 datasets or S0/policy artefacts.
  * It only writes to:

    * `zone_alloc@seed={seed}/fingerprint={manifest_fingerprint}`,
    * `zone_alloc_universe_hash@fingerprint={manifest_fingerprint}`.

* **Fail atomically**

  * On any failure in Steps 1–19, S5 MUST NOT leave partially written or conflicting `zone_alloc` / `zone_alloc_universe_hash` artefacts in place.
  * Either:

    * no outputs are written, or
    * existing outputs are confirmed to be identical and left untouched.

Under this algorithm, for any fixed `(parameter_hash, manifest_fingerprint, seed, run_id)`, S5 yields:

* a `zone_alloc` egress dataset that is a faithful projection of S4’s counts with full lineage and a stable `routing_universe_hash`, and
* a `zone_alloc_universe_hash` artefact that cryptographically binds together the priors, mixture policy, floor policy, day-effect policy and the egress itself—without introducing new randomness or hidden semantics.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes how the two S5 artefacts:

* `zone_alloc` (zone allocation egress), and
* `zone_alloc_universe_hash` (routing universe digest),

are **identified**, how they are **partitioned**, what their **ordering** means, and what is allowed in terms of **merge / overwrite** behaviour.

Nothing in this section changes the domain or shapes already defined; it makes them explicit and binding.

---

### 7.1 `zone_alloc`: row identity & domain

For `zone_alloc`, each row is identified at two levels:

* **Run context** (shared across the partition):

  * `seed` — Layer-1 run seed.
  * `manifest_fingerprint` — Layer-1 manifest hash.

* **Business identity** within a run:

  * `merchant_id` — merchant ID (`id64`).
  * `legal_country_iso` — ISO-3166 country code.
  * `tzid` — IANA time-zone ID.

Given:

* `D` and `D_esc` from `s1_escalation_queue` (all merchant×country pairs and the escalated subset), and
* `Z(c)` from `s2_country_zone_priors` for each `legal_country_iso = c`,

the **intended domain** of `zone_alloc` is:

[
D_{\text{zone_alloc}} = { (m,c,z) \mid (m,c) \in D_{\text{esc}},\ z \in Z(c) }.
]

Binding requirements:

* For each `(m,c) ∈ D_esc` and each `z ∈ Z(c)`, there MUST be **exactly one** `zone_alloc` row with:

  * `merchant_id = m`, `legal_country_iso = c`, `tzid = z`.
* There MUST be **no** `zone_alloc` rows for:

  * `(m,c)` that are not in `D`,
  * `(m,c)` with `is_escalated = false`, or
  * any `tzid` not in `Z(c)` for that country.

**Logical primary key** within a `{seed, manifest_fingerprint}` partition:

[
PK = (\text{merchant_id},\ \text{legal_country_iso},\ \text{tzid})
]

No duplicates for this triple are allowed.

---

### 7.2 `zone_alloc`: partitions & path tokens

` zone_alloc` is a **run-scoped** cross-layer egress, aligned with S1/S3/S4.

**Partition keys**

* The partition key set MUST be exactly:

```yaml
["seed", "fingerprint"]
```

**Path template**

As per the dataset dictionary:

```text
data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/...
```

Binding rules:

* For any concrete partition, the physical path MUST include:

  * `seed=<uint64>` and
  * `fingerprint=<hex64>`.
* There MUST be at most one `zone_alloc` dataset for any `{seed, manifest_fingerprint}`.

**Path↔embed equality**

Every row in the partition MUST satisfy:

* `row.seed == <seed from path>`,
* `row.manifest_fingerprint == <fingerprint from path>`.

Any mismatch is a schema/validation error.

---

### 7.3 `zone_alloc`: ordering semantics (writer-sort)

Physical row order in `zone_alloc` is **not semantically meaningful**. S5 MUST, however, apply a deterministic writer-sort for reproducibility and digest stability.

Within each `{seed, manifest_fingerprint}` partition, rows MUST be sorted by:

1. `merchant_id` (ascending),
2. `legal_country_iso` (ascending),
3. `tzid` (ascending, ASCII-lex).

Consumers MUST:

* NOT rely on row order for any semantics, and
* use only the keys and fields for joins and logic.

The only purpose of the sort is to ensure that:

* re-running S5 with identical inputs produces **byte-identical** Parquet output, and
* the `zone_alloc_parquet_digest` is stable.

---

### 7.4 `zone_alloc`: merge & idempotence discipline

` zone_alloc` is a **snapshot** for one `{seed, manifest_fingerprint}`. It is not an append log and MUST obey strict immutability.

**Single snapshot per run**

* There MUST be at most one `zone_alloc` dataset at the path
  `data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/`.
* Only S5 is authorised to write to this dataset.

**No partial or incremental updates**

* S5 MUST always treat the dataset as an atomic snapshot of the entire `D_zone_alloc` domain.
* It MUST NOT:

  * append new rows onto an existing snapshot,
  * delete or mutate individual rows in place, or
  * split the same `{seed,fingerprint}` snapshot across multiple “versions” or subdirectories.

**Idempotent re-writes only**

If a `zone_alloc` dataset already exists for `{seed, manifest_fingerprint}` when S5 runs:

1. S5 MUST read it, normalise it (schema + writer-sort), and construct a canonical in-memory representation.
2. S5 MUST compare that representation to the newly computed row set:

   * If **identical** (rows and all field values match), S5 MAY:

     * either leave the existing files untouched, or
     * overwrite with identical bytes; in either case, the observable data and `zone_alloc_parquet_digest` remain unchanged.
   * If **different**, S5 MUST:

     * NOT overwrite, and
     * raise `E3A_S5_007_IMMUTABILITY_VIOLATION` and mark the run as FAIL.

There is no concept of “merging” multiple different `zone_alloc` snapshots for the same run; any such situation is a contract violation.

---

### 7.5 `zone_alloc_universe_hash`: identity & partitions

` zone_alloc_universe_hash` is a **fingerprint-scoped** validation artefact summarising the configuration and allocation digests for this manifest.

**Logical identity**

* At minimum, identity is given by:

  * `manifest_fingerprint` — the same value as used for S0/S5/S1–S4.
* The artefact also contains `parameter_hash` as a field, but `parameter_hash` is not a partition key in this version.

**Partition keys**

* The partition key set MUST be:

```yaml
["fingerprint"]
```

No other partition keys (e.g. `parameter_hash`, `seed`, `run_id`) are allowed.

**Path template**

From the dictionary:

```text
data/layer1/3A/zone_universe/fingerprint={manifest_fingerprint}/zone_alloc_universe_hash.json
```

Binding rules:

* For each `manifest_fingerprint`, there MUST be at most one `zone_alloc_universe_hash` file at this path.
* The JSON must contain a `manifest_fingerprint` field whose value equals the `{fingerprint}` token.

---

### 7.6 `zone_alloc_universe_hash`: ordering & merge discipline

` zone_alloc_universe_hash` is logically a single JSON object per `manifest_fingerprint`.

**Ordering**

* As a single JSON object (or single-row dataset), row ordering is not applicable.
* If encoded as JSON, the key order in the serialisation MUST be deterministic (e.g. lexicographically sorted keys) to ensure a stable file `digest`, but this ordering has no business semantics.

**Immutability**

Because this artefact is the **record of record** for the routing universe:

* Once written for a given `manifest_fingerprint`, `zone_alloc_universe_hash` MUST NOT be changed.
* If S5 is re-run for the same `(parameter_hash, manifest_fingerprint, seed, run_id)`:

  * It MUST recompute the JSON object and compare it to the existing file.
  * If identical (field-by-field), S5 may leave the file untouched.
  * If any field differs (any digest, `routing_universe_hash`, or metadata), S5 MUST NOT overwrite and MUST report `E3A_S5_007_IMMUTABILITY_VIOLATION`.

No “merging” or partial updates are allowed; any change in priors, policies or allocation that requires a new universe hash MUST be accompanied by a new `manifest_fingerprint` and/or `parameter_hash` per Layer-1 governance.

---

### 7.7 Cross-run semantics

S5 makes no claims about relationships between different runs.

* Each pair `(parameter_hash, manifest_fingerprint, seed, run_id)` defines a self-contained world with its own:

  * `zone_alloc@{seed,fingerprint}`, and
  * `zone_alloc_universe_hash@fingerprint`.

Consumers MUST NOT:

* treat a union of multiple `zone_alloc` partitions as a single coherent allocation for a specific run, or
* mix `zone_alloc` from one manifest with `zone_alloc_universe_hash` from another when checking hashes.

Cross-run unions (e.g. aggregating zone allocations across manifests for analytics) are allowed only for diagnostics; they MUST NOT be used to override or reinterpret the egress for any specific run.

---

### 7.8 Upstream & downstream identity alignment

Finally, S5’s outputs must remain consistent with upstream and downstream expectations:

* **Upstream:**

  * S1 provides `(merchant_id, legal_country_iso, site_count, is_escalated)`.
  * S2 provides `Z(c)` and priors.
  * S3 provides `Θ(m,c,z)`.
  * S4 provides `zone_site_count(m,c,z)`.

  S5 MUST NOT alter any of these identities or quantities; it only repackages them.

* **Downstream:**

  * Segment 2B and validation MUST use:

    * `(seed, manifest_fingerprint, merchant_id, legal_country_iso, tzid)` as the key to join onto `zone_alloc`, and
    * `routing_universe_hash` (and, if needed, component digests) to ensure that their own priors, floors, mixture, day-effect policies and routing configuration match the universe used to produce these counts.

Under these constraints, S5’s artefacts have clear, stable identities and are safe to treat as **final, immutable authority surfaces** for zone allocation and routing-universe definition.

---

## 8. Acceptance criteria & validator hooks *(Binding)*

This section defines **when 3A.S5 is considered PASS** for a given run
`(parameter_hash, manifest_fingerprint, seed, run_id)` and what a validation state (or cross-segment harness) MUST verify.

S5 is PASS **only if**:

* `zone_alloc` is a faithful, deterministic projection of `s4_zone_counts` (and thus S1–S3), and
* `zone_alloc_universe_hash` correctly summarises and binds the sealed priors/policies and the `zone_alloc` egress via `routing_universe_hash`.

There is no notion of “partial success”: either all criteria are met, or the run is FAIL.

---

### 8.1 Local acceptance criteria for 3A.S5

For a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, 3A.S5 is **PASS** if and only if **all** of the following hold.

#### 8.1.1 Preconditions (S0–S4 & policies) are satisfied

* `s0_gate_receipt_3A` and `sealed_inputs_3A` exist for `manifest_fingerprint` and are schema-valid.
* `upstream_gates.segment_1A/1B/2A.status == "PASS"`.
* `s1_escalation_queue@{seed,fingerprint}`, `s2_country_zone_priors@parameter_hash`, `s3_zone_shares@{seed,fingerprint}`, `s4_zone_counts@{seed,fingerprint}` all exist and validate against their schemas.
* Segment-state run-report rows for S1, S2, S3, S4 indicate `status="PASS"` for the relevant identities.
* The mixture policy, prior pack, floor policy and day-effect policy artefacts:

  * are present in `sealed_inputs_3A`,
  * validate against their `schema_ref`s, and
  * have `sha256_hex` in `sealed_inputs_3A` equal to the digest S5 computes over their bytes.

If any of these checks fail, S5 MUST be treated as FAIL.

---

#### 8.1.2 Domain alignment: `zone_alloc` vs S1 & S4

Let:

* `D` = set of `(merchant_id, legal_country_iso)` from `s1_escalation_queue`.
* `D_esc` = `{ (m,c) ∈ D | is_escalated(m,c) = true }`.
* `D_S4_proj` = projection of `s4_zone_counts` onto `(merchant_id, legal_country_iso)`.
* `D_alloc_proj` = projection of `zone_alloc` onto `(merchant_id, legal_country_iso)`.

S5 is PASS only if:

* `D_S4_proj == D_esc` (this should already be true from S4’s contract).
* `D_alloc_proj == D_esc`:

  * Every escalated `(m,c)` appears in `zone_alloc`.
  * No non-escalated `(m,c)` appears in `zone_alloc`.

For each `(m,c) ∈ D_esc`:

* Let:

  * `N = site_count(m,c)` from S1,
  * `N_sum = zone_site_count_sum(m,c)` as stored in `zone_alloc`,
  * `N_z = Σ_z zone_site_count(m,c,z)` across all `tzid` rows in `zone_alloc`.

Then S5 is PASS only if:

* `N_sum = N_z = N` for every `(m,c) ∈ D_esc`.
* `zone_site_count(m,c,z) ≥ 0` for all `(m,c,z)`.

Any missing/extra `(m,c)` or any conservation failure MUST cause FAIL.

---

#### 8.1.3 Domain alignment: `zone_alloc` vs S2/S3 (zones)

For each `country_iso = c` appearing in any `(m,c) ∈ D_esc`:

* Let `Z(c) = { tzid | (country_iso=c, tzid) ∈ s2_country_zone_priors }`.
* For each `(m,c) ∈ D_esc`:

  * `Z_S3(m,c) = { tzid | rows in s3_zone_shares with (m,c, tzid) }`.
  * `Z_alloc(m,c) = { tzid | rows in zone_alloc with (m,c, tzid) }`.

S5 is PASS only if, for all `(m,c) ∈ D_esc`:

* `Z_S3(m,c) == Z(c) == Z_alloc(m,c)`.

There MUST be:

* no `(m,c,z)` in `zone_alloc` for `z ∉ Z(c)`, and
* no missing `(m,c,z)` in `zone_alloc` for any `z ∈ Z(c)`.

Any zone-domain mismatch MUST cause FAIL.

---

#### 8.1.4 Per-row invariants in `zone_alloc`

For every row in `zone_alloc`:

* `seed` and `manifest_fingerprint` match the partition tokens.
* `zone_site_count` is integer ≥ 0.
* `zone_site_count_sum` is integer ≥ 0.
* `site_count` is integer ≥ 0 and equals `zone_site_count_sum` for that `(m,c)`.
* `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version`, `mixture_policy_id`, `mixture_policy_version`, `day_effect_policy_id`, `day_effect_policy_version` are non-empty strings and constant across the entire `{seed,fingerprint}` partition.
* `routing_universe_hash` is present, non-empty, and matches the value stored in `zone_alloc_universe_hash.routing_universe_hash`.

Any schema violation, path↔embed mismatch, negative counts, or inconsistent lineage MUST cause FAIL.

---

#### 8.1.5 `zone_alloc_universe_hash` correctness

Let:

* `U` be the JSON object read from `zone_alloc_universe_hash@fingerprint={manifest_fingerprint}`.

S5 is PASS only if:

1. **Schema & identity**

   * `U` validates against `schemas.3A.yaml#/validation/zone_alloc_universe_hash`.
   * `U.manifest_fingerprint` equals the partition token `{fingerprint}`.
   * `U.parameter_hash` equals the run’s `parameter_hash`.

2. **Component digests match recomputed values**

   Let:

   * `U.zone_alpha_digest`, `U.theta_digest`, `U.zone_floor_digest`, `U.day_effect_digest`, `U.zone_alloc_parquet_digest` be the values in `U`.

   S5 (or the validator) MUST recompute:

   * `zone_alpha_digest'` from `s2_country_zone_priors` (or prior pack),
   * `theta_digest'` from the mixture policy artefact,
   * `zone_floor_digest'` from the floor policy artefact,
   * `day_effect_digest'` from the day-effect policy artefact,
   * `zone_alloc_parquet_digest'` from `zone_alloc` as per the canonical procedure.

   And assert:

   * `zone_alpha_digest' == U.zone_alpha_digest`,
   * `theta_digest' == U.theta_digest`,
   * `zone_floor_digest' == U.zone_floor_digest`,
   * `day_effect_digest' == U.day_effect_digest`,
   * `zone_alloc_parquet_digest' == U.zone_alloc_parquet_digest`.

3. **Combined `routing_universe_hash` recomputes**

   * Form the canonical concatenation:

     ```text
     concat' = zone_alpha_digest' ||
               theta_digest'      ||
               zone_floor_digest' ||
               day_effect_digest' ||
               zone_alloc_parquet_digest'
     ```

   * Compute `routing_universe_hash' = SHA256(concat')` (lowercase hex).

   * Assert:

     * `routing_universe_hash' == U.routing_universe_hash`, and
     * `U.routing_universe_hash == zone_alloc.routing_universe_hash` for all rows in `zone_alloc`.

Any mismatch in component digests or combined hash MUST cause FAIL.

---

#### 8.1.6 Idempotence & immutability

If `zone_alloc` or `zone_alloc_universe_hash` already exist for this `{seed, manifest_fingerprint}`:

* S5 MUST confirm that:

  * The newly computed `zone_alloc` row set (sorted and normalised) is byte-for-byte identical to the existing dataset;
  * The newly computed universe-hash JSON object is field-for-field identical to the existing JSON file.

Any attempt to overwrite a non-identical `zone_alloc` or `zone_alloc_universe_hash` MUST be treated as an immutability violation and the run MUST be FAIL.

---

### 8.2 Validator hooks for 3A & cross-segment validation

A 3A validation state (and/or a cross-segment routing validator) MUST treat S5 as follows:

#### 8.2.1 Shape & domain replay

* Re-validate `zone_alloc` and `zone_alloc_universe_hash` against their schema anchors.

* Reconstruct:

  * `D` and `D_esc` from S1,
  * `Z(c)` from S2,
  * `D_S3` from S3,
  * `D_S4` from S4,
  * `D_alloc` from `zone_alloc`.

* Confirm:

  * `D_S3` and `D_S4` already conform to their own contracts, and
  * `D_alloc` matches `D_S4` and thus `D_esc × Z(c)` exactly.

#### 8.2.2 Count conservation & replay

For each `(m,c) ∈ D_esc`:

* Join:

  * `site_count(m,c)` from S1,
  * `zone_site_count(m,c,z)` from S4,
  * `zone_site_count(m,c,z)` from `zone_alloc`.

Validators MUST assert:

* That `zone_site_count` in `zone_alloc` equals S4’s `zone_site_count`.
* That `Σ_z zone_site_count(m,c,z) == site_count(m,c)`.

If S4’s integerisation is replayed (per S4’s spec), validators can also confirm that:

* applying the deterministic rounding scheme to `(N, Θ)` reproduces the same counts S4 produced and that S5 preserved them.

#### 8.2.3 Universe hash replay

For each `manifest_fingerprint`:

* Recompute component digests from:

  * S2 prior surface/pack,
  * mixture policy artefact,
  * floor policy artefact,
  * day-effect policy artefact,
  * `zone_alloc` egress.

* Validate equality with the values in `zone_alloc_universe_hash`.

* Recompute `routing_universe_hash` and check:

  * equals `zone_alloc_universe_hash.routing_universe_hash`, and
  * equals `zone_alloc.routing_universe_hash` on every row.

Any mismatch MUST be treated as a universe-hash integrity failure.

#### 8.2.4 Cross-segment enforcement (2B side)

A cross-segment validator (or 2B’s own governance layer) SHOULD:

* For each run where 2B consumes `zone_alloc`:

  * load `zone_alloc_universe_hash`,
  * recompute or verify component digests against the priors, mixture and day-effect policies **seen by 2B**,
  * recompute `routing_universe_hash` and assert equality with `zone_alloc.routing_universe_hash` and whatever hash 2B has recorded in its own state (if applicable).

If a discrepancy is detected, 2B MUST treat that configuration as invalid (“routing universe drift”), and either:

* refuse to start, or
* perform a controlled shutdown / rollback as per operational policy.

---

### 8.3 Handling of S5 failures

If any of the acceptance criteria in §8.1 fail, either during S5 or in a later validation pass:

* `zone_alloc` and `zone_alloc_universe_hash` for that `{seed, manifest_fingerprint}` MUST be treated as **non-authoritative**.
* Segment 2B and any other consumers MUST NOT use this `zone_alloc` for routing, simulation or modelling.
* Any downstream artefacts derived from this allocation (e.g. 2B alias blobs, day-effect group weights) MUST NOT be released or used in production.

Recovery requires:

* identifying and correcting the root cause (e.g. S1–S4 bug, policy mis-sealing, catalogue misconfiguration, data corruption), and
* re-running the affected states (S0→S5 as necessary) to produce a new, consistent `zone_alloc` and `zone_alloc_universe_hash` under a clean `(parameter_hash, manifest_fingerprint, seed, run_id)`.

Only when all of §8.1’s criteria are satisfied and the validator hooks in §8.2 succeed is S5 considered **PASS**, and only then may `zone_alloc` and `zone_alloc_universe_hash` be treated as the final, immutable authority surfaces for zone allocation and routing universe definition for this run.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only allowed failure classes** for `3A.S5 — Zone Allocation Egress & Routing Universe Hash` and assigns each a **canonical error code**.

Every S5 run MUST end in exactly one of:

* `status = "PASS"` with `error_code = null`, or
* `status = "FAIL"` with `error_code ∈ {E3A_S5_001 … E3A_S5_008}`.

No other error codes may be used by S5 without revising this specification.

---

### 9.1 Error taxonomy overview

S5 can fail only for the following reasons:

1. **Preconditions not met** — S0/S1/S2/S3/S4 or required policies are missing or not PASS.
2. **Catalogue / schema failures** — required schema/dictionary/registry artefacts are missing or invalid.
3. **Domain/count mismatches** — `zone_alloc` disagrees with S1/S2/S3/S4 on which rows exist or what totals they carry.
4. **Digest mismatches** — component digests (priors/mixture/floor/day-effect/zone_alloc) do not match the underlying artefacts.
5. **Universe hash mismatches** — `routing_universe_hash` does not reflect the component digests or does not match between artefacts.
6. **Output schema / structural violations** — `zone_alloc` or `zone_alloc_universe_hash` fail schema or internal consistency checks.
7. **Immutability / idempotence violations** — attempting to overwrite an existing non-identical snapshot.
8. **Infrastructure / I/O failures** — environment-level issues (storage, network, permissions).

Each case is mapped to a specific error code with required fields and retryability semantics.

---

### 9.2 Preconditions not met

#### `E3A_S5_001_PRECONDITION_FAILED`

**Condition**

Raised when any S5 precondition in §2.1 / §2.2 is not satisfied, including but not limited to:

* `s0_gate_receipt_3A` or `sealed_inputs_3A` missing or schema-invalid.
* `s0_gate_receipt_3A.upstream_gates.segment_1A/1B/2A.status != "PASS"`.
* `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`, or `s4_zone_counts` missing or schema-invalid.
* The S1/S2/S3/S4 run-report rows for this run show `status != "PASS"`.
* Any required policy/prior artefact (mixture, prior pack, floor policy, day-effect policy) is missing from `sealed_inputs_3A` or fails schema validation.

**Required fields**

* `component` — one of:

  * `"S0_GATE"`, `"S0_SEALED_INPUTS"`,
  * `"S1_ESCALATION_QUEUE"`, `"S2_PRIORS"`, `"S3_ZONE_SHARES"`, `"S4_ZONE_COUNTS"`,
  * `"MIXTURE_POLICY"`, `"PRIOR_PACK"`, `"FLOOR_POLICY"`, `"DAY_EFFECT_POLICY"`.
* `reason` — one of:

  * `"missing"`, `"schema_invalid"`, `"upstream_gate_not_pass"`, `"upstream_state_not_pass"`.
* If `reason = "upstream_gate_not_pass"`:

  * `segment ∈ {"1A","1B","2A"}`,
  * `reported_status` — non-`"PASS"` upstream status.
* If `reason = "upstream_state_not_pass"`:

  * `state ∈ {"S1","S2","S3","S4"}`,
  * `reported_status` — non-`"PASS"` state status.

**Retryability**

* **Non-retryable** until the offending component is corrected and successfully re-run (e.g. re-run S2 if priors are malformed, re-run S4 if counts are invalid, etc.).
* Re-running S5 alone without fixing the underlying issue MUST reproduce the same failure.

---

### 9.3 Catalogue & schema failures

#### `E3A_S5_002_CATALOGUE_MALFORMED`

**Condition**

Raised when S5 cannot load or validate required catalogue artefacts, such as:

* `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml`.
* `dataset_dictionary.layer1.3A.yaml`.
* `artefact_registry_3A.yaml`.

Failure conditions include missing files, parse errors, or schema validation failures.

**Required fields**

* `catalogue_id` — identifier of the failing artefact, e.g.:

  * `"schemas.3A.yaml"`,
  * `"dataset_dictionary.layer1.3A"`,
  * `"artefact_registry_3A"`.

**Retryability**

* **Non-retryable** until the catalogue artefact is fixed and conforms to its governing schema.

---

### 9.4 Domain & count mismatches

#### `E3A_S5_003_DOMAIN_MISMATCH`

**Condition**

Raised when `zone_alloc` is not domain-consistent with S1/S2/S3/S4 for this `{seed,fingerprint}`, including any of:

* **Merchant×country domain mismatch vs S1 / S4:**

  * There exists `(m,c)` with `is_escalated=true` in S1 but no `(m,c,·)` rows in `zone_alloc`.
  * There exists `(m,c,·)` in `zone_alloc` where S1 shows `is_escalated=false` or where `(m,c)` does not exist in S1.
  * For some `(m,c)`:

    * `zone_site_count_sum(m,c)` != `Σ_z zone_site_count(m,c,z)`, or
    * `zone_site_count_sum(m,c)` != `site_count(m,c)` from S1.

* **Zone-domain mismatch vs S2 / S3:**

  * For some escalated `(m,c)` with `c = legal_country_iso`:

    * `Z_alloc(m,c) = {tzid}` in `zone_alloc` is not equal to `Z(c)` from S2, or
    * `Z_alloc(m,c)` is not equal to the zone set seen in `s3_zone_shares` for `(m,c)`.

**Required fields**

* `missing_escalated_pairs_count` — number of escalated `(m,c)` pairs in S1 with no rows in `zone_alloc`.
* `unexpected_pairs_count` — number of `(m,c)` pairs present in `zone_alloc` that are not escalated in S1.
* `affected_zone_triplets_count` — number of `(m,c,z)` combinations where a zone is missing or extra relative to S2/S3.
* Optionally:

  * `sample_merchant_id`,
  * `sample_country_iso`,
  * `sample_tzid`
    for at least one offending example (subject to logging/redaction policy).

**Retryability**

* **Non-retryable** until S4’s outputs or S5’s domain construction are corrected.
* This error indicates a logic or data-corruption problem; re-running S5 alone will not fix it.

---

### 9.5 Digest and universe-hash mismatches

#### `E3A_S5_004_DIGEST_MISMATCH`

**Condition**

Raised when one or more **component digests** in `zone_alloc_universe_hash` do not match recomputed values from the underlying artefacts, including:

* `zone_alpha_digest` mismatch vs S2 prior surface/pack.
* `theta_digest` mismatch vs the mixture policy artefact.
* `zone_floor_digest` mismatch vs the floor/bump policy artefact.
* `day_effect_digest` mismatch vs the day-effect policy artefact.
* `zone_alloc_parquet_digest` mismatch vs the actual bytes of the `zone_alloc` data files.

**Required fields**

* `component ∈ {"zone_alpha_digest","theta_digest","zone_floor_digest","day_effect_digest","zone_alloc_parquet_digest"}`
* `expected_sha256_hex` — digest recomputed from underlying artefact.
* `observed_sha256_hex` — digest stored in `zone_alloc_universe_hash`.

**Retryability**

* **Non-retryable** until the discrepancy is resolved:

  * fix the underlying artefact (e.g. restore correct priors/policies / `zone_alloc`),
  * or update the manifest to point to the correct artefact and rerun S5.

This error typically indicates either:

* configuration drift without updating `sealed_inputs_3A` / `zone_alloc_universe_hash`, or
* corruption or accidental modification of an artefact after S5 was run.

---

#### `E3A_S5_005_UNIVERSE_HASH_MISMATCH`

**Condition**

Raised when the **combined routing universe hash** is inconsistent, including:

* `routing_universe_hash` in `zone_alloc_universe_hash` does not equal the recomputed `SHA256(zone_alpha_digest ∥ theta_digest ∥ zone_floor_digest ∥ day_effect_digest ∥ zone_alloc_parquet_digest)`.
* `routing_universe_hash` embedded in `zone_alloc` rows does not match `zone_alloc_universe_hash.routing_universe_hash`.
* Different `zone_alloc` rows in the same `{seed,fingerprint}` partition carry different `routing_universe_hash` values.

**Required fields**

* `reason ∈ {"bad_combination","mismatch_zone_alloc","inconsistent_within_zone_alloc"}`
* `expected_routing_universe_hash` — recomputed from component digests.
* `observed_routing_universe_hash` — from `zone_alloc_universe_hash` or `zone_alloc`.

**Retryability**

* **Non-retryable** until the hash computation or artefact content is corrected:

  * if computation is wrong: fix S5 and rerun S5,
  * if artefacts changed: regenerate digests under a new manifest / parameter set.

---

### 9.6 Output schema & structural failures

#### `E3A_S5_006_OUTPUT_SCHEMA_INVALID`

**Condition**

Raised when either `zone_alloc` or `zone_alloc_universe_hash` fails validation against its schema anchor:

* `zone_alloc`:

  * missing required fields,
  * wrong types or ranges (e.g. `zone_site_count` negative, `routing_universe_hash` missing),
  * path vs embedded `seed` / `manifest_fingerprint` mismatch.

* `zone_alloc_universe_hash`:

  * missing required digest fields or `routing_universe_hash`,
  * malformed `manifest_fingerprint` / `parameter_hash`,
  * incorrect types for digests.

**Required fields**

* `output_id ∈ {"zone_alloc","zone_alloc_universe_hash"}`
* `violation_count` — number of schema validation errors detected.
* Optionally:

  * `example_field` — a representative field that failed validation.

**Retryability**

* **Retryable only after implementation fix**.

  * Indicates that S5’s write path violated its own schema contracts.
  * Re-running S5 without fixing the bug is expected to reproduce the error.

---

### 9.7 Immutability / idempotence violations

#### `E3A_S5_007_IMMUTABILITY_VIOLATION`

**Condition**

Raised when S5 detects that an artefact already exists for the run identity and is **not** equal to what S5 would produce:

* For `zone_alloc` at the target `{seed, fingerprint}`:

  * existing dataset, when normalised and sorted, differs in any row or field from the newly computed `zone_alloc`.

* For `zone_alloc_universe_hash` at `fingerprint={manifest_fingerprint}`:

  * existing JSON object differs in any field from the newly computed universe-hash object.

S5 MUST NOT overwrite existing non-identical artefacts.

**Required fields**

* `artefact ∈ {"zone_alloc","zone_alloc_universe_hash","both"}`
* `difference_kind ∈ {"row_set","field_value"}`
* `difference_count` — number of differing rows or fields detected (may be approximate / bounded).

**Retryability**

* **Non-retryable** until the conflict is resolved.

Operators MUST decide whether:

* the existing artefact is authoritative (and S5’s logic needs correction), or
* the new calculation is correct (in which case a new manifest / run identity should be used).

Under no circumstances should S5 be configured to “force overwrite” for the same identity.

---

### 9.8 Infrastructure / I/O failures

#### `E3A_S5_008_INFRASTRUCTURE_IO_ERROR`

**Condition**

Raised when S5 cannot complete due to environment-level issues unrelated to its logical design, such as:

* temporary object-store or filesystem unavailability,
* permission errors on read/write,
* network timeouts,
* storage quota exhaustion.

This code MUST NOT be used for logical errors covered by `E3A_S5_001`–`E3A_S5_007`.

**Required fields**

* `operation ∈ {"read","write","list","stat"}`
* `path` — path or resource URI involved (if known).
* `io_error_class` — short classification, e.g.:

  * `"timeout"`, `"permission_denied"`, `"not_found"`, `"quota_exceeded"`, `"connection_reset"`.

**Retryability**

* **Potentially retryable**, depending on infrastructure policy.

Orchestrators MAY:

* retry the S5 run under the same inputs after a backoff,
* but any successful retry MUST still satisfy all acceptance criteria in §8 before `zone_alloc` and `zone_alloc_universe_hash` are considered authoritative.

---

### 9.9 Run-report mapping

For run-report integration:

* Every S5 run MUST set:

  * `status="PASS", error_code=null`, **or**
  * `status="FAIL", error_code ∈ {E3A_S5_001 … E3A_S5_008}`.

Downstream components (2B, validation, analytics) MUST treat any `status="FAIL"` for S5 as meaning:

* `zone_alloc` and `zone_alloc_universe_hash` for this `{seed, manifest_fingerprint}` MUST NOT be used as authoritative inputs for routing, day-effect modelling or other downstream processing,
* and corrective action (fix + rerun) is required before allocating or routing based on 3A’s zone universe.

---

## 10. Observability & run-report integration *(Binding)*

This section defines what `3A.S5 — Zone Allocation Egress & Routing Universe Hash` MUST emit for observability, and how it MUST integrate with the Layer-1 run-report.

Because S5 is the **final pack/seal** step for 3A, observability must let you answer, for any run
`(parameter_hash, manifest_fingerprint, seed, run_id)`:

* Did S5 run?
* Did it succeed or fail, and why?
* How many merchants/zones were packaged?
* What is the `routing_universe_hash`, and which priors/policies/artefacts it encapsulates?
* Are 2B and the validator looking at the same universe?

S5 MUST NOT dump row-level business data (no full `zone_alloc` in logs/metrics); it only reports **summaries and hashes**.

---

### 10.1 Structured logging requirements

S5 MUST emit structured logs (e.g. JSON) for three lifecycle events: **start**, **success**, and **failure**.

#### 10.1.1 State start

Exactly one log event at the beginning of each S5 invocation.

Required fields:

* `layer = "layer1"`
* `segment = "3A"`
* `state = "S5"`
* `parameter_hash` (hex64)
* `manifest_fingerprint` (hex64)
* `seed` (uint64)
* `run_id` (string or u128-encoded)
* `attempt` (integer, if provided by orchestration; otherwise a fixed default such as `1`)

Optional:

* `trace_id` — correlation ID from the orchestration layer.

Log level: `INFO`.

#### 10.1.2 State success

Exactly one log event **only if** S5 meets all acceptance criteria in §8.

Required fields:

* All “start” fields above.
* `status = "PASS"`.
* `error_code = null`.

**Domain summary:**

* `zone_alloc_rows_total` — number of rows in `zone_alloc` (i.e. |`D_zone_alloc`|).
* `merchants_escalated` — number of distinct `merchant_id` values in `zone_alloc`.
* `countries_escalated` — number of distinct `legal_country_iso` in `zone_alloc`.

**Count & domain sanity:**

* `pairs_escalated` — |`D_esc`| (from S1).
* `pairs_in_zone_alloc` — number of distinct `(merchant_id, legal_country_iso)` pairs in `zone_alloc`.
* `pairs_with_count_conservation_violations` — MUST be `0` on PASS.

**Universe digest summary:**

* `zone_alpha_digest` — as stored in `zone_alloc_universe_hash`.
* `theta_digest` — mixture policy digest.
* `zone_floor_digest`.
* `day_effect_digest`.
* `zone_alloc_parquet_digest`.
* `routing_universe_hash`.

Optional:

* `elapsed_ms` — wall-clock duration (from orchestration; MUST NOT influence behaviour).
* `zone_count_histogram` — small JSON map summarising the distribution of `|Z(c)|` for escalated countries (e.g. `{ "1": n1, "2-3": n2, "4+": n3 }`).

Log level: `INFO`.

#### 10.1.3 State failure

Exactly one log event **only if** S5 terminates without satisfying §8.

Required fields:

* All “start” fields.

* `status = "FAIL"`.

* `error_code` — one of `E3A_S5_001 … E3A_S5_008`.

* `error_class` — coarse category, e.g.:

  * `"PRECONDITION"`,
  * `"CATALOGUE"`,
  * `"DOMAIN"`,
  * `"DIGEST"`,
  * `"UNIVERSE_HASH"`,
  * `"OUTPUT_SCHEMA"`,
  * `"IMMUTABILITY"`,
  * `"INFRASTRUCTURE"`.

* `error_details` — structured map containing the required fields specified in §9 for that `error_code` (e.g. `component`, `missing_escalated_pairs_count`, `expected_sha256_hex`, `observed_sha256_hex`, etc.).

Recommended additional fields (if available at failure time):

* `zone_alloc_rows_total` — number of rows S5 attempted to process.
* `pairs_escalated`, `pairs_in_zone_alloc`.

Optional:

* `elapsed_ms`.

Log level: `ERROR`.

All logs MUST be machine-parsable and MUST NOT contain full `zone_alloc` content (no full row dumps).

---

### 10.2 Segment-state run-report integration

S5 MUST write exactly **one** row into the Layer-1 **segment-state run-report** (e.g. `run_report.layer1.segment_states`) per invocation.

The run-report row must uniquely identify the S5 run and summarise its outcome.

**Identity & context:**

* `layer = "layer1"`
* `segment = "3A"`
* `state = "S5"`
* `parameter_hash`
* `manifest_fingerprint`
* `seed`
* `run_id`
* `attempt`

**Outcome:**

* `status ∈ {"PASS","FAIL"}`.
* `error_code` — `null` on PASS; one of `E3A_S5_001 … E3A_S5_008` on FAIL.
* `error_class` — as above.
* `first_failure_phase` — optional enum indicating where the run failed, e.g.:

  ```text
  "S0_GATE" | "S1_S2_S3_S4_PRECONDITION" |
  "DOMAIN_BUILD" | "COUNTS_CHECK" |
  "DIGEST_COMPUTE" | "UNIVERSE_HASH_BUILD" |
  "OUTPUT_WRITE" | "IMMUTABILITY" |
  "INFRASTRUCTURE"
  ```

**Zone alloc summary:**

* `zone_alloc_rows_total`.
* `pairs_escalated` — from S1.
* `pairs_in_zone_alloc` — from `zone_alloc`.
* `pairs_with_count_conservation_violations` — number of `(m,c)` failing conservation checks (MUST be `0` on PASS).

**Universe digest summary (required on PASS; MAY be populated on FAIL if known):**

* `zone_alpha_digest`.
* `theta_digest`.
* `zone_floor_digest`.
* `day_effect_digest`.
* `zone_alloc_parquet_digest`.
* `routing_universe_hash`.

**Catalogue/policy versions:**

* `schemas_layer1_version`.
* `schemas_3A_version`.
* `dictionary_layer1_3A_version`.
* Versions/IDs for relevant policy artefacts, if available (e.g. `zone_mixture_policy_version`, `zone_floor_policy_version`, `day_effect_policy_version`).

**Timing & correlation:**

* `started_at_utc` — orchestrator-provided; MUST NOT affect S5 logic.
* `finished_at_utc`.
* `elapsed_ms`.
* `trace_id` — if used.

The run-report row MUST be consistent with:

* `s1_escalation_queue`, `s4_zone_counts`, `zone_alloc`, and `zone_alloc_universe_hash`.
* Any validator MUST be able to navigate from this row to all relevant artefacts using the IDs and hashes provided.

---

### 10.3 Metrics & counters

S5 MUST expose a minimal set of metrics suitable for monitoring. Names and export mechanisms are implementation-specific; semantics are binding.

At minimum:

* `mlr_3a_s5_runs_total{status="PASS"|"FAIL"}`

  * Monotone counter; incremented once per S5 run.

* `mlr_3a_s5_zone_alloc_rows_total` (gauge)

  * Number of rows in `zone_alloc` for the most recent successful run (per `{seed,fingerprint}`).

* `mlr_3a_s5_pairs_escalated` (gauge)

  * Number of escalated `(m,c)` pairs in the most recent successful run.

* `mlr_3a_s5_pairs_count_conservation_errors_total` (counter)

  * Count of runs where `E3A_S5_003_DOMAIN_MISMATCH` was raised due to count conservation issues.

* `mlr_3a_s5_digest_mismatch_total` (counter)

  * Count of runs failing with `E3A_S5_004_DIGEST_MISMATCH`.

* `mlr_3a_s5_universe_hash_mismatch_total` (counter)

  * Count of runs failing with `E3A_S5_005_UNIVERSE_HASH_MISMATCH`.

* `mlr_3a_s5_duration_ms` (histogram)

  * Distribution of S5 run durations.

Metric labels MUST NOT include high-cardinality identifiers (e.g. raw merchant IDs, tzids). Labels SHOULD be limited to:

* `state="S5"`,
* `status="PASS"|"FAIL"`,
* `error_class`,
* maybe coarse buckets for `zone_alloc_rows_total` (e.g. `size="small|medium|large"`).

---

### 10.4 Correlation & traceability

S5’s artefacts must be easy to correlate with upstream and downstream components:

1. **Cross-state correlation**

   * S5’s run-report row MUST be joinable with S0–S4 run-report rows via:

     ```text
     (layer="layer1", segment="3A", parameter_hash, manifest_fingerprint, seed, run_id)
     ```

   * If a `trace_id` is provided by the orchestration, S5 MUST include it in:

     * structured logs;
     * run-report rows.

2. **Artefact navigation**

   * From the S5 run-report row, a validator MUST be able to locate:

     * `zone_alloc` (via `dataset_dictionary.layer1.3A.yaml` + `artefact_registry_3A.yaml` + `{seed,fingerprint}`),
     * `zone_alloc_universe_hash` (via `fingerprint`),
     * S1/S2/S3/S4 artefacts referenced in the `dependencies` lists, and
     * sealed priors/policies (via `sealed_inputs_3A` and `s0_gate_receipt_3A`).

3. **Universe check by 2B**

   * 2B (or its own validator) MUST be able to:

     * read `zone_alloc_universe_hash` for the relevant `manifest_fingerprint`,
     * recompute digests from its own view of priors/policies/zone_alloc (if it has a local copy), and
     * compare `routing_universe_hash` to its own reference value.
   * S5’s logs/run-report row MUST expose `routing_universe_hash` and component digests so that mismatches can be detected and investigated.

---

### 10.5 Retention, access control & privacy

Even though the data are synthetic, zone allocations and universe hashes are sensitive from a system-behaviour perspective. The following constraints apply:

1. **Retention**

   * `zone_alloc` and `zone_alloc_universe_hash` MUST be retained for at least as long as:

     * any 2B routing/day-effect artefacts derived from them are in use, and
     * any models/analytics that depend on those routing outcomes remain active.

   * Deleting S5 artefacts while dependants are still active is out-of-spec.

2. **Access control**

   * Access to `zone_alloc` and `zone_alloc_universe_hash` SHOULD be restricted to operators and components that require knowledge of the zone allocation universe (e.g. 2B, validation, observability tools).
   * S5’s logs and metrics MUST NOT expose full `zone_alloc` rows or contain secrets (credentials, keys).

3. **No bulk data leakage via observability**

   * Structured logs MUST NOT include entire `zone_alloc` content or all `(m,c,z)` counts.
   * If any sample identifiers (e.g. specific merchants/countries) are logged for debugging, they MUST comply with Layer-1 logging/redaction policies and should be limited to a small sample.

---

### 10.6 Relationship to Layer-1 run-report governance

The Layer-1 run-report may impose additional fields and rules (e.g. standardised `environment`, `build_id`, `cluster` columns). Where there is a conflict:

* Layer-1 run-report governance dictates the **schema and required fields**.
* This S5 section defines:

  * which S5-specific fields MUST be populated, and
  * the relationships those fields MUST have to S5’s artefacts and upstream components.

Under these rules, every S5 run is:

* **observable** (via structured logs),
* **summarised** (via a single, well-defined run-report row), and
* **auditable** (via `zone_alloc`, `zone_alloc_universe_hash`, and their upstream dependencies),

while keeping the routing universe explicit and preventing silent drift between what 3A sealed and what 2B actually uses.

---

## 11. Performance & scalability *(Informative)*

This section describes how 3A.S5 behaves as data volumes grow, and where its cost actually comes from. The binding rules are still in §§1–10; here we’re just interpreting them.

---

### 11.1 Workload shape

S5 is deliberately light:

* It operates on **already-aggregated** data:

  * `s4_zone_counts`: one row per **escalated** `(merchant, country, zone)` triple.
  * `s2_country_zone_priors`: one row per `(country, zone)` (priors; usually small).
* It touches a few relatively small **policy artefacts**:

  * mixture policy, prior pack, floor policy, day-effect policy.

The only “big” artefact S5 ever digests is `zone_alloc` itself, which is effectively the same size as `s4_zone_counts` (plus a bit of extra lineage).

So the core complexity is:

[
\text{Work} \sim |s4_zone_counts| + |s2_country_zone_priors| + \text{size of policy files},
]

with `|s4_zone_counts|` dominating.

---

### 11.2 Core cost drivers

S5’s main activities:

1. **Projection from S4 → `zone_alloc`**

   * For every row in `s4_zone_counts`:

     * copy identifiers and integer counts into `zone_alloc`,
     * join on small lookup tables (S1 for `site_count`, S2 for lineage, S0 for policy IDs).
   * Complexity: **O(|s4_zone_counts|)**; joins are either hash lookups (`(m,c)` → `site_count`) or small dictionary reads (`country_iso` → lineage).

2. **Digest computation over priors & policies**

   * Prior surface (`s2_country_zone_priors`):

     * `O(|countries| × |zones_per_country|)` bytes; tiny compared to main transaction data.
   * Mixture/floor/day-effect policies:

     * config-sized YAML/JSON files (KB–MB scale).
     * Single-pass SHA-256 over each file.

3. **Digest computation over `zone_alloc`**

   * Hashing `zone_alloc` is the only step that scales with the number of rows:

     * read each Parquet file, stream bytes through SHA-256,
     * complexity: **O(total_bytes(zone_alloc))**.
   * This is a simple streaming operation; no need to materialise the dataset in memory.

Net effect: S5’s runtime is roughly linear in the size of `zone_alloc` (i.e., the number of escalated `(merchant×country×zone)` rows) plus a small constant overhead for policy/priors.

---

### 11.3 Memory footprint

S5 does not need to hold large structures in memory:

* **Projection step:**

  * Can be implemented as a streaming transform:

    * Read `s4_zone_counts` in partitions/chunks.
    * Join on:

      * a small in-memory map from `(merchant_id, legal_country_iso)` → `site_count` (from S1),
      * a small map from `country_iso` → lineage (from S2),
      * pre-parsed policy IDs/versions (from S0).
    * Write `zone_alloc` rows incrementally.

* **Digest step:**

  * Use streaming SHA-256:

    * Read Parquet/JSON files in fixed-size chunks (e.g. 4–64 MB).
    * Update hash incrementally; no need to buffer entire files.

Peak memory is therefore controlled by:

* size of the small lookup tables (merchant×country → totals; country → lineage), plus
* buffering for one chunk of file data.

You never need to load all of `zone_alloc` or `s4_zone_counts` into RAM.

---

### 11.4 Concurrency & parallelism

S5 is easy to parallelise:

* **Across runs / manifests:**

  * Different `(parameter_hash, manifest_fingerprint, seed, run_id)` can be processed independently.

* **Within a run:**

  * Projection S4 → `zone_alloc` is embarrassingly parallel over partitions of `s4_zone_counts` (e.g. shard by `merchant_id` or by file).
  * Component digests can be computed in parallel:

    * priors, mixture policy, floor policy, day-effect policy are independent SHA-256 passes.
  * The final `zone_alloc_parquet_digest` must be computed over the fully written dataset, but can also be computed in parallel per file, then reduced:

    * e.g. compute SHA-256 per file, then combine deterministically into a single digest if you adopt a “hash tree” scheme (as long as this is defined in the contract).

Constraints:

* Parallel writers MUST respect:

  * the canonical writer-sort (or produce sorted output via a final shuffle/merge step),
  * the idempotence and immutability rules (no conflicting writes to the same `{seed,fingerprint}` path).

---

### 11.5 Expected runtime profile

Compared to other 3A/Layer-1 states:

* S5 is significantly cheaper than:

  * S1 (group-by over all outlets),
  * S2 (if priors are large, but those are still relatively small),
  * S3 (Gamma + Dirichlet sampling) and S4 (per-zone integerisation).

* S5’s heavy lifting is:

  * reading/writing `zone_alloc` (which is the same size as `s4_zone_counts`),
  * streaming `zone_alloc` through SHA-256.

In practice:

* If `s4_zone_counts` is, say, tens of millions of rows, S5 will:

  * read those rows once,
  * write out the same number of rows (with a bit more metadata),
  * compute a single SHA-256 over the resulting Parquet files.

No additional `O(N log N)` or quadratic behaviour is introduced by S5.

---

### 11.6 Tuning levers (non-normative)

Implementers can tune S5 performance without changing its semantics by:

1. **Batching & streaming:**

   * Process `s4_zone_counts` in streaming batches to avoid large shuffles.
   * Use vectorised Parquet readers/writers to maximise throughput.

2. **Efficient hashing:**

   * Ensure SHA-256 computation is done with large sequential reads (avoid many tiny I/O calls).
   * Optionally pre-compute and cache priors/policy digests across runs that share the same `parameter_hash` (since those artefacts are invariant given 𝓟).

3. **Early exits:**

   * Perform cheap structural checks early (existence, schema validation) before any heavy I/O.
   * If domain or conservation mismatches are detected, fail before computing digests.

4. **Parallelising across runs:**

   * S5 is a good candidate for “fan-out” parallelism across many manifests; each run is independent so you can add more workers to keep latency low.

All such tuning MUST preserve:

* the exact `zone_alloc` row set and field values,
* the canonical writer-sort,
* the digest algorithms and concatenation order, and
* the immutability and idempotence guarantees.

---

### 11.7 Scaling with `zone_alloc` size

As the number of escalated merchants and zones grows:

* `|zone_alloc|` grows linearly.
* S5’s runtime and I/O scale linearly with `|zone_alloc|`.
* Memory footprint remains bounded by the chosen batch/chunk size and small lookup tables.

The design deliberately ensures that **S5 remains a packaging/hashing step**, not a computational hot spot, even when the rest of the engine is operating at “big data” scale.

---

## 12. Change control & compatibility *(Binding)*

This section defines how the `3A.S5` contract may evolve, and what guarantees downstream consumers (2B, validation, other layers) can rely on when:

* the shape or meaning of `zone_alloc` changes,
* the routing universe hash logic changes, or
* the governed parameter set 𝓟 changes (and thus `parameter_hash`).

The goal is that, given:

* `parameter_hash`,
* `manifest_fingerprint`,
* `seed`,
* `run_id`,
* `zone_alloc` / `zone_alloc_universe_hash` **version**,

consumers can unambiguously interpret:

* which rows are in the zone allocation egress,
* how counts and lineage are defined, and
* what exactly is bound into `routing_universe_hash`.

---

### 12.1 Scope of change control

Change control for S5 covers:

1. The **shape and semantics** of its outputs:

   * `zone_alloc` (columns, identity, partitioning, meaning of `zone_site_count`, `site_count`, `routing_universe_hash`, etc.),
   * `zone_alloc_universe_hash` (digest fields, how `routing_universe_hash` is computed).

2. The **mapping** from inputs to outputs:

   * how S5 projects `s4_zone_counts` into `zone_alloc` (no changes to counts or domain),
   * how S5 computes `zone_alloc_parquet_digest`,
   * how S5 computes component digests (`zone_alpha_digest`, `theta_digest`, `zone_floor_digest`, `day_effect_digest`) and how they are combined into `routing_universe_hash`.

3. The **error taxonomy** and acceptance criteria in §§8–9.

It does **not** govern:

* internal performance details (batch sizes, parallelism, streaming strategy), so long as the logical outputs and digests are unchanged,
* Layer-1 definitions of `parameter_hash`, `manifest_fingerprint`, `seed`, `run_id`.

---

### 12.2 Dataset contract versioning

S5’s dataset contracts have versions carried in the dataset dictionary and registry:

* `zone_alloc` `version` in `dataset_dictionary.layer1.3A.yaml` and `artefact_registry_3A.yaml`.
* `zone_alloc_universe_hash` `version` in the dictionary and registry.

**Rules:**

1. **Single authoritative version per dataset.**

   * For `zone_alloc` and `zone_alloc_universe_hash`, the `version` in `dataset_dictionary.layer1.3A.yaml` and `artefact_registry_3A.yaml` MUST match.
   * Any change that affects the observable shape or semantics of a dataset MUST bump that dataset’s `version`.

2. **Semver semantics.**

   Versions use `MAJOR.MINOR.PATCH`:

   * **PATCH** (`x.y.z → x.y.(z+1)`):

     * Documentation clarifications,
     * stricter validations that only turn previously “silently invalid” runs into explicit FAILs,
     * changes that do **not** alter:

       * which rows appear,
       * any field values,
       * any digest values,
       * or how `routing_universe_hash` is computed.

   * **MINOR** (`x.y.z → x.(y+1).0`):

     * Backwards-compatible extensions, e.g.:

       * adding optional diagnostic fields,
       * adding new run-report or log fields,
       * adding new error codes,
       * exposing additional lineage fields that can be ignored by old consumers.
     * Existing consumers that ignore the new fields remain correct.

   * **MAJOR** (`x.y.z → (x+1).0.0`):

     * Breaking changes (see §12.4):

       * changing dataset identity/partitioning,
       * changing the semantics of counts or digests,
       * altering the definition of `routing_universe_hash` or which components it combines.

3. **Consumers MUST key off version.**

   * Behaviour MUST NOT be inferred from dates, build IDs, or “guesswork”.
   * Downstream code MUST check `version` (and schema) to handle different S5 contracts appropriately.

---

### 12.3 Backwards-compatible changes (MINOR/PATCH)

The following changes are **backwards-compatible** if implemented as described:

1. **Adding optional columns to `zone_alloc`.**
   Examples:

   * new diagnostic fields (e.g. `alpha_sum_country`, `zero_zone_flag`, `allocation_strategy_id`),
   * additional lineage (e.g. `s4_run_id` for debugging).

   Conditions:

   * New fields MUST be optional or have defaults,
   * They MUST be deterministic functions of existing inputs,
   * They MUST NOT affect:

     * domain `D_zone_alloc`,
     * `zone_site_count`, `zone_site_count_sum`, `site_count`,
     * `routing_universe_hash` or component digests.

2. **Adding optional fields to `zone_alloc_universe_hash`.**
   Examples:

   * `priors_schema_version`,
   * `mixture_policy_schema_version`,
   * additional digests (e.g. a digest over `s1_escalation_queue`, if you later decide to include it).

   Conditions:

   * New fields MUST be optional; older validators may ignore them.
   * They MUST NOT change how `routing_universe_hash` is computed unless marked as a breaking change (see §12.4).

3. **Extending error codes / metrics / logging.**

   * New `E3A_S5_***` codes MAY be added for finer error reporting.
   * New metrics and run-report fields MAY be added for observability.
   * Existing error codes MUST retain their semantics.

4. **Stronger internal validations.**

   * Additional checks (e.g. verifying that all lineage IDs match S0’s `sealed_policy_set`) are allowed if:

     * they do **not** change outputs for valid runs,
     * they only cause S5 to FAIL in cases that would previously have produced logically inconsistent artefacts.

5. **Performance improvements / implementation refactors.**

   * The internal processing (e.g. streaming vs batch, degree of parallelism) may change freely as long as:

     * `zone_alloc` and `zone_alloc_universe_hash` remain identical (byte-for-byte) for any given run,
     * RNG is still unused, and
     * digest algorithms and concatenation order are unchanged.

These changes generally warrant a MINOR bump if they touch schema or output, or a PATCH if they are implementation-only.

---

### 12.4 Breaking changes (MAJOR)

The following are **breaking changes**, requiring a **MAJOR** version bump for the affected dataset(s), and potentially coordinated changes in 2B / validation:

1. **Changing dataset identity or partitioning.**

   * Changing `id` or path format for `zone_alloc` or `zone_alloc_universe_hash`.
   * Changing partition keys (e.g. adding `parameter_hash` to `zone_alloc`’s partitioning, removing `seed`, or adding `run_id`).
   * Changing the logical primary key for `zone_alloc` (anything other than `(merchant_id, legal_country_iso, tzid)` for this contract).

2. **Changing semantics of zone counts.**

   * Reinterpreting `zone_site_count` to mean something other than “integer outlet count from S4 for this `(m,c,z)`”.
   * Changing how `site_count` or `zone_site_count_sum` relate to S1 `site_count` (e.g. no longer requiring equality).
   * Excluding some `Z(c)` zones, or including non-prior zones, without marking this as a new contract.

3. **Changing which rows appear in `zone_alloc`.**

   * Including non-escalated `(m,c)` pairs in `zone_alloc` without treating it as an explicit contract change.
   * Excluding some escalated `(m,c)` or some `z ∈ Z(c)` for a given `(m,c)`.

4. **Changing digest definitions or `routing_universe_hash` semantics.**

   * Altering *what* is digested (e.g. switching `zone_alpha_digest` from S2 surface to some other basis) without changing the contract version.
   * Changing the order or method of concatenation used to compute `routing_universe_hash` from the component digests.
   * Adding or removing components from the universe hash (e.g. including `s4_zone_counts` separately, or dropping `zone_floor_digest`) without a MAJOR bump and coordination with both 3A validation and 2B.

5. **Relaxing immutability or idempotence.**

   * Allowing S5 to overwrite existing `zone_alloc` or `zone_alloc_universe_hash` for the same `{seed, manifest_fingerprint}` with different contents.
   * Allowing multiple different “epochs” to exist under the same path and treating them as if they were a single logical snapshot.

Any of these require:

* a MAJOR bump for the relevant dataset version,
* updates to `schemas.3A.yaml`, `dataset_dictionary.layer1.3A.yaml`, and `artefact_registry_3A.yaml`, and
* coordinated changes with 2B and the 3A validation state, as they both interpret `zone_alloc` and `routing_universe_hash`.

---

### 12.5 Parameter set evolution vs `parameter_hash`

The governed parameter set 𝓟 includes, at least:

* `country_zone_alphas` (priors),
* `zone_floor_policy`,
* `zone_mixture_policy`,
* `day_effect_policy` (2B),
* any other policy that affects S1–S4 behaviour.

Binding rules:

1. **Any semantic change to priors or policies that affect S1–S4 MUST change `parameter_hash`.**

   * Changing the content of `country_zone_alphas`, `zone_floor_policy`, or `zone_mixture_policy` in a way that affects S1/S2/S3/S4 outputs requires a new `parameter_hash`.
   * Changing the day-effect policy (if the 2B contract says it affects routing/day-effect behaviour) likewise requires updating 𝓟 and computing a new `parameter_hash`.

2. **S5 must assume that, for a fixed `parameter_hash`, priors/policies are fixed.**

   * If S5 detects that any policy/prior artefact’s digest from `sealed_inputs_3A` does not match what S2/S3 expect for this `parameter_hash`, it MUST fail (precondition error), not proceed.

3. **Component digests are per-manifest, but semantics are per-parameter-set.**

   * You may choose to reuse the same `parameter_hash` across multiple manifests (`manifest_fingerprint` differing by e.g. `seed` or other non-parameter artefacts).
   * In such cases, S5’s `zone_alpha_digest`, `theta_digest`, `zone_floor_digest`, `day_effect_digest` **must** be identical across all manifests sharing that `parameter_hash`.

4. **Universe hash reflects both 𝓟 and allocation.**

   * Even if `parameter_hash` and priors/policies are unchanged, if `zone_alloc` changes (e.g. because S4 changed its integerisation contract or a bug was fixed), `zone_alloc_parquet_digest` and `routing_universe_hash` will change.
   * This is by design; 2B should detect such changes to avoid silently mixing incompatible routing universes.

---

### 12.6 Catalogue evolution (schemas, dictionary, registry)

S5’s outputs are tied tightly to the catalogue; changes there must be controlled.

1. **Schema evolution (`schemas.3A.yaml`).**

   * Adding optional fields to `#/egress/zone_alloc` or `#/validation/zone_alloc_universe_hash` is MINOR if they are optional and do not change required semantics.
   * Removing or changing the type/meaning of required fields is MAJOR (see §12.4).

2. **Dataset dictionary evolution.**

   * Changing the `id`, `path`, `partitioning`, or `schema_ref` for `zone_alloc` or `zone_alloc_universe_hash` is a breaking change and MUST be accompanied by:

     * a MAJOR bump, and
     * updates to all consumers (2B, validators).

3. **Artefact registry evolution.**

   * Adding new artefacts that do not affect S5’s outputs (e.g. extra diagnostics) is fine.
   * Changing the `manifest_key`, `path`, or `schema` for `zone_alloc` or `zone_alloc_universe_hash` is breaking and must be handled as above.

---

### 12.7 Deprecation strategy

When S5 needs to change, the following approach is REQUIRED:

1. **Introduce new behaviour alongside old.**

   * For example, if a more detailed universe hash is needed, introduce new optional fields (e.g. `zone_alloc_metadata_digest`) in a MINOR version first, while maintaining the existing `routing_universe_hash`.

2. **Signal deprecation.**

   * The S5 spec (and/or validation state) MAY include non-normative deprecation notes, such as:

     * “In version 2.0.0, `zone_alloc_parquet_digest` will be computed over a different canonical representation; this will be accompanied by an S5 MAJOR bump and updated validation logic.”

3. **Remove/alter only with MAJOR bump.**

   * When old fields or behaviours must be removed or repurposed, bump the MAJOR version and coordinate changes with all consumers:

     * S4/S5 validation logic,
     * 2B’s routing/day-effect configuration reader,
     * any offline analytics relying on these artefacts.

Historic artefacts (produced under earlier versions) MUST NOT be mutated to fit the new contract.

---

### 12.8 Cross-version operation

Because different manifests and parameter sets may use different S5 versions, consumers must be prepared to handle multiple versions.

1. **Per-run contract.**

   * For each run, the `version` of `zone_alloc` and `zone_alloc_universe_hash` defines the contract for that run’s egress and hash.
   * 2B and validators MUST inspect the `version` before interpreting these artefacts.

2. **Consumer strategies.**

   * Version-aware consumers SHOULD:

     * explicitly support known S5 versions (e.g. `1.x`, `2.x`), or
     * restrict themselves to the intersection of fields/behaviours common across versions they wish to handle.

3. **No retroactive upgrades.**

   * Existing `zone_alloc` and `zone_alloc_universe_hash` artefacts MUST NOT be rewritten in-place to match a new schema or hash definition.
   * If you need to “recompute” S5 under a new contract for an existing run, treat it as a new run:

     * new `manifest_fingerprint` and/or `run_id`, and
     * new `zone_alloc` and `zone_alloc_universe_hash` under the new contract.

---

Under these rules, 3A.S5 can evolve **safely and transparently**:

* small diagnostics or validation improvements are clearly backward-compatible;
* any change that could alter `zone_alloc` or the meaning of `routing_universe_hash` is clearly marked with a MAJOR bump and coordinated with 2B and validation;
* and no consumer ever has to guess what “universe” a given `zone_alloc` belongs to.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix records the symbols and shorthand used in the 3A.S5 design. It has **no normative force**; it’s here so S0–S5, 2B and validation talk about the same things in the same way.

---

### 13.1 Scalars, hashes & identifiers

* **`parameter_hash`**
  Layer-1 hash over the governed parameter set 𝓟 (priors, mixture, floor/bump policy, day-effect policy, etc.). Fixed for a family of runs that share the same configuration.

* **`manifest_fingerprint`**
  Layer-1 hash over the resolved manifest (including `parameter_hash` and sealed artefacts). Used as a partition token and as the identity of the “world” S0–S5 ran against.

* **`seed`**
  Layer-1 RNG seed (`uint64`) for the run. S5 itself is RNG-free but uses `seed` as part of its `zone_alloc` partition key and lineage.

* **`run_id`**
  Logical run identifier (string or u128-encoded). Used for correlation and run-reporting. Does not affect S5’s data-plane logic.

* **`merchant_id`**
  Merchant identity (`id64`), as defined in 1A and carried through S1–S4.

* **`legal_country_iso` / `country_iso`**
  ISO-3166 alpha-2 country code (e.g. `"GB"`, `"US"`).

  * S1/S3/S4/S5 use `legal_country_iso`.
  * S2 and some references use `country_iso`. They refer to the same value.

* **`tzid`**
  IANA time zone identifier (e.g. `"Europe/London"`), as defined by 2A and the zone-universe references (`Z(c)`).

---

### 13.2 Sets & domains

For a fixed `{seed, manifest_fingerprint}`:

* **`D` (S1 domain)**

  [
  D = {(m,c)} = {(merchant_id, legal_country_iso)\ \text{present in } s1_escalation_queue}.
  ]

* **`D_{\text{esc}}` (escalated domain)**

  [
  D_{\text{esc}} = {(m,c) \in D \mid is_escalated(m,c) = true}.
  ]

  Only these pairs are split across zones by 3A.

* **`Z(c)` (zone universe per country)**

  For a country `c`:

  [
  Z(c) = {\ tzid \mid (country_iso=c, tzid) \in s2_country_zone_priors}.
  ]

  This is the set of zones used by 3A for country `c`.

* **`D_{\text{S4}}` / `D_{\text{zone_alloc}}`**

  Domain of S4 / S5 over `(merchant, country, zone)`:

  [
  D_{\text{S4}} = D_{\text{zone_alloc}} = {(m,c,z) \mid (m,c) \in D_{\text{esc}},\ z \in Z(c)}.
  ]

  * `s4_zone_counts` and `zone_alloc` must each have exactly one row per triple in this set.

---

### 13.3 Counts & allocation quantities

For an escalated merchant×country pair `(m,c)`:

* **`site_count(m,c)`**
  Total outlet count for merchant `m` in country `c`, as defined by S1 / 1A:

  [
  N(m,c) = site_count(m,c) \in \mathbb{N},\quad N(m,c) \ge 1.
  ]

* **`zone_site_count(m,c,z)`**

  Integer count of outlets assigned to zone `z` in country `c` for merchant `m`, as output by S4:

  [
  zone_site_count(m,c,z) \in \mathbb{N},\quad zone_site_count(m,c,z) \ge 0.
  ]

  In S4 and S5: `zone_site_count`.

* **`zone_site_count_sum(m,c)`**

  Sum of zone counts for a given `(m,c)`:

  [
  zone_site_count_sum(m,c) = \sum_{z \in Z(c)} zone_site_count(m,c,z).
  ]

  Contract requires:

  [
  zone_site_count_sum(m,c) = site_count(m,c).
  ]

  In S4 and S5: `zone_site_count_sum`.

---

### 13.4 Priors & policy digests

S5 does not manipulate priors/policies; it only computes digests over them:

* **`zone_alpha_digest`**
  SHA-256 (hex) over the canonical representation of S2’s prior surface for this `parameter_hash` (e.g. concatenation of `s2_country_zone_priors` data files in lexicographic path order) or, equivalently, over the `country_zone_alphas` pack.

* **`theta_digest`**
  SHA-256 (hex) over the zone mixture policy artefact used by S1 (e.g. `zone_mixture_policy_3A`).

* **`zone_floor_digest`**
  SHA-256 (hex) over the zone floor/bump policy artefact (e.g. `zone_floor_policy_3A`).

* **`day_effect_digest`** (also referred to as `gamma_variance_digest` in some designs)
  SHA-256 (hex) over the day-effect policy artefact used by 2B (e.g. `day_effect_policy_v1`).

* **`zone_alloc_parquet_digest`**
  SHA-256 (hex) over the canonical concatenation of `zone_alloc` data file bytes in ASCII-lex path order under
  `data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/`.

---

### 13.5 Routing universe hash

* **`routing_universe_hash`**

  Combined SHA-256 (hex) over the concatenation of component digests:

  [
  routing_universe_hash = \mathrm{SHA256}\big(
  zone_alpha_digest ,|, \theta_digest ,|, zone_floor_digest ,|, day_effect_digest ,|, zone_alloc_parquet_digest
  \big),
  ]

  where `∥` is byte-wise concatenation of the ASCII encodings of each hex digest, in the specified order.

  * Stored:

    * once per row in `zone_alloc`,
    * once in `zone_alloc_universe_hash` as the canonical value for the manifest.

  * Used by Segment 2B and validation to check that they are operating in the same “routing universe” (same priors, mixture, floors, day-effect policy and zone allocation).

---

### 13.6 Datasets & artefacts

* **`s1_escalation_queue`**
  S1 output: `(merchant_id, legal_country_iso) → site_count, is_escalated, decision_reason`.

* **`s2_country_zone_priors`**
  S2 output: `(country_iso, tzid) → alpha_raw, alpha_effective, alpha_sum_country, prior/floor lineage`.

* **`s3_zone_shares`**
  S3 output: `(merchant_id, legal_country_iso, tzid) → share_drawn, share_sum_country`, plus RNG lineage.

* **`s4_zone_counts`**
  S4 output: `(merchant_id, legal_country_iso, tzid) → zone_site_count, zone_site_count_sum`, plus lineage.

* **`zone_alloc`**
  S5 egress: projection of `s4_zone_counts` plus priors/policies and `routing_universe_hash`. Cross-layer authority on zone-level counts.

* **`zone_alloc_universe_hash`**
  S5 validation artefact: per-manifest summary of component digests and `routing_universe_hash`.

* **`s0_gate_receipt_3A`**, **`sealed_inputs_3A`**
  S0 outputs: gate descriptor and sealed-input inventory; used by S5 to find and trust priors/policies and to ensure upstream segments are PASS.

---

### 13.7 Error codes & status (S5)

* **`error_code`**
  One of `E3A_S5_001 … E3A_S5_008` (see §9), e.g.:

  * `E3A_S5_001_PRECONDITION_FAILED`
  * `E3A_S5_003_DOMAIN_MISMATCH`
  * `E3A_S5_004_DIGEST_MISMATCH`
  * `E3A_S5_005_UNIVERSE_HASH_MISMATCH`
  * `E3A_S5_007_IMMUTABILITY_VIOLATION`

* **`status`**
  S5 outcome in logs/run-report:

  * `"PASS"` — `zone_alloc` and `zone_alloc_universe_hash` are valid and authoritative.
  * `"FAIL"` — the run ended with one of the error codes; S5 outputs MUST NOT be used.

* **`error_class`**
  Coarse category for the error, e.g.:

  * `"PRECONDITION"`, `"CATALOGUE"`, `"DOMAIN"`, `"DIGEST"`, `"UNIVERSE_HASH"`, `"OUTPUT_SCHEMA"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`.

---

These symbols are chosen to align with the rest of the 3A and Layer-1 documentation so that when you read across:

> S0 (sealed inputs) → S1 (escalation) → S2 (priors) → S3 (shares) → S4 (counts) → S5 (egress & universe hash),

the same `(m,c,z)`, `N(m,c)`, `Z(c)`, `zone_site_count`, and `routing_universe_hash` concepts appear consistently and unambiguously.

---
