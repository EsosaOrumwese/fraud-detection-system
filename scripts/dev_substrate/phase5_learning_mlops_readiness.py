#!/usr/bin/env python3
"""Probe the managed learning corridor against the promoted Phase 4 run scope."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_registry(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rx = re.compile(r"^\* `([^`=]+?)\s*=\s*([^`]+)`")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(line.strip())
        if not m:
            continue
        key = m.group(1).strip()
        raw = m.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            value: Any = raw[1:-1]
        elif raw.lower() == "true":
            value = True
        elif raw.lower() == "false":
            value = False
        else:
            try:
                value = int(raw) if "." not in raw else float(raw)
            except ValueError:
                value = raw
        out[key] = value
    return out


def is_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    if not text:
        return True
    if lowered in {"tbd", "todo", "none", "null", "unset"}:
        return True
    if "placeholder" in lowered or "to_pin" in lowered:
        return True
    if "<" in text and ">" in text:
        return True
    return False


def summary_value(snapshot: dict[str, Any], component: str, field: str) -> float | None:
    value = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def generated_at(snapshot: dict[str, Any], component: str) -> str:
    payload = (((snapshot.get("components") or {}).get(component) or {}).get("metrics_payload") or {})
    return str(payload.get("generated_at_utc") or snapshot.get("generated_at_utc") or "").strip()


def parse_maturity_days(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.fullmatch(r"(?i)(\d+)\s*d", text)
    if match:
        return int(match.group(1))
    if text.isdigit():
        return int(text)
    return None


def parse_s3_uri(uri: str) -> tuple[str, str]:
    value = str(uri or "").strip()
    if not value.startswith("s3://"):
        raise ValueError(f"invalid_s3_uri:{value}")
    bucket, _, key = value[5:].partition("/")
    if not bucket or not key:
        raise ValueError(f"invalid_s3_uri:{value}")
    return bucket, key


def s3_read_json(s3: Any, uri: str) -> dict[str, Any]:
    bucket, key = parse_s3_uri(uri)
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def s3_read_text(s3: Any, uri: str) -> str:
    bucket, key = parse_s3_uri(uri)
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def find_job_id(base_url: str, token: str, job_name: str) -> int | None:
    page_token = ""
    while True:
        query: dict[str, Any] = {"limit": 100}
        if page_token:
            query["page_token"] = page_token
        payload = request_json(base_url, token, "/api/2.1/jobs/list", query)
        for row in payload.get("jobs", []) or []:
            settings = row.get("settings") or {}
            if str(settings.get("name") or "").strip() == job_name:
                try:
                    return int(row.get("job_id"))
                except (TypeError, ValueError):
                    return None
        page_token = str(payload.get("next_page_token") or "").strip()
        if not page_token:
            return None


def request_json(base_url: str, token: str, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    query_string = ""
    if query:
        query_string = "?" + urllib.parse.urlencode(query, doseq=True)
    request = urllib.request.Request(
        url=f"{base_url.rstrip('/')}{path}{query_string}",
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def role_name_from_arn(role_arn: str) -> str:
    return role_arn.rsplit("/", 1)[-1] if ":role/" in role_arn else role_arn


def trust_allows_sagemaker(doc: dict[str, Any]) -> bool:
    statements = doc.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        return False
    for row in statements:
        if not isinstance(row, dict):
            continue
        principal = row.get("Principal")
        if not isinstance(principal, dict):
            continue
        service = principal.get("Service")
        values: list[str] = []
        if isinstance(service, str):
            values = [service]
        elif isinstance(service, list):
            values = [str(item) for item in service]
        if any(value.strip().lower() == "sagemaker.amazonaws.com" for value in values):
            return True
    return False


def read_ssm(ssm_client: Any, name: str, *, decrypt: bool) -> str:
    return str(ssm_client.get_parameter(Name=name, WithDecryption=decrypt)["Parameter"]["Value"]).strip()


def probe_mlflow(tracking_uri: str, databricks_workspace_url: str) -> tuple[bool, str]:
    if is_placeholder(tracking_uri):
        return False, "TRACKING_URI_UNRESOLVED"
    normalized = str(tracking_uri).strip()
    if normalized.lower() == "databricks":
        if is_placeholder(databricks_workspace_url):
            return False, "DATABRICKS_TRACKING_ALIAS_WITHOUT_WORKSPACE"
        return True, "DATABRICKS_TRACKING_ALIAS"
    if "://" not in normalized:
        return False, "TRACKING_URI_INVALID_FORMAT"
    candidates = [
        normalized.rstrip("/") + "/api/2.0/mlflow/experiments/search",
        normalized.rstrip("/") + "/health",
        normalized.rstrip("/"),
    ]
    for url in candidates:
        request = urllib.request.Request(url=url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status = int(getattr(response, "status", 200))
                if status < 500:
                    return True, f"HTTP_{status}"
        except urllib.error.HTTPError as exc:
            if int(exc.code) < 500:
                return True, f"HTTP_{int(exc.code)}"
        except Exception:
            continue
    return False, "TRACKING_URI_UNREADABLE"


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe Phase 5 managed learning telemetry readiness.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--source-execution-id", required=True)
    ap.add_argument("--source-receipt-name", default="phase4_coupled_readiness_receipt.json")
    ap.add_argument("--source-bootstrap-name", default="phase4_control_plane_bootstrap.json")
    ap.add_argument("--source-snapshot-post-name", default="g3a_p4_component_snapshot_post.json")
    ap.add_argument("--source-charter-name", default="g4a_run_charter.active.json")
    ap.add_argument("--summary-name", default="phase5_learning_surface_summary.json")
    ap.add_argument("--receipt-name", default="phase5_learning_surface_receipt.json")
    ap.add_argument("--aws-region", default="eu-west-2")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    source_root = Path(args.run_control_root) / args.source_execution_id

    receipt = load_json(source_root / str(args.source_receipt_name).strip())
    bootstrap = load_json(source_root / str(args.source_bootstrap_name).strip())
    snapshot_post = load_json(source_root / str(args.source_snapshot_post_name).strip())
    source_charter = load_json(source_root / str(args.source_charter_name).strip())
    registry = parse_registry(REGISTRY_PATH)

    blockers: list[str] = []
    notes: list[str] = []

    if str(receipt.get("verdict") or "").strip().upper() != "PHASE4_READY":
        blockers.append("PHASE5.A01_SOURCE_PHASE4_NOT_GREEN")
    if not bool(bootstrap.get("overall_pass")):
        blockers.append("PHASE5.A02_SOURCE_BOOTSTRAP_NOT_GREEN")

    platform_run_id = str(receipt.get("platform_run_id") or bootstrap.get("platform_run_id") or "").strip()
    scenario_run_id = str(bootstrap.get("scenario_run_id") or "").strip()
    if not platform_run_id:
        blockers.append("PHASE5.A03_PLATFORM_RUN_ID_UNRESOLVED")

    case_mgmt_labels = summary_value(snapshot_post, "case_mgmt", "labels_accepted")
    label_store_accepted = summary_value(snapshot_post, "label_store", "accepted")
    label_store_pending = summary_value(snapshot_post, "label_store", "pending")
    label_store_rejected = summary_value(snapshot_post, "label_store", "rejected")
    runtime_label_generated_at_utc = generated_at(snapshot_post, "label_store")
    mission_binding = dict(source_charter.get("mission_binding") or {})
    feature_asof_utc = str(mission_binding.get("as_of_time_utc") or mission_binding.get("window_end_ts_utc") or "").strip()
    label_maturity_lag = str(mission_binding.get("label_maturity_lag") or "").strip()
    label_maturity_days = parse_maturity_days(label_maturity_lag)
    if label_maturity_days is None:
        try:
            label_maturity_days = int(registry.get("LEARNING_LABEL_MATURITY_DAYS_DEFAULT"))
        except (TypeError, ValueError):
            label_maturity_days = None
    label_asof_utc = feature_asof_utc

    if (case_mgmt_labels or 0.0) <= 0.0:
        blockers.append("PHASE5.A04_CASE_LABEL_TRUTH_MISSING")
    if (label_store_accepted or 0.0) <= 0.0:
        blockers.append("PHASE5.A05_LABEL_STORE_ACCEPTED_MISSING")
    if (label_store_pending or 0.0) > 0.0:
        blockers.append(f"PHASE5.A06_LABEL_STORE_PENDING:{int(label_store_pending or 0.0)}")
    if (label_store_rejected or 0.0) > 0.0:
        blockers.append(f"PHASE5.A07_LABEL_STORE_REJECTED:{int(label_store_rejected or 0.0)}")
    if not feature_asof_utc:
        blockers.append("PHASE5.A07B_SOURCE_FEATURE_ASOF_UNRESOLVED")
    if label_maturity_days is None or label_maturity_days <= 0:
        blockers.append("PHASE5.A07C_LABEL_MATURITY_POLICY_UNRESOLVED")

    ssm = boto3.client("ssm", region_name=args.aws_region)
    iam = boto3.client("iam", region_name=args.aws_region)
    sm = boto3.client("sagemaker", region_name=args.aws_region)
    s3 = boto3.client("s3", region_name=args.aws_region)

    dbx_workspace_url_path = str(registry.get("SSM_DATABRICKS_WORKSPACE_URL_PATH") or "").strip()
    dbx_token_path = str(registry.get("SSM_DATABRICKS_TOKEN_PATH") or "").strip()
    mlflow_uri_path = str(registry.get("SSM_MLFLOW_TRACKING_URI_PATH") or "").strip()
    sm_role_path = str(registry.get("SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN_PATH") or "").strip()

    try:
        dbx_workspace_url = read_ssm(ssm, dbx_workspace_url_path, decrypt=False)
        dbx_token = read_ssm(ssm, dbx_token_path, decrypt=True)
        mlflow_tracking_uri = read_ssm(ssm, mlflow_uri_path, decrypt=False)
        sm_role_arn_ssm = read_ssm(ssm, sm_role_path, decrypt=False)
    except (BotoCoreError, ClientError, KeyError) as exc:
        blockers.append(f"PHASE5.A08_SSM_SURFACE_UNREADABLE:{type(exc).__name__}")
        dbx_workspace_url = ""
        dbx_token = ""
        mlflow_tracking_uri = ""
        sm_role_arn_ssm = ""

    if is_placeholder(dbx_workspace_url) or is_placeholder(dbx_token):
        blockers.append("PHASE5.A09_DATABRICKS_SECRET_UNRESOLVED")
    if is_placeholder(mlflow_tracking_uri):
        blockers.append("PHASE5.A10_MLFLOW_TRACKING_URI_UNRESOLVED")

    dbx_me_user = ""
    dbx_build_job_id: int | None = None
    dbx_quality_job_id: int | None = None
    if "PHASE5.A09_DATABRICKS_SECRET_UNRESOLVED" not in blockers and "PHASE5.A08_SSM_SURFACE_UNREADABLE" not in blockers:
        try:
            me_payload = request_json(dbx_workspace_url, dbx_token, "/api/2.0/preview/scim/v2/Me")
            dbx_me_user = str(me_payload.get("userName") or "").strip()
            dbx_build_job_id = find_job_id(dbx_workspace_url, dbx_token, str(registry.get("DBX_JOB_OFS_BUILD_V0") or "").strip())
            dbx_quality_job_id = find_job_id(dbx_workspace_url, dbx_token, str(registry.get("DBX_JOB_OFS_QUALITY_GATES_V0") or "").strip())
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"PHASE5.A11_DATABRICKS_PROBE_FAILED:{type(exc).__name__}")
        if not dbx_build_job_id or not dbx_quality_job_id:
            blockers.append("PHASE5.A12_DATABRICKS_REQUIRED_JOBS_MISSING")

    sm_role_arn_handle = str(registry.get("ROLE_SAGEMAKER_EXECUTION") or "").strip()
    sm_package_group = str(registry.get("SM_MODEL_PACKAGE_GROUP_NAME") or "").strip()
    sm_role_trust_ok = False
    sm_package_group_present = False
    if not sm_role_arn_ssm or sm_role_arn_ssm != sm_role_arn_handle:
        blockers.append("PHASE5.A13_SAGEMAKER_ROLE_MISMATCH")
    else:
        try:
            role_name = role_name_from_arn(sm_role_arn_ssm)
            trust_doc = (iam.get_role(RoleName=role_name)["Role"].get("AssumeRolePolicyDocument") or {})
            sm_role_trust_ok = trust_allows_sagemaker(trust_doc)
            if not sm_role_trust_ok:
                blockers.append("PHASE5.A14_SAGEMAKER_TRUST_INVALID")
            sm.list_training_jobs(MaxResults=1)
            sm.list_model_package_groups(MaxResults=100)
            sm.describe_model_package_group(ModelPackageGroupName=sm_package_group)
            sm_package_group_present = True
        except ClientError as exc:
            code = str((exc.response or {}).get("Error", {}).get("Code") or type(exc).__name__)
            blockers.append(f"PHASE5.A15_SAGEMAKER_CONTROL_PLANE_UNREADABLE:{code}")
        except (BotoCoreError, KeyError) as exc:
            blockers.append(f"PHASE5.A15_SAGEMAKER_CONTROL_PLANE_UNREADABLE:{type(exc).__name__}")

    mlflow_probe_ok, mlflow_probe_detail = probe_mlflow(mlflow_tracking_uri, dbx_workspace_url)
    if not mlflow_probe_ok:
        blockers.append(f"PHASE5.A16_MLFLOW_SURFACE_UNREADABLE:{mlflow_probe_detail}")

    oracle_root = str((((bootstrap.get("oracle") or {})).get("oracle_engine_run_root")) or "").strip()
    manifest_fingerprint = str((((bootstrap.get("oracle") or {})).get("manifest_fingerprint")) or "").strip()
    object_store_bucket = str(registry.get("S3_OBJECT_STORE_BUCKET") or "").strip()
    facts_view_ref = str((((bootstrap.get("sr") or {})).get("facts_view_ref")) or "").strip()
    facts_view_uri = f"s3://{object_store_bucket}/{facts_view_ref.lstrip('/')}" if object_store_bucket and facts_view_ref else ""
    intended_outputs: list[str] = []
    output_roles: dict[str, str] = {}
    if not facts_view_uri:
        blockers.append("PHASE5.A17_FACTS_VIEW_REF_UNRESOLVED")
    else:
        try:
            run_facts = s3_read_json(s3, facts_view_uri)
            intended_outputs = [str(item).strip() for item in run_facts.get("intended_outputs", []) if str(item).strip()]
            for key, value in (run_facts.get("output_roles") or {}).items():
                name = str(key).strip()
                if not name:
                    continue
                if isinstance(value, dict):
                    output_roles[name] = str(value.get("role") or "").strip()
                else:
                    output_roles[name] = str(value or "").strip()
        except (BotoCoreError, ClientError, ValueError, KeyError, json.JSONDecodeError):
            blockers.append("PHASE5.A18_FACTS_VIEW_UNREADABLE")
    allowed_outputs = {"s2_event_stream_baseline_6B", "s3_event_stream_with_fraud_6B"}
    if intended_outputs and set(intended_outputs) != allowed_outputs:
        blockers.append("PHASE5.A19_UNAUTHORIZED_INTENDED_OUTPUTS")
    if any(output_roles.get(name) != "business_traffic" for name in intended_outputs):
        blockers.append("PHASE5.A20_OUTPUT_ROLE_MISMATCH")

    sixb_flag_uri = ""
    validation_uri = ""
    sixb_flag_hash = ""
    validation_status = ""
    validation_checks: dict[str, str] = {}
    if not oracle_root or not manifest_fingerprint:
        blockers.append("PHASE5.A21_ORACLE_GATE_BASIS_UNRESOLVED")
    else:
        sixb_flag_uri = (
            f"{oracle_root}/data/layer3/6B/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag"
        )
        validation_uri = (
            f"{oracle_root}/data/layer3/6B/validation/manifest_fingerprint={manifest_fingerprint}/s5_validation_report_6B.json"
        )
        try:
            sixb_flag_hash = s3_read_text(s3, sixb_flag_uri).strip()
            validation_report = s3_read_json(s3, validation_uri)
            validation_status = str(validation_report.get("overall_status") or "").strip().upper()
            for row in validation_report.get("checks", []) or []:
                if not isinstance(row, dict):
                    continue
                check_name = str(row.get("check_id") or row.get("name") or "").strip()
                if check_name:
                    validation_checks[check_name] = str(row.get("result") or row.get("status") or "").strip().upper()
            if validation_status not in {"PASS", "WARN"}:
                blockers.append(f"PHASE5.A22_6B_STATUS_RED:{validation_status or 'UNSET'}")
            for check_name in (
                "REQ_UPSTREAM_HASHGATES",
                "REQ_FLOW_EVENT_PARITY",
                "REQ_FLOW_LABEL_COVERAGE",
                "REQ_CRITICAL_TRUTH_REALISM",
                "REQ_CRITICAL_CASE_TIMELINE",
            ):
                if validation_checks.get(check_name) != "PASS":
                    blockers.append(f"PHASE5.A23_6B_REQUIRED_CHECK_RED:{check_name}")
        except (BotoCoreError, ClientError, ValueError, KeyError, json.JSONDecodeError):
            blockers.append("PHASE5.A24_6B_GATE_UNREADABLE")

    notes.append("Phase 5.A is telemetry-first and semantic-admission-first: this gate now scores both managed learning surface readability and whether the current world is admissible through interface-pack and 6B gate truth.")
    notes.append("No learning jobs are dispatched here. The objective is to eliminate blindspots and basis ambiguity before the first bounded dataset-basis proof.")
    notes.append("The rebuilt Phase 5 keeps OFS dataset-basis proof ahead of any acceptance of train/eval or promotion claims.")
    notes.append("The bounded learning temporal contract is now anchored to the promoted Phase 4 mission binding instead of to the wall-clock time of the post-run label-store snapshot.")

    summary = {
        "phase": "PHASE5",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_execution_id": args.source_execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": len(blockers) == 0,
        "blocker_ids": blockers,
        "source_boundary": {
            "receipt_name": str(args.source_receipt_name).strip(),
            "bootstrap_name": str(args.source_bootstrap_name).strip(),
            "snapshot_post_name": str(args.source_snapshot_post_name).strip(),
            "charter_name": str(args.source_charter_name).strip(),
            "phase4_verdict": str(receipt.get("verdict") or "").strip(),
        },
        "upstream_truth": {
            "case_mgmt_labels_accepted": case_mgmt_labels,
            "label_store_accepted": label_store_accepted,
            "label_store_pending": label_store_pending,
            "label_store_rejected": label_store_rejected,
            "runtime_label_generated_at_utc": runtime_label_generated_at_utc,
            "feature_asof_utc": feature_asof_utc,
            "label_asof_utc": label_asof_utc,
            "label_maturity_lag": label_maturity_lag,
            "label_maturity_days": label_maturity_days,
        },
        "source_temporal_basis": {
            "window_start_ts_utc": str(mission_binding.get("window_start_ts_utc") or "").strip(),
            "window_end_ts_utc": str(mission_binding.get("window_end_ts_utc") or "").strip(),
            "as_of_time_utc": str(mission_binding.get("as_of_time_utc") or "").strip(),
            "label_maturity_lag": label_maturity_lag,
        },
        "semantic_admission": {
            "facts_view_ref": facts_view_uri,
            "intended_outputs": intended_outputs,
            "output_roles": output_roles,
            "oracle_root": oracle_root,
            "manifest_fingerprint": manifest_fingerprint,
            "sixb_passed_flag_ref": sixb_flag_uri,
            "sixb_passed_flag_sha256_hex": sixb_flag_hash,
            "sixb_validation_report_ref": validation_uri,
            "sixb_validation_status": validation_status,
            "sixb_validation_checks": validation_checks,
        },
        "managed_surfaces": {
            "databricks": {
                "workspace_url": dbx_workspace_url,
                "workspace_user": dbx_me_user,
                "build_job_name": str(registry.get("DBX_JOB_OFS_BUILD_V0") or "").strip(),
                "build_job_id": dbx_build_job_id,
                "quality_job_name": str(registry.get("DBX_JOB_OFS_QUALITY_GATES_V0") or "").strip(),
                "quality_job_id": dbx_quality_job_id,
                "compute_policy": str(registry.get("DBX_COMPUTE_POLICY") or "").strip(),
                "autoscale_workers": str(registry.get("DBX_AUTOSCALE_WORKERS") or "").strip(),
            },
            "sagemaker": {
                "execution_role_arn": sm_role_arn_ssm,
                "execution_role_matches_handle": sm_role_arn_ssm == sm_role_arn_handle,
                "role_trust_ok": sm_role_trust_ok,
                "training_job_prefix": str(registry.get("SM_TRAINING_JOB_NAME_PREFIX") or "").strip(),
                "batch_transform_job_prefix": str(registry.get("SM_BATCH_TRANSFORM_JOB_NAME_PREFIX") or "").strip(),
                "model_package_group_name": sm_package_group,
                "model_package_group_present": sm_package_group_present,
                "endpoint_name": str(registry.get("SM_ENDPOINT_NAME") or "").strip(),
            },
            "mlflow": {
                "tracking_uri": mlflow_tracking_uri,
                "probe_ok": mlflow_probe_ok,
                "probe_detail": mlflow_probe_detail,
            },
        },
        "notes": notes,
        "assessment": (
            "Phase 5.A semantic admission and telemetry gate is green: the current world is admissible and the managed learning corridor is readable from the promoted Phase 4 truth boundary."
            if len(blockers) == 0
            else "Phase 5.A semantic admission and telemetry gate is not green yet; the first bounded learning slice would still be blind, basis-ambiguous, or operationally unresolved."
        ),
    }
    receipt_payload = {
        "phase": "PHASE5",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "platform_run_id": platform_run_id,
        "verdict": "PHASE5A_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_phase": "PHASE5B" if len(blockers) == 0 else "PHASE5A",
        "open_blockers": len(blockers),
        "blocker_ids": blockers,
    }
    dump_json(root / str(args.summary_name).strip(), summary)
    dump_json(root / str(args.receipt_name).strip(), receipt_payload)
    print(json.dumps(receipt_payload, indent=2))


if __name__ == "__main__":
    main()
