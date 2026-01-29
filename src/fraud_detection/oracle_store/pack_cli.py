"""CLI entrypoint to seal an oracle pack from engine outputs."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from fraud_detection.platform_runtime import platform_log_paths
from fraud_detection.scenario_runner.logging_utils import configure_logging

from .config import OracleProfile
from .packer import OraclePackPacker


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle Store pack sealer (engine-rooted)")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--engine-run-root", required=True, help="Engine run root path or URI")
    parser.add_argument("--scenario-id", required=True, help="Scenario id for this engine world")
    parser.add_argument("--engine-release", required=True, help="Engine release identifier")
    parser.add_argument("--pack-root", help="Override pack root (defaults to engine run root)")
    parser.add_argument(
        "--seal-status",
        default="SEALED_OK",
        choices=["SEALED_OK", "SEALED_FAILED"],
        help="Seal status to write",
    )
    args = parser.parse_args()

    configure_logging(level=logging.INFO, log_paths=platform_log_paths(create_if_missing=True))
    profile = OracleProfile.load(Path(args.profile))
    packer = OraclePackPacker(profile)
    result = packer.seal_from_engine_run(
        args.engine_run_root,
        scenario_id=args.scenario_id,
        pack_root=args.pack_root,
        engine_release=args.engine_release,
        seal_status=args.seal_status,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
