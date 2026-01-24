from __future__ import annotations

import hashlib
import pytest
from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
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


def _build_policy(output_ids: list[str] | None = None) -> PolicyProfile:
    return PolicyProfile(
        policy_id="sr_policy",
        revision="v0-test",
        content_digest="b" * 64,
        reuse_policy="ALLOW",
        evidence_wait_seconds=60,
        attempt_limit=1,
        traffic_output_ids=output_ids or ["sealed_inputs_1A"],
    )


def _write_gate_bundle(engine_root: Path, manifest_fingerprint: str) -> None:
    bundle_root = engine_root / f"data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}"
    bundle_root.mkdir(parents=True, exist_ok=True)
    index_path = bundle_root / "index.json"
    index_path.write_text("{\"items\": [{\"path\": \"index.json\"}]}", encoding="utf-8")
    digest = hashlib.sha256(index_path.read_bytes()).hexdigest()
    flag_path = bundle_root / "_passed.flag"
    flag_path.write_text(f"sha256_hex = {digest}", encoding="utf-8")


def _write_output(engine_root: Path, manifest_fingerprint: str) -> None:
    output_path = engine_root / f"data/layer1/1A/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/sealed_inputs_1A.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("{\"ok\": true}", encoding="utf-8")


def test_gate_verification_with_real_map(tmp_path: Path) -> None:
    manifest_fingerprint = "a" * 64
    engine_root = tmp_path / "engine_root"
    _write_gate_bundle(engine_root, manifest_fingerprint)
    _write_output(engine_root, manifest_fingerprint)

    wiring = _build_wiring(tmp_path)
    policy = _build_policy(["sealed_inputs_1A"])
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(engine_root)))

    request = RunRequest(
        run_equivalence_key="gate-verification-1A",
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash="c" * 64,
        seed=1,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        output_ids=["sealed_inputs_1A"],
        engine_run_root=str(engine_root),
        requested_strategy=Strategy.FORCE_REUSE,
        invoker="test",
    )

    response = runner.submit_run(request)
    assert response.message == "READY committed"
    facts_view = runner.ledger.read_facts_view(response.run_id)
    assert facts_view is not None
    assert len(facts_view["gate_receipts"]) >= 1


RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92")


@pytest.mark.skipif(not RUN_ROOT.exists(), reason="local_full_run-5 not available")
def test_sr_reuse_with_real_engine_run(tmp_path: Path) -> None:
    run_root = RUN_ROOT
    manifest = "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"
    wiring = _build_wiring(tmp_path)
    policy = _build_policy(["s5_validation_report_6A"])
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(run_root)))

    request = RunRequest(
        run_equivalence_key="sr-reuse-real-run-6a",
        manifest_fingerprint=manifest,
        parameter_hash="56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7",
        seed=42,
        scenario=ScenarioBinding(scenario_id="baseline_v1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        output_ids=["s5_validation_report_6A"],
        engine_run_root=str(run_root),
        requested_strategy=Strategy.FORCE_REUSE,
        invoker="test",
    )

    response = runner.submit_run(request)
    assert response.message == "READY committed"
    facts_view = runner.ledger.read_facts_view(response.run_id)
    assert facts_view is not None
    assert len(facts_view["gate_receipts"]) >= 1
    assert len(facts_view["locators"]) >= 1
