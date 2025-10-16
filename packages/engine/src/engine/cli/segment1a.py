"""CLI runner for Segment 1A (S0 foundations – S5 currency weights)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error
from engine.scenario_runner.l1_seg_1A import Segment1AOrchestrator

logger = logging.getLogger(__name__)


def _parse_parameter_files(values: List[str]) -> Dict[str, Path]:
    mapping: Dict[str, Path] = {}
    for item in values:
        if "=" not in item:
            raise argparse.ArgumentTypeError(
                f"parameter specification '{item}' must be NAME=PATH"
            )
        name, raw_path = item.split("=", 1)
        name = name.strip()
        if not name:
            raise argparse.ArgumentTypeError("parameter file name may not be empty")
        mapping[name] = Path(raw_path).expanduser().resolve()
    return mapping


def _normalise_paths(values: List[str]) -> List[Path]:
    return [Path(raw).expanduser().resolve() for raw in values]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Segment 1A states S0–S1–S2–S3 over prepared artefacts.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Base directory for parameter-scoped outputs and validation bundles.",
    )
    parser.add_argument(
        "--merchant-table",
        required=True,
        type=Path,
        help="Path to the merchant ingress parquet table.",
    )
    parser.add_argument(
        "--iso-table",
        required=True,
        type=Path,
        help="Path to the canonical ISO parquet table.",
    )
    parser.add_argument(
        "--gdp-table",
        required=True,
        type=Path,
        help="Path to the GDP parquet table (obs-year 2024).",
    )
    parser.add_argument(
        "--bucket-table",
        required=True,
        type=Path,
        help="Path to the GDP bucket parquet table (Jenks-5).",
    )
    parser.add_argument(
        "--param",
        dest="parameter_files",
        action="append",
        default=[],
        help=(
            "Parameter artefacts in NAME=PATH form (repeat per file, "
            "e.g. policy.s3.rule_ladder.yaml)."
        ),
    )
    parser.add_argument(
        "--git-commit",
        required=True,
        help="Git commit SHA the run should record as lineage.",
    )
    parser.add_argument(
        "--seed", type=int, required=True, help="Philox master seed (uint64)."
    )
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
        "--validation-policy",
        required=True,
        type=Path,
        help=(
            "Path to validation policy YAML for S2 corridors "
            "(e.g. contracts/policies/l1/seg_1A/s2_validation_policy.yaml)."
        ),
    )
    parser.add_argument(
        "--extra-manifest",
        dest="extra_manifest",
        action="append",
        default=[],
        help=(
            "Additional artefacts to include when computing the manifest "
            "fingerprint (repeat per path)."
        ),
    )
    parser.add_argument(
        "--no-validate-s0",
        dest="validate_s0",
        action="store_false",
        help="Skip S0 validation.",
    )
    parser.add_argument(
        "--no-validate-s1",
        dest="validate_s1",
        action="store_false",
        help="Skip S1 validation.",
    )
    parser.add_argument(
        "--no-validate-s2",
        dest="validate_s2",
        action="store_false",
        help="Skip S2 validation.",
    )
    parser.add_argument(
        "--no-validate-s3",
        dest="validate_s3",
        action="store_false",
        help="Skip S3 validation.",
    )
    parser.add_argument(
        "--no-diagnostics",
        dest="include_diagnostics",
        action="store_false",
        help="Disable optional diagnostic outputs from S0.",
    )
    parser.add_argument(
        "--s3-priors",
        dest="s3_priors",
        action="store_true",
        help="Enable base-weight priors (requires policy.s3.base_weight.yaml).",
    )
    parser.add_argument(
        "--s3-integerisation",
        dest="s3_integerisation",
        action="store_true",
        help="Enable deterministic integerisation of S3 candidates.",
    )
    parser.add_argument(
        "--s3-sequencing",
        dest="s3_sequencing",
        action="store_true",
        help="Enable S3 site sequencing (requires integerisation).",
    )
    parser.add_argument(
        "--s4-features",
        dest="s4_features",
        type=Path,
        help="Optional parquet providing X feature values for S4 (defaults to policy value).",
    )
    parser.add_argument(
        "--no-validate-s4",
        dest="validate_s4",
        action="store_false",
        help="Skip S4 validation.",
    )
    parser.add_argument(
        "--s4-validation-output",
        dest="s4_validation_output",
        type=Path,
        help="Optional directory for S4 validation artefacts.",
    )
    parser.add_argument(
        "--result-json",
        dest="result_json",
        type=Path,
        help="Optional JSON file to persist the combined run summary.",
    )

    parser.set_defaults(
        validate_s0=True,
        validate_s1=True,
        validate_s2=True,
        validate_s3=True,
        include_diagnostics=True,
    )

    args = parser.parse_args(argv)

    parameter_files = _parse_parameter_files(args.parameter_files)
    extra_manifest = _normalise_paths(args.extra_manifest)
    validation_policy_path = args.validation_policy.expanduser().resolve()

    orchestrator = Segment1AOrchestrator()

    logger.info(
        "Segment1A CLI: run initialised (seed=%d, output_dir=%s)",
        args.seed,
        args.output_dir,
    )

    try:
        result = orchestrator.run(
            base_path=args.output_dir.expanduser().resolve(),
            merchant_table=args.merchant_table.expanduser().resolve(),
            iso_table=args.iso_table.expanduser().resolve(),
            gdp_table=args.gdp_table.expanduser().resolve(),
            bucket_table=args.bucket_table.expanduser().resolve(),
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
            include_diagnostics=args.include_diagnostics,
            validate_s0=args.validate_s0,
            validate_s1=args.validate_s1,
            validate_s2=args.validate_s2,
            validate_s3=args.validate_s3,
            extra_manifest_artifacts=extra_manifest,
            validation_policy_path=validation_policy_path,
            s3_priors=args.s3_priors,
            s3_integerisation=args.s3_integerisation,
            s3_sequencing=args.s3_sequencing,
            s4_features=args.s4_features,
            validate_s4=args.validate_s4,
            s4_validation_output=(
                args.s4_validation_output.expanduser().resolve()
                if args.s4_validation_output is not None
                else None
            ),
        )
    except S0Error as exc:
        logger.exception("Segment1A CLI: run failed")
        print(f"[segment1a-run] failed: {exc}", file=sys.stderr)
        return 1

    logger.info(
        "Segment1A CLI: run completed (run_id=%s, accepted_merchants=%d, s3_merchants=%d, s4_merchants=%d)",
        result.s2_result.deterministic.run_id,
        len(result.nb_context.finals),
        len(result.s3_context.deterministic.merchants),
        len(result.s4_context.deterministic.merchants),
    )
    logger.info(
        "Segment1A CLI: S3 candidate set %s", result.s3_context.candidate_set_path
    )
    if result.s3_context.base_weight_priors_path:
        logger.info(
            "Segment1A CLI: S3 priors %s", result.s3_context.base_weight_priors_path
        )
    if result.s3_context.integerised_counts_path:
        logger.info(
            "Segment1A CLI: S3 counts %s", result.s3_context.integerised_counts_path
        )
    if result.s3_context.site_sequence_path:
        logger.info(
            "Segment1A CLI: S3 sequence %s", result.s3_context.site_sequence_path
        )
    if result.s3_context.metrics:
        logger.info("Segment1A CLI: S3 metrics %s", result.s3_context.metrics)
    if result.s3_context.validation_passed is not None:
        if result.s3_context.validation_passed:
            logger.info("Segment1A CLI: S3 validation PASS")
        else:
            logger.warning("Segment1A CLI: S3 validation FAIL")
            if result.s3_context.validation_failed_merchants:
                logger.warning(
                    "Segment1A CLI: S3 failed merchants %s",
                    result.s3_context.validation_failed_merchants,
                )
    if result.s3_context.validation_artifacts_path:
        logger.info(
            "Segment1A CLI: S3 validation artefacts %s",
            result.s3_context.validation_artifacts_path,
        )
    logger.info("Segment1A CLI: S4 poisson events %s", result.s4_context.poisson_events_path)
    if result.s4_context.metrics:
        logger.info("Segment1A CLI: S4 metrics %s", result.s4_context.metrics)
    if result.s4_context.validation_passed is not None:
        if result.s4_context.validation_passed:
            logger.info("Segment1A CLI: S4 validation PASS")
        else:
            logger.warning("Segment1A CLI: S4 validation FAIL")
    if result.s4_context.validation_artifacts_path:
        logger.info("Segment1A CLI: S4 validation artefacts %s", result.s4_context.validation_artifacts_path)
    if result.nb_context.metrics:
        logger.info("Segment1A CLI: S2 metrics %s", result.nb_context.metrics)

    s5_ctx = result.s5_context
    logger.info("Segment1A CLI: S5 weights %s", s5_ctx.weights_path)
    if s5_ctx.sparse_flag_path:
        logger.info("Segment1A CLI: S5 sparse flag %s", s5_ctx.sparse_flag_path)
    if s5_ctx.merchant_currency_path:
        logger.info(
            "Segment1A CLI: S5 merchant currency %s",
            s5_ctx.merchant_currency_path,
        )
    if s5_ctx.stage_log_path:
        logger.info("Segment1A CLI: S5 stage log %s", s5_ctx.stage_log_path)
    logger.info(
        "Segment1A CLI: S5 receipt %s (policy_digest=%s)",
        s5_ctx.receipt_path,
        s5_ctx.policy_digest,
    )

    if args.result_json:
        catalogue_path = (
            args.output_dir.expanduser().resolve()
            / "parameter_scoped"
            / f"parameter_hash={result.s2_result.deterministic.parameter_hash}"
            / "s2_nb_catalogue.json"
        )
        summary = {
            "seed": args.seed,
            "output_dir": str(args.output_dir.expanduser().resolve()),
            "s0": {
                "run_id": result.s0_result.run_id,
                "parameter_hash": result.s0_result.sealed.parameter_hash.parameter_hash,
                "manifest_fingerprint": result.s0_result.sealed.manifest_fingerprint.manifest_fingerprint,
            },
            "s1": {
                "run_id": result.s1_result.run_id,
                "events_path": str(result.s1_result.events_path),
                "trace_path": str(result.s1_result.trace_path),
                "catalogue_path": str(result.hurdle_context.catalogue_path),
                "multi_merchant_ids": list(result.hurdle_context.multi_merchant_ids),
            },
            "s2": {
                "accepted_merchants": len(result.nb_context.finals),
                "nb_final_path": str(result.nb_context.final_events_path),
                "gamma_path": str(result.nb_context.gamma_events_path),
                "poisson_path": str(result.nb_context.poisson_events_path),
                "trace_path": str(result.nb_context.trace_path),
                "catalogue_path": str(catalogue_path),
                "validation_artifacts_path": (
                    str(result.nb_context.validation_artifacts_path)
                    if result.nb_context.validation_artifacts_path is not None
                    else None
                ),
                "metrics": result.nb_context.metrics,
            },
            "s3": {
                "candidate_set_path": str(result.s3_context.candidate_set_path),
                "merchants": len(result.s3_context.deterministic.merchants),
                "parameter_hash": result.s3_context.parameter_hash,
                "manifest_fingerprint": result.s3_context.manifest_fingerprint,
                "base_weight_priors_path": (
                    str(result.s3_context.base_weight_priors_path)
                    if result.s3_context.base_weight_priors_path is not None
                    else None
                ),
                "integerised_counts_path": (
                    str(result.s3_context.integerised_counts_path)
                    if result.s3_context.integerised_counts_path is not None
                    else None
                ),
                "site_sequence_path": (
                    str(result.s3_context.site_sequence_path)
                    if result.s3_context.site_sequence_path is not None
                    else None
                ),
                "metrics": result.s3_context.metrics,
                "validation_passed": result.s3_context.validation_passed,
                "validation_failed_merchants": (
                    dict(result.s3_context.validation_failed_merchants)
                    if result.s3_context.validation_failed_merchants is not None
                    else None
                ),
                "validation_artifacts_path": (
                    str(result.s3_context.validation_artifacts_path)
                    if result.s3_context.validation_artifacts_path is not None
                    else None
                ),
                "toggles": {
                    "priors": args.s3_priors,
                    "integerisation": args.s3_integerisation,
                    "sequencing": args.s3_sequencing,
                },
                "validation_enabled": args.validate_s3,
            },
            "s4": {
                "merchants": len(result.s4_context.deterministic.merchants),
                "poisson_path": str(result.s4_context.poisson_events_path),
                "rejection_path": str(result.s4_context.rejection_events_path),
                "retry_exhausted_path": str(result.s4_context.retry_exhausted_events_path),
                "final_path": str(result.s4_context.final_events_path),
                "trace_path": str(result.s4_context.trace_path),
                "metrics": result.s4_context.metrics,
                "validation_passed": result.s4_context.validation_passed,
                "validation_artifacts_path": (
                    str(result.s4_context.validation_artifacts_path)
                    if result.s4_context.validation_artifacts_path is not None
                    else None
                ),
                "validation_enabled": args.validate_s4,
                "features_path": (
                    str(args.s4_features.expanduser().resolve())
                    if args.s4_features is not None
                    else None
                ),
            },
            "s5": {
                "weights_path": str(s5_ctx.weights_path),
                "sparse_flag_path": (
                    str(s5_ctx.sparse_flag_path)
                    if s5_ctx.sparse_flag_path is not None
                    else None
                ),
                "merchant_currency_path": (
                    str(s5_ctx.merchant_currency_path)
                    if s5_ctx.merchant_currency_path is not None
                    else None
                ),
                "stage_log_path": (
                    str(s5_ctx.stage_log_path)
                    if s5_ctx.stage_log_path is not None
                    else None
                ),
                "receipt_path": str(s5_ctx.receipt_path),
                "policy_digest": s5_ctx.policy_digest,
                "policy_path": str(s5_ctx.policy_path),
                "policy_semver": s5_ctx.policy_semver,
                "policy_version": s5_ctx.policy_version,
            },
            "s6": {
                "events_path": (
                    str(result.s6_context.events_path)
                    if result.s6_context.events_path is not None
                    else None
                ),
                "trace_path": (
                    str(result.s6_context.trace_path)
                    if result.s6_context.trace_path is not None
                    else None
                ),
                "membership_path": (
                    str(result.s6_context.membership_path)
                    if result.s6_context.membership_path is not None
                    else None
                ),
                "policy_path": str(result.s6_context.policy_path),
                "policy_digest": result.s6_context.policy_digest,
                "policy_semver": result.s6_context.policy_semver,
                "policy_version": result.s6_context.policy_version,
                "events_expected": result.s6_context.events_expected,
                "events_written": result.s6_context.events_written,
                "shortfall_count": result.s6_context.shortfall_count,
                "reason_code_counts": dict(result.s6_context.reason_code_counts),
            },
        }
        args.result_json.expanduser().resolve().write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        logger.info("Segment1A CLI: wrote result summary to %s", args.result_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
