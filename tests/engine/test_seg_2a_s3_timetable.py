import hashlib
import json
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from engine.layers.l1.seg_2A.s0_gate.l0.filesystem import (
    aggregate_sha256,
    expand_files,
    hash_files,
)
from engine.layers.l1.seg_2A.s3_timetable import TimetableInputs, TimetableRunner


def _write_dictionary(path: Path) -> Path:
    payload = """
version: test
datasets:
  - id: s0_gate_receipt_2A
    path: data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
  - id: sealed_inputs_v1
    path: data/layer1/2A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.parquet
  - id: tz_timetable_cache
    path: data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/
reference_data:
  - id: tz_world_2025a
    path: reference/spatial/tz_world/2025a/tz_world.parquet
artefacts:
  - id: tzdb_release
    path: artefacts/priors/tzdata/{release_tag}
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
        "sealed_inputs": [
            {
                "id": "tzdb_release",
                "partition": [],
                "schema_ref": "schemas.2A.yaml#/ingress/tzdb_release_v1",
            },
            {
                "id": "tz_world_2025a",
                "partition": [],
                "schema_ref": "schemas.ingress.layer1.yaml#/tz_world_2025a",
            },
        ],
        "validation_bundle_path": "data/layer1/1B/validation/fingerprint=dummy/bundle",
        "verified_at_utc": "2025-11-07T00:00:00.000000Z",
    }
    receipt_path = receipt_dir / "s0_gate_receipt.json"
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return receipt_path


def _write_tz_world(base: Path) -> Path:
    path = base / "reference/spatial/tz_world/2025a/tz_world.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({"tzid": pa.array(["Etc/UTC", "Custom/Zone"])})
    pq.write_table(table, path)
    return path


def _write_tzdb_release(base: Path) -> tuple[Path, str, int]:
    tzdb_dir = base / "artefacts/priors/tzdata/2025a"
    tzdb_dir.mkdir(parents=True, exist_ok=True)
    zone_file = base / "zone1970.tab"
    zone_file.write_text(
        "\n".join(
            [
                "AA\t+0000+00000\tEtc/UTC",
                "BB\t+1111+22222\tCustom/Zone",
            ]
        ),
        encoding="utf-8",
    )
    archive_path = tzdb_dir / "tzdata2025a.tar.gz"
    import tarfile

    with tarfile.open(archive_path, "w:gz") as handle:
        handle.add(zone_file, arcname="zone1970.tab")
    zone_file.unlink()
    version_file = tzdb_dir / "zoneinfo_version.yml"
    version_file.write_text("tzdata=2025a\n", encoding="utf-8")
    digests = hash_files(expand_files(tzdb_dir), error_prefix="TEST_TZDB")
    digest = aggregate_sha256(digests)
    size_bytes = sum(d.size_bytes for d in digests)
    return tzdb_dir, digest, size_bytes


def _write_sealed_inputs(
    base: Path,
    manifest: str,
    tzdb_digest: str,
    tzdb_size: int,
    tz_world_path: Path,
) -> Path:
    inventory_dir = base / f"data/layer1/2A/sealed_inputs/fingerprint={manifest}"
    inventory_dir.mkdir(parents=True, exist_ok=True)
    tz_world_digest = hashlib.sha256(tz_world_path.read_bytes()).hexdigest()
    df = pl.DataFrame(
        [
            {
                "manifest_fingerprint": manifest,
                "asset_id": "tzdb_release",
                "asset_kind": "artefact",
                "basename": "2025a",
                "version_tag": "2025a",
                "schema_ref": "schemas.2A.yaml#/ingress/tzdb_release_v1",
                "catalog_path": "artefacts/priors/tzdata/2025a",
                "partition_keys": [],
                "sha256_hex": tzdb_digest,
                "size_bytes": tzdb_size,
                "license_class": "Proprietary-Internal",
                "notes": None,
            },
            {
                "manifest_fingerprint": manifest,
                "asset_id": "tz_world_2025a",
                "asset_kind": "reference",
                "basename": "tz_world.parquet",
                "version_tag": "2025a",
                "schema_ref": "schemas.ingress.layer1.yaml#/tz_world_2025a",
                "catalog_path": "reference/spatial/tz_world/2025a/tz_world.parquet",
                "partition_keys": [],
                "sha256_hex": tz_world_digest,
                "size_bytes": tz_world_path.stat().st_size,
                "license_class": "ODbL-1.0",
                "notes": None,
            },
        ]
    )
    inventory_path = inventory_dir / "sealed_inputs_v1.parquet"
    df.write_parquet(inventory_path)
    return inventory_path


@pytest.mark.parametrize("resume", [False, True])
def test_timetable_runner_builds_cache(tmp_path: Path, resume: bool) -> None:
    manifest = "d" * 64
    dictionary_path = _write_dictionary(tmp_path)
    tz_world_path = _write_tz_world(tmp_path)
    tzdb_dir, tzdb_digest, tzdb_size = _write_tzdb_release(tmp_path)
    _write_sealed_inputs(tmp_path, manifest, tzdb_digest, tzdb_size, tz_world_path)
    _write_gate_receipt(tmp_path, manifest)

    runner = TimetableRunner()
    result = runner.run(
        TimetableInputs(
            data_root=tmp_path,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            resume=False,
        )
    )
    assert result.resumed is False
    manifest_path = (
        result.output_path / "tz_timetable_cache.json"
    )
    index_path = result.output_path / "tz_index.json"
    assert manifest_path.exists()
    assert index_path.exists()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["manifest_fingerprint"] == manifest
    assert manifest_payload["tzdb_archive_sha256"] == tzdb_digest
    index_entries = json.loads(index_path.read_text(encoding="utf-8"))
    tzids = [entry[0] for entry in index_entries]
    assert tzids == sorted({"Etc/UTC", "Custom/Zone"})

    run_report = Path(result.run_report_path)
    assert run_report.exists()
    report_payload = json.loads(run_report.read_text(encoding="utf-8"))
    assert report_payload["status"] == "pass"
    assert report_payload["compiled"]["tzid_count"] == 2

    resumed_result = runner.run(
        TimetableInputs(
            data_root=tmp_path,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            resume=True,
        )
    )
    assert resumed_result.resumed is True
    assert resumed_result.output_path == result.output_path
