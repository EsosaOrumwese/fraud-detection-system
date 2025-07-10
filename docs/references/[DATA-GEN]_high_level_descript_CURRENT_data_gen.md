# Mid-Level Architecture
Here’s a detailed low-level ASCII flowchart showing how all the pieces fit together in the synthetic data generator:

```text
                                  ┌─────────────────────────────┐
                                  │   generate.py  (entry)      │
                                  │   └─> generate_dataset()    │
                                  │       (alias for core)      │
                                  └─────────────┬───────────────┘
                                                │
                                  ┌─────────────▼───────────────┐
                                  │   cli.py → main()           │
                                  │   └─> parse args            │
                                  └─────────────┬───────────────┘
                                                │
                                  ┌─────────────▼───────────────┐
                                  │ config.py → load_config()   │
                                  │   └─> GeneratorConfig       │
                                  └─────────────┬───────────────┘
                                                │
                                  ┌─────────────▼───────────────┐
                                  │ core.py → generate_dataframe│
                                  └─────────────┬───────────────┘
                                                │
                      ┌─────────────────────────┴──────────────────────────┐
                      │                                                    │
                      │ num_workers > 1?                                   │
                      │                                                    │
              ┌───────▼────────────┐                              ┌────────▼─────────────────┐
              │ Parallel mode:     │                              │ Single-process           │
              │ ┌ init catalogs    │                              │ fallback:                │
              │ │ write_catalogs & │                              │ call _generate_chunk once│
              │ │ load_catalogs    │                              │                          │
              │ └─ init Pool with  │                              │                          │
              │    (_init_worker)  │                              │                          │
              └───────┬────────────┘                              └───────┬──────────────────┘
                      │                                                   │
              ┌───────▼───────────┐           ┌───────────────────────────▼───────────┐
              │Pool.imap_unordered┼──────────►│ _generate_chunk(rows, cfg, seed)      │
              └───────┬───────────┘           └───────────────────────────────────────┘
                      │
                      ▼
    (each worker executes _generate_chunk, which does:)
    ┌────────────────────────────────────────────────────────────────────┐
    │ 1) sample_timestamps(total_rows, start_date, end_date, seed)       │
    │    └─> from temporal.py                                            │
    ├────────────────────────────────────────────────────────────────────┤
    │ 2) generate or reuse catalogs                                      │
    │    ├─> generate_customer_catalog(...)                              │
    │    ├─> generate_merchant_catalog(...)                              │
    │    └─> generate_card_catalog(...)                                  │
    │        (all in catalog.py)                                         │
    ├────────────────────────────────────────────────────────────────────┤
    │ 3) sample_entities(...) → cust_ids, merch_ids, card_ids            │
    │    └─> catalog.py                                                  │
    ├────────────────────────────────────────────────────────────────────┤
    │ 4) compute numeric & categorical features:                         │
    │    • amount (lognormal/normal/uniform)                             │
    │    • device_type, card_scheme, channel, pos_entry_mode             │
    │    • geo (latitude/longitude), ip_address, user_agent              │
    │    • timestamp fields, UUIDs, exp dates, local_time_offset         │
    │    (all in core.py)                                                │
    ├────────────────────────────────────────────────────────────────────┤
    │ 5) assemble Polars DataFrame (including raw merch_risk & card_risk)│
    └────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────────────────┐
        │ Concatenate chunks (if parallel)        │
        └─────────────────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────────────────┐
        │ label_fraud(df, fraud_rate, seed)       │
        │ └─> bursty fraud clustering & logistic  │
        │    draw in labeler.py                   │
        └─────────────────────────────────────────┘
                      │
                      ▼
        ┌──────────────────────────────────────────┐
        │ cast columns to schema & reorder fields  │
        │ (using transaction_schema.yaml)          │
        └──────────────────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────────────────┐
        │ write_parquet(df, out_path)             │
        │ └─> Snappy-compressed Parquet file      │
        │    (core.py)                            │
        └─────────────────────────────────────────┘
                      │
                      ▼
        ┌──────────────────────────────────────────┐
        │ optional S3 upload                       │
        │ └─> boto3.upload_file(...)               │
        │    (back in cli.py)                      │
        └──────────────────────────────────────────┘
```

**Legend & notes:**

* **Entry**: `generate.py` (legacy) or `cli.py` → `main()`
* **Config**: loaded by `config.py` into a `GeneratorConfig` Pydantic model
* **Core**: `core.generate_dataframe()` orchestrates chunking, timestamp sampling, catalog builds, feature generation, DataFrame assembly
* **Temporal**: diurnal Gaussian-mixture sampler in `temporal.py`
* **Catalog**: customer/merchant/card Zipf + Beta risk in `catalog.py`
* **Entity sampling**: weighted draws in `catalog.py:sample_entities()`
* **Labeler**: bursty, risk-weighted logistic fraud labels in `labeler.py`
* **Output**: cast to schema, write as Parquet, optionally upload to S3 via boto3 in the CLI

This ASCII diagram captures the full logical flow, all major modules, and how data moves from configuration to final output.

---

# Section Descriptions
At a mid-level you can think of the generator as five (well-connected) “stages,” each handling one slice of the work:

1. **Entry & Configuration**
   * **CLI/Script bootstrap** (`generate.py` or `cli.py`)
   * **Argument parsing** and **config loading** (`config.py` reads `generator_config.yaml` into a `GeneratorConfig`)

2. **Catalog Preparation**
   * **Customer, merchant, card catalogs** (`catalog.py`)
   * Compute **base risk scores** (Zipf/Beta distributions)
   * Once (or per-worker) in parallel mode, cache/load these tables

3. **Transaction Assembly**
   * **Chunk orchestration** (`core.py`)
     * Decide on single vs. multi-worker
     * Split total rows into chunks
   * For each chunk:
     1. **Timestamp sampling** (`temporal.py`)
     2. **Entity sampling** (pick customer-IDs, merchant-IDs, card-IDs)
     3. **Feature generation** (amount, geo, channel, device, IP, user-agent, UUIDs, etc.)

4. **Labeling**
   * **Fraud tagging** (`labeler.py`)
   * Bursty clusters + logistic-draw based on risk scores

5. **Post-processing & Delivery**
   * **Schema enforcement** (cast types, reorder fields per `transaction_schema`)
   * **Write out** Snappy-compressed Parquet (`core.py`)
   * **Optional upload** to S3 via boto3 (back in `cli.py`)

Each stage hands off to the next in sequence, but catalog prep and chunking can overlap via worker pools, and the final write/upload may be tucked back into the CLI wrapper.

---

## 1. Entry & Configuration
### Entrypoint and Backwards-Compatibility Layer

When you invoke the generator via `generate.py`, the script first re-exports the core functions from the `fraud_detection.simulator` package and then delegates to the CLI entrypoint. At the top of `generate.py`, the module imports `generate_dataframe` and `write_parquet` from `core.py`, as well as the `main` function from `cli.py` (aliased as `_cli_main`). Calling `generate.py` without arguments triggers its `main()` function, which simply calls `_cli_main()`, ensuring that any existing integrations (Airflow DAGs, Makefiles, tests) that rely on `generate_dataset` continue to work unmodified .

### Command-Line Argument Parsing and Logging Configuration

Control then transfers to `cli.py`’s `main()` function. Here, an `argparse.ArgumentParser` defines the accepted flags—among them `--config` (path to your YAML), `--s3`, `--log-level`, `--num-workers`, `--batch-size`, and `--realism` (legacy “v1” vs. preloaded “v2”) . Once `parser.parse_args()` returns an `args` namespace, `logging.basicConfig()` is called with `level=getattr(logging, args.log_level)` and a timestamped format. A debug‐level log records the full parsed arguments, aiding in troubleshooting.

### Loading and Validating the YAML Configuration

Next, the code attempts to load and validate your YAML file via `load_config(args.config)` from `config.py`. This function first checks that the file exists, then parses its contents with `yaml.safe_load()`, and finally invokes `GeneratorConfig.model_validate(data)`—a Pydantic model that enforces the presence of the `catalog`, `temporal`, and `feature` sections (via `@model_validator` hooks) and coerces types such as converting a string `out_dir` into a `Path` . Any `FileNotFoundError`, `ValidationError`, or `ValueError` raised during this process is caught immediately, logged as a “Config error,” and causes the process to exit with code 1.

### Applying CLI Overrides and Preparing for Core Generation

With a fully validated `GeneratorConfig` instance in hand, the CLI layer then applies any performance-tuning overrides supplied on the command line: if `args.num_workers` or `args.batch_size` are non-null, they replace the corresponding values in the config object; if `--realism` was specified, it overrides `cfg.realism` . Finally, the script determines whether to perform an S3 upload by computing `do_upload = args.s3 or cfg.s3_upload`. At that point, all CLI-level concerns are resolved and a log entry reports the target row count, fraud rate, and seed, before handing control off to `core.generate_dataframe(cfg)` to begin the actual data‐generation pipeline.

---

## 2. Catalog Preparation

Upon entering the catalog‐preparation phase, the generator immediately references the `catalog` block of the validated `GeneratorConfig`. This nested `CatalogConfig` object exposes all of the entity‐catalog parameters—including `num_customers`, `num_merchants`, `num_cards`, their respective Zipf exponents, and the Alpha/Beta shape parameters for merchant and card risk—as well as file‐size and Parquet row‐group limits (`max_size_mb` and `parquet_row_group_size`) . These values drive every subsequent step of catalog construction and I/O.

### Pre-Building and Serializing Catalogs (v2 Mode)

If the user has selected “v2” realism, `generate_dataframe()` creates a dedicated on-disk catalog directory under `cfg.out_dir / "catalog"` and invokes `write_catalogs(catalog_dir, cfg)` . Inside `write_catalogs`, three separate Polars DataFrames are constructed via `generate_customer_catalog`, `generate_merchant_catalog`, and `generate_card_catalog`, each seeded and parameterized according to `cfg.catalog` . Once built in memory, these DataFrames are written to Snappy-compressed Parquet files (`customers.parquet`, `merchants.parquet`, `cards.parquet`) using the configured `row_group_size`. After each write, the file size is checked against `cfg.catalog.max_size_mb`; exceeding that limit immediately raises an error, preventing runaway catalog growth.

Immediately following serialization, the generator calls `load_catalogs(catalog_dir)` to read the three Parquet files back into Polars DataFrames, returning the tuple `(cust_df, merch_df, card_df)` for in-memory reuse . This two-step write-then-read ensures that the on-disk artifacts are both valid and size-constrained before any chunked transaction generation begins.

### Worker Initialization with Preloaded Catalogs

In parallel‐generation mode (`cfg.num_workers > 1`), the tuple of preloaded DataFrames is passed as `initargs` to the `multiprocessing.Pool` constructor. The pool’s initializer function, `_init_worker(cust, merch, card)`, assigns these DataFrames to module-level globals (`_CUST_CAT`, `_MERCH_CAT`, `_CARD_CAT`) within each worker process, making them immediately available at chunk time without further disk I/O .

### On-the-Fly Catalog Generation (v1 Mode or Fallback)

If `cfg.realism` remains at its legacy “v1” setting—or if a worker finds its `_CUST_CAT` globals unset—the code falls back to rebuilding all three catalogs at the start of each chunk in `_generate_chunk()`. It checks `if cfg.realism == "v2" and _CUST_CAT is not None`; otherwise it calls `generate_customer_catalog(...)`, `generate_merchant_catalog(...)`, and `generate_card_catalog(...)` anew for that chunk’s RNG seed and Zipf/risk parameters . This approach guarantees reproducible, seeded catalogs per chunk in v1 mode, while v2 mode avoids this overhead by reusing the single prebuilt set.

### Zipf- and Beta-Driven Catalog Construction

Under the hood, each `generate_*_catalog` function begins by computing a normalized Zipf weight vector over entity ranks using the private `_zipf_weights(n, exponent)` routine.

* **Customer catalog**: Produces a two-column DataFrame of `customer_id` (1…N) and Zipf‐derived `weight` (Float64) cast to Polars types .
* **Merchant catalog**: Extends the same Zipf weighting with a per-merchant fraud risk drawn from a Beta(`merchant_risk_alpha`, `merchant_risk_beta`) distribution (via a seeded `default_rng`), and randomly assigns each merchant an MCC code from the `MCC_CODES` list .
* **Card catalog**: Mirrors the merchant approach—drawing Beta-distributed risk, then using a Faker‐seeded SHA-256 generator to create persistent `pan_hash` strings for each `card_id` .

Together, these routines furnish both the sampling weights and risk priors that later drive entity selection and fraud‐label correlation in the transaction assembly stage.

---

## 3. Transaction Assembly
### Chunk Dispatch and Orchestration

Once the generator has pre-built or loaded its catalogs, control returns to the `generate_dataframe(cfg)` function, which decides whether to spawn multiple workers or run single-threaded. If `cfg.num_workers > 1` and `cfg.batch_size` is positive, it computes the number of chunks as `ceil(total_rows / batch_size)` and builds a list of argument tuples `(chunk_size, cfg, seed + chunk_index)`. A `multiprocessing.Pool` is then created with `processes=cfg.num_workers`, passing the preloaded catalog DataFrames into each worker via the `_init_worker` initializer. The pool’s `imap_unordered(_chunk_worker, args)` invokes `_generate_chunk` in parallel for each chunk; as each chunk DataFrame returns, `generate_dataframe` logs its row count and throughput before appending it to a list. After all chunks complete, they are concatenated into a single Polars DataFrame with `pl.concat(dfs, rechunk=False)` .

In the single-worker fallback (`cfg.num_workers == 1`), if “v2” realism and catalogs are already loaded, they are assigned to the module globals and `_generate_chunk(total_rows, cfg, cfg.seed)` is called directly. This path bypasses any inter-process communication yet retains identical chunk-generation logic .

### Per-Chunk Generation Pipeline

The heart of the transaction assembly resides in `_generate_chunk(chunk_rows, cfg, seed)`, which proceeds through a fully vectorized sequence:

**Seeding and Defaults**
Before drawing any random values, the function unpacks `start_date` and `end_date` from `cfg.temporal`, defaulting to today if absent, and seeds Python’s `random`, Faker, and NumPy’s `default_rng` with the provided `seed`, ensuring reproducibility across runs .

**1. Timestamp Sampling**
Timestamps are generated by calling `sample_timestamps(total_rows=chunk_rows, start_date, end_date, seed)`. This routine uniformly samples a calendar date within the inclusive range, then superimposes a three-component Gaussian mixture (morning, afternoon, evening) to model diurnal transaction patterns. The result is a `numpy.datetime64[ns]` array of length `chunk_rows` .

**2. Catalog Access**
Depending on `cfg.realism`, the code either reuses the global `_CUST_CAT`, `_MERCH_CAT`, and `_CARD_CAT` DataFrames (in “v2” mode) or rebuilds them in-memory via `generate_customer_catalog(...)`, `generate_merchant_catalog(...)`, and `generate_card_catalog(...)` using the same Zipf and Beta parameters defined in `cfg.catalog` .

**3. Entity Sampling**
With catalogs in hand, the function draws `chunk_rows` customer, merchant, and card IDs by weight using `sample_entities(catalog, entity_col, size, seed)`. This yields three integer arrays—`cust_ids`, `merch_ids`, and `card_ids`—each sampled according to its catalog’s normalized Zipf weights .

**4. Internal Risk Extraction**
To prepare for later fraud labeling, the per-entity risk scores are looked up by indexing into each catalog’s `"risk"` column with the sampled IDs, producing `m_risk` and `c_risk` float arrays aligned with the chunk’s transactions .

**5. Numeric Feature Generation**
A local time‐offset (in minutes) is drawn as integers between –720 and +840. The transaction amount is sampled according to `cfg.feature.amount_distribution`:

* A lognormal draw when set to `"lognormal"`,
* A normal draw when `"normal"`,
* A uniform draw otherwise.
  The raw amounts are then rounded to two decimal places to produce the `amount` array .

**6. Categorical Feature Generation**
Vectorized NumPy choices produce arrays for:

* `device_type`, weighted by the `cfg.feature.device_types` map;
* `card_scheme` from the fixed list `["VISA","MASTERCARD","AMEX","DISCOVER"]`;
* `channel` from `["ONLINE","IN_STORE","ATM"]`;
* `pos_entry_mode` from `["CHIP","MAGSTRIPE","NFC","ECOM"]`;
* A boolean `is_recurring` mask with \~10% probability of `True` .

**7. Geographic and Currency Fields**
Merchant country codes are sampled from a Faker-generated pool and then mapped to `"EUR"` or `"USD"` based on whether the country is in the hard-coded Eurozone list `_EUR_COUNTRIES`. The merchant’s MCC code is similarly looked up by indexing into the merchant catalog’s `"mcc_code"` column .

**8. Ancillary Identifiers and Location**
Additional fields include:

* `pan_hash`, fetched by indexing the card catalog’s `"pan_hash"` column;
* Uniform latitude and longitude to six decimal places;
* A fully RFC-4122-compliant UUID4 `transaction_id` array generated via the helper `_make_uuid4_hex_array(rng, chunk_rows)`;
* A `device_id` array where \~90% of rows receive a UUID4 and the remainder are `None`;
* Randomly chosen `ip_address` and `user_agent` strings sampled from Faker pools.&#x20;

**9. DataFrame Assembly**
Finally, all arrays are collated into a single Polars DataFrame via `pl.DataFrame({...})`, with keys matching the transaction schema fields (including the internal `merch_risk`, `card_risk`, and `mcc_code`). This DataFrame is returned directly to the orchestration layer for concatenation, labeling, and schema casting .

At the end of this pipeline, each chunk yields a self-contained batch of synthetic transactions, complete with timestamps, identifiers, features, and risk priors, ready for the fraud-labeling stage.

---

## 4. Labeling
### Overview of the `label_fraud` Workflow

Once the raw transaction DataFrame has been assembled and concatenated, the generator hands it off to the `label_fraud` function in **labeler.py**, passing in the full DataFrame, the target `fraud_rate`, and an optional RNG `seed` .  This function enriches the DataFrame with a new Boolean column, `label_fraud`, by executing a two-phase process: first, a risk-weighted logistic draw to approximate the desired marginal fraud rate; second, a series of corrective steps—random drops or burst-clustered additions—to ensure the exact number of fraud cases.

### Preparation and Array Extraction

Upon entry, `label_fraud` reads out the total row count `N` from `df.height` and immediately converts several critical columns into NumPy arrays: the transaction `amount`, merchant-level risk (`merch_risk`), card-level risk (`card_risk`), and the event timestamps as nanoseconds since the Unix epoch .  It then computes per-record “hour of day” by integer-dividing the timestamp array, allowing the later model to upweight nighttime transactions.

### Logistic Scoring and Initial Draw

To seed the fraud probabilities, the function first clamps the provided `fraud_rate` to the open interval (ε, 1 − ε) to avoid degenerate log-odds.  It calculates a logistic intercept as

```python
intercept = log(fr / (1–fr))
```

and then forms the linear predictor

```python
logit = intercept
    + w_amount * log(amount + 1)
    + w_mrisk * merch_risk
    + w_crisk * card_risk
    + w_night * (hour < 6)
```

where `w_amount`, `w_mrisk`, `w_crisk`, and `w_night` are tunable weights defaulting to 0.8, 2.0, 1.5, and 0.5 respectively .  Applying the logistic sigmoid (`expit`) yields a probability vector `p`, and a fresh NumPy `default_rng(seed)` conducts a Bernoulli trial for each row, producing an initial Boolean mask `labels`.

### Enforcing the Exact Fraud Count

After the initial draw, `label_fraud` computes the target fraud count as `round(fr * N)` and compares it to the number of positives in `labels`.  If the draw **overshoots**, it identifies the indices of all `True` labels, then uses `rng.choice` to randomly pick and flip off the surplus, preserving fairness.  If the draw **undershoots**, the function enters a burst-clustering routine to add exactly the needed number of fraud labels (`remaining`) in a way that reflects merchant-centric fraud waves .

**Burst-Clustering Undershoot Corrections**

To build burst waves, the code first determines `num_waves = max(1, remaining // burst_factor)`, where `burst_factor` (default 10) controls how many frauds occur per wave.  It samples `wave_times` uniformly from the set of event-time nanoseconds and selects corresponding `wave_merch` merchant IDs by weighting each unique merchant by its `merch_risk`.  For each `(wt, wm)` anchor, it constructs a mask of all transactions from merchant `wm` that occurred within ±`burst_window_s` seconds (default 1,800 s) of `wt` and that remain unlabeled .

If at least `burst_factor` candidates exist, it randomly labels exactly that many.  If fewer are available, it labels them all, then immediately fills the per-wave shortfall by sampling from the global pool of yet-unlabeled transactions, with probabilities proportional to the product of `merch_risk * card_risk`.  This two-step ensures that each wave both clusters fraud around risky merchants and maintains the exact per-wave size.

### Final Global Fallback and Return

After processing all waves, if there remain any unlabeled transactions but still fewer than the target count, `label_fraud` performs one last global draw on the remaining deficit, again weighting by combined entity risk.  At this point, exactly `round(fr * N)` labels have been flipped to `True`.  Finally, the function attaches the completed `labels` array back onto the original Polars DataFrame as a Boolean `label_fraud` column and returns the augmented DataFrame for subsequent schema casting and output .

---

## 5. Post-processing & Delivery
### Schema Enforcement and Column Casting

After fraud labels have been applied, the generator transitions into post-processing by enforcing the official transaction schema defined in `schema/transaction_schema.yaml`. Inside `core.generate_dataframe()`, the module loads this YAML at import time (via `_SCHEMA_PATH = Path("schema/transaction_schema.yaml")`) and builds two key structures: the ordered list of column names `_COLUMNS` and the Polars dtype map `_POLARS_SCHEMA` that associates each column with its target `pl.DataType` . Once the full, labeled DataFrame is available—whether produced by concatenating multiple chunks or a single `_generate_chunk` call—the code invokes

```python
df = df.with_columns([
    pl.col(col).cast(_POLARS_SCHEMA[col]) for col in _COLUMNS
]).select(_COLUMNS)
```

This two-step pipeline first casts every column to its precise type (for example, `event_time` to `pl.Datetime(ns, UTC)`, `amount` to `pl.Float64`, and `label_fraud` to `pl.Boolean`) and then reorders the columns into the exact sequence required by downstream consumers and the schema . Any mismatch—such as a missing column or invalid cast—will trigger a Polars error immediately, safeguarding schema compliance.

### Local Parquet Output

With schema conformance ensured, control returns to the CLI layer in `cli.py:main()`. The script computes a partitioned output path based on the current date:

1. It captures today’s date via `date.today()`, extracting `year` and zero-padded `month`.
2. It constructs the filename as

   ```python
   filename = f"payments_{cfg.total_rows:_}_{today.isoformat()}.parquet"
   ```

   embedding both the total row count and ISO-formatted date.
3. It then assembles the directory

   ```python
   local_dir = cfg.out_dir / "payments" / f"year={year}" / f"month={month}"
   ```

   ensuring consistency with partitioned data lakes.

Calling the helper `write_parquet(df, local_dir / filename)` creates all necessary parent directories, writes the DataFrame with Snappy compression, and returns the final `Path` to the file . A log entry immediately follows:

> `INFO: Written local file: /path/to/out_dir/payments/year=2025/month=07/payments_1_000_000_2025-07-10.parquet`

### Optional S3 Upload and Artifact Delivery

If the CLI flag `--s3` or the configuration parameter `s3_upload` is set, the generator proceeds to upload both the transaction Parquet and, in “v2” mode, the prebuilt catalog Parquets. Using `boto3.client("s3")`, it retrieves parameterized bucket names from the parameter store (`get_param("/fraud/raw_bucket_name")` and, if applicable, `"/fraud/artifacts_bucket_name"`).

For the transactions file, the S3 key mirrors the local partition structure:

```python
key = f"payments/year={year}/month={month}/{filename}"
s3.upload_file(str(local_path), bucket, key)
```

Each upload is accompanied by informative logs:

> `INFO: Uploading to S3: s3://<bucket>/payments/year=2025/month=07/payments_...`
> `INFO: Upload complete: s3://<bucket>/payments/...`

In “v2” realism, the directory `cfg.out_dir / "catalog"` is globbed for `*.parquet`, and each file (e.g. `customers.parquet`, `merchants.parquet`, `cards.parquet`) is uploaded under the `catalogues/` prefix to the artifacts bucket, preserving file names and ensuring that the risk priors and Zipf-distribution artifacts are available for audit or repeated runs .

### Error Handling and Exit Codes

All post-processing steps are wrapped in a `try`/`except` in `cli.py:main()`. An `ClientError` during S3 operations is caught explicitly, logged as an “S3 upload failed,” and leads to `sys.exit(2)`. Any other uncaught exception—whether from disk I/O, schema casting, or boto3 configuration—is logged with a full stack trace and results in `sys.exit(1)`. This clear division of exit codes ensures that orchestrators (e.g., CI/CD pipelines or Airflow) can distinguish between configuration issues, upload failures, and unexpected runtime errors.
