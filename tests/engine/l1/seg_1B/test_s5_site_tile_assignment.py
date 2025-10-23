from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_1B import (
    S5RunnerConfig,
    S5SiteTileAssignmentRunner,
    S5SiteTileAssignmentValidator,
    S5ValidatorConfig,
)
from engine.layers.l1.seg_1B.s5_site_tile_assignment.exceptions import S5Error


def _dictionary() -> dict[str, object]:
    return {
        "datasets": {
            "s4_alloc_plan": {
                "path": "data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/",
                "partitioning": ["seed", "fingerprint", "parameter_hash"],
                "ordering": ["merchant_id", "legal_country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/plan/s4_alloc_plan",
            },
            "tile_index": {
                "path": "data/layer1/1B/tile_index/parameter_hash={parameter_hash}/",
                "partitioning": ["parameter_hash"],
                "ordering": ["country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/prep/tile_index",
            },
            "s5_site_tile_assignment": {
                "path": "data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/",
                "partitioning": ["seed", "fingerprint", "parameter_hash"],
                "ordering": ["merchant_id", "legal_country_iso", "site_order"],
                "schema_ref": "schemas.1B.yaml#/plan/s5_site_tile_assignment",
            },
            "s5_run_report": {
                "path": "control/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s5_run_report.json",
                "partitioning": ["seed", "fingerprint", "parameter_hash"],
                "ordering": [],
            },
        },
        "reference_data": {
            "iso3166_canonical_2024": {
                "path": "reference/iso/iso3166_canonical.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
                "version": "demo",
            }
        },
    }


def _write_parquet(frame: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)


def test_runner_assigns_sites(tmp_path: Path) -> None:
    dictionary = _dictionary()
    data_root = tmp_path

    fingerprint = "f" * 64
    alloc_path = (
        data_root
        / f"data/layer1/1B/s4_alloc_plan/seed=123/fingerprint={fingerprint}/parameter_hash=abc"
    )
    tile_index_path = data_root / "data/layer1/1B/tile_index/parameter_hash=abc"
    iso_path = data_root / "reference/iso"

    _write_parquet(
        pl.DataFrame(
            {
                "merchant_id": [1, 1, 2],
                "legal_country_iso": ["US", "US", "GB"],
                "tile_id": [11, 12, 20],
                "n_sites_tile": [2, 1, 1],
            }
        ),
        alloc_path / "part-00000.parquet",
    )

    _write_parquet(
        pl.DataFrame(
            {
                "country_iso": ["US", "US", "GB"],
                "tile_id": [11, 12, 20],
            }
        ),
        tile_index_path / "part-00000.parquet",
    )

    _write_parquet(
        pl.DataFrame({"country_iso": ["US", "GB"]}),
        iso_path / "iso3166_canonical.parquet",
    )

    runner = S5SiteTileAssignmentRunner()
    config = S5RunnerConfig(
        data_root=data_root,
        manifest_fingerprint=fingerprint,
        seed="123",
        parameter_hash="abc",
        dictionary=dictionary,
    )

    result = runner.run(config)

    expected_rows = {
        (1, "US", 1),
        (1, "US", 2),
        (1, "US", 3),
        (2, "GB", 1),
    }
    produced_rows = {
        (row[0], row[1], row[2])
        for row in result.assignments.select(
            ["merchant_id", "legal_country_iso", "site_order"]
        ).iter_rows()
    }
    assert produced_rows == expected_rows
    assert result.rows_emitted == 4
    assert result.rng_events_emitted == 4
    assert result.pairs_total == 2
    assert isinstance(result.run_id, str) and len(result.run_id) == 32
    assert all(event["module"] == "1B.s5_site_tile_assignment" for event in result.rng_events)
    assert all(event["substream_label"] == "site_tile_assign" for event in result.rng_events)
    assert result.rng_events[0]["run_id"] == result.run_id


def test_runner_invalid_seed(tmp_path: Path) -> None:
    dictionary = _dictionary()
    data_root = tmp_path

    fingerprint = "f" * 64
    alloc_path = (
        data_root
        / f"data/layer1/1B/s4_alloc_plan/seed=not-an-int/fingerprint={fingerprint}/parameter_hash=abc"
    )
    tile_index_path = data_root / "data/layer1/1B/tile_index/parameter_hash=abc"
    iso_path = data_root / "reference/iso"

    _write_parquet(
        pl.DataFrame(
            {
                "merchant_id": [1],
                "legal_country_iso": ["US"],
                "tile_id": [11],
                "n_sites_tile": [1],
            }
        ),
        alloc_path / "part-00000.parquet",
    )
    _write_parquet(
        pl.DataFrame({"country_iso": ["US"], "tile_id": [11]}),
        tile_index_path / "part-00000.parquet",
    )
    _write_parquet(
        pl.DataFrame({"country_iso": ["US"]}),
        iso_path / "iso3166_canonical.parquet",
    )

    runner = S5SiteTileAssignmentRunner()
    config = S5RunnerConfig(
        data_root=data_root,
        manifest_fingerprint=fingerprint,
        seed="not-an-int",
        parameter_hash="abc",
        dictionary=dictionary,
    )

    with pytest.raises(S5Error) as excinfo:
        runner.run(config)
    assert excinfo.value.context.code == "E501_INVALID_SEED"


def test_validator_placeholder(tmp_path: Path) -> None:
    validator = S5SiteTileAssignmentValidator()
    config = S5ValidatorConfig(
        data_root=tmp_path,
        seed="123",
        manifest_fingerprint="f" * 64,
        parameter_hash="abc",
    )
    with pytest.raises(S5Error):
        validator.validate(config)
