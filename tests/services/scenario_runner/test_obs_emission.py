from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.authority import RunHandle
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.evidence import EvidenceBundle, EvidenceStatus
from fraud_detection.scenario_runner.ids import hash_payload, run_id_from_equivalence_key
from fraud_detection.scenario_runner.models import RunPlan, RunRequest, RunWindow, ScenarioBinding, Strategy
from fraud_detection.scenario_runner.obs import ObsEvent, ObsOutcome, ObsPhase, ObsSeverity, ObsSink
from fraud_detection.scenario_runner.runner import ScenarioRunner


class FailingObsSink(ObsSink):
    def emit(self, event) -> None:
        raise RuntimeError("obs sink failure")


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


def test_obs_failure_does_not_block_ready(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(), obs_sink=FailingObsSink())

    run_key = "obs-ready"
    run_id = run_id_from_equivalence_key(run_key)
    engine_root = tmp_path / "engine_root"
    engine_root.mkdir(parents=True, exist_ok=True)

    request = RunRequest(
        run_equivalence_key=run_key,
        manifest_fingerprint="a" * 64,
        parameter_hash="b" * 64,
        seed=1,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        engine_run_root=str(engine_root),
    )
    intent = runner._canonicalize(request)
    intent_fingerprint = runner._intent_fingerprint(intent)
    _, _ = runner.equiv_registry.resolve(run_key, intent_fingerprint)
    leader, lease_token = runner.lease_manager.acquire(run_id, owner_id="test")
    assert leader and lease_token
    run_handle = RunHandle(run_id=run_id, intent_fingerprint=intent_fingerprint, leader=True, lease_token=lease_token)
    runner._anchor_run(run_handle)

    plan = RunPlan(
        run_id=run_id,
        plan_hash=hash_payload("plan"),
        policy_rev=policy.as_rev(),
        strategy=Strategy.FORCE_REUSE,
        intended_outputs=[],
        required_gates=[],
        evidence_deadline_utc=datetime.now(tz=timezone.utc),
        attempt_limit=1,
        created_at_utc=datetime.now(tz=timezone.utc),
    )
    runner._commit_plan(run_handle, plan)

    bundle = EvidenceBundle(
        status=EvidenceStatus.COMPLETE,
        locators=[],
        gate_receipts=[],
        bundle_hash="c" * 64,
    )
    response = runner._commit_ready(run_handle, intent, plan, bundle)
    assert response.state.value == "READY"


def test_metrics_sink_records_duration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SR_OBS_CONSOLE", "false")
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    runner._emit_obs(
        ObsEvent.now(
            event_kind="TEST_EVENT",
            phase=ObsPhase.PLAN,
            outcome=ObsOutcome.OK,
            severity=ObsSeverity.INFO,
            pins={"run_id": "test"},
            details={"duration_ms": 123},
        )
    )
    snapshot = runner.metrics_sink.snapshot()
    assert snapshot["counters"]["TEST_EVENT"] == 1
    assert snapshot["durations"]["TEST_EVENT"]["count"] == 1
