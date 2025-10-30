from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import polars as pl
import pytest

from engine.layers.l1.seg_1B.s7_site_synthesis import (
    RunnerConfig as S7RunnerConfig,
    S7SiteSynthesisRunner,
)
from engine.layers.l1.seg_1B.s7_site_synthesis.exceptions import S7Error
from engine.layers.l1.seg_1B.s7_site_synthesis.l3.validator import (
    S7SiteSynthesisValidator,
    ValidatorConfig as S7ValidatorConfig,
)


def _build_dictionary() -> Dict[str, object]:
    return {
        "datasets": {
            "s5_site_tile_assignment": {
                "path": "data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/"
            },
            "s6_site_jitter": {
                "path": "data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/"
            },
            "s7_site_synthesis": {
                "path": "data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/"
            },
            "outlet_catalogue": {
                "path": "data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/"
            },
            "tile_bounds": {
                "path": "data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}/"
            },
        },
        "reference_data": {
            "validation_bundle_1A": {
                "path": "data/layer1/1A/validation/fingerprint={manifest_fingerprint}/"
            },
        },
    }


def _write_parquet(path: Path, frame: pl.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)


def _prepare_validation_bundle(bundle_dir: Path) -> str:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    checks_dir = bundle_dir / "checks"
    checks_dir.mkdir(parents=True, exist_ok=True)
    artefact_path = checks_dir / "report.json"
    artefact_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    index_payload = [
        {"artifact_id": "report", "path": "checks/report.json"},
        {"artifact_id": "index", "path": "index.json"},
    ]
    index_path = bundle_dir / "index.json"
    index_path.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")

    import hashlib

    digest = hashlib.sha256()
    for relative in sorted(["checks/report.json", "index.json"]):
        digest.update((bundle_dir / relative).read_bytes())
    sha = digest.hexdigest()
    (bundle_dir / "_passed.flag").write_text(f"sha256_hex = {sha}", encoding="utf-8")
    return sha


def _prepare_inputs(tmp_path: Path) -> tuple[S7RunnerConfig, Dict[str, object]]:
    dictionary = _build_dictionary()
    manifest_fingerprint = "f" * 64
    parameter_hash = "abc123"
    seed = "123"

    # S5 assignments
    s5_path = (
        tmp_path
        / f"data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}"
    )
    s5_frame = pl.DataFrame(
        {
            "merchant_id": [1, 2],
            "legal_country_iso": ["US", "CA"],
            "site_order": [1, 1],
            "tile_id": [10, 20],
        }
    )
    _write_parquet(s5_path / "part-00000.parquet", s5_frame)

    # S6 jitter
    s6_path = (
        tmp_path
        / f"data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}"
    )
    s6_frame = pl.DataFrame(
        {
            "merchant_id": [1, 2],
            "legal_country_iso": ["US", "CA"],
            "site_order": [1, 1],
            "tile_id": [10, 20],
            "delta_lon_deg": [0.001, -0.002],
            "delta_lat_deg": [0.003, -0.004],
        }
    )
    _write_parquet(s6_path / "part-00000.parquet", s6_frame)

    # Tile bounds
    tile_path = tmp_path / f"data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}"
    tile_frame = pl.DataFrame(
        {
            "country_iso": ["US", "CA"],
            "tile_id": [10, 20],
            "min_lon_deg": [-1.0, -2.0],
            "max_lon_deg": [1.0, 0.0],
            "min_lat_deg": [-1.0, -2.0],
            "max_lat_deg": [1.0, 0.0],
            "centroid_lon_deg": [0.0, -1.0],
            "centroid_lat_deg": [0.0, -1.0],
        }
    )
    _write_parquet(tile_path / "part-00000.parquet", tile_frame)

    # Outlet catalogue
    outlet_path = (
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}"
    )
    outlet_frame = pl.DataFrame(
        {
            "merchant_id": [1, 2],
            "legal_country_iso": ["US", "CA"],
            "site_order": [1, 1],
            "manifest_fingerprint": [manifest_fingerprint, manifest_fingerprint],
        }
    )
    _write_parquet(outlet_path / "part-00000.parquet", outlet_frame)

    # Validation bundle
    bundle_dir = tmp_path / f"data/layer1/1A/validation/fingerprint={manifest_fingerprint}"
    _prepare_validation_bundle(bundle_dir)

    config = S7RunnerConfig(
        data_root=tmp_path,
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        parameter_hash=parameter_hash,
        dictionary=dictionary,
    )
    return config, dictionary


def test_runner_and_validator_s7(tmp_path: Path):
    config, dictionary = _prepare_inputs(tmp_path)

    runner = S7SiteSynthesisRunner()
    result = runner.run(config)

    assert result.dataset_path.exists()
    assert result.run_summary_path.exists()

    dataset = pl.read_parquet(result.dataset_path / "part-00000.parquet")
    assert dataset.height == 2

    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert summary["counts"]["sites_total_s7"] == 2
    counters = summary["validation_counters"]
    assert counters["coverage_1a_ok_count"] == 2
    assert counters["coverage_1a_pruned_count"] == 0

    validator = S7SiteSynthesisValidator()
    validator.validate(
        S7ValidatorConfig(
            data_root=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
            run_summary_path=result.run_summary_path,
        )
    )


def test_validator_s7_coverage_failure(tmp_path: Path):
    config, dictionary = _prepare_inputs(tmp_path)
    runner = S7SiteSynthesisRunner()
    result = runner.run(config)

    outlet_path = (
        tmp_path
        / f"data/layer1/1A/outlet_catalogue/seed={config.seed}/fingerprint={config.manifest_fingerprint}"
    )
    outlet_frame = pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "site_order": [1],
            "manifest_fingerprint": [config.manifest_fingerprint],
        }
    )
    _write_parquet(outlet_path / "part-00000.parquet", outlet_frame)

    validator = S7SiteSynthesisValidator()
    with pytest.raises(S7Error) as exc:
        validator.validate(
            S7ValidatorConfig(
                data_root=config.data_root,
                seed=config.seed,
                manifest_fingerprint=config.manifest_fingerprint,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
                run_summary_path=result.run_summary_path,
            )
        )
    assert exc.value.context.code == "E708_1A_COVERAGE_FAIL"


def test_validator_s7_geometry_failure(tmp_path: Path):
    config, dictionary = _prepare_inputs(tmp_path)
    runner = S7SiteSynthesisRunner()
    result = runner.run(config)

    dataset_path = result.dataset_path / "part-00000.parquet"
    data = pl.read_parquet(dataset_path)
    corrupted = data.with_columns(
        pl.when(pl.col("merchant_id") == 1)
        .then(pl.lit(5.0))
        .otherwise(pl.col("lon_deg"))
        .alias("lon_deg")
    )
    corrupted.write_parquet(dataset_path)

    validator = S7SiteSynthesisValidator()
    with pytest.raises(S7Error) as exc:
        validator.validate(
            S7ValidatorConfig(
                data_root=config.data_root,
                seed=config.seed,
                manifest_fingerprint=config.manifest_fingerprint,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
                run_summary_path=result.run_summary_path,
            )
        )
    assert exc.value.context.code == "E707_POINT_OUTSIDE_PIXEL"
