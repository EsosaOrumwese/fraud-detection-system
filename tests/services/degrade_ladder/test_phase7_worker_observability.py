from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.degrade_ladder.worker import DegradeLadderWorker, DlWorkerConfig


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")


def _build_worker(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_id: str,
    include_component_health: bool,
) -> DegradeLadderWorker:
    runs_root = tmp_path / "runs" / "fraud-platform"
    monkeypatch.setattr("fraud_detection.degrade_ladder.worker.RUNS_ROOT", runs_root)

    run_root = runs_root / run_id
    if include_component_health:
        _write_json(
            run_root / "online_feature_plane" / "health" / "last_health.json",
            {"health_state": "GREEN"},
        )
        _write_json(
            run_root / "identity_entity_graph" / "health" / "last_health.json",
            {"health_state": "GREEN"},
        )

    _write_json(
        runs_root / "operate" / "local_parity_rtdl_core_v0" / "status" / "last_status.json",
        {"processes": [{"process_id": "ofp_projector", "readiness": {"ready": True}}]},
    )
    registry_snapshot = tmp_path / "registry_snapshot.yaml"
    registry_snapshot.write_text("snapshot_id: snap-1\n", encoding="utf-8")

    config = DlWorkerConfig(
        profile_path=Path("config/platform/profiles/local_parity.yaml"),
        policy_ref=Path("config/platform/dl/policy_profiles_v0.yaml"),
        policy_profile_id="local_parity",
        stream_id=f"dl.test::{run_id}",
        scope_key="scope=GLOBAL",
        store_dsn=str(tmp_path / "posture.sqlite"),
        outbox_dsn=str(tmp_path / "outbox.sqlite"),
        ops_dsn=str(tmp_path / "ops.sqlite"),
        poll_seconds=0.01,
        max_age_seconds=120,
        outbox_max_events=10,
        outbox_max_attempts=3,
        outbox_backoff_seconds=1,
        platform_run_id=run_id,
        registry_snapshot_ref=registry_snapshot,
    )
    return DegradeLadderWorker(config=config)


def test_worker_emits_run_scoped_metrics_and_health_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = "platform_20260209T220000Z"
    worker = _build_worker(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        run_id=run_id,
        include_component_health=True,
    )

    payload = worker.run_once()
    assert payload["run_observability"]["health_state"] == "GREEN"

    metrics_path = tmp_path / "runs" / "fraud-platform" / run_id / "degrade_ladder" / "metrics" / "last_metrics.json"
    health_path = tmp_path / "runs" / "fraud-platform" / run_id / "degrade_ladder" / "health" / "last_health.json"
    assert metrics_path.exists()
    assert health_path.exists()

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    health = json.loads(health_path.read_text(encoding="utf-8"))
    assert metrics["platform_run_id"] == run_id
    assert metrics["scope_key"] == "scope=GLOBAL"
    assert metrics["decision_mode"] == "NORMAL"
    assert isinstance(metrics["metrics"], dict)
    assert health["health_state"] == "GREEN"
    assert health["bad_required_signals"] == []


def test_worker_marks_health_red_when_required_signals_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = "platform_20260209T220100Z"
    worker = _build_worker(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        run_id=run_id,
        include_component_health=False,
    )

    payload = worker.run_once()
    assert payload["mode"] == "FAIL_CLOSED"
    assert payload["run_observability"]["health_state"] == "RED"

    health_path = tmp_path / "runs" / "fraud-platform" / run_id / "degrade_ladder" / "health" / "last_health.json"
    health = json.loads(health_path.read_text(encoding="utf-8"))
    assert health["health_state"] == "RED"
    assert "REQUIRED_SIGNAL_NOT_OK" in health["reason_codes"]
    assert "ofp_health" in health["bad_required_signals"]
    assert "ieg_health" in health["bad_required_signals"]
