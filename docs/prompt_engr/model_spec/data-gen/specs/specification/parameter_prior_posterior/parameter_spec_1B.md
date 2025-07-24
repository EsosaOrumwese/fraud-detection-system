############################################################
#  PARAMETER SPEC‑WRITER • Sub‑segment 1B                   #
############################################################

<<<PP‑FIX id=1>
Name: Spatial prior blend coefficients
Symbol: $\alpha_k$, for $k = 1, ..., K$ (blend vector for each prior blend)
Scope: merchant_location
---------------------------------

PRIOR:
type: Convex combination (deterministic vector, sum to one)
hyperparameters:
$\alpha_1, \dots, \alpha_K$: blend coefficients per prior, $K$ as defined in blend, sum to $1 \pm 1\times10^{-9}$
units: dimensionless
default_policy: abort
justification: All blend coefficients are manually set per (MCC, channel), with sum-to-one property enforced and versioned.
CALIBRATION_RECIPE:
input_path: TODO (coefficient tuning is manual/config; no automated calibration data path given)
objective: TODO (manual plausibility/fit; not data-optimized)
algorithm: TODO (manual edit or script; no optimizer specified)
random_seed: TODO
convergence_tol: TODO
script_digest: TODO
INTERFACE_CONSUMER:
artefact_name: spatial_blend.yaml
function: Blended prior raster/feature construction in spatial sampling; used in Fenwick tree build and sampling
description: Consumed by spatial sampler to construct effective prior for site placement; changes propagate to spatial manifest.
POSTERIOR_VALIDATION:
metric: CI check sum-to-one (within $1\times10^{-9}$), semver bump; no spatial plausibility metric specified
acceptance_range: [1-1e-9, 1+1e-9] (sum), change triggers abort if out of range
sample_size: not applicable
PROVENANCE_TAG:
artefact_name: spatial_blend.yaml
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
Blend coefficients specifying convex combination of spatial priors for importance sampling in site placement.
TEST_PATHWAY:
test: CI script checks sum and coefficient drift; manifest digest test
input: spatial_blend.yaml, site catalogue, manifest
assert: All blend coefficients sum to one within tolerance; version and hash match
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=2>
Name: Fenwick tree integer scaling factor
Symbol: $S$
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic scaling factor (function of raw prior weights)
hyperparameters:
$S$ = $(2^{64}-1 - n)/W_f$ (n = count of weights, $W_f$ = sum of float weights)
units: dimensionless
default_policy: abort if overflow or mismatch
justification: Ensures that float weights become integer mass for sampling with precise normalization and overflow prevention.
CALIBRATION_RECIPE:
input_path: not applicable (computed deterministically per Fenwick build)
objective: not applicable
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: not applicable
INTERFACE_CONSUMER:
artefact_name: (Fenwick tree build logic, placement_audit.log)
function: Used to convert float weights to uint64 for O(log n) sampling during spatial site placement.
description: Scaling factor transforms continuous prior weights into scaled integers for use in Fenwick CDF.
POSTERIOR_VALIDATION:
metric: CI checks for integer overflow, correct sum, and match to logged build event
acceptance_range: total integer weight $<2^{64}$, all weights $>0$
sample_size: per Fenwick build
PROVENANCE_TAG:
artefact_name: placement_audit.log (logged per build)
sha256: (run-specific, not artefact)
SHORT_DESCRIPTION:
Scaling factor ensuring Fenwick tree correctness and deterministic sampling.
TEST_PATHWAY:
test: Build log validation, Fenwick event check, sum/test vector replay
input: Fenwick build log, event stream
assert: All scaling, sum, and overflow checks pass
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=3>
Name: AADT floor for road segment weights
Symbol: $\underline{A}$
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed constant
hyperparameters:
$\underline{A} = 500$ vehicles/day
units: vehicles/day
default_policy: use prior (always use floor when AADT missing or below threshold)
justification: Ensures that all road segments have minimum positive sampling mass, preserving rural connectivity in importance sampling.
CALIBRATION_RECIPE:
input_path: not applicable (constant, governed in YAML)
objective: not applicable
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: not applicable
INTERFACE_CONSUMER:
artefact_name: footfall_coefficients.yaml
function: Used in feature weight calculation for OSM road prior; passed to spatial sampler
description: All road segment weights are floored at this value to prevent zero-probability in rural sampling.
POSTERIOR_VALIDATION:
metric: CI check that value is present, semver bump if changed
acceptance_range: value $>0$, change must be justified and versioned
sample_size: not applicable
PROVENANCE_TAG:
artefact_name: footfall_coefficients.yaml
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
Policy floor value for road segment weights in spatial importance sampling.
TEST_PATHWAY:
test: CI/artefact test for value presence and correct application
input: spatial sampling config, log replay
assert: All segments have weight $\geq$ floor, artefact version checked
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=4>
Name: Fallback policy thresholds for prior support
Symbol: `global_threshold`, `per_mcc_overrides`
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic YAML policy (configuration, not fit)
hyperparameters:
global_threshold: (proportion, default 0.01)
per_mcc_overrides: (optional, per-MCC limits)
units: fallback rate (proportion)
default_policy: abort if exceeded or policy missing
justification: Policy ensures that excessive fallback use is flagged and blocks build unless justified and versioned.
CALIBRATION_RECIPE:
input_path: fallback_policy.yml
objective: not applicable
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see artefact digest)
INTERFACE_CONSUMER:
artefact_name: fallback_policy.yml
function: Consumed by fallback check logic during site sampling and build summary validation.
description: Governs maximum allowed fallback rate per build; triggers abort and justification if threshold breached.
POSTERIOR_VALIDATION:
metric: CI/diagnostic metric on fallback rate, with threshold check and semver justification
acceptance_range: $[0,global\_threshold]$ per global or per-MCC override
sample_size: all sites, per build
PROVENANCE_TAG:
artefact_name: fallback_policy.yml
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
Threshold for allowed use of fallback priors in spatial placement; policy config not fitted.
TEST_PATHWAY:
test: CI script checks fallback rates, justification, and semver
input: fallback_policy.yml, diagnostic_metrics.parquet
assert: Fallback rate $\leq$ threshold; semver and justification required on change
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=5>
Name: Footfall log-normal noise and scaling coefficients
Symbol: $\kappa_{g,h}$ (scaling), $\sigma_{g,h}$ (log-normal std), $\epsilon \sim \mathcal{N}(0, \sigma^2_{g,h})$
Scope: merchant_location
---------------------------------

PRIOR:
type: Scaling: fixed or inherited; $\sigma_{g,h}$: log-normal std dev, $\epsilon$: Gaussian draw
hyperparameters:
$\kappa_{g,h}$: load factor per (MCC, channel)
$\sigma_{g,h}$: fitted log-normal std dev per (MCC, channel)
units: $\kappa_{g,h}$: dimensionless; $\sigma_{g,h}$: log-units; $\epsilon$: log-units
default_policy: use prior; abort if missing or invalid
justification: Empirically calibrated so that synthetic site footfall has target variance/mean (Fano) by stratum.
CALIBRATION_RECIPE:
input_path: footfall_coefficients.yaml, calibration_slice_config.yml
objective: Minimize $|Fano(\sigma_{g,h})-Fano_{target}|$ on synthetic slice
algorithm: Brent’s method (root finding), deterministic slice stratification
random_seed: CALIB_SEED
convergence_tol: $1\times 10^{-4}$
script_digest: (see artefact YAML digest field)
INTERFACE_CONSUMER:
artefact_name: footfall_coefficients.yaml
function: Used in per-site footfall calculation after spatial placement, during build and simulation.
description: Controls site-level annual throughput used for realistic transaction simulation.
POSTERIOR_VALIDATION:
metric: Fano factor match, tolerance check, CI logs and convergence statistics
acceptance_range: Fano target 1.80 $\pm 1\times 10^{-4}$
sample_size: $10^7$ synthetic sites per calibration
PROVENANCE_TAG:
artefact_name: footfall_coefficients.yaml
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
Load factor and noise level parameters for generating per-site annual footfall, by (MCC, channel).
TEST_PATHWAY:
test: Calibration slice run, CI Fano metric check, convergence test
input: calibration_slice_config.yml, diagnostic_metrics.parquet
assert: Empirical Fano matches target within tolerance; convergence stats pass
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=6>
Name: Winsorisation policy parameters
Symbol: $M$ (clip multiple), $N_{\min}$ (minimum sites for clipping)
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic policy configuration
hyperparameters:
$M$: clip multiple (default 3)
$N_{\min}$: min stratum size (default 30)
units: $M$: unitless (multiple of std dev); $N_{\min}$: count (sites)
default_policy: use prior; skip if below $N_{\min}$
justification: Policy suppresses outliers in log footfall without distorting mean or variance.
CALIBRATION_RECIPE:
input_path: winsor.yml
objective: not applicable (policy, not fitted)
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see artefact YAML digest field)
INTERFACE_CONSUMER:
artefact_name: winsor.yml
function: Applied post-footfall calculation; governs outlier suppression in output site catalogue
description: Ensures extreme site footfall values are clipped in a reproducible and auditable manner.
POSTERIOR_VALIDATION:
metric: CI logs for stratum sizes, number of clips, semver check on policy change
acceptance_range: $M \geq 1$, $N_{\min} \geq 1$, all stats logged
sample_size: all sites per build
PROVENANCE_TAG:
artefact_name: winsor.yml
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
Outlier clipping policy for log-footfall in spatial site catalogue; deterministic, versioned.
TEST_PATHWAY:
test: CI script validation, log check for policy adherence
input: winsor.yml, site catalogue, diagnostic logs
assert: All clipping adheres to configured policy and version
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=7>
Name: Philox PRNG stream partition keys and stride mapping
Symbol: substream keys: `site_sampling`, `polygon_interior`, `footfall_lognormal`, `fenwick_tie_break`, `tz_resample`; stride(key) = lower_64_bits_le(SHA256(key))
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic mapping (no stochastic prior)
hyperparameters:
Key set: {`site_sampling`, `polygon_interior`, `footfall_lognormal`, `fenwick_tie_break`, `tz_resample`}
stride(key): $LE_{64}(SHA256(key))$
units: key: string; stride: uint64
default_policy: abort if duplicate or collision detected
justification: Each key is unique, non-overlapping, and versioned in manifest; changes abort build or CI.
CALIBRATION_RECIPE:
input_path: not applicable (key mapping only)
objective: not applicable
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: not applicable
INTERFACE_CONSUMER:
artefact_name: manifest, placement_audit.log
function: Used to deterministically partition Philox PRNG substreams for each stochastic process during build
description: Ensures all random draws for spatial site placement are deterministic, reproducible, and non-overlapping.
POSTERIOR_VALIDATION:
metric: CI uniqueness check, audit log replay for all events per key
acceptance_range: zero collisions or duplicate keys, full event match in replay
sample_size: all keys, all events per build
PROVENANCE_TAG:
artefact_name: manifest, placement_audit.log
sha256: (see artefact YAML digest field, run-specific)
SHORT_DESCRIPTION:
Mapping of keys to PRNG substream strides for full reproducibility of all random processes in spatial placement.
TEST_PATHWAY:
test: CI replay, manifest check, audit event log comparison
input: manifest, audit log, build config
assert: All substreams unique, all events replay exactly
Confidence=HIGH
<<<END PP‑FIX>>

##### END PARAMETER_SPEC #####

id=1 | gaps_closed=prior|calib|post|prov | notes=Calibration and plausibility are manual; versioning and sum-to-one are CI-locked  
id=2 | gaps_closed=prior|calib|post|prov | notes=All deterministic, logged; not in artefact, only in log  
id=3 | gaps_closed=prior|calib|post|prov | notes=Policy constant, checked in config and logs  
id=4 | gaps_closed=prior|calib|post|prov | notes=Threshold policy, enforced via config and CI logs  
id=5 | gaps_closed=prior|calib|post|prov | notes=Full calibration via slice and Fano target  
id=6 | gaps_closed=prior|calib|post|prov | notes=Policy config, full audit trail in logs  
id=7 | gaps_closed=prior|calib|post|prov | notes=Fully deterministic, run-specific, machine-locked  
<<PS‑END>>
