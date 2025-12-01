```
      LAYER 1 – SEGMENT 1A - STATE S2 (NB MIXTURE: TOTAL OUTLET COUNT N ≥ 2)

Authoritative inputs at S2 entry (read-only)
-------------------------------------------
[H] rng_event.hurdle_bernoulli
      path: logs/rng/events/hurdle_bernoulli/
            seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
      role:
        - gate: only merchants with is_multi = true may enter S2
        - branch purity: single-site merchants MUST have no S2 events

[X_mu], [X_phi] NB design surfaces (from S0 feature prep)
      role:
        - fixed design vectors x_mu(m), x_phi(m) per merchant
        - built deterministically from merchant_ids + GDP map + encoders
        - not a separate dataset; derived from S0.4/S0.5 universe

[B] Model coefficients
      files:
        - hurdle_coefficients.yaml         (key: beta_mu  → NB mean)
        - nb_dispersion_coefficients.yaml  (key: beta_phi → NB dispersion)
      role:
        - governed beta_mu, beta_phi vectors for NB mean/dispersion links
        - sole authority for mu_m, phi_m in S2

[K] lineage keys (from S0)
      { seed, parameter_hash, manifest_fingerprint, run_id }

[L] RNG + numeric law (from S0)
      - Philox2x64-10, open-interval U(0,1)
      - shared rng_envelope (counters, blocks, draws, module, substream_label, ts_utc, …)
      - numeric_policy.json & math_profile_manifest.json
        (binary64, RNE, FMA-off, deterministic libm, Neumaier sums)

[D] Data dictionary & schemas
      - schemas.layer1.yaml#/rng/events/gamma_component
      - schemas.layer1.yaml#/rng/events/poisson_component
      - schemas.layer1.yaml#/rng/events/nb_final
      - dataset_dictionary.layer1.1A.yaml entries:
          * rng_event_gamma_component
          * rng_event_poisson_component
          * rng_event_nb_final
        all:
          * partitioned by [seed, parameter_hash, run_id]
          * gated_by: rng_event_hurdle_bernoulli (is_multi == true)


Segment-level context (where S2 sits)
-------------------------------------

(S0) Universe, lineage, design, RNG & numeric law (no RNG draws)
    ⇒ hurdle_design_matrix, GDP/bucket features, NB design view (x_mu, x_phi)
    ⇒ crossborder_eligibility_flags (later S4/S6)
    ⇒ {seed, parameter_hash, manifest_fingerprint, run_id} + RNG/numeric contracts

(S1) Hurdle: single vs multi  [RNG-bounded]
    - Consumes: hurdle_design_matrix + hurdle_coefficients
    - Emits: rng_event.hurdle_bernoulli @ [seed, parameter_hash, run_id]
        · exactly 1 per merchant
        · is_multi flag gates all downstream 1A RNG streams

[H] + [X_mu,X_phi] + [B] + [K] + [L]
                |
                v

(S2) NB mixture → total multi-site outlets N ≥ 2  [RNG-bounded]

    Conceptual steps (per multi-site merchant):
      1) Evaluate NB links (deterministic; S2.2)
           - eta_mu  = beta_mu  · x_mu(m)
           - eta_phi = beta_phi · x_phi(m)
           - mu_m  = exp(eta_mu)   > 0   (NB mean)
           - phi_m = exp(eta_phi)  > 0   (NB dispersion)

      2) Attempt loop (Gamma + Poisson mixture; S2.3–S2.4)
           - draw G ~ Gamma(shape = phi_m, scale = 1)
                 → emit gamma_component (context="nb")
           - set lambda = (mu_m / phi_m) * G
           - draw k ~ Poisson(lambda)
                 → emit poisson_component (context="nb")
           - if k ∈ {0,1}:
                 · reject, increment nb_rejections, loop
             else:
                 · accept N_m := k (N_m ≥ 2)

      3) Finalise (non-consuming echo; S2.5)
           - emit nb_final with:
               merchant_id,
               mu           = mu_m,
               dispersion_k = phi_m,
               n_outlets    = N_m (N_m ≥ 2),
               nb_rejections (number of rejected {0,1}),
               method       = "poisson_gamma_mixture"
           - nb_final’s envelope has blocks = 0, draws = "0"
             (echo-only; proves which parameters and outcome were used)

    Outputs (persisted streams):
      -> rng_event.gamma_component
             path: logs/rng/events/gamma_component/
                   seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
             body (conceptual): merchant_id, context="nb",
                                alpha=phi_m, gamma_value

      -> rng_event.poisson_component
             path: logs/rng/events/poisson_component/
                   seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
             body (conceptual): merchant_id, context="nb",
                                lambda=lambda_m, k, attempt

      -> rng_event.nb_final  (non-consuming final echo)
             path: logs/rng/events/nb_final/
                   seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
             body: merchant_id, mu, dispersion_k,
                   n_outlets (N_m ≥ 2), nb_rejections, method


Downstream touchpoints (who depends on S2)
------------------------------------------
- S3 - Candidate universe & order (deterministic):
    · reads nb_final to obtain N_m per multi-site merchant

- S4 - ZTP foreign K_target (logs only):
    · uses N_m to parameterise lambda_extra (how many foreign countries we target)

- S7 / S8 - Allocation & outlet_catalogue:
    · S7/S8 must respect N_m as the total outlet count for the merchant
      when splitting across countries and materialising stubs

- S9 - Validation / replay:
    · replays NB2 parameters from (x_mu, x_phi, beta_mu, beta_phi)
    · verifies:
         * each multi-site merchant has exactly one nb_final
         * gamma_component + poisson_component budgets match RNG trace
         * nb_final.mu and nb_final.dispersion_k echo S2.2’s mu_m, phi_m
         * reconstructed N_m / nb_rejections match logged values

Legend
------
(Sx)           = state
[name]         = dataset or artefact
@[keys]        = partition keys
[RNG-bounded]  = state that consumes RNG; events logged under [seed, parameter_hash, run_id]
mu_m           = NB mean (expected outlet count)
phi_m          = NB dispersion (controls over-dispersion; Var(N) ≈ mu_m + mu_m^2 / phi_m)
```

