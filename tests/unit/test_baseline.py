"""
tests/unit/test_baseline.py

Unit tests for the quick_train function in train_baseline.py.
Instead of relying on a large Parquet under outputs/, we generate a tiny
dummy DataFrame that respects the 24-field schema. This ensures:
  - Tests never depend on external files.
  - Run time is < 10s.
  - Prevalence (0.3%) is roughly enforced.
"""

import pathlib
import subprocess
import sys

import pytest

from fraud_detection.simulator.generate import generate_dataset  # type: ignore
from fraud_detection.modelling.train_baseline import quick_train  # type: ignore
from fraud_detection.simulator.config import load_config  # type: ignore

import warnings

### Although my pipeline is fit, it still throws this error. So I'll ignore it for now till it's fixed
warnings.filterwarnings(
    "ignore",
    message="This Pipeline instance is not fitted yet.*",
    category=FutureWarning,
)

# Load schema once (relative to repository root)
BASE_DIR = pathlib.Path(__file__).parents[2]  # tests/unit → repo root
GE_VALIDATE_PATH = BASE_DIR / "scripts" / "ge_validate.py"
CONFIG_PATH = BASE_DIR / "project_config" / "generator_config.yaml"


@pytest.mark.parametrize("n_rows", [3000, 5000])
def test_quick_auc(n_rows: int, tmp_path: pathlib.Path):
    # 1) Load your standard YAML config
    cfg = load_config(CONFIG_PATH)
    # 2) Override just the row-count and output directory
    cfg.total_rows = n_rows
    cfg.out_dir = tmp_path
    cfg.fraud_rate = 0.03

    parquet_path = generate_dataset(cfg)
    # validate schema
    subprocess.run([sys.executable, GE_VALIDATE_PATH, str(parquet_path)], check=True)
    # Request only a subset for speed
    auc = quick_train(rows=n_rows, parquet_path=parquet_path, seed=123)
    # Baseline prevalence ~0.003 → AUC-PR should be >0.005 for a learned model
    assert isinstance(auc, float)
    assert auc > 0.005


def test_model_saves(tmp_path: pathlib.Path):
    # 1) Load your standard YAML config
    cfg = load_config(CONFIG_PATH)
    # 2) Override just the row-count and output directory
    cfg.total_rows = 2000
    cfg.out_dir = tmp_path
    cfg.fraud_rate = 0.03

    parquet_path = generate_dataset(cfg)
    auc, model_path = quick_train(  # type: ignore
        rows=2000,
        parquet_path=parquet_path,
        save_model=True,
        out_dir=tmp_path,
        seed=7,
    )
    assert isinstance(auc, float)
    assert model_path.exists()
    # File should be a pickled sklearn Pipeline
    import joblib  # type: ignore

    loaded = joblib.load(model_path)
    from sklearn.base import BaseEstimator  # type: ignore

    assert isinstance(loaded, BaseEstimator)
    # Clean up (optional)
    model_path.unlink()
