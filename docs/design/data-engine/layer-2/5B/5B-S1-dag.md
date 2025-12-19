```
        LAYER 2 · SEGMENT 5B — STATE S1 (TIME GRID & GROUPING PLAN)  [NO RNG]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5B
      @ data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
      · provides, for this 5B run:
          - manifest_fingerprint     (world id from 1A–3B),
          - parameter_hash           (5A/5B parameter pack),
          - seed, run_id             (run identity; S1 outputs MUST NOT depend on these),
          - scenario_set_5B          (set/list of scenario_id values in scope),
          - verified_upstream_segments.{1A,1B,2A,2B,3A,3B,5A},
          - sealed_inputs_digest     (SHA-256 hash over sealed_inputs_5B).
      · S1 MUST:
          - trust upstream PASS/FAIL as given,
          - treat sealed_inputs_digest as the canonical fingerprint of the 5B input universe.

    - sealed_inputs_5B
      @ data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
      · describes every artefact 5B.S1–S4 are allowed to read:
          - {owner_layer, owner_segment, artifact_id, manifest_key,
             path_template, partition_keys[], schema_ref,
             sha256_hex, role, status, read_scope, source_dictionary, source_registry}.
      · S1 MUST:
          - only resolve inputs that appear here,
          - respect `status` (REQUIRED/OPTIONAL/IGNORED),
          - respect `read_scope`:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → may only inspect metadata / digests.

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.layer2.yaml, schemas.5B.yaml
        · shape authority for S1 outputs:
              - schemas.5B.yaml#/model/s1_time_grid_5B,
              - schemas.5B.yaml#/model/s1_grouping_5B.
    - dataset_dictionary.layer2.5B.yaml
        · IDs & contracts for:
              - s1_time_grid_5B
                · description: canonical scenario-level time grid for arrivals.
                · path:
                    data/layer2/5B/s1_time_grid/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_time_grid_5B.parquet
                · partitioning: [fingerprint, scenario_id]
                · primary_key:  [manifest_fingerprint, scenario_id, bucket_index]
                · ordering:     [scenario_id, bucket_index].
              - s1_grouping_5B
                · description: deterministic mapping from merchant×zone×channel to latent group IDs.
                · path:
                    data/layer2/5B/s1_grouping/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_grouping_5B.parquet
                · partitioning: [fingerprint, scenario_id]
                · primary_key:  [manifest_fingerprint, scenario_id, merchant_id, zone_representation, channel_group]
                · ordering:     [scenario_id, merchant_id, zone_representation, channel_group].
    - dataset_dictionary.layer1.*.yaml + artefact_registry_{1A,1B,2A,2B,3A,3B,5A,5B}.yaml
        · used ONLY to resolve logical IDs referenced in sealed_inputs_5B to concrete artefacts.

[Upstream surfaces S1 depends on (must be listed in sealed_inputs_5B)]
    - 5A scenario manifest & surfaces (authorities on scenarios & horizons)
        · “Scenario manifest” from 5A:
            - defines which scenario_id values exist for this (parameter_hash, manifest_fingerprint),
            - gives each scenario’s horizon start/end in UTC,
            - labels scenarios (baseline, stress, holiday, etc.).
        · 5A scenario intensity surfaces (metadata only in S1):
            - used to derive which merchant×zone×scenario entities should be in scope for grouping.

    - 2A civil-time assets (authorities on UTC⇄local mapping)
        · `tz_timetable_cache` and related civil-time manifests:
            - define how every UTC instant maps to local time for each tzid,
            - handle DST gaps/folds.
        · S1 uses these only to attach local-time attributes to time buckets in s1_time_grid_5B
          (e.g. local day-of-week & time-of-day tags), NOT to produce any new tz logic.

    - World / routing metadata (for grouping features, optional)
        · zone_alloc, site_timezones, routing/meta surfaces from 2B/3A/3B:
            - used only to derive features for grouping (e.g. physical vs virtual, zone cluster),
            - S1 MUST NOT alter or reinterpret their contracts.

[5B policies & configs (for S1)]
    - time_grid_policy_5B
        · config that describes:
            - how to discretise each scenario’s horizon into buckets:
                 · bucket duration,
                 · coding of bucket_index,
            - which scenario tags/labels to carry onto grid rows.

    - grouping_policy_5B
        · config that defines:
            - which entities to group:
                 · default: (merchant_id, zone_representation[, channel_group]) per scenario,
            - which features (from 5A, 2A, 3A, 3B) may be used in grouping decisions,
            - how to assign group_id deterministically (e.g. by stratifying by class, zone, scenario tag).

[Outputs owned by S1]
    - s1_time_grid_5B  (required)
      @ data/layer2/5B/s1_time_grid/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_time_grid_5B.parquet
      · partition_keys: [fingerprint, scenario_id]
      · primary_key:    [manifest_fingerprint, scenario_id, bucket_index]
      · ordering:       [scenario_id, bucket_index]
      · schema_ref:     schemas.5B.yaml#/model/s1_time_grid_5B
      · one row per (scenario_id, bucket_index), with at least:
            manifest_fingerprint,
            parameter_hash,
            scenario_id,
            bucket_index,
            bucket_start_utc, bucket_end_utc,
            scenario_tags (optional),         # baseline/stress labels etc.
            local_time_metadata (sketched here; detailed tz rules live in 2A).

    - s1_grouping_5B   (required)
      @ data/layer2/5B/s1_grouping/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_grouping_5B.parquet
      · partition_keys: [fingerprint, scenario_id]
      · primary_key:    [manifest_fingerprint, scenario_id, merchant_id, zone_representation, channel_group]
      · ordering:       [scenario_id, merchant_id, zone_representation, channel_group]
      · schema_ref:     schemas.5B.yaml#/model/s1_grouping_5B
      · one row per in-scope entity in the grouping domain, with at least:
            manifest_fingerprint,
            scenario_id,
            merchant_id,
            zone_representation,
            channel_group,
            group_id,
            grouping_policy_id,
            grouping_policy_version.

[Numeric & RNG posture]
    - RNG:
        · S1 is **strictly RNG-free**:
            - MUST NOT open or advance any Philox stream,
            - MUST NOT emit RNG events or mutate RNG logs.
    - Determinism:
        · For fixed (parameter_hash, manifest_fingerprint, scenario_set_5B) and fixed sealed_inputs_5B,
          S1 MUST produce byte-identical s1_time_grid_5B & s1_grouping_5B, regardless of seed or run_id.
    - Identity scope:
        · Outputs are partitioned by [fingerprint, scenario_id].
        · They MUST NOT introduce a seed or run_id partition dimension.


----------------------------------------------------------------------
DAG — 5B.S1 (5A scenarios + 2A time law → time grid & grouping)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S1.1) Load S0 artefacts & fix identity
                    - Resolve:
                        · s0_gate_receipt_5B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_5B@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer2.5B.yaml.
                    - Validate both against schemas.5B.yaml.
                    - From s0_gate_receipt_5B:
                        · fix parameter_hash, manifest_fingerprint, seed, run_id,
                        · read scenario_set_5B = list/set of scenario_id values,
                        · read verified_upstream_segments for {1A,1B,2A,2B,3A,3B,5A}.
                    - Recompute SHA-256 over sealed_inputs_5B rows in a canonical manner;
                      require equality with sealed_inputs_digest.
                    - If any upstream segment that 5B depends on is not PASS:
                        · S1 MUST fail (world not valid for Layer-2 arrivals).

sealed_inputs_5B,
[Schema+Dict]
                ->  (S1.2) Resolve 5A scenario surfaces, 2A civil-time assets & S1 policies
                    - Using sealed_inputs_5B + dictionaries/registries:
                        · resolve 5A scenario manifest artefact(s):
                              - must declare:
                                    scenario_id values for this (parameter_hash, manifest_fingerprint),
                                    each scenario’s horizon_start_utc/horizon_end_utc,
                                    scenario labels (baseline/stress/etc.).
                        · resolve 5A scenario intensity surfaces (metadata only):
                              - used to discover which merchant×zone×scenario entities have non-zero support or are in-scope.
                        · resolve civil-time artefacts from 2A:
                              - `tz_timetable_cache`, and any associated tz manifests required to derive local-time tags.
                        · resolve S1 policies:
                              - time_grid_policy_5B,
                              - grouping_policy_5B.
                    - For each external artefact resolved:
                        · locate its row in sealed_inputs_5B by (owner_layer,owner_segment,artifact_id),
                        · recompute SHA-256(raw bytes),
                        · assert equality with sealed_inputs_5B.sha256_hex.
                    - Validate policy & manifest shapes against their schema_refs.

[5A scenario manifest],
scenario_set_5B,
time_grid_policy_5B
                ->  (S1.3) Derive scenario horizon windows
                    - For each scenario_id ∈ scenario_set_5B:
                        · look up in 5A scenario manifest:
                              horizon_start_utc(scenario_id),
                              horizon_end_utc(scenario_id),
                              scenario_tags (baseline/stress/holiday tags).
                    - Apply time-grid policy:
                        · check each horizon window is non-empty and well-formed:
                              horizon_start_utc < horizon_end_utc,
                        · decide bucket_duration for each scenario (or shared across scenarios).
                    - Build in-memory `HORIZON[scenario_id]`:
                        · the continuous [start_utc, end_utc) interval for each scenario.

HORIZON,
time_grid_policy_5B
                ->  (S1.4) Construct canonical time buckets for each scenario (UTC)
                    - For each scenario_id S in scenario_set_5B:
                        · derive bucket duration Δt (seconds) from time_grid_policy_5B.
                        · starting at horizon_start_utc(S), partition [start,end) into non-overlapping buckets:
                              bucket_index k = 0..K_S−1,
                              bucket_start_utc(k), bucket_end_utc(k),
                              such that:
                                   bucket_end_utc(K_S−1) == horizon_end_utc(S).
                    - Domain:
                        · For each S, define BUCKETS(S) = { (S,k) | k = 0..K_S−1 }.
                    - Attach scenario tags from manifest to each bucket as metadata (e.g. scenario_type).

BUCKETS(S) per scenario,
2A civil-time assets
                ->  (S1.5) Attach local-time tags to buckets (metadata only)
                    - For each scenario_id S and each bucket k:
                        · S1 MUST annotate:
                              - local_day_of_week,
                              - local_time_of_day ranges,
                          in a way that is consistent with 2A tz law and 5A shape grid.
                    - Because S1 is scenario/global (not per merchant), local tags here are coarse:
                        · e.g. “bucket S,k corresponds to Monday 10:00–11:00 local in the zone’s local clock”,
                          or a similar scheme agreed with S2–S4.
                    - S1 MUST:
                        · use civil-time assets only via 2A contracts (tz_timetable_cache etc.),
                        · NOT invent new tz semantics or override 2A’s gap/fold behaviour.
                    - Result: per (scenario_id, bucket_index) metadata capturing how S2–S4 can interpret bucket timing.

BUCKETS, local-time metadata
                ->  (S1.6) Assemble s1_time_grid_5B rows
                    - For each scenario_id S and bucket_index k:
                        · assemble row:
                              manifest_fingerprint,
                              parameter_hash,
                              scenario_id = S,
                              bucket_index = k,
                              bucket_start_utc,
                              bucket_end_utc,
                              scenario_tags (from 5A scenario manifest),
                              local_time_metadata (per policy and 2A rules).
                    - Sort rows by [scenario_id, bucket_index].
                    - Validate in-memory table against schemas.5B.yaml#/model/s1_time_grid_5B:
                        · PK uniqueness,
                        · coverage of full [start,end) interval for each scenario,
                        · no overlapping or missing buckets.

[5A scenario surfaces metadata],
zone_alloc / 5A λ surfaces,
(grouping_policy_5B),
scenario_set_5B
                ->  (S1.7) Derive grouping domain: entities to group
                    - For each scenario_id S:
                        · using 5A intensity surfaces (metadata only, as allowed by sealed_inputs_5B),
                          derive domain D_group(S) as:
                                set of (merchant_id, zone_representation[, channel_group]) that:
                                     - appear as active in the 5A scenario surface for S,
                                     - and pass any inclusion/exclusion filters in grouping_policy_5B
                                       (e.g. ignore very low-intensity tails if configured).
                        · `zone_representation` is the canonical zone key:
                              (legal_country_iso, tzid) or reversible zone_id, as defined in schemas.5B.yaml.
                        · `channel_group` is derived deterministically from upstream attributes if grouping uses channels.
                    - Validate:
                        · D_group(S) MUST be non-empty if grouping_policy_5B says “this scenario must be modelled”,
                        · all keys are well-formed (no null merchant_id, no malformed zone_representation).
                    - S1 MUST treat D_group(S) as the sole entity set for grouping in scenario S.

D_group(S),
grouping_policy_5B,
upstream features (metadata only)
                ->  (S1.8) Assign group_id to each entity (per scenario)
                    - For each scenario_id S:
                        - For each entity e = (merchant_id, zone_representation, channel_group) in D_group(S):
                              1. Build feature vector F(e,S):
                                     - may include:
                                           demand_class from 5A (metadata),
                                           zone attributes (from 3A),
                                           virtual vs physical flags (from 3B),
                                           scenario tags,
                                     - all features MUST be derived via artefacts listed in sealed_inputs_5B and
                                       MUST NOT require row-level reads when read_scope=METADATA_ONLY.
                              2. Apply grouping_policy_5B:
                                     group_id(e,S) = f_group(F(e,S), S),
                                     where f_group is a deterministic map defined by grouping_policy_5B.
                        - Enforce:
                              · every e ∈ D_group(S) receives exactly one group_id,
                              · group_id values are valid per schema (e.g. non-empty strings, or integers),
                              · grouping policy may cluster multiple entities into same group
                                but MUST NOT omit any entity in D_group(S).
                    - Failure (any entity without group_id, or invalid group_id) ⇒ `5B.S1.GROUP_ASSIGNMENT_INCOMPLETE`.

D_group(S),
group_id(e,S)
                ->  (S1.9) Assemble s1_grouping_5B rows
                    - For each scenario_id S and each entity e = (m, zone_representation, channel_group) ∈ D_group(S):
                        · assemble row:
                              manifest_fingerprint,
                              scenario_id          = S,
                              merchant_id          = m,
                              zone_representation  = zone_representation(e),
                              channel_group        = channel_group(e),
                              group_id             = group_id(e,S),
                              grouping_policy_id   = grouping_policy_5B.id,
                              grouping_policy_version = grouping_policy_5B.version.
                    - Sort rows by [scenario_id, merchant_id, zone_representation, channel_group].
                    - Validate in-memory table against schemas.5B.yaml#/model/s1_grouping_5B:
                        · PK uniqueness,
                        · every entity in D_group(S) represented exactly once for its scenario,
                        · no extra entities.

s1_time_grid_5B rows,
s1_grouping_5B rows
                ->  (S1.10) Persist s1_time_grid_5B & s1_grouping_5B (write-once, per scenario)
                    - For each scenario_id S ∈ scenario_set_5B:

                      1. s1_time_grid_5B:
                          - target path:
                                data/layer2/5B/s1_time_grid/fingerprint={manifest_fingerprint}/scenario_id={S}/s1_time_grid_5B.parquet
                          - if no dataset at target:
                                · write via staging → fsync → atomic move.
                          - if dataset exists:
                                · load existing, normalise schema+sort,
                                · if byte-identical → idempotent re-run; OK,
                                · else → `5B.S1.IO_WRITE_CONFLICT`; MUST NOT overwrite.

                      2. s1_grouping_5B:
                          - target path:
                                data/layer2/5B/s1_grouping/fingerprint={manifest_fingerprint}/scenario_id={S}/s1_grouping_5B.parquet
                          - same write-once/idempotence rules as above.

                    - S1 MUST NOT write any other datasets; it only produces s1_time_grid_5B and s1_grouping_5B.

Downstream touchpoints
----------------------
- **5B.S2 — Latent intensity fields (LGCP):**
    - MUST treat s1_time_grid_5B as the canonical time bucket grid per scenario:
          - S2 uses bucket_start_utc/bucket_end_utc and local-time tags; it MUST NOT define its own bucket boundaries.
    - MUST treat s1_grouping_5B as the canonical grouping:
          - S2 determines which `(merchant, zone[,channel])` entities share a latent field by reading group_id,
          - S2 MUST NOT re-group entities or create its own grouping scheme.

- **5B.S3 — Bucket-level arrival counts:**
    - Uses s1_time_grid_5B to align intensities with bucket windows and indexes.
    - Uses s1_grouping_5B metadata only (if needed) but MUST NOT change grouping.

- **5B.S4 — Arrival events (micro-time & routing):**
    - Uses s1_time_grid_5B to map bucket indices to time windows when placing micro-time arrivals.
    - Uses s1_grouping_5B only if grouping metadata is needed for debugging/audit; S4 MUST NOT override grouping.

- **5B.S5 — Validation bundle & `_passed.flag_5B`:**
    - Replays S1 invariants:
          - all in-scope entities for a scenario appear exactly once in s1_grouping_5B,
          - s1_time_grid_5B covers each scenario horizon completely with non-overlapping buckets,
          - local-time tags are consistent with 2A contracts.
    - Bundles S1 outputs as part of the 5B validation evidence for this manifest_fingerprint.
```