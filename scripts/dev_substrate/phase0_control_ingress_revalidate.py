#!/usr/bin/env python3
"""Thin CLI wrapper for Phase 0 Control + Ingress bounded correctness runs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def resolve_python_executable() -> str:
    override = str(Path.cwd() / ".venv" / "Scripts" / "python.exe")
    candidate = Path(override)
    if candidate.exists():
        return str(candidate)
    return sys.executable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Phase 0 bounded Control + Ingress correctness proof on AWS."
    )
    parser.add_argument(
        "--run-control-root",
        default="runs/dev_substrate/dev_full/proving_plane/run_control",
    )
    parser.add_argument("--execution-id", default="")
    parser.add_argument("--state-id", default="PHASE0B")
    parser.add_argument("--window-label", default="correctness")
    parser.add_argument("--artifact-prefix", default="phase0b")
    parser.add_argument("--blocker-prefix", default="PHASE0.B.INGRESS")
    parser.add_argument("--platform-run-id", default="")
    parser.add_argument("--scenario-run-id", default="")
    parser.add_argument("--duration-seconds", type=int, default=90)
    parser.add_argument("--warmup-seconds", type=int, default=0)
    parser.add_argument("--early-cutoff-seconds", type=int, default=45)
    parser.add_argument("--early-cutoff-floor-ratio", type=float, default=0.70)
    parser.add_argument("--expected-window-eps", type=float, default=3000.0)
    parser.add_argument("--stream-speedup", type=float, default=19.7)
    parser.add_argument("--lane-count", type=int, default=24)
    parser.add_argument("--lane-launch-stagger-seconds", type=float, default=0.5)
    parser.add_argument("--output-concurrency", type=int, default=4)
    parser.add_argument("--ig-push-concurrency", type=int, default=4)
    parser.add_argument("--http-pool-maxsize", type=int, default=512)
    parser.add_argument("--target-request-rate-eps", type=float, default=3000.0)
    parser.add_argument("--target-burst-seconds", type=float, default=0.25)
    parser.add_argument("--target-initial-tokens", type=float, default=0.25)
    parser.add_argument("--traffic-output-ids", default="s3_event_stream_with_fraud_6B")
    parser.add_argument(
        "--context-output-ids",
        default="arrival_events_5B,s1_arrival_entities_6B,s3_flow_anchor_with_fraud_6B",
    )
    parser.add_argument("--oracle-engine-run-root", default="")
    parser.add_argument("--api-id", default="pd7rtjze95")
    parser.add_argument("--ig-api-name", default="fraud-platform-dev-full-ig-edge")
    parser.add_argument("--api-stage", default="v1")
    parser.add_argument("--generated-by", default="phase0-control-ingress-cli")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    script_path = Path(__file__).with_name("pr3_wsp_replay_dispatch.py")
    execution_id = str(args.execution_id).strip() or f"phase0_{now_stamp()}"
    checkpoint_attempt_id = now_stamp()
    platform_run_id = str(args.platform_run_id).strip() or f"platform_{checkpoint_attempt_id}"
    scenario_run_id = str(args.scenario_run_id).strip() or uuid.uuid4().hex
    api_stage = str(args.api_stage).strip().strip("/")
    api_id = str(args.api_id).strip()
    explicit_ig_ingest_url = ""
    if api_id and api_stage:
        explicit_ig_ingest_url = f"https://{api_id}.execute-api.eu-west-2.amazonaws.com/{api_stage}/ingest/push"

    command = [
        resolve_python_executable(),
        str(script_path),
        "--run-control-root",
        str(args.run_control_root),
        "--pr3-execution-id",
        execution_id,
        "--state-id",
        str(args.state_id),
        "--window-label",
        str(args.window_label),
        "--artifact-prefix",
        str(args.artifact_prefix),
        "--blocker-prefix",
        str(args.blocker_prefix),
        "--platform-run-id",
        platform_run_id,
        "--scenario-run-id",
        scenario_run_id,
        "--duration-seconds",
        str(int(args.duration_seconds)),
        "--warmup-seconds",
        str(int(args.warmup_seconds)),
        "--early-cutoff-seconds",
        str(int(args.early_cutoff_seconds)),
        "--early-cutoff-floor-ratio",
        str(float(args.early_cutoff_floor_ratio)),
        "--expected-window-eps",
        str(float(args.expected_window_eps)),
        "--stream-speedup",
        str(float(args.stream_speedup)),
        "--lane-count",
        str(int(args.lane_count)),
        "--lane-launch-stagger-seconds",
        str(float(args.lane_launch_stagger_seconds)),
        "--output-concurrency",
        str(int(args.output_concurrency)),
        "--ig-push-concurrency",
        str(int(args.ig_push_concurrency)),
        "--http-pool-maxsize",
        str(int(args.http_pool_maxsize)),
        "--target-request-rate-eps",
        str(float(args.target_request_rate_eps)),
        "--target-burst-seconds",
        str(float(args.target_burst_seconds)),
        "--target-initial-tokens",
        str(float(args.target_initial_tokens)),
        "--traffic-output-ids",
        str(args.traffic_output_ids),
        "--context-output-ids",
        str(args.context_output_ids),
        "--api-id",
        str(args.api_id),
        "--ig-api-name",
        str(args.ig_api_name),
        "--api-stage",
        str(args.api_stage),
        "--ig-ingest-url",
        explicit_ig_ingest_url,
        "--generated-by",
        str(args.generated_by),
        "--checkpoint-attempt-id",
        checkpoint_attempt_id,
    ]
    oracle_engine_run_root = str(args.oracle_engine_run_root).strip()
    if oracle_engine_run_root:
        command.extend(["--oracle-engine-run-root", oracle_engine_run_root])

    if args.dry_run:
        print(
            json.dumps(
                {
                    "execution_id": execution_id,
                    "platform_run_id": platform_run_id,
                    "scenario_run_id": scenario_run_id,
                    "command": command,
                },
                indent=2,
            )
        )
        return

    execution_root = Path(args.run_control_root) / execution_id
    execution_root.mkdir(parents=True, exist_ok=True)
    compatibility_receipt = execution_root / "pr3_s0_execution_receipt.json"
    if not compatibility_receipt.exists():
        dump_json(
            compatibility_receipt,
            {
                "generated_by": str(args.generated_by),
                "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "compatibility_mode": "phase0_wrapper_seed",
                "verdict": "PR3_S0_READY",
                "open_blockers": 0,
            },
        )

    subprocess.run(command, check=True)

    summary_path = execution_root / f"{str(args.artifact_prefix).strip()}_wsp_runtime_summary.json"
    result = {"execution_id": execution_id, "platform_run_id": platform_run_id, "scenario_run_id": scenario_run_id}
    if summary_path.exists():
        summary = load_json(summary_path)
        observed = summary.get("observed", {}) if isinstance(summary, dict) else {}
        result["summary_path"] = str(summary_path)
        result["verdict"] = summary.get("verdict")
        result["open_blockers"] = summary.get("open_blockers")
        result["observed_admitted_eps"] = observed.get("observed_admitted_eps")
        result["latency_p95_ms"] = observed.get("latency_p95_ms")
        result["latency_p99_ms"] = observed.get("latency_p99_ms")
        result["error_4xx_ratio"] = observed.get("4xx_rate_ratio")
        result["error_5xx_ratio"] = observed.get("5xx_rate_ratio")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
