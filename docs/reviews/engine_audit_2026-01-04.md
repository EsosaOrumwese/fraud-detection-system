# Engine Audit 2026-01-04 (1A-6B)

Scope
- Purpose: Segment-by-segment review of engine implementation vs binding specs and contracts (Layer-1 1A-3B, Layer-2 5A-5B, Layer-3 6A-6B).
- Focus: Inputs/outputs, path/partition law, gate enforcement, upstream/downstream handoffs, and failure points.
- Sources: packages/engine implementation, docs/model_spec specs and contracts, runtime dictionaries/registries under contracts/.
- Runs referenced: runs/local_full_run-3, runs/local_full_run-2.

Status
- This document is being built incrementally. Each segment section will be filled as reviewed.

Method
- For each segment: capture expected inputs/outputs from spec contracts; trace implementation resolution paths and gate logic; note mismatches, missing assets, and handoff failures.
- No code changes in this audit.

---

Segment 1A
- Spec scope: docs/model_spec/data-engine/layer-1/specs/state-flow/1A/* and contracts/1A/*
- Implementation scope: packages/engine/src/engine/layers/l1/seg_1A, scenario_runner/l1_seg_1A.py, CLI segment1a.py

Expected inputs (spec + contracts)
- Ingress/reference: merchant_ids (transaction_schema_merchant_ids), iso3166_canonical_2024, world_countries, population_raster_2025, tz_world_2025a, GDP/bucket refs (per S0 spec).
- Parameter policies: ccy_smoothing_params, s6_selection_policy, s7 integerisation policy, S3 rule ladder/thresholds/bounds, S3 priors toggles (per S3/S7 specs).
- Validation policy for S2 corridor (used when validate_s2 is enabled).

Observed implementation
- Orchestrator sequences S0 -> S9 (packages/engine/src/engine/scenario_runner/l1_seg_1A.py).
- S0 materialises validation_bundle_1A at data/layer1/1A/validation/fingerprint={manifest_fingerprint}/ with MANIFEST.json, parameter_hash_resolved.json, manifest_fingerprint_resolved.json, param_digest_log.jsonl, fingerprint_artifacts.jsonl, numeric_policy_attest.json, and _passed.flag (packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l2/output.py).
- S2/S3/S4 validation artifact publishers add files into validation bundle and refresh _passed.flag using refresh_validation_bundle_flag (packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/l3/bundle.py and s4_ztp_target/l3/bundle.py).

Handoff to 1B (and other downstreams)
- 1B S0 reads validation_bundle_1A and validation_passed_flag_1A and verifies outlet_catalogue lineage (packages/engine/src/engine/layers/l1/seg_1B/s0_gate/l2/runner.py). This aligns with 1B S0 spec and contracts.

Findings
- Validation bundle path mismatch suspected: run log shows S2/S4 attempting to publish to runs/local_full_run-3/validation_bundle/manifest_fingerprint=... and skipping because the directory is missing. The dictionary path for validation_bundle should be data/layer1/1A/validation/fingerprint=... (contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml). Either a stale dictionary or divergent path resolution is used at runtime, which prevents validation artifacts from being added to the bundle.
- Run log warnings indicate missing legal tender mapping (S5) and missing settlement currency for many merchants (S6), then S8 defaulting to home-only allocation for many merchants. The spec expects full coverage or explicit gate failures for missing coverage; current implementation appears to degrade without abort. Needs an explicit spec-compliance decision: should missing coverage be fatal or allowed with warnings.

---

Segment 1B
- Spec scope: docs/model_spec/data-engine/layer-1/specs/state-flow/1B/* and contracts/1B/*
- Implementation scope: packages/engine/src/engine/layers/l1/seg_1B, scenario_runner/l1_seg_1B.py, CLI segment1b.py

Expected inputs (spec + contracts)
- Upstream: validation_bundle_1A + validation_passed_flag_1A (gate), outlet_catalogue (1A egress).
- Reference: iso3166_canonical_2024, world_countries, population_raster_2025.
- Governed parameters: tile_index/tile_bounds built in S1, weights in S2, requirements in S3, etc.

Observed implementation
- S0 gate verifies validation_bundle_1A, _passed.flag, and outlet_catalogue lineage before proceeding (packages/engine/src/engine/layers/l1/seg_1B/s0_gate/l2/runner.py).
- S6 jitter and later states complete successfully in run log; S9 writes bundle and _passed.flag (runs/local_full_run-3/run_log_run-3.log).
 - S7 run summary and S8 run summary are written via dataset_path.parent, which drops parameter_hash (S7) and fingerprint (S8) from the path, diverging from dictionary contracts (packages/engine/src/engine/layers/l1/seg_1B/s7_site_synthesis/l2/materialise.py and s8_site_locations/l2/materialise.py).

Handoff to 2A (and other downstreams)
- 2A depends on site_locations and 1B validation bundle; 1B S8 emits site_locations and S9 emits validation bundle + _passed.flag.

Findings
- S7 run summary path is written to dataset_path.parent/s7_run_summary.json. dataset_path is the seed/fingerprint/parameter_hash partition, so parent drops parameter_hash. Dictionary expects s7_run_summary inside the partition (contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml). This is a path/partition mismatch.
- S8 run summary path is written to dataset_path.parent/s8_run_summary.json, which drops fingerprint (seed-only path). Dictionary expects s8_run_summary inside the seed+fingerprint partition. This mismatch is visible in run log (report path missing fingerprint).

---

Segment 2A
- Spec scope: docs/model_spec/data-engine/layer-1/specs/state-flow/2A/* and contracts/2A/*
- Implementation scope: packages/engine/src/engine/layers/l1/seg_2A, scenario_runner/l1_seg_2A.py, CLI segment2a.py

Expected inputs (spec + contracts)
- Upstream gate: validation_bundle_1B + validation_passed_flag_1B (No PASS -> No Read).
- Required inputs: site_locations (1B egress), tz_world_2025a, tzdb_release, tz_overrides, tz_nudge, merchant_mcc_map (materialised from reference).

Observed implementation
- S0 resolves validation_bundle_1B and verifies its _passed.flag (packages/engine/src/engine/layers/l1/seg_2A/s0_gate/l2/runner.py).
- S0 additionally resolves validation_bundle_1A to load parameter_hash_resolved.json and verify parameter_hash (runner.py:163, 267). The Segment 2A runtime dictionary does not include validation_bundle_1A, causing a hard failure in run_log_run-3 (2A-S0-012).
- S0GateError is a frozen dataclass; exception handling triggers FrozenInstanceError when Python tries to assign __traceback__, masking the original error (packages/engine/src/engine/layers/l1/seg_2A/s0_gate/exceptions.py).
- S0 materialises merchant_mcc_map by reading the latest reference/layer1/transaction_schema_merchant_ids version; if the reference root or a version folder is missing, S0 aborts (packages/engine/src/engine/layers/l1/seg_2A/s0_gate/l2/runner.py).
- S1 resolves site_locations using upstream_manifest_fingerprint and validates sealed_inputs_v1 paths against dictionary entries; tz_world asset id is discovered from sealed assets and must contain tzid column, tz_nudge must include epsilon_degrees and sha256_digest (packages/engine/src/engine/layers/l1/seg_2A/s1_provisional/l2/runner.py).
- S2 loads tz_overrides and optionally merchant_mcc_map; when MCC overrides exist but mapping is missing, it warns and proceeds, meaning overrides may be silently skipped (packages/engine/src/engine/layers/l1/seg_2A/s2_overrides/l2/runner.py).
- S3 requires tzdb_release bundle, validates digest, emits tz_timetable_cache and tz_offset_adjustments; missing tzdb files or invalid digest aborts (packages/engine/src/engine/layers/l1/seg_2A/s3_timetable/l2/runner.py).
- S4 requires site_timezones and tz_timetable_cache; missing tzids in cache yield FAIL status (packages/engine/src/engine/layers/l1/seg_2A/s4_legality/l2/runner.py).
- S5 builds validation_bundle_2A by collecting tz_timetable_cache.json, optional tz_offset_adjustments.json, and PASSing s4_legality_report per seed; missing or non-PASS seeds abort; index.json + _passed.flag are emitted after staging (packages/engine/src/engine/layers/l1/seg_2A/s5_validation/l2/runner.py).

Handoff to 2B/3A/3B
- Outputs (site_timezones, tz_timetable_cache, validation bundle + _passed.flag) are intended inputs for 2B, 3A, 3B. The current run did not reach these states due to S0 failure.

Findings
- Critical: Segment 2A dictionary lacks validation_bundle_1A but code requires it. This is a spec/implementation mismatch and the immediate run-stopper for S0.
- Critical: S0GateError frozen dataclass causes FrozenInstanceError on exception handling, preventing clean failure reporting.
- High: S0 depends on reference/layer1/transaction_schema_merchant_ids being present; missing reference root or version folder will hard-fail gate even before upstream bundle checks.
- Medium: S2 proceeds when MCC overrides exist but merchant_mcc_map is missing, silently skipping overrides. If the spec expects MCC overrides to be applied when declared, this is a compliance gap.

---

Segment 2B
- Spec scope: docs/model_spec/data-engine/layer-1/specs/state-flow/2B/* and contracts/2B/*
- Implementation scope: packages/engine/src/engine/layers/l1/seg_2B, scenario_runner/l1_seg_2B.py, CLI segment2b.py

Expected inputs (spec + contracts)
- Upstream gates: validation_bundle_1B + _passed.flag, plus 2A site_timezones and tz_timetable_cache (with 2A PASS).
- Policy packs: route_rng_policy_v1, alias_layout_policy_v1, day_effect_policy_v1, virtual_edge_policy_v1, virtual_rules_policy_v1.

Observed implementation
- S0 gate verifies validation_bundle_1B and _passed.flag, seals site_locations and policy packs, and optionally seals site_timezones/tz_timetable_cache using a separate seg2a_manifest_fingerprint (packages/engine/src/engine/layers/l1/seg_2B/s0_gate/l2/runner.py).
- No explicit verification of validation_bundle_2A/_passed.flag is performed before sealing site_timezones or tz_timetable_cache; only 1B is gated.
- S0 requires policy asset IDs route_rng_policy_v1, alias_layout_policy_v1, day_effect_policy_v1, virtual_edge_policy_v1, virtual_rules_policy_v1; missing any policy file or dictionary entry will hard-fail S0.
- S1 loads alias_layout_policy_v1, reads site_locations, applies floor/cap/normalisation/quantisation per merchant, and writes s1_site_weights with a run report under reports/l1/s1_weights (packages/engine/src/engine/layers/l1/seg_2B/s1_weights/l2/runner.py).
- S2 reads s1_site_weights and alias_layout_policy_v1, builds alias index/blob (index.json + alias.bin) and writes s2_alias_index/blob with a run report under reports/l1/s2_alias (packages/engine/src/engine/layers/l1/seg_2B/s2_alias/l2/runner.py).
- S3 generates s3_day_effects via Philox RNG, joining s1_site_weights to site_timezones pinned by seg2a_manifest_fingerprint; run report paths refer to the 2B manifest even when inputs are pinned to seg2a (packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/l2/runner.py).
- S4 joins s1_site_weights, site_timezones (seg2a manifest), and s3_day_effects; enforces per-day coverage and normalisation, emitting s4_group_weights (packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/l2/runner.py).
- S5 router reads s4_group_weights + s1_site_weights + site_timezones (seg2a manifest), builds alias tables, emits rng_event logs and optional selection logs under parameter_hash/run_id; uses hashed site_id = sha256(merchant_id:country:site_order) for routing and logging (packages/engine/src/engine/layers/l1/seg_2B/s5_router/l2/runner.py).
- S6 routes virtual arrivals using virtual_edge_policy_v1 + route_rng_policy_v1, emits rng logs and optional edge logs under parameter_hash/run_id, and writes a run report under reports/l1/s6_virtual_edge (packages/engine/src/engine/layers/l1/seg_2B/s6_virtual_edge/l2/runner.py).
- S7 audit validates alias artefacts and day surfaces; when S5/S6 evidence is provided it cross-checks RNG logs and selection logs, using site_id = (merchant_id << 32 | site_order) to map site_timezones (packages/engine/src/engine/layers/l1/seg_2B/s7_audit/l2/runner.py).
- S8 builds validation_bundle_2B by collecting S7 PASS reports across the seed intersection of s2/s3/s4 outputs, staging policies + s0 evidence, and emitting index.json + _passed.flag (packages/engine/src/engine/layers/l1/seg_2B/s8_validation/l2/runner.py).

Handoff to 3A/3B/5B
- Outputs: s1_site_weights, s2_alias_index/blob, s3_day_effects, s4_group_weights (all seed+fingerprint). Used downstream by 5A (intensity baseline) and 5B routing, and for 3A/3B cross-segment integrity.

Findings
- Potential gate gap: 2B S0 verifies 1B bundle but does not explicitly verify 2A validation bundle/_passed.flag despite sealing 2A egress (site_timezones, tz_timetable_cache). Spec indicates No PASS -> No Read for civil time; implementation should enforce this if 2A outputs are present.
- Blocker risk: required policy files must exist at the dictionary paths; missing any of the required policy assets aborts S0 and blocks the entire segment.
- Critical: S5 logs site_id as sha256(merchant_id:country:site_order), but S7 audit derives site_id as (merchant_id << 32 | site_order) when validating selection logs; evidence-based audits will fail even when routing is correct because IDs never match.
- High: S0 treats site_timezones/tz_timetable_cache as required (allow_missing=False) even though the dictionary marks them optional; pin_civil_time is defined but not used to relax this, so S0 fails if civil-time assets are absent.
- Medium: S5 falls back to merchant_mcc_map under the 2B manifest if the 2A manifest path is missing; this can mask upstream mismatches and violates a strict 2A handoff contract.
- Low: S3 run report/input summary renders site_timezones paths with manifest_fingerprint instead of seg2a_manifest_fingerprint; if the manifests diverge, run reports misrepresent the actual input partition.

---

Segment 3A
- Spec scope: docs/model_spec/data-engine/layer-1/specs/state-flow/3A/* and contracts/3A/*
- Implementation scope: packages/engine/src/engine/layers/l1/seg_3A, scenario_runner/l1_seg_3A.py, CLI segment3a.py

Expected inputs (spec + contracts)
- Upstream gates: validation_bundle_1A, 1B, 2A; inputs include outlet_catalogue, site_timezones, tz_timetable_cache, iso3166, tz_world, policy/prior packs (zone_mixture_policy, country_zone_alphas, zone_floor_policy, day_effect_policy_v1).

Observed implementation
- S0 gate verifies upstream bundles for 1A/1B/2A and loads parameter_hash_resolved.json from 1A (packages/engine/src/engine/layers/l1/seg_3A/s0_gate/l2/runner.py).
- Seals policies and upstream egress inputs via dictionary resolution.
- S1 reads sealed_inputs_3A and s0 receipt, loads zone_mixture_policy + outlet_catalogue + tz_world + iso3166, and emits s1_escalation_queue (packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/l2/runner.py).
- S2 reads country_zone_alphas + zone_floor_policy + tz_world to build parameter_hash-scoped s2_country_zone_priors (packages/engine/src/engine/layers/l1/seg_3A/s2_priors/l2/runner.py).
- S3 draws Dirichlet shares for escalated pairs using Philox RNG, emits rng event + trace logs, and writes s3_zone_shares (packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/l2/runner.py).
- S4 deterministically integerises s3_zone_shares into s4_zone_counts, enforcing site_count totals (packages/engine/src/engine/layers/l1/seg_3A/s4_zone_counts/l2/runner.py).
- S5 joins s4_zone_counts with s1 mixture metadata and s3 shares to emit zone_alloc plus zone_alloc_universe_hash (packages/engine/src/engine/layers/l1/seg_3A/s5_zone_alloc/l2/runner.py).
- S6 validates s1-s4 + zone_alloc + universe hash, writes s6_validation_report_3A, s6_issue_table_3A, and s6_receipt_3A (packages/engine/src/engine/layers/l1/seg_3A/s6_validation/l2/runner.py).
- S7 assembles validation_bundle_3A from S0/S1/S2/S3/S4/S5/S6 artefacts and emits _passed.flag (packages/engine/src/engine/layers/l1/seg_3A/s7_bundle/l2/runner.py).

Handoff to 2B/3B/5B
- Outputs: zone_alloc and zone_alloc_universe_hash provide routing universe context for 2B/5A and 3B validations.

Findings
- Blocker risk: 3A S0 will hard-fail if any upstream bundle (1A/1B/2A) is missing or its flag digest does not match index. This makes 2A a strict dependency.
- Blocker risk: parameter_hash verification is anchored to 1A parameter_hash_resolved.json; any divergence between S0 parameter set and 1A manifest contents will fail the gate.
- Critical: S3 empty-escalation branch references rng_trace_path before it is assigned; when no escalations exist, S3 raises UnboundLocalError instead of emitting empty outputs.
- Medium: S5 routing_universe_hash hashes pandas.to_csv bytes of s3_zone_shares; pandas formatting differences across versions can change the hash for identical data, risking non-deterministic manifests.

---

Segment 3B
- Spec scope: docs/model_spec/data-engine/layer-1/specs/state-flow/3B/* and contracts/3B/*
- Implementation scope: packages/engine/src/engine/layers/l1/seg_3B, scenario_runner/l1_seg_3B.py, CLI segment3b.py

Expected inputs (spec + contracts)
- Upstream gates: validation bundles for 1A, 1B, 2A, 3A; inputs include site_locations, virtual merchant classification/policies, edge catalogue policies and reference assets.

Observed implementation
- S0 gate verifies upstream bundles and seals inputs per dictionary (packages/engine/src/engine/layers/l1/seg_3B/s0_gate/...).
- S1 reads merchant_ids, mcc_channel_rules, and virtual_settlement_coords to emit virtual_classification_3B + virtual_settlement_3B; missing settlement coords are filled with deterministic pseudo-coordinates to keep the pipeline moving (packages/engine/src/engine/layers/l1/seg_3B/s1_virtuals/l2/runner.py).
- S2 builds a synthetic edge catalogue (one edge per virtual merchant) and edge_catalogue_index_3B, based on settlement coords and merchant home_country_iso (packages/engine/src/engine/layers/l1/seg_3B/s2_edges/l2/runner.py).
- S3 packages edge alias blob/index using synthetic JSON slices and emits edge_universe_hash_3B (packages/engine/src/engine/layers/l1/seg_3B/s3_alias/l2/runner.py).
- S4 compiles virtual_routing_policy_3B + virtual_validation_contract_3B and writes s4_run_summary_3B (packages/engine/src/engine/layers/l1/seg_3B/s4_routing/l2/runner.py).
- S5 assembles validation_bundle_3B, s5_manifest_3B, index.json, and _passed.flag after consistency checks (packages/engine/src/engine/layers/l1/seg_3B/s5_validation/l2/runner.py).

Handoff to 2B
- Outputs: virtual_classification_3B, virtual_settlement_3B, edge_catalogue_3B, edge_alias_* and virtual routing policy are used by 2B virtual routing branch.

Findings
- Dependent on 2A and 3A gates; current failure in 2A prevents 3B from running in full pipeline.
- Compliance risk: S1 fills missing settlement coordinates with deterministic pseudo-lat/lon instead of failing; spec describes evidence-backed settlement coords, so this is a placeholder behavior that may violate strict governance expectations.
- Placeholder scope: S2/S3 emit synthetic single-edge catalogues and JSON alias blobs; these outputs will not match full routing realism expectations until replaced with the intended edge-generation logic.

---

Segment 5A
- Spec scope: docs/model_spec/data-engine/layer-2/specs/state-flow/5A/* and contracts/5A/*
- Implementation scope: packages/engine/src/engine/layers/l2/seg_5A, scenario_runner/l2_seg_5A.py, CLI segment5a.py

Expected inputs (spec + contracts)
- Upstream gates: validation bundles for 1A-3B; inputs include site_timezones, tz_timetable_cache, 2B routing surfaces, 3A zone allocation, 3B virtual surfaces; scenario policies and calendars (layer-2 contracts).

Observed implementation
- S0 gate seals upstream bundles and layer-1 artefacts explicitly via cross-segment dictionary paths, and writes sealed_inputs plus run reports (packages/engine/src/engine/layers/l2/seg_5A/s0_gate/runner.py).
 - S0 enumerates required layer-1 inputs (site_timezones, tz_timetable_cache, 2B alias artifacts, 3A zone_alloc, 3B virtual artifacts) using per-segment dictionary files. This matches the spec handoff surface list but depends on upstream gates being present.
- S1 builds merchant_zone_profile_5A plus optional merchant_class_profile_5A from merchant_class_policy_5A, demand_scale_policy_5A, transaction_schema_merchant_ids, and zone_alloc (packages/engine/src/engine/layers/l2/seg_5A/s1_profiles/runner.py).
- S2 builds shape_grid_definition_5A + merchant_zone_shapes_5A from shape_library_5A and S1 profiles (packages/engine/src/engine/layers/l2/seg_5A/s2_shapes/runner.py).
- S3 merges S1 profiles + S2 shapes with baseline_intensity_policy_5A to emit merchant_zone_baseline_local_5A, merchant_zone_baseline_class_5A, merchant_zone_baseline_utc_5A (packages/engine/src/engine/layers/l2/seg_5A/s3_baselines/runner.py).
- S4 overlays apply scenario_horizon_config_5A + scenario_overlay_policy_5A + scenario_calendar_5A, emitting merchant_zone_scenario_local_5A, merchant_zone_overlay_factors_5A, merchant_zone_scenario_utc_5A; UTC projection uses fixed offsets per tzid (packages/engine/src/engine/layers/l2/seg_5A/s4_overlays/runner.py).
- S5 validation verifies sealed_inputs digest + required outputs per scenario, writes s5_validation_report_5A, validation_bundle_index_5A, and _passed.flag (packages/engine/src/engine/layers/l2/seg_5A/s5_validation/runner.py).

Handoff to 5B/6A/6B
- Outputs include merchant_zone_* baselines and scenario overlays (manifest + parameter + scenario scoped). These feed 5B for arrivals and 6A/6B for downstream modeling.

Findings
- No run evidence in latest log due to upstream 2A failure. 5A S0 expects upstream bundles to exist for 1A-3B; any missing gate will block.
- Spec alignment risk: S4 UTC projection uses a fixed tz offset snapshot (zoneinfo at 2025-01-01) rather than tz_timetable_cache; DST/offset changes across horizon are not represented.

---

Segment 5B
- Spec scope: docs/model_spec/data-engine/layer-2/specs/state-flow/5B/* and contracts/5B/*
- Implementation scope: packages/engine/src/engine/layers/l2/seg_5B, scenario_runner/l2_seg_5B.py, CLI segment5b.py

Expected inputs (spec + contracts)
- Upstream gates: validation bundles for 1A-3B and 5A; inputs include 5A scenario baselines and 2B routing surfaces, plus 2A civil time.

Observed implementation
- 5B S0 explicitly verifies upstream bundles for 1A-3B and 5A before sealing upstream datasets and policies (packages/engine/src/engine/layers/l2/seg_5B/s0_gate/runner.py).
- S1 builds scenario time grids (s1_time_grid_5B) and deterministic groupings (s1_grouping_5B) using time_grid_policy_5B, grouping_policy_5B, merchant_zone_scenario_local_5A, and virtual_classification_3B (packages/engine/src/engine/layers/l2/seg_5B/s1_time_grid/runner.py).
- S2 realises intensities by sampling latent LGCP factors from arrival_lgcp_config_5B and applying them to merchant_zone_scenario_local_5A; emits s2_realised_intensity_5B and optional s2_latent_field_5B with RNG logs (packages/engine/src/engine/layers/l2/seg_5B/s2_intensity/runner.py).
- S3 converts realised intensities to counts using arrival_count_config_5B, parallel row-group processing, and RNG logs; emits s3_bucket_counts_5B (packages/engine/src/engine/layers/l2/seg_5B/s3_counts/runner.py).
- S4 synthesises arrival_events_5B and s4_arrival_summary_5B by joining counts, time grid, and routing surfaces (s1_site_weights, s4_group_weights, edge_alias_index/blob, virtual_settlement_3B) (packages/engine/src/engine/layers/l2/seg_5B/s4_arrivals/runner.py).
- S5 validation checks bundle integrity, routing consistency, civil-time conversions, RNG accounting, and count/time window matching; writes s5_validation_report_5B, validation_bundle_index_5B, and _passed.flag (packages/engine/src/engine/layers/l2/seg_5B/s5_validation/runner.py).

Handoff to 6B
- Outputs: arrival_events_5B and validation bundle + _passed.flag are required for 6B behavior synthesis.

Findings
- Critical: 5B S4 indentation error exits the scenario loop early; the bulk of S4 processing runs once outside the loop, using only the final scenario’s inputs and emitting arrivals for at most one scenario (packages/engine/src/engine/layers/l2/seg_5B/s4_arrivals/runner.py:181-210).
- High: 5B S2 rejects latent_model_id=none (default when missing), raising ValueError. If arrival_lgcp_config_5B omits latent_model_id, S2 hard-fails (packages/engine/src/engine/layers/l2/seg_5B/s2_intensity/runner.py:142-149).
- Medium: S4 relies on edge_alias_blob_3B and edge_alias_index_3B for virtual routing and loads the entire blob into memory; large routing universes may stress memory and violate the “stream large artefacts” doctrine.

---

Segment 6A
- Spec scope: docs/model_spec/data-engine/layer-3/specs/state-flow/6A/* and contracts/6A/*
- Implementation scope: packages/engine/src/engine/layers/l3/seg_6A, scenario_runner/l3_seg_6A.py, CLI segment6a.py

Expected inputs (spec + contracts)
- Upstream gates: validation bundles for 1A-3B, 5A, 5B; inputs include outlet_catalogue, site_locations, site_timezones, zone_alloc, virtual_* (per 6A S0 spec and contracts).

Observed implementation
- 6A S0 gate explicitly verifies upstream bundles for 1A-3B and 5A/5B and seals upstream egress surfaces (packages/engine/src/engine/layers/l3/seg_6A/s0_gate/runner.py).
 - 6A S0 seals outlet_catalogue, site_locations, site_timezones, zone_alloc, virtual_* datasets as read-authorised inputs for later 6A states.
- S1 generates s1_party_base_6A and s1_party_summary_6A from population/segmentation priors and outlet/arrival country hints (packages/engine/src/engine/layers/l3/seg_6A/s1_parties/runner.py).
- S2 builds s2_account_base_6A and s2_party_product_holdings_6A (plus summaries), using account/product mix priors and deterministic per-party weighting (packages/engine/src/engine/layers/l3/seg_6A/s2_accounts/runner.py).
- S3 emits s3_instrument_base_6A, s3_account_instrument_links_6A, s3_party_instrument_holdings_6A, s3_instrument_summary_6A; current logic creates one instrument per eligible account using the first instrument type + scheme (packages/engine/src/engine/layers/l3/seg_6A/s3_instruments/runner.py).
- S4 builds device/ip bases + link graphs (s4_device_base_6A, s4_ip_base_6A, s4_device_links_6A, s4_ip_links_6A) and optional summaries (packages/engine/src/engine/layers/l3/seg_6A/s4_network/runner.py).
- S5 assigns fraud roles for parties/accounts/merchants/devices/IPs and writes validation bundle artifacts + _passed.flag when outputs are present (packages/engine/src/engine/layers/l3/seg_6A/s5_validation/runner.py).

Handoff to 6B
- Outputs (party, account, instrument, device/ip graph, fraud posture, 6A validation bundle) are required for 6B behavioral synthesis.

Findings
- No runtime evidence yet; upstream 2A failure blocks earlier layers.
- Spec alignment risk: 6A S4 does not use graph_linkage_rules_6A; only device_linkage_rules_6A (max devices per party) influences counts. Spec-specified linkage constraints are currently ignored.

---

Segment 6B
- Spec scope: docs/model_spec/data-engine/layer-3/specs/state-flow/6B/* and contracts/6B/*
- Implementation scope: packages/engine/src/engine/layers/l3/seg_6B, scenario_runner/l3_seg_6B.py, CLI segment6b.py

Expected inputs (spec + contracts)
- Upstream gates: 1A-3B, 5A, 5B, 6A validation bundles; inputs include arrival_events_5B and 6A entity graph and fraud posture.

Observed implementation
- 6B S0 gate and subsequent states are implemented under packages/engine/src/engine/layers/l3/seg_6B (not exercised in latest run due to upstream failures).
 - 6B S0 verifies bundles for 1A-5B and 6A, then seals upstream datasets (arrival_events_5B, entity graph surfaces) for behavioral synthesis (packages/engine/src/engine/layers/l3/seg_6B/s0_gate/runner.py).
- S1 attaches entities and session IDs to arrival_events_5B, emitting s1_arrival_entities_6B and s1_session_index_6B (packages/engine/src/engine/layers/l3/seg_6B/s1_arrivals/runner.py).
- S2 generates baseline flow anchors and event streams from S1 arrivals; only amount_model_6B bounds are used (packages/engine/src/engine/layers/l3/seg_6B/s2_baseline/runner.py).
- S3 overlays fraud on flows/events using fraud_overlay_policy_6B + fraud_campaign_catalogue_config_6B; emits campaign catalogue and fraud-enriched streams (packages/engine/src/engine/layers/l3/seg_6B/s3_fraud/runner.py).
- S4 generates truth/bank-view labels and case timelines from S3 outputs, with detection_rate derived from bank_view_policy_6B (packages/engine/src/engine/layers/l3/seg_6B/s4_labels/runner.py).
- S5 validates presence of all S1-S4 outputs per scenario and writes the validation bundle + _passed.flag (packages/engine/src/engine/layers/l3/seg_6B/s5_validation/runner.py).

Findings
- Critical: 6B S5 uses Path.exists() on dataset paths that include part-*.parquet, so it will always report missing outputs even when files exist (packages/engine/src/engine/layers/l3/seg_6B/s5_validation/runner.py:41-95). This makes 6B validation fail deterministically.
- Critical: 6B S4 only writes s4_case_timeline_6B if any bank_hit occurs; with zero detected fraud (or no fraud flows), required case timeline outputs are missing and S5 fails (packages/engine/src/engine/layers/l3/seg_6B/s4_labels/runner.py:74-179).
- High: 6B S1 ignores attachment_policy_6B and sessionisation_policy_6B, using a fixed arrival_seq//10 session rule and uniform attachment across entities; this diverges from the policy-driven contracts and can invalidate expected downstream distributions (packages/engine/src/engine/layers/l3/seg_6B/s1_arrivals/runner.py).
- High: 6B S2 ignores flow_shape_policy_6B, timing_policy_6B, flow_rng_policy_6B, and rng_profile_layer3; only amount_model_6B is used (packages/engine/src/engine/layers/l3/seg_6B/s2_baseline/runner.py).
- High: 6B S3 ignores fraud_rng_policy_6B and most fraud_campaign_catalogue_config_6B fields; fraud overlays are a single-rate toggle, not the specified campaign model (packages/engine/src/engine/layers/l3/seg_6B/s3_fraud/runner.py).
- Medium: 6B S0 seals arrival_events_5B with read_scope=METADATA_ONLY even though S1 reads row-level arrivals; this conflicts with the read-scope contract and audit expectations (packages/engine/src/engine/layers/l3/seg_6B/s0_gate/runner.py).

---

Cross-segment failure map (run logs + implementation blockers)
- Run local_full_run-3 fails in Segment2A S0: dataset 'validation_bundle_1A' not present in Segment 2A dictionary (2A-S0-012), then FrozenInstanceError masks traceback (runs/local_full_run-3/run_log_run-3.log:10114-10134).
- 1B S7/S8 run summary paths are written outside fingerprint/parameter_hash partitions, diverging from dictionary contracts (run log shows s8_run_summary.json under seed-only path).
- 1A S2/S4 validation artifact publishing skips because validation bundle path resolves to a non-existent directory; likely dictionary/path mismatch.
- 3A S3 empty-escalation branch throws UnboundLocalError (rng_trace_path referenced before assignment), so runs with zero escalations fail even if upstream data is valid.
- 2B S7 evidence validation will always fail when selection logs are provided because site_id hashing in S5 and S7 is inconsistent.
- 5B S4 indentation bug runs S4 outside the scenario loop, producing outputs only for the final scenario (if any).
- 6B S5 uses glob paths with Path.exists(), so required datasets that are partitioned as part-*.parquet are always flagged missing.

Prioritized fix list (no code changes in this audit)
- Fix 2A S0 dictionary mismatch: either add validation_bundle_1A to 2A dictionary or remove 1A bundle resolution from 2A S0 (align with 2A spec).
- Make S0GateError mutable or avoid frozen dataclass so exception handling does not raise FrozenInstanceError.
- Align 1B run summary paths (S7/S8) with dictionary partitions (include fingerprint and parameter_hash).
- Resolve 1A validation bundle path mismatch for S2/S4 artifact publishing; ensure validation bundle exists where publishers expect it.
- Fix 3A S3 empty-escalation branch to define rng_trace_path before use so empty runs do not crash.
- Align 2B S7 site_id derivation with S5 hashing (or change S5 to use the S7 convention) to make audit evidence verifiable.
- Decide whether 2B S0 should enforce optional civil-time assets based on pin_civil_time; align implementation with dictionary optionality.
- Remove or tighten 2B S5 merchant_mcc_map fallback to the 2B manifest so 2A handoff violations surface explicitly.
- Stabilize 3A S5 routing_universe_hash serialization to avoid pandas-version drift (e.g., use a fixed-format writer).
- Fix 5B S4 indentation to ensure scenario processing loop wraps the arrival synthesis logic (s4_arrivals runner).
- Require arrival_lgcp_config_5B to set latent_model_id explicitly (or handle "none" without raising) to avoid S2 hard-failures.
- Update 6B S5 to handle part-*.parquet outputs (glob/scan) rather than Path.exists(), or write non-wildcard outputs.
- Ensure 6B S4 writes empty s4_case_timeline_6B outputs when no cases exist so validation can pass.
