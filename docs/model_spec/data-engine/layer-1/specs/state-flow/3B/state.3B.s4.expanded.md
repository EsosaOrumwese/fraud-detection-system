# 3B.S4 — Virtual routing semantics & validation contracts

## 1. Purpose & scope *(Binding)*

1.1 **State identity and role in subsegment 3B**

1.1.1 This state, **3B.S4 — Virtual routing semantics & validation contracts** (“S4”), is an **RNG-free, control-plane state** in Layer-1 subsegment **3B — Virtual merchants & CDN surfaces**. It executes only after:

* **3B.S0 — Gate & environment seal** has successfully sealed the environment for `manifest_fingerprint`;
* **3B.S1 — Virtual classification & settlement node construction** has defined the virtual merchant set and `tzid_settlement` per merchant;
* **3B.S2 — CDN edge catalogue construction** has produced the static edge universe (`edge_catalogue_3B`);
* **3B.S3 — Edge alias tables & virtual edge universe hash** has produced the alias blob/index and `edge_universe_hash_3B` for that same `{seed, manifest_fingerprint}`.

1.1.2 S4’s primary role is to publish a **binding contract for virtual routing and post-arrival validation**. Concretely, S4:

* codifies **dual timezone semantics** for virtual merchants (distinguishing *settlement* vs *operational* clocks);
* defines a **virtual routing policy** that 2B MUST follow when routing virtual merchants via edges;
* defines a **validation contract** that downstream validation harnesses MUST follow when checking the quality and correctness of virtual flows once arrivals exist.

1.1.3 S4 does **not** introduce any new stochastic behaviour or data-plane records. It is a semantics and contracts layer that says:

> “Given the virtual merchants, settlement nodes, edges, alias tables and hashes we already built, **here is exactly how 2B must route virtual traffic and exactly what we will test to prove that behaviour is correct**.”

---

1.2 **High-level responsibilities**

1.2.1 S4 MUST:

* read the **sealed environment** from S0 (`s0_gate_receipt_3B`, `sealed_inputs_3B`) to establish identity, upstream PASS gates and the admissible artefact set;

* consume 3B upstream outputs for the same `{seed, manifest_fingerprint}`:

  * `virtual_classification_3B` and `virtual_settlement_3B` (S1) for virtual set and `tzid_settlement`;
  * `edge_catalogue_3B` and `edge_catalogue_index_3B` (S2) for edge geography and `tzid_operational`;
  * `edge_alias_blob_3B`, `edge_alias_index_3B` and `edge_universe_hash_3B` (S3) for alias representation and virtual edge universe hash;

* read the governed **virtual validation policy pack** (e.g. `virtual_validation.yml`) that specifies validation tests, metrics and thresholds for virtual flows;

* compile and emit a **virtual routing policy surface** (e.g. `virtual_routing_policy_3B`) that:

  * defines per-merchant and global semantics for how 2B MUST use:

    * `tzid_settlement` vs `tzid_operational`;
    * `edge_alias_blob_3B` / `edge_alias_index_3B`;
    * `edge_universe_hash_3B` and any relevant RNG stream names;
  * specifies which event-level fields (IP geo, apparent local time, settlement clock, etc.) MUST be derived from which upstream artefacts;
  * references the exact version IDs and digests of S1–S3 artefacts and relevant policies;

* compile and emit a **validation-test contract** (e.g. `virtual_validation_contract_3B`) that:

  * enumerates the post-arrival tests that MUST be run for this manifest (e.g. IP-country mix, cut-off / clock tests, edge usage vs weights);
  * binds each test to the precise datasets, fields and tolerances it uses;
  * encodes the expected gating semantics for each test (e.g. PASS/WARN/FAIL thresholds, aggregations per merchant / cohort).

1.2.2 S4 MUST ensure that, for any manifest where it reports PASS:

* 2B can route virtual transactions **without consulting any extra ad-hoc logic** beyond:

  * the 3B.S4 routing policy,
  * sealed RNG/routing policy,
  * and the S0–S3 artefacts;

* the validation harness can determine **exactly which checks** must be run over arrivals and labels to consider the virtual path “healthy” for that manifest.

---

1.3 **RNG-free scope**

1.3.1 S4 is **strictly RNG-free**. It MUST NOT:

* open or advance any Philox RNG stream;
* emit any RNG events (including but not limited to routing events such as `cdn_edge_pick`);
* depend on non-deterministic sources (wall-clock time, process ID, host name, unordered filesystem iteration) for any decision.

1.3.2 All S4 behaviour MUST be a pure, deterministic function of:

* the identity triple `{seed, parameter_hash, manifest_fingerprint}`;
* S0’s sealed inputs and upstream gate receipt;
* S1/S2/S3 data-plane outputs and digests;
* the virtual validation policy pack and RNG/routing policy artefact(s);
* the schema/dictionary/registry contracts for 2B’s event schema and 3B’s artefacts.

1.3.3 Given identical inputs (same identity triple, same sealed artefacts, same S1–S3 outputs, same validation policy and contracts), repeated executions of S4 for the same `{seed, parameter_hash, manifest_fingerprint}` MUST produce **bit-identical**:

* virtual routing policy dataset(s);
* validation contract dataset(s);
* any S4 run-summary artefacts.

---

1.4 **Relationship to upstream states and downstream consumers**

1.4.1 S4’s upstream dependencies:

* It **trusts** S0 on:

  * which artefacts are admissible for 3B (via `sealed_inputs_3B`);
  * identity and upstream PASS flags for 1A, 1B, 2A, 3A;

* It **trusts** S1 on:

  * which merchants are virtual (`virtual_classification_3B`);
  * each virtual merchant’s settlement node and `tzid_settlement` (`virtual_settlement_3B`);

* It **trusts** S2 on:

  * the edge universe (`edge_catalogue_3B`) and its indexing (`edge_catalogue_index_3B`);
  * each edge’s `country_iso`, coordinates, and `tzid_operational`;

* It **trusts** S3 on:

  * alias table representation (`edge_alias_blob_3B`, `edge_alias_index_3B`);
  * the virtual edge universe hash (`edge_universe_hash_3B`).

S4 MUST treat all of these upstream artefacts as read-only and MUST NOT attempt to modify or reinterpret their semantics.

1.4.2 S4’s downstream consumers:

* **2B’s virtual routing branch**, which MUST:

  * use S4’s virtual routing policy to:

    * select the correct RNG streams/substreams,
    * decide when/how to route via virtual edges vs physical sites (if any hybrid logic exists),
    * populate event-level geography, clocks and metadata in a way that matches 3B’s declared semantics;
  * verify that the alias and edge artefacts it is decoding match the hashes recorded in S3 and S4.

* The **3B validation state and any 4A/4B-style harness**, which MUST:

  * read S4’s validation–test contract;
  * execute the listed tests against arrivals/labels for this manifest;
  * interpret results and gating thresholds according to S4, when deciding whether virtual flows are “acceptable” under this engine configuration.

---

1.5 **Out-of-scope behaviour**

1.5.1 The following concerns are explicitly **out of scope** for S4 and are handled in other states:

* Virtual vs non-virtual merchant classification and settlement node construction — S1 is authoritative.
* Edge placement, jitter, country attribution and operational tzid assignment — S2 is authoritative.
* Alias table construction and edge-universe hashing — S3 is authoritative.
* Per-arrival routing decisions, edge sampling and routing RNG events — handled in 2B.
* 3B’s segment-level validation bundle and `_passed.flag` — constructed by the 3B validation state (though it consumes S4’s outputs).

1.5.2 S4 MUST NOT:

* create, modify or delete edges or merchants;
* change any `tzid_settlement` or `tzid_operational` values;
* construct or modify alias tables or hashes;
* perform or log per-arrival routing;
* emit its own segment-level PASS flag.

1.5.3 S4’s mandate is strictly to:

> **Freeze the semantics of virtual routing (dual clocks, edge vs settlement roles, RNG stream usage) and the semantics of virtual validation (which tests, which fields, which thresholds) for a given manifest, in a deterministic, RNG-free way that downstream routing and validation components must obey.**

---

### Contract Card (S4) - inputs/outputs/authorities

**Inputs (authoritative; see Section 3 for full list):**
* `s0_gate_receipt_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S0
* `sealed_inputs_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S0
* `virtual_classification_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3B.S1
* `virtual_settlement_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3B.S1
* `edge_catalogue_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3B.S2
* `edge_catalogue_index_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3B.S2
* `edge_alias_blob_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3B.S3
* `edge_alias_index_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3B.S3
* `edge_universe_hash_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S3
* `virtual_validation_policy` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `cdn_key_digest` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `alias_layout_policy_v1` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required

**Authority / ordering:**
* S4 is the sole authority for virtual routing and validation contracts.

**Outputs:**
* `virtual_routing_policy_3B` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `virtual_validation_contract_3B` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `s4_run_summary_3B` - scope: FINGERPRINT_SCOPED; gate emitted: none (optional)

**Sealing / identity:**
* External policy inputs MUST appear in `sealed_inputs_3B` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or contract violations -> abort; no outputs published.

## 2. Preconditions & gated inputs *(Binding)*

2.1 **Execution context & identity**

2.1.1 S4 SHALL execute only in the context of a Layer-1 run where the identity triple

> `{seed, parameter_hash, manifest_fingerprint}`

has already been resolved by the enclosing engine and is consistent with the Layer-1 identity/hashing policy.

2.1.2 At entry, S4 MUST be provided with:

* `seed` — the Layer-1 Philox seed for this run;
* `parameter_hash` — the governed 3B parameter hash (including S4-relevant configuration);
* `manifest_fingerprint` — the enclosing manifest fingerprint.

2.1.3 S4 MUST NOT recompute or override these values. It MUST:

* treat them as read-only identity inputs; and
* ensure that any identity echoes it writes (e.g. into routing/validation policy artefacts) match these values and those embedded in `s0_gate_receipt_3B`.

---

2.2 **Dependence on 3B.S0 (gate & sealed inputs)**

2.2.1 For a given `manifest_fingerprint`, S4 MAY proceed only if both of the following artefacts exist and are schema-valid:

* `s0_gate_receipt_3B` at its canonical fingerprint-partitioned path;
* `sealed_inputs_3B` at its canonical fingerprint-partitioned path.

2.2.2 Before performing any work, S4 MUST:

* load and validate `s0_gate_receipt_3B` against `schemas.3B.yaml#/validation/s0_gate_receipt_3B`;
* load and validate `sealed_inputs_3B` against `schemas.3B.yaml#/validation/sealed_inputs_3B`;
* assert that `segment_id = "3B"` and `state_id = "S0"` in the gate receipt;
* assert that `manifest_fingerprint` in the gate receipt equals the run’s `manifest_fingerprint`;
* where present, assert that `seed` and `parameter_hash` in the gate receipt equal the values supplied to S4.

2.2.3 S4 MUST also assert that, in `s0_gate_receipt_3B.upstream_gates`:

* `segment_1A.status = "PASS"`;
* `segment_1B.status = "PASS"`;
* `segment_2A.status = "PASS"`;
* `segment_3A.status = "PASS"`.

If any of these statuses is not `"PASS"`, S4 MUST treat the 3B environment as **not gated** and fail with a FATAL upstream-gate error. S4 MUST NOT attempt to re-verify or repair upstream validation bundles directly.

2.2.4 If `s0_gate_receipt_3B` or `sealed_inputs_3B` is missing, schema-invalid, or inconsistent with the run identity, S4 MUST fail fast and MUST NOT attempt to “re-seal” inputs on its own.

---

2.3 **Dependence on 3B.S1–S3 (virtual set, edges, alias & hash)**

2.3.1 S4 MUST treat S1–S3 as functional preconditions. For a given `{seed, manifest_fingerprint}`, S4 MAY proceed only if:

* `virtual_classification_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/plan/virtual_classification_3B`;
* `virtual_settlement_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/plan/virtual_settlement_3B`;
* `edge_catalogue_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/plan/edge_catalogue_3B`;
* `edge_catalogue_index_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/plan/edge_catalogue_index_3B`;
* `edge_alias_blob_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}` exists and passes header-level validation against `schemas.3B.yaml#/egress/edge_alias_blob_3B`;
* `edge_alias_index_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/egress/edge_alias_index_3B`;
* `edge_universe_hash_3B@manifest_fingerprint={manifest_fingerprint}` exists and validates against `schemas.3B.yaml#/validation/edge_universe_hash_3B`.

2.3.2 Before compiling routing/validation contracts, S4 MUST at least:

* verify that the virtual merchant set implied by `virtual_classification_3B` and `virtual_settlement_3B` is coherent (e.g. one settlement node per virtual merchant as defined by S1);
* verify that for each merchant with edges in `edge_catalogue_3B`, there is a corresponding alias table/index entry in S3 (unless a documented “no-edge” or special mode is in effect);
* verify consistency between `edge_catalogue_index_3B` and `edge_alias_index_3B` (per-merchant/global counts agreed);
* verify that `edge_universe_hash_3B` is internally consistent (its components align with S2/S3 artefacts) per the S3 spec.

2.3.3 S4 MUST NOT:

* re-create or mutate virtual classification (S1), edges (S2), or alias tables/hashes (S3);
* introduce any new business semantics that contradict what S1–S3 already established.

If any S1–S3 invariant needed for S4 is violated, S4 MUST fail with a S1/S2/S3 contract error and MUST NOT proceed.

2.3.4 If configuration explicitly disables virtual routing for this manifest (e.g. `enable_virtual_routing=false`), S4 MUST:

* either produce a trivial routing policy/validation contract that encodes “no virtual routing” semantics, or
* short-circuit according to the 3B design (but still obey identity, S0/S1/S2/S3 gating, and schema correctness).

The chosen behaviour MUST be explicitly defined in the S4 spec and contracts.

---

2.4 **Required sealed artefacts (validation & routing policies)**

2.4.1 S4 MUST treat `sealed_inputs_3B` as the **sole authority** on which policy artefacts it may consume. For S4 to run, `sealed_inputs_3B` MUST contain rows for at least the following **mandatory** 3B control-plane artefacts (with well-formed entries):

* **Virtual validation policy** (e.g. `virtual_validation.yml`)

  * defines the list of candidate tests, metrics and thresholds for virtual flows
  * includes IDs for test types (e.g. IP-country mix, cut-off / clock tests, edge-usage tests) and their parameterisation.

* **Routing/RNG policy** relevant to virtual routing (shared with 2B)

  * defines which RNG streams/substreams 2B MUST use for virtual edge selection (even though S4 is RNG-free);
  * defines layout expectations for alias decode (e.g. supported alias layout versions, mapping alias indices → edges).

* **Event schema / routing field contracts**

  * either via explicit schema anchors (e.g. 2B event schema in Layer-1 schemas) or via a routing-field policy, indicating:

    * fields that will carry settlement vs operational tz information;
    * fields that will carry IP geo vs physical site geo;
    * any extra per-event fields used in virtual validations (e.g. `ip_country`, `apparent_local_time`, `settlement_day`).

2.4.2 For each such artefact, S4 MUST:

* locate its row in `sealed_inputs_3B` using `logical_id` (and, if needed, `owner_segment`, `artefact_kind`);
* resolve `path` and `schema_ref` (if non-null);
* open and validate the artefact against its schema;
* if hardened mode is enabled, recompute its digest and confirm it matches `sha256_hex`.

2.4.3 If any required artefact (validation policy, routing policy, event schema contract) is missing from `sealed_inputs_3B`, unreadable, schema-incompatible, or digest-mismatched, S4 MUST fail with a FATAL sealed-input error and MUST NOT attempt to resolve it “out-of-band” via dictionary/registry.

---

2.5 **Feature flags and configuration modes**

2.5.1 If the 3B configuration includes feature flags or modes that affect S4 (for example):

* `enable_virtual_routing` / `disable_virtual_routing`;
* `virtual_validation_profile ∈ {strict, relaxed, off}`;
* per-merchant “hybrid routing” modes (e.g. partial virtual vs physical fallback),

S4 MUST treat these flags as part of the governed 3B parameter set that contributed to `parameter_hash`.

2.5.2 S4 MUST:

* read these configuration values from a governed location (e.g. parameter bundle sealed by S0);
* enforce the semantics for each mode exactly as specified in the 3B design (e.g. empty routing policy vs populated policy, validation tests enabled/disabled).

2.5.3 If a feature flag enables additional required artefacts (e.g. an extra validation profile file, or per-merchant override tables), S4 MUST:

* treat those artefacts as mandatory in that mode;
* fail if they are not sealed in `sealed_inputs_3B`.

---

2.6 **Scope of gated inputs & downstream obligations**

2.6.1 The union of:

* S1 outputs (`virtual_classification_3B`, `virtual_settlement_3B`);
* S2 outputs (`edge_catalogue_3B`, `edge_catalogue_index_3B`);
* S3 outputs (`edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`);
* policy artefacts sealed in `sealed_inputs_3B` (virtual validation policy, routing/RNG policy, event schema contracts, and any S4-specific configs),

SHALL define the **closed input universe** for 3B.S4.

2.6.2 S4 MUST NOT:

* read any artefact not listed in `sealed_inputs_3B` for the target `manifest_fingerprint`;
* use environment variables, local adhoc files or network calls as inputs to routing/validation semantics;
* infer new semantics from unstated assumptions (e.g. guessing validation thresholds from code rather than from the validation policy).

2.6.3 Downstream components (2B routing, 3B validation, 4A/4B harness) MAY assume that:

* S4’s routing policy and validation contract were compiled **only** from S0–S3 outputs and sealed 3B artefacts;
* any missing or inconsistent artefact that would have affected routing or validation semantics would have caused S4 to fail, not to produce partial or silently degraded outputs.

2.6.4 If, during execution, S4 discovers that it needs an artefact or configuration that is not present in `sealed_inputs_3B` (or is not represented in the 3B contracts), S4 MUST:

* treat this as a configuration / S0-sealing error (or contracts error);
* fail fast with an appropriate `E3B_S4_*` error code;
* NOT attempt to resolve or invent the missing input outside the sealed universe.

---

## 3. Inputs & authority boundaries *(Binding)*

3.1 **Control-plane inputs from 3B.S0**

3.1.1 S4 SHALL treat the following S0 artefacts as **required control-plane inputs** for the target `manifest_fingerprint`:

* `s0_gate_receipt_3B` (fingerprint-scoped JSON);
* `sealed_inputs_3B` (fingerprint-scoped table).

3.1.2 For S4, `s0_gate_receipt_3B` is the **sole authority** on:

* the identity triple `{seed, parameter_hash, manifest_fingerprint}` that S4 MUST echo where appropriate;
* upstream gate state for 1A, 1B, 2A, 3A;
* which versions of `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, `artefact_registry_3B.yaml` are in force for this run;
* the set of artefacts that have been sealed as admissible inputs for 3B (via `sealed_inputs_3B`).

3.1.3 `sealed_inputs_3B` is the **only list** of artefacts S4 is permitted to read. S4 MUST NOT:

* discover additional artefacts via dictionary/registry lookups that are not present in `sealed_inputs_3B`;
* use ad-hoc paths, environment variables, or network resources as inputs to routing/validation semantics.

3.1.4 When S4 uses any artefact, it MUST:

* locate the corresponding row in `sealed_inputs_3B` via `logical_id` (and, where necessary, `owner_segment` and `artefact_kind`);
* treat the recorded `path` as canonical;
* treat `schema_ref` (if non-null) as canonical shape;
* treat `sha256_hex` as the canonical digest, and treat any mismatch as a hard error (if S4 recomputes a digest).

---

3.2 **Inputs from 3B.S1 — virtual semantics**

3.2.1 S4 SHALL treat S1 outputs as the **sole authority** on virtual merchant semantics:

* `virtual_classification_3B` — authoritative classification of merchants as virtual vs non-virtual;
* `virtual_settlement_3B` — authoritative per-virtual-merchant settlement node, including `tzid_settlement`.

3.2.2 S4 MUST use `virtual_classification_3B` only to:

* know which merchants are in scope for virtual routing semantics, and
* detect consistency anomalies (e.g. alias/edges for a merchant not marked virtual).

S4 MUST NOT:

* re-evaluate MCC/channel rules or any other classification logic;
* mark new merchants as virtual or non-virtual;
* “correct” or override S1’s classification results.

3.2.3 S4 MUST use `virtual_settlement_3B` only to:

* obtain `tzid_settlement` and legal settlement coordinates per virtual merchant;
* define in policy terms which *clock* is used for settlement-day semantics.

S4 MUST NOT:

* change `tzid_settlement` or settlement coordinates;
* reinterpret settlement geometry or move settlement nodes.

3.2.4 If S4 detects inconsistencies between S1 and later outputs (e.g. edge/alias entries for merchants not marked virtual, or missing settlement nodes in a mode that requires them), it MUST treat this as an upstream contract violation (S1/S2/S3) and fail, rather than attempting to repair the data.

---

3.3 **Inputs from 3B.S2 — edge semantics**

3.3.1 S4 SHALL treat S2 outputs as the **sole authority** on the virtual edge universe:

* `edge_catalogue_3B` — per-edge node records (`merchant_id`, `country_iso`, edge coordinates, `tzid_operational`, `edge_weight`, spatial provenance);
* `edge_catalogue_index_3B` — per-merchant/global edge counts and digests.

3.3.2 S4 MAY consume S2 outputs to:

* understand the **operational geography** available to virtual routing (countries, edge locations, `tzid_operational`);
* refer to S2 digests in downstream policy (e.g. in routing or validation contracts);
* define validation hooks that depend on S2 semantics (e.g. IP-country mix vs `cdn_country_weights`).

3.3.3 S4 MUST NOT:

* add, remove, or relocate edges;
* change any S2 field values (`country_iso`, coordinates, `tzid_operational`, `edge_weight`);
* re-derive or rescale `edge_weight` in ways that change its semantics.

3.3.4 Where S4 needs aggregate facts (e.g. per-merchant edge counts) it MUST:

* treat `edge_catalogue_index_3B` as authoritative, or
* if it recomputes counts from `edge_catalogue_3B`, treat any discrepancy as an upstream inconsistency, not as something to “normalise away”.

---

3.4 **Inputs from 3B.S3 — alias semantics & edge universe hash**

3.4.1 S4 SHALL treat S3 outputs as the **sole authority** on the alias representation and signed edge universe:

* `edge_alias_blob_3B` — authoritative per-merchant alias tables (implementation-level representation);
* `edge_alias_index_3B` — authoritative index into the alias blob (offsets, lengths, per-merchant metadata);
* `edge_universe_hash_3B` — authoritative descriptor of the **virtual edge universe hash** and its component digests.

3.4.2 S4 MAY consume S3 outputs to:

* reference `layout_version`, `blob_sha256_hex`, `edge_alias_index_sha256_hex`, etc. in the routing policy surface;
* assert in policy that 2B **MUST** verify `edge_universe_hash` before routing;
* include S3 digests as part of a broader “routing universe” description exposed to validation harnesses.

3.4.3 S4 MUST NOT:

* inspect or decode alias tables for the purpose of re-computing distributions (that is S3/S2’s responsibility);
* modify alias blobs or indexes;
* compute a new universe hash that overrides `edge_universe_hash_3B`;
* define new alias layouts or low-level decode semantics (those belong to alias-layout policy and 2B).

3.4.4 If S4 recomputes any digest of S3 outputs for sanity (e.g. to echo in its own artefacts) and detects a mismatch vs `edge_universe_hash_3B.components`, it MUST treat this as an S3/ environment corruption error and fail, not “fix” the hash.

---

3.5 **Validation-policy & routing-policy inputs**

3.5.1 **Virtual validation policy**

S4 MUST consume a governed **virtual validation policy** artefact (e.g. `virtual_validation.yml`), sealed in `sealed_inputs_3B`, which SHALL be the **sole authority** on:

* which **test types** exist for virtual flows (e.g. IP-country mix, cut-off / clock tests, edge usage vs weight);
* how each test is parameterised (per merchant, per cohort, global);
* thresholds, tolerances, and classification as PASS/WARN/FAIL;
* any aggregation windows (e.g. per settlement day, per scenario, per manifest).

S4 MUST NOT invent new validation tests or thresholds outside this policy; any test included in S4’s validation contract MUST correspond to a policy-defined test type and parameters.

3.5.2 **Routing/RNG policy (compatibility)**

S4 MUST consume the Layer-1 routing/RNG policy artefact(s) (shared with 2B), which are the **sole authority** on:

* which RNG streams/substreams 2B MUST use for virtual edge selection and virtual vs physical routing choices;
* which alias layouts and blob/index versions 2B’s decoder supports;
* any constraints that 2B must honour when routing virtual traffic (e.g. “always use alias for these merchants”, “never mix virtual and physical edges in same stream”).

S4 MUST NOT:

* define its own RNG streams or budgets;
* attempt to override the layer-wide RNG policy.

S4’s routing semantics MUST be expressed **in terms of** the streams / layouts declared in this policy.

3.5.3 **Event schema / routing-field contracts**

S4 MUST bind routing semantics and validation tests to the **Layer-1 event schema** (owned by 2B/Layer-1), via:

* schema anchors for event fields (e.g. `event.ip_country`, `event.latitude`, `event.longitude`, `event.local_time`, `event.settlement_day`, etc.);
* a routing-field contract (if defined) that states which fields must be populated from:

  * S1 settlement semantics;
  * S2 edge semantics;
  * 2B’s own routing logic.

The event schema / routing-field contract remains the **authority** on event-shape and field naming; S4 only specifies **which upstream value** each field must carry for virtual flows.

---

3.6 **Authority boundaries summary**

3.6.1 S4 SHALL respect the following authority boundaries:

* **JSON-Schema packs** (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.3B.yaml`, upstream segment schemas) are the **only authorities on shapes** of all datasets, policies and event records. S4 MUST NOT relax or override these shapes.

* **Dataset dictionaries** (Layer-1, 3B, and upstream) are the **only authorities on dataset IDs, path templates, partition keys and writer sort orders**. S4 MUST NOT hard-code alternative paths or partition schemes.

* **Artefact registries** are the **only authorities on logical IDs, ownership, licence classes and roles** of policies and datasets. S4 MUST NOT invent unregistered artefacts.

* **S1 outputs** are the **only authority** on virtual merchant membership and settlement (`tzid_settlement`, settlement coordinates).

* **S2 outputs** are the **only authority** on edge nodes (`edge_catalogue_3B`) and their attributes (`country_iso`, edge coordinates, `tzid_operational`, edge weights).

* **S3 outputs** are the **only authority** on alias representation (`edge_alias_blob_3B`, `edge_alias_index_3B`) and `edge_universe_hash_3B`.

* **Virtual validation policy** is the **only authority** on which validation tests exist for virtual flows, how they are parameterised, and what thresholds apply.

* **Routing/RNG policy & event schema** are the **only authorities** on how 2B must handle RNG streams, alias decode and event field shapes; S4 only constrains **how those are used** for virtual flows.

3.6.2 If S4 detects any conflict between:

* what schemas/dictionaries/registries/policies claim, and
* what is observed on disk or in upstream outputs,

S4 MUST treat this as a configuration/contract error and fail, rather than silently adjusting semantics.

3.6.3 Any future extension that introduces new inputs to S4 (e.g. new validation profiles, additional routing modes, extra cross-segment digests) MUST:

* be registered in the relevant dictionaries/registries;
* be sealed in `sealed_inputs_3B`;
* have its shape defined in the appropriate schema;
* and be reflected explicitly in this section’s authority-boundary description before S4 is modified to rely on it.

---

## 4. Outputs (datasets) & identity *(Binding)*

4.1 **Overview of S4 outputs**

4.1.1 For each successfully prepared manifest `manifest_fingerprint`, S4 SHALL emit the following 3B-owned, RNG-free control-plane artefacts:

* **`virtual_routing_policy_3B`** — a machine-readable contract describing how 2B MUST route virtual merchants via the S1–S3 artefacts.
* **`virtual_validation_contract_3B`** — a machine-readable contract describing which virtual-specific tests MUST be run by the validation harness (3B validation state / 4A–4B) for this manifest.

4.1.2 S4 MAY also emit an optional **S4 run-summary / receipt** (e.g. `s4_run_summary_3B`) for observability, but such a dataset is informative only and MUST NOT alter the semantics of `virtual_routing_policy_3B` or `virtual_validation_contract_3B`.

4.1.3 S4 MUST NOT emit any data-plane egress (no events, no edges, no labels) and MUST NOT emit a 3B segment-level `_passed.flag`. Segment-level PASS/FAIL remains the responsibility of the 3B validation state.

---

4.2 **Virtual routing policy contract — `virtual_routing_policy_3B`**

4.2.1 `virtual_routing_policy_3B` SHALL be the **authoritative routing contract** for virtual merchants in this manifest. It MUST be declared in `dataset_dictionary.layer1.3B.yaml` with at least:

* `id: virtual_routing_policy_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/egress/virtual_routing_policy_3B`
* `path: data/layer1/3B/virtual_routing_policy/manifest_fingerprint={manifest_fingerprint}/virtual_routing_policy_3B.json`
* `partitioning: ["fingerprint"]`
* `ordering: []` (single JSON document; no row sort concept)

4.2.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* reference `name: virtual_routing_policy_3B` and its `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a stable `manifest_key` (e.g. `"mlr.3B.virtual_routing_policy_3B"`);
* list `2B` and the 3B validation state as primary consumers.

4.2.3 `schemas.3B.yaml#/egress/virtual_routing_policy_3B` MUST define a JSON object containing at least:

* **Identity & versioning**

  * `manifest_fingerprint`, `parameter_hash`, `edge_universe_hash` — MUST mirror S0/S3 values;
  * `routing_policy_id` / `routing_policy_version` — logical ID & version from the sealed routing/RNG policy artefact;
  * `virtual_validation_policy_id` / `virtual_validation_policy_version` — logical ID & version of the virtual validation policy pack;
  * `cdn_key_digest`, `alias_layout_version`, `alias_blob_manifest_key`, `alias_index_manifest_key`, `edge_universe_hash_manifest_key` — digests/manifest keys that allow downstream readers to verify artefact provenance.

* **Dual timezone semantics**

  * `dual_timezone_semantics` object describing which event fields correspond to settlement vs operational clocks:
    * `tzid_settlement_field` — schema anchor for the settlement TZ field populated from S1;
    * `tzid_operational_field` — schema anchor for the operational (edge) TZ field populated from S2/S3;
    * `settlement_cutoff_rule` — string identifier describing which cutoff logic applies.

* **Geography / field bindings**

  * `geo_field_bindings` object naming the schema anchors that must be filled from edge geometry:
    * `ip_country_field`, `ip_latitude_field`, `ip_longitude_field`.

* **Artefact references**

  * `artefact_paths` object containing canonical strings for:
    * `edge_catalogue_index`, `edge_alias_blob`, `edge_alias_index`.
  * `alias_blob_manifest_key`, `alias_index_manifest_key`, `edge_universe_hash_manifest_key` echo the manifest keys from S3.

* **RNG & alias usage for virtual routing**

  * `virtual_edge_rng_binding` defining the RNG stream/label and event schema that 2B MUST use (`module`, `substream_label`, `event_schema`);
  * `alias_layout_version` plus the artefact paths above tie the routing policy to specific alias tables.

* **Per-merchant overrides (optional)**

  * `overrides` array of objects `{ merchant_id, mode, notes }` where `mode ∈ {virtual, hybrid, disable_virtual}` conveys any per-merchant deviations from default routing semantics.

* **Notes**

  * Optional free-text `notes` field for diagnostics or operator guidance.

4.2.4 The schema may include additional fields (e.g. comments, debug flags), but they MUST be explicitly marked optional and MUST NOT change the semantics of required routing instructions.

4.2.5 S4 MUST populate `virtual_routing_policy_3B` in a way that:

* references all S1–S3 artefacts via their canonical manifest keys or digests;
* does not introduce any routing logic that cannot be traced back to S1–S3 outputs or sealed policies;
* can be consumed by 2B without needing any additional, out-of-band configuration.

---

4.3 **Validation-test contract - `virtual_validation_contract_3B`**

4.3.1 `virtual_validation_contract_3B` SHALL be the **authoritative test contract** for virtual-specific validation on this manifest. It MUST be declared in `dataset_dictionary.layer1.3B.yaml` with at least:

* `id: virtual_validation_contract_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/egress/virtual_validation_contract_3B`
* `path: data/layer1/3B/virtual_validation_contract/manifest_fingerprint={manifest_fingerprint}/virtual_validation_contract_3B.parquet`
* `partitioning: ["fingerprint"]`
* `ordering: ["test_id"]`

4.3.2 The corresponding registry entry MUST:

* reference `name: virtual_validation_contract_3B` and `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a stable `manifest_key` (e.g. `"mlr.3B.virtual_validation_contract_3B"`);
* list consumers: 3B validation state and any global validation harness.

4.3.3 `schemas.3B.yaml#/egress/virtual_validation_contract_3B` MUST define a table-shaped dataset with at least one row per **test configuration**. Required columns include:

* `test_id`

  * string identifier, unique per `fingerprint`;
  * stable across runs for the same manifest.

* `test_type`

  * enum; examples: `"IP_COUNTRY_MIX"`, `"SETTLEMENT_CUTOFF"`, `"EDGE_USAGE_VS_WEIGHT"`, etc.;
  * MUST correspond to a test type defined in the virtual validation policy.

* `scope`

  * describes where the test is applied, e.g. `"per_merchant"`, `"per_scenario"`, `"global"`.

* `target_population`

  * description of which merchants / segments / flows are in scope, e.g.:

    * `{"virtual_only":true}`, or
    * an expression referencing S1 classification fields.

* `inputs`

  * structured field (object/JSON) that binds this test to concrete data:

    * references to datasets (by manifest key or dataset ID) — e.g. arrivals, decisions, labels;
    * event fields (by schema anchor) — e.g. `event.ip_country`, `event.settlement_day`.

* `thresholds`

  * structured field describing PASS/WARN/FAIL thresholds, e.g. maximum KL divergence, max absolute deviation, time windows.

* `severity`

  * enum describing how a FAIL should be interpreted by the validation harness ( `"BLOCKING"`, `"WARNING"`, `"INFO"`).

4.3.4 Optional columns (schema-optional) may include:

* `description` — human–readable description of the test.
* `profile` — to group tests under profiles (e.g. `"strict"`, `"relaxed"`).
* `enabled` — boolean flag to explicitly enable/disable a test for this manifest (per policy).

4.3.5 S4 MUST ensure that:

* every test row corresponds to a policy-defined test in the virtual validation policy pack;
* all referenced datasets and fields exist in the manifest’s schemas and dictionaries;
* there is no ambiguity in how a test should be applied (scope, inputs and thresholds MUST be fully specified in the row).

---

4.4 **Optional S4 run-summary / receipt - `s4_run_summary_3B`**

4.4.1 If S4 produces a run-summary artefact, `s4_run_summary_3B` MUST be declared in the 3B contracts with:

* `id: s4_run_summary_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/validation/s4_run_summary_3B`
* `path: data/layer1/3B/s4_run_summary/manifest_fingerprint={manifest_fingerprint}/s4_run_summary_3B.json`
* `partitioning: ["fingerprint"]`
* `ordering: []`

4.4.2 `s4_run_summary_3B` MAY capture at least:

* `manifest_fingerprint`, `parameter_hash`;
* S4 `status ∈ {"PASS","FAIL"}` and `error_code` if any;
* counts of:

  * virtual merchants in scope,
  * merchants covered by routing semantics,
  * tests defined in `virtual_validation_contract_3B`;
* IDs/versions of key policies (`routing_policy_id`, `virtual_validation_policy_id`);
* references (paths or manifest keys) to:

  * `virtual_routing_policy_3B`,
  * `virtual_validation_contract_3B`,
  * `edge_universe_hash_3B`.

4.4.3 This artefact is **informative**: it does not alter routing/validation semantics. Absence of `s4_run_summary_3B` MUST NOT change the binding behaviour of S4; it only helps with observability.

---

4.5 **Identity & partitioning for S4 outputs**

4.5.1 All S4 outputs are manifest-scoped control-plane artefacts. Their **on-disk identity** is:

* `manifest_fingerprint={manifest_fingerprint}` as the only partition key.

4.5.2 `virtual_routing_policy_3B` and `virtual_validation_contract_3B` MUST:

* be stored under their respective `path`s with `manifest_fingerprint={manifest_fingerprint}`;
* not include `seed` or `run_id` as partition keys.

If a future version introduces per-seed variants, this MUST be treated as a change in partition law and go through change control.

4.5.3 S4 MAY include identity echoes (`manifest_fingerprint`, `parameter_hash`, `edge_universe_hash`) in its outputs as columns/fields. If present:

* their values MUST match S0 and S3;
* they MUST NOT be used as partition keys;
* the 3B validation state MAY enforce path↔embed equality for these fields as part of segment-level validation.

---

4.6 **Downstream consumption & authority**

4.6.1 Within the virtual path:

* 2B’s virtual routing branch MUST treat `virtual_routing_policy_3B` as the **binding routing contract** for virtual merchants in this manifest. It MUST NOT:

  * introduce additional implicit rules not present in S4’s policy or sealed Layer-1 policies;
  * ignore or override routing constraints recorded in the policy.

* The validation harness (3B validation state, 4A/4B) MUST treat `virtual_validation_contract_3B` as the **binding test manifest** for virtual flows. It MUST:

  * run the tests declared;
  * interpret PASS/WARN/FAIL through the thresholds and severity defined there.

4.6.2 No other state or component MAY mutate S4 outputs in place. Any new routing/validation behaviour MUST:

* be encoded by creating new schema/dictionary/registry versions and updated S4 contracts;
* not rely on ad-hoc, out-of-band configuration.

---

4.7 **Immutability & idempotence**

4.7.1 For a fixed `{seed, parameter_hash, manifest_fingerprint}`, S4 outputs are **logically immutable**:

* Once S4 reports PASS and publishes `virtual_routing_policy_3B` and `virtual_validation_contract_3B` for a fingerprint, subsequent S4 runs with the same identity triple MUST NOT change their contents.

4.7.2 On re-execution for the same identity triple:

* S4 MAY recompute expected outputs;
* S4 MUST compare recomputed outputs to on-disk artefacts (by bytes or canonical digest);
* If identical, S4 MAY treat the run as idempotent and leave artefacts unchanged;
* If different, S4 MUST fail with a conflict error (e.g. `E3B_S4_OUTPUT_INCONSISTENT_REWRITE`) and MUST NOT overwrite existing artefacts.

4.7.3 S4 MUST publish its outputs atomically per fingerprint:

* It MUST NOT expose a state where `virtual_routing_policy_3B` exists but `virtual_validation_contract_3B` does not (or vice versa) for the same `manifest_fingerprint`;
* Any partial or mismatched state MUST be treated as failure by downstream components, not as valid configuration.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

5.1 **`virtual_routing_policy_3B` - dataset contract**

5.1.1 The dataset **`virtual_routing_policy_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with at least:

* `id: virtual_routing_policy_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/egress/virtual_routing_policy_3B`
* `path: data/layer1/3B/virtual_routing_policy/manifest_fingerprint={manifest_fingerprint}/virtual_routing_policy_3B.json`
* `partitioning: ["fingerprint"]`
* `ordering: []` (single JSON document per fingerprint)

5.1.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* reference `name: virtual_routing_policy_3B` and the same `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a stable `manifest_key` (e.g. `"mlr.3B.virtual_routing_policy_3B"`);
* list `2B` and the 3B validation state as primary `consumed_by` clients.

5.1.3 `schemas.3B.yaml#/egress/virtual_routing_policy_3B` MUST define a JSON object with, at minimum, the following **required fields**:

* **Identity & contracts**

  * `manifest_fingerprint`

    * type: string, MUST match `manifest_fingerprint={manifest_fingerprint}` partition;
    * SHOULD reuse `schemas.layer1.yaml#/validation/manifest_fingerprint_resolved`.

  * `parameter_hash`

    * type: string (if present), MUST match S0 `parameter_hash`;
    * SHOULD reuse `schemas.layer1.yaml#/validation/parameter_hash_resolved`.

  * `edge_universe_hash`

    * type: string (hex digest);
    * MUST be copied from `edge_universe_hash_3B.edge_universe_hash`.

  * `routing_policy_id` / `routing_policy_version`

    * type: string;
    * logical ID & version of the routing/RNG policy artefact sealed in `sealed_inputs_3B`.

  * `virtual_validation_policy_id` / `virtual_validation_policy_version`

    * type: string;
    * logical ID & version of the virtual validation policy pack.

* **Global routing semantics**

  * `dual_timezone_semantics` — object describing how settlement vs operational time zones are used, including:

    * `settlement_timezone_field` — schema anchor or path to the event field holding `tzid_settlement` or settlement-day info;
    * `operational_timezone_field` — schema anchor/path to the event field holding `tzid_operational`/apparent local time;
    * `settlement_day_definition` — description (e.g. anchor to a contract schema) of how settlement-day boundaries are computed from `tzid_settlement`;
    * `operational_day_definition` — similar for operational/local day if applicable.

  * `geo_field_bindings` — object mapping:

    * event fields such as `ip_country_field`, `ip_latitude_field`, `ip_longitude_field`
    * to their upstream sources (`edge_catalogue_3B` vs `virtual_settlement_3B` vs physical sites), using schema anchors or manifest keys.

* **Alias & RNG integration**

  * `alias_layout_version`

    * type: string/integer;
    * MUST match `layout_version` used by S3 in `edge_alias_blob_3B` / `edge_alias_index_3B`.

  * `alias_blob_manifest_key`

    * type: string;
    * MUST reference the `manifest_key` for `edge_alias_blob_3B` in the 3B registry.

  * `alias_index_manifest_key`

    * type: string;
    * MUST reference the `manifest_key` for `edge_alias_index_3B`.

  * `edge_universe_hash_manifest_key`

    * type: string;
    * MUST reference the `manifest_key` for `edge_universe_hash_3B`.

  * `virtual_edge_rng_binding` — object describing which RNG streams 2B MUST use, including:

    * `edge_pick_stream_id` — logical RNG stream name or ID from the routing/RNG policy;
    * `edge_pick_substream_label` — substream label (if applicable) used by 2B when sampling edges;
    * any other fixed RNG identifiers needed by 2B to route virtual flows (e.g. multi-stream vs single-stream semantics).

* **Per-merchant / per-class overrides (if supported)**

  * Optionally, a `merchant_overrides` array/table with entries:

    * `merchant_id` (or `merchant_key`)
    * `mode` — enum, e.g. `"VIRTUAL_ONLY"`, `"HYBRID"`, `"DISABLED"`, if such modes exist;
    * `notes` or small config payload to clarify specific handling.

5.1.4 Any additional fields in `virtual_routing_policy_3B` beyond the above MUST be:

* explicitly defined in `schemas.3B.yaml`;
* clearly marked as `optional` where they are not essential for correctness;
* non-breaking with respect to 2B and validation consumers that only understand the earlier schema version.

---

5.2 **`virtual_validation_contract_3B` — dataset contract**

5.2.1 The dataset **`virtual_validation_contract_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with at least:

* `id: virtual_validation_contract_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/egress/virtual_validation_contract_3B`
* `path: data/layer1/3B/virtual_validation_contract/manifest_fingerprint={manifest_fingerprint}/virtual_validation_contract_3B.parquet`
* `partitioning: ["fingerprint"]`
* `ordering: ["test_id"]`

5.2.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* reference `name: virtual_validation_contract_3B` and `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a stable `manifest_key` (e.g. `"mlr.3B.virtual_validation_contract_3B"`);
* list the 3B validation state and global validation harness as primary consumers.

5.2.3 `schemas.3B.yaml#/egress/virtual_validation_contract_3B` MUST define a table-shaped dataset with at least the following **required columns**:

* `test_id`

  * type: string;
  * unique per `fingerprint`;
  * stable identifier that the validation harness uses for reporting and gating.

* `test_type`

  * type: enum;
  * MUST be one of `{ "IP_COUNTRY_MIX", "SETTLEMENT_CUTOFF", "EDGE_USAGE_VS_WEIGHT", "ROUTING_RECEIPT" }` as defined in `schemas.3B.yaml`.

* `scope`

  * type: enum; `{ "GLOBAL", "PER_MERCHANT", "PER_CLASS", "PER_SCENARIO" }`.
  * defines aggregation level for the test.

* `target_population`

  * structured object with schema-owned fields:
    * `virtual_only` — boolean flag limiting scope to merchants marked virtual in S1;
    * `merchant_ids` — array of `id64` merchant identifiers (optional, for allow-lists);
    * `classes` — array of strings describing merchant classes or labels;
    * `notes` — optional free-text context.
  * No additional properties are permitted.

* `inputs`

  * structured object with strict members:

    * `datasets` — array (min 1) of objects `{ logical_id, role }` referencing dataset dictionary IDs / manifest keys and describing their use in the test;
    * `fields` — array of objects `{ schema_anchor, role }` that bind event-field anchors to semantic roles within the test;
    * `join_keys` — optional array of string field names used to join the referenced datasets.

* `thresholds`

  * structured object describing numerical tolerances:

    * `max_abs_error` — non-negative number;
    * `max_rel_error` — non-negative number;
    * `max_kl_divergence` — non-negative number;
    * extensions require schema updates (no ad-hoc keys).

* `severity`

  * enum; `{ "BLOCKING", "WARNING", "INFO" }`;
  * informs the validation harness whether a FAIL on this test should prevent a segment-level PASS.

5.2.4 The schema MAY also define optional columns, such as:

* `description` — human-readable description of the test;
* `profile` — string/enum to group tests into profiles (e.g. `"STRICT"`, `"RELAXED"`);
* `enabled` — boolean flag; if `false`, the test is defined but not active for this manifest;
* `labels` — free-form tags (e.g. `["latency","geo_mix"]`) for grouping in dashboards.

5.2.5 S4 MUST ensure that:

* each `test_id` relates to exactly one policy-defined test configuration;
* all `test_type` values come from the enumeration defined in the virtual validation policy schema;
* all `datasets` and `fields` references in `inputs` are valid (exist in schema/dictionary and are compatible with test logic);
* `thresholds` structures are syntactically valid and semantically meaningful (e.g. numeric values where required, sensible ranges).

---

5.3 **Optional S4 run-summary dataset - `s4_run_summary_3B`**

5.3.1 If the design includes an S4 run-summary, **`s4_run_summary_3B`** MUST be registered with:

* `id: s4_run_summary_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/validation/s4_run_summary_3B`
* `path: data/layer1/3B/s4_run_summary/manifest_fingerprint={manifest_fingerprint}/s4_run_summary_3B.json`
* `partitioning: ["fingerprint"]`
* `ordering: []`

5.3.2 `schemas.3B.yaml#/validation/s4_run_summary_3B` MUST define a JSON object with fields such as:

* `manifest_fingerprint`, `parameter_hash`;
* `status ∈ {"PASS","FAIL"}`;
* `error_code` (for FAIL);
* `virtual_merchant_count` (in scope for S4);
* `routing_policy_id` / `routing_policy_version`;
* `virtual_validation_policy_id` / `virtual_validation_policy_version`;
* counts of tests in `virtual_validation_contract_3B` by `severity` or `profile`;
* references (paths or manifest keys) to the main S4 outputs and upstream artefacts (S1–S3).

5.3.3 This dataset is optional and informative; its absence MUST NOT change the semantics of `virtual_routing_policy_3B` or `virtual_validation_contract_3B`.

---

5.4 **Input anchors & cross-segment references**

5.4.1 `schemas.3B.yaml` MUST reference upstream schemas via `$ref` in S4-related schemas where appropriate, including:

* `virtual_classification_3B` — via `schemas.3B.yaml#/plan/virtual_classification_3B`;
* `virtual_settlement_3B` — via `schemas.3B.yaml#/plan/virtual_settlement_3B`;
* `edge_catalogue_3B` — via `schemas.3B.yaml#/plan/edge_catalogue_3B`;
* `edge_alias_blob_3B` / `edge_alias_index_3B` — via S3 schemas;
* the virtual validation policy artefact — via `schemas.3B.yaml#/policy/virtual_validation_policy`;
* the routing/RNG policy — via the appropriate Layer-1 schema (e.g. `schemas.layer1.yaml#/rng/policy`);
* the event schema / routing-field contract — via its own schema anchor (likely in `schemas.layer1.yaml`).

5.4.2 `dataset_dictionary.layer1.3B.yaml` MUST mark S1–S3 outputs and relevant Layer-1 event datasets as **inputs** to S4, with:

* `schema_ref` anchors pointing to their owning segment schemas;
* optional `consumed_by` metadata listing `"3B.S4"`.

5.4.3 S4 MUST rely on these schema anchors for shapes and field names when constructing the `inputs` portions of `virtual_validation_contract_3B` and the field bindings in `virtual_routing_policy_3B`. It MUST NOT assume shapes not expressed in those schemas.

---

5.5 **Catalogue usage & discoverability**

5.5.1 All S4 outputs MUST be:

* discoverable via `dataset_dictionary.layer1.3B.yaml` (dataset ID → path template, partitioning, schema);
* described in `artefact_registry_3B.yaml` with explicit 3B ownership metadata, manifest keys and basic metadata (licence, retention, intended consumers).

5.5.2 The engine and downstream components (2B, validation harness) MUST:

* resolve `virtual_routing_policy_3B` and `virtual_validation_contract_3B` via the dictionary, not via hard-coded paths;
* respect partitioning (`manifest_fingerprint={manifest_fingerprint}`) and not infer additional partition keys or naming patterns.

5.5.3 Any new S4-owned dataset introduced in the future (e.g. additional policy layers, scenario-specific routing contracts) MUST:

* be added to `schemas.3B.yaml` with a clear `schema_ref`;
* be registered in the dictionary and registry;
* be explicitly documented in this state spec if it is binding for 2B or validation.

---

5.6 **Binding vs informative elements**

5.6.1 Binding in this section:

* Existence of `virtual_routing_policy_3B` and `virtual_validation_contract_3B` as S4 outputs.
* Their `schema_ref`, `path`, and `partitioning` in the dictionary.
* Required fields enumerated in §§5.1–5.2.
* Requirement that S4 outputs be discoverable via catalogues and referenced by downstream components.

5.6.2 Informative or optional elements:

* `s4_run_summary_3B` and any debug/diagnostic fields within S4 outputs, as long as they are schema-optional and do not change semantics of required fields.

5.6.3 If any discrepancy arises between this section and:

* `schemas.3B.yaml`,
* `dataset_dictionary.layer1.3B.yaml`, or
* `artefact_registry_3B.yaml`,

then **schemas and catalogues are authoritative**. This section MUST be updated in the next non-editorial revision to match the actual contracts in force, while maintaining the core guarantees that:

* routing behaviour for virtual flows is fully specified in `virtual_routing_policy_3B`;
* validation behaviour for virtual flows is fully specified in `virtual_validation_contract_3B`.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

6.1 **Phase overview**

6.1.1 S4 SHALL implement a single **deterministic, RNG-free** algorithm, composed of the following phases:

* **Phase A — Environment & input load (RNG-free)**
  Load and validate S0–S3 artefacts, schemas, dictionaries, registries and policy packs required by S4.

* **Phase B — Dual timezone semantics & merchant scope (RNG-free)**
  Derive, for each virtual merchant, the dual-timezone semantics (settlement vs operational) and the set of merchants in scope for virtual routing.

* **Phase C — Virtual routing policy compilation (RNG-free)**
  Assemble `virtual_routing_policy_3B` from S1–S3 artefacts, routing/RNG policy and event schema contracts.

* **Phase D — Virtual validation contract compilation (RNG-free)**
  Expand the virtual validation policy pack into concrete test rows for `virtual_validation_contract_3B`.

* **Phase E — Output validation & atomic publish (RNG-free)**
  Validate internal consistency of policy/contract artefacts and write them atomically to their canonical locations.

6.1.2 None of these phases MAY:

* open or advance any RNG stream;
* emit RNG events;
* depend on non-deterministic sources (wall-clock time, process ID, host name, unordered filesystem iteration) in a way that affects outputs.

6.1.3 All S4 outputs MUST be pure functions of:

* `{seed, parameter_hash, manifest_fingerprint}`;
* S0–S3 outputs and digests;
* sealed routing/RNG & validation policies;
* Layer-1 schemas/dictionaries/registries.

---

6.2 **Phase A — Environment & input load (RNG-free)**

6.2.1 S4 MUST perform the precondition checks defined in §§2–3, including:

1. Load `s0_gate_receipt_3B` and `sealed_inputs_3B` and validate them against their schemas.

2. Confirm identity alignment: `{seed, parameter_hash, manifest_fingerprint}` equals the values recorded in `s0_gate_receipt_3B`.

3. Confirm upstream gates for segments 1A, 1B, 2A, 3A are all `status="PASS"`.

4. Load or confirm a compatible triplet of 3B contracts:

   * `schemas.3B.yaml`
   * `dataset_dictionary.layer1.3B.yaml`
   * `artefact_registry_3B.yaml`

5. From `sealed_inputs_3B`, resolve and validate, at minimum:

   * the **virtual validation policy** artefact;
   * the **routing/RNG policy** artefact;
   * references (IDs, digests) to S2/S3 artefacts that will be echoed in S4 (e.g. `edge_universe_hash_3B` manifest key).

6.2.2 S4 MUST load and validate the following S1–S3 outputs for the `{seed, manifest_fingerprint}` in scope:

* `virtual_classification_3B`, `virtual_settlement_3B`;
* `edge_catalogue_3B`, `edge_catalogue_index_3B`;
* `edge_alias_blob_3B` (at least header-level) and `edge_alias_index_3B`;
* `edge_universe_hash_3B`.

6.2.3 If any required artefact cannot be resolved, opened, or validated, S4 MUST fail immediately with the appropriate `E3B_S4_*` error and MUST NOT proceed to generate policy/contract outputs.

---

6.3 **Phase B — Dual timezone semantics & merchant scope (RNG-free)**

6.3.1 From S1, S4 MUST derive the virtual merchant scope:

* let `V = { m | virtual_classification_3B(m).is_virtual = 1 }` (or equivalent field if an enum is used);
* S4 MUST treat `V` as the set of merchants for which virtual routing semantics MAY apply.

6.3.2 From S1/S2, S4 MUST derive **dual-timezone semantics** for each `m ∈ V`:

* `tzid_settlement(m)` from `virtual_settlement_3B` (S1);
* for each edge `e` belonging to `m` in `edge_catalogue_3B`:

  * `tzid_operational(e)` from S2;
  * `country_iso(e)`, `edge_latitude_deg(e)`, `edge_longitude_deg(e)`.

6.3.3 S4 MUST define, in policy terms, **which clock is used for which semantics**, at minimum:

* Settlement semantics (e.g. `settlement_day`, settlement cut-off) MUST be defined in terms of `tzid_settlement(m)`;
* Operational / apparent semantics (e.g. `ip_country`, `apparent_local_time`) MUST be defined in terms of `tzid_operational(e)` and `country_iso(e)` when a virtual edge is chosen.

6.3.4 S4 MUST NOT alter actual tzids or coordinates. It only derives **rules** such as:

* “Field `event.settlement_timezone` is bound to `tzid_settlement(m)`”;
* “Field `event.ip_country` is bound to `country_iso(e)`”;
* “Field `event.operational_timezone` is bound to `tzid_operational(e)`”.

These rules are encoded in `dual_timezone_semantics` and `geo_field_bindings` sections of `virtual_routing_policy_3B`.

6.3.5 If S4 detects:

* a virtual merchant `m ∈ V` without `tzid_settlement(m)` where required;
* or edges for `m` with missing or invalid `tzid_operational(e)`;

it MUST fail with a FATAL S1/S2-contract error and MUST NOT attempt to derive tzids itself.

---

6.4 **Phase C — Virtual routing policy compilation (RNG-free)**

6.4.1 S4 MUST initialise a `virtual_routing_policy_3B` object with identity and global contract fields:

* `manifest_fingerprint` and `parameter_hash`;
* `edge_universe_hash` from `edge_universe_hash_3B`;
* `routing_policy_id` / `routing_policy_version` from the routing/RNG policy;
* `virtual_validation_policy_id` / `virtual_validation_policy_version` from the validation policy.

6.4.2 S4 MUST populate **dual timezone semantics**:

* `dual_timezone_semantics.settlement_timezone_field` MUST reference the event field (by schema anchor) that carries settlement tz semantics;
* `dual_timezone_semantics.operational_timezone_field` MUST reference the field that carries operational tz semantics;
* `dual_timezone_semantics.settlement_day_definition` MUST encode, for validation/reference, how settlement-day boundaries are defined from `tzid_settlement` (e.g. using a Layer-1 contract anchor);
* if an operational-day concept exists, its definition MUST be similarly encoded.

6.4.3 S4 MUST populate **geo field bindings**:

* map event fields such as `ip_country`, `ip_latitude`, `ip_longitude` to “edge-derived” sources, referencing `edge_catalogue_3B` or its schema;
* if any event fields are still bound to physical sites for hybrid modes, those bindings MUST refer to the appropriate upstream segments.

6.4.4 S4 MUST populate **alias & RNG integration**:

* `alias_layout_version` from `edge_alias_blob_3B` header;
* `alias_blob_manifest_key` and `alias_index_manifest_key` from the 3B registry;
* `edge_universe_hash_manifest_key` referring to `edge_universe_hash_3B`;
* `virtual_edge_rng_binding` from the routing/RNG policy, specifying exactly which RNG stream/substream 2B MUST use for virtual edge picks (even though S4 does not open these streams).

6.4.5 If per-merchant routing modes are supported (e.g. virtual-only, hybrid, disabled):

* S4 MUST derive `merchant_overrides` from configuration/policy, using deterministic rules (no RNG);
* for each merchant in scope, S4 MUST record an explicit `mode` if required by the design;
* where no overrides exist, global defaults defined in routing policy MUST apply.

6.4.6 S4 MUST ensure that `virtual_routing_policy_3B`:

* references only artefacts that are sealed in `sealed_inputs_3B` or produced by S1–S3;
* contains no implicit or free-form rules that cannot be traced back to policies and upstream artefacts.

---

6.5 **Phase D — Virtual validation contract compilation (RNG-free)**

6.5.1 S4 MUST parse the **virtual validation policy** artefact into an internal representation of test definitions, including:

* test types (e.g. `"IP_COUNTRY_MIX"`, `"SETTLEMENT_CUTOFF"`, `"EDGE_USAGE_VS_WEIGHT"`);
* default thresholds and severities;
* scoping rules (per-merchant, per-class, global) and any explicit target populations.

6.5.2 For each configured test definition in the validation policy that is **enabled** for this manifest/profile, S4 MUST generate at least one row in `virtual_validation_contract_3B`, with:

* `test_id` — stable identifier derived from (manifest, test_type, scope, population) using a documented, deterministic naming convention (e.g. `"{test_type}:{scope}:{profile}:{hash_of_population}"` truncated to a safe length);
* `test_type` — from the policy;
* `scope` — as specified (GLOBAL / PER_MERCHANT / etc.);
* `target_population` — compiled expression describing the population in terms of S1/S2 fields or merchant groups;
* `inputs.datasets` — dataset IDs / manifest keys for arrivals, decisions, labels, and any other S2/S3/S1 artefacts used in the test;
* `inputs.fields` — event field anchors (e.g. `event.ip_country`, `event.settlement_day`) that must exist in the Layer-1 event schema;
* `thresholds` — numeric/logical thresholds pulled from policy, resolved for this manifest;
* `severity` — `"BLOCKING"`, `"WARNING"`, or `"INFO"` per policy.

6.5.3 Where the validation policy defines **profiles** (e.g. strict vs relaxed), S4 MUST:

* include a `profile` field if present;
* only materialise tests for the active profile(s) declared in configuration;
* mark any unselected tests as `enabled=false` or omit them entirely, according to schema and policy rules.

6.5.4 S4 MUST ensure that each test’s `inputs`:

* refer only to datasets and fields that are present in the manifest’s schemas/dictionaries;
* include join keys if multiple datasets are involved, using documented join semantics;
* do not rely on unspecified or ambiguous fields.

6.5.5 If S4 encounters a validation policy definition that cannot be compiled into a concrete test (e.g. references non-existent fields or datasets), it MUST:

* treat this as a policy/contract error;
* fail rather than emitting an incomplete or inconsistent test.

---

6.6 **Phase E — Output validation & atomic publish (RNG-free)**

6.6.1 Before publishing outputs, S4 MUST perform internal validation of its artefacts:

* **`virtual_routing_policy_3B`**:

  * validates against `schemas.3B.yaml#/egress/virtual_routing_policy_3B`;
  * `manifest_fingerprint` and `parameter_hash` (if present) match S0;
  * `edge_universe_hash` matches `edge_universe_hash_3B.edge_universe_hash`;
  * references to artefact manifest keys (alias blob/index, edge universe hash) correspond to real entries in the 3B registry.

* **`virtual_validation_contract_3B`**:

  * validates against `schemas.3B.yaml#/egress/virtual_validation_contract_3B`;
  * `test_id` is unique per fingerprint;
  * `test_type` values are drawn from the policy-defined enum;
  * referenced datasets/fields exist and are consistent with schemas/dictionaries.

6.6.2 S4 MUST then publish outputs using an **atomic publish** protocol per `manifest_fingerprint`:

1. Write `virtual_routing_policy_3B` to a temporary file under `manifest_fingerprint={manifest_fingerprint}`.
2. Write `virtual_validation_contract_3B` to a temporary directory or file set under the same fingerprint.
3. Validate both artefacts in place as per 6.6.1.
4. Move/rename temporary artefacts into their canonical paths in a way that does not expose partial state (e.g. directory-level rename or carefully ordered renames).

6.6.3 If any step in writing or validation fails (I/O error, schema violation, internal consistency error), S4 MUST:

* treat the run as FAIL;
* ensure that partially written artefacts are not visible at canonical locations;
* require a fresh S4 run once underlying issues are fixed.

6.6.4 On re-execution for the same identity triple with existing S4 outputs, S4 MUST:

* recompute candidate `virtual_routing_policy_3B` and `virtual_validation_contract_3B`;
* compare them to existing artefacts (e.g. via digest or byte comparison);
* if identical, treat the run as idempotent and do not overwrite;
* if different, fail with an “inconsistent rewrite” style error and MUST NOT overwrite existing artefacts.

---

6.7 **RNG & determinism guardrails**

6.7.1 S4 MUST NOT:

* call any RNG API or produce RNG events;
* introduce any behaviour that depends on environment state outside the sealed inputs (e.g. clock time, PID, hostname) for its outputs.

6.7.2 S4 MUST ensure that:

* given identical inputs (identity, S0–S3 artefacts, policies, schemas/dictionaries/registries), its outputs are **bit-identical** across re-runs;
* any discovered non-determinism (e.g. tests or policy sections being emitted in different orders due to unordered iteration) is treated as a bug and corrected by imposing canonical ordering before write.

6.7.3 Any implementation that violates these guardrails is non-conformant with this specification; corrective action MUST restore S4’s RNG-free, deterministic behaviour and idempotence guarantees.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

7.1 **Identity model for 3B.S4**

7.1.1 For S4, the **canonical run identity triple** is:

* `seed`
* `parameter_hash`
* `manifest_fingerprint`

These MUST match the values recorded in `s0_gate_receipt_3B` for the same manifest.

7.1.2 S4’s persisted outputs are **manifest-scoped**, not run/seed scoped in the default design:

* `virtual_routing_policy_3B` — scoped by `manifest_fingerprint` only.
* `virtual_validation_contract_3B` — scoped by `manifest_fingerprint` only.
* `s4_run_summary_3B` (if present) — scoped by `manifest_fingerprint` only.

7.1.3 `parameter_hash` is part of the logical identity of the manifest configuration, but:

* MUST NOT be used as a partition key for any S4 output;
* MAY appear inside S4 artefacts as an identity echo;
* MUST equal the value recorded in `s0_gate_receipt_3B` when present.

7.1.4 If `run_id` is used by the Layer-1 harness, it MAY:

* appear in logs and run-report entries for S4;
* appear as an informational field in `s4_run_summary_3B`,

but it MUST NOT:

* affect partitioning or path structure of S4 outputs;
* influence any routing or validation semantics encoded by S4;
* be used as an input to any digest or hash that is expected to be manifest-invariant.

---

7.2 **Partition law**

7.2.1 `virtual_routing_policy_3B` MUST be partitioned **exactly** by:

* `manifest_fingerprint={manifest_fingerprint}`

No additional partition keys (e.g. `seed`, `parameter_hash`, `run_id`) are allowed in its dataset `path`.

7.2.2 `virtual_validation_contract_3B` MUST be partitioned **exactly** by:

* `manifest_fingerprint={manifest_fingerprint}`

Again, no additional partition keys are allowed unless explicitly introduced via a future, versioned contract change.

7.2.3 If `s4_run_summary_3B` is produced, it MUST also be partitioned **exactly** by:

* `manifest_fingerprint={manifest_fingerprint}`

7.2.4 Any future change that introduces per-seed variants of these artefacts (e.g. per-seed routing policy) is a change in **partition law**, and MUST:

* be explicitly reflected in `dataset_dictionary.layer1.3B.yaml`;
* be treated as a breaking change for S4 contracts unless designed for backwards compatibility.

---

7.3 **Ordering & writer sort**

7.3.1 `virtual_routing_policy_3B` is a single JSON document per fingerprint and has no row-level sort semantics. Its ordering constraints apply to:

* the **internal representation** of structured fields, where S4 MUST ensure deterministic ordering when:

  * emitting lists (e.g. `merchant_overrides` sorted by `merchant_id` if present);
  * emitting maps/dictionaries (either rely on a canonical JSON encoder, or emit keys in a defined order).

7.3.2 `virtual_validation_contract_3B` is table-shaped and MUST honour its declared `ordering`:

* `ordering: ["test_id"]` (or an explicitly declared alternative in the dictionary).
* Before writing, S4 MUST sort all rows by `test_id` ascending.
* If global/special tests require different ordering, they MUST either follow the same sort or be distinguished via explicit schema fields (e.g. `scope`) — not via ad-hoc row ordering.

7.3.3 S4 MUST NOT rely on non-deterministic iteration for ordering:

* no dependence on hash-map iteration order;
* no dependence on filesystem listing order;
* all lists and tables MUST be sorted according to rules described in this spec and/or the declared `ordering`.

7.3.4 Any digest or hash that S4 or downstream validation computes over S4 outputs (e.g. for run-report comparisons) MUST be based on:

* a well-defined byte representation (e.g. canonical JSON or sorted Parquet rows);
* the ordering rules above, not incidental side-effects of serialization libraries.

---

7.4 **Join & reference discipline**

7.4.1 S4 outputs are **control-plane contracts**, not data-plane tables, but they still reference other artefacts via keys:

* `virtual_routing_policy_3B` MUST reference S1–S3 artefacts and Layer-1 datasets only by:

  * dataset IDs or manifest keys defined in dictionaries/registries;
  * schema anchors defined in schemas (for event fields).

* `virtual_validation_contract_3B.inputs.datasets` MUST reference dataset IDs / manifest keys which are valid;

* `virtual_validation_contract_3B.inputs.fields` MUST reference event-schema anchors which exist.

7.4.2 S4 and downstream consumers MUST:

* treat these references as **foreign keys** into the manifest’s catalogue;
* not invent hidden or implicit joins (e.g. relying on string conventions rather than explicit field references).

7.4.3 Any test or routing rule that refers to:

* a dataset not declared in the dictionaries;
* a field not declared in the schemas;

MUST be treated as an S4 contract error and MUST not be silently ignored or “best-effort” interpreted by downstream components.

---

7.5 **Immutability, idempotence & merge discipline**

7.5.1 For a given `{seed, parameter_hash, manifest_fingerprint}`, S4 outputs are **logically immutable**:

* Once S4 reports PASS and publishes `virtual_routing_policy_3B` and `virtual_validation_contract_3B` for a fingerprint, they define the only valid routing/validation semantics for that manifest under the current S4 contract version.

7.5.2 On re-execution of S4 for the same identity triple:

* S4 MUST recompute candidate outputs based on current S0–S3 artefacts and policies;

* S4 MUST compare the recomputed artefacts against existing ones (by bytes or canonical digest);

* If they are identical, S4 MAY:

  * treat the run as idempotent;
  * return PASS without rewriting.

* If they differ, S4 MUST:

  * treat this as an environment/manifest inconsistency (`E3B_S4_OUTPUT_INCONSISTENT_REWRITE` or equivalent);
  * FAIL;
  * MUST NOT overwrite existing artefacts.

7.5.3 S4 MUST publish its outputs **atomically** per `manifest_fingerprint`:

* It MUST NOT expose a state where `virtual_routing_policy_3B` exists but `virtual_validation_contract_3B` does not (or vice versa) for the same fingerprint;
* It MUST NOT expose a state where either dataset is partially written or schema-invalid at its canonical path.

7.5.4 Downstream components (2B, validation harness) MUST treat any partial or mismatched presence of S4 outputs (e.g. only one of the two datasets present, or identity echoes not matching path) as a **S4 failure**, not as a valid configuration.

---

7.6 **Multi-manifest behaviour**

7.6.1 S4 MUST treat each `manifest_fingerprint` as an independent semantic universe:

* S4 does not impose requirements on how routing/validation semantics relate across different manifests;
* Cross-manifest comparisons (e.g. checking for drift) are out of scope for S4 and belong to higher-level tooling.

7.6.2 If the engine runs multiple `seed` values under the same `manifest_fingerprint`, S4’s outputs are **shared** across seeds (by default) unless future contracts explicitly define per-seed routing/validation; in that case:

* this change MUST be reflected in partition law (see 7.2);
* S4 MUST ensure per-seed outputs are still deterministic and discoverable.

---

7.7 **Non-conformance and correction**

7.7.1 Any implementation that:

* deviates from the partition law in §7.2;
* writes `virtual_validation_contract_3B` unsorted with respect to `ordering`;
* mutates S4 outputs in place without idempotent comparison;
* exposes partial, inconsistent, or identity-mismatched S4 outputs at canonical paths,

is **non-conformant** with this specification.

7.7.2 Such behaviour MUST be treated as a bug in the engine/spec translation. Corrective action MUST:

* restore the partitioning, key and ordering discipline described above;
* re-establish immutability and idempotence guarantees for S4 outputs;
* ensure downstream components can safely assume that, for any given manifest, S4’s contracts are stable, complete, and fully determined by S0–S3 and sealed policies.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

8.1 **S4 state-level PASS criteria**

8.1.1 A run of 3B.S4 for a given
`{seed, parameter_hash, manifest_fingerprint}`
SHALL be considered **PASS** if and only if **all** of the following conditions hold.

**Identity & S0 gate**

a. `s0_gate_receipt_3B` and `sealed_inputs_3B` exist for `manifest_fingerprint` and validate against their schemas.
b. `segment_id = "3B"` and `state_id = "S0"` in `s0_gate_receipt_3B`.
c. The S4 runtime `{seed, parameter_hash, manifest_fingerprint}` exactly matches identity values in `s0_gate_receipt_3B`.
d. `upstream_gates.segment_1A/1B/2A/3A.status = "PASS"`.

**Contracts & sealed artefacts**

e. `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` form a compatible triplet for S4 (per 3B versioning rules).
f. The following artefacts are present in `sealed_inputs_3B`, readable and schema-valid:

* virtual validation policy;
* routing/RNG policy used for alias decode and virtual routing;
* any event-schema/routing-field contract that S4 references.
  g. Any policy digests that S4 must echo (e.g. `routing_policy_id/version`, `virtual_validation_policy_id/version`) are consistent with the artefacts S4 actually reads.

**S1–S3 inputs**

h. S1 outputs for `{seed, fingerprint}` exist and validate:

* `virtual_classification_3B`;
* `virtual_settlement_3B`.

i. S2 outputs for `{seed, fingerprint}` exist and validate:

* `edge_catalogue_3B`;
* `edge_catalogue_index_3B`.

j. S3 outputs exist and validate:

* `edge_alias_blob_3B` header fields;
* `edge_alias_index_3B`;
* `edge_universe_hash_3B`.

k. S1–S3 invariants S4 depends on hold, at minimum:

* virtual merchant set `V` from `virtual_classification_3B` is coherent with `virtual_settlement_3B` (exactly one settlement node per virtual merchant where required);
* every merchant with edges in `edge_catalogue_3B` is either:

  * virtual (in `V`), or
  * explicitly allowed by configuration/policy in a documented “no-edge-virtual” / hybrid mode;
* `edge_catalogue_index_3B` and `edge_alias_index_3B` counts are consistent with `edge_catalogue_3B`;
* `edge_universe_hash_3B` is internally consistent (component digests recompute correctly).

**Dual-timezone & field-binding semantics**

l. S4 successfully derives dual-timezone semantics for all virtual merchants `m ∈ V` that are in scope for routing:

* `tzid_settlement(m)` present and valid in `virtual_settlement_3B`;
* all edges `e` for those merchants have valid `tzid_operational(e)` and `country_iso(e)` in `edge_catalogue_3B`.

m. `virtual_routing_policy_3B.dual_timezone_semantics` is populated and consistent with S1/S2:

* settlement-related fields are bound to S1’s `tzid_settlement`;
* operational-related fields (IP geo, local time) are bound to S2’s `tzid_operational` and `country_iso`;
* references use valid event-schema anchors.

**Routing & alias integration semantics**

n. `virtual_routing_policy_3B`:

* validates against `schemas.3B.yaml#/egress/virtual_routing_policy_3B`;
* carries `manifest_fingerprint` and (if present) `parameter_hash` matching S0;
* carries `edge_universe_hash` equal to `edge_universe_hash_3B.edge_universe_hash`;
* references `edge_alias_blob_3B`, `edge_alias_index_3B` and `edge_universe_hash_3B` via valid manifest keys;
* includes a `virtual_edge_rng_binding` that references a valid stream/substream in the routing/RNG policy (for 2B to use), even though S4 itself remains RNG-free.

o. Any per-merchant routing modes (if supported) in `virtual_routing_policy_3B` are:

* derived deterministically from configuration/policy;
* consistent with S1/S2 (no merchants in a “virtual-only” mode without S2 edges, unless explicitly allowed and documented);
* free of contradictions (e.g. no merchant simultaneously marked “virtual-only” and “virtual-disabled”).

**Validation contract semantics**

p. `virtual_validation_contract_3B`:

* exists for `manifest_fingerprint={manifest_fingerprint}`;
* validates against `schemas.3B.yaml#/egress/virtual_validation_contract_3B`;
* has unique `test_id` values across all rows.

q. For each row in `virtual_validation_contract_3B`:

* `test_type` is a known type from the virtual validation policy;
* `scope` is valid and consistent with `test_type`;
* `target_population` is well-formed (refers only to valid S1 fields / merchant classes where used);
* `inputs.datasets` refers only to datasets that exist in the manifest;
* `inputs.fields` refer only to event-schema field anchors that exist;
* `thresholds` are syntactically valid and within the domains expected by the policy;
* `severity` is a valid enum, consistent with the policy definition.

r. All tests that the active profile(s) require (e.g. `"STRICT"` profile) are present; any tests omitted or marked `enabled=false` are consistent with policy configuration for this manifest.

**RNG-free guarantee**

s. S4 has emitted **no RNG events** and advanced **no RNG streams**:

* there are no S4 entries in layer RNG logs;
* S4’s implementation contains no calls to RNG APIs.

8.1.2 If **any** of the criteria in 8.1.1 fail, S4 MUST be considered **FAIL** for that `{seed, parameter_hash, manifest_fingerprint}`. S4 MUST NOT publish `virtual_routing_policy_3B` or `virtual_validation_contract_3B` as valid canonical outputs; any partially written artefacts MUST be treated as invalid and MUST NOT be used by downstream components.

---

8.2 **Gating obligations for 2B (virtual routing)**

8.2.1 For a given `manifest_fingerprint`, 2B’s virtual routing implementation MUST, before routing any virtual traffic:

* resolve `virtual_routing_policy_3B` from the dictionary;
* validate it against its schema;
* verify that:

  * the referenced `edge_universe_hash` matches the `edge_universe_hash_3B` descriptor;
  * the alias layout version and manifest keys it references correspond to alias artefacts S3 produced.

8.2.2 When routing events for virtual merchants:

* 2B MUST honour the **dual-timezone semantics** encoded by S4 (e.g. using `tzid_settlement` for settlement-day/cut-off, and `tzid_operational` for apparent local time / IP geo);
* 2B MUST populate event fields that S4 bound to S1/S2 artefacts exactly as described in `virtual_routing_policy_3B.geo_field_bindings` and related sections;
* 2B MUST use the RNG stream(s)/substreams specified in `virtual_routing_policy_3B.virtual_edge_rng_binding` when sampling alias tables for virtual edges.

8.2.3 2B MUST NOT:

* introduce ad-hoc routing logic for virtual merchants that contradicts S4 (e.g. using physical sites instead of edges where S4 says “virtual-only”);
* bypass alias tables and directly use edge weights where S4 declares alias as the agreed representation for this manifest;
* use alias or edge artefacts whose digests do not match those in `edge_universe_hash_3B` / `virtual_routing_policy_3B`.

8.2.4 If 2B detects that:

* `virtual_routing_policy_3B` is missing or invalid;
* `edge_universe_hash` in routing policy does not match the current alias/edge artefacts;

2B MUST treat this as a **configuration/contract failure** for the manifest and MUST:

* fail or refuse to route virtual traffic;
* not silently fallback to a different, undeclared behaviour.

---

8.3 **Gating obligations for validation harness (3B validation / 4A–4B)**

8.3.1 The 3B validation state and any higher-level validation harness MUST treat `virtual_validation_contract_3B` as the **binding list of virtual tests** for this manifest.

8.3.2 For each row in `virtual_validation_contract_3B`, the validation harness MUST:

* treat `test_id` as a stable identifier for reporting and gating;
* interpret `severity` and thresholds according to the policy (e.g. FAIL on a `BLOCKING` test must prevent segment-level PASS);
* apply the test on the scope and inputs specified (`scope`, `target_population`, `inputs.datasets`, `inputs.fields`).

8.3.3 The validation harness MUST NOT:

* invent additional blocking tests outside `virtual_validation_contract_3B` for virtual flows;
* ignore or skip tests present in `virtual_validation_contract_3B` when computing segment-level PASS, unless a test row is explicitly marked `enabled=false`.

8.3.4 Any validation-report UI or audit MUST be able to trace each virtual-related PASS/WARN/FAIL back to a `test_id` in `virtual_validation_contract_3B`, including:

* the test type;
* the population tested;
* the thresholds used.

---

8.4 **Interaction with S0–S3 gating and segment-level PASS**

8.4.1 S4 acceptance is strictly downstream of S0–S3 acceptance:

* If S0 or S1–S3 mandatory invariants fail, S4 MUST fail and MUST NOT produce outputs.
* The 3B validation state MUST treat an S4 failure as a **segment-level failure** until S4 is successfully rerun.

8.4.2 For a manifest to be eligible for a 3B segment-level PASS, all of the following MUST hold:

* S0–S3 have satisfied their own acceptance criteria;
* S4 has satisfied all acceptance criteria in 8.1 and its outputs are in place;
* 2B has honoured S4’s routing policy when generating arrivals for virtual merchants (enforced via cross-checks in the validation state);
* The validation harness has executed tests in `virtual_validation_contract_3B` and applied their severities appropriately.

8.4.3 If, during validation, the harness discovers that 2B **did not** follow S4’s routing policy (e.g. event fields do not match the declared bindings), this MUST be treated as:

* a violation of the S4/2B contract;
* a failure for that manifest run;
* a reason to revisit S4 specs and 2B implementation.

---

8.5 **Failure semantics & propagation**

8.5.1 Any violation of the binding requirements in §§8.1–8.4 MUST result in:

* S4 returning **FAIL** for that `{seed, parameter_hash, manifest_fingerprint}`;
* no S4 outputs being considered valid for routing or validation (partial artefacts MUST be rejected);
* an appropriate `E3B_S4_*` error being logged with enough context to diagnose (e.g. missing test types, invalid bindings, upstream contract issues).

8.5.2 The run harness MUST:

* prevent 2B from running virtual routing for a manifest where S4 has failed (or where S4 hasn’t run);
* prevent the 3B validation state from emitting `_passed.flag` for that manifest;
* surface S4 failures in global run reports as **“3B.S4 routing/validation contract failure”**.

8.5.3 If downstream components (2B or validation harness) detect latent S4 contract issues **after** S4 reported PASS (for example, because S4 implementation had a bug):

* they MUST treat S4 outputs as invalid;
* they MUST not attempt to “fix” contracts on the fly;
* they MUST require corrected S4 outputs (and likely a new manifest or re-run) before considering the manifest healthy.

In all cases, **fully specified routing semantics plus a fully specified validation contract, aligned with S0–S3 artefacts and sealed policies**, are the binding conditions under which S4 can be said to have “passed” for a given run.

---

## 9. Failure modes & canonical error codes *(Binding)*

9.1 **Error model & severity**

9.1.1 3B.S4 SHALL use a **state-local error namespace** of the form:

> `E3B_S4_<CATEGORY>_<DETAIL>`

All codes in this section are reserved for S4 and MUST NOT be reused by other states.

9.1.2 Every surfaced S4 failure MUST carry, at minimum:

* `segment_id = "3B"`
* `state_id = "S4"`
* `error_code`
* `severity ∈ {"FATAL","WARN"}`
* `manifest_fingerprint`
* optional `{seed, parameter_hash}`
* a human-readable `message` (non-normative)

9.1.3 Unless explicitly marked as `WARN`, all codes below are **FATAL** for S4:

* **FATAL** ⇒ S4 MUST NOT publish `virtual_routing_policy_3B` or `virtual_validation_contract_3B` as valid canonical outputs for that `manifest_fingerprint`. The manifest MUST be treated as **not having a virtual routing / validation contract**.
* **WARN** ⇒ S4 MAY complete and publish outputs, but the condition MUST be visible in logs / run-report and SHOULD be surfaced via metrics.

---

### 9.2 Identity & gating failures

9.2.1 **E3B_S4_IDENTITY_MISMATCH** *(FATAL)*
Raised when S4’s view of identity is inconsistent with S0:

* `seed`, `parameter_hash`, or `manifest_fingerprint` passed into S4 differ from those embedded in `s0_gate_receipt_3B`; or
* `s0_gate_receipt_3B` contains self-inconsistent identity fields.

Typical triggers:

* 3B.S0 and 3B.S4 invoked with different identity triples.
* Manual tampering with S0 outputs.

Remediation:

* Fix run harness so S0 and S4 share the same identity triple.
* Regenerate S0 artefacts if they were modified.

---

9.2.2 **E3B_S4_GATE_MISSING_OR_INVALID** *(FATAL)*
Raised when S4 cannot use S0 outputs as a valid gate:

* `s0_gate_receipt_3B` or `sealed_inputs_3B` is missing; or
* either artefact fails schema validation.

Typical triggers:

* S4 invoked before S0 has run or succeeded.
* Schema drift or corruption of S0 artefacts.

Remediation:

* Run/fix 3B.S0 for the manifest;
* restore or regenerate missing/invalid artefacts.

---

9.2.3 **E3B_S4_UPSTREAM_GATE_BLOCKED** *(FATAL)*
Raised when `s0_gate_receipt_3B.upstream_gates` indicates that any of 1A, 1B, 2A or 3A has `status ≠ "PASS"`.

Typical triggers:

* one or more upstream segments failed validation or did not run for this manifest.

Remediation:

* Diagnose and repair the failing upstream segment(s);
* rerun their validations, then S0–S3 before S4.

---

9.2.4 **E3B_S4_S1S2S3_CONTRACT_VIOLATION** *(FATAL)*
Raised when S1/S2/S3 outputs do not satisfy their contracts from S4’s perspective, e.g.:

* Missing or schema-invalid:

  * `virtual_classification_3B`, `virtual_settlement_3B`,
  * `edge_catalogue_3B`, `edge_catalogue_index_3B`,
  * `edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`.
* Virtual merchant appears in `V` but has no settlement row where S1 requires one.
* Merchant has edges in `edge_catalogue_3B` but no alias entry in `edge_alias_index_3B` in a mode where this is not allowed.
* `edge_universe_hash_3B` is internally inconsistent (component digests don’t match artefacts).

Typical triggers:

* Incomplete S1–S3 runs.
* Manual modification or partial deletion of S1–S3 artefacts.

Remediation:

* Fix/rerun S1–S3 until their invariants hold;
* rerun S4.

---

### 9.3 Contract & sealed-input failures

9.3.1 **E3B_S4_SCHEMA_PACK_MISMATCH** *(FATAL)*
Raised when `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` are not compatible for S4:

* missing or wrong `schema_ref` for S4 outputs;
* S4 dataset IDs absent from dictionary or registry;
* MAJOR version mismatch across contracts.

Typical triggers:

* partial deployment of updated 3B contracts;
* editing dictionary/registry without updating schema.

Remediation:

* Align schema, dictionary and registry versions;
* deploy a coherent contract set;
* rerun S0–S4.

---

9.3.2 **E3B_S4_REQUIRED_INPUT_NOT_SEALED** *(FATAL)*
Raised when one or more essential S4 input artefacts are not present in `sealed_inputs_3B`, e.g.:

* virtual validation policy artefact;
* routing/RNG policy artefact that defines 2B’s streams & alias compatibility;
* event-schema/routing-field contract used by S4.

Typical triggers:

* new required policy present but not yet sealed in S0;
* inconsistent catalogue vs S0 sealing logic.

Remediation:

* Register artefacts in dictionary/registry;
* update S0 to seal them;
* rerun S0–S4.

---

9.3.3 **E3B_S4_INPUT_OPEN_FAILED** *(FATAL)*
Raised when S4 resolves a required policy or contract from `sealed_inputs_3B` but cannot open it for reading.

Typical triggers:

* `path` in `sealed_inputs_3B` is stale/wrong;
* missing file/object;
* permissions or storage endpoint misconfigured.

Remediation:

* Fix storage/permissions/network;
* ensure sealed paths match reality;
* rerun S0 (if paths changed) and S4.

---

9.3.4 **E3B_S4_INPUT_SCHEMA_MISMATCH** *(FATAL)*
Raised when a sealed policy/contract S4 depends on does not conform to its declared `schema_ref`, e.g.:

* virtual validation policy missing required fields for test definitions;
* routing/RNG policy lacking required fields for alias layout compatibility;
* event-schema/routing-field contract missing required field anchors.

Typical triggers:

* schema updated without matching changes to policy files;
* incorrect `schema_ref` in the dictionary.

Remediation:

* Correct the policy / contract contents or fix the schema_ref;
* redeploy;
* reseal via S0 and rerun S4.

---

### 9.4 Dual-timezone & routing semantics failures

9.4.1 **E3B_S4_DUAL_TZ_INCOMPLETE** *(FATAL)*
Raised when S4 cannot establish complete dual-timezone semantics for virtual merchants:

* a virtual merchant `m ∈ V` lacks `tzid_settlement(m)` in `virtual_settlement_3B` where required;
* or some edge(s) for a merchant have missing/invalid `tzid_operational(e)` or `country_iso(e)`.

Typical triggers:

* incomplete S1 (missing settlement tzid) or S2 (missing operational tzid);
* schema-breaking changes upstream.

Remediation:

* correct S1/S2 outputs;
* ensure all virtual merchants in scope have valid `tzid_settlement` and corresponding edges with valid `tzid_operational` / `country_iso`.

---

9.4.2 **E3B_S4_FIELD_BINDING_INVALID** *(FATAL)*
Raised when S4 attempts to bind routing semantics to event fields that don’t exist or don’t match type expectations:

* `dual_timezone_semantics.*_field` refers to a non-existent event-schema anchor;
* `geo_field_bindings` refers to fields that aren’t present or have incompatible types (e.g. binding a string field to a numeric coordinate).

Typical triggers:

* event-schema changes not reflected in S4 contracts or validation;
* typos or outdated field names in policy templates.

Remediation:

* update S4 spec and/or validation policy to use correct schema anchors;
* ensure contracts and event schemas are aligned;
* rerun S4.

---

9.4.3 **E3B_S4_ROUTING_MODE_CONFLICT** *(FATAL)*
Raised when S4’s routing semantics are internally contradictory or inconsistent with upstream:

* the same merchant appears both in a “virtual-only” and “virtual-disabled” mode;
* hybrid routing configuration for a merchant contradicts upstream classification/edges (e.g. “virtual-only” but no edges; “hybrid” but no physical sites).

Typical triggers:

* conflicting per-merchant overrides in routing policy;
* misconfigured feature flags.

Remediation:

* fix routing policy / configuration;
* ensure per-merchant modes are coherent with S1/S2;
* rerun S4.

---

### 9.5 Validation-contract failures

9.5.1 **E3B_S4_VALIDATION_POLICY_INVALID** *(FATAL)*
Raised when the virtual validation policy artefact:

* fails schema validation;
* lacks required definitions for declared test types;
* refers to undefined profiles.

Typical triggers:

* malformed YAML/JSON;
* policy edited without schema updates.

Remediation:

* correct the validation policy to conform to schema;
* reseal via S0;
* rerun S4.

---

9.5.2 **E3B_S4_TEST_BINDING_INVALID** *(FATAL)*
Raised when S4 cannot bind a policy-defined test to concrete datasets/fields:

* `inputs.datasets` references dataset IDs or manifest keys that do not exist;
* `inputs.fields` reference event-schema anchors that do not exist or are not compatible with the test type;
* required join keys between datasets are missing.

Typical triggers:

* test definitions out of sync with Layer-1 event schema or dataset dictionary;
* new tests added in policy without updating schemas/dictionaries.

Remediation:

* update policy or schemas/dictionaries to align;
* or disable the offending tests in policy;
* rerun S4.

---

9.5.3 **E3B_S4_TEST_THRESHOLD_INVALID** *(FATAL)*
Raised when the `thresholds` structure for a test is syntactically or semantically invalid:

* required numeric fields are missing or non-numeric;
* thresholds are logically impossible (e.g. `max_KL_divergence < 0`, `min > max`).

Typical triggers:

* misconfigured validation policy;
* incorrectly constructed thresholds in S4.

Remediation:

* fix thresholds in policy or S4 logic;
* ensure test configs are meaningful and consistent.

---

9.5.4 **E3B_S4_TEST_ID_DUPLICATE** *(FATAL)*
Raised when `virtual_validation_contract_3B` contains duplicate `test_id` values for the same `manifest_fingerprint`.

Typical triggers:

* non-deterministic or poorly designed `test_id` construction;
* multiple policy definitions mapping to the same `test_id`.

Remediation:

* adjust `test_id` naming scheme to be globally unique per manifest;
* fix policy definitions to avoid collisions;
* rerun S4.

---

### 9.6 Output structure & idempotence failures

9.6.1 **E3B_S4_ROUTING_POLICY_SCHEMA_VIOLATION** *(FATAL)*
Raised when `virtual_routing_policy_3B` fails validation against `schemas.3B.yaml#/egress/virtual_routing_policy_3B`:

* missing required fields (identity, dual-tz, alias/RNG bindings, etc.);
* wrong types;
* invalid enum values.

Typical triggers:

* implementation bug in S4 policy assembly;
* schema updated without adjusting S4.

Remediation:

* fix S4 assembly logic;
* or adjust schema with proper versioning if behaviour is intended to change.

---

9.6.2 **E3B_S4_VALIDATION_CONTRACT_SCHEMA_VIOLATION** *(FATAL)*
Raised when `virtual_validation_contract_3B` fails schema validation:

* missing required columns (`test_id`, `test_type`, `scope`, `inputs`, `thresholds`, `severity`);
* wrong partitioning or unsorted rows (violating declared `ordering`);
* invalid field types.

Typical triggers:

* bug in S4 test compilation;
* schema mismatch.

Remediation:

* fix S4 compilation;
* or update schema/dictionary as part of a versioned change.

---

9.6.3 **E3B_S4_OUTPUT_WRITE_FAILED** *(FATAL)*
Raised when S4 cannot complete atomic writes of `virtual_routing_policy_3B` and/or `virtual_validation_contract_3B`.

Typical triggers:

* I/O failures;
* permissions errors;
* disk-space or storage-quota issues.

Remediation:

* correct underlying storage issues;
* rerun S4;
* ensure atomic write patterns are used.

---

9.6.4 **E3B_S4_OUTPUT_INCONSISTENT_REWRITE** *(FATAL)*
Raised when S4 detects that existing outputs for a given `manifest_fingerprint` differ from newly recomputed outputs under the same inputs:

* routing policy JSON differs;
* validation contract table differs.

Typical triggers:

* environment or policies changed without changing `manifest_fingerprint` / `parameter_hash`;
* manual editing of S4 outputs.

Remediation:

* treat as environment/manifest inconsistency;
* either restore original environment or compute a new manifest/parameter set and rerun S0–S4.

---

### 9.7 RNG & determinism failures

9.7.1 **E3B_S4_RNG_USED** *(FATAL)*
Raised if any RNG usage is observed under S4, for example:

* RNG events with `state_id = "S4"` recorded in layer RNG logs;
* internal instrumentation confirms RNG API calls in S4 code paths.

Typical triggers:

* accidental introduction of RNG-based helper calls;
* copy-paste from S2-style code that uses RNG.

Remediation:

* remove all RNG usage from S4;
* add regression tests to detect RNG events for S4.

---

9.7.2 **E3B_S4_NONDETERMINISTIC_OUTPUT** *(FATAL)*
Raised when S4 outputs differ across re-runs with identical inputs:

* `virtual_routing_policy_3B` differs byte-for-byte;
* `virtual_validation_contract_3B` rows differ or appear in different order;
* identity or digests change without any change in inputs.

Typical triggers:

* reliance on non-deterministic iteration (map/dict order, filesystem listing order);
* hidden state affecting S4 logic across runs.

Remediation:

* enforce canonical ordering for all lists and tables before writing;
* remove environment-dependent logic;
* verify idempotence via regression tests.

---

9.8 **Error propagation & downstream behaviour**

9.8.1 On any FATAL S4 error, S4 MUST:

* log a structured error event with fields in §9.1.2;
* ensure that no partial S4 artefacts are treated as canonical (using atomic publish or explicit cleanup);
* report FAIL to the run harness for the manifest.

9.8.2 The run harness MUST:

* prevent 2B’s virtual routing from using S4 contracts for a failed manifest;
* prevent the 3B validation state from emitting `_passed.flag` for that manifest;
* surface S4 failures as **“3B.S4 routing/validation contract failure”** in global run reports.

9.8.3 Downstream components (2B routing, validation harness) that detect S4-related inconsistencies at consumption time SHOULD:

* re-use the most appropriate `E3B_S4_*` error code;
* set their own `state_id` (e.g. `"2B"` or `"3B_validation"`) to indicate where the error was detected.

9.8.4 Any new S4 failure conditions introduced in future versions MUST:

* be given unique `E3B_S4_...` codes;
* be documented here with severity, typical triggers and remediation;
* NOT overload existing error codes with incompatible semantics.

---

## 10. Observability & run-report integration *(Binding)*

10.1 **Structured logging requirements**

10.1.1 S4 MUST emit at least the following **lifecycle log events** per attempted run:

* a **`start`** event when S4 begins work for a given `{seed, parameter_hash, manifest_fingerprint}`, and
* a **`finish`** event when S4 either completes successfully or fails.

10.1.2 Both `start` and `finish` events MUST be structured and include at least:

* `segment_id = "3B"`
* `state_id = "S4"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `event_type ∈ {"start","finish"}`
* `ts_utc` — UTC timestamp for the log event

10.1.3 The `finish` event MUST additionally include:

* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL; `null` or omitted for PASS)
* `routing_policy_written` — boolean flag; true iff `virtual_routing_policy_3B` was successfully written and validated
* `validation_contract_written` — boolean flag; true iff `virtual_validation_contract_3B` was successfully written and validated
* `virtual_merchant_count` — number of merchants in S1’s virtual set `V`
* `routing_scope_virtual_merchant_count` — number of virtual merchants for which S4 has compiled routing semantics (may equal `virtual_merchant_count` or be less in documented modes)
* `validation_test_count` — number of rows in `virtual_validation_contract_3B`

10.1.4 For every FATAL error, S4 MUST emit at least one **error log event** that includes:

* all fields in 10.1.2,
* `error_code` from the `E3B_S4_*` namespace,
* `severity = "FATAL"`,
* and sufficient diagnostic context, for example:

  * for contract failures: `logical_id`, `path`, `schema_ref` of the offending policy/artefact;
  * for dual-TZ/field-binding failures: `merchant_id` and the offending field anchor(s);
* for test-binding failures: `candidate_test_type`, dataset dictionary `id`, and `field_anchor` that caused the failure.

10.1.5 WARN-level conditions (if any) MUST:

* have `severity = "WARN"` and an appropriate `E3B_S4_*` code;
* never be used to mask conditions that this spec classifies as FATAL.

---

10.2 **Run-report record for 3B.S4**

10.2.1 S4 MUST produce a **run-report record** per `{seed, manifest_fingerprint}` that can be consumed by the Layer-1 run-report / 4A–4B harness. This record MAY be a dedicated dataset or in-memory structure but MUST contain at least:

* `segment_id = "3B"`
* `state_id = "S4"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL; `null` or omitted for PASS)
* `virtual_merchant_count`
* `routing_scope_virtual_merchant_count`
* `validation_test_count`
* `routing_policy_id` / `routing_policy_version`
* `virtual_validation_policy_id` / `virtual_validation_policy_version`
* `edge_universe_hash` (copied from `edge_universe_hash_3B`)
* Paths or manifest keys for:

  * `s0_gate_receipt_3B`
  * `sealed_inputs_3B`
  * `virtual_classification_3B` / `virtual_settlement_3B`
  * `edge_catalogue_3B` / `edge_catalogue_index_3B`
  * `edge_alias_blob_3B` / `edge_alias_index_3B`
  * `edge_universe_hash_3B`
  * `virtual_routing_policy_3B`
  * `virtual_validation_contract_3B`

10.2.2 Where available, the run-report record SHOULD also include:

* counts of tests by `severity` (e.g. number of `BLOCKING` vs `WARNING` tests);
* test-profile information (e.g. `"STRICT"` vs `"RELAXED"`) if the policy differentiates profiles;
* any feature-flag status that impacts routing/validation semantics (e.g. `enable_virtual_routing`, selected validation profile).

10.2.3 The run-report harness MUST be able to determine from S4’s record alone:

* whether S4 has **successfully** produced binding routing and validation contracts for this manifest;
* where to locate those contracts;
* whether there are obvious coverage anomalies (e.g. `routing_scope_virtual_merchant_count < virtual_merchant_count` in a configuration that expects all virtual merchants to be routed via virtual path).

---

10.3 **Metrics & counters**

10.3.1 S4 MUST emit the following **metrics** (names illustrative; concrete metric names may vary provided semantics are preserved):

* `3b_s4_runs_total{status="PASS|FAIL"}` — counter; incremented once per S4 run.
* `3b_s4_virtual_merchants` — gauge/histogram; value = `virtual_merchant_count`.
* `3b_s4_routing_scope_virtual_merchants` — gauge/histogram; value = `routing_scope_virtual_merchant_count`.
* `3b_s4_validation_test_count` — gauge/histogram; value = number of tests in `virtual_validation_contract_3B`.
* `3b_s4_tests_by_severity{severity="BLOCKING|WARNING|INFO"}` — gauge or histogram; counts of tests by severity.
* `3b_s4_errors_total{error_code=...}` — counter; count of errors per `E3B_S4_*` code.
* `3b_s4_duration_seconds` — S4 run latency from `start` to `finish`.

10.3.2 Metrics SHOULD be tagged with:

* `segment_id = "3B"`
* `state_id = "S4"`
* a reduced identifier for `manifest_fingerprint` (e.g. hash prefix or manifest label, to control cardinality)
* where relevant, `severity` or `profile` for test-related metrics;
* `status` and `error_code` for high-level run metrics.

10.3.3 Operators SHOULD be able to use these metrics to answer, at minimum:

* “Is S4 executing and passing reliably across manifests?”
* “How many virtual merchants are in scope, and how many are actually covered by routing semantics?”
* “How many validation tests are being enforced per manifest, and what are their severities?”
* “What are the most common S4 failure causes?”
* “Is S4’s latency negligible relative to data-plane states (S2/S3/2B)?”

---

10.4 **Traceability & correlation**

10.4.1 S4 MUST ensure that its outputs, logs and run-report entries are **correlatable** via identity:

* Logs MUST include `{segment_id="3B", state_id="S4", manifest_fingerprint, seed, parameter_hash}` and optionally `run_id`;
* S4 outputs MUST adhere to partition laws (`manifest_fingerprint={manifest_fingerprint}`);
* Any identity echoes in `virtual_routing_policy_3B` and `virtual_validation_contract_3B` (e.g. `manifest_fingerprint`, `parameter_hash`, `edge_universe_hash`) MUST match S0 and S3.

10.4.2 Given a manifest, an operator MUST be able to:

* locate `virtual_routing_policy_3B` and see:

  * which artefacts (S1–S3, policies) are referenced;
  * how event fields are bound to upstream semantics;
  * which RNG stream identifiers 2B must use;

* locate `virtual_validation_contract_3B` and see:

  * what tests exist;
  * their scopes, target populations, thresholds and severities.

10.4.3 If a platform-wide **correlation/trace ID** exists, S4 MAY:

* include it in lifecycle/error logs;
* expose it in `s4_run_summary_3B` as an informational field.

Such IDs MUST NOT affect any of S4’s deterministic decisions or policy content.

---

10.5 **Integration with Layer-1 / 4A–4B validation harness**

10.5.1 The Layer-1 validation / observability harness MUST be able to consume S4’s outputs and run-report to:

* understand, per manifest, what virtual routing semantics are in effect;
* understand, per manifest, what virtual validation tests are required and how they gate segment-level PASS;
* attribute S4 failures to specific `E3B_S4_*` codes.

10.5.2 At minimum, the harness MUST be able to derive:

* `3B.S4.status ∈ {"PASS","FAIL"}`
* `3B.S4.error_code` (if any)
* `virtual_merchant_count` and `routing_scope_virtual_merchant_count`
* `validation_test_count` and per-severity breakdown
* `routing_policy_id` / `routing_policy_version`
* `virtual_validation_policy_id` / `virtual_validation_policy_version`
* references to S4 outputs and key upstream artefacts.

10.5.3 In any **global manifest summary**, S4 SHOULD contribute:

* a brief description of virtual routing semantics (e.g. “virtual routing enabled, alias layout vX, dual-TZ semantics in effect”);
* a summary of tests (e.g. “5 BLOCKING, 3 WARNING, 2 INFO virtual-specific tests for this manifest”).

---

10.6 **Operational diagnostics & debugability**

10.6.1 On any FATAL S4 failure, S4 SHOULD log **diagnostic context** sufficient for root-cause analysis without immediate interactive debugging, for example:

* for **contract/sealing** errors: offending `logical_id`, `path`, `schema_ref`, and a short description of the mismatch;
* for **dual-TZ binding** errors: `merchant_id`, missing/invalid `tzid_settlement` or `tzid_operational`, and the relevant S1/S2 dataset references;
* for **field-binding** errors: the event field anchor that failed and the dataset/field S4 attempted to bind;
* for **validation-test** errors: the policy-defined test type and parameters that could not be compiled, including invalid dataset IDs or field anchors;
* for **idempotence** errors: hashes of current vs existing S4 outputs.

10.6.2 If the engine supports a **debug / dry-run** mode for S4, such a mode MUST:

* execute the full deterministic algorithm through Phases A–D (compile routing & validation contracts in memory);
* run all internal consistency checks;
* **not** publish `virtual_routing_policy_3B` or `virtual_validation_contract_3B` at canonical locations.

S4 MUST clearly label log and run-report entries with `mode = "dry_run"` vs `mode = "normal"` so operators do not confuse a dry-run with a committed configuration.

10.6.3 Any additional observability features (e.g. tools that render human-readable summaries of routing/validation contracts) MAY be implemented as long as they:

* use separate diagnostic artefacts or log streams;
* do not change the binding shape or semantics of S4 outputs;
* do not introduce non-determinism into S4’s behaviour.

10.6.4 Where this section appears to conflict with schemas or the dataset dictionary/registry, **schemas and catalogues are authoritative**. This section MUST be updated in the next non-editorial revision to match the actual S4 contracts while preserving the core observability guarantees above.

---

## 11. Performance & scalability *(Informative)*

11.1 **Workload character**

11.1.1 3B.S4 is a **control-plane-only** state. It does not handle high-volume tables (edges, transactions, labels) directly. Its work is mostly:

* reading S0–S3 artefacts and policy files;
* joining **merchant-level metadata** (virtual classification, settlement tz) with edge/alias metadata at a summary level;
* compiling one small routing policy JSON and one small validation-contract table.

11.1.2 The dominant scale drivers are:

* the number of **virtual merchants** `|V|`;
* the number of **virtual tests** configured in the validation policy;
* the complexity of test scoping (e.g. per-merchant tests vs a few global tests).

Even for large `|V|`, S4 is expected to be cheap compared to S2/S3 or 2B.

---

11.2 **Complexity & expected scale**

11.2.1 Let:

* `|V|` = number of virtual merchants in S1;
* `|T|` = number of tests defined in `virtual_validation_contract_3B`.

Then, asymptotically:

* **Routing policy compilation** (Phase C):

  * O(|V|) to derive per-merchant routing modes (if used), but in many designs the routing policy is mostly global and depends only weakly on |V|.

* **Validation contract compilation** (Phase D):

  * O(|T|), since each policy-defined test becomes one (or a small handful of) contract rows.

11.2.2 `|V|` might be up to ~10⁵–10⁶ in a large engine; `|T|` is usually O(10–100) per manifest. Under these assumptions, S4 remains **linear and light**, with runtime dominated by:

* reading a handful of small policies;
* generating a modest JSON and a small-to-medium table.

---

11.3 **Latency considerations**

11.3.1 Major contributors to S4 latency:

* parsing and validating schemas/dictionaries/registries (often cached across states);
* reading a few S1–S3 artefacts (usually metadata-heavy, not full scans);
* parsing the validation policy and compiling test configurations;
* serializing the routing policy and validation contract.

11.3.2 For typical configurations, S4 latency is expected to be *negligible* relative to S2/S3 or data-plane routing:

* sub-second to a few seconds per manifest in most environments, even for large `|V|`;
* possibly more in debug modes with heavy sanity checks turned on, but still small compared to spatial/RNG-heavy work.

If S4 becomes a noticeable fraction of total runtime, that is usually a sign of:

* excessive schema/dictionary reloads per run;
* very complex test definitions or target-population expressions;
* unnecessary full scans of S1–S3 data instead of metadata-level reads.

---

11.4 **Memory model & parallelism**

11.4.1 A straightforward single-process implementation can:

* load all relevant policies and contracts into memory (they are small);
* read only the **merchant-level metadata** it needs from S1–S3 (e.g. keys, tzids, counts), not full event tables;
* build `virtual_routing_policy_3B` as a single in-memory object;
* build `virtual_validation_contract_3B` as a small in-memory table, then write.

11.4.2 Memory usage is therefore modest:

* O(|V|) for any per-merchant override list (if present);
* O(|T|) for the validation contract table;
* plus a small fixed cost for policies and schema metadata.

11.4.3 Parallelism is generally unnecessary, but if implemented (e.g. parallel expansion of per-merchant tests), S4 MUST still:

* enforce canonical ordering (e.g. sort by `test_id` and `merchant_id`) before writing;
* avoid any merge order that might introduce non-determinism.

---

11.5 **I/O patterns**

11.5.1 Reads:

* S0 gate and sealed-inputs manifest;
* S1–S3 metadata (and possibly limited slices of S1–S3 outputs, but not full scans of large tables);
* virtual validation policy and routing/RNG policy files;
* event-schema/routing-field contracts.

11.5.2 Writes:

* `virtual_routing_policy_3B` — a small JSON document per manifest;
* `virtual_validation_contract_3B` — a small-to-medium table per manifest;
* optional `s4_run_summary_3B` — a small JSON document.

11.5.3 Because all outputs are **tiny** relative to data-plane artefacts, S4 is not I/O-intensive. Network or object-store latency will dominate only if the environment has very slow metadata access.

---

11.6 **SLOs & tuning knobs**

11.6.1 Reasonable SLOs for S4 in production might be:

* `P95(3b_s4_duration_seconds) < 5–10 seconds` per manifest (tunable based on environment),
* essentially no variance with respect to data volumes, but some dependence on `|V|` and `|T|`.

11.6.2 Tuning levers include:

* limiting the complexity of **validation policies** (e.g. avoid generating thousands of per-merchant tests when a small number of aggregate tests would suffice);
* caching **schema and dictionary parsing** across states or runs, rather than re-parsing for S4;
* avoiding full reading of large upstream datasets where a light metadata pass will do.

11.6.3 Changes to S4 should rarely be motivated by performance; correctness and clarity of semantics are the primary design drivers. If S4 becomes a bottleneck, it is more likely a symptom of inappropriate work being pushed into S4 (e.g. heavy data-plane analysis) and should trigger a design review.

---

11.7 **Testing & regression checks**

11.7.1 Performance/regression tests for S4 SHOULD include:

* manifests with **large virtual merchant sets** to ensure O(|V|) behaviour scales as expected;
* manifests with **many configured tests** (large `|T|`) to ensure validation contract compilation is still fast and deterministic;
* cases where multiple profiles (e.g. strict vs relaxed) are present to check that profile selection doesn’t alter cost qualitatively.

11.7.2 Tests SHOULD verify that:

* S4 runtime is stable as S1–S3 data volumes grow, given fixed `|V|` and `|T|`;
* outputs are deterministic across re-runs;
* identity, partition and ordering requirements in §§7–8 remain satisfied.

11.7.3 Since this section is informative, specific numeric thresholds and hardware assumptions are left to deployment choices. The binding requirements remain:

* S4 must be deterministic and RNG-free;
* S4 must scale in a predictable way with `|V|` and `|T|`;
* S4 must not grow into a data-plane state — its job is to compile routing & validation contracts, not to process bulk events or edges.

---

## 12. Change control & compatibility *(Binding)*

12.1 **Scope of change control**

12.1.1 This section governs all changes that affect **3B.S4 — Virtual routing semantics & validation contracts** and its artefacts, specifically:

* The **behaviour** of S4, including:

  * how dual timezone semantics (settlement vs operational) are compiled;
  * how `virtual_routing_policy_3B` is assembled;
  * how `virtual_validation_contract_3B` is assembled;
  * what tests and routing semantics are considered “in scope” for a manifest.

* The **schemas and catalogue entries** for S4-owned datasets:

  * `virtual_routing_policy_3B`;
  * `virtual_validation_contract_3B`;
  * `s4_run_summary_3B` (if defined).

* S4’s **use of upstream policies/contracts**, including:

  * the virtual validation policy pack schema;
  * routing/RNG policy schemas insofar as they affect alias layout compatibility and routing semantics;
  * any event-schema / routing-field contracts used to bind semantics to event fields.

12.1.2 This section does **not** govern:

* S0 contracts (`s0_gate_receipt_3B`, `sealed_inputs_3B`);
* S1–S3 contracts (`virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`, `edge_alias_blob_3B`, `edge_universe_hash_3B`), beyond S4’s dependence on their keys and invariants;
* Layer-1 RNG contracts or 2B’s implementation details (RNG engines, alias decoding, event production) — those are governed by Layer-1 / 2B specs;
* The 3B segment-level validation bundle and `_passed.flag`, which are owned by the 3B validation state (though they consume S4 outputs).

---

12.2 **Versioning of S4-related contracts**

12.2.1 All 3B contracts that affect S4 MUST be versioned explicitly across:

* `schemas.3B.yaml` — defining shapes for:

  * `virtual_routing_policy_3B`;
  * `virtual_validation_contract_3B`;
  * `s4_run_summary_3B` (if present);
  * any S4-specific policy helper schemas (if added).

* `dataset_dictionary.layer1.3B.yaml` - defining:

  * `id`, `schema_ref`, `path`, `partitioning`, `ordering` for each S4 dataset.

* `artefact_registry_3B.yaml` — defining:

  * manifest keys, ownership, retention and consumers for S4 datasets.

12.2.2 Policy artefacts that S4 consumes and then compiles into outputs MUST also be versioned, e.g.:

* virtual validation policy schema (e.g. `schemas.3B.yaml#/policy/virtual_validation_policy`);
* routing/RNG policy schema (either in Layer-1 or a 3B-local wrapper) that governs 2B compatibility.

12.2.3 Implementations SHOULD follow a semantic-style scheme:

* **MAJOR** — incompatible or breaking changes to:

  * S4 output shapes, semantics, partition law;
  * contract between S4 and 2B / validation harness (e.g. changes in required fields or meaning);
  * the virtual validation model (what tests must exist, how severity is interpreted).

* **MINOR** — backwards-compatible extensions:

  * new optional fields;
  * new test types that are optional;
  * new enums that older consumers can safely treat as “unknown/other” without misbehaving.

* **PATCH** — non-semantic fixes:

  * documentation corrections;
  * stricter validation that only rejects previously invalid configurations;
  * typo fixes that do not change meaning.

12.2.4 S4 MUST ensure (directly or via `s0_gate_receipt_3B.catalogue_versions`) that:

* `schemas.3B.yaml`;
* `dataset_dictionary.layer1.3B.yaml`;
* `artefact_registry_3B.yaml`

form a **compatible triplet** for the S4 implementation (e.g. same MAJOR version, or explicit compatibility matrix). If they do not, S4 MUST fail with `E3B_S4_SCHEMA_PACK_MISMATCH` and MUST NOT emit outputs.

---

12.3 **Backwards-compatible vs breaking changes**

12.3.1 The following changes are considered **backwards-compatible** (MINOR or PATCH) for S4, provided all binding guarantees in §§4–9 remain satisfied:

* Adding **optional fields** to:

  * `virtual_routing_policy_3B` (e.g. additional debug metadata, extra global flags);
  * `virtual_validation_contract_3B` (e.g. `profile`, `labels`, additional non-gating test metadata);
  * `s4_run_summary_3B`.

* Extending **enumerations** with new values where:

  * existing values retain their semantics;
  * consumers that don’t recognise new values can treat them as “other” or ignore them without mis-routing or mis-gating validation.

* Introducing **new optional test types** in the validation policy where:

  * S4 only materialises them when they are explicitly enabled;
  * older harnesses can ignore them without affecting existing gating semantics.

* Tightening **validation** in S4:

  * e.g. enforcing uniqueness of `test_id`, or stricter schema checking, as long as only configurations that were already invalid are rejected.

12.3.2 The following changes are **breaking** (MAJOR) for S4:

* Removing or renaming any **required field** in:

  * `virtual_routing_policy_3B` (identity, dual-TZ semantics, alias/RNG bindings, references to S1–S3 artefacts);
  * `virtual_validation_contract_3B` (`test_id`, `test_type`, `scope`, `inputs`, `thresholds`, `severity`).

* Changing the **type or semantics** of required fields, for example:

  * redefining the meaning of `edge_universe_hash` (e.g. different hashing law) without adding a new field;
* redefining `severity` semantics (e.g. `"WARNING"` suddenly becomes blocking without a major bump);
  * changing how `target_population` expressions are interpreted.

* Changing `path`, `partitioning` or `ordering` for S4 outputs in the dictionary.

* Changing the **validation contract model** such that:

  * previously defined tests and severity levels are interpreted differently;
  * the mapping `test_id → gating behaviour` changes for an unchanged manifest.

* Changing S4’s **routing semantics** (e.g. the binding between event fields and upstream semantics, or the meaning of per-merchant “mode”) in ways that would cause 2B to handle the same manifest differently without a new manifest or MAJOR schema bump.

12.3.3 Any breaking change MUST:

* bump the MAJOR version of `schemas.3B.yaml`;
* be accompanied by coherent updates to `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml`;
* be documented in a S4 (or 3B) changelog with a clear description of:

  * what changed;
  * how routing semantics or validation semantics are affected;
  * what migration steps are required (e.g. need for new manifests or 2B/validation changes).

---

12.4 **Mixed-version environments**

12.4.1 A **mixed-version environment** arises when:

* historical S4 outputs (`virtual_routing_policy_3B`, `virtual_validation_contract_3B`, `s4_run_summary_3B`) exist on disk under an older S4 schema; and
* the engine and contracts now reflect a newer S4 schema/dictionary/registry version.

12.4.2 S4 is responsible only for emitting outputs under the **current** contracts. It MUST:

* write new outputs according to the current schemas and dictionaries;
* **NOT** rewrite or reinterpret legacy S4 artefacts produced under older contracts as if they matched the new schema.

12.4.3 Interpreting historical S4 artefacts under old versions is the responsibility of:

* offline reporting / auditing tools;
* explicit migration tools;
* or a version-aware validation harness.

S4 MUST NOT implicitly treat old artefacts as conforming to the new layout.

12.4.4 If S4 is invoked for a `manifest_fingerprint` where S4 outputs already exist but:

* they do not validate against the current schemas, or
* recomputed outputs differ from the existing ones given the same S0–S3 inputs and policies,

then S4 MUST:

* fail with `E3B_S4_OUTPUT_INCONSISTENT_REWRITE` (or equivalent);
* not overwrite existing artefacts.

Operators MUST then either:

* preserve the old outputs and avoid re-running S4 under a newer contract for that fingerprint; or
* migrate and re-emit S4 artefacts under a **new** manifest and/or schema version, then update consumers to use the new contract.

---

12.5 **Migration & deprecation**

12.5.1 When introducing new fields or behaviours in S4 that are intended to become **mandatory**, the recommended pattern is:

1. **MINOR phase (optional)**:

   * add new fields (e.g. additional test metadata, expanded routing semantics) as optional in `schemas.3B.yaml`;
   * update S4 to populate them when possible;
   * update 2B / validation harness to prefer new fields when present but fall back gracefully when absent.

2. **MAJOR phase (required)**:

   * after adoption, promote the new fields/behaviours to required in schemas;
   * update 2B / validation to rely on them exclusively;
   * deprecate older patterns as appropriate.

12.5.2 Deprecating legacy fields or semantics SHOULD follow a similar two-step approach:

* Step 1 (MINOR): mark fields or behaviours as deprecated in documentation and add schema comments; ensure 2B/harness can ignore or stop relying on them.
* Step 2 (MAJOR): remove or repurpose those fields/behaviours only after consumers have been updated.

12.5.3 For validation tests:

* Deprecating a test type should be represented in the validation policy and schema;
* S4 should stop emitting new `test_id`s of that type in new manifests once policy says so;
* removal of support for an old test type in S4/validation harness should be treated as a MAJOR change if it alters gating semantics for existing manifests.

---

12.6 **Compatibility with upstream segments & 2B / validation harness**

12.6.1 Changes to S4 MUST remain compatible with **upstream authority boundaries**:

* S4 cannot redefine what `tzid_settlement`, `tzid_operational`, `edge_weight`, or event fields mean; those are owned by S1–S3 and Layer-1 event schemas;
* S4 cannot change the semantics of `edge_universe_hash` (S3) without a coordinated MAJOR change in S3 and in any consumers.

12.6.2 If upstream segments or policies change:

* event schema for routing/validation fields (`ip_country`, `settlement_day`, etc.);
* alias layout expectations (S3/2B);
* validation policy shapes,

the S4 spec and implementation MUST be updated accordingly and:

* preserve behaviour where possible (MINOR/PATCH); or
* treat changes as breaking (MAJOR) where semantics for existing manifests would otherwise change.

12.6.3 Changes to 2B’s routing implementation or the validation harness that affect:

* how `virtual_routing_policy_3B` is interpreted;
* how `virtual_validation_contract_3B` is executed;

MUST be coordinated with S4:

* S4 may need to emit new fields or adjust semantics;
* any incompatible changes require MAJOR versioning and clear migration steps.

---

12.7 **Change documentation & review**

12.7.1 Any non-trivial change to S4 behaviour, schemas or catalogue entries MUST be:

* recorded in a change log (e.g. `CHANGELOG.3B.S4.md` or shared `CHANGELOG.3B.md` with S4 sections);
* associated with specific schema/dictionary/registry version increments;
* accompanied by clear migration notes for 2B and validation harness consumers.

12.7.2 Before deploying S4-affecting changes, implementers SHOULD:

* run regression tests on representative manifests to ensure:

  * S4 still produces deterministic, RNG-free outputs;
  * S4 still satisfies all acceptance criteria in §8;
  * 2B correctly interprets the updated routing policy;
  * validation harness correctly interprets and runs the updated test contract.

* explicitly test **idempotence**:

  * re-run S4 under the same `{seed, parameter_hash, manifest_fingerprint}` and confirm routing & validation contracts are unchanged (or, if changed, that a new manifest/contract version was intended and documented).

12.7.3 Where this section conflicts with `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` or `artefact_registry_3B.yaml`, those artefacts SHALL be treated as **authoritative**. This section MUST be updated in the next non-editorial revision to reflect the contracts actually in force, while preserving the core guarantees that S4:

* is deterministic and RNG-free;
* obeys identity and partitioning rules;
* exposes virtual routing semantics and validation contracts in a stable, versioned, and backwards-compatible way.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

> This appendix is descriptive only. If anything here conflicts with a Binding section or with JSON-Schema / dictionary / registry entries, those authoritative sources win.

---

### 13.1 Identity & governance

* **`seed`**
  Layer-1 Philox seed for the run. Shared across segments for a given manifest; part of S4’s run identity triple, but not used to partition S4 outputs.

* **`parameter_hash`**
  Tuple-hash over the governed 3B parameter set (including any S4-relevant flags and profiles). Echoed in S4 outputs for identity, but not a partition key.

* **`manifest_fingerprint`**
  Hash of the Layer-1 manifest (ingress, artefacts, code, policies) as defined by S0. Primary partition key for all S4 datasets (`manifest_fingerprint={manifest_fingerprint}`).

* **`run_id`**
  Optional, opaque identifier for a concrete S4 execution under a given `{seed, parameter_hash, manifest_fingerprint}`. Used for logging / run-report; MUST NOT affect semantics or hashes.

---

### 13.2 Sets & high-level notation

* **`M`**
  Merchant universe (from ingress / 1A). S4 does not change `M`, but refers to it via S1.

* **`V`**
  Virtual merchant set, as defined by S1:
  `V = { m | virtual_classification_3B(m).is_virtual = 1 }`
  (or equivalent classification field).

* **`V_routing`**
  Subset of `V` for which S4 defines explicit virtual routing semantics, e.g.
  `V_routing ⊆ V`.
  In full virtual mode, `V_routing = V`. In hybrid / special modes, some `m ∈ V` may be routed differently or disabled.

* **`T`**
  Set of validation tests for a manifest, represented as rows of `virtual_validation_contract_3B`. Each `t ∈ T` has a `test_id`, `test_type`, `scope`, `inputs`, `thresholds`, `severity`.

---

### 13.3 Timezone & clock notation

* **`tzid_settlement(m)`**
  IANA timezone for merchant `m`’s **settlement** reality, as defined in `virtual_settlement_3B`. Used to define settlement-day boundaries and settlement cut-off times.

* **`tzid_operational(e)`**
  IANA timezone for the **operational** location of edge `e` in `edge_catalogue_3B`, derived by S2. Used for apparent local-time / IP-geo semantics.

* **`settlement_day`**
  The settlement day for an event, defined relative to `tzid_settlement(m)`. Computed according to Layer-1 contracts and referenced from S4 in the routing policy.

* **`operational_time` / `apparent_local_time`**
  Local time for an event from the perspective of the edge location (`tzid_operational(e)`), used for IP-like behaviour and operational analyses.

* **Dual-TZ semantics**
  Informal term for the combination:

  * *settlement clock* → `tzid_settlement(m)` for accounting/cut-off, and
  * *operational clock* → `tzid_operational(e)` for IP geo / local time.

S4 codifies which event fields use which clock.

---

### 13.4 Routing policy-specific symbols

* **`virtual_routing_policy_3B`**
  S4 egress. JSON contract that tells 2B exactly how to route virtual merchants for a manifest, including:

  * identity and policy IDs/versions;
  * dual-TZ bindings;
  * geo field bindings;
  * alias-layout version;
  * RNG stream bindings for virtual edge selection.

* **`edge_universe_hash`**
  Virtual edge universe hash from `edge_universe_hash_3B`, echoed into S4. Used by 2B and validation to check that alias tables and edge catalogue match the signed universe.

* **`virtual_edge_rng_binding`**
  Structured field (within `virtual_routing_policy_3B`) containing the logical RNG stream / substream labels that 2B MUST use for sampling edges for virtual merchants. S4 does not use RNG itself, but declares how 2B must.

* **`merchant_overrides`**
  Optional per-merchant configuration in `virtual_routing_policy_3B` describing special routing modes, e.g.:

  * `"VIRTUAL_ONLY"`
  * `"HYBRID"`
  * `"DISABLED"`

Exact vocabulary and semantics are defined in the S4 spec and routing policy.

---

### 13.5 Validation-test notation

* **`virtual_validation_policy`**
  Logical name for the governed virtual validation policy pack (e.g. `virtual_validation.yml`) that S4 compiles into `virtual_validation_contract_3B`. It defines test types, default thresholds and profiles.

* **`virtual_validation_contract_3B`**
  S4 egress. Table of test configurations, one row per `test_id`. Defines which tests must run, where, and with what thresholds.

* **`test_id`**
  Stable identifier for a single test configuration within `virtual_validation_contract_3B`. Used by validation harness for reporting and gating.

* **`test_type`**
  Test family enum; examples (illustrative):

  * `"IP_COUNTRY_MIX"` — IP-country vs `cdn_country_weights`.
  * `"SETTLEMENT_CUTOFF"` — correctness of settlement cut-off times.
  * `"EDGE_USAGE_VS_WEIGHT"` — edge selection frequencies vs `edge_weight`.

Exact vocab is defined in the validation policy schema.

* **`scope`**
  Aggregation scope for the test, e.g.:

  * `"GLOBAL"`
  * `"PER_MERCHANT"`
  * `"PER_MERCHANT_CLASS"`

* **`target_population`**
  Structured description of which merchants / flows are included in a test. Often expressed in terms of S1 outputs (e.g. `virtual_only`, merchant class lists).

* **`inputs.datasets` / `inputs.fields`**
  For each test, the concrete datasets and event fields used, referenced by dataset ID / manifest key and schema anchors.

* **`thresholds`**
  Test-specific numeric/logical thresholds (e.g. max deviation, max time skew). Interpreted according to the validation policy.

* **`severity`**
  Enum describing how a FAIL is interpreted:

  * `"BLOCKING"` — MUST prevent segment-level PASS.
  * `"WARNING"` — can WARN, but not block PASS.
  * `"INFO"` — informational only.

---

### 13.6 Error & status codes (S4)

* **`E3B_S4_*`**
  Namespace for S4 canonical error codes, such as:

  * `E3B_S4_SCHEMA_PACK_MISMATCH`
  * `E3B_S4_REQUIRED_INPUT_NOT_SEALED`
  * `E3B_S4_DUAL_TZ_INCOMPLETE`
  * `E3B_S4_FIELD_BINDING_INVALID`
  * `E3B_S4_VALIDATION_POLICY_INVALID`
  * `E3B_S4_TEST_BINDING_INVALID`
  * `E3B_S4_OUTPUT_INCONSISTENT_REWRITE`
  * `E3B_S4_RNG_USED`
  * `E3B_S4_NONDETERMINISTIC_OUTPUT`

Full semantics are described in §9.

* **`status ∈ {"PASS","FAIL"}`**
  Run-level S4 status recorded in logs and run-report.

* **`severity ∈ {"FATAL","WARN"}`**
  Error severity associated with each `E3B_S4_*` code.

---

### 13.7 Miscellaneous abbreviations

* **CDN** — Content Delivery Network (here: the virtual edge network for virtual merchants).
* **FK** — Foreign key (i.e. join key across datasets).
* **IO** — Input/Output (filesystem / object-store operations).
* **RNG** — Random Number Generator (Philox2x64-10 across Layer-1; S4 is RNG-free).
* **SLO** — Service Level Objective (latency / reliability target; S4 should be cheap compared to data-plane states).
* **tzid** — Timezone identifier (IANA tzid, as in `Europe/London`, `America/New_York`).

---

### 13.8 Cross-reference

Authoritative definitions for the symbols and concepts listed here are found in:

* **Layer-wide contracts**

  * `schemas.layer1.yaml` — primitives, RNG envelopes, validation and event schemas.
  * `schemas.ingress.layer1.yaml` — ingress shapes for merchant and geo objects.

* **Upstream segment contracts**

  * S1 — `schemas.3B.yaml#/plan/virtual_classification_3B` and `#/plan/virtual_settlement_3B`.
  * S2 — `schemas.3B.yaml#/plan/edge_catalogue_3B` and `#/plan/edge_catalogue_index_3B`.
  * S3 — `schemas.3B.yaml#/egress/edge_alias_blob_3B`, `#/egress/edge_alias_index_3B`, `#/validation/edge_universe_hash_3B`.

* **S4 contracts**

  * `schemas.3B.yaml#/egress/virtual_routing_policy_3B`
  * `schemas.3B.yaml#/egress/virtual_validation_contract_3B`
  * `schemas.3B.yaml#/validation/s4_run_summary_3B` (if used)
  * `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` entries for S4 datasets.

This appendix is intended purely as a vocabulary and symbol reference when reading or implementing **3B.S4 — Virtual routing semantics & validation contracts**.

---
