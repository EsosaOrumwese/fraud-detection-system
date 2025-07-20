The purpose of this companion text is to surface—line by line—the premises, data sources, numeric linkages and operational guard‑rails that uphold the **“Placing outlets on the planet”** engine. Everything stated here is enforceable by configuration or by deterministic code; nothing is allowed to hide in implicit defaults. If a future implementer alters any assumption, the catalogue’s manifest hash will change and the continuous‑integration gate will block downstream use until reviewers accept the modification.

---

#### 1 Spatial artefacts are sovereign and version‑locked

Every geographic prior resides in a file held under git LFS. Rasters are GeoTIFFs; vectors are ESRI shapefiles or GeoPackages. Each file is accompanied by a sibling text file containing its SHA‑256 digest. The catalogue build opens a manifest called `spatial_manifest.json`, concatenates every digest in lexical path order, hashes that concatenation, and embeds the result into every row it writes. The engine refuses to start if any listed artefact is missing or if any un‑listed file intrudes into the directory; this guarantees a one‑to‑one mapping between manifest and build output.

---

#### 2 Mapping MCC×channel to a single spatial prior

The YAML table `spatial_blend.yaml` maps each `(mcc_code, channel)` to either

* a direct artefact path, or
* a blend of artefacts expressed as a convex weight vector that sums exactly to one.

Blending is performed by loading each raster at native resolution, resampling on the fly to match the highest‑resolution member, scaling each pixel’s value by its weight, summing, and writing the blend to `/tmp/blended_Δ.tif`. The temporary file’s digest is included in the manifest; a later audit can reproduce it by repeating the blend under the same seed. Blended priors are read‑only: if an implementer wants a different linear combination they must edit `spatial_blend.yaml`.

---

#### 3 Deterministic importance‑sampling with Fenwick trees

A single Fenwick tree is built for every country–artefact pair the first time it is requested. The tree stores uint64 prefix sums of pixel or feature weights. Random sampling draws a 64‑bit uniform `u`, multiplies by the total weight `W`, and performs a Fenwick search in O(log n) steps to locate the index whose cumulative weight exceeds `uW`. Because the Fenwick construction iterates over artefact indices in geographic sort order, two developers on two machines will build identical trees even if the underlying spatial library enumerates features nondeterministically.

---

#### 4 Numerical definition of feature weights

For population rasters the pixel weight is simply the population value. For OSM road vectors the weight of a line segment is

$$
w_{\text{road}} = L \times \max\bigl(\text{AADT},\,\underline{A}\bigr)
$$

where $L$ is segment length in metres and $\underline{A}=500$ vehicles/day prevents zero‑weight segments. For airport polygons, weight equals polygon area in square metres. The 500‑vehicle floor lives in `road_weight.yml`, so that a reviewer can raise or lower it without touching Python.

---

#### 5 Land–water filter and termination guarantee

The land polygon is Natural‑Earth 1:10 m, commit hash `c2d9…`. A candidate coordinate is rejected if `shapely.point.within(land_poly)` is false, or if a road prior was used and `distance(point, segment) > 50 m`. The loop is theoretically unbounded, but an empirical acceptance probability above 0.95 has been measured on 2023‑Q4 WorldPop rasters. If acceptance falls below 0.9 for any prior during the nightly smoke test, CI fails and flags the offending artefact.

---

#### 6 Tagging for traceability

Every accepted point receives

```
prior_tag        = artefact_basename | "blend("+id1+","+id2+…+")"
prior_weight     = numeric weight that won the CDF draw
artefact_digest  = SHA-256 of the artefact (or of the blended temp file)
```

Because the digest is stored, anyone can confirm that a pixel debugged later in GIS truly came from the artefact the tag claims.

---

#### 7 Fallback mechanics for unsupported MCC–country pairs

If no artefact path exists for a requested (MCC, channel, country) tuple, the engine falls back to the 1 km WorldPop raster for that country. The fallback inserts `prior_tag="FALLBACK_POP"`. CI computes the fallback rate each night; if the global proportion exceeds 1 %, the build fails until a maintainer supplies a proper prior or explicitly raises the threshold in `fallback_policy.yml`.

---

#### 8 Time‑zone country‑consistency check

After coordinate acceptance the engine calls

```python
tzid = tz_world.lookup(lat, lon)
```

and derives the two‑letter ISO code from `tzid.split('/')[-1]` via a static table. If that code disagrees with the site’s `country_iso`, resampling occurs. A maximum of 50 resamples is permitted; exceeding that threshold triggers an exception with a pointer to the failing prior.

---

#### 9 Formula for foot‑traffic scalar

```
footfall = κ_(mcc,channel)  × prior_weight × exp(ε),  ε~N(0, σ_(mcc,channel)^2)
```

Both κ and σ come from `footfall_coefficients.yaml`. They are calibrated by running the LGCP arrival engine on a ten‑million‑row synthetic slice and solving

$$
\text{Fano}_\text{target} - \text{Fano}_\text{sim}(κ,σ)=0
$$

via Brent’s method. The calibration notebook is checked into `notebooks/calibrate_footfall.ipynb` and its output YAML is committed in the same PR as the catalogue manifest.

---

#### 10 Outlier control policy

After sampling `footfall`, if

$$
\log\text{footfall} > \mu + 3σ
$$

where μ and σ are the mean and standard deviation of `log footfall` within the merchant’s country × MCC stratum, the value is clipped to the threshold (`winsorisation`). The 3‑sigma constant and the stratum definition live in `winsor.yml`.

---

#### 11 Remoteness proxies for later travel‑speed features

Haversine distance $d_H$ to the country’s capital is computed analytically. If the artefact is a road vector, the graph distance $d_R$ from site to capital is found by scanning a contraction‑hierarchies graph pre‑built from the same OSM snapshot used for priors. The graph’s build commit hash is included in the manifest so that a future developer cannot accidentally recompute on fresher OSM data without detection.

---

#### 12 Philox stream partitioning guarantee

The global seed is a 128‑bit hex string in `manifest.json`. The site‑placement module obtains a stream key by SHA‑1‑hashing its fully qualified module path and jumping ahead by that integer mod 2¹²⁸. This ensures the stream cannot collide with any other sub‑segment. A validity proof is documented in `rng_proof.md`.

---

#### 13 Crash‑tolerance and idempotency

Every `(merchant_id, site_id)` combination maps deterministically to the $k$-th sample drawn on its RNG sub‑stream. If a build crashes midway, a re‑run will regenerate exactly the same coordinates for the already‑written sites and continue, because the Fenwick tree search and the rejection‑sampling loop read only from the sub‑stream.

---

#### 14 Catalogue immutability contract

The Parquet schema includes an `artefact_manifest_digest` column whose value must be identical across all rows. Downstream modules read that digest and refuse to proceed if it does not match the digest in the JSON manifest at the catalogue root. This contract enforces the rule that once “Placing outlets on the planet” finishes, no step may rewrite the spatial columns without producing a brand‑new catalogue version.

---

By enumerating each numerical constant’s storage location, each calibrated coefficient’s provenance, every geometric filter, every random‑stream safeguard, and every CI test that monitors divergence, the present document removes the last hint of tacit knowledge from the spatial‑placement engine. An implementation team can follow it verbatim, and an auditor can challenge any individual assumption simply by changing the corresponding YAML or artefact file and reproducing the build under a new manifest hash.
