############################################################
#  PARAMETER CATALOGUE‑FINDER • Sub‑segment 1A             #
############################################################

--- PP 1 ---
Name: Hurdle logistic regression coefficients
Symbol: $\beta$ (vector: $\beta_0, \beta_{\text{mcc}}, \beta_{\text{channel}}, \beta_{\text{dev}}$)
Scope: merchant_location
Prior_type: Unknown (fitted, not stated as Bayesian prior)
Prior_specified: No
Calibration_recipe: No
Posterior_validation: Partial (stationarity test, but metric and range not fully specified)
Provenance_tag: Yes (hurdle_coefficients.yaml, semver, sha256_digest, estimation_window, stationarity_test_digest)
Units: Dimensionless (applies to log-odds)
Default_policy: abort
Interface_consumer: Hurdle branch decision (single-site vs. multi-site logic in merchant-location realism; direct consumer is the site count allocation pipeline)
Description: Vector of coefficients determining the probability a merchant is multi-site based on merchant category, channel, and GDP development bucket.
Anchor: "this single vector already contains a coefficient for every predictor in the hurdle design matrix—including the five GDP‑development bucket dummies—so no separate parameter symbol (e.g. a standalone `γ_{dev}` file or term) exists; all hurdle logistic coefficients are co‑located in `hurdle_coefficients.yaml` and loaded atomically."
Context: "The build process begins with a tight handshake ... every predictor in the hurdle design matrix—including the five GDP‑development bucket dummies—so no separate parameter symbol (e.g. a standalone `γ_{dev}` file or term) exists; all hurdle logistic coefficients are co‑located in `hurdle_coefficients.yaml` and loaded atomically. ... downstream readers reject mismatching manifests at open time."
Gap_flags:
  prior_missing=Y
  hyperparams_missing=Y
  calibration_missing=Y
  posterior_missing=Y
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 1 ---

--- PP 2 ---
Name: Negative binomial mean and dispersion coefficients
Symbol: $\alpha_0$, $\alpha_{\text{mcc}}$, $\alpha_{\text{channel}}$ (mean link); $\delta_0$, $\delta_{\text{mcc}}$, $\delta_{\text{channel}}$, $\eta$ (dispersion link)
Scope: merchant_location
Prior_type: Unknown (MLE fit, not stated as Bayesian prior)
Prior_specified: No
Calibration_recipe: No
Posterior_validation: Partial (stationarity and drift tests on parameters, corridor for rejection rates)
Provenance_tag: Yes (nb_dispersion_coefficients.yaml, semver, sha256_digest; diagnostic_metrics.parquet)
Units: mean and dispersion (log-outlet counts); $\eta$ is per log(GDPpc), dimensionless
Default_policy: abort
Interface_consumer: Multi-site outlet count allocation (after hurdle); used for Poisson–Gamma NB draws
Description: Mean and dispersion regression coefficients for negative binomial distribution generating multi-site outlet counts; includes GDP-driven heteroskedasticity.
Anchor: "mean log-link (μ): intercept + MCC dummies + channel dummies. Dispersion log-link (φ): same categorical set + continuous log(GDPpc) ... η > 0 enforced (profile likelihood); typical fitted η ∈ [0.15, 0.35]"
Context: "For every merchant declared multi-site ... The mean log-link intentionally excludes the developmental (GDP bucket) factor present in the hurdle logistic ... dispersion log-link reuses those categorical components and appends a continuous natural log(GDP per capita in constant 2015 USD) term with positive coefficient η constrained during estimation."
Gap_flags:
  prior_missing=Y
  hyperparams_missing=Y
  calibration_missing=Y
  posterior_missing=Y
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 2 ---

--- PP 3 ---
Name: Zero-truncated Poisson (ZTP) cross-border expansion parameters
Symbol: $\lambda_{\text{extra}}$, $\theta_0$, $\theta_1$
Scope: merchant_location
Prior_type: Linear link on log N, parameters fitted; prior not stated
Prior_specified: No
Calibration_recipe: No
Posterior_validation: Yes (Wald p-value < 1e-5, corridor for mean and p99.9 ZTP rejections)
Provenance_tag: Yes (crossborder_hyperparams.yaml, theta1_stats; referenced in stationarity_diagnostics.parquet)
Units: $\lambda_{\text{extra}}$ dimensionless (Poisson mean); $\theta_1$ is per log(outlet count)
Default_policy: abort (cap 64, abort if exceeded)
Interface_consumer: Cross-border country count allocation branch in merchant-location realism layer
Description: Parameters for Poisson mean $\lambda_{\text{extra}}$ determining the number of foreign countries for cross-border chains; $\theta_0$ and $\theta_1$ control the linear model in log N.
Anchor: "Zero‑truncated Poisson for Foreign Country Count ... K ~ ZTPoisson(λ_extra) with λ_extra = θ₀ + θ₁ log N (θ₁ < 1, Wald p-value < 1e−5; stored as `theta1_stats`)."
Context: "Geographic sprawl is the random variable K (count of foreign countries). For merchants entering the cross-border branch it samples a true zero-truncated Poisson, K ∼ ZTPoisson(λ_extra) with λ_extra = θ₀ + θ₁ log N, θ-hyperparameters from crossborder_hyperparams.yaml (digest recorded, theta1_stats includes Wald p-value < 1e-5 and confidence interval establishing sub-linearity)."
Gap_flags:
  prior_missing=Y
  hyperparams_missing=N
  calibration_missing=Y
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 3 ---

--- PP 4 ---
Name: Dirichlet concentration parameters for outlet allocation
Symbol: $\alpha_i$
Scope: merchant_location
Prior_type: Dirichlet (parameterised by hyperparameters in crossborder_hyperparams.yaml)
Prior_specified: Yes
Calibration_recipe: No (source or estimation procedure not specified)
Posterior_validation: Partial (rounded allocation error bounded; empirical report, but no explicit test metric/acceptance range)
Provenance_tag: Yes (crossborder_hyperparams.yaml, alpha_digest)
Units: dimensionless (each $\alpha_i > 0$)
Default_policy: use prior (fallback to equal split if sparse)
Interface_consumer: Country allocation of outlets (after cross-border country selection; used by Dirichlet allocation branch)
Description: Dirichlet concentration vector controlling relative allocation of outlets across home and selected foreign countries for each merchant.
Anchor: "The code loads the α‑vector for (home_country, mcc_code, channel) from crossborder_hyperparams.yaml; α has length K+1. A single Dirichlet(α) draw is produced via independent Gamma(α_i,1) ... raw gamma deviates and the normalised weights w_i (rounded to 8 decimal places) are logged (event_type=dirichlet_gamma_vector)."
Context: "The ordered country_set is thus length K+1: the home ISO first, followed by the K foreign ISO codes in the exact order selected. The code loads the α‑vector for (home_country, mcc_code, channel) from crossborder_hyperparams.yaml; α has length K+1."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=Y
  posterior_missing=Y
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 4 ---

--- PP 5 ---
Name: Additive Dirichlet smoothing alpha
Symbol: $\alpha=0.5$
Scope: merchant_location
Prior_type: Dirichlet smoothing, fixed value
Prior_specified: Yes
Calibration_recipe: No (fixed at 0.5)
Posterior_validation: No (smoothing effect not tested or monitored)
Provenance_tag: Partial (applied in logic, not in artefact)
Units: dimensionless
Default_policy: use prior (always applied to small count cases)
Interface_consumer: Currency→country proportional expansion logic in country allocation
Description: Fixed additive smoothing parameter for sparse intra-currency country split tables, ensuring no country receives zero weight.
Anchor: "Apply additive Dirichlet smoothing α=0.5 to per-destination counts. If any destination count <30, smoothed value used; if total post-smoothing mass insufficient ... fall back to equal split (flag sparse_flag=true)."
Context: "Settlement share vector s^(ccy) at currency level; multi-country currency expansion: 1. Load intra-currency proportional weights (and observation counts). 2. Apply additive Dirichlet smoothing α=0.5 to per-destination counts. 3. If any destination count <30, smoothed value used ..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=Y
  posterior_missing=Y
  provenance_missing=Y
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 5 ---

--- PP 6 ---
Name: GDP bucket mapping
Symbol: 5 Jenks buckets (indices 1–5)
Scope: merchant_location
Prior_type: Jenks natural breaks (nonparametric, deterministic)
Prior_specified: Yes
Calibration_recipe: Yes (uses World Bank GDP per capita data, mapping path and vintage are fixed)
Posterior_validation: Partial (stationarity test, rolling Wald test; no direct distributional validation on mapping)
Provenance_tag: Yes (artefacts/gdp/gdp_bucket_map_2024.parquet, gdp_bucket_map_digest, gdp_bucket_map_semver)
Units: constant USD (2015 base), categorical bucket
Default_policy: use prior (mapping is frozen)
Interface_consumer: Used in merchant design matrix for GDP developmental factor in hurdle logistic
Description: Mapping table and bucket indices for discretizing GDP per capita by home country; used to assign development status in merchant logistic model.
Anchor: "GDP per capita is looked up in the World‑Bank data vintage released on 2025‑04‑15 and frozen by SHA‑256; subsequent updates never alter historical runs because the artefact path embeds that release date. It is discretised into five buckets using Jenks natural breaks; the mapping table lives at artefacts/gdp/gdp_bucket_map_2024.parquet with its own digest (gdp_bucket_map_digest) and semantic version so reviewers can rerun the binning step on a later vintage."
Context: "For each merchant the hurdle logistic uses ... a developmental (GDP bucket) categorical derived from the merchant’s registered home country GDP per capita. GDP per capita is looked up in the World‑Bank data vintage released on 2025‑04‑15 and frozen by SHA‑256; subsequent updates never alter historical runs because the artefact path embeds that release date. It is discretised into five buckets using Jenks natural breaks ..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=Y
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 6 ---

--- PP 7 ---
Name: NB and ZTP Poisson/Gamma/Dirichlet RNG seeds and stream jump strides
Symbol: "Philox 2^128 master seed" / sub-stream jump strides
Scope: merchant_location
Prior_type: Deterministic (parameter hash + manifest fingerprint)
Prior_specified: Yes
Calibration_recipe: Not applicable (purely for reproducibility, not statistical estimation)
Posterior_validation: Yes (replay audit log, validation must reconstruct sequence exactly)
Provenance_tag: Yes (parameter hash, manifest_fingerprint, SHA-256 digests, embedded in every output row)
Units: seed (uint128), stride (uint64), dimensionless
Default_policy: abort (if mismatch, aborts build or downstream processing)
Interface_consumer: All stochastic draw logic, audit/replay, validation scripts
Description: PRNG seeding and stream jump calculation for full determinism and auditability of every stochastic draw and branch; covers NB, ZTP, Dirichlet, Gumbel, etc.
Anchor: "The fingerprint is written to (a) the top-level _manifest.json, (b) every Parquet file’s comment field, and (c) the RNG master-seed derivation string, so that any artefact changed without a version bump becomes instantly visible—downstream readers reject mismatching manifests at open time."
Context: "The build process begins with a tight handshake between code and data: the pipeline enumerates every artefact bundle ... computes a SHA‑256 digest; it then XOR-reduces all those digests together with the git commit hash and a combined parameter hash (XOR of coefficient/hyperparameter YAML digests then SHA‑256) to yield a single 256‑bit manifest fingerprint. That fingerprint is written to (a) the top-level _manifest.json, (b) every Parquet file’s comment field, and (c) the RNG master-seed derivation string ... Any artefact changed without a version bump becomes instantly visible—downstream readers reject mismatching manifests at open time."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 7 ---

<<PP‑END>>