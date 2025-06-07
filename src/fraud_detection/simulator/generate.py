"""
generate.py
───────────
Create synthetic payment events that conform to config/transaction_schema.yaml.

CLI
---
    poetry run python -m fraud_detection.simulator.generate \
        --rows 1_000_000 \
        --out outputs/ \
        --s3 yes

• Streams data in 100k-row chunks (constant RAM) to a single Snappy‐compressed Parquet.
• Column order is enforced via the YAML schema.
• Optionally uploads to S3 bucket defined in environment variable raw_bucket_name.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import math
import pathlib
import random
import time
import uuid
import hashlib
from typing import Dict, List, Optional

import boto3  # type: ignore
import polars as pl  # type: ignore
from polars.datatypes import (
    Int64,
    Float64,
    Utf8,
    Boolean,
    Datetime,
    Categorical,
)
import pyarrow.parquet as pq  # type: ignore
import yaml  # type: ignore
from faker import Faker

# from mimesis import Finance  # type: ignore
# Since Mimesis no longer provides MCC in version 18.0.0, define a static list of common MCCs
from .mcc_codes import MCC_CODES
from fraud_detection.utils.param_store import get_param  # type: ignore

# ---------- Setup logging ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------- Constants & Global Generators -----------------------------------
SCHEMA_YAML = pathlib.Path("config/transaction_schema.yaml")
faker = Faker()
# finance = Finance()
random.seed(42)
faker.seed_instance(42)

# Load YAML once and extract column order
SCHEMA = yaml.safe_load(SCHEMA_YAML.read_text())
COLUMNS: List[str] = [field_dict["name"] for field_dict in SCHEMA["fields"]]

# map YAML "dtype" → an actual Polars DataType instance
_DTYPES: dict[str, pl.DataType] = {
    "int":      Int64(),             # nullable 64-bit int
    "float":    Float64(),           # nullable 64-bit float
    "string":   Utf8(),              # UTF-8 string
    "bool":     Boolean(),           # nullable boolean
    "datetime": Datetime("ns","UTC"),# timestamp[ns, UTC]
    "enum":     Categorical(),       # categorical for enums
}

# now map each field name to its Polars type
SCHEMA_POLARS: dict[str, pl.DataType] = {
    f["name"]: _DTYPES.get(f["dtype"], pl.Utf8)  # type: ignore
    for f in SCHEMA["fields"]
}


# You can extend this list as needed for more variety.
MCC_CODES = MCC_CODES


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
        rand_ts = now_ts - random.uniform(
            0, 30 * 24 * 3600
        )  # compute a random timestamp sometime in the past 30 days
        ts = datetime.datetime.fromtimestamp(
            rand_ts, tz=datetime.timezone.utc
        )  # create a UTC‐aware datetime in one go

        # 2. Customer and card information:
        user_id = faker.random_int(10_000, 999_999)
        raw_card_number = faker.credit_card_number()  # e.g. "4242 4242 4242 4242"
        # card_pan_hash = faker.sha256(raw_card_number)
        card_pan_hash = hashlib.sha256(raw_card_number.encode("utf-8")).hexdigest()

        # 3. Merchant / business info:
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
            round(faker.longitude(), 6)
            if random.random() > self.null_geo_rate
            else None
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
            "card_scheme": faker.random_element(
                ("VISA", "MASTERCARD", "AMEX", "DISCOVER")
            ),
            "card_exp_year": faker.random_int(2026, 2030),
            "card_exp_month": faker.random_int(1, 12),
            "customer_id": user_id,
            "merchant_id": faker.random_int(1000, 9999),
            "merchant_country": faker.country_code(representation="alpha-2"),
            "mcc_code": mcc,
            "channel": channel,
            "pos_entry_mode": faker.random_element(
                ("CHIP", "MAGSTRIPE", "NFC", "ECOM")
            ),
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
        logger.info(
            f"Chunk size: {self.chunk_size:,} rows ({total_chunks} total chunks)"
        )

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
                chunk_dicts, schema_overrides=SCHEMA_POLARS
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
        logger.info(
            f"Completed: {self.total_rows:,} rows in {total_duration:0.2f}s → {out_path}"
        )
        return out_path

    def upload_to_s3(self, file_path: pathlib.Path, bucket: str) -> None:
        """
        Upload the given file to S3 under a date‐partitioned key.
        E.g.: s3://{bucket}/payments/year=2025/month=05/payments_1_000_000_2025-05-31.parquet
        """
        today = datetime.date.today()
        key = f"payments/year={today.year}/month={today:%m}/{file_path.name}"

        logger.info(f"Uploading {file_path} to s3://{bucket}/{key} …")
        boto3.client("s3").upload_file(str(file_path), bucket, key)
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
        help="Whether to upload the final Parquet to S3 (requires 'raw_bucket_name' env var).",
    )

    args = parser.parse_args()

    simulator = TransactionSimulator(total_rows=args.rows, out_dir=args.out)
    parquet_path = simulator.generate_to_parquet()

    if args.s3 == "yes":
        bucket_name = get_param("/fraud/raw_bucket_name")
        if not bucket_name:
            logger.error(
                "Environment variable `raw_bucket_name` not set. Aborting upload."
            )
            raise SystemExit(1)
        simulator.upload_to_s3(parquet_path, bucket_name)


def generate_dataset(total_rows: int, out_dir: pathlib.Path) -> pathlib.Path:
    sim = TransactionSimulator(total_rows=total_rows, out_dir=out_dir)
    return sim.generate_to_parquet()


def _upload_to_s3(file_path: pathlib.Path, bucket: str) -> str:
    """
    Wraps TransactionSimulator.upload_to_s3 and returns the actual s3:// URI,
    including year/month prefixes.
    """
    sim = TransactionSimulator(total_rows=0, out_dir=file_path.parent)  # dummy instance
    # We assume upload_to_s3() writes to: s3://{bucket}/payments/year=YYYY/month=MM/{filename}
    sim.upload_to_s3(file_path, bucket)
    today = datetime.date.today()
    key = f"payments/year={today.year}/month={today:%m}/{file_path.name}"
    return f"s3://{bucket}/{key}"


if __name__ == "__main__":
    main()
