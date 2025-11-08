import json
from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_2A.s4_legality import LegalityInputs, LegalityRunner


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


def _write_site_timezones(base: Path, seed: int, manifest: str) -> Path:
    partition_dir = base / f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(
        {
            "tzid": ["America/New_York", "America/New_York", "Etc/UTC"],
        }
    )
    df.write_parquet(partition_dir / "part-00000.parquet")
    return partition_dir


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
    (cache_dir / "tz_timetable_cache.json").write_text(
        json.dumps(manifest_payload, indent=2), encoding="utf-8"
    )
    tz_index = [
        ["America/New_York", [[-9223372036854775808, -300], [0, -240], [3600, -300]]],
        ["Etc/UTC", [[-9223372036854775808, 0]]],
    ]
    (cache_dir / "tz_index.json").write_text(
        json.dumps(tz_index, separators=(",", ":")), encoding="utf-8"
    )
    return cache_dir


def _write_tz_adjustments(base: Path, manifest: str, count: int = 2) -> Path:
    adjustments_dir = base / f"data/layer1/2A/tz_offset_adjustments/fingerprint={manifest}"
    adjustments_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifest_fingerprint": manifest,
        "created_utc": "2025-11-08T00:00:00.000000Z",
        "count": count,
        "adjustments": [
            {
                "tzid": "America/New_York",
                "transition_unix_utc": -9223372036854775808,
                "raw_seconds": -18010,
                "adjusted_minutes": -300,
                "reasons": ["clip"],
            }
            for _ in range(count)
        ],
    }
    path = adjustments_dir / "tz_offset_adjustments.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_legality_runner_builds_report(tmp_path: Path) -> None:
    seed = 42
    manifest = "a" * 64
    dictionary_path = _write_dictionary(tmp_path)
    _write_gate_receipt(tmp_path, manifest)
    _write_site_timezones(tmp_path, seed, manifest)
    _write_tz_cache(tmp_path, manifest)

    runner = LegalityRunner()
    result = runner.run(
        LegalityInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
        )
    )
    assert result.resumed is False
    assert result.output_path.exists()
    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["counts"]["sites_total"] == 3
    assert payload["counts"]["tzids_total"] == 2
    assert payload["counts"]["gap_windows_total"] == 60  # -300 -> -240
    assert payload["counts"]["fold_windows_total"] == 60
    assert payload["missing_tzids"] == []

    run_report = Path(result.run_report_path)
    assert run_report.exists()
    report_payload = json.loads(run_report.read_text(encoding="utf-8"))
    assert report_payload["status"] == "PASS"
    assert report_payload["counts"]["gap_windows_total"] == 60
    assert report_payload["adjustments"]["path"] is None
    assert report_payload["adjustments"]["count"] == 0

    resumed = runner.run(
        LegalityInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            resume=True,
        )
    )
    assert resumed.resumed is True
    assert resumed.output_path == result.output_path


def test_legality_runner_reports_adjustments_metadata(tmp_path: Path) -> None:
    seed = 8
    manifest = "c" * 64
    dictionary_path = _write_dictionary(tmp_path)
    _write_gate_receipt(tmp_path, manifest)
    _write_site_timezones(tmp_path, seed, manifest)
    _write_tz_cache(tmp_path, manifest)
    adjustments_path = _write_tz_adjustments(tmp_path, manifest, count=3)

    runner = LegalityRunner()
    result = runner.run(
        LegalityInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
        )
    )
    report_payload = json.loads(Path(result.run_report_path).read_text(encoding="utf-8"))
    assert report_payload["adjustments"]["path"] == str(adjustments_path)
    assert report_payload["adjustments"]["count"] == 3
    assert report_payload["adjustments"]["tzids_sample"] == ["America/New_York"]


def test_legality_runner_flags_missing_tzid(tmp_path: Path) -> None:
    seed = 7
    manifest = "b" * 64
    dictionary_path = _write_dictionary(tmp_path)
    _write_gate_receipt(tmp_path, manifest)
    _write_site_timezones(tmp_path, seed, manifest)
    cache_dir = _write_tz_cache(tmp_path, manifest)
    # Remove America/New_York to trigger coverage failure
    tz_index_path = cache_dir / "tz_index.json"
    raw = json.loads(tz_index_path.read_text(encoding="utf-8"))
    tz_index_path.write_text(json.dumps(raw[1:], indent=2), encoding="utf-8")

    runner = LegalityRunner()
    result = runner.run(
        LegalityInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
        )
    )
    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert payload["missing_tzids"] == ["America/New_York"]
