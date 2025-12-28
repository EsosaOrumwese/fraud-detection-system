```text
        LAYER 3 · SEGMENT 6B — STATE S5 (SEGMENT VALIDATION & 6B HASHGATE)  [RNG-FREE]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[S0 gate & sealed inputs]
    - s0_gate_receipt_6B
      @ data/layer3/6B/gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json
      · For this world:
          - manifest_fingerprint        (world id),
          - parameter_hash              (6B parameter pack id),
          - run_id                      (execution id; S5 MUST NOT depend on it),
          - spec_version_6B             (contract version),
          - upstream_segments{seg_id → {status,bundle_path,bundle_sha256,flag_path}},
          - contracts_6B{logical_id → {path,sha256_hex,schema_ref,role}},
          - sealed_inputs_digest_6B.
      · S5 MUST:
          - load & validate this before doing any work,
          - require status="PASS" for all required upstream segments {1A,1B,2A,2B,3A,3B,5A,5B,6A},
          - treat upstream_segments as the **only** source of truth on upstream HashGates.

    - sealed_inputs_6B
      @ data/layer3/6B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet
      · One row per artefact 6B may read:
          - owner_layer, owner_segment, manifest_key,
          - path_template, partition_keys[], schema_ref,
          - sha256_hex, role, status, read_scope.
      · S5 MUST:
          - recompute sealed_inputs_digest_6B (canonical serialisation) and
            require equality with s0_gate_receipt_6B.sealed_inputs_digest_6B,
          - only read artefacts listed here,
          - honour status (REQUIRED/OPTIONAL/IGNORED),
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → presence/shape checks only.

[Schema+Dict · shape & catalogue authority]
    - schemas.layer3.yaml, schemas.6B.yaml
        · shape authority for:
              - all 6B S1–S4 datasets,
              - s5_validation_report_6B,
              - s5_issue_table_6B,
              - validation_bundle_index_6B,
              - validation_passed_flag_6B.
    - dataset_dictionary.layer3.6B.yaml
        · IDs/contracts for S1–S4 datasets, including:
              - s1_arrival_entities_6B,
              - s1_session_index_6B,
              - s2_flow_anchor_baseline_6B,
              - s2_event_stream_baseline_6B,
              - s3_campaign_catalogue_6B,
              - s3_flow_anchor_with_fraud_6B,
              - s3_event_stream_with_fraud_6B,
              - s4_flow_truth_labels_6B,
              - s4_flow_bank_view_6B,
              - s4_event_labels_6B,
              - s4_case_timeline_6B.
        · IDs/contracts for S5 outputs:
              - s5_validation_report_6B
                · path:
                    data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6B.json
                · partitioning: [fingerprint]
                · primary_key: [manifest_fingerprint]
                · schema_ref: schemas.layer3.yaml#/validation/6B/s5_validation_report
              - s5_issue_table_6B
                · path:
                    data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6B.parquet
                · partitioning: [fingerprint]
                · primary_key:
                      [manifest_fingerprint, check_id, issue_id]
                · schema_ref: schemas.layer3.yaml#/validation/6B/s5_issue_table
              - validation_bundle_6B
                · directory:
                    data/layer3/6B/validation/fingerprint={manifest_fingerprint}/
                · schema_ref: schemas.layer3.yaml#/validation/6B/validation_bundle_index_6B
              - validation_passed_flag_6B
                · path:
                    data/layer3/6B/validation/fingerprint={manifest_fingerprint}/_passed.flag
                · partitioning: [fingerprint]
                · primary_key: [manifest_fingerprint]
                · schema_ref: schemas.layer3.yaml#/validation/6B/passed_flag_6B

[Upstream 6B data-plane surfaces (S1–S4)]
    - S1 (attachment & sessions):
        · s1_arrival_entities_6B
        · s1_session_index_6B
    - S2 (baseline flows & events):
        · s2_flow_anchor_baseline_6B
        · s2_event_stream_baseline_6B
    - S3 (fraud & abuse overlay):
        · s3_campaign_catalogue_6B
        · s3_flow_anchor_with_fraud_6B
        · s3_event_stream_with_fraud_6B
    - S4 (truth & bank-view labels + cases):
        · s4_flow_truth_labels_6B
        · s4_flow_bank_view_6B
        · s4_event_labels_6B
        · s4_case_timeline_6B
    - S5 MUST:
        - treat these as **read-only**,
        - NEVER patch or rewrite them,
        - rely on them, together with policies, to determine structural and behavioural health.

[RNG logs & trace surfaces (for S1–S4)]
    - rng_event_* datasets for 6B families:
        · rng_event_entity_attach, rng_event_session_boundary   (S1),
        · rng_event_flow_shape, rng_event_event_timing,
          rng_event_amount_draw                                  (S2),
        · rng_event_campaign_activation, rng_event_campaign_targeting,
          rng_event_overlay_mutation                             (S3),
        · rng_event_truth_label_ambiguity, rng_event_detection_delay,
          rng_event_dispute_delay, rng_event_chargeback_delay,
          rng_event_case_timeline                                (S4).
    - rng_trace_log (Layer-3)
      · per-stream envelopes: counters, blocks, draws per family.
    - S5 MUST:
        - treat these as the sole record of RNG usage for S1–S4,
        - perform only deterministic aggregation over them (no new RNG).

[6B configuration & validation policy]
    - segment_validation_policy_6B
      · defines:
          - the list of structural checks, behavioural checks, RNG checks,
          - severity per check (REQUIRED, WARN, INFO),
          - numeric thresholds and acceptable ranges for metrics (fraud rate, detection rate, etc.),
          - which checks are fatal (FAIL terminates HashGate) vs non-fatal (WARN-only).
    - behaviour_config_6B (if used at validation time)
      · may define which seeds/scenarios are in scope, and which checks apply to which segments.

[Outputs owned by S5]
    - s5_validation_report_6B
      @ data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6B.json
      · partitioning: [fingerprint]
      · primary_key: [manifest_fingerprint]
      · logical content:
            - manifest_fingerprint, parameter_hash, spec_version_6B,
            - overall_status ∈ {PASS, FAIL},
            - per-check entries:
                  check_id, severity, result ∈ {PASS, WARN, FAIL},
                  metrics (per-check numeric summaries),
                  thresholds (where applicable),
            - metadata: evaluated_seeds, evaluated_scenarios, policy ids, created_utc.

    - s5_issue_table_6B   (optional)
      @ data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6B.parquet
      · partitioning: [fingerprint]
      · primary_key: [manifest_fingerprint, check_id, issue_id]
      · logical content:
            - manifest_fingerprint,
            - check_id, issue_id,
            - severity, result,
            - location fields (e.g. seed, scenario_id, flow_id, campaign_id, case_id),
            - message, details,
            - metrics snapshot (if per-issue),
            - policy ids.

    - validation_bundle_6B  (directory)
      @ data/layer3/6B/validation/fingerprint={manifest_fingerprint}/
      · contains:
            - index.json     (validation_bundle_index_6B),
            - s5_validation_report_6B,
            - s5_issue_table_6B (if present),
            - any additional evidence files included by policy,
            - _passed.flag (HashGate flag; see below).

    - validation_passed_flag_6B  (`_passed.flag`)
      @ data/layer3/6B/validation/fingerprint={manifest_fingerprint}/_passed.flag
      · text file with single logical field:
            sha256_hex = <64-hex-of-bundle-digest>
      · MUST be produced only when overall_status="PASS" under segment_validation_policy_6B.

DAG — 6B.S5 (S0–S4 surfaces + RNG logs → 6B validation report + HashGate)  [RNG-FREE]
--------------------------------------------------------------------------------------

### Phase 1 — Gate, domain discovery & policy

[S0 gate & sealed_inputs_6B],
[Schema+Dict]
                ->  (S5.1) Verify S0 gate & sealed_inputs_6B  (no RNG)
                    - Resolve s0_gate_receipt_6B and sealed_inputs_6B via Layer-3 dictionary.
                    - Validate both against schemas.layer3.yaml and schemas.6B.yaml.
                    - Recompute sealed_inputs_digest_6B from sealed_inputs_6B
                      (canonical row order + serialisation) and require equality with value in receipt.
                    - Check upstream_segments in receipt:
                          all required upstream segments {1A,1B,2A,2B,3A,3B,5A,5B,6A} MUST have status="PASS".
                    - If any check fails:
                          S5 MUST NOT proceed to S1–S4 validation and MUST record a precondition failure.

sealed_inputs_6B,
dataset_dictionary.layer3.6B.yaml,
artefact_registry_6B
                ->  (S5.2) Determine 6B work domain (seeds, scenarios)  (no RNG)
                    - Using sealed_inputs_6B and dictionaries:
                          · identify which datasets correspond to S1–S4 surfaces and RNG logs,
                          · enumerate all (seed, scenario_id) partitions present for S2/S3/S4 outputs
                            (the “behavioural workload” for this world).
                    - Build:
                          · world_seeds   = set of seeds in scope,
                          · world_scenarios = set of scenario_id in scope.
                    - If behaviour_config_6B restricts seeds/scenarios, intersect accordingly.
                    - If the resulting domain is empty but 6B is expected to be active for this world:
                          · S5 MUST treat it as a configuration error (precondition failure).

segment_validation_policy_6B
                ->  (S5.3) Load & validate segment_validation_policy_6B  (no RNG)
                    - Resolve policy path from sealed_inputs_6B and artefact_registry_6B.
                    - Validate against schemas.layer3.yaml#/validation/6B/segment_validation_policy.
                    - Extract:
                          · structural_checks[],
                          · behavioural_checks[],
                          · rng_checks[],
                          · severity/threshold maps.
                    - If policy is missing or invalid:
                          · S5 MUST stop with precondition failure and emit no HashGate flag.

### Phase 2 — Structural & path/identity checks

s0_gate_receipt_6B,
sealed_inputs_6B,
upstream validation bundles & flags for {1A,1B,2A,2B,3A,3B,5A,5B,6A}
                ->  (S5.4) Re-check S0 & upstream HashGates  (no RNG)
                    - Re-verify:
                          · sealed_inputs_digest_6B vs recomputed digest,
                          · each upstream segment’s validation bundle + _passed.flag_* digest
                            using its own index/digest law.
                    - Compare results with upstream_segments entries in s0_gate_receipt_6B.
                    - If any mismatch is found:
                          · record structural FAIL checks,
                          · mark world overall_status="FAIL" (precondition),
                          · do NOT write _passed.flag.

S1–S4 dataset contracts (from dictionaries),
sealed_inputs_6B
                ->  (S5.5) Structural presence & schema conformity (S1–S4)  (no RNG)
                    - For every required 6B dataset in S1–S4 according to sealed_inputs_6B:
                          · check that the corresponding path exists,
                          · validate file format (JSON/Parquet/directory as per contract),
                          · validate schema & PK/ordering invariants against schemas.6B.yaml and dictionaries:
                                - s1_arrival_entities_6B,
                                - s1_session_index_6B,
                                - s2_flow_anchor_baseline_6B,
                                - s2_event_stream_baseline_6B,
                                - s3_campaign_catalogue_6B,
                                - s3_flow_anchor_with_fraud_6B,
                                - s3_event_stream_with_fraud_6B,
                                - s4_flow_truth_labels_6B,
                                - s4_flow_bank_view_6B,
                                - s4_event_labels_6B,
                                - s4_case_timeline_6B.
                    - For each failure (missing dataset, schema violation, PK/ordering error):
                          · record a structural check result (FAIL or WARN based on policy),
                          · mark world for FAIL if any REQUIRED check fails.

### Phase 3 — Cross-state & behavioural consistency checks

S1–S4 surfaces (S1: arrivals/sessions, S2: baseline, S3: overlay, S4: labels/cases),
segment_validation_policy_6B
                ->  (S5.6) Cross-state coverage & identity checks  (no RNG)
                    - For each (seed, scenario_id) in world_seeds × world_scenarios:
                          · check S1:
                                - every arrival in arrival_events_5B (if in scope) has exactly one
                                  s1_arrival_entities_6B row,
                                - every session_id in s1_session_index_6B is used by at least one arrival,
                                - arrival_count in sessions matches arrivals per session_id.
                          · check S2:
                                - every s1_arrival_entities_6B row is assigned to exactly one baseline flow
                                  via s2_flow_anchor_baseline_6B and/or s2_event_stream_baseline_6B,
                                - every flow_id in s2_event_stream_baseline_6B has exactly one anchor row.
                          · check S3:
                                - every baseline flow_id appears in s3_flow_anchor_with_fraud_6B with
                                  origin_flow_id = that baseline id,
                                - any flow with origin_type=PURE_FRAUD_FLOW has no baseline counterpart,
                                - every event in s3_event_stream_with_fraud_6B has a valid flow_id and consistent origin links.
                          · check S4:
                                - every flow_id with-fraud has exactly one truth row and one bank-view row,
                                - every event with-fraud has exactly one event-label row,
                                - any flow that is marked as case-involved appears in at least one case in s4_case_timeline_6B,
                                - case_event_seq is strictly increasing per case_id.
                    - Classify each consistency check as PASS/WARN/FAIL according to segment_validation_policy_6B
                      and accumulate metrics (counts, rates, coverage percentages).

S3 campaigns,
S3 overlay surfaces,
S4 truth/bank labels & cases,
segment_validation_policy_6B
                ->  (S5.7) Behavioural metrics & bounds checks  (no RNG)
                    - For each (seed, scenario_id) and/or for the world as a whole:
                          · compute metrics defined in behavioural_checks:
                                - total flows, total fraud flows, fraud rate,
                                - detection rate, missed-fraud rate,
                                - dispute/chargeback rates,
                                - case volumes and average case size,
                                - campaign activation counts vs intended intensity from config,
                                - overlay severity distributions, etc.
                          · for each behavioural check:
                                - compare computed metric(s) to thresholds in policy,
                                - assign result ∈ {PASS, WARN, FAIL}.
                    - Aggregate results across seeds/scenarios if policy requires world-level metrics.
                    - Record per-check metrics & results for inclusion in s5_validation_report_6B
                      and (optionally) s5_issue_table_6B.

### Phase 4 — RNG envelope & accounting checks (S1–S4 only)

rng_event_* datasets for S1–S4,
rng_trace_log,
segment_validation_policy_6B
                ->  (S5.8) RNG accounting & envelope checks  (no RNG)
                    - For each RNG family used by S1–S4 (declared in rng_policy_6B.yaml):
                          · load the corresponding rng_event_* dataset,
                          · validate schema & partitioning,
                          · compute:
                                - total_rows (events),
                                - total_blocks, total_draws (from envelopes),
                                - expected_draws and expected_blocks based on:
                                      · number of arrivals (S1),
                                      · number of sessions/flows/events (S2),
                                      · number of campaigns/targets/overlays (S3),
                                      · number of flows/cases for labelling/delays (S4),
                                - reconcile with rng_trace_log counters per stream.
                          · check:
                                - monotone counters per stream/family,
                                - no draws from undeclared families,
                                - drawn ≤ budget (or within policy tolerances).
                          · classify each RNG check as PASS/WARN/FAIL according to segment_validation_policy_6B.
                    - Summarise RNG check metrics for inclusion in s5_validation_report_6B.

### Phase 5 — Report & bundle construction

S5 structural, behavioural, RNG check results & metrics
                ->  (S5.9) Build s5_validation_report_6B & s5_issue_table_6B  (no RNG)
                    - Construct s5_validation_report_6B JSON object:
                          · manifest_fingerprint, parameter_hash, spec_version_6B,
                          · evaluated_seeds, evaluated_scenarios,
                          · checks[]:
                                - check_id, severity, result,
                                - metrics, thresholds,
                          · overall_status:
                                - "PASS" if and only if:
                                      all REQUIRED checks result=PASS,
                                - "FAIL" if any REQUIRED check result=FAIL,
                                - WARN checks do not prevent PASS unless policy says otherwise.
                          · created_utc timestamp.
                    - Optionally build s5_issue_table_6B:
                          · for checks configured with per-issue output,
                          · for each failing or warning condition:
                                - create one or more rows with:
                                      manifest_fingerprint,
                                      check_id, issue_id,
                                      severity, result,
                                      location (seed, scenario_id, flow_id, event_id, campaign_id, case_id, etc.),
                                      message, details, metrics snapshot.
                    - Validate:
                          · s5_validation_report_6B against schemas.layer3.yaml#/validation/6B/s5_validation_report,
                          · s5_issue_table_6B (if present) against schemas.layer3.yaml#/validation/6B/s5_issue_table.
                    - Write:
                          · s5_validation_report_6B JSON to the dictionary path for this fingerprint,
                          · s5_issue_table_6B Parquet (if any issues/warnings need row-level detail).

s5_validation_report_6B,
s5_issue_table_6B (optional),
selected evidence (e.g. digests or snapshots of S1–S4 surfaces, RNG summaries),
dataset_dictionary.layer3.6B.yaml
                ->  (S5.10) Build validation_bundle_index_6B (index.json)  (no RNG)
                    - Determine bundle membership according to segment_validation_policy_6B:
                          · s5_validation_report_6B (always),
                          · s5_issue_table_6B (if present),
                          · any additional evidence files required by policy
                            (e.g. compact metrics snapshots, RNG summaries).
                    - For each member file:
                          · compute sha256_hex over its raw bytes,
                          · record {path (relative to validation root), sha256_hex}.
                    - Assemble validation_bundle_index_6B:
                          · manifest_fingerprint,
                          · members[] = { path, sha256_hex },
                          · policy ids, created_utc.
                    - Sort members by `path` in ASCII-lexical order.
                    - Validate index.json against schemas.layer3.yaml#/validation/6B/validation_bundle_index_6B.
                    - Write index.json into validation_bundle_6B directory:
                          data/layer3/6B/validation/fingerprint={manifest_fingerprint}/index.json
                      using atomic write semantics.

validation_bundle_index_6B (index.json),
all bundle member files,
segment_validation_policy_6B
                ->  (S5.11) Compute bundle digest & write validation_passed_flag_6B  (no RNG)
                    - Compute bundle_digest as:
                          · concatenate the bytes of each file listed in index.json.members
                            in the order of members[].path (ASCII-lex sorted),
                          · compute SHA-256 over that concatenation,
                          · represent as lowercase 64-hex.
                    - If s5_validation_report_6B.overall_status != "PASS":
                          · S5 MUST NOT write or update _passed.flag,
                          · any existing _passed.flag MUST be treated as stale and ignored by consumers.
                    - If overall_status == "PASS":
                          · construct validation_passed_flag_6B text:
                                "sha256_hex = {bundle_digest}\n"
                            (exact formatting as defined in schemas.layer3.yaml#/validation/6B/passed_flag_6B),
                          · if _passed.flag does not exist:
                                - write it atomically at:
                                      data/layer3/6B/validation/fingerprint={manifest_fingerprint}/_passed.flag
                          · if _passed.flag exists:
                                - read existing content and compare sha256_hex:
                                      - if equal to bundle_digest → idempotent; OK,
                                      - if different               → treat as immutability violation;
                                                                     S5 MUST NOT overwrite and MUST mark
                                                                     the world as FAIL for operational purposes.

Downstream touchpoints
----------------------
- **Layer-4 (4A/4B, model-training, ops tooling):**
    - MUST:
          - recompute the 6B bundle digest from index.json and require equality with validation_passed_flag_6B.sha256_hex,
          - treat failure to verify (_passed.flag missing or mismatched) as **“no PASS → no read”**
            for all 6B outputs (S1–S4).
    - MAY:
          - inspect s5_validation_report_6B and s5_issue_table_6B to understand coverage, metrics, and
            any non-fatal warnings.

- **6B re-runs / reproducibility tooling:**
    - MUST:
          - treat s5_validation_report_6B + validation_bundle_index_6B as the canonical record of which
            checks were run and what they concluded for this world,
          - ensure that any re-run that changes 6B behaviour either:
                · produces a byte-identical bundle & _passed.flag, or
                · increments spec_version_6B / parameter_hash and writes to a new world.
```
