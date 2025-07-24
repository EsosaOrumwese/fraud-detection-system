## Subsegment 4B: Validation without bullet points

| Artefact Class                | Path Pattern                              | SemVer Field | Digest Field             |
| ----------------------------- | ----------------------------------------- | ------------ | ------------------------ |
| Artefact Registry YAML        | `artefact_registry.yaml`                  | N/A          | N/A                      |
| Validation Configuration      | `config/validation_conf.yml`              | `version`    | `validation_conf_digest` |
| Footfall Coefficients         | `config/footfall_coefficients.yaml`       | `version`    | `footfall_coeff_digest`  |
| Barcode Bounds                | `config/barcode_bounds.yml`               | `version`    | `barcode_bounds_digest`  |
| Transaction Schema JSON       | `schemas/transaction_schema.json`         | N/A          | `schema_digest`          |
| Zoneinfo Version YAML         | `config/zoneinfo_version.yml`             | N/A          | `zoneinfo_digest`        |
| Time‑Zone Shapefile           | `tz_world_2025a.shp`                      | N/A          | `tz_polygon_digest`      |
| Site Catalogue Parquet        | `{dataset_root}/site_catalogue/*.parquet` | N/A          | `creator_param_hash`     |
| Transaction Catalogue Parquet | `{dataset_root}/transactions/*.parquet`   | N/A          | `creator_param_hash`     |
| RNG Audit Log                 | `{dataset_root}/logs/rng_trace.log`       | N/A          | `rng_trace_digest`       |

