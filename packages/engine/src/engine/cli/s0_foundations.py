"""CLI wrapper for running Layer-1 Segment 1A state-0 foundations.

The command mirrors the orchestrator API: point it at the sealed artefacts and
it will drive S0 to completion, optionally writing a small JSON blob so callers
can chain runs together.  This keeps ad-hoc experimentation and CI flows simple
without tying us to a heavy orchestration framework.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.layers.l1.seg_1A.s0_foundations import (
    S0FoundationsRunner,
    SchemaAuthority,
)
from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error


def _parse_parameter_files(values: list[str]) -> dict[str, Path]:
    """Parse NAME=PATH pairs into a mapping ready for the runner."""
    mapping: dict[str, Path] = {}
    for item in values:
        if "=" not in item:
            raise argparse.ArgumentTypeError(
                f"parameter specification '{item}' must be NAME=PATH"
            )
        name, raw_path = item.split("=", 1)
        name = name.strip()
        if not name:
            raise argparse.ArgumentTypeError("parameter file name may not be empty")
        path = Path(raw_path).expanduser().resolve()
        mapping[name] = path
    return mapping


def _load_extra_manifest(values: list[str]) -> list[Path]:
    """Normalise extra manifest artefact paths supplied on the CLI."""
    extras: list[Path] = []
    for raw in values:
        extras.append(Path(raw).expanduser().resolve())
    return extras


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Layer-1 Segment 1A state-0 foundations over prepared artefacts.",
    )
    parser.add_argument("--output-dir", required=True, type=Path, help="Target base directory for parameter-scoped outputs and validation bundle.")
    parser.add_argument("--merchant-table", required=True, type=Path, help="Path to the merchant ingress parquet table.")
    parser.add_argument("--iso-table", required=True, type=Path, help="Path to the canonical ISO parquet table.")
    parser.add_argument("--gdp-table", required=True, type=Path, help="Path to the GDP parquet table (obs-year 2024).")
    parser.add_argument("--bucket-table", required=True, type=Path, help="Path to the GDP bucket parquet table (Jenks-5).")
    parser.add_argument(
        "--param",
        dest="parameter_files",
        action="append",
        default=[],
        help="Parameter artefacts in NAME=PATH form (repeat per file).",
    )
    parser.add_argument(
        "--git-commit",
        required=True,
        help="Git commit SHA the run should record as lineage.",
    )
    parser.add_argument("--seed", type=int, required=True, help="Philox master seed (uint64).")
    parser.add_argument(
        "--numeric-policy",
        dest="numeric_policy_path",
        type=Path,
        help="Optional numeric_policy.json path.",
    )
    parser.add_argument(
        "--math-profile",
        dest="math_profile_manifest_path",
        type=Path,
        help="Optional math_profile_manifest.json path.",
    )
    parser.add_argument(
        "--extra-manifest",
        dest="extra_manifest",
        action="append",
        default=[],
        help="Additional artefacts to include in the manifest fingerprint (repeat per path).",
    )
    parser.add_argument(
        "--no-validate",
        dest="validate",
        action="store_false",
        help="Skip re-opening outputs for validation.",
    )
    parser.add_argument(
        "--context-json",
        dest="context_json",
        type=Path,
        help="Optional JSON file that captures the resolved context for downstream tooling.",
    )

    args = parser.parse_args(argv)

    parameter_files = _parse_parameter_files(args.parameter_files)
    extra_manifest = _load_extra_manifest(args.extra_manifest)

    authority = SchemaAuthority(
        ingress_ref="layer1/schemas.ingress.layer1.yaml#/merchant_ids",
        segment_ref="layer1/schemas.1A.yaml",
        rng_ref="layer1/schemas.layer1.yaml",
    )
    runner = S0FoundationsRunner(schema_authority=authority)

    try:
        result = runner.run_from_paths(
            base_path=args.output_dir.expanduser().resolve(),
            merchant_table_path=args.merchant_table.expanduser().resolve(),
            iso_table_path=args.iso_table.expanduser().resolve(),
            gdp_table_path=args.gdp_table.expanduser().resolve(),
            bucket_table_path=args.bucket_table.expanduser().resolve(),
            parameter_files=parameter_files,
            git_commit_hex=args.git_commit,
            seed=args.seed,
            numeric_policy_path=(
                args.numeric_policy_path.expanduser().resolve()
                if args.numeric_policy_path
                else None
            ),
            math_profile_manifest_path=(
                args.math_profile_manifest_path.expanduser().resolve()
                if args.math_profile_manifest_path
                else None
            ),
            validate=args.validate,
            extra_manifest_artifacts=extra_manifest,
        )
    except S0Error as exc:
        print(f"[s0-run] failed: {exc}", file=sys.stderr)
        return 1

    if args.context_json:
        payload = {
            "run_id": result.run_id,
            "parameter_hash": result.sealed.parameter_hash.parameter_hash,
            "manifest_fingerprint": result.sealed.manifest_fingerprint.manifest_fingerprint,
            "output_dir": str(result.base_path),
            "seed": args.seed,
        }
        args.context_json.expanduser().resolve().write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
