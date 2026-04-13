# `iso3166_canonical_2024` S0 first read

## Question

What exactly is the sealed ISO country authority available to Segment 1A at `S0`, and what does it tell us about the merchant-universe country spine we have already been analysing?

## Why this matters

`iso3166_canonical_2024` is not just a lookup table. At `1A.S0` it is the canonical `country_iso` authority used to:

- validate country ISO values in the merchant universe and other upstream artefacts
- provide a deterministic country sort/tie-break spine
- anchor joins across GDP, settlement shares, currency-country shares, and merchant home countries

So before moving deeper into governed artefacts, we need to understand what this ISO surface actually contains and what it does **not** contain.

## Authoritative sources checked

- acquisition guide: `docs/model_spec/data-engine/layer-1/specs/data-intake/1A/iso3166_canonical_2024_acquisition-guide.md`
- sealed canonical artefact: `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`
- sealed deprecated companion: `reference/iso/iso3166_canonical/2024-12-31/deprecated_iso3166.parquet`
- merchant universe already under investigation: `reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet`

## What the spec says this surface is

The acquisition guide is explicit:

- this is the engine’s **frozen canonical country code authority** for ISO-3166-1 alpha-2
- its target path is `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`
- required columns are:
  - `country_iso`
  - `alpha3`
  - `numeric_code`
  - `name`
- optional columns may be null:
  - `region`
  - `subregion`
  - `start_date`
  - `end_date`
- every `country_iso` appearing in:
  - `transaction_schema_merchant_ids.home_country_iso`
  - `world_bank_gdp_per_capita_20250415.country_iso`
  - `settlement_shares_2024Q4.country_iso`
  - `ccy_country_shares_2024Q4.country_iso`
  must be present in this canonical set

So the contract tells us to treat this artefact primarily as a **validation and join spine**, not as a rich geography product.

## What is actually in the sealed artefact

The canonical parquet contains:

- `251` rows
- `251` unique `country_iso`
- no duplicate `country_iso`
- no duplicate `alpha3`
- no duplicate `numeric_code`

The schema is:

- `country_iso`
- `alpha3`
- `numeric_code`
- `name`
- `region`
- `subregion`
- `start_date`
- `end_date`

## Important first-read finding

Although `region`, `subregion`, `start_date`, and `end_date` exist structurally, in the sealed canonical parquet they are currently **all null**:

- `region` null rows: `251 / 251`
- `subregion` null rows: `251 / 251`
- `start_date` null rows: `251 / 251`
- `end_date` null rows: `251 / 251`

That means the surface is functioning as a **minimal ISO authority spine**, not as a rich regional classification table.

This matters because:

- we can trust it for ISO membership, alpha-3 mapping, numeric-code mapping, and deterministic sorting
- we should **not** assume it provides meaningful region/subregion semantics in the current sealed form

## Deprecated companion and what it means

The deprecated companion parquet contains:

- `271` rows
- `271` unique `country_iso`

Compared with the canonical set:

- canonical-only rows: `2`
- deprecated-only rows: `22`

Examples of deprecated-only / non-canonical codes:

- `EU`
- `OE`
- `XC`
- `XE`
- `XF`
- `XG`
- `XH`
- `XI`
- `XJ`
- `XK`
- `XL`
- `XO`
- `XP`
- `XQ`
- `XU`
- `ZF`
- `ZG`
- `ZH`
- `ZI`
- `ZJ`
- `ZQ`
- `ZT`

So the deprecated companion is where non-canonical or retired spillover codes live; the current engine authority is the `251`-row canonical file.

## What this means for the merchant universe

The merchant universe uses:

- `190` distinct `home_country_iso` values

Coverage result:

- merchant countries missing from canonical: `0`
- merchant countries present only in deprecated but not canonical: `0`

So the merchant-universe country spine is fully covered by the sealed canonical authority.

This is a useful closure point because it means:

- the merchant-country concentration we observed is **not** being driven by invalid or fallback country codes
- top countries like `MC`, `BM`, `LU`, `IE`, `GH`, `CH`, `NO`, `SG`, `AU`, and `US` all sit cleanly inside the canonical ISO authority

## Direct interpretation

`iso3166_canonical_2024` is doing exactly what the engine needs it to do at `S0`: it is a frozen, deterministic country-code spine that cleanly covers the merchant universe and other upstream join surfaces.

But it is also narrower than its schema might suggest:

- it is **strong** as a membership and deterministic-order authority
- it is **weak** as a geography-enrichment source in its current sealed form because the optional regional/time columns are unpopulated

So in this investigation, we should treat it as:

- authoritative for `country_iso` validity
- authoritative for alpha-3 and numeric-code mapping
- authoritative for stable country ordering
- **not** authoritative for region/subregion interpretation

## What this suggests next

The next useful governed-artefact checks after this are:

1. `world_bank_gdp_per_capita_20250415`
   - because the merchant-allocation law clearly leans on GDP shape
2. `gdp_bucket_map_2024`
   - because it explains how the macro-economic surface is discretised into the allocation policy

Those are the artefacts most likely to explain the rich-country cluster in the merchant universe without yet leaving the external/governed-input lane.
