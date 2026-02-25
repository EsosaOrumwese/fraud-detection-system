#!/usr/bin/env python3
"""Build and publish M6.G P6 gate rollup artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _read_json_from_s3(s3_client: Any, *, bucket: str, key: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read().decode("utf-8")
        return json.loads(raw), None
    except (BotoCoreError, ClientError) as exc:
        return None, f"s3_read_failed:{type(exc).__name__}:{key}"
    except json.JSONDecodeError:
        return None, f"json_decode_failed:{key}"


def _upload_artifacts(
    s3_client: Any,
    *,
    bucket: str,
    execution_id: str,
    files: list[Path],
) -> tuple[bool, str | None]:
    prefix = f"evidence/dev_full/run_control/{execution_id}/"
    try:
        for file_path in files:
            key = f"{prefix}{file_path.name}"
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=file_path.read_bytes(),
                ContentType="application/json",
            )
            s3_client.head_object(Bucket=bucket, Key=key)
        return True, None
    except (BotoCoreError, ClientError) as exc:
        return False, f"s3_upload_failed:{type(exc).__name__}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _dedupe_blockers(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for blocker in blockers:
        code = str(blocker.get("code", "")).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        deduped.append({"code": code, "message": str(blocker.get("message", "")).strip()})
    return deduped


def main() -> int:
    parser = argparse.ArgumentParser(description="Build M6.G P6 gate rollup artifacts")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--upstream-m6e-execution", required=True)
    parser.add_argument("--upstream-m6f-execution", required=True)
    parser.add_argument("--evidence-bucket", required=True)
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--local-output-root", default="runs/dev_substrate/dev_full/m6")
    args = parser.parse_args()

    captured_at = _now_utc()
    local_root = Path(args.local_output_root) / args.execution_id
    local_root.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", region_name=args.region)

    m6e_prefix = f"evidence/dev_full/run_control/{args.upstream_m6e_execution}"
    m6f_prefix = f"evidence/dev_full/run_control/{args.upstream_m6f_execution}"
    required_artifacts: dict[str, str] = {
        "m6e_summary": f"{m6e_prefix}/m6e_execution_summary.json",
        "m6e_blockers": f"{m6e_prefix}/m6e_blocker_register.json",
        "m6f_summary": f"{m6f_prefix}/m6f_execution_summary.json",
        "m6f_blockers": f"{m6f_prefix}/m6f_blocker_register.json",
        "m6f_active": f"{m6f_prefix}/m6f_streaming_active_snapshot.json",
        "m6f_lag": f"{m6f_prefix}/m6f_streaming_lag_posture.json",
        "m6f_ambiguity": f"{m6f_prefix}/m6f_publish_ambiguity_register.json",
        "m6f_overhead": f"{m6f_prefix}/m6f_evidence_overhead_snapshot.json",
    }

    payloads: dict[str, dict[str, Any]] = {}
    read_errors: list[str] = []
    for alias, key in required_artifacts.items():
        payload, err = _read_json_from_s3(s3, bucket=args.evidence_bucket, key=key)
        if err:
            read_errors.append(err)
            continue
        if payload is not None:
            payloads[alias] = payload

    m6e_summary = payloads.get("m6e_summary", {})
    m6e_blockers = payloads.get("m6e_blockers", {})
    m6f_summary = payloads.get("m6f_summary", {})
    m6f_blockers = payloads.get("m6f_blockers", {})
    m6f_active = payloads.get("m6f_active", {})
    m6f_lag = payloads.get("m6f_lag", {})
    m6f_ambiguity = payloads.get("m6f_ambiguity", {})
    m6f_overhead = payloads.get("m6f_overhead", {})

    m6e_pass = bool(m6e_summary.get("overall_pass"))
    m6f_pass = bool(m6f_summary.get("overall_pass"))
    active_pass = (
        _safe_int(m6f_active.get("wsp_active_count")) > 0
        and _safe_int(m6f_active.get("sr_ready_active_count")) > 0
        and _safe_int(m6f_active.get("ig_idempotency_count")) > 0
    )
    lag_pass = bool(m6f_lag.get("within_threshold"))
    ambiguity_pass = _safe_int(m6f_ambiguity.get("unresolved_publish_ambiguity_count")) == 0
    overhead_pass = bool(m6f_overhead.get("budget_check_pass"))

    lane_matrix: list[dict[str, Any]] = [
        {
            "lane": "P6.A_ENTRY_STREAM_ACTIVATION",
            "source": "M6.E",
            "execution_id": args.upstream_m6e_execution,
            "overall_pass": m6e_pass,
            "details": {
                "next_gate": m6e_summary.get("next_gate"),
                "blocker_count": _safe_int(m6e_summary.get("blocker_count")),
            },
        },
        {
            "lane": "P6.B_STREAMING_ACTIVE",
            "source": "M6.F",
            "execution_id": args.upstream_m6f_execution,
            "overall_pass": m6f_pass,
            "details": {
                "next_gate": m6f_summary.get("next_gate"),
                "blocker_count": _safe_int(m6f_summary.get("blocker_count")),
            },
        },
        {
            "lane": "P6.B_ACTIVE_FLOW_COUNTERS",
            "source": "M6.F",
            "execution_id": args.upstream_m6f_execution,
            "overall_pass": active_pass,
            "details": {
                "wsp_active_count": _safe_int(m6f_active.get("wsp_active_count")),
                "sr_ready_active_count": _safe_int(m6f_active.get("sr_ready_active_count")),
                "ig_idempotency_count": _safe_int(m6f_active.get("ig_idempotency_count")),
            },
        },
        {
            "lane": "P6.B_LAG_POSTURE",
            "source": "M6.F",
            "execution_id": args.upstream_m6f_execution,
            "overall_pass": lag_pass,
            "details": {
                "within_threshold": bool(m6f_lag.get("within_threshold")),
                "measured_lag": m6f_lag.get("measured_lag"),
                "threshold": m6f_lag.get("threshold"),
            },
        },
        {
            "lane": "P6.B_AMBIGUITY_POSTURE",
            "source": "M6.F",
            "execution_id": args.upstream_m6f_execution,
            "overall_pass": ambiguity_pass,
            "details": {
                "unresolved_publish_ambiguity_count": _safe_int(
                    m6f_ambiguity.get("unresolved_publish_ambiguity_count")
                ),
            },
        },
        {
            "lane": "P6.B_EVIDENCE_OVERHEAD_POSTURE",
            "source": "M6.F",
            "execution_id": args.upstream_m6f_execution,
            "overall_pass": overhead_pass,
            "details": {
                "budget_check_pass": bool(m6f_overhead.get("budget_check_pass")),
                "bytes_per_event": m6f_overhead.get("bytes_per_event"),
                "write_rate_bytes_per_sec": m6f_overhead.get("write_rate_bytes_per_sec"),
            },
        },
    ]

    blockers: list[dict[str, str]] = []

    if read_errors:
        blockers.append(
            {
                "code": "M6P6-B8",
                "message": "Required upstream evidence artifacts are missing/unreadable in durable storage.",
            }
        )

    upstream_codes: set[str] = set()
    for payload in (m6e_blockers, m6f_blockers):
        for item in payload.get("blockers", []):
            code = str(item.get("code", "")).strip()
            if code:
                upstream_codes.add(code)
    for code in sorted(upstream_codes):
        blockers.append({"code": code, "message": f"Upstream blocker remains active: {code}"})

    if not m6e_pass:
        blockers.append({"code": "M6P6-B1", "message": "M6.E entry/activation precheck is not green."})
    if not m6f_pass:
        blockers.append({"code": "M6P6-B2", "message": "M6.F streaming-active lane is not green."})
    if not active_pass:
        blockers.append(
            {
                "code": "M6P6-B3",
                "message": "Active flow counters are not all positive for the authoritative M6.F run.",
            }
        )
    if not lag_pass:
        blockers.append({"code": "M6P6-B4", "message": "Lag posture does not satisfy threshold."})
    if not ambiguity_pass:
        blockers.append(
            {"code": "M6P6-B5", "message": "Publish ambiguity register contains unresolved records."}
        )
    if not overhead_pass:
        blockers.append(
            {"code": "M6P6-B7", "message": "Evidence-overhead budget check did not pass."}
        )

    blockers = _dedupe_blockers(blockers)
    blocker_codes = {item["code"] for item in blockers}

    if not blockers:
        verdict = "ADVANCE_TO_P7"
        next_gate = "M6.H_READY"
    elif "M6P6-B8" in blocker_codes:
        verdict = "NO_GO_RESET_REQUIRED"
        next_gate = "NO_GO_RESET_REQUIRED"
    else:
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    consistency_ok = (not blockers and verdict == "ADVANCE_TO_P7") or (
        bool(blockers) and verdict in {"HOLD_REMEDIATE", "NO_GO_RESET_REQUIRED"}
    )
    if not consistency_ok:
        blockers.append(
            {
                "code": "M6P6-B6",
                "message": "Rollup verdict is inconsistent with blocker register state.",
            }
        )
        blockers = _dedupe_blockers(blockers)
        verdict = "NO_GO_RESET_REQUIRED"
        next_gate = "NO_GO_RESET_REQUIRED"

    blocker_register = {
        "captured_at_utc": captured_at,
        "phase": "M6.G",
        "phase_id": "P6.C",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
    }

    rollup_matrix = {
        "captured_at_utc": captured_at,
        "phase": "M6.G",
        "phase_id": "P6.C",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "inputs": {
            "m6e_execution_id": args.upstream_m6e_execution,
            "m6f_execution_id": args.upstream_m6f_execution,
        },
        "lane_matrix": lane_matrix,
        "source_artifacts": {
            alias: f"s3://{args.evidence_bucket}/{key}" for alias, key in required_artifacts.items()
        },
    }

    overall_pass = len(blockers) == 0
    gate_verdict = {
        "captured_at_utc": captured_at,
        "phase": "M6.G",
        "phase_id": "P6.C",
        "execution_id": args.execution_id,
        "inputs": {
            "m6e_execution_id": args.upstream_m6e_execution,
            "m6f_execution_id": args.upstream_m6f_execution,
        },
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
    }

    execution_summary = {
        "captured_at_utc": captured_at,
        "phase": "M6.G",
        "phase_id": "P6.C",
        "execution_id": args.execution_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
    }

    _write_json(local_root / "m6g_p6_gate_rollup_matrix.json", rollup_matrix)
    _write_json(local_root / "m6g_p6_blocker_register.json", blocker_register)
    _write_json(local_root / "m6g_p6_gate_verdict.json", gate_verdict)
    _write_json(local_root / "m6g_execution_summary.json", execution_summary)

    files_for_upload = [
        local_root / "m6g_p6_gate_rollup_matrix.json",
        local_root / "m6g_p6_blocker_register.json",
        local_root / "m6g_p6_gate_verdict.json",
        local_root / "m6g_execution_summary.json",
    ]
    uploaded, upload_error = _upload_artifacts(
        s3,
        bucket=args.evidence_bucket,
        execution_id=args.execution_id,
        files=files_for_upload,
    )
    if not uploaded:
        current_blockers = json.loads((local_root / "m6g_p6_blocker_register.json").read_text(encoding="utf-8"))
        amended = list(current_blockers.get("blockers", []))
        amended.append(
            {
                "code": "M6P6-B8",
                "message": f"Durable publish/readback failed for M6.G artifact set ({upload_error}).",
            }
        )
        amended = _dedupe_blockers(amended)
        current_blockers["blockers"] = amended
        current_blockers["blocker_count"] = len(amended)
        _write_json(local_root / "m6g_p6_blocker_register.json", current_blockers)

        current_verdict = json.loads((local_root / "m6g_p6_gate_verdict.json").read_text(encoding="utf-8"))
        current_verdict["overall_pass"] = False
        current_verdict["blocker_count"] = len(amended)
        current_verdict["verdict"] = "NO_GO_RESET_REQUIRED"
        current_verdict["next_gate"] = "NO_GO_RESET_REQUIRED"
        _write_json(local_root / "m6g_p6_gate_verdict.json", current_verdict)

        current_summary = json.loads((local_root / "m6g_execution_summary.json").read_text(encoding="utf-8"))
        current_summary["overall_pass"] = False
        current_summary["blocker_count"] = len(amended)
        current_summary["verdict"] = "NO_GO_RESET_REQUIRED"
        current_summary["next_gate"] = "NO_GO_RESET_REQUIRED"
        _write_json(local_root / "m6g_execution_summary.json", current_summary)

    print(
        json.dumps(
            {
                "execution_id": args.execution_id,
                "overall_pass": execution_summary.get("overall_pass"),
                "blocker_count": execution_summary.get("blocker_count"),
                "verdict": execution_summary.get("verdict"),
                "next_gate": execution_summary.get("next_gate"),
                "local_output": str(local_root),
                "durable_prefix": (
                    f"s3://{args.evidence_bucket}/evidence/dev_full/run_control/{args.execution_id}/"
                ),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

