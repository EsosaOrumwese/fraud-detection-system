```text
        LAYER 3 · SEGMENT 6B — STATE S1 (ARRIVAL→ENTITY ATTACHMENT & SESSIONISATION)  [RNG-BEARING]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[S0 gate & identity]
    - s0_gate_receipt_6B
      @ data/layer3/6B/gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6B.json
      · provides, for this world:
          - manifest_fingerprint        (world id for Layers 1–3),
          - parameter_hash              (6B parameter pack),
          - run_id                      (6B run identity; S1 outputs MUST NOT depend on it),
          - sealed_inputs_digest_6B     (hash over sealed_inputs_6B),
          - upstream_segments{seg_id → {status,bundle_path,bundle_sha256,flag_path}},
          - contracts_6B{logical_id → {path,sha256_hex,schema_ref,role}},
          - s0_spec_version_6B, created_utc.
      · S1 MUST:
          - resolve and validate this object before doing any work,
          - require all required upstream segments {1A,1B,2A,2B,3A,3B,5A,5B,6A} to have status="PASS",
          - treat it as the sole authority on upstream gate status and 6B contract set.

    - sealed_inputs_6B
      @ data/layer3/6B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet
      · one row per artefact 6B is allowed to read for this world:
          - owner_layer, owner_segment, manifest_key,
          - path_template, partition_keys[], schema_ref,
          - sha256_hex, role, status, read_scope.
      · S1 MUST:
          - recompute sealed_inputs_digest_6B from this table (canonical order/serialisation)
            and require equality with the value embedded in s0_gate_receipt_6B,
          - only consume artefacts recorded here,
          - honour status (REQUIRED/OPTIONAL/IGNORED),
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → only presence/shape checks, no row-level logic.

[Schema+Dict · shape & catalogue authority]
    - schemas.layer3.yaml, schemas.6B.yaml
        · shape authority for:
              - s1_arrival_entities_6B   (S1 primary output),
              - s1_session_index_6B      (S1 secondary output).
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
    - dataset_dictionary.layer2.5B.yaml
        · ID & contract for 5B arrival egress:
              - arrival_events_5B (or the concrete manifest_key used for 5B arrivals)
                · path and partitioning resolved via dictionary + sealed_inputs_6B
                · primary_key includes:
                    [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
                · schema_ref: schemas.5B.yaml#/egress/s4_arrival_events_5B
    - dataset_dictionary.layer3.6A.yaml
        · IDs & contracts for 6A entity bases, links, and fraud roles used by S1:
              - s1_party_base_6A
              - s2_account_base_6A
              - s3_instrument_base_6A
              - s4_device_base_6A
              - s4_ip_base_6A
              - s3_account_instrument_links_6A
              - s4_device_links_6A
              - s4_ip_links_6A
              - s5_party_fraud_roles_6A
              - s5_account_fraud_roles_6A
              - s5_device_fraud_roles_6A
              - s5_ip_fraud_roles_6A
              - s5_merchant_fraud_roles_6A (if marked REQUIRED for S1 in sealed_inputs_6B).

[Upstream arrivals (Layer-2 / 5B)]
    - arrival_events_5B
      · the sealed arrival skeleton:
          - arrival identity:
                seed, manifest_fingerprint, scenario_id,
                merchant_id, arrival_seq,
          - timing:
                ts_utc, primary/local timestamps (as defined by 5B),
          - routing:
                site_id or edge_id, zone / tz context, is_virtual, routing_universe_hash,
          - scenario & grouping fields (scenario_id, channel_group, etc.).
      · S1 MUST:
          - treat these fields as authoritative and immutable,
          - ensure **every** row in arrival_events_5B has exactly one corresponding row
            in s1_arrival_entities_6B with the same identity.

[Upstream entity graph & static posture (Layer-3 / 6A)]
    - Entity bases (REQUIRED, ROW_LEVEL):
        · s1_party_base_6A              (party/party_type/segment/country universe),
        · s2_account_base_6A            (accounts, owners, currencies),
        · s3_instrument_base_6A         (payment instruments, owning accounts/parties),
        · s4_device_base_6A             (devices with static attributes),
        · s4_ip_base_6A                 (IP / network endpoints).
    - Link surfaces (REQUIRED, ROW_LEVEL):
        · s3_account_instrument_links_6A (account↔instrument relationships),
        · s4_device_links_6A             (device↔party/account/instrument/merchant edges),
        · s4_ip_links_6A                 (ip↔device/party/merchant edges).
    - Static fraud posture surfaces (REQUIRED, ROW_LEVEL unless S1 marks them OPTIONAL):
        · s5_party_fraud_roles_6A,
        · s5_account_fraud_roles_6A,
        · s5_device_fraud_roles_6A,
        · s5_ip_fraud_roles_6A,
        · s5_merchant_fraud_roles_6A.
      · S1 MUST:
          - treat these as **read-only ground truth**,
          - NEVER introduce new entity keys not present in these bases,
          - NEVER alter fraud role assignments (may only copy them into S1 outputs as context).

[6B control-plane policies & configuration]
    - Behaviour & attachment policies (resolved via artefact_registry_6B, listed in sealed_inputs_6B):
        · attachment_policy_6B
            - rules for building candidate sets and priors for:
                  party attachment, account selection, instrument choice,
                  device selection, IP selection, merchant posture usage.
        · sessionisation_policy_6B
            - definitions of session key (which fields form a session),
            - inactivity gap thresholds,
            - whether dwell/session boundaries are deterministic or stochastic.
        · behaviour_config_6B (if present)
            - enables/disables features (e.g. whether to attach instrument at S1),
            - scenario filters and guardrails.
    - RNG policies (Layer-3 shared + 6B-specific):
        · rng_profile_layer3.yaml
            - Philox engine parameters and global invariants.
        · rng_policy_6B.yaml
            - mapping from 6B.S1 decision families → rng_stream_id, budgets:
                  rng_event_entity_attach,
                  rng_event_session_boundary (if used),
              plus `blocks`/`draws` contracts and envelope semantics.
      · S1 MUST:
          - use only these configured families for stochastic decisions,
          - respect declared budgets and envelope semantics,
          - emit rng_event_* rows and corresponding rng_trace_log entries as specified
            by the Layer-3 RNG profile.

[Outputs owned by S1]
    - s1_arrival_entities_6B
      @ data/layer3/6B/s1_arrival_entities_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
      · ordering:
            [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq]
      · logical content:
            - arrival identity & routing: ALL 5B fields MUST be preserved unmodified,
            - entity attachments:
                  party_id, account_id, instrument_id?,
                  device_id, ip_id,
                  any local flags (e.g. attachment_source, attachment_confidence),
            - session_id (assigned by S1),
            - optional derived context copied from 6A (e.g. posture snippets, segments).

    - s1_session_index_6B
      @ data/layer3/6B/s1_session_index_6B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet
      · partitioning: [seed, fingerprint, scenario_id]
      · primary_key:
            [seed, manifest_fingerprint, scenario_id, session_id]
      · ordering:
            [seed, manifest_fingerprint, scenario_id, session_id]
      · logical content:
            - session_id,
            - session_key fields (e.g. party_id, device_id, merchant_id, channel_group, scenario_id),
            - `session_start_utc`, `session_end_utc`,
            - `arrival_count`, session duration & basic gap metrics,
            - dominant static context (e.g. majority posture flags, zone, country).

DAG — 6B.S1 (sealed arrivals + entity graph → attached arrivals & sessions)  [RNG-BEARING]
-------------------------------------------------------------------------------------------

[S0 gate & identity],
[Schema+Dict]
                ->  (S1.1) Verify S0 gate & load 6B input universe  (RNG-free)
                    - Resolve:
                        · s0_gate_receipt_6B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_6B@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer3.6B.yaml.
                    - Validate both against schemas.layer3.yaml and schemas.6B.yaml.
                    - Recompute sealed_inputs_digest_6B from sealed_inputs_6B (canonical row order + serialisation);
                      require equality with the value embedded in s0_gate_receipt_6B.
                    - Check `upstream_segments` in s0_gate_receipt_6B:
                        · all required segments {1A,1B,2A,2B,3A,3B,5A,5B,6A} MUST have status="PASS".
                    - If any condition fails:
                        · S1 MUST fail and MUST NOT emit s1_arrival_entities_6B or s1_session_index_6B.

sealed_inputs_6B,
dataset_dictionary.layer2.5B.yaml,
dataset_dictionary.layer3.6A.yaml,
artefact_registry_{5B,6A,6B}
                ->  (S1.2) Discover partitions & required upstream artefacts  (RNG-free)
                    - From sealed_inputs_6B, extract rows with:
                        · status      = "REQUIRED",
                        · read_scope  = "ROW_LEVEL",
                        · owner_segment ∈ {"5B","6A"} and roles in:
                              {"arrival_stream", "entity_base", "entity_links", "fraud_posture"}.
                    - For 5B arrivals:
                        · resolve path_template & partition_keys for arrival_events_5B via dictionary,
                        · enumerate all (seed, scenario_id) partitions present for this manifest_fingerprint.
                    - For 6A bases/posture:
                        · confirm that required 6A datasets exist for (seed, manifest_fingerprint),
                        · resolve their concrete paths via path_template and partition_keys.
                    - Optionally apply 6B behaviour_config_6B filters to restrict which (seed, scenario_id)
                      combinations S1 will process.
                    - S1 MAY treat each (seed, scenario_id) partition independently; there must be no
                      cross-partition state.

6A bases & links,
6A posture surfaces
                ->  (S1.3) Load entity graph & build attachment indices  (RNG-free, per (seed,manifest_fingerprint))
                    - For the current (seed, manifest_fingerprint):
                        · load s1_party_base_6A, s2_account_base_6A, s3_instrument_base_6A,
                          s4_device_base_6A, s4_ip_base_6A,
                          s3_account_instrument_links_6A,
                          s4_device_links_6A, s4_ip_links_6A,
                          and required s5_*_fraud_roles_6A.
                    - Validate:
                        · foreign-keys between bases and link tables,
                        · no duplicate keys in bases,
                        · fraud-role tables cover only known entity keys.
                    - Build in-memory indices to support attachment:
                        · account_index_by_party,
                        · instrument_index_by_account (and by party or merchant as needed),
                        · device_index_by_party / by merchant / by instrument (depending on policy),
                        · ip_index_by_device / by party / by merchant,
                        · per-entity fraud posture lookup.

attachment_policy_6B,
behaviour_config_6B,
arrival_events_5B (schema & partitions),
entity indices from S1.3
                ->  (S1.4) Build candidate sets & attachment priors per arrival  (RNG-free)
                    - For each (seed, scenario_id) and for each arrival row r in arrival_events_5B:
                        · derive a **session key base** and attachment context from arrival fields:
                              merchant_id, zone / tz, channel_group, is_virtual, scenario_id,
                              routing context, and timestamp.
                        · Using attachment_policy_6B and entity indices, derive:
                              candidate_parties(r),
                              candidate_accounts(r),
                              candidate_instruments(r) (if enabled),
                              candidate_devices(r),
                              candidate_ips(r),
                          ensuring all candidates are valid 6A entities and consistent with link tables.
                        - For each dimension d ∈ {party,account,instrument,device,ip}:
                              - if |candidates_d(r)| == 0:
                                    · treat as configuration/coverage error; S1 MUST fail or apply the
                                      configured fallback path (if explicitly defined).
                              - if |candidates_d(r)| == 1:
                                    · mark attachment for d as **deterministic** (no RNG needed).
                              - if |candidates_d(r)| > 1:
                                    · construct a prior weight vector w_d(r) over candidates based on policy
                                      (e.g. proximity, posture, historical affinity),
                                    · mark attachment for d as **stochastic**; S1.5 will sample from w_d(r).

rng_policy_6B,
rng_profile_layer3.yaml,
stochastic attachment marks from S1.4
                ->  (S1.5) Sample entity attachments (RNG-bearing)
                    - For each arrival r and each entity dimension d marked as stochastic:
                        1. Determine RNG family and key:
                               · use rng_event_entity_attach with a key derived from:
                                     (manifest_fingerprint, seed, scenario_id, merchant_id, arrival_seq, dimension_d)
                               · obtain rng_stream_id and budget (blocks, draws) from rng_policy_6B.
                        2. Draw uniforms:
                               · consume the required number of Philox uniforms for this decision
                                 (e.g. one per dimension), updating rng_trace_log envelopes.
                        3. Map uniforms to candidate indices using the prior weights w_d(r).
                        4. Fix the chosen candidate entity for dimension d and record provenance:
                               · chosen_entity_id_d,
                               · candidate_list_digest_d,
                               · prior_config_id_d,
                               · rng_event_id_d, rng_stream_id, envelope (blocks,draws,counter_before/after).
                    - For deterministic dimensions, S1 MUST NOT consume RNG; it MUST record attachment decisions
                      with deterministic=true semantics (no rng_event_* rows for that dimension).

arrival_events_5B,
final entity attachments from S1.4–S1.5,
sessionisation_policy_6B
                ->  (S1.6) Build sessions & assign session_ids  (RNG-free with optional RNG for boundaries)
                    - For each (seed, scenario_id):
                        1. Join arrival_events_5B with entity attachments to form a working view:
                               · key: (merchant_id, arrival_seq),
                               · context: ts_utc, party_id, device_id, ip_id, merchant_id, channel_group, scenario_id.
                        2. Define a **session key** K(r) per arrival r according to sessionisation_policy_6B,
                           e.g. K(r) = (party_id, device_id, merchant_id, channel_group, scenario_id).
                        3. For each session key K:
                               · sort its arrivals by ts_utc ascending,
                               · walk the sorted list and split into segments when:
                                     - the gap between consecutive arrivals exceeds a configured threshold, and/or
                                     - policy requires a new session after a maximum duration or count.
                               · if the policy allows *stochastic* boundaries:
                                     - for each candidate boundary, use rng_event_session_boundary with a key
                                       derived from (manifest_fingerprint, seed, scenario_id, K, gap_index)
                                       to decide whether to split; update rng_trace_log accordingly.
                        4. For each resulting session segment:
                               · assign a unique session_id within (seed, manifest_fingerprint, scenario_id),
                                 using a deterministic scheme (e.g. monotone counter or hash64 of
                                 (manifest_fingerprint, seed, scenario_id, K, local_session_index)).
                        5. Compute session aggregates:
                               · session_start_utc = min(ts_utc) in session,
                               · session_end_utc   = max(ts_utc) in session,
                               · arrival_count,
                               · derived metrics required by the schema (duration, mean_gap, etc.).
                    - Invariants:
                        · every arrival in s1_arrival_entities_6B MUST belong to exactly one session_id,
                        · there MUST be no duplicate (seed, manifest_fingerprint, scenario_id, session_id) keys
                          in s1_session_index_6B.

entity attachments & session assignments,
schemas.6B.yaml#/s1/arrival_entities_6B,
schemas.6B.yaml#/s1/session_index_6B
                ->  (S1.7) Materialise s1_arrival_entities_6B & s1_session_index_6B  (RNG-free)
                    - Construct s1_arrival_entities_6B rows:
                        · copy all arrival_events_5B identity & routing fields unchanged,
                        · add:
                              party_id, account_id, instrument_id?,
                              device_id, ip_id,
                              session_id,
                              any configured context/posture fields.
                        · enforce:
                              primary_key:
                                  [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq],
                              ordering:
                                  [seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq].
                    - Construct s1_session_index_6B rows:
                        · one row per session_id with:
                              session_id,
                              session_key fields,
                              session_start_utc, session_end_utc,
                              arrival_count, duration, basic gap metrics,
                              any configured dominant-context fields.
                        · enforce:
                              primary_key:
                                  [seed, manifest_fingerprint, scenario_id, session_id],
                              ordering:
                                  [seed, manifest_fingerprint, scenario_id, session_id].
                    - Write both datasets to the paths specified in dataset_dictionary.layer3.6B.yaml,
                      using atomic write patterns (staging → fsync → move).
                    - Validate against schemas.6B.yaml anchors and check PK uniqueness.
                    - If any validation or invariant fails:
                        · S1 MUST fail for that (seed, scenario_id) partition and MUST NOT publish partial outputs.

Downstream touchpoints
----------------------
- **6B.S2 (baseline flows & events):**
    - Reads:
        · s1_arrival_entities_6B (arrival→entity context + session_id),
        · s1_session_index_6B (session-level anchors).
    - Treats:
        · arrivals and entity attachments as **authoritative**; S2 must not reattach or alter 5B identity.

- **6B.S3 (fraud & abuse overlay):**
    - Uses:
        · sessions and entity attachments to construct targeting domains and campaign contexts.

- **6B.S4 (truth/bank labels & cases):**
    - Uses:
        · session_id and entity context as part of its feature space and case grouping logic.

- **6B.S5 (segment validation & HashGate):**
    - Validates:
        · coverage of arrival_events_5B by s1_arrival_entities_6B,
        · structural and PK/ordering invariants for both S1 outputs,
        · RNG accounting for rng_event_entity_attach and rng_event_session_boundary families.
```
