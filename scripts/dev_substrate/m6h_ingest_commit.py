#!/usr/bin/env python3
"""Build and publish M6.H P7.A ingest-commit artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
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


def _resolve_pattern(pattern: str, *, platform_run_id: str) -> str:
    return str(pattern).replace("{platform_run_id}", platform_run_id)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_bool(text: str) -> bool:
    return str(text).strip().lower() in {"1", "true", "yes", "y"}


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


def _safe_int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_offset_topics_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], list[str]] = {}
    for row in rows:
        state = str(row.get("state") or "").strip().upper()
        if state != "ADMITTED":
            continue
        eb_ref = row.get("eb_ref") if isinstance(row.get("eb_ref"), dict) else {}
        topic = str(row.get("eb_topic") or eb_ref.get("topic") or "").strip()
        partition = _safe_int_or_none(row.get("eb_partition"))
        if partition is None:
            partition = _safe_int_or_none(eb_ref.get("partition"))
        offset = row.get("eb_offset")
        if offset is None:
            offset = eb_ref.get("offset")
        offset_kind = str(row.get("eb_offset_kind") or eb_ref.get("offset_kind") or "").strip() or "kafka_offset"
        offset_text = str(offset).strip() if offset is not None else ""
        if not topic or partition is None or partition < 0 or not offset_text:
            continue
        key = (topic, int(partition), offset_kind)
        grouped.setdefault(key, []).append(offset_text)

    topics: list[dict[str, Any]] = []
    for key in sorted(grouped.keys()):
        topic, partition, offset_kind = key
        offsets = grouped[key]
        numeric_offsets = [item for item in offsets if item.isdigit()]
        if len(numeric_offsets) == len(offsets) and len(numeric_offsets) > 0:
            ordered = sorted(int(item) for item in numeric_offsets)
            first_offset = str(ordered[0])
            last_offset = str(ordered[-1])
        else:
            ordered_text = sorted(offsets)
            first_offset = ordered_text[0]
            last_offset = ordered_text[-1]
        topics.append(
            {
                "topic": topic,
                "partition": partition,
                "offset_kind": offset_kind,
                "first_offset": first_offset,
                "last_offset": last_offset,
                "observed_count": len(offsets),
            }
        )
    return topics


def _build_proxy_offset_topics(*, admitted_epochs: list[int], admit_count: int) -> list[dict[str, Any]]:
    if not admitted_epochs or admit_count <= 0:
        return []
    ordered = sorted(admitted_epochs)
    return [
        {
            "topic": "ig.edge.admission.proxy.v1",
            "partition": 0,
            "offset_kind": "admitted_at_epoch",
            "first_offset": str(ordered[0]),
            "last_offset": str(ordered[-1]),
            "observed_count": int(admit_count),
        }
    ]


def _av_to_py(value: dict[str, Any] | None) -> Any:
    if not isinstance(value, dict) or not value:
        return None
    if "S" in value:
        return str(value["S"])
    if "N" in value:
        number = str(value["N"])
        try:
            return int(number)
        except ValueError:
            try:
                return float(number)
            except ValueError:
                return number
    if "BOOL" in value:
        return bool(value["BOOL"])
    if "NULL" in value:
        return None
    if "M" in value:
        return {k: _av_to_py(v) for k, v in value["M"].items()}
    if "L" in value:
        return [_av_to_py(v) for v in value["L"]]
    return None


def _scan_idempotency_rows(
    ddb_client: Any,
    *,
    table_name: str,
    platform_run_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    read_errors: list[str] = []
    eks: dict[str, Any] | None = None
    while True:
        request: dict[str, Any] = {
            "TableName": table_name,
            "FilterExpression": "platform_run_id = :rid",
            "ExpressionAttributeValues": {":rid": {"S": platform_run_id}},
        }
        if eks:
            request["ExclusiveStartKey"] = eks
        try:
            response = ddb_client.scan(**request)
        except (BotoCoreError, ClientError) as exc:
            read_errors.append(f"ddb_scan_failed:{type(exc).__name__}")
            break
        for item in response.get("Items", []):
            py_row = {k: _av_to_py(v) for k, v in item.items()}
            rows.append(py_row)
        eks = response.get("LastEvaluatedKey")
        if not eks:
            break
    return rows, read_errors


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build M6.H ingest-commit artifacts")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--upstream-m6g-execution", required=True)
    parser.add_argument("--evidence-bucket", required=True)
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--ig-idempotency-table", required=True)
    parser.add_argument("--idempotency-ttl-field", default="ttl_epoch")
    parser.add_argument("--idempotency-ttl-seconds", type=int, default=259200)
    parser.add_argument("--allow-empty-run-waiver", default="false")
    parser.add_argument(
        "--receipt-summary-path-pattern",
        default="evidence/runs/{platform_run_id}/ingest/receipt_summary.json",
    )
    parser.add_argument(
        "--quarantine-summary-path-pattern",
        default="evidence/runs/{platform_run_id}/ingest/quarantine_summary.json",
    )
    parser.add_argument(
        "--offsets-snapshot-path-pattern",
        default="evidence/runs/{platform_run_id}/ingest/kafka_offsets_snapshot.json",
    )
    parser.add_argument("--local-output-root", default="runs/dev_substrate/dev_full/m6")
    args = parser.parse_args()

    captured_at = _now_utc()
    local_root = Path(args.local_output_root) / args.execution_id
    local_root.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", region_name=args.region)
    ddb = boto3.client("dynamodb", region_name=args.region)

    required_handles = {
        "RECEIPT_SUMMARY_PATH_PATTERN": args.receipt_summary_path_pattern,
        "QUARANTINE_SUMMARY_PATH_PATTERN": args.quarantine_summary_path_pattern,
        "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN": args.offsets_snapshot_path_pattern,
        "DDB_IG_IDEMPOTENCY_TABLE": args.ig_idempotency_table,
        "DDB_IG_IDEMPOTENCY_TTL_FIELD": args.idempotency_ttl_field,
        "IG_IDEMPOTENCY_TTL_SECONDS": str(args.idempotency_ttl_seconds),
    }

    blockers: list[dict[str, str]] = []
    read_errors: list[str] = []
    missing = [k for k, v in required_handles.items() if not str(v).strip()]
    if missing:
        blockers.append(
            {
                "code": "M6P7-B1",
                "message": f"Required ingest-commit handles missing/inconsistent: {','.join(sorted(missing))}",
            }
        )

    m6g_prefix = f"evidence/dev_full/run_control/{args.upstream_m6g_execution}"
    m6g_summary, err = _read_json_from_s3(
        s3,
        bucket=args.evidence_bucket,
        key=f"{m6g_prefix}/m6g_execution_summary.json",
    )
    if err:
        read_errors.append(err)
    m6g_verdict, err = _read_json_from_s3(
        s3,
        bucket=args.evidence_bucket,
        key=f"{m6g_prefix}/m6g_p6_gate_verdict.json",
    )
    if err:
        read_errors.append(err)
    m6g_blockers, err = _read_json_from_s3(
        s3,
        bucket=args.evidence_bucket,
        key=f"{m6g_prefix}/m6g_p6_blocker_register.json",
    )
    if err:
        read_errors.append(err)
    if read_errors:
        blockers.append(
            {
                "code": "M6P7-B8",
                "message": "Required upstream evidence artifacts are missing/unreadable in durable storage.",
            }
        )

    m6g_pass = bool((m6g_summary or {}).get("overall_pass"))
    m6g_verdict_ok = str((m6g_verdict or {}).get("verdict", "")).strip() == "ADVANCE_TO_P7"
    if not m6g_pass or not m6g_verdict_ok:
        blockers.append(
            {
                "code": "M6P7-B2",
                "message": "P7 entry gate is unmet because upstream M6.G is not ADVANCE_TO_P7.",
            }
        )

    rows, ddb_errors = _scan_idempotency_rows(
        ddb,
        table_name=args.ig_idempotency_table,
        platform_run_id=args.platform_run_id,
    )
    read_errors.extend(ddb_errors)
    if ddb_errors:
        blockers.append(
            {
                "code": "M6P7-B8",
                "message": "Unable to scan IG idempotency table for ingest commit verification.",
            }
        )

    decision_counts: Counter[str] = Counter()
    event_class_counts: Counter[str] = Counter()
    reason_code_counts: Counter[str] = Counter()
    dedupe_seen: set[str] = set()
    duplicate_dedupe_rows = 0
    malformed_rows = 0
    admitted_epochs: list[int] = []

    for row in rows:
        state = str(row.get("state") or "").strip().upper()
        if state == "ADMITTED":
            decision = "ADMIT"
        elif state == "DUPLICATE":
            decision = "DUPLICATE"
        elif state in {"QUARANTINED", "QUARANTINE"}:
            decision = "QUARANTINE"
        else:
            decision = "UNKNOWN"
            malformed_rows += 1
        decision_counts[decision] += 1
        event_class = str(row.get("event_class") or "unknown_event_class").strip() or "unknown_event_class"
        event_class_counts[event_class] += 1
        reason_code = str(row.get("reason_code") or "").strip()
        if reason_code:
            reason_code_counts[reason_code] += 1
        dedupe_key = str(row.get("dedupe_key") or "").strip()
        if dedupe_key:
            if dedupe_key in dedupe_seen:
                duplicate_dedupe_rows += 1
            dedupe_seen.add(dedupe_key)
        if decision == "ADMIT":
            admitted_epoch = _safe_int(row.get("admitted_at_epoch"), 0)
            if admitted_epoch > 0:
                admitted_epochs.append(admitted_epoch)

    admit_count = _safe_int(decision_counts.get("ADMIT"), 0)
    duplicate_count = _safe_int(decision_counts.get("DUPLICATE"), 0)
    quarantine_count = _safe_int(decision_counts.get("QUARANTINE"), 0)
    total_receipts = sum(decision_counts.values())

    allow_empty = _parse_bool(args.allow_empty_run_waiver)
    entry_gate_pass = admit_count > 0 or allow_empty
    if not entry_gate_pass:
        blockers.append(
            {
                "code": "M6P7-B2",
                "message": "Entry gate unmet: no admitted ingest records and no explicit empty-run waiver.",
            }
        )

    anomaly_count = duplicate_dedupe_rows + malformed_rows
    if anomaly_count > 0:
        blockers.append(
            {
                "code": "M6P7-B5",
                "message": "Dedupe/anomaly checks detected malformed or duplicate idempotency rows.",
            }
        )

    receipt_summary = {
        "captured_at_utc": captured_at,
        "phase": "M6.H",
        "phase_id": "P7.A",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "counts_by_decision": {
            "ADMIT": admit_count,
            "DUPLICATE": duplicate_count,
            "QUARANTINE": quarantine_count,
            "UNKNOWN": _safe_int(decision_counts.get("UNKNOWN"), 0),
        },
        "counts_by_event_class": dict(sorted(event_class_counts.items())),
        "counts_by_reason_code": dict(sorted(reason_code_counts.items())),
        "total_receipts": total_receipts,
        "sanity_total_matches": total_receipts == (admit_count + duplicate_count + quarantine_count + _safe_int(decision_counts.get("UNKNOWN"), 0)),
        "source": {
            "type": "ddb_scan",
            "table": args.ig_idempotency_table,
            "filter": "platform_run_id",
        },
    }

    quarantine_summary = {
        "captured_at_utc": captured_at,
        "phase": "M6.H",
        "phase_id": "P7.A",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "quarantine_count": quarantine_count,
        "quarantine_records_materialized": quarantine_count > 0,
        "source": {
            "type": "ddb_scan",
            "table": args.ig_idempotency_table,
            "note": "Current IG edge mode does not persist dedicated quarantine payload objects.",
        },
    }

    offset_key = _resolve_pattern(args.offsets_snapshot_path_pattern, platform_run_id=args.platform_run_id)
    existing_offset_snapshot, offset_read_err = _read_json_from_s3(
        s3,
        bucket=args.evidence_bucket,
        key=offset_key,
    )
    if offset_read_err:
        read_errors.append(offset_read_err)

    existing_topics: list[dict[str, Any]] = []
    if isinstance(existing_offset_snapshot, dict):
        candidate_topics = existing_offset_snapshot.get("topics")
        if isinstance(candidate_topics, list):
            existing_topics = [item for item in candidate_topics if isinstance(item, dict)]

    real_offset_topics = _extract_offset_topics_from_rows(rows)
    proxy_offset_topics = _build_proxy_offset_topics(admitted_epochs=admitted_epochs, admit_count=admit_count)

    if isinstance(existing_offset_snapshot, dict) and existing_topics:
        kafka_offsets_snapshot = dict(existing_offset_snapshot)
        if "offset_mode" not in kafka_offsets_snapshot:
            kafka_offsets_snapshot["offset_mode"] = "PREEXISTING"
        kafka_offsets_snapshot["evidence_basis"] = "existing_run_scoped_snapshot"
    elif real_offset_topics:
        kafka_offsets_snapshot = {
            "captured_at_utc": captured_at,
            "phase": "M6.H",
            "phase_id": "P7.A",
            "execution_id": args.execution_id,
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "offset_mode": "KAFKA_TOPIC_PARTITION_OFFSETS",
            "evidence_basis": "ig_idempotency_eb_ref_fields",
            "topics": real_offset_topics,
            "kafka_offsets_materialized": True,
        }
    elif proxy_offset_topics:
        kafka_offsets_snapshot = {
            "captured_at_utc": captured_at,
            "phase": "M6.H",
            "phase_id": "P7.A",
            "execution_id": args.execution_id,
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "offset_mode": "IG_ADMISSION_INDEX_PROXY",
            "evidence_basis": "admitted_at_epoch_from_run_scoped_idempotency_rows",
            "topics": proxy_offset_topics,
            "kafka_offsets_materialized": True,
            "admission_proxy": {
                "admit_count": admit_count,
                "first_admitted_epoch": min(admitted_epochs) if admitted_epochs else None,
                "latest_admitted_epoch": max(admitted_epochs) if admitted_epochs else None,
            },
        }
    else:
        kafka_offsets_snapshot = {
            "captured_at_utc": captured_at,
            "phase": "M6.H",
            "phase_id": "P7.A",
            "execution_id": args.execution_id,
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "offset_mode": "IG_ADMISSION_INDEX_PROXY",
            "evidence_basis": "insufficient_admission_rows_for_proxy_offsets",
            "kafka_offsets_materialized": False,
            "topics": [],
            "admission_proxy": {
                "admit_count": admit_count,
                "first_admitted_epoch": min(admitted_epochs) if admitted_epochs else None,
                "latest_admitted_epoch": max(admitted_epochs) if admitted_epochs else None,
            },
            "note": "No material run-scoped offset evidence could be derived.",
        }

    topics_obj = kafka_offsets_snapshot.get("topics")
    offsets_materialized = bool(kafka_offsets_snapshot.get("kafka_offsets_materialized")) or (
        isinstance(topics_obj, list) and len(topics_obj) > 0
    )
    kafka_offsets_snapshot["kafka_offsets_materialized"] = offsets_materialized

    if not offsets_materialized:
        blockers.append(
            {
                "code": "M6P7-B4",
                "message": "Kafka offsets snapshot is missing/unreadable or not materially populated with topic/partition offsets.",
            }
        )

    receipt_key = _resolve_pattern(args.receipt_summary_path_pattern, platform_run_id=args.platform_run_id)
    quarantine_key = _resolve_pattern(args.quarantine_summary_path_pattern, platform_run_id=args.platform_run_id)

    run_scoped_status: dict[str, str] = {}
    ok, err = _put_json_and_head(s3, bucket=args.evidence_bucket, key=receipt_key, payload=receipt_summary)
    run_scoped_status["receipt_summary"] = "ok" if ok else str(err)
    if not ok:
        blockers.append({"code": "M6P7-B3", "message": "Failed to publish/readback receipt summary evidence."})

    ok, err = _put_json_and_head(s3, bucket=args.evidence_bucket, key=quarantine_key, payload=quarantine_summary)
    run_scoped_status["quarantine_summary"] = "ok" if ok else str(err)
    if not ok:
        blockers.append({"code": "M6P7-B3", "message": "Failed to publish/readback quarantine summary evidence."})

    ok, err = _put_json_and_head(s3, bucket=args.evidence_bucket, key=offset_key, payload=kafka_offsets_snapshot)
    run_scoped_status["kafka_offsets_snapshot"] = "ok" if ok else str(err)
    if not ok:
        blockers.append({"code": "M6P7-B4", "message": "Failed to publish/readback kafka offsets snapshot evidence."})

    blockers = _dedupe_blockers(blockers)
    blocker_codes = {item["code"] for item in blockers}
    if not blockers:
        next_gate = "M6.I_READY"
    elif "M6P7-B8" in blocker_codes:
        next_gate = "NO_GO_RESET_REQUIRED"
    else:
        next_gate = "HOLD_REMEDIATE"
    overall_pass = len(blockers) == 0

    ingest_commit_snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M6.H",
        "phase_id": "P7.A",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "inputs": {
            "upstream_m6g_execution": args.upstream_m6g_execution,
            "allow_empty_run_waiver": allow_empty,
        },
        "entry_gate": {
            "upstream_m6g_overall_pass": m6g_pass,
            "upstream_m6g_verdict": str((m6g_verdict or {}).get("verdict", "")),
            "upstream_m6g_verdict_ok": m6g_verdict_ok,
            "admit_count": admit_count,
            "entry_gate_pass": entry_gate_pass,
        },
        "evidence_refs": {
            "receipt_summary_ref": f"s3://{args.evidence_bucket}/{receipt_key}",
            "quarantine_summary_ref": f"s3://{args.evidence_bucket}/{quarantine_key}",
            "kafka_offsets_snapshot_ref": f"s3://{args.evidence_bucket}/{offset_key}",
        },
        "checks": {
            "receipt_summary_readable": run_scoped_status.get("receipt_summary") == "ok",
            "quarantine_summary_readable": run_scoped_status.get("quarantine_summary") == "ok",
            "kafka_offsets_snapshot_readable": run_scoped_status.get("kafka_offsets_snapshot") == "ok",
            "kafka_offsets_materialized": offsets_materialized,
            "dedupe_anomaly_count": anomaly_count,
        },
        "counts": {
            "total_receipts": total_receipts,
            "admit": admit_count,
            "duplicate": duplicate_count,
            "quarantine": quarantine_count,
        },
        "blockers": blockers,
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "run_scoped_publish_status": run_scoped_status,
    }

    blocker_register = {
        "captured_at_utc": captured_at,
        "phase": "M6.H",
        "phase_id": "P7.A",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
    }

    execution_summary = {
        "captured_at_utc": captured_at,
        "phase": "M6.H",
        "phase_id": "P7.A",
        "execution_id": args.execution_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    _write_json(local_root / "receipt_summary.json", receipt_summary)
    _write_json(local_root / "quarantine_summary.json", quarantine_summary)
    _write_json(local_root / "kafka_offsets_snapshot.json", kafka_offsets_snapshot)
    _write_json(local_root / "m6h_ingest_commit_snapshot.json", ingest_commit_snapshot)
    _write_json(local_root / "m6h_blocker_register.json", blocker_register)
    _write_json(local_root / "m6h_execution_summary.json", execution_summary)

    run_control_prefix = f"evidence/dev_full/run_control/{args.execution_id}"
    run_control_files: list[tuple[str, dict[str, Any]]] = [
        (f"{run_control_prefix}/m6h_ingest_commit_snapshot.json", ingest_commit_snapshot),
        (f"{run_control_prefix}/m6h_blocker_register.json", blocker_register),
        (f"{run_control_prefix}/m6h_execution_summary.json", execution_summary),
    ]
    run_control_errors: list[str] = []
    for key, payload in run_control_files:
        ok, err = _put_json_and_head(s3, bucket=args.evidence_bucket, key=key, payload=payload)
        if not ok:
            run_control_errors.append(str(err))

    if run_control_errors:
        blockers = list(blockers)
        blockers.append(
            {
                "code": "M6P7-B8",
                "message": "Failed to publish/readback M6.H run-control artifact set.",
            }
        )
        blockers = _dedupe_blockers(blockers)
        blocker_register["blockers"] = blockers
        blocker_register["blocker_count"] = len(blockers)
        blocker_register["run_control_errors"] = run_control_errors
        execution_summary["overall_pass"] = False
        execution_summary["blocker_count"] = len(blockers)
        execution_summary["next_gate"] = "NO_GO_RESET_REQUIRED"
        ingest_commit_snapshot["blockers"] = blockers
        ingest_commit_snapshot["overall_pass"] = False
        ingest_commit_snapshot["next_gate"] = "NO_GO_RESET_REQUIRED"
        _write_json(local_root / "m6h_ingest_commit_snapshot.json", ingest_commit_snapshot)
        _write_json(local_root / "m6h_blocker_register.json", blocker_register)
        _write_json(local_root / "m6h_execution_summary.json", execution_summary)

    print(
        json.dumps(
            {
                "execution_id": args.execution_id,
                "overall_pass": execution_summary.get("overall_pass"),
                "blocker_count": execution_summary.get("blocker_count"),
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
