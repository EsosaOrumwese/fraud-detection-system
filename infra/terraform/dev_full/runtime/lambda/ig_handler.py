import json
import logging
import os
import time
import hmac
import base64

import boto3
from botocore.exceptions import BotoCoreError, ClientError

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

PROTECTED_ROUTES = {
    ("GET", "/ops/health"),
    ("POST", "/ingest/push"),
}

_SSM_CLIENT = boto3.client("ssm")
_API_KEY_CACHE = {
    "path": None,
    "value": None,
    "loaded_at_epoch": 0,
}


def _safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _auth_mode() -> str:
    mode = os.getenv("IG_AUTH_MODE", "api_key").strip().lower()
    return mode or "api_key"


def _auth_header_name() -> str:
    header = os.getenv("IG_AUTH_HEADER_NAME", "X-IG-Api-Key").strip()
    return header or "X-IG-Api-Key"


def _api_key_cache_ttl_seconds() -> int:
    return _safe_int(os.getenv("IG_API_KEY_CACHE_SECONDS", "300"), 300)


def _max_request_bytes() -> int:
    return _safe_int(os.getenv("IG_MAX_REQUEST_BYTES", "1048576"), 1048576)


def _configured_envelope() -> dict:
    return {
        "max_request_bytes": _max_request_bytes(),
        "request_timeout_seconds": _safe_int(
            os.getenv("IG_REQUEST_TIMEOUT_SECONDS", "30"), 30
        ),
        "internal_retry_max_attempts": _safe_int(
            os.getenv("IG_INTERNAL_RETRY_MAX_ATTEMPTS", "3"), 3
        ),
        "internal_retry_backoff_ms": _safe_int(
            os.getenv("IG_INTERNAL_RETRY_BACKOFF_MS", "250"), 250
        ),
        "idempotency_ttl_seconds": _safe_int(
            os.getenv("IG_IDEMPOTENCY_TTL_SECONDS", "259200"), 259200
        ),
        "dlq_mode": os.getenv("IG_DLQ_MODE", "sqs"),
        "dlq_queue_name": os.getenv("IG_DLQ_QUEUE_NAME", ""),
        "replay_mode": os.getenv("IG_REPLAY_MODE", "dlq_replay_workflow"),
        "rate_limit_rps": _safe_float(os.getenv("IG_RATE_LIMIT_RPS", "200"), 200.0),
        "rate_limit_burst": _safe_int(os.getenv("IG_RATE_LIMIT_BURST", "400"), 400),
    }


def _body_size_bytes(event: dict) -> int:
    raw = event.get("body")
    if raw is None:
        return 0
    if isinstance(raw, dict):
        return len(json.dumps(raw, separators=(",", ":")).encode("utf-8"))
    if isinstance(raw, str):
        if bool(event.get("isBase64Encoded")):
            try:
                return len(base64.b64decode(raw.encode("utf-8"), validate=False))
            except Exception:
                return len(raw.encode("utf-8"))
        return len(raw.encode("utf-8"))
    return len(str(raw).encode("utf-8"))


def _load_expected_api_key() -> tuple[str | None, str | None]:
    api_key_path = os.getenv("IG_API_KEY_PATH", "").strip()
    if not api_key_path:
        return None, "ig_api_key_path_missing"

    now = int(time.time())
    cache_ttl = _api_key_cache_ttl_seconds()
    if (
        _API_KEY_CACHE["path"] == api_key_path
        and _API_KEY_CACHE["value"]
        and (now - int(_API_KEY_CACHE["loaded_at_epoch"])) < cache_ttl
    ):
        return str(_API_KEY_CACHE["value"]), None

    try:
        parameter = _SSM_CLIENT.get_parameter(Name=api_key_path, WithDecryption=True)
    except (BotoCoreError, ClientError) as exc:
        return None, f"ssm_get_parameter_failed:{type(exc).__name__}"

    expected_key = (
        parameter.get("Parameter", {}).get("Value")
        if isinstance(parameter, dict)
        else None
    )
    if not expected_key:
        return None, "ig_api_key_empty"

    _API_KEY_CACHE["path"] = api_key_path
    _API_KEY_CACHE["value"] = expected_key
    _API_KEY_CACHE["loaded_at_epoch"] = now
    return str(expected_key), None


def _authorize(event: dict) -> dict | None:
    mode = _auth_mode()
    if mode != "api_key":
        return _response(500, {"error": "auth_mode_invalid", "auth_mode": mode})

    headers = event.get("headers") if isinstance(event.get("headers"), dict) else {}
    normalized = {
        str(k).lower(): "" if v is None else str(v) for k, v in headers.items()
    }
    header_name = _auth_header_name()
    supplied_key = normalized.get(header_name.lower(), "")
    if not supplied_key:
        return _response(401, {"error": "unauthorized", "reason": "missing_api_key"})

    expected_key, load_error = _load_expected_api_key()
    if load_error:
        return _response(
            503,
            {"error": "auth_backend_unavailable", "reason": load_error},
        )

    if not hmac.compare_digest(supplied_key, str(expected_key)):
        return _response(401, {"error": "unauthorized", "reason": "invalid_api_key"})

    return None


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
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    if (method, path) in PROTECTED_ROUTES:
        auth_failure = _authorize(event if isinstance(event, dict) else {})
        if auth_failure is not None:
            return auth_failure

    if method == "GET" and path == "/ops/health":
        return _response(
            200,
            {
                "status": "ok",
                "service": "ig-edge",
                "mode": "apigw_lambda_ddb",
                "timestamp_epoch": int(time.time()),
                "envelope": _configured_envelope(),
            },
        )

    if method == "POST" and path == "/ingest/push":
        body_size = _body_size_bytes(event if isinstance(event, dict) else {})
        max_bytes = _max_request_bytes()
        if body_size > max_bytes:
            return _response(
                413,
                {
                    "error": "payload_too_large",
                    "body_size_bytes": body_size,
                    "max_request_bytes": max_bytes,
                },
            )

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
                "body_size_bytes": body_size,
                "correlation_echo": correlation_echo,
                "note": "runtime-surface validation handler",
            },
        )

    return _response(404, {"error": "route_not_found", "path": path, "method": method})
