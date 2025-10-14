> A conceptual preview of the input datasets required for the start of the engine at subsegment 1A of layer 1 in state-0 (and through to S9)

## Preview intent (non-binding, blueprint)
This document is a **preview/blueprint** for hunting & wrangling. It mirrors what the engine expects at ingestion, but it is **not** a contract or schema. Examples (e.g., categories like “GROCERY”, specific ISO sets) are **illustrative**, not prescriptive.

### Machine-use guidance
- Do **not** constrain discovery to example tokens; treat examples as **representative**, not exhaustive (e.g., don’t search only for MCC 5411—use the *class* of relevant MCCs for your run/region).
- Respect authority boundaries: **S0** owns **eligibility** (`crossborder_hyperparams.yaml`); **S3** produces **admission metadata & the only inter-country order** (`candidate_rank`).
- Region scope is controlled via policy (e.g., R-EEA12) rather than hard-coding in datasets; switching scope means editing policy files, not schemas.

## Scope & governance (read me first)
This pack previews **14 datasets** plus **4 governance inputs** (G1–G4) and **3 optional policy surfaces** (O1–O3).
S0 **must** open and seal **G1 numeric_policy** and **G2 math_profile** before S0.2; **G3** (S6) is required only if the S6 lane is enabled; **G4** (S7 bounds) is optional. O1–O3 are optional S3/S5 policies captured here for hunt precision.
**Path style.** Policy artefacts live under `config/`. Both flat names (e.g., `config/policy.s6.selection.yaml`) and subfolders (e.g., `config/policy/s3.base_weight.yaml`) are acceptable—the **Dictionary/Registry path** is authoritative.
1) `reference/governance/numeric_policy/{version}/numeric_policy.json`
2) `reference/governance/math_profile/{version}/math_profile_manifest.json`
Opening these, along with the **dataset dictionary** and **artefact registry** anchors, contributes to the `manifest_fingerprint`. No RNG events are permitted until S0.8 attests this surface.
**Notation.** 𝓟 = the governed **parameter set** for a run (policy/config artefacts whose **bytes** feed `parameter_hash` and must be sealed in S0.2).

## Scale & Coverage (magnitude) — macros & gates
To make capacity planning explicit while data is still being sourced, define the following macros. These are **non-binding defaults** until written to the run manifest and/or `numeric_policy.json`; once recorded there, they become binding gates for S0.

**Macro definitions (resolved at run-time):**
* `RUN_ISO := distinct(country_iso)` from Dataset #2 (intersected with the policy-selected scope)
* `N_ISO := |RUN_ISO|`
* `N_CCY := |distinct(currency)| in Datasets #9/#10 (per policy scope)`
* `N_MCC := |distinct(mcc)| in Dataset #1`
* `K_BUCKETS := |distinct(bucket_id)| in Dataset #4`
* `N_TZID := |distinct(tzid)| in Dataset #12a`
* `N_POLY_TZ := row_count(Dataset #12a)`; `N_POLY_ISO := row_count(Dataset #11)`

**Numeric policy hooks** (add under `magnitude` in `numeric_policy.json`; snippet in Appendix):
* `merchants_min`, `merchants_max`, `min_merchants_per_iso`, `min_mccs_per_iso`
* `iso_min_count`, `iso_max_count`
* `gdp.required_year`, `gdp.min_years`, `gdp.k_buckets`, `gdp.min_countries_per_bucket`
* `shares.min_obs_per_pair`, `shares.min_iso_per_currency`, `shares.min_mass_per_country`
* `geom.max_vertices_per_polygon`, `geom.max_rings_per_polygon`, `geom.max_world_countries_rows`,
  `tz.min_tzid`, `tz.max_tzid`, `tz.max_polygons`
* `raster.max_bytes`, `raster.require_overviews`

*Validation rule:* each dataset’s **Magnitude** section below adds *hard gates* that S0 must check **before** S0.8. If a hook is `TBD`, compute & record the observed value in the manifest (warning), then flip to hard-fail once the policy value is set.


# Dataset 1 — `transaction_schema_merchant_ids`  [Internal Dataset]

**What it is (purpose).** The **authoritative merchant seed** for 1A. It’s a *normalized* snapshot (not a raw dump) with just the four fields S0 needs to freeze the universe and build features. 

**Where it lives (path & partitions).**
`reference/layer1/transaction_schema_merchant_ids/{version}/` — single partition key `version` in the path (not a column).

**Schema authority (must match).**
`schemas.ingress.layer1.yaml#/merchant_ids` — JSON-Schema is the **only** authority for 1A.

**Columns & types (exact).** 

* `merchant_id : int64` (≥ 1) — PK
* `mcc : int32` (0..9999)
* `channel : string` ∈ {`"card_present"`, `"card_not_present"`}
* `home_country_iso : ISO2` (uppercase) — **FK →** `iso3166_canonical_2024.country_iso` (Dataset #2)

**How S0 uses it.** Validates schema, **maps** `channel` to internal `{CP,CNP}` symbols, and derives `merchant_u64` for RNG substreams; enforces FK to the ISO table **here**, not later. 

---

## Example rows (engine-usable)

| merchant_id |  mcc | channel          | home_country_iso |
|------------:|-----:|------------------|------------------|
|      100001 | 5411 | card_present     | GB               |
|      100002 | 5732 | card_not_present | DE               |
|      100003 | 5812 | card_present     | US               |
|      100004 | 5942 | card_not_present | FR               |
|      100005 | 4111 | card_present     | NG               |
|      100006 | 5311 | card_not_present | ZA               |
|      100007 | 6011 | card_present     | IN               |
|      100008 | 4112 | card_not_present | BR               |

*(That’s exactly the shape S0 will read; the `version` lives in the folder name, not in the rows.)* 

---

## Acceptance checklist (what must be true before S0 runs)

* **Schema pass** against `#/merchant_ids`; **no extra columns**. 
* **PK uniqueness:** no duplicate `merchant_id`. 
* **Domain checks:** `mcc ∈ [0,9999]`; `channel ∈ {"card_present","card_not_present"}`; `home_country_iso` matches `^[A-Z]{2}$`. 
* **Foreign key:** every `home_country_iso` exists in `iso3166_canonical_2024`. 
* **Authority hygiene:** dictionary/registry entries for this dataset point to the JSON-Schema anchor (no `.avsc`). 

**Common pitfalls to avoid**

* Lower-case or mixed-case ISO codes (must be uppercase). 
* Any channel values beyond the **two allowed** strings (S0 will hard-fail). 
* Sneaking a `version` column into the table (it’s a **path** partition). 

### Magnitude (Scale & Coverage)
- **Expected rows (`N_MERCHANTS`)**: `merchants_min ≤ N_MERCHANTS ≤ merchants_max` (policy).
- **Coverage by ISO**: for every `iso ∈ RUN_ISO`, `count(merchant_id where home_country_iso=iso) ≥ min_merchants_per_iso` (≥1 recommended).
- **MCC breadth**: for every `iso ∈ RUN_ISO`, `|distinct(mcc)| ≥ min_mccs_per_iso`.
- **Channel presence (global)**: both `"card_present"` and `"card_not_present"` must appear (per-ISO recommended, not hard-fail).
- **Sanity**: `N_MCC = |distinct(mcc)|` and `N_MCC ∈ [1, 10_000]`; `channel ∈ {CP,CNP}` by map.
- **Capacity note**: loaders must stream ≥10^6 rows without materialising all columns.

---

# Dataset 2 — `iso3166_canonical_2024`  [External Dataset]

**What it is (purpose).** The **canonical ISO-3166-1 country list** the engine uses for FK checks, deterministic tie-breaks, and as the join target for many other inputs/outputs. It’s pinned to the **2024-12-31** vintage and treated as immutable for the run. 

**Where it lives (path & partitions).**
`reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet` — **no** path partitions. 

**Schema authority (must match).**
`schemas.ingress.layer1.yaml#/iso3166_canonical_2024` — JSON-Schema is the **only** authority.

**Columns & types (exact).** 

* `country_iso : ISO2` (uppercase, PK)
* `alpha3 : ISO3` (uppercase)
* `numeric_code : int16`
* `name : string` (short English name)
* `region : string` (optional, UN M49)
* `subregion : string` (optional, UN M49)
* `start_date : date` (optional; effective-from)
* `end_date : date` (optional; effective-to)
  **Constraints:** unique on `("alpha3","numeric_code")`. 

**How S0 uses it.** S0.1 enforces FK from `merchant_ids.home_country_iso → iso3166_canonical_2024.country_iso`, and records this table as the single source of truth for countries used throughout 1A. Many other 1A schemas **FK to this** (GDP, bucket map, world_countries, egress).

---

## Example rows (engine-usable)

| country_iso | alpha3 | numeric_code | name           | region   | subregion        | start_date | end_date |
|-------------|--------|-------------:|----------------|----------|------------------|------------|----------|
| GB          | GBR    |          826 | United Kingdom | Europe   | Northern Europe  |            |          |
| DE          | DEU    |          276 | Germany        | Europe   | Western Europe   |            |          |
| US          | USA    |          840 | United States  | Americas | Northern America |            |          |
| FR          | FRA    |          250 | France         | Europe   | Western Europe   |            |          |
| NG          | NGA    |          566 | Nigeria        | Africa   | Western Africa   |            |          |
| ZA          | ZAF    |          710 | South Africa   | Africa   | Southern Africa  |            |          |
| IN          | IND    |          356 | India          | Asia     | Southern Asia    |            |          |
| BR          | BRA    |           76 | Brazil         | Americas | South America    |            |          |

*(Empty cells under dates mean `null`, which is allowed by the schema.)* 

---

## Acceptance checklist (before S0 runs this)

* **Schema pass** against `#/iso3166_canonical_2024`. 
* **PK uniqueness:** all `country_iso` are unique and match `^[A-Z]{2}$`. 
* **Cross-uniqueness:** `(alpha3,numeric_code)` pairs are unique. 
* **Optional fields ok:** `region/subregion/start_date/end_date` may be null; if present, types/format must match. 
* **Authority hygiene:** data dictionary/registry entries point to this **JSON-Schema** anchor (no `.avsc`).

**Common pitfalls to avoid**

* Lowercase or mixed-case codes (must be uppercase by regex). 
* Missing ISO rows that other tables FK to (e.g., GDP, bucket map, world_countries, egress).
* Duplicates in `(alpha3,numeric_code)` — validator will hard-fail. 

### Magnitude (Scale & Coverage)
- **Expected rows (`N_ISO`)**: `iso_min_count ≤ N_ISO ≤ iso_max_count` (policy). This table is pinned to 2024-12-31 for the run.
- **Linkage**: `RUN_ISO` is derived from this; all FK’ing datasets must cover *every* ISO in `RUN_ISO`.

---

# Dataset 3 — `world_bank_gdp_per_capita_20250415`  [External Dataset]

**What it is (purpose).** Flattened **GDP per capita (constant 2015 USD)** by ISO2 and year. S0 uses this to look up **`g_c` at observation_year = 2024**; S0 never recomputes anything from it. 

**Where it lives (path & partitions).**
`reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet` — **no path partitions**. 

**Schema authority (must match).**
Use the JSON-Schema anchor **`schemas.ingress.layer1.yaml#/world_bank_gdp_per_capita`** (the dictionary may point to the alias `#/world_bank_gdp`, which is explicitly mapped to the same anchor). **JSON-Schema is the only authority.**

**Columns & types (exact).** 

* `country_iso : ISO2` (uppercase; **FK →** `iso3166_canonical_2024.country_iso`)
* `observation_year : int16` (1950..2100)
* `gdp_pc_usd_2015 : float64` (**> 0**)
* `source_series : string` (const `"NY.GDP.PCAP.KD"`)

**Constraints.** `UNIQUE(country_iso, observation_year)` and `NOT NULL(gdp_pc_usd_2015)`. 

**How S0 uses it.** In **S0.4**, for each merchant’s `home_country_iso = c`, the engine looks up **`g_c = GDPpc[c, 2024]`** (constant 2015 USD). This is a pure lookup; no thresholds are computed here. The same GDP vintage underpins the precomputed **`gdp_bucket_map_2024`**. 

---

## Example rows (engine-usable, 2025-04-15 vintage; we’ll use year 2024 at runtime)

| country_iso | observation_year | gdp_pc_usd_2015 | source_series  |
|-------------|-----------------:|----------------:|----------------|
| GB          |             2024 |        46843.21 | NY.GDP.PCAP.KD |
| DE          |             2024 |        47601.35 | NY.GDP.PCAP.KD |
| US          |             2024 |        63450.72 | NY.GDP.PCAP.KD |
| FR          |             2024 |        43310.55 | NY.GDP.PCAP.KD |
| NG          |             2024 |         2650.10 | NY.GDP.PCAP.KD |
| ZA          |             2024 |         5705.90 | NY.GDP.PCAP.KD |
| IN          |             2024 |         2250.40 | NY.GDP.PCAP.KD |
| BR          |             2024 |         9450.60 | NY.GDP.PCAP.KD |

*(These are plausible values for illustration. The engine only requires the shape/types and the presence of **2024** rows; real numbers will come from the pinned extract.)* 

---

## Acceptance checklist (before S0 runs)

* **Schema pass** against `#/world_bank_gdp_per_capita` (or its alias `#/world_bank_gdp`).
* **PK uniqueness:** no duplicate `(country_iso, observation_year)`. 
* **Domain checks:** `gdp_pc_usd_2015 > 0`; `country_iso` matches `^[A-Z]{2}$`. 
* **Foreign key:** every `country_iso` exists in `iso3166_canonical_2024`. 
* **Coverage for runtime:** **all `home_country_iso` in the merchant seed have a `2024` row** present. (S0 aborts if any is missing.) 
* **Authority hygiene:** dictionary/registry `schema_ref` uses the **JSON-Schema** (not Avro); aliasing is OK but must resolve to the canonical anchor.

**Where it’s consumed downstream:** The hurdle **design matrix** depends on this GDP vintage (via the bucket map) and is explicitly wired in the artefact registry (`hurdle_design_matrix` depends on `world_bank_gdp_per_capita_20250415`). 

### Magnitude (Scale & Coverage)
- **Lower bound**: `row_count ≥ N_ISO · gdp.min_years` measured over `[gdp.required_year − (gdp.min_years − 1) .. gdp.required_year]`.
- **Required year coverage**: for every `iso ∈ RUN_ISO`, ≥1 row where `observation_year == gdp.required_year`.
- **Bucket linkage**: every `country_iso` in Dataset #4 must have that `source_year` present here.
- **Sanity cap**: reject if `row_count > N_ISO · 200` (unexpected depth).

---

# Dataset 4 — `gdp_bucket_map_2024`  [Internal Dataset]

**What it is (purpose).** A **precomputed**, deterministic **country → GDP bucket** map used only as categorical predictors for the hurdle model. It’s built offline from the **same GDP vintage** (obs-year **2024**, const-2015 USD) and is **never recomputed at runtime**. 

**Where it lives (path & partitions).**
`reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet` — no path partitions. (Dictionary points here.) 

**Schema authority (must match).**
Use **`schemas.ingress.layer1.yaml#/gdp_bucket_map_2024`**. (Alias **`#/gdp_bucket_map`** is provided for compatibility and resolves to the same anchor.) **JSON-Schema is the only authority.**

**Columns & types (exact).** 

* `country_iso : ISO2` (uppercase; **FK →** `iso3166_canonical_2024.country_iso`)
* `bucket_id : int32` (**1..5**)
* `bucket_label : string` (nullable; e.g., “Very Low/Low/…”)
* `method : string` (**const `"jenks"`**)
* `k : int8` (**const `5`**)
* `source_year : int16` (**must be `2024`** to match the GDP lookup)

**How S0 uses it.** In **S0.4**, for each merchant’s `home_country_iso=c`, the engine does pure lookups: **`b_m ← B(c) ∈ {1..5}`**; this bucket enters **only** the hurdle design (five dummies in fixed order `[1..5]`). No thresholds are computed at runtime.

---

## Example rows (engine-usable)

| country_iso | bucket_id | bucket_label | method | k | source_year |
|-------------|----------:|--------------|--------|--:|------------:|
| GB          |         5 | Very High    | jenks  | 5 |        2024 |
| DE          |         5 | Very High    | jenks  | 5 |        2024 |
| US          |         5 | Very High    | jenks  | 5 |        2024 |
| FR          |         5 | Very High    | jenks  | 5 |        2024 |
| BR          |         3 | Medium       | jenks  | 5 |        2024 |
| ZA          |         2 | Low          | jenks  | 5 |        2024 |
| IN          |         1 | Very Low     | jenks  | 5 |        2024 |
| NG          |         1 | Very Low     | jenks  | 5 |        2024 |

*(Labels are optional and purely descriptive; the model consumes `bucket_id`.)* 

---

## Acceptance checklist (before S0 runs)

* **Schema pass** against `#/gdp_bucket_map_2024` (or alias `#/gdp_bucket_map`).
* **PK uniqueness:** one row per `country_iso`. **No duplicates.** 
* **Domain checks:** `bucket_id ∈ {1..5}`; `method == "jenks"`; `k == 5`; `source_year == 2024`; `country_iso` matches `^[A-Z]{2}$`. 
* **Foreign key:** all `country_iso` exist in `iso3166_canonical_2024`. 
* **Coverage for runtime:** every `home_country_iso` present in the **merchant seed** has a row here (S0 aborts if missing). 
* **Lineage:** this artefact is enumerated in the **manifest fingerprint** (S0.2); any byte change flips egress lineage. 
* **Consistency with GDP vintage:** built from **the same extract** used by `world_bank_gdp_per_capita_20250415` (obs-year 2024). *(CI may rebuild and diff; runtime still trusts the shipped table.)* 

**Common pitfalls to avoid**

* Using `bucket` instead of **`bucket_id`** (name must match the schema). 
* `source_year` ≠ 2024 (must match the GDP lookup year S0 pins). 
* Missing ISO rows that exist in your merchant set (S0.4 will hard-fail as `E_BUCKET_MISSING`). 
* Recomputing Jenks during runtime (disallowed; rebuild is CI-only and must equal the shipped table). 

### Magnitude (Scale & Coverage)
- **Rows**: exactly `N_ISO` (one per ISO in scope).
- **Buckets**: `|distinct(bucket_id)| == gdp.k_buckets` (policy; default 5).
- **Per-bucket occupancy**: for each `b ∈ [1..K_BUCKETS]`, `count(country_iso where bucket_id=b) ≥ gdp.min_countries_per_bucket`.
- **Integrity**: `method == "jenks"` and `k == gdp.k_buckets` for all rows.

---

# Dataset 5 — `hurdle_coefficients.yaml`  [Model Param/Policy]

**What it is (purpose).** The **single logistic hurdle vector** β used in **S1** (intercept + MCC dummies + channel dummies + 5 GDP-bucket dummies) **and** the **NB-mean vector** `beta_mu` used in **S2**. Its bytes participate in `parameter_hash`, so any change flips run lineage.

**Where it lives (path).** `config/models/hurdle/exports/version={config_version}/{iso8601_timestamp}/hurdle_coefficients.yaml` (artefact registry name: `hurdle_coefficients`). 

**Schema authority.** This is a governed **config** (registry lists `schema: null`). The **shape and ordering constraints** come from S0.5/S1/S2 and the fitting bundle’s **frozen column dictionaries**. Loaders must hard-check lengths and block orders.

---

## Required structure (engine-ready)

> The loader asserts:
> `len(beta) == 1 + C_mcc + 2 + 5` (hurdle) and `len(beta_mu) == 1 + C_mcc + 2` (NB mean). Channel order **exactly** `["CP","CNP"]`; bucket order **exactly** `[1,2,3,4,5]`.

```yaml
# config/models/hurdle/exports/version={config_version}/{iso8601_timestamp}/hurdle_coefficients.yaml  (preview)

semver: "1.3.0"
version: "2025-09-15"
released: "2025-09-15T12:00:00Z"
metadata:
  estimation_window: "2019-01..2024-12"
  stationarity_test_digest: "sha256:abc123..."   # optional; for CI provenance only

# Frozen dictionary orders (must match the fitting bundle)
dicts:
  channel: ["CP","CNP"]           # exact order, normative
  gdp_bucket: [1,2,3,4,5]         # exact order, normative
  # MCC dictionary is often large; include it or reference it.
  # Here we inline a small illustrative subset (order is authoritative):
  mcc: [4111, 5411, 5732, 5812, 5942, 6011]

# Logistic hurdle coefficients  (π = σ(beta · x))
# x = [1 | onehot(mcc) | onehot(channel CP,CNP) | onehot(bucket 1..5)]
beta:
  # intercept
  - -1.2503
  # mcc block (|mcc| = 6 here, preview)
  -  0.0200   # mcc=4111
  -  0.0850   # mcc=5411
  - -0.0312   # mcc=5732
  -  0.1400   # mcc=5812
  -  0.0120   # mcc=5942
  - -0.0200   # mcc=6011
  # channel block (order: CP, CNP)
  -  0.4100   # CP
  - -0.4100   # CNP
  # GDP bucket block (order: 1..5)
  - -0.5500   # bucket=1
  - -0.2000   # bucket=2
  -  0.0000   # bucket=3
  -  0.1200   # bucket=4
  -  0.3500   # bucket=5

# NB mean coefficients  (μ = exp(beta_mu · x_mu))
# x_mu = [1 | onehot(mcc) | onehot(channel CP,CNP)]   # no GDP bucket in NB mean
beta_mu:
  -  0.9100     # intercept
  -  0.0300     # mcc=4111
  -  0.0700     # mcc=5411
  - -0.0200     # mcc=5732
  -  0.1100     # mcc=5812
  -  0.0100     # mcc=5942
  - -0.0100     # mcc=6011
  -  0.0900     # channel=CP
  - -0.0900     # channel=CNP
```

**Why this exact layout?**

* S0.5 defines the **frozen** encoders and the rule that **GDP bucket dummies appear only in the hurdle**; NB mean **excludes** them.
* S1 loads **one** vector `beta`, aligns it to `x_m=[1|MCC|channel|bucket]`, and enforces the length identity before any RNG.
* S2 reads **`beta_mu` from this same YAML** (key `beta_mu`) to compute the NB mean link; dispersion coefficients live in a **separate** YAML (`nb_dispersion_coefficients.yaml`). 

---

## Example dimension check (preview numbers)

If `dicts.mcc` has 6 entries (as above), then:

* `len(beta)` **must** be `1 + 6 + 2 + 5 = 14`;
* `len(beta_mu)` **must** be `1 + 6 + 2 = 9`.
  S1/S2 abort on any mismatch (`E_S1_DSGN_SHAPE_MISMATCH`). 

---

## Acceptance checklist (before S0/S1/S2 run)

* **Block orders fixed:** `channel == ["CP","CNP"]`, `gdp_bucket == [1..5]` (exact), MCC dictionary frozen and **ordered**. 
* **Lengths match:** `len(beta) == 1 + C_mcc + 2 + 5`; `len(beta_mu) == 1 + C_mcc + 2`. 
* **No NaN/Inf:** all coefficients finite (binary64 policy per S0). 
* **Parameter sealing:** file bytes flow into **`parameter_hash`**; changing this YAML must flip the hash. 
* **Loader behavior:** S1 **atomically** loads `beta`; S2 loads `beta_mu` (no map-iteration derived orders; use the dictionaries).

**Common pitfalls to avoid**

* Reversing channel order or using labels other than **CP/CNP**. 
* Including bucket dummies in `beta_mu` (forbidden by design). 
* Omitting/externally sourcing the MCC dictionary order at runtime (must come from the fitting bundle). 

---

**Where it’s consumed**

* **S0** uses it for shape/dictionary checks and (optionally) to build **`hurdle_pi_probs`** deterministically. 
* **S1** computes π and emits the hurdle Bernoulli event. 
* **S2** uses `beta_mu` for ( \mu ); dispersion comes from `nb_dispersion_coefficients.yaml`. 

### Magnitude (Scale & Coverage)
- **Vector lengths**: `len(beta) == 1 + N_MCC + 2 + K_BUCKETS`; `len(beta_mu) == 1 + N_MCC + 2`.
- **Block sizes**: channel block size **2** (`[CP,CNP]`), GDP bucket block **K_BUCKETS**, MCC block **N_MCC**.
- **Completeness**: all coefficients present; no NaN/Inf.

---

# Dataset 6 — `nb_dispersion_coefficients.yaml`  [Model Param/Policy]

**What it is (purpose).** The **negative-binomial dispersion** coefficient vector, used by **S2** to compute
$\phi=\exp(\beta_\phi^\top x_\phi)$. Its bytes are part of `parameter_hash`, so any edit flips run lineage.

**Where it lives (path).**
`config/models/hurdle/nb_dispersion_coefficients.yaml` (artefact name typically `nb_dispersion_coefficients`).

**Authority model.** It’s a governed **config** (no JSON-Schema authority); **shape & order** are enforced by S0/S2 using the **frozen column dictionaries** from the fitting bundle.

---

## Required structure (engine-ready)

> The loader asserts the **exact design order**:
> `x_φ = [1 | one-hot(MCC) | one-hot(channel: CP, CNP) | ln(g_c)]`
> So `len(beta_phi) == 1 + C_mcc + 2 + 1 = C_mcc + 4`.
> Channel order **must be** `["CP","CNP"]`.

```yaml
# config/models/hurdle/nb_dispersion_coefficients.yaml  (preview)

semver: "1.1.0"
version: "2025-09-15"
released: "2025-09-15T12:00:00Z"

dicts:
  channel: ["CP","CNP"]          # exact order, normative
  # MCC dictionary order MUST match the fitting bundle (authoritative order).
  # We inline a small illustrative subset here:
  mcc: [4111, 5411, 5732, 5812, 5942, 6011]

design_order:
  intercept: true
  mcc_one_hot: true
  channel_block: true            # order: CP, CNP
  ln_gdp_pc_usd_2015: true       # scalar term ln(g_c) from S0 GDP lookup

beta_phi:        # dispersion link coefficients (φ = exp(beta_phi · x_φ))
  - -0.3500      # intercept
  # mcc block (|mcc| = 6 in this preview)
  -  0.0100      # mcc=4111
  -  0.0450      # mcc=5411
  - -0.0150      # mcc=5732
  -  0.0600      # mcc=5812
  -  0.0050      # mcc=5942
  - -0.0080      # mcc=6011
  # channel block (order: CP, CNP)
  -  0.0200      # CP
  - -0.0200      # CNP
  # final scalar term
  -  0.1200      # slope on ln(g_c)   (home-country GDP per capita, const-2015 USD)
```

**Dimension check (using the preview MCC list of 6 codes).**
`len(beta_phi)` **must** be `6 + 4 = 10`. S2 aborts the run if this check fails.

---

## How it’s used

* **S0 (prep only).** Freezes the column dictionaries and prepares `ln(g_c)` from the GDP table for each merchant’s home ISO; no stochastic use here.
* **S2 (runtime).** Loads `beta_phi`, builds `x_φ` exactly in the frozen order, computes $\phi=\exp(\beta_\phi^\top x_\phi)$ in binary64 (stable dot product), and **echoes (\phi)** (via μ/φ echo rules) in the **non-consuming** `nb_final`.

---

## Acceptance checklist (before S2 runs)

* **Block orders fixed.** `channel == ["CP","CNP"]`; MCC dictionary present and **ordered** (same order as the fitting bundle).
* **Length identity.** `len(beta_phi) == 1 + C_mcc + 2 + 1`.
* **No NaN/Inf.** All coefficients are finite (numeric profile from S0).
* **Parameter sealing.** File bytes included in `parameter_hash` (altering them flips the hash).
* **Loader behaviour.** Loader must **not** rely on map iteration; it must index by the frozen dictionaries and assert equality of lengths and orders.

**Common pitfalls to avoid**

* Swapping channel order or using labels beyond **CP/CNP**.
* Omitting the final **`ln(g_c)`** coefficient (length off by one).
* Using a different MCC order than the one frozen at fit time (silently scrambles features).

---

**Where it’s consumed downstream**

* Only **S2** consumes this at runtime. (Hurdle `beta`/`beta_mu` are in `hurdle_coefficients.yaml`; this file is **dispersion only**.)

### Magnitude (Scale & Coverage)
- **Vector length**: `len(beta_phi) == 1 + N_MCC + 2 + 1` (intercept + MCC + 2-channel + ln(GDP)).
- **Block sizes**: as in Dataset #5 (`N_MCC`, channels=2).

---

# Dataset 7 — `crossborder_hyperparams.yaml`  [Model Param/Policy]

**What it is (purpose).**
The **only** knobs S4 needs to turn the ZTP (Zero-Truncated Poisson) into a concrete **`K_target`** per merchant: the link coefficients **θ** and the **attempts cap / exhaustion policy**. It’s sealed in **`parameter_hash`** during S0 and then read in S4. (Also carries the **eligibility rule set** that S0.6 consumes to produce `crossborder_eligibility_flags`.)

**Where it lives (path).**
`config/policy/crossborder_hyperparams.yaml`

**Authority model.**
Governed **config** (no JSON-Schema). The **shape and field names** below are enforced by the S0/S4 loaders.

---

## Required structure (engine-ready)

> S4 uses
> $\lambda_{\text{extra}} = \exp(\theta_0 + \theta_1 \cdot \ln N + \theta_2 \cdot X_m)$
> where $N$ is S2’s domestic site count and $X_m$ is the (optional) openness feature from S0 (defaults to **0.0** if absent).
> Sampling regime is engine-constant: **inversion** if $\lambda<10$, else **PTRS**.

```yaml
# config/policy/crossborder_hyperparams.yaml
# Engine-ready: governs S0 eligibility and S4 ZTP link/controls. Part of parameter_hash.

semver: "1.0.2"
version: "2025-10-02"
released: "2025-10-02T12:00:00Z"

# S4 link: λ_extra = exp(θ0 + θ1 * ln N + θ2 * X_m)
ztp_link:
  theta0: -1.10            # float64 (finite)
  theta1:  0.75            # float64 (finite)
  theta2:  0.60            # float64 (finite)

# S4 controls (spec-fixed cap)
ztp_controls:
  MAX_ZTP_ZERO_ATTEMPTS: 64
  ztp_exhaustion_policy: "abort"     # "abort" | "downgrade_domestic"

# S0 ownership of eligibility (merchant-level gate to enter ZTP for foreign spread)
# DSL: decision ∈ {"allow","deny"}, channel tokens ∈ {"CP","CNP"}, iso = merchant's home ISO2 (UPPER),
#       mcc accepts "*" or inclusive ranges "NNNN-NNNN". Precedence: DENY ≻ ALLOW; then priority asc; then id A→Z.
eligibility:
  rule_set_id: "eligibility.v1.2025-10-02"
  default_decision: "deny"
  rules:
    # Regional scope: only merchants with home ISO in R-EEA12 are eligible to attempt foreign spread.
    - id: "ALLOW_REGION_EEA12"
      priority: 15
      decision: "allow"
      channel: ["CP","CNP"]
      iso: ["AT","BE","DE","ES","FI","FR","IE","IT","NL","PT","SE","GB"]
      mcc: ["*"]

    # Sanctions: deny regardless of channel/MCC.
    - id: "DENY_SANCTIONED_HOME"
      priority: 10
      decision: "deny"
      channel: ["CP","CNP"]
      iso: ["IR","KP"]
      mcc: ["*"]
```

**Field rules (must pass):**

* `theta0/theta1/theta2` are **finite** binary64 numbers.
* `MAX_ZTP_ZERO_ATTEMPTS == 64` (**spec-fixed in this version; validator enforces 64**).
* `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}`.
  * `"abort"` → terminal **exhausted** marker, no final.
  * `"downgrade_domestic"` → terminal **final** with `K_target=0` and `exhausted:true`.

* **Eligibility precedence & tie-breaks (S0 DSL):** `DENY ≻ ALLOW`; then ascending `priority`; then `id` A→Z; the **first decision-bearing** rule under that order wins; `default_decision` is the fallback if none fire.

**Also in this file:** the **`eligibility`** rule set that **S0.6** evaluates to produce `crossborder_eligibility_flags` (S3 reads those flags as a gate; S3 does not re-decide eligibility).
* No regime threshold key (sampling regime split is fixed: `λ<10 → inversion`).

---

## How S0 and S4 use it

* **S0:** opens & validates this YAML and **evaluates `eligibility`** to write `crossborder_eligibility_flags` (parameter-scoped); bytes flow into **`parameter_hash`**. Any change here flips lineage.
* **S4 (runtime):**

  1. For each gated merchant, compute **`lambda_extra`** once from the θ link.
  2. Loop attempts: sample Poisson **until k>0** or cap.
  3. Emit **attempt** events (consuming), **rejection** markers for zeros (non-consuming), and a single terminal (**final** or **exhausted**) per merchant according to `ztp_exhaustion_policy`.
  4. After **every** event, append exactly **one** cumulative **trace** row.

---

## Acceptance checklist (before S4 runs)

* **Presence & parse:** File exists, loads, keys exactly `ztp_link.{theta0,theta1,theta2}`, `ztp_controls.{MAX_ZTP_ZERO_ATTEMPTS, ztp_exhaustion_policy}`, `eligibility.{rule_set_id, default_decision, rules[]}`.
* **Channel domain:** `eligibility.rules[].channel` values must use **internal tokens** `CP`/`CNP` (post-S0 mapping), **not** ingress strings.
* **ISO domain:** `eligibility.rules[].iso` values are **uppercase ISO2** and a subset of the canonical ISO set (Dataset #2).
* **MCC tokens:** `eligibility.rules[].mcc` accepts either `"*"` or **inclusive ranges** of the form `"NNNN-NNNN"` within `0000–9999`; **no regex** and no free-form strings.
* **Numeric sanity:** all θ finite; `MAX_ZTP_ZERO_ATTEMPTS == 64` (spec-fixed; attempts domain is 1..64).
* **Policy value:** `ztp_exhaustion_policy` is one of the two allowed strings.
* **Parameter sealing:** the file’s bytes are included in **`parameter_hash`** (changing it flips the hash).
* **No extras:** no unexpected keys; loader should fail closed on unknown fields.

**Common pitfalls to avoid**

* Missing **eligibility** block (S0.6 cannot produce `crossborder_eligibility_flags`).
* Setting the cap to something other than **64** while the validator enforces 64.
* Non-finite θ values (NaN/Inf) or missing one of the three coefficients.
* Adding a `regime_threshold` key (ignored/non-authoritative).

---

## Example behaviour (one merchant)

* Inputs: `N=4`, `X_m=0.3`, θ as above → `lambda_extra = exp(-1.10 + 0.75*ln 4 + 0.60*0.3)`.
* Attempts: draws k = 0,0,2 → emits 2 **rejections**, then **final** `{K_target=2, attempts=3, regime:"inversion"}` (all with proper attempt numbering and traces).
* If 64 zeros in a row:

  * `"abort"` → **exhausted** marker only.
  * `"downgrade_domestic"` → **final** `{K_target=0, exhausted:true}`.

### Magnitude (Scale & Coverage)
- **Parameter count cap**: `≤ max_hparams` (policy; e.g., 128).
- **Required keys**: all keys referenced by S1/S2 kernels must exist; extras allowed but logged.

---

# Dataset 8 — `policy.s3.rule_ladder.yaml`  [Model Param/Policy]

**What it is (purpose).** The **sole policy authority** S3 uses to produce **deterministic admission metadata** and the **only** inter-country order via `candidate_rank`. It does **not** re-decide eligibility (S0 writes `crossborder_eligibility_flags`). No RNG; pure, ordered rules; **closed vocabularies**.

**Where it lives (path).** `config/policy/s3.rule_ladder.yaml` (artefact registry id `mlr.1A.policy.s3.rule_ladder`).

**Who consumes it.**
S3.1 **evaluates** the ladder; S3.2 builds the candidate set; S3.3 **ranks** using a key derived from the ladder `(precedence, priority, rule_id, …)`. S3 **reads** `crossborder_eligibility_flags` (S0) as a gate; the ladder then builds admission metadata and ranking only. The resulting `candidate_rank` is the **only** inter-country order. **Egress `outlet_catalogue` never encodes cross-country order—consumers must join on `s3_candidate_set.candidate_rank`.**

---

## Required structure (binding shape)

Top-level required keys:

* `reason_codes : array<string>` — **closed** set (A→Z stable).
* `filter_tags : array<string>` — **closed** set (A→Z stable).
* `rules : array<Rule>` — **total ordered** rules. 

Each `Rule` **must** have:
`rule_id : [A-Z0-9_]+` (unique), `precedence ∈ {"DENY","ALLOW","CLASS","LEGAL","THRESHOLD","DEFAULT"}`, `priority : int`, `is_decision_bearing : bool`, `predicate : string` (deterministic over the S3 Context), `outcome.reason_code : string ∈ reason_codes`, optional `outcome.tags : array<string> ⊆ filter_tags`. 

**Precedence law (how decisions are chosen).**
`DENY ≻ ALLOW ≻ {CLASS,LEGAL,THRESHOLD,DEFAULT}`; within each precedence: sort by `priority` asc, then `rule_id` A→Z; the **first decision-bearing** rule under that order is the **decision source**. Exactly **one** terminal, decision-bearing `DEFAULT` must exist (catch-all). 

**Determinism constraints.** Predicates may use only equality/inequality, set-membership, ISO lexicographic comparisons, and numeric comparisons over the S3 **Context** fields: `merchant_id, home_country_iso, mcc, channel, N` **and the candidate’s `country_iso`** (plus artefact-declared constants). No RNG, no clock, no external calls.

---

## Minimal, engine-ready preview (illustrative)

```yaml
# config/policy/s3.rule_ladder.yaml
# Engine-ready: S3 builds admission metadata and the ONLY inter-country order (candidate_rank). No eligibility here.

rule_set_id: "CB-2025.10"
notes: "Closed vocabs, total order, single DEFAULT. Predicates use S3 Context + candidate.country_iso only."

# Closed vocabularies (must be stable A→Z)
reason_codes:
  - ALLOW_EEA_CNP_GROCERY
  - DENY_NON_REGION
  - DENY_SANCTIONED_CP
  - DEFAULT_FALLBACK

filter_tags:
  - EEA
  - GROCERY
  - REGION_SCOPE
  - SANCTIONED

# Total-ordered rules (first decision-bearing match under precedence/priority/id wins)
# Precedence: DENY ≻ ALLOW ≻ CLASS/LEGAL/THRESHOLD/DEFAULT
rules:
  # Guard: never rank foreign destinations outside the region (belt-and-braces with S0 scope).
  - rule_id: "DENY_NON_REGION"
    precedence: "DENY"
    priority: 5
    is_decision_bearing: true
    predicate: 'country_iso not in {"AT","BE","DE","ES","FI","FR","IE","IT","NL","PT","SE","GB"}'
    outcome:
      reason_code: "DENY_NON_REGION"
      tags: ["REGION_SCOPE"]

  # Example deny: CP to sanctioned destinations
  - rule_id: "DENY_SANCTIONED_CP"
    precedence: "DENY"
    priority: 10
    is_decision_bearing: true
    predicate: 'channel == "CP" && country_iso in {"IR","KP"}'
    outcome:
      reason_code: "DENY_SANCTIONED_CP"
      tags: ["SANCTIONED"]

  # Example allow: grocery (MCC 5411) CNP to EEA destinations
  - rule_id: "ALLOW_EEA_CNP_GROCERY"
    precedence: "ALLOW"
    priority: 20
    is_decision_bearing: true
    predicate: 'channel == "CNP" && mcc == 5411 && country_iso in {"AT","BE","DE","ES","FI","FR","IE","IT","NL","PT","SE","GB"}'
    outcome:
      reason_code: "ALLOW_EEA_CNP_GROCERY"
      tags: ["EEA","GROCERY"]

  # Terminal catch-all (mandatory)
  - rule_id: "DEFAULT"
    precedence: "DEFAULT"
    priority: 9999
    is_decision_bearing: true
    predicate: "true"
    outcome:
      reason_code: "DEFAULT_FALLBACK"
      tags: []
```

This preview satisfies: **closed vocabs**, **total order**, and **exactly one DEFAULT**. Predicates refer only to Context fields (`channel`, `mcc`, `home_country_iso`) and literal sets—fully deterministic. 

---

## What S3 produces from this artefact

* **S3.1 (ladder eval)** → `admission_meta`, `rule_trace` (ordered, flags decision source), `merchant_tags` (A→Z). 
* **S3.3 (ranking)** → per-foreign `AdmissionMeta = {precedence, priority, rule_id, country_iso, stable_idx}` and a **total, contiguous** `candidate_rank` with **home=0**. File order is non-authoritative; `candidate_rank` is the *only* order.

---

## Acceptance checklist (before S3 runs)

* **Presence/shape:** has `reason_codes[]`, `filter_tags[]`, and `rules[]` with required fields. 
* **Closed sets:** every `outcome.reason_code` ∈ `reason_codes`; every tag ∈ `filter_tags`. 
* **Total order & terminal:** precedence is well-formed; exactly **one** `DEFAULT` rule with `is_decision_bearing==true` and a predicate that always fires. 
* **Deterministic predicates:** use only allowed features/operations (Context fields + artefact constants). No external references. 
* **ISO/Channel domains:** ISO lists use **uppercase ISO2**; `channel` predicates must use **internal tokens** `CP`/`CNP` (post-S0 mapping), **not** ingress strings.
* **Predicate language (clarification):** allowed ops are **equality** (`==`), **set membership** (`IN [...]`), and **simple numeric comparisons** on numeric fields; **no regex** and **no range syntax inside strings**. Prefer **explicit finite sets** in rules to avoid ambiguity and drift.
  *Note:* The **S0 `eligibility` DSL** (in Dataset 7) **does allow MCC range tokens** like `"5000-5999"`; the **S3 ladder DSL intentionally forbids them**. This difference is by design.
* **Registry alignment:** artefact is listed in the registry (path/semver/digest) and depends on `iso3166_canonical_2024`. 

**Failure modes the validator will raise**
`ERR_S3_RULE_LADDER_INVALID` (missing DEFAULT / non-total / unknown vocab), `ERR_S3_RULE_EVAL_DOMAIN` (predicate uses unknown value/field), `ERR_S3_RULE_CONFLICT` (ties among decision-bearing rules after all tiebreaks). 

**Common pitfalls to avoid**

* Encoding ranges or regexes in predicates that your deterministic DSL doesn’t support (prefer explicit set membership). 
* Introducing new reason codes or tags in a rule without adding them to the **closed** vocab arrays. 
* Multiple `DEFAULT` rules or a `DEFAULT` that doesn’t always fire. 

### Magnitude (Scale & Coverage)
- **Rules count**: `1 ≤ rules ≤ rule_ladder.max_rules` (policy; e.g., 64).
- **Universe match**: ISO and GDP bucket universes referenced here must equal `RUN_ISO` and `[1..K_BUCKETS]`.

---

# Dataset 9 — `settlement_shares_2024Q4`  [External Dataset]

**What it is (purpose).** Long-form **currency→country settlement share vectors** with observation counts. Sealed in S0; consumed later in 1A (e.g., currency→country expansion, priors).

**Where it lives (path).**
`reference/network/settlement_shares/2024Q4/settlement_shares.parquet` — no path partitions.

**Schema authority (must match).**
`schemas.ingress.layer1.yaml#/settlement_shares_2024Q4` (dictionary may point to alias `#/settlement_shares`, which resolves to the same anchor). **JSON-Schema is the authority.** 

**Primary key.** `("currency","country_iso")` (long form). 

**Columns & types (exact).** 

* `currency : ISO4217` (uppercase 3-letter code)
* `country_iso : ISO2` (uppercase; **FK →** `iso3166_canonical_2024.country_iso`)
* `share : pct01` (numeric in **[0,1]**)
* `obs_count : int64` (≥ 0)

**Constraint (must hold).** For each `currency`, **Σ share = 1.0** within **tolerance 1e-6**. 

**How 1A uses it.** Sealed by S0; later states (S5/S6) expand currency to country and build deterministic weights/caches together with `ccy_country_shares_2024Q4` and smoothing params. 

---

## Example rows (engine-usable)

| currency | country_iso |    share | obs_count |
|----------|-------------|---------:|----------:|
| USD      | US          | 0.850000 |    128450 |
| USD      | CA          | 0.100000 |     14200 |
| USD      | MX          | 0.050000 |      8120 |
| EUR      | DE          | 0.230000 |     97501 |
| EUR      | FR          | 0.200000 |     91334 |
| EUR      | NL          | 0.150000 |     41220 |
| EUR      | IT          | 0.140000 |     40550 |
| EUR      | ES          | 0.120000 |     39700 |
| EUR      | IE          | 0.080000 |     23100 |
| EUR      | PT          | 0.080000 |     22750 |

*(Per currency block, shares sum to 1 within 1e-6; ISO codes are uppercase; PK is `(currency,country_iso)`.)* 

---

## Acceptance checklist (before sealing / use)

* **Schema pass** against `#/settlement_shares_2024Q4` (or alias `#/settlement_shares`). 
* **PK uniqueness:** no duplicate `(currency,country_iso)`. 
* **Domain checks:** `currency` matches ISO-4217; `country_iso` matches `^[A-Z]{2}$` and **FKs to ISO**; `share ∈ [0,1]`; `obs_count ≥ 0`. 
* **Group sum rule:** for each `currency`, `Σ share = 1.0 ± 1e-6`. (Validator will hard-fail this.) 
* **Registry/dictionary hygiene:** dictionary item points to this **JSON-Schema** anchor; registry entry present with path/version.

**Common pitfalls to avoid**

* Lower/mixed-case ISO codes (must be uppercase). 
* Rounding shares that cause group sums to drift beyond **1e-6**. 
* Extra columns not defined in the schema (keep exactly the four required). 

### Magnitude (Scale & Coverage)
- **Currency set (`C`)**: `|C| ≥ 1`; if a policy currency universe exists, enforce `C ⊆ policy.ccy_universe`.
- **Per-currency coverage**: for each `c ∈ C`, `count(country_iso where share>0 and country_iso ∈ RUN_ISO) ≥ shares.min_iso_per_currency`.
- **Row cap**: `row_count ≤ N_ISO · |C|` (long-form envelope).
- **Observation floor**: `obs_count ≥ shares.min_obs_per_pair` for every `(currency, country_iso)`.

---

# Dataset 10 — `ccy_country_shares_2024Q4`  [External Dataset]

**What it is (purpose).** Long-form **currency → country split “priors”** with observation counts. It’s sealed in S0 for hermeticity and later consumed in 1A (e.g., currency→country expansion / caches).

**Where it lives (path).**
`reference/network/ccy_country_shares/2024Q4/ccy_country_shares.parquet` — no path partitions. (As specified in the dataset dictionary & registry.)

**Schema authority (must match).**
`schemas.ingress.layer1.yaml#/ccy_country_shares_2024Q4` (dictionary may point to alias `#/ccy_country_shares`, which resolves to the same anchor). **JSON-Schema is the authority.** 

**Primary key.** `("currency","country_iso")` (long form). 

**Columns & types (exact).** 

* `currency : ISO4217` (uppercase 3-letter)
* `country_iso : ISO2` (uppercase; **FK →** `iso3166_canonical_2024.country_iso`)
* `share : pct01` (numeric in **[0,1]**)
* `obs_count : int64` (≥ 0)

**Constraint (must hold).** For each `currency`, **Σ share = 1.0** within **tolerance 1e-6**. 

**Where 1A uses it later.** It’s listed as a reference in the artefact registry and participates (with `settlement_shares_2024Q4` and smoothing params) in building the deterministic **`ccy_country_weights_cache`** and **`merchant_currency`** caches. 

---

## Example rows (engine-usable)

| currency | country_iso |    share | obs_count |
|----------|-------------|---------:|----------:|
| GBP      | GB          | 0.970000 |     75000 |
| GBP      | GI          | 0.020000 |      1520 |
| GBP      | IM          | 0.010000 |       780 |
| EUR      | DE          | 0.230000 |     97501 |
| EUR      | FR          | 0.200000 |     91334 |
| EUR      | NL          | 0.150000 |     41220 |
| EUR      | IT          | 0.140000 |     40550 |
| EUR      | ES          | 0.120000 |     39700 |
| EUR      | IE          | 0.080000 |     23100 |
| EUR      | PT          | 0.080000 |     22750 |

*(Per-currency block, shares sum to 1 within 1e-6; ISO codes uppercase; PK is `(currency,country_iso)`; `obs_count ≥ 0`.)* 

---

## Acceptance checklist (before sealing / use)

* **Schema pass** against `#/ccy_country_shares_2024Q4` (or alias `#/ccy_country_shares`). 
* **PK uniqueness:** no duplicate `(currency,country_iso)`. 
* **Domain checks:** `currency` is ISO-4217; `country_iso` matches `^[A-Z]{2}$` and FKs to ISO; `share ∈ [0,1]`; `obs_count ≥ 0`. 
* **Group sum rule:** for each `currency`, `Σ share = 1.0 ± 1e-6`. (Validator hard-fails otherwise.) 
* **Registry/dictionary hygiene:** dictionary item & registry entry present, pointing to the **JSON-Schema** anchor and the exact path/version shown above.

**Common pitfalls to avoid**

* Lower/mixed-case ISO codes (must be uppercase). 
* Rounding that breaks the per-currency sum rule (>1e-6 drift). 
* Extra columns not defined in the schema (keep exactly the four required). 

### Magnitude (Scale & Coverage)
- **Currency alignment**: `distinct(currency)` must equal the set `C` in Dataset #9 (or a documented policy subset/superset).
- **Per-currency coverage**: same gate as Dataset #9.
- **Row cap**: `row_count ≤ N_ISO · |C|`.
- **Observation floor**: `obs_count ≥ shares.min_obs_per_pair` for every `(currency, country_iso)`.

---

# Dataset 11 — `world_countries`  [External Dataset]

**What it is (purpose).** Canonical **country boundary polygons** used for geo-conformance checks and spatial joins. Pinned for Layer-1 hermeticity; consumed by **1A/1B/2A** (even if 1A only references it lightly now). 

**Where it lives (path).**
`reference/spatial/world_countries/2024/world_countries.parquet` — **no path partitions**. 

**Schema authority (must match).**
`schemas.ingress.layer1.yaml#/world_countries_shp` (type: **geotable**, CRS **EPSG:4326**). **JSON-Schema is the authority.** 

**Columns & geometry (exact).** 

* `country_iso : ISO2` (uppercase; **PK**; **FK →** `iso3166_canonical_2024.country_iso`)
* `name : string` (optional display name)
* `geom : geometry` (**Polygon** | **MultiPolygon**, WGS84)

---

## Example rows (engine-usable; WKT excerpts for readability)

| country_iso | name           | geom (WKT excerpt)                                      |
|-------------|----------------|---------------------------------------------------------|
| GB          | United Kingdom | `MULTIPOLYGON((( -7.57 49.96, ... , 1.77 51.04 )))`     |
| DE          | Germany        | `POLYGON(( 5.87 47.27, ... , 15.04 55.06 ))`            |
| US          | United States  | `MULTIPOLYGON((( -124.73 24.52, ... , -66.95 49.38 )))` |

*(In files, `geom` is GeoParquet geometry in EPSG:4326; WKT here is just to visualize.)* 

---

## Acceptance checklist (before sealing/consuming)

* **Schema pass** against `#/world_countries_shp`; table **type = geotable**; **CRS = EPSG:4326**. 
* **PK uniqueness:** one row per `country_iso` (uppercase `^[A-Z]{2}$`). FK to ISO table holds. 
* **Geometry validity:** each `geom` is **Polygon/MultiPolygon**, non-empty, valid rings; no other geometry types. CRS stored and correct. 
* **No partitions:** path has no `{…}` tokens; dictionary entry points to the single GeoParquet file. 
* **Registry/dictionary hygiene:** dataset listed with `schema_ref` to this anchor and license **ODbL-1.0**. 

**Common pitfalls**

* Mixed/invalid CRS (anything but **EPSG:4326** will fail). 
* MultiLine/Point geometries (must be Polygon/MultiPolygon only). 
* ISO2 not uppercased / missing in canonical ISO table. 

### Magnitude (Scale & Coverage)
- **Rows**: exactly `N_ISO` (one feature per ISO in scope).
- **Geometry budgets**: for every row, `vertices ≤ geom.max_vertices_per_polygon` and `rings ≤ geom.max_rings_per_polygon`.
- **CRS/type**: schema-gated (EPSG:4326; Polygon/MultiPolygon).

---

# Dataset 12a — `tz_world_2025a`  [External Dataset]

**What it is (purpose).** Canonical **TZ-world** polygons (by IANA TZID) pinned for Layer-1 hermeticity and consumed downstream by **2A** (civil time-zone derivation). Not used by S0→S4 directly, but it **must** be sealed in the run’s manifest. 

**Where it lives (path).**
`reference/spatial/tz_world/2025a/tz_world.parquet` — **no** path partitions. 

**Schema authority (must match).**
`schemas.ingress.layer1.yaml#/tz_world_shp` → alias that **resolves to** `#/tz_world_2025a`. **JSON-Schema is the only authority.** 

**Table type & CRS.** `type: geotable`, geometry column **`geom`**, allowed types **Polygon/MultiPolygon**, **CRS = EPSG:4326**. 

**Primary key.** `["tzid","polygon_id"]` (unique per polygon within a TZID). 

**Columns & types (exact).** 

* `tzid : string` (IANA TZID; pattern `^[A-Za-z0-9_+\-./]+$`)
* `polygon_id : int32` (deterministic polygon identifier **per tzid**)
* `geom : geometry` (GeoParquet WGS84)

**Licence.** ODbL-1.0 (as recorded in the dictionary/registry).

---

## Example rows (engine-usable; WKT excerpts just to visualise)

| tzid             | polygon_id | geom (WKT excerpt)                                 |
|------------------|-----------:|----------------------------------------------------|
| Europe/London    |          1 | `MULTIPOLYGON((( -8.6 49.9, ... , 1.8 55.8 )))`    |
| America/New_York |          1 | `MULTIPOLYGON((( -79.8 24.5, ... , -71.8 45.0 )))` |
| Africa/Lagos     |          1 | `POLYGON(( 2.7 4.3, ... , 14.7 13.9 ))`            |

*(In files, `geom` is GeoParquet geometry in EPSG:4326; these WKT snippets are illustrative only.)* 

---

## How it’s used later (context)

* **2A** opens this geotable to map site coordinates → `tzid`, with strict **EPSG:4326** checks and deterministic spatial-indexing; any drift or non-conformance aborts. (Your design also documents shapefile provenance, STR-tree determinism, and tie-break rules; pinning the GeoParquet here makes the run hermetic for later use.)

---

## Acceptance checklist (before sealing)

* **Schema pass** against `#/tz_world_shp` (alias → `#/tz_world_2025a`). 
* **CRS & geometry:** `geom` is **Polygon/MultiPolygon** in **EPSG:4326** (WGS84). 
* **PK uniqueness:** no duplicate `(tzid, polygon_id)`. 
* **Domain checks:** `tzid` matches the allowed pattern (IANA-style IDs). 
* **No partitions:** the path points to a single GeoParquet file (dictionary lists none). 
* **Registry/dictionary hygiene:** entry points to the **JSON-Schema** anchor and records licence/version/path exactly as above.

**Common pitfalls to avoid**

* Wrong CRS or mixed geometry types (must be Polygon/MultiPolygon, EPSG:4326). 
* Omitting `polygon_id` (required for the composite PK). 
* Using non-IANA strings or illegal characters in `tzid`. 

### Magnitude (Scale & Coverage)
- **Unique TZIDs**: `tz.min_tzid ≤ N_TZID ≤ tz.max_tzid` (policy).
- **Polygons**: `N_POLY_TZ ≤ tz.max_polygons`.
- **PK density**: for every `tzid`, `count(polygon_id) ≥ 1`.
- **CRS/type**: schema-gated (EPSG:4326; Polygon/MultiPolygon).

---

# Dataset 12b — `population_raster_2025`  [External Dataset]

**What it is (purpose).** Canonical **population-density raster** pinned for Layer-1 hermeticity; consumed by **1B** as a spatial prior (or deterministic fallback) when placing outlets. Not read by S0→S4, but **must** be sealed in the run’s manifest. 

**Where it lives (path).**
`reference/spatial/population/2025/population.tif` — single COG file, no path partitions. (Dictionary + registry point here.)

**Schema authority (must match).**
`schemas.ingress.layer1.yaml#/population_raster_2025` (compat alias: `#/population_raster`). **JSON-Schema is the authority.** 

**Raster contract (exact).** 

* `driver: "COG"` (Cloud-Optimized GeoTIFF)
* `crs: "EPSG:4326"` (lat/lon, WGS84)
* `bands: 1`
* `dtype: float32` (values normalised at ingest)
* `nodata: -1.0`
* `pixel_unit: "persons"`
* `overview_levels: [2, 4, 8, 16]`

---

## “gdalinfo-style” header (illustrative, matches the contract)

```text
Driver: COG/Cloud Optimized GeoTIFF
Coordinate System: EPSG:4326 (WGS84)
Bands: 1  Type=Float32  NoData=-1.0
Overviews: 2x, 4x, 8x, 16x
Pixel Unit: persons
```

*(The engine does not require exact width/height/geotransform in S0; 1B will consume those when building spatial priors.)* 

---

## How it’s used later (context)

* **1B spatial priors.** Population may be used directly (e.g., HRSL/WorldPop) or as a component of blends; 1B logs weights, sampling indices, and Fenwick-tree build details so any draw is exactly replayable. 
* **Deterministic fallback.** If a chosen prior has **zero support** inside a country, the engine falls back to a governed population raster, tagging rows (`prior_tag='FALLBACK_POP'`) and recording provenance; CI enforces a max fallback rate. 

---

## Acceptance checklist (before sealing)

* **Schema pass** against `#/population_raster_2025` (or alias `#/population_raster`). 
* **COG compliance** (internal tiling + overviews present): must expose **2,4,8,16** overview levels. 
* **CRS & bands:** CRS is exactly **EPSG:4326**; **one** band only. 
* **Type & nodata:** band **Float32** with **NoData = −1.0**; values represent **persons**. 
* **Dictionary/registry hygiene:** entry points to this anchor and path; artefact is listed (digest, semver/version, licence) so S0 can seal it.

**Common pitfalls to avoid**

* Wrong CRS (e.g., EPSG:3857) or multiple bands. 
* Missing COG overviews (2/4/8/16). 
* Using integer dtype or `nodata=0` (must be **Float32**, **−1.0**). 
* Skipping the dictionary/registry entry (then S0 can’t include it in the **manifest fingerprint**). 

### Magnitude (Scale & Coverage)
- **File size**: `bytes ≤ raster.max_bytes` (policy).
- **Overviews**: if `raster.require_overviews == true`, COG must advertise ≥1 overview level.
- **Band/type**: Bands==1, dtype Float32 (schema); NoData present. S0 records `width`, `height`, `transform` in the manifest (no hard gate on exact dims).
- **IO hint**: require tiled layout (COG); S0 must not attempt full in-memory load.

---

## Dataset 13 — `ccy_smoothing_params.yaml`  [Model Param/Policy · **Required by S5**]

**What it is (purpose).** S5’s governed policy for blending, smoothing, floors and fixed-dp. **Changing its bytes flips `parameter_hash`**; S5 will not run without it. 

**Where it lives (canonical path).** `config/allocation/ccy_smoothing_params.yaml`

**Schema/authority.** Governed config (enforced by S5 loader; JSON-Schema optional). Keys and domains **must** match the contract below.

**Required structure (exact keys).**

```yaml
semver: "<MAJOR.MINOR.PATCH>"
version: "YYYY-MM-DD"
dp: <int 0..18>                       # fixed decimals for OUTPUT weights
defaults:
  blend_weight: <0..1>
  alpha:        <≥0>                  # Dirichlet mass (per-ISO via overrides)
  obs_floor:    <int ≥0>
  min_share:    <0..1>                # floor applied post-smoothing
  shrink_exponent: <≥0>               # <1 treated as 1 at eval
per_currency:                          # OPTIONAL; ISO-4217 uppercase keys
  <CCY>:
    blend_weight|alpha|obs_floor|min_share|shrink_exponent: <…>
overrides:                             # OPTIONAL fine-grain ISO floors/alphas
  alpha_iso:     { <CCY>: { <ISO2>: <≥0> } }
  min_share_iso: { <CCY>: { <ISO2>: <0..1> } }
```

**Acceptance checklist.**

* Keys present: `semver, version, dp, defaults` (required). Values in domain above.
* All CCYs **uppercase ISO-4217**; all ISO2 **uppercase** and FK-valid to canonical ISO.
* **Feasibility:** for each currency, Σ `min_share_iso[cur][iso] ≤ 1.0`.
* **Override resolution:** ISO-override → per-currency → defaults (deterministic).
* **Lineage:** file is listed in artefact registry and included in the governed set **𝓟**; bytes **must** flip `parameter_hash`. 

**Where it’s used.** S5 builds `ccy_country_weights_cache` (and optional `merchant_currency`) deterministically from Dataset #9/#10 + this policy. 

---

## Dataset 14 — `iso_legal_tender_2024`  [External Dataset · **Optional for S5.0 `merchant_currency`**]

**What it is (purpose).** Canonical **ISO2 → primary legal tender** map used only if you emit `merchant_currency` (κₘ provenance fallback). 

**Where it lives (path).** `reference/iso/iso_legal_tender/2024/iso_legal_tender.parquet`

**Schema authority (must match).** `schemas.ingress.layer1.yaml#/iso_legal_tender_2024` (add this anchor if not already present).

**Columns & types (exact).**

* `country_iso : ISO2` (uppercase; **PK**; **FK →** `iso3166_canonical_2024.country_iso`)
* `primary_ccy : ISO4217` (uppercase)

**Acceptance checklist.**

* Schema pass; PK uniqueness on `country_iso`; FK to canonical ISO; both codes uppercase.
* Coverage: all `home_country_iso` in merchant seed appear.
* Registry/dictionary entries present (schema_ref, licence, retention). 

**Where it’s used.** S5.0 may populate `merchant_currency` (κₘ) with precedence & tie-break rules from the S5 spec. 

---

# G1 — `numeric_policy.json`  [Governance Input]

Here’s a drop-in **`numeric_policy.json`** that matches your S0.8 contract (binary64, RNE, FMA-off, no FTZ/DAZ, fixed-order reductions), plus the minimal extras your docs make normative (total-order for floats, shortest round-trip float printing). You’d store it at:

`reference/governance/numeric_policy/{version}/numeric_policy.json` 

```json
{
  "policy_id": "mlr.gov.numeric_policy@1",
  "semver": "1.0.0",
  "version": "2025-10-01",
  "binary_format": "ieee754-binary64",
  "rounding_mode": "rne",
  "fma_allowed": false,
  "flush_to_zero": false,
  "denormals_are_zero": false,
  "endianness": "little",
  "nan_inf_is_error": true,
  "sum_policy": "serial_neumaier",
  "reduction_order": "fixed_serial",
  "parallel_decision_kernels": "disallowed",
  "float_total_order": "ieee754_totalOrder",
  "json_float_printing": "shortest_roundtrip",
  "constants_encoding": "binary64_hex_literals",
  "build_contract": {
    "cflags": [
      "-fno-fast-math",
      "-fno-unsafe-math-optimizations",
      "-ffp-contract=off",
      "-fexcess-precision=standard",
      "-frounding-math",
      "-fno-associative-math",
      "-fno-reciprocal-math",
      "-fno-finite-math-only"
    ],
    "env": {
      "MKL_NUM_THREADS": "1",
      "OPENBLAS_NUM_THREADS": "1"
    }
  },
  "self_tests": {
    "require_attestation": true,
    "suite": [
      "rounding",
      "ftz_daz",
      "fma_contraction",
      "libm_regression",
      "neumaier_consistency",
      "total_order"
    ]
  }
}
```

Why this matches your spec (key points):

* **binary64 + RNE**, **FMA off**, **no FTZ/DAZ** are the S0.8.1 must-holds; changing this file flips the fingerprint because S0 opens it in S0.2.
* **Neumaier** fixed-order reductions and **no parallel BLAS** are required for any decision/ordering path. 
* **Shortest round-trip float printing** (for payload numbers like `pi`, `u`) and **IEEE-754 totalOrder** are enforced downstream by S1/S2/validators; encoding them here keeps the policy single-sourced.
* Compiler/env flags in **`build_contract`** mirror S0.8.4, and S0’s self-tests produce `numeric_policy_attest.json` capturing these plus digests of this file and the math profile manifest.

---

# G2 — `math_profile_manifest.json`  [Governance Input]
Here’s a drop-in **`math_profile_manifest.json`** that matches your S0.8 contract (pins a deterministic libm surface; exposes the exact function set the loader checks; carries artifact digests). Store it at:

`reference/governance/math_profile/{version}/math_profile_manifest.json`. 

```json
{
  "math_profile_id": "mlr-math-1.2.0",
  "semver": "1.2.0",
  "version": "2025-09-15",
  "vendor": "acme-deterministic-libm",
  "build": "glibc-2.38-toolchain-2025-04-10",
  "functions": [
    "exp", "log", "log1p", "expm1",
    "sqrt", "sin", "cos", "atan2",
    "pow", "tanh", "erf", "lgamma"
  ],
  "artifacts": [
    { "name": "libmlr_math.so", "sha256": "TBD_SHA256_LIB" },
    { "name": "headers.tgz", "sha256": "TBD_SHA256_HDRS" },
    { "name": "test_vectors.json", "sha256": "TBD_SHA256_TESTS" }
  ],
  "notes": "Deterministic across platforms; sqrt correctly rounded; others bit-identical under this profile."
}
```

Why this is on-spec (tight):

* S0 requires a **deterministic libm profile** covering exactly these functions (including **`lgamma`** and **`erf`**) and mandates that this manifest be folded into the **S0.2 artefact set**; the attestation later records its digest.
* Your L1 loader reads `math_profile_id` and asserts the **function set** covers the required surface before proceeding; missing any of them raises `E_NUM_LIBM_PROFILE`. 

---

## G3 — `policy.s6.selection.yaml`  [Governance Input · **Required by S6**]

**What it is (purpose).** Pins S6 behaviour: logging mode, zero-weight handling, optional membership emission, and candidate caps. Listed in 𝓟—**changes flip `parameter_hash`**.

**Where it lives (path).** `config/policy.s6.selection.yaml`

**Schema/authority.** Register a `$ref` (e.g., `schemas.layer1.yaml#/policy/s6_selection`) with `additionalProperties:false`.

**Required keys & domains.**

```yaml
policy_semver: "<MAJOR.MINOR.PATCH>"
version: "YYYY-MM-DD"
defaults:
  emit_membership_dataset: <bool>     # default false
  log_all_candidates:     <bool>      # default true
  zero_weight_rule:       "exclude" | "include"   # default "exclude"
  max_candidates_cap:     <int ≥0>    # default 0 (no cap)
# OPTIONAL: currency-specific overrides (same keys except log_all_candidates)
per_currency:
  <CCY>: { emit_membership_dataset|zero_weight_rule|max_candidates_cap: … }
```

**Acceptance checklist.**

* Values in domain; overrides only by **uppercase ISO-4217**; **no** per-currency override for `log_all_candidates` (global only).
* Policy files are members of **𝓟**; bytes change flips `parameter_hash`.
* Dictionary/registry entries exist (id, path, licence/retention) and `$ref` resolves.

**Where it’s used.** S6 selection & logging (`gumbel_key` budgets; membership surface emission); validator relies on this to set coverage/counter-replay expectations.

---

## G4 — `policy.s7.bounds.yaml`  [Governance Input · **Optional for S7**]

**What it is (purpose).** Enables **bounded Hamilton** in S7: per-ISO integer floors/ceilings; dp for residual quantisation (S7 binds dp_resid=8 by spec; include for clarity).

**Where it lives (path).** `config/policy.s7.bounds.yaml`

**Required structure.**

```yaml
policy_semver: "<MAJOR.MINOR.PATCH>"
version: "YYYY-MM-DD"
dp_resid: 8                           # S7 spec binding; keep 8
floors:   { <ISO2>: <int ≥0>, ... }   # OPTIONAL; absent ISO ⇒ 0
ceilings: { <ISO2>: <int ≥0>, ... }   # OPTIONAL; absent ISO ⇒ +INF
```

**Acceptance checklist.**

* ISO keys **uppercase** and FK-valid; if both present for an ISO, `ceiling ≥ floor`.
* Feasibility guard (per merchant): Σ floors ≤ N ≤ Σ ceilings, else **FAIL**.
* Listed in 𝓟 if you enable the bounded variant; bytes flip `parameter_hash`.

**Where it’s used.** Only when the S7 bounds lane is turned on; base S7 runs without this (still dp_resid=8).

---

# O1 — `policy.s3.base_weight.yaml`  [Model Param/Policy]

**What it is (purpose).**
Governed **priors policy** for S3. It supplies a **run-constant `dp`** and a **deterministic rule set** that decides which `(merchant_id, country_iso)` candidates receive a **non-negative base score** (not a probability). S3 turns those scores into **fixed-dp decimal strings** and emits them in `s3_base_weight_priors`. No RNG; no renormalisation.

**Where it lives (path).**
`config/policy/s3.base_weight.yaml` (artefact registry id `mlr.1A.policy.s3.base_weight`; depends on `iso3166_canonical_2024`).

**Who consumes it.**
S3 L1 kernel **`s3_compute_priors`** (optional lane). L2 emits `s3_base_weight_priors` if present. L3 validates writer sort, subset coverage vs candidates, `dp` consistency, and fixed-dp string shape.

---

## Required structure (engine-ready)

Top-level keys your loader already expects:
`{ dp:int, selection_rules: RuleSpec[], constants: Map<string,float>, sets?: Map<string, ISO2[]> }`

* **`dp`** must be **int in [0..18]** and is **constant per run**. 
* **`selection_rules`** are evaluated **in order**; each rule’s predicate is a deterministic, side-effect-free expression over **S3 Context** fields (`merchant_id, home_country_iso, mcc, channel, N`) **and the candidate’s `country_iso`** (plus any named ISO sets you define under `sets`). A rule either *excludes* (no score) or *assigns* a **non-negative** score (via constants). 
* **`constants`** holds named non-negative float64 constants used to build scores. 
* **Forbidden:** any key implying probabilities/renormalisation (loader enforces `NOT HAS_KEY(..., "renormalise")`). 

### Minimal, policy-true preview


*Optional extensions:* Rules may declare `score_value` for literal deterministic weights, and a top-level `normalisation` block (for example `method: sum_to_target` with an optional positive `target`) can rescale the resulting scores without introducing probabilities.
```yaml
# config/policy/s3.base_weight.yaml
semver: "1.0.0"
version: "2025-10-02"

# All priors are quantised to this many decimal places and emitted as strings.
dp: 4

# Non-negative constants used to build scores (scores are NOT probabilities; no renormalisation).
constants:
  base: 1.0000
  grocery_bonus: 0.2500
  eea_bonus: 0.1000

# Reusable ISO2 sets (UPPERCASE) for predicates.
sets:
  EEA12: ["AT","BE","DE","ES","FI","FR","IE","IT","NL","PT","SE","GB"]
  SANCTIONED_DEST: ["IR","KP"]

# Ordered rules — evaluated in order; the FIRST matching rule that yields a score wins.
# A rule with [] components EXCLUDES the candidate (no prior row).
selection_rules:
  # Block sanctioned destinations
  - id: "DENY_SANCTIONED_DEST"
    predicate: 'country_iso in SANCTIONED_DEST'
    score_components: []

  # Regional guard (belt-and-braces; aligns to your region scope)
  - id: "DENY_NON_REGION"
    predicate: 'country_iso not in EEA12'
    score_components: []

  # Category-specific bump: groceries (MCC 5411) over CNP to EEA12
  - id: "GROCERY_CNP_EEA"
    predicate: 'channel == "CNP" && mcc == 5411 && country_iso in EEA12'
    score_components: ["base","grocery_bonus","eea_bonus"]

  # Baseline for any in-region destination
  - id: "BASELINE_REGION"
    predicate: 'country_iso in EEA12'
    score_components: ["base"]

  # Terminal default (should never fire if region guard is in place, but kept for totality)
  - id: "DEFAULT"
    predicate: 'true'
    score_components: []
```

**How scores are formed (deterministic):**
Your L1 hook **`EVAL_PRIOR_SCORE`** computes `w ≥ 0` from the matching rule by **summing the named constants** in `score_components` (no variable or time-dependent terms). `w` is then quantised to a fixed-dp **string** via the exact decimal half-even routine and emitted as `base_weight_dp` with the same `dp` on every row. The output table shape and constraints are fixed by `schemas.1A.yaml#/s3/base_weight_priors`.

---

## Acceptance checklist (loader + validator)

**Loader (S3·L0) must verify:**

* `dp ∈ [0..18]` (else `ERR_S3_PRIOR_DOMAIN`). 
* All `constants.*` are **finite, ≥ 0** (else `ERR_S3_PRIOR_DOMAIN`). 
* Predicates only reference allowed fields/sets; `sets` contain **uppercase ISO2** and are a subset of canonical ISO. 
* **No** `renormalise` key present. 

**Kernel (S3·L1) guarantees & checks:**

* Produces rows only for a **subset of the candidate set**; writer sort `(merchant_id, country_iso)`. 
* `base_weight_dp` is a **fixed-dp decimal string** (half-even), and **`dp` is constant** within the run. 

**Validator (S3·L3) will fail if:**

* Priors contain a country **not in** `s3_candidate_set` for that merchant (`PRIORS-EXTRA-COUNTRY`).
* File order is not non-decreasing `(merchant_id, country_iso)` (`DATASET-UNSORTED`).
* Any `base_weight_dp` fails fixed-dp format or `dp` **isn’t constant** (`PRIORS-DP-VIOL` / `ERR_S3_FIXED_DP_FORMAT`). 

---

## Where it shows up on disk (downstream)

If `priors_enabled=true`, L2 emits:
`data/layer1/1A/s3_base_weight_priors/parameter_hash={parameter_hash}/…`
Schema anchor: **`schemas.1A.yaml#/s3/base_weight_priors`** (PK `merchant_id,country_iso`; columns `merchant_id, country_iso, base_weight_dp, dp, parameter_hash[, produced_by_fingerprint]`). **Scores, not probabilities.**

---

### Notes & guardrails (to keep it friction-free)

* Keep the rule algebra **simple and deterministic** (sums of named constants are ideal). If you later add multipliers, stay within pure arithmetic over constants and Context fields (no clocks, no random, no IO). 
* It’s acceptable for **no rule** to assign a score for some merchants — L1 returns an **empty** priors array; integerisation (if enabled) falls back to **uniform** shares. 
* Changing `dp` or the rule set **changes policy** → new `parameter_hash` (S0.2 sealing). 

---

# O2 — `policy.s3.thresholds.yaml`  [Model Param/Policy]

**What it is (purpose).**
Optional **integerisation policy** for S3 that supplies **per-ISO floors/ceilings** and the **residual quantisation precision** used by the **bounded Hamilton (Largest-Remainder)** step. No RNG; used only if you enable S3’s integerisation lane that emits `s3_integerised_counts`.

**Where it lives (path).**
`config/policy/s3.thresholds.yaml` *(artefact registry id: `mlr.1A.policy.s3.thresholds`; mark as “optional” and a dependency of the integerisation lane)*. The dataset it influences is `data/layer1/1A/s3_integerised_counts/parameter_hash={parameter_hash}/` with schema `schemas.1A.yaml#/s3/integerised_counts`.

**Who consumes it.**
S3·L0/§13 when building bounds and running **Largest-Remainder**; S3·L3 validates feasibility, sum to `N`, and `residual_rank`.

---

## Required structure (engine-ready)

Top-level keys:

```yaml
dp_resid: <int>                 # quantisation places for residuals (binding spec value: 8)
floors:   { <ISO2>: <int≥0>, ... }     # optional; absent ISO ⇒ floor 0
ceilings: { <ISO2>: <int≥0>, ... }     # optional; absent ISO ⇒ +INF (no cap)
```

* **`dp_resid`** is the **residual quantisation precision** used after floors/ceilings and before tie-breaks. The spec binds this to **8**; if omitted, S3 defaults to 8. 
* **`floors/ceilings`** are **per-country integers** applied merchant-locally during integerisation: floors are enforced first, ceilings clamp post-floor base counts, then the **Largest-Remainder** bump distributes the leftover subject to capacity (`base < ceiling`). Feasibility rules apply. 

---

## Minimal, policy-true preview

```yaml
# config/policy/s3.thresholds.yaml
semver: "1.0.0"
version: "2025-10-02"

# Quantisation for residuals BEFORE tie-breaks (binding value in spec = 8).
dp_resid: 8

# Optional per-country integer floors (absent ISO ⇒ 0)
floors:
  IE: 0
  NL: 0

# Optional per-country integer ceilings (absent ISO ⇒ +INF)
ceilings:
  IE: 3
  NL: 3
```

**How it behaves in S3.**

1. Build exact fractional targets `t_i` from priors (or uniform if priors absent).
2. Set **base** counts to `⌊t_i⌋`, raise to **floor** if needed; enforce `Σ floor_i ≤ N`, clamp to **ceiling**; if `Σ base > N` → **infeasible**.
3. Compute **quantised residuals** at `dp_resid` (half-even), mark **eligible** (`base < ceiling`).
4. Distribute the leftover `R = N − Σ base` by **Largest-Remainder**, at most **one bump per eligible**; if `R > eligible_count`, **infeasible**.
5. Emit `count` and deterministic **`residual_rank`** (sort by residual↓, ISO↑, stable_idx↑).

---

## Acceptance checklist (loader + validator)

**Loader (S3·L0) must verify:**

* `dp_resid` is **int ≥ 0**; for this spec, **`dp_resid == 8`** (treat others as unsupported). 
* `floors`/`ceilings` keys are **uppercase ISO2** present in the canonical ISO table; values are **ints ≥ 0**; for each ISO where both present, **`ceiling ≥ floor`**. 

**Kernel/Validator guarantees:**

* Integerisation uses priors→targets (or uniform), applies bounds, quantises residuals at **`dp_resid`**, and emits **`residual_rank`** with counts that **sum to `N`**. Feasibility checks enforce `Σ floors ≤ N`, and the **one-bump** capacity rule.

---

## Notes & guardrails

* **No “home-aware” placeholders.** Bounds are keyed by **ISO**, not by “home”; S3 applies them to whichever ISO appear in the merchant’s candidate set. If you need home-specific logic, encode it in the **candidate ladder** or a separate policy stage, not here. 
* **Priors/weights vs bounds.** Priors determine the ideal fractional split; bounds can still force non-zero counts where priors give zero weight (via floors). If **all priors zero**, S3 falls back to **uniform** shares deterministically. 
* **Tie-break determinism.** Residual ties break by **ISO A→Z** (then **stable_idx** if provided), which is what the validator re-derives to produce `residual_rank`. 

---

# O3 — `ccy_smoothing_params.yaml`  [Model Param/Policy]

**Alias of Dataset 13 (notes only).**
Canonical path: `config/allocation/ccy_smoothing_params.yaml`. This section is kept as **informative** notes for Codex; defer to **Dataset 13** for the binding preview.

**Who consumes it.**
S5 **weights builder** and S6 **merchant_currency** cache builder. Changing this file **changes policy** → new `parameter_hash`.

---

## Required structure (engine-ready)

Top-level keys your loader should support:

```yaml
semver: "1.0.0"
version: "YYYY-MM-DD"

dp: 6                             # fixed decimals for OUTPUT weights (0..18)

defaults:
  blend_weight: 0.60              # w in [0,1]: mix ccy_shares vs settlement_shares
  alpha: 0.50                     # additive Dirichlet α per country (non-negative)
  obs_floor: 1000                 # minimum effective observation mass (≥0)
  min_share: 0.000001             # post-step floor per country (∈[0,1])
  shrink_exponent: 1.0            # ≥0; 0=no shrink, >1 shrinks influence of huge obs

per_currency:
  USD:
    blend_weight: 0.70
    alpha: 0.20
    obs_floor: 5000
    min_share: 0.00001
  EUR:
    blend_weight: 0.65
    alpha: 0.30
    obs_floor: 4000

overrides:                        # (optional) ISO-scoped α bumps or floors/caps
  alpha_iso:
    USD:
      CA: 0.40
      MX: 0.30
  min_share_iso:
    EUR:
      IE: 0.00005
```

**Parameter domains (loader must enforce):**

* `dp ∈ [0..18]`; `blend_weight ∈ [0,1]`; `alpha ≥ 0`; `obs_floor ≥ 0`; `min_share ∈ [0,1]`; `shrink_exponent ≥ 0`.
* `overrides.alpha_iso.* ≥ 0`; `overrides.min_share_iso.* ∈ [0,1]`.

---

## Deterministic algorithm (what S5 does, per currency `cur`)

Let from **(10)**: `s_ccy[c]` (share), `n_ccy[c]` (obs_count).
From **(9)**: `s_settle[c]`, `n_settle[c]`. Missing rows imply zero. Define sets over **union of countries** seen in either input.

1. **Blend the two sources (shares):**
   `w ← per_currency[cur].blend_weight` (else `defaults.blend_weight`)
   `q[c] = w * s_ccy[c] + (1 - w) * s_settle[c]` (for all countries `c` in union)

2. **Effective evidence mass (robust to sparsity):**
   `N0 = w * Σ n_ccy + (1 - w) * Σ n_settle`
   `N_eff = max( obs_floor, N0^(1/shrink_exponent) )`
   (with `shrink_exponent=1.0` ⇒ `N_eff = max(obs_floor, N0)`)

3. **Dirichlet smoothing (additive α):**
   Base `α_default ← per_currency[cur].alpha` (else `defaults.alpha`).
   Per-ISO α override: `α[c] = alpha_iso[cur][c]` if present, else `α_default`.
   `A = Σ_c α[c]`.
   `posterior[c] = ( q[c] * N_eff + α[c] ) / ( N_eff + A )`.

4. **Floor tiny mass & renormalise (deterministic):**
   Apply ISO-specific `min_share_iso[cur][c]` if defined, else `min_share`.
   `p'[c] = max( posterior[c], min_share_for_c )`.
   **Renormalise**: `p[c] = p'[c] / Σ_c p'[c]` (required so Σ=1).

5. **Quantise for output:**
   Emit `weight_dp[c] = to_fixed_dp_string(p[c], dp)` (half-even).
   Output table passes Σ weights = 1 within tolerance (`1e-6` at dp=6).

---

## Minimal, policy-true preview

```yaml
semver: "1.0.0"
version: "2025-10-02"

dp: 6

defaults:
  blend_weight: 0.60
  alpha: 0.50
  obs_floor: 1000
  min_share: 0.000001
  shrink_exponent: 1.0

per_currency:
  GBP:
    blend_weight: 0.65
    alpha: 0.30
    obs_floor: 2500

overrides:
  alpha_iso:
    GBP:
      GI: 0.40
      IM: 0.35
  min_share_iso:
    GBP:
      GI: 0.000010
      IM: 0.000010
```

---

## Acceptance checklist (loader + validator)

**Loader must reject if:**

* Any parameter outside domain; any ISO not uppercase; override given for ISO not present in canonical ISO2.
* `sum(min_share_iso[cur].values) > 1` for any currency (feasibility).
* Duplicate keys / unknown fields (fail closed).

**Validator will assert (on the built cache):**

* For each currency, weights are **fixed-dp** strings with the declared `dp`; Σ weights = **1 ± 1e-6**; all `∈[0,1]`.
* Coverage equals the **union of countries** in inputs 9 & 10 (unless you purposely restrict elsewhere).
* Writer sort `(currency, country_iso)`; partition is **parameter_hash**.

---

## Notes & guardrails

* Keep **renormalisation** explicit and last (after floors) so Σ=1 holds deterministically.
* If a currency has **no rows** in both inputs, treat as configuration error (or require an explicit `per_currency` block for it).
* Raising `alpha` increases smoothing toward uniform; raising `obs_floor` down-weights very sparse empirical signals; `blend_weight` controls the relative trust in inputs (10) vs (9).

---