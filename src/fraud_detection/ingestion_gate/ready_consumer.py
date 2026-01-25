"""READY control bus consumer CLI."""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from .admission import IngestionGate
from .config import WiringProfile
from .control_bus import FileControlBusReader, ReadyConsumer
from .logging_utils import configure_logging
from ..platform_runtime import append_session_event, platform_log_paths
from .pull_state import PullRunStore
from .schemas import SchemaRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description="IG READY consumer")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Process READY messages once and exit")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval seconds")
    args = parser.parse_args()

    configure_logging(log_paths=platform_log_paths(create_if_missing=False))
    wiring = WiringProfile.load(Path(args.profile))
    gate = IngestionGate.build(wiring)
    if wiring.control_bus_kind != "file":
        raise SystemExit("CONTROL_BUS_KIND_UNSUPPORTED")
    root = Path(wiring.control_bus_root or "runs/fraud-platform/control_bus")
    registry = SchemaRegistry(Path(wiring.schema_root) / "scenario_runner")
    reader = FileControlBusReader(root, wiring.control_bus_topic, registry=registry)
    consumer = ReadyConsumer(gate, reader, PullRunStore(gate.store))

    if args.once:
        results = consumer.poll_once()
        append_session_event("ig", "ready_poll", {"results": results}, create_if_missing=False)
        print(json.dumps(results, ensure_ascii=True))
        return

    while True:
        results = consumer.poll_once()
        if results:
            append_session_event("ig", "ready_poll", {"results": results}, create_if_missing=False)
            logging.info("IG READY batch processed count=%d", len(results))
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
