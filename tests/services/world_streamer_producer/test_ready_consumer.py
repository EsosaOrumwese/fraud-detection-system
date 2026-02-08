from __future__ import annotations

import json
from pathlib import Path

from fraud_detection.world_streamer_producer.config import PolicyProfile, WiringProfile, WspProfile
from fraud_detection.world_streamer_producer import ready_consumer as ready_consumer_module
from fraud_detection.world_streamer_producer.ready_consumer import ReadyConsumerRunner
from fraud_detection.world_streamer_producer.runner import StreamResult

RUN_ID = "platform_20260101T000000Z"
RUN_PREFIX = f"fraud-platform/{RUN_ID}"


def _write_control_message(root: Path, *, topic: str, message_id: str, payload: dict) -> None:
    topic_dir = root / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "topic": topic,
        "message_id": message_id,
        "published_at_utc": "2026-01-01T00:00:00Z",
        "attributes": {"kind": "READY"},
        "partition_key": payload.get("run_id"),
        "payload": payload,
    }
    (topic_dir / f"{message_id}.json").write_text(json.dumps(envelope, ensure_ascii=True), encoding="utf-8")


def _write_run_facts(
    store_root: Path,
    run_id: str,
    engine_root: Path,
    scenario_id: str,
    *,
    platform_run_id: str = RUN_ID,
) -> str:
    facts_ref = f"{RUN_PREFIX}/sr/run_facts_view/{run_id}.json"
    payload = {
        "run_id": run_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": run_id,
        "pins": {
            "manifest_fingerprint": "a" * 64,
            "parameter_hash": "b" * 64,
            "seed": 7,
            "scenario_id": scenario_id,
            "run_id": run_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": run_id,
        },
        "locators": [
            {
                "output_id": "arrival_events_5B",
                "path": str(engine_root / "data" / "placeholder.parquet"),
            }
        ],
        "gate_receipts": [
            {
                "gate_id": "gate.test.validation",
                "status": "PASS",
                "scope": {"manifest_fingerprint": "a" * 64},
            }
        ],
        "policy_rev": {"policy_id": "sr_policy", "revision": "v0", "content_digest": "c" * 64},
        "bundle_hash": "d" * 64,
        "run_config_digest": "c" * 64,
        "plan_ref": "ref/plan",
        "record_ref": "ref/record",
        "status_ref": "ref/status",
        "oracle_pack_ref": {"engine_run_root": str(engine_root)},
    }
    path = store_root / facts_ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    return facts_ref


def _profile(store_root: Path, control_root: Path) -> WspProfile:
    store_root.mkdir(parents=True, exist_ok=True)
    policy = PolicyProfile(
        policy_rev="local",
        require_gate_pass=True,
        stream_speedup=0.0,
        traffic_output_ids=["arrival_events_5B"],
        context_output_ids=[],
    )
    wiring = WiringProfile(
        profile_id="local",
        object_store_root=str(store_root),
        object_store_endpoint=None,
        object_store_region=None,
        object_store_path_style=None,
        control_bus_kind="file",
        control_bus_root=str(control_root),
        control_bus_topic="fp.bus.control.v1",
        control_bus_stream=None,
        control_bus_region=None,
        control_bus_endpoint_url=None,
        schema_root="docs/model_spec/platform/contracts",
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        oracle_root=str(store_root),
        oracle_engine_run_root=str(store_root),
        oracle_scenario_id=None,
        stream_view_root=None,
        ig_ingest_url="http://localhost:8081",
        checkpoint_backend="file",
        checkpoint_root=str(store_root / "wsp" / "checkpoints"),
        checkpoint_dsn=None,
        checkpoint_every=1,
        producer_id="svc:world_stream_producer",
        producer_allowlist_ref=str(store_root / "allowlist.txt"),
        ig_retry_max_attempts=5,
        ig_retry_base_delay_ms=250,
        ig_retry_max_delay_ms=5000,
    )
    (store_root / "allowlist.txt").write_text("svc:world_stream_producer\n", encoding="utf-8")
    return WspProfile(policy=policy, wiring=wiring)


def test_ready_consumer_streams_from_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_RUN_ID", RUN_ID)
    store_root = tmp_path / "store"
    control_root = tmp_path / "control_bus"
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir(parents=True, exist_ok=True)
    profile = _profile(store_root, control_root)

    run_id = "a" * 32
    scenario_id = "baseline_v1"
    facts_ref = _write_run_facts(store_root, run_id, engine_root, scenario_id)
    message_id = "1" * 64
    ready_payload = {
        "run_id": run_id,
        "platform_run_id": RUN_ID,
        "scenario_run_id": run_id,
        "facts_view_ref": facts_ref,
        "bundle_hash": "d" * 64,
        "message_id": message_id,
        "run_config_digest": "c" * 64,
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "b" * 64,
        "scenario_id": scenario_id,
        "oracle_pack_ref": {"engine_run_root": str(engine_root)},
    }
    _write_control_message(control_root, topic="fp.bus.control.v1", message_id=message_id, payload=ready_payload)

    captured: dict[str, str] = {}

    def _fake_stream(*, engine_run_root: str | None = None, scenario_id: str | None = None, **_kwargs):
        captured["engine_run_root"] = engine_run_root or ""
        captured["scenario_id"] = scenario_id or ""
        return StreamResult(engine_run_root or "", scenario_id or "", "STREAMED", 3)

    runner = ReadyConsumerRunner(profile)
    monkeypatch.setattr(runner._producer, "stream_engine_world", _fake_stream)

    results = runner.poll_once()
    assert results
    assert results[0].status == "STREAMED"
    assert captured["engine_run_root"] == str(store_root)
    assert captured["scenario_id"] == scenario_id


def test_ready_consumer_skips_duplicate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_RUN_ID", RUN_ID)
    store_root = tmp_path / "store"
    control_root = tmp_path / "control_bus"
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir(parents=True, exist_ok=True)
    profile = _profile(store_root, control_root)

    run_id = "b" * 32
    scenario_id = "baseline_v1"
    facts_ref = _write_run_facts(store_root, run_id, engine_root, scenario_id)
    message_id = "2" * 64
    ready_payload = {
        "run_id": run_id,
        "platform_run_id": RUN_ID,
        "scenario_run_id": run_id,
        "facts_view_ref": facts_ref,
        "bundle_hash": "e" * 64,
        "message_id": message_id,
        "run_config_digest": "c" * 64,
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "b" * 64,
        "scenario_id": scenario_id,
        "oracle_pack_ref": {"engine_run_root": str(engine_root)},
    }
    _write_control_message(control_root, topic="fp.bus.control.v1", message_id=message_id, payload=ready_payload)

    record_path = store_root / RUN_PREFIX / "wsp" / "ready_runs" / f"{message_id}.jsonl"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps({"status": "STREAMED"}) + "\n", encoding="utf-8")

    called = {"value": False}

    def _fake_stream(*_args, **_kwargs):
        called["value"] = True
        return StreamResult("", "", "STREAMED", 1)

    runner = ReadyConsumerRunner(profile)
    monkeypatch.setattr(runner._producer, "stream_engine_world", _fake_stream)

    results = runner.poll_once()
    assert results
    assert results[0].status == "SKIPPED_DUPLICATE"
    assert called["value"] is False
    assert len(record_path.read_text(encoding="utf-8").splitlines()) == 1


def test_ready_consumer_duplicate_logging_is_throttled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_RUN_ID", RUN_ID)
    store_root = tmp_path / "store"
    control_root = tmp_path / "control_bus"
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir(parents=True, exist_ok=True)
    profile = _profile(store_root, control_root)

    run_id = "d" * 32
    scenario_id = "baseline_v1"
    facts_ref = _write_run_facts(store_root, run_id, engine_root, scenario_id)
    message_id = "4" * 64
    ready_payload = {
        "run_id": run_id,
        "platform_run_id": RUN_ID,
        "scenario_run_id": run_id,
        "facts_view_ref": facts_ref,
        "bundle_hash": "a" * 64,
        "message_id": message_id,
        "run_config_digest": "c" * 64,
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "b" * 64,
        "scenario_id": scenario_id,
        "oracle_pack_ref": {"engine_run_root": str(engine_root)},
    }
    _write_control_message(control_root, topic="fp.bus.control.v1", message_id=message_id, payload=ready_payload)

    record_path = store_root / RUN_PREFIX / "wsp" / "ready_runs" / f"{message_id}.jsonl"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps({"status": "STREAMED"}) + "\n", encoding="utf-8")

    runner = ReadyConsumerRunner(profile)
    runner._duplicate_log_interval_seconds = 3600.0

    calls: list[tuple[object, ...]] = []

    def _capture_info(*args, **_kwargs):
        calls.append(args)

    monkeypatch.setattr(ready_consumer_module.logger, "info", _capture_info)

    first = runner.poll_once()
    second = runner.poll_once()
    assert first[0].status == "SKIPPED_DUPLICATE"
    assert second[0].status == "SKIPPED_DUPLICATE"
    duplicate_messages = [args[0] for args in calls if args and isinstance(args[0], str) and "duplicate skipped" in args[0]]
    assert len(duplicate_messages) == 1


def test_ready_consumer_skips_out_of_scope_platform_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_RUN_ID", RUN_ID)
    store_root = tmp_path / "store"
    control_root = tmp_path / "control_bus"
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir(parents=True, exist_ok=True)
    profile = _profile(store_root, control_root)

    run_id = "c" * 32
    other_platform_run_id = "platform_20990101T000000Z"
    scenario_id = "baseline_v1"
    facts_ref = _write_run_facts(
        store_root,
        run_id,
        engine_root,
        scenario_id,
        platform_run_id=other_platform_run_id,
    )
    message_id = "3" * 64
    ready_payload = {
        "run_id": run_id,
        "platform_run_id": other_platform_run_id,
        "scenario_run_id": run_id,
        "facts_view_ref": facts_ref,
        "bundle_hash": "f" * 64,
        "message_id": message_id,
        "run_config_digest": "c" * 64,
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "b" * 64,
        "scenario_id": scenario_id,
        "oracle_pack_ref": {"engine_run_root": str(engine_root)},
    }
    _write_control_message(control_root, topic="fp.bus.control.v1", message_id=message_id, payload=ready_payload)

    called = {"value": False}

    def _fake_stream(*_args, **_kwargs):
        called["value"] = True
        return StreamResult("", "", "STREAMED", 1)

    runner = ReadyConsumerRunner(profile)
    monkeypatch.setattr(runner._producer, "stream_engine_world", _fake_stream)

    results = runner.poll_once()
    assert results
    assert results[0].status == "SKIPPED_OUT_OF_SCOPE"
    assert results[0].reason == "PLATFORM_RUN_SCOPE_MISMATCH"
    assert called["value"] is False
