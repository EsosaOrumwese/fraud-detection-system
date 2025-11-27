"""CLI runner for Segment 3B (S0 gate + S1 virtuals)."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Optional

import yaml

from engine.scenario_runner.l1_seg_3B import (
    Segment3BConfig,
    Segment3BOrchestrator,
    Segment3BResult,
)

logger = logging.getLogger(__name__)


def _load_dictionary_override(path: Optional[Path]) -> Optional[Mapping[str, object]]:
    if path is None:
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise ValueError("dictionary YAML must decode to a mapping")
    return payload  # type: ignore[return-value]


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
    except Exception:  # pragma: no cover
        return default


def _print_summary(result: Segment3BResult) -> None:
    payload = {
        "manifest_fingerprint": result.manifest_fingerprint,
        "parameter_hash": result.parameter_hash,
        "receipt_path": str(result.receipt_path),
        "sealed_inputs_path": str(result.sealed_inputs_path),
        "run_report_path": str(result.run_report_path),
        "resumed": result.resumed,
    }
    if result.s1_output_path:
        payload["s1_output_path"] = str(result.s1_output_path)
    if result.s1_run_report_path:
        payload["s1_run_report_path"] = str(result.s1_run_report_path)
    if result.s1_resumed:
        payload["s1_resumed"] = result.s1_resumed
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Run Segment 3B S0 gate and optional S1 virtual classification."
    )
    parser.add_argument("--data-root", required=True, type=Path, help="Run root base path.")
    parser.add_argument(
        "--upstream-manifest-fingerprint", required=True, help="Upstream manifest fingerprint (64 hex)."
    )
    parser.add_argument("--seed", required=True, type=int, help="Seed used for upstream segments.")
    parser.add_argument(
        "--git-commit-hex",
        required=False,
        default=None,
        help="Git commit hex for manifest sealing (defaults to HEAD if discoverable).",
    )
    parser.add_argument("--dictionary", type=Path, required=False, help="Override dataset dictionary path.")
    parser.add_argument("--validation-bundle-1a", type=Path, required=False, help="Override 1A validation bundle path.")
    parser.add_argument("--validation-bundle-1b", type=Path, required=False, help="Override 1B validation bundle path.")
    parser.add_argument("--validation-bundle-2a", type=Path, required=False, help="Override 2A validation bundle path.")
    parser.add_argument("--validation-bundle-3a", type=Path, required=False, help="Override 3A validation bundle path.")
    parser.add_argument("--notes", type=str, required=False, help="Optional run notes for receipts.")
    parser.add_argument("--result-json", type=Path, required=False, help="Path to write a JSON summary.")
    parser.add_argument(
        "--skip-s1",
        action="store_true",
        help="Skip S1 virtual classification/settlement (runs S0 gate only).",
    )
    parser.add_argument(
        "--run-s2",
        action="store_true",
        help="Run S2 edge catalogue construction after S1.",
    )
    parser.add_argument(
        "--run-s3",
        action="store_true",
        help="Run S3 alias/universe hash after S2.",
    )

    args = parser.parse_args(argv)

    git_commit_hex = args.git_commit_hex or _discover_git_commit()
    config = Segment3BConfig(
        data_root=args.data_root,
        upstream_manifest_fingerprint=args.upstream_manifest_fingerprint,
        seed=args.seed,
        git_commit_hex=git_commit_hex,
        dictionary_path=args.dictionary,
        validation_bundle_1a=args.validation_bundle_1a,
        validation_bundle_1b=args.validation_bundle_1b,
        validation_bundle_2a=args.validation_bundle_2a,
        validation_bundle_3a=args.validation_bundle_3a,
        notes=args.notes,
        run_s1=not args.skip_s1,
        run_s2=args.run_s2,
        run_s3=args.run_s3,
    )

    orchestrator = Segment3BOrchestrator()
    result = orchestrator.run(config)
    _print_summary(result)

    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result.__dict__, default=str, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
