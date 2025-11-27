"""CLI runner for Segment 5A (S0 gate)."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from engine.scenario_runner.l2_seg_5A import Segment5AConfig, Segment5AOrchestrator, Segment5AResult

logger = logging.getLogger(__name__)


def _discover_git_commit(default: str = "0" * 40) -> str:
    repo_root: Path | None = None
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".git").exists():
            repo_root = candidate
            break
    if repo_root is None:
        return default
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True
        )
        commit = result.stdout.strip()
        return commit or default
    except Exception:  # pragma: no cover
        return default


def _print_summary(result: Segment5AResult) -> None:
    payload = {
        "manifest_fingerprint": result.manifest_fingerprint,
        "parameter_hash": result.parameter_hash,
        "receipt_path": str(result.receipt_path),
        "sealed_inputs_path": str(result.sealed_inputs_path),
        "sealed_inputs_digest": result.sealed_inputs_digest,
        "run_report_path": str(result.run_report_path),
    }
    if result.s1_profile_path:
        payload["s1_profile_path"] = str(result.s1_profile_path)
    if result.s1_class_profile_path:
        payload["s1_class_profile_path"] = str(result.s1_class_profile_path)
    if result.s1_run_report_path:
        payload["s1_run_report_path"] = str(result.s1_run_report_path)
    if result.s1_resumed:
        payload["s1_resumed"] = result.s1_resumed
    if result.s2_grid_path:
        payload["s2_grid_path"] = str(result.s2_grid_path)
    if result.s2_shape_path:
        payload["s2_shape_path"] = str(result.s2_shape_path)
    if result.s2_catalogue_path:
        payload["s2_catalogue_path"] = str(result.s2_catalogue_path)
    if result.s2_run_report_path:
        payload["s2_run_report_path"] = str(result.s2_run_report_path)
    if result.s2_resumed:
        payload["s2_resumed"] = result.s2_resumed
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Run Segment 5A S0 gate (and optional S1/S2).")
    parser.add_argument("--data-root", required=True, type=Path, help="Run root base path.")
    parser.add_argument(
        "--upstream-manifest-fingerprint", required=True, help="Upstream manifest fingerprint (64 hex)."
    )
    parser.add_argument("--parameter-hash", required=True, help="Parameter hash for 5A (64 hex).")
    parser.add_argument("--run-id", required=False, default=None, help="Run identifier for this invocation.")
    parser.add_argument("--dictionary", type=Path, required=False, help="Override dataset dictionary path.")
    parser.add_argument("--validation-bundle-1a", type=Path, required=False, help="Override 1A validation bundle path.")
    parser.add_argument("--validation-bundle-1b", type=Path, required=False, help="Override 1B validation bundle path.")
    parser.add_argument("--validation-bundle-2a", type=Path, required=False, help="Override 2A validation bundle path.")
    parser.add_argument("--validation-bundle-2b", type=Path, required=False, help="Override 2B validation bundle path.")
    parser.add_argument("--validation-bundle-3a", type=Path, required=False, help="Override 3A validation bundle path.")
    parser.add_argument("--validation-bundle-3b", type=Path, required=False, help="Override 3B validation bundle path.")
    parser.add_argument("--skip-s1", action="store_true", help="Skip S1 demand profiles (runs S0 only).")
    parser.add_argument("--skip-s2", action="store_true", help="Skip S2 shapes (runs S0/S1 only).")
    parser.add_argument("--notes", type=str, required=False, help="Optional run notes for receipts.")
    parser.add_argument("--result-json", type=Path, required=False, help="Path to write a JSON summary.")

    args = parser.parse_args(argv)

    run_id = args.run_id or f"run-{_discover_git_commit()[:8]}"
    config = Segment5AConfig(
        data_root=args.data_root,
        upstream_manifest_fingerprint=args.upstream_manifest_fingerprint,
        parameter_hash=args.parameter_hash,
        run_id=run_id,
        dictionary_path=args.dictionary,
        validation_bundle_1a=args.validation_bundle_1a,
        validation_bundle_1b=args.validation_bundle_1b,
        validation_bundle_2a=args.validation_bundle_2a,
        validation_bundle_2b=args.validation_bundle_2b,
        validation_bundle_3a=args.validation_bundle_3a,
        validation_bundle_3b=args.validation_bundle_3b,
        notes=args.notes,
        run_s1=not args.skip_s1,
        run_s2=not args.skip_s2,
    )

    orchestrator = Segment5AOrchestrator()
    result = orchestrator.run(config)
    _print_summary(result)

    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result.__dict__, default=str, indent=2), encoding="utf-8")
        logger.info("Segment5A CLI: wrote summary to %s", args.result_json)

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
