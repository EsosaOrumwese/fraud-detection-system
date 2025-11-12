import json
from pathlib import Path

import pytest

from engine.layers.l1.seg_2A.s0_gate.exceptions import S0GateError
from engine.layers.l1.seg_2A.s5_validation import ValidationInputs, ValidationRunner


def _write_dictionary(path: Path) -> Path:
    payload = """
version: test
datasets:
  - id: s0_gate_receipt_2A
    path: data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
  - id: site_timezones
    path: data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
  - id: tz_timetable_cache
    path: data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/
  - id: tz_offset_adjustments
    path: data/layer1/2A/tz_offset_adjustments/fingerprint={manifest_fingerprint}/
  - id: s4_legality_report
    path: data/layer1/2A/legality_report/seed={seed}/fingerprint={manifest_fingerprint}/s4_legality_report.json
  - id: validation_bundle_2A
    path: data/layer1/2A/validation/fingerprint={manifest_fingerprint}/
"""
    dictionary_path = path / "dictionary.yaml"
    dictionary_path.write_text(payload.strip(), encoding="utf-8")
    return dictionary_path


def _write_gate_receipt(base: Path, manifest: str) -> Path:
    receipt_dir = base / f"data/layer1/2A/s0_gate_receipt/fingerprint={manifest}"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "flag_sha256_hex": "0" * 64,
        "manifest_fingerprint": manifest,
        "parameter_hash": "f" * 64,
        "sealed_inputs": [],
        "validation_bundle_path": "data/layer1/1B/validation/fingerprint=dummy/bundle",
        "verified_at_utc": "2025-11-08T00:00:00.000000Z",
    }
    receipt_path = receipt_dir / "s0_gate_receipt.json"
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return receipt_path


def _write_determinism_receipt(base: Path, manifest: str) -> Path:
    target = (
        base
        / "reports"
        / "l1"
        / "s0_gate"
        / f"fingerprint={manifest}"
        / "determinism_receipt.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sha256_hex": "facecafe" * 8,
        "partition_hash": "decafbad" * 8,
        "partition_path": f"data/layer1/2A/validation/fingerprint={manifest}",
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _write_site_timezones(base: Path, manifest: str, seeds: list[int]) -> None:
    for seed in seeds:
        partition_dir = base / f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        (partition_dir / "dummy.parquet").write_text("{}", encoding="utf-8")


def _write_s4_reports(base: Path, manifest: str, seeds: list[int]) -> None:
    for seed in seeds:
        report_dir = base / f"data/layer1/2A/legality_report/seed={seed}/fingerprint={manifest}"
        report_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "PASS",
            "manifest_fingerprint": manifest,
            "seed": seed,
            "generated_utc": "2025-11-08T00:00:00.000000Z",
            "counts": {
                "sites_total": 1,
                "tzids_total": 1,
                "gap_windows_total": 0,
                "fold_windows_total": 0,
            },
        }
        (report_dir / "s4_legality_report.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )


def _write_tz_cache(base: Path, manifest: str) -> Path:
    cache_dir = base / f"data/layer1/2A/tz_timetable_cache/fingerprint={manifest}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_payload = {
        "manifest_fingerprint": manifest,
        "tzdb_release_tag": "test-release",
        "tzdb_archive_sha256": "0" * 64,
        "tz_index_digest": "1" * 64,
        "rle_cache_bytes": 123,
        "created_utc": "2025-11-08T00:00:00.000000Z",
    }
    manifest_path = cache_dir / "tz_timetable_cache.json"
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    return manifest_path


def _write_tz_adjustments(base: Path, manifest: str) -> Path:
    adjustments_dir = base / f"data/layer1/2A/tz_offset_adjustments/fingerprint={manifest}"
    adjustments_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifest_fingerprint": manifest,
        "created_utc": "2025-11-08T00:00:00.000000Z",
        "count": 1,
        "adjustments": [
            {
                "tzid": "America/New_York",
                "transition_unix_utc": -9223372036854775808,
                "raw_seconds": -18001,
                "adjusted_minutes": -300,
                "reasons": ["clip"],
            }
        ],
    }
    path = adjustments_dir / "tz_offset_adjustments.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_validation_runner_builds_bundle(tmp_path: Path) -> None:
    manifest = "c" * 64
    seeds = [1, 2]
    dictionary_path = _write_dictionary(tmp_path)
    _write_gate_receipt(tmp_path, manifest)
    _write_determinism_receipt(tmp_path, manifest)
    _write_site_timezones(tmp_path, manifest, seeds)
    _write_s4_reports(tmp_path, manifest, seeds)
    _write_tz_cache(tmp_path, manifest)

    runner = ValidationRunner()
    result = runner.run(
        ValidationInputs(
            data_root=tmp_path,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
        )
    )
    assert result.resumed is False
    bundle_root = result.bundle_path
    assert bundle_root.exists()
    index_path = bundle_root / "index.json"
    assert index_path.exists()
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    paths = [entry["path"] for entry in index_payload["files"]]
    assert f"evidence/s4/seed={seeds[0]}/s4_legality_report.json" in paths
    assert f"evidence/s4/seed={seeds[1]}/s4_legality_report.json" in paths
    flag_line = result.flag_path.read_text(encoding="utf-8").strip()
    assert flag_line.startswith("sha256_hex = ")
    digest_value = flag_line.split(" = ", 1)[1]
    report_payload = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert report_payload["bundle"]["files_indexed"] == len(paths)
    assert report_payload["seeds"]["discovered"] == len(seeds)
    assert report_payload["s4"]["covered"] == len(seeds)
    assert report_payload["digest"]["computed_sha256"] == digest_value
    assert report_payload["flag"]["value"] == digest_value
    assert report_payload["inputs"]["adjustments"]["path"] is None
    assert report_payload["inputs"]["adjustments"]["count"] == 0
    assert report_payload["determinism"]["sha256_hex"] == "facecafe" * 8

    resumed = runner.run(
        ValidationInputs(
            data_root=tmp_path,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            resume=True,
        )
    )
    assert resumed.resumed is True


def test_validation_runner_requires_pass_reports(tmp_path: Path) -> None:
    manifest = "d" * 64
    dictionary_path = _write_dictionary(tmp_path)
    _write_gate_receipt(tmp_path, manifest)
    _write_determinism_receipt(tmp_path, manifest)
    _write_site_timezones(tmp_path, manifest, [5])
    _write_tz_cache(tmp_path, manifest)
    # write failing S4 report
    report_dir = tmp_path / f"data/layer1/2A/legality_report/seed=5/fingerprint={manifest}"
    report_dir.mkdir(parents=True, exist_ok=True)
    failing_payload = {
        "status": "FAIL",
        "manifest_fingerprint": manifest,
        "seed": 5,
        "generated_utc": "2025-11-08T00:00:00.000000Z",
        "counts": {
            "sites_total": 1,
            "tzids_total": 1,
            "gap_windows_total": 0,
            "fold_windows_total": 0,
        },
    }
    report_dir.joinpath("s4_legality_report.json").write_text(
        json.dumps(failing_payload), encoding="utf-8"
    )

    runner = ValidationRunner()
    with pytest.raises(S0GateError) as excinfo:
        runner.run(
            ValidationInputs(
                data_root=tmp_path,
                manifest_fingerprint=manifest,
                dictionary_path=dictionary_path,
            )
        )
    assert excinfo.value.code == "2A-S5-030"


def test_validation_runner_requires_s4_reports(tmp_path: Path) -> None:
    manifest = "e" * 64
    dictionary_path = _write_dictionary(tmp_path)
    _write_gate_receipt(tmp_path, manifest)
    _write_determinism_receipt(tmp_path, manifest)
    _write_site_timezones(tmp_path, manifest, [11])
    _write_tz_cache(tmp_path, manifest)

    runner = ValidationRunner()
    with pytest.raises(S0GateError) as excinfo:
        runner.run(
            ValidationInputs(
                data_root=tmp_path,
                manifest_fingerprint=manifest,
                dictionary_path=dictionary_path,
            )
        )
    assert excinfo.value.code == "2A-S5-030"


def test_validation_runner_validates_tz_manifest_fingerprint(tmp_path: Path) -> None:
    manifest = "f" * 64
    dictionary_path = _write_dictionary(tmp_path)
    _write_gate_receipt(tmp_path, manifest)
    _write_determinism_receipt(tmp_path, manifest)
    _write_site_timezones(tmp_path, manifest, [3])
    manifest_path = _write_tz_cache(tmp_path, manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["manifest_fingerprint"] = "0" * 64
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_s4_reports(tmp_path, manifest, [3])

    runner = ValidationRunner()
    with pytest.raises(S0GateError) as excinfo:
        runner.run(
            ValidationInputs(
                data_root=tmp_path,
                manifest_fingerprint=manifest,
                dictionary_path=dictionary_path,
            )
        )
    assert excinfo.value.code == "2A-S5-011"


def test_validation_runner_rejects_empty_cache_bytes(tmp_path: Path) -> None:
    manifest = "a" * 64
    dictionary_path = _write_dictionary(tmp_path)
    _write_gate_receipt(tmp_path, manifest)
    _write_determinism_receipt(tmp_path, manifest)
    _write_site_timezones(tmp_path, manifest, [4])
    manifest_path = _write_tz_cache(tmp_path, manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["rle_cache_bytes"] = 0
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_s4_reports(tmp_path, manifest, [4])

    runner = ValidationRunner()
    with pytest.raises(S0GateError) as excinfo:
        runner.run(
            ValidationInputs(
                data_root=tmp_path,
                manifest_fingerprint=manifest,
                dictionary_path=dictionary_path,
            )
        )
    assert excinfo.value.code == "2A-S5-020"


def test_validation_runner_stages_adjustments_when_present(tmp_path: Path) -> None:
    manifest = "abc" + "0" * 61
    seeds = [9]
    dictionary_path = _write_dictionary(tmp_path)
    _write_gate_receipt(tmp_path, manifest)
    _write_determinism_receipt(tmp_path, manifest)
    _write_site_timezones(tmp_path, manifest, seeds)
    _write_tz_cache(tmp_path, manifest)
    _write_s4_reports(tmp_path, manifest, seeds)
    adjustments_path = _write_tz_adjustments(tmp_path, manifest)

    runner = ValidationRunner()
    result = runner.run(
        ValidationInputs(
            data_root=tmp_path,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
        )
    )

    index_payload = json.loads((result.bundle_path / "index.json").read_text(encoding="utf-8"))
    paths = [entry["path"] for entry in index_payload["files"]]
    assert "evidence/s3/tz_offset_adjustments.json" in paths
    report_payload = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert report_payload["inputs"]["adjustments"]["path"] == str(adjustments_path)
    assert report_payload["inputs"]["adjustments"]["count"] == 1
