############################################################
#  PARAMETER CATALOGUE‑FINDER • Sub‑segment 1B             #
############################################################

--- PP 1 ---
Name: Spatial prior blend coefficients
Symbol: $\alpha_k$, for $k = 1, ..., K$ (blend vector for each prior blend)
Scope: merchant_location
Prior_type: Convex combination (weights on spatial priors, deterministic sum-to-one vector)
Prior_specified: Yes
Calibration_recipe: Partial (manual/configurable, must sum to 1 within $1\times10^{-9}$, changes require semver bump and propagate to manifest digest)
Posterior_validation: Partial (CI checks for sum-to-one, semver, and coefficient drift; but no empirical spatial plausibility test)
Provenance_tag: Yes (`spatial_blend.yaml`, semver, sha256_digest)
Units: dimensionless (each $\alpha_k \geq 0$)
Default_policy: abort (build aborts if not sum-to-one or on illegal change)
Interface_consumer: Blended prior raster construction for site placement (importance sampler, Fenwick tree construction)
Description: Weights for convex combination of spatial priors (e.g. population, roads) per (MCC, channel), governing spatial sampling.
Anchor: "The blend coefficients live in `spatial_blend.yaml`; a reviewer can change a coefficient and regenerate a new catalogue to test sensitivity. `spatial_blend.yaml` is a governed artefact carrying `semver` and a SHA‑256 digest; weight vectors are stored in canonical lexicographic order of `prior_id` and must sum to 1 within 1×10⁻⁹ or CI fails; any coefficient change requires a semver bump."
Context: "For big-box categories the prior is a blended raster ... blend is constructed ... blend coefficients live in `spatial_blend.yaml`; a reviewer can change a coefficient ... test sensitivity."
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
--- END PP 1 ---

--- PP 2 ---
Name: Fenwick tree integer scaling factor
Symbol: $S$
Scope: merchant_location
Prior_type: Deterministic scaling (function of weight vector; not stochastic)
Prior_specified: Yes
Calibration_recipe: No (computed directly)
Posterior_validation: Yes (log events for all build steps, range validation, overflow check)
Provenance_tag: Partial (calculated per Fenwick build, logged, not in artefact)
Units: dimensionless (used to scale float weights to uint64)
Default_policy: abort (if overflow or mismatch, build aborts)
Interface_consumer: Fenwick tree construction for spatial importance sampling
Description: Converts float prior weights into scaled integers for efficient and exact Fenwick tree sampling; ensures deterministic sampling and O(log n) search.
Anchor: "Float weights are scaled to uint64 deterministically: let W_f = Σ w_i; S = (2^64−1 − n)/W_f; store w_i' = max(1, floor(w_i × S)) ensuring every positive w_i has at least unit mass; cumulative sums are little-endian and never overflow by construction"
Context: "Fenwick trees are built eagerly the first time any site in a country references a given prior: a double‑checked lock guards construction ... Float weights are scaled to uint64 deterministically ... cumulative sums are little‑endian and never overflow by construction."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=Y
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 2 ---

--- PP 3 ---
Name: AADT floor for road segment weights
Symbol: $\underline{A}$
Scope: merchant_location
Prior_type: Fixed floor constant
Prior_specified: Yes
Calibration_recipe: No (fixed at 500 vehicles/day)
Posterior_validation: Yes (policy is versioned and changes trigger semver bump, referenced in artefact digest)
Provenance_tag: Yes (`footfall_coefficients.yaml`)
Units: vehicles/day
Default_policy: use prior (always use floor if AADT missing or too low)
Interface_consumer: Road segment feature weight calculation in road prior for spatial sampling
Description: Minimum value for AADT when calculating road segment weight, ensuring sparse roads retain positive sampling mass.
Anchor: "AADT values are floored at 500 vehicles/day before multiplication to avoid zero-weight segments and retain sparse rural roads in sampling; units are vehicles per day"
Context: "If the prior is a vector layer instead of a raster, the engine ... for roads ... (AADT values are floored at 500 vehicles/day before multiplication ... units are vehicles per day)"
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
--- END PP 3 ---

--- PP 4 ---
Name: Fallback policy thresholds for prior support
Symbol: `global_threshold`, `per_mcc_overrides`
Scope: merchant_location
Prior_type: Deterministic (YAML policy)
Prior_specified: Yes
Calibration_recipe: No (policy configuration, not fitted)
Posterior_validation: Yes (CI checks fallback rate, triggers threshold justification if changed)
Provenance_tag: Yes (`fallback_policy.yml`, semver, sha256_digest)
Units: fallback rate (proportion, dimensionless)
Default_policy: abort if threshold exceeded or policy missing
Interface_consumer: Fallback logic in site sampling for missing/zero-support priors
Description: Policy threshold for global fallback rate and optional MCC overrides; governs when fallback is allowed and when build must abort.
Anchor: "Fallback inserts prior_tag='FALLBACK_POP' and sets fallback_reason in {missing_prior, zero_support, empty_vector_after_filter}. fallback_policy.yml (semver, sha256) specifies global_threshold and optional per_mcc_overrides; CI validates (a) thresholds non‑decreasing vs previous, (b) any raise includes justification text"
Context: "Edge cases arise when a country is so small—or an MCC so specialised—that the chosen prior has zero support ... Fallback raster provenance: WorldPop ... fallback_policy.yml ... specifies global_threshold and optional per_mcc_overrides; CI validates ... "
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=Y
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 4 ---

--- PP 5 ---
Name: Footfall log-normal noise and scaling coefficients
Symbol: $\kappa_{g,h}$ (scaling), $\sigma_{g,h}$ (log-normal std), $\epsilon \sim \mathcal{N}(0, \sigma^2_{g,h})$
Scope: merchant_location
Prior_type: Scaling: fixed; $\sigma_{g,h}$: calibrated log-normal noise (prior is $\mathcal{N}(0, \sigma^2)$); $\epsilon$: site draw
Prior_specified: Partial (scaling may be fixed, $\sigma_{g,h}$ is calibrated)
Calibration_recipe: Yes (calibrated for Fano target via 10M-row synthetic slice; Brent’s method)
Posterior_validation: Yes (Fano factor, variance/mean check, tolerance, convergence stats logged)
Provenance_tag: Yes (`footfall_coefficients.yaml`, calibration_slice_config.yml)
Units: footfall: dimensionless (proxy for annual throughput), $\sigma$: log-units, $\epsilon$: log-units
Default_policy: use prior (always apply for each site, abort on missing)
Interface_consumer: Footfall calculation for each placed site (footfall field in site catalogue)
Description: Scaling and log-normal noise parameters for annual footfall estimate per site, stratified by MCC and channel; sets micro-level throughput for simulation.
Anchor: "Footfall formula: footfall = κ_(mcc,channel) × prior_weight_raw × exp(ε), ε ~ N(0, σ_(mcc,channel)^2) ... Both κ and σ stored in `footfall_coefficients.yaml` ... Calibration specification: synthetic slice size = 10,000,000 ... Fano target 1.80 ... Brent bracket [0.05, 2.0]; tolerance 1e−4 ... convergence stats embedded."
Context: "Finally, the foot-traffic scalar is computed ... engine multiplies a category-specific load factor κ (read from `footfall_coefficients.yaml`) with the raw blended float weight ... then with a Log-Normal residual ... Calibration uses a governed 10 million-row synthetic slice ... Brent’s method searches σ in [0.05, 2.0] until |Fano_sim − Fano_target|<1 × 10⁻⁴ (target Fano 1.80); resulting κ, σ and convergence stats enter `footfall_coefficients.yaml`."
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
--- END PP 5 ---

--- PP 6 ---
Name: Winsorisation policy parameters
Symbol: $M$ (clip multiple), $N_{\min}$ (minimum sites for clipping)
Scope: merchant_location
Prior_type: Deterministic (policy config)
Prior_specified: Yes
Calibration_recipe: No (policy fixed in YAML)
Posterior_validation: Yes (CI checks for $M \geq 1$ and $N_{\min} \geq 1$, semver and drift, clipping stats logged)
Provenance_tag: Yes (`winsor.yml`, semver, sha256_digest)
Units: $M$: dimensionless (multiples of $\sigma$), $N_{\min}$: count (sites)
Default_policy: use prior (policy always applied)
Interface_consumer: Clipping logic for log footfall in site catalogue, after placement and noise
Description: Outlier control policy for log-footfall per (country, MCC); governs how much deviation from mean is clipped and at what sample size threshold.
Anchor: "Means and standard deviations (μ, σ) of log footfall used for clipping are computed ... two-pass procedure ... the clipping multiple (3) and minimum stratum size (30) are governed in winsor.yml (semver, sha256)."
Context: "Means and standard deviations (μ, σ) of log footfall used for clipping ... two-pass procedure ... the clipping multiple (3) and minimum stratum size (30) are governed in winsor.yml (semver, sha256)."
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
--- END PP 6 ---

--- PP 7 ---
Name: Philox PRNG stream partition keys and stride mapping
Symbol: substream keys: `site_sampling`, `polygon_interior`, `footfall_lognormal`, `fenwick_tie_break`, `tz_resample`; stride(key) = lower_64_bits_le(SHA256(key))
Scope: merchant_location
Prior_type: Deterministic (RNG partitioning; no stochastic parameter)
Prior_specified: Yes
Calibration_recipe: Not applicable
Posterior_validation: Yes (every draw/event is auditable, full replay)
Provenance_tag: Yes (manifest, artefact digests, logged stride per event)
Units: key: string; stride: uint64
Default_policy: abort (CI asserts uniqueness of each key and stride, any change aborts build)
Interface_consumer: Every stochastic process and audit log in spatial sampling, placement, footfall, resampling, Fenwick
Description: Mapping from string keys to unique 64-bit strides for Philox PRNG substreams, ensuring deterministic, non-overlapping streams for every stochastic branch.
Anchor: "All spatial sub‑streams derive 64‑bit stride values as the lower little‑endian half of SHA‑256(key_string); SHA‑1 is not used; each stride is unique across modules (`site_sampling`, `polygon_interior`, `footfall_lognormal`, `fenwick_tie_break`, `tz_resample`). Jumping ahead means adding the unsigned 128‑bit stride to the current Philox counter (no leapfrog); uniqueness of strides plus monotonic addition guarantees non‑overlap of generated sub‑streams; stride collisions are asserted absent by CI."
Context: "Every randomness source emits an audit event: ... All spatial sub‑streams derive 64‑bit stride values ... uniqueness of strides plus monotonic addition guarantees non-overlap ... stride collisions are asserted absent by CI."
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
