# Acquisition Guide — `tz_world_2025a` (IANA TZ polygons, GeoParquet)

## 0) Purpose and role in the engine

`tz_world_2025a` is the engine’s **pinned world time-zone polygon table**, used downstream (notably **Segment 2A**) to map a `(lat, lon)` to an **IANA time zone ID** (`tzid`). The dataset is pinned in Layer-1 for hermeticity.

This is **not** an OSM planet download. We use **prebuilt release products** (tens of MB, not tens of GB).

---

## 1) Engine requirements (MUST)

### 1.1 Identity (MUST)

* **Dataset ID:** `tz_world_2025a`
* **Version:** `2025a`
* **Format:** Parquet (GeoParquet)
* **Path:** `reference/spatial/tz_world/2025a/tz_world.parquet`
* **License:** ODbL-1.0 (must be recorded in provenance)

### 1.2 Schema (MUST)

GeoParquet **geotable** with:

* **Primary key:** `(tzid, polygon_id)`
* Columns:

  * `tzid` (string): **IANA time zone ID** (e.g., `Europe/London`)
  * `polygon_id` (int32): deterministic polygon identifier per `tzid`
  * `geom` (geometry): Polygon or MultiPolygon, **CRS EPSG:4326**

The upstream release data associates each boundary with a tz database identifier and provides a `tzid` attribute/property. ([GitHub][1])

---

## 2) Recommended source (small, authoritative, versioned)

### Primary source: `timezone-boundary-builder` release **2025a**

* Project produces timezone boundary files (GeoJSON + Shapefile) aligned to tz database releases. ([GitHub][1])
* Output data is licensed under **ODbL**. ([GitHub][1])
* You download **one zip** from a release, not raw OSM.

**Why this won’t be 35–56GB**
A recent release shows typical asset sizes in the **tens of MB** (e.g., 23–72MB for common products). ([GitHub][2])

### Version alignment note

IANA announced tz database release **2025a** (Jan 16, 2025). ([IANA Lists][3])
`timezone-boundary-builder` uses tz database releases as its release numbering scheme. ([GitHub][1])

---

## 3) Acquisition method (download)

### 3.1 Choose an upstream release product (PINNED for now; move to config later)

Use a product that:

* includes `tzid`
* is global coverage
* preferably includes oceans to avoid “holes” outside land polygons

**Recommended default (most common for point-in-polygon lookups):**

* `timezones-with-oceans.shapefile.zip`
  (Example of this exact filename being used from releases: datasette tutorial downloads it from a release.) ([Datasette][4])

**Smaller alternatives (if needed):**

* `timezones-with-oceans.geojson.zip`
* `timezones-with-oceans-1970.*` and `timezones-with-oceans-now.*` exist as other variations; recent release assets show these variants and their sizes (e.g., 45.4MB GeoJSON, 71.6MB shapefile for `with-oceans-1970`). ([GitHub][2])

### 3.2 Working links (copy/paste)

```text
# Release pages (browse + manual download)
https://github.com/evansiroky/timezone-boundary-builder/releases
https://github.com/evansiroky/timezone-boundary-builder/releases/tag/2025a

# License (data is ODbL)
https://github.com/evansiroky/timezone-boundary-builder/blob/master/DATA_LICENSE

# IANA tz database 2025a announcement (version evidence)
https://lists.iana.org/hyperkitty/list/tz-announce@iana.org/thread/MWII7R3HMCEDNUCIYQKSSTYYR7UWK4OQ/
```

### 3.3 Direct download URLs (deterministic)

GitHub release assets follow a stable pattern:

```text
https://github.com/evansiroky/timezone-boundary-builder/releases/download/<TAG>/<ASSET_FILENAME>
```

### 3.4 Placeholder resolution (MUST)

Replace the angle-bracket tokens as follows:

* `<TAG>`: the tzdb release tag (v1 is `2025a`).
* `<ASSET_FILENAME>`: the exact asset name chosen by the pinned preference order in 3.1.

The resolved URL MUST match an asset listed under the chosen tag; do not guess filenames outside that list.

So for `2025a`, the default asset is expected at:

```text
https://github.com/evansiroky/timezone-boundary-builder/releases/download/2025a/timezones-with-oceans.shapefile.zip
```

**Fallback if 404 (MUST):** enumerate the release assets for tag `2025a` and select the asset filename matching the pinned preference order:
1) `timezones-with-oceans.shapefile.zip`
2) else `timezones-with-oceans.geojson.zip`
Fail closed if neither exists.

(That naming pattern is stable across releases; it's explicitly used in public tutorials.) ([Datasette][4])

---

## 4) Shaping rules (Codex implements; this doc specifies)

### 4.1 Read and normalize geometries

From the downloaded release asset:

* Read features; each feature must have a `tzid` attribute/property. ([GitHub][1])
* Ensure CRS is **EPSG:4326**.
* Normalize geometry column name to `geom`.
* Ensure geometry types are Polygon or MultiPolygon.

### 4.2 Enforce tzid validity (MUST)

* `tzid` must be non-empty, and must match the basic IANA form:

  * `^[A-Za-z_]+/[A-Za-z0-9_+-]+$` OR `^Etc/[A-Za-z0-9_+-]+$`
* Drop any feature with missing/invalid `tzid` and record in provenance.

### 4.3 Deterministic `polygon_id` assignment (MUST)

Because PK is `(tzid, polygon_id)` and one `tzid` can have multiple polygons:

1. For each feature, explode MultiPolygon → individual Polygon parts.
2. For each `tzid`, sort polygon parts by this deterministic key:

   * `area(desc)` in EPSG:4326 **computed consistently** (MUST use geodesic area; alternatively use one pinned equal-area projection and record it in provenance)
   * then `bbox(minx, miny, maxx, maxy)` ascending
   * then `centroid(x, y)` ascending
   * then final tie-break: `sha256(WKB)` ascending (WKB emitted in a stable canonical form by the chosen GIS stack)
3. Assign `polygon_id = 0..n-1` in that sorted order.

This guarantees stable IDs across runs for the same upstream asset.

### 4.4 Output ordering (SHOULD)

Write rows sorted by `(tzid ASC, polygon_id ASC)`.

---

## 5) Engine-fit validation checklist (MUST pass)

### 5.1 Structural

* PK uniqueness: `(tzid, polygon_id)` unique
* `tzid` non-null; `polygon_id` non-null int32
* `geom` non-null, non-empty
* geometry type ∈ {Polygon, MultiPolygon}
* CRS = EPSG:4326

### 5.2 Coverage sanity (SHOULD)

* No “holes” for expected coordinate domains:

  * If using “with-oceans” variant, you should be able to map most ocean coordinates as well (useful for robustness).
* Optional test: sample a set of known world cities and verify non-null tzid mapping.

---

## 6) Provenance sidecar (MANDATORY)

Write `reference/spatial/tz_world/2025a/tz_world.provenance.json` containing:

* source: `timezone-boundary-builder`
* release tag used: `2025a`
* asset filename used (e.g., `timezones-with-oceans.shapefile.zip`)
* download timestamp (UTC)
* raw asset checksum (sha256)
* output parquet checksum (sha256)
* license note: ODbL-1.0 and attribution requirements (OSM-derived) ([GitHub][1])
* counts:

  * number of tzids
  * total polygon parts (post-explode)
  * dropped/invalid tzid features (if any)

---

## 7) Deliverables

1. `reference/spatial/tz_world/2025a/tz_world.parquet`
2. `reference/spatial/tz_world/2025a/tz_world.provenance.json`

---

[1]: https://github.com/evansiroky/timezone-boundary-builder "GitHub - evansiroky/timezone-boundary-builder: A tool to extract data from Open Street Map (OSM) to build the boundaries of the world's timezones."
[2]: https://github.com/evansiroky/timezone-boundary-builder/releases "Releases · evansiroky/timezone-boundary-builder · GitHub"
[3]: https://lists.iana.org/hyperkitty/list/tz-announce@iana.org/thread/MWII7R3HMCEDNUCIYQKSSTYYR7UWK4OQ/ "2025a release of tz code and data available"
[4]: https://datasette.io/tutorials/spatialite "Building a location to time zone API with SpatiaLite - Tutorial"
