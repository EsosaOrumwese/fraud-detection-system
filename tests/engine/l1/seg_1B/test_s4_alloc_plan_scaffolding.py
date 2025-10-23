from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_1B import (
    S4AllocPlanRunner,
    S4AllocPlanValidator,
    S4RunnerConfig,
    S4ValidatorConfig,
    s4_allocate_sites,
)
from engine.layers.l1.seg_1B.s4_alloc_plan.l2 import materialise as s4_materialise
from engine.layers.l1.seg_1B.s4_alloc_plan.exceptions import S4Error


def _dictionary() -> dict[str, object]:
    return {
        "datasets": {
            "s3_requirements": {
                "path": "data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/",
                "partitioning": ["seed", "fingerprint", "parameter_hash"],
                "ordering": ["merchant_id", "legal_country_iso"],
                "schema_ref": "schemas.1B.yaml#/plan/s3_requirements",
            },
            "tile_weights": {
                "path": "data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/",
                "partitioning": ["parameter_hash"],
                "ordering": ["country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/prep/tile_weights",
            },
            "tile_index": {
                "path": "data/layer1/1B/tile_index/parameter_hash={parameter_hash}/",
                "partitioning": ["parameter_hash"],
                "ordering": ["country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/prep/tile_index",
            },
            "s4_alloc_plan": {
                "path": "data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/",
                "partitioning": ["seed", "fingerprint", "parameter_hash"],
                "ordering": ["merchant_id", "legal_country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/plan/s4_alloc_plan",
            },
            "s3_run_report": {
                "path": "control/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s3_run_report.json",
                "partitioning": ["seed", "fingerprint", "parameter_hash"],
                "ordering": [],
                "schema_ref": None,
            },
            "s4_run_report": {
                "path": "control/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s4_run_report.json",
                "partitioning": ["seed", "fingerprint", "parameter_hash"],
                "ordering": [],
                "schema_ref": None,
            },
        },
        "reference_data": {
            "iso3166_canonical_2024": {
                "path": "reference/iso/iso3166_canonical.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
                "version": "test",
            }
        },
    }


def test_allocate_sites_basic() -> None:
    requirements = pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "n_sites": [5],
        }
    )
    tile_weights = pl.DataFrame(
        {
            "country_iso": ["US", "US"],
            "tile_id": [1, 2],
            "weight_fp": [700, 300],
            "dp": [3, 3],
        }
    )
    tile_index = tile_weights.select(["country_iso", "tile_id"])

    result = s4_allocate_sites(requirements, tile_weights, tile_index, dp=3)
    allocations = {
        (row[0], row[1], row[2]): row[3]
        for row in result.frame.rows()
    }
    assert allocations[(1, "US", 1)] == 4
    assert allocations[(1, "US", 2)] == 1


@pytest.mark.parametrize(
    "tile_weights",
    [
        pl.DataFrame({"country_iso": ["GB", "GB", "GB"], "tile_id": [10, 11, 12], "weight_fp": [333, 333, 334], "dp": [3, 3, 3]}),
    ],
)
def test_allocate_sites_tie_breaks(tile_weights: pl.DataFrame) -> None:
    requirements = pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["GB"],
            "n_sites": [3],
        }
    )
    tile_index = tile_weights.select(["country_iso", "tile_id"])

    result = s4_allocate_sites(requirements, tile_weights, tile_index, dp=3)
    allocation_map = {row[2]: row[3] for row in result.frame.rows()}
    assert allocation_map == {10: 1, 11: 1, 12: 1}


def test_runner_and_validator_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dictionary = _dictionary()
    data_root = tmp_path
    (data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "data/layer1/1B/tile_weights/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "data/layer1/1B/tile_index/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "reference/iso").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        s4_materialise,
        "_collect_resource_metrics",
        lambda: {"workers_used": 2, "max_worker_rss_bytes": 1024, "open_files_peak": 5},
    )

    pl.DataFrame({"country_iso": ["US", "GB"]}).write_parquet(
        data_root / "reference/iso/iso3166_canonical.parquet"
    )
    pl.DataFrame(
        {
            "merchant_id": [1, 2],
            "legal_country_iso": ["US", "GB"],
            "n_sites": [5, 2],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh/part-00000.parquet"
    )
    pl.DataFrame(
        {
            "country_iso": ["US", "US", "GB", "GB"],
            "tile_id": [1, 2, 5, 6],
            "weight_fp": [700, 300, 600, 400],
            "dp": [3, 3, 3, 3],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/tile_weights/parameter_hash=hh/part-00000.parquet"
    )
    pl.DataFrame(
        {
            "country_iso": ["US", "US", "GB", "GB"],
            "tile_id": [1, 2, 5, 6],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/tile_index/parameter_hash=hh/part-00000.parquet"
    )

    runner = S4AllocPlanRunner()
    config = S4RunnerConfig(
        data_root=data_root,
        manifest_fingerprint="ff",
        seed="123",
        parameter_hash="hh",
        dictionary=dictionary,
    )
    result = runner.run(config)

    dataset = pl.read_parquet(result.alloc_plan_path / "part-00000.parquet")
    assert dataset.sort(["merchant_id", "legal_country_iso", "tile_id"]).rows() == [
        (1, "US", 1, 4),
        (1, "US", 2, 1),
        (2, "GB", 5, 1),
        (2, "GB", 6, 1),
    ]
    assert result.merchants_total == 2
    assert result.pairs_total == 2
    assert result.alloc_sum_equals_requirements is True

    run_report_payload = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert run_report_payload["workers_used"] == 2
    assert run_report_payload["max_worker_rss_bytes"] == 1024
    assert run_report_payload["open_files_peak"] == 5
    summaries = run_report_payload.get("merchant_summaries")
    assert isinstance(summaries, list) and len(summaries) == 2

    validator = S4AllocPlanValidator()
    validator.validate(
        S4ValidatorConfig(
            data_root=data_root,
            seed="123",
            manifest_fingerprint="ff",
            parameter_hash="hh",
            dictionary=dictionary,
        )
    )


def test_validator_detects_mismatch(tmp_path: Path) -> None:
    dictionary = _dictionary()
    data_root = tmp_path
    (data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "data/layer1/1B/tile_weights/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "data/layer1/1B/tile_index/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "data/layer1/1B/s4_alloc_plan/seed=123/fingerprint=ff/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "reference/iso").mkdir(parents=True, exist_ok=True)

    pl.DataFrame({"country_iso": ["US"]}).write_parquet(
        data_root / "reference/iso/iso3166_canonical.parquet"
    )
    pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "n_sites": [2],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh/part-00000.parquet"
    )
    pl.DataFrame(
        {
            "country_iso": ["US", "US"],
            "tile_id": [1, 2],
            "weight_fp": [500, 500],
            "dp": [3, 3],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/tile_weights/parameter_hash=hh/part-00000.parquet"
    )
    pl.DataFrame(
        {
            "country_iso": ["US", "US"],
            "tile_id": [1, 2],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/tile_index/parameter_hash=hh/part-00000.parquet"
    )
    pl.DataFrame(
        {
            "merchant_id": [1, 1],
            "legal_country_iso": ["US", "US"],
            "tile_id": [1, 2],
            "n_sites_tile": [2, 2],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/s4_alloc_plan/seed=123/fingerprint=ff/parameter_hash=hh/part-00000.parquet"
    )

    control_dir = (
        data_root / "control/s4_alloc_plan/seed=123/fingerprint=ff/parameter_hash=hh"
    )
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "s4_run_report.json").write_text(
        json.dumps(
            {
                "seed": "123",
                "manifest_fingerprint": "ff",
                "parameter_hash": "hh",
                "rows_emitted": 2,
                "merchants_total": 1,
                "pairs_total": 1,
                "shortfall_total": 0,
                "ties_broken_total": 0,
                "alloc_sum_equals_requirements": False,
                "ingress_versions": {"iso3166": "test"},
                "bytes_read_s3": 0,
                "bytes_read_weights": 0,
                "bytes_read_index": 0,
                "wall_clock_seconds_total": 0.0,
                "cpu_seconds_total": 0.0,
                "workers_used": 1,
                "max_worker_rss_bytes": 0,
                "open_files_peak": 0,
                "determinism_receipt": {
                    "partition_path": str(
                        data_root
                        / "data/layer1/1B/s4_alloc_plan/seed=123/fingerprint=ff/parameter_hash=hh"
                    ),
                    "sha256_hex": "deadbeef",
                },
            }
        ),
        encoding="utf-8",
    )

    validator = S4AllocPlanValidator()
    with pytest.raises(S4Error) as excinfo:
        validator.validate(
            S4ValidatorConfig(
                data_root=data_root,
                seed="123",
                manifest_fingerprint="ff",
                parameter_hash="hh",
                dictionary=dictionary,
            )
        )
    assert excinfo.value.context.code == "E403_SHORTFALL_MISMATCH"


def test_runner_missing_tile_weights(tmp_path: Path) -> None:
    dictionary = _dictionary()
    data_root = tmp_path
    (data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "data/layer1/1B/tile_index/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "reference/iso").mkdir(parents=True, exist_ok=True)

    pl.DataFrame({"country_iso": ["US"]}).write_parquet(
        data_root / "reference/iso/iso3166_canonical.parquet"
    )
    pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "n_sites": [1],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh/part-00000.parquet"
    )
    pl.DataFrame(
        {
            "country_iso": ["US"],
            "tile_id": [10],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/tile_index/parameter_hash=hh/part-00000.parquet"
    )

    runner = S4AllocPlanRunner()
    config = S4RunnerConfig(
        data_root=data_root,
        manifest_fingerprint="ff",
        seed="123",
        parameter_hash="hh",
        dictionary=dictionary,
    )
    with pytest.raises(S4Error) as excinfo:
        runner.run(config)
    assert excinfo.value.context.code == "E402_WEIGHTS_MISSING"


def test_runner_missing_tile_index(tmp_path: Path) -> None:
    dictionary = _dictionary()
    data_root = tmp_path
    (data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "data/layer1/1B/tile_weights/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "reference/iso").mkdir(parents=True, exist_ok=True)

    pl.DataFrame({"country_iso": ["US"]}).write_parquet(
        data_root / "reference/iso/iso3166_canonical.parquet"
    )
    pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "n_sites": [1],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh/part-00000.parquet"
    )
    pl.DataFrame(
        {
            "country_iso": ["US"],
            "tile_id": [10],
            "weight_fp": [1000],
            "dp": [3],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/tile_weights/parameter_hash=hh/part-00000.parquet"
    )

    runner = S4AllocPlanRunner()
    config = S4RunnerConfig(
        data_root=data_root,
        manifest_fingerprint="ff",
        seed="123",
        parameter_hash="hh",
        dictionary=dictionary,
    )
    with pytest.raises(S4Error) as excinfo:
        runner.run(config)
    assert excinfo.value.context.code == "E408_COVERAGE_MISSING"


def test_validator_missing_run_report_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dictionary = _dictionary()
    data_root = tmp_path
    (data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "data/layer1/1B/tile_weights/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "data/layer1/1B/tile_index/parameter_hash=hh").mkdir(parents=True, exist_ok=True)
    (data_root / "reference/iso").mkdir(parents=True, exist_ok=True)

    pl.DataFrame({"country_iso": ["US"]}).write_parquet(
        data_root / "reference/iso/iso3166_canonical.parquet"
    )
    pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "n_sites": [1],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/s3_requirements/seed=123/fingerprint=ff/parameter_hash=hh/part-00000.parquet"
    )
    pl.DataFrame(
        {
            "country_iso": ["US"],
            "tile_id": [99],
            "weight_fp": [1000],
            "dp": [3],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/tile_weights/parameter_hash=hh/part-00000.parquet"
    )
    pl.DataFrame(
        {
            "country_iso": ["US"],
            "tile_id": [99],
        }
    ).write_parquet(
        data_root / "data/layer1/1B/tile_index/parameter_hash=hh/part-00000.parquet"
    )

    runner = S4AllocPlanRunner()
    config = S4RunnerConfig(
        data_root=data_root,
        manifest_fingerprint="ff",
        seed="123",
        parameter_hash="hh",
        dictionary=dictionary,
    )
    monkeypatch.setattr(
        s4_materialise,
        "_collect_resource_metrics",
        lambda: {"workers_used": 2, "max_worker_rss_bytes": 2048, "open_files_peak": 7},
    )
    runner.run(config)

    report_path = data_root / "control/s4_alloc_plan/seed=123/fingerprint=ff/parameter_hash=hh/s4_run_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload.pop("bytes_read_s3", None)
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    validator = S4AllocPlanValidator()
    with pytest.raises(S4Error) as excinfo:
        validator.validate(
            S4ValidatorConfig(
                data_root=data_root,
                seed="123",
                manifest_fingerprint="ff",
                parameter_hash="hh",
                dictionary=dictionary,
            )
        )
    assert excinfo.value.context.code == "E409_DETERMINISM"
