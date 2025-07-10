# High Level ASCII Diagram of the Synthetic Data Generator
```{text}
                            ┌───────────────────────────┐
                            │    CLI / Entry Point      │
                            │  generate.py  (main())    │
                            └────────────┬──────────────┘
                                         │
                                         ▼
                        ┌──────────────────────────────────────┐
                        │ TransactionSimulator.__init__        │
                        │ • Load schema YAML (schema/…)        │
                        │ • Seed Faker & random                │
                        │ • Configure rates (fraud, nulls…)    │
                        └────────────────┬─────────────────────┘
                                         │
                                         ▼
                        ┌───────────────────────────────────────┐
                        │   Loop: generate_to_parquet()         │
                        │ • Calculate total_chunks              │
                        │ • For each chunk:                     │
                        │   ┌────────────────────────────────┐  │
                        │   │ 1. _generate_one_row()         │  │
                        │   │    – Faker / random timestamps │  │
                        │   │    – card, geo, MCC_CODES      │  │
                        │   └────────────┬───────────────────┘  │
                        │                │                      │
                        │                ▼                      │
                        │   ┌────────────────────────────────┐  │
                        │   │ 2. Build Polars DataFrame      │  │
                        │   │    – schema_overrides SCHEMA   │  │
                        │   │    – enforce column order      │  │
                        │   └────────────┬───────────────────┘  │
                        │                │                      │
                        │                ▼                      │
                        │   ┌────────────────────────────────┐  │
                        │   │ 3. Convert to Arrow Table      │  │
                        │   └────────────┬───────────────────┘  │
                        │                │                      │
                        │                ▼                      │
                        │   ┌────────────────────────────────┐  │
                        │   │ 4. ParquetWriter.write_table() │  │
                        │   │    – Snappy compression        │  │
                        │   └────────────────────────────────┘  │
                        └────────────────┬──────────────────────┘
                                         │
                                         ▼
                        ┌────────────────────────────────────────┐
                        │  Final Parquet file in outputs/        │
                        │  (payments_{rows}_{YYYY-MM-DD}.parquet)│
                        └────────────────┬───────────────────────┘
                                         │
                       [ if “--s3 yes” ] │
                                         ▼
                        ┌────────────────────────────────────────┐
                        │   upload_to_s3(file, bucket)           │
                        │ • Read raw_bucket_name via param       │
                        │ • boto3.upload_file → s3://…           │
                        └────────────────────────────────────────┘
```

**Key pieces:**

1. **CLI / Entry Point**
   `generate.py` parses args (`--rows`, `--out`, `--s3`) and kicks off `TransactionSimulator`.&#x20;

2. **Schema Loading**
   Reads `schema/transaction_schema.yaml` once to extract column order and data types.&#x20;

3. **Row Generation**
   `_generate_one_row()` uses Faker (seeded for reproducibility), random uniform sampling for timestamps, and a static list of MCC codes (`mcc_codes.py`).&#x20;

4. **Chunked Write**
   Batches of rows (default 100 000) are converted to a Polars DataFrame with the exact schema, then to a PyArrow Table, and written via a `ParquetWriter` with Snappy compression.&#x20;

5. **Optional S3 Upload**
   If requested, uses `boto3` to upload the final parquet under a date-partitioned key, retrieving the bucket name from AWS Parameter Store. .

This flow ensures constant RAM usage, reproducibility, schema conformity, and easy downstream consumption of daily synthetic payment streams.

## 1. CLI/Entry Point

```text
┌────────────────────────────────────────────────────────────────┐
│ CLI Invocation                                                 │
│ poetry run python -m fraud_detection.simulator.generate        │
│     --rows 1_000_000                                           │
│     --out outputs/                                             │
│     --s3 yes                                                   │
└───────────────┬────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│ def main() → argparse setup                                      │
│ • parser = ArgumentParser(...)                                   │
│ • parser.add_argument("--rows", type=int, default=1_000_000)     │
│ • parser.add_argument("--out", type=Path, default="outputs")     │
│ • parser.add_argument("--s3", choices=["yes","no"], default="no")│
│ • args = parser.parse_args()                                     │
└───────────────┬──────────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────────┐
│ simulator = TransactionSimulator(                              │
│     total_rows=args.rows, out_dir=args.out                     │
│ )                                                              │
└───────────────┬────────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────────┐
│ parquet_path = simulator.generate_to_parquet()                 │
│ • Streams chunks into Snappy-compressed Parquet                │
│ • Enforces schema order via YAML                               │ 
└───────────────┬────────────────────────────────────────────────┘
                │
      args.s3 == "yes"? ──► Yes ──┐
                                  ▼
                       ┌──────────────────────────────────────────────┐
                       │ bucket = get_param("/fraud/raw_bucket_name") │
                       │ simulator.upload_to_s3(parquet_path, bucket) │
                       └──────────────────────────────────────────────┘
```

## 2. Schema Loading
```text
┌────────────────────────────────────────────────────────────┐
│  Input from #1: CLI / Entry Point                          │
├────────────────────────────────────────────────────────────┤
│  • total_rows       (int)           – e.g. 1_000_000       │
│  • out_dir          (Path)          – e.g. "outputs/"      │
│  • chunk_size       (int, default 100_000)                 │
│  • fraud_rate       (float, default 0.003)                 │
│  • null_mcc_rate    (float, default 0.05)                  │
│  • null_device_rate (float, default 0.08)                  │
│  • null_geo_rate    (float, default 0.01)                  │
│  • timezone_offset  (int, minutes, default –60)            │
└────────────────────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────┐
│  Module-Level Initialization (on import)                   │
├────────────────────────────────────────────────────────────┤
│  • Read & parse “schema/transaction_schema.yaml”           │
│    → SCHEMA dict                                           │
│  • Extract COLUMNS list (field order)                      │
│  • Map YAML dtypes → Polars DataTypes → SCHEMA_POLARS      │
│  • Seed random & Faker (seed=42) for reproducibility       │
│  • Load MCC_CODES list from mcc_codes module               │
└────────────────────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────┐
│  TransactionSimulator.__init__(                            │
│      total_rows, out_dir, chunk_size, fraud_rate,          │
│      null_mcc_rate, null_device_rate, null_geo_rate,       │
│      timezone_offset                                       │
│  )                                                         │
├────────────────────────────────────────────────────────────┤
│  • Assign each parameter to self (self.total_rows, etc.)   │
│  • Record reference “now” timestamp                        │
│    self._now_ts = time.time()                              │
└────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│  Output to #3: Ready TransactionSimulator instance          │
│  • Holds: configuration params, schema metadata,            │
│    seeded Faker/random, MCC_CODES, reference timestamp      │
│  → Next step: call simulator.generate_to_parquet()          │
└─────────────────────────────────────────────────────────────┘
```

## 3. Row Generation

```text
┌──────────────────────────────────────────────────────────────┐
│ #3: generate_to_parquet()                                    │
├──────────────────────────────────────────────────────────────┤
│ Input from #2: TransactionSimulator instance                 │
│  • total_rows (e.g. 1_000_000)                               │
│  • out_dir (e.g. "outputs/")                                 │
│  • chunk_size, fraud_rate, null_mcc_rate, null_device_rate,  │
│    null_geo_rate, timezone_offset                            │
│  • Schema metadata:                                          │
│      – COLUMNS list (column order)                           │
│      – SCHEMA_POLARS (Polars/Arrow dtypes)                   │
│  • Seeded Faker/random, MCC_CODES list, reference timestamp  │
├──────────────────────────────────────────────────────────────┤
│ Inside generate_to_parquet():                                │
│ 1. total_chunks = ceil(total_rows / chunk_size)              │
│ 2. writer = ParquetWriter(schema=SCHEMA_POLARS,              │
│       compression='snappy')                                  │
│ 3. For each chunk_index in range(total_chunks):              │
│                                                              │
│    ┌─────────────────────────────────────────────────────┐   │
│    │ a) rows_in_chunk = min(chunk_size,                  │   │
│    │    remaining rows)                                  │   │
│    │ b) rows_list = []                                   │   │
│    │ c) For i in range(rows_in_chunk):                   │   │
│    │    • row = self._generate_one_row()                 │   │
│    │        – timestamp, uuid, amount, card, geo, etc.   │   │
│    │    • inject nulls (MCC, device, geo) based on rates │   │
│    │    • set is_fraud flag based on fraud_rate          │   │
│    │    • rows_list.append(row)                          │   │
│    └─────────────────────────────────────────────────────┘   │
│                                                              │
│    ┌─────────────────────────────────────────────────────┐   │
│    │ d) df = pl.DataFrame(rows_list)                     │   │
│    │ e) enforce column order & cast to SCHEMA_POLARS     │   │
│    └─────────────────────────────────────────────────────┘   │
│                                                              │
│    ┌─────────────────────────────────────────────────────┐   │
│    │ f) table = df.to_arrow()                            │   │
│    │ g) writer.write_table(table)                        │   │
│    └─────────────────────────────────────────────────────┘   │
│                                                              │
│ 4. writer.close()                                            │
│ 5. output_path = out_dir /                                   │
│    f"payments_{total_rows}_{YYYY-MM-DD}.parquet"             │
│ 6. return output_path                                        │
└──────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────┐
│ Output to #4:                                                │
│  • Path to the single, Snappy-compressed Parquet file        │
└──────────────────────────────────────────────────────────────┘
```

## 4. Chunked Write

```text
┌──────────────────────────────────────────────────────────────┐
│ #4: Finalize Parquet File                                    │
├──────────────────────────────────────────────────────────────┤
│ Input from #3:                                               │
│  • ParquetWriter with open file handle                       │
│  • out_dir (Path for outputs)                                │
│  • total_rows, date_str (YYYY-MM-DD)                         │
├──────────────────────────────────────────────────────────────┤
│ Inside finalize step:                                        │
│ 1. writer.close()                                            │
│    – flushes all buffered RowGroups to disk                  │
│ 2. Ensure out_dir exists                                     │
│    – mkdir(parents=True, exist_ok=True)                      │
│ 3. Construct filename                                        │
│    – payments_{total_rows}_{date_str}.parquet                │
│ 4. Resolve output_path                                       │
│    – out_dir / filename                                      │
│ 5. Log or print:                                             │
│    – “Parquet file written to {output_path}”                 │
│ 6. return output_path                                        │
└──────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────┐
│ Output to #5:                                                │
│  • output_path (Path to generated Parquet file)              │
│  → Used by CLI driver to decide on optional S3 upload        │
└──────────────────────────────────────────────────────────────┘
```

## 5. Optional S3 Upload
```text
┌──────────────────────────────────────────────────────────────┐
│ #5: Optional S3 Upload                                       │
├──────────────────────────────────────────────────────────────┤
│ Input from #4:                                               │
│  • output_path (Path) – local Parquet file path              │
│  • args.s3 == "yes"                                          │
└──────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────┐
│ upload_to_s3(file_path: Path, bucket_name: str)              │
├──────────────────────────────────────────────────────────────┤
│ 1. Retrieve bucket name via AWS SSM Parameter Store:         │
│     ssm = boto3.client("ssm")                                │
│     param = ssm.get_parameter(Name="/fraud/raw_bucket_name") │
│     bucket_name = param["Parameter"]["Value"]                │
│ 2. Create S3 client:                                         │
│     s3 = boto3.client("s3")                                  │
│ 3. Determine S3 key (object path):                           │
│     – today = datetime.date.today()                          │
│     – key = f"payments/year={today.year}/month={today:%m}""  │
                "/{file_path.name}"                            │
│ 4. s3.upload_file(                                           │
│       Filename=str(output_path),                             │
│       Bucket=bucket_name,                                    │
│       Key=key                                                │
│   )                                                          │
│ 5. Print or log success:                                     │
│     “Uploaded to s3://{bucket_name}/{key}”                   │
└──────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────┐
│ Output to CLI / User:                                        │
│  • s3_uri = “s3://{bucket_name}/{key}”                       │
│  → End of data-generation pipeline                           │
└──────────────────────────────────────────────────────────────┘

```

# Explanation of Key-pieces
## 1. CLI / Entry Point
### Script Entry and Guard Clause

Execution begins when the user invokes the `generate.py` script from the command line. At the top of the module, a standard Python guard:

```python
if __name__ == "__main__":
    main()
```

ensures that the `main()` function is called only when the file is run as a script (rather than being imported). This guard hands control immediately to `main()`, encapsulating all of the CLI orchestration in one entry-point function.

---

### Argument Parsing and Validation

Inside `main()`, the script constructs an `argparse.ArgumentParser` to formalize its command-line interface. As soon as the parser is created, each supported option is declared with a call to `add_argument()`. Typical parameters include:

* `--rows`: total number of synthetic transactions to generate (an integer).
* `--chunk-size`: number of rows to process per write operation.
* `--schema`: path to the transaction schema file.
* `--output-dir`: directory into which Parquet files will be written.
* `--s3`: a flag (`yes`/`no`) indicating whether to upload the result to S3.

When `parser.parse_args()` returns, the script has a fully validated `args` namespace. Any missing or mistyped options trigger an immediate, user-friendly error message and usage summary.

---

### Instantiating the Transaction Simulator

With parsed arguments in hand, `main()` next creates an instance of the `TransactionSimulator` class. The constructor signature aligns directly with the CLI options:

```python
simulator = TransactionSimulator(
    total_rows=args.rows,
    chunk_size=args.chunk_size,
    schema_path=args.schema,
    output_path=args.output_dir,
    # ... any date filters or seeding arguments as provided
)
```

By mapping each CLI argument to a corresponding parameter, the script centralizes all configuration in one object. Internally, the simulator seeds its random number generators, loads and validates the schema definition, and readies any optional behavior (such as null-value injection or fraud-rate configuration).

---

### Triggering Data Generation

Immediately after instantiation, `main()` invokes:

```python
output_file = simulator.generate_to_parquet()
```

This single method call kicks off the entire data-generation pipeline. Under the hood, it:

1. **Calculates** how many chunks are needed based on `total_rows` and `chunk_size`.
2. **Iterates** through each chunk, calling `_generate_one_row()` to synthesize individual records.
3. **Batches** rows into a Polars DataFrame, applies schema enforcement, converts it to a PyArrow Table, and writes via a `ParquetWriter` with Snappy compression.
4. **Returns** the final Parquet file path upon completion.

By capturing `output_file`, the CLI retains full control for any post-processing steps.

---

### Optional S3 Upload

The last step in `main()` examines the `--s3` argument. If the user specified `yes`, the script proceeds to:

```python
simulator.upload_to_s3(output_file)
```

This method retrieves the target bucket name (for example, from AWS SSM Parameter Store), composes an S3 key—often incorporating the generation date—and uses `boto3` to perform an upload. Success or failure is logged to the console, and the script then exits cleanly.

---

Through this structured flow—from guard clause to argument parsing, through simulator instantiation and execution, ending with an optional S3 push—`generate.py` provides a clear, repeatable, and configurable interface for producing synthetic transaction data.



## 2. Schema Loading
### Initializing the Schema Path and Global Generators

Before any data is produced, the module defines a constant pointing to the YAML file that describes the transaction schema. At import time, `SCHEMA_YAML` is set to a `pathlib.Path` object targeting `schema/transaction_schema.yaml`. Simultaneously, global instances of the Faker and random generators are seeded—ensuring reproducibility across runs—by invoking `faker.seed_instance(42)` and `random.seed(42)`. This setup guarantees that both the schema definition and the randomness source are immutable throughout the process .

### Reading and Parsing the YAML Schema

Immediately after seeding, the code loads the entire schema into memory by calling:

```python
SCHEMA = yaml.safe_load(SCHEMA_YAML.read_text())
```

Here, `yaml.safe_load` parses the YAML content into a native Python dictionary. This dictionary is expected to contain, at minimum, a top-level key `"fields"` whose value is a list of field-definition mappings. Reading and parsing occur only once—upon module import—so subsequent operations can rely on the in-memory `SCHEMA` without re-reading the file .

### Extracting and Ordering Column Names

With the parsed schema in hand, the next step is to derive a definitive column order. A list comprehension iterates over each field dictionary in `SCHEMA["fields"]`, pulling out the value under the `"name"` key. The resulting list, assigned to `COLUMNS`, serves two purposes: it preserves the intended column ordering from the YAML, and it drives the final DataFrame’s column selection, ensuring every output file adheres exactly to the prescribed schema order .

### Mapping YAML Types to Polars DataTypes

YAML schemas typically express data types in human-readable form (e.g., `"int"`, `"string"`, `"datetime"`). To enforce these types at write time, the code defines a mapping `_DTYPES` that associates each YAML-style dtype string with a corresponding Polars data-type instance (for example, `"int"` → `Int64()`, `"datetime"` → `Datetime("ns", "UTC")`). Immediately afterward, a dictionary comprehension constructs `SCHEMA_POLARS` by iterating over the same `SCHEMA["fields"]` list, mapping each field’s `"name"` to the appropriate Polars type via `_DTYPES`. Fields whose `"dtype"` is unrecognized default to `Utf8()` (nullable string). This two-stage mapping guarantees that every column in every chunk is cast to the exact type the downstream Parquet writer expects .

---

By front-loading schema loading and type mapping in this fashion, the generator ensures that all subsequent data-generation steps—row synthesis, DataFrame assembly, and Parquet serialization—operate against a single, authoritative schema definition. This design minimizes I/O overhead and enforces strict type and order conformance across the entire synthetic dataset.



## 3. Row Generation

Each synthetic transaction is crafted by the private method `_generate_one_row(now_ts: float)`, which the main loop invokes once per record to produce a Python dictionary representing the event. This function is optimized for throughput—avoiding expensive object instantiation on every call—and proceeds through a fixed sequence of steps to populate all required fields .

### Generating the Transaction Timestamp

The method begins by selecting a random point within the past 30 days. It subtracts a uniformly sampled offset (up to 30 × 24 × 3600 seconds) from the reference timestamp `now_ts`, then converts that result into a timezone-aware UTC `datetime` via `datetime.datetime.fromtimestamp(...)`. The resulting `ts` value serves as the canonical `event_time` for the transaction .

### Synthesizing Customer and Card Details

Next, a unique `user_id` is drawn with `faker.random_int(10_000, 999_999)`. A dummy credit-card number, generated by `faker.credit_card_number()`, is hashed using `hashlib.sha256(...).hexdigest()` to produce `card_pan_hash`, ensuring the raw PAN never persists. Together, these values anchor the transaction to a single customer and payment instrument .

### Determining Merchant, Channel, and POS Information

The merchant category code (`mcc_code`) is assigned by choosing randomly from the global `MCC_CODES` list, unless a draw from `random.random()` falls below the configured `null_mcc_rate`, in which case it is set to `None`. The transaction `channel` is selected from the tuple `("ONLINE", "IN_STORE", "ATM")`, and the point-of-sale entry mode (`pos_entry_mode`) is sampled from `("CHIP", "MAGSTRIPE", "NFC", "ECOM")`. These fields collectively describe how and where the purchase occurred .

### Populating Geolocation and Device Attributes

Location and device metadata enrich ONLINE transactions in particular. Latitude and longitude are each generated via `faker.latitude()` and `faker.longitude()`, rounded to six decimal places, with a small fraction intentionally left null (per `null_geo_rate`). A `device_id` is minted via `faker.uuid4()` unless omitted by `null_device_rate`. If the channel is `"ONLINE"`, an IPv4 address and a user-agent string are also assigned; otherwise, these fields remain `None` .

### Assigning Transaction Amount and Fraud Label

The monetary `amount` is drawn uniformly between 1.00 and 500.00 and rounded to two decimal places. A boolean `label_fraud` flag is set to `True` whenever a uniform random draw falls below the configured `fraud_rate`, injecting controlled noise to simulate fraudulent activity .

### Assembling the Event Record

Finally, all generated values—alongside additional fields such as a UUID‐based `transaction_id`, `currency_code`, randomized card scheme and expiration, merchant identifiers, `is_recurring`, and a placeholder `previous_txn_id`—are packaged into a single dictionary. This dictionary conforms exactly to the YAML-defined schema and is returned for inclusion in the current chunk of records .



## 4. Chunked Write
### Preparing the Output File and Directory

When `generate_to_parquet()` is invoked, it first determines today’s date via `datetime.date.today().isoformat()` and uses this to construct a filename of the form `payments_{total_rows}_{YYYY-MM-DD}.parquet`. It then resolves the full output path by joining this filename with the configured `out_dir`, creating the directory hierarchy if it does not already exist (`self.out_dir.mkdir(parents=True, exist_ok=True)`). This ensures that, no matter how deeply nested the target folder is, the Parquet file will be written to a valid location without additional user intervention .

### Determining the Chunking Strategy

To manage memory usage, the method computes how many chunks will be required by dividing the total number of rows (`self.total_rows`) by the user-specified `chunk_size` and rounding up via `math.ceil`. At the same time, it initializes two control variables: `rows_remaining` (initialized to the full row count) and a monotonically increasing `chunk_index`. A timestamp of `start_time` is captured to facilitate progress logging and elapsed‐time calculations. These variables drive the subsequent while‐loop that processes one chunk at a time .

### Iterative Chunk Processing

The core of the method is a `while rows_remaining > 0` loop that performs five tightly coupled steps on each iteration. First, it computes `current_chunk_size` as the lesser of `chunk_size` and `rows_remaining`, ensuring the final batch may be smaller. Next, it calls the private generator `_generate_one_row(self._now_ts)` in a list comprehension—repeated `current_chunk_size` times—to produce a list of Python dictionaries, each representing a synthetic transaction. These dictionaries are then passed to `polars.from_dicts(..., schema_overrides=SCHEMA_POLARS)` to create a Polars DataFrame that already enforces the precise dtypes defined in the loaded schema. Finally, `.select(COLUMNS)` reorders the columns exactly as specified in the YAML, guaranteeing consistent layout across all chunks .

### ParquetWriter Initialization and Append

Once the DataFrame for the current chunk is assembled, `df_chunk.to_arrow()` converts it into a PyArrow Table. On the very first chunk, `parquet_writer` is still `None`, so the code instantiates a new `pq.ParquetWriter`, passing in the output path, the Arrow schema, and compression settings (Snappy with modern timestamp handling). For every subsequent chunk—whether the second, tenth, or final—the same `ParquetWriter` instance is reused, appending each Arrow Table to the single Parquet file via `parquet_writer.write_table(arrow_table)`. This streaming write pattern ensures the process never holds more than one chunk’s worth of data in memory at once .

### Resource Cleanup and Completion

After each chunk is written, `rows_remaining` is decremented by `current_chunk_size`, and a log entry records the chunk number, rows processed, rows left, and elapsed time since `start_time`. To help the garbage collector, the temporary list of dictionaries is explicitly deleted (`del chunk_dicts`) before the next iteration. Once all rows have been handled and the loop exits, the code checks if the `ParquetWriter` is non-null; if so, it calls `parquet_writer.close()` to flush and finalize the file footer. A final log statement then reports the total duration and absolute path of the completed Parquet file, which the method returns to its caller .



## 5. Optional S3 Upload
### Invoking the S3 Upload from the CLI

Once the Parquet file has been successfully written, `main()` inspects the user-supplied `--s3` flag. If it equals `"yes"`, the script must determine the target S3 bucket before handing off to the simulator instance. To do so, it calls:

```python
bucket_name = get_param("/fraud/raw_bucket_name")
```

Behind the scenes, `get_param()` (from `fraud_detection.utils.param_store`) queries AWS Systems Manager Parameter Store for the value of `raw_bucket_name`. If no value is returned, the script logs an error and exits with a non-zero status, preventing any unintended behavior .

Having obtained a valid bucket name, `main()` then issues:

```python
simulator.upload_to_s3(parquet_path, bucket_name)
```

This single call delegates the responsibility for key construction, upload, and logging to the `TransactionSimulator` class.

---

### Constructing the Date-Partitioned S3 Key

Inside `TransactionSimulator.upload_to_s3(file_path: pathlib.Path, bucket: str)`, the method first captures today’s date via `datetime.date.today()`. It then formats an S3 key that embeds year and month partitions:

```python
today = datetime.date.today()
key = f"payments/year={today.year}/month={today:%m}/{file_path.name}"
```

For example, if today is May 31, 2025 and the local file is named `payments_1000000_2025-05-31.parquet`, the key becomes
`s3://{bucket}/payments/year=2025/month=05/payments_1000000_2025-05-31.parquet` .

---

### Performing the Upload with Boto3

With the fully qualified S3 URI components in hand, the method logs its intent to the console:

```python
logger.info(f"Uploading {file_path} to s3://{bucket}/{key} …")
```

It then obtains an S3 client via `boto3.client("s3")` and calls `upload_file()`, passing the local file path, target bucket, and the computed key:

```python
boto3.client("s3").upload_file(str(file_path), bucket, key)
```

Under the hood, `upload_file()` handles multipart transfer for large files, retries on transient errors, and streams the file data to S3 without loading it entirely into memory .

---

### Final Confirmation and Exit

Upon successful completion of the upload, the method records a final log entry:

```python
logger.info(f"Upload complete → s3://{bucket}/{key}")
```

Control then returns to `main()`, which exits cleanly. At this point, the user has both a local copy of the Parquet file and a mirror in S3 organized by year and month, ready for downstream ETL or analytics jobs. This optional, flag-driven design keeps the core data-generation logic separate from deployment concerns, while still offering seamless integration with AWS storage.
