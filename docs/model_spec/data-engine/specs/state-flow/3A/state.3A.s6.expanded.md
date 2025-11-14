# State 3A·S6 — Structural Validation & Segment Audit

## 1. Purpose & scope *(Binding)*

State **3A.S6 — Structural Validation & Segment Audit** is the **end-to-end validator** for Segment 3A. It does **not** generate or modify any business data, priors, shares, counts, or egress; instead it re-evaluates, aggregates, and records the results of all critical invariants across S0–S5 and their associated logs. Its output is the single source of truth for whether Segment 3A is internally consistent and safe to be marked as “validated” for a given manifest.

Concretely, 3A.S6:

* **Replays and consolidates structural checks across S0–S5.**
  For a given `manifest_fingerprint`, S6:

  * re-runs or re-derives the key invariants from each 3A state (S0–S5) using their own datasets and contracts:

    * S0: gate & sealed inputs (upstream 1A/1B/2A gates; policy/prior sealing; catalogue version coherence),
    * S1: merchant×country domain coverage vs 1A, `site_count` correctness, escalation decisions,
    * S2: country→zone prior surface and zone universes per country, α-sum positivity, absence of stray tzids,
    * S3: alignment between escalated domain and Dirichlet draws, share sums ≈ 1, RNG event coverage and envelope/trace accounting,
    * S4: per-pair count conservation (zone counts sum exactly to `site_count`), domain equality with S1/S2/S3,
    * S5: `zone_alloc` and `zone_alloc_universe_hash` correctness, component digests and combined `routing_universe_hash` consistency.
  * applies each check deterministically and records its outcome (`PASS` / `WARN` / `FAIL`) and summary metrics.

* **Produces a structured validation report for Segment 3A.**
  S6 emits a fingerprint-scoped **validation report** (`s6_validation_report_3A`) that:

  * enumerates all defined check IDs (e.g. `CHK_S1_DOMAIN`, `CHK_S3_RNG_ACCOUNTING`, `CHK_S5_UNIVERSE_HASH`),
  * records, for each check:

    * its status (`PASS`, `WARN`, `FAIL`),
    * counts of affected entities (e.g. number of merchants, countries, zones, or rows touched),
    * optional high-level metrics (e.g. fraction of escalated pairs with zero-mass zones).
  * provides enough structure for automated consumption by higher-level orchestration and validation tools.

  This report is the **authoritative summary** of how S0–S5 performed against their contracts for this manifest.

* **Captures per-entity issues in a machine-readable issue table (optional but recommended).**
  When checks detect localised problems (e.g. a specific `(merchant_id, country_iso, tzid)` with a domain mismatch), S6 may populate an **issue table** (`s6_issue_table_3A`) with one row per issue, including:

  * `issue_code` (linked to a check ID),
  * affected keys (e.g. `merchant_id`, `country_iso`, `tzid`),
  * `severity` (e.g. `ERROR`, `WARN`),
  * a short, structured message or reason code.

  This table is non-authoritative for business data but is the canonical place to look when diagnosing why a check failed or raised warnings.

* **Publishes a compact validation receipt for S7 and cross-segment consumers.**
  S6 produces a small, fingerprint-scoped **validation receipt** (`s6_receipt_3A`) that:

  * encodes the **overall segment status** (`overall_status ∈ {"PASS","FAIL"}`) for 3A on this manifest,
  * contains a stable map from check IDs to their final statuses,
  * includes digests (e.g. a hash of `s6_validation_report_3A` and, optionally, of `s6_issue_table_3A`) so that S7 and external validators can quickly detect tampering or drift,
  * references the versions of S0–S5 contracts and key inputs it validated.

  This receipt is the artefact that S7 (the final bundle & `_passed.flag` state) will use as its single source of truth when deciding whether to mark 3A as validated in the segment-level bundle.

* **Operates in a read-only, RNG-free fashion.**
  3A.S6:

  * MUST NOT modify any S0–S5 outputs or any upstream artefacts (data, priors, policies, logs, egress),
  * MUST NOT consume any RNG (Philox or otherwise),
  * MUST NOT depend on wall-clock time for any decisions (timestamps may be included in reports for human audit only, not for logic),
  * MUST be fully deterministic given:

    * the fixed `(parameter_hash, manifest_fingerprint, seed, run_id)`,
    * the catalogue and S0–S5 artefacts, and
    * the defined set of checks and their thresholds.

  Re-running S6 over the same inputs MUST produce byte-identical `s6_validation_report_3A` and `s6_receipt_3A` (and, if present, `s6_issue_table_3A`), unless upstream artefacts have changed.

Out of scope for 3A.S6:

* S6 does **not** generate or adjust any business data (no new counts, priors, or shares).
* S6 does **not** write the final 3A validation bundle or `_passed.flag`; that responsibility rests with S7, which will package S6’s receipt and related artefacts into the formal segment-level bundle.
* S6 does **not** enforce cross-segment policies (e.g. between 3A and other layers) beyond exposing the information (via its report and receipt) that those higher-level validators need.

Within these bounds, 3A.S6’s sole purpose is to **audit and codify** the health of Segment 3A, turning the distributed guarantees of S0–S5 into a single, well-defined “thumbs-up/thumbs-down” verdict and an accompanying set of structured diagnostics that can be safely used by 3A’s final validation and by any cross-segment governance.

---

## 2. Preconditions & gated inputs *(Binding)*

This section defines **what MUST already hold** and which artefacts S6 is allowed to use before it performs any validation. Anything outside these constraints is **out of scope** for 3A.S6.

S6 is **RNG-free** and **read-only**. Its job is to validate the world that S0–S5 have already constructed; it must never try to “heal” that world.

---

### 2.1 Layer-1 & segment-level preconditions

Before invoking 3A.S6 for a given tuple
`(parameter_hash, manifest_fingerprint, seed, run_id)`, the orchestrator MUST ensure:

1. **Layer-1 identities are fixed and coherent**

   * `parameter_hash`

     * A valid `hex64` string, already computed by the Layer-1 parameter governance logic, denoting a closed parameter set 𝓟 (priors, mixture, floors, day-effect, etc.).
   * `manifest_fingerprint`

     * A valid `hex64` value produced by the Layer-1 manifest mechanism, which includes this `parameter_hash` and the sealed artefacts enumerated in S0.
   * `seed`

     * A valid `uint64` Layer-1 run seed; S6 does not consume RNG but uses `seed` as a partition key and for correlation.
   * `run_id`

     * A stable run identifier (string / u128-encoded) used to tie together this S6 invocation with the S3/S4/S5 runs for the same manifest.

   S6 MUST treat these identifiers as **inputs**, not as values to compute or alter.

2. **3A.S0 gate & sealed inputs exist and are well-formed**

   For `manifest_fingerprint`:

   * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`

     * MUST exist and validate against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`.
     * MUST encode `upstream_gates.segment_1A/1B/2A.status` and the catalogue/policy versions S0 used.

   * `sealed_inputs_3A@fingerprint={manifest_fingerprint}`

     * MUST exist and validate against `schemas.3A.yaml#/validation/sealed_inputs_3A`.
     * MUST list all external policy/prior artefacts S1–S5 claim to use (mixture policy, prior pack, floor policy, day-effect policy, zone-universe references, etc.), with `sha256_hex` digests.

   If either artefact is missing or fails schema validation, S6 MUST mark the run as FAIL (`E3A_S6_001_PRECONDITION_FAILED`) and MUST NOT proceed to deeper checks.

3. **3A.S1–S5 have run and produced their surfaces**

   For this `(parameter_hash, manifest_fingerprint, seed, run_id)` (or, in the case of S2, for `parameter_hash`):

   * Datasets MUST exist and be schema-valid:

     * `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}`
     * `s2_country_zone_priors@parameter_hash={parameter_hash}`
     * `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}`
     * `s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}`
     * `zone_alloc@seed={seed}/fingerprint={manifest_fingerprint}`
     * `zone_alloc_universe_hash@fingerprint={manifest_fingerprint}`

   * Segment-state run-report entries MUST exist for S1–S5, each with at least:

     * `layer="layer1"`, `segment="3A"`, appropriate `state`, and this run’s identity fields.

   S6 does **not** require S1–S5 to be `status="PASS"` as a precondition; rather, it uses those statuses as part of its own checks. A missing dataset or malformed schema, however, is a **precondition failure** (S6 cannot even evaluate the checks) and MUST result in `E3A_S6_001_PRECONDITION_FAILED` or `E3A_S6_002_CATALOGUE_MALFORMED`.

4. **RNG logs for S3 are available**

   For the Dirichlet sampling state S3:

   * The Layer-1 RNG events dataset MUST contain entries for:

     * `module="3A.S3"`, `substream_label="zone_dirichlet"`,
     * partitioned by `seed={seed}`, `parameter_hash={parameter_hash}`, `run_id={run_id}` (per the Layer-1 RNG spec).

   * The Layer-1 `rng_trace_log` MUST contain corresponding aggregate entries for the same `(seed, parameter_hash, run_id, module, substream_label)`.

   These logs MUST validate against the RNG schemas declared in `schemas.layer1.yaml`. If they are missing or malformed, S6 cannot verify RNG accounting and MUST fail with a precondition or catalogue error.

---

### 2.2 Gated external inputs (via S0)

S6 may need to re-parse certain **external** artefacts (priors, policies, references) when reproducing S1–S5 checks. It MUST do so only for artefacts that are listed and sealed in `sealed_inputs_3A`.

For every external artefact S6 reads (non-3A dataset), S6 MUST:

1. **Resolve via catalogue & sealed inputs**

   * Use dataset dictionaries / registries to resolve its `logical_id`, `path`, and `schema_ref`.
   * Confirm that `sealed_inputs_3A` contains a row with the same `logical_id` and `path`, and a recorded `sha256_hex`.

2. **Verify shape & digest**

   * Read the artefact bytes (e.g. YAML/JSON for policies; Parquet for zone-universe or ISO tables).
   * Validate against the declared `schema_ref` (from `schemas.layer1.yaml` / `schemas.ingress.layer1.yaml` / `schemas.2A.yaml` / `schemas.3A.yaml`).
   * Recompute SHA-256 over the bytes and assert equality with `sealed_inputs_3A.sha256_hex`.

If any external artefact S6 intends to use:

* is not present in `sealed_inputs_3A`, or
* fails schema validation, or
* has a digest mismatch,

S6 MUST record a precondition failure (`E3A_S6_001_PRECONDITION_FAILED`) and **stop**; it MUST NOT attempt to “repair” or ignore the discrepancy.

Typical external artefacts S6 may need to re-inspect include:

* Zone mixture policy (`zone_mixture_policy_3A`) — to confirm S1 used the sealed version.
* Country→zone prior pack (`country_zone_alphas_3A`) and zone floor policy (`zone_floor_policy_3A`) — to cross-check S2.
* Day-effect policy (`day_effect_policy_v1`) — to validate S5’s `day_effect_digest`.
* ISO and zone-universe references (e.g. `iso3166_canonical_2024`, `country_tz_universe` or `tz_world_2025a`) — for structural checks on country and tzid sets.

---

### 2.3 3A internal inputs & their roles

Within Segment 3A, S6 is allowed to read, but not modify, the following **internal** datasets and metadata. Each comes with a specific role in validation; S6 MUST respect their authority boundaries:

* **`s1_escalation_queue`**

  * Source of:

    * merchant×country domain `D`,
    * total outlet counts `site_count(m,c)`,
    * escalation flags and reasons.
  * S6 uses this to cross-check:

    * 1A domain & counts,
    * S3/S4/S5 domains and per-pair totals.

* **`s2_country_zone_priors`**

  * Source of:

    * zone universes `Z(c)`,
    * α-sum and prior/floor lineage.
  * S6 uses this to verify:

    * S3/S4/S5 zone sets,
    * S5 `zone_alpha_digest` consistency.

* **`s3_zone_shares` + S3 RNG logs**

  * Source of:

    * Dirichlet share vectors `Θ(m,c,z)`,
    * RNG event and trace data for `rng_event_zone_dirichlet`.
  * S6 uses this to verify:

    * S3 domain coverage, share sums, and RNG accounting,
    * S4 integerisation replay from `(N, Θ)`, if needed.

* **`s4_zone_counts`**

  * Source of:

    * `zone_site_count(m,c,z)` and `zone_site_count_sum(m,c)` per escalated pair.
  * S6 uses this to verify:

    * count conservation vs S1,
    * domain alignment vs S2/S3,
    * correctness of S4’s deterministic integerisation.

* **`zone_alloc`**

  * Source of:

    * egress projection of zone counts,
    * embedded `routing_universe_hash` and policy lineage.
  * S6 uses this to verify:

    * equality of counts vs `s4_zone_counts`,
    * consistency between `zone_alloc` and the universe hash artefact.

* **`zone_alloc_universe_hash`**

  * Source of:

    * component digests (`zone_alpha_digest`, `theta_digest`, `zone_floor_digest`, `day_effect_digest`, `zone_alloc_parquet_digest`),
    * combined `routing_universe_hash`.
  * S6 uses this to validate:

    * recomputed digests vs recorded digests,
    * recomputed combined hash vs recorded `routing_universe_hash`,
    * equality of `routing_universe_hash` between this artefact and `zone_alloc`.

S6 MUST treat all of these as **inputs** to validation. It MUST NOT write to or alter them.

---

### 2.4 RNG & invocation-level constraints

Finally, S6 has the following absolute constraints:

1. **No RNG consumption**

   * S6 MUST NOT invoke Philox or any other RNG.
   * All checks MUST be deterministic functions of their inputs; any perceived randomness stems only from S3’s prior draws, never from S6.

2. **No data mutation**

   * S6 MUST NOT modify:

     * S0 artefacts (`s0_gate_receipt_3A`, `sealed_inputs_3A`),
     * any S1–S5 datasets or logs,
     * any upstream Layer-1 or 2B artefacts.
   * S6’s only writable artefacts are its own validation outputs:

     * `s6_validation_report_3A`,
     * `s6_issue_table_3A` (if used),
     * `s6_receipt_3A`.

3. **Deterministic and idempotent behaviour**

   * Given the same `(parameter_hash, manifest_fingerprint, seed, run_id)` and unchanged inputs (catalogue + datasets/artefacts), S6 MUST produce:

     * byte-identical `s6_validation_report_3A`,
     * byte-identical `s6_issue_table_3A` (if present),
     * byte-identical `s6_receipt_3A`.
   * If S6 is re-run and its newly computed outputs differ from existing ones for the same `manifest_fingerprint`, this is an immutability violation and MUST be treated as a failure (see §9).

Within these preconditions and gated inputs, 3A.S6 has a well-defined, read-only, deterministic view of the entire 3A world and is ready to apply its validation algorithm as defined in subsequent sections.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes **exactly what 3A.S6 is allowed to look at**, what each input is **authoritative for**, and where S6’s own authority **stops**.

S6 is **purely read-only**; it may only assert whether upstream contracts were honoured. It MUST NOT change any S0–S5 artefacts or any upstream segments.

---

### 3.1 Catalogue & schema packs (shape-only authority)

S6 relies on the Layer-1 catalogue to tell it **what exists** and **how it is shaped**. It MUST treat these artefacts as **shape/metadata authorities only**:

1. **Schema packs**

   * `schemas.layer1.yaml`
   * `schemas.ingress.layer1.yaml`
   * `schemas.2A.yaml`
   * `schemas.3A.yaml`

   S6 MAY:

   * use them to validate the structure of every dataset/artefact it reads (S0–S5, RNG logs, S6 outputs),
   * resolve `schema_ref` anchors for its own validation outputs.

   S6 MUST NOT:

   * redefine primitives or RNG envelopes,
   * treat schema content as mutable,
   * invent ad-hoc shapes outside these packs.

2. **Dataset dictionaries & artefact registries**

   * `dataset_dictionary.layer1.{1A,2A,3A}.yaml`
   * `artefact_registry_{1A,1B,2A,2B,3A}.yaml`

   S6 MAY:

   * use them to resolve dataset IDs → paths/partitioning/`schema_ref`,
   * use registry entries to determine which artefacts are part of the manifest and what roles they play.

   S6 MUST NOT:

   * hard-code paths or schema anchors,
   * write any new datasets that lack dictionary/registry entries,
   * edit dictionary/registry content.

The catalogue layer sits **above** S6; S6 can only check whether S0–S5 and RNG logs obey what the catalogue declares.

---

### 3.2 3A internal artefacts: S0–S5 (contract authority)

S6 treats S0–S5 artefacts as **“contract instances”**. It does not overwrite them; it only checks whether each state obeyed its own spec and how those specs line up.

S6 MAY read:

1. **S0 — Gate & sealed inputs**

   * `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`
   * `sealed_inputs_3A@fingerprint={manifest_fingerprint}`

   S6 uses these as **trust anchors** to:

   * confirm upstream segment gates (1A/1B/2A) are PASS,
   * confirm that the priors/policies S1–S5 claim to use are sealed and have stable digests,
   * check catalogue version coherence (which schema/dictionary/registry versions S0 recorded).

   S6 MUST NOT modify or reinterpret S0’s gate semantics; if S0’s content is inconsistent with other artefacts, S6 MUST flag that inconsistency, not “fix” it.

2. **S1 — Escalation & merchant×country domain**

   * `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}`
   * S1’s run-report row.

   S6 uses S1 as the authority on:

   * which `(merchant_id, legal_country_iso)` pairs exist (`D`),
   * which pairs are escalated (`D_esc`),
   * per-pair totals `site_count(m,c)`.

   S6:

   * MAY cross-check S1’s domain/`site_count` against 1A and S2–S5,
   * MUST NOT alter `site_count` or `is_escalated` anywhere.

3. **S2 — Priors & zone universe**

   * `s2_country_zone_priors@parameter_hash={parameter_hash}`
   * S2’s run-report row.

   S6 uses S2 as the authority on:

   * zone universe `Z(c)` per country,
   * `alpha_sum_country(c)` and prior/floor lineage,
   * basis for `zone_alpha_digest`.

   S6:

   * MAY assert whether S3/S4/S5 use exactly `Z(c)`,
   * MUST NOT add/drop zones or recompute α’s.

4. **S3 — Shares & RNG usage**

   * `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}`
   * `rng_event_zone_dirichlet` events for `(seed, parameter_hash, run_id, module="3A.S3", substream_label="zone_dirichlet")`,
   * `rng_trace_log` entries for `("3A.S3", "zone_dirichlet")`,
   * S3’s run-report row.

   S6 uses S3 as the authority on:

   * per-pair zone share vectors `Θ(m,c,z)`,
   * which escalated pairs actually had Dirichlet draws,
   * how many Philox uniforms were consumed (and where).

   S6:

   * MAY replay Dirichlet draws for validation,
   * MAY check envelope and trace accounting,
   * MUST NOT resample or change shares, or “fix” RNG counters.

5. **S4 — Integer zone counts**

   * `s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}`
   * S4’s run-report row.

   S6 uses S4 as the authority on:

   * integer zone counts `zone_site_count(m,c,z)` and `zone_site_count_sum(m,c)`,
   * S4’s declared integerisation scheme from `(N, Θ)`.

   S6:

   * MAY replay integerisation from `(site_count, share_drawn)` and compare with S4’s counts,
   * MUST NOT modify counts or recompute a “better” integerisation.

6. **S5 — Egress & universe hash**

   * `zone_alloc@seed={seed}/fingerprint={manifest_fingerprint}`
   * `zone_alloc_universe_hash@fingerprint={manifest_fingerprint}`
   * S5’s run-report row.

   S6 uses S5 as the authority on:

   * final cross-layer zone allocation snapshot (projection of S4),
   * component digests (`zone_alpha_digest`, `theta_digest`, `zone_floor_digest`, `day_effect_digest`, `zone_alloc_parquet_digest`),
   * combined `routing_universe_hash` for this manifest.

   S6:

   * MAY recompute all these digests and the combined hash to check correctness,
   * MUST NOT change counts or hashes; inconsistencies are treated as validation failures, not patched.

---

### 3.3 External artefacts (priors, policies, references)

S6 may need to read certain **external** inputs to verify that S0–S5 used them correctly. These MUST be referenced via `sealed_inputs_3A` and the catalogue.

S6 MAY read:

* **Mixture policy** — `zone_mixture_policy_3A` (3A, role `"zone_mixture_policy"`).
* **Prior pack** — `country_zone_alphas_3A` (3A, role `"country_zone_alphas"`).
* **Floor/bump policy** — `zone_floor_policy_3A` (3A, role `"zone_floor_policy"`).
* **Day-effect policy** — `day_effect_policy_v1` (2B, role `"day_effect_policy"`).
* **Structural references** — `iso3166_canonical_2024`, `country_tz_universe` or `tz_world_2025a`, etc.

For each, S6:

* uses S0 to confirm the artefact is sealed and has a stable digest,
* uses the relevant schema to validate shape,
* recomputes digests to check S5’s `zone_alloc_universe_hash` is correct.

S6 MUST treat these artefacts as **opaque** for validation purposes (content is interpreted only insofar as it affects upstream contracts); it MUST NOT treat them as mutable configuration knobs.

---

### 3.4 S6’s own authority vs upstream/downstream

**What S6 owns:**

* The **validation perspective** on 3A for a given `manifest_fingerprint`:

  * The list of checks performed, their outcomes, and associated metrics (`s6_validation_report_3A`).
  * The list of concrete issues (if emitted) in `s6_issue_table_3A`.
  * The compact statement of segment-level status and report hashes in `s6_receipt_3A`.

* The decision logic for **when Segment 3A is considered “validated”** at S6 level (subject to S7 packaging it into the final bundle).

**What S6 does *not* own:**

* Any underlying **business data** or allocations (S1–S5).
* Any **priors/policies** content; that’s owned by 3A/2B governance and 𝓟.
* Any **RNG behaviour**; that’s owned by S3 and Layer-1 RNG infrastructure.
* The final `_passed.flag` and segment-level validation bundle; those are S7’s authority.

S6’s job is to **diagnose and report**, not to mutate or re-interpret upstream behaviour.

---

### 3.5 Explicit “MUST NOT” list for S6

To keep boundaries sharp, S6 is explicitly forbidden from:

* **Changing inputs**

  * MUST NOT modify:

    * S0 artefacts (`s0_gate_receipt_3A`, `sealed_inputs_3A`),
    * any S1–S5 datasets (`s1`…`s4`, `zone_alloc`, `zone_alloc_universe_hash`),
    * RNG logs (`rng_event_*`, `rng_trace_log`),
    * any upstream ingress or policy artefacts.

* **Introducing new business semantics**

  * MUST NOT adjust counts (`site_count`, `zone_site_count`, etc.),
  * MUST NOT adjust shares, priors or policy parameters,
  * MUST NOT attempt to “heal” domains or patch inconsistencies by rewriting data.

* **Consuming RNG or time**

  * MUST NOT call RNG functions (Philox or otherwise),
  * MUST NOT use system time (`now()`) to affect any validation decision or output values (timestamps, if present, are purely informative).

* **Reading unsealed external artefacts**

  * MUST NOT read any external artefact that does not appear in `sealed_inputs_3A` for this `manifest_fingerprint`.
  * MUST NOT treat environment variables, local files, or ad-hoc configuration as validation inputs.

Within these boundaries, S6’s inputs and authority are tightly scoped: it sees **everything** 3A did (and the key upstream surfaces), checks that they all agree with their contracts, and emits a clear, immutable validation verdict and diagnostics—without altering any of the underlying state.

---

## 4. Outputs (datasets & reports) & identity *(Binding)*

3A.S6 produces **validation artefacts only**. It does **not** emit any new business data, nor does it modify S0–S5 outputs.

S6 has up to **three** outputs:

1. A **segment-level validation report** (`s6_validation_report_3A`).
2. An optional but recommended **issue table** (`s6_issue_table_3A`).
3. A compact **validation receipt** (`s6_receipt_3A`) used by S7 and cross-segment validators.

All three are **fingerprint-scoped** and logically tied to a single `manifest_fingerprint`.

---

### 4.1 Overview of S6 outputs

For each `manifest_fingerprint = F`, S6 MUST produce **exactly one**:

* `s6_validation_report_3A(F)`
* `s6_receipt_3A(F)`

and MAY produce zero or one:

* `s6_issue_table_3A(F)` (it is valid to have no issues and therefore no issue rows; the dataset itself still exists as an empty table).

No other persistent artefacts are owned by S6 in this contract version.

---

### 4.2 `s6_validation_report_3A` — segment-level validation report

#### 4.2.1 Identity & scope

* **Dataset ID (logical):** `s6_validation_report_3A`
* **Partitioning:** `["fingerprint"]`
* **Scope:** exactly **one report object** per `manifest_fingerprint`.

Conceptually:

* Path pattern:
  `data/layer1/3A/s6_validation_report/fingerprint={manifest_fingerprint}/report.json`
* The report is a single JSON object (or single-row table) summarising all checks and aggregate metrics for 3A on this manifest.

#### 4.2.2 Logical content

` s6_validation_report_3A` MUST contain, at minimum:

* **Identity:**

  * `manifest_fingerprint` — `hex64`, MUST match the path token `{fingerprint}`.
  * `parameter_hash` — `hex64`, tying this report to the parameter set 𝓟.

* **Overall summary:**

  * `overall_status ∈ {"PASS","FAIL"}` — S6’s own judgement of the segment-level status for 3A, based on all checks.
  * `checks_passed_count` — integer ≥ 0.
  * `checks_failed_count` — integer ≥ 0.
  * `checks_warn_count` — integer ≥ 0.

* **Per-check results (core structure):**

  * `checks` — an array or map keyed by **check ID**, where each entry has:

    * `check_id` — string, from a closed vocabulary (e.g. `"CHK_S1_DOMAIN"`, `"CHK_S3_RNG_ACCOUNTING"`, `"CHK_S5_UNIVERSE_HASH"`).
    * `status ∈ {"PASS","WARN","FAIL"}`.
    * `severity ∈ {"INFO","WARN","ERROR"}` — how bad a non-PASS is.
    * `affected_count` — integer ≥ 0 (e.g. number of merchants or zones impacted).
    * `notes` — optional short string giving human-readable context.

* **Aggregate metrics (examples; the precise list defined in the schema):**

  * `pairs_total` — number of merchant×country pairs in S1.
  * `pairs_escalated` — number of escalated pairs.
  * `zones_total` — total `(country, tzid)` combinations from S2.
  * `zone_rows_s3` — number of rows in `s3_zone_shares`.
  * `zone_rows_s4` — number of rows in `s4_zone_counts`.
  * `zone_rows_alloc` — number of rows in `zone_alloc`.
  * `rng_events_dirichlet_total` — number of Dirichlet RNG events for S3.
  * `rng_draws_dirichlet_total` — total `draws` for S3’s Dirichlet events.

Additional metrics MAY be included in a structured field (e.g. `metrics: { ... }`) as long as the schema enforces types and the values are deterministically derived from inputs.

#### 4.2.3 Authoritative role

` s6_validation_report_3A` is the **authoritative narrative** of:

* which checks were run,
* how they turned out, and
* what aggregate statistics the checks observed.

It is:

* **consumed by:**

  * 3A.S7 (validation bundle and `_passed.flag`),
  * cross-segment validation harnesses,
  * operators and monitoring tools.
* **not** a business surface; it carries only validation/diagnostic content.

---

### 4.3 `s6_issue_table_3A` — per-entity issue table (optional but recommended)

#### 4.3.1 Identity & scope

* **Dataset ID (logical):** `s6_issue_table_3A`
* **Partitioning:** `["fingerprint"]`
* **Scope:** 0 or more rows per `manifest_fingerprint`, each describing a specific issue.

Conceptual path:

* `data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet`

#### 4.3.2 Logical content (row-level)

Each row in `s6_issue_table_3A` represents a **single issue instance** and MUST contain, at minimum:

* **Identity:**

  * `manifest_fingerprint` — `hex64`; MUST match the partition token.

* **Issue classification:**

  * `issue_code` — string; usually derived from the check ID (e.g. `"CHK_S1_DOMAIN_MISSING_PAIR"`, `"CHK_S3_RNG_EVENT_MISSING"`).
  * `severity ∈ {"INFO","WARN","ERROR"}`.
  * `check_id` — the ID of the parent check from the report (e.g. `"CHK_S3_RNG_ACCOUNTING"`).

* **Affected entity keys** (may be nullable per issue type):

  * `merchant_id` — `id64` or null (if not applicable).
  * `legal_country_iso` — `iso2` or null.
  * `tzid` — `iana_tzid` or null.
  * Additional keys may be added in future (e.g. `zone_group_id`, `rng_stream_id`) with clear semantics.

* **Details:**

  * `message` — short human-readable description (e.g. “Escalated pair has no shares in s3_zone_shares”).
  * `details` — optional structured object or string containing machine-readable detail (e.g. expected vs observed counts).

#### 4.3.3 Role

` s6_issue_table_3A` is:

* **consumed by:**

  * debugging and operator tooling,
  * offline analysis of validation issues,
  * S7 (if it wants to include issue counts or severity summaries in the final bundle).
* **not required** for the 3A segment to function, but strongly recommended to avoid burying detailed issues inside a monolithic JSON report.

Absence of rows for a given `manifest_fingerprint` is interpreted as “no issues recorded” (but the report still governs overall status).

---

### 4.4 `s6_receipt_3A` — compact validation receipt

#### 4.4.1 Identity & scope

* **Dataset ID (logical):** `s6_receipt_3A`
* **Partitioning:** `["fingerprint"]`
* **Scope:** exactly **one** receipt object per `manifest_fingerprint`.

Conceptual path:

* `data/layer1/3A/s6_receipt/fingerprint={manifest_fingerprint}/s6_receipt.json`

#### 4.4.2 Logical content

` s6_receipt_3A` MUST contain, at minimum:

* **Identity & contract versioning:**

  * `manifest_fingerprint` — `hex64`; equals partition token.
  * `parameter_hash` — `hex64`.
  * `s6_version` — version of the S6 contract/report schema (e.g. `"1.0.0"`).
  * `s0_version` … `s5_version` — optional; record which versions of upstream state contracts were assumed (if available in the catalogue).

* **Overall status:**

  * `overall_status ∈ {"PASS","FAIL"}` — S6’s overall judgement for 3A on this manifest.
  * `checks_passed_count`, `checks_failed_count`, `checks_warn_count` — as in the report.

* **Check status map:**

  * `check_status_map` — a map from `check_id` → `status ∈ {"PASS","WARN","FAIL"}`.

    * This MUST match the per-check statuses in `s6_validation_report_3A`.

* **Hashes/digests:**

  * `validation_report_digest` — SHA-256 (hex) of a canonical serialisation of `s6_validation_report_3A` (e.g. JSON with sorted keys).
  * `issue_table_digest` — optional SHA-256 (hex) of `s6_issue_table_3A` (e.g. concatenating Parquet files in lexicographic order), or a sentinel value if no issues table exists.

These digests allow S7 and external harnesses to quickly detect whether:

* the report and issues table have changed or been tampered with, or
* a receipt and report/issue-table pair are mismatched.

#### 4.4.3 Role

` s6_receipt_3A` is the **compact, machine-friendly verdict** consumed by:

* **S7** — the final 3A validation bundle builder and `_passed.flag` writer, which will:

  * ensure `overall_status == "PASS"` before marking 3A as validated,
  * pull in `s6_validation_report_3A` and (optionally) `s6_issue_table_3A` into the bundle,
  * assert that reported digests match the embedded artefacts.

* **Cross-segment validators** — which may:

  * look only at `overall_status` and a small subset of check IDs,
  * use `validation_report_digest` to detect drift between previously seen reports and current ones.

The receipt itself carries **no business data**; it only summarises validation results and their provenance.

---

### 4.5 Partitions, identity & immutability guarantees

For all S6 outputs:

* **Partitioning:**

  * `s6_validation_report_3A` → `["fingerprint"]`
  * `s6_issue_table_3A` → `["fingerprint"]`
  * `s6_receipt_3A` → `["fingerprint"]`

* **Identity:**

  * Each `manifest_fingerprint` MUST have:

    * exactly one report (`s6_validation_report_3A`),
    * exactly one receipt (`s6_receipt_3A`),
    * zero or more issue rows (but exactly one `issues` dataset partition).

* **Immutability:**

  * Once S6 has written its report and receipt for a given `manifest_fingerprint`, they MUST be treated as immutable.
  * If S6 is re-run for the same inputs and the newly computed report/receipt differs from existing ones, S6 MUST NOT overwrite and MUST raise an immutability error.

Within these constraints, S6’s outputs form a stable, fingerprint-scoped validation layer on top of S0–S5: a structured report, a per-entity issue list, and a compact receipt that Segment 3A and cross-layer governance can safely rely on when deciding whether 3A is “green” for a given manifest.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes **where S6’s outputs live** in the authority chain:

* which JSON-Schema anchors define their shape,
* how they are declared in the Layer-1 dataset dictionary, and
* how they are registered in the 3A artefact registry.

Everything here is **normative** for:

* `s6_validation_report_3A`
* `s6_issue_table_3A`
* `s6_receipt_3A`

No other S6 datasets are in scope for this contract version.

---

### 5.1 Segment schema pack for S6

S6 uses the Segment-3A schema pack:

* **Schema pack ID:** `schemas.3A.yaml`
* **Role:** shape authority for S6’s outputs and all other 3A artefacts.

`schemas.3A.yaml` MUST:

1. Reuse Layer-1 primitives via `$ref: "schemas.layer1.yaml#/$defs/…"`, e.g.:

   * `hex64`, `uint64`, `id64`, `iso2`, `iana_tzid`, `rfc3339_micros`, etc.

2. Define three new anchors:

   * `#/validation/s6_validation_report_3A` — for the segment-level validation report object.
   * `#/validation/s6_issue_table_3A` — for per-issue rows in the issue table.
   * `#/validation/s6_receipt_3A` — for the compact validation receipt.

No other schema pack may define these shapes.

---

### 5.2 Schema anchor: `#/validation/s6_validation_report_3A`

`schemas.3A.yaml#/validation/s6_validation_report_3A` defines the **top-level validation report** as a single JSON object.

At minimum, the schema MUST enforce:

* **Type:** `object`

* **Required properties:**

  * `manifest_fingerprint`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `parameter_hash`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `overall_status`

    * `type: "string"`
    * `enum: ["PASS", "FAIL"]`

  * `checks_passed_count`

    * `type: "integer"`
    * `minimum: 0`

  * `checks_failed_count`

    * `type: "integer"`
    * `minimum: 0`

  * `checks_warn_count`

    * `type: "integer"`
    * `minimum: 0`

  * `checks`

    * `type: "array"`
    * `items`:

      * `type: "object"`
      * `required: ["check_id", "status", "severity", "affected_count"]`
      * `properties`:

        * `check_id` — `type: "string"` (e.g. `"CHK_S1_DOMAIN"`)
        * `status`   — `type: "string"`, `enum: ["PASS", "WARN", "FAIL"]`
        * `severity` — `type: "string"`, `enum: ["INFO", "WARN", "ERROR"]`
        * `affected_count` — `type: "integer"`, `minimum: 0`
        * `notes` — `type: "string"` (optional)
      * `additionalProperties: false`

* **Optional metrics section** (non-exhaustive, but structured):

  * `metrics`

    * `type: "object"`
    * `additionalProperties` MAY be allowed but SHOULD be typed where known, e.g.:

      * `properties` (examples):

        * `pairs_total` — `type: "integer"`, `minimum: 0`
        * `pairs_escalated` — `type: "integer"`, `minimum: 0`
        * `zones_total` — `type: "integer"`, `minimum: 0`
        * `zone_rows_s3` — `type: "integer"`, `minimum: 0`
        * `zone_rows_s4` — `type: "integer"`, `minimum: 0`
        * `zone_rows_alloc` — `type: "integer"`, `minimum: 0`
        * `rng_events_dirichlet_total` — `type: "integer"`, `minimum: 0`
        * `rng_draws_dirichlet_total` — `type: "integer"`, `minimum: 0`

      * `additionalProperties: true` MAY be allowed to permit future metrics, but implementation SHOULD document new metrics in the spec and use predictable naming.

* **Additional properties (top-level):**

  * `additionalProperties: false`

    * If flexible extension is desired, the spec can instead permit an `x_debug` or `extensions` object; in this version we forbid stray top-level fields.

The `manifest_fingerprint` field MUST equal the partition token `{fingerprint}` when stored.

---

### 5.3 Schema anchor: `#/validation/s6_issue_table_3A`

`schemas.3A.yaml#/validation/s6_issue_table_3A` defines the **row shape** of the per-issue table.

Each row MUST obey:

* **Type:** `object`

* **Required properties:**

  * `manifest_fingerprint`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `issue_code`

    * `type: "string"`
    * Short code such as `"CHK_S1_DOMAIN_MISSING_PAIR"`.

  * `check_id`

    * `type: "string"`
    * MUST correspond to one of the check IDs defined in the report.

  * `severity`

    * `type: "string"`
    * `enum: ["INFO", "WARN", "ERROR"]`

  * `message`

    * `type: "string"`

* **Optional properties (entity keys & details):**

  * `merchant_id`

    * `$ref: "schemas.layer1.yaml#/$defs/id64"`
    * `nullable: true` (if the issue is not merchant-specific).

  * `legal_country_iso`

    * `$ref: "schemas.layer1.yaml#/$defs/iso2"`
    * `nullable: true`.

  * `tzid`

    * `$ref: "schemas.layer1.yaml#/$defs/iana_tzid"`
    * `nullable: true`.

  * `details`

    * `type: "string"` or
    * `type: "object"` (if a structured details schema is desired; for this version, likely `string`).

* **Additional properties:**

  * `additionalProperties: false`

    * As with the report: new fields should be added via a version bump, not free-form.

---

### 5.4 Schema anchor: `#/validation/s6_receipt_3A`

`schemas.3A.yaml#/validation/s6_receipt_3A` defines the **compact validation receipt** object.

At minimum, it MUST enforce:

* **Type:** `object`

* **Required properties:**

  * `manifest_fingerprint`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `parameter_hash`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `s6_version`

    * `type: "string"` (semver of the S6 contract, e.g. `"1.0.0"`)

  * `overall_status`

    * `type: "string"`
    * `enum: ["PASS", "FAIL"]`

  * `checks_passed_count`

    * `type: "integer"`, `minimum: 0`

  * `checks_failed_count`

    * `type: "integer"`, `minimum: 0`

  * `checks_warn_count`

    * `type: "integer"`, `minimum: 0`

  * `check_status_map`

    * `type: "object"`
    * Keys: `check_id` strings
    * Values: objects with at least:

      * `status` — `type: "string"`, `enum: ["PASS","WARN","FAIL"]`
      * (Optional) `severity` — `type: "string"`, `enum: ["INFO","WARN","ERROR"]`

  * `validation_report_digest`

    * `type: "string"` (hex SHA-256 of the canonical serialisation of `s6_validation_report_3A`).

* **Optional properties:**

  * `issue_table_digest`

    * `type: "string"` (hex SHA-256 of the underlying issue-table files), or
    * a sentinel value (e.g. `"none"`) if no issue table exists.

  * `created_at_utc`

    * `$ref: "schemas.layer1.yaml#/$defs/rfc3339_micros"` (audit only; MUST NOT be used as input to the digests).

  * `notes`

    * `type: "string"`.

* **Additional properties:**

  * `additionalProperties: false`.

The `manifest_fingerprint` field MUST equal the `{fingerprint}` partition token.

---

### 5.5 Dataset dictionary entries: `dataset_dictionary.layer1.3A.yaml`

The 3A dataset dictionary MUST declare S6’s outputs as datasets.

#### 5.5.1 `s6_validation_report_3A`

```yaml
datasets:
  - id: "s6_validation_report_3A"
    subsegment: "3A"
    version: "1.0.0"
    path: "data/layer1/3A/s6_validation_report/fingerprint={manifest_fingerprint}/report.json"
    format: "json"
    partitioning: ["fingerprint"]
    schema_ref: "schemas.3A.yaml#/validation/s6_validation_report_3A"
    ordering: []              # single logical object; no row ordering
    lineage:
      produced_by: ["3A.S6"]
      consumed_by: ["3A.S7", "3A.validation", "cross_segment_validation"]
    final_in_layer: false
    role: "Segment 3A structural validation report per manifest_fingerprint"
```

#### 5.5.2 `s6_issue_table_3A`

```yaml
  - id: "s6_issue_table_3A"
    subsegment: "3A"
    version: "1.0.0"
    path: "data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet"
    format: "parquet"
    partitioning: ["fingerprint"]
    schema_ref: "schemas.3A.yaml#/validation/s6_issue_table_3A"
    ordering: ["issue_code", "severity", "merchant_id", "legal_country_iso", "tzid"]
    lineage:
      produced_by: ["3A.S6"]
      consumed_by: ["3A.validation", "ops_tooling"]
    final_in_layer: false
    role: "Per-issue validation findings for Segment 3A at this manifest_fingerprint"
```

#### 5.5.3 `s6_receipt_3A`

```yaml
  - id: "s6_receipt_3A"
    subsegment: "3A"
    version: "1.0.0"
    path: "data/layer1/3A/s6_receipt/fingerprint={manifest_fingerprint}/s6_receipt.json"
    format: "json"
    partitioning: ["fingerprint"]
    schema_ref: "schemas.3A.yaml#/validation/s6_receipt_3A"
    ordering: []              # single logical object
    lineage:
      produced_by: ["3A.S6"]
      consumed_by: ["3A.S7", "cross_segment_validation"]
    final_in_layer: false
    role: "Compact validation receipt for Segment 3A; overall_status and report digests per manifest_fingerprint"
```

Binding requirements:

* IDs MUST be exactly as declared (`"s6_validation_report_3A"`, `"s6_issue_table_3A"`, `"s6_receipt_3A"`).
* Paths MUST include `fingerprint={manifest_fingerprint}` as the only partition token.
* `schema_ref` MUST reference the anchors defined above.

---

### 5.6 Artefact registry entries: `artefact_registry_3A.yaml`

For each manifest (`manifest_fingerprint`), the 3A artefact registry MUST include entries for S6’s artefacts.

#### 5.6.1 `s6_validation_report_3A`

```yaml
- manifest_key: "mlr.3A.s6_validation_report"
  name: "Segment 3A S6 validation report"
  subsegment: "3A"
  type: "dataset"
  category: "validation"
  path: "data/layer1/3A/s6_validation_report/fingerprint={manifest_fingerprint}/report.json"
  schema: "schemas.3A.yaml#/validation/s6_validation_report_3A"
  version: "1.0.0"
  digest: "<sha256_hex>"       # SHA-256 of the report.json bytes
  dependencies:
    - "mlr.3A.s0_gate_receipt"
    - "mlr.3A.s1_escalation_queue"
    - "mlr.3A.s2_country_zone_priors"
    - "mlr.3A.s3_zone_shares"
    - "mlr.3A.s4_zone_counts"
    - "mlr.3A.zone_alloc"
    - "mlr.3A.zone_alloc_universe_hash"
    - "mlr.layer1.rng_events"
    - "mlr.layer1.rng_trace_log"
  role: "Segment 3A structural validation summary per manifest_fingerprint"
  cross_layer: true
```

#### 5.6.2 `s6_issue_table_3A`

```yaml
- manifest_key: "mlr.3A.s6_issue_table"
  name: "Segment 3A S6 per-issue validation findings"
  subsegment: "3A"
  type: "dataset"
  category: "validation"
  path: "data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet"
  schema: "schemas.3A.yaml#/validation/s6_issue_table_3A"
  version: "1.0.0"
  digest: "<sha256_hex>"       # SHA-256 over canonical concatenation of issue files
  dependencies:
    - "mlr.3A.s6_validation_report"
  role: "Detailed record of individual validation issues for Segment 3A"
  cross_layer: false           # primarily internal/ops-facing
```

#### 5.6.3 `s6_receipt_3A`

```yaml
- manifest_key: "mlr.3A.s6_receipt"
  name: "Segment 3A S6 validation receipt"
  subsegment: "3A"
  type: "dataset"
  category: "validation"
  path: "data/layer1/3A/s6_receipt/fingerprint={manifest_fingerprint}/s6_receipt.json"
  schema: "schemas.3A.yaml#/validation/s6_receipt_3A"
  version: "1.0.0"
  digest: "<sha256_hex>"       # SHA-256 of s6_receipt.json bytes
  dependencies:
    - "mlr.3A.s6_validation_report"
    - "mlr.3A.s6_issue_table"
  role: "Compact, hash-protected verdict on Segment 3A validation for this manifest; consumed by 3A.S7 and cross-segment validators"
  cross_layer: true
```

Binding requirements:

* Registry `manifest_key` values MUST be unique and clearly linked to S6.
* `path` and `schema` MUST match the dataset dictionary entries.
* `dependencies` MUST list all artefacts that the validation result is derived from.

---

### 5.7 No additional S6 datasets in this version

Under this contract version:

* S6 MUST NOT emit or register any datasets beyond:

  * `s6_validation_report_3A`,
  * `s6_issue_table_3A` (optional rows; dataset always present),
  * `s6_receipt_3A`.

Any future S6 datasets (e.g. additional per-check metrics tables) MUST:

1. Be introduced with new schema anchors in `schemas.3A.yaml`.
2. Be added as new `datasets` entries in `dataset_dictionary.layer1.3A.yaml`.
3. Have corresponding entries in `artefact_registry_3A.yaml`.

Only by going through this catalogue chain may S6’s output surface be extended.

---

## 6. Validation algorithm (RNG-free) **(Binding)**

This section defines the **exact behaviour** of 3A.S6.

S6:

* is **RNG-free** (no Philox, no other RNG),
* is **read-only** with respect to all S0–S5 and upstream artefacts, and
* MUST be **deterministic and idempotent** given the same inputs.

Its job is to:

1. Run a fixed set of checks over S0–S5 outputs + RNG logs.
2. Collect their results into:

   * `s6_validation_report_3A` (summary),
   * `s6_issue_table_3A` (detailed issues, optional rows),
   * `s6_receipt_3A` (compact verdict + digests).

Re-running S6 for the same `(parameter_hash, manifest_fingerprint, seed, run_id)` and unchanged artefacts MUST produce byte-identical outputs.

---

### 6.1 Phase overview

For a given run `(parameter_hash, manifest_fingerprint, seed, run_id)`, S6 executes the following phases:

1. **Initialisation & input resolution**

   * Load S0–S5 artefacts, RNG logs, and catalogue entries.
   * Verify basic preconditions (presence & schema validity).

2. **Check registry initialisation**

   * Instantiate a fixed set of check IDs and metadata (severity, description).

3. **Execute per-state checks (S0–S5, RNG)**

   * For each check, run its deterministic logic, accumulating:

     * `status ∈ {"PASS","WARN","FAIL"}`,
     * `affected_count`,
     * optional issue rows.

4. **Aggregate results & build report**

   * Compute `overall_status`, totals, metrics; construct `s6_validation_report_3A`.

5. **Build issue table (optional rows)**

   * Write or update `s6_issue_table_3A` from collected issue records.

6. **Build receipt**

   * Compute digests over `s6_validation_report_3A` (and issues) and populate `s6_receipt_3A`.

7. **Idempotent write & immutability checks**

   * For each of the three artefacts, enforce snapshot semantics and immutability.

All steps MUST be performed without RNG and without modifying any non-S6 datasets.

---

### 6.2 Phase 1 — Initialisation & input resolution

**Step 1 – Fix run identity**

S6 is invoked with:

* `parameter_hash`,
* `manifest_fingerprint`,
* `seed`,
* `run_id`.

S6 MUST:

* validate formats (`hex64` for hashes, `uint64` for seed),
* treat them as immutable inputs.

**Step 2 – Load S0 gate & sealed inputs**

* Resolve `s0_gate_receipt_3A` and `sealed_inputs_3A` for `manifest_fingerprint` via dictionary/registry.
* Read and validate both against their schemas.
* If either is missing or invalid → precondition failure, no further checks (this will be reflected as a failed check in §6.4).

**Step 3 – Load S1–S5 datasets**

Using the 3A dictionary & registry, resolve and read:

* `s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}`
* `s2_country_zone_priors@parameter_hash={parameter_hash}`
* `s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}`
* `s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}`
* `zone_alloc@seed={seed}/fingerprint={manifest_fingerprint}`
* `zone_alloc_universe_hash@fingerprint={manifest_fingerprint}`

For each:

* validate against its `schema_ref`.
* record basic metrics (row counts, distinct merchants/countries/zones) for later.

S6 MUST NOT abort immediately if a dataset fails validation; instead, it MUST:

* mark the relevant check(s) as `FAIL`,
* record issues as appropriate, and
* continue to collect as many diagnostics as possible, unless doing so requires the missing artefact.

**Step 4 – Load S1–S5 run-report rows**

From the Layer-1 segment-state run-report, retrieve rows for:

* S1 (`state="S1"`), S2 (`"S2"`), S3 (`"S3"`), S4 (`"S4"`), S5 (`"S5"`),
  matching this run’s identity (`parameter_hash`, `manifest_fingerprint`, `seed`, and `run_id` where applicable).

These rows are used by a dedicated check to ensure upstream self-reporting is consistent with structural checks.

**Step 5 – Load RNG logs for S3**

Using the RNG dataset definitions in `schemas.layer1.yaml` and the catalogue:

* Load `rng_event_zone_dirichlet` entries for:

  * `seed={seed}`, `parameter_hash={parameter_hash}`, `run_id={run_id}`,
  * `module="3A.S3"`, `substream_label="zone_dirichlet"`.

* Load the corresponding `rng_trace_log` aggregate row(s) for the same `(seed, parameter_hash, run_id, module, substream_label)`.

Validate their shape; missing/malformed logs will produce failed RNG checks.

**Step 6 – Load policy/priors artefacts if needed**

Using `sealed_inputs_3A` plus dictionary/registry:

* Locate and read:

  * the mixture policy artefact (`zone_mixture_policy_3A`),
  * the prior pack (`country_zone_alphas_3A`),
  * the floor/bump policy (`zone_floor_policy_3A`),
  * the day-effect policy (`day_effect_policy_v1`).

* Validate each against its schema and recompute SHA-256 digests (for checks that compare S5’s recorded digests vs actual).

---

### 6.3 Phase 2 — Check registry initialisation

S6 MUST initialise a **fixed registry** of checks before running any logic. Each check entry has:

* `check_id`: stable string (e.g. `"CHK_S0_GATE_SEALED_INPUTS"`).
* `default_severity`: `"ERROR"` or `"WARN"` (severity class of a `FAIL` status).
* `description`: human-readable summary.
* `status`: initial value `"PASS"`.
* `affected_count`: initial `0`.

At minimum, the registry MUST cover:

* **S0 level**:

  * `CHK_S0_GATE_SEALED_INPUTS` — S0 gate + sealed inputs consistency.

* **S1 level**:

  * `CHK_S1_DOMAIN_COUNTS` — S1 domain and `site_count` consistency (at least vs S1’s own contract; optionally vs 1A egress if available).

* **S2 level**:

  * `CHK_S2_PRIORS_ZONE_UNIVERSE` — priors cover zone universe; no extraneous tzids; α-sums positive.

* **S3 level**:

  * `CHK_S3_DOMAIN_ALIGNMENT` — S3 domain vs S1 escalation and S2 zone-universe.
  * `CHK_S3_SHARE_SUM` — share vectors per `(m,c)` sum ≈ 1.
  * `CHK_S3_RNG_ACCOUNTING` — RNG events vs trace log, envelope consistency.

* **S4 level**:

  * `CHK_S4_COUNT_CONSERVATION` — per-pair counts sum to S1 `site_count`.
  * `CHK_S4_DOMAIN_ALIGNMENT` — S4 domain vs S2/S3.

* **S5 level**:

  * `CHK_S5_ZONE_ALLOC_COUNTS` — `zone_alloc` vs S4 counts and S1 totals.
  * `CHK_S5_UNIVERSE_HASH_DIGESTS` — S5 component digests vs recomputed values.
  * `CHK_S5_UNIVERSE_HASH_COMBINED` — combined `routing_universe_hash` recomputes and matches `zone_alloc`.

* **Status coherence**:

  * `CHK_STATE_STATUS_CONSISTENCY` — S1–S5 run-report statuses vs structural checks (e.g. a state self-reporting PASS but failing a structural check).

The schema for `checks` in the report must be capable of housing all these IDs.

---

### 6.4 Phase 3 — Execute per-state checks

For each check in the registry, S6 runs deterministic logic using the preloaded artefacts. When a check finds issues:

* it sets `status` to `"FAIL"` or `"WARN"` (depending on check type and severity),
* increments `affected_count`, and
* optionally emits issue rows into an internal issue buffer.

**All checks MUST be independent of evaluation order** (i.e. their result does not depend on which check runs first).

Below is the high-level mandated behaviour for each check family.

#### 6.4.1 `CHK_S0_GATE_SEALED_INPUTS`

* Verify:

  * `upstream_gates.segment_1A/1B/2A.status == "PASS"`.
  * every external artefact needed by S1–S5 (priors, policies, references) appears in `sealed_inputs_3A` with a matching digest and schema validity.

* On any failure:

  * set `status="FAIL"`, `severity="ERROR"`,
  * `affected_count` = number of offending artefacts or segments,
  * emit issue rows per artefact/segment.

#### 6.4.2 `CHK_S1_DOMAIN_COUNTS`

* Check:

  * S1 schema correctness is already validated;
  * no duplicate `(merchant_id, legal_country_iso)` pairs;
  * `site_count(m,c) ≥ 1` for all rows;
  * escalated/non-escalated flags are well-formed.

* Optionally (if 1A egress is available and included in `sealed_inputs_3A`):

  * Cross-check distinct `(m,c)` domain and per-pair `site_count` vs 1A `outlet_catalogue`.

* Any mismatch or anomaly increments `affected_count`; serious invariants (e.g. domain mismatch vs 1A) set `status="FAIL"`.

#### 6.4.3 `CHK_S2_PRIORS_ZONE_UNIVERSE`

* Check:

  * S2’s `s2_country_zone_priors` covers all expected countries and zones;
  * per-country domain of `(country_iso, tzid)` is consistent with zone-universe references;
  * `alpha_effective(c,z) > 0` and `alpha_sum_country(c) > 0` for all relevant countries.

* Issues (e.g. missing zone, α_sum ≤ 0) increment `affected_count` and lead to `status="FAIL"`.

#### 6.4.4 `CHK_S3` checks

* **Domain alignment (`CHK_S3_DOMAIN_ALIGNMENT`)**:

  * Confirm S3 domain `D_S3` (projection of `s3_zone_shares` onto `(m,c)`) equals `D_esc`.
  * Confirm `Z_S3(m,c)` (tzid set from S3) equals `Z(c)` from S2 for each `(m,c)`.

* **Share sum (`CHK_S3_SHARE_SUM`)**:

  * For each `(m,c)` in S3:

    * compute `Σ_z share_drawn(m,c,z)`,
    * check `|Σ_z - 1| ≤ ε_share` where ε_share is a fixed tolerance (e.g. 1e-10).
  * Warnings if just outside tolerance, errors if grossly inconsistent.

* **RNG accounting (`CHK_S3_RNG_ACCOUNTING`)**:

  * For each escalated `(m,c)` in S3:

    * assert there is exactly one `rng_event_zone_dirichlet` event,
    * confirm event envelope (`blocks`, `draws`, counter deltas) matches the expectations.

  * Compare Σ`blocks` and Σ`draws` from events against the `rng_trace_log` aggregate.

* Any breaches set corresponding check `status` and populate issues.

#### 6.4.5 `CHK_S4_COUNT_CONSERVATION` & `CHK_S4_DOMAIN_ALIGNMENT`

* **Domain alignment:**

  * Confirm S4’s domain equals `D_esc × Z(c)` for each country.

* **Count conservation:**

  * For each `(m,c)`:

    * compute Σ_z `zone_site_count(m,c,z)`;
    * check it equals `zone_site_count_sum(m,c)` (S4) and `site_count(m,c)` (S1).

* Any mismatch increment `affected_count` and set `status="FAIL"`.

#### 6.4.6 `CHK_S5_ZONE_ALLOC_COUNTS` & `CHK_S5_UNIVERSE_HASH_*`

* **`CHK_S5_ZONE_ALLOC_COUNTS`**:

  * Confirm `zone_alloc` domain equals S4 domain;
  * confirm counts/redundant totals in `zone_alloc` match `s4_zone_counts` and S1, as per S5 spec.

* **`CHK_S5_UNIVERSE_HASH_DIGESTS`**:

  * Recompute component digests (`zone_alpha_digest`, `theta_digest`, `zone_floor_digest`, `day_effect_digest`, `zone_alloc_parquet_digest`) from the underlying artefacts.
  * Compare to values stored in `zone_alloc_universe_hash`.

* **`CHK_S5_UNIVERSE_HASH_COMBINED`**:

  * Recompute `routing_universe_hash` from the recomputed component digests.
  * Confirm it matches:

    * `zone_alloc_universe_hash.routing_universe_hash`, and
    * `zone_alloc.routing_universe_hash` on all rows.

Any inconsistency sets the corresponding check `status="FAIL"` and writes issue records.

#### 6.4.7 `CHK_STATE_STATUS_CONSISTENCY`

* For each state `S ∈ {S1, S2, S3, S4, S5}`:

  * Compare its run-report `status` with all S6-derived checks that pertain to that state.

  For example:

  * if S3’s run-report says `PASS` but a S3-related check (e.g. `CHK_S3_RNG_ACCOUNTING`) has `status="FAIL"`, this check flags a consistency issue.

* Depending on policy:

  * this may be `WARN` (state underreports issues), or
  * `FAIL` if you require states to self-report correctly.

---

### 6.5 Phase 4 — Aggregate results & build `s6_validation_report_3A`

After all checks have run:

**Step 7 – Derive per-check statuses & counts**

For each check in the registry:

* `status` is:

  * `"PASS"` if no issues,
  * `"WARN"` if only non-fatal anomalies were detected,
  * `"FAIL"` if any fatal anomaly was detected.

* `affected_count` is the number of primary entities affected (e.g. pairs, zones, artefacts) as recorded during check execution.

**Step 8 – Compute overall status**

S6 MUST derive `overall_status` deterministically from the check statuses, according to the project’s policy (e.g.):

* `overall_status = "FAIL"` if **any** check with `default_severity="ERROR"` has `status="FAIL"`.
* Otherwise `overall_status = "PASS"` (WARN-only checks tolerated).

The precise rule is part of the S6 contract; S7 and validation harnesses will use it implicitly via this field.

**Step 9 – Assemble the report object**

S6 constructs a JSON object for `s6_validation_report_3A` with:

* identity fields (`manifest_fingerprint`, `parameter_hash`),
* `overall_status`,
* counts of checks per status,
* `checks` array with entries from the registry,
* `metrics` object with aggregate metrics derived from S1–S5 and RNG logs.

This object MUST validate against `schemas.3A.yaml#/validation/s6_validation_report_3A`.

---

### 6.6 Phase 5 — Build issue table (`s6_issue_table_3A`)

During check execution, S6 MAY accumulate issue records in memory, each with:

* `issue_code`, `check_id`, `severity`,
* affected keys (`merchant_id`, `legal_country_iso`, `tzid`, or null),
* `message`, optional `details`.

**Step 10 – Assemble rows**

S6 builds the row set for `s6_issue_table_3A` (possibly empty) where each row conforms to `schemas.3A.yaml#/validation/s6_issue_table_3A` and has:

* `manifest_fingerprint`,
* the recorded issue attributes.

**Step 11 – Sort & validate**

Within each `fingerprint={manifest_fingerprint}` partition, rows MUST be sorted deterministically (e.g.):

1. `severity` descending (`ERROR`, `WARN`, `INFO`),
2. `issue_code` ascending,
3. `merchant_id`, `legal_country_iso`, `tzid`.

The sorted rows MUST validate against the schema.

---

### 6.7 Phase 6 — Build receipt (`s6_receipt_3A`)

**Step 12 – Compute report & issues digests**

S6 MUST:

* Serialise `s6_validation_report_3A` JSON in a deterministic manner (e.g. keys sorted, stable formatting).
* Compute `validation_report_digest = SHA-256(report_bytes)` as lowercase hex.

If an issue table exists:

* Enumerate its data files in ASCII-lexicographic order,
* Concatenate their bytes,
* Compute `issue_table_digest = SHA-256(concatenated_bytes)`.

If no issues exist:

* Either omit `issue_table_digest`, or set a sentinel (e.g. `"none"`) per schema.

**Step 13 – Assemble receipt object**

Construct `s6_receipt_3A` with:

* `manifest_fingerprint`, `parameter_hash`, `s6_version`,
* `overall_status`, `checks_passed_count`, `checks_failed_count`, `checks_warn_count`,
* `check_status_map` (mapping each check_id to its `status` and (optionally) `severity`),
* `validation_report_digest`,
* `issue_table_digest` (or sentinel),
* optional `created_at_utc` and `notes`.

Validate this object against `schemas.3A.yaml#/validation/s6_receipt_3A`.

---

### 6.8 Phase 7 — Idempotent write & immutability

For each S6 artefact (`s6_validation_report_3A`, `s6_issue_table_3A`, `s6_receipt_3A`):

**Step 14 – Check for existing data**

* Use the dataset dictionary/registry to resolve the expected path for `fingerprint={manifest_fingerprint}`.
* If no prior artefact exists, proceed to write.
* If a prior artefact exists:

  * Read and validate it.
  * Compare it (after normalisation/sorting) to the newly computed object/rows.

**Step 15 – Idempotence vs immutability**

* If existing and new artefacts are **identical**:

  * S6 MAY either leave them unchanged or overwrite with identical bytes; the observable content MUST remain unchanged.

* If they **differ in any way**:

  * S6 MUST NOT overwrite.
  * MUST report an immutability violation (via a dedicated error code in §9) and set `overall_status` to `"FAIL"`.

S6 MUST NOT attempt any partial write/update; all S6 outputs are written atomically per `manifest_fingerprint`.

---

### 6.9 RNG & side-effect discipline

Throughout all phases, S6 MUST:

* **Never consume RNG**:

  * No calls to Philox or any RNG API.
  * Any stochastic behaviour must be upstream in S3; S6 only analyses recorded RNG events/logs.

* **Never mutate upstream artefacts**:

  * Only write to its own outputs (`s6_validation_report_3A`, `s6_issue_table_3A`, `s6_receipt_3A`).
  * Must not create or modify any S0–S5 artefacts, RNG logs, or external priors/policies.

* **Be fully deterministic**:

  * Given fixed inputs and catalogue, all checks produce the same statuses, metrics and issue rows.
  * Two runs of S6 for the same `(parameter_hash, manifest_fingerprint, seed, run_id)` MUST result in byte-identical outputs (or a flagged immutability violation if existing outputs differ).

Under this algorithm, S6 provides a **single, well-defined validation verdict** and diagnostics for 3A, suitable for S7 to package into the final segment-level validation bundle and for cross-segment governance to reason about the correctness of Segment 3A.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S6’s outputs are identified**, how they are **partitioned**, what (if any) **ordering** guarantees exist, and what is allowed in terms of **merge / overwrite** behaviour.

All three S6 artefacts are **fingerprint-scoped** and are treated as immutable **snapshots**.

The artefacts are:

* `s6_validation_report_3A` — single JSON object per `manifest_fingerprint`.
* `s6_issue_table_3A` — 0 or more issue rows per `manifest_fingerprint`.
* `s6_receipt_3A` — single JSON receipt per `manifest_fingerprint`.

---

### 7.1 Common identity vocabulary

For all S6 outputs, the **core identity** is:

* `manifest_fingerprint` — the Layer-1 manifest hash (`hex64`), and
* (logically) the contract version(s) recorded in the artefact (`s6_version`, and optionally upstream versions).

S6 outputs do **not** depend on `seed` or `run_id` for partitioning; those exist in run-report/logs for correlation, not for S6 dataset identity.

For all three datasets:

* Partitioning MUST be exactly:

```yaml
["fingerprint"]
```

* The partition token `fingerprint={manifest_fingerprint}` MUST match the embedded `manifest_fingerprint` field in each JSON object and each issue row.

---

### 7.2 `s6_validation_report_3A`

#### 7.2.1 Identity & domain

* **Domain:** exactly **one** report object per `manifest_fingerprint`.

* **Path pattern (from dictionary):**

  ```text
  data/layer1/3A/s6_validation_report/fingerprint={manifest_fingerprint}/report.json
  ```

* Inside this directory there MUST be:

  * exactly one `report.json` file that conforms to `#/validation/s6_validation_report_3A`.

There is no notion of “multiple versions” of the report per fingerprint; if you need a different report version, that must be reflected via versioning and, if necessary, a new manifest.

#### 7.2.2 Partition & path↔embed equality

* Partition key: `fingerprint={manifest_fingerprint}`.
* The JSON object’s `manifest_fingerprint` field MUST equal the partition token’s value.
* Any mismatch is a schema/validation error and MUST be treated as such by S6 and any validator.

#### 7.2.3 Ordering semantics

* `s6_validation_report_3A` is a **single JSON object** — row ordering is not applicable.
* When serialised, the report MUST be written with a **deterministic key order** (e.g. lexicographically sorted keys) to ensure:

  * repeatable `validation_report_digest`,
  * idempotent re-runs.

This ordering is **not** semantically meaningful; it exists purely to stabilise digests and immutability checks.

#### 7.2.4 Merge & overwrite discipline

* Only one `report.json` is permitted per `manifest_fingerprint`.

* If a report already exists:

  * S6 MUST read and validate it.
  * S6 MUST compare the existing report (after normalising JSON) to the newly computed report.

* If they are **identical**:

  * S6 MAY leave the existing file untouched or overwrite with identical bytes; observable content MUST remain unchanged.

* If they **differ**:

  * S6 MUST NOT overwrite.
  * MUST raise an immutability error and mark the S6 run as FAIL.

No partial or incremental update semantics are permitted.

---

### 7.3 `s6_issue_table_3A`

#### 7.3.1 Identity & domain

* **Domain:** 0 or more issue rows per `manifest_fingerprint`.

* **Path pattern:**

  ```text
  data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet
  ```

* There MUST be exactly one dataset partition under `fingerprint={manifest_fingerprint}`, even if it contains zero rows.

Each row corresponds to one **issue instance** as defined in `#/validation/s6_issue_table_3A`.

#### 7.3.2 Partition & path↔embed equality

* Partition key: `fingerprint={manifest_fingerprint}`.
* Every row in `s6_issue_table_3A` MUST have:

  * `manifest_fingerprint` equal to the partition token.

Any mismatch is a schema/validation error.

#### 7.3.3 Ordering semantics

* Within a `fingerprint={manifest_fingerprint}` partition, rows MUST be written in a deterministic **writer sort**, e.g.:

  1. `severity` (ordered `ERROR` > `WARN` > `INFO`),
  2. `issue_code` ascending (lexicographic),
  3. `merchant_id` ascending (nulls first/last per schema conventions),
  4. `legal_country_iso` ascending (nulls last),
  5. `tzid` ascending (nulls last).

* Consumers MUST:

  * NOT infer any additional meaning from row order,
  * use the fields (`issue_code`, `severity`, etc.) for logic.

Ordering exists only for reproducibility and stable digests.

#### 7.3.4 Merge & overwrite discipline

* `s6_issue_table_3A` is a **snapshot** of issues for a given `manifest_fingerprint`.

* S6 MUST always treat the dataset as a complete issue list:

  * it MUST NOT append issues to an existing table,
  * MUST NOT delete or mutate individual rows in place.

* If an issues dataset already exists:

  * S6 MUST read and normalise it to the same schema & writer sort,
  * compare it row-for-row and field-for-field with the newly computed set.

* If identical:

  * S6 MAY reuse the existing file(s) or re-write identical bytes.

* If different:

  * S6 MUST NOT overwrite;
  * MUST treat as an immutability violation and fail the run.

---

### 7.4 `s6_receipt_3A`

#### 7.4.1 Identity & domain

* **Domain:** exactly one receipt object per `manifest_fingerprint`.

* **Path pattern:**

  ```text
  data/layer1/3A/s6_receipt/fingerprint={manifest_fingerprint}/s6_receipt.json
  ```

* The receipt MUST conform to `#/validation/s6_receipt_3A`.

#### 7.4.2 Partition & path↔embed equality

* Partition key: `fingerprint={manifest_fingerprint}`.
* The JSON object’s `manifest_fingerprint` MUST equal the partition token.
* `parameter_hash` in the receipt MUST equal the `parameter_hash` for the run; while not a partition key, this forms part of the logical identity of the validated universe.

Any mismatch is a schema/validation error.

#### 7.4.3 Ordering & digests

* As with the report, `s6_receipt_3A` is a single JSON object.
* When serialised, S6 MUST:

  * write JSON with deterministic key ordering,
  * ensure this deterministic representation is used to compute its own file digest (for registry) if needed.

Ordering is not semantically meaningful; it exists to ensure:

* stable `validation_report_digest` and `issue_table_digest` usage,
* idempotent re-runs.

#### 7.4.4 Merge & overwrite discipline

* Only one receipt file per `manifest_fingerprint` is allowed.

* On re-run:

  * S6 MUST read and normalise existing `s6_receipt_3A`,
  * compare it field-for-field with the newly computed receipt.

* If identical:

  * S6 MAY reuse or rewrite identical bytes.

* If different:

  * S6 MUST NOT overwrite;
  * MUST record an immutability violation and fail.

---

### 7.5 Cross-artifact consistency

Within a given `manifest_fingerprint`:

* `s6_receipt_3A.check_status_map` MUST correspond to `s6_validation_report_3A.checks[*].status`.
* `s6_receipt_3A.validation_report_digest` MUST equal the digest computed over the actual `report.json` content stored in `s6_validation_report_3A`.
* If `issue_table_digest` is present in the receipt, it MUST match a digest recomputed over `s6_issue_table_3A`’s data files.

These are **binding invariants**:

* If any of these cross-artifact relationships fail, S6 (or a higher-level validator) MUST treat the S6 outputs as **inconsistent** and not rely on them.

---

### 7.6 Cross-run semantics

S6 makes **no claims** about relationships between different `manifest_fingerprint` values:

* Each fingerprint defines a self-contained validation world;
* `s6_validation_report_3A`, `s6_issue_table_3A`, and `s6_receipt_3A` for different fingerprints MUST NOT be mixed and matched.

It is valid, however, for analytics tools to:

* aggregate metrics from **many** S6 reports (e.g. “how many manifests have `CHK_S3_RNG_ACCOUNTING` WARN vs FAIL?”),
* provided they interpret each report under its own contract version and do not attempt to override the verdict for any specific manifest.

---

Under these rules, all S6 outputs have:

* clear identity based on `manifest_fingerprint`,
* simple, well-defined partitioning,
* deterministic ordering where needed, and
* strict immutability, ensuring that validation results for a given manifest remain stable and auditable once published.

---

## 8. Acceptance criteria & segment-level status *(Binding)*

This section defines **when S6 is considered PASS** for a given `manifest_fingerprint`, and how S6 determines the **segment-level status** of 3A. It also fixes how this status must be reflected in `s6_validation_report_3A` and `s6_receipt_3A`, and what S7 and higher-level validators MUST do with it.

S6 is **not** allowed to redefine S1–S5 contracts; it only judges whether they have all been honoured, together, for this manifest.

---

### 8.1 Local acceptance criteria for S6

For a given `(parameter_hash, manifest_fingerprint, seed, run_id)`, 3A.S6 is considered **PASS** if and only if **all** the following hold:

1. **S6 successfully executes all mandatory checks**

   * All mandatory checks listed in the registry (e.g. `CHK_S0_GATE_SEALED_INPUTS`, `CHK_S1_DOMAIN_COUNTS`, `CHK_S2_PRIORS_ZONE_UNIVERSE`, `CHK_S3_DOMAIN_ALIGNMENT`, `CHK_S3_SHARE_SUM`, `CHK_S3_RNG_ACCOUNTING`, `CHK_S4_COUNT_CONSERVATION`, `CHK_S4_DOMAIN_ALIGNMENT`, `CHK_S5_ZONE_ALLOC_COUNTS`, `CHK_S5_UNIVERSE_HASH_DIGESTS`, `CHK_S5_UNIVERSE_HASH_COMBINED`, `CHK_STATE_STATUS_CONSISTENCY`) MUST be **executed** without internal S6 errors.

   * If S6 is unable to execute a check due to infrastructure issues (e.g. I/O failure) or missing artefacts, that check MUST be marked as `status="FAIL"` and its absence reflected in the report. S6 cannot declare overall PASS if any mandatory check was skipped or failed to run.

2. **All ERROR-severity checks are PASS**

   * For every check with `default_severity="ERROR"` in the registry, its final `status` MUST be `"PASS"`.
   * If any ERROR-severity check has `status="FAIL"`, S6 MUST set:

     * `s6_validation_report_3A.overall_status = "FAIL"`,
     * `s6_receipt_3A.overall_status = "FAIL"`,

     and the S6 run is considered FAIL.

3. **WARN-severity checks may fail without blocking PASS**

   * Checks designated with `default_severity="WARN"` MAY end up with `status="WARN"` or `status="FAIL"` without forcing overall failure, **if and only if** the project’s governance classifies them as non-fatal.

   * In this contract version, WARN-severity check failures are assumed **non-fatal** for `overall_status`. That is:

     * WARN failures increment `checks_warn_count`,
     * are recorded in `check_status_map` and `checks[*].status`,
     * may write issues to the issue table,

     but do **not** flip `overall_status` from `"PASS"` to `"FAIL"`.

   * Any change to that rule MUST be made via a change to this section and a new S6 contract version.

4. **Report & receipt are internally consistent**

   After running all checks, S6 MUST construct `s6_validation_report_3A` and `s6_receipt_3A`. For S6 to be PASS:

   * `s6_validation_report_3A` MUST:

     * validate against `#/validation/s6_validation_report_3A`,
     * have `overall_status` equal to the value derived from the checks (criteria 2 & 3),
     * have `checks_passed_count`, `checks_failed_count`, `checks_warn_count` equal to the counts derived from the `checks` array.

   * `s6_receipt_3A` MUST:

     * validate against `#/validation/s6_receipt_3A`,
     * have `overall_status` equal to `s6_validation_report_3A.overall_status`,
     * have `checks_passed_count`, `checks_failed_count`, `checks_warn_count` equal to those in the report,
     * have `check_status_map` that matches the `checks[*].status` values in the report for each `check_id`.

5. **Receipt digests match report & issue table**

   * Compute `validation_report_digest` over the canonical serialisation of `s6_validation_report_3A`.
   * Compute `issue_table_digest` over `s6_issue_table_3A` (or set the agreed sentinel if empty).

   S6 is PASS only if:

   * `s6_receipt_3A.validation_report_digest` equals the digest computed from the stored report.
   * If `s6_receipt_3A.issue_table_digest` is non-sentinel, it equals a digest computed from the stored issue table contents.
   * If the digest is sentinel (e.g. `"none"`), the issue table is either absent or empty, per the schema’s rules.

Any inconsistency between receipt and report/issue table MUST cause S6 to mark `overall_status="FAIL"` and treat the run as FAIL.

6. **Idempotence & immutability are preserved**

If S6 is re-run for the same `manifest_fingerprint` and the same upstream artefacts:

* If S6 outputs (`s6_validation_report_3A`, `s6_issue_table_3A`, `s6_receipt_3A`) already exist:

  * Their content (after normalisation) MUST equal the freshly computed artefacts.
  * If differences are found, S6 MUST NOT overwrite and MUST raise its immutability error (`E3A_S6_006_IMMUTABILITY_VIOLATION`), resulting in `overall_status="FAIL"`.

Only when criteria 1–6 hold may S6 consider its run **successful** and set `overall_status = "PASS"` for this `manifest_fingerprint`.

---

### 8.2 Segment-level status semantics

S6 assigns two levels of status:

1. **Per-check status** (`checks[*].status`, `check_status_map[check_id].status`):

   * `"PASS"` — check’s invariants hold.
   * `"WARN"` — minor anomalies detected that do not violate the segment’s formal contracts; warnings are surfaced but may be acceptable.
   * `"FAIL"` — invariants that MUST hold are violated.

2. **Segment-level status** (`overall_status`):

   * `overall_status = "PASS"`

     * All ERROR-severity checks are `"PASS"`.
     * WARN-severity checks may be `"PASS"` or `"WARN"`.
   * `overall_status = "FAIL"`

     * At least one ERROR-severity check has `status = "FAIL"`.
     * Or any of the internal consistency conditions (report/receipt schema, digests, immutability) fail.

This `overall_status` is the canonical Segment 3A verdict that S7 and cross-layer validators MUST use.

---

### 8.3 Obligations on S7 and cross-segment validators

S6 does **not** write the final validation bundle or `_passed.flag`; that is the work of S7. However, S6’s outputs impose strict obligations:

1. **S7 MUST honour S6’s `overall_status`.**

   * S7 MUST treat Segment 3A as **eligible for PASS** only if `s6_receipt_3A.overall_status == "PASS"` for the `manifest_fingerprint`.
   * If `overall_status != "PASS"` or `s6_receipt_3A` is missing/invalid, S7 MUST NOT issue a `_passed.flag` for 3A and MUST mark the 3A segment as FAIL in the bundle.

2. **S7 MUST verify S6’s digests.**

   * Before including `s6_validation_report_3A` and `s6_issue_table_3A` into the segment-level validation bundle, S7 MUST recompute:

     * `validation_report_digest` from the stored report,
     * `issue_table_digest` (if present) from the stored issue table,

   * and assert equality with the fields in `s6_receipt_3A`.

   * Any mismatch MUST cause S7 to treat the S6 outputs as invalid/untrusted and abort the PASS decision.

3. **Cross-segment validators MUST treat S6 as the 3A truth source.**

   * Any cross-segment governance (e.g. “only release segment bundles whose 3A S6 receipt is PASS”) MUST base its decisions on:

     * `s6_receipt_3A.overall_status`, and
     * optionally, the per-check statuses in `check_status_map`.

   * They MUST NOT attempt to recompute or reinterpret 3A’s status from S1–S5 alone; that is S6’s responsibility.

---

### 8.4 Relationship to upstream run-report statuses

S6 **does not** blindly trust S1–S5 `status` flags; it re-evaluates the structural invariants:

* A state may self-report `PASS` in the run-report but fail a structural check at S6.
* In such a case:

  * The relevant S6 check for that state MUST be `"FAIL"`.
  * `CHK_STATE_STATUS_CONSISTENCY` MUST highlight the discrepancy.
  * `overall_status` MUST be `"FAIL"` if that check is ERROR-severity.

Conversely, a state may self-report `FAIL`, and S6 may confirm structural failures or uncover additional context; S6’s job is to **finalise** the story for the segment, not simply rubber-stamp per-state self-reports.

---

### 8.5 Handling of S6 failures

If S6’s `overall_status = "FAIL"` for a `manifest_fingerprint`:

* `s6_validation_report_3A` and `s6_receipt_3A` MUST still be written (or confirmed), as they are the primary diagnostics.
* `s6_issue_table_3A` SHOULD contain as much detail as needed to diagnose issues (e.g. which merchants/countries/zones or artefacts failed).
* S7 MUST NOT mark 3A as PASS for this manifest.

Recovering from an S6 FAIL requires:

* identifying whether the failure is:

  * a true upstream contract violation (S1–S5 or priors/policies are wrong), or
  * an S6 implementation or catalogue bug,

* correcting the root cause, and then

* re-running the affected states and S6 to produce a new, coherent, PASS receipt for the manifest.

Under these rules, S6 yields a **single, authoritative segment-level status** for 3A and a detailed, machine-readable explanation of why that status is what it is.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only allowed failure classes** for `3A.S6 — Structural Validation & Segment Audit` and assigns each a **canonical error code**.

For each S6 run, we distinguish between:

* The **segment-level validation result** (`overall_status` in the report/receipt), and
* The **S6 state-level run status** (what appears in the segment-state run-report as S6’s `status` and `error_code`).

S6’s run status MUST be:

* `status="PASS", error_code=null` if:

  * S6 successfully executed all checks and produced consistent report/receipt artefacts, **even if** the segment-level `overall_status="FAIL"` (i.e. S6 has correctly detected 3A problems); or

* `status="FAIL", error_code ∈ {E3A_S6_001 … E3A_S6_007}` if:

  * S6 itself could not complete correctly (preconditions, catalogue issues, internal schema/immuatbility/IO errors).

In other words:

* **S6 run FAIL** means “the validation state itself is broken or cannot complete,”
* **Segment `overall_status="FAIL"`** means “3A is structurally invalid,” even though S6 run may be `PASS`.

---

### 9.1 Error taxonomy overview

S6’s **run-level failures** are partitioned into these classes:

1. **Preconditions not met / missing artefacts**
2. **Catalogue / schema layer malformed**
3. **Validation checks could not be completed** (logic/framework error, not “checks found failures”)
4. **Report or issue table schema violations**
5. **Receipt inconsistency with report/issue table**
6. **Immutability / idempotence violations**
7. **Infrastructure / I/O failures**

Each is mapped to a specific `E3A_S6_XXX_*` code.

Segment-level check failures (i.e. some check has `status="FAIL"`) are **not** S6 run failures; they are reflected inside the S6 report/receipt and yield `overall_status="FAIL"` but still `status="PASS", error_code=null` for S6 itself.

---

### 9.2 Preconditions not met

#### `E3A_S6_001_PRECONDITION_FAILED`

**Condition**

Raised when S6 cannot start or cannot even collect enough information to run checks due to missing or invalid preconditions, including:

* `s0_gate_receipt_3A` or `sealed_inputs_3A` missing or schema-invalid.
* One or more S1–S5 datasets (`s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`, `s4_zone_counts`, `zone_alloc`, `zone_alloc_universe_hash`) completely missing or failing basic schema validation.
* Required RNG logs for S3 (`rng_event_zone_dirichlet` and/or `rng_trace_log`) missing or failing schema validation.
* Critical external artefacts needed for checks (e.g. mixture policy, prior pack, floor policy, day-effect policy, zone-universe references) not listed in `sealed_inputs_3A` or failing basic schema validation.

**Required fields**

* `component` — one of:

  * `"S0_GATE"`, `"S0_SEALED_INPUTS"`,
  * `"S1_ESCALATION_QUEUE"`, `"S2_PRIORS"`, `"S3_ZONE_SHARES"`, `"S4_ZONE_COUNTS"`, `"S5_ZONE_ALLOC"`, `"S5_UNIVERSE_HASH"`,
  * `"RNG_EVENTS"`, `"RNG_TRACE"`,
  * `"MIXTURE_POLICY"`, `"PRIOR_PACK"`, `"FLOOR_POLICY"`, `"DAY_EFFECT_POLICY"`, `"ZONE_UNIVERSE_REF"`.

* `reason` — one of:

  * `"missing"`, `"schema_invalid"`, `"not_sealed"`.

* Optionally, for extra context:

  * `expected_schema_ref` — schema anchor S6 tried to validate against.
  * `manifest_fingerprint`, `parameter_hash` — to aid debugging.

**Retryability**

* **Non-retryable** for S6 alone.

  * Upstream or catalogue artefacts MUST be fixed/created, and S6 rerun with corrected preconditions.
  * Re-running S6 without fixing the precondition will reproduce the failure.

---

### 9.3 Catalogue & schema layer failures

#### `E3A_S6_002_CATALOGUE_MALFORMED`

**Condition**

Raised when S6 cannot trust the catalogue layer used to interpret artefacts, specifically:

* `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.2A.yaml` or `schemas.3A.yaml` missing or failing their own schema validation.
* `dataset_dictionary.layer1.3A.yaml` missing or malformed.
* `artefact_registry_3A.yaml` missing or malformed in ways that prevent S6 from resolving S1–S6 datasets or policy artefacts.

**Required fields**

* `catalogue_id` — identifier of the failing catalogue artefact, e.g.:

  * `"schemas.3A.yaml"`,
  * `"dataset_dictionary.layer1.3A"`,
  * `"artefact_registry_3A"`,
  * `"schemas.layer1.yaml"`.

* Optionally:

  * `reason ∈ {"missing","schema_invalid"}`.

**Retryability**

* **Non-retryable** until the catalogue is repaired or restored; S6 MUST not attempt to run on a broken catalogue.

---

### 9.4 Validation check execution failures

> Note: This is about S6 failing to *execute* checks, not checks finding 3A failures. If checks run and find issues, that is represented in the report/receipt (`overall_status`), with S6 `status="PASS"`.

#### `E3A_S6_003_CHECK_EXECUTION_FAILED`

**Condition**

Raised when S6 itself encounters an internal error while trying to run checks, including:

* Programming errors (e.g. unexpected nulls, unhandled cases) that prevent some checks from completing.
* Inability to iterate over or join S1–S5 datasets due to unexpected structural anomalies that are not purely schema-level (e.g. keys required by the joining logic are missing in practice, but schema still passes).
* Partial check execution (some checks ran, others not), resulting in an incomplete view of the segment.

**Required fields**

* `failed_checks[]` — non-empty list of `check_id`s that S6 could not execute or complete.
* `total_failed_checks` — integer count.
* `reason` — short label, e.g. `"internal_error"`, `"join_unexpected_null"`, `"unexpected_key_mismatch"`.

**Retryability**

* **Non-retryable** without S6 implementation/debugging changes.

  * If the cause is clearly due to corrupted input data, upstream states may also require correction before S6 can run successfully.
  * Re-running S6 without addressing the cause is likely to reproduce the failure.

---

### 9.5 Output schema & structural failures

These errors occur when S6 does its work but fails to produce outputs that conform to its own schema contracts.

#### `E3A_S6_004_REPORT_SCHEMA_INVALID`

**Condition**

Raised when `s6_validation_report_3A` or `s6_issue_table_3A` (if produced) fails validation against their schema anchors:

* `s6_validation_report_3A` fails `#/validation/s6_validation_report_3A` (e.g. missing required fields, wrong types, invalid `overall_status`, malformed `checks` array).
* OR `s6_issue_table_3A` rows fail `#/validation/s6_issue_table_3A` (e.g. missing `issue_code`, bad `severity`, invalid key fields).

**Required fields**

* `output_id ∈ {"s6_validation_report_3A","s6_issue_table_3A"}`.
* `violation_count` — number of schema validation errors found.
* Optionally:

  * `example_field` — one representative field path that failed (e.g. `"checks[2].status"`).

**Retryability**

* **Retryable only after S6 implementation/schema alignment is fixed.**

  * Indicates a bug in S6’s construction of the report or issue rows.

#### `E3A_S6_005_RECEIPT_INCONSISTENT`

**Condition**

Raised when `s6_receipt_3A` fails internal consistency checks:

* `s6_receipt_3A` does not validate against `#/validation/s6_receipt_3A`.
* OR `check_status_map` does not match the statuses in `s6_validation_report_3A.checks`.
* OR `validation_report_digest` does not equal the digest recomputed over `s6_validation_report_3A`.
* OR (if present) `issue_table_digest` differs from a digest recomputed over `s6_issue_table_3A`.

**Required fields**

* `reason ∈ {"schema_invalid","check_status_mismatch","report_digest_mismatch","issue_digest_mismatch"}`.
* `expected_value` and `observed_value` — optional fields for digests when mismatched.

**Retryability**

* **Retryable only after S6 implementation bug is fixed.**

  * If the root cause is an upstream modification of the report or issues after S6 originally wrote them, upstream write-discipline must be enforced.

---

### 9.6 Immutability / idempotence violations

#### `E3A_S6_006_IMMUTABILITY_VIOLATION`

**Condition**

Raised when S6 detects that existing S6 artefacts for this `manifest_fingerprint` are **not** identical to what S6 would produce now, indicating a conflict between previous and current validation results, including:

* Pre-existing `s6_validation_report_3A` that, after normalisation, differs from the newly computed report.
* Pre-existing `s6_issue_table_3A` whose row set differs from S6’s newly computed issue list.
* Pre-existing `s6_receipt_3A` whose fields differ from the newly computed receipt.

S6 MUST never silently overwrite these artefacts.

**Required fields**

* `artefact ∈ {"s6_validation_report_3A","s6_issue_table_3A","s6_receipt_3A","multiple"}`.
* `difference_kind ∈ {"field_value","row_set"}`.
* `difference_count` — number of differing fields or rows detected (may be approximate, but MUST be > 0).

**Retryability**

* **Non-retryable** until the conflict is resolved.

Operators MUST determine:

* whether previous S6 outputs are authoritative and current inputs are wrong, or
* whether the current environment is authoritative and previous S6 outputs must be archived/invalidated (which typically requires new manifest identity rather than overwriting).

S6 MUST never auto-resolve such conflicts.

---

### 9.7 Infrastructure / I/O failures

#### `E3A_S6_007_INFRASTRUCTURE_IO_ERROR`

**Condition**

Raised when S6 cannot complete its work due to environment-level issues that are not logical validation errors, including:

* Transient storage or network failures while reading S0–S5 datasets, RNG logs, policies, or writing S6 outputs.
* Permission errors (`EACCES`, `EPERM`) on relevant paths.
* Storage quota exhaustion or full disks.
* Connection resets/timeouts to remote catalogue or object storage.

This code MUST NOT be used for logical inconsistencies (e.g. domain mismatch, digest mismatch); those are captured as failed checks inside the report, not as S6 run-level errors.

**Required fields**

* `operation ∈ {"read","write","list","stat"}`.
* `path` — path or URI of the artefact involved (if known).
* `io_error_class` — short string classification, e.g.:

  * `"timeout"`,
  * `"permission_denied"`,
  * `"not_found"`,
  * `"quota_exceeded"`,
  * `"connection_reset"`.

**Retryability**

* **Potentially retryable**, depending on infrastructure policy.

Orchestrators MAY:

* automatically retry S6 when `E3A_S6_007_INFRASTRUCTURE_IO_ERROR` is raised,
* but a successful retry MUST still satisfy all requirements in §8 and ALL checks MUST run, or S6 cannot be considered a successful validation run.

---

### 9.8 Run-report mapping

For each S6 invocation, the Layer-1 segment-state run-report MUST record:

* `status = "PASS", error_code = null` when:

  * S6 completed all check execution and successfully wrote consistent `s6_validation_report_3A` and `s6_receipt_3A`, regardless of whether 3A’s segment-level `overall_status` is `"PASS"` or `"FAIL"`.

* `status = "FAIL", error_code ∈ {E3A_S6_001 … E3A_S6_007}` when:

  * S6 itself encountered precondition/catalogue/schema/immutability/IO errors and could not complete a valid validation run.

Downstream consumers (S7, cross-segment validators) MUST interpret:

* S6 run `status="PASS"` + `s6_receipt_3A.overall_status="PASS"` ⇒ **3A validated and green**.
* S6 run `status="PASS"` + `s6_receipt_3A.overall_status="FAIL"` ⇒ **3A has structural issues; S7 MUST NOT mark segment as PASS**, but S6 executed successfully.
* S6 run `status="FAIL"` ⇒ **S6 validation itself failed**; 3A’s status is not trustworthy for this manifest until S6 is fixed and re-run.

---

## 10. Observability & run-report integration *(Binding)*

This section defines what `3A.S6 — Structural Validation & Segment Audit` MUST emit for observability, and how it MUST integrate with the Layer-1 **segment-state run-report**.

S6 has two distinct notions of “status”:

* **S6 run status** — whether S6 itself executed successfully (for the run-report and logs).
* **3A segment-level status** — `overall_status ∈ {"PASS","FAIL"}` inside the S6 report/receipt (whether 3A is structurally sound for this manifest).

S6 MUST be explicit about both.

S6 MUST NOT log row-level business data (e.g. all `zone_alloc` rows); it only reports **validation-level summaries** and **hashes**.

---

### 10.1 Structured logging requirements

S6 MUST emit structured logs for three lifecycle events: **start**, **success**, and **failure**.

#### 10.1.1 State start log

Exactly one log event at the beginning of each S6 invocation.

**Required fields:**

* `layer = "layer1"`
* `segment = "3A"`
* `state = "S6"`
* `parameter_hash` — `hex64`
* `manifest_fingerprint` — `hex64`
* `seed` — `uint64`
* `run_id` — string / u128-encoded
* `attempt` — integer (e.g. `1` for first attempt, incremented by orchestration on retries)

**Optional fields:**

* `trace_id` — correlation ID from orchestration.

**Log level:** `INFO`.

#### 10.1.2 State success log

Exactly one log event **only if** the S6 run completes successfully as a state:

* i.e. all mandatory checks executed and S6 wrote consistent report/receipt artefacts,
* regardless of whether `overall_status` for 3A is `"PASS"` or `"FAIL"`.

**Required fields:**

* All fields from the start log.
* `status = "PASS"`                    (S6 run status)
* `error_code = null`                  (no S6 run-level error)

**Summary of checks:**

* `overall_status` — `"PASS"` or `"FAIL"` (segment-level status copied from `s6_receipt_3A.overall_status`).
* `checks_total` — total number of checks in the registry.
* `checks_passed_count` — number of checks with `status="PASS"`.
* `checks_failed_count` — number of checks with `status="FAIL"`.
* `checks_warn_count` — number of checks with `status="WARN"`.

**Key metrics (taken from `s6_validation_report_3A.metrics`):**

At minimum:

* `pairs_total`
* `pairs_escalated`
* `zones_total`
* `zone_rows_s3`
* `zone_rows_s4`
* `zone_rows_alloc`
* `rng_events_dirichlet_total`
* `rng_draws_dirichlet_total`

**Optional fields:**

* `elapsed_ms` — wall-clock duration measured by orchestration.
* Additional metrics (e.g. `issues_error_count`, `issues_warn_count`) MAY be included in a `metrics` sub-object.

**Log level:** `INFO`.

#### 10.1.3 State failure log

Exactly one log event **only if** the S6 state cannot complete, i.e. S6 run status is FAIL due to one of the error codes in §9.

**Required fields:**

* All fields from the start log.

* `status = "FAIL"`                    (S6 run status)

* `error_code` — one of `E3A_S6_001 … E3A_S6_007`.

* `error_class` — coarser category corresponding to the code, e.g.:

  * `"PRECONDITION"`,
  * `"CATALOGUE"`,
  * `"CHECK_EXECUTION"`,
  * `"REPORT_SCHEMA"`,
  * `"RECEIPT_INCONSISTENT"`,
  * `"IMMUTABILITY"`,
  * `"INFRASTRUCTURE"`.

* `error_details` — structured map including the required fields for that error code (see §9).

**Recommended additional fields (if available):**

* `checks_executed_count` — number of checks that were run before failure.
* `checks_failed_count` — number of checks that had already been marked `FAIL` (if any).

**Optional:**

* `elapsed_ms`.

**Log level:** `ERROR`.

All logs MUST be machine-parseable and MUST NOT include large dumps of per-entity data (no full `(merchant_id, country_iso, tzid)` lists).

---

### 10.2 Segment-state run-report entry

S6 MUST write exactly **one row** into the Layer-1 **segment-state run-report** (e.g. `run_report.layer1.segment_states`) per invocation.

This row describes the health of the S6 **state**, not necessarily the health of 3A as a segment (that is `overall_status` inside the S6 artefacts).

**Identity & context fields (required):**

* `layer = "layer1"`
* `segment = "3A"`
* `state = "S6"`
* `parameter_hash`
* `manifest_fingerprint`
* `seed`
* `run_id`
* `attempt`

**Outcome fields (required):**

* `status ∈ {"PASS","FAIL"}` — S6 run status (not segment-level status).
* `error_code` — `null` if `status="PASS"`, else one of `E3A_S6_001 … E3A_S6_007`.
* `error_class` — as in logs (coarse category for the error), `null` if `status="PASS"`.

**Failure localisation (optional but recommended):**

* `first_failure_phase` — enum, e.g.:

  ```text
  "PRECONDITION"
  | "CATALOGUE"
  | "CHECK_EXECUTION"
  | "REPORT_BUILD"
  | "ISSUE_TABLE_BUILD"
  | "RECEIPT_BUILD"
  | "IMMUTABILITY"
  | "INFRASTRUCTURE"
  ```

**Validation summary fields (required if `status="PASS"`; MAY be present on FAIL if available):**

* `overall_status` — `"PASS"` or `"FAIL"` copied from `s6_receipt_3A.overall_status` (segment-level status).

* `checks_total` — total checks from the registry.

* `checks_passed_count`

* `checks_failed_count`

* `checks_warn_count`

* `issues_error_count` — total number of issue rows with `severity="ERROR"` in `s6_issue_table_3A` (or aggregated in memory).

* `issues_warn_count` — number with `severity="WARN"`.

* `issues_info_count` — number with `severity="INFO"`.

**Catalogue & contract versioning (recommended):**

* `s6_version` — the S6 contract version.
* Optionally, versions for upstream state specs (e.g. `s1_version`, `s2_version`, etc.), if available and useful for governance.

**Timing & correlation:**

* `started_at_utc` — orchestrator-provided; MUST NOT influence S6 logic.
* `finished_at_utc`
* `elapsed_ms`
* `trace_id` — if used.

The run-report row MUST be consistent with:

* the S6 artefacts (report/receipt/issues), and
* the S6 logs (status, error_code), for this `(parameter_hash, manifest_fingerprint, seed, run_id)`.

---

### 10.3 Metrics & counters

S6 MUST expose a small set of metrics suitable for monitoring. The emission mechanism is implementation-specific; the semantics below are binding.

At minimum:

* `mlr_3a_s6_runs_total{status="PASS"|"FAIL"}`

  * Monotone counter; incremented once per S6 invocation (run-level status).

* `mlr_3a_s6_checks_failed_total`

  * Counter; total number of checks that ended with `status="FAIL"` across all S6 runs.

* `mlr_3a_s6_checks_warn_total`

  * Counter; number of checks that ended with `status="WARN"`.

* `mlr_3a_s6_issues_total{severity="ERROR"|"WARN"|"INFO"}`

  * Counters; cumulative count of issue rows emitted at each severity level.

* `mlr_3a_s6_duration_ms`

  * Histogram; distribution of S6 run durations (`elapsed_ms`).

Metric labels MUST NOT use raw `merchant_id`s, `tzid`s, or other high-cardinality keys. Labels SHOULD be limited to:

* `state="S6"`,
* `status` (for runs),
* `severity` (for issues),
* `error_class` (for failures),
* and optionally coarse buckets (e.g. `checks_total="low|medium|high"`).

---

### 10.4 Correlation & traceability

S6 outputs MUST be correlated with upstream states and accessible to higher-level validators:

1. **Cross-state correlation**

   * S6’s run-report row MUST be joinable with S0–S5 rows via:

     ```text
     (layer="layer1",
      segment="3A",
      parameter_hash,
      manifest_fingerprint,
      seed,
      run_id)
     ```

   * A shared `trace_id` (if provided) SHOULD be propagated across S0–S6 logs and run-report rows.

2. **Artefact navigation**

   From S6’s run-report row and/or `s6_receipt_3A`, a validator MUST be able to:

   * locate S6 outputs (`s6_validation_report_3A`, `s6_issue_table_3A`, `s6_receipt_3A`) via the dataset dictionary & registry;
   * locate all relevant upstream artefacts (S0–S5, RNG logs, priors, policies) using the `dependencies` information in registry entries and `sealed_inputs_3A`.

These relationships MUST be stable and documented; S6 must not rely on ad-hoc path knowledge.

---

### 10.5 Retention, access control & privacy

S6 artefacts contain **validation metadata**, not primary business data, but they still require disciplined handling:

1. **Retention**

   * S6 reports, issues and receipts MUST be retained for at least as long as:

     * the corresponding 3A segment outputs (S1–S5), and
     * the segment-level validation bundle that incorporates S6’s receipt remains in use.

   * Deleting S6 artefacts while their dependent 3A validation bundle is still considered authoritative is out of spec.

2. **Access control**

   * Access to S6 outputs SHOULD be limited to:

     * platform operators,
     * validation harnesses and monitoring/analytics tooling,
     * 3A owners and relevant feature teams.

   * Because S6 artefacts reference IDs (merchant_id / country / tzid, etc.) in the issue table, access MUST follow the same policies that apply to underlying 3A data.

3. **No excessive row-level leakage via logs**

   * Errors and warnings in logs MUST NOT include full dumps of affected rows; typically:

     * summarise counts,
     * include at most a small sample of IDs (possibly anonymised/hardened),
     * rely on the S6 issue table for exact lists.

---

### 10.6 Relationship to Layer-1 governance

Layer-1 may define additional, generic run-report and logging requirements. S6 MUST satisfy both:

* Layer-1 rules (for shape and mandatory fields), and
* this S6 contract (for S6-specific fields and semantics).

Where there is a conflict:

* Layer-1 schema/field requirements take precedence on shape,
* this section controls **how S6 uses those fields** to reflect:

  * S6 run status,
  * segment-level `overall_status`,
  * per-check counts, and
  * the link between S6 artefacts and upstream 3A state.

Under these rules, every S6 run is:

* **observable** (via structured logs),
* **summarised** (via a single run-report row), and
* **auditable** (via S6 artefacts plus upstream dependencies),

giving S7 and any cross-segment governance a clear, trustworthy view of Segment 3A’s structural health for each manifest.

---

## 11. Performance & scalability *(Informative)*

This section explains how 3A.S6 behaves at scale and what actually dominates its cost. The binding rules remain in §§1–10; this is an operational reading of them.

---

### 11.1 Workload shape

S6 is ultimately a **validation & audit pass** over:

* **3A internal artefacts:** S1–S5 datasets and their run-report rows
* **RNG logs:** S3’s Dirichlet events and trace logs
* **Policies/priors:** mixture, prior pack, floor policy, day-effect policy
* **Optional references:** ISO and zone-universe references

It does **not**:

* touch per-transaction data,
* resample RNG,
* run heavy numeric models.

The effective size drivers are:

* Number of merchant×country pairs (`|D|`, `|D_esc|`),
* Number of zones per country (`|Z(c)|`),
* Size of `s3_zone_shares`, `s4_zone_counts`, `zone_alloc`, and RNG event logs.

---

### 11.2 Complexity drivers

At a high level, S6’s checks fall into three categories:

1. **Schema & catalogue checks**

   * Simple existence + shape checks on S0–S5 artefacts and catalogue entries.
   * Cost is negligible: O(#artefacts), not data volume.

2. **Domain & conservation checks**

   * Joins and set-comparisons:

     * S1 vs S3 vs S4 vs S5 on `(m,c)` and `(m,c,z)`,
     * S2 vs S3/S4/S5 on `(c,z)`.

   * Per `(m,c)` conservation checks:

     * Σ_z `share_drawn` ≈ 1 (S3),
     * Σ_z `zone_site_count` = `site_count` (S4/S5).

   These are mostly **grouped scans** over:

   * `s1_escalation_queue` — `O(|D|)`
   * `s3_zone_shares` — `O(|D_esc| × avg|Z(c)|)`
   * `s4_zone_counts` & `zone_alloc` — also `O(|D_esc| × avg|Z(c)|)`

3. **RNG & digest checks**

   * RNG accounting:

     * Count Dirichlet events in RNG logs: `O(#events)` ≈ `O(|D_esc|)`,
     * Verify trace totals: `O(#events)`.

   * Universe hash/digest recomputation:

     * SHA-256 over relatively small policy/priors artefacts (config-sized),
     * SHA-256 streaming over `s2_country_zone_priors` and `zone_alloc` files: cost ∝ file size.

In practice, the dominant terms are linear in the **size of the 3A surfaces and RNG logs**:

[
\text{Total cost} \approx O\big(|s3_zone_shares| + |s4_zone_counts| + |zone_alloc| + \text{size of RNG logs}\big)
]

with a small constant factor.

---

### 11.3 Memory footprint

S6 can be implemented with a **streaming** mindset:

* Schema/catalogue checks require almost no memory.
* Domain equalities and conservation checks can be done via:

  * keyed aggregations (e.g. group-by over `(m,c)`), or
  * streaming joins partitioned by merchant/country.

Implementation guidelines:

* **Per-entity checks:**

  * For `(m,c)` checks, process in batches (e.g. per country, per merchant shard),
  * maintain only the necessary aggregates (counts, sums) for the current batch in memory.

* **RNG and universe hash checks:**

  * RNG events/trace can be processed in one or more streaming passes; do not materialise the entire log if large.
  * SHA-256 over `s2_country_zone_priors` and `zone_alloc` is naturally streaming (read in fixed-size chunks, update hash state).

Peak memory is thus dominated by:

* maximum batch size of `(m,c)` and `Z(c)` you choose to hold at once,
* ephemeral issue buffers (which can be flushed incrementally),
* any caches of small reference tables (e.g. country→zone sets).

No part of S6 requires keeping all 3A data in RAM simultaneously.

---

### 11.4 Parallelism

S6 is “pleasantly parallel” in several dimensions:

* **By check family:**

  * S1/S2 checks (domain & priors) can run independently of RNG/S3 checks.
  * S4/S5 conservation/universe-hash checks can run in parallel with S1/S2 checks, as long as dependencies are respected for final aggregation.

* **Within checks:**

  * Domain and conservation checks can be distributed across workers by key ranges:

    * partition `s3_zone_shares`, `s4_zone_counts`, `zone_alloc` by merchant or country,
    * each worker validates its partition and reports partial metrics;
    * a reducer aggregates counts and statuses.

* **Across manifests:**

  * Different `manifest_fingerprint` values are independent; S6 can be run concurrently across many manifests.

Caveats:

* Parallel execution must still maintain deterministic output:

  * The order of issue rows MUST be stable (e.g. sort at the end).
  * The report and receipt MUST be assembled in a deterministic way (e.g. sorted `check_id` order when computing digests).

As long as final sorting/aggregation is deterministic, parallelisation does not affect behaviour.

---

### 11.5 Runtime expectations

Relative to S1–S5:

* S6 is **lighter** than any state that:

  * scans 1A egress in full (S1),
  * constructs priors (S2) or performs Gamma/Dirichlet sampling (S3),
  * integerises counts (S4), or
  * hashes large egress surfaces on write (S5).

* S6’s cost is mostly:

  * reading and scanning S3/S4/S5 datasets once or twice,
  * scanning RNG logs,
  * hashing a few large-ish artefacts.

In a typical environment:

* If 3A surfaces are in the “millions of rows” range, S6’s runtime should be:

  * roughly linear in that row count,
  * usually modest compared to S1/S3’s heavy lifting.

The **runtime ratio** (S6 vs S3/S4/S5) will depend on:

* number of checks enabled,
* how aggressively S6 is parallelised,
* storage throughput for scanning large Parquet files and RNG logs.

---

### 11.6 Tuning levers (non-normative)

S6 can be tuned in several ways without changing semantics:

1. **Batching and streaming strategy**

   * Choose a batch size for `(m,c)` validation that balances memory vs network/disk I/O.
   * Use streaming aggregations instead of materialising entire join results.

2. **Selective RNG replay**

   * Full replay of Dirichlet draws is expensive; S6 may use a:

     * full accounting check (`CHK_S3_RNG_ACCOUNTING`) over all events, plus
     * sampled replay for share recomputation (if that’s in scope),

     as long as checks are deterministic and thresholds are clearly documented.

3. **Configurable check sets**

   * Some checks (e.g. very heavy cross-run metrics) might be optional or run in a lower frequency tier.
   * The S6 spec already encodes severity; additional fields could, in future, allow certain checks to be toggled in different environments (with appropriate versioning).

4. **Digest caching across manifests**

   * For policy/prior artefacts that are stable across many manifests with the same `parameter_hash`, S6 may be able to reuse known digests instead of re-hashing, provided:

     * those digests are stored in an authoritative place (e.g. S2/S5 metadata),
     * S6 still verifies that the underlying artefacts haven’t changed (e.g. via S0/sealed inputs or catalogue versioning).

This is subject to governance and may require additional bookkeeping; the spec cares only that digests are correct and consistent, not how you efficiently arrive at them.

---

### 11.7 Scalability summary

S6 is designed to scale **linearly** with:

* the size of 3A’s internal surfaces (S1–S5 outputs) and
* the size of RNG logs.

By:

* avoiding any dependence on raw 1A transaction volume,
* operating in a streaming, batch-aware fashion,
* and treating checks as embarrassingly parallel across keys/runs,

S6 remains a **manageable, predictable** validation step, even when the core engine is operating at “big data” scale.

---

## 12. Change control & compatibility *(Binding)*

This section defines **how the 3A.S6 contract is allowed to evolve** and what guarantees consumers (S7, validation harnesses, ops tooling) can rely on when:

* the schema or semantics of S6 outputs change,
* the set of checks or their severity changes, or
* upstream S0–S5 contracts evolve.

Given:

* `parameter_hash`,
* `manifest_fingerprint`,
* `seed`,
* `run_id`,
* and the **S6 version** recorded in `s6_receipt_3A`,

consumers must be able to interpret:

* what checks were run,
* how `overall_status` was derived,
* what the report/receipt/issue-table schemas mean.

S6 MUST evolve in a way that preserves **traceability and auditability** across versions.

---

### 12.1 Scope of change control

Change control for S6 covers:

1. The **shape and semantics** of S6 outputs:

   * `s6_validation_report_3A`
   * `s6_issue_table_3A`
   * `s6_receipt_3A`

2. The **check registry**:

   * set of check IDs and their meanings,
   * severity classification (`ERROR` vs `WARN`),
   * rules for deriving `overall_status` from per-check statuses.

3. The **error taxonomy** and run-report contract for S6 as a state:

   * `E3A_S6_*` error codes and their meaning.

It does **not** govern:

* internal implementation details (batching, parallelism, how the engine organises code), provided outputs and semantics remain unchanged;
* upstream S0–S5 behaviour, which is governed by their own change-control sections.

---

### 12.2 S6 contract versioning

S6 has a **contract version** that MUST be:

* recorded in `s6_receipt_3A.s6_version`, and
* tracked wherever S6 is declared in the catalogue (e.g. comments or version metadata in S6’s spec; the dataset version numbers for S6 outputs reflect their shapes but `s6_version` is the S6 state-level contract indicator).

S6 follows semantic versioning:

* `MAJOR.MINOR.PATCH`

#### PATCH (`x.y.z → x.y.(z+1)`)

* Bug fixes or doc clarifications that:

  * do **not** change the meaning of any existing fields in S6 outputs,
  * do **not** change the check set or `overall_status` derivation for any given inputs,
  * may tighten implementation correctness (e.g. fixing an internal bug so `check_status_map` matches the report), without changing valid results.

#### MINOR (`x.y.z → x.(y+1).0`)

* Backwards-compatible extensions, e.g.:

  * new optional fields in `s6_validation_report_3A.metrics` or `checks[*].notes`,
  * new optional columns or details in `s6_issue_table_3A` (e.g. adding a `rng_stream_id` column),
  * new **checks** that default to `status="PASS"` on existing data and do not change `overall_status` unless upstream data is actually wrong,
  * new WARN-only checks that only introduce `WARN` statuses and associated issues.

Existing consumers that ignore new fields and new checks remain correct.

#### MAJOR (`x.y.z → (x+1).0.0`)

* Breaking changes such as:

  * changing check semantics or severity in a way that can flip `overall_status` for existing manifests,
  * removing or renaming existing check IDs,
  * changing the structure/shape of `s6_validation_report_3A`, `s6_issue_table_3A`, or `s6_receipt_3A` in incompatible ways,
  * changing the rules for how per-check statuses are aggregated into `overall_status`.

Any of these require coordination with S7 and any validation tooling that consumes S6.

---

### 12.3 Backwards-compatible changes (MINOR/PATCH)

The following are considered **backwards-compatible** when done as described:

1. **Adding new checks**

   * Introducing new check IDs (e.g. `CHK_S2_ALPHA_DISTRIBUTION`) that:

     * default to `status="PASS"` for all current manifests, **or**
     * only surface `status="WARN"` for anomalies that do not violate existing contracts.

   * S6 MUST list new checks in `checks[]` and `check_status_map`, and MUST update `checks_*_count` appropriately.

   * Older consumers that ignore unknown `check_id`s remain safe as long as `overall_status` rule is unchanged.

2. **Adding optional report metrics**

   * Extending `metrics` in `s6_validation_report_3A` with additional fields, e.g.:

     * `issues_error_count`, `issues_warn_count`,
     * more detailed RNG statistics.

   * These metrics MUST be optional and MUST NOT change the semantics of existing metrics.

3. **Adding optional issue-table fields**

   * Adding new nullable columns to `s6_issue_table_3A`:

     * e.g. `rng_stream_id`, `zone_group_id`, `policy_id`.

   * They MUST be optional and not required for interpreting existing rows.

4. **Extending `check_status_map`**

   * Adding auxiliary attributes inside the map values, e.g.:

     * `severity` per check,
     * `last_run_at_utc` for the check.

   As long as `status` field semantics remain unchanged, this is MINOR-compatible.

5. **Extending error taxonomy**

   * Adding new `E3A_S6_***` error codes, provided:

     * existing codes keep their original meaning,
     * S6 run-report remains consistent.

6. **Strengthening validations without changing success cases**

   * Adding internal checks that only convert previously-invalid-but-unnoticed cases into explicit `FAIL` statuses for relevant checks, not for previously valid manifests.
   * Example: more precise RNG replay that only fails when S3 truly violated its contract.

Such changes can be MINOR or PATCH, depending on whether schema surfaces change.

---

### 12.4 Breaking changes (MAJOR)

The following changes are **breaking** and require a **MAJOR** bump to `s6_version` and coordinated updates in S7 and other consumers:

1. **Changing `overall_status` semantics**

   * Altering the rule that maps per-check statuses to `overall_status`, e.g.:

     * making WARN-severity check failures fatal when they previously were not,
     * treating some checks as optional that were previously required.

2. **Renaming or removing check IDs**

   * Removing an existing `check_id`, or changing the meaning of its name without clearly versioning it.
   * Reusing a check ID to mean something different from earlier versions (e.g. `CHK_S3_RNG_ACCOUNTING` now covers different invariants).

3. **Changing report, issue table or receipt shape in incompatible ways**

   * Removing required fields (e.g. `overall_status`, `check_status_map`) or changing their types.
   * Changing the nesting structure (e.g. flattening `checks` into a map, or changing `check_status_map` to a list).
   * Changing the `manifest_fingerprint` or `parameter_hash` semantics in any of the outputs.

4. **Changing the meaning of severity for existing checks**

   * For example, reclassifying a given check from `default_severity="WARN"` to `"ERROR"` such that existing manifests that were previously `overall_status="PASS"` now become `overall_status="FAIL"` without an S6 MAJOR bump.

5. **Relaxing immutability**

   * Allowing S6 to overwrite previously published reports/receipts for the same `manifest_fingerprint` with different content would be a significant governance change and MUST be accompanied by strong compatibility controls and versioning; the default is that this is NOT allowed.

Such changes are not prohibited, but MUST be carefully versioned and coordinated with:

* S7 (bundle builder & `_passed.flag` logic),
* cross-segment validation harnesses,
* any dashboards/monitors that interpret S6 outputs.

---

### 12.5 Interaction with upstream S0–S5 contracts

S6 depends on S0–S5 contracts; changes there can force S6 to evolve.

1. **Upstream breaking changes**

   * If any upstream contract changes **in a way that alters what S6 checks** (e.g. new S3 RNG family, different domain shapes in S4/S5), S6 MUST:

     * update its check logic to reflect the new invariants,
     * update the S6 spec accordingly, and
     * bump `s6_version` **at least** MINOR, MAJOR if results can change for existing manifests.

2. **Upstream optional extensions**

   * New upstream OPTIONAL fields or surfaces (e.g. extra lineage in S4, extra diagnostics in S5) may be:

     * ignored by S6, or
     * incorporated into new S6 checks, provided those checks do not break previous behaviour without a version bump.

3. **Parameter set evolution**

   * Changes in `parameter_hash` (priors/policies) do not require S6 contract changes by themselves:

     * S6 simply sees a different universe and re-runs the same checks.
   * If new priors/policies introduce **new invariants** that S6 must check (e.g. additional zone or day-effect constraints), this is handled by S6 adding new checks or extending existing ones, with appropriate versioning as in §12.3–12.4.

---

### 12.6 Catalogue evolution (schema/dictionary/registry) for S6

Any changes to:

* `schemas.3A.yaml#/validation/s6_*` anchors,
* S6 entries in `dataset_dictionary.layer1.3A.yaml`,
* S6 artefact entries in `artefact_registry_3A.yaml`,

must obey:

1. **Schema anchors**

   * Adding new optional fields (as per §12.3) is MINOR-compatible.
   * Removing or changing type/meaning of required fields is MAJOR and must be reflected in `s6_version`.

2. **Dataset dictionary entries**

   * Changing IDs, paths, or partitioning for S6 datasets is MAJOR.
   * Adding new S6 datasets (e.g. additional metrics tables) is OK if fully documented and given their own IDs, with clear dependencies.

3. **Artefact registry entries**

   * Adding new artefacts referencing S6 outputs (e.g. packaging S6 artefacts into a larger bundle) is compatible.
   * Changing the `manifest_key`, `path`, or `schema` declared for S6 artefacts is breaking and MUST be versioned and coordinated.

---

### 12.7 Deprecation strategy

When evolving S6:

1. **Introduce, then deprecate, then remove**

   * New behaviour or fields SHOULD be introduced in a way that coexists with old ones for at least one MINOR version.
   * Deprecation of fields/checks SHOULD be communicated in the S6 documentation and, where appropriate, via `notes` or a dedicated `deprecated` section in the report.

2. **Removal only with MAJOR bump**

   * Removing a check or field (or changing its meaning) MUST be accompanied by a MAJOR version bump and a clear migration path for consumers.

Historic S6 outputs MUST NOT be mutated to match new schemas; they remain valid under the version they were produced with.

---

### 12.8 Cross-version behaviour

S6 outputs of different versions may co-exist for different manifests in the same system.

Consumers MUST:

* always read `s6_version` from `s6_receipt_3A`,
* interpret report/issue/receipt according to that version’s contract,
* for cross-run analytics, either:

  * explicitly handle multiple versions, or
  * restrict themselves to the intersection of fields and semantics that are common across the versions they aggregate.

Under these rules, S6 can evolve:

* **safely** (new checks, metrics, diagnostics) without breaking existing workflows, and
* **explicitly** (when invariants or severity change, that is versioned and visible).

No consumer should ever have to guess what S6’s outputs mean for a given manifest; the combination of `s6_version`, schemas, and this change-control section defines that unambiguously.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix records the symbols and shorthand used in the 3A.S6 design. It has **no normative force**; it’s here so S0–S6, S7, and external validators all speak the same language.

---

### 13.1 Scalars, hashes & identifiers

* **`parameter_hash`**
  Layer-1 hash over the governed parameter set 𝓟 (priors, mixture, floor policy, day-effect policy, etc.). Fixed before any 3A state runs.

* **`manifest_fingerprint`**
  Layer-1 manifest hash for a run, including `parameter_hash` and sealed artefacts. S6 is fingerprint-scoped: all its outputs are keyed by this.

* **`seed`**
  Layer-1 global RNG seed (`uint64`). S6 itself is RNG-free but uses `seed` in run-report entries and for correlating with S3/S4/S5 runs.

* **`run_id`**
  Logical run identifier (string or u128-encoded). Used to tie S6 to a particular S3/S4/S5 execution.

* **`id64` / `iso2` / `iana_tzid`**
  Primitive types defined in `schemas.layer1.yaml` used for `merchant_id`, `legal_country_iso`, and `tzid`.

---

### 13.2 Sets & domains (reused from upstream)

For a given `{seed, manifest_fingerprint}` and `parameter_hash`:

* **`D` (S1 merchant×country domain)**

  [
  D = {(m,c)} = {(merchant_id, legal_country_iso)\ \text{present in } s1_escalation_queue}.
  ]

* **`D_{\text{esc}}` (escalated domain)**

  [
  D_{\text{esc}} = {(m,c) \in D \mid is_escalated(m,c) = true}.
  ]

* **`Z(c)` (zone universe per country)**

  For `country_iso = c`:

  [
  Z(c) = { tzid \mid (country_iso=c, tzid) \in s2_country_zone_priors }.
  ]

* **`D_{\text{S3}}` (S3 domain)**

  * Projection of `s3_zone_shares` onto `(m,c)`, plus `Z_S3(m,c)` per `(m,c)`:

  [
  Z_{\text{S3}}(m,c) = { tzid \mid (merchant_id=m, legal_country_iso=c, tzid)\in s3_zone_shares }.
  ]

* **`D_{\text{S4}}` / `D_{\text{alloc}}` (S4/S5 domain)**

  [
  D_{\text{S4}} = D_{\text{alloc}} = {(m,c,z) \mid (m,c) \in D_{\text{esc}},\ z \in Z(c)}.
  ]

S6’s domain checks essentially assert:

* `D_S3 = D_esc`,
* `Z_S3(m,c) = Z(c)`,
* `D_S4 = D_alloc = D_esc × Z(c)`.

---

### 13.3 Counts, priors & shares (referenced quantities)

For an escalated pair `(m,c)`:

* **`site_count(m,c)`**
  Total outlets per merchant×country from S1:

  [
  N(m,c) = site_count(m,c) \in \mathbb{N},\quad N(m,c) \ge 1.
  ]

* **`α_\text{effective}(c,z)`**
  Effective Dirichlet concentration from S2 for country `c` and zone `z`:

  [
  \alpha_\text{effective}(c,z) > 0.
  ]

* **`α_\text{sum\_country}(c)`**

  [
  \alpha_\text{sum_country}(c)
  = \sum_{z \in Z(c)} \alpha_\text{effective}(c,z) > 0.
  ]

* **`Θ(m,c,z)` (Dirichlet share)**

  From S3, the share for zone `z`:

  [
  \Theta(m,c,z) = share_drawn(m,c,z) \in [0,1],\quad
  \sum_{z \in Z(c)} \Theta(m,c,z) \approx 1.
  ]

* **`zone_site_count(m,c,z)`**

  From S4, integer outlets in zone `z`:

  [
  zone_site_count(m,c,z) \in \mathbb{N},\quad
  zone_site_count(m,c,z) \ge 0.
  ]

* **`zone_site_count_sum(m,c)`**

  Per-pair sum from S4/S5:

  [
  zone_site_count_sum(m,c)
  = \sum_{z \in Z(c)} zone_site_count(m,c,z)
  = site_count(m,c).
  ]

S6’s structural checks reassert these relationships.

---

### 13.4 RNG & logs (S3 validation)

* **`rng_event_zone_dirichlet`**
  RNG event family used by S3 for Dirichlet sampling; each event has:

  * `module = "3A.S3"`
  * `substream_label = "zone_dirichlet"`
  * `seed`, `parameter_hash`, `run_id`
  * `counter_before`, `counter_after`, `blocks`, `draws`
  * `merchant_id`, `country_iso`, `zone_count`, etc.

* **`rng_trace_log`**
  Layer-1 RNG aggregate where:

  * `blocks_total` and `draws_total` for the `(seed, parameter_hash, run_id, module="3A.S3", substream_label="zone_dirichlet")` key MUST equal Σ over Dirichlet events.

S6 checks these to ensure RNG accounting is intact (`CHK_S3_RNG_ACCOUNTING`).

---

### 13.5 S6 artefacts

* **`s6_validation_report_3A`**
  Single JSON object per `manifest_fingerprint` containing:

  * `overall_status`,
  * `checks[]` (per-check statuses),
  * `metrics` (aggregates).

* **`s6_issue_table_3A`**
  Zero or more rows per `manifest_fingerprint`, each describing an individual issue:

  * `issue_code`, `check_id`, `severity`, `message`,
  * optional keys (`merchant_id`, `legal_country_iso`, `tzid`).

* **`s6_receipt_3A`**
  Single JSON object per `manifest_fingerprint` containing:

  * `overall_status`,
  * `s6_version`,
  * `check_status_map[check_id] → status`,
  * `validation_report_digest`,
  * `issue_table_digest` (if any).

---

### 13.6 Check IDs (examples)

S6’s internal **check IDs** follow a `CHK_*` convention. Examples:

* **S0 checks:**

  * `CHK_S0_GATE_SEALED_INPUTS` — S0 gate, sealed inputs, upstream gate PASS.

* **S1 checks:**

  * `CHK_S1_DOMAIN_COUNTS` — S1 domain completeness & `site_count` coherence.

* **S2 checks:**

  * `CHK_S2_PRIORS_ZONE_UNIVERSE` — priors cover zone universe; no stray tzids; α-sums positive.

* **S3 checks:**

  * `CHK_S3_DOMAIN_ALIGNMENT` — S3 domain vs S1 escalation & S2 zones.
  * `CHK_S3_SHARE_SUM` — share vectors sum ≈ 1.
  * `CHK_S3_RNG_ACCOUNTING` — RNG events & trace consistency.

* **S4 checks:**

  * `CHK_S4_COUNT_CONSERVATION` — per-pair zone counts sum to `site_count`.
  * `CHK_S4_DOMAIN_ALIGNMENT` — S4 triples vs S1/S2/S3.

* **S5 checks:**

  * `CHK_S5_ZONE_ALLOC_COUNTS` — `zone_alloc` counts vs S4 & S1.
  * `CHK_S5_UNIVERSE_HASH_DIGESTS` — component digests vs recomputed values.
  * `CHK_S5_UNIVERSE_HASH_COMBINED` — `routing_universe_hash` recomputes and matches.

* **Global status check:**

  * `CHK_STATE_STATUS_CONSISTENCY` — S1–S5 self-reported run statuses vs S6 structural findings.

These IDs appear in:

* `s6_validation_report_3A.checks[*].check_id`,
* `s6_issue_table_3A.check_id`,
* `s6_receipt_3A.check_status_map`.

---

### 13.7 Error codes & status (S6 as a state)

* **`error_code`** (S6 run-level)
  One of:

  * `E3A_S6_001_PRECONDITION_FAILED`
  * `E3A_S6_002_CATALOGUE_MALFORMED`
  * `E3A_S6_003_CHECK_EXECUTION_FAILED`
  * `E3A_S6_004_REPORT_SCHEMA_INVALID`
  * `E3A_S6_005_RECEIPT_INCONSISTENT`
  * `E3A_S6_006_IMMUTABILITY_VIOLATION`
  * `E3A_S6_007_INFRASTRUCTURE_IO_ERROR`

* **`status` (S6 run status in run-report)**

  * `"PASS"` — S6 ran its checks and produced consistent outputs; segment may still be structurally `FAIL` at 3A level.
  * `"FAIL"` — S6 itself failed; its outputs cannot be trusted.

* **`overall_status` (segment-level status inside S6 artefacts)**

  * `"PASS"` — all ERROR-severity checks are PASS; WARNs only.
  * `"FAIL"` — at least one ERROR-severity check failed or S6’s own artefacts inconsistent.

* **`error_class`** (for S6 run failures)

  * `"PRECONDITION"`, `"CATALOGUE"`, `"CHECK_EXECUTION"`, `"REPORT_SCHEMA"`, `"RECEIPT_INCONSISTENT"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`.

---

These symbols are meant to align with upstream and downstream documentation so that when you read across:

> S0–S5 (data & policy) → S6 (validation & audit) → S7 (bundle & `_passed.flag`),

you see the same `D`, `D_esc`, `Z(c)`, `site_count`, `zone_site_count`, `routing_universe_hash`, `check_id`, and `overall_status` concepts used consistently and unambiguously.

---