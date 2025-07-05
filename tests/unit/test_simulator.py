import polars as pl
import pathlib
import yaml  # type: ignore

from fraud_detection.simulator.config import load_config  # type: ignore
from fraud_detection.simulator.generate import generate_dataset  # type: ignore

# Load schema once (relative to repository root)
BASE_DIR = pathlib.Path(__file__).parents[2]  # tests/unit → repo root
SCHEMA_PATH = BASE_DIR / "schema" / "transaction_schema.yaml"
CONFIG_PATH = BASE_DIR / "project_config" / "generator_config.yaml"
SCHEMA = yaml.safe_load(SCHEMA_PATH.read_text())


def test_schema(tmp_path):
    """
    Generate 50k rows, read back zero rows to inspect column names,
    and assert they match exactly the names in transaction_schema.yaml.
    """
    # 1) Load your standard YAML config
    cfg = load_config(CONFIG_PATH)
    # 2) Override just the row-count and output directory
    cfg.total_rows = 50000
    cfg.out_dir     = tmp_path
    cfg.fraud_rate  = 0.03

    p = generate_dataset(cfg)
    cols = pl.read_parquet(p, n_rows=0).columns
    expected = {field_dict["name"] for field_dict in SCHEMA["fields"]}
    assert set(cols) == expected


def test_fraud_rate(tmp_path):
    """
    Generate 50k rows, read back all, compute mean(label_fraud),
    and assert it falls within [0.02, 0.04] (±4σ around 0.03).
    """
    # 1) Load your standard YAML config
    cfg = load_config(CONFIG_PATH)
    # 2) Override just the row-count and output directory
    cfg.total_rows = 50000
    cfg.out_dir = tmp_path
    cfg.fraud_rate = 0.03

    p = generate_dataset(cfg)
    rate = pl.read_parquet(p).select(pl.col("label_fraud").mean()).item()
    assert 0.02 <= rate <= 0.04


def test_row_count(tmp_path):
    """
    Confirms the correct row count. Can be used to catch accidental
    off-by-one bugs (e.g., generating 9 999 or 10 001 rows).
    """
    # 1) Load your standard YAML config
    cfg = load_config(CONFIG_PATH)
    # 2) Override just the row-count and output directory
    cfg.total_rows = 10000
    cfg.out_dir     = tmp_path
    cfg.fraud_rate  = 0.03

    p = generate_dataset(cfg)
    cnt = pl.read_parquet(p).height  # Or: pl.read_parquet(p).shape[0]
    assert cnt == 10_000
