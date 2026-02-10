from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.ids import run_id_from_equivalence_key
from fraud_detection.scenario_runner.models import RunRequest, RunWindow, ScenarioBinding, Strategy
from fraud_detection.scenario_runner.runner import ScenarioRunner

RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92")
MANIFEST = "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"
PARAM_HASH = "56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7"


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
        evidence_wait_seconds=0,
        attempt_limit=1,
        traffic_output_ids=["sealed_inputs_6B"],
    )


@pytest.mark.engine_fixture
@pytest.mark.skipif(not RUN_ROOT.exists(), reason="local_full_run-5 not available")
def test_missing_gate_flag_fails(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_root"
    validation_src = RUN_ROOT / f"data/layer3/6B/validation/manifest_fingerprint={MANIFEST}"
    validation_dst = engine_root / validation_src.relative_to(RUN_ROOT)
    shutil.copytree(validation_src, validation_dst, dirs_exist_ok=True)
    passed_flag = validation_dst / "_passed.flag"
    if passed_flag.exists():
        passed_flag.unlink()

    sealed_src = RUN_ROOT / f"data/layer3/6B/sealed_inputs/manifest_fingerprint={MANIFEST}/sealed_inputs_6B.json"
    sealed_dst = engine_root / sealed_src.relative_to(RUN_ROOT)
    sealed_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sealed_src, sealed_dst)

    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(engine_root)))

    request = RunRequest(
        run_equivalence_key="missing-gate-flag-6b",
        manifest_fingerprint=MANIFEST,
        parameter_hash=PARAM_HASH,
        seed=1,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        output_ids=["sealed_inputs_6B"],
        engine_run_root=str(engine_root),
        requested_strategy=Strategy.FORCE_REUSE,
        invoker="test",
    )

    response = runner.submit_run(request)
    assert response.message == "Reuse evidence failed."
    run_id = run_id_from_equivalence_key("missing-gate-flag-6b")
    status = runner.ledger.read_status(run_id)
    assert status is not None
    assert status.state.value == "FAILED"
    assert status.reason_code == "EVIDENCE_MISSING_DEADLINE"
