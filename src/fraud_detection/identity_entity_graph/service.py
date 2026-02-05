"""Flask service wrapper for IEG query surface."""

from __future__ import annotations

import argparse
from typing import Any

from flask import Flask, jsonify, request

from fraud_detection.ingestion_gate.logging_utils import configure_logging
from fraud_detection.platform_runtime import platform_log_paths

from .query import IdentityGraphQuery, QueryError


def create_app(profile_path: str) -> Flask:
    configure_logging(log_paths=platform_log_paths(create_if_missing=True))
    query = IdentityGraphQuery.from_profile(profile_path)

    app = Flask(__name__)

    @app.get("/v1/ops/status")
    def ops_status() -> Any:
        scenario_run_id = request.args.get("scenario_run_id") or ""
        if not scenario_run_id:
            return jsonify({"error": "MISSING_SCENARIO_RUN_ID"}), 400
        return jsonify(query.status(scenario_run_id=scenario_run_id))

    @app.post("/v1/query/resolve")
    def query_resolve() -> Any:
        payload = request.get_json(force=True)
        try:
            pins = payload.get("pins")
            identifier = payload.get("identifier") or {}
            identifier_type = payload.get("identifier_type") or identifier.get("identifier_type")
            identifier_value = payload.get("identifier_value") or identifier.get("identifier_value")
            if not identifier_type or not identifier_value:
                raise QueryError("MISSING_IDENTIFIER", "identifier_type and identifier_value required")
            limit = int(payload.get("limit") or 50)
            page_token = payload.get("page_token")
            result = query.resolve_identity(
                pins=pins,
                identifier_type=str(identifier_type),
                identifier_value=str(identifier_value),
                limit=limit,
                page_token=page_token,
            )
            return jsonify(result)
        except QueryError as exc:
            return jsonify({"error": exc.code, "detail": exc.detail}), exc.status
        except Exception as exc:  # pragma: no cover - defensive
            return jsonify({"error": "INTERNAL_ERROR", "detail": str(exc)}), 500

    @app.post("/v1/query/profile")
    def query_profile() -> Any:
        payload = request.get_json(force=True)
        try:
            pins = payload.get("pins")
            entity_id = payload.get("entity_id")
            entity_type = payload.get("entity_type")
            if not entity_id or not entity_type:
                raise QueryError("MISSING_ENTITY", "entity_id and entity_type required")
            result = query.get_entity_profile(
                pins=pins,
                entity_id=str(entity_id),
                entity_type=str(entity_type),
            )
            return jsonify(result)
        except QueryError as exc:
            return jsonify({"error": exc.code, "detail": exc.detail}), exc.status
        except Exception as exc:  # pragma: no cover - defensive
            return jsonify({"error": "INTERNAL_ERROR", "detail": str(exc)}), 500

    @app.post("/v1/query/neighbors")
    def query_neighbors() -> Any:
        payload = request.get_json(force=True)
        try:
            pins = payload.get("pins")
            entity_id = payload.get("entity_id")
            entity_type = payload.get("entity_type")
            if not entity_id or not entity_type:
                raise QueryError("MISSING_ENTITY", "entity_id and entity_type required")
            limit = int(payload.get("limit") or 50)
            page_token = payload.get("page_token")
            result = query.get_neighbors(
                pins=pins,
                entity_id=str(entity_id),
                entity_type=str(entity_type),
                limit=limit,
                page_token=page_token,
            )
            return jsonify(result)
        except QueryError as exc:
            return jsonify({"error": exc.code, "detail": exc.detail}), exc.status
        except Exception as exc:  # pragma: no cover - defensive
            return jsonify({"error": "INTERNAL_ERROR", "detail": str(exc)}), 500

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="IEG query service")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app(args.profile)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
