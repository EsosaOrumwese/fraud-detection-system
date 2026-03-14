#!/usr/bin/env python3
"""Emit a bounded managed learning-plane proof for PR3-S4."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import urllib.parse
import urllib.request

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from fraud_detection.scenario_runner.storage import build_object_store

REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
DEFAULT_M10B_EXECUTION = "m10b_databricks_readiness_20260309T012323Z"
DEFAULT_M10D_EXECUTION = "m10d_ofs_build_20260226T164304Z"
DEFAULT_M11B_EXECUTION = "m11b_sagemaker_readiness_20260226T182038Z"
DEFAULT_M12J_EXECUTION = "m12j_closure_sync_20260227T184452Z"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_registry(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    rx = re.compile(r"^\*\s*`([^`]+)`")
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(raw.strip())
        if not m:
            continue
        body = m.group(1)
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def ensure_s3_ref(ref: str, root: str) -> str:
    value = str(ref or "").strip()
    if value.startswith("s3://") or not value:
        return value
    return f"{root.rstrip('/')}/{value.lstrip('/')}"


def rel_s3(ref: str, root: str) -> str:
    norm = ensure_s3_ref(ref, root)
    prefix = root.rstrip("/") + "/"
    if norm.startswith(prefix):
        return norm[len(prefix) :]
    return urlparse(norm).path.lstrip("/")


def store_read_json(store: Any, ref: str, root: str, blocker: str) -> dict[str, Any]:
    norm = ensure_s3_ref(ref, root)
    if not norm:
        raise RuntimeError(f"{blocker}:REF_EMPTY")
    return store.read_json(rel_s3(norm, root))


def store_write_json(store: Any, root: str, key: str, payload: dict[str, Any]) -> str:
    store.write_json(key, payload)
    return ensure_s3_ref(key, root)


def s3_get_json(s3: Any, bucket: str, key: str) -> dict[str, Any]:
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def run_control_ref(bucket: str, execution_id: str, filename: str) -> str:
    return f"s3://{bucket}/evidence/dev_full/run_control/{execution_id}/{filename}"


def load_run_control_json(s3: Any, bucket: str, execution_id: str, filename: str) -> dict[str, Any]:
    return s3_get_json(s3, bucket, f"evidence/dev_full/run_control/{execution_id}/{filename}")


def resolve_ssm(region: str, names: list[str]) -> dict[str, str]:
    ssm = boto3.client("ssm", region_name=region)
    resp = ssm.get_parameters(Names=names, WithDecryption=True)
    out = {str(x.get("Name", "")).strip(): str(x.get("Value", "")).strip() for x in resp.get("Parameters", [])}
    missing = [name for name in names if not out.get(name)]
    if missing:
        raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:MISSING_SSM:{','.join(missing)}")
    return out


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_json(path)


def component_metric(snapshot: dict[str, Any], component: str, metric: str) -> float:
    payload = ((((snapshot.get("components") or {}).get(component) or {}).get("metrics_payload") or {}).get("metrics") or {})
    try:
        return float(payload.get(metric) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def component_summary(snapshot: dict[str, Any], component: str, field: str) -> float:
    payload = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}))
    try:
        return float(payload.get(field) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def component_generated_at(snapshot: dict[str, Any], component: str) -> str:
    payload = (((snapshot.get("components") or {}).get(component) or {}).get("metrics_payload") or {})
    return str(payload.get("generated_at_utc") or snapshot.get("generated_at_utc") or "")


def case_label_stats(pre: dict[str, Any] | None, post: dict[str, Any] | None) -> dict[str, Any]:
    if post is None:
        raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:CASE_LABEL_SNAPSHOT_MISSING")
    pre = pre or {}
    label_event_count = int(component_metric(post, "label_store", "timeline_rows"))
    labelled_subject_count = int(component_metric(post, "label_store", "accepted"))
    case_trigger_count = int(component_metric(post, "case_trigger", "triggers_seen"))
    cases_created = int(component_metric(post, "case_mgmt", "cases_created"))
    labels_accepted = int(component_metric(post, "case_mgmt", "labels_accepted"))
    label_pending = int(component_metric(post, "label_store", "pending"))
    label_rejected = int(component_metric(post, "label_store", "rejected"))
    label_window_start_utc = str(pre.get("generated_at_utc") or "")
    label_asof_utc = component_generated_at(post, "label_store")
    return {
        "label_event_count": label_event_count,
        "labelled_subject_count": labelled_subject_count,
        "label_asof_utc": label_asof_utc,
        "label_window_start_utc": label_window_start_utc,
        "case_trigger_count": case_trigger_count,
        "cases_created": cases_created,
        "labels_accepted": labels_accepted,
        "label_pending": label_pending,
        "label_rejected": label_rejected,
        "case_trigger_delta": int(case_trigger_count - component_metric(pre, "case_trigger", "triggers_seen")),
        "cases_created_delta": int(cases_created - component_metric(pre, "case_mgmt", "cases_created")),
        "labels_accepted_delta": int(labels_accepted - component_metric(pre, "case_mgmt", "labels_accepted")),
        "label_timeline_delta": int(label_event_count - component_metric(pre, "label_store", "timeline_rows")),
    }


def archive_stats(s3: Any, bucket: str, platform_run_id: str, topics: list[str], sample_limit: int) -> dict[str, Any]:
    total = 0
    samples: list[str] = []
    counts: dict[str, int] = {}
    for topic in topics:
        prefix = f"{platform_run_id}/archive/events/topic={topic}/"
        count = 0
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []) or []:
                key = str(item.get("Key") or "")
                if not key.endswith(".json"):
                    continue
                count += 1
                total += 1
                if len(samples) < sample_limit:
                    samples.append(f"s3://{bucket}/{key}")
        counts[topic] = count
    return {"archive_event_count": total, "topic_counts": counts, "sample_refs": samples}


def dbx_json(base_url: str, token: str, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    qs = "?" + urllib.parse.urlencode(query, doseq=True) if query else ""
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}{qs}",
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def dbx_find_job(base_url: str, token: str, job_name: str) -> dict[str, Any] | None:
    page = ""
    while True:
        query: dict[str, Any] = {"limit": 100}
        if page:
            query["page_token"] = page
        payload = dbx_json(base_url, token, "/api/2.1/jobs/list", query)
        for row in payload.get("jobs", []) or []:
            if str((row.get("settings") or {}).get("name") or "").strip() == job_name:
                return row
        page = str(payload.get("next_page_token") or "").strip()
        if not page:
            return None


def role_name(role_arn: str) -> str:
    return role_arn.rsplit("/", 1)[-1] if ":role/" in role_arn else role_arn


def sagemaker_trust(doc: dict[str, Any]) -> bool:
    statements = doc.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    for row in statements if isinstance(statements, list) else []:
        principal = row.get("Principal") if isinstance(row, dict) else None
        service = principal.get("Service") if isinstance(principal, dict) else None
        values = [service] if isinstance(service, str) else [str(x) for x in service] if isinstance(service, list) else []
        if any(v.strip().lower() == "sagemaker.amazonaws.com" for v in values):
            return True
    return False

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--scenario-run-id", required=True)
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--summary-name", default="g3a_correctness_learning_summary.json")
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--label-type", default="fraud_disposition")
    ap.add_argument("--min-labelled-subjects", type=int, default=10)
    ap.add_argument("--min-replay-events", type=int, default=10)
    ap.add_argument("--max-archive-sample-refs", type=int, default=8)
    ap.add_argument("--m10b-execution-id", default=DEFAULT_M10B_EXECUTION)
    ap.add_argument("--m10d-execution-id", default=DEFAULT_M10D_EXECUTION)
    ap.add_argument("--m11b-execution-id", default=DEFAULT_M11B_EXECUTION)
    ap.add_argument("--m12j-execution-id", default=DEFAULT_M12J_EXECUTION)
    args = ap.parse_args()

    run_root = Path(args.run_control_root) / args.pr3_execution_id
    summary_path = run_root / args.summary_name
    blockers: list[str] = []
    notes: list[str] = []

    try:
        reg = parse_registry(REGISTRY_PATH)
        object_root = f"s3://{str(reg['S3_OBJECT_STORE_BUCKET']).strip()}"
        evidence_bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
        if not evidence_bucket:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:EVIDENCE_BUCKET_UNRESOLVED")

        s3 = boto3.client("s3", region_name=args.aws_region)
        iam = boto3.client("iam", region_name=args.aws_region)
        sm = boto3.client("sagemaker", region_name=args.aws_region)
        store = build_object_store(object_root, s3_region=args.aws_region, s3_path_style=False)

        bootstrap = load_json(run_root / "g3a_control_plane_bootstrap.json")
        if not bool(bootstrap.get("overall_pass")):
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:CONTROL_BOOTSTRAP_NOT_GREEN")
        run_facts_ref = ensure_s3_ref(str(((bootstrap.get("sr") or {}).get("facts_view_ref")) or ""), object_root)
        store_read_json(store, run_facts_ref, object_root, "PR3.B29_LEARNING_BOUND_FAIL:RUN_FACTS")

        ssm = resolve_ssm(
            args.aws_region,
            [
                str(reg["SSM_DATABRICKS_WORKSPACE_URL_PATH"]).strip(),
                str(reg["SSM_DATABRICKS_TOKEN_PATH"]).strip(),
                str(reg["SSM_MLFLOW_TRACKING_URI_PATH"]).strip(),
                str(reg["SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN_PATH"]).strip(),
            ],
        )
        pre_snapshot = load_optional_json(run_root / "g3a_s4_component_snapshot_pre.json")
        post_snapshot = load_optional_json(run_root / "g3a_s4_component_snapshot_post.json")
        labels = case_label_stats(pre_snapshot, post_snapshot)
        if labels["labelled_subject_count"] < args.min_labelled_subjects:
            raise RuntimeError(
                f"PR3.B29_LEARNING_BOUND_FAIL:LABELLED_SUBJECTS_SHORTFALL:{labels['labelled_subject_count']}<{args.min_labelled_subjects}"
            )
        if labels["case_trigger_count"] <= 0 or labels["cases_created"] <= 0 or labels["labels_accepted"] <= 0:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:CASE_LABEL_PARTICIPATION_UNPROVEN")
        if labels["label_pending"] > 0 or labels["label_rejected"] > 0:
            raise RuntimeError(
                f"PR3.B29_LEARNING_BOUND_FAIL:LABEL_STORE_INTEGRITY_RED:pending={labels['label_pending']},rejected={labels['label_rejected']}"
            )
        archives = archive_stats(
            s3,
            str(reg["S3_OBJECT_STORE_BUCKET"]).strip(),
            args.platform_run_id,
            ["fp.bus.traffic.fraud.v1", "fp.bus.case.triggers.v1"],
            args.max_archive_sample_refs,
        )
        if archives["archive_event_count"] < args.min_replay_events:
            raise RuntimeError(
                f"PR3.B29_LEARNING_BOUND_FAIL:REPLAY_EVENTS_SHORTFALL:{archives['archive_event_count']}<{args.min_replay_events}"
            )

        contract = {
            "replay_basis_mode": str(reg.get("LEARNING_REPLAY_BASIS_MODE", "")).strip(),
            "feature_asof_required": bool(reg.get("LEARNING_FEATURE_ASOF_REQUIRED")),
            "label_asof_required": bool(reg.get("LEARNING_LABEL_ASOF_REQUIRED")),
            "label_maturity_days_default": int(str(reg.get("LEARNING_LABEL_MATURITY_DAYS_DEFAULT", "0")).strip() or "0"),
            "future_timestamp_policy": str(reg.get("LEARNING_FUTURE_TIMESTAMP_POLICY", "")).strip(),
            "timestamp_fields": str(reg.get("LEARNING_TIMESTAMP_FIELDS", "")).strip(),
        }
        if contract["replay_basis_mode"] != "origin_offset_ranges":
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:REPLAY_BASIS_MODE_INVALID")
        if not contract["feature_asof_required"] or not contract["label_asof_required"]:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:ASOF_POLICY_INVALID")
        if contract["label_maturity_days_default"] <= 0:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:LABEL_MATURITY_INVALID")
        if contract["future_timestamp_policy"] != "fail_closed":
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:FUTURE_TIMESTAMP_POLICY_INVALID")

        dbx_url = ssm[str(reg["SSM_DATABRICKS_WORKSPACE_URL_PATH"]).strip()]
        dbx_token = ssm[str(reg["SSM_DATABRICKS_TOKEN_PATH"]).strip()]
        dbx_me = dbx_json(dbx_url, dbx_token, "/api/2.0/preview/scim/v2/Me")
        dbx_build = dbx_find_job(dbx_url, dbx_token, str(reg["DBX_JOB_OFS_BUILD_V0"]).strip())
        dbx_quality = dbx_find_job(dbx_url, dbx_token, str(reg["DBX_JOB_OFS_QUALITY_GATES_V0"]).strip())
        if not dbx_build or not dbx_quality:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:DATABRICKS_JOB_MISSING")

        sm_role_arn = ssm[str(reg["SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN_PATH"]).strip()]
        trust_doc = (iam.get_role(RoleName=role_name(sm_role_arn))["Role"].get("AssumeRolePolicyDocument") or {})
        if not sagemaker_trust(trust_doc):
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:SAGEMAKER_TRUST_INVALID")
        try:
            sm.list_training_jobs(MaxResults=1)
            sm.list_model_package_groups(MaxResults=1)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:SAGEMAKER_CONTROL_PLANE_UNREADABLE:{type(exc).__name__}") from exc

        m10b = load_run_control_json(s3, evidence_bucket, args.m10b_execution_id, "m10b_databricks_readiness_snapshot.json")
        m10d = load_run_control_json(s3, evidence_bucket, args.m10d_execution_id, "m10d_ofs_build_execution_snapshot.json")
        m11b = load_run_control_json(s3, evidence_bucket, args.m11b_execution_id, "m11b_sagemaker_readiness_snapshot.json")
        m12j = load_run_control_json(s3, evidence_bucket, args.m12j_execution_id, "m12_execution_summary.json")
        upstream = dict(m12j.get("upstream_refs") or {})
        for name in ("m12b_execution_id", "m12c_execution_id", "m12e_execution_id", "m12g_execution_id"):
            if not str(upstream.get(name, "")).strip():
                raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:M12_UPSTREAM_REFS_MISSING:{name}")
        m12b = load_run_control_json(s3, evidence_bucket, str(upstream["m12b_execution_id"]), "m12b_candidate_eligibility_snapshot.json")
        m12c = load_run_control_json(s3, evidence_bucket, str(upstream["m12c_execution_id"]), "m12c_compatibility_precheck_snapshot.json")
        m12e = load_run_control_json(s3, evidence_bucket, str(upstream["m12e_execution_id"]), "m12e_rollback_drill_snapshot.json")
        m12g = load_run_control_json(s3, evidence_bucket, str(upstream["m12g_execution_id"]), "m12_operability_acceptance_report.json")
        if not all(bool(x.get("overall_pass")) for x in (m10b, m10d, m11b, m12j, m12g)):
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:MANAGED_AUTHORITY_NOT_GREEN")
        if not bool((m12b.get("candidate_checks") or {}).get("present")):
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:M12B_CANDIDATE_MISSING")
        if not bool((m12c.get("policy_degrade_checks") or {}).get("required_vs_degrade_mask_compatible")):
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:M12C_COMPATIBILITY_FALSE")
        if not bool((m12e.get("bounded_restore_objective") or {}).get("overall_pass")):
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:M12E_ROLLBACK_OBJECTIVE_FALSE")

        refs = dict(m12b.get("readable_ref_report") or {})
        required_ref_names = [
            "mf_candidate_bundle_ref",
            "m11_model_operability_report_ref",
            "m11_eval_report_ref",
            "m11_eval_vs_baseline_report_ref",
            "mf_leakage_provenance_check_ref",
            "m11_reproducibility_check_ref",
            "m11f_mlflow_lineage_snapshot_ref",
        ]
        unreadable = [name for name in required_ref_names if not bool((refs.get(name) or {}).get("readable"))]
        if unreadable:
            raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:MLOPS_REFS_UNREADABLE:{','.join(unreadable)}")
        candidate_bundle_ref = str((refs.get("mf_candidate_bundle_ref") or {}).get("ref") or "").strip()
        eval_report_upstream_ref = str((refs.get("m11_eval_report_ref") or {}).get("ref") or "").strip()
        baseline_upstream_ref = str((refs.get("m11_eval_vs_baseline_report_ref") or {}).get("ref") or "").strip()
        reproducibility_upstream_ref = str((refs.get("m11_reproducibility_check_ref") or {}).get("ref") or "").strip()
        lineage_upstream_ref = str((refs.get("m11f_mlflow_lineage_snapshot_ref") or {}).get("ref") or "").strip()
        leakage_upstream_ref = str((refs.get("mf_leakage_provenance_check_ref") or {}).get("ref") or "").strip()
        operability_upstream_ref = str((refs.get("m11_model_operability_report_ref") or {}).get("ref") or "").strip()

        ofs_manifest_ref = store_write_json(store, object_root, f"{args.platform_run_id}/ofs/pr3_s4_managed_bound_manifest.json", {
            "schema_version": "pr3.s4.learning.ofs_manifest.v0",
            "proof_mode": "bounded_same_run_managed_corridor",
            "generated_at_utc": now_utc(),
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "current_run_inputs": {
                "run_facts_ref": run_facts_ref,
                "label_type": args.label_type,
                "label_event_count": labels["label_event_count"],
                "labelled_subject_count": labels["labelled_subject_count"],
                "label_asof_utc": labels["label_asof_utc"],
                "case_trigger_count": labels["case_trigger_count"],
                "cases_created": labels["cases_created"],
                "labels_accepted": labels["labels_accepted"],
                "case_trigger_delta": labels["case_trigger_delta"],
                "cases_created_delta": labels["cases_created_delta"],
                "labels_accepted_delta": labels["labels_accepted_delta"],
                "label_timeline_delta": labels["label_timeline_delta"],
                "archive_event_count": archives["archive_event_count"],
                "archive_sample_refs": archives["sample_refs"],
                "archive_topic_counts": archives["topic_counts"],
            },
            "learning_contract": contract,
            "managed_authority": {
                "m10b_execution_id": args.m10b_execution_id,
                "m10d_execution_id": args.m10d_execution_id,
                "workspace_url": dbx_url,
                "workspace_user": str(dbx_me.get("userName") or ""),
                "build_job_name": str(reg["DBX_JOB_OFS_BUILD_V0"]).strip(),
                "build_job_id": dbx_build.get("job_id"),
                "quality_job_name": str(reg["DBX_JOB_OFS_QUALITY_GATES_V0"]).strip(),
                "quality_job_id": dbx_quality.get("job_id"),
                "upstream_build_run_id": ((m10d.get("databricks") or {}).get("run_id")),
                "upstream_build_result_state": ((m10d.get("databricks") or {}).get("result_state")),
            },
            "assessment": "Current-run learning inputs are present and the Databricks-managed OFS control surface is alive for bounded PR3-S4 correctness.",
            "upstream_refs": {
                "m10b_snapshot_ref": run_control_ref(evidence_bucket, args.m10b_execution_id, "m10b_databricks_readiness_snapshot.json"),
                "m10d_snapshot_ref": run_control_ref(evidence_bucket, args.m10d_execution_id, "m10d_ofs_build_execution_snapshot.json"),
            },
        })
        mf_eval_report_ref = store_write_json(store, object_root, f"{args.platform_run_id}/mf/pr3_s4_managed_eval_report.json", {
            "schema_version": "pr3.s4.learning.mf_eval_report.v0",
            "proof_mode": "bounded_same_run_managed_corridor",
            "generated_at_utc": now_utc(),
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "current_run_inputs": {"run_facts_ref": run_facts_ref, "labelled_subject_count": labels["labelled_subject_count"], "archive_event_count": archives["archive_event_count"]},
            "managed_runtime": {
                "m11b_execution_id": args.m11b_execution_id,
                "sagemaker_execution_role_arn": sm_role_arn,
                "mlflow_tracking_uri": ssm[str(reg["SSM_MLFLOW_TRACKING_URI_PATH"]).strip()],
                "mlflow_hosting_mode": str(reg.get("MLFLOW_HOSTING_MODE", "")).strip(),
                "experiment_path": str(reg.get("MLFLOW_EXPERIMENT_PATH", "")).strip(),
                "package_group_name": str(reg.get("SM_MODEL_PACKAGE_GROUP_NAME", "")).strip(),
                "control_plane_ready": True,
            },
            "upstream_candidate": {
                "bundle_id": str(m12b.get("candidate_bundle_bundle_id") or ""),
                "eval_report_ref": eval_report_upstream_ref,
                "eval_vs_baseline_ref": baseline_upstream_ref,
                "lineage_snapshot_ref": lineage_upstream_ref,
                "leakage_provenance_ref": leakage_upstream_ref,
                "reproducibility_ref": reproducibility_upstream_ref,
                "operability_ref": operability_upstream_ref,
            },
            "assessment": "Managed SageMaker + MLflow surfaces are readable and the authoritative candidate/eval lineage set is intact for bounded PR3-S4 proof.",
        })
        mf_gate_receipt_ref = store_write_json(store, object_root, f"{args.platform_run_id}/mf/pr3_s4_managed_gate_receipt.json", {
            "schema_version": "pr3.s4.learning.mf_gate_receipt.v0",
            "proof_mode": "bounded_same_run_managed_corridor",
            "generated_at_utc": now_utc(),
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "gate_decision": "PASS",
            "checks": {
                "candidate_eligibility": bool((m12b.get("candidate_checks") or {}).get("present")),
                "compatibility": bool((m12c.get("policy_degrade_checks") or {}).get("required_vs_degrade_mask_compatible")),
                "rollback_objective": bool((m12e.get("bounded_restore_objective") or {}).get("overall_pass")),
                "operability": bool(m12g.get("overall_pass")),
            },
            "upstream_refs": {
                "m12b_snapshot_ref": run_control_ref(evidence_bucket, str(upstream["m12b_execution_id"]), "m12b_candidate_eligibility_snapshot.json"),
                "m12c_snapshot_ref": run_control_ref(evidence_bucket, str(upstream["m12c_execution_id"]), "m12c_compatibility_precheck_snapshot.json"),
                "m12e_snapshot_ref": run_control_ref(evidence_bucket, str(upstream["m12e_execution_id"]), "m12e_rollback_drill_snapshot.json"),
                "m12g_operability_ref": run_control_ref(evidence_bucket, str(upstream["m12g_execution_id"]), "m12_operability_acceptance_report.json"),
            },
        })
        mf_bundle_publication_ref = store_write_json(store, object_root, f"{args.platform_run_id}/mf/pr3_s4_managed_bundle_publication.json", {
            "schema_version": "pr3.s4.learning.mf_bundle_publication.v0",
            "proof_mode": "bounded_same_run_managed_corridor",
            "generated_at_utc": now_utc(),
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "candidate_bundle_ref": candidate_bundle_ref,
            "bundle_id": str(m12b.get("candidate_bundle_bundle_id") or ""),
            "publish_allowed": True,
        })
        mf_registry_lifecycle_event_ref = store_write_json(store, object_root, f"{args.platform_run_id}/mf/pr3_s4_managed_registry_lifecycle_event.json", {
            "schema_version": "pr3.s4.learning.mf_registry_lifecycle_event.v0",
            "proof_mode": "bounded_same_run_managed_corridor",
            "generated_at_utc": now_utc(),
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "registry_event_topic": str(reg.get("FP_BUS_LEARNING_REGISTRY_EVENTS_V1", "")).strip(),
            "compatibility_mode": str((m12c.get("resolved_schema_handles") or {}).get("GLUE_SCHEMA_COMPATIBILITY_MODE") or ""),
            "rollback_targets": {
                "rto_target_seconds": int(reg.get("MPR_ROLLBACK_RTO_TARGET_SECONDS", 900)),
                "rto_hard_max_seconds": int(reg.get("MPR_ROLLBACK_RTO_HARD_MAX_SECONDS", 1200)),
                "rpo_target_events": int(reg.get("MPR_ROLLBACK_RPO_TARGET_EVENTS", 0)),
            },
        })
        learning_obs_ref = store_write_json(store, object_root, f"{args.platform_run_id}/obs/pr3_s4_learning_plane_observability.json", {
            "schema_version": "pr3.s4.learning.observability.v0",
            "generated_at_utc": now_utc(),
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "status": "PASS",
            "checks": [
                {"check_id": "current_run_inputs_present", "status": "PASS"},
                {"check_id": "databricks_managed_surface_ready", "status": "PASS"},
                {"check_id": "sagemaker_mlflow_surface_ready", "status": "PASS"},
                {"check_id": "mlops_corridor_authority_readable", "status": "PASS"},
            ],
        })
        for ref, blocker in (
            (ofs_manifest_ref, "PR3.B29_LEARNING_BOUND_FAIL:OFS_MANIFEST_READBACK"),
            (mf_eval_report_ref, "PR3.B29_LEARNING_BOUND_FAIL:MF_EVAL_READBACK"),
            (mf_gate_receipt_ref, "PR3.B29_LEARNING_BOUND_FAIL:MF_GATE_READBACK"),
            (mf_bundle_publication_ref, "PR3.B29_LEARNING_BOUND_FAIL:MF_BUNDLE_READBACK"),
            (mf_registry_lifecycle_event_ref, "PR3.B29_LEARNING_BOUND_FAIL:MPR_EVENT_READBACK"),
            (learning_obs_ref, "PR3.B29_LEARNING_BOUND_FAIL:OBS_READBACK"),
        ):
            store_read_json(store, ref, object_root, blocker)

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
                "label_event_count": labels["label_event_count"],
                "labelled_subject_count": labels["labelled_subject_count"],
                "archive_event_count": archives["archive_event_count"],
                "archive_topic_count": len([v for v in archives["topic_counts"].values() if int(v) > 0]),
                "managed_databricks_jobs_present": 2,
                "managed_sagemaker_probes_passed": 2,
                "mlops_required_refs_readable": len(required_ref_names),
                "mlops_required_refs_total": len(required_ref_names),
                "rollback_rto_target_seconds": int(reg.get("MPR_ROLLBACK_RTO_TARGET_SECONDS", 900)),
            },
            "scope": {
                "run_facts_ref": run_facts_ref,
                "label_type": args.label_type,
                "label_asof_utc": labels["label_asof_utc"],
                "case_label_snapshot_window": {
                    "window_start_utc": labels["label_window_start_utc"],
                    "window_end_utc": labels["label_asof_utc"],
                },
                "learning_contract": contract,
                "managed_executions": {
                    "m10b_execution_id": args.m10b_execution_id,
                    "m10d_execution_id": args.m10d_execution_id,
                    "m11b_execution_id": args.m11b_execution_id,
                    "m12j_execution_id": args.m12j_execution_id,
                },
            },
            "refs": {
                "run_facts_ref": run_facts_ref,
                "ofs_manifest_ref": ofs_manifest_ref,
                "mf_eval_report_ref": mf_eval_report_ref,
                "mf_gate_receipt_ref": mf_gate_receipt_ref,
                "mf_bundle_publication_ref": mf_bundle_publication_ref,
                "mf_registry_lifecycle_event_ref": mf_registry_lifecycle_event_ref,
                "learning_observability_ref": learning_obs_ref,
            },
            "notes": [
                "PR3-S4 learning is now proven against the managed dev_full learning corridor, not an ad hoc EKS worker lane.",
                "This bounded same-run proof validates current-run learning inputs, managed control-surface readiness, and MLOps corridor continuity without claiming a fresh full retrain/promotion cycle.",
            ],
            "assessment": "Meets the bounded PR3-S4 learning/evolution goal: the active run has learning inputs, managed Databricks/SageMaker surfaces are live, and the authoritative MLOps corridor remains readable, rollback-capable, and compatible on dev_full.",
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
            "error": str(exc),
        }
        dump_json(summary_path, summary)
        raise SystemExit(1)

    dump_json(summary_path, summary)


if __name__ == "__main__":
    main()
