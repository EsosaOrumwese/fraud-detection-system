from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.evidence import EvidenceBundle, EvidenceStatus
from fraud_detection.scenario_runner.ids import run_id_from_equivalence_key
from fraud_detection.scenario_runner.authority import RunHandle
from fraud_detection.scenario_runner.models import ReemitKind, ReemitRequest, RunPlan, RunRequest, RunWindow, ScenarioBinding, Strategy
from fraud_detection.scenario_runner.runner import ScenarioRunner
from fraud_detection.scenario_runner.security import redact_dsn


def _build_wiring(tmp_path: Path, auth_mode: str = "disabled") -> WiringProfile:
    return WiringProfile(
        object_store_root=str(tmp_path / "artefacts"),
        control_bus_topic="fp.bus.control.v1",
        control_bus_root=str(tmp_path / "control_bus"),
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        gate_map_path="docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
        schema_root="docs/model_spec/platform/contracts/scenario_runner",
        engine_contracts_root="docs/model_spec/data-engine/interface_pack/contracts",
        authority_store_dsn=f"sqlite:///{(tmp_path / 'sr_authority.db').as_posix()}",
        auth_mode=auth_mode,
        auth_allowlist=["allowed-user"],
        reemit_allowlist=["ops-user"],
        reemit_rate_limit_max=1,
        reemit_rate_limit_window_seconds=3600,
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


def _ready_run(runner: ScenarioRunner, run_id: str, policy: PolicyProfile) -> RunHandle:
    handle = RunHandle(run_id=run_id, intent_fingerprint="x", leader=True, lease_token="token")
    runner.lease_manager.check = lambda *_: True
    runner.lease_manager.renew = lambda *_: True
    runner._anchor_run(handle)
    plan = RunPlan(
        run_id=run_id,
        plan_hash="a" * 64,
        policy_rev=policy.as_rev(),
        strategy=Strategy.FORCE_REUSE,
        intended_outputs=[],
        required_gates=[],
        evidence_deadline_utc=datetime.now(tz=timezone.utc),
        attempt_limit=1,
        created_at_utc=datetime.now(tz=timezone.utc),
    )
    runner._commit_plan(handle, plan)
    bundle = EvidenceBundle(status=EvidenceStatus.COMPLETE, locators=[], gate_receipts=[], bundle_hash="b" * 64)
    runner._commit_ready(handle, runner._canonicalize(
        RunRequest(
            run_equivalence_key="tmp",
            manifest_fingerprint="a" * 64,
            parameter_hash="b" * 64,
            seed=1,
            scenario=ScenarioBinding(scenario_id="s1"),
            window=RunWindow(
                window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
                window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        )
    ), plan, bundle)
    return handle


def test_auth_denied_on_submit(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path, auth_mode="allowlist")
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    request = RunRequest(
        run_equivalence_key="auth-denied",
        manifest_fingerprint="a" * 64,
        parameter_hash="b" * 64,
        seed=1,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        invoker="unknown",
    )
    response = runner.submit_run(request)
    assert response.message == "Unauthorized."


def test_auth_allow_submit(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path, auth_mode="allowlist")
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    request = RunRequest(
        run_equivalence_key="auth-allowed",
        manifest_fingerprint="a" * 64,
        parameter_hash="b" * 64,
        seed=1,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        invoker="allowed-user",
    )
    response = runner.submit_run(request)
    assert response.run_id


def test_reemit_auth_denied(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path, auth_mode="allowlist")
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    response = runner.reemit(ReemitRequest(run_id=run_id_from_equivalence_key("auth-reemit"), requested_by="bad"))
    assert response.message == "Unauthorized."


def test_reemit_rate_limit(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path, auth_mode="disabled")
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    run_id = run_id_from_equivalence_key("rate-limit")
    _ready_run(runner, run_id, policy)
    runner.ledger.append_record(run_id, runner._event("REEMIT_PUBLISHED", run_id, {"kind": "READY"}))

    response = runner.reemit(ReemitRequest(run_id=run_id, reemit_kind=ReemitKind.READY_ONLY))
    assert response.message == "Reemit rate limit exceeded."


def test_reemit_dry_run(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path, auth_mode="disabled")
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    run_id = run_id_from_equivalence_key("dry-run")
    _ready_run(runner, run_id, policy)
    response = runner.reemit(ReemitRequest(run_id=run_id, dry_run=True))
    assert response.message == "Dry-run complete; no publish performed."


def test_quarantine_artifact_written(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path, auth_mode="disabled")
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    run_id = run_id_from_equivalence_key("quarantine")
    run_handle = RunHandle(run_id=run_id, intent_fingerprint="x", leader=True, lease_token="token")
    runner.lease_manager.check = lambda *_: True
    runner.lease_manager.renew = lambda *_: True
    runner._anchor_run(run_handle)
    bundle = EvidenceBundle(status=EvidenceStatus.CONFLICT, locators=[], gate_receipts=[], reason="EVIDENCE_CONFLICT")
    runner._commit_terminal(run_handle, bundle)

    quarantine_path = Path(wiring.object_store_root) / f"fraud-platform/sr/quarantine/{run_id}.json"
    assert quarantine_path.exists()


def test_redact_dsn() -> None:
    dsn = "postgresql://user:password@localhost:5432/db"
    assert redact_dsn(dsn) == "postgresql://user:***@localhost:5432/db"
