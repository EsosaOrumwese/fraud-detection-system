from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from engine.layers.l1.seg_1A.s8_outlet_catalogue.validate import (
    S8ValidationError,
    validate_outputs,
)


def _write_candidate_set(base_path: Path, parameter_hash: str, rows: list[dict]) -> None:
    path = base_path / "data" / "layer1" / "1A" / "s3_candidate_set" / f"parameter_hash={parameter_hash}"
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path / "part-00000.parquet", index=False)


def _write_outlet_catalogue(
    base_path: Path,
    *,
    seed: int,
    manifest_fingerprint: str,
    rows: list[dict],
) -> Path:
    path = base_path / "data" / "layer1" / "1A" / "outlet_catalogue" / f"seed={seed}" / f"fingerprint={manifest_fingerprint}"
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / "part-00000.parquet"
    pd.DataFrame(rows).to_parquet(file_path, index=False)
    return file_path


def test_validate_outputs_membership_mismatch(tmp_path: Path) -> None:
    parameter_hash = "phash"
    manifest_fingerprint = "f" * 64
    seed = 101
    run_id = "run-1"

    _write_candidate_set(
        tmp_path,
        parameter_hash,
        rows=[
            {"merchant_id": 1, "country_iso": "US", "candidate_rank": 0, "is_home": True},
        ],
    )
    catalogue_rows = [
        {
            "manifest_fingerprint": manifest_fingerprint,
            "merchant_id": 1,
            "site_id": "000001",
            "home_country_iso": "US",
            "legal_country_iso": "US",
            "single_vs_multi_flag": True,
            "raw_nb_outlet_draw": 3,
            "final_country_outlet_count": 2,
            "site_order": 1,
            "global_seed": seed,
        },
        {
            "manifest_fingerprint": manifest_fingerprint,
            "merchant_id": 1,
            "site_id": "000002",
            "home_country_iso": "US",
            "legal_country_iso": "US",
            "single_vs_multi_flag": True,
            "raw_nb_outlet_draw": 3,
            "final_country_outlet_count": 2,
            "site_order": 2,
            "global_seed": seed,
        },
        {
            "manifest_fingerprint": manifest_fingerprint,
            "merchant_id": 1,
            "site_id": "000001",
            "home_country_iso": "US",
            "legal_country_iso": "CA",
            "single_vs_multi_flag": True,
            "raw_nb_outlet_draw": 3,
            "final_country_outlet_count": 1,
            "site_order": 1,
            "global_seed": seed,
        },
    ]
    catalogue_path = _write_outlet_catalogue(
        tmp_path,
        seed=seed,
        manifest_fingerprint=manifest_fingerprint,
        rows=catalogue_rows,
    )

    with pytest.raises(S8ValidationError) as exc:
        validate_outputs(
            base_path=tmp_path,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            seed=seed,
            run_id=run_id,
            catalogue_path=catalogue_path,
            event_paths={},
        )
    assert "S3 membership reconciliation failed" in str(exc.value)


def test_validate_outputs_iso_violation(tmp_path: Path) -> None:
    parameter_hash = "phash"
    manifest_fingerprint = "f" * 64
    seed = 202
    run_id = "run-1"

    _write_candidate_set(
        tmp_path,
        parameter_hash,
        rows=[
            {"merchant_id": 1, "country_iso": "US", "candidate_rank": 0, "is_home": True},
        ],
    )
    catalogue_path = _write_outlet_catalogue(
        tmp_path,
        seed=seed,
        manifest_fingerprint=manifest_fingerprint,
        rows=[
            {
                "manifest_fingerprint": manifest_fingerprint,
                "merchant_id": 1,
                "site_id": "000001",
                "home_country_iso": "US",
                "legal_country_iso": "USA",  # invalid ISO
                "single_vs_multi_flag": False,
                "raw_nb_outlet_draw": 1,
                "final_country_outlet_count": 1,
                "site_order": 1,
                "global_seed": seed,
            }
        ],
    )

    with pytest.raises(S8ValidationError) as exc:
        validate_outputs(
            base_path=tmp_path,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            seed=seed,
            run_id=run_id,
            catalogue_path=catalogue_path,
            event_paths={},
        )
    assert "invalid ISO" in str(exc.value)
