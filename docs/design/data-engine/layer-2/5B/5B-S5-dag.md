```
        LAYER 2 · SEGMENT 5B — STATE S5 (VALIDATION BUNDLE & `_PASSED.FLAG_5B`)  [NO RNG]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5B
      @ data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5B.json
      · provides, for this fingerprint:
          - manifest_fingerprint, parameter_hash, seed, run_id,
          - scenario_set_5B (the scenarios 5B intends to cover),
          - verified_upstream_segments.{1A,1B,2A,2B,3A,3B,5A},
          - sealed_inputs_digest (SHA-256 over sealed_inputs_5B rows),
          - spec_version.
      · S5 MUST:
          - trust upstream PASS/FAIL/MISSING status as given,
          - treat sealed_inputs_digest as the canonical fingerprint of 5B’s input universe.

    - sealed_inputs_5B
      @ data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet
      · closed-world inventory of artefacts that 5B states may read:
          - each row: {owner_layer, owner_segment, artifact_id, manifest_key,
                       path_template, partition_keys[], schema_ref,
                       sha256_hex, role, status, read_scope, source_dictionary, source_registry}.
      · S5 MUST:
          - only resolve artefacts that appear in this table,
          - ensure every artefact it actually reads is covered by sealed_inputs_5B.

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml                  (RNG envelope, rng_audit_log, rng_trace_log, RNG event schemas)
    - schemas.layer2.yaml                  (Layer-2 validation bundle/report/index/flag schemas)
    - schemas.5B.yaml                      (5B segment-specific anchors, if used by S5)
    - dataset_dictionary.layer2.5B.yaml    (5B dataset contracts)
        · includes:
            - s0_gate_receipt_5B, sealed_inputs_5B,
            - s1_time_grid_5B, s1_grouping_5B,
            - s2_realised_intensity_5B,
            - s3_bucket_counts_5B,
            - s4_arrival_events_5B,
            - validation_report_5B,
            - validation_issue_table_5B,
            - validation_bundle_index_5B (index.json),
            - validation_passed_flag_5B  (`_passed.flag_5B`).
    - dataset_dictionary.layer1.*.yaml + artefact_registry_{1A,1B,2A,2B,3A,3B,5A,5B}.yaml
        · used only to resolve logical IDs ↔ paths/schema_refs, never via hard-coded paths.

[5B data-plane artefacts to validate (S0–S4)]
    - S0:
        · s0_gate_receipt_5B, sealed_inputs_5B.
    - S1:
        · s1_time_grid_5B@fingerprint={mf}/scenario_id={sid}
        · s1_grouping_5B@fingerprint={mf}/scenario_id={sid}
    - S2:
        · s2_realised_intensity_5B@seed={seed}/fingerprint={mf}/scenario_id={sid}
    - S3:
        · s3_bucket_counts_5B@seed={seed}/fingerprint={mf}/scenario_id={sid}
    - S4:
        · s4_arrival_events_5B@seed={seed}/fingerprint={mf}/scenario_id={sid}

    Across these datasets, the 5B domain is:
        DOMAIN_5B(mf) = { (parameter_hash, scenario_id, seed) }
        for which s3_bucket_counts_5B and s4_arrival_events_5B both have partitions.

[RNG logs (Layer-wide, for 5B.S2–S4)]
    - rng_audit_log, rng_trace_log    (Layer-wide RNG summaries)
    - RNG event tables for 5B’s families:
        · S2 latent-field draws,
        · S3 bucket-count draws,
        · S4 micro-time and routing draws.
    - These MUST be present and schema-valid for mf; S5 will reconcile expected vs observed draws/blocks and counters.

[Validation configs (5B-specific)]
    - 5B validation policy / config (if present)
        · defines check IDs, severities, and any numeric tolerances that are not hard-wired in S5.
        · MUST itself be listed in sealed_inputs_5B.

[Outputs owned by S5]
    - validation_report_5B
      @ data/layer2/5B/validation/fingerprint={manifest_fingerprint}/validation_report_5B.json
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer2.yaml#/validation/validation_report_5B
      · single JSON object per fingerprint with:
            manifest_fingerprint,
            status ∈ {"PASS","FAIL"},
            checks[] (id, status, severity, affected_count, description),
            metrics (domain sizes, max deviations, RNG stats, etc.),
            domain_summary (per (parameter_hash,scenario_id,seed) if desired),
            error_code (if FAIL).

    - validation_issue_table_5B   (optional)
      @ data/layer2/5B/validation/fingerprint={manifest_fingerprint}/validation_issue_table_5B.parquet
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer2.yaml#/validation/validation_issue_table_5B
      · 0+ rows, each describing an issue:
            {manifest_fingerprint, parameter_hash, scenario_id, seed,
             check_id, issue_code, severity, entity keys, message, ...}.

    - validation_bundle_index_5B
      @ data/layer2/5B/validation/fingerprint={manifest_fingerprint}/index.json
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer2.yaml#/validation/validation_bundle_index_5B
      · describes bundle members:
            entries[] = {logical_id/role, path, sha256_hex, schema_ref?}, paths relative to bundle root.

    - validation_passed_flag_5B   (`_passed.flag_5B`)
      @ data/layer2/5B/validation/fingerprint={manifest_fingerprint}/_passed.flag_5B
      · partition_keys: [fingerprint]
      · schema_ref: schemas.layer2.yaml#/validation/passed_flag_5B
      · single logical field:
            sha256_hex = <bundle_digest_sha256>,
        represented as a tiny file (e.g. text line `sha256_hex = <hex>`).


[Numeric & RNG posture]
    - S5 is **RNG-free**:
        · MUST NOT open or advance Philox or any RNG stream,
        · MUST NOT emit RNG events or mutate RNG logs.
    - Determinism:
        · For a fixed `manifest_fingerprint` and fixed inputs (S0–S4 outputs, RNG logs, configs),
          S5 MUST produce byte-identical:
              validation_report_5B,
              validation_issue_table_5B (if present),
              validation_bundle_index_5B,
              validation_passed_flag_5B.
    - Scope:
        · S5 covers the entire 5B domain under `mf`:
              all (parameter_hash, scenario_id, seed) that have S3 counts & S4 events.
        · S5 MUST NOT claim PASS for `mf` if any part of that domain is missing or fails checks.


----------------------------------------------------------------------
DAG — 5B.S5 (S0–S4 + RNG logs → validation report + bundle + `_passed.flag_5B`)  [NO RNG]

### Phase 1 — Discovery (domain & evidence set)

[Schema+Dict],
s0_gate_receipt_5B,
sealed_inputs_5B
                ->  (S5.1) Load gate & sealed_inputs; check consistency
                    - Resolve s0_gate_receipt_5B and sealed_inputs_5B via 5B dictionary.
                    - Validate both against schemas.5B.yaml.
                    - Recompute SHA-256 over sealed_inputs_5B rows (canonical sort + serialisation);
                      require equality with `sealed_inputs_digest` in receipt.
                    - Check `verified_upstream_segments` in receipt:
                        · all required segments (1A–3B, 5A, 3B) MUST have status="PASS".
                    - Any mismatch or upstream FAIL/MISSING:
                        · S5 MUST fail and MUST NOT publish a PASS-looking bundle or flag.

sealed_inputs_5B,
dataset_dictionary.layer2.5B.yaml
                ->  (S5.2) Enumerate 5B domain under mf: RUNS = {(ph, sid, seed)}
                    - Using dataset_dictionary.layer2.5B.yaml + sealed_inputs_5B:
                        · enumerate all `(parameter_hash, scenario_id, seed)` triples such that:
                              - s3_bucket_counts_5B exists at:
                                    seed={seed}/fingerprint={mf}/scenario_id={sid}/…,
                              - AND s4_arrival_events_5B exists at:
                                    seed={seed}/fingerprint={mf}/scenario_id={sid}/….
                    - Define 5B domain:
                        · RUNS(mf) = {(ph, sid, seed)} from this intersection.
                    - Derive canonical ordering:
                        · sort RUNS by parameter_hash, then scenario_id, then seed.
                    - S5 MUST treat RUNS(mf) as the complete 5B domain for this fingerprint.
                    - If s3_bucket_counts_5B exists for a triple and s4_arrival_events_5B does not:
                        · this is a validation failure; S5 MUST record a `5B.S5.DOMAIN_INCOMPLETE` issue and FAIL.

sealed_inputs_5B
                ->  (S5.3) Resolve physical paths for S0–S4 artefacts & RNG logs
                    - Using sealed_inputs_5B + dictionaries/registries, S5 resolves paths for:
                        · all S0–S4 datasets under mf:
                              s0_gate_receipt_5B, sealed_inputs_5B,
                              s1_time_grid_5B, s1_grouping_5B,
                              s2_realised_intensity_5B,
                              s3_bucket_counts_5B,
                              s4_arrival_events_5B,
                        · relevant upstream geometry/time/routing/virtual/intensity artefacts,
                        · RNG logs (`rng_audit_log`, `rng_trace_log`, RNG event tables for S2,S3,S4),
                        · 5B validation policy/configs.
                    - S5 MUST NOT resolve or read artefacts that are not listed in sealed_inputs_5B.

### Phase 2 — Validation of S0–S4 invariants (no RNG)

RUNS,
s0_gate_receipt_5B,
sealed_inputs_5B
                ->  (S5.4) Check S0 invariants (gate & sealed inputs)
                    - Confirm:
                        · s0_gate_receipt_5B schema-valid and bound to this mf,
                        · all artefacts S5 resolved in 5.3 are present in sealed_inputs_5B
                          with matching (owner_layer, owner_segment, artifact_id, path_template, schema_ref),
                        · any REQUIRED artefact is present and not marked MISSING.
                    - Any missing or mismatched artefact:
                        · mark check `CHECK_S0_SEALED_INPUTS` as FAIL,
                        · S5 overall status MUST be FAIL.

RUNS,
s1_time_grid_5B,
s1_grouping_5B,
s2_realised_intensity_5B,
s3_bucket_counts_5B
                ->  (S5.5) Check S1–S3 invariants (grid, domain & counts)
                    - For each (ph, sid, seed) ∈ RUNS:
                        · Load:
                              s1_time_grid_5B(mf,sid),
                              s1_grouping_5B(mf,sid),
                              s2_realised_intensity_5B(seed,mf,sid),
                              s3_bucket_counts_5B(seed,mf,sid).
                        - S1 grid:
                              - buckets cover the scenario’s horizon fully with no overlaps or gaps,
                              - partition keys & columns match mf,sid.
                        - S1 grouping:
                              - every s2/s3 entity key appears in s1_grouping_5B,
                              - no stray keys not in grouping.
                        - S2 intensities:
                              - domain matches s1_grouping×time_grid domain (as required by config),
                              - lambda_realised ≥ 0 and finite.
                        - S3 counts:
                              - every (key,b) row in s3_bucket_counts_5B has a matching λ_realised row,
                              - count_N is integer ≥ 0,
                              - any per-bucket numeric guardrails from S3 config.
                    - Any violation:
                        · record corresponding check as FAIL (e.g. `CHECK_S1_GRID`, `CHECK_S2_DOMAIN`, `CHECK_S3_COUNTS`),
                        · increase affected_count and record issues.

RUNS,
s3_bucket_counts_5B,
s4_arrival_events_5B,
s1_time_grid_5B
                ->  (S5.6) Check S4 vs S3: count & time invariants
                    - For each (ph, sid, seed) ∈ RUNS:
                        1. Load s3_bucket_counts_5B and s4_arrival_events_5B for (seed,mf,sid).
                        2. For each bucket row (key,b) from S3:
                               - let N = count_N(key,b).
                               - count arrivals in S4 with same (mf,seed,sid,key,b).
                               - require:
                                     arrivals_count(key,b) == N.
                               - require:
                                     - if N == 0 → no arrivals for (key,b),
                                     - if N > 0 → exactly N arrivals.
                        3. For each arrival event in S4:
                               - bucket_index b MUST exist in s1_time_grid_5B(sid),
                               - ts_utc MUST lie within [bucket_start_utc(b), bucket_end_utc(b)) according to bucket law.
                    - Any mismatch:
                        · mark `CHECK_S4_COUNTS` or `CHECK_S4_BUCKET_TIMES` as FAIL,
                        · log individual issues with entity keys & bucket_index.

RUNS,
s4_arrival_events_5B,
2A civil-time artefacts,
2B routing surfaces,
3B virtual routing surfaces
                ->  (S5.7) Check civil time & routing invariants
                    - For each (ph, sid, seed) ∈ RUNS and each arrival event:
                        · Civil time:
                              - using 2A’s tz_timetable_cache and tz rules:
                                    * recompute ts_local from ts_utc + tzid_local,
                                    * confirm that ts_local matches or is consistent with stored ts_local/local_dow,
                                    * ensure no arrival is placed in an impossible DST region (unless 2A defines behaviour).
                        · Routing for physical arrivals (is_virtual=false):
                              - check site_id is valid in site_locations,
                              - ensure chosen site_id is reachable from 2B routing plan given (merchant,zone,channel),
                              - for simple local checks: confirm site’s country/zone consistent with zone_representation.
                        · Routing for virtual arrivals (is_virtual=true):
                              - check edge_id is valid in edge_catalogue_3B,
                              - ensure edge universe matches edge_universe_hash_3B,
                              - verify that virtual_routing_policy_3B would allow this edge for this merchant/scenario.
                    - S5 does NOT re-run the full 2B/3B routing algorithms; it only checks S4 outputs are compatible
                      with authoritative surfaces and policies.
                    - Any violation:
                        · mark checks (e.g. `CHECK_S4_CIVIL_TIME`, `CHECK_S4_ROUTING_COMPAT`) as FAIL.

RUNS,
s4_arrival_events_5B,
schemas.5B.yaml
                ->  (S5.8) Schema / partition / PK checks for S4 egress
                    - For each (mf,sid,seed) partition of s4_arrival_events_5B:
                        · validate against schemas.5B.yaml#/model/s4_arrival_events_5B:
                              - required fields, types, allowed enums.
                        · confirm partition keys:
                              - `seed` column = seed path token,
                              - `manifest_fingerprint` column = mf,
                              - `scenario_id` column = sid.
                        · confirm PK uniqueness for whatever primary key the schema defines
                          (e.g. composite of (seed,mf,sid,merchant_id,zone_representation,channel_group,bucket_index,arrival_seq)).
                    - Any violation:
                        · mark `CHECK_S4_SCHEMA_PK` as FAIL.

### Phase 3 — RNG accounting checks (no RNG, read-only)

RUNS,
RNG events for S2,S3,S4,
rng_trace_log,
arrival_lgcp_config_5B,
arrival_count_config_5B,
s4_time_placement_policy_5B,
s4_routing_policy_5B
                ->  (S5.9) Check RNG accounting for S2, S3, S4
                    - For each (ph, mf, sid, seed) ∈ RUNS:
                        · derive **expected** draw counts per RNG family from:
                              - S2 domain (groups × buckets),
                              - S3 domain (entities × buckets),
                              - S4 arrivals (number of arrivals; may differ per family: time, site pick, edge pick).
                        · Using RNG event tables:
                              - aggregate **actual** draws & blocks per family and per run_id (if relevant),
                              - check that:
                                    * actual draws == expected draws,
                                    * actual blocks match expected (if specified),
                                    * counters are monotonically increasing with no overlaps.
                        · Cross-check with rng_trace_log & rng_audit_log:
                              - totals in trace/audit must match aggregated events for 5B’s families.
                    - Any mismatch or counter anomaly:
                        · mark `CHECK_RNG_ACCOUNTING` as FAIL.

### Phase 4 — Evidence materialisation (no RNG)

check registry & metrics,
issue list,
schemas.layer2.yaml
                ->  (S5.10) Build validation_report_5B & validation_issue_table_5B
                    - Determine overall_status:
                        · "FAIL" if any check has status="FAIL",
                        · "PASS" otherwise (WARNs/INFO allowed).
                    - Build `validation_report_5B` JSON with:
                        · manifest_fingerprint,
                        · overall_status,
                        · checks[] = {check_id, status, severity, affected_count, description},
                        · metrics{} = domain sizes, max deviations, RNG stats, counts of FAIL/WARN, etc.,
                        · error_code = first or most severe failure code (if FAIL).
                    - Build `validation_issue_table_5B` rows (if issue list non-empty) with:
                        · event-level or entity-level issues, each referencing:
                              manifest_fingerprint, parameter_hash, scenario_id, seed,
                              check_id, issue_code, severity, entity keys, message.
                    - Validate:
                        · validation_report_5B against schemas.layer2.yaml#/validation/validation_report_5B,
                        · validation_issue_table_5B (if not empty) against schemas.layer2.yaml#/validation/validation_issue_table_5B.

validation_report_5B,
validation_issue_table_5B,
dataset_dictionary.layer2.5B.yaml
                ->  (S5.11) Write validation_report_5B & validation_issue_table_5B (fingerprint-only, write-once)
                    - Target paths from dictionary:
                        · validation_report_5B:
                              data/layer2/5B/validation/fingerprint={mf}/validation_report_5B.json
                        · validation_issue_table_5B:
                              data/layer2/5B/validation/fingerprint={mf}/validation_issue_table_5B.parquet
                              (written only if there are any issue rows, or as an explicit empty table if spec requires).
                    - For each artefact:
                        · if file/dataset does not exist:
                              - write via staging → fsync → atomic move.
                        · if it exists:
                              - read existing, normalise logical content,
                              - if byte-identical → idempotent re-run; OK,
                              - else → immutability conflict; S5 MUST NOT overwrite.

                    - If overall_status="FAIL":
                        · S5 MUST still persist validation_report_5B (and issues), but:
                              - MUST NOT proceed to build a PASS bundle+flag.

### Phase 5 — Bundle assembly (`validation_bundle_5B`)  [NO RNG]

validation_report_5B,
validation_issue_table_5B,
any additional evidence files,
schemas.layer2.yaml
                ->  (S5.12) Select bundle members & compute per-file digests
                    - Bundle root:
                        · B_root = data/layer2/5B/validation/fingerprint={mf}/
                    - Select bundle members (at minimum):
                        · validation_report_5B.json,
                        · validation_issue_table_5B.parquet (if present),
                        · any extra 5B receipts / RNG summary files if you choose to include them.
                    - `_passed.flag_5B` MUST NOT be included as a member.
                    - For each selected file f:
                        · compute its relative path p under B_root (no leading "/", no "."/".."),
                        · read raw bytes of f,
                        · compute sha256_hex(f) = SHA256(raw_bytes), as lowercase hex.
                    - Build an array `entries` = [
                          {logical_id/role, path=p, sha256_hex=sha256_hex(f), schema_ref?}, …
                      ].
                    - Sort entries by `path` in strict ASCII-lex order.

entries,
schemas.layer2.yaml
                ->  (S5.13) Write validation_bundle_index_5B (index.json)
                    - Construct index object conforming to schemas.layer2.yaml#/validation/validation_bundle_index_5B:
                        · includes bundle metadata (manifest_fingerprint, spec_version, etc.),
                        · includes `entries` as constructed above.
                    - Serialise index object to JSON with a stable serializer (key order deterministic).
                    - Target path:
                        · data/layer2/5B/validation/fingerprint={mf}/index.json
                    - Immutability:
                        · if index.json does not exist:
                              - write via staging → fsync → atomic move.
                        · if index.json exists:
                              - read existing, parse and normalise logical content,
                              - if logically identical → idempotent re-run; OK,
                              - else → bundle-index conflict; MUST NOT overwrite.

### Phase 6 — Bundle digest & `_passed.flag_5B`  [NO RNG]

validation_bundle_index_5B,
bundle members on disk
                ->  (S5.14) Compute bundle_digest_sha256
                    - Re-read index.json and extract `entries` in its stored order
                      (which MUST be ASCII-lex by `path`).
                    - For each entry e in `entries`:
                        · open the file at B_root / e.path,
                        · read its raw bytes,
                        · append those bytes to a hash stream.
                    - Compute:
                        · bundle_digest_sha256 = SHA256(concatenated_bytes),
                          encoded as 64-char lowercase hex.
                    - This is the **single 5B bundle digest** for manifest_fingerprint = mf.

bundle_digest_sha256,
schemas.layer2.yaml
                ->  (S5.15) Write validation_passed_flag_5B (`_passed.flag_5B`)
                    - Logical payload:
                        · sha256_hex = bundle_digest_sha256.
                    - On disk representation (per schemas.layer2.yaml#/validation/passed_flag_5B):
                        · e.g. a single ASCII line:
                              `sha256_hex = <bundle_digest_sha256>`
                          with a trailing newline.
                    - Target path:
                        · data/layer2/5B/validation/fingerprint={mf}/_passed.flag_5B
                    - Immutability:
                        · if file does not exist:
                              - write via staging → fsync → atomic move.
                        · if file exists:
                              - read, parse sha256_hex,
                              - if existing value == bundle_digest_sha256 → idempotent re-run; OK,
                              - else → HashGate conflict; MUST NOT overwrite.

Downstream touchpoints
----------------------
- **Layer-3 (6A/6B, ingestion, analytics):**
    - MUST treat 5B as PASS for a given `manifest_fingerprint` only if:
          1. validation_bundle_index_5B exists at the fingerprint path and is schema-valid,
          2. `_passed.flag_5B` exists at the same root and is schema-valid,
          3. recomputing `bundle_digest_sha256` from bundle members yields
             the same value as `_passed.flag_5B.sha256_hex`,
          4. validation_report_5B.status == "PASS".
    - If any of these are false:
          **No 5B PASS → No read/use of `s4_arrival_events_5B` or any other 5B egress.**

- **5B authority boundary recap:**
    - S0–S4 own the construction of the arrival world (inputs → intensities → counts → arrivals).
    - S5 owns only:
          - checking that 5B’s world is self-consistent and policy-compliant,
          - building a fingerprint-scoped validation bundle for 5B,
          - computing the 5B HashGate (`_passed.flag_5B`).
```