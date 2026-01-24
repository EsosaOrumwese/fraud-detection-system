from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.ids import run_id_from_equivalence_key
from fraud_detection.scenario_runner.models import RunRequest, RunWindow, ScenarioBinding, Strategy
from fraud_detection.scenario_runner.runner import ScenarioRunner


def _build_wiring(tmp_path: Path) -> WiringProfile:
    return WiringProfile(
        object_store_root=str(tmp_path / "artefacts"),
        control_bus_topic="fp.bus.control.v1",
        control_bus_root=str(tmp_path / "control_bus"),
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        gate_map_path="docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
        schema_root="docs/model_spec/platform/contracts/scenario_runner",
        engine_contracts_root="docs/model_spec/data-engine/interface_pack/contracts",
        authority_store_dsn=f"sqlite:///{(tmp_path / 'sr_authority.db').as_posix()}",
    )


def _build_policy(attempt_limit: int = 1) -> PolicyProfile:
    return PolicyProfile(
        policy_id="sr_policy",
        revision="v0-test",
        content_digest="b" * 64,
        reuse_policy="DENY",
        evidence_wait_seconds=60,
        attempt_limit=attempt_limit,
        traffic_output_ids=["sealed_inputs_1A"],
    )


def _build_request(run_key: str, engine_root: Path) -> RunRequest:
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
        output_ids=["sealed_inputs_1A"],
        engine_run_root=str(engine_root),
        requested_strategy=Strategy.FORCE_INVOKE,
        invoker="test",
    )


def _write_run_receipt(engine_root: Path, run_id: str, manifest: str, parameter_hash: str, seed: int) -> None:
    payload = {
        "run_id": run_id,
        "manifest_fingerprint": manifest,
        "parameter_hash": parameter_hash,
        "seed": seed,
        "created_utc": datetime.now(tz=timezone.utc).isoformat(),
    }
    (engine_root / "run_receipt.json").write_text(json.dumps(payload), encoding="utf-8")


def test_engine_receipt_missing_fails(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_root"
    engine_root.mkdir(parents=True, exist_ok=True)
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(engine_root)))

    request = _build_request("engine-missing-receipt", engine_root)
    response = runner.submit_run(request)

    assert response.message == "Engine attempt failed."
    run_id = run_id_from_equivalence_key("engine-missing-receipt")
    status = runner.ledger.read_status(run_id)
    assert status is not None
    assert status.state.value == "FAILED"
    assert status.reason_code == "ENGINE_RECEIPT_MISSING"


def test_engine_receipt_invalid_schema_fails(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_root"
    engine_root.mkdir(parents=True, exist_ok=True)
    run_id = run_id_from_equivalence_key("engine-invalid-receipt")
    (engine_root / "run_receipt.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")

    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(engine_root)))

    request = _build_request("engine-invalid-receipt", engine_root)
    response = runner.submit_run(request)

    assert response.message == "Engine attempt failed."
    status = runner.ledger.read_status(run_id)
    assert status is not None
    assert status.state.value == "FAILED"
    assert status.reason_code == "ENGINE_RECEIPT_INVALID"


def test_engine_receipt_mismatch_fails(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_root"
    engine_root.mkdir(parents=True, exist_ok=True)
    run_id = run_id_from_equivalence_key("engine-receipt-mismatch")
    _write_run_receipt(engine_root, run_id, manifest="b" * 64, parameter_hash="c" * 64, seed=1)

    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(engine_root)))

    request = _build_request("engine-receipt-mismatch", engine_root)
    response = runner.submit_run(request)

    assert response.message == "Engine attempt failed."
    status = runner.ledger.read_status(run_id)
    assert status is not None
    assert status.state.value == "FAILED"
    assert status.reason_code == "ENGINE_RECEIPT_MISMATCH"


def test_attempt_limit_enforced(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_root"
    engine_root.mkdir(parents=True, exist_ok=True)
    wiring = _build_wiring(tmp_path)
    policy = _build_policy(attempt_limit=1)
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(engine_root)))

    run_id = run_id_from_equivalence_key("engine-attempt-limit")
    seeded_event = runner._event("ENGINE_ATTEMPT_FINISHED", run_id, {"attempt_no": 1})
    runner.ledger.append_record(run_id, seeded_event)

    request = _build_request("engine-attempt-limit", engine_root)
    response = runner.submit_run(request)

    assert response.message == "Engine attempt failed."
    status = runner.ledger.read_status(run_id)
    assert status is not None
    assert status.state.value == "FAILED"
    assert status.reason_code == "ATTEMPT_LIMIT_EXCEEDED"
