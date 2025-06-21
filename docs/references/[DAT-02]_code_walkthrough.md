# Main Code Walkthrough
> Refer to `docs/references/[DAT-02]_code_init_refactor.md`

Below is a guided walkthrough of the refactored **`generate.py`** file. I’ll go through it in logical sections—essentially “line by line” in the sense of each import, constant, class, and function—explaining:

* **What** each statement or block is doing in Python,
* **Why** it’s there (especially in the context of building a production-grade synthetic-data pipeline for fraud detection),
* **How** each library (Polars, PyArrow, Faker, Mimesis, YAML, boto3, logging, etc.) fits into the big picture.

Throughout, I’ll speak as though you’re a mid-level engineer being mentored by a senior MLOps/Data Scientist: clear enough for a “noob” to follow, yet grounded in industry best practices so you could confidently describe it in an interview.

---

## 1. Module-Level Docstring

```python
"""
generate.py
───────────
Create synthetic payment events that conform to schema/transaction_schema.yaml.

CLI
---
    poetry run python -m fraud_detection.simulator.generate \
        --rows 1_000_000 \
        --out outputs/ \
        --s3 yes

• Streams data in 100k-row chunks (constant RAM) to a single Snappy‐compressed Parquet.  
• Column order is enforced via the YAML schema.  
• Optionally uploads to S3 bucket defined in environment variable RAW_BUCKET.
"""
```

1. **Purpose**: This multiline string at the very top is a “module docstring.” It serves two main functions:

   * **Self-documentation**: Anyone opening `generate.py` immediately sees what this file is responsible for—namely, generating synthetic payments according to a schema, writing them in Parquet format, and (optionally) uploading to S3.
   * **CLI Instructions**: Under “CLI,” you see an example command. This shows how a user would run this script from the command line using `python -m fraud_detection.simulator.generate`.
2. **Why It Matters**: In a production repository, it’s standard to include a clear docstring explaining:

   * What the file does at a high level,
   * How to invoke the main functionality,
   * Any special constraints (e.g., chunking, compression, required environment variables).

Without this, someone new to the code (or a future you, six months from now) would have to read every line just to understand “What am I supposed to run here?”

---

## 2. Future Imports & Standard Library Imports

```python
from __future__ import annotations
```

1. **What It Does**: This line enables **“postponed evaluation of type hints”**. In Python 3.7+, when you write type hints (e.g. `def foo(x: MyClass) -> MyClass:`), those annotations are evaluated at function-definition time by default. The `from __future__ import annotations` directive makes all type hints be stored as **strings** internally, deferring their evaluation until later (e.g., during static analysis or at runtime if you call `get_type_hints()`).
2. **Why It Matters**:

   * **Avoids circular imports**: If one part of your package imports a class for a type hint, you won’t inadvertently force Python to import that module immediately.
   * **Performance**: Defer the cost of type hint evaluation to runtime only if needed.
   * **Cleaner**: You can reference classes that are defined “later” in the file without wrapping them in quotes manually.
3. **Context**: Since our `TransactionSimulator` is typed (e.g., constructor returns `-> None`, methods return typed values), it’s good practice in an industry codebase to use this future import to keep annotations clean.

```python
import argparse
import datetime
import logging
import math
import os
import pathlib
import random
import time
import uuid
from typing import Dict, List, Optional
```

Here are why each of these standard-library imports is included:

* **`argparse`**

  * **What**: A built-in Python module for parsing command-line arguments (flags, options, positional args).
  * **Why**: We want users (or CI/CD pipelines) to be able to call `python -m fraud_detection.simulator.generate --rows 500_000 --out outputs --s3 yes` without editing the code. `argparse` handles the parsing, validation, and help messages for us automatically.

* **`datetime`**

  * **What**: Provides `date`, `datetime`, and `timezone` classes.
  * **Why**: Our synthetic transactions need realistic timestamps. We randomly pick a point in the last 30 days (using `datetime.datetime`) and attach a UTC timezone. Also, for naming the output file, we embed today’s date (`datetime.date.today().isoformat()`).

* **`logging`**

  * **What**: The standard Python logging library, which lets you write `logger.info`, `logger.error`, etc., instead of doing bare `print()` statements.
  * **Why**: In production code, you want structured, configurable logs that can be redirected to files, cloud log-aggregators, or have different verbosity levels. This sets us up in case we later want to hook into CloudWatch, ELK, or Splunk.

* **`math`**

  * **What**: Provides basic mathematical functions.
  * **Why**: We use `math.ceil()` to figure out how many chunks we’ll need (e.g., if `total_rows=1_000_000` and `chunk_size=100_000`, `math.ceil(1_000_000/100_000) => 10`).

* **`os`**

  * **What**: Interacts with the operating system environment.
  * **Why**: When uploading to S3, we check `os.environ.get("RAW_BUCKET")` to see if the user set the `RAW_BUCKET` environment variable. This is how we know which bucket to write to.

* **`pathlib`**

  * **What**: A modern, object-oriented way to handle filesystem paths (`Path` instead of raw strings).
  * **Why**: We want to build pathnames in a cross-platform way (macOS/Linux/Windows). For example, `pathlib.Path("outputs") / filename` ensures correct path separators. We also call `.mkdir(parents=True, exist_ok=True)` to create directories if they don’t exist.

* **`random`**

  * **What**: Python’s pseudo-random number generator.
  * **Why**: We need to decide—on each transaction—whether the transaction is fraudulent (`random.random() < fraud_rate`), whether the MCC field is null (`random.random() > null_mcc_rate`), and so on. We seed it (`random.seed(42)`) so our synthetic data is repeatable; a CEO might appreciate that “if I run tomorrow, I get the same rows so I can compare apples to apples.”

* **`time`**

  * **What**: Gives access to timestamps (`time.time()`) in seconds since the Unix epoch.
  * **Why**: In the constructor, we capture a single “now” (e.g., `self._now_ts = time.time()`). We then generate each transaction’s timestamp by subtracting a random uniform offset (up to 30 days in seconds). This ensures every row is generated relative to exactly the same “reference now.” We also use `time.time()` to measure how long it takes to write each chunk.

* **`uuid`**

  * **What**: Generate universally unique identifiers.
  * **Why**: Each transaction needs a `transaction_id` that’s globally unique. We use `uuid.uuid4().hex`, which is a random 128-bit UUID represented as a 32-character hexadecimal string. In real fraud systems, you want each event to have a stable unique key.

* **`typing.Dict, List, Optional`**

  * **What**: Type annotations for dictionaries, lists, and optional values.
  * **Why**: We annotate methods like `_generate_one_row(self, now_ts: float) -> Dict[str, object]` so any future reader (or automated type checker like mypy) knows we expect a dictionary mapping strings to arbitrary objects. `Optional[int]` is shorthand for “`int` or `None`.”

---

## 3. Third-Party Imports

```python
import boto3
import botocore
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from faker import Faker
from mimesis import Business
```

Here’s what each external library brings to the table, and *why* it’s used:

1. **`boto3` and `botocore`**

   * **`boto3`** is AWS’s official Python SDK. You use it to create clients for AWS services—in our case, S3.
   * **`botocore`** is under the hood of `boto3` and gives you lower-level configuration options. We specifically grab `botocore.client.Config(signature_version="s3v4")` to ensure we use the latest S3 signature version.
   * **Why**: Once we have a generated Parquet file on disk, we want the option to upload it directly to an S3 bucket. In fraud-detection pipelines, your synthetic data might feed downstream ETL jobs or model training jobs that reside in AWS.

2. **`polars as pl`**

   * **What**: Polars is a DataFrame library (Rust-backed) that is extremely fast, especially for writing Parquet or Arrow data. Underneath, Polars uses Apache Arrow’s columnar format.
   * **Why**: Compared to Pandas, Polars can operate on large data much more memory-efficiently. Because we want to generate up to 1 million or more rows, and then write them to Parquet, we do not want to hold a huge in-memory Pandas DataFrame. Polars also has very convenient conversions to/from PyArrow tables (`df.to_arrow()`)—crucial when streaming to a `ParquetWriter`.

3. **`pyarrow as pa` & `pyarrow.parquet as pq`**

   * **What**: PyArrow is the official Python interface to Apache Arrow. Its `pyarrow.parquet` submodule gives you low-level control over writing Parquet files, including streaming writes (`ParquetWriter`).
   * **Why**: We want to avoid “build a giant DataFrame and call `write_parquet` once” because that can blow up memory in a “write-once” scenario. Instead, we open `ParquetWriter(out_path, schema, compression="snappy")` *once* and then, for each chunk, call `.write_table(arrow_table)`. This way:

     1. Each chunk is freed immediately after writing.
     2. We never materialize 1 million rows in a single in-memory table.
     3. We still get a single final Parquet file with one uniform schema.

4. **`yaml`**

   * **What**: A YAML-parsing library (`PyYAML`).
   * **Why**: We have a separate schema file at `config/transaction_schema.yaml` that defines the column names, types, and order. By loading this YAML once (with `yaml.safe_load(...)`) and extracting `fields → name`, we ensure that *every* chunk of generated data has exactly the same column ordering. In production, having a single source of truth for your schema—decoupled from code—means if you ever adjust the schema, you only change the YAML, not every piece of code that builds a DataFrame.

5. **`from faker import Faker`**

   * **What**: Faker is a widely-used Python library for generating fake—but realistic—personal data (names, addresses, credit cards, IPs, etc.).
   * **Why**: To simulate transactions, you need random `credit_card_number()`, `ipv4_public()`, `user_agent()`, and so on. Faker gives us realistic (yet dummy) data so if we ever train a model—or demo to a colleague—it looks “real.” We seed Faker with `faker.seed_instance(42)` to make the results repeatable.

6. **`from mimesis import Business`**

   * **What**: Mimesis is another synthetic data library, focused on “entities” like businesses, passports, etc.
   * **Why**: We use `Business().mcc()` to generate realistic Merchant Category Codes (MCC). In fraud detection, the MCC often influences risk (e.g., “gas station” vs. “online gambling”). By leveraging Mimesis, we can generate a plausible 4-digit MCC for each merchant.
   * **Note**: We choose Mimesis for business-specific attributes because Faker’s MCCs are either nonexistent or too simplistic. Mimesis has a built-in `Business.mcc()` that returns a valid MCC code (e.g., 5411 for “grocery stores”) as a string. We cast it to `int`.

---

## 4. Logging Configuration

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
```

1. **`logging.basicConfig(...)`**

   * **What**: Sets up a default logging configuration for the entire module.
   * **Parameters**:

     * `level=logging.INFO`: Only logs with level INFO or above will be emitted. (DEBUG messages will be ignored unless you lower the level later.)
     * `format="%(asctime)s %(levelname)s: %(message)s"`: Defines how each log line looks, e.g. `2025-05-31 14:23:45 INFO: Beginning simulation...`
     * `datefmt="%Y-%m-%d %H:%M:%S"`: Custom format for the timestamp.
   * **Why**: Instead of sprinkling `print(...)` everywhere, using `logger.info(...)` or `logger.error(...)` is standard because:

     * You can easily switch between console vs. file vs. external log systems.
     * You can change log levels (e.g., to DEBUG) in one place without touching all the code.

2. **`logger = logging.getLogger(__name__)`**

   * **What**: Grabs a logger with the module’s name (e.g., `fraud_detection.simulator.generate`).
   * **Why**: If you import this module elsewhere or integrate into a larger application, you can configure logging per module. For instance, you could set `"fraud_detection.simulator.generate": "DEBUG"` in a YAML config or command-line flag. It also helps identify which file emitted a log in multi-module apps.

---

## 5. Constants & Global Generator Instances

```python
SCHEMA_YAML = pathlib.Path("schema/transaction_schema.yaml")
faker = Faker()
business = Business()
random.seed(42)
faker.seed_instance(42)
```

1. **`SCHEMA_YAML`**

   * **What**: A `pathlib.Path` object pointing to our YAML file.
   * **Why**: We will later read this file to figure out what columns our synthetic data must have, and in what order. By defining it as a `Path`, the code is cross-platform: if you ever run this on Windows, `Path("config/transaction_schema.yaml")` still works.

2. **`faker = Faker()`**

   * **What**: Instantiates a single Faker generator.
   * **Why**: We keep a single global instance so we’re not recreating a new Faker object on every row. That saves a tiny bit of CPU overhead, and also preserves the random seed.

3. **`business = Business()`**

   * **What**: Instantiates Mimesis’s Business provider.
   * **Why**: Just like Faker, we only need one global instance. We’ll call `business.mcc()` every time we need a merchant category code.

4. **`random.seed(42)` and `faker.seed_instance(42)`**

   * **What**: Both Python’s built-in RNG (`random`) and Faker’s own RNG are seeded with the same integer.
   * **Why**: This ensures that if you run:

     ```bash
     python -m fraud_detection.simulator.generate --rows 100 --out outputs
     ```

     you’ll always get the same 100 rows. Repeatability makes it easier to debug (if someone says “In run #1, I saw a fraud rate of 0.23%; in run #2 I saw 0.31%—something’s off!”). With a fixed seed, you know the randomness is deterministic.

---

## 6. Load & Parse the YAML Schema

```python
SCHEMA = yaml.safe_load(SCHEMA_YAML.read_text())
COLUMNS: List[str] = [field_dict["name"] for field_dict in SCHEMA["fields"]]
```

1. **`SCHEMA_YAML.read_text()`**

   * **What**: Reads the entire contents of the YAML file (`config/transaction_schema.yaml`) into a Python string.
   * **Why**: We need to parse it. It typically looks something like:

     ```yaml
     fields:
       - name: transaction_id
         type: string
       - name: event_time
         type: timestamp
       - name: local_time_offset
         type: integer
       # … and so on for every column …
     ```
   * If you ever add a new field to your schema or change an existing one, you do it in this YAML, and the Python code “automatically” picks it up.

2. **`yaml.safe_load(...)`**

   * **What**: Parses the YAML string into a Python dictionary. `safe_load` avoids executing arbitrary code embedded in YAML (which is a security best practice).
   * **Why**: We then have `SCHEMA` as a nested dictionary, e.g.:

     ```python
     {
       "fields": [
         {"name": "transaction_id", "type": "string"},
         {"name": "event_time", "type": "timestamp"},
         # …
       ]
     }
     ```

3. **`COLUMNS = [field_dict["name"] for field_dict in SCHEMA["fields"]]`**

   * **What**: Builds a Python list of column names in exactly the same order as they appear in the YAML.
   * **Why**: Later, after we build a Polars DataFrame from a list of dictionaries, we’ll call `df.select(COLUMNS)` to reorder (and potentially drop any extra keys). By keeping column order in a single place (the YAML), we avoid “magic numbers” or mismatched schemas. If your schema changes, you only need to update `config/transaction_schema.yaml`; no need to hunt through the code for `.with_columns([...])` or `.select([...])`.

---

## 7. The `TransactionSimulator` Class

Everything from here on is encapsulated in a single class called `TransactionSimulator`. This is idiomatic in production code: group related functionality (generate, write, upload) into one reusable object. If you ever want to write unit tests, you can instantiate `TransactionSimulator` with a small `total_rows` (say, 1\_000) and `chunk_size=100`, then call its methods directly.

```python
class TransactionSimulator:
    """
    Encapsulates all logic for generating a synthetic payments dataset
    and writing it to a single Parquet file (in Snappy compression),
    chunk by chunk.
    """
```

1. **Docstring**: Explains exactly what happens when you use this class.

   * You “generate a synthetic payments dataset,”
   * “write it to Parquet” with Snappy compression,
   * and do so in chunks so that your RAM usage never spikes.
2. **Why a Class?**

   * **Grouping state**: The constructor (`__init__`) will set properties like `total_rows`, `fraud_rate`, etc., so you don’t have to pass them around to multiple functions.
   * **Testability**: You can write `sim = TransactionSimulator(total_rows=1000, chunk_size=250)` and then `assert sim._generate_one_row(...)` returns a dict with exactly the right keys. Or test that `sim.generate_to_parquet()` actually writes the right number of rows.

---

### 7.1. The Constructor (`__init__`)

```python
    def __init__(
        self,
        total_rows: int,
        out_dir: pathlib.Path,
        chunk_size: int = 100_000,
        fraud_rate: float = 0.003,
        null_mcc_rate: float = 0.05,
        null_device_rate: float = 0.08,
        null_geo_rate: float = 0.01,
        timezone_offset: int = -60,
    ) -> None:
        """
        Args:
            total_rows: Number of rows to generate in total.
            out_dir: Directory into which the final Parquet file will be written.
            chunk_size: How many rows to buffer per batch before writing.
            fraud_rate: Probability any given transaction is labeled fraudulent.
            null_mcc_rate: Fraction of rows where mcc_code is set to None.
            null_device_rate: Fraction of rows with no device_id.
            null_geo_rate: Fraction of rows with no latitude/longitude.
            timezone_offset: Value for "local_time_offset" column (in minutes).
        """
        self.total_rows = total_rows
        self.out_dir = out_dir
        self.chunk_size = chunk_size
        self.fraud_rate = fraud_rate
        self.null_mcc_rate = null_mcc_rate
        self.null_device_rate = null_device_rate
        self.null_geo_rate = null_geo_rate
        self.timezone_offset = timezone_offset

        # Capture a single "now" timestamp so all rows are relative to the same reference.
        self._now_ts = time.time()
```

#### Line-by-Line Explanation

1. **`def __init__(...) -> None:`**

   * This is the constructor. When you do `TransactionSimulator(1_000_000, pathlib.Path("outputs"))`, Python calls this method to set up internal state.
   * The return annotation `-> None` just tells readers (and type checkers) that `__init__` doesn’t return anything.

2. **`total_rows: int`**

   * **What**: A required positional argument, e.g. `1_000_000`.
   * **Why**: The generator needs to know how many synthetic transactions to produce in total.

3. **`out_dir: pathlib.Path`**

   * **What**: A required positional argument, e.g. `pathlib.Path("outputs")`.
   * **Why**: We need to know where on disk to write `payments_1_000_000_2025-05-31.parquet`. Later, `self.out_dir.mkdir(parents=True, exist_ok=True)` will ensure the directory exists.

4. **`chunk_size: int = 100_000`**

   * **Default**: 100 000 rows per chunk.
   * **Why**: We do not want to hold 1 million rows in memory. We generate 100 000 rows, convert them to a Polars DataFrame, write them via a PyArrow `ParquetWriter`, then discard them from memory. This keeps peak RAM usage low.

5. **`fraud_rate: float = 0.003`**

   * **Default**: 0.3% of transactions flagged as fraudulent.
   * **Why**: A realistic fraud rate is often in the tenths of a percent. Embedding a parameter here means you can simulate “how does my model perform if fraud is 1%?” by changing `fraud_rate=0.01`.

6. **`null_mcc_rate`, `null_device_rate`, `null_geo_rate`**

   * **Purpose**: Real production payment streams often have missing fields.

     * Sometimes MCC is missing (e.g., a boutique merchant not in the standard Maharishi list).
     * Sometimes device IDs fail to be captured.
     * Sometimes geolocation is not available (e.g., offline ATM).
   * **Why**: By parameterizing these percentages, you can test how downstream code handles nulls. A model that assumes “mcc never null” might break if 5% are missing.

7. **`timezone_offset: int = -60`**

   * **What**: A fixed integer (in minutes) indicating the local time offset from UTC (e.g., `-60` means UTC–1).
   * **Why**: The schema likely has a column called `local_time_offset` so that, downstream, your fraud model can reconstruct local time from the UTC `event_time`. We pick a default of –60 minutes so generated data looks like it’s from a European time zone.

8. **Storing Everything on `self`**

   * **What**: Lines like `self.total_rows = total_rows` store each parameter as an instance attribute.
   * **Why**: Inside methods like `_generate_one_row()` or `generate_to_parquet()`, we need to refer back to these settings: “What fraction of rows should be fraud?” → `self.fraud_rate`. This is standard object-oriented design: keep state on the instance.

9. **`self._now_ts = time.time()`**

   * **What**: Captures the exact “now” (in seconds since epoch) when the constructor is called.
   * **Why**: All synthetic events should be distributed in the range `[ now - 30 days, now ]`. By capturing `now` once, you ensure every chunk of 100k rows is generated relative to the same reference point. If we instead called `time.time()` in each chunk, the “now” might drift by a few seconds or minutes as the generator runs.

---

### 7.2. The `_generate_one_row` Method

```python
    def _generate_one_row(self, now_ts: float) -> Dict[str, object]:
        """
        Generate a single synthetic payment event dictionary.
        We intentionally keep this lean: avoid re-creating Faker()/Mimesis() instances on every call.
        """
        # 1. Randomize a transaction timestamp between (now - 30 days) and now:
        ts = datetime.datetime.utcfromtimestamp(now_ts - random.uniform(0, 30 * 24 * 3600))
        ts = ts.replace(tzinfo=datetime.timezone.utc)

        # 2. Customer and card information:
        user_id = faker.random_int(10_000, 999_999)
        raw_card_number = faker.credit_card_number()  # e.g. "4242 4242 4242 4242"
        card_pan_hash = faker.sha256(raw_card_number)

        # 3. Merchant / business info:
        mcc: Optional[int] = int(business.mcc()) if random.random() > self.null_mcc_rate else None
        channel = faker.random_element(("ONLINE", "IN_STORE", "ATM"))

        # 4. Geolocation & device fields:
        latitude = (
            round(faker.latitude(), 6) if random.random() > self.null_geo_rate else None
        )
        longitude = (
            round(faker.longitude(), 6) if random.random() > self.null_geo_rate else None
        )
        device_id = faker.uuid4() if random.random() > self.null_device_rate else None
        ip_address = faker.ipv4_public() if channel == "ONLINE" else None
        user_agent = faker.user_agent() if channel == "ONLINE" else None

        # 5. Transaction amount & labeling:
        amount = round(random.uniform(1.0, 500.0), 2)
        is_fraud = random.random() < self.fraud_rate

        return {
            "transaction_id": uuid.uuid4().hex,
            "event_time": ts,
            "local_time_offset": self.timezone_offset,
            "amount": amount,
            "currency_code": faker.currency_code(),
            "card_pan_hash": card_pan_hash,
            "card_scheme": faker.random_element(("VISA", "MASTERCARD", "AMEX", "DISCOVER")),
            "card_exp_year": faker.random_int(2026, 2030),
            "card_exp_month": faker.random_int(1, 12),
            "customer_id": user_id,
            "merchant_id": faker.random_int(1000, 9999),
            "merchant_country": faker.country_code(representation="alpha-2"),
            "mcc_code": mcc,
            "channel": channel,
            "pos_entry_mode": faker.random_element(("CHIP", "MAGSTRIPE", "NFC", "ECOM")),
            "device_id": device_id,
            "device_type": faker.random_element(("IOS", "ANDROID", "WEB", "POS")),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "latitude": latitude,
            "longitude": longitude,
            "is_recurring": faker.boolean(chance_of_getting_true=10),
            "previous_txn_id": None,
            "label_fraud": is_fraud,
        }
```

#### Overall Purpose

* This method generates **one** dictionary representing a single payment event.
* It never writes to disk or DataFrames directly; it only returns a plain `dict[str, object]`.
* By keeping it “lean”—not instantiating `Faker()` or `Business()` each call—we minimize overhead. This method may be called 100 000 times per chunk, so creating a new Faker inside the loop would be wasteful.

#### Step-by-Step

1. **Signature**:

   ```python
   def _generate_one_row(self, now_ts: float) -> Dict[str, object]:
   ```

   * `now_ts: float` is the timestamp (in seconds) that was captured in the constructor.
   * We return a dictionary mapping column names (strings) to their values (ints, floats, `datetime`, or `None`). Polymorphism is okay here because when we convert to a DataFrame, we’ll let Polars infer types or we’ll explicitly cast.

2. **Docstring**:

   * Explains “We intentionally keep this lean: avoid re-creating Faker()/Mimesis() instances on every call.”
   * That’s because instantiating those providers is a little expensive compared to calling their methods repeatedly on an existing instance.

---

##### 2.1. Generating the Timestamp

```python
ts = datetime.datetime.utcfromtimestamp(now_ts - random.uniform(0, 30 * 24 * 3600))
ts = ts.replace(tzinfo=datetime.timezone.utc)
```

* **`random.uniform(0, 30 * 24 * 3600)`**

  * **What**: Picks a random float between `0` and `30 * 24 * 3600` (i.e., 30 days in seconds).
  * **Why**: We want each transaction’s event time to be uniformly distributed over the last 30 days relative to `now_ts`.

* **`now_ts - that_uniform_value`**

  * **What**: Subtracts a random offset from “now.”
  * **Why**: If `now_ts` is today at 12:00 UTC, subtracting 7 days in seconds would give you a timestamp exactly 7 days ago at 12:00 UTC. By using `random.uniform`, we get any second in the past 30 days.

* **`datetime.datetime.utcfromtimestamp(...)`**

  * **What**: Converts a POSIX timestamp (seconds since epoch) into a naive `datetime` object in UTC.
  * **Why**: We want a Python `datetime` so Polars knows this is a timestamp column later.

* **`ts.replace(tzinfo=datetime.timezone.utc)`**

  * **What**: Takes that naive `datetime` and explicitly tags it as UTC.
  * **Why**: Downstream systems often need a timezone-aware timestamp. Otherwise, some libraries interpret naive datetimes as “local time,” which can lead to confusion or incorrect conversions.

---

##### 2.2. Customer & Card Information

```python
user_id = faker.random_int(10_000, 999_999)
raw_card_number = faker.credit_card_number()  # e.g. "4242 4242 4242 4242"
card_pan_hash = faker.sha256(raw_card_number)
```

* **`user_id = faker.random_int(10_000, 999_999)`**

  * **What**: Picks a random integer between 10 000 and 999 999 to simulate a customer ID.
  * **Why**: Real user IDs are often millions of integers; here we choose a smaller range for simplicity. You could easily switch to a broader range if you needed more realistic cardinality.

* **`raw_card_number = faker.credit_card_number()`**

  * **What**: Produces a fake credit card number as a string, like `"4242 4242 4242 4242"`.
  * **Why**: In real production, you would never store raw PANs. We only generate it so we can hash it, simulating how you’d store a tokenized or hashed PAN in a payments pipeline.

* **`card_pan_hash = faker.sha256(raw_card_number)`**

  * **What**: Hashes the fake credit card number using SHA-256, returning a 64-character hex string.
  * **Why**: That mimics the real practice: the payment platform has a hashed or tokenized version of the PAN. A fraud model might use that hash to lookup historical patterns without seeing raw data.

---

##### 2.3. Merchant / Business Information

```python
mcc: Optional[int] = int(business.mcc()) if random.random() > self.null_mcc_rate else None
channel = faker.random_element(("ONLINE", "IN_STORE", "ATM"))
```

* **`random.random() > self.null_mcc_rate`**

  * **What**: Returns a uniform float in `[0.0, 1.0)`. If it’s greater than `null_mcc_rate`, we actually generate an MCC; otherwise we set it to `None`.
  * **Why**: If `null_mcc_rate=0.05`, about 5% of transactions will have `mcc_code = None`. In real data, some merchants don’t report a valid MCC.

* **`int(business.mcc())`**

  * **What**: `business.mcc()` returns a string like `"5411"`. We cast it to `int` so the column is a numeric type.
  * **Why**: Polars will infer this column as an integer. If we left it as a string sometimes and `None` at other times, Polars would have to treat it as a generic object string field. But real analytics prefer typed columns (so you can do `df.groupby("mcc_code").agg(...)` efficiently).

* **`channel = faker.random_element(("ONLINE", "IN_STORE", "ATM"))`**

  * **What**: Picks one of the three strings with uniform probability.
  * **Why**: Real fraud data often distinguishes between “online” vs. “in-store” vs. “ATM” transactions. For “ONLINE,” you’ll later populate `ip_address` and `user_agent`; for the others, those will be `None`.

---

##### 2.4. Geolocation & Device Fields

```python
latitude = (
    round(faker.latitude(), 6) if random.random() > self.null_geo_rate else None
)
longitude = (
    round(faker.longitude(), 6) if random.random() > self.null_geo_rate else None
)
device_id = faker.uuid4() if random.random() > self.null_device_rate else None
ip_address = faker.ipv4_public() if channel == "ONLINE" else None
user_agent = faker.user_agent() if channel == "ONLINE" else None
```

1. **Latitude / Longitude**

   * **`faker.latitude()`** and **`faker.longitude()`** each return a random floating-point coordinate (e.g., 51.509865, –0.118092).
   * We do `round(..., 6)` to limit it to six decimal places—typical for GPS coordinates (sub-meter precision).
   * We only populate these if `random.random() > self.null_geo_rate`; otherwise, we set them to `None`. If `null_geo_rate=0.01`, \~1% of transactions have no geolocation (e.g., the merchant device didn’t capture a GPS).
   * **Production Context**: Fraud models often look for “mismatched locations” (e.g., a transaction in London following one in New York minutes earlier). Having `None` mimics cases where location data is missing.

2. **Device ID**

   * **`faker.uuid4()`** generates a random UUID to simulate the device’s unique ID (e.g., GUID for a mobile app).
   * We only assign it if `random.random() > self.null_device_rate`; otherwise, `device_id = None`. Some transactions—say, an ATM withdrawal—might not have a device-side footprint.

3. **`ip_address` and `user_agent`**

   * Both only apply if `channel == "ONLINE"`. If the transaction is in-store or at an ATM, we set these to `None`.
   * **Why**: Online transactions have an IP and a User-Agent string (desktop vs. mobile vs. bot). These fields are highly useful features in fraud modeling. By keeping them `None` when `channel != "ONLINE"`, you accurately mimic real patterns.

---

##### 2.5. Transaction Amount & Fraud Label

```python
amount = round(random.uniform(1.0, 500.0), 2)
is_fraud = random.random() < self.fraud_rate
```

1. **`amount = round(random.uniform(1.0, 500.0), 2)`**

   * **What**: Picks a float uniformly between \$1.00 and \$500.00, then rounds to two decimals.
   * **Why**: Most ecommerce or retail transactions fall in that dollar range. You could easily extend this to `random.gammavariate(...)` or a log-normal distribution if you wanted more realistic “heavy tail” on transaction amount. But uniform is a simple start.

2. **`is_fraud = random.random() < self.fraud_rate`**

   * **What**: If `fraud_rate=0.003` (0.3%), then there’s a 0.3% chance this transaction is flagged fraud.
   * **Why**: Models need both positive and negative examples. We store this as a boolean and later cast it to an integer or keep it as a bool in Parquet. Downstream code might do `df.filter(df.label_fraud == True)` to look at only fraudulent records.

---

##### 2.6. Returning the Dictionary

```python
return {
    "transaction_id": uuid.uuid4().hex,
    "event_time": ts,
    "local_time_offset": self.timezone_offset,
    "amount": amount,
    "currency_code": faker.currency_code(),
    "card_pan_hash": card_pan_hash,
    "card_scheme": faker.random_element(("VISA", "MASTERCARD", "AMEX", "DISCOVER")),
    "card_exp_year": faker.random_int(2026, 2030),
    "card_exp_month": faker.random_int(1, 12),
    "customer_id": user_id,
    "merchant_id": faker.random_int(1000, 9999),
    "merchant_country": faker.country_code(representation="alpha-2"),
    "mcc_code": mcc,
    "channel": channel,
    "pos_entry_mode": faker.random_element(("CHIP", "MAGSTRIPE", "NFC", "ECOM")),
    "device_id": device_id,
    "device_type": faker.random_element(("IOS", "ANDROID", "WEB", "POS")),
    "ip_address": ip_address,
    "user_agent": user_agent,
    "latitude": latitude,
    "longitude": longitude,
    "is_recurring": faker.boolean(chance_of_getting_true=10),
    "previous_txn_id": None,
    "label_fraud": is_fraud,
}
```

Let’s unpack each key/value:

1. **`"transaction_id": uuid.uuid4().hex`**

   * **Why**: A unique identifier for each transaction. We use `uuid4()` (random) and call `.hex` to get a 32-character hex representation (no dashes). In production, transaction IDs might come from downstream systems; here we fake them.

2. **`"event_time": ts`**

   * **Why**: The timestamp we generated above, which is timezone-aware in UTC. This will become a Polars `Datetime("ns", "UTC")` later (when we do `schema_overrides={"event_time": pl.Datetime("ns", "UTC")}`).

3. **`"local_time_offset": self.timezone_offset`**

   * **Why**: A constant offset (–60) representing that local currency is UTC–1. In a real dataset, you might vary this by merchant country. For now, we keep it simple.

4. **`"amount": amount`**

   * Random float with two decimals from above.

5. **`"currency_code": faker.currency_code()`**

   * **What**: Randomly picks a three-letter ISO currency code (e.g., “USD,” “EUR,” “GBP”).
   * **Why**: If you train models on multi-currency data, having a `currency_code` column is essential so you can either one-hot-encode it or convert to a baseline currency.

6. **`"card_pan_hash": card_pan_hash`**

   * Hashed PAN from earlier.

7. **`"card_scheme": faker.random_element(("VISA", "MASTERCARD", "AMEX", "DISCOVER"))`**

   * **What**: Randomly chooses a card brand.
   * **Why**: Different card networks may have different fraud characteristics. Having this column means a model can learn, for instance, that AMEX fraud rates are historically higher.

8. **`"card_exp_year": faker.random_int(2026, 2030)`** and **`"card_exp_month": faker.random_int(1, 12)`**

   * **Why**: Faking an expiration year/month so you can simulate “expired card” logic if needed. For now, these are random and not necessarily coherent (e.g., you could generate a month/year combination that’s already in the past), but that might be fine if your downstream code just stores it.

9. **`"customer_id": user_id`**

   * The random integer from earlier.

10. **`"merchant_id": faker.random_int(1000, 9999)`**

    * **Why**: Creates a 4-digit merchant ID. In reality, merchant IDs are often longer, but this is enough to partition data by `merchant_id`, do group-by-counts, etc.

11. **`"merchant_country": faker.country_code(representation="alpha-2")`**

    * **What**: Two-letter country codes like “US,” “GB,” “DE,” etc.
    * **Why**: If you want to simulate cross-border transactions, downstream code might look for “merchant\_country != customer\_country” as a fraud indicator.

12. **`"mcc_code": mcc`**

    * The MCC from earlier, possibly `None`.

13. **`"channel": channel`**

    * “ONLINE,” “IN\_STORE,” or “ATM.”

14. **`"pos_entry_mode": faker.random_element(("CHIP", "MAGSTRIPE", "NFC", "ECOM"))`**

    * **Why**: Indicates how the card was read—“CHIP” if the customer inserted their EMV chip card; “MAGSTRIPE” if the stripe was swiped; “NFC” if contactless tap; “ECOM” for online. Models often treat “ECOM” differently (higher risk).

15. **`"device_id": device_id`** and **`"device_type": faker.random_element(("IOS", "ANDROID", "WEB", "POS"))`**

    * We only set `device_id` if `random.random() > null_device_rate`.
    * `device_type` is uniformly random among four categories. In production, “POS” might correlate to in-store (where IP is `None`), while “WEB,” “IOS,” “ANDROID” often correlate with “ONLINE.”

16. **`"ip_address": ip_address`** and **`"user_agent": user_agent`**

    * Only set if `channel == "ONLINE"`; otherwise, they are None.

17. **`"latitude": latitude`, `"longitude": longitude`**

    * Possibly `None`.

18. **`"is_recurring": faker.boolean(chance_of_getting_true=10)`**

    * **What**: With a 10% chance, sets `is_recurring=True`, else `False`.
    * **Why**: Some transactions come from recurring subscriptions (e.g., Netflix bill). Recurring transactions often have a different fraud profile.

19. **`"previous_txn_id": None`**

    * Always `None` in this spike. In a more advanced simulator, you might link some transactions together to simulate “card-present chain” or “merchant chain,” but for now we leave it blank.

20. **`"label_fraud": is_fraud`**

    * Boolean that tells downstream models “this is fraud” vs. “legit.”
    * Some pipelines prefer `0/1` instead of `False/True`; Polars will coerce `False` → `0` and `True` → `1` when writing to Parquet as an integer or boolean type.

---

### 7.3. The `generate_to_parquet` Method

```python
    def generate_to_parquet(self) -> pathlib.Path:
        """
        Streams the entire dataset into a single Parquet file, chunk by chunk.
        Returns the path to the written Parquet file.
        """
        # 1. Prepare output directory and final filename
        today_str = datetime.date.today().isoformat()
        filename = f"payments_{self.total_rows:_}_{today_str}.parquet"
        out_path = self.out_dir / filename
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # 2. We'll buffer `chunk_size` rows at a time, convert to Polars DF,
        #    then to PyArrow Table to write via ParquetWriter.
        parquet_writer: Optional[pq.ParquetWriter] = None
        rows_remaining = self.total_rows
        start_time = time.time()
        total_chunks = math.ceil(self.total_rows / self.chunk_size)

        logger.info(f"Beginning simulation: {self.total_rows:,} rows → {out_path}")
        logger.info(f"Chunk size: {self.chunk_size:,} rows ({total_chunks} total chunks)")

        chunk_index = 0
        while rows_remaining > 0:
            chunk_index += 1
            current_chunk_size = min(self.chunk_size, rows_remaining)

            # 2a. Generate a list of dicts for this chunk
            chunk_dicts: List[Dict[str, object]] = [
                self._generate_one_row(self._now_ts) for _ in range(current_chunk_size)
            ]

            # 2b. Build a Polars DataFrame with the correct schema/order
            df_chunk = pl.from_dicts(
                chunk_dicts, schema_overrides={"event_time": pl.Datetime("ns", "UTC")}
            ).select(COLUMNS)  # enforce column order exactly as in YAML

            # 2c. Convert to PyArrow table
            arrow_table = df_chunk.to_arrow()

            # 2d. Initialize or append to the ParquetWriter
            if parquet_writer is None:
                parquet_writer = pq.ParquetWriter(
                    out_path,
                    arrow_table.schema,
                    compression="snappy",
                    use_deprecated_int96_timestamps=False,
                )
            parquet_writer.write_table(arrow_table)

            # Cleanup for next chunk
            rows_remaining -= current_chunk_size
            elapsed = time.time() - start_time
            logger.info(
                f"Chunk {chunk_index}/{total_chunks} written "
                f"({current_chunk_size:,} rows). "
                f"{rows_remaining:,} rows left. Elapsed: {elapsed:0.2f}s"
            )

            # Let Python free the list memory
            del chunk_dicts

        # 3. Close the ParquetWriter
        if parquet_writer:
            parquet_writer.close()

        total_duration = time.time() - start_time
        logger.info(f"Completed: {self.total_rows:,} rows in {total_duration:0.2f}s → {out_path}")
        return out_path
```

#### Purpose

* This method loops until all `self.total_rows` are generated, writing them out in **batches of size `self.chunk_size`**.
* It returns the full path to the final Parquet file so callers know where to find it.

---

##### 3.1. Preparing Output Path & Filename

```python
today_str = datetime.date.today().isoformat()
filename = f"payments_{self.total_rows:_}_{today_str}.parquet"
out_path = self.out_dir / filename
self.out_dir.mkdir(parents=True, exist_ok=True)
```

1. **`today_str = datetime.date.today().isoformat()`**

   * **What**: Grabs the current date, e.g. `2025-05-31`, and turns it into the string `"2025-05-31"`.
   * **Why**: We often want the output file to include the date so that if you run this job daily, you end up with:

     ```
     payments_1000000_2025-05-31.parquet
     payments_1000000_2025-06-01.parquet
     ```

     This makes auditing and debugging easier (e.g., “Which day’s synthetic data am I looking at?”).

2. **`filename = f"payments_{self.total_rows:_}_{today_str}.parquet"`**

   * **`{self.total_rows:_}`** uses Python’s “underscore as thousands separator” feature. So if `total_rows=1000000`, the string becomes `"1_000_000"`.
   * **Concatenation**: You end up with `"payments_1_000_000_2025-05-31.parquet"`.
   * **Why**: Embedding `total_rows` in the filename makes it clear at a glance how many rows are in that dataset. If someone sees `payments_500_000_2025-05-31.parquet`, they know it’s a half-million-row file.

3. **`out_path = self.out_dir / filename`**

   * Joins the directory (e.g., `Path("outputs")`) with the filename.
   * If `self.out_dir` was `"outputs/"`, `out_path` becomes `Path("outputs/payments_1_000_000_2025-05-31.parquet")`.

4. **`self.out_dir.mkdir(parents=True, exist_ok=True)`**

   * **What**: Creates the directory (and any missing parent directories) if it doesn’t already exist.
   * **Why**: If you run this in a fresh clone of the repo, `outputs/` might not exist. We want to avoid a crash like “No such file or directory.” By doing this, we guarantee that `out_path.parent` is there.

---

##### 3.2. Initializing the Parquet Writer Loop

```python
parquet_writer: Optional[pq.ParquetWriter] = None
rows_remaining = self.total_rows
start_time = time.time()
total_chunks = math.ceil(self.total_rows / self.chunk_size)

logger.info(f"Beginning simulation: {self.total_rows:,} rows → {out_path}")
logger.info(f"Chunk size: {self.chunk_size:,} rows ({total_chunks} total chunks)")
```

1. **`parquet_writer: Optional[pq.ParquetWriter] = None`**

   * **What**: We declare a variable that will eventually hold an instance of `ParquetWriter`. Initially, it’s `None` because we haven’t yet created it.
   * **Why**: We can’t open the Parquet file until we know the schema (i.e., after writing the first chunk’s PyArrow table). That’s why we do a lazy initialization—on the first iteration of the loop, if `parquet_writer is None`, we create it with the right schema.

2. **`rows_remaining = self.total_rows`**

   * **Why**: A countdown for our loop. Each chunk we generate reduces `rows_remaining` by up to `chunk_size`.

3. **`start_time = time.time()`**

   * **Why**: We capture a timestamp so that after each chunk, we can log how long we’ve been running. In production, this is helpful for monitoring (e.g., “It took 12 seconds to write 500 000 rows. At this rate, we’ll finish a million in \~24 s.”).

4. **`total_chunks = math.ceil(self.total_rows / self.chunk_size)`**

   * **Why**: If `total_rows=1_000_000` and `chunk_size=100 000`, `math.ceil(1_000_000/100 000)` is exactly 10. If `total_rows=1_050 000`, it’s 11. This number is used purely for logging: “Chunk 3/11 written ...”

5. **`logger.info(...)`**

   * Output to console:

     ```
     2025-05-31 14:30:00 INFO: Beginning simulation: 1,000,000 rows → outputs/payments_1_000_000_2025-05-31.parquet
     2025-05-31 14:30:00 INFO: Chunk size: 100,000 rows (10 total chunks)
     ```
   * **Why**: Gives immediate feedback on what the script is about to do. If someone runs this in a dev environment, they see “Okay, I’m writing a million rows in 100k-row chunks.”

---

##### 3.3. The While-Loop (Chunked Generation)

```python
chunk_index = 0
while rows_remaining > 0:
    chunk_index += 1
    current_chunk_size = min(self.chunk_size, rows_remaining)
```

1. **`chunk_index = 0`**

   * We’ll increment this each loop so we can log “Chunk 1/10,” “Chunk 2/10,” etc.

2. **`while rows_remaining > 0:`**

   * We keep looping until we’ve generated all `total_rows`.
   * Inside, we decide how many rows to generate in this iteration:

     * If `rows_remaining >= chunk_size`, then `current_chunk_size = chunk_size`.
     * If `rows_remaining < chunk_size` (i.e., the last chunk), we generate only those leftover rows.

---

###### 3.3.1. Generating a List of Dicts

```python
chunk_dicts: List[Dict[str, object]] = [
    self._generate_one_row(self._now_ts) for _ in range(current_chunk_size)
]
```

1. **List Comprehension**

   * For each of `range(current_chunk_size)`, call `self._generate_one_row(self._now_ts)`.
   * If `current_chunk_size == 100_000`, this makes a list of 100 000 dictionaries, each with 24 fields (as defined earlier).
   * **Why**: We need a homogeneous structure to feed into Polars. Polars can accept a list of dictionaries and turn it into a DataFrame efficiently.

2. **Performance Note**

   * Although building a Python list of 100 k dicts is nontrivial, it’s still more memory-efficient than trying to hold 1 million rows at once. Once we convert these 100 k dicts to a Polars DataFrame (and then to a PyArrow Table), we immediately discard the Python list.

---

###### 3.3.2. Creating a Polars DataFrame with Correct Schema

```python
df_chunk = pl.from_dicts(
    chunk_dicts, schema_overrides={"event_time": pl.Datetime("ns", "UTC")}
).select(COLUMNS)  # enforce column order exactly as in YAML
```

1. **`pl.from_dicts(chunk_dicts, schema_overrides={"event_time": pl.Datetime("ns", "UTC")})`**

   * **What**: Polars inspects the list of dicts and creates a DataFrame.
   * **`schema_overrides`**: By default, Polars might infer a Python `datetime.datetime` as a generic “object” or an “int64” representing epoch. We explicitly tell it that `event_time` should be a Polars `Datetime` type in nanoseconds with UTC.
   * **Why**: Without this override, you might end up with inconsistent types (e.g., Polars can sometimes default to `Int64` for timestamps). Enforcing `Datetime("ns", "UTC")` ensures that when we write to Parquet, the column has the proper Arrow timestamp type.

2. **`.select(COLUMNS)`**

   * **What**: Reorders columns exactly as `COLUMNS` (the list we built from YAML). It also drops any extra keys that might have been in `chunk_dicts`.
   * **Why**: We want to guarantee that the final Parquet file has columns in exactly the order specified by `transaction_schema.yaml`. This is critical for downstream consumers (ETL jobs, BI dashboards) that expect a consistent column order. If tomorrow you add a new column in YAML at position 5, the `.select(COLUMNS)` ensures all existing code still works and sees the new column in the right place.

---

###### 3.3.3. Converting Polars to PyArrow Table

```python
arrow_table = df_chunk.to_arrow()
```

1. **`df_chunk.to_arrow()`**

   * **What**: Converts the Polars DataFrame into a PyArrow Table.
   * **Why**: `ParquetWriter` expects a PyArrow Table (not a Polars DataFrame). By going through Arrow, we maintain zero-copy for many columns (especially if they’re already Arrow buffers under the hood).
   * **Performance**: This is typically fast, because Polars is built on Arrow internally. So the conversion is mostly “pointer swapping,” not a deep copy.

---

###### 3.3.4. Initialize or Append to the ParquetWriter

```python
if parquet_writer is None:
    parquet_writer = pq.ParquetWriter(
        out_path,
        arrow_table.schema,
        compression="snappy",
        use_deprecated_int96_timestamps=False,
    )
parquet_writer.write_table(arrow_table)
```

1. **First Iteration (`parquet_writer is None`)**

   * **`pq.ParquetWriter(out_path, arrow_table.schema, compression="snappy", use_deprecated_int96_timestamps=False)`**

     * **`out_path`**: The final Parquet filename, e.g., `outputs/payments_1_000_000_2025-05-31.parquet`.
     * **`arrow_table.schema`**: We pass the schema of the first chunk’s table. That becomes the “official” schema for the entire Parquet file.
     * **`compression="snappy"`**: Commonly used in big data environments (e.g., AWS Athena, Spark) because Snappy is fast to compress and decompress.
     * **`use_deprecated_int96_timestamps=False`**: Modern Parquet readers prefer `TIMESTAMP (NANOS)`. This flag ensures we use the recommended representation rather than the older “INT96” style.
   * **Why**: We can’t create an empty `ParquetWriter` with no schema; we wait until we have a real Arrow Table (from the first chunk) and then capture its schema.

2. **Subsequent Iterations (`parquet_writer` already exists)**

   * We skip the initialization and directly call `parquet_writer.write_table(arrow_table)`.
   * **Why**: Each chunk is appended to the same physical Parquet file underneath. By the end of the loop, you have a single Parquet file containing all rows in a single row group per chunk (unless you specify row-group thresholds manually).

---

###### 3.3.5. Logging & Cleanup

```python
rows_remaining -= current_chunk_size
elapsed = time.time() - start_time
logger.info(
    f"Chunk {chunk_index}/{total_chunks} written "
    f"({current_chunk_size:,} rows). "
    f"{rows_remaining:,} rows left. Elapsed: {elapsed:0.2f}s"
)
del chunk_dicts
```

1. **`rows_remaining -= current_chunk_size`**

   * **What**: Subtract the number of rows we just wrote from the total. When this hits zero, we exit the while loop.

2. **`elapsed = time.time() - start_time`**

   * **Why**: Compute how many seconds have passed since we started the job. It’s helpful to log “Elapsed: 12.32 s” so you can estimate total runtime. If your system needs to finish within 30 s, you can check progress easily.

3. **`logger.info(...)`**

   * Outputs a line such as:

     ```
     2025-05-31 14:30:15 INFO: Chunk 3/10 written (100,000 rows). 700,000 rows left. Elapsed: 15.32s
     ```
   * **Why**: Provides feedback in real time. If a system is running this as part of a larger pipeline, you can tail the logs and verify progress.

4. **`del chunk_dicts`**

   * **What**: Deletes the Python list of dictionaries so that the memory can be freed.
   * **Why**: Although Python’s garbage collector would free it eventually, explicitly deleting that large list helps free up tens of megabytes right away. This reduces the chance your script hits an Out-Of-Memory error if you have many chunks or large chunk sizes.

---

##### 3.4. Closing the ParquetWriter & Final Log

```python
if parquet_writer:
    parquet_writer.close()

total_duration = time.time() - start_time
logger.info(f"Completed: {self.total_rows:,} rows in {total_duration:0.2f}s → {out_path}")
return out_path
```

1. **`if parquet_writer: parquet_writer.close()`**

   * **What**: Gracefully closes the file handle, writes any remaining metadata, flushes buffers.
   * **Why**: If you don’t close, the file may be incomplete or corrupted. It also ensures `_metadata` (column statistics, row count) is properly written at the end of the Parquet file.

2. **`total_duration = time.time() - start_time`**

   * **Why**: Measures the entire run time of `generate_to_parquet()`. If it took 24 seconds to write a million rows, you’ll know.

3. **`logger.info(...)`**

   * Example output:

     ```
     2025-05-31 14:30:24 INFO: Completed: 1,000,000 rows in 24.15s → outputs/payments_1_000_000_2025-05-31.parquet
     ```
   * **Why**: Confirms success and gives you a summary.

4. **`return out_path`**

   * **Why**: The caller of `generate_to_parquet()` (in this case, `main()`) receives the path to the Parquet file so it can decide “Do I upload this to S3? Do I feed it to another process?”

---

### 7.4. The `upload_to_s3` Method

```python
    def upload_to_s3(self, file_path: pathlib.Path, bucket: str) -> None:
        """
        Upload the given file to S3 under a date‐partitioned key.
        E.g.: s3://{bucket}/payments/year=2025/month=05/payments_1_000_000_2025-05-31.parquet
        """
        today = datetime.date.today()
        key = f"payments/year={today.year}/month={today:%m}/{file_path.name}"

        s3_client = boto3.client(
            "s3", config=botocore.client.Config(signature_version="s3v4")
        )
        logger.info(f"Uploading {file_path} to s3://{bucket}/{key} …")
        s3_client.upload_file(str(file_path), bucket, key)
        logger.info(f"Upload complete → s3://{bucket}/{key}")
```

#### Purpose

* After `generate_to_parquet()` returns a local `file_path`, this method takes that file and “pushes” it into an S3 bucket under a well-defined key.
* It uses “date partitions” (year and month) so that downstream systems (Athena, Glue, Redshift Spectrum, etc.) can discover data by partition pruning (e.g., only scan May 2025).

---

##### 4.1. Constructing the S3 Key

```python
today = datetime.date.today()
key = f"payments/year={today.year}/month={today:%m}/{file_path.name}"
```

1. **`today = datetime.date.today()`**

   * Grabs the local machine’s date. (We assume the machine’s timezone is set to UTC or Europe/London, but this only extracts the date portion.)

2. **`f"payments/year={today.year}/month={today:%m}/{file_path.name}"`**

   * If `today.year` is 2025 and `today:%m` is “05” (May), and `file_path.name` is `"payments_1_000_000_2025-05-31.parquet"`, the resulting key is:

     ```
     payments/year=2025/month=05/payments_1_000_000_2025-05-31.parquet
     ```
   * **Why**: Partitioned key structure is very common in data lakes. Athena or Glue can automatically discover partitions in S3 by these folder names. It also keeps your bucket tidy (all 2025 data is under `year=2025/`).

---

##### 4.2. Creating the S3 Client

```python
s3_client = boto3.client(
    "s3", config=botocore.client.Config(signature_version="s3v4")
)
```

1. **`boto3.client("s3")`**

   * **What**: Creates a low-level client for interacting with AWS S3. Under the hood, this uses your environment’s AWS credentials (e.g., instance role, `~/.aws/credentials`, or environment variables).
   * **`signature_version="s3v4"`**: Ensures we use AWS’s latest signing mechanism for S3 requests, which is typically required unless you’re using some very old region. It’s a best practice in production.

2. **Why We Don’t Use High-Level Resource API**

   * We pick the low-level client so we can call `upload_file(...)` directly. The resource API is slightly more “Pythonic” (`s3_resource.Bucket(bucket).upload_file(...)`), but the client approach is fine for a simple script.

---

##### 4.3. Performing the Upload & Logging

```python
logger.info(f"Uploading {file_path} to s3://{bucket}/{key} …")
s3_client.upload_file(str(file_path), bucket, key)
logger.info(f"Upload complete → s3://{bucket}/{key}")
```

1. **`logger.info("Uploading ...")`**

   * Logs something like:

     ```
     2025-05-31 14:31:00 INFO: Uploading outputs/payments_1_000_000_2025-05-31.parquet to s3://fraud-raw-prod/payments/year=2025/month=05/payments_1_000_000_2025-05-31.parquet …
     ```

2. **`s3_client.upload_file(str(file_path), bucket, key)`**

   * **`str(file_path)`**: Converts the `Path` object to a string path, e.g. `"/home/ubuntu/project/outputs/payments_1_000_000_2025-05-31.parquet"`.
   * **`bucket`**: The name of the S3 bucket, e.g. `"fraud-raw-prod"`.
   * **`key`**: The object key inside the bucket.
   * **Why**: This API method handles multipart uploads automatically if the file is large (>100 MB). It also retries on transient network errors. Using this built-in method is more robust than rolling your own HTTP calls.

3. **`logger.info("Upload complete …")`**

   * Confirms success. If there’s an error (permissions, network, no such bucket), Boto3 will raise an exception. You could catch it here and do more sophisticated retry logic, but for a simple spike, letting it bubble up is fine.

---

## 8. The `main()` Function (CLI Entry Point)

```python
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic payments and optionally upload to S3."
    )
    parser.add_argument(
        "--rows", type=int, default=1_000_000, help="Total number of rows to generate."
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("outputs"),
        help="Local directory to write the Parquet file.",
    )
    parser.add_argument(
        "--s3",
        choices=["yes", "no"],
        default="no",
        help="Whether to upload the final Parquet to S3 (requires RAW_BUCKET env var).",
    )

    args = parser.parse_args()

    simulator = TransactionSimulator(total_rows=args.rows, out_dir=args.out)
    parquet_path = simulator.generate_to_parquet()

    if args.s3 == "yes":
        bucket_name = os.environ.get("RAW_BUCKET")
        if not bucket_name:
            logger.error("Environment variable RAW_BUCKET not set. Aborting upload.")
            raise SystemExit(1)
        simulator.upload_to_s3(parquet_path, bucket_name)
```

### Line-by-Line Explanation

1. **`def main() -> None:`**

   * Defines a top-level function called `main`. In Python, by convention, this is the function you call if you run the script directly.
   * Return annotation `-> None` means it doesn’t return anything.

2. **`parser = argparse.ArgumentParser(...)`**

   * Creates a new argument parser. The `description` appears when you run `python -m fraud_detection.simulator.generate --help`.

3. **`parser.add_argument("--rows", type=int, default=1_000_000, help="Total number of rows to generate.")`**

   * Adds a `--rows` flag. If the user runs `--rows 500000`, `args.rows` will be `500000`. If they omit it, `args.rows` defaults to `1_000_000`.

4. **`parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("outputs"), help="Local directory to write the Parquet file.")`**

   * Adds a `--out` flag that’s parsed as a `pathlib.Path`. If the user says `--out my_data`, `args.out` becomes `Path("my_data")`.
   * Default is `Path("outputs")`.

5. **`parser.add_argument("--s3", choices=["yes", "no"], default="no", help="Whether to upload the final Parquet to S3 (requires RAW_BUCKET env var).")`**

   * Adds a `--s3` flag. The user can only type `yes` or `no`.
   * If they do `--s3 yes`, we’ll attempt to upload to S3. If `--s3 no` (or omit it), we skip upload.

6. **`args = parser.parse_args()`**

   * Reads `sys.argv` (the command-line arguments) and populates `args.rows`, `args.out`, and `args.s3` fields. If the user typed something invalid (e.g., `--rows foo`), `argparse` will print an error and show `--help` automatically.

7. **`simulator = TransactionSimulator(total_rows=args.rows, out_dir=args.out)`**

   * Instantiates the `TransactionSimulator` object, passing in the parsed values. Notice we didn’t pass `chunk_size`, `fraud_rate`, etc., so it uses the defaults (`100_000` chunk size, 0.3% fraud, etc.).

8. **`parquet_path = simulator.generate_to_parquet()`**

   * Calls our chunk-writing logic. When this finishes, the returned `parquet_path` is something like `Path("outputs/payments_1_000_000_2025-05-31.parquet")`.

9. **`if args.s3 == "yes":`**

   * Checks whether the user explicitly asked for an upload.
   * If they did:

   ```python
       bucket_name = os.environ.get("RAW_BUCKET")
       if not bucket_name:
           logger.error("Environment variable RAW_BUCKET not set. Aborting upload.")
           raise SystemExit(1)
       simulator.upload_to_s3(parquet_path, bucket_name)
   ```

   * **`bucket_name = os.environ.get("RAW_BUCKET")`**: We look up an environment variable called `RAW_BUCKET`. In a real environment, you might set `export RAW_BUCKET="fraud-raw-prod"`.
   * If that env var is missing, we log an error and exit with a nonzero status (`SystemExit(1)`). This explicitly fails the job, rather than trying to upload to an empty or incorrect bucket.
   * If `bucket_name` is present, we call `simulator.upload_to_s3(...)` with the local Parquet path and the bucket name.

---

## 9. The Script Entry Point

```python
if __name__ == "__main__":
    main()
```

1. **What**: This idiom checks “Is this file being run as the main script?” (i.e., `python generate.py` or `python -m fraud_detection.simulator.generate`). If so, call `main()`.
2. **Why**: If someone imports this module in another Python file (`import fraud_detection.simulator.generate`), you do *not* want it to immediately start generating data. You only want it to run when explicitly invoked as a script.

---

## 10. Putting It All Together

Once you drop this file into **`src/fraud_detection/simulator/generate.py`**, here’s how it looks in practice:

1. **Developer Workflow**

   * Fork or clone the repo.
   * `cd fraud-detection-system`
   * `poetry install` (installs dependencies from `pyproject.toml`: PyArrow, Polars, Faker, Mimesis, boto3, etc.)
   * `export RAW_BUCKET="my-bucket-name"` (only if you want to upload)
   * `poetry run python -m fraud_detection.simulator.generate --rows 200_000 --out test_outputs --s3 yes`

     * This spins up a `TransactionSimulator` with `total_rows=200_000`.
     * It writes `test_outputs/payments_200_000_<today’s date>.parquet` in four 50k-row chunks.
     * Then it uploads that Parquet to `s3://my-bucket-name/payments/year=2025/month=05/payments_200_000_<today’s date>.parquet`.
   * If you omit `--s3 yes`, it just writes locally.

2. **Why This Design Fits an Industry Task**

   * **Modularity**: All logic to generate, write, and upload is wrapped in `TransactionSimulator`. If you later want a “dry run” that only prints a few sample rows, you could add a `–dry-run` flag, or add a method `sample_rows(n)` returning a Pandas DataFrame.
   * **Testability**: You can write unit tests for:

     * `_generate_one_row()` → returns a dict with exactly the keys in `COLUMNS`.
     * `generate_to_parquet()` with `total_rows=1_000, chunk_size=500` → the output file has exactly 1\_000 rows, correct schema, etc.
     * `upload_to_s3()` → you can mock Boto3’s client to test that the right key is constructed.
   * **Observability**: The `logging` calls at INFO level let a DevOps pipeline parse logs to see how many chunks were written, how long it took, and if the upload succeeded. We’re not using `print()`, so we can raise the log level to WARNING or ERROR if we move to production.
   * **Scalability**: By streaming in chunks via `ParquetWriter`, this code can handle 10 million or 100 million rows on a beefy EC2 instance without blowing up RAM. If you tried to do “one big DataFrame” with Pandas, you’d quickly exceed 32 GB of memory.
   * **Flexibility**: Because we load `transaction_schema.yaml` dynamically, if tomorrow you add a `billing_address` or remove `previous_txn_id`, you only change the YAML, and Polars still builds a DataFrame with the correct columns.

---

## 11. How You’d Explain This to a Recruiter

If a recruiter asks, “Tell me about the code you wrote for the synthetic-data simulator,” you could say something like:

> “I designed a Python module called `generate.py` that creates realistic, fraud-labeled payment events in a memory-efficient, production-grade way. The script:
>
> 1. Loads a YAML schema (`transaction_schema.yaml`) to enforce column order and data types.
> 2. Uses Mimesis and Faker to generate realistic merchant category codes, credit card hashes, geolocation, device identifiers, and so on—while injecting controlled null rates (e.g., 5% MCC missing, 8% device missing).
> 3. Writes a user-specified number of rows (default 1 million) in 100 k-row chunks to a single Snappy-compressed Parquet file. We use Polars for fast DataFrame construction (via `pl.from_dicts`) and PyArrow’s `ParquetWriter` for chunked streaming to disk, which keeps RAM usage constant even for very large datasets.
> 4. Optionally—if the user passes `--s3 yes`—the script uploads the final Parquet artifact into a date-partitioned S3 key (for example, `s3://fraud-raw-<env>/payments/year=2025/month=05/...`). We use Boto3 with signature version v4 to ensure compatibility across AWS regions.
> 5. Everything is wrapped in a `TransactionSimulator` class so it’s modular and testable: you can unit-test `_generate_one_row()` in isolation or mock S3 calls when testing `upload_to_s3()`.
>
> By structuring it this way—chunked writing, strict schema enforcement, built-in logging, and CLI arguments—I’ve built a reusable, maintainable, and scalable synthetic-data generator that fits into a larger fraud detection microservice.”

That explanation covers:

* **Libraries used**: YAML, Polars, PyArrow, Faker, Mimesis, Boto3, logging, argparse.
* **Design decisions**: chunked streaming for memory efficiency; schema in YAML for single source of truth; optional S3 upload.
* **Production-readiness**: unit tests, logging, error handling (missing `RAW_BUCKET`), consistent file naming with timestamps.
* **Why it matters** to a fraud detection pipeline: you now have 1 million+ rows of realistic “payments” where \~0.3% are labeled fraud, including realistic fields (IP, user agent, MCC, etc.) so a downstream model or ETL job can train/evaluate without ever touching real PII or real card data.

---

### Key Takeaways

1. **Imports & Setup**

   * We use standard libs (`argparse`, `logging`, `random`, etc.) alongside third-party libs (Polars, PyArrow, Faker, Mimesis, YAML, Boto3). Each has a clear purpose:

     * **Faker/Mimesis** → realistic synthetic values.
     * **YAML** → single source of truth for schema.
     * **Polars + PyArrow** → high-performance, low-memory DataFrame → Parquet pipeline.
     * **Boto3** → optional S3 upload for downstream data lake integration.
     * **Logging** → structured, leveled logging instead of `print()`.

2. **Class Design**

   * All state (e.g., `total_rows`, `fraud_rate`, `null_*_rate`) is stored on `TransactionSimulator`.
   * Methods are broken up by responsibility:

     * `_generate_one_row(...)` → returns a single dict of fields.
     * `generate_to_parquet()` → orchestrates chunked DataFrame creation and streaming writes to a Parquet file.
     * `upload_to_s3(...)` → handles the S3 upload using date-partitioned keys.

3. **Chunked Streaming**

   * Minimizes memory usage: by generating 100 000 rows at a time, then writing them out via `ParquetWriter`, we never hold more than \~a few megabytes in RAM at once (depending on number of columns).
   * Each chunk is converted to a Polars DataFrame (`pl.from_dicts(...)`) with explicit schema override for `event_time`, then turned into a PyArrow table for `ParquetWriter.write_table(...)`.

4. **CLI & Entry Point**

   * `argparse` → user-friendly interface (`--rows`, `--out`, `--s3`).
   * `if __name__ == "__main__": main()` → ensures the module can be imported without side effects or run as a script when needed.

5. **Industry Standards**

   * Directory structure, testing readiness, logging, error handling, and environment variables align with what a real MLOps team expects.
   * The code is modular so that later, you could:

     1. Wrap `generate_to_parquet()` in a Prefect flow for scheduling.
     2. Add a “seasonality” bump (e.g., Black Friday) by extending `_generate_one_row()` or inserting logic before chunking.
     3. Write a unit test that mocks Boto3 to ensure `upload_to_s3()` constructs the correct key.

By walking through this code, you now have a clear mental model of how a production-grade synthetic data generator is structured. You can confidently talk to a recruiter or a teammate about why Polars and PyArrow are used (speed and memory efficiency), why we chunk the writes (constant RAM), how Faker/Mimesis provide realistic values, how YAML drives schema consistency, and how Boto3 handles the S3 integration.

# Fixing the `mimesis.Business` not having `.mcc()`
Below is the updated **`generate.py`** that works with Mimesis 18.0.0 (where `Business()` no longer exists). In this version:

1. We remove any use of `Business()`/`Finance()` for MCC codes.
2. We instead define a small, hard-coded list of common MCCs (`MCC_CODES`) and randomly pick from it (or set to `None` per your null rate).
3. All other logic (chunked Parquet writes, schema enforcement, Faker usage, S3 upload) remains the same.

You can drop this into `src/fraud_detection/simulator/generate.py`—replacing your previous file—and it will generate an identical synthetic‐data pipeline, except MCCs come from our predefined list rather than Mimesis.

```python
"""
generate.py
───────────
Create synthetic payment events that conform to schema/transaction_schema.yaml,
using Mimesis 18.0.0 (no Business().mcc()).

CLI
---
    poetry run python -m fraud_detection.simulator.generate \
        --rows 1_000_000 \
        --out outputs/ \
        --s3 yes

• Streams data in 100k-row chunks (constant RAM) to a single Snappy‐compressed Parquet.  
• Column order is enforced via the YAML schema.  
• Optionally uploads to S3 bucket defined in environment variable RAW_BUCKET.
"""
from __future__ import annotations

import argparse
import datetime
import logging
import math
import os
import pathlib
import random
import time
import uuid
from typing import Dict, List, Optional

import boto3
import botocore
import polars as pl
import pyarrow.parquet as pq
import yaml
from faker import Faker

# ---------- Setup logging ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------- Constants & Global Generators -----------------------------------
SCHEMA_YAML = pathlib.Path("schema/transaction_schema.yaml")
faker = Faker()
random.seed(42)
faker.seed_instance(42)

# Since Mimesis no longer provides MCC in version 18.0.0, define a static list of common MCCs:
# You can extend this list as needed for more variety.
MCC_CODES: List[int] = [
    5411,  # Grocery Stores
    5812,  # Eating Places, Restaurants
    4111,  # Local/Suburban Commuter Transport—Incl. Ferries
    5541,  # Service Stations (with or without ancillary services)
    5944,  # Jewelry, Watch, Clock, and Silverware Stores
    5691,  # Men’s and Boys’ Clothing Stores
    5732,  # Electronics Stores
    5814,  # Fast Food Restaurants
    5912,  # Drug Stores and Pharmacies
    5943,  # Office, School Supply, and Stationery Stores
]

# Load YAML once and extract column order
SCHEMA = yaml.safe_load(SCHEMA_YAML.read_text())
COLUMNS: List[str] = [field_dict["name"] for field_dict in SCHEMA["fields"]]


class TransactionSimulator:
    """
    Encapsulates all logic for generating a synthetic payments dataset
    and writing it to a single Parquet file (in Snappy compression),
    chunk by chunk.
    """

    def __init__(
        self,
        total_rows: int,
        out_dir: pathlib.Path,
        chunk_size: int = 100_000,
        fraud_rate: float = 0.003,
        null_mcc_rate: float = 0.05,
        null_device_rate: float = 0.08,
        null_geo_rate: float = 0.01,
        timezone_offset: int = -60,
    ) -> None:
        """
        Args:
            total_rows: Number of rows to generate in total.
            out_dir: Directory into which the final Parquet file will be written.
            chunk_size: How many rows to buffer per batch before writing.
            fraud_rate: Probability any given transaction is labeled fraudulent.
            null_mcc_rate: Fraction of rows where mcc_code is set to None.
            null_device_rate: Fraction of rows with no device_id.
            null_geo_rate: Fraction of rows with no latitude/longitude.
            timezone_offset: Value for "local_time_offset" column (in minutes).
        """
        self.total_rows = total_rows
        self.out_dir = out_dir
        self.chunk_size = chunk_size
        self.fraud_rate = fraud_rate
        self.null_mcc_rate = null_mcc_rate
        self.null_device_rate = null_device_rate
        self.null_geo_rate = null_geo_rate
        self.timezone_offset = timezone_offset

        # Capture a single "now" timestamp so all rows are relative to the same reference.
        self._now_ts = time.time()

    def _generate_one_row(self, now_ts: float) -> Dict[str, object]:
        """
        Generate a single synthetic payment event dictionary.
        Avoids re-creating Faker on every call; uses a static MCC list instead of Mimesis.
        """
        # 1. Randomize a transaction timestamp between (now - 30 days) and now:
        ts = datetime.datetime.utcfromtimestamp(
            now_ts - random.uniform(0, 30 * 24 * 3600)
        )
        ts = ts.replace(tzinfo=datetime.timezone.utc)

        # 2. Customer and card information:
        user_id = faker.random_int(10_000, 999_999)
        raw_card_number = faker.credit_card_number()  # e.g. "4242 4242 4242 4242"
        card_pan_hash = faker.sha256(raw_card_number)

        # 3. Merchant / business info (static MCC list):
        if random.random() > self.null_mcc_rate:
            mcc = random.choice(MCC_CODES)
        else:
            mcc = None
        channel = faker.random_element(("ONLINE", "IN_STORE", "ATM"))

        # 4. Geolocation & device fields:
        latitude = (
            round(faker.latitude(), 6) if random.random() > self.null_geo_rate else None
        )
        longitude = (
            round(faker.longitude(), 6) if random.random() > self.null_geo_rate else None
        )
        device_id = faker.uuid4() if random.random() > self.null_device_rate else None
        ip_address = faker.ipv4_public() if channel == "ONLINE" else None
        user_agent = faker.user_agent() if channel == "ONLINE" else None

        # 5. Transaction amount & labeling:
        amount = round(random.uniform(1.0, 500.0), 2)
        is_fraud = random.random() < self.fraud_rate

        return {
            "transaction_id": uuid.uuid4().hex,
            "event_time": ts,
            "local_time_offset": self.timezone_offset,
            "amount": amount,
            "currency_code": faker.currency_code(),
            "card_pan_hash": card_pan_hash,
            "card_scheme": faker.random_element(("VISA", "MASTERCARD", "AMEX", "DISCOVER")),
            "card_exp_year": faker.random_int(2026, 2030),
            "card_exp_month": faker.random_int(1, 12),
            "customer_id": user_id,
            "merchant_id": faker.random_int(1000, 9999),
            "merchant_country": faker.country_code(representation="alpha-2"),
            "mcc_code": mcc,
            "channel": channel,
            "pos_entry_mode": faker.random_element(("CHIP", "MAGSTRIPE", "NFC", "ECOM")),
            "device_id": device_id,
            "device_type": faker.random_element(("IOS", "ANDROID", "WEB", "POS")),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "latitude": latitude,
            "longitude": longitude,
            "is_recurring": faker.boolean(chance_of_getting_true=10),
            "previous_txn_id": None,
            "label_fraud": is_fraud,
        }

    def generate_to_parquet(self) -> pathlib.Path:
        """
        Streams the entire dataset into a single Parquet file, chunk by chunk.
        Returns the path to the written Parquet file.
        """
        # 1. Prepare output directory and final filename
        today_str = datetime.date.today().isoformat()
        filename = f"payments_{self.total_rows:_}_{today_str}.parquet"
        out_path = self.out_dir / filename
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # 2. Buffer `chunk_size` rows at a time → Polars DF → PyArrow Table → ParquetWriter
        parquet_writer: Optional[pq.ParquetWriter] = None
        rows_remaining = self.total_rows
        start_time = time.time()
        total_chunks = math.ceil(self.total_rows / self.chunk_size)

        logger.info(f"Beginning simulation: {self.total_rows:,} rows → {out_path}")
        logger.info(f"Chunk size: {self.chunk_size:,} rows ({total_chunks} total chunks)")

        chunk_index = 0
        while rows_remaining > 0:
            chunk_index += 1
            current_chunk_size = min(self.chunk_size, rows_remaining)

            # 2a. Generate a list of dicts for this chunk
            chunk_dicts: List[Dict[str, object]] = [
                self._generate_one_row(self._now_ts) for _ in range(current_chunk_size)
            ]

            # 2b. Build a Polars DataFrame with the correct schema/order
            df_chunk = pl.from_dicts(
                chunk_dicts, schema_overrides={"event_time": pl.Datetime("ns", "UTC")}
            ).select(COLUMNS)  # enforce column order as in YAML

            # 2c. Convert to PyArrow table
            arrow_table = df_chunk.to_arrow()

            # 2d. Initialize or append to the ParquetWriter
            if parquet_writer is None:
                parquet_writer = pq.ParquetWriter(
                    out_path,
                    arrow_table.schema,
                    compression="snappy",
                    use_deprecated_int96_timestamps=False,
                )
            parquet_writer.write_table(arrow_table)

            # Cleanup & logging
            rows_remaining -= current_chunk_size
            elapsed = time.time() - start_time
            logger.info(
                f"Chunk {chunk_index}/{total_chunks} written "
                f"({current_chunk_size:,} rows). "
                f"{rows_remaining:,} rows left. Elapsed: {elapsed:0.2f}s"
            )
            del chunk_dicts

        # 3. Close the ParquetWriter
        if parquet_writer:
            parquet_writer.close()

        total_duration = time.time() - start_time
        logger.info(f"Completed: {self.total_rows:,} rows in {total_duration:0.2f}s → {out_path}")
        return out_path

    def upload_to_s3(self, file_path: pathlib.Path, bucket: str) -> None:
        """
        Upload the given file to S3 under a date‐partitioned key.
        E.g.: s3://{bucket}/payments/year=2025/month=05/payments_1_000_000_2025-05-31.parquet
        """
        today = datetime.date.today()
        key = f"payments/year={today.year}/month={today:%m}/{file_path.name}"

        s3_client = boto3.client(
            "s3", config=botocore.client.Config(signature_version="s3v4")
        )
        logger.info(f"Uploading {file_path} to s3://{bucket}/{key} …")
        s3_client.upload_file(str(file_path), bucket, key)
        logger.info(f"Upload complete → s3://{bucket}/{key}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic payments and optionally upload to S3."
    )
    parser.add_argument(
        "--rows", type=int, default=1_000_000, help="Total number of rows to generate."
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("outputs"),
        help="Local directory to write the Parquet file.",
    )
    parser.add_argument(
        "--s3",
        choices=["yes", "no"],
        default="no",
        help="Whether to upload the final Parquet to S3 (requires RAW_BUCKET env var).",
    )

    args = parser.parse_args()

    simulator = TransactionSimulator(total_rows=args.rows, out_dir=args.out)
    parquet_path = simulator.generate_to_parquet()

    if args.s3 == "yes":
        bucket_name = os.environ.get("RAW_BUCKET")
        if not bucket_name:
            logger.error("Environment variable RAW_BUCKET not set. Aborting upload.")
            raise SystemExit(1)
        simulator.upload_to_s3(parquet_path, bucket_name)


if __name__ == "__main__":
    main()
```

---

### What Changed & Why

1. **Removed Mimesis’s `Business()` / `Finance()`**

   * In Mimesis 18.0.0, `Business()` was renamed (or removed) and there’s no built-in `mcc()` method.
   * To compensate, we defined a short list of common MCCs (`MCC_CODES`) at the top. This list can be extended or replaced with a larger static file if you want more variety.

2. **`MCC_CODES` List**

   * We chose about ten representative MCC values (e.g., `5411`, `5812`, `5541`, etc.) to simulate real‐world categories.
   * In `_generate_one_row()`, we replace:

     ```python
     mcc: Optional[int] = int(business.mcc()) if random.random() > self.null_mcc_rate else None
     ```

     with:

     ```python
     if random.random() > self.null_mcc_rate:
         mcc = random.choice(MCC_CODES)
     else:
         mcc = None
     ```
   * This way, approximately `null_mcc_rate` fraction of rows get `None`, and the rest pick a random code from our hard-coded list.

3. **Dropped the `mimesis` Import**

   * Because we no longer rely on `Business()` or `Finance()`, you can remove `mimesis` entirely from this file. If you’re not using Mimesis elsewhere, you can also remove it from `pyproject.toml` dependencies.

4. **Everything Else Stays Identical**

   * Faker still powers random credit‐card numbers, IPs, user agents, currency codes, etc.
   * Polars + PyArrow still chunk and stream to Parquet.
   * Logging, schema enforcement, and S3 upload remain unchanged.

---

### How to Explain This Change to a Recruiter

> “It turned out that in Mimesis 18.0.0, the `Business()` provider no longer offers an MCC generator. To keep everything compatible with that version, I removed the Mimesis dependency for MCCs and instead maintain a small, hard-coded list of representative MCC codes. In `_generate_one_row()`, each transaction’s `mcc_code` is now either `None` (with some null rate) or a random choice from that list.
>
> This way, I still simulate realistic MCC distributions without relying on an external library for that specific field. All other aspects—like using Faker for credit‐card hashing, chunked Parquet writes via Polars and PyArrow, and optional S3 upload with Boto3—are unchanged, preserving our memory efficiency, testability, and production readiness.”

---

#### Next Steps

* **Verify Dependencies**:

  * If you no longer need any Mimesis functionality beyond MCC, you can remove `"mimesis (>=18.0.0,<19.0.0)"` from `pyproject.toml`.
  * Otherwise, keep Mimesis for any other “fake data” needs you might add later (e.g., account numbers, bank names, etc.).

* **Run a Quick Smoke Test**:

  ```bash
  # From your repo root:
  poetry run python -m fraud_detection.simulator.generate --rows 10_000 --out test_outputs
  ```

  * Check that `test_outputs/payments_10_000_<today’s date>.parquet` appears.
  * Use a Parquet viewer (e.g., `polars` REPL or `pyarrow`) to confirm the `mcc_code` column is populated from your `MCC_CODES` list and has `None` where expected.

* **Unit Test the `mcc` Logic**:
  In `tests/unit/test_generate.py`, you can add something like:

  ```python
  from pathlib import Path
  from fraud_detection.simulator.generate import TransactionSimulator, MCC_CODES

  def test_mcc_values_or_none():
      sim = TransactionSimulator(total_rows=10, out_dir=Path("dummy"), null_mcc_rate=0.0)
      rows = [sim._generate_one_row(sim._now_ts) for _ in range(100)]
      # Since null_mcc_rate=0.0, none of these should be None, and all should be in the MCC_CODES list:
      for row in rows:
          assert row["mcc_code"] in MCC_CODES

      sim2 = TransactionSimulator(total_rows=10, out_dir=Path("dummy"), null_mcc_rate=1.0)
      rows2 = [sim2._generate_one_row(sim2._now_ts) for _ in range(10)]
      # Now null_mcc_rate=1.0, so every mcc_code must be None:
      assert all(row["mcc_code"] is None for row in rows2)
  ```

  This ensures your logic around `random.choice(MCC_CODES)` / `None` is bulletproof.

With these adjustments, your generator is now fully compatible with Mimesis 18.0.0 and continues to meet all the performance, schema-enforcement, and production-readiness requirements we discussed earlier.
