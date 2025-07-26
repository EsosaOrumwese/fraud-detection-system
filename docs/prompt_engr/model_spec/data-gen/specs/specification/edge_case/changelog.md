## [1A.1.0] – 2025-07-26  
### Added  
- Complete Edge-Case Catalogue for **1A** capturing every missing artefact, config or parameter in the “merchants → physical sites” flow (EC IDs 1–7).  
- Edge-Case Spec Writer blocks (IDs 1–7) closing all detection, recovery, idempotence and monitoring gaps for 1A.  
### Changed  
- Refined CF prompt to pick up inline YAML/CSV path patterns specific to sub-segment 1A.  
- Harmonized interface_affected naming to match module/function conventions.  
### Fixed  
- Addressed a missed “missing site_id seed column” failure by adding an EC block.  
- Corrected Detection_gap logic for zero-traffic and missing manifest fields.  
### Removed  
- Deprecated placeholder anchors in earlier CF runs.  
### Breaking  
- New EC-FIX format (strict ordering) may require downstream tasks to update parsing logic.  

## [1B.1.0] – 2025-07-26  
### Added  
- Edge-Case Catalogue for **1B** covering missing routing/YAML artefacts, RNG policy, manifest digests, temporal anomalies (leap seconds) and audit retention (EC 1–13).  
- EC-FIX blocks 1–13 specifying deterministic recovery, idempotence guarantees and CI test injections.  
### Changed  
- Prompt templates updated to include “recovery_gap” and “metrics_gap” flags.  
### Fixed  
- Closed gaps for missing `weight_digest`, `cdn_alias_digest` and `validation_config_digest`.  
- Corrected Severity assignments for audit log retention.  
### Removed  
- Old “partial recovery” placeholder actions.  
### Breaking  
- Expanded EC block headers now include both Stage and Severity fields.  

## [2A.1.0] – 2025-07-26  
### Added  
- Edge-Case Catalogue for **2A** capturing missing time-zone derivation artefacts, leap-second handling and schema drift (EC 1–14).  
- Recovery specs (EC-FIX 1–14) enforcing abort on missing `zoneinfo_version.yml`, bounding valid_from ranges and RIPEMD digest checks.  
### Changed  
- Detection logic for missing IANA-2024a releases moved to CF rules.  
### Fixed  
- Filled prior holes in timezone boundary flip detection.  
### Removed  
- Ambiguous DST-fold skip notes without concrete injection tests.  
### Breaking  
- CF now requires explicit “expected_format” for each temporal artefact.  

## [2B.1.0] – 2025-07-26  
### Added  
- Edge-Case Catalogue for **2B** routing transactions through sites, covering alias manifests, CSV ordering, virtual routing configs and audit steps (EC 1–13).  
- Spec Writer blocks 1–13 guaranteeing deterministic failure recovery and idempotence.  
### Changed  
- Standardized test_type to {unit, fuzz, CI} across all EC entries.  
### Fixed  
- Closed detection_gap for missing `rng_policy.yml` in corporate-day derivation.  
### Removed  
- Early CF prompt that omitted “Context” field.  
### Breaking  
- CF merge-duplicates logic now OR-ing gaps instead of concatenating anchors.  

## [3A.1.0] – 2025-07-26  
### Added  
- Edge-Case Catalogue for **3A** “Capturing cross-zone merchants,” identifying missing YAMLs, CSVs, Parquets, and RNG proofs (EC 1–14).  
- EC-FIX blocks 1–14 closing all detection/recovery/idempotence/monitoring gaps with CI injections.  
### Changed  
- Interface_affected entries normalized to `<Module>/<function>` format.  
### Fixed  
- Added missing proof document check for `docs/rng_proof.md`.  
- Ensured CSV schema validation on `country_major_zone.csv`.  
### Removed  
- Redundant “partial Parquet write” placeholder.  
### Breaking  
- Severity classification tightened: missing manifest fields now always HIGH.  

## [3B.1.0] – 2025-07-26  
### Added  
- Edge-Case Catalogue for **3B** “Special treatment for purely virtual merchants,” covering missing MCC rules, geocode bundles, CDN weights, raster files and crash-recovery logs (EC 1–16).  
- EC-FIX blocks 1–16 with full recovery specs, monitoring metrics and idempotence guarantees.  
### Changed  
- Test_injection descriptions enriched with exact file paths and module calls.  
### Fixed  
- Closed a gap in RFC-compliant CSV handling for `virtual_settlement_coords.csv`.  
- Clarified digest mismatch detection for `pelias_cached.sqlite`.  
### Removed  
- Ambiguous “scripts not yet implemented” entries.  
### Breaking  
- EC-FIX “backoff_sec” default changed from 0 to 5 for retryable database operations.  

## [4A.1.0] – 2025-07-26  
### Added  
- Edge-Case Catalogue for **4A** “Reproducibility and configurability,” capturing missing lockfiles, manifests, schemas, licence validations, Postgres failures and RNG traces (EC 1–11).  
- EC-FIX blocks 1–11 enforcing strict abort/retry semantics and immutability enforcement.  
### Changed  
- “Metrics_gap” flag name standardized across all CF prompts.  
### Fixed  
- Added missing CI job check for `bootstrap_validator.py`.  
- Ensured JSON Schema version enforcement via `schemas/<domain>.json`.  
### Removed  
- Deprecated S3-throttling placeholder in external dependencies.  
### Breaking  
- Merged detection and error_code fields into a single deterministic section.  

## [4B.1.0] – 2025-07-26  
### Added  
- Edge-Case Catalogue for **4B** “Validation without bullet points,” covering all validation stages: Parquet integrity, tz-world, schema, adversarial drift, semantic congruence, barcode bounds, licence logs and final manifest flags (EC 1–19).  
- EC-FIX blocks 1–19 providing complete recovery, idempotence, monitoring and test pathways.  
### Changed  
- “Expected_format” entries now uniformly specify file extension and content requirements.  
### Fixed  
- Filled gaps for missing `barcode_failure_<merchant_id>.png` overlays.  
- Enforced uniqueness constraint checks in Postgres `datasets` catalog.  
### Removed  
- Manual CI pass-flag note in initial prompt.  
### Breaking  
- Introduction of split CF/SW token management markers (`<<EC-CONTINUE>>`) may require pipeline updates.