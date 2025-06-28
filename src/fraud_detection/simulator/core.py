"""
Core data‐generation logic for synthetic payment events.

This module has NO external side‐effects (no AWS, no CLI parsing).
It reads your schema, builds a Polars DataFrame in‐memory, and hands it back.
"""

from __future__ import annotations
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml  # type: ignore
import polars as pl
from faker import Faker

from .mcc_codes import MCC_CODES

# Locate the schema at the project root (/schema/transaction_schema.yaml)
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "schema" / "transaction_schema.yaml"
)
if not _SCHEMA_PATH.exists():
    raise FileNotFoundError(f"Schema not found at {_SCHEMA_PATH}")
_schema = yaml.safe_load(_SCHEMA_PATH.read_text())

# Extract column order and dtype map:
_COLUMNS = [f["name"] for f in _schema["fields"]]
_DTYPE_MAP: dict[str, pl.DataType] = {
    "int": pl.Int64,  # type: ignore
    "float": pl.Float64,  # type: ignore
    "string": pl.Utf8,  # type: ignore
    "bool": pl.Boolean,  # type: ignore
    "datetime": lambda: pl.Datetime(time_unit="ns", time_zone="UTC"),  # type: ignore
    "enum": pl.Categorical,  # type: ignore
}
# Build Polars schema for casting
_POLARS_SCHEMA = {
    fld["name"]: (
        _DTYPE_MAP[fld["dtype"]]()
        if not isinstance(_DTYPE_MAP[fld["dtype"]], type)  # type: ignore
        else _DTYPE_MAP[fld["dtype"]]
    )
    for fld in _schema["fields"]
}
_fake = Faker()


def generate_dataframe(
    total_rows: int,
    fraud_rate: float = 0.01,
    seed: Optional[int] = None,
) -> pl.DataFrame:
    """
    Generate a Polars DataFrame of synthetic payment events.

    Parameters
    ----------
    total_rows : int
        Number of rows to produce.
    fraud_rate : float
        Fraction (0–1) of transactions labeled as fraud.
    seed : Optional[int]
        Seed for RNG reproducibility; if None, randomness is not seeded.

    Returns
    -------
    pl.DataFrame
        A DataFrame with exactly `total_rows` rows, columns in schema order,
        and dtypes matching your YAML spec.
    """
    # Seed control
    if seed is not None:
        random.seed(seed)
        _fake.seed_instance(seed)

    # # Pre-extract the enum list for mcc_code by name
    # mcc_field = next(f for f in _schema["fields"] if f["name"] == "mcc_code")
    # mcc_list = mcc_field.get("enum", [])

    rows: list[dict[str, object]] = []
    now = datetime.now(timezone.utc)

    for _ in range(total_rows):
        is_fraud = random.random() < fraud_rate
        record = {
            "transaction_id": uuid.uuid4().hex,
            "event_time": now,
            "local_time_offset": random.randint(-720, 840),
            "amount": round(random.uniform(1.0, 500.0), 2),
            "currency_code": _fake.currency_code(),
            "card_pan_hash": _fake.sha256(),
            "card_scheme": _fake.random_element(
                ["VISA", "MASTERCARD", "AMEX", "DISCOVER"]
            ),
            "card_exp_year": random.randint(now.year + 1, now.year + 5),
            "card_exp_month": random.randint(1, 12),
            "customer_id": random.randint(1_000, 999_999),
            "merchant_id": random.randint(1_000, 9_999),
            "merchant_country": _fake.country_code(representation="alpha-2"),
            "mcc_code": (
                str(_fake.random_element(MCC_CODES))  # now a string
                if _fake.random.random() > 0.05
                else None
            ),
            "channel": _fake.random_element(["ONLINE", "IN_STORE", "ATM"]),
            "pos_entry_mode": _fake.random_element(
                ["CHIP", "MAGSTRIPE", "NFC", "ECOM"]
            ),
            "device_id": _fake.uuid4() if _fake.random.random() > 0.1 else None,
            "device_type": _fake.random_element(["IOS", "ANDROID", "WEB", "POS"]),
            "ip_address": _fake.ipv4_public(),
            "user_agent": _fake.user_agent(),
            "latitude": round(_fake.latitude(), 6),
            "longitude": round(_fake.longitude(), 6),
            "is_recurring": _fake.boolean(chance_of_getting_true=10),
            "previous_txn_id": None,
            "label_fraud": is_fraud,
        }
        rows.append(record)

    # Build DataFrame & enforce schema
    df = (
        pl.DataFrame(rows)
        .with_columns([pl.col(col).cast(_POLARS_SCHEMA[col]) for col in _COLUMNS])
        .select(_COLUMNS)
    )
    return df


def write_parquet(df: pl.DataFrame, out_path: Path) -> Path:
    """
    Write the DataFrame to a Snappy‐compressed Parquet file.

    Parameters
    ----------
    df : pl.DataFrame
        The data to write.
    out_path : Path
        File path to write (must end with .parquet).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(str(out_path), compression="snappy")
    return out_path
