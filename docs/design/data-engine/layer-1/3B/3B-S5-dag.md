```
        LAYER 1 · SEGMENT 3B — STATE S5 (SEGMENT VALIDATION BUNDLE & `_PASSED.FLAG_3B`)  [NO RNG]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3B
      @ data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json
      · sole authority for:
          - identity triple {seed, parameter_hash, manifest_fingerprint},
          - upstream gates: segment_1A/1B/2A/3A.status MUST be "PASS",
          - which schemas/dicts/registries were in force for 3B.
    - sealed_inputs_3B
      @ data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet
      · whitelist of all external artefacts S5 MAY read:
          - policies, priors, spatial/tiling assets, RNG profiles, validation policies, RNG logs, etc.
      · Any external artefact S5 reads MUST:
          - appear in sealed_inputs_3B,
          - match {logical_id, path, schema_ref},
          - match `sha256_hex` when S5 recomputes SHA-256.

[Schema+Dict & bundle law]
    - schemas.layer1.yaml
        · bundle index schema: `#/validation/validation_bundle_index_3B`
        · passed-flag schema:   `#/validation/passed_flag_3B`
        · definition of SHA-256 bundle law (index + flag semantics).
    - schemas.3B.yaml
        · shapes for:
            - s0_gate_receipt_3B, sealed_inputs_3B,
            - plan/virtual_classification_3B, plan/virtual_settlement_3B,
            - plan/edge_catalogue_3B, plan/edge_catalogue_index_3B,
            - plan/edge_alias_index_3B, binary/edge_alias_blob_header_3B,
            - validation/edge_universe_hash_3B,
            - egress/virtual_routing_policy_3B,
            - egress/virtual_validation_contract_3B,
            - validation/s5_manifest_3B.
    - dataset_dictionary.layer1.3B.yaml
        · IDs → {path, partitioning, schema_ref} for:
            - all S0–S4 artefacts above,
            - `validation_bundle_3B` (directory),
            - `validation_bundle_index_3B` (index.json),
            - `validation_passed_flag_3B` (`_passed.flag`),
            - `s5_manifest_3B`.
    - artefact_registry_3B.yaml
        · manifest_keys and roles for the same artefacts.

[3B S1–S4 artefacts to be audited]
    - virtual_classification_3B      @ seed={seed}/fingerprint={manifest_fingerprint}
    - virtual_settlement_3B         @ seed={seed}/fingerprint={manifest_fingerprint}
    - edge_catalogue_3B             @ seed={seed}/fingerprint={manifest_fingerprint}
    - edge_catalogue_index_3B       @ seed={seed}/fingerprint={manifest_fingerprint}/edge_catalogue_index_3B.parquet
    - edge_alias_blob_3B            @ seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_blob_3B.bin
    - edge_alias_index_3B           @ seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_index_3B.parquet
    - edge_universe_hash_3B         @ fingerprint={manifest_fingerprint}/edge_universe_hash_3B.json
    - virtual_routing_policy_3B     @ fingerprint={manifest_fingerprint}/virtual_routing_policy_3B.json
    - virtual_validation_contract_3B@ fingerprint={manifest_fingerprint}/virtual_validation_contract_3B.parquet
    - s4_run_summary_3B (optional)  @ fingerprint={manifest_fingerprint}/s4_run_summary_3B.json

[Policies, refs & RNG logs S5 must re-validate]
    - CDN/edge-budget policy pack(s) (for S2 checks)
    - spatial/tiling assets & world polygons used in S2
    - tz-world/tzdb/overrides (via civil_time_manifest) if relevant to S2 checks
    - alias-layout policy for 3B.S3
    - routing/RNG policy for 3B/2B
    - virtual_validation_policy_3B
    - Layer-1 RNG logs for S2:
        · rng_audit_log,
        · rng_trace_log,
        · S2-specific RNG event streams (e.g. edge_jitter events).

[Outputs owned by S5]
    - validation_bundle_3B
      @ data/layer1/3B/validation/fingerprint={manifest_fingerprint}/
      · directory containing:
            - evidence files (JSON, Parquet, logs, summaries…),
            - `index.json` (validation_bundle_index_3B),
            - `_passed.flag`,
            - optional `s5_manifest_3B.json`.
    - validation_bundle_index_3B
      @ data/layer1/3B/validation/fingerprint={manifest_fingerprint}/index.json
      · schema_ref: schemas.layer1.yaml#/validation/validation_bundle_index_3B
      · enumerates each evidence file with `{path, sha256_hex}`.

    - validation_passed_flag_3B
      @ data/layer1/3B/validation/fingerprint={manifest_fingerprint}/_passed.flag
      · schema_ref: schemas.layer1.yaml#/validation/passed_flag_3B
      · single line: `sha256_hex = <bundle_sha256_hex>`.

    - s5_manifest_3B  (optional, informative)
      @ data/layer1/3B/validation/fingerprint={manifest_fingerprint}/s5_manifest_3B.json
      · schema_ref: schemas.3B.yaml#/validation/s5_manifest_3B
      · captures manifest_fingerprint, parameter_hash, status, and a list of key evidence {logical_id, sha256_hex}.

[Numeric & RNG posture]
    - RNG:
        · S5 is **strictly RNG-free**:
            - MUST NOT advance Philox,
            - MUST NOT emit RNG events,
            - MUST NOT modify RNG logs.
    - Determinism:
        · Given identical inputs (identity triple, sealed_inputs_3B, S0–S4 artefacts, RNG logs, policies, refs),
          S5 MUST produce bit-identical:
              - evidence files inside validation_bundle_3B,
              - `index.json`,
              - `_passed.flag`,
              - `s5_manifest_3B` (if present).
    - Partitioning:
        · All S5 outputs are partitioned **only** by fingerprint={manifest_fingerprint};
          S5 MUST NOT introduce seed/parameter_hash/run_id as partitions.


----------------------------------------------------------------------
DAG — 3B.S5 (S0–S4 + RNG logs → validation bundle & `_passed.flag`)  [NO RNG]

### Phase A — Environment & input load (RNG-free)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S5.1) Load S0 artefacts & check upstream gates
                    - Resolve & validate:
                        · s0_gate_receipt_3B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3B@fingerprint={manifest_fingerprint}.
                    - Assert in s0_gate_receipt_3B:
                        · segment_id="3B", state_id="S0",
                        · manifest_fingerprint equals path token,
                        · (if present) seed and parameter_hash match S5’s run identity.
                    - Require upstream_gates in receipt:
                        · segment_1A.status == "PASS",
                        · segment_1B.status == "PASS",
                        · segment_2A.status == "PASS",
                        · segment_3A.status == "PASS".
                    - If any check fails or either artefact missing:
                        · S5 MUST NOT proceed to audits or bundle construction.

sealed_inputs_3B,
[Schema+Dict]
                ->  (S5.2) Resolve 3B S1–S4 artefacts via dictionary
                    - Resolve and schema-validate (using dictionary+registry):
                        · virtual_classification_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · virtual_settlement_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_catalogue_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_catalogue_index_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_alias_blob_3B@seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_blob_3B.bin,
                        · edge_alias_index_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_universe_hash_3B@fingerprint={manifest_fingerprint},
                        · virtual_routing_policy_3B@fingerprint={manifest_fingerprint},
                        · virtual_validation_contract_3B@fingerprint={manifest_fingerprint},
                        · s4_run_summary_3B (if present)@fingerprint={manifest_fingerprint}.
                    - Any missing or schema-invalid artefact ⇒ S5 MUST record a structural error and fail overall.

sealed_inputs_3B,
[Schema+Dict]
                ->  (S5.3) Resolve policies, refs & RNG logs
                    - Using sealed_inputs_3B and dictionary+registry, resolve:
                        · CDN/edge-budget policy,
                        · spatial/tiling assets & world polygons (if used in S2),
                        · tz-world/tzdb/overrides (if relevant to S2 checks),
                        · alias-layout policy for 3B.S3,
                        · routing/RNG policy (shared with 2B),
                        · virtual_validation_policy_3B,
                        · RNG logs for S2:
                              - rng_audit_log,
                              - rng_trace_log,
                              - S2-specific RNG event streams (e.g. edge jitter events).
                    - For each **external** artefact:
                        · locate matching row in sealed_inputs_3B,
                        · recompute SHA-256(raw bytes),
                        · assert equality with sealed_inputs_3B.sha256_hex.
                    - Any failure ⇒ configuration/sealing error; S5 MUST fail.

### Phase B — Structural & contract checks over S1–S4 (RNG-free)

virtual_classification_3B,
virtual_settlement_3B,
edge_catalogue_3B,
edge_catalogue_index_3B,
edge_alias_blob_3B,
edge_alias_index_3B,
edge_universe_hash_3B,
virtual_routing_policy_3B,
virtual_validation_contract_3B,
s4_run_summary_3B (if present),
policies & refs
                ->  (S5.4) Run S1–S4 structural checks & accumulate findings
                    - Initialise an internal check registry with fixed check_ids for:
                        · S1 classification/settlement,
                        · S2 edge catalogue & index,
                        · S3 alias & edge_universe_hash,
                        · S4 routing & validation contracts.
                    - **S1 checks** (virtual classification & settlement):
                        · each virtual merchant m in virtual_classification_3B:
                              - has exactly one row in virtual_settlement_3B (unless S1 spec allows explicit exceptions),
                              - tzid_settlement is non-null and valid (IANAtz),
                              - key constraints and schema invariants hold.
                    - **S2 checks** (edge catalogue & index):
                        · edge_catalogue_3B and edge_catalogue_index_3B conform to S2 schemas,
                        · for each merchant m:
                              - row count in edge_catalogue_3B with merchant_id=m equals edge_count_total(m) in index,
                        · global counts in index match total edge rows.
                    - **S3 checks** (alias artefacts & edge_universe_hash):
                        · edge_alias_index_3B schema-invariants (keys, layout_version, offsets, lengths, checksums),
                        · per-merchant alias metadata matches S2 edge counts,
                        · alias blob segments at (blob_offset_bytes, blob_length_bytes) decode to merchant_alias_checksum,
                        · blob_sha256_hex in header/index/global summary equals recomputed SHA-256(blob),
                        · component digests in edge_universe_hash_3B match recomputed digests of:
                              - CDN policy,
                              - spatial surfaces/tiling assets,
                              - RNG/alias policies,
                              - S2 catalogue,
                              - alias blob/index,
                        · recomputed edge_universe_hash matches edge_universe_hash_3B.universe_hash.
                    - **S4 checks** (routing & validation contracts):
                        · virtual_routing_policy_3B schema-valid, and if it includes edge_universe_hash/digests:
                              - those match edge_universe_hash_3B,
                              - referenced artefact manifest_keys resolve to S2/S3 outputs.
                        · virtual_validation_contract_3B schema-valid:
                              - `test_id` unique,
                              - `test_type`, `scope`, `severity` allowed by virtual_validation_policy_3B,
                              - `inputs.datasets` & `inputs.fields` refer to known datasets/fields,
                              - thresholds shapes & values conform to policy.
                        · If virtual_validation_contract_3B or s4_run_summary_3B carries digests of S1–S3 artefacts or policies:
                              - they must match recomputed digests.
                    - For any failure:
                        · record it against the appropriate check_id (status=FAIL/WARN),
                        · accumulate per-check affected_count and optional issue records.

### Phase C — RNG accounting for S2 (RNG-free)

edge_catalogue_3B,
tiling & jitter config (from S2 spec and policies),
rng_audit_log,
rng_trace_log,
S2-specific RNG event streams
                ->  (S5.5) Reconcile RNG usage vs S2 spec
                    - From edge_catalogue_3B and tiling/jitter policy:
                        · derive expected RNG usage for S2:
                              - number of jitter events per edge (min one per edge + retries bound),
                              - number of draws per jitter event (e.g. 2 uniforms per attempt),
                              - any additional RNG calls (e.g. tile assignment behaviour) and their per-edge/per-tile draw counts.
                    - Using RNG logs (rng_audit_log, rng_trace_log, S2-specific RNG event streams):
                        · filter to S2’s module and stream IDs,
                        · compute, per substream:
                              - total RNG events,
                              - total `draws` and `blocks`,
                              - monotonic counters (no wrap-around/reuse).
                    - Compare expected vs observed totals within policy-defined tolerances.
                    - If counts, draws or counters do not line up:
                        · mark RNG-related check(s) as FAIL,
                        · record RNG-accounting error in S5’s findings.

### Phase D — Evidence assembly & staging bundle (RNG-free)

all findings & metrics,
S0–S4 artefacts,
sealed_inputs_3B,
RNG logs,
policies & refs
                ->  (S5.6) Build evidence files for validation_bundle_3B (in staging directory)
                    - Create a **staging directory** for this manifest (not yet the final bundle path).
                    - Populate it with a stable set of evidence files, e.g.:
                        · S0 evidence:
                              - s0_gate_receipt_3B.json
                              - sealed_inputs_3B.parquet (or digest manifest)
                        · Structural summaries:
                              - copies or digests of virtual_classification_3B, virtual_settlement_3B,
                                edge_catalogue_3B, edge_catalogue_index_3B,
                                edge_alias_index_3B, edge_universe_hash_3B,
                                virtual_routing_policy_3B, virtual_validation_contract_3B,
                              - RNG summary JSON (S2 RNG-accounting checks),
                              - S4 run summary (if present).
                        · S5 findings:
                              - S5 structural-check summary JSON,
                              - optional issues table / failure list.
                        · Policy & config snapshots/digests as per S5 spec.
                    - Evidence MUST be written under the staging root with **relative paths** only (no `..`, no absolute).
                    - On any write/validation error:
                        · S5 MUST abandon staging and fail; no partial bundle is published.

### Phase E — Build `validation_bundle_index_3B` (index.json)  [RNG-free]

staging directory (evidence files),
schemas.layer1.yaml
                ->  (S5.7) Construct `index.json` describing the bundle
                    - Enumerate all evidence files under the staging root, **excluding `_passed.flag`** (which does not yet exist).
                    - For each file:
                        · compute SHA-256 over its raw bytes → sha256_hex,
                        · compute its relative path from the staging root (no leading "/", no `.`/`..` segments).
                    - Build index object:
                        · `files`: array of `{ "path": "<relative_path>", "sha256_hex": "<digest>" }`.
                    - Sort entries by `path` in strict ASCII lexicographic order.
                    - Write `index.json` into the staging root.
                    - Validate index.json against `schemas.layer1.yaml#/validation/validation_bundle_index_3B`.
                    - Any error in enumeration, hashing, or writing index.json ⇒ S5 MUST fail without publishing.

### Phase F — Bundle hash, `_passed.flag` & atomic publish (RNG-free)

index.json (in staging),
evidence files (in staging)
                ->  (S5.8) Compute bundle_sha256 over staged evidence
                    - Re-open index.json from staging and parse entries.
                    - For each file entry in `files[]`, in ASCII-sorted order of `path`:
                        · read the referenced file’s raw bytes from staging root + path,
                        · append bytes to a hashing stream.
                    - Compute:
                        · `bundle_sha256 = SHA256(concat(all indexed file bytes in sorted path order))`.
                    - Encode `bundle_sha256` as 64-character lowercase hex string `bundle_sha256_hex`.

bundle_sha256_hex,
schemas.layer1.yaml
                ->  (S5.9) Construct `_passed.flag` content
                    - Logical content: `{ sha256_hex = bundle_sha256_hex }`.
                    - On disk:
                        · single ASCII line:
                              `sha256_hex = <bundle_sha256_hex>`
                          terminated by a single newline (as per passed_flag_3B schema).
                    - Validate this representation against `schemas.layer1.yaml#/validation/passed_flag_3B`.
                    - Write `_passed.flag` into the staging root.

parameter_hash,
manifest_fingerprint,
bundle_sha256_hex,
selected evidence logical_ids & digests
                ->  (S5.10) Construct optional `s5_manifest_3B` object
                    - Build JSON object conforming to schemas.3B.yaml#/validation/s5_manifest_3B:
                        · manifest_fingerprint,
                        · parameter_hash,
                        · status ∈ {"PASS","FAIL"}:
                              - "PASS" if all planned checks succeeded and bundle constructed,
                              - "FAIL" if S5 is emitting a diagnostic manifest for partial runs (implementation choice).
                        · evidence: array of minimal evidence references:
                              - {logical_id, sha256_hex} for key artefacts
                                (e.g. edge_universe_hash_3B, virtual_routing_policy_3B, virtual_validation_contract_3B).
                    - Write `s5_manifest_3B.json` to the staging root.
                    - This artefact is **informative** only; bundle semantics are governed by index.json + `_passed.flag`.

staging directory (with evidence, index.json, _passed.flag, s5_manifest_3B),
final bundle path from dictionary
                ->  (S5.11) Atomic publish of `validation_bundle_3B`, `index.json`, `_passed.flag`, `s5_manifest_3B`
                    - Final bundle directory (via dictionary `validation_bundle_3B`):
                        · data/layer1/3B/validation/fingerprint={manifest_fingerprint}/
                    - If the final directory does **not** exist:
                        · atomically rename/move the entire staging directory to the final bundle path.
                    - If the final directory exists:
                        · load existing index.json & evidence files,
                        · recompute bundle_sha256 from existing files using the same law,
                        · compare to new bundle_sha256_hex:
                              - if equal and each file is byte-identical → idempotent re-run; OK,
                              - if not equal → immutability violation; S5 MUST NOT overwrite.
                    - After publish:
                        · ensure that index.json and `_passed.flag` are present together,
                        · ensure there is no state where one exists without the other.

Downstream touchpoints
----------------------
- **All consumers of 3B artefacts** (2B routing, validation harnesses, tooling) MUST treat 3B as PASS for a manifest only if:
    1. `validation_bundle_3B` exists at `data/layer1/3B/validation/fingerprint={manifest_fingerprint}/`,
    2. `index.json` is schema-valid and lists the evidence files,
    3. `_passed.flag` exists at the same root and is schema-valid,
    4. recomputing `bundle_sha256` from index.json’s entries yields the same hex as `_passed.flag.sha256_hex`.

- **3B HashGate rule:**
    - For any 3B dataset (e.g. `virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`,
      `edge_alias_blob_3B`, `virtual_routing_policy_3B`, `virtual_validation_contract_3B`, `edge_universe_hash_3B`),
      downstream MUST enforce:

          **No PASS (S5 bundle+flag) → No read/use** of that 3B artefact for this manifest_fingerprint.

- **Layer-wide 4A/4B & external verifiers:**
    - Use `validation_bundle_3B` and `_passed.flag` as the 3B-level HashGate;
      they may apply additional global conditions, but MUST NOT bypass or weaken S5’s bundle law.
```
