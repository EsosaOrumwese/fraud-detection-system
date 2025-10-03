# Generating `nb_dispersion_coefficients.yaml`

Below is a tight, one-person, region-bounded plan: what extra data to hunt, why it matters, and the exact “training tables” to add to your preview so you know what to collect.

---

# What to hunt — NB dispersion (`beta_phi`) (concept preview)

**Picture (one paragraph).**
We want a **region-scoped census of outlet footprints** per **brand × country × MCC**, plus just enough context to attach **channel (CP/CNP)** and **ln(gdp_pc)**. From this, we’ll learn the two S2 heads:

* **NB mean** `beta_mu` with features `[1 | onehot(MCC) | onehot(channel: CP, CNP)]`.
* **NB dispersion** `beta_phi` with features `[1 | onehot(MCC) | onehot(channel: CP, CNP) | ln(gdp_pc_2015USD)]`.

Everything below exists only to supply those covariates and a reliable sample of **domestic outlet counts**.

---

## NB-φ: training-only hunt list (minimal but sufficient)

### H1 — Brand–Country–MCC Outlet Census *(core label source, REQUIRED)*

**Purpose.** Give you the **domestic outlet count** per *(brand, country, MCC)*—this is the raw signal for both NB-mean and NB-dispersion.

**Row.** One per `(brand_id, country_iso, mcc)` in-region.

**Processed fields.**

* `brand_id` (stable; prefer Wikidata QID)
* `brand_name` (normalized; QC only)
* `country_iso` (ISO2, uppercase)
* `mcc : int32` (4-digit; assigned per POI before aggregation)
* `outlet_count_domestic : int32 ≥ 0` — **deduped** store count for this tuple
* `is_multi : int8 ∈ {0,1}` — `1{outlet_count_domestic ≥ 2}`
* `asof_date`
* `source_mask` (e.g., `OSM|STORE_LOCATOR`)

**Likely sources.** OpenStreetMap POIs (ODbL) and selected official store-locator snapshots.

**Dedup rule (painted).**
Within each **(brand_id, country_iso, mcc)** cluster, collapse POIs that either share **identical address**, or lie within **75 m** *and* share tag family (`shop` vs `amenity`) and any of `{opening_hours, phone}` if present—keep first-seen. **Dedup happens before counting.**

**Acceptance (fast).**

* Coverage floor per country: Σ`outlet_count_domestic` over top-20 brands ≥ **100**.
* 0 unmapped MCC; 100% POIs resolve to a country polygon.
* Observed multi-rate weakly ↑ from low to high GDP buckets (sanity only).

**Tiny peek (illustrative).**

| `brand_id`  | `country_iso` | `mcc` | `outlet_count_domestic` | `is_multi` |
|-------------|---------------|-------|------------------------:|-----------:|
| Q-LIDL      | DE            | 5411  |                    1023 |          1 |
| Q-CARREFOUR | FR            | 5411  |                     756 |          1 |
| Q-STARBUCKS | IT            | 5812  |                     178 |          1 |
| Q-ACME_ECOM | GB            | 5732  |                       0 |          0 |

> Note: keep rows with 0/1 as well—they help when you later fit a **zero/one-truncated NB** (you won’t *use* n∈{0,1} as observations, but you’ll need them to compute the truncation mass).

---

### H2 — OSM tag → MCC mapping *(category signal, REQUIRED)*

**Purpose.** Deterministic MCC assignment per POI **before** aggregation, so your counts are truly per-MCC.

**What to hold.**

* The governed ruleset (documentation, not data rows): e.g.,
  • `shop ∈ {"supermarket","convenience"} → mcc=5411`
  • `amenity ∈ {"restaurant"} → mcc=5812`
  • `amenity ∈ {"fuel"} → mcc=5541`

**Brand-level hints (optional).** If you keep a `brand → primary_mcc` hint, treat it as QC only; the **POI-level** mapping drives the counts.

---

### H3 — Brand → Channel labels (CP/CNP) *(channel signal, REQUIRED)*

**Purpose.** Put the **channel** into the design.

**What to collect.**

* `brand_id`
* `channel_token ∈ {"CP","CNP"}` (engine tokens)
* `evidence ∈ {"OSM_POI","ONLINE_ONLY_LIST","MACRO_CALIBRATION"}`

**Where it comes from.**

* **CP** from H1: any presence (`outlet_count_domestic > 0`) ⇒ CP evidence.
* **CNP** coverage via a small **online-only roster** (30–50 brands: marketplaces, fintech, ticketing, SaaS). If a brand has no POIs (absent in H1), create a **zero-count H1 stub** when assembling the training frame—nothing else to hunt.

**Why both.** The roster gives genuine CNP examples; later you can calibrate **one global** CNP offset from a public macro series without adding per-country effects (engine only has one CP/CNP block).

---

### H4 — Country macro (GDP 2015-USD, 2024 vintage) *(macro covariate, REQUIRED)*

**Purpose.** Provide **`gdp_pc_usd_2015`** to compute **`ln(g_c)`** for each `country_iso`.

**What to collect.**

* `country_iso` (ISO2)
* `gdp_pc_usd_2015 : float64` (strictly > 0, **year 2024**)
* Derived later: `ln_g_c = ln(gdp_pc_usd_2015)`

**Likely sources.** Reuse your World Bank GDP table from the runtime pack.

**Painted peek.**

| `country_iso` | `gdp_pc_usd_2015` | `ln_g_c` |
|---------------|------------------:|---------:|
| DE            |             48000 |    10.78 |
| FR            |             43000 |    10.67 |
| IT            |             38000 |    10.54 |
| GB            |             42500 |    10.66 |

---

### H5 — Brand alias map *(ID hygiene, RECOMMENDED)*

**Purpose.** Unify messy brand strings so each brand contributes a single `brand_id`.

**What to collect.**

* `brand_alias` (raw) → `brand_id` (canonical)
* `method` (e.g., normalization rules / wikidata match)

---

### H6 — Online-only brand roster *(channel coverage, RECOMMENDED)*

**Purpose.** Ensure you have genuine **CNP** brands (even if they have 0 outlets).

**What to collect.**

* `brand_id`, `brand_name`, optional `evidence_url`, optional `category_hint`

---

## Optional “more signal” (nice to have; not required)

* **O1 — MCC taxonomy hints**: `mcc → mcc_group` for gentle pooling of ultra-sparse MCCs (pre-fit only; not a runtime input).
* **O2 — Country coverage proxy**: `country_iso, brand_coverage_n` to use as optional weights when aggregating diagnostics.

---

## What you do **not** need for NB-φ

* Transaction logs, sales, or customer activity (we’re modelling outlet counts).
* Per-site attributes or exact geo beyond country attribution (H1 already clips by polygons).
* GDP **buckets** (those are a hurdle feature). Dispersion uses the **continuous** `ln_g_c` only.

---

## Why H1–H4 are sufficient

For each **brand × country × MCC** tuple you’ll assemble the training variables:
`(outlet_count_domestic, mcc, channel_token, ln_g_c)`.
That’s exactly what the dispersion design expects:

* Mean head: $x_\mu = [1 \mid \text{onehot(MCC)} \mid \text{onehot(channel)}]$.
* Dispersion head: $x_\phi = [1 \mid \text{onehot(MCC)} \mid \text{onehot(channel)} \mid \ln g_c]$.

H5/H6 just keep identities and **channel coverage** clean so the fit isn’t noisy.

---

## Copy-paste mini-spec (to slot under “Training-only, NB dispersion”)

* **NB-H1 `brand_country_mcc_outlet_census`**
  `brand_id, brand_name, country_iso, mcc:int, outlet_count_domestic:int, is_multi:int8, asof_date, source_mask`

* **NB-H2 `osm_to_mcc_map` (governed ruleset)**
  documentation of tag→MCC mapping (POI-level), optionally brand→primary_mcc hints for QC

* **NB-H3 `brand_channel_labels`**
  `brand_id, channel_token:{CP,CNP}, evidence:{OSM_POI,ONLINE_ONLY_LIST,MACRO_CALIBRATION}`

* **NB-H4 `country_gdp_pc_2015usd_2024`** *(reuse runtime)*
  `country_iso, gdp_pc_usd_2015:float` → derive `ln_g_c`

* *(Recommended)* **NB-H5 `brand_aliases`**
  `brand_alias, brand_id, method`

* *(Recommended)* **NB-H6 `online_only_brand_roster`**
  `brand_id, brand_name, evidence_url?, category_hint?`

---

# NB dispersion (`beta_phi`) — data preview & training plan (concept, executable)

**Picture (one paragraph).**
We want a **region-scoped census of brand footprints** per **brand × country × MCC**, plus just enough context to attach **channel (CP/CNP)** and **`ln(gdp_pc)`**. From those counts we construct stable **cell moments**, and then fit a simple, regularised model that produces a coefficient vector `beta_phi` in the **exact order S2 expects**:
`[intercept | mcc block (dict order) | CP | CNP | ln_gdp_pc]`.

Everything below exists only to supply those covariates and a reliable sample of **domestic outlet counts**.

---

## 1) From hunted data to three training tables (deterministic)

You’ve already defined what to hunt (brand×country×MCC counts; channel; GDP; optional aliases/roster). We funnel those into **three** small, engine-aligned tables.

### A) `nb_phi.training_rows_all.parquet`  *(brand-level counts; raw “k + covariates”)*

**Source.** Hunted counts (OSM/store locator) ⟂ MCC mapping (POI→MCC) ⟂ Channel labels (CP/CNP) ⟂ GDP join (2024).

**Keep all counts** (`outlet_count_domestic ≥ 0`). We’ll derive dispersion targets from **untruncated** moments; a separate multi-site view is for QC only.

**Columns (exact, minimal).**

- `brand_id : string` — canonical (prefer Wikidata QID)
- `country_iso : string` — ISO2 uppercase
- `mcc : int32` — must be in the engine MCC dictionary
- `channel : string ∈ {"CP","CNP"}` — engine tokens
- `ln_g_c : float64` — `ln(gdp_pc_usd_2015)` for `country_iso` (year 2024), strictly > 0
- `outlet_count_domestic : int32 ≥ 0`

**Dedup before counting (painted).**
For each `(brand_id, country_iso, mcc)`: collapse POIs that either share **identical address**, or lie within **75 m** *and* share tag family (`shop` vs `amenity`) and any of `{opening_hours, phone}` if present → keep first-seen.

**Tiny preview (illustrative).**

| `brand_id` | `country_iso` | `mcc` | `channel` | `ln_g_c` | `outlet_count_domestic` |
|------------|---------------|-------|-----------|----------|------------------------:|
| Q-LIDL     | DE            | 5411  | CP        | 10.78    |                    1023 |
| Q-STARBKS  | IT            | 5812  | CP        | 10.54    |                     178 |
| Q-ACME_EC  | GB            | 5732  | CNP       | 10.66    |                       0 |
| Q-NBRAND   | FR            | 5732  | CP        | 10.67    |                       1 |

> Keep a **QC view** `training_rows_ms` (same schema, filtered to `outlet_count_domestic ≥ 2`) for plots and sanity checks, but don’t use it to compute dispersion targets.

---

### B) `nb_phi.cell_stats.parquet`  *(aggregated moments → stable dispersion targets)*

**Cells.** Partition rows by `(mcc, channel, ln_g_c_bin)` where `ln_g_c_bin` are quantile bins (e.g., 6–10) computed over **training_rows_all** within your region.

**For each cell C** with enough brands (e.g., `n_brands ≥ 8`), compute:

* `k_mean` (mean of counts) and `k_var` (sample variance) using **all counts (≥0)**.
* **Untruncated MoM dispersion**
  $$
  \phi_{\text{mom}} = \max\big(\varepsilon,\ \frac{\bar{k}^{,2}}{\max(\varepsilon,\ s^2 - \bar{k})}\big)
  $$
  If `s² ≤ k_mean`, mark **Poisson-like** → set a large sentinel φ and **down-weight** this cell.
* `weight` default `n_brands` (cap if needed).

*Optional (more faithful).* Instead of MoM, estimate per-cell **truncated NB2 MLE** `phi_mle` using the brand counts (some 0/1, some ≥2). Use `log(phi_mle)` as the target in the regression below; it avoids MoM bias when the run has high `P{0 or 1}`.

**Columns.** `mcc:int32, channel:{"CP","CNP"}, ln_g_c_bin_id:int16, n_brands:int32, k_mean:float64, k_var:float64, phi_mom:float64, weight:float64`.

**Tiny preview.**

| mcc  | channel | ln_g_c_bin_id | n_brands | k_mean | k_var | phi_mom | weight |
|------|---------|---------------|---------:|-------:|------:|--------:|-------:|
| 5411 | CP      | 5             |       42 |    9.6 |  38.7 |    2.59 |     42 |
| 5812 | CP      | 3             |       18 |    3.7 |  11.8 |    1.46 |     18 |
| 5732 | CP      | 4             |       10 |    2.5 |   3.0 |    5.00 |     10 |
| 5942 | CNP     | 5             |        9 |    2.2 |   6.0 |    1.76 |      9 |

---

### C) `nb_phi.regression_design.parquet`  *(fit-ready design for `beta_phi`)*

**Target.** `y = log(phi_mom)` (or `log(phi_mle)` if you used the truncated MLE).

**Features (one row per cell).**
$$
\bar{x}_{\phi,C}=\big[1\ \big|\ \text{one-hot(MCC)}\ \big|\ \text{one-hot(channel: CP, CNP)}\ \big|\ \overline{\ln g_c}\big]
$$  
where tables use `ln_g_c`; in the emitted YAML `feature_order` this appears as **`ln_gdp_pc`**.

**Columns (wide is simplest; order must match engine dictionaries).**

* `intercept : int8` (always 1)
* `mcc__{code} ∈ {0,1}` for each MCC **in dictionary order**
* `channel__CP ∈ {0,1}`, `channel__CNP ∈ {0,1}` (CP first, CNP second)
* `ln_g_c_mean : float64`
* `log_phi_mom : float64`
* `weight : float64`

**Tiny preview (wide form).**

| `intercept` | `mcc__5411` | `mcc__5812` | `mcc__5732` | … | `channel__CP` | `channel__CNP` | `ln_g_c_mean` | `log_phi_mom` | `weight` |
|------------:|------------:|------------:|------------:|---|--------------:|---------------:|--------------:|--------------:|---------:|
|           1 |           1 |           0 |           0 | … |             1 |              0 |         10.90 |         0.952 |       42 |
|           1 |           0 |           1 |           0 | … |             1 |              0 |         10.60 |         0.378 |       18 |
|           1 |           0 |           0 |           1 | … |             1 |              0 |         10.75 |         1.609 |       10 |
|           1 |           0 |           0 |           0 | … |             0 |              1 |         10.88 |         0.567 |        9 |

> This alignment guarantees the fitted vector `beta_phi` is **exactly** in S2 order:
> `[intercept | mcc block (dict order) | CP | CNP | ln_gdp_pc]` → length `1 + C_mcc + 2 + 1`.

---

## 2) Training procedure (compact, reproducible)

**Step 0 — Hygiene.**
Freeze dictionaries you’ll emit with:
`dict.channel = ["CP","CNP"]`, `dict.mcc = [...]` (the MCC list **from the engine’s dictionary** for this run).

**Step 1 — Build training rows.**
Create **A) `training_rows_all`** (`outlet_count_domestic ≥ 0`) joined to MCC/channel/ln_g_c.
(Keep **`training_rows_ms`** = `≥ 2` for QC plots only.)
Optionally winsorize counts within `(mcc,channel)` at the 99th pct **for cell stats only**.

**Step 2 — Aggregate to cells.**
Bin `ln_g_c` (e.g., 6–10 quantile bins). Compute **B) `cell_stats`**: `k_mean`, `k_var`, `phi_mom` (or `phi_mle`), `n_brands`, `weight`. Drop/merge sparse cells (e.g., `n_brands < 8`).

**Step 3 — Build regression design.**
For each cell, build **C) `regression_design`** with one-hot blocks and `ln_g_c_mean`. Target `y = log(phi_)`, weight = `weight`.

**Step 4 — Fit.**
Weighted **ridge regression** (L2) on
`y ~ intercept + MCC + channel + ln_g_c_mean`.
Choose λ by CV (k-fold over cells or leave-one-MCC-out). Robust alternative: weighted Huber regression.

**Record provenance:** persist the chosen ridge **λ**, the **CV scheme** (e.g., K and folds/LOO), and any **random seed** alongside the coefficients for reproducibility.

**Step 5 — QC (binding).**

* **Vector shape & order:** length `1 + C_mcc + 2 + 1`; channel = CP then CNP; all finite.
* **Variance check:** pick a few cells, compute $\hat{\mu}$ (from your NB-mean fit, or use (`k_mean`) as a proxy); confirm
  $\widehat{\mathrm{Var}}(K) = \hat{\mu} + \hat{\mu}^2 / \exp(\beta_\phi^\top x_\phi) \ge \hat{\mu}$.
* **Truncation corridors (engine-alignment):** with fitted $\hat{\mu},\hat{k}$ per cell, compute $P(N\in{0,1}) = p(0)+p(1)$ overall and p99 of attempts; expect overall **≤ 0.06**, p99 **≤ 3**. Fail if breached.
* **Sensitivity sanity:** sign/magnitude of `ln_g_c` plausible for your region; MCC/channel effects not exploding (|β| bounded, e.g., < 10).

**Step 6 — Package** `nb_dispersion_coefficients.yaml` *(engine order & block shape)*

```yaml
semver: "1.0.0"
dicts:
  channel: ["CP","CNP"]
  mcc: [5411, 5812, 5732, 5942, ...]  # exact MCC order used when fitting
dispersion:
  feature_order: [intercept, mcc..., channel.CP, channel.CNP, ln_gdp_pc]
  beta_phi:
    - <intercept>
    - <mcc 5411>
    - <mcc 5812>
    - <mcc 5732>
    - <mcc 5942>
    # ... rest of MCCs in dict order ...
    - <CP>      # channel effect for CP
    - <CNP>     # channel effect for CNP
    - <ln_g_c>  # macro term coefficient (tables' ln_g_c → YAML name ln_gdp_pc)
```

Record λ (ridge) and any CV seeds with the artifact for reproducibility.

---

## 3) Acceptance checklist (printable)

* [ ] **Tables A/B/C exist** and pass column/type checks.
* [ ] **Cell coverage:** ≥ 2–3 `ln_g_c` bins populated for major MCCs; each kept cell `n_brands ≥ 8` (or your chosen floor).
* [ ] **Fit artifacts recorded:** λ, CV scheme, seed; coefficients exported **in engine order**.
* [ ] **YAML shape:** `beta_phi` length = `C_mcc + 4`; block order `[intercept | mcc… | CP | CNP | ln_gdp_pc]`.
* [ ] **Corridor sanity:** overall `P{0 or 1} ≤ 0.06`, p99 attempts ≤ 3.
* [ ] **All finite:** no NaN/Inf; numeric scales sane; spot-checked variance ≥ mean on several cells.

---

## 4) Painted mini walk-through (end-to-end on 3 tuples)

**Raw POIs → dedup & map.**
`Lidl (DE, shop=supermarket, 2 nodes within 50m) → 1 store, mcc=5411`
`Starbucks (IT, amenity=restaurant) → mcc=5812`
`AcmePay (GB, online-only roster) → mcc=5732, count=0 (stubbed)`

**A) training_rows_all (fragment).**

| `brand_id` | `country_iso` | `mcc` | `channel` | `ln_g_c` | `outlet_count_domestic` |
|------------|---------------|-------|-----------|----------|------------------------:|
| Q-LIDL     | DE            | 5411  | CP        | 10.78    |                    1023 |
| Q-STARB    | IT            | 5812  | CP        | 10.54    |                     178 |
| Q-ACMEC    | GB            | 5732  | CNP       | 10.66    |                       0 |

**B) cell_stats (5411,CP,bin=5) →** many brands → `k_mean≈9.6`, `k_var≈38.7` → `phi_mom≈2.59`.

**C) regression_design row →**
`intercept=1, mcc__5411=1, channel__CP=1, ln_g_c_mean≈10.90, log_phi_mom≈0.952, weight=42`.

Fit ridge on all cells → export `beta_phi` in the exact block order.

---

## 5) What we are **not** hunting/using here

* No transaction logs or per-store detail (counts are enough).
* No GDP **buckets** (dispersion uses continuous `ln_g_c` only).
* No per-country channel effects in the engine (we keep **one** CP/CNP block; any macro calibration for CNP happens **once** offline and manifests as the single channel coefficient).

---

