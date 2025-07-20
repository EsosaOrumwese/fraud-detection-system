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

The land polygon is Natural Earth 1:10m v5.1.2 (`natural_earth_land_10m_v5.1.2.geojson`, full SHA‑256 in manifest, CRS EPSG:4326, no simplification or pre‑processing). A candidate coordinate is rejected if it lies outside the land polygon, or if a road prior was used and its closest point distance to the sampled road segment exceeds 50 m. Termination cap: max\_attempts\_per\_site = min(500, 10 \* expected\_success\_factor) where expected\_success\_factor is 1 / max(0.10, current\_prior\_acceptance\_lower\_bound). Exceed cap → raise exception and log `placement_failure` (reason=`acceptance_cap_exceeded`, merchant\_id, site\_id, attempts); partial outputs rolled back; no infinite loops. Acceptance monitoring: sample\_size\_per\_prior=10,000 nightly; compute point estimate p̂ and Wilson lower 95% bound L; require L ≥ 0.90; metrics logged with (prior\_id, p\_hat, L, sample\_size, failures); regression alert triggers if p̂ drops >5 percentage points week‑over‑week even if L≥0.90.

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

Capital source: `capitals_dataset_2024.parquet` (sha256 recorded) containing possible multiple roles; select the single record with `role_type='administrative'` and `primary_flag=true`; if absent, fall back to `role_type='primary'`; absence of both aborts build. Haversine distance $d_H$ computed using earth radius 6371.0088 km (WGS84) with no planar approximation. Road graph provenance: built from OSM planet extract dated `YYYY-MM-DD` (sha256 of `.pbf`), contraction‑hierarchies build commit and parameters (level count, ordering heuristic) stored; edge weight = segment length (metres, EPSG:4326 great‑circle approximated by projection to EPSG:3857); any change triggers new digest. $d_R$ definition: shortest path sum of edge lengths (metres) converted to kilometres (divide by 1000, IEEE‑754 binary64); no travel‑time or speed weighting applied; time‑based metrics will be a downstream enrichment using separate speed artefacts. Elevation intentionally excluded (no DEM artefact listed); rationale: adds storage and build latency with negligible fraud signal uplift at this layer; incorporation would mandate DEM digest inclusion and schema extension later.

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

---
Below is an **appendix (“Mathematical Summary”)** you can append *verbatim* to the end of the consolidated Assumptions 1B document. It is concise, uses consistent symbols, and mirrors the prose definitions without introducing new concepts. Where parameters are governed artefacts, I reference the file name. All random variables, transformations, and clipping rules are formalized.

---

### Appendix: Mathematical Summary

**Notation**

* Countries indexed by $c$; merchants $m$; sites $s$; Merchant Category Codes (MCC) $g$; channel $h$.
* A spatial *prior* (possibly a blend) for tuple $(g,h,c)$ is $P_{g,h,c}$.
* Raster pixels (after reprojection + alignment) indexed $i=1,\dots,n$; vector features (roads, polygons) indexed $f$; polyline segments within feature $f$ indexed $q$; polygon triangulation triangles indexed $t$.
* Raw (float) prior weights before scaling: $w_i > 0$ (raster) or $w_f > 0$ (feature). Support subset $S_{g,h,c}\subset$ national territory has positive weights; outside $S_{g,h,c}$ weight $0$.
* Blended prior coefficient vector for blend id $b$: $\alpha = (\alpha_1,\dots,\alpha_K)$ with $\sum_k \alpha_k = 1$, $\alpha_k \ge 0$ (`spatial_blend.yaml`).
* Global grid cell angular resolution $\Delta_\lambda = \Delta_\phi = 1/1200^\circ$.
* Land mask polygon $L_c$; road network graph $G_c=(V_c,E_c)$.
* AADT floor constant $\underline{A}=500$ (vehicles/day).
* Footfall coefficients per $(g,h)$: $\kappa_{g,h}, \sigma_{g,h}$ (`footfall_coefficients.yaml`).
* Fano target $F_{\text{target}}=1.80$ (calibration).
* Winsor policy: clip multiple $M=3$, minimum stratum size $N_{\min}=30$ (`winsor.yml`).
* RNG: Philox counter-based PRNG; sub‑streams keyed and derived by SHA‑256; stride(key) = lower 64 bits (little-endian) of digest.

---

#### 1. Blended Prior

For a blended prior with component rasters (already co-registered) having pixel values $r^{(k)}_i \ge 0$:

$$
w_i = \sum_{k=1}^{K} \alpha_k\, r^{(k)}_i, \quad \sum_k \alpha_k = 1.
$$

Nodata pixels are treated as 0. For a direct (non‑blend) prior, $w_i$ is the pixel (or feature) value after preprocessing.

---

#### 2. Vector Feature Weights

**Road segment $e$** with geodesic length $L_e$ (metres) and AADT reading $\text{AADT}_e$:

$$
w_e = L_e \cdot \max(\text{AADT}_e, \underline{A}).
$$

**Airport polygon feature $f$** of area $A_f$ (m²):

$$
w_f = A_f.
$$

---

#### 3. Zero‑Support Condition & Fallback

Let total weight $W_{\text{raw}} = \sum_{i} w_i$ (raster) or $\sum_f w_f$ (vector).
If $W_{\text{raw}} = 0$ ⇒ fallback prior $F_c$ (WorldPop 1 km) substituted; `fallback_reason` ∈ {missing\_prior, zero\_support, empty\_vector\_after\_filter}.

---

#### 4. Integer Scaling for Fenwick Tree

Given positive raw weights $\{w_i\}_{i=1}^n$ and $W_f = \sum_i w_i$.
Define scale factor

$$
S = \frac{2^{64}-1 - n}{W_f}.
$$

Integer weight:

$$
\tilde{w}_i =
\begin{cases}
\max\left(1,\; \lfloor S w_i \rfloor \right), & w_i > 0,\\
0, & w_i = 0.
\end{cases}
$$

Total integer weight $\tilde{W} = \sum_i \tilde{w}_i < 2^{64}$. Fenwick tree stores prefix sums of $\tilde{w}_i$.

---

#### 5. Sampling Algorithms

**Raster Pixel:**

1. Draw $U \sim \text{Uniform}[0,1)$.
2. Let $u = \lfloor U \cdot \tilde{W} \rfloor + 1$.
3. Fenwick search for smallest index $i$ with cumulative $\ge u$.
4. Pixel center coordinate:

$$
\lambda_i = \lambda_{\min} + (x_i + 0.5)\Delta_\lambda,\quad
\phi_i = \phi_{\min} + (y_i + 0.5)\Delta_\phi.
$$

**Polyline Feature:**

1. Precompute cumulative lengths $C_0=0, C_j = \sum_{q=1}^j L_q$.
2. Draw $U \sim \text{Uniform}[0,C_{Q})$; find segment $q$ with $C_{q-1} \le U < C_q$.
3. Fraction $f = (U - C_{q-1})/L_q$; linear interpolate endpoints to position.

**Polygon Feature:**

1. Triangulate polygon (holes respected) into triangles $t$ with areas $A_t$.
2. Build alias table on probabilities $p_t = A_t / \sum_t A_t$.
3. Sample triangle $t$; draw $u,v\sim \text{Uniform}[0,1)$. If $u+v>1$: set $u'=1-u, v'=1-v$; else $u'=u, v'=v$.
4. Point = $v_0 + u'(v_1 - v_0) + v'(v_2 - v_0)$ in triangle vertices.

---

#### 6. Land / Road Proximity Filters

Accept sampled point $p$ iff $p \in L_c$ (point-in-polygon true) and, when prior is road, distance(p, nearest road segment) ≤ 50 m. Otherwise resample. Hard cap defined in Section 9.

---

#### 7. Time‑Zone Consistency

Given sampled point $p$ with IANA zone $z$, allowed ISO set $C_z$. Accept if country ISO $c \in C_z$ or pair $(z,c)$ in anomaly whitelist. Otherwise resample (counts toward attempt cap).

---

#### 8. RNG Sub‑Streams

For key string $k$:

$$
\text{stride}(k) = \text{LE}_{64}\big(\text{SHA256}(k)\big),
$$

Philox counter update:

$$
\text{counter}_{\text{next}} = \text{counter}_{\text{current}} + \text{stride}(k) \pmod{2^{128}}.
$$

Distinct keys $k \in\{\texttt{site_sampling}, \texttt{polygon_interior}, \texttt{footfall_lognormal}, \texttt{fenwick_tie_break}, \texttt{tz_resample}\}$.

---

#### 9. Termination Cap

Let empirical acceptance lower bound (Wilson 95%) for current prior be $a_L$. Define

$$
\text{expected\_success\_factor} = \frac{1}{\max(0.10, a_L)}.
$$

Per‑site attempt cap:

$$
A_{\max} = \min(500,\; 10 \cdot \text{expected\_success\_factor}).
$$

Exceeding $A_{\max}$ ⇒ failure event `placement_failure`.

---

#### 10. Remoteness Metrics

Haversine distance to capital:

$$
d_H = 2R \arcsin\left(\sqrt{\sin^2\frac{\phi-\phi_c}{2} + \cos\phi \cos\phi_c \sin^2\frac{\lambda-\lambda_c}{2}}\right),
$$

with $R=6371.0088$ km.

Road distance $d_R$ = length (km) of shortest path in graph $G_c$ with edge weights = metres /1000.

---

#### 11. Footfall Generation

For site $s$ in category $(g,h)$:

$$
\text{footfall}_s = \kappa_{g,h} \cdot w^{(\text{raw})}_s \cdot \exp(\varepsilon_s), \quad \varepsilon_s \sim \mathcal{N}(0,\sigma_{g,h}^2),
$$

independent across sites on sub‑stream `footfall_lognormal`. Raw blended weight $w^{(\text{raw})}_s = w_i$ or $w_f$ at sampled location. Normalised weight:

$$
w^{(\text{norm})}_s = \frac{w^{(\text{raw})}_s}{\sum_{x \in S_{g,h,c}} w_x^{(\text{raw})}}.
$$

---

#### 12. Winsorisation (Two‑Pass)

For each stratum (country $c$, MCC $g$) with $N\ge N_{\min}$:

1. Pass 1: compute

$$
\mu = \frac{1}{N}\sum_{s} \log(\text{footfall}_s), \quad
\sigma = \sqrt{ \frac{1}{N} \sum_s (\log(\text{footfall}_s) - \mu)^2 }.
$$

2. Pass 2: clip

$$
\log(\text{footfall}_s) \leftarrow \min\left(\log(\text{footfall}_s), \mu + M\sigma\right),
$$

store original as `log_footfall_preclip`, set flag `footfall_clipped` if altered.

Strata with $N < N_{\min}$: no clipping.

---

#### 13. Calibration (κ, σ Estimation)

Let simulated slice $T$ of size $N_T = 10{,}000{,}000$ stratified by historic distribution (weights $p_{g,h}$). For candidate $\sigma$, simulate $\varepsilon$ and compute empirical Fano factor

$$
F(\sigma) = \frac{\mathrm{Var}_T(\text{footfall})}{\mathbb{E}_T(\text{footfall})}.
$$

Root finding (Brent) over $\sigma \in [0.05,2.0]$ solves

$$
F(\sigma) - F_{\text{target}} = 0 \quad \text{within tolerance } 10^{-4}.
$$

Resulting $\sigma_{g,h}$ stored; κ values determined (or adjusted) so aggregate scaling matches business volume calibration (details inherited from upstream layer if defined; otherwise κ provided exogenously in same YAML and considered fixed during σ search).

---

#### 14. RNG Sample Index Mapping

Let merchants ordered by ascending merchant\_id. Let $M(m)$ be site count for merchant $m$; prefix

$$
\text{base\_offset}(m) = \sum_{m' < m} M(m').
$$

Within merchant $m$, site ordinal $s$ (0‑based). For j‑th random draw (spatial / footfall) associated with site:

$$
k = \text{base\_offset}(m) + s + j.
$$

Logged as `site_rng_index`.

---

### Notes & Domain Constraints

* **Geospatial Grid:** Global raster grid resolution fixed at 1/1200° (\~300 m at equator); indices must not assume constant metre size across latitude—only angular spacing is invariant.
* **Coordinate CRS:** All stored lat/lon coordinates are in EPSG:4326 (WGS84). No intermediate projected coordinates are persisted.
* **Weight Non‑Negativity:** All prior weights (raw raster values, blended weights, vector weights) must be ≥ 0. Any negative encountered is a data error → build abort.
* **Support Subset:** Absence (nodata or filtered feature) is represented by zero weight, never by omission of index order. Pixel / feature ordering is canonical: rasters row‑major (north→south, west→east); vectors stable file order.
* **Integer Scaling Stability:** Scale factor S recomputed per (country, prior) and must satisfy Σ integer weights < 2^64; overflow check is mandatory.
* **Fallback Trigger Equivalence:** Missing prior path, zero total weight, or empty vector after filtering are *functionally equivalent* and must produce `prior_tag='FALLBACK_POP'` plus a distinct `fallback_reason`.
* **Attempt Caps:** Per‑site resample attempts must never exceed A\_max (min(500, 10×expected\_success\_factor)); reaching cap aborts entire build (no partial continuation).
* **RNG Isolation:** Keys for Philox sub‑streams are immutable literals; adding a new key requires documentation + stride uniqueness CI test.
* **Semver Governance:** Any modification to governed YAMLs (`spatial_blend.yaml`, `footfall_coefficients.yaml`, `winsor.yml`, `fallback_policy.yml`, `calibration_slice_config.yml`, `tz_world_metadata.json`) must bump semver and rerun CI to regenerate `spatial_manifest_digest`.
* **Audit Event Completeness:** For each accepted site exactly one of (`pixel_draw`, `feature_draw`, `triangle_draw`, `polyline_offset`) must exist preceding tagging; absence or multiplicity invalidates the build.
* **Clipping Idempotence:** Winsorisation applied at most once; reprocessing (e.g. pipeline re-run) must detect prior clipping (via `footfall_clipped`) and skip.
* **Calibration Slice Integrity:** Calibration slice seed and distribution digest must match those recorded in `footfall_coefficients.yaml`; mismatch requires recalibration (σ invalid).
* **Distance Metrics Scope:** $d_H$ and $d_R$ are *proxy* metrics only; no travel time, elevation, or congestion adjustments are permissible in 1B.
* **Anomaly Whitelist Bound:** Only (zone, ISO2) pairs present in `tz_world_metadata.json` may bypass tz mismatch resampling; runtime additions are prohibited.
* **Data Type Precision:** All persisted floating values are IEEE‑754 binary64 (double). No down‑casting to float32 is allowed in persisted Parquet.
* **Reconstruction Sufficiency:** (`prior_weight_raw`, `scale_factor` from `fenwick_build`, indices, `cdf_threshold_u`, RNG event counters) must be sufficient to replay any sampling decision—no hidden state permitted.

---

### Quick Reference Summary (Variables & Domains)

| Symbol / Field                            | Meaning                                           | Domain / Type                                                      | Source / Artefact            |
|-------------------------------------------|---------------------------------------------------|--------------------------------------------------------------------|------------------------------|
| $g$                                       | MCC code                                          | Categorical string                                                 | Upstream (1A)                |
| $h$                                       | Channel                                           | Categorical string                                                 | Upstream (1A)                |
| $c$                                       | Country (ISO2)                                    | 2-letter code                                                      | Upstream (1A)                |
| `prior_tag`                               | Identifier of prior used                          | String (enum incl. `FALLBACK_POP`)                                 | Derived                      |
| `hrsl_pop_100m`                           | HRSL prior id                                     | String                                                             | `spatial_manifest.json`      |
| `worldpop_1km`                            | Fallback prior family                             | String                                                             | Manifest                     |
| `spatial_manifest_digest`                 | Composite spatial digest                          | Hex (64 chars)                                                     | Manifest build               |
| `artefact_digest`                         | Digest of concrete prior artefact used for a site | Hex (64)                                                           | Manifest lookup              |
| `prior_weight_raw` ($w^{(\text{raw})}$)   | Raw float weight at sampled location              | $[0,\infty)$ double                                                | Blended / feature weight     |
| `prior_weight_norm` ($w^{(\text{norm})}$) | Normalized weight                                 | $[0,1]$ double                                                     | Computed                     |
| $S$                                       | Integer scaling factor                            | $>0$ double                                                        | Fenwick build                |
| $\tilde{w}_i$                             | Scaled integer weight                             | $\mathbb{N}_0 \le 2^{64}-1$                                        | Fenwick tree                 |
| `pixel_index`                             | Raster index (row-major)                          | Int32 (≥0)                                                         | Sampling                     |
| `feature_index`                           | Vector feature ordinal                            | Int32 (≥0)                                                         | Sampling                     |
| `segment_index`                           | Polyline segment ordinal                          | Int32 (≥0)                                                         | Polyline sampling            |
| `segment_frac`                            | Position along segment                            | \[0,1) double                                                      | Polyline sampling            |
| `triangle_id`                             | Triangle ordinal in triangulation                 | Int32 (≥0)                                                         | Polygon sampling             |
| `u`, `v`                                  | Barycentric aux coords                            | \[0,1) double                                                      | Polygon sampling             |
| `cdf_threshold_u`                         | Uniform used to pick index                        | \[0,1) double (scaled)                                             | RNG event                    |
| `site_rng_index` (k)                      | Global draw position for site                     | Int64 (≥0)                                                         | RNG event                    |
| $\underline{A}$                           | AADT floor                                        | 500 vehicles/day                                                   | `footfall_coefficients.yaml` |
| $L_e$                                     | Road segment length                               | (0,∞) metres                                                       | Derived                      |
| $\text{AADT}_e$                           | AADT count                                        | $[0,\infty)$                                                       | Source attribute             |
| $A_f$                                     | Polygon area                                      | (0,∞) m²                                                           | Derived                      |
| κ\_{g,h}                                  | Load factor                                       | (0,∞) double                                                       | `footfall_coefficients.yaml` |
| σ\_{g,h}                                  | Log-normal std dev                                | (0,∞) double                                                       | `footfall_coefficients.yaml` |
| ε                                         | Log-normal residual                               | $\mathcal{N}(0,σ^2)$                                               | RNG sub-stream               |
| `footfall_preclip`                        | Footfall before winsor                            | (0,∞) double                                                       | Computed                     |
| `log_footfall_preclip`                    | Log footfall pre-clip                             | $\mathbb{R}$                                                       | Computed                     |
| `footfall_clipped`                        | Clipping indicator                                | Boolean                                                            | Winsor pass                  |
| M                                         | Clip multiple                                     | 3 (≥1)                                                             | `winsor.yml`                 |
| N\_{\min}                                 | Min stratum size                                  | 30                                                                 | `winsor.yml`                 |
| $d_H$                                     | Haversine distance to capital                     | (0,∞) km                                                           | Computed                     |
| $d_R$                                     | Road network distance                             | (0,∞) km                                                           | Graph shortest path          |
| `fallback_reason`                         | Fallback cause                                    | Enum {missing\_prior, zero\_support, empty\_vector\_after\_filter} | Fallback logic               |
| `fallback_policy.yml`                     | Fallback thresholds                               | YAML (semver)                                                      | Governed                     |
| `fenwick_build` event fields              | n, total\_weight, scale\_factor                   | Logged types                                                       | Build                        |
| `footfall_draw` event fields              | kappa, sigma, epsilon                             | Logged                                                             | RNG                          |
| `tz_mismatch` events                      | mismatch metadata                                 | Logged                                                             | TZ check                     |
| A\_{\max}                                 | Attempt cap per site                              | ≤500 int                                                           | Termination calc             |
| `tz_world_metadata.json`                  | Zone→ISO map                                      | JSON                                                               | Governed                     |
| `calibration_slice_config.yml`            | Calibration slice spec                            | YAML                                                               | Governed                     |
| F\_{target}                               | Fano target                                       | 1.80                                                               | Calibration                  |
| σ bracket                                 | Search interval                                   | \[0.05, 2.0]                                                       | Calibration                  |
| Tolerance                                 | Fano absolute tolerance                           | 1e-4                                                               | Calibration                  |
| Δ                                         | Grid angular step                                 | 1/1200°                                                            | Grid spec                    |
| R                                         | Earth radius                                      | 6371.0088 km                                                       | Distance calc                |

---

This mathematical appendix is intentionally concise; every symbol aligns with a governed artefact or algorithmic step defined earlier. No new assumptions are introduced.