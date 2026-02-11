from __future__ import annotations

from datetime import datetime, timezone
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
        reuse_policy="DENY",
        evidence_wait_seconds=60,
        attempt_limit=1,
        traffic_output_ids=["s2_event_stream_baseline_6B", "s3_event_stream_with_fraud_6B"],
    )


def _intent() -> CanonicalRunIntent:
    return CanonicalRunIntent(
        request_id=None,
        run_equivalence_key="oracle-s2",
        manifest_fingerprint="a" * 64,
        parameter_hash="b" * 64,
        seed=42,
        scenario_id="baseline_v1",
        scenario_set=None,
        window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        window_tz="UTC",
        requested_strategy=None,
        output_ids=["s2_event_stream_baseline_6B"],
        engine_run_root=None,
        notes=None,
        invoker=None,
    )


def test_oracle_scope_rejects_request_root_mismatch(tmp_path: Path) -> None:
    runner = ScenarioRunner(_build_wiring(tmp_path), _build_policy(), LocalEngineInvoker())
    runner.wiring.acceptance_mode = "dev_min_managed"
    runner.wiring.oracle_engine_run_root = "s3://oracle-store/dev_min/run-1"
    runner.wiring.oracle_scenario_id = "baseline_v1"
    runner.wiring.oracle_stream_view_root = "s3://oracle-store/dev_min/run-1/stream_view/ts_utc"

    reason = runner._validate_oracle_scope(
        request_root="s3://oracle-store/dev_min/run-2",
        resolved_engine_root="s3://oracle-store/dev_min/run-1",
        scenario_id="baseline_v1",
    )
    assert reason == "ORACLE_ENGINE_ROOT_REQUEST_MISMATCH"


def test_oracle_scope_rejects_scenario_mismatch(tmp_path: Path) -> None:
    runner = ScenarioRunner(_build_wiring(tmp_path), _build_policy(), LocalEngineInvoker())
    runner.wiring.acceptance_mode = "dev_min_managed"
    runner.wiring.oracle_engine_run_root = "s3://oracle-store/dev_min/run-1"
    runner.wiring.oracle_scenario_id = "baseline_v1"
    runner.wiring.oracle_stream_view_root = "s3://oracle-store/dev_min/run-1/stream_view/ts_utc"

    reason = runner._validate_oracle_scope(
        request_root="s3://oracle-store/dev_min/run-1",
        resolved_engine_root="s3://oracle-store/dev_min/run-1",
        scenario_id="fraud_v1",
    )
    assert reason == "ORACLE_SCENARIO_ID_MISMATCH"


def test_oracle_pack_ref_includes_stream_view_refs(tmp_path: Path) -> None:
    runner = ScenarioRunner(_build_wiring(tmp_path), _build_policy(), LocalEngineInvoker())
    runner.wiring.oracle_scenario_id = "baseline_v1"
    runner.wiring.oracle_stream_view_root = "s3://oracle-store/dev_min/run-1/stream_view/ts_utc"

    ref, error = runner._build_oracle_pack_ref(
        "runs/local_full_run-5/sample",
        _intent(),
        intended_outputs=["s3_event_stream_with_fraud_6B", "s2_event_stream_baseline_6B"],
    )
    assert error is None
    assert ref is not None
    assert ref["scenario_id"] == "baseline_v1"
    assert ref["stream_view_root"] == "s3://oracle-store/dev_min/run-1/stream_view/ts_utc"
    output_refs = ref.get("stream_view_output_refs") or {}
    assert output_refs["s2_event_stream_baseline_6B"].endswith("/output_id=s2_event_stream_baseline_6B")
    assert output_refs["s3_event_stream_with_fraud_6B"].endswith("/output_id=s3_event_stream_with_fraud_6B")


def test_oracle_pack_ref_fails_closed_when_stream_view_missing(tmp_path: Path) -> None:
    runner = ScenarioRunner(_build_wiring(tmp_path), _build_policy(), LocalEngineInvoker())
    runner.wiring.acceptance_mode = "dev_min_managed"
    runner.wiring.oracle_scenario_id = "baseline_v1"
    runner.wiring.oracle_stream_view_root = str(tmp_path / "missing_stream_view")

    ref, error = runner._build_oracle_pack_ref(
        str(tmp_path / "engine_run"),
        _intent(),
        intended_outputs=["s2_event_stream_baseline_6B"],
    )
    assert ref is None
    assert error == "ORACLE_STREAM_VIEW_OUTPUT_MISSING:s2_event_stream_baseline_6B"


def test_oracle_pack_ref_accepts_stream_view_when_artifacts_present(tmp_path: Path) -> None:
    runner = ScenarioRunner(_build_wiring(tmp_path), _build_policy(), LocalEngineInvoker())
    runner.wiring.acceptance_mode = "dev_min_managed"
    runner.wiring.oracle_scenario_id = "baseline_v1"
    stream_view_root = tmp_path / "stream_view"
    output_dir = stream_view_root / "output_id=s2_event_stream_baseline_6B"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "_stream_view_manifest.json").write_text("{}", encoding="utf-8")
    (output_dir / "_stream_sort_receipt.json").write_text("{}", encoding="utf-8")
    (output_dir / "part-000.parquet").write_bytes(b"parquet")
    runner.wiring.oracle_stream_view_root = str(stream_view_root)

    ref, error = runner._build_oracle_pack_ref(
        str(tmp_path / "engine_run"),
        _intent(),
        intended_outputs=["s2_event_stream_baseline_6B"],
    )
    assert error is None
    assert ref is not None
    assert ref["stream_view_output_refs"]["s2_event_stream_baseline_6B"].endswith(
        "/output_id=s2_event_stream_baseline_6B"
    )
