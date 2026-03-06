from __future__ import annotations

import json

from fraud_detection.ingestion_gate import managed_service


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
