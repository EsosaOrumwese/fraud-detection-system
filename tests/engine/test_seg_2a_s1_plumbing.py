import json
from pathlib import Path

import pytest

from engine.layers.l1.seg_2A.shared.receipt import load_gate_receipt
from engine.layers.l1.seg_2A.s1_provisional import ProvisionalLookupInputs, ProvisionalLookupRunner


@pytest.fixture()
def manifest_fingerprint() -> str:
    return "a" * 64


@pytest.fixture()
def seed() -> int:
    return 2025110601


def _build_dictionary() -> dict[str, object]:
    return {
        "datasets": [
            {
                "id": "s0_gate_receipt_2A",
                "path": "data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json",
            }
        ],
        "reference_data": [
            {
                "id": "site_locations",
                "path": "data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/",
            },
            {
                "id": "tz_world_2025a",
                "path": "reference/spatial/tz_world/2025a/tz_world.parquet",
            },
        ],
        "policies": [
            {
                "id": "tz_nudge",
                "path": "config/timezone/tz_nudge.yml",
            },
            {
                "id": "tz_overrides",
                "path": "config/timezone/tz_overrides.yaml",
            },
        ],
    }


def _write_receipt(base_path: Path, manifest_fingerprint: str) -> Path:
    receipt_path = (
        base_path
        / f"data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": "abc123",
        "validation_bundle_path": "data/layer1/1B/validation/fingerprint=abc/bundle",
        "flag_sha256_hex": "1" * 64,
        "verified_at_utc": "2025-11-06T00:00:00.000000Z",
        "sealed_inputs": [
            {
                "id": "site_locations",
                "partition": ["seed=2025110601", f"fingerprint={manifest_fingerprint}"],
                "schema_ref": "schemas.1B.yaml#/egress/site_locations",
            },
            {
                "id": "tz_world_2025a",
                "partition": [],
                "schema_ref": "schemas.ingress.layer1.yaml#/tz_world_2025a",
            },
        ],
    }
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return receipt_path


def _write_assets(base_path: Path, seed: int, manifest_fingerprint: str) -> None:
    (base_path / f"data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}").mkdir(
        parents=True, exist_ok=True
    )
    tz_world = base_path / "reference/spatial/tz_world/2025a"
    tz_world.mkdir(parents=True, exist_ok=True)
    (tz_world / "tz_world.parquet").write_text("", encoding="utf-8")
    tz_nudge = base_path / "config/timezone"
    tz_nudge.mkdir(parents=True, exist_ok=True)
    (tz_nudge / "tz_nudge.yml").write_text("semver: \"1.0.0\"\nsha256_digest: \"00\"\n", encoding="utf-8")
    (tz_nudge / "tz_overrides.yaml").write_text("semver: \"1.0.0\"\nsha256_digest: \"00\"\noverrides: []\n", encoding="utf-8")


def test_load_gate_receipt(tmp_path: Path, manifest_fingerprint: str) -> None:
    dictionary = _build_dictionary()
    _write_receipt(tmp_path, manifest_fingerprint)
    summary = load_gate_receipt(
        base_path=tmp_path,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
    )
    assert summary.manifest_fingerprint == manifest_fingerprint
    assert summary.assets[0].asset_id == "site_locations"
    assert summary.path.exists()


def test_resolve_assets(tmp_path: Path, manifest_fingerprint: str, seed: int) -> None:
    dictionary = _build_dictionary()
    _write_receipt(tmp_path, manifest_fingerprint)
    _write_assets(tmp_path, seed, manifest_fingerprint)
    runner = ProvisionalLookupRunner()
    inputs = ProvisionalLookupInputs(
        data_root=tmp_path,
        seed=seed,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
    )
    receipt = load_gate_receipt(
        base_path=tmp_path,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
    )
    context = runner._prepare_context(
        data_root=tmp_path,
        seed=seed,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
        receipt=receipt,
    )
    assert context.assets.site_locations.name == f"fingerprint={manifest_fingerprint}"
    assert context.assets.tz_world.name == "tz_world.parquet"
    assert context.assets.tz_nudge.name == "tz_nudge.yml"
    assert context.receipt_path == receipt.path

