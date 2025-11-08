"""CLI runner for Segment 2B (S0 gate)."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from engine.scenario_runner import Segment2BConfig, Segment2BOrchestrator, Segment2BResult

logger = logging.getLogger(__name__)


def _discover_git_commit(default: str = "0" * 40) -> str:
    repo_root: Optional[Path] = None
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".git").exists():
            repo_root = candidate
            break
    if repo_root is None:
        return default
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        commit = result.stdout.strip()
        return commit or default
    except Exception:
        return default


def _print_summary(result: Segment2BResult) -> None:
    payload = {
        "manifest_fingerprint": result.manifest_fingerprint,
        "parameter_hash": result.parameter_hash,
        "receipt_path": str(result.receipt_path),
        "inventory_path": str(result.inventory_path),
        "flag_sha256_hex": result.flag_sha256_hex,
        "verified_at_utc": result.verified_at_utc,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    parser = argparse.ArgumentParser(
        description="Run Segment 2B S0 gate for the routing engine.",
    )
    parser.add_argument(
        "--data-root",
        required=True,
        type=Path,
        help="Base directory where governed artefacts and outputs are stored.",
    )
    parser.add_argument(
        "--seed",
        required=True,
        type=int,
        help="Seed used when Segment 1B emitted site_locations.",
    )
    parser.add_argument(
        "--manifest-fingerprint",
        required=True,
        help="Manifest fingerprint produced by Segment 1B.",
    )
    parser.add_argument(
        "--parameter-hash",
        required=True,
        help="Parameter hash used to scope the routing run.",
    )
    parser.add_argument(
        "--git-commit-hex",
        type=str,
        help="Optional git commit hex recorded in the receipt (auto-detected if omitted).",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        help="Override path to the Segment 2B dataset dictionary.",
    )
    parser.add_argument(
        "--validation-bundle",
        type=Path,
        help="Explicit path to the Segment 1B validation bundle (fingerprint-scoped).",
    )
    parser.add_argument(
        "--notes",
        type=str,
        help="Optional notes recorded in the S0 receipt.",
    )
    parser.add_argument(
        "--pin-tz-assets",
        action="store_true",
        help="Pin site_timezones and tz_timetable_cache as optional dictionary assets.",
    )

    args = parser.parse_args(argv)

    git_commit_hex = args.git_commit_hex or _discover_git_commit()
    orchestrator = Segment2BOrchestrator()
    result = orchestrator.run(
        Segment2BConfig(
            data_root=args.data_root,
            seed=args.seed,
            manifest_fingerprint=args.manifest_fingerprint,
            parameter_hash=args.parameter_hash,
            git_commit_hex=git_commit_hex,
            dictionary_path=args.dictionary,
            validation_bundle_path=args.validation_bundle,
            notes=args.notes,
            pin_civil_time=args.pin_tz_assets,
        )
    )
    _print_summary(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
