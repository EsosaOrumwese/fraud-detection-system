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


def _parse_output_ids(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or None


def main() -> None:
    parser = argparse.ArgumentParser(description="World Stream Producer (engine-rooted)")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--engine-run-root", help="Engine run root (overrides profile wiring)")
    parser.add_argument("--scenario-id", help="Scenario id (required if not discoverable)")
    parser.add_argument("--output-ids", help="Comma-separated output_ids override (subset of policy)")
    parser.add_argument("--max-events", type=int, default=None, help="Max events to emit")
    args = parser.parse_args()

    configure_logging(level=logging.INFO, log_paths=platform_log_paths(create_if_missing=False))
    profile = WspProfile.load(Path(args.profile))
    producer = WorldStreamProducer(profile)
    result = producer.stream_engine_world(
        engine_run_root=args.engine_run_root,
        scenario_id=args.scenario_id,
        output_ids=_parse_output_ids(args.output_ids),
        max_events=args.max_events,
    )
    print(json.dumps(result.__dict__, sort_keys=True))
    raise SystemExit(0 if result.status == "STREAMED" else 1)


if __name__ == "__main__":
    main()
