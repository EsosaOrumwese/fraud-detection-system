import json
import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl

from engine.layers.l1.seg_3A import S0GateInputs, S0GateRunner
from engine.layers.l1.seg_2A.s0_gate.l0.bundle import compute_index_digest, load_index


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_yaml(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(payload).lstrip(), encoding="utf-8")


def _build_validation_bundle(bundle_root: Path) -> str:
    payload_path = bundle_root / "payload.json"
    _write_json(payload_path, {"ok": True})
    index_payload = [
        {"artifact_id": "payload", "path": payload_path.name},
        {"artifact_id": "self_index", "path": "index.json"},
    ]
    _write_json(bundle_root / "index.json", index_payload)
    index = load_index(bundle_root)
    digest = compute_index_digest(bundle_root, index)
    (bundle_root / "_passed.flag").write_text(f"sha256_hex = {digest}\n", encoding="utf-8")
    return digest


def _build_dictionary(path: Path, policies: dict[str, Path]) -> Path:
    dict_payload = {
        "version": "test",
        "datasets": [
            {
                "id": "s0_gate_receipt_3A",
                "path": "data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json",
                "schema_ref": "schemas.3A.yaml#/validation/s0_gate_receipt_3A",
            },
            {
                "id": "sealed_inputs_3A",
                "path": "data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet",
                "schema_ref": "schemas.3A.yaml#/validation/sealed_inputs_3A",
            },
        ],
        "reports": [
            {
                "id": "segment_state_runs",
                "path": "reports/l1/segment_states/segment_state_runs.jsonl",
                "schema_ref": "schemas.layer1.yaml#/run_report/segment_state_run",
            }
        ],
        "reference_data": [
            {
                "id": "outlet_catalogue",
                "path": "data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/outlet_catalogue.parquet",
                "schema_ref": "schemas.1A.yaml#/egress/outlet_catalogue",
                "description": "Outlet catalogue",
                "licence": "Proprietary-Internal",
            },
            {
                "id": "site_timezones",
                "path": "data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/site_timezones.parquet",
                "schema_ref": "schemas.2A.yaml#/egress/site_timezones",
                "description": "Site timezones",
                "licence": "Proprietary-Internal",
            },
            {
                "id": "tz_timetable_cache",
                "path": "data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/",
                "schema_ref": "schemas.2A.yaml#/cache/tz_timetable_cache",
                "description": "TZ timetable cache",
                "licence": "Proprietary-Internal",
            },
            {
                "id": "iso3166_canonical_2024",
                "path": "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
                "description": "ISO canonical table",
                "licence": "CC-BY-4.0",
            },
            {
                "id": "tz_world_2025a",
                "path": "reference/spatial/tz_world/2025a/tz_world.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/tz_world_2025a",
                "description": "TZ world polygons",
                "licence": "ODbL-1.0",
            },
        ],
    }
    for policy_id, policy_path in policies.items():
        dict_payload["reference_data"].append(
            {
                "id": policy_id,
                "path": str(policy_path),
                "schema_ref": "schemas.3A.yaml#/policy/placeholder",
                "description": policy_id,
                "licence": "Proprietary-Internal",
            }
        )
    dictionary_path = path / "dictionary.yaml"
    _write_yaml(dictionary_path, yaml_dump(dict_payload))
    return dictionary_path


def yaml_dump(payload: dict) -> str:
    import yaml

    return yaml.safe_dump(payload, sort_keys=False)


def test_seg_3a_s0_gate_happy_path():
    upstream_fp = "a" * 64
    seed = "123"
    git_hex = "b" * 40

    with TemporaryDirectory() as tmp:
        base = Path(tmp) / "base"
        out = Path(tmp) / "out"
        # policies
        policy_dir = base / "policies"
        policy_paths = {}
        for pid in (
            "zone_mixture_policy",
            "country_zone_alphas",
            "zone_floor_policy",
            "day_effect_policy_v1",
        ):
            ppath = policy_dir / f"{pid}.yaml"
            _write_yaml(ppath, f"semver: 1.0.0\nid: {pid}\n")
            policy_paths[pid] = ppath

        # dictionary
        dictionary_path = _build_dictionary(base, policy_paths)

        # upstream bundles
        for seg, sub in (("1A", "validation"), ("1B", "validation")):
            bundle_dir = base / f"data/layer1/{seg}/{sub}/fingerprint={upstream_fp}"
            _build_validation_bundle(bundle_dir)
        bundle_dir_2a = base / f"data/layer1/2A/validation/fingerprint={upstream_fp}/bundle"
        _build_validation_bundle(bundle_dir_2a)

        outlet_dir = base / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={upstream_fp}"
        outlet_dir.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(
            {"merchant_id": [1], "legal_country_iso": ["US"], "site_order": [1]}
        ).write_parquet(outlet_dir / "outlet_catalogue.parquet")

        tz_dir = base / f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={upstream_fp}"
        tz_dir.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(
            {
                "merchant_id": [1],
                "legal_country_iso": ["US"],
                "site_order": [1],
                "tzid": ["America/New_York"],
            }
        ).write_parquet(tz_dir / "site_timezones.parquet")

        tz_cache_dir = base / f"data/layer1/2A/tz_timetable_cache/fingerprint={upstream_fp}"
        tz_cache_dir.mkdir(parents=True, exist_ok=True)
        (tz_cache_dir / "tz_timetable_cache.json").write_text('{"tzdb_release_tag": "2025a"}', encoding="utf-8")

        runner = S0GateRunner()
        outputs = runner.run(
            S0GateInputs(
                base_path=base,
                output_base_path=out,
                seed=seed,
                upstream_manifest_fingerprint=upstream_fp,
                git_commit_hex=git_hex,
                dictionary_path=dictionary_path,
            )
        )

        # artefacts exist
        assert outputs.receipt_path.exists()
        assert outputs.sealed_inputs_path.exists()
        df = pl.read_parquet(outputs.sealed_inputs_path)
        expected_assets = {
            "zone_mixture_policy",
            "country_zone_alphas",
            "zone_floor_policy",
            "day_effect_policy_v1",
            "outlet_catalogue",
            "site_timezones",
            "tz_timetable_cache",
            "iso3166_canonical_2024",
            "tz_world_2025a",
            "validation_bundle_1A",
            "validation_bundle_1B",
            "validation_bundle_2A",
        }
        assert set(df["logical_id"]) == expected_assets
        # manifest hash shape
        assert len(outputs.manifest_fingerprint) == 64
        assert outputs.parameter_hash
        assert outputs.determinism_receipt_path.exists()
