# Acquisition Guide — `hrsl_raster` (HRSL population surface for 3B edge sampling)

## 0) Purpose and role in the engine

`hrsl_raster` is the **pinned population surface** used by **3B.S2** to place CDN edge nodes in realistic “where people are” locations (then jittered with Philox and checked against country polygons). It must be **non-toy** (global-ish coverage, real population texture) and **deterministic to reproduce once pinned**.

Source posture: Meta+CIESIN HRSL (public, CC-BY-4.0) hosted as Cloud-Optimized GeoTIFFs on AWS Open Data. ([Open Data Registry][1])

---

## 1) Engine requirements (MUST)

### 1.1 Identity (from 3B contracts)

* **Dataset ID:** `hrsl_raster`
* **Format:** `tif`
* **Path:** `artefacts/rasters/hrsl_100m.tif`
* **Version token:** `{vintage}`
* **Semver token:** `{semver}`
* **Schema ref:** `schemas.ingress.layer1.yaml#/population_raster` (population counts raster)

### 1.2 Raster semantics (MUST)

* Pixel values represent **estimated number of people per pixel** (population counts, not density per km²).
* CRS MUST be **WGS84 / EPSG:4326**.
* Values MUST be **non-negative**.
* NoData MUST be defined and MUST equal `0` for this sampling surface (modelling convention: "unknown/uninhabited → zero mass").
  This is not claiming upstream NoData semantics are preserved; it is a pinned engine sampling convention.

---

## 2) Recommended source (PINNED, no “random mirrors”)

### Primary source: AWS Open Data (Meta HRSL / High Resolution Population Density Maps)

* Dataset page (license + access): ([Open Data Registry][1])
* COG bucket: `s3://dataforgood-fb-data/hrsl-cogs/` (no-sign-request) ([Open Data Registry][1])
* These data are distributed as **Cloud-Optimized GeoTIFFs** and described as **1 arcsecond blocks**. ([Open Data Registry][1])

Quick sanity check (optional, deterministic):

```
aws s3 ls --no-sign-request s3://dataforgood-fb-data/hrsl-cogs/
```

You should see the `hrsl_general/` prefix.

### Access convenience: “general population” VRT mosaic

Use the upstream VRT as the stable “mosaic view”:

* `s3://dataforgood-fb-data/hrsl-cogs/hrsl_general/hrsl_general-latest.vrt` ([docs.digitalearthafrica.org][2])
* HTTP equivalent (for /vsicurl/):
  `https://dataforgood-fb-data.s3.amazonaws.com/hrsl-cogs/hrsl_general/hrsl_general-latest.vrt` ([LinkedIn][3])

This avoids having to hardcode a per-tile key list.

---

## 3) Inputs Codex MUST be given (fail-closed)

Codex MUST be provided (via intake manifest / scenario selection):

* `vintage` (string): governance label you want written into the 3B sealing inventory (e.g., `HRSL_v1.5_aws`, `HRSL_2025Q4`).
* `semver` (string): pipeline semver for *your* shaping procedure (e.g., `v1.0.0`).

If either is missing → **FAIL CLOSED**.

*(We are not inferring “latest” as a version token. The upstream VRT may be “latest”, but your engine still pins **your own** `{vintage}` for reproducibility and audit.)*

---

### 3.1 Placeholder resolution (MUST)

Replace placeholder tokens consistently:

* `{vintage}`: the governance label pinned in intake (e.g., `HRSL_2025Q4`).
* `{semver}`: your shaping pipeline semver (e.g., `1.0.0`).
* `<tmp>`: a local temp directory used during acquisition (not part of any sealed output paths).

## 4) Acquisition + shaping procedure (Codex implements; this doc specifies)

### 4.1 Fetch the upstream VRT (MUST)

Download bytes of the VRT:

* From S3 (preferred, no-sign-request):
  `aws s3 cp --no-sign-request s3://dataforgood-fb-data/hrsl-cogs/hrsl_general/hrsl_general-latest.vrt <tmp>/hrsl_general.vrt` ([Open Data Registry][1])
* Or HTTP:
  `curl -L -o <tmp>/hrsl_general.vrt https://dataforgood-fb-data.s3.amazonaws.com/hrsl-cogs/hrsl_general/hrsl_general-latest.vrt` ([LinkedIn][3])

Important:

* The VRT references tiles **relative to the `hrsl_general/` prefix** (e.g., `v1.5/...tif`). Ensure the downstream reader resolves those relative paths against `https://dataforgood-fb-data.s3.amazonaws.com/hrsl-cogs/hrsl_general/` or rewrite the VRT paths to absolute `/vsicurl/` URLs before warping.

Compute and record:

* `vrt_sha256`
* `vrt_bytes`

If download fails / non-200 / HTML error → **FAIL CLOSED**.

### 4.2 Materialise a 100m-class raster (MUST)

Because HRSL is 1 arcsecond (~30m) ([Open Data Registry][1]), define the 100m-class target grid as **3 arcseconds**:

* `tr_deg = 3 / 3600 = 0.0008333333333333334`

**Target resolution MUST be exactly `0.0008333333333333334` degrees** for both x and y.

#### 4.2.1 Resampling law (MUST; count-preserving)

We want population **counts** per output pixel.

Let the input be 1-arcsecond counts. To aggregate to 3-arcseconds:

* Use an **average resample** to 3 arcseconds, then multiply by **9** (3×3) to approximate an exact block-sum on aligned grids.

This is deterministic and avoids relying on whether a given GDAL build supports `-r sum`.

Concrete implementation pattern (one valid approach):

1. `hrsl_3as_avg.tif` = warp VRT → EPSG:4326 @ 3 arcseconds using resample=average
2. `hrsl_3as_sum.tif` = `hrsl_3as_avg.tif * 9`, preserving NoData

Notes:

* Set `srcnodata`/`dstnodata` explicitly (recommended `0`).
* After multiplication, clamp any tiny negative rounding artefacts to 0.

### 4.3 Output format (MUST)

Write final output as a **Cloud-Optimized GeoTIFF**:

* Path: `artefacts/rasters/hrsl_100m.tif`
* Internal tiling enabled (e.g., 512×512)
* Compression enabled (e.g., DEFLATE or ZSTD)
* Overviews enabled (for fast coarse reads)

---

## 5) Engine-fit validation checklist (MUST pass)

Codex MUST validate the produced file before sealing:

### 5.1 File validity

* File begins with a valid GeoTIFF header and opens via raster tooling.
* CRS == EPSG:4326
* Pixel size == `(0.0008333333333333334, 0.0008333333333333334)` within `1e-12`
* NoData is defined (recommended 0)

### 5.2 Non-toy realism floors

Fail closed if any of:

* Output file size `< 200 MB` (prevents “tiny stub raster”)
* Raster dimensions are implausibly small:

  * `width < 50,000` OR `height < 25,000`  *(coarse guardrail — adjust if your pipeline clips to land only)*
* More than 0.1% of sampled pixels are negative (should be ~0 after clamp)

*(If you later decide to clip to a land mask or a country subset to control size, keep that as an explicit v2 of this guide and update the realism floors accordingly.)*

### 5.3 Digests (MUST)

Compute:

* `sha256(hrsl_100m.tif bytes)` and record it in the 3B sealing inventory.

---

## 6) Provenance sidecar (MANDATORY)

Write:

* `artefacts/rasters/hrsl_100m.provenance.json`

Must include at minimum:

* `dataset_id: "hrsl_raster"`
* `{vintage}`, `{semver}`
* `source`:

  * `aws_registry_entry: "dataforgood-fb-hrsl"`
  * `bucket: "s3://dataforgood-fb-data/hrsl-cogs/"`
  * `vrt_url` used
  * `vrt_sha256`, `vrt_bytes`
* `build`:

  * target grid `tr_deg`
  * resampling law: `avg_then_times_9`
  * nodata value
  * toolchain versions (gdal/rasterio)
* `output`:

  * `sha256`
  * `bytes`

---

## 7) Reference pointers (for Codex)

* AWS Open Data registry entry (license + bucket ARN + no-sign-request listing): ([Open Data Registry][1])
* Example VRT usage paths (S3 + HTTP): ([docs.digitalearthafrica.org][2])
