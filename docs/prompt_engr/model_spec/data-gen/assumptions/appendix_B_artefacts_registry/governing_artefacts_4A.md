## Subsegment 4A: Reproducibility and configurability

| Artefact Class                     | Path Pattern                                                    | SemVer Field | Digest Field                |
|------------------------------------|-----------------------------------------------------------------|--------------|-----------------------------|
| Docker Lockfile                    | `Dockerfile.lock`                                               | N/A          | N/A                         |
| Artefact Registry YAML             | `artefact_registry.yaml`                                        | N/A          | N/A                         |
| Hurdle Coefficients                | `config/hurdle_coefficients.yaml`                               | `version`    | `hurdle_coeff_digest`       |
| NB Coefficients                    | `config/nb_coefficients.yaml`                                   | `version`    | `nb_coeff_digest`           |
| Cross‑Border Hyperparams           | `config/crossborder_hyperparams.yaml`                           | `version`    | `crossborder_hyp_digest`    |
| Footfall Coefficients              | `config/footfall_coefficients.yaml`                             | `version`    | `footfall_coeff_digest`     |
| Routing Day Effect                 | `config/routing_day_effect.yml`                                 | `version`    | `gamma_variance_digest`     |
| Winsorisation Policy               | `config/winsor.yml`                                             | `version`    | `winsor_digest`             |
| Fallback Policy                    | `config/fallback_policy.yml`                                    | `version`    | `fallback_policy_digest`    |
| Zone Floor Constraints             | `config/zone_floor.yml`                                         | `version`    | `zone_floor_digest`         |
| Country‑Zone Alphas                | `config/country_zone_alphas.yaml`                               | `version`    | `zone_alpha_digest`         |
| Calibration Slice Config           | `config/calibration_slice_config.yml`                           | `version`    | `calibration_slice_digest`  |
| Cross‑Zone Validation              | `config/cross_zone_validation.yml`                              | `version`    | `cross_zone_val_digest`     |
| CDN Country Weights                | `config/cdn_country_weights.yaml`                               | `version`    | `cdn_weights_digest`        |
| Validation Configuration           | `config/validation_conf.yml`                                    | `version`    | `validation_conf_digest`    |
| Transaction Schema AVSC            | `schemas/transaction_schema.avsc`                               | N/A          | `schema_digest`             |
| Domain JSON Schemas                | `schemas/<domain>.json`                                         | N/A          | `schema_<domain>_digest`    |
| Spatial Blend Config               | `spatial_blend.yaml`                                            | `version`    | `spatial_blend_digest`      |
| HRSL Population Rasters            | `artefacts/priors/hrsl_pop_100m_{ISO}.tif`                      | N/A          | `hrsl_pop_digest`           |
| OSM Roads                          | `artefacts/priors/osm_primary_roads_*.pbf`                      | N/A          | `osm_roads_digest`          |
| Airport Boundaries                 | `artefacts/priors/iata_airport_boundaries_*.geojson`            | N/A          | `airport_boundaries_digest` |
| WorldPop Fallback                  | `artefacts/priors/worldpop_fallback_{ISO}.tif`                  | N/A          | `worldpop_fallback_digest`  |
| Spatial Manifest JSON              | `spatial_manifest.json`                                         | N/A          | `spatial_manifest_digest`   |
| Timezone Shapefile                 | `tz_world_2025a.shp`                                            | N/A          | `tz_polygon_digest`         |
| Timezone Data Archive              | `tzdata2025a.tar.gz`                                            | N/A          | `tzdata_digest`             |
| Timezone Overrides YAML            | `tz_overrides.yaml`                                             | `version`    | `tz_overrides_digest`       |
| Timezone Nudge Config              | `tz_nudge.yml`                                                  | `version`    | `tz_nudge_digest`           |
| Zoneinfo Version YAML              | `zoneinfo_version.yml`                                          | N/A          | `zoneinfo_version_digest`   |
| Network‑Share Vectors              | `artefacts/network_share_vectors/settlement_shares_*.parquet`   | N/A          | `settlement_share_digest`   |
| Currency‑Country Shares            | `artefacts/currency_country_split/ccy_country_shares_*.parquet` | N/A          | `currency_country_digest`   |
| MCC Channel Rules YAML             | `config/mcc_channel_rules.yaml`                                 | `version`    | `virtual_rules_digest`      |
| Virtual Settlement Coordinates CSV | `virtual_settlement_coords.csv`                                 | N/A          | `settlement_coord_digest`   |
| CDN Edge Weights YAML              | `config/virtual/cdn_country_weights.yaml`                       | `version`    | `cdn_weights_digest`        |
| Alias Tables NPZ                   | `alias/*.npz`                                                   | N/A          | `alias_digest`              |
| Edge Catalogue Parquet             | `edge_catalogue/*.parquet`                                      | N/A          | `edge_catalogue_digest`     |


### Integrated Additions and Enforcement for Subsegment 4A

#### A. Artefact, Source, Manifest, and Provenance Registry

Add the following entries to your artefact table (or beneath as a supplementary block):

| Artefact Class        | Path Pattern / Example                    | SemVer Field | Digest Field                  | Notes                                                                        |
|-----------------------|-------------------------------------------|--------------|-------------------------------|------------------------------------------------------------------------------|
| **Build Manifest**    | `/tmp/build.manifest`                     | N/A          | `build_manifest_digest`       | Generated at every build; must be registered, immutable, and row-referenced. |
| **Live Manifest**     | `<export_dir>/manifest_<hash>.json`       | N/A          | `live_manifest_digest`        | Live reference manifest, must match all row provenance.                      |
| **Pipeline Script**   | `pipeline_launcher.sh`                    | N/A          | `script_digest`               | Governs the execution pipeline; must be hash-captured.                       |
| **Source SHA/Branch** | (from `git rev-parse HEAD`, `git branch`) | N/A          | `source_sha`, `source_branch` | Recorded in manifest, referenced in every output row.                        |
| **Container Hash**    | `Dockerfile.lock`                         | N/A          | `container_sha`               | Immutable pipeline/container build image.                                    |

---

#### B. Output, Validation, and Forensic Artefact Registry

Explicitly register all required validation, CI, and audit logs—each governed, hash-tracked, and blocking for build/merge on failure or omission:

| Artefact Class                 | Path Pattern / Example                                                 | SemVer Field | Digest Field                 | Notes                                                        |
|--------------------------------|------------------------------------------------------------------------|--------------|------------------------------|--------------------------------------------------------------|
| **Bootstrap Histograms**       | `validation/bootstrap_*.png`, `validation/bootstrap_*.csv`             | N/A          | `bootstrap_digest`           | Confidence, dispersion, and statistical envelope validation. |
| **Geospatial Conformance**     | `validation/geo_conformance_*.csv`, `validation/geo_conformance_*.png` | N/A          | `geo_conformance_digest`     | Footfall and spatial regression checks.                      |
| **Footfall Regression**        | `validation/footfall_regression_*.csv`                                 | N/A          | `footfall_regression_digest` | Over-dispersion and GLM validation artefacts.                |
| **AUROC Indistinguishability** | `validation/auroc_indistinguishability_*.csv`                          | N/A          | `auroc_digest`               | Adversarial and indistinguishability validation.             |
| **DST Validation/Edge**        | `validation/dst_failures.csv`                                          | N/A          | `dst_failures_digest`        | DST gap and fold validation.                                 |
| **Structural Firewall**        | `validation/firewall_report.log`                                       | N/A          | `firewall_digest`            | Any blocked/malformed/structurally invalid record.           |
| **CI/Needs-Tune Flags**        | `validation/ci_needs_tune.log`, `validation/retune_hurdle.log`         | N/A          | `ci_tune_digest`             | CI-enforced retune and YAML/threshold alerts.                |
| **HashGate URI/Audit**         | `audit/hashgate_uri.txt`                                               | N/A          | `hashgate_uri_digest`        | Forensic trail and approval.                                 |

---

#### C. Licence Mapping and Enforcement

Explicitly extend the registry or notes with:

* Every artefact above **must be mapped to a licence file in `LICENSES/`**, with SHA-256 digest (`licence_digest`) enforced by CI.
* **The `artefact_registry.yaml:license_map`** is a governed field, and any omission, drift, or failure blocks merge.

---

#### D. Directory Immutability and Collision Enforcement

**Enforcement notes:**
* The export directory, named for the parameter-set hash, **must be set read-only at the OS/NFS layer after build. Any overwrite or second export for the same hash triggers a fatal collision error.**
* All directories and files must be registered, reference the build manifest and parameter-set hash, and be auditable.

---

#### E. Forensic/Audit Linkage and Row Provenance

* Every output artefact must record the manifest digest, source SHA/branch, container SHA, and parameter-set hash in schema metadata and row-level fields.
* **All output, validation, and forensic artefacts must be auditable by the HashGate URI and included in both build and live manifests.**

