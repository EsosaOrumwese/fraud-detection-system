"""CLI: build a global time-sorted stream view (Option C)."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from fraud_detection.platform_runtime import platform_log_paths
from fraud_detection.scenario_runner.logging_utils import configure_logging

from .config import OracleProfile
from .engine_reader import resolve_engine_root
from .stream_sorter import build_stream_view, compute_stream_view_id, load_output_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle Store stream view builder")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--engine-run-root", required=True, help="Engine run root (local or s3://)")
    parser.add_argument("--scenario-id", required=True, help="Scenario id for this engine world")
    parser.add_argument(
        "--output-ids-ref",
        required=False,
        help="YAML ref containing output_ids list (default: config/platform/wsp/traffic_outputs_v0.yaml)",
    )
    parser.add_argument(
        "--stream-view-root",
        required=False,
        help="Target stream view root (default from profile env)",
    )
    parser.add_argument(
        "--partition-granularity",
        default="day",
        help="Partition granularity (day only in v0)",
    )
    args = parser.parse_args()

    configure_logging(level=logging.INFO, log_paths=platform_log_paths(create_if_missing=True))
    profile = OracleProfile.load(Path(args.profile))
    run_root = args.engine_run_root
    scenario_id = args.scenario_id
    resolved_root = resolve_engine_root(run_root, profile.wiring.oracle_root)
    default_ref = Path(args.profile).parent.parent / "wsp/traffic_outputs_v0.yaml"
    output_ids_ref = Path(args.output_ids_ref) if args.output_ids_ref else default_ref
    output_ids = load_output_ids(str(output_ids_ref))
    if not output_ids:
        raise SystemExit("OUTPUT_IDS_MISSING")

    stream_view_root = args.stream_view_root or f"{resolved_root.rstrip('/')}/stream_view/ts_utc"
    sort_keys = ["ts_utc", "event_type", "payload_hash"]
    stream_view_id = compute_stream_view_id(
        engine_run_root=resolved_root,
        scenario_id=scenario_id,
        output_ids=output_ids,
        sort_keys=sort_keys,
        partition_granularity=args.partition_granularity,
    )
    stream_view_root = f"{stream_view_root.rstrip('/')}/{stream_view_id}"

    receipt = build_stream_view(
        profile=profile,
        engine_run_root=resolved_root,
        scenario_id=scenario_id,
        output_ids=output_ids,
        stream_view_root=stream_view_root,
        stream_view_id=stream_view_id,
        partition_granularity=args.partition_granularity,
    )
    print(json.dumps(receipt.__dict__, sort_keys=True))


if __name__ == "__main__":
    main()
