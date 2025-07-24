Below is the full expository record of every premise, data‑source dependency, numerical convention, guard‑rail and deterministic rule that governs **“Deriving the civil time zone.”** Nothing is implicit: each statement names the artefact that stores the value, the code point that consumes it, the validation that defends it, and the effect a change would cause. Every artefact mentioned is tracked in the repository with its SHA‑256 digest baked into the dataset manifest so that any alteration forces a rebuild and triggers CI scrutiny.

---

### 1 Authoritative polygon source and reproducible spatial index

The shapefile and its companion files (`tz_world_2025a.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`) reside under `artefacts/priors/tz_world/2025a/`. Each file declares metadata `semver` and `sha256_digest` under manifest keys `tz_world_shp_digest`, `tz_world_shx_digest`, etc., aggregated into `tz_polygon_digest`; Fiona must open them with CRS EPSG:4326 or the build aborts. All polygons load in lexical order by `TZID` into an STR‑tree; the index is serialized via Python 3.10’s pickle protocol 5, hashed with SHA‑256 (not MD5), and stored as `tz_index_digest`, ensuring consistent index reproduction across environments.

---

### 2 Deterministic point‑to‑zone mapping with numerically safe tie‑break

Each site coordinate is filtered through STR‑tree and then `prepared_polygon.contains`. Zero hits raise `TimeZoneLookupError` (latitude, longitude, `prior_tag`), halting the build. Two hits trigger a deterministic nudge: let \$x\$ be the coordinate and \$c\$ the centroid of the smaller polygon; \$x' = x + ε,(c-x)/|c-x|\$, where ε is read from `config/timezone/tz_nudge.yml` (fields `semver`, `sha256_digest`, `nudge_distance_degrees: 0.0001`). That file’s digest is recorded as `tz_nudge_digest` and any ε change bumps semver. The nudge vector (`nudge_lat`, `nudge_lon`) is persisted per site for forensic replay.

---

### 3 Manual override governance

The governed artefact `config/timezone/tz_overrides.yaml` (fields `semver`, `sha256_digest`, `overrides`) lists entries with `scope` (`country:CA` | `mcc:6011` | \[`merchant_id`,`site_id`]), `tzid`, `evidence_url`, and `expiry_yyyy_mm_dd`. Git pre‑commit validates URL and date formats. Nightly CI reloads the site catalogue, reapplies overrides in specificity order (site → MCC → country), and asserts at least one row would change compared to polygon‐only lookup; zero differences block the merge. Any modification updates `tz_overrides_digest`.

---

### 4 Pinning the civil‑rule timeline

The tzdata archive `artefacts/priors/tzdata/tzdata2025a.tar.gz` is declared in `zoneinfo_version.yml` (`semver`, `tzdata_version: tzdata2025a`) and its SHA‑256 is recorded as `tzdata_archive_digest`. The code loads zones via `zoneinfo.ZoneInfo`. For each `TZID` in the catalogue, the engine extracts `(transition_epoch, offset_minutes)`, truncates the arrays to the configured horizon `[sim_start, sim_end]` (values read from `config/timezone/simulation_horizon.yml`, fields `semver`, `sha256_digest`, `sim_start_iso8601`, `sim_end_iso8601`, stored as `tz_horizon_digest`), applies run‑length encoding, and stores as bytes. CI asserts that `tz_cache_bytes` (manifest field) remains < 8 MiB; any increase triggers a build failure.

---

### 5 Legality filter for local timestamps

When the LGCP sampler proposes a local epoch second \$t\_{\text{local}}\$, the engine locates the most recent transition \$t\_i\$ and offset \$o\_i\$.

* If \$t\_{\text{local}}\$ lies in the forward gap \$(t\_i, t\_i+\Delta)\$, with \$\Delta=(o\_{i+1}-o\_i)\times60\$ (seconds difference of pre/post offsets), it resets \$t\_{\text{local}}\$ to \$t\_i+\Delta\$, sets `dst_adjusted=True`, computes `gap_seconds = (t_i+\Delta) - t_{\text{local}}`, and returns `surplus_wait=gap_seconds` for the arrival engine.
* If \$t\_{\text{local}}\$ lies in the fall‑back fold, it computes \$h=\mathrm{SHA256}(\mathit{global\_seed}\parallel\mathit{site\_id}\parallel t\_{\text{local}})\$ and sets `fold = h[0]\bmod2`.

These definitions ensure pure functions of immutable inputs.

---

### 6 Computation and storage of the UTC offset

After legality adjustment, the engine records:

```
event_time_utc    = floor((t_local - o*60) * 1000)    (int64, milliseconds since epoch)  
local_time_offset = o                                (int16, minutes)  
dst_adjusted      = {0|1}                            (bool)  
fold              = {0|1} or NULL                    (int8)  
```

Sub‑millisecond fractions in `event_time_utc` are truncated to align with Parquet logical type `TIMESTAMP_MILLIS`.

---

### 7 Error‑handling contract

On validation failures—`TimeZoneLookupError`, `ZoneMismatchError`, or `TimeTableCoverageError`—the engine raises the corresponding exception, cleans up temporary files, flushes audit logs, and aborts without writing any new site rows. This atomic rollback ensures no partial or corrupted outputs persist.

---

### 8 Random‑number‑stream independence

Fold‑bit hashing reads `global_seed` but not Philox counters, preserving RNG isolation. The formal proof in `docs/rng_proof.md` (SHA‑256 in manifest as `rng_proof_digest`) documents this property and is version‑controlled.

---

### 9 Memory‑safety and timetable horizon

The engine refuses to cache transitions outside `[sim_start, sim_end]`, raising `TimeTableCoverageError` on first access beyond those bounds. This forces explicit regeneration with updated horizon or tzdata version and captures the update in the manifest.

---

### 10 Licence provenance and data privacy

All shapefiles and tzdata archives carry licences in `LICENSES/` (CC BY 4.0 for `tz_world`, public domain for IANA). No personal data is used, so GDPR/CCPA concerns are addressed; see data‑provenance appendix.
