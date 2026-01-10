# 6B.S4 — Truth & bank-view labelling (Layer-3 / Segment 6B)

## 1. Purpose & scope *(Binding)*

6B.S4 is the **truth & bank-view labelling** state for Segment 6B.

For a sealed world `manifest_fingerprint` and a specific `(parameter_hash, seed, scenario_id)`:

* **S1** has already attached arrivals to entities and grouped them into sessions.
* **S2** has constructed **baseline (all-legit) flows and events**.
* **S3** has overlaid **fraud and abuse campaigns** on those flows/events and emitted the **with-fraud behavioural canvas** plus a campaign catalogue.

S4’s job is to take that canvas and assign:

1. **Truth labels** — what *actually* happened in the synthetic world, independent of any bank decisions; and
2. **Bank-view labels and lifecycle** — how the *bank* perceives and reacts to that behaviour over time.

S4 is the **only state** in the engine that is allowed to say, in a binding way:

* whether a flow is **LEGIT**, **FRAUD**, or **ABUSE** (and with which subtype), and
* whether and when the bank:

  * detected the problem (if at all),
  * opened cases,
  * saw disputes and chargebacks,
  * reached specific case outcomes.

### In-scope responsibilities

Within this contract, S4 is responsible for:

* **Truth labelling**

  * For every flow in `s3_flow_anchor_with_fraud_6B`, S4 MUST derive a **truth label** that classifies the flow as:

    * purely legitimate (`LEGIT`),
    * fraudulent (`FRAUD_*`), or
    * abusive but not classical fraud (`ABUSE_*` — e.g. refund abuse, friendly fraud, policy abuse),

    with subtypes aligned to S3’s `fraud_pattern_type` and campaign catalogue.
  * These labels MUST be driven primarily by:

    * S3’s campaign metadata (`campaign_id`, `fraud_pattern_type`, overlay flags),
    * and, where necessary, additional deterministic rules and priors (e.g. collateral flows that become part of a fraud story, supporting flows around primary fraudulent activity).

* **Bank-view labelling & lifecycle**

  * For each flow, S4 MUST simulate the **bank’s view** of that flow across time, including:

    * auth-time decisions (approve/decline, possibly with step-up / manual review),
    * post-auth detection or non-detection (e.g. detection by model/rules, detection triggered by a later dispute),
    * dispute and chargeback behaviour (if a customer raises an issue),
      as governed by S4’s bank-view policies and delay distributions.

  * This simulation MUST produce:

    * a **flow-level bank-view label** (e.g. `BANK_VIEW_LABEL` such as `CONFIRMED_FRAUD`, `CUSTOMER_DISPUTE_REJECTED`, `NO_CASE_OPENED`), and
    * a timeline of **case events** (case opened, actions, final decision) where applicable.

* **Label and case surfaces**

  * Emitting one or more **label surfaces**:

    * `s4_flow_truth_labels_6B` — one row per flow with truth labels and provenance (which policy/campaign drove the label).
    * `s4_flow_bank_view_6B` — one row per flow with bank-view outcomes and key lifecycle timestamps (detection time, dispute time, chargeback time, case closure).
    * `s4_event_labels_6B` (or equivalent flags attached to final events) — per-event truth/bank-view flags where event-level labelling is required.

  * Emitting `s4_case_timeline_6B` (and any auxiliary case tables) that describe:

    * case identity (`case_id` per `(seed, manifest_fingerprint)`),
    * the set of flows/events in each case,
    * the ordered sequence of case actions (open, investigation, decisions, closure) with timestamps.

These surfaces together form the **final labelled view** of the synthetic world that downstream evaluation and model-training will use.

### Out-of-scope responsibilities

S4 is explicitly **not** allowed to:

* **Modify upstream behaviour**

  * It MUST NOT create, delete, or alter any rows in:

    * S1 outputs (`s1_arrival_entities_6B`, `s1_session_index_6B`),
    * S2 outputs (`s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`),
    * S3 outputs (`s3_campaign_catalogue_6B`, `s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`).
  * If S4 needs to express derived quantities (e.g. “this event is the detection point”), it MUST do so in its own label/case datasets, or via downstream-owned projections, not by rewriting upstream surfaces.

* **Redefine fraud/abuse behaviour**

  * It MUST NOT introduce new campaign behaviour or modify which flows/events belong to which campaigns; that is S3’s responsibility.
  * Any classification of flows/events as fraud/abuse MUST be traceable to S3’s behavioural patterns, static posture from 6A, and S4’s own labelling policy — not to ad-hoc changes in behaviour.

* **Override static posture**

  * It MUST NOT change static fraud roles in 6A (`s5_*_fraud_roles_6A`); it may *interpret* those roles when deciding truth/bank-view labels (e.g. treat flows on mule accounts differently), but cannot alter 6A itself.

* **Perform segment-level validation or HashGate**

  * It MUST NOT construct the 6B validation bundle or `_passed.flag`; that is S5’s role.
  * It MUST NOT re-validate upstream HashGates (S0, S1, S2, S3); it trusts their receipts and sealed inputs.

### Relationship to the rest of Segment 6B and the enterprise

Within Segment 6B:

* **Upstream:**

  * S0 has sealed the world and inputs.
  * S1–S3 have produced, in order, “who + sessions”, baseline flows, and with-fraud overlays plus campaign catalogue.

* **S4:**

  * Uses those surfaces plus labelling/Outcome policies to derive ground-truth and bank-view labels and case timelines.
  * Is the last data-plane state in 6B before validation.

* **Downstream:**

  * The 6B validation/HashGate state (S5) will verify that S4’s labels are internally consistent, consistent with S3’s behaviour and configuration, and respect S4’s own labelling policies and RNG envelopes.
  * The wider fraud platform (4A/4B, model-training pipelines, evaluation harnesses) will treat S4’s label & case surfaces as the **canonical labelled ground truth** for this synthetic world.

If S4 is implemented as specified here, then for each world/run/scenario:

* Every flow and, where required, event has a clear, reproducible **truth label** and **bank-view trajectory**, and
* Downstream consumers never need to guess or infer labels from behaviour — they can rely on S4’s labelled surfaces as the authoritative source.

---

### Contract Card (S4) - inputs/outputs/authorities

**Inputs (authoritative; see Section 2 for full list):**
* `s0_gate_receipt_6B` - scope: FINGERPRINT_SCOPED; source: 6B.S0
* `sealed_inputs_6B` - scope: FINGERPRINT_SCOPED; source: 6B.S0
* `s3_flow_anchor_with_fraud_6B` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, scenario_id]; source: 6B.S3
* `s3_event_stream_with_fraud_6B` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, scenario_id]; source: 6B.S3
* `truth_labelling_policy_6B` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `bank_view_policy_6B` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `delay_models_6B` - scope: UNPARTITIONED (sealed model); sealed_inputs: required
* `case_policy_6B` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `label_rng_policy_6B` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required

**Authority / ordering:**
* S4 is the sole authority for truth labels and bank-view outcomes.

**Outputs:**
* `s4_flow_truth_labels_6B` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, scenario_id]
* `s4_flow_bank_view_6B` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, scenario_id]
* `s4_event_labels_6B` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, scenario_id]
* `s4_case_timeline_6B` - scope: FINGERPRINT_SCOPED; scope_keys: [seed, manifest_fingerprint, scenario_id]
* `rng_event_truth_label` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]
* `rng_event_bank_view_label` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]
* `rng_audit_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]
* `rng_trace_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]

**Sealing / identity:**
* External inputs MUST appear in `sealed_inputs_6B` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or RNG/policy violations -> abort; no outputs published.

## 2. Preconditions & upstream gates *(Binding)*

This section defines **what must already be true** before 6B.S4 is allowed to run, and which upstream gates it **MUST** honour.

S4 is evaluated per triple:

```text
(manifest_fingerprint, seed, scenario_id)
```

and depends on:

* world-level gates (S0 + upstream segments),
* partition-level gates (S1, S2, S3), and
* presence of S4’s own label/Outcome configs and RNG policy.

If any precondition here is not satisfied, S4 **MUST NOT** attempt to assign labels for that domain and **MUST** fail fast with a precondition error (defined in S4’s failure section).

---

### 2.1 6B.S0 gate MUST be PASS (world-level)

For a given `manifest_fingerprint`, S4 **MUST NOT** run unless 6B.S0 has successfully completed for that fingerprint.

Before doing any work, S4 MUST:

1. Locate `s0_gate_receipt_6B` for the target `manifest_fingerprint` via `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml`.
2. Validate it against `schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B`.
3. Confirm, via the Layer-3 run-report (or equivalent control-plane API), that 6B.S0 is recorded as `status="PASS"` for this `manifest_fingerprint`.

If:

* the receipt is missing,
* fails schema validation, or
* the run-report does not show 6B.S0 as PASS,

then S4 **MUST** treat this as a hard precondition failure and MUST NOT read any S1–S3 or upstream data-plane tables for that world.

S4 is **not** allowed to reconstruct or bypass S0’s sealed-inputs universe.

---

### 2.2 Upstream HashGates (1A–3B, 5A, 5B, 6A) MUST be PASS

S0 has already verified the HashGates for the required upstream segments:

* Layer-1: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
* Layer-2: `5A`, `5B`
* Layer-3: `6A`

S4 does **not** re-validate those bundles, but it **MUST** respect their recorded status in `s0_gate_receipt_6B.upstream_segments`:

* For each `SEG ∈ { "1A","1B","2A","2B","3A","3B","5A","5B","6A" }`, S4 MUST check:

  ```text
  s0_gate_receipt_6B.upstream_segments[SEG].status == "PASS"
  ```

* If any required upstream segment has `status != "PASS"`, S4 MUST fail with a precondition error and MUST NOT attempt to label flows/events for that world.

S4 MUST NOT attempt to “work around” a non-PASS upstream segment: if S0 says the world isn’t sealed, S4 cannot run.

---

### 2.3 S1, S2 and S3 MUST be PASS for `(seed, scenario_id)`

S4’s labelling sits on top of S1, S2 and S3. For each `(manifest_fingerprint, seed, scenario_id)`:

* S4 **MUST NOT** run unless:

  * 6B.S1 is PASS for that triple,
  * 6B.S2 is PASS for that triple, and
  * 6B.S3 is PASS for that triple.

Binding checks:

1. Inspect the Layer-3 run-report for entries:

   ```text
   (segment="6B", state="S1", manifest_fingerprint, seed, scenario_id, status="PASS")
   (segment="6B", state="S2", manifest_fingerprint, seed, scenario_id, status="PASS")
   (segment="6B", state="S3_overlay", manifest_fingerprint, seed, scenario_id, status="PASS")
   ```

2. Confirm that the required data-plane outputs exist and are schema-valid for this partition:

   * S1:

     * `s1_arrival_entities_6B@{seed,fingerprint,scenario_id}`,
     * `s1_session_index_6B@{seed,fingerprint,scenario_id}`.

   * S2:

     * `s2_flow_anchor_baseline_6B@{seed,fingerprint,scenario_id}`,
     * `s2_event_stream_baseline_6B@{seed,fingerprint,scenario_id}`.

   * S3:

     * `s3_flow_anchor_with_fraud_6B@{seed,fingerprint,scenario_id}`,
     * `s3_event_stream_with_fraud_6B@{seed,fingerprint,scenario_id}`.

If any of these states are not PASS, or any of these datasets are missing or fail schema validation, S4 MUST treat this as a precondition failure and MUST NOT attempt labelling for that `(seed, scenario_id)` domain.

S4 MUST NOT:

* bypass S3 to label directly on S2 baseline, nor
* bypass S2/S1 to label directly on arrivals or entities.

---

### 2.4 Required `sealed_inputs_6B` entries for S4

All artefacts S4 reads MUST be discoverable via `sealed_inputs_6B` for the target `manifest_fingerprint`.

Before processing any `(seed, scenario_id)` partition, S4 MUST:

1. Load `sealed_inputs_6B@{fingerprint}` and validate it against `schemas.layer3.yaml#/gate/6B/sealed_inputs_6B`.

2. Confirm that the following rows exist with:

   * `status = "REQUIRED"`
   * appropriate `read_scope` (often `ROW_LEVEL`, `METADATA_ONLY` where indicated)

   **S3 behavioural canvases (6B / S3)**

   * `owner_layer = 3`, `owner_segment = "6B"`, `manifest_key = "s3_flow_anchor_with_fraud_6B"`
   * `owner_layer = 3`, `owner_segment = "6B"`, `manifest_key = "s3_event_stream_with_fraud_6B"`

   **S3 campaign catalogue (for provenance)**

   * `owner_layer = 3`, `owner_segment = "6B"`, `manifest_key = "s3_campaign_catalogue_6B"`

   **Upstream context surfaces**

   S4 MAY require some or all of the following, depending on the label policy. When required, they MUST appear with `status="REQUIRED"` and appropriate `read_scope`:

   * S2 baseline surfaces (usually `METADATA_ONLY` for S4, or `ROW_LEVEL` if policy uses them directly):

     * `s2_flow_anchor_baseline_6B`,
     * `s2_event_stream_baseline_6B`.

   * S1/S6A for extra context (e.g. entity posture):

     * `s1_arrival_entities_6B`, `s1_session_index_6B`,
     * `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_merchant_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A`.

   **S4 configuration & policy packs (6B)**

   Names are indicative and must match your contract files; each MUST be present with `status="REQUIRED"` and a valid `schema_ref`:

   * `truth_labelling_policy_6B`

     * mapping from S3 campaigns/patterns + context → truth labels.
   * `bank_view_policy_6B`

     * mapping from flows + truth labels + bank controls → bank decisions (auth, review, decline, allow).
   * `delay_models_6B`

     * detection, dispute, chargeback and investigation delay distributions.
   * `case_policy_6B`

     * rules for case grouping, escalation, and closure.
   * `label_rng_policy_6B` (or similar)

     * RNG family and budget configuration for S4 (e.g. for ambiguous truth cases and stochastic delays).

3. For each required row, S4 MUST verify:

   * `schema_ref` resolves into `schemas.6B.yaml` or `schemas.layer3.yaml` as appropriate.
   * `partition_keys` and `path_template` are consistent with the owning dictionary/registry.

If any required row is missing or malformed, S4 MUST fail with a precondition error and MUST NOT proceed to read data-plane rows or generate labels.

Optional context artefacts (e.g. additional 6A attributes, extra monitoring surfaces) MAY appear with `status="OPTIONAL"` and any appropriate `read_scope`; their absence MUST NOT, by itself, block S4 from running.

---

### 2.5 Partition coverage and “empty” partitions

S4 operates on the same `(seed, scenario_id)` partitions as S3 overlays for a given world.

For each `(manifest_fingerprint, seed, scenario_id)` that S4 intends to process, it MUST ensure:

1. `s3_flow_anchor_with_fraud_6B` has a partition at:

   ```text
   seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}
   ```

2. `s3_event_stream_with_fraud_6B` has a partition at the same axes.

If S3 is PASS but a given partition has **zero flows** (e.g. scenario with no traffic or all flows filtered upstream), S4 MAY:

* treat that partition as a trivial PASS:

  * emit empty label surfaces for that partition, or
  * emit no label datasets for that partition but still record S4 `status="PASS"` with zero counts in the run-report.

The choice (empty outputs vs “absent because empty”) MUST be fixed by the S4 spec and applied consistently. Under this contract, S4 MUST NOT synthesize labels for flows that do not exist in S3.

If S3 overlays are missing for a partition where S3 is expected to have run, S4 MUST treat that as a precondition failure for that partition.

---

### 2.6 Layer-3 RNG & numeric environment for S4

S4 is an RNG-consuming state (for probabilistic truth cases and delay modelling). Before any labelling, S4 MUST ensure that:

* The Layer-3 Philox RNG configuration (event envelope, counters, numeric policy) exists and is valid, as defined in `schemas.layer3.yaml` and Layer-3 RNG policy artefacts.
* The S4-specific RNG policy (`label_rng_policy_6B` or equivalent) is present in `sealed_inputs_6B` and schema-valid, including:

  * RNG family names reserved for S4 (e.g. `rng_event_truth_label_ambiguity`, `rng_event_detection_delay`, `rng_event_chargeback_delay`),
  * per-family budgets (draws per decision),
  * substream keying rules (e.g. keys based on `(manifest_fingerprint, seed, scenario_id, flow_id, label_stage)`).

If the S4 RNG policy is missing, inconsistent with the Layer-3 RNG spec, or invalid, S4 MUST fail preconditions and MUST NOT attempt stochastic labelling.

---

### 2.7 Prohibited partial / speculative invocations

S4 MUST NOT be invoked in any of the following situations:

* **Before** 6B.S0 has PASSed for the target `manifest_fingerprint`.
* **Before** 6B.S1, 6B.S2, and 6B.S3 have PASSed for the target `(manifest_fingerprint, seed, scenario_id)`.
* With a manually specified set of inputs that bypasses `sealed_inputs_6B`.
* When required S1/S2/S3 surfaces, 6A posture surfaces, or S4 config packs are missing or schema-invalid.
* Against a world where any required upstream HashGate (`1A–3B`, `5A`, `5B`, `6A`) is not PASS according to `s0_gate_receipt_6B`.
* In any “best-effort”, “partial labelling” mode that allows S4 to continue when some of the above requirements are not met.

If any of these conditions hold, the correct behaviour is:

* S4 MUST fail early for the affected `(manifest_fingerprint, seed, scenario_id)` with a precondition error, and
* S4 MUST NOT emit any label or case outputs for that domain.

These preconditions are **binding**: any conformant implementation of 6B.S4 MUST enforce them before performing any truth or bank-view labelling.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **precisely what 6B.S4 may read** and what each input is the **authority for**. Anything outside these boundaries is out of scope for S4 and **MUST NOT** be touched.

S4 is a **data-plane + RNG-consuming** state:

* It reads flows/events/campaigns from S3 plus a small amount of upstream context.
* It reads S4 configuration packs (truth & bank-view policies, delay models, case policy, RNG policy).
* It emits **labels and case timelines only**.
* It MUST NOT mutate any upstream datasets.

---

### 3.1 Engine parameters (implicit inputs)

S4 is evaluated over:

* `manifest_fingerprint` — sealed world snapshot for Layers 1–3.
* `seed` — run axis shared with 5B, 6A, S1, S2, S3.
* `scenario_id` — arrival scenario (from 5A/5B).
* `parameter_hash` — 6B behavioural/config pack identifier (shared with S0–S3).

These values are supplied by orchestration and/or resolved via `s0_gate_receipt_6B` and `sealed_inputs_6B`. S4 **MUST NOT**:

* infer them from wall-clock time or environment state, or
* mutate them.

---

### 3.2 6B control-plane inputs (S0 outputs)

S4 uses S0’s outputs as **control-plane authority**:

1. **`s0_gate_receipt_6B`**

   Authority for:

   * which upstream segments are PASS/MISSING/FAIL for this `manifest_fingerprint`,
   * which `parameter_hash` and `spec_version_6B` are in force,
   * the `sealed_inputs_digest_6B` summarising the input universe.

   S4 MUST:

   * check it is running against the intended world and config,
   * respect upstream statuses (no labelling if any required segment is not PASS),
   * not attempt to recompute or override S0’s decisions.

2. **`sealed_inputs_6B`**

   Authority for:

   * which artefacts S4 is allowed to read,
   * where they live (`path_template`, `partition_keys`),
   * how they should be interpreted (`schema_ref`, `role`, `status`, `read_scope`),
   * integrity (`sha256_hex`).

   S4 MUST:

   * resolve all dataset paths via `sealed_inputs_6B` + the owning segment’s dictionary/registry,
   * NEVER construct dataset paths “by hand”,
   * NEVER read artefacts not listed in `sealed_inputs_6B`,
   * honour `status` and `read_scope` for each artefact.

---

### 3.3 Behavioural surfaces to be labelled (S3 outputs)

S4’s **primary data-plane inputs** are S3 overlays. They are authoritative for **what behaviour exists to be labelled**.

These MUST be listed in `sealed_inputs_6B` with `owner_layer=3`, `owner_segment="6B"`, `status="REQUIRED"`:

1. **`s3_flow_anchor_with_fraud_6B`** (`ROW_LEVEL`)

   * One row per **post-overlay flow** for `(seed, manifest_fingerprint, scenario_id)`.
   * Contains:

     * flow identity (`flow_id`),
     * linkage to baseline (`origin_flow_id`, `origin_type`),
     * entity/session context,
     * amounts/timestamps/outcomes after overlay,
     * overlay metadata (`campaign_id`, `fraud_pattern_type`, overlay flags).

   **Authority:** This is the **sole flow-level behavioural surface** S4 labels. It tells S4:

   * which flows exist after fraud/abuse overlay,
   * which flows are touched by campaigns and how.

   S4 MUST NOT:

   * change any fields in this dataset,
   * create or delete flows here,
   * treat S2 flows as the behavioural canvas instead of S3.

2. **`s3_event_stream_with_fraud_6B`** (`ROW_LEVEL`)

   * One row per **post-overlay event** for `(seed, manifest_fingerprint, scenario_id)`.
   * Contains:

     * event identity (`flow_id`, `event_seq`),
     * `event_type`, `event_ts_utc`,
     * entity & routing context,
     * overlay metadata (`campaign_id`, `fraud_pattern_type`, per-event overlay flags),
     * provenance (`origin_flow_id`, `origin_event_seq`).

   **Authority:** This is the **sole event-level behavioural surface** for S4. It tells S4:

   * what actually happened in each flow at event level, after overlay,
   * which events are structurally part of fraud/abuse patterns (per S3’s overlay flags).

   S4 MUST NOT:

   * mutate event sequences or types,
   * insert/remove events here,
   * change overlay flags produced by S3.

3. **`s3_campaign_catalogue_6B`** (`ROW_LEVEL` or `METADATA_ONLY`)

   * Campaign catalogue for `(manifest_fingerprint, seed)`.
   * Contains one row per realised `campaign_id` with type, parameters, scope, and intensity metrics.

   **Authority:** This defines:

   * what campaign instances exist,
   * their type (`campaign_type`),
   * time/scope and intensity.

   S4 MUST:

   * treat campaigns as given; it may use them to inform truth/bank-view labels,
   * NOT invent or delete campaigns,
   * NOT change `campaign_type` or instance parameters.

---

### 3.4 Upstream context surfaces (S1, S2, 6A)

S4 may use some upstream surfaces purely as **context** when deriving labels. These MUST appear in `sealed_inputs_6B` with appropriate `status` and `read_scope` (often `METADATA_ONLY`, sometimes `ROW_LEVEL`):

1. **S2 baseline surfaces**

   * `s2_flow_anchor_baseline_6B` (often `METADATA_ONLY` for S4).
   * `s2_event_stream_baseline_6B` (often `METADATA_ONLY`).

   **Authority:** baseline (all-legit) behaviour. S4 may use it:

   * to distinguish legit vs fraudulent distortions,
   * to compute relative anomalies (e.g. amount or timing deviations).

   S4 MUST NOT:

   * treat baseline flows as the labelled surface,
   * change S2 outputs.

2. **S1 entity/session surfaces**

   * `s1_arrival_entities_6B`
   * `s1_session_index_6B`

   **Authority:** “who + session” context:

   * entity graph (which party/account/instrument/device/IP is involved),
   * which arrivals belong to which sessions.

   S4 MAY re-join these for high-level context (e.g. “this flow is from a mule account, high-risk device”), but MUST NOT:

   * change any attachments or `session_id`,
   * treat S1 surfaces as label carriers.

3. **6A static posture surfaces**

   * `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`,
   * `s5_merchant_fraud_roles_6A`, `s5_device_fraud_roles_6A`,
   * `s5_ip_fraud_roles_6A`.

   **Authority:** static fraud posture:

   * e.g. which accounts are mules, which merchants are structurally risky.

   S4 MAY use these to adjust truth/bank-view priors (e.g. treat flows on mule accounts as more likely fraud, or treat certain merchants as abuse-prone), but MUST NOT:

   * change any static fraud roles,
   * reinterpret posture fields beyond what labelling policy allows.

---

### 3.5 S4 configuration & policy inputs (6B)

S4’s behaviour is governed by S4-specific config packs. These MUST be:

* registered for `owner_layer=3`, `owner_segment="6B"`,
* listed in `sealed_inputs_6B` with `role` appropriate to their function,
* `status="REQUIRED"` for the active `spec_version_6B`,
* validated against their schemas before use.

Indicative set (names to match your contract files):

1. **Truth labelling policy** (e.g. `truth_labelling_policy_6B`)

   Role: `label_policy_truth`.
   Authority for:

   * mapping from S3 behaviour (`fraud_pattern_type`, overlay flags, campaigns) + context (6A posture, S2 baseline) → **truth labels**:

     * classification into `LEGIT`, `FRAUD_*`, `ABUSE_*`,
     * handling of ambiguous / collateral flows (e.g. supporting flows around a primary fraud campaign).

   S4 MUST NOT hard-code truth mapping logic outside this pack.

2. **Bank-view policy** (e.g. `bank_view_policy_6B`)

   Role: `label_policy_bank_view`.
   Authority for:

   * how the simulated bank decides at auth time (approve/decline/review),
   * how it decides detection vs non-detection given scores/thresholds,
   * how it routes to manual review and cases,
   * what bank-view classifications exist (e.g. `CONFIRMED_FRAUD`, `DISPUTE_REJECTED`).

3. **Delay models** (e.g. `delay_models_6B`)

   Role: `delay_models`.
   Authority for:

   * distributions over detection delay, dispute delay, chargeback delay, case resolution delay, etc.
   * whether those distributions are deterministic or stochastic; S4 MUST use them for any timing attached to bank-view lifecycle events.

4. **Case policy** (e.g. `case_policy_6B`)

   Role: `case_policy`.
   Authority for:

   * rules for grouping flows into cases (e.g. same card, same merchant, time window),
   * case escalation, linking and closure policies,
   * maximum case duration, allowed state transitions.

5. **S4 RNG policy** (e.g. `label_rng_policy_6B`)

   Role: `rng_policy`.
   Authority for:

   * RNG families S4 is allowed to use (e.g. `rng_event_truth_label_ambiguity`, `rng_event_detection_delay`, `rng_event_chargeback_delay`),
   * per-family budgets (draws per decision),
   * substream key structures for label/delay decisions.

Binding rules:

* S4 MUST use these packs as the **sole source** of label mapping and stochastic behaviour; no hidden policy in code.
* If any required pack is missing or invalid, S4 MUST fail preconditions.

---

### 3.6 Authority boundaries & prohibitions

To make the boundaries explicit:

* **Authority for “what behaviour happened”**

  * S3 overlays (`s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`) are the only authority.
  * S4 MUST NOT:

    * change flow/event identity,
    * add/drop flows/events in those datasets,
    * change `campaign_id`, `fraud_pattern_type`, or overlay flags produced by S3.

* **Authority for “what entities exist and their posture”**

  * 6A bases and posture surfaces are the only authority.
  * S4 MUST NOT:

    * create new entities,
    * alter static fraud roles,
    * violate 6A link constraints in any derived view.

* **Authority for “what S4 may read”**

  * `sealed_inputs_6B` is the exclusive inventory.
  * S4 MUST NOT:

    * read artefacts not listed there,
    * exceed `read_scope` (e.g. reading rows from `METADATA_ONLY` datasets).

* **Authority for “how S4 behaves”**

  * S4 configuration packs (truth policy, bank-view policy, delay models, case policy, RNG policy) are the only source of labelling rules and stochastic behaviour.
  * S4 MUST NOT:

    * alter S0/S1/S2/S3 preconditions or gating semantics,
    * re-implement fraud campaigns (those belong to S3).

S4’s scope is thus strictly limited to:

> Using S3’s behaviour + 6A/S1/S2 context + S4 policies to emit **labels and case timelines** — nothing more, nothing less.

---

## 4. Outputs (datasets) & identity *(Binding)*

6B.S4 produces the **final labelled surfaces** for Layer-3 / Segment 6B:

1. `s4_flow_truth_labels_6B` — **flow-level truth labels**.
2. `s4_flow_bank_view_6B` — **flow-level bank-view outcomes & lifecycle**.
3. `s4_event_labels_6B` — **event-level truth/bank-view flags** keyed to S3 events.
4. `s4_case_timeline_6B` — **case-level timeline** of disputes/chargebacks/investigations.

These datasets:

* Are **Layer-3 / 6B-owned**,

* Are treated as **final-in-layer** label surfaces for the fraud engine,

* Share axes with S3:

  * flow/event labels: `[seed, fingerprint, scenario_id]`,
  * case timeline: `[seed, manifest_fingerprint]`,

* And are consumed by:

  * 6B.S5 (validation/HashGate),
  * enterprise-level consumption layers (4A/4B),
  * model-training/evaluation pipelines.

No other datasets may be written by S4.

---

### 4.1 `s4_flow_truth_labels_6B` — flow-level truth

**Dataset id**

* `id: s4_flow_truth_labels_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

One row per **post-overlay flow** (from `s3_flow_anchor_with_fraud_6B`), providing its **ground truth** classification:

* whether the flow is **LEGIT**, **FRAUD**, or **ABUSE**,
* more specific subtype (e.g. `CARD_TESTING`, `ATO`, `REFUND_ABUSE`, `MULE_ACTIVITY`, `FRIENDLY_FRAUD`),
* provenance (which campaign/pattern and policy rule(s) drove the truth label),
* optional flags for collateral/secondary flows in a fraud story.

This table is the **sole authority** for truth labels at flow level. Downstream consumers MUST NOT infer truth from behaviour; they MUST read it from here.

**Format, path & partitioning**

Registered in dictionary/registry as:

* `version: '{seed}.{manifest_fingerprint}.{scenario_id}'`

* `format: parquet`

* `path` (template):

  ```text
  data/layer3/6B/s4_flow_truth_labels_6B/
      seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `partitioning: [seed, fingerprint, scenario_id]`

Embedded `seed`, `manifest_fingerprint`, `scenario_id` columns MUST match path tokens.

**Primary key & identity**

For each `(seed, manifest_fingerprint, scenario_id)`:

* Primary key (binding):

  ```text
  [seed, manifest_fingerprint, scenario_id, flow_id]
  ```

where `flow_id` is exactly the same as in `s3_flow_anchor_with_fraud_6B` for that partition.

Every flow in S3 MUST have exactly one truth-label row here; no extra flow_ids are allowed.

**Schema anchor & lineage**

* Schema anchor (for §5):

  ```text
  schemas.6B.yaml#/s4/flow_truth_labels_6B
  ```

* Dictionary:

  * `status: required`
  * `produced_by: [ '6B.S4' ]`
  * `consumed_by: [ '6B.S5', '4A', '4B', 'model_training' ]`

* Registry:

  * `manifest_key: s4_flow_truth_labels_6B`
  * `type: dataset`
  * `category: labels`
  * `final_in_layer: true`

---

### 4.2 `s4_flow_bank_view_6B` — flow-level bank-view outcome

**Dataset id**

* `id: s4_flow_bank_view_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

One row per **post-overlay flow** describing **how the bank sees and handles it** over time. For each `(seed, fingerprint, scenario_id, flow_id)`, this dataset records:

* auth-time outcome (approved, declined, stepped-up, sent to manual review),

* detection outcome:

  * whether the bank ever identified the flow as fraud/abuse,
  * whether detection occurred at auth, shortly after, or only via later dispute/case,

* customer dispute & chargeback outcomes:

  * whether the customer disputed the transaction,
  * whether a chargeback was initiated, the chargeback type, and its timing,

* final bank classification:

  * e.g. `BANK_CONFIRMED_FRAUD`, `BANK_CONFIRMED_LEGIT`, `CUSTOMER_DISPUTE_REJECTED`, `NO_CASE_OPENED`, etc.,

* key lifecycle timestamps:

  * `detection_ts_utc`, `dispute_ts_utc`, `chargeback_ts_utc`, `case_opened_ts_utc`, `case_closed_ts_utc` (nullable where not applicable).

This table is the **sole authority** on bank-view labels at flow level.

**Format, path & partitioning**

Registered as:

* `version: '{seed}.{manifest_fingerprint}.{scenario_id}'`

* `format: parquet`

* `path`:

  ```text
  data/layer3/6B/s4_flow_bank_view_6B/
      seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `partitioning: [seed, fingerprint, scenario_id]`

**Primary key & identity**

Same PK as truth labels:

```text
[seed, manifest_fingerprint, scenario_id, flow_id]
```

Constraints:

* Every `flow_id` present in `s3_flow_anchor_with_fraud_6B` for this partition MUST have exactly one row in `s4_flow_bank_view_6B`.
* `flow_id` and axes MUST match the corresponding truth-label row.

**Schema anchor & lineage**

* Schema anchor:

  ```text
  schemas.6B.yaml#/s4/flow_bank_view_6B
  ```

* Dictionary:

  * `status: required`
  * `produced_by: [ '6B.S4' ]`
  * `consumed_by: [ '6B.S5', '4A', '4B', 'model_training' ]`

* Registry:

  * `manifest_key: s4_flow_bank_view_6B`
  * `type: dataset`
  * `category: labels`
  * `final_in_layer: true`

---

### 4.3 `s4_event_labels_6B` — event-level labels

**Dataset id**

* `id: s4_event_labels_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

One row per **post-overlay event** (from `s3_event_stream_with_fraud_6B`), providing event-level truth/bank-view flags. At minimum, for each `(seed, fingerprint, scenario_id, flow_id, event_seq)`, this dataset can encode:

* truth flags:

  * `is_fraud_event_truth` — whether this event is part of the fraudulent/abusive behaviour in the story,
  * `truth_event_role` — optional enum such as `PRIMARY_FRAUD_ACTION`, `SUPPORTING_EVENT`, `LEGIT_CONTEXT`, `DETECTION_ACTION`, `CASE_EVENT`.

* bank-view flags:

  * `is_detection_action` — whether this event is associated with model/rule detection or manual review.
  * `is_case_event` — whether this event is part of the case lifecycle (e.g. `CASE_OPENED`, `CHARGEBACK_POSTED`).
  * optional bank-view event labels (e.g. “flagged as suspicious”, “investigation note added”).

This table is optional for pure flow-level modelling, but required for fine-grained label use cases (per-event training, case-timeline validation).

**Format, path & partitioning**

Registered as:

* `version: '{seed}.{manifest_fingerprint}.{scenario_id}'`

* `format: parquet`

* `path`:

  ```text
  data/layer3/6B/s4_event_labels_6B/
      seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `partitioning: [seed, fingerprint, scenario_id]`

**Primary key & identity**

For each `(seed, manifest_fingerprint, scenario_id)`:

* Primary key (binding):

  ```text
  [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
  ```

Constraints:

* For every `(seed, fingerprint, scenario_id, flow_id, event_seq)` present in `s3_event_stream_with_fraud_6B`, there MUST be exactly one row in `s4_event_labels_6B`.
* No labels may exist for events not present in S3.

**Schema anchor & lineage**

* Schema anchor:

  ```text
  schemas.6B.yaml#/s4/event_labels_6B
  ```

* Dictionary:

  * `status: required` (for this S4 spec; a future variant could treat it as `OPTIONAL`)
  * `produced_by: [ '6B.S4' ]`
  * `consumed_by: [ '6B.S5', '4A', '4B', 'model_training' ]`

* Registry:

  * `manifest_key: s4_event_labels_6B`
  * `type: dataset`
  * `category: labels`
  * `final_in_layer: true`

---

### 4.4 `s4_case_timeline_6B` — case-level timeline

**Dataset id**

* `id: s4_case_timeline_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

This dataset encodes the **lifecycle of cases** (disputes, chargebacks, investigations) across the world. Each row represents a **case event** (a step in the case lifecycle), such as:

* `CASE_OPENED`,
* `DETECTION_EVENT_ATTACHED`,
* `CUSTOMER_DISPUTE_FILED`,
* `CHARGEBACK_INITIATED`,
* `CHARGEBACK_DECISION`,
* `CASE_CLOSED`.

For each case event, S4 records:

* `case_id` — unique within `(seed, manifest_fingerprint)`,
* event identity and ordering,
* links to affected flows/events,
* timestamps and event type.

This table is the authority for **case-level timelines**. Case-level aggregates (e.g. one-row-per-case views) can be derived downstream as needed.

**Format, path & partitioning**

Registered as:

* `version: '{seed}.{manifest_fingerprint}'`

* `format: parquet`

* `path`:

  ```text
  data/layer3/6B/s4_case_timeline_6B/
      seed={seed}/manifest_fingerprint={manifest_fingerprint}/part-*.parquet
  ```

* `partitioning: [seed, manifest_fingerprint]`

**Primary key & identity**

For each `(seed, manifest_fingerprint)`:

* Primary key (binding):

  ```text
  [seed, manifest_fingerprint, case_id, case_event_seq]
  ```

where:

* `case_id` uniquely identifies a case in this world/seed, and
* `case_event_seq` is a strictly monotone, contiguous sequence number per case, defining event order.

Constraints:

* For each `(seed, fingerprint, case_id)`:

  * `case_event_seq` values form a contiguous sequence (e.g. `0..N-1` or `1..N`).
  * There is at least one event row (no empty cases).

* Any flow that is referenced in `s4_flow_bank_view_6B` as being in a case MUST appear in at least one row of `s4_case_timeline_6B` via case-flow linkage fields (defined in the schema).

**Schema anchor & lineage**

* Schema anchor:

  ```text
  schemas.6B.yaml#/s4/case_timeline_6B
  ```

* Dictionary:

  * `status: required`
  * `produced_by: [ '6B.S4' ]`
  * `consumed_by: [ '6B.S5', '4A', '4B', 'model_training' ]`

* Registry:

  * `manifest_key: s4_case_timeline_6B`
  * `type: dataset`
  * `category: labels` (or `case_labels`)
  * `final_in_layer: true`

---

### 4.5 Relationships & identity consistency

To make the cross-surface relationships explicit:

* **Flows:**

  * Every `(seed, fingerprint, scenario_id, flow_id)` in `s3_flow_anchor_with_fraud_6B` MUST appear exactly once in both:

    * `s4_flow_truth_labels_6B`,
    * `s4_flow_bank_view_6B`.

* **Events:**

  * Every `(seed, fingerprint, scenario_id, flow_id, event_seq)` in `s3_event_stream_with_fraud_6B` MUST appear exactly once in `s4_event_labels_6B`.

* **Cases:**

  * Any flow that has a non-null “case involvement” flag in `s4_flow_bank_view_6B` MUST appear in `s4_case_timeline_6B` via one or more case events.
  * `case_id`s in `s4_case_timeline_6B` MUST be unique within `(seed, fingerprint)` and stable given inputs and config.

These identity relationships are enforced by S4’s algorithm and invariants, and will be validated by S5. This section fixes **what** S4 outputs and **how** they are keyed; §5 will pin down their schema anchors and catalogue wiring in detail.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

All binding schema anchors, dataset IDs, partitioning rules, and manifest keys for this state's egress live in the Layer-3 / Segment 6B contracts:
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/schemas.layer3.yaml`

This specification only summarises semantics so there is a single source of truth for catalogue details. Always consult the files above for precise schema refs, physical paths, partition keys, writer ordering, lifecycle flags, and dependency metadata.

### 5.1 Outputs owned by this state
- `s4_flow_truth_labels_6B` — Truth-table style labels for each flow (benign vs fraud variants).
- `s4_flow_bank_view_6B` — Bank-side observational view for each flow (limited to the signals a bank would see).
- `s4_event_labels_6B` — Per-event labels derived from the bank view and truth table.
- `s4_case_timeline_6B` — Case timeline summarising alerts/interventions for flows S4 deems material.

### 5.2 Catalogue & downstream obligations
Implementations and downstream consumers MUST resolve datasets via the dictionary/registry, honour the declared schema anchors, and treat any artefact not listed there as out of scope for this state.

## 6. Deterministic algorithm (with RNG) *(Binding)*

This section specifies **how** 6B.S4 constructs its four outputs for a given
`(manifest_fingerprint, parameter_hash, seed, scenario_id)`:

* `s4_flow_truth_labels_6B`
* `s4_flow_bank_view_6B`
* `s4_event_labels_6B`
* `s4_case_timeline_6B`

S4 is **data-plane + RNG-consuming**:

* Deterministic given:

  * `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`,
  * S1/S2/S3/6A inputs listed in §3,
  * S4 config packs (truth_labelling_policy, bank_view_policy, delay_models, case_policy, label_rng_policy),
  * Layer-3 Philox RNG contracts.

* All stochastic choices (ambiguity resolution, detection/dispute/chargeback delays, case dynamics) MUST use **S4-specific RNG families** configured in `label_rng_policy_6B`. No ad-hoc RNG is allowed.

At a high level, per `(seed, scenario_id)` S4:

1. Discovers the domain (flows/events) and loads configs.
2. Assigns **truth labels** to each flow.
3. Simulates **bank-view outcomes** (auth, detection, disputes, chargebacks).
4. Builds **case timelines** according to case policy.
5. Emits flow-level, event-level and case-level label surfaces, enforcing identity & coverage invariants.
6. Enforces idempotence and RNG envelope sanity.

Any deviation from this algorithm’s constraints MUST result in S4 failing for the partition and MUST NOT produce label outputs.

---

### 6.1 Determinism & RNG envelope

**Binding constraints:**

1. **Pure function + Philox**

   For fixed:

   * `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`,
   * upstream surfaces (S1/S2/S3/6A),
   * S4 config packs,
   * Layer-3 RNG/RNG-policy,

   S4’s outputs MUST be bit-for-bit reproducible across runs.

2. **RNG families reserved for S4**

   All random draws in S4 MUST use Philox through S4-specific families declared in `label_rng_policy_6B`, for example (names indicative):

   * `rng_event_truth_label_ambiguity` — for resolving ambiguous/ collateral truth cases.
   * `rng_event_detection_delay` — for sampling detection delays / whether detection occurs.
   * `rng_event_dispute_delay` — for sampling customer dispute delays.
   * `rng_event_chargeback_delay` — for sampling chargeback delays and outcomes.
   * `rng_event_case_timeline` — for any residual stochasticity in case event timing/structure (if required).

   S4 MUST NOT use RNG families reserved for other states and MUST NOT invent new families outside `label_rng_policy_6B`.

3. **Fixed budgets per decision type**

   For each type of stochastic decision, S4 MUST adhere to a fixed, documented budget in `label_rng_policy_6B`, e.g.:

   * `1` draw per ambiguous truth decision (per flow).
   * `k` draws per flow for detection (e.g. detection vs no detection + delay).
   * `m` draws per flow for dispute/chargeback decisions and delays.
   * `n` draws per case for any additional case-timeline randomness.

   For a given domain size (number of flows/events/cases), the number of draws per RNG family MUST be a deterministic function of that domain and policy, not of draw outcomes.

4. **Deterministic keying**

   RNG keys MUST be derived deterministically from:

   * `manifest_fingerprint`, `parameter_hash`, `seed`,
   * `scenario_id`,
   * `flow_id`, `event_seq`, `case_id` (or pre-case keys in case construction),
   * and a fixed decision “stage” id (e.g. `"truth"`, `"detection"`, `"dispute"`).

   Keying MUST be chosen such that:

   * changing processing order (e.g. parallelism) does not change which draws each decision sees, and
   * no two logically distinct decisions share the same key in the same family.

---

### 6.2 Step 0 — Discover domain & load configs

For a given `manifest_fingerprint` and `(seed, scenario_id)`:

1. **Load control-plane & inputs**

   * Read and validate `s0_gate_receipt_6B` and `sealed_inputs_6B`.
   * Confirm S1/S2/S3 are PASS and required S1/S2/S3/S6A datasets exist and are schema-valid (per §2).

2. **Resolve S3 behavioural domain**

   * Identify flows in `s3_flow_anchor_with_fraud_6B@{seed,fingerprint,scenario_id}`.
   * Identify events in `s3_event_stream_with_fraud_6B@{seed,fingerprint,scenario_id}`.
   * Optionally read S2 baseline and 6A posture surfaces as context, per `sealed_inputs_6B` and S4 config.

3. **Load S4 configuration packs**

   * `truth_labelling_policy_6B` — defines truth mapping rules, categories, and precedence.
   * `bank_view_policy_6B` — defines bank decision rules and detection outcomes.
   * `delay_models_6B` — defines delay distributions for detection, disputes, chargebacks, and case events.
   * `case_policy_6B` — defines case keys, grouping rules, timelines.
   * `label_rng_policy_6B` — defines S4 RNG families, budgets, and keying scheme.

All configs MUST pass schema validation before S4 proceeds.

---

### 6.3 Step 1 — Flow-level truth labelling

For each flow `f` in `s3_flow_anchor_with_fraud_6B@{seed,fingerprint,scenario_id}`:

1. **Construct flow context**

   From S3 flow anchor, event stream, and optional S1/S2/6A context, build a context object including:

   * `fraud_pattern_type`, `campaign_id`, overlay flags (`amount_modified_flag`, `extra_auths_flag`, etc.).
   * Static posture (e.g. from 6A: mule roles, risky merchant flags).
   * Baseline vs overlay comparison (if S2 is used): e.g. magnitude of distortions, timing anomalies.

2. **Apply deterministic truth rules**

   Using `truth_labelling_policy_6B`, S4 MUST:

   * Evaluate deterministic rules that classify flows unambiguously, e.g.:

     * If `fraud_pattern_type` is a known fraud pattern associated with `campaign_type`, mark `FRAUD` with a specific subtype.
     * If `fraud_pattern_type = NONE` and all overlays flags are false, mark `LEGIT`.
     * If specific abuse pattern flags set (e.g. refund-abuse overlay) and policy says “this is abuse, not fraud”, mark `ABUSE_*`.

   * These rules MUST be applied in a documented precedence order (e.g. primary campaign → posture-based override → residual heuristics). Rules that fully determine the truth label MUST NOT consume RNG.

3. **Handle ambiguous & collateral cases (with RNG)**

   For flows where deterministic rules leave multiple plausible truth labels (e.g. ambiguous collateral flows around a primary fraud event):

   * Determine the **set of candidate truth labels** and associated probabilities, as defined in `truth_labelling_policy_6B`.
   * Use `rng_event_truth_label_ambiguity`:

     * Key: `(manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, "truth")`.
     * Draw exactly the configured number of uniforms.
     * Map draws to a single label choice using the configured distribution.

   The selected label becomes the flow’s truth label.

4. **Populate `s4_flow_truth_labels_6B` row**

   For each flow, construct a row with:

   * axes + `flow_id`,
   * `truth_label`, `truth_subtype`,
   * `label_policy_id` = id/version of `truth_labelling_policy_6B`,
   * `campaign_id` (from S3, if present),
   * `pattern_source` (e.g. `CAMPAIGN`, `COLLATERAL`, `HEURISTIC_ONLY`).

At the end of Step 1, every flow in S3 has an assigned **truth** row; there are no unlabeled flows.

---

### 6.4 Step 2 — Flow-level bank-view simulation

Using truth labels and bank-view policy, S4 simulates how the bank sees each flow.

For each flow `f`:

1. **Derive bank-view context**

   Build an input context for `bank_view_policy_6B` including:

   * truth label and subtype from Step 1,
   * S3 overlay metadata (`campaign_id`, `fraud_pattern_type`, overlay flags),
   * any risk scores or posture signals from 6A,
   * S2/S3 timing and amounts,
   * scenario metadata.

2. **Auth decision (deterministic or with RNG)**

   Using `bank_view_policy_6B`:

   * For flows with certain patterns, auth decision may be deterministic (e.g. some flows always DECLINE at auth).
   * For others, policy may prescribe probabilities (e.g. 0.5 manual-review vs 0.5 approve):

     * Use a dedicated family within S4 RNG (often `rng_event_detection_delay` or a separate `rng_event_auth_decision` if defined) keyed on `(mf, ph, seed, scenario_id, flow_id, "auth_decision")`.
     * Draw configured number of uniforms and map to auth_decision.

3. **Detection outcome & detection delay**

   Given auth decision, truth label, and bank-view policy:

   * Determine whether the flow is subject to fraud detection at all (e.g. only flows with fraud-related patterns).

   * If detection is deterministic (e.g. always detected at auth for certain patterns), set:

     * `detection_outcome = "DETECTED_AT_AUTH"`,
     * `detection_ts_utc` = appropriate auth-time timestamp from S3.

   * If detection is probabilistic and/or delayed:

     * Use `rng_event_detection_delay` keyed on `(mf, ph, seed, scenario_id, flow_id)` to decide detection vs non-detection and sample detection delay from `delay_models_6B`.
     * If not detected, set `detection_outcome = "NOT_DETECTED"`, `detection_ts_utc = null`.

4. **Disputes & chargebacks**

   Given truth label, detection outcome, and `bank_view_policy_6B`:

   * If the flow is eligible for customer dispute (e.g. fraud or certain abuse types), use `delay_models_6B` and `rng_event_dispute_delay` to decide:

     * whether a dispute occurs,
     * if so, `dispute_ts_utc`.

   * If dispute occurs (and policy says a chargeback is possible):

     * Use `rng_event_chargeback_delay` and related configs to determine:

       * whether a chargeback is initiated,
       * its type,
       * `chargeback_ts_utc`,
       * chargeback outcome (win/loss, partial/ full).

5. **Final bank-view label & lifecycle timestamps**

   Combine:

   * auth decision,
   * detection outcome + ts,
   * dispute/chargeback outcomes + ts,
   * case-level decisions (if some flows are resolved as non-fraud despite suspicion),

   to derive `bank_view_label` and set `case_opened_ts_utc` / `case_closed_ts_utc` (preliminary; case-timeline may adjust those later).

6. **Populate `s4_flow_bank_view_6B` row**

   For each flow, construct a row with:

   * axes + `flow_id`,
   * `auth_decision`, `detection_outcome`, `bank_view_label`,
   * relevant timestamps (`detection_ts_utc`, `dispute_ts_utc`, `chargeback_ts_utc`, `case_opened_ts_utc`, `case_closed_ts_utc`),
   * references to policy ids (`bank_view_policy_id`, `delay_model_id`).

At the end of Step 2, every flow has a **single, consistent bank-view outcome** compatible with truth labels and policies.

---

### 6.5 Step 3 — Event-level label assignment

For each event `e` in `s3_event_stream_with_fraud_6B@{seed,fingerprint,scenario_id}`:

1. **Pull context**

   * Flow-level truth & bank-view labels from Steps 1–2.
   * S3 event-level overlay fields (`fraud_pattern_type`, overlay flags, `origin_*`).
   * Bank-view context (e.g. whether event falls before/after detection/dispute/chargeback times).

2. **Truth-level event roles**

   Using `truth_labelling_policy_6B`:

   * Compute `is_fraud_event_truth` and `truth_event_role`, e.g.:

     * If the event is part of the fraudulent pattern (e.g. a fraudulent auth), mark `PRIMARY_FRAUD_ACTION`.
     * If it is a non-fraud event in a fraud flow (e.g. legit-looking setup or trailing noise), mark `SUPPORTING_EVENT` or `LEGIT_CONTEXT`.
     * If it is a detection or case-management event (if such events are represented in S3), mark `DETECTION_ACTION` or `CASE_EVENT`.

   Deterministic classification is preferred; RNG may be used (via `rng_event_truth_label_ambiguity`) only for ambiguous assignment of secondary roles, per policy.

3. **Bank-view flags**

   Using `bank_view_policy_6B`:

   * Set `is_detection_action` true for events that represent detection or manual review actions.
   * Set `is_case_event` true for events that represent case lifecycle actions (if represented in S3).
   * Optionally set `bank_event_label` with a more detailed classification (e.g. `FLAGGED_SUSPICIOUS`, `CASE_NOTE`, `AUTO_DECLINE_SIGNAL`).

4. **Populate `s4_event_labels_6B` rows**

   For each event, write a row with:

   * axes + `flow_id`, `event_seq`,
   * truth-level fields (`is_fraud_event_truth`, `truth_event_role`),
   * bank-view fields (`is_detection_action`, `is_case_event`, `bank_event_label`),
   * policy ids as needed.

At the end of Step 3, event-level truth and bank-view flags are fully derived and consistent with flow-level labels and timelines.

---

### 6.6 Step 4 — Case construction & timeline

S4 now constructs cases according to `case_policy_6B`, using flow-level truth and bank-view outcomes.

1. **Define case keys & grouping strategy**

   From `case_policy_6B`, S4 MUST have a deterministic definition of **case keys**, e.g.:

   ```text
   case_key = { account_id, instrument_id, manifest_fingerprint, seed }
   ```

   or a richer structure including merchant/region/time windows, depending on policy.

2. **Allocate flows to cases**

   For flows that require case handling (e.g. flows with disputes/chargebacks or certain fraud/abuse scenarios):

   * Group flows by `case_key` (deterministic).
   * For each group and policy, decide:

     * whether a single case or multiple cases are opened,
     * which flows are bundled into each case.

   If there is stochastic choice here (e.g. random assignment of flows to multiple cases in a group), S4 MUST use `rng_event_case_timeline` with keys derived from `(mf, ph, seed, case_key, flow_id)` and fixed budgets.

3. **Assign `case_id`s deterministically**

   For each case:

   * Generate a `case_id` using a deterministic scheme, e.g.:

     ```text
     case_id = hash64(manifest_fingerprint, seed, case_key, case_index_within_key)
     ```

   * Ensure that `(seed, manifest_fingerprint, case_id)` is unique.

4. **Build case timelines**

   For each case:

   * Construct a sequence of **case events** (`case_event_type`, `case_event_ts_utc`, optional link to `flow_id` / `event_seq`) consistent with:

     * flow-level bank-view labels from Step 2 (e.g. case opened when a dispute or detection occurs),
     * delay models (`delay_models_6B`) and any randomness via `rng_event_case_timeline`,
     * case state machine in `case_policy_6B` (allowed transitions, maximum durations).

   * Construct `case_event_seq` as a contiguous, strictly monotone sequence per case (starting at 0 or 1 per schema).

5. **Populate `s4_case_timeline_6B`**

   For each case event, emit a row with:

   * axes + `case_id`, `case_event_seq`,
   * `case_event_type`, `case_event_ts_utc`,
   * linkage fields (`flow_id`/`flow_ids`, `event_seq` if applicable),
   * policy ids as needed.

At the end of Step 4, case timelines are fully specified and consistent with flow-level bank-view outcomes.

---

### 6.7 Step 5 — Write outputs & enforce idempotence

For each `(seed, manifest_fingerprint, scenario_id)`:

1. **Construct & validate per-partition label datasets**

   * Build `s4_flow_truth_labels_6B` and `s4_flow_bank_view_6B` rows in memory or in a streaming fashion.
   * Build `s4_event_labels_6B` rows per event.

   Before writing:

   * Validate each dataset against its schema anchor.
   * Ensure PK uniqueness and that every `flow_id`/`event_seq` in S3 overlays has exactly one corresponding label row.

2. **Write flow & event labels**

   * Write `s4_flow_truth_labels_6B` and `s4_flow_bank_view_6B` to their respective partition paths.
   * Write `s4_event_labels_6B` likewise.

3. **Construct & validate case timeline (per `(seed, fingerprint)`)**

   * Build `s4_case_timeline_6B` rows aggregating across all scenarios for the given `(seed, fingerprint)` if policy spans multiple scenarios.
   * Validate schema + PK/ordering constraints (`case_id`, `case_event_seq`).

4. **Write case timeline**

   * Write `s4_case_timeline_6B@{seed,fingerprint}` to its path.

5. **Idempotence rules**

   For each unit:

   * Per `(seed, fingerprint, scenario_id)`: flow/event label partitions.
   * Per `(seed, fingerprint)`: case-timeline partition.

   If outputs do **not** exist:

   * S4 writes them once.

   If outputs **do** exist:

   * S4 MUST either:

     * reproduce logically identical outputs (same rows/keys/labels/timestamps), or
     * fail with an idempotence error and MUST NOT overwrite existing data.

   Partial write states (e.g. some label tables written but not others) MUST be treated as failures by orchestrators and S5, and cleaned up/overwritten on rerun according to engine-wide recovery rules.

---

### 6.8 RNG accounting obligations

Even though full RNG reconciliation is the responsibility of S5, S4 MUST ensure that its RNG usage is internally coherent:

* For each RNG family used by S4 (`rng_event_truth_label_ambiguity`, `rng_event_detection_delay`, `rng_event_dispute_delay`, `rng_event_chargeback_delay`, `rng_event_case_timeline`):

  * The number of RNG events and draws must be:

    * deterministic given the number of flows, events, and cases in the partition and configured policies, and
    * within configured budget functions in `label_rng_policy_6B`.

* Local counters in S4 MUST be able to show:

  * how many truth-ambiguity decisions were made and how many draws were used,
  * how many detection/dispute/chargeback delay draws were used,
  * how many case-timeline decisions used RNG.

* If S4 observes that:

  * the number of draws for any family is inconsistent with expected domain size, or
  * there are zero draws where policy requires stochastic behaviour,

  it MUST treat this as a failure for the affected partition and not publish labels.

Together with §§1–5, this algorithm defines S4 as a **deterministic, RNG-accounted labelling layer**: it takes sealed S3 overlays plus upstream context and produces reproducible truth & bank-view label surfaces and case timelines that S5 and downstream consumers can trust.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S4’s outputs are identified and stored**, and what rules implementations MUST follow for **partitioning, ordering, coverage, re-runs and merges**.

It applies to all four S4 datasets:

* `s4_flow_truth_labels_6B`
* `s4_flow_bank_view_6B`
* `s4_event_labels_6B`
* `s4_case_timeline_6B`

and is binding for any conforming implementation.

---

### 7.1 Identity axes

S4 has two natural identity scopes:

* **Flow/event labels** — per `(manifest_fingerprint, seed, scenario_id)`
* **Case timeline** — per `(manifest_fingerprint, seed)`

Binding rules:

1. All S4 rows MUST carry their axes explicitly as columns:

   * `s4_flow_truth_labels_6B`: `manifest_fingerprint`, `seed`, `scenario_id`, `flow_id`.
   * `s4_flow_bank_view_6B`: `manifest_fingerprint`, `seed`, `scenario_id`, `flow_id`.
   * `s4_event_labels_6B`: `manifest_fingerprint`, `seed`, `scenario_id`, `flow_id`, `event_seq`.
   * `s4_case_timeline_6B`: `manifest_fingerprint`, `seed`, `case_id`, `case_event_seq`.

2. S4 MUST NOT introduce `run_id` or any other execution identifier as a partition key in these datasets. `run_id` is reserved for RNG/logging artefacts.

3. For a given world (`manifest_fingerprint`) and run (`seed`), S4 operates on exactly the same set of `scenario_id`s as S3 overlays (i.e. those for which S3 is PASS).

---

### 7.2 Partitioning & path layout

The partitioning and path templates for S4 outputs are:

* **Flow truth labels**:

  * `partitioning: [seed, fingerprint, scenario_id]`
  * `path`:

    ```text
    data/layer3/6B/s4_flow_truth_labels_6B/
        seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
    ```

* **Flow bank-view labels**:

  * `partitioning: [seed, fingerprint, scenario_id]`
  * `path`:

    ```text
    data/layer3/6B/s4_flow_bank_view_6B/
        seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
    ```

* **Event labels**:

  * `partitioning: [seed, fingerprint, scenario_id]`
  * `path`:

    ```text
    data/layer3/6B/s4_event_labels_6B/
        seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
    ```

* **Case timeline**:

  * `partitioning: [seed, manifest_fingerprint]`
  * `path`:

    ```text
    data/layer3/6B/s4_case_timeline_6B/
        seed={seed}/manifest_fingerprint={manifest_fingerprint}/part-*.parquet
    ```

**Path↔embed rules (binding):**

* For every row in a partitioned file:

  * In flow/event label tables: `seed`, `manifest_fingerprint`, and `scenario_id` columns MUST equal their respective path tokens.
  * In case timeline: `seed` and `manifest_fingerprint` columns MUST equal the path tokens.

No S4 data-plane rows may be written outside these layouts or with mismatched axis values.

---

### 7.3 Primary keys & writer ordering

#### 7.3.1 `s4_flow_truth_labels_6B`

**Primary key (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id]
```

**Writer ordering (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id]
```

Per `(seed, manifest_fingerprint, scenario_id)`:

* Each `flow_id` MUST be unique.
* Rows MUST be sorted by `flow_id` ascending.

#### 7.3.2 `s4_flow_bank_view_6B`

**Primary key (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id]
```

**Writer ordering (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id]
```

Per `(seed, manifest_fingerprint, scenario_id)`:

* Each `flow_id` MUST be unique.
* Rows MUST be sorted by `flow_id` ascending.
* The set of `(seed, fingerprint, scenario_id, flow_id)` keys MUST be identical to the set in `s4_flow_truth_labels_6B` and to `s3_flow_anchor_with_fraud_6B`.

#### 7.3.3 `s4_event_labels_6B`

**Primary key (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
```

**Writer ordering (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
```

Per `(seed, manifest_fingerprint, scenario_id, flow_id)`:

* `(flow_id, event_seq)` MUST be unique.
* Rows MUST be grouped by `flow_id` and sorted by `event_seq` ascending.
* For each flow, `event_seq` MUST form a contiguous, monotone sequence (e.g. 0..N-1 or 1..N), consistent with the event PK in S3.

#### 7.3.4 `s4_case_timeline_6B`

**Primary key (binding):**

```text
[seed, manifest_fingerprint, case_id, case_event_seq]
```

**Writer ordering (binding):**

```text
[seed, manifest_fingerprint, case_id, case_event_seq]
```

Per `(seed, manifest_fingerprint, case_id)`:

* `(case_id, case_event_seq)` MUST be unique.
* `case_event_seq` MUST be a contiguous, strictly monotone sequence for that case.
* Each case MUST have ≥1 event row.

---

### 7.4 Coverage & relationship to S3 overlays

For each `(manifest_fingerprint, seed, scenario_id)` where S3 is PASS and S4 runs:

Let:

* `FA3` = `s3_flow_anchor_with_fraud_6B@{seed,fingerprint,scenario_id}`
* `EV3` = `s3_event_stream_with_fraud_6B@{seed,fingerprint,scenario_id}`
* `TL4` = `s4_flow_truth_labels_6B@{seed,fingerprint,scenario_id}`
* `BV4` = `s4_flow_bank_view_6B@{seed,fingerprint,scenario_id}`
* `EL4` = `s4_event_labels_6B@{seed,fingerprint,scenario_id}`

Binding relationships:

1. **Flow coverage**

   * Truth labels coverage:

     ```text
     {flow_id(FA3)} == {flow_id(TL4)}
     ```

   * Bank-view coverage:

     ```text
     {flow_id(FA3)} == {flow_id(BV4)}
     ```

   That is, every flow in S3 overlays has exactly one truth row and one bank-view row; no extra flows appear in labels.

2. **Event coverage**

   * For event keys `K = (seed, fingerprint, scenario_id, flow_id, event_seq)`:

     ```text
     {K(EV3)} == {K(EL4)}
     ```

   Every event in S3 overlays has exactly one label row; no extra labelled events exist.

3. **Case coverage**

   * For any flow that S4 marks as “case-involved” in `BV4` (e.g. non-null case flags), there MUST be at least one row in `s4_case_timeline_6B@{seed,fingerprint}` with a `case_id` that references that flow (via `flow_id` or related linkage).

The detailed invariants are checked in S4’s acceptance criteria; here we fix that all such relationships are expressible via keys and that joins are unambiguous.

---

### 7.5 Re-run & idempotence discipline

S4 MUST be **idempotent** per configuration and domain:

> For fixed `(manifest_fingerprint, parameter_hash, seed, scenario_id)` and fixed upstream inputs, a re-run of S4 MUST either reproduce identical outputs or fail without overwriting.

Binding rules:

1. **Unit of work**

   * For flow/event labels: the unit is `(manifest_fingerprint, seed, scenario_id)` — all three label tables for that partition.
   * For the case timeline: the unit is `(manifest_fingerprint, seed)`.

   Within each unit:

   * S4 MUST treat all relevant S4 datasets as a **set**: they are either all written successfully and considered valid, or none are.

2. **Single logical writer per unit**

   * At any time, only one S4 instance may be responsible for writing a given unit:

     * `(seed, fingerprint, scenario_id)` for flow/event labels,
     * `(seed, fingerprint)` for case timeline.

   * Parallelism across different seeds or scenarios is allowed; concurrent writes to the same unit by multiple instances are disallowed.

3. **Idempotent re-runs**

   For each unit:

   * If no S4 outputs exist yet, S4 writes them once.
   * If outputs already exist, a re-run under the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)` MUST either:

     * produce logically identical content (same keys, same labels, same timestamps), or
     * fail with an idempotence error (e.g. `S4_IDEMPOTENCE_VIOLATION`) and MUST NOT overwrite existing data.

   Incremental append/merge semantics (e.g. “adding labels for some flows later”) are forbidden.

4. **Partial write failure handling**

   * If S4 fails after writing some, but not all, of the outputs in a unit (e.g. flow truth labels written but bank-view labels not), that unit MUST be considered FAILED.
   * Orchestrators and S5 MUST treat partial S4 outputs as invalid and ensure they are either deleted or overwritten on a clean re-run, in line with engine-wide recovery rules.

---

### 7.6 Join discipline for downstream consumers

Downstream states (S5, 4A/4B, model-training) MUST use explicit keys for joins:

* **Flows:**

  * Join S3 overlays and S4 labels via:

    ```text
    [seed, manifest_fingerprint, scenario_id, flow_id]
    ```

  * This is the canonical link from behaviour to truth/bank-view labels.

* **Events:**

  * Join S3 events and S4 event labels via:

    ```text
    [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
    ```

* **Cases:**

  * Join S4 case timeline with flow labels via:

    ```text
    [seed, manifest_fingerprint, case_id]  // to get events
    [seed, manifest_fingerprint, scenario_id, flow_id]  // via linkage fields in case events
    ```

No consumer may infer relationships solely from file paths or ordering; identity is always expressed through these columns plus partition axes.

---

### 7.7 Interaction with RNG logs (non-partition identity)

S4 consumes RNG via its families (`rng_event_truth_label_ambiguity`, `rng_event_detection_delay`, etc.), whose **RNG log artefacts** (if materialised) are partitioned according to the Layer-3 RNG law (typically `[seed, parameter_hash, run_id]`).

Binding points:

* S4 label datasets MUST NOT:

  * include `run_id` as a partition key, or
  * rely on RNG-log partitioning for their identity.

* RNG log events MUST encode sufficient keys (e.g. `flow_id`, `scenario_id`, decision stage) for S5 to reconcile:

  * how many ambiguity/detection/dispute/chargeback decisions were made, and
  * whether per-family draw counts match the expected domain size.

The only connection between RNG logs and S4 labels is via shared axes (`seed, parameter_hash`) and identifiers (e.g. `flow_id`, `case_id`); labels themselves are not partitioned by RNG state.

---

By adhering to these identity, partitioning, ordering, and merge rules, S4 remains:

* a deterministic, reproducible labelling layer on top of S3 overlays and upstream context, and
* a stable, unambiguous source of truth and bank-view labels for S5 and the wider fraud platform to consume.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines:

* When 6B.S4 is considered **PASS** vs **FAIL**, and
* How that status **gates** 6B.S5 (validation/HashGate) and external consumers (4A/4B, model-training).

S4 has two scopes:

* **Flow/event labelling scope** — per `(manifest_fingerprint, seed, scenario_id)`.
* **Case timeline scope** — per `(manifest_fingerprint, seed)`.

S4 is only **acceptable for a world** if **both** scopes satisfy their acceptance criteria.

---

### 8.1 Domains of evaluation

* **Partition-level (flows/events)**:
  For each `(manifest_fingerprint, seed, scenario_id)`, S4 evaluates:

  * `s4_flow_truth_labels_6B@{seed,fingerprint,scenario_id}`
  * `s4_flow_bank_view_6B@{seed,fingerprint,scenario_id}`
  * `s4_event_labels_6B@{seed,fingerprint,scenario_id}`

* **Case-level (timeline)**:
  For each `(manifest_fingerprint, seed)`, S4 evaluates:

  * `s4_case_timeline_6B@{seed,fingerprint}`

Acceptance is decided separately per scope, but S5 will treat **any** failure in either as a segment-level failure for that world.

---

### 8.2 Acceptance criteria — flow/event labelling (per `(manifest_fingerprint, seed, scenario_id)`)

For a fixed `(manifest_fingerprint, seed, scenario_id)`, S4 is considered **PASS** for flow/event labelling if and only if all of the following hold.

#### 8.2.1 Preconditions satisfied

* S0 is PASS for `manifest_fingerprint` and `s0_gate_receipt_6B` / `sealed_inputs_6B` are present and schema-valid.

* Upstream HashGates (`1A–3B`, `5A`, `5B`, `6A`) are `status="PASS"` in the S0 receipt.

* S1, S2, and S3 are PASS for this `(manifest_fingerprint, seed, scenario_id)` in the run-report.

* Required S1/S2/S3 datasets for this partition are present and schema-valid:

  * `s1_arrival_entities_6B`, `s1_session_index_6B`
  * `s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`
  * `s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`

* Required S4 configuration packs (truth policy, bank-view policy, delay models, case policy, RNG policy) are present in `sealed_inputs_6B` and schema-valid.

If any of these fail, S4 MUST **not** attempt labelling and MUST mark this partition as FAIL with an appropriate precondition error.

#### 8.2.2 Schema & identity validity of S4 outputs

For this `(seed, fingerprint, scenario_id)`:

* `s4_flow_truth_labels_6B` MUST validate against `schemas.6B.yaml#/s4/flow_truth_labels_6B`.
* `s4_flow_bank_view_6B` MUST validate against `schemas.6B.yaml#/s4/flow_bank_view_6B`.
* `s4_event_labels_6B` MUST validate against `schemas.6B.yaml#/s4/event_labels_6B`.

And:

* PKs MUST be unique:

  * Truth/bank-view: `[seed, manifest_fingerprint, scenario_id, flow_id]`.
  * Event labels: `[seed, manifest_fingerprint, scenario_id, flow_id, event_seq]`.

* Partition columns in rows MUST match path tokens:

  * `seed`, `manifest_fingerprint`, `scenario_id`.

Any schema or identity failure MUST cause S4 to FAIL this partition.

#### 8.2.3 Coverage with respect to S3 flows

Let:

* `FA3` = `s3_flow_anchor_with_fraud_6B@{seed,fingerprint,scenario_id}`
* `TL4` = `s4_flow_truth_labels_6B@{seed,fingerprint,scenario_id}`
* `BV4` = `s4_flow_bank_view_6B@{seed,fingerprint,scenario_id}`

Then:

1. **Truth coverage**

   ```text
   {flow_id(FA3)} == {flow_id(TL4)}
   ```

2. **Bank-view coverage**

   ```text
   {flow_id(FA3)} == {flow_id(BV4)}
   ```

3. **Consistency between truth and bank-view sets**

   ```text
   {flow_id(TL4)} == {flow_id(BV4)} == {flow_id(FA3)}
   ```

Every flow S3 defines **must** have exactly one truth row and one bank-view row; no extra flow_ids may appear in S4 tables.

If these sets differ in any way, S4 MUST FAIL the partition.

#### 8.2.4 Coverage with respect to S3 events

Let:

* `EV3` = `s3_event_stream_with_fraud_6B@{seed,fingerprint,scenario_id}`
* `EL4` = `s4_event_labels_6B@{seed,fingerprint,scenario_id}`
* Use `K = (seed, manifest_fingerprint, scenario_id, flow_id, event_seq)` as the event key.

Then:

```text
{K(EV3)} == {K(EL4)}
```

Every event in S3 overlays MUST have exactly one event-label row in S4; no extra events may be labelled.

If this equality fails, S4 MUST FAIL the partition.

#### 8.2.5 Truth ↔ campaign/behaviour consistency

For each flow:

* Truth labels in `TL4` MUST be consistent with:

  * `fraud_pattern_type`, `campaign_id`, and overlay flags in `FA3`/`EV3`,
  * static posture (6A) and any additional heuristics as defined in `truth_labelling_policy_6B`.

Examples of required consistency:

* Flows with no campaign and no overlay anomalies SHOULD be labelled `LEGIT` unless explicitly overridden in policy.
* Flows tagged by S3 as belonging to a clear fraud pattern (e.g. card testing campaign) MUST be labelled as `FRAUD_*` or `ABUSE_*` consistent with that pattern, not `LEGIT`.
* Collateral flows labelled as fraud/abuse MUST be explainable via policy rules (e.g. “flows within this window on the same account are considered fraud”) and MUST not contradict S3 overlay semantics.

S4 MUST treat violations of truth-policy consistency as failures (e.g. `S4_TRUTH_CONSISTENCY_FAILED`).

#### 8.2.6 Bank-view ↔ truth / policy consistency

For each flow, bank-view labels in `BV4` MUST be consistent with:

* truth label (e.g. a true-fraud flow cannot end with a bank-view “confirmed legit” if policy forbids that outcome),
* S3 behaviour (e.g. no detection before the flow’s events exist),
* `bank_view_policy_6B` and `delay_models_6B`.

Examples:

* A `BANK_CONFIRMED_FRAUD` outcome MUST only occur on flows with truth label `FRAUD_*` (or defined abuse types) and detection present, with `detection_ts_utc` within the world horizon and consistent with event timings.
* A `NO_CASE_OPENED` outcome MUST have `case_opened_ts_utc = null` and no case events referring to that flow.
* Timestamps MUST respect ordering constraints (e.g. `detection_ts_utc ≤ case_opened_ts_utc ≤ case_closed_ts_utc`, when non-null) and MUST be consistent with delay models.

Any violation MUST cause S4 to FAIL this partition (e.g. `S4_BANK_VIEW_CONSISTENCY_FAILED`).

#### 8.2.7 Event-level label consistency

For each event row:

* Truth event role and `is_fraud_event_truth` MUST be consistent with:

  * the flow’s truth label,
  * event type and overlay flags in `EV3`,
  * `truth_labelling_policy_6B`.

* Bank-view event flags MUST be consistent with `bank_view_policy_6B` and flow-level bank-view outcomes:

  * Events marked `is_detection_action` MUST occur at or before `detection_ts_utc` and MUST be consistent with detection decisions.
  * Events marked `is_case_event` MUST be reflected in `s4_case_timeline_6B` for the corresponding case (subject to how S4 encodes case events).

Inconsistent event labels MUST cause S4 to FAIL (e.g. `S4_LABEL_SCHEMA_VIOLATION` or `S4_TRUTH_CONSISTENCY_FAILED`).

#### 8.2.8 RNG envelope sanity (local to S4)

For the partition:

* For each S4 RNG family (`rng_event_truth_label_ambiguity`, `rng_event_detection_delay`, etc.), the number of draws MUST be:

  * consistent with the number of decisions made (flows requiring ambiguity resolution, flows subject to detection/delay draws, etc.), and
  * within configured budgets in `label_rng_policy_6B`.

If S4 observes that RNG usage is inconsistent with domain size (e.g. zero draws where stochastic behaviour is required, or excessive draws beyond configured bounds), it MUST FAIL the partition.

---

### 8.3 Acceptance criteria — case timeline (per `(manifest_fingerprint, seed)`)

For a fixed `(manifest_fingerprint, seed)`, S4 is considered **PASS** at the case level if and only if:

1. **Preconditions satisfied**

   * S4 flow/event labelling is PASS for all `(manifest_fingerprint, seed, scenario_id)` partitions that feed into this `(seed, fingerprint)`.
   * `s4_case_timeline_6B@{seed,fingerprint}` exists and passes schema/PK/partition validation.

2. **Case identity & coverage**

   * `(seed, manifest_fingerprint, case_id, case_event_seq)` keys are unique.
   * For each `case_id`, `case_event_seq` is contiguous and strictly monotone.
   * For any flow that bank-view labels indicate is in a case (e.g. has non-null `case_opened_ts_utc` or a case-related `bank_view_label`), there MUST exist at least one case event in `s4_case_timeline_6B` linking that flow to a `case_id`.

3. **Case lifecycle consistency**

   For each `case_id`:

   * Case events MUST follow the state machine defined in `case_policy_6B` (e.g. you cannot close a case before it’s opened; you cannot have multiple `CASE_OPENED` events without an intervening closure if policy forbids it).
   * Event timestamps in the case timeline MUST be non-decreasing and consistent with the flow-level timestamps (e.g. case opening at or after detection/dispute, case closure at or after last case event).
   * Case-level outcomes MUST be consistent with affected flows’ bank-view labels (e.g. a case that ends in a bank-confirmed fraud decision MUST correspond to at least one flow with `BANK_CONFIRMED_FRAUD`).

Any violation MUST cause S4 to FAIL the case scope for `(seed, fingerprint)`.

---

### 8.4 Conditions that MUST cause S4 to FAIL

S4 MUST mark the corresponding scope (partition or world/seed) as **FAIL** if any of the following occur:

* Preconditions in §2 are not met.
* Any S4 output fails schema/PK/partition validation.
* Flow/event coverage invariants in §8.2.3–§8.2.4 are violated.
* Truth ↔ behaviour/campaign consistency fails (§8.2.5).
* Bank-view ↔ truth/policy consistency fails (§8.2.6).
* Event-level label consistency fails (§8.2.7).
* RNG envelope sanity checks fail (§8.2.8).
* Case ID / timeline invariants (§8.3) are violated.
* Output write/idempotence rules in §7.5 are violated (e.g. partial label surfaces, non-idempotent re-runs).

On FAIL:

* S4 outputs for that scope MUST be considered **unusable**.
* Downstream consumers MUST NOT treat labels for that scope as valid.

---

### 8.5 Gating obligations for S5 (6B validation/HashGate)

S5 (6B validation/HashGate) MUST:

* Treat S4’s acceptance criteria in this section as **binding checks**:

  * verify schema/PK/partition rules for all S4 datasets,
  * verify coverage of S3 flows/events by S4 labels,
  * verify truth and bank-view consistency versus S3 behaviour and S4 policies,
  * verify case timeline consistency and RNG envelopes.

* Consider **any** S4 failure (for any `(seed, scenario_id)` or `(seed)` case scope) as a **segment-level FAIL** for the corresponding `manifest_fingerprint`.

* Include S4 label and case surfaces (and their run-report summary) as first-class artefacts in the 6B validation bundle for that world.

S5 MUST NOT declare the 6B segment HashGate PASS if S4 has not PASSed all required scopes for that world.

---

### 8.6 Gating obligations for 4A/4B & model-training consumers

External consumers (4A/4B, model-training, evaluation pipelines) MUST:

* Only treat S4 outputs as **authoritative labels** if:

  * S0 is PASS for the world, and
  * the 6B segment HashGate (S5) is PASS for that `manifest_fingerprint`.

* NOT rely directly on S4’s `status` alone; they should gate on S5’s HashGate, which subsumes S4’s status.

* Use S4’s label surfaces as the **single source of truth and bank-view labels**:

  * they MUST NOT attempt to re-derive labels from S3 behaviour in ways that conflict with S4,
  * any training/evaluation logic that uses behaviour should do so in conjunction with S4 labels, not in place of them.

Under this contract, if S5 indicates that a world is PASS, consumers may safely regard S4 as providing a complete, coherent, and policy-consistent labelling of all flows/events/cases in that world.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical failure modes** for 6B.S4 and the **error codes** that MUST be used when they occur.

For any scope S4 attempts:

* **Flow/event-labelling scope**: `(manifest_fingerprint, seed, scenario_id)`
* **Case-timeline scope**: `(manifest_fingerprint, seed)`

S4 MUST:

* End each scope with exactly one of: `status = "PASS"` or `status = "FAIL"`.
* If `status = "FAIL"`, attach a **single primary error code** from this section, and MAY attach secondary codes and diagnostics.

Downstream components (S5, 4A/4B, model-training) MUST treat any S4 failure as a **hard gate** for that scope.

---

### 9.1 Error model & context

For any failed S4 scope:

* **Primary error code**

  * One code from §§9.2–9.8 (e.g. `S4_LABEL_COVERAGE_MISMATCH`).
  * Summarises the main cause of failure.

* **Secondary error codes** (optional)

  * A list of additional codes providing more detail (e.g. both `S4_TRUTH_CONSISTENCY_FAILED` and `S4_BANK_VIEW_CONSISTENCY_FAILED`).
  * MUST NOT be present without a primary code.

* **Context fields** (run-report/logs SHOULD include):

  * `manifest_fingerprint`
  * `seed`
  * `scenario_id` (for flow/event scope; MAY be null for case-only failures)
  * Optionally `flow_id`, `event_seq`, `case_id`, `case_event_seq`, `owner_segment`, `manifest_key`
  * Optional human-readable `detail`.

The run-report schema (Section 10) MUST be able to carry these fields.

---

### 9.2 Preconditions & sealed-input/config failures

These indicate S4 never legitimately entered the labelling workflow for the relevant scope.

#### 9.2.1 `S4_PRECONDITION_S0_S1_S2_S3_FAILED`

**Definition**
Emitted when S4 is invoked but any of S0, S1, S2, or S3 is not PASS for the necessary axes.

**Examples**

* S0 not PASS for `manifest_fingerprint` (world not sealed).
* S1, S2, or S3 not PASS for `(manifest_fingerprint, seed, scenario_id)` in the run-report.
* Required S1/S2/S3 datasets missing or schema-invalid for that partition.

**Obligations**

* S4 MUST NOT read S1/S2/S3 data-plane surfaces.
* No S4 label outputs may be written for that scope.

---

#### 9.2.2 `S4_PRECONDITION_SEALED_INPUTS_INCOMPLETE`

**Definition**
Emitted when `sealed_inputs_6B` is present but lacks required entries for S4.

**Examples**

* `s3_flow_anchor_with_fraud_6B` or `s3_event_stream_with_fraud_6B` absent or not marked `status="REQUIRED", read_scope="ROW_LEVEL"`.
* Required 6A posture surfaces missing where label policy requires them.
* Required S4 config packs (truth/bank-view policy, delay models, case policy, RNG policy) missing or mis-declared in `sealed_inputs_6B`.

**Obligations**

* S4 MUST NOT guess dataset locations or read unsanctioned artefacts.
* S4 MUST fail before reading data-plane rows.

---

#### 9.2.3 `S4_PRECONDITION_LABEL_POLICY_INVALID`

**Definition**
Emitted when S4’s policy/config packs required for labelling cannot be loaded or validated.

**Examples**

* `truth_labelling_policy_6B` or `bank_view_policy_6B` missing or failing schema validation.
* `delay_models_6B` or `case_policy_6B` inconsistent (e.g. negative delays, invalid state machine).
* Configuration contradicts itself (e.g. a combination of labels that can’t be represented given schema enums).

**Obligations**

* S4 MUST NOT attempt truth or bank-view labelling.
* Policies must be corrected before S4 can run.

---

### 9.3 Schema & coverage failures for label outputs

These indicate S4 attempted to run but produced structurally invalid label surfaces.

#### 9.3.1 `S4_LABEL_SCHEMA_VIOLATION`

**Definition**
Emitted when any S4 label dataset fails schema or key validation.

**Examples**

* `s4_flow_truth_labels_6B` missing required fields (`truth_label`, `truth_subtype`), or wrong types.
* `s4_flow_bank_view_6B` missing `bank_view_label` or `detection_outcome`.
* `s4_event_labels_6B` missing `is_fraud_event_truth` or `truth_event_role`.
* `s4_case_timeline_6B` missing `case_event_type` or `case_event_ts_utc`.

Or:

* Duplicate PKs in any S4 dataset (e.g. same `(seed, fingerprint, scenario_id, flow_id)` appearing twice).
* Partition columns in rows (`seed`, `manifest_fingerprint`, `scenario_id`) do not match path tokens.

**Obligations**

* S4 MUST treat the affected scope as FAIL.
* Downstream consumers MUST NOT use the malformed tables.

---

#### 9.3.2 `S4_LABEL_COVERAGE_MISMATCH`

**Definition**
Emitted when S4’s label surfaces do not cover S3’s flows/events exactly.

**Examples**

* Some `flow_id`s in `s3_flow_anchor_with_fraud_6B` have no row in `s4_flow_truth_labels_6B` or `s4_flow_bank_view_6B`.
* Extra `flow_id`s appear in S4 labels that do not exist in S3 overlays.
* Some `(flow_id, event_seq)` in `s3_event_stream_with_fraud_6B` have no corresponding row in `s4_event_labels_6B`, or vice versa.

**Obligations**

* S4 MUST fail; label coverage must be fixed before outputs are considered usable.

---

### 9.4 Truth & bank-view consistency failures

These indicate that labels contradict S3 behaviour, posture, or S4 policy.

#### 9.4.1 `S4_TRUTH_CONSISTENCY_FAILED`

**Definition**
Emitted when flow-level truth labels in `s4_flow_truth_labels_6B` are inconsistent with S3 overlays, 6A posture, or `truth_labelling_policy_6B`.

**Examples**

* A flow clearly tagged by S3 as a card-testing campaign (`fraud_pattern_type="CARD_TESTING"`) is labelled `truth_label="LEGIT"` when policy forbids that.
* A flow with no fraud/abuse pattern and no overlay anomalies is labelled `FRAUD` without a policy rule that explains it.
* Collateral flows are labelled as fraud/abuse in ways that contradict policy (e.g. not in the allowed time window or on the wrong entity).

**Obligations**

* S4 MUST fail the partition. Truth labels must be recomputed according to policy.

---

#### 9.4.2 `S4_BANK_VIEW_CONSISTENCY_FAILED`

**Definition**
Emitted when flow-level bank-view labels in `s4_flow_bank_view_6B` are inconsistent with:

* truth labels,
* S3 behaviour and event timings, or
* `bank_view_policy_6B` and `delay_models_6B`.

**Examples**

* A flow with `truth_label="FRAUD_*"` is labelled `bank_view_label="BANK_CONFIRMED_LEGIT"` where policy forbids such outcomes.
* `detection_outcome="DETECTED_AT_AUTH"` but `detection_ts_utc` is after all flow events, or null.
* Chargeback timestamps precede disputes or real transaction timestamps in ways that violate delay models.
* `case_opened_ts_utc` is after `case_closed_ts_utc`, or inconsistent with case policy.

**Obligations**

* S4 MUST fail the partition; bank-view labels must be corrected.

---

#### 9.4.3 `S4_CASE_TIMELINE_INCONSISTENT`

**Definition**
Emitted when `s4_case_timeline_6B` is inconsistent with:

* flow-level bank-view labels,
* case state machine in `case_policy_6B`, or
* temporal ordering constraints.

**Examples**

* A `CASE_CLOSED` event appears before a `CASE_OPENED` event for the same `case_id`.
* Case events reference flows that bank-view labels say are not in any case.
* Case timelines show sequences of events that violate allowed transitions (e.g. 2 consecutive `CASE_OPENED` events without closure, when policy forbids that).
* Case events have timestamps earlier than flow events they are supposed to respond to, beyond allowed delay tolerances.

**Obligations**

* S4 MUST fail the case scope `(manifest_fingerprint, seed)` and relevant partitions.
* Case construction logic must be corrected.

---

### 9.5 RNG envelope & configuration failures

These concern incorrect use or configuration of RNG in S4.

#### 9.5.1 `S4_RNG_EVENT_COUNT_MISMATCH`

**Definition**
Emitted when S4’s observed RNG usage (per-family event/draw counts) does not match the expected budgets given domain size and `label_rng_policy_6B`.

**Examples**

* Zero `rng_event_detection_delay` draws used, despite flows/policy requiring stochastic detection delays.
* More `rng_event_truth_label_ambiguity` draws than ambiguous flows.
* Orders-of-magnitude mismatch between expected and actual number of RNG events for a family.

**Obligations**

* S4 MUST fail the partition.
* RNG calling patterns and/or policy configuration must be corrected.

---

#### 9.5.2 `S4_RNG_STREAM_MISCONFIGURED`

**Definition**
Emitted when S4 cannot correctly attach to Layer-3 RNG families/streams as defined in `label_rng_policy_6B`.

**Examples**

* RNG family names in `label_rng_policy_6B` do not match the Layer-3 RNG spec.
* Substream keying reuses the same key for distinct decisions, causing counter collisions or non-monotone counter sequences.
* Another state’s RNG family is accidentally used for S4 decisions.

**Obligations**

* S4 MUST fail and **not** perform labelling until RNG configuration is corrected.

---

### 9.6 Output write & idempotence failures

#### 9.6.1 `S4_OUTPUT_WRITE_FAILED`

**Definition**
Emitted when S4 fails to persist one or more of its outputs due to I/O or infrastructure errors.

**Examples**

* Filesystem/network errors when writing parquet files.
* Permission or quota errors preventing writes to `s4_flow_*`, `s4_event_labels_6B`, or `s4_case_timeline_6B`.

**Obligations**

* S4 MUST treat the affected scope as FAIL.
* Orchestrators MUST treat any partially written outputs as invalid and handle cleanup/overwrite on retry per engine-wide recovery rules.

---

#### 9.6.2 `S4_IDEMPOTENCE_VIOLATION`

**Definition**
Emitted when S4 detects that existing outputs for a scope would be overwritten by a re-run that produces different labels for the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)` (or `(seed, fingerprint)` for case timeline).

**Examples**

* S4 config (label/delay/case policy) changes without updating `parameter_hash` or `spec_version_6B`, causing different labels for the same flows.
* Upstream S3 overlays have changed, but S4 is re-run under the old assumptions without clearing old label outputs.

**Obligations**

* S4 MUST NOT overwrite existing outputs.
* This indicates contract or environment drift; operators MUST investigate and resolve via correct versioning/rebuild.

---

### 9.7 Internal / unexpected failures

#### 9.7.1 `S4_INTERNAL_ERROR`

**Definition**
Catch-all for failures not attributable to:

* known precondition errors,
* sealed-input/config problems,
* schema/coverage/consistency violations, or
* RNG misconfiguration.

**Examples**

* Uncaught exceptions, assertion failures, or process crashes within S4 logic.
* Unexpected type errors or impossible code paths that are not yet classified into a more specific error code.

**Obligations**

* S4 MUST fail the affected scope.
* Implementations SHOULD log enough context for recurring `S4_INTERNAL_ERROR` instances to be analysed and, where possible, reclassified as more specific error codes in future spec revisions.

---

### 9.8 Surfaces & propagation

For any scope where S4 fails:

* The **Layer-3 run-report** MUST record for S4:

  * `segment = "6B"`, `state = "S4"`,
  * `manifest_fingerprint`, `seed`, `scenario_id` (or `null` for case-only failures),
  * `status = "FAIL"`,
  * `primary_error_code` (from this section),
  * optional `secondary_error_codes` and context.

* **S5 (6B validation/HashGate)** MUST:

  * treat any S4 failure as a **segment-level FAIL** for the associated `manifest_fingerprint`, and
  * propagate S4’s error codes and diagnostics into its own validation bundle and summaries.

* **4A/4B & model-training pipelines** MUST:

  * treat S4 failure (or S5 failure caused by S4) as meaning that labels for the affected world/partitions are **not trustworthy**, and
  * avoid training/evaluation on those labels until the underlying issues are resolved and S4/S5 PASS.

These error codes and behaviours are part of S4’s external contract and MUST be respected by both implementers and downstream consumers.

---

## 10. Observability & run-report integration *(Binding)*

This section specifies what 6B.S4 **must expose** for observability, and **how** its status and summaries must appear in the engine run-report.

There are two scopes:

* **Partition scope (flows/events):** per `(manifest_fingerprint, seed, scenario_id)`.
* **Case scope (case timeline):** per `(manifest_fingerprint, seed)`.

All requirements in this section are **binding**.

---

### 10.1 Run-report keying & status

#### 10.1.1 Partition scope — flow/event labelling

For every `(manifest_fingerprint, seed, scenario_id)` that S4 attempts to label, the Layer-3 run-report **MUST** contain exactly one entry:

* `segment` = `"6B"`
* `state`   = `"S4_labels"`
* `manifest_fingerprint`
* `seed`
* `scenario_id`
* `status` — `"PASS"` or `"FAIL"`
* `primary_error_code` — from §9 (or `null` if `status="PASS"`)
* `secondary_error_codes` — list (possibly empty)

Plus a **label summary** for that partition (see §10.2.1).

#### 10.1.2 Case scope — case timeline

For every `(manifest_fingerprint, seed)` for which S4 constructs case timelines, the run-report **MUST** contain exactly one entry:

* `segment` = `"6B"`
* `state`   = `"S4_cases"`
* `manifest_fingerprint`
* `seed`
* `status` — `"PASS"` or `"FAIL"`
* `primary_error_code` — from §9 (or `null` if `status="PASS"`)
* `secondary_error_codes` — list (possibly empty)

Plus a **case summary** for that `(manifest_fingerprint, seed)` (see §10.2.2).

There MUST NOT be duplicate S4 entries for the same scope in a single run-report.

---

### 10.2 Required summary metrics

#### 10.2.1 Partition summary (per `(manifest_fingerprint, seed, scenario_id)`)

For each partition S4 processes, the run-report **MUST** include a summary object containing at least:

**Flow counts & label distribution**

* `flow_count_S3`

  * Number of flows in `s3_flow_anchor_with_fraud_6B`.

* `flow_count_labeled`

  * Number of rows in `s4_flow_truth_labels_6B` (and MUST equal `flow_count_S3` on PASS).

* `truth_label_distribution`

  * Map: `truth_label → count` (e.g. `{"LEGIT": X, "FRAUD": Y, "ABUSE": Z}`).

* `truth_subtype_distribution`

  * Map: `truth_subtype → count` (e.g. `{"CARD_TESTING": a, "ATO": b, ...}`).

**Bank-view outcomes & detection/dispute statistics**

* `bank_view_label_distribution`

  * Map: `bank_view_label → count`.

* `detection_outcome_distribution`

  * Map: `detection_outcome → count` (e.g. `{"DETECTED_AT_AUTH": x, "DETECTED_POST_AUTH": y, "NOT_DETECTED": z}`).

* `fraud_flow_count_truth`

  * Number of flows with `truth_label` in the fraud family (e.g. `FRAUD_*`).

* `fraud_flow_detected_count`

  * Number of flows where `truth_label` is fraud and `detection_outcome != "NOT_DETECTED"`.

* `fraud_detection_rate`

  * Derived metric: `fraud_flow_detected_count / max(fraud_flow_count_truth, 1)`.

* `chargeback_count`

  * Number of flows with non-null `chargeback_ts_utc`.

**Event-level metrics**

* `event_count_S3`

  * Number of events in `s3_event_stream_with_fraud_6B`.

* `event_count_labeled`

  * Number of rows in `s4_event_labels_6B` (MUST equal `event_count_S3` on PASS).

* `fraud_event_count_truth`

  * Number of events with `is_fraud_event_truth = true`.

* `detection_event_count`

  * Number of events with `is_detection_action = true`.

* `case_event_flagged_count`

  * Number of events with `is_case_event = true`.

**Binding consistency flags**

* `flow_label_coverage_ok: boolean`

  * True iff `{flow_id(FA3)} == {flow_id(TL4)} == {flow_id(BV4)}` as per §8.2.3.

* `event_label_coverage_ok: boolean`

  * True iff event keys in `s3_event_stream_with_fraud_6B` and `s4_event_labels_6B` match exactly as per §8.2.4.

* `truth_consistency_ok: boolean`

  * True iff all flow truth labels are consistent with S3 overlays and `truth_labelling_policy_6B` (§8.2.5).

* `bank_view_consistency_ok: boolean`

  * True iff all bank-view labels and timestamps are consistent with truth labels, S3 overlays, and `bank_view_policy_6B` / `delay_models_6B` (§8.2.6).

If S4 reports `status="PASS"` for a partition, then:

* `flow_label_coverage_ok == true`
* `event_label_coverage_ok == true`
* `truth_consistency_ok == true`
* `bank_view_consistency_ok == true`

If any of these would be false, S4 MUST instead report `status="FAIL"` with an appropriate primary error code (§9).

#### 10.2.2 Case summary (per `(manifest_fingerprint, seed)`)

For each `(seed, fingerprint)`:

* `case_count_total`

  * Number of distinct `case_id`s in `s4_case_timeline_6B`.

* `case_event_count_total`

  * Total number of case events.

* `flows_in_cases_total`

  * Number of flows (across all scenarios) that are referenced in at least one case event.

* `flows_in_cases_by_truth_label`

  * Map: `truth_label → count of flows with that truth_label that are in at least one case`.

* `case_status_distribution` (if encoded in schema)

  * Map: final case status → count (e.g. `{"CLOSED_CONFIRMED_FRAUD": x, "CLOSED_NO_FRAUD": y, "OPEN": z}`).

* `avg_case_duration_seconds`

  * Average difference between earliest and latest event timestamp per case (for closed cases).

If case scope is `status="PASS"`, then:

* All flows with case involvement flags in `s4_flow_bank_view_6B` MUST be included in `flows_in_cases_total`.
* `case_event_count_total ≥ case_count_total` and all case timelines respect ordering/state-machine constraints (cross-checked in §8.3).

---

### 10.3 Logging requirements

S4 MUST emit structured logs for traceability and debugging.

#### 10.3.1 Partition scope logs (`S4_labels`)

For each `(manifest_fingerprint, seed, scenario_id)`:

1. **Start**

   * `event_type: "6B.S4.LABELS.START"`
   * `manifest_fingerprint`, `seed`, `scenario_id`
   * reference to S3 status (e.g. `s3_status = "PASS"`).

2. **Precondition check**

   * `event_type: "6B.S4.LABELS.PRECONDITION_CHECK"`
   * includes boolean flags for:

     * `s0_pass`, `s1_pass`, `s2_pass`, `s3_pass`
     * `configs_loaded_ok`
   * and any precondition error code if failing.

3. **Input summary**

   * `event_type: "6B.S4.LABELS.INPUT_SUMMARY"`
   * `flow_count_S3`, `event_count_S3`
   * counts of flows/events per truth-relevant attributes if available (e.g. flows with campaigns vs none).

4. **Truth labelling summary**

   * `event_type: "6B.S4.LABELS.TRUTH_SUMMARY"`
   * `truth_label_distribution` (or major buckets),
   * `truth_subtype_distribution` (if not too large),
   * count of ambiguous/collateral flows requiring RNG.

5. **Bank-view summary**

   * `event_type: "6B.S4.LABELS.BANK_VIEW_SUMMARY"`
   * `bank_view_label_distribution`, `detection_outcome_distribution`,
   * `fraud_flow_count_truth`, `fraud_flow_detected_count`, `fraud_detection_rate`.

6. **RNG usage summary**

   * `event_type: "6B.S4.LABELS.RNG_SUMMARY"`
   * counts per S4 RNG family:

     * `rng_truth_ambiguity_events`,
     * `rng_detection_delay_events`,
     * `rng_dispute_delay_events`,
     * `rng_chargeback_delay_events`.
   * `rng_usage_ok: boolean` indicating local envelope sanity.

7. **End**

   * `event_type: "6B.S4.LABELS.END"`
   * `manifest_fingerprint`, `seed`, `scenario_id`
   * `status`, `primary_error_code`, `secondary_error_codes`.

#### 10.3.2 Case scope logs (`S4_cases`)

For each `(manifest_fingerprint, seed)`:

1. **Start**

   * `event_type: "6B.S4.CASES.START"`
   * `manifest_fingerprint`, `seed`.

2. **Case input summary**

   * `event_type: "6B.S4.CASES.INPUT_SUMMARY"`
   * `flows_in_cases_total`, `case_count_total`.

3. **Case lifecycle summary**

   * `event_type: "6B.S4.CASES.LIFECYCLE_SUMMARY"`
   * `case_status_distribution` (final case statuses),
   * `avg_case_duration_seconds`, `p95_case_duration_seconds` (if computed).

4. **End**

   * `event_type: "6B.S4.CASES.END"`
   * `status`, `primary_error_code`, `secondary_error_codes`.

These logs MUST provide enough detail to understand:

* why S4 failed (if it did),
* how labels and cases are distributed,
* how much RNG was used.

---

### 10.4 Metrics & SLI/monitoring

S4 SHOULD expose metrics for operational monitoring. The **shape** is binding; thresholds and alerting policies are operational.

Indicative metrics:

* `6B_S4_label_runs_total`

  * Counter; labels: `status`, `scenario_id`.

* `6B_S4_flows_labeled_total`

  * Counter; labels: `truth_label` (and possibly `scenario_id`).

* `6B_S4_fraud_flows_total`

  * Counter; labels: `scenario_id`, `detected` (`"true"/"false"`).

* `6B_S4_detection_rate`

  * Gauge; labels: `scenario_id` (or tracked via `fraud_flow_count_truth` and `fraud_flow_detected_count`).

* `6B_S4_case_runs_total`

  * Counter; labels: `status`.

* `6B_S4_cases_total`

  * Counter; labels: `final_case_status`.

* `6B_S4_failure_primary_code_total`

  * Counter; label: `primary_error_code`.

* `6B_S4_label_runtime_seconds`

  * Histogram or summary; label: `status`.

Implementations MAY expose additional metrics (e.g. label distributions per merchant segment), but if they expose metrics with the names above, they MUST abide by the semantics described.

---

### 10.5 Downstream consumption of S4 observability

**S5 (6B validation/HashGate)** MUST:

* Use S4 run-report entries and logs as inputs to its validation logic:

  * If any `(manifest_fingerprint, seed, scenario_id)` has `S4_labels` `status="FAIL"`, or any `(manifest_fingerprint, seed)` has `S4_cases` `status="FAIL"`, S5 MUST treat the world as FAIL.
  * Even if S4 reports `status="PASS"`, S5 MUST still validate schema/coverage/consistency invariants against S4 outputs.

**4A/4B & model-training/evaluation pipelines** MUST:

* Gate consumption of labels on S5’s segment HashGate, **not** solely on S4’s status.
* MAY surface S4 label statistics (truth label distribution, detection rates, case counts) in diagnostic UIs or reports, but MUST clearly indicate that labels are valid only when S5 is PASS.

---

### 10.6 Traceability & audit trail

The combination of:

* S4 outputs (`s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`, `s4_event_labels_6B`, `s4_case_timeline_6B`),
* S3 overlays and S1/S2/6A context,
* S4 run-report entries and logs,

MUST allow an auditor or operator to answer, for any world/run/scenario:

* How many flows/events were truth-labelled as legit, fraud, or abuse?
* How often did the bank detect them? At what delay?
* How many cases were opened, with what outcomes and durations?
* Where and why did S4 fail (if it did)?
* Is RNG usage consistent with configured label/delay/case policies?

Because of this, emitting run-report entries, logs and core metrics as described in this section is **not optional** — it is part of 6B.S4’s binding contract.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on how to keep S4 practical and predictable at scale. It does **not** relax any of the binding constraints in §§1–10; it only suggests sensible implementation strategies that fit inside them.

---

### 11.1 Where S4 actually spends time

For a given `(manifest_fingerprint, seed, scenario_id)`, most of S4’s cost comes from:

1. **Reading S3 overlays and context**

   * One scan of:

     * `s3_flow_anchor_with_fraud_6B` (flow-level context),
     * `s3_event_stream_with_fraud_6B` (event-level context).
   * Optional joins to:

     * S2 baseline flows/events (for comparison),
     * 6A posture / S1 entity context (for priors).

2. **Flow-level truth & bank-view labelling**

   * For each flow:

     * apply deterministic truth rules,
     * apply bank-view rules (auth, detection, disputes, chargebacks),
     * occasionally draw RNG for ambiguous truth or stochastic delays.

3. **Event-level label assignment**

   * For each event:

     * derive truth event role and detection/case flags from:

       * flow-level labels,
       * S3 event overlay metadata,
       * bank-view decisions.

4. **Case construction**

   * Group a subset of flows into cases (usually much smaller than total flow count).
   * Build case timelines with typically handfuls of events per case.

Rough scaling, per `(seed, scenario_id)`:

```text
Time ~ O(#flows_S3 + #events_S3)  +  O(#cases)
Space ~ O(#flows_S3 + #cases)     +  small per-flow/per-case state
```

---

### 11.2 Parallelism & unit of work

S4 parallelises naturally along existing partition axes:

* **Across `(seed, scenario_id)`**

  * Flow/event labelling shots are independent:

    * each partition reads S3 overlays for that `(seed, scenario_id)`,
    * emits its own flow/event label tables.
  * This is the main axis of parallelism.

* **Across `seed` for cases**

  * Case-timeline construction is per `(seed, fingerprint)`.
  * Different seeds can be processed independently.

Within a partition:

* You can parallelise by **flow** (or `flow_id` shards) as long as:

  * each worker owns a disjoint set of flows,
  * RNG keying is deterministic per flow,
  * final outputs are merged via deterministic sort on `[flow_id]` / `[flow_id, event_seq]`.

Case-level work (grouping flows into cases) is more coupled:

* It’s often easier to run case construction in a single worker per `(seed, fingerprint)`, or at least shard on case keys that don’t overlap.

The rule: parallelise on **flows/cases**, not on arbitrary loop order, to preserve determinism.

---

### 11.3 Efficient use of S3 overlays & context

To keep S4 fast and memory-sane:

* **Index S3 flows once per partition**

  * Load `s3_flow_anchor_with_fraud_6B` into memory (or a stream with an index structure):

    * keyed by `flow_id`, with important overlay fields,
    * optionally index by campaign/type if truth policy uses them heavily.

* **Stream events as much as possible**

  * For `s3_event_stream_with_fraud_6B`:

    * avoid loading all events into a giant in-memory structure;
    * instead, process events grouped by `flow_id` (partitioning and ordering already enforce a natural grouping), and emit `s4_event_labels_6B` in a streaming manner.

* **Lightweight posture/context joins**

  * Pre-load 6A posture and any needed S1/S2 context into modest indices:

    * e.g. `account_id → fraud_role_account`,
    * `party_id → fraud_role_party`,
    * `flow_id → baseline summary` if S2 context is needed.

  * Join only the fields required by S4’s policies; avoid wide fan-out joins that pull in entire upstream row sets unnecessarily.

---

### 11.4 RNG cost & accounting

S4’s RNG usage is usually modest relative to data-plane costs:

* **Truth label ambiguity**:

  * Most flows will be deterministically classifiable (clear fraud patterns or clear legit).
  * RNG is used only when truth_labelling_policy marks a flow as ambiguous/collateral.

* **Detection/dispute/chargeback delays**:

  * Typically 1–few draws per flow for:

    * detection vs non-detection + detection delay,
    * dispute vs no-dispute + dispute delay,
    * chargeback vs no-chargeback + chargeback delay/outcome.

* **Case-timeline stochasticity** (if any):

  * Optionally a few draws per case for small timing jitter or choice between multiple allowed case sequences.

Rough heuristic:

```text
total RNG draws ~ O(#ambiguous_flows + #fraud_flows + #case_flows)
```

Guidance:

* **Keep per-decision budgets small and fixed**

  * e.g. one uniform to decide between 2–3 discrete outcomes,
  * one uniform to sample from a delay distribution (possibly via inversion/ICDF).

* **Avoid RNG-heavy modelling for marginal gain**

  * If a phenomenon can be modelled with deterministic rules + a small delay distribution, prefer that to many draws per flow.

* **Plan domain-dependent budgets explicitly**

  * `label_rng_policy_6B` should specify formulas like:

    * `draws_truth_ambiguity = #flows_ambiguous`,
    * `draws_detection_delay = #flows_requires_detection_sampling`, etc.

This keeps RNG envelope checks simple and makes S5’s accounting straightforward.

---

### 11.5 Memory footprint

S4’s memory needs per `(seed, scenario_id)` are largely:

* S3 flows (can fit in memory if partition sizes are reasonable).
* A few per-flow derived structures (truth label, bank-view state) until they’re written out.
* Event labels, which can be streamed.

Practical suggestions:

* **Flow-centric pipeline**

  * For each flow:

    1. gather required context (from flow anchor + posture + policy),
    2. compute truth + bank-view labels,
    3. optionally compute event-level roles by joining its S3 events on the fly,
    4. emit labels immediately.

  * This avoids storing large “all flows at once” structures.

* **Case construction layering**

  * Unless case policy is extremely complex, case construction can be done in two phases:

    1. During flow labelling, write out simple link hints (e.g. `case_key_candidate` per flow).
    2. Then run a separate case-timeline pass per `(seed, fingerprint)` that:

       * groups flows by `case_key_candidate`,
       * builds timelines and writes them as you go.

  * This keeps case-related memory usage proportional to number of flows in the current grouping, not the whole world.

---

### 11.6 I/O patterns

To keep I/O predictable and proportional:

* **One read, one write per partition**

  * For each `(seed, scenario_id)`:

    * read S3 overlays exactly once (plus any small context tables),
    * write S4 flow/event labels exactly once.

  * For `(seed, fingerprint)`:

    * read the minimal set of flow label summaries needed,
    * write S4 case timeline once.

* **Locality**

  * Storing S3 and S4 partitions in the same storage region/bucket reduces I/O latency.
  * Keeping S4 outputs in similar partition layouts to S3 (axes and ordering) simplifies readers and co-scans.

* **Avoid multiple full scans**

  * Don’t repeatedly re-scan `s3_event_stream_with_fraud_6B` for different purposes; design the pipeline so event-level labels are computed in one pass.

---

### 11.7 Sizing partitions & avoiding hotspots

S4 inherits partitioning from S3. If a given `(seed, scenario_id)` partition becomes very large:

* Flow/event counts can make S4 heavier, especially for:

  * per-flow detection/dispute/chargeback simulation,
  * event-level label assignment.

Mitigations (implemented upstream, not in S4 contract):

* Tuning S2/S3 partitioning (e.g. number of seeds, scenario design) to keep per-partition flow/event volumes within acceptable bounds.
* Avoiding scenarios that combine “world-wide everything” behaviour with extremely heavy overlay patterns unless intentionally stress testing.

Within S4, you can still:

* process flows in batches (e.g. per merchant or per range of flow_ids),
* but you MUST merge results deterministically into the final sorted tables.

---

### 11.8 Monitoring S4 performance

Operationally, you’ll want to monitor:

* **S4 runtimes** per `(seed, scenario_id)` and per `(seed, fingerprint)` for cases.

* **Label distributions**:

  * truth label & subtype distribution,
  * bank-view outcomes,
  * detection rates and chargeback rates.

* **Case metrics**:

  * number of cases per world/seed,
  * case duration distributions,
  * ratio of fraud vs non-fraud cases.

Red flags:

* runtime blowing up super-linearly with flow/event volume,
* sudden shifts in label distributions without corresponding config changes,
* high incidence of S4 failures with codes like `S4_LABEL_COVERAGE_MISMATCH`, `S4_TRUTH_CONSISTENCY_FAILED`, `S4_BANK_VIEW_CONSISTENCY_FAILED`, or RNG-related failures.

These are usually signs of:

* configuration drift,
* unexpected upstream behaviour, or
* bugs in the S4 implementation that need investigation.

---

### 11.9 Parallelism vs determinism

As with S1–S3:

> **Parallelism is allowed; non-determinism is not.**

Safe patterns:

* parallelising across independent `(seed, scenario_id)` partitions,
* sharding flows within a partition on a deterministic key (e.g. `flow_id` ranges), then merging with explicit sorting,
* sharding case construction by `case_key` with deterministic `case_id` derivation.

Unsafe patterns:

* branching RNG paths based on thread scheduling or hash-map iteration order,
* writing outputs from multiple workers without a deterministic merge/sort step,
* silently re-running S4 with changed configs under the same `parameter_hash` and treating differing outputs as acceptable.

A good litmus test:

* Run S4 twice on the same world/seed/scenario with the same configs and RNG policy; if the outputs are not logically identical, any performance tricks you’ve applied are violating this spec and need to be revised.

---

## 12. Change control & compatibility *(Binding)*

This section defines how the **6B.S4 contract may evolve over time**, and what changes are considered **backwards-compatible** vs **breaking**.

It is binding on:

* authors of future S4 specs,
* implementers of S4, and
* downstream consumers (S5, 4A/4B, model-training/evaluation).

The goals:

* Existing worlds/runs remain **replayable**.
* Consumers can safely rely on S4’s shapes, identity and invariants.

---

### 12.1 Versioning surfaces relevant to S4

S4 participates in the following version tracks:

1. **`spec_version_6B`**

   * Behavioural contract version for Segment 6B as a whole (S0–S5).
   * Recorded in `s0_gate_receipt_6B` and referenced by orchestrators and S5.

2. **Schema packs**

   * `schemas.6B.yaml`, containing S4 anchors:

     * `#/s4/flow_truth_labels_6B`
     * `#/s4/flow_bank_view_6B`
     * `#/s4/event_labels_6B`
     * `#/s4/case_timeline_6B`
   * `schemas.layer3.yaml`, containing Layer-3 RNG/gate/validation schemas.

3. **Catalogue artefacts**

   * `dataset_dictionary.layer3.6B.yaml` entries for:

     * `s4_flow_truth_labels_6B`
     * `s4_flow_bank_view_6B`
     * `s4_event_labels_6B`
     * `s4_case_timeline_6B`
   * `artefact_registry_6B.yaml` entries for the same.

**Binding rules:**

* For any S4 run, the tuple
  `(spec_version_6B, schemas.6B.yaml version, schemas.layer3.yaml version)`
  MUST be internally consistent and discoverable from catalogues.
* This specification describes S4’s contract for a particular `spec_version_6B` (e.g. `"1.0.0"`).
  Any **incompatible** change to S4’s contract MUST be accompanied by a **new major** `spec_version_6B` and corresponding schema/catalogue updates.

---

### 12.2 Backwards-compatible changes

A change to S4 is **backwards-compatible** if:

* Existing consumers (S5, 4A/4B, model-training/evaluation) built against this contract can still:

  * parse S4 datasets, and
  * rely on identity/partitioning and invariants in §§4–8 without modification.

Examples of **allowed** backwards-compatible changes:

1. **Additive, optional schema extensions**

   * Adding **optional** fields to `s4_flow_truth_labels_6B`:

     * e.g. additional diagnostics (`truth_confidence_score`, `is_collateral_flow_flag`).
   * Adding **optional** fields to `s4_flow_bank_view_6B`:

     * e.g. additional bank metrics (`risk_score_at_auth`, `manual_review_flag`).
   * Adding **optional** fields to `s4_event_labels_6B`:

     * e.g. per-event reasons or extra event-level diagnostics.
   * Adding **optional** fields to `s4_case_timeline_6B`:

     * e.g. `case_status_after_event`, `case_owner_queue`.

   Required fields and their semantics MUST remain unchanged.

2. **New label subtypes/outcomes with clear defaults**

   * Extending `truth_subtype` enum with new values (e.g. a new abuse subtype) while:

     * keeping existing values’ meaning unchanged,
     * allowing consumers to treat unknown subtypes as “OTHER” or ignore them.
   * Extending `bank_view_label` or `case_event_type` enums with new values that older consumers can safely ignore or bucket.

3. **More expressive label/delay/case policies**

   * Extending `truth_labelling_policy_6B`, `bank_view_policy_6B`, `delay_models_6B`, or `case_policy_6B` with new optional knobs that:

     * default to behaviour equivalent to this spec, and
     * do not change outputs when those knobs are unset.

4. **Internal implementation optimisations**

   * Changing internal data structures, sharding strategies, or minor algorithmic details while:

     * preserving determinism for fixed inputs (`manifest_fingerprint, parameter_hash, seed, scenario_id`), and
     * preserving all invariants in §§6–8 (coverage, consistency, RNG envelope).

Backwards-compatible changes MAY be rolled out as a **minor** `spec_version_6B` bump (e.g. `1.0.0 → 1.1.0`) if desired, but don’t require it as long as the contract defined here is preserved.

---

### 12.3 Breaking changes

A change is **breaking** for S4 if it can:

* cause existing consumers to misinterpret label surfaces,
* cause a replay of a world/run to produce **different labels** without an explicit config/version boundary, or
* violate the identity/coverage/consistency guarantees in §§4–8.

Breaking changes **MUST** be accompanied by a **new major** `spec_version_6B` and related schema/catalogue updates.

Examples of **breaking** changes:

1. **Identity / partitioning changes**

   * Changing partitioning for S4 datasets:

     * e.g. dropping `scenario_id` from flow/event labels, or changing case timeline partitioning off `[seed, manifest_fingerprint]`.
   * Changing primary keys:

     * e.g. removing `flow_id` from flow-label PKs,
     * changing `event_seq` semantics so it no longer uniquely identifies events within a flow,
     * changing `case_id` identity without a migration plan.

2. **Schema contract changes**

   * Removing or renaming any **required** field in S4 outputs:

     * e.g. `truth_label`, `truth_subtype`, `bank_view_label`, `detection_outcome`, `is_fraud_event_truth`, `case_event_type`.
   * Changing types of required fields in incompatible ways:

     * e.g. string→int or int→string, changing timestamp formats, etc.
   * Changing the semantics of core labels:

     * e.g. redefining `FRAUD` vs `ABUSE`, or what `BANK_CONFIRMED_FRAUD` means, without a new version and migration guidance.

3. **Relaxing coverage / consistency invariants**

   * Allowing flows in S3 overlays to **lack** labels in S4 (violating one-to-one coverage).
   * Allowing event labels to be absent or not match S3 events.
   * Dropping consistency requirements between truth labels, bank-view labels, case timelines and policies.

4. **RNG contract changes affecting reproducibility**

   * Changing which RNG families S4 uses or their budgets in a way that:

     * changes the number of RNG draws for a fixed domain,
     * invalidates existing RNG accounting logic in S5.

   * Altering keying schemes in a way that changes decisions for the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)` without a version/config bump.

5. **Changing label semantics without config/version boundary**

   * e.g. under the same `parameter_hash`/`spec_version_6B`:

     * mapping a given `fraud_pattern_type` from S3 to a different `truth_label`/`truth_subtype`,
     * changing detection/chargeback rates or delay shapes in ways that materially shift label distributions.

Any such change MUST:

* be documented under a new `spec_version_6B`,
* be encoded in updated `schemas.6B.yaml` and catalogues, and
* be accompanied by updated S5 & consumer specs explaining how to interpret the new labels.

---

### 12.4 Interaction with `parameter_hash` and reproducibility

S4 is required to be reproducible for fixed inputs, including `parameter_hash`:

> For fixed upstream inputs and fixed
> `(manifest_fingerprint, parameter_hash, seed, scenario_id)`,
> S4 outputs MUST be deterministic.

Implications:

* **Policy/config changes that affect labels** MUST be expressed as:

  * a new configuration pack → new `parameter_hash`, and/or
  * a new `spec_version_6B` if they change the S4 contract.

* It is **not acceptable** to:

  * silently change label/delay/case policies in place while keeping the same `parameter_hash` and `spec_version_6B`,
  * re-run S4 and accept that labels differ for the same world/run.

Operationally, idempotence is scoped to:

```text
(manifest_fingerprint, parameter_hash, seed, scenario_id)
```

and `(manifest_fingerprint, parameter_hash, seed)` for case timelines. If behaviour must change, it MUST be accompanied by a new `parameter_hash` and/or spec version, and S4 outputs regenerated accordingly.

---

### 12.5 Upstream dependency evolution

S4 depends on:

* S1 entity/session outputs,
* S2 baseline flows/events,
* S3 overlays & campaign catalogue,
* 6A posture surfaces,
* Layer-3 RNG environment.

**Binding rules for upstream changes:**

1. **Additive / compatible upstream changes**

   * Upstream segments MAY add optional fields to S1, S2, S3, or 6A surfaces.
   * S4 MAY start using those fields in labelling logic if:

     * they are treated as optional (no reliance on their presence), and
     * behaviour for fixed configs remains deterministic.

2. **Upstream breaking changes**

   * Changes to S3 identity (flow/event keys) or coverage invariants (e.g. dropping baseline flows in overlays) are breaking for S4.
   * Changes to S3’s `campaign_type` / `fraud_pattern_type` semantics that S4 relies on for truth mapping are breaking.
   * Changes to S2 identity that alter S3 or S4 join keys or to 6A posture semantics are breaking.

   In these cases, S4 MUST be updated and this spec (and `spec_version_6B`) MUST be revised, ideally in step with the upstream specs.

3. **New upstream label-relevant layers**

   * New label-adjacent layers (e.g. a “dynamic posture” layer or extra risk scores) can be adopted as **optional context** in S4 policy, provided they are not required for correctness.
   * If S4 correctness starts depending on new layers (e.g. S4 MUST read a new risk feature), this is a breaking change and MUST be versioned accordingly.

---

### 12.6 Co-existence & migration

To support rollouts and historical replay:

1. **Co-existence of S4 versions**

   * Orchestrators MUST choose a single `spec_version_6B` per deployment/world when invoking S4.
   * Different S4 implementations for different spec versions MUST NOT both write to the same dataset ids for the same `(manifest_fingerprint, seed, scenario_id)`.

   If side-by-side S4 contracts are needed:

   * use new dataset ids (e.g. `s4_flow_truth_labels_6B_v2`) or separate catalogue entries, and
   * document which consumers read which version.

2. **Reading old S4 outputs**

   * Newer tooling/S5 MAY read S4 outputs produced under older contracts, but MUST NOT assume they satisfy new invariants unless a migration layer is in place.
   * Any compatibility mapping from “old labels” to “new labels” MUST be clearly documented and implemented as a separate transform.

3. **Migration strategies**

   When introducing a new major S4 contract (new `spec_version_6B`):

   * Decide whether to re-run S4 for existing worlds with updated configs and contracts, or
   * Mark older worlds as using “legacy S4 vX” and handle them separately in consumption/training.

---

### 12.7 Non-negotiable stability points for S4

For the lifetime of this `spec_version_6B`, the following aspects of S4 are **stable** and MUST NOT change without a major version bump:

* S4 produces exactly four datasets:

  * `s4_flow_truth_labels_6B`
  * `s4_flow_bank_view_6B`
  * `s4_event_labels_6B`
  * `s4_case_timeline_6B`

* Partitioning and primary keys MUST remain as defined in §§4–7.

* **Flow coverage invariants:**

  * Every flow in `s3_flow_anchor_with_fraud_6B` has exactly one truth-label row and one bank-view row.
  * No labels exist for flows not in S3.

* **Event coverage invariants:**

  * Every event in `s3_event_stream_with_fraud_6B` has exactly one event-label row in S4.
  * No labels exist for events not in S3.

* **Case linkage invariants:**

  * Any flow marked as case-involved in `s4_flow_bank_view_6B` appears in `s4_case_timeline_6B` via one or more case events.
  * Case timelines follow the state machine and ordering rules defined in `case_policy_6B`.

* **Authority boundaries:**

  * S4 never mutates S1/S2/S3/6A data in place.
  * S4 remains the sole source of truth & bank-view labels; consumption layers MUST rely on S4 for labels, not re-derive them ad hoc.

Any future design that relaxes or modifies these stability points MUST:

* be treated as a breaking change,
* be guarded by a new major `spec_version_6B`, and
* arrive with updated S5/consumer specs and migration guidance.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects shorthand and symbols used in the 6B.S4 spec. It is **informative** only; if anything here conflicts with §§1–12, the binding sections win.

---

### 13.1 Identity & axes

* **`manifest_fingerprint` / `fingerprint`**
  Sealed world snapshot id. All S4 outputs are scoped to this.

* **`seed`**
  Stochastic run axis shared with 5B, 6A, S1–S3. S4 label outputs are partitioned by `seed` (and `scenario_id` for flows/events).

* **`scenario_id`**
  Scenario axis from 5A/5B (e.g. baseline vs stress). S4 flow/event labels are partitioned by `scenario_id`.

* **`parameter_hash`**
  Hash of the 6B behavioural/config pack (including S4 policies). For fixed `(manifest_fingerprint, parameter_hash, seed, scenario_id)`, S4 outputs MUST be deterministic.

* **`flow_id`**
  Flow/transaction identifier, unique within `(seed, manifest_fingerprint, scenario_id)` and inherited from S2/S3 overlays.

* **`event_seq`**
  Integer defining strict order of events within a `(seed, manifest_fingerprint, scenario_id, flow_id)` in S3/S4.

* **`case_id`**
  Case identifier, unique within `(seed, manifest_fingerprint)` in `s4_case_timeline_6B`.

* **`case_event_seq`**
  Integer defining strict order of events inside a `(seed, manifest_fingerprint, case_id)` in the case timeline.

---

### 13.2 Dataset shorthands

Upstream (for context):

* **`FA3`**
  `s3_flow_anchor_with_fraud_6B` — S3’s flow-level overlay.

* **`EV3`**
  `s3_event_stream_with_fraud_6B` — S3’s event-level overlay.

S4 outputs (informal names used in the spec):

* **`TL4`**
  `s4_flow_truth_labels_6B` — flow-level truth labels.

* **`BV4`**
  `s4_flow_bank_view_6B` — flow-level bank-view labels and lifecycle.

* **`EL4`**
  `s4_event_labels_6B` — event-level truth/bank-view flags keyed to EV3.

* **`CASE4`**
  `s4_case_timeline_6B` — case-level event timeline.

These are convenience names; canonical ids live in the dataset dictionary.

---

### 13.3 Label fields & enums (names indicative)

**Flow-level truth labels:**

* **`truth_label`**
  High-level category, e.g.:

  * `LEGIT` — non-fraud, non-abuse.
  * `FRAUD` — flows that are fraudulent.
  * `ABUSE` — flows that are abusive but not classic fraud (e.g. policy abuse).

* **`truth_subtype`**
  More detailed type, e.g.:

  * `CARD_TESTING`
  * `ACCOUNT_TAKEOVER` / `ATO`
  * `REFUND_ABUSE`
  * `MULE_ACTIVITY`
  * `FRIENDLY_FRAUD`
  * `NONE` (for purely legit flows, if used)

* **`label_policy_id`**
  Identifies the version of `truth_labelling_policy_6B` used.

* **`pattern_source`**
  Short descriptor of what drove the label, e.g.:

  * `CAMPAIGN` (direct from S3 campaign),
  * `COLLATERAL` (derived from a nearby fraud story),
  * `HEURISTIC_ONLY` (no explicit campaign, label assigned via heuristic).

**Flow-level bank-view labels:**

* **`bank_view_label`**
  Bank’s final classification, e.g.:

  * `BANK_CONFIRMED_FRAUD`
  * `BANK_CONFIRMED_LEGIT`
  * `NO_CASE_OPENED`
  * `CUSTOMER_DISPUTE_REJECTED`
  * `CHARGEBACK_WRITTEN_OFF`

* **`auth_decision`**
  Auth-time decision, e.g.:

  * `APPROVE`, `DECLINE`, `REVIEW`, `CHALLENGE`.

* **`detection_outcome`**
  High-level detection status, e.g.:

  * `DETECTED_AT_AUTH`
  * `DETECTED_POST_AUTH`
  * `NOT_DETECTED`

* **Lifecycle timestamps (nullable)**

  * `detection_ts_utc`
  * `dispute_ts_utc`
  * `chargeback_ts_utc`
  * `case_opened_ts_utc`
  * `case_closed_ts_utc`

**Event-level labels:**

* **`is_fraud_event_truth`**
  `true` if the event is part of the fraudulent/abusive behaviour according to truth.

* **`truth_event_role`**
  Event’s truth-level role, e.g.:

  * `PRIMARY_FRAUD_ACTION`
  * `SUPPORTING_EVENT`
  * `LEGIT_CONTEXT`
  * `DETECTION_ACTION`
  * `CASE_EVENT`
  * `NONE`

* **`is_detection_action`**
  `true` if the event represents the bank’s detection action (model/rule/manual review).

* **`is_case_event`**
  `true` if the event is part of the case lifecycle (if events are represented as such).

* **`bank_event_label`**
  Optional detailed bank-view label per event (e.g. `FLAGGED_SUSPICIOUS`, `CASE_NOTE`).

**Case timeline fields:**

* **`case_event_type`**
  E.g.:

  * `CASE_OPENED`
  * `DETECTION_ATTACHED`
  * `CUSTOMER_DISPUTE_RECEIVED`
  * `CHARGEBACK_FILED`
  * `CHARGEBACK_DECISION`
  * `CASE_CLOSED`

* **`case_event_ts_utc`**
  Timestamp of the case event.

---

### 13.4 RNG families (names indicative)

S4 uses Layer-3 Philox RNG via S4-specific families defined in `label_rng_policy_6B`. Names used in the spec (actual names live in the RNG contract):

* **`rng_event_truth_label_ambiguity`**
  Used when resolving ambiguous truth labels (e.g. collateral flows that could be `LEGIT` or `FRAUD`).

* **`rng_event_detection_delay`**
  Used for:

  * deciding detection vs non-detection where probabilistic,
  * sampling detection delay for detected flows.

* **`rng_event_dispute_delay`**
  Used to sample if/when a customer disputes a transaction.

* **`rng_event_chargeback_delay`**
  Used to sample if/when a chargeback is initiated, and possibly its outcome.

* **`rng_event_case_timeline`**
  Used for any remaining stochastic choices in case construction (e.g. case grouping or small jitter in case event timing), if policy uses randomness there.

All S4 RNG must go through these families; S4 MUST NOT use RNG families reserved for other states.

---

### 13.5 Error code prefix (S4)

All S4 error codes from §9 follow the prefix:

* **`S4_*`**

Examples (see §9 for full definitions):

* `S4_PRECONDITION_S0_S1_S2_S3_FAILED`
* `S4_PRECONDITION_SEALED_INPUTS_INCOMPLETE`
* `S4_PRECONDITION_LABEL_POLICY_INVALID`
* `S4_LABEL_SCHEMA_VIOLATION`
* `S4_LABEL_COVERAGE_MISMATCH`
* `S4_TRUTH_CONSISTENCY_FAILED`
* `S4_BANK_VIEW_CONSISTENCY_FAILED`
* `S4_CASE_TIMELINE_INCONSISTENT`
* `S4_RNG_EVENT_COUNT_MISMATCH`
* `S4_RNG_STREAM_MISCONFIGURED`
* `S4_OUTPUT_WRITE_FAILED`
* `S4_IDEMPOTENCE_VIOLATION`
* `S4_INTERNAL_ERROR`

These codes are part of S4’s external contract and are consumed by S5 and monitoring.

---

### 13.6 Miscellaneous shorthand

* **“truth label” / “truth”**
  The ground-truth classification of flows/events in the synthetic world, independent of bank decisions.

* **“bank-view label” / “bank-view”**
  The simulated classification and lifecycle from the bank’s perspective (what the bank thinks and does).

* **“case”**
  A multi-event object representing the bank’s investigation/dispute/chargeback process around one or more flows.

* **“partition” (S4 context)**
  Typically a `(seed, manifest_fingerprint, scenario_id)` slice for flow/event labels or `(seed, manifest_fingerprint)` for case timeline.

These symbols and abbreviations are provided purely for readability and do not introduce new obligations beyond what is already binding in §§1–12.

---
