## Subsegment 4A: Reproducibility and configurability

| Artefact Class                     | Path Pattern                                                    | SemVer Field | Digest Field                |
| ---------------------------------- | --------------------------------------------------------------- | ------------ | --------------------------- |
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