from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_1B import (
    S5RunnerConfig,
    S5RunResult,
    S5SiteTileAssignmentRunner,
    S5SiteTileAssignmentValidator,
    S5ValidatorConfig,
)
from engine.layers.l1.seg_1B.s5_site_tile_assignment.exceptions import S5Error
from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest


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
                "schema_ref": "schemas.1B.yaml#/control/s5_run_report",
            },
        },
        "reference_data": {
            "iso3166_canonical_2024": {
                "path": "reference/iso/iso3166_canonical.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
                "version": "demo",
            }
        },
        "logs": {
            "rng_event_site_tile_assign": {
                "path": "logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/",
                "partitioning": ["seed", "parameter_hash", "run_id"],
                "ordering": [],
                "schema_ref": "schemas.layer1.yaml#/rng/events/site_tile_assign",
            },
            "rng_trace_log": {
                "path": "logs/rng/trace/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl",
                "partitioning": ["seed", "parameter_hash", "run_id"],
                "ordering": [],
                "schema_ref": "schemas.layer1.yaml#/rng/core/rng_trace_log",
            }
        },
    }


def _write_parquet(frame: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)


def test_runner_materialises_outputs(tmp_path: Path) -> None:
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

    assert isinstance(result, S5RunResult)
    assert result.dataset_path.exists()
    assert result.run_report_path.exists()
    assert result.rng_log_path.exists()
    assert result.rows_emitted == 4
    assert result.rng_events_emitted == 4
    assert result.pairs_total == 2
    assert isinstance(result.run_id, str) and len(result.run_id) == 32

    dataset = pl.read_parquet(result.dataset_path / "part-00000.parquet").select(
        ["merchant_id", "legal_country_iso", "site_order", "tile_id"]
    )

    expected_keys = {
        (1, "US", 1),
        (1, "US", 2),
        (1, "US", 3),
        (2, "GB", 1),
    }
    assert {
        (int(row[0]), row[1], int(row[2]))
        for row in dataset.select(
            ["merchant_id", "legal_country_iso", "site_order"]
        ).iter_rows()
    } == expected_keys

    digest = compute_partition_digest(result.dataset_path)
    run_report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert run_report["determinism_receipt"]["partition_path"] == str(result.dataset_path)
    assert run_report["determinism_receipt"]["sha256_hex"] == digest
    assert run_report["rng_events_emitted"] == 4
    assert run_report["expected_rng_events"] == 4
    assert run_report["rows_emitted"] == 4
    assert run_report["pairs_total"] == 2
    assert run_report["run_id"] == result.run_id
    assert run_report["seed"] == "123"
    assert run_report["parameter_hash"] == "abc"
    assert run_report["manifest_fingerprint"] == fingerprint
    assert run_report.get("quota_mismatches", 0) == 0

    log_files = sorted((result.rng_log_path).glob("*.jsonl"))
    assert log_files, "expected rng event file"
    lines = [line for file in log_files for line in file.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 4
    events = [json.loads(line) for line in lines]
    assert all(event["module"] == "1B.s5_site_tile_assignment" for event in events)
    assert all(event["run_id"] == result.run_id for event in events)
    assert {event["site_order"] for event in events} == {1, 2, 3, 1}
    assert all(0.0 < float(event["u"]) < 1.0 for event in events)


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


def test_validator_passes_on_valid_outputs(tmp_path: Path) -> None:
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
        pl.DataFrame({"country_iso": ["US", "US", "GB"], "tile_id": [11, 12, 20]}),
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
    runner.run(config)

    validator = S5SiteTileAssignmentValidator()
    validator_config = S5ValidatorConfig(
        data_root=data_root,
        seed="123",
        manifest_fingerprint=fingerprint,
        parameter_hash="abc",
        dictionary=dictionary,
    )
    validator.validate(validator_config)


def test_validator_detects_missing_rng_logs(tmp_path: Path) -> None:
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
    run_config = S5RunnerConfig(
        data_root=data_root,
        manifest_fingerprint=fingerprint,
        seed="123",
        parameter_hash="abc",
        dictionary=dictionary,
    )
    run_result = runner.run(run_config)
    # Remove RNG log to trigger validator failure.
    for file in run_result.rng_log_path.glob("*"):
        file.unlink()

    validator = S5SiteTileAssignmentValidator()
    validator_config = S5ValidatorConfig(
        data_root=data_root,
        seed="123",
        manifest_fingerprint=fingerprint,
        parameter_hash="abc",
        dictionary=dictionary,
    )
    with pytest.raises(S5Error) as excinfo:
        validator.validate(validator_config)
    assert excinfo.value.context.code == "E507_RNG_EVENT_MISMATCH"
