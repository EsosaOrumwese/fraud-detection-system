# State 3A·S3 — Zone Share Sampling (Dirichlet draws)

## 1. Purpose & scope *(Binding)*

State **3A.S3 — Zone Share Sampling (Dirichlet draws)** is the **RNG-bearing state** in Segment 3A. It takes:

* the **escalated merchant×country pairs** from 3A.S1, and
* the **country→zone Dirichlet α-vectors** from 3A.S2,

and produces **stochastic zone share vectors** for each escalated pair, together with the corresponding RNG event logs, under the Layer-1 RNG discipline.

S3 does **not** integerise outlet counts or write final zone allocation egress; that is the responsibility of later 3A states.

Concretely, 3A.S3:

* **Consumes S1’s escalation decisions and S2’s priors as its sole authorities.**
  For each `(merchant_id, legal_country_iso)` that 3A.S1 has marked `is_escalated = true`, S3:

  * treats S1 as the **only** authority on whether that pair is in scope for zone allocation;
  * treats `legal_country_iso` as the country key `c`, and uses S2’s `s2_country_zone_priors@parameter_hash` to obtain the effective α-vector
    $$
    \boldsymbol{\alpha}(c) = \big(\alpha_\text{effective}(c,z)\big)_{z \in Z(c)},
    $$
    where `Z(c)` is the authoritative zone set for that country;
  * MUST NOT re-evaluate the mixture policy (S1) or reconstruct α from raw configs (S2 inputs) on its own.

* **Draws a Dirichlet zone-share vector per escalated merchant×country.**
  For each **escalated** `(merchant_id, legal_country_iso)` and its country’s zone set `Z(c)`, S3:

  * uses the Layer-1 Philox RNG engine and a dedicated, reproducible substream keyed by `(merchant_id, country_iso)` (exact keying defined later) to generate the required uniform variates;
  * transforms those variates into independent Gamma variates and normalises them to produce a **Dirichlet sample**:
    $$
    \Theta(m,c,z) \in (0,1), \quad z \in Z(c), \quad \sum_{z \in Z(c)} \Theta(m,c,z) = 1,
    $$
    where `Θ(m,c,·)` is the drawn zone-share vector for merchant×country `(m,c)`;
  * records per-zone shares in a seed+fingerprint-scoped dataset (e.g. `s3_zone_shares`), with one row per `(merchant_id, legal_country_iso, tzid)` for escalated pairs only.

  Non-escalated `(m,c)` pairs are **not** sampled by S3; they do not appear in the Dirichlet RNG events or in `s3_zone_shares`.

* **Emits RNG events under the Layer-1 RNG law.**
  S3 is the first 3A state that consumes RNG. It MUST:

  * use the Layer-1 Philox 2×64-10 engine and RNG envelope semantics defined in `schemas.layer1.yaml` (open-interval `u01`, `before/after/blocks/draws`, `rng_trace_log` discipline);
  * introduce a dedicated RNG event family (e.g. `rng_event_zone_dirichlet`) that records, for each escalated `(m,c)`:

    * the module/substream identifiers,
    * the counters and number of uniforms consumed,
    * identity (`merchant_id`, `country_iso`),
    * and any summary diagnostics needed for later replay and validation;
  * append these events to the shared RNG log and ensure `rng_trace_log` totals for the 3A.S3 module match the sum over all Dirichlet events, in line with Layer-1 RNG accounting.

  S3 MUST NOT modify RNG events from other states or deviate from the global RNG policy.

* **Publishes a stable, run-scoped zone-share surface for later 3A states.**
  S3’s per-zone share dataset (e.g. `s3_zone_shares`) is positioned as the **stochastic planning surface** for zone allocation:

  * it is partitioned by `{seed, manifest_fingerprint}`,
  * keyed by `(merchant_id, legal_country_iso, tzid)` for escalated pairs,
  * and contains, for each row, at minimum:

    * `share_drawn(m,c,z)`,
    * the relevant Lineage / RNG metadata needed by S4 and validators.

  Later 3A states (e.g. S4) MUST consume these shares as their **only stochastic input** when turning continuous shares into integer zone counts; they MUST NOT resample Dirichlet vectors themselves.

* **Respects upstream authority boundaries and state responsibilities.**
  S3:

  * relies on 3A.S0 outputs (`s0_gate_receipt_3A`, `sealed_inputs_3A`) as evidence that upstream segments (1A/1B/2A) are green and that S1/S2 policy artefacts are sealed;
  * treats S1’s `s1_escalation_queue` as the authority on “who is escalated” and MUST NOT escalate or de-escalate extra pairs;
  * treats S2’s `s2_country_zone_priors` as the authority on α-vectors and MUST NOT re-derive priors from raw policy artefacts.

  S3’s authority is limited to **how** the Dirichlet draws are performed and recorded; it does not redefine who is in scope or what priors they use.

* **Is deterministic *given* the RNG stream.**
  S3 is stochastic by design, but it MUST be deterministic **conditional on the Layer-1 RNG configuration**:

  * Given the same `(seed, parameter_hash, manifest_fingerprint, run_id)` and the same catalogue + sealed artefacts, S3 MUST:

    * consume the exact same sequence of Philox uniforms for each escalated `(m,c)`,
    * emit identical Dirichlet RNG events, and
    * produce identical `s3_zone_shares` rows (same shares, same ordering, same bytes).

  All variability in S3’s outputs across runs MUST be explainable by differences in `seed`/`run_id` or in the sealed priors/policies (via `parameter_hash`), never by implementation accident.

Out of scope for 3A.S3:

* S3 does **not** decide which merchant×country pairs are escalated (S1’s job).
* S3 does **not** modify or reinterpret α-priors (S2’s job).
* S3 does **not** integerise counts or produce final zone allocation egress; it only provides **continuous shares** for later states.
* S3 does **not** reason about arrivals, day effects or routing behaviour; those are handled by Layer-2 and Segment 2B.

Within these boundaries, 3A.S3’s scope is to provide a **reproducible, fully logged, Dirichlet-based zone-share realisation** for each escalated merchant×country pair, forming the stochastic heart of Segment 3A while staying tightly aligned with S1/S2 and the Layer-1 RNG and validation framework.

---

### Contract Card (S3) - inputs/outputs/authorities

**Inputs (authoritative; see Section 2 for full list):**
* `s0_gate_receipt_3A` - scope: FINGERPRINT_SCOPED; source: 3A.S0
* `sealed_inputs_3A` - scope: FINGERPRINT_SCOPED; source: 3A.S0
* `s1_escalation_queue` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3A.S1
* `s2_country_zone_priors` - scope: PARAMETER_SCOPED; scope_keys: [parameter_hash]; source: 3A.S2

**Authority / ordering:**
* S3 is the sole authority for Dirichlet draws and RNG event emission for 3A.

**Outputs:**
* `s3_zone_shares` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; gate emitted: none
* `rng_event_zone_dirichlet` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; gate emitted: none
* `rng_audit_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; gate emitted: none (shared append-only log)
* `rng_trace_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; gate emitted: none (shared append-only log)

**Sealing / identity:**
* S3 reads only S0 evidence plus S1/S2 outputs; any external policies or references remain sealed by S0.

**Failure posture:**
* Missing required inputs or RNG policy violations -> abort; no outputs published.

## 2. Preconditions & gated inputs *(Binding)*

This section defines **what MUST already hold** before 3A.S3 can run, and which inputs it is explicitly allowed to use. Anything outside these constraints is **out of spec** for S3.

S3 is **run-scoped**: it operates for a concrete quadruple
`(parameter_hash, manifest_fingerprint, seed, run_id)` and writes seed+fingerprint-scoped outputs plus RNG logs keyed by `(seed, parameter_hash, run_id)`.

---

### 2.1 Layer-1 & segment-level preconditions

Before 3A.S3 is invoked for a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, the orchestrator MUST ensure:

1. **Layer-1 identity is fixed.**

   * `parameter_hash` MUST already identify a closed governed parameter set 𝓟, as defined by Layer-1.
   * `manifest_fingerprint` MUST already have been computed for this run and be compatible with `parameter_hash` (i.e. the manifest includes the same parameter set sealed by S0).
   * `seed` (uint64) MUST be the Layer-1 RNG seed for this run.
   * `run_id` MUST be fixed for this execution and used consistently for RNG logs.

2. **3A.S0 has completed successfully for this `manifest_fingerprint`.**

   * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}` and `sealed_inputs_3A@fingerprint={manifest_fingerprint}` MUST exist and be schema-valid.
   * `s0_gate_receipt_3A.upstream_gates.segment_1A.status == "PASS"`,
     `segment_1B.status == "PASS"`,
     `segment_2A.status == "PASS"`.
   * If any of these conditions fail, S3 MUST treat this as a hard precondition failure and MUST NOT proceed.

3. **3A.S1 has produced an escalation queue for this `{seed, manifest_fingerprint}`.**

   * `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}` MUST exist and be schema-valid under `schemas.3A.yaml#/plan/s1_escalation_queue`.
   * The orchestrator MUST only trigger S3 once the S1 run for this `{seed, fingerprint}` has completed successfully (per S1’s own run-report status).
   * S3 MUST treat the absence or schema-invalidity of `s1_escalation_queue` as a hard precondition failure.

4. **3A.S2 has produced priors for this `parameter_hash`.**

   * `s2_country_zone_priors@parameter_hash={parameter_hash}` MUST exist and be schema-valid under `schemas.3A.yaml#/plan/s2_country_zone_priors`.
   * S3 MUST treat the absence or schema-invalidity of this dataset as a precondition failure; it MUST NOT attempt to re-derive priors directly from policy artefacts.

5. **Global RNG law is established.**

   * The Layer-1 RNG engine and envelopes (Philox 2×64-10, `rng_audit_log`, `rng_trace_log`, event envelope semantics) MUST already be defined in `schemas.layer1.yaml`.
   * Any Layer-1 or 3A-specific RNG policy artefacts that govern S3’s stream layout (e.g. which `(module, substream_label)` to use) MUST be part of 𝓟 and sealed via S0 (see next subsection).

---

### 2.2 Gated inputs from 3A.S0 (gate & whitelist)

S3 MUST treat 3A.S0 outputs as its **gate** and **input whitelist** for external artefacts.

1. **Gate descriptor: `s0_gate_receipt_3A`**
   S3 MUST read `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}` and:

   * validate it against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`,
   * confirm upstream gates for 1A/1B/2A are `"PASS"`,
   * confirm that the policy/prior artefacts relevant to S3 (S1 mixture policy, S2 prior pack & floor policy, RNG policy artefacts) are present in `sealed_policy_set` with stable IDs/versions.

   If `s0_gate_receipt_3A` is missing, invalid, or indicates any upstream gate is not PASS, S3 MUST fail and MUST NOT proceed.

2. **Sealed input inventory: `sealed_inputs_3A`**
   For **external** artefacts S3 reads directly (e.g. ISO/tz-universe references, RNG policy configs), S3 MUST:

   * confirm there is at least one row in `sealed_inputs_3A@fingerprint={manifest_fingerprint}` with matching `logical_id` and `path`, and
   * recompute SHA-256 over the artefact bytes and assert equality with the `sha256_hex` recorded in that row.

   If any external artefact S3 intends to read is missing from `sealed_inputs_3A`, or if digests disagree, S3 MUST fail.

   Note: `s1_escalation_queue` and `s2_country_zone_priors` are **internal 3A artefacts**, not external inputs; they are governed via the 3A catalogue and S1/S2 contracts, not via S0 sealing.

---

### 2.3 Data-plane inputs S3 is allowed to read

Within the sealed universe established by S0 and the 3A catalogue, S3 MAY read and interpret the following data-plane artefacts:

1. **3A.S1 escalation queue (required)**

   * Dataset: `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}`.
   * S3 MUST treat this as the sole authority on which merchant×country pairs are escalated:

     * Domain: all `(merchant_id, legal_country_iso)` with `site_count ≥ 1`.
     * S3 MUST use only rows where `is_escalated = true` as its Dirichlet worklist.
     * Pairs with `is_escalated = false` MUST NOT receive Dirichlet draws.

2. **3A.S2 country→zone priors (required)**

   * Dataset: `s2_country_zone_priors@parameter_hash={parameter_hash}`.
   * S3 MUST use this dataset to obtain α-vectors for each country:

     * For each country `c`, α-vector is
       $\boldsymbol{\alpha}(c) = {\alpha_\text{effective}(c,z)}_{z \in Z(c)}$.
     * S3 MUST NOT derive α from `country_zone_alphas` or `zone_floor_policy` artefacts directly.

3. **Country & zone universe references (structural)**
   S3 MAY read sealed reference artefacts (via `sealed_inputs_3A` and the catalogue) to confirm structural expectations:

   * `iso3166_canonical_2024` — to validate `legal_country_iso` values.
   * `country_tz_universe` (or equivalent) — to get `Z(c)` per country when needed to order zones consistently with S2.
   * These are used only to check that `s2_country_zone_priors` covers all zones in `Z(c)` and to define a deterministic `z` ordering; S3 MUST NOT alter these references.

S3 MUST express all business logic in terms of these artefacts and constants derived from them.

---

### 2.4 RNG configuration inputs

S3 is the first 3A state to consume RNG. It MUST respect Layer-1 RNG law, and any **configuration** for S3’s stream layout MUST be sealed.

Within `sealed_inputs_3A` and the catalogue, S3 MAY read:

1. **Layer-1 RNG policy artefacts**

   * e.g. a shared `rng_policy_layer1` that defines:

     * allowed PRNG algorithm (`philox2x64-10`),
     * envelope rules,
     * trace logging discipline.

2. **3A-specific RNG layout policy (if present)**

   * e.g. `zone_rng_policy_3A` or an extension to 2B’s `route_rng_policy_v1`, specifying:

     * `module`/`substream_label` names for Dirichlet events,
     * per-merchant or per-country substream keying,
     * allowed RNG budgets per event.

These artefacts MUST:

* be part of the governed parameter set 𝓟 for this `parameter_hash`,
* be listed in `s0_gate_receipt_3A.sealed_policy_set`, and
* appear in `sealed_inputs_3A` with `sha256_hex` digests matching their on-disk bytes.

S3 MUST NOT:

* use any RNG configuration not sealed in this manner,
* invent ad-hoc stream layout that violates Layer-1 RNG accounting.

---

### 2.5 Inputs S3 MUST NOT consume

To keep authority boundaries clean and avoid circular dependencies, S3 is explicitly forbidden from:

1. **Reading merchant- or site-level datasets outside S1/S2 surfaces.**

   * No direct reads of:

     * 1A `outlet_catalogue`,
     * 1B `site_locations`,
     * 2A `site_timezones`,
     * 2B routing datasets or logs.
   * S3’s domain is fully defined by S1; its α-vectors are fully defined by S2.

2. **Reading 2B plan or runtime artefacts.**

   * No reads of `s1_site_weights`, alias blobs, day-effects, routing logs, etc.
   * S3’s notion of zones is purely `(country_iso, tzid)` and is independent of 2B routing semantics.

3. **Reading any artefact not sealed in `sealed_inputs_3A` (for external inputs).**

   * Any reference/config not present in `sealed_inputs_3A` for this `manifest_fingerprint` MUST NOT influence S3’s behaviour.
   * Environment variables, local files, or command-line overrides MUST NOT alter S3’s RNG behaviour, domains, or priors.

4. **Re-deriving priors or escalation decisions.**

   * S3 MUST NOT:

     * re-classify merchant×country pairs (escalation is S1’s job), or
     * re-compute α-vectors from raw `country_zone_alphas` or floor policy artefacts (that is S2’s job).

5. **Using unsealed RNG sources.**

   * S3 MUST NOT use any RNG other than the Layer-1 Philox engine and substreams defined by sealed RNG policy.
   * It MUST NOT call system RNG or use non-deterministic sources.

---

### 2.6 Invocation-level assumptions

For a specific S3 run on `(parameter_hash, manifest_fingerprint, seed, run_id)`:

* The orchestrator MAY schedule S3 independently of S2/S1 as long as:

  * S0 has sealed inputs for `manifest_fingerprint`,
  * S1 has successfully produced `s1_escalation_queue@{seed,fingerprint}`, and
  * S2 has successfully produced `s2_country_zone_priors@parameter_hash`.

* S3’s outputs are:

  * `s3_zone_shares` partitioned by `{seed, fingerprint}`, and
  * RNG events/logs partitioned by `{seed, parameter_hash, run_id}`.

If any of these preconditions fail, S3 MUST treat the run as **invalid** and MUST NOT emit partial or approximate outputs.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes **exactly what S3 is allowed to use**, what each input is **authoritative for**, and where S3’s own authority **stops**. Anything outside these inputs, or used beyond the roles defined here, is out of spec for 3A.S3.

---

### 3.1 Catalogue & schema packs (shape, not behaviour)

S3 sits under the same catalogue and schema regime as the rest of Layer-1. It MUST treat the following as **shape authorities**, not things it can redefine:

1. **Schema packs**

   * `schemas.layer1.yaml` — defines:

     * RNG envelopes, `rng_audit_log`, `rng_trace_log`,
     * primitive types (`id64`, `iso2`, `iana_tzid`, `hex64`, `uint64`, etc.).
   * `schemas.ingress.layer1.yaml` — for reference shapes (ISO, tz-universe if present).
   * `schemas.2A.yaml` — for any 2A zone reference shapes reused.
   * `schemas.3A.yaml` — for S1/S2/S3 shapes (e.g. `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`).

   S3 MAY only use these to:

   * validate the shape of `s1_escalation_queue`, `s2_country_zone_priors`, and its own outputs, and
   * resolve `schema_ref` anchors for data and RNG events.

   S3 MUST NOT:

   * redefine primitive types,
   * alter RNG envelope semantics, or
   * change validation receipt structures defined at Layer-1.

2. **Dataset dictionaries & artefact registries**

   * `dataset_dictionary.layer1.{2A,3A}.yaml`
   * `artefact_registry_{2A,3A}.yaml`

   For every dataset S3 reads/writes, the dictionary/registry pair is the **only authority** on:

   * dataset ID,
   * path template and partition keys,
   * `schema_ref`, format,
   * lineage (`produced_by`, `consumed_by`), and role.

   S3 MUST resolve paths and schemas via the catalogue. Hard-coded paths, ad-hoc schemas or “magic” directory scans are out of spec.

---

### 3.2 3A internal inputs: S1 & S2 (business & prior authority)

Within the 3A segment, S3 depends on two internal surfaces:

1. **Escalation queue from S1 (`s1_escalation_queue`)**

   * Dataset: `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}`
   * Schema: `schemas.3A.yaml#/plan/s1_escalation_queue`

   Authority:

   * Defines the full set of merchant×country pairs with outlets:
     $$
     D = {(m,c)}
     $$
   * For each `(merchant_id=m, legal_country_iso=c)`:

     * `site_count(m,c)` — outlet count in 1A,
     * `is_escalated(m,c) ∈ {true,false}`,
     * `decision_reason` — why the pair is monolithic or escalated.

   S3 MUST:

   * derive its **Dirichlet worklist** as:
     $$
     D_{\text{esc}} = {(m,c) \in D \mid is\_escalated(m,c) = true}
     $$
   * use **only** `D_esc` as the set of merchant×country pairs for which it draws Dirichlet zone shares.

   S3 MUST NOT:

   * escalate any `(m,c)` with `is_escalated=false`,
   * de-escalate any `(m,c)` with `is_escalated=true`,
   * derive its own escalation decisions from other inputs.

   S1 is the sole authority on “who goes through zone allocation”.

2. **Country→zone priors from S2 (`s2_country_zone_priors`)**

   * Dataset: `s2_country_zone_priors@parameter_hash={parameter_hash}`
   * Schema: `schemas.3A.yaml#/plan/s2_country_zone_priors`

   Authority:

   * For each `country_iso = c`, defines the **effective Dirichlet α-vector**:
     $$
     \boldsymbol{\alpha}(c) = \big(\alpha_\text{effective}(c,z)\big)_{z \in Z(c)}
     $$
   * `Z(c)` is implicitly determined by the set of `tzid` values present for that `country_iso`.

   S3 MUST:

   * for any `(m,c) ∈ D_esc`, obtain `Z(c)` and the α-vector **only** from `s2_country_zone_priors`,
   * use `alpha_effective(c,z)` as the Dirichlet concentration for zone `z` in `Z(c)`.

   S3 MUST NOT:

   * re-parse `country_zone_alphas` or `zone_floor_policy` directly to obtain α,
   * change or rescale α-vectors, except as allowed by a **separately specified** S3 RNG policy (and then only in a way that does not contradict S2’s contract; ideally not at all).

S2 is the sole authority on priors; S3 only *uses* them.

---

### 3.3 Zone-universe references (structural authority)

S3 needs to know the **zone universe per country** to ensure consistency between priors and draws, and to define a consistent ordering of zones.

Within the sealed universe (via S0) and the catalogue, S3 MAY read:

1. **Country reference**

   * `iso3166_canonical_2024` (or equivalent), as a structural check:

     * verify that all `legal_country_iso` values from `s1_escalation_queue` and `s2_country_zone_priors` are valid ISO codes.

2. **Country→tzid universe**

   * Either:

     * a sealed `country_tz_universe` dataset with rows `(country_iso, tzid)`, or
     * the ingress tz geometry `tz_world_2025a`, from which the Layer-1 zone universe `Z(c)` can be derived.

Authority:

* Defines the set `Z(c)` of tzids valid for each country.
* S3 MAY use this only to check that:

  * S2’s priors cover all tzids in `Z(c)`, and
  * `s3_zone_shares` rows for `(m,c,z)` use only `z ∈ Z(c)`.

S3 MUST NOT:

* alter the zone universe,
* introduce additional tzids not present in `Z(c)`,
* drop tzids from `Z(c)` in its outputs.

Where ordering of `z ∈ Z(c)` is needed (for deterministic mapping uniforms→vector components), S3 MUST use a deterministic ordering (e.g. ASCII-lex over `tzid`) consistent with S2/validation docs.

---

### 3.4 RNG inputs & envelopes (stochastic authority)

S3 is the first 3A state that **consumes RNG**. It MUST:

1. **Use the Layer-1 RNG engine and envelopes**

   * Algorithm: **Philox 2×64-10** (as defined in `schemas.layer1.yaml`).
   * Uniforms: open-interval `u ∈ (0,1)` mapping.
   * Envelope: each RNG event has `before_counter`, `after_counter`, `blocks`, `draws` semantics as per Layer-1 S0; `rng_trace_log` totals must match event sums.

2. **Conform to RNG policy artefacts**

   * Any RNG policy artefact (Layer-1 or 3A-specific) that S3 uses (e.g. `zone_rng_policy_3A` or a shared `route_rng_policy_v1`) MUST be:

     * part of 𝓟,
     * sealed in `s0_gate_receipt_3A.sealed_policy_set`, and
     * present in `sealed_inputs_3A` with matching digest.

   These policies MAY define:

   * `module` and `substream_label` to use for Dirichlet events (e.g. `module="3A.S3"`, `substream_label="zone_dirichlet"`).
   * Keying scheme for substreams (e.g. keyed by `(merchant_id, country_iso)` or by a hash of them).
   * Expected RNG budgets per Dirichlet event (number of blocks/draws).

3. **Use only Philox + policy-approved substreams**

   S3 MUST NOT:

   * use any RNG other than Philox 2×64-10,
   * draw additional uniforms outside the declared Dirichlet event budgets,
   * open substreams or modules not defined or allowed by the RNG policy,
   * use system RNG or non-deterministic sources.

The actual Dirichlet sampling algorithm (Gamma draws + normalisation) MUST be built strictly on Philox `u01` draws and respect the envelope and trace laws.

---

### 3.5 S3’s own authority vs upstream and downstream

S3’s **only new authority** in Segment 3A is:

* the stochastic zone share vector `Θ(m,c,z)` for escalated `(m,c)`, and
* the Philox counters and RNG event trace that record how those shares were drawn.

Within that:

* S3 **owns**:

  * the mapping from `(seed, parameter_hash, manifest_fingerprint, run_id, m, c)` to:

    * the sequence of uniforms consumed, and
    * the resulting zone share vector `Θ(m,c,·)` over `Z(c)`,
  * the precise representation of those shares in `s3_zone_shares` and in the Dirichlet RNG event logs.

* S3 does **not** own:

  * the domain of `(m,c)` pairs (that’s S1),
  * the α-vectors used as Dirichlet parameters (that’s S2),
  * the integer zone counts or final zone allocation egress (later 3A states),
  * any routing or arrival semantics (Segment 2B / Layer-2).

Downstream:

* S4 and validation states MUST treat:

  * `s1_escalation_queue` as the **domain authority**,
  * `s2_country_zone_priors` as the **Dirichlet parameter authority**, and
  * `s3_zone_shares` + RNG events as the **sampling authority**.

None of them may re-sample Dirichlet vectors for the same `(m,c)` under the same `(seed, parameter_hash, manifest_fingerprint, run_id)`.

---

### 3.6 Explicit “MUST NOT” list for S3

To keep boundaries sharp, S3 is explicitly forbidden from:

* **Re-classifying merchant×country pairs**

  * MUST NOT change `is_escalated`; MUST NOT process non-escalated pairs.

* **Re-deriving priors from raw configs**

  * MUST NOT read `country_zone_alphas` or floor/bump policy directly to compute α; MUST use `s2_country_zone_priors`.

* **Reading merchant/site/arrival data outside S1/S2 surfaces**

  * No direct access to `outlet_catalogue`, `site_locations`, `site_timezones`, arrivals or routing logs.

* **Reading any artefact not in `sealed_inputs_3A` (for external refs/config)**

  * All reference and config artefacts must be sealed; anything else is out of bounds.

* **Using unsealed or non-Philox RNG**

  * No `random()` from system libraries, no other PRNGs.

Within these boundaries, S3’s input world is:

* **S0**: gate + whitelist,
* **S1**: escalated merchant×country domain,
* **S2**: country→zone α-vectors,
* **Layer-1/ingress**: structural country/zone references,
* **RNG policy**: Philox configuration + substream layout,

and S3’s authority is strictly limited to turning those into a reproducible Dirichlet draw per escalated merchant×country pair.

---

## 4. Outputs (datasets & logs) & identity *(Binding)*

3A.S3 produces **one new dataset** and writes to the **shared Layer-1 RNG logs**. Together, these form the authoritative record of:

* which escalated merchant×country pairs received Dirichlet draws,
* what zone-share vector was drawn for each, and
* exactly how many Philox uniforms were consumed to do so.

S3 does **not** emit any final zone-allocation egress or validation bundles.

---

### 4.1 Overview of S3 outputs

For a given run `(parameter_hash, manifest_fingerprint, seed, run_id)`, S3 MUST produce:

1. **`s3_zone_shares`** — A seed+fingerprint-scoped table with the **drawn zone share** for each `(merchant_id, legal_country_iso, tzid)` where the pair `(merchant_id, legal_country_iso)` is escalated. This is the **stochastic planning surface** for later zone integerisation (S4).

2. **Dirichlet RNG events** — A new RNG event family (e.g. `rng_event_zone_dirichlet`) appended to the Layer-1 RNG logs, with one event per escalated `(merchant_id, legal_country_iso)`; this records Philox counters and per-event budgets, enabling replay and accounting.

No other persistent outputs are in scope for S3.

---

### 4.2 `s3_zone_shares` — per-merchant×country×zone share surface

#### 4.2.1 Domain & identity

For a given `{seed, manifest_fingerprint}`:

* Let `D_esc` be the set of escalated merchant×country pairs:

  $$
  D_{\text{esc}} = { (m,c) \mid (m,c) \in s1\_escalation\_queue, is\_escalated(m,c) = true }.
  $$

* For each `c`, let `Z(c)` be the zone set for that country as implied by `s2_country_zone_priors` (set of `tzid` values where `country_iso=c`).

Then the **domain** of `s3_zone_shares` is:

$$
D_{\text{S3}} = { (m,c,z) \mid (m,c) \in D_{\text{esc}}, z \in Z(c) }.
$$

Binding requirements:

* For each `(m,c) ∈ D_esc` and each `z ∈ Z(c)`, S3 MUST produce **exactly one** row in `s3_zone_shares` with `(merchant_id=m, legal_country_iso=c, tzid=z)`.
* There MUST be **no** rows for:

  * any `(m,c)` with `is_escalated = false`, or
  * any `tzid` not in `Z(c)` for that country.

**Logical primary key** (within a `{seed, fingerprint}` partition):

$$
(\text{merchant\_id}, \text{legal\_country\_iso}, \text{tzid})
$$

There MUST NOT be duplicate rows for a given `(merchant_id, legal_country_iso, tzid)`.

#### 4.2.2 Partitioning & path

` s3_zone_shares` is **run-scoped** (seed+fingerprint), like other L1/L2 per-run plan tables.

* Partition keys:

  ```text
  ["seed", "fingerprint"]
  ```

* Conceptual path template (final value in dataset dictionary):

  ```text
  data/layer1/3A/s3_zone_shares/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...
  ```

Binding rules:

* Each partition is uniquely identified by `{seed, manifest_fingerprint}`.
* Every row in a partition MUST have:

  * `seed` equal to the path token `{seed}`, and
  * `manifest_fingerprint` equal to the path token `{manifest_fingerprint}`.

No other partition keys (e.g. `parameter_hash`, `run_id`) may be used for `s3_zone_shares`.

#### 4.2.3 Required columns & meaning

Each row in `s3_zone_shares` MUST contain, at minimum:

* **Lineage / partitions**

  * `seed` — Layer-1 run seed (`uint64`, from `schemas.layer1.yaml`).
  * `manifest_fingerprint` — `hex64`, same for all rows in this partition.

* **Identity**

  * `merchant_id` — `id64`, matching 1A and S1.
  * `legal_country_iso` — `iso2`, matching S1 and S2.
  * `tzid` — `iana_tzid`, with `(legal_country_iso, tzid)` present in `s2_country_zone_priors` for the corresponding `parameter_hash`.

* **Shares**

  * `share_drawn`

    * Type: `number`,
    * Range: `[0.0, 1.0]`.
    * The realised Dirichlet zone share for this `(m,c,z)` under the current `seed` and prior α’s,
      coming from the sampled vector `Θ(m,c,·)`.

  * `share_sum_country`

    * Type: `number`,
    * Range: `(0.0, 1.0 + ε]` for small ε due to floating-point error.
    * The sum over zones for this `(m,c)`:
      [
      share_sum_country(m,c) = \sum_{z \in Z(c)} share_drawn(m,c,z),
      ]
      repeated on each row for that `(m,c)`.
    * By design, this SHOULD be ≈ 1; deviations beyond tolerance are a validation failure.

* **Prior lineage**

  * `alpha_sum_country`

    * Type: `number`, `exclusiveMinimum: 0.0`.
    * Copy of `alpha_sum_country(c)` from `s2_country_zone_priors` (same for all zones of country `c`).

  * `prior_pack_id`, `prior_pack_version`

    * Strings, identical to S2’s fields; identify the prior pack used.

  * `floor_policy_id`, `floor_policy_version`

    * Strings, identical to S2’s fields; identify the floor/bump policy applied in S2.

* **RNG lineage (per `(m,c,z)` row)**

  * `rng_module` — string, e.g. `"3A.S3"`.
  * `rng_substream_label` — string, e.g. `"zone_dirichlet"`.
  * `rng_stream_id` — implementation-defined but deterministic ID tying this row back to its Dirichlet RNG event (e.g. hash of `(merchant_id, country_iso)` or explicit field).
  * `rng_event_id` — optional: identifier linking to the specific `rng_event_zone_dirichlet` event (e.g. an integer index or a UUID-like hash).

These RNG lineage fields allow validators to join `s3_zone_shares` rows to `rng_event_zone_dirichlet` events and replay the Dirichlet sampling if needed.

Additional diagnostic columns (e.g. per-zone α-as-seen-by-S3) MAY be added in future minor versions but MUST NOT change the meaning of the required fields.

#### 4.2.4 Writer-sort & immutability

Within each `{seed, fingerprint}` partition, S3 MUST write `s3_zone_shares` rows in a deterministic order, e.g.:

1. `merchant_id` ascending,
2. `legal_country_iso` ascending,
3. `tzid` ascending.

Ordering is **not** semantically authoritative; all semantics come from keys and field values. Ordering exists only to guarantee:

* re-running S3 with the same inputs yields byte-identical datasets.

Once written for a given `{seed, fingerprint}`:

* `s3_zone_shares` MUST be treated as a **snapshot**,
* re-runs MUST either:

  * detect byte-identical content and leave it unchanged; or
  * treat differences as an immutability violation and fail without overwriting.

---

### 4.3 RNG event logs — `rng_event_zone_dirichlet` & trace entries

S3 writes to the **shared Layer-1 RNG logs**; it does not own those datasets, but it introduces a new event family and uses them in a specific way.

#### 4.3.1 Event family identity

S3 MUST use a dedicated RNG event family, defined in `schemas.layer1.yaml` (or the Layer-1 RNG schema), conceptually named:

* `rng_event_zone_dirichlet`

Each event corresponds to **one** Dirichlet sample for one `(merchant_id, country_iso)` pair.

**Partitioning & path (as per Layer-1 RNG contracts)**:

* RNG events: partitioned by `[seed, parameter_hash, run_id]` (consistent with other segments).
* `manifest_fingerprint` MAY be present as a column but is not a partition key for RNG logs.
* `module` MUST identify 3A.S3 (e.g. `"3A.S3"`).
* `substream_label` MUST identify Dirichlet events (e.g. `"zone_dirichlet"`).

#### 4.3.2 Required event fields & envelope

Each `rng_event_zone_dirichlet` MUST, at minimum, include:

* **Envelope (Layer-1 requirements)**

  * `seed`
  * `parameter_hash`
  * `run_id`
  * `module` (e.g. `"3A.S3"`)
  * `substream_label` (e.g. `"zone_dirichlet"`)
  * `counter_before`, `counter_after` — 128-bit Philox counters at start/end of this event’s draws.
  * `blocks` — integer count of Philox blocks consumed (MUST equal `counter_after - counter_before`).
  * `draws` — string or integer representing number of `u01` uniforms consumed for this Dirichlet sample.

* **Identity & linkage**

  * `merchant_id`
  * `country_iso` (same as `legal_country_iso` for S1/S2/S3; used to select `Z(c)`).
  * `rng_stream_id` — matches `s3_zone_shares` rows for `(m,c,·)`.

* **Dirichlet shape metadata**

  * `zone_count` — |Z(c)|, number of zones in the Dirichlet vector.
  * Optionally: `alpha_sum_country` and minimal/maximal α values, for validation.

There MUST be exactly **one** `rng_event_zone_dirichlet` per escalated `(merchant_id, country_iso)`.

#### 4.3.3 RNG trace log integration

S3 MUST also append appropriate rows to the Layer-1 `rng_trace_log`, summarising:

* cumulative `blocks` and `draws` per `(seed, parameter_hash, run_id, module, substream_label)`,
* with totals equal to the sum across all `rng_event_zone_dirichlet` events for this run.

Trace-log schema and path are defined at Layer-1; S3 must conform (no extra S3-specific trace datasets).

---

### 4.4 Consumers & authority of S3 outputs

**`s3_zone_shares`** and `rng_event_zone_dirichlet` together form S3’s **authority surface**:

* **Required consumers:**

  * 3A.S4 (zone integerisation) MUST:

    * derive per-merchant×country zone counts from `s3_zone_shares` (combined with 1A total outlet counts),
    * and treat `share_drawn(m,c,z)` as the sole stochastic input for splitting counts across zones.
  * 3A validation state MUST:

    * use `rng_event_zone_dirichlet` + `rng_trace_log` to verify RNG usage, and
    * replay Dirichlet draws from the Uniforms to validate `share_drawn(m,c,z)` in `s3_zone_shares`.

* **Optional consumers:**

  * Diagnostics and analytics tools MAY read `s3_zone_shares` to understand the distribution of mass across zones for escalated merchants, subject to access controls and volume constraints.

S3 does **not** introduce any new public egress dataset; these surfaces are internal to 3A + validation, but their semantics are binding and must be treated as authoritative for:

* “what share did each zone get for each escalated merchant×country?”, and
* “how was RNG used to produce those shares?”.

---

### 4.5 Explicit non-outputs

For clarity, S3 does **not** emit:

* any dataset that changes or re-states α-priors (that remains S2’s job),
* any final zone allocation counts or egress (that belongs to S4+),
* any validation bundle or `_passed.flag` for 3A (segment-level PASS remains a later state’s responsibility).

Within these constraints, `s3_zone_shares` and the `rng_event_zone_dirichlet` family are the **only** artefacts 3A.S3 is responsible for producing, and they are the **sole authorities** on the realised zone-share vectors and associated RNG activity for each escalated merchant×country pair.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes where S3’s outputs **live** in the authority chain:

* which JSON-Schema anchors define their shapes,
* how they appear in the Layer-1 dataset dictionary, and
* how they are registered in the 3A artefact registry.

Everything here is normative for **`s3_zone_shares`** and the **Dirichlet RNG event family**.

---

### 5.1 Segment schema pack for `s3_zone_shares`

3A.S3 uses the existing segment schema pack:

* **Schema pack ID:** `schemas.3A.yaml`
* **Role:** shape authority for all Segment-3A datasets (S0–S7).

`schemas.3A.yaml` MUST:

1. Reuse Layer-1 primitive definitions via `$ref: "schemas.layer1.yaml#/$defs/…"`:

   * `id64`, `iso2`, `iana_tzid`, `hex64`, `uint64`, standard numeric types, etc.
2. Define a dedicated anchor for S3’s per-zone share dataset:

   * `#/plan/s3_zone_shares`

No other schema pack may define the shape of `s3_zone_shares`.

---

### 5.2 Schema anchor: `schemas.3A.yaml#/plan/s3_zone_shares`

The anchor `#/plan/s3_zone_shares` defines the **row shape** of S3’s per-zone share table.

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

  * `tzid`

    * `$ref: "schemas.layer1.yaml#/$defs/iana_tzid"`

  * `share_drawn`

    * `type: "number"`
    * `minimum: 0.0`
    * `maximum: 1.0`

  * `share_sum_country`

    * `type: "number"`
    * `exclusiveMinimum: 0.0`

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

  * `rng_module`

    * `type: "string"`

  * `rng_substream_label`

    * `type: "string"`

  * `rng_stream_id`

    * `type: "string"`

* **Optional properties (diagnostic / linkage):**

  * `rng_event_id`

    * `type: "string"` (identifier tying rows back to a specific Dirichlet RNG event; format is implementation-chosen but stable).

  * `notes`

    * `type: "string"` (free-text diagnostics).

  * Any further diagnostic fields MAY be added in later MINOR/MAJOR versions, provided they do not change the semantics of the required fields.

* **Additional properties:**

  * At the top level, S3 v1 MUST set
    `additionalProperties: false`
    to prevent shape drift, except when extended under a new schema / version per §12.

This anchor MUST be used as the `schema_ref` for `s3_zone_shares` in the dataset dictionary.

---

### 5.3 Dataset dictionary entry: `dataset_dictionary.layer1.3A.yaml`

The Layer-1 dataset dictionary for subsegment 3A MUST define S3’s dataset as follows (conceptual YAML):

```yaml
datasets:
  - id: s3_zone_shares
    owner_subsegment: 3A
    description: Dirichlet share draws per merchant×country×zone.
    version: '{seed}.{manifest_fingerprint}'
    format: parquet
    path: data/layer1/3A/s3_zone_shares/seed={seed}/manifest_fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    ordering: [merchant_id, legal_country_iso, tzid]
    schema_ref: schemas.3A.yaml#/plan/s3_zone_shares
    lineage:
      produced_by: 3A.S3
      consumed_by: [3A.S4, 3A.S5]
    final_in_layer: false
    pii: false
    licence: Proprietary-Internal
```

Binding points:

* `id` MUST be `s3_zone_shares` under `owner_subsegment: 3A`.
* `partitioning` MUST be exactly `[seed, fingerprint]`.
* `path` MUST contain `seed={seed}` and `fingerprint={manifest_fingerprint}` and no other partition tokens.
* `schema_ref` MUST be `schemas.3A.yaml#/plan/s3_zone_shares`.
* `ordering` expresses the deterministic writer-sort; consumers MUST NOT ascribe semantics beyond reproducibility.

Any alternative ID, path template, partitioning or schema_ref for S3’s zone share dataset is out of spec.

---

### 5.4 Artefact registry entry: `artefact_registry_3A.yaml`

For each `(seed, manifest_fingerprint)` where S3 runs, the 3A artefact registry records `s3_zone_shares` as:

```yaml
- manifest_key: mlr.3A.s3.zone_shares
  name: "Segment 3A S3 zone share draws"
  subsegment: "3A"
  type: "dataset"
  category: "plan"
  path: data/layer1/3A/s3_zone_shares/seed={seed}/manifest_fingerprint={manifest_fingerprint}/
  schema: schemas.3A.yaml#/plan/s3_zone_shares
  semver: '1.0.0'
  version: '{seed}.{manifest_fingerprint}'
  digest: '<sha256_hex>'
  dependencies:
    - mlr.3A.s1.escalation_queue
    - mlr.3A.s2.country_zone_priors
  source: internal
  owner: {owner_team: "mlr-3a-core"}
  cross_layer: true
```

Binding requirements:

* `manifest_key` MUST be `mlr.3A.s3.zone_shares`.
* `path`/`schema` MUST match the dataset dictionary entry.
* `version` MUST encode `{seed}.{manifest_fingerprint}`; contract versioning remains in `semver`.
* Dependencies MUST include, at minimum, the escalation queue and prior surface listed above. If additional artefacts become required (e.g. extra policy packs), the registry entry and this spec MUST be updated in lockstep.

The registry entry MUST remain consistent with the dictionary entry and the actual stored dataset (path↔embed equality, digest correctness).

---

### 5.5 RNG event family schema & catalogue links

The Dirichlet RNG events are catalogued at the Layer-1 level, not as a 3A dataset, but S3 imposes specific expectations on their schema and registration.

#### 5.5.1 Schema anchor in `schemas.layer1.yaml`

Layer-1 MUST expose a dedicated RNG event anchor for S3, conceptually:

* `schemas.layer1.yaml#/rng/events/zone_dirichlet`

This anchor MUST define an **object** with at least:

* `seed` — `uint64`
* `parameter_hash` — `hex64`
* `run_id` — string or u128 encoded as string
* `module` — string, e.g. `"3A.S3"`
* `substream_label` — string, e.g. `"zone_dirichlet"`
* `counter_before`, `counter_after` — 128-bit counters (representation as per existing RNG schema)
* `blocks` — integer ≥ 0
* `draws` — integer or decimal string representing number of `u01` uniforms consumed
* `merchant_id` — `id64`
* `country_iso` — `iso2`
* `zone_count` — integer ≥ 1
* Optional: `alpha_sum_country`, min/max α or other diagnostics.

S3 MUST emit only events conforming to this anchor for Dirichlet draws.

#### 5.5.2 RNG logs dataset & registry entries (Layer-1)

The RNG event stream (Dirichlet plus other families) is defined by Layer-1; for S3 the binding requirements are:

* Dirichlet events MUST be written into the standard RNG events dataset, whose:

  * dataset ID,
  * path pattern (partitioning by `seed, parameter_hash, run_id`), and
  * `schema_ref`
    are defined in Layer-1’s dictionary (e.g. `rng_events@seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` with `schema_ref` pointing to a union of event types including `zone_dirichlet`).

* `artefact_registry_layer1` MUST include:

  * an artefact key for RNG events (e.g. `mlr.layer1.rng_events`), and
  * `schemas.layer1.yaml#/rng/events/zone_dirichlet` in its schema union.

S3 MUST NOT introduce a separate, segment-specific RNG dataset; it plugs into the existing Layer-1 RNG logging infrastructure.

---

### 5.6 No additional S3 datasets in this contract version

Under this version of the spec:

* 3A.S3 MUST NOT register or emit any datasets beyond:

  * `s3_zone_shares`, and
  * its contributions to the Layer-1 RNG events/log/trace infrastructure.

Any additional S3 dataset (e.g. separate diagnostics, summaries) MUST:

1. Be introduced via new schema anchors in `schemas.3A.yaml`.
2. Get its own `datasets` entry in `dataset_dictionary.layer1.3A.yaml`.
3. Be registered in `artefact_registry_3A.yaml` with its own `manifest_key`, `path`, `schema`, and dependencies.

Until such changes are made under §12 (change control), the shapes and catalogue links defined above are the **only** valid ones for S3’s outputs.

---

## 6. Deterministic algorithm (with RNG) **(Binding)**

This section defines the **exact behaviour** of 3A.S3. The algorithm is:

* **Deterministic conditional on RNG**:
  Given `(parameter_hash, manifest_fingerprint, seed, run_id)` and a fixed catalogue, S3 must:

  * consume the same sequence of Philox uniforms,
  * produce the same Dirichlet events, and
  * write byte-identical `s3_zone_shares`.

* **Catalogue- and policy-driven**:
  All inputs are discovered through S0 (`sealed_inputs_3A`), the 3A dictionaries/registries, and S1/S2 outputs.

* **RNG-bounded and fully accounted**:
  Every uniform is accounted for via `rng_event_zone_dirichlet` events and `rng_trace_log` totals under the Layer-1 RNG law.

No step may use non-Philox RNG or wall-clock time.

---

### 6.1 Phase overview

For a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, S3 executes in five phases:

1. **Resolve S0/S1/S2 & catalogue.**
   Check preconditions and load references.

2. **Construct escalated worklist & join to priors.**
   Form `D_esc` (escalated `(m,c)` pairs), derive `Z(c)` and α-vectors per country.

3. **For each escalated `(m,c)`, define a deterministic RNG substream.**
   Establish Philox stream keying for Dirichlet events.

4. **For each escalated `(m,c)`, draw a Dirichlet vector over `Z(c)` using Philox.**
   Emit one RNG event and populate `s3_zone_shares` rows.

5. **Write `s3_zone_shares` and update RNG trace logs.**
   Enforce partitioning, writer-sort, and idempotence.

---

### 6.2 Phase 1 — Resolve S0/S1/S2 & catalogue

**Step 1 – Fix run identity**

S3 is invoked with:

* `parameter_hash` (hex64),
* `manifest_fingerprint` (hex64),
* `seed` (uint64),
* `run_id` (string / u128-encoded).

S3 MUST:

* validate formats,
* treat `(seed, parameter_hash, manifest_fingerprint, run_id)` as immutable for the run,
* embed them consistently into RNG events and datasets according to Layer-1 rules.

**Step 2 – Load S0 artefacts**

Using the 3A dictionary/registry, resolve and read:

* `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`,
* `sealed_inputs_3A@fingerprint={manifest_fingerprint}`.

S3 MUST:

* validate both against their schemas (`#/validation/s0_gate_receipt_3A`, `#/validation/sealed_inputs_3A`),
* assert that upstream segments 1A/1B/2A have status `"PASS"` in `upstream_gates`.

Failure ⇒ abort S3 (no outputs).

**Step 3 – Load S1 escalation queue**

Resolve and read:

* `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}` with `schema_ref: schemas.3A.yaml#/plan/s1_escalation_queue`.

S3 MUST:

* validate this dataset;
* treat its domain
  $$
  D = {(m,c)}
  $$
  and `is_escalated` flags as authoritative for merchant×country escalation.

**Step 4 – Load S2 prior surface**

Resolve and read:

* `s2_country_zone_priors@parameter_hash={parameter_hash}` with `schema_ref: schemas.3A.yaml#/plan/s2_country_zone_priors`.

S3 MUST:

* validate it,
* derive, for each `country_iso = c`, the zone set:

  $$
  Z(c) = {z \mid (c,z)\ \text{appears in}\ s2\_country\_zone\_priors}.
  $$

---

### 6.3 Phase 2 — Construct escalated worklist & join priors

**Step 5 – Build escalated `(m,c)` worklist**

From `s1_escalation_queue`, S3 defines:

$$
D_{\text{esc}} = { (m,c) \in D \mid is\_escalated(m,c) = true }.
$$

S3 MUST:

* ensure this set is deterministic, e.g. by collecting and later iterating in the order:

  1. `merchant_id` ascending,
  2. `legal_country_iso` ascending.

This ordering defines the **event order** for Dirichlet draws.

**Step 6 – Check country coverage in S2**

Let `C_esc` be the set of `legal_country_iso` in `D_esc`. S3 MUST:

* for each `c ∈ C_esc`, check that S2 provides priors:

  * there exists at least one row in `s2_country_zone_priors` with `country_iso = c`.

If any `c ∈ C_esc` has no matching rows in S2 ⇒ S3 MUST fail (prior surface incomplete for an escalated country; error handled elsewhere).

**Step 7 – Derive consistent zone ordering per country**

For each country `c` that appears in `C_esc`, S3 MUST:

* derive a per-country ordered zone list `Z_ord(c)` from `s2_country_zone_priors`:

  * gather all rows with `country_iso = c`,
  * sort them by `tzid` ascending (ASCII) to obtain an ordered list
    $$
    Z_{\text{ord}}(c) = [z_1, z_2, \dots, z_{k(c)}].
    $$

* construct the corresponding α-vector:

  * `alpha_effective(c, z_i)` as given by S2, in this same order.

This ordering MUST be used consistently:

* when sampling Dirichlet vectors, and
* when writing `s3_zone_shares` rows.

**Step 8 – Join necessary prior metadata**

For each country `c`:

* read `alpha_sum_country(c)` from any row in `s2_country_zone_priors` for that `c` (all rows must agree);
* record `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version` (must be constant across all S2 rows for this `parameter_hash`).

These values will be repeated on all `s3_zone_shares` rows for escalated `(m,c)`.

---

### 6.4 Phase 3 — Define deterministic RNG substreams

**Step 9 – Select RNG policy & event family**

From `sealed_inputs_3A` and `s0_gate_receipt_3A.sealed_policy_set`, S3 locates any RNG policy artefact that governs S3 (if present). From that, and/or Layer-1 RNG spec, S3 MUST:

* set `module = "3A.S3"` (or equivalent agreed string),
* set `substream_label = "zone_dirichlet"` (or equivalent),
* define a deterministic mapping from `(merchant_id=m, country_iso=c)` to an RNG stream identifier `rng_stream_id`.

The exact mapping from `(seed, parameter_hash, run_id, rng_stream_id)` to Philox counters is defined by Layer-1; S3 MUST use that mapping and MUST NOT override it.

**Step 10 – Define event order and stream keying**

S3 MUST:

* iterate over `D_esc` in a **fixed deterministic order**, e.g.:

  1. sort `D_esc` by `merchant_id` ascending, then
  2. by `legal_country_iso` ascending.

For each `(m,c)` in that order:

* compute `rng_stream_id` as a deterministic function of `(m,c)` and possibly `parameter_hash` (e.g. hashing the tuple `(module, "zone_dirichlet", merchant_id, country_iso)`);
* use `(seed, parameter_hash, run_id, module, substream_label, rng_stream_id)` to identify the Philox stream for this event.

S3 MUST NOT depend on physical row order in `s1_escalation_queue` or on nondeterministic iteration over maps.

---

### 6.5 Phase 4 — Dirichlet sampling per escalated `(m,c)`

This phase is RNG-bearing. All RNG usage MUST follow the Layer-1 Philox + envelope law.

For each `(m,c) ∈ D_esc` in the order defined in Step 10:

**Step 11 – Read α-vector for this country**

* Let `c = legal_country_iso`.
* Retrieve:

  * ordered zone list `Z_ord(c) = [z_1, …, z_K]` from Step 7,
  * α-vector `α_i = alpha_effective(c, z_i)` for `i = 1..K`,
  * `alpha_sum_country(c)`.

S3 MUST ensure:

* all `α_i > 0`,
* `K ≥ 1`.

**Step 12 – Snapshot Philox counter before sampling**

Using the RNG subsystem:

* determine `counter_before` for the configured stream `(seed, parameter_hash, run_id, module, substream_label, rng_stream_id)` *at the point immediately before any uniforms for this Dirichlet event are drawn*.

S3 MUST NOT consume any uniforms between capturing `counter_before` and starting the Dirichlet sampling, except for this event.

**Step 13 – Draw Gamma variates for Dirichlet**

S3 MUST construct a Dirichlet sample for this `(m,c)` using the Layer-1 Gamma machinery already defined (e.g. the Gamma algorithm from 1A’s S0), driven by Philox uniforms:

* For each component `i = 1..K`:

  * Draw a Gamma variate:

    $$
    G_i \sim \mathrm{Gamma}(\alpha_i, 1)
    $$

    using Philox `u01` uniforms and the Layer-1 Gamma implementation.

  * Let `draws_i` be the number of `u01` uniforms consumed during the `G_i` draw.

* Let `draws_total(m,c) = Σ_i draws_i`.

The Gamma algorithm implementation is defined at Layer-1 (e.g. Marsaglia–Tsang), not by S3; S3’s requirement is **which α values** to pass and **how many uniforms** it consumes, not the internal maths.

**Step 14 – Normalise to Dirichlet share vector**

Compute:

$$
S = \sum_{i=1}^K G_i.
$$

S3 MUST:

* ensure `S > 0` (if not, treat as a numeric failure and abort the run),
* compute the Dirichlet components:

$$
\Theta(m,c,z_i) = \frac{G_i}{S}, \quad i = 1..K.
$$

These are the `share_drawn` values for each `(m,c,z_i)`.

Due to floating-point rounding, the sum `Σ_i Θ(m,c,z_i)` may differ slightly from 1; S3 MUST:

* compute `share_sum_country(m,c) = Σ_i Θ(m,c,z_i)` as stored,
* accept minor numerical deviation (tolerance specified in the validation state; S3 itself MUST NOT “fix up” shares in a way that changes the underlying sample).

**Step 15 – Snapshot Philox counter after sampling**

After finishing the Gamma draws and normalisation:

* capture `counter_after` for this stream.
* Compute:

  * `blocks = counter_after − counter_before` (as defined in the Layer-1 RNG spec; subtracting 128-bit counters),
  * `draws = draws_total(m,c)`.

S3 MUST ensure:

* `blocks * BLOCK_SIZE_UNIFORMS ≥ draws`, where `BLOCK_SIZE_UNIFORMS` is defined at Layer-1 (typically 2^n uniforms per block);
* the recorded `draws` equals the actual count of `u01` calls made during this Dirichlet sample.

---

### 6.6 Phase 4b — Emit RNG event & stage share rows

For each `(m,c)` after sampling:

**Step 16 – Emit `rng_event_zone_dirichlet` event**

S3 MUST append exactly one RNG event for this Dirichlet draw, with fields:

* `seed`, `parameter_hash`, `run_id`,
* `module`, `substream_label`,
* `rng_stream_id`,
* `counter_before`, `counter_after`, `blocks`, `draws`,
* `merchant_id = m`, `country_iso = c`,
* `zone_count = K`,
* optional diagnostics (e.g. `alpha_sum_country(c)`).

Schema must match `schemas.layer1.yaml#/rng/events/zone_dirichlet`.

Each event MUST be written to the standard RNG events dataset partitioned by `[seed, parameter_hash, run_id]`. S3 MUST NOT write RNG events elsewhere.

**Step 17 – Stage `s3_zone_shares` rows**

For each `i = 1..K`:

* Construct a row with:

  * `seed`, `manifest_fingerprint`,
  * `merchant_id = m`,
  * `legal_country_iso = c`,
  * `tzid = z_i`,
  * `share_drawn = Θ(m,c,z_i)`,
  * `share_sum_country = share_sum_country(m,c)`,
  * `alpha_sum_country = alpha_sum_country(c)`,
  * `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version` (from S2),
  * `rng_module`, `rng_substream_label`, `rng_stream_id`,
  * optional `rng_event_id` (link to the event emitted in Step 16).

Rows MUST not be written yet; S3 stages them in memory or a temporary structure.

---

### 6.7 Phase 5 — Write `s3_zone_shares` & update RNG trace

**Step 18 – Build complete row set for `s3_zone_shares`**

After iterating over all `(m,c) ∈ D_esc`:

* S3 has a staged collection of rows for `D_S3 = {(m,c,z)}` for this `{seed, manifest_fingerprint}`.

S3 MUST:

* ensure there are **no rows** for pairs `(m,c)` with `is_escalated = false`,
* ensure there are **no rows** for `tzid` not present in `Z(c)`,
* ensure that for each `(m,c) ∈ D_esc`, there are rows for **all** `z_i ∈ Z_ord(c)`.

**Step 19 – Sort rows & validate**

Using the dataset dictionary entry for `s3_zone_shares`:

* Determine the target path:
  `data/layer1/3A/s3_zone_shares/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...`.

* Sort rows (writer-sort) by:

  1. `merchant_id` ascending,
  2. `legal_country_iso` ascending,
  3. `tzid` ascending.

* Validate all rows against `schemas.3A.yaml#/plan/s3_zone_shares`.

Any validation failure MUST cause S3 to treat the run as failed before publishing output.

**Step 20 – Idempotent write for `s3_zone_shares`**

If no dataset exists yet at `{seed, fingerprint}`:

* S3 writes the new `s3_zone_shares` dataset with partitioning `["seed","fingerprint"]` and the defined writer-sort.

If a dataset already exists:

* S3 MUST read and normalise existing rows to the same schema and sort order.

* If the existing rows and staged rows are **identical**:

  * S3 MAY skip rewriting, or write identical bytes; visible content MUST not change.

* If they **differ**:

  * S3 MUST NOT overwrite;
  * S3 MUST treat this as an immutability violation and fail.

**Step 21 – Update `rng_trace_log`**

Following Layer-1 RNG trace rules, S3 MUST append or update entries in `rng_trace_log` for this `(seed, parameter_hash, run_id, module, substream_label)` such that:

* `blocks_total` equals the sum of `blocks` across all `rng_event_zone_dirichlet` events for this run.
* `draws_total` equals the sum of `draws` across all these events.

S3 MUST NOT alter trace entries belonging to other modules or substreams.

---

### 6.8 RNG & side-effect discipline

Throughout all phases, S3 MUST:

* use only the Layer-1 Philox RNG engine and `u01` mapping;
* ensure all RNG draws for Dirichlet sampling are covered by `rng_event_zone_dirichlet` events and `rng_trace_log` totals;
* not consume extra uniforms outside Dirichlet sampling paths;
* not read or modify any artefacts other than:

  * `s0_gate_receipt_3A`, `sealed_inputs_3A`,
  * `s1_escalation_queue`, `s2_country_zone_priors`,
  * sealed references and RNG policy artefacts,
  * the RNG events/logs datasets it appends to,
  * the `s3_zone_shares` dataset it writes.

On any failure at any step:

* S3 MUST NOT leave a partially written `s3_zone_shares` visible; writes MUST be atomic or rolled back.
* RNG events written before the failure MAY remain (append-only log), but the run MUST be marked FAIL, and downstream states MUST NOT treat `s3_zone_shares` as authoritative for that run.

Under this algorithm, for a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, S3 provides a **reproducible, fully logged Dirichlet sampling** over zones for all and only the escalated merchant×country pairs, with strict adherence to Layer-1 RNG and catalogue contracts.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes, precisely, how 3A.S3’s artefacts are:

* **identified** (keys),
* **partitioned** (path tokens),
* what their **ordering** means (and doesn’t), and
* what is allowed in terms of **merge / overwrite** behaviour.

There are two categories to consider:

* the **`s3_zone_shares`** dataset (seed+fingerprint scoped, snapshot), and
* S3’s contributions to the **Layer-1 RNG logs** (append-only, shared).

---

### 7.1 What a `s3_zone_shares` row *is*

For `s3_zone_shares`, the identity of a row is:

* **Run context** (shared across many rows in the partition):

  * `seed` — Layer-1 run seed.
  * `manifest_fingerprint` — Layer-1 manifest hash.

* **Business keys** (within that run):

  * `merchant_id` — Layer-1 merchant ID.
  * `legal_country_iso` — ISO-3166 country code.
  * `tzid` — IANA time zone ID.

**Domain definition**

For a given `{seed, manifest_fingerprint}`, define:

* From S1:

  $$
  D = {(m,c)} = {(merchant\_id,legal\_country\_iso) \mid site_count(m,c) \ge 1}
  $$

* Escalated subset:

  $$
  D_{\text{esc}} = {(m,c) \in D \mid is\_escalated(m,c) = true}
  $$

* From S2, for each country `c`:

  $$
  Z(c) = {\ tzid\ \mid (country\_iso=c, tzid) \in s2\_country\_zone\_priors}
  $$

Then the **intended domain** for `s3_zone_shares` is:

$$
D_{\text{S3}} = {(m,c,z) \mid (m,c) \in D_{\text{esc}},\ z \in Z(c)}.
$$

Binding requirements:

* For each `(m,c) ∈ D_esc` and each `z ∈ Z(c)`, there MUST be **exactly one** row in `s3_zone_shares` with:

  * `merchant_id = m`, `legal_country_iso = c`, `tzid = z`.
* There MUST be **no rows** for:

  * any `(m,c)` where `is_escalated = false`, or
  * any `tzid` not in `Z(c)` for the corresponding `legal_country_iso`.

**Logical primary key**

Within a given `{seed, manifest_fingerprint}` partition:

* Logical PK:
  $$
  (\text{merchant\_id}, \text{legal\_country\_iso}, \text{tzid})
  $$
* There MUST NOT be duplicate rows for the same triple.

---

### 7.2 Partitions & path tokens for `s3_zone_shares`

` s3_zone_shares` is a **run-scoped** dataset.

**Partition keys**

* Partition key set MUST be exactly:

```text
["seed", "fingerprint"]
```

No other partition keys (e.g. `parameter_hash`, `run_id`) are allowed for this dataset.

**Path template (conceptual)**

From the dataset dictionary:

```text
data/layer1/3A/s3_zone_shares/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...
```

Binding rules:

* For each concrete partition, the path MUST include exactly:

  * `seed=<uint64>`,
  * `fingerprint=<hex64>`.
* There MUST be at most one `s3_zone_shares` partition for any `{seed, manifest_fingerprint}` pair.

**Path↔embed equality**

Every row in a given `{seed, fingerprint}` partition MUST satisfy:

* `row.seed == {seed}` (from the path)
* `row.manifest_fingerprint == {manifest_fingerprint}` (from the path)

Any mismatch between embedded values and path tokens MUST be treated as a schema/validation error by both S3 and later validators.

---

### 7.3 Domain alignment with S1 & S2

Within a `{seed, manifest_fingerprint}` partition:

1. **Alignment with S1**

   * Let `D_esc` be escalated pairs from `s1_escalation_queue`.
   * `s3_zone_shares` MUST satisfy:

     * Projection onto `(merchant_id, legal_country_iso)` equals `D_esc`:
       $$
       {(m,c)\ \text{seen in S3 rows}} = D_{\text{esc}}
       $$
     * No `(m,c)` from S1 with `is_escalated = false` may appear in S3.

2. **Alignment with S2**

   * For each `(m,c)` in `D_esc`, let `c = legal_country_iso`.
   * S2 defines `Z(c)` via `s2_country_zone_priors`.
   * For each `(m,c)` row group in S3:

     * set of `tzid` values MUST equal `Z(c)`,
     * `alpha_sum_country` MUST equal the value from S2 for that `c`.

This alignment is enforced by accepted behaviour (algorithms) and by validators; logically, S3 is a *per-merchant Dirichlet realisation* of α-vectors defined by S2 for the subsets of countries that S1 has escalated.

---

### 7.4 Ordering semantics (writer-sort)

Physical file order in `s3_zone_shares` is **not semantically authoritative**, but S3 MUST use deterministic ordering.

Inside each `{seed, manifest_fingerprint}` partition, rows MUST be written sorted by the `ordering` key declared in the dictionary, for example:

1. `merchant_id` ascending,
2. `legal_country_iso` ascending,
3. `tzid` ascending.

Consumers MUST NOT:

* infer any additional meaning from row order (e.g. “first zone is special”), or
* depend on row order for identifying join partners.

The only role of ordering is:

* to guarantee that re-running S3 with the same inputs produces **byte-identical** `s3_zone_shares` content.

---

### 7.5 Merge, overwrite & idempotence discipline for `s3_zone_shares`

` s3_zone_shares` is a **snapshot per `{seed, manifest_fingerprint}`**. It is not an append log.

**Single snapshot per run**

* For each `{seed, manifest_fingerprint}`, there MUST be at most one `s3_zone_shares` dataset at the configured path.
* S3 is the **only** state authorised to write it.

**No row-level merges**

* S3 MUST always construct the **complete** row set for `D_S3` (all `(m,c,z)` for escalated `(m,c)` and zones `Z(c)`) before writing.
* It MUST NOT:

  * append rows to an existing snapshot,
  * delete or mutate individual rows in place, or
  * “top up” missing `(m,c,z)` rows via incremental writes.

**Idempotent re-writes only**

If a dataset already exists at `{seed, manifest_fingerprint}` when S3 runs:

1. S3 MUST read and normalise it to the same schema and writer-sort,
2. compare it row-for-row and field-for-field with the newly computed rows.

* If they are **identical**:

  * S3 MAY skip the write, or re-write identical bytes; the observable content MUST not change.
* If they **differ**:

  * S3 MUST NOT overwrite the existing dataset, and
  * MUST treat this as an immutability violation and mark the run as FAIL.

Under no circumstances may S3 silently replace a different `s3_zone_shares` snapshot for the same `{seed, manifest_fingerprint}`.

---

### 7.6 Identity & merge discipline for RNG logs

S3 does not own the RNG log datasets, but its use of them is constrained.

**Partitioning & identity (Layer-1)**

* RNG events (including `rng_event_zone_dirichlet`) MUST be written into the Layer-1 RNG events dataset, partitioned by:

  * `["seed", "parameter_hash", "run_id"]`.

* Within a given `(seed, parameter_hash, run_id)`:

  * *Identity* of a Dirichlet event is given by the tuple:
    $$
    (\text{module="3A.S3"},\ \text{substream\_label="zone\_dirichlet"},\ \text{rng\_stream\_id})
    $$
    plus associated `merchant_id` and `country_iso`.

* For S3, there MUST be **exactly one** `rng_event_zone_dirichlet` event for each escalated `(merchant_id, country_iso)` in `D_esc`.

**Append-only discipline**

* RNG events are an **append-only** log; S3 MUST NOT modify or delete existing events.
* If a run fails after emitting some events but before writing `s3_zone_shares`, those events remain part of the log, but:

  * the run MUST be marked FAIL, and
  * downstream components MUST treat `s3_zone_shares` (if missing or partial) as non-authoritative for that run.

**Trace log aggregation**

* RNG trace entries are also aggregate; S3’s contribution is an append/update to an aggregate keyed by `(seed, parameter_hash, run_id, module, substream_label)`.
* For S3 to be consistent:

  * `trace.blocks_total` MUST equal Σ `blocks` across all S3 Dirichlet events for that key,
  * `trace.draws_total` MUST equal Σ `draws` across those events.

S3 MUST NOT change trace entries belonging to other modules or substreams.

---

### 7.7 Cross-run semantics

S3 makes **no claims** about relationships between different runs:

* Each `{parameter_hash, manifest_fingerprint, seed, run_id}` describes its own world of `s3_zone_shares` and RNG events.
* It is out-of-spec to union multiple `{seed, manifest_fingerprint}` partitions and treat them as a single coherent zone-share surface for a specific run.

Cross-run unions of `s3_zone_shares` or RNG events are allowed **only for analytics**, e.g.:

* understanding distribution of mass across zones aggregated over many runs.

Such analytics MUST NOT be used to reconstruct or override the sampling result for any one specific run.

---

### 7.8 Interaction with upstream & downstream identity

* **Upstream:**

  * S1 defines the **escalation domain** `D_esc`.
  * S2 defines the **country→zone universe and α-vectors**.
  * S3 MUST reflect these exactly in its domain `D_S3` and in its identity keys.

* **Downstream:**

  * S4 and validation states MUST use:

    * `(seed, manifest_fingerprint, merchant_id, legal_country_iso, tzid)` as the join key to `s3_zone_shares`, and
    * `(seed, parameter_hash, run_id, module, substream_label, rng_stream_id)` to link back to Dirichlet RNG events.

Under these rules, S3’s outputs are:

* unambiguous in identity,
* well-behaved under partitioning,
* deterministic in ordering, and
* immune to silent merge/overwrite drift, while fitting cleanly into the Layer-1 RNG logging model.

---

## 8. Acceptance criteria & validator hooks *(Binding)*

This section defines **when 3A.S3 is considered PASS** for a given run
`(parameter_hash, manifest_fingerprint, seed, run_id)`, and what later validators MUST check against S3’s outputs and RNG logs.

S3 is PASS **only** if both:

* `s3_zone_shares` is a valid, complete snapshot for all escalated pairs, **and**
* the Dirichlet RNG usage is fully consistent with S2’s priors and Layer-1 RNG law.

---

### 8.1 Local acceptance criteria for 3A.S3

For a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, 3A.S3 is **PASS** iff **all** of the following hold:

#### 8.1.1 S0/S1/S2 preconditions honoured

* `s0_gate_receipt_3A` and `sealed_inputs_3A` for `manifest_fingerprint` exist, are schema-valid, and assert
  `segment_1A.status = segment_1B.status = segment_2A.status = "PASS"`.
* `s1_escalation_queue@{seed,fingerprint}` exists and is schema-valid.
* `s2_country_zone_priors@parameter_hash` exists and is schema-valid.
* `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version` used in S3 match those in S2.

Failure of any of these ➝ S3 MUST be considered FAIL.

#### 8.1.2 Domain alignment: S1 → S3

Let:

* `D` = set of `(merchant_id, legal_country_iso)` in `s1_escalation_queue`.
* `D_esc` = `{ (m,c) ∈ D | is_escalated(m,c) = true }`.
* `D_S3_proj` = projection of `s3_zone_shares` onto `(merchant_id, legal_country_iso)`.

S3 is PASS only if:

* `D_S3_proj == D_esc`:

  * Every escalated `(m,c)` has at least one row in `s3_zone_shares`.
  * No monolithic `(m,c)` appears in `s3_zone_shares`.

#### 8.1.3 Domain alignment: S2 → S3

For each `country_iso = c` appearing in any escalated pair:

* Let `Z(c)` = `{ tzid | (country_iso=c, tzid) ∈ s2_country_zone_priors }`.
* For each `(m,c) ∈ D_esc`, define `Z_S3(m,c)` = `{ tzid | rows in s3_zone_shares with (m,c,tzid) }`.

S3 is PASS only if for every `(m,c) ∈ D_esc`:

* `Z_S3(m,c) == Z(c)`:

  * every zone from S2’s priors for country `c` appears as a row in S3 for that `(m,c)`, and
  * no extra tzids appear.

#### 8.1.4 Per-row invariants for `s3_zone_shares`

For every row in `s3_zone_shares`:

* `seed` and `manifest_fingerprint` equal their partition tokens.
* `(merchant_id, legal_country_iso, tzid)` conforms to the domain constraints above.
* `share_drawn ∈ [0.0, 1.0]`.
* `share_sum_country > 0.0`.
* `alpha_sum_country > 0.0`.
* `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version`:

  * non-empty strings,
  * constant across all rows in this `{seed,fingerprint}` partition, and
  * equal to the values in `s2_country_zone_priors` for this `parameter_hash`.
* `rng_module`, `rng_substream_label`, `rng_stream_id` are present and consistent with the RNG policy.

Any schema violation or path↔embed mismatch MUST cause S3 to FAIL.

#### 8.1.5 Per-(merchant×country) share invariants

For each `(m,c) ∈ D_esc`, let:

* `rows(m,c)` = all rows in S3 with `(merchant_id=m, legal_country_iso=c)`.
* `K = |Z(c)|` (from S2).

S3 is PASS only if:

* `|rows(m,c)| = K`.

* All rows in `rows(m,c)` share the same `share_sum_country` value.

* Let:

  $$
  \tilde{S}(m,c) = \sum_{z \in Z(c)} share\_drawn(m,c,z).
  $$

  Then `share_sum_country(m,c) = \tilde{S}(m,c)`, and `\tilde{S}(m,c)` is within a small numeric tolerance of 1 (tolerance defined by validation state; S3 MUST NOT renormalise in a way that changes the sample).

* All rows for `(m,c)` carry the same `alpha_sum_country(c)` as in S2.

#### 8.1.6 RNG event coverage & exclusivity

Let `E_dir` be the set of `rng_event_zone_dirichlet` events for `(seed, parameter_hash, run_id, module="3A.S3", substream_label="zone_dirichlet")`.

S3 is PASS only if:

* For each `(m,c) ∈ D_esc`, there exists **exactly one** `e ∈ E_dir` with:

  * `merchant_id = m`,
  * `country_iso = c`.
* For each `(m,c) ∉ D_esc`, there is **no** `e ∈ E_dir` with that `(m,c)`.
* For each `e ∈ E_dir`, `zone_count` recorded in the event equals `|Z(c)|` for its `country_iso`.

#### 8.1.7 RNG envelope & trace invariants

For each `e ∈ E_dir`:

* `blocks ≥ 0`, `draws ≥ 0`.
* `counter_after − counter_before = blocks` (per Layer-1 counter semantics).
* The number of actual `u01` uniforms consumed by S3 for that Dirichlet draw equals `draws`.
* `draws` and `zone_count` are consistent with the Gamma sampling implementation (number of uniforms required per Γ draw is fixed by Layer-1).

For the corresponding `rng_trace_log` entry `(seed, parameter_hash, run_id, module="3A.S3", substream_label="zone_dirichlet")`:

* `blocks_total = Σ_e blocks(e)` over all `e ∈ E_dir`.
* `draws_total = Σ_e draws(e)` over all `e ∈ E_dir`.

Any discrepancy MUST cause S3 to be treated as FAIL.

#### 8.1.8 Idempotence & immutability

If a `s3_zone_shares` dataset already exists at `{seed, fingerprint}` when S3 runs:

* After reconstructing the new row set for this run, S3 MUST confirm it is **byte-identical** (when normalised and sorted) to the existing dataset.
* If not identical, S3 MUST:

  * refuse to overwrite, and
  * treat this as an immutability violation.

Under these rules, either:

* S3 produces a single, consistent `s3_zone_shares` and corresponding RNG events/trace for the run (PASS), or
* no authoritative `s3_zone_shares` exists for that run (FAIL).

---

### 8.2 Validator hooks for 3A validation state

A later 3A validation state MUST perform at least the following checks before declaring S3 “valid” for a run:

1. **Schema & domain checks**

   * Re-validate `s3_zone_shares` against `schemas.3A.yaml#/plan/s3_zone_shares`.
   * Reconstruct:

     * `D` and `D_esc` from `s1_escalation_queue`,
     * `Z(c)` and α-vectors from `s2_country_zone_priors`.
   * Check domain equality:

     * Projection of S3 onto `(m,c)` equals `D_esc`.
     * For each `(m,c)`, the set of `tzid` values equals `Z(c)`.

2. **Share-sum & α consistency**

   * For each `(m,c)`:

     * recompute `Σ_z share_drawn(m,c,z)` and compare to `share_sum_country(m,c)`; assert ≈1 within tolerance.
   * For each `c`:

     * verify `alpha_sum_country` in S3 rows for that `c` matches S2.

3. **RNG event/domain consistency**

   * From RNG logs, collect `E_dir` for this `(seed, parameter_hash, run_id, module="3A.S3", substream_label="zone_dirichlet")`.
   * Check:

     * one event per `(m,c) ∈ D_esc`, none for monolithic `(m,c)`,
     * `zone_count` in each event matches `|Z(c)|`.

4. **RNG replay (spot or full)**

   * For a selected subset (or all) of `(m,c)` pairs:

     * use `rng_event_zone_dirichlet` counters to reconstruct the Philox sequence for that event,
     * feed uniforms into the same Gamma + normalisation pipeline used by S3,
     * recompute `Θ(m,c,z)` and verify it matches `share_drawn(m,c,z)` for all zones within numerical tolerance.

   If any discrepancy is detected that cannot be explained by numeric tolerance, the validator MUST mark S3 as FAIL for that run.

5. **Trace log equality**

   * Verify that `rng_trace_log` totals for `(seed, parameter_hash, run_id, module="3A.S3", substream_label="zone_dirichlet")` match Σ `blocks` and Σ `draws` across `E_dir`.

---

### 8.3 Obligations imposed on downstream S4 & segment-level gating

Once S3 is PASS for `{parameter_hash, manifest_fingerprint, seed, run_id}`, it imposes binding obligations on downstream components:

1. **S4 MUST trust S3 as the only share authority**

   * S4 MUST:

     * obtain per-merchant×country total outlet counts from upstream (e.g. 1A),
     * obtain zone share vectors from `s3_zone_shares`, and
     * compute integer zone counts using these shares and counts.
   * S4 MUST NOT:

     * re-sample Dirichlet vectors for the same `(m,c)` under the same run, or
     * ignore or override S3’s shares.

2. **3A validation bundle MUST include S3 artefacts**

   * The eventual 3A validation bundle (later state) MUST include:

     * `s3_zone_shares` (or its digest + schema_ref) per run,
     * references to the `rng_event_zone_dirichlet` events and trace rows used by S3.

   * A segment-level PASS for 3A MUST NOT be declared unless S3 is PASS by these criteria.

---

### 8.4 Handling of S3 failures

If any of the acceptance criteria in §8.1 fail, either in S3’s own checks or in the validation state:

* That run’s `s3_zone_shares` MUST be treated as **non-authoritative**.
* S4 MUST NOT use it for zone allocation.
* Any derived artefacts (e.g. zone integerisation, later Layer-2 or model training) MUST be excluded from release.
* Recovery requires:

  * fixing configuration/priors/RNG policy or S3 implementation, and
  * re-running S0/S1/S2/S3 (and S4 as needed) under a clean `(parameter_hash, manifest_fingerprint, seed, run_id)`.

Under these rules, S3 is only considered acceptable when:

* every escalated merchant×country pair has a fully accounted, reproducible Dirichlet draw over the correct zone set, and
* the resulting zone-share surface and RNG logs are internally consistent and replayable.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only allowed failure classes** for 3A.S3 and assigns each a **canonical error code**.

Any S3 implementation MUST end each run in exactly one of:

* `status="PASS"` with `error_code = null`, or
* `status="FAIL"` with `error_code` equal to one of the codes below.

No additional error codes may be introduced without updating this specification.

---

### 9.1 Error taxonomy overview

3A.S3 can fail only for these reasons:

1. S0 / S1 / S2 preconditions are not satisfied.
2. Catalogue or schema artefacts are malformed.
3. Prior surface is incomplete or inconsistent with escalation domain.
4. Domain misalignment between S1, S2 and `s3_zone_shares`.
5. Dirichlet α usage or RNG behaviour is inconsistent (alpha mismatch, accounting broken, replay mismatch).
6. Output dataset schema/self-consistency failures.
7. Immutability / idempotence violations.
8. Infrastructure / I/O failures.

Each maps to a specific `E3A_S3_XXX_*` code.

---

### 9.2 S0 / S1 / S2 precondition failures

#### `E3A_S3_001_PRECONDITION_FAILED`

**Condition**

Raised when any required upstream 3A artefact is missing or invalid for this `(parameter_hash, manifest_fingerprint, seed, run_id)`, including:

* `s0_gate_receipt_3A` or `sealed_inputs_3A` missing or schema-invalid,
* `s0_gate_receipt_3A.upstream_gates.segment_1A/1B/2A.status != "PASS"`,
* `s1_escalation_queue@{seed,fingerprint}` missing or schema-invalid,
* `s2_country_zone_priors@parameter_hash` missing or schema-invalid.

**Required fields**

* `component ∈ {"S0_GATE","S0_SEALED_INPUTS","S1_ESCALATION_QUEUE","S2_PRIORS"}`
* `reason ∈ {"missing","schema_invalid","upstream_gate_not_pass"}`
* If `reason="upstream_gate_not_pass"`:

  * `segment ∈ {"1A","1B","2A"}`
  * `reported_status` — non-PASS value.

**Retryability**

* **Non-retryable** until the failing component is corrected (e.g. S0/S1/S2 re-run and PASS).

---

### 9.3 Catalogue & schema failures

#### `E3A_S3_002_CATALOGUE_MALFORMED`

**Condition**

Raised when S3 cannot load or validate required catalogue artefacts, such as:

* `schemas.layer1.yaml`, `schemas.3A.yaml`,
* `dataset_dictionary.layer1.3A.yaml`,
* `artefact_registry_3A.yaml`,
* RNG event schema bundle in `schemas.layer1.yaml`.

Examples:

* missing files,
* malformed YAML/JSON,
* schema validation failures.

**Required fields**

* `catalogue_id` — identifier of the failing artefact (e.g. `"schemas.3A.yaml"`, `"dataset_dictionary.layer1.3A"`).

**Retryability**

* **Non-retryable** until the catalogue artefact is corrected.

---

### 9.4 Prior surface / escalation domain failures

#### `E3A_S3_003_PRIOR_SURFACE_INCOMPLETE`

**Condition**

Raised when S3 detects that S2’s prior surface does not cover all countries that S1 has escalated, e.g.:

* there exists `(m,c)` with `is_escalated=true` in `s1_escalation_queue`, but no rows for `country_iso = c` in `s2_country_zone_priors`.

**Required fields**

* `missing_countries_count` — number of `legal_country_iso` values in the escalated domain with no priors.
* Optionally `sample_country_iso` — one example value.

**Retryability**

* **Non-retryable** until S2 or configuration is fixed (priors must be defined for all escalated countries).

---

### 9.5 Domain misalignment between S1/S2 and S3

#### `E3A_S3_004_DOMAIN_MISMATCH_S1`

**Condition**

Raised when the domain of `s3_zone_shares` does not match S1’s escalation decisions, for this `{seed,fingerprint}`:

* some `(m,c)` with `is_escalated=true` in S1 have no rows in `s3_zone_shares`, and/or
* S3 contains rows for `(m,c)` where S1 has `is_escalated=false` (or `(m,c)` not present in S1 at all).

**Required fields**

* `missing_escalated_pairs_count` — number of escalated `(m,c)` pairs missing in S3.
* `unexpected_pairs_count` — number of `(m,c)` pairs present in S3 but not escalated in S1.
* Optionally `sample_merchant_id`, `sample_country_iso` for one example of each class (subject to logging policy).

**Retryability**

* **Non-retryable** until S3 implementation or orchestration is corrected.

---

#### `E3A_S3_005_DOMAIN_MISMATCH_S2`

**Condition**

Raised when the per-(merchant×country×zone) domain in `s3_zone_shares` does not match S2’s zone universe for escalated countries, i.e. for some `(m,c)`:

* `Z_S3(m,c) ≠ Z(c)` where `Z(c)` is from `s2_country_zone_priors`.

Examples:

* missing zone rows in S3 for a zone that exists in S2’s priors for that country,
* S3 rows for tzids not present in S2’s priors for that country.

**Required fields**

* `affected_pairs_count` — number of `(m,c)` with zone-set mismatches.
* Optionally `sample_country_iso`, `sample_tzid`, `sample_merchant_id` for one example.

**Retryability**

* **Non-retryable** until S3 implementation or S2 surface is corrected.

---

### 9.6 Dirichlet α / RNG consistency failures

#### `E3A_S3_006_DIRICHLET_ALPHA_MISMATCH`

**Condition**

Raised when S3 appears to use α-vectors inconsistent with `s2_country_zone_priors`, as detected by S3 internal checks or by the validation state. Examples:

* `alpha_sum_country` in S3 rows for country `c` does not match S2’s `alpha_sum_country(c)`,
* S3’s inferred α parameters (if logged or inferred from RNG events) differ from S2’s `alpha_effective(c,z)`.

**Required fields**

* `country_iso` — at least one affected country.
* `reason ∈ {"alpha_sum_mismatch","alpha_values_mismatch"}`.
* Optionally `expected_alpha_sum`, `observed_alpha_sum`.

**Retryability**

* **Non-retryable** until S3 or S2 behaviour is corrected and aligned.

---

#### `E3A_S3_007_RNG_ACCOUNTING_BROKEN`

**Condition**

Raised when RNG envelope or trace invariants fail for S3’s Dirichlet events, e.g.:

* for some Dirichlet RNG event:

  * `blocks < 0` or `draws < 0`,
  * `counter_after - counter_before ≠ blocks`,
  * recorded `draws` does not equal the number of uniforms actually consumed.
* or `rng_trace_log` totals for `(seed, parameter_hash, run_id, module="3A.S3", substream_label="zone_dirichlet")` do not match Σ `blocks` and Σ `draws` across all S3 Dirichlet events.

**Required fields**

* `reason ∈ {"invalid_envelope","trace_mismatch"}`.
* Optionally:

  * `module` (expected `"3A.S3"`),
  * `substream_label` (e.g. `"zone_dirichlet"`).

**Retryability**

* **Non-retryable** until RNG accounting is corrected in S3 (or Layer-1 RNG infrastructure if the bug is there).

---

#### `E3A_S3_008_DIRICHLET_REPLAY_MISMATCH`

**Condition**

Raised when replaying Dirichlet draws from recorded RNG events does not reproduce `share_drawn` values in `s3_zone_shares`, e.g. during validation:

* given `rng_event_zone_dirichlet` and the α-vector from S2 for `(country_iso=c)`,
* re-running the Gamma + normalisation algorithm with the recorded Philox counters yields a share vector that materially differs from `share_drawn(m,c,z)`.

**Required fields**

* `merchant_id` — one example affected merchant (or a hashed/redacted form if required).
* `country_iso` — affected country.
* `reason` — short label (e.g. `"replay_share_mismatch"`).
* Optionally `max_abs_diff` — maximum absolute difference across zones between replayed and stored shares.

**Retryability**

* **Non-retryable** until S3’s Dirichlet implementation or RNG event recording is corrected (or until S2’s priors are aligned, if they are at fault).

---

### 9.7 Output schema & self-consistency failures

#### `E3A_S3_009_OUTPUT_SCHEMA_INVALID`

**Condition**

Raised when `s3_zone_shares` fails validation against `schemas.3A.yaml#/plan/s3_zone_shares`, e.g.:

* missing required fields,
* invalid value ranges (e.g. `share_drawn` outside `[0,1]`, `alpha_sum_country <= 0`),
* path↔embed mismatch (`seed`, `manifest_fingerprint` fields not matching partition tokens).

**Required fields**

* `violation_count` — number of schema validation errors.
* Optionally `example_field` — a representative field that failed.

**Retryability**

* **Retryable only after implementation fix**; indicates S3 is not writing conformant rows.

---

#### `E3A_S3_010_OUTPUT_INCONSISTENT`

**Condition**

Raised when `s3_zone_shares` is schema-valid but internally inconsistent, e.g.:

* for some `(m,c)`:

  * `share_sum_country(m,c)` does not equal Σ `share_drawn(m,c,z)` within tolerance,
  * `alpha_sum_country` differs across zones for the same country,
  * prior-lineage fields (`prior_pack_id`, etc.) differ across rows in the same run.

**Required fields**

* `reason ∈ {"share_sum_mismatch","alpha_sum_inconsistent","lineage_inconsistent"}`.
* Optionally:

  * `merchant_id`, `country_iso` for one example,
  * `expected`, `observed` values for a failing metric.

**Retryability**

* **Non-retryable** until S3 implementation or orchestration is fixed.

---

### 9.8 Immutability / idempotence failures

#### `E3A_S3_011_IMMUTABILITY_VIOLATION`

**Condition**

Raised when S3 detects that an existing `s3_zone_shares` snapshot for this `{seed, manifest_fingerprint}` differs from what it would produce for the same `(parameter_hash, seed, manifest_fingerprint, run_id)` and catalogue state, e.g.:

* difference in row set (extra/missing `(m,c,z)`),
* difference in `share_drawn`, `share_sum_country`, or lineage fields.

**Required fields**

* `difference_kind ∈ {"row_set","field_value"}`.
* `difference_count` — number of differing rows (may be approximate/capped).

**Retryability**

* **Non-retryable** until operators resolve the conflict (decide which snapshot, if any, is authoritative) and, if necessary, rerun S3 under a new `(seed, manifest_fingerprint)` or `run_id`.

---

### 9.9 Infrastructure / I/O failures

#### `E3A_S3_012_INFRASTRUCTURE_IO_ERROR`

**Condition**

Raised when S3 cannot complete due to non-logical environment issues, such as:

* transient object-store or filesystem failures,
* permission errors,
* network timeouts while reading/writing inputs/outputs,
* storage quota exhaustion.

This code MUST NOT be used for any of the logical errors covered by `E3A_S3_001`–`E3A_S3_011`.

**Required fields**

* `operation ∈ {"read","write","list","stat"}`.
* `path` — artefact path involved (if known).
* `io_error_class` — short label (e.g. `"timeout"`, `"permission_denied"`, `"not_found"`, `"quota_exceeded"`).

**Retryability**

* **Potentially retryable**, subject to infrastructure policy.

  * Orchestrators MAY retry automatically, but every successful run MUST still satisfy all acceptance criteria in §8 before `s3_zone_shares` is considered authoritative.

---

### 9.10 Run-report mapping

Every S3 run MUST set:

* `status="PASS", error_code=null` **or**
* `status="FAIL", error_code ∈ {E3A_S3_001 … E3A_S3_012}`.

Downstream components MUST treat any `status="FAIL"` for S3 as meaning:

* `s3_zone_shares` for that `{seed, manifest_fingerprint}` is **non-authoritative**, and
* S4 / later stages MUST NOT use it to drive zone integerisation until the cause is fixed and S3 has been successfully re-run.

---

## 10. Observability & run-report integration *(Binding)*

This section defines what **3A.S3 MUST emit** for observability and how it MUST integrate with the Layer-1 run-report.

Because S3 is **run-scoped and RNG-bearing**, observability must make it possible to answer, for any run
`(parameter_hash, manifest_fingerprint, seed, run_id)`:

* Did S3 run?
* Did it succeed or fail, and why?
* How many merchant×country pairs were escalated and actually sampled?
* How many zones per country were involved?
* How much RNG did S3 consume and in which streams?
* Which prior / floor policy / RNG policy versions were in force?

—without re-deriving everything from scratch.

S3 MUST NOT dump full row-level content (e.g. all shares or priors) into logs or metrics.

---

### 10.1 Structured logging requirements

3A.S3 MUST emit **structured logs** (e.g. JSON records) for three lifecycle events: **start**, **success**, and **failure**.

#### 10.1.1 State start

Exactly one log event at the beginning of each S3 invocation.

Required fields:

* `layer = "layer1"`
* `segment = "3A"`
* `state = "S3"`
* `parameter_hash` (hex64)
* `manifest_fingerprint` (hex64)
* `seed` (uint64)
* `run_id` (string or u128-encoded)
* `attempt` (integer, if provided by orchestration; otherwise default `1`)

Optional fields:

* `trace_id` — correlation ID if provided by infrastructure.

Log level: `INFO`.

#### 10.1.2 State success

Exactly one log event **only if** S3 meets all acceptance criteria in §8 for this run.

Required fields:

* All “start” fields above

* `status = "PASS"`

* `error_code = null`

* Domain summary:

  * `pairs_total` — total merchant×country pairs in `s1_escalation_queue` (|D|).
  * `pairs_escalated` — number of pairs with `is_escalated = true` (|D_esc|).
  * `pairs_monolithic` — `pairs_total − pairs_escalated`.

* Zone/prior summary (based on S2 for countries actually escalated):

  * `countries_escalated` — distinct `legal_country_iso` in `D_esc`.
  * `avg_zones_per_country` — average |Z(c)| over those countries.
  * `zone_shares_rows_total` — number of rows in `s3_zone_shares` (|D_S3|).

* RNG summary:

  * `dirichlet_events_total` — number of `rng_event_zone_dirichlet` events.
  * `rng_draws_total` — sum of `draws` across all Dirichlet events.
  * `rng_blocks_total` — sum of `blocks` across those events.

* Prior/policy lineage (copied from S2):

  * `prior_pack_id`
  * `prior_pack_version`
  * `floor_policy_id`
  * `floor_policy_version`

Optional fields:

* `elapsed_ms` — wall-clock duration measured by orchestration; MUST NOT influence S3 logic.

* Coarse distributions (encoded in a small JSON object), e.g.:

  * `zone_count_histogram` — bucketed counts of |Z(c)| for escalated countries, such as `{ "1": n1, "2-3": n2, "4+": n3 }`.

Log level: `INFO`.

#### 10.1.3 State failure

Exactly one log event **only if** S3 terminates without satisfying §8.

Required fields:

* All “start” fields

* `status = "FAIL"`

* `error_code` — one of the `E3A_S3_***` codes from §9

* `error_class` — coarse label, e.g.:

  * `"PRECONDITION"` (for `E3A_S3_001`)
  * `"CATALOGUE"`
  * `"PRIOR_SURFACE"`
  * `"DOMAIN_S1"`
  * `"DOMAIN_S2"`
  * `"ALPHA_RNG"`
  * `"OUTPUT_SCHEMA"`
  * `"OUTPUT_INCONSISTENT"`
  * `"IMMUTABILITY"`
  * `"INFRASTRUCTURE"`

* `error_details` — structured object containing the code-specific fields required by §9 (e.g. `component`, `country_iso`, `missing_escalated_pairs_count`, `reason`, etc.).

Recommended additional fields (if available at the time of failure):

* `pairs_total`, `pairs_escalated`, `dirichlet_events_total` — if S3 progressed far enough to compute them; else omitted or 0.

Optional:

* `elapsed_ms` — if available.

Log level: `ERROR`.

All logs MUST be machine-parseable and MUST NOT contain bulk row-level data (e.g. all `(m,c,z)` shares); only summary counts and IDs/versions.

---

### 10.2 Segment-state run-report row

Layer-1 maintains a **segment-state run-report** for all states, including S3 (e.g. `run_report.layer1.segment_states`). For each S3 invocation, exactly **one row** MUST be written.

Because S3 is RNG-bearing and run-scoped, the run-report row MUST uniquely identify the run:

* **Identity & context**

  * `layer = "layer1"`
  * `segment = "3A"`
  * `state = "S3"`
  * `parameter_hash`
  * `manifest_fingerprint`
  * `seed`
  * `run_id`
  * `attempt`

* **Outcome**

  * `status ∈ {"PASS","FAIL"}`
  * `error_code` — `null` on PASS; one of §9 on FAIL
  * `error_class` — as above
  * `first_failure_phase` — optional enum such as:

    `{ "S0_GATE", "S1_INPUT", "S2_PRIORS", "DOMAIN_BUILD", "DIRICHLET_SAMPLING", "OUTPUT_WRITE", "IMMUTABILITY", "INFRASTRUCTURE" }`

* **Domain & escalation summary**

  * `pairs_total` — |D| from S1.
  * `pairs_escalated` — |D_esc|.
  * `pairs_monolithic` — `pairs_total − pairs_escalated`.
  * `countries_escalated` — distinct `legal_country_iso` in `D_esc`.

* **Zone & share summary (when `status="PASS"`; MAY be filled on FAIL if known)**

  * `zone_shares_rows_total` — count of rows in `s3_zone_shares`.
  * `avg_zones_per_country` — average |Z(c)| for escalated countries.
  * `zone_count_histogram` — serialised small JSON map (as described above).

* **Prior / policy lineage**

  * `prior_pack_id`
  * `prior_pack_version`
  * `floor_policy_id`
  * `floor_policy_version`

* **RNG usage summary**

  * `dirichlet_events_total` — number of Dirichlet RNG events.
  * `rng_draws_total` — sum of `draws` across those events.
  * `rng_blocks_total` — sum of `blocks` across those events.

* **Catalogue / schema versions**

  * At minimum, for consistency with S0/S1/S2:

    * `schemas_layer1_version`
    * `schemas_3A_version`
    * `dictionary_layer1_3A_version`

  * Optionally entries for `artefact_registry_3A` or RNG policy versions.

* **Timing & correlation**

  * `started_at_utc` — orchestrator-provided timestamp; MUST NOT drive S3 behaviour.
  * `finished_at_utc`
  * `elapsed_ms`
  * `trace_id` — optional, if provided.

The run-report row MUST be:

* consistent with `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`, and RNG logs,
* sufficient for an operator or audit harness to see “what happened” in S3 without inspecting every row.

---

### 10.3 Metrics & counters

S3 MUST expose a minimal set of metrics useful for monitoring. Names/export mechanism are implementation details; semantics are binding.

At minimum:

* `mlr_3a_s3_runs_total{status="PASS"|"FAIL"}`

  * Monotone counter, incremented once per S3 run.

* `mlr_3a_s3_pairs_escalated` (gauge)

  * Number of escalated `(merchant_id, country_iso)` pairs in the most recent successful run for a given `{seed,fingerprint}`.

* `mlr_3a_s3_dirichlet_events_total` (gauge)

  * Number of `rng_event_zone_dirichlet` events in that run.

* `mlr_3a_s3_rng_draws_total` (gauge)

  * Total `draws` consumed by S3 Dirichlet events in the most recent successful run.

* `mlr_3a_s3_rng_blocks_total` (gauge)

  * Total `blocks` consumed by S3 Dirichlet events.

* `mlr_3a_s3_domain_mismatch_s1_total` (counter)

  * Incremented whenever `E3A_S3_004_DOMAIN_MISMATCH_S1` occurs.

* `mlr_3a_s3_domain_mismatch_s2_total` (counter)

  * Incremented whenever `E3A_S3_005_DOMAIN_MISMATCH_S2` occurs.

* `mlr_3a_s3_rng_accounting_errors_total` (counter)

  * Aggregates `E3A_S3_007_RNG_ACCOUNTING_BROKEN` and `E3A_S3_008_DIRICHLET_REPLAY_MISMATCH`.

* `mlr_3a_s3_duration_ms` (histogram)

  * Distribution of `elapsed_ms` per S3 run.

Metric labels MUST NOT include raw merchant IDs, full tzids, or other high-cardinality identifiers. Labels SHOULD be limited to:

* `state="S3"`,
* `status="PASS"|"FAIL"`,
* `error_class`,
* possibly coarse buckets (e.g. small / medium / large domain sizes).

---

### 10.4 Correlation & traceability

To allow auditors and operators to trace behaviour across the 3A pipeline and RNG logs:

1. **Correlation with S0/S1/S2/S4**

   * S3’s run-report rows MUST be joinable to S0, S1, S2, S4 via:

     * `(layer="layer1", segment="3A", state="Sx", parameter_hash, manifest_fingerprint, seed, run_id)`
       (S2 may omit `seed`/`run_id` as it is parameter-scoped).

   * If a `trace_id` is used by the orchestration, S3 MUST propagate it to:

     * structured logs,
     * run-report row.

2. **Linkage to artefacts & RNG logs**

   A 3A validation state MUST be able to:

   * go from S3’s run-report row →
   * locate `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}` via the dictionary/registry →
   * locate S1 and S2 artefacts via their own manifest keys →
   * locate RNG logs (`rng_event_zone_dirichlet` and relevant `rng_trace_log` entries) via `(seed, parameter_hash, run_id, module="3A.S3", substream_label="zone_dirichlet")`.

S3 MUST ensure its logging and run-report fields provide enough identity to make these joins unambiguous.

---

### 10.5 Retention, access control & privacy

Even though S3 works with synthetic data, its outputs are still **behaviourally sensitive** (zone concentrations, RNG trace). The following are binding:

1. **Retention**

   * `s3_zone_shares` MUST be retained at least as long as:

     * any S4/S4+ artefacts derived from it are in use, and
     * any models/analysis that depend on those artefacts are considered active.

   * Deleting S3 outputs while their dependants are still deployed is out of spec.

2. **Access control**

   * Access to `s3_zone_shares`, RNG logs, and S3 run-report rows SHOULD be limited to principals authorised to inspect internal engine behaviour.
   * S3 observability artefacts MUST NOT expose:

     * full per-merchant per-zone share vectors in logs,
     * any secrets (keys, credentials),
     * unredacted identifiers beyond what Layer-1 logging policy permits.

3. **No bulk row-level leakage via observability**

   * Structured logs and metrics MUST NOT contain massive per-row dumps (no logging of every `(merchant_id, country_iso, tzid, share_drawn)`), except possibly in tightly controlled, sampled debug modes governed by separate operational policies (outside this spec).
   * Error details that include `merchant_id` or `country_iso` MUST respect any redaction/aggregation policies defined at Layer-1.

---

### 10.6 Relationship to Layer-1 run-report governance

The Layer-1 run-report schema may impose additional mandatory fields (e.g. generic state metadata, environment identifiers). Where there is a conflict:

* Layer-1 run-report rules take precedence for **schema shape and required columns**.
* This S3 section then specifies what S3 MUST populate for its own fields and how those fields relate to:

  * `s1_escalation_queue`,
  * `s2_country_zone_priors`,
  * `s3_zone_shares`,
  * RNG logs, and
  * the S0 gate and sealed inputs.

Under these rules, every S3 run is:

* **observable** (structured logs),
* **summarised** (single run-report row), and
* **auditable** (via `s3_zone_shares` + RNG logs + S1/S2 + S0 artefacts),

while respecting privacy and keeping the Layer-1 authority chain intact.

---

## 11. Performance & scalability *(Informative)*

This section explains how 3A.S3 behaves at scale and what actually drives its cost. The binding rules are still in §§1–10; this just interprets them operationally.

---

### 11.1 Workload shape

S3 only touches:

* **Escalated merchant×country pairs** from S1 (`D_esc`), and
* **Country→zone priors** from S2 (`s2_country_zone_priors`).

It never:

* reads all outlets,
* reads per-site geometry/tzids,
* reads arrivals or routing logs.

So the effective problem size is:

[
\text{Work} \sim |D_{\text{esc}}| \times \text{avg}(|Z(c)|),
]

where:

* ( |D_{\text{esc}}| ) = number of escalated `(merchant_id, country_iso)` pairs,
* ( |Z(c)| ) = number of zones for country `c`.

This is often much smaller than “number of outlets” or “number of transactions”.

---

### 11.2 Complexity drivers

The main costs are:

1. **Joining S1 & S2**

   * Building `D_esc` from `s1_escalation_queue`.
   * For each `country_iso`, reading its α-vector and zone set `Z(c)` from `s2_country_zone_priors`.
   * Complexity: ~O(|D| + |C_priors| × avg |Z(c)|), typically negligible compared to the sampling step.

2. **Dirichlet sampling**

   For each `(m,c) ∈ D_esc`:

   * S3 draws `|Z(c)|` Gamma variates and normalises them.
   * Each Gamma draw uses a fixed, small number of uniforms (depending on the Layer-1 Gamma implementation).

   Overall complexity: approximately:

   [
   O\left(\sum_{(m,c) \in D_{\text{esc}}} |Z(c)|\right)
   ]

   i.e. linear in the number of **escalated** zones.

3. **Writing outputs**

   * `s3_zone_shares` has one row per `(m,c,z)` triple (for escalated pairs only).
   * RNG logs have one event per escalated `(m,c)`.

   This is again linear in (|D_{\text{esc}}| \times \text{avg}(|Z(c)|)).

So S3’s cost is dominated by “number of escalated pairs × zones per country”, not by total data volume in the engine.

---

### 11.3 Memory footprint

S3 does **not** need to keep everything in memory at once. A reasonable implementation can:

* Stream `s1_escalation_queue` to build `D_esc` in a partitioned way (e.g. by country or merchant),
* For each country `c`, load its `Z(c)` and α-vector once from `s2_country_zone_priors`,
* Process escalated `(m,c)` pairs in batches:

  * draw Dirichlet shares for a batch,
  * write `s3_zone_shares` rows (or buffer them per-partition),
  * discard intermediate Gamma vectors as soon as `Θ(m,c,·)` has been written.

Peak memory is thus proportional to:

* size of `Z(c)` for the country currently being processed,
* plus a working buffer of `(merchant, zone)` rows for a batch.

You never have to hold the entire `(merchant, country, zone)` cube in RAM.

---

### 11.4 Reuse & scheduling

S3 is **tightly tied to a run**: its outputs depend on `seed`, `run_id`, and the escalated domain for that particular manifest. However, you can still:

* **Cache S2 priors** per `parameter_hash` (S2 is parameter-scoped).
* Run S3:

  * once per `(seed, manifest_fingerprint, run_id)` you care about,
  * potentially multiple times per `parameter_hash` as you change seeds or manifests.

In practice:

* S2 runs “once per parameter configuration”,
* S3 runs “once per RNG realisation (per seed/run_id) for each manifest”.

---

### 11.5 Parallelism

S3 is naturally parallelisable:

* **Across escalated pairs**:
  Dirichlet draws for different `(m,c)` are independent given priors; you can shard `D_esc` by merchant or country across workers.

* **Within a worker**:
  You can process `(m,c)` in streaming fashion, drawing and writing shares without building a huge in-memory structure.

Constraints:

* You still need a consistent RNG story:

  * parallel workers must respect the Philox stream/substream layout,
  * counters must not overlap.
    This normally means assigning disjoint stream ranges or keys per worker, as defined by the RNG policy.

Done correctly, parallelism affects only throughput, not semantics.

---

### 11.6 Expected runtime profile

Compared to:

* 1A/1B (heavy modelling, spatial sampling),
* S1 (full group-by over `outlet_catalogue`),
* 2B (alias table construction, routing),

S3 is relatively light:

* It only touches the **escalated subset** of merchant×country pairs.
* Zone counts per country are typically small (few tzids per country).
* Gamma + Dirichlet sampling is numerically non-trivial but cheap at the scale of thousands or tens of thousands of vectors.

The main knobs that affect S3 runtime are:

* `pairs_escalated` (how aggressive S1 is),
* `avg_zones_per_country` (how zone-rich your world is),
* the efficiency of the underlying RNG and Gamma implementation.

---

### 11.7 Tuning levers (non-normative)

Implementers can tune S3 performance without changing its semantics by:

* **Batch size**:
  Choosing how many `(m,c)` pairs to process at once, balancing:

  * RNG API overhead,
  * memory footprint,
  * write throughput for `s3_zone_shares`.

* **RNG implementation and vectorisation**:
  Using vectorised Gamma sampling over multiple zones or multiple `(m,c)` pairs at once, as long as:

  * you still draw the same number of uniforms,
  * you preserve the same ordering of streams/counters, and
  * the mapping from uniforms → Gamma → Dirichlet remains mathematically equivalent.

* **I/O layout**:
  Writing `s3_zone_shares` in reasonably sized Parquet row groups to improve scan performance for S4 and validators.

None of these tuning choices may change:

* which `(m,c,z)` rows appear,
* the `share_drawn` values given a fixed RNG stream,
* RNG envelopes (`blocks`, `draws`), or
* any of the acceptance criteria in §8.

---

Net effect: S3 is designed so that its complexity is driven by **escalated pairs × zones** and can be implemented in a streaming or parallel way, making it practical even when the overall engine is working at “big data” scale.

---

## 12. Change control & compatibility *(Binding)*

This section defines **how the 3A.S3 contract is allowed to evolve**, and what guarantees downstream consumers (S4, validation, tooling) can rely on when:

* S3’s dataset/RNG contracts change,
* S2’s α-surface or 3A RNG policies change, or
* the governed parameter set 𝓟 changes (hence `parameter_hash`).

The goal: given
`(parameter_hash, manifest_fingerprint, seed, run_id, version_of_s3_zone_shares)`
and the Layer-1 RNG law, a consumer can **unambiguously** understand:

* what domain of `(m,c,z)` was sampled,
* what Dirichlet behaviour was in force, and
* how to replay/validate RNG.

---

### 12.1 Scope of change control

Change control for 3A.S3 covers:

1. The **shape and semantics** of:

   * `s3_zone_shares` (columns, partitioning, identity, meaning of `share_drawn`, `share_sum_country`, RNG lineage fields), and
   * the `rng_event_zone_dirichlet` family (fields, envelope semantics).

2. The **mapping** from inputs to outputs:

   * how S3 maps from:

     * escalated domain `D_esc` (S1),
     * α-vectors `α_effective(c,z)` (S2),
     * RNG streams `(seed, parameter_hash, run_id, rng_stream_id)`,
       to:
     * `Θ(m,c,z)` (shares) and Dirichlet events,
   * how zone ordering `Z_ord(c)` is chosen,
   * how many uniforms are consumed per Dirichlet event.

3. The **error taxonomy** and acceptance criteria in §§8–9.

It does **not** govern:

* the internal numeric implementation details of Gamma/Dirichlet algorithms, as long as:

  * they consume the same number of uniforms, and
  * they remain deterministic and numerically compatible with replay expectations;
* global Layer-1 definitions of `parameter_hash`, `manifest_fingerprint`, `seed`, or `run_id`.

---

### 12.2 S3 dataset contract versioning

The S3 dataset contract has a **version** carried as:

* `version` in the `dataset_dictionary.layer1.3A.yaml` entry for `s3_zone_shares`, and
* the matching `version` in `artefact_registry_3A.yaml` for `mlr.3A.s3_zone_shares`.

Rules:

1. **Single authoritative version.**

   * The dictionary and registry MUST agree on the `version` for `s3_zone_shares`.
   * Any change in its observable shape or semantics MUST be accompanied by a version bump.

2. **Semver semantics.**

   * `MAJOR.MINOR.PATCH`:

     * **PATCH** (`x.y.z → x.y.(z+1)`): clarifications or fixes that:

       * do not change schema or contract for any compliant implementation, and
       * do not change the *distribution* or *identity* of `s3_zone_shares` or RNG events for any run.
     * **MINOR** (`x.y.z → x.(y+1).0`): backwards-compatible extensions, e.g.:

       * adding optional columns,
       * adding new error codes,
       * adding extra observability fields.
         Existing consumers that ignore new fields remain correct.
     * **MAJOR** (`x.y.z → (x+1).0.0`): breaking changes:

       * output shape/identity/partitioning changes,
       * changes to `share_drawn` semantics,
       * changes in which domain of `(m,c,z)` is sampled under the same inputs,
       * changes to RNG envelope semantics or consumption patterns visible in logs.

3. **Consumers MUST key off version.**
   Consumers MUST NOT infer behaviour from date or build; they MUST rely on:

   * `schema_ref` for `s3_zone_shares`, and
   * its `version` in the dictionary/registry,

to decide how to interpret the dataset.

---

### 12.3 Dirichlet RNG event contract versioning

The `rng_event_zone_dirichlet` family is defined at Layer-1 (in `schemas.layer1.yaml` / Layer-1 RNG spec). Changes here are governed primarily by Layer-1, but S3 depends on them.

Binding for S3:

1. **Event schema versioning.**

   * If Layer-1 uses versioned RNG schemas, `rng_event_zone_dirichlet` MUST carry a version or be part of a versioned union.
   * Any breaking change (fields removed/retasked, envelope semantics change) MUST be versioned and coordinated with S3.

2. **S3 compatibility.**

   * S3 MUST:

     * use only event shapes compatible with the current Layer-1 RNG contract, and
     * treat any change to `counter_before/after`, `blocks`, or `draws` semantics as breaking (requires S3 contract review and likely a MAJOR bump).

3. **Replay contract.**

   * Changes to the Dirichlet numeric algorithm (e.g. using a different Gamma algorithm) MAY be backwards-compatible if:

     * the RNG consumption pattern (number and order of `u01` draws per event) remains fixed, and
     * replay at validation time can still reproduce `share_drawn` from logged events.
   * If a change breaks replay fidelity (e.g. uses a different mapping from uniforms → Gamma/Dirichlet), it is a **breaking change** for the Dirichlet contract and MUST be coordinated with S3 and validation states, likely requiring a MAJOR bump in the S3 contract and/or RNG event version.

---

### 12.4 Backwards-compatible changes (MINOR/PATCH)

The following changes are considered **backwards-compatible** for S3, provided they obey the constraints below.

1. **Adding optional columns to `s3_zone_shares`.**
   Examples:

   * extra RNG lineage fields (e.g. `rng_event_id` if absent before),
   * diagnostic fields (e.g. `max_zone_share`, `min_zone_share` per `(m,c,z)` group),
   * metadata fields (e.g. `sampling_strategy_id`).

   Conditions:

   * New fields MUST be optional in the schema (or have defaults) with clear “absent = legacy behaviour” semantics.
   * They MUST NOT change or reinterpret `share_drawn`, `share_sum_country`, `alpha_sum_country`, or the domain `D_S3`.

2. **Adding new metrics / run-report / log fields.**

   * Additional summary fields in logs or run-report rows are allowed as long as they:

     * do not affect S3’s sampling or domain, and
     * do not alter acceptance criteria.

3. **Adding new error codes.**

   * New `E3A_S3_XXX_*` codes may be added, as long as:

     * existing codes keep their original meaning, and
     * existing consumers treat unknown codes as generic FAIL.

4. **Tightening validation.**

   * Stricter internal checks (e.g. smaller tolerance for `share_sum_country ≈ 1`) that:

     * do not change outputs for previously valid runs, but
     * may convert previously invalid runs into explicit FAILs.

5. **Internal performance improvements.**

   * Changing execution strategy (e.g. vectorising Gamma draws, parallelising over `(m,c)`) is allowed if:

     * the RNG policy ensures the same streams/counters are used for each `(m,c)`,
     * `rng_event_zone_dirichlet` envelopes and `s3_zone_shares` remain unchanged for any given run.

These changes MAY require a MINOR or PATCH version bump for `s3_zone_shares` depending on whether schema surfaces change.

---

### 12.5 Breaking changes (MAJOR)

The following are **breaking changes** and MUST trigger a **MAJOR** version bump for S3’s dataset contract (and possibly Layer-1 RNG contracts as well):

1. **Changing dataset identity or partitioning.**

   * Altering the partition key set for `s3_zone_shares` (e.g. adding/removing `seed`, `fingerprint`).
   * Changing the dataset ID away from `"s3_zone_shares"` or modifying its path template in incompatible ways.
   * Changing the logical primary key `(merchant_id, legal_country_iso, tzid)`.

2. **Changing the semantics of `share_drawn` or domain `D_S3`.**

   * Redefining `share_drawn` from “Dirichlet sample over zones” to something else (e.g. a deterministic function of α, or a mixture of Dirichlet + other noise).
   * Changing which `(m,c,z)` combinations appear for a given S1/S2 domain under the same inputs (e.g. skipping some zones, or emitting rows for monolithic pairs).
   * Changing per-run identity, e.g. sampling multiple Dirichlet vectors per `(m,c)` without changing the dataset design.

3. **Changing RNG consumption semantics.**

   * Changing how many uniforms are consumed per Dirichlet draw in a way that breaks the envelope/trace law (without a co-ordinated RNG spec change).
   * Changing stream keying for `(m,c)` in a way that makes previous RNG streams incompatible (e.g. events appear in a different order or on different streams).
   * Removing or repurposing required fields in `rng_event_zone_dirichlet` (e.g. dropping `merchant_id` or `country_iso`).

4. **Relaxing domain & RNG accounting invariants.**

   * Allowing `s3_zone_shares` to omit escalated `(m,c)` or zones for a given `c` without S3 failing.
   * Allowing Dirichlet events for monolithic `(m,c)` pairs.
   * Relaxing requirements that `rng_trace_log` totals match the sum of event envelopes.

5. **Relaxing immutability.**

   * Permitting S3 to overwrite existing `s3_zone_shares` content for the same `{seed, manifest_fingerprint}` with different draws or different domains, without treating it as an immutability violation.

Any of these changes require:

* a MAJOR bump for `s3_zone_shares` (and, where applicable, versioning updates for RNG event schemas), and
* co-ordinated updates in S4 and 3A validation to interpret the new contract correctly.

---

### 12.6 Parameter set evolution vs `parameter_hash`

Unlike S2, S3 is **run-scoped**, but it still conditions on `parameter_hash`. The governed parameter set 𝓟 includes:

* `country_zone_alphas`,
* `zone_floor_policy`,
* any RNG policy artefacts that influence S3’s stream layout (if present).

Binding rules:

1. **Any change in priors/floor policy that alters α-vectors MUST change `parameter_hash`.**

   * This is enforced at S2; S3 depends on `s2_country_zone_priors`.
   * S3 MUST assume that if `parameter_hash` is unchanged, S2’s α-vectors for each `(country_iso, tzid)` are unchanged.

2. **RNG policy artefacts that alter stream layout MUST also participate in 𝓟.**

   * If a change in RNG policy (e.g. different substream keying for `(m,c)`) affects which uniforms are consumed for Dirichlet draws in S3, that policy MUST be part of 𝓟 and trigger a new `parameter_hash` when changed.
   * If S3 uses only Layer-1 RNG law without extra policies, this may not apply.

3. **S3 MUST NOT silently adapt to changed priors under the same `parameter_hash`.**

   * If S3 detects digests for prior/floor artefacts in `sealed_inputs_3A` that do not match what S2 used for this `parameter_hash`, S3 MUST fail via an S0/S2 precondition failure (see §9) rather than proceed.

In short: S3 assumes that for a fixed `parameter_hash`, priors and any RNG policy affecting S3 are immutable; changing them requires a new parameter set and may require re-running S2 and S3.

---

### 12.7 Catalogue evolution (schemas, dictionary, registry)

S3 depends on Layer-1 and 3A catalogue artefacts.

1. **Schema evolution**

   * Adding optional fields to `schemas.3A.yaml#/plan/s3_zone_shares` is MINOR-compatible.
   * Removing or changing the type/meaning of required fields (e.g. dropping `alpha_sum_country` or `rng_stream_id`) is MAJOR and MUST be co-ordinated with S3 and S4.

2. **Dictionary evolution**

   * Changing `id`, `path`, `partitioning` or `schema_ref` for `s3_zone_shares` is a **breaking** change per §12.5(1), requiring a MAJOR bump.
   * Adding new datasets for S3 (e.g. additional diagnostics) is compatible if they are declared with their own IDs and DO NOT change S3’s core behaviour for existing datasets.

3. **Registry evolution**

   * Adding new artefacts to `artefact_registry_3A.yaml` unrelated to S3 is compatible.
   * Removing or renaming `mlr.3A.s3_zone_shares` or changing its `path`/`schema` is breaking and MUST be synchronised with a MAJOR version bump.

---

### 12.8 Deprecation strategy

When evolving S3:

1. **Introduce before removing.**

   * New behaviour (e.g. new optional lineage fields or metrics) SHOULD be introduced in a MINOR version while preserving existing behaviour.

2. **Deprecation signalling.**

   * The S3 spec and/or validation state MAY include non-normative notes such as:

     * “`rng_event_id` will be introduced in v1.1.0 and become required in v2.0.0.”
     * “In v2.0.0, `share_sum_country` column will be dropped; consumers must recompute sums if needed.”

3. **Hard removal only on MAJOR bump.**

   * Removing fields, relaxing invariants, or otherwise changing semantics MUST be done only with a MAJOR version bump and coordinated changes in S4 and validators.

Historic runs MUST NOT have their `s3_zone_shares` or RNG events mutated in-place to match new contracts.

---

### 12.9 Cross-version operation

Multiple S3 versions may co-exist across different runs and parameter sets.

1. **Per-run contract.**

   * For each `(parameter_hash, manifest_fingerprint, seed, run_id)`, the version of `s3_zone_shares` found in the dictionary/registry defines the contract for that run’s zone shares.
   * Downstream consumers MUST honour each run’s own S3 version when interpreting `s3_zone_shares`.

2. **Consumer strategy.**

   * Consumers (e.g. S4, validation, analytic tools) SHOULD:

     * explicitly support the S3 versions they expect to see, or
     * operate only on the intersection of fields and semantics common across those versions.

3. **No retroactive upgrades.**

   * Existing `s3_zone_shares` partitions and RNG events MUST NOT be rewritten to conform to new S3 contracts.
   * If there is a need to “re-evaluate” S3 under a new contract, this MUST be treated as a new run (new `run_id`, and potentially new `manifest_fingerprint` or `parameter_hash`), with new outputs.

---

Under these rules, 3A.S3 can evolve **incrementally** (extra diagnostics, tighter validation) without breaking S4 and validators, and any genuine changes in Dirichlet sampling behaviour or RNG semantics are clearly marked and versioned so they never silently alter the meaning of existing runs.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix records the symbols and shorthand used in the 3A.S3 design. It has **no normative force**; it’s here so S3, S2, S1 and the validation docs speak the same language.

---

### 13.1 Scalars, hashes & identifiers

* **`parameter_hash`**
  Layer-1 hash over the governed parameter set 𝓟 (priors, floor/bump policy, RNG policy, etc). Fixed before any 3A state runs.

* **`manifest_fingerprint`**
  Layer-1 manifest hash for a run, used by S0 to seal inputs. S3 uses it for `s3_zone_shares` partitioning and lineage.

* **`seed`**
  Layer-1 global RNG seed (`uint64`). Combined with `parameter_hash` and `run_id` to determine Philox streams.

* **`run_id`**
  Run identifier (string or u128-encoded), used as a partition key for RNG events and trace logs and to distinguish multiple S3 realisations under the same `seed`/`parameter_hash`.

* **`merchant_id`**
  Layer-1 merchant identity (`id64`), inherited from 1A/S1.

* **`legal_country_iso` / `country_iso`**
  ISO-3166 alpha-2 country code (e.g. `"GB"`, `"US"`).

  * `legal_country_iso` is the name used in S1/S3 datasets.
  * `country_iso` is the name used in some RNG events; they refer to the same value.

* **`tzid`**
  IANA time zone identifier (e.g. `"Europe/London"`), as defined by 2A and the ingress tz universe.

---

### 13.2 Sets & domains

* **`D` (S1 domain)**
  Set of all merchant×country pairs with at least one outlet under this `{seed,fingerprint}`:

  [
  D = {(m,c) \mid \text{site_count}(m,c) \ge 1 \text{ in } s1_escalation_queue}.
  ]

* **`D_{\text{esc}}` (escalated domain)**

  [
  D_{\text{esc}} = {(m,c) \in D \mid is_escalated(m,c) = true}.
  ]

  The set of merchant×country pairs S3 actually samples.

* **`Z(c)` (zone universe per country)**

  For a given country `c`:

  [
  Z(c) = {\ tzid \mid (country_iso=c, tzid) \in s2_country_zone_priors }.
  ]

  The set of zones for which S2 defined α-priors for country `c`.

* **`Z_{\text{ord}}(c)` (ordered zone list)**

  A deterministically ordered list of `Z(c)`, e.g.:

  [
  Z_{\text{ord}}(c) = [z_1, \dots, z_{K(c)}]
  ]

  where `z_i` are tzids sorted lexicographically. Used by S3 to map uniforms → Γ’s → Dirichlet components.

* **`D_{\text{S3}}` (S3 domain)**

  Domain of `s3_zone_shares` for a given run:

  [
  D_{\text{S3}} = {(m,c,z) \mid (m,c) \in D_{\text{esc}},\ z \in Z(c)}.
  ]

  `s3_zone_shares` must have exactly one row per triple in `D_S3`.

---

### 13.3 Priors & Dirichlet notation

For a given country `c` and tzid `z ∈ Z(c)`:

* **`α_\text{effective}(c,z)`**
  Effective Dirichlet concentration (α) for zone `z` in country `c`, as produced by S2 and stored in `s2_country_zone_priors`.

* **`α_\text{sum\_country}(c)`**

  Total α mass for country `c` from S2:

  [
  \alpha_\text{sum_country}(c) = \sum_{z \in Z(c)} \alpha_\text{effective}(c,z).
  ]

  S3 copies this into `alpha_sum_country` for all rows with `country_iso = c`.

For a given escalated merchant×country pair `(m,c)`:

* **Γ variates:**

  S3 draws independent Gamma variates per zone:

  [
  G_i \sim \mathrm{Gamma}(\alpha_\text{effective}(c,z_i), 1),\quad i=1..\ K(c).
  ]

* **`S(m,c)` (Gamma sum)**

  [
  S(m,c) = \sum_{i=1}^{K(c)} G_i.
  ]

* **`Θ(m,c,z)` (Dirichlet share vector)**

  The Dirichlet sample for `(m,c)` is:

  [
  \Theta(m,c,z_i) = \frac{G_i}{S(m,c)},\quad i=1..\ K(c),\quad z_i \in Z_{\text{ord}}(c).
  ]

  In `s3_zone_shares`, this is stored as `share_drawn` for each `(m,c,z_i)`.

* **`share_sum_country(m,c)`**

  Stored per row in `s3_zone_shares` for each `(m,c)`:

  [
  share_sum_country(m,c) = \sum_{z \in Z(c)} \Theta(m,c,z).
  ]

  Expected ≈ 1, up to floating-point error.

---

### 13.4 RNG notation

* **Philox 2×64-10**
  The Layer-1 PRNG used by S3. Takes 128-bit counters; produces pairs of 64-bit values transformed into `u01` uniforms.

* **`u01`**
  Open-interval uniform variate in `(0,1)`, as defined by the Layer-1 mapping from Philox output to floats.

* **`module`**
  String identifying the producer of RNG events; for S3, typically `"3A.S3"`.

* **`substream_label`**
  String distinguishing logical RNG streams; for S3 Dirichlet events, typically `"zone_dirichlet"`.

* **`rng_stream_id`**
  An implementation-defined but deterministic identifier tying:

  * an S3 Dirichlet RNG event, and
  * its related `s3_zone_shares` rows

  together, often derived from `(merchant_id, country_iso)` and S3’s RNG policy.

* **`rng_event_zone_dirichlet`**
  RNG event family used for S3’s Dirichlet draws, with fields including:

  * `seed`, `parameter_hash`, `run_id`,
  * `module`, `substream_label`, `rng_stream_id`,
  * `counter_before`, `counter_after`, `blocks`, `draws`,
  * `merchant_id`, `country_iso`, `zone_count`.

* **`rng_trace_log`**
  Aggregate log over RNG events; S3 contributes totals for `(seed, parameter_hash, run_id, module="3A.S3", substream_label="zone_dirichlet")`.

---

### 13.5 Datasets & artefacts

* **`s1_escalation_queue`**
  S1’s per-merchant×country classification dataset, partitioned by `{seed,fingerprint}`; S3 reads its `site_count`, `is_escalated`, `decision_reason`.

* **`s2_country_zone_priors`**
  S2’s parameter-scoped prior surface, partitioned by `parameter_hash`; S3 reads `alpha_effective(c,z)`, `alpha_sum_country(c)`, prior/floor policy IDs/versions.

* **`s3_zone_shares`**
  S3’s per-merchant×country×zone share surface, partitioned by `{seed,fingerprint}`; each row has `(merchant_id, legal_country_iso, tzid)` plus `share_drawn`, `share_sum_country`, `alpha_sum_country`, RNG lineage, etc.

* **`s0_gate_receipt_3A` / `sealed_inputs_3A`**
  S0’s gate and sealed-input inventory; S3 reads them to verify upstream gates and find sealed policy artefacts.

* **`rng_event_zone_dirichlet`**
  Dirichlet RNG events emitted by S3; lives in the shared RNG events dataset.

---

### 13.6 Error codes & status (S3)

* **`error_code`**
  Canonical S3 error code from §9, e.g.:

  * `E3A_S3_001_PRECONDITION_FAILED`
  * `E3A_S3_004_DOMAIN_MISMATCH_S1`
  * `E3A_S3_007_RNG_ACCOUNTING_BROKEN`
  * `E3A_S3_011_IMMUTABILITY_VIOLATION`

* **`status`**
  S3 outcome in logs/layer1/3A/run-report:

  * `"PASS"` — S3 met all acceptance criteria; `s3_zone_shares` and Dirichlet RNG events are authoritative for this run.
  * `"FAIL"` — S3 terminated with one of the error codes; its outputs for this run MUST NOT be used.

* **`error_class`**
  Coarse category for `error_code`, e.g.:

  * `"PRECONDITION"`, `"CATALOGUE"`, `"PRIOR_SURFACE"`, `"DOMAIN_S1"`, `"DOMAIN_S2"`, `"ALPHA_RNG"`, `"OUTPUT_SCHEMA"`, `"OUTPUT_INCONSISTENT"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`.

---

These symbols align with S0/S1/S2 and Layer-1 docs so that when you read across:

> S0 (sealed inputs) → S1 (escalation) → S2 (priors) → S3 (Dirichlet shares),

the notation for `D_esc`, `Z(c)`, `α_effective`, `Θ(m,c,z)`, and the RNG streams/counters is consistent and unambiguous.

---
