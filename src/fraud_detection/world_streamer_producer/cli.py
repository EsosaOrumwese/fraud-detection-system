"""CLI entrypoint for WSP."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from fraud_detection.platform_runtime import platform_log_paths
from fraud_detection.scenario_runner.logging_utils import configure_logging

from .config import WspProfile
from .runner import WorldStreamProducer


def main() -> None:
    parser = argparse.ArgumentParser(description="World Stream Producer (WSP)")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Process READY messages once and exit")
    parser.add_argument("--max-events", type=int, default=1, help="Max events to emit (smoke guard)")
    args = parser.parse_args()

    configure_logging(level=logging.INFO, log_paths=platform_log_paths(create_if_missing=False))
    profile = WspProfile.load(Path(args.profile))
    producer = WorldStreamProducer(profile)

    if args.once:
        results = producer.poll_ready_once(max_events=args.max_events)
        print(json.dumps(results, sort_keys=True))
        return

    # Default behavior: run once for now (no daemon loop yet).
    results = producer.poll_ready_once(max_events=args.max_events)
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()

