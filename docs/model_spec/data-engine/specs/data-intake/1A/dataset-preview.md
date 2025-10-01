> A conceptual preview of the input datasets required for the start of the engine at subsegment 1A of layer 1 in state-0 (and through to S9)

# Dataset 1 — `transaction_schema_merchant_ids` (processed preview)

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

---

# Dataset 2 — `iso3166_canonical_2024` (processed preview)

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

---

# Dataset 3 — `world_bank_gdp_per_capita_20250415` (processed preview)

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

---

# Dataset 4 — `gdp_bucket_map_2024` (Jenks-5 lookup)

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

---

# Dataset 5 — `hurdle_coefficients.yaml` (governed parameter bundle)

**What it is (purpose).** The **single logistic hurdle vector** β used in **S1** (intercept + MCC dummies + channel dummies + 5 GDP-bucket dummies) **and** the **NB-mean vector** `beta_mu` used in **S2**. Its bytes participate in `parameter_hash`, so any change flips run lineage.

**Where it lives (path).** `configs/models/hurdle/hurdle_coefficients.yaml` (artefact registry name: `hurdle_coefficients`). 

**Schema authority.** This is a governed **config** (registry lists `schema: null`). The **shape and ordering constraints** come from S0.5/S1/S2 and the fitting bundle’s **frozen column dictionaries**. Loaders must hard-check lengths and block orders.

---

## Required structure (engine-ready)

> The loader asserts:
> `len(beta) == 1 + C_mcc + 2 + 5` (hurdle) and `len(beta_mu) == 1 + C_mcc + 2` (NB mean). Channel order **exactly** `["CP","CNP"]`; bucket order **exactly** `[1,2,3,4,5]`.

```yaml
# configs/models/hurdle/hurdle_coefficients.yaml  (preview)

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

---

# Dataset 6 — `nb_dispersion_coefficients.yaml` (governed parameter bundle)

**What it is (purpose).** The **negative-binomial dispersion** coefficient vector, used by **S2** to compute
(\phi=\exp(\beta_\phi^\top x_\phi)). Its bytes are part of `parameter_hash`, so any edit flips run lineage.

**Where it lives (path).**
`configs/models/hurdle/nb_dispersion_coefficients.yaml` (artefact name typically `nb_dispersion_coefficients`).

**Authority model.** It’s a governed **config** (no JSON-Schema authority); **shape & order** are enforced by S0/S2 using the **frozen column dictionaries** from the fitting bundle.

---

## Required structure (engine-ready)

> The loader asserts the **exact design order**:
> `x_φ = [1 | one-hot(MCC) | one-hot(channel: CP, CNP) | ln(g_c)]`
> So `len(beta_phi) == 1 + C_mcc + 2 + 1 = C_mcc + 4`.
> Channel order **must be** `["CP","CNP"]`.

```yaml
# configs/models/hurdle/nb_dispersion_coefficients.yaml  (preview)

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
* **S2 (runtime).** Loads `beta_phi`, builds `x_φ` exactly in the frozen order, computes (\phi=\exp(\beta_\phi^\top x_\phi)) in binary64 (stable dot product), and **echoes (\phi)** (via μ/φ echo rules) in the **non-consuming** `nb_final`.

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

---

# Dataset 7 — `crossborder_hyperparams.yaml` (governed parameter bundle)

**What it is (purpose).**
The **only** knobs S4 needs to turn the ZTP (Zero-Truncated Poisson) into a concrete **`K_target`** per merchant: the link coefficients **θ** and the **attempts cap / exhaustion policy**. It’s sealed in **`parameter_hash`** during S0 and then read in S4. *(Eligibility rules live in the S3 ladder, not here.)*

**Where it lives (path).**
`configs/allocation/crossborder_hyperparams.yaml`

**Authority model.**
Governed **config** (no JSON-Schema). The **shape and field names** below are enforced by the S0/S4 loaders.

---

## Required structure (engine-ready)

> S4 uses
> (\lambda_{\text{extra}} = \exp(\theta_0 + \theta_1 \cdot \ln N + \theta_2 \cdot X_m))
> where (N) is S2’s domestic site count and (X_m) is the (optional) openness feature from S0 (defaults to **0.0** if absent).
> Sampling regime is engine-constant: **inversion** if (\lambda<10), else **PTRS**.

```yaml
# configs/allocation/crossborder_hyperparams.yaml  (preview)

semver: "1.0.2"
version: "2025-09-15"
released: "2025-09-15T12:00:00Z"

ztp_link:
  # η = θ0 + θ1*ln(N) + θ2*openness
  theta0: -1.10        # float64, finite
  theta1:  0.75        # float64, finite
  theta2:  0.60        # float64, finite

ztp_controls:
  MAX_ZTP_ZERO_ATTEMPTS: 64          # hard cap on zero draws before resolution
  ztp_exhaustion_policy: "abort"     # "abort" | "downgrade_domestic"
```

**Field rules (must pass):**

* `theta0/theta1/theta2` are **finite** binary64 numbers.
* `MAX_ZTP_ZERO_ATTEMPTS` is a **positive integer** (the engine and validator assume **64** as the cap for compliance).
* `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}`.

  * `"abort"` → terminal **exhausted** marker, no final.
  * `"downgrade_domestic"` → terminal **final** with `K_target=0` and `exhausted:true`.

**Not in this file:**

* No S3 eligibility rules.
* No regime threshold (it’s fixed in code as `λ<10 → inversion`).

---

## How S0 and S4 use it

* **S0 (sealing only):** opens and validates this YAML; bytes flow into **`parameter_hash`**. Any change here flips lineage.
* **S4 (runtime):**

  1. For each gated merchant, compute **`lambda_extra`** once from the θ link.
  2. Loop attempts: sample Poisson **until k>0** or cap.
  3. Emit **attempt** events (consuming), **rejection** markers for zeros (non-consuming), and a single terminal (**final** or **exhausted**) per merchant according to `ztp_exhaustion_policy`.
  4. After **every** event, append exactly **one** cumulative **trace** row.

---

## Acceptance checklist (before S4 runs)

* **Presence & parse:** File exists, loads, keys exactly `ztp_link.{theta0,theta1,theta2}`, `ztp_controls.{MAX_ZTP_ZERO_ATTEMPTS, ztp_exhaustion_policy}`.
* **Numeric sanity:** all θ finite; `MAX_ZTP_ZERO_ATTEMPTS ≥ 1` (recommended **64**).
* **Policy value:** `ztp_exhaustion_policy` is one of the two allowed strings.
* **Parameter sealing:** the file’s bytes are included in **`parameter_hash`** (changing it flips the hash).
* **No extras:** no unexpected keys; loader should fail closed on unknown fields.

**Common pitfalls to avoid**

* Putting S3 **eligibility** rules here (they belong in `policy.s3.rule_ladder.yaml`).
* Setting the cap to something other than **64** while the validator enforces 64.
* Non-finite θ values (NaN/Inf) or missing one of the three coefficients.
* Adding a `regime_threshold` key (ignored/non-authoritative).

---

## Example behaviour (one merchant)

* Inputs: `N=4`, `X_m=0.3`, θ as above → `lambda_extra = exp(-1.10 + 0.75*ln 4 + 0.60*0.3)`.
* Attempts: draws k = 0,0,2 → emits 2 **rejections**, then **final** `{K_target=2, attempts=3, regime:"ptrs"}` (all with proper attempt numbering and traces).
* If 64 zeros in a row:

  * `"abort"` → **exhausted** marker only.
  * `"downgrade_domestic"` → **final** `{K_target=0, exhausted:true}`.

---

# Dataset 8 — `policy.s3.rule_ladder.yaml` (governed policy artefact)

**What it is (purpose).** The **sole policy authority** S3 uses to (a) decide a merchant’s **cross-border eligibility** and (b) produce **deterministic admission metadata** that later becomes the **only** inter-country order via `candidate_rank`. No RNG; pure, ordered rules; **closed vocabularies**.

**Where it lives (path).** `configs/policy.s3.rule_ladder.yaml` (artefact registry id `mlr.1A.policy.s3.rule_ladder`).

**Who consumes it.**
S3.1 **evaluates** the ladder; S3.2 builds the candidate set; S3.3 **ranks** using a key derived from the ladder `(precedence, priority, rule_id, …)`. The resulting `candidate_rank` is the **only** inter-country order.

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

**Determinism constraints.** Predicates may use only equality/inequality, set-membership, ISO lexicographic comparisons, and numeric comparisons over the S3 **Context** fields: `merchant_id, home_country_iso, mcc, channel, N` (plus artefact-declared constants). No RNG, no clock, no external calls. 

---

## Minimal, engine-ready preview (illustrative)

```yaml
# configs/policy.s3.rule_ladder.yaml  (preview)
# Optional metadata (not normative for the engine):
rule_set_id: "CB-2025.09"
notes: "Illustrative; closed vocab + total order + single DEFAULT"

# Closed vocabularies (must be closed & stable A→Z)
reason_codes:
  - ALLOW_EEA_CNP_GROCERY
  - DENY_SANCTIONED_CP
  - DEFAULT_FALLBACK

filter_tags:
  - EEA
  - GROCERY
  - SANCTIONED

# Total ordered rules
rules:
  - rule_id: "DENY_SANCTIONED_CP"
    precedence: "DENY"
    priority: 10
    is_decision_bearing: true
    predicate: 'channel == "CP" && home_country_iso in {"IR","KP"}'
    outcome:
      reason_code: "DENY_SANCTIONED_CP"
      tags: ["SANCTIONED"]

  - rule_id: "ALLOW_EEA_CNP_GROCERY"
    precedence: "ALLOW"
    priority: 20
    is_decision_bearing: true
    predicate: 'channel == "CNP" && mcc == 5411 && home_country_iso in {"AT","BE","DE","ES","FI","FR","IE","IT","NL","PT","SE"}'
    outcome:
      reason_code: "ALLOW_EEA_CNP_GROCERY"
      tags: ["EEA","GROCERY"]

  - rule_id: "DEFAULT"
    precedence: "DEFAULT"
    priority: 9999
    is_decision_bearing: true
    predicate: "true"   # guaranteed catch-all
    outcome:
      reason_code: "DEFAULT_FALLBACK"
      tags: []
```

This preview satisfies: **closed vocabs**, **total order**, and **exactly one DEFAULT**. Predicates refer only to Context fields (`channel`, `mcc`, `home_country_iso`) and literal sets—fully deterministic. 

---

## What S3 produces from this artefact

* **S3.1 (ladder eval)** → `eligible_crossborder`, `rule_trace` (ordered, flags decision source), `merchant_tags` (A→Z). 
* **S3.3 (ranking)** → per-foreign `AdmissionMeta = {precedence, priority, rule_id, country_iso, stable_idx}` and a **total, contiguous** `candidate_rank` with **home=0**. File order is non-authoritative; `candidate_rank` is the *only* order.

---

## Acceptance checklist (before S3 runs)

* **Presence/shape:** has `reason_codes[]`, `filter_tags[]`, and `rules[]` with required fields. 
* **Closed sets:** every `outcome.reason_code` ∈ `reason_codes`; every tag ∈ `filter_tags`. 
* **Total order & terminal:** precedence is well-formed; exactly **one** `DEFAULT` rule with `is_decision_bearing==true` and a predicate that always fires. 
* **Deterministic predicates:** use only allowed features/operations (Context fields + artefact constants). No external references. 
* **ISO/Channel domains:** any ISO lists use **uppercase ISO2**; any `channel` tests use the ingress vocabulary (`"CP"|"CNP"` internally in S3). 
* **Registry alignment:** artefact is listed in the registry (path/semver/digest) and depends on `iso3166_canonical_2024`. 

**Failure modes the validator will raise**
`ERR_S3_RULE_LADDER_INVALID` (missing DEFAULT / non-total / unknown vocab), `ERR_S3_RULE_EVAL_DOMAIN` (predicate uses unknown value/field), `ERR_S3_RULE_CONFLICT` (ties among decision-bearing rules after all tiebreaks). 

**Common pitfalls to avoid**

* Encoding ranges or regexes in predicates that your deterministic DSL doesn’t support (prefer explicit set membership). 
* Introducing new reason codes or tags in a rule without adding them to the **closed** vocab arrays. 
* Multiple `DEFAULT` rules or a `DEFAULT` that doesn’t always fire. 

---

# Dataset 9 — `settlement_shares_2024Q4` (currency→country shares)

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

---

# Dataset 10 — `ccy_country_shares_2024Q4` (intra-currency splits, long form)

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

---

# Dataset 11 — `world_countries` (GeoParquet polygons)

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

---

# Dataset 12a — `tz_world_2025a` (IANA time-zone polygons, GeoParquet)

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

---

# Dataset 12b — `population_raster_2025` (Cloud-Optimized GeoTIFF)

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

---