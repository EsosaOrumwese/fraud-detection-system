Yes — **`world_countries` should be small** (MBs to a few 10s of MB), *as long as we don’t touch OSM planet dumps*. We’ll use a **country-boundary vector dataset** and convert it to **GeoParquet**.

# Acquisition Guide — `world_countries` (Country polygons, GeoParquet)

## 0) Purpose and role in the engine

`world_countries` is the engine’s **country polygon boundary table** used for:

* geo conformance checks (points-in-country),
* spatial joins / clipping,
* later downstream uses (1B placement sanity checks; 2A provenance pins).

This is **not** a "world map" raster and **not** OSM planet data.

**Pinned licence for this artefact (MUST):** if using Natural Earth as Route A, record licence as **Public Domain** and align `artefact_registry` + `dataset_dictionary` accordingly (do not claim ODbL).

---

## 1) Engine requirements (MUST)

### 1.1 Identity

* **Dataset ID:** `world_countries`
* **Version:** `2024`
* **Format:** **GeoParquet**
* **Path:** `reference/spatial/world_countries/2024/world_countries.parquet`

### 1.2 Schema (GeoParquet geotable)

Primary key: **`country_iso`**

Columns:

* `country_iso` (ISO-3166-1 alpha-2, uppercase; FK → `iso3166_canonical_2024.country_iso`)
* `name` (string; optional)
* `geom` (geometry; **Polygon or MultiPolygon**; CRS **EPSG:4326**)

---

## 2) Recommended source (small, stable, automatable)

### 2.1 Routing policy (MUST; decision-free)

* **Default:** Route A (Natural Earth Admin 0 Countries).
* **Fallback (ONLY if default fails):** Route B (geoBoundaries).
* Default failure triggers: download 404/410, unreadable archive, or post-shaping coverage check fails to include every ISO2 needed by the join spine (`iso3166_canonical_2024` and merchant home countries).

### Route A (PRIMARY): Natural Earth Admin 0 Countries (10m)

Why:

* It’s **public domain** and hosted as a **simple ZIP shapefile** on AWS and NACIS infrastructure. ([Registry of Open Data][1])
* You download only the one file you need — not the full Natural Earth bundle.

**Working download options**

* **NACIS CDN direct ZIP** (simple HTTP):

  * `https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip` ([rOpenSci][2])
* **AWS Open Data S3 bucket** (reliable, no account):

  * Use `aws s3 ls --no-sign-request s3://naturalearth/` and download the specific ZIP you need. ([Registry of Open Data][1])

**Size note**

* This is **not** 35–56GB. It’s a single country-boundary ZIP.

### Route B (FALLBACK): geoBoundaries (global ADM0)

Why:

* Provides **global country boundaries**, downloadable via GUI or API; CC-BY 4.0. ([geoBoundaries][4])
* Use their “Global Files” or API if Natural Earth endpoints are flaky.

---

## 3) Acquisition method (download)

### 3.1 Natural Earth (recommended)

1. Download the ZIP from NACIS CDN (or AWS S3). ([rOpenSci][2])
2. Extract the shapefile contents.
3. Read the shapefile as a geotable (it’s already WGS84 / EPSG:4326 in practice; still verify).

### 3.2 geoBoundaries fallback

1. Use the geoBoundaries download page “Global Files” or the API to obtain the ADM0 global dataset. ([geoBoundaries][4])
2. Proceed to the same shaping rules below.

---

## 4) Shaping rules (Codex implements; this doc specifies)

### 4.1 Determine `country_iso` deterministically

From source attributes:

* Prefer an **ISO2 field** if present and valid (`^[A-Z]{2}$`).
* If ISO2 is missing/invalid (e.g., `-99` in some Natural Earth rows), fall back to **ISO3 → ISO2** using `iso3166_canonical_2024.alpha3 → country_iso`.
* If neither mapping yields a valid ISO2 in `iso3166_canonical_2024`, **drop the row** (and record it in provenance).

### 4.2 Enforce PK uniqueness

If multiple source features map to the same `country_iso`:

* **Dissolve** geometries by `country_iso` (union) to produce exactly one row per ISO2.
* `name` selection:

  * Prefer `iso3166_canonical_2024.name` (if you want consistent naming),
  * else pick a deterministic source name (lexicographically smallest).

### 4.3 Geometry rules (MUST)

* Output geometry column name: **`geom`**
* CRS must be **EPSG:4326**
* Geometry must be **Polygon or MultiPolygon**
* Geometry must be **non-empty**
* If any geometry is invalid:

  * apply a deterministic “make valid” step (record the method in provenance).

---

## 5) Engine-fit validation checklist (MUST pass)

### 5.1 Table integrity

* `country_iso` unique
* `country_iso` ∈ `iso3166_canonical_2024.country_iso`
* `geom` non-null, non-empty
* geometry type ∈ {Polygon, MultiPolygon}
* CRS = EPSG:4326

### 5.2 Coverage sanity (SHOULD)

At minimum, you should cover every `country_iso` that appears in:

* `transaction_schema_merchant_ids.home_country_iso`
* `world_bank_gdp_per_capita_20250415.country_iso`
* `settlement_shares_2024Q4.country_iso`
* `ccy_country_shares_2024Q4.country_iso`

If a country appears in those but has no polygon here, downstream geo checks won’t be meaningful.

---

## 6) Provenance sidecar (MANDATORY)

Store next to the parquet:

* source route (Natural Earth vs geoBoundaries)
* exact URL(s)
* download timestamp
* raw checksum(s)
* list of dropped/failed-to-map features (with source identifiers)
* dissolve count (how many ISO2 had >1 feature)
* output checksum

**Licensing note:** Natural Earth is **public domain** per the AWS registry entry. ([Registry of Open Data][1])
(Your current registry/dictionary says ODbL for `world_countries`; if you adopt Natural Earth, you should patch that metadata later to avoid license mismatch.)

---

## 7) Deliverables

1. `reference/spatial/world_countries/2024/world_countries.parquet`
2. `reference/spatial/world_countries/2024/world_countries.provenance.json` (or yaml)

[1]: https://registry.opendata.aws/naturalearth/ "Natural Earth - Registry of Open Data on AWS"
[2]: https://docs.ropensci.org/rnaturalearth/reference/countries.html "world country polygons from Natural Earth - Docs - rOpenSci"
[3]: https://www.geoboundaries.org/countryDownloads.html "geoBoundaries"

---

## Working links (copy/paste)

```text
# Natural Earth (recommended): direct ZIPs (small files)
# 10m (high detail; Natural Earth page lists “countries” around ~4.7 MB)
https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip

# 50m (medium detail; good compromise)
https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip

# 110m (low detail; very small)
https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip


# Natural Earth via AWS Open Data (if you want S3-backed reliability)
# Registry entry (shows bucket + “no-sign-request” usage)
https://registry.opendata.aws/naturalearth/

# List the bucket (no account):
aws s3 ls --no-sign-request s3://naturalearth/


# geoBoundaries fallback (CC BY 4.0)
# API docs (supports ALL + ADM0)
https://www.geoboundaries.org/api.html

# Global ADM0 via API (returns JSON with download URLs)
https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM0/

# geoBoundaries home (license info + download entry points)
https://www.geoboundaries.org/
```

Notes:

* Natural Earth "Admin 0 - Countries" is small (the site lists the ZIP around ~4.7 MB at 10m). ([Natural Earth Data][3])
* The NACIS CDN URLs are widely referenced as the canonical direct downloads. ([rOpenSci][2])
* AWS registry confirms the `naturalearth` S3 bucket and `--no-sign-request` access pattern. ([Registry of Open Data][1])
* geoBoundaries API supports `ALL` for global files and documents the endpoint format. ([geoBoundaries][4])

[1]: https://registry.opendata.aws/naturalearth/ "Natural Earth - Registry of Open Data on AWS"
[2]: https://docs.ropensci.org/rnaturalearth/reference/countries.html "world country polygons from Natural Earth - Docs - rOpenSci"
[3]: https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/ "Admin 0 - Countries - Natural Earth"
[4]: https://www.geoboundaries.org/api.html "geoBoundaries API"
