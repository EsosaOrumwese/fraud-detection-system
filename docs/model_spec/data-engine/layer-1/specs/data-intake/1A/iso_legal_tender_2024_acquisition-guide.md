# Acquisition Guide — `iso_legal_tender_2024` (ISO2 → primary legal tender currency)

## 0) Purpose and role in the engine

`iso_legal_tender_2024` is a **small reference lookup**: for each `country_iso` (ISO-3166-1 alpha-2), it provides the **primary legal-tender currency code** (ISO-4217 alpha-3).
In 1A it is **optional**, used only as a **fallback** when you choose to emit `merchant_currency` from `home_country_iso` rather than from a richer ingress currency signal.

This dataset must be **deterministic, auditable, and tiny** (MB-scale).

---

## 1) Engine requirements (MUST)

### 1.1 Identity

* **Dataset ID:** `iso_legal_tender_2024`
* **Version:** `2024`
* **Format:** Parquet
* **Path:** `reference/iso/iso_legal_tender/2024/iso_legal_tender.parquet`

* **Schema anchor:** `schemas.ingress.layer1.yaml#/iso_legal_tender_2024` *(must exist; add if missing)*

### 1.1.1 Contract alignment note (MUST)

This dataset is referenced in the **artefact registry**, but to keep contracts aligned you MUST also:

* add a dataset dictionary entry for `iso_legal_tender_2024` (path + version + schema anchor), and
* add the schema anchor `schemas.ingress.layer1.yaml#/iso_legal_tender_2024` (or an explicit compatibility alias) to `schemas.ingress.layer1.yaml`.

Until those two are aligned, this artefact should be treated as **"optional / not wired"** even if the parquet exists.

### 1.2 Schema (MUST)

Primary key: **`country_iso`**

Columns:

* `country_iso` : ISO-3166-1 alpha-2 uppercase (FK → `iso3166_canonical_2024.country_iso`)
* `currency` : ISO-4217 alpha-3 uppercase (3 letters)
* `currency_numeric` : int16 (optional but recommended)
* `minor_units` : int8 (optional but recommended; if missing in source, allow NULL)
* `source_vintage` : string (e.g., `SIX_List_One_YYYY-MM-DD`)
* `is_exact_vintage` : boolean (provenance flag; see §6.3)

### 1.3 Domain constraints (MUST)

* `country_iso` unique
* `country_iso` FK-valid in `iso3166_canonical_2024`
* `currency` matches `^[A-Z]{3}$`
* If present: `currency_numeric` in `[0..999]`
* If present: `minor_units` in `[0..9]`

---

## 2) Source strategy (authoritative + automatable)

### Primary source (PINNED): ISO-4217 Maintenance Agency “List One” (SIX)

Use **SIX ISO-4217 List One (Current currency & funds code list)** as the authoritative machine-readable input. It is downloadable (XLS, XML) and contains the *entity (country/territory)* and *alphabetic currency code* fields needed to produce the mapping. ([SIX][1])

**Why this fits the engine**

* It’s not a “toy list” and it’s maintained as part of ISO-4217 processes. ([ISO][2])
* It’s small (single file), so no risk of huge downloads.

---

## 3) Working links (copy/paste)

```text
# SIX ISO 4217 List One (XLS)
https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xls

# SIX ISO 4217 List One (XML)
https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml

# SIX data standards page (index + links to lists)
https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html

# ISO overview page (what ISO 4217 is)
https://www.iso.org/iso-4217-currency-codes.html
```

SIX List One is explicitly a “currency, fund and precious metal codes” list and is published by date. ([SIX][1])

---

## 4) Acquisition procedure (spec steps; Codex implements)

### 4.1 Download the upstream list (MUST)

* Download `list-one.xls` (primary) or `list-one.xml` (fallback). ([SIX][1])
* Read and record its published date (the XML has `Pblshd="YYYY-MM-DD"`; the XLS is dated in its metadata/heading). ([SIX][3])

### 4.2 Extract candidate records (MUST)

From List One, extract rows/entries that provide at least:

* entity/country name (e.g., `CtryNm` / “ENTITY”)
* alphabetic code (3-letter code)
* numeric code (if available)
* minor units (if available)

### 4.3 Map entity names → `country_iso` (MUST, deterministic)

You MUST map List One entity names to ISO2 using `iso3166_canonical_2024`.

Deterministic normalization (MUST apply to both sides):

* uppercase
* remove diacritics
* replace `&` with `AND`
* remove punctuation: `, . ' ( ) -`
* collapse whitespace
* remove trailing “(THE)” tokens and standalone “THE” tokens

Then:

* exact match normalized entity ↔ normalized `iso3166_canonical_2024.name`
* if no match: try a **small deterministic alias table** (see §7 pinned defaults)
* if still no match: drop the entity and record it in provenance

If a single entity maps to multiple ISO2 candidates after normalization/aliases: **fail the build** (don’t guess).

### 4.4 Choose the “primary legal tender” per ISO2 (MUST)

For each `country_iso`, there may be multiple candidate ISO-4217 codes associated with the entity list (because List One includes currencies + funds + metals).

Selection rule (MUST):

1. Filter candidates to codes that look like “legal tender currencies” by excluding a pinned non-tender set (funds/units/metals/testing/no-currency). (See §7.)
2. If exactly one remains → select it.
3. If more than one remains → select deterministically by:

   * prefer the candidate with a numeric `minor_units` value in `{0,1,2,3}` (common tender minor units)
   * then tie-break by `currency` alphabetic ascending
4. If none remain → drop the country and record in provenance.

### 4.5 Write the parquet (MUST)

Write:

* `reference/iso/iso_legal_tender/2024/iso_legal_tender.parquet`
* rows sorted by `country_iso ASC`

---

## 5) Engine-fit validation checklist (MUST pass)

* `country_iso` unique
* every `country_iso` is in `iso3166_canonical_2024`
* `currency` matches `^[A-Z]{3}$`
* no NULLs in (`country_iso`, `currency`)
* (optional columns) numeric types parse cleanly
* the output is stable for the same List One input + same ruleset

Coverage sanity (SHOULD):

* For any country you expect to appear in `transaction_schema_merchant_ids.home_country_iso`, there is a row here **if** you plan to use this as your `merchant_currency` fallback.

---

## 6) Provenance sidecar (MANDATORY)

Write `reference/iso/iso_legal_tender/2024/iso_legal_tender.provenance.json` containing:

* source URLs used (XLS/XML) ([SIX][1])
* `downloaded_at_utc`
* `published_date` from List One (if available) ([SIX][3])
* `raw_sha256`, `output_sha256`
* list of dropped/unmapped entities (raw strings)
* list of countries dropped due to “no tender currency candidate”
* `is_exact_vintage` (see below)

### 6.3 Vintage honesty rule (PINNED)

Because List One is updated over time, `version=2024` may not match the publish date you download today.
Rule:

* always write to the contract path `.../2024/...`
* set `is_exact_vintage=false` if the List One publish date is not in 2024, and record the actual publish date in provenance.

---

## 7) Temporary PINNED DEFAULTS (move to acquisition config later)

### 7.1 Primary source

* Use SIX `list-one.xls` primarily; fallback to `list-one.xml`. ([SIX][1])

### 7.2 Excluded non-tender codes (PINNED)

Exclude these from “legal tender” selection:

* **No currency / testing / units / SDR / bond units / metals**:

  * `XXX`, `XTS`, `XDR`,
  * `XAU`, `XAG`, `XPT`, `XPD`,
  * `XBA`, `XBB`, `XBC`, `XBD`,
  * `XSU`, `XUA`, `XFU`,
  * plus common fund/special codes often associated with countries:
    `BOV`, `CHE`, `CHW`, `CLF`, `COU`, `MXV`, `USN`, `UYI`.

*(These are kept as a pinned list so Codex does not “invent” what to exclude.)*

### 7.3 Minimal alias table (PINNED starter)

Apply these aliases **before** matching to `iso3166_canonical_2024.name`:

* remove “(THE)” and standalone “THE”
* normalize:

  * `BOLIVIA PLURINATIONAL STATE OF` → `BOLIVIA`
  * `IRAN ISLAMIC REPUBLIC OF` → `IRAN`
  * `KOREA REPUBLIC OF` → `KOREA SOUTH`
  * `KOREA DEMOCRATIC PEOPLE S REPUBLIC OF` → `KOREA NORTH`
  * `RUSSIAN FEDERATION` → `RUSSIA`
  * `TANZANIA UNITED REPUBLIC OF` → `TANZANIA`
  * `VENEZUELA BOLIVARIAN REPUBLIC OF` → `VENEZUELA`
  * `VIET NAM` → `VIETNAM`
  * `UNITED STATES OF AMERICA` → `UNITED STATES`
  * `UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND` → `UNITED KINGDOM`

If you later see unmapped entities in provenance, you extend this alias list deterministically.

---

## 8) Deliverables

1. `reference/iso/iso_legal_tender/2024/iso_legal_tender.parquet`
2. `reference/iso/iso_legal_tender/2024/iso_legal_tender.provenance.json`

---

If you want the cleanest build pipeline: **reuse the same downloaded SIX List One file** for both `ccy_country_shares_2024Q4` and `iso_legal_tender_2024`, so Codex only pulls ISO-4217 once.

[1]: https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xls "List one: Currency, fund and precious metal codes - SIX"
[2]: https://www.iso.org/iso-4217-currency-codes.html "ISO 4217 - Currency codes"
[3]: https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml "List One (XML) - SIX"
