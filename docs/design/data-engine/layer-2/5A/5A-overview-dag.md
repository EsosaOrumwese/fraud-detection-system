```
                     LAYER 2 · SEGMENT 5A (Arrival Intensity Engine · “λ Planner”)

Authoritative inputs (sealed in 5A.S0)
--------------------------------------
[World & identity]
    - manifest_fingerprint      (the Layer-1 world from 1A–3B / 2B / 3A / 3B)
    - parameter_hash            (which 5A parameter pack / policies / scenarios we’re using)
    - run_id                    (this 5A run; never used for partitioning)

[Upstream Layer-1/2 segments (must be PASS)]
    - 1A/1B/2A/2B/3A/3B validation_bundle_* + _passed.flag_* @ fingerprint={manifest_fingerprint}
      · 5A never reads their data here; S0 only replays their bundle+flag laws to confirm PASS.

[World surfaces 5A may read]
    - Merchant reference / merchant catalogue          (ids, MCC, channel, size, home_country, brand, etc.)
    - Zone allocation                                  (from 3A — per merchant×country×tzid, with outlet counts)
    - Civil-time surfaces                              (site_timezones, tz_timetable_cache, zone tz metadata)
    - Virtual flags/surfaces                           (from 3B, if class/scale policies use virtual vs physical)
    - Any additional Layer-1/2 surfaces explicitly named by 5A policies

[5A policies & configs]
    - Classing policy             (merchant_class_policy_5A)
    - Scale policy                (demand_scale_policy_5A)
    - Weekly shape/grid policy    (shape_grid_policy_5A)
    - Class shape policy          (class_shape_policy_5A)
    - Baseline composition policy (baseline_intensity_policy_5A)
    - Horizon & calendar configs  (horizon_config_5A, scenario_calendar_*)
    - Overlay policy              (scenario_overlay_policy_5A)
    - Validation policy           (what S5 will check per state)
    - Scenario pack               (scenario_id, scenario_type, scenario_profile, etc.)


DAG
---
(M, world, policies) --> (S0) Gate & sealed inputs                           [NO RNG]
                    - Re-verifies upstream segment HashGates (1A–3B, 2B, 3A/3B) for this manifest_fingerprint.
                    - Discovers all artefacts 5A is allowed to use via dictionaries + registries:
                        · world surfaces (merchant ref, zone_alloc, civil-time, virtual flags),
                        · all 5A policies/configs,
                        · scenario definitions.
                    - Computes SHA-256 over each and writes:
                        · sealed_inputs_5A@ fingerprint={manifest_fingerprint}:
                              one row per artefact with {owner, id, path_template, schema_ref, sha256_hex, role, status, read_scope}.
                        · s0_gate_receipt_5A@ fingerprint={manifest_fingerprint}:
                              manifest_fingerprint, parameter_hash, run_id,
                              scenario_id / scenario_pack_id,
                              verified_upstream_segments,
                              sealed_inputs_digest (hash over sealed_inputs_5A).
                    - S0 is RNG-free; defines the closed world that S1–S4 must live in.

                                      |
                                      | s0_gate_receipt_5A, sealed_inputs_5A
                                      v

(S1) Merchant×zone demand class & base scale        [NO RNG]
    inputs:
        - merchant reference (MCC, channel, size, home_country, etc.),
        - zone_alloc (who has outlets in which time-zones),
        - optional civil-time & virtual flags,
        - merchant_class_policy_5A,
        - demand_scale_policy_5A,
        - scenario metadata.
    -> merchant_zone_profile_5A@ fingerprint={manifest_fingerprint}
         - Builds domain D = { (merchant_id, legal_country_iso, tzid[, channel]) } from zone_alloc.
         - For each (m, zone):
             · builds feature vector from merchant + zone + scenario,
             · applies classing policy → demand_class(m, zone),
             · applies scale policy → base_scale(m, zone) + scale_unit + flags.
         - Emits one row per (m, zone) with:
             · demand_class,
             · base_scale (e.g. weekly expected arrivals),
             · scale_unit, flags,
             · class_source, scale_source.
         - S1 is RNG-free; it is the sole authority on demand_class and base_scale per merchant×zone.

                                      |
                                      | merchant_zone_profile_5A
                                      v

(S2) Class×zone weekly shape library               [NO RNG]
    inputs:
        - merchant_zone_profile_5A (to see which demand_class×zone combos exist),
        - shape_grid_policy_5A (defines local-week time grid),
        - class_shape_policy_5A (templates/modifiers per class, zone, scenario),
        - scenario metadata.
    -> shape_grid_definition_5A@ parameter_hash,scenario_id
         - Defines the **local-week grid**:
             · bucket_index k,
             · local_day_of_week(k),
             · local_minutes_since_midnight(k),
             · bucket_duration_minutes,
             · covers exactly 7×24h at fixed resolution.

    -> class_zone_shape_5A@ parameter_hash,scenario_id
         - For each (demand_class, zone) in domain:
             · builds an unnormalised weekly curve v(class,zone,k),
             · normalises to unit mass:
                   shape_value(class,zone,k) ≥ 0,
                   Σ_k shape_value(class,zone,k) ≈ 1.
         - Emits one row per (class,zone,k) with:
             · shape_value and optional shape_sum_class_zone.

    (optional) -> class_shape_catalogue_5A (template-level info)

    - S2 is RNG-free; it is the sole authority on the “shape” of a week for each class×zone.

                                      |
                                      | merchant_zone_profile_5A, class_zone_shape_5A, shape_grid_definition_5A
                                      v

(S3) Baseline merchant×zone weekly intensities      [NO RNG]
    inputs:
        - merchant_zone_profile_5A  (class & base_scale per (m,zone)),
        - class_zone_shape_5A       (unit-mass shape per (class,zone)),
        - shape_grid_definition_5A  (time grid),
        - baseline_intensity_policy_5A (how to interpret base_scale).
    -> merchant_zone_baseline_local_5A@ fingerprint={manifest_fingerprint},scenario_id
         - Domain D_S3 = D from S1.
         - For each (m, zone):
             · get demand_class and base_scale from S1,
             · get shape_value(class(m,zone), zone, k) from S2,
             · compute λ_base_local(m,zone,k) = base_scale × shape_value.
         - Enforces:
             · λ_base_local ≥ 0 and finite,
             · per-(m,zone) weekly sum Σ_k λ_base_local respects base_scale semantics
               (e.g. equals weekly_expected_arrivals within tolerance).
         - Emits one row per (m,zone,k) with:
             · lambda_local_base,
             · base_scale_used, scale_unit,
             · demand_class, class/scale sources.

    (optional) -> class_zone_baseline_local_5A  (aggregated over merchants)
    (optional) -> merchant_zone_baseline_utc_5A (UTC projection via 2A tz law)

    - S3 is RNG-free; it is the single authority on baseline λ(m,zone,k) over the local week.

                                      |
                                      | merchant_zone_baseline_local_5A, shape_grid_definition_5A,
                                      | horizon_config_5A, scenario_calendar_*, scenario_overlay_policy_5A
                                      v

(S4) Calendar & scenario overlays                   [NO RNG]
    inputs:
        - merchant_zone_baseline_local_5A (baseline λ_local),
        - shape_grid_definition_5A        (local-week k grid),
        - horizon_config_5A               (local horizon grid H_local),
        - scenario_calendar_*             (events: holidays, campaigns, outages, etc.),
        - scenario_overlay_policy_5A      (how events map to multiplicative factors),
        - optional merchant_zone_profile_5A (metadata / domain cross-checks).
    -> merchant_zone_scenario_local_5A@ fingerprint={manifest_fingerprint},scenario_id
         - Builds local horizon grid H_local: buckets h across real dates.
         - Maps each horizon bucket h to a weekly bucket k via WEEK_MAP[h] using the shape grid.
         - Builds per-bucket event sets:
             · EVENTS[m,zone,h] = events whose time window & scope include that (m,zone,h).
         - Evaluates overlay factors via policy:
             · F_overlay(m,zone,h) ≥ 0, finite.
         - For each (m,zone,h):
             · λ_base_local = λ_base_local(m,zone,k=WEEK_MAP[h]),
             · λ_scenario_local(m,zone,h) = λ_base_local × F_overlay(m,zone,h).
         - Emits one row per (m,zone,h) with:
             · lambda_local_scenario,
             · optional lambda_local_base, overlay_factor_total.

    (optional) -> merchant_zone_overlay_factors_5A (explicit F_overlay per bucket)
    (optional) -> merchant_zone_scenario_utc_5A    (UTC projection of scenario λ)

    - S4 is RNG-free; it is the sole authority on scenario-aware λ_local(m,zone,h).

                                      |
                                      | s0_gate_receipt_5A, sealed_inputs_5A,
                                      | S1–S4 outputs, policies, configs
                                      v

(S5) Segment validation & HashGate                   [NO RNG]
    inputs:
        - s0_gate_receipt_5A, sealed_inputs_5A,
        - S1–S4 outputs (as discovered via dictionary + sealed_inputs_5A),
        - 5A validation policy (check definitions, thresholds).
    -> validation_report_5A@ fingerprint={manifest_fingerprint}
         - Replays and records:
             · S1: domain coverage, class completeness, base_scale validity,
             · S2: full-week grid coverage, shape normalisation Σ=1,
             · S3: domain alignment, weekly sums vs base_scale, numeric safety,
             · S4: horizon mapping correctness, overlay factor validity, scenario λ properties.
         - Produces overall PASS/FAIL + check-level metrics.

    -> validation_issue_table_5A@ fingerprint={manifest_fingerprint} (optional)
         - Per-issue rows with check_id, severity, code, and entity context.

    -> validation_bundle_index_5A@ fingerprint={manifest_fingerprint}
         - `entries[] = {path, sha256_hex}` for all evidence files in the bundle,
           paths relative to `data/layer2/5A/validation/fingerprint={manifest_fingerprint}/`,
           sorted by path.

    -> validation_passed_flag_5A@ fingerprint={manifest_fingerprint}
         - Recomputes `bundle_digest_sha256 = SHA256( concat(all indexed file bytes in path order) )`,
         - Writes `_passed.flag` as:
               `sha256_hex = <bundle_digest_sha256>`.

    - S5 is RNG-free; it builds the 5A HashGate for this world.

Downstream obligations
----------------------
- **5B (arrival realisation) & 6A (later layers)** MUST:
    - Treat 5A’s outputs as authoritative for arrival intensities **only after** validating:
          - `validation_bundle_index_5A` is schema-valid for this manifest_fingerprint,
          - `_passed.flag` exists and its sha256_hex matches the recomputed bundle digest.
    - Enforce:

          **No 5A PASS → No read/use of S1–S4 outputs**  
          (no merchant_zone_profile_5A, no shapes, no baselines, no scenario λ).

Legend
------
(Sx) = state in Segment 5A
[manifest_fingerprint]  = partition key for world
[parameter_hash]        = partition key for parameter pack / policies
[scenario_id]           = partition key for scenario
[NO RNG]                = state consumes no RNG
HashGate (5A)           = validation_bundle_index_5A + `_passed.flag` at fingerprint={manifest_fingerprint}
```
