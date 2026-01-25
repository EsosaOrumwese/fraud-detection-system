"""Flask service wrapper for IG."""

from __future__ import annotations

import argparse
import os
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

from .admission import IngestionGate
from .config import WiringProfile
from .control_bus import FileControlBusReader, ReadyConsumer
from .errors import IngestionError, reason_code
from .logging_utils import configure_logging
from .pull_state import PullRunStore
from .schemas import SchemaRegistry


def create_app(profile_path: str) -> Flask:
    configure_logging()
    wiring = WiringProfile.load(Path(profile_path))
    gate = IngestionGate.build(wiring)

    app = Flask(__name__)

    @app.post("/v1/ingest/push")
    def ingest_push() -> Any:
        payload = request.get_json(force=True)
        try:
            decision, receipt = gate.admit_push_with_decision(payload)
            receipt_id = receipt.payload.get("receipt_id")
            receipt_ref = None
            if receipt_id:
                lookup = gate.ops_index.lookup_receipt(receipt_id)
                receipt_ref = lookup.get("receipt_ref") if lookup else None
            return jsonify({"decision": decision.decision, "receipt": receipt.payload, "receipt_ref": receipt_ref})
        except IngestionError as exc:
            return jsonify({"error": exc.code, "detail": exc.detail}), 400
        except Exception as exc:  # pragma: no cover - defensive
            return jsonify({"error": reason_code(exc)}), 500

    @app.post("/v1/ingest/pull")
    def ingest_pull() -> Any:
        payload = request.get_json(force=True) or {}
        run_id = payload.get("run_id")
        run_facts_ref = payload.get("run_facts_ref") or payload.get("facts_view_ref")
        message_id = payload.get("message_id")
        try:
            if not run_facts_ref and run_id:
                run_facts_ref = gate.resolve_run_facts_ref(run_id)
            if not run_facts_ref:
                raise IngestionError("RUN_FACTS_MISSING")
            status = gate.admit_pull_with_state(run_facts_ref, run_id=run_id, message_id=message_id)
            return jsonify(status)
        except IngestionError as exc:
            return jsonify({"error": exc.code, "detail": exc.detail}), 400
        except Exception as exc:  # pragma: no cover - defensive
            return jsonify({"error": reason_code(exc)}), 500

    @app.get("/v1/ops/lookup")
    def ops_lookup() -> Any:
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
        result = gate.health.check()
        return jsonify({"state": result.state.value, "reasons": result.reasons})

    _start_ready_consumer(app, wiring, gate)
    return app


def _start_ready_consumer(app: Flask, wiring: WiringProfile, gate: IngestionGate) -> None:
    if os.getenv("IG_READY_CONSUMER", "false").lower() not in {"1", "true", "yes"}:
        return
    if wiring.control_bus_kind != "file":
        raise RuntimeError("CONTROL_BUS_KIND_UNSUPPORTED")
    root = Path(wiring.control_bus_root or "artefacts/fraud-platform/control_bus")
    registry = SchemaRegistry(Path(wiring.schema_root) / "scenario_runner")
    reader = FileControlBusReader(root, wiring.control_bus_topic, registry=registry)
    consumer = ReadyConsumer(gate, reader, PullRunStore(gate.store))
    stop_event = threading.Event()

    def loop() -> None:
        interval = float(os.getenv("IG_READY_POLL_SECONDS", "2.0"))
        while not stop_event.is_set():
            consumer.poll_once()
            time.sleep(interval)

    thread = threading.Thread(target=loop, name="ig-ready-consumer", daemon=True)
    thread.start()

    @app.teardown_appcontext
    def _stop_ready_consumer(exc: Exception | None = None) -> None:
        stop_event.set()


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
