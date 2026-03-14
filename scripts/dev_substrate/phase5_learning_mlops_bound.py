#!/usr/bin/env python3
"""Emit a bounded Phase 5 proof on current semantic admission plus managed-corridor continuity."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
RUNS_ROOT = Path("runs")
DEFAULT_M10B_EXECUTION = "m10b_databricks_readiness_20260309T012323Z"
DEFAULT_M10D_EXECUTION = "m10d_ofs_build_20260226T164304Z"
DEFAULT_M11F_EXECUTION = "m11f_mlflow_lineage_20260227T075634Z"
DEFAULT_M11G_EXECUTION = "m11g_candidate_bundle_20260227T081200Z"
DEFAULT_M12B_EXECUTION = "m12b_candidate_eligibility_20260227T123135Z"
DEFAULT_M12C_EXECUTION = "m12c_compatibility_precheck_20260227T130306Z"
DEFAULT_M12D_EXECUTION = "m12d_promotion_commit_20260227T144832Z"
DEFAULT_M12E_EXECUTION = "m12e_rollback_drill_20260227T165747Z"
DEFAULT_M12F_EXECUTION = "m12f_active_resolution_20260227T174035Z"
DEFAULT_M12G_EXECUTION = "m12g_governance_append_20260227T175530Z"
DEFAULT_M12J_EXECUTION = "m12j_closure_sync_20260227T184452Z"


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
        match = rx.match(line.strip())
        if not match:
            continue
        key = match.group(1).strip()
        raw = match.group(2).strip()
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


def s3_prefix_has_objects(s3: Any, uri: str) -> bool:
    bucket, prefix = parse_s3_uri(uri)
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
    return bool(response.get("Contents"))


def summary_value(snapshot: dict[str, Any], component: str, field: str) -> float | None:
    value = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def find_local_artifact(execution_id: str, filename: str) -> Path:
    token = str(execution_id).strip()
    matches = [path for path in RUNS_ROOT.rglob(filename) if token and token in str(path)]
    if not matches:
        raise FileNotFoundError(f"{execution_id}/{filename}")
    matches.sort(key=lambda item: len(str(item)))
    return matches[0]


def check_summary_green(payload: dict[str, Any]) -> bool:
    if "overall_pass" in payload:
        return bool(payload.get("overall_pass"))
    verdict = str(payload.get("verdict") or "").strip().upper()
    return verdict.endswith("_READY") or verdict.startswith("ADVANCE_TO_")


def require_local_green(execution_id: str, filename: str, blockers: list[str], blocker_code: str) -> tuple[dict[str, Any] | None, str]:
    try:
        path = find_local_artifact(execution_id, filename)
        payload = load_json(path)
    except (FileNotFoundError, json.JSONDecodeError):
        blockers.append(f"{blocker_code}:ARTIFACT_UNREADABLE")
        return None, ""
    if not check_summary_green(payload):
        blockers.append(f"{blocker_code}:NOT_GREEN")
    return payload, str(path)


def map_checks(report: dict[str, Any]) -> dict[str, str]:
    rows = report.get("checks") or []
    if not isinstance(rows, list):
        return {}
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("check_id") or "").strip()
        result = str(row.get("result") or row.get("status") or "").strip().upper()
        if name:
            out[name] = result
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit bounded Phase 5 learning/MLOps proof.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--source-execution-id", required=True)
    ap.add_argument("--phase5a-execution-id", required=True)
    ap.add_argument("--source-receipt-name", default="phase4_coupled_readiness_receipt.json")
    ap.add_argument("--source-bootstrap-name", default="phase4_control_plane_bootstrap.json")
    ap.add_argument("--source-snapshot-post-name", default="g3a_p4_component_snapshot_post.json")
    ap.add_argument("--phase5a-receipt-name", default="phase5_learning_surface_receipt.json")
    ap.add_argument("--summary-name", default="phase5_learning_bound_summary.json")
    ap.add_argument("--receipt-name", default="phase5_learning_bound_receipt.json")
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--m10b-execution-id", default=DEFAULT_M10B_EXECUTION)
    ap.add_argument("--m10d-execution-id", default=DEFAULT_M10D_EXECUTION)
    ap.add_argument("--m11f-execution-id", default=DEFAULT_M11F_EXECUTION)
    ap.add_argument("--m11g-execution-id", default=DEFAULT_M11G_EXECUTION)
    ap.add_argument("--m12b-execution-id", default=DEFAULT_M12B_EXECUTION)
    ap.add_argument("--m12c-execution-id", default=DEFAULT_M12C_EXECUTION)
    ap.add_argument("--m12d-execution-id", default=DEFAULT_M12D_EXECUTION)
    ap.add_argument("--m12e-execution-id", default=DEFAULT_M12E_EXECUTION)
    ap.add_argument("--m12f-execution-id", default=DEFAULT_M12F_EXECUTION)
    ap.add_argument("--m12g-execution-id", default=DEFAULT_M12G_EXECUTION)
    ap.add_argument("--m12j-execution-id", default=DEFAULT_M12J_EXECUTION)
    args = ap.parse_args()

    run_root = Path(args.run_control_root) / args.execution_id
    source_root = Path(args.run_control_root) / args.source_execution_id
    phase5a_root = Path(args.run_control_root) / args.phase5a_execution_id

    receipt_phase4 = load_json(source_root / str(args.source_receipt_name).strip())
    bootstrap = load_json(source_root / str(args.source_bootstrap_name).strip())
    snapshot_post = load_json(source_root / str(args.source_snapshot_post_name).strip())
    receipt_phase5a = load_json(phase5a_root / str(args.phase5a_receipt_name).strip())
    registry = parse_registry(REGISTRY_PATH)

    blockers: list[str] = []
    notes: list[str] = []

    if str(receipt_phase4.get("verdict") or "").strip().upper() != "PHASE4_READY":
        blockers.append("PHASE5.B01_SOURCE_PHASE4_NOT_GREEN")
    if not bool(bootstrap.get("overall_pass")):
        blockers.append("PHASE5.B02_SOURCE_BOOTSTRAP_NOT_GREEN")
    if str(receipt_phase5a.get("verdict") or "").strip().upper() != "PHASE5A_READY":
        blockers.append("PHASE5.B03_PHASE5A_NOT_GREEN")

    platform_run_id = str(receipt_phase4.get("platform_run_id") or bootstrap.get("platform_run_id") or "").strip()
    scenario_run_id = str(bootstrap.get("scenario_run_id") or "").strip()
    oracle_root = str((((bootstrap.get("oracle") or {})).get("oracle_engine_run_root")) or "").strip()
    manifest_fingerprint = str((((bootstrap.get("oracle") or {})).get("manifest_fingerprint")) or "").strip()
    if not platform_run_id:
        blockers.append("PHASE5.B04_PLATFORM_RUN_ID_UNRESOLVED")
    if not oracle_root or not manifest_fingerprint:
        blockers.append("PHASE5.B05_ORACLE_BASIS_UNRESOLVED")

    label_store_accepted = int(summary_value(snapshot_post, "label_store", "accepted") or 0.0)
    label_store_pending = int(summary_value(snapshot_post, "label_store", "pending") or 0.0)
    label_store_rejected = int(summary_value(snapshot_post, "label_store", "rejected") or 0.0)
    case_mgmt_labels = int(summary_value(snapshot_post, "case_mgmt", "labels_accepted") or 0.0)
    if label_store_accepted <= 0 or case_mgmt_labels <= 0:
        blockers.append("PHASE5.B06_CURRENT_LABEL_TRUTH_MISSING")
    if label_store_pending > 0:
        blockers.append(f"PHASE5.B07_LABEL_STORE_PENDING:{label_store_pending}")
    if label_store_rejected > 0:
        blockers.append(f"PHASE5.B08_LABEL_STORE_REJECTED:{label_store_rejected}")

    s3 = boto3.client("s3", region_name=args.aws_region)
    object_store_bucket = str(registry.get("S3_OBJECT_STORE_BUCKET") or "").strip()
    if not object_store_bucket:
        blockers.append("PHASE5.B09_OBJECT_STORE_BUCKET_UNRESOLVED")

    facts_view_ref = str((((bootstrap.get("sr") or {})).get("facts_view_ref")) or "").strip()
    if facts_view_ref and object_store_bucket:
        facts_uri = f"s3://{object_store_bucket}/{facts_view_ref.lstrip('/')}"
    else:
        facts_uri = ""
        blockers.append("PHASE5.B10_FACTS_VIEW_REF_UNRESOLVED")

    intended_outputs: list[str] = []
    output_roles: dict[str, str] = {}
    if facts_uri:
        try:
            run_facts = s3_read_json(s3, facts_uri)
            intended_outputs = [str(item).strip() for item in run_facts.get("intended_outputs", []) if str(item).strip()]
            output_roles = {}
            for key, value in (run_facts.get("output_roles") or {}).items():
                name = str(key).strip()
                if not name:
                    continue
                if isinstance(value, dict):
                    output_roles[name] = str(value.get("role") or "").strip()
                else:
                    output_roles[name] = str(value or "").strip()
        except (BotoCoreError, ClientError, ValueError, KeyError, json.JSONDecodeError):
            blockers.append("PHASE5.B11_RUN_FACTS_UNREADABLE")

    allowed_outputs = {"s2_event_stream_baseline_6B", "s3_event_stream_with_fraud_6B"}
    if not intended_outputs:
        blockers.append("PHASE5.B12_INTENDED_OUTPUTS_EMPTY")
    if set(intended_outputs) != allowed_outputs:
        blockers.append("PHASE5.B13_INTENDED_OUTPUTS_NOT_6B_BUSINESS_TRAFFIC")
    if any(output_roles.get(name) != "business_traffic" for name in intended_outputs):
        blockers.append("PHASE5.B14_OUTPUT_ROLE_MISMATCH")

    sixb_flag_uri = ""
    validation_uri = ""
    validation_index_uri = ""
    sixb_prefixes: dict[str, str] = {}
    if oracle_root and manifest_fingerprint:
        sixb_flag_uri = (
            f"{oracle_root}/data/layer3/6B/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag"
        )
        validation_uri = (
            f"{oracle_root}/data/layer3/6B/validation/manifest_fingerprint={manifest_fingerprint}/s5_validation_report_6B.json"
        )
        validation_index_uri = (
            f"{oracle_root}/data/layer3/6B/validation/manifest_fingerprint={manifest_fingerprint}/index.json"
        )
        sixb_prefixes = {
            "s3_event_stream_with_fraud_6B": f"{oracle_root}/data/layer3/6B/s3_event_stream_with_fraud_6B/",
            "s4_event_labels_6B": f"{oracle_root}/data/layer3/6B/s4_event_labels_6B/",
            "s4_flow_truth_labels_6B": f"{oracle_root}/data/layer3/6B/s4_flow_truth_labels_6B/",
            "s4_flow_bank_view_6B": f"{oracle_root}/data/layer3/6B/s4_flow_bank_view_6B/",
            "s4_case_timeline_6B": f"{oracle_root}/data/layer3/6B/s4_case_timeline_6B/",
        }

    sixb_flag_hash = ""
    validation_status = ""
    validation_required: dict[str, str] = {}
    truth_prefix_presence: dict[str, bool] = {}
    if sixb_flag_uri and validation_uri and validation_index_uri:
        try:
            sixb_flag_hash = s3_read_text(s3, sixb_flag_uri).strip()
            validation_report = s3_read_json(s3, validation_uri)
            s3_read_json(s3, validation_index_uri)
            validation_status = str(validation_report.get("overall_status") or "").strip().upper()
            validation_required = map_checks(validation_report)
            if validation_status not in {"PASS", "WARN"}:
                blockers.append(f"PHASE5.B15_6B_STATUS_RED:{validation_status or 'UNSET'}")
            for check_name in (
                "REQ_UPSTREAM_HASHGATES",
                "REQ_FLOW_EVENT_PARITY",
                "REQ_FLOW_LABEL_COVERAGE",
                "REQ_CRITICAL_TRUTH_REALISM",
                "REQ_CRITICAL_CASE_TIMELINE",
            ):
                if validation_required.get(check_name) != "PASS":
                    blockers.append(f"PHASE5.B16_6B_REQUIRED_CHECK_RED:{check_name}")
            for key, prefix_uri in sixb_prefixes.items():
                truth_prefix_presence[key] = s3_prefix_has_objects(s3, prefix_uri)
                if not truth_prefix_presence[key]:
                    blockers.append(f"PHASE5.B17_6B_TRUTH_PREFIX_MISSING:{key}")
        except (BotoCoreError, ClientError, ValueError, KeyError, json.JSONDecodeError):
            blockers.append("PHASE5.B18_6B_GATE_UNREADABLE")

    managed_artifacts: dict[str, dict[str, Any]] = {}
    managed_sources = [
        ("m10b", args.m10b_execution_id, "m10b_execution_summary.json", "PHASE5.B19_M10B"),
        ("m10d", args.m10d_execution_id, "m10d_execution_summary.json", "PHASE5.B20_M10D"),
        ("m11f", args.m11f_execution_id, "m11f_execution_summary.json", "PHASE5.B21_M11F"),
        ("m11g", args.m11g_execution_id, "m11_model_operability_report.json", "PHASE5.B22_M11G"),
        ("m12b", args.m12b_execution_id, "m12b_execution_summary.json", "PHASE5.B23_M12B"),
        ("m12c", args.m12c_execution_id, "m12c_execution_summary.json", "PHASE5.B24_M12C"),
        ("m12d", args.m12d_execution_id, "m12d_execution_summary.json", "PHASE5.B25_M12D"),
        ("m12e", args.m12e_execution_id, "m12e_execution_summary.json", "PHASE5.B26_M12E"),
        ("m12f", args.m12f_execution_id, "m12f_execution_summary.json", "PHASE5.B27_M12F"),
        ("m12g", args.m12g_execution_id, "m12g_execution_summary.json", "PHASE5.B28_M12G"),
    ]
    for label, execution_id, filename, blocker_code in managed_sources:
        payload, path = require_local_green(execution_id, filename, blockers, blocker_code)
        managed_artifacts[label] = {
            "execution_id": execution_id,
            "artifact_path": path,
            "overall_pass": None if payload is None else check_summary_green(payload),
            "platform_run_id": "" if payload is None else str(payload.get("platform_run_id") or "").strip(),
        }

    m12d_event = None
    m12d_event_path = ""
    try:
        m12d_event_path = str(find_local_artifact(args.m12d_execution_id, "m12d_registry_lifecycle_event.json"))
        m12d_event = load_json(Path(m12d_event_path))
    except (FileNotFoundError, json.JSONDecodeError):
        blockers.append("PHASE5.B30_M12D_EVENT_UNREADABLE")

    m12f_snapshot = None
    m12f_snapshot_path = ""
    try:
        m12f_snapshot_path = str(find_local_artifact(args.m12f_execution_id, "m12f_active_resolution_snapshot.json"))
        m12f_snapshot = load_json(Path(m12f_snapshot_path))
    except (FileNotFoundError, json.JSONDecodeError):
        blockers.append("PHASE5.B31_M12F_SNAPSHOT_UNREADABLE")

    candidate_bundle_ref = ""
    if m12d_event is not None:
        candidate_bundle_ref = str((((m12d_event.get("bundle_ref") or {})).get("registry_ref")) or "").strip()
        if str(m12d_event.get("event_type") or "").strip().upper() != "BUNDLE_PROMOTED_ACTIVE":
            blockers.append("PHASE5.B32_M12D_EVENT_NOT_PROMOTED_ACTIVE")
    if m12f_snapshot is not None:
        if not bool((((m12f_snapshot.get("active_resolution") or {})).get("overall_pass"))):
            blockers.append("PHASE5.B33_M12F_ACTIVE_RESOLUTION_RED")
        if not bool((((m12f_snapshot.get("runtime_compatibility") or {})).get("overall_pass"))):
            blockers.append("PHASE5.B34_M12F_RUNTIME_COMPATIBILITY_RED")
        m12f_ref = str((((m12f_snapshot.get("refs") or {})).get("candidate_bundle_ref")) or "").strip()
        if candidate_bundle_ref and m12f_ref and candidate_bundle_ref != m12f_ref:
            blockers.append("PHASE5.B35_CANDIDATE_BUNDLE_REF_DRIFT")
        candidate_bundle_ref = candidate_bundle_ref or m12f_ref

    managed_platform_run_ids = sorted(
        {
            info["platform_run_id"]
            for info in managed_artifacts.values()
            if str(info.get("platform_run_id") or "").strip()
        }
    )
    if len(set(managed_platform_run_ids)) > 1:
        blockers.append("PHASE5.B36_MANAGED_CHAIN_PLATFORM_SCOPE_DRIFT")

    if not candidate_bundle_ref:
        blockers.append("PHASE5.B37_CANDIDATE_BUNDLE_REF_UNRESOLVED")
    else:
        notes.append("Managed candidate bundle truth remains attributable and stable through M12 promotion and active-resolution artifacts.")

    summary = {
        "phase": "PHASE5",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_execution_id": args.source_execution_id,
        "phase5a_execution_id": args.phase5a_execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "oracle_root": oracle_root,
        "manifest_fingerprint": manifest_fingerprint,
        "semantic_basis": {
            "facts_view_ref": facts_uri,
            "intended_outputs": intended_outputs,
            "output_roles": output_roles,
            "sixb_passed_flag_ref": sixb_flag_uri,
            "sixb_passed_flag_sha256_hex": sixb_flag_hash,
            "sixb_validation_report_ref": validation_uri,
            "sixb_validation_status": validation_status,
            "sixb_required_checks": validation_required,
            "truth_prefix_presence": truth_prefix_presence,
            "label_store_accepted": label_store_accepted,
            "label_store_pending": label_store_pending,
            "label_store_rejected": label_store_rejected,
            "case_mgmt_labels_accepted": case_mgmt_labels,
        },
        "managed_corridor": {
            "artifacts": managed_artifacts,
            "m12d_registry_lifecycle_event_path": m12d_event_path,
            "m12f_active_resolution_snapshot_path": m12f_snapshot_path,
            "candidate_bundle_ref": candidate_bundle_ref,
            "managed_platform_run_ids": managed_platform_run_ids,
        },
        "notes": notes,
        "blocker_ids": blockers,
        "open_blockers": len(blockers),
        "overall_pass": len(blockers) == 0,
    }
    receipt = {
        "phase": "PHASE5",
        "generated_at_utc": summary["generated_at_utc"],
        "execution_id": args.execution_id,
        "platform_run_id": platform_run_id,
        "verdict": "PHASE5_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_phase": "PHASE6" if len(blockers) == 0 else "PHASE5B_REMEDIATE",
        "open_blockers": len(blockers),
        "blocker_ids": blockers,
    }

    dump_json(run_root / str(args.summary_name).strip(), summary)
    dump_json(run_root / str(args.receipt_name).strip(), receipt)


if __name__ == "__main__":
    main()
