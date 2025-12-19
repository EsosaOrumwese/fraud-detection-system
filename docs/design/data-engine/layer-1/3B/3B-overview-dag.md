```
                  LAYER 1 · SEGMENT 3B (Virtual Merchants & CDN Edge World)

Authoritative inputs (sealed by 3B.S0)
--------------------------------------
[V] Upstream segments & HashGates (must be PASS for this manifest_fingerprint):
    - 1A/1B/2A/3A validation bundles + `_passed.flag_*`
      · 3B never reads their rows at S0; it only verifies their bundles and flags.

[D] Upstream data-plane surfaces (read-only in 3B):
    - Merchant reference (canonical merchant universe)
    - outlet_catalogue            (1A: merchant×country×site stubs)
    - site_locations              (1B: per-site lat/lon; for cross-checks)
    - site_timezones              (2A: per-site tzid)
    - tz_timetable_cache, civil_time_manifest (2A: tz polygons/db/index)
    - zone_alloc / zone_alloc_universe_hash (3A; referenced for universe coherence)

[P] 3B policies, priors & external assets:
    - Virtual rules:           `mcc_channel_rules`       (which merchants count as “virtual”)
    - Settlement coords:       `virtual_settlement_coords` (candidate settlement lat/lon per brand/merchant)
    - CDN country mix:         `cdn_country_weights` (+ external CDN weights YAML if used)
    - Spatial surfaces:        HRSL raster, tile_index/tile_weights
    - Tz assets:               tz_world polygons, tzdb archive, tz overrides/index (via civil_time_manifest)
    - Alias layout policy:     layout_version, grid size, endianness, alignment, checksum rules
    - Routing/RNG policy:      which Philox streams/substreams 2B must use for virtual `cdn_edge_pick`
    - Virtual validation policy:  test types, thresholds, scopes for virtual/CDN behaviour

[N] Identity & numeric/RNG posture:
    - Identity triple:  { seed, parameter_hash, manifest_fingerprint }
    - Numeric:          IEEE-754 binary64, round-to-nearest-even, FMA/FTZ/DAZ off on decision paths
    - RNG:
        · Only 3B.S2 consumes RNG (edge jitter),
        · 3B.S0/S1/S3/S4/S5 are RNG-free.


DAG
---
(M,D,P,N) --> (S0) Gate & sealed inputs for 3B          [NO RNG]
                    - Verify upstream HashGates (1A/1B/2A/3A bundles + flags) for this manifest_fingerprint.
                    - Resolve all 3B-relevant external artefacts:
                        · merchant ref, outlet_catalogue, site_timezones, tz assets,
                          virtual rules, settlement coords, CDN weights, HRSL raster,
                          alias layout policy, routing/RNG policy, virtual validation policy, etc.
                    - Compute SHA-256 over each, build the closed input set SEALED.
                    - Emit:
                        · `s0_gate_receipt_3B@fingerprint`:
                              identity triple,
                              upstream_gates.{1A,1B,2A,3A}.status/digests,
                              sealed_policy_set, catalogue_versions.
                        · `sealed_inputs_3B@fingerprint`:
                              one row per sealed artefact with {owner_segment, logical_id, path, schema_ref, sha256_hex, role}.
                    - S0 is RNG-free; defines “what world 3B is allowed to see”.

                                      |
                                      | s0_gate_receipt_3B, sealed_inputs_3B
                                      v

        (S1) Virtual classification & settlement node         [NO RNG]
             inputs: merchant reference, `mcc_channel_rules`,
                     `virtual_settlement_coords`, tz assets (via civil_time_manifest)
             -> virtual_classification_3B@ [seed, fingerprint]
                  - Apply overrides + MCC/channel/country rules to classify each merchant:
                        classification ∈ {VIRTUAL, NON_VIRTUAL},
                        decision_reason (closed code per rule/default).
                  - This is the **only authority** on which merchants are virtual.

             -> virtual_settlement_3B@ [seed, fingerprint]
                  - For virtual merchants only:
                        · pick one settlement coord row per merchant (deterministic tie-break),
                        · resolve `tzid_settlement` using either ingested tzid or tz polygons/tzdb,
                        · construct a `settlement_site_id` per merchant (hash-based id64),
                        · record tz_source (“INGESTED”, “POLYGON”, “OVERRIDE”), coord_source_id/version, evidence/jurisdiction.
                  - This is the **legal settlement anchor** per virtual merchant.

                                      |
                                      | virtual_classification_3B, virtual_settlement_3B
                                      v

        (S2) CDN edge catalogue construction                 [RNG-BOUNDED]
             inputs: virtual_classification_3B (virtual set V),
                     virtual_settlement_3B (settlement nodes),
                     CDN weights policy, tiling surfaces, HRSL raster,
                     tz assets (tz_world/tzdb/overrides), 3B RNG/routing policy
             -> edge_catalogue_3B@ [seed, fingerprint]
                  - For each virtual merchant m:
                        · decide total edge budget E_clipped(m) from CDN policy,
                        · split that budget across countries C_m with integerisation on country weights,
                        · within each (m,c), split across tiles T_c using tile_weights (HRSL-based),
                        · within each tile, use Philox RNG to jitter edge nodes (lon,lat) inside the tile/country,
                        · resolve `tzid_operational` for each edge via tz polygons/db,
                        · assign `edge_id`, `edge_seq_index`, `edge_weight`, and per-edge digest.
                  - One row per edge with:
                        merchant_id, edge_id,
                        country_iso, lat_deg, lon_deg,
                        tzid_operational, tz_source,
                        edge_weight, RNG/spatial provenance.

             -> edge_catalogue_index_3B@ [seed, fingerprint]
                  - MERCHANT rows:
                        edge_count_total(m), per-merchant edge_digest, optional country_mix_summary.
                  - GLOBAL row:
                        edge_count_total_all_merchants,
                        edge_catalogue_digest_global (digest over whole edge universe).
                  - Used later for alias sanity + edge universe hash.

             RNG outputs:
             -> rng_event_edge_* + rng_trace_log/audit_log   (RNG accounting for jitter)

                                      |
                                      | edge_catalogue_3B, edge_catalogue_index_3B
                                      v

        (S3) Edge alias tables & virtual edge universe hash   [NO RNG]
             inputs: edge_catalogue_3B, edge_catalogue_index_3B,
                     alias-layout policy, CDN weights artefact(s),
                     virtual rules policy, RNG/routing policy
             -> edge_alias_blob_3B@ [seed, fingerprint]
                  - Packs per-merchant alias tables into a single binary blob:
                        header: layout_version, endianness, alignment_bytes,
                                blob_length_bytes, blob_sha256_hex,
                                alias_layout_policy_id/version,
                                universe_hash (filled after digest step).
                        payload: concatenated per-merchant alias segments.
                  - No RNG here; pure encoding.

             -> edge_alias_index_3B@ [seed, fingerprint]
                  - MERCHANT rows:
                        merchant_id, blob_offset_bytes, blob_length_bytes,
                        edge_count_total, alias_table_length,
                        merchant_alias_checksum, alias_layout_version,
                        universe_hash (filled later), blob_sha256_hex.
                  - GLOBAL row:
                        edge_count_total_all_merchants, blob_length_bytes, blob_sha256_hex,
                        edge_catalogue_digest_global.

             -> edge_universe_hash_3B@ [fingerprint]
                  - Computes component digests:
                        cdn_weights_digest,
                        edge_catalogue_index_digest,
                        edge_alias_index_digest,
                        virtual_rules_digest.
                  - Combines them into a single `universe_hash`, writes:
                        manifest_fingerprint, parameter_hash,
                        those component digests, universe_hash.

             -> gamma_draw_log_3B@ [seed, fingerprint]
                  - Exists as an **empty** proof-of-no-RNG-used log.
                  - Any records here would be a contract violation (S3 must be RNG-free).

                                      |
                                      | virtual_classification_3B, virtual_settlement_3B,
                                      | edge_catalogue_* and alias_*,
                                      | edge_universe_hash_3B, RNG/routing policy, validation policy
                                      v

        (S4) Virtual routing semantics & validation contracts [NO RNG]
             inputs: S1 outputs (virtual universe),
                     S2/S3 outputs (edge universe + alias + edge_universe_hash),
                     routing/RNG policy (shared with 2B),
                     virtual_validation_policy_3B,
                     event schema/routing-field contracts
             -> virtual_routing_policy_3B@ [fingerprint]
                  - Identity & provenance:
                        manifest_fingerprint, parameter_hash,
                        edge_universe_hash, routing_policy_id/version,
                        virtual_validation_policy_id/version, alias_layout_version, cdn_key_digest.
                  - Dual-TZ semantics:
                        defines which event fields carry “settlement” time vs “operational” (edge) time,
                        and how days/cutoffs are interpreted for each.
                  - Geo field bindings:
                        maps event IP fields (ip_country, ip_lat, ip_lon) to:
                              edge_catalogue_3B fields and/or settlement fields.
                  - Artefact references:
                        points to edge_catalogue_index, alias blob/index, edge_universe_hash via manifest_keys.
                  - RNG/alias binding:
                        specifies the RNG stream/substream and alias layout 2B MUST use for `cdn_edge_pick`.
                  - Optional per-merchant overrides (e.g. hybrid or “disable virtual” modes).

             -> virtual_validation_contract_3B@ [fingerprint]
                  - Expands virtual_validation_policy_3B into concrete tests:
                        test_id, test_type (IP_COUNTRY_MIX, EDGE_USAGE_VS_WEIGHT, CUT-OFF, etc.),
                        scope (GLOBAL / PER_MERCHANT / PER_CLASS / PER_SCENARIO),
                        target_population (virtual merchants, classes, cohorts),
                        inputs.datasets & inputs.fields (event schema anchors),
                        thresholds (max_abs_error, max_rel_error, KL, coverage thresholds),
                        severity (BLOCKING / WARNING / INFO),
                        enabled/profile flags.
                  - This is the manifest of **what tests to run** against virtual flows.

             -> optional s4_run_summary_3B@ [fingerprint] (informative only)

                                      |
                                      | s0_gate_receipt_3B, sealed_inputs_3B,
                                      | S1–S4 artefacts, RNG logs
                                      v

        (S5) 3B validation bundle & `_passed.flag_3B`         [NO RNG]
             inputs: S0/S1/S2/S3/S4 artefacts,
                     sealed_inputs_3B, RNG logs, policies, refs
             -> validation_bundle_3B@ [fingerprint]/index.json
                  - Stages a directory of evidence:
                        S0 gate + sealed_inputs,
                        S1–S4 key datasets,
                        edge_universe_hash_3B,
                        RNG-accounting summaries for S2,
                        virtual_routing_policy_3B,
                        virtual_validation_contract_3B,
                        S5’s own structural-check summaries.
                  - Builds `index.json`:
                        files: [{path, sha256_hex}] for every evidence file (excluding `_passed.flag_3B`),
                        sorted by path,
                        validated against `validation_bundle_index_3B` schema.

             -> `_passed.flag_3B`@ [fingerprint]
                  - Recomputes `bundle_sha256 = SHA256(concat(all indexed-file bytes in path order))`.
                  - Writes single-line text:
                        `sha256_hex = <bundle_sha256>`.
                  - `index.json` + `_passed.flag_3B` form the 3B HashGate.

             -> optional s5_manifest_3B@ [fingerprint] (informative map of key digests)

Downstream obligations
----------------------
- Any consumer of **3B artefacts** (virtual_classification_3B, virtual_settlement_3B, edge_catalogue_3B,
  edge_alias_blob_3B, edge_universe_hash_3B, virtual_routing_policy_3B, virtual_validation_contract_3B) MUST:

    1. Load `validation_bundle_3B/index.json` for the manifest_fingerprint.
    2. Recompute `bundle_sha256` from indexed file bytes.
    3. Load `_passed.flag_3B` and ensure it says `sha256_hex = <bundle_sha256>`.
    4. Only then treat 3B surfaces as valid.

- In short:

      **No 3B PASS (bundle + flag) → No read / use** of virtual merchant or edge artefacts.

Legend
------
(Sx) = state
[seed, fingerprint]   = run-scoped partitions
[parameter_hash]      = parameter-scoped partitions
[fingerprint]         = manifest-scoped partitions
[NO RNG]              = state consumes no RNG
[RNG-BOUNDED]         = state uses governed Philox with explicit RNG logs
HashGate (3B)         = validation_bundle_3B@fingerprint + `_passed.flag_3B`
```