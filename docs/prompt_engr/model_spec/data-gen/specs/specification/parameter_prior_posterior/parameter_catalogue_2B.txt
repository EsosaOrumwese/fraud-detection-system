############################################################
#  PARAMETER CATALOGUE‑FINDER • Sub‑segment 2B             #
############################################################

--- PP 1 ---
Name: Routing site weight normalization (probabilities per outlet)
Symbol: $p_i = F_i / \sum_j F_j$
Scope: merchant_location
Prior_type: Deterministic function (of persisted foot-traffic weights)
Prior_specified: Yes
Calibration_recipe: No (direct calculation, fully specified)
Posterior_validation: Yes (checksum of normalized weights, manifest digest and CI assertion)
Provenance_tag: Yes (`site_catalogue_parquet`, `routing_manifest.json`, `weight_digest`)
Units: unitless (probabilities, $\sum p_i = 1$)
Default_policy: abort (RoutingZeroWeightError if $\sum_j F_j = 0$)
Interface_consumer: Router, alias-table constructor, routing audit
Description: Normalized probabilities for outlet choice per merchant, computed from immutable foot-traffic weights and persisted for all routing.
Anchor: "Each outlet’s routing weight is the *exact* foot‑traffic scalar `F_i` persisted by the placement stage. Weights are loaded from the immutable catalogue Parquet ... router computes `p_i = F_i / Σ_j F_j` using double‑precision IEEE‑754 addition in the lexicographic order of `site_id`."
Context: "Each outlet’s routing weight is the *exact* foot‑traffic scalar ... router computes `p_i = F_i / Σ_j F_j` using double‑precision IEEE‑754 addition ... The vector is written to a binary file `<merchant_id>_pweights.bin`; its SHA‑256 is recorded in `routing_manifest.json` under the key `weight_digest`."
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
Name: Alias table O(1) sampling arrays
Symbol: Arrays `prob`, `alias` from $p_i$
Scope: merchant_location
Prior_type: Deterministic function (of normalized $p_i$ vector)
Prior_specified: Yes
Calibration_recipe: No (direct algorithm, fully defined in A.2)
Posterior_validation: Yes (unit test reconstructs table, hashes, asserts identity with on-disk npz)
Provenance_tag: Yes (`alias_npz`, `alias_digest`, referenced in `routing_manifest.json`)
Units: unitless (uint32 indices and probabilities)
Default_policy: abort (CI/test fail if reconstruct/hashes do not match)
Interface_consumer: Router/sampler, O(1) outlet sampling function
Description: Arrays for Vose alias method to sample outlets in constant time per merchant, persisted as .npz artefact.
Anchor: "The alias table is generated once per merchant by the Vose algorithm ... The table is serialised as two `uint32` numpy arrays `prob` and `alias`, concatenated and written as `<merchant_id>_alias.npz` ... Unit tests reconstruct the table in memory, re‑serialise, re‑hash and assert equality, proving immutability."
Context: "Because naïve multinomial sampling in O(N) time would choke on global merchants ... constructs **an alias table** per merchant. The deterministic alias construction proceeds by streaming through the `p_i` vector ... The `.npz` file `<merchant_id>_alias.npz` is uncompressed, saved via NumPy 1.23 with named arrays `prob` and `alias`, and its digest is recorded as `alias_digest`."
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
Name: Corporate-day random effect variance
Symbol: $\sigma_\gamma^2$
Scope: merchant_location
Prior_type: LogNormal variance (governed parameter)
Prior_specified: Yes
Calibration_recipe: Yes (fit by `calibrate_gamma.ipynb` to JPM hourly counts; path in manifest/licence)
Posterior_validation: Yes (empirical correlation and share checks in validation log; value must match digests)
Provenance_tag: Yes (`routing_day_effect.yml`, `gamma_variance_digest`)
Units: variance (dimensionless)
Default_policy: use prior (fallback: default 0.15)
Interface_consumer: Router day-effect sampler; daily γ_d modulation in routing, referenced in buffer columns
Description: Variance for latent corporate-day random effect ($\log\gamma_d$); induces realistic cross-zone synchrony for promotions.
Anchor: "the routing engine introduces a **latent “corporate‑day” random effect** γ\_d drawn once per merchant per UTC day `d` via $\log\gamma_d \sim \mathcal{N}\!\bigl(-\tfrac{1}{2}\sigma_{\gamma}^2,\;\sigma_{\gamma}^2\bigr)$, with `σ_γ²` governed by `config/routing/routing_day_effect.yml` (`sigma_squared`, semver, `gamma_variance_digest`) and defaulting to 0.15."
Context: "Long‑run shares, however, are not enough; real data reveal a subtle **cross‑zone co‑movement** when a corporate promotion begins ... the routing engine introduces a **latent “corporate‑day” random effect** γ\_d ... drawn once per merchant per UTC day ... with `σ_γ²` governed by `config/routing/routing_day_effect.yml` (`sigma_squared`, semver, `gamma_variance_digest`) and defaulting to 0.15."
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
Name: Virtual merchant CDN edge country weights
Symbol: $Q = [q_1,\dots,q_K]$
Scope: merchant_location
Prior_type: Discrete weights (stationary, sum-to-one vector)
Prior_specified: Yes
Calibration_recipe: Yes (empirical fit, from Akamai State of the Internet report, CC-BY 4.0)
Posterior_validation: Yes (sum-to-one CI, audit log; digest checked on each build)
Provenance_tag: Yes (`cdn_country_weights.yaml`, `cdn_alias_digest`)
Units: unitless (probabilities per country, $\sum q_k = 1$)
Default_policy: use prior (fallback to equal weights if missing)
Interface_consumer: Router alias sampler for CDN country, `ip_country_code` in output buffer/log
Description: Probabilities for CDN edge-node country assignment in routing of purely virtual merchants.
Anchor: "If a merchant row in the catalogue carries `is_virtual=1`, physical outlet count is forced to one, but the router loads `cdn_country_weights.yaml`. For each virtual merchant the YAML gives a stationary vector `q_c` across CDN edge countries. An alias table on `q_c` is built exactly as for outlets ..."
Context: "Certain merchants flagged `is_virtual=1` receive a shadow list of edge‑node countries drawn from `config/routing/cdn_country_weights.yaml` (`semver`, `sha256_digest`, `q_c`), using the same alias‑table logic to select `ip_country`;"
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
Name: Routing validation thresholds
Symbol: $\epsilon_p$ (share), $\rho^*$ (correlation)
Scope: merchant_location
Prior_type: Fixed threshold (YAML-governed, not stochastic)
Prior_specified: Yes
Calibration_recipe: Yes (empirically chosen; governed in `routing_validation.yml`)
Posterior_validation: Yes (all merchants validated daily; CI blocks merge if failed)
Provenance_tag: Yes (`routing_validation.yml`, `validation_config_digest`)
Units: $\epsilon_p$: unitless (probability diff), $\rho^*$: unitless (correlation)
Default_policy: abort (if tolerance/target is breached)
Interface_consumer: Router validation and assertion, CI
Description: Tolerance for per-site share deviation, and target/threshold for cross-zone correlation validation in synthetic routing.
Anchor: "the harness computes ... (1) the empirical share vector ... (2) the Pearson correlation of hourly site counts across time‑zones. It asserts `|ŝ_i – p_i| < 0.01` for all `i` and `|ρ_emp – 0.35| < 0.05`. Tolerance and target reside in `routing_validation.yml` ..."
Context: "Once the full synthetic day is produced ... It asserts `|ŝ_i – p_i| < 0.01` for all `i` and `|ρ_emp – 0.35| < 0.05`. Tolerance and target reside in `routing_validation.yml`; CI blocks merges if any merchant breaches them."
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
Name: Audit batch size and checksum
Symbol: $B = 10^6$, SHA256($merchant\_id$‖$batch\_index$‖$C$)
Scope: merchant_location
Prior_type: Fixed policy constant and function
Prior_specified: Yes
Calibration_recipe: No (constant batch size and hash algorithm)
Posterior_validation: Yes (checksum computed, logged, CI reruns for determinism)
Provenance_tag: Yes (`routing_audit_log`, batch index/manifest lineage in log)
Units: $B$: count, checksum: 64-char hex
Default_policy: abort (any audit or checksum drift aborts build)
Interface_consumer: Routing audit log, nightly regression test
Description: Number of events per routing audit batch and SHA256 reproducibility hash on cumulative site counts.
Anchor: "After routing every 1 000 000 events globally, the router computes checksum = SHA256(merchant_id || batch_index || cumulative_counts_vector) ... and appends it with an ISO 8601 timestamp to `logs/routing/routing_audit.log`."
Context: "Finally, once per million routed events ... computes checksum = SHA256(merchant_id || batch_index || cumulative_counts_vector) ... appends it with an ISO 8601 timestamp to `logs/routing/routing_audit.log`."
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
Name: Routing RNG policy (seed derivation)
Symbol: $\mathrm{SHA1}(\mathtt{global\_seed}\|\text{"router"}\|\mathtt{merchant\_id})$
Scope: merchant_location
Prior_type: Deterministic (hash, not stochastic)
Prior_specified: Yes
Calibration_recipe: No (hash policy set in YAML, not calibrated)
Posterior_validation: Yes (manifest and event audit; proof in docs/rng_proof.md)
Provenance_tag: Yes (`rng_policy.yml`, `rng_proof.md`, manifest: `rng_policy_digest`)
Units: hex (128-bit Philox key)
Default_policy: abort (drift or mismatch aborts build)
Interface_consumer: Router seed/stream derivation, reproducibility proof
Description: Policy and hash function for deterministic, merchant-specific Philox PRNG key in routing.
Anchor: "Seed derivation uses Python 3.10’s `hashlib.sha1()` on `(global_seed, "router", merchant_id)` in `router/seed.py`, governed by `rng_policy.yml` (`rng_policy_digest`)."
Context: "Seed derivation uses Python 3.10’s `hashlib.sha1()` on `(global_seed, "router", merchant_id)` in `router/seed.py`, governed by `rng_policy.yml` (`rng_policy_digest`)."
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
Name: Routing performance thresholds (throughput, memory)
Symbol: $\mathrm{TP}\ (\mathrm{MB}/\mathrm{s})$, $\mathrm{Mem}\ (\mathrm{GB})$
Scope: merchant_location
Prior_type: Fixed policy threshold (YAML-governed)
Prior_specified: Yes
Calibration_recipe: Yes (thresholds loaded from `performance.yml`; enforced by CI/performance log)
Posterior_validation: Yes (build logs must show TP $\geq$ 200 MB/s, Mem $\leq$ 2 GB; deviation aborts)
Provenance_tag: Yes (`performance_config`, `perf_config_digest`)
Units: $\mathrm{TP}$: MB/s, $\mathrm{Mem}$: GB
Default_policy: abort (breach aborts build)
Interface_consumer: Router, CI, performance monitoring
Description: Throughput (MB/s) and memory (GB) performance SLA for routing batch jobs, enforced by CI and manifest contract.
Anchor: "Thresholds ($\mathrm{TP}\ge200$, $\mathrm{Mem}\le2$) are loaded from `config/routing/performance.yml`."
Context: "Thresholds ($\mathrm{TP}\ge200$, $\mathrm{Mem}\le2$) are loaded from `config/routing/performance.yml`."
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

<<PP‑END>>
