from __future__ import annotations

import json
from pathlib import Path

import fraud_detection.label_store.observability as observability_mod
from fraud_detection.label_store import LabelStoreWriterBoundary
from fraud_detection.label_store.worker import LabelStoreWorker, LabelStoreWorkerConfig, load_worker_config


def test_worker_bootstraps_startup_export_with_explicit_run_scope(monkeypatch, tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    monkeypatch.setattr(observability_mod, "RUNS_ROOT", runs_root)

    locator = str(tmp_path / "label_store.sqlite")
    LabelStoreWriterBoundary(locator)

    config = LabelStoreWorkerConfig(
        profile_path=tmp_path / "dev_full.yaml",
        locator=locator,
        stream_id="label_store.v0::platform_20260308T140000Z",
        platform_run_id="platform_20260308T140000Z",
        required_platform_run_id="platform_20260308T140000Z",
        scenario_run_id="a" * 32,
        poll_seconds=0.1,
    )

    LabelStoreWorker(config)

    metrics_path = runs_root / "platform_20260308T140000Z" / "label_store" / "metrics" / "last_metrics.json"
    health_path = runs_root / "platform_20260308T140000Z" / "label_store" / "health" / "last_health.json"
    reconciliation_path = runs_root / "platform_20260308T140000Z" / "label_store" / "reconciliation" / "last_reconciliation.json"

    assert metrics_path.exists()
    assert health_path.exists()
    assert reconciliation_path.exists()

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    health = json.loads(health_path.read_text(encoding="utf-8"))
    assert metrics["platform_run_id"] == "platform_20260308T140000Z"
    assert metrics["scenario_run_id"] == "a" * 32
    assert metrics["metrics"]["accepted"] == 0
    assert health["health_state"] == "GREEN"


def test_label_store_load_worker_config_resolves_nested_run_scope_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ACTIVE_PLATFORM_RUN_ID", "platform_20260308T141818Z")
    profile = tmp_path / "dev_full.yaml"
    profile.write_text(
        "\n".join(
            [
                "profile_id: dev_full",
                "label_store:",
                "  wiring:",
                "    locator: " + str(tmp_path / "label_store.sqlite"),
                "    required_platform_run_id: ${LABEL_STORE_REQUIRED_PLATFORM_RUN_ID:-${ACTIVE_PLATFORM_RUN_ID:-}}",
                "    scenario_run_id: ${ACTIVE_SCENARIO_RUN_ID:-" + "a" * 32 + "}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_worker_config(profile)

    assert config.required_platform_run_id == "platform_20260308T141818Z"
