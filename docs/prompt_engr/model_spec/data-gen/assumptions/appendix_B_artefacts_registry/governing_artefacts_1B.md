## Subsegment 1B: Placing outlets on the planet
Below is the complete list of every spatial and policy artefact referenced in this sub‑segment. Each entry must appear in `spatial_manifest.json` with the indicated metadata; any change to the artefact file, its semver or its digest will produce a new `spatial_manifest_digest`.

| ID / Key                               | Path Pattern                                                | Role                                              | Semver Field          | Digest Field               |
|----------------------------------------|-------------------------------------------------------------|---------------------------------------------------|-----------------------|----------------------------|
| **spatial_manifest.json**              | `spatial_manifest.json`                                     | Composite listing of all spatial artefacts        | n/a (manifest header) | `composite_spatial_digest` |
| **spatial_blend.yaml**                 | `spatial_blend.yaml`                                        | Prior blending coefficients                       | `semver`              | `sha256_digest`            |
| **hrsl_pop_100m**                      | `artefacts/priors/hrsl/2020_v1.2/{ISO2}.tif`                | 100 m Meta/HRSL population raster                 | `semver`              | `sha256_digest`            |
| **osm_primary_roads**                  | `artefacts/priors/osm_primary_roads_{planet_YYYYMMDD}.gpkg` | Filtered OSM primary‑road network                 | (`snapshot_date`)     | `sha256_digest`            |
| **aadt_counts_compiled_v1.parquet**    | `artefacts/priors/aadt_counts_compiled_v1.parquet`          | Government‑sourced AADT table for roads           | `semver`              | `sha256_digest`            |
| **iata_airport_boundaries_v2023Q4**    | `artefacts/priors/iata_airport_boundaries_v2023Q4.geojson`  | Commercial‑airport boundary polygons              | `semver`              | `sha256_digest`            |
| **suburban_pop_density_2022_v1**       | `artefacts/priors/suburban_pop_density_2022_v1.tif`         | Suburban population density raster                | `semver`              | `sha256_digest`            |
| **road_traffic_density_2022_v2**       | `artefacts/priors/road_traffic_density_2022_v2.tif`         | Road traffic density raster                       | `semver`              | `sha256_digest`            |
| **worldpop_fallback_2023Q4**           | `artefacts/priors/worldpop/2023Q4/{ISO2}.tif`               | WorldPop 1 km fallback population raster          | (`vintage`)           | `sha256_digest`            |
| **tz_world_polygons_v2024a**           | `artefacts/priors/tz_world_polygons_v2024a.geojson`         | IANA time‑zone polygon boundaries                 | `semver`              | `sha256_digest`            |
| **tz_world_metadata.json**             | `tz_world_metadata.json`                                    | Zone→ISO mapping & enclave whitelist              | `semver`              | `sha256_digest`            |
| **capitals_dataset_2024.parquet**      | `artefacts/priors/capitals_dataset_2024.parquet`            | Country capital coordinates                       | `semver`              | `sha256_digest`            |
| **natural_earth_land_10m_v5.1.2**      | `artefacts/priors/natural_earth_land_10m_v5.1.2.geojson`    | Land‑mask polygon for dry‑land filtering          | `semver`              | `sha256_digest`            |
| **footfall_coefficients.yaml**         | `footfall_coefficients.yaml`                                | κ and σ per (MCC, channel) + calibration metadata | `semver`              | `sha256_digest`            |
| **winsor.yml**                         | `winsor.yml`                                                | Outlier clipping policy                           | `semver`              | `sha256_digest`            |
| **fallback_policy.yml**                | `fallback_policy.yml`                                       | Fallback rate thresholds & overrides              | `semver`              | `sha256_digest`            |
| **calibration_slice_config.yml**       | `calibration_slice_config.yml`                              | Footfall calibration slice specification          | `semver`              | `sha256_digest`            |
| **osm_planet_snapshot_{YYYYMMDD}.pbf** | `artefacts/priors/osm_planet_snapshot_{YYYYMMDD}.pbf`       | OSM planet extract for road graph construction    | `snapshot_date`       | `sha256_digest`            |
| **osm_ch_graph_{snapshot}.bin**        | `artefacts/priors/osm_ch_graph_{snapshot}.bin`              | Contraction‑hierarchies graph for road distances  | `semver`              | `sha256_digest`            |

*Notes:*

* All pattern entries are case‑sensitive.
* Fields in parentheses (e.g., `snapshot_date`, `vintage`) are embedded in the file’s metadata sidecar and must be captured in the manifest entry.
* Any addition, removal, or version change of an artefact must follow semver rules and will automatically refresh the `spatial_manifest_digest` via CI.
* The manifest itself is authored at `spatial_manifest.json` and should list each artefact row with the above columns plus optional metadata (e.g., file size, byte count).

### **A. Additions to Artefact Registry Table**

Add the following rows **below the main artefact table** to explicitly register all critical logs, outputs, and schema/contract artefacts mentioned in your narrative/assumptions:

| ID / Key                         | Path Pattern                                                                            | Role                                                                           | Semver Field    | Digest Field              |
| -------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | --------------- | ------------------------- |
| **placement_audit.log**         | `logs/placement_audit.log`                                                              | Audit log for all spatial sampling, Fenwick, and placement ops                 | n/a             | n/a (run-specific)        |
| **diagnostic_metrics.parquet**  | `logs/diagnostic_metrics.parquet`                                                       | Nightly metrics for acceptance rates, fallback counts, CUSUM                   | n/a             | n/a (run-specific)        |
| **site_catalogue**              | `site_catalogue/partition_date=YYYYMMDD/merchant_id={id}/site_id={site_id}.parquet`     | Final spatial catalogue output for each merchant/site, all fields (see schema) | Manifest semver | `spatial_manifest_digest` |
| **site_catalogue_schema.json** | `site_catalogue_schema.json`                                                            | Parquet schema descriptor for output catalogue                                 | `semver`        | `sha256_digest`           |
| **schema_version.txt**          | `schema_version.txt`                                                                    | Output schema versioning, required for immutability contract                   | `semver`        | n/a                       |
| **calib_dist_digest.txt**      | `calib_dist_digest.txt`                                                                 | Digest for calibration slice distribution (see footfall cal.)                  | n/a             | `sha256_digest`           |
| **placement_temp_files**       | `site_catalogue/partition_date=YYYYMMDD/merchant_id={id}/site_id={site_id}.parquet.tmp` | Crash-tolerant, idempotent temp files for site catalogue rows                  | n/a             | n/a (run-specific)        |

### **B. Explicit Policy/Manifest Contract**

**Manifest/Whitelist Policy**

* Only artefacts and file patterns explicitly listed in `spatial_manifest.json` or `allow_patterns` are permitted at build time.
* Any stray file, missing artefact, or unlisted pattern aborts the build.
* Any addition/removal triggers a required semver bump, which CI must verify.

**Immutability & Downstream Contract**

* All output rows in the site catalogue must have identical `spatial_manifest_digest` matching the manifest at the catalogue root.
* Any downstream read or transform must verify this digest and abort if it does not match—immutable contract is enforced via schema and manifest checks.

**Event/Audit Log Requirements**

* Every site placement, resample, Fenwick build, failure, or fallback event must be logged in `placement_audit.log` with full event schema (see maths appendix for fields).
* Any missing or duplicate mandatory event is a structural validation failure; no partial or orphaned output rows may be published.

**Crash Tolerance/Recovery**

* Partial temp files from interrupted writes must never be promoted to final output; crash recovery protocol is to revalidate, skip existing `.parquet` files, and ensure only completed, validated rows are included.

### **C. Notes/Clarifications**

* Any change to the catalogue schema or artefact inventory requires a version bump for both `spatial_manifest.json` and `site_catalogue_schema.json`, ensuring downstream processes detect all lineage and schema changes.
* All logs and diagnostics (even if ephemeral/run-specific) must be captured in the build artefact manifest for full auditability and to enable reproducibility review.
