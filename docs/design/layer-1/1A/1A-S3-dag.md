```
        LAYER 1 · SEGMENT 1A — STATE S3 (CANDIDATE UNIVERSE & TOTAL ORDER)  [NO RNG]

Authoritative inputs (read-only at S3 entry)
-------------------------------------------
[M] Merchant scope & upstream gates:
    - merchant_ids (ingress) @ schemas.ingress.layer1.yaml#/merchant_ids
        · merchant_id:u64, home_country_iso:ISO-2, mcc, channel (closed vocab)
    - rng_event_hurdle_bernoulli @ [seed, parameter_hash, run_id]
        · payload: {merchant_id, is_multi, …}; exactly 1 per merchant
    - rng_event_nb_final @ [seed, parameter_hash, run_id]
        · payload: {merchant_id, n_outlets ≥ 2, mu, dispersion_k}; exactly 1 per merchant
        · non-consuming finaliser (before==after; blocks=0, draws="0")

[P] S3 policy artefacts (governed; value-only):
    - policy.s3.rule_ladder.yaml
        · ordered rules[] with total precedence; closed reason_codes[]; closed filter_tags[]
        · optional validity window; optional static sets/maps/constants
    - (opt) policy.s3.base_weight.yaml
        · deterministic base-weight prior formula, coeffs, fixed dp
    - (opt) policy.s3.thresholds.yaml
        · deterministic integerisation bounds / feasibility thresholds (L_i, U_i, etc.)

[R] Static references:
    - iso3166_canonical_2024  (canonical ISO-2 set + lexicographic order)
    - (opt) static.currency_to_country.map.json
        · currency_code → [country_iso]; deterministic, no RNG

[N] Numeric / math policy:
    - numeric_policy.json
    - math_profile_manifest.json
        · inherit S0.8: IEEE-754 binary64, RNE, FMA-OFF, no FTZ/DAZ; deterministic libm

[G] Run / lineage context:
    - {seed, parameter_hash, manifest_fingerprint, run_id} from S0
    - rng_audit_log / rng_trace_log exist (S3 does not update them)
    - no S3-specific RNG families are defined (S3 never draws)

[Dict] Dictionary & registry:
    - dataset_dictionary.layer1.1A.yaml
        · IDs, partitions, $ref for s3_candidate_set, s3_base_weight_priors,
          s3_integerised_counts, s3_site_sequence
    - artefact_registry_1A.yaml
        · semver + digest for policy.s3.*; S3 datasets; inclusion in manifest_fingerprint


----------------------------------------------------------------- DAG (S3.0–S3.6, deterministic; parameter-scoped; no RNG)

[M],[P],[R],
[N],[G],[Dict] ->  (S3.0) Load scopes, gates & assemble Context
                     - Resolve all read locations via the Data Dictionary (no literal paths).
                     - Open governed artefacts atomically:
                         * policy.s3.rule_ladder.yaml (rules, reason_codes, filter_tags, window)
                         * iso3166_canonical_2024
                         * (opt) static.currency_to_country.map.json
                     - For each merchant_id:
                         * read one ingress merchant row (home_country_iso, mcc, channel)
                         * read exactly one hurdle_bernoulli row
                         * read exactly one nb_final row
                         * enforce path↔embed equality on {seed, parameter_hash, run_id} for S1/S2 logs
                     - Preconditions (per merchant):
                         * is_multi == true  ⇒ may enter S3
                         * n_outlets N ≥ 2
                         * channel in ingress closed vocab
                         * home_country_iso ∈ iso3166_canonical_2024
                         * rule ladder is total; reason_codes/filter_tags are closed; window (if any) holds
                     - On success, assemble immutable Context:
                         * Ctx = {merchant_id, home_country_iso, mcc, channel,
                                  N, seed, parameter_hash, manifest_fingerprint,
                                  artefact_digests}
                     - Failures map to ERR_S3_AUTHORITY_MISSING / PRECONDITION /
                       PARTITION_MISMATCH / VOCAB_INVALID / RULE_LADDER_INVALID.
                     - No tables/events written; S3.0 is read-only.

Ctx,[P]            ->  (S3.1) Rule ladder evaluation (cross-border policy; no I/O)
                         - Evaluate rules[] in fixed precedence order:
                             DENY ≻ ALLOW ≻ CLASS ≻ LEGAL ≻ THRESHOLD ≻ DEFAULT.
                         - Each rule:
                             · has deterministic predicate over Ctx + artefact-declared sets/maps
                             · emits one reason_code and zero-or-more filter_tags when it fires
                         - Accumulate RuleTrace = ordered list of fired rules with their reasons/tags.
                         - Derive eligible_crossborder: bool
                             · from decision-bearing rules per precedence / priority
                             · fall back to DEFAULT branch if no decision rule fired
                         - Outputs:
                             · RuleTrace (ordered)
                             · eligible_crossborder:bool
                         - No writes; no RNG.

Ctx,RuleTrace,
[R]                 ->  (S3.2) Candidate universe construction (home + foreigns)
                         - Start candidate set C with home:
                             · row for (merchant_id, home_country_iso,
                                        is_home=true, reason_codes, filter_tags)
                         - If eligible_crossborder == true:
                             · derive admissible foreign ISO2s deterministically from:
                                 – ladder outputs (e.g. region/class tags)
                                 – (opt) static.currency_to_country.map.json
                                 – ISO set (sanctions, allowlists, etc.), all per policy
                             · add foreign ISO2s to C, tagging each with:
                                 – reason_codes (why this ISO was admitted)
                                 – filter_tags (class/segment markers)
                         - De-duplicate by country_iso; keep stable admission order.
                         - Guarantees:
                             · C non-empty and contains exactly one home row.
                             · K_foreign = |C \ {home}|; if eligible_crossborder == false ⇒ K_foreign = 0.
                         - Failure:
                             · empty C or missing home ⇒ ERR_S3_CANDIDATE_CONSTRUCTION.
                         - Still no writes.

C,[R]              ->  (S3.3) Total order & candidate_rank (sole inter-country order)
                         - Define total comparator (admission-order comparator from spec §9):
                             1) coarse groups & rule outcomes (e.g. DENY’d futures, priority tiers)
                             2) then ISO lexicographic A→Z
                             3) then stable original input index if needed
                         - Sort C under this comparator to obtain ordered list C_ranked.
                         - Assign candidate_rank per merchant:
                             · candidate_rank starts at 0, contiguous integers
                             · home row has candidate_rank == 0
                         - Outputs:
                             · C_ranked = C + candidate_rank
                         - Invariants per merchant:
                             · candidate_rank contiguous, no duplicates
                             · candidate_rank(home)=0
                         - Failures:
                             · gaps or duplicates in ranks ⇒ ERR_S3_ORDERING_NONCONTIGUOUS
                             · no row with candidate_rank==0 & is_home==true ⇒ ERR_S3_ORDERING_HOME_MISSING.

C_ranked,[P]       ->  (S3.4) Base-weight priors (optional; deterministic scores)
                         - If policy.s3.base_weight.yaml is enabled:
                             · read dp and coeffs/constants from artefact.
                             · for each candidate in C_ranked:
                                 – compute continuous prior weight w_i in spelled evaluation order (§12)
                                 – quantise to base_weight_dp string w_i^⋄ with exactly dp decimals.
                         - Outputs:
                             · C_weighted = C_ranked + w_i^⋄ (for emission only)
                         - Contracts:
                             · dp constant within run; encoded once per merchant/partition.
                             · priors are deterministic scores only; **never** used for ranking.
                         - Failure:
                             · unknown coeff/param or missing dp ⇒ ERR_S3_WEIGHT_CONFIG.
                         - If priors disabled, skip S3.4; carry C_ranked forward.

C_weighted or
C_ranked, N,[P]    ->  (S3.5) Integerise to per-country counts (optional; sum to N)
                         - If S3 owns integerisation:
                             · Choose fractional targets a_i:
                                 – priors present: s_i = w_i^⋄ / Σ_j w_j^⋄ (guard Σ>0); a_i = N·s_i
                                       · if Σ_j w_j^⋄ == 0 ⇒ fall back to equal-weight; raise ERR_S3_WEIGHT_ZERO
                                 – no priors: equal-weight s_i = 1/M; a_i = N/M
                             · (Optional bounds via policy.s3.thresholds.yaml):
                                 – enforce Σ_i L_i ≤ N ≤ Σ_i U_i (else ERR_S3_INTEGER_FEASIBILITY)
                                 – initialise b_i = L_i; N′ = N − Σ L_i; cap_i = U_i − L_i
                             · Floor step:
                                 – b_i = floor(a_i) (or L_i + floor(a_i′) under bounds)
                                 – d = N − Σ_i b_i  with 0 ≤ d < M
                             · Residuals:
                                 – r_i = a_i − b_i
                                 – quantise r_i^⋄ = round_to_dp(r_i, dp_resid=8) (binding)
                             · Deterministic bump (largest remainder):
                                 1) sort by r_i^⋄ descending
                                 2) tie-break by country_iso A→Z
                                 3) if still tied, by candidate_rank, then stable index
                                 – bump +1 for top d entries
                                 – define residual_rank_i as 1-based position in this order
                             · Final counts:
                                 – count_i = b_i + 1[i in top d]
                         - Outputs:
                             · C_counts = per-country rows with count_i ≥ 0, Σ count_i = N,
                               plus residual_rank_i.
                         - Failures:
                             · Σ count_i ≠ N ⇒ ERR_S3_INTEGER_SUM_MISMATCH
                             · any count_i < 0 ⇒ ERR_S3_INTEGER_NEGATIVE.
                         - If S3 does not integerise, skip S3.5; counts belong to S7/S8 instead.

C_ranked / 
C_weighted /
C_counts, Ctx,
[Dict],[G]         ->  (S3.6) Emit parameter-scoped tables (authority surfaces; no RNG)
                         - Resolve dataset IDs via dictionary; partition writes by parameter_hash only:
                             1) s3_candidate_set  (required)
                                 · schema: schemas.1A.yaml#/s3/candidate_set
                                 · path: data/layer1/1A/s3_candidate_set/parameter_hash={parameter_hash}/
                                 · rows: C_ranked
                                 · columns (core): merchant_id, country_iso, candidate_rank,
                                                   reason_codes[], filter_tags[], parameter_hash,
                                                   produced_by_fingerprint? (optional)
                                 · contracts:
                                     – unique country_iso per merchant
                                     – candidate_rank total & contiguous; candidate_rank(home)=0
                                     – **sole authority for inter-country order** (downstream must not
                                       infer order from file order or ISO alone)
                             2) (opt) s3_base_weight_priors  (if S3.4 ran)
                                 · schema: #/s3/base_weight_priors
                                 · rows: C_weighted
                                 · columns: merchant_id, country_iso,
                                             base_weight_dp (fixed-dp string), dp:u8,
                                             parameter_hash, produced_by_fingerprint?
                                 · priors live only here (not duplicated into candidate_set).
                             3) (opt) s3_integerised_counts  (if S3.5 ran)
                                 · schema: #/s3/integerised_counts
                                 · rows: C_counts
                                 · columns: merchant_id, country_iso,
                                             count (i64 ≥ 0), residual_rank (u32),
                                             parameter_hash, produced_by_fingerprint?
                                 · Σ count_i = N per merchant; residual_rank reconstructs bump set.
                             4) (opt, Variant A) s3_site_sequence (if S3 owns sequencing; see §11)
                                 · schema: #/s3/site_sequence
                                 · rows: one per (merchant_id, country_iso, site_order) with
                                         site_order ∈ {1..count_i}, optional site_id "000001".."999999"
                                 · contracts:
                                     – contiguous 1..count_i per (merchant,country)
                                     – no duplicate (country_iso, site_order) (or site_id)
                                     – sequencing never changes inter-country order (still candidate_rank).
                         - Write discipline:
                             · partition: parameter_hash={…}; **no seed in any S3 path**
                             · embed parameter_hash column matching path byte-for-byte
                             · MAY embed produced_by_fingerprint == manifest_fingerprint (informational)
                             · emit _manifest.json sidecar with manifest_fingerprint, parameter_hash,
                               dataset_digest, row_count, files_sorted.
                         - Failures:
                             · any schema or path↔embed mismatch ⇒ ERR_S3_EGRESS_SHAPE.
                         - No RNG events are produced; rng_audit_log / rng_trace_log are untouched.


State boundary (authoritative outputs of S3)
-------------------------------------------
- s3_candidate_set            @ [parameter_hash]   (required)
    * Deterministic ordered candidate universe per merchant.
    * candidate_rank is the **only** cross-country order authority; home rank=0.

- (optional) s3_base_weight_priors  @ [parameter_hash]
    * Deterministic base-weight priors per candidate (fixed-dp strings); priors live here only.

- (optional) s3_integerised_counts  @ [parameter_hash]
    * Deterministic integer counts per merchant×country; Σ count = N; includes residual_rank.

- (optional) s3_site_sequence       @ [parameter_hash]
    * Deterministic within-country site_order (and optional 6-digit site_id) if S3 owns sequencing.

All S3 outputs are parameter-scoped only; no seed/run_id in partitions; S3 defines **no RNG families**.


Downstream touchpoints (from S3 outputs)
----------------------------------------
- S4 (ZTP foreign K_target):
    * Uses:
        - crossborder_eligibility_flags (gate) from S0 (is_eligible)
        - s3_candidate_set to derive A = |foreign candidates| (set size only; not order).
    * Treats file order as non-authoritative; A is computed from the set of foreign ISO2s.

- S5 (Currency→country expansion):
    * MUST NOT encode or alter inter-country order; if it needs an ordering, it must join
      s3_candidate_set.candidate_rank.
    * crossborder_features / weight caches are order-free; S3 remains sole order authority.

- S6 (Foreign set selection):
    * Reads s3_candidate_set as:
        - authority for admissible set A, and
        - sole authority for cross-country order when tagging membership.
    * Membership surfaces (s6_membership) MUST NOT encode their own inter-country order;
      they must be joined back to S3 by candidate_rank when needed.

- S7 (Integer allocation across legal set):
    * If S3 integerises: consumes s3_integerised_counts as the **only** authority for
      per-country counts; S7 must not recompute from priors or weights.
    * Always uses s3_candidate_set to know which countries are in scope and in what order.

- S8 (Outlet catalogue & sequencing):
    * Uses s3_candidate_set to recover cross-country order; outlet_catalogue itself does
      not encode inter-country order.
    * If s3_integerised_counts is present: treats its counts as authoritative
      `final_country_outlet_count` per merchant×country.
    * If s3_site_sequence exists: S8 cross-checks it but must not change within-country
      sequencing semantics.

- S9 (Replay validation & HashGate):
    * Validates S3 via schemas.1A.yaml#/s3/*:
        - re-checks candidate_rank totality & home rank=0
        - re-sums any s3_integerised_counts to N from nb_final
        - cross-checks optional s3_site_sequence contiguity and uniqueness.
    * Treats S3 tables, not legacy country_set/ranking_residual_cache, as the authority.

```