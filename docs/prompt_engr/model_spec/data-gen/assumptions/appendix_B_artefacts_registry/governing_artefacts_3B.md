## Subsegment 3B: Special treatment for purely virtual merchants

| ID / Key                       | Path Pattern                                      | Role                                                                  | Semver Field              | Digest Field                   |
|--------------------------------|---------------------------------------------------|-----------------------------------------------------------------------|---------------------------|--------------------------------|
| **virtual_rules**              | `config/virtual/mcc_channel_rules.yaml`           | MCC→is_virtual policy ledger                                          | `semver`                  | `virtual_rules_digest`         |
| **settlement_coords**          | `artefacts/virtual/virtual_settlement_coords.csv` | Settlement‑node coordinate & evidence URLs                            | `settlement_coord_semver` | `settlement_coord_digest`      |
| **pelias_bundle**              | `artefacts/geocode/pelias_cached.sqlite`          | Offline Pelias geocoder bundle                                        | `semver`                  | `pelias_digest`                |
| **cdn_weights**                | `config/virtual/cdn_country_weights.yaml`         | CDN edge‑weight policy                                                | `semver`                  | `cdn_weights_digest`           |
| **hrsl_raster**                | `artefacts/rasters/hrsl_100m.tif`                 | Facebook HRSL 100m population raster                                  | `semver`                  | `hrsl_digest`                  |
| **edge_catalogue_parquet**     | `edge_catalogue/<merchant_id>.parquet`            | Per‑merchant virtual edge node table                                  | n/a                       | `edge_digest`                  |
| **edge_catalogue_index**       | `edge_catalogue/edge_catalogue_index.csv`         | Digest registry for edge catalogues                                   | `semver`                  | `edge_catalogue_index_digest`  |
| **rng_policy**                 | `config/routing/rng_policy.yml`                   | Philox RNG key derivation policy                                      | `semver`                  | `cdn_key_digest`               |
| **virtual_validation**         | `config/virtual/virtual_validation.yml`           | CI thresholds for virtual‑merchant validation                         | `semver`                  | `virtual_validation_digest`    |
| **transaction_schema**         | `schema/transaction_schema.avsc`                  | AVSC schema defining virtual‑flow fields                              | `semver`                  | `transaction_schema_digest`    |
| **virtual_logging**            | `config/logging/virtual_logging.yml`              | Logging rotation & retention policy for virtual builders              | `semver`                  | `virtual_logging_digest`       |
| **licence_files_virtual**      | `LICENSES/*.md`                                   | Licence texts for virtual‑merchant artefacts                          | n/a                       | `licence_digests_virtual`      |
| **edge_catalogue_schema**      | `edge_catalogue_schema.json`                      | Parquet schema for edge_catalogue output                              | schema_version            | `edge_catalogue_schema_digest` |
| **virtual_error_log**          | `logs/virtual_error.log`                          | Log of runtime/CI errors, drift, non-reproducibility, cutoff failures | Manifest semver           | (run-specific)                 |
| **edge_progress_log**          | `logs/edge_progress.log`                          | Build progress/crash recovery log for edge creation                   | Manifest semver           | (run-specific)                 |
| **test_virtual_rules_log**     | `logs/test_virtual_rules.log`                     | Property-based/CI test results for all virtual merchant rules         | Manifest semver           | (run-specific)                 |
| **verify_coords_evidence_log** | `logs/verify_coords_evidence.log`                 | Log from coordinate/evidence validation test suite                    | Manifest semver           | (run-specific)                 |
| **test_cdn_key_log**           | `logs/test_cdn_key.log`                           | CDN key/weight validation log                                         | Manifest semver           | (run-specific)                 |
| **test_virtual_universe_log**  | `logs/test_virtual_universe.log`                  | Log from universe replay validation                                   | Manifest semver           | (run-specific)                 |
| **test_cutoff_time_log**       | `logs/test_cutoff_time.log`                       | Log from cutoff time and cutpoint assertion tests                     | Manifest semver           | (run-specific)                 |
| **validate_virtual_log**       | `logs/validate_virtual.log`                       | Output from main validator over all virtual merchant pipeline rules   | Manifest semver           | (run-specific)                 |
| **virtual_universe_hash**      | `edge_catalogue/{merchant_id}_virtual_hash.txt`   | Hash sentinel for virtual merchant artefacts                          | Manifest semver           | <run-specific>                 |


**Notes:**

* Any entry marked **n/a** in the Semver column means the artefact has no inline version field; it is frozen purely by its digest.
* Replace `<merchant_id>` with the zero‑padded merchant identifier when resolving path patterns.
* All paths use Unix‑style forward slashes and are case‑sensitive.
* The manifest keys shown are the exact JSON fields in your `manifest*.json`; CI tests byte‑compare those against live artefacts.
* Adding, removing or changing any of these artefacts (path, semver or digest) will automatically bump the manifest digest and fail CI until revalidated.
* Any missing, empty, or failed log above is a build-stopper and must be referenced in the manifest for every run.**
* All output tables (`edge_catalogue/<merchant_id>.parquet`) must be schema-checked against `edge_catalogue_schema.json` and include all required fields and order.
* Any change in manifest, schema, YAML, or digest triggers a manifest refresh and aborts queued or running builds until validated.
* Every YAML/CSV/NPZ/Parquet artefact must map to a tracked file in `LICENSES/`, with SHA-256 digest checked every CI run.
* Any detected drift, non-reproducibility, or hidden state must be error-logged and causes the build to abort.
