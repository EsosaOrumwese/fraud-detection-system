## Subsegment 4B: Validation without bullet points

| Artefact Class                | Path Pattern                              | SemVer Field | Digest Field             |
|-------------------------------|-------------------------------------------|--------------|--------------------------|
| Artefact Registry YAML        | `artefact_registry.yaml`                  | N/A          | N/A                      |
| Validation Configuration      | `config/validation_conf.yml`              | `version`    | `validation_conf_digest` |
| Footfall Coefficients         | `config/footfall_coefficients.yaml`       | `version`    | `footfall_coeff_digest`  |
| Barcode Bounds                | `config/barcode_bounds.yml`               | `version`    | `barcode_bounds_digest`  |
| Transaction Schema JSON       | `schemas/transaction_schema.json`         | N/A          | `schema_digest`          |
| Zoneinfo Version YAML         | `config/zoneinfo_version.yml`             | N/A          | `zoneinfo_digest`        |
| Time‑Zone Shapefile           | `tz_world_2025a.shp`                      | N/A          | `tz_polygon_digest`      |
| Site Catalogue Parquet        | `{dataset_root}/site_catalogue/*.parquet` | N/A          | `creator_param_hash`     |
| Transaction Catalogue Parquet | `{dataset_root}/transactions/*.parquet`   | N/A          | `creator_param_hash`     |
| RNG Audit Log                 | `{dataset_root}/logs/rng_trace.log`       | N/A          | `rng_trace_digest`       |

### Additions to the Registry Table:

| Artefact Class            | Path Pattern                              | SemVer Field | Digest Field                | Notes                                                                                      |
|---------------------------|-------------------------------------------|--------------|-----------------------------|--------------------------------------------------------------------------------------------|
| Structural Failure Log    | `validation/structural_failure_*.parquet` | N/A          | `structural_failure_digest` | All null/type/structural errors, merge-blocking.                                           |
| AUROC Model Dump          | `validation/auroc_model_*.parquet`        | N/A          | `auroc_model_digest`        | Output of adversarial validation, merge-blocking on failure.                               |
| Misclassification Indices | `validation/misclassified_*.csv`          | N/A          | `misclassification_digest`  | Output from misclassified instance analysis, referenced in manifest.                       |
| Theta Violation PDF       | `validation/theta_violation_*.pdf`        | N/A          | `theta_violation_digest`    | Parameter/model out-of-confidence-region, merge-blocking.                                  |
| Barcode Failure Overlay   | `validation/barcode_failure_*.png`        | N/A          | `barcode_failure_digest`    | Visual barcode/convergence failure overlays, merge-blocking.                               |
| Validator Log             | `validation/validator.log`                | N/A          | `validator_log_digest`      | Main log for validator CI, referenced in PR/manifest.                                      |
| CI Result/Pass Artefact   | `validation/ci_validation_passed.flag`    | N/A          | `ci_validation_digest`      | Set to true only if all validation passes, referenced in manifest, blocks merge otherwise. |
| HashGate/Audit URI        | `validation/hashgate_uri.txt`             | N/A          | `hashgate_uri_digest`       | Audit endpoint, must be referenced in manifest, PR, and output schema.                     |
| Licence Validation Log    | `validation/licence_check.log`            | N/A          | `licence_log_digest`        | Output from automated licence checker; any failure blocks build/merge.                     |
| Read-only Export Flag     | `{dataset_root}/readonly.flag`            | N/A          | `readonly_flag_digest`      | Presence = directory is locked for writing; required for approval.                         |


#### Enforcement & Contract Notes :
* Every output, log, or artefact above must be written, hash-tracked, and referenced in the build manifest for parameter hash $P$.
* Any error log, failure overlay, or diagnostic output in the above set that is missing or non-passing blocks merge, triggers dataset quarantine, and must be auditable by HashGate.
* CI must reference the HashGate/Audit URI and poll for final approval before release.
* All governed artefacts, config files, and validation outputs must have an explicit licence mapping, with SHA-256 digest checked for every build/merge.
* Exported dataset directory is set read-only after build, and any collision for the same $P$, master seed, and timestamp triggers a fatal error.



