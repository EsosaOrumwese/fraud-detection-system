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


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle Store checker")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--run-facts-ref", required=True, help="run_facts_view reference path")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--strict-seal", action="store_true", help="Fail if seal markers are missing")
    group.add_argument("--allow-unsealed", action="store_true", help="Allow missing seal markers")
    parser.add_argument("--allow-missing-digest", action="store_true", help="Do not fail on missing digests")
    args = parser.parse_args()

    configure_logging(level=logging.INFO, log_paths=platform_log_paths(create_if_missing=False))
    profile = OracleProfile.load(Path(args.profile))
    if args.strict_seal:
        strict_seal = True
    elif args.allow_unsealed:
        strict_seal = False
    else:
        strict_seal = profile.wiring.profile_id in {"dev", "prod"}
    checker = OracleStoreChecker(profile)
    report = checker.check_run_facts(
        args.run_facts_ref,
        strict_seal=strict_seal,
        require_digest=not args.allow_missing_digest,
    )
    print(json.dumps(report.__dict__, sort_keys=True))
    raise SystemExit(0 if report.ok() else 1)


if __name__ == "__main__":
    main()
