```text
        LAYER 3 · SEGMENT 6B — STATE S2 (BASELINE TRANSACTIONAL FLOW SYNTHESIS)  [RNG-BEARING]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_6B
      @ data/layer3/6B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json
      · provides, for this world:
          - manifest_fingerprint        (world id from Layers 1–3),
          - parameter_hash              (6B parameter pack),
          - run_id                      (6B run identity; S2 outputs MUST NOT depend on it),
          - sealed_inputs_digest_6B     (hash over sealed_inputs_6B),
          - upstream_segments{seg_id → {status,bundle_path,bundle_sha256,flag_path}},
          - contracts_6B{logical_id → {path,sha256_hex,schema_ref,role}},
          - spec_version_6B, created_utc.
      · S2 MUST:
          - resolve and validate this object before doing any work,
          - require all required upstream segments {1A,1B,2A,2B,3A,3B,5A,5B,6A} to have status="PASS",
          - treat upstream_segments as the sole authority on upstream gate status.

    - sealed_inputs_6B
      @ data/layer3/6B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet
      · one row per artefact 6B is allowed to read for this world:
          - owner_layer, owner_segment, manifest_key,
          - path_template, partition_keys[], schema_ref,
          - sha256_hex, role, status, read_scope.
      · S2 MUST:
          - recompute sealed_inputs_digest_6B (canonical serialisation) and require equality with the value in s0_gate_receipt_6B,
          - resolve all dataset locations via sealed_inputs_6B + owning segment dictionaries/registries,
          - NEVER construct dataset paths by hand,
          - NEVER read artefacts not listed in sealed_inputs_6B,
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → only presence/shape checks, no row-level logic.

[Schema+Dict · shape & catalogue authority]
    - schemas.layer3.yaml, schemas.6B.yaml
        · shape authority for:
              - s1_arrival_entities_6B,
              - s1_session_index_6B,
              - s2_flow_anchor_baseline_6B,
              - s2_event_stream_baseline_6B.
    - dataset_dictionary.layer3.6B.yaml
        · IDs & contracts for:
              - s1_arrival_entities_6B
                · path:
                    data/layer3/6B/s1_arrival_entities_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
                · partitioning: [seed, fingerprint, scenario_id]
                · primary_key:
                      [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
                · ordering:
                      [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
                · schema_ref: schemas.6B.yaml#/s1/arrival_entities_6B
              - s1_session_index_6B
                · path:
                    data/layer3/6B/s1_session_index_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
                · partitioning: [seed, fingerprint, scenario_id]
                · primary_key:
                      [seed, manifest_fingerprint, scenario_id, session_id]
                · ordering:
                      [seed, manifest_fingerprint, scenario_id, session_id]
                · schema_ref: schemas.6B.yaml#/s1/session_index_6B
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

[Primary data-plane inputs (S1 outputs)]
    - s1_arrival_entities_6B   (REQUIRED, ROW_LEVEL)
      · one row per arrival in the (seed, manifest_fingerprint, scenario_id) domain:
            - carries arrival identity & routing from 5B,
            - entity attachments: party_id, account_id, instrument_id?, device_id, ip_id,
            - session_id assigned by S1,
            - optional copied context from 6A (segments, posture).
      · Authority:
            - which entities each arrival is attached to,
            - that these attachments and session_ids MUST NOT be changed by S2.

    - s1_session_index_6B      (REQUIRED, ROW_LEVEL)
      · one row per session:
            - session_id,
            - session key fields (e.g. party_id, device_id, merchant_id, channel_group, scenario_id),
            - session_start_utc, session_end_utc,
            - arrival_count and coarse aggregates.
      · Authority:
            - session existence & identity,
            - baseline time windows for behaviour planning.
      · S2 MUST NOT redefine session boundaries or session_ids.

[Optional upstream context (5B, 6A, 5A/2B/3B)]
    - arrival_events_5B    (typically METADATA_ONLY for S2)
      · S2 MAY use this only to cross-check identity/time/routing against S1,
        but MUST NOT reattach entities directly to 5B arrivals or bypass S1.

    - 6A bases & posture (ROW_LEVEL, OPTIONAL)
      · S2 MAY read 6A surfaces (party/account/instrument/device/IP bases & link tables, fraud roles)
        as context to influence flow shapes, amounts, timing priors, or validation,
        but MUST NOT:
            - invent or mutate entities,
            - change static fraud posture.

    - 5A/2B/3B context (OPTIONAL)
      · intensity surfaces, routing plans, virtual routing policy, etc.
      · S2 MAY use as extra features when deciding shapes/timing,
        but MUST NOT change upstream routing or arrivals.

[6B configuration & policy inputs for S2]
    - flow_shape_policy_6B       (behaviour_prior / flow_policy)
      · how many flows per session,
      · flow types & structures (auth-only, auth+clear, auth+clear+refund, etc.),
      · arrival→flow assignment rules (one-to-one vs many-to-one).

    - amount_model_6B            (behaviour_prior / amount_policy)
      · per-merchant/segment distributions over amounts & currencies,
      · relationships between auth, clearing, refund amounts.

    - timing_policy_6B           (behaviour_prior / timing_policy)
      · distributions over intra-session & intra-flow time offsets,
      · constraints relative to session windows and arrival timestamps.

    - flow_rng_policy_6B         (RNG policy for S2)
      · mapping from S2 RNG families → rng_stream_id & budgets, e.g.:
            rng_event_flow_shape,
            rng_event_event_timing,
            rng_event_amount_draw.

    - behaviour_config_6B (if present)
      · feature flags, domain filters, and guardrails that may constrain:
            which sessions are eligible for multiple flows,
            which flows may have refunds, etc.

[RNG & envelope policies]
    - rng_profile_layer3.yaml
      · global Philox configuration & envelope rules for Layer-3.
    - rng_policy_6B.yaml   (referenced by flow_rng_policy_6B)
      · declares:
            - the S2 RNG families,
            - their per-event budgets (`blocks`, `draws`),
            - how RNG counters map to (manifest_fingerprint, parameter_hash, seed, scenario_id, session_id, flow_id).

[Outputs owned by S2]
    - s2_flow_anchor_baseline_6B
      @ data/layer3/6B/s2_flow_anchor_baseline_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, flow_id]
      · ordering:
            [seed, manifest_fingerprint, scenario_id, flow_id]
      · logical content:
            - identity axes: manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id,
            - linkage:
                  session_id,
                  arrival_keys (one or more arrivals from S1),
            - timing summary:
                  first_auth_ts_utc, final_auth_ts_utc,
                  clear_ts_utc?, refund_ts_utc?, etc.,
            - amount summary:
                  auth_amount, clear_amount, refund_amount, transaction_currency,
            - baseline outcome flags (no fraud/dispute semantics),
            - entity & routing context (copied, not mutated),
            - provenance for RNG families used for the flow (optional).

    - s2_event_stream_baseline_6B
      @ data/layer3/6B/s2_event_stream_baseline_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
      · ordering:
            [seed, manifest_fingerprint, scenario_id, flow_id, event_seq]
      · logical content:
            - identity axes: manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, event_seq,
            - `event_type` (AUTH_REQUEST, AUTH_RESPONSE, CLEARING, REFUND, etc.),
            - `event_ts_utc` (monotone non-decreasing in event_seq per flow),
            - event-level amounts, response codes, flags,
            - full entity & routing context (copied from S1 / arrivals/ sessions),
            - optional linkage back to arrival(s) that seeded the flow.

DAG — 6B.S2 (attached arrivals + sessions → baseline flows & events)  [RNG-BEARING]
-----------------------------------------------------------------------------------

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S2.1) Verify S0 gate & sealed_inputs_6B  (RNG-free)
                    - Resolve:
                        · s0_gate_receipt_6B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_6B@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer3.6B.yaml.
                    - Validate both against schemas.layer3.yaml and schemas.6B.yaml.
                    - Recompute sealed_inputs_digest_6B from sealed_inputs_6B
                      (canonical row order + serialisation); require equality with receipt.
                    - Check upstream_segments in receipt:
                        · required segments {1A,1B,2A,2B,3A,3B,5A,5B,6A} MUST have status="PASS".
                    - If any check fails:
                        · S2 MUST fail and MUST NOT emit s2_flow_anchor_baseline_6B or s2_event_stream_baseline_6B.

sealed_inputs_6B,
dataset_dictionary.layer3.6B.yaml,
artefact_registry_6B
                ->  (S2.2) Discover work domain & resolve S2 configs  (RNG-free)
                    - From sealed_inputs_6B, extract rows with:
                        · owner_segment="6B",
                        · manifest_key ∈ {"s1_arrival_entities_6B", "s1_session_index_6B"},
                        · status      = "REQUIRED",
                        · read_scope  = "ROW_LEVEL".
                    - Using dictionary+registry, resolve:
                        · path_template, partition_keys for s1_arrival_entities_6B and s1_session_index_6B.
                    - Determine the (seed, scenario_id) partitions to process:
                        · by enumerating partitions of s1_arrival_entities_6B (and/or s1_session_index_6B),
                          optionally filtered by behaviour_config_6B.
                    - Resolve and validate S2 config artefacts:
                        · flow_shape_policy_6B,
                        · amount_model_6B,
                        · timing_policy_6B,
                        · flow_rng_policy_6B (and underlying rng_profile_layer3.yaml).
                    - If any required S2 config is missing or schema-invalid:
                        · S2 MUST fail preconditions.

s1_arrival_entities_6B,
s1_session_index_6B,
optional 6A/5A/2B/3B context (as allowed by sealed_inputs_6B)
                ->  (S2.3) Load S1 outputs & build in-memory session views  (RNG-free)
                    - For each (seed, scenario_id) partition:
                        1. Read s1_arrival_entities_6B@{seed,fingerprint,scenario_id}.
                        2. Read s1_session_index_6B@{seed,fingerprint,scenario_id}.
                        3. Validate:
                             - schemas.6B.yaml anchors for both tables,
                             - PK uniqueness & ordering invariants,
                             - that every session_id present in s1_arrival_entities_6B
                               exists in s1_session_index_6B,
                             - that arrival_count in s1_session_index_6B matches
                               the number of arrivals per session_id.
                        4. Optionally join selected 6A/5A/2B/3B attributes onto in-memory views
                           (for priors only; MUST NOT change S1 identity/attachments).
                        5. Build indices:
                             - session_index: session_id → session record,
                             - arrivals_by_session: session_id → [arrival rows], sorted by ts_utc (and/or arrival_seq).

flow_shape_policy_6B,
flow_rng_policy_6B,
session_index & arrivals_by_session
                ->  (S2.4) Session-level flow planning (number of flows & arrival→flow assignment)  (RNG-bearing)
                    - For each session s in s1_session_index_6B:
                        1. Build **session planning context** using:
                               - session window: session_start_utc, session_end_utc, arrival_count,
                               - entities: party/account/instrument/device/IP for this session,
                               - merchant/channel/zone/scenario context,
                               - any relevant 6A posture or 5A/2B surfaces (if joined).
                        2. Determine number of flows N_flows(s):
                               - If flow_shape_policy_6B declares a deterministic rule for s:
                                     · compute N_flows(s) with NO RNG.
                               - Else:
                                     · use rng_event_flow_shape (session-level family):
                                           * derive rng_stream_id from (manifest_fingerprint, parameter_hash,
                                              seed, scenario_id, session_id),
                                           * consume the configured number of Philox uniforms,
                                           * map them via the policy to an integer N_flows(s) ≥ 0.
                        3. Assign arrivals in this session to flows:
                               - If N_flows(s) == 0:
                                     · policy MUST specify a fallback (e.g. N_flows(s)=1 with a degenerate shape),
                                       or S2 MUST treat this as an invalid configuration.
                               - If N_flows(s) == 1:
                                     · assign all arrivals in s to the single flow (order-preserving).
                               - If N_flows(s) > 1:
                                     · use flow_shape_policy_6B to decide which arrivals belong to which flow,
                                       optionally consuming additional rng_event_flow_shape draws (with
                                       budgets fixed by arrival_count and N_flows(s)).
                                     · ensure every arrival in the session is assigned to exactly one flow.
                        4. Allocate a unique flow_id per flow within (seed, manifest_fingerprint, scenario_id),
                           using a deterministic scheme (e.g. monotonically increasing counter or hash of
                           (session_id, local_flow_index)).
                    - At the end of this step, S2 has a mapping:
                        · session_id → {flow_ids},
                        · flow_id → {session_id, assigned_arrival_keys}.

timing_policy_6B,
amount_model_6B,
flow_shape_policy_6B,
flow_rng_policy_6B,
session & arrival context,
flow assignments from S2.4
                ->  (S2.5) Intra-flow event planning (flow types, event templates, timing & amounts)  [RNG-bearing]
                    - For each flow f:
                        1. Build **flow planning context**:
                               - parent session context (window, entities, merchant/channel/zone/scenario),
                               - arrivals assigned to f (their ts_utc and routing),
                               - any relevant priors from 6A posture or intensities.
                        2. Decide **flow scenario / type**:
                               - auth-only vs auth+clear vs auth+clear+refund, etc.,
                               - use flow_shape_policy_6B:
                                     · deterministic for some contexts, or
                                     · stochastic via rng_event_flow_shape (flow-level component) with
                                       budgets fixed by the chosen type.
                        3. Plan **event template**:
                               - sequence of event_type values (AUTH_REQUEST, AUTH_RESPONSE, CLEARING, REFUND, etc.),
                               - required event-specific attributes (e.g. response codes).
                        4. Plan **event timing**:
                               - derive base timestamps from arrivals/sessions (anchor event),
                               - for each event in template, draw or compute offsets using timing_policy_6B:
                                     · if stochastic:
                                           - use rng_event_event_timing (flow-level family),
                                           - consume a fixed number of uniforms per event,
                                           - ensure offsets respect constraints (e.g. auth before clearing).
                               - ensure event_ts_utc is non-decreasing in event_seq.
                        5. Plan **amounts & currencies**:
                               - use amount_model_6B to decide:
                                     · auth_amount, clear_amount, refund_amount, transaction_currency,
                                     · relationships between these amounts (e.g. refund ≤ clear).
                               - if stochastic:
                                     · use rng_event_amount_draw family with budgets fixed per flow/event.
                        6. Record per-flow planned values:
                               - event template with planned (event_type, event_seq, planned_ts_utc, planned_amounts),
                               - any baseline outcome flags implied by the template (e.g. “auth approved then cleared”).

flow templates & planned values from S2.5,
session & arrival context,
schemas.6B.yaml#/s2/event_stream_baseline_6B
                ->  (S2.6) Instantiate events & materialise s2_event_stream_baseline_6B  (RNG-free)
                    - For each flow f:
                        1. For each planned event in f’s template:
                               - compute `event_ts_utc` from planned offsets and base timestamps,
                               - assign `event_seq` (0..N-1 or 1..N, consistent with schema),
                               - attach:
                                     · identity axes: manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, event_seq,
                                     · event_type,
                                     · event_ts_utc,
                                     · event-specific fields (amounts, response codes, etc.),
                                     · entity context (party_id, account_id, instrument_id?, device_id, ip_id),
                                     · routing context (site_id/edge_id, zone/tz, is_virtual),
                                     · linkage back to source arrivals if required by schema.
                        2. Enforce invariants:
                               - event_ts_utc non-decreasing in event_seq per flow,
                               - keys & types conform to schemas.6B.yaml#/s2/event_stream_baseline_6B.
                    - Write s2_event_stream_baseline_6B for this (seed,scenario) partition:
                        · path and partitioning as per dataset_dictionary.layer3.6B.yaml,
                        · ensure primary_key and ordering invariants hold,
                        · use atomic write (staging → fsync → move).
                    - S2 MUST NOT consume RNG in this step; all stochastic choices were made in S2.4–S2.5.

s2_event_stream_baseline_6B,
s1_arrival_entities_6B,
s1_session_index_6B,
schemas.6B.yaml#/s2/flow_anchor_baseline_6B
                ->  (S2.7) Construct flow anchors & enforce invariants, then materialise s2_flow_anchor_baseline_6B  (RNG-free)
                    - For each flow_id in s2_event_stream_baseline_6B:
                        1. Aggregate from events:
                               - first_auth_ts_utc, final_auth_ts_utc,
                               - clear_ts_utc?, refund_ts_utc?, etc.,
                               - auth_amount, clear_amount, refund_amount, transaction_currency,
                               - baseline outcome flags derived purely from baseline event sequence
                                 (e.g. approved-and-cleared vs declined, no fraud semantics).
                        2. Link to session & arrivals:
                               - session_id from the flow’s parent session,
                               - arrival_keys (the set of (merchant_id, arrival_seq) from S1 assigned to this flow),
                               - enforce that these arrivals exist and are unique.
                        3. Copy entity & routing context from S1/S1+arrivals:
                               - party_id, account_id, instrument_id?, device_id, ip_id,
                               - merchant_id, site_id/edge_id, zone/tz, is_virtual.
                        4. Construct s2_flow_anchor_baseline_6B row with:
                               - identity axes: manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id,
                               - session_id, arrival_keys,
                               - timing and amount summaries,
                               - baseline outcome flags,
                               - any optional provenance fields for S3/S4/S5.
                        5. Enforce invariants:
                               - every flow_id present in s2_event_stream_baseline_6B has exactly one anchor row,
                               - every anchor’s session_id exists in s1_session_index_6B,
                               - every arrival referenced in arrival_keys exists in s1_arrival_entities_6B
                                 and is assigned to exactly one flow.
                    - Write s2_flow_anchor_baseline_6B for this (seed,scenario) partition:
                        · path and partitioning as per dataset_dictionary.layer3.6B.yaml,
                        · ensure primary_key and ordering invariants hold,
                        · use atomic write (staging → fsync → move).
                    - S2 MUST perform local consistency checks (counts, joins) and fail the partition
                      rather than publishing partial anchors.

RNG events emitted in S2.4–S2.5,
rng_trace_log (Layer-3)
                ->  (S2.8) RNG accounting checks (per-partition, implementation detail but required logically)
                    - Summarise:
                        · total rng_event_flow_shape and rng_event_event_timing and rng_event_amount_draw rows,
                        · per-family (blocks, draws) from envelopes vs expectations derived from domain size
                          (number of sessions, flows, events).
                    - Reconcile with rng_trace_log for this (seed,scenario):
                        · counters monotone, no overlaps between families,
                        · no draws from families not declared for S2,
                        · no over-budget usage.
                    - Record metrics for S5 (validation) via a per-partition run-report entry;
                      S2 MUST NOT emit separate public datasets for these metrics.

Downstream touchpoints
----------------------
- **6B.S3 (fraud & abuse overlay):**
    - Reads:
        · s2_flow_anchor_baseline_6B (flow-level baseline),
        · s2_event_stream_baseline_6B (event-level baseline).
    - Treats:
        · both datasets as the **authoritative all-legit plan** to be overlaid;
          S3 MUST NOT mutate or delete S2 rows in place.

- **6B.S4 (truth & bank-view labels, cases):**
    - Uses:
        · S2 anchors & events as the baseline behaviour against which fraud/abuse and disputes are defined.

- **6B.S5 (segment validation & HashGate):**
    - Validates:
        · structural invariants (keys, ordering, schemas) for both S2 outputs,
        · referential integrity to S1 outputs,
        · RNG accounting for S2’s RNG families (flow_shape, event_timing, amount_draw),
        · that S3/S4 overlays are consistent with S2’s baseline.
```
