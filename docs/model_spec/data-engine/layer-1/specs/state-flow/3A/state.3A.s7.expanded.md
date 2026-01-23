# State 3A·S7 — Segment Validation Bundle & PASS Flag

## 1. Purpose & scope *(Binding)*

State **3A.S7 — Segment Validation Bundle & PASS Flag** is the **final sealing and gating state** for Segment 3A. It does **not** generate or modify any business data, priors, shares, or counts; instead, it takes the outputs of S0–S6 and packages them into a **validation bundle** with a single authoritative **HashGate digest** and PASS flag. This is the artefact that other layers use to enforce the rule:

> **“No 3A PASS ⇒ No read of 3A surfaces.”**

Concretely, 3A.S7:

* **Assembles the 3A validation bundle for a manifest.**
  For a given `manifest_fingerprint`, S7 constructs a **3A validation bundle directory** (conceptually `validation_bundle_3A@manifest_fingerprint={manifest_fingerprint}`) that:

  * contains (by value or by canonical reference) the core 3A validation artefacts for this manifest, including at minimum:

    * S0: `s0_gate_receipt_3A`, `sealed_inputs_3A`,
    * S1: `s1_escalation_queue`,
    * S2: `s2_country_zone_priors`,
    * S3: `s3_zone_shares` (and, if required, RNG logs or their digests for the Dirichlet stream),
    * S4: `s4_zone_counts`,
    * S5: `zone_alloc`, `zone_alloc_universe_hash`,
    * S6: `s6_validation_report_3A`, `s6_issue_table_3A` (if present), `s6_receipt_3A`.
  * includes a single **bundle index** (`index.json`) that lists each member, its canonical path, its `schema_ref`, its SHA-256 digest, and its logical role (gate, prior, share, count, egress, validation report, etc.).

  S7 does not re-run checks at this stage; it assumes S6 has already decided whether 3A is structurally valid and instead focuses on **bundling and indexing** the evidence.

* **Computes a composite HashGate digest over the bundle.**
  Using the `index.json` as the canonical manifest of bundle contents, S7:

  * enumerates all listed artefacts in a deterministic order (e.g. by logical ID or canonical path),
  * concatenates their SHA-256 digests (as ASCII hex) in that order,
  * computes a single composite digest:
    [
    bundle_sha256_hex = \mathrm{SHA256}\big(\text{concat(digests in index order)}\big),
    ]
  * treats this `bundle_sha256_hex` as the **3A segment HashGate digest** for this manifest.

  This digest is the only value that appears in the `_passed.flag` file and is what orchestrator/consumers verify when deciding whether 3A is safe to read.

* **Emits the segment-level PASS flag for 3A.**
  S7 writes a small, manifest_fingerprint-scoped `_passed.flag` file colocated with the validation bundle (e.g. inside `validation_bundle_3A@manifest_fingerprint={manifest_fingerprint}`), whose content is:

  ```text
  sha256_hex = <bundle_sha256_hex>
  ```

  in exactly the same format as other Layer-1 HashGate flags (1A, 2A, etc.).

  This flag is the **only authoritative PASS surface** for Segment 3A. By contract, any downstream orchestrator or consumer that wants to read 3A surfaces for this `manifest_fingerprint` MUST:

  * confirm that `validation_bundle_3A` exists,
  * verify `_passed.flag` against the bundle index and member digests,
  * regard absence or mismatch as “3A not validated; no read allowed”.

* **Binds the S6 verdict into the segment-level PASS decision.**
  S7 does not re-evaluate structural correctness; it takes S6’s verdict as a prerequisite:

  * S7 MUST only proceed to bundle construction and PASS-flag emission if:

    * the S6 state run for this manifest has `status="PASS"` in the segment-state run-report, **and**
    * `s6_receipt_3A.overall_status == "PASS"` for this `manifest_fingerprint`.
  * If S6 indicates `overall_status="FAIL"` or S6 itself failed as a state, S7 MUST NOT issue (or must not treat as valid) `_passed.flag` for this manifest.

  In effect, S6 says “3A is structurally green/red”, and S7 says “if green, here is the sealed bundle + digest”.

* **Remains RNG-free and read-only with respect to business data.**
  3A.S7:

  * MUST NOT consume any Philox stream or other RNG.
  * MUST NOT modify any S0–S6 artefacts, nor any upstream data, priors, policies or logs.
  * Only:

    * reads existing artefacts (S0–S6, RNG logs, policies) to compute per-member digests or confirm membership, and
    * writes the validation bundle index and `_passed.flag`.

  Given the same `parameter_hash`, `manifest_fingerprint`, `seed`, `run_id`, and an unchanged artefact set, re-running S7 MUST produce the **same bundle layout**, the **same `index.json`**, and the **same `_passed.flag` bytes**. Any divergence under identical inputs MUST be treated as an immutability error.

Out of scope for 3A.S7:

* S7 does **not**:

  * change escalation decisions, priors, shares, counts, or egress;
  * re-run validation logic or RNG replay (S6 is the last place that happens);
  * generate any new business surfaces inside 3A.

* S7 does **not**:

  * perform cross-segment governance beyond exposing a canonical HashGate digest and PASS flag that other layers (2B, higher-level bundles) can depend on.

Within these boundaries, S7’s sole purpose is to **seal Segment 3A**: to take a manifest that S6 has judged as structurally valid, and emit exactly one immutable validation bundle and PASS flag that make 3A’s state auditable and enforceable under the same “no PASS → no read” discipline used elsewhere in Layer 1.

---

### Contract Card (S7) - inputs/outputs/authorities

**Inputs (authoritative; see Section 2 for full list):**
* `s0_gate_receipt_3A` - scope: FINGERPRINT_SCOPED; source: 3A.S0
* `sealed_inputs_3A` - scope: FINGERPRINT_SCOPED; source: 3A.S0
* `s1_escalation_queue` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3A.S1
* `s2_country_zone_priors` - scope: PARAMETER_SCOPED; scope_keys: [parameter_hash]; source: 3A.S2
* `s3_zone_shares` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3A.S3
* `s4_zone_counts` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3A.S4
* `zone_alloc` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3A.S5
* `zone_alloc_universe_hash` - scope: FINGERPRINT_SCOPED; source: 3A.S5
* `s6_validation_report_3A` - scope: FINGERPRINT_SCOPED; source: 3A.S6
* `s6_issue_table_3A` - scope: FINGERPRINT_SCOPED; source: 3A.S6 (optional)
* `s6_receipt_3A` - scope: FINGERPRINT_SCOPED; source: 3A.S6
* `rng_event_zone_dirichlet` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; source: 3A.S3 (optional)
* `rng_audit_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; source: 3A.S3 (optional)
* `rng_trace_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; source: 3A.S3 (optional)

**Authority / ordering:**
* S7 is the sole authority for the 3A validation bundle index and PASS flag.

**Outputs:**
* `validation_bundle_3A` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `validation_passed_flag_3A` - scope: FINGERPRINT_SCOPED; gate emitted: final consumer gate

**Sealing / identity:**
* All bundled artefacts must match the S0-sealed inventory for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or failed S6 verdict -> abort; no outputs published.

## 2. Preconditions & gated inputs *(Binding)*

This section defines **what MUST already hold** before `3A.S7 — Segment Validation Bundle & PASS Flag` can execute, and which artefacts it is allowed to touch. Anything outside these conditions is **out of scope** for S7.

S7 is the final **pack & seal** step. It is **RNG-free** and **read-only** with respect to all S0–S6 and upstream data: if the world is not already “green” at S6, S7 must refuse to issue a PASS flag.

---

### 2.1 Invocation & identity preconditions

S7 is invoked in the context of a 3A run identified by:

* `parameter_hash` — layer-wide governed parameter set ID (priors, policies, etc.),
* `manifest_fingerprint` — manifest ID,
* `seed` — Layer-1 run seed (S7 itself does not use RNG),
* `run_id` — identifier for this execution of the 3A pipeline.

S7 MUST treat these values as **inputs only**:

* It MUST NOT alter or re-derive `parameter_hash`, `manifest_fingerprint`, `seed`, or `run_id`.
* All bundle paths and artefacts S7 creates are scoped to `manifest_fingerprint={manifest_fingerprint}`; `seed` and `run_id` are used for correlation in logs/layer1/3A/run-report only.

---

### 2.2 Hard precondition: S6 says 3A is PASS

S7 MUST treat S6 as the **only authority** on segment-level structural health for 3A. Before doing anything, S7 MUST verify that:

1. **S6 ran successfully as a state**

   * In the segment-state run-report, the row for `state="S6"` and this `(parameter_hash, manifest_fingerprint, seed, run_id)` MUST have:

     * `status = "PASS"`,
     * `error_code = null`.

   If the S6 state run itself failed (`status="FAIL"`), S7 MUST NOT proceed and MUST treat this as a precondition failure.

2. **S6’s segment verdict is PASS**

   * The dataset `s6_receipt_3A@manifest_fingerprint={manifest_fingerprint}` MUST exist.
   * It MUST validate against `schemas.3A.yaml#/validation/s6_receipt_3A`.
   * It MUST have `overall_status = "PASS"`.

   If `overall_status != "PASS"` or the receipt is missing/invalid, S7 MUST NOT assemble a validation bundle or write `_passed.flag`. For this manifest, 3A is **not** eligible to be marked as PASS.

S7 MUST NOT “second-guess” S6’s verdict by re-running checks. If S6 says FAIL (or S6 itself failed), S7’s job is to refuse to seal, not to repair.

---

### 2.3 Gated inputs from S0 (gate & sealed inputs)

Although S7 does not perform new validations, it still operates under the S0 gate:

1. **S0 gate & upstream segment PASS**

   For `manifest_fingerprint`, S7 MUST:

   * Resolve and read `s0_gate_receipt_3A@manifest_fingerprint={manifest_fingerprint}`.
   * Validate it against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`.
   * Confirm that `upstream_gates.segment_1A/1B/2A.status == "PASS"`.

   If these conditions are not met, S7 MUST NOT seal 3A: upstream segments are not known-good for this manifest.

2. **Sealed external artefacts**

   * Resolve and read `sealed_inputs_3A@manifest_fingerprint={manifest_fingerprint}`.
   * Validate it against `schemas.3A.yaml#/validation/sealed_inputs_3A`.

   S7 relies on S0 + `sealed_inputs_3A` to know which **external** policy/prior artefacts were in play (mixture policy, priors, floors, day-effect, references). S7 itself does not need to re-read their content (S5/S6 already did), but:

   * a bundle membership plan that references any external artefact MUST only use artefacts listed in `sealed_inputs_3A`,
   * if a required external artefact for the bundle is **not** present in `sealed_inputs_3A`, S7 MUST treat that as a precondition failure.

---

### 2.4 Required 3A internal artefacts for bundling

S7’s job is to bundle the evidence that S6 validated. To do that, S7 MUST ensure that **all required 3A artefacts to be included in the bundle actually exist and are schema-valid**.

At minimum, for `manifest_fingerprint`, S7 MUST be able to resolve and read:

* **S0:**

  * `s0_gate_receipt_3A`,
  * `sealed_inputs_3A`.

* **S1:**

  * `s1_escalation_queue@seed={seed}/manifest_fingerprint={manifest_fingerprint}`.

* **S2:**

  * `s2_country_zone_priors@parameter_hash={parameter_hash}`.

* **S3:**

  * `s3_zone_shares@seed={seed}/manifest_fingerprint={manifest_fingerprint}`.
  * Optionally, S3 RNG events/trace log digests, if the bundle includes RNG evidence or their digests (depending on the agreed bundle content).

* **S4:**

  * `s4_zone_counts@seed={seed}/manifest_fingerprint={manifest_fingerprint}`.

* **S5:**

  * `zone_alloc@seed={seed}/manifest_fingerprint={manifest_fingerprint}`,
  * `zone_alloc_universe_hash@manifest_fingerprint={manifest_fingerprint}`.

* **S6:**

  * `s6_validation_report_3A@manifest_fingerprint={manifest_fingerprint}`,
  * `s6_issue_table_3A@manifest_fingerprint={manifest_fingerprint}` (may be empty but MUST exist as a dataset),
  * `s6_receipt_3A@manifest_fingerprint={manifest_fingerprint}`.

For each of these, S7 MUST:

* resolve the path and `schema_ref` via `dataset_dictionary.layer1.3A.yaml` and `artefact_registry_3A.yaml`,
* confirm existence,
* confirm schema validity (using the relevant anchor).

If any required artefact:

* cannot be resolved,
* is missing from storage, or
* fails schema validation,

S7 MUST treat the preconditions as unsatisfied and MUST NOT assemble a validation bundle or write `_passed.flag`. Instead it MUST surface the failure as an S7 run-level error.

> **Note:** The exact list of artefacts in the bundle is defined in §6/§5 for S7. Whatever that list is, S7’s preconditions include the existence and validity of **every** member.

---

### 2.5 Catalogue inputs (bundle membership & HashGate rules)

To know what goes in the bundle and how hashing works, S7 MUST rely on the catalogue:

* **3A dataset dictionary & registry**

  * `dataset_dictionary.layer1.3A.yaml` — to know IDs, paths and roles for S0–S6 outputs and S7’s own bundle artefacts.
  * `artefact_registry_3A.yaml` — to know which artefacts are considered 3A validation members and their `manifest_key`s.

* **Layer-1 HashGate rules**

  * From `schemas.layer1.yaml` and any shared validation spec, S7 MUST know:

    * the schema of a validation bundle index (`validation_bundle_index_3A`),
    * the format of `_passed.flag` files (`sha256_hex = …`),
    * the canonical ordering & concatenation rules for computing composite digests.

These catalogue artefacts are **inputs** to S7’s algorithm and MUST be present and schema-valid. S7 MUST NOT hard-code bundle membership or digest rules beyond what is recorded in the catalogue and its own contract.

---

### 2.6 RNG & side-effect constraints

For clarity:

* **No RNG**

  * S7 MUST NOT consume any RNG; it does not create or modify business or validation content, it only hashes existing artefacts and writes bundle metadata and the flag.

* **No mutation of S0–S6 or upstream artefacts**

  * S7 MUST NOT modify:

    * any S0–S6 datasets or JSONs,
    * any RNG logs,
    * any priors/policies or references.

  * The **only** new artefacts S7 is allowed to create are:

    * the `validation_bundle_3A` directory (including `index.json`), and
    * `_passed.flag` for this `manifest_fingerprint`.

If these preconditions are not satisfied — in particular, if S6 has not produced a PASS receipt or required bundle members are missing/invalid — S7’s responsibility is simply to **refuse to seal** 3A for this manifest, not to attempt to repair or bypass the upstream pipeline.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes **exactly what 3A.S7 is allowed to use**, what each input is **authoritative for**, and where S7’s own authority **starts and stops**.

S7 is **purely a pack-and-seal state**:

* It does **not** re-validate S0–S6.
* It does **not** modify any upstream artefact.
* It only builds:

  * the 3A validation bundle (`validation_bundle_3A` + `index.json`), and
  * the `_passed.flag` HashGate flag,

based on **already-agreed contracts** and **sealed artefacts**.

---

### 3.1 Catalogue & HashGate law (shape & behaviour authority)

S7 MUST treat the **Layer-1 catalogue** and **HashGate specification** as the **sole authorities** for:

* how bundles and flags are shaped, and
* how composite digests are computed.

Inputs in this class:

1. **Schema packs**

   * `schemas.layer1.yaml`
   * `schemas.ingress.layer1.yaml`
   * `schemas.2A.yaml`
   * `schemas.3A.yaml`

   S7 MAY:

   * use these to validate the shape of all artefacts included in the bundle (`index.json`, S0–S6 datasets, `_passed.flag`),
   * resolve `schema_ref` anchors for data-plane (S0–S5) and validation artefacts (S6, S7).

   S7 MUST NOT:

   * redefine or override any Layer-1 primitive types,
   * change HashGate or validation index semantics,
   * invent schema anchors outside these packs.

2. **Dataset dictionaries & artefact registries**

   * `dataset_dictionary.layer1.3A.yaml` (and 1A/2A as needed)
   * `artefact_registry_3A.yaml` (and upstream registries as referenced)

   S7 MAY:

   * use the dictionaries to resolve dataset IDs → paths, partitioning, and `schema_ref`,
   * use registry entries to:

     * know which artefacts belong to Segment 3A,
     * identify which artefacts are designated as validation members,
     * determine paths and roles for S7 outputs (`validation_bundle_3A`, `_passed.flag`).

   S7 MUST NOT:

   * hard-code paths or membership beyond what the catalogue and S7 contract prescribe,
   * edit dictionary or registry content; any evolution is governed at the catalogue level.

3. **HashGate / bundle specification**

   From `schemas.layer1.yaml` (and any dedicated HashGate spec), S7 MUST take as binding:

   * the **format** and **semantics** of `_passed.flag` files (e.g. `sha256_hex = <digest>`),

   * the **schema** of the bundle index (`validation_bundle_index_3A`):

     * required per-member fields (logical ID, path, `schema_ref`, `sha256_hex`, role, etc.),
     * any bundle-level metadata (e.g. `manifest_fingerprint`, `parameter_hash`, `s6_receipt_digest`),

   * the **canonical ordering and concatenation rule** for computing composite digests from individual `sha256_hex` values.

S7 MUST NOT invent its own bundle or flag formats; it only instantiates what the catalogue & HashGate spec declare.

---

### 3.2 S6 artefacts & run-report (segment-verdict authority)

S7 treats S6 as the **only authority** on Segment 3A’s structural status for a manifest.

Inputs in this class:

1. **S6 artefacts**

   * `s6_validation_report_3A@manifest_fingerprint={manifest_fingerprint}`
   * `s6_issue_table_3A@manifest_fingerprint={manifest_fingerprint}` (dataset exists even if 0 rows)
   * `s6_receipt_3A@manifest_fingerprint={manifest_fingerprint}`

   S7 MUST:

   * validate all three against their schema anchors,
   * treat `s6_receipt_3A.overall_status` as the **canonical PASS/FAIL decision** for Segment 3A.

   S7 MAY:

   * use `s6_validation_report_3A` and `s6_issue_table_3A` to:

     * populate bundle metadata (e.g. `s6_receipt_digest`, check counts),
     * include them as bundle entries.

   S7 MUST NOT:

   * change `overall_status` or any field in S6 artefacts,
   * re-run or reinterpret S6’s checks; if S6 says FAIL, S7 MUST refuse to seal (no `_passed.flag`).

2. **S6 run-report row**

   From the segment-state run-report for `state="S6"` and this `(parameter_hash, manifest_fingerprint, seed, run_id)`, S7 MUST:

   * verify `status="PASS"` and `error_code=null` (S6 executed successfully as a state),
   * treat any S6 run-level failure (`status="FAIL"`) as a hard precondition failure: S7 MUST NOT build a bundle.

S7’s entire gating logic rests on “S6 PASS & `overall_status="PASS"` ⇒ S7 may seal; else S7 must not.”

---

### 3.3 Core 3A artefacts S7 bundles (data & config authority)

S7’s bundle is a **packaging** of S0–S6 evidence. Each upstream artefact has its own contract; S7 does not modify or reinterpret them.

S7 MAY read the following **internal 3A artefacts** solely to:

* confirm existence & schema validity, and
* compute **per-artefact digests** for inclusion in `index.json`.

S7 MUST NOT alter their contents.

1. **S0 (gate & sealed inputs)**

   * `s0_gate_receipt_3A` — authority on upstream gates, catalogue versions, sealed policy/prior set.
   * `sealed_inputs_3A` — authority on which external artefacts are in scope.

2. **S1 (escalation & domain)**

   * `s1_escalation_queue` — authority on `D`, `D_esc`, and `site_count(m,c)`.

   S7 bundles this as “what S1 said the domain and totals are”; it does not check or adjust those values.

3. **S2 (priors & zone universe)**

   * `s2_country_zone_priors` — authority on zone universe per country and prior lineage.

   S7 includes this as the sealed basis for `zone_alpha_digest` (computed by S5/S6).

4. **S3 (shares & RNG)**

   * `s3_zone_shares` — authority on Dirichlet share vectors.
   * RNG logs (or their digests) for S3’s Dirichlet family — authority on RNG usage.

   Whether S3 RNG logs themselves are bundled or included via digests is determined by the bundle spec; in either case, S7 does not replay or modify them, it just indexes and hashes.

5. **S4 (integer counts)**

   * `s4_zone_counts` — authority on integer zone counts per `(m,c,z)`.

6. **S5 (egress & universe hash)**

   * `zone_alloc` — cross-layer egress for zone counts; authority on `(m,c,z) → count` as exposed outside 3A.
   * `zone_alloc_universe_hash` — authority on the component digests and `routing_universe_hash` binding priors/policies and `zone_alloc`.

7. **S6 (validation)**

   * `s6_validation_report_3A`
   * `s6_issue_table_3A`
   * `s6_receipt_3A`

   These are bundled as the **final validation evidence** for 3A.

For all of the above, S7:

* MAY compute SHA-256 digests (per their own canonical rules) to write into the bundle index.
* MUST NOT edit or “fix” any of their content, even if S7 discovers inconsistencies; those must have been caught by S6.

---

### 3.4 External artefacts referenced in the bundle (sealed authority)

Depending on the final bundle spec, some **external** artefacts may be:

* either included directly in the bundle,
* or referenced via digest only.

Typical examples:

* **Priors & policies**:

  * `zone_mixture_policy_3A`,
  * `country_zone_alphas_3A`,
  * `zone_floor_policy_3A`,
  * `day_effect_policy_v1`.

* **Structural references**:

  * `iso3166_canonical_2024`,
  * zone-universe references (e.g. `country_tz_universe`, `tz_world_2025a`).

S7 MUST treat these artefacts as **sealed and immutable**, based on:

* their presence in `sealed_inputs_3A` and `s0_gate_receipt_3A.sealed_policy_set`, and
* their `sha256_hex` values as already established by S0/S5/S6.

S7 MAY:

* read these artefacts to recompute digests for the bundle index, if digests are not already stored in a canonical upstream place (e.g. `zone_alloc_universe_hash`, S6 report).

S7 MUST NOT:

* treat them as editable configuration,
* introduce any new semantics over these artefacts (e.g. new invariants about their content); that remains in S2/S5/S6.

---

### 3.5 S7’s own authority: bundle index & `_passed.flag`

S7’s **exclusive authority surface** in Segment 3A is:

1. **The 3A validation bundle index** (`index.json`)

   * lists the exact set of artefacts that comprise “3A validation evidence” for a manifest,
   * records per-artefact digests, roles and schema_refs,
   * is used to compute the composite `bundle_sha256_hex`.

   S7 owns:

   * which artefacts (S0–S6, S3 RNG logs or their digests, etc.) are included in the 3A validation bundle (as specified in S7’s bundle membership rules),
   * the construction and serialisation of `index.json` under `validation_bundle_3A`.

2. **The 3A `_passed.flag`**

   * contains:

     ```text
     sha256_hex = <bundle_sha256_hex>
     ```

     where `bundle_sha256_hex` is derived solely from the artefacts listed in `index.json` and their individual digests.

   * is the **only segment-level PASS flag** for 3A.

   S7 owns:

   * when to write this flag (only when S6 says PASS and all bundle invariants hold),
   * ensuring that it is consistent with the current bundle and index.

S7 MUST:

* ensure that any 3A consumer that follows HashGate rules can reconstruct the bundle digest from `index.json` and verify `_passed.flag`.
* treat a mismatch between recomputed digest and `_passed.flag` as an S7 failure, not a condition to be silently fixed.

---

### 3.6 Explicit “MUST NOT” list for S7

To keep boundaries sharp, S7 is explicitly forbidden from:

* **Re-validating or changing upstream contracts**

  * MUST NOT re-run S6’s checks or override S6’s `overall_status`.
  * MUST NOT attempt to “fix” inconsistencies in S1–S5; if S6 allowed this state to be PASS, S7 trusts that or fails fast if artefacts are missing/malformed.

* **Mutating S0–S6 or upstream artefacts**

  * MUST NOT modify any S0–S6 dataset, RNG log, or policy/prior/reference file.
  * MUST NOT change `routing_universe_hash`, any per-artefact digest already recorded by S5/S6, or any business content.

* **Consuming RNG**

  * MUST NOT call any RNG API (Philox or otherwise).
  * The composite digest MUST be a deterministic function of the artefacts and their digests, with no randomness.

* **Reading unsealed external artefacts**

  * MUST NOT read or include any external artefact that is not in `sealed_inputs_3A` for this `manifest_fingerprint`.
  * MUST NOT use environment variables or local files as implicit bundle members or digest sources.

Within these boundaries, S7’s job is narrow but critical: it takes a 3A world that S6 has declared “PASS” and transforms that into a **single, immutable validation bundle + HashGate flag**, without changing any upstream semantics or data.

---

## 4. Outputs (bundle & PASS flag) & identity **(Binding)**

3A.S7 produces exactly **two** new artefacts for each validated manifest:

1. A **3A validation bundle** (`validation_bundle_3A`) — a manifest_fingerprint-scoped directory with an index.
2. A **segment PASS flag** (`_passed.flag`) — a small text file that encodes the composite HashGate digest over that bundle.

S7 MUST NOT produce any business datasets or change any S0–S6 artefacts.

All statements below are **normative** unless explicitly marked informative.

---

### 4.1 Overview of S7 outputs

For each `manifest_fingerprint = F`, S7 MAY produce a bundle+flag pair **only** if S6 has already:

* run successfully as a state, and
* declared `overall_status="PASS"` for Segment 3A at F.

If those preconditions are met, S7 MUST produce at most one instance of:

* `validation_bundle_3A@manifest_fingerprint={F}` — a directory whose contents are fully described by an `index.json` file.
* `_passed.flag@manifest_fingerprint={F}` — a text file whose value is derived solely from `index.json` and the digests of bundle members.

No other S7 outputs are in scope in this contract version.

---

### 4.2 `validation_bundle_3A` — bundle structure & identity

#### 4.2.1 Identity & partitioning

**Identity**

* Logical bundle ID: `validation_bundle_3A`.
* Scope: **one bundle per `manifest_fingerprint`** at most.

**Partitioning & path (conceptual)**

* Partitioning: `["manifest_fingerprint"]`.
* Path pattern (subject to dictionary in §5):

  ```text
  data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/
  ```

Binding rules:

* For a given `manifest_fingerprint = F`, there MUST be at most one directory:

  ```text
  data/layer1/3A/validation/manifest_fingerprint=F/
  ```

representing the 3A validation bundle for that manifest.

* All metadata inside the bundle that embeds `manifest_fingerprint` (especially `index.json`) MUST match the `F` from the path.

S7 MUST NOT create multiple different bundles for the same `manifest_fingerprint`.

#### 4.2.2 Required contents of the bundle

The directory `validation_bundle_3A@manifest_fingerprint={F}` MUST contain, at minimum:

1. **An index file:**

   * `index.json` — a JSON file that:

     * conforms to the bundle index schema (`validation_bundle_index_3A` in §5), and
     * lists every artefact that is considered part of the bundle, with its per-artefact SHA-256 digest.

2. **Entries for the following 3A artefacts** (by value or by canonical reference as defined in §5):

   At minimum, the bundle MUST include entries for:

   * **S0**

     * `s0_gate_receipt_3A`
     * `sealed_inputs_3A`

   * **S1**

     * `s1_escalation_queue`

   * **S2**

     * `s2_country_zone_priors`

   * **S3**

     * `s3_zone_shares`
     * plus at least a reference to S3’s RNG evidence (either full logs or a separately sealed RNG digest artefact, as defined in the catalogue).

   * **S4**

     * `s4_zone_counts`

   * **S5**

     * `zone_alloc`
     * `zone_alloc_universe_hash`

   * **S6**

     * `s6_validation_report_3A`
     * `s6_issue_table_3A` (even if empty)
     * `s6_receipt_3A`

Each of these MUST appear as a distinct entry in `index.json`, with:

* a `logical_id` (dataset/artefact ID or manifest_key),
* a concrete `path` (the path to the artefact’s root or file),
* a `schema_ref` anchor describing its shape,
* a `sha256_hex` digest over its canonical representation, and
* a `role` (e.g. `"gate"`, `"sealed_inputs"`, `"domain"`, `"priors"`, `"shares"`, `"counts"`, `"egress"`, `"universe_hash"`, `"validation_report"`, `"validation_receipt"`).

Additional artefacts (e.g. explicit RNG digest artefacts) MAY be included in the bundle in later contract versions, but the above subset is **required** for this version.

S7 MUST NOT include artefacts in the bundle that are unknown to the catalogue (no ad-hoc files).

#### 4.2.3 `index.json` identity & canonical form

The file `index.json` inside the bundle directory:

* MUST be the sole authoritative manifest of bundle membership and digest state.

* MUST contain:

  * bundle-level metadata:

    * `manifest_fingerprint`,
    * `parameter_hash`,
    * optionally some or all of:

      * `s6_receipt_digest`,
      * `s0_version`…`s6_version`, etc.

  * a list/array of **member entries**, each with:

    * `logical_id`,
    * `path`,
    * `schema_ref`,
    * `sha256_hex` (64-char lowercase hex),
    * `role`,
    * optionally: `size_bytes`, `notes`.

* MUST validate against the `validation_bundle_index_3A` schema in `schemas.layer1.yaml` / `schemas.3A.yaml`.

**Canonical ordering**

The `index.json` serialisation MUST be deterministic. At minimum:

* the member list MUST be sorted by a canonical key (e.g. ASCII-lex order of `logical_id`, or `path` if specified in §5), and
* JSON keys in objects MUST be serialised in a stable (e.g. lexicographic) order when computing digests (see HashGate rules).

This ensures that:

* the composite bundle digest computed from `index.json` is stable, and
* re-running S7 does not produce digests that drift over time.

#### 4.2.4 Relationship between `index.json` and members

S7 MUST ensure that:

* For each entry in `index.json`, the `path` resolves (via the catalogue) to an existing, schema-valid artefact.
* For each member artefact, `sha256_hex` equals the SHA-256 digest of the artefact’s canonical representation:

  * For JSON files (e.g. S0 gate, S6 report, S6 receipt, universe hash), the digest MUST be computed over a deterministic serialisation (sorted keys, stable whitespace).
  * For Parquet datasets (e.g. S1, S2, S3, S4, `zone_alloc`, issue table), the digest MUST be computed over:

    * all data files under the dataset’s root path,
    * read in ASCII-lex path order,
    * concatenated raw bytes for the digest.

If any mismatch is found between `index.json` and the actual artefacts, S7 MUST treat this as a bundle integrity error and MUST NOT produce or confirm `_passed.flag`.

---

### 4.3 `_passed.flag` — PASS flag & identity

#### 4.3.1 Identity & partitioning

**Identity**

* Logical artefact ID: `validation_passed_flag_3A`.
* Scope: one flag per `manifest_fingerprint` at most.

**Partitioning & path**

* Partitioning: `["manifest_fingerprint"]`.
* Path pattern (conceptual):

  ```text
  data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
  ```

Per `manifest_fingerprint = F`:

* There MUST be at most one `_passed.flag` file at this path.
* If present, it is the **only** segment-level PASS surface for 3A at F.

#### 4.3.2 Content & canonical format

The flag file:

* MUST be a plain text file encoded in UTF-8.
* MUST follow the standard HashGate format:

  ```text
  sha256_hex = <bundle_sha256_hex>
  ```

where:

* `bundle_sha256_hex` is a 64-character lowercase hex string,
* representing the SHA-256 digest computed over the canonical concatenation of member `sha256_hex` values in `index.json` (in the prescribed order).

No other content (no additional lines, no comments) is allowed in `_passed.flag` in this contract version.

S7 MUST ensure:

* `bundle_sha256_hex` is computed from `index.json` and its entries exactly as defined in §6 (algorithm section).
* Any consumer that recomputes `bundle_sha256_hex` from `index.json` will obtain the same value as recorded in `_passed.flag`.

---

### 4.4 Consumers & “no PASS → no read” obligations

The combination of `validation_bundle_3A` and `_passed.flag` becomes the **Segment-3A HashGate** for this `manifest_fingerprint`.

**Obligations for downstream consumers — binding:**

* Any component that wants to treat 3A surfaces for manifest `F` as **trusted** (e.g. read `zone_alloc` or other 3A egress) MUST:

  1. Locate `validation_bundle_3A@manifest_fingerprint=F` and `index.json`.
  2. Locate `_passed.flag@manifest_fingerprint=F`.
  3. Validate both against their schemas (`validation_bundle_index_3A`, `passed_flag_3A`).
  4. Recompute `bundle_sha256_hex` from `index.json` and confirm it matches the value in `_passed.flag`.

* If any of these steps fail (bundle or flag missing, schema invalid, digest mismatch), consumers MUST treat 3A as **not validated** for `F` and MUST NOT read or consume 3A surfaces for that manifest.

This mirrors the “no PASS → no read” rule used for upstream segments (1A, 2A, etc.), but applied at the 3A segment level.

**Examples:**

* A cross-segment validation harness must not inspect 3A priors, counts, or egress for `F` unless `_passed.flag` is present and verified.
* A production 2B run that depends on `zone_alloc` MUST verify `_passed.flag` for the same `manifest_fingerprint` and fail fast if it is missing or does not verify.

---

### 4.5 Non-outputs (explicit exclusions)

For clarity, 3A.S7 does **not** introduce:

* any new data-plane datasets (no new priors, shares, counts, or egress),
* any new RNG logs or receipts,
* any new validation artefacts beyond:

  * `validation_bundle_3A` (and its `index.json`),
  * `_passed.flag`.

All other 3A artefacts (S0–S6) are produced by their respective states; S7 only references and hashes them.

Within this section’s constraints:

* `validation_bundle_3A` and `_passed.flag` are the **only artefacts** produced by S7, and
* they together form the **immutable, manifest_fingerprint-scoped authority surface** for “3A is validated and safe to be read for this manifest.”

---

## 5. Dataset shapes, schema anchors & catalogue links **(Binding)**

This section fixes **where S7’s outputs live in the authority chain**, and **how** they are shaped:

* JSON-Schema anchors for:

  * the 3A validation bundle index (`index.json`),
  * the `_passed.flag` file.
* Dataset dictionary entries for:

  * `validation_bundle_3A` (the bundle / index),
  * `_passed.flag` (the flag).
* Artefact registry entries tying them into the manifest.

S7 MUST NOT introduce any other datasets in this contract version.

---

### 5.1 Schema packs & anchors

S7 uses the existing Layer-1 and 3A schema packs:

* `schemas.layer1.yaml` — defines generic HashGate and validation structures.
* `schemas.3A.yaml` — may provide 3A-specific aliases/types that reuse Layer-1 definitions.

For S7, the following anchors MUST exist:

1. **Bundle index schema**

   * Primary anchor:

     ```text
     schemas.layer1.yaml#/validation/validation_bundle_index_3A
     ```

   * Optionally re-aliased in `schemas.3A.yaml` if convenient, but Layer-1 is the source of truth.

2. **PASS flag schema**

   * Primary anchor:

     ```text
     schemas.layer1.yaml#/validation/passed_flag_3A
     ```

These anchors define the **logical shape** of the artefacts; the on-disk representation of `_passed.flag` is a single-line text file that parses into the `passed_flag_3A` logical object.

---

### 5.2 Schema: `validation_bundle_index_3A` (index.json)

`schemas.layer1.yaml#/validation/validation_bundle_index_3A` MUST describe a top-level object with:

* **Type:** `object`

* **Required properties:**

  * `manifest_fingerprint`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `parameter_hash`

    * `$ref: "schemas.layer1.yaml#/$defs/hex64"`

  * `s6_receipt_digest`

    * `type: "string"`
    * SHA-256 (hex) digest of the canonical serialisation of `s6_receipt_3A`.

  * `members`

    * `type: "array"`
    * `items`:

      * `type: "object"`
      * `required: ["logical_id", "path", "schema_ref", "sha256_hex", "role"]`
      * `properties`:

        * `logical_id` — `type: "string"`

          * usually the dataset/artefact ID or manifest_key (e.g. `"mlr.3A.s1_escalation_queue"`).
        * `path` — `type: "string"`

          * concrete path to the artefact, e.g. `data/layer1/3A/s1_escalation_queue/seed=.../manifest_fingerprint=.../`.
        * `schema_ref` — `type: "string"`

          * schema anchor, e.g. `schemas.3A.yaml#/plan/s1_escalation_queue`.
        * `sha256_hex` — `type: "string"`

          * pattern `^[0-9a-f]{64}$`.
        * `role` — `type: "string"`

          * short semantic label (e.g. `"gate"`, `"sealed_inputs"`, `"domain"`, `"priors"`, `"shares"`, `"counts"`, `"egress"`, `"universe_hash"`, `"validation_report"`, `"validation_receipt"`).
        * `size_bytes` — `type: "integer"`, `minimum: 0` (optional).
        * `notes` — `type: "string"` (optional).
      * `additionalProperties: false`

* **Optional bundle metadata:**

  A `metadata` object MAY be present:

  * `metadata`

    * `type: "object"`
    * `properties` (examples):

      * `s0_version` … `s6_version` — `type: "string"`
      * `created_at_utc` — `$ref: "schemas.layer1.yaml#/$defs/rfc3339_micros"`
    * `additionalProperties: true` (future-proof).

* **Additional properties (top-level):**

  * `additionalProperties: false`

    * new top-level fields MUST go through schema/contract evolution per §12.

`manifest_fingerprint` in the index MUST equal the `{manifest_fingerprint}` token in the bundle path.

---

### 5.3 Schema: `passed_flag_3A` (`_passed.flag`)

`schemas.layer1.yaml#/validation/passed_flag_3A` defines the **logical shape** of the PASS flag.

* **Logical form:** object with a single property:

  * `sha256_hex`

    * `type: "string"`
    * pattern `^[0-9a-f]{64}$`.

* **On-disk representation:** single-line UTF-8 text, exactly:

  ```text
  sha256_hex = <64-lowercase-hex>
  ```

where `<64-lowercase-hex>` is the value of `sha256_hex` in the logical object.

When S7 reads or writes `_passed.flag` it MUST:

* parse/serialise according to this format, and
* treat the parsed `sha256_hex` value as governed by `passed_flag_3A`.

---

### 5.4 Dataset dictionary entries (`dataset_dictionary.layer1.3A.yaml`)

The 3A dataset dictionary MUST declare S7’s outputs as datasets.

#### 5.4.1 `validation_bundle_3A`

```yaml
datasets:
  - id: validation_bundle_3A
    owner_subsegment: 3A
    description: Fingerprint-scoped validation bundle for Segment 3A.
    version: '{manifest_fingerprint}'
    format: dir
    path: data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/
    partitioning: [manifest_fingerprint]
    schema_ref: schemas.layer1.yaml#/validation/validation_bundle_index_3A
    ordering: []
    lineage:
      produced_by: 3A.S7
      consumed_by: [orchestrator, cross_segment_validation]
    final_in_layer: true
    pii: false
    licence: Proprietary-Internal
```

Binding points:

* `id` MUST be `"validation_bundle_3A"`.
* `path` MUST use `manifest_fingerprint={manifest_fingerprint}` as its only partition token.
* `schema_ref` MUST be `schemas.layer1.yaml#/validation/validation_bundle_index_3A` (index schema).
* `format: "dir"` indicates this is a directory-style dataset; consumers know to look for `index.json` inside.

#### 5.4.2 `validation_passed_flag_3A` (`_passed.flag`)

```yaml
  - id: validation_passed_flag_3A
    owner_subsegment: 3A
    description: HashGate PASS flag accompanying the validation bundle.
    version: '{manifest_fingerprint}'
    format: text
    path: data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
    partitioning: [manifest_fingerprint]
    schema_ref: schemas.layer1.yaml#/validation/passed_flag_3A
    ordering: []
    lineage:
      produced_by: 3A.S7
      consumed_by: [orchestrator, segment_readers]
    final_in_layer: true
    pii: false
    licence: Proprietary-Internal
```

Binding points:

* `id` MUST be `"validation_passed_flag_3A"` (file name remains `_passed.flag`).
* `path` MUST locate the flag in the same directory as the bundle.
* `schema_ref` MUST be `schemas.layer1.yaml#/validation/passed_flag_3A`.
* `format: "text"` indicates a single small text file.

---

### 5.5 Artefact registry entries (`artefact_registry_3A.yaml`)

For each `manifest_fingerprint`, the 3A artefact registry MUST include entries for:

* the validation bundle, and
* the PASS flag.

#### 5.5.1 `validation_bundle_3A` registry entry

```yaml
- manifest_key: "mlr.3A.validation_bundle"
  name: "Segment 3A validation bundle"
  subsegment: "3A"
  type: "dataset"
  category: "validation"
  path: "data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/"
  schema: "schemas.layer1.yaml#/validation/validation_bundle_index_3A"
  version: "1.0.0"
  digest: "<sha256_hex>"     # SHA-256 of index.json bytes (or a canonical representation)
  dependencies:
    - "mlr.3A.s0_gate_receipt"
    - "mlr.3A.sealed_inputs"
    - "mlr.3A.s1_escalation_queue"
    - "mlr.3A.s2_country_zone_priors"
    - "mlr.3A.s3_zone_shares"
    - "mlr.3A.s4_zone_counts"
    - "mlr.3A.zone_alloc"
    - "mlr.3A.zone_alloc_universe_hash"
    - "mlr.3A.s6_validation_report"
    - "mlr.3A.s6_issue_table"
    - "mlr.3A.s6_receipt"
    # plus any RNG digest artefacts if those are registered separately
  role: "Complete validation evidence for Segment 3A at this manifest"
  cross_layer: true
  notes: "Bundle members and their sha256_hex digests are enumerated in index.json; composite digest lives in _passed.flag"
```

Binding requirements:

* `manifest_key` MUST be unique and clearly identify the 3A validation bundle.
* `path` and `schema` MUST match the dataset dictionary entry.
* `dependencies` MUST list all artefacts whose digests appear in `index.json` (directly or via digest artefacts).

#### 5.5.2 `_passed.flag` registry entry

```yaml
- manifest_key: "mlr.3A.validation.passed"
  name: "Segment 3A HashGate PASS flag"
  subsegment: "3A"
  type: "dataset"
  category: "validation"
  path: "data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag"
  schema: "schemas.layer1.yaml#/validation/passed_flag_3A"
  version: "1.0.0"
  digest: "<sha256_hex>"     # SHA-256 of the _passed.flag file content
  dependencies:
    - "mlr.3A.validation_bundle"
  role: "Segment 3A HashGate flag; sha256_hex equals composite digest of validation_bundle_3A members"
  cross_layer: true
  notes: "Any consumer must verify this flag against the bundle index before treating 3A outputs as trusted"
```

Binding requirements:

* `manifest_key` MUST uniquely identify the flag.
* `path` and `schema` MUST match the dictionary entry.
* `dependencies` MUST include `mlr.3A.validation_bundle`.

---

### 5.6 No additional S7 datasets in this version

Under this contract version:

* S7 MUST NOT emit or register any outputs beyond:

  * `validation_bundle_3A` (with its `index.json`), and
  * `_passed.flag`.

If, in future, additional S7 artefacts are required (e.g. a separate 3A-wide RNG summary digest), they MUST be introduced via:

1. New schema anchors in the relevant schema pack(s).
2. New dataset entries in `dataset_dictionary.layer1.3A.yaml` with their own IDs, paths and partitioning.
3. Corresponding entries in `artefact_registry_3A.yaml` with clear `manifest_key`, `schema`, `path` and dependencies.

Until such changes are explicitly added and versioned, the shapes and catalogue links defined in this section are the **only valid definitions** of S7’s outputs.

---

## 6. Deterministic algorithm (RNG-free) **(Binding)**

This section defines the **exact behaviour** of `3A.S7 — Segment Validation Bundle & PASS Flag`.

S7:

* is **RNG-free** (no Philox, no other RNG),
* is **read-only** with respect to S0–S6 and upstream data, and
* MUST be **deterministic and idempotent**: given the same inputs, it MUST produce the same bundle and PASS flag, or detect immutability violations if outputs already exist and differ.

The algorithm is described in phases; all MUST be implemented.

---

### 6.1 Phase overview

For a given run `(parameter_hash, manifest_fingerprint, seed, run_id)`, S7 executes:

1. **Resolve inputs & pre-checks**

   * Confirm S6 PASS + `overall_status="PASS"`.
   * Confirm S0 and required S1–S6 artefacts exist and are schema-valid.

2. **Build bundle membership set**

   * Construct the **exact list** of artefacts that constitute the 3A validation bundle.

3. **Compute per-artefact digests**

   * For each member, compute (or validate) a SHA-256 digest over its canonical representation.

4. **Build `index.json`**

   * Construct a canonical index object listing all members and their digests, then serialise deterministically.

5. **Compute composite bundle digest & write `_passed.flag`**

   * Compute `bundle_sha256_hex` from the ordered per-artefact digests.
   * Write/confirm `_passed.flag` with that digest.

6. **Idempotence & immutability checks**

   * Ensure existing bundle/flag, if present, match the newly computed index and digest; otherwise fail with immutability error.

Throughout, S7 MUST NOT modify S0–S6 artefacts or any external policy/prior/reference artefacts.

---

### 6.2 Phase 1 — Resolve inputs & pre-checks

**Step 1 – Fix run identity**

S7 receives:

* `parameter_hash`,
* `manifest_fingerprint`,
* `seed`,
* `run_id`.

S7 MUST:

* validate formats (`hex64` for hashes, `uint64` for `seed`),
* treat them as immutable inputs; they MUST NOT be recomputed or altered.

**Step 2 – Verify S6 run success**

From the segment-state run-report:

* Locate the row where `state="S6"` and identity matches this run (same `parameter_hash`, `manifest_fingerprint`, `seed`, `run_id`).

S7 MUST:

* verify `status="PASS"` and `error_code=null` for S6.
* If `status != "PASS"` or `error_code != null` ⇒ S7 MUST STOP and fail with `E3A_S7_001_S6_NOT_PASS` (or equivalent), without writing a bundle or flag.

**Step 3 – Read and validate `s6_receipt_3A`**

* Resolve `s6_receipt_3A@manifest_fingerprint={manifest_fingerprint}` via dictionary/registry.
* Read the JSON and validate against `schemas.3A.yaml#/validation/s6_receipt_3A`.

S7 MUST:

* assert `s6_receipt_3A.overall_status == "PASS"`.
* If the receipt is missing, schema-invalid, or `overall_status != "PASS"` ⇒ treat as hard precondition failure; S7 MUST NOT proceed.

**Step 4 – Confirm S0 gate & sealed inputs**

* Resolve and read:

  * `s0_gate_receipt_3A@manifest_fingerprint={manifest_fingerprint}`,
  * `sealed_inputs_3A@manifest_fingerprint={manifest_fingerprint}`.

* Validate both against their schemas.

S7 MUST:

* assert that `upstream_gates.segment_1A/1B/2A.status == "PASS"`.
* If S0 reports any upstream gate as not PASS, S7 MUST NOT seal 3A and MUST fail (upstream not validated).

**Step 5 – Confirm existence & schema validity of bundle members**

Using dictionary/registry (see §5) S7 MUST resolve and validate, at minimum:

* `s0_gate_receipt_3A`
* `sealed_inputs_3A`
* `s1_escalation_queue@seed={seed}/manifest_fingerprint={manifest_fingerprint}`
* `s2_country_zone_priors@parameter_hash={parameter_hash}`
* `s3_zone_shares@seed={seed}/manifest_fingerprint={manifest_fingerprint}`
* `s4_zone_counts@seed={seed}/manifest_fingerprint={manifest_fingerprint}`
* `zone_alloc@seed={seed}/manifest_fingerprint={manifest_fingerprint}`
* `zone_alloc_universe_hash@manifest_fingerprint={manifest_fingerprint}`
* `s6_validation_report_3A@manifest_fingerprint={manifest_fingerprint}`
* `s6_issue_table_3A@manifest_fingerprint={manifest_fingerprint}` (dataset may have 0 rows but MUST exist)
* `s6_receipt_3A@manifest_fingerprint={manifest_fingerprint}`

Each artefact MUST:

* exist at the resolved path, and
* validate against its declared `schema_ref`.

If any required artefact is missing or schema-invalid, S7 MUST fail with a precondition or catalogue error and MUST NOT write bundle or flag.

---

### 6.3 Phase 2 — Build bundle membership set

**Step 6 – Construct membership list**

Based on:

* S7’s contract (required members in §4/§5), and
* `artefact_registry_3A.yaml` (which identifies 3A validation artefacts via `manifest_key` and `category: "validation"`),

S7 MUST construct a **membership list** `M`, where each element contains:

* `logical_id` — canonical ID or `manifest_key` for the artefact (e.g. `"mlr.3A.s1_escalation_queue"`),
* `path` — the concrete data path (as in the dictionary/registry),
* `schema_ref` — the schema anchor for that artefact,
* `role` — a short, stable string describing its semantic role (e.g. `"gate"`, `"sealed_inputs"`, `"domain"`, `"priors"`, `"shares"`, `"counts"`, `"egress"`, `"universe_hash"`, `"validation_report"`, `"validation_receipt"`).

The membership set MUST include, at minimum, entries for the artefacts listed in §4.2.2.

**Step 7 – Order membership list canonically**

S7 MUST define a deterministic **member ordering** to be used throughout:

* Sort `M` by `logical_id` in ASCII-lexicographic order (or by `path`, if the specification prefers that; the choice MUST be fixed in the contract and used consistently).

This ordered list `M_ord` will be used when populating `index.json` and when computing the composite bundle digest.

---

### 6.4 Phase 3 — Compute per-artefact digests

For each member `m ∈ M_ord`, S7 MUST associate a SHA-256 digest over the **canonical representation** of that artefact.

**Step 8 – Define canonical digests**

For each artefact type:

* **JSON-like single-file artefacts** (e.g. `s0_gate_receipt_3A`, `sealed_inputs_3A`, `zone_alloc_universe_hash`, `s6_validation_report_3A`, `s6_receipt_3A`):

  * S7 MUST use a deterministic JSON serialisation when computing the digest:

    * parse into logical object,
    * serialise back with:

      * keys sorted lexicographically at each level,
      * fixed whitespace rules (e.g. no insignificant whitespace),
    * compute `sha256_hex = SHA-256(serialised_bytes)`.

* **Tabular dataset artefacts** (e.g. `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`, `s4_zone_counts`, `zone_alloc`, `s6_issue_table_3A`):

  * S7 MUST compute the digest over the dataset’s data files only:

    * list all Parquet data files under the dataset root path,
    * sort file paths ASCII-lexicographically,
    * read their raw bytes in that order,
    * compute `sha256_hex = SHA-256(concatenated_bytes)`.

* **Other artefacts (e.g. RNG digest artefact, if present)**:

  * MUST follow their own contract’s canonicalisation rule; S7 MUST respect those when hashing.

S7 MAY reuse digests that have already been computed upstream (e.g. `zone_alloc_parquet_digest` in `zone_alloc_universe_hash`, `s6_receipt_digest` in S6), but:

* any reused digest MUST represent the same canonical representation defined here, and
* S7 MUST ensure integrity either by recomputing or by trusting a previously validated digest from S6/S5 (as per governance).

**Step 9 – Attach digests to membership entries**

For each `m ∈ M_ord`, S7 MUST:

* compute or retrieve `sha256_hex(m)` as above,
* record:

  * `logical_id(m)`,
  * `path(m)`,
  * `schema_ref(m)`,
  * `role(m)`,
  * `sha256_hex(m)`.

This will become the `members[]` section of `index.json`.

---

### 6.5 Phase 4 — Build `index.json`

**Step 10 – Build logical index object**

S7 MUST construct a logical index object:

```json
{
  "manifest_fingerprint": "...",
  "parameter_hash": "...",
  "s6_receipt_digest": "...",
  "members": [
    {
      "logical_id": "...",
      "path": "...",
      "schema_ref": "...",
      "sha256_hex": "...",
      "role": "...",
      "size_bytes": ...,
      "notes": "..."
    },
    ...
  ],
  "metadata": {
    "s6_version": "1.0.0",
    "...": "..."
  }
}
```

with:

* `manifest_fingerprint` = the current `manifest_fingerprint`,
* `parameter_hash` = the current `parameter_hash`,
* `s6_receipt_digest` = SHA-256 (hex) of the canonical serialisation of `s6_receipt_3A`, computed as in Step 8.

`members` MUST be:

* one entry per `m ∈ M_ord`, in the canonical order decided in Step 7,
* containing at least `logical_id`, `path`, `schema_ref`, `sha256_hex`, `role`.

If `size_bytes` is populated, it MUST be the sum of the sizes of the canonical files for that artefact (e.g. total bytes across all Parquet data files).

**Step 11 – Validate & serialise `index.json`**

The logical index object MUST:

* validate against `schemas.layer1.yaml#/validation/validation_bundle_index_3A`.

S7 MUST then:

* serialise this object as JSON using a deterministic strategy for keys (e.g. lexicographic key ordering at all levels),
* write it to:

  ```text
  data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/index.json
  ```

If an `index.json` already exists:

* S7 MUST read and parse it,
* validate it against the schema,
* compare it field-by-field with the newly constructed index object:

  * If identical (ignoring trivial whitespace differences under canonical parse/serialise) ⇒ treat it as consistent.
  * If different ⇒ S7 MUST NOT overwrite and MUST fail with immutability error (`E3A_S7_006_IMMUTABILITY_VIOLATION`).

---

### 6.6 Phase 5 — Compute composite bundle digest & write `_passed.flag`

**Step 12 – Compute composite bundle digest**

Given the ordered member list `M_ord` and their `sha256_hex` values:

* Build a byte string:

  ```text
  concat = sha256_hex(m_1) || sha256_hex(m_2) || ... || sha256_hex(m_n)
  ```

where:

* `m_1, …, m_n` are members in canonical order,

* each `sha256_hex(m_i)` is the ASCII representation of the 64-hex digest (no separators).

* Compute:

  ```text
  bundle_sha256_hex = SHA-256(concat)
  ```

and encode as a lowercase hex string of length 64.

This `bundle_sha256_hex` is the **only value** to be written to `_passed.flag`.

**Step 13 – Write or verify `_passed.flag`**

Logical form: object `{ "sha256_hex": bundle_sha256_hex }`. On disk:

```text
sha256_hex = <bundle_sha256_hex>
```

at:

```text
data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
```

If no flag exists:

* S7 MUST write this file exactly.

If a flag exists:

* S7 MUST read it, parse the line to recover `existing_sha256_hex`, and validate it against the `passed_flag_3A` schema.
* If `existing_sha256_hex == bundle_sha256_hex`, S7 MAY leave it unchanged (idempotent).
* If `existing_sha256_hex != bundle_sha256_hex`, S7 MUST NOT overwrite and MUST signal an immutability error (`E3A_S7_005_HASHGATE_MISMATCH` or `E3A_S7_006_IMMUTABILITY_VIOLATION` as appropriate).

---

### 6.7 Phase 6 — Idempotence & immutability

After execution:

* `validation_bundle_3A` (specifically `index.json`) and `_passed.flag` jointly define the 3A HashGate state for `manifest_fingerprint`.

S7 MUST guarantee:

* **Idempotence**:

  * If S7 is re-run with the same inputs and all upstream artefacts are unchanged:

    * recomputing per-artefact digests yields the same `index.json`,
    * recomputing `bundle_sha256_hex` yields the same value,
    * existing `index.json` and `_passed.flag` are identical to the newly computed ones.

* **Immutability**:

  * Existing `index.json` and `_passed.flag` MUST never be overwritten with different content for the same `manifest_fingerprint`.
  * Any attempt to do so MUST be treated as a failure and reported via S7’s error codes.

If upstream artefacts change (e.g. any S0–S6 artefact is altered) without changing `manifest_fingerprint`, S7’s recomputation will produce a different digest or index. It MUST then:

* detect the mismatch between existing bundle/flag and the new computation,
* treat this as a serious governance error (artefacts changed without manifest change),
* refuse to overwrite, and
* surface this via an immutability or digest-mismatch error.

Changing the validation universe MUST be accompanied by a new `manifest_fingerprint` (or other higher-level governance), not by mutating a bundle in place.

---

### 6.8 RNG & side-effect discipline

Across all phases, S7 MUST:

* **Never consume RNG**

  * No Philox calls, no `random()`, no time-based seeds; all hashing is deterministic.

* **Never mutate S0–S6 or upstream artefacts**

  * S7 only reads/touches them for computing digests and confirming membership.
  * Only its own artefacts (`index.json` and `_passed.flag`) may be created or updated under the immutability rules above.

* **Be deterministic**

  * For fixed inputs (S0–S6 artefacts, policies, references, catalogue), the membership list, per-artefact digests, `index.json`, and `_passed.flag` MUST always be the same.
  * Any non-determinism (e.g. iteration order, key order) MUST be resolved via canonical sorting and serialisation as specified.

Under this algorithm, S7 takes a manifest that S6 has already judged as structurally valid and produces a single, immutable, verifiable bundle + flag pair that downstream components can trust as the definitive PASS indicator for Segment 3A.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes, for **3A.S7**, how its two outputs:

* the **3A validation bundle** (`validation_bundle_3A` with `index.json`), and
* the **segment PASS flag** (`_passed.flag`),

are:

* **identified** (what uniquely names them),
* **partitioned** (what tokens appear in their paths),
* what **ordering** rules they must obey, and
* what is allowed for **merge / overwrite** behaviour.

All of this is **binding**.

---

### 7.1 Shared identity: manifest-only scoped

For S7 artefacts, the core identity is:

* `manifest_fingerprint` — the Layer-1 manifest hash (`hex64`).

All S7 outputs are **manifest_fingerprint-scoped only**:

* Partitioning MUST be exactly:

```yaml
["manifest_fingerprint"]
```

S7’s outputs are **not** keyed by `seed` or `run_id`:

* `seed` and `run_id` are relevant to S3/S4/S5 and the run-report,
* but the **3A validation bundle & PASS flag** are **per-manifest**, not per-seed or per-run.

Thus:

* For a given `manifest_fingerprint = F`, there MUST be at most one 3A validation bundle and at most one `_passed.flag`.

---

### 7.2 `validation_bundle_3A`: identity, partitioning & path↔embed equality

**Identity**

* Logical dataset ID: `validation_bundle_3A`.
* Logical key: `manifest_fingerprint`.

**Partitioning & path**

* Partitioning: `["manifest_fingerprint"]`.
* Path pattern (from dictionary):

```text
data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/
```

Binding rules:

* For a given `F`, there MUST be at most one `validation_bundle_3A` directory located at:

```text
data/layer1/3A/validation/manifest_fingerprint=F/
```

* The `index.json` inside that directory MUST have:

  * `manifest_fingerprint` equal to `F`,
  * `parameter_hash` equal to the `parameter_hash` for the manifest.

Any mismatch between the embedded `manifest_fingerprint` in `index.json` and the `{manifest_fingerprint}` path token is a schema/validation error and MUST cause S7 (or validators) to treat the bundle as invalid.

---

### 7.3 `validation_bundle_3A`: ordering semantics (members & index)

There are two relevant notions of order:

1. **Order of bundle members inside `index.json`.**
2. **Serialisation order of keys in the JSON objects.**

Both must be deterministic and are used to compute stable digests.

#### 7.3.1 Member ordering in `index.json`

Let `members[]` be the array of bundle member entries in `index.json`. S7 MUST:

* construct a membership list for all required artefacts (S0–S6, and any additional members defined in the contract),
* sort that list in a **canonical order** before writing `members[]`.

**Canonical rule (binding):**

* Sort members by `logical_id` in **ASCII-lexicographic** order.
* If there are two entries with the same `logical_id` (not allowed in this version), this is a contract violation; S7 MUST treat this as an error (or never generate such a case).

`members[]` MUST appear in this sorted order in `index.json`. This ordering is used when:

* computing the composite `bundle_sha256_hex`, and
* comparing existing vs newly constructed indices for immutability checks.

Consumers MUST NOT attach any semantic meaning to the order beyond its use for hashing and equality checks.

#### 7.3.2 JSON key ordering in `index.json`

When serialising `index.json`, S7 MUST:

* serialise JSON objects with keys in a **deterministic order**, e.g.:

  * sort keys lexicographically at each object level.

This canonical serialisation (keys sorted, no non-deterministic whitespace) MUST be used:

* to compute the index file’s own digest (if recorded in the registry), and
* whenever S6/S7 or validators recompute digests for comparison.

Again, key order is not semantically meaningful beyond digest stability.

---

### 7.4 `_passed.flag`: identity, partitioning & format

**Identity**

* Logical dataset ID: `validation_passed_flag_3A`.
* Logical key: `manifest_fingerprint`.

**Partitioning & path**

* Partitioning: `["manifest_fingerprint"]`.
* Path pattern:

```text
data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
```

Binding rules:

* For each `manifest_fingerprint = F`, there MUST be at most one `_passed.flag` at this path.
* `_passed.flag` is the only file that may serve as the PASS indicator for 3A at `F`; no alternative PASS flags are allowed.

**On-disk format**

The flag file MUST:

* be a single-line UTF-8 text file,
* contain exactly:

```text
sha256_hex = <64-lowercase-hex>
```

with:

* no extra lines, no trailing comments, and
* `<64-lowercase-hex>` equal to the composite bundle digest `bundle_sha256_hex` computed from `index.json` and its members.

When S7 reads the flag, it MUST parse it into the logical object:

```json
{ "sha256_hex": "<64-lowercase-hex>" }
```

and validate it against the `passed_flag_3A` schema.

---

### 7.5 Merge & overwrite discipline (bundle & flag)

Both `validation_bundle_3A` (specifically, its `index.json`) and `_passed.flag` are **write-once snapshots** for a given `manifest_fingerprint`. S7 MUST enforce:

#### 7.5.1 Single snapshot per `manifest_fingerprint`

* For each `F`, there MUST be at most one bundle and one PASS flag at the defined paths.
* If S7 is invoked for a manifest that already has bundle+flag, it MUST behave idempotently (see below).

#### 7.5.2 Idempotence on re-run

On a re-run for the same `(parameter_hash, manifest_fingerprint, seed, run_id)` and **unchanged upstream artefacts**:

* S7 MUST recompute:

  * membership list and per-artefact digests,
  * `index.json` logical object,
  * `bundle_sha256_hex`.

* Then:

  * If an `index.json` exists:

    * parse & normalise it,
    * compare field-by-field against the newly constructed index; they MUST be identical.

  * If `_passed.flag` exists:

    * parse its `sha256_hex`,
    * it MUST equal the newly computed `bundle_sha256_hex`.

If existing bundle and flag match the new computation:

* S7 MAY leave them untouched, or
* re-write identical bytes (implementation choice), but the **observable content MUST NOT change**.

#### 7.5.3 Immutability when differences are detected

If S7 detects that:

* an existing `index.json` is **not** logically identical to the newly computed index, and/or
* an existing `_passed.flag` has `sha256_hex` different from the newly computed `bundle_sha256_hex`,

then:

* S7 MUST NOT overwrite `index.json` or `_passed.flag`.
* S7 MUST treat this as an immutability/digest violation and fail the state with the appropriate `E3A_S7_*` error.

In particular, S7 MUST NOT:

* “update” a previously issued PASS flag to match new upstream artefacts, or
* silently change the bundle membership or digests without a new `manifest_fingerprint` (or higher-level governance).

If upstream artefacts change, the correct response is to:

* update the manifest (or its mapping to `parameter_hash`),
* produce a new `manifest_fingerprint`,
* and then generate a new bundle+flag for that new manifest, rather than mutate an existing bundle.

---

### 7.6 Cross-run & cross-segment semantics

S7 makes **no** claims about relationships between different `manifest_fingerprint` values:

* Each bundle+flag pair is independent per manifest.
* Consumers MUST NOT mix index entries or flags across different `manifest_fingerprint=` directories.

Cross-segment semantics:

* 3A’s `_passed.flag` participates in the same “No PASS → No read” discipline as:

  * 1A’s `_passed.flag`,
  * 2A’s `_passed.flag`, etc.,

but at the 3A segment level. Other segments MUST treat 3A’s flag as:

* authoritative for “3A validated for this manifest”, and
* invalid if missing, malformed, or hash-mismatched.

---

Under these rules, `validation_bundle_3A` and `_passed.flag` have:

* clear identity (`manifest_fingerprint` only),
* simple partitioning (`manifest_fingerprint=`),
* deterministic ordering (members and JSON keys), and
* strict immutability and idempotence semantics,

ensuring that once Segment 3A is marked PASS for a manifest, its validation bundle and flag remain stable, auditable, and safe to trust.

---

## 8. Acceptance criteria & gating obligations **(Binding)**

This section defines:

1. **When S7, as a state, is considered PASS** for a given run
   `(parameter_hash, manifest_fingerprint, seed, run_id)`, and
2. The **gating obligations** S7 imposes on downstream consumers via
   `validation_bundle_3A` and `_passed.flag`.

S7’s job is *not* to re-validate S0–S6, but to:

* refuse to seal 3A unless S6 has already declared PASS, and
* ensure the bundle + flag are complete, consistent, and immutable.

---

### 8.1 Local acceptance criteria for S7 (state-level)

For a given run `(parameter_hash, manifest_fingerprint, seed, run_id)`, 3A.S7 is considered **PASS** (S7 `status="PASS", error_code=null` in the run-report) if and only if **all** of the following hold:

#### 8.1.1 S6 verdict and run status are acceptable

* S6 **state run** for this run has:

  * `status="PASS"` and `error_code=null` in the segment-state run-report.

* `s6_receipt_3A@manifest_fingerprint={manifest_fingerprint}`:

  * exists and validates against `#/validation/s6_receipt_3A`,
  * has `overall_status="PASS"`.

If S6 state run is not PASS, or `overall_status != "PASS"`, S7 MUST NOT proceed to build a bundle or flag and MUST treat the run as FAIL (`E3A_S7_001_S6_NOT_PASS` or equivalent).

**No S6 PASS ⇒ no S7 PASS.**

#### 8.1.2 S0 gate & sealed inputs are valid

For the given `manifest_fingerprint`:

* `s0_gate_receipt_3A` and `sealed_inputs_3A`:

  * exist and validate against their schemas,
  * `upstream_gates.segment_1A/1B/2A.status == "PASS"`.

If S0 gate or upstream gates are not PASS, S7 MUST NOT seal 3A and MUST fail.

#### 8.1.3 All required bundle members exist and are schema-valid

All artefacts that the S7 contract and catalogue declare as **bundle members** for this manifest MUST:

* be resolvable via dictionary/registry,
* exist at their declared paths, and
* validate against their declared `schema_ref`.

At minimum this covers:

* S0: `s0_gate_receipt_3A`, `sealed_inputs_3A`.
* S1: `s1_escalation_queue`.
* S2: `s2_country_zone_priors`.
* S3: `s3_zone_shares` (+ any declared RNG digest artefacts, if bundled).
* S4: `s4_zone_counts`.
* S5: `zone_alloc`, `zone_alloc_universe_hash`.
* S6: `s6_validation_report_3A`, `s6_issue_table_3A`, `s6_receipt_3A`.

If any required artefact is:

* missing,
* not resolvable, or
* schema-invalid,

S7 MUST fail with a precondition/catalogue error and MUST NOT write or confirm bundle/flag.

#### 8.1.4 `index.json` is complete, correct & canonical

S7 MUST:

1. **Construct the membership list** as per §6:

   * Include all required members, no duplicates, no unexpected extras
     (unless explicitly allowed by the bundle spec).

2. **Compute or verify per-artefact digests** as per §6.4, using canonical representations.

3. **Build a logical index object**:

   * `manifest_fingerprint`, `parameter_hash`, `s6_receipt_digest`,
   * `members[]` with (`logical_id`, `path`, `schema_ref`, `sha256_hex`, `role`, …),
   * optional `metadata`.

4. **Validate index**:

   * `index.json` MUST validate against `#/validation/validation_bundle_index_3A`.

5. **Ensure member list is ordered canonically** (by `logical_id` or `path`, as defined) and JSON keys are serialised deterministically.

If any of these steps fail (e.g. missing member, invalid schema, mismatched digest, unstable ordering), S7 MUST treat the run as FAIL (`E3A_S7_003_INDEX_BUILD_FAILED` / `E3A_S7_004_DIGEST_MISMATCH` as appropriate).

#### 8.1.5 Composite bundle digest & flag consistency

Given `index.json`:

* S7 MUST compute the composite digest:

  * `bundle_sha256_hex = SHA256(concat(sha256_hex(m_1), …, sha256_hex(m_n)))`
    with members in the canonical order.

* `_passed.flag`:

  * MUST exist after S7 PASS,
  * MUST parse as `sha256_hex = <64-lowercase-hex>`,
  * `sha256_hex` MUST equal `bundle_sha256_hex`.

If a flag already exists:

* its parsed `sha256_hex` MUST equal `bundle_sha256_hex`,
* otherwise S7 MUST NOT overwrite and MUST fail with a digest/immutability error.

#### 8.1.6 Idempotence & immutability are preserved

If `index.json` and/or `_passed.flag` already exist for this `manifest_fingerprint`:

* S7 MUST:

  * read & validate `index.json` and `_passed.flag`,
  * recompute the logical index object and `bundle_sha256_hex` from current inputs,
  * compare:

    * existing index vs newly computed index, and
    * existing flag `sha256_hex` vs newly computed `bundle_sha256_hex`.

* S7 is PASS only if:

  * both the index and flag are **logically identical** to what S7 would produce now.

If any difference is found (index or flag), S7 MUST:

* NOT overwrite the existing artefacts, and
* fail the state with an immutability/digest mismatch error (`E3A_S7_005_HASHGATE_MISMATCH` or `E3A_S7_006_IMMUTABILITY_VIOLATION`).

---

### 8.2 Gating obligations: “No 3A PASS → No read”

S7’s bundle and PASS flag jointly implement the 3A segment HashGate. They impose **binding obligations** on downstream consumers (orchestrator, cross-segment validation, 2B, external readers).

For any `manifest_fingerprint = F`, the following MUST hold:

1. **To treat 3A outputs as validated for F, a consumer MUST:**

   1.1. Locate `validation_bundle_3A@manifest_fingerprint=F` and `_passed.flag@manifest_fingerprint=F`.

   1.2. Validate both against their schemas:

   * `index.json` ⇒ `validation_bundle_index_3A`,
   * `_passed.flag` ⇒ `passed_flag_3A`.

   1.3. Recompute `bundle_sha256_hex` from `index.json`:

   * reconstruct the ordered list of members `m_1…m_n`,
   * parse each `sha256_hex(m_i)` as hex,
   * build the concatenated byte string `concat`,
   * compute `SHA-256(concat)`.

   1.4. Compare the recomputed digest with `_passed.flag.sha256_hex`:

   * If equal ⇒ **bundle verified**; 3A is validated for this manifest.
   * If not equal ⇒ **bundle invalid**; consumer MUST treat 3A as NOT PASS and not read 3A surfaces.

2. **No PASS → no read (binding)**

   * If a consumer cannot:

     * find `validation_bundle_3A` for `F`, or
     * find `_passed.flag` for `F`, or
     * validate their schemas, or
     * verify the HashGate digest match,

   then it MUST NOT:

   * treat 3A S1–S5 outputs as trusted for `F`,
   * use `zone_alloc` or any other 3A egress surfaces for routing, simulation, training, or analytics that assume validated data.

   In such cases, the correct behaviour is to fail fast or fall back per orchestration policy, not to bypass the gate.

3. **Use of S6 artefacts via bundle**

   * Consumers that need to understand **why** 3A is PASS or FAIL at a structural level SHOULD:

     * read `s6_receipt_3A`, `s6_validation_report_3A`, and `s6_issue_table_3A` via the bundle index,
     * respect S6’s `overall_status` and per-check statuses.

   * They MUST NOT override S6’s verdict based solely on partial re-analysis of S1–S5; S6 remains the validation authority.

---

### 8.3 S7 state vs 3A segment status

S7’s **state-level status** (in the run-report) and the **segment-level status** are related but distinct:

* **S7 run `status="PASS"`** means:

  * S7 successfully verified that:

    * S6 said PASS and its artefacts are valid,
    * required bundle members exist and are schema-valid,
    * `index.json` is correct and canonical,
    * `_passed.flag` matches the bundle digest (or was correctly created),
    * immutability constraints are respected.

* **S7 run `status="FAIL"`** means:

  * S7 could not complete bundling correctly (preconditions, catalogue, digest or immutability issues, or infra failures).
  * In this case, 3A cannot be considered sealed for this manifest.

From a **segment status** perspective:

* 3A is considered **fully validated and sealed** for `manifest_fingerprint = F` only if:

  * S6’s `overall_status="PASS"`, **and**
  * S7’s run status is `status="PASS", error_code=null`, **and**
  * `_passed.flag` has been successfully verified against `validation_bundle_3A`.

If any of those conditions fail, the segment is **not** to be treated as PASS, and consumers must obey the “no PASS → no read” rule.

---

### 8.4 Handling S7 failures

If S7 fails:

* No `_passed.flag` MUST be considered valid for that `manifest_fingerprint`.
* `validation_bundle_3A` (if partially constructed) MUST be treated as non-authoritative until S7 is re-run successfully.

Recovery requires:

* determining whether failure is:

  * due to true upstream inconsistency (e.g. members/digests changed without a new manifest), or
  * due to S7/catalogue/infrastructure issues,

* fixing the root cause (e.g. regenerate affected artefacts under a new `manifest_fingerprint`, repair catalogue, or correct S7 implementation), and

* re-running S7, producing a new, consistent bundle+flag pair.

Only then may 3A be considered sealed and safe to read for that manifest.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only allowed run-level failure classes** for
`3A.S7 — Segment Validation Bundle & PASS Flag` and assigns each a **canonical error code**.

These codes describe **S7’s ability to do its job** (build/verify the bundle + flag). They are **not** about whether 3A is structurally valid (that’s S6’s `overall_status`).

* If S7 completes all steps successfully, its run-report row MUST be:

  * `status="PASS", error_code=null`.
* If S7 cannot complete due to any of the conditions below, its run-report row MUST be:

  * `status="FAIL", error_code = <one of E3A_S7_001 … E3A_S7_007>`.

Segment-level “3A PASS/FAIL” is defined by **S6’s receipt + S7’s success** (see §8.3).

---

### 9.1 Error taxonomy overview

S7 run-level failures are partitioned into these classes:

1. **S6 gating or S0 precondition failure**
2. **Required 3A artefacts missing / malformed**
3. **Index build / validation failures**
4. **Per-artefact digest mismatch**
5. **Composite HashGate / flag mismatch**
6. **Immutability violations (existing bundle/flag differ from new)**
7. **Infrastructure / I/O failures**

Each maps to a specific `E3A_S7_XXX_*` code.

---

### 9.2 S6 gating failure – S6 not PASS

#### `E3A_S7_001_S6_NOT_PASS`

**Condition**

Raised when S7 cannot proceed because S6 has not declared Segment 3A as PASS for this manifest, including:

* In the segment-state run-report, S6’s row has:

  * `status != "PASS"` **or** `error_code != null`.
* `s6_receipt_3A@manifest_fingerprint={manifest_fingerprint}`:

  * is missing,
  * fails `#/validation/s6_receipt_3A`, or
  * has `overall_status != "PASS"`.

In any of these cases, S7 MUST NOT build a validation bundle or write `_passed.flag`.

**Required fields**

* `reason ∈ {"s6_run_failed","s6_receipt_missing","s6_receipt_invalid","s6_overall_not_pass"}`.
* Optionally:

  * `s6_status` — the S6 run-report `status` (if available).
  * `s6_error_code` — the S6 error code (if any).
  * `s6_overall_status` — value of `overall_status` from the receipt (if present).

**Retryability**

* **Non-retryable** for S7 alone.

  * Upstream (S6 and possibly earlier states) MUST be corrected and re-run before S7 can succeed.
  * Re-running S7 without addressing S6 will reproduce this failure.

---

### 9.3 Required artefacts missing / malformed

#### `E3A_S7_002_PRECONDITION_MISSING_ARTEFACT`

**Condition**

Raised when S7 cannot assemble the bundle due to missing or malformed 3A artefacts that are required bundle members, including:

* S0 artefacts:

  * `s0_gate_receipt_3A` missing or schema-invalid,
  * `sealed_inputs_3A` missing or schema-invalid,
  * `upstream_gates.segment_1A/1B/2A.status != "PASS"`.

* S1–S6 datasets/artefacts:

  * `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`, `s4_zone_counts`, `zone_alloc`, `zone_alloc_universe_hash`, `s6_validation_report_3A`, `s6_issue_table_3A`, or `s6_receipt_3A`:

    * missing from storage,
    * cannot be resolved via dictionary/registry, or
    * fail validation against their `schema_ref`.

**Required fields**

* `artefact_id` — logical ID or manifest_key of the missing/invalid artefact (e.g. `"mlr.3A.s1_escalation_queue"`, `"mlr.3A.zone_alloc_universe_hash"`).
* `reason ∈ {"missing","schema_invalid","upstream_gate_not_pass"}`.
* Optionally:

  * `expected_schema_ref` — the schema anchor S7 attempted to validate against.

**Retryability**

* **Non-retryable** for S7 alone.

  * The missing/malformed artefacts (or upstream gates) MUST be corrected and re-generated under the same or a new manifest before S7 can succeed.

---

### 9.4 Index build / validation failures

#### `E3A_S7_003_INDEX_BUILD_FAILED`

**Condition**

Raised when S7 cannot construct a valid `index.json` object for `validation_bundle_3A`, including:

* Failure to construct a complete membership list that matches the S7 contract and catalogue (e.g. duplicate `logical_id`, inconsistent roles, or missing required member entries).
* Logical index object fails validation against `#/validation/validation_bundle_index_3A` despite all members being present and schema-valid.
* Internal inconsistencies in the index (e.g. `manifest_fingerprint` or `parameter_hash` fields in index do not match the run’s identity).

**Required fields**

* `reason ∈ {"missing_member","duplicate_logical_id","index_schema_invalid","identity_mismatch"}`.
* `member_count` — number of member entries S7 attempted to include.
* Optionally:

  * `offending_logical_id` — a representative `logical_id` causing the problem (if applicable).

**Retryability**

* **Retryable only after either:**

  * S7’s implementation is fixed (if the cause is a bug in index construction), or
  * upstream catalogue/artefact registration is corrected (if the cause is inconsistent metadata).

Re-running S7 without addressing the root cause will likely reproduce this error.

---

### 9.5 Per-artefact digest mismatch

#### `E3A_S7_004_DIGEST_MISMATCH`

**Condition**

Raised when S7’s recomputed SHA-256 digest for a bundle member does **not** match an authoritative digest it expects to align with, including:

* `s6_receipt_digest` in the index does not equal `SHA-256(s6_receipt_3A)` recomputed from the stored receipt.
* A member entry in `index.json` has `sha256_hex` that does not match recomputed digest(s) from the referenced artefact (e.g. S5’s `zone_alloc_parquet_digest`, S2’s prior digest).
* Any other authoritative digest fields (as defined in S5/S6) diverge from the actual artefacts.

**Required fields**

* `artefact_id` — logical ID or manifest_key of the artefact whose digest mismatched.
* `path` — the path S7 used to read the artefact (if known).
* `expected_sha256_hex` — digest stored in index or upstream artefact (if applicable).
* `observed_sha256_hex` — digest recomputed over the canonical representation.

**Retryability**

* **Non-retryable** for S7 alone.

  * Usually indicates that artefacts have changed (or were corrupted) after S5/S6 ran, or upstream digests were recorded incorrectly.
  * Governance MUST decide whether to:

    * restore/fix the underlying artefact(s), and/or
    * regenerate the manifest and 3A pipeline before re-running S7.

---

### 9.6 Composite HashGate / flag mismatch

#### `E3A_S7_005_HASHGATE_MISMATCH`

**Condition**

Raised when S7 detects a mismatch between:

* the composite bundle digest recomputed from `index.json` and member digests (`bundle_sha256_hex`), and
* the value in `_passed.flag` (if it already exists).

Examples:

* `_passed.flag` exists and contains `sha256_hex = X`, but S7 recomputes `bundle_sha256_hex = Y` with `X != Y`.
* Index and member digests are internally consistent, but the flag does not reflect the current bundle content.

**Required fields**

* `existing_sha256_hex` — the `sha256_hex` value read from `_passed.flag`.
* `computed_sha256_hex` — the composite digest recomputed from `index.json`.
* Optionally:

  * `manifest_fingerprint` — for clarity in logs.

**Retryability**

* **Non-retryable** without governance intervention.

This typically indicates:

* `_passed.flag` was manually edited or belongs to a different bundle, or
* underlying bundle content changed without updating the flag (which must not happen under proper governance).

Corrective action usually involves:

* treating the existing flag as invalid,
* investigating why the bundle changed,
* possibly issuing a new manifest and re-running S0–S7.

S7 MUST NOT overwrite the existing flag to “fix” this mismatch.

---

### 9.7 Immutability violations (existing vs new bundle content)

#### `E3A_S7_006_IMMUTABILITY_VIOLATION`

**Condition**

Raised when S7 determines that:

* an existing `index.json` file for `validation_bundle_3A@manifest_fingerprint={F}` is logically different from the index S7 would produce now (with the current artefacts), **or**
* `_passed.flag` already exists and S7 would need to change its content to reflect the new composite digest, **and** the mismatch is not just a “flag vs index” mismatch (which is covered by `E3A_S7_005_*`), but a mismatch between **previously sealed** and **currently derived** bundle state.

Typical causes:

* underlying S0–S6 artefacts have been altered after an earlier bundle+flag were generated for the same `manifest_fingerprint`, without regenerating the manifest,
* or S7’s own index-building logic changed between runs, causing differences under a supposedly unchanged universe (this is a contract/implementation bug).

**Required fields**

* `artefact ∈ {"index","flag","both"}` — which artefact is in conflict.
* `difference_kind ∈ {"members","digest","identity"}` — whether the conflict is in membership list, per-member digest, or identity fields.
* Optionally:

  * `difference_count` — number of member entries or fields that differ (if computed).

**Retryability**

* **Non-retryable** without manual/governance intervention.

Operators must decide:

* whether to:

  * treat the existing bundle+flag as authoritative and investigate what changed upstream, or
  * invalidate the old bundle+flag and rerun the entire 3A pipeline under a new `manifest_fingerprint`.

S7 MUST NOT unilaterally overwrite existing bundle or flag for a given manifest.

---

### 9.8 Infrastructure / I/O failures

#### `E3A_S7_007_INFRASTRUCTURE_IO_ERROR`

**Condition**

Raised when S7 cannot complete due to environment-level issues that are not logical bundle/flag errors, for example:

* transient object-store or filesystem failures while reading S0–S6 artefacts or writing S7 outputs,
* permission errors (e.g. insufficient write access to the validation bundle directory),
* network timeouts when accessing remote storage,
* storage quota exhaustion or disk full.

This code MUST NOT be used for logical inconsistencies (e.g. digest mismatches, missing artefacts); those are covered by other S7 error codes.

**Required fields**

* `operation ∈ {"read","write","list","stat"}` — what kind of I/O S7 was performing.
* `path` — the path or URI involved (if known).
* `io_error_class` — short classification string, e.g. `"timeout"`, `"permission_denied"`, `"not_found"`, `"quota_exceeded"`, `"connection_reset"`.

**Retryability**

* **Potentially retryable**, depending on infrastructure policy.

Orchestrators MAY:

* retry S7 on `E3A_S7_007_INFRASTRUCTURE_IO_ERROR` after a backoff,
* but a successful retry MUST still satisfy all acceptance criteria in §8, including immutability checks and digest verification.

---

### 9.9 Run-report mapping

For each S7 invocation, the segment-state run-report row for `state="S7"` MUST follow:

* If no S7 run-level error occurs (all steps completed, bundle+flag are consistent):

  * `status = "PASS"`
  * `error_code = null`

* If any of the above failure conditions occur:

  * `status = "FAIL"`
  * `error_code =` the corresponding `E3A_S7_XXX_*` code
  * `error_class` MUST reflect the category (e.g. `"S6_GATE"`, `"PRECONDITION"`, `"INDEX"`, `"DIGEST"`, `"HASHGATE"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`).

Downstream consumers MUST interpret:

* S7 `status="PASS"` + S6 `overall_status="PASS"` + verified `_passed.flag` ⇒ **3A sealed and safe to read** for that manifest.
* Any S7 `status="FAIL"` ⇒ **3A cannot be sealed** for that manifest until the underlying cause is addressed and S7 is successfully re-run.

---

## 10. Observability & run-report integration *(Binding)*

This section defines what **3A.S7 — Segment Validation Bundle & PASS Flag** MUST emit for observability, and how it MUST integrate with the Layer-1 **segment-state run-report**.

S7 has **two distinct notions of status**:

* **S7 state run status** (in the run-report):

  * did S7 successfully build/verify the bundle + flag?
* **3A segment validation status** (indirect):

  * determined by **S6 `overall_status`** plus S7 success and a verifiable `_passed.flag`.

S7 MUST clearly report its own run status, and provide enough information for downstream systems to identify the 3A validation state.

S7 MUST NOT log or expose full business data from the bundle; it only reports **high-level summaries and digests**.

---

### 10.1 Structured logging requirements

S7 MUST emit structured logs (e.g. JSON) for three lifecycle events: **start**, **success**, and **failure**.

#### 10.1.1 Start log

Exactly one log event at the beginning of each S7 invocation.

**Required fields**

* `layer = "layer1"`
* `segment = "3A"`
* `state = "S7"`
* `parameter_hash` — `hex64`
* `manifest_fingerprint` — `hex64`
* `seed` — `uint64` (for correlation only)
* `run_id` — string / u128-encoded
* `attempt` — integer (1 for first attempt; incremented by orchestrator on retries)

**Optional fields**

* `trace_id` — correlation ID from orchestration.

**Log level:** `INFO`.

---

#### 10.1.2 Success log

Exactly one log event **only if** S7 completes successfully as a state, i.e.:

* built/verified `validation_bundle_3A` + `_passed.flag`, and
* met all acceptance criteria in §8 (including immutability).

**Required fields**

* All fields from the start log.
* `status = "PASS"`             *(S7 run status)*
* `error_code = null`

**Bundle summary**

* `bundle_member_count` — number of member entries in `index.json`.
* `bundle_path` — path to `validation_bundle_3A` root (e.g. `data/layer1/3A/validation/manifest_fingerprint=…/`).
* `bundle_sha256_hex` — composite digest written into `_passed.flag`.

**S6 linkage**

* `s6_overall_status` — value from `s6_receipt_3A.overall_status` (MUST be `"PASS"` on S7 success).
* `s6_receipt_digest` — SHA-256 (hex) of the canonical `s6_receipt_3A` used in the index.

**Optional**

* `elapsed_ms` — wall-clock duration for S7 (from orchestrator; MUST NOT influence logic).

**Log level:** `INFO`.

---

#### 10.1.3 Failure log

Exactly one log event **only if** the S7 state run fails (`status="FAIL"` in the run-report) for any reason described in §9.

**Required fields**

* All fields from the start log.

* `status = "FAIL"`

* `error_code` — one of `E3A_S7_001 … E3A_S7_007`.

* `error_class` — coarse category, e.g.:

  * `"S6_GATE"`, `"PRECONDITION"`, `"INDEX"`, `"DIGEST"`, `"HASHGATE"`, `"IMMUTABILITY"`, `"INFRASTRUCTURE"`.

* `error_details` — structured object including the required fields for the specific error code (e.g. `reason`, `artefact_id`, `expected_sha256_hex`, `observed_sha256_hex`, etc.).

**Recommended additional fields**

* `bundle_member_count` — if membership was computed before failure.
* `existing_flag_sha256_hex` — if a mismatched flag was detected.

**Optional**

* `elapsed_ms`.

**Log level:** `ERROR`.

Logs MUST be machine-parseable and MUST NOT include the content of bundle members (no dumping entire JSON or Parquet contents).

---

### 10.2 Segment-state run-report entry

S7 MUST write exactly **one row** into the Layer-1 **segment-state run-report** for each invocation.

This row is about **S7 as a state**, not directly about segment “PASS/FAIL” (which is S6 + S7 + flag).

**Required identity fields**

* `layer = "layer1"`
* `segment = "3A"`
* `state = "S7"`
* `parameter_hash`
* `manifest_fingerprint`
* `seed`
* `run_id`
* `attempt`

**Required outcome fields**

* `status ∈ {"PASS","FAIL"}` — S7 run status.
* `error_code` — `null` if `status="PASS"`, else one of `E3A_S7_001 … E3A_S7_007`.
* `error_class` — coarse category if `status="FAIL"`, `null` otherwise.

**Optional localisation**

* `first_failure_phase` — enum describing where S7 failed, e.g.:

  ```text
  "S6_GATE"
  | "PRECONDITION"
  | "INDEX_BUILD"
  | "DIGEST_COMPUTE"
  | "HASHGATE_VERIFY"
  | "IMMUTABILITY"
  | "INFRASTRUCTURE"
  ```

**Bundle summary fields** (required if `status="PASS"`; MAY be populated on FAIL if available)

* `bundle_member_count` — number of entries in `index.json.members`.
* `bundle_sha256_hex` — composite digest written to `_passed.flag`.
* `bundle_path` — path to the bundle root.

**S6 linkage fields** (required if `status="PASS"`)

* `s6_status` — S6 run-report `status` used as precondition (MUST be `"PASS"`).
* `s6_error_code` — error code from S6 (MUST be `null`).
* `s6_overall_status` — `overall_status` from `s6_receipt_3A` (MUST be `"PASS"`).
* `s6_receipt_digest` — digest used in the bundle index.

**Timing & correlation**

* `started_at_utc` — from orchestrator; MUST NOT influence S7 logic.
* `finished_at_utc`
* `elapsed_ms`
* `trace_id` — if used.

Run-report entries MUST be consistent with:

* S7 logs,
* the contents of `validation_bundle_3A` (`index.json`), and
* `_passed.flag`, for this `(parameter_hash, manifest_fingerprint, seed, run_id)`.

---

### 10.3 Metrics & counters

S7 MUST export a minimal set of metrics for monitoring. Names/export mechanism are implementation details; the semantics are binding.

At minimum:

* `mlr_3a_s7_runs_total{status="PASS"|"FAIL"}`

  * Monotone counter; incremented once per S7 invocation.

* `mlr_3a_s7_bundles_created_total`

  * Counter; number of times S7 successfully produced or confirmed a valid bundle+flag pair.

* `mlr_3a_s7_bundle_members_total`

  * Gauge; number of members per bundle in the most recent successful run (per manifest context or globally labelled).

* `mlr_3a_s7_hashgate_mismatch_total`

  * Counter; incremented when `E3A_S7_005_HASHGATE_MISMATCH` is raised.

* `mlr_3a_s7_immutability_violations_total`

  * Counter; incremented on `E3A_S7_006_IMMUTABILITY_VIOLATION`.

* `mlr_3a_s7_duration_ms`

  * Histogram; S7 run durations (derived from `elapsed_ms`).

Metric labels MUST NOT include raw `manifest_fingerprint` values or other high-cardinality identifiers. Recommended labels:

* `state="S7"`
* `status` (for run metrics)
* `error_class` (for failure metrics)
* coarse size buckets (e.g. `bundle_member_count_bucket ∈ {"small","medium","large"}`) if desired.

---

### 10.4 Correlation & traceability

S7 outputs MUST be easy to correlate with upstream and to verify:

1. **Cross-state correlation**

   * S7’s run-report row MUST be joinable with S0–S6 rows via:

     ```text
     (layer="layer1",
      segment="3A",
      parameter_hash,
      manifest_fingerprint,
      seed,
      run_id)
     ```

   * A shared `trace_id` (if present) SHOULD be propagated across S0–S7 logs and run-report rows to support per-run tracing.

2. **Artefact navigation**

   From S7’s run-report row and the catalogue, a tool MUST be able to:

   * locate `validation_bundle_3A@manifest_fingerprint={manifest_fingerprint}`,
   * load `index.json` via its `schema_ref`,
   * locate `_passed.flag@manifest_fingerprint={manifest_fingerprint}`,
   * and then, via `index.json.members[]`, locate all bundle members (S0–S6 artefacts) and verify their digests.

This ensures any validator can start from S7 and traverse:

> S7 run-report → bundle/flag → `index.json` → S0–S6 artefacts.

---

### 10.5 Retention, access control & privacy

Even though S7 artefacts are small and mostly metadata, they control access to 3A’s business surfaces; they require disciplined handling.

**Retention**

* `validation_bundle_3A` and `_passed.flag` MUST be retained:

  * at least as long as any 3A outputs they govern (S1–S5 egress, S6 validation artefacts) are in use, and
  * at least as long as any higher-level bundles (e.g. a “Layer-1 bundle” that includes 3A) remain considered valid.

* Deleting bundle/flag while dependants are live violates the “no PASS → no read” discipline and is out of spec.

**Access control**

* Access to S7 artefacts SHOULD be limited to:

  * orchestrators that enforce `no PASS → no read`,
  * cross-segment validators,
  * authorised operators and governance tooling.

* S7 logs/layer1/3A/run-report MUST NOT expose sensitive internal details beyond what is necessary (e.g. no raw policy bodies, no per-row data; only digests, counts, and statuses).

**No bundle content leakage via logging**

* S7 logs MUST NOT contain:

  * the full contents of bundle members (e.g. full `s6_validation_report_3A` or `sealed_inputs_3A`),
  * detailed lists of member paths beyond what is necessary (one or two example members for debugging is acceptable subject to policies).

---

### 10.6 Relationship to Layer-1 governance

Layer-1 may impose generic logging and run-report requirements (e.g. environment IDs, build IDs, cluster names). S7 MUST satisfy both:

* Layer-1 requirements (for shape and required fields), and
* this S7 contract (for S7-specific semantics and fields).

Where there is a conflict:

* Layer-1 run-report schema dictates **structure/field presence**.
* This section dictates **how S7 populates those fields** with:

  * S7 run status and error_code/error_class,
  * bundle + flag summary,
  * S6 linkage,
  * and the relationship between S7’s state and the 3A segment PASS condition.

Under these rules, every S7 run is:

* **observable** (structured logs),
* **summarised** (single run-report row), and
* **auditable** (verifiable bundle + flag + indices),

so that orchestrators and cross-segment governance can reliably enforce the intended “no 3A PASS → no 3A read” policy for each manifest.

---

## 11. Performance & scalability *(Informative)*

This section explains how 3A.S7 behaves at scale and what actually dominates its cost. The binding rules remain in §§1–10; this is only an operational view.

---

### 11.1 Workload shape

S7 is deliberately tiny compared to the rest of 3A. It does:

* **No modelling, no RNG, no big joins**.
* It only:

  * checks S6’s verdict and basic preconditions,
  * walks a *small set* of 3A artefacts (S0–S6) that are already persisted,
  * computes SHA-256 digests over them,
  * writes a single `index.json` and a one-line `_passed.flag`.

So the main work is:

* I/O to read each artefact once, and
* streaming them through SHA-256.

The cost is therefore ~proportional to the **total bytes** of S0–S6 artefacts included in the bundle, especially the larger ones (S1–S5 surfaces, RNG logs if bundled).

---

### 11.2 Complexity drivers

Per `manifest_fingerprint`:

1. **Catalogue & S6 pre-checks**

   * Lightweight: a few dictionary/registry lookups and S6/state run-report reads.
   * Complexity: O(1).

2. **Schema validation of bundle members**

   * Each artefact has already been validated in its own state (S0–S6); S7 only needs to revalidate briefly:

     * JSON artefacts: tiny.
     * Parquet datasets: can be “schema-validated” by checking metadata without scanning all rows.
   * Cost: small relative to reading full data for digesting.

3. **Digest computation over artefacts**

   * For each bundle member:

     * JSON/receipt/report/policy artefacts: KB–MB scale at most.
     * S1–S5 datasets: dominated by:

       * `s1_escalation_queue` size,
       * `s3_zone_shares`, `s4_zone_counts`, `zone_alloc`, and `s6_issue_table_3A` sizes.

   * SHA-256 is **O(bytes)**: read file(s) in chunks, update hash; no random access required.

4. **Index construction & serialisation**

   * Build a small JSON object with ~O(#members) entries.
   * Member count is bounded by “number of 3A validation artefacts”; it does not grow with data volume.
   * Cost: effectively O(1) in terms of data size; the number of members is tiny.

5. **Composite digest & flag**

   * Concatenate ~dozens of 64-hex digests ≈ negligible work.
   * Write one small text file.

Overall, runtime is essentially:

[
\text{Time}_{S7} \approx c_0 + c_1 \cdot \text{bytes}(s1\ldots s6\ \text{members}),
]

with `c_1` being the cost of streaming SHA-256 and `c_0` the constant overhead of wiring things up.

---

### 11.3 Memory footprint

S7 does not need large in-memory structures. It can be implemented as a **streaming digester**:

* For each member:

  * open the artefact file(s),
  * stream content in fixed-size chunks (e.g. 4–64 MB) into SHA-256,
  * close and store just the resulting 64-hex digest.

* The `index.json` object is small and easily fits in memory.

Peak memory is therefore bounded by:

* one digest context (constant size),
* one chunk buffer (e.g. tens of MB at most),
* a small membership list (a few dozen entries).

S7 never needs to load a full S1–S5 dataset into RAM; it only reads their bytes sequentially.

---

### 11.4 Parallelism & scheduling

S7 is naturally lightweight but can still benefit from parallelism if desired:

* **Across manifests**

  * Different `manifest_fingerprint` values are independent.
  * Bundles for multiple manifests can be computed in parallel.

* **Within a manifest**

  * Digests for different artefacts can be computed in parallel, provided:

    * you still produce a single, deterministic `index.json`,
    * per-artefact digests are assembled in the canonical order at the end.

Constraints:

* **Determinism matters more than speed**:

  * Final `index.json` MUST have a stable member order,
  * final `bundle_sha256_hex` MUST be derived from that stable order.
  * Parallel computation is fine as long as final assembly respects the canonical sort.

In most deployments, S7 will be so cheap that you can schedule it serially at the tail of the 3A pipeline without concern.

---

### 11.5 Expected runtime profile

Compared to earlier states:

* S7 is:

  * dramatically cheaper than S1 (group-bys over 1A outlets),
  * cheaper than S2/S3 (priors and Dirichlet sampling),
  * cheaper than S4 (integerisation) and S5/S6 (structural checks and digests).

* S7’s runtime is dominated by:

  * reading `zone_alloc` and other Parquet datasets once more,
  * hashing them,
  * writing one JSON file and a tiny text flag.

In a practical engine, the **S7 bottleneck** will almost always be I/O throughput (how fast you can stream big Parquet files, if needed), not CPU or memory.

---

### 11.6 Tuning levers (non-normative)

Implementations can tune S7 further without changing semantics:

1. **Chunk size tuning for SHA-256**

   * Choose an I/O chunk size that matches storage and CPU characteristics (e.g. 4–16 MB) for good throughput.

2. **Digest reuse where safe**

   * Where upstream states (S5/S6) have already computed canonical digests and exposed them (e.g. in `zone_alloc_universe_hash`, `s6_receipt_digest`), S7 can reuse those instead of re-reading artefacts, provided:

     * you trust those digests (they’ve been validated by S6), and
     * they follow the same canonicalisation rules.

3. **Configurable bundling depth**

   * Some deployments may choose to include only digests for certain heavy artefacts (e.g. RNG logs) rather than bundling the logs themselves.
   * The spec for what’s in the bundle is fixed by the contract; but internal representation (inlining vs referencing pre-sealed digest artefacts) can be tuned as long as `index.json` captures the correct digests.

4. **Deferred bundling**

   * S7 can be scheduled after S6 in a lower-priority pool since it doesn’t affect business data, only validation evidence.
   * For example, run S7 for all manifests in a nightly batch.

None of these levers may change:

* which members `index.json` declares,
* how canonical digests are computed,
* how the composite digest is computed and written, or
* the immutability semantics.

---

### 11.7 Scalability summary

S7’s design keeps **performance and scalability concerns minimal**:

* It scales with the **size and number of artefacts** in the 3A bundle, not with the total transaction volume or number of merchants directly.
* It uses **streaming hashes**, small metadata structures, and no heavy computation.
* It’s easily:

  * batchable (run after S6),
  * parallelisable across manifests, and
  * bounded in memory and CPU.

In short: if the rest of 3A can scale, S7 will follow almost for free; its primary role is to turn “validated state” into a small, cryptographically sealed “I promise this is 3A” bundle that is cheap to compute and easy to verify.

---

## 12. Change control & compatibility *(Binding)*

This section defines **how the 3A.S7 contract is allowed to evolve**, and what guarantees consumers (orchestrator, 2B, cross-segment validators, ops tooling) can rely on when:

* the **bundle membership**,
* the **index.json schema**, or
* the **`_passed.flag` semantics**

change over time.

Given:

* `parameter_hash`,
* `manifest_fingerprint`,
* `seed`,
* `run_id`, and
* the versions of `validation_bundle_3A` / `_passed.flag` recorded in the catalogue,

consumers must be able to unambiguously interpret:

* **what artefacts the bundle covers**,
* **how** the bundle’s composite digest is computed, and
* **what** `_passed.flag` means for a given manifest.

S7 MUST evolve in a way that preserves **hash-verifiability** and **governance clarity** across versions.

---

### 12.1 Scope of change control

Change control for S7 covers:

1. The **shape and semantics** of S7 outputs:

   * `validation_bundle_3A` (specifically `index.json`),
   * `_passed.flag`.

2. The **membership rules**:

   * which artefacts (S0–S6, RNG digest artefacts, etc.) are included in the bundle index,
   * what each `role` means for those members.

3. The **composite digest algorithm**:

   * how per-artefact `sha256_hex` values are canonicalised and concatenated,
   * how `bundle_sha256_hex` is computed,
   * how `_passed.flag` encodes that digest.

4. S7’s **run-level error taxonomy** (`E3A_S7_*`) and how it is mapped into the segment-state run-report.

It does **not** govern:

* S0–S6 contracts (each has its own change control),
* how consumers choose to operationally enforce “no PASS → no read” (only that `_passed.flag` + `index.json` are the authoritative signals).

---

### 12.2 Versioning of S7 outputs

S7’s outputs are versioned via the dataset dictionary and artefact registry:

* `validation_bundle_3A.version` in `dataset_dictionary.layer1.3A.yaml` and `artefact_registry_3A.yaml`.
* `_passed.flag.version` in the same catalogue entries.

Additionally, S7 MAY record its own state-contract version (e.g. `"s7_version"`) inside the `metadata` object of `index.json`, but the **catalogue versions** are the authoritative contract markers.

#### Semver semantics

Versions use `MAJOR.MINOR.PATCH`:

* **PATCH** (`x.y.z → x.y.(z+1)`)

  * Documentation clarifications.

  * Implementation fixes that do **not** change:

    * which members appear in the bundle for a given manifest,
    * any per-artefact `sha256_hex`,
    * the composite digest definition or value,
    * the schema of `index.json` or `_passed.flag`.

  * Example: fixing a bug where S7 previously mis-handled an internal `size_bytes` field but corrected it without impacting digests or membership.

* **MINOR** (`x.y.z → x.(y+1).0`)

  * Backwards-compatible extensions, e.g.:

    * adding optional fields in `index.json.metadata` (e.g. `s7_version`, additional version tags),
    * adding optional per-member metadata (e.g. `notes`, `size_bytes`) that consumers may ignore,
    * refining error codes / metrics / logging without changing bundle content or digests.

  * Existing consumers that ignore new metadata remain correct; `bundle_sha256_hex` is unchanged for the same universe.

* **MAJOR** (`x.y.z → (x+1).0.0`)

  * Any change that can alter:

    * the **set of members** participating in the composite digest for a given manifest,
    * the **algorithm** for computing the composite digest, or
    * the **on-disk format** or semantics of `_passed.flag`.

  * These changes require coordinated updates across all consumers that rely on the bundle and flag.

---

### 12.3 Backwards-compatible changes (MINOR/PATCH)

The following changes are considered **backwards-compatible** if implemented as described:

1. **Adding optional metadata to `index.json`**

   * Extending the `metadata` object in `validation_bundle_index_3A` with new fields, e.g.:

     * `s7_version`,
     * upstream contract versions (`s1_version`, `s2_version`, …),
     * `created_at_utc`, etc.

   * Conditions:

     * New fields MUST be optional or have defaults.
     * They MUST NOT affect what goes into `members[]` or any `sha256_hex` values.
     * Composite `bundle_sha256_hex` MUST remain unchanged for the same artefact set.

2. **Adding optional per-member fields**

   * E.g. `size_bytes`, `notes` in `members[]`.

   * Conditions:

     * New fields MUST be optional and ignored by hash computation (i.e. they are not included in per-artefact digest precursors; they are metadata only).
     * JSON serialisation for digest purposes MUST still follow the canonical rules defined in the contract (e.g. only particular fields are included for digest, or per-artefact digest is purely over the underlying dataset, not `index.json`).

3. **Extending logging, run-report, metrics**

   * Adding new log fields, run-report summary fields, or metrics for S7 is backward compatible as long as:

     * they do not change the bundle content, membership, or digest semantics, and
     * S7’s `status` and `error_code` semantics remain the same.

4. **Stricter internal checks that do not change valid bundles**

   * Implementation changes that:

     * only convert previously invalid states into explicit S7 run-level FAILs, and
     * do not change what S7 produces for manifests that already satisfied the S7 contract.

These changes qualify as MINOR or PATCH depending on whether the observable schemas are extended (MINOR) or only S7 internals/logging are updated (PATCH).

---

### 12.4 Breaking changes (MAJOR)

The following are **breaking** for S7 and MUST trigger a **MAJOR** version bump for at least `validation_bundle_3A` and `_passed.flag`, plus coordinated consumer updates:

1. **Changing membership semantics**

   * Adding or removing artefacts that are considered required members of the bundle **and** whose digests participate in the composite `bundle_sha256_hex`.

     * Example: deciding that RNG logs or a new 3A artefact must now be included in `members[]` and in the composite digest.
     * For the same S0–S6 universe, this would change `bundle_sha256_hex` and therefore `_passed.flag`, which is a behavioural change for all consumers.

   * Changing the meaning of `role` values in ways that alter how consumers interpret which artefacts are “part of the validation proof” vs incidental.

2. **Changing the composite digest algorithm**

   * Altering:

     * the ordering key used for `members[]` (e.g. from `logical_id` to `path`), or
     * the concatenation method (e.g. introducing separators, changing from hex to binary), or
     * the hash function (e.g. from SHA-256 to SHA-512).

   * Any change that makes a recomputed digest from the same `index.json` appear different to existing consumers.

3. **Changing the logical form or on-disk format of `_passed.flag`**

   * Adding more fields to the flag file (e.g. `manifest_fingerprint = …`) in a way that breaks existing parsers.
   * Changing the line format from `sha256_hex = …` to some other structure.

   These changes require updated flag readers, and so are MAJOR.

4. **Moving or renaming the validation bundle or flag**

* Changing the dataset IDs (`validation_bundle_3A`, `validation_passed_flag_3A`), or
   * Changing their paths/partitioning (e.g. adding `seed=` partitions, moving them out of `validation_bundle/`), is a breaking change.

5. **Relaxing immutability semantics**

   * Permitting S7 to overwrite an existing bundle or flag with different content for the same `manifest_fingerprint` without changing the manifest identity would be a major governance change and MUST be treated as MAJOR (and is strongly discouraged).

Any such change MUST be coordinated with:

* orchestrator and cross-segment validators (which enforce HashGate),
* 2B or any other consumers that guard their reads with `_passed.flag`,
* and, if relevant, upstream governance of `manifest_fingerprint`.

---

### 12.5 Interaction with upstream contracts (S0–S6)

S7 depends on S0–S6; changes there can require S7 to evolve.

1. **Upstream breaking changes that affect bundle membership**

   * If any upstream contract introduces or removes artefacts that must be part of the 3A validation proof (e.g. a new S3 RNG digest artefact, or a new S6 summary artefact), S7’s membership set must change accordingly.

   * If those changes affect **which artefacts contribute to the composite digest**, this is a **MAJOR** change to S7.

2. **Upstream optional extensions**

   * New upstream artefacts that are purely optional and not required members of the bundle can be:

     * either ignored by S7, or
     * incorporated into `index.json` as **non-participating** members (e.g. metadata entries whose digests are not included in the composite) **only if** the contract clearly distinguishes “participating” from “non-participating” members in the digest.
   * Any change from “non-participating” to “participating” (digest-affecting) is MAJOR.

3. **S6 contract evolution**

   * If S6 changes in a way that affects:

     * how `s6_receipt_3A` is hashed (e.g. canonical JSON rules), or
     * whether S6 artefacts are required members of the bundle,

     S7 must be updated and versioned to remain consistent.

   * In general, S7 is a **consumer** of S6; S6 MAJOR changes may require S7 MINOR or MAJOR changes depending on impact on bundle contents/digests.

---

### 12.6 Catalogue evolution (schemas, dictionary, registry)

Any change to S7 entries in:

* `schemas.layer1.yaml#/validation/validation_bundle_index_3A`
* `schemas.layer1.yaml#/validation/passed_flag_3A`
* `dataset_dictionary.layer1.3A.yaml`
* `artefact_registry_3A.yaml`

must obey:

1. **Schema evolution**

   * Adding new optional fields (e.g. to `index.json.metadata` or per-member `notes/size_bytes`) is MINOR-compatible.
   * Removing fields or changing type/meaning of required fields (e.g. dropping `sha256_hex` or changing `members` from an array to a map) is MAJOR.

2. **Dictionary evolution**

   * Changing IDs, paths or partitioning definitions for `validation_bundle_3A` or `_passed.flag` is MAJOR.

3. **Registry evolution**

   * Adding new dependencies or notes is allowed.
   * Changing `manifest_key`s, `schema` references, or `path` formats is MAJOR.

---

### 12.7 Deprecation strategy

When evolving S7, the preferred strategy is:

1. **Introduce before removing**

   * Add new metadata fields or additional bundle members (as non-participating metadata) in a MINOR version, while keeping old semantics intact.

2. **Deprecate via documentation and fields**

   * Mark older behaviours (e.g. legacy member roles, older metadata fields) as deprecated in the spec and, if needed, in `index.json.metadata` (e.g. a `deprecated` section) for at least one release cycle.

3. **Remove or repurpose only with MAJOR bump**

   * When it is necessary to:

     * remove fields,
     * change membership semantics, or
     * change composite digest behaviour,

     a MAJOR version bump MUST be used, and all consumers must be updated accordingly.

Historic bundles MUST NOT be rewritten in place to conform to new contracts; they remain valid under the contract version with which they were produced.

---

### 12.8 Cross-version behaviour

Multiple S7 versions may co-exist across manifests in a long-lived system.

Consumers (e.g. orchestrators, validators, 2B) MUST:

* read the version of `validation_bundle_3A` / `_passed.flag` from the catalogue (and, optionally, from `index.json.metadata`),
* interpret:

  * membership,
  * digest semantics, and
  * the meaning of `_passed.flag`

in terms of the **appropriate S7 contract version**, and

* for cross-manifest analytics (e.g. “how many manifests have S7 bundles?”), either:

  * explicitly handle multiple S7 versions, or
  * restrict themselves to the intersection of semantics that is stable across the versions they include.

Under these rules, S7 can:

* evolve **safely** (adding metadata, strengthening checks) without destabilising consumers, and
* evolve **explicitly** (when membership or digest semantics change) so that nobody has to guess what a given `validation_bundle_3A` and `_passed.flag` pair means for a given manifest.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix records the notation and shorthand used in the 3A.S7 design. It has **no normative force**; it just keeps naming consistent with S0–S6 and the Layer-1 HashGate docs.

---

### 13.1 Identities & hashes

* **`parameter_hash`**
  Layer-1 hash over the governed parameter set 𝓟 (priors, mixture, floor policy, day-effect policy, etc.). Fixed before S0 and reused across S2/S3/S5/S6/S7.

* **`manifest_fingerprint`**
  Layer-1 manifest hash for a run. S7 is **manifest_fingerprint-scoped**: bundle and flag are keyed by this.

* **`seed`**
  Layer-1 RNG seed (`uint64`). S7 does not use RNG, but `seed` appears in run-report and as context for S1–S5.

* **`run_id`**
  Identifier for a particular execution of the pipeline (string or u128-encoded). Used to correlate S7’s run-report/logs with S3–S6.

* **`sha256_hex`**
  Generic term for a 64-character lowercase hex string representing a SHA-256 digest.

* **`bundle_sha256_hex`**
  The composite **3A bundle digest** computed by S7 from all member digests listed in `index.json`:

  [
  bundle_sha256_hex = \mathrm{SHA256}\big( sha256_hex(m_1) ,|, \dots ,|, sha256_hex(m_n) \big)
  ]

  where `m_1…m_n` are bundle members in canonical order and `∥` is byte concatenation of ASCII hex strings.

---

### 13.2 Bundle & flag artefacts

* **`validation_bundle_3A`**
  Fingerprint-scoped directory that holds:

  * `index.json` — the **bundle index** (member manifests + digests), and
  * 3A validation members (directly or via referenced paths), such as S0–S6 artefacts.

  Structured as:

  ```text
  data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/
    ├── index.json
    ├── _passed.flag
    └── (other referenced artefacts or symlinks, per implementation)
  ```

* **`index.json`**
  The bundle index file; a JSON object conforming to `validation_bundle_index_3A`, containing:

  * bundle-level metadata (`manifest_fingerprint`, `parameter_hash`, `s6_receipt_digest`, `metadata`, …)
  * `members[]` — list of member entries with:

    * `logical_id` — logical artefact ID (often a `manifest_key`),
    * `path` — concrete path to the artefact,
    * `schema_ref` — JSON-Schema anchor for the artefact,
    * `sha256_hex` — SHA-256 over canonical representation of the artefact,
    * `role` — semantic label (e.g. `"gate"`, `"priors"`, `"shares"`, `"counts"`, `"egress"`, `"validation_report"`, etc.).

* **`_passed.flag`**
  Fingerprint-scoped PASS flag for Segment 3A. On disk:

  ```text
  sha256_hex = <bundle_sha256_hex>
  ```

  where `<bundle_sha256_hex>` is the composite digest computed from `index.json`’s member digests.

  Logically represented as:

  ```json
  { "sha256_hex": "<64-lowercase-hex>" }
  ```

  and validated against `passed_flag_3A`.

---

### 13.3 Bundle member notation

For a given `manifest_fingerprint`:

* **`M`**
  The set of all artefacts that must appear as members of the 3A validation bundle, e.g.:

  [
  M = { s0_gate_receipt_3A, sealed_inputs_3A, s1_escalation_queue, s2_country_zone_priors, s3_zone_shares, s4_zone_counts, zone_alloc, zone_alloc_universe_hash, s6_validation_report_3A, s6_issue_table_3A, s6_receipt_3A, \dots }
  ]

  (plus any additional members defined by the contract/catalogue.)

* **`M_ord`**
  The **canonical ordered list** of bundle members:

  [
  M_{\text{ord}} = [m_1, m_2, \dots, m_n]
  ]

  where the order is determined by a fixed sort key (e.g. `logical_id` ASCII-lexicographic).

* **`sha256_hex(m)`**
  The per-artefact digest attached in `index.json` to member `m ∈ M`, computed over the artefact’s canonical representation (JSON → canonical serialisation, Parquet → concatenation of data files, etc.).

These notations underpin both the bundle index structure and the composite digest computation.

---

### 13.4 Artefact IDs & roles

* **`logical_id`**
  The identifier used for each bundle member in `index.json`. It is typically:

  * the `manifest_key` from the artefact registry (e.g. `"mlr.3A.s1_escalation_queue"`), or
  * a dataset ID that uniquely identifies the artefact.

* **`role`**
  A short string describing the member’s semantic role within the bundle, such as:

  * `"gate"` — S0 gate receipt,
  * `"sealed_inputs"` — S0 sealed inputs inventory,
  * `"domain"` — S1 domain/esc queue,
  * `"priors"` — S2 priors surface,
  * `"shares"` — S3 share surface,
  * `"counts"` — S4 zone counts,
  * `"egress"` — S5 zone allocation egress,
  * `"universe_hash"` — S5 universe hash artefact,
  * `"validation_report"` — S6 validation report,
  * `"validation_receipt"` — S6 receipt,
  * `"issues"` — S6 issue table.

These roles are for human and tooling clarity; the *contract* is that the list of members and their digests are complete and correct per the S7 spec and catalogue.

---

### 13.5 S6 linkage

S7 depends on S6’s artefacts and verdict:

* **`s6_validation_report_3A`**
  JSON report of checks and metrics for Segment 3A at `manifest_fingerprint`. S7 bundles this as part of the validation evidence.

* **`s6_issue_table_3A`**
  Per-issue table listing individual structural problems (may be empty if there are no issues). Bundled as optional but recommended detailed evidence.

* **`s6_receipt_3A`**
  Compact verdict object from S6 for this `manifest_fingerprint`:

  * `overall_status ∈ {"PASS","FAIL"}` — final structural verdict for 3A,
  * `check_status_map` — per-check statuses,
  * `validation_report_digest` (hash of the S6 report),
  * optional `issue_table_digest`.

  S7 uses `s6_receipt_3A.overall_status` as the gating condition and includes `s6_receipt_digest` (SHA-256 of the receipt) in `index.json`.

* **`s6_receipt_digest`**
  SHA-256 hex digest of the canonical serialisation of `s6_receipt_3A`, recorded in `index.json` so that a validator can check:

  * the receipt hasn’t changed since the bundle was built.

---

### 13.6 Error codes & statuses (S7 as a state)

* **`E3A_S7_001_S6_NOT_PASS`**
  S7 cannot proceed: S6 run failed, S6 receipt missing/invalid, or S6 `overall_status != "PASS"`.

* **`E3A_S7_002_PRECONDITION_MISSING_ARTEFACT`**
  Required S0–S6 artefact (bundle member) missing or schema-invalid.

* **`E3A_S7_003_INDEX_BUILD_FAILED`**
  S7 couldn’t construct a valid index (missing members, duplicate IDs, schema-invalid index, or identity mismatch).

* **`E3A_S7_004_DIGEST_MISMATCH`**
  Per-artefact digest mismatch between `index.json` (or an upstream digest) and recomputed value.

* **`E3A_S7_005_HASHGATE_MISMATCH`**
  Composite `bundle_sha256_hex` recomputed from `index.json` does not match `_passed.flag.sha256_hex`.

* **`E3A_S7_006_IMMUTABILITY_VIOLATION`**
  Existing index/flag differ from what S7 would produce now for the same `manifest_fingerprint` & inputs; S7 refuses to overwrite.

* **`E3A_S7_007_INFRASTRUCTURE_IO_ERROR`**
  S7 cannot complete due to non-logical I/O issues (storage/network/permissions).

These error codes are used on S7’s own run-report row; they **do not** represent 3A structural health (that is S6’s domain).

* **`status` (S7 state run status)**
  S7’s row in the segment-state run-report:

  * `"PASS"` — S7 successfully built/verified bundle + flag; `error_code=null`.
  * `"FAIL"` — S7 encountered one of the errors above.

* **`bundle_member_count`**
  Number of entries in `index.json.members[]` (reported in run-report/logs).

---

### 13.7 PASS semantics

A manifest `F` is considered **3A-validated and sealed** only when:

* `s6_receipt_3A@manifest_fingerprint=F` has `overall_status="PASS"`,
* S7 run for `(parameter_hash, F, seed, run_id)` has `status="PASS", error_code=null`,
* `validation_bundle_3A@manifest_fingerprint=F` and `_passed.flag@manifest_fingerprint=F` are present and a recomputation of `bundle_sha256_hex` from `index.json` matches the flag’s `sha256_hex`.

Consumers must enforce:

> **“No 3A PASS (bundle+flag+S6 receipt) ⇒ No read of 3A surfaces for that manifest.”**

This appendix simply names the moving parts so that all participants (S0–S7, 2B, orchestrators, validators) can talk about the same things without ambiguity.

---
