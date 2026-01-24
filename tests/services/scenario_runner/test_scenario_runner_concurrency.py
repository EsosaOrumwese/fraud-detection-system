from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.ids import run_id_from_equivalence_key
from fraud_detection.scenario_runner.models import RunRequest, RunWindow, ScenarioBinding
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


def _build_policy() -> PolicyProfile:
    return PolicyProfile(
        policy_id="sr_policy",
        revision="v0-test",
        content_digest="b" * 64,
        reuse_policy="ALLOW",
        evidence_wait_seconds=3600,
        attempt_limit=1,
        traffic_output_ids=["arrival_events_5B"],
    )


def test_concurrent_duplicate_submissions(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    engine_root = tmp_path / "engine_root"
    engine_root.mkdir(parents=True, exist_ok=True)

    request = RunRequest(
        run_equivalence_key="concurrency-1",
        manifest_fingerprint="a" * 64,
        parameter_hash="c" * 64,
        seed=1,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        output_ids=["arrival_events_5B"],
        engine_run_root=str(engine_root),
        invoker="test",
    )

    responses: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(5)

    def worker() -> None:
        runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(engine_root)))
        barrier.wait()
        resp = runner.submit_run(request)
        with lock:
            responses.append(resp.message or "")

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    leader_msgs = [msg for msg in responses if msg == "Evidence incomplete; waiting."]
    lease_msgs = [msg for msg in responses if msg.startswith("Lease held by another runner")]
    assert len(leader_msgs) == 1
    assert len(lease_msgs) == 4

    run_id = run_id_from_equivalence_key("concurrency-1")
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(engine_root)))
    status = runner.ledger.read_status(run_id)
    assert status is not None
    assert status.state.value == "WAITING_EVIDENCE"
