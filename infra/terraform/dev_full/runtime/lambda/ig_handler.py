import json
import logging
import os
import time

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

CORRELATION_FIELDS = (
    "platform_run_id",
    "scenario_run_id",
    "phase_id",
    "event_id",
    "runtime_lane",
    "trace_id",
)

CORRELATION_HEADERS = (
    "traceparent",
    "tracestate",
    "x-fp-platform-run-id",
    "x-fp-phase-id",
    "x-fp-event-id",
)


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _parse_body(event: dict) -> dict:
    raw = event.get("body")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _extract_headers(event: dict) -> dict:
    headers = event.get("headers") if isinstance(event.get("headers"), dict) else {}
    normalized = {str(k).lower(): v for k, v in headers.items()}
    return {k: normalized.get(k) for k in CORRELATION_HEADERS}


def lambda_handler(event, _context):
    request_context = event.get("requestContext", {}) if isinstance(event, dict) else {}
    http = request_context.get("http", {}) if isinstance(request_context, dict) else {}
    method = (http.get("method") or "").upper()
    path = http.get("path") or event.get("rawPath") or ""
    stage = request_context.get("stage") if isinstance(request_context, dict) else None

    # HTTP API can include the stage segment in raw request path. Normalize so
    # route checks stay stable across default/staged endpoint invocations.
    if stage:
        stage_prefix = f"/{stage}"
        if path == stage_prefix:
            path = "/"
        elif path.startswith(f"{stage_prefix}/"):
            path = path[len(stage_prefix) :]

    if method == "GET" and path == "/ops/health":
        return _response(
            200,
            {
                "status": "ok",
                "service": "ig-edge",
                "mode": "apigw_lambda_ddb",
                "timestamp_epoch": int(time.time()),
            },
        )

    if method == "POST" and path == "/ingest/push":
        table = os.getenv("IG_IDEMPOTENCY_TABLE", "unset")
        payload = _parse_body(event if isinstance(event, dict) else {})
        correlation_echo = {k: payload.get(k) for k in CORRELATION_FIELDS}
        correlation_headers = _extract_headers(event if isinstance(event, dict) else {})
        # Log correlation-only envelope for audit; never log full payload.
        LOGGER.info(
            json.dumps(
                {
                    "event": "ig_ingest_boundary",
                    "timestamp_epoch": int(time.time()),
                    "correlation_echo": correlation_echo,
                    "correlation_headers": correlation_headers,
                }
            )
        )
        return _response(
            202,
            {
                "admitted": True,
                "ingress_mode": "managed_edge",
                "idempotency_table": table,
                "correlation_echo": correlation_echo,
                "note": "runtime-surface validation handler",
            },
        )

    return _response(404, {"error": "route_not_found", "path": path, "method": method})
