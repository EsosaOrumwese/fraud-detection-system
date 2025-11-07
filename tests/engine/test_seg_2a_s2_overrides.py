import json
from pathlib import Path

import polars as pl
import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from engine.layers.l1.seg_2A.s2_overrides import OverridesInputs, OverridesRunner


@pytest.fixture()
def manifest_fingerprint() -> str:
    return "d" * 64


@pytest.fixture()
def seed() -> int:
    return 2025110601


def _build_dictionary(include_mcc: bool = True) -> dict[str, object]:
    dictionary: dict[str, object] = {
        "datasets": [
            {
                "id": "s0_gate_receipt_2A",
                "path": "data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json",
            },
            {
                "id": "s1_tz_lookup",
                "path": "data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/",
            },
            {
                "id": "site_timezones",
                "path": "data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/",
            },
        ],
        "policies": [
            {
                "id": "tz_overrides",
                "path": "config/timezone/tz_overrides.yaml",
            }
        ],
        "reference_data": [
            {
                "id": "tz_world_2025a",
                "path": "reference/spatial/tz_world/2025a/tz_world.parquet",
            }
        ],
    }
    if include_mcc:
        dictionary["datasets"].append(
            {
                "id": "merchant_mcc_map",
                "path": "data/layer1/2A/merchant_mcc_map/seed={seed}/fingerprint={manifest_fingerprint}/merchant_mcc_map.parquet",
            }
        )
    return dictionary


def _write_receipt(base_path: Path, manifest_fingerprint: str, *, seed: int) -> Path:
    receipt_path = (
        base_path
        / f"data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": "c" * 64,
        "validation_bundle_path": "data/layer1/1B/validation/fingerprint=abc/bundle",
        "flag_sha256_hex": "1" * 64,
        "verified_at_utc": "2025-11-06T00:00:00.000000Z",
        "sealed_inputs": [
            {
                "id": "s1_tz_lookup",
                "partition": [f"seed={seed}", f"fingerprint={manifest_fingerprint}"],
                "schema_ref": "schemas.2A.yaml#/plan/s1_tz_lookup",
            }
        ],
    }
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return receipt_path


def _write_tz_world(base_path: Path) -> None:
    path = base_path / "reference/spatial/tz_world/2025a/tz_world.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({"tzid": pa.array(["TZ_A", "TZ_B", "TZ_C", "TZ_SITE", "TZ_MCC", "TZ_COUNTRY"])})
    pq.write_table(table, path)


def _write_s1_lookup(base_path: Path, seed: int, manifest_fingerprint: str) -> Path:
    target_dir = base_path / f"data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}"
    target_dir.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(
        {
            "merchant_id": ["M1", "M2", "M3"],
            "legal_country_iso": ["US", "US", "CA"],
            "site_order": [1, 1, 1],
            "tzid_provisional": ["TZ_A", "TZ_B", "TZ_C"],
            "nudge_lat_deg": [None, None, None],
            "nudge_lon_deg": [None, None, None],
        }
    )
    df.write_parquet(target_dir / "part-00000.parquet")
    return target_dir


def _write_overrides(base_path: Path) -> Path:
    overrides_body = {
        "semver": "1.0.0-alpha",
        "sha256_digest": "deadbeef",
        "overrides": [
            {"scope": "site", "target": "M1:US:1", "tzid": "TZ_SITE"},
            {"scope": "mcc", "target": "5812", "tzid": "TZ_MCC"},
            {"scope": "country", "target": "CA", "tzid": "TZ_COUNTRY"},
        ],
    }
    overrides_path = base_path / "config/timezone/tz_overrides.yaml"
    overrides_path.parent.mkdir(parents=True, exist_ok=True)
    overrides_path.write_text(json.dumps(overrides_body, indent=2), encoding="utf-8")
    return overrides_path


def _write_mcc_mapping(base_path: Path, seed: int, manifest_fingerprint: str) -> Path:
    path = (
        base_path
        / f"data/layer1/2A/merchant_mcc_map/seed={seed}/fingerprint={manifest_fingerprint}/merchant_mcc_map.parquet"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({"merchant_id": pa.array(["M2"]), "mcc": pa.array(["5812"])})
    pq.write_table(table, path)
    return path


def test_overrides_runner_writes_site_timezones_and_report(tmp_path: Path, manifest_fingerprint: str, seed: int) -> None:
    dictionary = _build_dictionary()
    _write_receipt(tmp_path, manifest_fingerprint, seed=seed)
    _write_s1_lookup(tmp_path, seed, manifest_fingerprint)
    _write_tz_world(tmp_path)
    _write_overrides(tmp_path)
    _write_mcc_mapping(tmp_path, seed, manifest_fingerprint)

    runner = OverridesRunner()
    result = runner.run(
        OverridesInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            upstream_manifest_fingerprint=manifest_fingerprint,
            dictionary=dictionary,
            chunk_size=1,
        )
    )

    output_parts = sorted(result.output_path.glob("*.parquet"))
    assert len(output_parts) == 3
    combined = pl.concat([pl.read_parquet(part) for part in output_parts]).sort(["merchant_id"])
    assert combined["tzid"].to_list() == ["TZ_SITE", "TZ_MCC", "TZ_COUNTRY"]
    assert combined["tzid_source"].to_list() == ["override", "override", "override"]
    assert combined["override_scope"].to_list() == ["site", "mcc", "country"]

    assert result.run_report_path.exists()
    payload = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["counts"]["sites_total"] == 3
    assert payload["counts"]["overridden_total"] == 3
    assert payload["warnings"] == []
    assert payload["output"]["created_utc"] == "2025-11-06T00:00:00.000000Z"
    assert payload["inputs"]["tz_overrides"]["semver"] == "1.0.0-alpha"


def test_override_no_effect_fails_and_reports(tmp_path: Path, manifest_fingerprint: str, seed: int) -> None:
    dictionary = _build_dictionary()
    _write_receipt(tmp_path, manifest_fingerprint, seed=seed)
    _write_s1_lookup(tmp_path, seed, manifest_fingerprint)
    _write_tz_world(tmp_path)
    overrides_dir = tmp_path / "config/timezone"
    overrides_dir.mkdir(parents=True, exist_ok=True)
    (overrides_dir / "tz_overrides.yaml").write_text(
        json.dumps(
            {
                "semver": "1.0.0-alpha",
                "sha256_digest": "deadbeef",
                "overrides": [
                    {"scope": "site", "target": "M1:US:1", "tzid": "TZ_A"},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_mcc_mapping(tmp_path, seed, manifest_fingerprint)

    runner = OverridesRunner()
    with pytest.raises(Exception) as excinfo:
        runner.run(
            OverridesInputs(
                data_root=tmp_path,
                seed=seed,
                manifest_fingerprint=manifest_fingerprint,
                upstream_manifest_fingerprint=manifest_fingerprint,
                dictionary=dictionary,
            )
        )
    assert "E_S2_OVERRIDE_NO_EFFECT" in str(excinfo.value)
    report_path = tmp_path / "reports/l1/s2_overrides" / f"seed={seed}" / f"fingerprint={manifest_fingerprint}" / "run_report.json"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert payload["errors"][0]["code"] == "E_S2_OVERRIDE_NO_EFFECT"


def test_missing_mcc_mapping_is_reported(tmp_path: Path, manifest_fingerprint: str, seed: int) -> None:
    dictionary = _build_dictionary(include_mcc=False)
    _write_receipt(tmp_path, manifest_fingerprint, seed=seed)
    _write_s1_lookup(tmp_path, seed, manifest_fingerprint)
    _write_tz_world(tmp_path)
    overrides = {
        "semver": "1.0.0-alpha",
        "sha256_digest": "deadbeef",
        "overrides": [
            {"scope": "mcc", "target": "5812", "tzid": "TZ_MCC"},
        ],
    }
    overrides_path = tmp_path / "config/timezone/tz_overrides.yaml"
    overrides_path.parent.mkdir(parents=True, exist_ok=True)
    overrides_path.write_text(json.dumps(overrides, indent=2), encoding="utf-8")

    runner = OverridesRunner()
    result = runner.run(
        OverridesInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            upstream_manifest_fingerprint=manifest_fingerprint,
            dictionary=dictionary,
            chunk_size=1,
        )
    )
    payload = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert "2A-S2-022 MCC_MAPPING_MISSING" in payload["warnings"]
    assert payload["counts"]["mcc_targets_missing"] == 3
