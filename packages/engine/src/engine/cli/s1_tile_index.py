"""Command-line entry point for Segment 1B S1 (Tile Index)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.layers.l1.seg_1B.s1_tile_index import (
    RunnerConfig,
    S1TileIndexRunner,
    S1TileIndexValidator,
    ValidatorConfig,
)
from engine.layers.l1.seg_1B.shared.dictionary import load_dictionary


def _load_dictionary(path: str | None):
    if path is None:
        return None
    return load_dictionary(Path(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Segment 1B S1 Tile Index utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Materialise tile_index/tile_bounds for a parameter hash")
    run_parser.add_argument("--data-root", type=Path, default=Path("."), help="Root directory containing sealed inputs")
    run_parser.add_argument("--parameter-hash", required=True, help="Parameter hash identifying the partition")
    run_parser.add_argument(
        "--inclusion-rule",
        choices=["center", "any_overlap"],
        default="center",
        help="Inclusion predicate used to enumerate eligible tiles",
    )
    run_parser.add_argument(
        "--dictionary",
        type=str,
        default=None,
        help="Optional path to an alternate Segment 1B dictionary YAML",
    )

    validate_parser = subparsers.add_parser("validate", help="Validate an existing tile_index partition")
    validate_parser.add_argument("--data-root", type=Path, default=Path("."), help="Root directory containing outputs")
    validate_parser.add_argument("--parameter-hash", required=True, help="Parameter hash identifying the partition")
    validate_parser.add_argument(
        "--inclusion-rule",
        choices=["center", "any_overlap"],
        default=None,
        help="Override inclusion predicate when the run report is absent",
    )
    validate_parser.add_argument(
        "--dictionary",
        type=str,
        default=None,
        help="Optional path to an alternate Segment 1B dictionary YAML",
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        dictionary = _load_dictionary(args.dictionary)
        runner = S1TileIndexRunner()
        result = runner.run(
            RunnerConfig(
                data_root=args.data_root,
                parameter_hash=args.parameter_hash,
                inclusion_rule=args.inclusion_rule,
                dictionary=dictionary,
            )
        )
        print(f"tile_index written to: {result.tile_index_path}")
        print(f"tile_bounds written to: {result.tile_bounds_path}")
        print(f"run report: {result.report_path}")
        return 0

    if args.command == "validate":
        dictionary = _load_dictionary(args.dictionary)
        validator = S1TileIndexValidator()
        validator.validate(
            ValidatorConfig(
                data_root=args.data_root,
                parameter_hash=args.parameter_hash,
                inclusion_rule=args.inclusion_rule,
                dictionary=dictionary,
            )
        )
        print("Validation succeeded")
        return 0

    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
