# 6B.S1 — Arrival-to-entity attachment & sessionisation (Layer-3 / Segment 6B)

## 1. Purpose & scope *(Binding)*

6B.S1 is the **first behavioural data-plane state** in Segment 6B.
Its job is to bridge the gap between:

* the **sealed arrival skeleton** from Layer-2 / 5B, and
* the **sealed entity graph + static fraud posture** from Layer-3 / 6A,

by assigning **who** is acting in each arrival, and **which arrivals belong together** as sessions.

Concretely, for a given `(manifest_fingerprint, parameter_hash, seed, scenario_id)`:

* S1 **attaches a concrete entity context** to every arrival in `arrival_events_5B`, choosing:

  * a `party_id` (customer or business party),
  * a primary `account_id` (or account tuple) involved,
  * a primary `instrument_id` (e.g. card or credential) where applicable,
  * a `device_id` and `ip_id` used to generate the traffic,

  such that these identifiers **exist in and respect** the 6A bases and link tables, and are consistent with 6A’s static fraud posture surfaces.

* S1 **groups arrivals into sessions** (and, if required, proto-flows):

  * assigning a `session_id` to each arrival,
  * defining sessions as coherent clusters over time and context (e.g. same party + device + channel + merchant within a governed time window),
  * producing a session index with per-session aggregates and diagnostic features.

This makes S1 the **unique place** in the engine where arrivals are:

> lifted from “anonymous traffic hitting sites/edges” to “traffic attributable to specific customers/accounts/instruments/devices/IPs, organised into sessions”.

### In-scope responsibilities

Within that framing, S1 is responsible for:

* **Entity attachment:**

  * Using 6A’s party/account/instrument/device/IP universes and link tables as the **only authority** for what entity combinations are valid.
  * Applying 6B’s behaviour priors (e.g. how often a party transacts, which accounts/instruments are likely for a given merchant/channel/scenario, how devices/IPs are reused) to rank candidate attachments.
  * Using Philox RNG (under the Layer-3 envelope) to **stochastically resolve** ambiguous choices between valid candidates, in a way that is deterministic given `(manifest_fingerprint, parameter_hash, seed)` and the S1 RNG family definitions.

* **Sessionisation:**

  * Defining a **session identity model** (`session_id`) that is stable within 6B and downstream (S2–S4), and partition-compatible with the rest of Layer-3.
  * Applying governed rules for when sessions start and end (e.g. inactivity timeouts, channel or device breaks), with optional stochastic variation where specified by priors.
  * Ensuring every arrival is assigned to exactly one session, and every session is representable as a compact row in a session index dataset.

* **Producing plan surfaces for downstream behaviour:**

  * Emitting `s1_arrival_entities_6B` as the **authoritative mapping** from arrivals to entity context and session ids.
  * Emitting `s1_session_index_6B` as the **authoritative per-session summary** that later states will use to seed flow generation (S2), campaigns (S3), and label assignment (S4).

S1 **does not** generate any financial events, bank decisions, disputes, or labels; it only defines “who is involved” and “which arrivals belong together”.

### Out-of-scope responsibilities

S1 is explicitly **not** allowed to:

* **Modify upstream facts**:

  * It MUST NOT create, delete, or alter rows in `arrival_events_5B`.
  * It MUST NOT create, delete, or modify any 6A entity or fraud-role row.
  * It MUST NOT alter timestamps, routing information (`site_id`, `edge_id`, `is_virtual`, `routing_universe_hash`), or counts defined by 5B.

* **Override upstream authority**:

  * It MUST NOT introduce new entity keys that do not exist in 6A bases.
  * It MUST NOT reinterpret 6A fraud roles; it may copy them into S1 outputs as context, but cannot change them.

* **Perform segment-level validation or HashGates**:

  * It does not publish any validation bundle or `_passed.flag` for 6B; that is the responsibility of the 6B validation state (S5).
  * It does not re-validate upstream HashGates; it relies on 6B.S0’s gate receipt.

* **Change gating or sealed-input semantics**:

  * It MUST treat `s0_gate_receipt_6B` and `sealed_inputs_6B` as authoritative for “what inputs exist” and “what 6B may read”.
  * It MUST NOT attempt to read artefacts that are not listed in `sealed_inputs_6B`.

### Relationship to the rest of Segment 6B

Within Segment 6B, S1 sits just after S0 and just before the more behaviour-heavy states:

* **Upstream:**

  * S0 has already verified that all required Layer-1, Layer-2 and 6A gates are PASS and has sealed the input universe.
  * S1 will use only those arrivals and entities declared in `sealed_inputs_6B` for its target `manifest_fingerprint`.

* **Downstream:**

  * S2 will treat `s1_arrival_entities_6B` and `s1_session_index_6B` as the **starting point** for constructing baseline transactional flows.
  * S3 will overlay fraud and abuse campaigns on those flows.
  * S4 will use the same mapping to assign truth and bank-view labels.

As a result, if S1 is implemented according to this specification:

* Every arrival that 5B produced will have a well-defined, reproducible entity context and session id.
* Subsequent behaviour states (S2–S4) will not need to rediscover or second-guess attachments; they can focus on **how** flows evolve and **how** fraud manifests, not on **who** is involved.
* The overall engine remains closed and traceable: given a world, a seed, and S1’s RNG logs, an auditor can reconstruct exactly which entity and session each arrival was assigned to, and why.

---

## 2. Preconditions & upstream gates *(Binding)*

This section defines **what must already be true** before 6B.S1 is allowed to run, and what upstream gates it **MUST** honour. If any precondition in this section is not satisfied for the target `manifest_fingerprint`, then S1 **MUST NOT** execute its attachment or sessionisation logic and **MUST** fail fast with a precondition error.

S1 is a **data-plane** state, evaluated over `(manifest_fingerprint, seed, scenario_id)`, with all trust in upstream worlds and contracts delegated to:

* 6B.S0 (behavioural gate & sealed inputs), and
* the upstream segments 1A–3B, 5A, 5B, and 6A (via their HashGates).

---

### 2.1 6B.S0 gate MUST be PASS

For any `manifest_fingerprint`, 6B.S1 **MUST NOT** run unless 6B.S0 has already succeeded for that fingerprint.

Concretely, before doing any work, S1 MUST:

1. Locate `s0_gate_receipt_6B` for the target `manifest_fingerprint` using `dataset_dictionary.layer3.6B.yaml` and `artefact_registry_6B.yaml`.
2. Validate the receipt against `schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B`.
3. Confirm, via the Layer-3 run-report (or equivalent control-plane API), that 6B.S0 is recorded as `status="PASS"` for this fingerprint.

If:

* `s0_gate_receipt_6B` is missing, or
* it fails schema validation, or
* the run-report does not show 6B.S0 as PASS,

then S1 **MUST** treat this as a hard precondition failure and **MUST NOT** proceed to read any upstream datasets (including `arrival_events_5B` or 6A surfaces).

S1 is **not** allowed to bypass S0 or to reconstruct the sealed-inputs universe on its own.

---

### 2.2 Upstream HashGates: transitive precondition

6B.S0 has already verified the HashGates for the upstream segments:

* Layer-1: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
* Layer-2: `5A`, `5B`
* Layer-3: `6A`

S1 does **not** re-compute these HashGates, but it **MUST** treat their status in `s0_gate_receipt_6B.upstream_segments` as binding:

* For each segment id in `{ "1A","1B","2A","2B","3A","3B","5A","5B","6A" }`, S1 MUST check that:

  ```text
  s0_gate_receipt_6B.upstream_segments[SEG].status == "PASS"
  ```

* If any required upstream segment has `status != "PASS"` in the receipt, S1 MUST immediately fail with a precondition error and MUST NOT attempt to read arrivals or entities.

S1 MUST NOT attempt to “repair” an upstream non-PASS status by re-validating or ignoring it. If S0 says a required segment is not PASS for this fingerprint, S1 is not allowed to run.

---

### 2.3 Required sealed-inputs entries

All data-plane inputs S1 reads MUST be discoverable via `sealed_inputs_6B` for the target `manifest_fingerprint`. S1 is **not** permitted to construct dataset locations by hand.

Before processing any `(seed, scenario_id)` partition, S1 MUST:

1. Load `sealed_inputs_6B` for `manifest_fingerprint` and validate it against `schemas.layer3.yaml#/gate/6B/sealed_inputs_6B`.

2. Confirm that the following logical artefacts exist as rows in `sealed_inputs_6B` with:

   * `status = "REQUIRED"`
   * `read_scope = "ROW_LEVEL"`

   **Required arrivals (Layer-2 / 5B)**

   * `owner_layer = 2`, `owner_segment = "5B"`, `manifest_key = "arrival_events_5B"` (or the exact manifest_key used in 5B’s registry).

   **Required entities & posture (Layer-3 / 6A)**

   At minimum:

   * `s1_party_base_6A`
   * `s2_account_base_6A`
   * `s3_instrument_base_6A`
   * `s4_device_base_6A`
   * `s4_ip_base_6A`
   * `s4_device_links_6A`
   * `s4_ip_links_6A`
   * `s5_party_fraud_roles_6A`
   * `s5_account_fraud_roles_6A`
   * `s5_device_fraud_roles_6A`
   * `s5_ip_fraud_roles_6A`

   (and `s5_merchant_fraud_roles_6A` if 6B’s policy marks merchant posture as required for S1).

3. Verify, for each of these rows, that:

   * `schema_ref` resolves into `schemas.5B.yaml` or `schemas.6A.yaml` as expected.
   * `partition_keys` are consistent with the owning segment’s dictionary (e.g. arrivals partitioned by `[seed, fingerprint, scenario_id]`; 6A tables by `[seed, fingerprint]`).

If any required row is missing or malformed, S1 MUST fail with a precondition error (a concrete S1 error code will be defined in its failure section) and MUST NOT read any of the upstream datasets.

Optional context artefacts (e.g. 5A intensity surfaces for enrichment) MAY appear in `sealed_inputs_6B` with `status="OPTIONAL"` and `read_scope` set appropriately; their presence is not a precondition for S1 to run.

---

### 2.4 Seed & scenario coverage

On the **arrival side**, S1 operates over the set of `(seed, scenario_id)` partitions that 5B has produced for this `manifest_fingerprint`.

Before processing a given partition `(seed, scenario_id)` for 6B.S1, the state MUST ensure:

1. That the combination `(seed, fingerprint={manifest_fingerprint}, scenario_id)` exists as a partition of `arrival_events_5B` according to:

   * the 5B dataset dictionary (`dataset_dictionary.layer2.5B.yaml`), and
   * the `path_template` / `partition_keys` recorded in the corresponding `sealed_inputs_6B` row.

2. That 6A has produced entity surfaces for the same `seed` and `manifest_fingerprint`:

   * Each required 6A dataset listed in §2.3 MUST have a partition for `[seed, fingerprint={manifest_fingerprint}]`.
   * If any of those partitions is missing, S1 MUST treat this as a precondition failure for that `(seed, scenario_id)` domain and fail (or skip) the entire S1 run for that `(seed, scenario_id)` according to the orchestration contract.

Semantics for **empty arrivals**:

* If `arrival_events_5B` has **no rows** for a given `(seed, scenario_id)` partition (e.g. legitimate world configuration with zero arrivals), S1 MAY treat this as a trivial PASS for that partition:

  * produce an empty `s1_arrival_entities_6B` and `s1_session_index_6B` for the partition, or
  * skip writing outputs while still recording a PASS in the run-report for that `(seed, scenario_id)` domain.

The choice between “empty outputs” vs “no outputs” for zero-arrival partitions MUST be made once in the 6B.S1 spec and kept consistent; this document assumes **empty outputs** as the default behaviour, but this can be refined later as long as it is fully documented.

In all cases, S1 MUST NOT silently run on a `(seed, scenario_id)` that does not exist in `arrival_events_5B` or for which the corresponding 6A surfaces (for that seed) are missing.

---

### 2.5 Layer-3 RNG and numeric environment

S1 is the first **RNG-consuming** state in 6B. It relies on the Layer-3 RNG and numeric policy environment defined elsewhere (Layer-3 schema pack and layer-wide contracts). As a precondition:

* The Layer-3 Philox RNG envelope and event family definitions MUST be present and valid, as per `schemas.layer3.yaml` and any Layer-3 RNG config artefacts.
* Numeric policy / math profiles (e.g. acceptable floating-point behaviour for priors, probabilities) MUST be available and sealed at Layer-3 level.

S1 itself does not initialise the RNG engine; it attaches to the existing Layer-3 RNG environment. If the engine configuration indicates that the Layer-3 RNG contracts are missing or invalid, S1 MUST fail before attempting any attachment sampling.

---

### 2.6 Prohibited partial or speculative invocations

6B.S1 MUST NOT be invoked under any of the following conditions:

* **Before** 6B.S0 has been run and marked PASS for the target `manifest_fingerprint`.
* With a manually-specified list of datasets or paths that bypasses `sealed_inputs_6B`.
* Against a world where one or more of `{1A,1B,2A,2B,3A,3B,5A,5B,6A}` are not PASS according to `s0_gate_receipt_6B.upstream_segments`.
* In a “speculative” mode that permits continuing execution when required `sealed_inputs_6B` entries or 6A/5B partitions are missing.

If such a situation occurs, the correct behaviour is for S1 to fail early with an appropriate precondition error (to be defined in its failure-mode section), leaving no partial S1 outputs for that `(manifest_fingerprint, seed, scenario_id)`.

These preconditions are binding: any conforming implementation of 6B.S1 MUST check and enforce them before performing any arrival-to-entity attachment or sessionisation work.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **exactly what 6B.S1 may read** and what each input is the **authority for**. Anything outside these boundaries is out of scope for S1 and **MUST NOT** be touched.

S1 is a **data-plane** state. Unlike S0, it reads rows from upstream datasets – but only those explicitly authorised in `sealed_inputs_6B`. It MUST NOT alter any upstream dataset.

---

### 3.1 Engine parameters (implicit inputs)

S1 is evaluated over:

* `manifest_fingerprint` — world snapshot.
* `seed` — stochastic run axis shared with 5B and 6A.
* `scenario_id` — arrival scenario axis from 5A/5B.
* `parameter_hash` — 6B behavioural config pack identifier.

These are supplied by orchestration and/or discovered through `sealed_inputs_6B` and 5B’s dictionary. S1 **MUST NOT** infer or modify these values from wall-clock or environment.

---

### 3.2 6B control-plane inputs (S0 outputs)

S1 depends on the two S0 outputs and treats them as **control-plane authority**:

1. **`s0_gate_receipt_6B`**

   * Authority for:

     * which upstream segments are PASS for this `manifest_fingerprint`,
     * which contract/parameter pack (`parameter_hash`, `spec_version_6B`) S1 must honour,
     * the `sealed_inputs_digest_6B` S1’s behaviour is bound to.
   * S1 MUST NOT run if this receipt is missing or invalid.

2. **`sealed_inputs_6B`**

   * Authority for:

     * which artefacts S1 is allowed to read,
     * their `path_template`, `partition_keys`, `schema_ref`, `role`, `status`, `read_scope`.
   * S1 MUST use `sealed_inputs_6B` as its **sole source of dataset locations**; it MUST NOT construct paths by hand or read artefacts not listed here.

S1 may only resolve concrete dataset paths (for arrivals, entities, config) via `sealed_inputs_6B` + the owning segment’s dictionary/registry.

---

### 3.3 Arrival skeleton (Layer-2 / 5B)

S1’s **only arrival input** is the egress from 5B:

* **`arrival_events_5B`** (or the manifest_key used in 5B for arrival egress), as recorded in `sealed_inputs_6B` with:

  * `owner_layer = 2`, `owner_segment = "5B"`,
  * `status = "REQUIRED"`, `read_scope = "ROW_LEVEL"`.

For each `(seed, manifest_fingerprint, scenario_id)` domain, `arrival_events_5B` is the **sole authority** on:

* which arrivals exist (`arrival_id`, PK),
* when they occur (`ts_utc`, bucket index),
* where they occur (merchant, zone_representation, routing fields: `site_id` or `edge_id`, `is_virtual`, `routing_universe_hash`),
* scenario identity (`scenario_id`),
* any upstream context fields (e.g. λ_realised, physical/virtual flags).

Binding rules:

* S1 **MUST** read arrivals only via this dataset.
* S1 **MUST NOT**:

  * create or delete arrival rows,
  * change arrival timestamps, bucket indices, or routing fields,
  * alter 5B-provided identifiers (`arrival_id`, `scenario_id`, `seed`, `manifest_fingerprint`).

All S1 outputs that refer to arrivals MUST do so via `arrival_events_5B`’s primary key.

---

### 3.4 Entity & posture inputs (Layer-3 / 6A)

S1 reads the 6A entity graph and static fraud posture for the same `(seed, manifest_fingerprint)` world. These datasets MUST appear in `sealed_inputs_6B` with `status="REQUIRED"` and `read_scope="ROW_LEVEL"`:

* **Party base**

  * `s1_party_base_6A`
  * Authority for all `party_id` values and party attributes (type, geography, segments).

* **Account & product base**

  * `s2_account_base_6A`
  * Authority for all `account_id` values and their linkage to `party_id` / merchants.

* **Instrument base & links**

  * `s3_instrument_base_6A`
  * `s3_account_instrument_links_6A` (or equivalent)
  * Authority for `instrument_id` values and which accounts/parties/merchants they belong to.

* **Device & IP base**

  * `s4_device_base_6A`
  * `s4_ip_base_6A`
  * Authority for `device_id`, `ip_id` values and their static types/properties.

* **Graph links**

  * `s4_device_links_6A` — device→party/account/instrument/merchant edges.
  * `s4_ip_links_6A` — ip→device/party/merchant edges.
    These are the **only authorities** for which entities are linked (e.g. which devices belong to which parties).

* **Static fraud posture**

  * `s5_party_fraud_roles_6A`
  * `s5_account_fraud_roles_6A`
  * `s5_device_fraud_roles_6A`
  * `s5_ip_fraud_roles_6A`
  * (`s5_merchant_fraud_roles_6A` if 6B uses it in S1)
    These tables are the **only authority** for static fraud roles; S1 may copy posture into its outputs but MUST NOT change it.

Binding rules:

* S1 MAY join all 6A tables by `seed` and `manifest_fingerprint` to derive candidate entity sets per arrival.
* S1 MUST treat these datasets as **read-only facts**:

  * It MUST NOT add, delete, or mutate any entity, link, or posture row.
  * It MUST NOT introduce new IDs for parties/accounts/instruments/devices/IPs.

All entity IDs written into S1 outputs MUST exist in the corresponding 6A base tables.

---

### 3.5 Behaviour priors & sessionisation configuration (Layer-3 / 6B)

S1 uses 6B-local configuration and prior packs to decide **how** to attach entities and define sessions. These artefacts are registered under 6B and MUST appear in `sealed_inputs_6B` with appropriate roles, e.g.:

* `behaviour_prior_pack_6B` (or equivalent)

  * Role: `behaviour_prior`
  * Authority for:

    * per-segment/channel/geo distributions of:

      * visit frequencies,
      * account/instrument selection preferences,
      * device/IP reuse behaviours,
      * multi-merchant and multi-channel patterns.

* `sessionisation_policy_6B` (may be part of behaviour priors or separate)

  * Role: `behaviour_prior` or `session_policy`
  * Authority for:

    * session boundary rules (timeout thresholds, maximum gaps),
    * identity of “session key” dimensions (e.g. {party, device, merchant, channel}),
    * any stochastic variation in session formation.

* Optional:

  * `entity_attachment_policy_6B` — explicit attachment rules and tie-breakers,
  * `rng_policy_6B_S1` — binding of Philox substreams / event families for S1 (if separated from layer-wide RNG config).

Binding rules:

* S1 MUST read these packs via `sealed_inputs_6B` and their `schema_ref` anchors.
* S1 MUST NOT interpret or alter any configuration that is not validated against its schema.
* S1 MUST NOT hard-code priors in code; all stochastic decisions (within S1’s remit) MUST be driven by these packs or by deterministic functions of upstream data.

These packs guide attachment and sessionisation, but **do not define new entities or arrivals**; they only shape how S1 selects among entities defined by 6A and arrivals defined by 5B.

---

### 3.6 Optional context inputs (METADATA or enrichment only)

Depending on the 6B spec version, S1 MAY also use optional context artefacts, with `status="OPTIONAL"` in `sealed_inputs_6B`. Examples include:

* **Intensity & scenario context (Layer-2 / 5A)**

  * `merchant_zone_baseline_local_5A`, `merchant_zone_scenario_local_5A`
  * Role: `context`
  * Usage: as features for attachment/session priors (e.g. “is this arrival in a high-traffic period?”).
  * Scope: `ROW_LEVEL` or `METADATA_ONLY` as per policy.

* **Routing/grouping context (Layer-2 / 5B)**

  * `s1_grouping_5B` or other non-arrival 5B plan shapes
  * Role: `context`
  * Usage: only as attachment features, not as an alternative source of arrivals.

Binding rules:

* These inputs MUST be listed in `sealed_inputs_6B` if S1 uses them.
* S1 MUST treat them as **non-authoritative** for arrivals or entities:

  * They may inform probabilities, but they cannot change which arrivals or entities exist.

If a context artefact marked `OPTIONAL` is missing, S1 MUST degrade gracefully (e.g. fall back to default priors) rather than failing the run.

---

### 3.7 Authority boundaries & prohibitions

To make the boundaries explicit:

* **Authority for arrivals**:

  * `arrival_events_5B` is the **only** source of arrival identity, counts, timestamps, routing and scenario.
  * S1 MUST NOT change these facts.

* **Authority for entities & fraud posture**:

  * 6A surfaces are the **only** source of party/account/instrument/device/IP/merchant IDs, their static attributes, and their static fraud roles.
  * S1 MUST NOT invent new IDs, rewire links, or change posture.

* **Authority for “what S1 may read”**:

  * `sealed_inputs_6B` is the **only** inventory of inputs; S1 MUST NOT read any artefact not listed there, nor read beyond `read_scope`.

* **Authority for “how S1 behaves”**:

  * 6B behavioural, attachment and sessionisation policies are the only source of knobs that change how S1 attaches entities and forms sessions.
  * S1 MUST NOT embed additional hidden policy in code that is not captured by these packs.

Anything that tries to:

* bypass `sealed_inputs_6B`,
* reinterpret upstream HashGates,
* change upstream data, or
* introduce new identity axes,

is outside S1’s authority and MUST be treated as a violation of this specification.

---

## 4. Outputs (datasets) & identity *(Binding)*

6B.S1 produces two **internal plan surfaces** for Segment 6B:

1. `s1_arrival_entities_6B` — arrival stream enriched with entity assignments and session ids.
2. `s1_session_index_6B` — one row per session, summarising the session context and basic diagnostics.

These outputs are:

* **Layer-3 / 6B–owned** datasets (not cross-layer egress).
* **Required** for downstream 6B states (S2–S4) and 6B validation (S5).
* Partitioned on the same axes as 5B’s arrivals: `[seed, fingerprint, scenario_id]`.

No other datasets may be written by S1.

---

### 4.1 `s1_arrival_entities_6B` — arrival→entity & session mapping

**Dataset id**

* `id: s1_arrival_entities_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

For each arrival row produced by 5B in `arrival_events_5B`, S1 emits exactly one row in `s1_arrival_entities_6B` that:

* preserves the arrival’s original identity and context (keys, timestamps, routing, scenario), and
* adds the **entity attachment** and **session key** fields:

  * `party_id` (or equivalent customer/party id),
  * `account_id` (or account tuple),
  * `instrument_id` (where applicable),
  * `device_id`,
  * `ip_id`,
  * `session_id` (session key S1 defines),
  * attachment provenance (e.g. attachment rule id, prior bucket id, RNG family version).

This dataset is the **single source of truth** in 6B for “which entity context and session each arrival belongs to”.

**Format, path & partitioning**

In the 6B dataset dictionary / artefact registry, this dataset MUST be registered as:

* `version: '{seed}.{manifest_fingerprint}.{scenario_id}'`

* `format: parquet`

* `path` (template):

  ```text
  data/layer3/6B/s1_arrival_entities_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `partitioning: [seed, fingerprint, scenario_id]`

The `manifest_fingerprint` column embedded in rows MUST match the `fingerprint` partition token. The `seed` and `scenario_id` columns MUST match the corresponding tokens in the path.

**Primary key & identity**

S1 MUST adopt and extend the **arrival identity** from 5B, not invent a new one. Concretely:

* Primary key:

  ```text
  [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
  ```

  where:

  * `seed`, `manifest_fingerprint`, `scenario_id`, `merchant_id`, `arrival_seq` are exactly as defined in `arrival_events_5B`.

* All columns required by `schemas.5B.yaml#/model/arrival_events_5B` that carry arrival identity and routing MUST be present and unchanged (S1 only adds columns, it does not modify 5B’s fields).

The writer ordering MUST be:

```text
[seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
```

(or equivalently, `scenario_id, merchant_id, ts_utc, arrival_seq` within a `(seed, fingerprint)` partition, as long as dictionary and schema agree). The key point is:

* every arrival from 5B appears exactly once in `s1_arrival_entities_6B`,
* tied to the same PK columns, with new entity/session fields layered on top.

**Schema anchor**

The logical shape MUST be defined in the 6B schema pack as:

```text
schemas.6B.yaml#/s1/arrival_entities_6B
```

This schema:

* MUST include all key and core context fields from `arrival_events_5B` (via `$ref` or duplication) as **required**, and
* MUST add entity and session fields (and attachment/provenance fields) as required/optional according to the S1 spec.

The 6B dataset dictionary MUST use this anchor as `schema_ref` for `s1_arrival_entities_6B`.

**Lineage**

In `dataset_dictionary.layer3.6B.yaml`:

* `produced_by: [ '6B.S1' ]`
* `consumed_by: [ '6B.S2', '6B.S3', '6B.S4', '6B.S5' ]`

In `artefact_registry_6B.yaml`:

* `final_in_layer: false` (internal plan surface, not Layer-3 egress).

---

### 4.2 `s1_session_index_6B` — session summary

**Dataset id**

* `id: s1_session_index_6B`
* `owner_layer: 3`
* `owner_segment: 6B`

**Purpose**

`s1_session_index_6B` holds one row per session, summarising:

* a stable `session_id` for the `(seed, manifest_fingerprint, scenario_id)` domain,
* the entity context for that session (e.g. primary party/account/instrument/device/ip),
* key session-level aggregates:

  * `arrival_count` (number of arrivals in this session),
  * `session_start_utc`, `session_end_utc`,
  * session duration and intra-session gap statistics,
  * channel/merchant mix indicators,
  * static posture hints (e.g. whether the session is backed by a high-risk entity according to 6A roles).

Downstream states (S2–S4) may use this index as a convenient way to:

* seed flow construction (one flow per session or per subset of a session), and
* implement campaign selection over sessions.

**Format, path & partitioning**

The session index MUST be registered as:

* `version: '{seed}.{manifest_fingerprint}.{scenario_id}'`

* `format: parquet`

* `path` (template):

  ```text
  data/layer3/6B/s1_session_index_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `partitioning: [seed, fingerprint, scenario_id]`

As with arrivals, the embedded `manifest_fingerprint`, `seed`, and `scenario_id` columns MUST match the path tokens.

**Primary key & identity**

Session identity for S1 outputs is defined per `(seed, manifest_fingerprint, scenario_id)`:

* Primary key:

  ```text
  [seed, manifest_fingerprint, scenario_id, session_id]
  ```

Where:

* `session_id` is a stable, opaque identifier for the session (e.g. a 64-bit integer or id64 string) whose type is defined in `schemas.6B.yaml#/s1/session_index_6B` via a `$defs/id64`-style constraint.

Within a given `(seed, manifest_fingerprint, scenario_id)`:

* Each session id MUST appear exactly once in `s1_session_index_6B`.
* Every `session_id` referenced in `s1_arrival_entities_6B` MUST exist in `s1_session_index_6B`.

Writer ordering MUST be:

```text
[seed, manifest_fingerprint, scenario_id, session_id]
```

**Schema anchor**

The logical shape MUST be defined as:

```text
schemas.6B.yaml#/s1/session_index_6B
```

At a minimum, this schema MUST require:

* `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`, `session_id`,
* `session_start_utc`, `session_end_utc`,
* `arrival_count`,

and any core entity context fields that S1 is expected to surface at the session level (e.g. primary `party_id` / `device_id`). Additional diagnostic fields MAY be added as optional.

The 6B dataset dictionary MUST use this anchor as `schema_ref` for `s1_session_index_6B`.

**Lineage**

In `dataset_dictionary.layer3.6B.yaml`:

* `status: required` (S2–S4 rely on it).
* `produced_by: [ '6B.S1' ]`
* `consumed_by: [ '6B.S2', '6B.S3', '6B.S4', '6B.S5' ]`

The artefact registry MUST mark it as `final_in_layer: false`.

---

### 4.3 Relationship to arrivals & identity consistency

To avoid ambiguity:

* `s1_arrival_entities_6B` and `s1_session_index_6B` MUST share the same identity axes (`seed`, `manifest_fingerprint`, `scenario_id`).

* Every arrival row in `arrival_events_5B@{seed,fingerprint,scenario_id}`:

  * MUST produce exactly one row in `s1_arrival_entities_6B` with the same arrival key (`seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq`), and
  * MUST be assigned to exactly one `session_id` that appears in `s1_session_index_6B`.

* No additional partition axes (e.g. `run_id`) may be introduced into S1’s outputs; `run_id` remains a runtime/RNG concern, not a partitioning key.

These identity rules ensure that:

* S1’s outputs are straightforward to join back to 5B arrivals and forward into S2–S4, and
* S1 remains a pure “enrichment + grouping” layer on top of the sealed arrival skeleton and sealed 6A entities, without altering upstream identity.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes the **logical shapes**, **schema anchors** and **catalogue wiring** for the two datasets produced by 6B.S1:

* `s1_arrival_entities_6B`
* `s1_session_index_6B`

It also defines how these shapes relate to upstream schemas (5B arrivals, 6A entities) and how they must appear in the Layer-3 dataset dictionary and artefact registry.

JSON-Schema files remain the **single source of truth** for shapes. The dataset dictionary and artefact registry **MUST** reflect those schemas; where they diverge, schemas win and the catalogue MUST be corrected.

---

### 5.1 Schema anchors in `schemas.6B.yaml`

The 6B segment schema pack **MUST** define the following anchors:

* Arrival→entity/session mapping:

```text
schemas.6B.yaml#/s1/arrival_entities_6B
```

* Session index:

```text
schemas.6B.yaml#/s1/session_index_6B
```

These anchors are binding:

* `dataset_dictionary.layer3.6B.yaml` **MUST** use them as `schema_ref` for the corresponding dataset ids.
* `artefact_registry_6B.yaml` **MUST** point its `schema` fields at the same anchors.

---

### 5.2 `s1_arrival_entities_6B` shape

#### 5.2.1 Relationship to `arrival_events_5B`

`schemas.6B.yaml#/s1/arrival_entities_6B` **MUST** be defined so that:

* All core identity and context fields from 5B’s arrival egress are present and required. This can be achieved in two ways:

  * via a `$ref` to a “base arrival” definition, e.g.:

    ```json
    { "allOf": [
      { "$ref": "schemas.5B.yaml#/s4/arrival_events_5B_core" },
      { "type": "object", "properties": { ... S1 additions ... } }
    ]}
    ```

  * or by explicitly inlining the relevant subset of fields (PK, scenario, routing, timestamps) with identical names and types.

* No field inherited from 5B may change type or semantics. In particular:

  * `seed`, `manifest_fingerprint`, `scenario_id`, `merchant_id`, `arrival_seq`, `ts_utc`, and routing fields (`site_id`/`edge_id`, `is_virtual`, `routing_universe_hash`) MUST be present and unchanged.

S1’s schema MUST be clear that it **extends** the arrival record; it does not redefine it.

#### 5.2.2 New fields defined by S1

The `arrival_entities_6B` schema MUST add, at minimum, the following fields (names indicative; exact names are to be finalised in the schema file):

* Entity attachments:

  * `party_id` — foreign key into `schemas.6A.yaml#/s1/party_base_6A`.
  * `account_id` — foreign key into `schemas.6A.yaml#/s2/account_base_6A`.
  * `instrument_id` — foreign key into `schemas.6A.yaml#/s3/instrument_base_6A` (nullable for arrivals without a payment instrument).
  * `device_id` — foreign key into `schemas.6A.yaml#/s4/device_base_6A`.
  * `ip_id` — foreign key into `schemas.6A.yaml#/s4/ip_base_6A` (nullable where not applicable).

* Session:

  * `session_id` — S1-defined session identifier, unique only within `(seed, manifest_fingerprint, scenario_id)`; type usually constrained via `$defs/id64` or equivalent.

* Provenance / diagnostics (minimally):

  * `attach_rule_id` — which attachment rule/strategy was applied.
  * `attach_score` / `attach_rank` (optional) — numeric score or rank among candidates.
  * `attach_rng_family` — which RNG family was used for the final attachment decision.
  * `static_posture_flags` (optional) — small summary of 6A posture (e.g. `party_risk_flag`, `device_risk_flag`) copied from 6A for convenience.

All new fields MUST be described in the schema with clear type constraints (string/integer/enums, nullability rules) and FK/semantic notes referencing the appropriate 6A anchors.

#### 5.2.3 Dictionary entry

`dataset_dictionary.layer3.6B.yaml` **MUST** include:

```yaml
- id: s1_arrival_entities_6B
  status: required
  owner_layer: 3
  owner_segment: 6B
  description: >
    Arrival events from 5B enriched with entity attachments and session identifiers
    for Layer-3 behaviour.
  version: '{seed}.{manifest_fingerprint}.{scenario_id}'
  format: parquet
  path: data/layer3/6B/s1_arrival_entities_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  partitioning: [seed, fingerprint, scenario_id]
  primary_key: [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
  ordering: [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
  schema_ref: schemas.6B.yaml#/s1/arrival_entities_6B
  produced_by: [6B.S1]
  consumed_by: [6B.S2, 6B.S3, 6B.S4, 6B.S5]
```

Binding points:

* `partitioning`, `primary_key`, and `ordering` MUST match the identity model agreed in §4.
* `schema_ref` MUST match the anchor in `schemas.6B.yaml`.

#### 5.2.4 Artefact registry entry

`artefact_registry_6B.yaml` **MUST** register the dataset consistently, for example:

```yaml
- manifest_key: s1_arrival_entities_6B
  type: dataset
  category: plan
  environment: engine
  owner_layer: 3
  owner_segment: 6B
  schema: schemas.6B.yaml#/s1/arrival_entities_6B
  path_template: data/layer3/6B/s1_arrival_entities_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  partitioning: [seed, fingerprint, scenario_id]
  final_in_layer: false
```

Any additional registry fields (e.g. retention, encryption class) MAY be added but MUST NOT change these core properties.

---

### 5.3 `s1_session_index_6B` shape

#### 5.3.1 Core fields

`schemas.6B.yaml#/s1/session_index_6B` MUST define, at minimum, the following required fields:

* Identity / axes:

  * `manifest_fingerprint: string`
  * `parameter_hash: string`
  * `seed: integer|string` (matching upstream convention)
  * `scenario_id: string|integer`
  * `session_id: string|integer` — constrained by a shared `id` format (e.g. `id64`).

* Temporal:

  * `session_start_utc: string` (ISO-8601, UTC).
  * `session_end_utc: string` (ISO-8601, UTC).
  * `session_duration_seconds: integer` (non-negative).

* Aggregates:

  * `arrival_count: integer` (non-negative).

* Entity context (at least one of the following, depending on S1 design):

  * `primary_party_id` (nullable if session is not attached to a single party).
  * `primary_device_id` (e.g. main device used in this session).
  * `primary_ip_id` (e.g. main IP used).

Additionally, the schema SHOULD allow optional diagnostic fields, for example:

* `channel_set` (set/array of channels observed).
* `merchant_set` (set/array of merchants touched in the session).
* `posture_summary` (compact representation of 6A risk posture for entities involved).

These MAY be added as optional properties and MUST NOT be required by the core contract.

#### 5.3.2 Dictionary entry

The dataset dictionary entry for the session index MUST look like:

```yaml
- id: s1_session_index_6B
  status: required
  owner_layer: 3
  owner_segment: 6B
  description: >
    Session-level summary for Layer-3 behaviour; one row per session with
    identity, time window, aggregates, and entity context.
  version: '{seed}.{manifest_fingerprint}.{scenario_id}'
  format: parquet
  path: data/layer3/6B/s1_session_index_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  partitioning: [seed, fingerprint, scenario_id]
  primary_key: [seed, manifest_fingerprint, scenario_id, session_id]
  ordering: [seed, manifest_fingerprint, scenario_id, session_id]
  schema_ref: schemas.6B.yaml#/s1/session_index_6B
  produced_by: [6B.S1]
  consumed_by: [6B.S2, 6B.S3, 6B.S4, 6B.S5]
```

Binding points:

* `status: required` — downstream states rely on this surface.
* PK and ordering MUST align with the identity semantics in §4.

#### 5.3.3 Artefact registry entry

The artefact registry MUST register the session index consistently, e.g.:

```yaml
- manifest_key: s1_session_index_6B
  type: dataset
  category: plan
  environment: engine
  owner_layer: 3
  owner_segment: 6B
  schema: schemas.6B.yaml#/s1/session_index_6B
  path_template: data/layer3/6B/s1_session_index_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  partitioning: [seed, fingerprint, scenario_id]
  final_in_layer: false
```

---

### 5.4 Cross-links & FK expectations (informative but strongly recommended)

While JSON-Schema does not enforce foreign keys, the shapes defined above assume:

* In `s1_arrival_entities_6B`:

  * `party_id` ∈ `s1_party_base_6A.party_id` for the same `(seed, manifest_fingerprint)`.
  * `account_id` ∈ `s2_account_base_6A.account_id`.
  * `instrument_id` ∈ `s3_instrument_base_6A.instrument_id` (when non-null).
  * `device_id` ∈ `s4_device_base_6A.device_id`.
  * `ip_id` ∈ `s4_ip_base_6A.ip_id` (when non-null).
  * `session_id` ∈ `s1_session_index_6B.session_id` for the same `(seed, manifest_fingerprint, scenario_id)`.

* In `s1_session_index_6B`:

  * `session_id` set matches exactly the session ids used in `s1_arrival_entities_6B` for the same axes.

These FK relationships will be enforced by the 6B validation state (S5), not by S1 itself, but S1’s schemas and dictionary wiring are designed to make such checks straightforward.

---

### 5.5 Summary

In summary, this section binds:

* The schema anchors for S1 outputs in `schemas.6B.yaml`.
* Their identity, partitioning, and ordering in `dataset_dictionary.layer3.6B.yaml`.
* Their artefact-level wiring in `artefact_registry_6B.yaml`.

Any implementation of 6B.S1 MUST produce outputs that conform to these shapes and catalogue links, so that:

* S2–S4 can consume them without special-case logic, and
* the 6B validation/HashGate state can reason about them uniformly alongside upstream surfaces.

---

## 6. Deterministic algorithm (with RNG) *(Binding)*

This section specifies **how** 6B.S1 behaves for a given
`(manifest_fingerprint, parameter_hash, seed, scenario_id)`.

S1 is **data-plane + RNG-consuming**:

* Deterministic given:

  * `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`,
  * upstream datasets (5B arrivals, 6A entities, posture),
  * 6B attachment & sessionisation policies,
  * Layer-3 Philox RNG contracts (streams/families).
* All stochastic choices must go through **Layer-3 RNG event families** reserved for S1; no ad-hoc RNG.

At a high level, per `(seed, scenario_id)` S1:

1. Discovers scope (which arrivals and upstream inputs exist).
2. Loads 6A entities/posture and builds indices.
3. Computes attachment candidates and priors per arrival.
4. Uses Philox to sample entity attachments where needed.
5. Defines sessions and session_ids (deterministic + optional RNG).
6. Emits `s1_arrival_entities_6B` and `s1_session_index_6B` with strict coverage and FK invariants.

If any step fails to meet the constraints in this section, S1 MUST fail for that `(seed, scenario_id)` and MUST NOT publish partial outputs.

---

### 6.1 Determinism & RNG envelope

**Binding constraints:**

1. **Pure function + Philox:**
   For fixed `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id` and fixed upstream/6B inputs, S1’s outputs MUST be bit-for-bit reproducible across runs, assuming the same Layer-3 RNG spec and run_id (if used for logging).

2. **RNG families:**
   All random draws in S1 MUST use Philox through a small, fixed set of event families reserved for this state, for example:

   * `rng_event_entity_attach` — sampling entity attachments for an arrival.
   * `rng_event_session_boundary` — sampling session boundaries / dwell times (if stochastic).

   The exact schema and budgets (`blocks`, `draws`) for these families are defined in the Layer-3 RNG spec; S1 MUST NOT introduce ad-hoc RNG families or bypass that contract.

3. **Non-consuming vs consuming:**

   * When an attachment/session decision is **deterministic** (e.g. exactly one candidate), S1 MUST NOT consume Philox draws for that decision, but MAY emit a non-consuming RNG event envelope if required by the Layer-3 RNG law.
   * When a decision is **stochastic**, S1 MUST use a fixed, documented number of Philox draws per decision, as defined in the RNG spec, so that RNG accounting is auditable by the 6B validation state.

4. **No data-dependent stream selection:**
   S1 may parameterise RNG substream keys (e.g. by `seed`, `manifest_fingerprint`, `scenario_id`, `arrival_id`), but MUST NOT choose different **families** or change budgets based on data in a way that breaks per-family accounting.

---

### 6.2 Step 0 — Discover S1 work domain

Given `manifest_fingerprint`:

1. Read `sealed_inputs_6B` and `s0_gate_receipt_6B`.

2. Discover the set of `(seed, scenario_id)` pairs for which `arrival_events_5B` has partitions:

   * Using the path template and `partition_keys` recorded in the `arrival_events_5B` row of `sealed_inputs_6B`, combined with the 5B dictionary/registry.

3. For each `(seed, scenario_id)` partition:

   * Confirm that required 6A datasets for `(seed, manifest_fingerprint)` exist (as per §2.4).
   * Optionally apply a filter (e.g. only scenarios enabled by 6B policies).

S1 MAY process different `(seed, scenario_id)` partitions in parallel, but each partition MUST be treated independently: no cross-partition attachment or session logic.

---

### 6.3 Step 1 — Load upstream entities & build indices

For a fixed `(seed, manifest_fingerprint)`:

1. **Load 6A bases and links** with `status="REQUIRED"`, `read_scope="ROW_LEVEL"` from `sealed_inputs_6B`:

   * Parties: `s1_party_base_6A`.
   * Accounts: `s2_account_base_6A`.
   * Instruments: `s3_instrument_base_6A`.
   * Devices & IPs: `s4_device_base_6A`, `s4_ip_base_6A`.
   * Links: `s4_device_links_6A`, `s4_ip_links_6A`, `s3_account_instrument_links_6A` (or equivalent).

2. **Load static fraud posture** surfaces:

   * `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A` (and merchant roles if used in S1).

3. Build in-memory indices keyed for efficient lookup, for example:

   * `party_id → { party attributes, posture }`.
   * `party_id → [accounts]`.
   * `account_id → [instruments]`.
   * `party_id / device_id / merchant_id → [devices/IPs]`.
   * `device_id → linked parties/accounts/merchants`.
   * `ip_id → linked devices/parties/merchants`.

The exact data structures are implementation detail, but:

* S1 MUST ensure that any entity ID it writes to its outputs can be validated back to a row in the appropriate 6A base table.
* S1 MUST NOT mutate or filter out entities in a way that changes the effective universe; filtering must be driven only by business logic (priors, channels, etc.) and must not contradict 6A’s existence facts.

---

### 6.4 Step 2 — Attachments: candidate sets & priors

For each `(seed, scenario_id)` partition:

1. **Load arrivals** for `(seed, manifest_fingerprint, scenario_id)` from `arrival_events_5B`.

2. For each arrival `r` (with keys from 5B: `arrival_id` or `(merchant_id, arrival_seq)` plus context fields such as merchant, zone, channel, routing):

   * Construct one or more **candidate sets** for each entity dimension:

     * Candidate parties: e.g. all parties in certain segments / geos consistent with the merchant and scenario, respecting 6A links if pre-bound (e.g. card-on-file).
     * Candidate accounts/instruments: from party’s holdings, optionally filtered by merchant, channel, ccy.
     * Candidate devices/IPs: from device/IP graph, filtered by parties, merchants, regions.

   * Use 6B behaviour priors and configuration packs to compute **attachment priors**, e.g.:

     * per-candidate scores / probabilities for party selection,
     * per-candidate scores for account/instrument selection,
     * per-candidate scores for device/IP reuse vs fresh device/IP.

   * Normalise priors where required so that per-arrival candidate probabilities form proper distributions (Σ=1) or structured mixtures as per policy.

3. For deterministic cases:

   * If a dimension has an unambiguous candidate (single candidate, probability 1 by policy), S1 MUST mark that attachment as deterministic and record the chosen entity without consuming RNG.

4. For ambiguous cases:

   * If more than one valid candidate exists and policy permits multiple, S1 MUST mark this dimension as **stochastic** and prepare to sample with Philox in Step 3.

S1 MUST NOT generate candidates that violate 6A constraints (e.g. accounts that do not belong to the chosen party, devices not linked to that party/merchant unless policy explicitly allows “new” entities and such entities are created in 6A beforehand).

---

### 6.5 Step 3 — Sample entity attachments (with RNG)

For each arrival `r` and each entity dimension marked as stochastic in Step 2:

1. **Select RNG family & key:**

   * Use `rng_event_entity_attach` (or equivalent family) with a key derived from:

     ```text
     (manifest_fingerprint, seed, scenario_id, arrival_id, dimension)
     ```

     or another deterministic composition defined in the Layer-3 RNG spec.

2. **Sample candidate index(es):**

   * Draw the required number of uniforms from Philox (e.g. one for party, one for device, etc.), as defined in the RNG budget per family.
   * Map uniforms to candidate indices according to the attachment prior distribution for that dimension.

3. **Record attachment & provenance:**

   * Commit the chosen `party_id`, `account_id`, `instrument_id`, `device_id`, `ip_id` for the arrival.
   * Store:

     * `attach_rule_id` indicating which rule/branch of policy was used.
     * Optional `attach_score` / candidate score for the chosen entity.
     * Identification of the RNG family/version used (e.g. via `attach_rng_family`).

4. **RNG accounting:**

   * Ensure that for each RNG-consuming decision, exactly the configured number of draws is used and recorded in the RNG logs.
   * For deterministic decisions (single candidate), no Philox draws are consumed for that dimension.

After Step 3, every arrival has a **complete entity context** `{party, account, instrument?, device, ip}` defined, with deterministic or RNG-backed provenance.

---

### 6.6 Step 4 — Sessionisation

With entity attachments fixed, S1 defines sessions.

1. **Define a session key template** from 6B’s session policy, e.g.:

   ```text
   session_key_base = {
     party_id,
     device_id,
     merchant_id,
     channel_group,
     scenario_id
   }
   ```

   (Exact composition is dictated by `sessionisation_policy_6B`.)

2. **Group arrivals by session_key_base**:

   * For each group, sort arrivals by `ts_utc` (ascending).

3. **Apply session boundary rules:**

   For each sorted group:

   * Walk the ordered list and decide, between `arrival[i]` and `arrival[i+1]`, whether to **continue the session** or **start a new one**, based on:

     * time gaps vs inactivity thresholds,
     * changes in key attributes (if policy considers them),
     * optional stochastic “break” behaviour (e.g. randomised threshold within a range).

   * Decisions MUST follow `sessionisation_policy_6B`. Typical pattern:

     * If `gap_seconds ≤ hard_timeout` → continue session.
     * If `gap_seconds ≥ hard_break` → start new session.
     * If `hard_timeout < gap_seconds < hard_break` and policy allows randomness, use `rng_event_session_boundary` to sample a decision.

4. **Assign `session_id`s:**

   * For each session fragment, assign a unique `session_id` within `(seed, manifest_fingerprint, scenario_id)`, using a deterministic scheme, e.g.:

     ```text
     session_id = hash64(manifest_fingerprint, seed, scenario_id, session_key_base, session_index) 
     ```

     or a monotone counter stored per `(seed, fingerprint, scenario_id)` with a deterministic initialisation. The exact form is defined in `schemas.6B.yaml` and 6B identity law.

   * Ensure that:

     * every arrival in `s1_arrival_entities_6B` gets exactly one `session_id`,
     * there are no duplicate `session_id` rows in `s1_session_index_6B`.

5. **Session aggregates:**

   For each session:

   * Compute:

     * `session_start_utc` = min arrival `ts_utc`,
     * `session_end_utc` = max arrival `ts_utc`,
     * `arrival_count`,
     * derived metrics (duration, average gap, etc.) as defined in the session schema.

   * Derive **session-level entity context**, e.g.:

     * `primary_party_id` (dominant party in the session; likely a single id),
     * `primary_device_id` / `primary_ip_id`,
     * `channel_set`, `merchant_set`, etc.

6. **RNG usage in sessionisation (if any):**

   * If `sessionisation_policy_6B` is entirely deterministic (single inactivity threshold), S1 MUST NOT consume RNG for sessionisation.
   * If randomisation is used (e.g. random thresholds), S1 MUST:

     * use a dedicated RNG family (e.g. `rng_event_session_boundary`),
     * adhere to fixed draw budgets per boundary decision or per session as specified in Layer-3 RNG contracts.

---

### 6.7 Step 5 — Emit outputs & enforce invariants

For each `(seed, manifest_fingerprint, scenario_id)` partition:

1. **Construct `s1_arrival_entities_6B`:**

   * For every arrival row from `arrival_events_5B` in this partition:

     * copy all 5B identity + context fields unchanged,
     * add the entity attachments `{party_id, account_id, instrument_id?, device_id, ip_id}`,
     * add `session_id` and provenance fields.

   * Enforce:

     * **Coverage:** there MUST be exactly one row in `s1_arrival_entities_6B` for each arrival in `arrival_events_5B@{seed,fingerprint,scenario_id}`.
     * **No extras:** no rows may exist for arrivals not present in 5B.
     * **FKs:** all entity IDs must exist in 6A bases for `(seed, manifest_fingerprint)`.

2. **Construct `s1_session_index_6B`:**

   * For every distinct `session_id` in `s1_arrival_entities_6B` for this partition:

     * emit exactly one row in `s1_session_index_6B` with identity, time window, aggregates, and session-level entity context.

   * Enforce:

     * **Coverage:** every `session_id` referenced in `s1_arrival_entities_6B` must appear exactly once in `s1_session_index_6B`.
     * **No orphan sessions:** no `session_id` rows without corresponding arrivals.

3. **Write outputs:**

   * Write `s1_arrival_entities_6B` and `s1_session_index_6B` to their respective paths:

     ```text
     data/layer3/6B/s1_arrival_entities_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/...
     data/layer3/6B/s1_session_index_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/...
     ```

   * Use the ordering and partitioning specified in §4–§5.

   * Ensure both datasets pass schema validation (including PK uniqueness) before marking S1 as PASS for this partition.

If any of these invariants fail, S1 MUST fail for that partition and MUST NOT publish partial outputs.

---

### 6.8 RNG accounting & reproducibility obligations

S1 MUST cooperate with the Layer-3 RNG accounting:

* For each RNG family used (`rng_event_entity_attach`, `rng_event_session_boundary`, etc.):

  * The total number of events and draws MUST be:

    * deterministic given `(manifest_fingerprint, parameter_hash, seed, scenario_id)`, and
    * consistent with the domain size (e.g. bounded by number of arrivals × number of stochastic dimensions).

  * S1 MUST emit RNG events/logs as per the Layer-3 RNG schema so that the 6B validation state can cross-check:

    * S1’s declared domain (number of stochastic decisions),
    * the actual number of RNG draws,
    * and the monotonicity of RNG counters.

* S1 MUST NOT:

  * consume RNG from families reserved for other states,
  * re-use RNG families for different logical decisions than those specified for S1,
  * use data-dependent branching that changes the **number** of RNG events in a way that cannot be inferred from inputs (e.g. early returns that skip events without a corresponding domain shrink).

Together with previous sections, this algorithm defines S1 as:

> a deterministic, RNG-accounted enrichment & grouping layer, which takes sealed arrivals + sealed entities and produces a reproducible mapping from arrivals to entities and sessions, ready for downstream behaviour (S2–S4) and validation (S5).

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S1’s outputs are identified and stored**, and what rules implementations MUST follow for **partitioning, ordering, re-runs and merges**.

It applies to both S1 datasets:

* `s1_arrival_entities_6B`
* `s1_session_index_6B`

and is binding for any conforming implementation.

---

### 7.1 Identity axes for S1

S1 is evaluated over the same axes as 5B’s arrivals:

* `manifest_fingerprint` — world snapshot.
* `seed` — stochastic run axis shared with 5B and 6A.
* `scenario_id` — arrival scenario from 5A/5B.

Binding rules:

1. For each `(manifest_fingerprint, seed, scenario_id)` where `arrival_events_5B` has a partition, S1 has the **option** to produce corresponding partitions in its outputs (see §7.4 for “empty” partitions).
2. All S1 data-plane outputs **MUST** carry these three axes as explicit columns: `manifest_fingerprint`, `seed`, `scenario_id`.
3. S1 MUST NOT introduce `run_id` or any other execution identifier as a partition key for its data-plane outputs. `run_id` remains an RNG/logging concern only.

Identity is thus:

```text
world axis:     manifest_fingerprint
run axis:       seed
scenario axis:  scenario_id
```

Everything else (arrival keys, session_ids) is subordinate to these axes.

---

### 7.2 Partitioning and paths

Both S1 datasets are **partitioned identically**:

* `partitioning: [seed, fingerprint, scenario_id]`

and use the following path templates:

* `s1_arrival_entities_6B`:

  ```text
  data/layer3/6B/s1_arrival_entities_6B/
      seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `s1_session_index_6B`:

  ```text
  data/layer3/6B/s1_session_index_6B/
      seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

Binding path↔embed rules:

* For every row:

  * `seed` column MUST equal the `seed={seed}` path token.
  * `manifest_fingerprint` column MUST equal the `fingerprint={manifest_fingerprint}` path token.
  * `scenario_id` column MUST equal the `scenario_id={scenario_id}` path token.

* No S1 dataset MAY be written outside this directory layout or without all three partition components.

---

### 7.3 Primary keys & writer ordering

#### 7.3.1 `s1_arrival_entities_6B`

**Primary key** (binding):

```text
[seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
```

where `(merchant_id, arrival_seq)` is exactly the arrival key from `arrival_events_5B`.

**Writer ordering** (binding):

```text
[seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
```

Within each `(seed, fingerprint, scenario_id)` partition:

* Rows MUST be sorted by `merchant_id` then `arrival_seq` in ascending order.
* There MUST be **exactly one** row for each arrival present in `arrival_events_5B` for that partition, and NO rows for arrivals that do not exist upstream.

#### 7.3.2 `s1_session_index_6B`

**Primary key** (binding):

```text
[seed, manifest_fingerprint, scenario_id, session_id]
```

**Writer ordering** (binding):

```text
[seed, manifest_fingerprint, scenario_id, session_id]
```

Within each `(seed, fingerprint, scenario_id)` partition:

* Each `session_id` MUST appear exactly once.
* All `session_id` values referenced in `s1_arrival_entities_6B` for that partition MUST appear in the session index.

Downstream states MUST use these primary keys for joins; ordering is for determinism and storage discipline, not as a substitute for proper keys.

---

### 7.4 Coverage discipline vs `arrival_events_5B`

For each `(manifest_fingerprint, seed, scenario_id)` where S1 runs:

* **Coverage (arrivals → S1 arrivals):**

  * Let `A_5B(seed,fingerprint,scenario)` be the set of arrival keys in `arrival_events_5B`.
  * Let `A_6B(seed,fingerprint,scenario)` be the set of arrival keys in `s1_arrival_entities_6B`.

  S1 MUST ensure:

  ```text
  A_6B(seed,fingerprint,scenario) == A_5B(seed,fingerprint,scenario)
  ```

  i.e. one and only one enrichment row per upstream arrival.

* **Coverage (sessions ↔ S1 arrivals):**

  * Every `session_id` in `s1_arrival_entities_6B` MUST correspond to exactly one row in `s1_session_index_6B`.
  * Every `session_id` row in `s1_session_index_6B` MUST have `arrival_count ≥ 1` and at least one associated arrival in the arrival-side dataset for that partition.

**Empty-partition semantics:**

* If `arrival_events_5B` has **zero rows** for a `(seed, fingerprint, scenario_id)` partition and S1 is invoked for that partition, then:

  * It is acceptable for S1 to write **empty** partitions for both outputs (zero rows, valid schema), or
  * To write no files at all for that partition, provided this choice is documented and consistent.

This spec recommends the **empty partitions** approach for simplicity and uniformity, but whichever choice is adopted MUST be applied consistently in implementation and reflected in 6B validation.

---

### 7.5 Re-run & idempotence discipline

S1 MUST be **idempotent** for a given `(manifest_fingerprint, parameter_hash, seed, scenario_id)` under fixed inputs.

Binding rules:

1. **Per-partition atomicity**

   For a given `(seed, fingerprint, scenario_id)`:

   * S1 MUST treat both `s1_arrival_entities_6B` and `s1_session_index_6B` as a **unit** for that partition.
   * It MUST NOT leave a state where one dataset is written and the other is missing or inconsistent for that partition.

   If a failure occurs after writing one dataset but before the other, the implementation MUST treat that partition as failed and orchestrators MUST clean up or overwrite partial outputs on the next attempt (per engine’s standard recovery model).

2. **Single-writer per partition**

   * For a given `(seed, fingerprint, scenario_id)`, at most one logical S1 writer may be active at a time.
   * Parallel writers for *different* `(seed, scenario_id)` pairs are allowed as long as they write to disjoint partitions.

3. **Idempotent re-runs**

   * If outputs for a partition **do not exist** yet, S1 writes them once.
   * If outputs **do exist**, a re-run for the same `(seed, fingerprint, scenario_id, parameter_hash)` MUST either:

     * reproduce byte-identical results (same rows, same ordering, same serialised parquet content modulo allowed physical encoding differences if the engine defines them as digest-equivalent), or
     * fail with an idempotence/merge error (e.g. `S1_IDEMPOTENCE_VIOLATION`) and MUST NOT overwrite the existing data.

   In particular, S1 MUST NOT append to existing files to “add” arrivals or sessions; recomputation must always be a full replacement per partition.

4. **No incremental merges**

   * S1 MUST NOT support “incremental” updates for a partition where only a subset of arrivals is recomputed and merged.
   * The unit of recomputation is the full `(seed, fingerprint, scenario_id)` domain.

Any “refresh” of S1 outputs due to contract changes (e.g. different attachment priors) MUST be treated as a new **spec/config version**, and should be accompanied by a new run of 5B or an explicit migration procedure; S1 MUST NOT silently change semantics for existing outputs.

---

### 7.6 Join discipline for downstream states

Downstream 6B states (S2–S4) and S5 MUST follow these identity rules:

* **World/run/scenario axes:**

  * Always join S1 outputs using the triple `(seed, manifest_fingerprint, scenario_id)` as the outer join key.
  * Never attempt to join across different `manifest_fingerprint` or `seed` values.

* **Arrival identity:**

  * To move from S1 to 5B or vice versa, use the full arrival PK:
    `[seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]`.

* **Session identity:**

  * To move between S1 arrivals and S1 sessions:
    `[seed, manifest_fingerprint, scenario_id, session_id]`.

Downstream states MUST NOT rely on file names or ordering alone; identity is always expressed via columns + partition axes.

---

### 7.7 Interaction with RNG logs (non-partition identity)

Although S1 consumes RNG, RNG logs (if materialised as separate datasets) follow the **Layer-3 RNG partition law**, typically:

* `partitioning: [seed, parameter_hash, run_id]`

S1’s data-plane outputs:

* MUST NOT introduce `run_id` into their partitioning,
* MUST NOT rely on RNG log partitioning for their own identity,
* MUST be fully determined by `(manifest_fingerprint, parameter_hash, seed, scenario_id)` and upstream inputs.

The 6B validation state will reconcile RNG logs against S1’s declared domain; that reconciliation is not part of S1’s identity discipline, but S1 MUST respect the separation of concerns.

---

By adhering to these identity, partitioning, ordering, and merge rules, S1 remains:

* a deterministic, reproducible enrichment layer over 5B arrivals and 6A entities, and
* a stable foundation for flow construction (S2), campaign overlay (S3), and labelling (S4), without introducing hidden identity axes or ambiguous re-runs.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines:

* When 6B.S1 is considered **PASS** vs **FAIL**, for a given
  `(manifest_fingerprint, seed, scenario_id)`, and
* What obligations this places on **downstream 6B states** (S2–S4, S5) and orchestrators.

All conditions here are **binding**. If they are not met, S1 MUST be treated as FAIL for that domain and downstream states MUST NOT proceed.

---

### 8.1 Domain of evaluation

S1 is evaluated per triple:

```text
(manifest_fingerprint, seed, scenario_id)
```

For a given `manifest_fingerprint`, there may be many `(seed, scenario_id)` pairs.
Acceptance criteria apply **per pair**. S0’s gate covers the fingerprint; S1’s acceptance covers individual arrival partitions.

---

### 8.2 Acceptance criteria for S1 (per `(seed, scenario_id)`)

For a fixed `(manifest_fingerprint, seed, scenario_id)`, S1 is considered **PASS** if and only if **all** the following hold:

#### 8.2.1 Preconditions satisfied

* 6B.S0 is PASS for `manifest_fingerprint`, and `s0_gate_receipt_6B` + `sealed_inputs_6B` are present and schema-valid.
* `s0_gate_receipt_6B.upstream_segments[SEG].status == "PASS"` for all required segments `{1A,1B,2A,2B,3A,3B,5A,5B,6A}`.
* `sealed_inputs_6B` contains `REQUIRED`, `ROW_LEVEL` entries for:

  * `arrival_events_5B`, and
  * the required 6A entity + posture datasets (as listed in §2.3).

If any of these are not satisfied, S1 MUST not attempt data-plane work and MUST be recorded as FAIL for this `(seed, scenario_id)`.

#### 8.2.2 Arrival coverage and identity consistency

Let:

* `AE5B` = `arrival_events_5B` at
  `(seed, fingerprint=manifest_fingerprint, scenario_id)`.
* `AE6B` = `s1_arrival_entities_6B` at the same axes.

Then:

1. **Row-count equality**

   * `|AE6B| == |AE5B|` (same number of rows).

2. **Key equality (coverage):**

   * If `K = [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]` is the PK in both tables, then:

     ```text
     { K(AE6B) } == { K(AE5B) }
     ```

   * Every arrival key in 5B appears exactly once in S1; no extra keys.

3. **Upstream fields preserved:**

   * For each arrival key, S1 MUST preserve all upstream identity and routing fields as defined by `arrival_events_5B` (including `ts_utc`, `scenario_id`, `merchant_id`, routing fields, etc.):

     ```text
     AE6B.K == AE5B.K
     and
     AE6B.upstream_field == AE5B.upstream_field
     ```

   * S1 MUST NOT change arrival timestamps, routing, or counts.

4. **Schema validity:**

   * `s1_arrival_entities_6B` passes schema validation against `schemas.6B.yaml#/s1/arrival_entities_6B`.

#### 8.2.3 Entity attachment integrity

For every row in `s1_arrival_entities_6B`:

1. **Existence in 6A bases:**

   * Any non-null `party_id` MUST exist in `s1_party_base_6A` for `(seed, manifest_fingerprint)`.
   * Any non-null `account_id` MUST exist in `s2_account_base_6A`.
   * Any non-null `instrument_id` MUST exist in `s3_instrument_base_6A`.
   * Any non-null `device_id` MUST exist in `s4_device_base_6A`.
   * Any non-null `ip_id` MUST exist in `s4_ip_base_6A`.

2. **Link consistency:**

   * Where policy requires specific relationships (e.g. `account_id` belongs to `party_id`, `instrument_id` linked to `account_id`, `device_id` linked to `party_id` or `merchant_id`), the corresponding rows MUST be present in the relevant 6A link tables (`s3_account_instrument_links_6A`, `s4_device_links_6A`, `s4_ip_links_6A`) and MUST be consistent.

   * S1 MUST NOT emit attachments that violate 6A’s link structure.

3. **Static posture consistency:**

   * If S1 copies static fraud roles into its outputs (e.g. `party_risk_flag`), those values MUST match the values in 6A posture tables for the referenced IDs.

4. **Nullability rules:**

   * Any null entity fields MUST be allowed by S1’s schema and policy (e.g. `instrument_id` may be null on non-monetary events).
   * Required entity dimensions (as defined in S1’s schema) MUST be non-null.

#### 8.2.4 Session integrity

Let:

* `SESS` = `s1_session_index_6B` at `(seed, fingerprint, scenario_id)`.

Then:

1. **Schema validity:**

   * `s1_session_index_6B` MUST validate against `schemas.6B.yaml#/s1/session_index_6B`.

2. **Session coverage:**

   * Every `session_id` referenced in `s1_arrival_entities_6B` MUST appear exactly once as a row in `s1_session_index_6B`.

3. **No orphan sessions:**

   * For each row in `SESS`, `arrival_count ≥ 1`, and there is at least one arrival row in `s1_arrival_entities_6B` with that `session_id`.

4. **Session aggregates consistent with arrivals:**

   For each `session_id`:

   * `arrival_count` MUST equal the number of arrivals in `s1_arrival_entities_6B` with that `session_id`.
   * `session_start_utc` MUST equal the minimum `ts_utc` over those arrivals.
   * `session_end_utc` MUST equal the maximum `ts_utc` over those arrivals.
   * `session_duration_seconds` MUST be consistent with `session_end_utc - session_start_utc` per policy.

5. **Axes consistency:**

   * All rows in both S1 outputs for a given partition MUST have `seed`, `manifest_fingerprint`, and `scenario_id` equal to the partition axes.

#### 8.2.5 RNG envelope sanity (local to S1)

While full RNG accounting is the responsibility of the 6B validation state, S1 MUST perform basic local checks:

* For each RNG-consuming decision family (e.g. `entity_attach`, `session_boundary`), the number of RNG events emitted MUST be within a predictable bound, such as:

  * `#entity_attach_events ≤ #arrivals × (#stochastic_dimensions_per_arrival)`,
  * `#session_boundary_events ≤ #arrivals` (if used).

* S1 MUST consider it a failure if observed RNG usage for a partition violates its declared budgets (e.g. zero events where stochastic behaviour is mandated, or more events than expected by policy).

These checks may be implemented via local counters and do not require reading the full global RNG logs; the full reconciliation is done by S5.

---

### 8.3 Conditions that MUST cause S1 to FAIL

For a given `(manifest_fingerprint, seed, scenario_id)`, S1 MUST be treated as **FAIL** (and MUST NOT publish or must roll back partial outputs) if any of the following occurs:

* Preconditions in §2 or §8.2.1 are not met.
* `s1_arrival_entities_6B` or `s1_session_index_6B` fail schema validation.
* Arrival coverage breaks: missing or extra arrivals relative to `arrival_events_5B`.
* Any entity attachment references non-existent 6A entities or violates 6A links.
* Session coverage breaks:

  * `session_id` in arrivals missing in the session index, or
  * sessions with zero arrivals or inconsistent `arrival_count` / time windows.
* Axes mismatch: any row has `seed`, `manifest_fingerprint`, or `scenario_id` differing from its partition tokens.
* Local RNG envelope checks reveal impossible usage (e.g. negative or clearly excessive counts relative to domain size).

On FAIL, S1 MUST ensure that:

* No partial outputs are left in a state that downstream states might misinterpret as PASS (see §7.5).
* The run-report marks S1 as FAIL for this `(manifest_fingerprint, seed, scenario_id)` with an appropriate error code (to be defined in §9).

---

### 8.4 Gating obligations for S2–S4 (downstream 6B states)

For any `(manifest_fingerprint, seed, scenario_id)`:

1. **S1 PASS is a hard precondition**

   * 6B.S2–S4 MUST NOT run for that partition unless:

     * S0 is PASS at the fingerprint level, and
     * S1 is recorded as `status="PASS"` in the run-report for that `(seed, scenario_id)`.

2. **S1 outputs are the only starting point**

   * S2–S4 MUST treat `s1_arrival_entities_6B` and `s1_session_index_6B` as the **sole starting surfaces** for behaviour:

     * They MUST NOT read `arrival_events_5B` directly to re-attach entities or re-form sessions.
     * They MUST NOT attempt to infer alternative entity/session mappings; if S1 is wrong, validation will fail, not S2–S4.

3. **No mutation of S1 outputs**

   * S2–S4 MUST treat S1 outputs as read-only. They may reference them, derive new surfaces, or project them into downstream tables, but MUST NOT rewrite, delete or append to S1 datasets.

If a downstream state detects that S1 outputs are missing or malformed for a partition, it MUST fail early with a precondition error, not attempt to repair S1.

---

### 8.5 Obligations for 6B segment validation (S5) and 4A/4B

The 6B validation / HashGate state (S5) and later layers MUST respect the following:

1. **S5 MUST validate S1 invariants**

   * S5 MUST treat the invariants from §8.2 as binding checks:

     * arrival coverage,
     * entity FK consistency,
     * session coverage and aggregate consistency.

   * Any violation MUST cause S5 to mark the segment as FAIL for that `manifest_fingerprint`, even if S2–S4 appear to be well-formed.

2. **S5 depends on S1 PASS**

   * S5 MUST NOT treat 6B as valid for a partition if S1 has not PASSed for all `(seed, scenario_id)` covered by the world.

3. **4A/4B MUST gate on the 6B HashGate, not directly on S1**

   * 4A/4B and external consumers MUST NOT consume any 6B business outputs (flows, campaigns, labels) unless:

     * S0 is PASS at the fingerprint level, and
     * the 6B segment HashGate (S5) is PASS, which in turn implies S1 has passed all its acceptance checks.

S1, by itself, does not authorise consumption; it **enables** downstream behaviour generation. The ultimate gate for external consumption remains the 6B segment HashGate.

---

In summary, these acceptance criteria ensure that:

* every arrival is cleanly and correctly attached to entities and sessions,
* S1 obeys upstream authorities and RNG contracts, and
* S2–S4 build on a solid, well-gated foundation.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical failure modes** for 6B.S1 and the **error codes** that MUST be used when they occur.

For any `(manifest_fingerprint, seed, scenario_id)` domain that S1 attempts, the state MUST:

* End in exactly one of: `status="PASS"` or `status="FAIL"` for that domain.
* If `status="FAIL"`, attach a **single primary error code** from the list below, and MAY attach secondary codes and diagnostics.

All codes here are **binding**. Downstream states and orchestrators MUST treat any non-PASS S1 status as a hard gate for that `(seed, scenario_id)`.

---

### 9.1 Error model & context

For each failed `(manifest_fingerprint, seed, scenario_id)`:

* **Primary error code**

  * One of the codes defined below (e.g. `S1_PRECONDITION_S0_FAILED`).
  * Captures the main reason S1 did not complete.

* **Secondary error codes** (optional)

  * A list of additional codes for fine-grained diagnostics (e.g. both `S1_ENTITY_REFERENCE_INVALID` and `S1_SESSION_AGGREGATE_MISMATCH`).
  * MUST NOT be used without a primary code.

* **Context fields** (run-report / logs SHOULD provide):

  * `manifest_fingerprint`
  * `seed`
  * `scenario_id`
  * Optionally `owner_segment`, `manifest_key`, `arrival_key`, `session_id` depending on failure type.

The exact run-report shape is defined in §10, but these codes and their semantics are binding.

---

### 9.2 Preconditions & upstream/metadata failures

These indicate S1 never legitimately entered its attachment/sessionisation workflow for the given `(seed, scenario_id)`.

#### 9.2.1 `S1_PRECONDITION_S0_FAILED`

**Definition**
Emitted when S0 has not PASSed or is not present for the `manifest_fingerprint`.

**Examples**

* `s0_gate_receipt_6B` missing or schema-invalid.
* Run-report does not show 6B.S0 `status="PASS"`.

**Obligations**

* S1 MUST NOT read any upstream datasets.
* S1 MUST NOT produce any outputs for this `(seed, scenario_id)`.

---

#### 9.2.2 `S1_PRECONDITION_UPSTREAM_GATE_NOT_PASS`

**Definition**
Emitted when `s0_gate_receipt_6B.upstream_segments[SEG].status != "PASS"` for any required segment in `{1A,1B,2A,2B,3A,3B,5A,5B,6A}`.

**Examples**

* S0 recorded `status="FAIL"` for 5B’s HashGate, but S1 was invoked anyway.

**Obligations**

* S1 MUST NOT proceed with arrivals/entities; treat as a hard precondition failure.

---

#### 9.2.3 `S1_PRECONDITION_SEALED_INPUTS_INCOMPLETE`

**Definition**
Emitted when `sealed_inputs_6B` is present but lacks the required entries for S1.

**Examples**

* No `arrival_events_5B` row in `sealed_inputs_6B` with `status="REQUIRED", read_scope="ROW_LEVEL"`.
* Missing required 6A entity or posture artefact (e.g. `s2_account_base_6A` not in `sealed_inputs_6B`).

**Obligations**

* S1 MUST NOT guess dataset locations or read unlisted artefacts.
* S1 MUST fail before reading data-plane rows.

---

### 9.3 Arrival coverage & schema failures

These indicate that S1 attempted to run but broke basic identity/schema guarantees.

#### 9.3.1 `S1_ARRIVAL_COVERAGE_MISMATCH`

**Definition**
Emitted when the set of arrival keys in `s1_arrival_entities_6B` does not exactly match `arrival_events_5B` for the `(seed, fingerprint, scenario_id)` domain.

**Examples**

* Some arrivals in 5B not present in S1.
* Extra rows in S1 for non-existent `arrival_seq` or merchants.

**Obligations**

* S1 MUST roll back or treat this as a failure; partial outputs MUST NOT be considered valid.

---

#### 9.3.2 `S1_OUTPUT_SCHEMA_VIOLATION`

**Definition**
Emitted when `s1_arrival_entities_6B` or `s1_session_index_6B` fails validation against its schema anchor.

**Examples**

* Missing required field (e.g. `session_id`), wrong type, out-of-range values.
* Violated PK/UK constraints (duplicate primary keys).

**Obligations**

* No output for this partition may be considered usable; downstream states MUST NOT run.

---

### 9.4 Entity attachment failures

These indicate S1 produced invalid or incomplete entity attachments.

#### 9.4.1 `S1_ENTITY_NO_CANDIDATES`

**Definition**
Emitted when S1 cannot find **any valid candidate** entity for a required dimension of an arrival, given 6A bases/links and policy.

**Examples**

* No accounts/instruments for a party that policy demands for a monetary arrival.
* No devices/IPs available for an arrival where policy forbids “fresh” devices and none are linked in 6A.

**Obligations**

* S1 MUST either:

  * (preferred) treat this as a hard failure for the partition, or
  * if policy explicitly allows dropping such arrivals (which this spec does **not**), that behaviour must be documented and validated; under this spec, dropping is disallowed, so this code is fatal.

---

#### 9.4.2 `S1_ENTITY_REFERENCE_INVALID`

**Definition**
Emitted when S1 writes entity IDs in its outputs that do not exist in 6A bases or that violate link semantics.

**Examples**

* `party_id` in S1 not found in `s1_party_base_6A`.
* `account_id` in S1 not linked to `party_id` per `s2_account_base_6A`.
* `device_id` not found in `s4_device_base_6A`, or `device_id`–`party_id` combination not supported by `s4_device_links_6A`.

**Obligations**

* S1 MUST treat this as a hard FAIL. 6B validation will also flag this.

---

#### 9.4.3 `S1_ENTITY_ATTACHMENT_INCONSISTENT`

**Definition**
Emitted when entity combinations chosen by S1 are internally inconsistent with 6A graphs or 6B policy, even though all individual IDs exist.

**Examples**

* `instrument_id` belongs to a different account than the `account_id` used in S1.
* `device_id` used in a session not linked to the `party_id` per 6A when policy requires consistency.

**Obligations**

* S1 MUST fail the partition; downstream states MUST NOT build flows on top of inconsistent attachments.

---

### 9.5 Sessionisation failures

These indicate that S1 constructed an invalid or inconsistent session index.

#### 9.5.1 `S1_SESSION_ID_MISMATCH`

**Definition**
Emitted when session IDs in arrivals and in the session index do not align.

**Examples**

* A `session_id` in `s1_arrival_entities_6B` has no corresponding row in `s1_session_index_6B`.
* A row in `s1_session_index_6B` has `arrival_count ≥ 1`, but no arrivals refer to that `session_id`.

**Obligations**

* S1 MUST fail; downstream states MUST NOT proceed.

---

#### 9.5.2 `S1_SESSION_AGGREGATE_MISMATCH`

**Definition**
Emitted when aggregate fields in `s1_session_index_6B` do not match the arrivals in `s1_arrival_entities_6B`.

**Examples**

* `arrival_count` ≠ number of arrivals for the session.
* `session_start_utc` or `session_end_utc` does not equal the min/max `ts_utc` across arrivals in the session.
* `session_duration_seconds` inconsistent with `session_start_utc` / `session_end_utc`.

**Obligations**

* S1 MUST fail; indexes and arrivals must be recomputed.

---

#### 9.5.3 `S1_SESSION_AXIS_MISMATCH`

**Definition**
Emitted when any row in the session index has `seed`, `manifest_fingerprint`, or `scenario_id` that does not match the partition tokens or the corresponding arrivals.

**Examples**

* Sessions recorded under the wrong scenario_id.
* Session row with a different `manifest_fingerprint` than its partition path.

**Obligations**

* Hard FAIL; identity axes must be consistent.

---

### 9.6 RNG envelope & determinism failures

These indicate inconsistent or impossible RNG usage for S1.

#### 9.6.1 `S1_RNG_EVENT_COUNT_MISMATCH`

**Definition**
Emitted when S1’s measured RNG usage for a partition violates its own declared budgets.

**Examples**

* Expected one `entity_attach` RNG event per stochastic dimension per arrival, but actual count is lower or higher beyond tolerances.
* Zero RNG events emitted when policy requires stochastic attachment behaviour.

**Obligations**

* S1 MUST fail; RNG misuse undermines reproducibility and auditability.

---

#### 9.6.2 `S1_RNG_STREAM_MISCONFIGURED`

**Definition**
Emitted when S1 cannot correctly attach to the Layer-3 RNG environment – e.g. missing or invalid RNG policy for S1’s family names, or conflicting counters.

**Examples**

* The configured RNG family name for S1 does not exist in the Layer-3 RNG spec.
* Attempts to create or consume from a RNG family reserved for another state.

**Obligations**

* S1 MUST not continue; configuration must be corrected.

---

### 9.7 Output write & idempotence failures

#### 9.7.1 `S1_OUTPUT_WRITE_FAILED`

**Definition**
Emitted when S1 fails to write one or both of its output datasets for a partition due to I/O or infrastructure errors.

**Examples**

* Filesystem/network error when writing parquet.
* Partial write that cannot be completed.

**Obligations**

* S1 MUST treat the partition as FAIL. Orchestrators MUST ensure partial outputs are either cleaned up or recognised as invalid on re-run.

---

#### 9.7.2 `S1_IDEMPOTENCE_VIOLATION`

**Definition**
Emitted when outputs already exist for a partition, and a re-run of S1 for the same `(manifest_fingerprint, seed, scenario_id, parameter_hash)` would produce different content.

**Examples**

* Existing `s1_arrival_entities_6B` differs in entity/session assignments from what S1 now computes, absent any declared spec/config change.

**Obligations**

* S1 MUST NOT overwrite existing outputs.
* The discrepancy must be investigated as contract drift or upstream/environment change.

---

### 9.8 Internal / unexpected failures

#### 9.8.1 `S1_INTERNAL_ERROR`

**Definition**
Catch-all for failures not attributable to user/contract misconfiguration, upstream gate issues, or the explicit categories above.

**Examples**

* Uncaught exceptions, segmentation faults, or other runtime panics in S1 logic.
* Unexpected type mismatches in in-memory indices not tied to schema violations.

**Obligations**

* S1 MUST fail the partition.
* Implementations SHOULD log sufficient context to allow reclassification of recurring internal errors into more specific codes over time.

---

### 9.9 Surfaces & propagation

For any partition where S1 fails:

* The **Layer-3 run-report** MUST record:

  * `status="FAIL"` for `segment=6B`, `state=S1`, plus
  * `primary_error_code` from the enumeration above,
  * optional `secondary_error_codes` and context.

* S2–S4 MUST NOT run for that `(manifest_fingerprint, seed, scenario_id)` and SHOULD surface S1’s primary error code in their own precondition failures.

* The 6B validation/HashGate state (S5) MUST treat any S1 failure for a partition as a **segment-level FAIL** for the affected world and MUST reflect S1’s error codes in its own diagnostics.

These error codes collectively define the failure semantics of S1 and are part of its external contract.

---

## 10. Observability & run-report integration *(Binding)*

This section defines what 6B.S1 **must expose** for observability, and **how it must appear in the engine run-report**, so that:

* Operators can see whether S1 is assigning entities/sessions correctly.
* Downstream states (S2–S4, S5) and orchestrators can **gate** on S1 status in a machine-readable way.

Everything here is **binding** for 6B.S1.

---

### 10.1 Run-report scope and keying

S1 is evaluated per:

```text
(manifest_fingerprint, seed, scenario_id)
```

The Layer-3 run-report **MUST** include an entry for each attempted `(seed, scenario_id)` under a given `manifest_fingerprint`, with at least:

* `segment` = `"6B"`
* `state` = `"S1"`
* `manifest_fingerprint`
* `seed`
* `scenario_id`
* `status` — `"PASS"` or `"FAIL"`
* `primary_error_code` — from §9 (or `null` if `status="PASS"`)
* `secondary_error_codes` — list (possibly empty)

Additionally, the run-report **MUST** expose summary metrics for the partition (see §10.2).

There MUST NOT be multiple S1 entries for the same `(manifest_fingerprint, seed, scenario_id)` in a single run-report.

---

### 10.2 Required summary metrics (per `(seed, scenario_id)`)

For each S1 partition (whether PASS or FAIL), the run-report MUST include a **summary block** with at least:

* **Arrival & session counts**

  * `arrival_count_5B`

    * Number of rows in `arrival_events_5B` for this `(seed, fingerprint, scenario_id)`.
  * `arrival_count_S1`

    * Number of rows in `s1_arrival_entities_6B`.
  * `session_count_S1`

    * Number of rows in `s1_session_index_6B`.

* **Coverage diagnostics**

  * `arrival_coverage_ok: boolean`

    * True iff arrival keys match exactly (as per §8.2.2).
  * `session_coverage_ok: boolean`

    * True iff every `session_id` has ≥1 arrival and every `session_id` in arrivals appears in the session index.

* **Entity attachment diagnostics**

  * `attachment_missing_entities_count`

    * Count of arrivals where a required entity dimension (e.g. `party_id`, `account_id`, `device_id`) is null or invalid under S1’s schema.
  * `attachment_invalid_fk_count`

    * Count of arrivals where entity IDs fail FK checks against 6A bases/links.

* **Session distribution hints** (for monitoring, not gating):

  * `avg_arrivals_per_session`
  * `p95_arrivals_per_session`
  * `max_arrivals_per_session`
  * `avg_session_duration_seconds` (computed over sessions with `arrival_count ≥ 2`).

Binding rules:

* If `status="PASS"` for S1, then:

  * `arrival_count_5B == arrival_count_S1`,
  * `arrival_coverage_ok == true`,
  * `session_coverage_ok == true`,
  * `attachment_missing_entities_count == 0`,
  * `attachment_invalid_fk_count == 0`.

If these conditions fail, S1 MUST be `status="FAIL"` with an appropriate primary error code (see §9).

---

### 10.3 Logging requirements

S1 MUST emit structured logs at key stages for each `(manifest_fingerprint, seed, scenario_id)`.

At minimum:

1. **Partition start**

   * `event_type: "6B.S1.START"`
   * `manifest_fingerprint`
   * `seed`
   * `scenario_id`
   * Reference to S0 gate (e.g. `sealed_inputs_digest_6B`).

2. **Precondition checks**

   * `event_type: "6B.S1.PRECONDITION_CHECK"`
   * `manifest_fingerprint`, `seed`, `scenario_id`
   * `s0_status` — `"PASS"` / `"FAIL"`
   * `upstream_gates_ok` — boolean
   * if `false`, `error_code` (e.g. `S1_PRECONDITION_UPSTREAM_GATE_NOT_PASS`).

3. **Entity load & index build**

   * `event_type: "6B.S1.ENTITIES_LOADED"`
   * counts per 6A dataset for this `(seed, fingerprint)`:

     * `party_count`, `account_count`, `instrument_count`, `device_count`, `ip_count`.

4. **Attachment summary**

   * `event_type: "6B.S1.ATTACHMENT_SUMMARY"`
   * `arrival_count_5B`, `arrival_count_S1` (if already known)
   * `attachment_missing_entities_count`
   * `attachment_invalid_fk_count`
   * optional histograms/buckets (e.g. distribution of candidate set sizes).

5. **Sessionisation summary**

   * `event_type: "6B.S1.SESSION_SUMMARY"`
   * `session_count_S1`
   * `avg_arrivals_per_session`, `max_arrivals_per_session`
   * `avg_session_duration_seconds`, etc.

6. **Partition end**

   * `event_type: "6B.S1.END"`
   * `manifest_fingerprint`, `seed`, `scenario_id`
   * `status` — `"PASS"` / `"FAIL"`
   * `primary_error_code`
   * `secondary_error_codes` (list).

All logs MUST be sufficient to reconstruct:

* whether S1 ran for a given partition,
* where it failed (precondition, attachment, sessionisation, I/O), and
* high-level statistics about the work performed.

---

### 10.4 Metrics & SLI/monitoring considerations

S1 SHOULD expose metrics for operational monitoring. The shape is binding; the thresholds and dashboards are operational.

At minimum, the following logical metrics MUST be available (names indicative):

* `6B_S1_runs_total`

  * Counter, labels:

    * `status ∈ {"PASS","FAIL"}`

* `6B_S1_arrivals_total`

  * Counter, labels:

    * `status ∈ {"PASS","FAIL"}`
    * `scenario_id` (or scenario group)

* `6B_S1_sessions_total`

  * Counter, labels:

    * `status`
    * `scenario_id`

* `6B_S1_failure_primary_code_total`

  * Counter, label: `primary_error_code` (from §9).

* `6B_S1_attachment_invalid_fk_total`

  * Counter of invalid entity references encountered before failure.

* `6B_S1_runtimes_seconds`

  * Histogram or summary, label: `status`.

Implementations are free to use any backend (Prometheus, etc.), but the **semantics** of these metrics MUST match the descriptions above.

---

### 10.5 Downstream consumption of S1 observability

Downstream states and layers MUST use S1’s run-report and logs as follows:

* **S2–S4 (downstream 6B states)**

  * Before running for `(manifest_fingerprint, seed, scenario_id)`, a downstream state MUST:

    * check the run-report entry for S1 at those axes,
    * verify `status="PASS"`.

  * If S1 is `FAIL` (or absent), S2–S4 MUST:

    * NOT attempt to read `s1_arrival_entities_6B` or `s1_session_index_6B` for that partition,
    * fail early with a precondition error referencing S1’s `primary_error_code`.

* **S5 (6B validation / HashGate)**

  * S5 MUST interpret S1’s run-report metrics as **evidence**:

    * If any `(seed, scenario_id)` has S1 `status="FAIL"`, S5 MUST treat the world as FAIL for 6B.
    * If any S1 invariant in §8 is violated (as checked by S5’s own validation), S5 MUST mark 6B FAIL even if S1 mistakenly reported `status="PASS"`.

* **4A/4B & external consumers**

  * MUST NOT attempt to drill into S1 outputs directly (they gate on the 6B HashGate as a whole), but MAY surface S1’s run-report stats in diagnostic tooling (e.g. “world X has Y arrivals and Z sessions per scenario”).

---

### 10.6 Traceability & audit trail

Together, S1’s outputs and observability signals MUST allow an auditor to answer, for any `(manifest_fingerprint, seed, scenario_id)`:

* Did S1 run successfully?
* If not, why not (via `primary_error_code` and logs)?
* How many arrivals and sessions were processed?
* What fraction of arrivals were attached to high-risk entities (if such diagnostics are recorded)?
* Were all S1 invariants (coverage, FK consistency, session coverage) satisfied?

As a result:

* Emitting run-report entries and logs as described above is **not optional**; they are part of the state’s contract.
* Any implementation of 6B.S1 that suppresses or weakens these signals is non-conforming, even if its data-plane outputs happen to be structurally correct.

---

## 11. Performance & scalability *(Informative)*

This section gives **non-binding** guidance on how to keep S1 practical at scale. It does **not** relax any binding constraints from §§1–10; it only suggests implementation strategies that fit inside them.

---

### 11.1 Cost model — where S1 spends time

For a given `(manifest_fingerprint, seed, scenario_id)`, S1 does three main things:

1. **Load & index 6A entities/posture**

   * One pass over:

     * `s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`,
     * `s4_device_base_6A`, `s4_ip_base_6A`,
     * `s3_account_instrument_links_6A`, `s4_device_links_6A`, `s4_ip_links_6A`,
     * and posture surfaces (`s5_*_fraud_roles_6A`).
   * Build in-memory indices keyed by IDs (party, account, instrument, device, IP, merchant).

2. **Walk arrivals & attach entities**

   * Scan `arrival_events_5B` once.
   * For each arrival:

     * build candidate sets (mostly lookups into 6A indices),
     * compute attachment priors (lightweight numeric ops),
     * consume a **small, fixed number of RNG draws** for stochastic attachments.

3. **Sessionisation & aggregation**

   * Group arrivals by session key base (e.g. party+device+merchant+channel),
   * sort per group by `ts_utc`,
   * walk once per group to decide boundaries and build aggregates.

Rough complexity per `(seed, scenario_id)` is:

```text
O(#entities_6A_for_seed + #arrivals_5B_for_seed,scenario × log M)

where M is typical group size for sessionisation (often small).
```

Domination is usually by `#arrivals_5B`: entity graphs are large but reused across all scenarios for a given seed.

---

### 11.2 Parallelism & decomposition

S1 is embarrassingly parallel along a couple of axes:

* **Across `(seed, scenario_id)`**

  * Each pair is independent: arrivals and sessions for `(seed A, scenario X)` do not interact with `(seed B, scenario Y)`.
  * Implementations SHOULD schedule S1 per `(seed, scenario_id)` partition, in parallel where resources allow.

* **Within `(seed, scenario_id)`**

  * After loading 6A entities once per `(seed, fingerprint)`, arrival processing can be:

    * parallelised by merchant,
    * or by chunks of arrival_id ranges,
    * or by hash buckets on e.g. `(party_id, device_id)` once attachment is decided.

Careful with sessionisation: if sessions are defined using a composite key `{party, device, merchant, channel}`, then:

* parallel units MUST align with this key,
* or you need a two-phase approach:

  1. assign session_key_base and sort/shard by it,
  2. run session boundary logic within each shard.

---

### 11.3 Entity graph indexing strategies

6A entity tables can be large; naïve N×M joins will not scale. S1 implementations SHOULD:

* **Index by ID**

  * Hash maps / key-value indices on:

    * `party_id`, `account_id`, `instrument_id`, `device_id`, `ip_id`.
  * Secondary indices as needed:

    * `party_id → [accounts]`,
    * `account_id → [instruments]`,
    * `party_id → [devices]`, `merchant_id → [devices]`, etc.

* **Pre-derive attachment views**

  * Instead of recomputing candidate sets per arrival from scratch, precompute:

    * per-party account & instrument lists,
    * per-party / per-merchant device & IP lists,
    * basic posture tags on each entity (risk flags) as simple booleans.

* **Avoid redundant joins**

  * Once an arrival has been attached to a party, lookups for account/instrument/device/IP **should not** re-join on large tables; they should hit compact attachment indices.

Memory-wise, these indices are O(#entities_6A_for_seed); if this becomes large, consider:

* sharding per merchant or region,
* pruning obviously unused entities for a given scenario (if priors/config allow).

---

### 11.4 Streaming over arrivals

`arrival_events_5B` can be large (millions of rows per `(seed, scenario_id)` in stress scenarios). S1 SHOULD treat arrivals as a stream:

* **Single pass**

  * Ideally, attachments and preliminary session key assignment happen in a single scan over arrivals, using the prebuilt 6A indices.

* **Chunked processing**

  * Read arrivals in bounded chunks (e.g. N rows per batch) to control memory usage.
  * For sessionisation, either:

    * buffer per `session_key_base` until a safe boundary (e.g. time window) is reached, or
    * perform a second pass grouped by `session_key_base` after writing an intermediate “arrival + session_key_base + entity attachments” surface.

Whether you choose a one-pass or two-pass design is an implementation choice; the spec only requires the final outputs to respect identity and session invariants.

---

### 11.5 RNG cost & accounting

S1 has **moderate RNG usage**:

* Attachments:

  * In worst case, each arrival may require a few draws (e.g. one for party, one for account/instrument, one for device/IP).
* Sessionisation:

  * Purely deterministic session rules (fixed inactivity threshold) cost zero draws.
  * If policy uses randomised thresholds or probabilities, expect at most one draw per potential boundary.

Practical guidance:

* **Keep RNG families simple**

  * Use 1–2 RNG families for S1 (`entity_attach`, `session_boundary`), with fixed budgets per decision.
  * Avoid multi-draw families with complicated variable budgets; this makes validation more complex.

* **Bound draws by arrival count**

  * Design policies so draws are O(#arrivals) or O(#arrivals × small constant).
  * This makes RNG logging/validation cheap relative to data-plane work.

---

### 11.6 Memory & footprint

Per `(seed, fingerprint)` S1 needs memory primarily for:

* 6A indices and posture (~O(#entities_6A_for_seed)),
* some working structures per `(seed, scenario_id)`:

  * arrival batch buffers,
  * candidate sets and attachment priors,
  * per-session accumulation.

Guidance:

* **Reuse 6A indices across scenarios**

  * Load 6A once per `(seed, fingerprint)`, then process all `scenario_id`s, then discard.
  * Don’t reload 6A per scenario if you can avoid it.

* **Keep per-arrival state minimal**

  * Do not store full candidate lists for all arrivals in memory at once if they’re large; generate candidates on the fly and discard after sampling.

* **Watch session state**

  * If sessions are long-lived and dense, in-memory per-session state can grow; consider:

    * writing intermediate partial aggregates, or
    * splitting processing in time windows if policy allows.

---

### 11.7 I/O and file layout considerations

To keep S1’s I/O cost manageable:

* **Read once, write once per partition**

  * One scan over `arrival_events_5B` per `(seed, scenario_id)`.
  * One write pass each for `s1_arrival_entities_6B` and `s1_session_index_6B`.

* **Locality**

  * Colocate:

    * 5B arrivals,
    * 6A entities,
    * and 6B S1 outputs

    on the same storage backend/zone when possible, to reduce cross-region latency.

* **Partition sizing**

  * Ensure `(seed, scenario_id)` partitions are neither:

    * too small (excess overhead), nor
    * so large they exceed memory/throughput targets.

  * Partitioning at 5B is the primary lever; S1 follows that partitioning.

---

### 11.8 Expected bottlenecks & monitoring

In most realistic deployments:

* **Dominant cost** is:

  * scanning `arrival_events_5B`,
  * plus lookups into 6A indices.

* **Secondary cost** is:

  * sessionisation grouping (sorting within session_key groups),
  * writing outputs.

RNG and schema validation costs are typically negligible in comparison.

You SHOULD monitor:

* per-partition wall-clock time for S1;
* `arrival_count_5B`, `session_count_S1`,
* average and p95 `arrivals_per_session`,
* memory utilisation when building 6A indices.

Large regressions in S1 runtime or memory footprint often indicate:

* inefficient join/index strategies,
* unbounded candidate sets (e.g. behaviour priors too permissive), or
* overly large partitions at 5B.

---

### 11.9 Parallelism vs determinism

Nothing in this spec forbids parallel implementations; but any parallelisation MUST respect:

* the deterministic attachment/session rules (given stable upstream inputs and RNG contracts), and
* the PK/ordering/coverage invariants in §§4, 7, 8.

Implementation patterns that are safe:

* Parallelising over `(seed, scenario_id)` partitions.
* Parallelising over disjoint `session_key_base` groups inside a partition.
* Using thread-local buffers and then merging in a deterministic ordering.

Unsafe patterns (to avoid):

* Data races updating shared state that influence RNG order or candidate enumeration order.
* Non-deterministic grouping/sorting that depends on thread scheduling rather than explicit sort keys.

The rule of thumb: if you can run S1 twice with the same inputs and get **bit-identical outputs**, your parallelisation respects this spec.

---

In summary:

* S1’s cost is linear-ish in the number of arrivals and entities per seed;
* it parallelises naturally along the existing partition axes;
* careful indexing and streaming avoid it becoming the bottleneck;
* and all performance choices must remain inside the hard correctness and determinism constraints defined earlier.

---

## 12. Change control & compatibility *(Binding)*

This section defines how the **6B.S1 contract may evolve over time**, and what is considered **backwards-compatible** vs **breaking**.

It is binding on:

* authors of future S1 specs,
* implementers of S1, and
* downstream consumers (6B.S2–S5, 4A/4B, orchestration).

The goal is:

* to keep existing worlds and runs **replayable**, and
* to ensure downstream components can **rely** on S1’s identity, shapes, and invariants.

---

### 12.1 Versioning surfaces relevant to S1

S1 participates in three version tracks:

1. **`spec_version_6B`**

   * Behavioural contract version for Segment 6B as a whole (S0–S5).
   * Stored in `s0_gate_receipt_6B` and used by orchestrators to select the correct implementation bundle.

2. **Schema packs**

   * `schemas.6B.yaml` (S1-specific anchors: `#/s1/arrival_entities_6B`, `#/s1/session_index_6B`).
   * `schemas.layer3.yaml` (layer-wide RNG, gate and validation schemas).

3. **Catalogue artefacts**

   * `dataset_dictionary.layer3.6B.yaml` entries for:

     * `s1_arrival_entities_6B`,
     * `s1_session_index_6B`.
   * `artefact_registry_6B.yaml` entries for the same.

Binding rules:

* For any run of S1, the tuple
  `(spec_version_6B, schemas.6B.yaml version, schemas.layer3.yaml version)`
  MUST be internally consistent and discoverable from catalogues.
* This document defines the S1 contract for a particular `spec_version_6B` (e.g. `"1.0.0"`). **Any incompatible change MUST bump `spec_version_6B`**.

---

### 12.2 Backwards-compatible changes

A change to S1 is **backwards-compatible** if:

* existing consumers (S2–S4, S5, 4A/4B, tooling) built against this spec can still:

  * parse `s1_arrival_entities_6B` and `s1_session_index_6B`, and
  * rely on the identity/partition rules and invariants in §§4–8 without change.

Examples of **allowed** backwards-compatible changes:

1. **Additive schema extensions**

   * Adding new **optional** fields to `s1_arrival_entities_6B` (e.g. extra diagnostics, attachment scores) with sensible defaults.
   * Adding new **optional** fields to `s1_session_index_6B` (e.g. more session metrics), without changing existing required fields.

2. **New roles / policies in config packs**

   * Extending behaviour priors or sessionisation policies with new knobs that:

     * keep the attachment/session invariants intact, and
     * do not change the meaning of existing config fields.
   * Existing S1 implementations may ignore the new config fields; new implementations may start using them.

3. **Additional optional context inputs**

   * Listing additional upstream artefacts in `sealed_inputs_6B` as `status="OPTIONAL"` and using them only for **enrichment** (e.g. extra context from 5A / 2B) while preserving all identity and coverage invariants.

4. **Internal algorithmic optimisations**

   * Changing S1’s implementation details (e.g. different index structure, more efficient grouping) while:

     * preserving RNG contracts and budgets,
     * preserving identity, partitioning, and output invariants.

   Note: such changes may alter *which* entity gets chosen in ambiguous cases; this is acceptable **only if** the change is accompanied by a new `parameter_hash` or a controlled rollout. For a fixed `(manifest_fingerprint, parameter_hash, seed, scenario_id)`, determinism is still required.

Backwards-compatible changes MAY be introduced under a **minor** `spec_version_6B` bump (e.g. `1.0.0 → 1.1.0`), provided all binding behaviour from §§1–11 remains valid.

---

### 12.3 Breaking changes

A change is **breaking for S1** if it risks:

* invalidating identity/coverage invariants for existing consumers,
* causing an implementation built to this spec to misinterpret S1 outputs,
* changing S1’s contract **without** a new version boundary.

Breaking changes **MUST** be accompanied by a **new major** `spec_version_6B` (e.g. `1.x → 2.0.0`) and updated schemas/catalogues.

Examples of **breaking** changes:

1. **Identity / partition law changes**

   * Changing S1 output partitioning from `[seed, fingerprint, scenario_id]` to anything else.
   * Introducing `run_id` (or any new axis) as a partition key for `s1_arrival_entities_6B` or `s1_session_index_6B`.
   * Changing primary keys (e.g. dropping `merchant_id, arrival_seq` from the arrival PK).

2. **Schema contract changes**

   * Removing or renaming any **required** field in `s1_arrival_entities_6B` or `s1_session_index_6B` (e.g. `session_id`, `arrival_count`, `session_start_utc`).
   * Changing the type or semantics of existing fields (e.g. changing `session_id` format without a clear migration path, redefining `arrival_count` to mean something other than “number of arrivals in the session”).

3. **Relaxing coverage / FK invariants**

   * Allowing S1 to drop arrivals or create extra arrivals relative to `arrival_events_5B`.
   * Allowing entity attachments that are not backed by 6A bases/links (unless the new spec explicitly changes the authority boundary and 6A is updated accordingly).
   * Weakening the requirement that every `session_id` in arrivals appears exactly once in the session index.

4. **RNG contract changes that affect reproducibility**

   * Changing the RNG family names or budgets used by S1 (e.g. `entity_attach`, `session_boundary` semantics) without updating the RNG spec and S5’s validation.
   * Changing the domain of stochastic decisions in a way that breaks the relation between arrivals and RNG usage, without updating validation and spec version.

5. **Gating behaviour changes**

   * Allowing S2–S4 to bypass S1 and attach entities/sessions themselves.
   * Making S1 optional for certain worlds or scenarios without an explicit new contract describing that reduced mode.

Any such change MUST be treated as a breaking change and:

* documented in a new spec version,
* accompanied by updated `schemas.6B.yaml`, `dataset_dictionary.layer3.6B.yaml`, and `artefact_registry_6B.yaml`, and
* reflected in S2–S5 specs so they know how to consume the new S1 outputs.

---

### 12.4 Interaction with `parameter_hash` and reproducibility

S1’s contract includes a **reproducibility requirement**:

> For fixed upstream inputs and fixed `(manifest_fingerprint, parameter_hash, seed, scenario_id)`, S1 outputs MUST be deterministic.

Implications:

* Changes to **behaviour priors / session policies** that alter which entities/sessions are chosen for a given world SHOULD be expressed as:

  * a new **parameter pack** (hence a new `parameter_hash`), and/or
  * a new `spec_version_6B` if they affect the contract itself.

* It is **not** acceptable to:

  * silently change attachment/session logic in a way that produces different outputs for the same `(manifest_fingerprint, parameter_hash, seed, scenario_id)` under the same `spec_version_6B`, and still claim idempotence.

Therefore:

* Operational changes that only tweak priors (no contract change) MUST ensure:

  * `parameter_hash` changes, so S1 runs are clearly distinguished, or
  * S1’s idempotence guarantees are restricted to the `(manifest_fingerprint, seed, scenario_id, parameter_hash)` tuple, not just `(manifest_fingerprint, seed, scenario_id)`.

---

### 12.5 Upstream dependency evolution

S1 depends on:

* 5B: `arrival_events_5B` shape and identity,
* 6A: entity/posture shapes (`s1`–`s5` tables),
* Layer-3 RNG and numeric environment.

Binding rules for upstream evolution:

1. **Upstream schema expansions (backwards-compatible)**

   * Upstream segments MAY add optional fields to 5B arrivals or 6A tables.
   * S1 MAY ignore them or start using them internally, as long as S1’s own contract and outputs remain consistent with this spec.

2. **Upstream schema/identity changes (breaking)**

   * Changes to 5B’s arrival primary key, partitioning, or core fields that S1 relies on are breaking for S1.
   * Changes to 6A ID columns (e.g. renaming/remapping `party_id`) or link semantics are breaking.

   In these cases, S1 MUST be updated and this spec (and `spec_version_6B`) MUST be bumped, possibly in lock-step with the upstream segment specs.

3. **New upstream segments**

   * If future layers/segments provide additional **optional context** that S1 may consume, they can be added as `OPTIONAL` entries in `sealed_inputs_6B` without breaking S1.
   * If new upstream segments are required for S1’s correctness (e.g. a new 6A-like entity source), that is a breaking change and MUST be spec-versioned.

---

### 12.6 Co-existence and migration

To support gradual rollout and replay of historical worlds:

1. **Co-existence of spec versions**

   * Orchestrators MUST choose a single `spec_version_6B` per environment / deployment, or per `manifest_fingerprint` if multi-version support is needed.
   * S1 implementations for different spec versions MUST NOT both write to the same dataset ids for the same `(manifest_fingerprint, seed, scenario_id)`.

   If multi-version support is required, it SHOULD be realised by:

   * new dataset ids (e.g. `s1_arrival_entities_6B_v2`), or
   * separate catalogue entries and distinct run pipelines.

2. **Reading older S1 outputs**

   * Newer S5 / tooling MAY read S1 outputs generated under an older spec version for audit/diagnostics, but MUST NOT assume those outputs meet the invariants of a newer spec version.
   * Any compatibility code to normalise old outputs SHOULD be clearly separated and documented.

3. **Migration plan**

   * When bumping `spec_version_6B`, migration guidance SHOULD specify:

     * how to regenerate S1 outputs for existing worlds (if required), and/or
     * how to interpret older outputs where regeneration is not feasible.

---

### 12.7 Non-negotiable stability points for S1

For the lifetime of this `spec_version_6B`, the following aspects of S1 are **stable** and MUST NOT change without a major version bump:

* S1 produces exactly two datasets: `s1_arrival_entities_6B` and `s1_session_index_6B`.
* Both outputs are partitioned by `[seed, fingerprint, scenario_id]`.
* `s1_arrival_entities_6B` has a one-to-one mapping with `arrival_events_5B` for each `(seed, scenario_id)` in a world.
* Entity IDs in S1 outputs are drawn from and consistent with 6A bases/links (no “new” entities invented by S1).
* Every `session_id` referenced in S1 arrivals appears exactly once in the session index with consistent aggregates.
* S2–S4 treat S1 outputs as **the sole starting surfaces** for behaviour (no direct re-attachment from 5B).

Any future design that wishes to relax or modify these guarantees MUST:

* define a new major `spec_version_6B`,
* update schemas and catalogues accordingly, and
* update S2–S5 specs to reflect the new contract.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects the key symbols and shorthand used in the 6B.S1 spec. It is **informative** only; if anything here conflicts with §§1–12, the binding sections win.

---

### 13.1 Identity & axes

* **`manifest_fingerprint` / `fingerprint`**
  World snapshot identifier; partitions S1 outputs at the “world” level and ties them to upstream HashGates.

* **`seed`**
  Stochastic run axis shared with 5B and 6A. S1 outputs are partitioned by `seed` and are deterministic given `(manifest_fingerprint, parameter_hash, seed, scenario_id)` and fixed inputs.

* **`scenario_id`**
  Scenario axis from 5A/5B (e.g. baseline, stress, campaign scenario). S1 outputs are partitioned by `scenario_id` alongside `seed` and `manifest_fingerprint`.

* **`parameter_hash`**
  Hash of the 6B behavioural config pack (behaviour priors, sessionisation policy, etc.). Recorded in S1 outputs (via shared columns) and in S0 gate receipt; not a partition key.

---

### 13.2 Dataset shorthands

* **`AE5B`**
  Shorthand for `arrival_events_5B` — the Layer-2 arrival egress table produced by 5B.
  Authority for: which arrivals exist, their timestamps, routing, and scenario.

* **`AE6B`**
  Shorthand for `s1_arrival_entities_6B` — S1’s arrival→entity→session mapping.
  One row per arrival in `AE5B` for a given `(seed, fingerprint, scenario_id)`.

* **`SESS`**
  Shorthand for `s1_session_index_6B` — one row per session for a `(seed, fingerprint, scenario_id)`.

* **`SI6B`**
  Sometimes used as shorthand for `s1_session_index_6B` in comments/diagrams.

* **`PBASE6A` / `ABASE6A` / `IBASE6A` / `DBASE6A` / `IPBASE6A`** (informal)

  * `PBASE6A` → `s1_party_base_6A`
  * `ABASE6A` → `s2_account_base_6A`
  * `IBASE6A` → `s3_instrument_base_6A`
  * `DBASE6A` → `s4_device_base_6A`
  * `IPBASE6A` → `s4_ip_base_6A`

  Used informally to refer to 6A base tables; the canonical names live in 6A’s dictionary/schemas.

---

### 13.3 Keys & IDs

* **Arrival key (`arrival_id` / `(merchant_id, arrival_seq)` )**
  The primary key for arrivals in 5B:

  ```text
  (seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq)
  ```

  S1 inherits this key unchanged in `s1_arrival_entities_6B`.

* **`session_id`**
  Opaque, S1-defined identifier for a session, unique within `(seed, manifest_fingerprint, scenario_id)`.
  Type is typically a constrained string or integer (e.g. “id64”) as defined in `schemas.6B.yaml`.

* **Entity IDs (from 6A)**

  * `party_id` — primary key in `s1_party_base_6A`.
  * `account_id` — primary key in `s2_account_base_6A`.
  * `instrument_id` — primary key in `s3_instrument_base_6A`.
  * `device_id` — primary key in `s4_device_base_6A`.
  * `ip_id` — primary key in `s4_ip_base_6A`.

S1 MUST treat all of the above as immutable identifiers coming from 6A/5B.

---

### 13.4 Attachment & session notation

* **`session_key_base`**
  The composite key used to group arrivals before applying session boundary logic. Typically something like:

  ```text
  { party_id, device_id, merchant_id, channel_group, scenario_id }
  ```

  Exact composition is set by `sessionisation_policy_6B`.

* **“Candidate set”**
  For an arrival and a given dimension (party, account, device, etc.), the set of all entities that S1 considers **valid** to attach, given 6A links + behaviour priors.

* **“Attachment prior”**
  The per-candidate weight or probability used when sampling an entity from the candidate set for that dimension.

* **“Deterministic attachment”**
  A case where policy + candidate sets imply exactly one valid choice (no RNG draw required) for a dimension.

---

### 13.5 RNG families (names indicative)

S1 uses Layer-3 Philox RNG through event families (exact naming lives in the Layer-3 RNG spec):

* **`rng_event_entity_attach`**
  RNG family used when sampling entity attachments (e.g. picking between multiple candidate parties/accounts/devices).

* **`rng_event_session_boundary`**
  RNG family used when session boundary decisions are stochastic (e.g. randomised inactivity thresholds).

These names are used informally in this spec; the binding definitions (event envelope, `blocks`/`draws`) live in the Layer-3 RNG & numeric policy contracts.

---

### 13.6 Error code prefixes (S1)

Error codes defined in §9 use a consistent prefix:

* **`S1_*`**
  Indicates the error originates from state S1.

Examples (see §9 for semantics):

* `S1_PRECONDITION_S0_FAILED`
* `S1_PRECONDITION_UPSTREAM_GATE_NOT_PASS`
* `S1_PRECONDITION_SEALED_INPUTS_INCOMPLETE`
* `S1_ARRIVAL_COVERAGE_MISMATCH`
* `S1_ENTITY_REFERENCE_INVALID`
* `S1_SESSION_ID_MISMATCH`
* `S1_RNG_EVENT_COUNT_MISMATCH`
* `S1_OUTPUT_WRITE_FAILED`
* `S1_IDEMPOTENCE_VIOLATION`
* `S1_INTERNAL_ERROR`

---

### 13.7 Miscellaneous

* **“World”**
  Informal term for a single `manifest_fingerprint` — a sealed snapshot of all upstream layers.

* **“Partition”** (in S1 context)
  Usually refers to a `(seed, manifest_fingerprint, scenario_id)` slice of the arrival stream and S1 outputs.

* **“Plan surface”**
  Internal, non-egress dataset used as a plan or intermediate surface (both S1 outputs are plan surfaces; not final Layer-3 egress).

These symbols/abbreviations are here purely to make the S1 spec easier to read and to avoid repeating long names; they do not introduce any behaviour beyond what the binding sections already define.

---