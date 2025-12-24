# Acquisition Guide — `settlement_shares_2024Q4` (Currency→Country settlement share vectors)

## 0) Purpose and role in the engine

`settlement_shares_2024Q4` is an **ingress reference surface** consumed by **1A.S5** to build currency→country weights (and later blend with `ccy_country_shares_2024Q4`). For each **ISO-4217 currency**, it provides a **probability vector over settlement countries**.

Think of it as:

> “If a transaction settles in currency **κ**, what’s the empirical share that the settlement is attributed to country **c**?”

It is **not produced by the engine**. It is a pinned reference artefact in the manifest.

---

## 1) Engine-fit contract (MUST)

### 1.1 Identity

* **Dataset ID:** `settlement_shares_2024Q4`
* **Version:** `2024Q4`
* **Format:** Parquet
* **Path:** `reference/network/settlement_shares/2024Q4/settlement_shares.parquet`
* **Partitioning:** none
* **Licence:** `Proprietary-Internal` (you build/own it; you can still cite public priors in provenance)

### 1.2 Schema (MUST)

Primary key: **(currency, country_iso)**

Columns:

* `currency` : ISO-4217 alpha-3 (uppercase)
* `country_iso` : ISO-3166-1 alpha-2 (uppercase; must exist in `iso3166_canonical_2024`)
* `share` : float in **[0,1]**
* `obs_count` : int64 in **[0,∞)**

Constraint:

* For each `currency`: **Σ share = 1.0 ± 1e-6**

### 1.3 Why `obs_count` matters (don’t fake it thoughtlessly)

1A.S5 uses observed counts to compute an **effective evidence mass** when blending settlement vs prior surfaces. So `obs_count` is not cosmetic; it controls how strongly “observed” vs “prior” dominates.

---

## 2) Quality bar (what makes this “enterprise-grade”)

A “good” `settlement_shares_2024Q4` has:

* **Strict domain hygiene** (ISO codes, FK-valid countries, no placeholders).
* **Stable definitions** (what counts as an “observation”, exact window, exact scope).
* **Reproducible computation** (same raw inputs → same output).
* **Coverage rationale** (which currencies are included and why; gaps are intentional, not accidental).

---

## 3) Acquisition routes (choose the best you can actually support)

### Route A (preferred): Derive from real settlement observations

Use this if you have **any** settlement/clearing event source (even synthetic but “transaction-like”):

**Raw inputs you need (minimum)**

* `event_time` (to filter to 2024Q4)
* `settlement_currency` (ISO-4217)
* `settlement_country_iso` (ISO2; or mappable deterministically to ISO2)
* one row per settlement observation (or a pre-aggregated count)

**Method (spec, not code)**

1. Filter events to **2024-10-01..2024-12-31** (UTC; define your boundary precisely).
2. Group by `(currency, country_iso)` → `obs_count`.
3. For each `currency`: `share = obs_count / Σ obs_count(currency, *)`.
4. Validate group-sums and FK rules; write parquet.

**This is the only route that makes the dataset truly “settlement-realistic”.**

---

### Route B (bootstrap): Build a governed proxy surface (closed-world baseline)

If you have no settlement data (likely at this stage), you can still create a **credible** proxy by anchoring it to **public macro priors** and making every rule explicit.

This route is acceptable because your dictionary already classifies the artefact as **Proprietary-Internal** (it’s something you own), but you must be honest in provenance that it’s a proxy.

---

## 4) Recommended proxy design (deterministic and defensible)

### 4.1 Currency universe (MUST define)

Pick **C**, the set of currencies you will include. Practical choices:

* **C = currencies needed by your merchant universe**, i.e., currencies you expect `merchant_currency` (S5.0) to produce; or
* **C = currencies appearing in your `ccy_country_shares_2024Q4`** (once built).

**Validation:** ensure every `currency` is a real ISO-4217 code (not just `^[A-Z]{3}$`). The ISO 4217 maintenance agency (SIX) publishes “List One” in machine-readable form. ([SIX][1])

### 4.2 Settlement hub prior (SHOULD)

Settlement tends to concentrate in major financial centres. A solid public proxy for “hub-ness” is **FX turnover by country** from the BIS Triennial Survey tables (public, downloadable, API-accessible). ([BIS Data Portal][2])

Define a stable hub set **H** (example: top 10–20 countries by FX turnover share in the latest pre-2024 release you choose).

### 4.3 Country candidates per currency (MUST define)

For each currency κ:

* Define candidate country set **Uκ** (where κ can plausibly “settle”).
* In a clean design, **Uκ should come from your currency→country prior surface** (`ccy_country_shares_2024Q4`), and settlement shares are a “hub-concentrated” reinterpretation of it (so the two surfaces have a meaningful difference).

If you haven’t built `ccy_country_shares_2024Q4` yet, you can temporarily define:

* **Uκ = {currency-issuing country} ∪ H**, plus any additional countries you explicitly choose to include.

### 4.4 Share construction rule (MUST)

For each currency κ, define a deterministic mixture:

* Let **hub_mass(κ)** be a fixed scalar in [0,1] (policy decision, recorded in provenance).
* Let **p_hubκ(c)** be hub weights over c∈(Uκ∩H) (from BIS hub shares, renormalised inside κ’s hub set).
* Let **p_baseκ(c)** be a base distribution over Uκ (e.g., from `ccy_country_shares_2024Q4`, renormalised to Uκ).

Then:

* `shareκ(c) = hub_mass(κ) * p_hubκ(c) + (1 - hub_mass(κ)) * p_baseκ(c)`

Finally enforce:

* Σc shareκ(c) = 1.0 (within tolerance)
* shareκ(c)∈[0,1]

### 4.5 Evidence mass (`obs_count`) rule (MUST)

Pick a deterministic **total evidence per currency** `Nκ`, then set:

* `obs_countκ(c) = round(Nκ * shareκ(c))`, with a deterministic “fixup” so Σ obs_countκ(c) = Nκ exactly.

How to choose `Nκ` without real settlement logs:

* Scale `Nκ` by **currency importance in international payments** (SWIFT-based series published in an official Fed note’s accessible data). ([Federal Reserve][3])
  (This is not “settlement counts”, but it’s a defensible proxy for relative evidence mass by currency.)

---

## 5) Engine-fit validation checklist (MUST pass)

Per row:

* `currency` is valid ISO-4217 (use SIX list)
* `country_iso` ∈ `iso3166_canonical_2024`
* `0 ≤ share ≤ 1`
* `obs_count` integer ≥ 0
* PK uniqueness: no duplicate `(currency, country_iso)`

Per currency:

* `abs(Σ share - 1.0) ≤ 1e-6`
* no NaN/Inf shares
* non-empty country set (at least 1 row per currency)

Cross-dataset sanity (SHOULD):

* Any currency you expect to appear in merchant currency resolution has at least one share vector (or you knowingly rely on the degrade path where only `ccy_country_shares_2024Q4` exists).

---

## 6) Provenance (MANDATORY for this one)

Store a sidecar next to the parquet with:

* definition of an “observation” (and whether it’s proxy or empirical)
* time window (2024Q4)
* currency universe definition
* hub source chosen + date
* `hub_mass(κ)` rule (and any overrides)
* `Nκ` rule
* raw source URLs + timestamps + checksums
* output parquet checksum

This is what prevents the surface from becoming “random realism”.

---

## 7) Working links (copy/paste)

```text
# ISO 4217 authoritative lists (SIX; free)
https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xls
https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml
https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html

# BIS Triennial Survey (FX turnover by country) + BIS developer/help pages
https://data.bis.org/topics/DER/tables-and-dashboards/BIS%2CDER_D11_2%2C1.0
https://data.bis.org/bulkdownload
https://data.bis.org/help/tools
https://www.bis.org/terms_statistics.htm

# SWIFT-based currency importance series (official Fed accessible table)
https://www.federalreserve.gov/econres/notes/feds-notes/the-international-role-of-the-u-s-dollar-2025-edition-accessible-20250718.htm
```
---

[1]: https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html?utm_source=chatgpt.com "Global Financial Data Standards - SIX"
[2]: https://data.bis.org/topics/DER/tables-and-dashboards/BIS%2CDER_D11_2%2C1.0 "Triennial Survey publication table: BIS,DER_D11_2,1.0"
[3]: https://www.federalreserve.gov/econres/notes/feds-notes/the-international-role-of-the-u-s-dollar-2025-edition-accessible-20250718.htm "Federal Reserve Board - The International Role of the U.S. Dollar – 2025 Edition, Accessible Data"

---
