```text
        LAYER 3 · SEGMENT 6B — STATE S4 (TRUTH & BANK-VIEW LABELLING + CASE TIMELINES)  [RNG-BEARING]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[S0 gate & sealed inputs]
    - s0_gate_receipt_6B
      @ data/layer3/6B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json
      · For this world:
          - manifest_fingerprint, parameter_hash, run_id, spec_version_6B,
          - upstream_segments{seg_id → {status,bundle_path,bundle_sha256,flag_path}},
          - contracts_6B{logical_id → {path,sha256_hex,schema_ref,role}},
          - sealed_inputs_digest_6B.
      · S4 MUST:
          - load & validate this before any data-plane work,
          - require S0 status="PASS" for this manifest_fingerprint,
          - require upstream_segments for {1A,1B,2A,2B,3A,3B,5A,5B,6A} to have status="PASS",
          - treat upstream_segments as the sole authority on upstream HashGates.

    - sealed_inputs_6B
      @ data/layer3/6B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet
      · One row per artefact 6B may read:
          - owner_layer, owner_segment, manifest_key,
          - path_template, partition_keys[], schema_ref,
          - sha256_hex, role, status, read_scope.
      · S4 MUST:
          - recompute sealed_inputs_digest_6B (canonical serialisation) and require equality with s0_gate_receipt_6B,
          - only read artefacts listed here,
          - honour status (REQUIRED/OPTIONAL/IGNORED),
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → presence/shape checks only.

[Schema+Dict · shape & catalogue authority]
    - schemas.layer3.yaml, schemas.6B.yaml
        · shape authority for:
              - s3_flow_anchor_with_fraud_6B,
              - s3_event_stream_with_fraud_6B,
              - s4_flow_truth_labels_6B,
              - s4_flow_bank_view_6B,
              - s4_event_labels_6B,
              - s4_case_timeline_6B.
    - dataset_dictionary.layer3.6B.yaml
        · IDs/contracts (key excerpts):

          - s3_flow_anchor_with_fraud_6B
            · path:
                data/layer3/6B/s3_flow_anchor_with_fraud_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
            · partitioning: [seed, fingerprint, scenario_id]
            · primary_key:
                  [seed, manifest_fingerprint, scenario_id, flow_id]
            · ordering:
                  [seed, manifest_fingerprint, scenario_id, flow_id]
            · schema_ref: schemas.6B.yaml#/s3/flow_anchor_with_fraud_6B

          - s3_event_stream_with_fraud_6B
            · path:
                data/layer3/6B/s3_event_stream_with_fraud_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
            · partitioning: [seed, fingerprint, scenario_id]
            · primary_key:
                  [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
            · ordering:
                  [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
            · schema_ref: schemas.6B.yaml#/s3/event_stream_with_fraud_6B

          - s4_flow_truth_labels_6B
            · path:
                data/layer3/6B/s4_flow_truth_labels_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
            · partitioning: [seed, fingerprint, scenario_id]
            · primary_key:
                  [seed, manifest_fingerprint, scenario_id, flow_id]
            · ordering:
                  [seed, manifest_fingerprint, scenario_id, flow_id]
            · schema_ref: schemas.6B.yaml#/s4/flow_truth_labels_6B

          - s4_flow_bank_view_6B
            · path:
                data/layer3/6B/s4_flow_bank_view_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
            · partitioning: [seed, fingerprint, scenario_id]
            · primary_key:
                  [seed, manifest_fingerprint, scenario_id, flow_id]
            · ordering:
                  [seed, manifest_fingerprint, scenario_id, flow_id]
            · schema_ref: schemas.6B.yaml#/s4/flow_bank_view_6B

          - s4_event_labels_6B
            · path:
                data/layer3/6B/s4_event_labels_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
            · partitioning: [seed, fingerprint, scenario_id]
            · primary_key:
                  [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
            · ordering:
                  [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
            · schema_ref: schemas.6B.yaml#/s4/event_labels_6B

          - s4_case_timeline_6B
            · path:
                data/layer3/6B/s4_case_timeline_6B/seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet
            · partitioning: [seed, fingerprint]
            · primary_key:
                  [seed, manifest_fingerprint, case_id, case_event_seq]
            · ordering:
                  [seed, manifest_fingerprint, case_id, case_event_seq]
            · schema_ref: schemas.6B.yaml#/s4/case_timeline_6B

[Primary behaviour inputs (S3 outputs)]
    - s3_flow_anchor_with_fraud_6B   (REQUIRED, ROW_LEVEL)
      · one row per **post-overlay** flow:
            - axes: manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id,
            - origin link: origin_flow_id, origin_type ∈ {BASELINE_UNTOUCHED, BASELINE_MUTATED, PURE_FRAUD_FLOW},
            - session_id, arrival_keys[],
            - timing & amount summary AFTER overlay,
            - overlay metadata: campaign_id, fraud_pattern_type, overlay_flags, overlay_severity_score?,
            - entity & routing context (party/account/instrument/device/IP/merchant/site/edge, zone/tz).
      · Authority:
            - what the flow looks like after S3 overlay (no fraud labels yet),
            - which flows are structurally involved in campaigns.

    - s3_event_stream_with_fraud_6B  (REQUIRED, ROW_LEVEL)
      · one row per **post-overlay** event:
            - axes: manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, event_seq,
            - origin link: origin_flow_id, origin_event_seq (nullable), origin_type,
            - event_type, event_ts_utc,
            - amounts, response codes, overlay flags, campaign_id, fraud_pattern_type,
            - entity & routing context.
      · Authority:
            - the final event-level behaviour in this world,
            - structural markers for fraud/abuse patterns (via overlay flags).

Upstream context (S1/S2/6A) for features only
    - s2_flow_anchor_baseline_6B, s2_event_stream_baseline_6B (OPTIONAL, ROW_LEVEL)
      · S4 MAY use these for baseline-vs-overlay comparisons (e.g. distortion magnitudes),
        but MUST NOT mutate them.

    - s1_arrival_entities_6B, s1_session_index_6B (OPTIONAL, ROW_LEVEL)
      · S4 MAY use these for additional context (e.g. session-level signals),
        but MUST NOT reinterpret attachments or sessions.

    - 6A bases & posture (ROW_LEVEL, REQUIRED if referenced in policies)
      · s1_party_base_6A, s2_account_base_6A, s3_instrument_base_6A,
        s4_device_base_6A, s4_ip_base_6A,
        s3_account_instrument_links_6A, s4_device_links_6A, s4_ip_links_6A,
        s5_*_fraud_roles_6A.
      · Authority:
            - static roles and structure; S4 may use them to explain fraud/abuse patterns
              (e.g. mules, risky merchants) but must not change them.

[6B configuration & policy inputs for S4]
    - truth_labelling_policy_6B    (REQUIRED, METADATA or ROW_LEVEL)
      · defines flow-level truth labels (`LEGIT`, `FRAUD_*`, `ABUSE_*`) and event-level truth roles:
            - deterministic rules based on fraud_pattern_type, overlay_flags, posture, baseline vs overlay,
            - optional ambiguous cases where RNG chooses between multiple plausible labels.

    - bank_view_policy_6B          (REQUIRED)
      · defines how the bank reacts:
            - auth decisions (approve/decline/review) given truth & context,
            - detection/no-detection rules and detection channels,
            - dispute/chargeback rules and bank-view labels.

    - delay_models_6B              (REQUIRED)
      · provides distributions for:
            - detection delays,
            - dispute delays,
            - chargeback delays and outcomes,
            - any extra case-event timing needed.

    - case_policy_6B               (REQUIRED)
      · defines:
            - case keys (how flows are grouped into cases),
            - rules for when to open a case,
            - how flows map to one or more cases,
            - canonical case event types and ordering constraints.

    - label_rng_policy_6B          (REQUIRED, METADATA)
      · declares S4 RNG families and budgets, e.g.:
            - rng_event_truth_label_ambiguity,
            - rng_event_detection_delay,
            - rng_event_dispute_delay,
            - rng_event_chargeback_delay,
            - rng_event_case_timeline;
        and keying scheme:
            - which tuple (mf, parameter_hash, seed, scenario_id, flow_id, case_key, etc.)
              maps to each family’s substream.

[RNG & envelope policies]
    - rng_profile_layer3.yaml
      · global Philox configuration & envelope semantics (blocks/draws, counters).
    - rng_policy_6B.yaml   (referenced by label_rng_policy_6B)
      · S4 MUST:
            - use only RNG families declared for S4,
            - honour per-family blocks/draws budgets,
            - emit rng_event_* rows and rng_trace_log envelopes accordingly.

[Outputs owned by S4]
    - s4_flow_truth_labels_6B
      @ data/layer3/6B/s4_flow_truth_labels_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, flow_id]
      · ordering:
            [seed, manifest_fingerprint, scenario_id, flow_id]
      · logical content:
            - axes: manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id,
            - truth_label ∈ {LEGIT, FRAUD, ABUSE},
            - truth_subtype (CARD_TESTING, ATO, REFUND_ABUSE, MULE_ACTIVITY, FRIENDLY_FRAUD, etc.),
            - pattern_source (CAMPAIGN / COLLATERAL / HEURISTIC_ONLY),
            - campaign_id (nullable),
            - policy ids: truth_labelling_policy_id, etc.

    - s4_flow_bank_view_6B
      @ data/layer3/6B/s4_flow_bank_view_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, flow_id]
      · ordering:
            [seed, manifest_fingerprint, scenario_id, flow_id]
      · logical content:
            - axes + flow_id,
            - auth_decision (APPROVE/DECLINE/REVIEW/...),
            - bank_view_label (BANK_CONFIRMED_FRAUD, NO_CASE_OPENED, CUSTOMER_DISPUTE_NO_CHARGEBACK, etc.),
            - detection_outcome (DETECTED_AT_AUTH, DETECTED_POST_AUTH, NOT_DETECTED, etc.),
            - timestamps: detection_ts_utc?, dispute_ts_utc?, chargeback_ts_utc?,
              case_opened_ts_utc?, case_closed_ts_utc?,
            - policy ids: bank_view_policy_id, delay_model_id, etc.

    - s4_event_labels_6B
      @ data/layer3/6B/s4_event_labels_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
      · ordering:
            [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
      · logical content:
            - axes + flow_id, event_seq,
            - truth-level fields:
                  is_fraud_event_truth (bool),
                  truth_event_role (PRIMARY_FRAUD_ACTION, SUPPORTING_FRAUD_ACTION, CLEAN_CONTEXT, etc.),
            - bank-view fields:
                  is_detection_action (bool),
                  is_case_event (bool),
                  bank_event_label (e.g. ALERT_RAISED, CASE_CREATED, CUSTOMER_CONTACT, etc.),
            - policy ids as needed.

    - s4_case_timeline_6B
      @ data/layer3/6B/s4_case_timeline_6B/seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet
      · partitioning: [seed, fingerprint]
      · primary_key:
            [seed, manifest_fingerprint, case_id, case_event_seq]
      · ordering:
            [seed, manifest_fingerprint, case_id, case_event_seq]
      · logical content:
            - axes: manifest_fingerprint, parameter_hash, seed, case_id, case_event_seq,
            - case_event_type (CASE_OPENED, CASE_UPDATED, CASE_ESCALATED, CASE_CLOSED, etc.),
            - case_event_ts_utc,
            - linkage:
                  flow_id/flow_ids (if applicable), event_seq (optional),
            - policy ids: case_policy_id, delay_model_id, etc.

DAG — 6B.S4 (flows/events with overlay → truth labels, bank view & cases)  [RNG-BEARING]
-----------------------------------------------------------------------------------------

[S0 gate & sealed_inputs_6B],
[Schema+Dict]
                ->  (S4.1) Verify S0 gate, sealed_inputs, and S1–S3 preconditions  (RNG-free)
                    - Resolve and validate:
                          s0_gate_receipt_6B,
                          sealed_inputs_6B.
                    - Recompute sealed_inputs_digest_6B from sealed_inputs_6B and
                      require equality with the value in s0_gate_receipt_6B.
                    - Require upstream_segments for {1A,1B,2A,2B,3A,3B,5A,5B,6A} to have status="PASS".
                    - Require (via Layer-3 run-report or equivalent) that:
                          6B.S1, 6B.S2, 6B.S3 have status="PASS" for every (seed, manifest_fingerprint, scenario_id)
                          that S4 intends to process.
                    - If any condition fails:
                          S4 MUST treat this as a precondition failure and MUST NOT read S1–S3 data-plane rows.

sealed_inputs_6B,
dataset_dictionary.layer3.6B.yaml,
artefact_registry_6B
                ->  (S4.2) Discover S4 work domain & resolve S4 configs  (RNG-free)
                    - From sealed_inputs_6B, select rows with:
                          owner_segment="6B",
                          manifest_key ∈ {
                              "s3_flow_anchor_with_fraud_6B",
                              "s3_event_stream_with_fraud_6B",
                              "s4_flow_truth_labels_6B",
                              "s4_flow_bank_view_6B",
                              "s4_event_labels_6B",
                              "s4_case_timeline_6B",
                              "truth_labelling_policy_6B",
                              "bank_view_policy_6B",
                              "delay_models_6B",
                              "case_policy_6B",
                              "label_rng_policy_6B"
                          },
                          status="REQUIRED".
                    - Resolve path_template, partition_keys, schema_ref for these datasets via dictionary/registry.
                    - Enumerate (seed, scenario_id) partitions by inspecting s3_flow_anchor_with_fraud_6B
                      (and optionally s3_event_stream_with_fraud_6B).
                    - Resolve & validate all S4 config packs:
                          truth_labelling_policy_6B,
                          bank_view_policy_6B,
                          delay_models_6B,
                          case_policy_6B,
                          label_rng_policy_6B,
                          behaviour_config_6B (if present).
                    - If any required config pack is missing or schema-invalid:
                          S4 MUST fail preconditions.

s3_flow_anchor_with_fraud_6B,
s3_event_stream_with_fraud_6B,
optional S2/S1/6A context
                ->  (S4.3) Load S3 surfaces & build per-flow / per-event indices  (RNG-free per partition)
                    - For each (seed, scenario_id) partition:
                          1. Read s3_flow_anchor_with_fraud_6B@{seed,fingerprint,scenario_id}.
                          2. Read s3_event_stream_with_fraud_6B@{seed,fingerprint,scenario_id}.
                          3. Validate:
                               · schema & PK/ordering invariants for both tables,
                               · every flow_id in event_stream_with_fraud has exactly one flow_anchor_with_fraud row.
                          4. If baseline S2 surfaces are enabled:
                               · read s2_flow_anchor_baseline_6B and s2_event_stream_baseline_6B and
                                 join as read-only context (e.g. for distortion metrics).
                          5. If 6A posture is enabled:
                               · join required posture fields for parties/accounts/merchants/devices/IPs.
                          6. Build indices:
                               · flows: flow_id → flow_anchor_with_fraud row,
                               · events_by_flow: flow_id → [events], sorted by event_seq,
                               · optional maps by entity or posture segment for case grouping.

truth_labelling_policy_6B,
label_rng_policy_6B,
rng_profile_layer3.yaml,
flows & events from S4.3
                ->  (S4.4) Flow-level truth labelling → s4_flow_truth_labels_6B  [RNG-bearing]
                    - For each flow f in s3_flow_anchor_with_fraud_6B:
                          1. Build flow truth-context:
                               · fraud_pattern_type, campaign_id, overlay_flags and severity from S3,
                               · static posture (6A fraud roles) for its entities,
                               · optional baseline-vs-overlay metrics (from S2).
                          2. Apply deterministic rules from truth_labelling_policy_6B:
                               · if pattern + overlay_flags unambiguously map to FRAUD_* or ABUSE_*,
                                 assign truth_label/truth_subtype deterministically,
                               · if clearly clean (no campaign involvement, no suspicious overlays),
                                 assign LEGIT.
                          3. If flow remains ambiguous after deterministic rules:
                               · use rng_event_truth_label_ambiguity:
                                     - derive rng_stream_id/key from
                                       (manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id),
                                     - draw the configured number of uniforms,
                                     - map to one truth_label/truth_subtype according to policy.
                          4. Construct s4_flow_truth_labels_6B row for f:
                               · axes + flow_id,
                               · truth_label, truth_subtype,
                               · pattern_source (CAMPAIGN / COLLATERAL / HEURISTIC_ONLY),
                               · campaign_id (if any),
                               · policy ids (truth_labelling_policy_id, etc.).
                    - At end of this step:
                          · every flow_id in s3_flow_anchor_with_fraud_6B has exactly one truth row,
                          · no S3 flows remain unlabeled.

bank_view_policy_6B,
delay_models_6B,
label_rng_policy_6B,
s4_flow_truth_labels_6B,
flows & events from S4.3
                ->  (S4.5) Flow-level bank-view simulation → s4_flow_bank_view_6B  [RNG-bearing]
                    - For each flow f:
                          1. Build bank-view context:
                               · truth_label / truth_subtype from s4_flow_truth_labels_6B,
                               · overlay metadata (campaign_id, fraud_pattern_type, overlay_flags),
                               · posture features (6A),
                               · timing & amounts (S3/S2),
                               · scenario metadata.
                          2. Decide authorisation outcome:
                               · apply bank_view_policy_6B (deterministic rules) to derive auth_decision.
                          3. Simulate detection:
                               · if policy dictates deterministic detection (e.g. certain patterns always detected at auth),
                                     - set detection_outcome & detection_ts_utc accordingly,
                               · else:
                                     - use rng_event_detection_delay with key (mf, ph, seed, scenario_id, flow_id)
                                       to decide:
                                           * detection vs no detection,
                                           * detection channel & delay (via delay_models_6B),
                                       - compute detection_ts_utc from underlying event timestamps.
                          4. Simulate dispute:
                               · if flow eligible (per truth_label & bank_view_policy_6B):
                                     - use rng_event_dispute_delay keyed by (mf, ph, seed, scenario_id, flow_id)
                                       to decide:
                                           * whether a dispute occurs,
                                           * dispute_ts_utc if it does.
                               · else:
                                     - dispute_ts_utc = null.
                          5. Simulate chargeback:
                               · if dispute (and policy allows chargeback):
                                     - use rng_event_chargeback_delay keyed by (mf, ph, seed, scenario_id, flow_id)
                                       to decide:
                                           * whether a chargeback occurs,
                                           * chargeback_ts_utc,
                                           * chargeback outcome (win/loss, partial/full),
                                           * any associated recovery amounts.
                               · else:
                                     - no chargeback; fields null or default as per schema.
                          6. Populate s4_flow_bank_view_6B row:
                               · axes + flow_id,
                               · auth_decision,
                               · detection_outcome, detection_ts_utc?,
                               · bank_view_label (per policy),
                               · dispute_ts_utc?, chargeback_ts_utc?,
                               · case_opened_ts_utc?, case_closed_ts_utc? (if policy sets them at flow level),
                               · policy ids (bank_view_policy_id, delay_model_id, etc.).

s4_flow_truth_labels_6B,
s4_flow_bank_view_6B,
s3_event_stream_with_fraud_6B
                ->  (S4.6) Event-level truth & bank-view labels → s4_event_labels_6B  (RNG-free)
                    - For each event e in s3_event_stream_with_fraud_6B:
                          1. Pull context:
                               · flow-level truth & bank-view from S4.4–S4.5 for its flow_id,
                               · event-level overlay metadata (fraud_pattern_type, overlay_flags, origin_*),
                               · bank-view times (detection_ts_utc, dispute_ts_utc, chargeback_ts_utc).
                          2. Assign truth-level event roles (deterministic):
                               · using truth_labelling_policy_6B, mark:
                                     - is_fraud_event_truth (bool),
                                     - truth_event_role (PRIMARY_FRAUD_ACTION, SUPPORTING_FRAUD_ACTION, CLEAN_CONTEXT, etc.),
                                 based on where e sits relative to the fraud pattern and its overlay flags.
                          3. Assign bank-view event roles (deterministic):
                               · using bank_view_policy_6B, mark:
                                     - is_detection_action (true if e corresponds to detection/alert case),
                                     - is_case_event (true if e corresponds to case workflow),
                                     - bank_event_label (ALERT_RAISED, CASE_CREATED, CUSTOMER_CONTACT, etc.)
                                 based on event_type and timing vs detection/dispute/chargeback/case windows.
                          4. Write s4_event_labels_6B row:
                               · axes + flow_id, event_seq,
                               · truth-level fields (is_fraud_event_truth, truth_event_role),
                               · bank-view fields (is_detection_action, is_case_event, bank_event_label),
                               · policy ids as needed.
                    - Invariants:
                          · every (seed,fingerprint,scenario_id,flow_id,event_seq) in s3_event_stream_with_fraud_6B
                            appears exactly once in s4_event_labels_6B.

s4_flow_truth_labels_6B,
s4_flow_bank_view_6B,
case_policy_6B,
label_rng_policy_6B
                ->  (S4.7) Case construction & timeline → s4_case_timeline_6B  [RNG-bearing]
                    - Define case keys:
                          · from case_policy_6B, derive case_key(f) for flows that require cases, e.g.:
                                case_key = { account_id, instrument_id, manifest_fingerprint, seed }
                            or richer structures including merchant/region/time windows.
                    - Allocate flows to cases:
                          · group flows with case involvement (e.g. disputes, chargebacks, fraud patterns
                            that require case handling) by case_key,
                          · for each group, apply case_policy_6B to decide:
                                - whether to open a single case or multiple cases,
                                - which flows belong to which case.
                          · if policy contains stochastic choices (e.g. random bundling of flows into cases):
                                - use rng_event_case_timeline with key (mf, ph, seed, case_key, flow_id)
                                  and fixed draws per decision.
                    - Assign case_ids deterministically:
                          · for each case in each group, compute:
                                case_id = hash64(manifest_fingerprint, seed, case_key, case_index_within_key)
                            or equivalent deterministic scheme.
                          · ensure case_id is unique within (seed, manifest_fingerprint).
                    - Build case event sequences:
                          · for each case, using case_policy_6B and delay_models_6B:
                                - construct an ordered list of case events:
                                      CASE_OPENED,
                                      CASE_UPDATED / CASE_ESCALATED,
                                      DISPUTE_ATTACHED / CHARGEBACK_ATTACHED (if applicable),
                                      CASE_CLOSED,
                                - derive case_event_ts_utc values from flow bank-view timestamps
                                  plus any additional delays (via rng_event_case_timeline where configured),
                                - attach linkage to relevant flow_id(s) and, if needed, event_seq.
                    - Write s4_case_timeline_6B rows:
                          · axes + case_id, case_event_seq,
                          · case_event_type, case_event_ts_utc,
                          · linkage fields (flow_id/flow_ids, event_seq?),
                          · policy ids as needed.
                    - Invariants:
                          · case_event_seq is strictly increasing per case_id,
                          · any flow with non-null case involvement in s4_flow_bank_view_6B appears in at least one
                            case in s4_case_timeline_6B.

s4_flow_truth_labels_6B,
s4_flow_bank_view_6B,
s4_event_labels_6B,
s4_case_timeline_6B,
schemas.6B.yaml
                ->  (S4.8) Materialise S4 outputs & enforce cross-surface invariants  (RNG-free)
                    - Validate each S4 dataset against its schema anchor and dictionary contract:
                          · PK uniqueness & ordering,
                          · partitioning,
                          · required fields.
                    - Cross-surface checks:
                          · every flow_id in s3_flow_anchor_with_fraud_6B has exactly one row in
                            s4_flow_truth_labels_6B and s4_flow_bank_view_6B,
                          · every (flow_id,event_seq) in s3_event_stream_with_fraud_6B appears exactly once
                            in s4_event_labels_6B,
                          · any flow flagged as involved in a case in s4_flow_bank_view_6B appears in at least one
                            s4_case_timeline_6B case,
                          · case_id uniqueness within (seed, manifest_fingerprint).
                    - Write:
                          s4_flow_truth_labels_6B,
                          s4_flow_bank_view_6B,
                          s4_event_labels_6B,
                          s4_case_timeline_6B
                      for each processed (seed,scenario), using atomic write patterns.
                    - On any invariant failure for a partition:
                          · S4 MUST treat that partition as failed and MUST NOT publish partial outputs.

RNG events (truth_label_ambiguity, detection_delay, dispute_delay, chargeback_delay, case_timeline),
rng_trace_log (Layer-3)
                ->  (S4.9) Local RNG accounting summary for S5  (RNG-free aggregation)
                    - For each (seed,scenario) partition:
                          · count rng_event_truth_label_ambiguity rows,
                            rng_event_detection_delay rows,
                            rng_event_dispute_delay rows,
                            rng_event_chargeback_delay rows,
                            rng_event_case_timeline rows,
                          · compute expected draws per family given:
                                - number of flows (for truth, detection, disputes, chargebacks),
                                - number of cases (for case_timeline),
                                - configured budgets in label_rng_policy_6B,
                          · reconcile with rng_trace_log:
                                - counters monotone per stream & family,
                                - no draws from undeclared families,
                                - draws within expected budgets.
                    - Record metrics in internal run-report structures for consumption by S5;
                      S4 MUST NOT publish separate RNG-accounting datasets.

Downstream touchpoints
----------------------
- **6B.S5 (segment validation & HashGate):**
    - Reads:
          s4_flow_truth_labels_6B,
          s4_flow_bank_view_6B,
          s4_event_labels_6B,
          s4_case_timeline_6B,
          S1–S3 surfaces as needed.
    - Validates:
          schema/PK/ordering invariants for S4 outputs,
          cross-surface invariants (flows/events/cases),
          RNG accounting for S4 families,
          alignment with truth/bank/case policies.

- **Layer-4 (4A/4B, model-training, ops tooling):**
    - Treats:
          S4 outputs as the **final labelled view** of the synthetic world:
              - truth_labels_6B → ground truth,
              - flow_bank_view_6B → bank’s perspective,
              - event_labels_6B → fine-grained event roles,
              - case_timeline_6B → case lifecycle.
    - MUST honour the 6B HashGate (S5) before consuming these datasets.
```
