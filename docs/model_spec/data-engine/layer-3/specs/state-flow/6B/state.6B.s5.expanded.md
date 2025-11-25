# 6B.S5 — Segment validation & HashGate (Layer-3 / Segment 6B)

## 1. Purpose & scope *(Binding)*

6B.S5 is the **segment-level validation and HashGate state** for Layer-3 / Segment 6B.

For any sealed world identified by a `manifest_fingerprint`, S5 is the **final authority** that decides whether:

* the entire 6B segment (S0–S4) is structurally and behaviourally sound, and
* its outputs are safe to be consumed by downstream systems (4A/4B, model-training, evaluation).

S5 does **not** produce any new business data (no flows, no events, no labels). Instead, it:

1. **Re-validates the full 6B chain (S0–S4)**

   * checks that all required 6B datasets exist and conform to their schemas and identity rules;
   * verifies **coverage** and **consistency** across states (e.g. arrivals → entities → sessions → baseline flows → overlays → labels → cases);
   * verifies that **RNG usage** in S1–S4 matches the configured Layer-3 RNG policies and per-state budgets;
   * confirms that truth labels and bank-view labels (S4) are compatible with S3 overlays, S2 baseline, and 6A posture, according to the configured validation policy.

2. **Summarises validation results for the world**

   * aggregates all check results into a single **segment validation report** (`s5_validation_report_6B`), with per-check PASS/WARN/FAIL statuses and metrics;
   * optionally emits a structured **issue table** (`s5_issue_table_6B`) listing any anomalies or WARN/FAIL findings at finer granularity (per flow, per campaign, per case, etc.).

3. **Builds a 6B validation bundle**

   * assembles selected validation artefacts (S5 reports, references/digests of critical S0–S4 surfaces, RNG summaries, coverage metrics) into a **validation bundle directory** for the world (`validation_bundle_6B`), under
     `data/layer3/6B/validation/fingerprint={manifest_fingerprint}/`;
   * constructs an `index.json` for that bundle (`validation_bundle_index_6B`), listing each member file and its `sha256_hex` digest with a stable, ASCII-lexical path ordering.

4. **Publishes the 6B HashGate flag**

   * computes a deterministic SHA-256 digest over the bundle contents (using the paths and digests from `index.json` according to the agreed bundle law);
   * writes the **segment-level `_passed.flag_6B`** (`validation_passed_flag_6B`) containing that digest.

This `_passed.flag_6B` is the **HashGate for Segment 6B**:

> If the flag is present and its digest matches the recomputed bundle digest, the 6B segment is considered **sealed and PASS** for that world.
> If the flag is missing or invalid, the world MUST be treated as **not validated**, and 6B outputs MUST NOT be used.

### In-scope responsibilities

Within this specification, S5 is responsible for:

* **World-scoped validation of 6B**

  * S5 operates at `manifest_fingerprint` granularity, not per seed/scenario. It consolidates S0–S4 status and data across all seeds and scenarios that belong to the world.

* **Validation logic and policy enforcement**

  * Applying the configured `segment_validation_policy_6B` to decide which checks are required, which are allowed as WARN, and which are fatal FAIL.
  * Implementing checks over:

    * 6B schemas, PKs, partitioning, and path↔embed rules;
    * cross-state coverage (S1/S2/S3/S4) as described in the upstream specs;
    * behavioural consistency (campaigns vs overlay vs labels) at the level of metrics and structural invariants;
    * RNG accounting for S1–S4 versus Layer-3 RNG policies.

* **Bundle construction and HashGate derivation**

  * Building a **complete and self-describing** validation bundle for the world: any consumer (internal or external) can re-run the hashing recipe and reach the same digest if and only if the bundle is intact and unmodified.
  * Publishing `_passed.flag_6B` only when all required checks have passed under the validation policy.

### Out-of-scope responsibilities

S5 is explicitly **not** allowed to:

* **Modify S0–S4 data**

  * It MUST NOT change or rewrite any S0–S4 datasets (arrivals, entities, flows, overlays, labels, cases).
  * It MUST NOT attempt to “fix” or “autocorrect” upstream outputs; any detected issues are reported via validation report and issue tables, not silently patched.

* **Alter upstream HashGates**

  * It MUST NOT re-define or override the HashGate semantics for Layer-1, Layer-2 or 6A.
  * It may re-verify upstream HashGates as part of its checks, but upstream `_passed.flag_*` artefacts remain authoritative for their respective layers/segments.

* **Introduce new behavioural or labelling logic**

  * It MUST NOT introduce new fraud campaigns, flows, events, or labels.
  * Any behavioural or label consistency checks are implemented as **tests**, not as generators.

* **Serve as a consumer-facing view by itself**

  * The validation bundle and flag are **control-plane artefacts**. Data-plane consumption is done via S1–S4 datasets; S5 does not expose new business-level tables.

### Relationship to the rest of the engine

Within the engine:

* **Upstream:**

  * S0–S4 have already produced all 6B data-plane outputs (behavioural surfaces, overlays, labels, cases) and recorded their statuses.
  * Upstream layers (1A–3B, 5A, 5B, 6A) have sealed their own worlds behind their HashGates.

* **S5:**

  * Is the **last** state in Segment 6B.
  * Treats all of 6B’s own outputs plus upstream HashGates as inputs to a world-level validation harness.
  * Produces `validation_bundle_6B` and `validation_passed_flag_6B` as the final decision about the world’s validity at Layer-3.

* **Downstream:**

  * Orchestrators, 4A/4B, model-training and evaluation pipelines MUST treat `_passed.flag_6B` as the **single, machine-checkable gate** determining whether 6B outputs are safe to read for that `manifest_fingerprint`.
  * Any world lacking a valid `_passed.flag_6B` MUST be considered **not validated**, and 6B outputs MUST NOT be consumed as authoritative.

If S5 is implemented according to this specification, then for each world:

* there is a clear, reproducible, cryptographically sealed record of all 6B validation work; and
* every downstream consumer can cheaply and reliably decide whether the 6B segment is **PASS** or **not safe to read** for that world, without re-running validation.

---

## 2. Preconditions & upstream gates *(Binding)*

This section defines **what must already be true** before 6B.S5 is allowed to run, and which upstream gates it **MUST** honour.

S5 is **world-scoped**: it is evaluated per `manifest_fingerprint`. It does *not* operate per seed or scenario directly, but it aggregates results across all `(seed, scenario_id)` partitions that belong to the world.

If any precondition here is not satisfied for a given `manifest_fingerprint`, S5 **MUST NOT** attempt to validate or seal Segment 6B for that world and **MUST** fail fast with an appropriate precondition error.

---

### 2.1 World selection & invocation scope

S5 is invoked for a specific world:

* A concrete `manifest_fingerprint` has been chosen, corresponding to a sealed world across Layers 1–3.
* The orchestration layer has completed all scheduled Segment 6B data-plane work for that world (S0–S4) for the configured set of `(seed, scenario_id)` partitions.

Binding rules:

* S5 MUST NOT be used as a “live pre-check” against a world that is still being computed (i.e. S1–S4 are still running or have not all recorded a status for their assigned `(seed, scenario_id)` partitions).
* S5 MAY be re-run idempotently for the same world, but only after the same or a strictly greater 6B workload has completed (see identity/idempotence later).

---

### 2.2 S0 gate & `sealed_inputs_6B` MUST exist and be valid

Before doing any segment-level validation, S5 MUST confirm that the **6B entry gate** has itself run correctly.

Concretely, for the target `manifest_fingerprint`, S5 MUST:

1. Locate `s0_gate_receipt_6B` using `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml`.

2. Validate it against `schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B`. This includes:

   * Required fields present (`manifest_fingerprint`, `parameter_hash`, `spec_version_6B`, `upstream_segments`, `contracts_6B`, `sealed_inputs_digest_6B`, etc.).
   * Embedded `manifest_fingerprint` equals the fingerprint path token.

3. Locate and load `sealed_inputs_6B` for this fingerprint using the paths and schema_ref recorded in S0 and the dictionary.

4. Validate `sealed_inputs_6B` against `schemas.layer3.yaml#/gate/6B/sealed_inputs_6B` and confirm that its content digest matches `sealed_inputs_digest_6B` in the gate receipt.

If any of the above fails (missing S0 outputs, schema violations, digest mismatch), S5 MUST:

* treat this as a **precondition failure**, and
* not proceed to any S1–S4 or bundle-level checks for this world.

S5 MUST NOT attempt to reconstruct or “patch” `sealed_inputs_6B` itself.

---

### 2.3 Upstream HashGates for Layers 1–2 & 6A MUST be present and verifiable

Segment 6B rests on sealed worlds in Layers 1–2 and 6A. For a given `manifest_fingerprint`, S5 MUST:

1. For each required upstream segment:

   * Layer-1: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
   * Layer-2: `5A`, `5B`
   * Layer-3: `6A`

   use the owning dictionaries/registries + `sealed_inputs_6B` to locate:

   * the `validation_bundle_*` directory for that segment at `fingerprint={manifest_fingerprint}`,
   * the corresponding `_passed.flag_*` artefact.

2. Re-validate each upstream HashGate according to that segment’s own spec:

   * Validate the upstream index (`index.json`) against the segment’s validation schema.
   * Confirm that all files listed exist and their checksums match the index.
   * Recompute the segment’s bundle digest using its documented hashing law.
   * Confirm that the digest recorded in `_passed.flag_*` equals the recomputed digest.

3. Reconcile these results with `s0_gate_receipt_6B.upstream_segments[*].status` and recorded digests.

Binding rules:

* If any required upstream segment’s validation bundle or `_passed.flag_*` is **missing**, malformed, or fails digest verification, S5 **MUST** treat this as a precondition failure (`S5_PRECONDITION_S0_OR_UPSTREAM_FAILED`) and MUST NOT consider the world valid for 6B.
* If S0 has recorded a non-PASS status for any required upstream segment, S5 MAY reproduce that as a stricter fail but MUST NOT override it as PASS.

S5 is allowed to *re-verify* upstream HashGates, but those HashGates remain the schema of record for their layers.

---

### 2.4 Segment 6B workloads (S1–S4) MUST be complete & reported

S5 validates the **entire** 6B segment; it needs a full picture of S1–S4’s work for the world.

For the target `manifest_fingerprint`, S5 MUST:

1. Determine the intended set of `(seed, scenario_id)` partitions that are “in scope” for this world. This can be derived from:

   * `sealed_inputs_6B` (e.g. all partitions where `s2_flow_anchor_baseline_6B` or `s3_flow_anchor_with_fraud_6B` exist), and/or
   * 6B configuration (scenario set, seeds set).

2. For every such `(seed, scenario_id)` pair, confirm that the Layer-3 run-report contains entries for:

   * `segment="6B", state="S1"` (S1 PASS/FAIL)
   * `segment="6B", state="S2"` (S2 PASS/FAIL)
   * `segment="6B", state="S3_overlay"` (S3 overlay PASS/FAIL)
   * `segment="6B", state="S4_labels"` (flow/event labels PASS/FAIL)

3. For the case-level scope `(seed, fingerprint)`, confirm that a `segment="6B", state="S4_cases"` run-report entry exists for each seed for which S4 is expected to produce case timelines.

Precondition vs validation:

* For **preconditions**, S5 only requires that these statuses **exist** (i.e. all work is finished and recorded). It does **not** require that S1–S4 are PASS; S5 will incorporate FAIL statuses into its own world verdict.
* If any expected S1–S4 run-report entry is missing (segment hasn’t run or hasn’t recorded status), S5 MUST treat this as a precondition failure for the world: the 6B workload is incomplete.

---

### 2.5 Presence of all critical 6B datasets (S1–S4)

Beyond the run-report status, S5 MUST be able to locate and read all **critical 6B datasets** identified in the 6B spec and `sealed_inputs_6B`:

* S1: `s1_arrival_entities_6B`, `s1_session_index_6B`
* S2: `s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`
* S3: `s3_campaign_catalogue_6B`, `s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`
* S4: `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`, `s4_event_labels_6B`, `s4_case_timeline_6B`

Binding rules:

* All of these datasets MUST appear in `sealed_inputs_6B` with appropriate `status` and `read_scope` (`ROW_LEVEL` or `METADATA_ONLY` as required by S5’s validation policy).
* For each such dataset, S5 MUST be able to:

  * resolve its `path_template` and `partition_keys`,
  * construct the expected paths for this world (and seeds/scenarios where applicable),
  * confirm that these paths exist (unless the spec explicitly allows empty/missing partitions in certain scenarios and the dictionary/validation policy encode that).

If any **required** 6B dataset is completely missing or unrecoverable (e.g. data not present in storage when dictionary and `sealed_inputs_6B` claim it should be), S5 MUST treat this as a **precondition failure** for the world (`S5_PRECONDITION_SEALED_INPUTS_INCOMPLETE`) and SHOULD NOT attempt partial validation.

---

### 2.6 Segment validation policy & RNG policy (S5) MUST be present

S5’s behaviour is governed by its own validation policy and (optionally) RNG policy artefacts, which MUST be present and valid before S5 can run:

* `segment_validation_policy_6B`

  * Defines the list of checks (by id), their severity (PASS/WARN/FAIL), thresholds for numerical metrics, and what counts as an overall PASS for the world.

* `segment_validation_rng_policy_6B` (if any)

  * Defines whether S5 uses RNG at all (typical default: S5 is RNG-free), and if so, which RNG families, budgets, and key definitions are used for S5’s own sampling checks.

Binding rules:

* S5 MUST locate these artefacts via `sealed_inputs_6B` and validate them against their `schema_ref`.
* If `segment_validation_policy_6B` is missing or schema-invalid, S5 MUST fail preconditions and MUST NOT attempt to “guess” validation behaviour.
* If S5 is configured to be RNG-free (recommended), then any RNG policy is either absent or trivial; if non-trivial RNG policy is present but inconsistent with the Layer-3 RNG spec, S5 MUST not proceed.

---

### 2.7 Prohibited partial / speculative invocations

S5 MUST NOT be invoked in any of the following situations:

* S0 has not run or is not recorded as PASS for the target `manifest_fingerprint`.
* Upstream HashGates (any of `1A–3B`, `5A`, `5B`, `6A`) are missing or fail verification for this fingerprint.
* The 6B workload is incomplete: any expected S1–S4 run-report entry for the world’s `(seed, scenario_id)` set is missing.
* Required 6B datasets or S5 config artefacts are missing from `sealed_inputs_6B` or fail schema validation.
* Orchestration wants a “partial S5” that only validates some subset of S1–S4 (e.g. S1–S2 only) without marking the world as final.

If any of these conditions hold, **the correct behaviour is**:

* S5 MUST fail early for that `manifest_fingerprint` with an appropriate precondition error (e.g. `S5_PRECONDITION_S0_OR_UPSTREAM_FAILED` or `S5_PRECONDITION_SEALED_INPUTS_INCOMPLETE`), and
* MUST NOT write any S5 outputs (`s5_validation_report_6B`, `s5_issue_table_6B`, `validation_bundle_6B`, or `validation_passed_flag_6B`) for that world.

These preconditions are **binding**. Any conformant implementation of 6B.S5 MUST enforce them before performing validation, building the bundle, or writing the 6B HashGate flag.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **exactly what 6B.S5 may read** and what each input is the **authority for**. Anything outside these boundaries is out of scope for S5 and **MUST NOT** be touched.

S5 is a **validation & sealing** state:

* It reads 6B control-plane + data-plane artefacts and upstream HashGates.
* It reads validation/RNG policies.
* It produces only **validation reports, a bundle index, and `_passed.flag_6B`**.
* It MUST NOT mutate any S0–S4 or upstream datasets.

---

### 3.1 Engine parameters (implicit inputs)

S5 is invoked per world:

* `manifest_fingerprint` — sealed world snapshot identifier.
* `parameter_hash` — 6B configuration pack hash, as recorded in `s0_gate_receipt_6B`.
* `spec_version_6B` — version of the 6B segment contract, also recorded in S0.

These values are given by orchestration and/or derived from `s0_gate_receipt_6B`. S5 **MUST NOT**:

* infer them from wall-clock or environment, or
* change them.

---

### 3.2 Schema packs & catalogue metadata

S5 relies on the engine’s schema packs and catalogues as the top of the authority stack:

1. **Schema packs (authoritative shapes)**

   * `schemas.layer1.yaml`, `schemas.layer2.yaml`, `schemas.layer3.yaml`
   * `schemas.1A.yaml`, …, `schemas.5B.yaml`, `schemas.6A.yaml`, `schemas.6B.yaml`

   These are the **only authoritative definitions** of:

   * tables/objects S5 validates (`s0_gate_receipt_6B`, `sealed_inputs_6B`, S1–S4 datasets, S5 outputs),
   * upstream validation bundles/index/flags,
   * Layer-3 RNG envelope and validation schema definitions.

   S5 MUST:

   * validate any artefact it inspects against its declared `schema_ref`, and
   * treat any schema violation, where encountered, as a structural validation failure.

2. **Dataset dictionaries**

   * `dataset_dictionary.layer1.*.yaml` for 1A–3B;
   * `dataset_dictionary.layer2.*.yaml` for 5A & 5B;
   * `dataset_dictionary.layer3.6A.yaml`, `dataset_dictionary.layer3.6B.yaml`.

   These are authoritative for:

   * dataset ids,
   * `path`/`path_template` and `partitioning`,
   * `schema_ref`,
   * primary keys and ordering.

   S5 MUST use dictionaries to:

   * locate all S1–S4 datasets,
   * derive expected partition layouts per `manifest_fingerprint`/`seed`/`scenario_id`.

3. **Artefact registries**

   * `artefact_registry_1A.yaml`, …, `artefact_registry_3B.yaml`, `artefact_registry_5A.yaml`, `artefact_registry_5B.yaml`,
   * `artefact_registry_6A.yaml`, `artefact_registry_6B.yaml`.

   These are authoritative for:

   * realised artefacts (datasets, bundles, flags),
   * whether an artefact is `validation_bundle`, `passed_flag`, `final_in_layer`, `cross_layer`, etc.,
   * low-level paths and environment (e.g. storage location).

   S5 MUST use registries in conjunction with dictionaries and `sealed_inputs_6B` to resolve concrete artefact locations; it MUST NOT guess paths.

---

### 3.3 S0 gate & `sealed_inputs_6B` (6B input universe)

S5 treats S0 artefacts as **control-plane authority** for Segment 6B:

1. **`s0_gate_receipt_6B`**

   Authority for:

   * which upstream segments (1A–3B, 5A, 5B, 6A) are PASS/MISSING/FAIL for this fingerprint,
   * which schema/dictionary/registry versions and config packs are bound to this world,
   * the digest of `sealed_inputs_6B`.

   S5 MUST:

   * trust `upstream_segments[*].status` as S0’s recorded view,
   * use it as the reference when re-verifying upstream HashGates,
   * use `contracts_6B` entries to confirm S4/S5 schema/registry versions.

2. **`sealed_inputs_6B`**

   Authority for:

   * the **complete and exclusive list of artefacts** that 6B is allowed to read for this fingerprint,
   * their `owner_layer`, `owner_segment`, `manifest_key`, `path_template`, `partition_keys`, `schema_ref`, `role`, `status`, `read_scope`, `sha256_hex`.

   S5 MUST:

   * treat `sealed_inputs_6B` as the only inventory for 6B-level validation;
   * resolve all S1–S4 dataset paths, all 6B configs, and any RNG logs used in validation via this manifest;
   * NEVER read artefacts that are not listed in `sealed_inputs_6B`;
   * respect `read_scope` (e.g. treat artefacts marked `METADATA_ONLY` as such; do not scan rows where forbidden).

S5 MUST NOT attempt to reconstruct a new sealed-inputs manifest; it validates and uses the one produced by S0.

---

### 3.4 Upstream HashGates & validation bundles

S5 uses upstream HashGate artefacts as **precondition evidence**, not as mutable inputs:

* For each required upstream segment `{1A,1B,2A,2B,3A,3B,5A,5B,6A}`, S5 may read:

  * the segment’s `validation_bundle_*` directory for this fingerprint, including its `index.json` and any RNG/validation summaries;
  * the segment’s `_passed.flag_*`.

Authority:

* These artefacts are the **only source of truth** for whether upstream worlds are sealed at their own layers.
* S5 may re-check consistency (index vs files vs flag) but MUST NOT:

  * alter upstream bundles,
  * rewrite or remove upstream flags,
  * override their PASS/FAIL semantics.

S5’s role is to **depend on** these HashGates, not to redefine them.

---

### 3.5 6B data-plane inputs (S1–S4 outputs)

For validation, S5 is allowed to read the 6B data-plane outputs listed below. These MUST all appear in `sealed_inputs_6B` with `owner_layer=3`, appropriate `owner_segment`, and a `status`/`read_scope` that meets S5’s needs (typically `ROW_LEVEL` for at least some checks):

* **S1 (arrival → entity → session)**

  * `s1_arrival_entities_6B`
  * `s1_session_index_6B`

  Authority for:

  * “who + session” mapping of arrivals to entities and sessions;
  * coverage of arrivals by entities/sessions.

* **S2 (baseline flows & events)**

  * `s2_flow_anchor_baseline_6B`
  * `s2_event_stream_baseline_6B`

  Authority for:

  * baseline (all-legit) flow/event structure per session;
  * baseline counts for coverage comparisons against S3/S4.

* **S3 (campaign catalogue & overlays)**

  * `s3_campaign_catalogue_6B`
  * `s3_flow_anchor_with_fraud_6B`
  * `s3_event_stream_with_fraud_6B`

  Authority for:

  * what campaigns were actually realised,
  * how baseline flows/events were overlaid and mutated,
  * coverage and identity between baseline and overlay flows/events.

* **S4 (truth & bank-view labels, case timelines)**

  * `s4_flow_truth_labels_6B`
  * `s4_flow_bank_view_6B`
  * `s4_event_labels_6B`
  * `s4_case_timeline_6B`

  Authority for:

  * final truth classifications and subtypes,
  * bank-view outcomes and lifecycle,
  * event-level flags (truth and bank-view event roles),
  * case identity and case event timelines.

S5 MUST treat all S1–S4 datasets as **read-only facts**. It may:

* read them at row level to compute coverage/consistency metrics,
* sample from them if an optimisation is allowed by validation policy,

but it MUST NOT:

* modify, delete, or rewrite S1–S4 outputs,
* change their identity/partitioning/ordering.

---

### 3.6 Upstream context: 6A, RNG logs & run-report

S5 may use some upstream artefacts and metadata as **context** for validation:

1. **6A entity & posture surfaces**

   * Base tables: `s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`, `s4_device_base_6A`, `s4_ip_base_6A`.
   * Posture tables: `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_merchant_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A`.

   Authority for:

   * entity existence and static fraud/role context.

   S5 uses them to:

   * check that S1–S4 respect entity identity and posture invariants.

2. **RNG logs & accounting surfaces**

   * Layer-3 RNG logs (e.g. `rng_event_*` logs and `rng_trace_log` / `rng_audit_log` surfaces) for S1–S4, as registered in their dictionaries and listed in `sealed_inputs_6B`.

   Authority for:

   * per-family RNG event counts and draw budgets,
   * monotonicity and coverage of RNG counters.

   S5 MUST NOT modify these logs; it only uses them to validate S1–S4 RNG usage against Layer-3 RNG policy.

3. **Run-report / control-plane metadata**

   * S5 may read the Layer-3 run-report sections for S1–S4 and S0, which record `status`, `primary_error_code`, and summary metrics per `(seed, scenario_id)`.

   Authority:

   * run-report entries are **not** a substitute for data-plane validation, but they:

     * provide S5 with a quick view of which partitions already report FAIL,
     * are used to cross-check that all intended partitions have been processed.

   S5 MUST NOT treat run-report alone as sufficient; it MUST verify S1–S4 surfaces directly where the validation policy requires.

---

### 3.7 S5 configuration & policy inputs

S5’s behaviour is governed by its own config/policy packs. These MUST be listed in `sealed_inputs_6B` with appropriate roles and `status="REQUIRED"`:

1. **Segment validation policy** (e.g. `segment_validation_policy_6B`)

   Role: `validation_policy`.
   Authority for:

   * which checks S5 MUST run (and at what granularity),
   * whether a check is `REQUIRED` (FAIL if violated), `WARN_ONLY`, or `INFO`,
   * numeric thresholds (e.g. acceptable bounds for fraud detection rate, campaign intensity).

2. **Segment validation RNG policy** (optional)

   Role: `rng_policy`.
   Authority for:

   * whether S5 itself uses RNG (typical design: S5 is RNG-free),
   * if so, which RNG families and budgets apply.

In this spec, S5 is intended to be **RNG-free**; if an RNG policy exists, it SHOULD be trivial. S5 MUST NOT use Philox for its own validation logic unless explicitly allowed and described in this policy.

---

### 3.8 Authority stack & prohibitions

S5’s authority stack, from highest to lowest, is:

1. **Schema packs** (`schemas.*.yaml`) — define shapes and types.
2. **Dataset dictionaries & artefact registries** — define dataset ids, paths, partitioning.
3. **Upstream HashGates** (1A–3B, 5A, 5B, 6A) — define whether upstream worlds are sealed.
4. **S0 gate & sealed_inputs_6B** — define 6B’s allowed inputs and contracts.
5. **S1–S4 specs + outputs** — define what 6B has produced.
6. **S5 spec + `segment_validation_policy_6B`** — define which checks S5 runs and how it decides PASS vs FAIL.

Binding prohibitions:

* S5 MUST NOT:

  * mutate any dataset from S0–S4 or upstream layers;
  * read artefacts not registered in `sealed_inputs_6B`;
  * ignore `read_scope` constraints;
  * reinterpret or weaken upstream HashGates (it may re-verify, not override);
  * reinterpret schemas or partitioning rules outside the declared contracts.

* S5 MAY:

  * re-run upstream HashGate verifications for sanity,
  * compute additional digests/metrics for 6B-specific validation.

But S5’s outputs are **purely validation artefacts**; the truth about behaviour and labels remains with S1–S4 and upstream layers.

---

## 4. Outputs (datasets & artefacts) & identity *(Binding)*

6B.S5 produces **only validation & sealing artefacts**. It does **not** emit business data (no flows/events/labels). Its outputs are:

1. `s5_validation_report_6B` — a world-scoped **summary report** of all 6B validation checks.
2. `s5_issue_table_6B` — an optional **detailed issue table** of non-PASS findings.
3. `validation_bundle_6B` — a **directory** containing all selected 6B validation artefacts for the world, plus an `index.json`.
4. `validation_passed_flag_6B` (`_passed.flag_6B`) — the **HashGate flag** for Segment 6B.

All S5 outputs are **fingerprint-scoped**:

* They are partitioned only by `manifest_fingerprint` (exposed as `fingerprint={manifest_fingerprint}` in paths).
* They do **not** partition by `seed`, `scenario_id`, or `run_id`.

No other datasets or artefacts may be written by S5.

---

### 4.1 `s5_validation_report_6B` — world-level validation summary

**Dataset id**

* `id: s5_validation_report_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

A single JSON document per `manifest_fingerprint` that summarises:

* the **overall validation verdict** for Segment 6B on this world (e.g. `overall_status: "PASS"|"WARN"|"FAIL"`),
* the list of **checks executed** (by check id), each with:

  * check type (structural, coverage, behavioural, RNG, bundle),
  * severity (`REQUIRED`, `WARN_ONLY`, `INFO`),
  * result (`PASS`, `WARN`, `FAIL`),
  * key metrics (e.g. coverage ratios, fraud detection rate) and thresholds,
* the set of S0–S4 states and whether they were treated as PASS/WARN/FAIL in S5.

This is the **primary human- and machine-readable summary** of 6B validation for the world.

**Format, path & partitioning**

Registered in the 6B dictionary/registry as:

* `version: '{manifest_fingerprint}'`

* `format: json`

* `path` (template):

  ```text
  data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6B.json
  ```

* `partitioning: [fingerprint]`

The embedded `manifest_fingerprint` field in the JSON MUST equal the `fingerprint` partition token.

**Primary key & identity**

Logical PK is:

```text
[manifest_fingerprint]
```

There MUST be at most one report per `manifest_fingerprint` per `spec_version_6B`.

If the dictionary supports explicit `primary_key`, it MUST be `[manifest_fingerprint]`.

**Lineage**

* `produced_by: [ '6B.S5' ]`
* `consumed_by: [ '6B.S5_bundle', '4A', '4B', 'ops_tooling' ]`

In the artefact registry:

* `manifest_key: s5_validation_report_6B`
* `type: dataset`
* `category: validation`
* `final_in_layer: true`

---

### 4.2 `s5_issue_table_6B` — detailed issues (optional but recommended)

**Dataset id**

* `id: s5_issue_table_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

A tabular dataset listing **individual issues** found during validation, each row capturing:

* which check (`check_id`) raised the issue,
* scope (world vs a particular `(seed, scenario_id)` or specific flow/case),
* severity (WARN/FAIL),
* identifiers (`seed`, `scenario_id`, `flow_id`, `case_id`, etc. as applicable),
* message and metrics.

This table is **supporting evidence** for `s5_validation_report_6B`: it allows operators and S5 tooling to inspect problems at granular resolution.

**Format, path & partitioning**

Registered as:

* `version: '{manifest_fingerprint}'`

* `format: parquet`

* `path` (template):

  ```text
  data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6B.parquet
  ```

* `partitioning: [fingerprint]`

Embedded `manifest_fingerprint` MUST match the partition token.

**Primary key & identity**

The exact PK is implementation-dependent, but MUST be stable and unique per issue record, e.g.:

```text
[manifest_fingerprint, check_id, issue_id]
```

Where:

* `check_id` is a string/enum defined in the validation policy.
* `issue_id` is a per-check unique identifier for the issue row.

**Lineage**

In the 6B dictionary:

* `status: optional` (recommended)
* `produced_by: [ '6B.S5' ]`
* `consumed_by: [ '6B.S5_bundle', 'ops_tooling' ]`

In the registry:

* `manifest_key: s5_issue_table_6B`
* `type: dataset`
* `category: validation`
* `final_in_layer: true`

---

### 4.3 `validation_bundle_6B` — world-scoped validation bundle

**Logical id**

* `id: validation_bundle_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

A **directory of validation artefacts** for Segment 6B at this `manifest_fingerprint`, including at least:

* `s5_validation_report_6B.json`
* `s5_issue_table_6B.parquet` (if present)
* `index.json` (the `validation_bundle_index_6B` file)
* Any additional evidence files specified in `segment_validation_policy_6B` (e.g. RNG summaries, coverage metrics, per-state digests).

This bundle is the **payload** over which the HashGate digest is computed.

**Layout & path**

Registered as:

* `version: '{manifest_fingerprint}'`

* `format: directory` (logical dataset)

* `path` (template):

  ```text
  data/layer3/6B/validation/fingerprint={manifest_fingerprint}/
  ```

* `partitioning: [fingerprint]`

Within that directory, S5 owns the layout of validation artefacts. It MUST at least produce:

* `index.json` (the index; see next subsection)
* `_passed.flag_6B` (HashGate flag; see §4.4)

Other filenames and subdirectories are allowed as long as they are clearly described in the index and follow the hashing law.

**Index: `validation_bundle_index_6B`**

The index is a JSON file within the bundle directory:

* file name (binding):

  ```text
  data/layer3/6B/validation/fingerprint={manifest_fingerprint}/index.json
  ```

* Schema anchor (for §5), e.g.:

  ```text
  schemas.layer3.yaml#/validation/6B/validation_bundle_index_6B
  ```

Minimum index structure:

* `manifest_fingerprint: string`
* `spec_version_6B: string`
* `parameter_hash: string`
* `items: [ { path: string, sha256_hex: string, role: string, [schema_ref: string] } ]`

Binding rules:

* `path` values MUST be:

  * relative to the bundle root (no leading `/`),
  * free of `..` segments,
  * ASCII-lexically sortable.

* The `items` array MUST:

  * list each file included in the bundle **exactly once**,
  * be sorted by `path` in ASCII-lex order,
  * NOT include `_passed.flag_6B`.

S5 MUST use this index to compute the bundle digest (see §6 later): concatenate files in `items` order, hash with SHA-256.

**Lineage**

In the dictionary:

* `status: required`
* `produced_by: [ '6B.S5' ]`
* `consumed_by: [ 'downstream_gate_checkers' ]`

In the registry:

* `manifest_key: validation_bundle_6B`
* `type: directory`
* `category: validation`
* `final_in_layer: true`
* `cross_layer: true` (since downstream layers will use it to gate consumption).

---

### 4.4 `validation_passed_flag_6B` — HashGate flag

**Artefact id**

* `id: validation_passed_flag_6B` (aka `_passed.flag_6B`)
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

A small text artefact that encodes the **HashGate digest** over the `validation_bundle_6B` contents for this world. It is the **sole gating artefact** for Segment 6B:

> A downstream consumer MUST recompute the bundle digest from `index.json` and confirm it matches `_passed.flag_6B` before treating any 6B outputs as valid for this `manifest_fingerprint`.

**Format, path & identity**

Registered as:

* `version: '{manifest_fingerprint}'`

* `format: text`

* `path`:

  ```text
  data/layer3/6B/validation/fingerprint={manifest_fingerprint}/_passed.flag_6B
  ```

* `partitioning: [fingerprint]`

Contents (binding):

* Single line, UTF-8 text, of the form:

  ```text
  sha256_hex = <64-lowercase-hex-digest>
  ```

* `<digest>` MUST be the SHA-256 of the concatenation of the raw bytes of all files listed in `validation_bundle_index_6B.items`, in ASCII-lex `path` order, and MUST NOT include `_passed.flag_6B` itself.

Primary key is logically `[manifest_fingerprint]`; there MUST be at most one `_passed.flag_6B` per world/spec version.

**Lineage**

In dictionary:

* `status: required`
* `produced_by: [ '6B.S5' ]`
* `consumed_by: [ 'downstream_gate_checkers', '4A', '4B', 'model_training' ]`

In registry:

* `manifest_key: validation_passed_flag_6B`
* `type: file`
* `category: HashGate`
* `final_in_layer: true`
* `cross_layer: true`

---

### 4.5 Relationship & identity consistency

The S5 outputs have the following identity relationships:

* All S5 artefacts are **fingerprint-only**:

  * They do not vary by `seed` or `scenario_id` (though they may *summarise* those dimensions).
  * They apply to the entire 6B workload for the world.

* The presence of `_passed.flag_6B` with a digest matching recomputation from `index.json` is the **single, world-level PASS signal** for Segment 6B.

* The absence of `_passed.flag_6B`, or a mismatch between its digest and the recomputed bundle digest, MUST be treated as “no PASS → no read” for 6B outputs.

This section fixes *what* S5 writes and *how* those artefacts are keyed and placed in storage. Subsequent sections define how they are populated (algorithm), how re-runs and merges behave (idempotence), and how downstream systems must use them.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes the **logical shapes**, **schema anchors**, and **catalogue wiring** for the S5 artefacts:

* `s5_validation_report_6B`
* `s5_issue_table_6B`
* `validation_bundle_6B` (specifically its `index.json`)
* `validation_passed_flag_6B` (`_passed.flag_6B`)

JSON-Schema remains the **single source of truth** for shapes. The Layer-3 dataset dictionary and artefact registry **MUST** match those schemas; if they diverge, schemas win and the catalogue MUST be corrected.

---

### 5.1 Schema anchors in `schemas.layer3.yaml` (or `schemas.6B.yaml`)

The Layer-3 schema pack **MUST** define the following anchors for S5:

* Validation report:

```text
schemas.layer3.yaml#/validation/6B/s5_validation_report
```

* Issue table:

```text
schemas.layer3.yaml#/validation/6B/validation_issue_table_6B
```

* Bundle index:

```text
schemas.layer3.yaml#/validation/6B/validation_bundle_index_6B
```

* Passed flag:

```text
schemas.layer3.yaml#/validation/6B/passed_flag_6B
```

These anchors are binding:

* `dataset_dictionary.layer3.6B.yaml` **MUST** use them as `schema_ref` for `s5_validation_report_6B`, `s5_issue_table_6B`, `validation_bundle_6B` (index), and `validation_passed_flag_6B` (flag).
* `artefact_registry_6B.yaml` **MUST** point its `schema` fields at the same anchors for their respective artefacts.

---

### 5.2 `s5_validation_report_6B` shape & catalogue links

#### 5.2.1 Row model

`schemas.layer3.yaml#/validation/6B/s5_validation_report` **MUST** define a single-object JSON schema (one file per world), with at least:

* Identity:

  * `manifest_fingerprint: string`
  * `parameter_hash: string`
  * `spec_version_6B: string`

* Overall verdict:

  * `overall_status: string`

    * Enum (e.g.): `"PASS"`, `"WARN"`, `"FAIL"`.

* Summary of upstream & S0–S4:

  * `upstream_segments: object`

    * Map `segment_id → { status, bundle_sha256, flag_path }`.
  * `segment_states: object`

    * Map for S0–S4 level states and their aggregate statuses (e.g. `S1: PASS`, `S3_overlay: WARN`).

* Check list:

  * `checks: array` of objects with at least:

    * `check_id: string` (e.g. `CHK_S3_CAMPAIGN_COVERAGE`).
    * `severity: string` (`"REQUIRED"`, `"WARN_ONLY"`, `"INFO"`).
    * `result: string` (`"PASS"`, `"WARN"`, `"FAIL"`).
    * `metrics: object` (check-specific key/value metrics).
    * `thresholds: object` (check-specific expected bounds; optional).

Optional fields MAY include `generated_at_utc`, tool version, or extra metadata, but MUST be optional.

#### 5.2.2 Dictionary entry

`dataset_dictionary.layer3.6B.yaml` **MUST** include:

```yaml
- id: s5_validation_report_6B
  status: required
  owner_layer: 3
  owner_segment: 6B
  description: >
    Segment 6B world-level validation report; one JSON document summarising
    all S0–S4 checks, metrics, and the overall verdict.
  version: '{manifest_fingerprint}'
  format: json
  path: data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6B.json
  partitioning: [fingerprint]
  primary_key: [manifest_fingerprint]
  ordering: []
  schema_ref: schemas.layer3.yaml#/validation/6B/s5_validation_report
  produced_by: [6B.S5]
  consumed_by: [6B.S5_bundle, 4A, 4B, ops_tooling]
```

#### 5.2.3 Registry entry

`artefact_registry_6B.yaml` **MUST** register the report as:

```yaml
- manifest_key: s5_validation_report_6B
  type: dataset
  category: validation
  environment: engine
  owner_layer: 3
  owner_segment: 6B
  schema: schemas.layer3.yaml#/validation/6B/s5_validation_report
  path_template: data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6B.json
  partitioning: [fingerprint]
  final_in_layer: true
```

---

### 5.3 `s5_issue_table_6B` shape & catalogue links

#### 5.3.1 Row model

`schemas.layer3.yaml#/validation/6B/validation_issue_table_6B` MUST define a tabular schema with one row per issue.

Required fields (minimum):

* Identity:

  * `manifest_fingerprint: string`
  * `check_id: string`

    * Matches a `check_id` in the validation policy.
  * `issue_id: string` or `integer`

    * Unique per check for this world.

* Classification:

  * `severity: string`

    * Enum: `"WARN"`, `"FAIL"` (INFO issues MAY be included but are optional).
  * `scope_type: string`

    * e.g. `"WORLD"`, `"PARTITION"`, `"FLOW"`, `"CASE"`, `"EVENT"`.

* Scope coordinates (nullable depending on `scope_type`):

  * `seed: integer|string|null`
  * `scenario_id: string|integer|null`
  * `flow_id: string|integer|null`
  * `case_id: string|integer|null`
  * `event_seq: integer|null`

* Description:

  * `message: string`
  * `metrics: object` (check-specific key/value pairs; optional).

#### 5.3.2 Dictionary entry

In `dataset_dictionary.layer3.6B.yaml`:

```yaml
- id: s5_issue_table_6B
  status: optional
  owner_layer: 3
  owner_segment: 6B
  description: >
    Detailed issues found during S5 validation; one row per issue, with
    scope, severity, and metrics.
  version: '{manifest_fingerprint}'
  format: parquet
  path: data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6B.parquet
  partitioning: [fingerprint]
  primary_key: [manifest_fingerprint, check_id, issue_id]
  ordering: [manifest_fingerprint, check_id, issue_id]
  schema_ref: schemas.layer3.yaml#/validation/6B/validation_issue_table_6B
  produced_by: [6B.S5]
  consumed_by: [6B.S5_bundle, ops_tooling]
```

#### 5.3.3 Registry entry

In `artefact_registry_6B.yaml`:

```yaml
- manifest_key: s5_issue_table_6B
  type: dataset
  category: validation
  environment: engine
  owner_layer: 3
  owner_segment: 6B
  schema: schemas.layer3.yaml#/validation/6B/validation_issue_table_6B
  path_template: data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6B.parquet
  partitioning: [fingerprint]
  final_in_layer: true
```

---

### 5.4 `validation_bundle_index_6B` (bundle index) shape & catalogue links

#### 5.4.1 JSON model

`schemas.layer3.yaml#/validation/6B/validation_bundle_index_6B` MUST define a JSON schema for the bundle index file (`index.json`) with at least:

* `manifest_fingerprint: string`
* `parameter_hash: string`
* `spec_version_6B: string`
* `items: array` of objects, where each item has:

  * `path: string`

    * Relative path to a file inside `validation_bundle_6B`, using only `./`-free segments and without `..`.
  * `sha256_hex: string`

    * 64-char lowercase hex digest of that file’s raw bytes.
  * `role: string`

    * e.g. `"report"`, `"issue_table"`, `"rng_summary"`, `"coverage_metrics"`.
  * Optional `schema_ref: string`

    * JSON-Schema `$ref` for that artefact.

Binding rules:

* `items` MUST be sorted by `path` in ASCII-lex order.
* `path` values MUST be unique.
* `items` MUST NOT list `_passed.flag_6B`.

#### 5.4.2 Dictionary entry

The index is part of the logical `validation_bundle_6B` dataset; in `dataset_dictionary.layer3.6B.yaml` this is expressed via the bundle entry, e.g.:

```yaml
- id: validation_bundle_6B
  status: required
  owner_layer: 3
  owner_segment: 6B
  description: >
    World-level validation bundle for Segment 6B; directory of validation
    artefacts plus index.json and _passed.flag_6B.
  version: '{manifest_fingerprint}'
  format: directory
  path: data/layer3/6B/validation/fingerprint={manifest_fingerprint}/
  partitioning: [fingerprint]
  primary_key: [manifest_fingerprint]
  ordering: []
  schema_ref: schemas.layer3.yaml#/validation/6B/validation_bundle_index_6B
  produced_by: [6B.S5]
  consumed_by: [downstream_gate_checkers]
```

> Note: `schema_ref` here points to the index schema; the bundle itself is a directory, but the index is what downstream checkers use to recompute the digest.

#### 5.4.3 Registry entry

`artefact_registry_6B.yaml` MUST register the bundle:

```yaml
- manifest_key: validation_bundle_6B
  type: directory
  category: validation
  environment: engine
  owner_layer: 3
  owner_segment: 6B
  schema: schemas.layer3.yaml#/validation/6B/validation_bundle_index_6B
  path_template: data/layer3/6B/validation/fingerprint={manifest_fingerprint}/
  partitioning: [fingerprint]
  final_in_layer: true
  cross_layer: true
```

---

### 5.5 `validation_passed_flag_6B` shape & catalogue links

#### 5.5.1 Text model

`schemas.layer3.yaml#/validation/6B/passed_flag_6B` MUST define a simple text schema constrained to:

* exactly one line of text, with the pattern:

  ```text
  sha256_hex = <64-lowercase-hex>
  ```

* where `<64-lowercase-hex>` is the SHA-256 digest of the concatenation of the raw bytes of all files listed in `validation_bundle_index_6B.items`, in **index order**, excluding `_passed.flag_6B`.

This schema is used to validate the format of `_passed.flag_6B`.

#### 5.5.2 Dictionary entry

`dataset_dictionary.layer3.6B.yaml` MUST include:

```yaml
- id: validation_passed_flag_6B
  status: required
  owner_layer: 3
  owner_segment: 6B
  description: >
    Segment 6B HashGate flag; encodes SHA-256 digest over the 6B validation
    bundle for this world.
  version: '{manifest_fingerprint}'
  format: text
  path: data/layer3/6B/validation/fingerprint={manifest_fingerprint}/_passed.flag_6B
  partitioning: [fingerprint]
  primary_key: [manifest_fingerprint]
  ordering: []
  schema_ref: schemas.layer3.yaml#/validation/6B/passed_flag_6B
  produced_by: [6B.S5]
  consumed_by: [downstream_gate_checkers, 4A, 4B, model_training]
```

#### 5.5.3 Registry entry

`artefact_registry_6B.yaml` MUST register:

```yaml
- manifest_key: validation_passed_flag_6B
  type: file
  category: HashGate
  environment: engine
  owner_layer: 3
  owner_segment: 6B
  schema: schemas.layer3.yaml#/validation/6B/passed_flag_6B
  path_template: data/layer3/6B/validation/fingerprint={manifest_fingerprint}/_passed.flag_6B
  partitioning: [fingerprint]
  final_in_layer: true
  cross_layer: true
```

---

### 5.6 Identity & wiring summary

With these shapes and links:

* All S5 artefacts are **fingerprint-partitioned**, keyed by `manifest_fingerprint`.
* `s5_validation_report_6B` and `s5_issue_table_6B` are standard datasets, discoverable via dictionary/registry.
* `validation_bundle_6B` is a logical directory, whose index schema ensures downstream gate checkers can recompute bundle hashes.
* `validation_passed_flag_6B` is a small, schema-validated text file, tied to the same fingerprint and bundle index.

This wiring ensures that:

* S5 can be implemented consistently across environments, and
* downstream systems can always find the validation bundle and HashGate flag for any world purely via the catalogue and schema anchors, without hard-coded paths.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section specifies **how** 6B.S5 behaves for a given `manifest_fingerprint`.

S5 is a **pure validation & sealing state**:

* It is **world-scoped** (no per-seed/scenario partitioning in its own outputs).
* It is **RNG-free** — it MUST NOT consume Philox or any other RNG.
* It produces only:

  * a validation report (`s5_validation_report_6B`),
  * an optional issue table (`s5_issue_table_6B`),
  * a validation bundle (`validation_bundle_6B`), and
  * the 6B HashGate flag (`validation_passed_flag_6B` / `_passed.flag_6B`).

S5’s behaviour MUST be fully deterministic given:

* `manifest_fingerprint`,
* `parameter_hash`, `spec_version_6B`,
* the catalogues (schemas, dictionaries, registries),
* upstream HashGates and 6B S0–S4 outputs,
* `segment_validation_policy_6B`.

If any of these inputs change, S5 may produce a different verdict and/or bundle; otherwise, S5 MUST produce exactly the same artefacts on every re-run (or detect an idempotence violation, see §7).

---

### 6.1 Determinism & RNG envelope

**Binding constraints:**

1. **RNG-free**

   * S5 MUST NOT call Philox or any RNG.
   * All decisions in S5 MUST be derived from deterministic computations over its inputs.

2. **Pure function**

   For a fixed `manifest_fingerprint` and fixed:

   * `parameter_hash`, `spec_version_6B`,
   * upstream HashGates,
   * S0–S4 outputs and run-report entries,
   * `segment_validation_policy_6B`,

   S5 MUST:

   * either produce identical `s5_validation_report_6B`, `s5_issue_table_6B` (if used), `validation_bundle_6B` and `_passed.flag_6B`, or
   * detect that those artefacts already exist and are identical, and treat itself as a no-op.

3. **Stable ordering**

   * Wherever ordering is required (e.g. in `validation_bundle_index_6B.items`), S5 MUST use a deterministic sort key (ASCII-lex `path`).
   * The exact same inputs MUST always produce the exact same index ordering and hence the exact same bundle digest.

---

### 6.2 Step 0 — Discover workload & inputs for the world

Given `manifest_fingerprint`:

1. **Load S0 & sealed inputs**

   * Load `s0_gate_receipt_6B` and `sealed_inputs_6B` and validate them, as per §2 and §3.
   * Extract:

     * `parameter_hash`, `spec_version_6B`;
     * `upstream_segments` status;
     * the list of all 6B artefacts (S1–S4 datasets, configs, RNG logs, etc.), with their roles and `read_scope`.

2. **Determine intended S1–S4 domains**

   Using `sealed_inputs_6B`, dictionaries and/or S4/S3 run-report entries:

   * Compute the set of `(seed, scenario_id)` partitions that are **in scope** for this world (i.e. where S2/S3 overlays exist and S4 labels are required).
   * Compute the set of `seed` values that are in scope for case timelines (`s4_case_timeline_6B`).

3. **Load S5 validation policy**

   * Load and validate `segment_validation_policy_6B`. This policy contains the list of checks S5 MUST run, severity (REQUIRED/WARN/INFO), and any numeric thresholds or sampling rules.

If this step fails (e.g. missing policy, sealed inputs invalid), S5 MUST stop with a precondition failure and write no outputs.

---

### 6.3 Step 1 — Re-check S0 & upstream HashGates

1. **S0 re-check**

   * Confirm that S0’s own invariants hold:

     * `upstream_segments[*].status` matches the re-verified upstream HashGate states (below),
     * `sealed_inputs_digest_6B` matches the digest recomputed over `sealed_inputs_6B` (according to S0’s law).

2. **Upstream HashGates re-verification**

   For each upstream segment in `{1A,1B,2A,2B,3A,3B,5A,5B,6A}`:

   * Locate its `validation_bundle_*` and `_passed.flag_*` using its own dictionary/registry and `sealed_inputs_6B`.
   * Validate the upstream index against its schema.
   * Recompute the upstream bundle digest according to that segment’s hashing law.
   * Check that `_passed.flag_*` encodes the same digest.
   * Cross-check `s0_gate_receipt_6B.upstream_segments[SEG].status` is `"PASS"` if and only if the upstream bundle+flag are valid.

3. **Record results into S5 check context**

   * Populate internal “check context” with verdicts and digests for S0 and upstream segments (for later inclusion in `s5_validation_report_6B`).

Any upstream HashGate failure must be recorded as a failed REQUIRED check; whether that automatically yields `overall_status="FAIL"` is dictated by `segment_validation_policy_6B` (normally yes).

---

### 6.4 Step 2 — Structural validation of 6B datasets (S1–S4)

For all 6B data-plane outputs (S1–S4) flagged as `status="REQUIRED"` in `sealed_inputs_6B`:

1. **Resolve schema & dictionary contract**

   * Retrieve `schema_ref` from `sealed_inputs_6B` entry.
   * Retrieve expected `path_template`, `partitioning`, `primary_key`, and `ordering` from `dataset_dictionary.layer3.6B.yaml`.

2. **Enumerate partitions for this world**

   * Using `path_template` and `partition_keys`, enumerate all expected partition paths for `manifest_fingerprint` and its seeds/scenarios (as defined by sealed inputs or spec).
   * Use storage metadata / catalogue to confirm actual partitions.

3. **Validate schema & PK/partitioning**

   For each existing partition file:

   * Validate each dataset against its schema (`schema_ref`).
   * Check that:

     * embedded `manifest_fingerprint` equals the path token,
     * other partition columns (`seed`, `scenario_id`) match path tokens where applicable,
     * primary key uniqueness holds within the partition,
     * ordering constraints are satisfied if they are declared (S1–S4 specs define ordering for each dataset).

4. **Record structural check results**

   For each dataset, record:

   * whether all partitions passed schema/PK/partition checks (PASS),
   * or else record WARN/FAIL issues into an internal list for `s5_issue_table_6B`.

This step enforces that S1–S4 outputs are structurally valid according to their own contracts.

---

### 6.5 Step 3 — Cross-state coverage & consistency checks

Using the domains discovered in Step 0 and the S1–S4 specs (and their own acceptance criteria), S5 MUST:

1. **Per-partition S1 coverage**

   For each `(seed, scenario_id)` in scope:

   * Check that S1 invariants hold, e.g.:

     * all arrivals intended for this partition (per S1/S2 contracts) appear in `s1_arrival_entities_6B`,
     * every arrival has a `session_id`,
     * every session in `s1_session_index_6B` has at least one arrival.

   These checks may be based on:

   * direct counts over S1 datasets,
   * and/or S1’s own run-report metrics, as configured in `segment_validation_policy_6B`.

2. **S2 coverage: sessions → baseline flows → baseline events**

   * For each `(seed, scenario_id)`:

     * verify that S2 covers S1 sessions as per S2 spec (e.g. each session yields the expected number of baseline flows; flows have events).
     * check that flow/event counts per partition match S2’s run-report metrics.

3. **S3 coverage: baseline ↔ overlays & campaigns**

   * Confirm that:

     * every baseline flow appears in S3 flow overlays (`{flow_id(FA2)} ⊆ {flow_id(FA3)}`),
     * S3 may add new flows (pure fraud) but not drop baseline flows,
     * S3’s campaign catalogue `s3_campaign_catalogue_6B` is consistent with overlay tagging: all non-null `campaign_id`s in S3 overlays exist in the catalogue and intensity metrics agree within tolerances.

4. **S4 coverage: overlays ↔ labels & cases**

   * Confirm that for each partition:

     * every flow in S3 overlays has exactly one truth-label row and one bank-view row,
     * every event in S3 overlays has exactly one event-label row,
     * any flows marked as case-involved in bank-view labels appear in the case timeline.

   * Cross-check that:

     * S4 label coverage metrics in S4’s run-report match computed counts,
     * S4 case timelines cover all case-involved flows.

5. **Record coverage check results**

   * Each coverage mismatch or anomaly is recorded as an issue (WARN or FAIL) according to `segment_validation_policy_6B`, tagged with a clear `check_id`.

This step ensures that there are no “holes” between S1–S4 surfaces.

---

### 6.6 Step 4 — Behavioural & label consistency checks

S5 runs **behavioural checks** as specified in `segment_validation_policy_6B`. Examples (non-exhaustive; the policy is the source of truth):

1. **Truth vs overlay vs posture**

   * Cross-check that:

     * S4 truth labels are consistent with S3 overlay patterns and 6A posture (no gross contradictions).
     * For each `truth_subtype`, associated `fraud_pattern_type` values are within allowed sets.

2. **Bank-view vs truth & delay models**

   * Check that:

     * bank-view labels are compatible with truth labels and bank-view policy (e.g. no “confirmed fraud” on flows labelled legit),
     * detection/dispute/chargeback timestamps fall within the world horizon and respect delay models (no negative/absurd delays).

3. **Campaign integrity**

   * Confirm that S3’s realised campaigns (from `s3_campaign_catalogue_6B`) match:

     * targeting intensity expectations,
     * patterns in overlays (flows/events actually tagged with those campaigns).

4. **Scenario-level metrics**

   * Evaluate configured metrics (e.g. fraud rate, detection rate, chargeback rate) per scenario and/or segment against bounds in the validation policy.
   * CLASSIFY them as PASS/WARN/FAIL.

5. **Record results**

   * For each behavioural check, record `check_id`, severity, result, metrics & thresholds.

These checks are all deterministic functions of S1–S4 outputs and policies; no RNG is used.

---

### 6.7 Step 5 — RNG envelope & accounting checks (S1–S4)

Although S5 itself is RNG-free, it MUST validate that RNG usage by S1–S4 conforms to the Layer-3 RNG specs and state-specific RNG policies.

For each Layer-3 RNG family used by S1–S4:

1. **Load RNG logs & trace summaries**

   * Use `sealed_inputs_6B` and dictionaries to find RNG log datasets (e.g. `rng_event_*`, `rng_trace_log`) for S1–S4.
   * Validate them against Layer-3 RNG schemas.

2. **Compute expected draw counts**

   * For each state and family, compute **expected** RNG event and draw counts as a deterministic function of:

     * domain sizes (e.g. number of arrivals, flows, sessions),
     * state policies (e.g. “1 draw per flow”, “1 draw per ambiguous flow”),
     * as defined by that state’s RNG policy.

3. **Compare to actual logs**

   * Summarise actual counts from RNG logs.
   * Check that actual counts match expected counts (or fall within configured tolerances, if policy allows).
   * Check that RNG counters are monotone and non-overlapping where required (e.g. no counter reuse between logically separate families).

4. **Record RNG check results**

   * For each (state, family), record whether RNG usage is PASS, WARN, or FAIL in S5’s check set.

Any mismatched RNG envelope MUST be marked as at least WARN; if policy marks it REQUIRED, it becomes a FAIL.

---

### 6.8 Step 6 — Derive world verdict & build S5 outputs

1. **Derive per-check verdicts**

   * Using `segment_validation_policy_6B`, classify each check as:

     * PASS — check is satisfied,
     * WARN — metrics outside nominal but within acceptable tolerance,
     * FAIL — violation of required invariant.

2. **Compute `overall_status`**

   * Aggregate all checks:

     * If any REQUIRED check is FAIL → `overall_status = "FAIL"`.
     * Else if at least one WARN_ONLY check is WARN → `overall_status = "WARN"`.
     * Else → `overall_status = "PASS"`.

3. **Construct `s5_validation_report_6B`**

   * Build the JSON object as per its schema:

     * embed identity (`manifest_fingerprint`, `parameter_hash`, `spec_version_6B`),
     * include `upstream_segments` verdicts,
     * include a structured list of checks with severity, result, metrics and thresholds,
     * set `overall_status`.

4. **Construct `s5_issue_table_6B` (optional)**

   * For every WARN/FAIL with issue-level detail (e.g. per-flow/per-case anomalies), generate issue rows containing:

     * `check_id`, `issue_id`, `severity`, `scope_type`, coordinates, message, metrics.

   * Leave the dataset empty or absent if no issues are present and policy doesn’t require an issue table.

5. **Write report & issue table**

   * Write `s5_validation_report_6B.json` and (if used) `s5_issue_table_6B.parquet` under the bundle root path for this fingerprint.
   * Validate both against their schemas before proceeding.

---

### 6.9 Step 7 — Build validation bundle & compute `_passed.flag_6B`

1. **Enumerate bundle members**

   * Based on `segment_validation_policy_6B`, determine which artefacts are included in `validation_bundle_6B` for this world.
   * At minimum, this MUST include:

     * `s5_validation_report_6B.json`,
     * `s5_issue_table_6B.parquet` if produced,
     * any additional S5-generated metrics or RNG/coverage summaries, and/or snapshot digests of S0–S4 artefacts as required by policy.

2. **Build `validation_bundle_index_6B`**

   * For each included file:

     * compute its `sha256_hex` digest over raw bytes,
     * define a relative `path` from the bundle root (no `..`, no leading `/`),
     * assign a `role` and optional `schema_ref`.

   * Assemble `items`:

     * list each file exactly once,
     * sort `items` by `path` in ASCII-lex order,
     * ensure `_passed.flag_6B` (if present) is **not** included.

   * Wrap into the index JSON with identity fields (`manifest_fingerprint`, `parameter_hash`, `spec_version_6B`) and write it as `index.json` (or the chosen filename) in the bundle directory, validating against `validation_bundle_index_6B` schema.

3. **Compute world-level bundle digest**

   * Concatenate the raw bytes of all files listed in `items`, in index order.
   * Compute the SHA-256 digest over this concatenated byte stream.
   * Represent the digest as a 64-character lowercase hex string `<digest>`.

4. **Decide flag emission**

   * If `overall_status` in `s5_validation_report_6B` is `"PASS"` (and any additional policy criteria for sealing are satisfied):

     * build `_passed.flag_6B` contents:

       ```text
       sha256_hex = <digest>
       ```

     * write `_passed.flag_6B` under `data/layer3/6B/validation/fingerprint={manifest_fingerprint}/`.

   * If `overall_status` is `"WARN"` or `"FAIL"` and policy forbids sealing on WARN, do **not** write `_passed.flag_6B` (or remove it if it existed and policy allows overwrite only on re-run with PASS — see idempotence in §7).

   S5 MUST NOT write `_passed.flag_6B` for a world that fails required checks.

5. **Idempotence check (on re-run)**

   * If a bundle and `_passed.flag_6B` already exist for this fingerprint:

     * recompute the bundle digest from the existing index and files;
     * compare to the digest encoded in `_passed.flag_6B`;
     * if they match and the newly computed digest (from Step 3) is the same, treat as a no-op;
     * if they differ, S5 MUST report an idempotence violation and MUST NOT overwrite existing artefacts.

---

This algorithm defines S5 as a **deterministic, RNG-free validator & sealer**:

* It re-checks S0–S4 and upstream HashGates,
* it produces a world-level validation report and optional issue table,
* it constructs a canonical validation bundle, and
* it emits `_passed.flag_6B` as the single, cryptographically sealed signal that Segment 6B is safe to read for the target `manifest_fingerprint`.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S5’s outputs are identified and stored**, and what rules implementations MUST follow for **partitioning, ordering, re-runs and merges**.

It applies to all S5 artefacts:

* `s5_validation_report_6B`
* `s5_issue_table_6B` (optional)
* `validation_bundle_6B` (including `validation_bundle_index_6B`)
* `validation_passed_flag_6B` (`_passed.flag_6B`)

All of these artefacts are **world-scoped**: they are keyed solely by `manifest_fingerprint`.

---

### 7.1 Identity axes

S5 is evaluated per world:

* **Primary identity axis:**

  * `manifest_fingerprint` — the sealed world snapshot id.

* **Secondary identity (data fields only):**

  * `parameter_hash` — hash of the 6B configuration pack.
  * `spec_version_6B` — version of the 6B segment contract.

Binding rules:

1. S5 outputs MUST include `manifest_fingerprint` as a first-class field in:

   * `s5_validation_report_6B` (JSON)
   * `validation_bundle_index_6B` (index JSON)
   * `s5_issue_table_6B` rows (if present)

2. S5 outputs MUST **NOT** be partitioned or keyed by:

   * `seed`, `scenario_id`, `run_id` or any other execution identifier.

3. `parameter_hash` and `spec_version_6B` are recorded as **data fields** inside S5 artefacts, but are **not** additional partition keys. They are part of the content identity, not storage identity.

---

### 7.2 Partitioning & path discipline

All S5 artefacts are partitioned solely by `fingerprint={manifest_fingerprint}`:

* `s5_validation_report_6B`:

  ```text
  data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6B.json
  ```

* `s5_issue_table_6B` (optional):

  ```text
  data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6B.parquet
  ```

* `validation_bundle_6B` (directory):

  ```text
  data/layer3/6B/validation/fingerprint={manifest_fingerprint}/
  ```

  (contains `index.json`, the evidence files listed there, plus `_passed.flag_6B`).

* `_passed.flag_6B`:

  ```text
  data/layer3/6B/validation/fingerprint={manifest_fingerprint}/_passed.flag_6B
  ```

**Path↔embed equality (binding):**

* Wherever `manifest_fingerprint` appears as a field in S5 artefacts, its value MUST equal the `fingerprint={manifest_fingerprint}` path token.
* S5 MUST NOT write any of its artefacts outside the `data/layer3/6B/validation/fingerprint={manifest_fingerprint}/` directory for that world.

---

### 7.3 Uniqueness & primary keys

Logical keys:

* `s5_validation_report_6B`

  ```text
  PK: [manifest_fingerprint]
  ```

* `s5_issue_table_6B`

  ```text
  PK: [manifest_fingerprint, check_id, issue_id]
  ```

* `validation_bundle_6B`

  * Logical PK is `[manifest_fingerprint]`; there is one bundle directory per world.

* `validation_passed_flag_6B`

  ```text
  PK: [manifest_fingerprint]
  ```

Binding rules:

1. For a given `manifest_fingerprint` and `spec_version_6B`, there MUST be **at most one**:

   * `s5_validation_report_6B.json`
   * `s5_issue_table_6B.parquet` (if present)
   * `validation_bundle_6B` directory
   * `_passed.flag_6B` file

2. If you support multiple spec versions side-by-side, that MUST be expressed via **different artefact ids/paths** (e.g. versioned ids), not multiple reports/flags colliding under the same path.

Within `s5_issue_table_6B`:

* The combination `(manifest_fingerprint, check_id, issue_id)` MUST be unique per row.

---

### 7.4 Bundle index ordering & identity

The bundle index (`validation_bundle_index_6B`, usually `index.json` under the bundle root) defines the logical content of `validation_bundle_6B`.

Binding rules for the index:

1. `items` MUST be an array of objects including at least:

   ```json
   { "path": "<relative_path>", "sha256_hex": "<64-hex>", "role": "<string>", ... }
   ```

2. `path`:

   * MUST be a **relative path** from the bundle root (no leading `/`, no `..` segments).
   * MUST be unique across items.
   * MUST NOT refer to `_passed.flag_6B`.

3. **Ordering:**

   * `items` MUST be sorted by `path` in ASCII-lexicographic order.
   * S5 MUST use this ordering both:

     * when computing each item’s position in the index, and
     * when concatenating files to compute the overall bundle digest.

This ordering is part of the **identity**: given the same bundle contents, S5 and any consumer recomputing the digest MUST derive the same `items` ordering and thus the same digest.

---

### 7.5 Write ordering & atomicity

S5 writes its artefacts in the following logical order for a world:

1. **Validation report & issue table**

   * Write `s5_validation_report_6B.json` and (if produced) `s5_issue_table_6B.parquet` first.
   * Both MUST be written and flushed successfully, and each MUST validate against its schema before S5 proceeds.

2. **Other evidence files (optional)**

   * Write any additional S5 evidence artefacts (e.g. RNG summaries, coverage tables) into the bundle directory.

3. **Bundle index**

   * Compute per-file `sha256_hex` digests and build `validation_bundle_index_6B` (index JSON).
  * Write the index file (`index.json`) and validate it against its schema.

4. **HashGate flag**

   * Compute the bundle digest over files listed in `index.items` in ASCII-lex `path` order.
   * If `overall_status` in the report is `PASS` (and policy permits sealing), write `_passed.flag_6B` with that digest.

Atomicity constraints:

* Writing the flag MUST be the **final step**.
* Presence of `_passed.flag_6B` implies that:

  * the index exists,
  * all files listed in the index exist and have the digests captured in the index,
  * `overall_status` meets the sealing requirements.

If any error occurs after the report but before the flag, S5 MUST leave `_passed.flag_6B` **absent**; such a world is not considered sealed.

---

### 7.6 Re-runs & idempotence discipline

S5 MUST be **write-once, idempotent** per `manifest_fingerprint` for a given contract.

Binding rules:

1. **No bundle & flag yet**

   * If `validation_bundle_6B` directory exists but contains **no index and no `_passed.flag_6B`** (e.g. previous run crashed early), S5 MAY:

     * rebuild the report/issue table if needed,
     * build a fresh index and digest,
     * write `_passed.flag_6B` if the world passes validation.

   * This is treated as completing a previously incomplete run, not as an idempotence violation.

2. **Bundle exists, flag absent**

   * If an index and evidence files exist, but `_passed.flag_6B` is absent, S5 MUST:

     * recompute the bundle digest from the existing index/files,
     * re-derive `overall_status` from a fresh or existing report,
     * if `overall_status` now permits sealing, write `_passed.flag_6B` with that digest;
     * if it does not, leave the flag absent.

   * S5 MUST NOT overwrite existing evidence files unless the contract explicitly allows “rebuild from scratch” and they are known to be incomplete; in that case it must do so consistently and document the behaviour.

3. **Bundle & flag exist**

   * On a re-run, if `index.json` and `_passed.flag_6B` already exist:

     * Recompute the digest from the index and bundle files.

     * Compare it to the digest recorded in `_passed.flag_6B`.

     * If they match, and S5’s freshly computed validation result (based on current inputs) would produce the *same* bundle content (i.e. no new issues or changed report), then:

       * Treat S5 as a **no-op** for this world (idempotent re-run).
       * MUST NOT rewrite any S5 artefact.

     * If there is any mismatch (flag digest ≠ recomputed digest, or S5 would generate a different report/index given unchanged inputs):

       * S5 MUST treat this as an **idempotence violation** (e.g. `S5_IDEMPOTENCE_VIOLATION`).
       * S5 MUST NOT overwrite existing bundle or flag.
       * Operators MUST resolve the conflict (e.g. by bumping `spec_version_6B`/`parameter_hash` or explicitly rebuilding from upstream).

4. **No incremental merges**

   * S5 MUST NOT support incremental appends/merges to an existing bundle:

     * you cannot “add a few more checks later” and append to the bundle under the same fingerprint/spec without treating it as a new world/contract.
     * any such change would change the bundle digest and MUST be treated as a new S5 result (requiring explicit rebuild and overwriting under controlled conditions).

---

### 7.7 Single-writer & concurrency discipline

For a given `manifest_fingerprint` and `spec_version_6B`:

* At any point in time, there MUST be at most one **active S5 writer** targeting that world in a given environment/deployment.

Binding rules:

1. **No concurrent writers**

   * Orchestrators MUST NOT schedule two S5 processes to write S5 artefacts for the same fingerpint concurrently.
   * If concurrency is unavoidable, a higher-level locking or leader-election mechanism MUST ensure a single effective writer.

2. **Safe parallel read**

   * It is safe for other components to read S1–S4, upstream bundles and previous S5 outputs while S5 runs, as long as:

     * S5 obeys the atomicity rules above (flag last),
     * consumers treat the absence of `_passed.flag_6B` as “not yet sealed”.

---

### 7.8 Downstream join & gating discipline

Downstream components (4A/4B, model-training, evaluation, any “gate checker”) MUST:

* Locate S5 artefacts via the dictionary/registry, using `manifest_fingerprint` alone.
* Use the following logic:

  1. Read `validation_bundle_index_6B` (`index.json`) and recompute the bundle digest over the listed files in sorted `path` order.
  2. Read `_passed.flag_6B` and parse the `sha256_hex`.
  3. If the digest values match, treat 6B for that fingerprint as **sealed & PASS**; otherwise, treat it as **not sealed** (even if S5 reports say otherwise).

This gating discipline binds S5’s identity and merge behaviour to a simple, robust rule:

> Only a world with a **matching** `_passed.flag_6B` and bundle index is considered validated for Segment 6B; all other worlds MUST be treated as unvalidated and unsafe to read.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines:

* When 6B.S5 is considered **PASS** vs **FAIL** for a given `manifest_fingerprint`, and
* How that verdict **gates** downstream consumers (4A/4B, model-training/eval, any “gate checker”).

S5 is **world-scoped**. There is exactly one S5 verdict per `manifest_fingerprint` per `spec_version_6B`.

---

### 8.1 Domain of evaluation

S5’s verdict is defined per world:

```text
(manifest_fingerprint)
```

Within that world, S5:

* aggregates validation over all `(seed, scenario_id)` partitions that belong to the world, and
* aggregates over all seeds used by S4 case timelines.

S5 does **not** emit separate PASS/FAIL per partition; it emits a single world-level verdict in `s5_validation_report_6B`.

---

### 8.2 Acceptance criteria for S5 (per `manifest_fingerprint`)

For a world with fingerprint `F`, S5 is considered **PASS** if and only if **all** of the following hold.

#### 8.2.1 Preconditions satisfied

All preconditions in §2 MUST be satisfied:

* `s0_gate_receipt_6B` and `sealed_inputs_6B` exist and are schema-valid for `F`.

* All required upstream segments (`1A,1B,2A,2B,3A,3B,5A,5B,6A`) have:

  * valid `validation_bundle_*` and `_passed.flag_*` for `F`,
  * consistent bundle digests and flags (recomputed by S5).

* The 6B workload is complete:

  * S1–S4 have recorded a status for each `(seed, scenario_id)` partition in scope,
  * required 6B datasets (S1–S4 surfaces listed in §3.5) are present and reachable via `sealed_inputs_6B`.

* `segment_validation_policy_6B` is present and schema-valid.

If any of these fail, S5 MUST treat the world as **FAIL** (precondition failure), set `overall_status = "FAIL"`, and MUST NOT write `_passed.flag_6B`.

#### 8.2.2 S0 & upstream HashGates validated

S5 MUST verify:

* S0’s own invariants:

  * `sealed_inputs_digest_6B` matches the digest recomputed from `sealed_inputs_6B`,
  * `upstream_segments[*].status` is consistent with re-verified upstream HashGates.

* Each required upstream HashGate:

  * index schema-valid,
  * all files listed exist and match their individual `sha256_hex`,
  * upstream bundle digest recomputation equals digest in upstream `_passed.flag_*`.

If any upstream HashGate fails verification and `segment_validation_policy_6B` marks this as a REQUIRED check (normally yes), S5 MUST set `overall_status = "FAIL"`.

#### 8.2.3 Structural validity of S1–S4 datasets

For all 6B data-plane outputs (S1–S4) that `sealed_inputs_6B` and the spec mark as REQUIRED:

* All expected partitions for `F` (and for seeds/scenarios in scope) MUST:

  * exist (or be explicitly allowed to be empty by spec/policy),
  * validate against their schema anchors,
  * obey partitioning rules (`seed`, `fingerprint`, `scenario_id` path↔embed),
  * obey primary key uniqueness,
  * satisfy ordering constraints defined in S1–S4 specs (where applicable).

Any schema/PK/partition/order violation in a REQUIRED dataset is, by default, a FAILED structural check. If `segment_validation_policy_6B` marks that check as REQUIRED, S5 MUST set `overall_status = "FAIL"`.

#### 8.2.4 Cross-state coverage & identity consistency

The cross-state invariants defined in S1–S4 specs MUST hold, including at least:

* **S1**: arrivals ↔ entities ↔ sessions:

  * arrivals are neither dropped nor duplicated in `s1_arrival_entities_6B`,
  * each arrival has exactly one `session_id`,
  * sessions in `s1_session_index_6B` have arrivals (unless explicitly allowed).

* **S2**: sessions → baseline flows → baseline events:

  * S2 covers intended S1 sessions according to S2 spec,
  * each baseline flow has ≥1 event, events refer to existing flows,
  * identity axes match across S1/S2.

* **S3**: baseline ↔ overlays & campaigns:

  * every baseline `flow_id` appears in S3 flow overlays,
  * campaign catalogue agrees with flows/events tagged with `campaign_id`,
  * S3 doesn’t drop baseline flows.

* **S4**: overlays ↔ labels & cases:

  * every S3 `flow_id` appears once in `s4_flow_truth_labels_6B` and `s4_flow_bank_view_6B`,
  * every S3 event key appears once in `s4_event_labels_6B`,
  * any flow marked as case-involved appears in `s4_case_timeline_6B`.

S5 MUST:

* evaluate these invariants (via direct checks or via per-state metrics + sampling, as configured),
* treat any violation of a REQUIRED coverage check as a FAIL.

If `segment_validation_policy_6B` allows some coverage checks to be WARN_ONLY, S5 MAY set `result="WARN"` for those checks without forcing `overall_status = "FAIL"`.

#### 8.2.5 Behavioural consistency checks

Behavioural consistency checks (truth vs overlay vs posture, bank-view vs truth/delays, campaign intensity vs config, etc.), as listed in `segment_validation_policy_6B`, MUST be applied and classified:

* If a behavioural metric is outside acceptable bounds for a REQUIRED check (e.g. fraud detection rate too low, fraud rate per segment too far off config) → that check is FAIL.
* If outside nominal but within warning bounds → check is WARN.
* If within nominal bounds → check is PASS.

S5 MUST:

* respect the severity levels from `segment_validation_policy_6B`:

  * REQUIRED → FAIL should drive `overall_status="FAIL"`.
  * WARN_ONLY → FAIL is not allowed; result MUST be downgraded to WARN if supported, or considered incompatible with the policy.
  * INFO → used only for reporting; never drives FAIL.

#### 8.2.6 RNG envelope & accounting checks for S1–S4

For each state S1–S4 and each RNG family used:

* S5 MUST confirm that:

  * actual RNG event/draw counts match the expected counts (or fall within allowed tolerances) defined by that state’s RNG policy,
  * RNG counters are monotonic where required,
  * no overlapping/duplicate counter ranges across disjoint families/streams.

If any RNG check marked as REQUIRED fails, S5 MUST set `overall_status = "FAIL"`.

#### 8.2.7 Overall verdict & sealing decision

S5 MUST derive:

* `overall_status ∈ {"PASS", "WARN", "FAIL"}` for this `manifest_fingerprint` by aggregating all checks:

  * If **any REQUIRED check** has `result="FAIL"` → `overall_status = "FAIL"`.
  * Else if **no REQUIRED FAIL**, but at least one WARN or WARN_ONLY check has `result="WARN"` → `overall_status = "WARN"`.
  * Else → `overall_status = "PASS"`.

Sealing rules:

* S5 MUST **NOT** write `_passed.flag_6B` if `overall_status = "FAIL"`.
* Whether `overall_status = "WARN"` permits sealing is determined by `segment_validation_policy_6B`:

  * If policy **requires fully PASS** to seal:

    * `overall_status = "WARN"` → no `_passed.flag_6B`.
  * If policy allows WARN for sealing (e.g. “warnings acceptable, but still seal world”):

    * S5 MAY write `_passed.flag_6B` even when `overall_status = "WARN"`, but MUST record warnings clearly in the report.

Under this spec, the default assumption is:

> Only `overall_status = "PASS"` produces `_passed.flag_6B`, unless explicitly overridden by policy.

---

### 8.3 Conditions that MUST cause S5 to FAIL

S5 MUST set `overall_status = "FAIL"` and MUST NOT write `_passed.flag_6B` if any of the following occurs:

* Precondition failures (§2.2–§2.6):

  * missing/invalid `s0_gate_receipt_6B` or `sealed_inputs_6B`,
  * missing/invalid upstream HashGates for required segments,
  * incomplete S1–S4 workload or missing dictionaries/registries.

* Structural failures (§6.4):

  * schema/PK/partition/order violations in REQUIRED S1–S4 datasets,
  * inability to locate required 6B partitions or artefacts.

* Coverage failures (§6.5):

  * S1–S4 cross-state coverage/identity invariants broken for checks marked REQUIRED.

* Behavioural consistency failures (§6.6):

  * S4 truth/bank labels contradict S3 overlays/6A posture outside allowed thresholds,
  * S3 campaign intensities inconsistent with config.

* RNG envelope failures (§6.7):

  * RNG logs for S1–S4 inconsistent with their policies for REQUIRED checks.

* Bundle & flag failures:

  * `validation_bundle_index_6B` invalid or inconsistent with bundle contents,
  * mismatch between bundle digest and `_passed.flag_6B` digest (on re-run or verification),
  * idempotence violation as per §7.6.

---

### 8.4 Gating obligations for downstream consumers

The primary purpose of S5 is to provide a simple, robust gate for **all downstream consumers** of Layer-3 / 6B outputs.

Binding obligations:

1. **HashGate as the only read gate**

   Any downstream consumer (4A/4B services, model-training/evaluation pipelines, auditing tools that rely on final 6B behaviour) MUST:

   * Locate `validation_bundle_6B` and `_passed.flag_6B` for `manifest_fingerprint`,
   * Recompute the bundle digest from the index (`validation_bundle_index_6B`) and bundle files,
   * Confirm that the recomputed digest equals the digest encoded in `_passed.flag_6B`.

   Only if this check succeeds may they treat 6B outputs for that world as **valid and sealed**.

   This is the binding rule:

   > **No valid `_passed.flag_6B` → no read of Layer-3 / 6B outputs.**

2. **Run-report vs HashGate**

   * Run-report entries for S0–S4 and S5 are helpful for diagnostics but are **not sufficient** by themselves to authorise consumption.
   * If S5 reports `overall_status="PASS"` but `_passed.flag_6B` is missing or digest mismatch occurs, consumers MUST treat the world as **unvalidated** and MUST NOT read 6B outputs.

3. **Cross-layer gating**

   * Higher-level systems that already gate on upstream HashGates (e.g. Layer-2, 6A) MUST add `_passed.flag_6B` as an additional requirement for any workload that depends on 6B outputs (flows, overlays, labels, cases).
   * For cross-layer analytics, all relevant segment HashGates (e.g. `_passed.flag_5B`, `_passed.flag_6A`, `_passed.flag_6B`) MUST pass.

4. **Use of S5 reports & issues**

   * Consumers MAY read `s5_validation_report_6B` and `s5_issue_table_6B` for:

     * detailed diagnostics,
     * automated alerts (e.g. drop worlds where detection rate is too low),
     * manual inspection.

   * These reports MUST be treated as **informational** with respect to correctness; the authoritative PASS/FAIL for gatekeeping is the success of the HashGate verification (`bundle digest == flag digest` and `overall_status` consistent with policy).

---

### 8.5 Obligations for orchestrators & ops tooling

Orchestration and operations tooling MUST:

* Only mark a world as “6B ready” / “Layer-3 ready” when:

  * S5 has run and produced `s5_validation_report_6B` for that `manifest_fingerprint`,
  * `_passed.flag_6B` exists and matches the bundle digest.

* Clearly distinguish:

  * worlds where S5 has **not yet run**,
  * worlds where S5 has run but **overall_status != "PASS"`** (and thus no flag was written),
  * worlds where S5 has PASSed and `_passed.flag_6B` matches the bundle digest.

Any automation that promotes worlds into training/eval or production-like evaluation MUST incorporate the S5 HashGate as a required condition.

---

In summary:

* S5’s acceptance criteria are defined by structural, coverage, behavioural, and RNG checks over S0–S4 and upstream HashGates.
* The **only** signal that a world is valid for 6B is a **consistent validation bundle and `_passed.flag_6B`**.
* All downstream consumers and orchestrators MUST honour this gate: if the flag is missing or invalid, the world is *not* safe to use, regardless of S0–S4 self-reported statuses.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical failure modes** for 6B.S5 and the **error codes** that MUST be used when they occur.

For any world (`manifest_fingerprint`) that S5 attempts to validate, S5 MUST:

* End with exactly one world-level `overall_status` in `s5_validation_report_6B`: `"PASS"`, `"WARN"`, or `"FAIL"`.
* If `overall_status="FAIL"`, record a **primary error code** from this section, and MAY record additional **secondary error codes** for detail.

Downstream systems (orchestrators, 4A/4B, model-training/eval) MUST treat any world where:

* `_passed.flag_6B` is **missing** or
* HashGate verification fails,

as **not sealed / not validated**, regardless of which error code is set.

---

### 9.1 Error model & reporting

* **Primary error code**

  * A single code from the enumeration below that best captures the **root cause** of world-level failure.
  * Example: `S5_SCHEMA_OR_PK_VIOLATION`.

* **Secondary error codes** (optional)

  * A list of additional codes that capture other detected issues; these are **supplementary**, not the main cause.
  * Example: `[ "S5_CHAIN_COVERAGE_VIOLATION", "S5_RNG_ENVELOPE_FAILED" ]`.

* **Context fields**

  * S5 MUST record enough metadata in `s5_validation_report_6B` and logs to support debugging:

    * `manifest_fingerprint`
    * `parameter_hash`, `spec_version_6B`
    * Check ids, per-check results, metrics & thresholds
    * (Optional) per-issue coordinates in `s5_issue_table_6B` (seed, scenario_id, flow_id, case_id, etc.)

The choice of primary vs secondary code is part of S5 implementation, but MUST follow the semantics defined below.

---

### 9.2 Preconditions & configuration failures

These failures indicate S5 **never legitimately entered** the full validation workflow for the world.

#### 9.2.1 `S5_PRECONDITION_S0_OR_UPSTREAM_FAILED`

**Definition**
Emitted when the S0 gate or any required upstream HashGate (1A–3B, 5A, 5B, 6A) is missing or invalid for this `manifest_fingerprint`.

**Examples**

* `s0_gate_receipt_6B` or `sealed_inputs_6B` missing or schema-invalid.
* Re-verification shows `_passed.flag_2B` digest does not match the recomputed bundle digest for 2B.
* `s0_gate_receipt_6B.upstream_segments["5B"].status != "PASS"` and S5’s own upstream check confirms 5B’s HashGate is not valid.

**Obligations**

* S5 MUST set `overall_status = "FAIL"`.
* S5 MUST NOT attempt any S1–S4 validation or attempt to seal 6B.
* No `_passed.flag_6B` may be written.

---

#### 9.2.2 `S5_PRECONDITION_SEALED_INPUTS_INCOMPLETE`

**Definition**
Emitted when `sealed_inputs_6B` is present but missing required 6B artefacts or has unrecoverable inconsistencies that prevent S5 from safely validating the world.

**Examples**

* Required S1–S4 datasets for this world are not present as rows in `sealed_inputs_6B` with appropriate `status` (`REQUIRED`) and `schema_ref`.
* `sealed_inputs_6B` lists an artefact with a `schema_ref` that does not resolve to any known schema, making it impossible to validate that dataset.
* Digest recorded in `sealed_inputs_6B` cannot be recomputed or does not match actual stored files, and policy marks this as fatal.

**Obligations**

* S5 MUST set `overall_status = "FAIL"`.
* No `_passed.flag_6B` may be written.
* Operators MUST repair sealed inputs and/or upstream data before re-running S5.

---

#### 9.2.3 `S5_PRECONDITION_VALIDATION_POLICY_INVALID`

**Definition**
Emitted when `segment_validation_policy_6B` is missing, schema-invalid, or internally inconsistent.

**Examples**

* Policy file missing from `sealed_inputs_6B`.
* Policy does not conform to `schemas.layer3.yaml#/validation/6B/segment_validation_policy` (e.g. missing required `checks` array).
* Policy references unknown `check_id`s or uses invalid severity values (`"CRITICAL"` when only `"REQUIRED"/"WARN_ONLY"/"INFO"` are allowed).

**Obligations**

* S5 MUST NOT run checks with an undefined or invalid policy.
* S5 MUST set `overall_status = "FAIL"` and leave `_passed.flag_6B` absent.

---

### 9.3 Structural validation failures (S1–S4)

These indicate S5 found **schema/PK/partition/order violations** in 6B datasets.

#### 9.3.1 `S5_SCHEMA_OR_PK_VIOLATION`

**Definition**
Emitted when any REQUIRED S1–S4 dataset fails **schema validation** or **primary key/partition/order rules** for the world.

**Examples**

* `s1_arrival_entities_6B` has rows that do not conform to `schemas.6B.yaml#/s1/arrival_entities_6B` (missing required fields, wrong types).
* Duplicated primary keys in `s2_flow_anchor_baseline_6B` or `s3_flow_anchor_with_fraud_6B`.
* `seed`, `manifest_fingerprint` or `scenario_id` columns in S3 partitions do not match their path tokens.
* `event_seq` in S2/S3/S4 is not contiguous or not strictly monotone within a flow, where specification requires it.

**Obligations**

* S5 MUST mark the relevant check(s) as FAIL.
* If such checks are marked REQUIRED in the validation policy, S5 MUST set `overall_status = "FAIL"` and MUST NOT seal the world.

---

### 9.4 Cross-state coverage & chain integrity failures

These indicate **coverage/identity mismatches** across S1–S4 (the “chain” is broken).

#### 9.4.1 `S5_CHAIN_COVERAGE_VIOLATION`

**Definition**
Emitted when S5 detects that cross-state invariants between S1→S2→S3→S4 are violated for REQUIRED checks.

**Examples**

* Some arrivals from S1 (entities/sessions) never appear in S2 baseline flows when S2 spec requires full coverage.
* Some baseline flows from S2 do not appear in S3 overlays (neither as baseline nor mutated flows) when S3 spec requires full coverage.
* Some `flow_id`s in S3 overlays have no labels in S4 (`s4_flow_truth_labels_6B` / `s4_flow_bank_view_6B`).
* Some events in S3 overlays are not present in `s4_event_labels_6B`.

**Obligations**

* S5 MUST record this as a FAILED chain integrity check.
* If the validation policy marks this check as REQUIRED, S5 MUST set `overall_status = "FAIL"` and no `_passed.flag_6B` may be written.

---

### 9.5 Behavioural & label consistency failures

These indicate S5’s **behavioural checks** have failed.

#### 9.5.1 `S5_BEHAVIOURAL_CONSISTENCY_FAILED`

**Definition**
Emitted when high-level behavioural consistency checks across S3/S4 and 6A posture indicate violations of REQUIRED invariants.

**Examples**

* A material fraction of flows labelled `LEGIT` in S4 exhibit S3 overlay patterns that the policy only allows in `FRAUD` flows.
* Flows labelled as fraud/abuse in S4 that have no plausible fraud pattern (either in S3 overlays or 6A posture), contradicting configured labelling rules.
* Fraud/abuse patterns appear on entities whose 6A posture prohibits such patterns (e.g. flows labelled `MULE_ACTIVITY` for accounts not allowed to be mules).

**Obligations**

* S5 MUST record the failing checks and metrics.
* If those checks are REQUIRED, S5 MUST set `overall_status = "FAIL"`.

---

#### 9.5.2 `S5_CAMPAIGN_INTEGRITY_FAILED`

**Definition**
Emitted when discrepancies between S3 campaign catalogue and overlays violate REQUIRED campaign checks.

**Examples**

* `s3_campaign_catalogue_6B` claims `target_flow_count=100` for a campaign, but only 10 flows in S3 overlays reference its `campaign_id`.
* Campaign templates marked as “must fire” have zero realised targets, while S3 overlays still appear to reflect partial execution.
* Campaign types appear in overlays with `campaign_id` values not present in the catalogue, or `campaign_type`/`fraud_pattern_type` mismatches according to config.

**Obligations**

* S5 MUST consider campaign integrity checks as FAIL and, if REQUIRED, treat the world as FAIL.

---

#### 9.5.3 `S5_LABEL_INTEGRITY_FAILED`

**Definition**
Emitted when S4 truth and bank-view labels materially contradict each other, S3 overlays, or S4 policies beyond allowed tolerances.

**Examples**

* A large fraction of flows with S3 fraud patterns are labelled `LEGIT` in S4, far outside allowed threshold.
* Bank-view labels (e.g. detection outcomes) contradict S4 truth labels and `bank_view_policy_6B` in systematic ways (e.g. `BANK_CONFIRMED_FRAUD` on `LEGIT` flows).
* Case timelines that contradict bank-view outcomes at the summary level (e.g. cases closed as “no fraud” while underlying flows are labelled `FRAUD` and vice versa).

**Obligations**

* S5 MUST record these as FAILED label-consistency checks.
* If REQUIRED by policy, S5 MUST set `overall_status = "FAIL"`.

---

### 9.6 RNG envelope & accounting failures

These indicate S5’s RNG checks on S1–S4 have failed.

#### 9.6.1 `S5_RNG_ENVELOPE_FAILED`

**Definition**
Emitted when, for one or more S1–S4 states and RNG families, actual RNG usage deviates from the configured envelope.

**Examples**

* Observed Philox draws for `rng_event_flow_shape` in S2 are significantly more or fewer than expected given the number of flows, violating that state’s RNG policy.
* S1 consumes RNG for deterministic cases where policy states “no draws when probability is 0 or 1”.
* RNG usage has unexplained gaps or spikes inconsistent with the domain size and state-specific policies.

**Obligations**

* S5 MUST mark the relevant RNG checks as FAIL.
* If envelope checks are REQUIRED, `overall_status` MUST be set to `"FAIL"`.

---

#### 9.6.2 `S5_RNG_LOG_INCONSISTENT`

**Definition**
Emitted when S5 detects structural inconsistencies in RNG logs or trace summaries.

**Examples**

* RNG logs missing for a state that is supposed to be consuming RNG.
* Non-monotone or overlapping Philox counter ranges for logically separate families/streams.
* RNG trace records conflict with state-reported budgets (e.g. trace says 100 draws, state-run-report says 50).

**Obligations**

* S5 MUST treat these as FAILED RNG checks.
* If REQUIRED, world MUST be considered FAIL.

---

### 9.7 Bundle & HashGate failures

These indicate issues building or verifying the S5 validation bundle and flag.

#### 9.7.1 `S5_BUNDLE_INDEX_INVALID`

**Definition**
Emitted when `validation_bundle_index_6B` (index `items`) is malformed or inconsistent with its schema.

**Examples**

* `index.json` missing required fields (`manifest_fingerprint`, `items`).
* Duplicate `path` entries in `items`.
* `items` not sorted ASCII-lex by `path`.
* `sha256_hex` fields not valid 64-char lowercase hex strings.

**Obligations**

* S5 MUST not attempt to write or rely on `_passed.flag_6B`.
* `overall_status` MUST be at least `"FAIL"` (or `"WARN"` only if policy explicitly allows an unsealed world, but then still no flag).

---

#### 9.7.2 `S5_BUNDLE_DIGEST_MISMATCH`

**Definition**
Emitted when recomputing the bundle digest over `validation_bundle_index_6B.items` and underlying files does not match the digest S5 expects (e.g. recomputed vs previously stored).

**Examples**

* Index lists a file with digest `X`, but recomputation over file bytes yields `Y != X`.
* On re-run, S5’s freshly computed digest for the bundle does not match the digest previously used to build `_passed.flag_6B`.

**Obligations**

* S5 MUST treat the bundle as corrupted or changed.
* S5 MUST NOT seal the world (no `_passed.flag_6B` should be considered valid).
* If a flag already exists and digest mismatch is confirmed, S5 MUST treat this as a severe integrity error.

---

#### 9.7.3 `S5_FLAG_DIGEST_MISMATCH`

**Definition**
Emitted when `_passed.flag_6B` exists but its `sha256_hex` value does not match the recomputed bundle digest.

**Examples**

* `_passed.flag_6B` claims `sha256_hex = abc...`, but recomputed digest over `index.items` yields `def...`.
* Flag file modified out-of-band after the bundle was written.

**Obligations**

* S5 MUST consider the world unsealed; `_passed.flag_6B` cannot be trusted.
* Downstream consumers MUST treat this as a gate failure.
* `overall_status` MUST be `"FAIL"`.

---

#### 9.7.4 `S5_IDEMPOTENCE_VIOLATION`

**Definition**
Emitted when, under unchanged inputs and contract, a re-run of S5 would produce a **different bundle** or digest than already exists for the world.

**Examples**

* S5 recomputes checks and would produce additional issues or different metrics, but an older bundle/flag has already been written.
* Multiple S5 runs under conflicting configuration produced different bundles, leaving ambiguous ground truth.

**Obligations**

* S5 MUST NOT overwrite the existing bundle or flag.
* `overall_status` MUST be `"FAIL"` for the re-run, with this code as primary.
* Operators MUST resolve the version/config drift explicitly (e.g. by bumping `spec_version_6B` or parameter_hash and rebuilding).

---

### 9.8 Output write & internal failures

#### 9.8.1 `S5_OUTPUT_WRITE_FAILED`

**Definition**
Emitted when S5 encounters an I/O or storage error while writing any of its outputs (report, issue table, bundle index, or flag).

**Examples**

* Filesystem error writing `s5_validation_report_6B.json`.
* Network/storage failure during `index.json` write.
* Permission or quota errors writing `_passed.flag_6B`.

**Obligations**

* S5 MUST set `overall_status = "FAIL"`.
* Any partially written S5 artefacts MUST be treated as invalid by orchestrators and gate checkers.

---

#### 9.8.2 `S5_INTERNAL_ERROR`

**Definition**
Catch-all for unexpected runtime failures not captured by other error codes:

* e.g. unhandled exceptions, assertion failures, impossible control paths, internal logic bugs.

**Examples**

* Null pointer or type error in S5 implementation.
* Unexpected schema/calc assumption violation not yet formalised as a specific check.

**Obligations**

* S5 MUST set `overall_status = "FAIL"`.
* Implementations SHOULD log full diagnostic information so that recurring issues can be mapped to more specific codes in future revisions.

---

### 9.9 Surfaces & propagation

For any world where S5 sets `overall_status="FAIL"`:

* `s5_validation_report_6B` MUST:

  * include the chosen `primary_error_code`,
  * include any relevant `secondary_error_codes`,
  * record all FAILED (and WARN) checks with metrics so operators know what went wrong.

* `s5_issue_table_6B` (if produced) SHOULD:

  * enumerate specific issues (per check, per partition/flow/case) where relevant.

Downstream obligations:

* Orchestrators MUST treat S5 failure as a block for promoting the world into training/eval pipelines.
* Gate checkers MUST ensure that either:

  * `_passed.flag_6B` is absent, or
  * HashGate verification fails,

and therefore treat the world as unsealed.

These error codes and their semantics are an explicit part of S5’s contract and MUST be adhered to by any implementation and consumer of S5 outputs.

---

## 10. Observability & run-report integration *(Binding)*

This section defines **what S5 must expose for observability**, and **how its verdict and checks must appear in the engine run-report**, so that:

* Operators and tooling can understand *why* a world passed or failed.
* Downstream “gate checkers” and orchestrators can make **machine-readable decisions** about world readiness.

All requirements in this section are **binding** for 6B.S5.

---

### 10.1 Run-report keying & scope

S5 is **world-scoped**. For each `manifest_fingerprint` that S5 evaluates, the Layer-3 run-report **MUST** contain exactly one S5 entry:

* `segment` = `"6B"`
* `state`   = `"S5"`
* `manifest_fingerprint`
* `status` — `"PASS"`, `"WARN"`, or `"FAIL"` (mirrors `overall_status` in `s5_validation_report_6B`)
* `primary_error_code` — one of the S5 error codes from §9, or `null` if `status ∈ {"PASS","WARN"}`
* `secondary_error_codes` — array of additional error codes (possibly empty)

S5’s run-report entry is **per world**:

* There MUST NOT be more than one S5 entry for the same `(manifest_fingerprint, spec_version_6B)` in a single run-report.
* S5 MUST NOT emit per-seed or per-scenario S5 status entries; those dimensions are summarised inside the world-level report.

---

### 10.2 Required summary fields in S5’s run-report entry

The S5 run-report entry for a world **MUST** include a summary block that mirrors the contents of `s5_validation_report_6B`. At minimum:

1. **Overall verdict & metadata**

   * `overall_status` — `"PASS"`, `"WARN"`, `"FAIL"`.
   * `parameter_hash` — as recorded in S0 and used during validation.
   * `spec_version_6B` — 6B contract version under which S5 ran.
   * `bundle_flag_present: boolean` — `true` iff `_passed.flag_6B` exists for this fingerprint.
   * `bundle_flag_valid: boolean` — `true` iff `_passed.flag_6B` digest matches the recomputed bundle digest.

2. **Upstream segment summary**

   * `upstream_segment_summary` — map:

     ```json
     {
       "1A": { "status": "PASS"|"FAIL"|"MISSING", "bundle_sha256": "<hex-or-null>" },
       "1B": { ... },
       "2A": { ... },
       "2B": { ... },
       "3A": { ... },
       "3B": { ... },
       "5A": { ... },
       "5B": { ... },
       "6A": { ... }
     }
     ```

   This MUST reflect S5’s re-verification of upstream HashGates, not just S0’s opinion.

3. **6B state summary (S0–S4)**

   * `segment_state_summary` — map such as:

     ```json
     {
       "S0": "PASS"|"WARN"|"FAIL",
       "S1": "PASS"|"WARN"|"FAIL",
       "S2": "PASS"|"WARN"|"FAIL",
       "S3": "PASS"|"WARN"|"FAIL",
       "S4": "PASS"|"WARN"|"FAIL"
     }
     ```

   This is S5’s **aggregated view** over all `(seed, scenario_id)` partitions (e.g. S3 considered FAIL if any partition-level S3 check is REQUIRED-FAIL).

4. **Check result summary**

   * `check_summary` — array or map summarising each check by `check_id`:

     At minimum, for each check:

     ```json
     {
       "check_id": "CHK_S4_LABEL_COVERAGE",
       "severity": "REQUIRED"|"WARN_ONLY"|"INFO",
       "result": "PASS"|"WARN"|"FAIL"
     }
     ```

   Optionally, S5 MAY include high-level metrics per check (e.g. detection rate, coverage ratios) here; those are already present in `s5_validation_report_6B` but can be echoed into the run-report for convenience.

5. **Key metrics**

   At least a handful of **headline metrics** MUST be present, such as:

   * `flows_total` — total number of flows in S3 overlays across all partitions.
   * `events_total` — total number of events in S3 overlays.
   * `fraud_flows_truth_total` — total number of S4 flows with `truth_label` in the fraud family.
   * `fraud_flows_detected_total` — number of those flows with detection outcome ≠ `NOT_DETECTED`.
   * `fraud_detection_rate_global` — derived fraction.
   * `cases_total` — total number of cases in `s4_case_timeline_6B`.

These metrics are cross-checked against S4/S3 metrics to ensure S5’s view is consistent.

---

### 10.3 Logging requirements

S5 MUST emit structured logs that make its operation traceable.

At minimum, for each `manifest_fingerprint`:

1. **S5 start**

   * `event_type: "6B.S5.START"`
   * `manifest_fingerprint`
   * `parameter_hash`
   * `spec_version_6B`

2. **Precondition check**

   * `event_type: "6B.S5.PRECONDITION_CHECK"`

   * Fields indicating:

     * `s0_present: bool`, `s0_schema_ok: bool`,
     * `sealed_inputs_ok: bool`,
     * `upstream_hashgates_ok: bool`,
     * `workload_complete_6B: bool` (all S1–S4 partitions reported).

   * If preconditions fail, this log entry MUST include `primary_error_code` (e.g. `S5_PRECONDITION_S0_OR_UPSTREAM_FAILED`).

3. **Structural validation summary**

   * `event_type: "6B.S5.STRUCTURAL_SUMMARY"`
   * For each 6B dataset family (S1–S4):

     * `dataset_id`,
     * `structural_checks_passed: int`,
     * `structural_checks_failed: int`,
     * optional counts of partitions/files checked.

4. **Coverage & chain summary**

   * `event_type: "6B.S5.CHAIN_SUMMARY"`
   * Summaries of S1→S2→S3→S4 coverage checks:

     * `coverage_checks_passed`, `coverage_checks_failed`,
     * key ratios: flows/events expected vs present at each step.

5. **Behavioural & label checks summary**

   * `event_type: "6B.S5.BEHAVIOURAL_SUMMARY"`
   * A list or map of important behavioural checks (`check_id` → result).
   * Headline metrics (fraud rates, detection rates, etc.) as used in those checks.

6. **RNG envelope summary**

   * `event_type: "6B.S5.RNG_SUMMARY"`
   * For each S1–S4 RNG family checked:

     * `state_id`, `rng_family`,
     * `expected_draws`, `actual_draws`,
     * `result` ("PASS"/"WARN"/"FAIL").

7. **Bundle & flag write summary**

   * `event_type: "6B.S5.BUNDLE_AND_FLAG"`
   * Fields:

     * `bundle_written: bool`,
     * `index_written: bool`,
     * `flag_written: bool`,
     * `bundle_digest_sha256`,
     * `flag_sha256` (from `_passed.flag_6B`, if present),
     * `flag_matches_bundle: bool`.

8. **S5 end**

   * `event_type: "6B.S5.END"`
   * `manifest_fingerprint`
   * `overall_status` (`"PASS"|"WARN"|"FAIL"`),
   * `primary_error_code` (if `overall_status="FAIL"`),
   * `secondary_error_codes` (if any).

These logs MUST be sufficient for an operator to reconstruct **what S5 checked**, **what it found**, and **why it failed or passed** for a world.

---

### 10.4 Metrics & SLI/monitoring

S5 SHOULD expose metrics suitable for SLI/SLO monitoring. The **shape and semantics** below are binding; thresholds/alerts are operational.

Indicative metrics:

* `6B_S5_worlds_validated_total`

  * Counter; labels: `status ∈ {"PASS","WARN","FAIL"}`.

* `6B_S5_checks_total`

  * Counter; labels: `check_id`, `result ∈ {"PASS","WARN","FAIL"}`.

* `6B_S5_structural_failures_total`

  * Counter; label: `state ∈ {"S1","S2","S3","S4"}`.

* `6B_S5_chain_coverage_failures_total`

  * Counter; label: `check_id` (e.g. `CHK_CHAIN_S2_S3`, `CHK_CHAIN_S3_S4`).

* `6B_S5_rng_failures_total`

  * Counter; labels: `state`, `rng_family`.

* `6B_S5_bundle_flag_mismatch_total`

  * Counter; increments whenever `S5_BUNDLE_DIGEST_MISMATCH` or `S5_FLAG_DIGEST_MISMATCH` occurs.

* `6B_S5_validation_runtime_seconds`

  * Histogram or summary; measures elapsed wall time per world.

When these metric names are used, they MUST have the semantics described above.

---

### 10.5 Downstream consumption of S5 observability

**Orchestrators & gate checkers MUST:**

* Use S5’s run-report entry in conjunction with bundle/flag verification to determine world readiness.

  * If `overall_status="FAIL"` or `_passed.flag_6B` is missing/invalid, world is *not ready*.
  * If `overall_status ∈ {"PASS","WARN"}` and `_passed.flag_6B` is valid (bundle digest matches flag), world is *sealed* and eligible for consumption (subject to any WARN-handling policy in the consuming system).

**4A/4B & model-training/evaluation MUST:**

* Treat S5’s metrics in the run-report as **diagnostic**, not as the gating mechanism.
* Gate actual use of 6B outputs strictly on `_passed.flag_6B` digest verification as described in §8.4 and §7.8.

**Ops and tooling MAY:**

* Use:

  * `s5_validation_report_6B`,
  * `s5_issue_table_6B`,
  * S5 logs and metrics,

  to prioritise investigations, track global health (e.g. how often worlds fail and why), and fine-tune `segment_validation_policy_6B` and upstream configs.

---

### 10.6 Traceability & audit trail

The combination of:

* S5 outputs (`s5_validation_report_6B`, `s5_issue_table_6B`, `validation_bundle_6B`, `_passed.flag_6B`),
* references to S0–S4 surfaces in the bundle index,
* S5 logs and metrics,

MUST allow an auditor or operator to answer, for any world:

* Which checks were run?
* Which checks were WARN/FAIL, with what metrics?
* Were upstream HashGates and 6B HashGate (`_passed.flag_6B`) consistent?
* Why did this world PASS/WARN/FAIL overall?

Because S5 is the **final trust anchor** for Segment 6B, emitting its run-report entry, logs and metrics as described here is **not optional** — it is part of the binding contract that ensures downstream systems can safely and transparently depend on the 6B HashGate.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on how to keep S5 cheap, predictable, and safe as the engine scales. It does **not** relax any binding constraints in §§1–10; it only suggests sensible implementation strategies within those constraints.

---

### 11.1 Role of S5 in the pipeline

S5 is fundamentally:

* **Metadata-heavy, data-light**: it reads a lot of **catalogue and summary information** and only small slices of 6B data-plane tables.
* **World-scoped, not partition-scoped**: one S5 run per `manifest_fingerprint`, not per `(seed, scenario_id)`.
* **Read-only**: it never mutates S0–S4 or upstream outputs.

So the cost profile is:

* dominated by:

  * loading schemas, dictionaries, registries,
  * reading S1–S4 **summaries** / small projections and RNG logs,
  * computing digests for S5 evidence files;
* small compared to:

  * heavy data-plane jobs in S2/S3 (flows, overlays) or upstream layers.

---

### 11.2 Rough complexity model

For a world with:

* `N_partitions` = number of `(seed, scenario_id)` partitions in scope,
* `N_flows` = total flows in S3 overlays across partitions,
* `N_events` = total events in S3 overlays,
* `N_checks` = number of S5 check definitions,

a typical (non-optimised) S5 cost looks like:

```text
Time ≈ O(#catalogue_entries + #validation_files) 
     + O(N_checks × N_partitions) 
     + O(#files_in_bundle_for_digest)

Space ≈ O(size_of_check_context + size_of_issue_table_for_world)
```

Key points:

* S5 **does not need to scan all rows** in every S1–S4 dataset: it can rely on:

  * per-partition metrics gathered by S1–S4 (run-report),
  * targeted sample checks where policy allows,
  * relation-level consistency checks (joining keys without heavy row inspection).
* Full-row scans should be reserved for a small subset of datasets where absolutely necessary and configured as REQUIRED checks.

---

### 11.3 Scoping & incremental validation strategy

A practical implementation can structure S5 in layers:

1. **Cheap, broad checks first**

   * Validate S0, upstream HashGates, and `sealed_inputs_6B`.
   * Validate schemas and PK/partitioning for S1–S4 datasets at the **schema-level and metadata-level** (e.g. using column statistics, file manifest) rather than scanning entire data.

2. **Coverage & consistency at summary level**

   * Use S1–S4 run-report metrics for quick coverage checks (e.g. comparing counts across stages).
   * Only dive into row-level details if summary metrics indicate a problem or as required by the validation policy.

3. **Selective deep dives**

   * Behavioural checks (truth/campaign/labels consistency) can often be done:

     * via summarised tables generated by S3/S4, or
     * via **sampling** (if the policy explicitly allows approximate checks) rather than validating every row.
   * RNG envelope checks can typically operate on RNG log **aggregates** (e.g. per-family counters) rather than enumerating every RNG event.

This layered approach keeps S5 performant, with the option to dial up depth when debugging or in “strict audit” modes.

---

### 11.4 Use of sampling vs full scans

By default, S5 is framed as **exact**: all checks are deterministic and can inspect all relevant rows. In practice:

* **Exact checks** are recommended for:

  * schema/PK/partition/order checks on S1–S4,
  * bundle/index/flag checks,
  * RNG draw counts (these are usually summarised already),
  * key coverage invariants (e.g. 1-to-1 mapping of flows/events).

* **Sampled checks** MAY be allowed by `segment_validation_policy_6B` for **behavioural-level** checks (e.g. verifying that label distributions are in line with expectations), with explicit policy semantics such as:

  * sample at most `k` flows per `(seed, scenario_id)` for deep inspection,
  * treat sampling-based checks as `WARN_ONLY` or `INFO`.

If sampling is used, the policy MUST be explicit about:

* sampling scheme (uniform, stratified),
* sample size per domain,
* how to interpret sampling failures (WARN vs FAIL).

All this remains deterministic (no randomness in S5 itself), e.g. by using hash-based sampling on stable keys.

---

### 11.5 Digest computation & bundle size

Digest computation (per-file SHA-256 + bundle-level SHA-256) is one of the heavier operations in S5, but it scales with **bundle size**, not with the entire 6B data-plane.

Guidance:

* **Keep the validation bundle compact**

  * Bundle **reports, issue tables, RNG summaries, coverage metrics**, and possibly **digests of big datasets**, but avoid:

    * embedding full S3/S4 tables,
    * duplicating large artefacts that are already HashGated upstream.

* **Pre-digest large surfaces upstream**

  * If you want to bind large S3/S4 datasets into the S5 bundle, prefer:

    * including **digests** or **small index/manifest files** for those datasets,
    * rather than including the entire dataset again.

This keeps S5’s digest work constrained to:

```text
Time_digest ≈ O(#files_in_bundle × file_size_for_reports_and_summaries)
```

which should be modest per world.

---

### 11.6 Memory footprint

S5’s memory requirements are dominated by:

* in-memory **check context** (per-check results, metrics),
* the optional **issue table rows** for the world.

The heavy S1–S4 tables do not need to be held entirely in memory:

* Schema/PK/partition checks can be done per-partition file and aggregated;
* Key coverage checks can often be implemented as **streaming joins** over sorted keys;
* Behavioural metrics can be built by streaming over summary surfaces rather than raw flows/events.

Best practices:

* Treat each 6B dataset family (e.g. S2 flows, S3 flows, S3 events) as a stream:

  * read a partition, validate it, emit any issues, discard it,
  * keep only aggregated counters/metrics in memory.

* Limit the size of `s5_issue_table_6B` by:

  * avoiding per-row issues for very large domains, except in debug/audit modes,
  * aggregating similar issues into a single issue row with metrics (e.g. “1000 flows failed S3/S4 coverage check”).

---

### 11.7 Concurrency & throughput

Because S5 is world-scoped, it parallelises well over **different worlds**:

* Run S5 in parallel for multiple `manifest_fingerprint`s, as long as each world has a single S5 writer.

Per world:

* S5 is effectively **single-threaded at the write stage** (to avoid idempotence/merge issues), but:

  * internal validation work (schema checks, coverage checks) may be parallelised across dataset families or `(seed, scenario_id)` partitions,
  * as long as:

    * intermediate results are merged deterministically,
    * there is a single logical bundle/index/flag built at the end.

In typical deployments:

* S5 will not be the performance bottleneck; the heavy lifting is done by S1–S4.
* Nonetheless, it is good practice to:

  * limit per-world validation time to a reasonable bound (e.g. seconds–few minutes),
  * monitor S5 runtime via `6B_S5_validation_runtime_seconds` and investigate outliers.

---

### 11.8 Monitoring S5’s health

From an operations perspective, you want to track:

* How many worlds:

  * PASS, WARN, FAIL (`6B_S5_worlds_validated_total`),
  * fail for structural reasons (`S5_SCHEMA_OR_PK_VIOLATION`),
  * fail for chain coverage reasons (`S5_CHAIN_COVERAGE_VIOLATION`),
  * fail for RNG envelope reasons (`S5_RNG_ENVELOPE_FAILED`), etc.

* How often:

  * bundle/flag mismatches occur (`6B_S5_bundle_flag_mismatch_total`),
  * idempotence violations happen (`S5_IDEMPOTENCE_VIOLATION`).

Red flags:

* High incidence of **precondition failures** → issues upstream (S0/sealed inputs or upstream HashGates).
* Frequent **chain coverage failures** → systemic drift between S1–S4 contracts and implementations.
* RNG failures in S5 → S1–S4 using RNG in ways that violate their contracts.

These signals help you decide whether to tighten or relax validation policies and guide debugging efforts.

---

### 11.9 Parallelism vs determinism

As with other segment states:

> **Parallelism is allowed; non-determinism is not.**

S5-specific guardrails:

* Internal parallelisation MUST use deterministic partitioning and merge strategies (e.g. process per `(seed, scenario_id)` in any order, but record per-check metrics via commutative aggregates and sort outputs deterministically).
* Do **not** parallelise digest computation in ways that depend on non-deterministic file ordering; always sort by `path` first.

Practical test:

* Run S5 twice on the same world with identical inputs and configs.
* If the validation report, issue table, bundle index, and flag differ in any way (including ordering), your implementation is violating this spec and MUST be corrected.

---

In summary:

* S5 is intentionally cheap and world-scoped: one run per world, mostly metadata work.
* Scalability comes from careful use of summaries, streaming checks, and compact bundles, not from heavy data-plane reprocessing.
* Determinism and idempotence are non-negotiable: performance optimisations are fine as long as they do not change any of the guarantees in §§1–10.

---

## 12. Change control & compatibility *(Binding)*

This section defines how the **6B.S5 contract may evolve**, and what changes are considered **backwards-compatible** vs **breaking**.

It is binding on:

* authors of future S5 specs,
* implementers of S5, and
* downstream consumers (orchestrators, 4A/4B, model-training/eval, gate checkers).

The goals are:

* existing worlds remain **replayable**,
* every `_passed.flag_6B` remains **verifiable** over time, and
* consumers can safely rely on S5’s semantics for gating.

---

### 12.1 Versioning surfaces relevant to S5

S5 participates in the following version tracks:

1. **`spec_version_6B`**

   * Contract version for Segment 6B as a whole (S0–S5).
   * Recorded in `s0_gate_receipt_6B` and in S5 artefacts (report, index).
   * Drives which checks and artefact shapes S5 is expected to honour.

2. **Schema packs**

   * `schemas.layer3.yaml`, containing S5 anchors:

     * `#/validation/6B/s5_validation_report`
    * `#/validation/6B/validation_issue_table_6B`
     * `#/validation/6B/validation_bundle_index_6B`
     * `#/validation/6B/passed_flag_6B`
   * Optionally `schemas.6B.yaml` if any S5-specific shapes live there instead.

3. **Catalogue entries**

   * `dataset_dictionary.layer3.6B.yaml` entries for:

     * `s5_validation_report_6B`
     * `s5_issue_table_6B`
     * `validation_bundle_6B` (index)
     * `validation_passed_flag_6B`
   * `artefact_registry_6B.yaml` entries for the same.

4. **Validation policy**

   * `segment_validation_policy_6B` — declares which checks S5 runs, their severity, and PASS/WARN/FAIL rules.

**Binding rule:**

For any world, the tuple:

```text
(spec_version_6B, schemas.layer3.yaml version, segment_validation_policy_6B version)
```

MUST be internally consistent and discoverable via catalogues and S0. S5 MUST treat this triple as the contract it is validating under.

---

### 12.2 Backwards-compatible changes

A change to S5 is **backwards-compatible** if:

* Existing consumers and gate checkers can still:

  * parse S5 artefacts (`s5_validation_report_6B`, `s5_issue_table_6B`, `index.json`, `_passed.flag_6B`), and
  * rely on the identity, partitioning, and hashing law described in §§4–8,

**without** changing their logic.

Examples of allowed backwards-compatible changes:

1. **Additive, optional schema fields**

   * Adding **optional** fields to `s5_validation_report_6B`:

     * e.g. extra summary metrics, additional metadata about tool versions or environment.
   * Adding **optional** fields to `s5_issue_table_6B`:

     * e.g. extra context columns for issues.
   * Adding **optional** fields to `validation_bundle_index_6B.items`:

     * e.g. `size_bytes`, extra `tags`, as long as `path` and `sha256_hex` semantics and ordering remain unchanged.

2. **Additional checks with non-fatal severity**

   * Adding new checks in `segment_validation_policy_6B` with severity `INFO` or `WARN_ONLY`:

     * they can increase the richness of `s5_validation_report_6B` and `s5_issue_table_6B`,
     * but they MUST NOT change world PASS/FAIL outcomes for existing worlds where all REQUIRED checks remain passing.

3. **Stronger internal diagnostics**

   * Writing additional **evidence files** into `validation_bundle_6B` and listing them in the index, as long as:

     * the hashing law remains **path-sorted concatenation → SHA-256**,
     * existing consumers that only check the digest don’t need to interpret new files.

4. **Implementation optimisations**

   * Changing internal algorithms (parallelisation, streaming vs batch, etc.) while:

     * respecting the deterministic algorithm contract, and
     * producing identical outputs (report/index/flag) for unchanged inputs.

Backwards-compatible changes MAY be introduced under the same `spec_version_6B` or via a minor bump (e.g. `1.0.0 → 1.1.0`), as long as the external contract in §§4–8 is not violated.

---

### 12.3 Breaking changes

A change is **breaking for S5** if it can:

* cause existing gate checkers to misinterpret S5 artefacts,
* cause `_passed.flag_6B` verification to behave differently for the same bundle, or
* change what “PASS vs FAIL” means for a world under the same `spec_version_6B`.

Breaking changes **MUST** be accompanied by a **new major** `spec_version_6B` and corresponding schema/catalogue updates.

Examples of breaking changes:

1. **Changing the hashing law or flag semantics**

   * Changing how the bundle digest is computed:

     * different hash function (e.g. SHA-256 → SHA-512),
     * different concatenation order (e.g. not sorted by `path`),
     * including/excluding different files without updating the index semantics.
   * Changing the meaning or format of `_passed.flag_6B` (e.g. additional fields or different line format) such that existing verifiers could mis-parse it.

2. **Changing index semantics**

   * Removing or redefining `path` or `sha256_hex` fields.
   * Allowing duplicate `path` values in `items`.
   * Dropping the requirement that `items` be sorted by `path`.

3. **Changing identity/partitioning of S5 artefacts**

   * Moving S5 outputs out of the `fingerprint={manifest_fingerprint}` partitioning scheme (e.g. adding `seed` as a partition axis).
   * Allowing multiple `s5_validation_report_6B` or `_passed.flag_6B` for the same `(manifest_fingerprint, spec_version_6B)`.

4. **Changing PASS/WARN/FAIL semantics for existing checks**

   * Modifying `segment_validation_policy_6B` so that:

     * a world previously considered PASS would now be FAIL (or vice versa),
     * without changing `spec_version_6B` or clearly updating the contract for checks and severities.

   * Reclassifying a check from `WARN_ONLY` to `REQUIRED` **without** a new spec version and migration guidance.

5. **Removing or renaming required checks**

   * Removing a REQUIRED check from the policy or repurposing it in a way that breaks consumers expecting its previous semantics.

Any such change MUST:

* bump `spec_version_6B`,
* update relevant schemas and catalogues, and
* be reflected in S5’s own spec and in consumer documentation.

---

### 12.4 Interaction with `parameter_hash` & reproducibility

S5’s outputs are deterministic for fixed inputs, including `parameter_hash`:

> For fixed `(manifest_fingerprint, parameter_hash, spec_version_6B)` and fixed upstream S0–S4 outputs and policies, S5 artefacts (report, issue table, bundle index, flag) MUST be reproducible.

Implications:

* Changes to S1–S4 behaviour or 6B configuration that affect validation outcomes MUST be expressed via:

  * a new `parameter_hash` (different config pack), and/or
  * a new `spec_version_6B` for contract-level changes.

* It is **not acceptable** to:

  * silently change S1–S4 or validation policies while keeping the same `(manifest_fingerprint, parameter_hash, spec_version_6B)`,
  * re-run S5 and accept a different bundle/flag as “idempotent”.

If such a situation occurs, S5 MUST detect and report `S5_IDEMPOTENCE_VIOLATION` (see §9.7.4), and MUST NOT overwrite existing S5 artefacts.

---

### 12.5 Upstream dependency evolution (S0–S4 & HashGates)

S5 depends on:

* the contracts and HashGates of upstream segments (1A–3B, 5A, 5B, 6A), and
* the contracts of S0–S4 and their datasets.

Binding rules:

1. **Upstream additive changes**

   * Upstream segments MAY add optional fields or new evidence files to their own validation bundles, without affecting S5, if:

     * existing `index.json` and `_passed.flag_*` semantics are preserved, and
     * S5’s re-verification logic still sees the same digest match.

   * S5 MAY ignore newly added upstream evidence files or incorporate them as additional sanity checks.

2. **Upstream breaking changes**

   * Changing upstream hashing laws, flag formats, or the meaning of PASS/FAIL for upstream HashGates is **breaking for S5**’s re-verification logic.
   * Changing S0–S4 contracts (schemas, partitioning, invariants) is breaking for the corresponding checks in S5.

   Such changes MUST be coordinated:

   * upstream specs & code updated,
   * S5 spec and `segment_validation_policy_6B` updated,
   * `spec_version_6B` bumped, and
   * consumer gate-checking logic updated if they re-verify upstream.

3. **New 6B checks based on new upstream artefacts**

   * If new upstream surfaces or 6B datasets are introduced, S5 MAY add new OPTIONAL checks around them without breaking existing behaviour (see §12.2).
   * If S5 starts treating checks on new artefacts as REQUIRED, that MUST be coupled with a spec/policy version bump.

---

### 12.6 Co-existence & migration

Because S5 works at the world/contract level, deployments may need to handle multiple S5 contracts over time.

Binding expectations:

1. **Single contract per world at sealing time**

   * For any given `manifest_fingerprint`, `_passed.flag_6B` MUST correspond to a single, clearly defined `spec_version_6B` and S5 contract.
   * If worlds are sealed under different contracts over time, they MUST:

     * either be re-validated under the new contract, producing new S5 artefacts and flags, or
     * be clearly marked as “legacy sealed under spec_version_6B = X” and handled accordingly by consumers.

2. **Multi-version support**

   * If an environment supports multiple 6B contracts simultaneously, this MUST be expressed via:

     * different `spec_version_6B` values, and/or
     * versioned artefact ids/paths (`s5_validation_report_6B_v2`, etc.),
       not by mixing incompatible bundles/flags under the same identifiers.

3. **Migration guidance**

   * When introducing a breaking S5 contract, migration policy SHOULD specify:

     * whether old worlds need to be re-sealed under the new contract, and
     * how consumer systems should interpret worlds sealed under older S5 contracts (e.g. accept them, reject them, or re-gate them).

---

### 12.7 Non-negotiable stability points for S5

For the lifetime of a given `spec_version_6B`, the following aspects of S5 are **stable** and MUST NOT change without a new major contract:

* S5 produces exactly:

  * `s5_validation_report_6B`,
  * optionally `s5_issue_table_6B`,
  * `validation_bundle_6B` with an index,
  * `validation_passed_flag_6B`.

* All S5 artefacts are partitioned by `[fingerprint]` only.

* The hashing law for `validation_bundle_6B`:

  * SHA-256 applied to the **concatenation** of raw bytes of the files listed in the index,
  * files taken in ASCII-lex order by `path`,
  * `_passed.flag_6B` is excluded from the index and digest.

* `_passed.flag_6B` format:

  * single line: `sha256_hex = <64-lowercase-hex>`.

* The gate rule:

  > A world is “sealed & valid for 6B” **if and only if** `_passed.flag_6B` exists and its digest matches a recomputation from `validation_bundle_index_6B` and the bundle files.

Any future design that changes these stability points MUST:

* define a new major `spec_version_6B`,
* update S5 schemas/catalogues and specs, and
* update consumer gate-checking logic and migration guidance accordingly.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects shorthand and symbols used in the 6B.S5 spec. It is **informative only**; if anything here conflicts with §§1–12, the binding sections win.

---

### 13.1 Identity & axes

* **`manifest_fingerprint` / `fingerprint`**
  Sealed world snapshot identifier. All S5 artefacts are scoped to a single `manifest_fingerprint` and partitioned by `fingerprint={manifest_fingerprint}`.

* **`parameter_hash`**
  Hash of the 6B configuration pack used to produce S0–S4 outputs for this world. S5 records it in its report and index to document the configuration context under which validation was performed.

* **`spec_version_6B`**
  Version identifier for the Segment 6B contract (S0–S5). Used to interpret S5’s checks and artefact shapes.

---

### 13.2 Artefact shorthands

* **`VR6B`**
  `s5_validation_report_6B` — the world-level validation report.

* **`IT6B`**
  `s5_issue_table_6B` — the optional detailed issue table.

* **`VB6B`**
  `validation_bundle_6B` — the directory of validation artefacts for Segment 6B, under
  `data/layer3/6B/validation/fingerprint={manifest_fingerprint}/`.

* **`IDX6B`**
  `validation_bundle_index_6B` — the bundle index (`index.json` or equivalent), listing all bundle members and their digests.

* **`_flag_6B` / `flag_6B`**
  `validation_passed_flag_6B` / `_passed.flag_6B` — the HashGate flag file containing the bundle digest.

These are just shorthand labels for readability; the canonical names are those in the dataset dictionary and registry.

---

### 13.3 Checks & policies

* **`segment_validation_policy_6B`**
  Configuration artefact that defines:

  * which checks S5 must run (`check_id`s),
  * their severity (`"REQUIRED"`, `"WARN_ONLY"`, `"INFO"`),
  * PASS/WARN/FAIL thresholds for metrics.

* **`check_id`**
  A stable identifier for a specific validation check, e.g.:

  * `CHK_S0_SEALED_INPUTS`,
  * `CHK_UPSTREAM_HASHGATES`,
  * `CHK_S3_CAMPAIGN_INTEGRITY`,
  * `CHK_S4_LABEL_COVERAGE`,
  * `CHK_RNG_S2_FLOW_SHAPE_ENVELOPE`.

* **`overall_status`**
  World-level verdict in `s5_validation_report_6B` and run-report:

  * `"PASS"` — all REQUIRED checks passed; no gating failure.
  * `"WARN"` — REQUIRED checks passed, but some WARN_ONLY checks raised warnings.
  * `"FAIL"` — at least one REQUIRED check failed.

* **`severity`** (per check)

  * `"REQUIRED"` — failure on this check implies overall FAIL.
  * `"WARN_ONLY"` — failure on this check yields WARN (subject to policy) but not overall FAIL.
  * `"INFO"` — purely informational; cannot drive FAIL.

* **`result`** (per check)

  * `"PASS"`, `"WARN"`, `"FAIL"` — outcome of the check before aggregation into `overall_status`.

---

### 13.4 Error codes (S5 prefix)

All S5 error codes are prefixed with **`S5_`**. The main families (see §9 for full semantics):

* **Preconditions/config:**

  * `S5_PRECONDITION_S0_OR_UPSTREAM_FAILED`
  * `S5_PRECONDITION_SEALED_INPUTS_INCOMPLETE`
  * `S5_PRECONDITION_VALIDATION_POLICY_INVALID`

* **Structural & chain integrity:**

  * `S5_SCHEMA_OR_PK_VIOLATION`
  * `S5_CHAIN_COVERAGE_VIOLATION`

* **Behavioural & label integrity:**

  * `S5_BEHAVIOURAL_CONSISTENCY_FAILED`
  * `S5_CAMPAIGN_INTEGRITY_FAILED`
  * `S5_LABEL_INTEGRITY_FAILED`

* **RNG envelope:**

  * `S5_RNG_ENVELOPE_FAILED`
  * `S5_RNG_LOG_INCONSISTENT`

* **Bundle & HashGate:**

  * `S5_BUNDLE_INDEX_INVALID`
  * `S5_BUNDLE_DIGEST_MISMATCH`
  * `S5_FLAG_DIGEST_MISMATCH`
  * `S5_IDEMPOTENCE_VIOLATION`

* **Output & internal:**

  * `S5_OUTPUT_WRITE_FAILED`
  * `S5_INTERNAL_ERROR`

The **primary_error_code** captures the root cause for a world-level FAIL; **secondary_error_codes** carry additional context.

---

### 13.5 Hashing & bundle terminology

* **`sha256_hex`**
  A 64-character lowercase hexadecimal string representing the SHA-256 digest of a file’s raw bytes or of the concatenated bytes of all bundle files (for the world digest).

* **Bundle hashing law**

  For a given world:

  1. `validation_bundle_index_6B.items` is an array of entries with `path` and `sha256_hex`.

  2. Items are sorted by `path` in ASCII-lexicographic order.

  3. The bundle digest is:

     ```text
     SHA256( bytes(file_1) || bytes(file_2) || ... || bytes(file_N) )
     ```

     where `file_i` are the files referenced by `items[i].path` in that order.

  4. `_passed.flag_6B` stores this digest as:

     ```text
     sha256_hex = <digest>
     ```

* **“HashGate”**
  The combination of:

  * a bundle (`validation_bundle_6B` + index), and
  * its `_passed.flag_6B`.

  A world is considered sealed & valid for 6B only if the flag’s `sha256_hex` equals the recomputed bundle digest.

---

### 13.6 Upstream HashGates (shorthand)

* **`HB_1A` … `HB_3B`**
  HashGates for Layer-1 segments (1A–3B).

* **`HB_5A`, `HB_5B`**
  HashGates for Layer-2 segments (5A intensity, 5B arrivals).

* **`HB_6A`**
  HashGate for Layer-3 Segment 6A (static entities & posture).

S5 re-verifies these HashGates as part of its preconditions but does not alter them; it only consumes them.

---

### 13.7 Miscellaneous shorthand

* **“World”**
  A single `manifest_fingerprint` representing a coherent, sealed snapshot across all layers.

* **“Partition”** (in S5 context)
  Typically refers to a `(seed, scenario_id)` slice at S1–S4; S5 itself is world-scoped but inspects metrics per partition.

* **“Chain”**
  Short for the S1→S2→S3→S4 flow/data lineage (arrivals → entities/sessions → baseline flows → overlays → labels → cases).

* **`CHK_*`**
  Shorthand for a specific validation check (e.g. `CHK_S3_CAMPAIGN_INTENSITY`, `CHK_S4_LABEL_COVERAGE`), as referenced in `segment_validation_policy_6B`.

These symbols and abbreviations are here purely to keep the S5 spec readable and structured; they do not introduce any new behaviour or obligations beyond what is already specified in the binding sections.

---
