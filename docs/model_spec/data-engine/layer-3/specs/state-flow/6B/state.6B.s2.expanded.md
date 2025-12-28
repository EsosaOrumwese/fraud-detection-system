# 6B.S2 — Baseline transactional flow synthesis (Layer-3 / Segment 6B)

## 1. Purpose & scope *(Binding)*

6B.S2 is the **baseline transactional flow synthesis** state for Segment 6B.

Given a sealed world `manifest_fingerprint` and a specific `(parameter_hash, seed, scenario_id)`:

* S1 has already said **who** is acting and **which arrivals belong together**:

  * `s1_arrival_entities_6B` — one row per arrival with attached `{party, account, instrument, device, ip, session_id}`.
  * `s1_session_index_6B` — one row per session with time window and coarse aggregates.

S2’s job is to take that information and construct **baseline transactional flows** that represent what would happen in an “all-legit” universe:

* It expands arrivals/sessions into **structured flows** of events:

  * authorisation attempts, auth responses, step-up / challenge events,
  * clearing/settlement events,
  * non-fraud refunds and simple reversals where behaviourally appropriate.
* It produces a **flow anchor** per transaction/flow, capturing:

  * entity context (party, account, instrument),
  * core amounts and currencies,
  * key timestamps (first_auth_ts, final_auth_ts, clear_ts, refund_ts…),
  * a baseline outcome (e.g. authorised then cleared, declined, refunded), **without** any fraud or abuse semantics.

S2 is the unique place in the engine where:

> **Attached arrivals + sessions** are lifted into **time-ordered flows of business events**, under the assumption that all behaviour is legitimate.

These baseline flows form the **canvas** that later states will use:

* **S3** overlays fraud/abuse campaigns and corrupts some baseline flows (adding extra events, changing patterns, creating anomalous flows).
* **S4** assigns truth labels and bank-view outcomes over the **final** (S2+S3) flows.

### In-scope responsibilities

Within this segment, S2 is responsible for:

* **Flow definition:**

  * Deciding, for each session (and its arrivals), how many **flows** exist and how arrivals map to those flows, according to 6B’s flow-shape priors (e.g. one flow per checkout vs multiple orders in a single visit).
  * Defining a stable `flow_id` per `(seed, manifest_fingerprint, scenario_id)` and mapping each flow back to:

    * one or more arrivals, and
    * exactly one session in `s1_session_index_6B`.

* **Event-level baseline behaviour:**

  * For each flow, constructing a **sequence of events** that represents plausible, non-fraud interaction with the bank’s systems, including:

    * auth requests and responses (including deterministic retry patterns where configured),
    * optional step-up / 3DS / challenge events according to channel/merchant/policy,
    * clearing/settlement events,
    * simple refunds and reversals consistent with legitimate customer behaviour.
  * Assigning timestamps, amounts, currencies and routing context to each event, consistent with:

    * the underlying arrivals and sessions,
    * 6A entity attributes and 5B routing,
    * 6B’s flow-shape and amount models.

* **Baseline outcome surface:**

  * For each flow, recording a **baseline outcome** under all-legit assumptions, e.g.:

    * authorised and settled,
    * declined at auth and not retried,
    * authorised, settled, then legitimately refunded.
  * These baseline outcomes are later used by S3 and S4 to decide how fraud and disputes distort or override them.

* **Producing internal plan surfaces:**

  * Emitting `s2_flow_anchor_baseline_6B` (one row per flow) and
    `s2_event_stream_baseline_6B` (one row per event) as internal Layer-3 plan surfaces that S3 and S4 can depend on.

### Out-of-scope responsibilities

S2 is explicitly **not** allowed to:

* **Change upstream identity or attachments:**

  * It MUST NOT create, delete or modify arrivals in `arrival_events_5B` or the enriched arrival records in `s1_arrival_entities_6B`.
  * It MUST NOT change entity attachments (`party_id`, `account_id`, `instrument_id`, `device_id`, `ip_id`) or `session_id` assigned by S1.

* **Introduce fraud or abuse:**

  * It MUST NOT inject fraud patterns, card testing, ATO, collusion, refund abuse, or any other adversarial behaviour.
  * It MUST NOT produce fraud labels, chargebacks, disputes, or any “bank-view” classifications; those are S3/S4 responsibilities.

* **Redefine upstream routing or time:**

  * It MUST NOT alter routing fields (`site_id`, `edge_id`, `is_virtual`, `routing_universe_hash`) established by Layer-1/5B, nor move events outside the plausible windows implied by S1’s sessions and 5B’s timestamps.
  * It MAY derive intra-flow timing from S2 priors but MUST remain consistent with the arrival and session windows.

* **Perform segment-level validation or HashGate:**

  * It does not build validation bundles or `_passed.flag`; that is the job of the 6B validation state.
  * It does not re-validate S0 or S1; it trusts their gates and invariants.

### Relationship to the rest of Segment 6B and the engine

Within Segment 6B:

* **Upstream:**

  * S0 has already frozen the behavioural input universe and verified that all required upstream segments are PASS.
  * S1 has attached arrivals to entities and grouped them into sessions, providing a clean “who + session” view.

* **S2:**

  * Turns that “who + session” view into **synthetic, all-legit flows and events**, suitable for downstream fraud overlay and labelling.

* **Downstream:**

  * S3 will read S2’s flows and event stream as **the** baseline canvas to overlay fraud and abuse campaigns.
  * S4 will assign truth and bank-view labels over the S2+S3 event stream and flow anchors.
  * The 6B validation/HashGate state will check that S2’s flows and events obey their contracts and align with S1 and upstream layers.

If S2 is implemented according to this specification:

* Every arrival/session in S1 will have corresponding flows and events that represent realistic, non-fraud transactional behaviour.
* Downstream states will not need to “invent” flow structure themselves; they can focus solely on how fraud and outcomes distort those baseline flows.

---

## 2. Preconditions & upstream gates *(Binding)*

This section defines **what must already be true** before 6B.S2 is allowed to run, and which upstream gates it **MUST** honour.

S2 is evaluated per triple:

```text
(manifest_fingerprint, seed, scenario_id)
```

If **any** precondition in this section is not satisfied for a given triple, then S2 **MUST NOT** build flows for that partition and **MUST** fail fast with a precondition error (to be defined in S2’s failure section).

---

### 2.1 6B.S0 gate MUST be PASS (world-level)

For a given `manifest_fingerprint`, S2 **MUST NOT** run unless 6B.S0 has already succeeded for that fingerprint.

Before doing any data-plane work, S2 MUST:

1. Locate `s0_gate_receipt_6B` for the target `manifest_fingerprint` using `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml`.
2. Validate the receipt against `schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B`.
3. Confirm (via the run-report or equivalent control-plane API) that 6B.S0 is recorded as `status="PASS"` for this `manifest_fingerprint`.

If:

* `s0_gate_receipt_6B` is missing or schema-invalid, or
* the run-report does not show S0 as PASS,

then S2 **MUST** treat this as a hard precondition failure and MUST NOT read S1 outputs or any upstream data-plane tables for that world.

S2 is **not** allowed to reconstruct or bypass S0’s sealed-inputs universe.

---

### 2.2 Upstream HashGates: transitive requirement

S0 has already verified the HashGates of required upstream segments:

* Layer-1: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
* Layer-2: `5A`, `5B`
* Layer-3: `6A`

S2 does **not** re-verify these bundles, but it **MUST** respect their recorded status in `s0_gate_receipt_6B.upstream_segments`:

* For each `SEG ∈ { "1A","1B","2A","2B","3A","3B","5A","5B","6A" }`, S2 MUST check:

  ```text
  s0_gate_receipt_6B.upstream_segments[SEG].status == "PASS"
  ```

* If **any** required upstream segment has `status != "PASS"`, S2 MUST fail with a precondition error and MUST NOT attempt flow synthesis.

S2 MUST NOT attempt to “fix” or ignore a non-PASS upstream segment. If S0 says the world is not sealed for that segment, S2 cannot run.

---

### 2.3 S1 MUST be PASS for `(seed, scenario_id)`

S2 builds flows **on top of** S1. For each `(manifest_fingerprint, seed, scenario_id)`:

* S2 MUST NOT run unless 6B.S1 has successfully completed for that same triple.

Binding checks:

1. Check the Layer-3 run-report for an entry:

   ```text
   segment = "6B", state = "S1",
   manifest_fingerprint, seed, scenario_id
   ```

   with `status = "PASS"`.

2. Confirm that both S1 outputs are present and schema-valid for that partition:

   * `s1_arrival_entities_6B`
   * `s1_session_index_6B`

   using their declared `schema_ref`s in `schemas.6B.yaml`.

If:

* S1 is `status="FAIL"` or missing for `(manifest_fingerprint, seed, scenario_id)`, or
* either S1 dataset is missing or fails schema validation,

then S2 MUST treat this as a hard precondition failure for that partition and MUST NOT attempt to generate flows.

S2 MUST NOT bypass S1 by reading `arrival_events_5B` directly and inventing its own entity/session assignments.

---

### 2.4 Required sealed-inputs entries for S1 & S2

All datasets that S2 reads MUST be discoverable via `sealed_inputs_6B` for the target `manifest_fingerprint`.

Before processing any `(seed, scenario_id)` partition, S2 MUST:

1. Load `sealed_inputs_6B` for `manifest_fingerprint` and validate it against `schemas.layer3.yaml#/gate/6B/sealed_inputs_6B`.

2. Confirm that the following artefacts exist as rows in `sealed_inputs_6B` with:

   * `status = "REQUIRED"`
   * `read_scope = "ROW_LEVEL"`

   **Required 6B / S1 surfaces**

   * `owner_layer = 3`, `owner_segment = "6B"`, `manifest_key = "s1_arrival_entities_6B"`
   * `owner_layer = 3`, `owner_segment = "6B"`, `manifest_key = "s1_session_index_6B"`

   **Required 6B / S2 config surfaces**

   At minimum (names indicative; exact ids from the 6B contract):

   * `flow_shape_policy_6B` or equivalent — flow structure priors.
   * `amount_model_6B` — transaction amount/currency models.
   * `flow_rng_policy_6B` — RNG family/budget config for S2.

   Each of these MUST be present with `status="REQUIRED"` (or whatever the 6B spec declares for this version) and a valid `schema_ref` into `schemas.6B.yaml` / `schemas.layer3.yaml`.

3. Verify that for those rows:

   * `schema_ref` resolves into the appropriate schema pack.
   * `partition_keys` and `path_template` fields are consistent with 6B’s dictionary/registry.

If any required row is missing or malformed, S2 MUST fail with a precondition error and MUST NOT proceed to read data-plane rows.

Optional context artefacts (e.g. 5A intensity surfaces, 5B grouping grids) MAY appear with `status="OPTIONAL"` and `read_scope` either `ROW_LEVEL` or `METADATA_ONLY`. Their presence is **not** a precondition for S2 to run.

---

### 2.5 Partition coverage: consistency with S1 and 5B

S2 operates on the same `(seed, scenario_id)` partitions as S1 and 5B:

For a given `(manifest_fingerprint, seed, scenario_id)`:

1. Using the S1 dictionary entries and `sealed_inputs_6B`, S2 MUST confirm that:

   * A partition of `s1_arrival_entities_6B` exists at:

     ```text
     seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}
     ```

   * A partition of `s1_session_index_6B` exists at the same axes.

2. S2 MAY (optionally) confirm that `arrival_events_5B` has a partition for the same `(seed, fingerprint, scenario_id)`, but S1’s outputs are the canonical reference — S2 MUST NOT try to “fill in” partitions that S1 did not produce.

If S1 outputs are missing for a `(seed, scenario_id)` where 5B has arrivals, S2 MUST treat that as a precondition failure for that partition (S1 has not completed correctly).

**Zero-arrival semantics:**

* If S1 PASSed with **zero arrivals** in `s1_arrival_entities_6B` for a partition (e.g. legitimate scenario with no traffic), S2 MAY treat this as a trivial PASS:

  * produce zero flows and zero events for that partition, or
  * emit no S2 files for that partition but still record S2 `status="PASS"` with zero counts.

S2’s spec will choose one behaviour and MUST apply it consistently; in either case, S2 MUST NOT synthesize flows for arrivals that don’t exist.

---

### 2.6 Layer-3 RNG & numeric environment

S2 is an RNG-consuming state. Before any flow synthesis, S2 MUST ensure that:

* The Layer-3 Philox RNG configuration exists and is valid (e.g. as declared in `schemas.layer3.yaml` and the Layer-3 RNG policy artefacts).
* The S2-specific RNG policy (`flow_rng_policy_6B` or equivalent) is present in `sealed_inputs_6B` and schema-valid, including:

  * the RNG family names allocated to S2 (e.g. `rng_event_flow_shape`, `rng_event_event_timing`, `rng_event_amount_draw`),
  * per-family budgets (`blocks`, `draws` per event),
  * any substream keying scheme.

If RNG policy is missing or invalid for S2, S2 MUST fail with an RNG precondition error and MUST NOT attempt to generate flows.

---

### 2.7 Prohibited partial / speculative invocations

S2 MUST NOT be invoked in the following situations:

* **Before** S0 is PASS for `manifest_fingerprint`.
* **Before** S1 is PASS for the target `(manifest_fingerprint, seed, scenario_id)`.
* With a manually specified set of inputs that bypass `sealed_inputs_6B`.
* When required S1 outputs or S2 config artefacts are missing from `sealed_inputs_6B`.
* Against a world where any required upstream HashGate (`1A`–`3B`, `5A`, `5B`, `6A`) is not PASS according to `s0_gate_receipt_6B`.
* In a “speculative” or “best effort” mode where S2 is allowed to proceed under missing or non-PASS preconditions.

If any of these conditions hold, **the correct behaviour is for S2 to fail early** for that `(manifest_fingerprint, seed, scenario_id)` with an appropriate precondition error, and to produce no S2 outputs for that partition.

These preconditions are **binding**: any conformant implementation of 6B.S2 MUST enforce them before performing any flow planning or event synthesis.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **exactly what 6B.S2 may read** and what each input is the **authority for**. Anything outside these boundaries is out of scope for S2 and **MUST NOT** be touched.

S2 is a **data-plane + RNG-consuming** state: it reads rows from its authorised inputs, uses 6B policies to synthesise flows/events, and writes its own plan surfaces. It MUST NOT mutate any upstream or S1 datasets.

---

### 3.1 Engine parameters (implicit inputs)

S2 is evaluated over:

* `manifest_fingerprint` — sealed world snapshot.
* `seed` — run axis shared with 5B and 6A.
* `scenario_id` — arrival scenario (from 5A/5B).
* `parameter_hash` — 6B behavioural config pack identifier.

These are supplied by orchestration and/or derived from `sealed_inputs_6B` + upstream dictionaries. S2 **MUST NOT** infer or modify them from wall-clock time or environment.

---

### 3.2 6B control-plane inputs (S0 outputs)

S2 depends on the S0 outputs as control-plane authority:

1. **`s0_gate_receipt_6B`**
   Authority for:

   * Which upstream segments are PASS for this `manifest_fingerprint`.
   * Which `parameter_hash` and `spec_version_6B` S2 must honour.
   * The `sealed_inputs_digest_6B` that summarises S2’s input universe.

   S2 MUST NOT run if this receipt is missing, schema-invalid, or not marked PASS in the run-report.

2. **`sealed_inputs_6B`**
   Authority for:

   * Which artefacts S2 is allowed to read.
   * Where they live (`path_template`, `partition_keys`).
   * How they should be interpreted (`schema_ref`, `role`, `status`, `read_scope`).

   S2 MUST:

   * Resolve all dataset locations through `sealed_inputs_6B` + the owning segment’s dictionary/registry.
   * NEVER construct dataset paths by hand.
   * NEVER read artefacts that are not listed in `sealed_inputs_6B`.

---

### 3.3 Primary data-plane inputs (S1 outputs)

S2’s **main inputs** are the S1 plan surfaces. They are authoritative for:

* which entities each arrival is attached to, and
* how arrivals are grouped into sessions.

These MUST appear in `sealed_inputs_6B` with `owner_layer=3`, `owner_segment="6B"`, `status="REQUIRED"`, `read_scope="ROW_LEVEL"`:

1. **`s1_arrival_entities_6B`**

   * One row per arrival for the `(seed, manifest_fingerprint, scenario_id)` domain.
   * Contains:

     * arrival identity and routing (inherited from 5B),
     * entity attachments: `{party_id, account_id, instrument_id?, device_id, ip_id}`,
     * `session_id` assigning the arrival to a session.

   **Authority:** this is the **only** source S2 may use for:

   * mapping arrivals to entities,
   * mapping arrivals to sessions.

   S2 MUST NOT:

   * change entity IDs for an arrival,
   * change `session_id`,
   * create or delete arrival rows.

2. **`s1_session_index_6B`**

   * One row per session for the same `(seed, manifest_fingerprint, scenario_id)` domain.
   * Contains:

     * `session_id`,
     * `session_start_utc`, `session_end_utc`,
     * `arrival_count`,
     * optional entity/session-level context.

   **Authority:** this is the **only** source S2 may use for:

   * session existence and identity,
   * session-level time windows and baseline aggregates.

   S2 MAY derive additional flow-level aggregates, but MUST NOT redefine session boundaries or `session_id`s.

Together, S1 outputs are S2’s **starting canvas**: “here are the arrivals, here’s who did them, and here’s how they cluster into sessions.”

---

### 3.4 Optional upstream context inputs (5B, 6A, others)

S2 MAY use some upstream artefacts as **context** or for integrity checks. These must be listed in `sealed_inputs_6B` with appropriate `status` and `read_scope`.

1. **Arrival skeleton (Layer-2 / 5B)**

   * **`arrival_events_5B`** (role: `arrival_stream`, typically `read_scope="METADATA_ONLY"` for S2).

   **Authority:**

   * Upstream definition of arrival identity, timestamps, and routing.
   * S2 MUST treat `arrival_events_5B` as the ultimate source of truth for arrival identity/time/routing if it needs to cross-check S1, but MUST NOT:

     * re-attach entities directly to 5B arrivals,
     * bypass S1’s mapping.

   S2 is not required to read rows from `arrival_events_5B` if all required information is carried through S1 outputs.

2. **Entity attributes & posture (Layer-3 / 6A)**

   S2 may optionally re-join static attributes or posture for richer flow models, using:

   * `s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`,
   * `s4_device_base_6A`, `s4_ip_base_6A`,
   * `s5_*_fraud_roles_6A`.

   These should be in `sealed_inputs_6B` with `status="OPTIONAL"` or `status="REQUIRED"` and appropriate `read_scope` (often `ROW_LEVEL`).

   **Authority:**

   * Existence and static attributes of entities (party/account/instrument/device/IP).
   * Static fraud posture.

   S2 MAY use these for:

   * choosing flow shapes or amounts based on entity type/posture,
   * validation cross-checks.

   S2 MUST NOT:

   * invent new entities,
   * change any 6A attributes or posture,
   * change S1’s entity attachments.

3. **Intensity / routing context (Layer-2 / 5A, 2B, 3B)**

   Optionally, S2 may consume:

   * 5A intensity surfaces (`merchant_zone_*_5A`) as context features (e.g. high vs low traffic times).
   * 2B routing plan surfaces, 3B virtual routing policy, etc. for extra realism in timestamping events.

   These MUST be listed in `sealed_inputs_6B` with `status="OPTIONAL"` and appropriate `read_scope`. They are **context only**: S2 MUST NOT use them to change upstream arrivals or routing, only to inform timing/shape of flows.

---

### 3.5 6B configuration & policy inputs for S2

S2’s behaviour is driven by 6B configuration artefacts that MUST be:

* registered in the 6B dictionary/registry,
* listed in `sealed_inputs_6B` with appropriate roles and `status`,
* schema-validated before use.

Indicative set (names to match your contract files):

1. **Flow-shape policy pack** (e.g. `flow_shape_policy_6B`)

   Role: `behaviour_prior` / `flow_policy`.
   Authority for:

   * how many flows per session (distribution over order counts per visit),
   * number and pattern of auth attempts, retries, and step-ups per flow,
   * probabilities of basic refunds/reversals (non-fraud) per merchant/channel/segment.

2. **Amount model pack** (e.g. `amount_model_6B`)

   Role: `behaviour_prior` / `amount_model`.
   Authority for:

   * distributions of transaction amounts and currencies given:

     * party/account/instrument profile,
     * merchant/segment,
     * scenario.

3. **Timing & spacing policy** (could be part of the flow-shape pack or separate)

   Role: `behaviour_prior` / `timing_policy`.
   Authority for:

   * distributions of time gaps between events within a flow (auth→auth, auth→clear, clear→refund),
   * constraints tying those gaps to 5B’s arrival timestamps and S1’s session windows.

4. **S2 RNG policy pack** (e.g. `flow_rng_policy_6B`)

   Role: `rng_policy`.
   Authority for:

   * RNG family names used by S2 (`rng_event_flow_shape`, `rng_event_event_timing`, `rng_event_amount_draw`, etc.),
   * per-family budgets (how many draws per decision),
   * allowed substream key structure (which axes feed into RNG keys).

Binding rules for config inputs:

* S2 MUST read and validate these packs via their `schema_ref`s.
* S2 MUST NOT embed additional behavioural rules or hard-coded numbers outside these packs; all stochastic flow-shape / amount / timing decisions must be parameterised by them.
* If a config pack is marked `status="REQUIRED"` in `sealed_inputs_6B`, its absence or schema failure MUST cause S2 to fail preconditions for the partition/world.

---

### 3.6 Authority boundaries & prohibitions

To make boundaries explicit:

* **Authority for arrivals & routing (when/where traffic happened)**

  * 5B’s `arrival_events_5B` is the ultimate authority on arrival identity, timestamps and routing; S1’s arrivals copy that state and add entity/session context.
  * S2 MUST NOT:

    * create or delete arrivals,
    * alter arrival timestamps or routing fields,
    * introduce new arrival keys.

* **Authority for entity attachment & sessions**

  * `s1_arrival_entities_6B` is the sole authority for which entities are involved in each arrival and which `session_id` it belongs to.
  * `s1_session_index_6B` is the sole authority for session identity and time windows.
  * S2 MUST NOT:

    * change any `*_id` or `session_id` in S1,
    * redefine which arrivals belong to which sessions.

* **Authority for entity existence & posture**

  * 6A bases & posture surfaces remain the single source of truth for entity existence and static attributes/roles.
  * S2 MAY re-join these for context but MUST NOT:

    * add new entities,
    * alter attributes or posture,
    * contradict link relationships.

* **Authority for “what S2 may read”**

  * `sealed_inputs_6B` is the exclusive inventory of inputs.
  * S2 MUST NOT:

    * read datasets not listed in `sealed_inputs_6B`,
    * exceed `read_scope` (e.g. read rows from artefacts marked `METADATA_ONLY`).

* **Authority for S2’s behaviour**

  * 6B’s flow/amount/timing/RNG policy packs are the only authority for how S2 shapes flows.
  * S2 MUST NOT change gating or HashGate semantics, which belong to S0 and the 6B validation state (S5).

Anything that attempts to:

* bypass `sealed_inputs_6B`,
* recontract arrival→entity/session mappings,
* mutate upstream data, or
* introduce new identity axes,

is outside S2’s authority and MUST be treated as a violation of this specification.

---

## 4. Outputs (datasets) & identity *(Binding)*

6B.S2 produces two **plan surfaces** for Segment 6B:

1. `s2_flow_anchor_baseline_6B` — one row per **baseline flow/transaction**.
2. `s2_event_stream_baseline_6B` — one row per **event** in those flows.

These are **internal Layer-3 / 6B datasets**:

* not cross-layer egress,
* required by S3 (fraud overlay), S4 (labelling), and S5 (validation),
* partitioned on the same axes as S1 and 5B: `[seed, fingerprint, scenario_id]`.

No other datasets may be written by S2.

---

### 4.1 `s2_flow_anchor_baseline_6B` — baseline flow anchor

**Dataset id**

* `id: s2_flow_anchor_baseline_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

` s2_flow_anchor_baseline_6B` holds the **flow-level view** of baseline behaviour. Each row represents a single, legitimate transaction/flow generated from one or more arrivals in S1, and summarises:

* identity of the flow (`flow_id`) within `(seed, manifest_fingerprint, scenario_id)`,

* linkage back to S1:

  * the `session_id` from `s1_session_index_6B` that this flow belongs to,
  * one or more originating arrivals (via a separate mapping field or array, as defined in the schema),

* entity context:

  * primary `party_id`, `account_id`, `instrument_id`,
  * optional primary `device_id` / `ip_id` for the flow,

* key amounts and currencies (e.g. `auth_amount`, `clear_amount`, `refund_amount`, `iso_currency_code`),

* key timestamps (e.g. `first_auth_ts_utc`, `final_auth_ts_utc`, `clear_ts_utc`, `refund_ts_utc`),

* **baseline outcome** fields under the “all-legit” assumption (e.g. authorised/declined, settled/not settled, refunded/not refunded).

This dataset is the **single authority in 6B** for:

* the set of flows,
* their core financial characteristics,
* their mapping to sessions and upstream arrivals.

**Format, path & partitioning**

The dataset dictionary and artefact registry MUST register this dataset as:

* `version: '{seed}.{manifest_fingerprint}.{scenario_id}'`

* `format: parquet`

* `path` (template):

  ```text
  data/layer3/6B/s2_flow_anchor_baseline_6B/
      seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `partitioning: [seed, fingerprint, scenario_id]`

The `seed`, `manifest_fingerprint`, and `scenario_id` columns in each row MUST match their respective partition tokens exactly.

**Primary key & identity**

For each `(seed, manifest_fingerprint, scenario_id)`:

* Primary key (binding):

  ```text
  [seed, manifest_fingerprint, scenario_id, flow_id]
  ```

where:

* `flow_id` is an S2-defined identifier, unique within the `(seed, manifest_fingerprint, scenario_id)` domain. It MUST be stable (deterministic) given inputs, `parameter_hash`, and `seed`; its type and format (e.g. integer, id64 string) are defined in `schemas.6B.yaml`.

Every event in `s2_event_stream_baseline_6B` MUST reference exactly one `flow_id` in this table for the same `(seed, fingerprint, scenario_id)`.

**Schema anchor**

The logical shape of the flow anchor MUST be defined in the S2 section of the 6B schema pack, for example:

```text
schemas.6B.yaml#/s2/flow_anchor_baseline_6B
```

This schema MUST:

* require the identity axes (`manifest_fingerprint`, `seed`, `scenario_id`, `flow_id`),
* define the core fields described above (linkage to sessions/arrivals, entity context, amounts, timestamps, baseline outcome),
* specify types and nullability, but it does **not** need to restate S1/S2 semantics (those are in this spec).

The S2 entry in `dataset_dictionary.layer3.6B.yaml` MUST use this anchor as `schema_ref`.

**Lineage**

In `dataset_dictionary.layer3.6B.yaml`:

* `produced_by: [ '6B.S2' ]`
* `consumed_by: [ '6B.S3', '6B.S4', '6B.S5' ]`
* `status: required`

In `artefact_registry_6B.yaml`:

* `manifest_key: s2_flow_anchor_baseline_6B`
* `type: dataset`
* `category: plan`
* `final_in_layer: false`

---

### 4.2 `s2_event_stream_baseline_6B` — baseline event stream

**Dataset id**

* `id: s2_event_stream_baseline_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

` s2_event_stream_baseline_6B` is the **event-level** companion to the flow anchor. Each row represents a single event in a baseline flow, such as:

* `AUTH_REQUEST`, `AUTH_RESPONSE`,
* `STEP_UP_CHALLENGE`, `STEP_UP_COMPLETE`,
* `CLEARING`, `REFUND`, `REVERSAL`, etc.

Per event, S2 records:

* the identity axes (`seed, manifest_fingerprint, scenario_id`),
* the `flow_id` that this event belongs to,
* an `event_seq` integer specifying order within the flow,
* event type, timestamp, and any event-specific fields (e.g. response code for auth, amount for clearing/refund),
* entity context (e.g. party/account/instrument), reusing the same IDs as the flow anchor where appropriate,
* routing context consistent with the originating arrival/session (e.g. `site_id` or `edge_id` if relevant).

This dataset is the **single authority in 6B** for the **ordered sequence of baseline events** per flow.

**Format, path & partitioning**

In the dictionary/registry, register as:

* `version: '{seed}.{manifest_fingerprint}.{scenario_id}'`

* `format: parquet`

* `path` (template):

  ```text
  data/layer3/6B/s2_event_stream_baseline_6B/
      seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `partitioning: [seed, fingerprint, scenario_id]`

Again, the `seed`, `manifest_fingerprint`, and `scenario_id` columns MUST match the path tokens.

**Primary key & identity**

For each `(seed, manifest_fingerprint, scenario_id)`:

* Primary key (binding):

  ```text
  [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
  ```

where:

* `flow_id` matches the flow anchor table for this partition,
* `event_seq` is a non-negative integer (or strictly positive, depending on your convention) that defines **strict ordering** of events within a flow, with a unique `(flow_id, event_seq)` pair.

Constraints:

* For any `flow_id`, the sequence of `event_seq` values MUST form a contiguous, strictly increasing sequence starting from a defined base (e.g. `0` or `1`), as specified in the schema.
* Every `(seed, fingerprint, scenario_id, flow_id)` appearing in `s2_event_stream_baseline_6B` MUST appear in `s2_flow_anchor_baseline_6B`.

**Schema anchor**

The shape MUST be defined in `schemas.6B.yaml`:

```text
schemas.6B.yaml#/s2/event_stream_baseline_6B
```

The schema MUST require, at minimum:

* identity axes: `manifest_fingerprint`, `seed`, `scenario_id`, `flow_id`, `event_seq`,
* event fields: `event_type`, `event_ts_utc` (plus any mandatory routing/entity pointers),
* and may add optional fields as needed by S2’s flow model.

The `schema_ref` in the dictionary entry MUST point to this anchor.

**Lineage**

In `dataset_dictionary.layer3.6B.yaml`:

* `produced_by: [ '6B.S2' ]`
* `consumed_by: [ '6B.S3', '6B.S4', '6B.S5' ]`
* `status: required`

In `artefact_registry_6B.yaml`:

* `manifest_key: s2_event_stream_baseline_6B`
* `type: dataset`
* `category: plan`
* `final_in_layer: false`

---

### 4.3 Relationship between flows, events, and S1

To avoid ambiguity:

* **Axes alignment**

  * Both S2 outputs MUST share the same identity axes and partitioning as S1 outputs:

    ```text
    (seed, manifest_fingerprint, scenario_id)
    ```

* **Flows vs sessions**

  * Each flow in `s2_flow_anchor_baseline_6B` MUST:

    * reference exactly one `session_id` from `s1_session_index_6B` in the same partition, and
    * derive its time window and context consistently from that session (and its arrivals), according to S2’s flow policy.

  * A session may map to:

    * one flow, or
    * multiple flows (e.g. multiple orders in one visit), as defined by flow-shape priors; S2’s later sections will define the mapping law, not here.

* **Flows vs events**

  * Every flow MUST have one or more events in `s2_event_stream_baseline_6B`.
  * Every event MUST reference exactly one flow via `{seed, manifest_fingerprint, scenario_id, flow_id}`.
  * There MUST be no “orphan” events or flows (no flow without events, no event without a flow).

* **S1 attachment immutability**

  * S2 MAY copy entity and session fields from S1 into its outputs, but MUST NOT change them. If there is any derived entity context at flow/event level (e.g. “primary device for flow”), it MUST stay consistent with the underlying S1 attachments.

These relationships will be checked by the 6B validation/HashGate state; S2’s outputs have to be wired so that those checks are possible and unambiguous.

---

### 4.4 Catalogue registration (dictionary & registry)

**Dictionary entries**
`dataset_dictionary.layer3.6B.yaml` MUST include entries for both datasets, with:

* `id`, `owner_layer`, `owner_segment`, `status`, `version`, `format`, `path`, `partitioning`, `primary_key`, `ordering`, `schema_ref`, `produced_by`, `consumed_by`.

Exact YAML shape is implementation detail, but the semantics above are binding.

**Artefact registry**
`artefact_registry_6B.yaml` MUST register these datasets with:

* `manifest_key` matching the dictionary `id`,
* `schema` equal to the same anchor used in the dictionary,
* `path_template` consistent with `path`,
* `partitioning: [seed, fingerprint, scenario_id]`,
* `final_in_layer: false`.

This section fixes the **what** and **where** for S2’s outputs. The subsequent sections define **how** they are populated (algorithm), **how** they are written (ordering/merge rules), and **how** they are validated downstream.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

All binding schema anchors, dataset IDs, partitioning rules, and manifest keys for this state's egress live in the Layer-3 / Segment 6B contracts:
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/schemas.layer3.yaml`

This specification only summarises semantics so there is a single source of truth for catalogue details. Always consult the files above for precise schema refs, physical paths, partition keys, writer ordering, lifecycle flags, and dependency metadata.

### 5.1 Outputs owned by this state
- `s2_flow_anchor_baseline_6B` — Deterministic per-flow anchor table capturing baseline attributes before RNG draws.
- `s2_event_stream_baseline_6B` — Exploded per-event baseline stream keyed by flow and event order before corruption/fraud overlays.

### 5.2 Catalogue & downstream obligations
Implementations and downstream consumers MUST resolve datasets via the dictionary/registry, honour the declared schema anchors, and treat any artefact not listed there as out of scope for this state.

## 6. Deterministic algorithm (with RNG) *(Binding)*

This section specifies **how** 6B.S2 constructs baseline flows and events for a given
`(manifest_fingerprint, parameter_hash, seed, scenario_id)`.

S2 is **data-plane + RNG-consuming**:

* Deterministic given:

  * `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`,
  * S1 outputs (`s1_arrival_entities_6B`, `s1_session_index_6B`),
  * any upstream context S2 is permitted to read,
  * 6B flow/amount/timing/RNG policy packs,
  * Layer-3 Philox contracts (event families, budgets).
* All stochastic choices MUST be routed through **S2-specific RNG families** declared in the Layer-3 RNG config; no ad-hoc RNG.

At a high level, per `(seed, scenario_id)` S2:

1. Discovers which sessions and arrivals exist (from S1).
2. Plans how many flows each session contains, and which arrivals belong to each flow.
3. For each flow, samples flow shape, event sequence, timings and amounts with Philox.
4. Instantiates events and anchors, enforcing identity, coverage and FK invariants.
5. Writes `s2_flow_anchor_baseline_6B` and `s2_event_stream_baseline_6B` atomically for the partition.

If any step fails to meet the constraints in this section, S2 MUST fail for that `(seed, scenario_id)` and MUST NOT publish partial outputs.

---

### 6.1 Determinism & RNG envelope

**Binding constraints:**

1. **Pure function + Philox**
   For fixed inputs (world, configs, S1 outputs) and fixed
   `(manifest_fingerprint, parameter_hash, seed, scenario_id)`, S2’s outputs MUST be bit-for-bit reproducible, assuming the same Layer-3 RNG config and `run_id` (if used for logging).

2. **RNG families reserved for S2**
   All random draws in S2 MUST use Philox via a small, fixed set of event families reserved for this state, for example (names indicative):

   * `rng_event_flow_shape` — sampling how many flows per session and what flow types.
   * `rng_event_event_timing` — sampling event time offsets inside flows.
   * `rng_event_amount_draw` — sampling amounts/currencies for flows or events.

   The exact family names, budgets (`blocks`, `draws` per event) and keying scheme are defined in the Layer-3 RNG/RNG-policy contracts; S2 MUST NOT introduce new RNG families outside that contract or re-use other states’ families.

3. **Deterministic budgets per decision**
   For each RNG-consuming decision type, S2 MUST have a fixed, documented budget:

   * e.g. `1` draw per “number of flows for a session”,
   * `k` draws per flow for shape choice,
   * `m` draws per flow/event for timing and amounts,

   where `k` and `m` do not depend on the draw outcomes, only on domain size (e.g. “events in this flow”). The 6B validation state will later reconcile actual draw counts against these budgets.

4. **Deterministic family selection**
   S2 MAY parameterise RNG substreams by `(manifest_fingerprint, parameter_hash, seed, scenario_id, session_id, flow_id)` etc., but MUST NOT:

   * change which RNG **family** is used based on data in a way that breaks per-family coverage accounting, or
   * vary the number of events in a family in a way that cannot be inferred from the domain size.

---

### 6.2 Step 0 — Discover work domain

For a given `manifest_fingerprint`:

1. Read and validate `s0_gate_receipt_6B` and `sealed_inputs_6B`, as defined in S0.

2. From `sealed_inputs_6B` + the 6B dictionary/registry, resolve:

   * the `path_template` and `partition_keys` for `s1_arrival_entities_6B` and `s1_session_index_6B`,
   * the configuration packs required by S2 (`flow_shape_policy_6B`, `amount_model_6B`, `timing_policy_6B`, `flow_rng_policy_6B`).

3. Determine the set of `(seed, scenario_id)` pairs for which S1 outputs exist for this `manifest_fingerprint`. This can be done by:

   * inspecting partitions of `s1_arrival_entities_6B` (and/or `s1_session_index_6B`), or
   * reading an index or manifest if provided.

S2 MAY process different `(seed, scenario_id)` partitions in parallel, but each partition MUST be treated independently and satisfy its own preconditions.

---

### 6.3 Step 1 — Load S1 outputs & optional context

For each `(seed, manifest_fingerprint, scenario_id)` partition S2 intends to process:

1. **Load S1 outputs**

   * Read `s1_arrival_entities_6B@{seed,fingerprint,scenario_id}`.
   * Read `s1_session_index_6B@{seed,fingerprint,scenario_id}`.

   These MUST pass schema validation and S1’s invariants. If they do not, S2 MUST fail preconditions for this partition.

2. **Optional: load upstream context (if enabled in policy)**

   Depending on configuration and `read_scope` in `sealed_inputs_6B`, S2 MAY:

   * Join selected 6A attributes (e.g. party/account/instrument type, posture) onto in-memory S1 data for richer priors.
   * Read context from 5A/5B (intensity, grouping) or 2B/3B (routing context) strictly as **features**.

   Any such context MUST be read via `sealed_inputs_6B` and MUST NOT change the basic domain: sessions and arrivals remain as defined by S1.

3. **Materialise in-memory views**

   For performance, S2 SHOULD build light per-partition indices:

   * `session_id → session record` (`SESS`), including `session_start_utc`, `session_end_utc`, `arrival_count`.
   * `session_id → [arrival rows]` or iterators, sorted by `ts_utc` and/or original arrival order.

   These indices are implementation detail; the spec only requires they are used to ensure invariants and domain coverage.

---

### 6.4 Step 2 — Session-level flow planning (with RNG)

For each session `s` in `s1_session_index_6B`:

1. **Define session planning context**

   Build a context object using:

   * session features: `session_start_utc`, `session_end_utc`, `arrival_count`, `channel_set`, `merchant_set`, etc.
   * entity context: party/account/instrument/device/IP (from S1 and optional 6A attributes).
   * scenario metadata and 6B flow policies.

2. **Determine number of flows for the session**

   Using `flow_shape_policy_6B`, S2 MUST decide the number `N_flows(s)`:

   * Deterministic case:

     * E.g. “exactly one flow per session” or “one flow per arrival” according to policy; no RNG is consumed.
   * Stochastic case:

     * If policy prescribes a distribution (e.g. a discrete distribution over `{1,2,3,…}` flows per session), S2 MUST:

       * use `rng_event_flow_shape` with a key derived from `(seed, fingerprint, scenario_id, session_id)`;
       * draw exactly 1 uniform and map it via the configured distribution to `N_flows(s)`.

   S2 MUST ensure `N_flows(s) ≥ 0` and that the mapping from sessions to flows is deterministic given the RNG output.

3. **Assign arrivals to flows**

   For each session:

   * If `N_flows(s) == 0`:

     * Policy MUST explicitly allow “empty sessions” (rare). In the baseline contract it is normally expected that `N_flows(s) ≥ 1` unless session is explicitly “non-transactional”.
   * If `N_flows(s) ≥ 1`:

     * Use one of S2’s documented assignment rules (defined in the flow policy), e.g.:

       * **One-flow case**: all arrivals in the session map to a single flow.
       * **Arrival-per-flow**: each arrival becomes its own flow.
       * **Multi-flow case**: flows correspond to “orders” within the session; assign arrivals to flows using deterministic rules or additional RNG (through `rng_event_flow_shape` or another family as defined in the policy).

   The assignment algorithm MUST be:

   * fully deterministic given the session’s arrivals, policies and RNG draws, and
   * recorded in flow anchor fields (e.g. via `session_id` and `arrival_keys`).

4. **Create flow identifiers**

   For each flow `f` derived from session `s`:

   * Generate a `flow_id` deterministically from:

     ```text
     (manifest_fingerprint, seed, scenario_id, session_id, flow_index_within_session)
     ```

     or a similar stable scheme defined in the 6B identity law.

   * Ensure that within `(seed, manifest_fingerprint, scenario_id)`, all `flow_id` values are unique.

At the end of this step, S2 has a conceptual mapping:

* from each session to `N_flows(s)`, and
* from each flow to:

  * its parent `session_id`,
  * its set of arrivals.

This mapping is used as the basis for event planning.

---

### 6.5 Step 3 — Intra-flow event planning (with RNG)

For each flow `f` (with known `session_id` and arrivals):

1. **Construct flow planning context**

   Build a flow context from:

   * parent session context (timing, entities, channel, merchant),
   * arrival-level context (one or more arrivals; their timestamps and routing),
   * 6B flow-shape, amount and timing policies.

2. **Decide flow scenario / type**

   Use `flow_shape_policy_6B` to decide high-level flow structure, e.g.:

   * “Single auth → settle”
   * “Auth retry → auth success → settle”
   * “Auth → settle → refund”
   * “Auth → decline, no further attempts”

   Modes:

   * Deterministic: if policy yields a single flow type given context (probability 1), no RNG is used.
   * Stochastic: if multiple flow types are available:

     * Use `rng_event_flow_shape` with key derived from `(seed, fingerprint, scenario_id, flow_id)`;
     * Draw a fixed number of uniforms (typically 1) to select flow type from the configured distribution.

3. **Decide event count and event roles**

   Once a flow type is chosen, S2 MUST:

   * Determine the **event sequence template** for that type, e.g.:

     ```text
     [AUTH_REQUEST, AUTH_RESPONSE, CLEARING]
     or
     [AUTH_REQUEST_1, AUTH_RESPONSE_1, AUTH_REQUEST_2, AUTH_RESPONSE_2, CLEARING]
     or
     [AUTH_REQUEST, AUTH_RESPONSE, CLEARING, REFUND]
     ```

   * This template may be entirely deterministic per flow type, or may include conditional branches (e.g. “optional refund”) resolved via RNG families documented in `flow_shape_policy_6B`.

   Where RNG is used (e.g. “refund vs no refund”), S2 MUST:

   * use the appropriate RNG family (`rng_event_flow_shape` or another S2 family) with a deterministic key based on `(seed, fingerprint, scenario_id, flow_id)`,
   * consume a fixed, documented number of draws per decision.

4. **Plan event timing offsets**

   For each event slot in the flow template, S2 uses `timing_policy_6B` to assign a relative offset from:

   * either a base arrival timestamp (e.g. first arrival in the flow), or
   * the parent session window, depending on policy.

   Typical pattern:

   * Sample gap durations (e.g. in seconds or minutes) for:

     * auth attempts relative to first arrival,
     * auth responses relative to their requests,
     * clearings relative to final successful auth,
     * refunds relative to clearing.

   * RNG: use `rng_event_event_timing` with a key derived from `(seed, fingerprint, scenario_id, flow_id, event_index)`.

   S2 MUST ensure:

   * Event timestamps do not violate the parent session window in gross ways (e.g. no events far before the session start, or far after session end), as defined by policy.
   * Any policy exceptions (e.g. clearings occurring outside session window by design) are explicitly allowed and documented.

5. **Plan amounts & currencies**

   Using `amount_model_6B` and entity/merchant context, S2 MUST decide:

   * the nominal transaction amount and currency for the flow, and
   * event-level amounts where required (e.g. clearing vs refund amounts).

   RNG: use `rng_event_amount_draw` for all amount/currency draws, keyed by `(seed, fingerprint, scenario_id, flow_id)` and event index where relevant.

   S2 MUST respect:

   * configured distributions per merchant/segment/party/account,
   * any constraints (e.g. refund amount ≤ clear amount).

At the end of Step 3, S2 has, for each flow:

* a flow type and event template,
* planned timestamp offsets for each event,
* planned amounts/currencies and baseline outcomes.

---

### 6.6 Step 4 — Event instantiation

For each flow:

1. **Compute event timestamps**

   Using the planned offsets and base timestamps (from arrivals/sessions):

   * Calculate `event_ts_utc` for each event in the flow.
   * Ensure strict ordering:

     ```text
     event_seq = 0,1,2,...  (or 1..N, per schema)
     event_ts_utc(event_seq[i]) ≤ event_ts_utc(event_seq[i+1])
     ```

     Minor non-monotonicity (e.g. equal timestamps) may be allowed per policy but MUST be consistent and documented.

2. **Assign entity and routing context**

   Copy from the flow context / S1 attachments:

   * `party_id`, `account_id`, `instrument_id` (and device/IP where applicable).
   * `session_id` (from S1) if included at event level.
   * Routing fields:

     * if event is tied to a specific arrival, copy/re-use that arrival’s routing context (`site_id` / `edge_id`, `is_virtual`, `routing_universe_hash`),
     * if event is more abstract (e.g. clearing at settlement), choose route consistently with policy (often the same merchant/settlement channel).

   S2 MUST NOT create routing or entity combinations that violate upstream constraints.

3. **Materialise event records**

   For each event template entry:

   * Create a row in `s2_event_stream_baseline_6B` with:

     * identity axes: `manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, event_seq`,
     * `event_type`, `event_ts_utc`,
     * event-specific fields (amounts, response codes, etc.),
     * entity and routing context.

   * Ensure the row conforms to `schemas.6B.yaml#/s2/event_stream_baseline_6B`.

---

### 6.7 Step 5 — Construct flow anchors & enforce invariants

Once events for a flow have been instantiated, S2 constructs the corresponding anchor row:

1. **Aggregate from events and session/arrival context**

   For each `flow_id`:

   * Determine:

     * `session_id` from the parent session.
     * Arrival linkage (`primary_arrival_key` or `arrival_keys`) from arrivals assigned to the flow (Step 2).
     * `first_auth_ts_utc`, `final_auth_ts_utc` from event stream.
     * `clear_ts_utc` and `refund_ts_utc`, if such events exist.
     * `auth_amount`, `clear_amount`, `refund_amount` and `transaction_currency` from event-level data.
     * Baseline outcome flags, derived purely from the baseline event sequence (no fraud/dispute semantics).

   * Copy entity context (party/account/instrument, optional device/IP) from S1 attachments in a consistent way (e.g. based on the primary arrival or majority rule).

2. **Create flow anchor row**

   * Create a row in `s2_flow_anchor_baseline_6B` for this flow with:

     * identity axes, `flow_id`,
     * session and arrival linkage,
     * entity context,
     * amounts/currencies,
     * timestamps,
     * baseline outcome.

   * Ensure the row conforms to `schemas.6B.yaml#/s2/flow_anchor_baseline_6B`.

3. **Flow/event consistency checks (local)**

   For each flow, S2 MUST locally verify:

   * There is at least one event row in `s2_event_stream_baseline_6B` with this `(seed, fingerprint, scenario_id, flow_id)`.
   * Event timestamps are consistent with flow timestamps as per policy (e.g. `first_auth_ts_utc` ≤ all event_ts, etc.).
   * Amounts and currencies in the anchor are consistent with event-level amounts.
   * For flows that are supposed to represent a “typical” outcome (e.g. authorise+settle), the event sequence matches that outcome.

If any of these checks fail for any flow, S2 MUST treat the whole `(seed, scenario_id)` partition as FAIL and MUST NOT publish results.

---

### 6.8 Step 6 — Write outputs & idempotence

For each `(seed, manifest_fingerprint, scenario_id)` partition:

1. **Write `s2_event_stream_baseline_6B`**

   * Write all event rows for the partition to the appropriate path under:

     ```text
     data/layer3/6B/s2_event_stream_baseline_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/...
     ```

   * Ensure:

     * partition keys embedded in rows match the path,
     * rows are sorted by `[seed, manifest_fingerprint, scenario_id, flow_id, event_seq]`,
     * primary key uniqueness holds.

2. **Write `s2_flow_anchor_baseline_6B`**

   * Write all flow anchor rows for the same partition under:

     ```text
     data/layer3/6B/s2_flow_anchor_baseline_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/...
     ```

   * Ensure:

     * partition keys match,
     * rows are sorted by `[seed, manifest_fingerprint, scenario_id, flow_id]`,
     * primary key uniqueness holds.

3. **Atomicity & re-run rules**

   * S2 MUST treat both datasets as a unit for the partition:

     * Either both are successfully written and schema-valid,
     * Or both are considered absent/invalid for that partition.

   * On re-run for the same `(seed, fingerprint, scenario_id, parameter_hash)`:

     * If no outputs exist, S2 writes them.
     * If outputs exist, S2 MUST either:

       * reproduce bit-for-bit identical outputs (idempotent re-run), or
       * fail with a non-idempotence error and MUST NOT overwrite.

---

### 6.9 RNG accounting obligations

S2 MUST cooperate with Layer-3 RNG accounting, even though full reconciliation is performed by the 6B validation state:

* For each RNG family used by S2 (`rng_event_flow_shape`, `rng_event_event_timing`, `rng_event_amount_draw`, etc.):

  * The number of RNG events and total draws MUST be:

    * deterministic given the domain (number of sessions, flows, events), and
    * within a bounded, documented function of that domain.

  * S2 MUST emit RNG events/logs as per the Layer-3 RNG schema so that the validation state can cross-check:

    * the declared domain size (e.g. number of flows, stochastic decisions),
    * the actual draws per family,
    * the monotonicity and non-overlap of RNG counters.

* S2 MUST NOT:

  * consume RNG from families reserved for other states,
  * re-use the same RNG family for semantically different decision types in ways not documented in `flow_rng_policy_6B`,
  * vary draw counts in ways not implied by domain size.

Together with previous sections, this algorithm defines S2 as a **deterministic, RNG-accounted flow synthesis layer**: it takes sealed S1 sessions and attachments and produces a reproducible baseline of flows and events that S3 and S4 can build on, and that S5 can validate against upstream invariants.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S2’s outputs are identified and stored**, and what rules implementations MUST follow for **partitioning, ordering, re-runs and merges**.

It applies to both S2 datasets:

* `s2_flow_anchor_baseline_6B`
* `s2_event_stream_baseline_6B`

and is binding for any conforming implementation.

---

### 7.1 Identity axes for S2

S2 shares the same outer axes as S1 and 5B:

* `manifest_fingerprint` — world snapshot.
* `seed` — run axis shared with 5B and 6A.
* `scenario_id` — arrival scenario axis from 5A/5B.

Binding rules:

1. All S2 outputs MUST include `manifest_fingerprint`, `seed` and `scenario_id` as explicit columns.
2. For a given world (`manifest_fingerprint`), S2 operates on the same `(seed, scenario_id)` partitions as S1 (i.e., those for which `s1_arrival_entities_6B` and `s1_session_index_6B` exist and are PASS).
3. S2 MUST NOT introduce `run_id` or any other execution identifier as a partition key for its outputs. `run_id` is reserved for RNG/logging surfaces only.

Within these axes, the additional identity is:

* `flow_id` — unique per `(seed, manifest_fingerprint, scenario_id)` in `s2_flow_anchor_baseline_6B`.
* `(flow_id, event_seq)` — unique per `(seed, manifest_fingerprint, scenario_id)` in `s2_event_stream_baseline_6B`.

---

### 7.2 Partitioning and file layout

Both S2 datasets are **partitioned identically**:

* `partitioning: [seed, fingerprint, scenario_id]`

and use the following path templates:

* `s2_flow_anchor_baseline_6B`:

  ```text
  data/layer3/6B/s2_flow_anchor_baseline_6B/
      seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `s2_event_stream_baseline_6B`:

  ```text
  data/layer3/6B/s2_event_stream_baseline_6B/
      seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

Binding path↔embed rules:

* For every row in either dataset:

  * `seed` column MUST equal the `seed={seed}` path token.
  * `manifest_fingerprint` column MUST equal the `fingerprint={manifest_fingerprint}` path token.
  * `scenario_id` column MUST equal the `scenario_id={scenario_id}` path token.

* There MUST be no S2 data written outside this directory and partitioning scheme.

---

### 7.3 Primary keys & writer ordering

#### 7.3.1 `s2_flow_anchor_baseline_6B`

**Primary key (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id]
```

where `flow_id` is a unique identifier for the flow within `(seed, manifest_fingerprint, scenario_id)`.

**Writer ordering (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id]
```

Within each `(seed, fingerprint, scenario_id)` partition:

* Rows MUST be sorted by `flow_id` in ascending order.
* The PK MUST be unique: no two rows may share the same `(seed, fingerprint, scenario_id, flow_id)`.

#### 7.3.2 `s2_event_stream_baseline_6B`

**Primary key (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
```

where:

* `flow_id` matches a key in `s2_flow_anchor_baseline_6B` for the same partition.
* `event_seq` is an integer defining per-flow order.

**Writer ordering (binding):**

```text
[seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
```

Within each `(seed, fingerprint, scenario_id)` partition:

* Rows MUST first be grouped by `flow_id`, and within each group be sorted by `event_seq` in ascending order.
* The PK MUST be unique: no two rows may share the same `(seed, fingerprint, scenario_id, flow_id, event_seq)`.

**Event sequence discipline:**

For each `(seed, fingerprint, scenario_id, flow_id)`:

* `event_seq` MUST form a contiguous, strictly monotone sequence starting from a defined base (e.g. 0 or 1) as specified in the schema and S2 identity law.
* There MUST be at least one event per flow.

---

### 7.4 Relationship to S1 and coverage discipline

For a given `(manifest_fingerprint, seed, scenario_id)` partition:

* S1 defines:

  * the set of sessions: `S = { session_id }` in `s1_session_index_6B`,
  * the set of arrivals: `A = { arrival keys }` in `s1_arrival_entities_6B`.

* S2 defines:

  * the set of flows: `F = { flow_id }` in `s2_flow_anchor_baseline_6B`,
  * the mapping `flow_id → session_id` recorded in the flow anchor,
  * the event set `E = { (flow_id, event_seq) }` in `s2_event_stream_baseline_6B`.

Binding relationships:

1. **Session linkage**

   * Every row in `s2_flow_anchor_baseline_6B` MUST contain a `session_id` that exists in `s1_session_index_6B` for the same axes.
   * A session MAY have zero, one or many flows depending on policy, but that mapping is explicitly a part of S2’s semantics and will be constrained in acceptance (§8). S2 MUST not produce flows for sessions that do not exist.

2. **Flow/event linkage**

   * For each flow_id in `s2_flow_anchor_baseline_6B`, there MUST be ≥1 event rows in `s2_event_stream_baseline_6B` with the same `(seed, fingerprint, scenario_id, flow_id)`.
   * There MUST be no event rows for `flow_id`s that do not appear in the anchor.

3. **Arrival linkage**

   * The mapping from arrivals in S1 to flows in S2 is defined by S2’s flow-shape policy (and encoded in flow-level fields such as `arrival_keys`).
   * While S2 may choose to aggregate multiple arrivals into a single flow or produce multiple flows per session, it MUST respect whatever mapping rules are defined in the S2 acceptance spec; identity-wise, any linkage fields MUST be stable across re-runs.

The exact coverage law (“one flow per arrival”, “one or more flows per session”, etc.) lives in S2’s acceptance section; here we only bind that all such relationships are expressible via keys and that joins are unambiguous.

---

### 7.5 Re-run & idempotence discipline

S2 MUST be **idempotent** per `(manifest_fingerprint, parameter_hash, seed, scenario_id)` under fixed inputs.

Binding rules:

1. **Per-partition atomicity**

   For each `(seed, fingerprint, scenario_id)`:

   * S2 MUST treat `s2_flow_anchor_baseline_6B` and `s2_event_stream_baseline_6B` as a **unit of work**.
   * It MUST NOT leave a state where one dataset is written and the other is missing or inconsistent.

   If a failure occurs after writing one dataset but before the other, the partition MUST be considered FAILED; orchestrators MUST ensure such partial outputs are either cleaned or overwritten on the next attempt, according to engine-wide recovery policy.

2. **Single logical writer per partition**

   * At any given time, there MUST be at most one S2 instance responsible for a given `(seed, fingerprint, scenario_id)` in a deployment.
   * Parallelism across different `(seed, scenario_id)` pairs is allowed, but concurrent writes to the same partition by multiple S2 instances are disallowed.

3. **Idempotent re-runs**

   For a given `(manifest_fingerprint, parameter_hash, seed, scenario_id)`:

   * If no S2 outputs exist yet, S2 writes them once.
   * If outputs already exist, a re-run MUST either:

     * reproduce exactly the same logical content (same rows, same PKs, and, under the engine’s encoding guarantees, effectively the same data), or
     * fail with an idempotence error (e.g. `S2_IDEMPOTENCE_VIOLATION`) and MUST NOT overwrite existing data.

   This implies that:

   * S2 MUST NOT implement “incremental” append/merge semantics for flows/events.
   * Any change to flow/amount/timing policy that would alter outputs for the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)` MUST be expressed via a new `parameter_hash` (and/or spec version), not by silently changing the implementation under the same configuration.

---

### 7.6 Join discipline for downstream states

Downstream states (S3, S4, S5) MUST join S2 outputs using the identity axes and keys defined here:

* **World/run/scenario axes:**

  * Always include `(seed, manifest_fingerprint, scenario_id)` in join keys when moving between S1, S2 and upstream surfaces.

* **Flows vs events:**

  * To relate flow anchors and event stream:

    ```text
    [seed, manifest_fingerprint, scenario_id, flow_id]
    ```

  * MUST be used as the join key; `event_seq` remains local to the event stream.

* **Flows vs sessions:**

  * To relate flows and S1 sessions:

    ```text
    [seed, manifest_fingerprint, scenario_id, session_id]
    ```

* **Flows vs S1 arrivals:**

  * If a downstream state needs to inspect arrivals behind a flow, it MUST do so via whatever arrival linkage fields S2 defines in `s2_flow_anchor_baseline_6B` (e.g. `primary_arrival_key` or `arrival_keys`) combined with S1’s arrival PK:

    ```text
    [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
    ```

Downstream states MUST NOT infer joins based on file paths or ordering alone; identity is always expressed through columns + partition axes.

---

### 7.7 Interaction with RNG logs (non-partition identity)

S2 consumes RNG through Layer-3 event families (e.g. `rng_event_flow_shape`, `rng_event_event_timing`, `rng_event_amount_draw`), whose logs, if materialised, follow the Layer-3 RNG partition law (typically `[seed, parameter_hash, run_id]`).

Binding points:

* S2’s data-plane outputs MUST NOT:

  * include `run_id` as a partition key,
  * rely on RNG-log dataset partitions for their own identity.

* S2’s deterministic mapping means that, given RNG logs and inputs, a validation state can reproduce:

  * for each `(seed, manifest_fingerprint, scenario_id)`,
  * which RNG decisions correspond to which flows/events.

The only identity link between RNG logs and S2 outputs is via axes like `(seed, parameter_hash)` and any keys encoded in RNG event contexts (e.g. `flow_id`, `session_id`), not via partitioning of S2 datasets themselves.

---

By adhering to these identity, partitioning, ordering and merge rules, S2 remains:

* a deterministic, reproducible baseline-flow builder on top of S1 and upstream layers, and
* a stable, unambiguous foundation for S3 (fraud overlay), S4 (labelling) and S5 (validation/HashGate).

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines:

* When 6B.S2 is considered **PASS** vs **FAIL** for a given
  `(manifest_fingerprint, seed, scenario_id)`, and
* What obligations this places on **downstream 6B states** (S3, S4, S5) and on orchestrators / 4A–4B.

All conditions here are **binding**. If they are not met, S2 MUST be treated as FAIL for that domain and downstream states MUST NOT proceed.

---

### 8.1 Domain of evaluation

S2 is evaluated per triple:

```text
(manifest_fingerprint, seed, scenario_id)
```

For a given `manifest_fingerprint`, there may be many `(seed, scenario_id)` pairs.
S0’s gate covers the world; S1’s gate covers `(seed, scenario_id)`; S2’s acceptance is **per (seed, scenario_id)**.

---

### 8.2 Acceptance criteria for S2 (per `(seed, scenario_id)`)

For a fixed `(manifest_fingerprint, seed, scenario_id)`, S2 is **PASS** if and only if all of the following hold.

#### 8.2.1 Preconditions satisfied

Before any flow is considered valid:

* 6B.S0 is PASS for the world and `s0_gate_receipt_6B` / `sealed_inputs_6B` are present and schema-valid.
* `s0_gate_receipt_6B.upstream_segments[SEG].status == "PASS"` for all required segments `{1A,1B,2A,2B,3A,3B,5A,5B,6A}`.
* 6B.S1 is PASS for this `(seed, scenario_id)` (as recorded in the run-report).
* `s1_arrival_entities_6B@{seed,fingerprint,scenario_id}` and `s1_session_index_6B@{seed,fingerprint,scenario_id}` exist and pass their own schema validation.

If any of these are not satisfied, S2 MUST fail the partition as a precondition failure and MUST NOT write S2 outputs.

#### 8.2.2 Schema validity of S2 outputs

Both S2 datasets for this `(seed, fingerprint, scenario_id)` MUST:

* Exist at their expected paths and partitions.

* Pass schema validation against their anchors:

  * `s2_flow_anchor_baseline_6B` → `schemas.6B.yaml#/s2/flow_anchor_baseline_6B`
  * `s2_event_stream_baseline_6B` → `schemas.6B.yaml#/s2/event_stream_baseline_6B`

* Respect their declared primary keys and partitioning:

  * No duplicate PKs.
  * All rows have `seed`, `manifest_fingerprint`, `scenario_id` equal to the partition tokens.

If either dataset fails schema or PK/partition checks, S2 MUST be considered FAIL for the partition.

#### 8.2.3 Flow–event consistency

Let:

* `FA2` = `s2_flow_anchor_baseline_6B@{seed,fingerprint,scenario_id}`.
* `EV2` = `s2_event_stream_baseline_6B@{seed,fingerprint,scenario_id}`.

S2 MUST ensure:

1. **Flow coverage in events**

   * For every `flow_id` in `FA2`, there is at least one row in `EV2` with the same `(seed, fingerprint, scenario_id, flow_id)`.

2. **No orphan events**

   * Every row in `EV2` has a `flow_id` that exists in `FA2` for the same axes.

3. **Event sequence discipline**

   * For each flow_id:

     * `(flow_id, event_seq)` is unique.
     * `event_seq` forms a contiguous, strictly monotone sequence starting from the base defined in the schema (e.g. 0 or 1).
     * Events are ordered by `event_seq` when sorted.

4. **Temporal consistency**

   For each flow:

   * `first_auth_ts_utc` and `final_auth_ts_utc` in `FA2` MUST match the min/max auth-related event timestamps in `EV2`, as defined by policy.
   * `clear_ts_utc` MUST be null or equal to the timestamp of a CLEARING event in `EV2`.
   * `refund_ts_utc` MUST be null or equal to the timestamp of a REFUND event in `EV2`.
   * No `event_ts_utc` MUST violate basic temporal constraints defined by S2 policy (e.g. no event grossly before the parent session start unless explicitly allowed, no negative durations).

5. **Amount/currency consistency**

   For each flow:

   * Flow-level amounts/currencies (`auth_amount`, `clear_amount`, `refund_amount`, `transaction_currency`, etc.) MUST be consistent with the event-level amounts/currencies in `EV2` (e.g. `clear_amount` = sum of CLEARING event amounts, `refund_amount` ≤ `clear_amount` where defined).

Any violation of these flow–event consistency rules MUST cause S2 to be marked FAIL for the partition.

#### 8.2.4 Linkage to S1 sessions and arrivals

Let:

* `SESS` = `s1_session_index_6B@{seed,fingerprint,scenario_id}`.
* `AE6B` = `s1_arrival_entities_6B@{seed,fingerprint,scenario_id}`.

S2 MUST ensure:

1. **Session linkage**

   * Every row in `FA2` contains a `session_id` that exists in `SESS`.
   * If S2’s policy requires at least one flow per session, then for each `session_id` in `SESS` either:

     * there exists ≥1 flow in `FA2` referencing that session, or
     * the session is explicitly flagged as “non-transactional” according to the flow-shape policy (e.g. purely informational session) and that flag is consistent across S2/S3/S4 specs.

2. **Arrival linkage**

   * For each flow, S2 MUST encode its linkage to originating arrivals in a consistent way (e.g. a primary arrival or a list of contributing arrivals).
   * For every arrival referenced in the flow anchor, there MUST be a matching row in `AE6B`.
   * S2 MUST NOT reference arrivals outside the `(seed,fingerprint,scenario_id)` domain of AE6B.

The exact mapping rules (one-flow-per-arrival, one-or-more flows per session, etc.) are defined in the flow policy; acceptance checks MUST verify that S2’s outputs are consistent with that policy.

#### 8.2.5 Entity & routing consistency

For each event and flow:

* Any entity IDs present (`party_id`, `account_id`, `instrument_id`, `device_id`, `ip_id`) MUST:

  * either be copied from S1 outputs for that arrival/session, or
  * be derivable in a way that is consistent with S1 and 6A (e.g. same account/instrument/party; derived primary entity across several arrivals).

* S2 MUST NOT introduce entity combinations that contradict S1 attachments or 6A link rules (e.g. a flow anchored to a different party than its arrivals).

* Routing fields (e.g. `site_id`, `edge_id`, `is_virtual`, `routing_universe_hash`) used in events MUST be consistent with the originating arrival(s) or with routing policy. S2 MUST NOT change routing in ways that contradict 5B/Layer-1.

If any event or flow contains entity or routing references that cannot be reconciled with S1 attachments / upstream surfaces, S2 MUST be marked FAIL for the partition.

#### 8.2.6 RNG envelope sanity (local to S2)

S2 MUST perform basic local checks that its RNG usage is consistent with its declared budgets, for this partition:

* For each RNG family used by S2 (`rng_event_flow_shape`, `rng_event_event_timing`, `rng_event_amount_draw`, etc.), S2 MUST ensure:

  * The count of RNG events and draws is within a bounded function of:

    * number of sessions,
    * number of flows,
    * number of events.

* If S2’s own counters show clear inconsistencies (e.g. zero draw events when policy requires stochastic behaviour, or significantly more draws than possible domain size × configured budget), S2 MUST treat this as a FAIL for the partition.

Full RNG reconciliation against global RNG logs is done by S5; S2 only needs to ensure its *local* accounting is internally coherent.

---

### 8.3 Conditions that MUST cause S2 to FAIL

For a given `(manifest_fingerprint, seed, scenario_id)`, S2 MUST be treated as **FAIL** (and its outputs considered unusable) if any of the following occurs:

* Any precondition in §2 or §8.2.1 is not met.
* Either S2 output fails schema validation or has PK/partition violations.
* Flow/event consistency (coverage, sequence, timestamps, amounts) fails per §8.2.3.
* Session and arrival linkage invariants fail per §8.2.4.
* Entity or routing consistency breaks per §8.2.5.
* RNG envelope sanity checks fail per §8.2.6.
* Any I/O or write failure prevents S2 from producing a complete, consistent pair of outputs for the partition.

On FAIL, S2 MUST:

* NOT advertise success in the run-report for that partition.
* Leave no partial outputs that could be mistaken for a valid S2 run (or ensure that any partial outputs are treated as invalid by orchestration and S5).

Downstream states MUST treat `status="FAIL"` as a hard gate for that partition.

---

### 8.4 Gating obligations for S3 and S4

For any `(manifest_fingerprint, seed, scenario_id)`:

1. **S2 PASS is a hard precondition for S3 and S4**

   * 6B.S3 (fraud/abuse overlay) and 6B.S4 (labelling) MUST NOT run for a partition unless:

     * S0 is PASS at the world level, AND
     * S1 is PASS for that `(seed, scenario_id)`, AND
     * S2 is PASS for that `(seed, scenario_id)`.

2. **S2 outputs are the baseline canvas**

   * S3 MUST treat `s2_flow_anchor_baseline_6B` and `s2_event_stream_baseline_6B` as the **canonical baseline flows**. It MAY:

     * attach campaign ids,
     * add/modify events to reflect fraud/abuse,
     * create additional flows for purely fraudulent activity,

     but it MUST NOT attempt to re-derive baseline flows from S1 or 5B in a way that contradicts S2’s outputs.

   * S4 MUST base its truth labels and bank-view outcomes on:

     * the final flow/event surfaces (S2+S3),
     * but it MUST be able to trace back to baseline S2 flows and S1 attachments where required.

3. **No mutation of S2 outputs**

   * S3 and S4 MUST treat S2 outputs as read-only baseline surfaces.
   * If S3 needs to derive “final” flows/events, it SHOULD write them to separate datasets (e.g. `s3_flow_anchor_final_6B`, `s3_event_stream_final_6B`), not overwrite S2.

If S3 or S4 detect that S2 outputs are missing or malformed for a partition, they MUST fail early with a precondition error referencing S2, not attempt repair.

---

### 8.5 Obligations for 6B validation (S5) and 4A/4B

The 6B validation / HashGate state (S5) and downstream layers MUST follow:

1. **S5 MUST validate S2 invariants**

   * S5 MUST treat the invariants in §8.2 as **binding checks**:

     * flow/event coverage and consistency,
     * linkage to S1 sessions and arrivals,
     * entity/routing consistency,
     * RNG envelope consistency.

   * Any violation MUST cause S5 to mark the 6B segment as FAIL for that `manifest_fingerprint`, regardless of S3/S4 status.

2. **S5 depends on S2 PASS for all partitions**

   * S5 MUST NOT declare the 6B segment HashGate PASS if there exists any `(seed, scenario_id)` for which S2 has not PASSed (or has not run when it should have).

3. **4A/4B MUST gate on S5, not directly on S2**

   * 4A/4B and external consumers MUST NOT treat any 6B flows/events/labels as **production-readable** unless:

     * S0 is PASS for the world, AND
     * the 6B segment HashGate (driven by S5) is PASS, which implies S2 has passed all its acceptance criteria.

S2 by itself does not authorise external consumption; it is a prerequisite for S3/S4 and for a successful 6B HashGate.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical failure modes** for 6B.S2 and the **error codes** that MUST be used when they occur.

For any `(manifest_fingerprint, seed, scenario_id)` partition that S2 attempts, the state MUST:

* End in exactly one of: `status="PASS"` or `status="FAIL"`.
* If `status="FAIL"`, attach a **single primary error code** from the list below, and MAY attach secondary codes and diagnostics.

Downstream states (S3, S4, S5) and orchestrators MUST treat any non-PASS S2 status for a partition as a **hard gate** for that partition.

---

### 9.1 Error model & context

For each failed `(manifest_fingerprint, seed, scenario_id)`:

* **Primary error code**

  * One code from the enumeration in §§9.2–9.7 (e.g. `S2_FLOW_EVENT_MISMATCH`).
  * Summarises the main reason S2 did not complete successfully.

* **Secondary error codes** (optional)

  * A list of additional codes giving more detail (e.g. both `S2_FLOW_EVENT_MISMATCH` and `S2_EVENT_SEQUENCE_INVALID`).
  * MUST NOT be used without a primary code.

* **Context fields**

  * Run-report and logs SHOULD include:

    * `manifest_fingerprint`
    * `seed`
    * `scenario_id`
    * Optional: `flow_id`, `session_id`, `owner_segment`, `manifest_key`, depending on failure.
    * Optional: a human-readable `detail` string.

The exact run-report schema is defined in §10; here we bind the error codes and their semantics.

---

### 9.2 Preconditions & sealed-inputs failures

These codes indicate S2 never legitimately entered flow/event synthesis for the partition.

#### 9.2.1 `S2_PRECONDITION_S0_OR_S1_FAILED`

**Definition**
Emitted when either:

* 6B.S0 is not PASS for `manifest_fingerprint`, or
* 6B.S1 is not PASS for `(manifest_fingerprint, seed, scenario_id)`.

**Examples**

* `s0_gate_receipt_6B` missing or invalid.
* Run-report marks S1 as `status="FAIL"` or has no S1 entry for this `(seed, scenario_id)`.

**Obligations**

* S2 MUST NOT read any S1 outputs or upstream data-plane tables.
* No S2 outputs for this partition may be produced.

---

#### 9.2.2 `S2_PRECONDITION_SEALED_INPUTS_INCOMPLETE`

**Definition**
Emitted when `sealed_inputs_6B` is present but does not contain the required S1 or S2 artefacts for this world.

**Examples**

* No row for `s1_arrival_entities_6B` or `s1_session_index_6B` with `status="REQUIRED", read_scope="ROW_LEVEL"`.
* No row for a required S2 config pack (e.g. `flow_shape_policy_6B`, `amount_model_6B`) or missing/invalid `schema_ref` for those packs.

**Obligations**

* S2 MUST NOT guess dataset locations or read unlisted artefacts.
* S2 MUST fail before any data-plane work.

---

#### 9.2.3 `S2_PRECONDITION_RNG_POLICY_INVALID`

**Definition**
Emitted when S2 cannot locate or validate the Layer-3 RNG policy entries required for its RNG families (e.g. `rng_event_flow_shape`, `rng_event_event_timing`, `rng_event_amount_draw`).

**Examples**

* `flow_rng_policy_6B` missing from `sealed_inputs_6B`.
* RNG family names used by S2 absent from the Layer-3 RNG spec.
* Inconsistent or unsupported `blocks`/`draws` budget configuration for S2’s families.

**Obligations**

* S2 MUST NOT proceed to plan flows or sample RNG.
* Configuration must be fixed before S2 can run.

---

### 9.3 Schema & identity failures for S2 outputs

These indicate that S2 attempted to run but produced structurally invalid outputs.

#### 9.3.1 `S2_FLOW_ANCHOR_SCHEMA_VIOLATION`

**Definition**
Emitted when `s2_flow_anchor_baseline_6B` fails schema or key validation for the partition.

**Examples**

* Missing required fields (e.g. `flow_id`, `session_id`, `auth_amount`).
* Duplicate primary keys `(seed, manifest_fingerprint, scenario_id, flow_id)`.
* Partition columns in rows do not match path tokens.

**Obligations**

* S2 MUST treat the entire partition as FAIL.
* Downstream states MUST NOT read the anchor table for this partition.

---

#### 9.3.2 `S2_EVENT_STREAM_SCHEMA_VIOLATION`

**Definition**
Emitted when `s2_event_stream_baseline_6B` fails schema or key validation.

**Examples**

* Missing `event_type` or `event_ts_utc`.
* Duplicate `(seed, manifest_fingerprint, scenario_id, flow_id, event_seq)` keys.
* Partition axes mismatched with path.

**Obligations**

* S2 MUST treat the partition as FAIL.
* Downstream states MUST NOT use the event stream.

---

#### 9.3.3 `S2_AXES_MISMATCH`

**Definition**
Emitted when S2 finds rows in its outputs whose `seed`, `manifest_fingerprint`, or `scenario_id` do not match the partition axes.

**Examples**

* A row under `seed=A` directory containing `seed=B`.
* Mixed `scenario_id` values inside a single `(seed, fingerprint, scenario_id)` partition.

**Obligations**

* Hard FAIL; outputs are unusable for this partition.

---

### 9.4 Flow–event consistency failures

These codes cover structural inconsistencies between the flow anchor and event stream.

#### 9.4.1 `S2_FLOW_EVENT_MISMATCH`

**Definition**
Emitted when flows and events do not match up for the partition.

**Examples**

* A `flow_id` in `s2_flow_anchor_baseline_6B` with **no** corresponding events in `s2_event_stream_baseline_6B`.
* Events in `s2_event_stream_baseline_6B` referencing a `flow_id` that does not exist in the anchor table.

**Obligations**

* S2 MUST treat the partition as FAIL; flows and events must be recomputed.

---

#### 9.4.2 `S2_EVENT_SEQUENCE_INVALID`

**Definition**
Emitted when per-flow event ordering/sequence constraints are violated.

**Examples**

* Non-contiguous `event_seq` values for a given flow (e.g. `0, 1, 3` with no `2`).
* Duplicate `event_seq` values for the same `(seed, fingerprint, scenario_id, flow_id)`.
* Event timestamps that violate S2’s basic monotonicity rules (e.g. a later `event_seq` has an earlier `event_ts_utc` when policy forbids that).

**Obligations**

* S2 MUST fail; event sequences must be regenerated.

---

#### 9.4.3 `S2_FLOW_EVENT_TEMPORAL_MISMATCH`

**Definition**
Emitted when flow-level timestamps are inconsistent with event-level timestamps.

**Examples**

* `first_auth_ts_utc` in the anchor does not equal the minimum auth-related event timestamp.
* `clear_ts_utc` is non-null but does not match any CLEARING event’s timestamp.
* `refund_ts_utc` is set, but no REFUND events exist for that flow.

**Obligations**

* S2 MUST fail; anchors and events must be brought back into alignment.

---

#### 9.4.4 `S2_FLOW_EVENT_AMOUNT_MISMATCH`

**Definition**
Emitted when flow-level amounts/currencies are inconsistent with event-level data.

**Examples**

* `clear_amount` in anchor does not equal sum of CLEARING event amounts for that flow.
* `refund_amount` > `clear_amount` when policy forbids this.
* `transaction_currency` inconsistent with currencies used in event-level amounts.

**Obligations**

* S2 MUST fail the partition; amount models or summarisation logic must be fixed.

---

### 9.5 Linkage to S1 sessions and arrivals

These failures indicate that S2’s flows are not correctly tied back to S1 sessions/arrivals.

#### 9.5.1 `S2_SESSION_LINKAGE_INVALID`

**Definition**
Emitted when session/flow linkage is broken.

**Examples**

* A `session_id` in `s2_flow_anchor_baseline_6B` not found in `s1_session_index_6B`.
* Policies declare that sessions with certain characteristics must produce flows, but S2 produces none and fails to flag them as non-transactional where required.

**Obligations**

* S2 MUST fail the partition; flows must not reference sessions that don’t exist.

---

#### 9.5.2 `S2_ARRIVAL_LINKAGE_INVALID`

**Definition**
Emitted when flows’ linkage to arrival-level context is invalid or inconsistent.

**Examples**

* A flow claims to originate from an arrival key that does not exist in `s1_arrival_entities_6B`.
* The mapping from arrivals to flows contradicts S2’s own documented flow-shape policy (e.g. “one flow per arrival” policy violated).

**Obligations**

* S2 MUST fail; arrival–flow mapping must be recalculated.

---

### 9.6 Entity & routing consistency failures

These capture inconsistencies between S2 outputs and S1/6A entity/routing facts.

#### 9.6.1 `S2_ENTITY_CONTEXT_INCONSISTENT`

**Definition**
Emitted when flow/event entity context in S2 is not consistent with S1 attachments or 6A bases/links.

**Examples**

* Flow-level `party_id` does not match the parties of its contributing arrivals.
* Device/IP assignments in flow or event rows contradict earlier S1 attachments or 6A link tables.

**Obligations**

* S2 MUST fail; entity context must be recalculated consistent with S1/6A.

---

#### 9.6.2 `S2_ROUTING_CONTEXT_INCONSISTENT`

**Definition**
Emitted when routing context (e.g. site/edge, virtual/physical flags) used in events is inconsistent with 5B or 3B/2B policies.

**Examples**

* A CLEARING or REFUND event uses a `site_id` / `edge_id` combination that cannot be reconciled with its originating arrivals and Layer-1 routing constraints.
* A flow anchored as virtual uses routing_universe_hash inconsistent with 3B’s virtual routing universe.

**Obligations**

* S2 MUST fail; routing decisions must be consistent with upstream facts.

---

### 9.7 RNG envelope & configuration failures

These codes concern incorrect use or configuration of RNG in S2.

#### 9.7.1 `S2_RNG_EVENT_COUNT_MISMATCH`

**Definition**
Emitted when measured RNG usage by S2 violates its own declared budgets for a partition.

**Examples**

* Fewer `rng_event_flow_shape` events than #sessions that require stochastic flow counting.
* More `rng_event_amount_draw` events than permitted given the number of flows and events.

**Obligations**

* S2 MUST fail the partition; RNG calling patterns must be corrected.

---

#### 9.7.2 `S2_RNG_STREAM_MISCONFIGURED`

**Definition**
Emitted when S2 cannot correctly attach to the allocated RNG families/streams.

**Examples**

* Attempting to use a RNG family not defined (or not reserved) for S2.
* Inconsistent or conflicting substream keys causing counter collisions or non-monotone counters.

**Obligations**

* S2 MUST fail and not attempt to proceed with flow synthesis.

---

### 9.8 Output write & idempotence failures

#### 9.8.1 `S2_OUTPUT_WRITE_FAILED`

**Definition**
Emitted when S2 fails to persist one or both of its outputs for a partition due to I/O or infrastructure errors.

**Examples**

* Filesystem/network error when writing parquet.
* Permission issues or storage quota exceeded.

**Obligations**

* S2 MUST mark the partition as FAIL.
* Orchestrators MUST treat any partial outputs as invalid and either clean them or allow S2 to overwrite them safely on re-run, according to engine-wide recovery policy.

---

#### 9.8.2 `S2_IDEMPOTENCE_VIOLATION`

**Definition**
Emitted when outputs already exist for a partition and a re-run of S2 with the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)` would produce different content.

**Examples**

* Changes to flow/amount/timing policies applied without updating `parameter_hash` or `spec_version_6B`.
* Upstream S1 outputs changed without corresponding gating logic preventing S2 from re-running under the old assumptions.

**Obligations**

* S2 MUST NOT overwrite existing outputs.
* This condition indicates contract drift; operators MUST investigate and address it (e.g. by bumping `parameter_hash` or spec version, or rebuilding from upstream).

---

### 9.9 Internal / unexpected failures

#### 9.9.1 `S2_INTERNAL_ERROR`

**Definition**
Catch-all for failures not attributable to:

* precondition violations,
* sealed-inputs/configuration gaps,
* schema/identity issues,
* flow/event/linkage inconsistencies, or
* RNG misconfiguration.

**Examples**

* Uncaught exceptions, segmentation faults, assertion failures.
* Unexpected type errors in internal data structures not captured by schema validation.

**Obligations**

* S2 MUST fail the partition.
* Implementations SHOULD log sufficient context to allow classification of recurring `S2_INTERNAL_ERROR` instances into more specific codes in future spec revisions.

---

### 9.10 Surfaces & propagation

For any `(manifest_fingerprint, seed, scenario_id)` where S2 fails:

* The **Layer-3 run-report** MUST record:

  * `segment = "6B"`, `state = "S2"`,
  * `status = "FAIL"`,
  * `primary_error_code` as above,
  * optional `secondary_error_codes` and context.

* S3 and S4 MUST treat S2 failure as a **hard precondition failure** for that partition and MUST NOT run; they SHOULD surface S2’s `primary_error_code` in their own precondition failure reports.

* The 6B validation/HashGate state (S5) MUST treat any S2 failure for any partition as a **segment-level FAIL** for the associated `manifest_fingerprint` and MUST propagate S2’s error codes into its own diagnostics.

These error codes and behaviours are binding and are part of S2’s external contract.

---

## 10. Observability & run-report integration *(Binding)*

This section defines what 6B.S2 **must expose** for observability, and **how** it must appear in the engine run-report, so that:

* Operators can see whether baseline flows and events are being synthesised correctly.
* Downstream states (S3, S4, S5) and orchestrators can **gate** on S2’s status in a machine-readable way.

Everything here is **binding** for S2.

---

### 10.1 Run-report scope and keying

S2 is evaluated per:

```text
(manifest_fingerprint, seed, scenario_id)
```

For each `(manifest_fingerprint, seed, scenario_id)` that S2 attempts, the Layer-3 run-report **MUST** contain exactly one entry with at least:

* `segment` = `"6B"`
* `state`   = `"S2"`
* `manifest_fingerprint`
* `seed`
* `scenario_id`
* `status` — `"PASS"` or `"FAIL"`
* `primary_error_code` — from §9 (or `null` if `status="PASS"`)
* `secondary_error_codes` — list (possibly empty)

Additionally, the run-report **MUST** include a summary block for this partition (see §10.2).

There MUST NOT be more than one S2 run-report entry per `(manifest_fingerprint, seed, scenario_id)` in a single run.

---

### 10.2 Required summary metrics (per `(seed, scenario_id)`)

For each `(manifest_fingerprint, seed, scenario_id)` partition, the run-report MUST include a **summary object** with at least:

#### 10.2.1 Counts

* `session_count_S1`

  * Number of rows in `s1_session_index_6B` for this partition.

* `arrival_count_S1`

  * Number of rows in `s1_arrival_entities_6B` for this partition.

* `flow_count_S2`

  * Number of rows in `s2_flow_anchor_baseline_6B`.

* `event_count_S2`

  * Number of rows in `s2_event_stream_baseline_6B`.

#### 10.2.2 Coverage & consistency flags

* `flows_have_events_ok: boolean`

  * True iff every flow in `s2_flow_anchor_baseline_6B` has ≥1 event in `s2_event_stream_baseline_6B`.

* `no_orphan_events_ok: boolean`

  * True iff every event in `s2_event_stream_baseline_6B` references a `flow_id` present in the flow anchor table.

* `session_linkage_ok: boolean`

  * True iff every `session_id` in `s2_flow_anchor_baseline_6B` exists in `s1_session_index_6B` for the same axes.

* `arrival_linkage_ok: boolean`

  * True iff all arrival linkages encoded in the flow anchor (e.g. `arrival_keys`) refer to arrivals in `s1_arrival_entities_6B` for this partition.

* `temporal_consistency_ok: boolean`

  * True iff flow-level timestamps (`first_auth_ts_utc`, `clear_ts_utc`, `refund_ts_utc`) are consistent with event-level timestamps and S2’s timing rules.

* `amount_consistency_ok: boolean`

  * True iff flow-level amounts/currencies are consistent with event-level data for all flows.

#### 10.2.3 Flow & event distributions (for monitoring)

At minimum:

* `avg_events_per_flow`

* `p95_events_per_flow`

* `max_events_per_flow`

* `fraction_flows_with_refund` (or count per policy)

* `fraction_flows_declined` (baseline auth outcome)

These are informative for operations but MUST be correctly computed wherever present.

#### 10.2.4 Binding relationships

If `status="PASS"` for S2 on this partition, then the following MUST be true:

* `flows_have_events_ok == true`
* `no_orphan_events_ok == true`
* `session_linkage_ok == true`
* `arrival_linkage_ok == true`
* `temporal_consistency_ok == true`
* `amount_consistency_ok == true`

If any of these flags would be `false`, S2 MUST NOT report `status="PASS"`; it MUST be `status="FAIL"` with an appropriate primary error code (§9).

---

### 10.3 Logging requirements

S2 MUST emit structured logs at key stages for each `(manifest_fingerprint, seed, scenario_id)` partition. At minimum:

1. **Partition start**

   ```text
   event_type: "6B.S2.START"
   manifest_fingerprint
   seed
   scenario_id
   sealed_inputs_digest_6B   // from S0 receipt
   ```

2. **Precondition check**

   ```text
   event_type: "6B.S2.PRECONDITION_CHECK"
   manifest_fingerprint
   seed
   scenario_id
   s0_status                  // PASS/FAIL
   s1_status                  // PASS/FAIL
   upstream_gates_ok: bool    // from S0 receipt
   error_code                 // if preconditions fail (e.g. S2_PRECONDITION_S0_OR_S1_FAILED)
   ```

3. **S1 input summary**

   ```text
   event_type: "6B.S2.S1_INPUT_SUMMARY"
   manifest_fingerprint
   seed
   scenario_id
   session_count_S1
   arrival_count_S1
   ```

4. **Flow planning summary**

   After planning flows but before writing:

   ```text
   event_type: "6B.S2.FLOW_PLANNING_SUMMARY"
   manifest_fingerprint
   seed
   scenario_id
   flow_count_S2
   sessions_with_flows       // count
   sessions_without_flows    // if policy allows them
   ```

5. **Event synthesis summary**

   ```text
   event_type: "6B.S2.EVENT_SYNTHESIS_SUMMARY"
   manifest_fingerprint
   seed
   scenario_id
   event_count_S2
   avg_events_per_flow
   max_events_per_flow
   ```

6. **RNG usage summary**

   ```text
   event_type: "6B.S2.RNG_SUMMARY"
   manifest_fingerprint
   seed
   scenario_id
   rng_family_flow_shape_events
   rng_family_event_timing_events
   rng_family_amount_draw_events
   rng_usage_ok: bool    // local envelope sanity, per §8.2.6
   ```

7. **Partition end**

   ```text
   event_type: "6B.S2.END"
   manifest_fingerprint
   seed
   scenario_id
   status                  // PASS / FAIL
   primary_error_code
   secondary_error_codes   // list
   ```

These logs MUST be sufficient to reconstruct:

* whether S2 ran for a given partition,
* why it failed if it did,
* and high-level statistics about flows/events and RNG usage.

---

### 10.4 Metrics & SLI/monitoring

S2 SHOULD expose metrics that allow operators to monitor health and performance. The **shape** of these metrics is binding; thresholds and dashboards are operational.

Indicative metric set:

* `6B_S2_runs_total`

  * Counter, labels: `status ∈ {"PASS","FAIL"}`.

* `6B_S2_flows_total`

  * Counter, labels: `status`, `scenario_id`.

* `6B_S2_events_total`

  * Counter, labels: `status`, `scenario_id`.

* `6B_S2_failure_primary_code_total`

  * Counter, label: `primary_error_code`.

* `6B_S2_flow_event_mismatch_total`

  * Counter of flows/events that violated consistency (incremented when `S2_FLOW_EVENT_MISMATCH` or `S2_EVENT_SEQUENCE_INVALID` occurs).

* `6B_S2_runtimes_seconds`

  * Histogram or summary, label: `status`.

Implementations MAY expose additional metrics (e.g. distribution of flow types, refund rates per scenario), but MUST ensure that any metric named as above has the semantics described here.

---

### 10.5 Downstream consumption of S2 observability

Downstream states MUST use S2’s run-report status and summary as part of gating and diagnostics:

* **S3 (fraud/abuse overlay)**

  * Before running for `(manifest_fingerprint, seed, scenario_id)`, S3 MUST:

    * check S2’s run-report entry and verify `status="PASS"`.
    * If S2 is `FAIL` or missing, S3 MUST fail early with a precondition error (e.g. `S3_PRECONDITION_S2_FAILED`) and MUST NOT read S2 outputs.

  * S3 MAY use S2’s summary metrics (flow_count, event_count, distributions) to:

    * sanity-check its own campaign overlays,
    * decide whether to thin or augment flows for specific scenarios.

* **S4 (labelling)**

  * BEFORE labelling, S4 MUST ensure that S2 (and S3, if applicable) are PASS for the relevant partitions; it MUST NOT label flows/events for partitions where S2 is FAIL.

* **S5 (6B validation/HashGate)**

  * S5 MUST treat S2’s run-report data as **inputs** to its validation logic:

    * Any S2 partition marked FAIL must cause S5 to fail the corresponding world.
    * Even if S2 reports `status="PASS"`, S5 MUST still cross-check S2 invariants using S2’s outputs and, if inconsistencies are found, override S2’s verdict.

* **4A/4B & external consumers**

  * MUST NOT use S2’s `status` alone to authorise consumption; they gate on the 6B HashGate as a whole.
  * MAY present S2 summary metrics in operator-facing tooling (e.g. “world X / scenario Y has N flows and M events”) for debugging or tuning.

---

### 10.6 Traceability & audit trail

The combination of:

* S2 outputs (`s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`),
* S1 outputs,
* S2 run-report entries, and
* S2 structured logs,

MUST allow an auditor or operator to answer, for any `(manifest_fingerprint, seed, scenario_id)`:

* Did S2 run, and did it succeed or fail?
* How many flows/events were produced, and how do they compare to sessions/arrivals?
* Are flows/events structurally consistent (coverage, temporal and amount consistency)?
* How much RNG was used, and was RNG usage within expected bounds?

Because of this:

* Emitting the run-report entries and logs described above is **not optional**; they are part of S2’s contract.
* Any implementation that omits these observability signals, or emits them in an inconsistent way, is non-conforming even if its data-plane outputs appear structurally correct.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on how to keep S2 practical at scale. It does **not** relax any of the binding constraints in §§1–10; it only suggests implementation strategies that fit inside them.

---

### 11.1 Cost model — where S2 actually spends time

For a given `(manifest_fingerprint, seed, scenario_id)`, S2 does three main things:

1. **Read S1 outputs**

   * Scan `s1_arrival_entities_6B` once.
   * Scan `s1_session_index_6B` once.
   * Optionally join in 6A attributes / upstream context for richer priors (light compared to arrival/event volumes).

2. **Flow planning**

   * For each session:

     * decide `N_flows(session)` (often small, often 1),
     * assign arrivals to flows.
   * Complexity: O(#sessions + #arrivals), with small constant factors.

3. **Event synthesis & writing**

   * For each flow:

     * build an event template,
     * sample timings and amounts,
     * materialise events and anchors.
   * Complexity: O(#flows + #events) for compute + I/O.

Roughly:

```text
Time ~ O(#arrivals + #events + #sessions)
Space ~ O(#sessions + #flows + limited per-session/per-flow state)
```

with `#events` usually a small multiple of `#flows`.

---

### 11.2 Parallelism & work decomposition

S2 parallelises naturally:

* **Across `(seed, scenario_id)` partitions**

  * Each partition is independent: no flows cross `(seed, scenario_id)` boundaries.
  * Recommended: schedule S2 per partition, in parallel where resources allow.

* **Within a partition**

  * After loading S1, the work can be split by **session**:

    * each session’s flows can be planned independently (given shared priors),
    * sessions can be processed in parallel, then flows and events merged with deterministic ordering by `flow_id` / `event_seq`.

Implementation tips:

* If using multi-threading or distributed workers, pick a stable shard key (e.g. `session_id` hash) and ensure:

  * each session is owned by exactly one worker,
  * merges are done via deterministic sort on `[flow_id]` and `[flow_id, event_seq]`.

Parallelism must not break determinism: given the same inputs and RNG config, two runs must still produce the same flows/events.

---

### 11.3 Efficient use of S1 outputs

To avoid S2 becoming arrival-heavy:

* **Index sessions once**

  * Build a map `session_id → session_record` in memory.
  * Build a second map `session_id → [arrival rows]` (or iterators) sorted in time.

* **Avoid repeated joins**

  * Once S1 rows are loaded, avoid re-reading `arrival_events_5B`.
  * If extra upstream context is needed (e.g. 6A posture, 5A intensity), join it onto in-memory S1 structures once per partition.

* **Work streaming-friendly**

  * You don’t need to hold all flows/events in memory:

    * you can process sessions in batches,
    * and stream out flows/events as soon as each batch is finished, as long as final files respect partition and ordering rules.

---

### 11.4 RNG cost & accounting

S2’s RNG load is moderate and should not dominate runtime:

* Typical patterns per partition:

  * 1 draw per session for `N_flows(session)` (if stochastic).
  * 1–few draws per flow for **flow type selection**.
  * 1–few draws per event for **timing**.
  * 1–few draws per flow/event for **amounts**.

* As a rule of thumb:

  ```text
  total RNG draws = O(#sessions + #flows + #events)
  ```

Guidance:

* **Keep family budgets small & predictable**

  * Prefer fixed small budgets per decision (e.g. `1` or `2` draws) over variable-length draws; this simplifies validation.

* **Avoid combinatorial explosion**

  * Do not model hyper-detailed behaviour that requires dozens of draws per event; keep per-event/per-flow RNG requirements simple and governed by config.

---

### 11.5 Memory footprint

Per `(seed, fingerprint, scenario_id)`, memory is mainly used for:

* S1 arrivals + sessions (loaded from parquet).
* S2’s intermediate representation:

  * flow planning data structures,
  * per-session/per-flow contexts.

Guidance:

* **Reuse S1 data**

  * Don’t create deep copies of S1 rows; store indices/offsets where possible.
  * If you need per-flow derived fields, compute them on the fly when emitting anchors/events.

* **Control peak state**

  * If partitions are very large, consider:

    * processing sessions in chunks (e.g. by merchant or by time window),
    * writing flows/events for completed chunks before reading more sessions.

The contract doesn’t mandate chunking, but a streaming/chunked approach keeps memory bounded.

---

### 11.6 I/O considerations

To keep I/O efficient:

* **Read S1 once per partition**

  * One pass over `s1_arrival_entities_6B` and `s1_session_index_6B` is ideal.
  * Avoid multiple full scans; precompute required indices/mappings.

* **Write S2 once per partition**

  * Write `s2_flow_anchor_baseline_6B` and `s2_event_stream_baseline_6B` in single passes.
  * Avoid append/merge patterns that require multiple rewrites; they also violate the merge discipline.

* **Colocate data**

  * Where possible, keep S1 and S2 data in the same storage region/bucket for locality.
  * This reduces cross-region latency when running S2.

---

### 11.7 Tuning partition sizes

S2 inherits partitioning from 5B & S1. If partitions become too big:

* S2 may hit:

  * large per-partition memory requirements,
  * longer wall times for a single S2 task.

Control points live upstream:

* Adjust `(seed, scenario_id)` partitioning in 5B/S1 (outside S2’s spec) if necessary to keep each partition within operational limits.
* S2 itself MUST respect given partitions; it doesn’t re-partition data, but implementations can choose to internally process sub-batches as long as final outputs respect the spec.

---

### 11.8 Monitoring S2 performance

From an operations perspective, you should track:

* Runtime per `(seed, scenario_id)` partition (`6B_S2_runtimes_seconds`).
* `flow_count_S2` and `event_count_S2` vs `session_count_S1` / `arrival_count_S1`.
* Average and p95 events per flow (`avg_events_per_flow`, `p95_events_per_flow`).
* Failure counts by primary error code (`6B_S2_failure_primary_code_total`).

Spikes in runtime or odd flow/event ratios often point to:

* misconfigured flow-shape or amount models,
* sessions with unexpectedly large numbers of flows or events,
* implementation bugs (e.g. N² behaviour when building flows for large sessions).

---

### 11.9 Parallelism vs determinism

S2 is allowed to be parallel, but:

* Parallelism MUST be **structured**:

  * Use deterministic shard keys (e.g. `session_id` or `flow_id` ranges),
  * Avoid any behaviour that depends on thread scheduling (e.g. using non-deterministic iteration order over hash maps without sorting before emit).

* Re-runs of S2 on the same inputs MUST produce logically identical outputs to be considered conformant.

Rule of thumb:

> If you can run S2 twice for the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)` and get identical flows and events, your performance optimisation is compatible with this spec.

Everything else (choice of data structures, thread pools, batching, etc.) is up to the implementation, as long as it respects the binding identity, invariants and determinism rules.

---

## 12. Change control & compatibility *(Binding)*

This section defines how the **6B.S2 contract may evolve over time**, and what counts as **backwards-compatible** vs **breaking**.

It is binding on:

* authors of future S2 specs,
* implementers of S2, and
* downstream consumers (S3, S4, S5, 4A/4B, orchestrators).

The goals are:

* existing worlds and runs remain **replayable**, and
* downstream components can safely **rely on S2’s shapes, identity and invariants**.

---

### 12.1 Versioning surfaces relevant to S2

S2 participates in three version tracks:

1. **`spec_version_6B`**

   * Behavioural contract version for Segment 6B as a whole (S0–S5).
   * Stored in `s0_gate_receipt_6B` and used by orchestration to choose the correct implementation bundle.

2. **Schema packs**

   * `schemas.6B.yaml` – includes S2 anchors:

     * `#/s2/flow_anchor_baseline_6B`
     * `#/s2/event_stream_baseline_6B`
   * `schemas.layer3.yaml` – Layer-3 RNG, gate, and validation schema definitions.

3. **Catalogue artefacts**

   * `dataset_dictionary.layer3.6B.yaml` entries for:

     * `s2_flow_anchor_baseline_6B`
     * `s2_event_stream_baseline_6B`
   * `artefact_registry_6B.yaml` entries for the same datasets.

**Binding rules:**

* For any run of S2, the tuple
  `(spec_version_6B, schemas.6B.yaml version, schemas.layer3.yaml version)`
  MUST be internally consistent and discoverable from the catalogue.
* This document defines S2’s contract for a specific `spec_version_6B` (e.g. `"1.0.0"`). Any **incompatible** change to S2’s contract MUST bump `spec_version_6B`.

---

### 12.2 Backwards-compatible changes

A change to S2 is **backwards-compatible** if:

* Existing consumers of S2 outputs (S3, S4, S5, tooling) built to this spec can still:

  * parse `s2_flow_anchor_baseline_6B` and `s2_event_stream_baseline_6B`, and
  * rely on the identity/partitioning and invariants in §§4–8 without modification.

Examples of **allowed** backwards-compatible changes:

1. **Additive schema extensions**

   * Adding **optional** fields to `s2_flow_anchor_baseline_6B`:

     * e.g. extra diagnostic fields, richer outcome detail, additional derived metrics.
   * Adding **optional** fields to `s2_event_stream_baseline_6B`:

     * e.g. more event-level diagnostics, extended response codes.

   In both cases, existing required fields and their semantics remain unchanged.

2. **New flow/event types with clear defaults**

   * Extending `event_type` enum with new types (e.g. `"PARTIAL_CLEARING"`, `"ADJUSTMENT"`) while:

     * keeping existing types with their semantics intact,
     * ensuring S3/S4/S5 can safely ignore unknown event types (treat as “other”) if they have not yet been updated.

3. **More expressive configuration packs**

   * Extending `flow_shape_policy_6B`, `amount_model_6B`, `timing_policy_6B`, or `flow_rng_policy_6B` with new optional knobs that:

     * default to behaviour equivalent to the current spec, and
     * do not change existing knobs’ meaning.

4. **Internal algorithmic optimisations**

   * Changing S2’s implementation details (e.g. more efficient session sharding, better caching) while:

     * preserving determinism for fixed inputs,
     * preserving the flow/event invariants in §§6–8.

Backwards-compatible changes MAY be rolled out under a **minor** `spec_version_6B` bump (e.g. `1.0.0 → 1.1.0`), provided all binding guarantees from §§1–11 remain valid.

---

### 12.3 Breaking changes

A change is **breaking for S2** if it can cause:

* a consumer expecting the current contract to misinterpret S2 outputs,
* a replay of an existing run (for the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)`) to produce **different** flows/events without a new version boundary, or
* S3/S4/S5 to violate their own contracts because S2 behaviour changed underneath them.

Breaking changes **MUST** be accompanied by a **new major** `spec_version_6B` (e.g. `1.x → 2.0.0`) and updated schemas/catalogues.

Examples of **breaking** changes:

1. **Identity / partition law changes**

   * Changing S2 output partitioning from `[seed, fingerprint, scenario_id]` to any other set (adding/removing axes).
   * Introducing `run_id` (or other axes) as partition keys for `s2_flow_anchor_baseline_6B` or `s2_event_stream_baseline_6B`.
   * Changing primary keys, e.g.:

     * dropping `flow_id` from the flow PK,
     * changing `event_seq` semantics so it is no longer a contiguous per-flow order.

2. **Schema contract changes**

   * Removing or renaming **required** fields in either dataset (e.g. `flow_id`, `session_id`, `event_type`, `event_ts_utc`, `auth_amount`).
   * Changing field types in incompatible ways (e.g. string → int without a migration layer).
   * Changing the semantics of key fields (e.g. redefining `flow_id` to mean “logical customer lifetime flow” instead of “transaction-like flow”).

3. **Relaxing coverage / consistency invariants**

   * Allowing flows without events or events without flows.
   * Removing the requirement that each flow’s timestamps/amounts are consistent with its events.
   * Removing the requirement that `session_id` in S2 anchors must exist in S1 sessions.

4. **RNG contract changes affecting reproducibility**

   * Changing which RNG families S2 uses or their budgets in a way that:

     * changes draw counts per domain without updating the RNG spec and S5 validation,
     * or makes per-family RNG behaviour non-deterministic for fixed inputs.

5. **Changing mapping rules between S1 sessions/arrivals and S2 flows without a new config/version boundary**

   * e.g. moving from “one flow per session” to “one flow per arrival” under the same `parameter_hash` / `spec_version_6B`, so that the same world produces a different number of flows/events.

Any of these changes MUST be treated as **breaking** and gated behind a new major `spec_version_6B`, with:

* updated `schemas.6B.yaml`,
* updated dictionary/registry entries, and
* updated specs for S3–S5 so they know how to consume the new S2 shapes.

---

### 12.4 Interaction with `parameter_hash` and reproducibility

S2 is required to be deterministic for fixed inputs, including fixed `parameter_hash`.

> For fixed upstream inputs and fixed
> `(manifest_fingerprint, parameter_hash, seed, scenario_id)`, S2 outputs MUST be reproducible.

Implications:

* Changes to **flow-shape, amount or timing policies** that alter which flows/events are produced for a given world SHOULD be expressed as:

  * a new **configuration pack** → new `parameter_hash`, and/or
  * a new `spec_version_6B` if they affect the S2 contract itself.

* It is **not acceptable** to:

  * silently change config or implementation in such a way that, under the same `parameter_hash` and `spec_version_6B`, the same `(manifest_fingerprint, seed, scenario_id)` yields different flow/event outputs, while still claiming idempotence.

Operationally:

* Idempotence is scoped to the tuple:

  ```text
  (manifest_fingerprint, parameter_hash, seed, scenario_id)
  ```

* If operators intend to change S2 behaviour (e.g. more retries, different amount distributions), they MUST either:

  * bump and propagate a new `parameter_hash`, or
  * bump `spec_version_6B` if the contract itself changes.

---

### 12.5 Upstream dependency evolution

S2 depends on:

* S1 outputs (`s1_arrival_entities_6B`, `s1_session_index_6B`),
* S0 gate/`sealed_inputs_6B`,
* Layer-2/Layer-3 upstream surfaces (5B arrivals, 6A entities/posture, optional context),
* Layer-3 RNG environment.

**Binding rules for upstream evolution:**

1. **Backwards-compatible upstream changes**

   * Upstream segments MAY add optional fields to S1 outputs, 5B arrivals or 6A tables.
   * S2 MAY ignore or consume those new fields, as long as:

     * its own contract (schema, identity, invariants) remains consistent, and
     * it does not change existing behaviour under the same `parameter_hash` without proper versioning.

2. **Breaking upstream changes**

   * Changes to S1’s identity or invariants (e.g. changing S1’s PKs or session semantics) are breaking for S2.
   * Changes to 5B’s arrival identity that alter `s1_arrival_entities_6B` keys are breaking.
   * Changes to 6A ID/graph semantics that invalidate S1 attachments are also breaking.

   In these cases, S2 MUST be updated and this spec (and `spec_version_6B`) MUST be revised, ideally in lock-step with S1 and the affected upstream segments.

3. **New upstream segments or context surfaces**

   * New upstream context (e.g. a new Layer-2 “calendar” or risk model) that S2 may use purely as enrichment can be added as `OPTIONAL` artefacts in `sealed_inputs_6B` without breaking S2.
   * If S2’s correctness starts to **depend** on new upstream segments being present, that is a breaking change and MUST be reflected in S2’s preconditions and `spec_version_6B`.

---

### 12.6 Co-existence and migration

To support gradual rollout and historical replay:

1. **Co-existence of S2 versions**

   * Orchestrators MUST choose a single `spec_version_6B` per deployment / environment, or at least per `manifest_fingerprint`, when running S2.
   * Implementations for different spec versions MUST NOT both write to the same dataset ids (`s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`) for the same `(manifest_fingerprint, seed, scenario_id)`.

   If multi-version support is required, it SHOULD be implemented by:

   * new dataset ids (e.g. `s2_flow_anchor_baseline_6B_v2`), or
   * separate catalogue entries with distinct paths, with clear documentation.

2. **Reading old S2 outputs**

   * Newer validation or tooling MAY read older S2 outputs for audit/diagnostics, but MUST NOT assume they satisfy the newer contract unless a migration layer is present.
   * Any compatibility or normalisation logic SHOULD be isolated and clearly documented.

3. **Migration path**

   * When bumping to a new major S2 contract (`spec_version_6B`), migration guidance SHOULD specify:

     * whether S2 needs to be re-run for existing worlds, and
     * how to compare or reconcile flows/events across versions if re-run is not possible.

---

### 12.7 Non-negotiable stability points for S2

For the lifetime of this `spec_version_6B`, the following aspects of S2 are **stable** and MUST NOT change without a major version bump:

* S2 produces exactly two datasets:

  * `s2_flow_anchor_baseline_6B` (one row per flow),
  * `s2_event_stream_baseline_6B` (one row per event).

* Both datasets are partitioned by `[seed, fingerprint, scenario_id]` and use the PKs as specified in §§4–7.

* Every event belongs to exactly one flow and every flow has ≥1 event; there are no orphan flows/events.

* Every flow is linked to a valid S1 `session_id` for the same `(seed, fingerprint, scenario_id)`.

* Entity and routing context in S2 outputs are consistent with S1 attachments and upstream surfaces; S2 never invents new entities or break upstream identity laws.

* S3 and S4 treat S2 outputs as the **baseline canvas** and MUST NOT re-derive baseline flows directly from S1 or 5B in ways that contradict S2.

Any future design that wishes to relax or update these stability points MUST:

* define a new major `spec_version_6B`,
* update schemas and catalogue entries accordingly, and
* update S3–S5 specs to explain how they consume the new S2 outputs.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the shorthand and symbols used in the 6B.S2 spec. It is **informative** only; if there’s ever tension, §§1–12 are authoritative.

---

### 13.1 Identity & axes

* **`manifest_fingerprint` / `fingerprint`**
  World snapshot identifier. Partitions S2 outputs at the “world” level and ties them to all upstream HashGates (1A–3B, 5A, 5B, 6A) and 6B.S0.

* **`seed`**
  Stochastic run axis shared with 5B and 6A. S2 outputs are partitioned by `seed` and must be deterministic given `(manifest_fingerprint, parameter_hash, seed, scenario_id)` and fixed inputs.

* **`scenario_id`**
  Scenario axis from 5A/5B (e.g. baseline, stress, campaign). S2 outputs are partitioned by `scenario_id` alongside `seed` and `manifest_fingerprint`.

* **`parameter_hash`**
  Hash of the active 6B behavioural configuration pack (flow-shape/amount/timing/RNG policies, etc.). Carried in control-plane and data-plane surfaces as part of identity, but **not** used as a partition key for S2 outputs.

* **`flow_id`**
  Opaque identifier for a baseline flow/transaction, unique within `(seed, manifest_fingerprint, scenario_id)`. Defined deterministically by S2.

* **`event_seq`**
  Integer sequence number of an event within a flow; defines strict order of events for a given `(seed, manifest_fingerprint, scenario_id, flow_id)`.

---

### 13.2 Dataset shorthands

* **`AE6B`**
  Shorthand for `s1_arrival_entities_6B` — S1’s arrival→entity→session mapping. One row per arrival; S2 uses it as the starting point for flow generation.

* **`SESS`**
  Shorthand for `s1_session_index_6B` — S1’s session index. One row per session with time window and basic aggregates.

* **`FA2`**
  Shorthand for `s2_flow_anchor_baseline_6B` — S2’s flow anchor table. One row per baseline flow/transaction.

* **`EV2`**
  Shorthand for `s2_event_stream_baseline_6B` — S2’s baseline event stream. One row per event; each event belongs to exactly one flow.

* **`AE5B`** (for context)
  `arrival_events_5B` — Layer-2 arrival egress. S2 reads this only as optional context / identity cross-check; S1 is canonical for arrival→entity/session mapping.

---

### 13.3 Keys & relationships

* **Arrival key**
  Inherited from 5B/S1 (shape indicative):

  ```text
  (seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq)
  ```

  S2 refers back to arrivals via fields in S1 outputs (e.g. `merchant_id, arrival_seq`) and any arrival-link fields in the flow anchor.

* **Session key**

  ```text
  (seed, manifest_fingerprint, scenario_id, session_id)
  ```

  Primary key in `s1_session_index_6B`; referenced (FK) by each flow in `FA2`.

* **Flow key**

  ```text
  (seed, manifest_fingerprint, scenario_id, flow_id)
  ```

  Primary key in `FA2`; referenced (FK) by each event in `EV2`.

* **Event key**

  ```text
  (seed, manifest_fingerprint, scenario_id, flow_id, event_seq)
  ```

  Primary key in `EV2`.

These relationships define the join paths:

* S1 sessions → S2 flows → S2 events,
* S1 arrivals → S2 flows (via flow-level arrival linkage fields).

---

### 13.4 Entity & routing context (shorthand)

Entity IDs (all defined and owned by 6A):

* **`party_id`** — primary key in `s1_party_base_6A`.
* **`account_id`** — primary key in `s2_account_base_6A`.
* **`instrument_id`** — primary key in `s3_instrument_base_6A`.
* **`device_id`** — primary key in `s4_device_base_6A`.
* **`ip_id`** — primary key in `s4_ip_base_6A`.

Routing-related fields (owned by Layer-1/5B/3B, copied consistently into S1/S2 where needed):

* **`site_id`** — identifier for physical site (POS/branch) from `site_locations` / 5B.
* **`edge_id`** — identifier for virtual/CDN edge from 3B’s virtual routing.
* **`is_virtual`** — flag showing whether the arrival/flow is virtual.
* **`routing_universe_hash`** — hash binding flows to the routing universe (from 3A/3B contracts).

S2 copies/propagates these fields; it does not own or redefine their semantics.

---

### 13.5 RNG families (names indicative)

Actual RNG families and schema live in the Layer-3 RNG contract; here we just use friendly names:

* **`rng_event_flow_shape`**
  RNG family used when S2 samples:

  * number of flows per session,
  * flow type for a given session/flow.

* **`rng_event_event_timing`**
  RNG family used when S2 samples:

  * event time gaps within flows (auth–auth, auth–clear, clear–refund, etc.).

* **`rng_event_amount_draw`**
  RNG family used when S2 samples transaction amounts and currencies for flows/events.

All S2 randomness MUST go through these (or equivalently defined) S2 families; S2 MUST NOT use RNG families reserved for other states.

---

### 13.6 Error code prefix (S2)

All S2 error codes in §9 follow the prefix pattern:

* **`S2_*`**

Examples (see §9 for semantics):

* `S2_PRECONDITION_S0_OR_S1_FAILED`
* `S2_PRECONDITION_SEALED_INPUTS_INCOMPLETE`
* `S2_PRECONDITION_RNG_POLICY_INVALID`
* `S2_FLOW_ANCHOR_SCHEMA_VIOLATION`
* `S2_EVENT_STREAM_SCHEMA_VIOLATION`
* `S2_AXES_MISMATCH`
* `S2_FLOW_EVENT_MISMATCH`
* `S2_EVENT_SEQUENCE_INVALID`
* `S2_FLOW_EVENT_TEMPORAL_MISMATCH`
* `S2_FLOW_EVENT_AMOUNT_MISMATCH`
* `S2_SESSION_LINKAGE_INVALID`
* `S2_ARRIVAL_LINKAGE_INVALID`
* `S2_ENTITY_CONTEXT_INCONSISTENT`
* `S2_ROUTING_CONTEXT_INCONSISTENT`
* `S2_RNG_EVENT_COUNT_MISMATCH`
* `S2_RNG_STREAM_MISCONFIGURED`
* `S2_OUTPUT_WRITE_FAILED`
* `S2_IDEMPOTENCE_VIOLATION`
* `S2_INTERNAL_ERROR`

---

### 13.7 Miscellaneous

* **“Baseline flow / baseline event”**
  A flow or event produced by S2 under the “all-legit” assumption, prior to any fraud/abuse overlay in S3. Baseline outcomes are non-fraudulent by design.

* **“Plan surface”**
  An internal dataset that is not final Layer-3 egress but is used to drive later states. Both `s2_flow_anchor_baseline_6B` and `s2_event_stream_baseline_6B` are plan surfaces.

* **“Canvas” (informal)**
  When we say “S2 provides the canvas for S3/S4”, we mean: S2’s baseline flows/events are the structures that S3 (fraud overlay) and S4 (labelling) treat as the underlying behaviour to corrupt or annotate.

This appendix is simply a convenience map; all behaviour is defined by the binding sections above.

---