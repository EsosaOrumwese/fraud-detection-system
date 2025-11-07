"""CLI runner for Segment 2A (S0 gate plus optional S1 execution)."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Optional

import yaml

from engine.scenario_runner.l1_seg_2A import (
    Segment2AConfig,
    Segment2AOrchestrator,
    Segment2AResult,
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
    candidates = [Path(__file__).resolve()]
    repo_root: Optional[Path] = None
    for candidate in candidates[0].parents:
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
    except Exception:  # pragma: no cover - fallback path
        return default


def _print_summary(result: Segment2AResult) -> None:
    payload = {
        "manifest_fingerprint": result.manifest_fingerprint,
        "receipt_path": str(result.receipt_path),
        "inventory_path": str(result.inventory_path),
        "resumed": result.resumed,
    }
    if result.s1_output_path:
        payload["s1_output_path"] = str(result.s1_output_path)
        payload["s1_resumed"] = result.s1_resumed
    if result.s2_output_path:
        payload["s2_output_path"] = str(result.s2_output_path)
        payload["s2_resumed"] = result.s2_resumed
    if result.s2_run_report_path:
        payload["s2_run_report_path"] = str(result.s2_run_report_path)
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    parser = argparse.ArgumentParser(
        description="Run Segment 2A S0 gate (and optionally S1 provisional lookup) for the civil-time layer.",
    )
    parser.add_argument(
        "--data-root",
        required=True,
        type=Path,
        help="Base directory where governed artefacts and outputs are stored.",
    )
    parser.add_argument(
        "--upstream-manifest-fingerprint",
        required=True,
        help="Segment 1B manifest fingerprint gating access to site_locations.",
    )
    parser.add_argument(
        "--parameter-hash",
        required=True,
        help="Parameter hash used to scope the run (mirrors Layer-1 identity law).",
    )
    parser.add_argument(
        "--seed",
        required=True,
        type=int,
        help="Seed used when Segment 1B emitted site_locations.",
    )
    parser.add_argument(
        "--tzdb-release-tag",
        required=True,
        help="Release tag for the IANA tzdata bundle sealed into the manifest.",
    )
    parser.add_argument(
        "--git-commit-hex",
        help="Git commit hash (40 or 64 hex). Defaults to current HEAD if available.",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        help="Optional path to a dictionary override YAML for Segment 2A.",
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
        "--resume",
        action="store_true",
        help="Skip execution if outputs already exist for the resume manifest.",
    )
    parser.add_argument(
        "--resume-manifest",
        type=str,
        help="Manifest fingerprint produced by a prior Segment 2A S0 run (required with --resume).",
    )
    parser.add_argument(
        "--run-s1",
        action="store_true",
        help="Execute the provisional time-zone lookup (S1) after S0 completes.",
    )
    parser.add_argument(
        "--s1-chunk-size",
        type=int,
        default=250_000,
        help="Number of site rows to process per batch when running S1 (default: 250000).",
    )
    parser.add_argument(
        "--s1-resume",
        action="store_true",
        help="Skip S1 execution when its output partition already exists.",
    )
    parser.add_argument(
        "--run-s2",
        action="store_true",
        help="Execute the override/finalisation step (S2) after upstream phases complete.",
    )
    parser.add_argument(
        "--s2-chunk-size",
        type=int,
        default=250_000,
        help="Number of site rows to process per batch when running S2 (default: 250000).",
    )
    parser.add_argument(
        "--s2-resume",
        action="store_true",
        help="Skip S2 execution when its output partition already exists.",
    )

    args = parser.parse_args(argv)

    if args.resume and not args.resume_manifest:
        parser.error("--resume requires --resume-manifest to locate prior outputs")

    git_commit_hex = args.git_commit_hex or _discover_git_commit()

    dictionary_override = _load_dictionary_override(args.dictionary)
    orchestrator = Segment2AOrchestrator()
    result = orchestrator.run(
        Segment2AConfig(
            data_root=args.data_root,
            upstream_manifest_fingerprint=args.upstream_manifest_fingerprint,
            parameter_hash=args.parameter_hash,
            seed=args.seed,
            tzdb_release_tag=args.tzdb_release_tag,
            git_commit_hex=git_commit_hex,
            dictionary=dictionary_override,
            dictionary_path=args.dictionary,
            validation_bundle_path=args.validation_bundle,
            notes=args.notes,
            resume=args.resume,
            resume_manifest_fingerprint=args.resume_manifest,
            run_s1=args.run_s1,
            s1_chunk_size=args.s1_chunk_size,
            s1_resume=args.s1_resume,
            run_s2=args.run_s2,
            s2_chunk_size=args.s2_chunk_size,
            s2_resume=args.s2_resume,
        )
    )
    _print_summary(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
