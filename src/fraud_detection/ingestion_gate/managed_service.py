"""HTTP service wrapper for the managed IG edge runtime.

This preserves the same DDB/Kafka/S3 admission semantics as the Lambda edge by
adapting incoming HTTP requests into the existing managed-edge handler.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from typing import Any

from flask import Flask, Response, jsonify, request

from .aws_lambda_handler import lambda_handler


class _RequestContext:
    def __init__(self, timeout_ms: int) -> None:
        self._deadline = time.monotonic() + (max(1000, int(timeout_ms)) / 1000.0)

    def get_remaining_time_in_millis(self) -> int:
        remaining = self._deadline - time.monotonic()
        return max(0, int(remaining * 1000))


def _configure_logging() -> None:
    gunicorn_error = logging.getLogger("gunicorn.error")
    root_logger = logging.getLogger()
    if gunicorn_error.handlers:
        root_logger.handlers = list(gunicorn_error.handlers)
    level_name = str(os.getenv("IG_LOG_LEVEL", "INFO") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger.setLevel(level)
    logging.getLogger(__name__).setLevel(level)
    logging.getLogger("fraud_detection").setLevel(level)


def create_app(*, stage_name: str = "v1", request_timeout_ms: int = 30000) -> Flask:
    _configure_logging()
    app = Flask(__name__)
    stage = str(stage_name).strip() or "v1"
    timeout_ms = max(1000, int(request_timeout_ms))
    slow_request_log_ms = max(1, int(str(os.getenv("IG_SLOW_REQUEST_LOG_MS", "500")).strip() or "500"))
    logger = logging.getLogger(__name__)

    @app.get("/healthz")
    def healthz() -> Any:
        return jsonify({"status": "ok", "service": "ig-edge-managed-http"}), 200

    @app.post("/v1/ingest/push")
    @app.get("/v1/ops/health")
    def managed_edge_proxy() -> Response:
        started = time.monotonic()
        body_bytes = request.get_data(cache=True)
        event = {
            "version": "2.0",
            "rawPath": request.path,
            "headers": {str(k): str(v) for k, v in request.headers.items()},
            "body": body_bytes.decode("utf-8") if body_bytes else "",
            "isBase64Encoded": False,
            "requestContext": {
                "stage": stage,
                "http": {
                    "method": request.method,
                    "path": request.path,
                },
            },
        }
        result = lambda_handler(event, _RequestContext(timeout_ms))
        status_code = int(result.get("statusCode", 500) or 500)
        payload = str(result.get("body", "") or "")
        headers = dict(result.get("headers") or {})
        elapsed_ms = (time.monotonic() - started) * 1000.0
        if status_code >= 400 or elapsed_ms >= float(slow_request_log_ms):
            logger.info(
                "IG managed request path=%s method=%s status=%s elapsed_ms=%.3f body_bytes=%s",
                request.path,
                request.method,
                status_code,
                elapsed_ms,
                len(body_bytes),
            )
        return Response(payload, status=status_code, headers=headers, mimetype=headers.get("Content-Type"))

    @app.get("/v1/ops/lookup")
    def ops_lookup_not_supported() -> Any:
        return jsonify({"error": "not_supported", "detail": "Managed HTTP edge exposes ingest and health only."}), 501

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run managed HTTP ingress edge.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--stage-name", default="v1")
    parser.add_argument("--request-timeout-ms", type=int, default=30000)
    args = parser.parse_args()

    app = create_app(stage_name=args.stage_name, request_timeout_ms=args.request_timeout_ms)
    app.run(host=args.host, port=args.port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
