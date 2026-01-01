"""CLI runner for Segment 5B (S0 gate plus optional S1-S5)."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from engine.scenario_runner.l2_seg_5B import Segment5BConfig, Segment5BOrchestrator, Segment5BResult

logger = logging.getLogger(__name__)


def _print_summary(result: Segment5BResult) -> None:
    logger.info("Segment5B completed: manifest=%s", result.manifest_fingerprint)
    logger.info("  sealed_inputs=%s", result.sealed_inputs_path)
    if result.s4_arrival_paths:
        logger.info("  arrivals=%s", list(result.s4_arrival_paths.values())[:1])
    if result.s5_bundle_index_path:
        logger.info("  validation_bundle=%s", result.s5_bundle_index_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Segment 5B S0 gate (and optional S1-S5).")
    parser.add_argument("--data-root", required=True, type=Path, help="Root directory containing data outputs")
    parser.add_argument("--manifest-fingerprint", required=True, help="Manifest fingerprint (64 hex)")
    parser.add_argument("--parameter-hash", required=True, help="Parameter hash (64 hex)")
    parser.add_argument("--seed", required=True, type=int, help="RNG seed (uint64)")
    parser.add_argument("--run-id", required=True, help="Run id")
    parser.add_argument("--dictionary-path", type=Path, help="Override dictionary path for 5B")
    parser.add_argument("--validation-bundle-1a", type=Path, help="Override validation bundle path for 1A")
    parser.add_argument("--validation-bundle-1b", type=Path, help="Override validation bundle path for 1B")
    parser.add_argument("--validation-bundle-2a", type=Path, help="Override validation bundle path for 2A")
    parser.add_argument("--validation-bundle-2b", type=Path, help="Override validation bundle path for 2B")
    parser.add_argument("--validation-bundle-3a", type=Path, help="Override validation bundle path for 3A")
    parser.add_argument("--validation-bundle-3b", type=Path, help="Override validation bundle path for 3B")
    parser.add_argument("--validation-bundle-5a", type=Path, help="Override validation bundle path for 5A")
    parser.add_argument("--no-s1", action="store_true", help="Skip S1 time grid/grouping")
    parser.add_argument("--no-s2", action="store_true", help="Skip S2 realised intensity")
    parser.add_argument("--no-s3", action="store_true", help="Skip S3 bucket counts")
    parser.add_argument("--no-s4", action="store_true", help="Skip S4 arrivals")
    parser.add_argument("--no-s5", action="store_true", help="Skip S5 validation")
    parser.add_argument("--result-json", type=Path, help="Optional output JSON summary path")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args()

    config = Segment5BConfig(
        data_root=args.data_root,
        upstream_manifest_fingerprint=args.manifest_fingerprint,
        parameter_hash=args.parameter_hash,
        seed=args.seed,
        run_id=args.run_id,
        dictionary_path=args.dictionary_path,
        validation_bundle_1a=args.validation_bundle_1a,
        validation_bundle_1b=args.validation_bundle_1b,
        validation_bundle_2a=args.validation_bundle_2a,
        validation_bundle_2b=args.validation_bundle_2b,
        validation_bundle_3a=args.validation_bundle_3a,
        validation_bundle_3b=args.validation_bundle_3b,
        validation_bundle_5a=args.validation_bundle_5a,
        run_s1=not args.no_s1,
        run_s2=not args.no_s2,
        run_s3=not args.no_s3,
        run_s4=not args.no_s4,
        run_s5=not args.no_s5,
    )

    orchestrator = Segment5BOrchestrator()
    result = orchestrator.run(config)
    _print_summary(result)

    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, default=str, indent=2), encoding="utf-8")
        logger.info("Segment5B CLI: wrote summary to %s", args.result_json)


if __name__ == "__main__":
    main()
