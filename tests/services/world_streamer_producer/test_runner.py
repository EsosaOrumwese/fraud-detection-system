from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from fraud_detection.world_streamer_producer.config import PolicyProfile, WiringProfile, WspProfile
from fraud_detection.world_streamer_producer.runner import (
    WorldStreamProducer,
    _replay_delay_seconds,
    _should_bypass_replay_delay_for_scheduled_rate_plan,
)


def _write_run_receipt(root: Path) -> dict:
    receipt = {
        "manifest_fingerprint": "c" * 64,
        "parameter_hash": "1" * 64,
        "seed": 42,
        "run_id": "abcd" * 8,
    }
    (root / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    return receipt


def _write_arrival_events(root: Path, receipt: dict, scenario_id: str, *, count: int = 1) -> list[dict]:
    path = (
        root
        / "data/layer2/5B/arrival_events"
        / f"seed={receipt['seed']}"
        / f"manifest_fingerprint={receipt['manifest_fingerprint']}"
        / f"scenario_id={scenario_id}"
    )
    path.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx in range(count):
        rows.append(
            {
                "ts_utc": f"2026-01-01T00:00:0{idx}Z",
                "seed": receipt["seed"],
                "manifest_fingerprint": receipt["manifest_fingerprint"],
                "scenario_id": scenario_id,
                "merchant_id": f"m-{idx+1}",
                "arrival_seq": idx + 1,
            }
        )
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path / "part-000.parquet")
    gate_flag = (
        root
        / "data/layer2/5B/validation"
        / f"manifest_fingerprint={receipt['manifest_fingerprint']}"
        / "_passed.flag"
    )
    gate_flag.parent.mkdir(parents=True, exist_ok=True)
    gate_flag.write_text("PASS", encoding="utf-8")
    return rows


def _write_stream_view(root: Path, *, output_id: str, rows: list[dict]) -> None:
    stream_root = root / "stream_view" / "ts_utc" / f"output_id={output_id}"
    stream_root.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, stream_root / "part-000.parquet")
    manifest = {"output_id": output_id}
    receipt = {"status": "OK"}
    (stream_root / "_stream_view_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    (stream_root / "_stream_sort_receipt.json").write_text(
        json.dumps(receipt, sort_keys=True), encoding="utf-8"
    )


def _profile(
    root: Path,
    *,
    output_ids: list[str],
    checkpoint_root: Path | None = None,
    producer_id: str = "svc:world_stream_producer",
    allowlist_ref: Path | None = None,
) -> WspProfile:
    allowlist_path = allowlist_ref or (root / "wsp_allowlist.txt")
    if allowlist_ref is None:
        allowlist_path.write_text(f"{producer_id}\n", encoding="utf-8")
    policy = PolicyProfile(
        policy_rev="local",
        require_gate_pass=True,
        stream_speedup=0.0,
        traffic_output_ids=output_ids,
        context_output_ids=[],
    )
    wiring = WiringProfile(
        profile_id="local",
        object_store_root=str(root),
        object_store_endpoint=None,
        object_store_region=None,
        object_store_path_style=None,
        control_bus_kind="file",
        control_bus_root="",
        control_bus_topic="",
        control_bus_stream=None,
        control_bus_region=None,
        control_bus_endpoint_url=None,
        schema_root="docs/model_spec/platform/contracts",
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        oracle_root=str(root),
        oracle_engine_run_root=str(root),
        oracle_scenario_id="baseline_v1",
        stream_view_root=None,
        ig_ingest_url="http://localhost:8081",
        ig_auth_header="X-IG-Api-Key",
        ig_auth_token=None,
        checkpoint_backend="file",
        checkpoint_root=str(checkpoint_root or (root / "wsp" / "checkpoints")),
        checkpoint_dsn=None,
        checkpoint_every=1,
        producer_id=producer_id,
        producer_allowlist_ref=str(allowlist_path),
        ig_retry_max_attempts=5,
        ig_retry_base_delay_ms=250,
        ig_retry_max_delay_ms=5000,
    )
    return WspProfile(policy=policy, wiring=wiring)


def test_wsp_streams_engine_world(monkeypatch, tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir()
    receipt = _write_run_receipt(engine_root)
    rows = _write_arrival_events(engine_root, receipt, "baseline_v1")
    _write_stream_view(engine_root, output_id="arrival_events_5B", rows=rows)
    profile = _profile(engine_root, output_ids=["arrival_events_5B"])
    producer = WorldStreamProducer(profile)

    sent: list[dict] = []

    def _fake_push(envelope: dict) -> None:
        sent.append(envelope)

    monkeypatch.setattr(producer, "_push_to_ig", _fake_push)
    scenario_run_id = "a" * 32
    result = producer.stream_engine_world(
        engine_run_root=str(engine_root),
        scenario_id="baseline_v1",
        scenario_run_id=scenario_run_id,
        max_events=5,
    )

    assert result.status == "STREAMED"
    assert result.emitted == 1
    assert sent
    expected_trace = hashlib.sha256(str(engine_root).encode("utf-8")).hexdigest()
    assert sent[0].get("producer") == "svc:world_stream_producer"
    assert sent[0].get("trace_id") == expected_trace
    assert sent[0].get("schema_version") == "v1"
    assert sent[0].get("scenario_run_id") == scenario_run_id
    assert sent[0].get("run_id") == receipt["run_id"]


def test_wsp_fails_missing_gate(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir()
    _write_run_receipt(engine_root)
    profile = _profile(engine_root, output_ids=["outlet_catalogue"])
    producer = WorldStreamProducer(profile)
    result = producer.stream_engine_world(engine_run_root=str(engine_root), scenario_id="baseline_v1")
    assert result.status == "FAILED"
    assert result.reason == "GATE_PASS_MISSING"


def test_wsp_checkpoint_resume(monkeypatch, tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir()
    receipt = _write_run_receipt(engine_root)
    rows = _write_arrival_events(engine_root, receipt, "baseline_v1", count=2)
    _write_stream_view(engine_root, output_id="arrival_events_5B", rows=rows)
    profile = _profile(engine_root, output_ids=["arrival_events_5B"], checkpoint_root=tmp_path / "cp")
    producer = WorldStreamProducer(profile)

    sent: list[dict] = []

    def _fake_push(envelope: dict) -> None:
        sent.append(envelope)

    monkeypatch.setattr(producer, "_push_to_ig", _fake_push)
    first = producer.stream_engine_world(
        engine_run_root=str(engine_root), scenario_id="baseline_v1", max_events=1
    )
    assert first.status == "STREAMED"
    assert first.emitted == 1

    sent.clear()
    second = producer.stream_engine_world(
        engine_run_root=str(engine_root), scenario_id="baseline_v1", max_events=5
    )
    assert second.status == "STREAMED"
    assert second.emitted == 1


def test_wsp_stream_view_supports_inflight_push_concurrency(monkeypatch, tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir()
    receipt = _write_run_receipt(engine_root)
    rows = _write_arrival_events(engine_root, receipt, "baseline_v1", count=8)
    _write_stream_view(engine_root, output_id="arrival_events_5B", rows=rows)
    profile = _profile(engine_root, output_ids=["arrival_events_5B"], checkpoint_root=tmp_path / "cp")
    producer = WorldStreamProducer(profile)

    state = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    def _fake_push(_envelope: dict) -> None:
        with lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.01)
        with lock:
            state["active"] -= 1

    monkeypatch.setenv("WSP_IG_PUSH_CONCURRENCY", "4")
    monkeypatch.setattr(producer, "_push_to_ig", _fake_push)
    result = producer.stream_engine_world(
        engine_run_root=str(engine_root),
        scenario_id="baseline_v1",
        max_events=8,
    )

    assert result.status == "STREAMED"
    assert result.emitted == 8
    assert state["max_active"] > 1


def test_wsp_checkpoint_isolated_by_platform_run_scope(monkeypatch, tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir()
    receipt = _write_run_receipt(engine_root)
    rows = _write_arrival_events(engine_root, receipt, "baseline_v1", count=2)
    _write_stream_view(engine_root, output_id="arrival_events_5B", rows=rows)
    profile = _profile(engine_root, output_ids=["arrival_events_5B"], checkpoint_root=tmp_path / "cp")
    producer = WorldStreamProducer(profile)

    sent: list[dict] = []

    def _fake_push(envelope: dict) -> None:
        sent.append(envelope)

    run_ids = iter(["platform_20260209T010101Z", "platform_20260209T010102Z"])
    monkeypatch.setattr(
        "fraud_detection.world_streamer_producer.runner.resolve_platform_run_id",
        lambda create_if_missing=True: next(run_ids),
    )
    monkeypatch.setattr(producer, "_push_to_ig", _fake_push)

    first = producer.stream_engine_world(
        engine_run_root=str(engine_root), scenario_id="baseline_v1", max_events=1
    )
    assert first.status == "STREAMED"
    assert first.emitted == 1


def test_replay_delay_bypass_requires_toggle_and_rate_plan(monkeypatch) -> None:
    monkeypatch.delenv("WSP_DISABLE_REPLAY_DELAY_WHEN_RATE_PLAN", raising=False)
    monkeypatch.delenv("WSP_RATE_PLAN_JSON", raising=False)
    assert _should_bypass_replay_delay_for_scheduled_rate_plan() is False

    monkeypatch.setenv("WSP_DISABLE_REPLAY_DELAY_WHEN_RATE_PLAN", "true")
    assert _should_bypass_replay_delay_for_scheduled_rate_plan() is False

    monkeypatch.setenv("WSP_RATE_PLAN_JSON", '[{"start_offset_seconds":0,"target_eps":75.0}]')
    assert _should_bypass_replay_delay_for_scheduled_rate_plan() is True


def test_replay_delay_seconds_returns_zero_when_bypassed() -> None:
    prev = time.strptime("2026-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
    current = time.strptime("2026-01-01T00:00:10Z", "%Y-%m-%dT%H:%M:%SZ")
    # Convert through datetime to exercise the same delay path as the runner.
    from datetime import datetime, timezone

    prev_dt = datetime(*prev[:6], tzinfo=timezone.utc)
    current_dt = datetime(*current[:6], tzinfo=timezone.utc)
    assert _replay_delay_seconds(prev_dt, current_dt, 2.0, bypass=False) == 5.0
    assert _replay_delay_seconds(prev_dt, current_dt, 2.0, bypass=True) == 0.0


def test_wsp_fails_producer_allowlist(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir()
    receipt = _write_run_receipt(engine_root)
    rows = _write_arrival_events(engine_root, receipt, "baseline_v1")
    _write_stream_view(engine_root, output_id="arrival_events_5B", rows=rows)
    allowlist = tmp_path / "allowlist.txt"
    allowlist.write_text("svc:other\n", encoding="utf-8")
    profile = _profile(
        engine_root,
        output_ids=["arrival_events_5B"],
        allowlist_ref=allowlist,
        producer_id="svc:world_stream_producer",
    )
    producer = WorldStreamProducer(profile)
    result = producer.stream_engine_world(engine_run_root=str(engine_root), scenario_id="baseline_v1")
    assert result.status == "FAILED"
    assert result.reason == "PRODUCER_NOT_ALLOWED"
