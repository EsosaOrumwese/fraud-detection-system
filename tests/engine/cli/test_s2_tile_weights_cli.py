from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
import yaml

from engine.cli import s2_tile_weights as s2_cli


def _write_iso_table(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"country_iso": ["AA", "BB"]}).write_parquet(path)


def _write_tile_index_partition(base_path: Path, parameter_hash: str) -> Path:
    partition_dir = base_path / f"data/layer1/1B/tile_index/parameter_hash={parameter_hash}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(
        {
            "country_iso": ["AA", "AA", "BB"],
            "tile_id": [0, 1, 0],
            "raster_row": [0, 0, 1],
            "raster_col": [0, 1, 0],
            "pixel_area_m2": [10.0, 12.0, 9.5],
        }
    )
    frame.write_parquet(partition_dir / "part-00000.parquet")
    return partition_dir


def _write_dictionary(path: Path, data_root: Path) -> None:
    dictionary = {
        "reference_data": {
            "iso3166_canonical_2024": {
                "path": "reference/iso/iso3166_canonical.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
                "version": "test",
            },
        },
        "datasets": {
            "tile_index": {
                "path": "data/layer1/1B/tile_index/parameter_hash={parameter_hash}/",
                "partitioning": ["parameter_hash"],
                "ordering": ["country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/prep/tile_index",
                "version": "{parameter_hash}",
            },
            "tile_weights": {
                "path": "data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/",
                "partitioning": ["parameter_hash"],
                "ordering": ["country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/prep/tile_weights",
                "version": "{parameter_hash}",
            },
        },
    }
    path.write_text(yaml.safe_dump(dictionary), encoding="utf-8")


@pytest.fixture()
def cli_environment(tmp_path: Path) -> tuple[Path, Path]:
    data_root = tmp_path
    dictionary_path = data_root / "dictionary.yaml"
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet")
    _write_tile_index_partition(data_root, "abc123")
    _write_dictionary(dictionary_path, data_root)
    return data_root, dictionary_path


def test_cli_run_and_validate(cli_environment: tuple[Path, Path]) -> None:
    data_root, dictionary_path = cli_environment

    exit_code = s2_cli.main(
        [
            "run",
            "--data-root",
            str(data_root),
            "--parameter-hash",
            "abc123",
            "--basis",
            "uniform",
            "--dp",
            "2",
            "--dictionary",
            str(dictionary_path),
        ]
    )
    assert exit_code == 0

    partition_path = (
        data_root / "data/layer1/1B/tile_weights/parameter_hash=abc123"
    )
    assert partition_path.exists()
    dataset_df = pl.read_parquet(partition_path / "part-00000.parquet")
    assert dataset_df.height == 3

    report_path = (
        data_root
        / "control"
        / "s2_tile_weights"
        / "parameter_hash=abc123"
        / "s2_run_report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["basis"] == "uniform"
    assert report["determinism_receipt"]["sha256_hex"]

    exit_code = s2_cli.main(
        [
            "validate",
            "--data-root",
            str(data_root),
            "--parameter-hash",
            "abc123",
            "--dictionary",
            str(dictionary_path),
        ]
    )
    assert exit_code == 0
