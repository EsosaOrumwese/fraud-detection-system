"""Flask service wrapper for IG."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

from .admission import IngestionGate
from .config import WiringProfile
from .errors import IngestionError, reason_code
from ..platform_runtime import platform_log_paths
from .logging_utils import configure_logging


def create_app(profile_path: str) -> Flask:
    configure_logging(log_paths=platform_log_paths(create_if_missing=True))
    wiring = WiringProfile.load(Path(profile_path))
    gate = IngestionGate.build(wiring)

    app = Flask(__name__)

    @app.post("/v1/ingest/push")
    def ingest_push() -> Any:
        payload = request.get_json(force=True)
        try:
            auth_context = _require_auth(gate, request)
            gate.enforce_push_rate_limit()
            decision, receipt = gate.admit_push_with_decision(payload, auth_context=auth_context)
            receipt_id = receipt.payload.get("receipt_id")
            receipt_ref = None
            if receipt_id:
                lookup = gate.ops_index.lookup_receipt(receipt_id)
                receipt_ref = lookup.get("receipt_ref") if lookup else None
            return jsonify({"decision": decision.decision, "receipt": receipt.payload, "receipt_ref": receipt_ref})
        except IngestionError as exc:
            return jsonify({"error": exc.code, "detail": exc.detail}), _error_status(exc)
        except Exception as exc:  # pragma: no cover - defensive
            return jsonify({"error": reason_code(exc)}), 500

    @app.get("/v1/ops/lookup")
    def ops_lookup() -> Any:
        _require_auth(gate, request)
        event_id = request.args.get("event_id")
        receipt_id = request.args.get("receipt_id")
        dedupe_key = request.args.get("dedupe_key")
        if event_id:
            result = gate.ops_index.lookup_event(event_id)
        elif receipt_id:
            result = gate.ops_index.lookup_receipt(receipt_id)
        elif dedupe_key:
            result = gate.ops_index.lookup_dedupe(dedupe_key)
        else:
            return jsonify({"error": "MISSING_QUERY"}), 400
        return jsonify(result or {})

    @app.get("/v1/ops/health")
    def ops_health() -> Any:
        _require_auth(gate, request)
        result = gate.health.check()
        return jsonify({"state": result.state.value, "reasons": result.reasons})

    return app


def _error_status(exc: IngestionError) -> int:
    if exc.code in {
        "UNAUTHORIZED",
        "AUTH_MODE_UNKNOWN",
        "AUTH_MODE_UNSUPPORTED",
        "AUTH_SERVICE_TOKEN_SECRET_MISSING",
    }:
        return 401
    if exc.code == "RATE_LIMITED":
        return 429
    return 400


def _require_auth(gate: IngestionGate, req):
    token = req.headers.get(gate.api_key_header)
    return gate.authorize_request(token)


def main() -> None:
    parser = argparse.ArgumentParser(description="IG service")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app(args.profile)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
