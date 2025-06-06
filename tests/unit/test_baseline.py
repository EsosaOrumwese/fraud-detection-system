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


@pytest.mark.parametrize("n_rows", [1000, 5000])
def test_quick_auc(n_rows: int, tmp_path: pathlib.Path):
    parquet_path = generate_dataset(n_rows, tmp_path)
    # validate schema
    subprocess.run(
        [sys.executable, "scripts/ge_validate.py", str(parquet_path)], check=True
    )
    # Request only a subset for speed
    auc = quick_train(rows=200, parquet_path=parquet_path, seed=123)
    # Baseline prevalence ~0.003 → AUC-PR should be >0.005 for a learned model
    assert isinstance(auc, float)
    assert auc > 0.005


def test_model_saves(tmp_path: pathlib.Path):
    parquet_path = generate_dataset(total_rows=2000, out_dir=tmp_path)
    auc, model_path = quick_train(
        rows=500,
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
