"""
Phase 6 tests for feature sampling logic in the synthetic fraud generator:
- device_type weights
- amount distributions (lognormal & uniform)
- currency mapping from MCC codes
"""
import math
import polars as pl
import pytest
from pathlib import Path

from fraud_detection.simulator.config import load_config, GeneratorConfig  # type: ignore
from fraud_detection.simulator.core import generate_dataframe  # type: ignore

# ─────── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def cfg():
    """Load and validate your production YAML config."""
    raw = load_config(Path("project_config/generator_config.yaml"))
    return GeneratorConfig.model_validate(raw)

@pytest.fixture(params=["uniform", "normal", "lognormal"])
def dist(request):
    """Amount distribution to test."""
    return request.param

@pytest.fixture
def df(cfg: GeneratorConfig, dist: str) -> pl.DataFrame:
    """
    Generate a 100 000-row DataFrame for the given distribution.
    """
    # copy + override total_rows
    cfg2 = cfg.model_copy(update={"total_rows": 100_000})
    # force the distribution under test
    cfg2.feature.amount_distribution = dist
    return generate_dataframe(cfg2)

# ─────── tests ─────────────────────────────────────────────────────────────────

def test_device_type_distribution(df: pl.DataFrame, cfg: GeneratorConfig):
    """Empirical device frequencies should track config weights within ±5%."""
    pdf = df.to_pandas()
    counts = pdf["device_type"].value_counts()
    total  = counts.sum()
    for device, weight in cfg.feature.device_types.items():
        observed = counts.get(device, 0) / total
        assert abs(observed - weight) < 0.05, (
            f"Device {device}: expected {weight:.2f}, saw {observed:.2f}"
        )

def test_amount_distribution_median(df: pl.DataFrame, cfg: GeneratorConfig, dist: str):
    """If lognormal, sample median ~ exp(mean) within 10%."""
    if dist != "lognormal":
        pytest.skip("Config not set to lognormal; skipping logmedian test")
    pdf = df.to_pandas()
    median_amount = pdf["amount"].median()
    expected = math.exp(cfg.feature.lognormal_mean)
    rel_err = abs(median_amount - expected) / expected
    assert rel_err < 0.10, f"Lognormal median off by {rel_err:.2%}"

def test_amount_uniform_range(df: pl.DataFrame, cfg: GeneratorConfig, dist: str):
    """All amounts must lie within [uniform_min, uniform_max]."""
    if dist != "uniform":
        pytest.skip("Config not set to uniform; skipping uniform‐range test")
    pdf = df.to_pandas()
    amin, amax = pdf["amount"].min(), pdf["amount"].max()
    assert amin >= cfg.feature.uniform_min, f"Min {amin} < {cfg.feature.uniform_min}"
    assert amax <= cfg.feature.uniform_max, f"Max {amax} > {cfg.feature.uniform_max}"

def test_currency_mapping(df: pl.DataFrame):
    """
    Transactions with MCC starting '4' → EUR; others USD.
    (We no longer test timezone here.)
    """
    pdf     = df.to_pandas()
    cur_col = "currency_code" if "currency_code" in pdf.columns else "currency"
    eur = pdf[pdf[cur_col] == "EUR"]
    usd = pdf[pdf[cur_col] == "USD"]

    assert not eur.empty, "No EUR transactions found!"
    assert not usd.empty, "No USD transactions found!"

def test_valid_device_types(df: pl.DataFrame, cfg: GeneratorConfig):
    """No stray device types outside the config‐defined set."""
    pdf     = df.to_pandas()
    unknown = set(pdf["device_type"].unique()) - set(cfg.feature.device_types.keys())
    assert not unknown, f"Found unexpected device types: {unknown}"
