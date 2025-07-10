import pytest
import polars as pl
from pathlib import Path

from fraud_detection.simulator.config import load_config
from fraud_detection.simulator.catalog import write_catalogs, load_catalogs


def test_load_catalogs_roundtrip(tmp_path):
    # ── 1) Load your real config and override for speed & isolation ─────────
    project_root = Path(__file__).parents[2]
    cfg = load_config(project_root / "project_config" / "generator_config.yaml")
    # tiny catalogs for fast tests
    cfg.catalog.num_customers = 10
    cfg.catalog.num_merchants = 15
    cfg.catalog.num_cards = 20
    # isolate out_dir
    cfg.out_dir = tmp_path

    # ── 2) Write and then load ────────────────────────────────────────────────
    write_catalogs(tmp_path, cfg)
    cust, merch, card = load_catalogs(tmp_path)

    # ── 3) Sanity checks ─────────────────────────────────────────────────────
    assert isinstance(cust, pl.DataFrame)
    assert isinstance(merch, pl.DataFrame)
    assert isinstance(card, pl.DataFrame)

    # correct row counts
    assert cust.height == 10
    assert merch.height == 15
    assert card.height == 20

    # weights normalized
    assert cust["weight"].sum() == pytest.approx(1.0)
    assert merch["weight"].sum() == pytest.approx(1.0)
    assert card["weight"].sum() == pytest.approx(1.0)
