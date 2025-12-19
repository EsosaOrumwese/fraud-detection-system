```
        LAYER 2 · SEGMENT 5A — STATE S2 (CLASS×ZONE WEEKLY SHAPE LIBRARY)  [NO RNG]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5A
      @ layer2/5A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5A.json
      · provides:
          - manifest_fingerprint, parameter_hash, run_id,
          - scenario_id / scenario_pack_id in scope,
          - verified_upstream_segments.{1A,1B,2A,2B,3A,3B},
          - sealed_inputs_digest.
      · S2 MUST:
          - trust upstream PASS/FAIL status as given,
          - recompute sealed_inputs_digest from sealed_inputs_5A and assert equality.

    - sealed_inputs_5A
      @ layer2/5A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5A.parquet
      · describes every artefact S2 is allowed to read:
          - {owner_layer, owner_segment, artifact_id, manifest_key, path_template,
             partition_keys[], schema_ref, sha256_hex, role, status, read_scope}.
      · S2 MUST:
          - only read artefacts listed here,
          - respect read_scope (ROW_LEVEL vs METADATA_ONLY).

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.layer2.yaml, schemas.5A.yaml
    - dataset_dictionary.layer2.5A.yaml
        · IDs & contracts for:
            - merchant_zone_profile_5A,
            - class_zone_shape_5A,
            - shape_grid_definition_5A,
            - (optional) class_shape_catalogue_5A.
    - dataset_dictionary.layer1.* + artefact_registry_{1A–3B,5A}.yaml
        · used to resolve logical IDs → {path, partitions, schema_ref}.

[Inputs from 5A.S1 · demand classes & scale]
    - merchant_zone_profile_5A
      @ layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/…
      · producer: 5A.S1.
      · partition_keys: [manifest_fingerprint]
      · primary_key:    [merchant_id, legal_country_iso, tzid]
      · schema_ref: schemas.5A.yaml#/model/merchant_zone_profile_5A
      · columns (min):
            merchant_id,
            legal_country_iso,
            tzid,
            demand_class,
            base_scale (e.g. weekly_volume_expected or scale_factor),
            scale_unit,
            scale_flags?,
            class_source, scale_source,
            scenario_id? (if wired),
            manifest_fingerprint.
      · S2’s use:
            - discover which demand_class×zone combinations actually exist,
            - derive the shape domain.

[5A shape/grid policies & configs]
    - shape_grid_policy_5A
        · defines the **local-week grid**:
            - bucket length (minutes),
            - number of buckets `T_week`,
            - mapping: bucket_index k → (local_day_of_week, local_minutes_since_midnight),
            - constraints (must cover exactly 7×24 hours when composed).
    - class_shape_policy_5A
        · defines base shape templates & modifiers for:
            - each demand_class (office-hours, weekend-heavy, night-heavy, etc.),
            - optional per-zone or per-country variants,
            - optional channel-based variants (if you encode that at S1).
        · shapes are defined as unnormalised “preference curves” over the week grid.
    - scenario metadata/configs
        · scenario_id, scenario_type (e.g. baseline vs stress),
        · “shape profile” selectors if S2 uses scenario to pick different templates.

[Outputs owned by S2]
    - shape_grid_definition_5A       (one grid per parameter_hash / scenario_id)
      @ layer2/5A/shape_grid_definition/{parameter_hash,scenario_id}/…
      · schema_ref: schemas.5A.yaml#/model/shape_grid_definition_5A
      · defines T_week buckets with:
            bucket_index,
            local_day_of_week,
            local_minutes_since_midnight,
            bucket_duration_minutes.

    - class_zone_shape_5A            (main shape library)
      @ layer2/5A/class_zone_shape/{parameter_hash,scenario_id}/…
      · schema_ref: schemas.5A.yaml#/model/class_zone_shape_5A
      · partition_keys: [parameter_hash, scenario_id]
      · primary_key:    [demand_class, legal_country_iso, tzid, bucket_index]
      · columns (min):
            parameter_hash,
            scenario_id,
            demand_class,
            legal_country_iso,
            tzid,
            bucket_index,
            shape_value ∈ [0,1],
            shape_sum_class_zone (optional cached Σ over k),
            shape_source_id/version.

    - class_shape_catalogue_5A       (optional, template-level)
      @ layer2/5A/class_shape_catalogue/{parameter_hash,scenario_id}/…
      · human-readable description of templates / parameters used to construct shapes.

[Numeric & RNG posture]
    - S2 is **RNG-free**:
        · MUST NOT use any RNG.
    - Determinism:
        · For fixed (parameter_hash, manifest_fingerprint, scenario_id) and sealed_inputs_5A,
          S2 MUST produce byte-identical shapes & grid even if re-run.
    - Numeric:
        · IEEE-754 binary64, round-to-nearest-even; no FMA/FTZ/DAZ.
        · Serial reductions only; no parallel sum reordering.
        · Per-class×zone shapes MUST sum to 1 (within configured tolerance ε_shape).


----------------------------------------------------------------------
DAG — 5A.S2 (classing output + shape policies → class×zone weekly shapes)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S2.1) Load S0 artefacts & fix identity
                    - Resolve:
                        · s0_gate_receipt_5A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_5A@fingerprint={manifest_fingerprint},
                      via 5A dictionary.
                    - Validate both against schemas.5A.yaml.
                    - From receipt:
                        · fix parameter_hash, manifest_fingerprint, run_id, scenario_id (or scenario_ids),
                        · read verified_upstream_segments.
                    - Recompute SHA-256 over sealed_inputs_5A rows in canonical order;
                      require equality with `sealed_inputs_digest` in the receipt.
                    - If upstream segments required by S2 (1A–3B, 2B, 3A/3B) are not PASS:
                        · S2 MUST fail (world not valid for Layer-2).

sealed_inputs_5A,
[Schema+Dict]
                ->  (S2.2) Resolve S1 output & shape policies via catalogue
                    - Using sealed_inputs_5A + dictionary/registry, resolve:
                        · merchant_zone_profile_5A@fingerprint={manifest_fingerprint},
                        · shape_grid_policy_5A (policy artefact),
                        · class_shape_policy_5A (policy artefact),
                        · scenario config pack (to map scenario_id → shape_profile, if used).
                    - For each policy/config artefact:
                        · recompute SHA-256(raw bytes) and assert equality with sealed_inputs_5A.sha256_hex,
                        · validate against their schema_refs in schemas.5A.yaml.
                    - Resolve & validate merchant_zone_profile_5A:
                        · schema_ref: schemas.5A.yaml#/model/merchant_zone_profile_5A,
                        · PK uniqueness and partition key check (fingerprint={manifest_fingerprint}).
                    - S2 MUST NOT directly read any other artefact not listed in sealed_inputs_5A.

shape_grid_policy_5A
                ->  (S2.3) Build local-week time grid (shape_grid_definition_5A)
                    - From shape_grid_policy_5A, derive:
                        · bucket_duration_minutes = Δt (fixed),
                        · T_week = number of buckets (integer),
                        · mapping:
                              for k = 0..T_week−1:
                                  local_day_of_week(k) ∈ {0..6} (or 1..7),
                                  local_minutes_since_midnight(k) ∈ [0, 24*60),
                                  bucket_duration_minutes(k) = Δt.
                    - Enforce:
                        · the grid covers a full 7 days exactly:
                              Σ_k bucket_duration_minutes(k) == 7*24*60.
                    - Assemble in-memory rows:
                        · one row per bucket_index k with the above fields plus {parameter_hash, scenario_id}.
                    - These rows define `shape_grid_definition_5A`; S2 MUST write them once (see S2.9–S2.10).

merchant_zone_profile_5A
                ->  (S2.4) Derive class×zone domain D_shape
                    - From merchant_zone_profile_5A:
                        · project onto:
                              demand_class, legal_country_iso, tzid.
                    - Define:
                        · D_shape = { (demand_class=c, country_iso, tzid) } for all rows.
                    - Optionally:
                        · union with any extra (demand_class, zone) combinations declared in class_shape_policy_5A
                          as “required shapes” even if no merchant currently occupies them.
                    - S2 MUST:
                        · treat D_shape as the domain of shapes it will emit in class_zone_shape_5A,
                        · NOT emit shapes for (class,zone) combos outside this domain.

shape_grid_definition_5A,
D_shape,
class_shape_policy_5A,
scenario_id / shape_profile
                ->  (S2.5) Construct unnormalised weekly shape templates per class×zone
                    - For each (demand_class C, legal_country_iso L, tzid Z) in D_shape:
                        1. Determine a **shape profile**:
                               profile_id = g_profile(C, L, Z, scenario_id, policy parameters),
                           e.g.:
                               - base template type (e.g. OFFICE_HOURS, 24_7, NIGHT_HEAVY),
                               - knobs (peak time, shoulder width, weekend boosts).
                        2. For each bucket_index k in shape_grid_definition_5A:
                               v(C,L,Z,k) = g_shape(profile_id, local_day_of_week(k), local_minutes_since_midnight(k)),
                           where g_shape is a deterministic function defined by the class_shape_policy_5A.
                    - The v-values are **unnormalised** (may not sum to 1, may be 0 in some buckets).
                    - S2 MUST ensure:
                        · v(C,L,Z,k) ≥ 0 for all (C,L,Z,k),
                        · not all v(C,L,Z,·) are zero (if all-zero, policy must define what to do: e.g. flat uniform).

unnormalised v(C,L,Z,k),
shape_grid_definition_5A
                ->  (S2.6) Normalise shapes per class×zone
                    - For each (C,L,Z) in D_shape:
                        1. Compute S = Σ_k v(C,L,Z,k) over the full 7-day grid.
                        2. If S == 0:
                               - behaviour MUST follow class_shape_policy_5A:
                                     · either treat as error, or
                                     · apply a deterministic fallback (e.g. uniform over all k),
                                   so that S_fallback > 0.
                               - record any fallback usage for validation.
                        3. Let S_eff be the mass after any fallback (S or S_fallback).
                        4. For each bucket k:
                               shape_value(C,L,Z,k) = v(C,L,Z,k) / S_eff.
                    - Enforce:
                        · shape_value(C,L,Z,k) ≥ 0,
                        · for each (C,L,Z):
                              Σ_k shape_value(C,L,Z,k) ≈ 1 within [1−ε_shape, 1+ε_shape]
                              for some small ε_shape defined in policy.
                    - Optionally compute:
                        · shape_sum_class_zone(C,L,Z) = Σ_k shape_value(C,L,Z,k) (stored for convenience).

(C,L,Z,k), shape_value,
shape_sum_class_zone (optional)
                ->  (S2.7) Assemble class_zone_shape_5A rows
                    - For each (C,L,Z) in D_shape and each bucket k:
                        · assemble row:
                              parameter_hash           = parameter_hash,
                              scenario_id              = scenario_id,
                              demand_class             = C,
                              legal_country_iso        = L,
                              tzid                     = Z,
                              bucket_index             = k,
                              shape_value              = shape_value(C,L,Z,k),
                              shape_sum_class_zone     = optional shape_sum_class_zone(C,L,Z),
                              shape_source_id          = class_shape_policy_5A.id,
                              shape_source_version     = class_shape_policy_5A.version.
                    - Domain:
                        · rows MUST cover D_shape × all bucket_index in shape_grid_definition_5A,
                        · no rows for (C,L,Z) / k outside this product set.
                    - Canonical ordering:
                        · sort by [demand_class, legal_country_iso, tzid, bucket_index] before writing.

class_zone_shape_5A (in-memory),
shape_grid_definition_5A (in-memory),
[Schema+Dict]
                ->  (S2.8) Validate shape invariants (pre-write)
                    - Validate `shape_grid_definition_5A` rows:
                        · cover exactly 7 days at the configured resolution,
                        · no duplicate bucket_index, no missing indices in 0..T_week−1,
                        · monotone non-decreasing (day_of_week, minutes) as index increases (if required by schema).
                    - Validate `class_zone_shape_5A` rows:
                        · PK uniqueness on (demand_class, legal_country_iso, tzid, bucket_index),
                        · for each (C,L,Z):
                              Σ_k shape_value ≈ 1 within ε_shape,
                        · shape_value ∈ [0,1] (or allowed range),
                        · legal_country_iso and tzid in permitted domains.
                    - Any invariant violation ⇒ S2 MUST fail; no output written.

shape_grid_definition_5A,
[Schema+Dict]
                ->  (S2.9) Write shape_grid_definition_5A (parameter-scoped, write-once)
                    - Target path via dictionary:
                        · (e.g.) data/layer2/5A/shape_grid_definition/parameter_hash={parameter_hash}/scenario_id={scenario_id}/…
                    - Validate rows against schemas.5A.yaml#/model/shape_grid_definition_5A.
                    - Immutability:
                        · if partition does not exist:
                              - write via staging → fsync → atomic move.
                        · if partition exists:
                              - read existing dataset, normalise schema + sort,
                              - if byte-identical → idempotent re-run; OK,
                              - else → conflict; S2 MUST NOT overwrite.

class_zone_shape_5A,
[Schema+Dict]
                ->  (S2.10) Write class_zone_shape_5A (parameter-scoped, write-once)
                    - Target path via dictionary:
                        · (e.g.) data/layer2/5A/class_zone_shape/parameter_hash={parameter_hash}/scenario_id={scenario_id}/…
                    - Validate rows against schemas.5A.yaml#/model/class_zone_shape_5A.
                    - Immutability:
                        · if partition does not exist:
                              - write via staging → fsync → atomic move.
                        · if partition exists:
                              - read existing dataset, normalise,
                              - if byte-identical → idempotent re-run; OK,
                              - else → conflict; MUST NOT overwrite.

class_zone_shape_5A,
shape_grid_definition_5A
                ->  (S2.11) Optionally build class_shape_catalogue_5A (template-level)
                    - From class_shape_policy_5A and the actual D_shape used:
                        · derive catalogue entries: one row per distinct template/profile_id,
                          with:
                              demand_class,
                              profile_id,
                              core parameters (peak_hour, peak_days, weekend_uplift, etc.).
                    - Validate and write only if dataset is registered and enabled:
                        · path resolved via dictionary (parameter_hash, scenario_id),
                        · same immutability/idempotence rules as other S2 outputs.

Downstream touchpoints
----------------------
- **5A.S3 — Baseline intensities:**
    - MUST combine:
          - base_scale(m,z) from merchant_zone_profile_5A,
          - shape_value(C(m,z), z, k) from class_zone_shape_5A,
      to obtain `lambda_local_base(m,z,k)`.
    - MUST NOT re-derive shapes from policies; S2 is the sole authority for class×zone weekly shapes.

- **5A.S4 — Scenario overlays:**
    - Uses shape_grid_definition_5A to map horizon buckets to local-week buckets,
      and conceptually relies on S2 as “the weekly shape oracle”.
    - MUST NOT change S2’s shape_value; only multiplies by overlay factors.

- **5A.S5 — Validation & HashGate:**
    - Replays S2 invariants:
          - domain alignment with S1 (D_shape ⊇ classes observed in merchant_zone_profile_5A),
          - grid coverage (full week, no duplicates/missing),
          - Σ_k shape_value ≈ 1 per (class,zone),
          - shape_source_id/version match the sealed class_shape_policy_5A.

- **External consumers (e.g. reporting tools):**
    - MAY read class_zone_shape_5A (subject to 5A HashGate) to get a high-level view
      of weekly intensity patterns per demand class×zone.
```