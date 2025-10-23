from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_1B.s8_site_locations import (
    RunnerConfig as S8RunnerConfig,
    S8SiteLocationsRunner,
)
from engine.layers.l1.seg_1B.s8_site_locations.exceptions import S8Error
from engine.layers.l1.seg_1B.s8_site_locations.l3.validator import (
    S8SiteLocationsValidator,
    ValidatorConfig as S8ValidatorConfig,
)


def _build_dictionary() -> dict[str, object]:
    return {
        "datasets": {
            "s7_site_synthesis": {
                "path": "data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/"
            },
            "site_locations": {
                "path": "data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/",
                "final_in_layer": True,
            },
        }
    }


def _write_parquet(path: Path, frame: pl.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)


def _prepare_inputs(tmp_path: Path) -> tuple[S8RunnerConfig, dict[str, object]]:
    dictionary = _build_dictionary()
    manifest_fingerprint = "f" * 64
    parameter_hash = "abc123"
    seed = "123"

    s7_path = (
        tmp_path
        / f"data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}"
    )
    s7_frame = pl.DataFrame(
        {
            "merchant_id": [1, 2],
            "legal_country_iso": ["US", "CA"],
            "site_order": [1, 1],
            "tile_id": [10, 20],
            "lon_deg": [0.1, -1.2],
            "lat_deg": [0.5, -0.7],
        }
    )
    _write_parquet(s7_path / "part-00000.parquet", s7_frame)

    config = S8RunnerConfig(
        data_root=tmp_path,
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        parameter_hash=parameter_hash,
        dictionary=dictionary,
    )
    return config, dictionary


def test_runner_and_validator_s8(tmp_path: Path):
    config, dictionary = _prepare_inputs(tmp_path)

    runner = S8SiteLocationsRunner()
    result = runner.run(config)

    assert result.dataset_path.exists()
    assert result.run_summary_path.exists()

    dataset = pl.read_parquet(result.dataset_path / "part-00000.parquet")
    assert dataset.height == 2

    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert summary["sizes"]["rows_s8"] == 2
    assert summary["sizes"]["parity_ok"] is True

    validator = S8SiteLocationsValidator()
    validator.validate(
        S8ValidatorConfig(
            data_root=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
            run_summary_path=result.run_summary_path,
        )
    )


def test_validator_s8_parity_failure(tmp_path: Path):
    config, dictionary = _prepare_inputs(tmp_path)
    runner = S8SiteLocationsRunner()
    result = runner.run(config)

    dataset_path = result.dataset_path / "part-00000.parquet"
    data = pl.read_parquet(dataset_path)
    corrupted = data.filter(pl.col("merchant_id") != 1)
    corrupted.write_parquet(dataset_path)

    validator = S8SiteLocationsValidator()
    with pytest.raises(S8Error) as exc:
        validator.validate(
            S8ValidatorConfig(
                data_root=config.data_root,
                seed=config.seed,
                manifest_fingerprint=config.manifest_fingerprint,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
                run_summary_path=result.run_summary_path,
            )
        )
    assert exc.value.context.code == "E801_ROW_MISSING"


def test_validator_s8_identity_failure(tmp_path: Path):
    config, dictionary = _prepare_inputs(tmp_path)
    runner = S8SiteLocationsRunner()
    result = runner.run(config)

    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    summary["identity"]["parameter_hash_consumed"] = "deadbeef"
    result.run_summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    validator = S8SiteLocationsValidator()
    with pytest.raises(S8Error) as exc:
        validator.validate(
            S8ValidatorConfig(
                data_root=config.data_root,
                seed=config.seed,
                manifest_fingerprint=config.manifest_fingerprint,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
                run_summary_path=result.run_summary_path,
            )
        )
    assert exc.value.context.code == "E809_PARTITION_SHIFT_VIOLATION"
