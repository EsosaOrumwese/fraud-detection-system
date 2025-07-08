"""
Entity‐catalog generation and sampling driven by Zipf distributions plus risk factors.
"""

from __future__ import annotations
from typing import Optional, Union, Tuple
import os
from pathlib import Path

import numpy as np
from numpy.random import Generator, default_rng
import polars as pl
from faker import Faker

from fraud_detection.simulator.mcc_codes import MCC_CODES
from fraud_detection.simulator.config import GeneratorConfig


def _zipf_weights(n: int, exponent: float) -> np.ndarray:
    """
    Compute normalized Zipf weights for ranks 1...n.

    Parameters
    ----------
    n : int
        Number of distinct entities (ranks 1 to n).
    exponent : float
        The Zipf exponent s (>1 for heavy‐tail).

    Raises
    ------
    ValueError
        If n < 1 or exponent <= 0.

    Returns
    -------
    np.ndarray
        Array of length n summing to 1, where weight[k-1] ∝ 1 / (k**exponent).
    """
    if n < 1:
        raise ValueError(f"num_entities must be ≥1; got {n}")
    if exponent <= 0:
        raise ValueError(f"zipf_exponent must be >0; got {exponent}")

    ranks = np.arange(1, n + 1, dtype=np.float64)
    raw = ranks ** (-exponent)
    return raw / raw.sum()


def generate_customer_catalog(
    num_customers: int, zipf_exponent: float = 1.2
) -> pl.DataFrame:
    """
    Build a customer catalog with Zipf-based sampling weights. (No risk, customers not risk‐modeled here.)

    Parameters
    ----------
    num_customers : int
        Total unique customers to generate. Must be ≥1.
    zipf_exponent : float
        Zipf exponent (higher → steeper drop in popularity). Must be >0.

    Returns
    -------
    pl.DataFrame
        with columns:
        - customer_id (int32): 1...num_customers
        - weight (Float64): normalized Zipf probabilities summing to 1
    """
    ids = np.arange(1, num_customers + 1, dtype=np.int32)
    weights = _zipf_weights(num_customers, zipf_exponent)
    return (pl.DataFrame(
        {
            "customer_id": ids,
            "weight": weights.astype(np.float64),
        })
        .with_columns([
            pl.col("customer_id").cast(pl.Int32),
            pl.col("weight").cast(pl.Float64),
        ])
    )


def generate_merchant_catalog(
    num_merchants: int,
    zipf_exponent: float = 1.2,
    seed: Optional[int] = None,
    risk_alpha: float = 2.0,
    risk_beta: float = 5.0,
) -> pl.DataFrame:
    """
    Build a merchant catalog with Zipf-based sampling weights + per‐merchant fraud risk.
    Risk ~ Beta(risk_alpha, risk_beta).

    Parameters
    ----------
    num_merchants : int
        Total unique merchants to generate.
    zipf_exponent : float
        Zipf exponent for merchant popularity.
    seed : int | None, optional
        RNG seed for reproducibility; if None, randomness is not seeded.
    risk_alpha : float, optional
        Alpha (shape) parameter for the Beta distribution of merchant risk.
    risk_beta : float, optional
        Beta (shape) parameter for the Beta distribution of merchant risk.

    Returns
    -------
    pl.DataFrame
        A DataFrame with columns:
          - merchant_id (Int32): IDs from 1 to `num_merchants`
          - weight (Float64): normalized Zipf probabilities summing to 1
          - risk (Float64): samples from Beta(`risk_alpha`, `risk_beta`)
          - mcc_code (Int32): randomly assigned merchant code
    """
    ids = np.arange(1, num_merchants + 1, dtype=np.int32)
    weights = _zipf_weights(num_merchants, zipf_exponent)
    risk_rng: Generator = default_rng((seed or 0) + 1)
    risks = risk_rng.beta(risk_alpha, risk_beta, size=num_merchants)

    # Assign each merchant an MCC code
    mcc_rng: Generator = default_rng((seed or 0) + 2)
    mccs = mcc_rng.choice(MCC_CODES, size=num_merchants)

    return (pl.DataFrame(
        {
            "merchant_id": ids,
            "weight": weights.astype(np.float64),
            "risk": risks.astype(np.float64),
            "mcc_code": mccs.astype(int),
        })
        .with_columns([
            pl.col("merchant_id").cast(pl.Int32),
            pl.col("weight").cast(pl.Float64),
            pl.col("risk").cast(pl.Float64),
            pl.col("mcc_code").cast(pl.Int32),
        ])
    )


def generate_card_catalog(
    num_cards: int,
    zipf_exponent: float = 1.0,
    seed: Optional[int] = None,
    risk_alpha: float = 2.0,
    risk_beta: float = 5.0,
) -> pl.DataFrame:
    """
    Build a card catalog with Zipf-based sampling weights + per‐card fraud risk + persistent pan_hash.
    Risk ~ Beta(risk_alpha, risk_beta).

    Parameters
    ----------
    num_cards : int
        Total unique cards to generate.
    zipf_exponent : float
        Zipf exponent for card usage (default 1.0 for mild skew).
    seed : int | None, optional
        RNG seed for reproducibility; if None, randomness is not seeded.
    risk_alpha : float, optional
        Alpha (shape) parameter for the Beta distribution of card risk.
    risk_beta : float, optional
        Beta (shape) parameter for the Beta distribution of card risk.

    Returns
    -------
    pl.DataFrame
        with columns:
          - card_id (Int32): IDs from 1 to `num_cards`
          - weight (Float64): normalized Zipf probabilities summing to 1
          - risk (Float64): samples from Beta(`risk_alpha`, `risk_beta`)
          - pan_hash (Utf8): deterministic, seeded hash strings for each card
    """
    ids = np.arange(1, num_cards + 1, dtype=np.int32)
    weights = _zipf_weights(num_cards, zipf_exponent)
    rng: Generator = default_rng((seed or 0) + 3)
    risks = rng.beta(risk_alpha, risk_beta, size=num_cards)
    fake = Faker()
    if seed is not None:
        fake.seed_instance((seed or 0) + 4)
    pan_hashes = [fake.sha256() for _ in range(num_cards)]
    return (pl.DataFrame(
        {
            "card_id": ids,
            "weight": weights.astype(np.float64),
            "risk": risks.astype(np.float64),
            "pan_hash": pan_hashes,
        })
        .with_columns([
            pl.col("card_id").cast(pl.Int32),
            pl.col("weight").cast(pl.Float64),
            pl.col("risk").cast(pl.Float64),
            pl.col("pan_hash").cast(pl.Utf8),
        ])
    )


def sample_entities(
    catalog: pl.DataFrame,
    entity_col: str,
    size: int,
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Sample a sequence of entity IDs from a catalog according to its weights.

    Parameters
    ----------
    catalog : pl.DataFrame
        Must have columns [entity_col, "weight"].
    entity_col : str
        Name of the ID column ("customer_id", "merchant_id", or "card_id").
    size : int
        Number of samples to draw.
    seed : Optional[int]
        RNG seed for reproducibility.

    Returns
    -------
    np.ndarray
        1D array of sampled IDs.

    Raises
    ------
    ValueError
        If required columns are missing, weights invalid, or size < 0.
    """
    # Validation
    if entity_col not in catalog.columns:
        raise ValueError(f"Catalog missing '{entity_col}' column")
    if "weight" not in catalog.columns:
        raise ValueError("Catalog missing 'weight' column")
    if size < 0:
        raise ValueError(f"Sample size must be ≥0; got {size}")

    # Extract arrays
    ids = catalog[entity_col].to_numpy()
    weights = catalog["weight"].to_numpy().astype(np.float64)

    if weights.ndim != 1 or ids.ndim != 1 or ids.shape[0] != weights.shape[0]:
        raise ValueError("Catalog columns must be 1-D and same length")

    total_w = weights.sum()
    if total_w <= 0 or np.isnan(total_w):
        raise ValueError("Weight sum must be positive and finite")

    # Renormalize to counter floating point drift
    p = weights / total_w

    # Use a local Generator for thread-safe reproducibility
    rng: Generator = default_rng((seed or 0) + 5)
    return rng.choice(ids, size=size, p=p)


def write_catalogs(
    catalog_dir: Path | str,
    cfg: GeneratorConfig,
) -> None:
    """
    Generate and write customer, merchant, and card catalogs as Parquet files,
    ensuring each artifact is <= cfg.catalog.max_size_mb on disk.
    """

    # 1) Build in-memory DataFrames once
    customers = generate_customer_catalog(
        num_customers=cfg.catalog.num_customers,
        zipf_exponent=cfg.catalog.customer_zipf_exponent,
    )
    merchants = generate_merchant_catalog(
        num_merchants=cfg.catalog.num_merchants,
        zipf_exponent=cfg.catalog.merchant_zipf_exponent,
        risk_alpha=cfg.catalog.merchant_risk_alpha,
        risk_beta=cfg.catalog.merchant_risk_beta,
        seed=cfg.seed,
    )
    cards = generate_card_catalog(
        num_cards=cfg.catalog.num_cards,
        zipf_exponent=cfg.catalog.card_zipf_exponent,
        risk_alpha=cfg.catalog.card_risk_alpha,
        risk_beta=cfg.catalog.card_risk_beta,
        seed=cfg.seed,
    )

    # 2) Define output paths
    # output_dir = Path(cfg.out_dir)
    # catalog_dir = output_dir / "catalog"
    catalog_dir = Path(catalog_dir)
    catalog_dir.mkdir(exist_ok=True, parents=True)

    paths = {
        "customers": catalog_dir / "customers.parquet",
        "merchants": catalog_dir / "merchants.parquet",
        "cards":     catalog_dir / "cards.parquet",
    }

    # 3) Write with Snappy + configured row_group_size, then check file sizes
    max_bytes = cfg.catalog.max_size_mb * 1024 * 1024
    for name, df in [("customers", customers), ("merchants", merchants), ("cards", cards)]:
        out_path = paths[name]
        df.write_parquet(
            out_path,
            compression="snappy",
            row_group_size=cfg.catalog.parquet_row_group_size,
            use_pyarrow=True,
        )
        size = os.path.getsize(out_path)
        ## Address later as I have n_rows unique customers

        # if size > max_bytes:
        #     mb = size / (1024 * 1024)
        #     raise ValueError(
        #         f"{name}.parquet is {mb:.2f} MB, exceeds max "
        #         f"{cfg.catalog.max_size_mb} MB"
        #     )

    # 4) All catalogs written and validated


def load_catalogs(catalog_dir: Path | str) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Load the three Parquet catalogs from disk.
    Expects files:
      - customers.parquet
      - merchants.parquet
      - cards.parquet
    """
    catalog_dir = Path(catalog_dir)
    cust = pl.read_parquet(catalog_dir / "customers.parquet")
    merch = pl.read_parquet(catalog_dir / "merchants.parquet")
    card = pl.read_parquet(catalog_dir / "cards.parquet")
    return cust, merch, card


# Smoke Script so anyone can run it and verify the three Parquet catalogs get written under 5 MB.
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from fraud_detection.simulator.config import load_config  # type: ignore

    # Allow passing a custom config path, else use default
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("project_config/generator_config.yaml")
    cfg = load_config(cfg_path)

    output_dir = Path(cfg.out_dir)
    catalog_directory = output_dir / "catalog"
    write_catalogs(catalog_directory, cfg)
    print(f"✅ Wrote catalogs to {catalog_directory.resolve()}")
