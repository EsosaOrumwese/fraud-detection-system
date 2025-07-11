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
import logging
import time

import yaml  # type: ignore
import polars as pl
from faker import Faker
import numpy as np

from .temporal import sample_timestamps
from .catalog import (
    generate_card_catalog,
    generate_customer_catalog,
    generate_merchant_catalog,
    sample_entities,
    write_catalogs,
    load_catalogs,
)
from .config import GeneratorConfig
from .labeler import label_fraud

# Locate the schema at the project root (/schema/transaction_schema.yaml)
_SCHEMA_PATH = Path("schema/transaction_schema.yaml")
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

# Globals to hold preloaded catalogs in v2 mode
_CUST_CAT: pl.DataFrame | None = None
_MERCH_CAT: pl.DataFrame | None = None
_CARD_CAT: pl.DataFrame | None = None

# ISO 3166-1 alpha-2 Eurozone country codes
_EUR_COUNTRIES = [
    "AT",
    "BE",
    "DE",
    "ES",
    "FR",
    "IE",
    "IT",
    "LU",
    "NL",
    "PT",
    "FI",
    "GR",
    "SK",
    "SI",
    "EE",
    "LV",
    "LT",
    "CY",
    "MT",
]


# ── Make this a true top-level function so it can be pickled on Windows ─────────
def _init_worker(
    cust_cat: pl.DataFrame | None,
    merch_cat: pl.DataFrame | None,
    card_cat: pl.DataFrame | None,
) -> None:
    """
    Pool initializer for multiprocessing.

    Stores the provided catalog DataFrames into the module-level globals
    `_CUST_CAT`, `_MERCH_CAT`, and `_CARD_CAT` so that each worker process
    can reuse the preloaded catalogs when `cfg.realism == "v2"`.

    Must be defined at the top level (not nested) for 'picklability' under
    spawn/fork start methods on all platforms (Windows, macOS, Linux).
    """
    global _CUST_CAT, _MERCH_CAT, _CARD_CAT
    _CUST_CAT, _MERCH_CAT, _CARD_CAT = cust_cat, merch_cat, card_cat


def _make_uuid4_hex_array(rng: np.random.Generator, n: int) -> list[str]:
    """
    Generate `n` RFC-4122-compliant UUID4 strings, using the provided NumPy RNG.

    Each UUID is returned in standard hyphenated 8-4-4-4-12 form.
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

    # 4) Convert to hyphenated UUID4 strings
    return [str(uuid.UUID(int=i)) for i in ints]


# Helper for Pool.imap_unordered to unpack the args tuple
def _chunk_worker(args: tuple[int, GeneratorConfig, Optional[int]]) -> pl.DataFrame:
    """
    Multiprocessing worker wrapper.

    Unpacks the tuple `(chunk_rows, cfg, seed)` passed via `Pool.imap_unordered`
    and invokes `_generate_chunk`. Returns the resulting DataFrame.
    """
    # from .core import _generate_chunk  # avoid circular at import
    return _generate_chunk(*args)


def _generate_chunk(
    chunk_rows: int, cfg: GeneratorConfig, seed: Optional[int]
) -> pl.DataFrame:
    """
    Generate a single chunk of `chunk_rows` events using fully vectorized operations.
    """
    # ── Unpack & defaults ──────────────────────────────────────────────────────
    start_date = cfg.temporal.start_date or date.today()
    end_date = cfg.temporal.end_date or date.today()
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
        timezone=cfg.temporal.timezone,
        distribution_type=cfg.temporal.distribution_type,
        time_components=cfg.temporal.time_components,  # type: ignore
        weekday_weights=cfg.temporal.weekday_weights,
        chunk_size=cfg.temporal.chunk_size,
    )

    # ── 2) Catalogs ────────────────────────────────────────────────────────────
    if cfg.realism == "v2" and _CUST_CAT is not None:
        cust_cat, merch_cat, card_cat = _CUST_CAT, _MERCH_CAT, _CARD_CAT
    else:
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
    cust_ids = sample_entities(cust_cat, "customer_id", chunk_rows, seed=seed)
    merch_ids = sample_entities(merch_cat, "merchant_id", chunk_rows, seed=(seed or 0) + 1)  # type: ignore
    card_ids = sample_entities(card_cat, "card_id", chunk_rows, seed=(seed or 0) + 2)  # type: ignore

    # ── 4) Fraud label ─────────────────────────────────────────────────────────
    m_risk = merch_cat["risk"].to_numpy()[merch_ids - 1]  # type: ignore
    c_risk = card_cat["risk"].to_numpy()[card_ids - 1]  # type: ignore

    # ── 5) Numeric features ───────────────────────────────────────────────────
    local_time_offset = rng.integers(-720, 841, size=chunk_rows)
    if cfg.feature.amount_distribution == "lognormal":
        raw_amt = rng.lognormal(
            cfg.feature.lognormal_mean, cfg.feature.lognormal_sigma, size=chunk_rows
        )
    elif cfg.feature.amount_distribution == "normal":
        raw_amt = rng.normal(
            cfg.feature.lognormal_mean, cfg.feature.lognormal_sigma, size=chunk_rows
        )
    else:
        raw_amt = rng.uniform(
            cfg.feature.uniform_min, cfg.feature.uniform_max, size=chunk_rows
        )
    amount = np.round(raw_amt, 2)

    # ── 6) Fully‐vectorized categoricals ───────────────────────────────────────
    # device_type
    dev_keys = list(cfg.feature.device_types.keys())
    dev_wts = np.array(list(cfg.feature.device_types.values()), dtype=float)
    device_type = rng.choice(dev_keys, size=chunk_rows, p=dev_wts / dev_wts.sum())
    # card_scheme
    schemes = ["VISA", "MASTERCARD", "AMEX", "DISCOVER"]
    card_scheme = rng.choice(schemes, size=chunk_rows)
    # channel
    channels = ["ONLINE", "IN_STORE", "ATM"]
    channel = rng.choice(channels, size=chunk_rows)
    # pos_entry_mode
    modes = ["CHIP", "MAGSTRIPE", "NFC", "ECOM"]
    pos_entry_mode = rng.choice(modes, size=chunk_rows)
    # is_recurring
    is_recurring = rng.random(chunk_rows) < 0.1

    # ── 7) Currency via MCC code ───────────────────────────────────
    mcc_arr = merch_cat["mcc_code"].to_numpy()[merch_ids - 1].astype(str)  # type: ignore

    # Sample merchant_country immediately after defining it, then map to currency
    pool_n = min(chunk_rows, 100_000)
    country_pool = [_fake.country_code(representation="alpha-2") for _ in range(pool_n)]
    merchant_country = rng.choice(country_pool, size=chunk_rows)

    eur_mask = np.isin(merchant_country, _EUR_COUNTRIES)
    currency_code = np.where(eur_mask, "EUR", "USD")

    # ── 8) Other vectorizable fields ──────────────────────────────────────────
    pan_hash = np.array(card_cat["pan_hash"].to_list(), dtype=object)[card_ids - 1]  # type: ignore

    # lat/lon uniform draws
    latitude = np.round(rng.uniform(-90, 90, size=chunk_rows), 6)
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
    df = pl.DataFrame(
        {
            "transaction_id": tx_ids,
            "event_time": timestamps,
            "local_time_offset": local_time_offset,
            "amount": amount,
            "currency_code": currency_code,
            "card_pan_hash": pan_hash,
            "customer_id": cust_ids,
            "merchant_id": merch_ids,
            "merchant_country": merchant_country,
            "device_type": device_type,
            "card_scheme": card_scheme,
            "card_exp_year": rng.integers(
                start_date.year + 1, start_date.year + 6, size=chunk_rows
            ),
            "card_exp_month": rng.integers(1, 13, size=chunk_rows),
            "channel": channel,
            "pos_entry_mode": pos_entry_mode,
            "device_id": device_ids,
            "ip_address": rng.choice(
                [_fake.ipv4_public() for _ in range(pool_n)], size=chunk_rows
            ),
            "user_agent": rng.choice(
                [_fake.user_agent() for _ in range(pool_n)], size=chunk_rows
            ),
            "latitude": latitude,
            "longitude": longitude,
            "is_recurring": is_recurring,
            "previous_txn_id": [None] * chunk_rows,
            # ── INCLUDE INTERNAL RISK COLUMNS FOR LABELER ─────────────
            "merch_risk": m_risk,
            "card_risk": c_risk,
            "mcc_code": mcc_arr,
        }
    )

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
    start_time = time.perf_counter()
    last_time = start_time
    cumulative_rows = 0

    # Unpack config
    total_rows = cfg.total_rows
    start_date = cfg.temporal.start_date or date.today()
    end_date = cfg.temporal.end_date or date.today()

    # ── Temporal sanity check ─────────────────────────────────────────────────
    if end_date < start_date:
        # Make sure invalid ranges bubble up as a ValueError
        raise ValueError(
            f"Temporal sampling failed: end_date {end_date!r} is before start_date {start_date!r}"
        )

    # Pre-build & load catalogs once in v2 mode
    catalogs: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame] | None = None
    if cfg.realism == "v2":
        catalog_dir = cfg.out_dir / "catalog"
        catalog_dir.mkdir(parents=True, exist_ok=True)
        write_catalogs(catalog_dir, cfg)
        catalogs = load_catalogs(catalog_dir)

    # If configured, split into parallel chunks
    if cfg.num_workers > 1 and cfg.batch_size > 0:
        num_chunks = math.ceil(total_rows / cfg.batch_size)
        counts = [cfg.batch_size] * (num_chunks - 1) + [
            total_rows - cfg.batch_size * (num_chunks - 1)
        ]
        base_seed = cfg.seed or 0
        args = [(counts[i], cfg, base_seed + i) for i in range(num_chunks)]
        dfs: list[pl.DataFrame] = []

        # Parallel generation with per‐chunk logging, injecting catalogs via our top-level initializer
        init_args = catalogs if catalogs is not None else (None, None, None)
        with multiprocessing.Pool(
            processes=cfg.num_workers, initializer=_init_worker, initargs=init_args
        ) as pool:
            for df in pool.imap_unordered(_chunk_worker, args):
                now = time.perf_counter()
                chunk_time = now - last_time
                total_time = now - start_time
                cumulative_rows += df.height
                speed = df.height / chunk_time if chunk_time > 0 else float("inf")
                logger.info(
                    "Chunk done: %d rows in %.2f s (%.0f rows/s) — total %d/%d rows in %.2f s",
                    df.height,
                    chunk_time,
                    speed,
                    cumulative_rows,
                    total_rows,
                    total_time,
                )
                last_time = now
                dfs.append(df)

            # One global concat + schema cast
        df = pl.concat(dfs, rechunk=False)
        df = label_fraud(df, fraud_rate=cfg.fraud_rate, seed=cfg.seed)
        return df.with_columns(
            [pl.col(col).cast(_POLARS_SCHEMA[col]) for col in _COLUMNS]
        ).select(_COLUMNS)

    # Single-process fallback with logging (also set globals if v2)
    if cfg.num_workers == 1 and cfg.realism == "v2" and catalogs is not None:
        global _CUST_CAT, _MERCH_CAT, _CARD_CAT
        _CUST_CAT, _MERCH_CAT, _CARD_CAT = catalogs
    df = _generate_chunk(total_rows, cfg, cfg.seed)
    now = time.perf_counter()
    chunk_time = now - last_time
    speed = df.height / chunk_time if chunk_time > 0 else float("inf")
    logger.info(
        "Single-chunk done: %d rows in %.2f s (%.0f rows/s)",
        df.height,
        chunk_time,
        speed,
    )
    df = label_fraud(df, fraud_rate=cfg.fraud_rate, seed=cfg.seed)
    # Apply schema cast
    return df.with_columns(
        [pl.col(col).cast(_POLARS_SCHEMA[col]) for col in _COLUMNS]
    ).select(_COLUMNS)


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
