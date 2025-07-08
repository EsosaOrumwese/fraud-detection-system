import pytest
import polars as pl
from pathlib import Path

from fraud_detection.simulator.config import load_config
from fraud_detection.simulator.core import generate_dataframe
import fraud_detection.simulator.catalog as catmod

def test_chunk_reuse(tmp_path, monkeypatch):
    # ── 1) Load and tweak config for a tiny run in v2 ─────────────────────────
    project_root = Path(__file__).parents[2]
    cfg = load_config(project_root / "project_config" / "generator_config.yaml")
    cfg.realism = "v2"
    cfg.num_workers = 2
    cfg.batch_size = 5
    cfg.total_rows = 15
    cfg.catalog.num_customers = 3
    cfg.catalog.num_merchants = 4
    cfg.catalog.num_cards = 5
    # isolate out_dir so write_catalogs goes here
    cfg.out_dir = tmp_path

    # ── 2) Spy on catalog builder calls ────────────────────────────────────────
    calls = {"cust": 0, "merch": 0, "card": 0}
    def wrap(fn, key):
        def inner(*args, **kwargs):
            calls[key] += 1
            return fn(*args, **kwargs)
        return inner

    monkeypatch.setattr(catmod, "generate_customer_catalog",
                        wrap(catmod.generate_customer_catalog, "cust"))
    monkeypatch.setattr(catmod, "generate_merchant_catalog",
                        wrap(catmod.generate_merchant_catalog, "merch"))
    monkeypatch.setattr(catmod, "generate_card_catalog",
                        wrap(catmod.generate_card_catalog, "card"))

    # ── 3) Run the generator and inspect calls ────────────────────────────────
    df = generate_dataframe(cfg)

    # exactly one build each
    assert calls["cust"] == 1
    assert calls["merch"] == 1
    assert calls["card"] == 1

    # and we got the right number of rows
    assert isinstance(df, pl.DataFrame)
    assert df.height == 15
