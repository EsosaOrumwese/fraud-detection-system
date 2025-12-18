```
        LAYER 2 · SEGMENT 5A — STATE S0 (GATE & SEALED INPUTS)  [NO RNG]

Authoritative inputs (read-only at S0 entry)
--------------------------------------------
[Engine run context]
    - (parameter_hash, manifest_fingerprint, run_id)
      · parameter_hash        — identifies the 5A parameter pack (priors, policies, scenarios).
      · manifest_fingerprint  — identifies the Layer-1 world (1A–3B) we are sitting on.
      · run_id                — opaque identifier for this 5A run; never used in partitioning.

[Layer-wide contracts]
    - schemas.layer1.yaml         (Layer-1 schema bundle — for upstream segments 1A–3B)
    - schemas.layer2.yaml         (Layer-2 schema bundle — shared contracts)
    - schemas.5A.yaml             (Segment-5A contracts; includes s0_gate_receipt_5A, sealed_inputs_5A)
    - dataset_dictionary.layer1.* (dataset dictionaries for 1A–3B)
    - artefact_registry_*         (artefact registries for 1A–3B)
    - dataset_dictionary.layer2.5A.yaml (dictionary for 5A datasets)
    - artefact_registry_5A.yaml          (artefact registry for 5A)

[Upstream segment validation artefacts (Layer-1 segments 1A–3B)]
    - For each required upstream segment seg ∈ {1A, 1B, 2A, 2B, 3A, 3B}:
        · validation_bundle_seg  @ data/layer1/seg/validation/fingerprint={manifest_fingerprint}/…
        · _passed.flag_seg       @ same directory
      S0 only checks:
        · presence,
        · structural validity,
        · equality between flag.digest and recomputed bundle digest under that segment’s hashing law.
      S0 never reads those segments’ data-plane rows.

[Upstream world surfaces (candidate inputs for later 5A states)]
    - Layer-1 “world” tables that 5A.S1+ may read, e.g.:
        · merchant catalogue / merchant attributes,
        · zone allocation (zone_alloc from 3A),
        · civil-time surfaces (site_timezones, tz_timetable_cache, tz manifests),
        · virtual surfaces (3B outputs, if 5A ever uses them),
        · routing / 2B outputs, if referenced in 5A policies.
    - S0 only:
        · discovers them via dictionaries/registries,
        · resolves logical IDs, path templates, schema_refs,
        · computes digests,
        · records them into sealed_inputs_5A.
      It MUST NOT read rows.

[5A / Layer-2 policies & scenario configs]
    - 5A classing / scale policies (used by S1).
    - 5A shape & grid policies (used by S2).
    - 5A baseline composition policy (S3).
    - 5A scenario calendar & overlay policies (S4).
    - 5A validation/CI policies (S5).
    - Scenario packs / scenario IDs bound to this parameter_hash.
    - Any 5A-specific RNG or numeric profiles (if defined at Layer-2).
    - S0 only:
        · resolves & hashes these artefacts,
        · does not interpret their content beyond schema validation.

[Outputs owned by S0]
    - sealed_inputs_5A
      @ data/layer2/5A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5A.parquet
      · partition_keys: [manifest_fingerprint]
      · schema_ref: schemas.5A.yaml#/validation/sealed_inputs_5A
      · row-level fields (per artefact):
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
            version,
            source_dictionary,
            source_registry,
            status      ∈ {REQUIRED, OPTIONAL, IGNORED},
            read_scope  ∈ {ROW_LEVEL, METADATA_ONLY}.

    - s0_gate_receipt_5A
      @ data/layer2/5A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5A.json
      · partition_keys: [manifest_fingerprint]
      · schema_ref: schemas.5A.yaml#/validation/s0_gate_receipt_5A
      · fields (min):
            manifest_fingerprint,
            parameter_hash,
            run_id,
            created_utc,
            s0_spec_version,
            scenario_id,
            verified_upstream_segments{seg_id→{status,bundle_id}},
            sealed_inputs_digest   (digest over canonical sealed_inputs_5A rows),
            optional catalogue_versions (schemas/dicts/registries versions).

[Numeric & RNG posture]
    - S0 is strictly **RNG-free**:
        · MUST NOT open or advance Philox (or any RNG),
        · MUST NOT emit RNG events or touch RNG logs.
    - Determinism & immutability:
        · For a fixed (parameter_hash, manifest_fingerprint, run_id) and catalogue state,
          S0 MUST always produce the same sealed_inputs_5A and s0_gate_receipt_5A.
        · If outputs already exist for a fingerprint and differ from what S0 would emit, this is a configuration error.
    - Row-free:
        · S0 only works on metadata (schema, dictionary, registry, file digests).
        · It MUST NOT read or interpret data rows from upstream world surfaces.


----------------------------------------------------------------------
DAG — 5A.S0 (Upstream gates + catalogues → sealed_inputs_5A & gate receipt)  [NO RNG]

[Engine run context],
[Layer-wide contracts]
                ->  (S0.1) Fix run identity & validate schema/dictionary availability
                    - Accept or derive:
                        · parameter_hash,
                        · manifest_fingerprint,
                        · run_id.
                    - Validate:
                        · parameter_hash, manifest_fingerprint are hex64,
                        · run_id is a non-empty string.
                    - Load and validate:
                        · schemas.layer1.yaml, schemas.layer2.yaml, schemas.5A.yaml,
                        · dataset_dictionary.layer1.* for 1A–3B,
                        · dataset_dictionary.layer2.5A.yaml,
                        · artefact_registry_* for 1A–3B, artefact_registry_5A.yaml.
                    - If any required schema or dictionary is missing or invalid:
                        · S0 MUST fail and emit no outputs.

[Upstream segment validation artefacts],
dataset_dictionary.layer1.*,
artefact_registry_*,
schemas.layer1.yaml
                ->  (S0.2) Verify upstream Layer-1 HashGates
                    - For each upstream segment seg in {1A,1B,2A,2B,3A,3B}:
                        1. Use seg’s dictionary+registry to resolve:
                               validation_bundle_seg@fingerprint={manifest_fingerprint},
                               _passed.flag_seg@same root.
                        2. Parse _passed.flag_seg to get declared digest d_seg.
                        3. Recompute the bundle digest according to seg’s own hashing law:
                               - load its bundle index,
                               - read files in its declared order,
                               - SHA-256 over the canonical byte concatenation.
                        4. Compare recomputed_digest_seg with d_seg:
                               - if equal  → status_seg = "PASS",
                               - if missing/invalid/unequal → status_seg = "FAIL" or "MISSING" as appropriate.
                    - S0 DOES NOT read data rows from any upstream egress here.
                    - Record `verified_upstream_segments{seg→{status,bundle_id}}` for later embedding.

[Dataset dictionaries & artefact registries],
parameter_hash,
manifest_fingerprint
                ->  (S0.3) Discover candidate 5A inputs from catalogue
                    - Using only dictionaries + registries (no hard-coded paths), S0:
                        · scans for artefacts whose:
                              - owner_layer ∈ {layer1, layer2},
                              - owner_segment ∈ {1A–3B, 5A},
                              - status ∈ {required, optional} for Segment 5A.
                        · identifies categories:
                              - upstream world surfaces (merchant catalogue, zone_alloc, civil-time surfaces, etc.),
                              - Layer-2 / 5A scenario configs & policies,
                              - 5A-specific class/shape/overlay/validation policies.
                    - For each candidate, S0 retrieves:
                        · artifact_id,
                        · manifest_key,
                        · path_template (with partition tokens),
                        · partition_keys,
                        · schema_ref,
                        · owner_layer, owner_segment,
                        · declared status and role (from registry).

[Candidate artefacts from S0.3],
parameter_hash,
manifest_fingerprint,
dataset_dictionary.*,
artefact_registry_*
                ->  (S0.4) Resolve physical paths & filter by (parameter_hash, manifest_fingerprint)
                    - For each candidate artefact:
                        1. Substitute partition tokens in path_template:
                               - e.g. `{manifest_fingerprint}`, `{parameter_hash}`, `{scenario_id}` if applicable.
                        2. Determine whether that concrete artefact belongs to this run:
                               - for Layer-1 surfaces: must match manifest_fingerprint,
                               - for 5A configs: must match parameter_hash (and scenario binding rules).
                        3. If the concrete file/directory does not exist:
                               - set status="MISSING" if dictionary says REQUIRED,
                               - or ignore/mark IGNORED if OPTIONAL and policy allows.
                    - For artefacts that *do* belong to (parameter_hash, manifest_fingerprint):
                        · S0 records resolved path_template + partition_keys;
                        · S0 will compute digests in the next step.

[Resolved paths from S0.4]
                ->  (S0.5) Compute SHA-256 digests for each artefact
                    - For each resolved artefact that exists:
                        · read its canonical on-disk representation:
                              - for datasets: all data files under the directory (implementation-defined, but fixed),
                              - for configs/policies: raw file bytes,
                          without re-serialising.
                        · compute `sha256_hex = SHA256(raw_bytes)`.
                    - For artefacts that are required but missing:
                        · set status="REQUIRED" with a special `sha256_hex` marker or handle as failure per spec.
                    - For optional artefacts that are absent:
                        · set status="IGNORED" or omit entirely, as defined by 5A.S0 policy.

[All artefacts + digests],
parameter_hash,
manifest_fingerprint
                ->  (S0.6) Assemble rows for `sealed_inputs_5A`
                    - For each artefact considered in S0.3–S0.5, construct a row with:
                        · manifest_fingerprint,
                        · parameter_hash,
                        · owner_layer,
                        · owner_segment,
                        · artifact_id,
                        · manifest_key,
                        · role              (e.g. "merchant_catalogue", "zone_alloc", "civil_time_surface",
                                             "class_policy", "shape_policy", "scenario_calendar"),
                        · schema_ref,
                        · path_template,
                        · partition_keys[]   (as strings),
                        · sha256_hex         (or null/marker for missing, as allowed by schema),
                        · version            (if known from registry; otherwise a documented default),
                        · source_dictionary,
                        · source_registry,
                        · status             ∈ {REQUIRED, OPTIONAL, IGNORED},
                        · read_scope         ∈ {ROW_LEVEL, METADATA_ONLY}.
                    - Canonical ordering:
                        · sort rows by (owner_layer, owner_segment, artifact_id, manifest_key, path_template)
                          before computing `sealed_inputs_digest` and writing.

[Row set for sealed_inputs_5A],
schemas.5A.yaml
                ->  (S0.7) Validate & write `sealed_inputs_5A` (fingerprint-scoped, write-once)
                    - Target path from dictionary:
                        · data/layer2/5A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5A.parquet
                    - Validate rows against schemas.5A.yaml#/validation/sealed_inputs_5A.
                    - Immutability:
                        · if no dataset exists at target path:
                              - write via staging → fsync → atomic move.
                        · if dataset exists:
                              - read existing data, normalise order & schema,
                              - if byte-identical → idempotent re-run; OK,
                              - else → treat as `S0_OUTPUT_CONFLICT`; MUST NOT overwrite.

[sealed_inputs_5A rows],
parameter_hash,
manifest_fingerprint,
run_id
                ->  (S0.8) Compute `sealed_inputs_digest`
                    - Compute a canonical serialisation of sealed_inputs_5A rows:
                        · e.g. stable JSON/Parquet row order & field order.
                    - Compute:
                        · sealed_inputs_digest = SHA256(canonical_bytes), encoded as hex64.
                    - This digest will be embedded in s0_gate_receipt_5A and used by downstream states
                      to detect any change in the sealed input universe.

[verified_upstream_segments from S0.2],
sealed_inputs_digest,
parameter_hash,
manifest_fingerprint,
run_id,
schemas.5A.yaml
                ->  (S0.9) Build s0_gate_receipt_5A logical object
                    - Construct JSON object with at least:
                        · manifest_fingerprint,
                        · parameter_hash,
                        · run_id,
                        · created_utc              (engine/harness-supplied, not system clock),
                        · s0_spec_version          (MAJOR.MINOR.PATCH),
                        · scenario_id              (or scenario_ids) bound to this pack, if applicable,
                        · verified_upstream_segments:
                              { seg_id → { status, bundle_id } }, where seg_id covers all required 1A–3B segments,
                        · sealed_inputs_digest.
                    - Validate against schemas.5A.yaml#/validation/s0_gate_receipt_5A.

s0_gate_receipt_5A JSON,
[Schema+Dict]
                ->  (S0.10) Write s0_gate_receipt_5A (fingerprint-scoped, write-once)
                    - Target path from dictionary:
                        · data/layer2/5A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5A.json
                    - If file does not exist:
                        · write JSON via staging → fsync → atomic move into final path.
                    - If file exists:
                        · read existing JSON, normalise, and compare to newly constructed object:
                              - if byte-identical → idempotent re-run; OK,
                              - else → `S0_OUTPUT_CONFLICT`; MUST NOT overwrite.
                    - Path↔embed equality:
                        · embedded manifest_fingerprint MUST equal fingerprint path token.

Downstream touchpoints
----------------------
- **5A.S1–S4 (classing, shapes, baseline, overlays):**
    - MUST:
        · read s0_gate_receipt_5A@fingerprint to:
              - fix {parameter_hash, manifest_fingerprint, run_id},
              - see which upstream segments are PASS,
              - discover which scenario_id(s) are bound;
        · treat sealed_inputs_5A as the **entire input universe** for Segment 5A:
              - any artefact they read MUST appear in sealed_inputs_5A,
              - they MUST honour `status` and `read_scope` for each artefact.
    - MUST NOT:
        · read random Layer-1/Layer-2 artefacts outside sealed_inputs_5A, even if they exist on disk.

- **5A.S5 (validation & HashGate):**
    - Uses s0_gate_receipt_5A and sealed_inputs_5A as:
        · the identity and upstream-gate evidence,
        · the canonical inventory of inputs when re-auditing 5A.S1–S4.

- **Layer-2 orchestration / external tooling:**
    - MUST treat:
        · the pair (s0_gate_receipt_5A, sealed_inputs_5A) for a fingerprint as logically immutable.
    - Any attempt to change the sealed input universe for a (parameter_hash, manifest_fingerprint)
      without re-running S0 is a contract violation.
```