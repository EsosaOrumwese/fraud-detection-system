"""CLI runner for Segment 1B (S0 -> S3)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Optional

import yaml

from engine.layers.l1.seg_1B import (
    S2TileWeightsValidator,
    S2ValidatorConfig,
    S3RequirementsValidator,
    S3ValidatorConfig,
)
from engine.scenario_runner.l1_seg_1B import Segment1BConfig, Segment1BOrchestrator


def _load_dictionary(path: Optional[Path]) -> Optional[Mapping[str, object]]:
    if path is None:
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise ValueError("dictionary YAML must decode to a mapping")
    return payload  # type: ignore[return-value]


def _command_run(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    orchestrator = Segment1BOrchestrator()
    result = orchestrator.run(
        Segment1BConfig(
            data_root=args.data_root,
            parameter_hash=args.parameter_hash,
            dictionary=dictionary,
            basis=args.basis,
            dp=args.dp,
            manifest_fingerprint=args.manifest_fingerprint,
            seed=args.seed,
            notes=args.notes,
            validation_bundle_path=args.validation_bundle,
            skip_s0=args.skip_s0,
        )
    )

    summary = {
        "s0_receipt": str(result.s0_receipt_path) if result.s0_receipt_path else None,
        "s1": {
            "tile_index_path": str(result.s1.tile_index_path),
            "tile_bounds_path": str(result.s1.tile_bounds_path),
            "report_path": str(result.s1.report_path),
        },
        "s2": {
            "tile_weights_path": str(result.s2.tile_weights_path),
            "report_path": str(result.s2.report_path),
            "country_summary_path": str(result.s2.country_summary_path),
        },
        "s3": {
            "requirements_path": str(result.s3.requirements_path),
            "report_path": str(result.s3.report_path),
            "determinism_receipt": result.s3.determinism_receipt,
            "rows_emitted": result.s3.rows_emitted,
            "merchants_total": result.s3.merchants_total,
            "countries_total": result.s3.countries_total,
            "source_rows_total": result.s3.source_rows_total,
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _command_validate(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    validator = S2TileWeightsValidator()
    validator.validate(
        S2ValidatorConfig(
            data_root=args.data_root,
            parameter_hash=args.parameter_hash,
            dictionary=dictionary,
            run_report_path=args.run_report,
            basis=args.basis,
            dp=args.dp,
        )
    )
    print("Validation succeeded")
    return 0


def _command_validate_s3(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    validator = S3RequirementsValidator()
    validator.validate(
        S3ValidatorConfig(
            data_root=args.data_root,
            seed=args.seed,
            manifest_fingerprint=args.manifest_fingerprint,
            parameter_hash=args.parameter_hash,
            dictionary=dictionary,
            run_report_path=args.run_report,
        )
    )
    print("Validation succeeded")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Segment 1B utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute Segment 1B states S0-S3")
    run_parser.add_argument("--data-root", type=Path, default=Path("."))
    run_parser.add_argument("--parameter-hash", required=True)
    run_parser.add_argument("--basis", choices=["uniform", "area_m2", "population"], default="uniform")
    run_parser.add_argument("--dp", type=int, default=2)
    run_parser.add_argument("--dictionary", type=Path)
    run_parser.add_argument("--manifest-fingerprint")
    run_parser.add_argument("--seed")
    run_parser.add_argument("--validation-bundle", type=Path)
    run_parser.add_argument("--notes")
    run_parser.add_argument("--skip-s0", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate tile_weights output")
    validate_parser.add_argument("--data-root", type=Path, default=Path("."))
    validate_parser.add_argument("--parameter-hash", required=True)
    validate_parser.add_argument("--dictionary", type=Path)
    validate_parser.add_argument("--basis")
    validate_parser.add_argument("--dp", type=int)
    validate_parser.add_argument("--run-report", type=Path)

    validate_s3_parser = subparsers.add_parser("validate-s3", help="Validate s3_requirements output")
    validate_s3_parser.add_argument("--data-root", type=Path, default=Path("."))
    validate_s3_parser.add_argument("--parameter-hash", required=True)
    validate_s3_parser.add_argument("--seed", required=True)
    validate_s3_parser.add_argument("--manifest-fingerprint", required=True)
    validate_s3_parser.add_argument("--dictionary", type=Path)
    validate_s3_parser.add_argument("--run-report", type=Path)

    args = parser.parse_args(argv)

    if args.command == "run":
        return _command_run(args)
    if args.command == "validate":
        return _command_validate(args)
    if args.command == "validate-s3":
        return _command_validate_s3(args)

    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
