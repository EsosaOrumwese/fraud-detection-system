############################################################
#  PARAMETER CATALOGUE‑FINDER • Sub‑segment 4B             #
############################################################

--- PP 1 ---
Name: Structural validation error contract
Symbol: StructuralError, structural_failure_<parameter_hash>.parquet
Scope: validation
Prior_type: Deterministic contract (Parquet + CI, not stochastic)
Prior_specified: Yes
Calibration_recipe: Yes (validator, artefact_registry.yaml, manifest, CI script, schema check)
Posterior_validation: Yes (defect log, fail fast, merge-blocking, manifest digest)
Provenance_tag: Yes (structural_failure_<parameter_hash>.parquet, structural_failure_digest)
Units: log entry (failed row, RNG jump offset)
Default_policy: abort (first error halts pipeline, blocks merge)
Interface_consumer: validator, CI, audit, manifest, logs
Description: Every failed row or coordinate/time/schema defect triggers a halt, is written to structural_failure parquet, digest is merge-blocking.
Anchor: "If a single row fails any of these checks, the defect channel halts subsequent validation, writes the row and its context into structural_failure_<parameter_hash>.parquet, then raises a StructuralValidationError pinpointing the exact generator line..."
Context: "Coordinate plausibility pulls `lat, lon` if the merchant is physical, or `ip_latitude, ip_longitude` if virtual, and feeds them directly into the same tz‑world point‑in‑polygon lookup used during generation... If the returned `TZID` disagrees with the row’s recorded `tzid_operational`, a defect object is pushed into a synchronous defect channel... If a single row fails any of these checks..."
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
Name: Adversarial AUROC drift detection
Symbol: DistributionDriftDetected, auroc_model_*.parquet, misclassified_*.csv
Scope: validation
Prior_type: Deterministic contract (XGBoost, YAML, hyper-parameter lock)
Prior_specified: Yes
Calibration_recipe: Yes (validation_conf.yml, hyper-parameter lock, CI)
Posterior_validation: Yes (AUROC threshold, misclassified indices, manifest hash, fail fast)
Provenance_tag: Yes (auroc_model_*.parquet, misclassification_digest, validation_conf_digest)
Units: AUROC (float), indices (CSV)
Default_policy: abort (if AUROC > 0.55 or artefact/log missing)
Interface_consumer: validator, CI, audit, manifest, logs
Description: Windowed AUROC adversarial test (AUROC > 0.55 triggers DistributionDriftDetected and halts pipeline, merges model dump and indices).
Anchor: "AUROC is evaluated once every million rows; as soon as it exceeds 0.55, the validator short‑circuits, dumps the model dump, the misclassified example indices, and the seed state of the RNG to /tmp/auroc_failure, then throws DistributionDriftDetected."
Context: "Streams...through a sliding window of 200 000 rows—half synthetic, half real reference data—embedding each row into a six‑dimensional feature space... AUROC is evaluated once every million rows..."
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
Name: Semantic GLM dispersion corridor
Symbol: θ, glm_theta_violation.pdf
Scope: validation
Prior_type: Corridor (YAML, Poisson GLM, channel-specific)
Prior_specified: Yes
Calibration_recipe: Yes (footfall_coefficients.yaml, statsmodels, empirical corridor, CI)
Posterior_validation: Yes (GLM fit, θ-corridor, PDF artefact, fail fast)
Provenance_tag: Yes (footfall_coefficients.yaml, theta_violation_digest)
Units: θ (dispersion, float)
Default_policy: abort (θ out of corridor triggers error, CI block, needs_recalibration flag)
Interface_consumer: validator, CI, semantic_glm.py, audit, manifest
Description: Poisson GLM θ estimate for footfall-thruput fit; must be in corridor [1,2] for CP, [2,4] for CNP or build fails.
Anchor: "The dispersion estimate θ must reside within the corridor specified in footfall_coefficients.yaml—1 to 2 for card‑present channels, 2 to 4 for CNP. If θ escapes this corridor, the validator labels the YAML with a Git attribute needs_recalibration, emits glm_theta_violation.pdf, and raises ThetaOutOfRange..."
Context: "A Poisson regression with hour‑of‑day spline and merchant‑day random intercepts is run in‑memory using statsmodels; the dispersion estimate θ is compared against the channel‑specific corridor promised by the LGCP variance calibration..."
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
Name: Barcode slope threshold
Symbol: barcode_bounds.yml, BarcodeSlopeError, barcode_failure_*.png
Scope: validation
Prior_type: Physical-law corridor (YAML, Hough transform)
Prior_specified: Yes
Calibration_recipe: Yes (barcode_bounds.yml, empirical slope, CI)
Posterior_validation: Yes (Hough transform, PNG overlay, manifest hash, fail fast)
Provenance_tag: Yes (barcode_bounds.yml, barcode_failure_digest)
Units: slope (offsets per UTC hour, float)
Default_policy: abort (slope out of bounds triggers PNG, fail, merge block)
Interface_consumer: validator, barcode.py, CI, audit, manifest
Description: Physics-based acceptance corridor for barcode slope; fails if slope falls outside [-1, -0.5].
Anchor: "Physics says the Earth rotates fifteen degrees each hour... If a merchant’s dominant slope falls outside −1 to −0.5, the barcode inspection fails. When it fails, the validator renders a 700 × 300 PNG showing the heat‑map with a red line through the detected slope and stores it under barcode_failure_<merchant_id>.png."
Context: "The validator bins each merchant’s events on a two‑dimensional plane of UTC hour (0–23) versus local_time_offset in minutes. Using a fast Hough transform it extracts the dominant line... Physics says... If a merchant’s dominant slope falls outside −1 to −0.5, the barcode inspection fails..."
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
Name: Licence mapping and audit
Symbol: artefact_registry.yaml, licence_digests
Scope: validation
Prior_type: Deterministic mapping (SHA-1 digest contract)
Prior_specified: Yes
Calibration_recipe: Yes (validate_licences.py, manifest/artefact_registry.yaml, CI, audit)
Posterior_validation: Yes (SHA-1 mapping check, manifest/licence_log_digest, fail fast)
Provenance_tag: Yes (artefact_registry.yaml, licence_log_digest)
Units: SHA-1 digest (hex string)
Default_policy: abort (licence mismatch, missing, or unreferenced)
Interface_consumer: validator, CI, audit, manifest, logs
Description: Every artefact must have mapped SHA-1 licence; CI blocks merge on any mapping error.
Anchor: "Every artefact path logged in the manifest has an accompanying licence path; the validator recomputes the SHA‑1 of each licence file, compares it with the SHA‑1 digests recorded in the manifest’s licence_digests field via validate_licences.py, raising LicenceMismatchError on any mismatch."
Context: "Every artefact path logged in the manifest has an accompanying licence path... validate_licences.py recomputes SHA-1 digests for each licence and compares them to the licence_digests field in the manifest; any mismatch raises LicenceMismatchError, preventing datasets whose legal pedigree has drifted."
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
Name: Directory immutability and audit hash/URI enforcement
Symbol: validation/hashgate_uri.txt, readonly.flag
Scope: validation
Prior_type: Deterministic (SHA-256, URI, file lock)
Prior_specified: Yes
Calibration_recipe: Yes (validator, audit, manifest, CI, NFS lock)
Posterior_validation: Yes (read-only flag, manifest/audit hash, CI poll/lock)
Provenance_tag: Yes (validation/hashgate_uri.txt, readonly.flag, hashgate_uri_digest, readonly_flag_digest)
Units: URI (string), SHA-256 digest, file presence
Default_policy: abort (if missing, not locked, or URI not referenced)
Interface_consumer: validator, CI, NFS, merge/release script, manifest
Description: Final directory must be read-only, audit URI must be referenced in manifest, and poll for approval; any unlock or collision aborts.
Anchor: "When all these intertwined narratives finish without raising an exception, the validator appends validation_passed=true to the manifest, hashes the entire validation/<parameter_hash>/ directory, uploads the resulting bundle to HashGate at /hashgate/<parameter_hash>/<master_seed>, and logs the HTTP status code."
Context: "When all these intertwined narratives finish without raising an exception, the validator appends validation_passed=true to the manifest, hashes the entire validation/<parameter_hash>/ directory, uploads the resulting bundle to HashGate at /hashgate/<parameter_hash>/<master_seed>..."
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

<<PP‑END>>
