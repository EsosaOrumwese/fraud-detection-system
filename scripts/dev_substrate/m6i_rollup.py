#!/usr/bin/env python3
"""Build and publish M6.I P7.B rollup and handoff artifacts."""

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


def _put_json_and_head(
    s3_client: Any,
    *,
    bucket: str,
    key: str,
    payload: dict[str, Any],
) -> tuple[bool, str | None]:
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=(json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8"),
            ContentType="application/json",
        )
        s3_client.head_object(Bucket=bucket, Key=key)
        return True, None
    except (BotoCoreError, ClientError) as exc:
        return False, f"s3_put_or_head_failed:{type(exc).__name__}:{key}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _dedupe_blockers(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for blocker in blockers:
        code = str(blocker.get("code", "")).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append({"code": code, "message": str(blocker.get("message", "")).strip()})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build M6.I P7 rollup artifacts")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--upstream-m6g-execution", required=True)
    parser.add_argument("--upstream-m6h-execution", required=True)
    parser.add_argument("--evidence-bucket", required=True)
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--local-output-root", default="runs/dev_substrate/dev_full/m6")
    args = parser.parse_args()

    captured_at = _now_utc()
    local_root = Path(args.local_output_root) / args.execution_id
    local_root.mkdir(parents=True, exist_ok=True)
    s3 = boto3.client("s3", region_name=args.region)

    required_artifacts: dict[str, str] = {
        "m6g_summary": f"evidence/dev_full/run_control/{args.upstream_m6g_execution}/m6g_execution_summary.json",
        "m6g_verdict": f"evidence/dev_full/run_control/{args.upstream_m6g_execution}/m6g_p6_gate_verdict.json",
        "m6g_blockers": f"evidence/dev_full/run_control/{args.upstream_m6g_execution}/m6g_p6_blocker_register.json",
        "m6h_summary": f"evidence/dev_full/run_control/{args.upstream_m6h_execution}/m6h_execution_summary.json",
        "m6h_blockers": f"evidence/dev_full/run_control/{args.upstream_m6h_execution}/m6h_blocker_register.json",
        "m6h_snapshot": f"evidence/dev_full/run_control/{args.upstream_m6h_execution}/m6h_ingest_commit_snapshot.json",
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

    m6g_summary = payloads.get("m6g_summary", {})
    m6g_verdict = payloads.get("m6g_verdict", {})
    m6g_blockers = payloads.get("m6g_blockers", {})
    m6h_summary = payloads.get("m6h_summary", {})
    m6h_blockers = payloads.get("m6h_blockers", {})
    m6h_snapshot = payloads.get("m6h_snapshot", {})

    m6g_pass = bool(m6g_summary.get("overall_pass"))
    m6g_verdict_ok = str(m6g_verdict.get("verdict", "")).strip() == "ADVANCE_TO_P7"
    m6h_pass = bool(m6h_summary.get("overall_pass"))
    receipt_ok = bool(((m6h_snapshot.get("checks") or {}).get("receipt_summary_readable")))
    quarantine_ok = bool(((m6h_snapshot.get("checks") or {}).get("quarantine_summary_readable")))
    offsets_readable = bool(((m6h_snapshot.get("checks") or {}).get("kafka_offsets_snapshot_readable")))
    offsets_materialized = bool(((m6h_snapshot.get("checks") or {}).get("kafka_offsets_materialized")))
    dedupe_anomaly_count = _safe_int(((m6h_snapshot.get("checks") or {}).get("dedupe_anomaly_count")))

    lane_matrix: list[dict[str, Any]] = [
        {
            "lane": "P7.A_INGEST_COMMIT_EXECUTION",
            "source": "M6.H",
            "execution_id": args.upstream_m6h_execution,
            "overall_pass": m6h_pass,
            "details": {
                "next_gate": m6h_summary.get("next_gate"),
                "blocker_count": _safe_int(m6h_summary.get("blocker_count")),
            },
        },
        {
            "lane": "P7.A_RECEIPT_QUARANTINE_SURFACES",
            "source": "M6.H",
            "execution_id": args.upstream_m6h_execution,
            "overall_pass": receipt_ok and quarantine_ok,
            "details": {
                "receipt_summary_readable": receipt_ok,
                "quarantine_summary_readable": quarantine_ok,
            },
        },
        {
            "lane": "P7.A_OFFSET_SNAPSHOT_SURFACE",
            "source": "M6.H",
            "execution_id": args.upstream_m6h_execution,
            "overall_pass": offsets_readable and offsets_materialized,
            "details": {
                "kafka_offsets_snapshot_readable": offsets_readable,
                "kafka_offsets_materialized": offsets_materialized,
            },
        },
        {
            "lane": "P7.A_DEDUPE_ANOMALY_POSTURE",
            "source": "M6.H",
            "execution_id": args.upstream_m6h_execution,
            "overall_pass": dedupe_anomaly_count == 0,
            "details": {
                "dedupe_anomaly_count": dedupe_anomaly_count,
            },
        },
    ]

    blockers: list[dict[str, str]] = []
    if read_errors:
        blockers.append(
            {
                "code": "M6P7-B8",
                "message": "Required upstream evidence artifacts are missing/unreadable in durable storage.",
            }
        )
    if not m6g_pass or not m6g_verdict_ok:
        blockers.append(
            {
                "code": "M6P7-B2",
                "message": "P7 rollup cannot proceed because upstream M6.G is not ADVANCE_TO_P7.",
            }
        )

    for payload in (m6g_blockers, m6h_blockers):
        for item in payload.get("blockers", []):
            code = str(item.get("code", "")).strip()
            if code.startswith("M6P7-"):
                blockers.append({"code": code, "message": f"Upstream blocker remains active: {code}"})

    if not (receipt_ok and quarantine_ok):
        blockers.append(
            {
                "code": "M6P7-B3",
                "message": "Receipt/quarantine summary evidence is missing or unreadable.",
            }
        )
    if not (offsets_readable and offsets_materialized):
        blockers.append(
            {
                "code": "M6P7-B4",
                "message": "Kafka offsets snapshot is missing/unreadable or not materially populated.",
            }
        )
    if dedupe_anomaly_count != 0:
        blockers.append(
            {
                "code": "M6P7-B5",
                "message": "Dedupe/anomaly checks did not pass.",
            }
        )

    blockers = _dedupe_blockers(blockers)
    blocker_codes = {item["code"] for item in blockers}
    if not blockers:
        verdict = "ADVANCE_TO_M7"
        next_gate = "M6.J_READY"
    elif "M6P7-B8" in blocker_codes:
        verdict = "NO_GO_RESET_REQUIRED"
        next_gate = "NO_GO_RESET_REQUIRED"
    else:
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    consistency_ok = (not blockers and verdict == "ADVANCE_TO_M7") or (
        bool(blockers) and verdict in {"HOLD_REMEDIATE", "NO_GO_RESET_REQUIRED"}
    )
    if not consistency_ok:
        blockers.append(
            {
                "code": "M6P7-B6",
                "message": "Rollup verdict is inconsistent with blocker register state.",
            }
        )
        blockers = _dedupe_blockers(blockers)
        verdict = "NO_GO_RESET_REQUIRED"
        next_gate = "NO_GO_RESET_REQUIRED"

    overall_pass = len(blockers) == 0

    rollup_matrix = {
        "captured_at_utc": captured_at,
        "phase": "M6.I",
        "phase_id": "P7.B",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "inputs": {
            "m6g_execution_id": args.upstream_m6g_execution,
            "m6h_execution_id": args.upstream_m6h_execution,
        },
        "lane_matrix": lane_matrix,
        "source_artifacts": {
            alias: f"s3://{args.evidence_bucket}/{key}" for alias, key in required_artifacts.items()
        },
    }

    blocker_register = {
        "captured_at_utc": captured_at,
        "phase": "M6.I",
        "phase_id": "P7.B",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
    }

    gate_verdict = {
        "captured_at_utc": captured_at,
        "phase": "M6.I",
        "phase_id": "P7.B",
        "execution_id": args.execution_id,
        "inputs": {
            "m6g_execution_id": args.upstream_m6g_execution,
            "m6h_execution_id": args.upstream_m6h_execution,
        },
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
    }

    m7_handoff_pack = {
        "captured_at_utc": captured_at,
        "handoff_from": "M6.I",
        "handoff_to": "M7",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "eligible_for_m7": overall_pass and verdict == "ADVANCE_TO_M7",
        "p7_verdict": verdict,
        "next_gate": next_gate,
        "upstream": {
            "m6g_execution_id": args.upstream_m6g_execution,
            "m6h_execution_id": args.upstream_m6h_execution,
        },
        "evidence_refs": {
            "m6g_p6_gate_verdict": f"s3://{args.evidence_bucket}/evidence/dev_full/run_control/{args.upstream_m6g_execution}/m6g_p6_gate_verdict.json",
            "m6h_ingest_commit_snapshot": f"s3://{args.evidence_bucket}/evidence/dev_full/run_control/{args.upstream_m6h_execution}/m6h_ingest_commit_snapshot.json",
            "m6i_p7_gate_verdict": f"s3://{args.evidence_bucket}/evidence/dev_full/run_control/{args.execution_id}/m6i_p7_gate_verdict.json",
        },
        "blockers": blockers,
    }

    execution_summary = {
        "captured_at_utc": captured_at,
        "phase": "M6.I",
        "phase_id": "P7.B",
        "execution_id": args.execution_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
    }

    _write_json(local_root / "m6i_p7_gate_rollup_matrix.json", rollup_matrix)
    _write_json(local_root / "m6i_p7_blocker_register.json", blocker_register)
    _write_json(local_root / "m6i_p7_gate_verdict.json", gate_verdict)
    _write_json(local_root / "m7_handoff_pack.json", m7_handoff_pack)
    _write_json(local_root / "m6i_execution_summary.json", execution_summary)

    run_control_prefix = f"evidence/dev_full/run_control/{args.execution_id}"
    files: list[tuple[str, dict[str, Any]]] = [
        (f"{run_control_prefix}/m6i_p7_gate_rollup_matrix.json", rollup_matrix),
        (f"{run_control_prefix}/m6i_p7_blocker_register.json", blocker_register),
        (f"{run_control_prefix}/m6i_p7_gate_verdict.json", gate_verdict),
        (f"{run_control_prefix}/m7_handoff_pack.json", m7_handoff_pack),
        (f"{run_control_prefix}/m6i_execution_summary.json", execution_summary),
    ]

    upload_errors: list[str] = []
    for key, payload in files:
        ok, err = _put_json_and_head(s3, bucket=args.evidence_bucket, key=key, payload=payload)
        if not ok:
            upload_errors.append(str(err))

    if upload_errors:
        blockers = list(blockers)
        blockers.append(
            {
                "code": "M6P7-B8",
                "message": "Failed to publish/readback M6.I run-control artifact set.",
            }
        )
        blockers = _dedupe_blockers(blockers)
        blocker_register["blockers"] = blockers
        blocker_register["blocker_count"] = len(blockers)
        blocker_register["upload_errors"] = upload_errors
        gate_verdict["overall_pass"] = False
        gate_verdict["blocker_count"] = len(blockers)
        gate_verdict["verdict"] = "NO_GO_RESET_REQUIRED"
        gate_verdict["next_gate"] = "NO_GO_RESET_REQUIRED"
        execution_summary["overall_pass"] = False
        execution_summary["blocker_count"] = len(blockers)
        execution_summary["verdict"] = "NO_GO_RESET_REQUIRED"
        execution_summary["next_gate"] = "NO_GO_RESET_REQUIRED"
        m7_handoff_pack["eligible_for_m7"] = False
        m7_handoff_pack["p7_verdict"] = "NO_GO_RESET_REQUIRED"
        m7_handoff_pack["next_gate"] = "NO_GO_RESET_REQUIRED"
        m7_handoff_pack["blockers"] = blockers
        _write_json(local_root / "m6i_p7_blocker_register.json", blocker_register)
        _write_json(local_root / "m6i_p7_gate_verdict.json", gate_verdict)
        _write_json(local_root / "m6i_execution_summary.json", execution_summary)
        _write_json(local_root / "m7_handoff_pack.json", m7_handoff_pack)

    print(
        json.dumps(
            {
                "execution_id": args.execution_id,
                "overall_pass": execution_summary.get("overall_pass"),
                "blocker_count": execution_summary.get("blocker_count"),
                "verdict": execution_summary.get("verdict"),
                "next_gate": execution_summary.get("next_gate"),
                "local_output": str(local_root),
                "run_control_prefix": f"s3://{args.evidence_bucket}/{run_control_prefix}/",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
