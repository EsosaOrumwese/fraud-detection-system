from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from fraud_detection.archive_writer.worker import ArchiveWriterWorker, load_worker_config
from fraud_detection.platform_runtime import RUNS_ROOT


def test_archive_writer_worker_archives_file_bus_event(tmp_path, monkeypatch) -> None:
    run_id = "platform_test_archive_writer_phase60"
    run_root = RUNS_ROOT / run_id
    if run_root.exists():
        shutil.rmtree(run_root)

    monkeypatch.setenv("ACTIVE_PLATFORM_RUN_ID", run_id)

    eb_root = tmp_path / "eb"
    topic = "fp.bus.traffic.fraud.v1"
    partition_path = eb_root / topic / "partition=0.jsonl"
    partition_path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "platform_run_id": run_id,
        "scenario_run_id": "scenario_a",
        "manifest_fingerprint": "f" * 8,
        "parameter_hash": "p" * 8,
        "scenario_id": "baseline_v1",
        "event_id": "evt_1",
        "event_type": "traffic_fraud",
        "ts_utc": "2026-02-10T00:00:00Z",
        "payload": {"amount": 10},
    }
    partition_path.write_text(json.dumps({"payload": envelope}) + "\n", encoding="utf-8")

    topics_ref = tmp_path / "topics.yaml"
    topics_ref.write_text("topics:\n  - fp.bus.traffic.fraud.v1\n", encoding="utf-8")

    profile_path = tmp_path / "profile.yaml"
    profile_payload = {
        "profile_id": "local_test",
        "policy": {"policy_rev": "local-test-v0"},
        "wiring": {
            "object_store": {
                "root": str(tmp_path / "store"),
                "path_style": True,
            },
            "event_bus_kind": "file",
            "event_bus": {},
        },
        "archive_writer": {
            "policy": {"policy_ref": "config/platform/archive_writer/policy_v0.yaml"},
            "wiring": {
                "stream_id": "archive_writer.v0",
                "ledger_dsn": str(tmp_path / "archive_writer.sqlite"),
                "event_bus_kind": "file",
                "event_bus_root": str(eb_root),
                "event_bus_start_position": "trim_horizon",
                "topics_ref": str(topics_ref),
                "poll_max_records": 20,
                "poll_sleep_seconds": 0.1,
            },
        },
    }
    profile_path.write_text(yaml.safe_dump(profile_payload, sort_keys=False), encoding="utf-8")

    config = load_worker_config(profile_path)
    worker = ArchiveWriterWorker(config)
    processed = worker.run_once()
    assert processed == 1

    archive_dir = tmp_path / "store" / "fraud-platform" / run_id / "archive" / "events"
    archived_files = list(archive_dir.rglob("*.json"))
    assert archived_files

    metrics_path = RUNS_ROOT / run_id / "archive_writer" / "metrics" / "last_metrics.json"
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert int(metrics["metrics"]["archived_total"]) == 1

    reconciliation_path = RUNS_ROOT / run_id / "archive" / "reconciliation" / "archive_writer_reconciliation.json"
    assert reconciliation_path.exists()

    if run_root.exists():
        shutil.rmtree(run_root)
