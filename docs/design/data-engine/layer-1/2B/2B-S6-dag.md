```
        LAYER 1 · SEGMENT 2B — STATE S6 (VIRTUAL-MERCHANT EDGE ROUTING)  [RNG-BOUNDED]

Authoritative inputs (read-only at S6 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2B @ data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: 2B.S0 ran for this manifest_fingerprint and verified upstream 1B PASS
      · binds: { seed, manifest_fingerprint, parameter_hash } for this edge-routing run
      · provides: canonical created_utc = verified_at_utc (echoed into s6_edge_log if enabled)
    - sealed_inputs_v1 @ data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/…
      · sealed inventory of cross-layer/policy artefacts S0 authorised
      · S6 MUST treat any cross-layer/policy read as a subset of this inventory (subset-of-S0 rule)

[Schema+Dict]
    - schemas.layer1.yaml                 (RNG envelope, rng_event.cdn_edge_pick, rng_audit_log, rng_trace_log)
    - schemas.2B.yaml                     (policy/virtual_edge_policy_v1, route_rng_policy_v1, trace/s6_edge_log_row)
    - dataset_dictionary.layer1.2B.yaml   (ID→path/partitions for 2B assets incl. s6_edge_log)
    - dataset_dictionary.layer1.2A.yaml   (ID→path/partitions for 2A assets; used only if consulted for echo)
    - artefact_registry_2B.yaml           (ownership/licence/retention; non-authoritative for shape/paths)

[Token-less policies (S0-sealed; no partitions)]
    - route_rng_policy_v1
        · declares routing_edge stream/substream for virtual edges
        · binds rng_event.cdn_edge_pick budgets: blocks=1, draws="1" per event
        · defines mapping from {seed, parameter_hash, run_id} → Philox key/initial counters
    - virtual_edge_policy_v1
        · sealed virtual-edge catalogue:
            edges: array of rows with fields:
              - edge_id (string, non-empty)
              - ip_country (ISO2)
              - edge_lat ∈ [−90,90]
              - edge_lon ∈ (−180,180]
              - either:
                  · weight > 0 (single global weight), or
                  · country_weights{iso2→non-negative} (per-country weights)
        · defines canonical edge ordering and per-merchant edge distributions

[Context (optional, integrity echo only; no decode in v1)]
    - s2_alias_index @ seed={seed} / fingerprint={manifest_fingerprint}
    - s2_alias_blob  @ seed={seed} / fingerprint={manifest_fingerprint}
        · MAY be read to confirm path↔embed/digest, but S6 MUST NOT decode alias tables or scan the blob

[Runtime inputs (from S5 router; not catalogue assets)]
    - Per-arrival decision records (in-memory or stream), each with:
        · merchant_id = m
        · utc_timestamp = t
        · utc_day = d (UTC date)
        · tz_group_id (tzid chosen by S5)
        · site_id (physical site chosen by S5)
        · is_virtual ∈ {0,1}
    - These carry run lineage {seed, parameter_hash, run_id}; they are **not** datasets in the catalogue.

[Output surfaces owned by S6 (run-scoped only)]
    - RNG core logs & envelope (run-scoped):
        · rng_audit_log   @ logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl
        · rng_trace_log   @ logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl
        · rng_event.cdn_edge_pick events @ logs/rng/events/2B/cdn_edge_pick/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…
          - exactly one event per **virtual** arrival, envelope {blocks=1, draws="1"}
    - Optional diagnostic dataset (policy-gated):
        - s6_edge_log @ logs/edge/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={utc_day}/s6_edge_log.jsonl
          · partitions: [seed, parameter_hash, run_id, utc_day]
          · row shape: schemas.2B.yaml#/trace/s6_edge_log_row
              { merchant_id, is_virtual, utc_timestamp, utc_day, tz_group_id,
                site_id, edge_id, ip_country, edge_lat, edge_lon,
                rng_stream_id, ctr_edge_hi, ctr_edge_lo,
                manifest_fingerprint, created_utc }

[Numeric & RNG posture]
    - Numeric:
        · IEEE-754 binary64; round-to-nearest-even
        · deterministic alias builder (Walker/Vose) over binary64 probabilities
        · stable serial operations; no data-dependent sum reorderings
    - RNG:
        · Philox-based engine from route_rng_policy_v1 (routing_edge stream)
        · exactly **one** single-uniform event per **virtual** arrival:
              rng_event.cdn_edge_pick with blocks=1, draws="1"
        · uniforms u ∈ (0,1), mapped from counters by the layer law; counters strictly increasing, no wrap
    - Catalogue discipline:
        · all reads resolved by Dictionary ID; no literal paths; no network I/O
        · cross-layer/policy inputs MUST appear in sealed_inputs_v1 for this fingerprint
    - Authority boundaries:
        · S6 SHALL NOT read or mutate fingerprint-scoped plan/egress surfaces (s4_group_weights, s1_site_weights, site_locations, etc.)
        · S6 SHALL NOT decode or derive anything from s2_alias_blob (context-only; S2 remains alias authority)


----------------------------------------------------------------------
DAG — 2B.S6 (Virtual-merchant edge routing branch)  [RNG-BOUNDED]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S6.1) Verify S0 evidence & fix run identity
                    - Resolve s0_gate_receipt_2B and sealed_inputs_v1 for manifest_fingerprint via Dictionary.
                    - Validate both against their schema anchors; abort on any shape or fingerprint mismatch.
                    - Fix run identity for S6:
                        · plan identity:   {seed, manifest_fingerprint} (used only for echo in logs)
                        · run identity:    {seed, parameter_hash, run_id} (RNG logs/events, s6_edge_log partitions)
                    - Derive created_utc_S0 ← s0_gate_receipt_2B.verified_at_utc;
                      S6 SHALL echo this into s6_edge_log.created_utc if diagnostics are enabled.
                    - Confirm S6 posture:
                        · branch-only state; it never touches fingerprint-scoped plan/egress surfaces,
                        · RNG-bounded: at most one draw per **virtual** arrival; zero for non-virtual.

[S6.1],
[Schema+Dict],
route_rng_policy_v1,
virtual_edge_policy_v1,
s2_alias_index?,
s2_alias_blob?
                ->  (S6.2) Resolve policies, enforce S0-evidence rule & pre-flight checks
                    - Resolve via Dictionary (no literals):
                        · route_rng_policy_v1
                        · virtual_edge_policy_v1
                        · optionally s2_alias_index / s2_alias_blob @ seed={seed}/fingerprint={manifest_fingerprint}
                          (if S0 sealed them; integrity echo only).
                    - S0-evidence rule:
                        · route_rng_policy_v1 and virtual_edge_policy_v1 MUST appear in sealed_inputs_v1 for this fingerprint.
                        · any context artefacts S6 reads (e.g. S2 alias surfaces) MUST also appear in sealed_inputs_v1.
                    - Validate virtual_edge_policy_v1:
                        · policy_id == "virtual_edge_policy_v1",
                        · edges[] non-empty; each edge row:
                              - edge_id string non-empty,
                              - ip_country is valid ISO2,
                              - edge_lat ∈ [−90,90],
                              - edge_lon ∈ (−180,180],
                              - exactly one of weight>0 or country_weights{iso2→≥0} present.
                    - If s2_alias_index/blob are consulted:
                        · confirm partition tokens [seed,fingerprint] and path↔embed equality
                          wherever identities are embedded; S6 SHALL NOT decode alias tables.
                    - From route_rng_policy_v1:
                        · obtain the Philox configuration for routing_edge:
                              - rng_stream_id (string),
                              - mapping from {seed, parameter_hash, run_id} → key / base_counter,
                              - affirmation that each cdn_edge_pick event has blocks=1, draws="1".
                    - Configure RNG:
                        · derive routing_edge stream (Philox key) from {seed, parameter_hash, run_id, rng_stream_id},
                        · initialise a 128-bit base_counter for this run; counters increment by +1 per event.

                ->  (S6.3) Build per-merchant edge distributions & alias caches (RNG-free)
                    - From virtual_edge_policy_v1.edges, derive per-merchant edge distributions:
                        · For each virtual merchant m:
                            - collect the list of edges associated with m in **canonical edge order** defined by policy
                              (the spec defines how the policy encodes merchant→edge mapping; S6 follows it exactly).
                            - construct non-negative weights over those edges:
                                  - if per-edge weight is present: use it,
                                  - if country_weights is present: aggregate to a single weight per edge according
                                    to policy’s deterministic law (no RNG).
                        - For each merchant m, normalise weights to probabilities p_edge[m][k] over k∈{0..K_m−1}:
                            - Σ_k p_edge[m][k] = 1 within policy ε; abort if violated.
                    - Define ephemeral cache:
                        · EDGE_ALIAS[m] : optional (prob[], alias[]) alias structure over that merchant’s edges.
                        · Initially empty for all m; S6 SHALL build entries lazily (on first use), RNG-free.
                        · Cache presence/eviction MUST NOT affect outcomes (same arrivals → same edges).

----------------------------------------------------------------------
Per-arrival procedure (from S5) — (m, t, d, tz_group_id, site_id, is_virtual)
-----------------------------------------------------------------------------

[A] Bypass non-virtual arrivals (no RNG, no logs)
-------------------------------------------------

arrival (m, t, d, tz_group_id, site_id, is_virtual)
                ->  (S6.A1) Virtuality check
                    - If is_virtual == 0:
                        · do **not** draw any RNG,
                        · do **not** write any S6 logs/events (rng_event.cdn_edge_pick or s6_edge_log),
                        · return immediately; the arrival remains fully governed by S5’s site choice.
                    - If is_virtual == 1:
                        · proceed to virtual edge pick (S6.B).

[B] Virtual edge pick (exactly one draw per virtual arrival)
-----------------------------------------------------------

(virtual_edge_policy_v1, EDGE_ALIAS cache),
merchant_id = m
                ->  (S6.B1) Ensure merchant-level edge alias exists (RNG-free)
                    - If EDGE_ALIAS[m] is missing:
                        · retrieve the canonical ordered edge list for merchant m from virtual_edge_policy_v1,
                        · take the precomputed normalised probabilities p_edge[m][k] over edges k=0..K_m−1,
                        · build alias arrays (prob_edge[], alias_edge[]) using the deterministic Walker/Vose builder:
                              - all operations in binary64,
                              - stable serial reductions; deterministic tie-break by edge order.
                        · store the result in EDGE_ALIAS[m].
                    - If there is no configured edge distribution for merchant m (i.e. merchant not present in policy):
                        · behaviour is defined by the policy (e.g., abort with NO_VIRTUAL_EDGES_FOR_MERCHANT).

(routing_edge stream from route_rng_policy_v1),
EDGE_ALIAS[m]
                ->  (S6.B2) Draw uniform & decode edge_id (RNG-consuming)
                    - Emit one rng_event.cdn_edge_pick:
                        · before: record current 128-bit counter (ctr_before),
                        · generate a 64-bit random integer, map to uniform u ∈ (0,1) via the layer law,
                        · after: counter_after = ctr_before + 1; record in envelope,
                        · envelope: {blocks=1, draws="1"}.
                    - Decode via alias:
                        · let K = number of edges for merchant m,
                        · j = floor(u * K),
                        · r = u * K − j,
                        · if r < prob_edge[j] → pick logical index k = j,
                          else               → pick logical index k = alias_edge[j].
                    - Map k back to a concrete edge_id via the canonical edge order for merchant m.
                    - Exactly one draw, one event per virtual arrival; no hidden draws in alias build or lookup.

(virtual_edge_policy_v1, edge_id)
                ->  (S6.B3) Attach edge attributes (RNG-free)
                    - Lookup edge_id in virtual_edge_policy_v1.edges (exact match, no fuzzy search).
                    - Extract:
                        · ip_country (ISO2),
                        · edge_lat ∈ [−90,90],
                        · edge_lon ∈ (−180,180].
                    - Abort if edge_id is missing or attributes fail domain checks.
                    - These attributes are deterministic given edge_id and the sealed policy.

[C] RNG logs & optional s6_edge_log (run-scoped evidence)
---------------------------------------------------------

(rng_event.cdn_edge_pick for this arrival),
rng_audit_log,
rng_trace_log
                ->  (S6.C1) Append RNG events & update core logs
                    - Append exactly one rng_event.cdn_edge_pick row for this virtual arrival:
                        · includes rng_stream_id, ctr_edge_hi/ctr_edge_lo before/after,
                          blocks=1, draws="1", and any required context fields.
                    - After appending the event:
                        · update rng_trace_log once with cumulative RNG totals
                          (events_seen, draws_seen, blocks_seen, counters_hi/lo).
                    - rng_audit_log tracks per-family summaries; S6 contributes counts to the cdn_edge_pick family.

(s6_edge_log enabled?),
arrival (m,t,d,tz_group_id,site_id,is_virtual),
edge_id, ip_country, edge_lat, edge_lon,
rng_stream_id, ctr_edge_hi, ctr_edge_lo,
created_utc_S0, manifest_fingerprint
                ->  (S6.C2) Append optional s6_edge_log row (if diagnostics enabled)
                    - If diagnostics are disabled by policy or s6_edge_log is not registered:
                        · skip this step entirely; no diagnostic dataset is written.
                    - If enabled:
                        · derive utc_day = d (already supplied from S5),
                        · construct a JSON object with fields:
                              merchant_id        = m
                              is_virtual         = true
                              utc_timestamp      = t (rfc3339_micros)
                              utc_day            = d (YYYY-MM-DD)
                              tz_group_id        = tz_group_id (from S5)
                              site_id            = site_id (from S5)
                              edge_id            = edge_id (from S6.B2)
                              ip_country         = ip_country
                              edge_lat           = edge_lat
                              edge_lon           = edge_lon
                              rng_stream_id      = routing_edge stream id
                              ctr_edge_hi        = high 64 bits of counter_after
                              ctr_edge_lo        = low  64 bits of counter_after
                              manifest_fingerprint = this run’s manifest_fingerprint
                              created_utc        = created_utc_S0
                        · resolve s6_edge_log path via Dictionary:
                              logs/edge/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={utc_day}/s6_edge_log.jsonl
                        · append the JSON row to the appropriate partition file (jsonl):
                              - writer order MUST equal arrival order within each partition,
                              - partitions: [seed, parameter_hash, run_id, utc_day].
                        - Immutability:
                              - per-partition files are write-once; if re-emitted, bytes MUST be identical
                                (otherwise a new run_id must be used).

------------------------------------------------
Determinism, boundaries & downstream touchpoints
------------------------------------------------
- Determinism & RNG bounds:
    - Non-virtual arrivals: 0 draws, no S6 events/logs.
    - Virtual arrivals: exactly 1 rng_event.cdn_edge_pick with {blocks=1, draws="1"} and one trace increment.
    - Alias build over edges is deterministic, RNG-free, and cache presence/eviction MUST NOT affect choices.
- Authority boundaries:
    - S6 never re-routes physical merchants; it only adds a virtual edge_id + attributes for is_virtual=1 arrivals.
    - S6 never writes or mutates fingerprint-scoped plan/egress datasets; 2B plan authority remains with S1–S4.
    - Edge distributions come only from virtual_edge_policy_v1; S6 MUST NOT infer edges from runtime behaviour or other tables.
    - S6 MAY NOT decode or scan s2_alias_blob; alias authority for site routing remains with 2B.S2.
- Downstream touchpoints:
    - 2B.S7 (audit) uses:
        · s6_edge_log (if present), rng_event.cdn_edge_pick, rng_trace_log, and virtual_edge_policy_v1
          to confirm one-draw-per-virtual-arrival, correct edge_id domain, and attribute semantics.
    - 2B.S8 (validation bundle) includes S7’s audit and relevant RNG evidence in the fingerprint-scoped validation_bundle_2B.
    - Later layers (e.g. Layer-2/Layer-3 flows) may treat edge_id/ip_country/edge_lat/edge_lon as part of the routing context,
      but MUST honour the 2B-wide “No PASS → No read” gate via `_passed.flag` before trusting any routing surfaces.
```