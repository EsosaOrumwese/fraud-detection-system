```
        LAYER 2 · SEGMENT 5A — STATE S4 (CALENDAR & SCENARIO OVERLAYS)  [NO RNG]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5A
      @ layer2/5A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5A.json
      · provides:
          - manifest_fingerprint, parameter_hash, run_id,
          - scenario_id (or scenario_pack_id),
          - verified_upstream_segments.{1A,1B,2A,2B,3A,3B},
          - sealed_inputs_digest.
      · S4 MUST:
          - treat this as the ONLY authority for identity & upstream PASS/FAIL,
          - recompute sealed_inputs_digest from sealed_inputs_5A and assert equality.

    - sealed_inputs_5A
      @ layer2/5A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5A.parquet
      · defines the complete artefact universe available to S4:
          - for each artefact:
                owner_layer, owner_segment, artifact_id, manifest_key,
                path_template, partition_keys[], schema_ref,
                sha256_hex, role, status, read_scope.
      · S4 MUST:
          - only read artefacts listed here,
          - honour `status` (REQUIRED/OPTIONAL/IGNORED),
          - honour `read_scope`:
                · ROW_LEVEL → may read rows,
                · METADATA_ONLY → may only inspect metadata (no row reads).

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.layer2.yaml, schemas.5A.yaml
    - dataset_dictionary.layer2.5A.yaml
        · IDs & contracts for:
            - merchant_zone_profile_5A             (S1; reference only),
            - shape_grid_definition_5A             (S2),
            - class_zone_shape_5A                  (S2; optional sanity),
            - merchant_zone_baseline_local_5A      (S3),
            - merchant_zone_scenario_local_5A      (S4; required),
            - merchant_zone_overlay_factors_5A     (S4; optional),
            - merchant_zone_scenario_utc_5A        (S4; optional).
    - artefact_registry_5A.yaml
        · registry entries for these datasets and S4 policies.

[Inputs from S1–S3]
    - merchant_zone_profile_5A  (S1)
      · used only for:
            - domain cross-check (S4 domain vs S1),
            - metadata; S4 MUST NOT reclassify or rescale.
    - shape_grid_definition_5A  (S2)
      · defines the local-week grid:
            bucket_index k → (local_day_of_week, local_minutes_since_midnight, bucket_duration_minutes),
            for (parameter_hash, scenario_id).
      · S4 uses it only to map horizon buckets to weekly buckets; MUST NOT modify it.
    - class_zone_shape_5A       (S2, optional)
      · S4 MAY read for sanity checks; MUST NOT rebuild shapes.
    - merchant_zone_baseline_local_5A  (S3)
      @ fingerprint={manifest_fingerprint}, scenario_id={scenario_id}
      · primary source for baseline λ:
            one curve λ_local_base(m,z[,ch],k) per (merchant, zone[,channel], bucket_index k).
      · S4 uses this as the sole baseline intensity surface; MUST NOT recompute scale×shape.

[Calendar & horizon configs (S4 control-plane)]
    - horizon_config_5A
        · defines:
            - local horizon start/end (dates & times),
            - local horizon bucket duration,
            - representation of horizon bucket index h,
            - optional UTC horizon config (if S4 outputs UTC intensities).
    - scenario_calendar artefacts
        · list of events with:
            - type (e.g. HOLIDAY, PAYDAY, CAMPAIGN, OUTAGE, STRESS),
            - time range (start_local, end_local),
            - scope (global, region, country, zone, demand_class, merchant, merchant_list, etc.),
            - event metadata (labels, scenario tags).
    - scenario_overlay_policy_5A
        · rules for mapping event surfaces → overlay factors F_overlay:
            - per event type,
            - per scope (global/zone/merchant),
            - combination rules (e.g. multiplicative cascade, caps, shutdown),
            - numeric bounds (min/max factor, special-case behaviour).

[Outputs owned by S4]
    - merchant_zone_scenario_local_5A   (required)
      @ layer2/5A/merchant_zone_scenario_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
      · partition_keys: [manifest_fingerprint, scenario_id]
      · primary_key:
            [manifest_fingerprint, scenario_id,
             merchant_id, legal_country_iso, tzid, local_horizon_bucket_index]
      · schema_ref: schemas.5A.yaml#/model/merchant_zone_scenario_local_5A
      · fields (min):
            manifest_fingerprint, parameter_hash, scenario_id,
            merchant_id, legal_country_iso, tzid,
            local_horizon_bucket_index (or equivalent local time key),
            lambda_local_scenario ≥ 0,
            optional: lambda_local_base, overlay_factor_total, spec_version.

    - merchant_zone_overlay_factors_5A  (optional)
      @ layer2/5A/merchant_zone_overlay_factors/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
      · partition_keys: [manifest_fingerprint, scenario_id]
      · primary_key:
            [manifest_fingerprint, scenario_id,
             merchant_id, legal_country_iso, tzid, local_horizon_bucket_index]
      · schema_ref: schemas.5A.yaml#/model/merchant_zone_overlay_factors_5A
      · fields: same keys as scenario_local, plus F_overlay and overlay components if schema defines them.

    - merchant_zone_scenario_utc_5A     (optional)
      @ layer2/5A/merchant_zone_scenario_utc/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
      · partition_keys: [manifest_fingerprint, scenario_id]
      · primary_key:
            [manifest_fingerprint, scenario_id,
             merchant_id, legal_country_iso, tzid, utc_horizon_bucket_index]
      · schema_ref: schemas.5A.yaml#/model/merchant_zone_scenario_utc_5A
      · fields:
            lambda_utc_scenario ≥ 0, plus UTC time keys.

[Numeric & RNG posture]
    - S4 is **RNG-free**:
        · MUST NOT use RNG,
        · MUST NOT emit RNG events or touch RNG logs.
    - Determinism:
        · For fixed (parameter_hash, manifest_fingerprint, scenario_id, run_id) and fixed S1–S3 outputs,
          horizon/calendar/overlay configs + sealed_inputs_5A, S4 MUST produce byte-identical outputs.
    - Numeric:
        · IEEE-754 binary64, round-to-nearest-even; no FMA/FTZ/DAZ.
        · Overlay factors F_overlay(m,z[,ch],h) MUST be finite and ≥ 0.
        · lambda_local_scenario(m,z[,ch],h) MUST be ≥ 0 and finite.


----------------------------------------------------------------------
DAG — 5A.S4 (Baseline λ_local + calendar + overlays → scenario λ_local/UTC)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S4.1) Load S0 gate & sealed_inputs; fix identity
                    - Resolve:
                        · s0_gate_receipt_5A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_5A@fingerprint={manifest_fingerprint},
                      via Layer-2 dictionary.
                    - Validate both against schemas.5A.yaml.
                    - From s0_gate_receipt_5A:
                        · fix {parameter_hash, manifest_fingerprint, run_id, scenario_id},
                        · read verified_upstream_segments.{1A,1B,2A,2B,3A,3B}.
                    - Recompute sealed_inputs_digest from sealed_inputs_5A (canonical order + serialisation);
                      require equality with receipt.sealed_inputs_digest.
                    - If any required upstream segment for S4 (1A–3B, 2B, 3A/3B) is not PASS:
                        · S4 MUST fail; world is not valid for scenario overlays.

sealed_inputs_5A,
[Schema+Dict]
                ->  (S4.2) Resolve S1–S3 surfaces & S4 configs via catalogue
                    - Using sealed_inputs_5A + dictionary/registry, resolve:
                        · merchant_zone_profile_5A@fingerprint={manifest_fingerprint}        (ROW_LEVEL or METADATA_ONLY),
                        · shape_grid_definition_5A@parameter_hash={parameter_hash},scenario_id={scenario_id},
                        · class_zone_shape_5A@parameter_hash={parameter_hash},scenario_id={scenario_id} (optional sanity),
                        · merchant_zone_baseline_local_5A@fingerprint={manifest_fingerprint},scenario_id={scenario_id},
                        · horizon_config_5A,
                        · scenario_calendar datasets,
                        · scenario_overlay_policy_5A.
                    - For each config/policy/calendar artefact:
                        · locate row in sealed_inputs_5A,
                        · recompute SHA-256(raw bytes) and assert equality with sha256_hex,
                        · validate against its schema_ref in schemas.5A.yaml.
                    - Validate S1–S3 datasets:
                        · merchant_zone_profile_5A, shape_grid_definition_5A,
                          class_zone_shape_5A (if used), merchant_zone_baseline_local_5A.

merchant_zone_baseline_local_5A,
(optional) merchant_zone_profile_5A,
scenario filters (if any)
                ->  (S4.3) Construct S4 domain D_S4 from S3
                    - Project merchant_zone_baseline_local_5A onto:
                          (merchant_id, zone_representation[,channel]) = (m,z[,ch]).
                    - Apply any S4-specific filters from configs, e.g.:
                          - exclude flag “no overlay” merchants/zones,
                          - ignore extremely small-scale cells if policy says so.
                    - Define:
                        · D_S4 = { (m,z[,ch]) } = set of in-scope merchant×zone×(channel) for S4.
                    - Optionally cross-check vs S1 domain:
                        · any (m,z[,ch]) in S1 but not in S3 or not in D_S4 SHOULD be treated as upstream misalignment.
                    - Invariant:
                        · D_S4 is the sole domain S4 will cover; all outputs refer only to D_S4.

horizon_config_5A,
shape_grid_definition_5A
                ->  (S4.4) Build local horizon grid H_local & WEEK_MAP[h] → k
                    - From horizon_config_5A, derive:
                        · H_local = {local_horizon_bucket_index h | h=0..H−1},
                        · for each h:
                              local_date(h) (e.g. YYYY-MM-DD in local time),
                              local_bucket_within_date(h),
                              local_day_of_week(h),
                              local_minutes_since_midnight(h),
                              bucket_duration_minutes(h).
                    - From shape_grid_definition_5A:
                        · weekly grid bucket_index k with:
                              (local_day_of_week(k), local_minutes_since_midnight(k), duration).
                    - Build mapping:
                        · WEEK_MAP[h] = k,
                          such that horizon bucket h falls into weekly bucket k
                          (same day_of_week and within its time span).
                    - Enforce:
                        · ∀h ∈ H_local, WEEK_MAP[h] is defined and unique,
                        · WEEK_MAP[h] ∈ [0..T_week−1],
                        · no h maps to an invalid or non-existent k.
                    - If mapping fails (mismatched configs) ⇒ S4_HORIZON_GRID_INVALID; S4 MUST abort.

scenario_calendar datasets,
D_S4,
H_local,
local time metadata per h
                ->  (S4.5) Construct event surfaces EVENTS[m,z[,ch],h]
                    - Preprocess scenario events:
                        · normalise each event’s time range to local time for each applicable zone,
                        · expand event scopes:
                              - GLOBAL,
                              - per region/country/zone,
                              - per demand_class/merchant/merchant_list.
                    - For each (m,z[,ch]) ∈ D_S4 and each h ∈ H_local:
                        · determine which events apply:
                              EVENTS[m,z[,ch],h] = {events e whose:
                                    time_range contains h’s local time window,
                                    AND scope includes (m,z[,ch]) }.
                    - Invariants:
                        · every event whose local range intersects H_local and whose scope includes (m,z[,ch])
                          MUST appear in EVENTS[m,z[,ch],h] for the relevant buckets.
                        · no event may appear outside its declared time window or scope.
                    - Any misalignment (invalid time ranges, unknown scope identifiers) ⇒ S4_CALENDAR_ALIGNMENT_FAILED.

EVENTS[m,z[,ch],h],
scenario_overlay_policy_5A
                ->  (S4.6) Evaluate overlay factors F_overlay[m,z[,ch],h]
                    - For each (m,z[,ch]) ∈ D_S4 and each h ∈ H_local:
                        1. Initialise F = 1.0 (baseline multiplicative factor).
                        2. From scenario_overlay_policy_5A, gather rules applicable to events in EVENTS[m,z[,ch],h].
                        3. For each event e in EVENTS[m,z[,ch],h] in a deterministic order:
                               - compute local factor f_e(m,z[,ch],h) according to e.type, e.scope and policy parameters:
                                     e.g. “holiday” multiplier, “campaign” uplift, “outage” suppression, etc.
                               - combine into F using policy’s combination law:
                                     (e.g. multiply, apply caps, handle mutually exclusive events).
                        4. After processing all events:
                               - F_overlay[m,z[,ch],h] = F.
                    - Invariants:
                        · F_overlay(m,z[,ch],h) MUST be finite and ≥ 0 for all (m,z[,ch],h).
                        · No ad-hoc, out-of-policy tweaks; mapping EVENTS → F_overlay must be entirely determined
                          by scenario_overlay_policy_5A.
                    - Failure to compute F_overlay for any (m,z[,ch],h) ⇒ S4_OVERLAY_EVAL_FAILED.

D_S4, H_local,
merchant_zone_baseline_local_5A,
WEEK_MAP[h],
F_overlay
                ->  (S4.7) Compose λ_local_scenario(m,z[,ch],h)
                    - Build an index over S3 baselines:
                        · BASE[m,z[,ch],k] = lambda_local_base(m,z[,ch],k)
                          for all (m,z[,ch]) ∈ D_S4, bucket_index k in weekly grid.
                    - For each (m,z[,ch]) ∈ D_S4 and each h ∈ H_local:
                        1. Look up k = WEEK_MAP[h].
                        2. Retrieve baseline λ_base = BASE[m,z[,ch],k].
                        3. Retrieve overlay factor F = F_overlay[m,z[,ch],h].
                        4. Compute:
                               lambda_local_scenario(m,z[,ch],h) = λ_base * F.
                        5. Check:
                               - lambda_local_scenario ≥ 0,
                               - finite (no NaN/Inf),
                               - any policy-defined max/min threshold.
                    - Optional checks:
                        · If overlay policy defines weekly/horizon invariants (e.g. budget-preservation of total mass),
                          compute such aggregates and verify within tolerance.
                    - Invariant:
                        · For every (m,z[,ch],h) ∈ D_S4×H_local, lambda_local_scenario is uniquely defined and ≥ 0.

lambda_local_scenario,
F_overlay (if persisted),
H_local,
optional tz mapping inputs
                ->  (S4.8) Optional UTC projection λ_utc_scenario(m,z[,ch],h_utc)
                    - If merchant_zone_scenario_utc_5A is enabled:
                        1. From UTC horizon config, build UTC grid:
                               H_utc = {utc_horizon_bucket_index h_utc}.
                        2. Use 2A tz mapping (e.g. tz_timetable_cache) and local horizon grid
                           to map local buckets h for zone z to UTC buckets h_utc.
                        3. For each (m,z[,ch],h_utc):
                               - compute lambda_utc_scenario(m,z[,ch],h_utc) as a deterministic redistribution
                                 of lambda_local_scenario(m,z[,ch],h) over mapped intervals.
                        4. Enforce:
                               - lambda_utc_scenario ≥ 0, finite,
                               - optional: Σ_{h_utc} lambda_utc_scenario ≈ Σ_h lambda_local_scenario per (m,z[,ch]).
                    - If disabled:
                        · S4 MUST NOT emit merchant_zone_scenario_utc_5A.

lambda_local_scenario,
F_overlay (if persisted),
H_local,
(optional) lambda_utc_scenario, H_utc
                ->  (S4.9) Construct S4 output rows
                    - Build `SCEN_LOCAL_ROWS`:
                        · For each (m,z[,ch]) ∈ D_S4 and each h ∈ H_local:
                              - row:
                                    manifest_fingerprint,
                                    parameter_hash,
                                    scenario_id,
                                    merchant_id,
                                    legal_country_iso,
                                    tzid,
                                    local_horizon_bucket_index = h,
                                    lambda_local_scenario      = lambda_local_scenario(m,z[,ch],h),
                                    optional:
                                         - lambda_local_base (echo),
                                         - overlay_factor_total = F_overlay(m,z[,ch],h),
                                         - spec_version = S4 spec version string.
                    - If overlay factors are to be persisted:
                        · Build `OVERLAY_ROWS` with the same key as SCEN_LOCAL_ROWS but storing F_overlay
                          (and any decomposed factors, if schema provides).
                    - If UTC projection is enabled:
                        · Build `SCEN_UTC_ROWS`:
                              - for each (m,z[,ch],h_utc) in UTC domain:
                                    manifest_fingerprint, parameter_hash, scenario_id,
                                    merchant_id, legal_country_iso, tzid,
                                    utc_horizon_bucket_index = h_utc,
                                    lambda_utc_scenario      = lambda_utc_scenario(m,z[,ch],h_utc),
                                    optional mapping hints.
                    - Validate in-memory rows against schemas.5A.yaml:
                        · merchant_zone_scenario_local_5A,
                        · merchant_zone_overlay_factors_5A (if used),
                        · merchant_zone_scenario_utc_5A (if used).

SCEN_LOCAL_ROWS,
OVERLAY_ROWS?,
SCEN_UTC_ROWS?,
[Schema+Dict]
                ->  (S4.10) Atomic write & idempotency
                    - Canonical paths via dictionary:
                        · merchant_zone_scenario_local_5A:
                              layer2/5A/merchant_zone_scenario_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
                        · merchant_zone_overlay_factors_5A (if enabled):
                              layer2/5A/merchant_zone_overlay_factors/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
                        · merchant_zone_scenario_utc_5A (if enabled):
                              layer2/5A/merchant_zone_scenario_utc/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
                    - Immutability & idempotence:
                        · For each dataset:
                              - if partition does not exist:
                                    * write via staging → fsync → atomic move into final path;
                              - if partition exists:
                                    * read existing dataset, normalise to same schema+sort,
                                    * if byte-identical to new rows → idempotent re-run; OK,
                                    * else → `S4_OUTPUT_CONFLICT`; MUST NOT overwrite.
                    - Atomicity:
                        · If multiple S4 outputs are enabled (local, overlay, UTC),
                          S4 MUST NOT publish a subset:
                              - either all required outputs for this (manifest_fingerprint,scenario_id) are committed,
                              - or none are visible (staging-only).
                    - On failure:
                        · S4 MUST leave no partially written “canonical” outputs; only `.staging/` artefacts may exist,
                          and downstream MUST ignore staging paths.

Downstream touchpoints
----------------------
- **5A.S5 — Validation & HashGate:**
    - Treats merchant_zone_scenario_local_5A (and UTC/overlay datasets if present) as the authoritative
      scenario-aware intensity surfaces.
    - Replays S4’s invariants:
          - domain = D_S4,
          - WEEK_MAP correctness,
          - EVENT → F_overlay mapping per policy,
          - λ_local_scenario ≥ 0 and finite,
          - optional UTC conservation (if enabled).

- **5B — Arrival realisation:**
    - Uses merchant_zone_scenario_local_5A (and/or merchant_zone_scenario_utc_5A) as the **only**
      intensity surfaces for Poisson/LGCP draws.
    - MUST NOT recompute overlays itself; it only realises stochastic arrivals from S4’s λ.

- **6A / other consumers:**
    - MUST gate use of S4 outputs on the segment-level `_passed.flag` produced by S5:
          **No 5A PASS → No read/use of 5A scenario intensities.**
```