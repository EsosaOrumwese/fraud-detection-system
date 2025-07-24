############################################################
#  PARAMETER SPEC‑WRITER • Sub‑segment 4B                   #
############################################################


<<<PP‑FIX id=1>
Name: Structural validation error contract
Symbol: StructuralError, structural_failure_<parameter_hash>.parquet
Scope: validation
---------------------------------

PRIOR:
type: Deterministic contract (Parquet + CI)
hyperparameters:
structural_failure_parquet: structural_failure_<parameter_hash>.parquet
units: log entry (failed row, RNG jump offset)
default_policy: abort (first error halts pipeline, blocks merge)
justification: Ensures no structural error is silently tolerated; every defect halts build, is logged and merge-blocked.
CALIBRATION_RECIPE:
input_path: structural_failure_<parameter_hash>.parquet, artefact_registry.yaml
objective: Capture and halt on every structural error, ensure every error is logged and hash-mapped
algorithm: synchronous defect channel, CI test, log and hash validation
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see structural_failure_digest)
INTERFACE_CONSUMER:
artefact_name: validator, CI, audit, manifest, logs
function: Captures and logs every failed row/defect for structural plausibility validation
description: All pipeline outputs and validation harnesses halt and log on structural defect, blocking merge.
POSTERIOR_VALIDATION:
metric: defect log check, fail-fast, merge-block
acceptance_range: no defects tolerated, all logged
sample_size: all failed rows per run
PROVENANCE_TAG:
artefact_name: structural_failure_<parameter_hash>.parquet
sha256: (see structural_failure_digest)
SHORT_DESCRIPTION:
Every failed row or coordinate/time/schema defect is logged and blocks build and merge.
TEST_PATHWAY:
test: CI, audit, manifest log replay
input: structural_failure parquet, logs, manifest
assert: All defects halt pipeline, defect log present, hash matches
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=2>
Name: Adversarial AUROC drift detection
Symbol: DistributionDriftDetected, auroc_model_*.parquet, misclassified_*.csv
Scope: validation
---------------------------------

PRIOR:
type: Deterministic contract (XGBoost, YAML, hyper-parameter lock)
hyperparameters:
auroc_model_parquet: auroc_model_*.parquet
misclassified_csv: misclassified_*.csv
units: AUROC (float), indices (CSV)
default_policy: abort (if AUROC > 0.55 or artefact/log missing)
justification: Ensures that any distributional drift is detected and blocks further progress if AUROC threshold exceeded.
CALIBRATION_RECIPE:
input_path: validation_conf.yml
objective: Windowed AUROC test, hyper-parameter locked model validation
algorithm: XGBoost windowed training, YAML/model/feature locking
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see validation_conf_digest)
INTERFACE_CONSUMER:
artefact_name: validator, CI, audit, manifest, logs
function: Runs adversarial test, logs drift, halts pipeline if drift detected
description: Detects and logs any AUROC drift above threshold, blocks merge, logs model dump and misclassified indices.
POSTERIOR_VALIDATION:
metric: AUROC threshold test, manifest/CI fail-fast
acceptance_range: AUROC ≤ 0.55
sample_size: million-row windows per run
PROVENANCE_TAG:
artefact_name: auroc_model_*.parquet, misclassification_digest
sha256: (see validation_conf_digest)
SHORT_DESCRIPTION:
Adversarial AUROC drift test logs and blocks build if drift detected.
TEST_PATHWAY:
test: CI, adversarial log check, manifest match
input: model parquet, misclassified csv, logs
assert: AUROC ≤ 0.55 or pipeline halts, logs/manifest match
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=3>
Name: Semantic GLM dispersion corridor
Symbol: θ, glm_theta_violation.pdf
Scope: validation
---------------------------------

PRIOR:
type: Corridor (YAML, Poisson GLM, channel-specific)
hyperparameters:
theta_cp: [1, 2]
theta_cnp: [2, 4]
units: θ (dispersion, float)
default_policy: abort (θ out of corridor triggers error, CI block, needs_recalibration flag)
justification: Protects model/fit plausibility; out-of-range θ means LGCP/footfall calibration has drifted.
CALIBRATION_RECIPE:
input_path: footfall_coefficients.yaml, statsmodels, CI logs
objective: Corridor and fit validation, channel-specific θ
algorithm: statsmodels GLM, in-memory, dispersion check
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see theta_violation_digest)
INTERFACE_CONSUMER:
artefact_name: validator, CI, semantic_glm.py, audit, manifest
function: Checks and flags dispersion; blocks merge if corridor violated.
description: Ensures every fitted channel stays within plausible θ corridor, recalibration forced if violated.
POSTERIOR_VALIDATION:
metric: θ corridor fit, GLM fit, CI manifest/flag check
acceptance_range: [1, 2] for CP; [2, 4] for CNP
sample_size: all channel/merchants per run
PROVENANCE_TAG:
artefact_name: footfall_coefficients.yaml
sha256: (see theta_violation_digest)
SHORT_DESCRIPTION:
GLM θ corridor for footfall calibration and semantic dispersion control.
TEST_PATHWAY:
test: semantic_glm.py, CI replay, log/manifest
input: YAML, fit, logs
assert: All θ within corridor, else block/recalibrate
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=4>
Name: Barcode slope threshold
Symbol: barcode_bounds.yml, BarcodeSlopeError, barcode_failure_*.png
Scope: validation
---------------------------------

PRIOR:
type: Physical-law corridor (YAML, Hough transform)
hyperparameters:
barcode_slope_low: -1.0
barcode_slope_high: -0.5
units: slope (offsets per UTC hour, float)
default_policy: abort (slope out of bounds triggers PNG, fail, merge block)
justification: Physics corridor enforcement for all merchants, hard block if barcode slope falls outside bounds.
CALIBRATION_RECIPE:
input_path: barcode_bounds.yml
objective: Empirical slope validation, Hough transform check
algorithm: fast Hough transform, PNG overlay, YAML corridor
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see barcode_failure_digest)
INTERFACE_CONSUMER:
artefact_name: validator, barcode.py, CI, audit, manifest
function: Runs Hough transform, renders and saves barcode failure PNG, logs event
description: Protects against physically implausible barcode drift or time-series implausibility.
POSTERIOR_VALIDATION:
metric: Hough slope corridor, PNG audit, manifest check
acceptance_range: [-1, -0.5]
sample_size: all barcode events per run
PROVENANCE_TAG:
artefact_name: barcode_bounds.yml
sha256: (see barcode_failure_digest)
SHORT_DESCRIPTION:
Physical corridor for barcode slope, rendered, checked, and merge-blocked if out of bounds.
TEST_PATHWAY:
test: barcode.py, PNG overlay, CI replay
input: YAML, PNG, logs
assert: All slopes within corridor, else block
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=5>
Name: Licence mapping and audit
Symbol: artefact_registry.yaml, licence_digests
Scope: validation
---------------------------------

PRIOR:
type: Deterministic mapping (SHA-1 digest contract)
hyperparameters:
licence_digests: SHA-1 for every mapped artefact
units: SHA-1 digest (hex string)
default_policy: abort (licence mismatch, missing, or unreferenced)
justification: Enforces full legal provenance for every artefact, all mapped, SHA-1 locked, blocking build if mismatch.
CALIBRATION_RECIPE:
input_path: artefact_registry.yaml, validate_licences.py
objective: Mapping and SHA-1 match for all artefacts
algorithm: SHA-1 calculation, mapping, audit
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see licence_log_digest)
INTERFACE_CONSUMER:
artefact_name: validator, CI, audit, manifest, logs
function: Checks mapping for all artefacts, SHA-1 for every licence; blocks build if mismatch
description: Mapping is fully checked and logged; CI blocks merge if any missing or mismatched
POSTERIOR_VALIDATION:
metric: mapping completeness, SHA-1 comparison
acceptance_range: all licences mapped, all SHA-1s match
sample_size: all artefacts per build
PROVENANCE_TAG:
artefact_name: artefact_registry.yaml
sha256: (see licence_log_digest)
SHORT_DESCRIPTION:
Legal and compliance mapping for every artefact and its SHA-1 licence.
TEST_PATHWAY:
test: validate_licences.py, CI, audit replay
input: artefact_registry.yaml, manifest
assert: All artefact SHA-1 digests match, mapping is complete
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=6>
Name: Directory immutability and audit hash/URI enforcement
Symbol: validation/hashgate_uri.txt, readonly.flag
Scope: validation
---------------------------------

PRIOR:
type: Deterministic (SHA-256, URI, file lock)
hyperparameters:
hashgate_uri: validation/hashgate_uri.txt
readonly_flag: readonly.flag
units: URI (string), SHA-256 digest, file presence
default_policy: abort (if missing, not locked, or URI not referenced)
justification: Directory must be read-only, hashgate URI must be present, audit/merge must reference hash/URI.
CALIBRATION_RECIPE:
input_path: validation/hashgate_uri.txt, readonly.flag
objective: Ensure directory immutability and audit URI/flag presence
algorithm: directory/file presence, SHA-256 calculation, URI check
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see hashgate_uri_digest, readonly_flag_digest)
INTERFACE_CONSUMER:
artefact_name: validator, CI, NFS, manifest, merge/release script
function: Ensures audit/validation directory is immutable, audit URI and readonly flag are referenced in manifest and logs
description: Final directory is checked for immutability, poll for URI approval, CI blocks merge if any test fails.
POSTERIOR_VALIDATION:
metric: directory/file presence, hash/URI check
acceptance_range: hashgate URI and readonly flag present and referenced, directory read-only
sample_size: all validation directories per build
PROVENANCE_TAG:
artefact_name: validation/hashgate_uri.txt, readonly.flag
sha256: (see hashgate_uri_digest, readonly_flag_digest)
SHORT_DESCRIPTION:
Directory and audit URI/flag for immutability and merge-blocking validation.
TEST_PATHWAY:
test: directory immutability, CI, audit log
input: hashgate_uri.txt, readonly.flag, manifest, logs
assert: Directory is read-only, all hashes/flags present
Confidence=HIGH
<<<END PP‑FIX>>

##### END PARAMETER_SPEC #####

id=1 | gaps_closed=prior|calib|post|prov | notes=Parquet defect contract, manifest/CI enforced  
id=2 | gaps_closed=prior|calib|post|prov | notes=AUROC test, model/hyper lock, fail-fast  
id=3 | gaps_closed=prior|calib|post|prov | notes=θ corridor, YAML, statsmodels, CI/manifest  
id=4 | gaps_closed=prior|calib|post|prov | notes=barcode slope, YAML, PNG overlay, CI  
id=5 | gaps_closed=prior|calib|post|prov | notes=SHA-1 mapping, validate_licences.py, manifest  
id=6 | gaps_closed=prior|calib|post|prov | notes=Directory immutability, hashgate URI, manifest  
<<PS‑END>>
