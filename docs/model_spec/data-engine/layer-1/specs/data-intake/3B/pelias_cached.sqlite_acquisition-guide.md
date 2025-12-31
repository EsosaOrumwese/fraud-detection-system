## Acquisition Guide — `pelias_cached.sqlite` (Offline gazetteer bundle for evidence-URL validation)

### 0) Purpose (what this is for)

`pelias_cached.sqlite` is the **offline geocode bundle** 3B uses to sanity-check / validate **settlement evidence** (e.g., place-name derived from evidence URLs) without calling external services. It must be **global**, **non-toy**, and stable enough to be sealed in 3B.S0.

In 3B contracts this is the ingress dataset:

* **dataset_id:** `pelias_cached_bundle`
* **path:** `artefacts/geocode/pelias_cached.sqlite`
* **version token:** `{pelias_version}`
* **license posture:** CC-BY-4.0 (GeoNames-compatible) ([download.geonames.org][1])

---

### 1) Inputs Codex must have (no human input)

Codex must be given (by config/manifest):

* `pelias_version` (string): a pinned label for this build (e.g., `2025-12-26`).
  If missing → **FAIL CLOSED** (no “latest” inference).

---

### 1.1 Placeholder resolution (MUST)

Replace placeholder tokens consistently:

* `{pelias_version}` and `<pelias_version>`: the pinned version label provided by intake.
* `<sha256 of pelias_cached.sqlite bytes>`: the lowercase hex SHA-256 of the final sqlite bytes.

Do not infer a new version from upstream "latest" metadata.

---

### 2) Source strategy (authoritative; fail-closed)

This project treats the bundle as a **SQLite gazetteer built deterministically from GeoNames dumps** (the same ecosystem Pelias commonly imports). ([GitHub][2])

**Required upstream files (GeoNames Gazetteer extract):**

* `cities500.zip` (baseline “real deal” size: ~185k settlements)
* `countryInfo.txt`
* `admin1CodesASCII.txt`
* `timeZones.txt`

GeoNames publishes these as tab-delimited UTF-8 extracts and states CC-BY-4.0 on the dump page/readme. ([download.geonames.org][1])

**Download base URL (GeoNames dump):**

```text
https://download.geonames.org/export/dump/
```

(If any required file is missing/unreachable → **FAIL CLOSED**. No fallbacks to random mirrors.)

---

### 3) Retrieval (download) rules

For each required file, Codex MUST:

1. Download via HTTPS from the base URL.
2. Fail if HTTP status != 200.
3. Fail if content is HTML/error text.
4. Record `raw_sha256` and `byte_size`.
5. Enforce minimum plausible sizes:

   * `cities500.zip` ≥ 1 MB
   * the `.txt` files ≥ 1 KB

---

### 4) Build rule (deterministic SQLite bundle)

Codex must build **one** SQLite file at:

```text
artefacts/geocode/pelias_cached.sqlite
```

#### 4.1 SQLite determinism knobs (required)

To keep outputs stable (within a fixed sqlite runtime):

* Set a fixed `page_size` (recommend 4096).
* Disable journaling for build (`journal_mode=OFF`) and use `VACUUM` once at end.
* Insert rows in deterministic order (see below).
* Record `sqlite_version()` in provenance.

*(The authoritative digest is still the SHA-256 of the final sqlite bytes; determinism knobs reduce accidental churn.)*

#### 4.2 Required tables (minimum “real deal” schema)

Build at least these tables:

1. `geoname` (from `cities500.zip`)

* Must include the core GeoNames fields:
  `geonameid (PK), name, asciiname, alternatenames, latitude, longitude, feature_class, feature_code, country_code, admin1_code, admin2_code, admin3_code, admin4_code, population, elevation, dem, timezone, modification_date`

2. `country_info` (from `countryInfo.txt`)
3. `admin1_codes` (from `admin1CodesASCII.txt`)
4. `timezones` (from `timeZones.txt`)

#### 4.3 Required indexes (non-toy usability)

* `geoname(country_code)`
* `geoname(feature_class, feature_code)`
* `geoname(population DESC)` (or equivalent)
* A name lookup structure:

  * either a simple index on `name` + `asciiname`
  * **or** an FTS index (preferred) over `{name, asciiname, alternatenames}`

#### 4.4 Deterministic row ordering (required)

* `geoname`: insert in ascending `geonameid`
* `country_info`: ascending ISO2
* `admin1_codes`: ascending `code`
* `timezones`: ascending `(countryCode, timezoneId)`

#### 4.5 NoData / missing handling (strict)

This bundle is built from **text dumps**, so:

* Do not invent missing countries.
* Preserve strings exactly as in dumps (UTF-8).
* If a row is malformed (wrong number of columns) → **FAIL CLOSED**.

---

### 5) Engine-fit validation checklist (must pass)

Codex MUST validate the built sqlite file before sealing:

#### 5.1 File validity

* First 16 bytes match SQLite magic (`SQLite format 3\000`).
* File opens with sqlite and passes `PRAGMA integrity_check;` == `ok`.

#### 5.2 “Real deal” volume / coverage floors

* `COUNT(*) FROM geoname` ≥ **150,000** (prevents toy bundles)
* `COUNT(DISTINCT country_code) FROM geoname` ≥ **200**
* `COUNT(*) FROM country_info` ≥ **200**
* If FTS is used: it must contain ≥ the same row count as `geoname` (or a documented content strategy).

#### 5.3 Sanity checks

* Lat/lon bounds respected: `latitude ∈ [-90,90]`, `longitude ∈ [-180,180]`
* `population` non-negative

Fail any check → **FAIL CLOSED** (do not publish, do not seal).

---

### 6) Packaging outputs (what gets written)

Under `artefacts/geocode/`:

1. `pelias_cached.sqlite`  ✅ (the actual bundle)
2. `pelias_cached_bundle.json` ✅ (metadata contract; see §7)
3. `pelias_cached_bundle.provenance.json` ✅ (provenance sidecar)

---

### 7) Metadata contract file (required for your schema anchor)

Write:

```text
artefacts/geocode/pelias_cached_bundle.json
```

JSON object:

```json
{
  "version": "<pelias_version>",
  "sha256_hex": "<sha256 of pelias_cached.sqlite bytes>",
  "tile_span": "global",
  "licence": "CC-BY-4.0 (GeoNames Gazetteer extract)",
  "notes": "Built deterministically from GeoNames dump files: cities500.zip, countryInfo.txt, admin1CodesASCII.txt, timeZones.txt."
}
```

This aligns with the contract shape that requires `{version, sha256_hex}` and allows `tile_span/licence/notes`. ([download.geonames.org][1])

---

### 8) Provenance sidecar (mandatory)

Write `pelias_cached_bundle.provenance.json` containing:

* `dataset_id: "pelias_cached_bundle"`
* `pelias_version`
* `upstream_sources`:

  * base_url
  * filenames + `raw_sha256` + `bytes`
* `build`:

  * `sqlite_version`
  * row counts per table
  * index list (names)
* `output`:

  * `sqlite_sha256`
  * `bytes`
* `retrieved_at_utc` (timestamp is fine here; it’s provenance, not a sealed policy surface)

---

### 9) Reference URLs (for Codex, in code)

```text
# GeoNames dump directory + readme/license
https://download.geonames.org/export/dump/

# Required files
https://download.geonames.org/export/dump/cities500.zip
https://download.geonames.org/export/dump/countryInfo.txt
https://download.geonames.org/export/dump/admin1CodesASCII.txt
https://download.geonames.org/export/dump/timeZones.txt
```

GeoNames dump readme states CC-BY-4.0 and describes the extract files. ([download.geonames.org][1])

