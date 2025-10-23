"""CLI runner for Segment 1B (S0 -> S9)."""

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
    S4AllocPlanValidator,
    S4ValidatorConfig,
    S5SiteTileAssignmentValidator,
    S5ValidatorConfig,
    S6SiteJitterValidator,
    S6ValidatorConfig,
    S7SiteSynthesisValidator,
    S7ValidatorConfig,
    S8SiteLocationsValidator,
    S8ValidatorConfig,
    S9ValidationRunner,
    S9RunnerConfig,
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
        "s4": {
            "alloc_plan_path": str(result.s4.alloc_plan_path),
            "report_path": str(result.s4.report_path),
            "determinism_receipt": result.s4.determinism_receipt,
            "rows_emitted": result.s4.rows_emitted,
            "merchants_total": result.s4.merchants_total,
            "pairs_total": result.s4.pairs_total,
            "shortfall_total": result.s4.shortfall_total,
            "ties_broken_total": result.s4.ties_broken_total,
            "alloc_sum_equals_requirements": result.s4.alloc_sum_equals_requirements,
        },
        "s5": {
            "dataset_path": str(result.s5.dataset_path),
            "run_report_path": str(result.s5.run_report_path),
            "rng_log_path": str(result.s5.rng_log_path),
            "determinism_receipt": result.s5.determinism_receipt,
            "rows_emitted": result.s5.rows_emitted,
            "pairs_total": result.s5.pairs_total,
            "rng_events_emitted": result.s5.rng_events_emitted,
            "run_id": result.s5.run_id,
        },
        "s6": {
            "dataset_path": str(result.s6.dataset_path),
            "run_report_path": str(result.s6.run_report_path),
            "rng_log_path": str(result.s6.rng_log_path),
            "rng_audit_log_path": str(result.s6.rng_audit_log_path),
            "rng_trace_log_path": str(result.s6.rng_trace_log_path),
            "determinism_receipt": result.s6.determinism_receipt,
            "rows_emitted": result.s6.rows_emitted,
            "rng_events_total": result.s6.rng_events_total,
            "counter_span": result.s6.counter_span,
            "run_id": result.s6.run_id,
        },
        "s7": {
            "dataset_path": str(result.s7.dataset_path),
            "run_summary_path": str(result.s7.run_summary_path),
            "determinism_receipt": result.s7.determinism_receipt,
            "run_id": result.s7.run_id,
        },
        "s8": {
            "dataset_path": str(result.s8.dataset_path),
            "run_summary_path": str(result.s8.run_summary_path),
            "determinism_receipt": result.s8.determinism_receipt,
            "run_id": result.s8.run_id,
        },
        "s9": {
            "bundle_path": str(result.s9.bundle_path),
            "flag_path": str(result.s9.flag_path) if result.s9.flag_path else None,
            "stage_log_path": str(result.s9.stage_log_path),
            "passed": result.s9.result.passed,
            "failure_codes": [failure.code for failure in result.s9.result.failures],
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


def _command_validate_s4(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    validator = S4AllocPlanValidator()
    validator.validate(
        S4ValidatorConfig(
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


def _command_validate_s5(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    validator = S5SiteTileAssignmentValidator()
    validator.validate(
        S5ValidatorConfig(
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


def _command_validate_s6(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    validator = S6SiteJitterValidator()
    validator.validate(
        S6ValidatorConfig(
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


def _command_validate_s7(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    validator = S7SiteSynthesisValidator()
    validator.validate(
        S7ValidatorConfig(
            data_root=args.data_root,
            seed=args.seed,
            manifest_fingerprint=args.manifest_fingerprint,
            parameter_hash=args.parameter_hash,
            dictionary=dictionary,
            run_summary_path=args.run_summary,
        )
    )
    print("Validation succeeded")
    return 0


def _command_validate_s8(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    validator = S8SiteLocationsValidator()
    validator.validate(
        S8ValidatorConfig(
            data_root=args.data_root,
            seed=args.seed,
            manifest_fingerprint=args.manifest_fingerprint,
            parameter_hash=args.parameter_hash,
            dictionary=dictionary,
            run_summary_path=args.run_summary,
        )
    )
    print("Validation succeeded")
    return 0


def _command_validate_s9(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    runner = S9ValidationRunner()
    outcome = runner.run(
        S9RunnerConfig(
            base_path=args.data_root,
            seed=int(args.seed),
            parameter_hash=args.parameter_hash,
            manifest_fingerprint=args.manifest_fingerprint,
            run_id=args.run_id,
            dictionary=dictionary,
        )
    )

    payload = {
        "bundle_path": str(outcome.bundle_path),
        "flag_path": str(outcome.flag_path) if outcome.flag_path else None,
        "stage_log_path": str(outcome.stage_log_path),
        "passed": outcome.result.passed,
        "failure_codes": [failure.code for failure in outcome.result.failures],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if outcome.result.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Segment 1B utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute Segment 1B states S0-S9")
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

    validate_s4_parser = subparsers.add_parser("validate-s4", help="Validate s4_alloc_plan output")
    validate_s4_parser.add_argument("--data-root", type=Path, default=Path("."))
    validate_s4_parser.add_argument("--parameter-hash", required=True)
    validate_s4_parser.add_argument("--seed", required=True)
    validate_s4_parser.add_argument("--manifest-fingerprint", required=True)
    validate_s4_parser.add_argument("--dictionary", type=Path)
    validate_s4_parser.add_argument("--run-report", type=Path)

    validate_s5_parser = subparsers.add_parser("validate-s5", help="Validate s5_site_tile_assignment output")
    validate_s5_parser.add_argument("--data-root", type=Path, default=Path("."))
    validate_s5_parser.add_argument("--parameter-hash", required=True)
    validate_s5_parser.add_argument("--seed", required=True)
    validate_s5_parser.add_argument("--manifest-fingerprint", required=True)
    validate_s5_parser.add_argument("--dictionary", type=Path)
    validate_s5_parser.add_argument("--run-report", type=Path)

    validate_s6_parser = subparsers.add_parser("validate-s6", help="Validate s6_site_jitter output")
    validate_s6_parser.add_argument("--data-root", type=Path, default=Path("."))
    validate_s6_parser.add_argument("--parameter-hash", required=True)
    validate_s6_parser.add_argument("--seed", required=True)
    validate_s6_parser.add_argument("--manifest-fingerprint", required=True)
    validate_s6_parser.add_argument("--dictionary", type=Path)
    validate_s6_parser.add_argument("--run-report", type=Path)

    validate_s7_parser = subparsers.add_parser("validate-s7", help="Validate s7_site_synthesis output")
    validate_s7_parser.add_argument("--data-root", type=Path, default=Path("."))
    validate_s7_parser.add_argument("--parameter-hash", required=True)
    validate_s7_parser.add_argument("--seed", required=True)
    validate_s7_parser.add_argument("--manifest-fingerprint", required=True)
    validate_s7_parser.add_argument("--dictionary", type=Path)
    validate_s7_parser.add_argument("--run-summary", type=Path)

    validate_s8_parser = subparsers.add_parser("validate-s8", help="Validate site_locations egress")
    validate_s8_parser.add_argument("--data-root", type=Path, default=Path("."))
    validate_s8_parser.add_argument("--parameter-hash", required=True)
    validate_s8_parser.add_argument("--seed", required=True)
    validate_s8_parser.add_argument("--manifest-fingerprint", required=True)
    validate_s8_parser.add_argument("--dictionary", type=Path)
    validate_s8_parser.add_argument("--run-summary", type=Path)

    validate_s9_parser = subparsers.add_parser("validate-s9", help="Validate Segment 1B S9 validation bundle")
    validate_s9_parser.add_argument("--data-root", type=Path, default=Path("."))
    validate_s9_parser.add_argument("--parameter-hash", required=True)
    validate_s9_parser.add_argument("--seed", required=True)
    validate_s9_parser.add_argument("--manifest-fingerprint", required=True)
    validate_s9_parser.add_argument("--run-id", required=True)
    validate_s9_parser.add_argument("--dictionary", type=Path)

    args = parser.parse_args(argv)

    if args.command == "run":
        return _command_run(args)
    if args.command == "validate":
        return _command_validate(args)
    if args.command == "validate-s3":
        return _command_validate_s3(args)
    if args.command == "validate-s4":
        return _command_validate_s4(args)
    if args.command == "validate-s5":
        return _command_validate_s5(args)
    if args.command == "validate-s6":
        return _command_validate_s6(args)
    if args.command == "validate-s7":
        return _command_validate_s7(args)
    if args.command == "validate-s8":
        return _command_validate_s8(args)
    if args.command == "validate-s9":
        return _command_validate_s9(args)

    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
