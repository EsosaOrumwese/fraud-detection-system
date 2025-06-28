import pytest
from pathlib import Path
from datetime import date
import yaml  # type: ignore


from fraud_detection.simulator.config import load_config, GeneratorConfig  # type: ignore

# Helper to locate the example YAML
CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "project_config" / "generator_config.yaml"
)


def test_load_valid_config():
    cfg = load_config(CONFIG_PATH)
    # Check top-level fields
    assert isinstance(cfg, GeneratorConfig)
    assert cfg.total_rows == 1000000
    assert 0 <= cfg.fraud_rate <= 1
    assert cfg.seed == 42
    # Catalog
    cat = cfg.catalog
    assert cat.num_customers == 50000
    # Temporal
    temp = cfg.temporal
    assert temp.start_date == date(2025, 6, 1)
    assert temp.end_date == date(2025, 6, 30)
    # I/O flags
    assert cfg.out_dir == Path("outputs")
    assert not cfg.s3_upload


def test_missing_config_file(tmp_path):
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError):
        load_config(missing)


def test_invalid_yaml_syntax(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("::: not_yaml")
    with pytest.raises(ValueError):
        load_config(bad)


def test_extra_fields_forbidden(tmp_path):
    # Copy valid config, add an extra key
    data = yaml.safe_load(CONFIG_PATH.read_text())
    data["unexpected"] = "oops"
    f = tmp_path / "extra.yaml"
    f.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError) as exc:
        load_config(f)
    assert "unexpected" in str(exc.value)


def test_missing_sections(tmp_path):
    # Remove the 'catalog' section entirely
    data = yaml.safe_load(CONFIG_PATH.read_text())
    data.pop("catalog", None)
    f = tmp_path / "nocatalog.yaml"
    f.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError) as exc:
        load_config(f)
    assert "Missing required `catalog`" in str(exc.value)

    # Remove the 'temporal' section
    data = yaml.safe_load(CONFIG_PATH.read_text())
    data.pop("temporal", None)
    f2 = tmp_path / "notemporal.yaml"
    f2.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError) as exc2:
        load_config(f2)
    assert "Missing required `temporal`" in str(exc2.value)


def test_date_order_validation(tmp_path):
    # Swap dates so end < start
    data = yaml.safe_load(CONFIG_PATH.read_text())
    data["temporal"]["start_date"] = "2025-07-01"
    data["temporal"]["end_date"] = "2025-06-01"
    f = tmp_path / "baddates.yaml"
    f.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError) as exc:
        load_config(f)
    assert "end_date must be on or after start_date" in str(exc.value)


def test_out_dir_coercion(tmp_path):
    # Provide out_dir as a string instead of Path
    data = yaml.safe_load(CONFIG_PATH.read_text())
    data["out_dir"] = "custom_outputs"
    f = tmp_path / "custom_out.yaml"
    f.write_text(yaml.safe_dump(data))
    cfg = load_config(f)
    assert isinstance(cfg.out_dir, Path)
    assert cfg.out_dir == Path("custom_outputs")
