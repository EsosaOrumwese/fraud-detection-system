import json
import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory

import geopandas as gpd
import polars as pl
import pytest
from shapely.geometry import Polygon

from engine.layers.l1.seg_2A import S0GateInputs, S0GateOutputs, S0GateRunner, S0SealedAsset
from engine.layers.l1.seg_2A.s0_gate.l0.bundle import compute_index_digest, load_index


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_yaml(path: Path, payload: str) -> None:
    path.write_text(textwrap.dedent(payload).lstrip(), encoding="utf-8")


def _build_dictionary(tmp: Path) -> Path:
    dictionary_payload = """
    version: test
    datasets:
      s0_gate_receipt_2A:
        path: data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
        schema_ref: schemas.2A.yaml#/validation/s0_gate_receipt_v1
        partitioning: [fingerprint]
        version: "{manifest_fingerprint}"
        license: Proprietary-Internal
      sealed_inputs_v1:
        path: data/layer1/2A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.parquet
        schema_ref: schemas.2A.yaml#/manifests/sealed_inputs_v1
        partitioning: [fingerprint]
        version: "{manifest_fingerprint}"
        license: Proprietary-Internal
      s1_tz_lookup:
        path: data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/
        schema_ref: schemas.2A.yaml#/plan/s1_tz_lookup
        partitioning: [seed, fingerprint]
        version: "{seed}.{manifest_fingerprint}"
        license: Proprietary-Internal
      merchant_mcc_map:
        path: data/layer1/2A/merchant_mcc_map/seed={seed}/fingerprint={manifest_fingerprint}/merchant_mcc_map.parquet
        schema_ref: schemas.2A.yaml#/reference/merchant_mcc_map
        partitioning: [seed, fingerprint]
        version: "{seed}.{manifest_fingerprint}"
        license: Proprietary-Internal
    reference_data:
      site_locations:
        path: data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
        schema_ref: schemas.1B.yaml#/egress/site_locations
        partitioning: [seed, fingerprint]
        version: "{seed}.{manifest_fingerprint}"
        license: Proprietary-Internal
      tz_world_2025a:
        path: reference/spatial/tz_world/2025a/tz_world.parquet
        schema_ref: schemas.ingress.layer1.yaml#/tz_world_2025a
        partitioning: []
        version: "2025a"
        license: ODbL-1.0
      iso3166_canonical_2024:
        path: reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet
        schema_ref: schemas.ingress.layer1.yaml#/iso3166_canonical_2024
        partitioning: []
        version: "2024-12-31"
        license: CC-BY-4.0
    policies:
      tz_overrides:
        path: config/timezone/tz_overrides.yaml
        schema_ref: schemas.2A.yaml#/policy/tz_overrides_v1
        partitioning: []
        version: "{semver}"
        license: Proprietary-Internal
      tz_nudge:
        path: config/timezone/tz_nudge.yml
        schema_ref: schemas.2A.yaml#/policy/tz_nudge_v1
        partitioning: []
        version: "{semver}"
        license: Proprietary-Internal
    artefacts:
      tzdb_release:
        path: artefacts/priors/tzdata/{release_tag}/
        schema_ref: schemas.2A.yaml#/ingress/tzdb_release_v1
        partitioning: []
        version: "{release_tag}"
        license: Proprietary-Internal
    validation:
      validation_bundle_1B:
        path: data/layer1/1B/validation/fingerprint={manifest_fingerprint}/bundle/
        schema_ref: schemas.1B.yaml#/validation/validation_bundle_1B
        partitioning: [fingerprint]
        version: "{manifest_fingerprint}"
        license: Proprietary-Internal
      validation_passed_flag_1B:
        path: data/layer1/1B/validation/fingerprint={manifest_fingerprint}/_passed.flag
        schema_ref: schemas.layer1.yaml#/validation/passed_flag
        partitioning: [fingerprint]
        version: "{manifest_fingerprint}"
        license: Proprietary-Internal
      validation_bundle_2A:
        path: data/layer1/2A/validation/fingerprint={manifest_fingerprint}/
        schema_ref: schemas.2A.yaml#/validation/validation_bundle_2A
        partitioning: [fingerprint]
        version: "{manifest_fingerprint}"
        license: Proprietary-Internal
      validation_passed_flag_2A:
        path: data/layer1/2A/validation/fingerprint={manifest_fingerprint}/_passed.flag
        schema_ref: schemas.layer1.yaml#/validation/passed_flag
        partitioning: [fingerprint]
        version: "{manifest_fingerprint}"
        license: Proprietary-Internal
    """
    dictionary_path = tmp / "dictionary.yaml"
    _write_yaml(dictionary_path, dictionary_payload)
    return dictionary_path


def _build_validation_bundle(fingerprint_dir: Path) -> tuple[Path, str]:
    bundle_dir = fingerprint_dir / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    payload_path = bundle_dir / "bundle_payload.json"
    _write_json(payload_path, {"bundle": "ok"})
    index_payload = {
        "artifacts": [
            {"artifact_id": "payload", "path": payload_path.name},
            {"artifact_id": "self_index", "path": "index.json"},
        ]
    }
    _write_json(bundle_dir / "index.json", index_payload)
    index = load_index(bundle_dir)
    digest = compute_index_digest(bundle_dir, index)
    (bundle_dir / "_passed.flag").write_text(f"sha256_hex = {digest}\n", encoding="utf-8")
    return bundle_dir, digest


def _write_reference_files(base: Path, seed: str, upstream_fp: str, tz_release: str) -> None:
    run_seed_dir = base / f"data/layer1/1B/site_locations/seed={seed}/fingerprint={upstream_fp}"
    run_seed_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "manifest_fingerprint": [upstream_fp, upstream_fp],
            "seed": [int(seed), int(seed)],
            "merchant_id": ["M1", "M2"],
            "legal_country_iso": ["US", "US"],
            "site_order": [0, 1],
            "lat_deg": [0.5, 1.0],
            "lon_deg": [0.5, 1.0],
        }
    ).write_parquet(run_seed_dir / "site_locations.parquet")

    tz_world_dir = base / "reference/spatial/tz_world/2025a"
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

    iso_dir = base / "reference/iso/iso3166_canonical/2024-12-31"
    iso_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"iso": ["US"]}).write_parquet(iso_dir / "iso3166.parquet")

    tzdb_dir = base / f"artefacts/priors/tzdata/{tz_release}"
    tzdb_dir.mkdir(parents=True, exist_ok=True)
    (tzdb_dir / "tzdata.txt").write_text("tzdata fixture", encoding="utf-8")

    config_dir = base / "config/timezone"
    config_dir.mkdir(parents=True, exist_ok=True)
    zero_hex = "0" * 64
    _write_yaml(
        config_dir / "tz_overrides.yaml",
        f"""
        semver: "1.0.0"
        sha256_digest: "{zero_hex}"
        overrides:
          - scope: "country:US"
            tzid: "America/New_York"
            evidence_url: "https://example.test"
            expiry_yyyy_mm_dd: null
        """,
    )
    _write_yaml(
        config_dir / "tz_nudge.yml",
        f"""
        semver: "1.0.0"
        sha256_digest: "{zero_hex}"
        nudge_distance_degrees: 0.0001
        """,
    )


def test_segment_2a_s0_runner_end_to_end():
    upstream_fp = "a" * 64
    git_commit_hex = "b" * 64
    tz_release = "test-release"
    seed = "42"

    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        dictionary_path = _build_dictionary(root)
        validation_dir = root / f"data/layer1/1B/validation/fingerprint={upstream_fp}"
        validation_dir.mkdir(parents=True, exist_ok=True)
        bundle_dir, declared_flag = _build_validation_bundle(validation_dir)
        _write_reference_files(root, seed, upstream_fp, tz_release)

        runner = S0GateRunner()
        inputs = S0GateInputs(
            base_path=root,
            output_base_path=root,
            seed=int(seed),
            upstream_manifest_fingerprint=upstream_fp,
            tzdb_release_tag=tz_release,
            git_commit_hex=git_commit_hex,
            dictionary_path=dictionary_path,
        )

        outputs: S0GateOutputs = runner.run(inputs)

        assert len(outputs.manifest_fingerprint) == 64
        assert len(outputs.parameter_hash) == 64
        assert outputs.flag_sha256_hex == declared_flag
        assert outputs.receipt_path.exists()
        assert outputs.inventory_path.exists()
        assert outputs.validation_bundle_path == bundle_dir

        receipt_payload = json.loads(outputs.receipt_path.read_text(encoding="utf-8"))
        assert receipt_payload["manifest_fingerprint"] == outputs.manifest_fingerprint
        assert receipt_payload["parameter_hash"] == outputs.parameter_hash
        assert receipt_payload["flag_sha256_hex"] == declared_flag
        sealed_ids = {entry["id"] for entry in receipt_payload["sealed_inputs"]}
        expected_ids = {
            "validation_bundle_1B",
            "validation_passed_flag_1B",
            "site_locations",
            "tz_world_2025a",
            "tzdb_release",
            "tz_overrides",
            "tz_nudge",
            "iso3166_canonical_2024",
            "merchant_mcc_map",
        }
        assert expected_ids.issubset(sealed_ids)
        merchant_map_path = (
            root
            / f"data/layer1/2A/merchant_mcc_map/seed={seed}/fingerprint={upstream_fp}/merchant_mcc_map.parquet"
        )
        assert merchant_map_path.exists()
        merchant_sample = pl.read_parquet(merchant_map_path, n_rows=5)
        assert merchant_sample.columns == ["merchant_id", "mcc"]
        assert merchant_sample.height > 0

        inventory_frame = pl.read_parquet(outputs.inventory_path)
        assert inventory_frame.shape[0] == len(outputs.sealed_assets)
        assert inventory_frame["manifest_fingerprint"].unique().to_list() == [
            outputs.manifest_fingerprint
        ]

        sealed_by_id = {asset.asset_id: asset for asset in outputs.sealed_assets}
        assert set(sealed_by_id) == sealed_ids
        assert isinstance(sealed_by_id["validation_bundle_1B"], S0SealedAsset)
        assert len(sealed_by_id["validation_passed_flag_1B"].sha256_hex) == 64
        assert sealed_by_id["tz_overrides"].size_bytes > 0
        assert sealed_by_id["tz_nudge"].size_bytes > 0

        assert "sha256_hex" in outputs.determinism_receipt
        assert len(outputs.determinism_receipt["sha256_hex"]) == 64
        determinism_path = outputs.run_report_path.parent / "determinism_receipt.json"
        assert determinism_path.exists()
        determinism_payload = json.loads(determinism_path.read_text(encoding="utf-8"))
        assert determinism_payload["sha256_hex"] == outputs.determinism_receipt["sha256_hex"]
        assert outputs.run_report_path.exists()
        report_payload = json.loads(outputs.run_report_path.read_text(encoding="utf-8"))
        assert report_payload["segment"] == "2A"
        assert report_payload["state"] == "S0"
        assert report_payload["manifest_fingerprint"] == outputs.manifest_fingerprint
        assert report_payload["determinism"]["sha256_hex"] == outputs.determinism_receipt["sha256_hex"]
        assert report_payload["sealed_inputs"]["count"] == len(outputs.sealed_assets)
