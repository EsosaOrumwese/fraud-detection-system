```
                     LAYER 1 - SEGMENT 2B (site_locations → routing plan & router behaviour)

Authoritative inputs (sealed in S0)
-----------------------------------
[M] Upstream 1B egress & gate:
    - validation_bundle_1B              @ [fingerprint]
    - validation_passed_flag_1B         @ [fingerprint]  (_passed.flag_1B; HashGate for 1B)
      · bundle index schema: schemas.1A.yaml#/validation/validation_bundle.index_schema
      · flag schema: schemas.1B.yaml#/validation/passed_flag       
    - site_locations                    @ [seed, fingerprint]
      · final per-site geometry from 1B (lon_deg, lat_deg)
      · PK: (merchant_id, legal_country_iso, site_order); order-free; write-once          

[O] Optional pins from 2A (all-or-none; read-only):
    - site_timezones                    @ [seed, fingerprint]
      · per-site IANA tzid (tz_group_id) from 2A; PK aligned with site_locations         
    - tz_timetable_cache                @ [fingerprint]
      · fingerprint-scoped tz transition cache; used for tz-group coherence only         

[P] Policy packs captured by S0:
    - route_rng_policy_v1               (Philox sub-stream layout & budgets for routing states) 
    - alias_layout_policy_v1            (alias table byte layout, endianness, alignment, bit-depth b)
    - day_effect_policy_v1              (daily γ variance, day range, RNG stream for S3)
    - virtual_edge_policy_v1            (virtual edges catalogue: edge_id, weights/country_weights, attributes) 

[N] Numeric, RNG & identity posture:
    - numeric_policy.json, math_profile_manifest.json
      · IEEE-754 binary64; round-to-nearest-even; FMA-off; deterministic libm on decision paths
    - RNG envelope (Layer-1 law):
      · counter-based Philox; open-interval uniforms; per-event envelope `{blocks, draws}`; rng_trace_log updated once
        after each event append (S3/S5/S6 only; other states are RNG-free).        
    - Identity & gate law:
      · manifest_fingerprint from S0 sealed inputs; path↔embed equality for `{seed, manifest_fingerprint}`
      · partitions write-once; stage → fsync → single atomic move; file order non-authoritative
      · **No PASS → No read**: 1B HashGate for site_locations; 2B HashGate (S8) for all 2B plan surfaces


DAG
---
(M,O,P,N) --> (S0) Gate, identity & sealed inputs  [NO RNG]
                    - Verify 1B’s fingerprint gate for this manifest_fingerprint:
                        * open validation_bundle_1B/ @ [fingerprint]
                        * read index.json (relative paths; ASCII-lex order; one entry per non-flag file)
                        * recompute SHA-256 over raw bytes in ASCII-lex path order (flag excluded)
                        * compare to _passed.flag_1B (`sha256_hex = <hex64>`)
                        * **No PASS → No read** of site_locations for 2B
                    - Resolve & seal minimum input set for this {seed, fingerprint} via Dictionary (no literals):
                        * site_locations                        @ [seed, fingerprint]
                        * route_rng_policy_v1, alias_layout_policy_v1, day_effect_policy_v1 (token-less)
                        * optional pins: site_timezones, tz_timetable_cache (if both present)
                    - Bind 2B run identity:
                        * {seed, manifest_fingerprint} for plan surfaces
                        * parameter_hash carried for run-scoped RNG logs (S5/S6)
                    - Emit fingerprint-scoped proof artefacts:
                        * s0_gate_receipt_2B      @ [fingerprint]   (gate receipt: identity, catalogue_resolution)
                        * sealed_inputs_v1        @ [fingerprint]   (inventory of sealed assets: IDs, paths, partitions, sha256) 
                    - S0 is RNG-free; it gates & seals; it does not read 2B plan rows or decode alias/tzdb

                                      |
                                      | s0_gate_receipt_2B, sealed_inputs_v1 (gate & sealed inputs)
                                      v

             (S1) Per-merchant weight freezing — static site law      [NO RNG]
                inputs: site_locations @ [seed, fingerprint],
                        alias_layout_policy_v1 (floor/cap, ε/ε_q, bit-depth b),
                        optional pins site_timezones/tz_timetable_cache (coherence only)   
                -> s1_site_weights      @ [seed, fingerprint]
                     - PK/sort: (merchant_id, legal_country_iso, site_order)
                     - For each merchant:
                         · derive policy-declared base weights w_i from site_locations (RNG-free transform),
                         · apply floors/caps & zero-mass fallback deterministically,
                         · normalise to p_i with Σ_i p_i = 1 (within ε),
                         · quantise to grid of size G = 2^b with deterministic Δ-adjust (Σ m_i = G),
                         · p_weight = p_i (real), quantised_bits = b, floor_applied flags per row.
                     - Only source of truth for per-site probabilities; S2–S6 MUST NOT recompute from site_locations

                                      |
                                      | s1_site_weights
                                      v

             (S2) Alias tables — O(1) sampler build                   [NO RNG]
                inputs: s1_site_weights @ [seed, fingerprint],
                        alias_layout_policy_v1 (layout_version, endianness, alignment_bytes, bit-depth b) 
                -> s2_alias_index      @ [seed, fingerprint]
                -> s2_alias_blob       @ [seed, fingerprint]
                     - For each merchant:
                         · reconstruct integer masses m_i = round_even(p_weight·2^b) + deterministic Δ-adjust (Σ m_i = 2^b),
                         · build per-merchant alias tables (prob[], alias[]) using policy encode law (Walker/Vose style),
                         · serialise slices into alias.bin with policy-declared layout & alignment,
                         · write index.json with one row per merchant {merchant_id, offset, length, sites, quantised_bits, checksum}.
                     - Header echoes policy: layout_version, endianness, alignment_bytes, quantised_bits, policy_id, policy_digest, blob_sha256
                     - Index+blob are the only alias authority; RNG-free; plan partitions are [seed, fingerprint]

                                      |
                                      | s1_site_weights, site_timezones (tzid per site)
                                      v

             (S3) Corporate-day modulation — γ(d, tz_group) draws     [RNG-BOUNDED]
                inputs: s1_site_weights @ [seed, fingerprint],
                        site_timezones  @ [seed, fingerprint],
                        day_effect_policy_v1 (day range, sigma_gamma, RNG stream for S3)   
                -> s3_day_effects       @ [seed, fingerprint]
                     - Define tz-group universe per merchant by joining S1 keys to site_timezones (tz_group_id = tzid)
                     - Define day grid D from policy start_day..end_day (UTC dates)
                     - For every (merchant_id, utc_day ∈ D, tz_group_id):
                         · draw one Philox uniform u ∈ (0,1) on S3’s rng_stream_id (counter-based),
                         · map u to standard normal Z via deterministic ICDF,
                         · log_gamma = μ + σ·Z, γ = exp(log_gamma) with μ = −½σ² so E[γ]=1,
                         · record {gamma, log_gamma, sigma_gamma, rng_stream_id, rng_counter_lo, rng_counter_hi, created_utc}
                     - S3 is RNG-bounded: exactly one draw per row; outputs partitioned [seed, fingerprint]

                                      |
                                      | s1_site_weights, site_timezones, s3_day_effects
                                      v

             (S4) Zone-group renormalisation — day-specific group mixes  [NO RNG]
                inputs: s1_site_weights   @ [seed, fingerprint],
                        site_timezones    @ [seed, fingerprint],
                        s3_day_effects    @ [seed, fingerprint]                                      
                -> s4_group_weights       @ [seed, fingerprint]
                     - Base shares (RNG-free):
                         · join S1 to site_timezones on site keys,
                         · per merchant, per tz_group_id (tzid) compute base_share = Σ_site p_weight,
                           with Σ_group base_share ≈ 1 (within ε).
                     - Combine with S3 γ:
                         · for each {merchant, utc_day, tz_group_id} in S3 grid,
                             mass_raw = base_share · gamma(d, group),
                         · per {merchant, utc_day} renormalise across groups:
                             p_group = mass_raw / Σ_group mass_raw, with Σ_group p_group ≈ 1.
                     - Output: per {merchant_id, utc_day, tz_group_id}:
                         {p_group, base_share, gamma, created_utc}; PK/sort [merchant_id, utc_day, tz_group_id].
                     - s4_group_weights is the sole authority for per-day tz-group routing probabilities

                                      |
                                      | s4_group_weights, s2_alias_index/blob, s1_site_weights, site_timezones
                                      v

             (S5) Router core — two-stage O(1): group → site (runtime)  [RNG-BOUNDED]
                inputs: s4_group_weights  @ [seed, fingerprint],
                        s2_alias_index/blob @ [seed, fingerprint],
                        s1_site_weights    @ [seed, fingerprint],
                        site_timezones     @ [seed, fingerprint],
                        route_rng_policy_v1, alias_layout_policy_v1                        
                -> rng_event.alias_pick_group / alias_pick_site   @ [seed, parameter_hash, run_id]    (core logs)
                -> rng_audit_log, rng_trace_log                   @ [seed, parameter_hash, run_id]
                -> (optional) s5_selection_log                    @ [seed, parameter_hash, run_id, utc_day]
                     - For each arrival (merchant_id m, UTC timestamp t):
                         · Stage A (group pick): use s4_group_weights(m, day(t), ·) to build/reuse alias over tz_group_id,
                           draw 1 uniform on alias_pick_group → choose tz_group_id.
                         · Stage B (site pick): within chosen group, derive site-level masses from s1_site_weights+site_timezones,
                           build/reuse per-group alias, draw 1 uniform on alias_pick_site → choose site_id.
                         · Log RNG envelopes (blocks=1, draws="1") and update rng_trace_log after each event.
                         · Optionally append per-arrival row to s5_selection_log with {m, t, tz_group_id, site_id, counters, fingerprint, created_utc}.
                     - S5 is RNG-bounded: exactly 2 single-uniform events per routed arrival; it writes logs only (no plan/egress tables)

                                      |
                                      | virtual merchants only (is_virtual=1)
                                      v

             (S6) Virtual-merchant edge routing (branch)              [RNG-BOUNDED]
                inputs: route_rng_policy_v1 (routing_edge stream),
                        virtual_edge_policy_v1 (edge catalogue, weights/attrs),
                        (context) s2_alias_index/blob, plan surfaces (read-only)                         
                -> rng_event.cdn_edge_pick    @ [seed, parameter_hash, run_id]
                -> (optional) s6_edge_log     @ [seed, parameter_hash, run_id, utc_day]
                     - For non-virtual arrivals (is_virtual=0):
                         · S6 performs no draw, writes no records (bypass).
                     - For virtual arrivals:
                         · build/reuse per-merchant edge alias from virtual_edge_policy_v1 (RNG-free),
                         · draw 1 uniform on routing_edge stream (cdn_edge_pick family) → choose edge_id,
                         · look up edge attributes {ip_country, edge_lat, edge_lon} from sealed policy,
                         · log RNG envelope & append one rng_trace_log row,
                         · optionally append s6_edge_log row with {m, t, tz_group_id, site_id, edge_id, ip_country,
                           edge_lat, edge_lon, counters, fingerprint, created_utc}.
                     - S6 is RNG-bounded: exactly 1 single-uniform cdn_edge_pick per virtual arrival

                                      |
                                      | S2/S3/S4 plan surfaces; optional S5/S6 logs + RNG logs
                                      v

             (S7) Audits & CI gate — per-seed audit report            [NO RNG]
                inputs: s0_gate_receipt_2B, sealed_inputs_v1        @ [fingerprint],
                        s2_alias_index/s2_alias_blob                @ [seed, fingerprint],
                        s3_day_effects, s4_group_weights            @ [seed, fingerprint],
                        alias_layout_policy_v1, route_rng_policy_v1, virtual_edge_policy_v1,
                        optional s5_selection_log, s6_edge_log, rng_audit_log, rng_trace_log     
                -> s7_audit_report          @ [seed, fingerprint]
                     - Alias mechanics:
                         · check index/blob schema, header↔blob parity, layout echo vs alias_layout_policy_v1,
                         · non-overlapping, aligned slices; sampled decode round-trip Σ p̂ = 1; record alias_decode_max_abs_delta.
                     - Day surfaces:
                         · require S3/S4 day grid equality,
                         · require S4.gamma == S3.gamma per (merchant, day, tz_group_id),
                         · check Σ_group p_group = 1 per merchant/day; record max_abs_mass_error_s4.
                     - Optional router evidence:
                         · if S5/S6 logs & RNG core logs present:
                             - ensure 2 draws per S5 selection (group+site) and 1 draw per S6 virtual arrival,
                               envelopes obeyed, counters monotone, mapping coherent, edge attrs in policy domain.
                     - Emits JSON report with:
                         · checks[] (id, status ∈ {PASS,FAIL,WARN}, codes[]),
                           metrics (merchants_total, groups_total, days_total, selections_checked, draws_expected,
                           draws_observed, alias_decode_max_abs_delta, max_abs_mass_error_s4),
                           summary.overall_status ∈ {PASS,FAIL}
                     - S7 is RNG-free; it never mutates plan surfaces; it is the sole audit artefact for 2B at [seed,fingerprint]

                                      |
                                      | all s7_audit_report[seed,fingerprint] for this fingerprint
                                      v

             (S8) Validation bundle & PASS flag for 2B (fingerprint-scoped)  [NO RNG]
                inputs: s0_gate_receipt_2B, sealed_inputs_v1       @ [fingerprint],
                        s7_audit_report                            @ [seed, fingerprint] for all Seeds_required,
                        policies alias_layout/route_rng/virtual_edge,
                        provenance of s2_alias_index/blob, s3_day_effects, s4_group_weights         
                -> validation_bundle_2B/     @ [fingerprint]
                     - Discover Seeds_required = intersection of seeds that have S2/S3/S4 for this fingerprint.
                     - Require one PASS s7_audit_report per seed ∈ Seeds_required.
                     - Stage a bundle workspace under a temp root:
                         · copy S0 evidence + sealed_inputs_v1 + all s7_audit_report[seed] (+ optional provenance snapshots).
                     - Build index.json (bundle index):
                         · one row per non-flag file: {path, sha256_hex}, path relative; ASCII-lex by path; no duplicates;
                           every file exists; `_passed.flag` excluded.
                         · validate against canonical bundle index law (schemas.1A.yaml#/validation/validation_bundle.index_schema).
                     - Compute bundle_digest = SHA-256(concat(all indexed file bytes in ASCII-lex path order)).
                -> validation_passed_flag_2B  @ [fingerprint]
                     - _passed.flag_2B content: `sha256_hex = <bundle_digest>`
                     - validate against passed_flag schema; path↔embed equality for fingerprint.
                     - Publish bundle+flag via single atomic move into `…/validation/fingerprint={manifest_fingerprint}/`;
                       write-once; idempotent re-emit must be byte-identical.
                     - This pair forms the **2B HashGate** for the fingerprint


Downstream touchpoints
----------------------
- **Any consumer of 2B routing plan surfaces** (e.g. Layer-2 arrival mechanics, downstream simulators, scenario runner):
    1) Locate `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/`.
    2) Read `index.json`, recompute SHA-256 over the listed files’ raw bytes in ASCII-lex path order (excluding `_passed.flag`).
    3) Read `_passed.flag_2B` and compare its `sha256_hex` to the recomputed digest.
    4) Only if they match MAY the consumer read:
         · s1_site_weights        @ [seed, fingerprint]   (static site law)
         · s2_alias_index/blob    @ [seed, fingerprint]   (alias sampler)
         · s3_day_effects         @ [seed, fingerprint]   (γ factors)
         · s4_group_weights       @ [seed, fingerprint]   (day-specific group mixes)
       **No PASS → No Read** for all 2B routing-plan outputs.

- **Runtime router (5A/5B & higher layers):**
    - Treat S5/S6 as implementation of the routing plan encoded by S1–S4:
        · arrivals in → (merchant_id, tz_group_id, site_id[, edge_id]) out,
          under the RNG envelope & day-effects governed by 2B policies and sealed in S0.
    - Replayability & audits rely on s5_selection_log, s6_edge_log and RNG core logs, with S7/S8 as the authoritative audit/bundle chain.

Legend
------
(Sx) = state
[name @ partitions] = artefact + its partition keys
[NO RNG] = state consumes no RNG (S0, S1, S2, S4, S7, S8)
[RNG-BOUNDED] = state uses governed Philox sub-streams with fixed draw budgets and RNG logs (S3, S5, S6)
HashGate for a segment = fingerprint-scoped validation_bundle + _passed.flag; **No PASS → No Read** of that segment’s plan/egress surfaces
```