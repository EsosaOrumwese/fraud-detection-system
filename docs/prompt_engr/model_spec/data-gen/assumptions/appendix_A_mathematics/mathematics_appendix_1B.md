## Subsegment 1B: Placing outlets on the planet
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

#### 15 .Manifest Digest Construction and Whitelist Enforcement

**Manifest Digest Construction**
Let $F = {f_1, ..., f_n}$ be the lexicographically ordered list of all spatial prior artefact files and governed YAMLs referenced for a given build (including every `.tif`, `.shp`, `.gpkg`, `.yaml`, `.json`, etc.), as enumerated in `spatial_manifest.json`.

* For each $f_i$, compute its SHA-256 digest $d_i$.
* Exclude the wall-clock build timestamp field from all hash inputs.
* Concatenate all $d_i$ in lexicographic path order to form $C = d_1 | d_2 | ... | d_n$.
* The **spatial manifest digest** is:

  $$
  \text{spatial_manifest_digest} = \text{SHA256}(C)
  $$
* This digest is written in every output row and output log, and is checked by downstream modules for lineage matching.
* Any modification, removal, or addition of a file to $F$ mandates a manifest semver bump and yields a new digest.

**Whitelist Enforcement:**

* Only artefacts and patterns explicitly enumerated in `spatial_manifest.json` (or `allow_patterns`) may exist in the prior library directory at build time.
* Presence of any stray file aborts the build; removal of any artefact mandates semver increment.
* The manifest filename must be exactly `spatial_manifest.json`; any deviation aborts the build.

---

#### 16. Fenwick Tree Concurrency and Logging

**Fenwick Tree Construction (Determinism & Concurrency)**

* For every (country, prior_id) pair, the Fenwick tree is built once per build under a double-checked locking protocol:

  1. If tree exists: skip.
  2. Else: acquire lock, build from canonical weight vector, record event `fenwick_build` with fields (country, prior_id, n, total_weight, build_ms, scale_factor).
  3. After release, blocked threads reuse completed tree.
* Build is crash-tolerant and idempotent: mismatch in (n, total_weight) aborts with error.

---

#### 17. Crash-Tolerant Write Protocol

**Crash-Tolerant Idempotent Writes**

* For each site:

  1. Write row to temp file: `sites/partition_date=YYYYMMDD/merchant_id={id}/site_id={site_id}.parquet.tmp`.
  2. Fsync, then atomically rename to `.parquet`.
  3. If final file exists (from prior crash/rerun), skip rewrite.
  4. Schema validation occurs before rename; only fully valid and written files are exposed as final output.

* Any error or hard cap (max attempts, placement failure, etc.) aborts the build; only fully completed site rows are retained.

---

#### 18. Audit Event Schema and Placement Failure Events

**Audit Event Schema**
Each stochastic or structural operation (sampling, Fenwick build, placement, footfall draw, tz mismatch, fallback, placement failure) is logged as a structured event with the following general fields (all events):

| Field                   | Type     | Description                     |
|-------------------------|----------|---------------------------------|
| timestamp_utc           | datetime | ISO-8601 UTC wall clock         |
| event_type              | string   | Event code (see below)          |
| merchant_id             | int64    | Merchant identifier             |
| site_id                 | int64    | Site identifier                 |
| pre_counter             | uint128  | Philox counter before operation |
| post_counter            | uint128  | Philox counter after operation  |
| stride_key              | string   | Key for substream               |
| site_rng_index          | int64    | Global RNG draw index           |
| [event-specific fields] | varies   | See below                       |

**Placement Failure Event Schema:**

* Event: `placement_failure`
* Additional fields:
  * `reason` (enum: `acceptance_cap_exceeded`, `tz_mismatch_exhausted`)
  * `attempt_count` (int)
  * `prior_tag` (string)

---

#### 19. Capital Row Selection Logic (Remoteness Metrics)

**Capital Selection**

* Load `capitals_dataset_2024.parquet`; select the row with `role_type='administrative'` and `primary_flag=true` for each country.
* If absent, fallback to `role_type='primary'`.
* If neither present, abort build.
* Haversine and road distances are computed from these coordinates for all remoteness metrics.

---

#### 20. Immutability Contract for Outputs

**Immutability Postcondition**

* Every output row contains the `spatial_manifest_digest` field.
* Downstream modules must verify that all rows have the same digest and that it matches the value in the root-level manifest; otherwise, output is treated as non-compliant and downstream simulation aborts.
* Any modification to the spatial columns or governed parameters triggers a new build, a manifest semver bump, and a new digest.

---

#### 21. Manifest Reproducibility and Lineage Propagation

* The overall build fingerprint for 1B is computed as

  $$
  \text{SHA256}(\text{manifest_fingerprint}_{\text{upstream}} \| \text{spatial_manifest_digest} \| \text{footfall_coefficients_digest} \| \text{winsor_policy_digest} \| \text{fallback_policy_digest})
  $$
* Any change to any included artefact, policy, or prior propagates a new output lineage; all downstream steps must verify lineage compatibility before proceeding.


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
