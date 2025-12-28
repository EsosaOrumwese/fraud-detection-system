```
        LAYER 2 · SEGMENT 5A — STATE S5 (SEGMENT VALIDATION & HASHGATE)  [NO RNG]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5A
      @ data/layer2/5A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5A.json
      · provides:
          - manifest_fingerprint,
          - parameter_hash (for the invocation that produced S0),
          - run_id,
          - scenario_pack_id / scenario_ids in scope,
          - verified_upstream_segments.{1A,1B,2A,2B,3A,3B},
          - sealed_inputs_digest (SHA-256 over sealed_inputs_5A rows).
      · S5 MUST:
          - trust upstream segment statuses,
          - treat sealed_inputs_digest as the only canonical fingerprint of the 5A input universe.

    - sealed_inputs_5A
      @ data/layer2/5A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5A.parquet
      · one row per artefact S1–S4 are allowed to read:
          - {owner_layer, owner_segment, artifact_id, manifest_key, path_template,
             partition_keys[], schema_ref, sha256_hex, role, status, read_scope, source_dictionary, source_registry}.
      · S5 MUST use this as:
          - the exclusive catalogue of external inputs,
          - the starting point for discovering 5A outputs to validate.

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.layer2.yaml, schemas.5A.yaml
    - dataset_dictionary.layer1.*        (for upstream Layer-1 artefacts used in cross-checks)
    - dataset_dictionary.layer2.5A.yaml  (for all S1–S4 + S5 artefacts)
        · includes (among others):
            - merchant_zone_profile_5A,
            - class_zone_shape_5A, shape_grid_definition_5A,
            - merchant_zone_baseline_local_5A,
            - merchant_zone_scenario_local_5A / _utc_5A / overlay_factors_5A,
            - validation_bundle_index_5A,
            - validation_report_5A,
            - validation_issue_table_5A,
            - validation_passed_flag_5A.
    - artefact_registry_5A.yaml
        · IDs → roles for S0–S5 datasets and configs.

[5A modelling outputs to validate (discovered from catalogues)]
    - S1:
        · merchant_zone_profile_5A
          @ data/layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/merchant_zone_profile_5A.parquet
    - S2:
        · shape_grid_definition_5A
          @ data/layer2/5A/shape_grid_definition/parameter_hash={parameter_hash}/scenario_id={scenario_id}/…
        · class_zone_shape_5A
          @ data/layer2/5A/class_zone_shape/parameter_hash={parameter_hash}/scenario_id={scenario_id}/…
        · class_shape_catalogue_5A (optional)
    - S3:
        · merchant_zone_baseline_local_5A
          @ data/layer2/5A/merchant_zone_baseline_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
        · class_zone_baseline_local_5A (optional)
        · merchant_zone_baseline_utc_5A (optional)
    - S4:
        · merchant_zone_scenario_local_5A
          @ data/layer2/5A/merchant_zone_scenario_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/…
        · merchant_zone_overlay_factors_5A (optional)
        · merchant_zone_scenario_utc_5A (optional)

    - S5 will **discover** the set of `(parameter_hash, scenario_id)` pairs (“RUNS”) for which the above
      outputs exist by using dictionaries + sealed_inputs_5A + artefact_registry_5A.
      It MUST NOT hard-code any particular set of parameter packs or scenarios.

[Validation reports & bundle artefacts (owned by S5)]
    - validation_report_5A      (required)
      @ data/layer2/5A/validation/fingerprint={manifest_fingerprint}/reports/validation_report_5A.json
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer2.yaml#/validation/validation_report_5A
      · single JSON per fingerprint with:
            per-check status, metrics, and per-(parameter_hash,scenario_id) summaries.

    - validation_issue_table_5A (optional)
      @ data/layer2/5A/validation/fingerprint={manifest_fingerprint}/issues/validation_issue_table_5A.parquet
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer2.yaml#/validation/validation_issue_table_5A
      · 0+ rows, each describing one issue instance (check_id, issue_code, severity, context…).

    - validation_bundle_index_5A (required)
      @ data/layer2/5A/validation/fingerprint={manifest_fingerprint}/validation_bundle_index_5A.json
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer2.yaml#/validation/validation_bundle_index_5A
      · lists every bundle evidence file as `{path, sha256_hex}` (relative paths only).

    - validation_passed_flag_5A (required)
      @ data/layer2/5A/validation/fingerprint={manifest_fingerprint}/_passed.flag
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer2.yaml#/validation/passed_flag_5A
      · single-line text: `sha256_hex = <bundle_digest_sha256>`.

[Numeric & RNG posture]
    - RNG:
        · S5 is strictly **RNG-free**:
            - MUST NOT open or advance Philox,
            - MUST NOT write RNG events or modify RNG logs.
    - Determinism & immutability:
        · For a fixed `manifest_fingerprint` and fixed inputs (S0, sealed_inputs_5A, S1–S4 outputs, policies),
          S5 MUST produce byte-identical validation_report_5A, validation_issue_table_5A (if present),
          validation_bundle_index_5A, validation_passed_flag_5A.
        · If any of those already exist with non-identical bytes, S5 MUST treat this as an immutability conflict.
    - Bundle hashing law:
        · Let index.entries be the array of `{path, sha256_hex}` in validation_bundle_index_5A,
          sorted ASCII-lexicographically by `path`.
        · Then:
              bundle_digest_sha256 = SHA256( concat( bytes(file[path₁]), bytes(file[path₂]), … ) )
          where files are read in that path order and concatenated byte-wise.
        · validation_passed_flag_5A.sha256_hex MUST equal bundle_digest_sha256.


----------------------------------------------------------------------
DAG — 5A.S5 (S0–S4 + policies → validation report + bundle + `_passed.flag`)  [NO RNG]

### Phase A — Load gate, sealed inputs & catalogues (RNG-free)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S5.1) Load S0 artefacts & check identity
                    - Resolve:
                        · s0_gate_receipt_5A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_5A@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer2.5A.yaml.
                    - Validate both against schemas.5A.yaml.
                    - From s0_gate_receipt_5A:
                        · read {parameter_hash, manifest_fingerprint, run_id, scenario_pack_id},
                        · read verified_upstream_segments.{1A,1B,2A,2B,3A,3B}.
                    - Recompute sealed_inputs_digest from sealed_inputs_5A (canonical sort + serialisation),
                      require equality with s0_gate_receipt_5A.sealed_inputs_digest.
                    - Require:
                        · all upstream segments required by 5A (1A–3B, 2B, 3A/3B) have status="PASS".
                      On any failure: S5 MUST abort; **no bundle** created or updated.

sealed_inputs_5A,
dataset_dictionary.layer2.5A.yaml,
artefact_registry_5A.yaml
                ->  (S5.2) Discover RUNS = {(parameter_hash, scenario_id)} to validate
                    - Using only:
                        · sealed_inputs_5A,
                        · dataset_dictionary.layer2.5A.yaml,
                        · artefact_registry_5A.yaml,
                      S5 MUST:
                        1. Find all parameter_hash values for which 5A policies/configs are sealed.
                        2. For each parameter_hash, find all scenario_id values for which S1–S4 outputs exist:
                               - merchant_zone_profile_5A@fingerprint,
                               - class_zone_shape_5A@parameter_hash,scenario_id,
                               - merchant_zone_baseline_local_5A@fingerprint,scenario_id,
                               - merchant_zone_scenario_local_5A@fingerprint,scenario_id (and any optional S4 outputs).
                        3. Build RUNS = set of (parameter_hash, scenario_id) pairs that appear consistently across these datasets.
                    - S5 MUST NOT:
                        · use ad-hoc filesystem scans,
                        · infer RUNS from filenames alone outside the dictionary/registry contracts.
                    - If RUNS is empty:
                        · treat as either:
                              - “no 5A outputs for this world yet” (valid if allowed by spec), or
                              - configuration error if S5 is invoked for a world that is expected to have outputs.

### Phase B — Per-run checks over S1–S4 (RNG-free)

RUNS,
sealed_inputs_5A,
dataset_dictionary.layer2.5A.yaml,
artefact_registry_5A.yaml,
schemas.5A.yaml
                ->  (S5.3) Initialise check registry & metrics
                    - Construct an in-memory registry of check_ids (fixed by spec), grouped by state:
                        · S1: "S1_DOMAIN_COVERAGE", "S1_CLASS_COMPLETENESS", "S1_BASE_SCALE_VALID".
                        · S2: "S2_GRID_COMPLETE", "S2_SHAPES_NORMALISED".
                        · S3: "S3_DOMAIN_ALIGNMENT", "S3_WEEKLY_SUM_VS_SCALE", "S3_NUMERIC_VALID".
                        · S4: "S4_HORIZON_MAPPING", "S4_OVERLAY_FACTORS_VALID", "S4_SCENARIO_LAMBDA_VALID".
                    - For each check_id:
                        · status = "PASS" (initial),
                        · affected_count = 0,
                        · severity (ERROR/WARN/INFO) from spec.
                    - Initialise metrics structure:
                        · per-run metrics (per parameter_hash,scenario_id),
                        · global metrics (e.g. max deviations, counts).

RUNS,
S1–S4 datasets (resolved per run),
check registry & metrics
                ->  (S5.4) Evaluate per-run S1–S4 checks
                    - For each (ph,sc) ∈ RUNS:
                        1. Resolve, via dictionary:
                               merchant_zone_profile_5A@fingerprint,
                               shape_grid_definition_5A@{ph,sc},
                               class_zone_shape_5A@{ph,sc},
                               merchant_zone_baseline_local_5A@fingerprint,sc,
                               merchant_zone_scenario_local_5A@fingerprint,sc,
                               (optional) class_zone_baseline_local_5A, merchant_zone_scenario_utc_5A,
                               (optional) overlay factors dataset.
                        2. Validate schemas and PK/partition invariants.
                        3. Run check families:

                           **S1 checks** (for this run, even if classing reused across scenarios)
                           - Domain coverage: merchant_zone_profile_5A domain vs zone_alloc & merchant universe.
                           - Demand class completeness: no NULL/invalid class labels.
                           - Base scale validity: base_scale ≥ 0, finite; scale_unit consistent.

                           **S2 checks**
                           - shape_grid_definition_5A:
                                 covers full 7 days at declared resolution;
                                 contiguous bucket_index, no gaps.
                           - class_zone_shape_5A:
                                 non-negative shape_value,
                                 Σ_k shape_value ≈ 1 per (class,zone),
                                 domain includes all class×zone combos used by S1 in this run.

                           **S3 checks**
                           - Domain alignment: merchant_zone_baseline_local_5A domain matches S1’s domain for (ph,sc).
                           - Weekly sum vs scale:
                                 for each (m,z[,ch]),
                                     Σ_k λ_base_local(m,z,k) respects base_scale semantics (per S3 policy).
                           - Numeric safety: no negative, NaN, or Inf λ values.

                           **S4 checks**
                           - Horizon mapping: every local_horizon_bucket_index in scenario output maps to a valid (day_of_week, minute) bucket, consistent with shape_grid_definition_5A and horizon_config_5A.
                           - Overlay factors: if overlay dataset exists, F_overlay ≥ 0, finite, within policy bounds.
                           - Scenario λ:
                                 λ_local_scenario ≥ 0, finite;
                                 optional sum/ratio invariants per policy (e.g. overlay budgets).

                        4. For every violated condition:
                               - set check.status = "FAIL" or "WARN",
                               - increment affected_count,
                               - optionally append issue records into an in-memory issue list with context {ph,sc,merchant_id,zone,bucket,...}.
                        5. Update per-run metrics (counts, max deviations).

                    - S5 MUST NOT:
                        · fix or overwrite S1–S4 outputs,
                        · emit any modelling artefacts; only diagnostics.

### Phase C — Build validation_report_5A & validation_issue_table_5A (RNG-free)

check registry,
per-run metrics,
issue list
                ->  (S5.5) Assemble validation_report_5A JSON
                    - Determine `overall_status` for this fingerprint:
                        · "FAIL" if any check.status == "FAIL",
                        · "PASS" otherwise (WARNs allowed).
                    - Build `validation_report_5A` object with at least:
                        · manifest_fingerprint,
                        · overall_status,
                        · checks[]:
                              [{check_id, status, severity, affected_count, description}],
                        · metrics:
                              - domain sizes (number of runs, merchants, zones, buckets),
                              - max |Σ shape−1| over all S2 shapes,
                              - max |weekly_sum−base_scale| over S3,
                              - max overlay factor and scenario λ deviations,
                              - counts of WARN/FAIL per check,
                              - per-(parameter_hash,scenario_id) summaries as needed.
                    - Validate against schemas.layer2.yaml#/validation/validation_report_5A.

issue list (may be empty),
schemas.layer2.yaml
                ->  (S5.6) Assemble validation_issue_table_5A rows (optional)
                    - If issue list is empty:
                        · S5 MAY choose:
                              - to write an empty validation_issue_table_5A dataset, OR
                              - to omit it entirely (as allowed by schema & pipeline).
                    - If issue list is non-empty:
                        · create one row per issue with fields (per schema):
                              - manifest_fingerprint,
                              - parameter_hash,
                              - scenario_id,
                              - check_id,
                              - issue_code,
                              - severity,
                              - context (e.g. merchant_id, legal_country_iso, tzid, bucket_index),
                              - message (human-readable),
                              - detected_at_utc (optional).
                    - Validate the table against schemas.layer2.yaml#/validation/validation_issue_table_5A.

[validation_report_5A JSON],
[validation_issue_table_5A table?],
[Schema+Dict]
                ->  (S5.7) Write validation_report_5A & validation_issue_table_5A (fingerprint-only, write-once)
                    - Target paths:
                        · validation_report_5A:
                              data/layer2/5A/validation/fingerprint={manifest_fingerprint}/reports/validation_report_5A.json
                        · validation_issue_table_5A:
                              data/layer2/5A/validation/fingerprint={manifest_fingerprint}/issues/validation_issue_table_5A.parquet
                          (if issue table is present).
                    - For each artefact:
                        · If file/dataset does not exist:
                              - write via staging → fsync → atomic move.
                        · If it exists:
                              - read existing bytes, normalise logical content,
                              - if byte-identical → idempotent re-run; OK,
                              - else → immutability conflict; S5 MUST NOT overwrite.

### Phase D — Build validation_bundle_index_5A (index.json)  [NO RNG]

validation_report_5A,
validation_issue_table_5A (if present),
optional additional evidence files (per spec),
bundle staging root
                ->  (S5.8) Collect evidence files & compute per-file digests
                    - Choose a **bundle root** for this fingerprint:
                          data/layer2/5A/validation/fingerprint={manifest_fingerprint}/
                    - Construct a logical list EVIDENCE of files to include, at minimum:
                        · reports/validation_report_5A.json,
                        · issues/validation_issue_table_5A.parquet (if present),
                        · any additional S5 evidence files defined by spec (e.g. per-run summaries).
                    - For each file f in EVIDENCE:
                        · compute its relative path `p` from bundle root (no leading '/', no '.', no '..'),
                        · read raw bytes from disk,
                        · compute sha256_hex_file = SHA256(raw bytes).
                    - Build array `entries`:
                        · entries = [{ "path": p, "sha256_hex": sha256_hex_file } for each f ∈ EVIDENCE ].
                    - Sort entries by `path` in strict ASCII lex order.

entries array,
schemas.layer2.yaml
                ->  (S5.9) Construct and write validation_bundle_index_5A.json
                    - Build JSON object (index) conforming to schemas.layer2.yaml#/validation/validation_bundle_index_5A:
                        · contains `entries` as above (and any extra metadata fields defined by schema).
                    - Serialise to JSON using a stable serializer (ordering of object keys deterministic).
                    - Write to:
                        · data/layer2/5A/validation/fingerprint={manifest_fingerprint}/validation_bundle_index_5A.json
                      via staging → fsync → atomic move.
                    - If index already exists:
                        · load existing, normalise logical content,
                        · compare to newly constructed index:
                              - if identical → idempotent re-run; keep existing,
                              - else → immutability conflict; MUST NOT overwrite.

### Phase E — Compute bundle_digest & write validation_passed_flag_5A  [NO RNG]

validation_bundle_index_5A.json,
EVIDENCE files
                ->  (S5.10) Compute bundle_digest_sha256
                    - Read index.json and extract `entries` (path, sha256_hex) in its stored order.
                    - For each entry in that order:
                        · read raw bytes of the file at `bundle_root / path`,
                        · append bytes to an in-memory buffer/stream (do NOT re-encode from JSON).
                    - Compute:
                        · bundle_digest_sha256 = SHA256(concatenated_bytes),
                          encoded as 64-char lowercase hex string.
                    - This `bundle_digest_sha256` is the value that MUST appear in validation_passed_flag_5A.sha256_hex.

bundle_digest_sha256,
schemas.layer2.yaml
                ->  (S5.11) Construct and write validation_passed_flag_5A (fingerprint-only, write-once)
                    - Logical content:
                        · single key: sha256_hex = bundle_digest_sha256.
                    - On disk:
                        · one line of text:
                              `sha256_hex = <bundle_digest_sha256>`
                          with a trailing newline, matching schemas.layer2.yaml#/validation/passed_flag_5A.
                    - Target path:
                        · data/layer2/5A/validation/fingerprint={manifest_fingerprint}/_passed.flag
                    - If flag does not exist:
                        · write via staging → fsync → atomic move.
                    - If flag exists:
                        · read, parse sha256_hex,
                        · if existing value == bundle_digest_sha256 → idempotent; OK,
                        · else → immutability conflict; MUST NOT overwrite.

Downstream touchpoints
----------------------
- **All consumers of 5A outputs** (5B, 6A, internal validation tools) MUST:
    1. Locate `validation_bundle_index_5A.json` and `_passed.flag` for the desired `manifest_fingerprint`.
    2. Recompute `bundle_digest_sha256` according to the fixed law:
           - read each file listed in `entries` in ASCII-lex path order,
           - SHA-256 over their concatenated bytes.
    3. Verify that `_passed.flag` contains `sha256_hex = <bundle_digest_sha256>`.
    4. Only then treat 5A modelling artefacts (S1–S4 outputs) as usable.

- **5A HashGate rule:**
    - For a given `manifest_fingerprint`, **no 5A PASS → no read/use**:
          - merchant_zone_profile_5A,
          - class_zone_shape_5A, shape_grid_definition_5A,
          - merchant_zone_baseline_local_5A,
          - merchant_zone_scenario_local_5A / _utc_5A / overlay_factors_5A,
      must all be gated on `_passed.flag`.

- **Change management:**
    - Any change to S1–S4 behaviour, policies, or inputs that materially changes shapes or intensities
      MUST result in:
          - new S1–S4 outputs,
          - a re-run of S5,
          - a new bundle_digest_sha256 and thus a new `_passed.flag` for that fingerprint.
```
