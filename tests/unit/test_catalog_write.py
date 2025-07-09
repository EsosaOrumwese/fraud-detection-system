from pathlib import Path

from fraud_detection.simulator.catalog import write_catalogs  # type: ignore
from fraud_detection.simulator.config import load_config  # type: ignore


def test_write_catalogs(tmp_path: Path):
    # Load the master config and shrink catalogs so test runs small
    cfg = load_config(Path("project_config/generator_config.yaml"))
    cfg.catalog.num_customers = 10
    cfg.catalog.num_merchants = 5
    cfg.catalog.num_cards = 8

    # Run the writer
    write_catalogs(tmp_path, cfg)

    # Verify each file exists and is within size bounds
    for name in ["customers", "merchants", "cards"]:
        p = tmp_path / f"{name}.parquet"
        assert p.exists(), f"{name}.parquet not found"
        size = p.stat().st_size
        assert size > 0, "Empty file written"
        assert (
            size <= cfg.catalog.max_size_mb * 1024 * 1024
        ), f"{name}.parquet is {size/(1024*1024):.2f} MB, exceeds {cfg.catalog.max_size_mb} MB"
