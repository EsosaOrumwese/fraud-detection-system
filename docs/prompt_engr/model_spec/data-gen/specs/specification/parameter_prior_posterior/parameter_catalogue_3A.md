############################################################
#  PARAMETER CATALOGUE‑FINDER • Sub‑segment 3A             #
############################################################

--- PP 1 ---
Name: Mixture threshold θ for escalation queue
Symbol: $\theta_{\text{mix}}$
Scope: merchant_location
Prior_type: Fixed threshold (YAML-governed, not stochastic)
Prior_specified: Yes
Calibration_recipe: No (policy parameter, not fit)
Posterior_validation: Yes (CI: test_mix_threshold.py, YAML-parquet queue identity, manifest digest)
Provenance_tag: Yes (`config/allocation/zone_mixture_policy.yml`, `theta_digest`)
Units: unitless (proportion)
Default_policy: use prior (abort if missing)
Interface_consumer: Mixture queue flagger, zone allocator, all downstream routing/zone Parquets
Description: Country-level mass threshold for determining need for internal time-zone split; governs mixture vs. monolithic zone allocation.
Anchor: "θ is loaded at runtime from `config/allocation/zone_mixture_policy.yml` (keys: `theta_mix`, `semver`, `sha256_digest`), and its SHA‑256 is recorded as `theta_digest` in the dataset manifest; the CI test `test_mix_threshold.py` byte‑compares the YAML‑driven queue to the parquet output to detect any drift."
Context: "The algorithm scans v and flags every country whose mass exceeds a tunable attention threshold θ, defaulting to 1 percent. For governance, θ is loaded at runtime from `config/allocation/zone_mixture_policy.yml`... Those flagged countries enter the *escalation queue*..."
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
--- END PP 1 ---

--- PP 2 ---
Name: Dirichlet concentration vector α (zone mixture)
Symbol: $\alpha = [\alpha_1, ..., \alpha_Z]$
Scope: merchant_location
Prior_type: Dirichlet (concentration vector, YAML-governed)
Prior_specified: Yes
Calibration_recipe: Yes (computed from two years of settlement data, scaled by τ=200, script: make_zone_alphas.py)
Posterior_validation: Yes (empirical share check, normalisation, CI YAML digest, manifest: zone_alpha_digest)
Provenance_tag: Yes (`config/allocation/country_zone_alphas.yaml`, `zone_alpha_digest`)
Units: unitless (positive integers, Dirichlet hyperparameters)
Default_policy: use prior (abort if missing; recalibrate via script)
Interface_consumer: Zone-share sampler, Gamma variate generator, LGCP zone allocation logic
Description: Dirichlet hyperparameter vector per (country, TZID) for zone-share sampling; derived from public settlement data, smoothed by global τ.
Anchor: "the engine opens the YAML ledger `country_zone_alphas.yaml`, finds the country key, and reads a concise Dirichlet concentration vector **α** that was itself computed from rolling two‑year averages of anonymised settlement counts... rescales them by a global smoothing constant τ = 200"
Context: "Each queued country now needs an internal split across its legal time‑zones. The engine opens the YAML ledger `country_zone_alphas.yaml`..."
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
--- END PP 2 ---

--- PP 3 ---
Name: Smoothing constant τ for Dirichlet vector
Symbol: $\tau$
Scope: merchant_location
Prior_type: Fixed constant (YAML, not fit)
Prior_specified: Yes
Calibration_recipe: No (value set in YAML: τ=200)
Posterior_validation: Yes (implied Dirichlet variance check, YAML/manifest locked)
Provenance_tag: Yes (`config/allocation/country_zone_alphas.yaml`, `zone_alpha_digest`)
Units: unitless
Default_policy: use prior
Interface_consumer: make_zone_alphas.py, alpha vector generator
Description: Scalar multiplying empirical zone shares to produce Dirichlet α; controls variance of allocation.
Anchor: "rescales them by a global smoothing constant τ = 200 so that the posterior variance matches what JPM’s analytics team observes in quarterly production."
Context: "the file simply rescales them by a global smoothing constant τ = 200..."
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
Name: Major zone fallback mapping (country→TZID)
Symbol: major zone per country
Scope: merchant_location
Prior_type: Deterministic (CSV, land area ranking)
Prior_specified: Yes
Calibration_recipe: Yes (area computed from frozen shapefile, CSV generated)
Posterior_validation: Yes (CSV/manifest hash, CI drift detection)
Provenance_tag: Yes (`artefacts/allocation/country_major_zone.csv`, `major_zone_digest`)
Units: TZID (string)
Default_policy: use prior (abort if missing)
Interface_consumer: Fallback allocation logic in zone allocator
Description: Assigns all outlets to single time zone if country mass below θ; zone chosen by largest land area.
Anchor: "code consults a CSV file called `artefacts/allocation/country_major_zone.csv`, created by scanning the frozen tz‑world shapefile, grouping polygons by ISO code, computing land area... choosing the `TZID` with the maximum area. The chosen zone is then assigned all outlets in that country."
Context: "The code consults a CSV file called `artefacts/allocation/country_major_zone.csv`..."
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
--- END PP 4 ---

--- PP 5 ---
Name: Zone floor vector φ_z (micro-zone protection)
Symbol: $\phi_z$
Scope: merchant_location
Prior_type: Fixed vector (YAML, positive integer per TZID)
Prior_specified: Yes
Calibration_recipe: Yes (micro-zone list, floor values set, YAML, manifest digest)
Posterior_validation: Yes (zone-floor enforcement tested in CI, log, and YAML hash)
Provenance_tag: Yes (`config/allocation/zone_floor.yml`, `zone_floor_digest`)
Units: integer (count per TZID)
Default_policy: use prior (abort if floor YAML missing)
Interface_consumer: Zone allocation post-bump-rule, floor enforcement pass
Description: Minimum number of outlets per TZID for micro-zones; enforced after integerisation and bump.
Anchor: "the engine enforces a *bump rule*... The floor definitions reside in `config/allocation/zone_floor.yml` (entries: `TZID`, `floor`, `semver`, `sha256_digest`), with its SHA‑256 recorded as `zone_floor_digest` and verified by `ci/test_zone_floor.py`"
Context: "the engine enforces a *bump rule*... The floor definitions reside in `config/allocation/zone_floor.yml`..."
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
Name: Corporate-day log-normal multiplier variance
Symbol: $\sigma_{\gamma}^{2}$
Scope: merchant_location
Prior_type: LogNormal variance (YAML-governed)
Prior_specified: Yes
Calibration_recipe: Yes (fit to cross-zone correlation, see routing_day_effect.yml, empirical check)
Posterior_validation: Yes (CI cross-zone correlation, digest, manifest: gamma_variance_digest)
Provenance_tag: Yes (`config/routing/routing_day_effect.yml`, `gamma_variance_digest`)
Units: variance (dimensionless)
Default_policy: use prior (fallback 0.15 if missing)
Interface_consumer: LGCP mean modulator, Poisson intensity, cross-zone synchrony, routing
Description: Variance for latent corporate-day multiplier γ_d, modulating all zones per merchant per day; matches observed cross-zone covariance.
Anchor: "log‑normal draw with variance σ\_γ²=0.15 does the trick; the log‑normal variance is pinned in `config/routing/routing_day_effect.yml`"
Context: "the generator instantiates a latent **corporate‑day multiplier** γ\_d for every merchant on every UTC calendar day d. A single log‑normal draw with variance σ\_γ²=0.15 does the trick; the log‑normal variance is pinned in `config/routing/routing_day_effect.yml`"
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
Name: Universe hash (cross-artifact linkage)
Symbol: $h = \mathrm{SHA256}(zone\_alpha\_digest \| theta\_digest \| zone\_floor\_digest \| gamma\_variance\_digest \| zone\_alloc\_parquet\_digest)$
Scope: merchant_location
Prior_type: Deterministic function of digests (not stochastic)
Prior_specified: Yes
Calibration_recipe: No (constructed by hash concatenation)
Posterior_validation: Yes (checked on every use, manifest/alias file, raises UniverseHashError on mismatch)
Provenance_tag: Yes (`zone_alpha_digest`, `theta_digest`, `zone_floor_digest`, `gamma_variance_digest`, `zone_alloc_parquet_digest`)
Units: 64-char hex string
Default_policy: abort (on any hash mismatch)
Interface_consumer: Routing alias tables, all allocation outputs, downstream validation and CI
Description: Cross-artifact linkage guard; ensures all routing, allocation, and daily effect use same config, allocation, and day-effect.
Anchor: "universe hash* by concatenating the manifest digests ... h = SHA256(zone_alpha_digest ∥ theta_digest ∥ zone_floor_digest ∥ gamma_variance_digest ∥ zone_alloc_parquet_digest) ... embeds `h` as `universe_hash` in each `<merchant_id>_alias.npz`"
Context: "When the router opens its per‑merchant alias table it also recomputes a *universe hash* by concatenating the manifest digests..."
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

--- PP 8 ---
Name: Barcode slope validation thresholds
Symbol: barcode_slope_low, barcode_slope_high
Scope: merchant_location
Prior_type: Fixed threshold (YAML-governed, not stochastic)
Prior_specified: Yes
Calibration_recipe: Yes (set empirically, config/validation/cross_zone_validation.yml)
Posterior_validation: Yes (barcode heatmap, Hough slope, CI/manifest digest)
Provenance_tag: Yes (`config/validation/cross_zone_validation.yml`, `cross_zone_validation_digest`)
Units: offsets per UTC hour (float)
Default_policy: abort (if threshold breached)
Interface_consumer: CI validation harness, barcode slope detection, cross-zone surges audit
Description: Validation thresholds for the minimum and maximum slope in offset-barcode detection (Hough transform) during cross-zone merchant CI.
Anchor: "A fast Hough‑transform scans the heat‑map looking for a diagonal ridge; if the slope lies outside the physically plausible –1 to –0.5 offsets‑per‑hour band, the build fails. Both thresholds live in `cross_zone_validation.yml`"
Context: "Validation closes the loop. After 30 synthetic days ... if the slope lies outside the physically plausible –1 to –0.5 offsets‑per‑hour band, the build fails. Both thresholds live in `cross_zone_validation.yml`"
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
--- END PP 8 ---

--- PP 9 ---
Name: Zone-share convergence tolerance
Symbol: share_tolerance
Scope: merchant_location
Prior_type: Fixed threshold (YAML-governed)
Prior_specified: Yes
Calibration_recipe: Yes (empirical, config/validation/cross_zone_validation.yml)
Posterior_validation: Yes (share deviation CI, manifest, logs, test output)
Provenance_tag: Yes (`config/validation/cross_zone_validation.yml`, `cross_zone_validation_digest`)
Units: unitless (absolute deviation)
Default_policy: abort (if tolerance breached)
Interface_consumer: CI validation harness, share convergence check, cross-zone merchant audit
Description: Tolerance for allowed absolute difference between empirical and target zone shares during CI share-convergence validation.
Anchor: "A second diagnostic compares empirical zone shares against integer allocations, flagging any deviation beyond two percentage points. Both thresholds live in `cross_zone_validation.yml`"
Context: "A second diagnostic compares empirical zone shares against integer allocations, flagging any deviation beyond two percentage points. Both thresholds live in `cross_zone_validation.yml`"
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
--- END PP 9 ---

--- PP 10 ---
Name: Random-stream isolation (Philox substream allocation)
Symbol: SHA256(merchant_id, country_iso)
Scope: merchant_location
Prior_type: Deterministic hash/key (not stochastic)
Prior_specified: Yes
Calibration_recipe: No (hash key per merchant/country, proven in docs/rng_proof.md)
Posterior_validation: Yes (proof checked, manifest/rng_proof_digest, property-based test suite)
Provenance_tag: Yes (`docs/rng_proof.md`, `rng_proof_digest`)
Units: 64-char hex string (Philox key)
Default_policy: abort (if proof not matched, CI fail)
Interface_consumer: Dirichlet draw/gamma sampler, all zone allocation streams
Description: Deterministic per-merchant/country substream for Dirichlet Gamma draws; proven isolation and replayability.
Anchor: "Philox sub‑stream keyed by `(merchant_id, country_iso)`... derivation is governed by `config/routing/rng_policy.yml`, and its SHA‑256 is stored as `gamma_day_key_digest` in the manifest to guarantee reproducible corporate‑day streams."
Context: "Philox sub‑stream keyed by `(merchant_id, country_iso)`... derivation is governed by `config/routing/rng_policy.yml`..."
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
--- END PP 10 ---

<<PP‑END>>