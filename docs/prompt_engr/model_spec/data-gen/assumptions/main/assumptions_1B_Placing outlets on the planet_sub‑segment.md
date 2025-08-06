The purpose of this companion text is to surface—line by line—the premises, data sources, numeric linkages and operational guard‑rails that uphold the **“Placing outlets on the planet”** engine. Everything stated here is enforceable by configuration or by deterministic code; nothing is allowed to hide in implicit defaults. If a future implementer alters any assumption, the catalogue’s manifest hash will change and the continuous‑integration gate will block downstream use until reviewers accept the modification.

---

### 1 Spatial artefacts are sovereign and version‑locked

Every geographic prior resides in a file held under git LFS. Rasters are GeoTIFFs; vectors are ESRI shapefiles or GeoPackages. Each file is accompanied by a sibling text file containing its SHA‑256 digest. The catalogue build opens a manifest called **`spatial_manifest.json`**, concatenates every digest in lexical path order, hashes that concatenation, and embeds the result into every row it writes as the column **`spatial_manifest_digest`**. The manifest filename is fixed (must be exactly `spatial_manifest.json`); alternate names or multiple manifests abort the build. The manifest also records wall‑clock build time (ISO‑8601 UTC) purely for audit; this timestamp is explicitly excluded from digest concatenations so that artefact‑identical reruns produce identical hashes. Intrusion policy is whitelist: only artefacts enumerated (or patterns explicitly listed under `allow_patterns`) may exist; removal of a previously listed artefact mandates manifest semver increment; presence of any other file aborts start‑up. The overall build fingerprint = SHA‑256( upstream `manifest_fingerprint` || `spatial_manifest_digest` || digests of `footfall_coefficients.yaml`, `winsor.yml`, and `fallback_policy.yml` ); CI recomputes `spatial_manifest_digest` after zeroing the timestamp to assert exclusion of wall‑clock time.

---

### 2 Mapping MCC×channel to a single spatial prior or blend

The governed YAML table **`spatial_blend.yaml`** (fields: `semver`, `sha256_digest`, `updated`, `entries[]`) maps each `(mcc_code, channel)` to either a direct artefact id or a blend of artefacts expressed as a convex weight vector. Blend member lists are stored in lexicographic order of `prior_id`; weights must sum to 1 within 1e‑9 or CI fails. Any change to a blend coefficient mandates a semver increment; CI compares prior and current digests and fails the build if weights changed without a semver bump or if post‑change weights fall outside the tolerance. Resampling for blending is standardised: all source rasters reprojected to EPSG:4326 and resampled onto a fixed 1/1200° grid (≈300 m at equator, origin −180°, −90°) using bilinear interpolation for continuous layers (nearest for any categorical layers if introduced later); nodata cells become weight zero. The blended raster is written once to a deterministic content‑addressed path `cache/blends/{sha256(component_digests+weights)}.tif` via atomic temp‑rename and, if already present, reused read‑only.

---

### 3 Deterministic importance‑sampling with Fenwick trees

A single Fenwick tree is built *eagerly* for every (country, prior\_id) pair on first reference with double‑checked locking: if tree exists skip; else acquire lock, materialise from canonical ordered weight vector, release; log `fenwick_build` (country, prior\_id, n, total\_weight, build\_ms, scale\_factor). Weights scaling: compute W\_f = Σ w\_i (float64); S = (2^64−1 − n)/W\_f; integer weight\_i = max(1, floor(w\_i \* S)) for w\_i>0 else 0; ensures Σ integer weights < 2^64; cumulative array stored little‑endian; log W\_f, S, Σ integer weights. Random sampling draws a 64‑bit uniform `u`, multiplies by the total integer weight `W`, and performs a Fenwick (binary indexed) search to find the least index with cumulative ≥ `u_scaled`. Pixel→coordinate mapping: row‑major index → (row, col); latitude = lat\_origin + (row+0.5)\*Δ; longitude = lon\_origin + (col+0.5)\*Δ; no jitter applied in governed build; optional jitter flag (off by default) would add uniform offsets in (−0.5Δ, 0.5Δ). Concurrency: construction guarded by a lock keyed `(country, prior_id)`; blocked threads reuse completed tree; duplicate build attempts detect mismatch in (n, total\_weight) and abort (should not occur).

---

### 4 Numerical definition of feature weights

Population raster pixel weight = raw population value (float). HRSL prior id: `hrsl_pop_100m` (provider Meta/HRSL, vintage `2020_v1.2`, path pattern `artefacts/priors/hrsl/2020_v1.2/{ISO2}.tif`, nodata→0, sha256 digest listed). WorldPop fallback population raster: 1 km v2023Q4 (path pattern `artefacts/priors/worldpop/2023Q4/{ISO2}.tif`, nodata=0, digest included). For OSM road vectors the weight of a line segment is

$$
w_{\text{road}} = L \times \max(\text{AADT}, \underline{A})
$$

where $L$ is geodesic length in metres (approximated via EPSG:3857 projection) and $\underline{A}=500$ vehicles/day prevents zero‑weight segments; AADT unit = vehicles/day. Floor parameter $\underline{A}$ is governed (appears in `footfall_coefficients.yaml` metadata) and any change requires semver bump. For airport polygons, weight equals polygon area in square metres.

---

### 5 Land–water filter and termination guarantee

The land polygon is Natural Earth 1:10 m v5.1.2 (`natural_earth_land_10m_v5.1.2.geojson`, full SHA-256 in the manifest, CRS EPSG:4326, no simplification or pre-processing). A candidate coordinate is rejected if it lies outside the land polygon or, when a road prior is used, if its closest-point distance to the sampled road segment exceeds 50 m. **Termination cap:** first compute the Wilson 95 % lower-confidence bound of the empirical acceptance rate for the current prior and denote it $a_L$. Define

$$
\text{expected_success_factor}=\frac{1}{\max(0.10, a_L)}.
$$

Then set

$$
\text{max_attempts_per_site}=\min\!\bigl(500,\;10\times\text{expected_success_factor}\bigr).
$$

Exceeding the cap raises an exception and logs `placement_failure` (`reason=acceptance_cap_exceeded`, `merchant_id`, `site_id`, `attempts`); partial outputs are rolled back; no infinite loops are possible. Acceptance monitoring: `sample_size_per_prior=10 000` nightly; we compute point estimate \$p̂\$ and Wilson lower 95 % bound \$L\$; we require \$L≥0.90\$; metrics are logged (prior id, \$p̂\$, \$L\$, sample size, failures); a regression alert fires if \$p̂\$ drops more than 5 percentage points week-over-week even with \$L≥0.90\$.


---

### 6 Tagging for full traceability

Extended site catalogue columns (additions to upstream 1A schema): `lat` (float64), `lon` (float64), `prior_tag` (string), `prior_weight_raw` (float64), `prior_weight_norm` (float64), `artefact_digest` (hex64), `spatial_manifest_digest` (hex64), `log_footfall_preclip` (float64), `footfall_clipped` (bool). Additionally per accepted point either (a) raster: `pixel_index` (int32) or (b) vector polyline: `feature_index` (int32), `segment_index` (int32), `segment_frac` (float64) or (c) vector polygon: `feature_index`, `triangle_id` (int32), barycentric `u`, `v` (float64 each). Global field `cdf_threshold_u` (float64) stores the exact scaled uniform used in Fenwick / alias search. `prior_weight_raw` = blended float value; `prior_weight_norm` = `prior_weight_raw / Σ(domain raw weights)`; scaled integer weights only exist inside Fenwick; reconstruction uses logged `scale_factor` plus `prior_weight_raw`.

---

### 7 Fallback mechanics and policy

Missing or unusable prior cases trigger governed fallback to the WorldPop raster: triggers include (a) missing artefact mapping, (b) zero‑support (Σ positive weights = 0 after construction), (c) empty vector after filtering. Fallback inserts `prior_tag="FALLBACK_POP"` and sets `fallback_reason` in {`missing_prior`,`zero_support`,`empty_vector_after_filter`}. `fallback_policy.yml` (semver, sha256) specifies `global_threshold` and optional `per_mcc_overrides`; CI validates (a) thresholds non‑decreasing vs previous, (b) any raise includes justification text, (c) all fallback events enumerate `fallback_reason` so rate reports can disaggregate causes.

---

### 8 Time‑zone country‑consistency check

Engine loads `tz_world_metadata.json` (semver, sha256) mapping each IANA zone to the (possibly multi‑valued) set of legitimate ISO‑alpha‑2 codes. Success criterion: `site_country_iso ∈ zone_country_set`. Whitelist: `anomaly_whitelist` listing (zone, iso2) pairs that may legitimately mismatch geometric boundaries; these bypass resampling. Non‑whitelisted mismatches trigger resampling (counting toward the site’s resample cap) and log `tz_mismatch` with fields (merchant\_id, site\_id, lat, lon, tzid, site\_country, candidate\_country\_set, attempt\_index, prior\_tag). If cap reached a `tz_mismatch_exhausted` event logs final attempt details and the build aborts.

---

### 9 Foot‑traffic scalar and calibration

Footfall formula:

```
footfall = κ_(mcc,channel) × prior_weight_raw × exp(ε),  ε ~ N(0, σ_(mcc,channel)^2)
```

Both κ and σ stored in `footfall_coefficients.yaml` (semver, sha256) with calibration metadata (Fano target, achieved Fano, iterations, final diff, seed). RNG: ε is drawn once per site from a Philox sub‑stream stride derived via SHA‑256("footfall\_lognormal"); event `footfall_draw` logs (merchant\_id, site\_id, kappa, sigma, epsilon, footfall\_preclip). Calibration specification: synthetic slice size = 10,000,000; seed `CALIB_SEED`; stratification weights proportional to historic 2024Q4 merchant distribution (digest `historic_dist_2024Q4.sha256`); row allocation by floor then largest fractional remainders; Brent bracket \[0.05, 2.0]; tolerance 1e−4 on Fano target 1.80; max iterations 200; convergence stats embedded. Slice construction: for each (mcc, channel) with historic share s, allocate ⌊s \* 10,000,000⌋ rows, distribute remainder by largest fractional part; merchant exemplars sampled deterministically with secondary hash ordering.

---

### 10 Winsorisation / outlier control policy

Two‑pass clipping: pass 1 accumulates sum and sum of squares of log footfall per (country, MCC) in deterministic ascending merchant\_id order; compute μ, σ; pass 2 applies clip at μ + `clip_multiple` × σ only if stratum count ≥ `min_sites_for_clip`; record `log_footfall_preclip` and boolean `footfall_clipped`. `winsor.yml` contains (`clip_multiple=3`, `min_sites_for_clip=30`, `semver`, `sha256_digest`); digest included in manifest; CI ensures any policy change bumps semver and that `clip_multiple` ≥ prior version.

---

### 11 Remoteness proxies (distance metrics)

Capital source: governed Parquet `capital_points_{vintage}.parquet` (digest recorded in the registry). Selection: choose the single record with `role_type='administrative' AND primary_flag=true`; if absent, fall back to `role_type='primary'`. Absence of both aborts the build. Haversine distance $d_H$ computed using earth radius 6371.0088 km (WGS84) with no planar approximation. Road graph provenance: built from OSM planet extract dated `YYYY-MM-DD` (sha256 of `.pbf`), contraction‑hierarchies build commit and parameters (level count, ordering heuristic) stored; edge weight = segment length (metres, EPSG:4326 great‑circle approximated by projection to EPSG:3857); any change triggers new digest. $d_R$ definition: shortest path sum of edge lengths (metres) converted to kilometres (divide by 1000, IEEE‑754 binary64); no travel‑time or speed weighting applied; time‑based metrics will be a downstream enrichment using separate speed artefacts. Elevation intentionally excluded (no DEM artefact listed); rationale: adds storage and build latency with negligible fraud signal uplift at this layer; incorporation would mandate DEM digest inclusion and schema extension later.

---

### 12 Philox RNG partitioning and audit

Global seed: 128‑bit hex in manifest. Sub‑stream stride derivation: stride(key) = lower\_64\_bits\_little\_endian(SHA‑256(key)); keys enumerated: `site_sampling`, `polygon_interior`, `footfall_lognormal`, `fenwick_tie_break`, `tz_resample`; CI asserts distinctness; SHA‑1 prohibited. Philox counter update: counter\_next = counter\_current + stride(key) (128‑bit modular addition); no leapfrog partitioning; expected maximum draws per sub‑stream ≪ 2^64 ensuring negligible wrap probability; any overflow wraps modulo 2^128 (documented). RNG audit events (all mandatory when operation occurs): `fenwick_build`, `pixel_draw`, `feature_draw`, `triangle_draw`, `polyline_offset`, `tz_mismatch`, `tz_mismatch_exhausted`, `footfall_draw`, `placement_failure`; each records (pre\_counter, post\_counter, stride\_key, merchant\_id, site\_id, site\_rng\_index) plus event‑specific payload enabling full replay; missing event triggers validation abort. `(merchant_id, site_id)` to k mapping: let M(m)=# sites for merchant m; base\_offset(m)=Σ\_{m'\<m} M(m'); site ordinal s (0‑based); j-th spatial draw index j starting at 0; k = base\_offset(m) + s + j; logged as `site_rng_index`.

---

### 13 Crash‑tolerance and idempotent writes

Write protocol: construct temp file `sites/partition_date=YYYYMMDD/merchant_id={id}/site_id={site_id}.parquet.tmp`, fsync, then atomic rename to final `.parquet`; if final exists (from prior crash rerun) skip rewrite; schema validation occurs before rename; ensures idempotency and prevents partial parquet exposure. Exceeding resample or tz mismatch cap raises a controlled exception; orchestrator aborts the build after flushing logs; no site rows beyond that merchant/site are committed; `placement_failure` event schema: (merchant\_id, site\_id, reason, attempt\_count, prior\_tag).

---

### 14 Catalogue immutability contract

The Parquet schema includes a `spatial_manifest_digest` column whose value must be identical across all rows. Downstream modules read that digest and refuse to proceed if it does not match the digest in the JSON manifest at the catalogue root. Once this sub‑segment finishes, any change to spatial columns or governed parameters mandates a new catalogue build (new manifest semver and digest). Unspecified behaviour is deemed non‑compliant rather than implicitly permitted.

---

By enumerating each numerical constant’s storage location, each calibrated coefficient’s provenance, every geometric filter, every random‑stream safeguard, and every CI test that monitors divergence, this document removes tacit knowledge from the spatial placement engine. An implementation team can follow it verbatim, and an auditor can challenge any governed assumption by editing the corresponding YAML or artefact file (forcing a digest change) and reproducing the build under a new manifest hash; unspecified behaviour is treated as a defect.
