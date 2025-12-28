# 6B.S3 — Fraud & abuse campaigns overlay (Layer-3 / Segment 6B)

## 1. Purpose & scope *(Binding)*

6B.S3 is the **fraud & abuse campaigns overlay** state for Segment 6B.

Given a sealed world `manifest_fingerprint` and a specific `(parameter_hash, seed, scenario_id)`:

* **S1** has already attached arrivals to entities and grouped them into sessions.
* **S2** has already built **baseline, all-legit flows and events**:

  * `s2_flow_anchor_baseline_6B` — one row per baseline flow/transaction.
  * `s2_event_stream_baseline_6B` — one row per baseline event in those flows.

S3’s job is to take those baseline flows/events and **overlay fraud and abuse campaigns** in a controlled, campaign-driven way, so that the final behaviour contains:

* realistic card testing, ATO, collusion and refund/chargeback abuse patterns,
* realistic “collateral” behaviour on related entities (mules, compromised devices/IPs, high-risk merchants),
* sufficient coverage and intensity to be useful for fraud modelling and rule evaluation.

S3 is the unique place in the engine where:

> baseline, legitimate flows are **corrupted or augmented** to become fraud/abuse stories, and those stories are tagged with explicit campaign metadata.

### In-scope responsibilities

Within that framing, S3 is responsible for:

* **Campaign realisation**

  * Reading 6B fraud/abuse campaign configurations (templates) that specify:

    * campaign types (e.g. card testing, account takeover, collusion, refund abuse),
    * target populations (segments of parties/accounts/merchants/devices/IPs, using 6A posture and attributes),
    * timing and duration (start/end windows, burst/slow-burn patterns),
    * intensity and tactics (e.g. number of tests per card, number of ATO login failures, refund multipliers).
  * For each template, instantiating zero or more **campaign instances** for the world/run, producing a concrete `campaign_id` and realised parameters.

* **Target selection**

  * Using baseline flows and 6A static posture to select **which entities and flows** are affected by each campaign instance, e.g.:

    * which parties/accounts/cards become compromised or used as mules,
    * which merchants/devices/IPs are used as attack surfaces,
    * which baseline flows/sessions/events are “captured” by each campaign.
  * All targets MUST be drawn from the sealed 6A + S2 universe; S3 does not invent new entities.

* **Flow & event overlay**

  * For flows/events targeted by campaigns, applying **overlay logic** that may:

    * change event sequences (e.g. repeated auths, fast retries, pattern changes in timing),
    * alter amounts or routing (e.g. small test amounts, cross-geo anomalies, route through risky merchants),
    * inject additional “dark” flows/events (e.g. pure card tests not obvious in the baseline).
  * Ensuring that all modifications are expressed as **overlay surfaces** that still reference the original baseline flow identity (`flow_id`, `event_seq` semantics) or clearly mark newly created flows as synthetic fraud-only flows.

* **Campaign tagging & fraud-pattern metadata**

  * Emitting a **campaign catalogue** describing all realised campaigns (`s3_campaign_catalogue_6B`), including:

    * `campaign_id`, `campaign_type`, configuration ids and resolved parameters,
    * target segment description and coverage statistics (entities/flows/events touched).
  * Tagging flows and events in overlay outputs (`s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`) with:

    * `campaign_id` (nullable),
    * `fraud_pattern_type` (e.g. `CARD_TESTING`, `ATO`, `REFUND_ABUSE`),
    * overlay flags (e.g. “amount_modified”, “routing_anomalous”, “device_swapped”),
    * optional severity/priority metrics per campaign.

S3 **does not** decide whether fraud is caught, charged back, or how the bank “sees” it; it only defines the *behavioural realisation* of fraud/abuse and the provenance (which campaign, which tactics).

### Out-of-scope responsibilities

S3 is explicitly **not** allowed to:

* **Modify upstream or baseline facts in-place**

  * It MUST NOT alter S1 outputs (`s1_arrival_entities_6B`, `s1_session_index_6B`).
  * It MUST NOT mutate S2 datasets (`s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`) in place.
  * Any changes to flows/events MUST be materialised as **S3 overlay outputs** that either:

    * reference baseline flows/events and describe overrides, or
    * produce separate “with_fraud” surfaces that are explicitly marked as such.

* **Introduce or change static entity posture**

  * It MUST NOT change 6A’s fraud roles or entity attributes (e.g. turning a normal party into a mule by editing 6A); instead, it may interpret those roles when targeting campaigns.
  * If S3 needs dynamic “fraud posture” (e.g. “currently compromised”), it MUST express this as overlay flags on flows/events or separate dynamic surfaces, not by rewriting 6A.

* **Assign final truth labels or bank-view outcomes**

  * It MUST NOT define final truth labels (e.g. `is_fraud_truth`, `truth_outcome`) or bank-view labels (e.g. `is_fraud_detected`, `chargeback_outcome`, `case_decision`); these are the responsibility of S4.
  * It MAY produce **candidate surfaces** (e.g. “this flow is fraud-like”) but those are interpreted by S4 and 6B validation, not treated as final labels.

* **Define segment-level validation or HashGate**

  * It does not create the 6B validation bundle or `_passed.flag`; that’s S5’s job.
  * It does not re-validate S0/S1/S2 gates; it trusts their receipts and sealed-inputs manifests.

### Relationship to other 6B states and the engine

Within Segment 6B:

* **Upstream:**

  * S0 has sealed the world and input universe.
  * S1 has attached arrivals to entities and sessions.
  * S2 has synthesised **baseline, all-legit** flows and event streams.

* **S3:**

  * Uses S2’s baseline flows/events and 6A static posture, plus 6B campaign configs, to **overlay fraud and abuse behaviour**.
  * Produces campaign-aware “with_fraud” flow and event surfaces, and a campaign catalogue.

* **Downstream:**

  * S4 will treat S3’s “with_fraud” flows and events as the **final behavioural story** to label with:

    * truth labels (fraud vs legit, abuse types),
    * bank-view labels (caught/not caught, disputes & chargebacks).
  * The 6B validation/HashGate state (S5) will verify that S3’s overlays honour campaign configs, static posture constraints, and RNG contracts, and that the resulting behaviour is structurally consistent with upstream layers.

If S3 is implemented according to this specification:

* The engine will have a **clear, reproducible mapping** from configuration-level fraud/abuse templates to concrete flows and events in the synthetic world.
* Downstream states (S4, S5, and the wider fraud platform) can reason precisely about **which flows came from which campaigns**, and assess detection performance and robustness against these structured attacks.

---

## 2. Preconditions & upstream gates *(Binding)*

This section defines **what must already be true** before 6B.S3 is allowed to run, and which upstream gates it **MUST** honour.

S3 is evaluated per triple:

```text
(manifest_fingerprint, seed, scenario_id)
```

If **any** precondition in this section is not satisfied for a given triple, then S3 **MUST NOT** overlay campaigns for that partition and **MUST** fail fast with a precondition error (defined in S3 failure modes).

---

### 2.1 6B.S0 gate MUST be PASS (world-level)

For a given `manifest_fingerprint`, S3 **MUST NOT** run unless 6B.S0 has successfully completed for that fingerprint.

Before any data-plane work, S3 MUST:

1. Locate `s0_gate_receipt_6B` for the target `manifest_fingerprint` using `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml`.
2. Validate it against `schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B`.
3. Confirm, via the Layer-3 run-report (or equivalent control-plane API), that 6B.S0 is recorded as `status="PASS"` for this `manifest_fingerprint`.

If:

* the receipt is missing,
* fails schema validation, or
* the run-report does not show S0 `status="PASS"`,

then S3 **MUST** treat this as a hard precondition failure and MUST NOT read any S1/S2 outputs or upstream data-plane tables for that world.

S3 is **not** allowed to reconstruct or bypass S0’s sealed-inputs universe.

---

### 2.2 Upstream HashGates: transitive requirement

S0 has already checked the HashGates for required upstream segments:

* Layer-1: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
* Layer-2: `5A`, `5B`
* Layer-3: `6A`

S3 does **not** re-verify these bundles, but it **MUST** respect their recorded status in `s0_gate_receipt_6B.upstream_segments`:

* For each `SEG ∈ { "1A","1B","2A","2B","3A","3B","5A","5B","6A" }`, S3 MUST check:

  ```text
  s0_gate_receipt_6B.upstream_segments[SEG].status == "PASS"
  ```

* If **any** required upstream segment has `status != "PASS"`, S3 MUST fail with a precondition error and MUST NOT attempt campaign realisation or overlay for that world.

S3 MUST NOT try to “work around” a non-PASS upstream segment. If S0 says the world isn’t sealed, S3 isn’t allowed to run.

---

### 2.3 S1 and S2 MUST be PASS for `(seed, scenario_id)`

S3’s overlay logic sits on top of S1 and S2. For each `(manifest_fingerprint, seed, scenario_id)`:

* S3 MUST NOT run unless **both** 6B.S1 and 6B.S2 have successfully completed for that same triple.

Binding checks:

1. Inspect the Layer-3 run-report for entries:

   ```text
   segment = "6B", state = "S1"
   segment = "6B", state = "S2"
   ```

   with matching `manifest_fingerprint`, `seed`, `scenario_id`, and `status = "PASS"` for both S1 and S2.

2. Confirm that S1/S2 data-plane outputs exist and are schema-valid for that partition:

   * `s1_arrival_entities_6B@{seed,fingerprint,scenario_id}`
   * `s1_session_index_6B@{seed,fingerprint,scenario_id}`
   * `s2_flow_anchor_baseline_6B@{seed,fingerprint,scenario_id}`
   * `s2_event_stream_baseline_6B@{seed,fingerprint,scenario_id}`

   validated against their `schema_ref`s in `schemas.6B.yaml`.

If S1 or S2 is `status="FAIL"` or missing for the partition, or any required S1/S2 dataset is missing or schema-invalid, S3 MUST treat this as a precondition failure and MUST NOT attempt any overlay for that `(seed, scenario_id)`.

S3 MUST NOT bypass S1/S2 to overlay directly on 5B arrivals or 6A entities.

---

### 2.4 Required sealed-inputs entries for S3

All datasets and config packs S3 reads MUST be discoverable via `sealed_inputs_6B` for the target `manifest_fingerprint`.

Before processing any `(seed, scenario_id)` partition, S3 MUST:

1. Load `sealed_inputs_6B@{fingerprint}` and validate it against `schemas.layer3.yaml#/gate/6B/sealed_inputs_6B`.

2. Confirm that the following artefacts exist as rows with:

   * `status = "REQUIRED"`
   * `read_scope = "ROW_LEVEL"` (unless otherwise stated)

   **Required 6B data-plane surfaces**

   * `owner_layer = 3`, `owner_segment = "6B"`, `manifest_key = "s1_arrival_entities_6B"`
   * `owner_layer = 3`, `owner_segment = "6B"`, `manifest_key = "s1_session_index_6B"`
   * `owner_layer = 3`, `owner_segment = "6B"`, `manifest_key = "s2_flow_anchor_baseline_6B"`
   * `owner_layer = 3`, `owner_segment = "6B"`, `manifest_key = "s2_event_stream_baseline_6B"`

   **Required 6A fraud posture surfaces**

   At minimum:

   * `s5_party_fraud_roles_6A`
   * `s5_account_fraud_roles_6A`
   * `s5_merchant_fraud_roles_6A` (if used by S3’s policy)
   * `s5_device_fraud_roles_6A`
   * `s5_ip_fraud_roles_6A`

   These MUST be present with `read_scope="ROW_LEVEL"` if S3’s policies require row-level targeting; if some surfaces are only used for metadata checks, they MAY be `METADATA_ONLY` but still `status="REQUIRED"`.

   **Required fraud & abuse configuration packs (6B)**

   Names are indicative and must match your contract files; each MUST be present with `status="REQUIRED"` and a valid `schema_ref`:

   * `fraud_campaign_catalogue_config_6B`

     * Templates for campaign types, segment definitions, intensity, and scheduling.
   * `fraud_overlay_policy_6B`

     * Rules for how campaigns mutate flows/events (tactics, allowed anomalies).
   * `fraud_rng_policy_6B`

     * RNG family and budget configuration for S3 (e.g. `rng_event_campaign_activation`, `rng_event_campaign_targeting`, `rng_event_overlay_mutation`).

3. For each required row, S3 MUST verify:

   * `schema_ref` resolves into `schemas.6B.yaml` or `schemas.layer3.yaml` as appropriate.
   * `partition_keys` and `path_template` are consistent with the owning dictionary/registry.

If **any** required row is missing or malformed, S3 MUST fail with a precondition error and MUST NOT read data-plane rows or perform overlay for that world.

Optional context artefacts (e.g. additional 6A attributes, 5A/5B/2B/3B context surfaces) MAY appear with `status="OPTIONAL"` and any appropriate `read_scope`; their presence is *not* a precondition for S3 to run.

---

### 2.5 Partition coverage alignment with S2

S3 operates on the same `(seed, scenario_id)` partitions as S2 for a given world.

For each `(manifest_fingerprint, seed, scenario_id)` that S3 intends to process, it MUST:

1. Confirm that:

   * `s2_flow_anchor_baseline_6B` has a partition at:

     ```text
     seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}
     ```

   * `s2_event_stream_baseline_6B` has a partition at the same axes.

2. Confirm that S1 outputs exist for the same axes (as per §2.3), since S3 may need them for entity/session context during targeting.

If S2 has **no flows** in a partition (legitimate case, e.g. no transactional behaviour), S3 MAY:

* treat that partition as trivially PASS for overlay (no campaigns applied), and
* either emit empty S3 overlays for that partition or emit no S3 data for that partition but still record S3 `status="PASS"` with zero counts.

The chosen convention MUST be documented in the detailed S3 spec and applied consistently.

S3 MUST NOT attempt to run on a `(seed, scenario_id)` where S2 has not produced outputs.

---

### 2.6 Layer-3 RNG & numeric environment for S3

S3 is an RNG-consuming state. Before any campaign or overlay logic, S3 MUST ensure that:

* The Layer-3 Philox RNG configuration exists and is valid (event envelope, counters, numeric policy) as per `schemas.layer3.yaml` and the Layer-3 RNG policy artefacts.
* The S3-specific RNG policy (`fraud_rng_policy_6B` or equivalent) is present in `sealed_inputs_6B` and schema-valid, including:

  * The RNG family names reserved for S3 (e.g. `rng_event_campaign_activation`, `rng_event_campaign_targeting`, `rng_event_overlay_mutation`).
  * Per-family budgets (`blocks`, `draws` per event).
  * Any substream keying law (e.g. keyed on `(seed, fingerprint, scenario_id, campaign_id, flow_id)`).

If the RNG policy for S3 is missing, inconsistent with the Layer-3 RNG spec, or otherwise invalid, S3 MUST fail preconditions and MUST NOT attempt to realise campaigns or mutate flows.

---

### 2.7 Prohibited partial / speculative invocations

S3 MUST NOT be invoked in any of the following situations:

* **Before** 6B.S0 has been run and recorded `status="PASS"` for the target `manifest_fingerprint`.
* **Before** 6B.S1 and 6B.S2 have been run and recorded `status="PASS"` for the target `(manifest_fingerprint, seed, scenario_id)`.
* With a manually supplied list of inputs that bypasses `sealed_inputs_6B`.
* Against a world where any required upstream HashGate (1A–3B, 5A, 5B, 6A) is not PASS according to `s0_gate_receipt_6B`.
* When required S1/S2 surfaces, 6A static posture surfaces, or S3 config packs are missing from `sealed_inputs_6B` or fail their schemas.
* In any “best-effort” or “partial overlay” mode that permits execution when the above preconditions are not satisfied.

If any of these conditions hold, the correct behaviour is:

* S3 MUST fail early with a precondition error for that `(manifest_fingerprint, seed, scenario_id)`.
* S3 MUST NOT emit any S3 outputs for that partition.

These preconditions are **binding**. Any conformant implementation of 6B.S3 MUST enforce them before performing campaign activation, targeting, or overlay on the baseline flows/events.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **exactly what 6B.S3 may read** and what each input is the **authority for**. Anything outside these boundaries is out of scope for S3 and **MUST NOT** be touched.

S3 is a **data-plane + RNG-consuming** state: it reads rows from its authorised inputs, uses 6B fraud/abuse policies to overlay campaigns, and writes its own overlay plan surfaces. It MUST NOT mutate any upstream or S1/S2 datasets.

---

### 3.1 Engine parameters (implicit inputs)

S3 is evaluated over:

* `manifest_fingerprint` — sealed world snapshot.
* `seed` — run axis (shared with 5B, 6A, S1, S2).
* `scenario_id` — arrival scenario (from 5A/5B).
* `parameter_hash` — 6B behavioural config pack identifier (shared across S0–S4).

These are supplied by orchestration and/or discovered via `sealed_inputs_6B` and the catalogues. S3 **MUST NOT** derive or change them from wall-clock or environment.

---

### 3.2 6B control-plane inputs (S0 outputs)

S3 depends on S0 control-plane surfaces as its **authority on what world and contracts it is running under**:

1. **`s0_gate_receipt_6B`**
   Authority for:

   * the set of upstream segments and their PASS/MISSING/FAIL status,
   * the `parameter_hash` and `spec_version_6B` in force,
   * the `sealed_inputs_digest_6B` summarising the input universe.

   S3 MUST:

   * confirm it is running against the intended `manifest_fingerprint`,
   * respect upstream segment statuses (see §2),
   * treat the recorded `parameter_hash` / `spec_version_6B` as binding.

2. **`sealed_inputs_6B`**
   Authority for:

   * which artefacts S3 is allowed to read,
   * their `path_template` and `partition_keys`,
   * their `schema_ref`, `role`, `status`, `read_scope`, and `sha256_hex`.

   S3 MUST:

   * resolve all dataset locations via `sealed_inputs_6B` + the owning segment’s dictionary/registry,
   * NEVER construct dataset paths by hand,
   * NEVER read artefacts not listed in `sealed_inputs_6B`,
   * respect `status` and `read_scope` (e.g. no row-level reads from `METADATA_ONLY` artefacts).

---

### 3.3 Baseline behaviour inputs (primary data-plane inputs)

S3’s **main data-plane inputs** are the baseline S1/S2 surfaces. They are authoritative for:

* who is acting, and
* how baseline flows behave when nothing fraudulent is happening.

These MUST appear in `sealed_inputs_6B` as `owner_layer=3`, `owner_segment="6B"`, `status="REQUIRED"`, `read_scope="ROW_LEVEL"`:

1. **`s1_arrival_entities_6B`**

   * One row per arrival for `(seed, manifest_fingerprint, scenario_id)`.
   * Contains:

     * arrival identity & routing (from 5B),
     * entity attachments (`party_id`, `account_id`, `instrument_id?`, `device_id`, `ip_id`),
     * `session_id`.

   **Authority for S3:**

   * which entity owns which arrival,
   * which arrivals belong to which `session_id`.

   S3 MUST NOT:

   * change attachments or `session_id`,
   * drop or invent arrivals.

2. **`s1_session_index_6B`**

   * One row per session.
   * Contains time window, counts, and optional entity/session-level context.

   **Authority for S3:**

   * which sessions exist,
   * session time windows and coarse behaviour context.

   S3 MAY use session-level information for campaign targeting (e.g. high-velocity sessions), but MUST NOT change session identity or boundaries.

3. **`s2_flow_anchor_baseline_6B`**

   * One row per baseline flow.
   * Contains flow identity (`flow_id`), link to session/arrivals, entity context, baseline amounts, timestamps, and baseline outcomes.

   **Authority for S3:**

   * the set of baseline flows to potentially target or leave untouched,
   * each flow’s legitimate structure and outcome.

4. **`s2_event_stream_baseline_6B`**

   * One row per baseline event.
   * Contains `event_type`, `event_ts_utc`, flow/event keys, entity & routing context.

   **Authority for S3:**

   * the baseline event sequence per flow (what “normal” looks like),
   * event-level timing and routing details S3 will distort.

Binding rules:

* S3 MUST treat these four datasets as **read-only baseline facts**.
* S3 MUST NOT edit or overwrite them; any overlay is expressed only in S3’s own outputs.

---

### 3.4 Static entity & posture inputs (Layer-3 / 6A)

S3 uses 6A static entity and posture surfaces to decide **who is a plausible target** for fraud/abuse. These MUST appear in `sealed_inputs_6B` with `owner_layer=3`, `owner_segment="6A"`, appropriate `status` and `read_scope` (often `ROW_LEVEL`):

1. **6A base tables (optional but strongly recommended for targeting):**

   * `s1_party_base_6A`
   * `s2_account_base_6A`
   * `s3_instrument_base_6A`
   * `s4_device_base_6A`
   * `s4_ip_base_6A`

   **Authority:** entity existence and static attributes (type, geography, segments, etc.). S3 MAY use them to drive richer target selection (e.g. “high-risk merchant segment”).

2. **6A fraud posture surfaces (required):**

   * `s5_party_fraud_roles_6A`
   * `s5_account_fraud_roles_6A`
   * `s5_merchant_fraud_roles_6A` (if used in policy),
   * `s5_device_fraud_roles_6A`
   * `s5_ip_fraud_roles_6A`

   **Authority:** static fraud roles (e.g. mule, synthetic, risky merchant, tainted device/IP). S3 MUST treat these as **read-only** and MUST NOT change them.

S3 MAY derive dynamic overlay flags (e.g. “currently compromised account”) in its own outputs, but MUST NOT change the static fraud roles in 6A.

---

### 3.5 Fraud & abuse configuration inputs (Layer-3 / 6B)

S3’s behaviour is driven by 6B-local configuration and policy packs. These MUST be:

* registered in the 6B dictionary/registry,
* listed in `sealed_inputs_6B` with appropriate `role`, `status`, `read_scope`,
* schema-validated before use.

Indicative set (names to match your contracts):

1. **Campaign catalogue config** (e.g. `fraud_campaign_catalogue_config_6B`)

   Role: `campaign_config`.
   Authority for:

   * campaign types (card testing, ATO, collusion, refund abuse, etc.),
   * per-type parameters (batch sizes, attack strategies, distributions),
   * segment/filter definitions over entities/flows/sessions,
   * scheduling rules (start/end windows, frequency).

2. **Overlay policy pack** (e.g. `fraud_overlay_policy_6B`)

   Role: `overlay_policy`.
   Authority for:

   * how each campaign type **mutates** baseline flows/events:

     * which event types to add/remove/change,
     * how to skew timings (e.g. compress into bursts),
     * how to adjust amounts and routing,
   * constraints so that overlay behaviour remains realistic and internally consistent.

3. **RNG policy pack for S3** (e.g. `fraud_rng_policy_6B`)

   Role: `rng_policy`.
   Authority for:

   * RNG families reserved for S3 (`rng_event_campaign_activation`, `rng_event_campaign_targeting`, `rng_event_overlay_mutation`, etc.),
   * per-family `blocks`/`draws` budgets per decision,
   * key structure (how `(manifest_fingerprint, seed, scenario_id, campaign_id, flow_id, event_seq)` feed into keys).

4. **Optional validation/tuning packs**

   Role: `validation_policy` / `tuning`.
   Authority for:

   * target fraud rates per segment,
   * expected intensity (e.g. card tests per card, ATO attempts per account),
   * campaign sanity bounds that S5 will later validate.

Binding rules for config:

* S3 MUST read these packs via `sealed_inputs_6B` and their `schema_ref`s.
* S3 MUST NOT embed behaviour outside these packs; all stochastic campaign/overlay decisions must be parameterised by them.
* If a pack is `status="REQUIRED"` and missing/invalid, S3 MUST fail preconditions (see §2).

---

### 3.6 Optional context inputs (METADATA or enrichment only)

Depending on the 6B spec version, S3 MAY also use optional context artefacts for **enrichment** or validation, for example:

* Additional 6A attributes (e.g. more detailed segmentation) to refine target selection.
* 5A/5B context (e.g. intensity surfaces, bucket counts) for time-of-day/seasonality patterns in campaigns.
* 2B/3B routing context (e.g. edge_catalogue, routing_universe hashes) for network-style attacks.

These MUST:

* be listed in `sealed_inputs_6B` with `status="OPTIONAL"` and appropriate `read_scope`,
* be treated as **non-authoritative** for entity identity, posture, arrivals, or baseline flows,
* only influence S3’s choice of *where* and *how* to overlay fraud, not **what the underlying world is**.

If an optional context artefact is missing, S3 MUST degrade gracefully (e.g. fall back to simpler targeting) rather than failing the partition.

---

### 3.7 Authority boundaries & prohibitions

To make the boundaries explicit:

* **Authority for arrivals, attachments & sessions**

  * `s1_arrival_entities_6B` and `s1_session_index_6B` remain the sole authority for:

    * which arrivals exist,
    * which entities they are attached to,
    * which `session_id` they belong to.
  * S3 MUST NOT modify these; it may read them for targeting context only.

* **Authority for baseline flows & events**

  * `s2_flow_anchor_baseline_6B` and `s2_event_stream_baseline_6B` are the **only authority** on baseline behaviour.
  * S3 MUST NOT edit them in place; instead, it writes its own “with_fraud” surfaces. Baseline data remains available for comparison and validation.

* **Authority for static entities & posture**

  * 6A base + posture tables remain the only authority on entity existence and static roles.
  * S3 MUST NOT create new entities or change their static fraud roles.

* **Authority for what S3 may read**

  * `sealed_inputs_6B` is the exclusive input inventory.
  * S3 MUST NOT:

    * read artefacts not present in `sealed_inputs_6B`,
    * ignore `status` and `read_scope` constraints.

* **Authority for S3 overlay behaviour**

  * 6B campaign, overlay, RNG and validation policy packs are the only authority for S3’s overlay logic.
  * S3 MUST NOT change gating/HashGate semantics; it only generates overlay surfaces that S5 will later validate.

Any attempt by S3 to:

* bypass `sealed_inputs_6B`,
* mutate S1/S2/6A/5B/Layer-1 data,
* introduce new identity axes or static posture,
* or invent entities outside 6A,

is out of spec and MUST be treated as a violation of this state’s binding contract.

---

## 4. Outputs (datasets) & identity *(Binding)*

6B.S3 produces three **overlay plan surfaces**:

1. `s3_campaign_catalogue_6B` — catalogue of **realised campaign instances**.
2. `s3_flow_anchor_with_fraud_6B` — **flow-level** view after overlay (baseline + fraud/abuse overlay).
3. `s3_event_stream_with_fraud_6B` — **event-level** view after overlay.

These are **Layer-3 / 6B owned** datasets:

* They **do not** replace S1/S2 outputs; they sit alongside them as overlay surfaces.
* They are required for S4 (labelling) and S5 (validation).
* Flow/event overlays share the same partition axes as S2: `[seed, fingerprint, scenario_id]`.

No other datasets may be written by S3.

---

### 4.1 `s3_campaign_catalogue_6B` — realised campaigns

**Dataset id**

* `id: s3_campaign_catalogue_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

One row per **realised campaign instance**, describing:

* `campaign_id` — unique identifier for the campaign instance within `(seed, manifest_fingerprint)` (see identity below).
* `campaign_type` — e.g. `CARD_TESTING`, `ATO`, `REFUND_ABUSE`, `COLLUSION`, etc.
* configuration references:

  * source template id from `fraud_campaign_catalogue_config_6B`,
  * parameters resolved for this instance (e.g. target rates, burstiness).
* targeting description:

  * high-level segment being targeted (e.g. “EU e-com mules”, “high-risk MCCs”),
  * indicates whether targeting is entity-centric (parties/accounts/devices/merchants), flow-centric, or session-centric.
* scope:

  * world axes: `manifest_fingerprint`, `seed`,
  * scenario scope (single `scenario_id` or a set, depending on policy),
  * calendar/timeline: start/end windows.
* realised intensity:

  * number of entities/flows/sessions/events touched.

This catalogue is the **only authoritative list** of which campaigns S3 actually realised and the parameters they used. All `campaign_id` references in S3 overlays MUST be traceable to this table.

**Format, path & partitioning**

Campaigns are realised per seed+world (even if they span multiple scenarios). The dataset MUST be registered with:

* `version: '{seed}.{manifest_fingerprint}'`

* `format: parquet`

* `path` (template):

  ```text
  data/layer3/6B/s3_campaign_catalogue_6B/
      seed={seed}/fingerprint={manifest_fingerprint}/s3_campaign_catalogue_6B.parquet
  ```

* `partitioning: [seed, fingerprint]`

The `manifest_fingerprint` and `seed` columns in all rows MUST match the partition tokens.

**Primary key & identity**

For each `(seed, manifest_fingerprint)`:

* Primary key (binding):

  ```text
  [seed, manifest_fingerprint, campaign_id]
  ```

`campaign_id` MUST be unique within `(seed, manifest_fingerprint)`.

**Schema anchor & lineage**

* Schema anchor (to be defined in §5):

  ```text
  schemas.6B.yaml#/s3/campaign_catalogue_6B
  ```

* Dictionary:

  * `status: required`
  * `produced_by: [ '6B.S3' ]`
  * `consumed_by: [ '6B.S4', '6B.S5' ]`

* Registry:

  * `manifest_key: s3_campaign_catalogue_6B`
  * `type: dataset`
  * `category: plan`
  * `final_in_layer: false`

---

### 4.2 `s3_flow_anchor_with_fraud_6B` — flows with overlay

**Dataset id**

* `id: s3_flow_anchor_with_fraud_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

Flow-level overlay view for each `(seed, manifest_fingerprint, scenario_id)` domain. Each row represents:

* a **flow after overlay**, with:

  * all baseline anchor fields from `s2_flow_anchor_baseline_6B` (flow identity, entity context, baseline timestamps/amounts/outcomes), plus
  * overlay-specific fields:

    * `origin_flow_id` (link to baseline flow if applicable),
    * `origin_type` (e.g. `BASELINE_FLOW`, `PURE_FRAUD_FLOW`),
    * `campaign_id` (nullable; FK into `s3_campaign_catalogue_6B`),
    * `fraud_pattern_type` (e.g. `CARD_TESTING`, `ATO`, `REFUND_ABUSE`, `NONE`),
    * overlay flags (e.g. `amount_modified_flag`, `routing_anomalous_flag`, `extra_auths_flag`),
    * any aggregate metrics derived from overlay (e.g. number of modified events).

There MUST be exactly one row per **post-overlay flow**. That includes:

* flows that are essentially unchanged from baseline (fraud_pattern_type = `NONE`), and
* flows that are new or heavily mutated by campaigns.

**Format, path & partitioning**

This dataset MUST be registered with:

* `version: '{seed}.{manifest_fingerprint}.{scenario_id}'`

* `format: parquet`

* `path` (template):

  ```text
  data/layer3/6B/s3_flow_anchor_with_fraud_6B/
      seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `partitioning: [seed, fingerprint, scenario_id]`

Columns `seed`, `manifest_fingerprint`, `scenario_id` MUST match the partition tokens.

**Primary key & identity**

S3 overlays flows per partition:

* Primary key (binding):

  ```text
  [seed, manifest_fingerprint, scenario_id, flow_id]
  ```

where:

* For flows derived from baseline:

  * `flow_id` MUST equal the baseline `flow_id` from `s2_flow_anchor_baseline_6B` in the same partition, and
  * `origin_flow_id` MUST also be set to that baseline `flow_id`.

* For “pure fraud” flows created by S3:

  * `flow_id` MUST be a new identifier unique within `(seed, manifest_fingerprint, scenario_id)` that does **not** clash with any baseline `flow_id`, and
  * `origin_type` MUST indicate `PURE_FRAUD_FLOW`, with `origin_flow_id` either null or pointing to a related baseline flow if the campaign semantics require that link.

Ordering MUST be:

```text
[seed, manifest_fingerprint, scenario_id, flow_id]
```

**Schema anchor & lineage**

* Schema anchor:

  ```text
  schemas.6B.yaml#/s3/flow_anchor_with_fraud_6B
  ```

* Dictionary:

  * `status: required`
  * `produced_by: [ '6B.S3' ]`
  * `consumed_by: [ '6B.S4', '6B.S5' ]`

* Registry:

  * `manifest_key: s3_flow_anchor_with_fraud_6B`
  * `type: dataset`
  * `category: plan`
  * `final_in_layer: false`

---

### 4.3 `s3_event_stream_with_fraud_6B` — events with overlay

**Dataset id**

* `id: s3_event_stream_with_fraud_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

Event-level overlay view for each `(seed, manifest_fingerprint, scenario_id)`. Each row represents a **post-overlay event** in a flow:

* For flows derived from baseline:

  * some events may be unchanged, some mutated (e.g. timing/amount changes), some inserted/removed.
  * S3 event rows MUST carry enough information to trace back to baseline events (e.g. `origin_flow_id`, `origin_event_seq` where applicable).

* For pure fraud flows:

  * events are wholly synthetic but must still obey identity, timing, routing and entity constraints.

Each row includes:

* identity axes: `manifest_fingerprint`, `seed`, `scenario_id`, `flow_id`, `event_seq`,
* event type and timestamp,
* entity context, routing context,
* overlay metadata:

  * `campaign_id` (nullable),
  * `fraud_pattern_type`,
  * per-event flags (e.g. `is_fraud_event`, `amount_modified_flag`, `device_swapped_flag`),
  * optional `origin_flow_id`, `origin_event_seq` for linking back to baseline.

**Format, path & partitioning**

MUST be registered with:

* `version: '{seed}.{manifest_fingerprint}.{scenario_id}'`

* `format: parquet`

* `path` (template):

  ```text
  data/layer3/6B/s3_event_stream_with_fraud_6B/
      seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `partitioning: [seed, fingerprint, scenario_id]`

Axes in each row MUST match the partition tokens.

**Primary key & identity**

For each `(seed, manifest_fingerprint, scenario_id)`:

* Primary key (binding):

  ```text
  [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
  ```

Constraints:

* For any given `(seed, fingerprint, scenario_id, flow_id)`:

  * `event_seq` MUST form a contiguous, strictly monotone sequence starting at a base defined in the schema (e.g. 0 or 1).
  * Every `flow_id` present in `s3_flow_anchor_with_fraud_6B` MUST have ≥1 event in this table.
  * No events may appear for `flow_id`s that are absent from the overlay flow anchor.

Ordering MUST be:

```text
[seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
```

**Schema anchor & lineage**

* Schema anchor:

  ```text
  schemas.6B.yaml#/s3/event_stream_with_fraud_6B
  ```

* Dictionary:

  * `status: required`
  * `produced_by: [ '6B.S3' ]`
  * `consumed_by: [ '6B.S4', '6B.S5' ]`

* Registry:

  * `manifest_key: s3_event_stream_with_fraud_6B`
  * `type: dataset`
  * `category: plan`
  * `final_in_layer: false`

---

### 4.4 Relationship to S2 outputs & identity consistency

To avoid ambiguity:

* **Axes alignment**

  * For flows and events, S3 uses the **same axes** as S2:

    ```text
    (seed, manifest_fingerprint, scenario_id)
    ```

  * For the campaign catalogue, axes are `(seed, manifest_fingerprint)`.

* **Baseline vs overlay**

  * For flows that originate from baseline:

    * `flow_id` in S3 MUST match `flow_id` in S2 for the same `(seed, fingerprint, scenario_id)`.
    * `origin_flow_id` MUST explicitly reference the baseline `flow_id`.
    * S3 may change per-flow amounts/timestamps/flags **in its own overlay anchor**, but S2’s anchor remains unchanged.

  * For purely synthetic fraud flows:

    * `flow_id` is new, unique in S3, and does not appear in S2.
    * `origin_type` or similar MUST indicate that the flow is “pure fraud”; `origin_flow_id` is null or set according to overlay semantics.

* **Events linkage**

  * Every `(seed, fingerprint, scenario_id, flow_id)` in S3 events MUST exist in S3 flow anchor.

  * For events derived from S2:

    * `origin_flow_id` and `origin_event_seq` (or equivalent) MUST allow traceability back to a baseline event when policy demands it.

  * For newly spawned events (pure fraud or extra overlay steps):

    * origin fields may be null or set to a sensible reference (e.g. the baseline event they attach to), as defined in the S3 schema.

* **Campaign linkage**

  * All non-null `campaign_id` values in S3 flow/event overlays MUST exist in `s3_campaign_catalogue_6B@{seed,fingerprint}`.
  * For flows/events with `campaign_id = null`, `fraud_pattern_type` MUST be either `NONE` or a value consistent with “no campaign” as defined in S3’s schema.

These relationships will be enforced by S3’s own acceptance criteria and by the 6B validation state. This section fixes the **identity and dataset surfaces**; subsequent sections describe how S3 populates and checks them.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

All binding schema anchors, dataset IDs, partitioning rules, and manifest keys for this state's egress live in the Layer-3 / Segment 6B contracts:
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/schemas.layer3.yaml`

This specification only summarises semantics so there is a single source of truth for catalogue details. Always consult the files above for precise schema refs, physical paths, partition keys, writer ordering, lifecycle flags, and dependency metadata.

### 5.1 Outputs owned by this state
- `s3_campaign_catalogue_6B` — Reference catalogue describing the fraud campaign patterns injected in S3.
- `s3_flow_anchor_with_fraud_6B` — Flow anchors after stochastic fraud pattern application.
- `s3_event_stream_with_fraud_6B` — Per-event stream reflecting injected fraud signals and metadata.

### 5.2 Catalogue & downstream obligations
Implementations and downstream consumers MUST resolve datasets via the dictionary/registry, honour the declared schema anchors, and treat any artefact not listed there as out of scope for this state.

## 6. Deterministic algorithm (with RNG) *(Binding)*

This section specifies **how** 6B.S3 constructs its three outputs for a given
`(manifest_fingerprint, parameter_hash, seed, scenario_id)`:

* `s3_campaign_catalogue_6B`
* `s3_flow_anchor_with_fraud_6B`
* `s3_event_stream_with_fraud_6B`

S3 is **data-plane + RNG-consuming**:

* Deterministic given:

  * `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`,
  * inputs from S1/S2/6A listed in §3,
  * 6B fraud configs (`fraud_campaign_catalogue_config_6B`, `fraud_overlay_policy_6B`, `fraud_rng_policy_6B`, etc.),
  * Layer-3 Philox RNG contracts (families, budgets, substream keys).
* All stochastic choices MUST go through **S3-specific RNG families** declared in `fraud_rng_policy_6B`. No ad-hoc RNG is allowed.

At a high level, per world/run:

1. Discover the **campaign universe** and targeting domains.
2. Realise **campaign instances** using RNG (how many, when, with what parameters).
3. Select **targets** (entities/sessions/flows/events) per campaign instance using RNG.
4. Construct **overlay plans** for flows/events (mutations and pure-fraud flows).
5. Instantiate overlay flows/events into S3 datasets, respecting identity & coverage invariants.
6. Write outputs atomically and enforce idempotence and RNG envelope sanity.

If any step fails the constraints in this section, S3 MUST fail for the affected domain and MUST NOT publish partial S3 outputs.

---

### 6.1 Determinism & RNG envelope

**Binding constraints:**

1. **Pure function + Philox**

   For fixed inputs and fixed `(manifest_fingerprint, parameter_hash, seed)` (and `scenario_id` where S3’s logic is partitioned that way), S3’s outputs MUST be bit-for-bit reproducible, given:

   * the same 6B configs and
   * the same Layer-3 RNG/RNG-policy definitions.

2. **RNG families reserved for S3**

   All random draws for S3 MUST use Philox through a small set of S3-specific RNG families defined in `fraud_rng_policy_6B`. Names are indicative (actual names live in the RNG spec):

   * `rng_event_campaign_activation` — for realising campaign instances (e.g. how many, with what offsets).
   * `rng_event_campaign_targeting` — for selecting targets (entities/sessions/flows/events).
   * `rng_event_overlay_mutation` — for per-target overlay decisions (e.g. whether to mutate amount, timestamps, routing, or spawn extra events/flows).

   S3 MUST NOT use RNG families reserved for other states, nor introduce undocumented families.

3. **Fixed budgets per decision type**

   For each stochastic decision, S3 MUST adhere to a fixed, documented budget in `fraud_rng_policy_6B`, e.g.:

   * `1` draw per campaign activation decision,
   * `k` draws per campaign instance for targeting (where `k` is a deterministic function of candidate set size and policy),
   * `m` draws per flow/event mutation decision (with `m` fixed given the event type / overlay rule).

   The exact numbers live in configuration; here we require that:

   * **domain size** + policy → fully determines the number of draws per family.

4. **Deterministic keying**

   S3 MUST key RNG substreams deterministically, using combinations of:

   * `manifest_fingerprint`, `parameter_hash`, `seed`,
   * `scenario_id` (where appropriate),
   * `campaign_id` (or hashed template id / instance index),
   * `flow_id`, `session_id`, `event_seq`.

   Keys MUST be chosen so that:

   * re-ordering loops over campaigns/targets does **not** change the sequence of draws, and
   * no two logically distinct decisions share the same key in the same RNG family.

---

### 6.2 Step 0 — Discover domains & load configs

For a given `manifest_fingerprint` and `seed`:

1. Read and validate:

   * `s0_gate_receipt_6B` and `sealed_inputs_6B`,
   * S1/S2 outputs for all `(seed, scenario_id)` being processed,
   * required 6A posture surfaces (§3.4),
   * S3 config packs: `fraud_campaign_catalogue_config_6B`, `fraud_overlay_policy_6B`, `fraud_rng_policy_6B`, and any validation/tuning packs.

2. From `fraud_campaign_catalogue_config_6B` discover the set of **campaign templates**:

   * Each template T has:

     * `campaign_type_T`,
     * segment definitions,
     * base parameters (intensity, duration, etc.),
     * any per-template constraints (e.g. target entity types, merchant MCC sets).

3. From S1/S2/6A, construct **targeting domains** per template type, e.g.:

   * candidate entities (parties/accounts/merchants/devices/IPs) that match static roles / segments,
   * candidate sessions/flows/events that match behaviour filters (channel, amount bucket, MCC, etc.).

These domains are deterministic given upstream inputs and configs; no RNG is used in Step 0.

---

### 6.3 Step 1 — Campaign instance realisation (with RNG)

For each campaign template T:

1. **Determine number of instances `N_T`**

   Using `fraud_campaign_catalogue_config_6B` and tuning/validation policies, S3 MUST decide how many instances of template T to realise for this world and seed:

   * Deterministic case:

     * Policy may prescribe an exact number (e.g. “one global card-testing campaign per seed”).
     * No RNG is consumed.

   * Stochastic case:

     * If policy defines a distribution over `N_T` (e.g. Poisson, binomial, categorical), S3 MUST:

       * use `rng_event_campaign_activation` with a key based on `(manifest_fingerprint, seed, template_id)`,
       * draw the configured number of uniforms for that family,
       * map draws to `N_T` via the configured distribution.

2. **Instantiate each campaign instance**

   For each instance `i ∈ {1..N_T}` of template T, S3 MUST:

   * deterministically compute a **campaign_id**, e.g.:

     ```text
     campaign_id = hash64(manifest_fingerprint, seed, template_id, i)
     ```

     or an equivalent stable scheme (the exact law is fixed in the identity spec).

   * sample or derive instance-level parameters:

     * start/end time windows within the world horizon,
     * per-instance intensity multipliers,
     * any per-instance variation (e.g. region focus, merchant subset).

     For any stochastic instance parameters, S3 MUST use `rng_event_campaign_activation` keyed on `(manifest_fingerprint, seed, template_id, campaign_index)` and consume a fixed number of draws per parameter.

3. **Populate campaign catalogue rows**

   For each realised `campaign_id`, S3 constructs a row for `s3_campaign_catalogue_6B`:

   * identity axes + `campaign_id`,
   * `campaign_type`, `template_id`, resolved parameters,
   * scope descriptors (scenario_scope, time window, target segment descriptors).

Intensity counts (`target_entity_count`, `target_flow_count`, etc.) are populated later once targeting is completed (Step 3) and written before persist.

No campaign-level overlay happens yet; this step only defines *what campaigns exist*.

---

### 6.4 Step 2 — Build per-campaign targeting domains

For each campaign instance C (with known `campaign_id`, type, scope):

1. **Define campaign-level filters**

   From C’s resolved parameters and `fraud_campaign_catalogue_config_6B`:

   * derive entity filters (e.g. `party_fraud_role == MULE`, `merchant_mcc in {…}`, region/time filters),
   * derive flow/session filters (e.g. flows above certain amount, sessions with specific channels, time windows).

2. **Construct targeting domains**

   Using S1/S2/6A surfaces:

   * Build candidate sets:

     * `D_entities(C)` ⊆ entities (parties/accounts/merchants/devices/IPs) that meet C’s conditions;
     * `D_sessions(C)` ⊆ S1 sessions matching C’s filters;
     * `D_flows(C)` ⊆ S2 flows matching C’s filters;
     * optionally `D_events(C)` ⊆ S2 events (for event-level attacks).

   * Ensure these domains are deterministic and completely defined by upstream data and config; **no RNG** is used in building them.

3. **Check feasibility**

   * If a campaign template or instance requires a minimum number of targets and `D_*` domains are insufficient, S3 MUST follow the template’s policy:

     * either mark the campaign instance as **inactive** and:

       * record it in the catalogue with zero realised intensity, or
       * remove it entirely from the realised set, depending on spec;

     * or treat as a failure if the template is marked “must fire”.

   The exact behaviour is controlled by `fraud_campaign_catalogue_config_6B`. Under this spec, if a campaign is marked “must fire” and has no feasible targets, S3 MUST fail the partition with an appropriate error (covered in §9), not silently ignore it.

---

### 6.5 Step 3 — Target selection (with RNG)

For each campaign instance C with non-empty domains:

1. **Compute targeting quotas**

   From C’s parameters (intensity) and tuning policy, compute target counts:

   * `n_entities(C)` — number of entities (e.g. cards/accounts/merchants) to target.
   * `n_flows(C)` — number of flows to target, if flow-centric.
   * `n_sessions(C)` — number of sessions, if session-centric.

   These may be deterministic or require RNG (e.g. sampling from binomial/Poisson distributions) using `rng_event_campaign_targeting` with a key based on `(manifest_fingerprint, seed, campaign_id)`.

2. **Sample target sets**

   Within each domain (e.g. `D_entities(C)`), S3 MUST:

   * define a deterministic **weighting** over candidates, based on posture and behaviour priors (e.g. favour high-risk posture, high-volume merchants, specific channels).
   * choose a sampling scheme consistent with `fraud_campaign_catalogue_config_6B` (e.g. weighted without replacement, stratified sampling).

   For each target slot:

   * use `rng_event_campaign_targeting` with a key that includes `(manifest_fingerprint, seed, campaign_id, target_index, target_kind)`;
   * draw the configured number of uniforms;
   * map those draws to a candidate in the domain.

3. **Form campaign target sets**

   S3 records:

   * `T_entities(C)` ⊆ `D_entities(C)` — chosen entities.
   * `T_sessions(C)` ⊆ `D_sessions(C)` — chosen sessions.
   * `T_flows(C)` ⊆ `D_flows(C)` — chosen flows.

   These target sets are used in the overlay step. The size and composition of T_* MUST align with the quotas and targeting rules in campaign config.

4. **Update campaign catalogue metrics**

   Once targets are chosen, S3 MUST update the in-memory campaign catalogue rows for each `campaign_id` with:

   * `target_entity_count`, `target_session_count`, `target_flow_count`, etc.

These metrics are persisted in `s3_campaign_catalogue_6B` when outputs are written.

---

### 6.6 Step 4 — Overlay planning for flows/events (with RNG)

For each targeted object (flow/session/entity) in each campaign instance, S3 constructs overlay plans.

1. **Flow-level overlay type**

   For each target flow `f ∈ T_flows(C)` (or flows derived from targeted sessions/entities):

   * Use `fraud_overlay_policy_6B` to determine which overlay template applies, given:

     * `campaign_type`,
     * flow context (baseline outcome, amounts, entity types, channel, time),
     * entity posture from 6A.

   * If multiple overlay templates are available, S3 MUST select one using `rng_event_overlay_mutation` with a key `(manifest_fingerprint, seed, campaign_id, flow_id, overlay_stage)` and fixed draw budget.

   Examples:

   * For card testing: convert baseline flow into a burst of small test transactions.
   * For ATO: generate sequences of login failures/suspicious changes before flows.
   * For refund abuse: chain legitimate purchase + abnormal refund pattern.

2. **Plan mutations and extra flows**

   Based on chosen overlay type, S3 MUST derive an overlay plan:

   * **Mutations of existing flows/events**:

     * which events in S2 will be mutated (amount/timing/routing),
     * which events will be removed or re-ordered (if policy allows),
     * which events are flagged as `is_fraud_event`.

   * **New events within existing flows**:

     * events to be inserted (e.g. extra auth attempts, suspicious step-ups).

   * **New flows (“pure fraud” flows)**:

     * number and shape of new flows to be created under a campaign (e.g. card tests that have no baseline counterpart),
     * their relation to existing sessions/entities (e.g. same account/device, new sessions).

   For each stochastic choice (e.g. “do we spawn an extra auth here?”, “how many test transactions per card?”), S3 MUST use `rng_event_overlay_mutation` keyed by `(manifest_fingerprint, seed, campaign_id, flow_id, local_index)` with fixed draw budgets.

3. **Ensure local policy constraints**

   The overlay plan MUST respect constraints defined in `fraud_overlay_policy_6B`, e.g.:

   * maximum number of mutated events per flow,
   * realistic spacing in time,
   * not exceeding configured fraud intensity bounds for a campaign,
   * keeping amounts and routing within plausible ranges (e.g. not negative amounts, TZ/routing combinations that violate upstream constraints).

If a plan would violate these constraints, S3 MUST adjust or reject the overlay for that target according to policy (e.g. skipping that target) or, if policy requires strict adherence, fail the partition with an overlay-specific error.

---

### 6.7 Step 5 — Instantiating overlay flows & events

After planning, S3 instantiates overlay flows and events into its S3 datasets.

1. **Flow-level instantiation**

   For each **baseline flow** `f` in S2:

   * Determine whether `f` is touched by one or more campaigns:

     * If not touched:

       * Create a row in `s3_flow_anchor_with_fraud_6B` with:

         * `flow_id` = baseline flow_id,
         * `origin_flow_id` = baseline flow_id,
         * `origin_type = "BASELINE_FLOW"`,
         * `campaign_id = null`,
         * `fraud_pattern_type = "NONE"`,
         * baseline amounts/timestamps/outcomes copied verbatim,
         * overlay flags all false.

     * If touched by one or more campaigns:

       * Merge overlay plans (if multiple campaigns stack) according to `fraud_overlay_policy_6B` (this may be deterministic or use RNG in a controlled way).
       * Create a row with:

         * `flow_id` = baseline flow_id,
         * `origin_flow_id` = baseline flow_id,
         * `origin_type = "BASELINE_FLOW_MUTATED"`,
         * `campaign_id` and `fraud_pattern_type` set per merged plan (policy MUST define how to handle multiple campaigns; e.g. primary vs secondary campaign fields),
         * mutated amounts/timestamps/outcomes in the anchor, consistent with event-level overlay,
         * overlay flags/metrics summarising the mutations.

   For each **pure fraud flow** `f_new` created in overlay planning:

   * Choose `flow_id` deterministically (e.g. via hash combining `(manifest_fingerprint, seed, campaign_id, local_flow_index)`) ensuring no collision with S2 flow_ids.
   * Create a row with:

     * `origin_type = "PURE_FRAUD_FLOW"`,
     * `origin_flow_id = null` or a related baseline flow id if policy demands,
     * `campaign_id` and `fraud_pattern_type` set appropriately,
     * entity context determined within policy constraints (entities MUST exist in 6A and be consistent with S1 attachments/patterns),
     * baseline-like amounts/timestamps/outcomes for this synthetic fraud flow.

2. **Event-level instantiation**

   For each **baseline flow**:

   * Start from its S2 event sequence and overlay plan:

     * For each baseline event, decide: keep unchanged, mutate, or drop, based on overlay plan.
     * For new events, decide their insertion positions within the flow (with event_seq re-assigned to form a contiguous ordering).

   * Materialise events in `s3_event_stream_with_fraud_6B` with:

     * identity axes: `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`, `flow_id`, `event_seq`,
     * baseline fields (type, timestamps, amounts, entity/routing context) copied or mutated as per plan,
     * overlay provenance: `origin_flow_id`, `origin_event_seq` where the event comes from; null for entirely new events,
     * overlay flags and `is_fraud_event` set appropriately,
     * `campaign_id` and `fraud_pattern_type` aligned with flow-level tags (if an event is touched by multiple campaigns, policy MUST define how to record this; e.g. primary campaign id plus extra metadata).

   For **pure fraud flows**:

   * Instantiate events according to overlay plan (timing, structure, amounts, routing) consistent with upstream constraints.
   * Use new `flow_id`s and event sequences starting from a consistent base.
   * Set `origin_flow_id`/`origin_event_seq` appropriately (likely null or referencing related baseline flows).

3. **Local consistency checks (per partition)**

   Before writing, S3 MUST locally verify:

   * Every `flow_id` in `s3_flow_anchor_with_fraud_6B` has ≥1 event in `s3_event_stream_with_fraud_6B`.
   * Every event’s `flow_id` exists in the overlay anchor.
   * `event_seq` is contiguous and strictly monotone per flow.
   * For flows derived from baseline, entity context remains consistent with S1/S2 and 6A; for pure fraud flows, entity context still references valid 6A entities and obeys link/posture constraints.
   * Flow-level overlay fields (amounts, timestamps, overlay flags) are consistent with event-level overlay.

If any of these checks fail, S3 MUST consider the partition FAIL and MUST NOT write outputs.

---

### 6.8 Step 6 — Write outputs & enforce idempotence

For each `(manifest_fingerprint, seed)` (for the campaign catalogue) and each `(manifest_fingerprint, seed, scenario_id)` (for flow/event overlays):

1. **Write `s3_campaign_catalogue_6B`**

   * For the `(seed, fingerprint)` pair, write a single parquet file per spec:

     ```text
     data/layer3/6B/s3_campaign_catalogue_6B/seed={seed}/fingerprint={manifest_fingerprint}/s3_campaign_catalogue_6B.parquet
     ```

   * Ensure PK uniqueness and schema validity.

2. **Write `s3_flow_anchor_with_fraud_6B` and `s3_event_stream_with_fraud_6B` per partition**

   * For each `(seed, fingerprint, scenario_id)`:

     * Write `s3_event_stream_with_fraud_6B` rows, sorted and PK-validated.
     * Write `s3_flow_anchor_with_fraud_6B` rows, sorted and PK-validated.

   * S3 MUST treat these two datasets as a **unit** per partition:

     * Either both are successfully written and schema-valid, or neither is considered valid.

3. **Idempotent re-runs**

   For a given `(manifest_fingerprint, parameter_hash, seed)` / `(seed, fingerprint, scenario_id)`:

   * If outputs do not exist yet, S3 writes them once.
   * If outputs already exist, a re-run MUST either:

     * reproduce logically identical outputs (same rows, same keys, same overlay attributes, modulo allowed low-level encoding variation), or
     * fail with an idempotence/merge error and MUST NOT overwrite existing data.

   This implies:

   * No in-place append/merge semantics.
   * Any material change in campaign/overlay behaviour for a given world and `parameter_hash` MUST be guarded by a new `parameter_hash` or `spec_version_6B`.

---

### 6.9 RNG accounting obligations

S3 MUST support Layer-3 RNG accounting and validation:

* For each RNG family used by S3 (`rng_event_campaign_activation`, `rng_event_campaign_targeting`, `rng_event_overlay_mutation`):

  * The number of RNG events and draws MUST be:

    * deterministic given the domains (#templates, #campaign instances, #targets, #overlay decisions), and
    * within a documented bound as a function of those domains.

  * S3 MUST emit RNG events/logs according to the Layer-3 RNG schema, so the 6B validation state (S5) can cross-check:

    * the number of campaign instances realised vs config,
    * the number of targets vs quotas,
    * the number of overlay decisions vs flows/events actually mutated,
    * the monotonicity and non-overlap of RNG counters.

* S3 MUST NOT:

  * mix decision types within one RNG family in ways not declared in `fraud_rng_policy_6B`,
  * use data-dependent short-circuiting that changes the number of RNG events for a given domain size without being accounted for in policy.

Together with §§1–5, this algorithm defines S3 as a **deterministic, RNG-accounted overlay layer**: it takes sealed S1/S2/6A worlds and 6B campaign configs, realises fraud/abuse campaigns, and produces reproducible “with_fraud” flows/events and a campaign catalogue that S4 and S5 can rely on.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S3’s outputs are identified and stored**, and what rules implementations MUST follow for **partitioning, ordering, coverage, re-runs and merges**.

It applies to all three S3 datasets:

* `s3_campaign_catalogue_6B`
* `s3_flow_anchor_with_fraud_6B`
* `s3_event_stream_with_fraud_6B`

and is binding for any conforming implementation.

---

### 7.1 Identity axes for S3

S3 has two natural identity scopes:

* **World + seed** for campaign catalogue:

  ```text
  (manifest_fingerprint, seed)
  ```

* **World + seed + scenario** for flow/event overlays:

  ```text
  (manifest_fingerprint, seed, scenario_id)
  ```

Binding rules:

1. **All S3 rows MUST carry their axes explicitly**:

   * `s3_campaign_catalogue_6B`: `manifest_fingerprint`, `seed`.
   * `s3_flow_anchor_with_fraud_6B`: `manifest_fingerprint`, `seed`, `scenario_id`.
   * `s3_event_stream_with_fraud_6B`: `manifest_fingerprint`, `seed`, `scenario_id`.

2. S3 MUST NOT introduce `run_id` or any other execution identifier as a partition key for these data-plane outputs. `run_id` is reserved for RNG/logging surfaces.

3. For a given world (`manifest_fingerprint`) and seed, S3 operates on the same set of `scenario_id`s as S2 (i.e. those for which S2 outputs exist and are PASS).

Within these axes:

* `campaign_id` is unique per `(seed, manifest_fingerprint)`.
* `flow_id` is unique per `(seed, manifest_fingerprint, scenario_id)`.
* `(flow_id, event_seq)` is unique per `(seed, manifest_fingerprint, scenario_id)`.

---

### 7.2 Partitioning & path layout

S3 datasets MUST use the following partitioning and path templates:

* **Campaign catalogue**:

  * `partitioning: [seed, fingerprint]`
  * `path`:

    ```text
    data/layer3/6B/s3_campaign_catalogue_6B/
        seed={seed}/fingerprint={manifest_fingerprint}/s3_campaign_catalogue_6B.parquet
    ```

* **Flow overlay anchor**:

  * `partitioning: [seed, fingerprint, scenario_id]`
  * `path`:

    ```text
    data/layer3/6B/s3_flow_anchor_with_fraud_6B/
        seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
    ```

* **Event overlay stream**:

  * `partitioning: [seed, fingerprint, scenario_id]`
  * `path`:

    ```text
    data/layer3/6B/s3_event_stream_with_fraud_6B/
        seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
    ```

Binding path↔embed rules:

* For every row in `s3_campaign_catalogue_6B`:

  * `seed` column MUST equal the `seed={seed}` path token, and
  * `manifest_fingerprint` MUST equal the `fingerprint={manifest_fingerprint}` token.

* For every row in `s3_flow_anchor_with_fraud_6B` and `s3_event_stream_with_fraud_6B`:

  * `seed`, `manifest_fingerprint`, `scenario_id` columns MUST match their respective path tokens.

No S3 data-plane rows may be written outside these layouts or without the appropriate axes.

---

### 7.3 Primary keys & writer ordering

#### 7.3.1 `s3_campaign_catalogue_6B`

**Primary key (binding):**

```text
[seed, manifest_fingerprint, campaign_id]
```

**Writer ordering (binding):**

```text
[seed, manifest_fingerprint, campaign_id]
```

Per `(seed, manifest_fingerprint)`:

* Each `campaign_id` MUST be unique.
* Rows MUST be sorted by `campaign_id` in ascending order.

#### 7.3.2 `s3_flow_anchor_with_fraud_6B`

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

For baseline-derived flows:

* `flow_id` MUST equal the corresponding `flow_id` in `s2_flow_anchor_baseline_6B`.

For pure-fraud flows:

* `flow_id` MUST be chosen so that it does not collide with any baseline `flow_id` in the same partition.

#### 7.3.3 `s3_event_stream_with_fraud_6B`

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
* `event_seq` MUST form a **contiguous**, strictly monotone sequence starting at a defined base (e.g. `0` or `1`, as the schema specifies).
* Rows MUST be grouped by `flow_id` and ordered by `event_seq` within each group.

---

### 7.4 Coverage & relationship to S2 outputs

For each `(manifest_fingerprint, seed, scenario_id)`:

Let:

* `FA2` = `s2_flow_anchor_baseline_6B@{seed,fingerprint,scenario_id}`,
* `EV2` = `s2_event_stream_baseline_6B@{seed,fingerprint,scenario_id}`,
* `FA3` = `s3_flow_anchor_with_fraud_6B@{seed,fingerprint,scenario_id}`,
* `EV3` = `s3_event_stream_with_fraud_6B@{seed,fingerprint,scenario_id}`.

Binding relationships:

1. **Flow coverage**

   * Every `flow_id` present in `FA2` MUST appear in `FA3`:

     ```text
     {flow_id(FA2)} ⊆ {flow_id(FA3)}
     ```

   * `FA3` MAY contain additional `flow_id`s that do not appear in `FA2` (pure fraud flows).

2. **Flow/event coverage within S3**

   * Every `flow_id` in `FA3` MUST have ≥1 corresponding event row in `EV3`.
   * Every event row in `EV3` MUST reference a `flow_id` existing in `FA3` for the same partition.

3. **Baseline vs overlay flow identity**

   * For flows derived from baseline:

     * `flow_id(FA3)` == `flow_id(FA2)` for that flow.
     * `origin_flow_id` in `FA3` MUST equal that baseline `flow_id`.
     * Entity identity and baseline fields must remain traceable to `FA2`.

   * For pure-fraud flows:

     * `flow_id(FA3)` ∉ `flow_id(FA2)`.
     * `origin_type` MUST indicate `PURE_FRAUD_FLOW`.
     * `origin_flow_id` MUST follow policy (null or set to a related baseline flow).

4. **Baseline vs overlay events**

   * For events that are mutated versions of baseline events:

     * `origin_flow_id` and `origin_event_seq` in an `EV3` row MUST reference a unique event in `EV2` for the same axes.

   * For completely new events (pure fraud or inserted overlay events):

     * `origin_*` fields MAY be null or reference a related baseline event, as specified by policy, but MUST be consistent across re-runs.

These identity relationships are enforced by S3’s acceptance criteria and by S5.

---

### 7.5 Join discipline for downstream states

Downstream states (S4, S5) MUST use the following join keys:

* **Campaigns ↔ overlays**

  * For any non-null `campaign_id` in `FA3` or `EV3`, join back to the campaign catalogue via:

    ```text
    [seed, manifest_fingerprint, campaign_id]
    ```

* **Overlays ↔ baseline flows**

  * For baseline-derived flows:

    * join `FA3` back to `FA2` via:

      ```text
      [seed, manifest_fingerprint, scenario_id, origin_flow_id]
      ```

    * join `EV3` partial overlays back to `EV2` via:

      ```text
      [seed, manifest_fingerprint, scenario_id, origin_flow_id, origin_event_seq]
      ```

  * For pure-fraud flows and events:

    * `origin_*` may be null or set per policy; S4/S5 must treat those as flows/events with no direct baseline counterpart.

* **Flows ↔ events within S3**

  * Join `FA3` and `EV3` via:

    ```text
    [seed, manifest_fingerprint, scenario_id, flow_id]
    ```

* **Flows ↔ sessions/entities (via S1/S2)**

  * Use the existing identity keys:

    * Flows ↔ sessions: `[seed, manifest_fingerprint, scenario_id, session_id]`.
    * Flows ↔ S1 arrivals: via arrival linkage fields in `FA3` + S1’s arrival PK.

Downstream states MUST NOT infer relationships from file names or ordering alone; they MUST use these explicit keys.

---

### 7.6 Re-run & merge discipline

S3 MUST be **idempotent** for a given configuration and domain:

> For fixed `(manifest_fingerprint, parameter_hash, seed)` and `scenario_id`, and fixed upstream inputs, re-running S3 MUST either reproduce the same logical outputs or fail without overwriting.

Binding rules:

1. **Unit of work**

   * For campaigns: the unit is `(manifest_fingerprint, seed)` (catalogue).
   * For overlays: the unit is `(manifest_fingerprint, seed, scenario_id)` (flow/event overlays).

   Within each unit:

   * S3 MUST treat the relevant S3 datasets as a **pair** or triple (for flows/events, plus catalogue at the seed scope), and not leave mismatched partial states.

2. **Single logical writer per unit**

   * At any point in time, at most one S3 instance may be responsible for writing:

     * `s3_campaign_catalogue_6B` for a given `(seed, fingerprint)`, and
     * `s3_flow_anchor_with_fraud_6B` / `s3_event_stream_with_fraud_6B` for a given `(seed, fingerprint, scenario_id)`.

   * Parallelism across different seeds or scenarios is allowed, but concurrent writes to the same partition set by different instances are disallowed.

3. **Idempotent re-runs**

   For a given unit:

   * If S3 outputs do not exist:

     * S3 writes them once.

   * If S3 outputs already exist:

     * A re-run MUST either:

       * produce logically identical outputs (same rows/keys/attributes, modulo allowed low-level encoding if the engine defines that notion), or
       * fail with an idempotence error (e.g. `S3_IDEMPOTENCE_VIOLATION`) and MUST NOT overwrite existing data.

   Incremental “append-only” or partial merge semantics are forbidden.

4. **Handling partial failures**

   * If an S3 run fails after writing some but not all required artefacts for a unit (e.g. event overlays written but flow overlays not), the partition/unit MUST be considered FAILED.
   * Orchestrators MUST ensure such partial outputs are either:

     * cleaned up, or
     * consistently treated as invalid on the next attempt, in line with engine-wide recovery rules.

---

### 7.7 Interaction with RNG logs (non-partition identity)

S3 consumes RNG via its families (e.g. `rng_event_campaign_activation`, `rng_event_campaign_targeting`, `rng_event_overlay_mutation`).

RNG evidence/log datasets (if materialised) follow the **Layer-3 RNG partition law**, typically:

* `partitioning: [seed, parameter_hash, run_id]`

Binding points:

* S3 data-plane outputs MUST NOT include `run_id` or depend on RNG-log partition layout for their identity.
* RNG log records MUST encode keys (e.g. `campaign_id`, `flow_id`, `session_id`, decision type) sufficient for S5 to reconcile:

  * how many campaigns were realised,
  * how many targets per campaign,
  * how many overlay decisions per flow/event.

The only link between RNG logs and S3 outputs is via shared axes (`seed, parameter_hash`) and keys (e.g. `campaign_id`, `flow_id`), not via segmentation or partitioning of S3 datasets themselves.

---

By adhering to these identity, partitioning, ordering and merge rules, S3 remains:

* a deterministic, reproducible overlay layer on top of S1/S2 and 6A, and
* a stable, unambiguous foundation for S4 (labelling) and S5 (validation/HashGate) to reason about fraud/abuse campaigns and their impact on flows and events.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines:

* When 6B.S3 is considered **PASS** vs **FAIL**, and
* How that status gates **S4 (labelling)**, **S5 (6B validation/HashGate)**, and orchestrators.

S3 has two scopes:

* **World + seed** for the campaign catalogue: `(manifest_fingerprint, seed)`.
* **World + seed + scenario** for flow/event overlays: `(manifest_fingerprint, seed, scenario_id)`.

S3 is only **globally acceptable** for a world if **both** scopes satisfy their criteria.

---

### 8.1 Acceptance criteria — campaign catalogue (per `(manifest_fingerprint, seed)`)

For a fixed `(manifest_fingerprint, seed)`, S3 is considered **PASS at the campaign catalogue scope** if and only if:

1. **Preconditions satisfied**

   * S0 has PASSed for `manifest_fingerprint`.
   * Upstream HashGates (`1A–3B`, `5A`, `5B`, `6A`) are `status="PASS"` in `s0_gate_receipt_6B`.
   * Required 6B fraud config packs (`fraud_campaign_catalogue_config_6B`, `fraud_overlay_policy_6B`, `fraud_rng_policy_6B`, and any required validation/tuning packs) are present in `sealed_inputs_6B` and schema-valid.

2. **`s3_campaign_catalogue_6B` exists and is schema-valid**

   * The parquet file for `(seed, fingerprint)` exists at the expected path.
   * It passes validation against `schemas.6B.yaml#/s3/campaign_catalogue_6B`.
   * PK/partition invariants hold:

     * `(seed, manifest_fingerprint, campaign_id)` is unique.
     * Partition columns in rows match path tokens.

3. **Campaign IDs & types are consistent with config**

   * Every `campaign_type` and `template_id` in the table is allowed by `fraud_campaign_catalogue_config_6B`.
   * No unexpected `campaign_type` appears (unless the config explicitly supports extensible enums).

4. **Campaign scope & intensity are internally coherent**

   For each `campaign_id` row:

   * The `start_ts_utc` and `end_ts_utc` window is within the world horizon and consistent (`start ≤ end`).
   * `scenario_scope` is valid for the world (scenario ids exist in S2/S1, or the field matches the intended scope semantics).
   * Realised intensity fields (e.g. `target_entity_count`, `target_flow_count`, `target_event_count`) are:

     * non-negative integers,
     * consistent with targeting policies (“must fire” campaigns have non-zero counts if they activated, inactive campaigns are clearly marked and have zero realised targets),
     * within any configured upper bounds (if config defines SLO-style limits).

5. **RNG envelope sanity for campaign activation/targeting**

   * Local counts of RNG decisions associated with campaign activation/targeting (for this `(seed, fingerprint)`) are within the configured budgets in `fraud_rng_policy_6B`.
   * No campaign instance was partially realised due to RNG misconfiguration (e.g. missing draws partway through activation).

If any of these catalogue-level criteria fail, S3 MUST be considered FAIL at the campaign scope for this `(manifest_fingerprint, seed)`, and all overlays that depend on those campaigns MUST be treated as invalid.

---

### 8.2 Acceptance criteria — overlays (per `(manifest_fingerprint, seed, scenario_id)`)

For a fixed `(manifest_fingerprint, seed, scenario_id)`, S3 is considered **PASS at the overlay scope** if and only if **all** of the following hold:

#### 8.2.1 Preconditions satisfied

* S0 is PASS for `manifest_fingerprint`.
* S1 and S2 are PASS for `(manifest_fingerprint, seed, scenario_id)` in the run-report.
* S1 datasets (`s1_arrival_entities_6B`, `s1_session_index_6B`) and S2 datasets (`s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`) exist and are schema-valid at this partition.
* `s3_campaign_catalogue_6B` is PASS for `(manifest_fingerprint, seed)` per §8.1.

#### 8.2.2 Schema & identity validity of S3 overlays

At this `(seed, fingerprint, scenario_id)`:

* `s3_flow_anchor_with_fraud_6B` exists and validates against `schemas.6B.yaml#/s3/flow_anchor_with_fraud_6B`.
* `s3_event_stream_with_fraud_6B` exists and validates against `schemas.6B.yaml#/s3/event_stream_with_fraud_6B`.
* PK/partition invariants hold:

  * Flow anchor:

    * `primary_key: [seed, manifest_fingerprint, scenario_id, flow_id]` unique.
    * Partition columns in rows match path tokens.

  * Event stream:

    * `primary_key: [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]` unique.
    * `event_seq` forms a contiguous, strictly monotone sequence per flow.
    * Partition columns in rows match path tokens.

If any schema/PK/partition constraint fails, S3 MUST fail the partition.

#### 8.2.3 Coverage & relationship to baseline flows/events

Let:

* `FA2` = S2 anchor (`s2_flow_anchor_baseline_6B`),
* `EV2` = S2 events (`s2_event_stream_baseline_6B`),
* `FA3` = S3 anchor (`s3_flow_anchor_with_fraud_6B`),
* `EV3` = S3 events (`s3_event_stream_with_fraud_6B`)
  for this `(seed, fingerprint, scenario_id)`.

S3 MUST ensure:

1. **Baseline flows preserved**

   * Every `flow_id` in `FA2` appears in `FA3`:

     ```text
     {flow_id(FA2)} ⊆ {flow_id(FA3)}
     ```

   * For each such flow:

     * `origin_flow_id` in `FA3` equals the baseline `flow_id`.
     * `origin_type` is either `BASELINE_FLOW` (no overlay) or `BASELINE_FLOW_MUTATED` (overlay applied).

2. **Flows & events coverage within S3**

   * Every `flow_id` in `FA3` has ≥1 event in `EV3`.
   * Every event in `EV3` references a `flow_id` present in `FA3` for the same axes.

3. **Baseline vs overlay event mapping (where applicable)**

   * For events that represent mutated baseline events, (`origin_flow_id`, `origin_event_seq`) in `EV3` MUST reference a unique baseline event in `EV2`.
   * For “pure overlay” events (inserted or pure-fraud), `origin_*` fields follow policy (null or referencing an appropriate baseline event/flow).

4. **Pure-fraud flows are clearly marked**

   * `flow_id`s that appear in `FA3` but not in `FA2` MUST have `origin_type = "PURE_FRAUD_FLOW"` (or equivalent), and their entity/session origin semantics MUST match S3 policy.

Any violation of these coverage rules MUST cause S3 to fail for the partition.

#### 8.2.4 Campaign linkage integrity

* For every non-null `campaign_id` in `FA3` or `EV3` at this partition:

  * There MUST be a row in `s3_campaign_catalogue_6B@{seed,fingerprint}` with the same `campaign_id`.

* For flows/events with `campaign_id = null`:

  * `fraud_pattern_type` MUST be `NONE` (or an equivalent “no campaign” value).
  * `is_fraud_event` MUST be false for all events referencing such flows.

* The realised intensity of each `campaign_id` in the catalogue (target_entity_count / target_flow_count / target_event_count) MUST be consistent with:

  * counts of tagged flows/events in `FA3`/`EV3`,
  * and configured bounds in `fraud_campaign_catalogue_config_6B`.

If flows/events reference campaigns that don’t exist in the catalogue, or catalogue counts materially disagree with actual overlays, S3 MUST fail.

#### 8.2.5 Entity & routing consistency

S3 MUST ensure:

* **Entities**:

  * All entity IDs in S3 flows/events (`party_id`, `account_id`, `instrument_id`, `device_id`, `ip_id`) are:

    * copied from S1/S2 or selected from valid 6A bases,
    * consistent with 6A link structure and static posture constraints,
    * not invented or mismatched (e.g. a flow annotated as fraud on a device that doesn’t belong to the session’s party/merchant when overlay policy forbids that).

* **Routing**:

  * Routing-related fields (e.g. `site_id`, `edge_id`, `is_virtual`, `routing_universe_hash`) in S3 events:

    * either match the baseline routing in S2, or
    * are mutated in a way consistent with overlay policy and upstream constraints (e.g. route change still legal under Layer-1 routing universe).

Any entity or routing inconsistencies must cause S3 to fail the partition.

#### 8.2.6 Temporal & structural plausibility

* Event timestamps and ordering in `EV3` MUST remain plausible:

  * Intra-flow temporal patterns must adhere to overlay policy limits for campaign types (e.g. realistic burst windows, no long gaps if not allowed).
  * Timestamps MUST remain within the world time horizon and any per-campaign window defined in `s3_campaign_catalogue_6B`.

* Flow-level summaries in `FA3` (fraud-linked timestamps, overlay flags) MUST be derivable from event-level data in `EV3`.

If overlay produces impossible sequences (e.g. negative time deltas or flows entirely outside configured windows), S3 MUST fail.

#### 8.2.7 RNG envelope sanity (local to S3)

For each partition:

* S3 MUST verify locally that the number of RNG events/draws per family:

  * is within the configured budgets as a function of:

    * number of campaign instances,
    * number of targets,
    * number of overlay decisions, and
  * is consistent with the domain size.

If S3’s internal counters show clear mismatches (e.g. too few targeting draws relative to targets, or orders of magnitude more overlay draws than overlay decisions), S3 MUST treat the partition as FAIL.

Full RNG reconciliation is done in S5; S3 is only responsible for its own local sanity.

---

### 8.3 Conditions that MUST cause S3 to FAIL

S3 MUST mark the partition (and where applicable, the `(seed,fingerprint)` campaign scope) as **FAIL** if any of the following occur:

* Any precondition in §2 is not met (missing S0/S1/S2/PASS, incomplete sealed_inputs, missing/invalid config).
* `s3_campaign_catalogue_6B`, `s3_flow_anchor_with_fraud_6B`, or `s3_event_stream_with_fraud_6B` fail schema or PK/partition validation.
* Flow/event coverage invariants in §8.2.3 are broken.
* Campaign linkage invariants in §8.2.4 are broken.
* Entity or routing inconsistencies in §8.2.5 are detected.
* Temporal or structural implausibility in §8.2.6 is detected beyond configured tolerances.
* RNG envelope sanity checks in §8.2.7 fail.
* Output write/idempotence rules in §7.6 are violated (e.g. partial overlay surfaces, non-idempotent re-runs).

On FAIL:

* S3 MUST NOT claim success for that partition in the run-report.
* S3 outputs for that partition MUST be treated as unusable by all downstream states.

---

### 8.4 Gating obligations for S4 (labelling)

For any `(manifest_fingerprint, seed, scenario_id)`:

1. **S3 PASS is a hard precondition for S4**

   * S4 MUST NOT run for that partition unless:

     * S0 is PASS at the world level,
     * S1 is PASS,
     * S2 is PASS, and
     * S3 is PASS for that partition.

2. **S3 overlays are the final behavioural canvas**

   * S4 MUST treat `s3_flow_anchor_with_fraud_6B` and `s3_event_stream_with_fraud_6B` as the **behavioural surfaces to label**:

     * Truth labels (`fraud_truth`, `abuse_type`, etc.) are applied over S3 flows/events, not directly over S2 baseline.
     * Bank-view labels (caught/not caught, disputes/chargebacks) are derived from S3 + S4 logic.

3. **No independent campaign logic in S4**

   * S4 MUST NOT implement its own separate fraud campaign logic that contradicts S3. It may:

     * interpret fraud patterns and campaign tags,
     * compute label surfaces based on them,
     * but MUST NOT change which flows/events belong to which campaigns.

If S4 detects missing or malformed S3 overlays for a partition, it MUST fail preconditions, not attempt to rebuild overlays itself.

---

### 8.5 Obligations for S5 (6B validation / HashGate) and 4A/4B

**S5 (validation / HashGate) obligations:**

* S5 MUST treat S3’s acceptance criteria in §8.1–§8.2 as **binding checks**:

  * verify campaign catalogue vs config,
  * verify flow/event coverage and linkages,
  * verify entity/routing consistency,
  * reconcile RNG usage with `fraud_rng_policy_6B`,
  * cross-check realised fraud intensity vs campaign targets.

* If any S3 invariant fails, S5 MUST mark the overall 6B segment HashGate as FAIL for that `manifest_fingerprint`, regardless of S4 status.

* S5 MUST include S3’s outputs and run-report status in its validation bundle for transparency.

**4A/4B & external consumers:**

* 4A/4B and external consumers MUST NOT rely directly on S3’s `status`; they gate on S5’s segment HashGate.
* However, for diagnostics, they MAY surface S3 metrics (e.g. realised fraud rate by segment, campaign coverage) as part of their reporting.

Under no circumstances may 4A/4B treat S3 PASS alone as sufficient to read or trust 6B flows/events; S5’s HashGate remains the final gate for Layer-3 behaviour.

---

In summary, these acceptance criteria ensure that:

* S3’s campaign catalogue is consistent with config,
* S3’s overlays are structurally and semantically sound,
* S4 builds labels only on top of a well-defined fraud/abuse canvas, and
* S5 can enforce all these invariants when deciding whether 6B as a whole is safe to expose.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical failure modes** for 6B.S3 and the **error codes** that MUST be used when they occur.

For any world/partition S3 attempts:

* At the **campaign scope**: `(manifest_fingerprint, seed)`
* At the **overlay scope**: `(manifest_fingerprint, seed, scenario_id)`

S3 MUST:

* End each scope in exactly one of: `status="PASS"` or `status="FAIL"`.
* If `status="FAIL"`, attach a **single primary error code** (from this section) and MAY attach secondary codes and diagnostics.

Downstream states (S4, S5) and orchestrators MUST treat any S3 failure as a **hard gate** at the relevant scope.

---

### 9.1 Error model & context

For any failed S3 scope:

* **Primary error code**

  * One code from §§9.2–9.8 (e.g. `S3_OVERLAY_FLOW_EVENT_MISMATCH`).
  * Summarises the main cause of failure.

* **Secondary error codes** (optional)

  * List of additional codes adding detail (e.g. both `S3_CAMPAIGN_TAGGING_INCONSISTENT` and `S3_CAMPAIGN_INTENSITY_MISMATCH`).
  * MUST NOT be present without a primary code.

* **Context fields** (run-report/logs SHOULD include):

  * `manifest_fingerprint`
  * `seed`
  * `scenario_id` (for overlay-scope failures; may be null for catalogue-only failures)
  * Optionally `campaign_id`, `flow_id`, `event_seq`, `owner_segment`, `manifest_key`, etc.
  * Optional human-readable `detail`.

The run-report schema will carry these; here we bind the error codes and their semantics.

---

### 9.2 Preconditions & sealed-input / policy failures

These indicate S3 never legitimately entered campaign realisation or overlay for the given scope.

#### 9.2.1 `S3_PRECONDITION_S0_S1_S2_FAILED`

**Definition**
Emitted when any of the necessary S0/S1/S2 preconditions fail:

* S0 not PASS for `manifest_fingerprint`, or
* S1 not PASS for `(manifest_fingerprint, seed, scenario_id)`, or
* S2 not PASS for `(manifest_fingerprint, seed, scenario_id)`.

**Examples**

* `s0_gate_receipt_6B` missing or schema-invalid.
* Run-report shows S1 or S2 `status="FAIL"` or no S1/S2 entry for the partition.

**Obligations**

* S3 MUST NOT read S1/S2 outputs or upstream data-plane tables.
* No S3 outputs for the world/partition may be considered valid.

---

#### 9.2.2 `S3_PRECONDITION_SEALED_INPUTS_INCOMPLETE`

**Definition**
Emitted when `sealed_inputs_6B` exists but lacks required entries for S3.

**Examples**

* Required S1/S2 surfaces (`s1_arrival_entities_6B`, `s1_session_index_6B`, `s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`) missing or not marked `status="REQUIRED", read_scope="ROW_LEVEL"`.
* Required 6A posture surfaces missing or mis-declared.
* Required S3 config packs (`fraud_campaign_catalogue_config_6B`, `fraud_overlay_policy_6B`, `fraud_rng_policy_6B`) missing from `sealed_inputs_6B`.

**Obligations**

* S3 MUST fail before reading any data-plane rows or attempting overlay.
* S3 MUST NOT guess paths or read artefacts not in `sealed_inputs_6B`.

---

#### 9.2.3 `S3_PRECONDITION_RNG_OR_CAMPAIGN_POLICY_INVALID`

**Definition**
Emitted when S3 cannot correctly load or validate its RNG or campaign config.

**Examples**

* `fraud_rng_policy_6B` missing or schema-invalid.
* RNG family names configured for S3 not present in Layer-3 RNG spec.
* `fraud_campaign_catalogue_config_6B` or `fraud_overlay_policy_6B` fail schema validation or contain inconsistent parameters (e.g. impossible segment definitions, negative intensities).

**Obligations**

* S3 MUST NOT attempt campaign realisation or overlay.
* Config/RNG setup must be fixed before S3 can run.

---

### 9.3 Campaign realisation & catalogue failures

These failures apply at the **campaign catalogue** scope `(manifest_fingerprint, seed)`.

#### 9.3.1 `S3_CAMPAIGN_CATALOGUE_SCHEMA_VIOLATION`

**Definition**
Emitted when `s3_campaign_catalogue_6B` fails schema or identity validation.

**Examples**

* Missing required fields (e.g. `campaign_id`, `campaign_type`, `start_ts_utc`, `end_ts_utc`).
* Duplicate `(seed, manifest_fingerprint, campaign_id)` keys.
* Partition columns in rows (`seed`, `manifest_fingerprint`) do not match the path tokens.

**Obligations**

* Entire campaign catalogue for this `(seed, fingerprint)` is invalid.
* S3 MUST be considered FAIL for this scope; overlays depending on this catalogue MUST NOT be trusted.

---

#### 9.3.2 `S3_CAMPAIGN_REALISATION_FAILED`

**Definition**
Emitted when S3 cannot realise campaign instances as required by configuration.

**Examples**

* A template marked as “must fire” has no feasible targets in the world and config demands a non-zero intensity, but S3 cannot satisfy that without violating constraints.
* Required campaign parameters (window, intensity, segment scope) cannot be instantiated without conflicting with other constraints.

**Obligations**

* S3 MUST fail; campaign definitions or upstream world must be corrected.
* It is not acceptable to silently drop such campaigns if they are configured as mandatory.

---

#### 9.3.3 `S3_CAMPAIGN_DUPLICATE_ID`

**Definition**
Emitted when S3 generates or observes duplicate `campaign_id`s for a given `(seed, manifest_fingerprint)`.

**Examples**

* Two different campaign instances end up with the same `campaign_id` due to a bug in the id generation scheme.
* Catalogue contains duplicated rows for the same campaign.

**Obligations**

* S3 MUST treat catalogue as invalid and fail; duplicates undermine traceability of overlay behaviour.

---

### 9.4 Overlay schema & coverage failures

These failures concern the shape and coverage of S3’s overlay datasets.

#### 9.4.1 `S3_OVERLAY_FLOW_EVENT_SCHEMA_VIOLATION`

**Definition**
Emitted when `s3_flow_anchor_with_fraud_6B` or `s3_event_stream_with_fraud_6B` fails schema or key validation.

**Examples**

* Required overlay fields (e.g. `origin_flow_id`, `campaign_id`, `fraud_pattern_type`, `is_fraud_event`) missing or wrong type.
* Duplicate PKs in flow anchors or event stream.
* Partition columns (`seed`, `manifest_fingerprint`, `scenario_id`) inconsistent with path.

**Obligations**

* Overlay outputs for the partition are invalid; S3 MUST be FAIL for that partition.

---

#### 9.4.2 `S3_OVERLAY_FLOW_EVENT_MISMATCH`

**Definition**
Emitted when flows and events are inconsistent within S3 overlays.

**Examples**

* A `flow_id` in `s3_flow_anchor_with_fraud_6B` has **no** events in `s3_event_stream_with_fraud_6B`.
* Events exist in `s3_event_stream_with_fraud_6B` for a `flow_id` not present in the overlay anchor.

**Obligations**

* S3 MUST fail the partition; overlay outputs must be regenerated.

---

#### 9.4.3 `S3_OVERLAY_BASELINE_COVERAGE_MISMATCH`

**Definition**
Emitted when overlay coverage relative to baseline flows/events is broken.

**Examples**

* A baseline `flow_id` present in `s2_flow_anchor_baseline_6B` does not appear in `s3_flow_anchor_with_fraud_6B`.
* For events tagged as mutated baseline events, `(origin_flow_id, origin_event_seq)` does not correspond to any row in `s2_event_stream_baseline_6B`.

**Obligations**

* S3 MUST fail; it is not allowed to drop baseline flows entirely or mis-map overlay to non-existent baseline events.

---

### 9.5 Campaign tagging & intensity failures

These concern the linkage between campaigns and overlays, and realised intensity vs configuration.

#### 9.5.1 `S3_CAMPAIGN_TAGGING_INCONSISTENT`

**Definition**
Emitted when `campaign_id` / `fraud_pattern_type` fields in S3 overlays are inconsistent with the campaign catalogue.

**Examples**

* A non-null `campaign_id` in `s3_flow_anchor_with_fraud_6B` or `s3_event_stream_with_fraud_6B` does not exist in `s3_campaign_catalogue_6B` for the same `(seed, fingerprint)`.
* `fraud_pattern_type` values in flows/events are not allowed by the campaign’s declared `campaign_type`.

**Obligations**

* S3 MUST fail; campaign references in overlays must be traceable and type-consistent.

---

#### 9.5.2 `S3_CAMPAIGN_INTENSITY_MISMATCH`

**Definition**
Emitted when realised intensity in overlays materially disagrees with campaign definitions or tuning policy.

**Examples**

* `target_flow_count` in `s3_campaign_catalogue_6B` is 100 but only 10 flows in `s3_flow_anchor_with_fraud_6B` carry that `campaign_id`.
* Realised fraud rate per segment (as defined in tuning policy) is far outside configured tolerances for that campaign type, when the policy requires adherence within bounds.

**Obligations**

* S3 MUST fail; this indicates the engine did not realise campaigns as configured.

---

### 9.6 Entity & routing consistency failures

These capture inconsistencies between S3 overlays and S1/S2/6A entity and routing facts.

#### 9.6.1 `S3_TARGET_SELECTION_INCONSISTENT`

**Definition**
Emitted when S3’s selected targets (entities/sessions/flows) fall outside the segments defined by campaign configs or beyond static posture constraints.

**Examples**

* A campaign configured to target only accounts with `fraud_role_account="MULE"` ends up tagging flows where accounts have `fraud_role_account="NORMAL"`.
* A card-testing campaign intended for e-com flows ends up targeting POS flows contrary to configuration.

**Obligations**

* S3 MUST fail; target selection must honour campaign segment definitions.

---

#### 9.6.2 `S3_ENTITY_CONTEXT_BROKEN`

**Definition**
Emitted when S3’s overlay breaks entity consistency relative to S1/S2/6A.

**Examples**

* A mutated flow in S3 is tagged with a `party_id` / `account_id` combination that is not present in S1/S2/6A relationships.
* S3-generated “pure fraud” flows reference entities that do not exist in 6A bases.

**Obligations**

* S3 MUST fail; overlays must not violate entity graph invariants.

---

#### 9.6.3 `S3_ROUTING_CONTEXT_INCONSISTENT`

**Definition**
Emitted when S3’s overlay breaks routing consistency relative to S2 and Layer-1/3B routing.

**Examples**

* An event is routed to a `site_id` or `edge_id` that does not exist in upstream routing surfaces, or is inconsistent with the routing_universe_hash.
* A virtual campaign event uses a `routing_universe_hash` incompatible with 3B’s virtual routing universe for this world.

**Obligations**

* S3 MUST fail; routing context must remain within upstream constraints.

---

### 9.7 Temporal & structural plausibility failures

#### 9.7.1 `S3_TEMPORAL_STRUCTURE_IMPLAUSIBLE`

**Definition**
Emitted when S3’s overlay produces event sequences that violate temporal or structural rules in `fraud_overlay_policy_6B`.

**Examples**

* Events in a flow occur out of plausible order (e.g. REFUND before CLEARING when policy forbids it).
* Event timestamps far outside campaign/time windows defined for `campaign_id`.
* Negative or absurdly large time deltas between related events beyond configured tolerances.

**Obligations**

* S3 MUST fail; overlay must be behaviourally plausible.

---

### 9.8 RNG envelope & configuration failures

These concern incorrect use or configuration of RNG in S3.

#### 9.8.1 `S3_RNG_EVENT_COUNT_MISMATCH`

**Definition**
Emitted when S3’s observed RNG usage deviates from configured budgets.

**Examples**

* Fewer `rng_event_campaign_activation` events than campaign instances realised.
* More `rng_event_campaign_targeting` events than expected given `(#targets × draws_per_target)` plus tolerances.
* No RNG draws occurring where campaign configs require stochastic behaviour.

**Obligations**

* S3 MUST fail the affected scope; RNG usage must align with `fraud_rng_policy_6B`.

---

#### 9.8.2 `S3_RNG_STREAM_MISCONFIGURED`

**Definition**
Emitted when S3 cannot correctly attach to Layer-3 RNG families and streams.

**Examples**

* S3 attempts to use a RNG family not defined or reserved for S3.
* Substream keys clash, causing counter overlaps or non-monotone counters in the RNG logs.

**Obligations**

* S3 MUST fail; RNG configuration or keying must be corrected.

---

### 9.9 Output write & idempotence failures

#### 9.9.1 `S3_OUTPUT_WRITE_FAILED`

**Definition**
Emitted when S3 fails to persist one or more of its outputs (campaign catalogue or overlays) due to I/O/infrastructure errors.

**Examples**

* Filesystem/network error when writing parquet files.
* Disk quota exceeded or permission denied.

**Obligations**

* S3 MUST mark the relevant scope as FAIL.
* Orchestrators MUST treat partial outputs as invalid and either clean or safely overwrite them on retry, according to global recovery policies.

---

#### 9.9.2 `S3_IDEMPOTENCE_VIOLATION`

**Definition**
Emitted when existing S3 outputs for a given scope would be overwritten by a re-run that produces different content under the same `(manifest_fingerprint, parameter_hash, seed[, scenario_id])`.

**Examples**

* Config or code was changed without updating `parameter_hash`/`spec_version_6B`, causing different campaigns/overlays to be realised for the same world/seed/scenario.
* Upstream S1/S2 surfaces changed but S3 was re-run without treating it as a new run.

**Obligations**

* S3 MUST NOT overwrite existing outputs.
* This condition indicates contract drift; operators MUST investigate and address it (e.g. by bumping `parameter_hash` or spec version and/or re-running pipeline from upstream).

---

### 9.10 Internal / unexpected failures

#### 9.10.1 `S3_INTERNAL_ERROR`

**Definition**
Catch-all for failures not attributable to:

* precondition violations,
* incomplete sealed-inputs/config,
* schema/coverage/linkage issues,
* entity/routing/temporal inconsistencies, or
* RNG misconfiguration.

**Examples**

* Uncaught exceptions, segmentation faults, assertion failures inside S3 logic.
* Unexpected type errors in internal data structures not caught by schema validation.

**Obligations**

* S3 MUST fail the affected scope.
* Implementations SHOULD log enough context for recurring `S3_INTERNAL_ERROR` cases to be refined into more specific codes in future spec revisions.

---

### 9.11 Surfaces & propagation

For any scope where S3 fails:

* The **Layer-3 run-report** MUST record:

  * `segment = "6B"`, `state = "S3"`,
  * `manifest_fingerprint`, `seed`, and optionally `scenario_id` (if overlay-scope),
  * `status = "FAIL"`,
  * `primary_error_code` (from this section),
  * optional `secondary_error_codes` and context.

* **S4 (labelling)** MUST:

  * treat any S3 failure for a partition as a precondition failure for labelling that partition,
  * NOT label flows/events for partitions where S3 is FAIL.

* **S5 (6B validation/HashGate)** MUST:

  * treat any S3 failure as a **segment-level FAIL** for the associated `manifest_fingerprint`,
  * propagate S3’s error codes and diagnostics into its own validation bundle and summaries.

These error codes and behaviours are part of S3’s external contract and MUST be honoured by both implementers and downstream consumers.

---

## 10. Observability & run-report integration *(Binding)*

This section specifies what 6B.S3 **must expose** for observability, and **how** its status and summary must appear in the engine run-report.

There are two scopes:

* **Campaign scope:** per `(manifest_fingerprint, seed)` — for `s3_campaign_catalogue_6B`.
* **Overlay scope:** per `(manifest_fingerprint, seed, scenario_id)` — for `s3_flow_anchor_with_fraud_6B` and `s3_event_stream_with_fraud_6B`.

All requirements in this section are **binding**.

---

### 10.1 Run-report keying & status

#### 10.1.1 Campaign scope

For every `(manifest_fingerprint, seed)` for which S3 attempts campaign realisation, the Layer-3 run-report **MUST** contain exactly one entry:

* `segment` = `"6B"`
* `state`   = `"S3_campaign"`  *(name indicative but stable within the implementation)*
* `manifest_fingerprint`
* `seed`
* `status` — `"PASS"` or `"FAIL"`
* `primary_error_code` — from §9 (or `null` if `status="PASS"`)
* `secondary_error_codes` — list (possibly empty)

Plus a **campaign summary** as in §10.2.1.

#### 10.1.2 Overlay scope

For every `(manifest_fingerprint, seed, scenario_id)` for which S3 attempts overlay, the run-report **MUST** contain exactly one entry:

* `segment` = `"6B"`
* `state`   = `"S3_overlay"`
* `manifest_fingerprint`
* `seed`
* `scenario_id`
* `status` — `"PASS"` or `"FAIL"`
* `primary_error_code` — from §9 (or `null` if `status="PASS"`)
* `secondary_error_codes` — list (possibly empty)

Plus an **overlay summary** as in §10.2.2.

There MUST NOT be duplicate S3 entries for the same key in a single run-report.

---

### 10.2 Required summary metrics

#### 10.2.1 Campaign summary (per `(manifest_fingerprint, seed)`)

For each `(manifest_fingerprint, seed)` S3 processes, the run-report MUST include:

* `campaign_count_total`

  * Total number of realised campaign instances in `s3_campaign_catalogue_6B`.

* `campaign_count_by_type`

  * Map: `campaign_type → integer` counts.

* `campaigns_with_targets_total`

  * Number of campaign instances with `target_flow_count > 0` or `target_entity_count > 0`.

* `campaigns_without_targets_total`

  * Number of campaign instances with zero realised targets (e.g. inactive or infeasible).

* `campaign_target_flow_count_total`

  * Sum over all campaigns of `target_flow_count`.

* `campaign_target_event_count_total`

  * Sum over all campaigns of `target_event_count`.

For `status="PASS"` at campaign scope, S3 MUST ensure basic consistency:

* `campaign_count_total ≥ 0`.
* `campaign_target_flow_count_total ≥` actual number of overlay-tagged flows (see below) and within configured tolerances.
* `campaign_target_event_count_total ≥` actual number of overlay-tagged events and within configured tolerances.

If S3 cannot compute these metrics or finds clear inconsistencies, it MUST report `status="FAIL"` with an appropriate error code.

#### 10.2.2 Overlay summary (per `(manifest_fingerprint, seed, scenario_id)`)

For each overlay scope, the run-report MUST include at least:

**Counts & coverage**

* `flow_count_baseline`

  * Number of baseline flows in `s2_flow_anchor_baseline_6B` for this partition.

* `flow_count_with_fraud`

  * Number of flows in `s3_flow_anchor_with_fraud_6B`.

* `event_count_baseline`

  * Number of baseline events in `s2_event_stream_baseline_6B`.

* `event_count_with_fraud`

  * Number of events in `s3_event_stream_with_fraud_6B`.

* `flows_untouched_count`

  * Number of overlay flows with `origin_type="BASELINE_FLOW"` and `fraud_pattern_type="NONE"`.

* `flows_touched_count`

  * Number of overlay flows that have `origin_type="BASELINE_FLOW_MUTATED"` or are pure-fraud flows.

**Coverage flags**

* `baseline_flow_coverage_ok: boolean`

  * True iff every baseline flow_id in S2 appears in S3 (as per §8.2.3).

* `flow_event_coverage_ok: boolean`

  * True iff every S3 flow has ≥1 S3 event and every S3 event references an S3 flow.

* `campaign_linkage_ok: boolean`

  * True iff all non-null `campaign_id`s in S3 overlays exist in `s3_campaign_catalogue_6B` and fraud_pattern_type values are compatible with those campaigns.

* `entity_routing_consistency_ok: boolean`

  * True iff no entity/routing inconsistencies were detected locally (per §8.2.5).

**Fraud intensity & basic stats**

* `fraud_flow_fraction`

  * Fraction of flows in `s3_flow_anchor_with_fraud_6B` that have `fraud_pattern_type != "NONE"`.

* `fraud_event_fraction`

  * Fraction of events in `s3_event_stream_with_fraud_6B` with `is_fraud_event = true`.

* `avg_fraud_events_per_fraud_flow`

  * Average event count for flows flagged with fraud_pattern_type != "NONE"`.

* Optional per-pattern summaries:

  * e.g. `fraud_flow_count_by_pattern_type`, `fraud_event_count_by_pattern_type` (maps).

**Binding relationships**

If `status="PASS"` at overlay scope, S3 MUST ensure:

* `baseline_flow_coverage_ok == true`.
* `flow_event_coverage_ok == true`.
* `campaign_linkage_ok == true`.
* `entity_routing_consistency_ok == true`.

If any of these flags would be false, S3 MUST report `status="FAIL"` and use an appropriate primary error code (e.g. `S3_OVERLAY_BASELINE_COVERAGE_MISMATCH`, `S3_CAMPAIGN_TAGGING_INCONSISTENT`).

---

### 10.3 Logging requirements

S3 MUST emit **structured logs** for each campaign and overlay scope. At minimum:

#### 10.3.1 Campaign scope logging (`S3_campaign`)

For each `(manifest_fingerprint, seed)`:

1. **Start**

   * `event_type: "6B.S3.CAMPAIGN.START"`
   * `manifest_fingerprint`
   * `seed`
   * `sealed_inputs_digest_6B` (from S0)

2. **Template discovery & config**

   * `event_type: "6B.S3.CAMPAIGN.CONFIG_LOADED"`
   * `manifest_fingerprint`, `seed`
   * counts of templates (`template_count_total`),
   * CAS/ids of config artefacts used.

3. **Instance realisation summary**

   * `event_type: "6B.S3.CAMPAIGN.REALISED"`
   * `manifest_fingerprint`, `seed`
   * `campaign_count_total`, `campaign_count_by_type`
   * `campaigns_with_targets_total`, `campaigns_without_targets_total`
   * RELEVANT RNG counters per activation family (where available).

4. **Campaign end**

   * `event_type: "6B.S3.CAMPAIGN.END"`
   * `manifest_fingerprint`, `seed`
   * `status` — `"PASS"` / `"FAIL"`
   * `primary_error_code` (if FAIL)
   * `secondary_error_codes` (list).

#### 10.3.2 Overlay scope logging (`S3_overlay`)

For each `(manifest_fingerprint, seed, scenario_id)`:

1. **Overlay start**

   * `event_type: "6B.S3.OVERLAY.START"`
   * `manifest_fingerprint`, `seed`, `scenario_id`
   * reference to S1/S2 status (e.g. `s1_status`, `s2_status`).

2. **Baseline input summary**

   * `event_type: "6B.S3.OVERLAY.BASELINE_SUMMARY"`
   * `manifest_fingerprint`, `seed`, `scenario_id`
   * `flow_count_baseline`, `event_count_baseline`.

3. **Targeting & overlay summary**

   * `event_type: "6B.S3.OVERLAY.TARGET_SUMMARY"`
   * `manifest_fingerprint`, `seed`, `scenario_id`
   * `flows_touched_count`, `flows_untouched_count`
   * `fraud_flow_fraction`, `fraud_event_fraction`
   * `fraud_flow_count_by_pattern_type`, `fraud_event_count_by_pattern_type` (where feasible).

4. **RNG usage summary**

   * `event_type: "6B.S3.OVERLAY.RNG_SUMMARY"`
   * `manifest_fingerprint`, `seed`, `scenario_id`
   * counts per RNG family:

     * `rng_campaign_activation_events`,
     * `rng_campaign_targeting_events`,
     * `rng_overlay_mutation_events`,
   * `rng_usage_ok: boolean` (local envelope sanity).

5. **Overlay end**

   * `event_type: "6B.S3.OVERLAY.END"`
   * `manifest_fingerprint`, `seed`, `scenario_id`
   * `status` — `"PASS"` / `"FAIL"`
   * `primary_error_code`
   * `secondary_error_codes`.

These logs MUST give enough context to understand, per world/seed/scenario, which campaigns ran, which flows were touched, and where overlay failed if it did.

---

### 10.4 Metrics & SLI/monitoring

S3 SHOULD expose metrics suitable for operational monitoring. The **shape** of these metrics is binding; thresholds and dashboards are not.

Indicative metrics:

* `6B_S3_campaign_runs_total`

  * Counter; labels: `status ∈ {"PASS","FAIL"}`.

* `6B_S3_campaign_instances_total`

  * Counter; labels: `campaign_type`, `status`.

* `6B_S3_overlay_runs_total`

  * Counter; labels: `status`, `scenario_id`.

* `6B_S3_flows_touched_total`

  * Counter; labels: `scenario_id`, `fraud_pattern_type`.

* `6B_S3_events_touched_total`

  * Counter; labels: `scenario_id`, `fraud_pattern_type`.

* `6B_S3_failure_primary_code_total`

  * Counter; label: `primary_error_code`.

* `6B_S3_overlay_runtime_seconds`

  * Histogram or summary; label: `status`.

Implementations MAY expose more detailed metrics (e.g. per-segment fraud rates vs targets), but if they expose metrics with these names, they MUST adhere to the semantics above.

---

### 10.5 Downstream consumption of S3 observability

**S4 (labelling)** MUST use S3 observability as:

* A **gate**:

  * S4 MUST check the S3 overlay run-report entry for `(manifest_fingerprint, seed, scenario_id)` and ONLY proceed if `status="PASS"`.

* A **context source**:

  * S4 MAY use S3 summary stats (fraud_flow_fraction, pattern breakdowns) for sanity checks, but MUST NOT override S3’s campaign mapping.

**S5 (validation/HashGate)** MUST:

* Use S3 run-report entries and logs as evidence for its own validation:

  * If any `(manifest_fingerprint, seed)` or `(manifest_fingerprint, seed, scenario_id)` scope has S3 `status="FAIL"`, S5 MUST mark the world as FAIL.
  * Even if S3 reports `status="PASS"`, S5 MUST validate S3’s invariants using S3 outputs; any inconsistency found by S5 overrides S3’s self-reported status.

* Include pointers to key S3 metrics (e.g. realised vs target fraud rate) in the 6B validation bundle, for downstream consumption.

**4A/4B & external consumers**:

* MUST never rely on S3 alone; they gate on the 6B segment HashGate (S5).
* MAY display S3’s campaign and overlay statistics in diagnostic UIs, as long as they clearly distinguish:

  * baseline flows/events (S2),
  * overlaid flows/events (S3),
  * labels and bank-view outcomes (S4).

---

### 10.6 Traceability & audit trail

The combination of:

* S3 outputs (`s3_campaign_catalogue_6B`, `s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`),
* S1/S2/6A upstream surfaces,
* S3 run-report entries and structured logs,

MUST allow an auditor to answer, for any world/seed/scenario:

* Which campaigns were realised, with what parameters?
* Which entities/sessions/flows/events each campaign touched?
* How much behaviour was fraud/abuse vs untouched baseline?
* How much RNG was used to realise and target campaigns, and does usage match policy?

Because of this, emitting the run-report entries, logs and metrics described in this section is **not optional**: they are part of S3’s binding contract, not an implementation detail.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on how to keep S3 practical and predictable at scale. It does **not** relax any of the binding constraints in §§1–10; it only suggests sane implementation strategies inside those constraints.

---

### 11.1 Where S3 actually spends time

For a given world and run `(manifest_fingerprint, seed)` and its scenarios, S3’s cost breaks down roughly as:

1. **Config + domain prep (light/medium)**

   * Load & validate:

     * campaign templates (`fraud_campaign_catalogue_config_6B`),
     * overlay policy, RNG policy, and any tuning packs.
   * Build targeting domains per template:

     * candidate entity sets from 6A posture,
     * candidate sessions/flows from S1/S2,
     * optional event-level candidate sets.

2. **Campaign realisation (light)**

   * For each template:

     * sample the number of instances,
     * sample per-instance parameters (windows, intensities, etc.).
   * Complexity ~ O(#templates + #instances).

3. **Target selection (medium/heavy)**

   * For each campaign instance:

     * compute weights / filters over candidate entities/sessions/flows,
     * sample targets from those domains.
   * Complexity ~ O(total candidates across campaigns) with some extra cost for weighting/sampling.

4. **Overlay planning & instantiation (medium/heavy)**

   * For flows/sessions/events selected as targets:

     * compute overlay plans,
     * generate new or mutated flows/events.
   * Complexity ~ O(#targeted_flows + #overlay_events + #pure_fraud_flows).

In practice, most cost sits in:

* scanning S2 outputs (flows/events),
* building candidate sets,
* writing S3 overlays.

---

### 11.2 Parallelism and unit-of-work

S3 has two natural parallel axes:

1. **Across `seed`**

   * Campaign realisation and overlay for different seeds can run independently:

     * separate `s3_campaign_catalogue_6B` per `(seed, fingerprint)`,
     * separate overlay partitions per `(seed, fingerprint, scenario_id)`.

2. **Across `scenario_id` (overlay)**

   * Once campaign instances exist for `(manifest_fingerprint, seed)`, overlay work can be run per `(seed, scenario_id)` partition:

     * each partition reads S1/S2 for that scenario,
     * applies campaigns whose scope includes that scenario,
     * writes overlay outputs.

Within a `(seed, scenario_id)` partition:

* you can further parallelise by sharding **flows/sessions** or even campaign instances, as long as:

  * RNG keys are chosen so that reshuffling work between threads/workers does not change the sequence of draws, and
  * you merge results via deterministic sort on `[flow_id]` / `[flow_id, event_seq]`.

Rule of thumb: parallelise on **partition boundaries** and **campaign or flow shards**, never on “whatever the scheduler does” without deterministic keys/sorting.

---

### 11.3 Managing targeting domains

Target selection is where things can blow up if you’re not careful. To keep it under control:

* **Index once, reuse often**

  * Build compact indices for S1/S2/6A up front, e.g.:

    * per-merchant / per-segment flow lists,
    * entity→flows and flow→entity reverse lookups,
    * posture-based buckets (e.g. `mule_accounts`, `risky_merchants`, `tainted_devices`).

* **Filter early**

  * Apply coarse filters (region, MCC, channel, amount bands) before posture-based or more expensive checks.
  * Avoid scanning “all flows” for each campaign if you can pre-bucket flows by segments relevant to that campaign type.

* **Bound candidate sizes**

  * Campaign configs should include explicit bounds (e.g. max targeted entities/flows).
  * If a campaign template is defined too broadly (e.g. “all flows”), S3 should still narrow candidacy by random subsampling rather than building enormous candidate sets when not needed.

* **Avoid quadratic behaviour**

  * Do not repeatedly scan all flows/entities for each campaign instance.
  * Instead, precompute domains once per template, then select instance-specific targets via sampling.

---

### 11.4 RNG cost & accounting

S3’s RNG load is moderate but not negligible:

* **Campaign activation**

  * Typically O(#templates) or O(#instances) draws — very light.

* **Targeting**

  * One of the main RNG sinks:

    * draws per targeted entity/session/flow.
  * Roughly O(#targets) draws spread across `rng_event_campaign_targeting`.

* **Overlay mutations**

  * One to a few draws per mutated flow/event to decide tactics, amounts, timing tweaks, etc.

Rough heuristic:

```text
total RNG draws = O(#campaign_instances + #targets + #overlay_decisions)
```

Practical tips:

* **Keep per-decision budgets small and fixed**

  * E.g. single uniform to pick from a discrete distribution; one or two for probability thresholds and continuous distortion.
  * This simplifies envelope checks and S5 validation.

* **Avoid nested RNG loops**

  * Don’t run unbounded “while (not satisfied) draw again” loops; instead, design campaigns so either:

    * they guarantee success given domain constraints, or
    * they fail fast and flag configuration/world mismatch.

---

### 11.5 Memory footprint

Memory is driven mainly by:

* S2 flows/events in the current `(seed, scenario_id)` partition,
* targeting domains (candidate sets, target sets),
* S3 overlay surfaces while being built.

Guidance:

* **Do not mirror all S2 events in memory if not needed**

  * If only a subset of flows are fraud-affected, you can:

    * keep full metadata for flows in memory;
    * stream events, applying overlay transformations on the fly, and writing S3 events incrementally.

* **Streaming overlay where possible**

  * For each flow:

    * read its events from S2 in order (or from a forward-only iterator),
    * apply overlay (mutate/insert/delete) to produce S3 events,
    * flush S3 events to disk (or a buffer for that flow),

    without keeping every flow’s full event history in memory at once.

* **Campaign-first or flow-first?**

  * You can design S3 as:

    * **campaign-centric**: for each campaign, mark target flows and build per-flow overlay plans; then merge all campaign overlays and materialise flows/events, or
    * **flow-centric**: for each flow, determine which campaigns apply (via precomputed targeting indices) and plan overlay.

  * Either approach is fine as long as merging is deterministic and memory remains bounded. Flow-centric tends to be easier to stream without large campaign-state overhead.

---

### 11.6 I/O patterns

S3’s I/O pattern per `(seed, scenario_id)` should ideally be:

1. Read:

   * S1 sessions (smallish, one per session).
   * S1 arrival entities as needed (for entity context).
   * S2 flow anchors and event stream.

2. Write:

   * S3 event stream with overlay.
   * S3 flow anchor with overlay.

Best practices:

* **Minimal passes**

  * Aim for a single pass over S2 flows and events for the overlay, per `(seed, scenario_id)`.

* **Locality**

  * Co-locate:

    * S2 inputs (`s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`),
    * S3 outputs,
    * catalogue/config artefacts,

    in the same storage “zone” to minimise cross-region latency.

* **Batching**

  * If flows or events per partition are huge, process in batches:

    * e.g. segments of flows by `flow_id` range or by merchant,
    * but always merge results into deterministically-sorted outputs.

---

### 11.7 Scaling campaigns & patterns

As you add more campaign types and patterns:

* **Keep template count manageable**

  * A moderate number of distinct template *types* is fine; you can express variety via parameters rather than thousands of template definitions.
  * Too many microscopic template variants can explode config and complicate validation without adding much benefit.

* **Control overlap between campaigns**

  * Overlapping campaigns (multiple campaigns hitting the same flows/entities) are realistic but expensive to reason about.
  * Overlay policy should define clear rules for stacking campaigns (priority or combination rules) to avoid combinatorial explosion in overlay decisions.

* **Use stratified targeting**

  * Instead of “randomly target any flow in the world for this campaign”, prefer configurations that:

    * segment by region/MCC/segment,
    * allocate per-segment quotas,
    * then sample within those segments.

This keeps targeting more interpretable and reduces the need for global passes over all flows at once.

---

### 11.8 Monitoring S3 performance

Operators should monitor:

* **Run time per scope**

  * Campaign scope: `6B_S3_campaign_runs_total` and `6B_S3_overlay_runtime_seconds` by status.
  * Overlay scope: runtime per `(seed, scenario_id)` partition.

* **Size/complexity metrics**

  * `campaign_count_total`, `campaign_target_flow_count_total`, `campaign_target_event_count_total`.
  * `flow_count_baseline`, `flow_count_with_fraud`, `event_count_with_fraud`.

* **Fraud intensity vs expectations**

  * Observed `fraud_flow_fraction` and `fraud_event_fraction` vs configured targets in tuning packs.
  * Pattern-wise breakdowns (e.g. card-testing fraction, ATO fraction).

Red flags:

* S3 runtime scaling superlinearly with `flow_count_baseline`.
* Very high `fraud_event_fraction` or `fraud_flow_fraction` compared to config (potential misconfiguration or bug).
* Frequent failures with `S3_CAMPAIGN_INTENSITY_MISMATCH` or `S3_RNG_EVENT_COUNT_MISMATCH`.

---

### 11.9 Parallelism vs determinism

As with S1/S2:

> Parallelism is allowed; non-determinism is not.

To stay safe:

* **Always derive RNG keys from deterministic identifiers**

  * e.g. `(fingerprint, seed, template_id, campaign_index, flow_id, event_seq)`;
  * never from ephemeral thread ids or in-iteration counters that depend on ordering.

* **Always sort before emit**

  * For flows: sort by `[seed, fingerprint, scenario_id, flow_id]`.
  * For events: sort by `[seed, fingerprint, scenario_id, flow_id, event_seq]`.
  * For campaigns: sort by `[seed, fingerprint, campaign_id]`.

If your implementation can run S3 twice for the same inputs and produce logically identical outputs (same keys, same fields), you’re respecting this spec; if not, any performance trick you added is out-of-bounds and must be revisited.

---

## 12. Change control & compatibility *(Binding)*

This section defines how the **6B.S3 contract may evolve over time**, and what counts as **backwards-compatible** vs **breaking**.

It is binding on:

* authors of future S3 specs,
* implementers of S3, and
* downstream consumers (S4, S5, 4A/4B, orchestrators).

The goals:

* existing worlds/runs remain **replayable**, and
* consumers can safely rely on S3’s shapes, identity and invariants.

---

### 12.1 Versioning surfaces relevant to S3

S3 participates in the same version tracks as the rest of Segment 6B:

1. **`spec_version_6B`**

   * Behavioural contract version for the entire Segment 6B (S0–S5).
   * Stored in `s0_gate_receipt_6B`; orchestrators use it to pick the right implementation bundle.

2. **Schema packs**

   * `schemas.6B.yaml`, containing S3 anchors:

     * `#/s3/campaign_catalogue_6B`
     * `#/s3/flow_anchor_with_fraud_6B`
     * `#/s3/event_stream_with_fraud_6B`
   * `schemas.layer3.yaml`, containing layer-wide RNG/gate/validation schemas.

3. **Catalogue artefacts**

   * `dataset_dictionary.layer3.6B.yaml` entries for:

     * `s3_campaign_catalogue_6B`
     * `s3_flow_anchor_with_fraud_6B`
     * `s3_event_stream_with_fraud_6B`
   * `artefact_registry_6B.yaml` entries for the same.

**Binding rules:**

* For any S3 run, the tuple
  `(spec_version_6B, schemas.6B.yaml version, schemas.layer3.yaml version)`
  MUST be internally consistent and discoverable from catalogues.
* This document describes S3’s contract for a particular `spec_version_6B` (e.g. `"1.0.0"`). Any **incompatible** change to S3’s contract MUST bump `spec_version_6B`.

---

### 12.2 Backwards-compatible changes

A change to S3 is **backwards-compatible** if:

* Existing S3 consumers (S4, S5, tooling) built to this spec can still:

  * parse `s3_campaign_catalogue_6B`, `s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`, and
  * rely on identity, partitioning and invariants in §§4–8 without change.

Examples of **allowed** backwards-compatible changes:

1. **Additive, optional schema extensions**

   * Adding new **optional** fields to `s3_campaign_catalogue_6B`:

     * e.g. more tuning knobs, extra metrics, richer segment descriptors.
   * Adding new **optional** fields to `s3_flow_anchor_with_fraud_6B`:

     * e.g. extra overlay flags/metrics, such as “campaign_priority”, “overlap_count”.
   * Adding new **optional** fields to `s3_event_stream_with_fraud_6B`:

     * e.g. additional pattern scores, correlation ids, or per-event diagnostics.

   In all cases, existing required fields and their semantics remain unchanged.

2. **New fraud pattern / campaign types**

   * Extending enums for `campaign_type` or `fraud_pattern_type` with new values (e.g. a new abuse pattern), where:

     * existing values keep their meaning, and
     * downstream consumers either tolerate unknown values (treat as “OTHER”) or are updated in lock-step.

3. **More expressive configuration packs**

   * Extending `fraud_campaign_catalogue_config_6B` or `fraud_overlay_policy_6B` with new optional parameters that:

     * default to behaviour equivalent to this spec,
     * do not change the meaning of existing parameters, and
     * do not affect realised overlays when those new parameters are unset.

4. **Internal algorithmic optimisations**

   * Changing S3’s internal implementation (e.g. different sharding, better indexing) while:

     * preserving determinism for fixed inputs, and
     * preserving all invariants in §§6–8 (coverage, campaign linkage, entity/routing consistency, RNG envelope).

Backwards-compatible changes MAY be rolled out as a **minor** `spec_version_6B` bump (e.g. `1.0.0 → 1.1.0`), provided all binding guarantees remain intact.

---

### 12.3 Breaking changes

A change is **breaking** for S3 if it can cause:

* a consumer expecting this contract to misinterpret S3 outputs,
* a replay for the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)` to produce **different campaigns/overlays** without a deliberate version boundary, or
* S4/S5/4A/4B to violate their own contracts because S3 behaviour changed underneath them.

Breaking changes **MUST** be accompanied by a **new major** `spec_version_6B` (e.g. `1.x → 2.0.0`) and updated schemas/catalogues.

Examples of **breaking** changes:

1. **Identity / partitioning changes**

   * Changing S3 dataset partitioning:

     * e.g. dropping `seed` from `s3_campaign_catalogue_6B` partitioning,
     * changing flow/event overlays off `[seed, fingerprint, scenario_id]`.
   * Changing primary keys:

     * e.g. dropping `campaign_id` from campaign catalogue PK,
     * changing flow/event PKs (removing `flow_id` or changing `event_seq` semantics).

2. **Schema contract changes**

   * Removing or renaming **required** fields in any S3 dataset:

     * e.g. `campaign_id`, `campaign_type`, `fraud_pattern_type`, `is_fraud_event`, `origin_flow_id`.
   * Changing field types in incompatible ways:

     * string→int or int→string without a migration contract.
   * Changing semantics of key fields:

     * e.g. turning `campaign_id` from “instance id of config template” into “pattern bucket id” with different meaning;
     * redefining `fraud_pattern_type` so existing values mean something different.

3. **Relaxing invariants / coverage rules**

   * Allowing baseline flows to disappear in S3 (breaking `{flow_id(FA2)} ⊆ {flow_id(FA3)}`).
   * Allowing flows without events or events without flows in overlay surfaces.
   * Dropping the requirement that `campaign_id` references in overlays exist in the catalogue.

4. **RNG contract changes affecting reproducibility**

   * Changing which RNG families S3 uses (e.g. collapsing activation/targeting/mutation into one family) or changing their budgets in a way that:

     * changes the number of draws for fixed domains,
     * invalidates S5’s RNG envelope checks.
   * Altering substream keying in a way that produces different overlays for the same inputs without a version/config change.

5. **Changing overlay semantics without config/version boundary**

   * e.g. under the same `parameter_hash`/`spec_version_6B`:

     * changing what a given `campaign_type` does to flows,
     * changing which flows are eligible targets for the same segment definition,
     * changing fraud rate/intensity logic for existing campaigns.

Any such change MUST be treated as **breaking**, and:

* documented under a new `spec_version_6B`,
* reflected in updated `schemas.6B.yaml`/catalogues,
* accompanied by updated S4/S5 specs which explain how to interpret the new S3 outputs.

---

### 12.4 Interaction with `parameter_hash` and reproducibility

S3 is required to be deterministic for fixed inputs, including `parameter_hash`:

> For fixed upstream inputs and fixed
> `(manifest_fingerprint, parameter_hash, seed, scenario_id)`,
> S3 outputs MUST be reproducible.

Implications:

* Any change to **fraud campaign configs, overlay policies, or RNG policies** which would alter:

  * which campaign instances are realised,
  * which entities/flows are targeted,
  * or how flows/events are mutated,

  SHOULD be expressed as:

  * a new **configuration pack** → new `parameter_hash`, and/or
  * a new `spec_version_6B` if it changes the S3 contract (schemas/invariants).

* It is **not acceptable** to:

  * silently update `fraud_campaign_catalogue_config_6B` or `fraud_overlay_policy_6B` in place,
  * and re-run S3 for the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)` while expecting idempotence.

Operationally, idempotence is scoped to:

```text
(manifest_fingerprint, parameter_hash, seed, scenario_id)
```

If operators intend to change S3’s behaviour for a world, they MUST either:

* bump `parameter_hash` (new config), and/or
* treat it as a new spec version with associated validation changes.

---

### 12.5 Upstream dependency evolution

S3 depends on:

* **S1**: entity/session attachments,
* **S2**: baseline flows/events,
* **6A**: entity graph & static fraud roles,
* **Layer-3 RNG**: RNG contracts & numeric policy.

**Binding rules for upstream changes:**

1. **Upstream additive / compatible changes**

   * Upstream segments MAY add optional fields to 6A posture, S1, or S2 datasets.
   * S3 MAY exploit those fields for richer targeting/overlay, as long as:

     * S3’s own schemas and invariants remain unchanged, and
     * behaviour for unchanged config (`parameter_hash`) remains deterministic.

2. **Upstream breaking changes**

   * Changes to S1’s identity (session/arrival keys),
   * Changes to S2’s identity or invariants (flow/event PKs, coverage rules),
   * Changes to 6A’s entity ID semantics or posture interpretations,

   are **breaking** for S3. In such cases:

   * S3 MUST be updated to consume new upstream contracts, and
   * this S3 spec (and `spec_version_6B`) MUST be bumped, ideally in lock-step with S1/S2/6A specs.

3. **New upstream fraud-adjacent segments**

   * If new segments/layers provide additional fraud signal or context (e.g. a “dynamic posture” layer), S3 MAY treat them as `OPTIONAL` inputs in `sealed_inputs_6B` (used only for enrichment) without breaking existing behaviour.
   * If S3’s correctness depends on such new segments being present, that is a breaking change and MUST be expressed via a new spec version and updated preconditions.

---

### 12.6 Co-existence and migration

To support gradual rollout and historical replay:

1. **Co-existence of S3 contracts**

   * Orchestrators MUST choose one `spec_version_6B` per **deployment / world** when running S3.
   * Different S3 spec versions MUST NOT write to the same dataset ids for the same `(manifest_fingerprint, seed, scenario_id)` concurrently.

   If you need side-by-side S3 versions:

   * You SHOULD use new dataset ids (e.g. `s3_flow_anchor_with_fraud_6B_v2`) or separate catalogue entries, with clear documentation.

2. **Reading old S3 outputs**

   * Newer tooling/S5 MAY read older S3 outputs for diagnostics, but MUST NOT assume they comply with newer invariants unless explicitly migrated.
   * Any compatibility layer that maps old outputs into the new contract MUST be documented and versioned separately.

3. **Migration strategy**

   When bumping to a new S3 contract:

   * Decide whether to re-run S3 for existing worlds, or
   * Freeze old worlds under old S3 outputs and treat them as “legacy S3 vX” in tooling and validation.

   The migration plan SHOULD be explicit in higher-level change notes even if it’s not encoded here.

---

### 12.7 Non-negotiable stability points for S3

For the lifetime of this `spec_version_6B`, the following aspects of S3 are **stable** and MUST NOT change without a **major** version bump:

* S3 produces exactly three datasets:

  * `s3_campaign_catalogue_6B` (per `(seed, fingerprint)`),
  * `s3_flow_anchor_with_fraud_6B` (per `(seed, fingerprint, scenario_id)`),
  * `s3_event_stream_with_fraud_6B` (per `(seed, fingerprint, scenario_id)`).

* Partitioning and PKs MUST remain:

  * `campaign_catalogue`: `[seed, fingerprint, campaign_id]` with partitioning `[seed, fingerprint]`.
  * `flow_anchor_with_fraud`: `[seed, fingerprint, scenario_id, flow_id]` with partitioning `[seed, fingerprint, scenario_id]`.
  * `event_stream_with_fraud`: `[seed, fingerprint, scenario_id, flow_id, event_seq]` with partitioning `[seed, fingerprint, scenario_id]`.

* Baseline coverage MUST hold:

  * every S2 flow appears in S3 (either untouched or mutated),
  * S3 may add new flows but not drop baseline flows entirely.

* Campaign identity MUST remain stable:

  * every non-null `campaign_id` in overlays MUST map to exactly one row in the campaign catalogue for the same `(seed, fingerprint)`.

* Overlay semantics MUST preserve upstream facts:

  * S3 NEVER mutates 6A/S1/S2 data in place; it only emits overlay surfaces referencing them.
  * Entity and routing invariants from upstream MUST continue to hold in S3 outputs.

Any change that relaxes or alters these stability points MUST:

* be treated as a breaking change,
* be guarded by a new major `spec_version_6B`, and
* come with correspondingly updated S4/S5 specs and migration guidance.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the shorthand and symbols used in the 6B.S3 spec. It is **informative** only; if anything here conflicts with §§1–12, the binding sections win.

---

### 13.1 Identity & axes

* **`manifest_fingerprint` / `fingerprint`**
  Sealed world snapshot id. S3’s campaign catalogue and overlays are always scoped to this.

* **`seed`**
  Run axis shared with 5B, 6A, S1, S2. S3’s campaign catalogue is per `(manifest_fingerprint, seed)`, and overlays are per `(manifest_fingerprint, seed, scenario_id)`.

* **`scenario_id`**
  Scenario axis from 5A/5B (e.g. baseline/stress scenarios). S3 overlays are partitioned by `scenario_id` alongside `seed` and `manifest_fingerprint`.

* **`parameter_hash`**
  Hash of the 6B behavioural config pack (including S3’s campaign/overlay/RNG policies). S3 must be deterministic for fixed `(manifest_fingerprint, parameter_hash, seed, scenario_id)`.

* **`campaign_id`**
  Opaque identifier for a realised campaign instance, unique within `(seed, manifest_fingerprint)`.

* **`flow_id`**
  Opaque identifier for a flow/transaction, unique within `(seed, manifest_fingerprint, scenario_id)` in both S2 and S3.

* **`event_seq`**
  Integer defining strict order of events within a flow in S2/S3; unique per `(seed, manifest_fingerprint, scenario_id, flow_id)`.

---

### 13.2 Dataset shorthands

Upstream (for context):

* **`AE6B`**
  `s1_arrival_entities_6B` — arrival→entity→session mapping.

* **`SESS`**
  `s1_session_index_6B` — session index.

* **`FA2`**
  `s2_flow_anchor_baseline_6B` — S2 baseline flow anchor.

* **`EV2`**
  `s2_event_stream_baseline_6B` — S2 baseline event stream.

S3 outputs:

* **`CC3`**
  `s3_campaign_catalogue_6B` — realised campaign instances.

* **`FA3`**
  `s3_flow_anchor_with_fraud_6B` — flow-level overlay (baseline + fraud/abuse overlay).

* **`EV3`**
  `s3_event_stream_with_fraud_6B` — event-level overlay (baseline + fraud/abuse overlay).

These names are just shorthand for the spec; canonical ids live in the dataset dictionary.

---

### 13.3 Keys & relationships

* **Campaign PK**

  ```text
  (seed, manifest_fingerprint, campaign_id)
  ```

* **Flow PK (S3)**

  ```text
  (seed, manifest_fingerprint, scenario_id, flow_id)
  ```

* **Event PK (S3)**

  ```text
  (seed, manifest_fingerprint, scenario_id, flow_id, event_seq)
  ```

* **Origin keys (baseline → overlay link):**

  * `origin_flow_id` — baseline `flow_id` from S2 (for mutated flows/events).
  * `origin_event_seq` — baseline `event_seq` from S2 (for mutated events).

Expected relationships:

* Every baseline flow_id in `FA2` must appear in `FA3` (unchanged or mutated).
* Every `flow_id` in `FA3` must have ≥1 event in `EV3`.
* Every non-null `(origin_flow_id, origin_event_seq)` in `EV3` must reference a unique event in `EV2`.
* Every non-null `campaign_id` in `FA3`/`EV3` must reference a row in `CC3`.

---

### 13.4 Entity & routing context (shorthand)

Entity IDs (owned by 6A, reused in S1/S2/S3):

* **`party_id`** — primary key in `s1_party_base_6A`.
* **`account_id`** — primary key in `s2_account_base_6A`.
* **`instrument_id`** — primary key in `s3_instrument_base_6A`.
* **`device_id`** — primary key in `s4_device_base_6A`.
* **`ip_id`** — primary key in `s4_ip_base_6A`.

Routing-related fields (owned by Layer-1/2/3B, propagated into S2 and S3):

* **`site_id`** — physical outlet/site id from `site_locations`.
* **`edge_id`** — virtual/CDN edge id from 3B.
* **`is_virtual`** — flag indicating virtual vs physical flows.
* **`routing_universe_hash`** — hash tying flows/events to the routing universe (3A/3B).

S3 uses these fields but does not own or redefine their semantics.

---

### 13.5 Campaign & overlay metadata

Common overlay/campaign fields:

* **`campaign_type`**
  High-level type of campaign, e.g. `CARD_TESTING`, `ATO`, `REFUND_ABUSE`, `COLLUSION`.

* **`fraud_pattern_type`**
  Per-flow/event pattern tag (often the same enum family as `campaign_type` but may be more fine-grained, e.g. `CARD_TESTING_SMALL_AMOUNTS`, `ATO_PASSWORD_SPRAY`, `NONE`).

* **`origin_type`**
  E.g.:

  * `BASELINE_FLOW` — baseline flow untouched by overlay.
  * `BASELINE_FLOW_MUTATED` — baseline flow with overlay.
  * `PURE_FRAUD_FLOW` — overlay-only flow with no baseline counterpart.

* **`is_fraud_event`**
  Boolean flag indicating whether a given event is part of the fraudulent/abusive behaviour (vs a legit event in a flow touched by a campaign).

* **Overlay flags** (examples, exact list lives in schema):

  * `amount_modified_flag`
  * `timestamp_modified_flag`
  * `device_swapped_flag`
  * `routing_anomalous_flag`
  * `extra_auths_flag`

These fields are used in S4/S5 to understand what changed relative to baseline.

---

### 13.6 RNG families (names indicative)

S3 uses Layer-3 Philox RNG via S3-specific families (exact details live in the RNG policy):

* **`rng_event_campaign_activation`**
  Used for:

  * sampling number of campaign instances per template,
  * sampling per-instance parameters (time windows, intensities).

* **`rng_event_campaign_targeting`**
  Used for:

  * sampling target entities/sessions/flows/events per campaign instance,
  * e.g. which cards/accounts/merchants to attack.

* **`rng_event_overlay_mutation`**
  Used for:

  * per-target overlay decisions: whether/how to mutate flows/events,
  * e.g. number of extra auths, degree of amount skew, timing jitter.

S3 must not use RNG families reserved for other states, and all RNG usage must be reflected in `fraud_rng_policy_6B`.

---

### 13.7 Error code prefix (S3)

All S3 error codes from §9 follow the prefix:

* **`S3_*`**

Examples (see §9 for semantics):

* `S3_PRECONDITION_S0_S1_S2_FAILED`
* `S3_PRECONDITION_SEALED_INPUTS_INCOMPLETE`
* `S3_PRECONDITION_RNG_OR_CAMPAIGN_POLICY_INVALID`
* `S3_CAMPAIGN_CATALOGUE_SCHEMA_VIOLATION`
* `S3_CAMPAIGN_REALISATION_FAILED`
* `S3_CAMPAIGN_DUPLICATE_ID`
* `S3_OVERLAY_FLOW_EVENT_SCHEMA_VIOLATION`
* `S3_OVERLAY_FLOW_EVENT_MISMATCH`
* `S3_OVERLAY_BASELINE_COVERAGE_MISMATCH`
* `S3_CAMPAIGN_TAGGING_INCONSISTENT`
* `S3_CAMPAIGN_INTENSITY_MISMATCH`
* `S3_TARGET_SELECTION_INCONSISTENT`
* `S3_ENTITY_CONTEXT_BROKEN`
* `S3_ROUTING_CONTEXT_INCONSISTENT`
* `S3_TEMPORAL_STRUCTURE_IMPLAUSIBLE`
* `S3_RNG_EVENT_COUNT_MISMATCH`
* `S3_RNG_STREAM_MISCONFIGURED`
* `S3_OUTPUT_WRITE_FAILED`
* `S3_IDEMPOTENCE_VIOLATION`
* `S3_INTERNAL_ERROR`

---

### 13.8 Miscellaneous

* **“Baseline” (S2)**
  Refers to flows/events from S2 (`FA2`, `EV2`) under the all-legit assumption.

* **“Overlay” (S3)**
  Refers to the fraud/abuse modifications S3 builds on top of baseline flows/events, resulting in `FA3` and `EV3`.

* **“Pure fraud flows”**
  Flows that exist only in S3 (no baseline `flow_id` match), typically representing dark fraud (e.g. pure card tests) injected by campaigns.

* **“Canvas”**
  Informal term for the behavioural surface S4 will label; in this spec, that is S3’s overlays (`s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`), plus campaign catalogue context.

These shorthands are here only to keep the spec readable; they don’t add any new obligations beyond what’s already in the binding sections.

---