"""
Core data‐generation logic for synthetic payment events.

This module has NO external side‐effects (no AWS, no CLI parsing).
It reads your schema, builds a Polars DataFrame in‐memory, and hands it back.
"""

from __future__ import annotations
import random
import uuid
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

import yaml  # type: ignore
import polars as pl
from faker import Faker
import numpy as np

from .mcc_codes import MCC_CODES
from .temporal import sample_timestamps
from .catalog import (
    generate_card_catalog,
    generate_customer_catalog,
    generate_merchant_catalog,
    sample_entities
)
from .config import CatalogConfig

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
        _DTYPE_MAP[fld["dtype"]]()  # type: ignore
        if not isinstance(_DTYPE_MAP[fld["dtype"]], type)  # type: ignore
        else _DTYPE_MAP[fld["dtype"]]
    )
    for fld in _schema["fields"]
}
_fake = Faker()


def generate_dataframe(
    total_rows: int,
    catalog_cfg: CatalogConfig,
    fraud_rate: float = 0.01,
    seed: Optional[int] = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pl.DataFrame:
    """
    Generate a Polars DataFrame of synthetic payment events.

    This function will:
      1. Sample `event_time` between `start_date` and `end_date` (diurnal mixture).
      2. Build Zipf-distributed customer, merchant, and card catalogs with Beta-distributed risk.
      3. Draw entity IDs from those catalogs.
      4. Correlate fraud labels with the per-entity risk factors.

    Parameters
    ----------
    total_rows : int
        Number of rows to produce.
    catalog_cfg : CatalogConfig
        Configuration for your entity catalogs (customers, merchants, cards),
        including counts, Zipf exponents, and Beta priors for risk.
    fraud_rate : float, optional
        Fraction (0–1) of transactions labeled as fraud.  Default is 0.01.
    seed : int | None, optional
        Seed for RNG reproducibility; if None, randomness is not seeded.
    start_date : date | None, optional
        Earliest date (UTC) for `event_time`.  If None, defaults to today.
    end_date : date | None, optional
        Latest date (UTC) for `event_time`.  If None, defaults to today.

    Returns
    -------
    pl.DataFrame
        A DataFrame with:
          - exactly `total_rows` rows,
          - columns in schema order,
          - dtypes matching your YAML spec,
          - Fraud labels correlated with merchant & card risk.
    """
    # Determine date range defaults at runtime
    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = date.today()

    # Seed control
    if seed is not None:
        random.seed(seed)
        _fake.seed_instance(seed)

    # Generate realistic event_time column (wrap errors clearly)
    try:
        timestamps = sample_timestamps(
            total_rows=total_rows,
            start_date=start_date,
            end_date=end_date,
            seed=seed,
        )
    except ValueError as e:
        raise ValueError(f"Temporal sampling failed for range {start_date} to {end_date}: {e}") from e

    # 1) Build entity catalogs (Zipf + risk)
    cust_cat = generate_customer_catalog(
        num_customers=catalog_cfg.num_customers,
        zipf_exponent=catalog_cfg.customer_zipf_exponent,
    )
    merch_cat = generate_merchant_catalog(
        num_merchants=catalog_cfg.num_merchants,
        zipf_exponent=catalog_cfg.merchant_zipf_exponent,
        seed=seed,
    )
    card_cat = generate_card_catalog(
        num_cards=catalog_cfg.num_cards,
        zipf_exponent=catalog_cfg.card_zipf_exponent,
        seed=seed,
    )

    # 2) Sample actual entity sequences
    cust_ids = sample_entities(cust_cat, "customer_id", total_rows, seed=seed)
    merch_ids = sample_entities(merch_cat, "merchant_id", total_rows, seed=(seed + 1) if seed is not None else None)
    card_ids = sample_entities(card_cat, "card_id", total_rows, seed=(seed + 2) if seed is not None else None)

    # 3) Vectorized arrays for risk & pan_hash (no KeyError risk)
    merch_risk_arr = merch_cat["risk"].to_numpy()
    card_risk_arr  = card_cat["risk"].to_numpy()
    pan_hash_arr   = np.array(card_cat["pan_hash"].to_list(), dtype=object)

    rows: list[dict[str, object]] = []

    for i in range(total_rows):
        # Correlated fraud probability
        m_factor = merch_risk_arr[merch_ids[i] - 1]
        c_factor = card_risk_arr[card_ids[i] - 1]
        p_fraud = fraud_rate * m_factor * c_factor
        is_fraud = random.random() < p_fraud

        record = {
            "transaction_id": _fake.uuid4().replace("-",""),
            "event_time": timestamps[i],
            "local_time_offset": random.randint(-720, 840),
            "amount": round(random.uniform(1.0, 500.0), 2),
            "currency_code": _fake.currency_code(),
            "card_pan_hash": pan_hash_arr[card_ids[i] - 1],
            "card_scheme": _fake.random_element(
                ["VISA", "MASTERCARD", "AMEX", "DISCOVER"]
            ),
            "card_exp_year": random.randint(start_date.year + 1, start_date.year + 5),
            "card_exp_month": random.randint(1, 12),
            # sample from catalogs instead of uniform random
            "customer_id": cust_ids[i],
            "merchant_id": merch_ids[i],
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
