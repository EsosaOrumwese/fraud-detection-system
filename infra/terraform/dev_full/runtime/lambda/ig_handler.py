import json
import os
import time


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


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
        return _response(
            202,
            {
                "admitted": True,
                "ingress_mode": "managed_edge",
                "idempotency_table": table,
                "note": "runtime-surface validation handler",
            },
        )

    return _response(404, {"error": "route_not_found", "path": path, "method": method})
