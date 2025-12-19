```
        LAYER 2 · SEGMENT 5B — STATE S4 (MICRO-TIME & ROUTING TO SITES/EDGES)  [RNG-BEARING]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5B
      @ data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
      · provides:
          - manifest_fingerprint, parameter_hash, seed, run_id,
          - scenario_set_5B (scenario_ids this run is responsible for),
          - verified_upstream_segments.{1A,1B,2A,2B,3A,3B,5A},
          - sealed_inputs_digest.
      · S4 MUST:
          - trust these upstream gate decisions,
          - recompute sealed_inputs_digest from sealed_inputs_5B and require equality.

    - sealed_inputs_5B
      @ data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
      · closed-world inventory of all artefacts S4 is allowed to read:
          - each row: {owner_layer, owner_segment, artifact_id, manifest_key,
                       path_template, partition_keys[], schema_ref,
                       sha256_hex, role, status, read_scope, source_dictionary, source_registry}.
      · S4 MUST:
          - only read artefacts that appear in this table,
          - honour `status` (REQUIRED/OPTIONAL/IGNORED),
          - honour `read_scope`:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → may only inspect metadata/digests.

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml         (RNG envelope, RNG events, rng_trace_log, etc.)
    - schemas.layer2.yaml         (Layer-2 validation & bundle contracts)
    - schemas.5B.yaml             (5B.S4 shapes: s4_arrival_events_5B, diagnostics)
    - dataset_dictionary.layer1.* (for 1A–3B, 2B, 5A surfaces S4 may use)
    - dataset_dictionary.layer2.{5A,5B}.yaml
        · IDs & contracts for:
            - s1_time_grid_5B         (5B.S1),
            - s1_grouping_5B          (5B.S1),
            - s3_bucket_counts_5B     (5B.S3),
            - s4_arrival_events_5B    (5B.S4 core output),
            - s4_arrival_summary_5B   (optional diagnostics).
    - artefact_registry_{1A,1B,2A,2B,3A,3B,5A,5B}.yaml
        · map logical IDs ↔ manifest_keys, roles, schema_refs.

[Internal 5B inputs]
    - s1_time_grid_5B
      @ data/layer2/5B/s1_time_grid/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_time_grid_5B.parquet
      · defines, for each scenario_id, ordered buckets:
            (bucket_index, bucket_start_utc, bucket_end_utc, optional local-time tags).
      · S4 uses this as the **only authority** on bucket time windows.

    - s1_grouping_5B
      @ data/layer2/5B/s1_grouping/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_grouping_5B.parquet
      · defines per scenario:
            entity keys: (merchant_id, zone_representation[, channel_group]),
            group_id for latent fields (already consumed in S2).
      · S4 uses entity keys to align counts with routing, but MUST NOT change groupings.

    - s3_bucket_counts_5B
      @ data/layer2/5B/s3_bucket_counts/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s3_bucket_counts_5B.parquet
      · one row per (scenario_id, merchant_id, zone_representation[,channel_group], bucket_index) with `count_N ≥ 0`.
      · This is the **only authority** on how many arrivals N must be realised per bucket.
      · S4 MUST:
            - emit exactly N arrivals per row where N>0,
            - emit zero arrivals where N==0,
            - NEVER resample or alter counts.

[Layer-1 geometry & time authority]
    - 1B: site_locations
        · defines physical outlets and their coordinates; S4 MUST treat this as read-only.
    - 2A: site_timezones, tz_timetable_cache, civil_time_manifest
        · sole authority for:
              - `tzid` per site,
              - UTC↔local mapping (including DST gaps/folds).
        · S4 MUST use these surfaces when deriving local timestamps; MUST NOT invent new tz logic.

[Routing authority: physical sites]
    - 2B routing plan surfaces:
        · site-level weights & alias tables:
              - s1_site_weights (per merchant, per site probabilities),
              - s2_alias_index + s2_alias_blob (alias tables),
              - s4_group_weights (group / day weights), etc.,
        · route_rng_policy_v1 + alias_layout_policy for sites.
      · Together, these define how arrivals are routed to **physical sites**.
      · S4 MUST:
            - call into these contracts (logically) when selecting a site_id,
            - NOT implement alternative weighting or alias schemes.

[Routing authority: virtual edges]
    - 3B virtual world:
        · virtual_classification_3B, virtual_settlement_3B,
        · edge_catalogue_3B, edge_catalogue_index_3B,
        · edge_alias_blob_3B, edge_alias_index_3B,
        · edge_universe_hash_3B,
        · virtual_routing_policy_3B, virtual_validation_contract_3B.
      · These define the universe & rules for virtual merchants.
      · S4 MUST:
            - obey virtual_routing_policy_3B when routing `is_virtual=true` arrivals to edge_id,
            - defer to edge alias surfaces for sampling edges.

[5B S4-specific configs: time placement & routing hooks]
    - s4_time_placement_policy_5B
        · defines how to place N arrivals inside a bucket [start_utc, end_utc):
              - e.g. uniform in time, or optionally modulated using a within-bucket shape,
              - how many u∈(0,1) draws per arrival,
              - how to handle boundaries (open/closed intervals, DST edges).
    - s4_routing_policy_5B
        · defines:
              - when to treat merchant as virtual vs physical (or hybrid),
              - any 5B-specific overrides on top of 2B/3B policies (e.g. exclude certain sites),
              - mapping of entity keys (merchant, zone_representation, channel_group) to routing context
                expected by 2B and 3B policies.
    - s4_rng_policy_5B
        · defines streams/substreams for:
              - micro-time draws,
              - site picks,
              - edge picks,
          and how they sit inside the global RNG envelope:
              - per-event `blocks`, `draws`,
              - mapping from (scenario_id, entity key, bucket_index, arrival_seq) → RNG stream/counter.

[Core output (required)]
    - s4_arrival_events_5B
      @ data/layer2/5B/arrival_events/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
      · partition_keys: [seed, fingerprint, scenario_id]
      · schema_ref: schemas.5B.yaml#/model/s4_arrival_events_5B
      · one row per realised arrival; at minimum:
            seed,
            manifest_fingerprint,
            parameter_hash,
            scenario_id,
            merchant_id,
            zone_representation,
            (optional) channel_group,
            bucket_index,        # which S3 bucket this arrival came from
            arrival_seq          # ordinal within that bucket (or a stable arrival_id),
            ts_utc               # UTC timestamp of arrival,
            ts_local             # local timestamp (optional, as per schema),
            tzid_local           # local tzid used for ts_local,
            is_virtual           ∈ {false, true},
            site_id              (if is_virtual=false),
            edge_id              (if is_virtual=true),
            routing_context_id/version (to tie to 2B/3B policies),
            optional: tz_source, local_day_of_week, etc.

[Optional outputs]
    - s4_arrival_summary_5B
      · aggregated diagnostics (counts per merchant/zone/scenario, etc.); not core to S4 DAG.

[Numeric & RNG posture]
    - S4 is **RNG-bearing**:
        · MUST use Philox only under configured s4_rng_policy_5B streams/substreams,
        · MUST log all RNG events and update rng_trace_log / rng_audit_log appropriately.
    - Determinism:
        · For fixed (seed, parameter_hash, manifest_fingerprint, scenario_id) and fixed inputs/configs,
          S4 MUST produce exactly the same arrival events (same ts_utc, site/edge choices, arrival_seq).
        · run_id MUST NOT affect arrival events (only RNG logs).
    - Scope:
        · S3 defines counts N; S4 only expands into arrivals and routes.
        · S4 MUST NOT change counts, shapes, λ or routing weights; it only consumes them.


----------------------------------------------------------------------
DAG — 5B.S4 (bucket counts → micro-time → routed arrivals)  [RNG-BEARING]

### Phase 1 — Gate & load inputs (no RNG)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S4.1) Load S0 receipt & sealed_inputs; fix identity
                    - Resolve:
                        · s0_gate_receipt_5B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_5B@fingerprint={manifest_fingerprint},
                      via 5B dictionary.
                    - Validate both documents against schemas.5B.yaml.
                    - From s0_gate_receipt_5B:
                        · fix (seed, parameter_hash, manifest_fingerprint, run_id),
                        · fix scenario_set_5B (scenario_ids),
                        · read verified_upstream_segments,
                        · read sealed_inputs_digest.
                    - Recompute sealed_inputs_digest from sealed_inputs_5B (canonical row order + serialisation);
                      require equality with receipt.
                    - If any upstream segment required by S4 (1A–3B, 2B, 3A/3B, 5A) is not PASS:
                        · S4 MUST fail; no arrival events may be produced.

sealed_inputs_5B,
[Schema+Dict]
                ->  (S4.2) Resolve S1/S3 data, routing & time policies
                    - Using sealed_inputs_5B + dictionaries/registries, resolve:
                        · s1_time_grid_5B@fingerprint={mf},scenario_id={S}  for all S ∈ scenario_set_5B,
                        · s1_grouping_5B@fingerprint={mf},scenario_id={S},
                        · s3_bucket_counts_5B@seed={seed},fingerprint={mf},scenario_id={S},
                        · Layer-1 geometry/time:
                              - site_locations,
                              - site_timezones, tz_timetable_cache,
                        · 2B routing artefacts:
                              - s1_site_weights,
                              - s2_alias_index + s2_alias_blob,
                              - group-weights surfaces, route_rng_policy_v1, alias layout,
                        · 3B virtual routing artefacts:
                              - virtual_classification_3B,
                              - edge_catalogue_3B, edge_alias_blob_3B, edge_alias_index_3B, edge_universe_hash_3B,
                              - virtual_routing_policy_3B,
                        · S4 configs:
                              - s4_time_placement_policy_5B,
                              - s4_routing_policy_5B,
                              - s4_rng_policy_5B.
                    - For each resolved external artefact:
                        · locate its row in sealed_inputs_5B,
                        · recompute SHA-256(raw bytes),
                        · assert equality with sha256_hex.
                    - Validate S1/S3 datasets:
                        · s1_time_grid_5B against `#/model/s1_time_grid_5B`,
                        · s1_grouping_5B against `#/model/s1_grouping_5B`,
                        · s3_bucket_counts_5B against `#/model/s3_bucket_counts_5B`.
                    - Validate configs/policies against schemas.5B.yaml and Layer-wide RNG schema.

### Phase 2 — Join counts with bucket windows & entity keys (no RNG)

s1_time_grid_5B,
s1_grouping_5B,
s3_bucket_counts_5B
                ->  (S4.3) Build expansion domain D₄ per scenario
                    - For each scenario_id S ∈ scenario_set_5B:
                        1. From s1_time_grid_5B(S):
                               BUCKETS(S) = set of bucket_index b, with (bucket_start_utc, bucket_end_utc).
                        2. From s1_grouping_5B(S):
                               E(S) = set of entities key = (merchant_id, zone_representation[, channel_group]).
                        3. From s3_bucket_counts_5B(S):
                               D_counts(S) = set of (key,b) for which count_N > 0 or ≥0.
                        4. Domain D₄(S):
                               D₄(S) = { (key,b) ∈ E(S)×BUCKETS(S) | row exists in s3_bucket_counts_5B(S) }.
                    - Invariants:
                        · Every row in s3_bucket_counts_5B(S) MUST correspond to some key ∈ E(S) and bucket_index ∈ BUCKETS(S),
                        · S4 MUST treat D₄(S) as its sole domain for expansions.
                        · It MUST NOT:
                              - drop any row with count_N > 0,
                              - create synthetic (key,b) domain elements.

s3_bucket_counts_5B,
s1_time_grid_5B
                ->  (S4.4) Attach bucket windows & counts to domain
                    - For each scenario_id S and (key,b) ∈ D₄(S):
                        · read count_N (integer ≥ 0) from s3_bucket_counts_5B,
                        · read bucket_start_utc, bucket_end_utc from s1_time_grid_5B(S),
                        · compute:
                              bucket_duration = bucket_end_utc − bucket_start_utc (seconds).
                    - Numeric checks:
                        · bucket_duration > 0 for all buckets,
                        · count_N is integer and ≥ 0.
                    - S4 MUST:
                        · remember count_N and bucket window for each (S,key,b),
                        · NEVER change count_N in the remainder of this state.

### Phase 3 — Micro-time: expand counts into intra-bucket timestamps (RNG-bearing)

s4_time_placement_policy_5B,
s4_rng_policy_5B,
D₄(S) with counts & bucket windows
                ->  (S4.5) Configure micro-time RNG streams per (S,key,b)
                    - From s4_rng_policy_5B:
                        · identify event family for micro-time draws, e.g. "5B.S4.time_in_bucket",
                        · define mapping M_time: (scenario_id S, key, bucket_index b, arrival_seq j)
                                            → RNG stream/substream & counters.
                        · define number of u∈(0,1) draws required per arrival (often 1).
                    - S4 MUST:
                        · use only these streams/substreams for micro-time,
                        · log each use in rng_event and update rng_trace_log.

D₄(S) with counts & bucket windows,
s4_time_placement_policy_5B,
M_time
                ->  (S4.6) Expand counts into per-arrival ts_utc via RNG
                    - For each scenario_id S:
                        · iterate D₄(S) in canonical order:
                              (merchant_id, zone_representation, channel_group, bucket_index).
                        · For each (key,b) with count_N=N > 0:
                              - define arrival sequences j = 0..N−1.
                              - For each j:
                                    1. Use M_time(S,key,b,j) and s4_rng_policy_5B to:
                                           - draw u ∈ (0,1) via Philox,
                                           - log RNG event (stream_id, counters_before/after, blocks, draws).
                                    2. Map u to a point in [bucket_start_utc, bucket_end_utc):
                                           ts_utc = bucket_start_utc + u * (bucket_end_utc − bucket_start_utc),
                                           with any edge-case rules (e.g. open/closed endpoints) from policy.
                    - If s4_time_placement_policy_5B supports within-bucket shape weighting:
                        · S4 applies that via deterministic transform of u (still RNG-driven but policy-governed).
                    - Invariants:
                        · Exactly N timestamps are produced for each (key,b) with count_N=N.
                        · ts_utc lies within the bucket window (respecting open/closed interval law).
                        · Micro-time RNG usage is fully logged and accounted.

### Phase 4 — Routing: decide site vs edge and select endpoint (RNG-bearing)

virtual_classification_3B,
s4_routing_policy_5B,
2B routing surfaces,
3B virtual routing surfaces
                ->  (S4.7) Decide routing mode per arrival: physical vs virtual
                    - For each entity key = (merchant_id, zone_representation[, channel_group]):
                        · load merchant-level virtual flag from virtual_classification_3B,
                          and any 5B-specific overrides from s4_routing_policy_5B.
                        - Determine routing mode:
                              mode ∈ {PHYSICAL_ONLY, VIRTUAL_ONLY, HYBRID} per merchant or (merchant,zone,channel).
                    - For each arrival (S,key,b,j):
                        · decide:
                              - if mode = PHYSICAL_ONLY  → route to site (site_id),
                              - if mode = VIRTUAL_ONLY   → route to virtual edge (edge_id),
                              - if HYBRID                → use policy-specific split:
                                    e.g. probability mass between physical vs virtual.
                        - HYBRID decisions that involve randomness MUST use a separate RNG substream
                          defined in s4_rng_policy_5B (and logged).

2B site routing surfaces,
3A zone_alloc,
s4_rng_policy_5B,
(ts_utc, key, b, j, routing mode=PHYSICAL_ONLY or physical branch of HYBRID)
                ->  (S4.8) Route physical arrivals to site_id via 2B plan (RNG-bearing)
                    - For arrival(s) routed to PHYSICAL:
                        1. Build routing context from key and upstream world:
                               - merchant_id m,
                               - zone information (country, tzid) from zone_alloc,
                               - any channel/zone grouping used in 2B plan.
                        2. Use 2B routing plan:
                               - choose tz_group_id (if 2B uses group weights),
                               - sample site using alias tables (s2_alias_index + s2_alias_blob),
                               - all RNG usage goes through route_rng_policy_v1, not ad-hoc streams.
                        3. Log RNG events:
                               - per group pick and site pick, with blocks/draws/counters,
                               - update rng_trace_log / rng_audit_log accordingly.
                        4. Produce:
                               site_id,
                               tzid_local = tzid from site_timezones[site_id].
                    - S4 MUST:
                        · honour 2B’s plan and RNG policy exactly,
                        · NOT alter routing weights or alias logic.

3B virtual surfaces,
virtual_routing_policy_3B,
s4_rng_policy_5B,
(ts_utc, key, b, j, routing mode=VIRTUAL_ONLY or virtual branch of HYBRID)
                ->  (S4.9) Route virtual arrivals to edge_id via 3B plan (RNG-bearing)
                    - For arrival(s) routed to VIRTUAL:
                        1. Build routing context from key and virtual-world surfaces:
                               - merchant_id m,
                               - edge universe for m from edge_catalogue_3B,
                               - edge alias structures from edge_alias_blob_3B + edge_alias_index_3B.
                        2. Apply virtual_routing_policy_3B:
                               - choose edge via alias tables using the RNG stream/substream
                                 configured for virtual `cdn_edge_pick`,
                               - interpret any dual-time semantics (settlement vs operational) as specified.
                        3. Log RNG events for edge picks:
                               - stream_id/substream_label,
                               - counters_before/after, blocks, draws.
                        4. Produce:
                               edge_id,
                               tzid_local = tzid_operational from edge_catalogue_3B[merchant_id,edge_id].
                    - S4 MUST:
                        · honour virtual_routing_policy_3B and edge_universe_hash_3B,
                        · NOT invent new edge distributions or override 3B semantics.

site_id or edge_id,
tzid_local,
ts_utc,
site_timezones / tz_timetable_cache
                ->  (S4.10) Derive local timestamps ts_local & tzid_local (no RNG)
                    - For each realised arrival:
                        · S4 MUST derive ts_local from ts_utc using 2A civil-time law:
                              - if physical:
                                    tzid_local from site_timezones[site_id],
                              - if virtual:
                                    tzid_local from edge_catalogue_3B[edge_id] or virtual_routing_policy_3B semantics.
                        · Use tz_timetable_cache and overrides exactly as 2A does:
                              - handle DST gaps/folds,
                              - make sure ts_local corresponds to a valid wall-clock time in tzid_local.
                    - Invariants:
                        · ts_local + tzid_local → recomputable ts_utc via 2A rules,
                        · no ts_local in a “forbidden” region (e.g. deleted hour) unless 2A defines behaviour.

### Phase 5 — Assemble & write s4_arrival_events_5B

arrival identity (S,key,b,j),
ts_utc, ts_local, tzid_local,
routing results (site_id / edge_id),
[Schema+Dict]
                ->  (S4.11) Assemble arrival event rows
                    - For each scenario_id S and each (key,b) ∈ D₄(S):
                        · let key = (merchant_id, zone_representation[, channel_group]).
                        · let count_N = N(S,key,b).
                        · for each sequence j ∈ {0..N−1}:
                              - compute arrival_seq = j or another deterministic sequence index,
                              - assemble row:
                                    seed                 = seed,
                                    manifest_fingerprint = mf,
                                    parameter_hash       = parameter_hash,
                                    scenario_id          = S,
                                    merchant_id          = m,
                                    zone_representation  = zone_representation,
                                    channel_group        = channel_group (if present),
                                    bucket_index         = b,
                                    arrival_seq          = j,
                                    ts_utc               = ts_utc(S,key,b,j),
                                    ts_local             = ts_local(S,key,b,j) (if schema requires),
                                    tzid_local           = tzid_local(S,key,b,j),
                                    is_virtual           = (mode==VIRTUAL_ONLY or virtual branch),
                                    site_id              = site_id (if is_virtual=false),
                                    edge_id              = edge_id (if is_virtual=true),
                                    routing_context_id   = ID of routing policy used (2B or 3B),
                                    routing_context_version = version,
                                    s4_spec_version      = current contract version (optional).
                    - Validate in-memory table against schemas.5B.yaml#/model/s4_arrival_events_5B:
                        · required fields present and well-typed,
                        · no duplicate primary keys (arrival_id or composite),
                        · per-(S,key,b) exactly count_N rows.

s4_arrival_events_5B rows,
dataset_dictionary.layer2.5B.yaml
                ->  (S4.12) Write s4_arrival_events_5B (write-once per seed/fingerprint/scenario)
                    - For each scenario_id S ∈ scenario_set_5B:
                        · target path:
                              data/layer2/5B/arrival_events/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={S}/…
                        · If no dataset exists at target:
                              - write rows for scenario_id=S via staging → fsync → atomic move.
                        · If dataset exists:
                              - load existing dataset, normalise schema+sort,
                              - if byte-identical → idempotent re-run; OK,
                              - else → immutability conflict; S4 MUST NOT overwrite.
                    - Constraints:
                        · S4 MUST NOT write arrival events into any path that does not embed (seed, fingerprint, scenario_id),
                        · S4 MUST NOT mix different scenario_id values in the same partition.

(optional) diagnostics (e.g. s4_arrival_summary_5B)
                ->  (S4.13) Write optional diagnostics (if configured)
                    - If diagnostic datasets are enabled and registered:
                        · derive them purely from s3_bucket_counts_5B and/or s4_arrival_events_5B
                          (e.g. total arrivals per merchant/zone/scenario),
                        · validate against their schema anchors,
                        · write to dictionary-specified paths with the same immutability/idempotence rules.
                    - Diagnostics MUST NOT be treated as egress for arrivals; only s4_arrival_events_5B is.

Downstream touchpoints
----------------------
- **5B.S5 — Validation bundle & `_passed.flag_5B`:**
    - MUST:
        · read s4_arrival_events_5B to verify:
              - per-(scenario,entity,bucket) counts equal s3_bucket_counts_5B.N,
              - timestamps lie in correct bucket windows,
              - local timestamps & tzids obey 2A civil-time law,
              - routing decisions obey 2B/3B policies and alias semantics,
              - RNG events & trace logs match S4 RNG usage.
        · bundle s4_arrival_events_5B and RNG evidence as part of 5B validation bundle.

- **Layer-3 (6A/6B, downstream simulations, analytics):**
    - MUST treat s4_arrival_events_5B as the **only** arrival egress surface from 5B.
    - MUST gate all reads of this dataset on 5B’s HashGate (`_passed.flag_5B`):
          **No 5B PASS → No read/use of 5B arrivals.**

- **5B.S4 authority boundary recap:**
    - S3 owns counts; S4 MUST not change N.
    - 2A owns civil-time; S4 MUST not change tz semantics.
    - 2B & 3B own routing laws & alias tables; S4 MUST not change those.
    - S4 owns only: “expand counts into timestamps, then route each arrival according to upstream routing contracts”.
```