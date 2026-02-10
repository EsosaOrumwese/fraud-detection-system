from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.models import RunRequest, RunWindow, ScenarioBinding, Strategy
from fraud_detection.scenario_runner.runner import ScenarioRunner


pytestmark = pytest.mark.integration


def _build_wiring(tmp_path: Path, gate_map_path: Path | None = None) -> WiringProfile:
    return WiringProfile(
        object_store_root=str(tmp_path / "artefacts"),
        control_bus_topic="fp.bus.control.v1",
        control_bus_root=str(tmp_path / "control_bus"),
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        gate_map_path=str(gate_map_path) if gate_map_path else "docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
        schema_root="docs/model_spec/platform/contracts/scenario_runner",
        engine_contracts_root="docs/model_spec/data-engine/interface_pack/contracts",
        authority_store_dsn=f"sqlite:///{(tmp_path / 'sr_authority.db').as_posix()}",
    )


def _build_policy() -> PolicyProfile:
    return PolicyProfile(
        policy_id="sr_policy",
        revision="v0-test",
        content_digest="b" * 64,
        reuse_policy="ALLOW",
        evidence_wait_seconds=60,
        attempt_limit=1,
        traffic_output_ids=["sealed_inputs_1A"],
    )


def _base_request(tmp_path: Path) -> RunRequest:
    return RunRequest(
        run_equivalence_key="fail-closed",
        manifest_fingerprint="a" * 64,
        parameter_hash="b" * 64,
        seed=7,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        engine_run_root=str(tmp_path / "engine_root"),
        requested_strategy=Strategy.FORCE_REUSE,
        invoker="test",
    )


def test_unknown_output_id_fails_closed(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(tmp_path / "engine_root")))
    request = _base_request(tmp_path)
    request.output_ids = ["unknown_output"]

    response = runner.submit_run(request)
    status = runner.ledger.read_status(response.run_id)
    assert status is not None
    assert status.state.value == "FAILED"
    assert status.reason_code == "UNKNOWN_OUTPUT_ID"


def test_unknown_gate_id_fails_closed(tmp_path: Path) -> None:
    gate_map_path = tmp_path / "gate_map.yaml"
    gate_map_path.write_text("version: '1.0'\ngates: []\n", encoding="utf-8")
    wiring = _build_wiring(tmp_path, gate_map_path=gate_map_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(tmp_path / "engine_root")))
    request = _base_request(tmp_path)
    request.output_ids = ["sealed_inputs_1A"]

    response = runner.submit_run(request)
    status = runner.ledger.read_status(response.run_id)
    assert status is not None
    assert status.state.value == "FAILED"
    assert status.reason_code == "UNKNOWN_GATE_ID"
