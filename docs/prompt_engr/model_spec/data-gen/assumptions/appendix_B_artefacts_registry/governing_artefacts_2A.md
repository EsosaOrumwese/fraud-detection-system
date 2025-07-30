## Subsegment 2A: Deriving the civil time zone (Integrated Registry)

| ID / Key                       | Path Pattern                                                             | Role                                                                                 | Semver Field                 | Digest Field                                              |
|--------------------------------|--------------------------------------------------------------------------|--------------------------------------------------------------------------------------|------------------------------|-----------------------------------------------------------|
| **tz_world_polygons_2025a**    | `artefacts/priors/tz_world/2025a/tz_world_2025a.*`                       | IANA time‑zone polygon shapefile and companion files                                 | `semver` (sidecar)           | component digests aggregated into **`tz_polygon_digest`** |
| **tzid_insertion_order**       | `artefacts/priors/tz_world/2025a/tzid_insertion_order.txt`               | Canonical lexicographic TZID list used when building STR‑tree                        | `semver`                     | `tzid_insertion_order_digest`                             |
| **tz_index_digest**            | `artefacts/priors/tz_world/2025a/tz_index_digest.txt`                    | STR-tree index digest (deterministic build, pickle protocol 5)                       | Manifest semver              | `tz_index_digest`                                         |
| **tz_nudge**                   | `config/timezone/tz_nudge.yml`                                           | Deterministic nudge distance ε                                                       | `semver`                     | `tz_nudge_digest`                                         |
| **tz_overrides**               | `config/timezone/tz_overrides.yaml`                                      | Manual mapping overrides for exceptional zones                                       | `semver`                     | `tz_overrides_digest`                                     |
| **locale_policy**              | `config/locale_policy.yaml`                                              | Pins Unicode collation for lexicographic TZID sort                                   | `semver`                     | `locale_policy_digest`                                    |
| **geometry_tolerance_policy**  | `config/numeric/geometry_tolerance_policy.yaml`                          | Max FP error in geometry ops                                                         | `semver`                     | `geometry_tol_digest`                                     |
| **timestamp_precision_policy** | `config/numeric/timestamp_precision_policy.yaml`                         | Millisecond truncation & rounding rules                                              | `semver`                     | `ts_precision_digest`                                     |
| **zoneinfo_version**           | `zoneinfo_version.yml`                                                   | IANA tzdata version descriptor                                                       | `semver` (`tzdata_version`)  | `tz_horizon_digest` (see horizon below)                   |
| **tzdata_archive**             | `artefacts/priors/tzdata/tzdata2025a.tar.gz`                             | Official IANA tzdata release archive                                                 | (in `zoneinfo_version.yml`)  | `tzdata_archive_digest`                                   |
| **simulation_horizon**         | `config/timezone/simulation_horizon.yml`                                 | Simulation start/end bounds for timeline extraction                                  | `semver`                     | `tz_horizon_digest`                                       |
| **rng_proof**                  | `docs/rng_proof.md`                                                      | Formal proof of RNG‑stream isolation                                                 | Git commit (ref in manifest) | `rng_proof_digest`                                        |
| **output_catalogue**           | `output/site_catalogue/partition_date=*/merchant_id=*/site_id=*.parquet` | Output catalogue: must include `nudge_lat`, `nudge_lon`, `TZID`, fold, offsets, etc. | Manifest semver, schema      | `tz_polygon_digest` (must match input artefact lineage)   |
| **output_catalogue_schema**    | `output/site_catalogue_schema.json`                                      | Parquet schema descriptor for site catalogue output                                  | schema_version               | `sha256_digest`                                           |
| **tz_lookup_events**           | `logs/timezone/{run_id}/tz_lookup_events.jsonl`                          | Per‑site audit of hit list, nudge, override flag                                     | Manifest semver              | run‑specific                                              |
| **tz_lookup_failures**         | `logs/timezone/{run_id}/tz_lookup_error.jsonl`                           | Rows that raise `TimeZoneLookupError`                                                | Manifest semver              | run‑specific                                              |
| **override_application_log**   | `logs/timezone/{run_id}/tz_override_applied.jsonl`                       | When an override supersedes polygon lookup                                           | Manifest semver              | run‑specific                                              |
| **audit_log**                  | `logs/timezone/{run_id}/tz_nudge_applied.jsonl`                          | ε‑nudge vector & before/after hit sets                                               | Manifest semver              | run‑specific                                              |
| **ci_validation_log**          | `logs/ci_override_validation.log`                                        | Nightly validation: override drift, manifest checks                                  | Manifest semver              | run‑specific                                              |
| **tz_cache_metrics**           | `artefacts/metrics/tz_cache_metrics.parquet`                             | Size & hit‑rate metrics for timetable cache                                          | Manifest semver              | run‑specific                                              |
| **override_metrics**           | `artefacts/metrics/override_metrics.parquet`                             | Hit‑rate & expiry‑coverage metrics for overrides                                     | Manifest semver              | run‑specific                                              |
| **civil_time_manifest**        | `artefacts/manifests/civil_time_manifest.json`                           | Roll‑up of tz digests + cache bytes                                                  | Manifest semver              | `civil_time_manifest_digest`                              |
| **licence_files**              | `LICENSES/`                                                              | All licences (CC BY 4.0 for tz_world, Public Domain for tzdata)                      | Manifest semver              | SHA-256 for each licence, referenced in manifest          |


**Process/Contract Enforcement (add after table):**

* **STR‑tree index, `tzid_insertion_order`, nudge artefact, and all overrides are mandatory and governed.**
* **All output catalogue files must include per-row nudge and provenance fields** as mandated in the output schema.
* **Any missing audit event, catalogue column, or artefact triggers a manifest drift and hard abort in downstream pipeline.**
* **CI validation and audit logs are tracked for every build; nightly validation must include override drift, cache‑budget and manifest checks.**
* **Every artefact listed has an explicit versioning and digesting contract.**
* **All relevant licences are tracked and must be referenced for every governed artefact.**


**Notes:**

* The `tz_world_polygons_2025a.*` pattern covers `.shp`, `.shx`, `.dbf`, `.prj` and `.cpg`; each must declare `semver` and `sha256_digest` in its sidecar or manifest entry.
* The `zoneinfo_version.yml` file holds both the tzdata version string and governs horizon defaults; its `tz_horizon_digest` covers both the tzdata version and the simulation bounds.
* Any addition, removal, or version bump of these artefacts must follow semver rules and will automatically refresh the overall manifest digest via CI.
* Pattern matching is case‑sensitive; path separators use Unix‑style forward slashes.

## 2A · Deriving the civil time zone — governing artefacts (revision)

### A) Polygon source & deterministic index

* **tz‑world shapefile components** (`.shp/.shx/.dbf/.prj/.cpg`) under `artefacts/priors/tz_world/2025a/`; provenance digests rolled up into **`tz_polygon_digest`** in `spatial_manifest.json`.
* **STR‑tree serialization** (`tz_world_strtree.pkl`) with SHA‑256 **`tz_index_digest`**; polygons inserted in **lexicographic TZID order** to fix tree shape.
* **`tzid_insertion_order`** *(manifest)* — the exact sorted TZID list used to build the tree. **\[New]** (guards collation drift).
* **`locale_policy.yaml`** — pins sort/collation (e.g., code‑point order) so “lexicographic” is identical across envs. **\[New]**

### B) Nudge tie‑break & exceptions

* **`tz_nudge.yml`** (ε = **0.0001°**) with `tz_nudge_digest`; nudge vector persisted as `nudge_lat`, `nudge_lon`.
* **Exceptions:** `TimeZoneLookupError` (zero‑hit), `DSTLookupTieError` (nudge still ambiguous).

### C) Overrides (governed)

* **`tz_overrides.yaml`** (scope, tzid, evidence\_url, expiry) + CI: **must change ≥ 1 row** or fail. 
* **`tz_overrides.schema.json`** — schema for pre‑commit validation. **\[New]**
* **`override_application.jsonl`** *(log)* — per‑row when an override fires. **\[New]**
* **`override_metrics.parquet`** — counts by (scope, tzid) backing the nightly check. **\[New]**

### D) tzdata, horizon & cache

* **`tzdata2025a.tar.gz`** plus **`zoneinfo_version.yml`**; digest pinned as `tzdata_archive_digest`.
* **`simulation_horizon.yml`** → `tz_horizon_digest`.
* **`tz_cache.pkl`** (RLE timetables) with **`tz_cache_bytes`**; CI gate **< 8 MiB**. 
* **`tz_cache_metrics.parquet`** — size & zone counts for CI trend. **\[New]**
* **`iana_links_snapshot.parquet`** — alias→canonical TZID table extracted from pinned tzdata. **\[New]**
* **`timetables/`** *(debug dump)* — optional per‑TZID timetables for investigations. **\[New]**

### E) Lookup audits & failure visibility

* **`tz_lookup_events.jsonl`** *(log)* — for each site: `(lat, lon, tzids_hit_list, nudge_vector, final_tzid, override_applied?)`. **\[New]** (lightweight replay surface).
* **`tz_lookup_failures.jsonl`** *(log)* — rows that raise `TimeZoneLookupError` (lat, lon, prior\_tag, reason). **\[New]**
* **`civil_time_manifest.json`** — **per‑run roll‑up** of `tz_polygon_digest`, `tz_index_digest`, `tz_nudge_digest`, `tzdata_archive_digest`, `tz_horizon_digest`, and `tz_cache_bytes` (single place auditors look). **\[New]** 

### F) Timestamp semantics & legality

* **`timestamp_precision_policy.yaml`** — defines `event_time_utc = floor((t_local − 60·o) × 1000)` (ms) and sub‑ms truncation. **\[New]**
* **Legality filter:** forward‑gap replacement with `dst_adjusted=True`, `gap_seconds` surfaced to the arrival engine; fall‑back fold resolved by `SHA‑256(global_seed ‖ site_id ‖ t_local) % 2`. 

### G) Reproducibility records

* **`python_lib_versions.txt`** — versions of Python/NumPy/Shapely/pyproj/zoneinfo; complements index/cache determinism. **\[New]**
* **`rng_proof.md`** — proof that fold parity uses only `(global_seed, site_id, t_local)`.

### H) CI gates (record explicitly)

* **Override freshness:** nightly reapply; **must change ≥ 1** row or block.
* **Cache budget:** `tz_cache_bytes < 8 MiB`; alert on trend growth.
* **Index determinism:** STR‑tree digest **must equal** `tz_index_digest` for the run.

### I) Output columns (reminder; schema file is source of truth)

* `event_time_utc` (int64 ms), `local_time_offset` (int16), `dst_adjusted` (bool), `fold` (int8); plus `nudge_lat`, `nudge_lon` for replay. 

### “New in this revision” — quick list to add to artefact index

`civil_time_manifest`, `tz_lookup_events`, `override_application_log`, `override_metrics`, `tz_cache_metrics`, `tzid_insertion_order`, `locale_policy`, `geometry_tolerance_policy`, `timestamp_precision_policy`, `iana_links_snapshot`, `tz_timetable_dump`, `python_lib_versions`, `tz_lookup_failures`. (All now present in 2A registry.)
