import json
from pathlib import Path

import geopandas as gpd
import polars as pl
import pytest
from shapely.geometry import Polygon

from engine.layers.l1.seg_2A.shared.receipt import load_gate_receipt
from engine.layers.l1.seg_2A.s1_provisional import ProvisionalLookupInputs, ProvisionalLookupRunner


@pytest.fixture()
def manifest_fingerprint() -> str:
    return "a" * 64


@pytest.fixture()
def seed() -> int:
    return 2025110601


@pytest.fixture()
def site_fingerprint() -> str:
    return "f" * 64


def _build_dictionary() -> dict[str, object]:
    return {
        "datasets": [
            {
                "id": "s0_gate_receipt_2A",
                "path": "data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json",
            },
            {
                "id": "s1_tz_lookup",
                "path": "data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/",
            },
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


def _write_receipt(base_path: Path, manifest_fingerprint: str, *, site_fingerprint: str | None = None) -> Path:
    receipt_path = (
        base_path
        / f"data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    site_fp = site_fingerprint or manifest_fingerprint
    payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": "abc123",
        "validation_bundle_path": "data/layer1/1B/validation/fingerprint=abc/bundle",
        "flag_sha256_hex": "1" * 64,
        "verified_at_utc": "2025-11-06T00:00:00.000000Z",
        "sealed_inputs": [
            {
                "id": "site_locations",
                "partition": ["seed=2025110601", f"fingerprint={site_fp}"],
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


def _write_assets(base_path: Path, seed: int, manifest_fingerprint: str, *, site_fingerprint: str | None = None) -> None:
    site_fp = site_fingerprint or manifest_fingerprint
    site_dir = base_path / f"data/layer1/1B/site_locations/seed={seed}/fingerprint={site_fp}"
    site_dir.mkdir(parents=True, exist_ok=True)
    site_df = pl.DataFrame(
        {
            "merchant_id": ["M1", "M2"],
            "legal_country_iso": ["US", "US"],
            "site_order": [1, 2],
            "lat_deg": [0.5, 1.0],
            "lon_deg": [0.5, 1.0],
        }
    )
    site_df.write_parquet(site_dir / "part-00000.parquet")

    tz_world_dir = base_path / "reference/spatial/tz_world/2025a"
    tz_world_dir.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(
        {"tzid": ["TZ_A", "TZ_B"]},
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(1, 1), (2, 1), (2, 2), (1, 2)]),
        ],
        crs="EPSG:4326",
    )
    gdf.to_parquet(tz_world_dir / "tz_world.parquet")

    tz_nudge = base_path / "config/timezone"
    tz_nudge.mkdir(parents=True, exist_ok=True)
    (tz_nudge / "tz_nudge.yml").write_text(
        "semver: \"1.0.0\"\nsha256_digest: \"00\"\nnudge_distance_degrees: 0.0001\n",
        encoding="utf-8",
    )
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


def test_resolve_assets(tmp_path: Path, manifest_fingerprint: str, seed: int, site_fingerprint: str) -> None:
    dictionary = _build_dictionary()
    _write_receipt(tmp_path, manifest_fingerprint, site_fingerprint=site_fingerprint)
    _write_assets(tmp_path, seed, manifest_fingerprint, site_fingerprint=site_fingerprint)
    runner = ProvisionalLookupRunner()
    inputs = ProvisionalLookupInputs(
        data_root=tmp_path,
        seed=seed,
        manifest_fingerprint=manifest_fingerprint,
        upstream_manifest_fingerprint=site_fingerprint,
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
        upstream_manifest_fingerprint=site_fingerprint,
        dictionary=dictionary,
        receipt=receipt,
    )
    assert context.assets.site_locations.name == f"fingerprint={site_fingerprint}"
    assert context.assets.tz_world.name == "tz_world.parquet"
    assert context.assets.tz_nudge.name == "tz_nudge.yml"
    assert context.receipt_path == receipt.path
    assert context.upstream_manifest_fingerprint == site_fingerprint


def test_runner_executes_lookup(tmp_path: Path, manifest_fingerprint: str, seed: int, site_fingerprint: str) -> None:
    dictionary = _build_dictionary()
    _write_receipt(tmp_path, manifest_fingerprint, site_fingerprint=site_fingerprint)
    _write_assets(tmp_path, seed, manifest_fingerprint, site_fingerprint=site_fingerprint)
    runner = ProvisionalLookupRunner()
    receipt = load_gate_receipt(
        base_path=tmp_path,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
    )
    result = runner.run(
        ProvisionalLookupInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            upstream_manifest_fingerprint=site_fingerprint,
            dictionary=dictionary,
            chunk_size=10,
        )
    )
    assert result.output_path.exists()
    parts = sorted(result.output_path.glob("*.parquet"))
    assert parts, "expected output parquet files"
    output_df = pl.read_parquet(parts[0]).sort(["merchant_id", "site_order"])
    tzids = output_df["tzid_provisional"].to_list()
    assert tzids == ["TZ_A", "TZ_B"]
    nudge_lat = output_df["nudge_lat_deg"].to_list()
    assert nudge_lat[0] is None
    assert nudge_lat[1] is not None
    created = output_df["created_utc"].unique().to_list()
    assert created == [receipt.verified_at_utc]

    report_path = (
        tmp_path
        / "reports"
        / "l1"
        / "s1_provisional_lookup"
        / f"seed={seed}"
        / f"fingerprint={manifest_fingerprint}"
        / "run_report.json"
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["rows_total"] == 2
    assert payload["s0_verified_at_utc"] == receipt.verified_at_utc
