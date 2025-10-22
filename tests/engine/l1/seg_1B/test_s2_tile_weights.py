from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_1B.s2_tile_weights import (
    RunnerConfig,
    S2Error,
    S2TileWeightsRunner,
)


@pytest.fixture()
def dictionary() -> dict[str, object]:
    return {
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


def _write_iso_table(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"country_iso": ["AA", "BB"]}).write_parquet(path)


def _write_tile_index_partition(base_path: Path, parameter_hash: str) -> Path:
    partition_dir = (
        base_path / f"data/layer1/1B/tile_index/parameter_hash={parameter_hash}"
    )
    partition_dir.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(
        {
            "country_iso": ["AA", "AA", "BB"],
            "tile_id": [0, 1, 0],
            "pixel_area_m2": [10.0, 12.0, 9.5],
        }
    )
    frame.write_parquet(partition_dir / "part-00000.parquet")
    return partition_dir


def test_prepare_inputs_happy_path(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    iso_path = data_root / "reference/iso/iso3166_canonical.parquet"
    _write_iso_table(iso_path)
    _write_tile_index_partition(data_root, "abc123")

    runner = S2TileWeightsRunner()
    prepared = runner.prepare(
        RunnerConfig(
            data_root=data_root,
            parameter_hash="abc123",
            basis="area_m2",
            dp=3,
            dictionary=dictionary,
        )
    )

    assert prepared.governed.basis == "area_m2"
    assert prepared.governed.dp == 3
    assert prepared.tile_index.rows == 3
    assert prepared.tile_index.path.exists()
    assert prepared.iso_table.codes == frozenset({"AA", "BB"})
    assert prepared.pat.countries_processed == 0


def test_prepare_inputs_missing_tile_index(
    tmp_path: Path, dictionary: dict[str, object]
) -> None:
    data_root = tmp_path
    iso_path = data_root / "reference/iso/iso3166_canonical.parquet"
    _write_iso_table(iso_path)

    runner = S2TileWeightsRunner()
    with pytest.raises(S2Error) as excinfo:
        runner.prepare(
            RunnerConfig(
                data_root=data_root,
                parameter_hash="missing",
                basis="uniform",
                dp=2,
                dictionary=dictionary,
            )
        )
    assert excinfo.value.context.code == "E101_TILE_INDEX_MISSING"

