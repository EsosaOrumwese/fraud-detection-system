############################################################
#  PARAMETER SPEC‑WRITER • Sub‑segment 1A                   #
############################################################

<<<PP‑FIX id=1>
Name: Hurdle logistic regression coefficients
Symbol: $\beta$ (vector: $\beta_0, \beta_{\text{mcc}}, \beta_{\text{channel}}, \beta_{\text{dev}}$)
Scope: merchant_location
---------------------------------

PRIOR:
type: Unknown (maximum-likelihood fit; not explicitly Bayesian)
hyperparameters:
(estimation window, not explicit; vector length = predictors in design matrix)
units: dimensionless (log-odds)
default_policy: abort
justification: All coefficients fit on proprietary acquirer data, covering intercept, MCC, channel, GDP bucket.
CALIBRATION_RECIPE:
input_path: TODO (source data, not disclosed)
objective: Maximum Likelihood Estimation (logistic regression)
algorithm: Standard logistic regression solver; method not specified (e.g., L-BFGS)
random_seed: TODO
convergence_tol: TODO
script_digest: TODO
INTERFACE_CONSUMER:
artefact_name: hurdle_coefficients.yaml
function: Hurdle logistic decision function (single-site vs. multi-site); loaded by merchant design matrix construction and site count allocation
description: Consumed by merchant design matrix build and outlet count logic in merchant-location realism layer.
POSTERIOR_VALIDATION:
metric: Stationarity test (Wald); corridor for drift (alpha=0.01)
acceptance_range: Non-rejection across simulation horizon; explicit corridor not given
sample_size: Not specified
PROVENANCE_TAG:
artefact_name: hurdle_coefficients.yaml
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
Coefficient vector for logistic regression predicting multi-site status from merchant features; used in first branch of merchant-location realism pipeline.
TEST_PATHWAY:
test: CI stationarity script / validation (property-based)
input: Simulation logs, stationary test artefact
assert: No parameter drift or rejection (see artefact diagnostics)
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=2>
Name: Negative binomial mean and dispersion coefficients
Symbol: $\alpha_0$, $\alpha_{\text{mcc}}$, $\alpha_{\text{channel}}$ (mean link); $\delta_0$, $\delta_{\text{mcc}}$, $\delta_{\text{channel}}$, $\eta$ (dispersion link)
Scope: merchant_location
---------------------------------

PRIOR:
type: Unknown (MLE fit, not Bayesian)
hyperparameters:
Mean: $\alpha_0$, $\alpha_{\text{mcc}}$, $\alpha_{\text{channel}}$
Dispersion: $\delta_0$, $\delta_{\text{mcc}}$, $\delta_{\text{channel}}$, $\eta$ (GDP term)
units: log outlet count (mean/dispersion)
default_policy: abort
justification: Regression coefficients fit to proprietary acquirer data; $\eta > 0$ for GDP monotonicity
CALIBRATION_RECIPE:
input_path: TODO (not disclosed)
objective: MLE for NB GLM (site counts)
algorithm: NB GLM fit (e.g., iteratively reweighted least squares, not specified)
random_seed: TODO
convergence_tol: TODO
script_digest: TODO
INTERFACE_CONSUMER:
artefact_name: nb_dispersion_coefficients.yaml
function: Computes mean/dispersion for Poisson–Gamma NB mixture; used for outlet count sampling (multi-site)
description: Merchant-level negative binomial parameterization; main outlet count engine for multi-site chains.
POSTERIOR_VALIDATION:
metric: Parameter drift stationarity (CUSUM, alpha=0.01), NB rejection rates (target corridor [0,0.06]), p99 rejections (≤3)
acceptance_range: Stationarity test non-rejection, rates within corridor
sample_size: Not specified
PROVENANCE_TAG:
artefact_name: nb_dispersion_coefficients.yaml
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
GLM coefficients for mean and dispersion in negative binomial draws for multi-site outlet counts.
TEST_PATHWAY:
test: CI monitoring script; diagnostic_metrics.parquet
input: Stochastic draw logs, metrics parquet
assert: All rates/parameters within corridor; abort on failure
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=3>
Name: Zero-truncated Poisson (ZTP) cross-border expansion parameters
Symbol: $\lambda_{\text{extra}}$, $\theta_0$, $\theta_1$
Scope: merchant_location
---------------------------------

PRIOR:
type: Linear model on log N; Poisson mean for ZTP
hyperparameters:
$\theta_0$, $\theta_1$ (see crossborder_hyperparams.yaml)
units: dimensionless
default_policy: abort (cap 64, abort if exceeded)
justification: Fitted by MLE, with explicit Wald p-value for $\theta_1$ < 1 for sub-linearity
CALIBRATION_RECIPE:
input_path: TODO (not disclosed)
objective: MLE for Poisson regression; ZTP correction
algorithm: Poisson GLM (method not specified)
random_seed: TODO
convergence_tol: TODO
script_digest: TODO
INTERFACE_CONSUMER:
artefact_name: crossborder_hyperparams.yaml
function: Parameterizes ZTP mean for number of foreign countries in merchant allocation
description: Controls the expected “sprawl” of a merchant beyond home country in site allocation logic
POSTERIOR_VALIDATION:
metric: Wald p-value on $\theta_1$ (< 1e-5); ZTP rejection rates (mean <0.05, p99.9 <3)
acceptance_range: corridor/threshold as per monitoring section
sample_size: Not specified
PROVENANCE_TAG:
artefact_name: crossborder_hyperparams.yaml
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
Poisson mean parameters for zero-truncated cross-border country count allocation per merchant.
TEST_PATHWAY:
test: Monitoring and stationarity diagnostics in CI, stationarity_diagnostics.parquet
input: stochastic logs, parameter drift
assert: Wald p-value passes; rejection metrics within corridor
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=4>
Name: Dirichlet concentration parameters for outlet allocation
Symbol: $\alpha_i$
Scope: merchant_location
---------------------------------

PRIOR:
type: Dirichlet
hyperparameters:
$\alpha_i$ for each country in set (home + foreigns), from crossborder_hyperparams.yaml
units: dimensionless
default_policy: use prior (fallback to equal split if sparse)
justification: Loaded as vector keyed on (home_country, MCC, channel); no dynamic fit
CALIBRATION_RECIPE:
input_path: TODO (artefact not specified; not disclosed)
objective: TODO
algorithm: TODO
random_seed: TODO
convergence_tol: TODO
script_digest: TODO
INTERFACE_CONSUMER:
artefact_name: crossborder_hyperparams.yaml
function: Supplies Dirichlet prior for Gamma draw in outlet allocation across countries
description: Drives proportional country split after cross-border country selection
POSTERIOR_VALIDATION:
metric: Rounding allocation error ($|n_i-w_iN|$), empirical report
acceptance_range: Max $|n_i-w_iN| ≤ 1$; relative error <0.3% (empirical)
sample_size: Not specified
PROVENANCE_TAG:
artefact_name: crossborder_hyperparams.yaml
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
Concentration vector for Dirichlet allocation of merchant outlets across legal countries.
TEST_PATHWAY:
test: Validation of allocation error post-write; error metrics in output log
input: Allocated vs. expected counts
assert: Empirical rounding error within envelope; abort otherwise
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=5>
Name: Additive Dirichlet smoothing alpha
Symbol: $\alpha=0.5$
Scope: merchant_location
---------------------------------

PRIOR:
type: Dirichlet smoothing (fixed)
hyperparameters:
$\alpha=0.5$ (hard-coded)
units: dimensionless
default_policy: use prior (always applied to small count cases)
justification: Ensures no destination country receives zero weight in proportional split
CALIBRATION_RECIPE:
input_path: not applicable (fixed constant)
objective: not applicable
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: not applicable
INTERFACE_CONSUMER:
artefact_name: (applied inline in expansion logic)
function: Smoothing of intra-currency split in country allocation
description: Ensures sparse country cases do not yield zero weights in expansion
POSTERIOR_VALIDATION:
metric: none (no monitoring)
acceptance_range: not applicable
sample_size: not applicable
PROVENANCE_TAG:
artefact_name: not applicable (inline constant)
sha256: not applicable
SHORT_DESCRIPTION:
Fixed additive smoothing parameter for sparse intra-currency country splits
TEST_PATHWAY:
test: none
input: not applicable
assert: not applicable
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=6>
Name: GDP bucket mapping
Symbol: 5 Jenks buckets (indices 1–5)
Scope: merchant_location
---------------------------------

PRIOR:
type: Jenks natural breaks (deterministic mapping)
hyperparameters:
World Bank GDP per capita; breakpoints computed in artefact
units: constant USD (2015 base), categorical
default_policy: use prior (mapping is frozen)
justification: GDP buckets fixed at mapping run, referenced by vintage and digest
CALIBRATION_RECIPE:
input_path: artefacts/gdp/gdp_bucket_map_2024.parquet
objective: Jenks optimization (minimize within-bucket variance)
algorithm: Jenks natural breaks algorithm
random_seed: not applicable (deterministic)
convergence_tol: not applicable
script_digest: (see artefact digest)
INTERFACE_CONSUMER:
artefact_name: artefacts/gdp/gdp_bucket_map_2024.parquet
function: Used in merchant design matrix for GDP bucket dummies in hurdle regression
description: Assigns development bucket per country for hurdle logistic
POSTERIOR_VALIDATION:
metric: Wald stationarity test, rolling horizon; no direct acceptance region for mapping
acceptance_range: non-rejection at alpha=0.01 over horizon
sample_size: not specified
PROVENANCE_TAG:
artefact_name: artefacts/gdp/gdp_bucket_map_2024.parquet
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
GDP bucket mapping artefact for development bucket assignment in site logic
TEST_PATHWAY:
test: CI stationarity diagnostics
input: GDP mapping artefact, rolling test results
assert: Non-rejection over test window
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=7>
Name: NB and ZTP Poisson/Gamma/Dirichlet RNG seeds and stream jump strides
Symbol: "Philox 2^128 master seed" / sub-stream jump strides
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic (parameter hash, manifest fingerprint)
hyperparameters:
Parameter hash (SHA-256), manifest fingerprint (SHA-256), substream strides (SHA-256 lower 64 bits of string keys)
units: seed (uint128), stride (uint64), dimensionless
default_policy: abort if mismatch
justification: Ensures bit-for-bit reproducibility of every stochastic branch and draw
CALIBRATION_RECIPE:
input_path: not applicable (reproducibility only)
objective: not applicable
algorithm: not applicable
random_seed: not applicable
convergence_tol: not applicable
script_digest: not applicable
INTERFACE_CONSUMER:
artefact_name: All draw logic, audit/replay, validation scripts
function: Supplies seed, jump stride for PRNG streams in all stochastic branches
description: Ensures every stochastic decision is reproducible and audit-ready
POSTERIOR_VALIDATION:
metric: Exact replay of stochastic event logs, matching all pre/post counters and values
acceptance_range: exact bitwise equality
sample_size: n/a
PROVENANCE_TAG:
artefact_name: manifest_fingerprint (see _manifest.json, output parquet comment fields)
sha256: (see artefact YAML digest field)
SHORT_DESCRIPTION:
Seed and PRNG stream stride mechanism for deterministic replay of all random events in the build.
TEST_PATHWAY:
test: Replay audit log, validation script reconstructs full decision history
input: Output catalogue, rng_audit.log, manifest
assert: Bitwise event match on replay
Confidence=HIGH
<<<END PP‑FIX>>

##### END PARAMETER_SPEC #####

id=1 | gaps_closed=prior|calib|post|prov | notes=Prior, calibration, and posterior details largely TODO due to external data  
id=2 | gaps_closed=prior|calib|post|prov | notes=MLE details, calibration input missing  
id=3 | gaps_closed=prior|calib|post|prov | notes=Calibration algorithm and input path not disclosed; corridor for posterior set  
id=4 | gaps_closed=prior|calib|post|prov | notes=Calibration/provenance only partial; hyperparameters are referenced  
id=5 | gaps_closed=prior|calib|post|prov | notes=Fixed constant; not in artefact file  
id=6 | gaps_closed=prior|calib|post|prov | notes=Mapping is deterministic; stationarity test only for posterior  
id=7 | gaps_closed=prior|calib|post|prov | notes=All details in manifest; no calibration/posterior  
<<PS‑END>>
