from __future__ import annotations

import pytest

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile, load_wiring
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.runner import ScenarioRunner


def _policy() -> PolicyProfile:
    return PolicyProfile(
        policy_id="sr_policy",
        revision="v0-test",
        content_digest="b" * 64,
        reuse_policy="DENY",
        evidence_wait_seconds=60,
        attempt_limit=1,
        traffic_output_ids=["sealed_inputs_1A"],
    )


def test_dev_min_managed_settlement_rejects_local_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEV_MIN_SR_EXECUTION_IDENTITY", raising=False)
    wiring = WiringProfile(
        profile_id="dev_min",
        object_store_root=str(tmp_path / "artefacts"),
        control_bus_topic="fp.bus.control.v1",
        control_bus_root=str(tmp_path / "control_bus"),
        control_bus_kind="file",
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        gate_map_path="docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
        schema_root="docs/model_spec/platform/contracts/scenario_runner",
        engine_contracts_root="docs/model_spec/data-engine/interface_pack/contracts",
        authority_store_dsn=f"sqlite:///{(tmp_path / 'sr_authority.db').as_posix()}",
        acceptance_mode="dev_min_managed",
        execution_mode="local",
        state_mode="local",
        execution_launch_ref="",
        execution_identity_env="DEV_MIN_SR_EXECUTION_IDENTITY",
    )
    with pytest.raises(RuntimeError, match="SR_SETTLEMENT_LOCK_FAIL_CLOSED"):
        ScenarioRunner(wiring, _policy(), LocalEngineInvoker())


def test_load_wiring_expands_env_tokens(tmp_path, monkeypatch) -> None:
    wiring_path = tmp_path / "wiring.yaml"
    wiring_path.write_text(
        "\n".join(
            [
                "object_store_root: s3://${TEST_BUCKET}/fraud-platform",
                "control_bus_topic: fp.bus.control.v1",
                "control_bus_root: runs/fraud-platform/control_bus",
                "engine_catalogue_path: docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
                "gate_map_path: docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
                "schema_root: docs/model_spec/platform/contracts/scenario_runner",
                "engine_contracts_root: docs/model_spec/data-engine/interface_pack/contracts",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_BUCKET", "fraud-platform-dev-min-object-store")
    wiring = load_wiring(wiring_path)
    assert wiring.object_store_root == "s3://fraud-platform-dev-min-object-store/fraud-platform"
