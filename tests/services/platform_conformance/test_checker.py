from __future__ import annotations

from pathlib import Path

import yaml

from fraud_detection.platform_conformance.checker import run_environment_conformance


def test_environment_conformance_passes_for_repo_profiles(tmp_path: Path) -> None:
    output = tmp_path / "conformance.json"
    result = run_environment_conformance(
        local_parity_profile="config/platform/profiles/local_parity.yaml",
        dev_profile="config/platform/profiles/dev.yaml",
        prod_profile="config/platform/profiles/prod.yaml",
        platform_run_id="platform_20260208T230000Z",
        output_path=str(output),
    )
    assert result.status == "PASS"
    assert output.exists()
    assert result.payload["status"] == "PASS"


def test_environment_conformance_fails_on_security_mode_drift(tmp_path: Path) -> None:
    local_payload = yaml.safe_load(Path("config/platform/profiles/local_parity.yaml").read_text(encoding="utf-8"))
    dev_payload = yaml.safe_load(Path("config/platform/profiles/dev.yaml").read_text(encoding="utf-8"))
    prod_payload = yaml.safe_load(Path("config/platform/profiles/prod.yaml").read_text(encoding="utf-8"))

    dev_payload.setdefault("wiring", {}).setdefault("security", {})["auth_mode"] = "api_key"

    local_path = tmp_path / "local_parity.yaml"
    dev_path = tmp_path / "dev.yaml"
    prod_path = tmp_path / "prod.yaml"
    local_path.write_text(yaml.safe_dump(local_payload, sort_keys=False), encoding="utf-8")
    dev_path.write_text(yaml.safe_dump(dev_payload, sort_keys=False), encoding="utf-8")
    prod_path.write_text(yaml.safe_dump(prod_payload, sort_keys=False), encoding="utf-8")

    result = run_environment_conformance(
        local_parity_profile=str(local_path),
        dev_profile=str(dev_path),
        prod_profile=str(prod_path),
        platform_run_id="platform_20260208T230100Z",
        output_path=str(tmp_path / "failed_conformance.json"),
    )
    assert result.status == "FAIL"
    checks = {item["check_id"]: item for item in result.payload["checks"]}
    assert checks["security_corridor_posture"]["status"] == "FAIL"
