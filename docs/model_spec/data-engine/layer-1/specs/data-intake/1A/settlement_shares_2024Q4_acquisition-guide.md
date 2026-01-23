# Acquisition Guide — `settlement_shares_2024Q4` (Currency→Country settlement share vectors)

## 0) Purpose and role in the engine

`settlement_shares_2024Q4` is an **ingress reference surface** consumed by **1A.S5** to build currency→country weights (and blend with `ccy_country_shares_2024Q4`). For each **ISO-4217 currency**, it provides a **probability vector over settlement countries**.

Think of it as:

> “If a transaction settles in currency **κ**, what’s the empirical share that the settlement is attributed to country **c**?”

It is **not produced by the engine**. It is a pinned reference artefact in the manifest.

**Important dependency note (Proxy Route B):** the governed proxy route is **explicitly anchored to** `ccy_country_shares_2024Q4`. This removes “invented” country candidates and makes the surface fully deterministic.

---

## 1) Engine-fit contract (MUST)

### 1.1 Identity

* **Dataset ID:** `settlement_shares_2024Q4`
* **Version:** `2024Q4`
* **Format:** Parquet
* **Path:** `reference/network/settlement_shares/2024Q4/settlement_shares.parquet`
* **Schema anchor:** `schemas.ingress.layer1.yaml#/settlement_shares`
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

## 3) Acquisition routes (decision-free)

### 3.0 Routing policy (MUST; decision-free)

* If a real settlement/clearing event source is explicitly provided **and** passes schema checks, use Route A.
* Otherwise, use Route B (proxy) and record `is_proxy=true` in provenance.
* Fail closed only if Route B inputs (BIS + `ccy_country_shares_2024Q4`) are unavailable.

### Route A (preferred): Derive from real settlement observations

Use this if you have **any** settlement/clearing event source (even synthetic but “transaction-like”).

**Raw inputs you need (minimum)**

* `event_time` (to filter to 2024Q4)
* `settlement_currency` (ISO-4217)
* `settlement_country_iso` (ISO2; or mappable deterministically to ISO2)
* one row per settlement observation (or a pre-aggregated count)

**Method (spec, not code)**

1. Filter events to **2024-10-01..2024-12-31** (UTC; define boundaries precisely).
2. Group by `(currency, country_iso)` → `obs_count`.
3. For each `currency`: `share = obs_count / Σ obs_count(currency, *)`.
4. Validate group-sums and FK rules; write parquet.

**This is the only route that makes the dataset truly “settlement-realistic”.**

---

### Route B (bootstrap / closed-world baseline): Governed proxy anchored to `ccy_country_shares_2024Q4`

If you have no settlement data (likely at this stage), you can create a **credible** proxy by anchoring it to:

* the **currency-area prior** (`ccy_country_shares_2024Q4`) for per-currency country membership and base weights, and
* a **macro hub prior** (BIS Triennial) for settlement concentration.

This route is acceptable because the artefact is **Proprietary-Internal**, but you must be explicit in provenance that it’s a proxy.

---

## 4) Proxy design (Route B) — deterministic and dependency-anchored

### 4.0 Prerequisites (MUST)

Route B requires these upstream artefacts to exist:

* `ccy_country_shares_2024Q4`
* `iso3166_canonical_2024`
* ISO-4217 List One (SIX) (for currency validation)

### 4.1 Currency universe (PINNED)

Define the currency set **C** as:

* **C = { κ : κ appears in `ccy_country_shares_2024Q4.currency` }**

This makes Route B currency coverage fully determined by the currency-area prior surface.

### 4.2 Settlement hub prior (PINNED)

Use **BIS Triennial Survey** “FX turnover by country” as the hubness proxy.

Define the hub set:

* **H = top 20 countries by BIS D11.2 value at TIME_PERIOD=2022**, after mapping BIS country labels to ISO2.

Define hub weights:

* Let `p_hub(c)` be the BIS value normalized over `c ∈ H`.

### 4.3 Country candidates per currency (PINNED)

For each currency κ:

* Define **Uκ = { country_iso : (κ, country_iso) ∈ ccy_country_shares_2024Q4 }**

No fallback like “issuing country ∪ H” is permitted in Route B. If you want that behaviour, it must be introduced later as an explicit policy extension (not an implicit fallback).

### 4.4 Share construction (PINNED)

For each currency κ:

* Let `p_baseκ(c)` be the normalized base distribution from `ccy_country_shares_2024Q4` restricted to Uκ.
* Let `p_hubκ(c)` be `p_hub(c)` restricted to `(Uκ ∩ H)` and renormalized over that set.

Define hub mass:

* Default: `hub_mass(κ) = 0.70`
* Override: if `max_c p_baseκ(c) ≥ 0.90`, set `hub_mass(κ) = 0.40`

If `(Uκ ∩ H)` is empty:

* set `shareκ(c) = p_baseκ(c)` (i.e., ignore the hub term for that κ).

Otherwise compute:

* `shareκ(c) = hub_mass(κ) * p_hubκ(c) + (1 - hub_mass(κ)) * p_baseκ(c)`

Finally enforce:

* `shareκ(c) ∈ [0,1]`
* `abs(Σc∈Uκ shareκ(c) - 1.0) ≤ 1e-6` (renormalize within κ if needed)

### 4.5 Evidence mass (`obs_count`) totals per currency (PINNED)

Use BIS Triennial Survey **D11.3 “FX turnover by currency”** at `TIME_PERIOD=2022` as the currency-importance prior.

Define totals:

* `N_total = 10,000,000`
* For currencies κ in BIS D11.3, let `sκ` be the normalized BIS share over supported κ.
* Set: `Nκ = clamp(round(N_total * sκ), min=25,000, max=2,000,000)`
* For κ not present in BIS (rare after intersection), set `Nκ = 25,000`.

### 4.6 Allocate `obs_count` within each currency (PINNED)

For each κ:

* `raw(c) = Nκ * shareκ(c)`
* `obs_count(c) = floor(raw(c))`
* Let `R = Nκ - Σ floor(raw(c))`
* Distribute `R` remaining units by **largest residual** `raw(c) - floor(raw(c))`
* Tie-break residual ties by `country_iso` ascending

---

## 5) Engine-fit validation checklist (MUST pass)

### 5.1 Per-row

* `currency` is valid ISO-4217 (use SIX list)
* `country_iso` ∈ `iso3166_canonical_2024`
* `0 ≤ share ≤ 1` and finite
* `obs_count` integer ≥ 0
* PK uniqueness: no duplicate `(currency, country_iso)`

### 5.2 Per-currency

* `abs(Σ share - 1.0) ≤ 1e-6`
* non-empty country set (at least 1 row per currency)

### 5.3 Cross-dataset sanity (Route B MUST)

* Every `currency` in `settlement_shares_2024Q4` must exist in `ccy_country_shares_2024Q4`.
* For each κ, the set of `(κ, country_iso)` in settlement output must be a subset of Uκ as defined from `ccy_country_shares_2024Q4`.

---

## 6) Provenance (MANDATORY for this one)

Store a sidecar next to the parquet with:

* route used (`A` empirical / `B` proxy)
* time window (2024Q4)
* currency universe definition (and resulting currency count)
* **input dependency digests**:

  * digest/checksum of the exact `ccy_country_shares_2024Q4` used
* hub source identifier (BIS D11.2) + `TIME_PERIOD=2022`
* currency-importance source identifier (BIS D11.3) + `TIME_PERIOD=2022`
* hub policy (`hub_top_n`, `hub_mass` rules)
* evidence policy (`N_total`, clamp bounds, rounding/fixup rule)
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

# BIS Triennial Survey (FX turnover by country/currency)
# D11.2 (by country)
https://data.bis.org/topics/DER/tables-and-dashboards/BIS%2CDER_D11_2%2C1.0
# D11.3 (by currency)
https://data.bis.org/topics/DER/tables-and-dashboards/BIS%2CDER_D11_3%2C1.0

# BIS bulk download + help
https://data.bis.org/bulkdownload
https://data.bis.org/help/tools
https://www.bis.org/terms_statistics.htm
```

---

## Placeholder resolution (MUST)

- Replace source URLs/vintage with the exact data release and extraction date.
- Record the final parquet path and sha256 digest after ingest.
- Replace any example coverage stats with the actual coverage/obs_count summary.

