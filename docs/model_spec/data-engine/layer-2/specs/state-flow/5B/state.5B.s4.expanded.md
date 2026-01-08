# 5B.S4 — Micro-time & routing to sites/edges (Layer-2 / Segment 5B)

## 1. Purpose & scope *(Binding)*

1.1 **Role of 5B.S4 in segment 5B**
5B.S4 is the **per-arrival realisation** state for Layer-2 / Segment 5B. For each `(parameter_hash, manifest_fingerprint, scenario_id, seed)` where 5B.S0–S3 have passed, S4:

* takes **bucket-level arrival counts** from `s3_bucket_counts_5B`, and
* expands them into a **concrete arrival event stream** with:

  * exact UTC timestamps (and associated local timestamps / tzids), and
  * a **routed endpoint**: either a physical site (`site_id`) or a virtual edge (`edge_id`),

using the existing Layer-1 routing and civil-time rails and the Philox RNG discipline defined at layer level.

---

1.2 **In-scope responsibilities**
S4’s responsibilities are strictly limited to:

* **Micro-time placement**
  For every bucket row in `s3_bucket_counts_5B` with count `N>0`, S4 must produce exactly `N` arrival timestamps:

  * placed **within that bucket’s horizon** as defined by `s1_time_grid_5B`, and
  * mapped to local clocks in a way that is consistent with 2A’s `site_timezones` and `tz_timetable_cache` and with the S4 time-placement policy (including handling of DST gaps and folds).

* **Routing to sites/edges**
  For every realised arrival, S4 must:

  * decide, according to 3B’s virtual classification and routing policy, whether the arrival is **physical** (routed to a site) or **virtual** (routed to an edge), and
  * select the concrete `site_id` or `edge_id` using the **existing routing fabric**:

    * 2B’s site weights, alias tables and tz-group weights for physical routing, and
    * 3B’s edge catalogue, alias tables and virtual routing policy for virtual routing.

* **Emission of the arrival skeleton dataset**
  S4 must emit a single canonical dataset (e.g. `s4_arrival_events_5B`) that:

  * contains one row per realised arrival,
  * is **partitioned and keyed** consistently with the rest of 5B (world + scenario + seed), and
  * carries enough identifiers (bucket index, merchant, zone, site/edge, scenario, timestamps) for Layer-3 (6A/6B) and the broader enterprise shell to consume without re-deriving anything from upstream states.

* **RNG usage and traceability**
  S4 is a **RNG-using** state. It must:

  * consume Philox uniforms only under the 5B RNG policy (with separate substreams for time placement and routing decisions), and
  * record all consuming events via the shared RNG envelope and trace logs so that S5 and higher-level validators can fully replay and account for S4’s random choices.

---

1.3 **Out-of-scope responsibilities**
To avoid conflict with upstream authority and to keep 5B clean, S4 explicitly **must not**:

* change or recompute:

  * any λ surfaces from 5A or 5B.S2,
  * the time grid or grouping plan from 5B.S1, or
  * the bucket-level counts `N` from 5B.S3.
* modify or re-interpret:

  * `site_locations` (1B), `site_timezones` / `tz_timetable_cache` (2A),
  * routing weights, alias tables or day effects (2B),
  * zone allocation or routing universe hashes (3A), or
  * virtual merchant / edge definitions or routing policy (3B).
* introduce fraud labels, flows, customer/account entities, or any business logic that belongs to Layer-3 (6A/6B) and above.

Any behaviour outside these bounds is considered **out of scope** and must be handled by other states or segments.

---

1.4 **Position in the wider engine**
Within segment 5B, S4 is the **final computational state**:

* 5B.S0–S3 prepare:

  * the sealed input world,
  * the time grid and grouping,
  * the realised intensity surfaces, and
  * bucket-level counts.
* 5B.S4 uses those to produce the **arrival event stream**.
* 5B.S5 will then validate S4 (together with S0–S3) and seal segment 5B via a Layer-2 validation bundle and `_passed.flag`, which Layer-3 (6A/6B) must gate on before consuming arrivals.

This section binds S4 to that role: it is the **only** state that may generate Layer-2 arrival events, and it must do so in a way that is fully consistent with upstream contracts and replayable under the global RNG and validation regime.

---

## 2. Preconditions & dependencies *(Binding)*

2.1 **Run identity & scope**
For S4 to run, a concrete **run identity** MUST be fixed:

* `parameter_hash` — arrival / 5B parameter pack in force.
* `manifest_fingerprint` — Layer-1 world & upstream artefact set.
* `scenario_id` — scenario whose λ is being realised.
* `seed` — RNG identity for this arrival realisation.

S4 **MUST NOT** execute for any `(parameter_hash, manifest_fingerprint, scenario_id, seed)` until this identity is fixed and recorded in `s0_gate_receipt_5B`.

---

2.2 **Upstream segment HashGates**
For a given `manifest_fingerprint`, S4 **MUST** see the following segment gates as VERIFIED (normally via 5B.S0, but S4 treats them as hard preconditions):

* Layer-1:

  * `_passed.flag` (merchant → site counts),
  * `_passed.flag` (site_locations),
  * `_passed.flag` (site_timezones, tz_timetable_cache),
  * `_passed.flag` (routing fabric),
  * `_passed.flag` (zone_alloc, routing_universe_hash),
  * `_passed.flag` (virtual merchants & edge universe).
* Layer-2:

  * `_passed.flag` (arrival intensity surfaces).

If any of these flags is missing or fails verification for the `manifest_fingerprint`, S4 **MUST NOT** proceed.

---

2.3 **5B-local upstream states (S0–S3)**
For the same `(parameter_hash, manifest_fingerprint, scenario_id, seed)`:

* 5B.S0:

  * `s0_gate_receipt_5B` and `sealed_inputs_5B` **MUST** exist and list all artefacts S4 intends to read.
* 5B.S1:

  * `s1_time_grid_5B` and `s1_grouping_5B` **MUST** exist, be schema-valid, and cover the full bucket and entity domain used by S3.
* 5B.S2:

  * `s2_realised_intensity_5B` **MUST** exist and be schema-valid (even if S4 only uses it for diagnostics / provenance).
* 5B.S3:

  * `s3_bucket_counts_5B` **MUST** exist, be schema-valid, and define all `(entity, bucket)` pairs S4 will expand.

S4 **MUST NOT** attempt to infer or rebuild any of these surfaces; if they are missing or inconsistent, S4 fails fast.

---

2.4 **Required sealed inputs from Layer-1/Layer-2**
The following artefacts **MUST** appear in `sealed_inputs_5B` (with `status=ALLOWED` or equivalent) before S4 runs, and be schema-valid for the relevant `manifest_fingerprint` (and `seed` where applicable):

* **Geometry & time:**

  * 1B: `site_locations`.
  * 2A: `site_timezones`, `tz_timetable_cache`.

* **Physical routing:**

  * 2B: `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s4_group_weights`, and the `route_rng_policy_v1` / alias layout policy that govern their use.

* **Zone allocation:**

  * 3A: `zone_alloc`, `zone_alloc_universe_hash`.

* **Virtual routing:**

  * 3B: `virtual_classification_3B`, `virtual_settlement_3B`,
    `edge_catalogue_3B`, `edge_alias_index_3B`, `edge_alias_blob_3B`,
    `edge_universe_hash_3B`, `virtual_routing_policy_3B`.

If S4 needs an artefact that is not listed in `sealed_inputs_5B`, that run **MUST** be treated as invalid.

---

2.5 **S4 configuration & RNG environment**
Before S4 runs, the following 5B-owned configuration artefacts **MUST** be present (and normally are part of the `parameter_hash` pack):

* **Time-placement config:**
  Rules for how to distribute arrivals inside a bucket (uniform vs shaped), and how to treat DST gaps/folds (e.g. clamp, shift, reject).

* **Routing config:**
  Any S4-specific routing rules layered on top of 2B/3B policies (e.g. channel-specific behaviour, opt-out for certain merchants).

* **S4 RNG policy:**
  Names and boundaries of Philox streams / substreams for:

  * intra-bucket time draws,
  * site picks,
  * edge picks,
    including per-stream budgets and mapping into the layer-wide RNG envelope and trace logs.

S4 assumes the Philox core, RNG envelope schema, and `rng_trace_log` contracts are already fixed at layer level; it does not redefine them, only consumes them according to its policy.

---

2.6 **Non-dependencies (for clarity)**
S4 has **no direct dependency** on any Layer-3 (6A/6B) artefacts, model factories, or enterprise ingestion topics. Those components are expected to treat `s4_arrival_events_5B` as their upstream authority and to gate on 5B’s final validation state, not the other way round.

---

## 3. Inputs & authority boundaries *(Binding)*

3.1 **Inputs from within Segment 5B**
S4 MAY only consume 5B-local artefacts that are explicitly listed in `sealed_inputs_5B` as `owner_segment = "5B"` and whose `state_id` is in `{S0, S1, S2, S3}`:

* **From S0 — gate & sealed universe**

  * `s0_gate_receipt_5B`

    * Run identity and upstream HashGate verification status for `(parameter_hash, manifest_fingerprint)`.
    * S4 uses this as *read-permission* and *context*; it MUST NOT attempt to re-derive gate decisions.
  * `sealed_inputs_5B`

    * Closed-world inventory of all artefacts S4 is allowed to read.
    * S4 MUST treat this as authoritative: if an artefact is not listed, it is out of world.

* **From S1 — time grid & grouping**

  * `s1_time_grid_5B`

    * Canonical bucket boundaries and identifiers for the arrival horizon (per `scenario_id`).
    * S4 uses this to map counts to bucket windows and MUST NOT alter bucket definitions.
  * `s1_grouping_5B`

    * Merchant×zone×(channel) → group mapping used for S2/S3.
    * S4 may use this for diagnostics or grouping in run-reports but MUST NOT change group membership.

* **From S2 — realised intensities (optional input)**

  * `s2_realised_intensity_5B`

    * `λ_realised` per entity×bucket, after applying latent fields.
    * S4 MAY read this for provenance or checks (e.g. to include λ in arrival rows or metrics), but **must not** change or re-interpret λ; S2 remains the sole authority for realised intensity.

* **From S3 — bucket-level counts (hard dependency)**

  * `s3_bucket_counts_5B`

    * **Authoritative counts** `N ≥ 0` per `(parameter_hash, manifest_fingerprint, seed, scenario_id, entity, bucket_index)`.
    * S4 MUST treat these counts as immutable:

      * if S3 says `N = 0`, S4 MUST emit no arrivals for that (entity, bucket);
      * if S3 says `N = N₀ > 0`, S4 MUST emit exactly `N₀` arrivals and MUST NOT resample, drop, or create additional arrivals.

S4 MUST NOT read any other 5B-owned datasets (e.g. experimental summaries) unless they are later added to `sealed_inputs_5B` and documented as inputs.

---

3.2 **Inputs from Layer-1 / Layer-2 upstream**
The following artefact *classes* are considered legitimate inputs for S4, but ONLY via entries explicitly present in `sealed_inputs_5B`:

* **Geometry & time authority (Layer-1)**

  * 1B: `site_locations`

    * Defines the universe of physical outlets and their coordinates.
    * S4 MUST treat this as read-only and MUST NOT change or “fix up” site IDs or geometry.
  * 2A: `site_timezones`, `tz_timetable_cache`

    * Sole authority for `tzid` per site and UTC↔local mapping.
    * All local timestamp derivations in S4 MUST be consistent with these surfaces and with configured DST policy.

* **Physical routing authority (Layer-1 / 2B)**

  * 2B: `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s4_group_weights`, plus `route_rng_policy_v1` and alias layout policy.

    * Define how physical traffic is distributed over sites and groups.
    * S4 MUST use these surfaces *as-is* when routing to physical sites and MUST NOT invent alternative weighting or alias schemes.

* **Zone allocation authority (Layer-1 / 3A)**

  * 3A: `zone_alloc`, `zone_alloc_universe_hash`

    * Provide invariants about how merchant outlets are distributed over zones and the signed “routing universe” hash.
    * S4 MUST NOT violate these invariants (e.g. by routing arrivals into zones that have zero allocation in `zone_alloc` for that merchant) and MAY use the universe hash purely for consistency checks and run-reporting.

* **Virtual routing authority (Layer-1 / 3B)**

  * 3B: `virtual_classification_3B`, `virtual_settlement_3B`,
    `edge_catalogue_3B`, `edge_alias_index_3B`, `edge_alias_blob_3B`,
    `edge_universe_hash_3B`, `virtual_routing_policy_3B`.

    * Define which merchants are virtual, what their settlement semantics are, the virtual edge universe, and how virtual routing must behave.
    * When S4 routes a **virtual** arrival, it MUST follow `virtual_routing_policy_3B` and use the edge alias tables as specified; it MUST NOT reinterpret virtual vs physical semantics.

* **Arrival intensity authority (Layer-2 / 5A)**

  * 5A: λ surfaces (`merchant_zone_scenario_local_5A`, `merchant_zone_scenario_utc_5A`, etc.) and their validation bundle.

    * 5A remains the sole authority on what λ is.
    * S4 MUST NOT call any 5A dataset directly for core logic (that is S2/S3’s job); it MAY only use 5A λ surfaces for diagnostics or lineage, and only via what S0 has sealed.

---

3.3 **S4 configuration inputs**

S4 MAY read the following 5B-owned configuration artefacts (again, only if present in `sealed_inputs_5B`):

* **Time placement config** (e.g. `arrival_time_placement_policy_5B`)

  * Defines whether intra-bucket times are uniform or shaped, and how DST gaps/folds are to be treated.
  * This config may change how timestamps are distributed *within* a bucket, but MUST NOT change `N`, bucket boundaries, or the global time grid.

* **Routing config** (e.g. `arrival_routing_policy_5B`)

  * Adds 5B-local routing rules on top of 2B/3B policies (e.g. channel-specific tweaks, merchant opt-outs).
  * MUST be purely restrictive/interpretive: it cannot redefine or contradict any of the following:

    * physical weights/alias semantics from 2B,
    * virtual edge universe or routing semantics from 3B,
    * zone allocation invariants from 3A.

* **5B RNG policy for S4**

  * Specifies which Philox streams/substreams S4 uses for:

    * intra-bucket time draws,
    * site picks,
    * edge picks.
  * MUST be consistent with the global RNG envelope, `rng_audit_log`, and `rng_trace_log` contracts; S4 does not own the Philox implementation, only its usage.

---

3.4 **Authority boundaries (summary)**

To keep responsibilities crisp and aligned with upstream design:

* **Who owns what:**

  * 5A + 5B.S2 own λ (intensity surfaces).
  * 5B.S3 owns bucket counts `N`.
  * 2A owns civil time and tz semantics.
  * 2B + 3B own routing laws and alias tables.
  * 3A + 3B own zone/edge universes and their hash invariants.
  * 5B.S4 owns *only* the expansion from `(entity, bucket, N)` → per-arrival timestamps and routed endpoints.

* **S4 MUST NOT:**

  * recompute or alter λ, counts, grids, routing weights, or universes;
  * read any artefact not listed in `sealed_inputs_5B`;
  * transcend the authority of Layer-1 / 5A in geometry, time, routing, or intensity.

* **S4 MUST:**

  * treat all upstream surfaces as **read-only**,
  * use them exactly as documented to generate arrival events, and
  * expose its own arrival outputs and RNG traces so they can be fully validated and replayed by 5B.S5 and downstream layers.

---

## 4. Outputs (datasets) & identity *(Binding)*

4.1 **Core output dataset**

4.1.1 **Arrival event stream (required)**
5B.S4 produces exactly one **required** data surface:

* **`s4_arrival_events_5B`** — the canonical Layer-2 arrival skeleton for Segment 5B.

Conceptually:

> One row per realised arrival for a given `(parameter_hash, manifest_fingerprint, scenario_id, seed)` after expanding S3’s bucket-level counts.

Each row carries, at minimum:

* **World & scenario identity**

  * `manifest_fingerprint`
  * `parameter_hash`
  * `seed`
  * `scenario_id`
* **Link back to S3 domain**

  * `bucket_index` (or equivalent horizon key from `s1_time_grid_5B`)
  * the same merchant×zone×(channel) entity key used by S3
* **Routing context**

  * `merchant_id`
  * `zone_representation` (and optional `channel` if 5B uses one)
  * either:

    * `site_id` + `is_virtual = false`, or
    * `edge_id` + `is_virtual = true`
  * optional `tz_group_id` / `routing_universe_hash` echoes for diagnostics
* **Time fields**

  * `ts_utc` (arrival UTC timestamp, authoritative)
  * one or more local-time representations as required by policy, e.g.:

    * `ts_local_primary`
    * `tzid_primary`
    * optional secondary local views if virtual dual-clock semantics are enabled

This dataset is the **only 5B surface** that Layer-3 (6A/6B) and the enterprise shell should treat as “arrival events”. S4 MUST NOT write any alternative event stream for the same scope.

---

4.2 **Optional S4 outputs**

S4 MAY (but is not required to) materialise lightweight diagnostic surfaces, for example:

* `s4_arrival_summary_5B`
  Per `(entity, bucket)` or `(merchant, scenario)` summaries derived from `s4_arrival_events_5B` (counts, routing mix, time-placement statistics).

* `s4_arrival_anomalies_5B`
  A structured log of soft anomalies detected during S4 (e.g. buckets with extreme skew, unusual routing splits) that do not justify failing the run.

These are **diagnostic only**:

* They MUST be derivable from `s4_arrival_events_5B` + upstream surfaces.
* They MUST NOT be used by downstream layers as primary authority; Layer-3 consumers should depend on `s4_arrival_events_5B` alone.

If such diagnostics are not needed, they can be omitted entirely; S4 remains valid with only the core event stream.

---

4.3 **Dataset identity & determinism**

4.3.1 **Identity keys**
For `s4_arrival_events_5B`:

* Logical identity is determined by the quadruple:

  * `(parameter_hash, manifest_fingerprint, scenario_id, seed)`.
* For a fixed quadruple and a fixed upstream world (i.e. same `sealed_inputs_5B`), S4 MUST be:

  * **purely deterministic**: every rerun produces the same set of arrival rows with the same `ts_utc`, site/edge assignments, and other fields.
  * independent of `run_id` — `run_id` may appear in RNG logs, but MUST NOT affect dataset content.

Within a given `(parameter_hash, manifest_fingerprint, scenario_id, seed)`:

* The dataset MUST define a clear primary key, e.g.:

  * `arrival_id` unique within `(manifest_fingerprint, seed, scenario_id)`, **or**
  * a composite key such as `(manifest_fingerprint, seed, scenario_id, merchant_id, bucket_index, arrival_seq)`,

  and the spec for that key MUST be stable across versions.

4.3.2 **Partition & path law**
To align with existing Layer-1 egress patterns (e.g. `site_locations` dropping `parameter_hash` from the path):

* `s4_arrival_events_5B` MUST be partitioned on:

  * `seed`
  * `manifest_fingerprint`
  * `scenario_id`

  with `parameter_hash` carried as a column only.

* Path template (informative example, exact prefix to be fixed in the contracts section):

  ```text
  data/layer2/5B/arrival_events/
    seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* Any optional S4 diagnostics SHOULD follow the same partitioning scheme or a coarser one (e.g. omit `scenario_id` if naturally aggregated).

S4 MUST NOT:

* write arrival events into any path that does not embed `seed` and `fingerprint` in this way,
* mix different `scenario_id` values into the same partition directory.

---

4.4 **Segment / layer closure flags for S4 outputs**

* Within **Segment 5B**:

  * `s4_arrival_events_5B` is the **final computational output**; subsequent 5B.S5 will only validate and package (no new arrival events).
  * In the dataset dictionary, `s4_arrival_events_5B` SHOULD be marked `final_in_segment: true`.

* Within **Layer-2**:

  * Unless later segments are added to Layer-2, `s4_arrival_events_5B` will also be the **arrival egress for the layer**, and SHOULD be flagged `final_in_layer: true` in the dictionary and artefact registry.
  * Layer-3 (6A/6B) MUST gate on 5B’s validation bundle / `_passed.flag` (defined in S5) before reading this dataset, but once gated, `s4_arrival_events_5B` is their sole Layer-2 arrival authority.

No other S4-owned dataset may be treated as egress for arrivals; any additional S4 outputs are auxiliary and MUST be marked as non-final in both the dictionary and registry.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

S4’s egress contracts live in the standard catalogue files:

* docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml
* docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml
* docs/model_spec/data-engine/layer-2/specs/contracts/5B/artefact_registry_5B.yaml

This section summarises how those contracts are used; it does not restate column-by-column shapes.

S4 can emit up to three datasets:

1. `arrival_events_5B` — required canonical arrival stream.
2. `s4_arrival_summary_5B` — optional per-entity/bucket summaries.
3. `s4_arrival_anomalies_5B` — optional anomaly/event log.

### 5.1 `arrival_events_5B`

* **Schema anchor:** `schemas.5B.yaml#/egress/s4_arrival_events_5B`
* **Dictionary entry:** `datasets[].id == "arrival_events_5B"`
* **Registry manifest key:** `mlr.5B.egress.arrival_events`

Binding rules:

* Files live under `data/layer2/5B/arrival_events/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/`, with partition keys `[seed, fingerprint, scenario_id]`. S4 MUST NOT deviate from this layout.
* Each row captures one realised arrival “skeleton” (merchant, zone/channel context, UTC/local timestamps, routing info). Column definitions and required orderings are governed by the schema pack; S4 MUST keep them byte-accurate.
* The registry declares that this surface is final-in-layer and depends on S3 counts, routing metadata, and RNG policies. S4 MUST NOT read additional artefacts that aren’t declared and sealed.
* Determinism: same `(seed, scenario_id, parameter_hash, manifest_fingerprint)` ⇒ byte-identical arrival stream.

### 5.2 `s4_arrival_summary_5B`

* **Schema anchor:** `schemas.5B.yaml#/diagnostics/s4_arrival_summary_5B`
* **Dictionary entry:** `datasets[].id == "s4_arrival_summary_5B"`
* **Registry manifest key:** `mlr.5B.diagnostics.arrival_summary`

Binding rules:

* Optional dataset. When present it MUST follow the dictionary’s partitioning and the schema’s per-bucket metrics. When absent, downstream tooling MUST rely on `arrival_events_5B` alone.
* Useful for observability pipelines; consumption/retention expectations defined in the registry MUST be honoured.

### 5.3 `s4_arrival_anomalies_5B`

* **Schema anchor:** `schemas.5B.yaml#/diagnostics/s4_arrival_anomalies_5B`
* **Dictionary entry:** `datasets[].id == "s4_arrival_anomalies_5B"`
* **Registry manifest key:** `mlr.5B.diagnostics.arrival_anomalies`

Binding rules:

* Optional anomaly log for stress testing. Paths/partitions mirror the summary dataset; key and column semantics live in the schema.
* Any anomaly codes/enums MUST be defined in the schema pack before use.

All future changes to these artefacts MUST begin with the schema/dictionary/registry so that this spec never diverges from the authoritative contracts.
## 6. Deterministic algorithm (with RNG — micro-time & routing) *(Binding)*

6.1 **Domain and iteration order**

6.1.1 **Bucket domain**
S4 operates over the **exact domain of `s3_bucket_counts_5B`**:

* Each row corresponds to:

  * `parameter_hash`
  * `manifest_fingerprint`
  * `seed`
  * `scenario_id`
  * an **entity key** (e.g. `merchant_id`, `zone_representation`, optional `channel`)
  * `bucket_index`
  * integer `count_N ≥ 0`

S4 MUST:

* skip rows where `count_N = 0` (emit no arrivals), and
* process every row where `count_N > 0`.

6.1.2 **Iteration order**
Within a fixed `(parameter_hash, manifest_fingerprint, scenario_id, seed)`:

* The engine MAY iterate in any implementation-friendly order (e.g. by merchant, by bucket), but:

  * the **resulting arrival set and their timestamps / routing decisions MUST be deterministic** for that quadruple, and
  * all RNG use MUST follow the configured Philox streams/substreams so that re-running S4 with the same identity reproduces the same events.

---

6.2 **Join to time grid and grouping**

For each `(entity, bucket_index)` row in `s3_bucket_counts_5B`:

1. **Join to S1 time grid**

   * Join on `(parameter_hash, manifest_fingerprint, scenario_id, bucket_index)` to obtain:

     * `bucket_start_utc`
     * `bucket_end_utc`
     * `bucket_duration = bucket_end_utc - bucket_start_utc`
     * any additional grid metadata (local DOW, labels, etc.)

   If this join fails (no matching bucket in `s1_time_grid_5B`), S4 MUST fail.

2. **Optional: join to S1 grouping**

   * Join on entity + bucket (or on entity + group key) to obtain `group_id` if needed for diagnostics.
   * S4 MUST NOT change any grouping defined by S1.

This step is RNG-free and purely deterministic.

---

6.3 **Micro-time placement within buckets (with RNG)**

For each joined row with `count_N = N > 0`:

1. **Draw intra-bucket offsets**

   * Use the S4 time-placement RNG substream (e.g. family `"arrival_time_jitter"`) to draw `N` pseudo-random offsets in the half-open interval `[0, bucket_duration)`.
   * The distribution of offsets is governed by the **time-placement config**:

     * simplest case: **uniform** over the bucket,
     * optional shaped profiles (e.g. more mass near the middle) MUST be deterministic functions of config + bucket metadata.

2. **Form UTC timestamps**

   * For each offset `δ`:

     * `ts_utc = bucket_start_utc + δ`
   * S4 MUST guarantee:

     * `ts_utc ∈ [bucket_start_utc, bucket_end_utc)` for all arrivals.

3. **Local time derivation**

   * At this point, timestamps are in UTC only.
   * Local timestamps are attached **after routing**, when the relevant tzid (physical or virtual) is known, using 2A’s civil-time mapping.

RNG obligations:

* The per-bucket number of draws for time placement MUST be:

  * either exactly `N` (one uniform per arrival), or
  * another fixed function of `N` defined in S4’s RNG policy.
* S4 MUST log time-placement RNG usage via the layer-wide RNG envelope and `rng_trace_log` so that a validator can verify total draws/blocks per run.

---

6.4 **Routing for physical arrivals (site selection)**

For each arrival associated with an entity that is **not virtual** (per `virtual_classification_3B` and routing config):

1. **Determine routing context**

   * Look up:

     * `merchant_id`, `zone_representation`, any channel flags from the entity key.
     * relevant entries in:

       * 2B `s4_group_weights` (tz-group weights per merchant/day),
       * 2B `s1_site_weights` + `s2_alias_index`/`s2_alias_blob` (site-level alias tables),
       * 3A `zone_alloc` (as an invariant, not as a sampler).

2. **Select tz-group / site**

   * Use the configured routing logic (consistent with 2B’s fabric) to:

     * decide which tz-group (if applicable) the arrival falls into, and
     * select a **single site_id** via alias sampling from the appropriate site weights.
   * Routing randomness MUST:

     * use the configured S4 routing RNG substream(s) (or reuse 2B’s alias streams, if that’s how the engine is wired),
     * be fully accounted in RNG logs.

3. **Attach site information**

   * Join `site_locations` on `(merchant_id, legal_country_iso, site_order)` (or equivalent key implied by `site_id`) to obtain:

     * physical coordinates,
     * `legal_country_iso`.

4. **Attach physical tz / local time**

   * Join `site_timezones` for the chosen site to get `tzid_site`.
   * Use `tz_timetable_cache` + `tzid_site` to derive `ts_local_primary` from `ts_utc`, applying the configured DST behaviour.
   * S4 MUST ensure local time derivation follows 2A’s semantics (no ad-hoc timezone math).

The result is an arrival tagged with `site_id`, `is_virtual = false`, `tzid_primary = tzid_site`, and corresponding `ts_local_primary`.

---

6.5 **Routing for virtual arrivals (edge selection)**

For each arrival where the merchant is **virtual** (or treated as such by policy):

1. **Determine virtual routing context**

   * Use:

     * `virtual_classification_3B` and `virtual_settlement_3B` for the merchant,
     * `edge_catalogue_3B`, `edge_alias_index_3B`, `edge_alias_blob_3B`,
     * `virtual_routing_policy_3B`,
     * `edge_universe_hash_3B` for consistency.

2. **Select edge**

   * Use alias sampling over virtual edges as specified by `virtual_routing_policy_3B` to pick a single `edge_id` for the arrival.
   * Routing randomness MUST:

     * follow the RNG streams/substreams described in the policy,
     * be logged and traceable.

3. **Attach edge information**

   * From `edge_catalogue_3B`, attach:

     * `country_iso`, coordinates,
     * operational `tzid_operational`,
     * any additional edge attributes required by policy.

4. **Attach virtual tz / local times**

   * Using 2A’s `tz_timetable_cache`:

     * derive `ts_local_operational` from `ts_utc` under `tzid_operational`,
     * optionally derive `ts_local_settlement` under a settlement tzid, if `virtual_settlement_3B`/policy requires it.
   * S4 MUST respect the dual-clock semantics defined in `virtual_routing_policy_3B` (which tzid is considered “primary” for the arrival event).

The result is an arrival tagged with `edge_id`, `is_virtual = true`, and appropriate tz/local fields per policy.

---

6.6 **Constructing `s4_arrival_events_5B` rows**

For each realised arrival, S4 MUST construct exactly one row in `s4_arrival_events_5B` with:

* Identity: `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`.
* Entity & bucket: `merchant_id`, `zone_representation`, optional `channel`, `bucket_index`.
* Time: `ts_utc`, `tzid_primary`, `ts_local_primary` (plus any virtual dual-clock fields).
* Routing: `is_virtual`, and either `site_id` or `edge_id` as per 6.4/6.5.
* A deterministic arrival sequence/ID:

  * e.g. `arrival_seq` incrementing per `(manifest_fingerprint, seed, scenario_id)` in a fixed ordering.

S4 MUST ensure:

* **Count preservation:**
  For each row in `s3_bucket_counts_5B` with `count_N = N`, there are exactly `N` arrivals with matching entity + bucket in `s4_arrival_events_5B`.

* **No duplication:**
  No arrival is emitted twice; the PK of `s4_arrival_events_5B` must be unique.

---

6.7 **Determinism & idempotence**

For any fixed `(parameter_hash, manifest_fingerprint, scenario_id, seed)`:

* Given the same upstream datasets (as captured by `sealed_inputs_5B`) and the same S1–S3 outputs, S4 MUST produce **bitwise identical** `s4_arrival_events_5B` (modulo allowed differences in file partitioning/ordering described elsewhere).
* Implementation MUST NOT depend on:

  * non-deterministic iteration over files or partitions,
  * wall-clock time,
  * `run_id` (which is reserved for RNG logging and run-reporting only).

If S4 is invoked multiple times for the same identity, the engine MUST either:

* overwrite the previous `s4_arrival_events_5B` with identical content, or
* reject the run as a conflict; it MUST NOT silently merge non-identical runs.

---

6.8 **RNG envelope & trace integration**

All RNG used in S4 (time-placement and routing decisions) MUST:

* use the global **Philox** generator and RNG envelope already defined for the engine,
* be recorded as structured RNG events under 5B’s allocated module/substream labels, with:

  * `seed`, `parameter_hash`, `run_id`, `manifest_fingerprint`,
  * `rng_counter_before_*`, `rng_counter_after_*`,
  * `draws` and `blocks` consistent with S4’s RNG policy,
* be summarised in `rng_trace_log` so that a validator can:

  * confirm per-family draw and block counts, and
  * reconcile them against:

    * the number of arrivals emitted, and
    * configuration-specified budgets.

S4 MUST treat any mismatch between configured budgets and actual RNG trace (over-consumption, under-consumption, or overlapping counters) as a **hard failure** for the state.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

7.1 **Core identity tokens**

S4 and its outputs MUST use the same identity vocabulary as the rest of 5B:

* `manifest_fingerprint` — **world** identity (Layer-1 sealed inputs).
* `parameter_hash` — **parameter pack** identity (5A/5B configuration).
* `scenario_id` — **scenario** identity (from 5A).
* `seed` — **RNG identity** for this arrival realisation.
* `run_id` — **log-only** identity for this execution; MUST NOT affect dataset content.

For the **data surfaces** owned by S4:

* `s4_arrival_events_5B` MUST be a pure function of
  `(manifest_fingerprint, parameter_hash, scenario_id, seed)`
  and upstream data; `run_id` is **not** part of its identity.

---

7.2 **Partition keys & path law**

For `s4_arrival_events_5B`:

* **Partition keys** (binding):

  * `[seed, manifest_fingerprint, scenario_id]`

* **Path template** (binding, modulo top-level prefix):

  ```text
  data/layer2/5B/arrival_events/
    seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
  ```

* `parameter_hash` MUST appear as a **column** in every row but MUST NOT be used as a partition token in the path. This mirrors the Layer-1 convention where egress drops `parameter_hash` from the directory structure.

Any optional S4 diagnostics (if implemented) MUST:

* either use the **same** partition triple, or
* a **coarser** partitioning (e.g. omit `scenario_id`) clearly documented in their own specs.

S4 MUST NOT write any S4-owned dataset into paths that do not embed at least `seed` and `fingerprint` as shown.

---

7.3 **Primary key & uniqueness**

Within a given `(manifest_fingerprint, seed, scenario_id)` partition, `s4_arrival_events_5B` MUST have a **stable primary key**. Two acceptable patterns:

* **A. Surrogate key**

  * Column `arrival_id` (or `arrival_seq`) which is:

    * unique within `(manifest_fingerprint, seed, scenario_id)`,
    * assigned deterministically from S3’s domain and the fixed RNG sequence.

* **B. Composite key**

  * Composite PK such as:

    * `(manifest_fingerprint, seed, scenario_id, merchant_id, bucket_index, arrival_seq)`
      where `arrival_seq` is a deterministic sequence per entity×bucket.

Whichever pattern is chosen MUST be:

* defined in `schemas.5B.yaml#/egress/s4_arrival_events_5B`, and
* treated as **immutable** across spec versions unless explicitly called out as a breaking change.

For any valid run, the PK set MUST be unique and complete; duplicate keys or missing keys relative to S3 counts are fatal.

---

7.4 **Writer ordering discipline**

S4 MUST enforce a **deterministic sort order** when writing `s4_arrival_events_5B`:

* Recommended **sort_keys**:

  * `[scenario_id, merchant_id, zone_representation, bucket_index, ts_utc, arrival_seq]`

* Writers MAY split output across multiple files within a partition, but:

  * each file MUST be internally sorted by the declared `sort_keys`, and
  * the union of all files for a given partition MUST respect the same global ordering (i.e. concatenating files in ASCII path order yields a fully sorted stream).

Readers MUST NOT rely on any ordering other than the declared `sort_keys`.

---

7.5 **Merge & overwrite discipline**

For each `(manifest_fingerprint, seed, scenario_id)`:

* S4 MUST treat the corresponding partition directory as a **single logical dataset**:

  * exactly one logical instance of `s4_arrival_events_5B` is allowed.
* Valid behaviours are:

  * **First-write wins + idempotent rerun**

    * Initial successful run creates the dataset.
    * Subsequent runs with the same `(ph, mf, scenario_id, seed)` MUST either:

      * produce byte-identical content (idempotent rewrite), **or**
      * be rejected as conflicts by the driver.

  * **Explicit replace with strong check**

    * A rerun is allowed to replace existing files **only if** the engine first confirms the new PK set and content are exactly the same, or operates under an explicit “replace” mode with operational safeguards.

S4 MUST NOT:

* append arrivals to an existing partition in a way that changes the logical PK set,
* merge partial runs (e.g. different merchant subsets) into the same logical dataset without a higher-level process that revalidates the entire partition against S3 counts.

Any attempt to write non-identical data into an already-populated `(manifest_fingerprint, seed, scenario_id)` without an explicit, validated replace MUST be treated as an error.

---

7.6 **Relationship to RNG logs**

RNG logs for S4 (time-placement and routing) are **run-scoped**, not data-scoped:

* RNG event tables and `rng_trace_log` entries for S4 MUST be partitioned by:

  * `[seed, parameter_hash, run_id]` (and optionally `manifest_fingerprint` if that’s the layer-wide convention).

Mapping between data and RNG logs:

* Every row in `s4_arrival_events_5B` MUST be attributable to:

  * a finite set of RNG events in S4’s families for that `(seed, parameter_hash, run_id)`, and
  * S5 MUST be able to verify, by counting arrivals and S3 bucket counts, that RNG consumption per family matches the configured law.

Data identity (`(ph, mf, scenario_id, seed)`) and RNG identity (`(ph, seed, run_id)`) must be kept separate but linked via run-report metadata; changing `run_id` MUST NOT change the content of `s4_arrival_events_5B`.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

8.1 **Local PASS criteria for S4**

For a given `(parameter_hash, manifest_fingerprint, scenario_id, seed)`, 5B.S4 is considered **locally PASS** iff **all** of the following hold:

8.1.1 **Upstream state & gate preconditions**

* 5B.S0–S3 have completed successfully for the same `(ph, mf, scenario_id, seed)` and their outputs are present and schema-valid.
* `s0_gate_receipt_5B` and `sealed_inputs_5B` exist for `manifest_fingerprint` and list every upstream artefact actually read by S4.
* All required upstream HashGates for `manifest_fingerprint` (`_passed.flag`, `_passed.flag`, `_passed.flag`, `_passed.flag`, `_passed.flag`, `_passed.flag`, `_passed.flag`) have been verified by S0 and no “must-pass” segment is marked FAIL or MISSING.

---

8.1.2 **Count conservation vs S3**

Let `D₃` be the domain of `s3_bucket_counts_5B` for `(ph, mf, scenario_id, seed)` and `N(entity, bucket)` the integer count in S3.

S4 MUST satisfy:

* For every `(entity, bucket_index) ∈ D₃` with `N = 0`:

  * there are **zero** rows in `s4_arrival_events_5B` with that `(entity, bucket_index)`.
* For every `(entity, bucket_index) ∈ D₃` with `N = N₀ > 0`:

  * there are **exactly `N₀`** rows in `s4_arrival_events_5B` whose entity key and `bucket_index` match.
* There are **no** rows in `s4_arrival_events_5B` whose `(entity, bucket_index)` does not appear in `D₃`.

Any mismatch (extra arrivals, missing arrivals, or mis-keyed arrivals) is a hard failure.

---

8.1.3 **Time grid consistency**

For every row in `s4_arrival_events_5B`:

* There exists a unique row in `s1_time_grid_5B` (for the same `(ph, mf, scenario_id, bucket_index)`) with:

  * `bucket_start_utc`
  * `bucket_end_utc`
* The UTC timestamp MUST obey:

> `bucket_start_utc ≤ ts_utc < bucket_end_utc`

No arrival may lie outside its bucket’s half-open interval.

If no matching grid row exists, or if any `ts_utc` falls outside `[start, end)`, the run is FAIL.

---

8.1.4 **Civil-time correctness (2A semantics)**

For every arrival row:

* All local timestamps and tzids (e.g. `tzid_primary`, `ts_local_primary`, and any settlement/operational pairs for virtuals) MUST be derivable from:

  * `ts_utc`, and
  * the appropriate tzid (`site_timezones` for physical, `edge_catalogue_3B` / settlement policy for virtual),
  * using `tz_timetable_cache` and the configured DST behaviour (gaps/folds policy).

S4 MUST ensure that:

* Every tzid it uses appears in `tz_timetable_cache` for the `manifest_fingerprint`.
* Local times do not violate the chosen DST policy (e.g. no unhandled non-existent times) and are internally consistent.

Any failure to map UTC→local correctly, or use of an unknown tzid, is a hard failure.

---

8.1.5 **Routing correctness vs Layer-1 routing & universes**

For every row in `s4_arrival_events_5B`:

* If `is_virtual = false` (physical arrival):

  * `site_id` MUST be non-null and `edge_id` MUST be null.
  * `site_id` MUST correspond to an existing row in `site_locations` for `(mf, seed)` and the same `merchant_id`.
  * Routing decisions MUST be compatible with:

    * 2B weights/alias tables (no use of sites outside the configured routing universe),
    * 3A `zone_alloc` (no routing into zones that have zero allocation for that merchant),
    * and any constraints expressed in `route_rng_policy_v1` and the 2B alias layout policy.

* If `is_virtual = true` (virtual arrival):

  * `edge_id` MUST be non-null and `site_id` MUST be null.
  * `edge_id` MUST correspond to an existing row in `edge_catalogue_3B` for the same `merchant_id`.
  * Routing MUST follow `virtual_routing_policy_3B`:

    * no use of edges outside the edge universe,
    * semantics of settlement vs operational clocks obeyed,
    * consistency with `edge_universe_hash_3B` and any policy invariants.

* If both `site_id` and `edge_id` are null, or both non-null, the row is invalid and the run is FAIL.

The implementation MAY additionally echo `routing_universe_hash` (3A/3B) per row or group for diagnostics; if echoed, it MUST match the hash computed from upstream.

---

8.1.6 **Schema, identity & partition invariants**

For `s4_arrival_events_5B`:

* The dataset MUST conform to `schemas.5B.yaml#/egress/s4_arrival_events_5B`:

  * all required columns present with the correct types,
  * no undeclared columns when `columns_strict: true`.
* Partitioning MUST obey:

  * paths embed the correct `{seed}`, `{fingerprint}`, `{scenario_id}` values,
  * all rows in a partition have matching `seed`, `manifest_fingerprint`, `scenario_id`.
* Primary key:

  * no duplicate PKs within `(mf, seed, scenario_id)`,
  * PK set is total for all emitted rows and consistent with count conservation (8.1.2).

Any schema or partition-law violation is a hard failure.

---

8.1.7 **Determinism & idempotence**

Given:

* fixed upstream surfaces as per `sealed_inputs_5B`,
* fixed S1–S3 outputs for `(ph, mf, scenario_id, seed)`,
* the same Philox RNG policy and seed,

S4 MUST be **deterministic**:

* Rerunning S4 with the same inputs MUST produce the same logical `s4_arrival_events_5B` (same PK set and values; any allowed differences in file-chunking MUST NOT change logical content).
* If an implementation detects non-deterministic differences across reruns for the same identity, it MUST treat that as a failure and signal it via appropriate error code (e.g. `RERUN_NONDETERMINISTIC`).

---

8.1.8 **RNG accounting**

For the run `(ph, mf, scenario_id, seed, run_id)`:

* The total number of time-placement draws and routing draws MUST match:

  * the configured S4 RNG policy (draws per arrival / per bucket), and
  * the aggregate `draws`/`blocks` reported in the RNG event tables and `rng_trace_log`.

Validators MUST be able to:

* derive an expected draw count from:

  * number of arrivals (for time draws / site/edge picks),
  * and any per-bucket overhead defined by policy,
* and find that expected count equal to the recorded count in RNG logs.

Any over-consumption, under-consumption, or counter overlap is a hard failure.

---

8.2 **Failure behaviour**

If **any** acceptance criterion in §8.1 is violated for a given `(ph, mf, scenario_id, seed)`:

* S4 MUST:

  * mark the run-report for S4 as `status = "FAIL"` with an appropriate `error_code` (see §9),
  * NOT publish or register `s4_arrival_events_5B` as valid in the artefact registry,
  * NOT allow downstream processes to treat this dataset as authoritative.

* The engine driver MUST NOT silently continue; the failure MUST be visible at the segment orchestration level.

Partial outputs (e.g. partially written arrival files) MUST be either:

* cleaned up (deleted or quarantined) before S4 reports PASS, or
* left in place but clearly marked as invalid (e.g. in run-report or registry) so they are never consumed.

---

8.3 **Gating obligations towards S5 and downstream**

8.3.1 **Obligations to 5B.S5 (validation & bundle)**

* 5B.S5 MUST treat S4 as a **mandatory dependency**:

  * It MUST reject any attempt to build `validation_bundle_5B` if S4:

    * has not run for the `(ph, mf, seed)` in question, or
    * has run but has `status != "PASS"` in its run-report, or
    * is missing or schema-invalid in the catalogue.

* S5 MUST:

  * recompute and verify the S4 acceptance criteria that can be checked from persisted data (counts, time windows, routing correctness, RNG accounting), and
  * treat any discrepancy as a failure for the segment as a whole.

8.3.2 **Obligations to Layer-3 / external consumers**

* Downstream consumers (6A/6B, enterprise ingestion) MUST NOT:

  * gate directly on S4’s run-report, or
  * read `s4_arrival_events_5B` using only S4-local signals.

Instead:

* They MUST gate on the **segment-level HashGate** produced by 5B.S5 (`validation_bundle_5B` + `_passed.flag`), which encapsulates S4’s acceptance criteria along with S0–S3.

In other words:

> S4 acceptance is **necessary but not sufficient**; it is a local gate into S5.
> 5B.S5’s PASS and `_passed.flag` is the only gate downstream layers may rely on.

---

## 9. Failure modes & canonical error codes *(Binding)*

9.1 **General conventions**

9.1.1 **Error code format**
All S4 errors MUST use the prefix:

* `5B.S4.`

followed by an UPPER_SNAKE_CASE identifier, e.g. `5B.S4.S3_OUTPUT_MISSING`.

9.1.2 **Failure semantics**
For **any** error code in this section:

* S4 MUST mark the run as `status = "FAIL"` in its run-report for `(parameter_hash, manifest_fingerprint, scenario_id, seed, run_id)`.
* S4 MUST NOT advertise `s4_arrival_events_5B` as valid in the artefact registry.
* 5B.S5 MUST treat any S4 failure as a **hard blocker** for building `validation_bundle_5B`.

---

### 9.2 Upstream gate / input failures

**9.2.1 `5B.S4.S0_GATE_MISSING_OR_INVALID`**
Raised when:

* `s0_gate_receipt_5B` or `sealed_inputs_5B` is missing, schema-invalid, or does not cover S4’s intended inputs.

**9.2.2 `5B.S4.UPSTREAM_HASHGATE_NOT_PASSED`**
Raised when:

* any required upstream `_passed.flag` (1A, 1B, 2A, 2B, 3A, 3B, 5A) is missing or fails verification for the `manifest_fingerprint`.

**9.2.3 `5B.S4.S1_OR_S3_OUTPUT_MISSING`**
Raised when:

* `s1_time_grid_5B`, `s1_grouping_5B`, or `s3_bucket_counts_5B` is missing, incomplete, or schema-invalid for the `(ph, mf, scenario_id, seed)` being processed.

---

### 9.3 Time grid & DST failures

**9.3.1 `5B.S4.TIME_GRID_MISMATCH`**
Raised when:

* a `(scenario_id, bucket_index)` present in `s3_bucket_counts_5B` has **no matching row** in `s1_time_grid_5B`, or
* `bucket_start_utc` / `bucket_end_utc` are invalid (non-monotone, negative duration, etc.).

**9.3.2 `5B.S4.TS_OUTSIDE_BUCKET_WINDOW`**
Raised when:

* any emitted `ts_utc` lies outside the corresponding `[bucket_start_utc, bucket_end_utc)` interval.

**9.3.3 `5B.S4.DST_MAPPING_FAILED`**
Raised when:

* S4 cannot map a `ts_utc` to local time according to `site_timezones` / `tz_timetable_cache` and the configured DST policy (e.g. tzid missing from cache, unhandled gap/fold).

---

### 9.4 Routing failures

**9.4.1 `5B.S4.ROUTING_POLICY_INVALID`**
Raised when:

* S4’s routing config is missing or inconsistent with:

  * 2B `route_rng_policy_v1` / alias layout, or
  * 3B `virtual_routing_policy_3B` / edge universe.

**9.4.2 `5B.S4.SITE_RESOLUTION_FAILED`**
Raised when, for a physical arrival:

* `is_virtual = false` but no valid `site_id` can be selected that:

  * exists in `site_locations` for `(mf, seed)`, and
  * is compatible with 2B routing surfaces and 3A `zone_alloc`.

**9.4.3 `5B.S4.EDGE_RESOLUTION_FAILED`**
Raised when, for a virtual arrival:

* `is_virtual = true` but no valid `edge_id` can be selected that:

  * exists in `edge_catalogue_3B`, and
  * is compatible with `virtual_routing_policy_3B` and `edge_universe_hash_3B`.

**9.4.4 `5B.S4.ROUTING_UNIVERSE_HASH_MISMATCH`**
Raised when:

* S4 detects a mismatch between any echoed `routing_universe_hash` / `edge_universe_hash` and the hashes computed from upstream artefacts for this `manifest_fingerprint`.

---

### 9.5 Count / schema / identity failures

**9.5.1 `5B.S4.BUCKET_COUNT_MISMATCH`**
Raised when:

* aggregation of `s4_arrival_events_5B` by `(entity, bucket_index)` does **not** match `N` in `s3_bucket_counts_5B` (extra arrivals, missing arrivals, or mis-keyed arrivals).

**9.5.2 `5B.S4.SCHEMA_VIOLATION`**
Raised when:

* `s4_arrival_events_5B` does not conform to `schemas.5B.yaml#/egress/s4_arrival_events_5B` (missing required columns, wrong types, undeclared columns when `columns_strict: true`).

**9.5.3 `5B.S4.PARTITION_OR_PK_VIOLATION`**
Raised when:

* partition keys inferred from file paths disagree with `seed`, `manifest_fingerprint`, `scenario_id` columns, or
* primary key constraints (uniqueness within `(mf, seed, scenario_id)`) are violated.

**9.5.4 `5B.S4.RERUN_NONDETERMINISTIC`**
Raised when:

* a rerun for the same `(ph, mf, scenario_id, seed)` produces logically different `s4_arrival_events_5B` (different PK set or different values) compared to an existing valid dataset.

---

### 9.6 RNG accounting failures

**9.6.1 `5B.S4.RNG_STREAM_CONFIG_INVALID`**
Raised when:

* S4 cannot map its configured RNG families (time-placement, site picks, edge picks) onto valid Philox streams/substreams consistent with the layer-wide RNG policy.

**9.6.2 `5B.S4.RNG_ACCOUNTING_MISMATCH`**
Raised when:

* the number of draws/blocks recorded in RNG event tables and `rng_trace_log`:

  * does not match the expected count derived from S3 bucket counts and S4’s RNG law, or
  * exhibits overlap / gaps in Philox counters inconsistent with a single forward-only stream.

Any RNG accounting failure MUST be treated as a hard failure for S4.

---

### 9.7 IO / infrastructure failures

**9.7.1 `5B.S4.IO_READ_FAILED`**
Raised when:

* S4 cannot read a required upstream dataset that is present in `sealed_inputs_5B` (e.g. IO error, permission issue, file missing on disk despite catalogue entry).

**9.7.2 `5B.S4.IO_WRITE_FAILED`**
Raised when:

* S4 fails to write `s4_arrival_events_5B` (or any declared diagnostics) to the target storage (e.g. out-of-space, permission denied, transient network error).

**9.7.3 `5B.S4.IO_WRITE_CONFLICT`**
Raised when:

* S4 detects that it is about to overwrite or merge into an existing `(mf, seed, scenario_id)` partition that already holds non-identical `s4_arrival_events_5B` content, contrary to the merge discipline in §7.

---

9.8 **Unhandled / internal errors**

**9.8.1 `5B.S4.UNEXPECTED_INTERNAL_ERROR`**
Reserved for:

* logic bugs, invariant violations, or any condition that does not fit a more specific code above.

S4 MUST:

* log sufficient context (stack / state summary) in its run-report for debugging, and
* still mark the run as FAIL with this generic code.

---

9.9 **Mapping to orchestration & S5**

* Orchestration MUST treat any `5B.S4.*` error as:

  * a failed S4 state for the corresponding `(ph, mf, scenario_id, seed)`, and
  * a hard block for subsequent S5 validation.

* 5B.S5 MUST:

  * surface the **first** or **most severe** S4 error code it sees when building `validation_bundle_5B`, and
  * incorporate the S4 error status into the segment-wide status for 5B so downstream systems never see a “PASS” for 5B when S4 has failed.

---

## 10. Observability, RNG accounting & run-report integration *(Binding)*

10.1 **Run-report obligations**

10.1.1 **Per-run record**
For every execution of S4 over a `(parameter_hash, manifest_fingerprint, scenario_id, seed, run_id)` tuple, the engine MUST emit a **single run-report record** for S4, with at least:

* `state_id = "5B.S4"`
* `parameter_hash`
* `manifest_fingerprint`
* `scenario_id`
* `seed`
* `run_id`
* `status ∈ {"PASS","FAIL"}`
* `error_code` (empty iff `status="PASS"`)
* `error_message` (optional, human-readable; required on FAIL)

This record MUST be written into the shared run-report mechanism used by other segments/states, so orchestration can see S4’s status alongside S0–S3 and S5.

10.1.2 **Core metrics (required)**
The S4 run-report record MUST include at least the following metrics for the `(ph, mf, scenario_id, seed)` run:

* **Volume metrics**

  * `n_buckets_total` — number of `(entity, bucket)` rows in `s3_bucket_counts_5B`.
  * `n_buckets_nonzero` — number of `(entity, bucket)` rows with `N>0`.
  * `n_arrivals_total` — total rows in `s4_arrival_events_5B`.
* **Routing mix**

  * `n_arrivals_physical`
  * `n_arrivals_virtual`
  * optional fraction fields (e.g. `share_virtual = n_arrivals_virtual / n_arrivals_total`).
* **Time-placement health**

  * `min_bucket_duration`, `max_bucket_duration` (over used buckets).
  * `n_arrivals_at_bucket_start` / `n_arrivals_at_bucket_end_minus_epsilon` (sanity checks).
* **Count consistency flags**

  * `counts_match_s3 ∈ {true,false}` (aggregate check of §8.1.2).
* **Schema/partition flags**

  * `schema_ok ∈ {true,false}`
  * `partition_ok ∈ {true,false}`
    (these roll up the checks in §8.1.6).

10.1.3 **Optional metrics (non-binding)**
S4 MAY include additional metrics for debugging/monitoring, e.g.:

* Per-merchant or per-zone arrival counts (aggregated).
* Simple histograms of intra-bucket offset distributions.
* Routing skew indicators (e.g. Gini-like metrics over sites/edges).

These MUST NOT be relied upon by gating logic; they are for observability only.

---

10.2 **RNG accounting integration**

10.2.1 **Event families & trace**
All RNG used by S4 MUST be exposed via the layer-wide RNG logging surfaces (as defined in `schemas.layer1.yaml`), using the `rng_envelope` and `rng_trace_log` contracts:

* At minimum, S4 MUST define and use distinct **event families** for:

  * intra-bucket time draws (e.g. `arrival_time_jitter`),
  * physical site picks (e.g. `arrival_site_pick`),
  * virtual edge picks (e.g. `arrival_edge_pick`).

The contract IDs for these RNG event tables are `rng_event_arrival_time_jitter`, `rng_event_arrival_site_pick`, and
`rng_event_arrival_edge_pick`; the `substream_label` values remain `arrival_time_jitter`, `arrival_site_pick`, and
`arrival_edge_pick`.
* For each consuming draw, S4 MUST emit an RNG event row with:

  * `module = "5B.S4"` (or equivalent),
  * appropriate `substream_label` identifying the family,
  * `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`,
  * `rng_counter_before_*`, `rng_counter_after_*`,
  * `draws` and `blocks` consistent with the S4 RNG policy.

The `rng_trace_log` for the run MUST aggregate these events and record, per family, the total draws and blocks consumed by S4.

10.2.2 **RNG metrics in run-report (required)**
The S4 run-report record MUST include, at minimum, the following RNG metrics per `(ph, mf, scenario_id, seed, run_id)`:

* `rng_draws_time` — total draws used for time placement.
* `rng_draws_site` — total draws used for physical site picks.
* `rng_draws_edge` — total draws used for virtual edge picks.
* `rng_blocks_time`, `rng_blocks_site`, `rng_blocks_edge` — corresponding block counts (if applicable).
* `rng_accounting_ok ∈ {true,false}` — aggregate flag indicating whether recorded draws/blocks match the expected counts implied by:

  * `s3_bucket_counts_5B` (number of arrivals) and
  * S4’s RNG law (draws per arrival / per bucket).

If `rng_accounting_ok = false`, S4 MUST set `status="FAIL"` and `error_code="5B.S4.RNG_ACCOUNTING_MISMATCH"`.

10.2.3 **Linkage to S5 validation**
5B.S5 MUST be able to:

* read S4’s RNG metrics from the run-report,
* read detailed S4 RNG usage from the RNG event tables and `rng_trace_log`,
* recompute expected draw counts from `s3_bucket_counts_5B` and S4 configuration,

and cross-check them. Any discrepancy S5 finds MUST cause S5 to treat S4 (and thus 5B) as FAIL even if S4 reported PASS.

---

10.3 **Logging & diagnostics**

10.3.1 **Structured logs**
S4 SHOULD emit structured log messages (to the engine’s logging system) for significant events, including but not limited to:

* start and end of processing for `(ph, mf, scenario_id, seed, run_id)`,
* counts of arrivals per scenario and per merchant (at coarse granularity),
* any soft anomalies detected (even if tolerable).

These logs are **informative only**; they do not participate in gating.

10.3.2 **Anomaly reporting surface (optional)**
If `s4_arrival_anomalies_5B` is implemented:

* S4 MUST populate it with one row per anomaly (threshold breaches, extreme skews, etc.) detected during the run.
* Each row SHOULD include:

  * `anomaly_code`, `severity`,
  * optional references to merchant / zone / bucket / site / edge,
  * a short machine-readable explanation.
* The run-report MAY include a summary of anomaly counts by code and severity.

Again, anomalies in this table do **not** directly gate S4; any condition that should fail the run MUST be mapped to a concrete error code in §9.

---

10.4 **Integration with global run-report / observability tooling**

10.4.1 **Inclusion in global view**
S4’s run-report entries MUST be discoverable via the same global run-report index as other states, keyed by:

* `layer = 2`
* `segment = "5B"`
* `state_id = "5B.S4"`
* `manifest_fingerprint`
* `parameter_hash`
* `scenario_id`
* `seed`
* `run_id`

This allows orchestration and operators to see S4’s status in context with S0–S3 and S5 for the same world/seed/scenario.

10.4.2 **Health dashboards (informative)**
Nothing in this section mandates dashboards, but the metrics defined above are intended to be usable directly for:

* monitoring arrival volume and routing mix over time,
* detecting unexpected spikes/drops in `n_arrivals_total`,
* tracking RNG health (`rng_accounting_ok`) across runs.

Such use is recommended but not required; the binding requirement is that S4 emits the run-report and RNG metrics in a consistent, machine-readable format.

---

## 11. Performance & scalability *(Informative)*

11.1 **Asymptotic cost model**
S4’s computational cost is dominated by **expanding bucket-level counts into arrivals**:

* Let:

  * `B` = number of `(entity, bucket)` rows in `s3_bucket_counts_5B` with `N>0`.
  * `N_total` = Σ over all such rows of `N` (total arrivals).
* Then, for a fixed `(ph, mf, scenario_id, seed)`:

  * Time complexity is **O(B + N_total)**:

    * O(B) for joins to grid/grouping and routing context.
    * O(N_total) for generating timestamps, routing, and writing rows.
  * Space complexity can be kept **O(B + W)**, where:

    * `B` is small if processed in chunks, and
    * `W` is the chosen in-memory buffer size for arrivals (e.g. a batch before writing).

In practice, **N_total** (total arrivals) is the key scaling driver; S4 should be implemented as a streaming expansion over S3.

---

11.2 **Memory & streaming considerations**
S4 SHOULD be implemented to avoid materialising all arrivals in memory:

* Recommended pattern per `(ph, mf, scenario_id, seed)`:

  * Load `s3_bucket_counts_5B` in **batches** (e.g. per merchant or per time-slice).
  * For each batch:

    * join to `s1_time_grid_5B` (small, reusable),
    * pull only the required slices from routing surfaces (`s1_site_weights`, alias tables, edge catalogue),
    * expand into arrivals and flush to `s4_arrival_events_5B` output files.
* This supports:

  * **bounded memory** (no dependence on N_total), and
  * incremental progress even for very large N_total.

Any implementation that attempts to hold all arrivals for a large run in memory is **discouraged**.

---

11.3 **I/O profile**

For a given `(ph, mf, scenario_id, seed)`:

* **Reads** (dominant surfaces):

  * `s3_bucket_counts_5B` — full scan (one row per `(entity, bucket)`).
  * `s1_time_grid_5B` — small dimension table (reused; ideally cached).
  * `site_locations`, `site_timezones` — read in segments aligned with the current merchant/bucket batch.
  * 2B routing surfaces (`s1_site_weights`, `s2_alias_index`/`blob`, `s4_group_weights`) and 3B edge surfaces — ideally loaded once per merchant or per merchant-group.
* **Writes**:

  * `s4_arrival_events_5B` — one write stream per `(seed, mf, scenario_id)` partition (potentially multi-file, but logically a single dataset).
  * Optional: diagnostics tables (summary/anomalies) — much smaller than arrivals.

To keep I/O efficient:

* S4 SHOULD favour **sequential reads** (scan or range reads) over many small random reads.
* Writers SHOULD use **reasonable Parquet row-group sizes** tuned for arrival volumes (e.g. large enough to amortise metadata, small enough to support predicate pushdown by merchant/scenario).

---

11.4 **Parallelism strategies**

S4 expansion is naturally parallelisable because:

* different `(seed, scenario_id)` pairs are **independent**, and
* within a single `(seed, scenario_id)`, different merchant ranges or time ranges can often be processed independently, provided RNG streams are partitioned carefully.

Recommended strategies:

* **Coarse-grained parallelism** (preferred):

  * Run different `(seed, scenario_id)` combinations in parallel, with each worker owning its own RNG streams (no overlap by construction).
* **Medium-grained parallelism**:

  * Within a `(seed, scenario_id)`, shard the domain by merchant ranges or by time ranges and assign each shard to a worker.
  * The RNG policy MUST ensure each worker gets a disjoint Philox counter or substream slice so that the combined RNG trace is equivalent to a single logical stream.

Fine-grained parallelism (e.g. per-arrival threads) is possible but usually unnecessary; it complicates RNG accounting and is not required for correctness.

---

11.5 **Throughput & backpressure**

Given that S4’s cost grows linearly with `N_total`:

* High-volume scenarios (e.g. “busy month” + “high λ + multiple seeds”) will push both CPU (RNG + routing) and I/O (arrival writes).
* Implementations SHOULD:

  * monitor `n_arrivals_total` and per-seed volume via the run-report, and
  * use backpressure or admission control at orchestration level (e.g. maximum concurrent S4 runs per cluster) to avoid saturating storage and routing surfaces.

If the underlying storage system has throughput constraints:

* Prefer to reduce **concurrent S4 runs** rather than truncating arrivals; S4 is not allowed to drop or compress arrivals compared to S3’s counts.

---

11.6 **Scalability knobs (non-binding)**

Operators and implementers can influence S4’s performance indirectly via upstream configuration:

* **Bucket granularity (S1/S3)**

  * Finer buckets: more rows in S3 but smaller `N` per bucket, which may help load balancing and make intra-bucket timing more realistic but increases overhead.
  * Coarser buckets: fewer S3 rows but larger `N`, which may create “bursty” workloads at S4; implementation SHOULD ensure it can handle buckets with large N without memory blow-ups.

* **Scenario count & seeds**

  * More scenarios or seeds multiply S4 work almost linearly; orchestration can limit concurrent seeds/scenarios to bound resource usage.

* **Routing complexity**

  * Heavy routing policies (multiple hops, complex virtual semantics) increase per-arrival CPU cost; tuning 2B/3B policies can trade realism vs throughput.

None of these knobs change S4’s **logical obligations**; they only affect how expensive a given `(ph, mf, scenario_id, seed)` run is in practice.

---

11.7 **Failure & retry posture**

From a performance standpoint:

* S4 SHOULD be **idempotent** for a given identity; if a run fails due to transient I/O or infrastructure issues, it SHOULD be safe to re-run without special handling beyond cleaning up partial output.
* Implementations SHOULD consider:

  * writing to temporary locations then atomically promoting to final paths on PASS, to avoid partial datasets appearing as valid,
  * or tagging partial runs clearly so S5 and downstream never treat them as candidates.

This section is informative only, but the suggested patterns are intended to keep S4 scalable and operationally predictable as arrival volumes increase.

---

## 12. Change control & compatibility *(Binding)*

12.1 **Spec versioning**

12.1.1 **Segment-wide version**
All S4 behaviour is governed by a **segment-level spec version**:

* `5B_spec_version` (string, e.g. `"1.0.0"`)

This version:

* is defined at 5B level (not per state),
* MUST be recorded in:

  * `s0_gate_receipt_5B`,
  * the 5B artefact registry entries for S4 (`arrival_events_5B`),
  * and the 5B run-report for S4.

S4 MUST NOT change semantics without updating `5B_spec_version` according to the rules below.

---

12.2 **Backwards-compatible vs breaking changes**

12.2.1 **Backwards-compatible changes (allowed within minor/patch bump)**
The following changes MAY be introduced under a **backwards-compatible** bump (e.g. `1.0.0 → 1.1.0` or `1.0.0 → 1.0.1`), provided they do **not** change the meaning of existing fields:

* Adding **new optional columns** to `s4_arrival_events_5B` with sensible defaults and no impact on existing columns.
* Adding or removing **optional diagnostics datasets** (`s4_arrival_summary_5B`, `s4_arrival_anomalies_5B`), as long as:

  * `s4_arrival_events_5B` remains unchanged in schema and semantics.
* Tightening **acceptance criteria** in S5 that only add extra checks but do not change what a “valid” S4 dataset looks like for existing consumers.
* Adding **new RNG event families** or additional run-report metrics, provided:

  * existing RNG families, their meanings, and accounting laws are preserved.

In these cases:

* `5B_spec_version` SHOULD bump the **minor** or **patch** component.
* Downstream consumers MAY safely accept the new version if they ignore unknown optional fields.

12.2.2 **Breaking changes (require major bump + coordination)**
The following are **breaking** and MUST only be introduced with a **major** spec bump (e.g. `1.x.y → 2.0.0`), and with coordinated updates to downstream consumers (6A/6B and ingestion):

* Changing the **primary key** or partitioning scheme of `s4_arrival_events_5B`.
* Changing the **semantics** of existing fields, including:

  * interpretation of `ts_utc` or local timestamps (e.g. DST policy change),
  * meaning of `is_virtual`, `site_id`, `edge_id`, or zone representation.
* Changing the **arrival identity model**, e.g.:

  * moving from one-arrival-per-row to event-grouping,
  * removing or repurposing `bucket_index` linkage to S3.
* Changing routing behaviour in a way that:

  * violates previous invariants tied to 2B/3B policies, or
  * would cause an unchanged 6A/6B implementation to misinterpret events.
* Changing the **RNG law** in a way that breaks replayability for the same `(ph, mf, scenario_id, seed)` (e.g. different number of draws per arrival) without updating RNG validation.

In these cases:

* `5B_spec_version` MUST bump its **major** component.
* S4 MUST NOT emit `validation_bundle_5B` PASS unless the artefact registry and run-report clearly expose the new major version so downstream can reject or adapt.

---

12.3 **Schema & catalogue evolution**

12.3.1 **Schema pack (`schemas.5B.yaml`)**

* Any change to the `s4_arrival_events_5B` anchor (columns, PK, partition_keys, types) MUST be:

  * reflected in `schemas.5B.yaml`,
  * accompanied by an appropriate `5B_spec_version` bump:

    * minor/patch for optional additions,
    * major for breaking changes as per §12.2.2.

12.3.2 **Dataset dictionary (`dataset_dictionary.layer2.5B.yaml`)**

* The dictionary entry for `arrival_events_5B` MUST include:

  * `spec_version: {5B_spec_version}`,
  * and MUST be updated alongside any schema change.
* Any change to `path`, `partitioning.keys`, or `final_in_layer` for `arrival_events_5B` is considered **breaking** and requires a major bump.

12.3.3 **Artefact registry (`artefact_registry_5B.yaml`)**

* The registry entry for `arrival_events_5B` MUST:

  * store the current `5B_spec_version`,
  * list dependencies on upstream segments by **range** (e.g. `2B_spec_version >= 1.2.0`), when relevant.
* If S4 semantics start to assume a higher minimum version of an upstream segment (e.g. a new 3B routing feature), this MUST be recorded in the registry and treated as a compatibility constraint at orchestration time.

---

12.4 **Compatibility contract with Layer-3 (6A/6B)**

12.4.1 **Consumer expectations**

Layer-3 and enterprise ingestion are allowed to assume:

* `s4_arrival_events_5B` exists and is **authoritative** for arrivals,
* its schema and semantics match the `5B_spec_version` declared in:

  * the artefact registry, and
  * S5’s validation bundle metadata.

12.4.2 **Gating on version**

* Downstream consumers SHOULD:

  * declare a minimum accepted `5B_spec_version` range,
  * reject or run in “compat mode” for versions outside that range.
* S5 MUST expose `5B_spec_version` in the `validation_bundle_5B` metadata so this gating is possible without re-reading the registry.

---

12.5 **Cross-version coexistence**

If multiple `5B_spec_version` values need to coexist (e.g. old runs vs new runs):

* Partitions for different runs (different `manifest_fingerprint` or `seed`) MAY use different `5B_spec_version` values.
* Within a **single** `(manifest_fingerprint, seed, scenario_id)`:

  * mixed versions for `s4_arrival_events_5B` are **not allowed**; S4 MUST ensure all files for that logical dataset share the same version.
  * any attempt to “upgrade in place” MUST be treated as a full replace and revalidated as if it were a new dataset.

---

12.6 **Deprecation**

When planning to deprecate an S4 feature (e.g. an optional column or diagnostics table):

* The feature MUST first be marked as **deprecated** in:

  * the 5B spec document (this section or dataset docs),
  * and, where appropriate, as `status: "deprecated"` in the dictionary/registry.
* Actual removal of the feature (field or dataset) is **breaking** and MUST follow the major bump rules in §12.2.2.

---

12.7 **Non-negotiables**

Regardless of version:

* S4 MUST always respect the **authority boundaries** defined in §§2–3 (no takeover of 5A/2A/2B/3A/3B responsibilities).
* S4 MUST always:

  * preserve S3 counts,
  * obey time grid and DST semantics,
  * obey routing/virtual semantics,
  * satisfy RNG accounting.

No version bump (major or otherwise) can relax those fundamental invariants without a deliberate redesign of upstream segments and the overall engine.

---

## 13. Appendix A — Symbols & notational conventions *(Informative)*

This appendix is **informative only**. It fixes the shorthand and symbols used throughout 5B.S4 so the binding sections stay readable.

---

### 13.1 Identity & scope symbols

* `ph` — shorthand for `parameter_hash` (5A/5B parameter pack identity).
* `mf` — shorthand for `manifest_fingerprint` (Layer-1 world identity).
* `sid` — shorthand for `scenario_id`.
* `seed` — RNG identity for a 5B run.
* `run_id` — log/execution identity; **never** affects dataset content.
* `(ph, mf, sid, seed)` — the **logical identity quadruple** for the arrival realisation that S4 produces.

---

### 13.2 Time & grid symbols

* `b` — bucket index (`bucket_index`) as defined by `s1_time_grid_5B`.
* `t_b_start`, `t_b_end` — start and end of bucket `b` in UTC (`bucket_start_utc`, `bucket_end_utc`).
* `Δt_b` — duration of bucket `b`, `Δt_b = t_b_end − t_b_start`.
* `δ` — intra-bucket offset in `[0, Δt_b)`.
* `ts_utc` — realised arrival timestamp in UTC: `ts_utc = t_b_start + δ`.
* `ts_local_primary` — corresponding local timestamp for the **primary** tzid.
* `tzid_primary` — primary IANA timezone identifier (physical: site; virtual: as per virtual policy).

For virtual dual-clock semantics (if used):

* `tzid_settlement`, `ts_local_settlement` — local clock for settlement context.
* `tzid_operational`, `ts_local_operational` — local clock for operational context.

---

### 13.3 Entity & bucket symbols

* `m` — `merchant_id`.

* `z` — `zone_representation` (zone key consistent with 5A/5B).

* `ch` — optional channel attribute (if used in 5A/5B).

* `e` — shorthand for an “entity” tuple (e.g. `e = (m, z[, ch])`).

* `(e, b)` — a single row in `s3_bucket_counts_5B` (entity + bucket).

* `N` or `N_{e,b}` — bucket-level count from S3 for entity `e` and bucket `b`.

---

### 13.4 Arrival & routing symbols

* `arrival_id` / `arrival_seq` — per-arrival sequence/identifier within `(mf, seed, sid)` (exact choice fixed in schema).
* `is_virtual` — boolean flag:

  * `false` → routed to a **physical** site (`site_id` non-null, `edge_id` null).
  * `true` → routed to a **virtual** edge (`edge_id` non-null, `site_id` null).
* `site_id` — identifier of a physical outlet in `site_locations`.
* `edge_id` — identifier of a virtual edge in `edge_catalogue_3B`.
* `g` / `group_id` — optional grouping identifier from `s1_grouping_5B` / routing fabric (e.g. tz-group).
* `routing_universe_hash` — digest tying routing/zone/edge universe together (echo of 3A/3B hash, when present).

---

### 13.5 Intensity & counts symbols (context from upstream)

These appear only for context in S4; the **authoritative definitions** live in 5A/S2/S3 and 5B.S2/S3:

* `λ_target` — target intensity from 5A (scenario surfaces).
* `λ_realised` — realised intensity after latent field in 5B.S2.
* `N` — integer count drawn in 5B.S3 for `(e, b)` (used by S4; not changed by S4).

S4 **never** changes `λ_target`, `λ_realised` or `N`; it only expands `N` into `N` arrivals.

---

### 13.6 RNG symbols

* Philox — the global counter-based RNG family fixed at layer level.
* `rng_envelope` — shared schema for RNG events (fields like `seed`, `parameter_hash`, counters, `draws`, `blocks`).
* `substream_label` — string label distinguishing S4 RNG families, e.g.:

  * `"arrival_time_jitter"` — intra-bucket time draws.
  * `"arrival_site_pick"` — site routing draws.
  * `"arrival_edge_pick"` — edge routing draws.
* `rng_trace_log` — aggregated per-family RNG accounting table (draws/blocks per run).

Where we write “one draw per arrival” or similar, that is shorthand for “one Philox uniform sample, recorded via an S4 RNG event under the appropriate `substream_label`”.

---

### 13.7 Set & index conventions

* Domains:

  * `D₃` — domain of S3: all `(e, b)` with a defined `N`.
  * `D_arr` — domain of S4 arrivals: all rows in `s4_arrival_events_5B` for `(ph, mf, sid, seed)`.

* Intervals:

  * Time intervals are always **half-open**: `[start, end)`.

Unless explicitly stated otherwise, indices start at 0 for buckets (`bucket_index`) and at 1 for sequence fields (`arrival_seq`).

---
