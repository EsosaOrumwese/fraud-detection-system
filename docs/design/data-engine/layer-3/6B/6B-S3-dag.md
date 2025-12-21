```text
        LAYER 3 · SEGMENT 6B — STATE S3 (FRAUD & ABUSE CAMPAIGN OVERLAY)  [RNG-BEARING]

Authoritative inputs (read-only at S3 entry)
--------------------------------------------
[S0 gate & sealed inputs]
    - s0_gate_receipt_6B
      @ data/layer3/6B/gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json
      · For this world:
          - manifest_fingerprint, parameter_hash, run_id, spec_version_6B,
          - upstream_segments{seg_id → {status,bundle_path,bundle_sha256,flag_path}},
          - contracts_6B{logical_id → {path,sha256_hex,schema_ref,role}},
          - sealed_inputs_digest_6B.
      · S3 MUST:
          - load & validate this before any data-plane work,
          - require S0 status="PASS" for this manifest_fingerprint,
          - require all required upstream segments {1A,1B,2A,2B,3A,3B,5A,5B,6A} to have status="PASS",
          - treat upstream_segments as the only authority on upstream HashGates.

    - sealed_inputs_6B
      @ data/layer3/6B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet
      · One row per artefact 6B may read:
          - owner_layer, owner_segment, manifest_key,
          - path_template, partition_keys[], schema_ref,
          - sha256_hex, role, status, read_scope.
      · S3 MUST:
          - recompute sealed_inputs_digest_6B (canonical serialisation) and require equality with s0_gate_receipt_6B,
          - only read artefacts listed here,
          - honour status (REQUIRED/OPTIONAL/IGNORED),
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → presence/shape checks only.

[Schema+Dict · shape & catalogue authority]
    - schemas.layer3.yaml, schemas.6B.yaml
        · shape authority for:
              - s2_flow_anchor_baseline_6B,
              - s2_event_stream_baseline_6B,
              - s3_campaign_catalogue_6B,
              - s3_flow_anchor_with_fraud_6B,
              - s3_event_stream_with_fraud_6B.
    - dataset_dictionary.layer3.6B.yaml
        · IDs/contracts (key excerpts):

          - s2_flow_anchor_baseline_6B
            · path:
                data/layer3/6B/s2_flow_anchor_baseline_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
            · partitioning: [seed, fingerprint, scenario_id]
            · primary_key:
                  [seed, manifest_fingerprint, scenario_id, flow_id]
            · ordering:
                  [seed, manifest_fingerprint, scenario_id, flow_id]
            · schema_ref: schemas.6B.yaml#/s2/flow_anchor_baseline_6B

          - s2_event_stream_baseline_6B
            · path:
                data/layer3/6B/s2_event_stream_baseline_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
            · partitioning: [seed, fingerprint, scenario_id]
            · primary_key:
                  [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
            · ordering:
                  [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
            · schema_ref: schemas.6B.yaml#/s2/event_stream_baseline_6B

          - s3_campaign_catalogue_6B
            · path:
                data/layer3/6B/s3_campaign_catalogue_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s3_campaign_catalogue_6B.parquet
            · partitioning: [seed, fingerprint, scenario_id]
            · primary_key:
                  [seed, manifest_fingerprint, scenario_id, campaign_id]
            · ordering: [campaign_id]
            · schema_ref: schemas.6B.yaml#/s3/campaign_catalogue_6B

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

[Baseline flows & events (S2 outputs)]
    - s2_flow_anchor_baseline_6B   (REQUIRED, ROW_LEVEL)
      · one row per baseline flow/transaction:
            flow_id, session_id, arrival keys,
            baseline amounts & currencies,
            baseline timing summary,
            entity & routing context,
            baseline outcome flags (no fraud semantics).
      · Authority:
            - the set of baseline flows to target or leave alone,
            - each flow’s legitimate structure & outcome in the no-fraud world.

    - s2_event_stream_baseline_6B  (REQUIRED, ROW_LEVEL)
      · one row per baseline event:
            flow_id, event_seq, event_type, event_ts_utc,
            event-level amounts, entity & routing context.
      · Authority:
            - baseline event sequence per flow,
            - baseline timing & routing details S3 will distort via overlays.

[Entity & posture context (Layer-3 / 6A)]
    - 6A bases & links (ROW_LEVEL, REQUIRED if referenced by policy):
        · s1_party_base_6A,
        · s2_account_base_6A,
        · s3_instrument_base_6A,
        · s4_device_base_6A,
        · s4_ip_base_6A,
        · s3_account_instrument_links_6A,
        · s4_device_links_6A,
        · s4_ip_links_6A.
    - 6A fraud posture (ROW_LEVEL, REQUIRED if referenced by policy):
        · s5_party_fraud_roles_6A,
        · s5_account_fraud_roles_6A,
        · s5_merchant_fraud_roles_6A (if used),
        · s5_device_fraud_roles_6A,
        · s5_ip_fraud_roles_6A.
      · S3 MUST:
          - treat these as read-only static truth,
          - never change or invent entity keys or roles,
          - use them only for targeting and overlay decisions.

[6B configuration & policy inputs for S3]
    - fraud_campaign_catalogue_config_6B   (REQUIRED, METADATA or ROW_LEVEL)
      · defines campaign templates:
            campaign_type, segment definitions,
            activation schedules, intended intensities,
            allowable target domains (entities/flows/events).
    - fraud_overlay_policy_6B             (REQUIRED, METADATA or ROW_LEVEL)
      · defines how each campaign type mutates flows & events:
            permitted tactics (amount shifts, routing anomalies, device/IP swaps, etc.),
            what can be inserted vs mutated vs suppressed,
            per-tactic constraints and severity scoring.
    - fraud_rng_policy_6B                 (REQUIRED, METADATA)
      · configuration for S3 RNG families:
            rng_event_campaign_activation,
            rng_event_campaign_targeting,
            rng_event_overlay_mutation,
        plus:
            - per-family budgets (blocks/draws per event),
            - substream keying law (e.g. keyed by (seed,fingerprint,scenario_id,campaign_id,flow_id)).
    - behaviour_config_6B (if present)
      · may limit which campaigns are enabled, which flows/entities are eligible,
        or adjust intensity scaling for particular segments.

[RNG & envelope policies]
    - rng_profile_layer3.yaml
      · global Philox 2×64-10 configuration & envelope semantics.
    - rng_policy_6B.yaml   (referenced by fraud_rng_policy_6B)
      · declares S3 RNG families and envelope rules for:
            rng_event_campaign_activation,
            rng_event_campaign_targeting,
            rng_event_overlay_mutation.
      · S3 MUST:
            - use only these families for stochastic decisions,
            - adhere to declared blocks/draws budgets,
            - emit rng_event_* rows and rng_trace_log envelopes accordingly.

[Outputs owned by S3]
    - s3_campaign_catalogue_6B
      @ data/layer3/6B/s3_campaign_catalogue_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s3_campaign_catalogue_6B.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, campaign_id]
      · ordering: [campaign_id]
      · logical content:
            - campaign_id, campaign_type,
            - configuration ids / template ids used,
            - resolved parameters (activation window, intended coverage, target filters, intensity multipliers),
            - realised activation metrics (number of targeted entities/flows/events),
            - provenance (policy pack ids, version hashes).

    - s3_flow_anchor_with_fraud_6B
      @ data/layer3/6B/s3_flow_anchor_with_fraud_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, flow_id]
      · ordering:
            [seed, manifest_fingerprint, scenario_id, flow_id]
      · logical content (per flow_id):
            - identity & linkage:
                  manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id,
                  origin_flow_id (baseline flow_id), origin_type ∈ {BASELINE_UNTOUCHED, BASELINE_MUTATED, PURE_FRAUD_FLOW},
                  session_id, arrival_keys[],
            - timing & amount summary **after overlay**:
                  first_auth_ts_utc, final_auth_ts_utc,
                  clear_ts_utc?, refund_ts_utc?,
                  auth_amount, clear_amount, refund_amount, transaction_currency,
            - overlay metadata:
                  campaign_id (nullable or list if multiple campaigns touched the flow),
                  fraud_pattern_type (e.g. CARD_TESTING, ATO, REFUND_ABUSE, COLLUSION, NONE),
                  overlay_flags (bitset/struct: amount_modified, routing_anomalous, device_swapped, ip_swapped, extra_events_inserted, etc.),
                  overlay_severity_score or similar metric,
            - entity & routing context (copied from baseline; keys MUST NOT change).

    - s3_event_stream_with_fraud_6B
      @ data/layer3/6B/s3_event_stream_with_fraud_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
      · ordering:
            [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
      · logical content (per event):
            - identity axes: manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, event_seq,
            - origin link:
                  origin_flow_id, origin_event_seq (nullable for pure-fraud events),
                  origin_type as above,
            - `event_type` (AUTH_REQUEST, AUTH_RESPONSE, CLEARING, REFUND, LOGIN, etc.),
            - `event_ts_utc` (non-decreasing in event_seq per flow),
            - amounts, response codes, and any other event-level fields after overlay,
            - entity & routing context (copied from baseline; keys MUST NOT introduce new entities),
            - overlay metadata:
                  campaign_id, fraud_pattern_type, overlay_flags at event level.

DAG — 6B.S3 (baseline flows/events + config → campaigns + flows/events with overlay)  [RNG-BEARING]
---------------------------------------------------------------------------------------------------

[S0 gate & sealed_inputs_6B],
[Schema+Dict]
                ->  (S3.1) Verify S0 gate, sealed_inputs, and S1/S2 preconditions  (RNG-free)
                    - Resolve and validate:
                          s0_gate_receipt_6B,
                          sealed_inputs_6B.
                    - Recompute sealed_inputs_digest_6B from sealed_inputs_6B and
                      require equality with the value in s0_gate_receipt_6B.
                    - Require upstream_segments for {1A,1B,2A,2B,3A,3B,5A,5B,6A} to have status="PASS".
                    - Require, via layer run-report or equivalent control plane, that:
                          6B.S1 and 6B.S2 have status="PASS" for each (seed, manifest_fingerprint, scenario_id)
                          that S3 intends to process.
                    - If any of the above fails:
                          S3 MUST treat this as a precondition failure and MUST NOT read S1/S2 data-plane rows.

sealed_inputs_6B,
dataset_dictionary.layer3.6B.yaml,
artefact_registry_6B
                ->  (S3.2) Discover S3 work domain & resolve S3 configs  (RNG-free)
                    - From sealed_inputs_6B select rows with:
                          owner_segment="6B",
                          manifest_key ∈ {
                              "s2_flow_anchor_baseline_6B",
                              "s2_event_stream_baseline_6B",
                              "s3_campaign_catalogue_6B",
                              "s3_flow_anchor_with_fraud_6B",
                              "s3_event_stream_with_fraud_6B",
                              "fraud_campaign_catalogue_config_6B",
                              "fraud_overlay_policy_6B",
                              "fraud_rng_policy_6B"
                          },
                          status="REQUIRED".
                    - Resolve:
                          path_template, partition_keys, schema_ref
                      for S2 baseline datasets and S3 outputs via dictionary/registry.
                    - Enumerate (seed, scenario_id) to process by inspecting
                      s2_flow_anchor_baseline_6B (and/or s2_event_stream_baseline_6B) partitions.
                    - Resolve and validate S3 config packs:
                          fraud_campaign_catalogue_config_6B,
                          fraud_overlay_policy_6B,
                          fraud_rng_policy_6B,
                          behaviour_config_6B (if present).
                    - If any required pack is missing or schema-invalid:
                          S3 MUST fail preconditions and MUST NOT perform overlay.

s2_flow_anchor_baseline_6B,
s2_event_stream_baseline_6B,
6A bases & posture (as required),
optional 5A/5B/2B/3B context
                ->  (S3.3) Load baseline surfaces & build targeting indices  (RNG-free per partition)
                    - For each (seed, scenario_id) partition:
                          1. Read s2_flow_anchor_baseline_6B@{seed,fingerprint,scenario_id}.
                          2. Read s2_event_stream_baseline_6B@{seed,fingerprint,scenario_id}.
                          3. Validate:
                                · schema & PK/ordering invariants (anchors & events),
                                · every flow_id in event stream has exactly one anchor,
                                · anchors’ arrival_keys and session_id refer to valid S1 outputs (via referential checks).
                          4. If 6A surfaces are marked REQUIRED for S3 in sealed_inputs_6B:
                                · load relevant 6A bases, links, posture,
                                · build lookup indices:
                                      flow_id → entities (party, account, instrument, device, ip, merchant),
                                      entity → flows/events (per campaign segment definitions).
                          5. Optionally incorporate additional context (5A/5B/2B/3B) as read-only features:
                                · per-flow time-of-day/seasonality signals,
                                · routing/edge metadata for network-style attacks.
                    - Build in-memory indices for S3:
                          · flows_by_segment   (e.g. flows grouped by merchant/MCC/geo/channel/posture),
                          · events_by_flow     (sorted by event_seq),
                          · entities_by_segment (parties/accounts/devices/IPs by fraud role & region).

fraud_campaign_catalogue_config_6B,
behaviour_config_6B,
flow_rng_policy_6B,
rng_profile_layer3.yaml
                ->  (S3.4) Realise campaign instances (s3_campaign_catalogue_6B)  [RNG-bearing]
                    - For each (seed, scenario_id) in the work domain:
                          1. For each campaign template T in fraud_campaign_catalogue_config_6B:
                                 · derive **deterministic** base parameters for this (seed,scenario):
                                       - target segments (entity/flow/event constraints),
                                       - nominal activation window(s) in time,
                                       - intended intensity (e.g. expected number of flows/entities to affect),
                                       - campaign-specific knobs (patterns, phases).
                          2. Decide whether to activate T and, if so, how many instances:
                                 · if T is deterministic (always-on or always-off for this world),
                                       - compute N_instances(T) with NO RNG.
                                 · otherwise:
                                       - use rng_event_campaign_activation:
                                             * derive rng_stream_id and key from
                                               (manifest_fingerprint, parameter_hash, seed, scenario_id, template_id),
                                             * draw the configured number of uniforms,
                                             * map to N_instances(T) and any per-instance randomisation of parameters.
                          3. For each realised instance i of T:
                                 · assign a unique campaign_id within (seed,fingerprint,scenario_id),
                                 · fix instance-level parameters:
                                       - activation_start/end,
                                       - target segment filters,
                                       - per-instance intensity multipliers or quotas.
                          4. Append a row to s3_campaign_catalogue_6B describing each realised campaign_id,
                             including configuration ids and resolved parameters.
                    - Enforce invariants:
                          · every campaign_id is unique per (seed,fingerprint,scenario_id),
                          · campaign configuration fields match schema & config packs.

s3_campaign_catalogue_6B,
baseline targeting indices from S3.3,
fraud_campaign_catalogue_config_6B,
flow_rng_policy_6B
                ->  (S3.5) Select targets (entities/flows/events) for each campaign  [RNG-bearing]
                    - For each realised campaign_id in s3_campaign_catalogue_6B:
                          1. Derive **targeting domain** using campaign template + segment definitions:
                                 · candidate_entities(campaign_id) (parties/accounts/merchants/devices/IPs),
                                 · candidate_flows(campaign_id)    (from flows_by_segment),
                                 · optionally candidate_events(campaign_id).
                          2. Filter candidates by behaviour_config_6B (e.g. enable/disable some segments).
                          3. Construct per-candidate weights from template & posture:
                                 · w_entity, w_flow, w_event based on:
                                       - 6A fraud roles & segments,
                                       - flow attributes (amounts, merchants, channels, geos),
                                       - time-of-day/seasonality features.
                          4. Use rng_event_campaign_targeting to realise actual targets:
                                 · derive rng_stream_id & key from
                                   (manifest_fingerprint, parameter_hash, seed, scenario_id, campaign_id, maybe tier),
                                 · sample:
                                       - a subset of entities to involve,
                                       - a subset of flows (and, if needed, events) to overlay,
                                       - respecting intensity/quota constraints per campaign.
                          5. Record, in in-memory overlay plan structures:
                                 · per-flow list of campaign_ids impacting it,
                                 · per-flow flags indicating which aspects are to be mutated
                                   (amounts, routing, device/IP, extra events, timing), as implied by the template.
                    - Invariants:
                          · no flow/event may be assigned to a campaign if it violates that campaign’s template constraints,
                          · if a flow is targeted by multiple campaigns, the combined overlay policy must define a clear precedence.

fraud_overlay_policy_6B,
flow_rng_policy_6B,
overlay plan from S3.5,
baseline flows/events (S2),
rng_profile_layer3.yaml
                ->  (S3.6) Apply overlays (plan mutations & new flows/events)  [RNG-bearing]
                    - For each flow_id in the baseline:
                          1. Determine which campaigns (if any) target this flow, and in what order:
                                 · derive an ordered list of (campaign_id, tactic_set) from overlay policy
                                   and the targeting results from S3.5.
                          2. Construct an initial working copy of the flow:
                                 · copy baseline anchor & event sequence.
                          3. For each (campaign_id, tactic_set) in order:
                                 · for each tactic (e.g. amount shift, device swap, add test auths, insert refund):
                                       - decide deterministically or via rng_event_overlay_mutation
                                         whether the tactic is applied, and with what parameters:
                                             * amount deltas or scaling factors,
                                             * which event positions to touch,
                                             * which device/IP/merchant edge to swap to,
                                             * how many new events to insert and where.
                                       - apply the tactic to the working copy:
                                             * mutate event attributes (amounts, routing, timestamps within allowed jitter),
                                             * insert new events (pure-fraud events),
                                             * optionally mark some baseline events as “logically suppressed”
                                               (but do not delete them from the baseline dataset).
                          4. After all campaigns are applied:
                                 · ensure resulting event sequence is consistent:
                                       - event_ts_utc non-decreasing in event_seq,
                                       - entity & routing keys remain valid 6A entities,
                                       - constraints from overlay_policy_6B are respected (e.g. limits on magnitude of shifts).
                          5. For flows not targeted by any campaign:
                                 · copy baseline anchor/events unchanged,
                                   marking origin_type=BASELINE_UNTOUCHED and fraud_pattern_type=NONE.
                    - For **pure-fraud** flows (campaigns that synthesize flows from scratch):
                          · construct flow_ids not present in the baseline:
                                - assign unique flow_id,
                                - generate event sequences entirely from campaign templates + RNG,
                                - treat origin_flow_id as NULL and origin_type=PURE_FRAUD_FLOW.

overlayed working copies from S3.6,
schemas.6B.yaml#/s3/flow_anchor_with_fraud_6B,
schemas.6B.yaml#/s3/event_stream_with_fraud_6B
                ->  (S3.7) Materialise s3_flow_anchor_with_fraud_6B & s3_event_stream_with_fraud_6B  (RNG-free)
                    - For each flow (baseline or pure-fraud) after overlay:
                          1. Build a row in s3_flow_anchor_with_fraud_6B:
                                 · identity & linkage:
                                       manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id,
                                       origin_flow_id (baseline flow_id or NULL), origin_type,
                                       session_id, arrival_keys[],
                                 · timing & amounts:
                                       first_auth_ts_utc, final_auth_ts_utc,
                                       clear_ts_utc?, refund_ts_utc?,
                                       auth_amount, clear_amount, refund_amount, transaction_currency,
                                 · overlay metadata:
                                       campaign_id (single or a primary campaign id),
                                       fraud_pattern_type,
                                       overlay_flags,
                                       overlay_severity_score (if configured),
                                 · entity & routing context:
                                       party_id, account_id, instrument_id?, device_id, ip_id,
                                       merchant_id, site_id/edge_id, zone/tz, is_virtual.
                          2. For each event in the final working sequence:
                                 · assign event_seq (0..N-1 or 1..N, as per schema),
                                 · construct a row in s3_event_stream_with_fraud_6B with:
                                       manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, event_seq,
                                       origin_flow_id, origin_event_seq (if derived from baseline),
                                       origin_type,
                                       event_type, event_ts_utc,
                                       amounts & codes after overlay,
                                       entity & routing context,
                                       campaign_id, fraud_pattern_type, overlay_flags at event level.
                          3. Enforce invariants:
                                 · event_ts_utc non-decreasing in event_seq per flow,
                                 · for every baseline flow_id:
                                       - exactly one row in s2_flow_anchor_baseline_6B,
                                       - exactly one row in s3_flow_anchor_with_fraud_6B,
                                 · for every baseline event:
                                       - either referenced by at least one with_fraud event (via origin_flow_id, origin_event_seq),
                                         or explicitly left untouched with origin_type=BASELINE_UNTOUCHED semantics.
                    - Write s3_flow_anchor_with_fraud_6B and s3_event_stream_with_fraud_6B for this (seed,scenario)
                      using paths & partitioning from dataset_dictionary.layer3.6B.yaml and atomic write patterns.
                    - Validate against schemas.6B.yaml anchors and PK/ordering invariants.

rng_event_campaign_activation,
rng_event_campaign_targeting,
rng_event_overlay_mutation,
rng_trace_log (Layer-3)
                ->  (S3.8) RNG accounting & per-partition metrics  (RNG-free aggregation)
                    - For each (seed,scenario) partition:
                          · summarise counts of rng_event_campaign_activation, rng_event_campaign_targeting,
                            and rng_event_overlay_mutation events,
                          · compute expected_draws and expected_blocks per family from:
                                - number of templates and campaigns (activation),
                                - number of targeted entities/flows/events (targeting),
                                - number of overlay decisions (mutation),
                          · reconcile with rng_trace_log:
                                - counters monotone per stream,
                                - blocks/draws match expected totals within tolerances,
                                - no draws from families not declared for S3.
                    - Record metrics in internal run-report structures for S5; S3 MUST NOT publish separate
                      public datasets for RNG accounting.

Downstream touchpoints
----------------------
- **6B.S4 (truth & bank-view labels, case timelines):**
    - Reads:
          s3_campaign_catalogue_6B,
          s3_flow_anchor_with_fraud_6B,
          s3_event_stream_with_fraud_6B.
    - Treats:
          S3 outputs as the authoritative post-overlay behaviour:
              - S2 baseline surfaces remain the “no-fraud” reference,
              - S4 MUST NOT mutate S3 surfaces in place.

- **6B.S5 (segment validation & HashGate):**
    - Validates:
          structural & PK/ordering invariants for all S3 outputs,
          consistency between baseline (S2) and with-fraud (S3) surfaces,
          coverage & provenance of campaigns,
          RNG accounting for S3 families.

- **Layer-4 / external consumers:**
    - May use S3 surfaces to understand generated fraud patterns and coverage,
      but MUST respect the 6B HashGate (S5) and authority boundaries (S2, 6A, 5B).
```
