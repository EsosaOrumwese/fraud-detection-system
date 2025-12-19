```
        LAYER 2 · SEGMENT 5A — STATE S3 (BASELINE MERCHANT×ZONE WEEKLY INTENSITIES)  [NO RNG]

Authoritative inputs (read-only at S3 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5A
      @ layer2/5A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5A.json
      · provides:
          - manifest_fingerprint, parameter_hash, run_id,
          - scenario_id (or scenario_ids) in scope,
          - verified_upstream_segments.{1A,1B,2A,2B,3A,3B},
          - sealed_inputs_digest.
      · S3 MUST:
          - trust upstream PASS/FAIL/MISSING as given,
          - recompute sealed_inputs_digest from sealed_inputs_5A and assert equality.

    - sealed_inputs_5A
      @ layer2/5A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5A.parquet
      · describes the complete artefact universe for 5A:
          - one row per artefact with {owner_layer, owner_segment, artifact_id, manifest_key,
             path_template, partition_keys[], schema_ref, sha256_hex, role, status, read_scope}.
      · S3 MUST:
          - only read artefacts listed here,
          - honour status (REQUIRED/OPTIONAL/IGNORED),
          - honour read_scope (ROW_LEVEL vs METADATA_ONLY).

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.layer2.yaml, schemas.5A.yaml
    - dataset_dictionary.layer2.5A.yaml
        · IDs & contracts for:
            - merchant_zone_profile_5A             (S1),
            - shape_grid_definition_5A             (S2),
            - class_zone_shape_5A                  (S2),
            - merchant_zone_baseline_local_5A      (S3, required),
            - class_zone_baseline_local_5A         (S3, optional),
            - merchant_zone_baseline_utc_5A        (S3, optional).
    - artefact_registry_5A.yaml
        · registry entries linking IDs → schema_refs, partition_specs, roles.

[S1 merchant×zone demand profiles]
    - merchant_zone_profile_5A
      @ layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/merchant_zone_profile_5A.parquet
      · producer: 5A.S1.
      · partition_keys: [manifest_fingerprint]
      · primary_key:    [merchant_id, legal_country_iso, tzid]  (plus channel if used)
      · schema_ref:     schemas.5A.yaml#/model/merchant_zone_profile_5A
      · S3 uses, per row:
            merchant_id,
            legal_country_iso,
            tzid (or zone_id),
            demand_class,
            base scale fields (e.g. weekly_volume_expected, scale_factor),
            scale_unit,
            any scale flags (e.g. high_variability_flag),
            scenario_id (if present),
            manifest_fingerprint, parameter_hash.
      · Authority:
            - defines domain D_S3 = {(m,z[,ch])} in-scope for S3,
            - is sole source of demand_class and base scale per (m,z[,ch]).

[S2 shapes & time grid]
    - shape_grid_definition_5A
      · producer: 5A.S2.
      · key fields:
            parameter_hash,
            scenario_id,
            bucket_index,
            local_day_of_week,
            local_minutes_since_midnight,
            bucket_duration_minutes.
      · defines the local-week time grid (set GRID = {k}).

    - class_zone_shape_5A
      @ layer2/5A/class_zone_shape/{parameter_hash,scenario_id}/…
      · producer: 5A.S2.
      · primary_key (typical):
            [demand_class, legal_country_iso, tzid, bucket_index]
      · schema_ref: schemas.5A.yaml#/model/class_zone_shape_5A
      · S3 uses, per row:
            demand_class, legal_country_iso, tzid, bucket_index, shape_value,
            (optional) shape_sum_class_zone, parameter_hash, scenario_id.
      · Authority:
            - sole provider of unit-mass weekly shapes per (class,zone[,ch]),
            - S2 guarantees Σ_k shape_value ≈ 1 per (class,zone[,ch]).

[S3 baseline policies/configs]
    - baseline_intensity_policy_5A  (optional)
        · defines:
            - which base scale field to use from S1,
            - unit semantics:
                  · “weekly_expected_arrivals” → Σ_k λ_base_local(m,z,k) ≈ weekly_volume_expected(m,z),
                  · or “dimensionless_scale”   → alternative weekly constraint,
            - optional clipping rules:
                  · min/max λ per bucket,
                  · behaviour when base_scale=0 with non-zero shape,
                  · any per-class/per-zone overrides.
        · Authority:
            - S3 MUST use this policy to interpret S1’s base scale fields,
            - MUST NOT invent base-scale semantics on the fly.

[Outputs owned by S3]
    - merchant_zone_baseline_local_5A    (required)
      @ layer2/5A/merchant_zone_baseline_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
      · partition_keys: [manifest_fingerprint, scenario_id]
      · primary_key:
            [manifest_fingerprint, scenario_id, merchant_id, legal_country_iso, tzid, bucket_index]
      · schema_ref: schemas.5A.yaml#/model/merchant_zone_baseline_local_5A
      · fields (min):
            manifest_fingerprint,
            parameter_hash,
            scenario_id,
            merchant_id,
            legal_country_iso,
            tzid,
            bucket_index,
            lambda_local_base ≥ 0,
            base_scale_used,
            scale_unit,
            demand_class,
            class_source, scale_source,
            optional weekly_sum_local (Σ_k λ per (m,z)).

    - class_zone_baseline_local_5A      (optional)
      · aggregated baseline per (demand_class, zone, bucket_index).

    - merchant_zone_baseline_utc_5A     (optional)
      · UTC projection of the local baseline via 2A tz law; if produced, must be a deterministic projection.

[Numeric & RNG posture]
    - S3 is **RNG-free**:
        · MUST NOT use RNG, emit RNG events, or touch RNG logs.
    - Determinism:
        · For fixed (parameter_hash, manifest_fingerprint, scenario_id, run_id) and fixed S1/S2 outputs + policies,
          S3 MUST produce byte-identical outputs.
    - Numeric:
        · IEEE-754 binary64, round-to-nearest-even; no FMA/FTZ/DAZ.
        · Serial reductions only (for weekly sums).
        · Per-(m,z) weekly sum must respect the base-scale contract from baseline_intensity_policy_5A.


----------------------------------------------------------------------
DAG — 5A.S3 (S1 class/scale × S2 shapes → baseline λ_local(m,z,k))  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S3.1) Load S0 artefacts & fix identity
                    - Resolve:
                        · s0_gate_receipt_5A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_5A@fingerprint={manifest_fingerprint},
                      via 5A dictionary.
                    - Validate both against schemas.5A.yaml.
                    - From s0_gate_receipt_5A:
                        · fix parameter_hash, manifest_fingerprint, run_id, scenario_id,
                        · read verified_upstream_segments.
                    - Recompute sealed_inputs_digest from sealed_inputs_5A (canonical row order and serialisation);
                      require equality with receipt.sealed_inputs_digest.
                    - If any upstream segment required for S3 is not PASS:
                          (e.g. 3A for zone_alloc, 3B if virtual flags matter),
                      then S3 MUST fail; world is not valid.

sealed_inputs_5A,
[Schema+Dict]
                ->  (S3.2) Resolve S1/S2 outputs & S3 baseline policies
                    - Using sealed_inputs_5A + dictionary/registry, resolve:
                        · merchant_zone_profile_5A@fingerprint={manifest_fingerprint},
                        · shape_grid_definition_5A@{parameter_hash,scenario_id},
                        · class_zone_shape_5A@{parameter_hash,scenario_id},
                        · baseline_intensity_policy_5A (if defined).
                    - For each policy/config artefact:
                        · recompute SHA-256 over raw bytes,
                        · assert equality with sealed_inputs_5A.sha256_hex,
                        · validate against schemas.5A.yaml (policy anchors).
                    - Validate datasets:
                        · merchant_zone_profile_5A against `#/model/merchant_zone_profile_5A`,
                        · shape_grid_definition_5A against `#/model/shape_grid_definition_5A`,
                        · class_zone_shape_5A against `#/model/class_zone_shape_5A`.
                    - S3 MUST NOT resolve any artefact not recorded in sealed_inputs_5A.

merchant_zone_profile_5A
                ->  (S3.3) Construct S3 domain D_S3 from S1
                    - Project S1 rows for this (manifest_fingerprint, parameter_hash):
                        · read at least:
                              merchant_id,
                              zone key: (legal_country_iso, tzid) or zone_id,
                              demand_class,
                              base-scale fields (e.g. weekly_volume_expected, scale_factor),
                              optional channel / channel_group.
                    - Define:
                        · zone_representation z = (legal_country_iso, tzid) (or zone_id),
                        · D_S3 = { (m,z[,ch]) } = all unique combinations observed.
                    - Validate:
                        · no duplicate (m,z[,ch]) rows,
                        · D_S3 is non-empty unless configuration explicitly allows an empty domain.
                    - S3 MUST treat D_S3 as its **sole domain**:
                        · merchant_zone_baseline_local_5A MUST NOT contain any key outside D_S3.

merchant_zone_profile_5A,
baseline_intensity_policy_5A (if present)
                ->  (S3.4) Build CLASS_SCALE map: (m,z[,ch]) → {class, base_scale}
                    - For each (m,z[,ch]) ∈ D_S3:
                        1. Read `demand_class(m,z[,ch])` from S1 row.
                        2. Determine base_scale field(s) according to baseline_intensity_policy_5A, e.g.:
                               - if policy says base_scale = weekly_volume_expected:
                                     base_scale(m,z[,ch]) = weekly_volume_expected(m,z[,ch]),
                               - else if base_scale = scale_factor:
                                     base_scale(m,z[,ch]) = scale_factor(m,z[,ch]),
                                     (and the policy will define how to interpret this in weekly sums).
                        3. Apply any policy-defined deterministic transforms (e.g. caps, flooring, log transforms),
                           keeping result non-negative and finite.
                        4. Build record:
                               CLASS_SCALE[m,z[,ch]] = {
                                   demand_class,
                                   base_scale,
                                   scale_unit,
                                   class_source, scale_source,
                                   aux_flags (e.g. high_variability_flag)
                               }.
                    - Invariants:
                        · every (m,z[,ch]) ∈ D_S3 has:
                              - a non-null demand_class,
                              - a base_scale ≥ 0 and finite.
                        · S3 MUST NOT derive new base scales from raw counts or other upstream surfaces.

shape_grid_definition_5A,
class_zone_shape_5A
                ->  (S3.5) Shape grid & SHAPE map per (class, zone[,ch])
                    - From shape_grid_definition_5A for (parameter_hash,scenario_id):
                        · assemble set GRID = {bucket_index k},
                        · compute T_week = |GRID|,
                        · validate:
                              - GRID is contiguous [0..T_week−1],
                              - Σ_k bucket_duration_minutes(k) == 7*24*60.
                    - From class_zone_shape_5A for (parameter_hash,scenario_id):
                        · create SHAPE map keyed by (demand_class, zone_representation[,channel], bucket_index):
                              SHAPE[(class, z[,ch], k)] = shape_value(class,z[,ch],k).
                        · optionally cache:
                              shape_sum[class,z[,ch]] = Σ_k shape_value(class,z[,ch],k).
                    - Validate:
                        · each (class,z[,ch]) has at least one bucket (coverage),
                        · shape_value ≥ 0,
                        · optional re-check of Σ_k shape_value ≈ 1 per (class,z[,ch]) (within ε_shape).

D_S3, CLASS_SCALE, SHAPE
                ->  (S3.6) Validate shape coverage for all (m,z[,ch])
                    - For each (m,z[,ch]) ∈ D_S3:
                        · let class = CLASS_SCALE[m,z[,ch]].demand_class.
                        · Check that for all k ∈ GRID:
                              SHAPE[(class, z[,ch], k)] exists.
                        - If any (m,z[,ch]) lacks a shape for its class×zone (or channel):
                              - mark as `S3_SHAPE_JOIN_FAILED`,
                              - S3 MUST treat this as fatal and abort (no fallbacks here; S2 must be fixed).

CLASS_SCALE,
SHAPE,
GRID,
baseline_intensity_policy_5A (semantics)
                ->  (S3.7) Compute λ_base_local(m,z[,ch],k)
                    - For each (m,z[,ch]) ∈ D_S3:
                        1. Read:
                               class       = CLASS_SCALE[m,z[,ch]].demand_class,
                               base_scale  = CLASS_SCALE[m,z[,ch]].base_scale.
                        2. For each k ∈ GRID:
                               shape_val = SHAPE[(class, z[,ch], k)],
                               lambda_local_base(m,z[,ch],k) = base_scale * shape_val.
                        3. Numeric checks per cell:
                               - lambda_local_base ≥ 0,
                               - finite (no NaNs/Inf),
                               - optional min/max λ bound from baseline_intensity_policy_5A.
                        4. Weekly sum check (per (m,z[,ch])):
                               - sum_week = Σ_k lambda_local_base(m,z[,ch],k) (serial reduction).
                               - If base_scale is defined as “weekly expected arrivals”:
                                     require |sum_week − base_scale| ≤ ε_sum (policy tolerance).
                               - If base_scale is dimensionless:
                                     enforce the weekly constraint defined by policy
                                     (e.g. sum_week ≤ max_allowed or sum_week ≈ base_scale within some law).
                        - If any cell-level or weekly-sum check fails:
                               - S3 MUST treat it as `S3_INTENSITY_NUMERIC_INVALID` and abort without writes.

λ_base_local(m,z,k) for all (m,z,k),
CLASS_SCALE
                ->  (S3.8) Assemble merchant_zone_baseline_local_5A rows
                    - For each (m,z[,ch]) ∈ D_S3 and each k ∈ GRID:
                        · compute row:
                              manifest_fingerprint = manifest_fingerprint,
                              parameter_hash       = parameter_hash,
                              scenario_id          = scenario_id,
                              merchant_id          = m,
                              legal_country_iso    = z.country_iso,
                              tzid                 = z.tzid (or zone_id per schema),
                              bucket_index         = k,
                              lambda_local_base    = lambda_local_base(m,z[,ch],k),
                              base_scale_used      = CLASS_SCALE[m,z[,ch]].base_scale,
                              scale_unit           = CLASS_SCALE[m,z[,ch]].scale_unit,
                              demand_class         = CLASS_SCALE[m,z[,ch]].demand_class,
                              class_source         = CLASS_SCALE[m,z[,ch]].class_source,
                              scale_source         = CLASS_SCALE[m,z[,ch]].scale_source,
                              weekly_sum_local?    = optional Σ_k λ over (m,z[,ch]) (if schema permits).
                    - Domain:
                        · rows must cover exactly D_S3 × GRID,
                        · no extra keys outside D_S3 or GRID.
                    - Canonical ordering:
                        · sort rows by:
                              [manifest_fingerprint, scenario_id,
                               merchant_id, legal_country_iso, tzid, bucket_index].

merchant_zone_baseline_local_5A rows,
[Schema+Dict]
                ->  (S3.9) Validate & write merchant_zone_baseline_local_5A
                    - Target path via dictionary:
                        · e.g. layer2/5A/merchant_zone_baseline_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
                    - Validate rows against schemas.5A.yaml#/model/merchant_zone_baseline_local_5A:
                        · required columns, PK, partition_keys, value ranges.
                        · path↔embed equality:
                              manifest_fingerprint matches partition token,
                              scenario_id matches partition token,
                              parameter_hash embedded equals S3’s parameter_hash.
                    - Immutability:
                        · if partition does NOT exist:
                              - write rows to staging → fsync → atomic move to final path.
                        · if partition exists:
                              - read existing dataset, normalise schema + sort,
                              - if byte-identical → idempotent re-run; OK,
                              - else → conflict; MUST NOT overwrite.

merchant_zone_baseline_local_5A (optional aggregation),
[Schema+Dict]
                ->  (S3.10) Optionally build class_zone_baseline_local_5A
                    - If configured/registered:
                        · aggregate merchant_zone_baseline_local_5A per:
                              (demand_class, legal_country_iso, tzid, bucket_index),
                          computing:
                              λ_class_zone_local = Σ_m lambda_local_base(m,z,k)
                          or another schema-specified aggregate.
                        - Validate against schemas.5A.yaml#/model/class_zone_baseline_local_5A.
                        - Write to dictionary-specified path with same identity rules and immutability constraints.

merchant_zone_baseline_local_5A,
shape_grid_definition_5A,
site_timezones (optional),
tz law (from 2A civil-time surfaces)
                ->  (S3.11) Optionally build merchant_zone_baseline_utc_5A
                    - If the optional UTC projection is enabled:
                        · project λ_base_local(m,z,k) into UTC grid using 2A’s tz mapping and shape_grid_definition_5A:
                              - each local bucket (z,k) maps to some UTC interval(s),
                              - λ values are redistributed accordingly.
                        - Validate against schemas.5A.yaml#/model/merchant_zone_baseline_utc_5A.
                        - Write to dictionary-specified path with same identity & immutability rules.
                    - If disabled:
                        · S3 MUST NOT emit this dataset.

Downstream touchpoints
----------------------
- **5A.S4 — Scenario overlays:**
    - MUST treat merchant_zone_baseline_local_5A as the sole source of baseline local intensities.
    - MUST NOT re-derive λ as scale×shape; it only multiplies S3 λ by overlay factors over the horizon.

- **5A.S5 — Validation & HashGate:**
    - Replays S3 invariants:
          - domain alignment with S1/S2 (D_S3 matches S1 domain, shapes present for each class×zone),
          - per-cell λ non-negativity & boundedness,
          - per-(m,z) weekly sums respect base-scale semantics,
          - identity fields consistent with partitions.
    - Any change in base-scale semantics or shape combination MUST come via policy changes → new parameter_hash, then S1–S3 re-run.

- **Downstream consumers (5B, 6A, analytics):**
    - MUST use merchant_zone_baseline_local_5A as their baseline intensity surface,
      gated by the segment-level `_passed.flag_5A` built in S5:
          **No 5A PASS → No read/use of 5A baselines.**
```