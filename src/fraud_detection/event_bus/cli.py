"""Local Event Bus CLI (tail/replay)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fraud_detection.scenario_runner.logging_utils import configure_logging
from fraud_detection.platform_runtime import platform_run_root

from .reader import EventBusReader


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Event Bus local replay/tail")
    sub = parser.add_subparsers(dest="command", required=True)
    tail = sub.add_parser("tail", help="Read records from the local file-bus")
    tail.add_argument("--root", default=None, help="Bus root path")
    tail.add_argument("--topic", required=True, help="Topic name")
    tail.add_argument("--partition", type=int, default=0, help="Partition id")
    tail.add_argument("--from-offset", type=int, default=0, help="Start offset (inclusive)")
    tail.add_argument("--max", type=int, default=20, help="Max records to return")
    return parser


def _cmd_tail(args: argparse.Namespace) -> int:
    root = args.root
    if not root:
        run_root = platform_run_root(create_if_missing=False)
        if not run_root:
            raise SystemExit("PLATFORM_RUN_ID required to resolve event bus root.")
        root = str(run_root / "eb")
    reader = EventBusReader(Path(root))
    records = reader.read(
        args.topic,
        partition=args.partition,
        from_offset=args.from_offset,
        max_records=args.max,
    )
    for record in records:
        payload = {
            "topic": record.topic,
            "partition": record.partition,
            "offset": record.offset,
            "record": record.record,
        }
        print(json.dumps(payload, ensure_ascii=True))
    return 0


def main() -> int:
    configure_logging()
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "tail":
        return _cmd_tail(args)
    raise SystemExit("UNKNOWN_COMMAND")


if __name__ == "__main__":
    raise SystemExit(main())
