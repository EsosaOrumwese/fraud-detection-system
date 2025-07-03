"""
Core data‐generation logic for synthetic payment events.

This module has NO external side‐effects (no AWS, no CLI parsing).
It reads your schema, builds a Polars DataFrame in‐memory, and hands it back.
"""

from __future__ import annotations
import random
import uuid
from datetime import date
from pathlib import Path

import yaml  # type: ignore
import polars as pl
from faker import Faker
import numpy as np
from numpy.random import default_rng

from .mcc_codes import MCC_CODES
from .temporal import sample_timestamps
from .catalog import (
    generate_card_catalog,
    generate_customer_catalog,
    generate_merchant_catalog,
    sample_entities
)
from .config import CatalogConfig, GeneratorConfig

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


def generate_dataframe(cfg: GeneratorConfig) -> pl.DataFrame:
    """
    Generate a Polars DataFrame of synthetic payment events.

    This function will:
      1. Sample `event_time` between `start_date` and `end_date` (diurnal mixture).
      2. Build Zipf-distributed customer, merchant, and card catalogs with Beta-distributed risk.
      3. Draw entity IDs from those catalogs.
      4. Correlate fraud labels with the per-entity risk factors.

    Parameters
    ----------
    cfg : GeneratorConfig
        Configuration for your entity catalogs (customers, merchants, cards),
        including counts, Zipf exponents, and Beta priors for risk.

    Returns
    -------
    pl.DataFrame
        A DataFrame with:
          - exactly `total_rows` rows,
          - columns in schema order,
          - dtypes matching your YAML spec,
          - Fraud labels correlated with merchant & card risk.
    """
    # Unpack config
    total_rows = cfg.total_rows
    fraud_rate = cfg.fraud_rate
    seed       = cfg.seed
    start_date = cfg.temporal.start_date
    end_date   = cfg.temporal.end_date

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
        num_customers=cfg.catalog.num_customers,
        zipf_exponent=cfg.catalog.customer_zipf_exponent,
    )
    merch_cat = generate_merchant_catalog(
        num_merchants=cfg.catalog.num_merchants,
        zipf_exponent=cfg.catalog.merchant_zipf_exponent,
        seed=seed,
        risk_alpha=cfg.catalog.merchant_risk_alpha,
        risk_beta=cfg.catalog.merchant_risk_beta,
    )
    card_cat = generate_card_catalog(
        num_cards=cfg.catalog.num_cards,
        zipf_exponent=cfg.catalog.card_zipf_exponent,
        seed=seed,
        risk_alpha=cfg.catalog.merchant_risk_alpha,
        risk_beta=cfg.catalog.merchant_risk_beta,
    )

    # 2) Sample actual entity sequences
    cust_ids = sample_entities(cust_cat, "customer_id", total_rows, seed=seed)
    merch_ids = sample_entities(merch_cat, "merchant_id", total_rows, seed=(seed or 0) + 1)
    card_ids = sample_entities(card_cat, "card_id", total_rows, seed=(seed or 0) + 2)

    # 3) Batched, vectorized feature generation
    rng = np.random.default_rng(seed)

    # Entity-level arrays
    cust_ids_arr  = cust_ids
    merch_ids_arr = merch_ids
    card_ids_arr  = card_ids

    merch_risk_arr = merch_cat["risk"].to_numpy()
    card_risk_arr  = card_cat["risk"].to_numpy()

    # Fraud label: p = fraud_rate * merchant_risk * card_risk
    m_factor   = merch_risk_arr[merch_ids_arr - 1]
    c_factor   = card_risk_arr[card_ids_arr - 1]
    p_fraud    = fraud_rate * m_factor * c_factor
    label_fraud = rng.random(total_rows) < p_fraud

    # Temporal and numeric features
    local_time_offset = rng.integers(-720, 841, size=total_rows)

    if cfg.feature.amount_distribution == "lognormal":
        raw_amounts = rng.lognormal(cfg.feature.lognormal_mean, cfg.feature.lognormal_sigma, size=total_rows)
    elif cfg.feature.amount_distribution == "normal":
        raw_amounts = rng.normal(cfg.feature.lognormal_mean, cfg.feature.lognormal_sigma, size=total_rows)
    else:
        raw_amounts = rng.uniform(cfg.feature.uniform_min, cfg.feature.uniform_max, size=total_rows)
    amount = np.round(raw_amounts, 2)

    # Map merchants → MCC codes (string) for currency/timezone logic
    mcc_arr       = merch_cat["mcc_code"].to_numpy()[merch_ids_arr - 1]
    mcc_strs      = mcc_arr.astype(str)
    eur_mask      = np.char.startswith(mcc_strs, "4")
    currency_code = np.where(eur_mask, "EUR", "USD")
    timezone      = np.where(eur_mask, "Europe/Berlin", "America/New_York")

    # Card PAN hashes
    pan_hash_arr = np.array(card_cat["pan_hash"].to_list(), dtype=object)[card_ids_arr - 1]

    # Semi-vectorized / list-comprehension features
    transaction_id    = [uuid.uuid4().hex for _ in range(total_rows)]
    device_type       = rng.choice(
        list(cfg.feature.device_types.keys()),
        size=total_rows,
        p=np.array(list(cfg.feature.device_types.values())) / sum(cfg.feature.device_types.values())
    )
    merchant_country  = [_fake.country_code(representation="alpha-2") for _ in range(total_rows)]
    card_scheme       = [_fake.random_element(["VISA","MASTERCARD","AMEX","DISCOVER"]) for _ in range(total_rows)]
    card_exp_year     = rng.integers(start_date.year + 1, start_date.year + 6, size=total_rows)
    card_exp_month    = rng.integers(1, 13, size=total_rows)
    channel           = [_fake.random_element(["ONLINE","IN_STORE","ATM"]) for _ in range(total_rows)]
    pos_entry_mode    = [_fake.random_element(["CHIP","MAGSTRIPE","NFC","ECOM"]) for _ in range(total_rows)]
    device_id         = [uuid.uuid4().hex if rng.random() < 0.9 else None for _ in range(total_rows)]
    ip_address        = [_fake.ipv4_public() for _ in range(total_rows)]
    user_agent        = [_fake.user_agent() for _ in range(total_rows)]
    latitude          = [round(_fake.latitude(), 6) for _ in range(total_rows)]
    longitude         = [round(_fake.longitude(), 6) for _ in range(total_rows)]
    is_recurring      = rng.random(total_rows) < 0.1
    previous_txn_id   = [None] * total_rows

    # Build DataFrame in one shot and cast
    df = pl.DataFrame({
        "transaction_id":    transaction_id,
        "event_time":        timestamps,
        "local_time_offset": local_time_offset,
        "amount":            amount,
        "currency_code":     currency_code,
        "card_pan_hash":     pan_hash_arr,
        "customer_id":       cust_ids_arr,
        "merchant_id":       merch_ids_arr,
        "merchant_country":  merchant_country,
        "device_type":       device_type,
        "timezone":          timezone,
        "card_scheme":       card_scheme,
        "card_exp_year":     card_exp_year,
        "card_exp_month":    card_exp_month,
        "channel":           channel,
        "pos_entry_mode":    pos_entry_mode,
        "device_id":         device_id,
        "ip_address":        ip_address,
        "user_agent":        user_agent,
        "latitude":          latitude,
        "longitude":         longitude,
        "is_recurring":      is_recurring,
        "previous_txn_id":   previous_txn_id,
        "label_fraud":       label_fraud,
        "mcc_code":          mcc_strs,
    }).with_columns([pl.col(col).cast(_POLARS_SCHEMA[col]) for col in _COLUMNS]) \
      .select(_COLUMNS)

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
