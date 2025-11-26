import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import pytest

from engine.scenario_runner.l1_seg_3A import Segment3AConfig, Segment3AOrchestrator
from engine.layers.l1.seg_2A.s0_gate.l0.bundle import compute_index_digest, load_index


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_yaml(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


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
        "reference_data": [],
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


def _stage_upstream(base: Path, fingerprint: str) -> None:
    for seg, sub in (("1A", "validation"), ("1B", "validation")):
        bundle_dir = base / f"data/layer1/{seg}/{sub}/fingerprint={fingerprint}"
        _build_validation_bundle(bundle_dir)
    bundle_dir_2a = base / f"data/layer1/2A/validation/fingerprint={fingerprint}/bundle"
    _build_validation_bundle(bundle_dir_2a)


def _stage_policies(base: Path) -> dict[str, Path]:
    policy_dir = base / "policies"
    policy_paths: dict[str, Path] = {}
    for pid in (
        "zone_mixture_policy",
        "country_zone_alphas",
        "zone_floor_policy",
        "day_effect_policy_v1",
    ):
        ppath = policy_dir / f"{pid}.yaml"
        _write_yaml(ppath, f"semver: 1.0.0\nid: {pid}\n")
        policy_paths[pid] = ppath
    return policy_paths


def test_segment3a_orchestrator_run_and_resume():
    upstream_fp = "a" * 64
    seed = 123
    git_hex = "b" * 40

    with TemporaryDirectory() as tmp:
        base = Path(tmp) / "base"
        base.mkdir(parents=True, exist_ok=True)
        policies = _stage_policies(base)
        dictionary_path = _build_dictionary(base, policies)
        _stage_upstream(base, upstream_fp)

        orchestrator = Segment3AOrchestrator()
        result = orchestrator.run(
            Segment3AConfig(
                data_root=base,
                upstream_manifest_fingerprint=upstream_fp,
                seed=seed,
                git_commit_hex=git_hex,
                dictionary_path=dictionary_path,
            )
        )

        assert result.receipt_path.exists()
        assert result.sealed_inputs_path.exists()
        sealed_df = pl.read_parquet(result.sealed_inputs_path)
        assert set(sealed_df["logical_id"]) >= {
            "zone_mixture_policy",
            "country_zone_alphas",
            "zone_floor_policy",
            "day_effect_policy_v1",
            "validation_bundle_1A",
            "validation_bundle_1B",
            "validation_bundle_2A",
        }
        # resume path reuses outputs
        resumed = orchestrator.run(
            Segment3AConfig(
                data_root=base,
                upstream_manifest_fingerprint=upstream_fp,
                seed=seed,
                git_commit_hex=git_hex,
                dictionary_path=dictionary_path,
                resume=True,
                resume_manifest_fingerprint=result.manifest_fingerprint,
            )
        )
        assert resumed.resumed is True
        assert resumed.receipt_path == result.receipt_path


def test_segment3a_cli_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    upstream_fp = "c" * 64
    seed = 456
    git_hex = "d" * 40
    base = tmp_path / "runroot"
    base.mkdir(parents=True, exist_ok=True)
    policies = _stage_policies(base)
    dictionary_path = _build_dictionary(base, policies)
    _stage_upstream(base, upstream_fp)
    summary_path = base / "summary.json"

    import os
    import sys

    cmd = [
        sys.executable,
        "-m",
        "engine.cli.segment3a",
        "--data-root",
        str(base),
        "--upstream-manifest-fingerprint",
        upstream_fp,
        "--seed",
        str(seed),
        "--git-commit-hex",
        git_hex,
        "--dictionary",
        str(dictionary_path),
        "--result-json",
        str(summary_path),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path("packages/engine/src").resolve())
    result = subprocess.run(
        cmd, env=env, capture_output=True, text=True, check=True
    )
    stdout = result.stdout.strip()
    assert stdout
    payload = json.loads(stdout)
    assert payload["manifest_fingerprint"]
    assert Path(payload["receipt_path"]).exists()
    assert summary_path.exists()
    summary_payload = json.loads(summary_path.read_text())
    assert summary_payload["manifest_fingerprint"] == payload["manifest_fingerprint"]
