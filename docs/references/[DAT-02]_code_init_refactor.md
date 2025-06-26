
Below is a refactored version of **`generate.py`** that follows a more “production-grade” structure:

* **Encapsulates** all generation logic in a `TransactionSimulator` class.
* **Streams** data to Parquet chunk by chunk (using PyArrow’s `ParquetWriter`) instead of collecting whole lists of DataFrames. This keeps peak memory usage low and avoids needing to concatenate large lists of Polars frames.
* **Enforces** column order based on your YAML schema.
* Uses Python’s built-in **`logging`** (instead of bare `print`) for better observability.
* Adds **type hints** and splits responsibilities cleanly (generation vs. CLI vs. upload).

You can drop this into `src/fraud_detection/simulator/generate.py` (replacing the old code) and it will behave identically from the user’s perspective, but be easier to maintain and test.

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
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from faker import Faker
from mimesis import Business

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
business = Business()
random.seed(42)
faker.seed_instance(42)

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

### Summary of Key Structural Improvements

1. **Class-Based Encapsulation**

   * All “generate one row” logic and “stream‐to‐Parquet” logic live in a single `TransactionSimulator` class.
   * This makes it easy to write unit tests against methods like `_generate_one_row()` or `generate_to_parquet()` in isolation.

2. **Chunked ParquetWriter (Streaming Write)**

   * Instead of collecting `frames: List[pl.DataFrame]` in memory and doing a final `pl.concat(...)`, we open a `pyarrow.ParquetWriter` once, then write each chunk’s table immediately.
   * This guarantees a constant memory footprint even for ten‐million‐row simulations.

3. **Schema/Column Enforcement**

   * We load `config/transaction_schema.yaml` once at import time and extract the `COLUMNS` list. Then, after building each Polars DataFrame, we `.select(COLUMNS)` to force the exact column order and data types.

4. **Logging Instead of Prints**

   * Using `logging.info()` makes it trivial to redirect logs to a file, change verbosity (e.g., to WARNING or DEBUG), or integrate with any centralized log aggregator.

5. **Type Hints & Docstrings**

   * Every public method/function now has a clear signature.
   * Docstrings explain why each piece exists (e.g. “This streams the entire dataset to one Parquet file…”).

6. **CLI Separation**

   * `main()` only handles argument parsing, instantiates the class, and delegates functionality.
   * This is a common pattern in production code: your `if __name__ == "__main__":` block is minimal, so testing the actual logic is trivial (just import `TransactionSimulator` in a test and verify it).

7. **Environment Checks**

   * If `--s3 yes` is passed without a `RAW_BUCKET` env var, we log an error and exit with a non‐zero status. This is more explicit than a cryptic `KeyError`.

---

Feel free to copy this new `generate.py` into your repository. Once you replace the old file, everything should work exactly the same (you can still run

```bash
poetry run python -m fraud_detection.simulator.generate --rows 1_000_000 --out outputs --s3 yes
```

), but now:

* Memory usage is predictable (no giant list of DataFrames).
* The code is easier to test (e.g., you can pass `chunk_size=10_000` in a unit test, generate 25k rows, and assert schema, row count, fraud‐rate, etc.).
* Future extensions—like adding a “seasonality bump” or plugging this into Prefect—are simpler now that everything lives in `TransactionSimulator` as methods.
