"""CLI runner for Segment 2B (S0 gate)."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from engine.scenario_runner import Segment2BConfig, Segment2BOrchestrator, Segment2BResult

logger = logging.getLogger(__name__)


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
    except Exception:
        return default


def _print_summary(result: Segment2BResult) -> None:
    payload = {
        "manifest_fingerprint": result.manifest_fingerprint,
        "seg2a_manifest_fingerprint": result.seg2a_manifest_fingerprint,
        "parameter_hash": result.parameter_hash,
        "receipt_path": str(result.receipt_path),
        "inventory_path": str(result.inventory_path),
        "flag_sha256_hex": result.flag_sha256_hex,
        "verified_at_utc": result.verified_at_utc,
    }
    if result.s1_output_path:
        payload["s1_output_path"] = str(result.s1_output_path)
        payload["s1_run_report_path"] = str(result.s1_run_report_path)
        payload["s1_resumed"] = result.s1_resumed
    if result.s2_index_path:
        payload["s2_index_path"] = str(result.s2_index_path)
        payload["s2_blob_path"] = str(result.s2_blob_path)
        payload["s2_run_report_path"] = str(result.s2_run_report_path)
        payload["s2_resumed"] = result.s2_resumed
    if result.s3_output_path:
        payload["s3_output_path"] = str(result.s3_output_path)
        payload["s3_run_report_path"] = str(result.s3_run_report_path)
        payload["s3_resumed"] = result.s3_resumed
    if result.s4_output_path:
        payload["s4_output_path"] = str(result.s4_output_path)
        payload["s4_run_report_path"] = str(result.s4_run_report_path)
        payload["s4_resumed"] = result.s4_resumed
    if result.s5_run_id:
        payload["s5_run_id"] = result.s5_run_id
        if result.s5_rng_event_group_path:
            payload["s5_rng_event_group_path"] = str(result.s5_rng_event_group_path)
        if result.s5_rng_event_site_path:
            payload["s5_rng_event_site_path"] = str(result.s5_rng_event_site_path)
        if result.s5_rng_trace_log_path:
            payload["s5_rng_trace_log_path"] = str(result.s5_rng_trace_log_path)
        if result.s5_rng_audit_log_path:
            payload["s5_rng_audit_log_path"] = str(result.s5_rng_audit_log_path)
        if result.s5_selection_log_paths:
            payload["s5_selection_log_paths"] = [str(path) for path in result.s5_selection_log_paths]
        if result.s5_run_report_path:
            payload["s5_run_report_path"] = str(result.s5_run_report_path)
    if result.s6_run_id:
        payload["s6_run_id"] = result.s6_run_id
        if result.s6_rng_event_edge_path:
            payload["s6_rng_event_edge_path"] = str(result.s6_rng_event_edge_path)
        if result.s6_rng_trace_log_path:
            payload["s6_rng_trace_log_path"] = str(result.s6_rng_trace_log_path)
        if result.s6_rng_audit_log_path:
            payload["s6_rng_audit_log_path"] = str(result.s6_rng_audit_log_path)
        if result.s6_edge_log_paths:
            payload["s6_edge_log_paths"] = [str(path) for path in result.s6_edge_log_paths]
        if result.s6_run_report_path:
            payload["s6_run_report_path"] = str(result.s6_run_report_path)
    if result.s7_report_path:
        payload["s7_report_path"] = str(result.s7_report_path)
        if result.s7_validators:
            total = len(result.s7_validators)
            passed = sum(1 for item in result.s7_validators if item.get("status") == "PASS")
            payload["s7_validators_summary"] = {
                "path": str(result.s7_report_path),
                "total": total,
                "pass": passed,
                "fail": total - passed,
            }
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    parser = argparse.ArgumentParser(
        description="Run Segment 2B S0 gate for the routing engine.",
    )
    parser.add_argument(
        "--data-root",
        required=True,
        type=Path,
        help="Base directory where governed artefacts and outputs are stored.",
    )
    parser.add_argument(
        "--seed",
        required=True,
        type=int,
        help="Seed used when Segment 1B emitted site_locations.",
    )
    parser.add_argument(
        "--manifest-fingerprint",
        required=True,
        help="Manifest fingerprint produced by Segment 1B.",
    )
    parser.add_argument(
        "--seg2a-manifest-fingerprint",
        required=True,
        help="Manifest fingerprint produced by Segment 2A (civil-time inputs).",
    )
    parser.add_argument(
        "--parameter-hash",
        required=True,
        help="Parameter hash used to scope the routing run.",
    )
    parser.add_argument(
        "--git-commit-hex",
        type=str,
        help="Optional git commit hex recorded in the receipt (auto-detected if omitted).",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        help="Override path to the Segment 2B dataset dictionary.",
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
        "--pin-tz-assets",
        action="store_true",
        help="Pin site_timezones and tz_timetable_cache as optional dictionary assets.",
    )
    parser.add_argument(
        "--run-s1",
        action="store_true",
        help="Execute S1 weight freezing after the gate completes.",
    )
    parser.add_argument(
        "--s1-resume",
        action="store_true",
        help="Skip S1 execution when its output partition already exists.",
    )
    parser.add_argument(
        "--s1-quiet-run-report",
        action="store_true",
        help="Suppress printing the S1 run-report JSON to STDOUT (still writes to disk).",
    )
    parser.add_argument(
        "--run-s2",
        action="store_true",
        help="Execute S2 alias generation after S1 completes.",
    )
    parser.add_argument(
        "--s2-resume",
        action="store_true",
        help="Skip S2 execution when its output partition already exists.",
    )
    parser.add_argument(
        "--s2-quiet-run-report",
        action="store_true",
        help="Suppress printing the S2 run-report JSON to STDOUT (still writes to disk).",
    )
    parser.add_argument(
        "--run-s3",
        action="store_true",
        help="Execute S3 day-effects generation after S2 completes.",
    )
    parser.add_argument(
        "--s3-resume",
        action="store_true",
        help="Skip S3 execution when its output partition already exists.",
    )
    parser.add_argument(
        "--s3-quiet-run-report",
        action="store_true",
        help="Suppress printing the S3 run-report JSON to STDOUT (still writes to disk).",
    )
    parser.add_argument(
        "--run-s4",
        action="store_true",
        help="Execute S4 tz-group renormalisation after S3 completes.",
    )
    parser.add_argument(
        "--s4-resume",
        action="store_true",
        help="Skip S4 execution when its output partition already exists.",
    )
    parser.add_argument(
        "--s4-quiet-run-report",
        action="store_true",
        help="Suppress printing the S4 run-report JSON to STDOUT (still writes to disk).",
    )
    parser.add_argument(
        "--run-s5",
        action="store_true",
        help="Execute S5 router core after S4 completes.",
    )
    parser.add_argument(
        "--s5-selection-log",
        action="store_true",
        help="Emit the optional s5_selection_log dataset when routing.",
    )
    parser.add_argument(
        "--s5-arrivals-jsonl",
        type=Path,
        help="Path to a JSONL file containing arrivals (merchant_id, utc_timestamp).",
    )
    parser.add_argument(
        "--s5-quiet-run-report",
        action="store_true",
        help="Suppress printing the S5 run-report JSON to STDOUT (still writes to disk).",
    )
    parser.add_argument(
        "--run-s6",
        action="store_true",
        help="Execute S6 virtual-edge routing after S5 completes.",
    )
    parser.add_argument(
        "--s6-edge-log",
        action="store_true",
        help="Emit the optional s6_edge_log dataset for virtual arrivals.",
    )
    parser.add_argument(
        "--s6-quiet-run-report",
        action="store_true",
        help="Suppress printing the S6 run-report JSON to STDOUT (still writes to disk).",
    )
    parser.add_argument(
        "--run-s7",
        action="store_true",
        help="Execute the S7 audit gate after upstream states complete.",
    )
    parser.add_argument(
        "--s7-quiet-run-report",
        action="store_true",
        help="Suppress printing the S7 run-report JSON to STDOUT (still writes via S7).",
    )

    args = parser.parse_args(argv)

    git_commit_hex = args.git_commit_hex or _discover_git_commit()
    orchestrator = Segment2BOrchestrator()
    result = orchestrator.run(
        Segment2BConfig(
            data_root=args.data_root,
            seed=args.seed,
            manifest_fingerprint=args.manifest_fingerprint,
            seg2a_manifest_fingerprint=args.seg2a_manifest_fingerprint,
            parameter_hash=args.parameter_hash,
            git_commit_hex=git_commit_hex,
            dictionary_path=args.dictionary,
            validation_bundle_path=args.validation_bundle,
            notes=args.notes,
            pin_civil_time=args.pin_tz_assets,
            run_s1=args.run_s1,
            s1_resume=args.s1_resume,
            s1_emit_run_report_stdout=not args.s1_quiet_run_report,
            run_s2=args.run_s2,
            s2_resume=args.s2_resume,
            s2_emit_run_report_stdout=not args.s2_quiet_run_report,
            run_s3=args.run_s3,
            s3_resume=args.s3_resume,
            s3_emit_run_report_stdout=not args.s3_quiet_run_report,
            run_s4=args.run_s4,
            s4_resume=args.s4_resume,
            s4_emit_run_report_stdout=not args.s4_quiet_run_report,
            run_s5=args.run_s5,
            s5_emit_selection_log=args.s5_selection_log,
            s5_arrivals_path=args.s5_arrivals_jsonl,
            s5_emit_run_report_stdout=not args.s5_quiet_run_report,
            run_s6=args.run_s6,
            s6_emit_edge_log=args.s6_edge_log,
            s6_emit_run_report_stdout=not args.s6_quiet_run_report,
            run_s7=args.run_s7,
            s7_emit_run_report_stdout=not args.s7_quiet_run_report,
        )
    )
    _print_summary(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
