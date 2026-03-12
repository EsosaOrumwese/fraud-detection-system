#!/usr/bin/env python3
"""Run the rebuilt Phase 5.B Databricks-managed OFS dataset-basis proof."""

from __future__ import annotations

import argparse
import base64
import json
import re
import time
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


def s3_write_json(s3: Any, uri: str, payload: dict[str, Any]) -> None:
    bucket, key = parse_s3_uri(uri)
    body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


def s3_read_json(s3: Any, uri: str) -> dict[str, Any]:
    bucket, key = parse_s3_uri(uri)
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def read_ssm(ssm: Any, name: str, *, decrypt: bool) -> str:
    return str(ssm.get_parameter(Name=name, WithDecryption=decrypt)["Parameter"]["Value"]).strip()


def dbx_request_json(
    base_url: str,
    token: str,
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_string = ""
    if query:
        query_string = "?" + urllib.parse.urlencode(query, doseq=True)
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        url=f"{base_url.rstrip('/')}{path}{query_string}",
        method=method,
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8")
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("json_not_object")
    return parsed


def dbx_import_python_source(
    base_url: str,
    token: str,
    *,
    workspace_root: str,
    workspace_notebook_path: str,
    source_text: str,
) -> None:
    dbx_request_json(base_url, token, "POST", "/api/2.0/workspace/mkdirs", payload={"path": workspace_root})
    encoded = base64.b64encode(source_text.encode("utf-8")).decode("ascii")
    dbx_request_json(
        base_url,
        token,
        "POST",
        "/api/2.0/workspace/import",
        payload={
            "path": workspace_notebook_path,
            "format": "SOURCE",
            "language": "PYTHON",
            "content": encoded,
            "overwrite": True,
        },
    )


def dbx_find_job(base_url: str, token: str, job_name: str) -> dict[str, Any] | None:
    page_token = ""
    while True:
        query: dict[str, Any] = {"limit": 100}
        if page_token:
            query["page_token"] = page_token
        payload = dbx_request_json(base_url, token, "GET", "/api/2.1/jobs/list", query=query)
        for row in payload.get("jobs", []) or []:
            if str((row.get("settings") or {}).get("name") or "").strip() == job_name:
                return row
        page_token = str(payload.get("next_page_token") or "").strip()
        if not page_token:
            return None


def dbx_run_job(
    base_url: str,
    token: str,
    *,
    job_id: int,
    execution_token: str,
    notebook_params: dict[str, str],
    max_wait_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    run_now = dbx_request_json(
        base_url,
        token,
        "POST",
        "/api/2.1/jobs/run-now",
        payload={
            "job_id": int(job_id),
            "idempotency_token": execution_token,
            "notebook_params": notebook_params,
        },
    )
    run_id = int(run_now.get("run_id") or 0)
    if run_id <= 0:
        raise RuntimeError("phase5b_run_now_missing_run_id")

    terminal_states = {"TERMINATED", "SKIPPED", "INTERNAL_ERROR", "BLOCKED"}
    start = time.time()
    trace: list[dict[str, Any]] = []
    while True:
        run_payload = dbx_request_json(
            base_url,
            token,
            "GET",
            "/api/2.1/jobs/runs/get",
            query={"run_id": str(run_id)},
        )
        state = run_payload.get("state") or {}
        life_cycle = str((state or {}).get("life_cycle_state") or "").strip()
        result_state = str((state or {}).get("result_state") or "").strip()
        state_message = str((state or {}).get("state_message") or "").strip()
        trace.append(
            {
                "captured_at_utc": now_utc(),
                "life_cycle_state": life_cycle,
                "result_state": result_state,
                "state_message": state_message,
            }
        )
        if life_cycle in terminal_states:
            return {
                "run_id": run_id,
                "run_page_url": str(run_payload.get("run_page_url") or "").strip(),
                "life_cycle_state": life_cycle,
                "result_state": result_state,
                "state_message": state_message,
                "poll_trace_tail": trace[-10:],
            }
        if time.time() - start > max_wait_seconds:
            return {
                "run_id": run_id,
                "run_page_url": str(run_payload.get("run_page_url") or "").strip(),
                "life_cycle_state": "TIMEOUT",
                "result_state": "",
                "state_message": "timeout",
                "poll_trace_tail": trace[-10:],
            }
        time.sleep(max(1, poll_seconds))


def dbx_get_run_output(base_url: str, token: str, *, run_id: int) -> dict[str, Any]:
    return dbx_request_json(base_url, token, "GET", "/api/2.0/jobs/runs/get-output", query={"run_id": str(run_id)})


def list_first_key(s3: Any, prefix_uri: str) -> str:
    bucket, prefix = parse_s3_uri(prefix_uri)
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    keys = sorted(str(row.get("Key") or "") for row in response.get("Contents", []) or [] if str(row.get("Key") or "").endswith(".parquet"))
    if not keys:
        raise RuntimeError(f"phase5b_slice_missing:{prefix_uri}")
    return f"s3://{bucket}/{keys[0]}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the rebuilt Phase 5.B Databricks-managed OFS dataset-basis proof.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--phase5a-execution-id", required=True)
    ap.add_argument("--source-execution-id", default="phase4_case_label_coupled_20260312T003302Z")
    ap.add_argument("--phase5a-summary-name", default="phase5_learning_surface_summary.json")
    ap.add_argument("--source-bootstrap-name", default="phase4_control_plane_bootstrap.json")
    ap.add_argument("--summary-name", default="phase5_ofs_dataset_basis_summary.json")
    ap.add_argument("--receipt-name", default="phase5_ofs_dataset_basis_receipt.json")
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--max-wait-seconds", type=int, default=1800)
    ap.add_argument("--poll-seconds", type=int, default=15)
    args = ap.parse_args()

    registry = parse_registry(REGISTRY_PATH)
    run_root = Path(args.run_control_root) / args.execution_id
    phase5a_root = Path(args.run_control_root) / args.phase5a_execution_id
    source_root = Path(args.run_control_root) / args.source_execution_id

    phase5a_summary = load_json(phase5a_root / str(args.phase5a_summary_name).strip())
    source_bootstrap = load_json(source_root / str(args.source_bootstrap_name).strip())

    if not bool(phase5a_summary.get("overall_pass")):
        raise SystemExit("Phase 5.A must be green before Phase 5.B.")

    s3 = boto3.client("s3", region_name=args.aws_region)
    ssm = boto3.client("ssm", region_name=args.aws_region)

    dbx_workspace_url = read_ssm(ssm, str(registry.get("SSM_DATABRICKS_WORKSPACE_URL_PATH") or "").strip(), decrypt=False)
    dbx_token = read_ssm(ssm, str(registry.get("SSM_DATABRICKS_TOKEN_PATH") or "").strip(), decrypt=True)
    evidence_bucket = str(registry.get("S3_EVIDENCE_BUCKET") or "").strip()
    object_store_bucket = str(registry.get("S3_OBJECT_STORE_BUCKET") or "").strip()
    if not evidence_bucket or not object_store_bucket:
        raise SystemExit("Evidence/object-store buckets unresolved.")

    bootstrap_oracle = dict(source_bootstrap.get("oracle") or {})
    semantic = dict(phase5a_summary.get("semantic_admission") or {})
    upstream_truth = dict(phase5a_summary.get("upstream_truth") or {})
    facts_view_ref = str(semantic.get("facts_view_ref") or "").strip()
    facts_payload = s3_read_json(s3, facts_view_ref)
    pins = dict(facts_payload.get("pins") or {})
    manifest_fingerprint = str(semantic.get("manifest_fingerprint") or pins.get("manifest_fingerprint") or "").strip()
    parameter_hash = str(pins.get("parameter_hash") or "").strip()
    scenario_id = str(pins.get("scenario_id") or bootstrap_oracle.get("oracle_scenario_id") or "").strip()
    label_asof_utc = str(upstream_truth.get("label_asof_utc") or "").strip()
    oracle_root = str(semantic.get("oracle_root") or bootstrap_oracle.get("oracle_engine_run_root") or "").strip()
    if not facts_view_ref or not manifest_fingerprint or not parameter_hash or not scenario_id or not label_asof_utc or not oracle_root:
        raise SystemExit("Phase 5.B semantic basis unresolved.")

    sixb_root = (
        f"{oracle_root}/data/layer3/6B"
        f"/seed={pins.get('seed')}"
    )
    seed = str(pins.get("seed") or "").strip()
    if not seed:
        raise SystemExit("Phase 5.B seed unresolved.")
    base_prefix = (
        f"{oracle_root}/data/layer3/6B"
        f"/"
    )
    keyed_suffix = (
        f"seed={seed}/parameter_hash={parameter_hash}/"
        f"manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/"
    )
    events_prefix = f"{base_prefix}s3_event_stream_with_fraud_6B/{keyed_suffix}"
    event_labels_prefix = f"{base_prefix}s4_event_labels_6B/{keyed_suffix}"
    flow_truth_prefix = f"{base_prefix}s4_flow_truth_labels_6B/{keyed_suffix}"
    case_timeline_prefix = f"{base_prefix}s4_case_timeline_6B/{keyed_suffix}"

    spec = {
        "phase": "PHASE5",
        "subphase": "PHASE5B",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_execution_id": args.source_execution_id,
        "phase5a_execution_id": args.phase5a_execution_id,
        "platform_run_id": str(phase5a_summary.get("platform_run_id") or "").strip(),
        "scenario_run_id": str(phase5a_summary.get("scenario_run_id") or "").strip(),
        "facts_view_ref": facts_view_ref,
        "oracle_root": oracle_root,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "scenario_id": scenario_id,
        "label_asof_utc": label_asof_utc,
        "label_maturity_days": int(registry.get("LEARNING_LABEL_MATURITY_DAYS_DEFAULT") or 0),
        "sixb_passed_flag_ref": str(semantic.get("sixb_passed_flag_ref") or "").strip(),
        "sixb_validation_report_ref": str(semantic.get("sixb_validation_report_ref") or "").strip(),
        "allowed_outputs": ["s2_event_stream_baseline_6B", "s3_event_stream_with_fraud_6B"],
        "required_checks": [
            "REQ_UPSTREAM_HASHGATES",
            "REQ_FLOW_EVENT_PARITY",
            "REQ_FLOW_LABEL_COVERAGE",
            "REQ_CRITICAL_TRUTH_REALISM",
            "REQ_CRITICAL_CASE_TIMELINE",
        ],
        "slice_files": {
            "events": list_first_key(s3, events_prefix),
            "event_labels": list_first_key(s3, event_labels_prefix),
            "flow_truth_labels": list_first_key(s3, flow_truth_prefix),
            "case_timeline": list_first_key(s3, case_timeline_prefix),
        },
    }
    dump_json(run_root / "phase5b_ofs_spec.json", spec)
    spec_json = json.dumps(spec, ensure_ascii=True)

    workspace_root = str(registry.get("DBX_WORKSPACE_PROJECT_ROOT") or "/Shared/fraud-platform/dev_full").strip().rstrip("/")
    build_source = Path("platform/databricks/dev_full/ofs_build_v0.py").read_text(encoding="utf-8").strip() + "\n"
    quality_source = Path("platform/databricks/dev_full/ofs_quality_v0.py").read_text(encoding="utf-8").strip() + "\n"
    build_workspace_notebook = f"{workspace_root}/ofs_build_v0"
    quality_workspace_notebook = f"{workspace_root}/ofs_quality_v0"
    dbx_import_python_source(
        dbx_workspace_url,
        dbx_token,
        workspace_root=workspace_root,
        workspace_notebook_path=build_workspace_notebook,
        source_text=build_source,
    )
    dbx_import_python_source(
        dbx_workspace_url,
        dbx_token,
        workspace_root=workspace_root,
        workspace_notebook_path=quality_workspace_notebook,
        source_text=quality_source,
    )

    build_job = dbx_find_job(dbx_workspace_url, dbx_token, str(registry.get("DBX_JOB_OFS_BUILD_V0") or "").strip())
    quality_job = dbx_find_job(dbx_workspace_url, dbx_token, str(registry.get("DBX_JOB_OFS_QUALITY_GATES_V0") or "").strip())
    if not build_job or not quality_job:
        raise SystemExit("Phase 5.B Databricks jobs unresolved.")

    notebook_params = {
        "phase5_spec_json": spec_json,
    }
    build_run = dbx_run_job(
        dbx_workspace_url,
        dbx_token,
        job_id=int(build_job.get("job_id") or 0),
        execution_token=f"{args.execution_id}:build",
        notebook_params=notebook_params,
        max_wait_seconds=args.max_wait_seconds,
        poll_seconds=args.poll_seconds,
    )
    if build_run["life_cycle_state"] != "TERMINATED" or build_run["result_state"] != "SUCCESS":
        build_output = dbx_get_run_output(dbx_workspace_url, dbx_token, run_id=int(build_run["run_id"]))
        summary = {
            "phase": "PHASE5",
            "subphase": "PHASE5B",
            "generated_at_utc": now_utc(),
            "execution_id": args.execution_id,
            "platform_run_id": spec["platform_run_id"],
            "overall_pass": False,
            "blocker_ids": [f"PHASE5.B60_DATABRICKS_BUILD_RUN_RED:{build_run['life_cycle_state']}:{build_run['result_state']}"],
            "databricks": {"build_run": build_run, "build_output": build_output},
        }
        receipt = {
            "phase": "PHASE5",
            "generated_at_utc": summary["generated_at_utc"],
            "execution_id": args.execution_id,
            "platform_run_id": spec["platform_run_id"],
            "verdict": "HOLD_REMEDIATE",
            "next_phase": "PHASE5B_REMEDIATE",
            "open_blockers": 1,
            "blocker_ids": summary["blocker_ids"],
        }
        dump_json(run_root / str(args.summary_name).strip(), summary)
        dump_json(run_root / str(args.receipt_name).strip(), receipt)
        return

    build_output = dbx_get_run_output(dbx_workspace_url, dbx_token, run_id=int(build_run["run_id"]))
    build_result_raw = str((((build_output.get("notebook_output") or {}).get("result")) or "")).strip()
    if not build_result_raw:
        raise SystemExit("Phase 5.B build output missing notebook result.")
    build_snapshot = json.loads(build_result_raw)

    quality_params = {
        "phase5_spec_json": spec_json,
        "phase5_build_snapshot_json": json.dumps(build_snapshot, ensure_ascii=True),
    }
    quality_run = dbx_run_job(
        dbx_workspace_url,
        dbx_token,
        job_id=int(quality_job.get("job_id") or 0),
        execution_token=f"{args.execution_id}:quality",
        notebook_params=quality_params,
        max_wait_seconds=args.max_wait_seconds,
        poll_seconds=args.poll_seconds,
    )
    if quality_run["life_cycle_state"] != "TERMINATED" or quality_run["result_state"] != "SUCCESS":
        quality_output = dbx_get_run_output(dbx_workspace_url, dbx_token, run_id=int(quality_run["run_id"]))
        summary = {
            "phase": "PHASE5",
            "subphase": "PHASE5B",
            "generated_at_utc": now_utc(),
            "execution_id": args.execution_id,
            "platform_run_id": spec["platform_run_id"],
            "overall_pass": False,
            "blocker_ids": [f"PHASE5.B61_DATABRICKS_QUALITY_RUN_RED:{quality_run['life_cycle_state']}:{quality_run['result_state']}"],
            "databricks": {"build_run": build_run, "build_output": build_output, "quality_run": quality_run, "quality_output": quality_output},
        }
        receipt = {
            "phase": "PHASE5",
            "generated_at_utc": summary["generated_at_utc"],
            "execution_id": args.execution_id,
            "platform_run_id": spec["platform_run_id"],
            "verdict": "HOLD_REMEDIATE",
            "next_phase": "PHASE5B_REMEDIATE",
            "open_blockers": 1,
            "blocker_ids": summary["blocker_ids"],
        }
        dump_json(run_root / str(args.summary_name).strip(), summary)
        dump_json(run_root / str(args.receipt_name).strip(), receipt)
        return

    quality_output = dbx_get_run_output(dbx_workspace_url, dbx_token, run_id=int(quality_run["run_id"]))
    quality_result_raw = str((((quality_output.get("notebook_output") or {}).get("result")) or "")).strip()
    if not quality_result_raw:
        raise SystemExit("Phase 5.B quality output missing notebook result.")
    quality_snapshot = json.loads(quality_result_raw)
    blocker_ids = [str(item).strip() for item in (quality_snapshot.get("blocker_ids") or []) if str(item).strip()]

    summary = {
        "phase": "PHASE5",
        "subphase": "PHASE5B",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_execution_id": args.source_execution_id,
        "phase5a_execution_id": args.phase5a_execution_id,
        "platform_run_id": spec["platform_run_id"],
        "scenario_run_id": spec["scenario_run_id"],
        "overall_pass": len(blocker_ids) == 0,
        "blocker_ids": blocker_ids,
        "spec_ref": str(run_root / "phase5b_ofs_spec.json"),
        "databricks": {
            "build_job_id": int(build_job.get("job_id") or 0),
            "quality_job_id": int(quality_job.get("job_id") or 0),
            "build_run": build_run,
            "build_output": build_output,
            "quality_run": quality_run,
            "quality_output": quality_output,
        },
        "semantic_basis": build_snapshot.get("semantic_basis"),
        "slice_metrics": build_snapshot.get("slice_metrics"),
        "quality_gate": quality_snapshot,
        "assessment": quality_snapshot.get("assessment"),
    }
    receipt = {
        "phase": "PHASE5",
        "generated_at_utc": summary["generated_at_utc"],
        "execution_id": args.execution_id,
        "platform_run_id": spec["platform_run_id"],
        "verdict": "PHASE5B_READY" if len(blocker_ids) == 0 else "HOLD_REMEDIATE",
        "next_phase": "PHASE5C" if len(blocker_ids) == 0 else "PHASE5B_REMEDIATE",
        "open_blockers": len(blocker_ids),
        "blocker_ids": blocker_ids,
    }
    dump_json(run_root / str(args.summary_name).strip(), summary)
    dump_json(run_root / str(args.receipt_name).strip(), receipt)


if __name__ == "__main__":
    main()
