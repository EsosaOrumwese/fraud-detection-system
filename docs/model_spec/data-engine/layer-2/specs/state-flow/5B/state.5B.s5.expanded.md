# 5B.S5 — Validation bundle & HashGate (Layer-2 / Segment 5B)

## 1. Purpose & scope *(Binding)*

1.1 **Role of 5B.S5 in Segment 5B**
5B.S5 is the **RNG-free validation and HashGate state** for Layer-2 / Segment 5B.
For each `manifest_fingerprint` (and all `(parameter_hash, scenario_id, seed)` runs underneath it), S5:

* re-validates the **structural and probabilistic invariants** of 5B.S0–S4, and
* produces a **fingerprint-scoped validation bundle** (`validation_bundle_5B`) and a single ASCII `_passed.flag_5B` that together form the **only authoritative “5B PASS” signal** for downstream consumers.

S5 does not generate any new arrival events; it decides whether the arrival world produced by 5B is acceptable and, if so, seals it.

---

1.2 **In-scope responsibilities**
Within Segment 5B, S5 is responsible for:

* **Replaying and checking 5B invariants**

  * S0: gate + `sealed_inputs_5B` consistency (upstream HashGates, sealed universe).
  * S1–S3: identity, domain, and arithmetic for time grid, realised intensities and bucket-level counts.
  * S4:

    * exact count conservation: S4 arrivals ≡ S3 bucket counts,
    * time grid & civil-time correctness vs 2A,
    * routing correctness vs 2B/3A/3B universes and policies,
    * schema/partition/PK discipline for `s4_arrival_events_5B`.
  * RNG accounting: draws/blocks for S2, S3 and S4 match their laws and `rng_trace_log`.

* **Assembling the 5B validation bundle**

  * Selecting the evidence artefacts (summaries, metrics, receipts, RNG accounting, sample checks) for the `manifest_fingerprint`.
  * Writing a canonical `index.json` with per-file `sha256_hex` and a stable ordering.
  * Ensuring the bundle is self-consistent and sufficient to replay the checks above.

* **Computing and publishing the HashGate**

  * Computing a **single bundle digest** from the indexed files using a fixed hashing law.
  * Writing `_passed.flag_5B` containing exactly that digest in canonical form.
  * Ensuring that, for a given `manifest_fingerprint`, there is at most one logically valid bundle/flag pair in the expected location.

* **Exposing a 5B-level PASS/FAIL decision**

  * Emitting a run-report record for S5 that records `status`, `error_code`, and key metrics for the `manifest_fingerprint`.
  * Making that decision visible to orchestration and to downstream components (6A/6B, ingestion) via the bundle/flag and registry/catalogue entries.

---

1.3 **Out-of-scope responsibilities**
To keep responsibilities clean and aligned with upstream design, S5 explicitly **must not**:

* modify or regenerate:

  * any S0–S4 outputs (including `s4_arrival_events_5B`),
  * any upstream Layer-1/Layer-2 artefacts (1A–3B, 5A).
* consume RNG or introduce any new randomness — S5 is strictly RNG-free.
* change arrival semantics (counts, timestamps, routing decisions) or “fix up” events; any violation detected during validation MUST result in FAIL, not silent correction.
* act as a consumer-facing data source; downstream components MUST read arrivals from `s4_arrival_events_5B`, not from S5’s internal evidence tables.

Any behaviour outside validation, bundling and gate publication is out of scope for this state.

---

1.4 **Position in the wider engine**
Within Segment 5B:

* S0–S4 **construct** the arrival world (gated inputs → grid/grouping → realised intensity → counts → arrival events).
* S5 **audits and seals** that world for a given `manifest_fingerprint`.

Within the broader engine:

* `_passed.flag_5B` is the **Layer-2 arrival HashGate**:

  * Layer-3 / Segment 6A–6B and any enterprise ingestion MUST gate on a **verified** `_passed.flag_5B` before treating `s4_arrival_events_5B` as authoritative.
  * A S4 PASS alone is **not sufficient**; only the combination of `validation_bundle_5B` + `_passed.flag_5B` produced by S5 constitutes a 5B-level PASS.

This section binds S5 to that narrow but critical role: it is the final arbiter of 5B correctness and the single point that turns a collection of 5B runs into a sealed, replayable arrival layer for the rest of the system.

---

## 2. Preconditions & dependencies *(Binding)*

2.1 **Scope of an S5 run**
S5 operates at the **fingerprint** level:

* A single S5 run covers one `manifest_fingerprint = mf` and all 5B runs beneath it:

  * all `parameter_hash` values present for that `mf` in S2/S3/S4,
  * all `scenario_id` and `seed` combinations for those `(mf, ph)` pairs.

S5 MUST NOT run in a way that only partially covers a fingerprint (e.g. only some seeds or scenarios) and then claim 5B PASS for that fingerprint.

---

2.2 **Required upstream HashGates (segments 1A–3B, 5A)**

For the `manifest_fingerprint` under validation, S5 assumes that **all mandatory upstream segments are already gated**:

* `_passed.flag_1A`
* `_passed.flag_1B`
* `_passed.flag_2A`
* `_passed.flag_2B`
* `_passed.flag_3A`
* `_passed.flag_3B`
* `_passed.flag_5A`

Precondition:

* S0 MUST already have verified these flags for `mf` and recorded their status in `s0_gate_receipt_5B`.
* S5 MUST see that **every mandatory upstream segment** is marked as PASS (not MISSING/FAIL) in `s0_gate_receipt_5B` before proceeding.

If any mandatory upstream segment is not PASS for `mf`, S5 MUST NOT attempt to validate 5B and MUST fail fast.

---

2.3 **5B-local upstream states (S0–S4)**

For the same `manifest_fingerprint`, S5 requires that:

* **5B.S0 (gate & sealed inputs)**

  * `s0_gate_receipt_5B` and `sealed_inputs_5B` exist and are schema-valid.
  * `sealed_inputs_5B` contains all 5B and upstream artefacts that S5 intends to read, with appropriate roles and statuses.
  * The 5B run-report for S0 (if present) indicates `status="PASS"` for `mf`.

* **5B.S1–S3 (grid, realised intensity, bucket counts)**

  * `s1_time_grid_5B`, `s1_grouping_5B` exist and are schema-valid for all `(ph, sid)` combinations encountered under `mf`.
  * `s2_realised_intensity_5B` exists and is schema-valid for all `(ph, sid, seed)` combinations under `mf` that appear in S3/S4.
  * `s3_bucket_counts_5B` exists and is schema-valid for all `(ph, sid, seed)` combinations under `mf`.
  * Their catalog entries and partitioning obey the identity law established in the 5B contracts.

* **5B.S4 (arrival events)**

  * `s4_arrival_events_5B` exists for every `(ph, sid, seed)` that appears in `s3_bucket_counts_5B` for `mf`.
  * It conforms to `schemas.5B.yaml#/egress/s4_arrival_events_5B` at the schema level.
  * The 5B run-report for S4 (if present) indicates `status="PASS"` for each `(ph, mf, sid, seed)` that S5 will consider.

If any of these S0–S4 preconditions fails, S5 MUST report a suitable S5-specific error and abort.

---

2.4 **Catalogue & registry preconditions**

S5 is a **catalogue-driven** state. Before S5 runs for `mf`, the following MUST hold:

* The Layer-2 dataset dictionary (`dataset_dictionary.layer2.5B.yaml`) includes entries for all relevant 5B datasets:

  * S0–S4 surfaces,
  * S5 validation artefacts (to be written).
* The 5B artefact registry (`artefact_registry_5B.yaml`) includes:

  * definitions for S0–S4 artefacts,
  * versioning and dependency metadata for `arrival_events_5B`,
  * a slot for S5’s `validation_bundle_5B` and `_passed.flag_5B`.

S5 MUST discover:

* the set of `(parameter_hash, scenario_id, seed)` to validate for `mf`, and
* the list of physical files constituting S3/S4 and RNG logs for `mf`,

**via the catalogue/registry**, NOT by ad-hoc directory scans. Any required dataset that is not discoverable via catalogue and `sealed_inputs_5B` is considered missing.

---

2.5 **Access to RNG logs & validation schemas**

Since S5 checks RNG accounting and bundle structure, the following MUST be available and schema-valid for `mf`:

* **RNG infrastructure:**

  * layer-wide `rng_audit_log`, `rng_trace_log` entries covering all runs of S2, S3, S4 under `mf`,
  * RNG event tables for S2, S3, S4 families (their IDs listed in `sealed_inputs_5B`).

* **Validation schema packs:**

  * `schemas.layer1.yaml` — for RNG envelope & trace schemas, and any shared validation defs.
  * `schemas.layer2.yaml` — for layer-2 validation bundle/index/report/issue-table anchors.
  * `schemas.5B.yaml` — for any 5B-specific bundle/receipt/report anchors used by S5.

If these schemas or logs are missing or invalid, S5 cannot complete its checks and MUST fail.

---

2.6 **Environment & non-dependencies**

Environment assumptions:

* S5 runs under the same filesystem / object-store conventions as other segment validators (1B S9, 2A S5, 2B S8, 3A S7, 3B S5), i.e.:

  * predictable base prefix for `data/layer2/5B/…`,
  * read access to 5B and upstream data paths for `mf`,
  * write access to `data/layer2/5B/validation/fingerprint={manifest_fingerprint}/`.

Non-dependencies (for clarity):

* S5 does **not** depend on any Layer-3 (6A/6B) artefacts, model outputs, or enterprise ingestion topics. Those components depend on S5’s outputs, not vice versa.

If any of the above preconditions are not satisfied for a `manifest_fingerprint`, S5 MUST NOT emit a PASS bundle/flag for that fingerprint.

---

## 3. Inputs & authority boundaries *(Binding)*

3.1 **Inputs from within Segment 5B**

S5 MAY only read 5B-owned artefacts that are explicitly listed in `sealed_inputs_5B` with `owner_segment = "5B"` and appropriate role. In practice these are:

* **From S0 — gate & sealed universe**

  * `s0_gate_receipt_5B`

    * Run/world identity for `manifest_fingerprint` and upstream HashGate status.
    * S5 uses this as the *single source of truth* for which upstream segments are PASS/MISSING/FAIL.
  * `sealed_inputs_5B`

    * Full inventory of artefacts 5B is allowed to read.
    * S5 MUST treat this as a hard whitelist: if a dataset is not listed, S5 MUST NOT use it as evidence.

* **From S1 — time grid & grouping**

  * `s1_time_grid_5B`

    * Canonical bucket definitions for each `(parameter_hash, scenario_id)` under `mf`.
    * S5 uses this to check that all S3/S4 buckets align to the same grid.
  * `s1_grouping_5B`

    * Optional; used only to sanity-check that S2/S3/S4 did not step outside the declared grouping.

* **From S2 — realised intensities**

  * `s2_realised_intensity_5B`

    * S5 uses this only for consistency checks (e.g. that S3/S4 work over the same domain), not for any numerical re-computation.

* **From S3 — bucket-level counts**

  * `s3_bucket_counts_5B`

    * **Authoritative** bucket-domain and counts `N(e,b)` for `(parameter_hash, scenario_id, seed)` under `mf`.
    * S5 uses this to check count conservation vs S4 and to derive expected RNG usage for S3/S4.

* **From S4 — arrival events**

  * `s4_arrival_events_5B`

    * Authoritative arrival event dataset for each `(ph, mf, sid, seed)`.
    * S5 uses this to verify:

      * count equality vs `s3_bucket_counts_5B`,
      * time window correctness vs `s1_time_grid_5B` and 2A surfaces,
      * routing correctness vs 2B/3A/3B.

S5 MUST NOT modify, rewrite, or “fix” any of these datasets; they are read-only evidence.

---

3.2 **Inputs from upstream segments & RNG infrastructure**

Via `sealed_inputs_5B`, S5 MAY read the following upstream artefact classes:

* **Layer-1 geometry & time**

  * 1B: `site_locations` — used only to confirm that S4’s `site_id` references valid outlets under `(mf, seed)`.
  * 2A: `site_timezones`, `tz_timetable_cache` — used to verify that `ts_utc` and local timestamps produced by S4 obey 2A’s civil-time semantics.

* **Layer-1 routing & zone/virtual universes**

  * 2B routing surfaces:

    * `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s4_group_weights`, `route_rng_policy_v1`, alias layout policy.
    * S5 uses these to check that S4’s physical routing is compatible with the configured routing fabric (no out-of-universe sites).
  * 3A zone surfaces:

    * `zone_alloc`, `zone_alloc_universe_hash`.
    * S5 uses these to confirm that arrivals respect zone allocation invariants and that any echoed routing hash is correct.
  * 3B virtual surfaces:

    * `virtual_classification_3B`, `virtual_settlement_3B`,
      `edge_catalogue_3B`, `edge_alias_index_3B`, `edge_alias_blob_3B`,
      `edge_universe_hash_3B`, `virtual_routing_policy_3B`.
    * S5 uses these to verify that virtual arrivals reference valid edges and follow virtual routing semantics.

* **5A intensity surfaces (for context)**

  * 5A λ surfaces (e.g. `merchant_zone_scenario_local_5A` / `merchant_zone_scenario_utc_5A`) and 5A validation artefacts.
  * S5 MAY use these for domain and sanity checks (e.g. bucket coverage), but NOT to re-drive Poisson draws or to re-compute λ.

* **RNG infrastructure**

  * Layer-wide `rng_audit_log`, `rng_trace_log`.
  * RNG event tables for 5B.S2, 5B.S3, 5B.S4 (families listed in `sealed_inputs_5B`).
  * S5 uses these solely to verify RNG accounting (draws/blocks vs expected) and counter monotonicity.

S5 MUST NOT:

* call any upstream code paths that generate new data,
* re-derive alternative routing or timing behaviour,
* treat upstream artefacts not present in `sealed_inputs_5B` as in-scope.

---

3.3 **S5 configuration inputs**

S5 MAY depend on a small set of 5B-owned configuration artefacts, for example:

* **Validation policy for 5B** — which invariants must be checked, and with what severity/thresholds (e.g. whether certain soft anomalies are warnings vs hard fails).
* **Bundle layout policy** — which evidence files to include in `validation_bundle_5B`, naming conventions, and the bundled index schema variant.

These configs:

* MUST themselves be listed in `sealed_inputs_5B`,
* MUST NOT alter the fundamental acceptance criteria of upstream segments (1A–3B, 5A), only how 5B verifies its own work and packages evidence.

---

3.4 **Authority boundaries**

To keep responsibilities sharp:

* **Upstream segments (1A–3B, 5A)**

  * Remain the sole authorities for their own invariants and PASSES.
  * S5 may *echo* their status and use their artefacts for cross-checks, but it does not revalidate upstream segments in full; it only checks that 5B has respected their contracts.

* **5B.S0–S4**

  * Own construction of the 5B arrival world (gating, grid, λ_realised, counts, events).
  * S5 may **only**:

    * read their outputs,
    * re-run validations against those outputs,
    * decide PASS/FAIL for 5B based on those checks.

* **5B.S5**

  * Is the **sole authority** for the 5B-level PASS/FAIL and for the contents of `validation_bundle_5B` + `_passed.flag_5B`.
  * MUST NOT write or modify any datasets other than its own validation artefacts (bundle, flag, and any S5-specific reports).

---

3.5 **Explicit non-inputs**

S5 MUST NOT directly depend on:

* any Layer-3 / 6A / 6B artefacts (models, flows, labels),
* any enterprise ingestion topics or downstream warehouses,
* any ad-hoc filesystem scans beyond what the catalogue and `sealed_inputs_5B` describe.

If such artefacts exist, they are consumers of S5, not inputs into it.

---

## 4. Outputs (artefacts) & identity *(Binding)*

4.1 **List of S5-owned artefacts**

For each `manifest_fingerprint = mf`, 5B.S5 owns exactly the following artefacts:

1. **`validation_bundle_5B`** — a *directory* of evidence files under a fingerprint-scoped path, containing at least:

   * a canonical `index.json` describing all bundle members (logical IDs, relative paths, per-file `sha256_hex`, roles), and
   * one or more evidence files (reports, receipts, RNG summaries, etc.) referenced by that index.

2. **`_passed.flag_5B`** — an ASCII text file at the root of the bundle directory, containing the **canonical digest** of `validation_bundle_5B` as computed by S5’s hash law.

3. **(Optional) S5-specific summary / receipt objects**
   If you choose to materialise a separate 5B-level summary or receipt (e.g. `s5_receipt_5B.json`), it MUST:

   * live inside `validation_bundle_5B`, and
   * be included in `index.json` like any other evidence file.

S5 MUST NOT write any other datasets or tables; its sole job is to produce the bundle + flag (plus any internal summary files inside the bundle).

---

4.2 **Identity scope of S5 artefacts**

All S5 artefacts are **fingerprint-scoped**:

* They are keyed by **`manifest_fingerprint` only**.
* They MUST aggregate and cover:

  * all `parameter_hash` values,
  * all `scenario_id`, and
  * all `seed` runs
    that belong to 5B.S0–S4 for that `mf`.

In particular:

* S5 artefacts MUST **not** be partitioned by `seed`, `parameter_hash` or `scenario_id` in their paths. Those identities appear *inside* bundle metadata, not in the directory layout.
* A single pair `(validation_bundle_5B, _passed.flag_5B)` represents the entire 5B status for `mf`.

---

4.3 **Directory layout & paths**

For a given `manifest_fingerprint = mf`, S5 MUST write its artefacts under a single directory of the form:

```text
data/layer2/5B/validation/fingerprint={manifest_fingerprint}/
```

Within this directory:

* `index.json` (required)

  * Canonical index of bundle members (relative paths, hashes, roles).
* One or more evidence files (required)

  * e.g. `validation_report_5B.json`, `validation_issue_table_5B.parquet`, `rng_accounting_5B.json`, etc.
* `_passed.flag_5B` (required)

  * A small ASCII file at the **root of this directory**, not referenced by `index.json`, containing the bundle digest in a fixed `key = value` format (to be specified in §6/§7).

No S5 evidence file may live outside this `fingerprint={mf}` directory, and `_passed.flag_5B` MUST NOT appear in any other location.

---

4.4 **Logical identity & uniqueness**

For each `manifest_fingerprint`:

* There MUST be **at most one** logically valid `validation_bundle_5B` + `_passed.flag_5B` pair per `5B_spec_version`.
* If S5 is re-run for the same `mf` and same `5B_spec_version`:

  * either the bundle and flag are **byte-identical** to the existing ones (idempotent rerun), or
  * the rerun is treated as a conflict and MUST NOT silently overwrite the previous bundle/flag.

The **logical identity** of S5 outputs is:

* `("5B.S5", manifest_fingerprint, 5B_spec_version)`

and S5 MUST ensure that:

* `index.json` and `_passed.flag_5B` both encode enough metadata (including `manifest_fingerprint` and `5B_spec_version`) for downstream systems to unambiguously tie the bundle to the correct world and spec version.

No other identity tokens (e.g. `seed`, `scenario_id`, `run_id`) may influence the on-disk location of S5 artefacts; they may only appear inside the bundle contents as descriptive metadata.

---

## 5. Bundle shapes, schema anchors & catalogue links *(Binding)*

5.1 **Schema packs used by S5**
S5 reuses the existing **Layer-2 validation schema pack** and, optionally, the 5B segment pack:

* **Layer-2 pack (shared)**

  * `schemas.layer2.yaml`
  * MUST define the generic validation shapes for 5B:

    * `validation_bundle_index_5B`
    * `validation_report_5B`
    * `validation_issue_table_5B`
    * `passed_flag_5B`

* **5B segment pack (optional, for extra receipts)**

  * `schemas.5B.yaml`
  * MAY define 5B-specific validation artefacts such as:

    * `validation/s5_receipt_5B` (structured summary of 5B checks for `mf`)

S5 MUST NOT introduce additional schema packs; any new 5B validation structures must be added to one of the two packs above.

---

5.2 **Bundle index schema (required)**

The index of the bundle MUST be anchored at:

* `schemas.layer2.yaml#/validation/validation_bundle_index_5B`

This anchor MUST define a **strict JSON object** whose role is to:

* list all evidence files included in `validation_bundle_5B` as relative paths (paths are relative to the `fingerprint={mf}` validation directory), and
* provide, for each file:

  * a logical identifier (e.g. `logical_id` or `role`),
  * its relative `path`,
  * its `sha256_hex` digest,
  * its `schema_ref` (when applicable).

Constraints:

* `columns_strict: true` / strict properties for this schema.
* The list of entries MUST be sorted in **ASCII-lexicographic order of `path`**; S5’s hash law later depends on this order.
* `_passed.flag_5B` MUST NOT appear as a member in this index.

---

5.3 **Report, issue table & flag schemas**

5.3.1 **Validation report (required)**
S5 MUST anchor a human/machine-readable report at:

* `schemas.layer2.yaml#/validation/validation_report_5B`

This schema describes a single JSON object that at least records:

* `manifest_fingerprint`
* `5B_spec_version`
* summary of check families (S0–S4, RNG, routing, time, counts)
* overall `status ∈ {"PASS","FAIL"}`
* high-level metrics (e.g. number of seeds, scenarios, arrivals checked)

5.3.2 **Issue table (optional)**
If S5 emits a structured issue table, it MUST be anchored at:

* `schemas.layer2.yaml#/validation/validation_issue_table_5B`

This anchor defines a **strict table** (e.g. Parquet) with columns such as:

* `manifest_fingerprint`
* `check_id`
* `issue_code`
* `severity`
* optional references to `parameter_hash`, `scenario_id`, `seed`, `merchant_id`, `bucket_index`, `site_id`, `edge_id`
* `details` / `details_json`

If no issues exist, S5 MAY omit this dataset or write an empty table; in both cases the index MUST reflect what was actually written.

5.3.3 **Passed flag schema (required)**
The `_passed.flag_5B` file MUST conform to:

* `schemas.layer2.yaml#/validation/passed_flag_5B`

This anchor describes a tiny ASCII text file with a single key–value line, for example:

```text
sha256_hex = <64 lowercase hex chars>
```

where `<hex>` is the digest computed over the bundle contents (hash law defined later). S5 MUST NOT embed any other content or whitespace beyond what the schema permits.

5.3.4 **Optional 5B receipt**
If implemented, a 5B-specific receipt MUST be anchored at:

* `schemas.5B.yaml#/validation/s5_receipt_5B`

This would typically summarise:

* `manifest_fingerprint`
* `5B_spec_version`
* list of seeds / scenarios included
* pointers (by `logical_id`) to key evidence files in the bundle

It remains purely **informative**; the index + flag are the binding HashGate.

---

5.4 **Catalogue entries in `dataset_dictionary.layer2.5B.yaml`**

The Layer-2 dataset dictionary MUST include entries for each S5 artefact:

1. **Bundle index**

   * `id: "validation_bundle_index_5B"`
   * `owner_layer: 2`
   * `owner_segment: "5B"`
   * `schema_ref: "schemas.layer2.yaml#/validation/validation_bundle_index_5B"`
   * `path: "data/layer2/5B/validation/fingerprint={manifest_fingerprint}/index.json"`
   * `partitioning.keys: ["manifest_fingerprint"]`
   * `status: "active"`
   * `final_in_segment: true`
   * `final_in_layer: true`

2. **Validation report**

   * `id: "validation_report_5B"`
   * `schema_ref: "schemas.layer2.yaml#/validation/validation_report_5B"`
   * `path: "data/layer2/5B/validation/fingerprint={manifest_fingerprint}/validation_report_5B.json"`
   * `partitioning.keys: ["manifest_fingerprint"]`
   * `status: "active"`

3. **Validation issue table`** (if implemented)

   * `id: "validation_issue_table_5B"`
   * `schema_ref: "schemas.layer2.yaml#/validation/validation_issue_table_5B"`
   * `path: "data/layer2/5B/validation/fingerprint={manifest_fingerprint}/validation_issue_table_5B.parquet"`
   * `partitioning.keys: ["manifest_fingerprint"]`
   * `status: "active"`

4. **Passed flag**

   * `id: "validation_passed_flag_5B"`
   * `schema_ref: "schemas.layer2.yaml#/validation/passed_flag_5B"`
   * `path: "data/layer2/5B/validation/fingerprint={manifest_fingerprint}/_passed.flag_5B"`
   * `partitioning.keys: ["manifest_fingerprint"]`
   * `status: "active"`
   * `final_in_segment: true`
   * `final_in_layer: true`

Any optional receipt inside the bundle (e.g. `s5_receipt_5B.json`) SHOULD also have a dictionary entry, but MUST NOT be treated as a separate HashGate.

---

5.5 **Artefact registry entries in `artefact_registry_5B.yaml`**

The 5B artefact registry MUST register S5 artefacts with roles and dependencies, for example:

* **`validation_bundle_5B` artefact**

  * `artifact_id: "validation_bundle_5B"`
  * `role: "validation_bundle"`
  * `layer: 2`
  * `segment: "5B"`
  * `path_template: "data/layer2/5B/validation/fingerprint={manifest_fingerprint}/"`
  * `schema_ref_index: "schemas.layer2.yaml#/validation/validation_bundle_index_5B"`
  * `depends_on`:

    * all S0–S4 artefacts (gate, grid, intensities, counts, arrivals),
    * RNG logs for S2–S4,
    * upstream HashGates (1A–3B, 5A).

* **`validation_passed_flag_5B` artefact**

  * `artifact_id: "validation_passed_flag_5B"`
  * `role: "hashgate"`
  * `layer: 2`
  * `segment: "5B"`
  * `path_template: "data/layer2/5B/validation/fingerprint={manifest_fingerprint}/_passed.flag_5B"`
  * `schema_ref: "schemas.layer2.yaml#/validation/passed_flag_5B"`
  * `depends_on: ["validation_bundle_5B"]`

Any optional receipt/report entries inside the bundle MUST be registered with `role: "validation_report"` / `"validation_issue_table"` / `"receipt"` accordingly, but MUST NOT be advertised as HashGates.

Together, these anchors, dictionary entries and registry definitions ensure that:

* the shape of the 5B validation bundle is explicit,
* the on-disk layout is predictable and fingerprint-scoped, and
* downstream systems can discover and trust `_passed.flag_5B` via catalogue/registry alone, without hard-coded paths.

---

## 6. Deterministic algorithm (RNG-free validator & bundler) *(Binding)*

6.1 **High-level phases**

For a given `manifest_fingerprint = mf`, S5 MUST execute the following phases **without any RNG**:

1. **Discovery** — determine the full 5B domain under `mf` from catalogue + `sealed_inputs_5B`.
2. **Validation** — replay S0–S4 invariants and RNG accounting over that domain.
3. **Evidence assembly** — write validation report / issue table and any auxiliary receipts.
4. **Bundle assembly** — construct `index.json` for `validation_bundle_5B`.
5. **HashGate computation** — compute the bundle digest and write `_passed.flag_5B`.

If any phase fails, S5 MUST mark the run FAIL and MUST NOT leave a “PASS-looking” bundle/flag behind.

---

6.2 **Phase 1 — Discovery (domain & evidence set)**

6.2.1 **Enumerate 5B domain for `mf`**
Using the catalogue (`dataset_dictionary.layer2.5B.yaml`) and `sealed_inputs_5B`, S5 MUST:

* enumerate all `(parameter_hash, scenario_id, seed)` triples that:

  * appear in `s3_bucket_counts_5B` for `mf`, and
  * have corresponding `s4_arrival_events_5B` partitions for `mf`.
* derive a canonical ordering for these triples, e.g.:

  * sort by `parameter_hash`, then `scenario_id`, then `seed`.

S5 MUST treat this ordered set as the **complete 5B domain** under `mf`; any missing `s4_arrival_events_5B` for a triple with S3 counts is a validation failure.

6.2.2 **Resolve upstream artefacts**
From `sealed_inputs_5B`, S5 MUST resolve the exact physical locations (paths) of:

* all required 5B datasets (S0–S4),
* upstream routing/time/virtual/intensity artefacts (1B–3B, 5A),
* RNG logs (`rng_audit_log`, `rng_trace_log`, S2/S3/S4 RNG event tables).

S5 MUST NOT read any artefact that is not referenced in `sealed_inputs_5B`.

---

6.3 **Phase 2 — Validation of S0–S4 invariants**

For each `manifest_fingerprint = mf`, S5 MUST:

6.3.1 **Check S0 (gate & sealed inputs)**

* Verify that `s0_gate_receipt_5B` and `sealed_inputs_5B`:

  * are schema-valid,
  * record all mandatory upstream `_passed.flag_*` as PASS for `mf`,
  * cover every artefact S5 has resolved in 6.2.2.
* Any mismatch (missing artefact, upstream FAIL/MISSING) MUST cause S5 to fail with a suitable error.

6.3.2 **Check S1/S2/S3 (grid, domain & counts)**

Across all `(ph, sid, seed)` discovered:

* **Grid alignment:**

  * Every `(ph, sid, bucket_index)` used in `s3_bucket_counts_5B` MUST have a matching row in `s1_time_grid_5B` (same `mf`).
* **S2 domain sanity:**

  * For every `(ph, sid, entity, bucket)` in S3, there MUST be a corresponding `(ph, sid, entity, bucket)` in `s2_realised_intensity_5B` (or an explicitly allowed exception, if defined in spec).

S5 does **not** re-compute λ or counts here; it only checks domain and structural consistency.

6.3.3 **Check S4 vs S3 (count & time invariants)**

For each `(ph, sid, seed)`:

* **Count conservation:**

  * Aggregate `s4_arrival_events_5B` by `(entity, bucket_index)` and check it matches `N` in `s3_bucket_counts_5B` exactly.
* **Time windows:**

  * For each arrival row, join to `s1_time_grid_5B` on `(ph, sid, bucket_index)` and check
    `bucket_start_utc ≤ ts_utc < bucket_end_utc`.

Any mismatch is a hard validation failure.

6.3.4 **Civil time & routing invariants**

For each arrival row:

* **Civil time:**

  * Using `site_timezones` / `tz_timetable_cache` (physical) and `virtual_routing_policy_3B` + `tz_timetable_cache` (virtual), recompute or verify the mapping from `ts_utc` to local timestamps and check that:

    * tzids exist in the cache, and
    * local times respect the configured DST behaviour.

* **Routing:**

  * Physical arrivals (`is_virtual = false`):

    * `site_id` exists in `site_locations` for `(mf, seed)` and `merchant_id`.
    * optionally check that sites are part of the routing universe implied by 2B/3A (using `s1_site_weights`, `zone_alloc`, policies).
  * Virtual arrivals (`is_virtual = true`):

    * `edge_id` exists in `edge_catalogue_3B` for the merchant.
    * semantics (settlement/operational tzids) obey `virtual_routing_policy_3B`.

S5 does not re-run the routing algorithm; it only checks that the outputs are compatible with the authoritative surfaces and policies.

6.3.5 **Schema/partition/PK checks for S4**

For each `(mf, sid, seed)` partition of `s4_arrival_events_5B`, S5 MUST:

* validate against `schemas.5B.yaml#/egress/s4_arrival_events_5B`,
* confirm partition keys (`seed`, `manifest_fingerprint`, `scenario_id`) match the directory and column values,
* confirm primary key uniqueness within `(mf, seed, sid)`.

Any schema or identity violation is a validation failure.

---

6.4 **Phase 3 — RNG accounting checks**

S5 MUST verify RNG accounting for **all RNG-using 5B states** (S2, S3, S4):

* For each `(ph, mf, sid, seed)`:

  * derive expected draw counts per RNG family from:

    * S2 domain (groups × buckets),
    * S3 domain (entity × bucket counts),
    * S4 arrivals (number of arrivals) and S4’s RNG law.
* Using RNG event tables and `rng_trace_log`:

  * aggregate actual `draws` and `blocks` per family and per `(seed, parameter_hash, run_id)` relevant to 5B,
  * check that:

    * actual draws/blocks equal expected values, and
    * Philox counters are monotonically increasing with no overlaps.

Any mismatch or counter anomaly is a validation failure.

---

6.5 **Phase 4 — Evidence materialisation**

If all checks in Phases 2–3 pass, S5 MUST materialise its evidence artefacts for `mf`:

* **`validation_report_5B`**

  * A single JSON file summarising:

    * which checks were run,
    * which seeds/scenarios were covered,
    * key metrics (arrival counts, routing mix, etc.),
    * final `status = "PASS"`.

* **`validation_issue_table_5B`** (optional)

  * A table of issues/warnings, possibly empty, each with `issue_code`, `severity`, and references into the 5B domain.

* Any optional `s5_receipt_5B` object (if designed) summarising bundle contents, spec version, etc.

All of these MUST be written under:

```text
data/layer2/5B/validation/fingerprint={manifest_fingerprint}/
```

and their paths recorded for the next phase.

If any check fails, S5 MUST:

* write a `validation_report_5B` with `status = "FAIL"` and appropriate `error_code`,
* **not** proceed to bundle/flag creation with PASS semantics.

---

6.6 **Phase 5 — Bundle assembly (`validation_bundle_5B`)**

S5 MUST then construct `index.json` and thereby the bundle:

1. **Select bundle members**

   * At minimum, `index.json` MUST reference:

     * `validation_report_5B`,
     * any `validation_issue_table_5B`,
     * any `s5_receipt_5B`,
     * any additional evidence files S5 chooses to include (e.g. RNG summaries).
   * `_passed.flag_5B` MUST NOT be listed as a bundle member.

2. **Compute per-file digests**

   * For each bundle member:

     * compute the SHA-256 digest of the file’s **raw bytes**,
     * encode as lowercase hex (`sha256_hex`).

3. **Build and write `index.json`**

   * Assemble an object conforming to `schemas.layer2.yaml#/validation/validation_bundle_index_5B`:

     * entries sorted in **ASCII-lexicographic order of the `path`** field,
     * each entry containing `logical_id` (or role), `path`, `sha256_hex`, `schema_ref` where applicable.
   * Write `index.json` into the same `fingerprint={mf}` directory.

This completes the **bundle structure**; no hashing across files has been done yet.

---

6.7 **Phase 6 — Bundle digest & `_passed.flag_5B`**

Finally, S5 MUST compute a single **bundle digest** and write `_passed.flag_5B`:

1. **Compute bundle digest**

   * Let `E` be the ordered list of bundle entries from `index.json`, sorted by `path` (already enforced in 6.6).

   * For each entry `e ∈ E`, take the corresponding file in that order and read its raw bytes.

   * Concatenate the bytes of all files in `E` in this exact order.

   * Compute:

     ```text
     bundle_sha256 = SHA256(concatenated_bytes)
     ```

   * Encode `bundle_sha256` as a 64-char lowercase hex string.

2. **Write `_passed.flag_5B`**

   * Create `_passed.flag_5B` at the root of the `fingerprint={mf}` directory with content conforming to the `passed_flag_5B` schema, e.g.:

     ```text
     sha256_hex = <bundle_sha256_hex>
     ```

   * `_passed.flag_5B` MUST NOT be included in the bundle digest calculation.

3. **Idempotence & safety**

   * If a valid `_passed.flag_5B` already exists for `mf`:

     * S5 MUST verify that the newly computed `bundle_sha256` matches the existing value; if so, the run is idempotent.
     * If not, S5 MUST treat this as a conflict (e.g. `5B.S5.BUNDLE_DIGEST_MISMATCH`) and fail without overwriting the existing flag.

With this phase complete and **only if all prior checks succeeded**, the pair `(validation_bundle_5B, _passed.flag_5B)` constitutes the canonical HashGate for 5B under `manifest_fingerprint = mf`.

---

## 7. Identity, partitions, ordering & bundle law *(Binding)*

7.1 **Core identity tokens for S5**

S5’s artefacts are identified at the **fingerprint** and **spec** level:

* `manifest_fingerprint` — world identity (which Layer-1/5A world we’re sealing).
* `5B_spec_version` — the segment-level spec version under which S5 ran.

For all S5 outputs (bundle, index, report, issue table, flag):

* Identity is the pair:
  **`(manifest_fingerprint, 5B_spec_version)`**
* `seed`, `parameter_hash`, `scenario_id`, and `run_id` MUST NOT appear in the path structure. They may only appear inside the bundle contents as metadata.

---

7.2 **Partition keys & path law**

All S5 artefacts are **fingerprint-scoped** and MUST obey the same directory layout:

```text
data/layer2/5B/validation/
  fingerprint={manifest_fingerprint}/
    index.json
    validation_report_5B.json
    validation_issue_table_5B.parquet       (optional)
    s5_receipt_5B.json                      (optional)
    ... other evidence files ...
    _passed.flag_5B
```

Binding rules:

* The directory **must** include `fingerprint={manifest_fingerprint}` as a path token.
* No additional partition tokens (e.g. `seed=`, `scenario_id=`, `parameter_hash=`) are allowed in the path for S5 artefacts.
* Every file in the bundle for a given `manifest_fingerprint` MUST live inside this directory (or its subdirectories, referenced via relative paths in `index.json`).

The dataset dictionary and artefact registry MUST reflect this by setting:

* `partitioning.keys: ["manifest_fingerprint"]` for all S5 entries.

---

7.3 **Uniqueness & overwrite discipline**

For each `manifest_fingerprint` and `5B_spec_version`:

* There MUST be **at most one** logical `validation_bundle_5B` + `_passed.flag_5B` pair considered valid.

S5 MUST enforce:

* If no bundle/flag exists for `mf`:

  * It may create a new directory and write `index.json`, evidence files, and `_passed.flag_5B` once the run passes.
* If a bundle/flag already exists for `mf`:

  * S5 MUST recompute the bundle digest as per §6.7 and compare it to the existing `_passed.flag_5B`.

    * If the digest matches, the run is **idempotent**; S5 MAY leave the existing files unchanged.
    * If the digest does *not* match, S5 MUST treat this as a conflict (e.g. `5B.S5.BUNDLE_DIGEST_MISMATCH`) and MUST NOT overwrite the existing bundle or flag.

S5 MUST NOT:

* append new evidence files to an existing bundle without regenerating `index.json` and `_passed.flag_5B`,
* silently replace existing bundle contents with non-identical data while keeping the same `_passed.flag_5B`.

Any change to the evidence set or its bytes for an `mf` requires recomputing the digest and thus a new `_passed.flag_5B`; if this is not allowed by policy, the driver MUST treat it as a separate, incompatible run.

---

7.4 **Canonical ordering & bundle law**

7.4.1 **Index ordering**

Within `index.json`:

* Every bundle member MUST have a unique `path` (relative to the `fingerprint={mf}` directory).
* S5 MUST store entries in an array sorted in **ASCII-lexicographic order of the `path` string**.
* This ordering is **binding** and is the only order used for computing the bundle digest.

7.4.2 **Bundle digest computation**

The digest written into `_passed.flag_5B` MUST be computed as follows:

1. Let `E = [e₁, e₂, …, eₖ]` be the ordered list of index entries from `index.json`, sorted by `path` (as stored).

2. For each `eᵢ`, open the corresponding file at `eᵢ.path` and read its **raw bytes**.

3. Concatenate these byte sequences in order:

   ```text
   bytes_concat = bytes(e₁) || bytes(e₂) || … || bytes(eₖ)
   ```

4. Compute:

   ```text
   bundle_sha256 = SHA256(bytes_concat)
   ```

5. Encode `bundle_sha256` as 64 lowercase hex characters.

7.4.3 **Flag content**

`_passed.flag_5B` MUST:

* live at the root of `fingerprint={mf}`, and
* contain exactly a single line conforming to `schemas.layer2.yaml#/validation/passed_flag_5B`, e.g.:

```text
sha256_hex = <64 lowercase hex chars>
```

Where `<…>` is the `bundle_sha256` computed above.

S5 MUST NOT:

* include `_passed.flag_5B` itself in the digest calculation,
* include any other data in the flag file (no extra keys, no trailing junk),
* vary whitespace or formatting in a way that violates the flag schema.

---

7.5 **Catalogue & discovery guarantees**

Given the rules above:

* The **dataset dictionary** entry for each S5 artefact MUST use:

  * `path: "data/layer2/5B/validation/fingerprint={manifest_fingerprint}/…"`
    with no other partition tokens.
* The **artefact registry** MUST mark:

  * `validation_bundle_5B` as the container at `…/fingerprint={mf}/`, and
  * `validation_passed_flag_5B` as the HashGate file at `…/fingerprint={mf}/_passed.flag_5B`.

Downstream components (6A/6B, ingestion, operators) MUST be able to:

* locate `validation_bundle_5B` and `_passed.flag_5B` for a given `manifest_fingerprint` using only:

  * the dictionary/registry entries, and
  * the fingerprint value,

without any hard-coded assumptions beyond the path law defined here.

This section together with §6 fixes the **bundle law** for 5B: there is one fingerprint-scoped bundle per world, a canonical index and digest, and a single flag file whose content is the only valid “5B PASS” token for arrivals under that world.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

8.1 **Local PASS criteria for S5 (per `manifest_fingerprint`)**

For a given `manifest_fingerprint = mf`, S5 is considered **PASS** *iff* all of the following conditions hold **simultaneously**:

8.1.1 **Domain completeness**

* The discovered 5B domain under `mf` (all `(parameter_hash, scenario_id, seed)` that appear in `s3_bucket_counts_5B`) is **fully covered** by S4:

  * For every `(ph, sid, seed)` with S3 bucket counts:

    * there exists a corresponding `s4_arrival_events_5B` dataset for `(mf, sid, seed)`.
  * There are **no** `s4_arrival_events_5B` partitions for `(mf, sid, seed)` that lack matching S3 counts.
* No required upstream HashGate (1A–3B, 5A) is missing or marked FAIL/MISSING in `s0_gate_receipt_5B`.

---

8.1.2 **S0 invariants (gate & sealed inputs)**

* `s0_gate_receipt_5B` and `sealed_inputs_5B` are schema-valid.
* Every artefact S5 actually reads:

  * appears in `sealed_inputs_5B`, with a role that permits read access, and
  * is consistent with its recorded `path_template` and `schema_ref`.
* All mandatory upstream `_passed.flag_*` entries for `mf` are recorded as PASS in `s0_gate_receipt_5B`.

Any missing or inconsistent entry is a FAIL for S5.

---

8.1.3 **S1–S3 invariants (grid, domain & counts)**

Across all discovered `(ph, sid, seed)` under `mf`:

* **Grid domain alignment**

  * Every `(ph, sid, bucket_index)` present in `s3_bucket_counts_5B` has a matching row in `s1_time_grid_5B`.
* **Intensity domain sanity**

  * For every `(ph, sid, entity, bucket_index)` in S3:

    * there is a matching row in `s2_realised_intensity_5B` (unless the spec explicitly allows a small, well-defined exception class — if you don’t define one, the default is “no gaps”).

S5 does **not** re-sample intensities or counts; it only ensures domain and structure consistency.

---

8.1.4 **S3↔S4 count and time invariants**

For each `(ph, sid, seed)`:

* **Count conservation**

  * Aggregate `s4_arrival_events_5B` by `(entity, bucket_index)` and confirm:

    * if S3’s `N = 0` → there are **zero** arrivals with that `(entity, bucket_index)`,
    * if S3’s `N = N₀ > 0` → there are **exactly `N₀`** arrivals with that `(entity, bucket_index)`,
    * there is no `(entity, bucket_index)` present in S4 that does not exist in S3.

* **Time window correctness**

  * For each arrival row:

    * join to `s1_time_grid_5B` on `(ph, sid, bucket_index)`,
    * check `bucket_start_utc ≤ ts_utc < bucket_end_utc`.

Any deviation (extra/missing arrivals or timestamps outside their bucket) causes S5 to FAIL.

---

8.1.5 **Civil-time & routing correctness**

For each arrival row in `s4_arrival_events_5B`:

* **Civil time (2A semantics)**

  * For the tzid(s) used on the row (physical or virtual), S5 can reconstruct local timestamps from `ts_utc` using:

    * `site_timezones` / `tz_timetable_cache` for physical sites,
    * `virtual_routing_policy_3B` + `tz_timetable_cache` for virtual edges.
  * All local timestamps are:

    * consistent with 2A’s tz database, and
    * consistent with the configured DST policy (no unhandled gaps/folds, no unknown tzids).

* **Routing (2B/3A/3B semantics)**

  * Physical arrivals (`is_virtual = false`):

    * `site_id` is non-null, `edge_id` is null,
    * `site_id` exists in `site_locations` for `(mf, seed)` and `merchant_id`,
    * no routing into zones or sites outside the universes defined by 2B + 3A.
  * Virtual arrivals (`is_virtual = true`):

    * `edge_id` is non-null, `site_id` is null,
    * `edge_id` exists in `edge_catalogue_3B` for the merchant,
    * tz semantics (settlement/operational) obey `virtual_routing_policy_3B`.

If `is_virtual` and site/edge fields are inconsistent, or if an arrival references a non-existent site/edge, or violates these semantics, S5 FAILS.

---

8.1.6 **Schema, partitioning & PK invariants for S4**

For each `(mf, sid, seed)` partition of `s4_arrival_events_5B`:

* The dataset is schema-valid against `schemas.5B.yaml#/egress/s4_arrival_events_5B`:

  * all required columns present, types correct, no undeclared columns.
* Partition keys in the path (`seed`, `fingerprint`, `scenario_id`) match the corresponding column values.
* Primary key (arrival identity) is unique within `(mf, seed, sid)` and covers all rows.

Any schema/partition/PK violation is a FAIL.

---

8.1.7 **RNG accounting for S2, S3, S4**

Using RNG event tables and `rng_trace_log`, S5 MUST confirm that:

* For each `(ph, mf, sid, seed)`:

  * expected number of draws/blocks for each RNG family (S2 latent, S3 counts, S4 time jitter, S4 site picks, S4 edge picks), derived from:

    * the S2 domain (groups × buckets),
    * the S3 domain (`N` per bucket),
    * the S4 arrival count,
  * matches the actual draws/blocks recorded in the RNG logs.
* Philox counters for S2, S3, S4 streams are **monotonic, non-overlapping, and forward-only**.

Any mismatch or counter anomaly is a FAIL.

---

8.1.8 **Bundle integrity & flag correctness**

After all checks above pass:

* All evidence files selected for the bundle:

  * exist,
  * are schema-valid,
  * and have stable SHA-256 digests.

* `index.json`:

  * conforms to `schemas.layer2.yaml#/validation/validation_bundle_index_5B`,
  * lists every evidence file exactly once,
  * stores entries sorted by `path` in ASCII-lex order,
  * contains per-file `sha256_hex` that match the actual file contents.

* The bundle digest computed according to the law in §7.4 matches the value written into `_passed.flag_5B` at:

  ```text
  data/layer2/5B/validation/fingerprint={mf}/_passed.flag_5B
  ```

* If a previous `_passed.flag_5B` already exists for `mf`, S5 recomputes the digest and confirms it is identical.

Only when all these conditions are satisfied MAY S5 report `status="PASS"` for `mf`.

---

8.2 **Failure semantics**

If **any** of the criteria in §8.1 fails for `mf`:

* S5 MUST:

  * mark 5B.S5 run-report for `mf` as `status="FAIL"` with an appropriate `5B.S5.*` `error_code`,
  * NOT advertise `validation_bundle_5B` or `_passed.flag_5B` as PASS in the artefact registry,
  * avoid leaving behind a misleading “PASS-looking” flag:

    * either no `_passed.flag_5B` is written, or
    * an existing flag is left as-is but the new run is clearly marked FAIL (no overwrite).

Downstream systems MUST treat any non-PASS S5 state as **“5B not sealed”** for that `manifest_fingerprint`, even if S0–S4 are individually marked PASS.

---

8.3 **Gating obligations**

8.3.1 **Within Segment 5B**

* S5 is the **final gate** for 5B:

  * Orchestration MUST NOT mark 5B as PASS for `mf` unless S5 has produced a valid `validation_bundle_5B` + `_passed.flag_5B` and reported `status="PASS"`.
  * Any attempt to run further 5B-related processes (e.g. publishing arrivals to external systems) MUST check S5’s status for `mf`.

8.3.2 **Towards Layer-3 (6A/6B) and enterprise consumers**

All downstream consumers of 5B arrivals (6A, 6B, and any enterprise ingestion) MUST:

* treat `s4_arrival_events_5B` as **authoritative arrival data** *only if*:

  * a `_passed.flag_5B` exists for the corresponding `manifest_fingerprint`, and
  * the flag’s digest verifies against `validation_bundle_5B` using the bundle law in §7.4.
* reject or quarantine any arrivals for a `manifest_fingerprint` that:

  * has no S5 bundle/flag, or
  * has a flag that fails verification.

In other words:

> S4 PASS is necessary but not sufficient.
> Only an S5 PASS with a verified `_passed.flag_5B` constitutes a valid “5B is sealed” signal for Layer-3 and downstream consumers.

---

## 9. Failure modes & canonical error codes *(Binding)*

9.1 **Conventions**

9.1.1 **Code format**
All S5 errors MUST use the prefix:

> `5B.S5.`

followed by an UPPER_SNAKE_CASE identifier, e.g. `5B.S5.S0_GATE_INVALID`.

9.1.2 **Effect of any S5 error**
If any error in this section is raised for a given `manifest_fingerprint`:

* S5 MUST mark its run-report as `status = "FAIL"` with that `error_code`.
* S5 MUST NOT:

  * claim 5B PASS for that `manifest_fingerprint`,
  * publish or update `_passed.flag_5B` to reflect a PASS state.

Downstream MUST treat 5B as **not sealed** for that `manifest_fingerprint`.

---

### 9.2 Upstream gate / discovery failures

**9.2.1 `5B.S5.S0_GATE_MISSING_OR_INVALID`**
Raised when:

* `s0_gate_receipt_5B` and/or `sealed_inputs_5B` is missing, schema-invalid, or fails basic consistency checks (e.g. missing required segments, malformed entries).

**9.2.2 `5B.S5.UPSTREAM_HASHGATE_NOT_PASSED`**
Raised when, for the `manifest_fingerprint`:

* any mandatory upstream `_passed.flag_*` (1A, 1B, 2A, 2B, 3A, 3B, 5A) is not present, not verifiable, or recorded as FAIL/MISSING in `s0_gate_receipt_5B`.

**9.2.3 `5B.S5.DOMAIN_DISCOVERY_FAILED`**
Raised when:

* S5 cannot derive a coherent domain of `(parameter_hash, scenario_id, seed)` triples from catalogue + `sealed_inputs_5B`, e.g.:

  * S3 and S4 refer to incompatible sets of triples, or
  * discovery yields an empty or obviously incomplete domain.

---

### 9.3 S0–S3 structural validation failures

**9.3.1 `5B.S5.S1_S3_GRID_DOMAIN_MISMATCH`**
Raised when:

* any `(ph, sid, bucket_index)` present in `s3_bucket_counts_5B` has no corresponding row in `s1_time_grid_5B`, or
* S3 uses a `(ph, sid, entity, bucket)` that is not present in `s2_realised_intensity_5B` (unless explicitly allowed by spec).

**9.3.2 `5B.S5.S0_SEALED_INPUTS_INCONSISTENT`**
Raised when:

* S5 needs to read an artefact that is **not** present in `sealed_inputs_5B`, or
* an artefact’s actual path or schema disagrees with its recorded `path_template` / `schema_ref` in `sealed_inputs_5B`.

---

### 9.4 S3↔S4 count & time validation failures

**9.4.1 `5B.S5.COUNT_MISMATCH_S3_S4`**
Raised when:

* aggregated counts from `s4_arrival_events_5B` by `(entity, bucket_index)` do not exactly match `N` in `s3_bucket_counts_5B` for any `(ph, sid, seed)`;

  * extra arrivals,
  * missing arrivals, or
  * mis-keyed arrivals.

**9.4.2 `5B.S5.TIME_WINDOW_VIOLATION`**
Raised when:

* for any arrival row, `ts_utc` is not within `[bucket_start_utc, bucket_end_utc)` of the matching `s1_time_grid_5B` row.

---

### 9.5 Civil time & routing validation failures

**9.5.1 `5B.S5.CIVIL_TIME_MAPPING_FAILED`**
Raised when:

* S5 cannot verify that local timestamps in `s4_arrival_events_5B` are consistent with 2A’s `site_timezones` / `tz_timetable_cache` (or virtual tz rules), e.g.:

  * unknown tzid,
  * unhandled DST gap/fold according to configured policy.

**9.5.2 `5B.S5.PHYSICAL_ROUTING_INVALID`**
Raised when, for any physical arrival (`is_virtual = false`):

* `site_id` is null or does not exist in `site_locations` for `(mf, seed, merchant_id)`, or
* S5 detects routing into zones/sites not allowed by the 2B + 3A routing/zone universes.

**9.5.3 `5B.S5.VIRTUAL_ROUTING_INVALID`**
Raised when, for any virtual arrival (`is_virtual = true`):

* `edge_id` is null or does not exist in `edge_catalogue_3B` for that merchant, or
* S5 detects violations of `virtual_routing_policy_3B` (e.g. wrong tz semantics, out-of-universe edge).

**9.5.4 `5B.S5.SITE_EDGE_FLAG_INCONSISTENT`**
Raised when:

* an S4 arrival row has both `site_id` and `edge_id` non-null, or both null, or
* `is_virtual` is inconsistent with which of `site_id` / `edge_id` is populated.

---

### 9.6 Schema / partition / PK validation failures

**9.6.1 `5B.S5.S4_SCHEMA_VIOLATION`**
Raised when:

* any `s4_arrival_events_5B` partition fails validation against `schemas.5B.yaml#/egress/s4_arrival_events_5B` (missing required columns, wrong types, undeclared columns when `columns_strict: true`).

**9.6.2 `5B.S5.S4_PARTITION_OR_IDENTITY_VIOLATION`**
Raised when:

* directory partition tokens (`seed`, `fingerprint`, `scenario_id`) do not match the values in the data columns, or
* multiple different `(seed, fingerprint, scenario_id)` values are mixed in the same logical partition.

**9.6.3 `5B.S5.S4_PK_VIOLATION`**
Raised when:

* primary key constraints for `s4_arrival_events_5B` are violated (duplicate keys, missing keys relative to the arrival rows).

---

### 9.7 RNG accounting failures

**9.7.1 `5B.S5.RNG_ACCOUNTING_INCOMPLETE`**
Raised when:

* required RNG event tables or `rng_trace_log` entries for S2, S3, or S4 are missing or incomplete for the 5B domain under `mf`.

**9.7.2 `5B.S5.RNG_ACCOUNTING_MISMATCH`**
Raised when:

* the expected draws/blocks for any RNG family in S2, S3, or S4 (derived from domain and S4 arrivals) do not match the actual draws/blocks recorded in RNG logs, or
* Philox counters are non-monotonic or overlapping.

---

### 9.8 Bundle / flag integrity failures

**9.8.1 `5B.S5.BUNDLE_INDEX_INVALID`**
Raised when:

* `index.json` is missing, schema-invalid, contains duplicate `path` entries, or is not sorted by `path` in ASCII-lexicographic order.

**9.8.2 `5B.S5.BUNDLE_MEMBER_MISSING_OR_HASH_MISMATCH`**
Raised when:

* an entry in `index.json` references a file that does not exist, or
* the recomputed SHA-256 of a member file does not match its `sha256_hex` in `index.json`.

**9.8.3 `5B.S5.BUNDLE_DIGEST_MISMATCH`**
Raised when:

* the digest computed over bundle members (per the bundle law) does not match the value in `_passed.flag_5B`, or
* an existing `_passed.flag_5B` for `mf` contains a digest that does not match the newly computed bundle digest for the same evidence set.

**9.8.4 `5B.S5.FLAG_SCHEMA_VIOLATION`**
Raised when:

* `_passed.flag_5B` is missing, malformed, or does not conform to `schemas.layer2.yaml#/validation/passed_flag_5B` (e.g. extra content, wrong format).

---

### 9.9 IO / orchestration failures

**9.9.1 `5B.S5.IO_READ_FAILED`**
Raised when:

* S5 cannot read a dataset or artefact that is present in `sealed_inputs_5B` and required for validation (e.g. transient storage error, permission issue).

**9.9.2 `5B.S5.IO_WRITE_FAILED`**
Raised when:

* S5 fails to write any of its outputs (`validation_report_5B`, `validation_issue_table_5B`, `index.json`, `_passed.flag_5B`) due to IO/storage errors.

**9.9.3 `5B.S5.IO_WRITE_CONFLICT`**
Raised when:

* S5 detects that it is about to overwrite or modify an existing `validation_bundle_5B` / `_passed.flag_5B` for `mf` in a way that conflicts with the uniqueness/overwrite rules in §7.

---

### 9.10 Unhandled / internal errors

**9.10.1 `5B.S5.UNEXPECTED_INTERNAL_ERROR`**
Raised when:

* an unexpected exception, invariant violation, or logic bug occurs that does not fit a more specific error code above.

In this case S5 MUST:

* log sufficient context into the run-report (and operator logs) to debug the problem, and
* treat the run as FAIL.

---

9.11 **Mapping to orchestration & downstream**

* Orchestration MUST treat any `5B.S5.*` error as a **5B-level failure** for the associated `manifest_fingerprint`.
* 5B.S5 MUST NOT mark the fingerprint as PASS or publish a PASS `_passed.flag_5B`.
* Layer-3 / ingestion MUST refuse to treat `s4_arrival_events_5B` as authoritative for that fingerprint whenever any `5B.S5.*` failure is present or `_passed.flag_5B` is absent/invalid.

---

## 10. Observability & run-report integration *(Binding)*

10.1 **Per-fingerprint run-report record (required)**
For every S5 execution over a `manifest_fingerprint = mf`, the engine MUST emit exactly **one** run-report record for 5B.S5 with at least:

* `state_id = "5B.S5"`
* `manifest_fingerprint`
* `5B_spec_version`
* `run_id` (execution identifier)
* `status ∈ {"PASS","FAIL"}`
* `error_code` (empty / null iff `status="PASS"`)
* `error_message` (optional human-readable detail; required on FAIL)

This record MUST be written into the same global run-report mechanism used by other states so orchestration can see S5 status alongside S0–S4.

---

10.2 **Required summary metrics**

The S5 run-report for `mf` MUST include, at minimum, the following metrics summarising what S5 has validated:

* **Domain coverage**

  * `n_parameter_hashes` — distinct `parameter_hash` values encountered.
  * `n_scenarios` — distinct `scenario_id` values.
  * `n_seeds` — distinct `seed` values under `mf`.
* **Volume**

  * `n_buckets_total` — total `(entity, bucket)` rows in `s3_bucket_counts_5B` under `mf`.
  * `n_buckets_nonzero` — `(entity, bucket)` with `N>0`.
  * `n_arrivals_total` — total rows in `s4_arrival_events_5B` under `mf`.
* **Routing mix**

  * `n_arrivals_physical`
  * `n_arrivals_virtual`
* **Check roll-ups (booleans)**

  * `counts_match_s3` — aggregate result of S3↔S4 count checks.
  * `time_windows_ok` — aggregate result of bucket window checks.
  * `civil_time_ok` — aggregate result of 2A civil-time checks.
  * `routing_ok` — aggregate result of 2B/3A/3B routing checks.
  * `schema_partition_pk_ok` — aggregate result of S4 schema/partition/PK checks.
  * `rng_accounting_ok` — aggregate result of S2/S3/S4 RNG accounting checks.
  * `bundle_integrity_ok` — aggregate result of bundle/index/flag checks.

If `status="PASS"`, **all** these booleans MUST be `true`. If any is `false`, S5 MUST set `status="FAIL"` and an appropriate `5B.S5.*` error_code.

---

10.3 **Optional observability metrics (non-gating)**

S5 MAY add additional metrics for operators, for example:

* Per-scenario counts (e.g. `n_arrivals_by_scenario` as a small map).
* Per-seed counts (e.g. `n_arrivals_by_seed`).
* Summary of issues by severity (e.g. count of warnings vs errors if an issue table is produced).

These metrics MUST NOT be used by gating logic; they are for dashboards and inspection only.

---

10.4 **RNG accounting summary in run-report**

Although S5 itself is RNG-free, it validates RNG for S2/S3/S4. The S5 run-report MUST therefore include a compact RNG summary:

* `rng_checked_states` — list/enum of states whose RNG was validated (e.g. `["5B.S2","5B.S3","5B.S4"]`).
* `rng_families_ok` — boolean (true iff all families passed accounting).
* Optionally, a small map like `rng_draws_by_family` and `rng_blocks_by_family` aggregated across the 5B domain under `mf`.

This summary MUST be consistent with the detailed RNG accounting files included in `validation_bundle_5B`.

---

10.5 **Linkage to bundle & flag**

The S5 run-report record for `mf` MUST:

* include the **relative path** to `validation_bundle_5B` and `_passed.flag_5B` (or enough information to derive it from dictionary/registry), and
* echo the `bundle_sha256` value written into `_passed.flag_5B`.

On PASS:

* `status="PASS"`
* `bundle_integrity_ok=true`
* `bundle_sha256` MUST equal the value in `_passed.flag_5B`.

On FAIL:

* `status="FAIL"`
* `bundle_sha256` MAY be omitted or set to a sentinel (e.g. null) if the bundle is incomplete.

---

10.6 **Integration with global run-report / orchestration**

S5 run-report entries MUST be discoverable via the global run-report index, keyed at least by:

* `layer = 2`
* `segment = "5B"`
* `state_id = "5B.S5"`
* `manifest_fingerprint`
* `run_id`

Orchestration and downstream tooling MUST be able to:

* query “latest S5 status” for a `manifest_fingerprint`,
* decide, based on `status`, `error_code`, and `bundle_sha256`, whether to treat 5B as sealed and `_passed.flag_5B` as valid.

No downstream component is allowed to infer 5B PASS solely from S4 metrics; they MUST go through S5’s run-report + bundle/flag for a binding decision.

---

## 11. Performance & scalability *(Informative)*

11.1 **Asymptotic cost model**
S5 is a **read–check–hash** state; it does no RNG and writes only a small bundle.

For a given `manifest_fingerprint = mf`:

* Let:

  * `N_arrivals_total` = total rows in `s4_arrival_events_5B` under `mf`.
  * `N_buckets_total` = total rows in `s3_bucket_counts_5B` under `mf`.
  * `N_rng_events` = total RNG event rows for 5B.S2/S3/S4 under `mf`.

Then:

* Time complexity is roughly:

  > **O(N_arrivals_total + N_buckets_total + N_rng_events)**

* Memory can be kept **O(window_size)** by streaming arrivals and RNG logs in batches rather than loading everything at once.

In practice, validating S4 arrivals (`N_arrivals_total`) is the dominant cost.

---

11.2 **Streaming vs materialisation**
S5 SHOULD be implemented in a **streaming** style where possible:

* Read `s3_bucket_counts_5B` and `s4_arrival_events_5B` in aligned batches (e.g. by `(parameter_hash, scenario_id, seed)` or by merchant ranges), checking:

  * count conservation,
  * time window invariants,
  * routing + civil-time invariants,

  without holding the entire arrival world in memory.

* RNG validation can similarly:

  * stream RNG event tables per `(seed, parameter_hash, run_id)`,
  * aggregate draws/blocks per family on the fly,
  * compare to expected counts derived from S3/S4.

The only artefacts that must be fully materialised at the end are:

* `validation_report_5B` (small JSON),
* optional issue table (bounded by number of issues, not N_arrivals),
* `index.json` (small),
* `_passed.flag_5B` (tiny).

---

11.3 **I/O profile**

For a typical world (`mf`):

* **Reads** (dominant):

  * `s3_bucket_counts_5B` — full scan once.
  * `s4_arrival_events_5B` — full scan once (possibly partitioned by `(ph, sid, seed)`).
  * RNG logs for S2/S3/S4 — partial or full scans depending on layout.
  * Small dimension tables (`s1_time_grid_5B`, `site_locations`, `site_timezones`, `edge_catalogue_3B`, etc.) — ideally cached and reused.

* **Writes**:

  * `validation_report_5B.json`,
  * optional `validation_issue_table_5B.parquet`,
  * `index.json`,
  * `_passed.flag_5B`.

The write volume is tiny compared to the read volume; S5 is primarily a **read-heavy** state.

---

11.4 **Parallelism strategies**

S5’s work can be parallelised along the same axes as S4, as long as final aggregation is deterministic:

* **Per `(parameter_hash, scenario_id, seed)`**:

  * Validate S3↔S4 counts, time windows, routing, and RNG accounting independently in worker tasks.
  * Each worker emits intermediate metrics and issue rows.

* **Coordinator step**:

  * Collect worker results,
  * aggregate metrics into a single `validation_report_5B`,
  * build `validation_issue_table_5B` (if used),
  * assemble `index.json` and compute `_passed.flag_5B`.

Care must be taken that:

* RNG accounting is aggregated deterministically (e.g. by sorting keys),
* bundle contents and index ordering are independent of worker scheduling.

---

11.5 **Scaling with arrival volume**

As `N_arrivals_total` grows (e.g. many seeds / scenarios / high λ):

* S5’s CPU cost grows linearly, but it remains **bounded by S4** in absolute work: S5 only reads and checks; S4 generated the arrivals in the first place.
* Memory remains manageable if:

  * arrivals are processed in batches,
  * only small per-batch aggregates are kept (counts, min/max times, etc.).

Operationally:

* If S5 becomes a bottleneck for very large worlds, orchestration can:

  * limit concurrent `manifest_fingerprint` validations,
  * or shard validation work by `(parameter_hash, scenario_id, seed)` and recombine results centrally.

---

11.6 **Retry & idempotence posture**

Because S5 is RNG-free and outputs are small:

* It is safe to **re-run** S5 for a given `mf`:

  * If no bundle exists yet, the rerun will simply produce it.
  * If a bundle + flag already exist, S5 recomputes the digest:

    * if identical → run is idempotent,
    * if different → treated as a conflict and fails (see §7, §9).

Implementations MAY choose to:

* write evidence files and `index.json` to temporary locations and only move them into place once all checks pass and the hash is computed,
* or overwrite intermediate evidence files but never overwrite a valid `_passed.flag_5B` for `mf` unless the digest is unchanged.

These patterns ensure S5 remains robust and operationally cheap even as 5B scales up.

---

## 12. Change control & compatibility *(Binding)*

12.1 **Spec version linkage**

12.1.1 **Shared segment version**
S5 is governed by the **same `5B_spec_version`** as the rest of Segment 5B (S0–S4):

* `5B_spec_version` MUST be recorded in:

  * `s0_gate_receipt_5B`,
  * S5 run-report for `manifest_fingerprint`,
  * the 5B artefact registry entries for:

    * `arrival_events_5B`,
    * `validation_bundle_5B`,
    * `validation_passed_flag_5B`,
  * and (if present) any `s5_receipt_5B` object inside the bundle.

S5 MUST NOT change bundle layout, hash law, or acceptance semantics without an appropriate `5B_spec_version` bump.

---

12.2 **Backwards-compatible vs breaking changes**

12.2.1 **Backwards-compatible changes (minor/patch bump)**
The following changes are considered **backwards-compatible** and MAY be made with a **minor** or **patch** bump of `5B_spec_version` (e.g. `1.0.0 → 1.1.0` or `1.0.0 → 1.0.1`), provided they do not alter the meaning of an existing PASS:

* Adding **new evidence files** to `validation_bundle_5B` and listing them in `index.json` (e.g. extra metrics, extra RNG summaries).
* Extending `validation_report_5B` or `validation_issue_table_5B` with **new optional fields**.
* Tightening S5’s checks in a way that only *rejects* worlds that would previously have been considered invalid (i.e. stricter validation), but does not change what a valid S4 world “means”.
* Adding optional 5B-specific receipt objects (e.g. `s5_receipt_5B`) inside the bundle.

In these cases, downstream consumers that only care about the existence and integrity of `_passed.flag_5B` and the basic bundle law remain compatible.

12.2.2 **Breaking changes (major bump required)**
The following changes are **breaking** and MUST only be introduced with a **major** bump of `5B_spec_version` (e.g. `1.x.y → 2.0.0`), and in coordination with downstream consumers:

* Changing the **bundle law**:

  * how `bundle_sha256` is computed (different file set, different ordering, different hash function),
  * or changing the on-disk location / naming of `_passed.flag_5B`.
* Changing the **shape** of `validation_bundle_index_5B` in a way that breaks existing parsers (e.g. removing fields, changing field meaning).
* Changing S5’s PASS semantics such that:

  * a world that previously produced a valid `_passed.flag_5B` would now produce a *different* set of arrival events being considered valid, or
  * a previously PASS world would now be considered PASS with *significantly different* guarantees (e.g. relaxing invariants).
* Repurposing `_passed.flag_5B` to mean anything other than “this bundle, under this bundle law, has passed all 5B checks”.

Any such change MUST be treated as a major version and downstream systems MUST be updated (or explicitly gate on supported version ranges).

---

12.3 **Schema, dictionary & registry evolution**

12.3.1 **Schemas (`schemas.layer2.yaml`, `schemas.5B.yaml`)**

* Any change to:

  * `validation_bundle_index_5B`,
  * `validation_report_5B`,
  * `validation_issue_table_5B`,
  * `passed_flag_5B`,
  * or any S5-specific receipt schema

MUST be accompanied by:

* an update to `schemas.layer2.yaml` / `schemas.5B.yaml`, and
* a corresponding `5B_spec_version` bump classified according to §12.2.

12.3.2 **Dataset dictionary (`dataset_dictionary.layer2.5B.yaml`)**

* Entries for `validation_bundle_index_5B`, `validation_report_5B`, `validation_issue_table_5B`, and `validation_passed_flag_5B` MUST:

  * include `spec_version: {5B_spec_version}`,
  * reflect any changes to paths or partitioning.

Changes to **paths** or **partitioning keys** of S5 artefacts are considered **breaking** and require a major version bump.

12.3.3 **Artefact registry (`artefact_registry_5B.yaml`)**

* Registry entries for:

  * `validation_bundle_5B`,
  * `validation_passed_flag_5B`,
    MUST store:

* `spec_version: {5B_spec_version}`,

* dependencies on upstream segments as **version ranges** where relevant (e.g. “requires 2B_spec_version ≥ 1.2.0”).

If S5’s logic starts to rely on newer guarantees from upstream (e.g. new 3B virtual semantics), these minimum upstream versions MUST be updated in the registry.

---

12.4 **Compatibility contract with downstream consumers**

12.4.1 **What downstream may assume**

Layer-3 (6A/6B) and enterprise ingestion may assume:

* If `_passed.flag_5B` exists for `mf` and its digest verifies against `validation_bundle_5B` using the current bundle law, then:

  * all S0–S4 invariants described for the current `5B_spec_version` have been checked and passed, and
  * `s4_arrival_events_5B` is safe to treat as the authoritative arrival layer for that `mf`.

They MUST NOT assume:

* any specific internal evidence layout beyond what their own code supports for the declared `5B_spec_version`.

12.4.2 **Gating on version**

Downstream components SHOULD:

* advertise a supported version range for `5B_spec_version` (e.g. `"1.x.y"`),
* reject or enter “compat mode” when reading bundles whose `5B_spec_version` lies outside that range.

S5 MUST expose `5B_spec_version` in:

* `validation_report_5B`,
* any S5 receipt object,
* and, where feasible, as a top-level field in `index.json` (if allowed by the index schema).

---

12.5 **Cross-version coexistence**

If multiple `5B_spec_version` values exist across different worlds:

* It is acceptable for:

  * `mf₁` to have a v1 bundle,
  * `mf₂` to have a v2 bundle,
    as long as each fingerprint is internally consistent (all S0–S5 runs and artefacts for that world share the same `5B_spec_version`).

Within a single `manifest_fingerprint`:

* Mixed `5B_spec_version` values across S0–S5 or across multiple S5 runs are **not permitted**.
* Orchestration MUST ensure that:

  * all 5B runs for `mf` use the same `5B_spec_version`, or
  * treat divergent runs as separate / incompatible and never publish a combined `_passed.flag_5B`.

---

12.6 **Non-negotiable invariants**

Regardless of version, S5 MUST always:

* be RNG-free,
* treat upstream and S0–S4 artefacts as immutable inputs,
* enforce that `_passed.flag_5B` is computed from a canonical bundle index + hash law,
* refuse to mark 5B PASS if any S0–S4 invariant, RNG accounting check, or bundle integrity check fails.

These behaviours are part of the **contract of 5B as a segment**; any intent to change them would require not just a `5B_spec_version` bump but also a broader redesign of the engine and is out of scope for ordinary versioning.

---

## 13. Appendix A — Symbols & notational conventions *(Informative)*

This appendix is **informative**. It fixes shorthand and symbols used in S5 so the binding sections stay readable.

---

### 13.1 Identity & scope

* `mf` — shorthand for `manifest_fingerprint` (world identity; one S5 run per `mf`).

* `ph` — shorthand for `parameter_hash` (5A/5B parameter-pack identity).

* `sid` — shorthand for `scenario_id`.

* `seed` — RNG identity for an arrival realisation.

* `run_id` — execution identity for a particular engine run; **never** influences S5 data content.

* **5B run identity** (upstream):

  * `(ph, mf, sid, seed)` — quadruple for a single S2/S3/S4 run.

* **S5 identity** (this state):

  * `(mf, 5B_spec_version)` — S5’s logical identity for a validation bundle.

---

### 13.2 Sets & domains

* `D₃` — domain of S3 under `mf`: all `(ph, sid, seed, entity, bucket_index)` with a defined `N`.
* `D₄` — domain of S4 under `mf`: all arrival rows in `s4_arrival_events_5B`.
* `Seeds(mf)` — set of seeds seen in S3/S4 for `mf`.
* `Scenarios(mf)` — set of `scenario_id` values seen in S3/S4 for `mf`.
* `Params(mf)` — set of `parameter_hash` values seen in S2/S3/S4 for `mf`.

Unless otherwise stated, **all quantifiers in S5 are over the discovered domain** `(Params(mf), Scenarios(mf), Seeds(mf))`.

---

### 13.3 Counts & metrics

* `N_{e,b}` or `N` — integer bucket-level count from S3 for entity `e` and bucket `b`.
* `N_arrivals_total` — total number of rows in `s4_arrival_events_5B` under `mf`.
* `n_buckets_total` — total S3 rows under `mf`.
* `n_buckets_nonzero` — S3 rows with `N>0`.
* `n_arrivals_physical` — arrivals with `is_virtual = false`.
* `n_arrivals_virtual` — arrivals with `is_virtual = true`.

These are *metrics* S5 computes; authoritative definitions of N live in S3.

---

### 13.4 Bundle & hashing notation

* `E` — ordered list of bundle members from `index.json`:

  ```text
  E = [e₁, e₂, …, eₖ]
  ```

  where each `eᵢ` has at least a `path` and `sha256_hex`.

* `path(eᵢ)` — relative path of bundle member `eᵢ` inside `fingerprint={mf}` directory.

* `bytes(eᵢ)` — **raw bytes** of the file at `path(eᵢ)`.

* **Bundle concatenation:**

  ```text
  bytes_concat = bytes(e₁) || bytes(e₂) || … || bytes(eₖ)
  ```

  where `E` is sorted in ASCII-lex order of `path(eᵢ)`.

* **Bundle digest:**

  ```text
  bundle_sha256 = SHA256(bytes_concat)
  ```

* `<bundle_sha256_hex>` — 64-character lowercase hex encoding of `bundle_sha256`.

This is the value written into `_passed.flag_5B` as:

```text
sha256_hex = <bundle_sha256_hex>
```

---

### 13.5 RNG-related symbols (for validation only)

S5 itself is RNG-free, but it validates RNG usage for 5B.S2/S3/S4. Shorthand:

* `rng_envelope` — shared schema for RNG events (fields like `seed`, `parameter_hash`, counters, `draws`, `blocks`).

* `substream_label` — string label for RNG families (e.g. `"latent_field"`, `"bucket_counts"`, `"arrival_time_jitter"`, `"arrival_site_pick"`, `"arrival_edge_pick"`).

* `rng_trace_log` — aggregated table of RNG usage (draws/blocks per `(module, substream_label, seed, parameter_hash, run_id)`).

* `draws_expected(family)` — expected number of Philox draws for a given RNG family (computed from S2/S3/S4 domain).

* `draws_actual(family)` — number of draws recorded in RNG logs for that family.

S5’s RNG acceptance condition is, conceptually:

```text
∀ family: draws_actual(family) = draws_expected(family)
```

plus counter monotonicity (no overlaps/gaps).

---

### 13.6 Routing & time shorthand

* `site_id` — physical outlet identifier from `site_locations`.
* `edge_id` — virtual edge identifier from `edge_catalogue_3B`.
* `is_virtual` — boolean flag, true iff routed via virtual edges.
* `tzid` — IANA timezone identifier.
* `ts_utc` — UTC timestamp of an arrival as written by S4.
* `ts_local_*` — local timestamps derived from `ts_utc` using 2A’s `tz_timetable_cache` and routing policies (physical or virtual).

S5 **never** writes or changes these; it only checks that values produced by S4 are compatible with upstream semantics.

---

### 13.7 Error code prefix

All S5 error codes follow the pattern:

```text
5B.S5.SOMETHING_DESCRIPTIVE
```

e.g. `5B.S5.COUNT_MISMATCH_S3_S4`, `5B.S5.BUNDLE_DIGEST_MISMATCH`.

These codes are the values emitted in S5’s run-report `error_code` field and referenced throughout §9.

---