## Acquisition Guide — `cdn_weights_ext_yaml` (External base CDN country weights)

### 0) Purpose

This artefact provides **stationary country weights** (`country_iso → weight`) that 3B uses as the **external base** for building `cdn_country_weights.yaml` (the internal wrapper). The output must be **global, heavy-tailed, and non-toy** (≥200 countries, realistic mass concentration).

Because a public “Akamai SOTI country weights YAML” isn’t reliably available as a machine-downloadable dataset, this guide defines a **Codex-no-input, CC-BY-4.0** acquisition route using World Bank–hosted indicators (ITU internet users % + World Bank population) to produce a realistic proxy distribution. World Bank open data is licensed under **CC BY 4.0** by default. ([World Bank Data Catalog][1])

---

### 1) Output identity (MUST)

* **Artefact name:** `cdn_weights_ext_yaml`
* **Path:** `artefacts/external/cdn_country_weights.yaml`
* **Format:** YAML (UTF-8, LF)
* **Version token:** `{vintage}` (provided by intake manifest; MUST NOT infer “latest”)

**File shape (strict; keep to this so downstream wrapper can parse):**

```yaml
version: "<vintage>"
countries:
  - country_iso: "US"
    weight: 0.182349817220
  - country_iso: "GB"
    weight: 0.045612398771
  ...
```

### 1.1 Placeholder resolution (MUST)

Replace the placeholders as follows:

* `<vintage>`: the version label provided by intake (e.g., `WDI_ITU_internet_users_share_2024`), used in the YAML payload.
* `{vintage_year}` in URLs: the integer year pinned in intake (e.g., `2024`).
* `{vintage_year-MAX_LAG_YEARS}`: compute as `vintage_year - MAX_LAG_YEARS` with `MAX_LAG_YEARS = 5`.

Do not infer a new vintage from upstream "latest" metadata.

---

### 2) Inputs Codex must be given (FAIL CLOSED if missing)

* `vintage` (string) — e.g. `WDI_ITU_internet_users_share_2024`
* `vintage_year` (int, YYYY) — e.g. `2024`
* Fixed policy constant: `MAX_LAG_YEARS = 5` (pinned)

---

### 3) Upstream sources (authoritative, CC-BY-4.0)

Use World Bank Indicators API (v2) to retrieve:

1. **Internet users (% of population)** — `IT.NET.USER.ZS`
   The indicator page shows license **CC BY-4.0**. ([World Bank Open Data][2])

2. **Population, total** — `SP.POP.TOTL`
   Retrieve via the same API (v2). The World Bank’s data licensing posture is CC BY 4.0 unless labeled otherwise. ([World Bank Data Catalog][1])

World Bank v2 API usage pattern is documented here (example includes `.../v2/country/all/indicator/...`). ([Data Help Desk][3])

---

### 4) Retrieval (MUST; deterministic)

Fetch these JSON payloads (store raw bytes for provenance + hashing):

* Internet users %, all countries, date window:

```
https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.ZS?date={vintage_year-MAX_LAG_YEARS}:{vintage_year}&format=json&per_page=20000
```

* Population total, all countries, date window:

```
https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?date={vintage_year-MAX_LAG_YEARS}:{vintage_year}&format=json&per_page=20000
```

Rules:

* Require HTTP 200 and JSON parse success.
* Fail if API returns an error payload or empty data.
* Compute `sha256` of each raw response and record in provenance.

---

### 5) Shaping algorithm (MUST; decision-free)

#### 5.1 Country universe extraction

From API rows, keep only entries where:

* `country.iso2Code` matches `^[A-Z]{2}$` (drop aggregates like “World”, regions, income groups) ([Data Help Desk][4])

Let `C_api` be the remaining ISO2 set.

#### 5.2 Choose “as-of” values per country (latest ≤ vintage_year)

For each country `c ∈ C_api`:

* From the fetched window, select the **latest year y ≤ vintage_year** with non-null value for:

  * `internet_pct(c,y)` from `IT.NET.USER.ZS`
  * `pop(c,y)` from `SP.POP.TOTL`
* If either series has no non-null value within the window → mark `c` as missing.

#### 5.3 Compute internet-user counts and weights

For each non-missing country:

* `users(c) = pop(c) * (internet_pct(c) / 100.0)`
* If `users(c) <= 0` → treat as missing (fail-closed cleanliness)

Let `P` be countries with valid `users(c)`.

Require:

* `|P| ≥ 200` (non-toy coverage). If not, **FAIL CLOSED**.

Normalize:

* `weight_raw(c) = users(c) / Σ_{j∈P} users(j)`

Emit only countries in `P` (missing countries are omitted; the internal wrapper can tail-fill).

---

### 6) Output formatting (MUST)

Write YAML:

* `version: <vintage>`
* `countries:` list sorted by `country_iso` ascending
* `weight` formatted as fixed-point with **12 digits after decimal**, no scientific notation.

---

### 7) Validations (MUST; FAIL CLOSED)

#### 7.1 Structural

* No duplicate `country_iso`
* `weight > 0` for all rows
* `abs(Σ weight - 1.0) ≤ 1e-12`

#### 7.2 Realism safeguards (non-toy)

* Heavy-tail check:

  * top 5 countries by weight carry **≥ 25%** of mass OR top 10 carry **≥ 40%**
* Coverage:

  * `len(countries) ≥ 200`

If any fail → abort (do not publish).

---

### 7.3 Acceptance checklist (MUST)

* YAML matches the required shape (`version`, `countries[]` with `country_iso`, `weight`).
* `country_iso` values are ISO2 uppercase, no duplicates.
* `weight > 0` for all rows and sums to 1.0 within 1e-12.
* Heavy-tail and coverage checks pass (`|countries| >= 200` and top-weight mass bounds).
* Provenance sidecar exists with raw response SHA-256 values and URLs.

---

### 8) Provenance sidecar (MANDATORY)

Write:

* `artefacts/external/cdn_country_weights.provenance.json`

Include:

* `dataset_id: "cdn_weights_ext_yaml"`
* `vintage`, `vintage_year`, `MAX_LAG_YEARS`
* Upstream URLs used
* Raw response digests + byte sizes
* Counts:

  * `countries_total_seen`, `countries_valid`, `countries_missing`
* Summary stats:

  * top-10 countries + weights (for audit)
  * heavy-tail check results
* License note:

  * cite World Bank CC BY 4.0 posture, and indicator license display for `IT.NET.USER.ZS`. ([World Bank Data Catalog][1])

---

### 9) What this enables downstream

This file becomes the **external base** for your internal `cdn_country_weights.yaml` wrapper (which can:

* canonicalize ISO,
* add a controlled tail for omitted countries,
* pin `edge_scale`,
* and enforce additional overlap checks).

