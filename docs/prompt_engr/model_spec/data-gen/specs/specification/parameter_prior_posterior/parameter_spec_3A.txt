############################################################
#  PARAMETER SPEC‑WRITER • Sub‑segment 3A                   #
############################################################


<<<PP‑FIX id=1>
Name: Mixture threshold θ for escalation queue
Symbol: $\theta_{\text{mix}}$
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed threshold (YAML-governed)
hyperparameters:
theta_mix: (as set in zone_mixture_policy.yml, default 0.01)
units: unitless (proportion)
default_policy: use prior (abort if missing)
justification: Controls which countries are escalated for internal zone split vs. fallback to major zone.
CALIBRATION_RECIPE:
input_path: config/allocation/zone_mixture_policy.yml
objective: not applicable (policy, not fitted)
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see theta_digest)
INTERFACE_CONSUMER:
artefact_name: config/allocation/zone_mixture_policy.yml
function: Consumed by mixture queue flagger and allocator during allocation pass
description: Sets per-country mass cutoff for requiring a time-zone split; escalates high-mass to queue.
POSTERIOR_VALIDATION:
metric: YAML vs. queue bytewise test, manifest hash
acceptance_range: YAML and output queue match exactly
sample_size: all countries per allocation pass
PROVENANCE_TAG:
artefact_name: config/allocation/zone_mixture_policy.yml
sha256: (see theta_digest)
SHORT_DESCRIPTION:
Threshold for escalation to internal time-zone split per country.
TEST_PATHWAY:
test: test_mix_threshold.py, CI, manifest comparison
input: zone_mixture_policy.yml, output parquet
assert: Output queue matches YAML policy and manifest digest
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=2>
Name: Dirichlet concentration vector α (zone mixture)
Symbol: $\alpha = [\alpha_1, ..., \alpha_Z]$
Scope: merchant_location
---------------------------------

PRIOR:
type: Dirichlet (YAML-governed)
hyperparameters:
$\alpha_z$: Dirichlet vector, one per (country, TZID), see country_zone_alphas.yaml
units: unitless (positive integer)
default_policy: use prior (abort if missing)
justification: Controls variance and mean of zone allocation share in escalated countries.
CALIBRATION_RECIPE:
input_path: config/allocation/country_zone_alphas.yaml
objective: Empirical smoothing from settlement data; match rolling share mean/variance
algorithm: make_zone_alphas.py (see docs)
random_seed: CALIB_SEED
convergence_tol: 1e-4 or as set in script
script_digest: (see zone_alpha_digest)
INTERFACE_CONSUMER:
artefact_name: config/allocation/country_zone_alphas.yaml
function: Sample zone-share via Dirichlet; feeds Gamma generator and zone allocation
description: Used in zone-share sampling for escalated countries.
POSTERIOR_VALIDATION:
metric: empirical share error, normalization, CI digest
acceptance_range: share within 2pp of empirical; sum to 1
sample_size: all queued countries, all runs
PROVENANCE_TAG:
artefact_name: config/allocation/country_zone_alphas.yaml
sha256: (see zone_alpha_digest)
SHORT_DESCRIPTION:
Dirichlet vector for per-zone share sampling in cross-zone merchant allocation.
TEST_PATHWAY:
test: empirical share check, manifest digest test
input: YAML, settlement data, manifest
assert: Sampled shares match empirical, YAML digest matches manifest
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=3>
Name: Smoothing constant τ for Dirichlet vector
Symbol: $\tau$
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed constant (YAML-governed)
hyperparameters:
tau: 200 (as set in YAML)
units: unitless
default_policy: use prior
justification: Sets scale for Dirichlet α; controls variance of allocation
CALIBRATION_RECIPE:
input_path: config/allocation/country_zone_alphas.yaml
objective: Match target Dirichlet variance in allocation
algorithm: scaling, empirical moment matching
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see zone_alpha_digest)
INTERFACE_CONSUMER:
artefact_name: make_zone_alphas.py, config/allocation/country_zone_alphas.yaml
function: Multiplies empirical zone shares to produce α
description: Smoothing hyperparameter for Dirichlet zone allocation vector.
POSTERIOR_VALIDATION:
metric: implied variance, CI digest check
acceptance_range: variance matches target in calibration
sample_size: all countries/zones per run
PROVENANCE_TAG:
artefact_name: config/allocation/country_zone_alphas.yaml
sha256: (see zone_alpha_digest)
SHORT_DESCRIPTION:
Smoothing hyperparameter for Dirichlet vector in zone allocation.
TEST_PATHWAY:
test: empirical moment check, digest test
input: YAML, settlement data
assert: Variance and mean as targeted, digest matches
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=4>
Name: Major zone fallback mapping (country→TZID)
Symbol: major zone per country
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic mapping (CSV, land area)
hyperparameters:
major_zone: TZID, per country (from country_major_zone.csv)
units: string (TZID)
default_policy: use prior (abort if missing)
justification: Ensures all outlets in low-mass countries get assigned to largest legal time zone.
CALIBRATION_RECIPE:
input_path: artefacts/allocation/country_major_zone.csv
objective: Largest land area assignment from frozen shapefile
algorithm: land area computation and ranking
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see major_zone_digest)
INTERFACE_CONSUMER:
artefact_name: artefacts/allocation/country_major_zone.csv
function: Assigns TZID for all low-mass countries at fallback allocation step
description: Ensures deterministic, reproducible fallback allocation in zone assignment.
POSTERIOR_VALIDATION:
metric: CSV hash, CI drift detection
acceptance_range: hash matches manifest
sample_size: all countries
PROVENANCE_TAG:
artefact_name: artefacts/allocation/country_major_zone.csv
sha256: (see major_zone_digest)
SHORT_DESCRIPTION:
Deterministic fallback mapping of country to major time zone by area.
TEST_PATHWAY:
test: CSV hash check, drift audit
input: country_major_zone.csv, manifest
assert: CSV matches manifest hash, no drift
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=5>
Name: Zone floor vector φ_z (micro-zone protection)
Symbol: $\phi_z$
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed vector (YAML)
hyperparameters:
$\phi_z$: integer (min outlets per TZID)
units: count (int)
default_policy: use prior (abort if missing)
justification: Guarantees minimum site allocation for micro-zones after rounding.
CALIBRATION_RECIPE:
input_path: config/allocation/zone_floor.yml
objective: Enforce minimums for micro-zones; no zone loses all mass on integerisation
algorithm: YAML + integerisation/bump logic
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see zone_floor_digest)
INTERFACE_CONSUMER:
artefact_name: config/allocation/zone_floor.yml
function: Post-allocation floor enforcement; prevents zero allocation to any micro-zone
description: Applied after allocation and rounding for micro-zone protection.
POSTERIOR_VALIDATION:
metric: CI test_zone_floor.py, log, hash
acceptance_range: All floors enforced as per YAML
sample_size: all zones/countries per build
PROVENANCE_TAG:
artefact_name: config/allocation/zone_floor.yml
sha256: (see zone_floor_digest)
SHORT_DESCRIPTION:
Minimum site floor vector per zone for micro-zone protection.
TEST_PATHWAY:
test: CI floor test, log replay
input: zone_floor.yml, output allocation
assert: All floors enforced; manifest digest matches
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=6>
Name: Corporate-day log-normal multiplier variance
Symbol: $\sigma_{\gamma}^{2}$
Scope: merchant_location
---------------------------------

PRIOR:
type: LogNormal variance (YAML-governed)
hyperparameters:
$\sigma_{\gamma}^{2}$: 0.15 (see routing_day_effect.yml)
units: variance (dimensionless)
default_policy: use prior (fallback 0.15)
justification: Modulates LGCP mean for synchrony in cross-zone merchant allocation.
CALIBRATION_RECIPE:
input_path: config/routing/routing_day_effect.yml
objective: Fit to cross-zone correlation, empirical synchrony
algorithm: empirical moment matching
random_seed: CALIB_SEED
convergence_tol: as set in YAML
script_digest: (see gamma_variance_digest)
INTERFACE_CONSUMER:
artefact_name: config/routing/routing_day_effect.yml
function: Modulates LGCP mean, Poisson intensity, synchrony
description: Used for latent synchrony modulation in LGCP per merchant, per day.
POSTERIOR_VALIDATION:
metric: empirical correlation, CI digest check
acceptance_range: matches cross-zone synchrony; digest in manifest
sample_size: all days/merchants
PROVENANCE_TAG:
artefact_name: config/routing/routing_day_effect.yml
sha256: (see gamma_variance_digest)
SHORT_DESCRIPTION:
Variance for corporate-day log-normal multiplier in cross-zone LGCP mean.
TEST_PATHWAY:
test: empirical synchrony check, digest audit
input: routing_day_effect.yml, validation log
assert: Synchrony/variance matches target, manifest lock
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=7>
Name: Universe hash (cross-artifact linkage)
Symbol: $h = \mathrm{SHA256}(zone\_alpha\_digest \| theta\_digest \| zone\_floor\_digest \| gamma\_variance\_digest \| zone\_alloc\_parquet\_digest)$
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic digest (hash concatenation, not stochastic)
hyperparameters:
digests: zone_alpha_digest, theta_digest, zone_floor_digest, gamma_variance_digest, zone_alloc_parquet_digest
units: 64-char hex string
default_policy: abort (on any hash mismatch)
justification: Ensures all allocation, routing, and validation use identical artefact set; cross-artifact linkage.
CALIBRATION_RECIPE:
input_path: manifest, per-run
objective: cross-artifact linkage; ensure all config digests align
algorithm: hash concatenation + SHA256
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see manifest)
INTERFACE_CONSUMER:
artefact_name: manifest, all downstream routing tables
function: Universe linkage guard for all alias tables and allocation outputs
description: Enforces artefact integrity; all downstream consumers must match hash
POSTERIOR_VALIDATION:
metric: manifest hash check, property-based test
acceptance_range: hash matches all downstream artefacts; abort on drift
sample_size: per allocation run, all merchants
PROVENANCE_TAG:
artefact_name: manifest
sha256: (hash of concatenated digests)
SHORT_DESCRIPTION:
Cross-artifact linkage hash for universe integrity in routing/allocation.
TEST_PATHWAY:
test: manifest check, alias table audit
input: manifest, alias tables
assert: All hash values match or abort build
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=8>
Name: Barcode slope validation thresholds
Symbol: barcode_slope_low, barcode_slope_high
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed threshold (YAML-governed)
hyperparameters:
barcode_slope_low: -1.0
barcode_slope_high: -0.5
units: offsets per UTC hour (float)
default_policy: abort (if threshold breached)
justification: Prevents physically impossible barcode slope in cross-zone audit.
CALIBRATION_RECIPE:
input_path: config/validation/cross_zone_validation.yml
objective: set empirically from synthetic validation
algorithm: empirical, Hough transform slope estimation
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see cross_zone_validation_digest)
INTERFACE_CONSUMER:
artefact_name: config/validation/cross_zone_validation.yml
function: Consumed by CI barcode audit in cross-zone merchant validation
description: Checks for barcode heatmap slope within valid bounds during CI
POSTERIOR_VALIDATION:
metric: barcode slope (Hough), CI digest
acceptance_range: [-1.0, -0.5]
sample_size: all synthetic validation jobs
PROVENANCE_TAG:
artefact_name: config/validation/cross_zone_validation.yml
sha256: (see cross_zone_validation_digest)
SHORT_DESCRIPTION:
Audit thresholds for barcode slope in cross-zone merchant validation.
TEST_PATHWAY:
test: barcode slope CI audit
input: barcode audit output, validation log
assert: All slopes within thresholds, manifest digest locked
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=9>
Name: Zone-share convergence tolerance
Symbol: share_tolerance
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed threshold (YAML-governed)
hyperparameters:
share_tolerance: 0.02
units: unitless (absolute deviation)
default_policy: abort (if tolerance breached)
justification: Ensures empirical/allocated shares agree to within two percentage points during validation.
CALIBRATION_RECIPE:
input_path: config/validation/cross_zone_validation.yml
objective: match share convergence between synthetic and allocated
algorithm: empirical deviation calculation
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see cross_zone_validation_digest)
INTERFACE_CONSUMER:
artefact_name: config/validation/cross_zone_validation.yml
function: Used by CI to check share deviation in cross-zone validation
description: Triggers build abort if share tolerance breached in CI check.
POSTERIOR_VALIDATION:
metric: absolute deviation in share
acceptance_range: ≤ 0.02
sample_size: all merchants, all validation runs
PROVENANCE_TAG:
artefact_name: config/validation/cross_zone_validation.yml
sha256: (see cross_zone_validation_digest)
SHORT_DESCRIPTION:
Tolerance for allowed share difference in zone convergence validation.
TEST_PATHWAY:
test: share convergence CI check
input: validation output, allocation logs
assert: All shares within tolerance or build aborts
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=10>
Name: Random-stream isolation (Philox substream allocation)
Symbol: SHA256(merchant_id, country_iso)
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic hash/key (not stochastic)
hyperparameters:
merchant_id: string
country_iso: string
units: 64-char hex (Philox key)
default_policy: abort (if proof not matched, CI fail)
justification: Guarantees per-merchant/country random stream isolation for Dirichlet, Gamma draws.
CALIBRATION_RECIPE:
input_path: docs/rng_proof.md
objective: proof of stream isolation and replay
algorithm: property-based test suite, hash construction
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see rng_proof_digest)
INTERFACE_CONSUMER:
artefact_name: docs/rng_proof.md
function: Dirichlet/Gamma stream isolation, downstream validation and audit
description: Enforces reproducibility and auditability of all random draws in cross-zone allocation.
POSTERIOR_VALIDATION:
metric: property-based test, proof in manifest
acceptance_range: all hash tests pass
sample_size: all allocation runs per merchant
PROVENANCE_TAG:
artefact_name: docs/rng_proof.md
sha256: (see rng_proof_digest)
SHORT_DESCRIPTION:
Keying for Philox substreams to isolate all random draws per merchant/country.
TEST_PATHWAY:
test: property-based suite, audit replay
input: validation logs, manifest, rng proof
assert: All substreams pass isolation and proof check
Confidence=HIGH
<<<END PP‑FIX>>

##### END PARAMETER_SPEC #####

id=1 | gaps_closed=prior|calib|post|prov | notes=YAML-driven escalation threshold, audit/manifest locked  
id=2 | gaps_closed=prior|calib|post|prov | notes=Dirichlet vector, script-calibrated, manifest locked  
id=3 | gaps_closed=prior|calib|post|prov | notes=Dirichlet smoothing constant, script-calibrated  
id=4 | gaps_closed=prior|calib|post|prov | notes=Major zone fallback, shapefile-calculated  
id=5 | gaps_closed=prior|calib|post|prov | notes=Micro-zone floor, YAML/CI/test enforced  
id=6 | gaps_closed=prior|calib|post|prov | notes=Corporate-day variance, YAML/script-driven  
id=7 | gaps_closed=prior|calib|post|prov | notes=Hash linkage, manifest/CI enforced  
id=8 | gaps_closed=prior|calib|post|prov | notes=Barcode slope, CI-audited  
id=9 | gaps_closed=prior|calib|post|prov | notes=Share tolerance, CI build-audited  
id=10 | gaps_closed=prior|calib|post|prov | notes=Stream isolation, proof-locked  
<<PS‑END>>
