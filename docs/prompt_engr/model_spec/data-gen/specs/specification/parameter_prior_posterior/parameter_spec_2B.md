############################################################
#  PARAMETER SPEC‑WRITER • Sub‑segment 2B                   #
############################################################


<<<PP‑FIX id=1>
Name: Routing site weight normalization (probabilities per outlet)
Symbol: $p_i = F_i / \sum_j F_j$
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic normalization (no stochastic prior)
hyperparameters:
foot-traffic weights: $F_i$ (as computed in site catalogue)
units: unitless (probabilities)
default_policy: abort (if sum zero, RoutingZeroWeightError)
justification: Normalization ensures sampling mass is correctly assigned per outlet; required for reproducible, unbiased routing.
CALIBRATION_RECIPE:
input_path: site_catalogue_parquet
objective: not applicable (no stochastic fit; direct calculation)
algorithm: direct sum and normalization
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see routing_manifest.json: weight_digest)
INTERFACE_CONSUMER:
artefact_name: site_catalogue_parquet, routing_manifest.json
function: Feeds router and alias table construction for all merchants; persists normalized weights per merchant
description: Ensures all routing/sampling logic is driven by immutable, normalized foot-traffic weights per outlet.
POSTERIOR_VALIDATION:
metric: checksum, manifest digest, CI assertion
acceptance_range: $\sum_i p_i = 1 \pm 1e-12$; all batch checksums match manifest
sample_size: all merchants per build
PROVENANCE_TAG:
artefact_name: routing_manifest.json
sha256: (see key: weight_digest)
SHORT_DESCRIPTION:
Normalized outlet choice probabilities per merchant for routing and sampling.
TEST_PATHWAY:
test: CI replay, checksum validation, sampling test
input: routing_manifest.json, site catalogue, pweights.bin
assert: All checksums and sums match, no zero-weight abort
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=2>
Name: Alias table O(1) sampling arrays
Symbol: Arrays `prob`, `alias` from $p_i$
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic function of normalized $p_i$ vector (Vose alias)
hyperparameters:
prob: array of threshold probabilities ($p_i$ transformed)
alias: array of indices (uint32) as per Vose method
units: uint32 indices, probabilities (unitless)
default_policy: abort (if CI/test fail, reconstruct mismatch, or alias_digest drift)
justification: Enables exact, O(1) multinomial sampling over outlets, required for high-throughput, reproducible event generation.
CALIBRATION_RECIPE:
input_path: alias_npz (per-merchant .npz files)
objective: not applicable (fully deterministic, not fitted)
algorithm: Vose alias method (see A.2)
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see routing_manifest.json: alias_digest)
INTERFACE_CONSUMER:
artefact_name: alias_npz, routing_manifest.json
function: Supplies sampler for router’s event generator; direct interface for O(1) draw
description: Used by routing pipeline to sample outlet per event in O(1), proven by on-disk hash and CI test.
POSTERIOR_VALIDATION:
metric: unit test, hash check, reconstruct assertion
acceptance_range: exact bytewise match to on-disk alias_npz, hash equality
sample_size: all merchants per build
PROVENANCE_TAG:
artefact_name: alias_npz, routing_manifest.json
sha256: (see alias_digest)
SHORT_DESCRIPTION:
Alias arrays for O(1) multinomial sampling of outlets by merchant.
TEST_PATHWAY:
test: unit test, reconstruct alias, CI replay
input: alias_npz file, routing_manifest.json
assert: In-memory alias equals on-disk, hash match
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=3>
Name: Corporate-day random effect variance
Symbol: $\sigma_\gamma^2$
Scope: merchant_location
---------------------------------

PRIOR:
type: LogNormal variance (latent random effect)
hyperparameters:
$\sigma_\gamma^2$: governed value (default 0.15, see routing_day_effect.yml)
units: variance (dimensionless)
default_policy: use prior (fallback to 0.15 if YAML missing)
justification: Governs magnitude of corporate-day synchrony in routing; calibrated for cross-zone co-movement.
CALIBRATION_RECIPE:
input_path: routing_day_effect.yml, calibrate_gamma.ipynb
objective: Fit to empirical JPM hourly shares (cross-zone synchrony)
algorithm: see calibrate_gamma.ipynb (empirical moment matching)
random_seed: CALIB_SEED
convergence_tol: $1e-4$ or as set in notebook
script_digest: (see gamma_variance_digest)
INTERFACE_CONSUMER:
artefact_name: routing_day_effect.yml
function: Feeds lognormal draw per merchant, per day, in router event pipeline
description: Draws latent log-normal effect for all events on a given merchant/UTC day, modulating counts.
POSTERIOR_VALIDATION:
metric: empirical cross-zone correlation, share error
acceptance_range: see routing_validation.yml (corr ±0.05, share error <0.01)
sample_size: all days/merchants in validation
PROVENANCE_TAG:
artefact_name: routing_day_effect.yml
sha256: (see gamma_variance_digest)
SHORT_DESCRIPTION:
Variance of latent log-normal effect for daily routing synchrony.
TEST_PATHWAY:
test: calibration/validation log, share/correlation test
input: synthetic hourly data, validation config
assert: All share/corr within acceptance, digest matches
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=4>
Name: Virtual merchant CDN edge country weights
Symbol: $Q = [q_1,\dots,q_K]$
Scope: merchant_location
---------------------------------

PRIOR:
type: Discrete weights (sum-to-one vector)
hyperparameters:
$q_k$: stationary probability per edge country, $\sum q_k=1$
units: unitless (probabilities)
default_policy: use prior (fallback: uniform if missing)
justification: Governs probability of virtual merchant being routed to CDN edge country; empirically derived.
CALIBRATION_RECIPE:
input_path: cdn_country_weights.yaml (Akamaized, CC-BY 4.0)
objective: Empirical fit to global CDN traffic shares
algorithm: empirical average (proportional allocation)
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see cdn_alias_digest)
INTERFACE_CONSUMER:
artefact_name: cdn_country_weights.yaml
function: Used in router alias sampler for edge node selection
description: Probabilities loaded and converted to alias table for virtual merchant routing.
POSTERIOR_VALIDATION:
metric: sum-to-one CI check, audit log digest
acceptance_range: $\sum_k q_k = 1 \pm 1e-12$
sample_size: all virtual merchants per build
PROVENANCE_TAG:
artefact_name: cdn_country_weights.yaml
sha256: (see cdn_alias_digest)
SHORT_DESCRIPTION:
Stationary vector of CDN edge country probabilities for virtual merchant routing.
TEST_PATHWAY:
test: sum check, audit log replay
input: cdn_country_weights.yaml, log
assert: All weights sum to one; hash matches
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=5>
Name: Routing validation thresholds
Symbol: $\epsilon_p$ (share), $\rho^*$ (correlation)
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed thresholds (YAML-governed)
hyperparameters:
$\epsilon_p$: 0.01 (share tolerance)
$\rho^*$: 0.35 (target correlation, ±0.05 acceptance)
units: $\epsilon_p$: unitless; $\rho^*$: unitless
default_policy: abort (merge blocked on validation fail)
justification: Ensures synthetic routing matches target empirical shares and cross-zone correlations; blocks CI/merge on failure.
CALIBRATION_RECIPE:
input_path: routing_validation.yml
objective: Empirical, set by observed validation performance
algorithm: empirical comparison (threshold assertion)
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see validation_config_digest)
INTERFACE_CONSUMER:
artefact_name: routing_validation.yml
function: Consumed by router validation and assertion engine; used to check all merchant routing outcomes
description: Sets hard tolerance/target for share and correlation deviation in synthetic routing, enforced by CI.
POSTERIOR_VALIDATION:
metric: $|ŝ_i – p_i| < \epsilon_p$ for all $i$, $|\rho_{emp} – \rho^*| < 0.05$
acceptance_range: as above, CI blocks merge on any breach
sample_size: all merchants and sites per build
PROVENANCE_TAG:
artefact_name: routing_validation.yml
sha256: (see validation_config_digest)
SHORT_DESCRIPTION:
Thresholds and targets for daily routing share/correlation validation.
TEST_PATHWAY:
test: routing validation script, CI run
input: synthetic output, site shares, hourly counts
assert: All checks pass or merge is blocked
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=6>
Name: Audit batch size and checksum
Symbol: $B = 10^6$, SHA256($merchant\_id$‖$batch\_index$‖$C$)
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed policy constant and deterministic hash function
hyperparameters:
$B$: 1,000,000
checksum: SHA256(merchant_id || batch_index || cumulative_counts_vector)
units: $B$: count; checksum: 64-char hex
default_policy: abort (drift aborts build)
justification: Batching controls log granularity and reproducibility; hash proves deterministic event stream.
CALIBRATION_RECIPE:
input_path: routing_audit_log
objective: not applicable (constant and algorithmic)
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: not applicable
INTERFACE_CONSUMER:
artefact_name: routing_audit_log
function: Consumed by nightly audit log regression tests, manifest lineage
description: Audit and checksum logic for every routing batch, verifying no drift or nondeterminism.
POSTERIOR_VALIDATION:
metric: audit replay, hash match, batch index check
acceptance_range: full match; no drift in audit log
sample_size: all events, all merchants, all batches
PROVENANCE_TAG:
artefact_name: routing_audit_log
sha256: (see audit batch/manifest lineage)
SHORT_DESCRIPTION:
Batch size and checksum for deterministic, reproducible routing audit and drift-proofing.
TEST_PATHWAY:
test: nightly audit log replay
input: routing_audit_log, manifest
assert: All batches/checksums match or fail build
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=7>
Name: Routing RNG policy (seed derivation)
Symbol: $\mathrm{SHA1}(\mathtt{global\_seed}\|\text{"router"}\|\mathtt{merchant\_id})$
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic hash-based PRNG key derivation
hyperparameters:
global_seed: 128-bit hex
router: string constant
merchant_id: string
units: hex (Philox 128-bit key)
default_policy: abort (drift or mismatch aborts build)
justification: Provides deterministic, reproducible seed for each merchant’s router event stream.
CALIBRATION_RECIPE:
input_path: rng_policy.yml, rng_proof.md
objective: not applicable
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see rng_policy_digest)
INTERFACE_CONSUMER:
artefact_name: rng_policy.yml, rng_proof.md
function: Feeds router’s PRNG key/stream derivation for sampling, reproducibility, and audit replay
description: All routing streams keyed and partitioned by this deterministic policy; prevents collisions and drift.
POSTERIOR_VALIDATION:
metric: CI audit, replay, proof hash match
acceptance_range: key matches manifest and replay hash
sample_size: all merchants per build
PROVENANCE_TAG:
artefact_name: rng_policy.yml, rng_proof.md
sha256: (see rng_policy_digest)
SHORT_DESCRIPTION:
Policy and algorithm for merchant-specific Philox PRNG stream in routing.
TEST_PATHWAY:
test: audit replay, manifest proof, CI run
input: routing log, manifest, proof
assert: All PRNG keys match and no drift in audit
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=8>
Name: Routing performance thresholds (throughput, memory)
Symbol: $\mathrm{TP}\ (\mathrm{MB}/\mathrm{s})$, $\mathrm{Mem}\ (\mathrm{GB})$
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed performance threshold (YAML-governed)
hyperparameters:
throughput_MBps: 200
memory_GB: 2
units: MB/s, GB
default_policy: abort (if breached)
justification: Performance SLAs for routing pipeline; enforced by CI/build logs and contract
CALIBRATION_RECIPE:
input_path: performance.yml
objective: not applicable (policy only)
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see perf_config_digest)
INTERFACE_CONSUMER:
artefact_name: performance.yml
function: Consumed by router and CI monitoring script; sets min/max allowed runtime performance
description: Ensures routing pipeline is performant and build-time is bounded per merchant batch.
POSTERIOR_VALIDATION:
metric: CI build log: throughput, memory
acceptance_range: TP $\geq$ 200 MB/s, Mem $\leq$ 2 GB
sample_size: all build jobs per batch
PROVENANCE_TAG:
artefact_name: performance.yml
sha256: (see perf_config_digest)
SHORT_DESCRIPTION:
Build-time SLAs for routing throughput and memory, blocking build/merge if breached.
TEST_PATHWAY:
test: CI build performance script, log replay
input: CI build logs, performance config
assert: All jobs meet throughput/memory targets
Confidence=HIGH
<<<END PP‑FIX>>

##### END PARAMETER_SPEC #####

id=1 | gaps_closed=prior|calib|post|prov | notes=Direct normalization, no stochastic prior, audit hash locked  
id=2 | gaps_closed=prior|calib|post|prov | notes=O(1) alias, fully deterministic, CI/manifest locked  
id=3 | gaps_closed=prior|calib|post|prov | notes=Empirical fit for synchrony, all validation in log  
id=4 | gaps_closed=prior|calib|post|prov | notes=Empirical edge weights, sum-to-one enforced  
id=5 | gaps_closed=prior|calib|post|prov | notes=Thresholds block merge, YAML/CI driven  
id=6 | gaps_closed=prior|calib|post|prov | notes=Batch size, checksum, audit log proven  
id=7 | gaps_closed=prior|calib|post|prov | notes=Seed policy, manifest and proof-locked  
id=8 | gaps_closed=prior|calib|post|prov | notes=Performance SLA, build/merge blocking  
<<PS‑END>>
