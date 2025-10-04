## What the GDP bucket map “is” (information payload)

* A **deterministic segmentation** of countries into **K=5** macro buckets using their **2024 GDP per capita (constant 2015 US$)**.
* It encodes a **coarse, non-linear macro context** that the engine uses as **dummy features** (bucket 1..5) in the **S1 Hurdle** model.
* It’s **not re-estimated at runtime**. You compute it once from the pinned GDP table and **freeze the result** (and the breakpoints) so training/serving are aligned.

In other words: it’s a frozen mapping

```
country_iso → bucket_id ∈ {1,2,3,4,5}
```

plus the **global breakpoints** that define each bucket’s numeric range.

---

## Do we need an external dataset?

**No.** You derive it from your **frozen GDP table** (the one we just built) and then publish two artefacts:

1. **Breaks sidecar** (metadata)

   * `year: 2024`
   * `series: NY.GDP.PCAP.KD`
   * `method: Fisher–Jenks (natural breaks), K=5`
   * `breakpoints`: `[b0, b1, b2, b3, b4, b5]` with `b0 = min(g)`, `b5 = max(g)`
   * `dp` (decimal places used when serialising), `rounding: half-even`
   * `population_weighted: false` (recommended)
   * `input_universe`: count of countries used (should match your GDP table’s coverage)
   * lineage anchors: reference to the GDP dataset’s parameter hash / manifest fingerprint

2. **Per-country bucket map** (the table the engine reads)

   * Columns:

     * `country_iso : ISO2 (PK)`
     * `bucket_id : int ∈ {1..5}`
     * (optional) `gdp_pc_usd_2015 : float64` (echoed for audit/replay)
   * Partitioning & lineage per your S0 rules.

---

## How to derive it (deterministically)

1. **Input universe**

   * Start from the **final GDP CSV** (the 2024 snapshot you just approved).
   * Use only rows with **valid, positive `gdp_pc_usd_2015`** and a valid **ISO-2**.
   * Resulting set size today is ~**177** (or **~184** if you include the few extra territories we can map via your canonical ISO file—e.g., `HK`, `MO`, `PR`, `PS`, `SX`, `TC`, `BM`—all with actual 2024 values).

2. **Compute breaks**

   * Use **Fisher–Jenks (a.k.a. Jenks natural breaks)** with **K=5** on the **unweighted** array of 2024 GDP values.
   * The Fisher–Jenks DP algorithm is **deterministic** for a fixed input; avoid heuristic/approximate variants.
   * **Tie rule:** if a value equals an internal breakpoint, assign it to the **upper** bucket (document this).
   * Store breakpoints with a fixed decimal precision (e.g., `dp=2` or `dp=1`), and record the **exact unrounded** values inside the sidecar for byte-replay.

3. **Assign buckets**

   * For each country: find the interval `[b_k, b_{k+1})` (or your tie rule) that contains `gdp_pc_usd_2015` and set `bucket_id = k+1`.
   * Emit one row per `country_iso`.

4. **Freeze & publish**

   * Publish the **breaks sidecar** and the **bucket map table** together.
   * Pin both to the **same vintage/year** as the GDP table; **do not recompute at runtime**.

---

## Why freeze (and not recompute)?

* Buckets are a **feature definition**, not dynamic data. Recomputing would change design matrices and silently drift your hurdle model’s behaviour.
* Freezing the breaks ensures any refits or replays see the **identical** bucket encoding.

---

## Coverage considerations (your 177 rows)

* The bucket map covers exactly the set with valid 2024 GDP values (e.g., 177 or 184 entries, depending on ISO mapping choice).
* **If** any merchant’s `home_country_iso` is **not** in that set, they won’t have a bucket—S1 dummies would be undefined.
* Remedy **only if needed** (i.e., if such merchants exist):

  1. **Prefer** adding them via a verified 2024 GDP value (some territories do have 2024 values and can be recovered by using your canonical ISO mapping).
  2. If no 2024 exists, you may (with explicit documentation):

     * carry-forward the **most recent** available year for that country; **or**
     * exclude those merchants from the universe for this run.

  * Do **not** impute from regional averages unless you explicitly accept the realism trade-off and record it in the sidecar; it changes the distribution and can shift breaks if you recompute.

---

## Minimal schema (what I recommend you freeze)

**A. Breaks sidecar (YAML/JSON)**

```yaml
gdp_bucket_breaks:
  year: 2024
  series: NY.GDP.PCAP.KD
  method: fisher-jenks
  k: 5
  breakpoints_unrounded: [b0, b1, b2, b3, b4, b5]
  breakpoints_dp: 2
  rounding: half-even
  population_weighted: false
  input_universe: 177    # or 184, depending on mapping choice
  lineage:
    gdp_dataset_parameter_hash: "<...>"
    gdp_dataset_manifest_fingerprint: "<...>"
```

**B. Bucket map table (Parquet/CSV)**

```
country_iso : string(ISO2, uppercase)  # PK
bucket_id   : int8  # {1..5}
# optional:
gdp_pc_usd_2015 : float64
```

---

## My judgement call

* **Derive internally** from your pinned GDP dataset (no external source).
* **Compute once, freeze, and pin** to the GDP vintage/year.
* **Unweighted Fisher–Jenks (K=5)**, document the tie rule, and store breakpoints + lineage in a sidecar.
* **Coverage is sufficient** if all merchant home countries appear in the GDP table; run a quick join to confirm. If gaps matter, add only the **few** countries with real 2024 values (recoverable via your canonical ISO mapping), and avoid imputation unless you must—and if you must, document it loudly.

---

## Implementation

Here’s a clean, deterministic, **Fisher–Jenks (natural breaks)** implementation that:

* reads your frozen GDP CSV (`country_iso,gdp_pc_usd_2015,observation_year,source_series`),
* computes **K** buckets (configurable),
* emits **(1)** a sidecar with exact + rounded breakpoints and lineage, and **(2)** a per-country **bucket map**,
* uses **half-even** rounding and a documented **tie-to-upper** rule,
* stays fast and fully reproducible (no heuristic libs needed).

> **Usage**
>
> ```bash
> python gdp_bucket_map.py \
>   --gdp-csv /path/to/world_bank_gdp_pc_2024.csv \
>   --year 2024 \
>   --k 5 \
>   --dp 2 \
>   --out-dir ./out
> ```
>
> Outputs:
>
> * `./out/gdp_bucket_breaks.Y2024.K5.yaml`
> * `./out/gdp_bucket_map.Y2024.K5.csv`

---


### Notes & knobs you can tweak

* `--k` controls the number of buckets (defaults to **5**).
* `--dp` controls how many decimals the **rounded** breakpoints carry in the sidecar (exact unrounded values are preserved as well).
* Classification uses the **DP class memberships** directly (no float threshold ambiguity). The **sidecar** records a tie rule: “equals internal breakpoint → upper bucket.”
* If you later enhance coverage (e.g., add `HK`, `MO`, `PR`, …) and rerun this script on the updated GDP CSV, the buckets will be recomputed deterministically for the new universe — pin the resulting sidecar to your run/vintage and freeze it.
