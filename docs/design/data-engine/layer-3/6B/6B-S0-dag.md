```
        LAYER 3 · SEGMENT 6B — STATE S0 (BEHAVIOURAL UNIVERSE GATE & SEALED INPUTS)  [NO RNG]

Authoritative inputs (read-only at S0 entry)
--------------------------------------------
[Run identity & layer contracts]
    - Run identity (supplied by Layer-3 driver / orchestration):
        · manifest_fingerprint   (sealed world id from Layers 1–3, hex64)
        · parameter_hash         (6B parameter pack id, hex64)
        · run_id                 (opaque id; MUST NOT affect partitions in 6B)
        · spec_version_6B        (contract version string for 6B)
    - schemas.layer1.yaml        (Layer-1 contracts: validation bundles/flags, core types)
    - schemas.layer2.yaml        (Layer-2 contracts: validation bundles/flags, core types)
    - schemas.layer3.yaml        (Layer-3 contracts: bundle/index/flag schemas, generic validation)
    - schemas.6B.yaml            (Segment-6B contracts: S0–S5 dataset shapes, label/case shapes)
    - dataset_dictionary.layer1.*.yaml   (dictionaries for 1A–3B)
    - dataset_dictionary.layer2.*.yaml   (dictionaries for 5A, 5B)
    - dataset_dictionary.layer3.6A.yaml  (dictionary for 6A datasets)
    - dataset_dictionary.layer3.6B.yaml  (dictionary for 6B datasets)
    - artefact_registry_{1A,1B,2A,2B,3A,3B,5A,5B,6A,6B}.yaml
        · mapping from logical IDs → manifest_keys, roles, path templates, schema_refs, lifecycle flags

[Required upstream HashGates for this manifest_fingerprint]
    - For each upstream segment seg ∈ {1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B, 6A}:
        · validation bundle root for seg:
              data/layerX/seg/validation/fingerprint={manifest_fingerprint}/...
        · `_passed.flag` in that root.
      S0:
        · MUST resolve these via seg’s own dictionary/registry (no hard-coded paths),
        · MUST recompute seg’s bundle digest according to seg’s own bundle/index law,
        · MUST compare recomputed_digest_seg to `_passed.flag.sha256_hex`,
        · MUST record {status, bundle_path, bundle_sha256, flag_path} per seg in s0_gate_receipt_6B.
      Required failure modes (per seg):
        · Missing bundle or flag    → status = "MISSING"
        · Digest mismatch           → status = "FAIL"
        · Only "PASS" is acceptable for required segments; otherwise S0 MUST fail and emit nothing.

[Upstream sealed-input manifests (metadata only at S0)]
    - Where upstream segments expose sealed-input manifests, S0 SHOULD read only their metadata:
        · sealed_inputs_5B (if present) — arrivals sealed-inputs manifest
        · sealed_inputs_6A (if present) — entity-world sealed-inputs manifest
    - S0:
        · MUST validate these against their own schemas,
        · MUST recompute their digests where the upstream schema defines one,
        · MUST treat any mismatch as a fatal precondition failure for 6B (cannot trust upstream universe).

[Upstream world surfaces 6B may depend on (metadata only at S0)]
    - Layer-1:
        · merchant universe, outlet/zone allocations, site_locations, site_timezones, tz_timetable_cache,
          routing surfaces, zone_alloc, virtual edge universes, etc.
    - Layer-2:
        · intensity surfaces (5A),
        · realised arrivals & arrival egress (5B).
    - Layer-3 (6A):
        · party/account/instrument/device/IP bases and link tables,
        · static fraud posture tables.
    - At S0:
        · these are *candidates only*; S0 will discover & hash them but MUST NOT read data rows.

[6B contracts & policies (core inputs for S1–S4, S5)]
    - 6B dataset dictionary, registry, schemas (already listed).
    - Behavioural contracts and priors (logical examples):
        · behaviour_config_6B          (global knobs; scenario bindings, feature flags),
        · attachment_policy_6B         (arrival→entity attachment rules & priors),
        · sessionisation_policy_6B     (session keys, gap thresholds, jitter rules),
        · flow_shape_policy_6B         (how arrivals expand into flows/events baseline),
        · amount_model_6B              (amount distributions, currencies, rounding),
        · fraud_campaign_catalogue_6B  (campaign templates, targeting rules),
        · fraud_overlay_policy_6B      (how campaigns mutate baseline flows/events),
        · truth_labelling_policy_6B    (truth label semantics),
        · bank_view_policy_6B          (bank’s decision + detection/dispute/chargeback logic),
        · case_policy_6B               (case grouping and lifecycle rules),
        · segment_validation_policy_6B (what S5 checks and how severe they are).
    - RNG & envelope policies:
        · rng_profile_layer3.yaml      (Philox configuration, substreams for 6A/6B),
        · rng_policy_6B.yaml           (mapping from 6B decision families → rng_stream_id, budgets).
    - All of the above MUST be registered in artefact_registry_6B and discovered via dictionaries;
      S0 does NOT interpret them beyond schema validation and hashing.

[Outputs owned by S0]
    - sealed_inputs_6B
      @ data/layer3/6B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer3.yaml#/gate/6B/sealed_inputs_6B
      · one row per artefact 6B is allowed to read for this world, with (minimum):
            manifest_fingerprint (hex64; matches path token),
            owner_layer          ∈ {1,2,3},
            owner_segment        (e.g. "5B", "6A", "6B"),
            manifest_key         (logical id in the relevant registry),
            path_template        (dictionary-resolved; no literal paths),
            partition_keys[]     (ordered list of partition dimensions),
            schema_ref           (JSON-Schema anchor to interpret the artefact),
            role                 (e.g. "arrivals", "entity_base", "behaviour_config", "rng_policy"),
            status               ∈ {"REQUIRED","OPTIONAL","IGNORED"},
            read_scope           ∈ {"ROW_LEVEL","METADATA_ONLY"},
            sha256_hex           (hex64 digest of the realised artefact),
            upstream_bundle_id   (optional; id of the upstream validation bundle this artefact hangs under),
            notes                (optional free-form).
      · rows MUST only describe artefacts that actually exist; missing required artefacts MUST cause S0 to fail before writing.

    - s0_gate_receipt_6B
      @ data/layer3/6B/gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B
      · single logical object per fingerprint, recording:
            manifest_fingerprint   (world id; equals path token),
            parameter_hash         (6B parameter pack id),
            spec_version_6B        (contract version string),
            upstream_segments      (map seg_id → {status, bundle_path, bundle_sha256, flag_path}),
            contracts_6B           (map logical_id → {path, sha256_hex, schema_ref, role}),
            sealed_inputs_digest_6B  (hex64 digest over canonical sealed_inputs_6B contents).

DAG — 6B.S0 (Upstream HashGates + catalogues → sealed_inputs_6B & gate receipt)  [NO RNG]
----------------------------------------------------------------------------------------

[Run identity & core contracts]
                ->  (S0.1) Fix identity & validate core contracts
                    - Accept:
                        · manifest_fingerprint, parameter_hash, run_id, spec_version_6B.
                    - Validate formats:
                        · manifest_fingerprint, parameter_hash are hex64,
                        · run_id is a non-empty string,
                        · spec_version_6B is a non-empty version string.
                    - Load & validate:
                        · schemas.layer1.yaml, schemas.layer2.yaml, schemas.layer3.yaml, schemas.6B.yaml,
                        · dataset_dictionary.layer1.* for 1A–3B,
                        · dataset_dictionary.layer2.* for 5A,5B,
                        · dataset_dictionary.layer3.{6A,6B}.yaml,
                        · artefact_registry_{1A,1B,2A,2B,3A,3B,5A,5B,6A,6B}.yaml.
                    - If any core schema/dictionary/registry fails:
                        · S0 MUST fail and MUST NOT emit outputs.

[Upstream HashGates],
dataset_dictionary.layer1.*,
dataset_dictionary.layer2.*,
artefact_registry_{1A,1B,2A,2B,3A,3B,5A,5B,6A}
                ->  (S0.2) Verify upstream segments’ HashGates for this manifest
                    - For each seg ∈ {1A,1B,2A,2B,3A,3B,5A,5B,6A}:
                        1. Use seg’s dictionary+registry to resolve:
                               validation bundle root @ fingerprint={manifest_fingerprint},
                               `_passed.flag` at that root.
                        2. Parse `_passed.flag`:
                               - expect format `sha256_hex = <64hex>`,
                               - extract declared_digest_seg.
                        3. Recompute bundle digest according to seg’s bundle/index law:
                               - read seg’s bundle index,
                               - iterate files in the specified order,
                               - compute SHA-256 over concatenated bytes.
                        4. Compare recomputed_digest_seg to declared_digest_seg:
                               - equal   → status_seg = "PASS",
                               - missing bundle/flag → status_seg = "MISSING",
                               - mismatch            → status_seg = "FAIL".
                    - Build upstream_segments_map:
                        · upstream_segments_map[seg_id] = { status, bundle_path, bundle_sha256, flag_path }.
                    - If any required seg has status ∈ {"FAIL","MISSING"}:
                        · S0 MUST fail and MUST NOT emit outputs.

[Upstream sealed-input manifests],
dataset_dictionary.layer2.*,
dataset_dictionary.layer3.6A.yaml
                ->  (S0.3) Discover upstream sealed-input manifests (metadata only)
                    - For each upstream seg that exposes sealed_inputs_*:
                        · locate sealed_inputs_* for this manifest_fingerprint via its dictionary/registry,
                        · if present:
                              - validate against seg’s own schema,
                              - recompute its digest if seg’s schema defines one,
                              - record reference in a local map upstream_sealed_inputs[seg_id].
                        · if missing but seg is required:
                              - treat as configuration error; S0 MUST fail.
                    - S0 MUST NOT read data-plane rows via upstream sealed-inputs; they are metadata only.

[Catalogues & registries],
upstream_segments_map,
upstream_sealed_inputs
                ->  (S0.4) Discover candidate inputs for 6B (no literal paths)
                    - Starting from:
                        · 6B’s own dictionary & registry,
                        · upstream sealed_inputs manifests (5B, 6A, others),
                        · Layer-1/2/3 registries,
                      derive a *candidate set* of artefacts that 6B might depend on:
                        · arrivals (5B),
                        · 6A entity/posture surfaces,
                        · 6B contracts & policies,
                        · any other artefacts tagged as "behavioural_input" or "engine_context" in registries.
                    - For each candidate:
                        · resolve owner_layer, owner_segment, manifest_key,
                        · resolve path_template & partition_keys via dictionary + registry,
                        · resolve schema_ref and role from registry.
                    - At this stage, candidates may include artefacts that are not actually present on disk.

[candidate set from S0.4],
file-system metadata,
upstream_segments_map
                ->  (S0.5) Resolve concrete paths, filter on identity & presence
                    - For each candidate artefact:
                        · instantiate path_template with manifest_fingerprint (and other static tokens),
                        · check that the realised path lies under the expected root for {layer,segment},
                        · check that owner_segment’s upstream status in upstream_segments_map is "PASS" (for upstream segments).
                    - Probe storage:
                        · if the realised path exists and passes basic shape checks (directory vs file):
                              - mark artefact as "present" and attach its concrete path,
                              - compute sha256_hex over its bytes (or index-defined subset for bundles).
                        · if the realised path does NOT exist:
                              - if status should be REQUIRED → S0 MUST fail,
                              - if status is OPTIONAL/IGNORED → drop from candidate list (do not emit a sealed_inputs row).

[present artefacts from S0.5],
schemas.layer3.yaml#/gate/6B/sealed_inputs_6B
                ->  (S0.6) Assemble sealed_inputs_6B rows (canonical order)
                    - For each present artefact:
                        · construct one sealed_inputs_6B row with:
                              manifest_fingerprint = manifest_fingerprint,
                              owner_layer, owner_segment, manifest_key,
                              path_template        (as per registry),
                              partition_keys[]     (as per dictionary),
                              schema_ref           (as per registry),
                              role                 (from registry or 6B-specific mapping),
                              status               ∈ {"REQUIRED","OPTIONAL","IGNORED"} (as per 6B config),
                              read_scope           ∈ {"ROW_LEVEL","METADATA_ONLY"} (as per 6B config),
                              sha256_hex           (computed in S0.5),
                              upstream_bundle_id   (id of the upstream validation bundle this artefact belongs to, if any),
                              notes                (optional).
                    - Sort rows canonically by:
                        · owner_layer, owner_segment, manifest_key.

[sealed_inputs_6B rows]
                ->  (S0.7) Compute sealed_inputs_digest_6B
                    - Serialise sealed_inputs_6B rows into a canonical byte sequence:
                        · stable column order,
                        · stable row order (as sorted above),
                        · stable encoding (e.g. UTF-8, normalised numbers).
                    - Compute:
                        · sealed_inputs_digest_6B = SHA256(canonical_bytes) as hex64.

[sealed_inputs_6B rows, sealed_inputs_digest_6B],
schemas.layer3.yaml#/gate/6B/sealed_inputs_6B
                ->  (S0.8) Validate & write sealed_inputs_6B (fingerprint-scoped, write-once)
                    - Validate rows against schemas.layer3.yaml#/gate/6B/sealed_inputs_6B.
                    - Target path via dictionary:
                        · data/layer3/6B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet
                    - If file does NOT exist:
                        · write Parquet via staging → fsync → atomic move.
                    - If file exists:
                        · read existing sealed_inputs_6B,
                        · recompute its canonical bytes and digest,
                        · if digest == sealed_inputs_digest_6B → idempotent re-run; OK,
                        · else → `S0_6B_SEALED_INPUTS_CONFLICT`; MUST NOT overwrite.

[upstream_segments_map, contracts_6B set, sealed_inputs_digest_6B],
schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B
                ->  (S0.9) Assemble s0_gate_receipt_6B logical object
                    - contracts_6B:
                        · enumerate all 6B contract artefacts (schemas, dictionaries, registries, policy packs),
                        · resolve their paths & schema_refs via dictionary/registry,
                        · compute sha256_hex for each contract artefact,
                        · build contracts_6B[logical_id] = { path, sha256_hex, schema_ref, role }.
                    - Build JSON object:
                        · manifest_fingerprint = manifest_fingerprint,
                        · parameter_hash       = parameter_hash,
                        · spec_version_6B      = spec_version_6B,
                        · upstream_segments    = upstream_segments_map (with status, bundle_path, bundle_sha256, flag_path),
                        · contracts_6B         = contracts_6B map,
                        · sealed_inputs_digest_6B = sealed_inputs_digest_6B.
                    - Validate object against schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B.

[s0_gate_receipt_6B object],
schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B
                ->  (S0.10) Write s0_gate_receipt_6B (fingerprint-scoped, write-once)
                    - Target path via dictionary:
                        · data/layer3/6B/gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json
                    - If file does NOT exist:
                        · write JSON via staging → fsync → atomic move.
                    - If file exists:
                        · read existing JSON, normalise logical content,
                        · if byte-identical to newly constructed object → idempotent re-run; OK,
                        · else → `S0_6B_GATE_RECEIPT_CONFLICT`; MUST NOT overwrite.
                    - Path↔embed equality:
                        · ensure embedded manifest_fingerprint equals the fingerprint path token.

Downstream touchpoints
----------------------
- **6B.S1–S4 (attachment, baseline flows, fraud overlay, labels/cases):**
    - MUST:
        · read s0_gate_receipt_6B and sealed_inputs_6B for their manifest_fingerprint before doing any work,
        · trust `upstream_segments` in s0_gate_receipt_6B as the only upstream gate status,
        · treat sealed_inputs_6B as the complete input universe:
              - any artefact they read MUST appear in sealed_inputs_6B,
              - they MUST honour each artefact’s status and read_scope.
    - MUST NOT:
        · read artefacts not listed in sealed_inputs_6B,
        · weaken S0’s upstream gate decisions (e.g. ignoring a FAILED upstream segment).

- **6B.S5 (segment validation & HashGate):**
    - MUST:
        · use s0_gate_receipt_6B as the source of truth for upstream segment status,
        · verify that every artefact it inspects appears in sealed_inputs_6B,
        · include both s0_gate_receipt_6B and sealed_inputs_6B (or their digests) in the 6B validation bundle.

- **Layer-4 orchestration & external tooling:**
    - Should treat the pair:
          (sealed_inputs_6B, s0_gate_receipt_6B)
      as the formal description of “which world 6B ran against and which inputs it was allowed to see”.
    - MUST use these artefacts, not ad-hoc configuration, when explaining or reproducing 6B behaviour for a given world.
```
