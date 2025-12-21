```text
                  LAYER 3 · SEGMENT 6B — BEHAVIOURAL WORLD, FRAUD STORIES & LABELS

Authoritative upstream & inputs (sealed by 6B.S0)
-------------------------------------------------
[World identity]
    - manifest_fingerprint      (which L1/L2/6A world we’re on)
    - parameter_hash            (which 6B configuration/behaviour pack)
    - seed                      (behavioural RNG seed; S1–S4 are seed-scoped)
    - scenario_id               (traffic scenario id; S1–S4 are also scenario-scoped)

[Upstream segments that MUST be PASS for this manifest_fingerprint]
    - Layer 1:
        · 1A — merchant universe & outlet counts
        · 1B — site/location universe
        · 2A — civil time / time-zone surfaces
        · 2B — routing & alias plans (sites/edges)
        · 3A — zone allocations per merchant (outlets by zone)
        · 3B — virtual merchants & edge universe
    - Layer 2:
        · 5A — deterministic intensity surfaces (λ over merchant×zone×time×scenario)
        · 5B — realised arrivals (timestamps + routing to sites/edges)
    - Layer 3:
        · 6A — static entity graph & fraud posture (parties, accounts, instruments, devices, IPs)

    - For all of the above:
        · their own validation bundles and `_passed.flag_*` MUST validate,
        · 6B.S0 re-computes bundle digests and records PASS/MISSING/FAIL;
          any required FAIL/MISSING means 6B MUST NOT run for that world.

[Sealed static world from 6A]
    - 6A bases and links:
        · party_base_6A, account_base_6A, instrument_base_6A,
          device_base_6A, ip_base_6A,
          account↔instrument, device↔entity, ip↔entity link tables.
    - 6A fraud posture:
        · per-entity fraud roles (party/account/merchant/device/IP).
    - 6A HashGate:
        · validation bundle + `_passed.flag_6A` per manifest_fingerprint.
    - 6B MUST treat 6A as:
        · closed, immutable static truth about entities and roles.

[Sealed arrival world from 5B]
    - 5B arrival egress:
        · arrival_events_5B keyed by (seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq),
          with timestamps and routing to sites/edges.
    - 5B HashGate:
        · validation bundle + `_passed.flag_5B` per manifest_fingerprint.
    - 6B MUST:
        · use 5B arrivals as the only arrival universe,
        · never invent extra arrivals or change 5B identity/timestamps/routing.

[6B priors, policies & RNG profiles]
    - S1 policies:
        · attachment_policy_6B      (arrival→entity attachment rules),
        · sessionisation_policy_6B  (session key, gap thresholds, optional stochastic boundaries).
    - S2 policies:
        · flow_shape_policy_6B      (flows per session, flow types and structures),
        · amount_model_6B           (amount distributions & relationships),
        · timing_policy_6B          (intra-flow timing offsets).
    - S3 policies:
        · fraud_campaign_catalogue_config_6B  (campaign templates & intensities),
        · fraud_overlay_policy_6B             (how campaigns mutate flows & events).
    - S4 policies:
        · truth_labelling_policy_6B   (flow truth labels & event truth roles),
        · bank_view_policy_6B         (bank’s decisions & outcomes),
        · delay_models_6B             (detection/dispute/chargeback delays),
        · case_policy_6B              (case keys & case lifecycle).
    - RNG:
        · Layer-3 Philox profile,
        · 6B RNG policies for:
              S1: entity_attach, session_boundary,
              S2: flow_shape, event_timing, amount_draw,
              S3: campaign_activation, campaign_targeting, overlay_mutation,
              S4: truth_label_ambiguity, detection_delay, dispute_delay,
                  chargeback_delay, case_timeline.
    - Validation:
        · segment_validation_policy_6B (which checks S5 runs, thresholds, severity),
        · behaviour_config_6B          (feature flags, scopes).


DAG — Segment 6B overview
-------------------------

(Sealed world: Layers 1–2, 6A + 5B arrivals + 6B policies)
    -> (S0) BEHAVIOURAL GATE & SEALED INPUTS           [NO RNG]
        inputs:
            - 6B world identity (manifest_fingerprint, parameter_hash),
            - upstream validation bundles & `_passed.flag_*` for 1A–3B, 5A–5B, 6A,
            - 6B schemas, dictionaries, artefact registries,
            - 6B configuration packs & RNG policies.
        -> sealed_inputs_6B@fingerprint
             - Discovers and fixes the complete set of artefacts 6B may read:
                  · Layer-1/2/3 datasets (arrivals, entities, etc.),
                  · 6B policies & RNG profiles,
               with their paths, schema_refs, roles, checksums and read_scope.
        -> s0_gate_receipt_6B@fingerprint
             - Records:
                  upstream gate status (PASS/MISSING/FAIL per segment),
                  which 6B contracts were used (paths + digests),
                  sealed_inputs_digest_6B.
             - This is the only authoritative description of
               “which world and which inputs 6B runs against”.

                                      |
                                      | s0_gate_receipt_6B, sealed_inputs_6B
                                      v

(S1) ARRIVAL→ENTITY ATTACHMENT & SESSIONISATION      [RNG-BEARING]
    inputs:
        - sealed_inputs_6B, s0_gate_receipt_6B,
        - 5B arrivals (arrival_events_5B),
        - 6A entity graph & posture (bases, links, roles),
        - attachment_policy_6B, sessionisation_policy_6B, RNG policy.
    -> s1_arrival_entities_6B@seed,fingerprint,scenario
         - For every arrival:
              - builds candidate entities (party/account/instrument/device/IP),
              - uses priors + RNG (where needed) to pick exact attachments,
              - joins in static posture/context (read-only),
              - assigns a session_id based on a deterministic/stochastic
                sessionisation policy.
         - Outputs one row per arrival carrying:
              arrival identity (from 5B),
              attached entities,
              session_id.
    -> s1_session_index_6B@seed,fingerprint,scenario
         - Defines the **session universe**:
              one row per session with:
              session key (e.g. party×device×merchant×channel×scenario),
              start/end timestamps, arrival_count, coarse gap metrics.

    - S1 is where “who generated each arrival and which arrivals form a session” is realised.

                                      |
                                      | s1_arrival_entities_6B, s1_session_index_6B
                                      v

(S2) BASELINE TRANSACTIONAL FLOWS & EVENTS          [RNG-BEARING]
    inputs:
        - s1_arrival_entities_6B, s1_session_index_6B,
        - (optional) 6A context & 5A/2B/3B surfaces as features,
        - flow_shape_policy_6B, amount_model_6B, timing_policy_6B, RNG policy.
    -> s2_flow_anchor_baseline_6B@seed,fingerprint,scenario
         - For each session:
              - decides (deterministically or via RNG) how many flows it contains,
                and which arrivals belong to which flow,
              - for each flow:
                    chooses a flow type (auth-only, auth+clear, auth+clear+refund, etc.),
                    plans amounts & currencies from amount priors,
                    plans event-level timing within the session window.
         - Summarises each **baseline flow** with:
              session_id, arrival_keys[],
              timing & amount summary, entity & routing context,
              baseline outcome flags (no fraud yet).
    -> s2_event_stream_baseline_6B@seed,fingerprint,scenario
         - Expands every baseline flow into a time-ordered sequence of events
           (AUTH_REQUEST, AUTH_RESPONSE, CLEARING, REFUND, etc.),
           with concrete timestamps and amounts.

    - S2 is where “what would this world look like if everything were legitimate” is realised.

                                      |
                                      | s2_flow_anchor_baseline_6B,
                                      | s2_event_stream_baseline_6B,
                                      | 6A posture, fraud campaign configs
                                      v

(S3) FRAUD & ABUSE CAMPAIGN OVERLAY                 [RNG-BEARING]
    inputs:
        - baseline flows/events (S2),
        - 6A posture & entity graph (targets),
        - fraud_campaign_catalogue_config_6B,
        - fraud_overlay_policy_6B,
        - fraud RNG policy.
    -> s3_campaign_catalogue_6B@seed,fingerprint,scenario
         - Realises campaign templates into concrete instances:
              how many of each type,
              their time windows,
              targeting segments and intensities for this world.
    -> s3_flow_anchor_with_fraud_6B@seed,fingerprint,scenario
    -> s3_event_stream_with_fraud_6B@seed,fingerprint,scenario
         - For each campaign instance:
              - samples which entities/sessions/flows to target,
              - applies overlay tactics (amount shifts, routing anomalies,
                extra auths, abusive refunds, synthetic flows, etc.),
                using RNG where policy says so.
         - Produces a **post-overlay world**:
              all flows (baseline and pure-fraud) and all events,
              now carrying overlay metadata (campaign_id, fraud_pattern_type,
              overlay_flags, severity), but still no truth/bank labels.

    - S3 is where “clean flows are corrupted into fraud/abuse stories” is realised.

                                      |
                                      | s3_flow_anchor_with_fraud_6B,
                                      | s3_event_stream_with_fraud_6B,
                                      | 6A posture, S2 baseline (for context),
                                      | labelling, bank-view & case policies
                                      v

(S4) TRUTH & BANK-VIEW LABELLING + CASE TIMELINES   [RNG-BEARING]
    inputs:
        - s3_flow_anchor_with_fraud_6B, s3_event_stream_with_fraud_6B,
        - (optional) baseline S2 + S1/6A context as features,
        - truth_labelling_policy_6B,
        - bank_view_policy_6B, delay_models_6B,
        - case_policy_6B, RNG policy.
    -> s4_flow_truth_labels_6B@seed,fingerprint,scenario
         - Assigns a **truth label** to every flow:
              LEGIT vs FRAUD vs ABUSE,
              plus more detailed subtypes (card testing, ATO, refund abuse, mules, etc.),
              using deterministic rules or RNG where ambiguity is allowed.
    -> s4_flow_bank_view_6B@seed,fingerprint,scenario
         - Simulates the bank’s response to each flow:
              auth decision,
              detection/no-detection and channel,
              dispute/chargeback outcomes and timings,
              high-level bank-view labels (e.g. BANK_CONFIRMED_FRAUD vs NO_CASE_OPENED).
    -> s4_event_labels_6B@seed,fingerprint,scenario
         - Gives each event a role:
              truth-level (primary fraud action, supporting action, clean context),
              bank-level (detection action, case action, ordinary event).
    -> s4_case_timeline_6B@seed,fingerprint
         - Groups flows into **cases** via case_policy_6B,
           assigns case_ids, and builds ordered case event timelines
           (CASE_OPENED, ALERT_RAISED, CASE_UPDATED, CASE_CLOSED, …),
           using delay models and RNG where configured.

    - S4 is where “ground truth, bank-view and cases for the whole world” are realised.

                                      |
                                      | all 6B surfaces S1–S4,
                                      | RNG logs & trace,
                                      | segment_validation_policy_6B
                                      v

(S5) SEGMENT VALIDATION & 6B HASHGATE              [NO RNG]
    inputs:
        - s0_gate_receipt_6B, sealed_inputs_6B,
        - all 6B outputs from S1–S4,
        - 6B RNG event logs and Layer-3 rng_trace_log,
        - segment_validation_policy_6B.
    -> s5_validation_report_6B@fingerprint
         - Runs structural, behavioural and RNG accounting checks:
              structural: schemas, PK/ordering, referential links across S1–S4,
              behavioural: fraud rates, detection rates, campaign coverage vs config,
              RNG: that S1–S4 used only the allowed RNG families, with correct budgets,
              cross-surface invariants:
                  arrivals → sessions → baseline flows → with-fraud flows →
                  truth labels → bank view → cases.
         - Summarises results in one world-level report with per-check metrics,
           and an overall_status ∈ {PASS, FAIL}.
    -> s5_issue_table_6B@fingerprint (optional)
         - Per-issue detail for checks configured to produce row-level diagnostics.
    -> validation_bundle_6B + `_passed.flag_6B`@fingerprint
         - If and only if overall_status == "PASS":
              - packages s5_validation_report_6B, s5_issue_table_6B (if present)
                and any evidence files into a bundle,
              - writes index.json with per-file digests,
              - computes bundle SHA-256 and writes `_passed.flag_6B` with that digest.
         - This pair (bundle + flag) is the **6B HashGate**:
              no verified flag → no 6B read.

Downstream obligations
----------------------
- **Control & Ingress / Execution plane (outside the Data Engine):**
    - MUST treat Segment 6B as:
          the complete behavioural, fraud, label and case universe for a world.
    - MUST:
          verify the 6B HashGate:
              - recompute the bundle digest from validation_bundle_6B/index.json,
              - require equality with `_passed.flag_6B`,
          before reading any S1–S4 datasets.
    - MUST NOT:
          read or consume 6B outputs if `_passed.flag_6B` is missing or invalid.

- **Decision & Learning planes (models, feature factories, evaluation tooling):**
    - MUST:
          use s4_flow_truth_labels_6B as the source of ground truth for flows,
          use s4_flow_bank_view_6B and s4_event_labels_6B for bank-centric evaluation,
          use s4_case_timeline_6B as the case universe,
          and ALWAYS gate on `_passed.flag_6B` for the relevant manifest_fingerprint.
    - SHOULD:
          use S2/S3 as “clean vs with-fraud” references when analysing attack patterns.

- **Audit, governance & reproducibility tooling:**
    - SHOULD:
          treat s0_gate_receipt_6B + sealed_inputs_6B + s5_validation_report_6B +
          validation_bundle_6B + `_passed.flag_6B` as the canonical explanation of:
              - which world was used,
              - which upstream segments were trusted,
              - which inputs & policies 6B had,
              - and whether the generated behavioural universe is acceptable.

Legend
------
(Sx) = state in Segment 6B
[seed, fingerprint, scenario] = partitions for S1–S4 behavioural outputs
[fingerprint]                  = partitions for S0 & S5 validation artefacts
[NO RNG]                       = state consumes no RNG
[RNG-BEARING]                  = state consumes RNG under Layer-3 RNG policy
HashGate (6B)                  = validation_bundle_6B/index.json + `_passed.flag_6B`
                                 per manifest_fingerprint (no PASS → no read)
```
