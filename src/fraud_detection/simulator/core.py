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
from typing import Optional
import math
import multiprocessing
import sys
import logging
import time

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


def _make_uuid4_hex_array(rng: np.random.Generator, n: int) -> list[str]:
    """
    Generate `n` RFC-4122-compliant UUIDv4 hex strings, deterministically
    from the given numpy Generator.
    """
    # 1) Draw two arrays of 64-bit unsigned ints
    hi = rng.integers(0, 2**64, size=n, dtype=np.uint64)
    lo = rng.integers(0, 2**64, size=n, dtype=np.uint64)

    # 2) Combine to 128-bit Python ints
    ints = (hi.astype(object) << 64) | lo.astype(object)

    # 3) Set version bits (flip bits 76–79 to 0b0100) and variant bits (flip bits 62–63 to 0b10)
    def _set_uuid4_bits(i: int) -> int:
        i = (i & ~(0xF << 76)) | (4 << 76)
        i = (i & ~(0x3 << 62)) | (2 << 62)
        return i

    ints = [_set_uuid4_bits(i) for i in ints]

    # 4) Convert to hex strings
    return [uuid.UUID(int=i).hex for i in ints]


# Helper for Pool.imap_unordered to unpack the args tuple
def _chunk_worker(args: tuple[int, GeneratorConfig, Optional[int]]) -> pl.DataFrame:
    """
    Unpack (chunk_rows, cfg, seed) tuple for multiprocessing.
    """
    from .core import _generate_chunk  # avoid circular at import
    return _generate_chunk(*args)

def _generate_chunk(chunk_rows: int, cfg: GeneratorConfig, seed: Optional[int]) -> pl.DataFrame:
    """
    Generate a single chunk of `chunk_rows` events using fully vectorized operations.
    """
    # ── Unpack & defaults ──────────────────────────────────────────────────────
    fraud_rate = cfg.fraud_rate
    start_date = cfg.temporal.start_date or date.today()
    end_date   = cfg.temporal.end_date   or date.today()
    # seed Python/NumPy/Faker for reproducibility
    if seed is not None:
        random.seed(seed)
        _fake.seed_instance(seed)
    rng = np.random.default_rng(seed)

    # ── 1) Timestamps ──────────────────────────────────────────────────────────
    timestamps = sample_timestamps(
        total_rows=chunk_rows,
        start_date=start_date,
        end_date=end_date,
        seed=seed,
    )

    # ── 2) Catalogs ────────────────────────────────────────────────────────────
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
        risk_alpha=cfg.catalog.card_risk_alpha,
        risk_beta=cfg.catalog.card_risk_beta,
    )

    # ── 3) Entity‐ID draws ──────────────────────────────────────────────────────
    cust_ids  = sample_entities(cust_cat,  "customer_id", chunk_rows, seed=seed)
    merch_ids = sample_entities(merch_cat, "merchant_id", chunk_rows, seed=(seed or 0) + 1)
    card_ids  = sample_entities(card_cat, "card_id",     chunk_rows, seed=(seed or 0) + 2)

    # ── 4) Fraud label ─────────────────────────────────────────────────────────
    m_risk = merch_cat["risk"].to_numpy()[merch_ids - 1]
    c_risk = card_cat["risk"].to_numpy()[card_ids  - 1]
    p_fraud = fraud_rate * m_risk * c_risk
    label_fraud = rng.random(chunk_rows) < p_fraud

    # ── 5) Numeric features ───────────────────────────────────────────────────
    local_time_offset = rng.integers(-720, 841, size=chunk_rows)
    if cfg.feature.amount_distribution == "lognormal":
        raw_amt = rng.lognormal(cfg.feature.lognormal_mean, cfg.feature.lognormal_sigma, size=chunk_rows)
    elif cfg.feature.amount_distribution == "normal":
        raw_amt = rng.normal(cfg.feature.lognormal_mean, cfg.feature.lognormal_sigma, size=chunk_rows)
    else:
        raw_amt = rng.uniform(cfg.feature.uniform_min, cfg.feature.uniform_max, size=chunk_rows)
    amount = np.round(raw_amt, 2)

    # ── 6) Fully‐vectorized categoricals ───────────────────────────────────────
    # device_type
    dev_keys   = list(cfg.feature.device_types.keys())
    dev_wts    = np.array(list(cfg.feature.device_types.values()), dtype=float)
    device_type = rng.choice(dev_keys, size=chunk_rows, p=dev_wts/dev_wts.sum())
    # card_scheme
    schemes    = ["VISA","MASTERCARD","AMEX","DISCOVER"]
    card_scheme = rng.choice(schemes, size=chunk_rows)
    # channel
    channels   = ["ONLINE","IN_STORE","ATM"]
    channel    = rng.choice(channels, size=chunk_rows)
    # pos_entry_mode
    modes      = ["CHIP","MAGSTRIPE","NFC","ECOM"]
    pos_entry_mode = rng.choice(modes, size=chunk_rows)
    # is_recurring
    is_recurring = rng.random(chunk_rows) < 0.1

    # ── 7) Currency & timezone via MCC code ───────────────────────────────────
    mcc_arr = merch_cat["mcc_code"].to_numpy()[merch_ids - 1].astype(str)
    eur_mask = np.char.startswith(mcc_arr, "4")
    currency_code = np.where(eur_mask, "EUR", "USD")
    timezone      = np.where(eur_mask, "Europe/Berlin", "America/New_York")

    # ── 8) Other vectorizable fields ──────────────────────────────────────────
    pan_hash = np.array(card_cat["pan_hash"].to_list(), dtype=object)[card_ids - 1]
    # merchant_country pool‐sample
    pool_n = min(chunk_rows, 100_000)
    country_pool = [_fake.country_code(representation="alpha-2") for _ in range(pool_n)]
    merchant_country = rng.choice(country_pool, size=chunk_rows)
    # lat/lon uniform draws
    latitude  = np.round(rng.uniform(-90,  90, size=chunk_rows), 6)
    longitude = np.round(rng.uniform(-180, 180, size=chunk_rows), 6)

    # Generate transaction_id
    tx_ids = _make_uuid4_hex_array(rng, chunk_rows)

    # Generate device_id with ~90% present
    mask = rng.random(chunk_rows) < 0.9
    # Make exactly sum(mask) UUIDs
    dev_ids_pool = _make_uuid4_hex_array(rng, int(mask.sum()))
    it = iter(dev_ids_pool)
    device_ids = [next(it) if m else None for m in mask]

    # ── 9) Assemble & cast ─────────────────────────────────────────────────────
    df = pl.DataFrame({
        "transaction_id":  tx_ids,
        "event_time":      timestamps,
        "local_time_offset": local_time_offset,
        "amount":          amount,
        "currency_code":   currency_code,
        "card_pan_hash":   pan_hash,
        "customer_id":     cust_ids,
        "merchant_id":     merch_ids,
        "merchant_country":merchant_country,
        "device_type":     device_type,
        "timezone":        timezone,
        "card_scheme":     card_scheme,
        "card_exp_year":   rng.integers(start_date.year + 1, start_date.year + 6, size=chunk_rows),
        "card_exp_month":  rng.integers(1, 13, size=chunk_rows),
        "channel":         channel,
        "pos_entry_mode":  pos_entry_mode,
        "device_id":       device_ids,
        "ip_address":      rng.choice([_fake.ipv4_public() for _ in range(pool_n)], size=chunk_rows),
        "user_agent":      rng.choice([_fake.user_agent()   for _ in range(pool_n)], size=chunk_rows),
        "latitude":        latitude,
        "longitude":       longitude,
        "is_recurring":    is_recurring,
        "previous_txn_id": [None]*chunk_rows,
        "label_fraud":     label_fraud,
        "mcc_code":        mcc_arr,
    })

    return df


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

    # Set up logging for per‐chunk status updates
    logger = logging.getLogger(__name__)
    start_time     = time.perf_counter()
    last_time      = start_time
    cumulative_rows = 0

    # Unpack config
    total_rows = cfg.total_rows
    start_date = cfg.temporal.start_date or date.today()
    end_date = cfg.temporal.end_date or date.today()

    # ── Temporal sanity check ─────────────────────────────────────────────────
    if end_date < start_date:
        # Make sure invalid ranges bubble up as a ValueError
        raise ValueError(f"Temporal sampling failed: end_date {end_date!r} is before start_date {start_date!r}")

    # If configured, split into parallel chunks
    if cfg.num_workers > 1 and cfg.batch_size > 0:
        num_chunks = math.ceil(total_rows / cfg.batch_size)
        counts     = [cfg.batch_size] * (num_chunks - 1) + [total_rows - cfg.batch_size * (num_chunks - 1)]
        base_seed  = cfg.seed or 0
        args       = [(counts[i], cfg, base_seed + i) for i in range(num_chunks)]
        dfs: list[pl.DataFrame] = []

        # Parallel generation with per‐chunk logging
        with multiprocessing.Pool(cfg.num_workers) as pool:
            for df in pool.imap_unordered(_chunk_worker, args):
                now = time.perf_counter()
                chunk_time = now - last_time
                total_time = now - start_time
                cumulative_rows += df.height
                speed = df.height / chunk_time if chunk_time > 0 else float('inf')
                logger.info(
                    "Chunk done: %d rows in %.2f s (%.0f rows/s) — total %d/%d rows in %.2f s",
                    df.height, chunk_time, speed, cumulative_rows, total_rows, total_time,
                )
                last_time = now
                dfs.append(df)

            # One global concat + schema cast
        df = pl.concat(dfs, rechunk=False)
        return (
            df
            .with_columns([pl.col(col).cast(_POLARS_SCHEMA[col]) for col in _COLUMNS])
            .select(_COLUMNS)
        )

    # Single-process fallback with logging
    df = _generate_chunk(total_rows, cfg, cfg.seed)
    now        = time.perf_counter()
    chunk_time = now - last_time
    speed      = df.height / chunk_time if chunk_time > 0 else float('inf')
    logger.info(
        "Single-chunk done: %d rows in %.2f s (%.0f rows/s)",
        df.height, chunk_time, speed,
    )
    # Apply schema cast
    return (
        df
        .with_columns([pl.col(col).cast(_POLARS_SCHEMA[col]) for col in _COLUMNS])
        .select(_COLUMNS)
    )

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
