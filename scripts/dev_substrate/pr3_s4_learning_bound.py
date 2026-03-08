#!/usr/bin/env python3
"""Run a bounded learning-plane proof on the active PR3-S4 run scope."""

from __future__ import annotations

import argparse
import json
import os
import re
import traceback
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import boto3
import psycopg

from fraud_detection.learning_registry.worker import LearningRegistryWorker, load_worker_config as load_mpr_worker_config
from fraud_detection.model_factory.worker import MfJobWorker, enqueue_train_build_request, load_worker_config as load_mf_worker_config
from fraud_detection.offline_feature_plane.worker import OfsJobWorker, enqueue_build_request, load_worker_config as load_ofs_worker_config
from fraud_detection.scenario_runner.storage import build_object_store


REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def emit_summary(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True), flush=True)


def parse_registry(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    pattern = re.compile(r"^\*\s*`([^`]+)`")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw_line.strip())
        if not match:
            continue
        body = match.group(1)
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        payload[key.strip()] = value.strip().strip('"')
    return payload


def resolve_ssm(region: str, names: list[str]) -> dict[str, str]:
    ssm = boto3.client("ssm", region_name=region)
    response = ssm.get_parameters(Names=names, WithDecryption=True)
    values = {
        str(row.get("Name", "")).strip(): str(row.get("Value", "")).strip()
        for row in response.get("Parameters", [])
    }
    missing = [name for name in names if not values.get(name)]
    if missing:
        raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:MISSING_SSM:{','.join(missing)}")
    return values


def build_aurora_dsn(*, endpoint: str, username: str, password: str, db_name: str, port: int) -> str:
    return (
        f"postgresql://{quote_plus(username)}:{quote_plus(password)}@"
        f"{endpoint}:{int(port)}/{db_name}?sslmode=require"
    )


def ensure_s3_ref(ref: str, object_store_root: str) -> str:
    value = str(ref or "").strip()
    if value.startswith("s3://"):
        return value
    if not value:
        return value
    return f"{object_store_root.rstrip('/')}/{value.lstrip('/')}"


def s3_relative_path(ref: str) -> tuple[str, str]:
    parsed = urlparse(ref)
    return parsed.netloc, parsed.path.lstrip("/")


def query_label_subjects(*, dsn: str, platform_run_id: str, limit: int, label_type: str) -> list[dict[str, str]]:
    sql = """
        SELECT event_id, MAX(observed_time) AS observed_time, MAX(committed_at_utc) AS committed_at_utc
        FROM ls_label_timeline
        WHERE platform_run_id = %s
          AND label_type = %s
        GROUP BY event_id
        ORDER BY MAX(committed_at_utc) DESC
        LIMIT %s
    """
    rows: list[dict[str, str]] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (platform_run_id, label_type, int(limit)))
            for event_id, observed_time, committed_at_utc in cur.fetchall():
                rows.append(
                    {
                        "platform_run_id": platform_run_id,
                        "event_id": str(event_id),
                        "observed_time": str(observed_time),
                        "committed_at_utc": str(committed_at_utc),
                    }
                )
    return rows


def collect_archived_events(
    *,
    bucket: str,
    prefix_root: str,
    subject_event_ids: set[str],
    sample_limit: int,
) -> tuple[list[dict[str, Any]], list[str], str]:
    client = boto3.client("s3")
    selected: OrderedDict[str, dict[str, Any]] = OrderedDict()
    scanned = 0
    topic_used = ""
    candidate_topics = ("fp.bus.traffic.fraud.v1", "fp.bus.case.triggers.v1")
    for topic in candidate_topics:
        prefix = f"{prefix_root.rstrip('/')}/archive/events/topic={topic}/"
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                scanned += 1
                key = str(item.get("Key") or "").strip()
                if not key.endswith(".json"):
                    continue
                payload = json.loads(client.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8"))
                event_id = str(payload.get("event_id") or "").strip()
                if not event_id and isinstance(payload.get("payload"), dict):
                    event_id = str((payload["payload"].get("event_id") or "")).strip()
                if event_id not in subject_event_ids or event_id in selected:
                    continue
                origin = payload.get("origin_offset") or {}
                selected[event_id] = {
                    "topic": str(origin.get("topic") or topic),
                    "partition": int(origin.get("partition") or 0),
                    "offset_kind": str(origin.get("offset_kind") or "kafka_offset"),
                    "offset": str(origin.get("offset") or ""),
                    "event_id": event_id,
                    "ts_utc": str(payload.get("ts_utc") or ""),
                    "payload_hash": str(payload.get("payload_hash") or ""),
                    "payload": payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
                    "archive_ref": f"s3://{bucket}/{key}",
                }
                topic_used = str(origin.get("topic") or topic)
                if len(selected) >= sample_limit:
                    break
            if len(selected) >= sample_limit:
                break
        if selected:
            break
    return list(selected.values()), candidate_topics, topic_used


def build_replay_basis(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    basis: list[dict[str, Any]] = []
    for event in events:
        basis.append(
            {
                "topic": str(event["topic"]),
                "partition": int(event["partition"]),
                "offset_kind": str(event["offset_kind"]),
                "start_offset": str(event["offset"]),
                "end_offset": str(event["offset"]),
            }
        )
    return basis


def read_receipt(store_root: str, relative_path: str) -> dict[str, Any]:
    store = build_object_store(store_root, s3_region=os.getenv("OBJECT_STORE_REGION"), s3_path_style=False)
    return store.read_json(relative_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr3-execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--aws-region", default="eu-west-2")
    parser.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    parser.add_argument("--summary-name", default="g3a_correctness_learning_summary.json")
    parser.add_argument("--sample-limit", type=int, default=25)
    parser.add_argument("--min-labelled-subjects", type=int, default=10)
    parser.add_argument("--min-replay-events", type=int, default=10)
    parser.add_argument("--label-type", default="fraud_disposition")
    args = parser.parse_args()

    run_root = Path(args.run_control_root) / args.pr3_execution_id
    summary_path = run_root / args.summary_name
    blockers: list[str] = []
    notes: list[str] = []

    try:
        registry = parse_registry(REGISTRY_PATH)
        bootstrap = load_json(run_root / "g3a_control_plane_bootstrap.json")
        if not bool(bootstrap.get("overall_pass")):
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:CONTROL_BOOTSTRAP_NOT_GREEN")

        object_store_root = f"s3://{str(registry['S3_OBJECT_STORE_BUCKET']).strip()}"
        ssm_values = resolve_ssm(
            args.aws_region,
            [
                str(registry["SSM_AURORA_ENDPOINT_PATH"]).strip(),
                str(registry["SSM_AURORA_USERNAME_PATH"]).strip(),
                str(registry["SSM_AURORA_PASSWORD_PATH"]).strip(),
            ],
        )
        aurora_dsn = build_aurora_dsn(
            endpoint=ssm_values[str(registry["SSM_AURORA_ENDPOINT_PATH"]).strip()],
            username=ssm_values[str(registry["SSM_AURORA_USERNAME_PATH"]).strip()],
            password=ssm_values[str(registry["SSM_AURORA_PASSWORD_PATH"]).strip()],
            db_name=str(registry.get("AURORA_DB_NAME", "fraud_platform")).strip() or "fraud_platform",
            port=int(str(registry.get("AURORA_PORT", "5432")).strip() or "5432"),
        )

        subjects = query_label_subjects(
            dsn=aurora_dsn,
            platform_run_id=args.platform_run_id,
            limit=max(args.sample_limit * 4, args.min_labelled_subjects),
            label_type=args.label_type,
        )
        if len(subjects) < args.min_labelled_subjects:
            raise RuntimeError(
                f"PR3.B29_LEARNING_BOUND_FAIL:LABELLED_SUBJECTS_SHORTFALL:{len(subjects)}<{args.min_labelled_subjects}"
            )

        bucket, prefix_root = s3_relative_path(object_store_root.rstrip("/") + f"/{args.platform_run_id}")
        selected_events, topic_candidates, topic_used = collect_archived_events(
            bucket=bucket,
            prefix_root=prefix_root,
            subject_event_ids={row["event_id"] for row in subjects},
            sample_limit=args.sample_limit,
        )
        if len(selected_events) < args.min_replay_events:
            raise RuntimeError(
                f"PR3.B29_LEARNING_BOUND_FAIL:REPLAY_EVENTS_SHORTFALL:{len(selected_events)}<{args.min_replay_events}"
            )
        selected_subjects = [
            {"platform_run_id": args.platform_run_id, "event_id": event["event_id"]}
            for event in selected_events
        ]
        matched_subject_meta = {row["event_id"]: row for row in subjects if row["event_id"] in {e["event_id"] for e in selected_events}}
        label_asof_utc = max(row["observed_time"] for row in matched_subject_meta.values())
        run_facts_ref = ensure_s3_ref(str(((bootstrap.get("sr") or {}).get("facts_view_ref")) or ""), object_store_root)
        if not run_facts_ref:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:RUN_FACTS_REF_EMPTY")

        intent_payload = {
            "schema_version": "learning.ofs_build_intent.v0",
            "request_id": f"pr3.s4.ofs.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "intent_kind": "dataset_build",
            "platform_run_id": args.platform_run_id,
            "scenario_run_ids": [args.scenario_run_id],
            "replay_basis": build_replay_basis(selected_events),
            "label_basis": {
                "label_asof_utc": label_asof_utc,
                "resolution_rule": "observed_time<=label_asof_utc",
                "maturity_days": 3,
            },
            "feature_definition_set": {
                "feature_set_id": "core_features",
                "feature_set_version": "v1",
            },
            "join_scope": {
                "subject_key": "platform_run_id,event_id",
                "required_output_ids": ["s3_event_stream_with_fraud_6B"],
            },
            "filters": {"label_types": [args.label_type]},
            "run_facts_ref": run_facts_ref,
            "policy_revision": "ofs-policy-v0",
            "config_revision": "dev-full-pr3-s4",
            "ofs_code_release_id": "git:pr3_s4_learning_bound",
            "non_training_allowed": False,
        }
        replay_events_payload = [
            {
                "topic": event["topic"],
                "partition": int(event["partition"]),
                "offset_kind": event["offset_kind"],
                "offset": event["offset"],
                "event_id": event["event_id"],
                "ts_utc": event["ts_utc"],
                "payload_hash": event["payload_hash"],
                "payload": event["payload"],
            }
            for event in selected_events
        ]
        replay_evidence_payload = {
            "observations": [
                {
                    "topic": event["topic"],
                    "partition": int(event["partition"]),
                    "offset_kind": event["offset_kind"],
                    "offset": event["offset"],
                    "payload_hash": event["payload_hash"],
                    "archive_ref": event["archive_ref"],
                    "source": "ARCHIVE",
                }
                for event in selected_events
            ]
        }

        intent_path = run_root / "g3a_learning_intent.json"
        replay_events_path = run_root / "g3a_learning_replay_events.json"
        target_subjects_path = run_root / "g3a_learning_target_subjects.json"
        replay_evidence_path = run_root / "g3a_learning_replay_evidence.json"
        mf_request_path = run_root / "g3a_learning_mf_request.json"
        dump_json(intent_path, intent_payload)
        dump_json(replay_events_path, {"replay_events": replay_events_payload})
        dump_json(target_subjects_path, {"target_subjects": selected_subjects})
        dump_json(replay_evidence_path, replay_evidence_payload)

        os.environ["PLATFORM_RUN_ID"] = args.platform_run_id
        os.environ["ACTIVE_PLATFORM_RUN_ID"] = args.platform_run_id
        os.environ["ACTIVE_SCENARIO_RUN_ID"] = args.scenario_run_id
        os.environ["PLATFORM_STORE_ROOT"] = object_store_root
        os.environ["OBJECT_STORE_REGION"] = args.aws_region
        os.environ["OBJECT_STORE_PATH_STYLE"] = "false"
        os.environ["LABEL_STORE_LOCATOR"] = aurora_dsn
        os.environ["OFS_REQUIRED_PLATFORM_RUN_ID"] = args.platform_run_id
        os.environ["OFS_RUN_LEDGER_DSN"] = aurora_dsn
        os.environ["MF_REQUIRED_PLATFORM_RUN_ID"] = args.platform_run_id
        os.environ["MF_RUN_LEDGER_DSN"] = aurora_dsn

        ofs_config = load_ofs_worker_config(Path("config/platform/profiles/dev_full.yaml"))
        ofs_request_ref = enqueue_build_request(
            config=ofs_config,
            intent_path=intent_path,
            replay_events_path=replay_events_path,
            target_subjects_path=target_subjects_path,
            replay_evidence_path=replay_evidence_path,
            supersedes_manifest_refs=(),
            backfill_reason="PR3_S4_BOUNDED_CORRECTNESS",
            request_id_override=str(intent_payload["request_id"]),
        )
        ofs_processed = OfsJobWorker(ofs_config).run_once()
        if ofs_processed <= 0:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:OFS_RUN_ONCE_IDLE")
        ofs_receipt = read_receipt(object_store_root, f"{args.platform_run_id}/ofs/job_invocations/{intent_payload['request_id']}.json")
        if str(ofs_receipt.get("status") or "").strip().upper() != "DONE":
            raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:OFS_STATUS:{ofs_receipt.get('status')}")
        manifest_ref = ensure_s3_ref(str(((ofs_receipt.get("refs") or {}).get("manifest_ref")) or ""), object_store_root)
        if not manifest_ref:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:OFS_MANIFEST_REF_EMPTY")
        manifest_bucket, manifest_key = s3_relative_path(manifest_ref)
        manifest_payload = json.loads(
            boto3.client("s3").get_object(Bucket=manifest_bucket, Key=manifest_key)["Body"].read().decode("utf-8")
        )

        mf_request_payload = {
            "schema_version": "learning.mf_train_build_request.v0",
            "request_id": f"pr3.s4.mf.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "intent_kind": "baseline_train",
            "platform_run_id": args.platform_run_id,
            "dataset_manifest_refs": [manifest_ref],
            "training_config_ref": "config/platform/mf/training_profile_v0.yaml",
            "governance_profile_ref": "config/platform/mf/governance_profile_v0.yaml",
            "requester_principal": "SYSTEM::pr3_s4_learning_bound",
            "target_scope": {
                "environment": "dev_full",
                "mode": "fraud",
                "bundle_slot": "primary",
            },
            "policy_revision": "mf-policy-v0",
            "config_revision": "dev-full-pr3-s4",
            "mf_code_release_id": "git:pr3_s4_learning_bound",
            "publish_allowed": True,
        }
        dump_json(mf_request_path, mf_request_payload)
        mf_config = load_mf_worker_config(Path("config/platform/profiles/dev_full.yaml"))
        mf_request_ref = enqueue_train_build_request(
            config=mf_config,
            request_path=mf_request_path,
            request_id_override=str(mf_request_payload["request_id"]),
        )
        mf_processed = MfJobWorker(mf_config).run_once()
        if mf_processed <= 0:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:MF_RUN_ONCE_IDLE")
        mf_receipt = read_receipt(object_store_root, f"{args.platform_run_id}/mf/job_invocations/{mf_request_payload['request_id']}.json")
        if str(mf_receipt.get("status") or "").strip().upper() != "DONE":
            raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:MF_STATUS:{mf_receipt.get('status')}")
        mf_refs = dict(mf_receipt.get("refs") or {})
        lifecycle_ref = ensure_s3_ref(str(mf_refs.get("registry_lifecycle_event_ref") or ""), object_store_root)
        eval_report_ref = ensure_s3_ref(str(mf_refs.get("eval_report_ref") or ""), object_store_root)
        gate_receipt_ref = ensure_s3_ref(str(mf_refs.get("gate_receipt_ref") or ""), object_store_root)
        bundle_publication_ref = ensure_s3_ref(str(mf_refs.get("bundle_publication_ref") or ""), object_store_root)
        if not lifecycle_ref or not eval_report_ref or not gate_receipt_ref or not bundle_publication_ref:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:MF_OUTPUT_REFS_INCOMPLETE")
        eval_bucket, eval_key = s3_relative_path(eval_report_ref)
        eval_payload = json.loads(
            boto3.client("s3").get_object(Bucket=eval_bucket, Key=eval_key)["Body"].read().decode("utf-8")
        )
        mpr_config = load_mpr_worker_config(profile_path=Path("config/platform/profiles/dev_full.yaml"), poll_seconds=5.0)
        mpr_worker = LearningRegistryWorker(mpr_config)
        lifecycle_bucket, lifecycle_key = s3_relative_path(lifecycle_ref)
        lifecycle_local_path = run_root / "g3a_learning_registry_event.json"
        lifecycle_local_path.write_text(
            boto3.client("s3").get_object(Bucket=lifecycle_bucket, Key=lifecycle_key)["Body"].read().decode("utf-8"),
            encoding="utf-8",
        )
        mpr_result = mpr_worker.validate_promote_event(lifecycle_local_path)

        summary = {
            "phase": "PR3",
            "state": "S4",
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "overall_pass": True,
            "blocker_ids": [],
            "impact_metrics": {
                "labelled_subject_count": len(subjects),
                "selected_subject_count": len(selected_subjects),
                "selected_replay_event_count": len(selected_events),
                "ofs_dataset_row_count": int(manifest_payload.get("row_count") or 0),
                "ofs_dataset_manifest_id": manifest_payload.get("dataset_manifest_id"),
                "mf_auc_roc": ((eval_payload.get("metrics") or {}).get("auc_roc")),
                "mf_precision_at_50": ((eval_payload.get("metrics") or {}).get("precision_at_50")),
                "mf_gate_decision": ((json.loads(
                    boto3.client("s3").get_object(Bucket=s3_relative_path(gate_receipt_ref)[0], Key=s3_relative_path(gate_receipt_ref)[1])["Body"].read().decode("utf-8")
                )).get("gate_decision")),
                "learning_registry_validation_status": mpr_result.status,
            },
            "scope": {
                "archive_topic_candidates": list(topic_candidates),
                "archive_topic_used": topic_used,
                "label_type": args.label_type,
                "label_asof_utc": label_asof_utc,
                "sample_limit": args.sample_limit,
            },
            "refs": {
                "run_facts_ref": run_facts_ref,
                "ofs_request_ref": ofs_request_ref,
                "ofs_receipt_ref": f"{object_store_root}/{args.platform_run_id}/ofs/job_invocations/{intent_payload['request_id']}.json",
                "ofs_manifest_ref": manifest_ref,
                "mf_request_ref": mf_request_ref,
                "mf_receipt_ref": f"{object_store_root}/{args.platform_run_id}/mf/job_invocations/{mf_request_payload['request_id']}.json",
                "mf_eval_report_ref": eval_report_ref,
                "mf_gate_receipt_ref": gate_receipt_ref,
                "mf_bundle_publication_ref": bundle_publication_ref,
                "mf_registry_lifecycle_event_ref": lifecycle_ref,
            },
            "notes": notes,
        }
    except Exception as exc:  # noqa: BLE001
        blockers.append(str(exc))
        summary = {
            "phase": "PR3",
            "state": "S4",
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "overall_pass": False,
            "blocker_ids": blockers,
            "notes": notes,
            "error_type": type(exc).__name__,
            "traceback_tail": traceback.format_exc().strip().splitlines()[-5:],
            "error": str(exc),
        }
        dump_json(summary_path, summary)
        emit_summary(summary)
        raise SystemExit(1)

    dump_json(summary_path, summary)
    emit_summary(summary)


if __name__ == "__main__":
    main()
