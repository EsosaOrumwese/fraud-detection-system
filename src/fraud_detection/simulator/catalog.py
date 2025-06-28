"""
Entity‐catalog generation and sampling driven by Zipf distributions.
"""

from __future__ import annotations
from typing import Optional

import numpy as np
from numpy.random import Generator, default_rng
import polars as pl


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
    Build a customer catalog with Zipf-based sampling weights.

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
        - weight (float64): sampling probability
    """
    ids = np.arange(1, num_customers + 1, dtype=np.int32)
    weights = _zipf_weights(num_customers, zipf_exponent)
    return pl.DataFrame(
        {
            "customer_id": ids,
            "weight": weights.astype(np.float64),
        }
    )


def generate_merchant_catalog(
    num_merchants: int,
    zipf_exponent: float = 1.2,
) -> pl.DataFrame:
    """
    Build a merchant catalog with Zipf-based sampling weights.

    Parameters
    ----------
    num_merchants : int
        Total unique merchants to generate.
    zipf_exponent : float
        Zipf exponent for merchant popularity.

    Returns
    -------
    pl.DataFrame
        with columns:
        - merchant_id (int32): 1...num_merchants
        - weight (float64): sampling probability
    """
    ids = np.arange(1, num_merchants + 1, dtype=np.int32)
    weights = _zipf_weights(num_merchants, zipf_exponent)
    return pl.DataFrame(
        {
            "merchant_id": ids,
            "weight": weights.astype(np.float64),
        }
    )


def generate_card_catalog(
    num_cards: int,
    zipf_exponent: float = 1.0,
) -> pl.DataFrame:
    """
    Build a card catalog with Zipf-based sampling weights.

    Parameters
    ----------
    num_cards : int
        Total unique cards to generate.
    zipf_exponent : float
        Zipf exponent for card usage (default 1.0 for mild skew).

    Returns
    -------
    pl.DataFrame
        with columns:
        - card_id (int32): 1...num_cards
        - weight (float64): sampling probability
    """
    ids = np.arange(1, num_cards + 1, dtype=np.int32)
    weights = _zipf_weights(num_cards, zipf_exponent)
    return pl.DataFrame(
        {
            "card_id": ids,
            "weight": weights.astype(np.float64),
        }
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
    rng: Generator = default_rng(seed)
    return rng.choice(ids, size=size, p=p)
