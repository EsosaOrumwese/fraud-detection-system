# tests/test_cli_stage5.py

import sys
import json
import logging
import pytest
import tempfile
import yaml  # type: ignore
import polars as pl

from pathlib import Path

import fraud_detection.simulator.cli as cli_mod  # type: ignore
from fraud_detection.simulator.core import generate_dataframe as real_generate_dataframe  # type: ignore

@pytest.fixture(autouse=True)
def isolate_argv_and_env(monkeypatch):
    """Ensure each test gets a clean sys.argv."""
    orig_argv = sys.argv.copy()
    yield
    sys.argv = orig_argv

def write_minimal_config(tmp_path, **temporal_overrides):
    """Emit a minimal valid generator_config.yaml and return its path."""
    cfg = {
        "total_rows": 10,
        "fraud_rate": 0.1,
        "seed": 123,
        "realism": "v1",
        "num_workers": 1,
        "batch_size": 10,
        "catalog": {
            "num_customers": 10,
            "customer_zipf_exponent": 1.0,
            "num_merchants": 5,
            "merchant_zipf_exponent": 1.0,
            "merchant_risk_alpha": 1.0,
            "merchant_risk_beta": 1.0,
            "num_cards": 20,
            "card_zipf_exponent": 1.0,
            "card_risk_alpha": 1.0,
            "card_risk_beta": 1.0,
            "max_size_mb": 1,
            "parquet_row_group_size": 1
        },
        "temporal": {
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
            "weekday_weights": None,
            "time_components": None,
            "distribution_type": "gaussian",
            "chunk_size": None,
            **temporal_overrides
        },
        "feature": {
            "device_types": {"IOS": 0.5, "ANDROID": 0.5},
            "amount_distribution": "uniform",
            "lognormal_mean": 1.0,
            "lognormal_sigma": 1.0,
            "uniform_min": 1.0,
            "uniform_max": 10.0
        },
        "out_dir": str(tmp_path / "out"),
        "s3_upload": False
    }
    cfg_path = tmp_path / "generator_config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    return cfg_path

def test_empty_weekday_weights_becomes_uniform(tmp_path, monkeypatch):
    # Arrange: write base config
    cfg_path = write_minimal_config(tmp_path)

    # Intercept the actual generation call to capture the final cfg
    captured = {}
    def fake_generate(cfg):
        captured['cfg'] = cfg
        return pl.DataFrame()  # satisfy return type for Polars-based generator
    monkeypatch.setattr(cli_mod, 'generate_dataframe', fake_generate)

    # Act: invoke CLI with an empty JSON override for weekday_weights
    sys.argv = [
        "prog",
        "--config", str(cfg_path),
        "--weekday-weights", "{}"
    ]
    # Force INFO logs to console for any assertions
    logging.basicConfig(level=logging.INFO)

    cli_mod.main()

    # Assert: weekday_weights was turned into {0:1.0, ..., 6:1.0}
    final_ws = captured['cfg'].temporal.weekday_weights
    assert isinstance(final_ws, dict), "Should be a dict"
    assert set(final_ws.keys()) == set(range(7)), "Must cover all 7 weekdays"
    assert all(weight == 1.0 for weight in final_ws.values()), "All weights should be 1.0"

def test_malformed_weekday_weights_json_exits_with_error(monkeypatch, tmp_path, caplog):
    cfg_path = write_minimal_config(tmp_path)
    # Act & Assert: invalid JSON should SystemExit(1) with appropriate log
    sys.argv = [
        "prog",
        "--config", str(cfg_path),
        "--weekday-weights", "{not: valid json"
    ]
    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as exc:
        cli_mod.main()
    assert exc.value.code == 1
    assert "Invalid JSON for --weekday-weights" in caplog.text

def test_chunk_size_zero_exits_with_error(monkeypatch, tmp_path, caplog):
    cfg_path = write_minimal_config(tmp_path)
    # Act & Assert: chunk_size <= 0 should be rejected
    sys.argv = [
        "prog",
        "--config", str(cfg_path),
        "--chunk-size", "0"
    ]
    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as exc:
        cli_mod.main()
    assert exc.value.code == 1
    assert "--chunk-size must be > 0" in caplog.text

def test_time_components_override_and_merge(tmp_path, monkeypatch):
    # Provide a custom single-component time mixture
    custom_tc = [{"mean_hour": 0.0, "std_hours": 0.1, "weight": 1.0}]
    cfg_path = write_minimal_config(tmp_path)

    captured = {}

    def fake_generate(cfg):
        captured['cfg'] = cfg
        return pl.DataFrame()

    monkeypatch.setattr(cli_mod, 'generate_dataframe', fake_generate)

    sys.argv = [
        "prog",
        "--config", str(cfg_path),
        "--time-components", json.dumps(custom_tc)
    ]
    cli_mod.main()

    # Assert that the final config uses exactly that single component
    final_tc = captured['cfg'].temporal.time_components
    assert len(final_tc) == 1
    comp = final_tc[0]
    assert comp.mean_hour == 0.0
    assert comp.std_hours == 0.1
    assert comp.weight == 1.0

def test_full_override_precedence(tmp_path, monkeypatch):
    # Test that CLI overrides > file > defaults
    base_w = {0: 0.1, 6: 0.9}
    cfg_path = write_minimal_config(tmp_path, weekday_weights=base_w, chunk_size=5)

    captured = {}

    def fake_generate(cfg):
        captured['cfg'] = cfg
        return pl.DataFrame()

    monkeypatch.setattr(cli_mod, 'generate_dataframe', fake_generate)

    # Override both weekday_weights and chunk_size
    override_w = {2: 2.0}
    sys.argv = [
        "prog",
        "--config", str(cfg_path),
        "--weekday-weights", json.dumps(override_w),
        "--chunk-size", "42"
    ]
    cli_mod.main()

    # weekday_weights: base {0:0.1,6:0.9} merged with override {2:2.0} → {0:0.1,6:0.9,2:2.0}
    fw = captured['cfg'].temporal.weekday_weights
    assert fw[0] == 0.1 and fw[6] == 0.9 and fw[2] == 2.0

    # chunk_size must be the CLI value
    assert captured['cfg'].temporal.chunk_size == 42
