# Acquisition Guide — `world_bank_gdp_per_capita_20250415` (WDI GDP per capita, constant 2015 USD)

## 0) Purpose and role in the engine

This artefact is the **frozen GDP-per-capita “vintage”** used by **Segment 1A** for:

* **GDP buckets** (via the precomputed `gdp_bucket_map_2024`)
* **A numeric GDP signal** used downstream in 1A’s modelling logic (e.g., log-GDP terms)

The source MUST be **World Bank World Development Indicators (WDI)** and MUST be the **constant-price (base year 2015 USD) series**, not “current USD”.

Indicator definition and licensing are published on the World Bank indicator page. ([World Bank Open Data][1])

---

## 1) Engine requirements (what you are freezing)

### 1.1 Artefact identity (MUST)

* **ID:** `world_bank_gdp_per_capita_20250415`
* **Version label:** `2025-04-15`
* **Format:** Parquet
* **Target path:** `reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet`
* **Schema anchor:** `schemas.ingress.layer1.yaml#/world_bank_gdp`
* **License:** **CC-BY-4.0** (must be recorded in metadata) ([World Bank Open Data][1])

### 1.2 Required series (MUST)

* **WDI indicator code:** `NY.GDP.PCAP.KD`
* **Meaning:** GDP per capita (**constant 2015 US$**) ([World Bank Open Data][1])

### 1.3 Required table schema (MUST)

Columns:

* `country_iso` (ISO-3166-1 alpha-2; FK into `iso3166_canonical_2024.country_iso`)
* `observation_year` (int16)
* `gdp_pc_usd_2015` (float64; **strictly > 0**)
* `source_series` (string; **const** `NY.GDP.PCAP.KD`)

Primary key:

* (`country_iso`, `observation_year`)

### 1.4 Year pin used by 1A (MUST keep in mind)

Your 1A spec pins the “GDP function” for this run to **`observation_year = 2024`** (fixed). Practically: your frozen dataset MUST include **valid 2024 values** for the countries you expect the engine to operate over, or the run will fail at validation time (or you’ll be forced into ad-hoc exceptions later).

---

## 2) Source quality bar (avoid “toy GDP lists”)

Acceptable sources MUST be:

* **World Bank WDI** (official distribution)
* **Bulk-accessible** and reproducible (API or archived bulk releases)
* **Clearly licensed** (CC-BY-4.0) ([World Bank Data Catalog][2])
* Provide the exact indicator `NY.GDP.PCAP.KD` (constant 2015 US$), not derived/third-party mirrors

---

## 3) Recommended acquisition routes (pick one)

### Route A (recommended for “true vintage” reproducibility): WDI Archives (bulk snapshot)

Use the **WDI Archives** page to fetch the archived WDI release closest to your intended version, then extract only `NY.GDP.PCAP.KD`.

Why this is best:

* You can point to a **named archived release** (strong provenance)
* You can rebuild the artefact later even if the “current” database updates

The World Bank maintains a “WDI Archives” page with month-stamped archive downloads. ([Data Topics][3])

### Route B (recommended for automation + minimal bulk): World Bank Indicators API (programmatic)

Use the Indicators API to retrieve only the indicator you need.

Why this is good:

* Small download footprint (only one indicator)
* No dependency on huge bulk files
* The API is the official path for programmatic WDI access ([World Bank Data Help Desk][4])

---

## 4) Working links (copy/paste)

```text
# Indicator definition page (series identity + license + years shown)
https://data.worldbank.org/indicator/NY.GDP.PCAP.KD

# Indicators API docs (how to form calls; JSON via format=json)
https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures
https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation

# WDI dataset catalog metadata (license + coverage)
https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators

# World Bank public licensing page (CC-BY 4.0 default for WB-produced datasets)
https://datacatalog.worldbank.org/public-licenses

# WDI Archives (bulk snapshot downloads by month)
https://datatopics.worldbank.org/world-development-indicators/wdi-archives.html
```

Indicator licensing (CC-BY-4.0) and coverage up to 2024 are shown on the indicator page. ([World Bank Open Data][1])
WDI dataset licensing/coverage are also stated in the Data Catalog entry. ([World Bank Data Catalog][5])

---

## 5) Route A procedure — WDI Archives snapshot (bulk)

### 5.1 Acquire the archive (MUST)

1. Go to the **WDI Archives** page.
2. Pick the archive closest to your target vintage (e.g., April 2025 is listed on the page). ([Data Topics][3])
3. Download the archive zip from the DataBank "download/Archive" link (the page lists direct `.zip` links). ([Data Topics][3])
4. Record the **exact archive filename** you downloaded (do not assume it equals the version label), plus SHA-256 of the raw zip.

### 5.2 Extract the indicator (MUST)

From the bulk archive contents:

* Use the file(s) that contain the country-year indicator matrix (bulk WDI releases include data + metadata; the WDI products page describes bulk downloads). ([World Bank Open Data][6])
* Filter down to **indicator code `NY.GDP.PCAP.KD`** only.

### 5.3 Shape to engine schema (MUST)

* Map country code to **ISO2 (`country_iso`)**
* Keep rows where `observation_year` is within the needed range (engine pins 2024; you may keep the full series, but 2024 MUST be present where required)
* Rename value column to `gdp_pc_usd_2015`
* Add `source_series = NY.GDP.PCAP.KD`

---

## 6) Route B procedure — Indicators API (programmatic)

### 6.1 API call structure (MUST)

The World Bank’s API supports country/indicator calls; JSON output is requested with `format=json`. ([World Bank Data Help Desk][7])

Use the standard pattern (example in docs is Brazil GDP, with a `date=` parameter). ([World Bank Data Help Desk][7])

### 6.2 Suggested retrieval calls (MUST be pinned)

```text
# Retrieve indicator data for all countries (time series)
https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.KD?format=json&per_page=20000

# Or restrict to the pinned year (2024) if you only want what 1A uses
https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.KD?date=2024&format=json&per_page=20000
```

Notes:

* Expect pagination metadata; the docs show paged responses (page/per_page/total semantics). ([World Bank Data Help Desk][7])
* The API also defaults to XML unless you set `format=json`. ([World Bank Data Help Desk][7])

### 6.3 Country filtering (MUST)

The API can return aggregates/regions depending on the endpoint and parameters. To keep the dataset ISO-canonical:

* Keep only rows where `country_iso` is exactly 2 uppercase letters AND exists in `iso3166_canonical_2024`.
* Drop aggregates/regions/invalid codes.

---

## 7) Canonicalisation rules (Codex implements; this doc specifies)

### 7.1 Inclusion rules (MUST)

* `country_iso` MUST be ISO2 and MUST be present in `iso3166_canonical_2024`
* `gdp_pc_usd_2015` MUST be non-null and **> 0**
* `source_series` MUST be exactly `NY.GDP.PCAP.KD` ([DataBank][8])

### 7.2 Year policy (MUST)

Because 1A pins `observation_year = 2024`:

* You MUST confirm that 2024 values exist for the required operating country set.
* If coverage is incomplete, you MUST choose one explicit resolution path (don’t wing it):

  * **Change the pinned year** (and update artefact IDs + bucket map year), or
  * **Define a deterministic fill policy** and record it as a separate governed rule (recommended only if you truly need “total function” coverage).

---

## 8) Engine-fit validation checklist (do before freezing)

### 8.1 Structural (MUST)

* PK uniqueness: (`country_iso`, `observation_year`) unique
* `gdp_pc_usd_2015 > 0` for all rows
* `source_series` constant `NY.GDP.PCAP.KD`

### 8.2 Coverage (MUST)

* For the pinned year **2024**, every country you expect the engine to support MUST have a value.
* At minimum, ensure coverage for all `country_iso` that appear in:

  * merchant home countries
  * settlement/currency share surfaces
  * your bucket map join spine

### 8.3 Provenance (MUST)

Record:

* acquisition route (Archives vs API)
* source URL(s)
* download timestamp
* raw checksum(s)
* output parquet checksum
* license note (CC-BY-4.0) ([World Bank Data Catalog][2])

---

## 9) Deliverables (what “done” looks like)

1. `reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet`
2. Provenance sidecar capturing:

   * `indicator_code = NY.GDP.PCAP.KD`
   * acquisition method + URLs + timestamps + checksums
   * license attribution statement (CC-BY-4.0) ([World Bank Open Data][1])
3. (Optional but recommended) the raw archive zip or raw API response stored in your artefact store for rebuild/audit.

---

[1]: https://data.worldbank.org/indicator/NY.GDP.PCAP.KD "GDP per capita (constant 2015 US$) | Data"
[2]: https://datacatalog.worldbank.org/public-licenses "Data Access And Licensing - World Bank Data Catalog"
[3]: https://datatopics.worldbank.org/world-development-indicators/wdi-archives.html "WDI - WDI Archives"
[4]: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation "About the Indicators API Documentation – World Bank Data Help Desk"
[5]: https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators "World Development Indicators - World Bank Data Catalog"
[6]: https://data.worldbank.org/products/wdi "WDI - Home"
[7]: https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures "API Basic Call Structures – World Bank Data Help Desk"
[8]: https://databank.worldbank.org/metadataglossary/sustainable-development-goals-%28sdgs%29/series/NY.GDP.PCAP.KD "Metadata Glossary - DataBank - World Bank"
