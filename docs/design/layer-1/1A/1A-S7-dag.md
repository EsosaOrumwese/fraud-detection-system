```
                LAYER 1 · SEGMENT 1A — STATE S7 (INTEGER ALLOCATION ACROSS LEGAL COUNTRY SET)  [NO RNG BY DEFAULT]

Authoritative inputs (read-only at S7 entry)
--------------------------------------------
[S2] Domestic outlet count (fact; no reinterpretation):
    - rng_event_nb_final @ [seed, parameter_hash, run_id]
      · schema: schemas.layer1.yaml#/rng/events/nb_final
      · one row per resolved merchant
      · payload (core): merchant_id, n_outlets (N ≥ 2), mu, dispersion_k, nb_rejections
      · non-consuming finaliser (before==after; blocks=0; draws="0")  :contentReference[oaicite:0]{index=0}  

[S3] Order & domain base (sole inter-country order authority):
    - s3_candidate_set @ [parameter_hash]
      · schema: schemas.1A.yaml#/s3/candidate_set
      · rows: merchant_id × country_iso (home + foreigns)
      · columns (core): merchant_id, country_iso, is_home, candidate_rank, …
      · contracts:
          * exactly one home row with candidate_rank = 0
          * foreign rows have candidate_rank > 0, contiguous per merchant
          * **only** authority for cross-country order; file order is non-authoritative    

[S4] Foreign-target fact (consistency only; S7 does not re-pick K):
    - rng_event_ztp_final @ [seed, parameter_hash, run_id]
      · schema: schemas.layer1.yaml#/rng/events/ztp_final
      · payload: merchant_id, K_target ≥ 0, lambda_extra > 0, attempts, exhausted:bool, regime, reason?
      · non-consuming finaliser (before==after; blocks=0; draws="0")  :contentReference[oaicite:2]{index=2}  

[S5] Weights authority (currency→country; no persistence beyond S5):
    - ccy_country_weights_cache @ [parameter_hash]
      · schema: schemas.1A.yaml#/prep/ccy_country_weights_cache
      · PK: (currency, country_iso); Σ weight == 1.0 per currency at dp; FK to iso3166_canonical_2024    
      · **sole persisted weights surface**; S7 may only restrict/renormalise to its domain, in-memory.
    - (optional) merchant_currency @ [parameter_hash]
      · schema: schemas.1A.yaml#/prep/merchant_currency
      · κₘ (ISO-4217) per merchant; if present, S7 MUST NOT override it.   

[S6] Membership information (who is in the foreign set):
    - (optional convenience) s6_membership @ [seed, parameter_hash]  (if S6 policy emit_membership_dataset=true)
      · schema: schemas.1A.yaml#/alloc/membership
      · PK: (merchant_id, country_iso); subset of S3 foreign candidates; no order encoded.   
    - (always authoritative) rng_event_gumbel_key @ [seed, parameter_hash, run_id]
      · schema: schemas.layer1.yaml#/rng/events/gumbel_key
      · used to reconstruct membership if s6_membership absent or gated by PASS.    
    - s6_validation_receipt (PASS gate) @ data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/
      · schema: schemas.layer1.yaml#/validation/s6_receipt
      · _passed.flag SHA-256 over S6_VALIDATION.json; **no PASS → no read** of s6_membership.   

[N] Numeric / quantisation policy:
    - numeric_policy.json, math_profile_manifest.json  (from S0)  :contentReference[oaicite:8]{index=8}  
      · IEEE-754 binary64, RNE, FMA-OFF, no FTZ/DAZ; deterministic libm; fixed-order reductions.
    - residual_quantisation_policy (registry id)  :contentReference[oaicite:9]{index=9}  
      · dp_resid = 8 for residuals; ties-to-even decimal rounding; deterministic total-order tie-breaks.

[G] Run / lineage context:
    - {seed, parameter_hash, manifest_fingerprint, run_id}
    - rng_audit_log & rng_trace_log @ [seed, parameter_hash, run_id]
      · no new RNG families consumed for default lane; only S7’s own non-consuming events written.   

[Dict] Dictionary & registry:
    - dataset_dictionary.layer1.1A.yaml
      · IDs/paths for all above datasets; `outlet_catalogue`, candidate_set, etc.   
    - artefact_registry_1A.yaml
      · rng_event_residual_rank log, dependencies, module/substream labels. :contentReference[oaicite:12]{index=12}  


----------------------------------------------------------------- DAG (S7.1–S7.8 · domain → weights → counts → residual_rank events)

[S2],[S3],[S4],
[S5],[S6],[N],
[G],[Dict]      ->  (S7.1) Pre-flight & hard gates (per-run & per-merchant)
                       - Resolve dataset locations exclusively via the Data Dictionary.
                       - Enforce **PASS gates** before reading authorities:
                           * S5 PASS required for ccy_country_weights_cache (weights) — **no PASS → no read**.
                           * S6 PASS required before reading any S6 convenience surface (s6_membership).   
                       - Per merchant m:
                           * confirm:
                               – exactly one nb_final row (N = n_outlets ≥ 2)
                               – s3_candidate_set rows present and valid (home at candidate_rank=0; contiguous foreign ranks)
                               – (optional) ztp_final row (K_target); used for later consistency checks only
                           * enforce path↔embed equality on {seed, parameter_hash, run_id} for all log inputs.
                       - Merchants missing any required upstream fact ⇒ hard E_UPSTREAM_MISSING / E_SCHEMA_INVALID; S7 does not process them.

[S3],[S6],
[S4],[Dict]     ->  (S7.2) Domain assembly D = {home} ∪ selected_foreigns (ordered)
                       - For each merchant that passes S7.1:
                           1) Start from S3 candidate_set:
                               · home row (is_home=true, candidate_rank=0)
                               · foreign rows (candidate_rank>0) — **this order is canonical**.
                           2) Determine foreign membership:
                               · if s6_membership is available and PASSed:
                                   – use it as the set of selected foreign ISO2s
                               · else:
                                   – reconstruct selection from rng_event_gumbel_key + S3 per S6 rules
                               · in either case: membership must be **subset of S3 foreigns**.
                           3) Construct domain:
                               · D = {home} ∪ (S6-selected foreigns)
                               · if K_target=0 (from S4) OR S6-selected set empty ⇒ D = {home} only.
                       - Domain properties:
                           * D non-empty (home always present)
                           * within D, **order is strictly S3.candidate_rank** (home=0, then foreign ranks 1..).  
                       - S7 MUST NOT read or revive legacy country_set as order authority.   

[S5],[S2],
D,[N]           ->  (S7.3) Share vector over D (ephemeral; not persisted)
                       - Resolve merchant’s currency κₘ:
                           * from merchant_currency if present; else per S5/S0 deterministic rule.
                       - Read full κₘ weight vector from ccy_country_weights_cache (weights over all ISO for that currency).
                       - Restrict weights to domain D:
                           * s_i_raw = weight(κₘ, country_i) for each i ∈ D
                           * if any country_i in D has no S5 weight row ⇒ E_WEIGHT_SUPPORT_MISMATCH (per-merchant FAIL).
                       - Renormalise to probabilities within D:
                           * s_i = s_i_raw / Σ_{j∈D} s_j in binary64.
                           * if Σ_{j∈D} s_j == 0 ⇒ E_ZERO_SUPPORT (merchant hard-fail).
                       - S7 **MUST NOT** persist {s_i}; the restricted / renormalised vector is memory-only.

D, s_i, N,
[N policy]      ->  (S7.4) Fractional targets, floor step & residuals (deterministic)
                       - For each i ∈ D:
                           * compute fractional target:
                               · a_i = N · s_i   (binary64, S0 numeric law)
                           * floor:
                               · b_i = floor(a_i)  (integer ≥ 0)
                       - Compute remainder:
                           * d = N − Σ_{i∈D} b_i
                           * enforce: 0 ≤ d < |D|; else E_FLOOR_REMAINDER (merchant FAIL). :contentReference[oaicite:15]{index=15}  
                       - Residuals:
                           * raw residual r_i = a_i − b_i  (0 ≤ r_i < 1 in exact reals)
                           * quantise at dp_resid = 8 via ties-to-even:
                               · r_i^⋄ = round_half_even(r_i, dp_resid)
                           * r_i^⋄ and dp_resid are used for ranking; raw r_i is not persisted.

D, r_i^⋄, d,
[S3],[N]        ->  (S7.5) Largest-remainder bump & residual_rank (ordering)
                       - Build a **total, stable** order over domain indices i ∈ D:
                           1) residual r_i^⋄ descending
                           2) ISO-2 country_iso A→Z
                           3) S3.candidate_rank ascending
                           4) stable input index (for absolute determinism)   
                       - Let this ordered list be [i₁, i₂, …, i_|D|].
                       - Define residual_rank_i = 1-based position of i in this order.
                       - Bump counts:
                           * for k=1..d: c_{i_k} = b_{i_k} + 1
                           * for all other j: c_j = b_j
                       - Invariants:
                           * Σ_{i∈D} c_i = N
                           * ∀i, c_i ≥ 0
                           * |c_i − N·s_i| ≤ 1  (Largest-Remainder property)
                           * residual_rank_i ∈ {1..|D|} for all i.

D, c_i,
(optional bounds) ->  (S7.6) Optional bounds variant (feature-flag; default OFF)
                       - If bounds policy is enabled by configuration:
                           * floors L_i and ceilings U_i are given per-country (deterministic artefact).
                           * Feasibility:
                               · Σ L_i ≤ N ≤ Σ U_i must hold; otherwise E_BOUNDS_INFEASIBLE (merchant FAIL).
                           * Enforce floors:
                               · b_i ← max(b_i, L_i) before computing d; recompute d accordingly.
                           * During bump:
                               · only countries with c_i < U_i are eligible to receive +1,
                                 ranked by the same residual order; tie-break unchanged.
                       - Bounds variant MUST NOT introduce new datasets or order surfaces; all other contracts identical. :contentReference[oaicite:17]{index=17}  

D, c_i,
residual_rank_i,
[G],[Dict]      ->  (S7.7) Emit rng_event.residual_rank & update trace (non-consuming)
                       - For each merchant and each i ∈ D:
                           * emit exactly one rng_event_residual_rank row to:
                               · logs/rng/events/residual_rank/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
                               · schema: schemas.layer1.yaml#/rng/events/residual_rank    
                           * Envelope (binding):
                               · ts_utc (RFC3339, Z, 6 fractional digits)
                               · run_id, seed, parameter_hash, manifest_fingerprint
                               · module="1A.integerisation"
                               · substream_label="residual_rank"
                               · rng_counter_before == rng_counter_after
                               · blocks = 0, draws = "0"   (non-consuming event)
                           * Payload (core):
                               · merchant_id
                               · country_iso
                               · N (n_outlets)
                               · count_i (final integer count for this country)
                               · residual_dp = r_i^⋄ (string/decimal at dp_resid)
                               · residual_rank (1-based position from S7.5)
                       - Update rng_trace_log for (module="1A.integerisation", substream_label="residual_rank"):
                           * append one cumulative row after each event append:
                               · events_total, blocks_total, draws_total (saturating); blocks_total and draws_total remain 0 for this family.
                       - Optional **Dirichlet lane** (feature-flag; default OFF):
                           * If enabled by policy, S7 MAY emit rng_event.dirichlet_gamma_vector once per merchant:
                               · mean-anchored to S5 weights restricted to D
                               · consumes its own RNG draws under module="1A.dirichlet_sampler"
                               · does **not** change allocation counts or residual_rank events; default remains deterministic-only.   

all above,
[G],[Dict]      ->  (S7.8) Invariants, failure modes & hand-off to S8/S9
                       - Per-merchant allocation invariants:
                           * Σ_{i∈D} c_i = N  (sum law)
                           * ∀i, c_i ≥ 0
                           * ∀i, |c_i − N·s_i| ≤ 1  (proximity law)
                           * if bounds enabled: L_i ≤ c_i ≤ U_i for all i. :contentReference[oaicite:20]{index=20}  
                       - Domain & authority invariants:
                           * D = {home} ∪ (S6-selected foreigns); if K_target=0 or no foreign membership ⇒ D={home}.
                           * S3.candidate_rank remains **sole** cross-country order authority.
                           * S5 ccy_country_weights_cache remains **sole** weight authority; S7 persists no weights.
                           * S7 MUST NOT read or revive legacy country_set as order authority.
                       - RNG discipline:
                           * residual_rank family is non-consuming: for every event, after==before, blocks=0, draws="0".
                           * if Dirichlet lane enabled, its blocks/draws obey global RNG envelope law and have isolated (module,substream_label).
                       - Failure classes (examples; mapped to S0/S9 global errors):
                           * E_UPSTREAM_MISSING / E_SCHEMA_INVALID / E_PATH_EMBED_MISMATCH
                           * E_ZERO_SUPPORT / E_FLOOR_REMAINDER / E_BOUNDS_INFEASIBLE
                           * E_S3_DOMAIN_VIOLATION (D contains non-S3 candidate or missing home)
                           * RNG_ACCOUNTING_FAIL (for Dirichlet lane if enabled)
                       - On any **hard FAIL**:
                           * S7 MUST NOT be considered complete for the run; S9 will reflect failure in validation_bundle_1A and no `_passed.flag` will be emitted for this fingerprint.


State boundary (authoritative outputs of S7)
-------------------------------------------
- rng_event_residual_rank           @ [seed, parameter_hash, run_id]  (required)
    * one non-consuming row per (merchant_id, country_iso) in D.
    * records (N, count_i, residual_dp, residual_rank) for integer allocation.
    * module="1A.integerisation", substream_label="residual_rank".

- rng_trace_log rows for residual_rank substream
    * module="1A.integerisation", substream_label="residual_rank".
    * blocks_total = draws_total = 0 (non-consuming family).

- (feature-flag lane; default OFF) rng_event_dirichlet_gamma_vector @ [seed, parameter_hash, run_id]
    * optional diagnostic anchoring to a Dirichlet sample over D; mean-anchored to S5 weights.
    * does not alter counts or residual_rank contracts.


Downstream touchpoints (from S7 outputs)
----------------------------------------
- S8 (Outlet catalogue materialisation):
    * Reads:
        – S2 nb_final.N (total outlets)
        – S3.s3_candidate_set (inter-country order, home=0)
        – S7’s per-country counts (via replay of residual_rank events, or a future counts cache if ever introduced)
    * MUST:
        – allocate exactly c_i sites per (merchant_id, legal_country_iso) using within-country site_order.
        – never infer cross-country order from residual_rank; still join S3.candidate_rank.   

- S9 (1A validation bundle & HashGate):
    * Replays S7 integerisation per merchant from:
        – nb_final (N), S5 weights, S3 domain, S6 membership, residual_quantisation_policy
        – rng_event_residual_rank (+ rng_event_dirichlet_gamma_vector if lane enabled)
        – rng_trace_log (residual_rank substream)
    * Asserts all S7 invariants (sum/proximity/bounds/authority) before admitting S7 into validation_bundle_1A for this fingerprint.   
```