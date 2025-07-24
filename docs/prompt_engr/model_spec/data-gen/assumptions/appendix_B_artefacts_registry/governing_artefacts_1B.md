## Subsegment 1B: Placing outlets on the planet
Below is the complete list of every spatial and policy artefact referenced in this sub‑segment. Each entry must appear in `spatial_manifest.json` with the indicated metadata; any change to the artefact file, its semver or its digest will produce a new `spatial_manifest_digest`.

| ID / Key                                  | Path Pattern                                                | Role                                              | Semver Field          | Digest Field               |
|-------------------------------------------|-------------------------------------------------------------|---------------------------------------------------|-----------------------|----------------------------|
| **spatial\_manifest.json**                | `spatial_manifest.json`                                     | Composite listing of all spatial artefacts        | n/a (manifest header) | `composite_spatial_digest` |
| **spatial\_blend.yaml**                   | `spatial_blend.yaml`                                        | Prior blending coefficients                       | `semver`              | `sha256_digest`            |
| **hrsl\_pop\_100m**                       | `artefacts/priors/hrsl/2020_v1.2/{ISO2}.tif`                | 100 m Meta/HRSL population raster                 | `semver`              | `sha256_digest`            |
| **osm\_primary\_roads**                   | `artefacts/priors/osm_primary_roads_{planet_YYYYMMDD}.gpkg` | Filtered OSM primary‑road network                 | (`snapshot_date`)     | `sha256_digest`            |
| **aadt\_counts\_compiled\_v1.parquet**    | `artefacts/priors/aadt_counts_compiled_v1.parquet`          | Government‑sourced AADT table for roads           | `semver`              | `sha256_digest`            |
| **iata\_airport\_boundaries\_v2023Q4**    | `artefacts/priors/iata_airport_boundaries_v2023Q4.geojson`  | Commercial‑airport boundary polygons              | `semver`              | `sha256_digest`            |
| **suburban\_pop\_density\_2022\_v1**      | `artefacts/priors/suburban_pop_density_2022_v1.tif`         | Suburban population density raster                | `semver`              | `sha256_digest`            |
| **road\_traffic\_density\_2022\_v2**      | `artefacts/priors/road_traffic_density_2022_v2.tif`         | Road traffic density raster                       | `semver`              | `sha256_digest`            |
| **worldpop\_fallback\_2023Q4**            | `artefacts/priors/worldpop/2023Q4/{ISO2}.tif`               | WorldPop 1 km fallback population raster          | (`vintage`)           | `sha256_digest`            |
| **tz\_world\_polygons\_v2024a**           | `artefacts/priors/tz_world_polygons_v2024a.geojson`         | IANA time‑zone polygon boundaries                 | `semver`              | `sha256_digest`            |
| **tz\_world\_metadata.json**              | `tz_world_metadata.json`                                    | Zone→ISO mapping & enclave whitelist              | `semver`              | `sha256_digest`            |
| **capitals\_dataset\_2024.parquet**       | `artefacts/priors/capitals_dataset_2024.parquet`            | Country capital coordinates                       | `semver`              | `sha256_digest`            |
| **natural\_earth\_land\_10m\_v5.1.2**     | `artefacts/priors/natural_earth_land_10m_v5.1.2.geojson`    | Land‑mask polygon for dry‑land filtering          | `semver`              | `sha256_digest`            |
| **footfall\_coefficients.yaml**           | `footfall_coefficients.yaml`                                | κ and σ per (MCC, channel) + calibration metadata | `semver`              | `sha256_digest`            |
| **winsor.yml**                            | `winsor.yml`                                                | Outlier clipping policy                           | `semver`              | `sha256_digest`            |
| **fallback\_policy.yml**                  | `fallback_policy.yml`                                       | Fallback rate thresholds & overrides              | `semver`              | `sha256_digest`            |
| **calibration\_slice\_config.yml**        | `calibration_slice_config.yml`                              | Footfall calibration slice specification          | `semver`              | `sha256_digest`            |
| **osm\_planet\_snapshot\_{YYYYMMDD}.pbf** | `artefacts/priors/osm_planet_snapshot_{YYYYMMDD}.pbf`       | OSM planet extract for road graph construction    | `snapshot_date`       | `sha256_digest`            |
| **osm\_ch\_graph\_{snapshot}.bin**        | `artefacts/priors/osm_ch_graph_{snapshot}.bin`              | Contraction‑hierarchies graph for road distances  | `semver`              | `sha256_digest`            |

*Notes:*

* All pattern entries are case‑sensitive.
* Fields in parentheses (e.g., `snapshot_date`, `vintage`) are embedded in the file’s metadata sidecar and must be captured in the manifest entry.
* Any addition, removal, or version change of an artefact must follow semver rules and will automatically refresh the `spatial_manifest_digest` via CI.
* The manifest itself is authored at `spatial_manifest.json` and should list each artefact row with the above columns plus optional metadata (e.g., file size, byte count).
