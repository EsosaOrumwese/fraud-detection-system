from __future__ import annotations

import concurrent.futures
import json
from types import SimpleNamespace

import werkzeug

from fraud_detection.ingestion_gate import aws_lambda_handler
from fraud_detection.ingestion_gate.aws_lambda_handler import lambda_handler
from fraud_detection.ingestion_gate.errors import IngestionError
from fraud_detection.ingestion_gate.security import AuthContext
from fraud_detection.ingestion_gate import managed_service

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3"


def test_healthz_is_unprotected() -> None:
    app = managed_service.create_app()
    client = app.test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_managed_ingest_proxies_to_lambda(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_lambda_handler(event, context):
        captured["event"] = event
        captured["remaining"] = context.get_remaining_time_in_millis()
        return {
            "statusCode": 202,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"decision": "ADMIT"}),
        }

    monkeypatch.setattr(managed_service, "lambda_handler", fake_lambda_handler)
    app = managed_service.create_app(stage_name="v1", request_timeout_ms=30000)
    client = app.test_client()

    response = client.post(
        "/v1/ingest/push",
        headers={"X-IG-Api-Key": "test-key"},
        json={"event_id": "evt-1", "platform_run_id": "run-1"},
    )

    assert response.status_code == 202
    assert response.get_json()["decision"] == "ADMIT"
    event = captured["event"]
    assert isinstance(event, dict)
    assert event["requestContext"]["stage"] == "v1"
    assert event["requestContext"]["http"]["path"] == "/v1/ingest/push"
    lowered_headers = {str(k).lower(): v for k, v in event["headers"].items()}
    assert lowered_headers["x-ig-api-key"] == "test-key"
    assert json.loads(event["body"])["event_id"] == "evt-1"
    assert int(captured["remaining"]) > 0


def test_lambda_handler_maps_retryable_inflight_to_503_without_dlq(monkeypatch) -> None:
    dlq_called = {"value": False}

    class _RetryGate:
        def admit_push_with_decision(self, payload, *, auth_context=None):
            raise IngestionError("PUBLISH_IN_FLIGHT_RETRY", payload.get("event_id"))

    monkeypatch.setattr(
        "fraud_detection.ingestion_gate.aws_lambda_handler._authorize",
        lambda _headers: (
            AuthContext(
                actor_id="SYSTEM::managed_edge",
                source_type="SYSTEM",
                auth_mode="api_key",
                principal="api_key",
            ),
            None,
        ),
    )
    monkeypatch.setattr("fraud_detection.ingestion_gate.aws_lambda_handler._gate_for", lambda _run: _RetryGate())
    monkeypatch.setattr(
        "fraud_detection.ingestion_gate.aws_lambda_handler._send_dlq",
        lambda *_args, **_kwargs: dlq_called.__setitem__("value", True),
    )

    response = lambda_handler(
        {
            "requestContext": {"http": {"method": "POST", "path": "/v1/ingest/push"}, "stage": "v1"},
            "rawPath": "/v1/ingest/push",
            "headers": {"X-IG-Api-Key": "test-key"},
            "body": json.dumps({"event_id": "evt-1", "platform_run_id": "run-1"}),
        },
        SimpleNamespace(get_remaining_time_in_millis=lambda: 30000),
    )

    body = json.loads(response["body"])
    assert response["statusCode"] == 503
    assert body["reason"] == "PUBLISH_IN_FLIGHT_RETRY"
    assert dlq_called["value"] is False


def test_load_expected_api_key_prefers_injected_secret(monkeypatch) -> None:
    monkeypatch.setenv("IG_API_KEY_VALUE", "env-secret")
    monkeypatch.setenv("IG_API_KEY_PATH", "/fraud-platform/dev_full/ig/api_key")
    monkeypatch.setitem(aws_lambda_handler._API_KEY_CACHE, "path", None)
    monkeypatch.setitem(aws_lambda_handler._API_KEY_CACHE, "value", None)
    monkeypatch.setitem(aws_lambda_handler._API_KEY_CACHE, "loaded_at_epoch", 0)

    class _BoomClient:
        def get_parameter(self, **_kwargs):
            raise AssertionError("SSM should not be called when IG_API_KEY_VALUE is injected")

    monkeypatch.setattr(aws_lambda_handler, "_SSM_CLIENT", _BoomClient())

    value, error = aws_lambda_handler._load_expected_api_key()

    assert error is None
    assert value == "env-secret"


def test_load_expected_api_key_uses_single_flight_cache(monkeypatch) -> None:
    monkeypatch.delenv("IG_API_KEY_VALUE", raising=False)
    monkeypatch.setenv("IG_API_KEY_PATH", "/fraud-platform/dev_full/ig/api_key")
    monkeypatch.setenv("IG_API_KEY_CACHE_SECONDS", "300")
    monkeypatch.setitem(aws_lambda_handler._API_KEY_CACHE, "path", None)
    monkeypatch.setitem(aws_lambda_handler._API_KEY_CACHE, "value", None)
    monkeypatch.setitem(aws_lambda_handler._API_KEY_CACHE, "loaded_at_epoch", 0)
    call_count = {"value": 0}

    class _FakeClient:
        def get_parameter(self, **_kwargs):
            call_count["value"] += 1
            return {"Parameter": {"Value": "ssm-secret"}}

    monkeypatch.setattr(aws_lambda_handler, "_SSM_CLIENT", _FakeClient())

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _i: aws_lambda_handler._load_expected_api_key(), range(8)))

    assert all(error is None for _value, error in results)
    assert all(value == "ssm-secret" for value, _error in results)
    assert call_count["value"] == 1

    value, error = aws_lambda_handler._load_expected_api_key()

    assert error is None
    assert value == "ssm-secret"
    assert call_count["value"] == 1
