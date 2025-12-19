```
        LAYER 1 · SEGMENT 3B — STATE S0 (GATE & ENVIRONMENT SEAL)  [NO RNG]

Authoritative inputs (read-only at S0 entry)
--------------------------------------------
[Identity & governance]
    - Layer-1 run identity triple (supplied by driver):
        · seed                (Layer-1 Philox seed, uint64)
        · parameter_hash      (hash over governed 3B parameter set, hex64)
        · manifest_fingerprint (Layer-1 manifest fingerprint, hex64)
    - schemas.layer1.yaml
        · numeric policy profile (rounding, FMA/FTZ/DAZ rules)
        · RNG algorithm + envelope (Philox config, RNG event shapes, trace layout)
    - schemas.ingress.layer1.yaml
    - schemas.3B.yaml
        · validation shapes for:
            - s0_gate_receipt_3B,
            - sealed_inputs_3B.

[3B catalogues]
    - dataset_dictionary.layer1.3B.yaml
        · IDs, paths, partitions, schema_refs for all 3B datasets (s0_gate_receipt_3B, sealed_inputs_3B, S1–S5 artefacts).
    - artefact_registry_3B.yaml
        · logical artefact entries for 3B configs, external assets, and upstream gates.

[Upstream HashGates (PASS gates 1A/1B/2A/3A)]
    - validation_bundle_1A + _passed.flag_1A
      @ data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
    - validation_bundle_1B + _passed.flag_1B
      @ data/layer1/1B/validation/fingerprint={manifest_fingerprint}/
    - validation_bundle_2A + _passed.flag_2A
      @ data/layer1/2A/validation/fingerprint={manifest_fingerprint}/
    - validation_bundle_3A + _passed.flag_3A
      @ data/layer1/3A/validation/fingerprint={manifest_fingerprint}/
    - S0 treats these as **gates only**:
        · verifies their internal bundle_hash ↔ flag,
        · never reads their data-plane rows.

[Upstream egress datasets for 3B (metadata-only in S0)]
    - outlet_catalogue        (1A) @ seed={seed}, fingerprint={manifest_fingerprint}
    - site_locations          (1B) @ seed={seed}, fingerprint={manifest_fingerprint}
    - site_timezones          (2A) @ seed={seed}, fingerprint={manifest_fingerprint}
    - tz_timetable_cache      (2A) @ fingerprint={manifest_fingerprint}
    - zone_alloc              (3A) @ seed={seed}, fingerprint={manifest_fingerprint}
    - zone_alloc_universe_hash (3A) @ fingerprint={manifest_fingerprint}
    - In S0:
        · S0 checks presence, type, and digests,
        · DOES NOT read rows (pure metadata / existence / digest).

[Ingress / external artefacts S0 must seal for 3B]
    - Virtual classification rules:
        · mcc_channel_rules @ config/virtual/mcc_channel_rules.yaml
          (logical_id ≈ "virtual_rules" / manifest_key mlr.3B.config.virtual_rules)
    - Virtual settlement coordinate sources:
        · virtual_settlement_coords @ artefacts/virtual/virtual_settlement_coords.csv (or parquet)
    - CDN country mix policy:
        · cdn_country_weights @ config/virtual/cdn_country_weights.yaml
          + external base weights cdn_weights_ext_yaml
    - Validation policy packs:
        · virtual_validation_config @ config/virtual/virtual_validation.yaml
          (tolerances for virtual/CDN behaviour)
    - Civil-time manifest for tz provenance:
        · civil_time_manifest (2A-level roll-up of tz polygons / tzdb / overrides / tz_index)
    - Geospatial & tz assets (transitively used by S1–S3):
        · hrsl_raster (HRSL population tiles),
        · pelias_cached_bundle_v1 (Pelias geocoder DB),
        · tz_world_2025a and related tz polygons/index (via 2A’s civil_time_manifest),
        · any tzdata archives / tz_index digests listed in artefact_registry_3B.
    - RNG / routing profile:
        · rng_policy / routing_rng_profile_3B (RNG/routing envelope config used later by 3B + 2B).

[Outputs owned by S0]
    - s0_gate_receipt_3B
      @ data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json
      · partition_keys: [fingerprint]
      · schema_ref: schemas.3B.yaml#/validation/s0_gate_receipt_3B
      · fields (min):
            segment_id="3B", state_id="S0",
            seed, parameter_hash, manifest_fingerprint, verified_at_utc,
            upstream_gates.{segment_1A,1B,2A,3A}.{bundle_path, flag_path, sha256_hex, status},
            catalogue_versions.{schemas_3B,dataset_dictionary_3B,artefact_registry_3B},
            sealed_input_count_total, sealed_input_count_by_kind,
            optional sealed_inputs_sha256 / gate_receipt_sha256,
            status="PASS" | "FAIL" (state-level).
    - sealed_inputs_3B
      @ data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet
      · partition_keys: [fingerprint]
      · ordering: [owner_segment, artefact_kind, logical_id, path]
      · schema_ref: schemas.3B.yaml#/validation/sealed_inputs_3B
      · each row:
            owner_segment, artefact_kind, logical_id,
            path, schema_ref, sha256_hex, role.

[Numeric & RNG posture]
    - S0 is strictly **RNG-free**:
        · MUST NOT open or advance any Philox stream,
        · MUST NOT emit any rng_event (including cdn_edge_pick),
        · MUST NOT use wall-clock (verified_at_utc must be derived deterministically or provided by harness).
    - Determinism & idempotence:
        · given the same identity triple + catalogues + upstream bundles + ingress artefacts,
          S0 MUST always produce byte-identical s0_gate_receipt_3B + sealed_inputs_3B.
    - Partitioning & immutability:
        · outputs are fingerprint-only; one pair per manifest_fingerprint,
        · if outputs exist and differ → FATAL inconsistency; S0 MUST NOT overwrite.


----------------------------------------------------------------------
DAG — 3B.S0 (Upstream HashGates & ingress → sealed inputs & gate receipt)  [NO RNG]

[Identity & governance],
schemas.layer1.yaml,
schemas.3B.yaml
                ->  (S0.1) Identity & governance check (Phase A)
                    - Inputs:
                        · seed, parameter_hash, manifest_fingerprint.
                    - Validate formats:
                        · seed is valid Layer-1 seed type,
                        · parameter_hash, manifest_fingerprint conform to Layer-1 hash format (hex64).
                    - Load governance blocks from schemas.layer1.yaml:
                        · numeric_policy_profile,
                        · rng_profile (algorithm, envelope shape).
                    - Assert:
                        · active numeric profile = layer-wide profile,
                        · active RNG profile = layer-wide Philox profile (even though S0 will not use RNG).
                    - On any mismatch:
                        · treat as FATAL configuration error,
                        · DO NOT proceed to upstream gate verification or write any S0 outputs.

[Schema+Dict],
[S0 identity triple]
                ->  (S0.2) Load 3B catalogues & version coherence (Phase C: part 1)
                    - Resolve 3B catalogues via registry:
                        · schemas.3B.yaml,
                        · dataset_dictionary.layer1.3B.yaml,
                        · artefact_registry_3B.yaml.
                    - Validate:
                        · schemas.3B.yaml is schema-valid,
                        · dictionary & registry parse correctly and are mutually consistent:
                              - every dataset_id in dictionary has a matching artefact entry (where required),
                              - schema_ref anchors resolve into schemas.3B.yaml.
                    - Extract version identifiers:
                        · catalogue_versions = {schemas_3B, dataset_dictionary_3B, artefact_registry_3B}.
                    - If any incompatibility is detected:
                        · FATAL → S0 MUST NOT emit s0_gate_receipt_3B nor sealed_inputs_3B.

[Upstream HashGates],
dataset_dictionary.layer1.*,
artefact_registry_*,
schemas.layer1.yaml
                ->  (S0.3) Verify upstream segment PASS gates (Phase B)
                    - For each upstream segment seg ∈ {1A,1B,2A,3A}:
                        1. Use that segment’s dictionary + registry to resolve:
                               validation_bundle_seg@fingerprint={manifest_fingerprint},
                               passed_flag_seg@fingerprint={manifest_fingerprint}.
                        2. Open passed_flag_seg and parse expected bundle digest:
                               `sha256_hex = <digest_hex>`.
                        3. Call a shared HashGate routine on validation_bundle_seg:
                               - reconstruct bundle index,
                               - compute SHA-256 over canonical representation (per that segment’s bundle law),
                               - obtain recomputed_digest_seg.
                        4. Require:
                               recomputed_digest_seg == <digest_hex>,
                               status for seg in `upstream_gates` = "PASS".
                    - If any segment fails HashGate verification:
                        · S0 MUST fail with FATAL upstream-gate error,
                        · MUST NOT treat upstream egress as readable.

[S0 identity triple],
[Upstream egress dataset IDs],
dataset_dictionary.layer1.*,
artefact_registry_*
                ->  (S0.4) Resolve upstream egress as metadata-only inputs
                    - For each required upstream dataset listed in §2.4:
                        · outlet_catalogue@seed={seed},fingerprint={manifest_fingerprint},
                        · site_locations@seed={seed},fingerprint={manifest_fingerprint},
                        · site_timezones@seed={seed},fingerprint={manifest_fingerprint},
                        · tz_timetable_cache@fingerprint={manifest_fingerprint},
                        · zone_alloc@seed={seed},fingerprint={manifest_fingerprint},
                        · zone_alloc_universe_hash@fingerprint={manifest_fingerprint},
                      S0 MUST:
                        1. Resolve `logical_id` → {owner_segment, path, schema_ref} via dictionary+registry.
                        2. Verify the file/directory exists and is readable.
                        3. Compute or verify SHA-256(raw bytes) → sha256_hex.
                    - S0 MUST NOT:
                        · read any rows from these datasets,
                        · treat any column values as business inputs (metadata-only at S0).

[Ingress / external artefacts for 3B],
dataset_dictionary.layer1.3B.yaml,
artefact_registry_3B.yaml
                ->  (S0.5) Resolve and hash ingress / external configs (Phase D: part 1)
                    - For each ingress artefact defined for 3B:
                        · mcc_channel_rules (virtual classification rules),
                        · virtual_settlement_coords,
                        · cdn_country_weights (internal wrapper) + cdn_weights_ext_yaml (external),
                        · virtual_validation_config (virtual/CDN validation policy),
                        · hrsl_raster,
                        · pelias_cached_bundle_v1 (Pelias geocoder DB),
                        · civil_time_manifest (2A tz roll-up),
                        · rng_policy / routing_rng_profile_3B,
                        · any other ingress assets explicitly referenced by S1–S5 specs,
                      S0 MUST:
                        1. Resolve logical_id → {owner_segment, path, schema_ref?, artefact_kind} via dictionary+registry.
                        2. Open the artefact bytes (dataset, YAML, CSV, Parquet, SQLite, etc.).
                        3. Compute SHA-256(raw bytes) → sha256_hex.
                    - S0 MUST record, per artefact:
                        · {owner_segment, artefact_kind, logical_id, path, schema_ref, sha256_hex, role}.

[s0_gate_receipt_3B.sealed_policy_set],
sealed_inputs_3B expectations,
all artefacts above
                ->  (S0.6) Build SEALED set (all artefacts to be sealed) (Phase D: part 2)
                    - Construct an in-memory collection SEALED that includes at least:
                        · all upstream validation bundles + PASS flags for 1A,1B,2A,3A,
                        · all upstream egress datasets required in 3B (outlet_catalogue, site_locations, site_timezones,
                          tz_timetable_cache, zone_alloc, zone_alloc_universe_hash),
                        · all 3B ingress / external artefacts:
                              - mcc_channel_rules, virtual_settlement_coords, cdn_country_weights (+ext),
                                virtual_validation_config, hrsl_raster, pelias bundle, civil_time_manifest, rng_policy, etc.,
                        · any 3B-local schemas/policies/RNG profiles prescribed by S1–S5 specs.
                    - For each artefact a ∈ SEALED, S0 MUST have:
                        · resolved {owner_segment, artefact_kind, logical_id, path, schema_ref},
                        · computed sha256_hex over bytes.
                    - SEALED defines the **closed input universe** for 3B:
                        · any artefact S1–S5 will ever read MUST be in SEALED.

SEALED
                ->  (S0.7) Derive sealed_inputs_3B rows (Phase D: part 3)
                    - For each artefact a ∈ SEALED, construct a row:
                        · owner_segment     (e.g. "1A","2A","3A","3B"),
                        · artefact_kind     ∈ {"dataset","policy","schema","rng_profile","external"},
                        · logical_id        (dictionary/registry ID),
                        · path              (canonical, including partition tokens),
                        · schema_ref        (nullable for non-schema’d assets),
                        · sha256_hex        (from S0.4–S0.5),
                        · role              (short descriptor: "upstream_gate", "upstream_egress", "virtual_rules",
                                             "virtual_coords", "cdn_weights", "tz_rollup", "rng_profile", etc.).
                    - Collect into a table; compute summary stats:
                        · sealed_input_count_total = |SEALED|,
                        · sealed_input_count_by_kind = counts by artefact_kind.
                    - Sort rows deterministically by:
                        · owner_segment, then artefact_kind, then logical_id, then path.

[S0 identity triple],
catalogue_versions,
SEALED summary
                ->  (S0.8) Construct s0_gate_receipt_3B JSON (Phase E: part 1)
                    - Construct object conforming to schemas.3B.yaml#/validation/s0_gate_receipt_3B:
                        · segment_id          = "3B",
                          state_id            = "S0",
                          seed                = seed,
                          parameter_hash      = parameter_hash,
                          manifest_fingerprint= manifest_fingerprint,
                          verified_at_utc     = (deterministic or harness-supplied timestamp),
                        · upstream_gates      = {
                              segment_1A: {bundle_path, flag_path, sha256_hex, status="PASS"},
                              segment_1B: { ... },
                              segment_2A: { ... },
                              segment_3A: { ... }
                          },
                        · catalogue_versions = {schemas_3B, dataset_dictionary_3B, artefact_registry_3B},
                        · sealed_input_count_total,
                        · sealed_input_count_by_kind,
                        · optionally:
                              sealed_inputs_sha256     (digest over sealed_inputs_3B as written),
                              gate_receipt_sha256      (digest over this JSON).
                    - S0 sets status="PASS" iff all Acceptance Criteria in §8.1 are met; otherwise status="FAIL".

rows for sealed_inputs_3B,
[Schema+Dict]
                ->  (S0.9) Write sealed_inputs_3B (fingerprint-only, write-once) (Phase E: part 2)
                    - Target path (via dictionary entry `sealed_inputs_3B`):
                        · data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet
                    - Write behaviour:
                        · if partition does not exist:
                              - write rows to temporary location,
                              - fsync, then atomic rename into final path.
                        · if partition exists:
                              - load existing dataset, normalise schema + sort order,
                              - compare to newly computed table:
                                    - if byte-identical → idempotent re-run; OK,
                                    - else → immutability violation; S0 MUST fail and MUST NOT overwrite.

s0_gate_receipt_3B JSON,
[Schema+Dict]
                ->  (S0.10) Write s0_gate_receipt_3B (fingerprint-only, write-once)
                    - Target path (via dictionary entry `s0_gate_receipt_3B`):
                        · data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json
                    - Write behaviour:
                        · if file does not exist:
                              - write JSON to a temporary filename,
                              - fsync, then atomic rename into canonical filename.
                        · if file exists:
                              - read existing JSON, normalise logical content,
                              - compare to newly constructed object:
                                    - if byte-identical → idempotent re-run; OK,
                                    - else → immutability violation; MUST NOT overwrite.
                    - S0 MUST ensure:
                        · embedded manifest_fingerprint matches path token,
                        · embedded seed, parameter_hash match the Layer-1 identity triple.

Downstream touchpoints
----------------------
- **3B.S1–S5 (classification, settlement, edges, alias, routing/validation contracts):**
    - MUST:
        · verify existence + schema of s0_gate_receipt_3B and sealed_inputs_3B for this manifest_fingerprint before doing any work,
        · treat s0_gate_receipt_3B as the canonical identity + upstream-gate proof,
        · treat sealed_inputs_3B as the **only** admissible universe of external artefacts;
          any attempt to read artefacts not in sealed_inputs_3B is a contract violation.
- **3B terminal validation state (3B.S5 according to your spec naming):**
    - uses s0_gate_receipt_3B + sealed_inputs_3B as inputs when:
        · re-verifying upstream gates,
        · recomputing digests,
        · constructing 3B’s own validation bundle + `_passed.flag_3B`.
- **Cross-segment consumers:**
    - do not consume S0 outputs directly, but must respect the segment-level HashGate produced later:
        · S0 is the root-of-trust for 3B’s input universe; if S0 is not PASS for a manifest,
          no 3B artefacts for that manifest should be considered valid.
```