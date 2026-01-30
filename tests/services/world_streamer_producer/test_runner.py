from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from fraud_detection.world_streamer_producer.config import PolicyProfile, WiringProfile, WspProfile
from fraud_detection.world_streamer_producer.runner import WorldStreamProducer


def _write_run_receipt(root: Path) -> dict:
    receipt = {
        "manifest_fingerprint": "c" * 64,
        "parameter_hash": "1" * 64,
        "seed": 42,
        "run_id": "abcd" * 8,
    }
    (root / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    return receipt


def _write_arrival_events(root: Path, receipt: dict, scenario_id: str, *, count: int = 1) -> None:
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
        checkpoint_backend="file",
        checkpoint_root=str(checkpoint_root or (root / "wsp" / "checkpoints")),
        checkpoint_dsn=None,
        checkpoint_every=1,
        producer_id=producer_id,
        producer_allowlist_ref=str(allowlist_path),
    )
    return WspProfile(policy=policy, wiring=wiring)


def test_wsp_streams_engine_world(monkeypatch, tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir()
    receipt = _write_run_receipt(engine_root)
    _write_arrival_events(engine_root, receipt, "baseline_v1")
    profile = _profile(engine_root, output_ids=["arrival_events_5B"])
    producer = WorldStreamProducer(profile)

    sent: list[dict] = []

    def _fake_push(envelope: dict) -> None:
        sent.append(envelope)

    monkeypatch.setattr(producer, "_push_to_ig", _fake_push)
    result = producer.stream_engine_world(
        engine_run_root=str(engine_root), scenario_id="baseline_v1", max_events=5
    )

    assert result.status == "STREAMED"
    assert result.emitted == 1
    assert sent
    expected_trace = hashlib.sha256(str(engine_root).encode("utf-8")).hexdigest()
    assert sent[0].get("producer") == "svc:world_stream_producer"
    assert sent[0].get("trace_id") == expected_trace


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
    _write_arrival_events(engine_root, receipt, "baseline_v1", count=2)
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


def test_wsp_fails_producer_allowlist(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_run"
    engine_root.mkdir()
    receipt = _write_run_receipt(engine_root)
    _write_arrival_events(engine_root, receipt, "baseline_v1")
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
