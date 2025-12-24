# Acquisition Guide — `gdp_bucket_map_2024` (Jenks K=5 GDP-per-capita buckets)

## 0) Purpose and role in the engine

`gdp_bucket_map_2024` is a **precomputed, frozen categorical feature** used in **1A** (and then reused downstream via frozen encoders) to map each `country_iso` to a **GDP bucket** in **{1..5}**.

Key rule: **this artefact is never recomputed at runtime**. It is treated like a reference input and therefore must be **auditable, reproducible, and immutable** once frozen.

---

## 1) Engine requirements (what you are freezing)

### 1.1 Artefact identity

* **ID:** `gdp_bucket_map_2024`
* **Version label:** `2024`
* **Format:** Parquet
* **Target path:** `reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet`
* **Schema anchor:** `schemas.ingress.layer1.yaml#/gdp_bucket_map`

### 1.2 Required schema (must match your ingress schema for `gdp_bucket_map_2024`)

* `country_iso` (ISO-3166-1 alpha-2; FK into `iso3166_canonical_2024.country_iso`) **PK**
* `bucket_id` (int; **must be in [1..5]**)
* `bucket_label` (string; nullable; purely human-readable)
* `method` (string; **must be exactly `jenks`**)
* `k` (int; **must be exactly `5`**)
* `source_year` (int; **the GDP observation year used for bucketing**)

### 1.3 Hard behavioural requirements (from 1A usage)

* For any `country_iso` that the run needs (at minimum: every merchant `home_country_iso`), **a bucket row must exist** and `bucket_id ∈ {1..5}`.
* If a required country is missing from this map, 1A is designed to **fail fast** (not “best effort”).

---

## 2) Inputs (upstream prerequisites)

This artefact is **derived**, not downloaded directly.

### 2.1 Required upstream artefacts

* `iso3166_canonical_2024` (canonical ISO2 universe / FK authority)
* `world_bank_gdp_per_capita_20250415` (WDI GDPpc **constant 2015 USD**), indicator **`NY.GDP.PCAP.KD`**, which is available up to **2024** and licensed **CC BY 4.0**. ([World Bank Open Data][1])

### 2.2 Pinned GDP year (must be explicit)

* **`source_year = 2024`** for this artefact.
* GDP values used must be the WDI series **GDP per capita (constant 2015 US$)** (`NY.GDP.PCAP.KD`). ([World Bank Open Data][1])

---

## 3) The method (what “Jenks K=5” means)

You are freezing a **Jenks / Natural Breaks** classification with **K=5** classes.

Conceptually:

* It chooses breakpoints that **group similar values together** and **maximize differences between classes**. ([ArcGIS Pro][2])

Implementation warning (important for determinism):

* Many “NaturalBreaks” implementations are actually **1D k-means** (can depend on initialization) rather than the **optimal Fisher–Jenks** solution. The PySAL `mapclassify` codebase explicitly notes “Jenks natural breaks is k-means in one dimension” for its natural-breaks helper. ([PySAL][3])
* Also avoid **sampled** variants (they introduce randomness). `mapclassify` documents `FisherJenksSampled` as using a random sample. ([PySAL][4])

**Spec requirement for your engine:** the bucket map must be produced via a **deterministic** procedure (no random init, no sampling, no hidden RNG).

---

## 4) Acquisition procedure (compute + freeze)

### 4.1 Build the bucketing universe (deterministic)

Define:

* **ISO authority set** `I` = all `country_iso` in `iso3166_canonical_2024`
* **GDP snapshot** `G2024` = all rows in `world_bank_gdp_per_capita_20250415` where:

  * `observation_year == 2024`
  * `country_iso ∈ I`
  * `gdp_pc_usd_2015 > 0` (strict)

The set of countries you actually bucket is:

* `U = { country_iso : (country_iso, 2024) ∈ G2024 }`

No imputation is implied here. If a country has no GDP value in 2024, it is **not bucketable** under the stated definition.

### 4.2 Compute Jenks breaks (K=5) over `U`

* Input vector = the multiset of `gdp_pc_usd_2015` for all `country_iso ∈ U`
* Output = 4 breakpoints (`b1..b4`) dividing values into 5 ordered classes from low → high

**Determinism requirements**

* Sort values ascending before classification.
* Use an algorithm that does not depend on random starts/samples.
* MUST use a deterministic **optimal** Jenks implementation (e.g., Fisher-Jenks DP); MUST NOT use sampled variants (e.g., `FisherJenksSampled`).
* If multiple optimal solutions exist (ties), apply a documented tie-break rule (e.g., choose the lexicographically smallest break vector).

**Determinism + non-degeneracy (MUST):** the chosen implementation MUST be **non-sampled** and MUST yield **exactly 5 non-empty buckets**. If ties/degeneracy produce fewer than 5 distinct classes, the build MUST fail closed (do not silently change `k`).

### 4.3 Assign bucket IDs (stable interval semantics)

Define bucket intervals (stable and unambiguous):

* Bucket 1: `[min, b1]`
* Bucket 2: `(b1, b2]`
* Bucket 3: `(b2, b3]`
* Bucket 4: `(b3, b4]`
* Bucket 5: `(b4, max]`

Then for each `country_iso ∈ U`, assign `bucket_id ∈ {1..5}` accordingly.

### 4.4 Emit the table

For each `country_iso ∈ U`, write one row:

* `country_iso`
* `bucket_id` (1..5)
* `bucket_label` (nullable; optional)
* `method = "jenks"`
* `k = 5`
* `source_year = 2024`

Write to:

* `reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet`

---

## 5) Engine-fit validation checklist (must pass before freezing)

### 5.1 Schema + integrity

* PK uniqueness: `country_iso` unique
* Domain checks:

  * `bucket_id ∈ {1,2,3,4,5}`
  * `method == "jenks"`
  * `k == 5`
  * `source_year == 2024`

### 5.2 Coverage checks (the ones that prevent runtime aborts)

At minimum, confirm:

* Every `home_country_iso` appearing in `merchant_ids` has:

  * GDP row in `G2024` **and**
  * bucket row in `gdp_bucket_map_2024`

Recommended (stronger) check:

* Every `country_iso` that can appear in 1A’s candidate-country universe (from your share surfaces / eligibility pipeline) has GDP+bucket coverage, or you accept that those paths will hard-fail.

### 5.3 Distribution sanity (guards against broken bucketing)

* Each bucket has **≥ 1** country (no empty classes).
* Breakpoints are monotone: `b1 ≤ b2 ≤ b3 ≤ b4` (and you can log strictness).

---

## 6) Provenance (audit-grade; mandatory)

Store a provenance sidecar alongside the parquet that records:

* Source GDP artefact ID + vintage: `world_bank_gdp_per_capita_20250415`
* Indicator: `NY.GDP.PCAP.KD` (constant 2015 US$) ([World Bank Open Data][1])
* `source_year = 2024`
* K=5, method=Jenks
* The breakpoints (`b1..b4`) you computed
* Checksums:

  * input GDP parquet sha256 (or its registered digest)
  * output bucket map sha256

This is what makes the bucket map defensible as a “frozen feature surface” rather than a classroom artefact.

---

## 7) Reference links (method definitions / guardrails)

```text
Jenks / Natural Breaks definition (ArcGIS Pro docs):
https://pro.arcgis.com/en/pro-app/3.4/help/mapping/layer-properties/data-classification-methods.htm

Jenks optimization / GVF (Esri KB):
https://support.esri.com/en-us/knowledge-base/what-is-the-jenks-optimization-method-1462479759617-000006743

World Bank indicator definition + license (GDPpc constant 2015 US$, NY.GDP.PCAP.KD):
https://data.worldbank.org/indicator/NY.GDP.PCAP.KD

Mapclassify note: “Jenks natural breaks is k-means in one dimension” (why you must avoid nondeterministic k-means variants):
https://pysal.org/mapclassify/_modules/mapclassify/classifiers.html

Mapclassify API showing sampled Fisher-Jenks exists (avoid sampled / random):
https://pysal.org/mapclassify/api.html
```

---

[1]: https://data.worldbank.org/indicator/NY.GDP.PCAP.KD "GDP per capita (constant 2015 US$)"
[2]: https://pro.arcgis.com/en/pro-app/3.4/help/mapping/layer-properties/data-classification-methods.htm "Data classification methods—ArcGIS Pro | Documentation"
[3]: https://pysal.org/mapclassify/_modules/mapclassify/classifiers.html "Source code for mapclassify.classifiers"
[4]: https://pysal.org/mapclassify/api.html "API reference — mapclassify v2.10.0 Manual"
