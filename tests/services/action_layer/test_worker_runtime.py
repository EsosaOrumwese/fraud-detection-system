from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import fraud_detection.action_layer.observability as observability_mod
import fraud_detection.action_layer.worker as worker_mod
from fraud_detection.action_layer.worker import ActionLayerWorker, AlWorkerConfig


def test_worker_bootstraps_zero_state_observability(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        worker_mod,
        "load_policy_bundle",
        lambda _ref: SimpleNamespace(retry_policy=None, execution_posture=SimpleNamespace(mode="NORMAL")),
    )
    monkeypatch.setattr(worker_mod, "ActionLedgerStore", lambda locator: SimpleNamespace(locator=locator))
    monkeypatch.setattr(worker_mod, "ActionOutcomeStore", lambda locator: SimpleNamespace(locator=locator))
    monkeypatch.setattr(worker_mod, "ActionOutcomeReplayLedger", lambda locator: SimpleNamespace(locator=locator))
    monkeypatch.setattr(worker_mod, "ActionCheckpointGate", lambda locator: SimpleNamespace(locator=locator))
    monkeypatch.setattr(worker_mod, "ActionIdempotencyGate", lambda store: SimpleNamespace(store=store))
    monkeypatch.setattr(worker_mod, "ActionLayerIgPublisher", lambda **kwargs: SimpleNamespace(**kwargs))

    config = AlWorkerConfig(
        profile_path=tmp_path / "dev_full.yaml",
        policy_ref=tmp_path / "al_policy.yaml",
        event_bus_kind="file",
        event_bus_root=str(tmp_path / "eb"),
        event_bus_stream=None,
        event_bus_region=None,
        event_bus_endpoint_url=None,
        event_bus_start_position="latest",
        admitted_topics=("fp.bus.rtdl.v1",),
        poll_max_records=10,
        poll_sleep_seconds=0.1,
        stream_id="al.v0::platform_20260307T150000Z",
        platform_run_id="platform_20260307T150000Z",
        scenario_run_id="a" * 32,
        required_platform_run_id="platform_20260307T150000Z",
        ig_ingest_url="https://example.invalid/ingest",
        ig_api_key=None,
        ig_api_key_header="X-IG-Api-Key",
        ledger_dsn=str(tmp_path / "al_ledger.sqlite"),
        outcomes_dsn=str(tmp_path / "al_outcomes.sqlite"),
        replay_dsn=str(tmp_path / "al_replay.sqlite"),
        checkpoint_dsn=str(tmp_path / "al_checkpoints.sqlite"),
        consumer_checkpoint_path=tmp_path / "al_consumer_checkpoints.sqlite",
    )

    worker = ActionLayerWorker(config)

    assert worker._metrics is not None
    assert worker._scenario_run_id == "a" * 32

    metrics_path = tmp_path / "runs" / "platform_20260307T150000Z" / "action_layer" / "observability" / "last_metrics.json"
    health_path = tmp_path / "runs" / "platform_20260307T150000Z" / "action_layer" / "health" / "last_health.json"

    monkeypatch.setattr(worker_mod, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(observability_mod, "RUNS_ROOT", tmp_path / "runs")
    worker._export()

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    health = json.loads(health_path.read_text(encoding="utf-8"))
    assert metrics["platform_run_id"] == "platform_20260307T150000Z"
    assert metrics["scenario_run_id"] == "a" * 32
    assert metrics["metrics"]["intake_total"] == 0
    assert health["health_state"] == "GREEN"
