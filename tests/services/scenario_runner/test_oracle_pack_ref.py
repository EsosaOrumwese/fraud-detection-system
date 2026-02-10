from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.models import CanonicalRunIntent
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
        evidence_wait_seconds=60,
        attempt_limit=1,
        traffic_output_ids=["sealed_inputs_1A"],
    )


def _intent() -> CanonicalRunIntent:
    return CanonicalRunIntent(
        request_id=None,
        run_equivalence_key="oracle-pack",
        manifest_fingerprint="a" * 64,
        parameter_hash="b" * 64,
        seed=7,
        scenario_id="baseline_v1",
        scenario_set=None,
        window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        window_tz="UTC",
        requested_strategy=None,
        output_ids=None,
        engine_run_root=None,
        notes=None,
        invoker="test",
    )


def _write_manifest(engine_root: Path, *, scenario_id: str, seed: int, parameter_hash: str) -> None:
    payload = {
        "version": "v0",
        "oracle_pack_id": "c" * 64,
        "world_key": {
            "manifest_fingerprint": "a" * 64,
            "parameter_hash": parameter_hash,
            "scenario_id": scenario_id,
            "seed": seed,
        },
        "engine_release": "engine-0.1.0",
        "catalogue_digest": "d" * 64,
        "gate_map_digest": "e" * 64,
        "created_at_utc": "2026-01-01T00:00:00Z",
    }
    (engine_root / "_oracle_pack_manifest.json").write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )


def test_oracle_pack_ref_valid(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())
    engine_root = tmp_path / "engine_root"
    engine_root.mkdir()
    intent = _intent()
    _write_manifest(engine_root, scenario_id=intent.scenario_id, seed=intent.seed, parameter_hash=intent.parameter_hash)

    ref, error = runner._build_oracle_pack_ref(str(engine_root), intent)

    assert error is None
    assert ref is not None
    assert ref["engine_run_root"] == str(engine_root)
    assert ref["oracle_pack_id"] == "c" * 64
    assert ref["engine_release"] == "engine-0.1.0"
    assert ref["manifest_ref"].endswith("_oracle_pack_manifest.json")


def test_oracle_pack_ref_missing_manifest(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())
    engine_root = tmp_path / "engine_root"
    engine_root.mkdir()
    intent = _intent()

    ref, error = runner._build_oracle_pack_ref(str(engine_root), intent)

    assert error is None
    assert ref is not None
    assert ref["engine_run_root"] == str(engine_root)
    assert "oracle_pack_id" not in ref


def test_oracle_pack_ref_mismatch(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())
    engine_root = tmp_path / "engine_root"
    engine_root.mkdir()
    intent = _intent()
    _write_manifest(engine_root, scenario_id="other", seed=intent.seed, parameter_hash=intent.parameter_hash)

    ref, error = runner._build_oracle_pack_ref(str(engine_root), intent)

    assert ref is None
    assert error == "ORACLE_PACK_MISMATCH"
