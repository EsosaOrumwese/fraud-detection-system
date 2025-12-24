# Acquisition Guide — `ccy_country_shares_2024Q4` (Currency-area country split priors)

## 0) Purpose and role in the engine

`ccy_country_shares_2024Q4` is an **ingress prior surface**: for each ISO-4217 currency **κ**, it provides a **probability vector over countries that are in κ’s “currency area”** (countries/territories that use κ as their currency). It is consumed by **1A.S5** and blended with `settlement_shares_2024Q4` to produce the authoritative `ccy_country_weights_cache`.  

This dataset is **not settlement flow**; it is a **structural prior** (“who could plausibly sit under this currency code”) with a deterministic split. 

---

## 1) Engine requirements (MUST)

### 1.1 Identity (MUST)

* **Dataset ID:** `ccy_country_shares_2024Q4` 
* **Version:** `2024Q4` 
* **Format:** parquet 
* **Path:** `reference/network/ccy_country_shares/2024Q4/ccy_country_shares.parquet`  
* **Partitions:** none 

### 1.2 Schema (MUST match `schemas.ingress.layer1.yaml#/ccy_country_shares_2024Q4`)

* **PK:** `(currency, country_iso)`
* Columns:

  * `currency` : ISO-4217 alpha-3 uppercase
  * `country_iso` : ISO-3166-1 alpha-2 uppercase (FK → `iso3166_canonical_2024.country_iso`)
  * `share` : float in **[0,1]**
  * `obs_count` : int64 **≥ 0**
* Constraint:

  * for each `currency`: **Σ share = 1.0 ± 1e-6**  

### 1.3 Hard failure behaviour (MUST remember)

S5 **fails closed** if any of: bad ISO codes, FK violations, share outside [0,1], NaN/Inf, PK duplicates, or per-currency sum not within tolerance. The engine does **not repair** ingress. 

---

## 2) What “good enough” means (avoid toy priors)

A production-useful `ccy_country_shares` must:

* derive membership from an **authoritative currency list** (not hand-edited Wikipedia tables),
* use a **defensible deterministic weighting** for multi-country currencies,
* include a **meaningful `obs_count`** (it drives effective evidence when blending in S5), not all zeros. 

---

## 3) Recommended source strategy (authoritative + automatable)

### 3.1 Currency→Entity membership (authoritative)

Use the **ISO 4217 “List One: Current Currency & Funds”** published by SIX (ISO 4217 Maintenance Agency). SIX publishes List One in **XLS and XML**. ([SIX][1])
ISO itself points people to machine-readable lists maintained by the agency. ([ISO][2])

**Working links (copy/paste):**

```text
# SIX ISO 4217 List One (XLS)
https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xls

# SIX ISO 4217 List One (XML)
https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml

# SIX “data standards” page (lists current/historical lists and links)
https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html

# ISO 4217 overview page
https://www.iso.org/iso-4217-currency-codes.html
```

List One includes the relevant columns (“ENTITY”, “Currency”, “Alphabetic Code”, etc.). ([SIX][3])

### 3.2 Country weighting prior (defensible for splits)

For multi-country currencies, weight members by **economic size** using **World Bank WDI GDP (current US$)** for year **2024**:

* Indicator: `NY.GDP.MKTP.CD` (“GDP (current US$)”, CC BY 4.0) ([World Bank Open Data][4])

Working links:

```text
# Indicator page (definition + license)
https://data.worldbank.org/indicator/NY.GDP.MKTP.CD

# Indicator API metadata endpoint (exists; API supports JSON via format=json)
https://api.worldbank.org/v2/indicator/NY.GDP.MKTP.CD
```

### 3.3 Currency importance prior for `obs_count` (optional but recommended)

Use BIS Triennial Survey **D11.3 “FX turnover by currency”** to allocate a realistic evidence mass across currencies (major currencies get higher pseudo-counts). ([Bank for International Settlements][5])

Working link:

```text
# BIS Triennial Survey tables index (includes D11.3)
https://www.bis.org/statistics/rpfx25.htm
```

---

## 4) Acquisition procedure (spec steps; Codex implements)

### 4.1 Build a country→currency membership table

1. Download **SIX List One** (XLS preferred; XML acceptable). ([SIX][3])
2. Extract rows where:

   * `Alphabetic Code` is present (3-letter ISO 4217),
   * `ENTITY` represents a country/territory that should map to ISO-3166.
3. Map `ENTITY` → `country_iso` using your canonical ISO table `iso3166_canonical_2024` (deterministic name normalization + strict matching).
4. Drop any rows that cannot be mapped to a valid `country_iso` (record them in provenance).

**Deterministic name normalization (MUST)**

* uppercase
* remove diacritics
* replace `&` → `AND`
* strip punctuation (`'`, `.`, `,`, `(`, `)`, `-`)
* collapse whitespace

If collisions occur (two ISO2 candidates match the same normalized entity), fail the build (do not guess).

### 4.2 For each currency κ, determine its currency-area member set

For each ISO-4217 alphabetic code `currency=κ`, define:

* `Members(κ) = { country_iso : country’s ISO 4217 currency code == κ }`

Only currencies with `|Members(κ)| ≥ 1` appear in the output dataset.

### 4.3 Compute `share` for each (κ, country_iso)

For each currency κ:

* If `|Members(κ)| = 1`:

  * that one member gets `share=1.0`

* If `|Members(κ)| > 1`:

  1. Fetch GDP totals for 2024 (`NY.GDP.MKTP.CD`) for each member country.
  2. Define weights:

     * `w(c) = GDP_2024(c)` if present and > 0
     * otherwise `w(c) = w_floor` (a small positive floor; see §8 pinned defaults)
  3. Set:

     * `share(c) = w(c) / Σ_{j∈Members(κ)} w(j)`
  4. Enforce:

     * `abs(Σ share - 1.0) ≤ 1e-6` (renormalize if needed)

### 4.4 Compute `obs_count` (per currency evidence mass)

This is a **pseudo-observation** mass for priors. It must be deterministic and nonnegative.

Recommended approach:

1. Obtain BIS D11.3 currency turnover shares for a pinned survey year (see §8).
2. For each currency κ in your output:

   * assign total evidence `Nκ` proportional to its BIS share
   * currencies not present in BIS get `N_min`
3. Allocate `Nκ` across member countries proportional to `share(c)` using:

   * floor + largest residual fixup
   * tie-break: `country_iso` ascending

Finally, output row-level `obs_count(κ,c)`.

### 4.5 Output writing discipline (determinism)

* Emit rows sorted by `(currency ASC, country_iso ASC)` (writer rule; readers must not assume physical order). 
* Enforce PK uniqueness before write.

---

## 5) Engine-fit validation checklist (MUST pass)

### 5.1 Schema + domains

* `currency` is valid ISO-4217 alpha-3 uppercase
* `country_iso` FK-valid in `iso3166_canonical_2024`
* `share` in [0,1], finite
* `obs_count` integer ≥ 0
* PK unique for `(currency, country_iso)`  

### 5.2 Per-currency group constraints

* `abs(Σ share - 1.0) ≤ 1e-6` per currency 

### 5.3 Coverage sanity (SHOULD)

* Every currency that will appear in `merchant_currency` (if produced) and/or in `settlement_shares_2024Q4` should have a corresponding block here, unless you intentionally treat it as out-of-scope.

---

## 6) Provenance sidecar (MANDATORY)

Store alongside the parquet:

* SIX source URL(s), download timestamp, checksum
* the list publish date (if present in file metadata) ([SIX][3])
* World Bank GDP indicator + year + API URL + checksum ([World Bank Open Data][4])
* BIS table reference + year (if used) ([Bank for International Settlements][5])
* number of entities dropped due to unmapped names + their raw strings
* output parquet checksum

This is what makes it defendable as “sealed reference” rather than a handwave.

---

## 7) Deliverables (what “done” looks like)

1. `reference/network/ccy_country_shares/2024Q4/ccy_country_shares.parquet` 
2. `reference/network/ccy_country_shares/2024Q4/ccy_country_shares.provenance.json` (or yaml)

---

## 8) Temporary PINNED DEFAULTS (move to acquisition config later)

These remove all “choose a constant” ambiguity so Codex can run without asking:

### 8.1 Membership source

* Use SIX **List One (XLS)** as primary; XML as fallback. ([SIX][3])

### 8.2 GDP weighting

* Use World Bank `NY.GDP.MKTP.CD` for **2024** as weights. ([World Bank Open Data][4])
* `w_floor = 1e9` (USD) for missing GDP (prevents zeroing a member).

### 8.3 `obs_count` currency totals

* Use BIS Triennial Survey D11.3 at **TIME_PERIOD=2022** as currency-importance prior. ([Bank for International Settlements][5])
* Set `N_total_ccy = 2,000,000`
* Set `N_min = 5,000`
* For each κ present in BIS: `Nκ = clamp(round(N_total_ccy * sκ), min=N_min, max=250,000)`
* For κ not present in BIS: `Nκ = N_min`

### 8.4 `obs_count` allocation within currency

* Allocate by `share` using:

  * `floor(raw)`
  * distribute residual units by largest residual
  * tie-break residual ties by `country_iso ASC`

### 8.5 Vintage mismatch policy

If SIX List One publish date is not within 2024Q4:

* still write to the contract path `…/2024Q4/…`
* record `is_exact_vintage=false` in provenance with the actual publish date. ([SIX][3])

---

[1]: https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html?utm_source=chatgpt.com "Global Financial Data Standards - SIX"
[2]: https://www.iso.org/iso-4217-currency-codes.html?utm_source=chatgpt.com "ISO 4217 — Currency codes"
[3]: https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xls?utm_source=chatgpt.com "List one: Currency, fund and precious metal codes - SIX"
[4]: https://data.worldbank.org/indicator/NY.GDP.MKTP.CD?utm_source=chatgpt.com "GDP (current US$)"
[5]: https://www.bis.org/statistics/rpfx25.htm?utm_source=chatgpt.com "Triennial Central Bank Survey of foreign exchange and ..."
