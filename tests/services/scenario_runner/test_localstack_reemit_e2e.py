from __future__ import annotations

import json
import os
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import EngineAttemptResult, EngineInvoker
from fraud_detection.scenario_runner.models import ReemitKind, ReemitRequest, RunRequest, RunWindow, ScenarioBinding, Strategy
from fraud_detection.scenario_runner.runner import ScenarioRunner


pytestmark = [pytest.mark.localstack, pytest.mark.integration]


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


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


def _require_env() -> dict[str, str]:
    endpoint = _env("SR_KINESIS_ENDPOINT_URL")
    stream = _env("SR_KINESIS_STREAM")
    region = _env("SR_KINESIS_REGION") or _env("AWS_DEFAULT_REGION")
    access_key = _env("AWS_ACCESS_KEY_ID")
    secret_key = _env("AWS_SECRET_ACCESS_KEY")
    if not all([endpoint, stream, region, access_key, secret_key]):
        pytest.skip("LocalStack Kinesis env not configured")
    return {
        "endpoint": endpoint,
        "stream": stream,
        "region": region,
    }


def _ensure_stream(client, stream_name: str) -> str:
    try:
        client.describe_stream_summary(StreamName=stream_name)
    except client.exceptions.ResourceNotFoundException:
        client.create_stream(StreamName=stream_name, ShardCount=1)
    for _ in range(20):
        summary = client.describe_stream_summary(StreamName=stream_name)
        if summary["StreamDescriptionSummary"]["StreamStatus"] == "ACTIVE":
            break
        time.sleep(0.5)
    desc = client.describe_stream(StreamName=stream_name)
    shards = desc["StreamDescription"]["Shards"]
    if not shards:
        raise RuntimeError("Kinesis stream has no shards")
    return shards[0]["ShardId"]


def _fetch_envelope(client, stream: str, shard_id: str, message_id: str, timeout_seconds: float = 6.0) -> dict[str, Any]:
    iterator = client.get_shard_iterator(
        StreamName=stream,
        ShardId=shard_id,
        ShardIteratorType="TRIM_HORIZON",
    )["ShardIterator"]
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        records = client.get_records(ShardIterator=iterator, Limit=25)
        iterator = records["NextShardIterator"]
        for record in records["Records"]:
            envelope = json.loads(record["Data"].decode("utf-8"))
            if envelope.get("message_id") == message_id:
                return envelope
        time.sleep(0.2)
    raise AssertionError(f"message_id not found in stream: {message_id}")


def _build_wiring(tmp_path: Path, env: dict[str, str]) -> WiringProfile:
    return WiringProfile(
        object_store_root=str(tmp_path / "artefacts"),
        control_bus_topic="fp.bus.control.v1",
        control_bus_root=str(tmp_path / "control_bus"),
        control_bus_kind="kinesis",
        control_bus_stream=env["stream"],
        control_bus_region=env["region"],
        control_bus_endpoint_url=env["endpoint"],
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


def test_localstack_reemit_ready_e2e(tmp_path: Path) -> None:
    env = _require_env()
    import boto3

    client = boto3.client("kinesis", region_name=env["region"], endpoint_url=env["endpoint"])
    shard_id = _ensure_stream(client, env["stream"])

    engine_root = tmp_path / "engine_root"
    wiring = _build_wiring(tmp_path, env)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, StubEngineInvoker(engine_root))

    request = RunRequest(
        run_equivalence_key="kinesis-ready-e2e",
        manifest_fingerprint="a" * 64,
        parameter_hash="b" * 64,
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

    reemit = runner.reemit(ReemitRequest(run_id=response.run_id, reemit_kind=ReemitKind.READY_ONLY, reason="e2e"))
    assert "Reemit published" in reemit.message
    events = runner.ledger.read_record_events(response.run_id)
    reemit_event = next(event for event in events if event.get("event_kind") == "REEMIT_PUBLISHED")
    message_id = reemit_event["details"]["message_id"]

    envelope = _fetch_envelope(client, env["stream"], shard_id, message_id)
    assert envelope["attributes"]["kind"] == "READY_REEMIT"
    assert envelope["payload"]["run_id"] == response.run_id


def test_localstack_reemit_terminal_e2e(tmp_path: Path) -> None:
    env = _require_env()
    import boto3

    client = boto3.client("kinesis", region_name=env["region"], endpoint_url=env["endpoint"])
    shard_id = _ensure_stream(client, env["stream"])

    wiring = _build_wiring(tmp_path, env)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, StubEngineInvoker(tmp_path / "engine_root"))

    request = RunRequest(
        run_equivalence_key="kinesis-terminal-e2e",
        manifest_fingerprint="a" * 64,
        parameter_hash="b" * 64,
        seed=7,
        scenario=ScenarioBinding(scenario_id="s1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        output_ids=["unknown_output"],
        engine_run_root=str(tmp_path / "engine_root"),
        requested_strategy=Strategy.FORCE_REUSE,
        invoker="test",
    )

    response = runner.submit_run(request)
    assert response.message == "Run failed."

    reemit = runner.reemit(
        ReemitRequest(run_id=response.run_id, reemit_kind=ReemitKind.TERMINAL_ONLY, reason="e2e-terminal"),
    )
    assert "Reemit published" in reemit.message
    events = runner.ledger.read_record_events(response.run_id)
    reemit_event = next(event for event in events if event.get("event_kind") == "REEMIT_PUBLISHED")
    message_id = reemit_event["details"]["message_id"]

    envelope = _fetch_envelope(client, env["stream"], shard_id, message_id)
    assert envelope["attributes"]["kind"] == "TERMINAL_REEMIT"
    assert envelope["payload"]["run_id"] == response.run_id
