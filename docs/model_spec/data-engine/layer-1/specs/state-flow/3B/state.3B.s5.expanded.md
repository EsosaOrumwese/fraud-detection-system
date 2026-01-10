# 3B.S5 — Segment validation bundle & `_passed.flag`

## 1. Purpose & scope *(Binding)*

1.1 **State identity and role in subsegment 3B**

1.1.1 This state, **3B.S5 — Segment validation bundle & `_passed.flag`** (“S5”), is the **terminal validation and HashGate state** for Layer-1 subsegment **3B — Virtual merchants & CDN surfaces**.

1.1.2 S5 is the final step in the 3B state ladder. For a given `{seed, parameter_hash, manifest_fingerprint}`, no further 3B state MAY execute after S5 (other than re-runs of S5 itself) when constructing 3B’s artefacts for that manifest.

1.1.3 S5’s core role is to:

* re-audit the **entire 3B subsegment** (S0–S4) for structural, contractual and RNG-accounting correctness;
* package that evidence into a **3B validation bundle**; and
* compute and publish a **3B segment-level PASS flag** (`_passed.flag`) that downstream components MUST verify before consuming any 3B artefacts.

1.1.4 S5 does **not** introduce new business semantics. It is a **gating & evidence state**: given what S0–S4 have already produced, S5 answers the question:

> “Is the 3B world (virtual classification, settlement nodes, edge universe, alias tables, routing & validation contracts) internally consistent, traceable, and safe to trust for this manifest?”

---

1.2 **High-level responsibilities**

1.2.1 S5 MUST:

* take the **sealed environment** from S0 (`s0_gate_receipt_3B`, `sealed_inputs_3B`) as the definition of what artefacts 3B is allowed to touch and which upstream segments have passed;

* consume all **3B outputs** for the same `{seed, manifest_fingerprint}`:

  * S1: `virtual_classification_3B`, `virtual_settlement_3B`;
  * S2: `edge_catalogue_3B`, `edge_catalogue_index_3B`, and S2’s RNG logs;
  * S3: `edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`;
  * S4: `virtual_routing_policy_3B`, `virtual_validation_contract_3B`;

* re-run a deterministic set of **3B-scoped checks**, including at minimum:

  * S1 invariants (virtual set vs settlement nodes);
  * S2 invariants (edge catalogue vs index, counts, basic geo/tz sanity);
  * S3 invariants (alias index vs edge catalogue, alias blob vs index, edge universe hash vs component digests);
  * S4 invariants (routing policy and validation contract consistent with S1–S3 and event schema);
  * RNG-accounting invariants for S2 (Philox streams, draws/blocks vs expectations);

* construct a **validation bundle directory** for 3B under `manifest_fingerprint={manifest_fingerprint}` containing:

  * 3B.S5 manifest/receipt;
  * structural check reports and metrics;
  * RNG-accounting summaries;
  * digest summaries and cross-checks for key 3B artefacts;
  * an `index.json` (bundle index) listing evidence files and their per-file digests;

* compute a **3B bundle digest** from the validation bundle contents using a documented hashing law (typically SHA-256 over concatenated evidence bytes in ASCII-sorted path order);

* write a 3B-scoped PASS flag `_passed.flag` that encodes this bundle digest and that downstream consumers MUST verify before trusting any 3B surfaces.

1.2.2 S5 MUST ensure that, for any manifest where it reports PASS:

* every 3B artefact (S1–S4 outputs) is covered by its checks, either directly or via referenced digests;
* RNG usage in S2 is accounted for and matches declared policy;
* the `edge_universe_hash` exposed to 2B and S4 truly reflects the S2/S3 state;
* the routing and validation contracts in S4 are consistent with what 3B has actually produced.

1.2.3 S5 MUST NOT alter any S1–S4 artefacts. If S5 detects inconsistencies, it MUST fail and require upstream correction, rather than “fixing” artefacts.

---

1.3 **RNG-free and audit-only scope**

1.3.1 S5 is **strictly RNG-free**. It MUST NOT:

* open or advance any Philox RNG stream;
* emit any RNG events;
* depend on non-deterministic sources such as wall-clock time, process ID, host name, or unsorted filesystem iteration when constructing its outputs.

1.3.2 S5 MAY read RNG logs that were written by S2 (`rng_audit_log`, `rng_trace_log` or S2-specific RNG event streams) in order to:

* verify that S2’s RNG usage conforms to policy (proper streams, draws, budgets);
* reconcile RNG usage with S2’s edge counts and jitter attempts.

However, these checks are **purely audit**; S5 itself MUST perform no new random draws or RNG state changes.

1.3.3 Given identical inputs (identity triple, sealed artefacts, S1–S4 outputs, RNG logs), repeated executions of S5 for the same `{seed, parameter_hash, manifest_fingerprint}` MUST produce **bit-identical** validation bundle contents and `_passed.flag`.

---

1.4 **Relationship to upstream states and downstream consumers**

1.4.1 Upstream, S5 depends on:

* **S0** for:

  * identity, numeric/RNG governance, sealed inputs, upstream segment gates (1A–3A);

* **S1–S4** for:

  * all 3B artefacts whose correctness S5 is auditing (virtual set + settlement, edge universe, alias, routing semantics, validation tests);

* **Layer-1 RNG governance** for:

  * the shape and semantics of RNG audit/trace logs,
  * the allowed RNG streams and budgets for S2.

S5 MUST treat all these upstream artefacts as read-only and MUST NOT change their content or semantics.

1.4.2 Downstream, S5’s outputs are gates for:

* **2B’s virtual routing branch**, which MUST enforce:

  > “No 3B PASS → No read of 3B virtual artefacts”

  by verifying `_passed.flag` for the manifest before using `virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`, `edge_alias_blob_3B`, `virtual_routing_policy_3B`, etc.

* **The 3B segment-level validation state and any 4A/4B-style harness**, which MUST:

  * treat `validation_bundle_3B` + `_passed.flag` as the definitive 3B-local evidence of correctness;
  * require S5 PASS as a prerequisite for declaring 3B “valid” within the overall Layer-1 run.

1.4.3 S5 does not itself produce the Layer-1–wide PASS decision. The layer-wide harness (e.g. segments 4A/4B) may combine:

* 1A/1B/2A/2B/3A/3B segment bundles and flags;
* additional cross-segment tests;

to decide whether the entire Layer-1 run is acceptable. S5’s role is to provide the 3B part of that evidence.

---

1.5 **Out-of-scope behaviour**

1.5.1 The following are explicitly out of scope for S5 and are handled by other states:

* Virtual classification and settlement semantics — defined by S1.
* Edge placement, spatial jitter and operational timezone assignment — defined by S2.
* Alias construction and `edge_universe_hash` — defined by S3.
* Virtual routing semantics and validation-test definitions — defined by S4.
* Per-arrivals routing, scoring and labelling — handled by 2B and downstream Layer-2 states.

1.5.2 S5 MUST NOT:

* create, modify or delete any S1–S4 datasets;
* change any RNG policy, edge weights, tzids, or merchant classification;
* emit events or labels;
* compute or write a Layer-1–wide `_passed.flag` (that belongs to a higher-level validation segment).

1.5.3 S5’s scope is strictly to:

> **Inspect the sealed 3B environment and S1–S4 outputs, verify that they are internally coherent and policy-compliant, package that evidence into a 3B validation bundle, and sign it with `_passed.flag` so all downstream consumers can enforce a simple rule: “No 3B PASS → No read of 3B.”**

---

### Contract Card (S5) - inputs/outputs/authorities

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
* `virtual_routing_policy_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S4
* `virtual_validation_contract_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S4
* `s4_run_summary_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S4 (optional)
* `rng_audit_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; source: 3B.S2 (optional)
* `rng_trace_log` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; source: 3B.S2 (optional)
* `rng_event_edge_tile_assign` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; source: 3B.S2 (optional)
* `rng_event_edge_jitter` - scope: LOG_SCOPED; scope_keys: [seed, parameter_hash, run_id]; source: 3B.S2 (optional)

**Authority / ordering:**
* S5 is the sole authority for the 3B validation bundle index and PASS flag.

**Outputs:**
* `validation_bundle_3B` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `validation_bundle_index_3B` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `validation_passed_flag_3B` - scope: FINGERPRINT_SCOPED; gate emitted: final consumer gate
* `s5_manifest_3B` - scope: FINGERPRINT_SCOPED; gate emitted: none (optional)

**Sealing / identity:**
* All bundled artefacts must match the S0-sealed inventory for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or failed validation checks -> abort; no outputs published.

## 2. Preconditions & gated inputs *(Binding)*

2.1 **Execution context & identity**

2.1.1 S5 SHALL execute only in the context of a Layer-1 run where the identity triple

> `{seed, parameter_hash, manifest_fingerprint}`

has been resolved by the enclosing engine and is consistent with the Layer-1 identity / hashing policy.

2.1.2 At entry, S5 MUST be provided with:

* `seed` — the Layer-1 Philox seed for this run;
* `parameter_hash` — the governed 3B parameter hash;
* `manifest_fingerprint` — the enclosing manifest fingerprint.

2.1.3 S5 MUST NOT recompute or override these values. It MUST:

* treat them as read-only identity inputs; and
* ensure that any identity echoes it writes (e.g. in S5 manifest/summary) match these values and those embedded in `s0_gate_receipt_3B`.

---

2.2 **Dependence on 3B.S0 (gate & sealed inputs)**

2.2.1 For a given `manifest_fingerprint`, S5 MAY proceed only if both:

* `s0_gate_receipt_3B` exists at its canonical fingerprint-partitioned path; and
* `sealed_inputs_3B` exists at its canonical fingerprint-partitioned path,

and both artefacts validate against their schemas.

2.2.2 Before performing any audit work, S5 MUST:

* load and validate `s0_gate_receipt_3B` against `schemas.3B.yaml#/validation/s0_gate_receipt_3B`;
* load and validate `sealed_inputs_3B` against `schemas.3B.yaml#/validation/sealed_inputs_3B`;
* assert that `segment_id = "3B"` and `state_id = "S0"` in the gate receipt;
* assert that `manifest_fingerprint` in the gate receipt equals the run’s `manifest_fingerprint`;
* where present, assert that `seed` and `parameter_hash` in the gate receipt equal the values supplied to S5.

2.2.3 S5 MUST also assert that, in `s0_gate_receipt_3B.upstream_gates`:

* `segment_1A.status = "PASS"`;
* `segment_1B.status = "PASS"`;
* `segment_2A.status = "PASS"`;
* `segment_3A.status = "PASS"`.

If any of these statuses is not `"PASS"`, S5 MUST treat the 3B environment as **not gated** and MUST fail with a FATAL upstream-gate error. S5 MUST NOT attempt to re-verify or repair upstream validation bundles itself.

2.2.4 If `s0_gate_receipt_3B` or `sealed_inputs_3B` is missing, schema-invalid, or identity-inconsistent, S5 MUST fail immediately and MUST NOT attempt to “re-seal” inputs or continue with degraded assumptions.

---

2.3 **Dependence on 3B.S1–S4 (3B artefacts)**

2.3.1 For a given `{seed, manifest_fingerprint}`, S5 MAY proceed only if all of the following artefacts exist and validate against their schemas:

* **S1 outputs**:

  * `virtual_classification_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}`;
  * `virtual_settlement_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}`.

* **S2 outputs**:

  * `edge_catalogue_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}`;
  * `edge_catalogue_index_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}`.

* **S3 outputs**:

  * `edge_alias_blob_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}` (at least header-level validation);
  * `edge_alias_index_3B@seed={seed}, manifest_fingerprint={manifest_fingerprint}`;
  * `edge_universe_hash_3B@manifest_fingerprint={manifest_fingerprint}`.

* **S4 outputs**:

  * `virtual_routing_policy_3B@manifest_fingerprint={manifest_fingerprint}`;
  * `virtual_validation_contract_3B@manifest_fingerprint={manifest_fingerprint}`.

2.3.2 S5 MUST validate each artefact against its registered `schema_ref` (in `schemas.3B.yaml` and/or `schemas.layer1.yaml`). If any artefact is missing or schema-invalid, S5 MUST treat this as a S1/S2/S3/S4 contract violation and fail, rather than attempting to continue or repair.

2.3.3 S5 MUST treat S1–S4 outputs as **immutable inputs** for validation. It MUST NOT:

* change any S1–S4 dataset content;
* write to any S1–S4 paths;
* inject “fix-up” rows or alter digests.

Any inconsistency S5 discovers is a reason to **fail and send the run back upstream**, not to mutate prior artefacts.

---

2.4 **Required sealed artefacts (policies, RNG logs, governance)**

2.4.1 S5 MUST treat `sealed_inputs_3B` as the **sole authority** for which policy and reference artefacts it may use. For S5 to run correctly, `sealed_inputs_3B` MUST contain entries (with well-formed schema/digest) for at least:

* 3B-relevant policies:

  * CDN country/edge-budget policy (used by S2/S3);
  * spatial/tiling assets and world polygons (used by 1B/S2);
  * tz-world polygons, tzdb archive, tz overrides (used by 2A/S2);
  * alias-layout policy (used by S3);
  * routing/RNG policy (used by 2B and referenced by S3/S4);
  * virtual validation policy (compiled by S4);

* Layer-1 RNG logs and governance:

  * `rng_audit_log` and `rng_trace_log` (or equivalent RNG accounting datasets) for the `module="3B.S2"` streams;
  * Layer-1 RNG governance / numeric profile declarations in `schemas.layer1.yaml`.

2.4.2 For each such artefact, S5 MUST:

* locate its row in `sealed_inputs_3B` (`logical_id`, `owner_segment`, `artefact_kind` as needed);
* resolve `path` and `schema_ref`;
* validate the artefact against its schema (e.g. RNG logs, policies);
* if S5 recomputes its digest, assert equality with `sha256_hex`.

2.4.3 If any required policy or RNG/log artefact is missing from `sealed_inputs_3B`, unreadable, schema-invalid, or digest-mismatched, S5 MUST fail with a FATAL sealed-input error and MUST NOT attempt to fetch artefacts directly from the filesystem or registry.

---

2.5 **RNG log preconditions for S2 audit**

2.5.1 To audit S2’s RNG usage, S5 MUST have access (via `sealed_inputs_3B` and Layer-1 dictionary/registry) to:

* `rng_audit_log` and `rng_trace_log` (or equivalent RNG datasets) that cover the Philox streams/substreams used by S2, with partitioning over `{seed, parameter_hash, run_id}` as defined in Layer-1 contracts.

2.5.2 S5 MUST ensure that:

* the RNG logs it reads correspond to the same `{seed, parameter_hash, manifest_fingerprint}` and `run_id` that S2 used;
* the log shapes conform to the Layer-1 RNG envelope (`schemas.layer1.yaml#/rng/core/...`).

2.5.3 If RNG logs for S2’s module/streams cannot be found, opened, or validated, S5 MUST fail with a RNG-accounting precondition error and MUST NOT assume “no RNG” or infer usage.

---

2.6 **Scope of gated inputs & downstream obligations**

2.6.1 The union of:

* S0 artefacts (`s0_gate_receipt_3B`, `sealed_inputs_3B`);
* all S1–S4 outputs for `{seed, manifest_fingerprint}`;
* the RNG logs and 3B-relevant policies sealed in `sealed_inputs_3B`,

SHALL define the **closed input universe** for 3B.S5.

2.6.2 S5 MUST NOT:

* read artefacts that are not present in `sealed_inputs_3B` (for policies/logs) or not declared in the 3B contracts (for S1–S4 outputs);
* fetch arbitrary files, environment variables or network resources as additional validation inputs.

2.6.3 Downstream components (2B, 3B validation, 4A/4B) MAY assume that:

* S5’s validation bundle and `_passed.flag` were constructed **only** from the sealed artefacts and S1–S4 outputs;
* any missing or inconsistent artefact that would undermine 3B’s correctness would have caused S5 to fail rather than emit a PASS flag.

2.6.4 If, during execution, S5 discovers that it requires an input not sealed by S0 (e.g. a new policy or log not present in `sealed_inputs_3B`), S5 MUST:

* treat this as a configuration / sealing / contracts error;
* fail with the appropriate `E3B_S5_*` error;
* not attempt to widen the sealed universe by ad-hoc lookups.

---

## 3. Inputs & authority boundaries *(Binding)*

3.1 **Control-plane inputs from 3B.S0**

3.1.1 S5 SHALL treat **`s0_gate_receipt_3B`** as the authoritative summary of the 3B run identity and upstream gates. In particular, `s0_gate_receipt_3B` is the **sole authority** for:

* the identity triple `{seed, parameter_hash, manifest_fingerprint}`;
* which schema/dictionary/registry versions were in effect for 3B;
* which artefacts were sealed as admissible inputs for 3B (via `sealed_inputs_3B`);
* the PASS/FAIL state of upstream segments 1A, 1B, 2A and 3A.

3.1.2 S5 SHALL treat **`sealed_inputs_3B`** as the **only** list of 3B-relevant artefacts it is allowed to inspect for policies and reference data. S5 MUST NOT:

* use dictionary/registry lookups to bring in additional artefacts that are not present in `sealed_inputs_3B`;
* use ad-hoc filesystem paths, environment variables or network resources as additional validation inputs.

3.1.3 S5 MAY copy or summarise entries from `sealed_inputs_3B` into its own manifest/summary artefacts for convenience, but:

* MUST NOT alter `sealed_inputs_3B`;
* MUST treat its copy as derived documentation, not as a new source of truth.

---

3.2 **Inputs from 3B.S1–S4 (data-plane & policy artefacts)**

3.2.1 S5 SHALL treat all 3B subsegment outputs as **candidate artefacts to be audited**, not as editable surfaces. These include, for the target `{seed, manifest_fingerprint}`:

* **From S1 (virtual semantics)**:

  * `virtual_classification_3B` — virtual vs non-virtual classification and reasons;
  * `virtual_settlement_3B` — settlement node coordinates and `tzid_settlement` per virtual merchant.

* **From S2 (edge semantics & RNG-bearing work)**:

  * `edge_catalogue_3B` — edge nodes, `country_iso`, `edge_latitude_deg`, `edge_longitude_deg`, `tzid_operational`, `edge_weight`, spatial provenance;
  * `edge_catalogue_index_3B` — per-merchant/global edge counts and digests;
  * any S2 RNG events recorded under Layer-1 RNG logs (see §3.3).

* **From S3 (alias & edge-universe semantics)**:

  * `edge_alias_blob_3B` — binary alias blob for virtual edges;
  * `edge_alias_index_3B` — alias index, offsets, lengths, per-merchant checksums;
  * `edge_universe_hash_3B` — virtual edge universe hash descriptor and component digests.

* **From S4 (routing & validation semantics)**:

  * `virtual_routing_policy_3B` — 2B-facing routing semantics contract for virtual flows;
  * `virtual_validation_contract_3B` — validation test manifest for virtual flows.

3.2.2 S5 MUST treat these artefacts as **authoritative** in their respective domains:

* S1 is authoritative on *who is virtual* and what `tzid_settlement` is.
* S2 is authoritative on the *set of edges* and their `country_iso`, coordinates, `tzid_operational`, `edge_weight`.
* S3 is authoritative on *alias representation* and the `edge_universe_hash` for virtual edges.
* S4 is authoritative on *how 2B is supposed to use* S1–S3 (routing semantics) and *which tests* must be run later (validation semantics).

3.2.3 S5 MUST NOT:

* modify, append to, or delete from any S1–S4 datasets;
* rewrite or re-sign `edge_universe_hash_3B`;
* change routing or validation semantics in S4;
* introduce new business semantics that contradict upstream states.

If S5 identifies inconsistencies in S1–S4 (e.g. join failures, digest mismatches, missing edges), it MUST fail and signal an upstream contract error; it MUST **not** amend S1–S4 outputs to “make them pass”.

---

3.3 **RNG logs & policy inputs (audit only)**

3.3.1 S5 SHALL treat the Layer-1 RNG artefacts as the **sole authority** on RNG usage, including:

* `rng_audit_log` — run-scoped log of RNG streams, budgets, modules and substreams;
* `rng_trace_log` (or equivalent per-stream trace) — cumulative counters and per-event envelope data, where present;
* any S2-specific RNG event streams (e.g. jitter events) declared in `schemas.layer1.yaml` / `schemas.3B.yaml`.

3.3.2 S5’s relationship to RNG is **purely audit**:

* It MAY derive expected RNG usage for S2 (e.g. “one jitter event with 2 draws per edge, plus rejects”) based on S2’s spec and S2’s edge counts;
* It MUST then verify that actual RNG logs are consistent with those expectations:

  * correct stream IDs and substream labels;
  * correct total number of events;
  * `draws` and `blocks` fields matching derived totals;
  * monotone counters (`before`/`after`) and no stream overlap with other modules.

3.3.3 The Layer-1 RNG policy and numeric governance in `schemas.layer1.yaml` remain the **authority** on:

* RNG algorithm and envelope structure;
* permitted streams/budgets;
* numeric behaviour in general.

S5 MUST NOT redefine RNG semantics; it only checks conformance.

---

3.4 **Authority boundaries summary**

3.4.1 For clarity, S5 MUST respect the following **authority boundaries**:

* **JSON-Schema and dataset dictionaries**

  * Authority on shapes, keys, path templates and partitioning for all datasets.
  * S5 MUST validate inputs and its own outputs against these and MUST NOT deviate from them.

* **Artefact registries + sealed_inputs_3B**

  * Authority on which artefacts exist, their logical IDs, owners, licences and digests.
  * S5 MUST NOT pull in artefacts that are not sealed.

* **S1–S4 outputs**

  * Authority on 3B business semantics and pre-HashGate artefacts.
  * S5 verifies, but does not alter, these artefacts.

* **Layer-1 RNG logs & policy**

  * Authority on RNG usage and constraints for S2.
  * S5 reconciles observed usage with expectations; it does not change RNG behaviour.

* **S5 itself**

  * Only S5 is authoritative on:

    * the structure and content of the 3B validation bundle;
    * the law for computing the 3B bundle digest;
    * the format and semantics of `_passed.flag`.

3.4.2 Where S5 detects conflict between:

* an artefact’s schema/dictionary/registry contract, and
* its actual on-disk content or its relationship to other artefacts,

S5 MUST treat this as a **contract violation** and fail, rather than silently correcting or reinterpret­ing any artefact.

3.4.3 Any future extension that expands S5’s input set (e.g. additional policies, extra RNG logs, more cross-segment digests) MUST:

* be registered and sealed via S0;
* have shapes and semantics defined in schemas;
* be explicitly integrated into this section’s authority-boundary description before S5 is updated to depend on it.

---

## 4. Outputs (datasets) & identity *(Binding)*

4.1 **Overview of S5 outputs**

4.1.1 For each successfully audited `manifest_fingerprint`, S5 SHALL emit the following 3B-owned artefacts:

* **`validation_bundle_3B`** — a fingerprint-scoped directory containing 3B-specific validation evidence (manifests, structural check reports, RNG accounting summaries, digest summaries, etc.) and an index file.
* **`validation_bundle_index_3B`** — an `index.json` file inside the bundle that enumerates all evidence files and their per-file digests.
* **`_passed.flag`** — a small text file at the root of the 3B validation directory, storing the combined digest of the validation bundle, as per the canonical HashGate law.

4.1.2 S5 MAY also emit an optional **S5 run-summary / manifest** (e.g. `s5_manifest_3B.json` or `s5_run_summary_3B.json`) inside the validation bundle. This artefact:

* captures S5’s own view of identity, contracts and check outcomes;
* is **informative** to operators and higher-level harnesses;
* does not change the semantics of `validation_bundle_index_3B` or `_passed.flag`.

4.1.3 S5 MUST NOT emit:

* any new data-plane egress (events, edges, labels);
* any additional segment-level flags with different hashing laws;
* any Layer-1–wide `_passed.flag` (that belongs to a higher-level harness).

---

4.2 **Validation bundle directory - `validation_bundle_3B`**

4.2.1 The **validation bundle** for 3B SHALL be represented as a directory artefact, referenced in `dataset_dictionary.layer1.3B.yaml` with at least:

* `id: validation_bundle_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.layer1.yaml#/validation/validation_bundle_index_3B` (or a 3B-local alias) - for the index shape;
* `path: data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/`
* `partitioning: ["fingerprint"]`
* `ordering: []` (directory artefact; sort semantics are handled inside `index.json`).

4.2.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* reference `name: validation_bundle_3B` and `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a stable `manifest_key` (e.g. `"mlr.3B.validation_bundle_3B"`);
* list consumers: 3B validation state, 4A/4B harness, any debugging/observability tooling.

4.2.3 The contents of `validation_bundle_3B` MUST include at least:

* `index.json` — the bundle index (see §4.3);
* one or more S5-produced evidence files, such as:

  * `s5_manifest_3B.json` — S5’s identity/manifest summary;
  * structural check reports (e.g. `checks/s1_s2_s3_s4_structural.json`);
  * RNG-accounting summary for S2 (e.g. `rng/s2_accounting.json`);
  * digest summaries (e.g. `digests/s3_edge_universe_digest.json`, `digests/s4_contract_digest.json`).

The exact set and naming of evidence files SHOULD be stable and schema-documented, but may be extended in backwards-compatible ways (see §12).

4.2.4 All evidence files listed in `index.json` MUST reside under the bundle root `data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/` using **relative paths** without `..` or absolute path components.

---

4.3 **Bundle index - `validation_bundle_index_3B` (index.json)**

4.3.1 The validation bundle index for 3B SHALL be a single JSON file named `index.json` inside `validation_bundle_3B`. It MUST be registered in `dataset_dictionary.layer1.3B.yaml` as:

* `id: validation_bundle_index_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.layer1.yaml#/validation/validation_bundle_index_3B` (or a 3B-local alias)
* `path: data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/index.json`
* `partitioning: ["fingerprint"]`
* `ordering: []`

4.3.2 The registry entry MUST:

* reference `name: validation_bundle_index_3B` and `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a `manifest_key` (e.g. `"mlr.3B.validation_bundle_index_3B"`);
* list consumers: 3B validation state, 4A/4B, HashGate verifier utilities.

4.3.3 `schemas.layer1.yaml#/validation/validation_bundle_index_3B` defines a **single JSON object** with:

* `manifest_fingerprint`, `parameter_hash` — echoes of the current run identity;
* `s5_manifest_digest` — SHA-256 digest of the S5 manifest/summary JSON;
* `members` — array of objects, each with required fields:
  * `logical_id` — dataset or artefact ID for the evidence file;
  * `path` — relative path within the bundle root (ASCII sorted, no `..`);
  * `schema_ref` — schema anchor for the evidence file;
  * `sha256_hex` — lowercase hex SHA-256 digest of the evidence file bytes;
  * `role` — short string describing the evidence role;
  * `size_bytes` - integer >= 0;
  * optional `notes`.
* optional `metadata` — object for future, schema-controlled extensions.

4.3.4 The index MUST satisfy:

* `members.path` entries are **unique** and sorted lexicographically;
* `path` values MUST exclude `_passed.flag`;
* every member's file MUST exist under the bundle root and be readable;
* every evidence file that contributes to the bundle hash MUST appear in `members` exactly once.

---

4.4 **Segment PASS flag - `_passed.flag`**

4.4.1 The segment-level PASS flag for 3B SHALL be represented as a single-line text file named `_passed.flag`, registered in `dataset_dictionary.layer1.3B.yaml` with at least:

* `id: validation_passed_flag_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.layer1.yaml#/validation/passed_flag_3B`
* `path: data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag`
* `partitioning: ["fingerprint"]`
* `ordering: []`

4.4.2 The registry entry MUST:

* reference `name: validation_passed_flag_3B` and `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide `manifest_key` (e.g. `"mlr.3B.validation.passed"`);
* list consumers: any downstream component that gates on 3B (2B, 3B validation, 4A/4B).

4.4.3 `schemas.layer1.yaml#/validation/passed_flag_3B` MUST define the flag file as:

* a single ASCII line of the form:

  ```text
  sha256_hex = <bundle_sha256>
  ```

  where `<bundle_sha256>` is the lower-case hex encoding of the SHA-256 digest computed over the concatenation of the raw bytes of all files listed in `index.json`, in ASCII-lexicographic order of `path`.

4.4.4 The flag file:

* MUST NOT include trailing whitespace beyond the newline;
* MUST NOT be included in `index.json`;
* MUST be written only after `index.json` and all evidence files have been finalised.

---

4.5 **S5 manifest / run-summary - `s5_manifest_3B` (optional but recommended)**

4.5.1 S5 MAY emit a S5-specific manifest/summary JSON file (e.g. `s5_manifest_3B.json`) inside the validation bundle. It SHOULD be registered with:

* `id: s5_manifest_3B` (or `s5_run_summary_3B`);
* `owner_subsegment: 3B`;
* `schema_ref: schemas.3B.yaml#/validation/s5_manifest_3B`;
* `path: data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/s5_manifest_3B.json`
* `partitioning: ["fingerprint"]`
* `ordering: []`

5.5.2 The schema for `s5_manifest_3B` SHOULD include:

* `manifest_fingerprint`, `parameter_hash`;
* S5 `status ∈ {"PASS","FAIL"}` and `error_code` (if summarising a run);
* versions of 3B contracts (`schemas.3B.yaml`, 3B dictionary/registry);
* lists of key artefact digests (e.g. `edge_universe_hash`, `edge_catalogue_digest_global`);
* counts and status of major checks (e.g. number of structural checks, RNG checks, digests verified).

4.5.3 `s5_manifest_3B` is an **evidence file** inside the bundle and MUST be listed in `index.json` if present. It is not required for the bundle to be valid, but is strongly recommended for debuggability and run-report integration.

---

4.6 **Identity & partitioning for S5 outputs**

4.6.1 All S5 artefacts are **fingerprint-only**:

* `validation_bundle_3B` root directory;
* `validation_bundle_index_3B/index.json`;
* `_passed.flag`;
* `s5_manifest_3B` (if present).

Their on-disk identity is fully determined by `manifest_fingerprint={manifest_fingerprint}` and the dataset IDs / filenames.

4.6.2 S5 MAY include identity echoes (`manifest_fingerprint`, `parameter_hash`, `seed`) within its manifest or summary files. Where present:

* they MUST match the values in `s0_gate_receipt_3B`;
* they MUST NOT be used as partition keys or to shard the bundle.

4.6.3 There MUST be at most one validation bundle and one `_passed.flag` for a given `manifest_fingerprint` under the S5 contracts in effect. Re-runs of S5 for the same fingerprint MUST follow the idempotence rules defined in §7.

---

4.7 **Downstream consumption & authority of S5 outputs**

4.7.1 Together, `validation_bundle_3B` and `_passed.flag` form the **3B segment-level gate**. Any downstream component that consumes 3B artefacts MUST:

* locate the bundle and flag via the dataset dictionary/registry;
* recompute the bundle digest using `index.json` and evidence files;
* verify that recomputed digest equals `sha256_hex` recorded in `_passed.flag`.

Only if this verification succeeds MAY downstream components treat 3B as PASS for that `manifest_fingerprint`.

4.7.2 S5’s outputs are authoritative for:

* determining whether 3B is **structurally & contractually sound** for the manifest;
* providing evidence to higher-level harnesses (4A/4B) and operators.

They are not, by themselves, a guarantee of Layer-1–wide correctness; 4A/4B may impose additional global conditions.

4.7.3 No other state MAY write or modify `_passed.flag` or `validation_bundle_3B`. Any changes to these artefacts must go through S5 and obey S5’s change-control and idempotence rules.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

5.1 **Validation bundle directory - `validation_bundle_3B`**

5.1.1 The 3B validation bundle MUST be registered in `dataset_dictionary.layer1.3B.yaml` as a directory artefact with at least:

* `id: validation_bundle_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.layer1.yaml#/validation/validation_bundle_index_3B` (for the index shape; the bundle itself is a directory)
* `path: data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/`
* `partitioning: ["fingerprint"]`
* `ordering: []`

5.1.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* reference `name: validation_bundle_3B` and `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a stable `manifest_key` (e.g. `"mlr.3B.validation_bundle_3B"`);
* list primary consumers: 3B validation state, layer-wide validation (4A/4B), any HashGate verifier tools.

5.1.3 The bundle directory MUST contain:

* exactly one `index.json` file at the root (see §5.2);
* zero or more evidence files (JSON/Parquet/etc.), all residing under the bundle root and referenced in `index.json`;
* the `_passed.flag` flag file at the root (see §5.3), which MUST **not** be referenced in `index.json`.

5.1.4 The shape and semantics of each evidence file (e.g. S5 manifest, structural check reports, RNG accounting summaries) MUST be defined in `schemas.3B.yaml` or a Layer-1 schema and linked via `schema_ref` from the 3B dataset dictionary if those evidence files are themselves registered datasets. Evidence files that are not independently registered (e.g. ad hoc JSON reports) MUST still be included in `index.json` with correct digests.

---

5.2 **Bundle index — `validation_bundle_index_3B` (index.json)**

5.2.1 The bundle index MUST be registered in `dataset_dictionary.layer1.3B.yaml` with:

* `id: validation_bundle_index_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.layer1.yaml#/validation/validation_bundle_index_3B`
* `path: data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/index.json`
* `partitioning: ["fingerprint"]`
* `ordering: []` (single JSON document per fingerprint)

5.2.2 The corresponding registry entry MUST:

* reference `name: validation_bundle_index_3B` and `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a stable `manifest_key` (e.g. `"mlr.3B.validation_bundle_index_3B"`);
* list consumers: any HashGate / validation tooling that verifies bundles and flags.

5.2.3 `schemas.layer1.yaml#/validation/validation_bundle_index_3B` defines a JSON object with:

* `manifest_fingerprint`, `parameter_hash`, `s5_manifest_digest` — identity echoes and manifest digest;
* `members` — array of objects, each with required fields:
  * `logical_id` — dataset or artefact ID for the evidence file;
  * `path` — relative path within the bundle root (ASCII sorted, no `..`);
  * `schema_ref` — schema anchor for the evidence file;
  * `sha256_hex` — lowercase hex digest of the evidence file bytes;
  * `role` — short description of why the evidence exists;
  * `size_bytes` — integer >= 0;
  * optional `notes`.
* optional `metadata` for informative extensions.

5.2.4 The index MUST satisfy:

* All `members.path` values are **unique** within a given `manifest_fingerprint`.
* `members.path` values are sorted in **strict ASCII lexicographic order**.
* Every file listed in `members[].path` exists under the bundle root and is readable.
* No member corresponds to `_passed.flag` (the flag is excluded from the index by design).

5.2.5 Any additional metadata fields in the index schema (e.g. bundle version, creation timestamps) MUST be clearly defined as optional/informative and MUST NOT change the hashing law (see §4 and §6).



---

5.3 **Segment PASS flag - `_passed.flag`**

5.3.1 The 3B PASS flag MUST be registered in `dataset_dictionary.layer1.3B.yaml` with:

* `id: validation_passed_flag_3B`
* `owner_subsegment: 3B`
* `schema_ref: schemas.layer1.yaml#/validation/passed_flag_3B`
* `path: data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag`
* `partitioning: ["fingerprint"]`
* `ordering: []`

5.3.2 The registry entry MUST:

* reference `name: validation_passed_flag_3B` and `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a `manifest_key` (e.g. `"mlr.3B.validation.passed"`);
* list all downstream consumers that gate on 3B (2B, 3B validation, 4A/4B, etc.).

5.3.3 `schemas.layer1.yaml#/validation/passed_flag_3B` MUST define the flag as a text file with exactly one ASCII line of the form:

```text
sha256_hex = <bundle_sha256>
```

where `<bundle_sha256>` is the lowercase hex encoding of the SHA-256 digest over the concatenation of all bytes of files listed in `validation_bundle_index_3B` (in ASCII-sorted `path` order).

5.3.4 The schema MUST prohibit:

* additional lines;
* trailing whitespace beyond the newline;
* alternative key names (e.g. only `sha256_hex = ...` is allowed).

Any deviation MUST be treated as a schema violation.

---

5.4 **S5 manifest / summary evidence - `s5_manifest_3B` (optional)**

5.4.1 If S5 emits a dedicated manifest/summary artefact, it MUST be declared in `dataset_dictionary.layer1.3B.yaml` with:

* `id: s5_manifest_3B` (or `s5_run_summary_3B` if preferred);
* `owner_subsegment: 3B`
* `schema_ref: schemas.3B.yaml#/validation/s5_manifest_3B`
* `path: data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/s5_manifest_3B.json`
* `partitioning: ["fingerprint"]`
* `ordering: []`

5.4.2 The corresponding registry entry MUST:

* reference `name: s5_manifest_3B` and `schema_ref`;
* declare `type: "dataset"` with explicit 3B ownership metadata;
* provide a `manifest_key` (e.g. `"mlr.3B.s5_manifest_3B"`);
* list consumers: 3B validation state, 4A/4B, run-report tooling.

5.4.3 `schemas.3B.yaml#/validation/s5_manifest_3B` SHOULD define an object including, at minimum:

* `manifest_fingerprint`, `parameter_hash` (identity echoes);
* S5 `status ∈ {"PASS","FAIL"}` and `error_code` (if summarising the run);
* references to key artefacts and digests:

  * S0–S4 contracts (IDs/versions);
  * `edge_universe_hash` and its components;
  * counts of checks and their outcomes.

5.4.4 `s5_manifest_3B` MUST be treated as an **evidence file inside the bundle**:

* it MUST be placed under the bundle root;
* it MUST be included in `validation_bundle_index_3B.files` with the correct `path` and `sha256_hex`.

---

5.5 **Input anchors & cross-segment references**

5.5.1 `schemas.3B.yaml` and/or `schemas.layer1.yaml` MUST define and anchor:

* `#/validation/validation_bundle_index_3B` — used by `validation_bundle_index_3B`;
* `#/validation/passed_flag_3B` — used by `_passed.flag`;
* `#/validation/s5_manifest_3B` — used by S5 manifest/summary (if present).

5.5.2 S5’s evidence schemas SHOULD include `$ref` links back to upstream schemas where appropriate, for example:

* `s5_manifest_3B` referencing:

  * Layer-1 identity schemas (for `manifest_fingerprint_resolved`, `parameter_hash_resolved`);
  * S1–S4 artefact schemas for any embedded references or summaries.

5.5.3 `dataset_dictionary.layer1.3B.yaml` MUST declare all S5 datasets (`validation_bundle_3B`, `validation_bundle_index_3B`, `_passed.flag`, `s5_manifest_3B`) with their correct `schema_ref`, path templates and partitioning. S5 MUST use these catalogue entries rather than hard-coded paths.

---

5.6 **Binding vs informative elements**

5.6.1 Binding aspects of this section include:

* existence and names of S5 datasets (`validation_bundle_3B`, `validation_bundle_index_3B`, `_passed.flag`);
* their `schema_ref`, `path`, and `partitioning`;
* the requirement that `_passed.flag` encodes the SHA-256 of all files listed in `index.json` in ASCII-sorted path order;
* that `_passed.flag` is excluded from `index.json`.

5.6.2 Optional S5 artefacts (e.g. `s5_manifest_3B`) and additional evidence files are binding only in the sense that:

* if they are declared in schemas and dictionaries, S5 MUST write them in a schema-conformant way and include them in `index.json`;
* their presence MUST NOT change the hashing law or the meaning of `_passed.flag`.

5.6.3 In case of any discrepancy between this section and:

* `schemas.layer1.yaml`;
* `schemas.3B.yaml`;
* `dataset_dictionary.layer1.3B.yaml`;
* `artefact_registry_3B.yaml`,

those contracts SHALL be treated as authoritative. This section MUST be updated in the next non-editorial revision to reflect the canonical dataset shapes and catalogue links actually in force, while preserving the HashGate semantics and gating obligations described elsewhere.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

6.1 **Phase overview**

6.1.1 S5 SHALL implement a single, deterministic, RNG-free algorithm composed of the following phases:

* **Phase A — Environment & input load**
  Re-verify S0 gate and load all required S1–S4 artefacts, policies and RNG logs.

* **Phase B — Structural & contract checks across S1–S4**
  Run a fixed set of structural and contract checks over 3B’s logical artefacts.

* **Phase C — RNG accounting for S2**
  Reconcile expected RNG usage for S2 with actual RNG logs.

* **Phase D — Digest & cross-hash checks**
  Recompute or verify digests for key 3B artefacts and ensure consistency with `edge_universe_hash_3B` and S4.

* **Phase E — Bundle assembly & index construction**
  Emit all S5 evidence files and build `validation_bundle_index_3B/index.json`.

* **Phase F — Bundle hash & `_passed.flag` publication**
  Compute the bundle hash, write `_passed.flag`, and atomically publish the bundle.

6.1.2 At no point MAY S5:

* open or advance any RNG stream;
* emit RNG events;
* depend on non-deterministic sources (wall-clock time, process ID, host name, unsorted filesystem iteration) for choices affecting outputs.

6.1.3 For a fixed `{seed, parameter_hash, manifest_fingerprint}` and fixed S0–S4 inputs, S5 MUST produce **bit-identical** outputs (bundle contents, index and flag) across re-runs.

---

6.2 **Phase A — Environment & input load (RNG-free)**

6.2.1 S5 MUST:

1. Load `s0_gate_receipt_3B` and `sealed_inputs_3B` and validate them as per §§2–3.
2. Confirm that `{seed, parameter_hash, manifest_fingerprint}` match S0.
3. Confirm upstream gates 1A, 1B, 2A, 3A are all `status = "PASS"`.

6.2.2 S5 MUST then load and validate (using dictionary + schema):

* `virtual_classification_3B` and `virtual_settlement_3B` for `{seed,fingerprint}`;
* `edge_catalogue_3B` and `edge_catalogue_index_3B` for `{seed,fingerprint}`;
* `edge_alias_blob_3B` (header at minimum) and `edge_alias_index_3B` for `{seed,fingerprint}`;
* `edge_universe_hash_3B` for `fingerprint`;
* `virtual_routing_policy_3B` and `virtual_validation_contract_3B` for `fingerprint`.

6.2.3 S5 MUST resolve, from `sealed_inputs_3B`, and validate:

* CDN/edge-budget policy;
* spatial/tiling assets and world polygons (if used in S2);
* tz-world/tzdb/overrides (if relevant to S2 checks);
* alias-layout policy;
* routing/RNG policy;
* virtual validation policy;
* Layer-1 RNG logs (`rng_audit_log`, `rng_trace_log`, and any S2-specific RNG event streams).

6.2.4 If any required artefact in 6.2.2 or 6.2.3 cannot be resolved, opened or validated, S5 MUST fail and MUST NOT proceed to later phases.

---

6.3 **Phase B — Structural & contract checks over S1–S4 (RNG-free)**

6.3.1 **S1 checks (virtual classification & settlement)**

For all virtual merchants `m` in `virtual_classification_3B`:

* Verify there is exactly one row in `virtual_settlement_3B` for `m` (unless S1’s spec allows explicit exceptions and S5 knows how to recognise them).
* Confirm `tzid_settlement` is non-null, valid as an IANA tzid, and consistent with 2A’s tz assets (if S5 cross-checks this).
* Confirm key constraints (e.g. `merchant_id` uniqueness) and schema invariants as defined in S1 spec.

If any check fails, S5 MUST register a structural error and fail the run.

6.3.2 **S2 checks (edge catalogue & index)**

For `edge_catalogue_3B` and `edge_catalogue_index_3B`:

* Confirm schema conformance (shapes, key columns, partition law) as per S2 contracts.

* For each merchant `m`:

  * count edges in `edge_catalogue_3B` with `merchant_id = m`;
  * verify this count equals `edge_count_total` in `edge_catalogue_index_3B` for `m`.

* Verify that `edge_count_total_all_merchants` in the S2 index equals the total row count of `edge_catalogue_3B` for the partition.

* Optionally sample or fully check that coordinates and `country_iso` / `tzid_operational` values respect basic invariants (e.g. valid ranges, non-null).

Any mismatch MUST be treated as an S2-contract failure.

6.3.3 **S3 checks (alias vs catalogue & edge_universe_hash)**

Using `edge_alias_blob_3B`, `edge_alias_index_3B` and `edge_catalogue_3B`:

* Validate alias index schema (keys, `layout_version`, offsets, lengths, per-merchant checksums).

* For each merchant `m`:

  * verify exactly one alias index row exists for `m` (unless S3 spec allows zero-edge merchants and S5 can recognise those cases);
  * verify that index’s `edge_count_total` matches S2’s `edge_count_total(m)`;
  * confirm `blob_offset_bytes` and `blob_length_bytes` point inside the blob according to header `blob_length_bytes`;
  * recompute the per-merchant alias checksum over the segment in the blob and compare to `merchant_alias_checksum`.

* For the blob as a whole:

  * recompute `blob_sha256_hex` per alias-layout policy and compare to header & index/global summary.

Using `edge_universe_hash_3B`:

* Load its `components` digests (CDN policy, spatial surfaces, RNG/alias policies, S2 catalogue, alias blob/index).
* Recompute or validate each component digest against the actual artefacts.
* Recompute `edge_universe_hash` from component digests according to S3’s combination law and verify it matches the value recorded in `edge_universe_hash_3B`.

Any discrepancy MUST be treated as an S3-contract or environment corruption error.

6.3.4 **S4 checks (routing & validation contracts)**

For `virtual_routing_policy_3B`:

* Validate against its schema.
* Verify:

  * `edge_universe_hash` field matches `edge_universe_hash_3B.edge_universe_hash`;
  * all referenced artefact manifest keys (alias blob/index, edge universe hash) exist in registry and correspond to the correct datasets;
  * dual-TZ and geo-field bindings reference valid event-schema anchors.

For `virtual_validation_contract_3B`:

* Validate against its schema.
* Verify:

  * `test_id` uniqueness;
  * `test_type`, `scope`, `severity` values are allowed per validation policy;
  * `inputs.datasets` and `inputs.fields` refer to known datasets and event fields;
  * `thresholds` conform to their expected shapes.

Any failure MUST be recorded and lead to S5 failing overall.

---

6.4 **Phase C — RNG accounting for S2 (RNG-free)**

6.4.1 S5 MUST derive **expected RNG usage** for S2, based on the S2 spec and actual edge/tile counts, including:

* number of jitter events per edge (e.g. at least 1 per edge, plus bounded resamples);
* number of draws per jitter event (e.g. 2 uniforms per attempt);
* any additional RNG calls (e.g. tile assignment permutations) and their per-edge/per-tile draw counts.

6.4.2 Using `rng_audit_log` / `rng_trace_log` and any S2-specifically declared RNG event streams:

* Filter to S2’s module, stream IDs and substream labels;
* Compute:

  * total number of RNG events per substream;
  * total `draws` and `blocks` per substream;
  * check monotone counters (`before`/`after`) and no counter wrap-around or reuse across events.

6.4.3 S5 MUST verify that:

* actual RNG event counts and draws match the expectations derived in 6.4.1, within the bounds defined in S2’s spec (e.g. handle resamples allowed by jitter’s retry cap);
* no S2 usage spills into streams reserved for other modules;
* RNG behaviour respects the Layer-1 RNG policy (e.g. no over-budget draws per stream).

Any mismatch MUST be recorded and cause S5 to fail (RNG-accounting error).

---

6.5 **Phase D — Digest & cross-hash checks (RNG-free)**

6.5.1 S5 MUST confirm that all key digests and hashes are consistent:

* Recompute or verify `edge_catalogue_digest_global` (from S2) matches any echoed values in S3/S4/S5.
* Confirm that:

  * `edge_universe_hash_3B.components.edge_catalogue_digest_global` matches S2’s digest;
  * `edge_universe_hash_3B.components.edge_alias_blob_sha256_hex` matches the recomputed blob digest;
  * `edge_universe_hash_3B.components.edge_alias_index_sha256_hex` matches the recomputed index digest.

6.5.2 S5 MUST also verify that S4’s routing policy and validation contract echo any digests/IDs they carry consistently with S2/S3:

* If `virtual_routing_policy_3B` includes `edge_universe_hash` or any component digests, they MUST match S3’s descriptor;
* If `virtual_validation_contract_3B` or `s4_run_summary` reference artefact digests, those MUST be consistent with S1–S3 and policies.

6.5.3 Any digest mismatch MUST be treated as a contract error or environment corruption; S5 MUST fail and MUST NOT proceed to bundle hashing.

---

6.6 **Phase E — Bundle assembly & index construction (RNG-free)**

6.6.1 S5 MUST assemble all 3B validation evidence into a staging directory for the target `manifest_fingerprint`, under:

```text
data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/.staging/
```

(or equivalent temporary location).

6.6.2 Evidence files MUST include at least:

* An S5 manifest/summary (e.g. `s5_manifest_3B.json`) containing:

  * identity echoes;
  * contract versions (schemas/dictionaries/registries, key policies);
  * references and digests for S1–S4 artefacts;
  * a summary of check outcomes.

* One or more structural check reports (e.g. `checks/s1_s4_structural.json`) with:

  * a list of checks run;
  * PASS/WARN/FAIL per check;
  * optional per-merchant metrics for diagnostics.

* A RNG accounting report (e.g. `rng/s2_accounting.json`) summarising:

  * expected vs actual RNG usage per stream/substream;
  * any discrepancies (which must be zero on PASS).

* A digest summary file (e.g. `digests/3b_components.json`) capturing:

  * digests for S1–S4 artefacts and policies, including those used in `edge_universe_hash_3B`.

6.6.3 After all evidence files are written to staging, S5 MUST construct `index.json` in the staging directory:

1. Enumerate all evidence files under the staging root, excluding `_passed.flag` (which does not exist yet).
2. For each file, compute SHA-256 over its raw bytes → `sha256_hex`.
3. Create an index structure with entries `{ "path": "<relative_path>", "sha256_hex": "<digest>" }`.
4. Sort entries by `path` in strict ASCII lexicographic order.
5. Write `index.json` conforming to `schemas.layer1.yaml#/validation/validation_bundle_index_3B`.

6.6.4 Any error during evidence writing or index construction (I/O failure, schema violation, digest mismatch) MUST cause S5 to abandon staging and fail, not to publish a partial bundle.

---

6.7 **Phase F — Bundle hash & `_passed.flag` publication (RNG-free)**

6.7.1 Once `index.json` and all evidence files are present in the staging directory and validated:

* S5 MUST re-open `index.json`;
* For each entry in `files[]` in **ASCII-sorted order of `path`**:

  * read the referenced file’s bytes (from staging root + `path`);
  * append bytes to a hashing stream.

6.7.2 S5 MUST compute:

* `bundle_sha256 = SHA256(concat(all indexed file bytes in sorted path order))`.

`bundle_sha256` MUST be encoded as a lowercase hex string.

6.7.3 S5 MUST then create `_passed.flag` **in the staging root** with exactly one ASCII line:

```text
sha256_hex = <bundle_sha256>
```

No additional lines, spaces or trailing content are permitted.

6.7.4 After the flag is written, S5 MUST perform an **atomic publish** of the entire bundle:

* Move/rename the staging directory to the canonical validation path:

```text
data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/
```

so that:

* at no point is a partially written bundle visible under the canonical path;
* any existing bundle for this fingerprint is only replaced after idempotence checks (see §7), not blindly overwritten.

6.7.5 If any I/O or validation error occurs during flag creation or atomic move, S5 MUST:

* treat the run as FAIL;
* ensure that no partially published bundle+flag is visible at the canonical path;
* require a fresh S5 run once the root cause is resolved.

---

6.8 **Determinism & RNG-free guardrails**

6.8.1 S5 MUST guarantee that for a fixed `{seed, parameter_hash, manifest_fingerprint}` and fixed S0–S4 inputs and RNG logs:

* the set of evidence files generated;
* their contents;
* their paths;
* the order and content of `index.json.files`;
* and the resulting `_passed.flag` contents

are identical across re-runs.

6.8.2 To ensure this, S5 MUST:

* use explicit, deterministic ordering for all enumerations (e.g. sort merchants, sort paths);
* avoid using map/dict iteration order or filesystem listing order without sorting;
* avoid any configuration or environment sources that are not part of the sealed input universe.

6.8.3 S5 MUST NOT call any RNG APIs or perform any operation that would change RNG state. Any detected RNG activity under S5 (e.g. RNG events tagged with `state_id = "S5"`) MUST be treated as a correctness bug and fixed.

6.8.4 Any implementation that produces different bundles or flags for identical inputs is non-conformant with this specification and MUST be corrected by:

* fixing ordering/iteration issues;
* removing hidden dependencies on environment state;
* enforcing strict adherence to the hashing and indexing laws specified above.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

7.1 **Identity model for 3B.S5**

7.1.1 For S5, the **run identity triple** is:

* `seed`
* `parameter_hash`
* `manifest_fingerprint`

and MUST match the values recorded in `s0_gate_receipt_3B` for the same 3B run.

7.1.2 S5’s **logical identity** is this triple plus the fact that it is the 3B segment’s terminal validation state. No additional identifiers (e.g. `run_id`) may alter the meaning of the S5 artefacts.

7.1.3 Within S5 artefacts, `manifest_fingerprint` (and optionally `parameter_hash`, `seed` as echoes) MUST be consistent across:

* `s5_manifest_3B` (if present);
* any internal evidence files that embed identity;

and MUST equal the partition `fingerprint` and upstream S0 identity.

---

7.2 **Partition law**

7.2.1 All S5 outputs are **fingerprint-only**:

* `validation_bundle_3B` directory;
* `validation_bundle_index_3B/index.json`;
* `_passed.flag`;
* `s5_manifest_3B` (if present).

7.2.2 The canonical paths for S5 artefacts MUST be of the form:

* Validation bundle root:

  ```text
  data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/
  ```

* Index:

  ```text
  data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/index.json
  ```

* Flag:

  ```text
  data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
  ```

* S5 manifest/summary (if present):

  ```text
  data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/s5_manifest_3B.json
  ```

7.2.3 S5 MUST NOT:

* introduce `seed`, `parameter_hash`, `run_id` or any other dimension as a partition key for S5 datasets;
* shard the validation bundle into additional sub-partitions beyond `manifest_fingerprint={manifest_fingerprint}`.

Any future change to partitioning (e.g. per-seed validation bundles) is a **change in partition law** and MUST go through change control (§12).

---

7.3 **Ordering & index discipline**

7.3.1 Within `validation_bundle_index_3B/index.json`, the following ordering rules are binding:

* every entry’s `path` MUST be a **relative path** under the bundle root, with no `..` or absolute components;
* entries MUST be sorted in **strict ASCII lexicographic order** by `path`;
* entries MUST be unique by `path`.

S5 MUST enforce this order when writing `index.json`.

7.3.2 When computing the bundle digest for `_passed.flag`, S5 MUST:

* iterate over `validation_bundle_index_3B.files` **in the exact sorted order** specified in `index.json`;
* concat the raw bytes of each file (as found at `path`) in that order;
* compute SHA-256 over the concatenated bytes.

Any other ordering (e.g. filesystem listing order) is non-conformant.

7.3.3 No evidence file other than `_passed.flag` MAY exist at the bundle root without being listed in `index.json`. `_passed.flag` MUST NOT be listed in `index.json`.

---

7.4 **Immutability & idempotence**

7.4.1 S5 outputs are **logically immutable** for a given `manifest_fingerprint`. Once S5 has successfully published:

* `validation_bundle_3B@manifest_fingerprint={manifest_fingerprint}` (including `index.json` and evidence files), and
* `_passed.flag@manifest_fingerprint={manifest_fingerprint}`,

these artefacts define the segment-level validation state for 3B under the current contracts.

7.4.2 If S5 is re-run for the same `{seed, parameter_hash, manifest_fingerprint}`:

* S5 MUST recompute the validation bundle and its hash in staging;
* S5 MUST compare the recomputed bundle hash (and, if desired, per-file digests) against the existing bundle/flag at the canonical location;
* if they are identical, S5 MAY treat the run as idempotent and MUST NOT modify existing artefacts;
* if they differ, S5 MUST treat this as an **inconsistent rewrite** and fail with the appropriate `E3B_S5_*` error, and MUST NOT overwrite existing artefacts.

7.4.3 No other state may mutate or overwrite S5 outputs. Any change to the validation bundle or `_passed.flag` MUST be orchestrated through S5 (or an explicit migration tool operating under a new contract and/or new `manifest_fingerprint`).

---

7.5 **Atomic publish & merge discipline**

7.5.1 S5 MUST publish the validation bundle and flag using an **atomic publish** pattern:

* Construct the entire bundle (index + evidence files) and `_passed.flag` in a staging directory (e.g. under a `.staging` subdirectory).
* Perform all validations (schema, digests, internal consistency) against the staged contents.
* Only once all checks succeed, atomically move/rename the staging directory to the canonical bundle path.

7.5.2 S5 MUST guarantee that at the canonical path:

* downstream consumers never observe a state where:

  * a new `_passed.flag` exists but the corresponding `index.json` and evidence files are incomplete or inconsistent;
  * a new `index.json` exists without the corresponding flag;
  * mixed old and new bundle contents co-exist.

7.5.3 Any detection (by S5 or by downstream consumers) of:

* missing `index.json` when `_passed.flag` exists;
* missing `_passed.flag` when `validation_bundle_3B` evidence files exist;
* mismatched bundle hash (recomputed from `index.json`) vs `sha256_hex` in `_passed.flag`;

MUST be treated as a **3B.S5 failure** or environment corruption, not a valid PASS state.

---

7.6 **Multi-manifest & re-run interactions**

7.6.1 S5 MUST treat each `manifest_fingerprint` independently:

* S5 does not impose any relationship between validation bundles of different manifests;
* Cross-manifest comparisons (e.g. drift analysis) are out of scope for S5 and belong to higher-level tooling.

7.6.2 When a new manifest is created (new `manifest_fingerprint`), S5 MUST produce a **new** bundle and flag under that fingerprint; it MUST NOT reuse bundles from previous manifests.

7.6.3 If the environment changes (e.g. policies, upstream data) in a way that affects S1–S4 outputs without changing `manifest_fingerprint`, this is a violation of the manifest/identity discipline. S5 MUST detect this as an inconsistent rewrite when re-run and refuse to overwrite the existing bundle/flag.

---

7.7 **Non-conformance and correction**

7.7.1 Any implementation that:

* uses partition keys other than `manifest_fingerprint={manifest_fingerprint}` for S5 outputs;
* writes unordered or duplicate entries in `index.json`;
* computes the bundle digest over a different ordering or file set than specified;
* silently overwrites an existing bundle/flag with differing contents;
* publishes partial bundles or flags at canonical paths,

is **non-conformant** with this specification.

7.7.2 Such behaviour MUST be treated as a bug in the engine or S5 implementation. Corrective action MUST:

* restore partitioning and ordering discipline;
* re-establish immutability and idempotence guarantees;
* ensure that `_passed.flag` is a reliable, single-bit gate for 3B segment validity for each manifest.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

8.1 **S5 state-level PASS criteria**

8.1.1 A run of 3B.S5 for a given
`{seed, parameter_hash, manifest_fingerprint}`
SHALL be considered **PASS** if and only if **all** of the following groups of conditions are satisfied.

**Identity & S0 gate**

a. `s0_gate_receipt_3B` and `sealed_inputs_3B` exist for `manifest_fingerprint` and validate against their schemas.
b. `segment_id = "3B"` and `state_id = "S0"` in `s0_gate_receipt_3B`.
c. The `{seed, parameter_hash, manifest_fingerprint}` used by S5 exactly match those in `s0_gate_receipt_3B`.
d. `upstream_gates.segment_1A/1B/2A/3A.status = "PASS"` in `s0_gate_receipt_3B`.

**Contracts & inputs**

e. `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, and `artefact_registry_3B.yaml` form a compatible triplet for S5 (per 3B versioning rules).
f. All S5-mandatory artefacts are present in `sealed_inputs_3B`, readable and schema-valid, including:

* virtual validation policy;
* routing/RNG policy;
* CDN/spatial/tz/alias-layout policies;
* RNG logs / RNG governance for S2.
  g. All S1–S4 outputs required by S5 exist for the target `{seed, fingerprint}` and validate against their schemas:
* S1: `virtual_classification_3B`, `virtual_settlement_3B`;
* S2: `edge_catalogue_3B`, `edge_catalogue_index_3B`;
* S3: `edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`;
* S4: `virtual_routing_policy_3B`, `virtual_validation_contract_3B`.

**Structural & contract checks across S1–S4**

h. **S1**: For all virtual merchants in `virtual_classification_3B` (or in the scope defined by S1):

* required invariants hold (e.g. exactly one settlement row per virtual merchant where S1 requires it);
* `tzid_settlement` fields are non-null and valid IANA tzids;
* S1’s own key/shape invariants are satisfied.

i. **S2**: For `edge_catalogue_3B` and `edge_catalogue_index_3B` for `{seed,fingerprint}`:

* schema-invariants hold (keys, partitioning, non-nullness constraints as per S2 spec);
* for each merchant `m`, the row count in `edge_catalogue_3B` with `merchant_id = m` equals `edge_count_total(m)` in `edge_catalogue_index_3B`;
* global counts in the index (e.g. `edge_count_total_all_merchants`) equal the total edge row count.

j. **S3**: For alias artefacts and `edge_universe_hash_3B`:

* alias index schema-invariants hold (keys, `layout_version`, offsets, lengths, checksums);
* for each merchant, index `edge_count_total(m)` matches S2’s `edge_count_total(m)`;
* per-merchant alias segments indicated by `(blob_offset_bytes, blob_length_bytes)` are within blob bounds and their `merchant_alias_checksum` matches recomputed values;
* blob-level digest (`blob_sha256_hex`) matches recomputed SHA-256 of the alias blob;
* component digests in `edge_universe_hash_3B` match recomputed digests of the referenced artefacts;
* `edge_universe_hash` in `edge_universe_hash_3B` matches the value recomputed from its components using the documented combination law.

k. **S4**: For routing and validation contracts:

* `virtual_routing_policy_3B` validates against its schema and echoes `edge_universe_hash` consistently with `edge_universe_hash_3B`;
* all artefact manifest keys referenced in `virtual_routing_policy_3B` exist in the registry and resolve to the expected S2/S3 outputs;
* routing field bindings reference valid event-schema anchors;
* `virtual_validation_contract_3B` validates against its schema;
* `test_id` values are unique per fingerprint;
* all `test_type`, `scope`, `severity` values are legal per validation-policy schema;
* all dataset/field references in `inputs` point to existing datasets and fields.

**RNG accounting for S2**

l. From S2’s spec and edge counts, S5 derives expected RNG usage (events, draws/blocks per stream/substream) for S2.
m. Using `rng_audit_log` / `rng_trace_log` and any S2-specific RNG event streams, S5 verifies that for all S2 streams/substreams:

* the number of RNG events and total `draws`/`blocks` matches the expectations (within any documented tolerance due to retries);
* stream IDs and substream labels are correct;
* counters (`before`/`after`) are strictly monotone and non-overlapping;
* no S2 usage appears on unauthorised streams or exceeds declared budgets.

**Bundle assembly & hashing**

n. S5 successfully assembles a staging `validation_bundle_3B` for the manifest, containing:

* an S5 manifest/summary;
* structural check reports;
* RNG-accounting report(s);
* digest summary reports;
* any other evidence files defined by the S5 spec.

o. S5 successfully builds `validation_bundle_index_3B/index.json` such that:

* it validates against `schemas.layer1.yaml#/validation/validation_bundle_index_3B`;
* it lists all bundle evidence files (every file S5 intends to include in the bundle digest) exactly once;
* `path` values are relative, unique, ASCII-lex sorted and contain no `..` or absolute elements;
* `sha256_hex` values match recomputed SHA-256 digests of the corresponding files.

p. S5 successfully computes the bundle digest:

* `bundle_sha256 = SHA256(concat(bytes_of_files_in_index_order))`,

and writes `_passed.flag` in the staging root with the exact content:

```text
sha256_hex = <bundle_sha256>
```

(no extra whitespace or lines).

q. After validation, S5 atomically publishes the staged bundle and flag to their canonical paths so that:

* `validation_bundle_3B` and `validation_bundle_index_3B` represent the same evidence set that was hashed;
* `_passed.flag` matches this bundle and nothing else.

**RNG-free & deterministic behaviour**

r. S5 itself has emitted **no RNG events** and used no RNG APIs.
s. Evidence generation, index ordering and bundle hashing depend only on sealed inputs and deterministic rules, not on ambient environment.

8.1.2 If **any** condition in 8.1.1 is not satisfied, the S5 run MUST be classified as **FAIL**. In that case:

* S5 MUST NOT publish a `_passed.flag` that claims a valid bundle;
* any partially written bundle and/or flag MUST be treated as invalid and MUST NOT be consumed by downstream components.

---

8.2 **Gating obligations for downstream consumers**

8.2.1 For each `manifest_fingerprint`, any downstream component that intends to **consume 3B artefacts** (including but not limited to: `virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`, `edge_alias_blob_3B`, `virtual_routing_policy_3B`, `virtual_validation_contract_3B`) MUST enforce:

> **No 3B PASS → No read of 3B artefacts**

by:

* resolving `validation_bundle_3B` and `_passed.flag` via the dataset dictionary and registry;
* recomputing the bundle digest from `index.json` and the listed files;
* verifying that recomputed digest equals `sha256_hex` in `_passed.flag`.

Only if this verification succeeds MAY 3B artefacts be treated as valid for that manifest.

8.2.2 In particular:

* **2B’s virtual routing branch** MUST NOT route using 3B virtual artefacts unless `_passed.flag` has been verified for the manifest;
* **3B validation state and any 4A/4B harness** MUST treat a failed or missing `_passed.flag` as “3B not validated” and MUST NOT declare Layer-1 globally PASS based on 3B surfaces.

8.2.3 Any downstream detection of:

* missing `validation_bundle_3B` or `_passed.flag` for a manifest that is expected to be validated;
* mismatch between recomputed bundle digest and `sha256_hex` in `_passed.flag`;
* schema-invalid `index.json` or missing evidence files listed in it;

MUST be treated as a **3B.S5 failure** or environment corruption and MUST cause the downstream component to:

* refuse to treat 3B as PASS for that manifest;
* log an appropriate error;
* require a fresh S5 run or environment remediation.

---

8.3 **Interaction with upstream gates and global validation**

8.3.1 S5 PASS is a **necessary but not sufficient** condition for overall Layer-1 PASS:

* S5 PASS guarantees only that 3B’s own artefacts satisfy 3B’s structural, RNG and contract checks for the manifest;
* other segments (1A, 1B, 2A, 2B, 3A) must also satisfy their own terminal validation states and PASS flags;
* the layer-wide harness (e.g. 4A/4B) may impose additional cross-segment checks and global criteria.

8.3.2 S5 MUST fail if S0 or S1–S4 invariants are violated, even if some 3B artefacts appear superficially usable. There is **no** notion of “partial 3B PASS” in S5: either the bundle & flag are valid and verified, or 3B is not gated for that manifest.

8.3.3 The layer-wide harness and any operator-facing tooling MUST treat:

* absence of S5 outputs;
* S5 FAILURE;
* or any divergence between bundle digest and flag

as a clear signal that 3B surfaces MUST NOT be used for that manifest, regardless of the state of other segments.

---

8.4 **Failure semantics & remediation**

8.4.1 Any violation of the binding requirements in this section MUST result in an S5 **FAILED** run with a specific `E3B_S5_*` error code (see §9). S5 MUST:

* not publish a misleading `_passed.flag`;
* log the error with sufficient context;
* leave any existing, previously valid S5 outputs intact (if they exist and pass idempotence checks).

8.4.2 Remediation is always **upstream or environment-facing**, not “fix-up in S5”:

* For structural errors in S1–S3 → fix S1–S3 implementations/data and rerun those states, then rerun S5.
* For S4 contract inconsistencies → correct S4 compilation or policies, rerun S4, then rerun S5.
* For RNG-accounting failures → adjust S2 or RNG policy/implementation, recompute S2, then rerun S5.
* For bundle/index/flag issues → correct S5 implementation, then regenerate bundle & flag.

8.4.3 Downstream harnesses MUST treat S5 failures as blocking for 3B and MUST NOT circumvent S5 by consuming S1–S4 artefacts directly, except in explicitly labelled debugging modes that are never used in production or for training/evaluation pipelines.

---

## 9. Failure modes & canonical error codes *(Binding)*

9.1 **Error model & severity**

9.1.1 3B.S5 SHALL use a **state-local error namespace** of the form:

> `E3B_S5_<CATEGORY>_<DETAIL>`

All codes in this section are reserved for S5 and MUST NOT be reused by other states.

9.1.2 Every surfaced S5 failure MUST include, at minimum:

* `segment_id = "3B"`
* `state_id = "S5"`
* `error_code`
* `severity ∈ {"FATAL","WARN"}`
* `manifest_fingerprint`
* optional `{seed, parameter_hash}`
* a human-readable `message` (non-normative)

9.1.3 All codes below are **FATAL** for S5 unless explicitly marked `WARN`:

* **FATAL** ⇒ S5 MUST NOT publish a `_passed.flag` asserting PASS for that `manifest_fingerprint`, and any bundle produced in the run MUST be considered invalid.
* **WARN** ⇒ S5 MAY complete and publish a bundle+flag, but the condition MUST be observable in logs / run-report and SHOULD be surfaced in metrics.

---

### 9.2 Identity & gating failures

9.2.1 **E3B_S5_IDENTITY_MISMATCH** *(FATAL)*
Raised when S5’s `{seed, parameter_hash, manifest_fingerprint}` do not match `s0_gate_receipt_3B`, or when S0’s identity fields are self-inconsistent.

Typical triggers:

* S5 invoked with a different identity triple than S0.
* Manual tampering with S0 artefacts.

Remediation:

* Fix the run harness to pass consistent identity to S0–S5.
* Regenerate S0 artefacts if they were modified.

---

9.2.2 **E3B_S5_GATE_MISSING_OR_INVALID** *(FATAL)*
Raised when S5 cannot use S0 artefacts as a valid gate:

* `s0_gate_receipt_3B` or `sealed_inputs_3B` missing;
* or either fails schema validation.

Typical triggers:

* S5 invoked before S0 has run successfully.
* S0 artefacts corrupted or out-of-date relative to schemas.

Remediation:

* Run/fix S0 for the manifest.
* Restore or regenerate S0 artefacts.

---

9.2.3 **E3B_S5_UPSTREAM_GATE_BLOCKED** *(FATAL)*
Raised when `s0_gate_receipt_3B.upstream_gates` indicates that any of 1A, 1B, 2A, 3A has `status ≠ "PASS"`.

Typical triggers:

* One or more upstream segments failed validation for this manifest.

Remediation:

* Diagnose and fix failing upstream segment(s);
* rerun their terminal validation;
* rerun S0–S5 for 3B afterwards.

---

### 9.3 Contract & sealed-input failures

9.3.1 **E3B_S5_SCHEMA_PACK_MISMATCH** *(FATAL)*
Raised when 3B’s contract triplet is incompatible for S5:

* `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, `artefact_registry_3B.yaml` do not form a consistent version set;
* required S5 datasets or schema refs are missing.

Typical triggers:

* Partial deployment of 3B contracts.
* Editing dictionary/registry without updating schemas.

Remediation:

* Align schema/dictionary/registry versions;
* redeploy coherent contracts;
* rerun S0–S5.

---

9.3.2 **E3B_S5_REQUIRED_INPUT_NOT_SEALED** *(FATAL)*
Raised when a **mandatory S5 input artefact** is not present in `sealed_inputs_3B`, including (non-exhaustive):

* virtual validation policy;
* routing/RNG policy;
* alias-layout policy;
* CDN / spatial / tz assets relevant to S2/S3 checks;
* RNG logs or RNG governance artefacts.

Typical triggers:

* New artefact introduced but S0 sealing logic not updated.
* Registry/dictionary updated but `sealed_inputs_3B` not.

Remediation:

* Register artefact properly and add to S0 sealing;
* rerun S0 and then S5.

---

9.3.3 **E3B_S5_INPUT_OPEN_FAILED** *(FATAL)*
Raised when S5 resolves a required artefact from `sealed_inputs_3B` but cannot open it.

Typical triggers:

* `path` is stale or incorrect;
* file/object missing;
* permissions or storage endpoint misconfigured.

Remediation:

* Fix storage/permissions/network;
* ensure `sealed_inputs_3B.path` entries are correct;
* rerun S0 (if paths changed) and then S5.

---

9.3.4 **E3B_S5_INPUT_SCHEMA_MISMATCH** *(FATAL)*
Raised when a sealed artefact that S5 depends on does not conform to its `schema_ref`:

* policy configuration missing required fields;
* RNG logs not matching their schema;
* spatial/tz assets missing required columns.

Typical triggers:

* Schema updated without updating artefact content.
* Incorrect schema_ref in the dictionary.

Remediation:

* Correct artefact or schema_ref;
* redeploy and reseal via S0;
* rerun S5.

---

### 9.4 S1–S4 structural & contract failures

9.4.1 **E3B_S5_S1_CONTRACT_VIOLATION** *(FATAL)*
Raised when S1 outputs violate S1 contracts from S5’s perspective, e.g.:

* virtual merchants missing required settlement rows;
* duplicate or inconsistent settlement records for a virtual merchant;
* invalid or missing `tzid_settlement` values.

Typical triggers:

* bugs in S1;
* partial or corrupted S1 outputs.

Remediation:

* Fix S1 implementation/inputs;
* regenerate S1 outputs;
* rerun S5 after S1–S4 are consistent.

---

9.4.2 **E3B_S5_S2_CONTRACT_VIOLATION** *(FATAL)*
Raised when S2 outputs violate S2 contracts, e.g.:

* mismatch between per-merchant edge counts in `edge_catalogue_3B` and `edge_catalogue_index_3B`;
* invalid or missing key fields (`merchant_id`, `country_iso`, coordinates, `tzid_operational`);
* global edge count mismatch.

Typical triggers:

* bugs in S2 edge allocation or index writing;
* partial S2 writes.

Remediation:

* Fix S2 logic;
* regenerate S2 outputs;
* rerun S5 after S2 is consistent with its spec.

---

9.4.3 **E3B_S5_S3_CONTRACT_VIOLATION** *(FATAL)*
Raised when alias artefacts or `edge_universe_hash_3B` violate S3 contracts, e.g.:

* alias index counts differ from S2’s counts;
* alias index points outside blob bounds;
* per-merchant alias checksums don’t match recomputed checksums;
* alias blob digest in header/index differs from actual blob hash;
* component digests in `edge_universe_hash_3B` don’t match the artefacts they claim to represent.

Typical triggers:

* bugs in alias construction or layout;
* adoption of a new alias layout without updating S3/S5 logic;
* corruption of alias blob or index files.

Remediation:

* Fix S3 implementation/config;
* regenerate S3 outputs;
* rerun S5.

---

9.4.4 **E3B_S5_S4_CONTRACT_VIOLATION** *(FATAL)*
Raised when routing/validation contracts from S4 are inconsistent with upstream artefacts or their own schemas, e.g.:

* `virtual_routing_policy_3B` references non-existent artefacts or mismatched digests;
* dual-TZ or geo-field bindings refer to invalid event-schema fields;
* `virtual_validation_contract_3B` references unknown datasets/fields or uses invalid test types/severities.

Typical triggers:

* bugs in S4 compilation;
* validation policy updated without updating S4.

Remediation:

* Fix S4 implementation or policy definitions;
* regenerate S4 outputs;
* rerun S5.

---

### 9.5 RNG accounting failures (S2)

9.5.1 **E3B_S5_RNG_LOG_MISSING_OR_INVALID** *(FATAL)*
Raised when RNG logs needed to account for S2’s RNG usage are missing or schema-invalid:

* `rng_audit_log` / `rng_trace_log` for S2 streams cannot be found;
* RNG log rows for S2 fail schema validation.

Typical triggers:

* RNG logging disabled or misconfigured;
* incorrect partitioning/paths for RNG logs.

Remediation:

* Fix RNG logging configuration;
* ensure logs are written as per Layer-1 RNG spec;
* re-run S2 (if needed) and S5.

---

9.5.2 **E3B_S5_RNG_ACCOUNTING_MISMATCH** *(FATAL)*
Raised when expected RNG usage for S2 (based on S2 spec + edge counts) does not match actual RNG logs:

* number of RNG events per stream/substream inconsistent;
* total draws/blocks incorrect;
* counters not monotone or overlapping;
* RNG streams used that are not declared for S2.

Typical triggers:

* RNG calls in S2 not aligned with spec;
* multiple S2 runs sharing streams;
* incorrect mapping from S2 events to logs.

Remediation:

* Fix S2 RNG usage and/or RNG policy;
* regenerate S2 outputs;
* rerun S5.

---

### 9.6 Digest & universe-hash failures

9.6.1 **E3B_S5_DIGEST_COMPONENT_MISMATCH** *(FATAL)*
Raised when a recorded digest for a key artefact does not match its recomputed digest, e.g.:

* `edge_catalogue_digest_global` in S2 index vs recomputed;
* `edge_alias_blob_sha256_hex` vs actual alias blob digest;
* `edge_alias_index_sha256_hex` vs index digest;
* S4 or S5 manifest echoes inconsistent with actual artefacts.

Typical triggers:

* partial overwrites or corruption of artefacts;
* digest computation bugs upstream or in S5.

Remediation:

* Fix upstream digest reporting or recompute artefacts;
* rerun S3/S4 (if they own digests);
* rerun S5.

---

9.6.2 **E3B_S5_UNIVERSE_HASH_MISMATCH** *(FATAL)*
Raised when the `edge_universe_hash` in `edge_universe_hash_3B` does not match the value S5 recomputes from its component digests using the documented combination law.

Typical triggers:

* bug in S3’s universe-hash computation;
* manual tampering or incomplete reprocessing of S2/S3 artefacts.

Remediation:

* Fix S3 universe-hash logic;
* regenerate S3 outputs;
* rerun S5.

---

### 9.7 Bundle/index/flag structure & idempotence failures

9.7.1 **E3B_S5_BUNDLE_INDEX_SCHEMA_VIOLATION** *(FATAL)*
Raised when `validation_bundle_index_3B/index.json` fails its schema:

* missing `files` or required fields;
* `path` not relative, containing `..` or absolute segments;
* unsorted or duplicate `path` entries.

Typical triggers:

* bugs in S5 index construction;
* manual edits to `index.json`.

Remediation:

* Fix S5 index-building logic;
* ensure canonical path handling;
* regenerate bundle + flag.

---

9.7.2 **E3B_S5_BUNDLE_CONTENT_MISMATCH** *(FATAL)*
Raised when:

* a file listed in `index.json.files` does not exist or is unreadable;
* the recomputed per-file `sha256_hex` for an entry does not match the value in `index.json`.

Typical triggers:

* partial writes;
* corruption or external modification of evidence files.

Remediation:

* Ensure S5 writes evidence files and index atomically;
* avoid external modification of bundle contents;
* regenerate bundle + flag.

---

9.7.3 **E3B_S5_FLAG_SCHEMA_VIOLATION** *(FATAL)*
Raised when `_passed.flag` does not conform to its schema:

* extra lines;
* malformed `sha256_hex = ...` line;
* incorrect position or partitioning.

Typical triggers:

* incorrect flag write logic;
* manual edits to the flag.

Remediation:

* Fix S5 flag-writing logic;
* regenerate bundle + flag.

---

9.7.4 **E3B_S5_FLAG_DIGEST_MISMATCH** *(FATAL)*
Raised when:

* the bundle digest recomputed from `index.json` and evidence files does not equal the `sha256_hex` recorded in `_passed.flag`.

Typical triggers:

* bundle contents changed after flag was written;
* index changed without updating the flag;
* bug in digest computation.

Remediation:

* treat as environment/bundle corruption;
* regenerate bundle + flag via S5.

---

9.7.5 **E3B_S5_OUTPUT_INCONSISTENT_REWRITE** *(FATAL)*
Raised when S5 is re-run for a `manifest_fingerprint` that already has a bundle+flag, and:

* recomputed bundle digest differs from existing `_passed.flag.sha256_hex`;
* or per-file digests in recomputed index differ from those in the existing index,

under identical inputs.

Typical triggers:

* environment drift (policies, artefacts, S1–S4 outputs) under a constant `manifest_fingerprint`;
* manual modification of bundle or S1–S4 artefacts after an earlier S5 run.

Remediation:

* treat as manifest/identity violation;
* either restore original environment to match original bundle, or generate a new manifest (new fingerprint) and re-run S0–S5 under that new identity.

---

### 9.8 RNG & determinism failures

9.8.1 **E3B_S5_RNG_USED** *(FATAL)*
Raised if S5 is observed to use RNG despite being specified as RNG-free, e.g.:

* RNG events with `state_id = "S5"` in RNG logs;
* known RNG APIs called during S5 execution.

Typical triggers:

* accidental reuse of RNG-based helper functions in S5;
* copy-paste of S2 code into S5.

Remediation:

* remove all RNG usage from S5;
* add regression tests to ensure S5 never emits RNG events.

---

9.8.2 **E3B_S5_NONDETERMINISTIC_OUTPUT** *(FATAL)*
Raised when S5 outputs differ across re-runs under identical inputs:

* different set/order/content of evidence files;
* different `index.json` ordering or digests;
* different `_passed.flag` value.

Typical triggers:

* reliance on unsorted directory listings or hash-map iteration order;
* hidden environment dependencies (e.g. timestamps affecting evidence content beyond manifest identity);
* inconsistent configuration sources.

Remediation:

* enforce canonical ordering and deterministic data generation;
* remove hidden dependencies on environment;
* verify idempotence via tests.

---

9.9 **Error propagation & downstream behaviour**

9.9.1 On any FATAL `E3B_S5_*` error, S5 MUST:

* log a structured error event with code, severity and context;
* ensure no misleading `_passed.flag` is published for the manifest;
* ensure partial bundles are not visible at the canonical location.

9.9.2 The run harness and downstream components MUST:

* treat any `E3B_S5_*` FATAL error as “3B not validated” for that manifest;
* refuse to treat 3B as PASS until S5 has successfully produced a coherent bundle and matching flag;
* surface S5 failures in run reports (e.g. 4A/4B) as **3B.S5 validation-bundle failure**.

9.9.3 Any new S5 failure condition introduced in future versions MUST:

* be given a unique `E3B_S5_...` error code;
* be documented here with severity, typical triggers and remediation;
* NOT overload an existing code with new, incompatible semantics.

---

## 10. Observability & run-report integration *(Binding)*

10.1 **Structured logging requirements**

10.1.1 S5 MUST emit, at minimum, the following **lifecycle log events** per attempted run:

* a **`start`** event when S5 begins work for a given `{seed, parameter_hash, manifest_fingerprint}`, and
* a **`finish`** event when S5 either completes successfully (PASS) or fails (FAIL).

10.1.2 Both `start` and `finish` events MUST be structured and include at least:

* `segment_id = "3B"`
* `state_id = "S5"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `event_type ∈ {"start","finish"}`
* `ts_utc` — UTC timestamp at which the event was logged

10.1.3 The `finish` event MUST additionally include:

* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL; `null` or omitted for PASS)
* `bundle_written` — boolean indicating whether a validation bundle was successfully written to a staging directory and validated
* `flag_written` — boolean indicating whether `_passed.flag` was successfully written in staging
* `evidence_file_count` — number of evidence files included in `validation_bundle_index_3B` (excluding `index.json` and `_passed.flag`)
* `rng_check_discrepancy_count` — number of RNG-accounting discrepancies detected (MUST be 0 for PASS)

10.1.4 For every FATAL error, S5 MUST emit at least one **error log event** that includes:

* the fields in 10.1.2,
* `error_code` in the `E3B_S5_*` namespace,
* `severity = "FATAL"`,
* and sufficient diagnostic context to triage the failure, for example:

  * for S1–S4 structural failures: which check failed (e.g. `check_id`), affected `merchant_id`/artefact, brief description;
  * for RNG-accounting failures: which S2 stream/substream, expected vs actual draws/events;
  * for digest mismatches: artefact name (`edge_alias_blob`, `edge_catalogue`, etc.), recorded digest vs recomputed digest;
  * for bundle/index/flag issues: problematic `path` entry, missing file, or mismatched hash.

10.1.5 WARN-level conditions (if any are defined in future) MUST:

* include `severity = "WARN"` and an appropriate `E3B_S5_*` code;
* never be used to hide conditions that this specification classifies as FATAL.

---

10.2 **Run-report record for 3B.S5**

10.2.1 S5 MUST produce a **run-report record** for each `{seed, manifest_fingerprint}` (or per `manifest_fingerprint` if the harness treats S5 as seed-agnostic) that can be consumed by the Layer-1 run-report / 4A–4B harness. This record MAY be implemented as:

* a row in a dedicated run-report dataset, and/or
* an in-memory summary passed to the harness,

but it MUST contain at least:

* `segment_id = "3B"`
* `state_id = "S5"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL; `null` or omitted for PASS)
* `evidence_file_count` — number of evidence files listed in `validation_bundle_index_3B`
* `bundle_size_bytes` — total size of all evidence files plus `index.json` (optional but recommended)
* `rng_check_discrepancy_count`
* `s1_structural_error_count`, `s2_structural_error_count`, `s3_structural_error_count`, `s4_structural_error_count` (0 on PASS; optional but recommended)
* canonical paths / manifest keys for:

  * `validation_bundle_3B`
  * `validation_bundle_index_3B`
  * `validation_passed_flag_3B`

10.2.2 Where available, the run-report record SHOULD also include:

* S5’s view of contract versions (e.g. `schemas_3B_version`, `dictionary_3B_version`, `registry_3B_version`);
* `edge_universe_hash` (echo from `edge_universe_hash_3B`);
* counts of checks by type (e.g. `check_structural_count`, `check_rng_count`, `check_digest_count`);
* number of merchants with edges (`virtual_edge_merchant_count`) and total edges (`edge_count_total_all_merchants`), echoed from S2/S3.

10.2.3 The run-report harness MUST be able to determine from S5’s record alone:

* whether S5 has successfully produced a validation bundle and `_passed.flag` for this manifest;
* where those artefacts are located;
* whether there were any RNG-accounting or structural issues (and how many) even in non-fatal diagnostic runs (if those are ever supported for development).

---

10.3 **Metrics & counters**

10.3.1 S5 MUST emit the following **metrics** (names illustrative; the actual metric names may vary as long as semantics are preserved):

* `3b_s5_runs_total{status="PASS|FAIL"}` — counter; incremented once per S5 run.
* `3b_s5_evidence_file_count` — gauge/histogram; number of evidence files in `validation_bundle_index_3B`.
* `3b_s5_bundle_size_bytes` — gauge/histogram; total size of bundle evidence bytes.
* `3b_s5_rng_discrepancies_total` — counter; number of RNG-accounting discrepancies detected across all runs, by `error_code` label if appropriate.
* `3b_s5_structural_failures_total{source="S1|S2|S3|S4"}` — counters; number of S5 runs that failed due to structural issues in each upstream state.
* `3b_s5_digest_mismatches_total` — counter; number of runs failing due to digest/universe-hash inconsistencies.
* `3b_s5_duration_seconds` — latency of S5 run (finish `ts_utc` minus start `ts_utc`).

10.3.2 Metrics SHOULD be tagged with:

* `segment_id = "3B"`
* `state_id = "S5"`
* a reduced identifier for `manifest_fingerprint` (e.g. hash prefix or manifest label) where cardinality constraints permit;
* `status` and `error_code` for run-level metrics;
* `source` for structural failure metrics (`S1`, `S2`, `S3`, `S4`, `RNG`, `DIGEST`).

10.3.3 Operators SHOULD be able to use these metrics to answer, for example:

* “How often does 3B.S5 run and how often does it PASS vs FAIL?”
* “What are the most common classes of S5 failures (S1/S2/S3/S4 structure, RNG accounting, digest mismatches, bundle issues)?”
* “What is the typical evidence-bundle size and evidence file count per manifest?”
* “Is S5 latency negligible compared to upstream segment costs?”

---

10.4 **Traceability & correlation**

10.4.1 S5 MUST ensure that its logs, run-report entries and bundle artefacts are **correlatable** via identity:

* All S5 logs MUST include `{segment_id="3B", state_id="S5", manifest_fingerprint, seed, parameter_hash}` and optionally `run_id`.
* S5’s manifest/summary evidence (if present) SHOULD embed the same identity.
* S5 outputs MUST adhere to the partitioning rules in §7 (`manifest_fingerprint={manifest_fingerprint}` only).

10.4.2 Given a `manifest_fingerprint`, an operator or tool MUST be able to:

* locate `validation_bundle_3B` and `_passed.flag`;
* recompute and verify the bundle digest using `validation_bundle_index_3B`;
* inspect S5 manifest/summary to see:

  * which checks were run;
  * which artefacts and digests were considered;
  * whether any checks WARNed or were skipped (if such semantics exist).

10.4.3 If a global **run-report / manifest summary** exists (e.g. built by 4A/4B), S5’s run-report record MUST provide all the fields needed to integrate 3B’s validation state into that global view (status, error_code, evidence counts, digest summaries, etc.).

---

10.5 **Integration with Layer-1 / 4A–4B validation harness**

10.5.1 The Layer-1 validation harness (4A/4B) MUST consume S5’s run-report record and/or S5 manifest/summary to:

* know whether 3B has a valid bundle and `_passed.flag` for this manifest;
* understand what kinds of checks S5 ran (structural, RNG, digest);
* see counts and, if needed, details of any WARNs or non-fatal anomalies (if supported in the future).

10.5.2 At a minimum, the harness MUST be able to derive:

* `3B.S5.status ∈ {"PASS","FAIL"}`
* `3B.S5.error_code` (if any)
* `3B.S5.evidence_file_count`
* `3B.S5.bundle_size_bytes` (if reported)
* references to S5 outputs (bundle/index/flag).

10.5.3 In its global decision logic, the harness MUST treat:

* 3B.S5 FAIL;
* missing bundle and/or flag;
* or any mismatch between recomputed bundle digest and `_passed.flag`

as a clear signal that 3B is **not** validated for this manifest, regardless of other segments’ statuses.

---

10.6 **Operational diagnostics & debugability**

10.6.1 On any FATAL S5 failure, S5 SHOULD log **diagnostic context** sufficient to diagnose the issue without immediately re-running in a debugger, e.g.:

* for S1 structural failures: include `merchant_id`, nature of mismatch (e.g. “no settlement row”).
* for S2 structure/contract issues: include `merchant_id`, expected vs actual edge counts.
* for S3 alias/blob/index issues: include `merchant_id`, `blob_offset_bytes`, `blob_length_bytes`, expected vs recomputed alias checksums.
* for RNG-accounting issues: include stream/substream IDs and expected vs actual draw/event counts.
* for digest mismatches: include artefact name and recorded vs recomputed digests.
* for bundle/index/flag issues: include offending `path` or index entry and a brief description.

10.6.2 If the engine supports a **debug / dry-run** mode for S5, that mode MUST:

* execute all phases A–E and compute the bundle digest in memory;
* produce logs and (optionally) a draft S5 manifest summarising findings;
* **not** publish `validation_bundle_3B` or `_passed.flag` at canonical locations.

Dry-run mode MUST be clearly indicated (e.g. `mode = "dry_run"`) in lifecycle logs and run-report so that operators do not confuse it with a committed validation state.

10.6.3 Any additional observability features (e.g. per-check or per-merchant debug dumps, sampled edge/alias comparisons) MAY be implemented provided they:

* are written as additional evidence files within the bundle and listed in `index.json`;
* or are written to separate diagnostic datasets that do not alter bundle/flag semantics;
* do not introduce non-determinism into S5 behaviour.

10.6.4 Where any aspect of this section conflicts with schemas or dictionary/registry entries for S5 artefacts, the **schemas and catalogues are authoritative**. This section MUST be updated in the next non-editorial revision to reflect the actual S5 contracts, while preserving the core requirements that:

* S5 is fully observable;
* S5 is straightforward to integrate into Layer-1 run reports;
* and S5 failures are clearly diagnosable and surfaced to operators and harnesses.

---

## 11. Performance & scalability *(Informative)*

11.1 **Workload character**

11.1.1 3B.S5 is a **control-plane validation state**, not a data-plane generator. It:

* reads and inspects S1–S4 artefacts and policies,
* reads RNG logs for S2,
* computes digests and runs structural checks,
* writes a relatively small bundle of JSON/Parquet-like evidence files.

11.1.2 The heavy lifting (big tables, spatial work, RNG draws) is done upstream in S1–S3. S5’s cost scales with:

* the **number of 3B artefacts** and their sizes (primarily S2/S3 catalogues and logs),
* the **number of checks** S5 chooses to run (e.g. per-merchant consistency checks vs sampled checks),
* the **size of the validation bundle** S5 emits (evidence file count and total bytes).

---

11.2 **Complexity & expected scale**

11.2.1 Let:

* `|V|` = number of virtual merchants (S1),
* `E_total` = total number of edges in `edge_catalogue_3B` for `{seed,fingerprint}`,
* `L_rng` = number of RNG events in S2’s RNG logs for the target streams/substreams,
* `F` = number of evidence files S5 writes into `validation_bundle_3B`.

11.2.2 Rough complexity:

* **Structural checks**:

  * S1: O(|V|) for single-pass checks over classification/settlement tables.
  * S2: O(E_total) for full row-count reconciliation; often implemented as grouped scans (can be batched/streamed).
  * S3: O(E_total) to relate alias index counts to S2 counts, plus O(|V|) for per-merchant checksums (depending on blob layout).
  * S4: O(|tests| + |V|) for contract sanity.

* **RNG accounting (S2)**:

  * O(L_rng) to walk S2’s RNG envelopes in the logs; in practice `L_rng ≈ c * E_total` for fixed c (few events per edge).

* **Bundle hashing**:

  * O(total bytes of evidence + index) to compute SHA-256 over the evidence file concatenation.

11.2.3 For realistic engine regimes (millions of edges, RNG logs of similar order, tens of evidence files), S5 remains linear in `E_total` and `L_rng` with small constants. It is much cheaper than S2’s jitter or S3’s alias construction.

---

11.3 **Latency considerations**

11.3.1 Latency components:

* Loading S1–S4 metadata and large tables (mostly S2 catalogue and S3 alias index/blob if fully scanned).
* Streaming through S2/S3 artefacts to compute counts/checks (can be done in a single pass per dataset).
* Streaming through RNG logs for S2 to do accounting.
* Writing a small number of evidence files and `index.json`, plus computing the bundle digest.

11.3.2 In most deployments:

* S5 latency is dominated by **I/O over S2/S3 artefacts and RNG logs**, not CPU.
* Hashing cost is proportional to evidence size, which should be modest relative to raw data tables (e.g. summaries rather than the entire catalogue re-mirrored).

11.3.3 If S5 becomes noticeably slow, likely causes include:

* evidence design that mirrors large data-plane tables rather than summarising them;
* RNG logs that are much larger than necessary (e.g. logging per-draw detail when per-event envelopes would suffice);
* re-reading large artefacts multiple times (e.g. separate scans for counts and digests) instead of combining checks into single passes.

---

11.4 **Memory model & parallelism**

11.4.1 A straightforward single-process implementation can:

* stream checks over S1–S3 artefacts without keeping the entire edge catalogue or alias blob in memory;
* hold only running aggregates (counts, digest contexts, small maps of per-merchant metrics);
* hold RNG counters per stream/substream, not per-event.

Memory footprint is then roughly:

* O(|V|) + O(#streams) + small overhead for evidence assembly.

11.4.2 For very large catalogues/logs, S5 SHOULD:

* ensure all structural checks and digest computations are implemented as **streaming operations** (no full in-memory materialisation of S2/S3 tables or RNG logs);
* avoid per-edge or per-event object graphs in memory; rely on streaming readers and incremental hashing.

11.4.3 Parallelism:

* S5 can be parallelised over **independent tasks**, such as:

  * per-merchant structural checks;
  * per-stream RNG accounting;
  * file-level hashing.

* Any parallelism MUST preserve determinism:

  * combine results using deterministic reductions;
  * ensure path lists and `index.json` entries are sorted deterministically before hashing;
  * avoid concurrency-induced non-determinism in evidence content.

---

11.5 **I/O patterns & bundle size**

11.5.1 Reads:

* S1–S4 tables:

  * S1: relatively small per-merchant tables;
  * S2: potentially large edge catalogue;
  * S3: alias index and blob (full scan only if necessary; partial scans may suffice if counts are summarised elsewhere);
  * S4: small JSON/table contracts.

* RNG logs:

  * log datasets sized in proportion to S2’s RNG usage (bounded by edge counts and jitter attempts).

* Policies and governance artefacts:

  * small files, negligible IO cost.

11.5.2 Writes:

* S5 evidence files: a handful of JSON/Parquet-like reports (structural checks, RNG accounting, digests, manifest).
* `index.json`: one file per manifest.
* `_passed.flag`: single-line text file.

11.5.3 Bundle size:

* Should be small relative to data-plane artefacts (on the order of KB–MB, not GBs), as evidence SHOULD be **summaries, not copies** of large datasets.
* Size is controllable via how much per-merchant/per-edge detail is included vs aggregated metrics or sampled diagnostics.

---

11.6 **SLOs & tuning knobs**

11.6.1 Reasonable SLOs for S5 in production might be:

* `P95(3b_s5_duration_seconds)` comfortably below S2/S3 runtimes for the same manifest (e.g. tens of seconds at most for very large runs, often much less).
* `3b_s5_rng_discrepancies_total` and structural failure counters at or near zero in steady-state production.

11.6.2 Tuning knobs:

* **Check granularity**:

  * For some structural checks, it may be acceptable to aggregate at per-merchant level instead of per-edge, reducing scan complexity and diagnostic output volume, while still surfacing any inconsistencies.

* **RNG logging detail**:

  * ensure RNG logs contain sufficient information for accounting but are not overly fine-grained (e.g. logging per-event envelopes instead of every primitive draw, if layer contracts allow).

* **Evidence verbosity**:

  * adjust how much per-merchant/edge-level detail is stored in S5 evidence vs aggregated metrics and limited samples.

11.6.3 Any tuning MUST preserve:

* completeness of checks as described in the S5 spec;
* determinism (no randomness in sampling without controlled design and clear exclusion from bundle hash, if ever allowed);
* HashGate semantics for `_passed.flag`.

---

11.7 **Testing & performance regression checks**

11.7.1 Performance/regression tests for S5 SHOULD include:

* manifests at the high end of expected S2/S3 size (large `E_total`, large RNG logs);
* manifests with many virtual merchants and extensive per-merchant diagnostics (if those are enabled in S5 evidence);
* boundary cases (e.g. no virtual merchants, minimal edge sets) to ensure S5 doesn’t degenerate unexpectedly.

11.7.2 Tests SHOULD verify that:

* S5 runtime scales approximately linearly with `E_total` and RNG log size for fixed check complexity;
* S5 memory footprint remains bounded (no accidental full materialisation of large tables/logs);
* rerunning S5 under identical inputs produces identical bundles, indices and flags.

11.7.3 Since this section is informative, concrete SLO values and hardware assumptions are deployment-specific. The binding requirements remain that S5:

* is deterministic and RNG-free;
* scales predictably with upstream artefact sizes;
* and remains “cheap enough” that it does not become the bottleneck relative to S1–S3 or 2B.

---

## 12. Change control & compatibility *(Binding)*

12.1 **Scope of change control**

12.1.1 This section governs all changes that affect **3B.S5 — Segment validation bundle & `_passed.flag`** and its artefacts, specifically:

* The **behaviour** of S5, including:

  * which checks it runs over S0–S4 and sealed artefacts;
  * how it assembles the validation bundle;
  * how it computes the bundle digest;
  * how it writes `_passed.flag`.

* The **schemas and catalogue entries** for S5-owned datasets:

  * `validation_bundle_3B` (directory);
  * `validation_bundle_index_3B` (`index.json`);
  * `_passed.flag`;
  * `s5_manifest_3B` / `s5_run_summary_3B` (if present);
  * any S5-specific evidence datasets that are registered.

12.1.2 This section does **not** govern:

* S0 contracts (`s0_gate_receipt_3B`, `sealed_inputs_3B`);
* S1–S4 contracts and artefacts (they’re inputs to S5);
* Layer-1 RNG governance or RNG log schemas (owned by layer-wide RNG spec);
* The Layer-1–wide validation harness (4A/4B) and any global `_passed.flagL1` — those are separate segments/states built on top of S5.

---

12.2 **Versioning of S5-related contracts**

12.2.1 All contracts that affect S5 MUST be versioned explicitly across:

* `schemas.layer1.yaml` and/or `schemas.3B.yaml` for:

  * `#/validation/validation_bundle_index_3B`;
  * `#/validation/passed_flag_3B`;
  * `#/validation/s5_manifest_3B` / `#/validation/s5_run_summary_3B` (if present);
  * schemas for any other S5 evidence files that are registered.

* `dataset_dictionary.layer1.3B.yaml` for:

  * `validation_bundle_3B`;
  * `validation_bundle_index_3B`;
  * `_passed.flag`;
  * `s5_manifest_3B` / `s5_run_summary_3B` (if present).

* `artefact_registry_3B.yaml` for:

  * manifest keys, ownership, retention, and consumers of S5 artefacts.

12.2.2 S5’s bundle-hashing law (which files are included and in what order) is a **Layer-1 HashGate contract**. Changes to:

* the **index schema**, or
* the **hashing process** (e.g. algorithm, ordering, or which files are included),

MUST be treated as changes to that contract and versioned accordingly (typically as a Layer-1 change, referenced by S5).

12.2.3 Implementations SHOULD follow a semantic-style scheme:

* **MAJOR** — incompatible/breaking changes to:

  * shapes of `index.json` or `_passed.flag`;
  * file-inclusion or hashing rules;
  * S5’s definition of what constitutes “3B PASS” (e.g. dropping classes of checks without replacing them).

* **MINOR** — backwards-compatible extensions, such as:

  * new optional evidence files or fields in S5 manifest/summary;
  * additional checks that, when they fail, are surfaced but do not change the meaning of PASS vs FAIL for existing criteria (or that are guarded by configuration).

* **PATCH** — non-semantic corrections:

  * doc / comment updates;
  * stricter validation that only rejects previously-invalid bundles;
  * minor refactors that preserve behaviour.

12.2.4 S5 MUST ensure (directly or via `s0_gate_receipt_3B.catalogue_versions`) that:

* the versions of `schemas.layer1.yaml` / `schemas.3B.yaml` that define S5 artefacts;
* `dataset_dictionary.layer1.3B.yaml`;
* `artefact_registry_3B.yaml`;

form a **compatible triplet** for S5. If they do not, S5 MUST fail with `E3B_S5_SCHEMA_PACK_MISMATCH` and MUST NOT emit bundle+flag.

---

12.3 **Backwards-compatible vs breaking changes**

12.3.1 The following changes are considered **backwards-compatible** (MINOR or PATCH) for S5, provided they respect all binding guarantees in §§4–9:

* Adding **optional evidence files** to `validation_bundle_3B`:

  * new JSON reports, additional metrics, extra diagnostics,
  * as long as they are included in `index.json` and do not alter the hashing law beyond adding new entries (the hash still covers all indexed files in sorted order).

* Adding **optional fields** to:

  * `s5_manifest_3B` (e.g. extra metrics, contract versions);
  * other evidence files, provided they remain schema-optional or have meaningful defaults.

* Introducing **additional checks** (structural or RNG) that:

  * only reject previously invalid configurations;
  * or are controlled by configuration and clearly documented as new, optional checks.

* Tightening **validation** of existing evidence (e.g. more consistency checks on digests) that catch previously undocumented bad states.

12.3.2 The following changes are **breaking** (MAJOR) for S5:

* Changing the **shape or semantics** of `validation_bundle_index_3B/index.json` such that existing HashGate verifiers can no longer interpret it correctly.

* Changing the **hashing law** that defines `_passed.flag`, for example:

  * switching from SHA-256 to a different algorithm without adding a new field;
  * changing which files are included in the hash without versioning;
  * altering the order (not ASCII path order) in substantive ways.

* Changing the **partition law** for S5 outputs (e.g. introducing `seed` or other partition keys).

* Redefining which checks are required for S5 PASS in a way that:

  * relaxes previously mandatory checks (e.g. dropping RNG-accounting or structural invariants) without a MAJOR bump;
  * or introduces stronger requirements that invalidate previously PASS’d bundles without a new manifest/contract.

* Removing or renaming required S5 evidence schemas (e.g. removing `s5_manifest_3B` if Layer-1 or 4A/4B assumes its presence as evidence) without updating consumers.

12.3.3 Any breaking change MUST:

* bump the relevant MAJOR version(s) (Layer-1 and/or 3B schemas);
* be accompanied by consistent updates to dictionary and registry;
* be documented in a changelog (S5-specific and/or 3B-global), clearly describing:

  * behavioural differences;
  * impact on existing manifests and bundles;
  * how HashGate verifiers and other consumers must update.

---

12.4 **Mixed-version environments**

12.4.1 A **mixed-version environment** arises when:

* historical S5 outputs (`validation_bundle_3B`, `validation_bundle_index_3B`, `_passed.flag`) exist for one contract version; and
* the engine/schemas/dictionary/registry now reflect a newer S5/Layer-1 contract version.

12.4.2 S5 is responsible only for emitting outputs under the **current** contract version. It MUST:

* write new bundles+flags according to the current schemas and hashing law;
* NOT reinterpret or rewrite historic S5 artefacts in place as if they conformed to the new contract.

12.4.3 Reading and understanding historic bundles and flags under older contracts is the responsibility of:

* version-aware HashGate/validation tools;
* migration/compatibility utilities;
* up-stack components that explicitly handle multiple versions.

S5 MUST NOT silently treat old bundles as if they followed the new rules.

12.4.4 If S5 is re-run for a `manifest_fingerprint` that already has S5 outputs but:

* existing bundles do not validate against current schemas; or
* recomputed bundle digest differs from `_passed.flag.sha256_hex` under the same identity and input artefacts,

S5 MUST:

* treat this as an **inconsistent rewrite / environment drift** (`E3B_S5_OUTPUT_INCONSISTENT_REWRITE`);
* fail and MUST NOT overwrite the existing artefacts.

Operators MUST then:

* either treat the existing bundle as historical under its original contract and avoid re-running S5 under the new contract for that fingerprint; or
* compute a new manifest (new `manifest_fingerprint`) and re-run S0–S5 under the updated contracts.

---

12.5 **Migration & deprecation**

12.5.1 When introducing new S5 evidence or checks that are expected to become **mandatory**, the recommended pattern is:

1. **MINOR phase (optional)**:

   * define schemas for new evidence files or fields;
   * include them in bundles and `index.json`;
   * ensure consumers (4A/4B, HashGate tooling) can consume them but still function if they’re absent in old bundles.

2. **MAJOR phase (required)**:

   * make the new evidence/checks mandatory for S5 PASS;
   * adjust schemas to mark fields as required if appropriate;
   * update tooling to assume their presence.

12.5.2 Deprecating legacy evidence fields or checks SHOULD follow a similar two-step approach:

* Step 1 (MINOR): mark them as deprecated in docs/schemas, stop relying on them in new tooling, but still emit them for compatibility.
* Step 2 (MAJOR): remove or repurpose them only after downstream consumers have been updated.

12.5.3 If you need to evolve HashGate semantics globally (e.g. adding a second hash algorithm, or adding versioned hashing profiles), do so via:

* extended schemas for index and flag (e.g. optional `algo` field, or an extended flag format);
* clear documentation of which algorithm/profile applies;
* compatibility paths that allow older manifests to be recognised as valid under their original laws.

---

12.6 **Compatibility with upstream segments & layer-wide harness**

12.6.1 S5 must remain compatible with **upstream segments**:

* It cannot change S1–S4 semantics or schemas;
* It must adapt to upstream MAJOR/MINOR changes by updating its checks or evidence logic, not by mutating upstream data.

12.6.2 When upstream contracts change (e.g. new fields in `edge_catalogue_3B`, new components in `edge_universe_hash_3B`, new routing/validation policy fields):

* S5 MAY add checks and evidence that leverage these new fields;
* S5 MUST keep required checks aligned with upstream behaviour;
* any change that makes previously valid S1–S4 outputs fail S5’s required checks without a manifest/contract update MUST be treated as a breaking change and versioned accordingly.

12.6.3 S5 must also remain compatible with **layer-wide harnesses** (4A, 4B):

* If 4A/4B relies on specific S5 evidence (e.g. `s5_manifest_3B` fields), any change to those fields must be coordinated;
* S5 contract changes that affect how `_passed.flag` is interpreted MUST be reflected in 4A/4B code and documentation.

---

12.7 **Change documentation & review**

12.7.1 Any non-trivial change to S5 behaviour, schemas, or catalogue entries MUST be:

* recorded in a changelog (e.g. `CHANGELOG.3B.S5.md` or shared `CHANGELOG.3B.md` with S5-specific entries);
* associated with corresponding schema/dictionary/registry version changes;
* documented with:

  * what changed (checks, evidence shape, hashing law, flag semantics);
  * whether the change is MAJOR/MINOR/PATCH;
  * how it affects existing bundles and manifests;
  * which downstream components need to be updated.

12.7.2 Before deploying S5-impacting changes, implementers SHOULD:

* run regression tests verifying:

  * S5 PASS/FAIL behaviour is as expected for representative manifests;
  * S5 remains deterministic (repeated runs with same inputs produce identical bundles + flags);
  * existing valid bundles produced under the new contracts can be verified by HashGate tooling;
  * upstream S1–S4 and downstream harnesses (4A/4B) continue to work correctly.

12.7.3 Where this section conflicts with `schemas.layer1.yaml`, `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, or `artefact_registry_3B.yaml`, those artefacts SHALL be treated as **authoritative**. This section MUST be updated in the next non-editorial revision to reflect the S5 contracts actually in force, while preserving the core guarantees:

* S5 is deterministic and RNG-free;
* S5 adheres to the global HashGate law for bundles and flags;
* S5 provides a stable and trustworthy gating mechanism for 3B in the overall Layer-1 architecture.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

> This appendix is descriptive only. If anything here conflicts with a Binding section or with JSON-Schema / dictionary / registry entries, those authoritative sources win.

---

### 13.1 Identity & governance

* **`seed`**
  Layer-1 Philox seed for the run. Part of S5’s run identity triple, but not used to partition S5 outputs.

* **`parameter_hash`**
  Tuple-hash over the governed Layer-1/3B parameter set. Echoed in S5 manifest/summary; must match S0’s value.

* **`manifest_fingerprint`**
  Hash of the Layer-1 manifest (ingress, artefacts, code, policies). Primary partition key for S5 outputs:
  `validation/manifest_fingerprint={manifest_fingerprint}/…`.

* **`run_id`**
  Optional, opaque identifier for a specific execution of S5 under a given identity triple. Used only for logging / run-report, never for hashing or partitioning.

---

### 13.2 Sets, counts & per-merchant notation

* **`V`**
  Virtual merchant set, as defined by S1 (e.g. those with `virtual_classification_3B.is_virtual = 1`).

* **`E_m`**
  Set (or ordered list) of edges associated with merchant `m` in `edge_catalogue_3B`.

* **`n_m`**
  Edge count for merchant `m`:
  `n_m = |E_m| = edge_count_total(m)` in `edge_catalogue_index_3B`.

* **`E_total`**
  Total number of edges in the 3B edge universe for `{seed,fingerprint}`:
  `E_total = Σ₍m∈V_edge₎ n_m`,
  where `V_edge` is the set of merchants that have edges in S2.

* **`L_rng`**
  Number of RNG events in S2’s RNG logs for the S2 module/streams relevant to edge placement/jitter.

* **`F`**
  Number of evidence files in `validation_bundle_3B` (excluding `_passed.flag`), i.e. the length of `validation_bundle_index_3B.files`.

---

### 13.3 RNG & accounting notation

* **`rng_audit_log` / `rng_trace_log`**
  Layer-1 RNG log datasets capturing per-module and per-event RNG usage (envelopes, counters, draws/blocks), as defined in `schemas.layer1.yaml`.

* **`rng_stream_id` / `substream_label`**
  Logical identifiers for specific RNG streams/substreams (e.g. those used by 3B.S2 for edge jitter). S5 doesn’t use RNG but checks these IDs in logs.

* **`draws` / `blocks`**
  Fields in RNG envelopes indicating the number of Philox draws and blocks requested per event.

* **RNG accounting**
  The process of comparing expected RNG usage (from S2 spec + edge counts) against observed RNG logs to ensure consistency and budget compliance.

---

### 13.4 Digest & hashing notation

* **`sha256_hex`**
  Lower-case hex encoding of a SHA-256 digest (64 hex chars). Used for per-file digests in `index.json` and for bundle digests.

* **`bundle_sha256`**
  The SHA-256 digest of the entire 3B validation bundle, computed over the concatenation of bytes of all evidence files listed in `validation_bundle_index_3B.files` in ASCII-sorted `path` order.

* **`edge_catalogue_digest_global`**
  Global digest for `edge_catalogue_3B` (as defined by S2), often echoed in S3/S4/S5 evidence.

* **`edge_alias_blob_sha256_hex` / `edge_alias_index_sha256_hex`**
  Digests for `edge_alias_blob_3B` and `edge_alias_index_3B` recorded in `edge_universe_hash_3B` and verified in S5.

* **`edge_universe_hash`**
  Virtual edge universe hash computed by S3 and recorded in `edge_universe_hash_3B`. S5 re-verifies its component digests but does not change its value.

---

### 13.5 Bundle, index & flag notation

* **`validation_bundle_3B`**
  S5 egress. Directory under
  `data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/`
  containing 3B validation evidence, `index.json` and `_passed.flag`.

* **`validation_bundle_index_3B`**
  S5 egress. `index.json` inside the bundle listing each evidence file with its relative `path` and `sha256_hex`.

* **`_passed.flag`**
  S5 egress. Single-line text file at the bundle root:

  ```text
  sha256_hex = <bundle_sha256>
  ```

  encoding the 3B bundle digest. Downstream components enforce “No 3B PASS → No read of 3B artefacts” via this flag.

* **`s5_manifest_3B`**
  Optional S5 evidence file summarising identity, contracts, digests and check outcomes for human/automated inspection.

---

### 13.6 Error & status codes (S5)

* **`E3B_S5_*`**
  Namespace for S5 canonical error codes, e.g.:

  * `E3B_S5_IDENTITY_MISMATCH`
  * `E3B_S5_REQUIRED_INPUT_NOT_SEALED`
  * `E3B_S5_S1_CONTRACT_VIOLATION`
  * `E3B_S5_S2_CONTRACT_VIOLATION`
  * `E3B_S5_S3_CONTRACT_VIOLATION`
  * `E3B_S5_S4_CONTRACT_VIOLATION`
  * `E3B_S5_RNG_ACCOUNTING_MISMATCH`
  * `E3B_S5_DIGEST_COMPONENT_MISMATCH`
  * `E3B_S5_UNIVERSE_HASH_MISMATCH`
  * `E3B_S5_BUNDLE_INDEX_SCHEMA_VIOLATION`
  * `E3B_S5_FLAG_DIGEST_MISMATCH`
  * `E3B_S5_OUTPUT_INCONSISTENT_REWRITE`
  * `E3B_S5_RNG_USED`
  * `E3B_S5_NONDETERMINISTIC_OUTPUT`

  Full semantics are defined in §9.

* **`status ∈ {"PASS","FAIL"}`**
  Run-level status for S5, used in logs and run-report.

* **`severity ∈ {"FATAL","WARN"}`**
  Error severity attached to `E3B_S5_*` codes. In the current spec, all S5 errors are FATAL.

---

### 13.7 Miscellaneous abbreviations

* **CDN** — Content Delivery Network (virtual edge network).
* **FK** — Foreign key (join key across datasets).
* **IO** — Input/Output (filesystem / object-store operations).
* **RNG** — Random Number Generator (Philox2x64-10 across Layer-1; S5 is RNG-free and audits RNG logs only).
* **SLO** — Service Level Objective (latency / reliability target).
* **tzid** — Time zone identifier (IANA tzid, e.g. `Europe/London`, `America/New_York`).

---

### 13.8 Cross-reference

Authoritative definitions for the symbols and concepts above are found in:

* **Layer-1 contracts**

  * `schemas.layer1.yaml` — RNG envelopes, numeric policy, validation bundle and flag schemas.
  * `schemas.ingress.layer1.yaml` — shared ingress artefact shapes.

* **3B contracts & state specs**

  * `schemas.3B.yaml` — shapes for S1–S5 artefacts.
  * `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` — dataset IDs, paths, partitioning, ownership.
  * S1–S4 specs — virtual classification/settlement, edge universe, alias/universe hash, routing & validation contracts.

This appendix is intended as a vocabulary / symbol reference when reading and implementing **3B.S5 — Segment validation bundle & `_passed.flag`**.

---
