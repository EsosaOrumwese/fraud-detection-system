```
                         LAYER 2 · SEGMENT 5B — ARRIVAL REALISATION (FROM λ TO EVENTS)

Authoritative inputs for 5B (sealed by 5B.S0)
---------------------------------------------
[World & identity]
    - manifest_fingerprint       (which Layer-1 world: 1A–3B / 2B / 3B)
    - parameter_hash             (which 5A/5B parameter pack)
    - seed                       (stochastic seed for latent fields & counts)
    - run_id                     (logical run identifier; does not affect data partitions)

[Upstream HashGates (MUST be PASS)]
    - Segment 1A: merchant universe / hurdles
    - Segment 1B: site geolocation
    - Segment 2A: civil time / tzid
    - Segment 2B: routing plan (sites & edges)
    - Segment 3A: cross-zone allocation
    - Segment 3B: virtual merchant/edge world
    - Segment 5A: intensity planner (class, shapes, baselines, scenario λ)
      · 5B S0 checks each segment’s bundle + flag for this manifest_fingerprint.

[World & intensity surfaces 5B may use]
    - From Layer-1:
        · site_locations           (sites + coordinates)
        · site_timezones, tz_timetable_cache (tzid per site, UTC↔local mapping)
        · zone_alloc, virtual surfaces (3A/3B) as needed for routing context.
    - From 2B:
        · routing plan for sites (site weights, alias tables, routing config)
        · routing RNG policy for site & edge picks.
    - From 3B:
        · virtual classification, settlement nodes
        · edge_catalogue, edge_alias_blob/index, edge_universe_hash
        · virtual routing policy.
    - From 5A:
        · scenario intensities λ_target(m, zone, bucket) on a known grid
        · scenario horizon and metadata.

[5B configs & RNG policy]
    - Latent field config (LGCP / “no latent field” etc.)
    - Arrival count law config (Poisson / NB / mixed etc.)
    - Micro-time placement policy (how to place arrivals inside a bucket)
    - 5B RNG policy:
        · which Philox streams/substreams are used for:
            - latent draws (S2),
            - bucket counts (S3),
            - time-in-bucket & routing (S4),
        · how RNG events are logged and traced.

5B state flow
-------------
S0: Gate & sealed inputs
S1: Time grid & grouping plan
S2: Latent intensity fields (LGCP) & λ_realised
S3: Bucket-level arrival counts
S4: Micro-time & routing to sites/edges
S5: Validation bundle & `_passed.flag_5B` (HashGate)


DAG
---
(World, HashGates, configs) --> (S0) GATE & SEALED INPUTS                  [NO RNG]
    - Checks that 1A–3B & 5A bundles/flags all PASS for this manifest.
    - Uses dictionaries/registries to discover all artefacts 5B is allowed to use:
        · world geometry/time,
        · routing surfaces (2B/3B),
        · 5A intensities & horizons,
        · 5B policies & RNG profiles.
    - Computes SHA-256 digests over these artefacts, and writes:
        · `sealed_inputs_5B@fingerprint={manifest_fingerprint}`:
              one row per artefact with owner, path_template, schema_ref, sha256_hex, role, status, read_scope.
        · `s0_gate_receipt_5B@fingerprint`:
              manifest_fingerprint, parameter_hash, seed, run_id,
              scenario_set_5B, verified_upstream_segments,
              sealed_inputs_digest (hash over sealed_inputs_5B).
    - S0 is RNG-free and row-free: it only fixes **what** 5B may see and **which world** it lives in.

                                      |
                                      | s0_gate_receipt_5B, sealed_inputs_5B
                                      v

(S1) TIME GRID & GROUPING PLAN                                         [NO RNG]
    inputs:
        - 5A scenario manifest (scenarios + horizons),
        - 2A civil-time law (for local-time labelling, metadata only),
        - 5A scenario λ surfaces (metadata only, to see which entities exist),
        - S0’s identity & sealed inputs,
        - time_grid_policy_5B, grouping_policy_5B.
    -> s1_time_grid_5B@fingerprint,scenario_id
         - For each scenario:
              - splits the scenario’s horizon [start_utc, end_utc) into ordered buckets:
                    bucket_index b, bucket_start_utc, bucket_end_utc,
              - may annotate buckets with scenario tags and simple local-time metadata.
         - This is the canonical **time grid** for 5B; later states MUST use these buckets.

    -> s1_grouping_5B@fingerprint,scenario_id
         - From 5A scenario λ surfaces:
              - builds set of entities E(scenario) = (merchant, zone_representation[, channel_group]) that have support.
         - Applies grouping_policy_5B:
              - assigns each entity a group_id (for shared latent field behaviour).
         - S2 will use these group_ids to sample latent fields; S3/S4 may treat group metadata as read-only.

    - S1 is RNG-free; it decides **when** we’ll draw arrivals (buckets) and **who** shares latent structure.

                                      |
                                      | s1_time_grid_5B, s1_grouping_5B
                                      v

(S2) LATENT INTENSITY FIELDS & REALISED λ                              [RNG-BEARING]
    inputs:
        - s1_time_grid_5B (bucket set per scenario),
        - s1_grouping_5B (entity→group mapping),
        - 5A scenario λ_target(m,zone, bucket),
        - latent-field config (LGCP or “no latent”),
        - 5B RNG policy (latent streams).
    -> s2_realised_intensity_5B@seed,fingerprint,scenario_id
         - For each scenario, for each group:
              - builds a latent field Z(group, bucket) over time using the chosen LGCP/latent law,
                drawing correlated noise via Philox (logged as RNG events).
         - For each entity×bucket:
              - looks up λ_target from 5A,
              - applies group’s latent factor ξ(Z) and any clipping rules,
              - produces λ_realised(entity,bucket) ≥ 0 and finite.
         - Writes one row per entity×bucket with λ_target, λ_realised, group and RNG lineage.

    (optional) -> s2_latent_field_5B@seed,fingerprint,scenario_id
         - Stores latent field values per group×bucket for diagnostics.

    - S2 is the **only** place 5B introduces correlated intensity noise on top of 5A’s deterministic λ.

                                      |
                                      | s2_realised_intensity_5B, s1_time_grid_5B, s1_grouping_5B
                                      v

(S3) BUCKET-LEVEL ARRIVAL COUNTS                                     [RNG-BEARING]
    inputs:
        - s1_time_grid_5B (bucket durations),
        - s1_grouping_5B (entity set),
        - s2_realised_intensity_5B (λ_realised per entity×bucket),
        - arrival_count_config_5B (Poisson/NB law),
        - arrival_rng_policy_5B (count streams).
    -> s3_bucket_counts_5B@seed,fingerprint,scenario_id
         - Domain: for each scenario, entity key and bucket_index.
         - For each (entity,bucket):
              - uses λ_realised and bucket_duration to compute law parameters,
              - samples a **count N** using configured arrival law and RNG,
              - logs RNG events and updates RNG trace/audit logs.
         - Writes one row per entity×bucket with `count_N` and optional law parameters.

    - S3 converts intensities into **integer counts per bucket**, preserving λ semantics via the arrival law.

                                      |
                                      | s3_bucket_counts_5B, s1_time_grid_5B, s1_grouping_5B
                                      v

(S4) MICRO-TIME & ROUTING TO SITES/EDGES                              [RNG-BEARING]
    inputs:
        - s1_time_grid_5B (bucket windows),
        - s1_grouping_5B (entity keys),
        - s3_bucket_counts_5B (counts N per entity×bucket),
        - Layer-1 geometry/time (site_locations, site_timezones, tz_timetable_cache),
        - 2B routing surfaces (site alias tables, route_rng_policy, etc.),
        - 3B virtual routing surfaces (edge universe & alias tables, virtual_routing_policy_3B),
        - s4_time_placement_policy_5B,
        - s4_routing_policy_5B,
        - s4_rng_policy_5B.
    -> arrival_events_5B (a.k.a. s4_arrival_events_5B)@seed,fingerprint,scenario_id
         - For each scenario, for each entity×bucket with N>0:
              1. **Micro-time inside bucket:**
                     - draws N uniforms u,
                     - maps each into (start_utc, end_utc) to get ts_utc per arrival,
                     - logs RNG events (time-in-bucket).
              2. **Routing:**
                     - decides physical vs virtual route based on merchant/zone and routing policy,
                     - for physical:
                           * uses 2B site alias tables to sample `site_id`,
                           * uses 2A tz data to derive ts_local, tzid_local.
                     - for virtual:
                           * uses 3B edge alias tables to sample `edge_id`,
                           * uses 3B tz semantics (edge tzid) to derive ts_local/tzid_local.
                     - logs routing RNG events (site/edge picks).
         - Writes one row per realised arrival with:
               world + scenario + seed identity,
               entity key + bucket_index + arrival_seq,
               ts_utc + optional local time,
               site_id or edge_id, plus routing context.

    - S4 expands each bucket count N into N **actual arrival events** with concrete timestamps and routing.

                                      |
                                      | S0–S4 outputs + RNG logs + configs
                                      v

(S5) VALIDATION BUNDLE & `_PASSED.FLAG_5B`                              [NO RNG]
    inputs:
        - s0_gate_receipt_5B, sealed_inputs_5B,
        - s1_time_grid_5B, s1_grouping_5B,
        - s2_realised_intensity_5B,
        - s3_bucket_counts_5B,
        - arrival_events_5B,
        - RNG logs for S2–S4,
        - 5B validation config (check IDs, thresholds).
    -> validation_report_5B@fingerprint
         - Replays invariants across S0–S4:
              - S0: sealed_inputs & upstream gate integrity,
              - S1: grid/frame coverage & grouping domain,
              - S2: λ_realised ≥ 0, domain alignment with S1, latent field law,
              - S3: counts vs λ_realised & law parameters,
              - S4: arrivals vs counts (N), bucket windows, civil time and routing correctness, RNG accounting.
         - Summarises PASS/FAIL per check and metrics.

    -> validation_issue_table_5B@fingerprint (optional)
         - Per-issue rows for detailed diagnostics.

    -> validation_bundle_index_5B@fingerprint/index.json
         - Lists all evidence files in the 5B validation bundle:
               [{path, sha256_hex}, …], paths relative to the 5B validation root.

    -> `_passed.flag_5B`@fingerprint
         - Recomputes a single bundle digest:
               bundle_digest = SHA256( concat( bytes(files in index order) ) ).
         - Writes `_passed.flag_5B` with:
               `sha256_hex = <bundle_digest>`.

    - S5 is RNG-free; it creates the 5B **HashGate** for this manifest.

Downstream obligations
----------------------
- Any consumer of 5B arrival events (Layer-3, ingestion, analytics) MUST:
    1. Read `validation_bundle_index_5B` and `_passed.flag_5B` for the manifest_fingerprint.
    2. Recompute the bundle digest using the same law.
    3. Confirm `_passed.flag_5B.sha256_hex` equals the recomputed digest.
    4. Confirm `validation_report_5B.status == "PASS"`.

- Only then may they read `arrival_events_5B` or treat any 5B outputs as valid.

- In short:

      **No 5B PASS (bundle + flag + report) → No read/use of arrivals.**

Legend
------
(Sx) = state in Segment 5B
[seed, fingerprint, scenario_id]   = partitions for stochastic S2–S4 outputs
[fingerprint]                      = partitions for S0, S5 outputs
[NO RNG]                           = state consumes no RNG
[RNG-BEARING]                      = state uses Philox under explicit RNG policy
HashGate (5B)                      = validation_bundle_index_5B + `_passed.flag_5B` per manifest_fingerprint
```