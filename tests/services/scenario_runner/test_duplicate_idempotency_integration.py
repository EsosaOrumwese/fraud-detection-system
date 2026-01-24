from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import EngineAttemptResult, EngineInvoker
from fraud_detection.scenario_runner.models import RunRequest, RunWindow, ScenarioBinding, Strategy
from fraud_detection.scenario_runner.runner import ScenarioRunner


pytestmark = pytest.mark.integration


class StubEngineInvoker(EngineInvoker):
    def __init__(self, engine_root: Path) -> None:
        self.engine_root = engine_root

    def invoke(self, run_id: str, attempt_no: int, invocation: dict[str, object]) -> EngineAttemptResult:
        self.engine_root.mkdir(parents=True, exist_ok=True)
        manifest = str(invocation["manifest_fingerprint"])
        parameter_hash = str(invocation["parameter_hash"])
        seed = int(invocation["seed"])

        _write_run_receipt(self.engine_root, run_id, manifest, parameter_hash, seed)
        _write_gate_bundle(self.engine_root, manifest)
        _write_output(self.engine_root, manifest)

        return EngineAttemptResult(
            run_id=run_id,
            attempt_id=f"attempt-{attempt_no}",
            attempt_no=attempt_no,
            outcome="SUCCEEDED",
            reason_code=None,
            engine_run_root=str(self.engine_root),
            invocation=invocation,
        )


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
        evidence_wait_seconds=60,
        attempt_limit=1,
        traffic_output_ids=["sealed_inputs_1A"],
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


def _write_gate_bundle(engine_root: Path, manifest: str) -> None:
    bundle_root = engine_root / f"data/layer1/1A/validation/manifest_fingerprint={manifest}"
    bundle_root.mkdir(parents=True, exist_ok=True)
    index_path = bundle_root / "index.json"
    index_path.write_text("{\"items\": [{\"path\": \"index.json\"}]}", encoding="utf-8")
    digest = hashlib.sha256(index_path.read_bytes()).hexdigest()
    flag_path = bundle_root / "_passed.flag"
    flag_path.write_text(f"sha256_hex = {digest}", encoding="utf-8")


def _write_output(engine_root: Path, manifest: str) -> None:
    output_path = engine_root / f"data/layer1/1A/sealed_inputs/manifest_fingerprint={manifest}/sealed_inputs_1A.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("{\"ok\": true}", encoding="utf-8")


def test_duplicate_submit_does_not_duplicate_ready(tmp_path: Path) -> None:
    manifest = "a" * 64
    parameter_hash = "b" * 64
    engine_root = tmp_path / "engine_root"

    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, StubEngineInvoker(engine_root))

    request = RunRequest(
        run_equivalence_key="dup-ready-1",
        manifest_fingerprint=manifest,
        parameter_hash=parameter_hash,
        seed=7,
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

    response = runner.submit_run(request)
    assert response.message == "READY committed"
    status = runner.ledger.read_status(response.run_id)
    assert status is not None
    assert status.state.value == "READY"

    topic_dir = Path(wiring.control_bus_root) / wiring.control_bus_topic
    first_files = list(topic_dir.glob("*.json"))
    assert len(first_files) == 1

    response_again = runner.submit_run(request)
    assert response_again.message.startswith("Lease held by another runner")

    second_files = list(topic_dir.glob("*.json"))
    assert len(second_files) == len(first_files)

    events = runner.ledger.read_record_events(response.run_id)
    ready_commits = [event for event in events if event.get("event_kind") == "READY_COMMITTED"]
    assert len(ready_commits) == 1
