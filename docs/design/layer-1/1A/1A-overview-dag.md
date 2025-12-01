```text
                     LAYER 1 - SEGMENT 1A (Merchants → outlet stubs)

Authoritative inputs (sealed in S0)
-----------------------------------
[M] Ingress merchant universe:
    - merchant_ids (canonical merchant rows)

[R] Reference surfaces:
    - iso3166_canonical_2024
    - world_bank_gdp_20250415
    - gdp_bucket_map_2024 (Jenks K=5)

[C] Model coefficients:
    - hurdle_coefficients.yaml        (logistic hurdle + NB mean)
    - nb_dispersion_coefficients.yaml (NB dispersion)

[P] Policy / hyperparams:
    - crossborder_hyperparams.yaml
    - policy.s3.rule_ladder.yaml
    - policy.s3.base_weight.yaml (if used)
    - ccy_smoothing_params.yaml

[W] Currency priors:
    - settlement_shares_2024Q4
    - ccy_country_shares_2024Q4

[N] Numeric & RNG profile:
    - numeric_policy.json
    - math_profile_manifest.json
    - Philox2x64-10, binary64, RNE, FMA-off, open-interval U(0,1)

DAG
---
(M,R,C,P,W,N) --> (S0) Universe, lineage & deterministic prep (no RNG)
                    - Fix {seed, parameter_hash, run_id, manifest_fingerprint}
                    - Build design surfaces & features:
                        * hurdle_design_matrix          @ [parameter_hash]
                        * crossborder_features          @ [parameter_hash]   (conceptual; via S0.6 policy)
                    - (optional) hurdle_pi_probs        @ [parameter_hash]   (π cache)
                    - crossborder_eligibility_flags     @ [parameter_hash]   (S0.6 gate for cross-border)
                    - Seal numeric/RNG law + manifests (audit inputs, digests)

                                      |
                                      | parameter_hash, manifest_fingerprint, design vectors
                                      v

             (S1) Hurdle: single vs multi  [RNG]
                inputs: hurdle_design_matrix, hurdle_coefficients
                -> rng_event.hurdle_bernoulli     @ [seed, parameter_hash, run_id]

             (S2) NB mixture → N≥2 for is_multi=1  [RNG]
                inputs: S1.hurdle (is_multi), nb_dispersion_coefficients, GDP features
                -> rng_event.gamma_component       @ [seed, parameter_hash, run_id]
                -> rng_event.poisson_component     @ [seed, parameter_hash, run_id]
                -> rng_event.nb_final  (non-cons.) @ [seed, parameter_hash, run_id]
                     (N = total outlet count per multi-site merchant)

             (S3) Candidate universe & TOTAL order (deterministic)
                inputs: merchant_ids, iso3166, static currency→country map,
                        S1 (is_multi), S2.nb_final (N), crossborder_eligibility_flags
                -> s3_candidate_set          @ [parameter_hash]     (sole cross-country order; candidate_rank)
                -> (opt) s3_base_weight_priors   @ [parameter_hash]
                -> (opt) s3_integerised_counts   @ [parameter_hash] (deterministic counts + residual_rank; owned by S3)

             (S4) ZTP foreign K_target (logs only)  [RNG]
                inputs: S2.nb_final (N), S3.candidate_set, crossborder_eligibility_flags,
                        crossborder_features, crossborder_hyperparams
                -> rng_event.ztp_rejection         @ [seed, parameter_hash, run_id]
                -> rng_event.ztp_retry_exhausted   @ [seed, parameter_hash, run_id]  (when cap hit)
                -> rng_event.ztp_final (non-cons.) @ [seed, parameter_hash, run_id]
                     (fixes K_target; A=0 → K_target=0 without draws)

             (S5) Currency→country weight expansion (deterministic)
                inputs: settlement_shares_2024Q4, ccy_country_shares_2024Q4,
                        iso3166, ccy_smoothing_params
                -> ccy_country_weights_cache  @ [parameter_hash]
                     (sole persisted currency→country weight surface; Σ=1 per currency)
                -> merchant_currency          @ [parameter_hash]
                -> sparse_flag                @ [parameter_hash]   (diagnostics only)

             (S6) Foreign membership selection (Gumbel-top-k)  [RNG]
                inputs: S3.candidate_set, S4.ztp_final(K_target),
                        S5.ccy_country_weights_cache, merchant_currency
                -> rng_event.gumbel_key       @ [seed, parameter_hash, run_id]
                -> (opt) s6_membership        @ [seed, parameter_hash]
                     (unordered pairs (merchant_id,country_iso); order remains in S3)
                -> s6_validation_receipt      @ [seed, parameter_hash]
                     (PASS gate for S7/S8 reads on S6 outputs)

             (S7) Integer allocation over {home ∪ foreigns} (deterministic)
                inputs: S2.nb_final (N),
                        S4.ztp_final(K_target),
                        S3.candidate_set (domain & candidate_rank),
                        S5.ccy_country_weights_cache (restricted+renormalised ephemerally),
                        S6 PASS / membership
                -> rng_event.residual_rank (non-cons.)       @ [seed, parameter_hash, run_id]
                -> (opt) rng_event.dirichlet_gamma_vector    @ [seed, parameter_hash, run_id]
                     (Dirichlet lane, observability only; S3 remains order authority)
                # No Parquet counts table by default; deterministic counts live in S3.integerised_counts today.

             (S8) Egress: outlet stubs & within-country sequences (deterministic)
                inputs: S3.candidate_set (home vs foreign identity, candidate_rank),
                        per-country counts (S3.integerised_counts or S7 flow-through),
                        S2.nb_final.raw draw,
                        S6 PASS (s6_validation_receipt)
                -> outlet_catalogue @ [seed, fingerprint]
                     - PK: (merchant_id, legal_country_iso, site_order)
                     - site_order is within-country only; no inter-country order.
                -> rng_event.sequence_finalize      @ [seed, parameter_hash, run_id]  (non-cons.)
                -> rng_event.site_sequence_overflow @ [seed, parameter_hash, run_id]  (guardrail; sequence space exhausted)

   (All logs + datasets) --> (S9) Replay validation & PASS gate (deterministic)
                -> validation_bundle_1A/  @ [fingerprint]
                -> _passed.flag           @ [fingerprint]
                     (SHA-256 over bundle bytes; flag excluded; ASCII-lex index order)

Downstream touchpoints
----------------------
- 1B MUST:
    1) locate `fingerprint={manifest_fingerprint}`;
    2) verify `_passed.flag` matches `SHA256(validation_bundle_1A)`;
    3) only then read `outlet_catalogue`.   (No PASS → No read.)
- Any consumer that needs **inter-country order** MUST join
    `s3_candidate_set.candidate_rank` (home = rank 0).
- `ccy_country_weights_cache` is the only persisted currency→country weight surface.
    S6/S7 MAY restrict/renormalise it in-memory, but MUST NOT persist alternatives.

Legend
------
(Sx) = state
[name @ partitions] = artefact + its partition keys
[RNG] = RNG-bounded state; events logged under [seed, parameter_hash, run_id] with 1 trace append per event
Order authority lives ONLY in S3 (`candidate_rank`); S8 egress is inter-country order-free (within-country only).
```

