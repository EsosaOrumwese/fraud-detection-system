from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.ids import run_id_from_equivalence_key
from fraud_detection.scenario_runner.models import RunRequest, RunWindow, ScenarioBinding, Strategy
from fraud_detection.scenario_runner.runner import ScenarioRunner


def _write_catalogue(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "version: '1.0'",
                "outputs:",
                "- output_id: test_output",
                "  class: surface",
                "  exposure: internal",
                "  scope: scope_seed_parameter_hash",
                "  owner_segment: T0",
                "  path_template: data/test_output/seed={seed}/parameter_hash={parameter_hash}/out.json",
                "  partitions:",
                "  - seed",
                "  - parameter_hash",
                "  read_requires_gates: []",
            ]
        ),
        encoding="utf-8",
    )


def _write_gate_map(path: Path) -> None:
    path.write_text("version: '1.0'\ngates: []\n", encoding="utf-8")


def _build_wiring(tmp_path: Path, catalogue_path: Path, gate_map_path: Path) -> WiringProfile:
    return WiringProfile(
        object_store_root=str(tmp_path / "artefacts"),
        control_bus_topic="fp.bus.control.v1",
        control_bus_root=str(tmp_path / "control_bus"),
        engine_catalogue_path=str(catalogue_path),
        gate_map_path=str(gate_map_path),
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
        evidence_wait_seconds=1,
        attempt_limit=1,
        traffic_output_ids=["test_output"],
        allow_instance_proof_bridge=False,
    )


def _build_request(engine_root: Path, run_key: str) -> RunRequest:
    return RunRequest(
        run_equivalence_key=run_key,
        manifest_fingerprint="a" * 64,
        parameter_hash="c" * 64,
        seed=1,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        output_ids=["test_output"],
        engine_run_root=str(engine_root),
        requested_strategy=Strategy.FORCE_REUSE,
        invoker="test",
    )


def _write_output(engine_root: Path) -> None:
    relative = f"data/test_output/seed=1/parameter_hash={'c' * 64}/out.json"
    output_path = engine_root / relative
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("{\"ok\": true}", encoding="utf-8")


def test_instance_proof_emits_receipt_and_ready(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_root"
    _write_output(engine_root)

    catalogue_path = tmp_path / "engine_outputs.catalogue.yaml"
    gate_map_path = tmp_path / "engine_gates.map.yaml"
    _write_catalogue(catalogue_path)
    _write_gate_map(gate_map_path)

    wiring = _build_wiring(tmp_path, catalogue_path, gate_map_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(engine_root)))

    request = _build_request(engine_root, "instance-proof-strict")
    response = runner.submit_run(request)

    assert response.message == "READY committed"
    run_id = run_id_from_equivalence_key("instance-proof-strict")
    status = runner.ledger.read_status(run_id)
    assert status is not None
    assert status.state.value == "READY"
    facts_view = runner.ledger.read_facts_view(run_id)
    assert facts_view is not None
    receipts = facts_view.get("instance_receipts") or []
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["output_id"] == "test_output"
    assert receipt["status"] == "PASS"
    receipt_path = receipt["artifacts"]["receipt_path"]
    assert receipt_path.startswith("fraud-platform/sr/instance_receipts/output_id=test_output/")
    assert (tmp_path / "artefacts" / receipt_path).exists()
