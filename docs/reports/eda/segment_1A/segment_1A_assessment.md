# Segment 1A - Realism Assessment (Design/Impl Context)

Run: runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92

This report assesses how realistic the 1A outputs are, in light of the design intent and implementation decisions. It does not assume real data; it measures plausibility, structural richness, and internal consistency sufficient for a semblance of realism.

## 1) What 1A produced in this run
                  dataset_dir                                                                                                path  file_count_total  file_count_sampled  sample_bytes                    suffixes
    ccy_country_weights_cache     runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\ccy_country_weights_cache                 3                   3        127384        .flag,.json,.parquet
crossborder_eligibility_flags runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\crossborder_eligibility_flags                 1                   1         87785                    .parquet
         crossborder_features          runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\crossborder_features                 1                   1         93074                    .parquet
         hurdle_design_matrix          runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\hurdle_design_matrix                 1                   1         98552                    .parquet
              hurdle_pi_probs               runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\hurdle_pi_probs                 1                   1        141223                    .parquet
            merchant_currency             runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\merchant_currency                 1                   1         88611                    .parquet
             outlet_catalogue              runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\outlet_catalogue                 1                   1         61643                    .parquet
              s0_gate_receipt               runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\s0_gate_receipt                 1                   1          3251                       .json
        s3_base_weight_priors         runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\s3_base_weight_priors                 1                   1         29101                    .parquet
             s3_candidate_set              runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\s3_candidate_set                 1                   1         55742                    .parquet
                           s6                            runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\s6                 4                   4        506323 .flag,.json,.jsonl,.parquet
                sealed_inputs                 runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\sealed_inputs                 1                   1          9543                       .json
                   validation                    runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A\validation                 8                   8         16921                 .flag,.json

## 2) Expected datasets from design contracts (dictionary)
                              id     status                                                                                                                      path                                             schema_ref
       ccy_country_weights_cache   approved                                                 data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/        schemas.1A.yaml#/prep/ccy_country_weights_cache
           s5_validation_receipt   approved                               data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/S5_VALIDATION.json             schemas.layer1.yaml#/validation/s5_receipt
                  s5_passed_flag   approved                                     data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/_passed.flag            schemas.layer1.yaml#/validation/passed_flag
               merchant_currency   approved                                                         data/layer1/1A/merchant_currency/parameter_hash={parameter_hash}/                schemas.1A.yaml#/prep/merchant_currency
            hurdle_design_matrix   approved                                                      data/layer1/1A/hurdle_design_matrix/parameter_hash={parameter_hash}/            schemas.1A.yaml#/model/hurdle_design_matrix
                 hurdle_pi_probs   approved                                                           data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/                 schemas.1A.yaml#/model/hurdle_pi_probs
                     sparse_flag   approved                                                               data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/                      schemas.1A.yaml#/prep/sparse_flag
   crossborder_eligibility_flags   approved                                             data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/    schemas.1A.yaml#/prep/crossborder_eligibility_flags
                     country_set deprecated                                                   data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/                     schemas.1A.yaml#/alloc/country_set
                   s6_membership   approved                                                 data/layer1/1A/s6/membership/seed={seed}/parameter_hash={parameter_hash}/                      schemas.1A.yaml#/alloc/membership
           s6_validation_receipt   approved                                                            data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/             schemas.layer1.yaml#/validation/s6_receipt
       ranking_residual_cache_1A deprecated                                     data/layer1/1A/ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/          schemas.1A.yaml#/alloc/ranking_residual_cache
                outlet_catalogue   approved                                  data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/               schemas.1A.yaml#/egress/outlet_catalogue
                s3_candidate_set   approved                                                          data/layer1/1A/s3_candidate_set/parameter_hash={parameter_hash}/                      schemas.1A.yaml#/s3/candidate_set
           s3_base_weight_priors   approved                                                     data/layer1/1A/s3_base_weight_priors/parameter_hash={parameter_hash}/                 schemas.1A.yaml#/s3/base_weight_priors
           s3_integerised_counts   approved                                                     data/layer1/1A/s3_integerised_counts/parameter_hash={parameter_hash}/                 schemas.1A.yaml#/s3/integerised_counts
                s3_site_sequence   approved                                                          data/layer1/1A/s3_site_sequence/parameter_hash={parameter_hash}/                      schemas.1A.yaml#/s3/site_sequence
hurdle_stationarity_tests_2024Q4   approved                                                 data/layer1/1A/hurdle_stationarity_tests/parameter_hash={parameter_hash}/  schemas.1A.yaml#/validation/hurdle_stationarity_tests
            crossborder_features   planning                                                      data/layer1/1A/crossborder_features/parameter_hash={parameter_hash}/            schemas.1A.yaml#/model/crossborder_features
              merchant_abort_log   approved                                     data/layer1/1A/prep/merchant_abort_log/parameter_hash={parameter_hash}/part-*.parquet               schemas.1A.yaml#/prep/merchant_abort_log
              s0_gate_receipt_1A   approved                           data/layer1/1A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt.json         schemas.1A.yaml#/validation/s0_gate_receipt_1A
                sealed_inputs_1A   approved                            data/layer1/1A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_1A.json           schemas.1A.yaml#/validation/sealed_inputs_1A
            validation_bundle_1A   approved                                                    data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/          schemas.1A.yaml#/validation/validation_bundle
      validation_bundle_index_1A   approved                                          data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/index.json schemas.1A.yaml#/validation/validation_bundle_index_1A
       validation_passed_flag_1A   approved                                        data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag            schemas.layer1.yaml#/validation/passed_flag
                   rng_audit_log   approved                  logs/layer1/1A/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl            schemas.layer1.yaml#/rng/core/rng_audit_log
                   rng_trace_log   approved                  logs/layer1/1A/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl            schemas.layer1.yaml#/rng/core/rng_trace_log
                  s4_metrics_log   approved                    logs/layer1/1A/metrics/s4/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/s4_metrics.jsonl      schemas.layer1.yaml#/observability/s4_metrics_log
                rng_event_anchor   approved                 logs/layer1/1A/rng/events/anchor/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl                 schemas.layer1.yaml#/rng/events/anchor
      rng_event_hurdle_bernoulli   approved       logs/layer1/1A/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl       schemas.layer1.yaml#/rng/events/hurdle_bernoulli
       rng_event_gamma_component   approved        logs/layer1/1A/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl        schemas.layer1.yaml#/rng/events/gamma_component
     rng_event_poisson_component   approved      logs/layer1/1A/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl      schemas.layer1.yaml#/rng/events/poisson_component
              rng_event_nb_final   approved               logs/layer1/1A/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl               schemas.layer1.yaml#/rng/events/nb_final
         rng_event_ztp_rejection   approved          logs/layer1/1A/rng/events/ztp_rejection/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl          schemas.layer1.yaml#/rng/events/ztp_rejection
   rng_event_ztp_retry_exhausted   approved    logs/layer1/1A/rng/events/ztp_retry_exhausted/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl    schemas.layer1.yaml#/rng/events/ztp_retry_exhausted
             rng_event_ztp_final   approved              logs/layer1/1A/rng/events/ztp_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl              schemas.layer1.yaml#/rng/events/ztp_final
            rng_event_gumbel_key   approved             logs/layer1/1A/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl             schemas.layer1.yaml#/rng/events/gumbel_key
rng_event_dirichlet_gamma_vector   approved logs/layer1/1A/rng/events/dirichlet_gamma_vector/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector
           rng_event_stream_jump   approved            logs/layer1/1A/rng/events/stream_jump/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl            schemas.layer1.yaml#/rng/events/stream_jump
     rng_event_normal_box_muller   approved      logs/layer1/1A/rng/events/normal_box_muller/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl      schemas.layer1.yaml#/rng/events/normal_box_muller
     rng_event_sequence_finalize   approved      logs/layer1/1A/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl      schemas.layer1.yaml#/rng/events/sequence_finalize
         rng_event_residual_rank   approved          logs/layer1/1A/rng/events/residual_rank/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl          schemas.layer1.yaml#/rng/events/residual_rank
rng_event_site_sequence_overflow   approved logs/layer1/1A/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl schemas.layer1.yaml#/rng/events/site_sequence_overflow

## 3) Presence of expected data outputs (data/layer1/1A only)
                              id     status                                                                                            path  present
       ccy_country_weights_cache   approved                       data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/     True
           s5_validation_receipt   approved     data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/S5_VALIDATION.json     True
                  s5_passed_flag   approved           data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/_passed.flag     True
               merchant_currency   approved                               data/layer1/1A/merchant_currency/parameter_hash={parameter_hash}/     True
            hurdle_design_matrix   approved                            data/layer1/1A/hurdle_design_matrix/parameter_hash={parameter_hash}/     True
                 hurdle_pi_probs   approved                                 data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/     True
                     sparse_flag   approved                                     data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/    False
   crossborder_eligibility_flags   approved                   data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/     True
                     country_set deprecated                         data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/    False
                   s6_membership   approved                       data/layer1/1A/s6/membership/seed={seed}/parameter_hash={parameter_hash}/     True
           s6_validation_receipt   approved                                  data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/     True
       ranking_residual_cache_1A deprecated           data/layer1/1A/ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/    False
                outlet_catalogue   approved        data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/     True
                s3_candidate_set   approved                                data/layer1/1A/s3_candidate_set/parameter_hash={parameter_hash}/     True
           s3_base_weight_priors   approved                           data/layer1/1A/s3_base_weight_priors/parameter_hash={parameter_hash}/     True
           s3_integerised_counts   approved                           data/layer1/1A/s3_integerised_counts/parameter_hash={parameter_hash}/    False
                s3_site_sequence   approved                                data/layer1/1A/s3_site_sequence/parameter_hash={parameter_hash}/    False
hurdle_stationarity_tests_2024Q4   approved                       data/layer1/1A/hurdle_stationarity_tests/parameter_hash={parameter_hash}/    False
            crossborder_features   planning                            data/layer1/1A/crossborder_features/parameter_hash={parameter_hash}/     True
              merchant_abort_log   approved           data/layer1/1A/prep/merchant_abort_log/parameter_hash={parameter_hash}/part-*.parquet    False
              s0_gate_receipt_1A   approved data/layer1/1A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt.json     True
                sealed_inputs_1A   approved  data/layer1/1A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_1A.json     True
            validation_bundle_1A   approved                          data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/     True
      validation_bundle_index_1A   approved                data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/index.json     True
       validation_passed_flag_1A   approved              data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag     True

## 4) Key realism metrics (computed)
                      dataset  merchants  countries  contiguous_site_order_rate  multi_country_rate  top_1pct_outlet_share  top_5pct_outlet_share  top_10pct_outlet_share  min_countries  median_countries  max_countries  min_outlets  median_outlets  max_outlets  min_candidates  median_candidates  max_candidates  max_rank_global  min_rank_global  rank_contiguous_rate prob_col      min     max     mean   median    elig_col  eligible_rate feature_col currency_col  unique_currencies min_currency max_currency  min_foreign  median_foreign  max_foreign
             outlet_catalogue     1238.0       77.0                         1.0             0.37399               0.237259               0.377483                0.461049            1.0               1.0           11.0          2.0            16.0       2546.0             NaN                NaN             NaN              NaN              NaN                   NaN     None      NaN     NaN      NaN      NaN        None            NaN        None         None                NaN         None         None          NaN             NaN          NaN
             s3_candidate_set        NaN        NaN                         NaN                 NaN                    NaN                    NaN                     NaN            NaN               NaN            NaN          NaN             NaN          NaN             1.0               38.0            39.0             38.0              0.0                   1.0     None      NaN     NaN      NaN      NaN        None            NaN        None         None                NaN         None         None          NaN             NaN          NaN
              hurdle_pi_probs        NaN        NaN                         NaN                 NaN                    NaN                    NaN                     NaN            NaN               NaN            NaN          NaN             NaN          NaN             NaN                NaN             NaN              NaN              NaN                   NaN       pi 0.000088 0.67972 0.160900 0.142137        None            NaN        None         None                NaN         None         None          NaN             NaN          NaN
crossborder_eligibility_flags        NaN        NaN                         NaN                 NaN                    NaN                    NaN                     NaN            NaN               NaN            NaN          NaN             NaN          NaN             NaN                NaN             NaN              NaN              NaN                   NaN     None      NaN     NaN      NaN      NaN is_eligible         0.7069        None         None                NaN         None         None          NaN             NaN          NaN
         crossborder_features        NaN        NaN                         NaN                 NaN                    NaN                    NaN                     NaN            NaN               NaN            NaN          NaN             NaN          NaN             NaN                NaN             NaN              NaN              NaN                   NaN     None 0.020000 0.53000 0.197606 0.190000        None            NaN    openness         None                NaN         None         None          NaN             NaN          NaN
            merchant_currency        NaN        NaN                         NaN                 NaN                    NaN                    NaN                     NaN            NaN               NaN            NaN          NaN             NaN          NaN             NaN                NaN             NaN              NaN              NaN                   NaN     None      NaN     NaN      NaN      NaN        None            NaN        None        kappa              139.0          AED          ZWG          NaN             NaN          NaN
                s6_membership        NaN        NaN                         NaN                 NaN                    NaN                    NaN                     NaN            NaN               NaN            NaN          NaN             NaN          NaN             NaN                NaN             NaN              NaN              NaN                   NaN     None      NaN     NaN      NaN      NaN        None            NaN        None         None                NaN         None         None          1.0             2.0         12.0

## 5) Interpretation (realism quality)

### Outlet structure realism
- Merchants: 1238 across 77 countries.
- Outlets per merchant: min=2, median=16.0, max=2546
- Countries per merchant: min=1, median=1.0, max=11
- Multi-country merchant rate: 0.3740
- Outlet concentration: top 1%=0.237, top 5%=0.377, top 10%=0.461
- Site order contiguity rate: 1.0000 (dense site_order from 1..N)
Interpretation: The outlet distribution is heavy-tailed (top 10% merchants hold ~46% of outlets). This is a reasonable realism signal; retail ecosystems tend to be skewed.

### Candidate set realism
- Candidate countries per merchant: min=1, median=38.0, max=39
- candidate_rank range: min_rank_global=0, max_rank_global=38
- Rank contiguity rate: 1.0000
Interpretation: Most merchants have large candidate sets (median 38 of max 39). This suggests a very broad cross-border candidate universe, which may be less realistic if most merchants are typically domestic or regional.

### Cross-border eligibility realism
- Eligibility rate: 0.7069 (fraction eligible)
Interpretation: ~70% eligibility indicates a mix of eligible and ineligible merchants. This is a reasonable realism signal if policy is meant to filter a meaningful minority.

### Hurdle probabilities realism
- Probability column: pi
- min=8.799538045423105e-05, median=0.14213722944259644, mean=0.16090011596679688, max=0.6797199249267578
Interpretation: Probabilities are in a realistic (0,1) range with a moderate spread and a median around 0.14. This indicates non-trivial variation in single vs multi-site propensity.

### Cross-border features realism
- Feature column: openness | min=0.019999999552965164, median=0.1899999976158142, mean=0.19760599732398987, max=0.5299999713897705
Interpretation: Openness appears to live in a reasonable band (0.02-0.53). This is plausible, though the upper bound may be low if you want truly global merchants.

### Merchant currency realism
- Currency column: kappa | unique currencies=139 (min=AED, max=ZWG)
Interpretation: 139 distinct currency codes is a strong realism signal for global coverage.

### Foreign membership realism (S6)
- Foreign countries per merchant: min=1, median=2.0, max=12
Interpretation: Median foreign count of 2 indicates most cross-border merchants only expand to a small number of countries. This is realistic if most merchants are regionally constrained.

## 6) Reality grade (1A only, structural realism)
Grade: **B (Moderate realism)**
Rationale: The outputs are structurally coherent and show heavy-tailed outlet distributions, multiple currencies, and non-trivial eligibility and hurdle variance. However, the candidate set breadth (median 38 countries) suggests globally permissive cross-border candidates, which may be less realistic for typical merchant populations. Several approved dictionary outputs are missing (s3_integerised_counts, s3_site_sequence, sparse_flag, merchant_abort_log, hurdle_stationarity_tests), which weakens fidelity to design intent even if some are internal or optional in practice.
