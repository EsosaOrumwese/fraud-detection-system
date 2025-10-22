"""CLI entry point for Segment 1B S2 (Tile Weights)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.layers.l1.seg_1B.s2_tile_weights import (
    RunnerConfig,
    S2RunResult,
    S2TileWeightsRunner,
    S2TileWeightsValidator,
    ValidatorConfig,
)
from engine.layers.l1.seg_1B.shared.dictionary import load_dictionary


def _load_dictionary(path: str | None):
    if path is None:
        return None
    return load_dictionary(Path(path))


def _materialise(args: argparse.Namespace) -> S2RunResult:
    dictionary = _load_dictionary(args.dictionary)
    runner = S2TileWeightsRunner()
    prepared = runner.prepare(
        RunnerConfig(
            data_root=args.data_root,
            parameter_hash=args.parameter_hash,
            basis=args.basis,
            dp=args.dp,
            dictionary=dictionary,
        )
    )
    masses = runner.compute_masses(prepared)
    runner.measure_baselines(prepared, measure_raster=prepared.governed.basis == "population")
    quantised = runner.quantise(prepared, masses)
    return runner.materialise(prepared, quantised)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Segment 1B S2 Tile Weights utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Materialise tile_weights for a parameter hash")
    run_parser.add_argument("--data-root", type=Path, default=Path("."), help="Root directory containing sealed inputs")
    run_parser.add_argument("--parameter-hash", required=True, help="Parameter hash identifying the partition")
    run_parser.add_argument(
        "--basis",
        choices=["uniform", "area_m2", "population"],
        default="uniform",
        help="Governed mass basis used to compute tile weights",
    )
    run_parser.add_argument("--dp", type=int, default=2, help="Fixed-decimal precision for integerisation")
    run_parser.add_argument(
        "--dictionary",
        type=str,
        default=None,
        help="Optional path to an alternate Segment 1B dictionary YAML",
    )

    validate_parser = subparsers.add_parser("validate", help="Validate a tile_weights partition")
    validate_parser.add_argument("--data-root", type=Path, default=Path("."), help="Root directory containing outputs")
    validate_parser.add_argument("--parameter-hash", required=True, help="Parameter hash identifying the partition")
    validate_parser.add_argument("--basis", type=str, default=None, help="Override basis when run report absent")
    validate_parser.add_argument("--dp", type=int, default=None, help="Override dp when run report absent")
    validate_parser.add_argument(
        "--run-report",
        type=Path,
        default=None,
        help="Explicit path to an existing S2 run report",
    )
    validate_parser.add_argument(
        "--dictionary",
        type=str,
        default=None,
        help="Optional path to an alternate Segment 1B dictionary YAML",
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        result = _materialise(args)
        print(f"tile_weights written to: {result.tile_weights_path}")
        print(f"run report: {result.report_path}")
        print(f"country summaries: {result.country_summary_path}")
        return 0

    if args.command == "validate":
        dictionary = _load_dictionary(args.dictionary)
        validator = S2TileWeightsValidator()
        validator.validate(
            ValidatorConfig(
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

    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
