```
        LAYER 3 · SEGMENT 6A — STATE S0 (GATE & SEALED INPUTS)  [NO RNG]

Authoritative inputs (read-only at S0 entry)
--------------------------------------------
[Run identity & layer contracts]
    - Run identity (supplied by Layer-3 driver):
        · manifest_fingerprint   (Layer-1/2 world id, hex64)
        · parameter_hash         (6A parameter pack id, hex64)
        · run_id                 (opaque id; NOT used for partitioning in 6A)
    - schemas.layer1.yaml        (Layer-1 contracts: validation bundles/flags, core types)
    - schemas.layer2.yaml        (Layer-2 contracts: validation bundles/flags, core types)
    - schemas.layer3.yaml        (Layer-3 contracts: bundle/index/flag schemas, generic validation)
    - schemas.6A.yaml            (Segment-6A contracts: s0_gate_receipt_6A, sealed_inputs_6A, S1–S5 shapes)
    - dataset_dictionary.layer1.*.yaml   (dictionaries for 1A–3B)
    - dataset_dictionary.layer2.*.yaml   (dictionaries for 5A, 5B)
    - dataset_dictionary.layer3.6A.yaml  (dictionary for 6A datasets)
    - artefact_registry_{1A,1B,2A,2B,3A,3B,5A,5B,6A}.yaml
        · mapping from logical IDs → manifest_keys, roles, schema_refs

[Upstream HashGates (must be verified for this manifest_fingerprint)]
    - For each upstream segment seg ∈ {1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B}:
        · validation bundle root for seg:
              data/layerX/seg/validation/fingerprint={manifest_fingerprint}/...
        · `_passed.flag_seg` in that root.
      S0:
        · MUST resolve these via seg’s own dictionary/registry (no hard-coded paths),
        · MUST recompute seg’s bundle digest according to seg’s hashing law,
        · MUST compare recomputed_digest_seg to `_passed.flag_seg.sha256_hex`,
        · MUST record {status,bundle_root,sha256_hex} per seg in its gate receipt.

[Upstream world surfaces 6A may depend on (metadata only at S0)]
    - Layer-1:
        · merchant universe, outlet/zone allocation, site_locations, site_timezones, tz_timetable_cache, etc.
    - Layer-2:
        · scenario λ surfaces (5A),
        · realised arrivals (5B) — typically only for metadata/coverage in 6A; S0 does NOT read rows.
    - At S0:
        · these are candidates only; S0 will discover & hash them but NOT read their rows.

[6A priors, taxonomies & configs (core inputs for S1–S5)]
    - Population priors & segmentation configs:
        · party population priors (per region/type/segment),
        · party segment taxonomies,
        · party attribute priors (income band, lifecycle stage, etc.).
    - Account & product priors:
        · account/product mix per party segment & region,
        · account & product taxonomies,
        · eligibility & linkage rules between party types and account/product families.
    - Instrument priors:
        · card/handle/wallet distributions per account type/segment,
        · instrument taxonomies & scheme/network taxonomies,
        · instrument attribute priors (expiry profiles, network brands, etc.).
    - Device/IP priors:
        · device type/OS priors per segment,
        · IP type/asn/geo priors and risk tags,
        · graph-shape priors (degree distributions, sharing patterns).
    - Fraud-role priors & taxonomies:
        · roles for parties/accounts/merchants/devices/IPs (e.g. “clean”, “mule”, “compromised”),
        · target role mixes per segment/region.
    - 6A validation policy/config:
        · which consistency checks to run at S5, thresholds & severities.
    - All of the above MUST be registered in artefact_registry_6A and discovered via dictionaries;
      S0 does NOT interpret them beyond schema validation and hashing.

[Outputs owned by S0]
    - sealed_inputs_6A
      @ data/layer3/6A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6A.parquet
      · partition_keys: [manifest_fingerprint]
      · schema_ref: schemas.6A.yaml#/validation/sealed_inputs_6A
      · one row per artefact the 6A segment is allowed to depend on, with (min):
            manifest_fingerprint,
            parameter_hash,
            owner_layer,
            owner_segment,
            artifact_id,
            manifest_key,
            role,                 # e.g. "population_priors", "account_mix", "device_priors", "fraud_role_priors"
            schema_ref,
            path_template,
            partition_keys[],
            sha256_hex,
            version,
            status      ∈ {"REQUIRED","OPTIONAL","IGNORED","REQUIRED_MISSING"},
            read_scope  ∈ {"ROW_LEVEL","METADATA_ONLY"},
            source_dictionary,
            source_registry.

    - s0_gate_receipt_6A
      @ data/layer3/6A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6A.json
      · partition_keys: [manifest_fingerprint]
      · schema_ref: schemas.6A.yaml#/validation/s0_gate_receipt_6A
      · single JSON object with (min):
            manifest_fingerprint,
            parameter_hash,
            run_id,
            created_utc,                    # supplied by orchestrator, not direct wall-clock
            s0_spec_version,
            verified_upstream_segments: {
                seg_id → { status, bundle_root, sha256_hex }
            } for seg ∈ {1A,1B,2A,2B,3A,3B,5A,5B},
            sealed_inputs_digest_6A,        # SHA-256 over canonical sealed_inputs_6A
            optional catalogue_versions (schemas/dicts/registries for 6A).

[Numeric & RNG posture]
    - S0 is strictly **RNG-free**:
        · MUST NOT open/advance any RNG stream,
        · MUST NOT emit RNG events or mutate RNG logs.
    - Row-free:
        · S0 MUST NOT read data rows from upstream tables; it only works at the file/artefact level.
    - Determinism:
        · Given (manifest_fingerprint, parameter_hash) and a fixed catalogue/artefact set,
          S0 MUST produce byte-identical sealed_inputs_6A and s0_gate_receipt_6A.


----------------------------------------------------------------------
DAG — 6A.S0 (Upstream gates + catalogue → sealed_inputs_6A & gate receipt)  [NO RNG]

[Run identity & layer contracts]
                ->  (S0.1) Fix identity & validate core contracts
                    - Accept:
                        · manifest_fingerprint, parameter_hash, run_id.
                    - Validate formats:
                        · manifest_fingerprint, parameter_hash are hex64,
                        · run_id is a non-empty string.
                    - Load & validate:
                        · schemas.layer1.yaml, schemas.layer2.yaml, schemas.layer3.yaml, schemas.6A.yaml,
                        · dataset_dictionary.layer1.* for 1A–3B,
                        · dataset_dictionary.layer2.* for 5A,5B,
                        · dataset_dictionary.layer3.6A.yaml,
                        · artefact_registry_{1A,1B,2A,2B,3A,3B,5A,5B,6A}.yaml.
                    - If any core schema/dictionary/registry fails:
                        · S0 MUST fail and MUST NOT emit outputs.

[Upstream HashGates],
dataset_dictionary.layer1.*,
dataset_dictionary.layer2.*,
artefact_registry_{1A,1B,2A,2B,3A,3B,5A,5B}
                ->  (S0.2) Verify upstream segments’ HashGates for this manifest
                    - For each seg ∈ {1A,1B,2A,2B,3A,3B,5A,5B}:
                        1. Use seg’s dictionary+registry to resolve:
                               validation bundle root @ fingerprint={manifest_fingerprint},
                               `_passed.flag_seg` at that root.
                        2. Parse `_passed.flag_seg`:
                               - expect format `sha256_hex = <64hex>`,
                               - extract declared_digest_seg.
                        3. Recompute bundle digest according to seg’s bundle/index law:
                               - read seg’s bundle index,
                               - iterate files in the specified order,
                               - compute SHA-256 over concatenated bytes.
                        4. Compare recomputed_digest_seg to declared_digest_seg:
                               - equal   → status_seg = "PASS",
                               - missing or unequal → status_seg = "FAIL" or "MISSING" as per 6A.S0 rules.
                    - Collect:
                        · verified_upstream_segments = { seg_id → { status, bundle_root, sha256_hex } }.
                    - S0 DOES NOT read data-plane rows from upstream segments here.

dataset_dictionary.layer1.*,
dataset_dictionary.layer2.*,
dataset_dictionary.layer3.6A.yaml,
artefact_registry_6A.yaml
                ->  (S0.3) Discover candidate 6A inputs via catalogue (no literal paths)
                    - Using only dictionaries & registries, S0 scans for artefacts that:
                        · are owned by segment 6A, and/or
                        · are upstream surfaces explicitly referenced by 6A specs,
                        · are marked with 6A roles in artefact_registry_6A, e.g.:
                              population_priors, segmentation_priors, product_mix_priors,
                              instrument_priors, device_priors, ip_priors,
                              fraud_role_priors, validation_policy_6A,
                              relevant upstream world surfaces (zone_alloc, merchant universe, 5A λ summaries, 5B arrivals metadata).
                    - For each candidate artefact a:
                        · retrieve from dictionary+registry:
                              owner_layer,
                              owner_segment,
                              artifact_id,
                              manifest_key,
                              path_template (with partition tokens),
                              partition_keys[],
                              schema_ref,
                              role,
                              status (REQUIRED/OPTIONAL/IGNORED),
                              read_scope (ROW_LEVEL/METADATA_ONLY).

[Candidate artefacts from S0.3],
manifest_fingerprint,
parameter_hash,
dataset_dictionary.*,
artefact_registry_*
                ->  (S0.4) Resolve concrete paths & filter on identity
                    - For each candidate artefact a:
                        1. Substitute partition tokens in path_template:
                               - e.g. `{manifest_fingerprint}`, `{parameter_hash}`, `{seed}` if applicable.
                        2. Evaluate applicability for this (manifest_fingerprint, parameter_hash):
                               - some artefacts are manifest-scoped only,
                               - some are parameter_hash-scoped only,
                               - some may be shared across worlds.
                        3. Check whether the resolved path exists on disk.
                        4. Determine initial status for sealed_inputs:
                               - if registry says REQUIRED and path missing → status="REQUIRED_MISSING",
                               - if OPTIONAL and missing → status="IGNORED",
                               - if present → status from registry (REQUIRED or OPTIONAL).
                    - S0 collects, for each artefact:
                        · {owner_layer, owner_segment, artifact_id, manifest_key,
                           path_template, partition_keys[], schema_ref, role, status}.

[Resolved artefacts],
schemas.*,
manifest_fingerprint,
parameter_hash
                ->  (S0.5) Compute SHA-256 digests for all present artefacts
                    - For each artefact a with an existing resolved path:
                        · if a is a dataset:
                              - identify canonical list of files to hash (e.g. all data files, no temp files),
                        · if a is a config/policy/taxonomy:
                              - hash the single file at the given path.
                        · Read raw bytes (no JSON reformatting),
                        · Compute sha256_hex = SHA256(raw_bytes).
                    - Attach sha256_hex to artefact record.
                    - For REQUIRED_MISSING artefacts:
                        · sha256_hex MAY be set null or a sentinel value, as allowed by sealed_inputs_6A schema.

[Artefact records + digests],
manifest_fingerprint,
parameter_hash
                ->  (S0.6) Assemble sealed_inputs_6A rows (canonical order)
                    - For each artefact record a:
                        · construct one sealed_inputs_6A row with:
                              manifest_fingerprint,
                              parameter_hash,
                              owner_layer,
                              owner_segment,
                              artifact_id,
                              manifest_key,
                              role,
                              schema_ref,
                              path_template,
                              partition_keys[],
                              sha256_hex,
                              version           (from registry; if missing, a documented default),
                              status,
                              read_scope,
                              source_dictionary,
                              source_registry.
                    - Sort rows in a canonical way, e.g.:
                        · by (owner_layer, owner_segment, artifact_id, manifest_key, path_template).

sealed_inputs_6A rows
                ->  (S0.7) Compute sealed_inputs_digest_6A
                    - Serialise sealed_inputs_6A rows into a canonical byte sequence:
                        · fixed column order,
                        · sorted row order as in S0.6,
                        · deterministic encoding (no environment-dependent formatting).
                    - Compute:
                        · sealed_inputs_digest_6A = SHA256(canonical_bytes) as hex64.
                    - This digest will be embedded in s0_gate_receipt_6A and later rechecked
                      by 6A.S1–S5 and 6B.

sealed_inputs_6A rows,
schemas.6A.yaml
                ->  (S0.8) Validate & write sealed_inputs_6A (fingerprint-scoped, write-once)
                    - Target path via dictionary:
                        · data/layer3/6A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6A.parquet
                    - Validate sealed_inputs_6A against schemas.6A.yaml#/validation/sealed_inputs_6A.
                    - Immutability:
                        · If target partition does NOT exist:
                              - write via staging → fsync → atomic move.
                        · If dataset exists:
                              - read existing data, normalise schema + sort,
                              - if byte-identical to new table → idempotent re-run; OK,
                              - else → `S0_6A_SEALED_INPUTS_CONFLICT`; MUST NOT overwrite.

verified_upstream_segments,
sealed_inputs_digest_6A,
manifest_fingerprint,
parameter_hash,
run_id,
schemas.6A.yaml
                ->  (S0.9) Assemble s0_gate_receipt_6A logical object
                    - Construct JSON object:
                        · segment_id                = "6A",
                          state_id                  = "S0",
                          manifest_fingerprint,
                          parameter_hash,
                          run_id,
                          created_utc               = orchestrator-supplied timestamp,
                          s0_spec_version           = current 6A S0 contract version string,
                          verified_upstream_segments = map from seg_id to {status,bundle_root,sha256_hex},
                          sealed_inputs_digest_6A   = sealed_inputs_digest_6A,
                          optional catalogue_versions (for schemas/dicts/registries 6A uses).
                    - Validate object against schemas.6A.yaml#/validation/s0_gate_receipt_6A.

s0_gate_receipt_6A,
schemas.6A.yaml
                ->  (S0.10) Write s0_gate_receipt_6A (fingerprint-scoped, write-once)
                    - Target path via dictionary:
                        · data/layer3/6A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6A.json
                    - If file does NOT exist:
                        · write JSON via staging → fsync → atomic move.
                    - If file exists:
                        · read existing JSON, normalise logical content,
                        · if byte-identical to newly constructed object → idempotent re-run; OK,
                        · else → `S0_6A_GATE_RECEIPT_CONFLICT`; MUST NOT overwrite.
                    - Path↔embed equality:
                        · ensure embedded manifest_fingerprint equals the fingerprint path token.

Downstream touchpoints
----------------------
- **6A.S1–S5 (party, account, instrument, device/IP, fraud posture):**
    - MUST:
        · read s0_gate_receipt_6A and sealed_inputs_6A for their manifest_fingerprint before doing any work,
        · trust verified_upstream_segments as the only upstream gate status,
        · treat sealed_inputs_6A as the complete input universe:
              - any artefact they read MUST appear in sealed_inputs_6A,
              - they MUST honour each artefact’s status and read_scope.
    - MUST NOT:
        · read artefacts not listed in sealed_inputs_6A,
        · weaken S0’s upstream gate decisions.

- **6B (Layer-3 flows/transactions):**
    - MUST also use s0_gate_receipt_6A + sealed_inputs_6A to understand:
        · which world it is sitting in,
        · which priors/configs underpin the 6A world.

- **Layer-3 orchestration & tooling:**
    - Should treat the pair:
          (sealed_inputs_6A, s0_gate_receipt_6A)
      as the formal description of “what 6A is allowed to see and under which upstream world”.
```