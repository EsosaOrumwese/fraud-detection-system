# Acquisition Guide — `iso3166_canonical_2024` (Canonical ISO-3166-1 Alpha-2 table)

## 0) Purpose and role in the engine

`iso3166_canonical_2024` is the engine’s **frozen canonical country code authority** for **ISO-3166-1 alpha-2 (`country_iso`)**. In **1A**, it is used for:

* **Validation**: all country ISO values in ingress/reference inputs must be members of this canonical set.
* **Deterministic tie-breaks**: when any step needs a stable “country order”, sorting by `country_iso` must be safe and consistent across runs.

This artefact MUST be treated as **the join spine** for `country_iso` across GDP, share surfaces, and merchant home countries.

---

## 1) Engine requirements (what you are freezing)

### 1.1 Artefact identity (MUST)

* **ID:** `iso3166_canonical_2024`
* **Version label:** `2024-12-31` *(see §7 for how to handle the date honestly)*
* **Format:** Parquet
* **Target path:** `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`

### 1.2 Schema (MUST match `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)

Required columns:

* `country_iso` *(ISO 3166-1 alpha-2)* **PK**
* `alpha3` *(ISO 3166-1 alpha-3)*
* `numeric_code` *(ISO 3166-1 numeric; store as integer / int16)*
* `name` *(English short name)*

Optional columns (may be NULL):

* `region`, `subregion`, `start_date`, `end_date`

### 1.3 Constraints (MUST)

* `country_iso` is unique (PK)
* (`alpha3`, `numeric_code`) is unique

### 1.4 Coverage requirement (MUST)

Every `country_iso` appearing in:

* `transaction_schema_merchant_ids.home_country_iso`
* `world_bank_gdp_per_capita_20250415.country_iso`
* `settlement_shares_2024Q4.country_iso`
* `ccy_country_shares_2024Q4.country_iso`

…MUST be present in `iso3166_canonical_2024.country_iso`.

---

## 2) Source quality bar (avoid “toy lists”)

A source is acceptable only if it meets **all** of:

* **Bulk access** (download/scrape) with repeatability
* **Clear licensing** for reuse in your repo + artefact store
* **Fields** sufficient to populate ISO2+ISO3+numeric+name without guesswork
* **Stability plan**: you can freeze a snapshot and prove what you froze (checksums + provenance)

---

## 3) Recommended sources (ranked)

### 3.1 Primary (recommended): GeoNames `countryInfo.txt` (direct download)

**Why**: single file includes ISO2/ISO3/numeric/name, bulk downloadable, and GeoNames publishes terms indicating CC-BY licensing + commercial use allowed + “as-is”. ([GeoNames][1])

**Important**: GeoNames explicitly documents that:

* UK official ISO code is **GB** and **UK is reserved**
* `XK` is a **temporary/non-ISO** Kosovo placeholder in their file header notes ([GeoNames][2])
  So you MUST apply canonicalisation rules (see §5).

### 3.2 Secondary (optional enrichment): UN Statistics Division M49 “Overview” table (scrape)

**Why**: provides **Region/Sub-region** and includes ISO alpha-2/alpha-3 columns you can use for cross-checking, plus it is maintained by UNSD. ([UNSD][3])

**Note**: this is an HTML table (scrapeable), not a clean CSV endpoint.

### 3.3 Official spot-check (manual / paid options): ISO

ISO states that the codes are available via the **Online Browsing Platform (OBP)** and also offers a **Country Codes Collection** product for downloadable formats. ([ISO][4])
Use ISO for **spot checks** or if you choose to pay for the official downloadable pack.

---

## 4) Working links and acquisition methods

### 4.1 Direct download (GeoNames) — preferred

```text
GeoNames countryInfo.txt (download):
https://download.geonames.org/export/dump/countryInfo.txt

GeoNames download + terms page:
https://www.geonames.org/export/

GeoNames “About” page (license statement):
https://www.geonames.org/about.html
```

GeoNames terms (cc-by, commercial allowed, as-is) are stated on their export/about pages. ([GeoNames][1])

**Acquisition (example)**

```bash
curl -L "https://download.geonames.org/export/dump/countryInfo.txt" -o countryInfo.txt
```

### 4.2 Optional enrichment scrape (UN M49 overview)

```text
UNSD M49 overview table (HTML):
https://unstats.un.org/unsd/methodology/m49/overview/
```

This page contains region/sub-region plus ISO alpha-2 and alpha-3 columns. ([UNSD][3])

### 4.3 ISO manual spot-check

```text
ISO 3166 info page (access routes + product mention):
https://www.iso.org/iso-3166-country-codes.html

ISO OBP UI:
https://www.iso.org/obp/ui/en/
```

ISO describes OBP access and the Country Codes Collection option here. ([ISO][4])

---

## 5) Canonicalisation and shaping rules (Codex implements; this doc specifies)

### 5.1 Field mapping (GeoNames → target)

From GeoNames `countryInfo.txt` columns:

* `ISO` → `country_iso`
* `ISO3` → `alpha3`
* `ISO-Numeric` → `numeric_code`
* `Country` → `name`

### 5.2 Inclusion/exclusion policy (MUST)

To avoid non-ISO / reserved code pollution:

* **MUST keep only** rows where `country_iso` matches `^[A-Z]{2}$`
* **MUST exclude**:

  * `XK` (GeoNames documents this as temporary/non-ISO) ([GeoNames][2])
  * `UK` (GeoNames notes UK is reserved; GB is official) ([GeoNames][2])

*(If you later decide you want Kosovo coverage, handle it explicitly as a separate policy choice, not an accidental leak from a source file.)*

### 5.3 Normalisation (MUST)

* `numeric_code` MUST be parsed as an integer (e.g., `"004"` → `4`) and stored as integer (int16 is fine).
* Output MUST be **sorted lexicographically by `country_iso`** before writing (tie-break determinism).

### 5.4 Optional enrichment (SHOULD if you need it)

If you want `region/subregion`:

* scrape UNSD M49 overview and left-join on ISO2.
* treat UNSD values as *enrichment only* (ISO2/ISO3/numeric/name remain anchored to your primary freezer rules). ([UNSD][3])

---

## 6) Engine-fit validation checklist (run before freezing)

### 6.1 Structural checks (MUST)

* No NULLs in `country_iso`, `alpha3`, `numeric_code`, `name`
* PK uniqueness: `country_iso` unique
* Uniqueness: (`alpha3`, `numeric_code`) unique
* No forbidden codes: `XK`, `UK` absent ([GeoNames][2])

### 6.2 Coverage checks vs 1A dependencies (MUST)

Confirm that all ISO2 values in:

* merchant ingress
* GDP per capita snapshot
* settlement shares surface
* currency-country shares surface
  …are present in this table (otherwise your 1A validation rules will correctly fail, and you’ll be forced into ad-hoc exceptions later).

### 6.3 “Not a toy list” check (SHOULD)

Row count should be in the ballpark of the full ISO3166-1 assigned universe (including territories/dependencies), not ~200 “UN members only”.

---

## 7) Version pinning (don’t lie to yourself)

GeoNames’ file is “current” and can change over time. The engine needs a **frozen snapshot**.

### 7.1 Default policy (MUST; decision-free)

* Always write the output to the contracted path/version `2024-12-31/`.
* If you do **not** possess an archived snapshot known to correspond to 2024-12-31, set `is_exact_vintage=false` in provenance (see 7.2) and freeze the bytes you download today.
* If you **do** possess an archived 2024-12-31 snapshot, you MAY use it and set `is_exact_vintage=true` (still record its raw sha256).

### 7.2 Provenance fields (MUST)

Provenance MUST record: `is_exact_vintage`, `upstream_retrieved_utc`, `upstream_url`, `upstream_version_label` (or null), `raw_bytes_sha256`, `output_sha256`, and `notes` (include exclusions like XK/UK).

---

## 8) Deliverables (what “done” looks like)

You should end up with:

1. `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`
2. A small provenance sidecar (json/yaml) containing:

   * source URLs, download timestamps, checksums, license note, and any exclusion rules applied (e.g., `XK`, `UK`)
3. (Optional) raw source archive retained alongside your internal artefact store (for audit/rebuild)

---

[1]: https://www.geonames.org/export/ "GeoNames webservice and data download"
[2]: https://download.geonames.org/export/dump/countryInfo.txt "download.geonames.org"
[3]: https://unstats.un.org/unsd/methodology/m49/overview/ "UNSD — Methodology "
[4]: https://www.iso.org/iso-3166-country-codes.html "ISO - ISO 3166 — Country Codes"
