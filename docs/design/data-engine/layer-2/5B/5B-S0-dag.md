```
        LAYER 2 · SEGMENT 5B — STATE S0 (GATE & SEALED INPUTS FOR ARRIVAL REALISATION)  [NO RNG]

Authoritative inputs (read-only at S0 entry)
--------------------------------------------
[Run identity & layer contracts]
    - Run identity triple (supplied by driver / harness):
        · seed                  (Layer-2 seed, uint64)
        · parameter_hash        (5A/5B parameter pack id, hex64)
        · manifest_fingerprint  (Layer-1 world id, hex64)
        · run_id                (opaque string; not used for partitioning)
    - schemas.layer1.yaml       (Layer-1 contracts: validation bundle/flag schemas, RNG primitives)
    - schemas.layer2.yaml       (Layer-2 contracts: bundle/flag schemas, generic validation)
    - schemas.5B.yaml           (Segment-5B contracts: s0_gate_receipt_5B, sealed_inputs_5B, S1–S5 shapes)
    - dataset_dictionary.layer1.*.yaml     (dictionaries for 1A–3B, 5A, 3B; used for upstream gates & world surfaces)
    - artefact_registry_{1A,1B,2A,2B,3A,3B,5A}.yaml
    - dataset_dictionary.layer2.5B.yaml    (dictionary for all 5B datasets)
    - artefact_registry_5B.yaml            (registry entries for 5B datasets & configs)

[Upstream HashGates (segments 1A–3B and 5A)]
    - For each upstream segment seg ∈ {1A, 1B, 2A, 2B, 3A, 3B, 5A}:
        · validation_bundle_seg@
              data/layerX/seg/validation/fingerprint={manifest_fingerprint}/validation_bundle_seg_index.json (or equivalent)
        · _passed.flag@
              data/layerX/seg/validation/fingerprint={manifest_fingerprint}/_passed.flag
      S0:
        · MUST resolve these via the segments’ own dictionaries/registries (no hard-coded paths),
        · MUST recompute each segment’s bundle digest according to its hashing law,
        · MUST compare recomputed digest to `_passed.flag.sha256_hex`,
        · MUST record {status,bundle_path,flag_path,digest} per segment in its receipt.

[Upstream world & intensity surfaces 5B may later depend on  (metadata-only in S0)]
    - World / geometry / time:
        · zone_alloc, site_locations, site_timezones, tz_timetable_cache, virtual surfaces (3B), etc.
    - Routing surfaces:
        · 2B routing plan surfaces and validation bundles (site/edge alias, routing policies).
    - Intensity surfaces from 5A:
        · merchant_zone_baseline_local_5A, merchant_zone_scenario_local_5A (and any UTC variants),
        · shape grids and horizon configs used by 5A.
    - In S0:
        · these artefacts are treated as **candidates** only,
        · S0 does NOT read any rows; it only discovers, resolves and hashes them.

[5B policies & configs]
    - 5B arrival realisation policies:
        · laws for intensity noise (LGCP / log-Gaussian variants),
        · laws for bucket-to-count conversion (Poisson, NB, etc.),
        · micro-time placement within buckets (uniform, shape-weighted, etc.).
    - 5B RNG / routing profiles:
        · which Philox streams/substreams 5B.S2–S4 may use,
        · event families and budgets for intensity noise, count sampling, and micro-time.
    - Scenario-run configs:
        · scenario_set_id,
        · mapping from scenario_id → which 5A intensity surfaces are in scope.

[Outputs owned by S0]
    - sealed_inputs_5B
      @ data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
      · partition_keys: [manifest_fingerprint]
      · schema_ref: schemas.5B.yaml#/validation/sealed_inputs_5B
      · one row per artefact in-scope for 5B, with (min):
            manifest_fingerprint,
            parameter_hash,
            owner_layer,
            owner_segment,
            artifact_id,
            manifest_key,
            role,                 # e.g. "arrival_policy", "world_surface", "routing_surface", "rng_profile"
            schema_ref,
            path_template,
            partition_keys[],
            sha256_hex,
            version,
            status      ∈ {"REQUIRED","OPTIONAL","IGNORED"},
            read_scope  ∈ {"ROW_LEVEL","METADATA_ONLY"},
            source_dictionary,
            source_registry.

    - s0_gate_receipt_5B
      @ data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
      · partition_keys: [manifest_fingerprint]
      · schema_ref: schemas.5B.yaml#/validation/s0_gate_receipt_5B
      · single JSON object with (min):
            manifest_fingerprint,
            parameter_hash,
            seed,
            run_id,
            scenario_set_id,
            verified_upstream_segments: { seg_id → {status,bundle_digest,bundle_root} },
            sealed_inputs_digest (SHA-256 over canonical sealed_inputs_5B),
            s0_spec_version,
            created_utc (supplied by orchestrator or derived deterministically).

[Numeric & RNG posture]
    - S0 is strictly **RNG-free**:
        · MUST NOT open or advance any Philox stream,
        · MUST NOT emit RNG events or touch RNG logs.
    - Determinism:
        · Given fixed identity triple + catalogue state, S0 MUST produce the same sealed_inputs_5B and s0_gate_receipt_5B bytes.
    - Row-free:
        · S0 works only on metadata (schemas, dictionaries, registries, file bytes),
        · MUST NOT read data rows from upstream intensity or world surfaces.


----------------------------------------------------------------------
DAG — 5B.S0 (Upstream HashGates + catalogues → sealed_inputs_5B & gate receipt)  [NO RNG]

[Run identity & layer contracts]
                ->  (S0.1) Fix run identity & validate core contracts
                    - Accept:
                        · seed, parameter_hash, manifest_fingerprint, run_id.
                    - Validate:
                        · parameter_hash, manifest_fingerprint are valid hex64,
                        · run_id is non-empty,
                        · seed is well-formed (uint64).
                    - Load and validate:
                        · schemas.layer1.yaml, schemas.layer2.yaml, schemas.5B.yaml,
                        · dataset_dictionary.layer1.* for 1A–3B/5A/3B,
                        · dataset_dictionary.layer2.5B.yaml,
                        · artefact_registry_* for 1A–3B/5A, artefact_registry_5B.
                    - If any core schema/dictionary/registry fails to load or validate:
                        · S0 MUST fail and emit no outputs.

[Upstream HashGates],
dataset_dictionary.layer1.*,
artefact_registry_{1A,1B,2A,2B,3A,3B,5A}
                ->  (S0.2) Verify upstream segment gates for this manifest_fingerprint
                    - For each seg ∈ {1A,1B,2A,2B,3A,3B,5A}:
                        1. Use seg’s dictionary+registry to resolve:
                               bundle_root_seg@fingerprint={manifest_fingerprint},
                               _passed.flag@same root.
                        2. Parse `_passed.flag`:
                               - ensure format `sha256_hex = <64hex>`,
                               - extract declared_digest_seg.
                        3. Recompute bundle digest per seg’s bundle law:
                               - load seg’s bundle index,
                               - sort files / follow declared order,
                               - SHA-256 over concatenated raw bytes of all indexed files.
                        4. If any of:
                               - bundle_root missing,
                               - flag missing,
                               - recomputed_digest_seg ≠ declared_digest_seg,
                           then record status_seg = "FAIL" (or "MISSING", as per spec),
                           else status_seg = "PASS".
                    - S0 DOES NOT read any data-plane rows from upstream segments at this step.
                    - Record a map:
                        · verified_upstream_segments = {seg_id → {status, bundle_root, sha256_hex}}.

dataset_dictionary.layer1.*,
dataset_dictionary.layer2.*,
artefact_registry_{1A–3B,5A,5B},
parameter_hash,
manifest_fingerprint
                ->  (S0.3) Discover candidate 5B inputs via catalogue (no literal paths)
                    - Using only dictionaries + registries, S0 scans for artefacts that:
                        · are relevant to 5B by role, e.g.:
                              - 5A intensity surfaces for the scenario_set,
                              - civil-time and geometry surfaces needed for micro-time placement,
                              - routing surfaces from 2B/3B,
                              - 5B arrival law configs & RNG/routing profiles,
                        · and are marked as REQUIRED or OPTIONAL for 5B.
                    - For each candidate artefact a:
                        · retrieve from dictionary+registry:
                              owner_layer,
                              owner_segment,
                              artifact_id,
                              manifest_key,
                              path_template with partition tokens,
                              partition_keys[],
                              schema_ref,
                              role.

[Candidate artefacts from S0.3],
parameter_hash,
manifest_fingerprint,
dataset_dictionary.*,
artefact_registry_*
                ->  (S0.4) Resolve concrete paths & filter on identity
                    - For each candidate artefact a:
                        1. Substitute `manifest_fingerprint` and, if applicable, `parameter_hash` and `scenario_id`
                           into its path_template.
                        2. Check if the resolved path exists on disk:
                               - dataset directory or config file.
                        3. Decide status:
                               - if dictionary marks a as REQUIRED and path missing → status="REQUIRED" but MISSING → will be handled as error later,
                               - if OPTIONAL and missing → status="IGNORED",
                               - if present → status initially "REQUIRED" or "OPTIONAL" as per registry.
                    - At this stage S0 collects:
                        · for each present artefact:
                              {owner_layer, owner_segment, artifact_id, manifest_key, path_template, partition_keys[], schema_ref, role, status}.

[Resolved artefacts],
schemas.*,
run identity
                ->  (S0.5) Compute SHA-256 digests for all resolved artefacts
                    - For each artefact a with an existing path:
                        · open the on-disk representation:
                              - for datasets: the canonical set of data files (as defined by 5B’s catalogue),
                              - for configs/policies: the single file.
                        · read raw bytes (no re-serialisation),
                        · compute sha256_hex = SHA256(raw_bytes).
                    - Attach sha256_hex to the record for a.
                    - For artefacts that are REQUIRED but missing:
                        · either:
                              - mark as status="REQUIRED_MISSING" with sha256_hex=null,
                              - or, if 5B.S0 spec requires, treat this immediately as failure and abort.
                    - After this step, S0 has an in-memory table of all candidate artefacts with digests.

[Artefact records + digests],
parameter_hash,
manifest_fingerprint
                ->  (S0.6) Assemble sealed_inputs_5B rows
                    - For each artefact record a:
                        · construct a row with:
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
                              version            (if present in registry; else a documented default),
                              status             ∈ {"REQUIRED","OPTIONAL","IGNORED","REQUIRED_MISSING"},
                              read_scope         ∈ {"ROW_LEVEL","METADATA_ONLY"} as specified by 5B spec,
                              source_dictionary  (id of the dictionary used to resolve),
                              source_registry    (id of the registry used).
                    - Canonical sort for sealing:
                        · sort rows by (owner_layer, owner_segment, artifact_id, manifest_key, path_template).

sealed_inputs_5B rows
                ->  (S0.7) Compute sealed_inputs_digest
                    - Serialise sealed_inputs_5B rows into a canonical byte representation:
                        · stable column order,
                        · stable row order from S0.6,
                        · no environment-dependent formatting.
                    - Compute:
                        · sealed_inputs_digest = SHA256(canonical_bytes), encoded as hex64.
                    - This digest will be embedded in s0_gate_receipt_5B and re-checked by later states.

sealed_inputs_5B rows,
schemas.5B.yaml
                ->  (S0.8) Validate & write sealed_inputs_5B (fingerprint-scoped, write-once)
                    - Target path from dictionary:
                        · data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
                    - Validate sealed_inputs_5B against schemas.5B.yaml#/validation/sealed_inputs_5B.
                    - Immutability:
                        · if dataset does not exist:
                              - write via staging → fsync → atomic move.
                        · if dataset exists:
                              - load existing dataset, normalise schema + sort,
                              - if byte-identical → idempotent re-run; OK,
                              - else → `S0_5B_SEALED_INPUTS_CONFLICT`; MUST NOT overwrite.

verified_upstream_segments,
sealed_inputs_digest,
parameter_hash,
manifest_fingerprint,
seed,
run_id,
schemas.5B.yaml
                ->  (S0.9) Assemble s0_gate_receipt_5B logical object
                    - Construct an object with at least:
                        · segment_id          = "5B",
                        · state_id            = "S0",
                        · manifest_fingerprint,
                        · parameter_hash,
                        · seed,
                        · run_id,
                        · scenario_set_id     (if known from configs bound to parameter_hash),
                        · created_utc         (supplied by orchestrator; NOT from system clock),
                        · verified_upstream_segments:
                              { seg_id → { status, bundle_root, sha256_hex } } for seg ∈ {1A,1B,2A,2B,3A,3B,5A },
                        · sealed_inputs_digest.
                    - Validate against schemas.5B.yaml#/validation/s0_gate_receipt_5B.

s0_gate_receipt_5B object,
schemas.5B.yaml
                ->  (S0.10) Write s0_gate_receipt_5B (fingerprint-scoped, write-once)
                    - Target path via dictionary:
                        · data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
                    - If file does not exist:
                        · write JSON to staging file → fsync → atomic move into final path.
                    - If file exists:
                        · read existing JSON, normalise logical content,
                        · if byte-identical to newly constructed object → idempotent re-run; OK,
                        · otherwise → `S0_5B_GATE_RECEIPT_CONFLICT`; MUST NOT overwrite.
                    - Path↔embed equality:
                        · ensure embedded manifest_fingerprint equals fingerprint path token.

Downstream touchpoints
----------------------
- **5B.S1–S4 (time grid, latent fields, bucket counts, arrival events):**
    - MUST:
        · read s0_gate_receipt_5B@fingerprint to:
              - fix {seed, parameter_hash, manifest_fingerprint, run_id, scenario_set_id},
              - see upstream segments’ PASS/FAIL status,
              - get sealed_inputs_digest,
        · treat sealed_inputs_5B as the **only** input universe:
              - any artefact they read MUST appear in sealed_inputs_5B,
              - they MUST honour each artefact’s `status` and `read_scope`.
    - MUST NOT:
        · read ad-hoc artefacts not present in sealed_inputs_5B,
        · silently ignore REQUIRED_MISSING artefacts; such cases must cause failure.

- **5B.S5 (validation & HashGate):**
    - Uses s0_gate_receipt_5B and sealed_inputs_5B as the basis for:
          - re-verifying that inputs used by S1–S4 match the sealed universe,
          - building the 5B validation bundle for this manifest_fingerprint.

- **Layer-3 / external tooling:**
    - SHOULD treat s0_gate_receipt_5B + sealed_inputs_5B as “the contract” describing which world and policies 5B used,
      but MUST gate on the 5B segment-level HashGate (`_passed.flag`) before trusting 5B’s arrival events.
```