```
        LAYER 2 · SEGMENT 5B — STATE S3 (BUCKET-LEVEL ARRIVAL COUNTS)  [RNG-BEARING]

Authoritative inputs (read-only at S3 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5B
      @ data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
      · provides:
          - manifest_fingerprint, parameter_hash, seed, run_id,
          - scenario_set_5B (scenario_id values S3 must process),
          - verified_upstream_segments.{1A,1B,2A,2B,3A,3B,5A},
          - sealed_inputs_digest.
      · S3 MUST:
          - trust upstream PASS/FAIL from this receipt (MUST NOT re-hash upstream bundles itself),
          - recompute sealed_inputs_digest from sealed_inputs_5B and assert equality.

    - sealed_inputs_5B
      @ data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
      · describes the entire artefact universe available to 5B:
          - one row per artefact with {owner_layer, owner_segment, artifact_id, manifest_key,
             path_template, partition_keys[], schema_ref, sha256_hex, role, status, read_scope, source_dictionary,…}.
      · S3 MUST:
          - only read artefacts listed here,
          - honour `status` (REQUIRED/OPTIONAL/INTERNAL/IGNORED),
          - honour `read_scope`:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → may only inspect metadata.

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.layer2.yaml, schemas.5B.yaml
        · define schemas for:
              - s1_time_grid_5B, s1_grouping_5B,
              - s2_realised_intensity_5B,
              - s3_bucket_counts_5B.
    - dataset_dictionary.layer2.5B.yaml
        · IDs & contracts for:
              - s1_time_grid_5B
              - s1_grouping_5B
              - s2_realised_intensity_5B
              - s3_bucket_counts_5B
                · path:
                    data/layer2/5B/s3_bucket_counts/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s3_bucket_counts_5B.parquet
                · partition_keys: [seed, fingerprint, scenario_id]
                · primary_key:
                      [seed, manifest_fingerprint, scenario_id, merchant_id, zone_representation, channel_group, bucket_index]
                · ordering:
                      [scenario_id, merchant_id, zone_representation, channel_group, bucket_index]
                · schema_ref: schemas.5B.yaml#/model/s3_bucket_counts_5B.
    - dataset_dictionary.layer2.5A.yaml
        · may be used only for metadata, not for λ-target re-derivation.
    - artefact_registry_{5A,5B}.yaml
        · roles & dependencies for arrival configs, RNG policies, S2 output, etc.

[S1 domain & time grid (required)]
    - s1_time_grid_5B  (per scenario)
      @ data/layer2/5B/s1_time_grid/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_time_grid_5B.parquet
      · producer: 5B.S1.
      · partition_keys: [fingerprint, scenario_id]
      · PK: [manifest_fingerprint, scenario_id, bucket_index]
      · S3’s use:
            - defines bucket set H_s = {bucket_index b} for scenario s,
            - provides bucket_start_utc, bucket_end_utc,
            - either stores or implies bucket_duration_seconds(b).

    - s1_grouping_5B  (per scenario)
      @ data/layer2/5B/s1_grouping/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_grouping_5B.parquet
      · producer: 5B.S1.
      · partition_keys: [fingerprint, scenario_id]
      · PK: [manifest_fingerprint, scenario_id, merchant_id, zone_representation, channel_group]
      · S3’s use:
            - defines entity set E_s = {(merchant_id, zone_representation[, channel_group])} for scenario s.

[S2 realised intensities (required)]
    - s2_realised_intensity_5B
      @ data/layer2/5B/s2_realised_intensity/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s2_realised_intensity_5B.parquet
      · producer: 5B.S2.
      · partition_keys: [seed, fingerprint, scenario_id]
      · PK: [seed, manifest_fingerprint, scenario_id, merchant_id, zone_representation, channel_group, bucket_index]
      · S3’s use:
            - provides λ_realised(e,b) per entity×bucket×scenario×seed,
            - may also carry λ_target and latent diagnostics, but S3 MUST treat S2 as the **only** λ_realised authority.

[Counting law & RNG configs]
    - arrival_count_config_5B
        · config object that defines:
            - which arrival law to use (e.g. Poisson, NB, mixed),
            - how to compute law parameters θ from (λ_realised, bucket_duration_seconds, group_id, key traits),
            - any parameter constraints and clipping behaviour,
            - required behaviour when λ_realised=0 or very small.
        · S3 MUST treat this as the **only** source of count-law semantics.

    - arrival_rng_policy_5B
        · RNG policy specific to S3 (or shared arrival RNG policy) defining:
            - event family for counts (e.g. "5B.S3.bucket_count"),
            - mapping from (scenario_id, key, bucket_index) → stream_id / substream_label / counters,
            - expected `draws` and `blocks` per count event,
            - RNG accounting rules for rng_trace_log / rng_audit_log.
        · S3 MUST use only these streams/substreams for count draws; any other RNG consumption is forbidden.

    - (optional) s3_count_guardrail_config_5B
        · optional guardrail config with additional local numeric checks:
            - max/min counts per bucket,
            - rules for “force zero” or “force upper bound” in edge cases.

[Outputs owned by S3]
    - s3_bucket_counts_5B  (required)
      @ data/layer2/5B/s3_bucket_counts/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s3_bucket_counts_5B.parquet
      · partition_keys: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, merchant_id, zone_representation, channel_group, bucket_index]
      · ordering:
            [scenario_id, merchant_id, zone_representation, channel_group, bucket_index]
      · schema_ref: schemas.5B.yaml#/model/s3_bucket_counts_5B
      · one row per domain element with at minimum:
            manifest_fingerprint,
            parameter_hash,
            seed,
            scenario_id,
            merchant_id,
            zone_representation,
            (optional) channel_group,
            bucket_index,
            count_N ≥ 0,
            optional: s3_spec_version, λ_realised, law parameters, flags.

    - RNG logs (not 5B datasets but Layer-wide logs)
      · rng_event entries for count draws,
      · rng_trace_log / rng_audit_log aggregates for the “arrival_counts” family.


[Numeric & RNG posture]
    - S3 is **RNG-bearing**:
        · MUST use Philox streams as defined in arrival_rng_policy_5B,
        · MUST emit one or more RNG events per domain element according to policy,
        · MUST update rng_trace_log / rng_audit_log consistently.
    - Determinism:
        · For fixed (parameter_hash, manifest_fingerprint, seed, scenario_set_5B) and fixed inputs/configs,
          S3 MUST produce the same counts and RNG logs on re-run (independent of run_id).
    - Scope:
        · 5B.S3 only maps λ_realised → integer counts;
        · it MUST NOT produce timestamps or routing decisions.


----------------------------------------------------------------------
DAG — 5B.S3 (λ_realised → bucket-level counts N)  [RNG-BEARING]

### Phase 1 — Gate & load inputs (no RNG)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S3.1) Load S0 artefacts & check identity
                    - Resolve:
                        · s0_gate_receipt_5B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_5B@fingerprint={manifest_fingerprint},
                      via 5B dictionary.
                    - Validate both against schemas.5B.yaml.
                    - From s0_gate_receipt_5B:
                        · fix (parameter_hash, manifest_fingerprint, seed, run_id),
                        · read `scenario_set_5B`,
                        · read `verified_upstream_segments` map,
                        · read `sealed_inputs_digest`.
                    - Recompute digest from sealed_inputs_5B (canonical row-order + serialisation);
                      require equality with `sealed_inputs_digest`.
                    - If any upstream segment required by 5B (1A–3B, 5A, 3B/2B as configured) is not PASS:
                        · S3 MUST fail; counts MUST NOT be computed on a non-PASS world.

sealed_inputs_5B,
[Schema+Dict]
                ->  (S3.2) Resolve S1/S2 data & S3 configs
                    - Using sealed_inputs_5B + dictionary/registry, resolve:
                        · s1_time_grid_5B@fingerprint={manifest_fingerprint},scenario_id={S},
                        · s1_grouping_5B@fingerprint={manifest_fingerprint},scenario_id={S},
                        · s2_realised_intensity_5B@seed={seed},fingerprint={manifest_fingerprint},scenario_id={S},
                      for all `scenario_id = S ∈ scenario_set_5B`.
                    - Resolve configs:
                        · arrival_count_config_5B,
                        · arrival_rng_policy_5B,
                        · (optional) s3_count_guardrail_config_5B.
                    - For each resolved artefact:
                        · locate its sealed_inputs_5B row,
                        · recompute SHA-256(raw bytes),
                        · assert equality with sealed_inputs_5B.sha256_hex.
                    - Validate datasets:
                        · s1_time_grid_5B against `#/model/s1_time_grid_5B`,
                        · s1_grouping_5B against `#/model/s1_grouping_5B`,
                        · s2_realised_intensity_5B against `#/model/s2_realised_intensity_5B`.
                    - Validate configs against their schema_refs.

### Phase 2 — Assemble count domain D_s and λ_realised(e,b) (no RNG)

s1_time_grid_5B,
s1_grouping_5B,
s2_realised_intensity_5B
                ->  (S3.3) Build domain D_s per scenario & join λ_realised
                    - For each scenario_id s ∈ scenario_set_5B:
                        1. From s1_time_grid_5B:
                               H_s := ordered set of bucket_index b for scenario s.
                               For each b, obtain bucket_duration_seconds(b) from:
                                   - explicit field, or
                                   - difference `bucket_end_utc − bucket_start_utc`.
                        2. From s1_grouping_5B:
                               E_s := set of `key = (merchant_id, zone_representation[, channel_group])`.
                        3. From s2_realised_intensity_5B@seed, mf, s:
                               join on `(merchant_id, zone_representation[, channel_group], bucket_index)` with E_s×H_s.
                               Define:
                                   D_s := {
                                      (key, b) | row exists in s2_realised_intensity_5B for (seed, mf, s)
                                   }.
                               For each (key,b) ∈ D_s, retain:
                                   - `lambda_realised(key,b)` (and λ_target if present),
                                   - any latent diagnostics (optional).
                    - Requirements:
                        · (key,b) pairs in s2_realised_intensity_5B MUST lie within E_s×H_s;
                        · if arrival_count_config_5B requires a dense domain (all E_s×H_s), then D_s MUST equal E_s×H_s.
                    - Any domain mismatch or missing required λ_realised ⇒ `5B.S3.DOMAIN_MISMATCH` → S3 MUST abort.

### Phase 3 — Compute arrival-law parameters per (s, key, b) (no RNG)

arrival_count_config_5B,
s1_time_grid_5B,
s1_grouping_5B,
D_s with λ_realised
                ->  (S3.4) Derive per-bucket distribution parameters θ(s,key,b)
                    - For each scenario_id s and each (key,b) ∈ D_s:
                        · Let key = (merchant_id m, zone_representation z[, channel_group ch]).
                        · Retrieve:
                              λ = lambda_realised(key,b),
                              Δ_b = bucket_duration_seconds(b),
                              group_id = group_id(key) from s1_grouping_5B (if count config uses groups),
                              optional key traits from grouping metadata (if policy permits).
                        - Using arrival_count_config_5B, compute:
                              μ_base = f_mu(λ, Δ_b, config, [group_id, key traits])
                          and then:
                              θ(s,key,b) = f_params(μ_base, config, [group_id, key traits])
                          where θ captures law parameters, e.g.:
                              - Poisson: λ_count,
                              - NB: (r, p) or (μ, k).
                    - Parameter guardrails:
                        · all parameters MUST be finite and in allowed ranges (e.g. λ_count ≥ 0, NB r>0, p∈(0,1)).
                        · if λ_realised = 0 and config demands N=0 with probability 1:
                              - θ MUST encode that (e.g. λ_count=0) and S3 MUST later produce N=0 deterministically.
                    - If any θ is invalid or non-computable:
                        · S3 MUST treat this as a configuration error (e.g. `5B.S3.PARAM_INVALID`) and abort.

### Phase 4 — RNG: Sample counts N with Philox (RNG-bearing)

arrival_rng_policy_5B,
θ(s,key,b),
D_s
                ->  (S3.5) Sample counts N(s,key,b) via count law
                    - From arrival_rng_policy_5B, obtain:
                        · stream_id for count draws (e.g. "arrival_counts"),
                        · substream_label for bucket-count events (e.g. "bucket_count"),
                        · deterministic mapping from (scenario_id s, key, bucket_index b) → RNG stream/substream/counter.
                    - Establish a canonical iteration order:
                        · sort D_s entries by:
                              (scenario_id s, merchant_id, zone_representation, channel_group, bucket_index).
                    - For each (s,key,b) in that canonical order:
                        1. Retrieve θ(s,key,b) from S3.4.
                        2. Use Philox under the configured stream/substream:
                               - generate the required U(0,1) uniforms for the arrival law:
                                     * Poisson: via inversion or PTRS, using a known uniform draw pattern,
                                     * NB: via gamma–Poisson mixture or direct NB algorithm, with known draw pattern.
                        3. Compute integer count:
                               N = sample_count(θ(s,key,b), uniforms, arrival_count_config_5B).
                        4. Emit RNG event(s) for this draw:
                               - event record(s) capturing:
                                     * stream_id, substream_label,
                                     * counter_before, counter_after,
                                     * blocks, draws,
                                     * seed, scenario_id, key, bucket_index,
                               - update rng_trace_log / rng_audit_log as per Layer-wide RNG rules.
                        5. Numeric constraints:
                               - N MUST be integer ≥ 0,
                               - if λ_realised = 0 and config demands N=0, S3 MUST enforce N=0.
                    - Requirements:
                        · total number of RNG events / draws MUST match policy expectations,
                        · counters per stream MUST be monotonically increasing, without overlaps where disallowed.
                    - Any RNG accounting violation ⇒ S3 MUST abort with a `5B.S3.RNG_*` error.

### Phase 5 — Build and persist s3_bucket_counts_5B

D_s,
N(s,key,b),
λ_realised(s,key,b),
s1_time_grid_5B,
schemas.5B.yaml
                ->  (S3.6) Assemble s3_bucket_counts_5B rows
                    - For each scenario_id s and each (key,b) ∈ D_s:
                        · decompose key = (merchant_id, zone_representation[, channel_group]).
                        · construct row:
                              manifest_fingerprint = mf,
                              parameter_hash       = ph,
                              seed                 = seed,
                              scenario_id          = s,
                              merchant_id          = m,
                              zone_representation  = zone_representation,
                              channel_group        = channel_group (if present),
                              bucket_index         = b,
                              count_N              = N(s,key,b),
                              s3_spec_version      = current S3 contract version string (optional).
                        - S3 MAY include additional non-key, non-required fields (if schema allows), e.g.:
                              lambda_realised, bucket_duration_seconds, law parameters,
                              but MUST honour schemas.5B.yaml#/model/s3_bucket_counts_5B (additionalProperties=true).
                    - Collect rows across all scenarios in scenario_set_5B.
                    - Sort rows by:
                          [scenario_id, merchant_id, zone_representation, channel_group, bucket_index].
                    - Validate in-memory table against schema:
                          - required fields present,
                          - count_N integer ≥ 0,
                          - PK uniqueness.

s3_bucket_counts_5B rows,
dataset_dictionary.layer2.5B.yaml
                ->  (S3.7) Write s3_bucket_counts_5B (write-once per seed/fingerprint/scenario)
                    - For each scenario_id s ∈ scenario_set_5B:
                        · target path:
                              data/layer2/5B/s3_bucket_counts/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={s}/s3_bucket_counts_5B.parquet
                        · If dataset does not exist:
                              - write rows belonging to scenario_id=s (after filtering) via staging → fsync → atomic move.
                        · If dataset exists:
                              - load existing dataset, normalise schema + sort,
                              - compare to would-be rows:
                                    * if byte-identical → idempotent re-run; OK,
                                    * else → immutability violation; MUST NOT overwrite.
                    - For each (ph, mf, seed, scenario_id):
                        · there MUST be at most one s3_bucket_counts_5B file at the canonical path,
                        · file MUST cover the entire domain D_s (no missing (key,b) with λ_realised from S2).
                    - S3 MUST NOT write any other 5B datasets.

Downstream touchpoints
----------------------
- **5B.S4 — Arrival events (micro-time & routing):**
    - MUST treat s3_bucket_counts_5B as the sole source of bucket counts N per (merchant, zone_representation[,channel_group], bucket_index, scenario_id, seed).
    - MUST NOT resample counts from λ_realised; it only:
          - spreads these N arrivals within each bucket in time,
          - routes each arrival to a site/edge using 2B/3B routing.

- **5B.S5 — Segment validation & HashGate:**
    - Replays S3 invariants:
          - domain D_s correctness vs s1_time_grid_5B × s1_grouping_5B × s2_realised_intensity_5B,
          - count-law parameter constraints,
          - RNG accounting (events & draws), counter monotonicity,
          - count_N ≥ 0 and integer, any configured hard constraints (e.g. forced zeros).
    - Bundles s3_bucket_counts_5B and RNG evidence as part of the 5B validation bundle for this manifest_fingerprint.

- **Layer-3 & external tooling:**
    - Must gate any use of s3_bucket_counts_5B on the 5B HashGate (`_passed.flag`):
          **No 5B PASS → No read/use of bucket counts or arrival events.**
```