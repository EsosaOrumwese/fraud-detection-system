from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalSubprocessInvoker
from fraud_detection.scenario_runner.ids import run_id_from_equivalence_key
from fraud_detection.scenario_runner.models import RunRequest, RunWindow, ScenarioBinding
from fraud_detection.scenario_runner.authority import RunHandle
from fraud_detection.scenario_runner.runner import ScenarioRunner


def _write_stub_engine(script_path: Path) -> None:
    script_path.write_text(
        "\n".join(
            [
                "import json, os, sys",
                "from pathlib import Path",
                "payload = json.loads(os.environ.get('SR_ENGINE_INVOCATION_JSON', '{}'))",
                "run_root = payload.get('engine_run_root')",
                "if not run_root:",
                "    print('missing engine_run_root', file=sys.stderr)",
                "    sys.exit(2)",
                "Path(run_root).mkdir(parents=True, exist_ok=True)",
                "receipt = {",
                "    'run_id': payload.get('run_id'),",
                "    'manifest_fingerprint': payload.get('manifest_fingerprint'),",
                "    'parameter_hash': payload.get('parameter_hash'),",
                "    'seed': payload.get('seed'),",
                "    'created_utc': '2026-01-24T00:00:00Z',",
                "}",
                "Path(run_root, 'run_receipt.json').write_text(json.dumps(receipt))",
                "print('engine ok')",
                "print('engine warn', file=sys.stderr)",
                "sys.exit(0)",
            ]
        ),
        encoding="utf-8",
    )


def test_subprocess_invoker_captures_output(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_root"
    script_path = tmp_path / "engine_stub.py"
    _write_stub_engine(script_path)

    invoker = LocalSubprocessInvoker([sys.executable, str(script_path)])
    run_id = run_id_from_equivalence_key("subprocess-direct")
    invocation = {
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "b" * 64,
        "seed": 1,
        "run_id": run_id,
        "scenario_binding": {"scenario_id": "s1"},
        "engine_run_root": str(engine_root),
    }
    result = invoker.invoke(run_id, 1, invocation)
    assert result.outcome == "SUCCEEDED"
    assert result.stdout and "engine ok" in result.stdout
    assert result.stderr and "engine warn" in result.stderr


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


def _build_policy() -> PolicyProfile:
    return PolicyProfile(
        policy_id="sr_policy",
        revision="v0-test",
        content_digest="b" * 64,
        reuse_policy="DENY",
        evidence_wait_seconds=60,
        attempt_limit=1,
        traffic_output_ids=["sealed_inputs_1A"],
    )


def test_runner_persists_attempt_logs(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_root"
    script_path = tmp_path / "engine_stub.py"
    _write_stub_engine(script_path)

    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    invoker = LocalSubprocessInvoker([sys.executable, str(script_path)])
    runner = ScenarioRunner(wiring, policy, invoker)

    run_key = "subprocess-runner"
    request = RunRequest(
        run_equivalence_key=run_key,
        manifest_fingerprint="a" * 64,
        parameter_hash="b" * 64,
        seed=1,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
            window_tz="UTC",
        ),
        engine_run_root=str(engine_root),
    )

    intent = runner._canonicalize(request)
    intent_fingerprint = runner._intent_fingerprint(intent)
    run_id, _ = runner.equiv_registry.resolve(run_key, intent_fingerprint)
    leader, lease_token = runner.lease_manager.acquire(run_id, owner_id="test")
    assert leader and lease_token
    run_handle = RunHandle(run_id=run_id, intent_fingerprint=intent_fingerprint, leader=True, lease_token=lease_token)
    runner._anchor_run(run_handle)
    plan = runner._compile_plan(intent, run_id)
    runner._commit_plan(run_handle, plan)

    runner._invoke_engine(run_handle, intent, plan)
    events = runner.ledger.read_record_events(run_id)
    finished = [event for event in events if event.get("event_kind") == "ENGINE_ATTEMPT_FINISHED"]
    assert finished
    logs_ref = finished[-1]["details"].get("logs_ref")
    assert logs_ref
    stdout_ref = logs_ref.get("stdout_ref")
    stderr_ref = logs_ref.get("stderr_ref")
    assert stdout_ref and runner.store.exists(stdout_ref)
    assert stderr_ref and runner.store.exists(stderr_ref)
