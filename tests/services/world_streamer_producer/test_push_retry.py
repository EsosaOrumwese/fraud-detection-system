from types import SimpleNamespace

import pytest
import requests

from fraud_detection.ingestion_gate.errors import IngestionError
from fraud_detection.world_streamer_producer.config import PolicyProfile, WiringProfile, WspProfile
from fraud_detection.world_streamer_producer.runner import WorldStreamProducer


def _profile(tmp_path, *, max_attempts: int = 3) -> WspProfile:
    policy = PolicyProfile(
        policy_rev="test",
        require_gate_pass=False,
        stream_speedup=1.0,
        traffic_output_ids=[],
        context_output_ids=[],
    )
    wiring = WiringProfile(
        profile_id="test",
        object_store_root=str(tmp_path),
        object_store_endpoint=None,
        object_store_region=None,
        object_store_path_style=None,
        control_bus_kind="file",
        control_bus_root=str(tmp_path / "control"),
        control_bus_topic="fp.bus.control.v1",
        control_bus_stream=None,
        control_bus_region=None,
        control_bus_endpoint_url=None,
        schema_root="docs/model_spec/platform/contracts",
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        oracle_root=str(tmp_path),
        oracle_engine_run_root=None,
        oracle_scenario_id=None,
        stream_view_root=None,
        ig_ingest_url="http://localhost:8081",
        ig_auth_header="X-IG-Api-Key",
        ig_auth_token=None,
        checkpoint_backend="file",
        checkpoint_root=str(tmp_path / "checkpoints"),
        checkpoint_dsn=None,
        checkpoint_every=1,
        producer_id="svc:world_stream_producer",
        producer_allowlist_ref=None,
        ig_retry_max_attempts=max_attempts,
        ig_retry_base_delay_ms=1,
        ig_retry_max_delay_ms=2,
    )
    return WspProfile(policy=policy, wiring=wiring)


def test_push_retries_on_429(tmp_path, monkeypatch) -> None:
    profile = _profile(tmp_path, max_attempts=3)
    producer = WorldStreamProducer(profile)
    calls = {"count": 0}

    def fake_post(*_args, **_kwargs):
        calls["count"] += 1
        status = 429 if calls["count"] < 3 else 200
        return SimpleNamespace(status_code=status, text="rate limit")

    monkeypatch.setattr(requests, "post", fake_post)
    import fraud_detection.world_streamer_producer.runner as wsp_runner

    monkeypatch.setattr(wsp_runner.time, "sleep", lambda *_args, **_kwargs: None)

    producer._push_to_ig({"event_id": "evt-1"})
    assert calls["count"] == 3


def test_push_rejects_non_retryable_4xx(tmp_path, monkeypatch) -> None:
    profile = _profile(tmp_path, max_attempts=3)
    producer = WorldStreamProducer(profile)
    calls = {"count": 0}

    def fake_post(*_args, **_kwargs):
        calls["count"] += 1
        return SimpleNamespace(status_code=400, text="bad request")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(IngestionError) as excinfo:
        producer._push_to_ig({"event_id": "evt-2"})
    assert excinfo.value.code == "IG_PUSH_REJECTED"
    assert calls["count"] == 1
