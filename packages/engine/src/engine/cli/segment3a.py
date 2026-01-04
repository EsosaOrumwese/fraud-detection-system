"""CLI runner for Segment 3A (S0 gate)."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Optional

import yaml

from engine.scenario_runner.l1_seg_3A import (
    Segment3AConfig,
    Segment3AOrchestrator,
    Segment3AResult,
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


def _print_summary(result: Segment3AResult) -> None:
    payload = {
        "manifest_fingerprint": result.manifest_fingerprint,
        "parameter_hash": result.parameter_hash,
        "receipt_path": str(result.receipt_path),
        "sealed_inputs_path": str(result.sealed_inputs_path),
        "resumed": result.resumed,
    }
    if result.s1_output_path:
        payload["s1_output_path"] = str(result.s1_output_path)
    if result.s1_run_report_path:
        payload["s1_run_report_path"] = str(result.s1_run_report_path)
    if result.s1_resumed:
        payload["s1_resumed"] = result.s1_resumed
    if result.s2_output_path:
        payload["s2_output_path"] = str(result.s2_output_path)
    if result.s2_run_report_path:
        payload["s2_run_report_path"] = str(result.s2_run_report_path)
    if result.s2_resumed:
        payload["s2_resumed"] = result.s2_resumed
    if result.s3_output_path:
        payload["s3_output_path"] = str(result.s3_output_path)
    if result.s3_run_report_path:
        payload["s3_run_report_path"] = str(result.s3_run_report_path)
    if result.s3_resumed:
        payload["s3_resumed"] = result.s3_resumed
    if result.s4_output_path:
        payload["s4_output_path"] = str(result.s4_output_path)
    if result.s4_run_report_path:
        payload["s4_run_report_path"] = str(result.s4_run_report_path)
    if result.s4_resumed:
        payload["s4_resumed"] = result.s4_resumed
    if result.s5_output_path:
        payload["s5_output_path"] = str(result.s5_output_path)
    if result.s5_run_report_path:
        payload["s5_run_report_path"] = str(result.s5_run_report_path)
    if result.s5_universe_hash_path:
        payload["s5_universe_hash_path"] = str(result.s5_universe_hash_path)
    if result.s5_resumed:
        payload["s5_resumed"] = result.s5_resumed
    if result.s6_report_path:
        payload["s6_report_path"] = str(result.s6_report_path)
    if result.s6_issues_path:
        payload["s6_issues_path"] = str(result.s6_issues_path)
    if result.s6_receipt_path:
        payload["s6_receipt_path"] = str(result.s6_receipt_path)
    if result.s6_run_report_path:
        payload["s6_run_report_path"] = str(result.s6_run_report_path)
    if result.s6_resumed:
        payload["s6_resumed"] = result.s6_resumed
    if result.s7_bundle_path:
        payload["s7_bundle_path"] = str(result.s7_bundle_path)
    if result.s7_passed_flag_path:
        payload["s7_passed_flag_path"] = str(result.s7_passed_flag_path)
    if result.s7_index_path:
        payload["s7_index_path"] = str(result.s7_index_path)
    if result.s7_run_report_path:
        payload["s7_run_report_path"] = str(result.s7_run_report_path)
    if result.s7_resumed:
        payload["s7_resumed"] = result.s7_resumed
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    parser = argparse.ArgumentParser(
        description="Run Segment 3A S0 gate (seal inputs and upstream validation bundles)."
    )
    parser.add_argument("--data-root", required=True, type=Path, help="Run root base path.")
    parser.add_argument(
        "--upstream-manifest-fingerprint",
        required=True,
        help="Manifest fingerprint from upstream segments (1A/1B/2A).",
    )
    parser.add_argument("--seed", required=True, type=int, help="Layer-1 seed for this run.")
    parser.add_argument(
        "--git-commit-hex",
        help="Git commit hash (40 or 64 hex). Defaults to current HEAD if available.",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        help="Optional path to a dictionary override YAML for Segment 3A.",
    )
    parser.add_argument(
        "--validation-bundle-1a",
        type=Path,
        help="Explicit path to the Segment 1A validation bundle (fingerprint-scoped).",
    )
    parser.add_argument(
        "--validation-bundle-1b",
        type=Path,
        help="Explicit path to the Segment 1B validation bundle (fingerprint-scoped).",
    )
    parser.add_argument(
        "--validation-bundle-2a",
        type=Path,
        help="Explicit path to the Segment 2A validation bundle (fingerprint-scoped).",
    )
    parser.add_argument("--notes", type=str, help="Optional notes recorded in the S0 receipt.")
    parser.add_argument("--run-s1", action="store_true", help="Run S1 escalation queue.")
    parser.add_argument("--run-s2", action="store_true", help="Run S2 priors stage.")
    parser.add_argument("--run-s3", action="store_true", help="Run S3 Dirichlet share sampling.")
    parser.add_argument("--run-s4", action="store_true", help="Run S4 integer zone counts.")
    parser.add_argument("--run-s5", action="store_true", help="Run S5 zone allocation egress.")
    parser.add_argument("--run-s6", action="store_true", help="Run S6 validation bundle.")
    parser.add_argument("--run-s7", action="store_true", help="Run S7 validation bundle + PASS flag.")
    parser.add_argument(
        "--parameter-hash",
        type=str,
        help="Parameter hash required for S0 (reused for S2 unless overridden).",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default="00000000000000000000000000000000",
        help="Run identifier for RNG/event logs (S3).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="If set, reuse existing S0 outputs for the provided resume manifest fingerprint.",
    )
    parser.add_argument(
        "--resume-manifest-fingerprint",
        type=str,
        help="Manifest fingerprint to resume if --resume is provided.",
    )
    parser.add_argument(
        "--result-json",
        type=Path,
        help="Optional JSON file to persist the Segment 3A run summary.",
    )
    parser.add_argument(
        "--quiet-summary",
        action="store_true",
        help="Suppress printing the Segment 3A summary to STDOUT.",
    )

    args = parser.parse_args(argv)
    git_commit = args.git_commit_hex or _discover_git_commit()
    orchestrator = Segment3AOrchestrator()

    config = Segment3AConfig(
        data_root=args.data_root,
        upstream_manifest_fingerprint=args.upstream_manifest_fingerprint,
        seed=args.seed,
        git_commit_hex=git_commit,
        dictionary_path=args.dictionary,
        validation_bundle_1a=args.validation_bundle_1a,
        validation_bundle_1b=args.validation_bundle_1b,
        validation_bundle_2a=args.validation_bundle_2a,
        notes=args.notes,
        resume=args.resume,
        resume_manifest_fingerprint=args.resume_manifest_fingerprint,
        run_s1=args.run_s1,
        run_s2=args.run_s2,
        run_s3=args.run_s3,
        run_s4=args.run_s4,
        run_s5=args.run_s5,
        run_s6=args.run_s6,
        run_s7=args.run_s7,
        parameter_hash=args.parameter_hash,
        run_id=args.run_id,
    )

    result = orchestrator.run(config)

    if not args.quiet_summary:
        _print_summary(result)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result.__dict__, default=str, indent=2), encoding="utf-8")
        logger.info("Segment3A CLI: wrote summary to %s", args.result_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
