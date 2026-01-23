# Derivation Guide — `crossborder_features` (1A deterministic merchant features)

## 0) Purpose (what this artefact is for)

`crossborder_features` is a **parameter-scoped, deterministic** per-merchant feature table used by **1A.S4** when computing the ZTP intensity:

* S4 uses a scalar **`X_m ∈ [0,1]`** (“openness”) in the linear predictor
  `η = θ0 + θ1·log N + θ2·X`, then `λ_extra = exp(η)`.
* If the feature is missing for a merchant, S4 defaults to **`X_m = 0.0`**.

So: this table exists to give S4 a **realistic, stable** merchant-level signal that moves `K_target` without using RNG.

---

## 1) Identity and location (dictionary + schema contract)

### 1.1 Dataset ID

* `crossborder_features`

### 1.2 Partitioning / path

* **Version key:** `{parameter_hash}`
* **Path:** `data/layer1/1A/crossborder_features/parameter_hash={parameter_hash}/`
* **Partition keys:** `parameter_hash`
* **Writer ordering:** `merchant_id` ascending (bytewise / numeric ascending for id64)

### 1.3 Schema authority

* `schemas.1A.yaml#/model/crossborder_features`

### 1.4 Columns (must match schema)

* `merchant_id` (id64)
* `openness` (pct01 in [0,1])
* `source` (string provenance label)
* `parameter_hash` (hex64; must equal partition key)
* `produced_by_fingerprint` (optional hex64; informational only)

---

## 2) Authoritative inputs (read-only)

Derive the merchant feature purely from read-only, deterministic upstream surfaces:

**Required**

* `transaction_schema_merchant_ids` (merchant universe + `mcc`, `channel`, `home_country_iso`)

**Recommended (for realism)**

* `gdp_bucket_map` (map `home_country_iso → bucket_id ∈ {1..5}`)

**Optional**

* `mcc_canonical` (for stable category lookups if you don’t want to hardcode MCC bands)

> No RNG. No sampling. No run_id/seed dependence. This dataset is **parameter-scoped**.

---

## 3) Deterministic derivation recipe (v1 baseline)

### 3.1 Feature definition

Define `openness` as a bounded score composed of:

* **home-country affluence proxy** (GDP bucket)
* **channel propensity** (CNP tends to be more cross-border than CP)
* **MCC tilt** (digital/travel tends to be more cross-border than local-only staples)

### 3.2 v1 mapping tables (minimal but realistic)

**GDP bucket baseline** (monotone; modest range)

| bucket_id | base |
| --------: | ---: |
|         1 | 0.06 |
|         2 | 0.12 |
|         3 | 0.20 |
|         4 | 0.28 |
|         5 | 0.35 |

**Channel delta**

| channel          | delta |
| ---------------- | ----: |
| card_present     | -0.04 |
| card_not_present | +0.08 |

**MCC tilt (additive; small)**

* digital band: `4810–4899`, `5960–5969`, `5815–5818` → `+0.10`
* travel/transport band: `3000–3999`, `4111`, `4121`, `4131`, `4411`, `4511`, `4722`, `4789`, `7011` → `+0.06`
* broad retail band: `5000–5999`, `5300–5399`, `5400–5599` → `+0.03`
* otherwise → `+0.00`

### 3.3 Final formula (v1)

Compute:

* `raw = base(bucket_id) + delta(channel) + tilt(mcc)`
* `openness = clamp01(raw)`  (i.e., min(max(raw, 0.0), 1.0))

### 3.4 Missing-data rules

* If a merchant’s `home_country_iso` can’t be bucketed: treat `bucket_id = 1` (conservative) and set `source` to include a missing marker.
* If any required merchant fields are missing (shouldn’t happen): hard fail (schema/ingress integrity breach).

---

## 4) Output writing rules (must)

* **Row universe:** exactly **one row per `merchant_id`** present in `transaction_schema_merchant_ids`.
* **Partition discipline:** every row embeds the **same** `parameter_hash` equal to the partition key.
* **Ordering:** write rows sorted by `merchant_id` ascending.
* **No dependence on file order** for correctness (but writer must emit sorted output).

---

## 5) Provenance (`source`) convention (recommended)

Because this is a derived feature, make provenance explicit and stable:

* `source: "heuristic_v1:gdp_bucket+channel+mcc"`

If you later change any mapping table/tilt ranges, bump the identifier:

* `source: "heuristic_v2:..."`

(Do not use timestamps in `source` unless you want that to propagate into downstream comparisons.)

---

## 6) MINIMAL EXAMPLE (illustrative only — do not ship as-is)

Assume `parameter_hash = "aaaaaaaa... (64 hex)"` and a known fingerprint.

| merchant_id | home_country_iso | channel          |  mcc |                         openness | source                              |
| ----------: | ---------------- | ---------------- | ---: | -------------------------------: | ----------------------------------- |
|         101 | BI               | card_present     | 5411 | 0.06 + (-0.04) + 0.03 = **0.05** | heuristic_v1:gdp_bucket+channel+mcc |
|         202 | GB               | card_not_present | 5969 |    0.28 + 0.08 + 0.10 = **0.46** | heuristic_v1:gdp_bucket+channel+mcc |
|         303 | US               | card_present     | 4511 | 0.28 + (-0.04) + 0.06 = **0.30** | heuristic_v1:gdp_bucket+channel+mcc |
|         404 | NG               | card_not_present | 5816 |    0.12 + 0.08 + 0.10 = **0.30** | heuristic_v1:gdp_bucket+channel+mcc |
|         505 | MC               | card_present     | 7995 | 0.35 + (-0.04) + 0.00 = **0.31** | heuristic_v1:gdp_bucket+channel+mcc |

Schema-shaped output rows (illustrative):

```yaml
- merchant_id: 202
  openness: 0.46
  source: "heuristic_v1:gdp_bucket+channel+mcc"
  parameter_hash: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  produced_by_fingerprint: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
```

---

## 7) Acceptance checklist (must pass before sealing)

**Shape / integrity**

* [ ] Rowcount equals merchant universe size.
* [ ] `merchant_id` unique (primary key).
* [ ] `openness` finite and in `[0,1]` for all rows.
* [ ] `parameter_hash` embedded equals partition key for all rows.
* [ ] Rows sorted by `merchant_id`.

**Sanity / realism**

* [ ] `mean(openness | CNP)` > `mean(openness | CP)`.
* [ ] `mean(openness | bucket=5)` > `mean(openness | bucket=1)`.
* [ ] Not degenerate: not all zeros; not all identical; reasonable spread (e.g., p5 < p50 < p95).

**Determinism**

* [ ] Rerun on same inputs yields byte-identical output (after canonical sort).

---
