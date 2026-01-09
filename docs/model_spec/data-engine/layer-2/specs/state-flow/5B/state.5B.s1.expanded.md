# 5B.S1 — Time grid & grouping plan (Layer-2 / Segment 5B)

## 1. Purpose & scope *(Binding)*

This section defines the purpose and scope of **5B.S1 — Time grid & grouping plan (Layer-2 / Segment 5B)**. It is binding on any implementation of this state and on all downstream 5B states that consume its outputs.

---

### 1.1 Role of 5B.S1 in the engine

Given a closed world sealed by **5B.S0** for a particular `(parameter_hash, manifest_fingerprint)` and a chosen `scenario_set_5B`, **5B.S1** is the **deterministic planning step** that:

1. **Fixes the arrival time grid** over the scenario horizon(s):

   * Constructs a canonical set of **time buckets** for each scenario in `scenario_set_5B`,
   * expresses each bucket in **UTC** and attaches **local-time metadata** (day-of-week, local clock position, scenario tags), in a way that is consistent with:

     * the 5A scenario manifest and scenario surfaces, and
     * the civil-time law from 2A (`tz_timetable_cache`, gap/fold semantics).

2. **Assigns grouping for the latent field (LGCP) and/or shared dynamics**:

   * Deterministically assigns each in-scope `(merchant, zone[, channel])` to a **group_id**,
   * where each group defines a unit over which S2 will later draw a shared latent field or other shared stochastic structure.

5B.S1 is **RNG-free** and **does not produce any arrivals, counts or stochastic fields**. It only prepares the **canvas** (time grid + groups) on which later 5B states (S2–S4) will realise the arrival process.

---

### 1.2 Objectives

5B.S1 MUST:

* **Align the 5B time grid with upstream authorities**

  * Use the 5A scenario manifest and scenario surfaces as the **only authority** on:

    * which `scenario_id` values exist for `(ph, mf)`,
    * each scenario’s horizon start/end (in UTC),
    * any scenario-specific labels (baseline, stress, holiday, etc.).
  * Use 2A (`site_timezones`, `tz_timetable_cache`) as the **only authority** on mapping between UTC and local time, including gap/fold behaviour.

* **Provide a canonical horizon grid for 5B**

  * Build a **stable, schema-governed time grid** (e.g. `s1_time_grid_5B`) that:

    * covers the full scenario horizon(s) at the chosen bucket granularity,
    * ensures no overlaps or gaps,
    * and can be joined unambiguously to:

      * 5A’s scenario-local intensity surfaces, and
      * 5B’s later per-bucket/arrival artefacts.

* **Define latent grouping deterministically**

  * Apply a 5B-local grouping policy (config) to deterministically map each in-scope `(merchant, zone[, channel])` into:

    * a finite set of **group_id** values, with 1-to-1 membership per key,
    * such that S2 can treat each group as a unit for latent field draws or other shared dynamics.
  * Ensure that the same `(ph, mf)` and grouping policy always yield the same group assignment, independent of `seed` or `run_id`.

* **Remain purely structural**

  * Restrict itself to planning operations:

    * defining time buckets,
    * tagging buckets with local time and scenario metadata,
    * defining group_ids and their membership;
  * and not perform any arrival-process maths (no λ transformations, no Poisson/NB/LGCP draws).

---

### 1.3 In-scope behaviour

The following activities are **in scope** for 5B.S1 and MUST be handled by this state (not duplicated elsewhere in 5B):

* **Time-grid construction**

  * For each `scenario_id ∈ scenario_set_5B`, derive the scenario horizon from the 5A manifest, and construct an ordered sequence of buckets over that horizon with:

    * `bucket_id` / `bucket_index`,
    * `bucket_start_utc`, `bucket_end_utc`,
    * scenario-local tags (baseline/stress, holiday windows, etc.),
    * and any 5B-specific labels needed by S2–S4.

* **Local-time annotation**

  * Using 2A’s civil-time law, attach local-time metadata to each bucket (e.g. local day-of-week, local time-of-day) in a way that:

    * is consistent with 2A’s `tz_timetable_cache` gap/fold semantics, and
    * does not overwrite or reinterpret 2A contracts.

  * If multiple tzids are relevant (e.g. per zone or per tz-group), define a clear, deterministic scheme for which local tz metadata is attached where (the detailed rules belong in later sections).

* **Domain discovery for grouping**

  * Determine the domain of entities to group, e.g.:

* `(merchant_id, zone_representation[, channel_group])` inferred from 5A’s scenario surfaces and 3A/2B/3B metadata,
  *Here `zone_representation` is the canonical “zone key” (either `(legal_country_iso, tzid)` or a reversible `zone_id`).*
    * filtered according to 5B’s spec and grouping policy.

* **Group assignment**

  * Apply a 5B grouping policy (config) to assign a `group_id` to each element in the grouping domain, e.g.:

    * each merchant-zone gets its own group (group = self), or
    * similar merchants/zones are pooled according to a policy (by MCC, region, size, etc.).

  * Emit a mapping dataset (e.g. `s1_grouping_5B`) that can be used by S2 to know which group(s) to draw latent fields for.

* **Consistency checks (structural)**

  * Ensure:

    * every in-scope `(merchant, zone[, channel])` appears in the grouping map exactly once,
    * every bucket in the time grid is fully specified (no missing start/end, no overlaps),
    * any required joins to 5A surfaces and 2A/2B/3A/3B metadata are key-complete at metadata level.

Any structural issues discovered here MUST be surfaced as S1 failures; later states must not attempt to repair the time grid or grouping.

---

### 1.4 Out-of-scope behaviour

The following are explicitly **out of scope** for 5B.S1 and MUST NOT be performed by this state:

* **Randomness and arrival realisation**

  * S1 MUST NOT:

    * consume any RNG streams,
    * produce any RNG events or traces,
    * sample latent fields or noise terms,
    * draw bucket counts or individual arrivals,
    * assign intra-bucket timestamps.

* **Changing intensity surfaces**

  * S1 MUST NOT:

    * read or alter 5A’s λ surfaces at row level to “massage” intensities,
    * rescale or reshape the intensities,
    * define any new λ-like quantity;
      it may only derive its grid so that later states can join to 5A’s surfaces cleanly.

* **Routing or geometry changes**

  * S1 MUST NOT:

    * change routing law, site weights, or alias tables from 2B/3B,
    * change zone allocations from 3A,
    * alter site locations or tzids from 1B/2A.

  Any use of routing/zone/virtual metadata in S1 is strictly for **domain discovery and tagging**, not for changing the routing semantics.

* **Segment-level PASS/HashGate for 5B**

  * S1 does not make a segment-wide PASS decision for 5B and does not write 5B’s final validation bundle or `_passed.flag`.
  * Its success/failure contributes to that decision, but the final 5B HashGate is owned by a dedicated validation state.

---

### 1.5 Downstream obligations

This section imposes the following obligations on downstream 5B states:

* **S2 (latent fields) MUST:**

  * treat the S1 time grid as the **only** authority on the bucket structure for the horizon;
  * only sample latent fields over buckets defined by S1;
  * only share latent structure across entities that share the same `group_id` as defined by S1.

* **S3–S4 (counts & arrivals) MUST:**

  * align their per-bucket work with the S1 grid (bucket IDs/indices),
  * avoid defining ad-hoc bucket boundaries independent of S1.

* **No re-derivation of grouping**

  * No later 5B state may re-classify or re-group merchants/zones for latent-field purposes; they MUST consume the `group_id` mapping produced by S1. If a new grouping policy is required, S1 MUST be re-run under a new `parameter_hash` or spec version.

Within this scope, **5B.S1** provides a deterministic, RNG-free foundation for time and grouping: later states add stochastic behaviour and routing on top, but they all operate on the same, canonical grid and grouping plan fixed here.

---

### Contract Card (S1) - inputs/outputs/authorities

**Inputs (authoritative; see Section 2 for full list):**
* `s0_gate_receipt_5B` - scope: FINGERPRINT_SCOPED; source: 5B.S0
* `sealed_inputs_5B` - scope: FINGERPRINT_SCOPED; source: 5B.S0
* `scenario_manifest_5A` - scope: FINGERPRINT_SCOPED; source: 5A.S0
* `merchant_zone_profile_5A` - scope: FINGERPRINT_SCOPED; source: 5A.S1
* `shape_grid_definition_5A` - scope: FINGERPRINT_SCOPED; source: 5A.S2
* `class_zone_shape_5A` - scope: FINGERPRINT_SCOPED; source: 5A.S3
* `merchant_zone_scenario_local_5A` - scope: FINGERPRINT_SCOPED; source: 5A.S4
* `merchant_zone_scenario_utc_5A` - scope: FINGERPRINT_SCOPED; source: 5A.S4
* `zone_alloc` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 3A.S5
* `zone_alloc_universe_hash` - scope: FINGERPRINT_SCOPED; source: 3A.S5
* `site_timezones` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 2A.S2
* `tz_timetable_cache` - scope: FINGERPRINT_SCOPED; source: 2A.S3 (optional)
* `time_grid_policy_5B` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `grouping_policy_5B` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required

**Authority / ordering:**
* S1 is the sole authority for 5B time-grid and grouping plans.

**Outputs:**
* `s1_time_grid_5B` - scope: FINGERPRINT_SCOPED; scope_keys: [manifest_fingerprint, scenario_id]
* `s1_grouping_5B` - scope: FINGERPRINT_SCOPED; scope_keys: [manifest_fingerprint, scenario_id]

**Sealing / identity:**
* External inputs MUST appear in `sealed_inputs_5B` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or policy violations -> abort; no outputs published.

## 2. Preconditions & dependencies *(Binding)*

This section defines **when 5B.S1 is allowed to run** and **what it may depend on**. If any precondition fails, S1 MUST NOT produce outputs and MUST be treated as FAIL for that run.

---

### 2.1 Dependency on 5B.S0 (Gate & sealed inputs)

Before 5B.S1 may execute for a given `(parameter_hash = ph, manifest_fingerprint = mf)`:

1. **S0 outputs MUST exist and be valid**

   * A single `s0_gate_receipt_5B` file MUST exist at:
     `data/layer2/5B/s0_gate_receipt/manifest_fingerprint=mf/s0_gate_receipt_5B.json`
   * A single `sealed_inputs_5B` file MUST exist at:
     `data/layer2/5B/sealed_inputs/manifest_fingerprint=mf/sealed_inputs_5B.json`

2. **Receipt and inventory MUST be consistent**

   * `s0_gate_receipt_5B` MUST:

     * be schema-valid,
     * embed `manifest_fingerprint = mf` and `parameter_hash = ph`,
     * embed a `scenario_set` set that matches the `scenario_set_5B` under which S1 is being invoked,
     * embed a `sealed_inputs_digest` value.
   * Recomputing the digest of `sealed_inputs_5B` for `mf` MUST equal the `sealed_inputs_digest` embedded in the receipt.

If any of these checks fail, 5B.S1 MUST abort and MUST NOT attempt to reconstruct its own sealed-input universe.

---

### 2.2 Upstream segment gates (indirect preconditions)

5B.S1 does not re-verify upstream bundles itself; it relies on the fact that 5B.S0 already did so.

As a precondition, S1 MUST confirm that `s0_gate_receipt_5B.upstream_segments` reports:

* `status = "PASS"` for all required upstream segments:
  `{1A, 1B, 2A, 2B, 3A, 3B, 5A}`.

If any required segment has `status ≠ "PASS"` in the receipt, S1 MUST treat this as a **hard gate failure** and MUST NOT proceed, even if the underlying upstream files appear to be present.

S1 MUST NOT independently re-hash or override upstream `_passed.flag` results; S0’s upstream status map is authoritative for gating.

---

### 2.3 Required configs & policies for S1

S1 depends on a small, explicit set of 5A/5B-level metadata and policies. As a precondition, the following artefacts MUST appear in `sealed_inputs_5B` with `status ∈ {REQUIRED, INTERNAL}`:

1. **From 5A (scenario & horizon)**

   * `scenario_manifest_5A` for `(ph, mf)` – the only authority on:

     * `scenario_id` values,
     * per-scenario horizon start/end in UTC.

2. **From 5B (local config)**

   * A **time-grid policy artefact** (name to be fixed, e.g. `time_grid_policy_5B`) describing:

     * bucket duration,
     * any allowed offsets,
     * whether different scenarios share or diverge in grid resolution.
   * A **grouping policy artefact** (e.g. `grouping_policy_5B`) describing:

     * which attributes S1 may use to group `(merchant, zone[, channel])`,
     * whether grouping is trivial (`group_id = self`) or pooled,
     * any exclusions or special cases (e.g. virtual-only or low-volume merchants).

These policies must be:

* discoverable via the 5B artefact registry,
* schema-valid (per `schemas.5B.yaml` or `schemas.layer2.yaml`), and
* listed in `sealed_inputs_5B` with correct `schema_ref` and `sha256_hex`.

If any required policy artefact is missing or invalid, S1 MUST fail before attempting to build the grid or grouping.

---

### 2.4 Data-plane access scope for S1

S1 is RNG-free, but it does need **domain and horizon context**. Its preconditions on data access are:

1. **Allowed sources (via sealed_inputs_5B + catalogue)**

   S1 MAY read, at **row level**, only:

   * 5A’s scenario-level metadata and, where needed, the **keys and horizon indices** from:

     * `scenario_manifest_5A`,
     * `merchant_zone_scenario_local_5A` (for domain discovery, not λ manipulation).
   * Any upstream `sealed_inputs_*` tables that help interpret domains (2A/2B/3A/3B/5A), as needed.

   S1 MAY *inspect metadata only* for:

   * 2A civil-time artefacts (`site_timezones`, `tz_timetable_cache`),
   * 2B, 3A, 3B routing/zone/virtual artefacts,
     as long as it does not scan bulk fact rows.

2. **Forbidden sources**

   * S1 MUST NOT read rows from large data-plane tables purely for time-grid or grouping decisions if the same information is available in smaller metadata/manifest tables.
   * S1 MUST NOT re-derive or transform λ values from 5A; it may join on keys and bucket indices but MUST NOT recompute intensities.

3. **Respect for `read_scope`**

   * For any artefact listed in `sealed_inputs_5B` with `read_scope = METADATA_ONLY`, S1 MUST NOT perform row-level reads.
   * If S1 requires row-level access to an artefact in the future, that artefact’s row must first be marked with `read_scope = ROW_LEVEL` in `sealed_inputs_5B` by S0/spec updates.

---

### 2.5 Invocation order within 5B

Within Segment 5B, S1 MUST only be run:

* **after** a successful S0 run for `(ph, mf)` (local PASS criteria from S0 satisfied), and
* **before** any S2/S3/S4 runs that depend on its time grid or grouping outputs.

S1 MUST NOT be invoked:

* concurrently with S0 for the same `(ph, mf)`, or
* after any S2–S4 run that assumes a different grid/grouping for the same `(ph, mf)`.

If S1 needs to change its grid or grouping policy for a world, that change MUST be expressed via a new `parameter_hash` and/or a new 5B spec version, followed by a fresh S0 and S1 run; it MUST NOT silently re-plan the grid in place under the same `{ph, mf}`.

---

## 3. Inputs & authority boundaries *(Binding)*

This section defines **what 5B.S1 is allowed to read** and **who is authoritative for what**. S1 MUST stay inside the closed world sealed by **5B.S0** and MUST NOT widen it.

---

### 3.1 Inputs S1 may use

S1 MAY only use artefacts that:

* are listed in `sealed_inputs_5B` for this `manifest_fingerprint`, and
* are resolved via the catalogue (dictionary + registry + upstream sealed-inputs), not hard-coded paths.

Within that, S1’s logical inputs are:

#### (a) From 5B.S0 (mandatory)

* `s0_gate_receipt_5B`

  * for `parameter_hash`, `manifest_fingerprint`, `seed`, `run_id`, `scenario_set`, and `upstream_segments`.

* `sealed_inputs_5B`

  * the whitelist of artefacts S1 is allowed to touch, plus:

    * `owner_segment`, `artifact_id`, `role`,
    * `schema_ref`, `path_template`, `read_scope`, `status`.

S1 MUST treat these as **primary gates**; if they disagree with the engine’s catalogue, S1 MUST side with S0 (and fail).

#### (b) From 5A — scenario & horizon (row-level allowed)

S1 MAY read rows from the following 5A artefacts (provided `read_scope = ROW_LEVEL` in `sealed_inputs_5B`):

* `scenario_manifest_5A`

  * authoritative list of `scenario_id` for `(ph, mf)`, plus `horizon_start_utc`, `horizon_end_utc`, and scenario labels.

* `merchant_zone_scenario_local_5A` (or the agreed S4 egress)

  * only for **key and bucket indexing**, e.g.:

    * which `(merchant, zone[, channel])` are in scope for each `scenario_id`,
    * which local bucket indices exist;
  * NOT for modifying λ or re-scaling intensities.

Other 5A surfaces (e.g. `merchant_zone_baseline_local_5A`, overlays, UTC projections) MAY be read **only** for structural alignment (e.g. bucket index domains) and **never** to recompute λ.

#### (c) From 2A — civil time metadata (metadata-only)

S1 MAY use 2A artefacts **for metadata and horizon sanity**, not for per-site iteration:

* `tz_timetable_cache`

  * as the only authority for gap/fold semantics and UTC↔local mapping rules.

* `site_timezones`

  * only to infer **which tzids are present** in the world or, where needed, to know which tzids are associated with which zones / merchant groups at a metadata level (e.g. distinct tzids per zone).
  * S1 MUST NOT perform full per-site scans just to build the time grid; it should rely on smaller surfaces where possible.

Row-level reads from these tables MUST be limited to what’s strictly needed to understand tzid domains and horizon intersections; most S1 consumers will only need tzid sets and references.

#### (d) From 2B / 3A / 3B — domain hints (metadata-only)

S1 MAY use routing/zone/virtual metadata to help define its **grouping domain**:

* 2B: `s1_site_weights`, `s4_group_weights` — to see which merchants/zones/tz-groups exist.
* 3A: `zone_alloc`, `zone_alloc_universe_hash` — to know the zone universe per merchant/country.
* 3B: `virtual_classification_3B`, `virtual_settlement_3B` — to distinguish physical vs purely virtual merchants, if grouping policy cares.

For S1 these are **metadata sources only**:

* S1 MUST NOT change routing law, zone allocation, or virtual semantics.
* Row-level access SHOULD be limited to keys and zone/tzid identifiers; no aggregations or re-weighting is allowed.

#### (e) From 5B — time-grid & grouping policies (row-level)

S1 MUST read the 5B-local config/policy artefacts declared as `REQUIRED` or `INTERNAL` in `sealed_inputs_5B`, including:

* `time_grid_policy_5B` (name to be fixed)

  * bucket size, alignment rules, any per-scenario overrides.

* `grouping_policy_5B`

  * which attributes (MCC, zone, region, size, virtual flag, etc.) S1 may use to form group_ids.

These are small, schema-governed configs (JSON/YAML or equivalent). S1 MUST treat them as **the only source** for its time-grid and grouping rules; it MUST NOT encode those rules directly in code.

---

### 3.2 Authority boundaries (who owns what)

Within S1, authority is divided as follows:

* **World identity & sealed inputs**

  * **Owner:** 5B.S0
  * S1 MUST NOT add/remove artefacts from the closed world; it only consumes what S0 has sealed.

* **Scenarios & horizons**

  * **Owner:** 5A
  * S1 MUST treat 5A’s scenario manifest as the only authority on:

    * which scenarios exist for `(ph, mf)`,
    * each scenario’s UTC horizon.
  * S1 MAY propose a finer time grid inside that horizon, but MUST NOT extend it or silently drop parts of it.

* **Civil time & gap/fold semantics**

  * **Owner:** 2A
  * S1 MUST follow 2A’s rules for:

    * how local time is derived from UTC,
    * how gaps and folds are treated.
  * If S1 annotates buckets with local information, it MUST do so in a way that is consistent with `tz_timetable_cache`; it MUST NOT invent a separate time model.

* **Routing, zones, virtual overlay**

  * **Owner:** 2B / 3A / 3B
  * S1 MAY use routing/zone/virtual metadata to decide grouping (e.g. pool similar merchants), but:

    * MUST NOT change any weights, alias tables, or zone assignments;
    * MUST NOT reinterpret `is_virtual` or edge universes;
    * MUST NOT emit any new routing artefacts.

* **Intensity surfaces (λ)**

  * **Owner:** 5A
  * S1 MUST NOT rescale, recompute, or otherwise transform 5A’s λ values; it may only align grids and domains to them (so S2–S4 can join cleanly).

* **Time grid & grouping plan**

  * **Owner:** 5B.S1
  * S1 owns the shape of its time grid and the mapping `(merchant, zone[, channel]) → group_id`, subject to the constraints above.
  * Later 5B states MUST treat S1’s outputs as authoritative for these concerns.

---

### 3.3 Prohibited inputs & behaviours

To keep boundaries clean, S1 MUST NOT:

* Read any artefact **not** listed in `sealed_inputs_5B` for this `mf`.

* Re-query the catalogue to “discover new” upstream artefacts beyond what S0 sealed.

* Perform full data-plane scans of large tables purely to build the time grid or grouping if equivalent information is available via:

  * scenario manifests,
  * upstream sealed-input tables, or
  * lightweight dimension tables.

* Use any external source (env vars, ad-hoc configs, network calls) as a hidden input into time-grid or grouping logic.

If S1 finds that it “needs” something that is not available under these rules, that is a **spec / configuration issue**, not a runtime permission: S1 MUST fail rather than widening its input universe.

---

## 4. Outputs (datasets) & identity *(Binding)*

This section fixes **what 5B.S1 produces** and **how those outputs are identified**. These outputs are **RNG-free** and must be deterministic functions of the sealed world from 5B.S0.

5B.S1 produces **two required datasets**:

1. `s1_time_grid_5B` — the canonical time-bucket grid over the 5B horizon(s).
2. `s1_grouping_5B` — the mapping from `(merchant, zone[, channel])` into latent-field groups.

No other datasets may be introduced by this state unless the spec and schemas are updated.

---

### 4.1 Identity scope (world vs run vs scenario)

All S1 outputs are determined by:

* `parameter_hash = ph`
* `manifest_fingerprint = mf`
* `scenario_set_5B` (from S0 + 5A)

and are **independent of**:

* `seed`
* `run_id`

Binding rules:

* For a fixed `(ph, mf, scenario_id)` and fixed S1 policies/configs, re-running S1 MUST produce **byte-identical** `s1_time_grid_5B` and `s1_grouping_5B` content.
* Changing `seed` or `run_id` MUST NOT change S1 outputs.
* Both datasets are **scenario-aware**: they MUST carry `scenario_id` as part of their logical key so that different scenarios can have different grids/groupings if the policy demands it.

---

### 4.2 `s1_time_grid_5B` — horizon time-bucket grid

**Role**

` s1_time_grid_5B` is the **authoritative 5B time grid**. Every later 5B state (S2–S4) MUST:

* reference this grid when:

  * sampling latent fields (S2),
  * drawing bucket counts (S3),
  * placing arrivals in time (S4),
* and MUST NOT invent its own bucket boundaries.

**Logical content (high level)**

Each row represents one time bucket for a `(scenario_id, bucket_index)` pair and MUST include at least:

* `manifest_fingerprint`
* `parameter_hash`
* `scenario_id`
* `bucket_index` (unique per scenario; contiguous and ordered)
* `bucket_start_utc`, `bucket_end_utc`
* basic local-time tags (e.g. `local_day_of_week`, `local_minutes_since_midnight`) as derived from 2A, and
* scenario tags from 5A (e.g. `is_baseline`, `is_stress`, `is_payday_bucket`, etc.) as needed by later states.

Precise column list, types, and any additional tags are fixed in `schemas.5B.yaml#/model/s1_time_grid_5B`.

**Identity**

* World: `(ph, mf)`
* Scenario: `scenario_id`

There MUST be a **complete, non-overlapping** set of buckets covering each scenario’s horizon as defined by 5A; that is part of S1’s acceptance criteria (later section).

---

### 4.3 `s1_grouping_5B` — latent-field grouping map

**Role**

`s1_grouping_5B` is the **only authority** for mapping in-scope entities to latent-field groups. S2 MUST use this mapping to decide:

* which groups to draw latent fields for, and
* which merchants/zones share those fields.

**Logical content (high level)**

Each row represents a single entity to be grouped (typically a `(merchant, zone[, channel])` combination) in a given scenario, and MUST include at least:

* `manifest_fingerprint`
* `parameter_hash`
* `scenario_id`
* `merchant_id`
* `zone_representation` (e.g. `tzid` or `(country, tzid)` depending on your Layer-1 convention)
* optional: `channel_group` or similar, if grouping policy is channel-aware
* `group_id` — an opaque identifier (string or integer) used by S2 to index latent fields.

Constraints:

* For any fixed `(mf, ph, scenario_id)` and grouping policy:

  * each in-scope `(merchant, zone[, channel])` MUST appear **exactly once**,
  * group_ids MUST form a finite set per scenario,
  * group assignment MUST be deterministic (no RNG).

Exact column definitions live under `schemas.5B.yaml#/model/s1_grouping_5B`.

**Identity**

* World: `(ph, mf)`
* Scenario: `scenario_id`

Grouping MAY be identical across scenarios (e.g. same group_ids reused), but the dataset stays keyed per `(scenario_id, merchant, zone[, channel])` so that scenario-specific grouping is possible without changing the schema.

---

### 4.4 Required vs optional outputs

For 5B.S1:

* `s1_time_grid_5B` — **REQUIRED**, `final_in_state: true`, not final in segment.
* `s1_grouping_5B` — **REQUIRED**, `final_in_state: true`, not final in segment.

No optional S1 outputs are defined in this spec. If in future you add:

* a group manifest (e.g. per-group summary stats), or
* a per-scenario horizon summary,

those would be additive and must be introduced via an updated spec and schema anchors.

---

### 4.5 Relationship to downstream states

* **S2 (latent fields)** MUST:

  * read `s1_time_grid_5B` to know which `(scenario_id, bucket_index)` to draw fields over, and
  * read `s1_grouping_5B` to know which `(merchant, zone[, channel])` belong to each group.

* **S3–S4 (counts, arrival times, routing)** MUST:

  * align per-bucket work with `s1_time_grid_5B` (same `scenario_id` + `bucket_index`),
  * treat grouping as a planning concern only (they do not change group_ids).

No later 5B state may:

* change `s1_time_grid_5B` or `s1_grouping_5B` in-place,
* define alternative grids or grouping maps for the same `(ph, mf, scenario_id)`.

Any change to the time-grid or grouping semantics requires a new `parameter_hash` and/or 5B spec version and a new S0+S1 run.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

To keep **one source of truth** for the S1 contracts, field-level requirements live exclusively in:

* docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml
* docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml
* docs/model_spec/data-engine/layer-2/specs/contracts/5B/artefact_registry_5B.yaml

This section summarises the binding behaviour for the two S1 datasets and points to the canonical entries that govern columns, partitions, and manifest wiring.

S1 produces:

1. `s1_time_grid_5B` — the canonical bucket plan for each `scenario_id`.
2. `s1_grouping_5B` — the deterministic group membership map for every in-scope `(merchant, zone[, channel])`.

No other datasets may be emitted unless those contracts are extended first.

### 5.1 `s1_time_grid_5B`

* **Schema anchor:** `schemas.5B.yaml#/model/s1_time_grid_5B`
* **Dictionary entry:** `datasets[].id == "s1_time_grid_5B"`
* **Registry manifest key:** `mlr.5B.model.s1_time_grid`

Binding rules:

* The dictionary path (`data/layer2/5B/s1_time_grid/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…`) and partition keys `[manifest_fingerprint, scenario_id]` are normative; S1 MUST write exactly there and nowhere else.
* Row content (bucket indices, UTC/local timing metadata, scenario tags) MUST match the schema pack’s definitions. This spec constrains behaviour (no gaps/overlaps, deterministic ordering) but the schema is the shape authority.
* Dependencies listed in the registry (S0 gate receipt, 5A scenario manifest, 5B time-grid policy) are the only artefacts S1 may read for this output; anything else must first be added to `sealed_inputs_5B`.
* Under a fixed `(parameter_hash, manifest_fingerprint)`, re-running S1 MUST regenerate byte-identical files; all variability (e.g. different bucket duration choices) requires a contract update.

### 5.2 `s1_grouping_5B`

* **Schema anchor:** `schemas.5B.yaml#/model/s1_grouping_5B`
* **Dictionary entry:** `datasets[].id == "s1_grouping_5B"`
* **Registry manifest key:** `mlr.5B.model.s1_grouping`

Binding rules:

* The grouping domain is fixed elsewhere in this spec; every in-scope entity MUST appear exactly once in this dataset with the deterministic `group_id` emitted by the current grouping policy pack.
* Column set, allowed enums, and optional metadata fields are governed entirely by the schema pack. If the grouping policy introduces new tags, the schema/dictionary must be updated before S1 writes them.
* Partitioning/ordering rules from the dictionary (`fingerprint={manifest_fingerprint}/scenario_id={scenario_id}`; sorted by scenario then merchant→zone) are mandatory for deterministic hashing and MUST be honoured.
* Registry dependencies (sealed inputs, grouping policy config, upstream zone/intensity surfaces) define the only artefacts S1 may touch to build the grouping. Any new dependency requires a registry + sealed-inputs update first.

With these references, downstream agents can always consult the contract files for exact shapes, while this state spec captures the behavioural guarantees (determinism, dependency boundaries, and identity law).
## 6. Deterministic algorithm (RNG-free) *(Binding)*

This section defines the **exact, RNG-free algorithm** for **5B.S1 — Time grid & grouping plan**. For a fixed:

* `parameter_hash = ph`
* `manifest_fingerprint = mf`
* `scenario_set_5B`

and fixed S1 policies/configs, the algorithm MUST produce **byte-identical** `s1_time_grid_5B` and `s1_grouping_5B` regardless of `seed` or `run_id`.

No Philox streams may be consumed and no RNG events may be emitted.

---

### 6.1 Step 0 — Load S0 context and validate

1. **Read S0 outputs**

   * Load `s0_gate_receipt_5B@mf` and `sealed_inputs_5B@mf`.
   * Validate both against their schemas.

2. **Check identity consistency**

   * Confirm:

     * `s0_gate_receipt_5B.manifest_fingerprint = mf`
     * `s0_gate_receipt_5B.parameter_hash = ph`
     * `scenario_set` from the receipt equals the runtime `scenario_set_5B`.

3. **Check upstream status map**

   * Ensure `upstream_segments[seg].status = "PASS"` for all required segments `{1A,1B,2A,2B,3A,3B,5A}`.
   * If any fails, S1 MUST abort with an appropriate error.

---

### 6.2 Step 1 — Load S1 policies

Using `sealed_inputs_5B` + catalogue:

1. **Resolve time-grid policy**

   * Locate the artefact designated as `time_grid_policy_5B` (exact ID per registry).
   * Load it into memory and validate against its schema.
   * Extract:

     * `bucket_duration_seconds` (or equivalent),
     * any allowed alignment rules (e.g. horizon aligned to midnight, to scenario boundaries, etc.),
     * any scenario-specific overrides.

2. **Resolve grouping policy**

   * Locate and validate `grouping_policy_5B`.
   * Extract:

     * the grouping unit (e.g. `(merchant_id, zone_representation[, channel_group])`),
     * which attributes may be used (e.g. MCC, country, tzid, region, virtual flag),
     * whether grouping is trivial (`group_id = self`) or pooled,
     * any explicit “must not group” or “must group together” constraints.

If either policy is missing or invalid, S1 MUST fail before touching any other artefacts.

---

### 6.3 Step 2 — Derive scenario horizons

For each `scenario_id ∈ scenario_set_5B`:

1. **Read 5A scenario manifest**

   * From `scenario_manifest_5A@mf`, read rows for this `scenario_id`.
   * Extract:

     * `horizon_start_utc(s)`
     * `horizon_end_utc(s)`
     * scenario tags (e.g. baseline/stress/holiday).

2. **Apply time-grid policy**

   * Use `bucket_duration_seconds` and alignment rules to derive a **canonical sequence of buckets** for scenario `s`:

     * starting at or inside `[horizon_start_utc(s), horizon_end_utc(s))`,
     * covering the entire horizon with no gaps or overlaps,
     * each bucket `b` defined by `(bucket_start_utc(s,b), bucket_end_utc(s,b))`.

   * Resolve edge behaviour deterministically (e.g. truncate final bucket vs require exact multiple) as defined by the time-grid policy; this MUST be documented in that policy’s schema description.

3. **Assign bucket indices**

   * For each scenario `s`, assign `bucket_index` as:

     * integer sequence `0,1,2,…,B_s-1` (or `1..B_s`, but the convention MUST be fixed and documented),
     * sorted in increasing `bucket_start_utc`.

Intermediate result: a per-scenario list of `(scenario_id, bucket_index, bucket_start_utc, bucket_end_utc)`.

---

### 6.4 Step 3 — Annotate buckets with local-time & scenario tags

For each `(scenario_id, bucket_index)`:

1. **Scenario tags**

   * Copy scenario-level tags from `scenario_manifest_5A` into the bucket:

     * `scenario_is_baseline`
     * `scenario_is_stress`
     * any other standard flags (payday/holiday markers if they are scenario-level).

2. **Local-time computation (purely deterministic)**

   * If S1 needs local-time tags (day-of-week, clock time), it MUST:

     * choose a reference tzid for annotation (e.g. a canonical tzid per scenario or per zone if the policy requires), and
     * map `bucket_start_utc` into local time using 2A’s `tz_timetable_cache`, following its gap/fold rules.

   * Compute:

     * `local_day_of_week`
     * `local_minutes_since_midnight`
     * `is_weekend` (per policy).

   * S1 MUST NOT invent its own UTC↔local mapping; it must call through the rules defined by 2A.

3. **Record per-bucket row**

   * Construct a row for `s1_time_grid_5B` with:

     * `manifest_fingerprint = mf`
     * `parameter_hash = ph`
     * `scenario_id`
     * `bucket_index`
     * `bucket_start_utc`, `bucket_end_utc`
     * `bucket_duration_seconds`
     * local tags and scenario tags as defined above.

---

### 6.5 Step 4 — Discover grouping domain

S1 next discovers the **set of entities that must be assigned a group_id**.

1. **Domain from 5A**

   * From `merchant_zone_scenario_local_5A@mf`, for each `scenario_id ∈ scenario_set_5B`:

     * collect distinct keys of the form `(merchant_id, zone_representation[, channel_group])` where:

       * `lambda_local_scenario` exists (or other agreed intensity field),
       * the record is within the scenario horizon.

   * `zone_representation` is whatever representation S1/5B has chosen (e.g. `tzid` or `(country_iso, tzid)`), consistent with `schemas.5B.yaml`.

2. **Optional filters from grouping policy**

   * Apply any explicit inclusions/exclusions defined in `grouping_policy_5B`:

     * e.g. remove low-volume merchants flagged as “no LGCP”,
     * treat purely virtual merchants differently if the policy says so (using `virtual_classification_3B` metadata if allowed).

3. **Order the domain deterministically**

   * For each `scenario_id`, construct a list `D_s` sorted by:

     * `merchant_id`, then
     * `zone_representation`, then
     * (if present) `channel_group`.

This `D_s` is the **exact domain** `s1_grouping_5B` must cover for scenario `s`.

---

### 6.6 Step 5 — Assign group_ids deterministically

Using `grouping_policy_5B` and the ordered domain `D_s`:

1. **Choose grouping mode**

   * For each scenario `s`, determine from policy whether grouping is:

     * **trivial**: each `(merchant, zone[, channel])` gets its own group (group = self), or
     * **pooled**: entities are clustered based on policy attributes.

2. **Compute group keys**

   * For each entity in `D_s`, compute a **grouping key** according to the policy, e.g.:

     * `(MCC_group, region_id, virtual_flag)` or
     * `(merchant_size_bucket, tzid)`.

   * This must be deterministic and based only on sealed inputs and policy fields.

3. **Assign group_ids**

   * For each distinct grouping key in scenario `s`, in deterministic order:

     * assign a `group_id` (e.g. integer starting at 0 or 1, or a stable hash/label) that is:

       * unique per `(mf, ph, scenario_id)`,
       * reproducible across S1 re-runs.

   * For each entity in `D_s`, set `group_id` equal to the group_id of its grouping key.

4. **Build `s1_grouping_5B` rows**

   * For each `(merchant_id, zone_representation[, channel_group])` in `D_s`, construct a row with:

     * `manifest_fingerprint = mf`
     * `parameter_hash = ph`
     * `scenario_id`
     * `merchant_id`
     * `zone_representation`
     * optional `channel_group`
     * `group_id`

   * Ensure no duplicates for the PK.

**Important:** S1 MUST NOT perform any random tie-breaking; if the policy leads to ambiguous group membership, that is a policy error, not a runtime decision.

---

### 6.7 Step 6 — Write outputs atomically

1. **Write `s1_time_grid_5B`**

   * For each `scenario_id`, write a Parquet (or agreed) file at:

     ```text
     data/layer2/5B/s1_time_grid/manifest_fingerprint=mf/scenario_id={scenario_id}/s1_time_grid_5B.parquet
     ```

   * Enforce:

     * schema = `schemas.5B.yaml#/model/s1_time_grid_5B`,
     * partition keys `{manifest_fingerprint, scenario_id}`,
     * writer order: `bucket_index` ascending.

2. **Write `s1_grouping_5B`**

   * For each `scenario_id`, write:

     ```text
     data/layer2/5B/s1_grouping/manifest_fingerprint=mf/scenario_id={scenario_id}/s1_grouping_5B.parquet
     ```

   * Enforce:

     * schema = `schemas.5B.yaml#/model/s1_grouping_5B`,
     * partition keys `{manifest_fingerprint, scenario_id}`,
     * writer order: `merchant_id`, then `zone_representation`, then `channel_group` (if present).

3. **Atomicity & idempotency**

   * Writes MUST be atomic at file level (temp path + rename).
   * If files already exist for a given `(mf, scenario_id)`:

     * either verify they are byte-identical to what S1 would produce (idempotent re-run), or
     * treat the situation as a write conflict and fail; S1 MUST NOT silently overwrite differing outputs.

---

### 6.8 Prohibited actions in S1

Throughout all steps, S1 MUST NOT:

* call any RNG functions or consume Philox streams;
* read or alter 5A λ values except to derive **keys and bucket indices**;
* change or recompute any upstream artefact (routing, zones, virtual overlay, civil time, intensity surfaces);
* widen the sealed world beyond what `sealed_inputs_5B` and the catalogue expose.

Within these constraints, the algorithm above fully specifies the RNG-free behaviour of **5B.S1 — Time grid & grouping plan**.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S1’s datasets are identified, partitioned, ordered and updated**. It’s binding on implementations, the dataset dictionary, and downstream 5B states.

S1 outputs:

* `s1_time_grid_5B`
* `s1_grouping_5B`

---

### 7.1 Identity scopes

There are three relevant scopes:

1. **World identity (closed world)**

   * `world_id := (parameter_hash, manifest_fingerprint) = (ph, mf)`
   * Determines which artefacts are in the sealed world via S0.

2. **Scenario identity**

   * `scenario_id ∈ scenario_set_5B`
   * Determines which horizon and intensity surfaces from 5A we’re aligned to.

3. **Run identity (for logging only)**

   * `(seed, run_id)` — used in run-reporting, **not** in S1 dataset identity.

Binding rules:

* For fixed `(ph, mf, scenario_id)` and fixed S1 policies, `s1_time_grid_5B` and `s1_grouping_5B` MUST be **independent of `(seed, run_id)`**.
* Re-running S1 for the same `(ph, mf)` and `scenario_set_5B` MUST produce **byte-identical** content.

---

### 7.2 Partitioning & path law

S1 uses a **two-key partitioning**:

* Partition keys: `manifest_fingerprint`, `scenario_id`
* Path token for world: `fingerprint={manifest_fingerprint}`

Canonical paths:

* `s1_time_grid_5B`:

  ```text
  data/layer2/5B/s1_time_grid/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_time_grid_5B.parquet
  ```

* `s1_grouping_5B`:

  ```text
  data/layer2/5B/s1_grouping/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_grouping_5B.parquet
  ```

Binding constraints:

* **Path ↔ embed equality**

  * Every row in each file MUST have:

    * `manifest_fingerprint == {manifest_fingerprint}` from the path,
    * `scenario_id == {scenario_id}` from the path.

* **No seed/run partitioning**

  * `seed` and `run_id` MUST NOT appear as partition tokens or influence the path.
  * If they are logged at all, they appear only in run-report, not in S1 datasets.

---

### 7.3 Primary keys & writer ordering

#### `s1_time_grid_5B`

* **Logical primary key:**

  ```text
  (manifest_fingerprint, scenario_id, bucket_index)
  ```

* **Writer sort order:**

  * Within each `(mf, scenario_id)` file, rows MUST be sorted by `bucket_index` ascending.

* **Bucket identity:**

  * For a given `(mf, scenario_id)`, the set of `bucket_index` values MUST be:

    * contiguous, and
    * uniquely identify buckets (no duplicates).

#### `s1_grouping_5B`

* **Logical primary key:**

  ```text
  (manifest_fingerprint, scenario_id, merchant_id, zone_representation[, channel_group])
  ```

  (exact components per schema; the combination MUST be unique.)

* **Writer sort order:**

  * Within each `(mf, scenario_id)` file, rows MUST be sorted by:

    * `merchant_id`, then
    * `zone_representation`, then
    * `channel_group` (if present).

This deterministic ordering is required to:

* make file-level hashes reproducible, and
* simplify diffing across versions.

---

### 7.4 Merge & overwrite discipline

For a fixed `(ph, mf, scenario_id)`:

* There MUST be **at most one** `s1_time_grid_5B` file and **at most one** `s1_grouping_5B` file at their respective paths.
* S1 MAY be re-run for the same `(ph, mf, scenario_id)` only if:

  * the new outputs are **byte-identical** to the existing files (idempotent re-run), or
  * the engine treats the situation as a **conflict** and fails with a write-conflict error.

S1 MUST NOT:

* append to or “merge” multiple partial grids/groupings for the same `(ph, mf, scenario_id)`, or
* roll up grids across scenarios into a single file; scenario is a first-class partition.

**No cross-fingerprint merges:**

* Datasets for different `manifest_fingerprint` values MUST live in separate `fingerprint=…` directories and MUST NOT be combined by S1.

---

### 7.5 Downstream consumption discipline

Downstream 5B states MUST:

1. **Select world + scenario explicitly**

   * Choose a single `(mf, scenario_id)` and read:

     * `s1_time_grid_5B@fingerprint=mf/scenario_id={scenario_id}`,
     * `s1_grouping_5B@fingerprint=mf/scenario_id={scenario_id}`.

   * They MUST NOT infer a time grid or grouping by scanning across multiple `(mf, scenario_id)`.

2. **Treat S1 outputs as canonical**

   * S2 MUST use `s1_time_grid_5B` as the **only** bucket index/state for latent fields.
   * S2–S4 MUST treat `s1_grouping_5B.group_id` as the only grouping law; they MUST NOT re-group entities.

3. **Not modify S1 outputs**

   * No later state may alter, overwrite, or append to `s1_time_grid_5B` or `s1_grouping_5B`.
   * Any change to time-grid or grouping semantics requires:

     * a new `parameter_hash` and/or spec version,
     * a fresh S0 (gate) and S1 run.

Within these rules, S1’s outputs have a **clear, stable identity** and an unambiguous merge story: one world, one scenario, one grid, one grouping — deterministic and reusable by all later 5B states.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines **when 5B.S1 — Time grid & grouping plan is considered PASS** and what that implies for downstream 5B states (S2–S4) and orchestration. If any criterion here fails, S1 MUST be treated as **FAIL** for that `(parameter_hash, manifest_fingerprint)` and its outputs MUST NOT be used.

---

### 8.1 Local PASS criteria for 5B.S1

For a fixed `(ph, mf, scenario_set_5B)`, a run of S1 is **PASS** if and only if **all** of the following hold:

1. **S0 gate is valid and consistent**

   * `s0_gate_receipt_5B@mf` and `sealed_inputs_5B@mf`:

     * exist and pass schema validation, and
     * embed `parameter_hash = ph`, `manifest_fingerprint = mf`, and `scenario_set = scenario_set_5B`.
   * The recomputed digest of `sealed_inputs_5B` equals the `sealed_inputs_digest` in the receipt.
   * `upstream_segments[seg].status == "PASS"` for all required segments `{1A,1B,2A,2B,3A,3B,5A}`.

2. **Policies resolved and applied**

   * `time_grid_policy_5B` and `grouping_policy_5B`:

     * are present in `sealed_inputs_5B` with `status ∈ {REQUIRED, INTERNAL}`,
     * pass schema validation, and
     * are actually the ones used by the implementation (no hard-coded overrides).

3. **Time grid completeness & correctness**

   For every `scenario_id ∈ scenario_set_5B`:

   * S1 has materialised a single `s1_time_grid_5B` file under the correct `(mf, scenario_id)` partition.
   * The file:

     * passes schema validation,
     * has at least one row, and
     * for that `(mf, scenario_id)`:

       * `bucket_index` values are contiguous and unique,
       * buckets are ordered by `bucket_index` with strictly increasing `bucket_start_utc`,
       * for every row, `bucket_end_utc > bucket_start_utc`,
       * the union of all `[bucket_start_utc, bucket_end_utc)` intervals covers the scenario horizon from the 5A manifest with no internal gaps or overlaps (modulo any edge behaviour explicitly allowed by `time_grid_policy_5B`).

4. **Local-time & tag consistency (if used)**

   * Where S1 populates local-time fields and scenario tags:

     * local tags (day-of-week, minutes since midnight, weekend flag) are derived consistently from `bucket_start_utc` using 2A’s `tz_timetable_cache` and agreed tzid choice;
     * scenario tags (baseline/stress/etc.) match 5A’s scenario manifest.

5. **Grouping coverage & uniqueness**

   For every `scenario_id ∈ scenario_set_5B`:

   * S1 has materialised a single `s1_grouping_5B` file under the correct `(mf, scenario_id)` partition.
   * The file:

     * passes schema validation,
     * has at least one row (unless the grouping domain is explicitly and legitimately empty per policy), and
     * for that `(mf, scenario_id)`:

       * the set of `(merchant_id, zone_representation[, channel_group])` in `s1_grouping_5B` is exactly the domain discovered in Step 4 of §6 (no missing or extra keys),
       * there are **no duplicates** for the grouping PK `(manifest_fingerprint, scenario_id, merchant_id, zone_representation[, channel_group])`,
       * each such key is associated with exactly one `group_id`.

6. **Group_id well-formedness**

   * For each `(mf, ph, scenario_id)`:

     * the `group_id` domain is finite,
     * `group_id` values are of the type/form expected by the schema (e.g. integer or string),
     * there is at least a 1:1 mapping between grouping keys and group_ids (no “orphan” group_id with no members).

If all of the above conditions hold, S1 is **locally PASS**, and `s1_time_grid_5B` and `s1_grouping_5B` may be consumed by downstream 5B states.

---

### 8.2 Local FAIL conditions

5B.S1 MUST be considered **FAIL** if **any** of the following occurs:

1. **S0 or upstream gate failure**

   * S0 outputs are missing or invalid, or
   * `upstream_segments[seg].status ≠ "PASS"` for any required segment in `s0_gate_receipt_5B`.

2. **Missing or invalid policies**

   * `time_grid_policy_5B` or `grouping_policy_5B`:

     * are not present in `sealed_inputs_5B` as `REQUIRED`/`INTERNAL`, or
     * fail schema validation.

3. **Time grid problems**

   * Any scenario in `scenario_set_5B` lacks a corresponding `s1_time_grid_5B` partition;
   * `s1_time_grid_5B` fails schema validation;
   * bucket coverage does not span the scenario horizon as per 5A and policy;
   * buckets overlap or leave unaccounted gaps, other than any well-defined edge pattern allowed by policy.

4. **Grouping problems**

   * Any scenario lacks `s1_grouping_5B` where grouping policy expects a non-empty domain;
   * `s1_grouping_5B` fails schema validation;
   * there are duplicates for the grouping PK;
   * there exist in-scope `(merchant_id, zone_representation[, channel_group])` keys (as discovered from 5A domain) that are not present in `s1_grouping_5B`;
   * `group_id` values are malformed or violate the schema.

5. **Idempotency / overwrite issues**

   * Pre-existing S1 outputs for `(mf, scenario_id)` exist and differ byte-for-byte from what S1 would produce under the same `(ph, mf, scenario_set_5B)` and policy;
   * S1 attempts to write over such outputs without explicit conflict handling.

On FAIL, S1 MUST NOT leave the impression that the grid or grouping is usable; downstream gating obligations (below) ensure nothing runs on top of a failed S1.

---

### 8.3 Gating obligations for 5B.S1 itself

5B.S1 MUST enforce the following **before** declaring PASS:

1. **Read S0 and sealed inputs first**

   * It MUST validate S0 outputs and derive all permitted inputs from `sealed_inputs_5B` and the catalogue before constructing any grid or grouping.
   * It MUST NOT attempt to infer additional inputs beyond that universe.

2. **Complete all scenarios in `scenario_set_5B`**

   * S1 MUST either:

     * successfully build grid + grouping for **every** `scenario_id ∈ scenario_set_5B`, or
     * fail the entire run for that `(ph, mf)` (no partial success per scenario).

3. **All-or-nothing write**

   * S1 SHOULD write outputs per `(mf, scenario_id)` atomically, but MUST treat a failure for any scenario as a run failure and surface it via its error codes / run-report; it MUST NOT mask failures by leaving a mix of old and new outputs.

---

### 8.4 Gating obligations for downstream 5B states (S2–S4)

All later 5B states MUST treat S1 as a **hard gate**:

1. **Presence & schema checks**

   Before using S1 outputs, S2–S4 MUST:

   * verify that, for each `scenario_id` they intend to process:

     * `s1_time_grid_5B@fingerprint=mf/scenario_id={scenario_id}` exists and passes schema validation,
     * `s1_grouping_5B@fingerprint=mf/scenario_id={scenario_id}` exists and passes schema validation.

   If either is missing or invalid, the downstream state MUST fail fast and MUST NOT attempt to construct its own grid or grouping.

2. **Grid adherence**

   * S2 MUST sample latent fields only over `(scenario_id, bucket_index)` pairs present in `s1_time_grid_5B`; it MUST NOT create its own time partitioning.
   * S3–S4 MUST treat `(scenario_id, bucket_index)` from `s1_time_grid_5B` as the canonical bucket identifiers for counts and arrivals.

3. **Grouping adherence**

   * S2 MUST use `s1_grouping_5B.group_id` to define its field groups and MUST NOT regroup entities.
   * S3–S4 MAY carry `group_id` through for observability, but MUST NOT change it.

4. **No in-place modification**

   * No downstream state may overwrite or append rows to S1 datasets. If a different grid or grouping is required, that change MUST be done via:

     * a new `parameter_hash` and/or 5B spec version, and
     * a fresh S0 + S1 run for the new world.

---

### 8.5 Orchestration-level obligations

Orchestration / pipeline control MUST:

* treat absence or invalidity of S1 outputs for `(ph, mf, scenario_set_5B)` as **“5B not ready for latent fields / counts / arrivals”**;
* not start S2–S4 for that world until S1 has locally PASSed;
* surface S1’s status and error code (from §9) alongside S0’s status when diagnosing why 5B cannot proceed.

Under these conditions, 5B.S1 acts as a clean, deterministic gate: either the time grid and grouping plan are fully defined and consistent with upstream authorities, or **no latent-field or arrival work is allowed to proceed for that world**.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **only failure modes** 5B.S1 may surface and the **canonical error codes** it MUST use. All are **fatal** for S1: on any of these, S1 is **FAIL** for `(parameter_hash, manifest_fingerprint)` and its outputs MUST NOT be used.

All S1 error codes are namespaced as:

> `5B.S1.<CATEGORY>`

Downstream 5B states and orchestration MUST key on these codes, not free-text error messages.

---

### 9.1 Error code catalogue

#### (A) S0 / upstream gate prerequisites

1. **`5B.S1.S0_GATE_MISSING`**
   Raised when S1 cannot find valid S0 outputs for `mf`, e.g.:

   * `s0_gate_receipt_5B` or `sealed_inputs_5B` missing,
   * schema invalid, or
   * `sealed_inputs_digest` mismatch between receipt and recomputed digest.

2. **`5B.S1.UPSTREAM_NOT_PASS`**
   Raised when `s0_gate_receipt_5B.upstream_segments` reports any required upstream segment `{1A,1B,2A,2B,3A,3B,5A}` with `status ≠ "PASS"`.

S1 MUST NOT proceed beyond basic validation if either of these occurs.

---

#### (B) Policy / config issues

3. **`5B.S1.TIME_GRID_POLICY_MISSING`**
   Raised when `time_grid_policy_5B`:

   * is not listed in `sealed_inputs_5B` for this `mf`, or
   * cannot be resolved via the catalogue.

4. **`5B.S1.TIME_GRID_POLICY_SCHEMA_INVALID`**
   Raised when `time_grid_policy_5B` is found but fails schema validation (wrong shape, missing required fields, invalid values).

5. **`5B.S1.GROUPING_POLICY_MISSING`**
   Raised when `grouping_policy_5B`:

   * is not listed in `sealed_inputs_5B` for this `mf`, or
   * cannot be resolved via the catalogue.

6. **`5B.S1.GROUPING_POLICY_SCHEMA_INVALID`**
   Raised when `grouping_policy_5B` is found but fails schema validation.

---

#### (C) Time grid construction

7. **`5B.S1.SCENARIO_HORIZON_INVALID`**
   Raised when S1 cannot derive a valid, finite horizon for one or more `scenario_id ∈ scenario_set_5B` from `scenario_manifest_5A`, e.g.:

   * `horizon_start_utc` or `horizon_end_utc` missing/invalid,
   * `horizon_end_utc ≤ horizon_start_utc`.

8. **`5B.S1.TIME_GRID_INCOMPLETE`**
   Raised when, for any `scenario_id ∈ scenario_set_5B`:

   * no `s1_time_grid_5B` partition is produced, or
   * bucket coverage fails to span the scenario horizon as defined by 5A and policy (detected gaps).

9. **`5B.S1.TIME_GRID_OVERLAP_OR_ORDER`**
   Raised when, for any `(mf, scenario_id)`:

   * buckets overlap in time, or
   * `bucket_index` values are not unique/contiguous or not strictly ordered with `bucket_start_utc`.

10. **`5B.S1.TIME_GRID_SCHEMA_INVALID`**
    Raised when the written `s1_time_grid_5B` file fails validation against `schemas.5B.yaml#/model/s1_time_grid_5B` (missing columns, wrong types, invalid enum values).

---

#### (D) Grouping construction

11. **`5B.S1.GROUP_DOMAIN_DERIVATION_FAILED`**
    Raised when S1 cannot derive a coherent grouping domain from 5A (and optional upstream metadata), e.g.:

    * required keys `(merchant_id, zone_representation[, channel_group])` are missing or malformed,
    * policy says the domain should be non-empty but no entities qualify.

12. **`5B.S1.GROUP_ASSIGNMENT_INCOMPLETE`**
    Raised when, for any `scenario_id`:

    * some in-scope `(merchant_id, zone_representation[, channel_group])` (per domain discovery) are missing from `s1_grouping_5B`, or
    * the grouping policy results in ambiguous or conflicting assignments that S1 cannot resolve deterministically.

13. **`5B.S1.GROUPING_SCHEMA_INVALID`**
    Raised when the written `s1_grouping_5B` file fails schema validation against `schemas.5B.yaml#/model/s1_grouping_5B`.

14. **`5B.S1.GROUPING_DUPLICATE_KEY`**
    Raised when `s1_grouping_5B` contains duplicate logical keys:

    * same `(manifest_fingerprint, scenario_id, merchant_id, zone_representation[, channel_group])` appearing more than once.

15. **`5B.S1.GROUP_ID_DOMAIN_INVALID`**
    Raised when `group_id` values do not respect the schema/contract, e.g.:

    * non-finite or null `group_id`,
    * type mismatch (e.g. mixed integer/string when the schema expects one),
    * or other structural violations of the group_id domain.

---

#### (E) IO / idempotency

16. **`5B.S1.IO_WRITE_FAILED`**
    Raised when S1 fails to write `s1_time_grid_5B` or `s1_grouping_5B` atomically (filesystem/permission errors, partial writes detected).

17. **`5B.S1.IO_WRITE_CONFLICT`**
    Raised when S1 detects pre-existing S1 outputs for `(mf, scenario_id)` whose contents are **not** byte-identical to what the current run would produce under the same `(ph, mf, scenario_set_5B)` and policies.

In this case, S1 MUST NOT overwrite and MUST treat it as an idempotency/consistency violation.

---

### 9.2 Error payload & logging

For any of the above error codes, S1 MUST log/include at least:

* `error_code` (exactly as above),
* `parameter_hash`, `manifest_fingerprint`,
* `scenario_id` (if scenario-specific),
* and where applicable:

  * offending `segment_id` (for upstream issues),
  * offending `scenario_id` (for horizon/grid issues),
  * offending `merchant_id` / `zone_representation` (for grouping issues).

Human-readable messages are implementation-defined, but consumers MUST key off `error_code`.

---

### 9.3 Behaviour on failure

On any S1 error:

1. **Abort before downstream work**

   * S1 MUST NOT signal success to orchestration or downstream states.
   * S1 MUST NOT allow S2–S4 to treat `s1_time_grid_5B` or `s1_grouping_5B` as usable.

2. **No partial “success” claim**

   * Even if some scenarios succeed and others fail, S1 MUST treat the entire run as FAIL for `(ph, mf)` and surface an error code.

3. **File system state**

   * S1 SHOULD avoid leaving partially written or inconsistent files; if partial files exist due to an IO error, a subsequent run MUST either:

     * repair them by writing a fully consistent set of outputs, or
     * fail again with `IO_WRITE_CONFLICT` or `IO_WRITE_FAILED` and not allow downstream consumption.

4. **No upstream repair**

   * S1 MUST NOT attempt to modify repair upstream manifests, bundles or S0’s sealed inputs in response to any error; those issues must be fixed upstream or in S0.

Under this error model, consumers can reliably interpret S1’s outcome: if any `5B.S1.*` error is raised, the time grid and grouping plan for that world are **not valid**, and no latent-field or arrival states (S2–S4) may proceed.

---

## 10. Observability & run-report integration *(Binding)*

This section fixes **what 5B.S1 MUST report** and **how it integrates with the engine’s run-report system**. It doesn’t add new datasets; it binds how S1 describes what it did.

---

### 10.1 Run-report record for 5B.S1

For every attempted invocation of S1 on `(parameter_hash = ph, manifest_fingerprint = mf, seed, run_id)`, the engine MUST emit **one** run-report record with at least:

* `state_id = "5B.S1"`
* `parameter_hash = ph`
* `manifest_fingerprint = mf`
* `seed`
* `run_id`
* `scenario_set = sorted(scenario_set_5B)`
* `status ∈ {"PASS","FAIL"}`
* `error_code` (one of `5B.S1.*`, or `null` if `status = "PASS"`)
* `started_at_utc`
* `finished_at_utc`

Where this is stored (shared Layer-2 run-report table, per-segment report, etc.) is implementation detail, but S1 MUST provide these fields.

---

### 10.2 Minimum structural metrics

On completion (PASS or FAIL), the S1 run-report record MUST include, at minimum, the following metrics:

1. **Scenario coverage**

   * `scenario_count_requested = |scenario_set_5B|`
   * `scenario_count_succeeded`

     * number of scenarios for which both `s1_time_grid_5B` and `s1_grouping_5B` were successfully materialised and validated.
   * `scenario_count_failed = scenario_count_requested - scenario_count_succeeded`

   On overall `status = "PASS"`, we expect `scenario_count_succeeded == scenario_count_requested`.

2. **Time-grid scale**

   Derived from `s1_time_grid_5B` (for PASS runs):

   * `total_bucket_count`
   * Optionally, per-scenario summary (either as fields or in a structured payload):

     * `bucket_count_min` / `bucket_count_max` / `bucket_count_mean` across scenarios
     * `bucket_duration_seconds` (if constant), or indication of multiple durations.

3. **Grouping scale**

   Derived from `s1_grouping_5B` (for PASS runs):

   * `total_grouping_rows`
   * `total_unique_group_ids` (across all scenarios in `scenario_set_5B`)
   * Optionally, per-scenario summary:

     * `group_ids_per_scenario_min` / `max`
     * `members_per_group_min` / `max` / `mean` (based on row counts).

These metrics MUST be consistent with the actual committed S1 datasets when `status = "PASS"`.

For `status = "FAIL"`, metrics MAY be partial (e.g. some scenarios discovered before the error), but MUST never claim higher counts than what was actually attempted.

---

### 10.3 Logging local details (structured payload)

S1 SHOULD attach a structured `details` / `payload` object in the run-report record with:

* For each `scenario_id`:

  * `bucket_count`
  * `grouping_row_count`
  * `group_id_count`

* Optional small samples (for debugging only, not for data-plane use), such as:

  * first and last `bucket_start_utc`/`bucket_end_utc` per scenario,
  * a small histogram of `members_per_group` (e.g. “many singletons, few large groups”).

This payload is **informative** (not part of the core contract) but SHOULD be present to aid debugging and tuning.

---

### 10.4 Error reporting integration

On any `status = "FAIL"` with one of the `5B.S1.*` error codes (§9):

* The run-report record MUST include:

  * `error_code` (canonical),
  * any relevant context in the payload, for example:

    * failing `scenario_id`,
    * offending `merchant_id` / `zone_representation` for grouping errors.

* S1 MUST NOT claim any scenario as “succeeded” in metrics if its grid or grouping failed validation.

Downstream systems (scheduler, dashboards, later states) MUST key off:

* `status`, and
* `error_code`,

not the free-text message, when deciding whether S2–S4 may run.

---

### 10.5 No RNG / data-plane telemetry

Because S1 is **RNG-free** and does not perform heavy data-plane scans:

* It MUST NOT emit RNG metrics (no streams, no draw counts).
* It MUST NOT log sample data-plane rows (e.g. example merchants or buckets) beyond what fits in small, anonymised debug payloads if configured.

All RNG observability for 5B belongs to S2–S4 and the final 5B validation/HashGate state.

Within these constraints, 5B.S1’s observability obligation is:

> *“For this world, here are the scenarios I tried, here’s how many buckets and groups I created, and here’s whether the plan is complete and consistent.”*

---

## 11. Performance & scalability *(Informative)*

This section is descriptive, not normative. It explains how 5B.S1 is expected to behave at scale and what to watch for.

---

### 11.1 Workload shape

S1’s work naturally decomposes into two planes:

* **Time grid:**

  * Cost is roughly proportional to
    `Σ_scenario bucket_count(scenario)`
    where `bucket_count ≈ horizon_length / bucket_duration`.
  * This is typically modest: even a 90-day horizon at 15-minute buckets is ~8.6k buckets per scenario.

* **Grouping:**

  * Cost is roughly proportional to
    `Σ_scenario |domain_scenario|`
    where `domain_scenario` is the set of `(merchant, zone[, channel])` keys that actually have 5A intensity for that scenario.

S1 does **no stochastic work** and no heavy joins across large fact tables; it mostly works over keys and manifests.

---

### 11.2 Time complexity

At a high level:

* **Grid construction:**
  O(#scenarios × buckets_per_scenario) to:

  * compute bucket boundaries,
  * annotate with local-time and scenario tags,
  * and write `s1_time_grid_5B`.

* **Grouping:**
  O(#scenarios × domain_size_per_scenario) to:

  * extract distinct `(merchant, zone[, channel])` keys from 5A surfaces,
  * apply a grouping function (usually a small amount of attribute logic),
  * and write `s1_grouping_5B`.

Any extra cost (e.g. reading some upstream metadata from 2B/3A/3B) should be small compared to the per-scenario domain size.

---

### 11.3 Memory & I/O profile

Memory expectations:

* S1 can stream per-scenario where needed:

  * build and write `s1_time_grid_5B` one scenario at a time,
  * build `s1_grouping_5B` per scenario from a streamed view of 5A domain keys.
* Peak memory is therefore bounded by:

  * the largest per-scenario bucket list, plus
  * the largest per-scenario grouping domain,
    which are both modest compared to full data-plane tables.

I/O expectations:

* Reads:

  * 5A scenario manifest (small),
  * 5A scenario-local intensity surfaces (keys only, not full analytical scans),
  * small configs/policies,
  * optional upstream manifests for hints.
* Writes:

  * one `s1_time_grid_5B` file per `(mf, scenario_id)`,
  * one `s1_grouping_5B` file per `(mf, scenario_id)`.

This keeps S1 cheap relative to later arrival states (S2–S4).

---

### 11.4 Concurrency & scheduling

Good patterns:

* **Per-world serial, per-world parallel scenarios (optional):**

  * Within one `(ph, mf)`, scenarios can be processed sequentially or in parallel, provided:

    * per-scenario files are written atomically,
    * identity and sort rules are respected.

* **Reuse across seeds:**

  * Because S1 is independent of `seed`, its outputs can be reused across many runs of S2–S4 for the same `(ph, mf)` and `scenario_set_5B`.

Bad patterns:

* Recomputing S1 for the same `(ph, mf)` with unchanged policies on every seed/run; that wastes resources and risks conflicts if not strictly idempotent.

---

### 11.5 Degradation & tuning

If S1 ever becomes noticeable in runtime:

* It’s likely due to:

  * very fine bucket granularity over very long horizons, or
  * a very large grouping domain (many merchants × zones × channels).

Mitigations live at **config level**, not in S1 logic:

* coarsen `bucket_duration` in `time_grid_policy_5B`,
* reduce `scenario_set_5B` per run,
* or adjust grouping policy (e.g. pool more aggressively).

S1 itself remains deterministic, metadata-lean, and generally much lighter than the RNG-bearing arrival states that follow.

---

## 12. Change control & compatibility *(Binding)*

This section defines **how 5B.S1 may evolve** and when a **spec/schema version bump** is required. It is binding on:

* the 5B.S1 state spec,
* the `schemas.5B.yaml` anchors for `s1_time_grid_5B` and `s1_grouping_5B`,
* the 5B dataset dictionary / artefact registry, and
* downstream 5B states (S2–S4) that consume S1 outputs.

---

### 12.1 Version signalling

5B as a segment already carries a **segment spec version** (e.g. `5B_spec_version`). For S1, the following MUST be true:

* The spec version present in **`s0_gate_receipt_5B`** (from S0) applies to S1 as well.
* The 5B dataset dictionary entries for `s1_time_grid_5B` and `s1_grouping_5B` MUST include the same `segment_spec_version` metadata.
* Downstream 5B states (S2–S4) MUST read this version (from S0 or dictionary) and:

  * explicitly support it, or
  * fail fast with an “unsupported 5B spec version” error.

There is no separate “S1-only” version; S1 evolves with the overall 5B spec.

---

### 12.2 Backwards-compatible changes (allowed with minor bump)

The following changes are considered **backwards-compatible** for S1 and MAY be made under a **minor** 5B spec bump (e.g. `5B-1.0 → 5B-1.1`), provided schemas, dictionary, and registry are updated consistently:

1. **Additive schema changes**

   * Adding new **optional** fields to:

     * `s1_time_grid_5B` (e.g. extra tags like `is_holiday_bucket`, `bucket_label`), or
     * `s1_grouping_5B` (e.g. `group_role`, `group_hints`).
   * Adding new **optional** fields to S1 policies (`time_grid_policy_5B`, `grouping_policy_5B`) that have clear defaults and do not change the meaning of existing fields.

2. **Additional artefacts or metrics**

   * Introducing new **optional** model/control datasets that S1 writes (e.g. a per-scenario horizon summary), registered as `status = OPTIONAL` or `INTERNAL` in `sealed_inputs_5B`.
   * Adding new run-report metrics or structured debug payload fields.

3. **Loosening constraints that do not change semantics**

   * Allowing S1 to attach more local-time tags, as long as existing fields keep their original semantics.
   * Allowing grouping policy to add new *ways* of pooling entities, as long as existing policy parameters continue to behave the same when set to their current defaults.

In all these cases, existing consumers that ignore the new fields/artefacts will still see the same grid and grouping behaviour.

---

### 12.3 Breaking changes (require new major 5B spec)

The following changes are **breaking** and MUST NOT be made under the same 5B `segment_spec_version`. They require:

* a new **major** 5B spec version (e.g. `5B-1.x → 5B-2.0`), and
* explicit handling in downstream 5B states.

Breaking changes include:

1. **Schema/shape changes that alter existing fields**

   * Renaming or removing existing fields in `s1_time_grid_5B` or `s1_grouping_5B`.
   * Changing the types or meaning of existing fields (e.g. `bucket_index` no longer contiguous, or `group_id` type changing from integer to string without dual-mode support).

2. **Partitioning / identity changes**

   * Changing the partitioning law for S1 datasets (e.g. introducing `seed` as a partition key, or dropping `scenario_id` from the partition).
   * Changing the primary key semantics (e.g. allowing multiple rows per `(scenario_id, bucket_index)`, or multiple groups per `(merchant, zone[, channel])`).

3. **Semantic changes to time grid**

   * Changing how the grid relates to 5A horizons (e.g. extending horizons beyond 5A, or changing bucket alignment rules in a way that breaks existing S2/S3 expectations).
   * Changing `bucket_index` semantics (e.g. using non-contiguous indices or redefining what a “bucket” represents in time).

4. **Semantic changes to grouping**

   * Changing the grouping unit (e.g. from `(merchant, zone)` to `(merchant, tz_group)` universally) in a way that breaks assumptions in S2+.
   * Changing grouping from 1:1 membership (each key in exactly one `group_id`) to something else (e.g. overlapping groups) without a new spec version and updated downstream states.

Whenever such changes are required, the implementation MUST:

* bump the 5B `segment_spec_version` and
* update S2–S4 specs to explicitly support the new semantics.

---

### 12.4 Interaction with S0 and other 5B states

* S0 (Gate & sealed inputs) is the “source of truth” for 5B spec version and sealed world.
* S1 MUST remain compatible with S0’s version declaration: if S0 says `5B_spec_version = X`, S1 must expect to behave as version X.

Downstream:

* S2–S4 MUST:

  * treat the S1 outputs as canonical for time/grid & grouping, and
  * gate on the 5B spec version from S0.

If S2–S4 see an unknown 5B version, they MUST fail fast (e.g. `5B.S2.UNSUPPORTED_SPEC_VERSION`) rather than assuming S1’s outputs are still compatible.

---

### 12.5 Migration principles

When evolving S1:

* Prefer **additive, backward-compatible** changes:

  * new optional fields,
  * new optional tags,
  * richer grouping metadata.

* Keep the core contracts stable:

  * `s1_time_grid_5B` remains the **canonical bucket grid**, aligned to 5A horizons.
  * `s1_grouping_5B` remains a **1:1 mapping** from each `(merchant, zone[, channel])` in domain to exactly one `group_id`.

* Avoid changes that force downstream states to reconstruct time grids or grouping themselves.

If you need fundamentally different behaviour (e.g. a different notion of “group” or a different time partition), express that by:

* introducing a new `parameter_hash` and/or
* bumping the 5B spec version,

then updating S0, S1, and S2–S4 together with clear version gating.

This keeps S1 compatible across minor evolutions while giving you a clean, explicit path when you need to make deeper architectural changes.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix just collects shorthand and symbols used in **5B.S1 — Time grid & grouping plan**. It does **not** add new behaviour; the binding bits are in §§1–12.

---

### 13.1 Identities & sets

* **`ph`**
  Shorthand for `parameter_hash`. The parameter pack in play (including 5B time-grid/grouping policies via S0).

* **`mf`**
  Shorthand for `manifest_fingerprint`. The sealed world identity; all S1 outputs are keyed by this.

* **`scenario_set_5B` / `sid_set`**
  The set of `scenario_id` values S0 bound 5B to for this `(ph, mf)`.

* **`world_id`**
  `(parameter_hash, manifest_fingerprint)`; the closed world S0 sealed.

* **`run_id`**
  Engine run identifier. Used in run-reporting; S1 outputs themselves are independent of it.

---

### 13.2 S1 datasets

* **`s1_time_grid_5B`**
  Time-bucket dimension table for 5B; canonical list of `(scenario_id, bucket_index)` with `bucket_start_utc`, `bucket_end_utc`, and tags.

* **`s1_grouping_5B`**
  Group-membership table; maps each in-scope `(merchant, zone[, channel])` to a `group_id` for latent fields / shared dynamics.

---

### 13.3 Keys & fields

* **`scenario_id`**
  Scenario identifier from 5A’s scenario manifest (e.g. `"baseline_2025Q1"`, `"stress_payday"`).

* **`bucket_index`**
  Integer index of a time bucket within a scenario; contiguous and ordered.

* **`bucket_start_utc`, `bucket_end_utc`**
  UTC bounds of a bucket, in RFC3339-with-micros format.

* **`zone_representation`**
  Short-hand for the chosen zone representation in 5B (e.g. `tzid` or `(country_iso, tzid)`) as fixed by the S1 schema.

* **`group_id`**
  Opaque identifier for a latent-field group (integer or string per schema). One per `(scenario_id, merchant, zone[, channel])`.

---

### 13.4 Policies & configs

* **`time_grid_policy_5B`**
  5B-local config that defines:

  * bucket duration and alignment,
  * any per-scenario overrides.

* **`grouping_policy_5B`**
  5B-local config that defines:

  * what constitutes an entity to group (keys),
  * which attributes may be used to pool or split entities,
  * whether grouping is trivial or pooled.

---

### 13.5 Error code prefix

All S1 error codes are prefixed:

> **`5B.S1.`**

Examples (see §9 for semantics):

* `5B.S1.S0_GATE_MISSING`
* `5B.S1.UPSTREAM_NOT_PASS`
* `5B.S1.TIME_GRID_POLICY_MISSING`
* `5B.S1.TIME_GRID_INCOMPLETE`
* `5B.S1.GROUP_ASSIGNMENT_INCOMPLETE`
* `5B.S1.IO_WRITE_CONFLICT`

Downstream tools should key on `error_code`, not free-text messages.

---

These abbreviations are just for readability; the normative behaviour of **5B.S1** is fully defined in §§1–12.

---
