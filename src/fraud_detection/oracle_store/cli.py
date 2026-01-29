"""CLI entrypoint for Oracle Store checks."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from fraud_detection.platform_runtime import platform_log_paths
from fraud_detection.scenario_runner.logging_utils import configure_logging

from .checker import OracleStoreChecker
from .config import OracleProfile


def _parse_output_ids(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    parts = [item.strip() for item in raw.split(",") if item.strip()]
    return parts or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle Store checker (engine-rooted)")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--engine-run-root", required=True, help="Engine run root path or URI")
    parser.add_argument("--scenario-id", help="Scenario id (required if not discoverable from engine root)")
    parser.add_argument(
        "--output-ids",
        help="Comma-separated output_ids to verify exist under engine run root",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--strict-seal", action="store_true", help="Fail if seal markers are missing")
    group.add_argument("--allow-unsealed", action="store_true", help="Allow missing seal markers")
    args = parser.parse_args()

    configure_logging(level=logging.INFO, log_paths=platform_log_paths(create_if_missing=True))
    profile = OracleProfile.load(Path(args.profile))
    if args.strict_seal:
        strict_seal = True
    elif args.allow_unsealed:
        strict_seal = False
    else:
        strict_seal = profile.wiring.profile_id in {"dev", "prod"}
    checker = OracleStoreChecker(profile)
    report = checker.check_engine_run(
        args.engine_run_root,
        scenario_id=args.scenario_id,
        strict_seal=strict_seal,
        output_ids=_parse_output_ids(args.output_ids),
    )
    print(json.dumps(report.__dict__, sort_keys=True))
    raise SystemExit(0 if report.ok() else 1)


if __name__ == "__main__":
    main()
