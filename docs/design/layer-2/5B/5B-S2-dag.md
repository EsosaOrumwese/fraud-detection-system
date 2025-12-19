```
        LAYER 2 · SEGMENT 5B — STATE S2 (LATENT INTENSITY FIELDS & REALISED λ)  [RNG-BEARING]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5B
      @ data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
      · provides:
          - manifest_fingerprint, parameter_hash, seed, run_id,
          - scenario_set_5B (scenario_id values 5B intends to process),
          - verified_upstream_segments.{1A,1B,2A,2B,3A,3B,5A},
          - sealed_inputs_digest.
      · S2 MUST:
          - trust upstream PASS/FAIL from this receipt,
          - recompute sealed_inputs_digest from sealed_inputs_5B and assert equality.

    - sealed_inputs_5B
      @ data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
      · whitelist of artefacts 5B is allowed to read:
          - for each artefact:
                owner_layer, owner_segment, artifact_id, manifest_key,
                path_template, partition_keys[], schema_ref, sha256_hex,
                role, status, read_scope, source_dictionary, source_registry.
      · S2 MUST:
          - only read artefacts listed here,
          - honour status (REQUIRED/OPTIONAL/INTERNAL/IGNORED),
          - honour read_scope:
                · ROW_LEVEL      → may read data rows,
                · METADATA_ONLY  → may inspect metadata only.

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.layer2.yaml, schemas.5B.yaml
        · anchors for:
              - s1_time_grid_5B, s1_grouping_5B,
              - s2_realised_intensity_5B,
              - s2_latent_field_5B (optional).
    - dataset_dictionary.layer2.5B.yaml
        · IDs & contracts for:
              - s1_time_grid_5B
              - s1_grouping_5B
              - s2_realised_intensity_5B
              - s2_latent_field_5B (optional)
    - dataset_dictionary.layer2.5A.yaml
        · IDs for 5A scenario intensity surfaces (λ_target on the S1 grid).
    - artefact_registry_{5A,5B}.yaml
        · logical IDs, roles, schema_refs for configs & datasets.

[S1 outputs · time grid & grouping]
    - s1_time_grid_5B
      @ data/layer2/5B/s1_time_grid/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_time_grid_5B.parquet
      · producer: 5B.S1
      · partition_keys: [fingerprint, scenario_id]
      · PK: [manifest_fingerprint, scenario_id, bucket_index]
      · role in S2:
            - defines the ordered bucket set per scenario: BUCKETS(S) = {k},
            - provides bucket_start_utc, bucket_end_utc and any tags S2 needs (e.g. bucket_duration).

    - s1_grouping_5B
      @ data/layer2/5B/s1_grouping/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_grouping_5B.parquet
      · producer: 5B.S1
      · partition_keys: [fingerprint, scenario_id]
      · PK: [manifest_fingerprint, scenario_id, merchant_id, zone_representation, channel_group]
      · role in S2:
            - defines entities E(S) = {(m, zone_representation, channel_group)} per scenario,
            - provides group_id for each entity; S2 MUST use these group_ids and MUST NOT re-group.

[5A scenario intensity surfaces · λ_target]
    - 5A scenario λ surfaces on S1’s grid (ROW_LEVEL read_scope)
      · one or more datasets (as per 5A/5B contracts) that expose:
            λ_target(m, zone_representation[, channel_group], scenario_id, bucket_index)
        on the same `{scenario_id, bucket_index}` grid as s1_time_grid_5B.
      · S2’s role:
            - λ_target is the deterministic intensity from 5A; S2 MUST treat it as the only “target λ” input.

[5B configs & RNG policy]
    - arrival_lgcp_config_5B   (name illustrative; spec: “arrival-process / LGCP config”)
        · defines:
            - latent field type (e.g. log-Gaussian Cox, OU-on-log-λ, “no latent field”),
            - kernel / covariance structure (variance, length-scale, correlation shape),
            - how groups map to kernel hyper-parameters (per-group overrides),
            - clipping/guardrails for λ_realised (min/max factors).
        · S2 MUST treat this as the only authority on latent-field law.

    - rng_policy_5B
        · defines:
            - event families for S2 (e.g. "s2_latent_field_draw"),
            - stream IDs / substream labels for each (scenario_id, group_id),
            - expected draws/blocks per event,
            - RNG accounting rules (how to update rng_trace_log / rng_audit_log).
        · S2 MUST use only these streams for latent draws and log events accordingly.

    - (optional) s2_validation_config_5B
        · small config providing additional numeric guardrails:
            - allowed ranges for latent values or λ_realised,
            - thresholds for sanity checks (e.g. variance bounds).

[Outputs owned by S2]
    - s2_realised_intensity_5B   (required)
      @ data/layer2/5B/s2_realised_intensity/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
      · partition_keys: [seed, fingerprint, scenario_id]
      · primary_key:    [seed, manifest_fingerprint, parameter_hash,
                         scenario_id, merchant_id, zone_representation, channel_group, bucket_index]
      · ordering:       [scenario_id, merchant_id, zone_representation, channel_group, bucket_index]
      · schema_ref:     schemas.5B.yaml#/model/s2_realised_intensity_5B
      · one row per entity×bucket with, at minimum:
            seed,
            manifest_fingerprint,
            parameter_hash,
            scenario_id,
            merchant_id,
            zone_representation,
            channel_group,
            bucket_index,
            lambda_target       (echo of 5A λ),
            lambda_realised     (post-latent, post-clipping),
            latent_source_id/version,
            rng_stream_id,
            rng_event_id (link to latent draw event),
            optional diagnostic metrics (e.g. latent_value, scaling factors).

    - s2_latent_field_5B         (optional diagnostic)
      @ data/layer2/5B/s2_latent_field/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
      · partition_keys: [seed, fingerprint, scenario_id]
      · primary_key:    [seed, manifest_fingerprint, parameter_hash,
                         scenario_id, group_id, bucket_index]
      · ordering:       [scenario_id, group_id, bucket_index]
      · schema_ref:     schemas.5B.yaml#/model/s2_latent_field_5B
      · one row per group×bucket with latent field values and any kernel-level metadata.

    - RNG events & trace logs (layer-wide, not 5B datasets)
      · rng_event entries for latent draws,
      · rng_trace_log / rng_audit_log updated with S2 usage.


[Numeric & RNG posture]
    - S2 is **RNG-bearing**:
        · MUST use Philox streams as defined in rng_policy_5B,
        · MUST log every latent draw event with correct {blocks, draws, counters},
        · MUST update rng_trace_log / rng_audit_log in accordance with the Layer-wide RNG law.
    - Determinism:
        · Given (seed, parameter_hash, manifest_fingerprint, scenario_id) and fixed configs & inputs,
          S2 MUST produce byte-identical s2_realised_intensity_5B and s2_latent_field_5B (if enabled).
    - Scope:
        · World identity: (manifest_fingerprint) and parameter_hash shared with 5A.
        · Stochastic identity: seed and run_id; path partitioning is [seed, fingerprint, scenario_id].


----------------------------------------------------------------------
DAG — 5B.S2 (5A λ_target + S1 grid/grouping → latent fields & λ_realised)  [RNG-BEARING]

### Phase A — Gate & resolve inputs (no RNG)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S2.1) Load S0 receipt & sealed_inputs; fix identity
                    - Resolve via 5B dictionary:
                        · s0_gate_receipt_5B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_5B@fingerprint={manifest_fingerprint}.
                    - Validate both against schemas.5B.yaml.
                    - From s0_gate_receipt_5B:
                        · fix (seed, parameter_hash, manifest_fingerprint, run_id),
                        · fix scenario_set_5B (scenarios S2 must process),
                        · read verified_upstream_segments.{1A,1B,2A,2B,3A,3B,5A},
                        · read sealed_inputs_digest.
                    - Recompute digest from sealed_inputs_5B (canonical row order + serialisation);
                      require equality with sealed_inputs_digest.
                    - If any upstream segment required by S2 is not PASS ⇒ S2 MUST fail.

sealed_inputs_5B,
[Schema+Dict]
                ->  (S2.2) Resolve S1 outputs, 5A λ_target surfaces & S2 configs
                    - Using sealed_inputs_5B + dictionaries/registries, resolve:
                        · s1_time_grid_5B@fingerprint={manifest_fingerprint},scenario_id={S}  for all S ∈ scenario_set_5B,
                        · s1_grouping_5B@fingerprint={manifest_fingerprint},scenario_id={S}  for all S ∈ scenario_set_5B,
                        · 5A scenario intensity surface(s) providing λ_target on the S1 grid,
                        · arrival_lgcp_config_5B,
                        · rng_policy_5B,
                        · (optional) s2_validation_config_5B.
                    - For each resolved artefact:
                        · locate it in sealed_inputs_5B,
                        · recompute SHA-256(raw bytes),
                        · assert equality with stored sha256_hex.
                    - Validate:
                        · s1_time_grid_5B against `#/model/s1_time_grid_5B`,
                        · s1_grouping_5B against `#/model/s1_grouping_5B`,
                        · 5A λ_target surfaces against their schema_refs,
                        · configs/policies against their schema anchors.

s1_time_grid_5B,
s1_grouping_5B
                ->  (S2.3) Check S1 identity & domain per scenario
                    - For each scenario_id S ∈ scenario_set_5B:
                        · time grid:
                              - extract BUCKETS(S) = {bucket_index k},
                              - require:
                                    manifest_fingerprint == mf,
                                    parameter_hash      == ph (if embedded),
                                    k’s form a finite, ordered set (e.g. 0..K_S−1),
                                    each bucket has well-formed [start_utc,end_utc).
                        · grouping:
                              - extract entity set E(S) = {(merchant_id, zone_representation, channel_group)},
                              - require:
                                    manifest_fingerprint == mf,
                                    scenario_id == S,
                                    no duplicate keys.
                    - If any S lacks either S1 dataset or has invalid shape ⇒ `S2_PRECONDITION_FAILED`: S2 MUST NOT run.

### Phase B — Build λ_target domain on S1 grid (no RNG)

5A λ_target surfaces,
s1_time_grid_5B,
s1_grouping_5B
                ->  (S2.4) Join λ_target onto (scenario, entity, bucket) domain
                    - For each scenario_id S:
                        · For each entity e = (m, zone_representation, channel_group) ∈ E(S),
                          and for each bucket k ∈ BUCKETS(S):
                              - S2 attempts to read λ_target(m, zone_representation, channel_group, S, k)
                                from 5A scenario surfaces.
                    - Domain:
                        · D_λ(S) = set of (e,k) pairs for which λ_target exists.
                    - Requirements:
                        · S2 MUST NOT invent λ_target values; missing λ_target entries must be handled according to config:
                              - either treat as λ_target=0 (for explicitly sparse modelling), or
                              - treat as a configuration error if they should exist.
                    - Construct in-memory table TARGET(S) keyed by:
                        · (merchant_id, zone_representation, channel_group, bucket_index), with λ_target ≥ 0.

arrival_lgcp_config_5B,
rng_policy_5B
                ->  (S2.5) Prepare LGCP laws & RNG layout (no RNG yet)
                    - Parse arrival_lgcp_config_5B:
                        · decide latent model:
                              - log-Gaussian Cox → latent Z ~ N(0,K), λ_realised = λ_target * exp(Z),
                              - OU-on-log-λ, or “no latent field” where Z≡0,
                        · decide kernel structure:
                              - kernel hyper-parameters per (scenario_id, group_id),
                              - correlation structure over bucket indices (e.g. Matérn, OU, AR(1) in time).
                    - Parse rng_policy_5B:
                        · identify event family for S2 latent draws, e.g.:
                              - event_family = "5B.S2.latent_field",
                              - map (scenario_id, group_id) → stream_id / substream_label,
                              - expected draws/blocks per latent event.
                    - S2 MUST record this configuration as the only source of stochastic law & RNG layout.

### Phase C — Latent-field construction per (scenario, group) (RNG-bearing)

TARGET(S),
s1_grouping_5B,
s1_time_grid_5B,
arrival_lgcp_config_5B,
rng_policy_5B
                ->  (S2.6) For each scenario S, define group-level latent domains
                    - For each scenario_id S:
                        · For each group_id g appearing in s1_grouping_5B(S):
                              - define latent domain:
                                    BUCKETS_g(S) = { bucket_index k ∈ BUCKETS(S) where
                                                     there exists at least one entity e in group g with λ_target(e,k) }.
                        - If BUCKETS_g(S) is empty for some g:
                              - handle according to config:
                                    either treat as “no latent for empty group” or configuration error.

                ->  (S2.7) Sample latent fields per group (RNG-bearing)
                    - For each scenario_id S and group_id g:
                        1. Construct covariance kernel K_g over BUCKETS_g(S) as defined in arrival_lgcp_config_5B:
                               - compute K_g[i,j] = k(t_i, t_j; θ_g) based on bucket midpoints and hyper-params θ_g.
                        2. Use rng_policy_5B to derive:
                               - Philox key / base counter for (S,g),
                               - event envelope for this latent sample (blocks/draws).
                        3. Sample latent vector Z_g (length |BUCKETS_g(S)|) according to cfg:
                               - e.g. via Cholesky / eigen decomposition with Philox uniforms → standard normals → correlated normals.
                        4. Emit one RNG event for the latent draw, logging:
                               - stream_id/substream_label,
                               - counter_before/after,
                               - blocks, draws,
                               - scenario_id, group_id.
                        5. Store latent values Z_g(k) per bucket k in BUCKETS_g(S).
                    - All RNG usage MUST be via the configured streams; any extra draws are a contract violation.

### Phase D — Map latent fields to entities & compute λ_realised (RNG-free)

TARGET(S),
s1_grouping_5B,
{Z_g(k)},
arrival_lgcp_config_5B,
(optional) s2_validation_config_5B
                ->  (S2.8) Map latent factors to each entity×bucket & transform λ
                    - For each scenario_id S:
                        · For each entity e = (m, zone_representation, channel_group) in E(S),
                          with group_id g = group_id(e):
                              - For each bucket k in BUCKETS(S) (or BUCKETS_g(S) if sparse):
                                    - read λ_target(e,k) from TARGET(S) (0 or >0, per config),
                                    - read latent value Z_g(k) if latent model applies, else Z_g(k)≡0.
                                    - compute ξ(e,k) = latent_factor(Z_g(k)) according to model:
                                          · e.g. log-Gaussian Cox:
                                                ξ(e,k) = exp(Z_g(k) − 0.5*Var(Z_g(k))) or similar,
                                                λ_proposed(e,k) = λ_target(e,k) * ξ(e,k).
                                    - apply clipping / guardrails from arrival_lgcp_config_5B:
                                          · enforce min/max factor on ξ or λ_proposed,
                                          · enforce non-negativity and finite values.
                                    - if s2_validation_config_5B specifies range checks:
                                          · assert λ_realised(e,k) within configured bounds.
                                    - set λ_realised(e,k) = clipped λ_proposed(e,k).
                    - S2 MUST NOT:
                        · change λ_target itself,
                        · introduce negative or NaN/Inf λ_realised values.

λ_target(e,k),
λ_realised(e,k),
latent metadata (g, Z_g(k), RNG event id)
                ->  (S2.9) Assemble s2_realised_intensity_5B rows
                    - For each scenario_id S, each entity e ∈ E(S), each bucket k ∈ BUCKETS(S):
                        · assemble row:
                              seed                = seed,
                              manifest_fingerprint= manifest_fingerprint,
                              parameter_hash      = parameter_hash,
                              scenario_id         = S,
                              merchant_id         = e.merchant_id,
                              zone_representation = e.zone_representation,
                              channel_group       = e.channel_group,
                              bucket_index        = k,
                              lambda_target       = λ_target(e,k),
                              lambda_realised     = λ_realised(e,k),
                              latent_source_id    = arrival_lgcp_config_5B.id,
                              latent_source_version = arrival_lgcp_config_5B.version,
                              rng_stream_id       = stream for (S,g) per rng_policy_5B,
                              rng_event_id        = identifier linking to the latent draw event,
                              latent_group_id     = g (optional),
                              latent_value        = Z_g(k) (optional, if schema allows).
                    - Sort rows by [scenario_id, merchant_id, zone_representation, channel_group, bucket_index].
                    - Validate against schemas.5B.yaml#/model/s2_realised_intensity_5B.

{Z_g(k)} per (scenario,group,bucket),
latent metadata
                ->  (S2.10) Optionally assemble s2_latent_field_5B rows
                    - If latent-field diagnostics are enabled and dataset registered:
                        · For each scenario_id S, group_id g, and bucket k in BUCKETS_g(S):
                              - assemble row:
                                    seed,
                                    manifest_fingerprint,
                                    parameter_hash,
                                    scenario_id = S,
                                    group_id    = g,
                                    bucket_index= k,
                                    latent_value= Z_g(k),
                                    kernel_id/version,
                                    latent_source_id/version.
                        - Sort rows by [scenario_id, group_id, bucket_index].
                        - Validate against schemas.5B.yaml#/model/s2_latent_field_5B.
                    - If disabled, S2 MUST NOT emit s2_latent_field_5B.

s2_realised_intensity_5B rows,
s2_latent_field_5B rows (optional),
[Schema+Dict]
                ->  (S2.11) Persist S2 outputs (write-once per seed/fingerprint/scenario)
                    - For each scenario_id S ∈ scenario_set_5B:

                      1. s2_realised_intensity_5B:
                          - target path:
                                data/layer2/5B/s2_realised_intensity/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={S}/…
                          - if dataset does not exist:
                                · write via staging → fsync → atomic move.
                          - if dataset exists:
                                · load existing dataset, normalise schema+sort,
                                · if byte-identical → idempotent re-run; OK,
                                · else → write conflict; MUST NOT overwrite.

                      2. s2_latent_field_5B (if enabled):
                          - target path:
                                data/layer2/5B/s2_latent_field/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={S}/…
                          - same immutability rules as above.

                    - S2 MUST NOT write any other 5B datasets.

Downstream touchpoints
----------------------
- **5B.S3 — Bucket-level arrival counts:**
    - MUST treat s2_realised_intensity_5B as the only source of λ_realised(e,k) per entity×bucket.
    - MUST NOT re-sample latent fields or reapply LGCP; it only converts λ_realised × bucket_duration → integer counts.

- **5B.S4 — Arrival events (micro-time & routing):**
    - Uses s2_realised_intensity_5B only indirectly via S3 counts (it does not read λ_realised directly in most designs).

- **5B.S5 — Validation bundle & `_passed.flag_5B`:**
    - Replays S2 invariants:
          - S2 domain = S1 domain×BUCKETS(S),
          - latent fields exist and were sampled via configured RNG policy,
          - λ_realised non-negative, finite, within clipping bounds and consistent with λ_target semantics.
    - includes s2_realised_intensity_5B (and s2_latent_field_5B if present) as part of validation evidence.

```